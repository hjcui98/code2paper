from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.benchmark_outcomes import best_variant, comparison_notes, recommended_actions, risk_flags
from code2paper.agentic.completion_report import load_run_completion_report
from code2paper.agentic.evaluation_report import AgenticRunEvaluationReport, load_run_evaluation_report


class AgenticBenchmarkRunSpec(BaseModel):
    """One evaluation report participating in a benchmark aggregation."""

    model_config = ConfigDict(extra="forbid")

    path: str
    variant: str = "agentic"
    label: str = ""


class AgenticBenchmarkRunRecord(BaseModel):
    """Normalized single-run benchmark row."""

    model_config = ConfigDict(extra="forbid")

    path: str
    variant: str
    label: str
    status: str
    blocked_reason: str = ""
    evidence_coverage_score: float | None = None
    evidence_support_rate: float | None = None
    unsupported_claim_rate: float | None = None
    partial_claim_rate: float | None = None
    retrieval_loops: int = 0
    retrieval_rescan_plan_items: int = 0
    retrieval_rescan_covered_items: int = 0
    retrieval_rescan_missing_items: int = 0
    retrieval_rescan_high_priority_missing_items: int = 0
    retrieval_rescan_coverage_score: float | None = None
    evidence_revision_loops: int = 0
    evidence_repair_focus_claims: int = 0
    evidence_repair_candidate_count: int = 0
    evidence_repair_task_count: int = 0
    evidence_repair_tasks_with_existing_evidence: int = 0
    evidence_repair_candidates_with_existing_evidence: int = 0
    revision_loops: int = 0
    validation_passed: bool | None = None
    contract_audit_passed: bool | None = None
    invariant_audit_passed: bool | None = None
    readiness_passed: bool | None = None
    traceability_passed: bool | None = None
    completion_complete: bool | None = None
    completion_status: str = ""
    missing_deliverables: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class AgenticBenchmarkVariantSummary(BaseModel):
    """Aggregated metrics for one pipeline or agent variant."""

    model_config = ConfigDict(extra="forbid")

    variant: str
    run_count: int = 0
    success_rate: float | None = None
    blocked_rate: float | None = None
    avg_evidence_coverage_score: float | None = None
    avg_evidence_support_rate: float | None = None
    avg_unsupported_claim_rate: float | None = None
    avg_partial_claim_rate: float | None = None
    validation_pass_rate: float | None = None
    contract_audit_pass_rate: float | None = None
    invariant_audit_pass_rate: float | None = None
    readiness_pass_rate: float | None = None
    traceability_pass_rate: float | None = None
    completion_pass_rate: float | None = None
    avg_retrieval_loops: float | None = None
    avg_retrieval_rescan_plan_items: float | None = None
    avg_retrieval_rescan_covered_items: float | None = None
    avg_retrieval_rescan_missing_items: float | None = None
    avg_retrieval_rescan_high_priority_missing_items: float | None = None
    avg_retrieval_rescan_coverage_score: float | None = None
    avg_evidence_revision_loops: float | None = None
    avg_evidence_repair_focus_claims: float | None = None
    avg_evidence_repair_candidate_count: float | None = None
    avg_evidence_repair_task_count: float | None = None
    avg_evidence_repair_tasks_with_existing_evidence: float | None = None
    avg_evidence_repair_candidates_with_existing_evidence: float | None = None
    avg_revision_loops: float | None = None
    missing_metric_counts: dict[str, int] = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)


class AgenticBenchmarkReport(BaseModel):
    """Cross-run benchmark report for evidence-constrained agentic runs."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-benchmark-report"
    scope: str = "multi_run"
    run_count: int = 0
    variants: list[str] = Field(default_factory=list)
    runs: list[AgenticBenchmarkRunRecord] = Field(default_factory=list)
    variant_summaries: list[AgenticBenchmarkVariantSummary] = Field(default_factory=list)
    best_variant: str = ""
    comparison_notes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_agentic_benchmark_report(specs: Sequence[AgenticBenchmarkRunSpec]) -> AgenticBenchmarkReport:
    """Aggregate single-run evaluation reports into benchmark-level evidence metrics."""

    runs = [_run_record(spec) for spec in specs]
    variants = sorted({run.variant for run in runs})
    summaries = [_variant_summary(variant, [run for run in runs if run.variant == variant]) for variant in variants]
    best_variant_name = best_variant(summaries)
    return AgenticBenchmarkReport(
        run_count=len(runs),
        variants=variants,
        runs=runs,
        variant_summaries=summaries,
        best_variant=best_variant_name,
        comparison_notes=comparison_notes(summaries, best_variant_name),
        recommended_actions=recommended_actions(summaries, best_variant_name),
    )


def write_agentic_benchmark_report(path: str | Path, report: AgenticBenchmarkReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_agentic_benchmark_report(path: str | Path) -> AgenticBenchmarkReport:
    return AgenticBenchmarkReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _run_record(spec: AgenticBenchmarkRunSpec) -> AgenticBenchmarkRunRecord:
    report = load_run_evaluation_report(spec.path)
    completion = _adjacent_completion_report(spec.path)
    return AgenticBenchmarkRunRecord(
        path=spec.path,
        variant=spec.variant,
        label=spec.label or Path(spec.path).stem,
        status=report.status,
        blocked_reason=report.blocked_reason,
        evidence_coverage_score=report.evidence_coverage_score,
        evidence_support_rate=report.evidence_support_rate,
        unsupported_claim_rate=report.unsupported_claim_rate,
        partial_claim_rate=report.partial_claim_rate,
        retrieval_loops=report.retrieval_loops,
        retrieval_rescan_plan_items=report.retrieval_rescan_plan_items,
        retrieval_rescan_covered_items=report.retrieval_rescan_covered_items,
        retrieval_rescan_missing_items=report.retrieval_rescan_missing_items,
        retrieval_rescan_high_priority_missing_items=report.retrieval_rescan_high_priority_missing_items,
        retrieval_rescan_coverage_score=report.retrieval_rescan_coverage_score,
        evidence_revision_loops=report.evidence_revision_loops,
        evidence_repair_focus_claims=report.evidence_repair_focus_claims,
        evidence_repair_candidate_count=report.evidence_repair_candidate_count,
        evidence_repair_task_count=report.evidence_repair_task_count,
        evidence_repair_tasks_with_existing_evidence=report.evidence_repair_tasks_with_existing_evidence,
        evidence_repair_candidates_with_existing_evidence=report.evidence_repair_candidates_with_existing_evidence,
        revision_loops=report.revision_loops,
        validation_passed=report.validation_passed,
        contract_audit_passed=report.contract_audit_passed,
        invariant_audit_passed=report.invariant_audit_passed,
        readiness_passed=report.readiness_passed,
        traceability_passed=report.traceability_passed,
        completion_complete=completion.complete if completion else None,
        completion_status=completion.status if completion else "",
        missing_deliverables=list(completion.missing_deliverables) if completion else [],
        recommended_actions=report.recommended_actions,
    )


def _variant_summary(variant: str, runs: list[AgenticBenchmarkRunRecord]) -> AgenticBenchmarkVariantSummary:
    run_count = len(runs)
    missing_counts = {
        "evidence_coverage_score": _missing_count([run.evidence_coverage_score for run in runs]),
        "evidence_support_rate": _missing_count([run.evidence_support_rate for run in runs]),
        "unsupported_claim_rate": _missing_count([run.unsupported_claim_rate for run in runs]),
        "partial_claim_rate": _missing_count([run.partial_claim_rate for run in runs]),
        "validation_passed": _missing_count([run.validation_passed for run in runs]),
        "contract_audit_passed": _missing_count([run.contract_audit_passed for run in runs]),
        "invariant_audit_passed": _missing_count([run.invariant_audit_passed for run in runs]),
        "readiness_passed": _missing_count([run.readiness_passed for run in runs]),
        "traceability_passed": _missing_count([run.traceability_passed for run in runs]),
        "completion_complete": _missing_count([run.completion_complete for run in runs]),
        "retrieval_rescan_coverage_score": _missing_count([run.retrieval_rescan_coverage_score for run in runs]),
    }
    summary = AgenticBenchmarkVariantSummary(
        variant=variant,
        run_count=run_count,
        success_rate=_bool_rate([run.status == "success" for run in runs]),
        blocked_rate=_bool_rate([run.status == "blocked" for run in runs]),
        avg_evidence_coverage_score=_average([run.evidence_coverage_score for run in runs]),
        avg_evidence_support_rate=_average([run.evidence_support_rate for run in runs]),
        avg_unsupported_claim_rate=_average([run.unsupported_claim_rate for run in runs]),
        avg_partial_claim_rate=_average([run.partial_claim_rate for run in runs]),
        validation_pass_rate=_bool_rate([run.validation_passed for run in runs]),
        contract_audit_pass_rate=_bool_rate([run.contract_audit_passed for run in runs]),
        invariant_audit_pass_rate=_bool_rate([run.invariant_audit_passed for run in runs]),
        readiness_pass_rate=_bool_rate([run.readiness_passed for run in runs]),
        traceability_pass_rate=_bool_rate([run.traceability_passed for run in runs]),
        completion_pass_rate=_bool_rate([run.completion_complete for run in runs]),
        avg_retrieval_loops=_average([run.retrieval_loops for run in runs]),
        avg_retrieval_rescan_plan_items=_average([run.retrieval_rescan_plan_items for run in runs]),
        avg_retrieval_rescan_covered_items=_average([run.retrieval_rescan_covered_items for run in runs]),
        avg_retrieval_rescan_missing_items=_average([run.retrieval_rescan_missing_items for run in runs]),
        avg_retrieval_rescan_high_priority_missing_items=_average(
            [run.retrieval_rescan_high_priority_missing_items for run in runs]
        ),
        avg_retrieval_rescan_coverage_score=_average([run.retrieval_rescan_coverage_score for run in runs]),
        avg_evidence_revision_loops=_average([run.evidence_revision_loops for run in runs]),
        avg_evidence_repair_focus_claims=_average([run.evidence_repair_focus_claims for run in runs]),
        avg_evidence_repair_candidate_count=_average([run.evidence_repair_candidate_count for run in runs]),
        avg_evidence_repair_task_count=_average([run.evidence_repair_task_count for run in runs]),
        avg_evidence_repair_tasks_with_existing_evidence=_average(
            [run.evidence_repair_tasks_with_existing_evidence for run in runs]
        ),
        avg_evidence_repair_candidates_with_existing_evidence=_average(
            [run.evidence_repair_candidates_with_existing_evidence for run in runs]
        ),
        avg_revision_loops=_average([run.revision_loops for run in runs]),
        missing_metric_counts=missing_counts,
    )
    return summary.model_copy(update={"risk_flags": risk_flags(summary)})


def _adjacent_completion_report(evaluation_path: str):
    completion_path = Path(evaluation_path).with_name("agentic_run_completion_report.json")
    if not completion_path.exists():
        return None
    return load_run_completion_report(completion_path)


def _average(values: Sequence[float | int | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def _bool_rate(values: Sequence[bool | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(1 for value in present if value) / len(present), 4)


def _missing_count(values: Sequence[Any]) -> int:
    return sum(1 for value in values if value is None)
