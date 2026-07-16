from __future__ import annotations

from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _build_decision_trace,
    _call_provider_for_trace,
)
from code2paper.agentic.decision_merge import (
    coverage_safety_notes,
    enrich_coverage_decision_with_rescan_plan,
    enrich_coverage_decision_with_rescan_report,
    merge_coverage_decision,
    retrieval_rescan_attention,
)
from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.decision_models import CoverageCriticProposal
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.retrieval import (
    RetrievalCoverageReport,
    RetrievalDecisionContext,
    RetrievalRescanPlan,
    RetrievalRescanReport,
    SymbolIndexReport,
)
from code2paper.agentic.retrieval_summary import RetrievalEvidenceSummary
from code2paper.agentic.routing import CoverageCriticDecision, critique_coverage


def coverage_decision_with_model(
    coverage: RetrievalCoverageReport,
    *,
    symbol_index: SymbolIndexReport | None = None,
    retrieval_context: RetrievalDecisionContext | None = None,
    retrieval_rescan_plan: RetrievalRescanPlan | None = None,
    retrieval_rescan_report: RetrievalRescanReport | None = None,
    retrieval_summary: RetrievalEvidenceSummary | None = None,
    author_intent_summary: AuthorIntentSummary | None = None,
    retrieval_round: int = 0,
    max_retrieval_rounds: int = 0,
    min_score: float = 0.55,
    decision_provider: DecisionProvider | None = None,
) -> CoverageCriticDecision:
    decision, _trace = coverage_decision_trace(
        coverage,
        symbol_index=symbol_index,
        retrieval_context=retrieval_context,
        retrieval_rescan_plan=retrieval_rescan_plan,
        retrieval_rescan_report=retrieval_rescan_report,
        retrieval_summary=retrieval_summary,
        author_intent_summary=author_intent_summary,
        retrieval_round=retrieval_round,
        max_retrieval_rounds=max_retrieval_rounds,
        min_score=min_score,
        decision_provider=decision_provider,
    )
    return decision


def coverage_decision_trace(
    coverage: RetrievalCoverageReport,
    *,
    symbol_index: SymbolIndexReport | None = None,
    retrieval_context: RetrievalDecisionContext | None = None,
    retrieval_rescan_plan: RetrievalRescanPlan | None = None,
    retrieval_rescan_report: RetrievalRescanReport | None = None,
    retrieval_summary: RetrievalEvidenceSummary | None = None,
    author_intent_summary: AuthorIntentSummary | None = None,
    retrieval_round: int = 0,
    max_retrieval_rounds: int = 0,
    min_score: float = 0.55,
    decision_provider: DecisionProvider | None = None,
) -> tuple[CoverageCriticDecision, AgenticDecisionTrace]:
    fallback = critique_coverage(
        coverage,
        symbol_index=symbol_index,
        retrieval_round=retrieval_round,
        max_retrieval_rounds=max_retrieval_rounds,
        min_score=min_score,
    )
    fallback = enrich_coverage_decision_with_rescan_plan(fallback, retrieval_rescan_plan)
    fallback = enrich_coverage_decision_with_rescan_report(fallback, retrieval_rescan_report)
    prompt = AgenticDecisionPrompt(
        node="coverage_critic",
        objective="Decide whether retrieval should continue, proceed to analysis with caveats, or block.",
        hard_rules=hard_rule_texts(),
        inputs={
            "coverage": coverage.model_dump(mode="json"),
            "retrieval_decision_context": retrieval_context.model_dump(mode="json") if retrieval_context else None,
            "retrieval_rescan_plan": retrieval_rescan_plan.model_dump(mode="json") if retrieval_rescan_plan else None,
            "retrieval_rescan_report": retrieval_rescan_report.model_dump(mode="json") if retrieval_rescan_report else None,
            "retrieval_summary": retrieval_summary.model_dump(mode="json") if retrieval_summary else None,
            "retrieval_priority_attention": _retrieval_priority_attention(retrieval_summary),
            "author_intent_summary": author_intent_summary.model_dump(mode="json") if author_intent_summary else None,
            "retrieval_rescan_attention": retrieval_rescan_attention(retrieval_rescan_report),
            "symbol_index": symbol_index.model_dump(mode="json") if symbol_index else None,
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
            safety_notes=["No decision provider was configured; deterministic coverage critic was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(
        decision_provider,
        prompt,
        CoverageCriticProposal,
    )
    if proposal is None:
        return fallback, _build_decision_trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_decision=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic coverage critic was used."],
        )
    final = merge_coverage_decision(
        fallback=fallback,
        proposal=proposal,
        coverage=coverage,
        symbol_index=symbol_index,
        retrieval_rescan_plan=retrieval_rescan_plan,
        retrieval_rescan_report=retrieval_rescan_report,
        retrieval_round=retrieval_round,
        max_retrieval_rounds=max_retrieval_rounds,
    )
    return final, _build_decision_trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_decision=final,
        safety_notes=coverage_safety_notes(fallback=fallback, proposal=proposal, final=final),
    )


def _retrieval_priority_attention(summary: RetrievalEvidenceSummary | None) -> dict[str, int | list[dict[str, str | float | list[str]]]]:
    if summary is None:
        return {"prioritized_target_count": 0, "top_prioritized_targets": []}
    return {
        "prioritized_target_count": len(summary.prioritized_targets),
        "top_prioritized_targets": [
            {
                "target_id": target.target_id,
                "claim_id": target.claim_id,
                "query": target.query,
                "path": target.path,
                "symbol": target.symbol,
                "status": target.status,
                "priority": target.priority,
                "score": target.score,
                "evidence_ids": list(target.evidence_ids),
                "reasons": list(target.reasons),
            }
            for target in summary.prioritized_targets[:8]
        ],
    }
