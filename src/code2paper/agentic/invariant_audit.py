from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evaluation_extractors import validation_passed
from code2paper.agentic.final_text_claims import text_digest
from code2paper.agentic.traceability_ledger import build_traceability_ledger


class InvariantCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    blocking: bool = True
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=list)


class AgenticInvariantAudit(BaseModel):
    """Machine-readable audit of Code2Paper's non-negotiable evidence invariants."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-invariant-audit"
    passed: bool
    blocking_failures: int = 0
    checks: list[InvariantCheck] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_invariant_audit(state: AgenticRunState) -> AgenticInvariantAudit:
    checks = [
        _check_frozen_evidence_present(state),
        _check_claim_verification(state),
        _check_evidence_sufficiency(state),
        _check_authoring_constraints(state),
        _check_authoring_context(state),
        _check_authoring_plan(state),
        _check_final_text_evidence_gate(state),
        _check_text_claim_traceability(state),
        _check_traceability_ledger(state),
        _check_validation_after_text(state),
        _check_final_package_traceability(state),
        _check_figure_plan(state),
    ]
    blocking_failures = sum(1 for check in checks if check.blocking and not check.passed)
    return AgenticInvariantAudit(
        passed=blocking_failures == 0,
        blocking_failures=blocking_failures,
        checks=checks,
        recommended_actions=_recommended_actions(checks),
    )


def write_invariant_audit(path: str | Path, audit: AgenticInvariantAudit) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(audit.model_dump_json(indent=2), encoding="utf-8")
    return output


def load_invariant_audit(path: str | Path) -> AgenticInvariantAudit:
    return AgenticInvariantAudit.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _check_frozen_evidence_present(state: AgenticRunState) -> InvariantCheck:
    required = ["evidence", "claims", "claim_verification"]
    missing = [key for key in required if not _artifact_exists(state, key)]
    return InvariantCheck(
        name="frozen_evidence_gate",
        passed=not missing,
        message="Frozen MethodEvidence, claim map, and claim verification are present."
        if not missing
        else "Missing frozen evidence artifacts: " + ", ".join(missing),
        artifact_keys=required,
    )


def _check_claim_verification(state: AgenticRunState) -> InvariantCheck:
    payload = _artifact_json(state, "claim_verification")
    if not payload:
        return InvariantCheck(
            name="claim_verification_audit",
            passed=False,
            message="claim_verification artifact is missing or unreadable.",
            artifact_keys=["claim_verification"],
        )
    claims = payload.get("claims", []) if isinstance(payload.get("claims", []), list) else []
    unsupported = [
        str(claim.get("claim_id") or "")
        for claim in claims
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    ]
    missing_evidence = int(payload.get("claims_with_missing_evidence") or 0)
    if missing_evidence:
        return InvariantCheck(
            name="claim_verification_audit",
            passed=False,
            message=f"{missing_evidence} claims reference missing evidence ids.",
            artifact_keys=["claim_verification"],
        )
    return InvariantCheck(
        name="claim_verification_audit",
        passed=True,
        blocking=False,
        message=(
            "Claim verification completed; unsupported claims must be handled by authoring constraints."
            if unsupported
            else "Claim verification completed with no unsupported claims."
        ),
        artifact_keys=["claim_verification"],
    )


def _check_evidence_sufficiency(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="evidence_sufficiency_gate",
            passed=True,
            blocking=False,
            message="No method text was produced; evidence sufficiency review is not required yet.",
            artifact_keys=["evidence_sufficiency_report", "evidence_sufficiency_decision_trace"],
        )
    report = _artifact_json(state, "evidence_sufficiency_report")
    trace = _artifact_json(state, "evidence_sufficiency_decision_trace")
    if not report or not trace:
        missing = []
        if not report:
            missing.append("evidence_sufficiency_report")
        if not trace:
            missing.append("evidence_sufficiency_decision_trace")
        return InvariantCheck(
            name="evidence_sufficiency_gate",
            passed=False,
            message="Method text exists but evidence sufficiency review artifacts are missing or unreadable: " + ", ".join(missing),
            artifact_keys=["evidence_sufficiency_report", "evidence_sufficiency_decision_trace", "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
        )
    safe_claims = _as_string_list(report.get("safe_claim_ids")) + _as_string_list(report.get("caveated_claim_ids"))
    problems: list[str] = []
    if not bool(report.get("hard_gate_passed", True)):
        problems.append("evidence sufficiency hard_gate_passed=false")
    if not safe_claims:
        problems.append("evidence sufficiency found no writable supported or caveated claims")
    final_decision = trace.get("final_decision") if isinstance(trace.get("final_decision"), dict) else {}
    if str(final_decision.get("recommended_next") or "") != "grounding":
        problems.append("method text exists but evidence sufficiency did not authorize grounding")
    return InvariantCheck(
        name="evidence_sufficiency_gate",
        passed=not problems,
        message="Evidence sufficiency review passed before Method authoring."
        if not problems
        else "; ".join(problems),
        artifact_keys=["evidence_sufficiency_report", "evidence_sufficiency_decision_trace", "claim_verification", "evidence", "claims"],
    )


def _check_authoring_constraints(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="authoring_constraints_gate",
            passed=True,
            blocking=False,
            message="No method text was produced; authoring constraints are not required yet.",
            artifact_keys=["authoring_constraints"],
        )
    constraints = _artifact_json(state, "authoring_constraints")
    if not constraints:
        return InvariantCheck(
            name="authoring_constraints_gate",
            passed=False,
            message="Method text exists but agentic_authoring_constraints.json is missing or unreadable.",
            artifact_keys=["authoring_constraints", "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
        )
    excluded = set(_as_list(constraints.get("excluded_claim_ids")))
    verification = _artifact_json(state, "claim_verification")
    unsupported = {
        str(claim.get("claim_id") or "")
        for claim in _as_list((verification or {}).get("claims"))
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    }
    missing_exclusions = sorted(claim_id for claim_id in unsupported if claim_id and claim_id not in excluded)
    return InvariantCheck(
        name="authoring_constraints_gate",
        passed=not missing_exclusions,
        message="Authoring constraints exclude unsupported claims."
        if not missing_exclusions
        else "Unsupported claims are not excluded from authoring constraints: " + ", ".join(missing_exclusions),
        artifact_keys=["authoring_constraints", "claim_verification"],
    )


def _check_authoring_context(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="authoring_context_gate",
            passed=True,
            blocking=False,
            message="No method text was produced; authoring context is not required yet.",
            artifact_keys=["authoring_context"],
        )
    context = _artifact_json(state, "authoring_context")
    if not context:
        return InvariantCheck(
            name="authoring_context_gate",
            passed=False,
            message="Method text exists but agentic_authoring_context.json is missing or unreadable.",
            artifact_keys=["authoring_context", "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
        )
    constraints = _artifact_json(state, "authoring_constraints")
    excluded_claim_ids = set(_as_string_list(constraints.get("excluded_claim_ids")))
    unsupported_claim_ids = _unsupported_claim_ids(state)
    known_evidence_ids = _known_evidence_ids(state)
    allowed_claims = _as_list(context.get("allowed_claims"))
    caveated_claims = _as_list(context.get("caveated_claims"))
    excluded_claims = _as_list(context.get("excluded_claims"))
    allowed_ids = _claim_ids_from_context(allowed_claims)
    caveated_ids = _claim_ids_from_context(caveated_claims)
    excluded_ids = _claim_ids_from_context(excluded_claims)
    safe_claim_ids = allowed_ids | caveated_ids
    forbidden_safe_claims = sorted(safe_claim_ids.intersection(excluded_claim_ids | unsupported_claim_ids))
    missing_exclusions = sorted((excluded_claim_ids | unsupported_claim_ids) - excluded_ids)
    unknown_evidence_ids: list[str] = []
    missing_evidence_claims: list[str] = []
    for claim in [*allowed_claims, *caveated_claims]:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        evidence_ids = _as_string_list(claim.get("evidence_ids"))
        if not evidence_ids:
            missing_evidence_claims.append(claim_id or "unknown_claim")
        unknown_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence_ids])
    problems = []
    if not bool(context.get("hard_gate_passed", True)):
        problems.append("authoring context hard_gate_passed=false")
    if forbidden_safe_claims:
        problems.append("excluded or unsupported claims marked writable: " + ", ".join(forbidden_safe_claims[:8]))
    if missing_exclusions:
        problems.append("excluded/unsupported claims missing from context exclusion list: " + ", ".join(missing_exclusions[:8]))
    if missing_evidence_claims:
        problems.append("writable claims missing evidence ids: " + ", ".join(_dedupe(missing_evidence_claims)[:8]))
    if unknown_evidence_ids:
        problems.append("authoring context unknown evidence ids: " + ", ".join(_dedupe(unknown_evidence_ids)[:8]))
    return InvariantCheck(
        name="authoring_context_gate",
        passed=not problems,
        message="Authoring context constrains method text to verified evidence-backed claims."
        if not problems
        else "; ".join(problems),
        artifact_keys=["authoring_context", "authoring_constraints", "claim_verification", "evidence", "claims"],
    )


def _check_authoring_plan(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="authoring_plan_gate",
            passed=True,
            blocking=False,
            message="No method text was produced; authoring plan is not required yet.",
            artifact_keys=["authoring_plan"],
        )
    plan = _artifact_json(state, "authoring_plan")
    if not plan:
        return InvariantCheck(
            name="authoring_plan_gate",
            passed=False,
            message="Method text exists but agentic_authoring_plan.json is missing or unreadable.",
            artifact_keys=[
                "authoring_plan",
                "authoring_plan_decision_trace",
                "text_md",
                "text_clean_md",
                "text_tex",
                "text_clean_tex",
            ],
        )
    trace = _artifact_json(state, "authoring_plan_decision_trace")
    if not trace:
        return InvariantCheck(
            name="authoring_plan_gate",
            passed=False,
            message="Method text exists but agentic_authoring_plan_decision_trace.json is missing or unreadable.",
            artifact_keys=["authoring_plan", "authoring_plan_decision_trace", "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
        )
    known_evidence_ids = _known_evidence_ids(state)
    known_claim_ids = _known_claim_ids(state)
    constraints = _artifact_json(state, "authoring_constraints")
    forbidden_claim_ids = set(_as_string_list(constraints.get("excluded_claim_ids"))) | _unsupported_claim_ids(state)
    problems: list[str] = []
    trace_problem = _decision_trace_plan_mismatch(
        trace=trace,
        plan=plan,
        expected_node="authoring_planner",
        signature_kind="authoring_plan",
    )
    if trace_problem:
        problems.append(trace_problem)
    if not bool(plan.get("hard_gate_passed", True)):
        problems.append("authoring plan hard_gate_passed=false")
    sections = _as_list(plan.get("sections"))
    if not sections:
        problems.append("authoring plan has no evidence-backed sections")
    unknown_evidence_ids: list[str] = []
    unknown_claim_ids: list[str] = []
    forbidden_used: list[str] = []
    missing_evidence_sections: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "unknown_section")
        evidence_ids = _as_string_list(section.get("evidence_ids"))
        claim_ids = _as_string_list(section.get("claim_ids"))
        if not evidence_ids:
            missing_evidence_sections.append(section_id)
        unknown_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence_ids])
        unknown_claim_ids.extend([claim_id for claim_id in claim_ids if claim_id not in known_claim_ids])
        forbidden_used.extend([claim_id for claim_id in claim_ids if claim_id in forbidden_claim_ids])
    if missing_evidence_sections:
        problems.append("planned sections missing evidence ids: " + ", ".join(_dedupe(missing_evidence_sections)[:8]))
    if unknown_evidence_ids:
        problems.append("authoring plan unknown evidence ids: " + ", ".join(_dedupe(unknown_evidence_ids)[:8]))
    if unknown_claim_ids:
        problems.append("authoring plan unknown claim ids: " + ", ".join(_dedupe(unknown_claim_ids)[:8]))
    if forbidden_used:
        problems.append("authoring plan uses excluded or unsupported claims: " + ", ".join(_dedupe(forbidden_used)[:8]))
    return InvariantCheck(
        name="authoring_plan_gate",
        passed=not problems,
        message="Authoring plan maps planned Method sections to verified claim and evidence ids."
        if not problems
        else "; ".join(problems),
        artifact_keys=[
            "authoring_plan",
            "authoring_plan_decision_trace",
            "authoring_context",
            "authoring_constraints",
            "claim_verification",
            "evidence",
            "claims",
        ],
    )


def _check_validation_after_text(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="validation_after_authoring",
            passed=True,
            blocking=False,
            message="No method text was produced; validation is not required yet.",
            artifact_keys=["validation_manifest"],
        )
    manifest = _artifact_json(state, "validation_manifest")
    passed = validation_passed(manifest) is True
    return InvariantCheck(
        name="validation_after_authoring",
        passed=passed,
        message="Validation manifest passed for produced method text."
        if passed
        else "Method text exists but the validation manifest is missing or failed.",
        artifact_keys=["validation_manifest", "fidelity"],
    )


def _check_final_text_evidence_gate(state: AgenticRunState) -> InvariantCheck:
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    required = ["authoring_projection", "final_text_claims", "text_evidence_validation", "final_text_trace"]
    if not has_text:
        return InvariantCheck(
            name="final_text_evidence_gate",
            passed=True,
            blocking=False,
            message="No method text was produced; the final text evidence gate is not required yet.",
            artifact_keys=required,
        )
    missing = [key for key in required if not _artifact_exists(state, key)]
    if missing:
        return InvariantCheck(
            name="final_text_evidence_gate",
            passed=False,
            message="Final method text is missing authoritative post-hoc trust artifacts: " + ", ".join(missing),
            artifact_keys=required,
        )
    projection = _artifact_json(state, "authoring_projection")
    claims = _artifact_json(state, "final_text_claims")
    validation = _artifact_json(state, "text_evidence_validation")
    trace = _artifact_json(state, "final_text_trace")
    text_path = _artifact_path(state, "final_text_candidate") or _artifact_path(state, "text_clean_md") or _artifact_path(state, "text_md")
    current_digest = text_digest(text_path.read_text(encoding="utf-8")) if text_path and text_path.exists() else ""
    problems: list[str] = []
    if str(validation.get("status") or "") != "passed":
        problems.append("text evidence validation status is not passed")
    if not bool(trace.get("hard_gate_passed")):
        problems.append("final text trace hard gate did not pass")
    bound_digests = {
        str(claims.get("input_text_digest") or ""),
        str(validation.get("input_text_digest") or ""),
        str(trace.get("input_text_digest") or ""),
    }
    if not current_digest or bound_digests != {current_digest}:
        problems.append("final text digest does not match extractor, validator, and trace")
    projection_digest = str(projection.get("projection_digest") or "")
    if not projection_digest or {
        str(validation.get("projection_digest") or ""),
        str(trace.get("projection_digest") or ""),
    } != {projection_digest}:
        problems.append("projection digest mismatch")
    factual_count = len(claims.get("atomic_claims") or [])
    verdicts = validation.get("verdicts") if isinstance(validation.get("verdicts"), list) else []
    entries = trace.get("entries") if isinstance(trace.get("entries"), list) else []
    if len(verdicts) != factual_count or len(entries) != factual_count:
        problems.append("not every factual atomic claim has a verdict and authoritative trace entry")
    return InvariantCheck(
        name="final_text_evidence_gate",
        passed=not problems,
        message="Exact final text is bound to passed atomic-claim verdicts and direct-evidence trace."
        if not problems
        else "; ".join(problems),
        artifact_keys=[*required, "final_text_candidate"],
    )


def _check_traceability_ledger(state: AgenticRunState) -> InvariantCheck:
    ledger = _artifact_json(state, "traceability_ledger")
    if not ledger:
        ledger_obj = build_traceability_ledger(state)
        return InvariantCheck(
            name="traceability_ledger",
            passed=ledger_obj.hard_gate_passed,
            blocking=not ledger_obj.hard_gate_passed,
            message="Traceability ledger can be constructed from current artifacts."
            if ledger_obj.hard_gate_passed
            else "Constructed traceability ledger found invalid entries: " + ", ".join(ledger_obj.recommended_actions),
            artifact_keys=["traceability_ledger", "evidence", "claims", "text_claims", "figure_plan"],
        )
    missing = int(ledger.get("entries_with_missing_evidence") or 0)
    unknown_claims = int(ledger.get("entries_with_unknown_claims") or 0)
    forbidden_claims = int(ledger.get("entries_with_forbidden_claims") or 0)
    hard_gate_passed = bool(ledger.get("hard_gate_passed"))
    passed = hard_gate_passed and missing == 0 and unknown_claims == 0 and forbidden_claims == 0
    problems = []
    if missing:
        problems.append(f"{missing} entries have missing/unknown evidence")
    if unknown_claims:
        problems.append(f"{unknown_claims} entries have unknown claims")
    if forbidden_claims:
        problems.append(f"{forbidden_claims} entries use excluded or unsupported claims")
    return InvariantCheck(
        name="traceability_ledger",
        passed=passed,
        message="Traceability ledger maps text, claims, and figures to frozen code evidence."
        if passed
        else "; ".join(problems) or "Traceability ledger hard_gate_passed=false.",
        artifact_keys=["traceability_ledger"],
    )


def _check_text_claim_traceability(state: AgenticRunState) -> InvariantCheck:
    if _artifact_exists(state, "final_text_trace"):
        return InvariantCheck(
            name="text_claim_traceability",
            passed=True,
            blocking=False,
            message="Legacy paragraph scaffold is non-authoritative; final_text_evidence_gate owns text trust.",
            artifact_keys=["final_text_trace", "text_claims"],
        )
    has_text = any(_artifact_exists(state, key) for key in ("text_md", "text_clean_md", "text_tex", "text_clean_tex"))
    if not has_text:
        return InvariantCheck(
            name="text_claim_traceability",
            passed=True,
            blocking=False,
            message="No method text was produced; text claim traceability is not required yet.",
            artifact_keys=["text_claims"],
        )
    draft_claim_map = _artifact_json(state, "text_claims")
    if not draft_claim_map:
        return InvariantCheck(
            name="text_claim_traceability",
            passed=False,
            message="Method text exists but text_claims.json is missing or unreadable.",
            artifact_keys=["text_claims", "text_md", "text_clean_md", "text_tex", "text_clean_tex"],
        )
    paragraphs = _as_list(draft_claim_map.get("paragraphs"))
    if not paragraphs:
        return InvariantCheck(
            name="text_claim_traceability",
            passed=False,
            message="text_claims.json has no paragraph trace records.",
            artifact_keys=["text_claims"],
        )
    known_claim_ids = _known_claim_ids(state)
    known_evidence_ids = _known_evidence_ids(state)
    excluded_claim_ids = set(_as_list(_artifact_json(state, "authoring_constraints").get("excluded_claim_ids")))
    unsupported_claim_ids = _unsupported_claim_ids(state)
    missing_evidence_paragraphs: list[str] = []
    unknown_evidence_ids: list[str] = []
    unknown_claim_ids: list[str] = []
    forbidden_claim_ids: list[str] = []
    unplanned_claim_ids: list[str] = []
    unplanned_evidence_ids: list[str] = []
    planned_claim_ids, planned_evidence_ids = _planned_authoring_claims_and_evidence(state)
    for index, paragraph in enumerate(paragraphs, start=1):
        if not isinstance(paragraph, dict):
            missing_evidence_paragraphs.append(f"paragraph:{index}")
            continue
        paragraph_id = str(paragraph.get("paragraph_id") or f"paragraph:{index}")
        evidence_ids = _as_string_list(paragraph.get("evidence_span_ids"))
        claim_ids = _as_string_list(paragraph.get("claim_ids"))
        if not evidence_ids:
            missing_evidence_paragraphs.append(paragraph_id)
        unknown_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence_ids])
        unknown_claim_ids.extend([claim_id for claim_id in claim_ids if claim_id not in known_claim_ids])
        forbidden_claim_ids.extend(
            [claim_id for claim_id in claim_ids if claim_id in excluded_claim_ids or claim_id in unsupported_claim_ids]
        )
        if planned_claim_ids:
            unplanned_claim_ids.extend([claim_id for claim_id in claim_ids if claim_id not in planned_claim_ids])
        if planned_evidence_ids:
            unplanned_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in planned_evidence_ids])
    problems = []
    if missing_evidence_paragraphs:
        problems.append("paragraphs missing evidence ids: " + ", ".join(missing_evidence_paragraphs[:8]))
    if unknown_evidence_ids:
        problems.append("unknown evidence ids: " + ", ".join(_dedupe(unknown_evidence_ids)[:8]))
    if unknown_claim_ids:
        problems.append("unknown claim ids: " + ", ".join(_dedupe(unknown_claim_ids)[:8]))
    if forbidden_claim_ids:
        problems.append("excluded or unsupported claim ids used in text: " + ", ".join(_dedupe(forbidden_claim_ids)[:8]))
    if unplanned_claim_ids:
        problems.append("text claim ids outside authoring plan: " + ", ".join(_dedupe(unplanned_claim_ids)[:8]))
    if unplanned_evidence_ids:
        problems.append("text evidence ids outside authoring plan: " + ", ".join(_dedupe(unplanned_evidence_ids)[:8]))
    return InvariantCheck(
        name="text_claim_traceability",
        passed=not problems,
        message="Every authored paragraph has frozen evidence-backed trace records."
        if not problems
        else "; ".join(problems),
        artifact_keys=["text_claims", "authoring_plan", "claims", "evidence", "authoring_constraints", "claim_verification"],
    )


def _check_figure_plan(state: AgenticRunState) -> InvariantCheck:
    has_figure_output = any(
        _artifact_exists(state, key)
        for key in ("method_overview_meta", "method_overview_png", "method_overview_svg", "method_overview_pdf")
    )
    plan = _artifact_json(state, "figure_plan")
    if not has_figure_output and not plan:
        return InvariantCheck(
            name="figure_evidence_plan",
            passed=True,
            blocking=False,
            message="No method figure output was produced; figure evidence plan is not required yet.",
            artifact_keys=["figure_plan"],
        )
    if not plan:
        return InvariantCheck(
            name="figure_evidence_plan",
            passed=False,
            message="Method figure output exists but figure_plan is missing or unreadable.",
            artifact_keys=["figure_plan"],
        )
    trace = _artifact_json(state, "figure_plan_decision_trace")
    if not trace:
        return InvariantCheck(
            name="figure_evidence_plan",
            passed=False,
            message="Method figure plan exists but figure_plan_decision_trace is missing or unreadable.",
            artifact_keys=["figure_plan", "figure_plan_decision_trace"],
        )
    nodes = _as_list(plan.get("nodes"))
    edges = _as_list(plan.get("edges"))
    nodes_have_evidence = bool(nodes) and all(
        isinstance(node, dict) and bool(_as_list(node.get("evidence_ids"))) for node in nodes
    )
    edges_have_evidence = all(
        isinstance(edge, dict) and bool(_as_list(edge.get("evidence_ids"))) for edge in edges
    )
    hard_gate_passed = bool(plan.get("hard_gate_passed"))
    known_evidence_ids = _known_evidence_ids(state)
    known_claim_ids = _known_claim_ids(state)
    excluded_claim_ids = set(_as_list(_artifact_json(state, "authoring_constraints").get("excluded_claim_ids")))
    unsupported_claim_ids = _unsupported_claim_ids(state)
    unknown_evidence_ids: list[str] = []
    unknown_claim_ids: list[str] = []
    forbidden_claim_ids: list[str] = []
    for item in [*nodes, *edges]:
        if not isinstance(item, dict):
            continue
        evidence_ids = _as_string_list(item.get("evidence_ids"))
        claim_ids = _as_string_list(item.get("claim_ids"))
        unknown_evidence_ids.extend([evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence_ids])
        unknown_claim_ids.extend([claim_id for claim_id in claim_ids if claim_id not in known_claim_ids])
        forbidden_claim_ids.extend(
            [claim_id for claim_id in claim_ids if claim_id in excluded_claim_ids or claim_id in unsupported_claim_ids]
        )
    problems = []
    trace_problem = _decision_trace_plan_mismatch(
        trace=trace,
        plan=plan,
        expected_node="figure_planner",
        signature_kind="figure_plan",
    )
    if trace_problem:
        problems.append(trace_problem)
    if not nodes_have_evidence or not edges_have_evidence or not hard_gate_passed:
        problems.append("missing node/edge evidence or hard_gate_passed=false")
    if unknown_evidence_ids:
        problems.append("unknown figure evidence ids: " + ", ".join(_dedupe(unknown_evidence_ids)[:8]))
    if unknown_claim_ids:
        problems.append("unknown figure claim ids: " + ", ".join(_dedupe(unknown_claim_ids)[:8]))
    if forbidden_claim_ids:
        problems.append("excluded or unsupported claim ids used in figure: " + ", ".join(_dedupe(forbidden_claim_ids)[:8]))
    return InvariantCheck(
        name="figure_evidence_plan",
        passed=not problems,
        message="Figure plan nodes and edges are evidence-backed."
        if not problems
        else "; ".join(problems),
        artifact_keys=[
            "figure_plan",
            "figure_plan_decision_trace",
            "claims",
            "evidence",
            "authoring_constraints",
            "claim_verification",
        ],
    )


def _check_final_package_traceability(state: AgenticRunState) -> InvariantCheck:
    has_final_package = any(
        _artifact_exists(state, key)
        for key in ("final_tex", "final_pdf", "final_pdf_report", "finalize_manifest")
    )
    if not has_final_package:
        return InvariantCheck(
            name="final_package_traceability",
            passed=True,
            blocking=False,
            message="No final Method package was produced; final package traceability is not required yet.",
            artifact_keys=["final_tex", "finalize_manifest"],
        )
    if not _artifact_exists(state, "finalize_manifest"):
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Final package artifacts exist but finalize_manifest is missing.",
            artifact_keys=["final_tex", "final_pdf", "finalize_manifest"],
        )
    if not _artifact_exists(state, "final_tex"):
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Final package manifest exists but final_tex is missing.",
            artifact_keys=["final_tex", "finalize_manifest"],
        )
    manifest = _artifact_json(state, "finalize_manifest")
    inputs = manifest.get("inputs")
    source_path = str(inputs.get("text_tex") if isinstance(inputs, dict) else "").strip()
    if not source_path:
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Finalize manifest does not record the source Method TeX input.",
            artifact_keys=["finalize_manifest"],
        )
    registered_source_key = _registered_tex_source_key(state, source_path)
    if not registered_source_key:
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Finalize source TeX is not a registered audited authoring artifact.",
            artifact_keys=["finalize_manifest", "text_tex", "text_clean_tex"],
        )
    source_text = _read_artifact_text_path(source_path).strip()
    final_text = _read_artifact_text(state, "final_tex")
    if not source_text:
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Finalize source TeX is empty or unreadable.",
            artifact_keys=[registered_source_key, "finalize_manifest"],
        )
    if source_text not in final_text:
        return InvariantCheck(
            name="final_package_traceability",
            passed=False,
            message="Final TeX does not contain the audited source Method TeX body.",
            artifact_keys=["final_tex", registered_source_key, "finalize_manifest"],
        )
    return InvariantCheck(
        name="final_package_traceability",
        passed=True,
        message=f"Final TeX preserves audited source Method TeX from {registered_source_key}.",
        artifact_keys=["final_tex", registered_source_key, "finalize_manifest"],
    )


def _decision_trace_plan_mismatch(
    *,
    trace: dict[str, Any],
    plan: dict[str, Any],
    expected_node: str,
    signature_kind: str,
) -> str:
    if str(trace.get("node") or "") != expected_node:
        return f"{signature_kind} decision trace node is not {expected_node}"
    final_decision = trace.get("final_decision") if isinstance(trace.get("final_decision"), dict) else {}
    if not final_decision:
        return f"{signature_kind} decision trace final_decision is missing"
    if _plan_signature(final_decision, signature_kind) != _plan_signature(plan, signature_kind):
        return f"{signature_kind} decision trace final_decision does not match the current plan artifact"
    return ""


def _planned_authoring_claims_and_evidence(state: AgenticRunState) -> tuple[set[str], set[str]]:
    plan = _artifact_json(state, "authoring_plan")
    claim_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for section in _as_list(plan.get("sections")):
        if not isinstance(section, dict):
            continue
        claim_ids.update(_as_string_list(section.get("claim_ids")))
        evidence_ids.update(_as_string_list(section.get("evidence_ids")))
    return claim_ids, evidence_ids


def _plan_signature(plan: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "authoring_plan":
        return {
            "hard_gate_passed": bool(plan.get("hard_gate_passed")),
            "sections": [
                {
                    "section_id": str(section.get("section_id") or ""),
                    "claim_ids": _as_string_list(section.get("claim_ids")),
                    "evidence_ids": _as_string_list(section.get("evidence_ids")),
                    "caveat_required": bool(section.get("caveat_required")),
                }
                for section in _as_list(plan.get("sections"))
                if isinstance(section, dict)
            ],
        }
    if kind == "figure_plan":
        return {
            "hard_gate_passed": bool(plan.get("hard_gate_passed")),
            "nodes": [
                {
                    "node_id": str(node.get("node_id") or ""),
                    "stage_id": str(node.get("stage_id") or ""),
                    "claim_ids": _as_string_list(node.get("claim_ids")),
                    "evidence_ids": _as_string_list(node.get("evidence_ids")),
                }
                for node in _as_list(plan.get("nodes"))
                if isinstance(node, dict)
            ],
            "edges": [
                {
                    "edge_id": str(edge.get("edge_id") or ""),
                    "source_node_id": str(edge.get("source_node_id") or ""),
                    "target_node_id": str(edge.get("target_node_id") or ""),
                    "evidence_ids": _as_string_list(edge.get("evidence_ids")),
                }
                for edge in _as_list(plan.get("edges"))
                if isinstance(edge, dict)
            ],
        }
    return {}


def _recommended_actions(checks: list[InvariantCheck]) -> list[str]:
    actions = []
    for check in checks:
        if check.passed:
            continue
        if check.name == "frozen_evidence_gate":
            actions.append("rerun_evidence_freeze_before_authoring")
        elif check.name == "claim_verification_audit":
            actions.append("return_to_analysis_for_claim_evidence_repair")
        elif check.name == "evidence_sufficiency_gate":
            actions.append("run_evidence_sufficiency_review_before_authoring")
        elif check.name == "authoring_constraints_gate":
            actions.append("rebuild_authoring_constraints_from_claim_verification")
        elif check.name == "authoring_context_gate":
            actions.append("rebuild_authoring_context_from_verified_claim_constraints")
        elif check.name == "authoring_plan_gate":
            actions.append("rebuild_authoring_plan_from_evidence_bound_authoring_context")
        elif check.name == "final_text_evidence_gate":
            actions.append("rebuild_final_text_claims_validation_and_posthoc_trace")
        elif check.name == "text_claim_traceability":
            actions.append("rebuild_text_claims_from_frozen_evidence_before_validation")
        elif check.name == "traceability_ledger":
            actions.append("rebuild_traceability_ledger_from_frozen_evidence")
        elif check.name == "validation_after_authoring":
            actions.append("run_validation_before_rendering_or_finalize")
        elif check.name == "final_package_traceability":
            actions.append("rebuild_final_package_from_validated_authoring_tex")
        elif check.name == "figure_evidence_plan":
            actions.append("rebuild_figure_plan_from_verified_method_evidence")
    return actions or ["all_agentic_evidence_invariants_satisfied"]


def _artifact_exists(state: AgenticRunState, key: str) -> bool:
    path = state.artifacts.get(key, "")
    return bool(path and Path(path).exists())


def _artifact_path(state: AgenticRunState, key: str) -> Path | None:
    path = state.artifacts.get(key, "")
    candidate = Path(path) if path else None
    return candidate if candidate is not None and candidate.exists() else None


def _artifact_json(state: AgenticRunState, key: str) -> dict[str, Any]:
    path = state.artifacts.get(key, "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_artifact_text(state: AgenticRunState, key: str) -> str:
    path = state.artifacts.get(key, "")
    return _read_artifact_text_path(path)


def _read_artifact_text_path(path: str | Path) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _registered_tex_source_key(state: AgenticRunState, source_path: str) -> str:
    source = _resolve_existing_path(source_path)
    if source is None:
        return ""
    for key in ("text_clean_tex", "text_tex"):
        registered = _resolve_existing_path(state.artifacts.get(key, ""))
        if registered is not None and registered == source:
            return key
    return ""


def _resolve_existing_path(path: str | Path) -> Path | None:
    if not path:
        return None
    try:
        candidate = Path(path)
        if not candidate.exists():
            return None
        return candidate.resolve()
    except OSError:
        return None


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _known_claim_ids(state: AgenticRunState) -> set[str]:
    claims = _as_list(_artifact_json(state, "claims").get("claims"))
    ids = {str(claim.get("claim_id") or "") for claim in claims if isinstance(claim, dict)}
    verification_claims = _as_list(_artifact_json(state, "claim_verification").get("claims"))
    ids.update(str(claim.get("claim_id") or "") for claim in verification_claims if isinstance(claim, dict))
    return {claim_id for claim_id in ids if claim_id}


def _unsupported_claim_ids(state: AgenticRunState) -> set[str]:
    verification_claims = _as_list(_artifact_json(state, "claim_verification").get("claims"))
    unsupported = {
        str(claim.get("claim_id") or "")
        for claim in verification_claims
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    }
    claim_map_claims = _as_list(_artifact_json(state, "claims").get("claims"))
    unsupported.update(
        str(claim.get("claim_id") or "")
        for claim in claim_map_claims
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    )
    return {claim_id for claim_id in unsupported if claim_id}


def _claim_ids_from_context(claims: list[Any]) -> set[str]:
    return {
        str(claim.get("claim_id") or "")
        for claim in claims
        if isinstance(claim, dict) and str(claim.get("claim_id") or "").strip()
    }


def _known_evidence_ids(state: AgenticRunState) -> set[str]:
    evidence_payload = _artifact_json(state, "evidence")
    claim_payload = _artifact_json(state, "claims")
    ids = _collect_evidence_ids(evidence_payload)
    ids.update(_collect_evidence_ids(claim_payload))
    return ids


def _collect_evidence_ids(value: object) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids", "primary_evidence_ids"}:
                ids.update(_as_string_list(item))
            else:
                ids.update(_collect_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_collect_evidence_ids(item))
    return ids


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
