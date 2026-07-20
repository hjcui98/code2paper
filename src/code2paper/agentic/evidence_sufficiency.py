from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _call_provider_for_trace,
)
from code2paper.agentic.decision_models import EvidenceSufficiencyProposal
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.evidence_sufficiency_attention import evidence_sufficiency_attention
from code2paper.core.schemas import MethodEvidence, SupportStatus
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, EvidencePacketSetV3


class EvidenceSufficiencyReport(BaseModel):
    """Post-freeze review of whether verified evidence is sufficient for writing."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "evidence-sufficiency-report"
    checked_claims: int = 0
    supported_claims: int = 0
    partial_claims: int = 0
    unsupported_claims: int = 0
    claims_with_missing_evidence: int = 0
    support_rate: float = 0.0
    safe_claim_ids: list[str] = Field(default_factory=list)
    caveated_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    missing_evidence_claim_ids: list[str] = Field(default_factory=list)
    frozen_evidence_ids: list[str] = Field(default_factory=list)
    evidence_backed_mechanisms: int = 0
    mechanisms_without_evidence: int = 0
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)


class EvidenceSufficiencyDecision(BaseModel):
    """Safe routing decision after claim verification and evidence sufficiency review."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    rationale: str
    recommended_next: str = ""
    support_rate: float = 0.0
    supported_claims: int = 0
    partial_claims: int = 0
    unsupported_claims: int = 0
    claims_with_missing_evidence: int = 0
    focus_claim_ids: list[str] = Field(default_factory=list)
    artifact_keys: list[str] = Field(default_factory=list)


def build_evidence_sufficiency_report(
    method_evidence: MethodEvidence,
    claim_verification: ClaimVerificationReport,
) -> EvidenceSufficiencyReport:
    """Summarize claim and evidence coverage after MethodEvidence is frozen."""

    checked = claim_verification.checked_claims
    safe_claim_ids = [
        claim.claim_id
        for claim in claim_verification.claims
        if claim.support_status == SupportStatus.SUPPORTED and claim.recommended_action == "allow_in_prose"
    ]
    caveated_claim_ids = [
        claim.claim_id
        for claim in claim_verification.claims
        if claim.support_status == SupportStatus.PARTIAL
    ]
    unsupported_claim_ids = [
        claim.claim_id
        for claim in claim_verification.claims
        if claim.support_status == SupportStatus.UNSUPPORTED
    ]
    missing_evidence_claim_ids = [
        claim.claim_id
        for claim in claim_verification.claims
        if claim.missing_evidence_ids or claim.recommended_action == "drop_or_retrieve_more_evidence"
    ]
    mechanism_counts = _mechanism_evidence_counts(method_evidence)
    support_rate = round((claim_verification.supported_claims + 0.5 * claim_verification.partial_claims) / checked, 4) if checked else 0.0
    hard_gate_passed = bool(safe_claim_ids or caveated_claim_ids) and bool(_frozen_evidence_ids(method_evidence))
    return EvidenceSufficiencyReport(
        checked_claims=checked,
        supported_claims=claim_verification.supported_claims,
        partial_claims=claim_verification.partial_claims,
        unsupported_claims=claim_verification.unsupported_claims,
        claims_with_missing_evidence=claim_verification.claims_with_missing_evidence,
        support_rate=support_rate,
        safe_claim_ids=safe_claim_ids,
        caveated_claim_ids=caveated_claim_ids,
        unsupported_claim_ids=unsupported_claim_ids,
        missing_evidence_claim_ids=_dedupe(missing_evidence_claim_ids),
        frozen_evidence_ids=_frozen_evidence_ids(method_evidence),
        evidence_backed_mechanisms=mechanism_counts["with_evidence"],
        mechanisms_without_evidence=mechanism_counts["without_evidence"],
        hard_gate_passed=hard_gate_passed,
        recommended_actions=_recommended_actions(
            safe_claims=len(safe_claim_ids),
            caveated_claims=len(caveated_claim_ids),
            unsupported_claims=claim_verification.unsupported_claims,
            missing_evidence=claim_verification.claims_with_missing_evidence,
            mechanisms_without_evidence=mechanism_counts["without_evidence"],
        ),
    )


def build_v3_evidence_sufficiency_report(
    claims: AtomicClaimSetV3,
    packets: EvidencePacketSetV3,
) -> EvidenceSufficiencyReport:
    """Describe validated compiler output without reopening legacy wide claims."""

    safe = [item.claim_id for item in claims.claims if item.status == "supported"]
    caveated = [item.claim_id for item in claims.claims if item.status == "partial"]
    frozen_ids = _dedupe([
        span.span_id
        for packet in packets.packets
        for span in packet.spans
    ])
    return EvidenceSufficiencyReport(
        mode="evidence-sufficiency-report-v3",
        checked_claims=len(claims.claims),
        supported_claims=len(safe),
        partial_claims=len(caveated),
        unsupported_claims=0,
        claims_with_missing_evidence=0,
        support_rate=1.0 if claims.claims else 0.0,
        safe_claim_ids=safe,
        caveated_claim_ids=caveated,
        unsupported_claim_ids=[],
        missing_evidence_claim_ids=[],
        frozen_evidence_ids=frozen_ids,
        evidence_backed_mechanisms=len(claims.claims),
        mechanisms_without_evidence=0,
        hard_gate_passed=bool(safe or caveated) and bool(frozen_ids),
        recommended_actions=[
            "proceed_from_validated_v3_facts_to_evidence_constrained_authoring",
            "preserve_explicit_code_gaps_outside_positive_prose",
        ],
    )


def evidence_sufficiency_trace(
    report: EvidenceSufficiencyReport,
    *,
    author_intent_summary: AuthorIntentSummary | None = None,
    evidence_revision_round: int = 0,
    max_evidence_revision_rounds: int = 0,
    decision_provider: DecisionProvider | None = None,
) -> tuple[EvidenceSufficiencyDecision, AgenticDecisionTrace]:
    """Return a safe sufficiency decision plus an auditable model/fallback trace."""

    fallback = critique_evidence_sufficiency(
        report,
        evidence_revision_round=evidence_revision_round,
        max_evidence_revision_rounds=max_evidence_revision_rounds,
    )
    prompt = AgenticDecisionPrompt(
        node="evidence_sufficiency",
        objective=(
            "Decide whether frozen MethodEvidence and claim verification are sufficient for grounding/authoring, "
            "or whether the graph should return to analysis for more evidence."
        ),
        hard_rules=_evidence_sufficiency_rules(),
        inputs={
            "evidence_sufficiency_report": report.model_dump(mode="json"),
            "author_intent_summary": author_intent_summary.model_dump(mode="json") if author_intent_summary else None,
            "evidence_sufficiency_attention": evidence_sufficiency_attention(
                report,
                evidence_revision_round=evidence_revision_round,
                max_evidence_revision_rounds=max_evidence_revision_rounds,
            ),
            "evidence_revision_round": evidence_revision_round,
            "max_evidence_revision_rounds": max_evidence_revision_rounds,
            "stage_tool_guidance": stage_tool_guidance_for_decision(["analysis", "evidence", "grounding", "authoring"]),
        },
        fallback_decision=fallback.model_dump(mode="json"),
    )
    if decision_provider is None:
        return fallback, _trace(
            prompt=prompt,
            provider_status="deterministic_fallback",
            final_decision=fallback,
            safety_notes=["No decision provider was configured; deterministic evidence sufficiency critic was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(
        decision_provider,
        prompt,
        EvidenceSufficiencyProposal,
    )
    if not isinstance(proposal, EvidenceSufficiencyProposal):
        return fallback, _trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_decision=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic evidence sufficiency critic was used."],
        )
    final = _merge_evidence_sufficiency_decision(
        report=report,
        fallback=fallback,
        proposal=proposal,
        evidence_revision_round=evidence_revision_round,
        max_evidence_revision_rounds=max_evidence_revision_rounds,
    )
    return final, _trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_decision=final,
        safety_notes=_safety_notes(fallback=fallback, proposal=proposal, final=final),
    )


def critique_evidence_sufficiency(
    report: EvidenceSufficiencyReport,
    *,
    evidence_revision_round: int = 0,
    max_evidence_revision_rounds: int = 0,
) -> EvidenceSufficiencyDecision:
    """Deterministically decide the safe next node from evidence sufficiency."""

    budget_remaining = evidence_revision_round < max_evidence_revision_rounds
    focus_claim_ids = _dedupe([*report.missing_evidence_claim_ids, *report.unsupported_claim_ids])
    if not report.hard_gate_passed:
        return EvidenceSufficiencyDecision(
            decision="return_to_analysis" if budget_remaining else "block_evidence_insufficient",
            recommended_next="analysis" if budget_remaining else "blocked",
            rationale=(
                "No evidence-backed writable claims are available; analysis must retrieve more evidence before writing."
                if budget_remaining
                else "No evidence-backed writable claims are available and no evidence revision budget remains."
            ),
            focus_claim_ids=focus_claim_ids,
            **_report_counts(report),
        )
    if report.claims_with_missing_evidence or report.unsupported_claims:
        if budget_remaining:
            return EvidenceSufficiencyDecision(
                decision="return_to_analysis",
                recommended_next="analysis",
                rationale="Some frozen claims are unsupported or reference missing evidence; revision budget remains.",
                focus_claim_ids=focus_claim_ids,
                **_report_counts(report),
            )
        return EvidenceSufficiencyDecision(
            decision="proceed_with_exclusions",
            recommended_next="grounding",
            rationale=(
                "Unsupported or missing-evidence claims remain, but safe/caveated claims exist. "
                "Authoring constraints must exclude unsafe claims."
            ),
            focus_claim_ids=focus_claim_ids,
            **_report_counts(report),
        )
    if report.partial_claims:
        return EvidenceSufficiencyDecision(
            decision="proceed_with_caveats",
            recommended_next="grounding",
            rationale="Evidence is sufficient only with caveats for partial claims.",
            focus_claim_ids=report.caveated_claim_ids,
            **_report_counts(report),
        )
    return EvidenceSufficiencyDecision(
        decision="proceed_to_grounding",
        recommended_next="grounding",
        rationale="Frozen evidence and claim verification are sufficient for evidence-constrained writing.",
        focus_claim_ids=[],
        **_report_counts(report),
    )


def write_evidence_sufficiency_report(path: str | Path, report: EvidenceSufficiencyReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_evidence_sufficiency_report(path: str | Path) -> EvidenceSufficiencyReport | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        return EvidenceSufficiencyReport.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _merge_evidence_sufficiency_decision(
    *,
    report: EvidenceSufficiencyReport,
    fallback: EvidenceSufficiencyDecision,
    proposal: EvidenceSufficiencyProposal,
    evidence_revision_round: int,
    max_evidence_revision_rounds: int,
) -> EvidenceSufficiencyDecision:
    next_node = proposal.recommended_next.strip() or fallback.recommended_next
    decision = proposal.decision.strip() or fallback.decision
    rationale = proposal.rationale.strip() or fallback.rationale
    if next_node not in {"grounding", "analysis", "blocked"}:
        return fallback.model_copy(
            update={"rationale": f"{rationale} Unsafe evidence sufficiency route rejected; using deterministic route."}
        )
    budget_remaining = evidence_revision_round < max_evidence_revision_rounds
    if next_node == "analysis" and not budget_remaining:
        next_node = fallback.recommended_next
        decision = fallback.decision
        rationale = f"{rationale} Evidence analysis revision budget is exhausted."
    if next_node == "grounding" and not report.hard_gate_passed:
        next_node = "analysis" if budget_remaining else "blocked"
        decision = "return_to_analysis" if budget_remaining else "block_evidence_insufficient"
        rationale = f"{rationale} Grounding cannot proceed without evidence-backed writable claims."
    allowed_focus = set(report.safe_claim_ids) | set(report.caveated_claim_ids) | set(report.unsupported_claim_ids) | set(report.missing_evidence_claim_ids)
    focus_claim_ids = [claim_id for claim_id in _dedupe(proposal.focus_claim_ids) if claim_id in allowed_focus] or fallback.focus_claim_ids
    return EvidenceSufficiencyDecision(
        decision=decision,
        rationale=rationale,
        recommended_next=next_node,
        focus_claim_ids=focus_claim_ids,
        **_report_counts(report),
    )


def _trace(
    *,
    prompt: AgenticDecisionPrompt,
    provider_status: str,
    final_decision: EvidenceSufficiencyDecision,
    provider_payload: dict[str, Any] | None = None,
    parsed_proposal: EvidenceSufficiencyProposal | None = None,
    safety_notes: list[str] | None = None,
) -> AgenticDecisionTrace:
    return AgenticDecisionTrace(
        node="evidence_sufficiency",
        provider_status=provider_status,
        prompt=prompt,
        provider_payload=provider_payload or {},
        parsed_proposal=parsed_proposal.model_dump(mode="json") if parsed_proposal else {},
        final_decision=final_decision.model_dump(mode="json"),
        safety_notes=safety_notes or [],
    )


def _safety_notes(
    *,
    fallback: EvidenceSufficiencyDecision,
    proposal: EvidenceSufficiencyProposal,
    final: EvidenceSufficiencyDecision,
) -> list[str]:
    notes = ["Model proposal was merged through evidence-sufficiency safety rules."]
    if proposal.recommended_next and proposal.recommended_next != final.recommended_next:
        notes.append(f"Proposed next node '{proposal.recommended_next}' was rewritten to '{final.recommended_next}'.")
    if proposal.decision and proposal.decision != final.decision:
        notes.append(f"Proposed decision '{proposal.decision}' was rewritten to '{final.decision}'.")
    if final.recommended_next == fallback.recommended_next and proposal.recommended_next != fallback.recommended_next:
        notes.append("Deterministic fallback route remained authoritative.")
    return notes


def _evidence_sufficiency_rules() -> list[str]:
    return [
        *hard_rule_texts(),
        "Evidence sufficiency decisions may choose only grounding, analysis, or blocked.",
        "Grounding cannot proceed unless at least one allowed or caveated claim has frozen evidence.",
        "Analysis revisions are bounded by max_evidence_revision_rounds.",
    ]


def _recommended_actions(
    *,
    safe_claims: int,
    caveated_claims: int,
    unsupported_claims: int,
    missing_evidence: int,
    mechanisms_without_evidence: int,
) -> list[str]:
    actions: list[str] = []
    if not safe_claims and not caveated_claims:
        actions.append("return_to_analysis_for_evidence_backed_claims")
    if missing_evidence:
        actions.append("retrieve_or_rebuild_claims_with_missing_evidence_ids")
    if unsupported_claims:
        actions.append("exclude_unsupported_claims_or_return_to_analysis")
    if caveated_claims:
        actions.append("carry_partial_claims_forward_only_with_caveats")
    if mechanisms_without_evidence:
        actions.append("review_mechanisms_without_frozen_evidence")
    if not actions:
        actions.append("evidence_sufficient_for_grounding_and_authoring")
    return actions


def _report_counts(report: EvidenceSufficiencyReport) -> dict[str, Any]:
    return {
        "support_rate": report.support_rate,
        "supported_claims": report.supported_claims,
        "partial_claims": report.partial_claims,
        "unsupported_claims": report.unsupported_claims,
        "claims_with_missing_evidence": report.claims_with_missing_evidence,
        "artifact_keys": ["evidence_sufficiency_report", "claim_verification", "evidence", "claims"],
    }


def _frozen_evidence_ids(method_evidence: MethodEvidence) -> list[str]:
    found: list[str] = []
    _collect_evidence_ids(method_evidence.model_dump(mode="json"), found)
    return _dedupe(found)


def _collect_evidence_ids(value: object, found: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "span_id"} and isinstance(item, str):
                found.append(item)
            elif key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids"} and isinstance(item, list):
                found.extend(str(element) for element in item if str(element).strip())
            else:
                _collect_evidence_ids(item, found)
        return
    if isinstance(value, list):
        for item in value:
            _collect_evidence_ids(item, found)


def _mechanism_evidence_counts(method_evidence: MethodEvidence) -> dict[str, int]:
    payload = method_evidence.model_dump(mode="json")
    mechanisms = _mechanism_like_items(payload)
    with_evidence = sum(1 for item in mechanisms if item.get("evidence_ids"))
    return {"with_evidence": with_evidence, "without_evidence": max(0, len(mechanisms) - with_evidence)}


def _mechanism_like_items(value: object) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        found: list[dict[str, Any]] = []
        if "mechanism_id" in value:
            found.append(value)
        for item in value.values():
            found.extend(_mechanism_like_items(item))
        return found
    if isinstance(value, list):
        found: list[dict[str, Any]] = []
        for item in value:
            found.extend(_mechanism_like_items(item))
        return found
    return []


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
