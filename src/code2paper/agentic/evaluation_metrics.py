from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class AgenticRunEvaluationMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | int | str | bool
    unit: str = ""
    higher_is_better: bool | None = None
    source_artifacts: list[str] = Field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class EvaluationMetricContext:
    evidence_coverage_score: float | None
    evidence_target_coverage_score: float | None
    legacy_alignment_score: float | None
    evidence_support_rate: float | None
    unsupported_claim_rate: float | None
    partial_claim_rate: float | None
    retrieval_loops: int
    retrieval_rescan_plan_items: int
    retrieval_rescan_missing_items: int
    retrieval_rescan_high_priority_missing_items: int
    retrieval_rescan_coverage_score: float | None
    retrieval_strategy_present: bool
    retrieval_strategy_guardrails: int
    retrieval_strategy_summary_uses: int
    evidence_revision_loops: int
    evidence_repair_focus_claims: int
    evidence_repair_candidate_count: int
    evidence_repair_task_count: int
    evidence_repair_tasks_with_existing_evidence: int
    evidence_repair_candidates_with_existing_evidence: int
    revision_loops: int
    validation_passed: bool | None
    figure_plan_nodes: int
    figure_plan_hard_gate_passed: bool | None
    contract_audit_passed: bool | None
    invariant_audit_passed: bool | None
    readiness_passed: bool | None
    traceability_passed: bool | None


def build_evaluation_metrics(context: EvaluationMetricContext) -> list[AgenticRunEvaluationMetric]:
    return [
        AgenticRunEvaluationMetric(
            name="evidence_coverage_score",
            value=context.evidence_coverage_score if context.evidence_coverage_score is not None else "missing",
            unit="ratio",
            higher_is_better=True,
            source_artifacts=["retrieval_coverage", "retrieval_decision_context"],
            notes="Author-intent retrieval target coverage before evidence freeze.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_target_coverage_score",
            value=context.evidence_target_coverage_score if context.evidence_target_coverage_score is not None else "missing",
            unit="ratio",
            higher_is_better=True,
            source_artifacts=["retrieval_coverage"],
            notes="Coverage of explicit retrieval targets before any legacy alignment fallback.",
        ),
        AgenticRunEvaluationMetric(
            name="legacy_alignment_score",
            value=context.legacy_alignment_score if context.legacy_alignment_score is not None else "missing",
            unit="ratio",
            higher_is_better=True,
            source_artifacts=["retrieval_coverage", "intake_alignment", "alignment"],
            notes="Legacy method-code alignment score retained as context, not as the primary retrieval score.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_support_rate",
            value=context.evidence_support_rate if context.evidence_support_rate is not None else "missing",
            unit="ratio",
            higher_is_better=True,
            source_artifacts=["evidence_sufficiency_report", "claim_verification"],
            notes="Fraction of frozen verified claims that are supported or partially supported after evidence freeze.",
        ),
        AgenticRunEvaluationMetric(
            name="unsupported_claim_rate",
            value=context.unsupported_claim_rate if context.unsupported_claim_rate is not None else "missing",
            unit="ratio",
            higher_is_better=False,
            source_artifacts=["claim_verification"],
            notes="Fraction of verified claims classified as unsupported.",
        ),
        AgenticRunEvaluationMetric(
            name="partial_claim_rate",
            value=context.partial_claim_rate if context.partial_claim_rate is not None else "missing",
            unit="ratio",
            higher_is_better=False,
            source_artifacts=["claim_verification"],
            notes="Fraction of verified claims requiring caveats.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_loops",
            value=context.retrieval_loops,
            unit="count",
            higher_is_better=None,
            source_artifacts=["coverage_critic_decision", "coverage_critic_decision_trace"],
            notes="Number of coverage-critic retrieval retries used.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_rescan_plan_items",
            value=context.retrieval_rescan_plan_items,
            unit="count",
            higher_is_better=None,
            source_artifacts=["retrieval_rescan_plan", "retrieval_decision_context", "analysis_repair_tasks"],
            notes="Number of bounded next-pass retrieval items generated from coverage gaps or repair tasks.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_rescan_coverage_score",
            value=context.retrieval_rescan_coverage_score if context.retrieval_rescan_coverage_score is not None else "missing",
            unit="ratio",
            higher_is_better=True,
            source_artifacts=["retrieval_rescan_report", "retrieval_rescan_plan", "evidence_index"],
            notes="Fraction of bounded rescan items matched to snippets/evidence ids in the current intake pass.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_rescan_missing_items",
            value=context.retrieval_rescan_missing_items,
            unit="count",
            higher_is_better=False,
            source_artifacts=["retrieval_rescan_report", "retrieval_rescan_plan"],
            notes="Number of bounded rescan items still missing after the current intake pass.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_rescan_high_priority_missing_items",
            value=context.retrieval_rescan_high_priority_missing_items,
            unit="count",
            higher_is_better=False,
            source_artifacts=["retrieval_rescan_report", "retrieval_rescan_plan", "analysis_repair_tasks"],
            notes="Number of high-priority rescan items still missing, especially claim evidence repair tasks.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_strategy_guardrails",
            value=context.retrieval_strategy_guardrails if context.retrieval_strategy_present else "missing",
            unit="count",
            higher_is_better=True,
            source_artifacts=["retrieval_strategy_manifest"],
            notes="Evidence guardrails declared by retrieval strategy; retrieval can prioritize candidates, but evidence freeze and validators decide writable claims.",
        ),
        AgenticRunEvaluationMetric(
            name="retrieval_strategy_summary_uses",
            value=context.retrieval_strategy_summary_uses if context.retrieval_strategy_present else "missing",
            unit="count",
            higher_is_better=True,
            source_artifacts=["retrieval_strategy_manifest", "retrieval_summary"],
            notes="Declared uses of retrieval summaries for code-evidence alignment, coverage attention, and next intake focus.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_revision_loops",
            value=context.evidence_revision_loops,
            unit="count",
            higher_is_better=None,
            source_artifacts=["evidence_sufficiency_decision", "evidence_sufficiency_decision_trace"],
            notes="Number of evidence-sufficiency analysis repair loops used.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_repair_focus_claims",
            value=context.evidence_repair_focus_claims,
            unit="count",
            higher_is_better=None,
            source_artifacts=["evidence_repair_focus", "evidence_sufficiency_decision"],
            notes="Number of claim ids carried from evidence sufficiency into analysis/intake repair focus.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_repair_candidate_count",
            value=context.evidence_repair_candidate_count,
            unit="count",
            higher_is_better=None,
            source_artifacts=["evidence_repair_focus", "symbol_index"],
            notes="Number of ranked file/symbol candidates attached to weak claims for evidence repair.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_repair_task_count",
            value=context.evidence_repair_task_count,
            unit="count",
            higher_is_better=None,
            source_artifacts=["analysis_repair_tasks", "evidence_repair_focus"],
            notes="Number of weak-claim repair tasks generated for the analysis stage.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_repair_tasks_with_existing_evidence",
            value=context.evidence_repair_tasks_with_existing_evidence,
            unit="count",
            higher_is_better=None,
            source_artifacts=["analysis_repair_tasks", "evidence_index"],
            notes="Number of repair tasks whose candidates already map to frozen snippet evidence ids.",
        ),
        AgenticRunEvaluationMetric(
            name="evidence_repair_candidates_with_existing_evidence",
            value=context.evidence_repair_candidates_with_existing_evidence,
            unit="count",
            higher_is_better=None,
            source_artifacts=["analysis_repair_tasks", "evidence_index"],
            notes="Number of repair candidates that are already backed by snippet-to-evidence mappings.",
        ),
        AgenticRunEvaluationMetric(
            name="revision_loops",
            value=context.revision_loops,
            unit="count",
            higher_is_better=None,
            source_artifacts=["revision_router_decision", "revision_router_decision_trace"],
            notes="Number of validator-driven revision retries recorded in state.",
        ),
        AgenticRunEvaluationMetric(
            name="validation_passed",
            value=context.validation_passed if context.validation_passed is not None else "missing",
            source_artifacts=["validation_manifest", "fidelity"],
            notes="Whether produced Method text passed validation artifacts.",
        ),
        AgenticRunEvaluationMetric(
            name="figure_plan_hard_gate_passed",
            value=context.figure_plan_hard_gate_passed if context.figure_plan_hard_gate_passed is not None else "missing",
            source_artifacts=["figure_plan", "figure_plan_decision_trace"],
            notes="Whether the method overview figure plan is backed by frozen evidence ids.",
        ),
        AgenticRunEvaluationMetric(
            name="figure_plan_nodes",
            value=context.figure_plan_nodes,
            unit="count",
            higher_is_better=None,
            source_artifacts=["figure_plan", "figure_plan_decision_trace"],
            notes="Number of evidence-backed visual nodes in the method overview plan.",
        ),
        AgenticRunEvaluationMetric(
            name="contract_audit_passed",
            value=context.contract_audit_passed if context.contract_audit_passed is not None else "missing",
            source_artifacts=["agentic_contract_audit", "agentic_decision_policy", "agentic_graph_catalog", "agentic_tool_catalog"],
            notes="Whether graph, policy, and LangChain stage tool contracts agree.",
        ),
        AgenticRunEvaluationMetric(
            name="invariant_audit_passed",
            value=context.invariant_audit_passed if context.invariant_audit_passed is not None else "missing",
            source_artifacts=["agentic_invariant_audit"],
            notes="Whether non-negotiable evidence invariants passed.",
        ),
        AgenticRunEvaluationMetric(
            name="readiness_passed",
            value=context.readiness_passed if context.readiness_passed is not None else "missing",
            source_artifacts=["agentic_run_readiness_report"],
            notes="Whether run-level review contracts are complete.",
        ),
        AgenticRunEvaluationMetric(
            name="traceability_passed",
            value=context.traceability_passed if context.traceability_passed is not None else "missing",
            source_artifacts=["traceability_ledger"],
            notes="Whether text, claims, and figure entries trace to frozen code evidence.",
        ),
    ]
