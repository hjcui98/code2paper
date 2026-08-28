#!/usr/bin/env python3
"""Replay the authoring/validation surface on frozen research artifacts.

Plan 16.3.1/16.3.2: reuse frozen research evidence (snapshot + digest
checks enforced by the writer's own gates), regenerate Writer/Editor/
Rewrite, candidate, verified and validation artifacts in a fresh root.
The read-only summarizer is ``scripts/run_agentic_product_probe.py
--summarize-only``.

R3/R4 contract:
- a persisted callback bundle is only a list of digest-pinned refs; every
  referenced file is copied into the fresh root (traversal-safe), its
  digest revalidated, and its relative reference rebased.  Reuse is
  reported distinctly (``reused_fulfilled_callback_ids``) from a new
  resume event (``writer_resumed_section_ids``).  Any missing, escaping,
  symlinked, or digest-mismatched artifact fails the replay closed.
- every replay writes ``execution_record.json`` (exact command, exit code,
  code-state digest, pre/post runtime ledger keys) next to the fresh root.
- the shared product-authoring overlay is persisted as
  ``artifacts/06_authoring/product_authoring_state_v1.json`` and its digest is
  included in replay telemetry.

WP0 (2026-08-20): clean replays copy only research/author authority and
rebuild derived authoring when ``--rebuild-authoring`` is set.  Old plan,
concept cards, and callbacks are not silently copied unless explicitly
requested via ``--reuse-authoring-callbacks``.

Usage: run_authoring_replay.py <frozen-root> <fresh-root> [--resume MA-S2]
       [--repo <repo-path>] [--callback-rounds N] [--callback-tool-turns N]
       [--rebuild-authoring] [--reuse-authoring-callbacks]
       [--persist-authoring-rebuild-manifest]

When ``--repo`` is given and the replay exposes an open authoring issue, local
callbacks are fulfilled through the Research LangGraph.  A persisted
``research_stage_checkpoint_v1.json`` restores the original thread; otherwise
the replay records a ``ResearchContinuationSeedV1`` reconstructed from frozen
authority and starts a new, explicitly scoped continuation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
_SCRIPTS = _ROOT / "scripts"
for _entry in (_SRC, _SCRIPTS):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

# Research / author authority copied by default (WP0 copy boundary).
RESEARCH_COPY_ARTIFACTS = (
    "intent_obligation_graph_v2",
    "research_agenda_v1",
    "method_evidence",
    "claim_evidence_map",
    "obligation_coverage_v2",
    "reference_method_agenda_v1",
    "method_completeness_matrix_v1",
    "equation_claims_v1",
    "configuration_claims_v1",
    "evidence_packets_v3",
    "code_facts_v1",
    "atomic_claims_v3",
)

# Derived authoring artifacts: never copied unless legacy compatibility is
# explicitly requested (tests guard this list).
DERIVED_AUTHORING_ARTIFACTS = (
    "authoring_projection_v1",
    "method_section_plan_v2",
    "method_argument_briefs_v1",
    "method_concept_cards_v1",
    "method_propositions_v1",
    "method_proposition_bindings_v1",
    "method_proposition_clusters_v1",
    "writing_research_callback_artifacts_v1",
    "method_argument_facets_v1",
    "facet_evidence_alignments_v1",
    "candidate_facet_policies_v1",
    "method_argument_facet_alignment_trace_v1",
    "publication_paragraph_transaction_assessments_v1",
    "authoring_structural_exit_v1",
)

# Back-compat alias used by focused tests.
FROZEN_ARTIFACTS = RESEARCH_COPY_ARTIFACTS

OPTIONAL_RESEARCH_ARTIFACTS = (
    "behavior_graph_v1",
    "research_stage_checkpoint_v1",
)

OPTIONAL_FROZEN_ARTIFACTS = OPTIONAL_RESEARCH_ARTIFACTS

RESEARCH_STAGE_CHECKPOINT_CANDIDATES = (
    "artifacts/research_product/research_stage_checkpoint_v1.json",
    "artifacts/research_stage_checkpoint_v1.json",
)


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _code_state_digest() -> str:
    """Deterministic read-only binding of the code state used for this batch.

    Hashes the sorted relative path plus content digest of every ``.py``
    file under ``src/``; no git command and no working-tree mutation.
    """

    digests: list[str] = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(_ROOT))
        content_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests.append(f"{relative}:{content_digest}")
    payload = "\n".join(digests).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _execution_manifest_digest(
    *,
    profile_path: Path,
    frozen: Path,
    copied_artifact_names: tuple[str, ...],
) -> str:
    """Bind replay script, profile, frozen inputs, and code manifest."""

    parts = [
        f"replay_script:{_digest_file(Path(__file__).resolve())}",
        f"code_state:{_code_state_digest()}",
    ]
    if profile_path.is_file():
        parts.append(f"profile:{_digest_file(profile_path)}")
    else:
        parts.append("profile:missing")
    for name in sorted(copied_artifact_names):
        candidates = [
            frozen / "artifacts" / f"{name}.json",
            frozen / "artifacts" / "06_authoring" / f"{name}.json",
        ]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            parts.append(f"frozen:{name}:missing")
        else:
            parts.append(f"frozen:{name}:{_digest_file(source)}")
    return _digest_text("\n".join(parts))


def _apply_live_profile(profile: str | Path) -> None:
    """Load a live ``.env`` profile without expanding secrets-bearing ``$`` values."""

    path = Path(profile)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = line.removeprefix("export ").strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and not key.startswith("_") and value and "$" not in value:
            os.environ[key] = value


def _write_execution_record(
    *,
    frozen: Path,
    fresh: Path,
    arguments: argparse.Namespace,
    exit_code: int,
    runtime_start: dict | None,
    runtime_end: dict | None,
    telemetry: dict,
) -> None:
    """Persist the durable R4 execution record without secrets."""

    record = {
        "schema_version": "1.0",
        "run_id": arguments.run_id,
        "command": " ".join(sys.argv),
        "argv": list(sys.argv),
        "exit_code": exit_code,
        "frozen_root": str(frozen),
        "fresh_root": str(fresh),
        "resume_section_ids": list(arguments.resume),
        "code_state_digest": _code_state_digest(),
        "runtime": {
            "start": runtime_start or {},
            "end": runtime_end or {},
        },
        "reused_fulfilled_callback_ids": telemetry.get(
            "reused_fulfilled_callback_ids", []
        ),
        "writer_resumed_section_ids": telemetry.get(
            "writer_resumed_section_ids", []
        ),
        "writer_status": telemetry.get("writer_status", ""),
        "writer_blocked_reason": telemetry.get("writer_blocked_reason", ""),
        "candidate_digest": telemetry.get("candidate_digest", ""),
        "research_continuation_seed": telemetry.get(
            "research_continuation_seed", {}
        ),
        "callback_fulfillment": telemetry.get("callback_fulfillment", {}),
        "product_authoring_state": telemetry.get(
            "product_authoring_state", {}
        ),
        "content_chain": telemetry.get("content_chain", {}),
        "structural_exit": telemetry.get("structural_exit", {}),
    }
    fresh.mkdir(parents=True, exist_ok=True)
    (fresh / "execution_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _candidate_digest_for_root(fresh: Path) -> str:
    from code2paper.agentic.publication_method_writer import _incumbent_candidate_digest

    return _incumbent_candidate_digest(fresh)


def _record_product_authoring_state(
    *,
    fresh: Path,
    paths: dict[str, str],
    telemetry: dict,
) -> None:
    """Expose the shared product graph checkpoint in replay telemetry."""

    path_value = str(
        paths.get("product_authoring_state_v1")
        or _find_fresh_artifact(fresh, "product_authoring_state_v1")
        or ""
    ).strip()
    if not path_value:
        return
    path = Path(path_value)
    if not path.is_file():
        return
    telemetry["product_authoring_state"] = {
        "path": str(path),
        "digest": _digest_file(path),
    }


def _record_method_content_trace(
    *,
    fresh: Path,
    artifact_paths: dict[str, str],
    telemetry: dict[str, Any],
) -> str:
    """Persist the source-to-render ledger for a replay after its final writer state.

    The autonomous runner writes this ledger itself, but ``run_authoring_replay``
    calls the Writer directly.  Keeping the same builder here makes replay
    artifacts comparable without copying a stale trace from the frozen root.
    """

    from code2paper.agentic.method_content_trace import write_method_content_trace

    trace_path = fresh / "artifacts" / "research_product" / "method_content_trace_v1.json"
    trace = write_method_content_trace(trace_path, artifact_paths)
    telemetry["content_chain"] = {
        **trace.summary,
        "content_digest": trace.content_digest,
        "trace_path": str(trace_path),
    }
    return str(trace_path)


def _load_artifact_payload(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _record_authoring_structural_exit(
    *,
    fresh: Path,
    paths: dict[str, str],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Persist the fail-closed callback=1 structural authorization receipt."""

    from code2paper.agentic.callback_semantic_contract import (
        evaluate_authoring_structural_exit,
    )
    from code2paper.core.output_names import method_output

    plan_path = paths.get("method_section_plan_v2") or _find_fresh_artifact(
        fresh, "method_section_plan_v2"
    )
    trace_path = paths.get("method_content_trace_v1") or _find_fresh_artifact(
        fresh, "method_content_trace_v1"
    )
    writer_path = paths.get("publication_writer_result_v1") or _find_fresh_artifact(
        fresh, "publication_writer_result_v1"
    )
    formalization_path = paths.get("formalization_section_results_v1") or _find_fresh_artifact(
        fresh, "formalization_section_results_v1"
    )
    assessment_path = paths.get(
        "publication_paragraph_transaction_assessments_v1"
    ) or _find_fresh_artifact(
        fresh, "publication_paragraph_transaction_assessments_v1"
    )
    callback_path = paths.get("writing_research_callback_artifacts_v1") or _find_fresh_artifact(
        fresh, "writing_research_callback_artifacts_v1"
    )
    decision = evaluate_authoring_structural_exit(
        plan_payload=_load_artifact_payload(plan_path),
        trace_payload=_load_artifact_payload(trace_path),
        writer_payload=_load_artifact_payload(writer_path),
        formalization_payload=_load_artifact_payload(formalization_path),
        callback_payload=_load_artifact_payload(callback_path),
        assessment_payload=_load_artifact_payload(assessment_path),
        candidate_digest=str(telemetry.get("candidate_digest") or ""),
    )
    exit_path = method_output(fresh, "authoring_structural_exit_v1")
    exit_path.parent.mkdir(parents=True, exist_ok=True)
    exit_path.write_text(decision.model_dump_json(indent=2) + "\n", encoding="utf-8")
    paths["authoring_structural_exit_v1"] = str(exit_path)
    telemetry["structural_exit"] = {
        "path": str(exit_path),
        **decision.model_dump(mode="json"),
    }
    print(
        "[replay] structural exit: "
        f"eligible={decision.eligible} reasons={list(decision.reasons)} "
        f"targets={decision.valid_targets}/{decision.required_targets} "
        f"formula={decision.consumed_formula_packages}/{decision.accepted_formula_packages}"
    )
    return decision.model_dump(mode="json")


def _write_authoring_rebuild_manifest(
    *,
    fresh: Path,
    entries: list[dict[str, Any]],
    execution_digest: str,
    refused_reason: str = "",
) -> None:
    payload = {
        "schema_version": "1.0",
        "execution_digest": execution_digest,
        "refused_reason": refused_reason,
        "artifacts": entries,
    }
    payload["content_digest"] = _digest_text(
        json.dumps(
            {key: value for key, value in payload.items() if key != "content_digest"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    path = fresh / "artifacts" / "authoring_rebuild_manifest_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _manifest_entry(
    *,
    name: str,
    path: Path,
    authority_class: str,
    decision: str,
    reason: str = "",
) -> dict[str, Any]:
    schema = name
    digest = _digest_file(path) if path.is_file() else ""
    return {
        "artifact_name": name,
        "path": str(path),
        "digest": digest,
        "schema": schema,
        "authority_class": authority_class,
        "decision": decision,
        "reason": reason,
    }


def _method_evidence_rebuild_template(
    *,
    artifacts: Path,
    intent_graph: Any,
    claims: Any,
) -> Any:
    """Build the MethodEvidence identity template for authoring rebuild.

    Frozen research may already carry a valid ``method_evidence.json``.  Snapshot
    fields ``repo_snapshot_id`` / ``project_tree_hash`` are claims identity, not
    MethodEvidence fields, and must never be passed through as extra inputs.
    """

    from pydantic import ValidationError

    from code2paper.core.schemas import MethodEvidence

    method_name = str(
        getattr(intent_graph, "method_goal", "") or getattr(intent_graph, "project_goal", "") or "Method"
    ).strip() or "Method"
    method_goal = str(
        getattr(intent_graph, "method_goal", "")
        or getattr(intent_graph, "project_goal", "")
        or "Describe the repository implementation."
    ).strip() or "Describe the repository implementation."
    implementation_scope = str(
        getattr(intent_graph, "implementation_scope", "") or "current repository implementation"
    ).strip() or "current repository implementation"
    project_id = str(getattr(claims, "repo_snapshot_id", "") or "").strip() or "repo:unknown"
    copied_path = artifacts / "method_evidence.json"
    if copied_path.is_file():
        try:
            raw = json.loads(copied_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            adapted = dict(raw)
            snapshot_id = str(
                adapted.pop("repo_snapshot_id", "") or project_id
            ).strip()
            adapted.pop("project_tree_hash", None)
            if not str(adapted.get("project_id") or "").strip():
                adapted["project_id"] = snapshot_id
            adapted.setdefault("method_name", method_name)
            adapted.setdefault("method_goal", method_goal)
            adapted.setdefault("implementation_scope", implementation_scope)
            try:
                return MethodEvidence.model_validate(adapted)
            except (TypeError, ValueError, ValidationError):
                pass
    return MethodEvidence(
        project_id=project_id,
        method_name=method_name,
        method_goal=method_goal,
        implementation_scope=implementation_scope,
        author_logic_priority=True,
        writing_constraints=[
            "Author intent may determine scope and organization, but only projected V3 claims authorize repository-positive prose.",
            "Unverified author intent, explicit gaps, external literature needs, and formalization needs must remain caveated or review-bound.",
        ],
    )


def _rebuild_derived_authoring(
    *,
    fresh: Path,
    artifacts: Path,
    llm_config: Any,
    llm_caller: Any = None,
) -> tuple[dict[str, str], list[dict[str, Any]], str]:
    """Rebuild derived authoring from frozen research authority only."""

    from code2paper.agentic.authoring_projection import (
        build_authoring_projection,
        projected_writer_inputs,
    )
    from code2paper.agentic.claim_verifier import ClaimVerificationReport
    from code2paper.core.schemas import ClaimEvidenceMap
    from code2paper.agentic.evidence_compiler_v3 import (
        load_atomic_claims_v3,
        load_code_facts_v1,
        load_evidence_packets_v3,
    )
    from code2paper.agentic.equation_claims import load_equation_claims
    from code2paper.agentic.intent_compiler_v2 import (
        IntentObligationGraphV2,
        build_story_spine_from_intent_graph,
    )
    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        MethodCompletenessMatrixV1,
    )
    from code2paper.agentic.method_architect import (
        build_method_section_plan_with_product_readiness,
    )
    from code2paper.agentic.method_argument_brief_compiler import compile_method_argument_briefs
    from code2paper.agentic.method_argument_brief_planner import build_mechanism_draft_planner
    from code2paper.agentic.method_argument_facet_aligner import (
        bind_facets_to_argument_briefs,
        decompose_and_align_argument_facets,
    )
    from code2paper.agentic.method_product_models import build_default_method_output_policy
    from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
    from code2paper.llm.providers import has_provider_api_key

    claims = load_atomic_claims_v3(str(artifacts / "atomic_claims_v3.json"))
    facts = load_code_facts_v1(str(artifacts / "code_facts_v1.json"))
    from code2paper.agentic.scientific_claim_ir import (
        append_technical_claims,
        write_technical_claims_sidecar,
    )

    claims = append_technical_claims(claims, facts)
    (artifacts / "atomic_claims_v3.json").write_text(
        json.dumps(claims.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_technical_claims_sidecar(artifacts / "atomic_claims_v3.json", claims)
    equations = load_equation_claims(str(artifacts / "equation_claims_v1.json"))
    packets = load_evidence_packets_v3(str(artifacts / "evidence_packets_v3.json"))
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        (artifacts / "method_completeness_matrix_v1.json").read_text(encoding="utf-8")
    )
    configurations = ConfigurationClaimSetV1.model_validate_json(
        (artifacts / "configuration_claims_v1.json").read_text(encoding="utf-8")
    )
    intent_graph = IntentObligationGraphV2.model_validate_json(
        (artifacts / "intent_obligation_graph_v2.json").read_text(encoding="utf-8")
    )
    coverage = None
    coverage_path = artifacts / "obligation_coverage_v2.json"
    if coverage_path.is_file():
        coverage = ObligationCoverageReportV2.model_validate_json(
            coverage_path.read_text(encoding="utf-8")
        )
    method_template = _method_evidence_rebuild_template(
        artifacts=artifacts,
        intent_graph=intent_graph,
        claims=claims,
    )
    story_spine = build_story_spine_from_intent_graph(
        intent_graph,
        claim_set=claims,
    )
    planner = None
    require_planner = False
    if llm_config is not None and has_provider_api_key(llm_config):
        planner = build_mechanism_draft_planner(
            llm_config,
            claims=claims,
            equations=equations,
            llm_caller=llm_caller,
        )
        require_planner = True
    argument_briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=coverage,
        intent_graph=intent_graph,
        story_spine=story_spine,
        equations=equations,
        configurations=configurations,
        planner=planner,
        require_planner_for_unlicensed=require_planner,
    )
    facet_result = decompose_and_align_argument_facets(
        briefs=argument_briefs,
        claims=claims,
        facts=facts,
        evidence_packets=packets,
        equations=equations,
        llm_config=(
            llm_config if llm_config is not None and has_provider_api_key(llm_config)
            else None
        ),
        intent_graph=intent_graph,
    )
    argument_briefs = bind_facets_to_argument_briefs(
        argument_briefs,
        facets=facet_result.facets,
        alignments=facet_result.alignments,
        policies=facet_result.policies,
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claims,
        completeness=completeness,
        equations=equations,
        configurations=configurations,
        method_name=str(intent_graph.method_goal or "Method"),
        story_spine=story_spine,
        policy=build_default_method_output_policy(),
        argument_briefs=argument_briefs,
    )
    projection = build_authoring_projection(
        method_evidence=method_template,
        claim_map=ClaimEvidenceMap(),
        verification=ClaimVerificationReport(),
        atomic_claims_v3=claims,
        evidence_packets_v3=packets,
        equation_claims_v1=equations,
        intent_obligation_graph_v2=intent_graph,
        completeness=completeness,
    )
    method_evidence, claim_evidence_map = projected_writer_inputs(
        projection,
        template=method_template,
    )
    manifest_entries: list[dict[str, Any]] = []
    written: dict[str, str] = {}
    outputs: dict[str, Any] = {
        "method_argument_briefs_v1": argument_briefs,
        "method_argument_facets_v1": {
            "schema_version": "1.0",
            "facets": [
                item.model_dump(mode="json") for item in facet_result.facets
            ],
        },
        "facet_evidence_alignments_v1": {
            "schema_version": "1.0",
            "alignments": [
                item.model_dump(mode="json")
                for item in facet_result.alignments
            ],
        },
        "candidate_facet_policies_v1": {
            "schema_version": "1.0",
            "policies": [
                item.model_dump(mode="json") for item in facet_result.policies
            ],
        },
        "method_argument_facet_alignment_trace_v1": {
            "schema_version": "1.0",
            "content_digest": facet_result.content_digest,
            "schema_failures": list(facet_result.schema_failures),
            "traces": list(facet_result.traces),
        },
        "method_section_plan_v2": plan,
        "authoring_projection_v1": projection,
        "method_evidence": method_evidence,
        "claim_evidence_map": claim_evidence_map,
    }
    for key, value in outputs.items():
        out_path = artifacts / f"{key}.json"
        if hasattr(value, "model_dump_json"):
            content = value.model_dump_json(indent=2)
        else:
            content = json.dumps(value, ensure_ascii=False, indent=2)
        out_path.write_text(content + "\n", encoding="utf-8")
        written[key] = str(out_path)
        manifest_entries.append(_manifest_entry(
            name=key,
            path=out_path,
            authority_class="derived-authoring",
            decision="rebuilt",
        ))
    return written, manifest_entries, ""


def _find_fresh_artifact(fresh: Path, name: str) -> Path | None:
    """Find one copied or rebuilt artifact without assuming its lane directory."""

    candidates = (
        fresh / "artifacts" / f"{name}.json",
        fresh / "artifacts" / "06_authoring" / f"{name}.json",
        fresh / "artifacts" / "07_validation" / f"{name}.json",
        fresh / "artifacts" / "research_product" / f"{name}.json",
    )
    return next((path for path in candidates if path.is_file()), None)


def _authoring_continuation_needed(fresh: Path) -> bool:
    """Whether a replay has an actionable writing-time authority gap.

    The Writer's initial success is deliberately not the deciding condition.
    This inspection only controls whether a repository-backed continuation is
    attempted; it does not authorize any evidence or mutate a status.
    """

    bundle_path = _find_fresh_artifact(
        fresh, "writing_research_callback_artifacts_v1"
    )
    if bundle_path is not None:
        try:
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            str(item.get("status") or "") in {"open", "partial"}
            for item in payload.get("requests") or ()
            if isinstance(item, dict)
        ):
            return True

    policy_path = _find_fresh_artifact(fresh, "candidate_facet_policies_v1")
    if policy_path is not None:
        try:
            payload = json.loads(policy_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            str(item.get("alignment_status") or "") in {
                "partial", "mismatch", "unresolved"
            }
            or bool(item.get("schema_failures"))
            for item in payload.get("policies") or ()
            if isinstance(item, dict)
        ):
            return True

    section_path = _find_fresh_artifact(
        fresh, "formalization_section_results_v1"
    )
    if section_path is not None:
        try:
            payload = json.loads(section_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        if any(
            item.get("disposition") not in {None, ""}
            or str((item.get("outcome") or "")).lower() == "unresolved"
            for item in payload.get("sections") or ()
            if isinstance(item, dict)
        ):
            return True

    validation_path = next(
        (
            _find_fresh_artifact(fresh, name)
            for name in (
                "text_evidence_validation",
                "agentic_text_evidence_validation",
            )
            if _find_fresh_artifact(fresh, name) is not None
        ),
        None,
    )
    if validation_path is not None:
        try:
            payload = json.loads(validation_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        status = str(payload.get("status") or "").casefold()
        issue_counts = (
            "unsupported_claims",
            "unsupported_positive_claims",
            "unverified_claims",
            "critical_failures",
            "major_failures",
        )
        has_positive_issue_count = any(
            isinstance(payload.get(key), (int, float))
            and int(payload.get(key) or 0) > 0
            for key in issue_counts
        )
        issue_lists = (
            "issues",
            "failures",
            "quality_failures",
            "unresolved_issues",
            "evidence_gaps",
        )
        has_issue_list = any(
            bool(payload.get(key))
            for key in issue_lists
        )
        if (
            status in {"failed", "blocked", "error", "warnings", "incomplete"}
            or has_positive_issue_count
            or has_issue_list
        ):
            return True
    return False


def _build_replay_continuation_context(
    *,
    fresh: Path,
    artifacts: Path,
    repo: Path,
    llm_config: Any,
) -> tuple[Any, Any, str]:
    """Build a Research runtime and honest seed from frozen authority."""

    from code2paper.agentic.autonomous_method_agent import (
        build_product_research_runtime,
    )
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
    from code2paper.agentic.research_models import ResearchAgendaV1
    from code2paper.agentic.writing_callback_fulfillment import (
        build_research_continuation_seed,
    )

    intent_path = artifacts / "intent_obligation_graph_v2.json"
    agenda_path = artifacts / "research_agenda_v1.json"
    if not intent_path.is_file() or not agenda_path.is_file():
        raise FileNotFoundError("frozen intent or research agenda is missing")
    intent_graph = IntentObligationGraphV2.model_validate_json(
        intent_path.read_text(encoding="utf-8")
    )
    agenda = ResearchAgendaV1.model_validate_json(
        agenda_path.read_text(encoding="utf-8")
    )
    runtime = build_product_research_runtime(
        repo_path=repo,
        author_intent_path=None,
        claims=None,
        run_id=agenda.run_id,
        llm_config=llm_config,
        artifact_root=fresh / "artifacts" / "research_tool_data",
        intent_graph_override=intent_graph,
        agenda_override=agenda,
    )
    runtime = runtime.model_copy(update={
        "intent_target_proposal_report": {
            "status": "reconstructed_from_frozen_authority",
            "origin": "reconstructed_from_frozen_authority",
            "past_decision_trace_available": False,
        },
    })
    artifact_paths = {
        path.stem: str(path)
        for path in artifacts.glob("*.json")
        if path.is_file()
    }
    artifact_paths.update({
        "writing_research_callback_artifacts_v1": str(
            fresh / "artifacts" / "06_authoring"
            / "writing_research_callback_artifacts_v1.json"
        ),
    })
    seed, seed_path = build_research_continuation_seed(
        runtime=runtime,
        artifact_paths=artifact_paths,
        out_root=fresh,
    )
    return runtime, seed, seed_path


def _replay(
    *,
    frozen: Path,
    fresh: Path,
    arguments: argparse.Namespace,
    telemetry: dict,
) -> int:
    # Load the live profile into the environment (same as the probe).
    profile_path = Path(arguments.profile).expanduser()
    _apply_live_profile(profile_path)

    from code2paper.llm.providers import load_llm_config_from_env

    llm_config = load_llm_config_from_env()

    # Copy frozen research artifacts into the fresh root (never move/delete).
    artifacts = fresh / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    manifest_entries: list[dict[str, Any]] = []
    for name in RESEARCH_COPY_ARTIFACTS:
        source_candidates = [
            frozen / "artifacts" / f"{name}.json",
            frozen / "artifacts" / "06_authoring" / f"{name}.json",
        ]
        source = next((path for path in source_candidates if path.is_file()), None)
        if source is None:
            continue
        target = artifacts / f"{name}.json"
        shutil.copy2(source, target)
        copied.append(name)
        manifest_entries.append(_manifest_entry(
            name=name,
            path=target,
            authority_class="research",
            decision="copied",
        ))
    print(f"[replay] copied {len(copied)} research artifacts: {', '.join(copied)}")
    missing = [
        name for name in RESEARCH_COPY_ARTIFACTS
        if not (artifacts / f"{name}.json").is_file()
    ]
    if missing:
        print(f"[replay] FATAL missing frozen artifacts: {missing}")
        return 2

    for name in OPTIONAL_RESEARCH_ARTIFACTS:
        source_candidates = [
            frozen / "artifacts" / "06_authoring" / f"{name}.json",
            frozen / "artifacts" / f"{name}.json",
        ]
        source = next((path for path in source_candidates if path.is_file()), None)
        if source is not None:
            shutil.copy2(source, artifacts / f"{name}.json")
            copied.append(name)
            manifest_entries.append(_manifest_entry(
                name=name,
                path=artifacts / f"{name}.json",
                authority_class="research",
                decision="copied",
            ))
            print(f"[replay] copied optional research artifact: {name}")

    execution_digest = _execution_manifest_digest(
        profile_path=profile_path,
        frozen=frozen,
        copied_artifact_names=tuple(copied),
    )
    if not profile_path.is_file():
        print("[replay] FATAL authoring rebuild manifest missing profile digest")
        return 2

    for derived_name in DERIVED_AUTHORING_ARTIFACTS:
        manifest_entries.append(_manifest_entry(
            name=derived_name,
            path=artifacts / f"{derived_name}.json",
            authority_class="derived-authoring",
            decision="refused",
            reason="not_copied_by_default",
        ))

    if arguments.rebuild_authoring:
        rebuilt_paths, rebuilt_entries, refused = _rebuild_derived_authoring(
            fresh=fresh,
            artifacts=artifacts,
            llm_config=llm_config,
        )
        if refused:
            print(f"[replay] FATAL authoring rebuild refused: {refused}")
            if arguments.persist_authoring_rebuild_manifest:
                _write_authoring_rebuild_manifest(
                    fresh=fresh,
                    entries=manifest_entries,
                    execution_digest=execution_digest,
                    refused_reason=refused,
                )
            return 2
        copied.extend(rebuilt_paths.keys())
        manifest_entries.extend(rebuilt_entries)
        for derived_name in DERIVED_AUTHORING_ARTIFACTS:
            if derived_name in rebuilt_paths:
                continue
            manifest_entries.append(_manifest_entry(
                name=derived_name,
                path=artifacts / f"{derived_name}.json",
                authority_class="derived-authoring",
                decision="refused",
                reason="rebuild_did_not_emit",
            ))

    research_checkpoint_path = (
        artifacts / "research_stage_checkpoint_v1.json"
        if (artifacts / "research_stage_checkpoint_v1.json").is_file()
        else None
    )

    # R3: callback bundle reuse is explicit only.
    reused_fulfilled_callback_ids: list[str] = []
    if arguments.reuse_authoring_callbacks:
        frozen_bundle_candidates = [
            frozen / "artifacts" / "06_authoring" / "writing_research_callback_artifacts_v1.json",
            frozen / "artifacts" / "writing_research_callback_artifacts_v1.json",
        ]
        frozen_bundle_path = next(
            (path for path in frozen_bundle_candidates if path.is_file()), None
        )
        if frozen_bundle_path is not None:
            from code2paper.agentic.publication_method_writer import (
                rebase_callback_bundle_artifacts,
            )

            rebase_report = rebase_callback_bundle_artifacts(
                bundle_path=frozen_bundle_path,
                frozen_root=frozen,
                fresh_root=fresh,
            )
            if rebase_report["failures"]:
                print(
                    "[replay] FATAL callback artifact integrity failures: "
                    + "; ".join(rebase_report["failures"])
                )
                return 2
            bundle_payload = rebase_report["bundle"]
            if bundle_payload is None:
                print("[replay] FATAL callback bundle rebase produced no bundle")
                return 2
            fresh_bundle_path = artifacts / "writing_research_callback_artifacts_v1.json"
            fresh_bundle_path.write_text(
                json.dumps(bundle_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            copied.append("writing_research_callback_artifacts_v1")
            manifest_entries.append(_manifest_entry(
                name="writing_research_callback_artifacts_v1",
                path=fresh_bundle_path,
                authority_class="derived-authoring",
                decision="copied",
                reason="reuse_authoring_callbacks",
            ))
            reused_fulfilled_callback_ids = rebase_report["reused_fulfilled_callback_ids"]
            print(
                "[replay] rebased callback bundle with "
                f"{len(rebase_report['copied_refs'])} file-backed artifact(s); "
                f"reused_fulfilled_callback_ids={reused_fulfilled_callback_ids}"
            )

    if arguments.persist_authoring_rebuild_manifest:
        _write_authoring_rebuild_manifest(
            fresh=fresh,
            entries=manifest_entries,
            execution_digest=execution_digest,
        )

    artifact_paths = {
        name: str(artifacts / f"{name}.json")
        for name in copied
    }

    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )

    result, paths = run_publication_method_writer(
        out_root=fresh,
        artifact_paths=artifact_paths,
        llm_config=llm_config,
        resume_section_ids=tuple(arguments.resume),
        llm_caller=None,
        editor_caller=None,
        rewrite_caller=None,
        formalization_caller=None,
        architect_proposal_caller=None,
    )
    print(f"[replay] writer status: {result.status} blocked={result.blocked_reason}")
    print(f"[replay] paths: {json.dumps({k: v for k, v in sorted(paths.items()) if v}, indent=1)[:1200]}")
    print(f"[replay] reused_fulfilled_callback_ids: {reused_fulfilled_callback_ids}")
    print(f"[replay] writer_resumed_section_ids: {list(result.resumed_section_ids)}")
    telemetry["reused_fulfilled_callback_ids"] = reused_fulfilled_callback_ids
    telemetry["writer_resumed_section_ids"] = list(result.resumed_section_ids)
    telemetry["writer_status"] = result.status
    telemetry["writer_blocked_reason"] = result.blocked_reason
    telemetry["candidate_digest"] = _candidate_digest_for_root(fresh)
    trace_path = _record_method_content_trace(
        fresh=fresh,
        artifact_paths={**artifact_paths, **paths},
        telemetry=telemetry,
    )
    paths["method_content_trace_v1"] = trace_path
    _record_product_authoring_state(
        fresh=fresh,
        paths=paths,
        telemetry=telemetry,
    )

    structural_exit = _record_authoring_structural_exit(
        fresh=fresh,
        paths=paths,
        telemetry=telemetry,
    )

    callback_requested = (
        arguments.repo
        and Path(arguments.repo).is_dir()
        and int(arguments.callback_rounds) > 0
    )
    if callback_requested and not bool(structural_exit.get("eligible")):
        # Fail closed before constructing a Research runtime or making a
        # callback LLM/tool call.  The Candidate and its diagnostics stay
        # available, but this run is never reported as a successful
        # callback continuation.
        reason = "callback1_not_authorized:" + ";".join(
            str(item) for item in (structural_exit.get("reasons") or ())
        )
        telemetry["callback_fulfillment"] = {
            "status": "not_authorized",
            "stopped_reason": "callback1_not_authorized",
            "reason": reason,
            "structural_exit_digest": str(
                telemetry.get("structural_exit", {}).get("content_digest") or ""
            ),
        }
        telemetry["writer_status"] = (
            "incomplete" if telemetry.get("writer_status") == "success"
            else telemetry.get("writer_status", "incomplete")
        )
        telemetry["writer_blocked_reason"] = reason
    if (
        callback_requested
        and bool(structural_exit.get("eligible"))
        and _authoring_continuation_needed(fresh)
    ):
        from code2paper.agentic.writing_callback_fulfillment import (
            WritingCallbackFulfillmentBudgetV1,
            fulfill_and_resume_writing_callbacks,
        )

        checkpoint_path = research_checkpoint_path
        continuation_seed = None
        try:
            if checkpoint_path is not None:
                from code2paper.agentic.autonomous_method_agent import (
                    build_product_research_runtime,
                )
                from code2paper.agentic.intent_compiler_v2 import (
                    IntentObligationGraphV2,
                )
                from code2paper.agentic.research_models import ResearchAgendaV1

                checkpoint_payload = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
                checkpoint_run_id = str(
                    checkpoint_payload.get("run_id") or arguments.run_id
                )
                runtime = build_product_research_runtime(
                    repo_path=Path(arguments.repo).expanduser().resolve(),
                    author_intent_path=None,
                    claims=None,
                    run_id=checkpoint_run_id,
                    llm_config=llm_config,
                    artifact_root=fresh / "artifacts" / "research_tool_data",
                    intent_graph_override=IntentObligationGraphV2.model_validate(
                        checkpoint_payload["intent_graph"]
                    ),
                    agenda_override=ResearchAgendaV1.model_validate(
                        checkpoint_payload["agenda"]
                    ),
                )
                seed_path = ""
            else:
                runtime, continuation_seed, seed_path = (
                    _build_replay_continuation_context(
                        fresh=fresh,
                        artifacts=artifacts,
                        repo=Path(arguments.repo).expanduser().resolve(),
                        llm_config=llm_config,
                    )
                )
                telemetry["research_continuation_seed"] = {
                    "path": seed_path,
                    **continuation_seed.model_dump(mode="json"),
                }
                if seed_path:
                    artifact_paths["research_continuation_seed_v1"] = seed_path
        except Exception as exc:  # noqa: BLE001 — checkpoint faults stay writer-only
            print(
                f"[replay] research continuation unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
            runtime = None
        if runtime is not None:
            callback_paths, callback_status, callback_reason, callback_result = (
                fulfill_and_resume_writing_callbacks(
                    runtime=runtime,
                    out_root=fresh,
                    artifact_paths=artifact_paths,
                    writer_paths=paths,
                    llm_config=llm_config,
                    budget=WritingCallbackFulfillmentBudgetV1(
                        max_callback_rounds=max(0, int(arguments.callback_rounds)),
                        max_tool_turns_per_request=max(
                            1, int(arguments.callback_tool_turns)
                        ),
                    ),
                    llm_caller=None,
                    research_stage_checkpoint=checkpoint_path,
                    research_continuation_seed=continuation_seed,
                )
            )
            print(
                f"[replay] callback continuation: fulfilled={callback_result.local_requests_fulfilled} "
                f"pending={callback_result.local_requests_seen - callback_result.local_requests_fulfilled} "
                f"resumed={list(callback_result.resumed_section_ids)} "
                f"stopped={callback_result.stopped_reason}"
            )
            telemetry["writer_status"] = callback_status
            telemetry["writer_blocked_reason"] = callback_reason
            telemetry["writer_resumed_section_ids"] = list(callback_result.resumed_section_ids)
            telemetry["callback_fulfillment"] = callback_result.model_dump(mode="json")
            telemetry["candidate_digest"] = _candidate_digest_for_root(fresh)
            paths.update(callback_paths)
            trace_path = _record_method_content_trace(
                fresh=fresh,
                artifact_paths={**artifact_paths, **paths},
                telemetry=telemetry,
            )
            paths["method_content_trace_v1"] = trace_path
            from code2paper.agentic.product_authoring_graph import (
                persist_product_authoring_state_from_writer,
            )
            _state, product_state_path = persist_product_authoring_state_from_writer(
                out_root=fresh,
                artifact_paths={**artifact_paths, **paths},
                run_id=arguments.run_id,
                terminal_status=(
                    "blocked"
                    if callback_status == "blocked"
                    else "completed"
                    if callback_status == "success"
                    else "review_ready_with_warnings"
                ),
                stop_reason=callback_reason or callback_result.stopped_reason,
            )
            paths["product_authoring_state_v1"] = product_state_path
            _record_product_authoring_state(
                fresh=fresh,
                paths=paths,
                telemetry=telemetry,
            )
            _record_authoring_structural_exit(
                fresh=fresh,
                paths=paths,
                telemetry=telemetry,
            )

    writer_status = str(telemetry.get("writer_status") or result.status)
    candidate_digest = str(telemetry.get("candidate_digest") or "")
    if writer_status == "blocked" and not candidate_digest:
        return 2
    if writer_status == "blocked" and candidate_digest:
        # Incumbent survives a blocked post-callback writer; warnings only.
        return 0
    if writer_status == "blocked":
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_root", help="Frozen run root with research artifacts")
    parser.add_argument("fresh_root", help="Fresh output root for the replay")
    parser.add_argument("--resume", action="append", default=[],
                        help="Section ids to resume (e.g. MA-S2)")
    parser.add_argument("--repo", default="",
                        help="Repository path for Research-Graph callback continuation")
    parser.add_argument("--callback-rounds", type=int, default=2)
    parser.add_argument("--callback-tool-turns", type=int, default=6)
    parser.add_argument("--profile", default="tests/live/profiles/qwen36_vllm_budgeted.example.env")
    parser.add_argument("--run-id", default="replay")
    parser.add_argument(
        "--rebuild-authoring",
        action="store_true",
        help="Rebuild derived authoring (concept cards, plan, projection) from research authority",
    )
    parser.add_argument(
        "--reuse-authoring-callbacks",
        action="store_true",
        help="Copy and rebase a frozen writing_research_callback_artifacts_v1 bundle",
    )
    parser.add_argument(
        "--persist-authoring-rebuild-manifest",
        action="store_true",
        help="Write authoring_rebuild_manifest_v1.json with copy/rebuild decisions",
    )
    arguments = parser.parse_args(argv)

    frozen = Path(arguments.frozen_root).expanduser().resolve()
    fresh = Path(arguments.fresh_root).expanduser().resolve()
    fresh.mkdir(parents=True, exist_ok=True)
    _apply_live_profile(arguments.profile)

    from run_d5_consolidated_matrix import record_runtime_ledger

    telemetry: dict = {}
    runtime_start: dict | None = None
    runtime_end: dict | None = None
    exit_code = 0

    def _request_exit(signum: int, _frame: object) -> None:
        raise SystemExit(128 + int(signum))

    signal.signal(signal.SIGTERM, _request_exit)
    signal.signal(signal.SIGHUP, _request_exit)
    try:
        runtime_start = record_runtime_ledger(fresh, "start")
        exit_code = _replay(
            frozen=frozen,
            fresh=fresh,
            arguments=arguments,
            telemetry=telemetry,
        )
    except SystemExit as exc:
        raw = exc.code
        exit_code = raw if isinstance(raw, int) else 143
        print(f"[replay] interrupted SystemExit={exit_code}")
        raise
    except KeyboardInterrupt:
        exit_code = 130
        print("[replay] interrupted KeyboardInterrupt")
        raise
    except Exception as exc:  # noqa: BLE001 - replay boundary must record
        print(f"[replay] FATAL unhandled error: {exc!r}")
        exit_code = 2
    finally:
        try:
            runtime_end = record_runtime_ledger(fresh, "end")
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            print(f"[replay] runtime end ledger failed: {exc!r}")
        try:
            _write_execution_record(
                frozen=frozen,
                fresh=fresh,
                arguments=arguments,
                exit_code=exit_code,
                runtime_start=runtime_start,
                runtime_end=runtime_end,
                telemetry=telemetry,
            )
        except Exception as exc:  # noqa: BLE001 - diagnostics-only
            print(f"[replay] execution record write failed: {exc!r}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
