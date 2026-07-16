from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from code2paper.agentic.analysis_repair_decisioning import analysis_repair_decision_trace
from code2paper.agentic.coverage_decisioning import coverage_decision_trace, coverage_decision_with_model
from code2paper.agentic.decision_core import (
    AgenticDecisionPrompt,
    AgenticDecisionTrace,
    DecisionProvider,
    _call_provider_for_trace,
    build_langchain_decision_provider,
    load_decision_trace,
    write_decision_trace,
)
from code2paper.agentic.decision_models import (
    AnalysisRepairRouterProposal,
    AuthoringPlanProposal,
    AuthoringPlanSectionProposal,
    CoverageCriticProposal,
    EvidenceSufficiencyProposal,
    RevisionRouterProposal,
)
from code2paper.agentic.revision_decisioning import revision_decision_trace, revision_decision_with_model


_SUPPORTED_DECISION_PROMPT_INPUTS: Final[Mapping[str, tuple[str, ...]]] = {
    "coverage_critic": (
        "coverage",
        "retrieval_decision_context",
        "retrieval_rescan_plan",
        "retrieval_rescan_report",
        "retrieval_rescan_attention",
        "stage_tool_guidance",
        "symbol_index",
        "retrieval_round",
        "max_retrieval_rounds",
    ),
    "analysis_repair_router": (
        "analysis_repair_tasks",
        "analysis_repair_attention",
        "stage_tool_guidance",
        "retrieval_round",
        "max_retrieval_rounds",
    ),
    "evidence_sufficiency": (
        "evidence_sufficiency_report",
        "evidence_sufficiency_attention",
        "stage_tool_guidance",
        "evidence_revision_round",
        "max_evidence_revision_rounds",
    ),
    "authoring_planner": (
        "authoring_context",
        "authoring_evidence_attention",
        "allowed_claim_ids",
        "caveated_claim_ids",
        "excluded_claim_ids",
        "stage_tool_guidance",
    ),
    "revision_router": (
        "blocked_reason",
        "artifact_keys",
        "validation",
        "revision_validation_attention",
        "revision_decision_context",
        "stage_tool_guidance",
    ),
    "figure_planner": (
        "method_evidence",
        "claim_map",
        "claim_verification",
        "figure_evidence_attention",
        "allowed_stage_ids",
        "allowed_node_ids",
        "allowed_claim_ids",
        "allowed_evidence_ids",
        "stage_tool_guidance",
    ),
}

_SUPPORTED_DECISION_PROMPT_HARD_RULE_NODES: Final[tuple[str, ...]] = tuple(_SUPPORTED_DECISION_PROMPT_INPUTS)


def supported_decision_prompt_inputs() -> Mapping[str, tuple[str, ...]]:
    return _SUPPORTED_DECISION_PROMPT_INPUTS


def supported_decision_prompt_hard_rule_nodes() -> tuple[str, ...]:
    return _SUPPORTED_DECISION_PROMPT_HARD_RULE_NODES
