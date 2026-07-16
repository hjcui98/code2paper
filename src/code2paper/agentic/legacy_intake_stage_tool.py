from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.repo_snapshot import build_repo_snapshot, load_repo_snapshot, write_repo_snapshot
from code2paper.agentic.legacy_retrieval_focus import (
    analysis_repair_tasks_payload,
    apply_rescan_focus,
    rescan_focus_from_state,
)
from code2paper.agentic.retrieval import (
    build_agentic_retrieval_plan,
    build_retrieval_decision_context,
    build_retrieval_coverage_report,
    build_retrieval_rescan_plan,
    build_retrieval_rescan_report,
    build_symbol_index,
    enrich_plan_with_orchestrator_targets,
    write_coverage_report,
    write_retrieval_decision_context,
    write_retrieval_plan,
    write_retrieval_rescan_plan,
    write_retrieval_rescan_report,
    write_symbol_index,
)
from code2paper.agentic.retrieval_summary import build_retrieval_evidence_summary, write_retrieval_evidence_summary
from code2paper.agentic.retrieval_strategy_manifest import (
    build_retrieval_strategy_manifest,
    write_retrieval_strategy_manifest,
)
from code2paper.agentic.rescan_evidence_freeze import freeze_rescan_symbol_index_evidence
from code2paper.core.output_names import artifact_dir
from code2paper.export.run_manifest import hash_file
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stages.intake import run_phase1_intake


def run_intake(state: AgenticRunState) -> StageToolResult:
    author_path = _require_author_markers(state)
    current_snapshot = build_repo_snapshot(state.project_root)
    existing_snapshot_path = state.artifacts.get("repo_snapshot", "")
    if existing_snapshot_path and Path(existing_snapshot_path).exists():
        frozen_snapshot = load_repo_snapshot(existing_snapshot_path)
        if frozen_snapshot.project_tree_hash != current_snapshot.project_tree_hash:
            return StageToolResult(
                stage="intake",
                status=StageStatus.BLOCKED,
                artifacts={"repo_snapshot": existing_snapshot_path},
                blocked_reason="source_drift",
                summary="Repository changed after the run snapshot was frozen; start a new snapshot lineage.",
            )
        repo_snapshot = frozen_snapshot
        snapshot_path = Path(existing_snapshot_path)
    else:
        repo_snapshot = current_snapshot
        snapshot_path = artifact_dir(state.method_root, "01_input") / "repo_snapshot.json"
        write_repo_snapshot(snapshot_path, repo_snapshot)
    llm_config = load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)
    plan = build_agentic_retrieval_plan(author_markers_path=author_path, llm_config=llm_config)
    rescan_focus = rescan_focus_from_state(state)
    if rescan_focus:
        plan = apply_rescan_focus(plan, rescan_focus)
    plan = enrich_plan_with_orchestrator_targets(project_root=state.project_root, plan=plan)
    plan_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_plan.json"
    write_retrieval_plan(plan_path, plan)
    rescan_focus_path = artifact_dir(state.method_root, "02_intake") / "agentic_rescan_focus.json"
    if rescan_focus:
        _write_json(rescan_focus_path, rescan_focus)
    symbol_index = build_symbol_index(project_root=state.project_root, plan=plan)
    symbol_index_path = artifact_dir(state.method_root, "02_intake") / "agentic_symbol_index.json"
    write_symbol_index(symbol_index_path, symbol_index)
    raw_pack, _comment_index, _context_index, _context_map, paths = run_phase1_intake(
        project_root=state.project_root,
        method_root=state.method_root,
        author_markers_path=author_path,
        project_id=state.project_id or None,
        llm_config=llm_config,
        retrieval_hints_overlay=rescan_focus,
    )
    coverage = build_retrieval_coverage_report(
        plan=plan,
        snippets_payload=_read_json(paths["snippets"]) if paths["snippets"].exists() else {},
        alignment_payload=_read_json(paths["intake_alignment"]) if paths["intake_alignment"].exists() else {},
    )
    coverage_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_coverage.json"
    write_coverage_report(coverage_path, coverage)
    retrieval_context = build_retrieval_decision_context(coverage=coverage, symbol_index=symbol_index)
    retrieval_context_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_decision_context.json"
    write_retrieval_decision_context(retrieval_context_path, retrieval_context)
    rescan_plan = build_retrieval_rescan_plan(
        coverage=coverage,
        context=retrieval_context,
        repair_tasks_payload=analysis_repair_tasks_payload(state),
    )
    rescan_plan_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_rescan_plan.json"
    write_retrieval_rescan_plan(rescan_plan_path, rescan_plan)
    snippets_payload = _read_json(paths["snippets"]) if paths["snippets"].exists() else {}
    evidence_index_payload = _read_json(paths["evidence_index"]) if paths["evidence_index"].exists() else {}
    freeze_result = freeze_rescan_symbol_index_evidence(
        project_root=state.project_root,
        raw_pack=raw_pack,
        snippets_payload=snippets_payload,
        evidence_index={str(key): str(value) for key, value in evidence_index_payload.items()},
        rescan_plan=rescan_plan,
        symbol_index=symbol_index,
    )
    if freeze_result.frozen_count:
        raw_pack = freeze_result.raw_pack
        snippets_payload = freeze_result.snippets_payload
        evidence_index_payload = freeze_result.evidence_index
        _write_json(paths["evidence_raw"], raw_pack.model_dump(mode="json"))
        _write_json(paths["snippets"], snippets_payload)
        _write_json(paths["evidence_index"], evidence_index_payload)
        _refresh_phase1_manifest_hashes(paths, ("evidence_raw", "snippets", "evidence_index"))
    rescan_report = build_retrieval_rescan_report(
        plan=rescan_plan,
        snippets_payload=snippets_payload,
        snippet_to_evidence={str(key): str(value) for key, value in evidence_index_payload.items()},
        symbol_index=symbol_index,
    )
    rescan_report_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_rescan_report.json"
    write_retrieval_rescan_report(rescan_report_path, rescan_report)
    retrieval_summary = build_retrieval_evidence_summary(
        coverage=coverage,
        symbol_index=symbol_index,
        context=retrieval_context,
        rescan_report=rescan_report,
    )
    retrieval_summary_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_summary.json"
    write_retrieval_evidence_summary(retrieval_summary_path, retrieval_summary)
    strategy_manifest = build_retrieval_strategy_manifest(
        plan=plan,
        coverage=coverage,
        symbol_index=symbol_index,
        rescan_plan=rescan_plan,
        rescan_report=rescan_report,
        summary=retrieval_summary,
    )
    strategy_manifest_path = artifact_dir(state.method_root, "02_intake") / "agentic_retrieval_strategy_manifest.json"
    write_retrieval_strategy_manifest(strategy_manifest_path, strategy_manifest)
    artifacts = _existing_paths(paths)
    artifacts.update(
        {
            "repo_snapshot": str(snapshot_path),
            "retrieval_plan": str(plan_path),
            "symbol_index": str(symbol_index_path),
            "retrieval_coverage": str(coverage_path),
            "retrieval_decision_context": str(retrieval_context_path),
            "retrieval_rescan_plan": str(rescan_plan_path),
            "retrieval_rescan_report": str(rescan_report_path),
            "retrieval_summary": str(retrieval_summary_path),
            "retrieval_strategy_manifest": str(strategy_manifest_path),
        }
    )
    if rescan_focus:
        artifacts["rescan_focus"] = str(rescan_focus_path)
    return StageToolResult(
        stage="intake",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary="Retrieved code evidence, indexed code symbols, and evaluated retrieval target coverage.",
        decisions=[
            AgentDecision(
                node="retrieval_planner",
                decision="plan_then_intake",
                rationale=(
                    f"{len(plan.targets)} retrieval targets; "
                    f"symbol_candidates={len(symbol_index.candidates)}; "
                    f"coverage_score={coverage.overall_score:.2f}; "
                    f"focused_paths={len(rescan_focus.get('priority_paths', [])) if rescan_focus else 0}"
                ),
                artifact_keys=[
                    "repo_snapshot",
                    "retrieval_plan",
                    *(["rescan_focus"] if rescan_focus else []),
                    "symbol_index",
                    "retrieval_coverage",
                    "retrieval_decision_context",
                    "retrieval_rescan_plan",
                    "retrieval_rescan_report",
                    "retrieval_summary",
                    "retrieval_strategy_manifest",
                ],
            )
        ],
        metrics={
            "retrieval_targets": len(plan.targets),
            "symbol_candidates": len(symbol_index.candidates),
            "focused_paths": len(rescan_focus.get("priority_paths", [])) if rescan_focus else 0,
            "focused_symbols": len(rescan_focus.get("symbol_targets", [])) if rescan_focus else 0,
            "coverage_score": coverage.overall_score,
            "missing_targets": coverage.missing_targets,
            "rescan_plan_items": len(rescan_plan.items),
            "rescan_covered_items": rescan_report.covered_items,
            "rescan_missing_items": rescan_report.missing_items,
            "rescan_frozen_evidence_items": freeze_result.frozen_count,
            "retrieval_summary_actions": len(retrieval_summary.recommended_actions),
            "retrieval_strategy_rules": len(strategy_manifest.evidence_guardrails),
        },
    )


def _require_author_markers(state: AgenticRunState) -> str:
    author_path = state.effective_author_markers_path
    if not author_path:
        raise ValueError("author_markers_path or resolved_author_markers artifact is required")
    return author_path


def _existing_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items() if path.exists()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _refresh_phase1_manifest_hashes(paths: dict[str, Path], names: tuple[str, ...]) -> None:
    manifest_path = paths["phase1_manifest"]
    manifest = _read_json(manifest_path)
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
    for name in names:
        path = paths[name]
        if path.exists():
            outputs[name] = {"path": str(path), "hash": hash_file(path)}
    manifest["outputs"] = outputs
    _write_json(manifest_path, manifest)
