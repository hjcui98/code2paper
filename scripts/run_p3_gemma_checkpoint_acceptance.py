#!/usr/bin/env python3
"""Fresh Gemma 4 + FastGS checkpoint acceptance for the P3 exit gate."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from code2paper.agentic.artifact_freshness import check_artifact_freshness
from code2paper.agentic.checkpointing import checkpoint_config, checkpoint_thread_id, open_sqlite_checkpointer, validate_resume_state
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.final_text_claims import load_final_text_claims
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.agentic.semantic_verifier_provider import LLMSemanticEvidenceVerifier
from code2paper.agentic.state_v2 import AgenticRunStateV2
from code2paper.agentic.text_evidence_validator import validate_text_evidence
from code2paper.agentic.text_trace_builder import build_final_text_trace
from code2paper.agentic.tool_runtime import atomic_write_json
from code2paper.agentic.trust_contracts import AuthoringInputProjection
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType
from code2paper.llm.providers import load_llm_config_from_env
try:
    from scripts.run_p3_checkpoint_acceptance import _digest, _file_digest, _prepare_artifacts
except ModuleNotFoundError:  # direct ``python scripts/...`` execution
    from run_p3_checkpoint_acceptance import _digest, _file_digest, _prepare_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/tmp/code2paper-p2-fastgs-deterministic")
    parser.add_argument("--work", default="/tmp/code2paper-p3-fastgs-gemma4-live-r1")
    parser.add_argument("--report", default="tests/baselines/agentic/p3_gemma4_checkpoint_validation_report.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="gemma4-31b-nvfp4")
    args = parser.parse_args()

    preflight = _preflight(args.base_url, args.model)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    cache_dir = work / "llm_cache"
    if any(cache_dir.glob("*.json")):
        raise RuntimeError(f"fresh acceptance refuses a populated cache: {cache_dir}")
    os.environ.update({
        "CODE2PAPER_OPENAI_BASE_URL": args.base_url,
        "CODE2PAPER_LLM_MODEL": args.model,
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "dummy-local-vllm"),
        "CODE2PAPER_LLM_CACHE_DIR": str(cache_dir),
        "CODE2PAPER_LLM_TIMEOUT_SECONDS": "180",
        "CODE2PAPER_LLM_RETRY_MAX_ATTEMPTS": "1",
        "CODE2PAPER_LLM_TEMPERATURE": "0",
    })
    artifacts = _prepare_artifacts(Path(args.source), work / "artifacts")
    repo = load_repo_snapshot(artifacts["repo_snapshot"])
    state = AgenticRunState(
        run_id="fastgs-p3-gemma4-checkpoint",
        project_root=repo.project_root,
        out_root=work / "out",
        repo_snapshot_ref=artifacts["repo_snapshot"],
        llm_provider="openai",
        llm_model=args.model,
        max_authoring_revision_rounds=2,
        max_semantic_verifier_calls=1,
        loop_counters={"authoring": 1, "semantic_verifier": 0},
        artifacts=artifacts,
        checkpoint_metadata={"checkpoint_backend": "sqlite"},
    )
    config = checkpoint_config(checkpoint_thread_id(run_id=state.run_id, repo_snapshot_id=repo.snapshot_id))
    cached_config = load_llm_config_from_env(provider="openai", model=args.model).model_copy(update={"cache": True})
    control = _execute(state, config, work / "control.sqlite", interrupt_after=None, llm_config=cached_config)
    interruptions = [
        _execute(state, config, work / "after_evidence.sqlite", interrupt_after="evidence_freeze", llm_config=cached_config),
        _execute(state, config, work / "after_text.sqlite", interrupt_after="final_text_validation", llm_config=cached_config),
        _execute(state, config, work / "after_render.sqlite", interrupt_after="structured_render", llm_config=cached_config),
    ]
    uncached = _uncached_stability(state, cached_config.model_copy(update={"cache": False}), repeats=3)
    report = {
        "schema_version": "1.0",
        "phase": "P3",
        "run_id": state.run_id,
        "preflight": preflight,
        "repo_snapshot_id": repo.snapshot_id,
        "repo_files": len(repo.included_files),
        "graph_contract_version": state.graph_contract_version,
        "control": control,
        "interruptions": interruptions,
        "all_resume_digests_match_control": all(item["final_digest"] == control["final_digest"] for item in interruptions),
        "all_resume_freshness_passed": all(item["freshness_status"] == "passed" for item in interruptions),
        "completed_nodes_never_reexecuted": all(item["completed_node_reexecutions"] == 0 for item in interruptions),
        "budgets_preserved": all(item["final_loop_counters"] == control["final_loop_counters"] for item in interruptions),
        "cache_probe": {
            "control_network_calls": control["network_model_calls"],
            "resume_scenario_cache_hits": sum(item["cache_hits"] for item in interruptions),
            "resume_added_invocations_after_completed_text_gate": [
                item["resume_added_model_invocations"] for item in interruptions
                if item["interrupt_after"] in {"final_text_validation", "structured_render"}
            ],
        },
        "cache_disabled_stability": uncached,
    }
    passed = (
        report["all_resume_digests_match_control"]
        and report["all_resume_freshness_passed"]
        and report["completed_nodes_never_reexecuted"]
        and report["budgets_preserved"]
        and control["network_model_calls"] == 1
        and all(value == 0 for value in report["cache_probe"]["resume_added_invocations_after_completed_text_gate"])
        and uncached["stable_trust_verdict"]
    )
    report["status"] = "passed" if passed else "failed"
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


def _execute(state, config, database: Path, *, interrupt_after: str | None, llm_config) -> dict:
    calls = {name: 0 for name in ("evidence_freeze", "final_text_validation", "structured_render", "finalize")}
    verifier = LLMSemanticEvidenceVerifier(llm_config)
    calls_before_resume = 0

    def evidence_node(raw):
        calls["evidence_freeze"] += 1
        current = AgenticRunState.model_validate(raw)
        _require_fresh(current)
        return _phase_update("evidence_freeze")

    def text_node(raw):
        calls["final_text_validation"] += 1
        current = AgenticRunState.model_validate(raw)
        projection = AuthoringInputProjection.model_validate_json(Path(current.artifacts["authoring_projection"]).read_text(encoding="utf-8"))
        claims = load_final_text_claims(current.artifacts["final_text_claims"])
        evidence = load_evidence_snapshot_v2(current.artifacts["evidence_snapshot_v2"])
        repo = load_repo_snapshot(current.artifacts["repo_snapshot"])
        validation = validate_text_evidence(
            final_claims=claims, projection=projection, raw_evidence=_raw(repo.project_root, evidence),
            evidence_snapshot_v2=evidence, semantic_verifier=verifier,
            max_semantic_verifier_calls=1, require_semantic_verifier=True,
        )
        if validation.status != "passed":
            raise RuntimeError("fresh Gemma semantic validation failed: " + validation.model_dump_json())
        validation_path = Path(current.artifacts["text_evidence_validation"])
        trace_path = Path(current.artifacts["final_text_trace"])
        atomic_write_json(validation_path, validation)
        trace = build_final_text_trace(
            final_claims=claims, validation=validation, projection=projection,
            validator_report_ref=str(validation_path), projection_ref=current.artifacts["authoring_projection"],
        )
        if not trace.hard_gate_passed:
            raise RuntimeError("fresh Gemma text trace failed: " + trace.model_dump_json())
        atomic_write_json(trace_path, trace)
        update = _phase_update("final_text_validation")
        update.update({
            "artifacts": {"text_evidence_validation": str(validation_path), "final_text_trace": str(trace_path)},
            "loop_counters": {
                **current.loop_counters,
                "authoring": current.loop_counters.get("authoring", 0) + 1,
                "semantic_verifier": current.loop_counters.get("semantic_verifier", 0) + validation.semantic_verifier_calls,
            },
        })
        return update

    def render_node(raw):
        calls["structured_render"] += 1
        current = AgenticRunState.model_validate(raw)
        _require_fresh(current)
        post = json.loads(Path(current.artifacts["post_render_audit"]).read_text(encoding="utf-8"))
        if not post.get("hard_gate_passed"):
            raise RuntimeError("post-render audit not passed")
        return _phase_update("structured_render")

    def finalize_node(raw):
        calls["finalize"] += 1
        current = AgenticRunState.model_validate(raw)
        _require_fresh(current)
        return {**_phase_update("finalize"), "validation": {"finalize_freshness": "passed"}}

    def compile_graph(saver):
        builder = StateGraph(AgenticRunStateV2)
        builder.add_node("evidence_freeze", evidence_node)
        builder.add_node("final_text_validation", text_node)
        builder.add_node("structured_render", render_node)
        builder.add_node("finalize", finalize_node)
        builder.add_edge(START, "evidence_freeze")
        builder.add_edge("evidence_freeze", "final_text_validation")
        builder.add_edge("final_text_validation", "structured_render")
        builder.add_edge("structured_render", "finalize")
        builder.add_edge("finalize", END)
        return builder.compile(checkpointer=saver, interrupt_after=[interrupt_after] if interrupt_after else None)

    with open_sqlite_checkpointer(database) as saver:
        app = compile_graph(saver)
        result = app.invoke(state.model_dump(mode="json"), config=config)
        calls_before_resume = len(verifier.traces)
    if interrupt_after:
        with open_sqlite_checkpointer(database) as saver:
            app = compile_graph(saver)
            validate_resume_state(app.get_state(config).values)
            result = app.invoke(None, config=config)
    payload = AgenticRunState.model_validate(result)
    traces = verifier.traces
    return {
        "interrupt_after": interrupt_after or "none",
        "node_calls": calls,
        "completed_node_reexecutions": max(0, sum(max(0, value - 1) for value in calls.values())),
        "model_invocations_before_resume": calls_before_resume,
        "model_invocations_after_resume": len(traces),
        "resume_added_model_invocations": len(traces) - calls_before_resume,
        "network_model_calls": sum(not item.get("cached", False) for item in traces),
        "cache_hits": sum(bool(item.get("cached")) for item in traces),
        "model_traces": traces,
        "freshness_status": payload.validation.get("finalize_freshness", ""),
        "final_loop_counters": payload.loop_counters,
        "final_digest": _final_digest(payload),
    }


def _uncached_stability(state: AgenticRunState, config, *, repeats: int) -> dict:
    outcomes = []
    for _index in range(repeats):
        verifier = LLMSemanticEvidenceVerifier(config)
        evidence = load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
        repo = load_repo_snapshot(state.artifacts["repo_snapshot"])
        projection = AuthoringInputProjection.model_validate_json(Path(state.artifacts["authoring_projection"]).read_text(encoding="utf-8"))
        report = validate_text_evidence(
            final_claims=load_final_text_claims(state.artifacts["final_text_claims"]), projection=projection,
            raw_evidence=_raw(repo.project_root, evidence), evidence_snapshot_v2=evidence,
            semantic_verifier=verifier, max_semantic_verifier_calls=1, require_semantic_verifier=True,
        )
        outcomes.append({
            "status": report.status,
            "verdicts": [{"status": item.status, "direct_evidence_ids": item.direct_evidence_ids} for item in report.verdicts],
            "trace": verifier.traces[0] if verifier.traces else {},
        })
    signatures = [_digest({"status": item["status"], "verdicts": item["verdicts"]}) for item in outcomes]
    return {
        "repeats": repeats,
        "network_model_calls": sum(not item["trace"].get("cached", False) for item in outcomes),
        "trust_signatures": signatures,
        "stable_trust_verdict": len(set(signatures)) == 1 and all(item["status"] == "passed" for item in outcomes),
        "outcomes": outcomes,
    }


def _require_fresh(state: AgenticRunState) -> None:
    report = check_artifact_freshness(
        repo_snapshot=load_repo_snapshot(state.artifacts["repo_snapshot"]),
        evidence_snapshot=load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"]),
        artifacts=state.artifacts,
    )
    if report.status != "passed":
        raise RuntimeError("freshness failed: " + ",".join(report.stale_artifact_keys))


def _phase_update(name: str) -> dict:
    return {
        "phase_statuses": {name: "success"},
        "decisions": [AgentDecision(node=name, decision="passed", rationale="P3 live acceptance gate passed.").model_dump(mode="json")],
    }


def _raw(project_root: str, evidence) -> RawEvidencePack:
    span = next(item for item in evidence.spans if item.evidence_id == "E1")
    return RawEvidencePack(project_id="FastGS", project_root=project_root, evidence_items=[EvidenceItem(
        evidence_id=span.evidence_id, source_type=SourceType.SOURCE, path=span.path, symbol=span.symbol,
        line_start=span.line_start, line_end=span.line_end,
        content_summary="training initializes first_iter to 0", confidence=1.0,
    )])


def _final_digest(state: AgenticRunState) -> str:
    return _digest({
        "artifacts": {key: _file_digest(Path(path)) for key, path in sorted(state.artifacts.items())},
        "phase_statuses": state.phase_statuses,
        "loop_counters": state.loop_counters,
    })


def _preflight(base_url: str, model: str) -> dict:
    api_root = base_url.rstrip("/").removesuffix("/v1")
    with urllib.request.urlopen(api_root + "/health", timeout=5) as response:
        health_status = response.status
    with urllib.request.urlopen(api_root + "/v1/models", timeout=5) as response:
        models = json.loads(response.read().decode("utf-8"))
    model_ids = [str(item.get("id")) for item in models.get("data", [])]
    if model not in model_ids:
        raise RuntimeError(f"served model mismatch: expected {model}, got {model_ids}")
    process = subprocess.run(["ps", "-ef"], capture_output=True, text=True, check=True).stdout
    lines = [line for line in process.splitlines() if model in line or "vllm" in line.lower()]
    process_text = "\n".join(lines)
    return {
        "health_status": health_status,
        "served_models": model_ids,
        "expected_model": model,
        "vllm_process_found": bool(lines),
        "mtp_config_visible": '"method":"mtp"' in process_text.replace(" ", "") or "'method': 'mtp'" in process_text,
        "process_fingerprint": _digest(process_text) if process_text else "",
    }


if __name__ == "__main__":
    raise SystemExit(main())
