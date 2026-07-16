from __future__ import annotations

from typing import Any

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.readiness_io import artifact_json, dedupe, has_any_artifact, list_value, string_list
from code2paper.agentic.readiness_models import ReadinessCheck


def check_authoring_context_contract(state: AgenticRunState) -> ReadinessCheck:
    has_text = has_any_artifact(state, "text_md", "text_clean_md", "text_tex", "text_clean_tex")
    if not has_text:
        return ReadinessCheck(
            name="authoring_context_contract",
            passed=True,
            blocking=False,
            message="No Method text was produced; evidence-bound authoring context is not required.",
            artifact_keys=["authoring_projection", "authoring_plan", "authoring_plan_decision_trace", "final_text_claims", "text_evidence_validation", "final_text_trace"],
        )
    required = [
        "authoring_projection",
        "authoring_plan",
        "authoring_plan_decision_trace",
        "final_text_claims",
        "text_evidence_validation",
        "final_text_trace",
    ]
    missing = [key for key in required if not artifact_json(state, key)]
    problems: list[str] = []
    if missing:
        problems.append("Method text exists but authoring trace artifacts are missing or unreadable: " + ", ".join(missing))
    else:
        validation = artifact_json(state, "text_evidence_validation")
        trace = artifact_json(state, "final_text_trace")
        claims = artifact_json(state, "final_text_claims")
        projection = artifact_json(state, "authoring_projection")
        mismatch = _text_trace_authoring_plan_mismatch(
            final_text_trace=trace,
            authoring_plan=artifact_json(state, "authoring_plan"),
        )
        if mismatch:
            problems.append(mismatch)
        if str(validation.get("status") or "") != "passed" or not bool(trace.get("hard_gate_passed")):
            problems.append("final text evidence validation or trace gate did not pass")
        text_digests = {
            str(claims.get("input_text_digest") or ""),
            str(validation.get("input_text_digest") or ""),
            str(trace.get("input_text_digest") or ""),
        }
        if "" in text_digests or len(text_digests) != 1:
            problems.append("final text trust artifact digests do not match")
        projection_digest = projection.get("projection_digest")
        if not projection_digest or validation.get("projection_digest") != projection_digest or trace.get("projection_digest") != projection_digest:
            problems.append("authoring projection digest is stale or mismatched")
        identity_fields = ("repo_snapshot_id", "project_tree_hash", "evidence_snapshot_id", "evidence_snapshot_digest")
        for field in identity_fields:
            expected = projection.get(field)
            if expected and (validation.get(field) != expected or trace.get(field) != expected):
                problems.append(f"final text trust artifact {field} is stale or mismatched")
    return ReadinessCheck(
        name="authoring_context_contract",
        passed=not problems,
        message="Method text has a projection-bound plan, passed atomic-claim validation, and authoritative post-hoc trace."
        if not problems
        else "; ".join(problems),
        artifact_keys=[*required, "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
    )


def check_traceability_ledger_contract(state: AgenticRunState) -> ReadinessCheck:
    public_output = has_any_artifact(
        state,
        "text_md",
        "text_clean_md",
        "text_tex",
        "text_clean_tex",
        "figure_plan",
        "final_tex",
        "final_pdf",
        "finalize_manifest",
    )
    ledger = artifact_json(state, "traceability_ledger")
    if not public_output and not ledger:
        return ReadinessCheck(
            name="traceability_ledger_contract",
            passed=True,
            blocking=False,
            message="No paper-facing text, figure, or final package was produced; ledger is not required.",
            artifact_keys=["traceability_ledger"],
        )
    passed = bool(ledger) and bool(ledger.get("hard_gate_passed"))
    return ReadinessCheck(
        name="traceability_ledger_contract",
        passed=passed,
        message="Traceability ledger is present and hard-gate passed."
        if passed
        else "Paper-facing output exists but traceability ledger is missing, unreadable, or hard_gate_passed=false.",
        artifact_keys=["traceability_ledger", "final_text_trace", "figure_plan", "figure_plan_decision_trace"],
    )


def check_invariant_audit_contract(state: AgenticRunState) -> ReadinessCheck:
    audit = artifact_json(state, "agentic_invariant_audit")
    passed = bool(audit) and bool(audit.get("passed"))
    return ReadinessCheck(
        name="invariant_audit_contract",
        passed=passed,
        message="Invariant audit is present and passed." if passed else "Invariant audit is missing, unreadable, or failed.",
        artifact_keys=["agentic_invariant_audit"],
    )


def _text_trace_authoring_plan_mismatch(*, final_text_trace: dict[str, Any], authoring_plan: dict[str, Any]) -> str:
    planned_claim_ids: set[str] = set()
    planned_evidence_ids: set[str] = set()
    for section in list_value(authoring_plan.get("sections")):
        if not isinstance(section, dict):
            continue
        planned_claim_ids.update(string_list(section.get("claim_ids")))
        planned_evidence_ids.update(string_list(section.get("evidence_ids")))
    unplanned_claim_ids: list[str] = []
    unplanned_evidence_ids: list[str] = []
    for entry in list_value(final_text_trace.get("entries")):
        if not isinstance(entry, dict):
            continue
        claim_ids = string_list(entry.get("projection_claim_ids"))
        evidence_ids = string_list(entry.get("direct_evidence_ids"))
        if planned_claim_ids:
            unplanned_claim_ids.extend([claim_id for claim_id in claim_ids if claim_id not in planned_claim_ids])
        if planned_evidence_ids:
            unplanned_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in planned_evidence_ids])
    problems: list[str] = []
    if unplanned_claim_ids:
        problems.append("text claim ids outside authoring plan: " + ", ".join(dedupe(unplanned_claim_ids)[:8]))
    if unplanned_evidence_ids:
        problems.append("text evidence ids outside authoring plan: " + ", ".join(dedupe(unplanned_evidence_ids)[:8]))
    return "; ".join(problems)
