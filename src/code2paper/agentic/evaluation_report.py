from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evaluation_extractors import (
    JsonObject,
    bool_or_none,
    claim_support_counts,
    float_or_none,
    int_or_zero,
    list_count,
    rate,
    repair_candidate_count,
    repair_task_metrics,
    validation_passed,
)
from code2paper.agentic.evaluation_metrics import (
    AgenticRunEvaluationMetric,
    EvaluationMetricContext,
    build_evaluation_metrics,
)
from code2paper.agentic.evaluation_recommendations import (
    EvaluationRecommendationContext,
    build_recommended_actions,
)


class AgenticRunEvaluationReport(BaseModel):
    """Single-run evaluation surface for agentic Code2Paper executions."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-run-evaluation-report"
    scope: str = "single_run"
    status: str
    blocked_reason: str = ""
    evidence_coverage_score: float | None = None
    evidence_target_coverage_score: float | None = None
    legacy_alignment_score: float | None = None
    evidence_coverage_basis: str = ""
    evidence_support_rate: float | None = None
    unsupported_claim_rate: float | None = None
    partial_claim_rate: float | None = None
    final_text_unsupported_claim_rate: float | None = None
    text_evidence_validation_passed: bool | None = None
    retrieval_loops: int = 0
    retrieval_rescan_plan_items: int = 0
    retrieval_rescan_covered_items: int = 0
    retrieval_rescan_missing_items: int = 0
    retrieval_rescan_high_priority_missing_items: int = 0
    retrieval_rescan_coverage_score: float | None = None
    retrieval_strategy_guardrails: int = 0
    retrieval_strategy_summary_uses: int = 0
    retrieval_strategy_coverage_basis: str = ""
    evidence_revision_loops: int = 0
    evidence_repair_focus_claims: int = 0
    evidence_repair_candidate_count: int = 0
    evidence_repair_task_count: int = 0
    evidence_repair_tasks_with_existing_evidence: int = 0
    evidence_repair_candidates_with_existing_evidence: int = 0
    revision_loops: int = 0
    validation_passed: bool | None = None
    figure_plan_nodes: int = 0
    figure_plan_edges: int = 0
    figure_plan_hard_gate_passed: bool | None = None
    contract_audit_passed: bool | None = None
    invariant_audit_passed: bool | None = None
    readiness_passed: bool | None = None
    traceability_passed: bool | None = None
    metrics: list[AgenticRunEvaluationMetric] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_run_evaluation_report(state: AgenticRunState) -> AgenticRunEvaluationReport:
    """Build benchmark-facing metrics from existing auditable run artifacts."""

    coverage = _artifact_json(state, "retrieval_coverage") or _artifact_json(state, "retrieval_decision_context")
    rescan_plan = _artifact_json(state, "retrieval_rescan_plan")
    rescan_report = _artifact_json(state, "retrieval_rescan_report")
    retrieval_strategy = _artifact_json(state, "retrieval_strategy_manifest")
    sufficiency = _artifact_json(state, "evidence_sufficiency_report")
    repair_focus = _artifact_json(state, "evidence_repair_focus")
    repair_tasks = _artifact_json(state, "analysis_repair_tasks")
    verification = _artifact_json(state, "claim_verification")
    text_validation = _artifact_json(state, "text_evidence_validation")
    validation_manifest = _artifact_json(state, "validation_manifest")
    contract_audit = _artifact_json(state, "agentic_contract_audit")
    audit = _artifact_json(state, "agentic_invariant_audit")
    readiness = _artifact_json(state, "agentic_run_readiness_report")
    ledger = _artifact_json(state, "traceability_ledger")
    figure_plan = _artifact_json(state, "figure_plan")

    evidence_coverage_score = float_or_none(coverage.get("overall_score", coverage.get("coverage_score")))
    evidence_target_coverage_score = float_or_none(coverage.get("target_coverage_score"))
    legacy_alignment_score = float_or_none(coverage.get("legacy_alignment_score"))
    evidence_coverage_basis = str(coverage.get("score_basis") or "").strip()
    evidence_support_rate = float_or_none(sufficiency.get("support_rate"))
    claim_counts = claim_support_counts(verification)
    unsupported_claim_rate = rate(claim_counts.unsupported, claim_counts.total)
    partial_claim_rate = rate(claim_counts.partial, claim_counts.total)
    final_checked = int_or_zero(text_validation.get("checked_factual_claims"))
    final_unsupported = int_or_zero(text_validation.get("unsupported_claims")) + int_or_zero(text_validation.get("unverified_claims"))
    final_text_unsupported_claim_rate = rate(final_unsupported, final_checked)
    text_evidence_validation_passed = validation_passed(text_validation)
    validation_passed_value = validation_passed(validation_manifest)
    figure_plan_nodes = len(figure_plan.get("nodes") or []) if isinstance(figure_plan.get("nodes"), list) else 0
    figure_plan_edges = len(figure_plan.get("edges") or []) if isinstance(figure_plan.get("edges"), list) else 0
    figure_plan_hard_gate_passed = bool_or_none(figure_plan.get("hard_gate_passed")) if figure_plan else None
    contract_audit_passed = bool_or_none(contract_audit.get("passed")) if contract_audit else None
    invariant_audit_passed = bool_or_none(audit.get("passed")) if audit else None
    readiness_passed = bool_or_none(readiness.get("passed")) if readiness else None
    traceability_passed = bool_or_none(ledger.get("hard_gate_passed")) if ledger else None
    retrieval_loops = int(state.loop_counters.get("retrieval") or 0)
    retrieval_rescan_plan_items = len(rescan_plan.get("items") or []) if isinstance(rescan_plan.get("items"), list) else 0
    retrieval_rescan_covered_items = int_or_zero(rescan_report.get("covered_items"))
    retrieval_rescan_missing_items = int_or_zero(rescan_report.get("missing_items"))
    retrieval_rescan_high_priority_missing_items = int_or_zero(rescan_report.get("high_priority_missing_items"))
    retrieval_rescan_coverage_score = float_or_none(rescan_report.get("coverage_score"))
    retrieval_strategy_guardrails = list_count(retrieval_strategy.get("evidence_guardrails"))
    retrieval_strategy_summary_uses = list_count(retrieval_strategy.get("summary_uses"))
    retrieval_strategy_coverage_basis = str(retrieval_strategy.get("coverage_score_basis") or "").strip()
    evidence_revision_loops = int(state.loop_counters.get("evidence_revision") or 0)
    evidence_repair_focus_claims = len(repair_focus.get("focus_claim_ids") or []) if isinstance(repair_focus.get("focus_claim_ids"), list) else 0
    evidence_repair_candidate_count = repair_candidate_count(repair_focus)
    repair_metrics = repair_task_metrics(repair_tasks)
    evidence_repair_task_count = repair_metrics.task_count
    evidence_repair_tasks_with_existing_evidence = repair_metrics.tasks_with_existing_evidence
    evidence_repair_candidates_with_existing_evidence = repair_metrics.candidates_with_existing_evidence
    revision_loops = int(state.loop_counters.get("revision") or 0)
    status = "blocked" if state.blocked_reason else "success"

    metrics = build_evaluation_metrics(
        EvaluationMetricContext(
            evidence_coverage_score=evidence_coverage_score,
            evidence_target_coverage_score=evidence_target_coverage_score,
            legacy_alignment_score=legacy_alignment_score,
            evidence_support_rate=evidence_support_rate,
            unsupported_claim_rate=unsupported_claim_rate,
            partial_claim_rate=partial_claim_rate,
            retrieval_loops=retrieval_loops,
            retrieval_rescan_plan_items=retrieval_rescan_plan_items,
            retrieval_rescan_missing_items=retrieval_rescan_missing_items,
            retrieval_rescan_high_priority_missing_items=retrieval_rescan_high_priority_missing_items,
            retrieval_rescan_coverage_score=retrieval_rescan_coverage_score,
            retrieval_strategy_present=bool(retrieval_strategy),
            retrieval_strategy_guardrails=retrieval_strategy_guardrails,
            retrieval_strategy_summary_uses=retrieval_strategy_summary_uses,
            evidence_revision_loops=evidence_revision_loops,
            evidence_repair_focus_claims=evidence_repair_focus_claims,
            evidence_repair_candidate_count=evidence_repair_candidate_count,
            evidence_repair_task_count=evidence_repair_task_count,
            evidence_repair_tasks_with_existing_evidence=evidence_repair_tasks_with_existing_evidence,
            evidence_repair_candidates_with_existing_evidence=evidence_repair_candidates_with_existing_evidence,
            revision_loops=revision_loops,
            validation_passed=validation_passed_value,
            figure_plan_nodes=figure_plan_nodes,
            figure_plan_hard_gate_passed=figure_plan_hard_gate_passed,
            contract_audit_passed=contract_audit_passed,
            invariant_audit_passed=invariant_audit_passed,
            readiness_passed=readiness_passed,
            traceability_passed=traceability_passed,
        )
    )
    return AgenticRunEvaluationReport(
        status=status,
        blocked_reason=state.blocked_reason,
        evidence_coverage_score=evidence_coverage_score,
        evidence_target_coverage_score=evidence_target_coverage_score,
        legacy_alignment_score=legacy_alignment_score,
        evidence_coverage_basis=evidence_coverage_basis,
        evidence_support_rate=evidence_support_rate,
        unsupported_claim_rate=unsupported_claim_rate,
        partial_claim_rate=partial_claim_rate,
        final_text_unsupported_claim_rate=final_text_unsupported_claim_rate,
        text_evidence_validation_passed=text_evidence_validation_passed,
        retrieval_loops=retrieval_loops,
        retrieval_rescan_plan_items=retrieval_rescan_plan_items,
        retrieval_rescan_covered_items=retrieval_rescan_covered_items,
        retrieval_rescan_missing_items=retrieval_rescan_missing_items,
        retrieval_rescan_high_priority_missing_items=retrieval_rescan_high_priority_missing_items,
        retrieval_rescan_coverage_score=retrieval_rescan_coverage_score,
        retrieval_strategy_guardrails=retrieval_strategy_guardrails,
        retrieval_strategy_summary_uses=retrieval_strategy_summary_uses,
        retrieval_strategy_coverage_basis=retrieval_strategy_coverage_basis,
        evidence_revision_loops=evidence_revision_loops,
        evidence_repair_focus_claims=evidence_repair_focus_claims,
        evidence_repair_candidate_count=evidence_repair_candidate_count,
        evidence_repair_task_count=evidence_repair_task_count,
        evidence_repair_tasks_with_existing_evidence=evidence_repair_tasks_with_existing_evidence,
        evidence_repair_candidates_with_existing_evidence=evidence_repair_candidates_with_existing_evidence,
        revision_loops=revision_loops,
        validation_passed=validation_passed_value,
        figure_plan_nodes=figure_plan_nodes,
        figure_plan_edges=figure_plan_edges,
        figure_plan_hard_gate_passed=figure_plan_hard_gate_passed,
        contract_audit_passed=contract_audit_passed,
        invariant_audit_passed=invariant_audit_passed,
        readiness_passed=readiness_passed,
        traceability_passed=traceability_passed,
        metrics=metrics,
        recommended_actions=build_recommended_actions(
            EvaluationRecommendationContext(
                blocked_reason=state.blocked_reason,
                evidence_coverage_score=evidence_coverage_score,
                has_retrieval_strategy_manifest=bool(retrieval_strategy),
                retrieval_rescan_missing_items=retrieval_rescan_missing_items,
                retrieval_rescan_high_priority_missing_items=retrieval_rescan_high_priority_missing_items,
                retrieval_rescan_coverage_score=retrieval_rescan_coverage_score,
                evidence_support_rate=evidence_support_rate,
                unsupported_claim_rate=unsupported_claim_rate,
                partial_claim_rate=partial_claim_rate,
                evidence_repair_task_count=evidence_repair_task_count,
                evidence_repair_tasks_with_existing_evidence=evidence_repair_tasks_with_existing_evidence,
                validation_passed=validation_passed_value,
                invariant_audit_passed=invariant_audit_passed,
                readiness_passed=readiness_passed,
                traceability_passed=traceability_passed,
            )
        ),
    )


def write_run_evaluation_report(path: str | Path, report: AgenticRunEvaluationReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_run_evaluation_report(path: str | Path) -> AgenticRunEvaluationReport:
    return AgenticRunEvaluationReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _artifact_json(state: AgenticRunState, key: str) -> JsonObject:
    path = state.artifacts.get(key, "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
