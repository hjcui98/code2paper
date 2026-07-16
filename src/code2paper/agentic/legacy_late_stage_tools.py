from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.author_intent_summary import author_intent_summary_from_state
from code2paper.agentic.claim_verifier import build_claim_verification_report, load_claim_verification_report, write_claim_verification_report
from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.decision_core import write_decision_trace
from code2paper.agentic.figure_planner import figure_plan_trace, load_figure_plan, write_figure_plan
from code2paper.agentic.render_authorization import check_pre_render_authorization, pre_render_blocked_result
from code2paper.agentic.figure_scene import load_figure_scene_graph
from code2paper.agentic.post_render_audit import audit_rendered_svg, write_post_render_audit
from code2paper.rendering.scene_svg import render_scene_svg
from code2paper.rendering.figure_manifest import build_figure_manifest, write_figure_manifest
from code2paper.core.output_names import artifact_dir, final_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, RawEvidencePack
from code2paper.pipeline.stages.finalize import write_phase8_artifacts
from code2paper.pipeline.stages.rendering import write_phase7_rendering_manifest
from code2paper.pipeline.stages.validation import write_phase6_validation_manifest
from code2paper.validation.fidelity_validator import validate_method_fidelity


def run_validation(state: AgenticRunState) -> StageToolResult:
    text_path = method_output(state.method_root, "text_md")
    if not text_path.exists():
        text_path = method_output(state.method_root, "text_clean_md")
    if not text_path.exists():
        manifest = write_phase6_validation_manifest(
            method_root=state.method_root,
            fidelity_passed=False,
            validation_skipped_reason="method_text_missing",
        )
        return StageToolResult(
            stage="validation",
            status=StageStatus.BLOCKED,
            artifacts={"validation_manifest": str(method_output(state.method_root, "phase6_manifest"))},
            blocked_reason="method_text_missing",
            summary=str(manifest.get("status") or "skipped"),
        )
    report = validate_method_fidelity(
        raw_pack=RawEvidencePack.model_validate(_read_json(method_output(state.method_root, "evidence_raw"))),
        method_evidence=MethodEvidence.model_validate(_read_json(method_output(state.method_root, "evidence"))),
        draft_markdown=text_path.read_text(encoding="utf-8"),
        claim_map=ClaimEvidenceMap.model_validate(_read_json(method_output(state.method_root, "claims"))),
    )
    fidelity_path = method_output(state.method_root, "fidelity")
    fidelity_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = write_phase6_validation_manifest(method_root=state.method_root, fidelity_passed=report.passed)
    validation_passed = bool(report.passed) and str(manifest.get("status") or "").lower() in {"passed", "success", "ok"}
    return StageToolResult(
        stage="validation",
        status=StageStatus.SUCCESS if validation_passed else StageStatus.BLOCKED,
        artifacts={
            "fidelity": str(fidelity_path),
            "validation_manifest": str(method_output(state.method_root, "phase6_manifest")),
        },
        blocked_reason="" if validation_passed else "validation_manifest_failed",
        summary=f"fidelity_passed={report.passed}; validation_status={manifest.get('status')}",
        metrics={"fidelity_passed": report.passed, "validation_passed": validation_passed},
    )


def run_rendering(state: AgenticRunState) -> StageToolResult:
    authorization = check_pre_render_authorization(state)
    if not authorization.passed:
        return pre_render_blocked_result("rendering", authorization)
    text_path = _method_text_path(state)
    if text_path is None:
        return StageToolResult(
            stage="rendering",
            status=StageStatus.BLOCKED,
            blocked_reason="method_text_required_for_rendering",
            summary="Rendering requires validated method text.",
        )
    formal_p2 = bool(state.artifacts.get("repo_snapshot"))
    scene_path = state.artifacts.get("figure_scene", "")
    pre_audit = state.artifacts.get("pre_render_audit", "")
    if formal_p2 and (not scene_path or not Path(scene_path).exists() or not pre_audit or not Path(pre_audit).exists()):
        return StageToolResult(
            stage="rendering", status=StageStatus.BLOCKED,
            blocked_reason="figure_scene_and_pre_render_audit_required",
            summary="Structured rendering requires a passed FigureSceneGraph pre-render contract.",
        )
    pre_payload = _read_json(Path(pre_audit)) if pre_audit and Path(pre_audit).exists() else {}
    if formal_p2 and not pre_payload.get("hard_gate_passed"):
        return StageToolResult(
            stage="rendering", status=StageStatus.BLOCKED,
            blocked_reason="pre_render_audit_failed", summary="Pre-render relation/scene audit failed.",
        )
    if formal_p2:
        scene = load_figure_scene_graph(scene_path)
    else:
        scene = None
    if formal_p2 and scene is not None:
        figure_root = final_dir(state.method_root, "figures")
        svg_path = figure_root / "method_overview.svg"
        render_scene_svg(scene, svg_path)
        manifest = build_figure_manifest(scene_digest=scene.content_digest, asset_path=svg_path)
        manifest_path = figure_root / "agentic_rendering_manifest.json"
        write_figure_manifest(manifest_path, manifest)
        post_audit = audit_rendered_svg(scene, manifest)
        post_audit_path = figure_root / "agentic_post_render_audit.json"
        write_post_render_audit(post_audit_path, post_audit)
        artifacts = {
            "figure_plan": state.artifacts.get("figure_plan", ""),
            "figure_plan_decision_trace": state.artifacts.get("figure_plan_decision_trace", ""),
            "method_overview_svg": str(svg_path), "method_overview_meta": str(manifest_path),
            "rendering_manifest": str(manifest_path), "post_render_audit": str(post_audit_path),
        }
        if not post_audit.hard_gate_passed:
            return StageToolResult(
                stage="rendering", status=StageStatus.BLOCKED, artifacts=artifacts,
                blocked_reason="post_render_audit_failed",
                summary="Rendered SVG drifted from the locked FigureSceneGraph.",
            )
        return StageToolResult(
            stage="rendering", status=StageStatus.SUCCESS, artifacts=artifacts,
            summary="Rendered and post-audited deterministic evidence-backed SVG.",
            decisions=[AgentDecision(
                node="structured_renderer", decision="post_render_passed",
                rationale="Every rendered scene element, label, endpoint, and digest matches the locked scene.",
                artifact_keys=["figure_scene", "method_overview_svg", "rendering_manifest", "post_render_audit"],
            )],
            metrics={"rendered_elements": post_audit.rendered_elements, "rendered_element_drift": 0},
        )
    method_evidence = MethodEvidence.model_validate(_read_json(method_output(state.method_root, "evidence")))
    claim_map = ClaimEvidenceMap.model_validate(_read_json(method_output(state.method_root, "claims")))
    verification_path = _claim_verification_path(state)
    if verification_path.exists():
        verification = load_claim_verification_report(verification_path)
    else:
        verification = build_claim_verification_report(method_evidence, claim_map)
        write_claim_verification_report(verification_path, verification)

    figure_root = final_dir(state.method_root, "figures")
    figure_plan_path = figure_root / "method_overview.intent.json"
    existing_figure_plan = state.artifacts.get("figure_plan", "")
    existing_trace = state.artifacts.get("figure_plan_decision_trace", "")
    if existing_figure_plan and Path(existing_figure_plan).exists() and existing_trace and Path(existing_trace).exists():
        figure_plan = load_figure_plan(existing_figure_plan)
        figure_plan_path = Path(existing_figure_plan)
        trace_path = Path(existing_trace)
    else:
        figure_plan, trace = figure_plan_trace(
            method_evidence=method_evidence,
            claim_map=claim_map,
            claim_verification=verification,
            author_intent_summary=author_intent_summary_from_state(state),
        )
        write_figure_plan(figure_plan_path, figure_plan)
        trace_path = figure_root / "method_overview.intent.decision_trace.json"
        write_decision_trace(trace_path, trace)
    figure_meta = {
        "status": "planned",
        "backend": "agentic-rendering-plan",
        "intent_path": str(figure_plan_path),
        "decision_trace_path": str(trace_path),
        "evidence_backed": figure_plan.hard_gate_passed,
        "nodes": len(figure_plan.nodes),
        "edges": len(figure_plan.edges),
    }
    skipped_reason = "" if figure_plan.hard_gate_passed else "figure_plan_missing_supported_evidence"
    write_phase7_rendering_manifest(
        method_root=state.method_root,
        figure_root=figure_root,
        figure_meta=figure_meta,
        figure_skipped_reason=skipped_reason,
        method_pdf_report=None,
    )
    artifacts = {
        "figure_plan": str(figure_plan_path),
        "figure_plan_decision_trace": str(trace_path),
        "rendering_manifest": str(method_output(state.method_root, "phase7_manifest")),
    }
    if not figure_plan.hard_gate_passed:
        return StageToolResult(
            stage="rendering",
            status=StageStatus.BLOCKED,
            artifacts=artifacts,
            blocked_reason=skipped_reason,
            summary="Figure rendering blocked because no evidence-backed figure plan is available.",
            decisions=[
                AgentDecision(
                    node="figure_planner",
                    decision="figure_plan_blocked",
                    rationale="; ".join(figure_plan.recommended_actions),
                    artifact_keys=["figure_plan", "figure_plan_decision_trace"],
                )
            ],
            metrics={"figure_nodes": len(figure_plan.nodes), "figure_edges": len(figure_plan.edges)},
        )
    return StageToolResult(
        stage="rendering",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary="Planned evidence-backed method overview figure.",
        decisions=[
            AgentDecision(
                node="figure_planner",
                decision="figure_plan_ready",
                rationale="; ".join(figure_plan.recommended_actions),
                artifact_keys=["figure_plan", "figure_plan_decision_trace"],
            )
        ],
        metrics={"figure_nodes": len(figure_plan.nodes), "figure_edges": len(figure_plan.edges)},
    )


def run_finalize(state: AgenticRunState) -> StageToolResult:
    final_audit_path = state.artifacts.get("final_invariant_audit", "")
    if state.artifacts.get("repo_snapshot") and (not final_audit_path or not Path(final_audit_path).exists() or not _read_json(Path(final_audit_path)).get("passed")):
        return StageToolResult(
            stage="finalize", status=StageStatus.BLOCKED,
            blocked_reason="final_invariant_audit_required",
            summary="Finalize requires a passed post-render final invariant audit.",
        )
    authorization = check_pre_render_authorization(state)
    if not authorization.passed:
        return pre_render_blocked_result("finalize", authorization)
    text_path = method_output(state.method_root, "text_clean_tex")
    if not text_path.exists():
        text_path = method_output(state.method_root, "text_tex")
    if not text_path.exists():
        return StageToolResult(
            stage="finalize",
            status=StageStatus.BLOCKED,
            blocked_reason="method_tex_required_for_finalize",
            summary="Finalize requires validated method TeX.",
        )
    figure_root = final_dir(state.method_root, "figures")
    report = write_phase8_artifacts(
        method_root=state.method_root,
        method_tex_path=text_path,
        figure_candidates=[
            figure_root / "method_overview.png",
            figure_root / "method_overview.pdf",
            figure_root / "method_overview.svg",
        ],
        equations_tex_path=method_output(state.method_root, "equations_tex"),
        symbols_tex_path=method_output(state.method_root, "symbols_tex"),
        compiler=None,
        timeout_seconds=300,
        figure_caption="Evidence-backed method overview.",
        figure_asset_basename="method_framework",
    )
    artifacts = _existing_paths(
        {
            "final_tex": method_output(state.method_root, "final_tex"),
            "final_pdf": method_output(state.method_root, "final_pdf"),
            "final_pdf_report": method_output(state.method_root, "final_pdf_report"),
            "finalize_manifest": method_output(state.method_root, "phase8_manifest"),
        }
    )
    return StageToolResult(
        stage="finalize",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary=f"Finalized method package with status={report.get('status', 'unknown')}.",
        decisions=[
            AgentDecision(
                node="finalize_packager",
                decision=str(report.get("status") or "unknown"),
                rationale=str(report.get("reason") or "Final package artifacts written."),
                artifact_keys=["final_tex", "final_pdf", "final_pdf_report", "finalize_manifest"],
            )
        ],
        metrics={"finalize_status": str(report.get("status") or "unknown")},
    )


def _claim_verification_path(state: AgenticRunState) -> Path:
    artifact = state.artifacts.get("claim_verification", "")
    if artifact:
        return Path(artifact)
    return artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"


def _existing_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items() if path.exists()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _method_text_path(state: AgenticRunState) -> Path | None:
    for key in ("text_clean_md", "text_md", "text_clean_tex", "text_tex"):
        path = method_output(state.method_root, key)
        if path.exists():
            return path
    return None
