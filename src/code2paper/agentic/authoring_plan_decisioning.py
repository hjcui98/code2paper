from __future__ import annotations

from typing import Any

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.authoring_context import EvidenceBoundAuthoringClaim, EvidenceBoundAuthoringContext
from code2paper.agentic.authoring_plan import (
    EvidenceBoundAuthoringPlan,
    EvidenceBoundAuthoringSection,
    build_authoring_plan,
    context_from_projection,
)
from code2paper.agentic.authoring_projection import projection_writer_payload
from code2paper.agentic.trust_contracts import AuthoringInputProjection
from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _call_provider_for_trace,
)
from code2paper.agentic.decision_models import AuthoringPlanProposal
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.intent_obligations import AuthoringObligationCoverageReport


def authoring_plan_trace(
    context: EvidenceBoundAuthoringContext,
    *,
    projection: AuthoringInputProjection | None = None,
    author_intent_summary: AuthorIntentSummary | None = None,
    obligation_coverage: AuthoringObligationCoverageReport | None = None,
    decision_provider: DecisionProvider | None = None,
) -> tuple[EvidenceBoundAuthoringPlan, AgenticDecisionTrace]:
    """Build a safe authoring plan plus an auditable model/fallback trace."""

    if projection is not None:
        context = context_from_projection(projection)
    fallback = build_authoring_plan(context, projection=projection)
    prompt = AgenticDecisionPrompt(
        node="authoring_planner",
        objective=(
            "Propose a concise Method section plan from author intent and verified code-evidence claims. "
            "The final plan may only contain allowed or caveated claim ids and frozen evidence ids."
        ),
        hard_rules=_authoring_plan_rules(),
        inputs={
            "authoring_projection": projection_writer_payload(projection) if projection is not None else None,
            "authoring_context": context.model_dump(mode="json") if projection is None else None,
            "author_intent_summary": (
                author_intent_summary.model_dump(mode="json")
                if author_intent_summary
                else None
            ),
            "authoring_obligation_coverage": (
                obligation_coverage.model_dump(mode="json")
                if obligation_coverage
                else None
            ),
            "authoring_evidence_attention": _authoring_evidence_attention(context),
            "allowed_claim_ids": [claim.claim_id for claim in context.allowed_claims],
            "caveated_claim_ids": [claim.claim_id for claim in context.caveated_claims],
            "excluded_claim_ids": [claim.claim_id for claim in context.excluded_claims],
            "stage_tool_guidance": stage_tool_guidance_for_decision(["authoring"]),
        },
        fallback_decision=fallback.model_dump(mode="json"),
    )
    if decision_provider is None:
        return fallback, _trace(
            prompt=prompt,
            provider_status="deterministic_fallback",
            final_plan=fallback,
            safety_notes=["No decision provider was configured; deterministic authoring plan was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(
        decision_provider,
        prompt,
        AuthoringPlanProposal,
    )
    if not isinstance(proposal, AuthoringPlanProposal):
        return fallback, _trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_plan=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic authoring plan was used."],
        )
    final_plan, safety_notes = _merge_authoring_plan(
        context=context,
        fallback=fallback,
        proposal=proposal,
        projection_digest=projection.projection_digest if projection is not None else "",
    )
    return final_plan, _trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_plan=final_plan,
        safety_notes=safety_notes,
    )


def _merge_authoring_plan(
    *,
    context: EvidenceBoundAuthoringContext,
    fallback: EvidenceBoundAuthoringPlan,
    proposal: AuthoringPlanProposal,
    projection_digest: str = "",
) -> tuple[EvidenceBoundAuthoringPlan, list[str]]:
    claim_by_id = {claim.claim_id: claim for claim in [*context.allowed_claims, *context.caveated_claims]}
    fallback_by_claim = {claim_id: section for section in fallback.sections for claim_id in section.claim_ids}
    sections: list[EvidenceBoundAuthoringSection] = []
    covered_claim_ids: set[str] = set()
    dropped_sections = 0
    rewritten_evidence = False

    for proposed in proposal.sections:
        claim_ids = [claim_id for claim_id in _dedupe(proposed.claim_ids) if claim_id in claim_by_id]
        if not claim_ids:
            dropped_sections += 1
            continue
        allowed_evidence_ids = _claim_evidence_ids([claim_by_id[claim_id] for claim_id in claim_ids])
        proposed_evidence_ids = [evidence_id for evidence_id in _dedupe(proposed.evidence_ids) if evidence_id in allowed_evidence_ids]
        evidence_ids = proposed_evidence_ids or allowed_evidence_ids
        if evidence_ids != _dedupe(proposed.evidence_ids):
            rewritten_evidence = True
        if not evidence_ids:
            dropped_sections += 1
            continue
        covered_claim_ids.update(claim_ids)
        section_index = len(sections) + 1
        claims = [claim_by_id[claim_id] for claim_id in claim_ids]
        sections.append(
            EvidenceBoundAuthoringSection(
                section_id=f"AP-S{section_index}",
                # Model free text is not trusted as a positive-fact channel. It may
                # choose grouping/order only; wording comes from projected claims.
                heading=_section_heading("", claims, fallback_by_claim),
                purpose="; ".join(claim.claim_text for claim in claims),
                claim_ids=claim_ids,
                evidence_ids=evidence_ids,
                caveat_required=proposed.caveat_required or any(_requires_caveat(claim) for claim in claims),
                qualifier_template=_claim_qualifiers(claims),
                writing_instructions=_section_instructions([], claims),
            )
        )

    appended_claims: list[str] = []
    for fallback_section in fallback.sections:
        missing_claims = [claim_id for claim_id in fallback_section.claim_ids if claim_id not in covered_claim_ids]
        if not missing_claims:
            continue
        appended_claims.extend(missing_claims)
        section = fallback_section.model_copy(update={"section_id": f"AP-S{len(sections) + 1}"})
        sections.append(section)
        covered_claim_ids.update(missing_claims)

    final_plan = EvidenceBoundAuthoringPlan(
        method_name=context.method_name,
        author_goal=context.author_goal,
        projection_digest=projection_digest,
        sections=sections,
        excluded_claim_ids=fallback.excluded_claim_ids,
        excluded_evidence_ids=fallback.excluded_evidence_ids,
        hard_gate_passed=bool(sections) and all(section.evidence_ids for section in sections),
        recommended_actions=_recommended_actions(bool(sections)),
    )
    notes = ["Model proposal was merged through authoring-plan safety rules."]
    if dropped_sections:
        notes.append(f"Dropped {dropped_sections} proposed section(s) without allowed claim ids or evidence ids.")
    if rewritten_evidence:
        notes.append("Rewrote proposed evidence ids to the frozen ids allowed by verified claims.")
    if appended_claims:
        notes.append("Appended fallback sections for safe claim ids omitted by the proposal: " + ", ".join(appended_claims) + ".")
    return final_plan, notes


def _trace(
    *,
    prompt: AgenticDecisionPrompt,
    provider_status: str,
    final_plan: EvidenceBoundAuthoringPlan,
    provider_payload: dict[str, Any] | None = None,
    parsed_proposal: AuthoringPlanProposal | None = None,
    safety_notes: list[str] | None = None,
) -> AgenticDecisionTrace:
    return AgenticDecisionTrace(
        node="authoring_planner",
        provider_status=provider_status,
        prompt=prompt,
        provider_payload=provider_payload or {},
        parsed_proposal=parsed_proposal.model_dump(mode="json") if parsed_proposal else {},
        final_decision=final_plan.model_dump(mode="json"),
        safety_notes=safety_notes or [],
    )


def _authoring_plan_rules() -> list[str]:
    return [
        *hard_rule_texts(),
        "Authoring sections may group or order verified claims, but may not introduce new claim ids.",
        "Every planned section must carry at least one frozen evidence id from its verified claims.",
        "Excluded and unsupported claims must remain outside the plan and outside Method prose.",
        "Use author intent to prioritize and order only; author wording cannot add facts or headings absent from authorized claims.",
        "Prefer sections that cover must-cover obligations, and keep unresolved obligations in the gap report rather than inventing prose.",
    ]


def _authoring_evidence_attention(context: EvidenceBoundAuthoringContext) -> dict[str, Any]:
    writable_claims = [*context.allowed_claims, *context.caveated_claims]
    return {
        "allowed_claim_count": len(context.allowed_claims),
        "caveated_claim_count": len(context.caveated_claims),
        "excluded_claim_count": len(context.excluded_claims),
        "claim_evidence": [
            {
                "claim_id": claim.claim_id,
                "writing_boundary": claim.writing_boundary,
                "support_status": claim.support_status,
                "evidence_ids": claim.evidence_ids,
                "caveats": claim.caveats[:3],
            }
            for claim in writable_claims[:20]
        ],
        "excluded_claim_ids": [claim.claim_id for claim in context.excluded_claims[:20]],
        "negative_scope": context.negative_scope[:12],
        "unsupported_author_parts": context.unsupported_author_parts[:12],
    }


def _section_heading(
    proposed_heading: str,
    claims: list[EvidenceBoundAuthoringClaim],
    fallback_by_claim: dict[str, EvidenceBoundAuthoringSection],
) -> str:
    heading = proposed_heading.strip()
    if heading:
        return heading[:120]
    for claim in claims:
        fallback = fallback_by_claim.get(claim.claim_id)
        if fallback and fallback.heading:
            return fallback.heading
    return "Evidence-backed method step"


def _section_instructions(proposed: list[str], claims: list[EvidenceBoundAuthoringClaim]) -> list[str]:
    base = [
        "Write only the implementation behavior supported by the listed evidence ids.",
        "Do not add mechanisms, motivations, or results that are absent from frozen code evidence.",
    ]
    caveats = [
        "Caveat this claim: " + "; ".join(claim.caveats[:3])
        for claim in claims
        if _requires_caveat(claim) and claim.caveats
    ]
    return _dedupe([*proposed[:4], *base, *caveats])


def _claim_qualifiers(claims: list[EvidenceBoundAuthoringClaim]) -> list[str]:
    return _dedupe([qualifier for claim in claims if _requires_caveat(claim) for qualifier in claim.caveats])


def _claim_evidence_ids(claims: list[EvidenceBoundAuthoringClaim]) -> list[str]:
    return _dedupe([evidence_id for claim in claims for evidence_id in claim.evidence_ids])


def _requires_caveat(claim: EvidenceBoundAuthoringClaim) -> bool:
    return claim.writing_boundary == "write_only_with_caveats" or claim.support_status == "partial"


def _recommended_actions(has_sections: bool) -> list[str]:
    if has_sections:
        return ["authoring_plan_ready_for_evidence_constrained_method_writing"]
    return ["return_to_analysis_for_evidence_backed_authoring_claims"]


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
