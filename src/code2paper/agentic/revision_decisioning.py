from __future__ import annotations

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _build_decision_trace,
    _call_provider_for_trace,
)
from code2paper.agentic.decision_merge_revision import merge_revision_decision, revision_safety_notes
from code2paper.agentic.decision_models import RevisionRouterProposal
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.revision_attention import revision_validation_attention
from code2paper.agentic.revision_context import RevisionDecisionContext
from code2paper.agentic.routing import RevisionRouterDecision, route_revision
from code2paper.agentic.stage_tool_selection import build_stage_tool_selection_context


REVISION_CANDIDATE_STAGES = ["analysis", "authoring", "validation", "rendering"]


def revision_decision_with_model(
    state: AgenticRunState,
    *,
    revision_context: RevisionDecisionContext | None = None,
    decision_provider: DecisionProvider | None = None,
) -> RevisionRouterDecision:
    decision, _trace = revision_decision_trace(
        state,
        revision_context=revision_context,
        decision_provider=decision_provider,
    )
    return decision


def revision_decision_trace(
    state: AgenticRunState,
    *,
    revision_context: RevisionDecisionContext | None = None,
    decision_provider: DecisionProvider | None = None,
) -> tuple[RevisionRouterDecision, AgenticDecisionTrace]:
    fallback = route_revision(state)
    selection_context = build_stage_tool_selection_context(state, candidate_stages=REVISION_CANDIDATE_STAGES)
    prompt = AgenticDecisionPrompt(
        node="revision_router",
        objective="Choose the next graph node after validation or a blocked authoring step.",
        hard_rules=hard_rule_texts(),
        inputs={
            "blocked_reason": state.blocked_reason,
            "artifact_keys": sorted(state.artifacts),
            "validation": state.validation,
            "revision_validation_attention": revision_validation_attention(revision_context, validation=state.validation),
            "revision_decision_context": revision_context.model_dump(mode="json") if revision_context else None,
            "stage_tool_selection_context": selection_context.model_dump(mode="json"),
            "stage_tool_guidance": stage_tool_guidance_for_decision(["authoring", "validation", "rendering", "finalize"]),
        },
        fallback_decision=fallback.model_dump(mode="json"),
    )
    # A deterministic terminal gate is authoritative.  In particular, do not
    # spend another model call (or let its proposal reopen the loop) after a
    # revision budget has been exhausted.
    if fallback.recommended_next == "blocked":
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status="deterministic_terminal_gate",
            final_decision=fallback,
            safety_notes=["Deterministic terminal revision gate was authoritative; the model provider was not called."],
        )
    if decision_provider is None:
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status="deterministic_fallback",
            final_decision=fallback,
            safety_notes=["No decision provider was configured; deterministic revision router was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(
        decision_provider,
        prompt,
        RevisionRouterProposal,
    )
    if proposal is None:
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_decision=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic revision router was used."],
        )
    final = merge_revision_decision(
        state=state,
        fallback=fallback,
        proposal=proposal,
        selection_context=selection_context,
    )
    return final, _build_decision_trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_decision=final,
        safety_notes=revision_safety_notes(state=state, fallback=fallback, proposal=proposal, final=final),
    )
