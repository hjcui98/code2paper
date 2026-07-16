from __future__ import annotations

from typing import Protocol, Sequence


class BenchmarkVariantSummaryLike(Protocol):
    variant: str
    run_count: int
    success_rate: float | None
    blocked_rate: float | None
    avg_evidence_coverage_score: float | None
    avg_evidence_support_rate: float | None
    avg_unsupported_claim_rate: float | None
    avg_partial_claim_rate: float | None
    validation_pass_rate: float | None
    contract_audit_pass_rate: float | None
    invariant_audit_pass_rate: float | None
    readiness_pass_rate: float | None
    traceability_pass_rate: float | None
    completion_pass_rate: float | None
    avg_retrieval_rescan_missing_items: float | None
    avg_retrieval_rescan_high_priority_missing_items: float | None
    avg_evidence_repair_task_count: float | None
    avg_evidence_repair_tasks_with_existing_evidence: float | None
    missing_metric_counts: dict[str, int]
    risk_flags: list[str]


def best_variant(summaries: Sequence[BenchmarkVariantSummaryLike]) -> str:
    if not summaries:
        return ""
    scored = sorted(((variant_score(summary), summary.variant) for summary in summaries), reverse=True)
    score, variant = scored[0]
    return variant if score > float("-inf") else ""


def comparison_notes(summaries: Sequence[BenchmarkVariantSummaryLike], chosen_variant: str) -> list[str]:
    if not summaries:
        return ["no_evaluation_reports_loaded"]
    notes = [f"best_variant={chosen_variant}"] if chosen_variant else ["best_variant_unavailable"]
    for summary in summaries:
        if summary.risk_flags:
            notes.append(f"{summary.variant}:risk_flags=" + ",".join(summary.risk_flags))
    return notes


def recommended_actions(summaries: Sequence[BenchmarkVariantSummaryLike], chosen_variant: str) -> list[str]:
    actions: list[str] = []
    if not summaries:
        return ["add_agentic_run_evaluation_reports"]
    for summary in summaries:
        if summary.missing_metric_counts and any(count > 0 for count in summary.missing_metric_counts.values()):
            actions.append(f"{summary.variant}:fill_missing_evaluation_metrics")
        if "unsupported_claims_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:repair_or_retrieve_evidence_for_unsupported_claims")
        if "weak_evidence_support_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:improve_evidence_support_before_authoring")
        if "repair_tasks_need_rescan" in summary.risk_flags:
            actions.append(f"{summary.variant}:rescan_candidate_code_for_repair_tasks")
        if "high_priority_rescan_items_missing" in summary.risk_flags:
            actions.append(f"{summary.variant}:prioritize_high_priority_rescan_items")
        if "rescan_items_still_missing" in summary.risk_flags:
            actions.append(f"{summary.variant}:continue_bounded_retrieval_for_missing_rescan_items")
        if "traceability_failures_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:repair_traceability_before_comparing_prose_quality")
        if "contract_audit_failures_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:repair_agentic_contract_drift_before_benchmarking")
        if "invariant_failures_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:repair_invariant_failures_before_benchmark_win")
        if "incomplete_runs_present" in summary.risk_flags:
            actions.append(f"{summary.variant}:complete_agentic_final_deliverables_before_benchmarking")
    if chosen_variant:
        actions.append(f"use_{chosen_variant}_as_current_evidence_first_baseline")
    return _dedupe(actions)


def risk_flags(summary: BenchmarkVariantSummaryLike) -> list[str]:
    flags: list[str] = []
    if _value(summary.avg_unsupported_claim_rate) > 0:
        flags.append("unsupported_claims_present")
    if summary.avg_evidence_support_rate is not None and summary.avg_evidence_support_rate < 0.5:
        flags.append("weak_evidence_support_present")
    if (
        summary.avg_evidence_repair_task_count is not None
        and summary.avg_evidence_repair_tasks_with_existing_evidence is not None
        and summary.avg_evidence_repair_tasks_with_existing_evidence < summary.avg_evidence_repair_task_count
    ):
        flags.append("repair_tasks_need_rescan")
    if summary.avg_retrieval_rescan_missing_items is not None and summary.avg_retrieval_rescan_missing_items > 0:
        flags.append("rescan_items_still_missing")
    if (
        summary.avg_retrieval_rescan_high_priority_missing_items is not None
        and summary.avg_retrieval_rescan_high_priority_missing_items > 0
    ):
        flags.append("high_priority_rescan_items_missing")
    if summary.contract_audit_pass_rate is not None and summary.contract_audit_pass_rate < 1.0:
        flags.append("contract_audit_failures_present")
    if summary.invariant_audit_pass_rate is not None and summary.invariant_audit_pass_rate < 1.0:
        flags.append("invariant_failures_present")
    if summary.traceability_pass_rate is not None and summary.traceability_pass_rate < 1.0:
        flags.append("traceability_failures_present")
    if summary.readiness_pass_rate is not None and summary.readiness_pass_rate < 1.0:
        flags.append("readiness_failures_present")
    if summary.completion_pass_rate is not None and summary.completion_pass_rate < 1.0:
        flags.append("incomplete_runs_present")
    if summary.blocked_rate is not None and summary.blocked_rate > 0:
        flags.append("blocked_runs_present")
    return flags


def variant_score(summary: BenchmarkVariantSummaryLike) -> float:
    if summary.run_count <= 0:
        return float("-inf")
    score = 0.0
    score += 2.0 * _value(summary.contract_audit_pass_rate)
    score += 2.0 * _value(summary.invariant_audit_pass_rate)
    score += 2.0 * _value(summary.traceability_pass_rate)
    score += 1.5 * _value(summary.readiness_pass_rate)
    score += 1.5 * _value(summary.completion_pass_rate)
    score += 1.2 * _value(summary.validation_pass_rate)
    score += 1.0 * _value(summary.avg_evidence_coverage_score)
    score += 1.0 * _value(summary.avg_evidence_support_rate)
    score += 0.8 * _value(summary.success_rate)
    score -= 2.0 * _value(summary.avg_unsupported_claim_rate)
    score -= 0.7 * _value(summary.avg_partial_claim_rate)
    score -= 0.6 * _value(summary.blocked_rate)
    return round(score, 6)


def _value(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
