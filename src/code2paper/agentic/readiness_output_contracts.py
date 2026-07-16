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
            artifact_keys=["authoring_context", "authoring_plan", "authoring_plan_decision_trace", "authoring_constraints", "text_claims"],
        )
    required = ["authoring_context", "authoring_plan", "authoring_plan_decision_trace", "authoring_constraints", "text_claims"]
    missing = [key for key in required if not artifact_json(state, key)]
    problems: list[str] = []
    if missing:
        problems.append("Method text exists but authoring trace artifacts are missing or unreadable: " + ", ".join(missing))
    else:
        mismatch = _text_trace_authoring_plan_mismatch(
            text_claims=artifact_json(state, "text_claims"),
            authoring_plan=artifact_json(state, "authoring_plan"),
        )
        if mismatch:
            problems.append(mismatch)
    return ReadinessCheck(
        name="authoring_context_contract",
        passed=not problems,
        message="Method text has evidence-bound authoring context, section plan, constraints, and paragraph trace records."
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
        artifact_keys=["traceability_ledger", "text_claims", "figure_plan", "figure_plan_decision_trace"],
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


def _text_trace_authoring_plan_mismatch(*, text_claims: dict[str, Any], authoring_plan: dict[str, Any]) -> str:
    planned_claim_ids: set[str] = set()
    planned_evidence_ids: set[str] = set()
    for section in list_value(authoring_plan.get("sections")):
        if not isinstance(section, dict):
            continue
        planned_claim_ids.update(string_list(section.get("claim_ids")))
        planned_evidence_ids.update(string_list(section.get("evidence_ids")))
    unplanned_claim_ids: list[str] = []
    unplanned_evidence_ids: list[str] = []
    for paragraph in list_value(text_claims.get("paragraphs")):
        if not isinstance(paragraph, dict):
            continue
        claim_ids = string_list(paragraph.get("claim_ids"))
        evidence_ids = string_list(paragraph.get("evidence_span_ids"))
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
