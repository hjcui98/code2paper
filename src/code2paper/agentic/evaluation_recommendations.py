from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationRecommendationContext:
    blocked_reason: str
    evidence_coverage_score: float | None
    has_retrieval_strategy_manifest: bool
    retrieval_rescan_missing_items: int
    retrieval_rescan_high_priority_missing_items: int
    retrieval_rescan_coverage_score: float | None
    evidence_support_rate: float | None
    unsupported_claim_rate: float | None
    partial_claim_rate: float | None
    evidence_repair_task_count: int
    evidence_repair_tasks_with_existing_evidence: int
    validation_passed: bool | None
    invariant_audit_passed: bool | None
    readiness_passed: bool | None
    traceability_passed: bool | None


def build_recommended_actions(context: EvaluationRecommendationContext) -> list[str]:
    actions: list[str] = []
    if context.blocked_reason:
        actions.append("inspect_blocked_reason_and_router_trace")
    if context.evidence_coverage_score is None:
        actions.append("emit_retrieval_coverage_for_benchmark_comparison")
    elif context.evidence_coverage_score < 0.8:
        actions.append("improve_author_intent_retrieval_coverage")
    if not context.has_retrieval_strategy_manifest:
        actions.append("emit_retrieval_strategy_manifest_for_benchmark_comparison")
    if context.retrieval_rescan_high_priority_missing_items > 0:
        actions.append("continue_high_priority_rescan_for_missing_evidence")
    if context.retrieval_rescan_missing_items > 0:
        actions.append("continue_bounded_rescan_for_missing_rescan_items")
    elif context.retrieval_rescan_coverage_score is not None and context.retrieval_rescan_coverage_score < 1.0:
        actions.append("map_partial_rescan_matches_to_evidence_ids")
    if context.unsupported_claim_rate is None:
        actions.append("emit_claim_verification_for_claim_quality_metrics")
    elif context.unsupported_claim_rate > 0:
        actions.append("remove_or_retrieve_evidence_for_unsupported_claims")
    if context.evidence_support_rate is None:
        actions.append("emit_evidence_sufficiency_report_for_evidence_quality_metrics")
    elif context.evidence_support_rate < 0.5:
        actions.append("return_to_analysis_for_stronger_evidence_before_authoring")
    if context.partial_claim_rate is not None and context.partial_claim_rate > 0:
        actions.append("keep_partial_claims_caveated_or_retrieve_more_evidence")
    if context.evidence_repair_task_count > 0:
        if context.evidence_repair_tasks_with_existing_evidence > 0:
            actions.append("reassess_existing_repair_task_evidence_before_rescan")
        if context.evidence_repair_tasks_with_existing_evidence < context.evidence_repair_task_count:
            actions.append("rescan_candidate_code_for_unbound_repair_tasks")
    if context.validation_passed is False:
        actions.append("route_back_through_revision_before_rendering")
    if context.invariant_audit_passed is False:
        actions.append("repair_evidence_invariant_failures")
    if context.readiness_passed is False:
        actions.append("repair_missing_agentic_review_contracts")
    if context.traceability_passed is False:
        actions.append("repair_text_or_figure_traceability_to_code_evidence")
    if not actions:
        actions.append("agentic_run_metrics_ready_for_benchmark_aggregation")
    return actions
