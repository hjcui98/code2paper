from __future__ import annotations

from typing import Any

from code2paper.agentic.analysis_repair_attention import analysis_repair_attention
from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _build_decision_trace,
    _call_provider_for_trace,
)
from code2paper.agentic.decision_merge import analysis_repair_safety_notes, merge_analysis_repair_decision
from code2paper.agentic.decision_models import AnalysisRepairRouterProposal
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.routing import AnalysisRepairRouterDecision, route_analysis_repair


def analysis_repair_decision_trace(
    repair_tasks_payload: dict[str, Any],
    *,
    author_intent_summary: AuthorIntentSummary | None = None,
    retrieval_round: int = 0,
    max_retrieval_rounds: int = 0,
    decision_provider: DecisionProvider | None = None,
) -> tuple[AnalysisRepairRouterDecision, AgenticDecisionTrace]:
    fallback = route_analysis_repair(
        repair_tasks_payload,
        retrieval_round=retrieval_round,
        max_retrieval_rounds=max_retrieval_rounds,
    )
    prompt = AgenticDecisionPrompt(
        node="analysis_repair_router",
        objective=(
            "Decide whether claim-level analysis repair tasks need a bounded candidate-code rescan, "
            "can continue to evidence freeze, or should block."
        ),
        hard_rules=hard_rule_texts(),
        inputs={
            "analysis_repair_tasks": repair_tasks_payload,
            "author_intent_summary": author_intent_summary.model_dump(mode="json") if author_intent_summary else None,
            "analysis_repair_attention": analysis_repair_attention(
                repair_tasks_payload,
                retrieval_round=retrieval_round,
                max_retrieval_rounds=max_retrieval_rounds,
            ),
            "retrieval_round": retrieval_round,
            "max_retrieval_rounds": max_retrieval_rounds,
            "stage_tool_guidance": stage_tool_guidance_for_decision(["intake", "analysis", "evidence"]),
        },
        fallback_decision=fallback.model_dump(mode="json"),
    )
    if decision_provider is None:
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status="deterministic_fallback",
            final_decision=fallback,
            safety_notes=["No decision provider was configured; deterministic analysis repair router was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(
        decision_provider,
        prompt,
        AnalysisRepairRouterProposal,
    )
    if proposal is None:
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_decision=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic analysis repair router was used."],
        )
    final = merge_analysis_repair_decision(fallback=fallback, proposal=proposal)
    return final, _build_decision_trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_decision=final,
        safety_notes=analysis_repair_safety_notes(fallback=fallback, proposal=proposal, final=final),
    )
