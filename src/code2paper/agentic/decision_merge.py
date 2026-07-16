from __future__ import annotations

from typing import Any

from code2paper.agentic.decision_models import (
    AnalysisRepairRouterProposal,
    CoverageCriticProposal,
)
from code2paper.agentic.retrieval import (
    RetrievalCoverageReport,
    RetrievalRescanPlan,
    RetrievalRescanReport,
    SymbolIndexReport,
)
from code2paper.agentic.routing import (
    AnalysisRepairRouterDecision,
    CoverageCriticDecision,
)


def merge_coverage_decision(
    *,
    fallback: CoverageCriticDecision,
    proposal: CoverageCriticProposal,
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport | None,
    retrieval_rescan_plan: RetrievalRescanPlan | None,
    retrieval_rescan_report: RetrievalRescanReport | None,
    retrieval_round: int,
    max_retrieval_rounds: int,
) -> CoverageCriticDecision:
    next_node = proposal.recommended_next.strip() or fallback.recommended_next
    decision = proposal.decision.strip() or fallback.decision
    rationale = proposal.rationale.strip() or fallback.rationale
    if next_node not in {"intake", "analysis", "blocked"}:
        next_node = fallback.recommended_next
        decision = fallback.decision
        rationale = f"{rationale} Unsafe coverage route rejected; using deterministic route."
    if not coverage.items and next_node == "analysis" and retrieval_round < max_retrieval_rounds:
        next_node = "intake"
        decision = "rescan_or_block"
        rationale = f"{rationale} No retrieval targets are covered, so analysis cannot bypass rescan budget."
    return CoverageCriticDecision(
        decision=decision,
        rationale=rationale,
        coverage_score=coverage.overall_score,
        missing_targets=coverage.missing_targets,
        partial_targets=coverage.partial_targets,
        recommended_next=next_node,
        recommended_paths=_merge_lists(proposal.recommended_paths, fallback.recommended_paths),
        recommended_symbols=_merge_lists(proposal.recommended_symbols, fallback.recommended_symbols),
        recommended_queries=_merge_lists(proposal.recommended_queries, fallback.recommended_queries),
        artifact_keys=[
            "retrieval_coverage",
            *(["symbol_index"] if symbol_index is not None else []),
            *(["retrieval_rescan_plan"] if retrieval_rescan_plan is not None else []),
            *(["retrieval_rescan_report"] if retrieval_rescan_report is not None else []),
        ],
    )


def enrich_coverage_decision_with_rescan_plan(
    decision: CoverageCriticDecision,
    rescan_plan: RetrievalRescanPlan | None,
) -> CoverageCriticDecision:
    if rescan_plan is None or not rescan_plan.items:
        return decision
    return decision.model_copy(
        update={
            "recommended_paths": _merge_lists(decision.recommended_paths, rescan_plan.recommended_paths),
            "recommended_symbols": _merge_lists(decision.recommended_symbols, rescan_plan.recommended_symbols),
            "recommended_queries": _merge_lists(decision.recommended_queries, rescan_plan.recommended_queries),
            "artifact_keys": _merge_lists(decision.artifact_keys, ["retrieval_rescan_plan"]),
        }
    )


def enrich_coverage_decision_with_rescan_report(
    decision: CoverageCriticDecision,
    rescan_report: RetrievalRescanReport | None,
) -> CoverageCriticDecision:
    if rescan_report is None:
        return decision
    rationale = decision.rationale
    if rescan_report.high_priority_missing_items > 0:
        rationale = (
            f"{rationale} Rescan report still has {rescan_report.high_priority_missing_items} "
            "high-priority bounded retrieval items without evidence."
        ).strip()
    if rescan_report.missing_items > 0:
        rationale = (
            f"{rationale} Rescan report still has {rescan_report.missing_items} missing bounded retrieval items."
        ).strip()
    elif rescan_report.partial_items > 0:
        rationale = (
            f"{rationale} Rescan report has {rescan_report.partial_items} partial matches that need evidence-id mapping."
        ).strip()
    return decision.model_copy(
        update={
            "rationale": rationale,
            "artifact_keys": _merge_lists(decision.artifact_keys, ["retrieval_rescan_report"]),
        }
    )


def retrieval_rescan_attention(rescan_report: RetrievalRescanReport | None) -> dict[str, Any]:
    if rescan_report is None:
        return {
            "high_priority_missing_items": 0,
            "missing_high_priority_items": [],
        }
    missing_high_priority_items = [
        {
            "item_id": item.item_id,
            "source": item.source,
            "claim_id": item.claim_id,
            "target_id": item.target_id,
            "path": item.path,
            "symbol": item.symbol,
            "query": item.query,
            "reasons": item.reasons,
        }
        for item in rescan_report.items
        if item.status == "missing" and item.priority == "high"
    ][:8]
    return {
        "high_priority_missing_items": rescan_report.high_priority_missing_items,
        "missing_high_priority_items": missing_high_priority_items,
    }


def merge_analysis_repair_decision(
    *,
    fallback: AnalysisRepairRouterDecision,
    proposal: AnalysisRepairRouterProposal,
) -> AnalysisRepairRouterDecision:
    next_node = proposal.recommended_next.strip() or fallback.recommended_next
    decision = proposal.decision.strip() or fallback.decision
    rationale = proposal.rationale.strip() or fallback.rationale
    if next_node not in {"intake", "evidence", "blocked"}:
        next_node = fallback.recommended_next
        decision = fallback.decision
        rationale = f"{rationale} Unsafe analysis repair route rejected; using deterministic route."
    if fallback.unbound_task_count > 0 and fallback.retrieval_round < fallback.max_retrieval_rounds and next_node == "evidence":
        next_node = "intake"
        decision = "rescan_candidate_code"
        rationale = f"{rationale} Unbound repair tasks still have retrieval budget, so evidence freeze cannot bypass candidate rescan."
    if next_node == "intake" and fallback.retrieval_round >= fallback.max_retrieval_rounds:
        next_node = fallback.recommended_next
        decision = fallback.decision
        rationale = f"{rationale} Retrieval budget is exhausted; using deterministic route."
    return AnalysisRepairRouterDecision(
        decision=decision,
        rationale=rationale,
        recommended_next=next_node,
        task_count=fallback.task_count,
        unbound_task_count=fallback.unbound_task_count,
        retrieval_round=fallback.retrieval_round,
        max_retrieval_rounds=fallback.max_retrieval_rounds,
        artifact_keys=fallback.artifact_keys,
    )


def coverage_safety_notes(
    *,
    fallback: CoverageCriticDecision,
    proposal: CoverageCriticProposal,
    final: CoverageCriticDecision,
) -> list[str]:
    notes = ["Model proposal was merged through coverage safety rules."]
    if proposal.recommended_next and proposal.recommended_next != final.recommended_next:
        notes.append(f"Proposed next node '{proposal.recommended_next}' was rewritten to '{final.recommended_next}'.")
    if proposal.decision and proposal.decision != final.decision:
        notes.append(f"Proposed decision '{proposal.decision}' was rewritten to '{final.decision}'.")
    if final.recommended_next == fallback.recommended_next and proposal.recommended_next != fallback.recommended_next:
        notes.append("Deterministic fallback route remained authoritative.")
    return notes


def analysis_repair_safety_notes(
    *,
    fallback: AnalysisRepairRouterDecision,
    proposal: AnalysisRepairRouterProposal,
    final: AnalysisRepairRouterDecision,
) -> list[str]:
    notes = ["Model proposal was merged through analysis repair safety rules."]
    if proposal.recommended_next and proposal.recommended_next != final.recommended_next:
        notes.append(f"Proposed next node '{proposal.recommended_next}' was rewritten to '{final.recommended_next}'.")
    if proposal.decision and proposal.decision != final.decision:
        notes.append(f"Proposed decision '{proposal.decision}' was rewritten to '{final.decision}'.")
    if final.recommended_next == fallback.recommended_next and proposal.recommended_next != fallback.recommended_next:
        notes.append("Deterministic fallback route remained authoritative.")
    return notes


def _merge_lists(primary: list[str], fallback: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in [*primary, *fallback]:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
