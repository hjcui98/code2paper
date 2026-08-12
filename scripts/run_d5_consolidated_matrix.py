#!/usr/bin/env python3
"""Consolidated Post-R8 D5 matrix runner for the four development projects.

Executes EBCAR, RAP, DyG, and LinearRAG serially through the real publication
pipeline from frozen D2.5 authority artifacts, under one exclusive endpoint
lease, with a runtime/queue ledger, code/profile/input digests, per-project
role-budget records, terminal aggregation, and checkpoint-bound resume.

Usage:
    CODE2PAPER_LLM_PROVIDER=openai python3 scripts/run_d5_consolidated_matrix.py \
        --manifest /tmp/code2paper-post-r8-d5-consolidated-20260804-1/matrix_manifest.json \
        --out-root /tmp/code2paper-post-r8-d5-consolidated-20260804-2 \
        [--projects ebcar,rap,dyg,linearrag] [--resume]
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

_PROJECT_ORDER = ("ebcar", "rap", "dyg", "linearrag")

_INPUT_FILE_KEYS = (
    ("atomic_claims_v3", "atomic_claims_v3_v3.json"),
    ("code_facts_v1", "code_facts_v1_v3.json"),
    ("equation_claims_v1", "equation_claims_v1_v3.json"),
    ("configuration_claims_v1", "configuration_claims_v1.json"),
    ("method_completeness_matrix_v1", "method_completeness_matrix_v1.json"),
    ("method_section_plan_v2", "method_section_plan_v2.json"),
    ("evidence_packets_v3", "evidence_packets_v3_v3.json"),
    ("reference_method_agenda_v1", "reference_method_agenda_v1.json"),
    ("obligation_coverage_v2", "obligation_coverage_v2.json"),
)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def digest_of(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def git_identity() -> dict[str, str]:
    """Bind tracked diff AND untracked working-tree content.

    ``git diff`` alone omits untracked files (the publication Writer, quality
    gate, matrix runner, and their tests are untracked in this worktree), so
    the identity hashes the content of every D5-relevant file under src/,
    scripts/, and tests/ that is tracked-with-changes or untracked.
    """

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff"], capture_output=True, text=True, check=False
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=False,
    ).stdout.splitlines()
    relevant = [
        name for name in untracked
        if name.startswith(("src/", "scripts/", "tests/"))
        and name.endswith((".py", ".json", ".env"))
    ]
    file_digests = {
        name: digest_bytes(Path(name).read_bytes())
        for name in sorted(relevant)
    }
    return {
        "git_head": head,
        "diff_sha256": digest_bytes(diff.encode("utf-8")),
        "untracked_file_digests": file_digests,
    }


def load_and_verify_manifest(manifest_path: Path) -> dict:
    """Load the frozen input manifest and verify every recorded file digest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for project_id, project in manifest.get("projects", {}).items():
        for name, info in project.get("files", {}).items():
            path = Path(info["path"])
            if not path.is_file():
                failures.append(f"{project_id}:{name}:missing:{path}")
                continue
            if digest_file(path) != info["digest"]:
                failures.append(f"{project_id}:{name}:digest_mismatch:{path}")
    if failures:
        raise ValueError("manifest verification failed: " + "; ".join(failures[:8]))
    return manifest


class EndpointLease:
    """Exclusive matrix lease over the shared local runtime."""

    def __init__(self, out_root: Path) -> None:
        self.path = out_root / "endpoint.lease"
        self._handle = None

    def acquire(self, owner: str) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.path, "a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            return False
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(json.dumps({
            "owner": owner,
            "acquired_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, ensure_ascii=False, indent=2) + "\n")
        self._handle.flush()
        return True

    def release(self) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self._handle.close()
            self._handle = None


def record_runtime_ledger(out_root: Path, key: str = "start") -> dict:
    """Record endpoint health/model/queue state without secrets.

    Each snapshot is preserved under ``runtime_ledger_<key>.json`` and
    appended to ``runtime_ledger.json`` so no pre-project record is
    overwritten.
    """
    ledger: dict = {
        "key": key,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "health": None,
        "models": [],
        "running": None,
        "waiting": None,
    }
    try:
        with urllib.request.urlopen("http://127.0.0.1:8003/health", timeout=10) as response:
            ledger["health"] = response.status
    except Exception as exc:  # noqa: BLE001 - diagnostics-only ledger
        ledger["health_error"] = str(exc)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8003/v1/models", timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            ledger["models"] = [item["id"] for item in payload.get("data", [])]
    except Exception as exc:  # noqa: BLE001
        ledger["models_error"] = str(exc)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8003/metrics", timeout=10) as response:
            for line in response.read().decode("utf-8").splitlines():
                if line.startswith("vllm:num_requests_running{"):
                    ledger["running"] = int(line.rsplit(" ", 1)[-1].split(".", 1)[0])
                elif line.startswith("vllm:num_requests_waiting{"):
                    ledger["waiting"] = int(line.rsplit(" ", 1)[-1].split(".", 1)[0])
    except Exception as exc:  # noqa: BLE001
        ledger["metrics_error"] = str(exc)
    safe_key = "".join(char if char.isalnum() else "_" for char in key)
    path = out_root / f"runtime_ledger_{safe_key}.json"
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    aggregate = out_root / "runtime_ledger.json"
    records: list[dict] = []
    if aggregate.is_file():
        try:
            existing = json.loads(aggregate.read_text(encoding="utf-8"))
            records = existing if isinstance(existing, list) else [existing]
        except (OSError, ValueError, json.JSONDecodeError):
            records = []
    records.append(ledger)
    aggregate.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return ledger


def role_budget_ledger(config) -> dict[str, Any]:
    """Record the effective role sampling/budget surface without secrets."""
    from code2paper.llm.role_config import (
        METHOD_WRITER,
        ROLE_GENERATION_CONFIGS,
        apply_role_config,
    )

    writer_config = apply_role_config(config, METHOD_WRITER)
    return {
        "provider": str(getattr(config.provider, "value", "")),
        "model": config.model,
        "base_max_output_tokens": config.max_output_tokens,
        "base_temperature": config.temperature,
        "writer_resolved_temperature": writer_config.temperature,
        "writer_resolved_max_output_tokens": writer_config.max_output_tokens,
        "writer_role_default_temperature": ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        "reasoning_effort": config.reasoning_effort,
        "thinking_token_budget": config.thinking_token_budget,
        "top_p": config.top_p,
        "top_k": config.top_k,
        "timeout_seconds": config.request_timeout_seconds,
        "editor_env": os.environ.get("CODE2PAPER_LLM_PUBLICATION_EDITOR_RESPONSE_MODE", ""),
        "writer_env": os.environ.get("CODE2PAPER_LLM_PUBLICATION_WRITER_RESPONSE_MODE", ""),
        "formalizer_env": os.environ.get("CODE2PAPER_LLM_PUBLICATION_FORMALIZER_RESPONSE_MODE", ""),
    }


def artifact_paths_for(project: dict, out_root: Path, project_id: str) -> dict[str, str]:
    """Build the writer input path map for one project from the manifest."""
    files = project["files"]
    paths = {
        key: files[filename]["path"]
        for key, filename in _INPUT_FILE_KEYS
        if filename in files
    }
    method_evidence = next(
        (info["path"] for name, info in files.items() if "method_evidence" in name),
        "",
    )
    if not method_evidence:
        method_evidence = str(out_root / f"{project_id}_method_evidence_for_final_validation.json")
        Path(method_evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(method_evidence).write_text(json.dumps({
            "project_id": project_id,
            "method_name": f"{project_id} Method",
            "method_goal": "Describe the repository implementation.",
            "implementation_scope": "repository snapshot",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["method_evidence"] = method_evidence
    return paths


def build_matrix_summary(project_results: dict[str, dict], out_root: Path) -> dict:
    """Aggregate per-project terminal fields into the matrix summary."""
    summary = {
        "schema_version": "1.0",
        "out_root": str(out_root),
        "projects": {},
        "aggregate": {
            "project_count": len(project_results),
            "all_safety_gates": all(
                item.get("safety_hard_gate") is True
                for item in project_results.values()
            ),
            "all_utility_gates": all(
                item.get("utility_gate") is True
                for item in project_results.values()
            ),
            "all_final_integrity_gates": all(
                item.get("final_integrity_gate") is True
                for item in project_results.values()
            ),
            "total_accepted_sections": sum(
                len(item.get("accepted_section_ids", []))
                for item in project_results.values()
            ),
            "total_incomplete_sections": sum(
                len(item.get("incomplete_section_ids", []))
                for item in project_results.values()
            ),
        },
    }
    for project_id, result in project_results.items():
        summary["projects"][project_id] = result
    path = out_root / "matrix_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--projects", default=",".join(_PROJECT_ORDER))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    manifest = load_and_verify_manifest(args.manifest)
    out_root = args.out_root.expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    code_identity = git_identity()
    # Fail closed when the frozen manifest's code identity does not match the
    # actual working-tree identity: the matrix may only run against the code
    # the manifest binds.
    manifest_identity = manifest.get("code_identity") or {}
    if (
        manifest_identity.get("git_head") != code_identity["git_head"]
        or manifest_identity.get("diff_sha256") != code_identity["diff_sha256"]
        or manifest_identity.get("untracked_file_digests") != code_identity["untracked_file_digests"]
    ):
        print(json.dumps({
            "error": "code_identity_mismatch",
            "manifest_identity": manifest_identity,
            "actual_identity": {k: v for k, v in code_identity.items() if k != "untracked_file_digests"},
        }, indent=2))
        return 2
    code_identity_digest = digest_of(json.dumps(code_identity, ensure_ascii=False, sort_keys=True))
    manifest_digest = digest_of(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    (out_root / "code_identity.json").write_text(
        json.dumps({**code_identity, "content_digest": code_identity_digest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_root / "matrix_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    owner = f"matrix:{time.strftime('%Y%m%d-%H%M%S')}"
    lease = EndpointLease(out_root)
    if not lease.acquire(owner):
        print(json.dumps({"error": "lease_unavailable"}, indent=2))
        return 2
    try:
        ledger = record_runtime_ledger(out_root)
        if ledger.get("health") != 200 or "qwen36-27b-nvfp4" not in ledger.get("models", []):
            print(json.dumps({"error": "endpoint_unavailable", "ledger": ledger}, indent=2))
            return 2
        selected = [pid for pid in args.projects.split(",") if pid] or list(_PROJECT_ORDER)
        project_results: dict[str, dict] = {}
        for project_id in selected:
            if project_id not in manifest["projects"]:
                print(json.dumps({"error": "unknown_project", "project": project_id}, indent=2))
                return 2
            started = time.time()
            if args.dry_run:
                project_results[project_id] = {
                    "status": "dry_run",
                    "project": project_id,
                    "input_files": sorted(manifest["projects"][project_id]["files"]),
                    "elapsed_seconds": 0.0,
                }
                continue
            idle = _wait_for_idle_queue(out_root, project_id=project_id)
            project_results[project_id] = run_one_project(
                project_id=project_id,
                project=manifest["projects"][project_id],
                out_root=out_root,
                resume=args.resume,
            )
            project_results[project_id]["elapsed_seconds"] = round(time.time() - started, 3)
            project_results[project_id]["pre_project_idle"] = idle
            record_runtime_ledger(out_root, key=f"after-{project_id}")
        summary = build_matrix_summary(project_results, out_root)
        summary["provenance"] = {
            "manifest_digest": manifest_digest,
            "code_identity_digest": code_identity_digest,
            "manifest_path": "matrix_manifest.json",
            "code_identity_path": "code_identity.json",
        }
        (out_root / "matrix_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        lease.release()


def run_one_project(
    *,
    project_id: str,
    project: dict,
    out_root: Path,
    resume: bool,
) -> dict:
    """Run the real publication pipeline for one project under the lease."""

    from code2paper.agentic.publication_method_writer import (
        PublicationWriterRunResultV1,
        fulfill_writing_research_callbacks,
        run_publication_method_writer,
    )
    from code2paper.llm.providers import load_llm_config_from_env

    project_root = out_root / project_id
    project_root.mkdir(parents=True, exist_ok=True)
    paths = artifact_paths_for(project, project_root, project_id)

    resume_section_ids: tuple[str, ...] = ()
    requested_section_ids: tuple[str, ...] = ()
    admitted_resume_section_ids: tuple[str, ...] = ()
    callback_artifacts: dict = {}
    if resume:
        result_path = project_root / "artifacts" / "06_authoring" / "publication_writer_result_v1.json"
        if result_path.is_file():
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            requested_section_ids = tuple(previous.get("incomplete_section_ids", ()))
            callback_path = project_root / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
            if callback_path.is_file():
                from code2paper.agentic.method_argument_models import (
                    WritingResearchCallbackBundleV1,
                )

                bundle_doc = json.loads(callback_path.read_text(encoding="utf-8"))
                try:
                    bundle_model = WritingResearchCallbackBundleV1.model_validate(bundle_doc)
                except (TypeError, ValueError):
                    bundle_model = None
                if bundle_model is not None:
                    requested = set(bundle_model.requested_resume_section_ids)
                    requested.update(requested_section_ids)
                    bundle_model = bundle_model.model_copy(update={
                        "requested_resume_section_ids": tuple(sorted(requested)),
                    })
                    # model_copy does not rerun validators; re-validate to
                    # recompute the content digest with the new field.
                    bundle_model = WritingResearchCallbackBundleV1.model_validate({
                        key: value for key, value in bundle_model.model_dump(mode="json").items()
                        if key != "content_digest"
                    })
                    callback_path.write_text(
                        bundle_model.model_dump_json(indent=2) + "\n",
                        encoding="utf-8",
                    )
                bundle_doc = json.loads(callback_path.read_text(encoding="utf-8"))
                callback_artifacts = _fulfilled_artifacts(bundle_doc)
                # The persisted bundle stores artifacts under artifact IDs;
                # normalize to request_id-keyed maps (the writer contract).
                normalized: dict[str, list] = {}
                for artifact in callback_artifacts.values():
                    request_id = str(artifact.get("request_id") or "")
                    if request_id:
                        normalized.setdefault(request_id, []).append(artifact)
                callback_artifacts = normalized
                auto = _execute_owned_route_artifacts(project, project_root, bundle_doc)
                for request_id, artifacts in auto.items():
                    callback_artifacts.setdefault(request_id, []).extend(artifacts)
                if callback_artifacts:
                    try:
                        fulfilled_bundle = fulfill_writing_research_callbacks(
                            callback_path, callback_artifacts
                        )
                    except (TypeError, ValueError, OSError):
                        fulfilled_bundle = None
                    if fulfilled_bundle is not None:
                        admitted_resume_section_ids = fulfilled_bundle.resume_section_ids
                        resume_section_ids = admitted_resume_section_ids

    config = load_llm_config_from_env()
    record_runtime_ledger(out_root, key=f"project-{project_id}-start")
    (project_root / "role_budgets.json").write_text(
        json.dumps(role_budget_ledger(config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if resume and not resume_section_ids:
        # Fail-closed resume admission: requested sections with unfulfilled
        # blocking local requests are never submitted to the Writer.  Zero
        # admitted sections means zero model calls and a blocked result.
        result = PublicationWriterRunResultV1(
            status="blocked",
            plan_digest="",
            claim_digest="",
            blocked_reason="writing_research_callback_artifacts_missing:no_admitted_sections",
        )
        summary = _resume_summary_fields(
            project_id=project_id,
            result=result,
            out_root=out_root,
            project_root=project_root,
            requested_resume_section_ids=requested_section_ids,
            admitted_resume_section_ids=admitted_resume_section_ids,
            quality_path=None,
            validation_path=None,
            writer_aggregate=None,
            bundle_doc=None,
            outputs={},
        )
        (project_root / "project_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return summary
    result, outputs = run_publication_method_writer(
        out_root=project_root,
        artifact_paths=paths,
        llm_config=config,
        resume_section_ids=resume_section_ids,
        research_callback_artifacts=callback_artifacts,
        formalization_caller=_formalization_caller,
        architect_proposal_caller=_architect_proposal_caller(config),
        rebuild_architect_plan=True,
    )
    record_runtime_ledger(out_root, key=f"project-{project_id}-end")

    quality_path = Path(outputs.get("publication_quality_report_v1", ""))
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else {}
    validation_path = Path(outputs.get("text_evidence_validation", ""))
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}
    writer_aggregate = result.writer_aggregate or {}
    bundle_doc: dict = {}
    bundle_path = project_root / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json"
    if bundle_path.is_file():
        try:
            bundle_doc = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            bundle_doc = {}
    summary = _resume_summary_fields(
        project_id=project_id,
        result=result,
        out_root=out_root,
        project_root=project_root,
        requested_resume_section_ids=requested_section_ids if resume else (),
        admitted_resume_section_ids=admitted_resume_section_ids,
        quality_path=quality_path,
        validation_path=validation_path,
        writer_aggregate=writer_aggregate,
        bundle_doc=bundle_doc,
        outputs=outputs,
    )
    (project_root / "project_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def _resume_summary_fields(
    *,
    project_id: str,
    result: PublicationWriterRunResultV1,
    out_root: Path,
    project_root: Path,
    requested_resume_section_ids: tuple[str, ...],
    admitted_resume_section_ids: tuple[str, ...],
    quality_path: Path | None,
    validation_path: Path | None,
    writer_aggregate: dict | None,
    bundle_doc: dict | None,
    outputs: dict,
) -> dict:
    """Build the per-project summary with truthful resume telemetry.

    ``requested`` are the sections the previous run asked to resume;
    ``admitted`` are the sections whose blocking locally owned requests are
    all fulfilled (measured before Writer); ``writer_regenerated`` are the
    sections the Writer actually regenerated this run (zero traces -> zero
    regenerated); ``blocked_before_writer`` = requested - admitted.
    """

    quality = {}
    validation = {}
    if quality_path is not None and quality_path.is_file():
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    if validation_path is not None and validation_path.is_file():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    writer_aggregate = writer_aggregate or {}
    bundle_doc = bundle_doc or {}
    if not requested_resume_section_ids:
        requested_resume_section_ids = tuple(bundle_doc.get("requested_resume_section_ids") or ())
    regenerated_section_ids = tuple(result.resumed_section_ids or ())
    traces = tuple(writer_aggregate.get("traces", []) or ())
    writer_model_call_delta = len(traces)
    blocked_before_writer_section_ids = tuple(sorted(
        set(requested_resume_section_ids) - set(admitted_resume_section_ids)
    ))
    return {
        "project": project_id,
        "status": result.status,
        "blocked_reason": result.blocked_reason,
        "accepted_section_ids": list(result.accepted_section_ids),
        "incomplete_section_ids": list(result.incomplete_section_ids),
        "binding_failures": list(result.binding_failures),
        "resumed_section_ids": list(regenerated_section_ids),
        "requested_resume_section_ids": list(requested_resume_section_ids),
        "admitted_resume_section_ids": list(admitted_resume_section_ids),
        "writer_regenerated_section_ids": list(regenerated_section_ids),
        "blocked_before_writer_section_ids": list(blocked_before_writer_section_ids),
        "writer_model_call_delta": writer_model_call_delta,
        "unchanged_unaffected_checkpoint_digests": _unaffected_digests(
            project_root / "artifacts" / "06_authoring" / "immutable_section_checkpoints",
            set(regenerated_section_ids),
        ),
        "unchanged_unaffected_output_digests": _unaffected_output_digests(
            project_root,
            set(regenerated_section_ids),
        ),
        "final_text_validation_status": quality.get("safety", {}).get("final_text_validation_status", ""),
        "safety_hard_gate": quality.get("safety", {}).get("hard_gate_passed", False),
        "unsupported_positive_claims": quality.get("safety", {}).get("unsupported_positive_claims", 0),
        "utility_gate": quality.get("utility", {}).get("utility_gate_passed", False),
        "final_integrity_gate": quality.get("final_integrity_gate_passed", False),
        "duplicate_information_rate": quality.get("utility", {}).get("duplicate_information_rate", 0.0),
        "equation_coverage": quality.get("utility", {}).get("equation_coverage", 0.0),
        "supported_unit_recall": quality.get("utility", {}).get("supported_unit_recall", 0.0),
        "argument_move_coverage": quality.get("utility", {}).get("argument_move_coverage", 0.0),
        "content_role_status": quality.get("utility", {}).get("content_role_status", {}),
        "cumulative_budget_consumed": writer_aggregate.get("cumulative_budget_consumed"),
        "cumulative_budget_cap": writer_aggregate.get("cumulative_budget_cap"),
        "generation_trace_count": len(writer_aggregate.get("traces", [])),
        "response_recovery_trace_count": len(result.response_recovery_traces),
        "formalization_agent_result": bool(outputs.get("formalization_agent_result_v1", "")),
        "architect_trace": bool(outputs.get("method_architect_trace_v1", "")),
        "checked_factual_claims": validation.get("checked_factual_claims"),
        "supported_claims": validation.get("supported_claims"),
        "unsupported_claims": validation.get("unsupported_claims"),
        "unverified_claims": validation.get("unverified_claims"),
        "outputs": outputs,
    }


def _unaffected_digests(checkpoint_dir: Path, regenerated_section_ids: set[str]) -> dict[str, str]:
    """Digest map of unaffected immutable section checkpoints (byte-identical)."""

    digests: dict[str, str] = {}
    if not checkpoint_dir.is_dir():
        return digests
    for path in sorted(checkpoint_dir.iterdir()):
        if not path.is_file():
            continue
        section_id = str(path.name)
        for suffix in (".json", ""):
            if section_id.endswith(suffix):
                section_id = section_id[: -len(suffix)]
                break
        if section_id in regenerated_section_ids:
            continue
        digests[section_id] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _unaffected_output_digests(project_root: Path, regenerated_section_ids: set[str]) -> dict[str, str]:
    """Output digest map of unaffected sections' per-section quality rows.

    The per-section authoring outputs live in the writer aggregate; for
    sections that were not regenerated the runner reports their prior
    checkpoint digest as the unchanged-output evidence.
    """

    digests: dict[str, str] = {}
    checkpoint_dir = project_root / "artifacts" / "06_authoring" / "immutable_section_checkpoints"
    if not checkpoint_dir.is_dir():
        return digests
    for path in sorted(checkpoint_dir.iterdir()):
        if not path.is_file():
            continue
        section_id = str(path.name)
        for suffix in (".json", ""):
            if section_id.endswith(suffix):
                section_id = section_id[: -len(suffix)]
                break
        if section_id in regenerated_section_ids:
            continue
        digests[section_id] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def _formalization_caller(config, request):
    """Real Formalization Agent caller with a json_object override.

    Mirrors the Writer/Editor live-caller pattern: the tracked capability
    profile defaults to native json_schema, but the loopback qwen36 model is
    far more reliable in json_object mode.  The deterministic guards remain
    the authority either way.
    """
    from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
    from code2paper.llm.client import LLMClient

    mode = os.environ.get(
        "CODE2PAPER_LLM_PUBLICATION_FORMALIZER_RESPONSE_MODE", ""
    ).strip()
    if not mode:
        mode = os.environ.get("CODE2PAPER_LLM_PUBLICATION_WRITER_RESPONSE_MODE", "json_object")
    try:
        response_mode = StructuredResponseMode(mode)
    except ValueError:
        response_mode = StructuredResponseMode.JSON_OBJECT
    profile = load_capability_profile(
        provider=getattr(config.provider, "value", str(config.provider)),
        model=config.model,
    ).model_copy(update={"response_mode": response_mode})
    return LLMClient(config, capability_profile=profile).complete(request)


def _architect_proposal_caller(config, proposal_caller_env_override: str = "") -> object:
    """Build the bounded closed-ID Architect proposal caller.

    The caller builds a small structured prompt that offers ONLY the existing
    closed unit/section/move IDs and asks the Architect to select one.  It may
    not invent units, moves, claims, facts, or authority.  When no proposal
    env/mode override is set, the caller returns None (deterministic closed
    bindings only) and ambiguous rows stay typed ``unplaced``.
    """

    from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
    from code2paper.llm.client import LLMClient, LLMRequest

    mode = (proposal_caller_env_override or
            os.environ.get("CODE2PAPER_LLM_PUBLICATION_ARCHITECT_PROPOSAL_RESPONSE_MODE", ""))
    if not mode:
        return None
    try:
        response_mode = StructuredResponseMode(mode)
    except ValueError:
        response_mode = StructuredResponseMode.JSON_OBJECT

    def caller(obligation_id, targets, sections, moves):
        prompt = {
            "task": (
                "Select the single best existing argument unit for the unresolved "
                "obligation. Choose only from the offered closed IDs."
            ),
            "obligation_id": obligation_id,
            "candidate_argument_units": targets,
            "candidate_sections": sections,
            "required_move": moves[0] if moves else "",
            "instruction": (
                "Return exactly one of the candidate argument_unit_id values. "
                "Do not invent any ID, claim, fact, or move."
            ),
        }
        schema = {
            "type": "object",
            "properties": {
                "argument_unit_id": {"type": "string", "enum": targets},
                "rationale": {"type": "string"},
            },
            "required": ["argument_unit_id"],
        }
        profile = load_capability_profile(
            provider=getattr(config.provider, "value", str(config.provider)),
            model=config.model,
        ).model_copy(update={"response_mode": response_mode})
        request = LLMRequest(
            prompt=json.dumps(prompt, ensure_ascii=False),
            prompt_template_id="phase5_architect_closed_id_proposal_v1",
            schema_name="architect_closed_id_proposal_v1",
            response_json_schema=schema,
            role="authoring_planner",
        )
        try:
            response = LLMClient(config, capability_profile=profile).complete(request)
        except Exception:
            return None
        payload = getattr(response, "parsed_payload", None) or {}
        if not isinstance(payload, dict):
            return None
        choice = str(payload.get("argument_unit_id") or "").strip()
        return choice if choice in targets else None

    return caller


def _repository_route_provider(project: dict):
    """Fulfill repository routes from the frozen code-fact authority.

    A repository request names the missing authority content; the frozen
    code facts are the repository authority available to the task.  The
    provider matches the request's candidate symbols/terms against the frozen
    fact vocabulary and returns a digest-pinned artifact when an exact match
    exists.  No match means the request genuinely stays pending.
    """
    from code2paper.agentic.evidence_compiler_v3 import load_code_facts_v1

    fact_path = project.get("files", {}).get("code_facts_v1_v3.json", {}).get("path", "")
    if not fact_path:
        return None
    try:
        facts = load_code_facts_v1(fact_path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    fact_index: dict[str, dict] = {}
    for fact in facts.facts:
        tokens = " ".join([
            str(fact.subject), str(fact.predicate),
            *([str(item) for item in fact.object] if isinstance(fact.object, list) else [str(fact.object)]),
        ]).lower()
        fact_index[fact.fact_id] = {
            "tokens": set(t for t in tokens.split() if len(t) > 2),
            "digest": fact.canonical_identity,
        }

    def provider(request) -> dict | None:
        # Exact-candidate matching: a provider may fulfill only when one of the
        # request's exact semantic candidates equals the fact subject or an
        # operand token (whole-token equality; symbols keep their qualified
        # form because fact vocab is whitespace-tokenized).  Fuzzy vocabulary
        # overlap or an unrelated fact in the same unit cannot satisfy it.
        exact_candidates = {
            str(term).strip().lower() for term in request.candidate_symbols_or_terms
            if len(str(term).strip()) > 2
        }
        best: str | None = None
        best_score = 0
        for fact_id, entry in fact_index.items():
            exact_hits = len(exact_candidates & entry["tokens"])
            if exact_hits > best_score:
                best = fact_id
                best_score = exact_hits
        if best is None or best_score == 0:
            return None
        return {
            "artifact_id": f"fact:{best}",
            "authority_lane": "executable_hard",
            "artifact_ref": best,
            "artifact_digest": fact_index[best]["digest"],
        }

    return provider


def _wait_for_idle_queue(out_root: Path, project_id: str, timeout_seconds: int = 120) -> dict:
    """Wait for an idle pre-project queue; preserve evidence either way.

    A nonzero running/waiting metric before a project could be a competing
    request or stale telemetry.  We wait up to ``timeout_seconds`` for an idle
    snapshot; the observed state is recorded in the project summary so the
    load surface is auditable rather than silently accepted.
    """

    deadline = time.time() + timeout_seconds
    last: dict = {"running": None, "waiting": None, "idle_observed": False}
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8003/metrics", timeout=10) as response:
                running = waiting = None
                for line in response.read().decode("utf-8").splitlines():
                    if line.startswith("vllm:num_requests_running{"):
                        running = int(line.rsplit(" ", 1)[-1].split(".", 1)[0])
                    elif line.startswith("vllm:num_requests_waiting{"):
                        waiting = int(line.rsplit(" ", 1)[-1].split(".", 1)[0])
            last = {"running": running, "waiting": waiting, "idle_observed": True}
            if not running and not waiting:
                return last
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            last = {"running": None, "waiting": None, "idle_error": str(exc)}
        time.sleep(10)
    last["idle_observed"] = bool(not last.get("running") and not last.get("waiting"))
    return last


def _fulfilled_artifacts(bundle: dict) -> dict[str, dict]:
    """Rebuild the fulfilled-artifact map from a persisted callback bundle."""
    artifacts: dict[str, dict] = {}
    for request in bundle.get("requests", []):
        for artifact_id in request.get("fulfilled_artifact_ids", []):
            for artifact in bundle.get("artifacts", {}).get(request.get("request_id", ""), []):
                if artifact.get("artifact_id") == artifact_id:
                    artifacts[artifact_id] = artifact
    return artifacts


def _execute_owned_route_artifacts(
    project: dict,
    project_root: Path,
    bundle: dict,
) -> dict[str, list[dict]]:
    """Auto-fulfill owned routes (repository/configuration/formalization).

    Repository routes are fulfilled from the frozen code-fact authority when
    the request's candidate terms match a fact; configuration routes match the
    frozen configuration claims; the formalization route binds the persisted
    Formalization result digest.  Author/empirical/literature lanes remain in
    their external queues.  The Writer still validates every artifact binding.
    """
    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        WritingResearchRequestV1,
    )
    from code2paper.agentic.writer_research_router import execute_open_requests_for_routes

    configuration_claims = None
    config_path = project.get("files", {}).get("configuration_claims_v1.json", {}).get("path", "")
    if config_path:
        try:
            configuration_claims = ConfigurationClaimSetV1.model_validate_json(
                Path(config_path).read_text(encoding="utf-8")
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            configuration_claims = None
    formalization = None
    formalization_path = project_root / "artifacts" / "06_authoring" / "formalization_result_v1.json"
    if formalization_path.is_file():
        try:
            from code2paper.agentic.formalization_agent import FormalizationResultV1

            formalization = FormalizationResultV1.model_validate_json(
                formalization_path.read_text(encoding="utf-8")
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            formalization = None
    requests = []
    for raw in bundle.get("requests", []):
        try:
            requests.append(WritingResearchRequestV1.model_validate(raw))
        except (TypeError, ValueError):
            continue
    executed = execute_open_requests_for_routes(
        requests,
        configuration_claims=configuration_claims,
        formalization=formalization,
        repository_provider=_repository_route_provider(project),
    )
    return {
        request_id: [item.model_dump(mode="json") for item in items]
        for request_id, items in executed.items()
    }


if __name__ == "__main__":
    raise SystemExit(main())
