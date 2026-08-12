from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.invariant_audit import check_final_package_traceability
from code2paper.agentic.readiness_io import artifact_exists, artifact_json, has_any_artifact


class CompletionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    deliverable: str
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=list)


class AgenticRunCompletionReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-run-completion-report"
    status: str
    complete: bool
    blocked_reason: str = ""
    missing_deliverables: list[str] = Field(default_factory=list)
    checks: list[CompletionCheck] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_run_completion_report(state: AgenticRunState) -> AgenticRunCompletionReport:
    checks = [
        _check_evidence_base(state),
        _check_method_text(state),
        _check_method_usability(state),
        _check_method_figure(state),
        _check_validation(state),
        _check_traceability(state),
        _check_final_package(state),
    ]
    missing = [check.deliverable for check in checks if not check.passed]
    complete = not missing and not state.blocked_reason
    status = "blocked" if state.blocked_reason else "complete" if complete else "incomplete"
    return AgenticRunCompletionReport(
        status=status,
        complete=complete,
        blocked_reason=state.blocked_reason,
        missing_deliverables=missing,
        checks=checks,
        recommended_actions=_recommended_actions(missing, state.blocked_reason),
    )


def write_run_completion_report(path: str | Path, report: AgenticRunCompletionReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_run_completion_report(path: str | Path) -> AgenticRunCompletionReport:
    return AgenticRunCompletionReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _check_evidence_base(state: AgenticRunState) -> CompletionCheck:
    required = ["evidence", "claims", "claim_verification"]
    if artifact_exists(state, "repo_snapshot"):
        required.extend(["intent_spec", "repo_snapshot", "evidence_snapshot_v2", "atomic_claims_v2", "artifact_freshness"])
    missing = [key for key in required if not artifact_exists(state, key)]
    freshness = artifact_json(state, "artifact_freshness")
    stale = "artifact_freshness" in required and (
        freshness.get("status") != "passed" or bool(freshness.get("source_drift"))
    )
    return CompletionCheck(
        name="evidence_base",
        passed=not missing and not stale,
        deliverable="evidence_base",
        message="Frozen evidence, claim map, claim verification, and source freshness are present."
        if not missing and not stale
        else "Evidence base is missing or stale: " + ", ".join(missing or ["artifact_freshness"]),
        artifact_keys=required,
    )


def _check_method_text(state: AgenticRunState) -> CompletionCheck:
    has_text = has_any_artifact(state, "text_md", "text_clean_md", "text_tex", "text_clean_tex")
    final_claims = artifact_json(state, "final_text_claims")
    validation = artifact_json(state, "text_evidence_validation")
    final_trace = artifact_json(state, "final_text_trace")
    has_trace = (
        bool(final_claims)
        and str(validation.get("status") or "") == "passed"
        and bool(final_trace.get("hard_gate_passed"))
        and bool(final_claims.get("input_text_digest"))
        and final_claims.get("input_text_digest") == validation.get("input_text_digest") == final_trace.get("input_text_digest")
    )
    return CompletionCheck(
        name="method_text",
        passed=has_text and has_trace,
        deliverable="method_text",
        message="Method text passed final atomic-claim evidence validation and post-hoc trace."
        if has_text and has_trace
        else "Method text requires final_text_claims, passed text_evidence_validation, and a digest-matched final_text_trace.",
        artifact_keys=["text_md", "text_clean_md", "text_tex", "text_clean_tex", "final_text_claims", "text_evidence_validation", "final_text_trace"],
    )


def _check_method_usability(state: AgenticRunState) -> CompletionCheck:
    publication_quality = artifact_json(state, "publication_quality_report_v1")
    if publication_quality:
        safety = publication_quality.get("safety") or {}
        utility = publication_quality.get("utility") or {}
        passed = bool(
            publication_quality.get("status") == "publication_ready"
            and publication_quality.get("plan_gate_passed")
            and publication_quality.get("final_integrity_gate_passed")
            and safety.get("hard_gate_passed")
            and utility.get("utility_gate_passed")
        )
        return CompletionCheck(
            name="method_usability",
            passed=passed,
            deliverable="method_usability",
            message=(
                "Method passed separate epistemic-safety and publication-utility gates."
                if passed else
                "Method is safe or partially authored but has not reached publication_ready utility."
            ),
            artifact_keys=[
                "publication_quality_report_v1",
                "method_section_plan_v2",
                "final_text_authorship_ledger_v1",
            ],
        )
    coverage = artifact_json(state, "authoring_obligation_coverage")
    if not coverage:
        return CompletionCheck(
            name="method_usability",
            passed=True,
            deliverable="method_usability",
            message="Obligation coverage is not available for this compatibility run; usability was not assessed.",
            artifact_keys=[],
        )
    must_cover = int(coverage.get("must_cover_count") or 0)
    covered = int(coverage.get("candidate_covered_must_cover_count") or 0)
    unresolved = [str(item) for item in coverage.get("unresolved_must_cover_ids", []) if str(item)]
    unique_claims = int(coverage.get("unique_projected_claim_count") or 0)
    passed = (must_cover == 0 or (covered == must_cover and not unresolved)) and unique_claims > 0
    return CompletionCheck(
        name="method_usability",
        passed=passed,
        deliverable="method_usability",
        message=(
            "Every must-cover author obligation is represented by an authorized code-evidence claim."
            if passed
            else (
                f"Method remains trustworthy but incomplete: covered {covered}/{must_cover} must-cover obligations; "
                f"unique projected claims={unique_claims}; unresolved={', '.join(unresolved) or 'none'}."
            )
        ),
        artifact_keys=["intent_obligation_graph", "authoring_obligation_coverage", "authoring_projection"],
    )
def _check_method_figure(state: AgenticRunState) -> CompletionCheck:
    plan = artifact_json(state, "figure_plan")
    scene = artifact_json(state, "figure_scene")
    relation_validation = artifact_json(state, "figure_relation_validation")
    manifest = artifact_json(state, "rendering_manifest")
    post_audit = artifact_json(state, "post_render_audit")
    has_trace = artifact_exists(state, "figure_plan_decision_trace")
    formal_p2 = artifact_exists(state, "repo_snapshot")
    passed = (
        bool(plan) and bool(plan.get("hard_gate_passed")) and has_trace
        and bool(scene.get("hard_gate_passed")) and bool(relation_validation.get("hard_gate_passed"))
        and artifact_exists(state, "method_overview_svg") and bool(manifest)
        and bool(post_audit.get("hard_gate_passed"))
    )
    if not formal_p2:
        passed = bool(plan) and bool(plan.get("hard_gate_passed")) and has_trace
    return CompletionCheck(
        name="method_figure",
        passed=passed,
        deliverable="method_figure",
        message="Method figure has a relation-backed scene, real SVG asset, manifest, and passed post-render audit."
        if passed
        else "Method figure requires a passed scene/relation gate plus real SVG, manifest, and post-render audit.",
        artifact_keys=["figure_plan", "figure_plan_decision_trace", "figure_scene", "figure_relation_validation", "method_overview_svg", "rendering_manifest", "post_render_audit"],
    )


def _check_validation(state: AgenticRunState) -> CompletionCheck:
    validation = artifact_json(state, "validation_manifest")
    passed = _status_passed(validation)
    return CompletionCheck(
        name="validation",
        passed=passed,
        deliverable="validation",
        message="Validation manifest passed." if passed else "Validation manifest is missing or not passed.",
        artifact_keys=["validation_manifest", "fidelity", "qa_claims", "qa_numbers", "qa_equations", "qa_terms", "qa_latex"],
    )


def _check_traceability(state: AgenticRunState) -> CompletionCheck:
    ledger = artifact_json(state, "traceability_ledger")
    audit = artifact_json(state, "agentic_invariant_audit")
    readiness = artifact_json(state, "agentic_run_readiness_report")
    passed = bool(ledger.get("hard_gate_passed")) and bool(audit.get("passed")) and bool(readiness.get("passed"))
    return CompletionCheck(
        name="traceability",
        passed=passed,
        deliverable="traceability",
        message="Traceability ledger, invariant audit, and readiness report passed."
        if passed
        else "Traceability requires passing ledger, invariant audit, and readiness report.",
        artifact_keys=["traceability_ledger", "agentic_invariant_audit", "agentic_run_readiness_report"],
    )


def _check_final_package(state: AgenticRunState) -> CompletionCheck:
    has_final_tex = artifact_exists(state, "final_tex")
    has_manifest = artifact_json(state, "finalize_manifest")
    lineage_check = check_final_package_traceability(state)
    requires_formal_lineage = artifact_exists(state, "repo_snapshot")
    has_package_manifest = bool(artifact_json(state, "package_manifest"))
    passed = has_final_tex and bool(has_manifest) and (
        not requires_formal_lineage or (has_package_manifest and lineage_check.passed)
    )
    return CompletionCheck(
        name="final_package",
        passed=passed,
        deliverable="final_package",
        message="Final text, figure, PDF, and audit lineage hashes are bound by the package manifest."
        if passed
        else (
            lineage_check.message
            if requires_formal_lineage
            else "Final package requires final_tex and finalize_manifest."
        ),
        artifact_keys=["final_tex", "final_pdf", "finalize_manifest", "package_manifest"],
    )


def _status_passed(payload: dict[str, object]) -> bool:
    status = str(payload.get("status") or payload.get("overall_status") or "").strip().lower()
    if status in {"success", "passed", "ok"}:
        return True
    return bool(payload.get("passed"))


def _recommended_actions(missing: list[str], blocked_reason: str) -> list[str]:
    if blocked_reason:
        return ["inspect_blocked_reason_and_router_trace"]
    actions = {
        "evidence_base": "produce_frozen_code_evidence_and_claim_verification",
        "method_text": "produce_evidence_backed_method_text",
        "method_usability": "resolve_must_cover_author_obligations_or_record_terminal_code_gaps",
        "method_figure": "produce_evidence_backed_method_figure_plan",
        "validation": "run_method_validation",
        "traceability": "pass_traceability_and_invariant_readiness_gates",
        "final_package": "assemble_final_method_package",
    }
    return [actions[item] for item in missing] or ["agentic_run_completion_ready"]
