#!/usr/bin/env python3
"""Replay the P3 checkpoint contract over the frozen FastGS P2 trust slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from code2paper.agentic.artifact_freshness import check_artifact_freshness
from code2paper.agentic.checkpointing import checkpoint_config, checkpoint_thread_id, open_sqlite_checkpointer, validate_resume_state
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.final_text_claims import extract_final_text_claims
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.agentic.state_v2 import AgenticRunStateV2
from code2paper.agentic.text_evidence_validator import validate_text_evidence
from code2paper.agentic.text_trace_builder import build_final_text_trace
from code2paper.agentic.tool_runtime import atomic_write_json
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ProjectedClaim
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/tmp/code2paper-p2-fastgs-deterministic")
    parser.add_argument("--live-trace", default="/tmp/code2paper-p2-fastgs-gemma4/figure_plan_decision_trace.json")
    parser.add_argument("--work", default="/tmp/code2paper-p3-fastgs-checkpoint")
    parser.add_argument("--report", default="tests/baselines/agentic/p3_checkpoint_validation_report.json")
    args = parser.parse_args()
    source, work = Path(args.source), Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    artifacts = _prepare_artifacts(source, work)
    state = AgenticRunState(
        run_id="fastgs-p3-checkpoint",
        project_root=load_repo_snapshot(artifacts["repo_snapshot"]).project_root,
        out_root=work / "out",
        repo_snapshot_ref=artifacts["repo_snapshot"],
        max_authoring_revision_rounds=2,
        max_semantic_verifier_calls=1,
        loop_counters={"authoring": 1},
        artifacts=artifacts,
        checkpoint_metadata={"checkpoint_backend": "sqlite"},
    )
    repo = load_repo_snapshot(artifacts["repo_snapshot"])
    config = checkpoint_config(checkpoint_thread_id(run_id=state.run_id, repo_snapshot_id=repo.snapshot_id))
    control = _execute(state, config, work / "control.sqlite", interrupt_after=None)
    scenarios = [
        _execute(state, config, work / "after_evidence.sqlite", interrupt_after="evidence_freeze"),
        _execute(state, config, work / "after_text.sqlite", interrupt_after="final_text_validation"),
        _execute(state, config, work / "after_render.sqlite", interrupt_after="structured_render"),
    ]
    live_trace = Path(args.live_trace)
    report = {
        "schema_version": "1.0",
        "phase": "P3",
        "run_id": state.run_id,
        "repo_snapshot_id": repo.snapshot_id,
        "repo_files": len(repo.included_files),
        "graph_contract_version": state.graph_contract_version,
        "checkpoint_backend": "sqlite",
        "control": control,
        "interruptions": scenarios,
        "all_resume_digests_match_control": all(item["final_digest"] == control["final_digest"] for item in scenarios),
        "all_freshness_gates_passed": all(item["freshness_status"] == "passed" for item in [control, *scenarios]),
        "budgets_preserved": all(item["final_loop_counters"] == control["final_loop_counters"] for item in scenarios),
        "model_calls_during_checkpoint_replay": 0,
        "prior_fastgs_gemma4_decision_trace": str(live_trace) if live_trace.exists() else "",
        "prior_fastgs_gemma4_decision_trace_sha256": _file_digest(live_trace) if live_trace.exists() else "",
        "live_model_status": "unavailable_http_127_0_0_1_8000_on_2026_07_17",
        "classification": (
            "Real frozen FastGS artifact replay with durable SQLite interruptions. It proves resume/freshness/digest "
            "equivalence and reuses an audited prior Gemma 4 decision trace, but is not a fresh P3 Gemma invocation; "
            "the fresh-live exit gate remains pending until the local service is available."
        ),
    }
    atomic_write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["all_resume_digests_match_control"] and report["all_freshness_gates_passed"] else 1


def _prepare_artifacts(source: Path, work: Path) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    names = {
        "repo_snapshot": "repo_snapshot.json",
        "evidence_snapshot_v2": "evidence_snapshot_v2.json",
        "evidence_relations_v2": "evidence_relations_v2.json",
        "figure_scene": "figure_scene.json",
        "figure_relation_validation": "pre_render_audit.json",
        "pre_render_audit": "pre_render_audit.json",
        "rendering_manifest": "rendering_manifest.json",
        "post_render_audit": "post_render_audit.json",
    }
    result: dict[str, str] = {}
    for key, filename in names.items():
        target = work / filename
        if not target.exists():
            shutil.copy2(source / filename, target)
        result[key] = str(target)
    evidence = load_evidence_snapshot_v2(result["evidence_snapshot_v2"])
    repo = load_repo_snapshot(result["repo_snapshot"])
    span = next(item for item in evidence.spans if item.evidence_id == "E1")
    claim_text = "The training function initializes first_iter to 0."
    projection = AuthoringInputProjection(
        project_id="FastGS", method_name="FastGS", author_goal="Describe the code-backed training initialization.",
        implementation_scope="training initialization", projected_claims=[ProjectedClaim(
            claim_id="P3C1", claim_text=claim_text, support_status="supported", direct_evidence_ids=[span.evidence_id],
            supported_fragment=claim_text, allowed_wording_boundary=claim_text, source="P3 FastGS replay",
            input_digest=_digest({"claim": claim_text, "evidence": span.excerpt_digest}),
        )], repo_snapshot_id=repo.snapshot_id, project_tree_hash=repo.project_tree_hash,
        evidence_snapshot_id=evidence.evidence_snapshot_id, evidence_snapshot_digest=evidence.content_digest,
        projection_digest=_digest({"claim": claim_text, "snapshot": evidence.evidence_snapshot_id}),
    )
    raw = RawEvidencePack(project_id="FastGS", project_root=repo.project_root, evidence_items=[EvidenceItem(
        evidence_id=span.evidence_id, source_type=SourceType.SOURCE, path=span.path, symbol=span.symbol,
        line_start=span.line_start, line_end=span.line_end, content_summary="training initializes first_iter to 0", confidence=1.0,
    )])
    claims = extract_final_text_claims(claim_text, projection)
    validation = validate_text_evidence(final_claims=claims, projection=projection, raw_evidence=raw, evidence_snapshot_v2=evidence)
    if validation.status != "passed":
        raise RuntimeError(f"FastGS text trust slice failed: {validation.model_dump(mode='json')}")
    projection_path, claims_path, validation_path, trace_path = [work / name for name in (
        "authoring_projection.json", "final_text_claims.json", "text_evidence_validation.json", "final_text_trace.json",
    )]
    trace = build_final_text_trace(final_claims=claims, validation=validation, projection=projection, validator_report_ref=str(validation_path), projection_ref=str(projection_path))
    for path, value in ((projection_path, projection), (claims_path, claims), (validation_path, validation), (trace_path, trace)):
        atomic_write_json(path, value)
    result.update(authoring_projection=str(projection_path), final_text_claims=str(claims_path), text_evidence_validation=str(validation_path), final_text_trace=str(trace_path))
    return result


def _execute(state: AgenticRunState, config: dict, database: Path, *, interrupt_after: str | None) -> dict:
    calls = {name: 0 for name in ("evidence_freeze", "final_text_validation", "structured_render", "finalize")}

    def node(name: str):
        def run(raw):
            calls[name] += 1
            current = AgenticRunState.model_validate(raw)
            freshness = check_artifact_freshness(
                repo_snapshot=load_repo_snapshot(current.artifacts["repo_snapshot"]),
                evidence_snapshot=load_evidence_snapshot_v2(current.artifacts["evidence_snapshot_v2"]),
                artifacts=current.artifacts,
            )
            if freshness.status != "passed":
                raise RuntimeError(f"freshness failed at {name}: {freshness.stale_artifact_keys}")
            update = {
                "phase_statuses": {name: "success"},
                "validation": {f"{name}_freshness": freshness.status},
                "decisions": [AgentDecision(node=name, decision="passed", rationale="Freshness and phase gate passed.").model_dump(mode="json")],
            }
            if name == "final_text_validation":
                update["loop_counters"] = {**current.loop_counters, "authoring": current.loop_counters.get("authoring", 0) + 1}
            return update
        return run

    def compile_graph(saver):
        builder = StateGraph(AgenticRunStateV2)
        phases = ["evidence_freeze", "final_text_validation", "structured_render", "finalize"]
        for phase in phases: builder.add_node(phase, node(phase))
        builder.add_edge(START, phases[0])
        for left, right in zip(phases, phases[1:]): builder.add_edge(left, right)
        builder.add_edge(phases[-1], END)
        return builder.compile(checkpointer=saver, interrupt_after=[interrupt_after] if interrupt_after else None)

    with open_sqlite_checkpointer(database) as saver:
        app = compile_graph(saver)
        first = app.invoke(state.model_dump(mode="json"), config=config)
    resumed = False
    if interrupt_after:
        with open_sqlite_checkpointer(database) as saver:
            app = compile_graph(saver)
            checkpoint_state, metadata = validate_resume_state(app.get_state(config).values)
            assert metadata.freshness_status == "passed" and checkpoint_state.run_id == state.run_id
            first = app.invoke(None, config=config)
            resumed = True
    payload = AgenticRunState.model_validate(first)
    final_digest = _digest({
        "artifacts": {key: _file_digest(Path(path)) for key, path in sorted(payload.artifacts.items())},
        "phase_statuses": payload.phase_statuses,
        "loop_counters": payload.loop_counters,
    })
    return {
        "interrupt_after": interrupt_after or "none",
        "resumed": resumed,
        "node_calls": calls,
        "skipped_completed_nodes": [name for name, count in calls.items() if count == 1 and interrupt_after and list(calls).index(name) <= list(calls).index(interrupt_after)],
        "freshness_status": payload.validation.get("finalize_freshness", ""),
        "final_loop_counters": payload.loop_counters,
        "final_digest": final_digest,
    }


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
