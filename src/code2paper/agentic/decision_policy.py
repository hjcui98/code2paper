from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AgenticPolicyRule(BaseModel):
    """One hard rule that constrains model-assisted graph decisions."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    description: str
    applies_to: list[str] = Field(default_factory=list)


class AgenticNodeDecisionPolicy(BaseModel):
    """Decision permissions and safety gates for one graph node."""

    model_config = ConfigDict(extra="forbid")

    node: str
    model_may_propose: bool = False
    allowed_next_nodes: list[str] = Field(default_factory=list)
    forbidden_next_nodes: list[str] = Field(default_factory=list)
    required_context_artifacts: list[str] = Field(default_factory=list)
    required_prompt_inputs: list[str] = Field(default_factory=list)
    required_gate_artifacts: list[str] = Field(default_factory=list)
    deterministic_fallback_required: bool = True
    safety_merge_required: bool = True
    rationale: str = ""


class AgenticDecisionPolicy(BaseModel):
    """Machine-readable policy for safe model-assisted LangGraph decisions."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-decision-policy"
    hard_rules: list[AgenticPolicyRule] = Field(default_factory=list)
    node_policies: list[AgenticNodeDecisionPolicy] = Field(default_factory=list)
    invariant_artifacts: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_agentic_decision_policy() -> AgenticDecisionPolicy:
    rules = [
        AgenticPolicyRule(
            rule_id="author_intent_guides_code_evidence_decides",
            description="Author intent guides retrieval priorities; code evidence decides what may be claimed.",
            applies_to=[
                "coverage_critic",
                "analysis_repair_router",
                "authoring_planner",
                "figure_planner",
                "revision_router",
                "authoring",
                "rendering",
            ],
        ),
        AgenticPolicyRule(
            rule_id="no_bypass_frozen_evidence",
            description="Do not route authored prose or figures around frozen MethodEvidence and claim verification.",
            applies_to=["evidence_sufficiency", "authoring_planner", "figure_planner", "revision_router", "authoring", "rendering"],
        ),
        AgenticPolicyRule(
            rule_id="unsupported_claims_excluded_or_caveated",
            description="Unsupported claims must be downgraded, caveated, or excluded before writing.",
            applies_to=["evidence_sufficiency", "authoring_planner", "revision_router", "authoring"],
        ),
        AgenticPolicyRule(
            rule_id="rendering_requires_validation_and_invariant_audit",
            description="Rendering is allowed only after validation and invariant audit have passed.",
            applies_to=["revision_router", "figure_planner", "invariant_audit", "rendering"],
        ),
    ]
    return AgenticDecisionPolicy(
        hard_rules=rules,
        node_policies=[
            AgenticNodeDecisionPolicy(
                node="coverage_critic",
                model_may_propose=True,
                allowed_next_nodes=["intake", "analysis", "blocked"],
                forbidden_next_nodes=["authoring", "validation", "rendering", "finalize"],
                required_context_artifacts=[
                    "retrieval_coverage",
                    "retrieval_decision_context",
                    "retrieval_rescan_plan",
                    "retrieval_rescan_report",
                    "symbol_index",
                ],
                required_prompt_inputs=["coverage", "retrieval_rescan_attention", "stage_tool_guidance"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Coverage decisions may steer bounded rescans from an explicit rescan queue or continue to analysis, "
                    "but cannot skip evidence freeze."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="analysis_repair_router",
                model_may_propose=True,
                allowed_next_nodes=["intake", "evidence", "blocked"],
                forbidden_next_nodes=["authoring", "validation", "rendering", "finalize"],
                required_context_artifacts=["analysis_repair_tasks", "evidence_repair_focus"],
                required_prompt_inputs=["analysis_repair_tasks", "analysis_repair_attention", "stage_tool_guidance"],
                required_gate_artifacts=["analysis_repair_router_decision_trace"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Analysis repair routing may accept model proposals for bounded candidate rescans or evidence freeze, "
                    "but safety merge keeps unbound repair tasks and retrieval budget authoritative."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="evidence_sufficiency",
                model_may_propose=True,
                allowed_next_nodes=["grounding", "analysis", "blocked"],
                forbidden_next_nodes=["authoring", "validation", "rendering", "finalize"],
                required_context_artifacts=["evidence_sufficiency_report", "claim_verification", "evidence", "claims"],
                required_prompt_inputs=[
                    "evidence_sufficiency_report",
                    "evidence_sufficiency_attention",
                    "stage_tool_guidance",
                ],
                required_gate_artifacts=["evidence_sufficiency_decision_trace"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Evidence sufficiency decisions may return to analysis for bounded evidence repair or proceed "
                    "to grounding with exclusions/caveats, but cannot skip claim verification."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="authoring_planner",
                model_may_propose=True,
                allowed_next_nodes=["authoring", "blocked"],
                forbidden_next_nodes=["analysis", "evidence", "rendering", "finalize"],
                required_context_artifacts=["authoring_context", "authoring_constraints", "claim_verification"],
                required_prompt_inputs=[
                    "authoring_context",
                    "authoring_evidence_attention",
                    "allowed_claim_ids",
                    "caveated_claim_ids",
                    "excluded_claim_ids",
                    "stage_tool_guidance",
                ],
                required_gate_artifacts=["evidence", "claims", "authoring_plan", "authoring_plan_decision_trace"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Authoring plan decisions may organize verified claims into Method sections, but every section "
                    "must be safety-merged against claim verification and frozen evidence ids before writing."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="revision_router",
                model_may_propose=True,
                allowed_next_nodes=["analysis", "authoring", "validation", "figure_planner", "blocked"],
                forbidden_next_nodes=["rendering", "finalize"],
                required_context_artifacts=["revision_decision_context", "revision_router_decision_trace"],
                required_prompt_inputs=[
                    "revision_decision_context",
                    "revision_validation_attention",
                    "validation",
                    "stage_tool_guidance",
                ],
                required_gate_artifacts=["validation_manifest", "agentic_invariant_audit", "traceability_ledger"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Revision decisions may choose repair routes, but rendering requests must be remapped through "
                    "figure_planner plus invariant_audit and final packaging is never directly reachable."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="figure_planner",
                model_may_propose=True,
                allowed_next_nodes=["invariant_audit", "blocked"],
                forbidden_next_nodes=["authoring", "analysis", "evidence", "rendering", "finalize"],
                required_context_artifacts=["evidence", "claims", "claim_verification"],
                required_prompt_inputs=[
                    "method_evidence",
                    "claim_map",
                    "claim_verification",
                    "figure_evidence_attention",
                    "allowed_stage_ids",
                    "allowed_node_ids",
                    "allowed_claim_ids",
                    "allowed_evidence_ids",
                    "stage_tool_guidance",
                ],
                required_gate_artifacts=["figure_plan", "figure_plan_decision_trace"],
                deterministic_fallback_required=True,
                safety_merge_required=True,
                rationale=(
                    "Figure planning may accept model proposals for visual labels, order, and edges, but the final "
                    "plan is safety-merged to supported stage nodes, verified claim ids, and frozen evidence ids."
                ),
            ),
            AgenticNodeDecisionPolicy(
                node="invariant_audit",
                model_may_propose=False,
                allowed_next_nodes=["rendering", "blocked"],
                forbidden_next_nodes=["authoring", "analysis", "finalize"],
                required_gate_artifacts=[
                    "evidence",
                    "claims",
                    "claim_verification",
                    "authoring_context",
                    "authoring_plan",
                    "figure_plan",
                    "figure_plan_decision_trace",
                    "text_claims",
                    "traceability_ledger",
                    "validation_manifest",
                ],
                deterministic_fallback_required=True,
                safety_merge_required=False,
                rationale="Pre-render audit is a deterministic hard gate over code-evidence traceability.",
            ),
        ],
        invariant_artifacts=[
            "evidence",
            "claims",
            "claim_verification",
            "evidence_sufficiency_report",
            "evidence_sufficiency_decision_trace",
            "analysis_repair_router_decision_trace",
            "authoring_constraints",
            "authoring_context",
            "authoring_plan",
            "authoring_plan_decision_trace",
            "figure_plan",
            "figure_plan_decision_trace",
            "text_claims",
            "traceability_ledger",
            "agentic_invariant_audit",
        ],
        recommended_actions=[
            "write_agentic_decision_policy_with_each_run",
            "include_policy_rules_in_model_decision_prompts",
            "reject_or_rewrite_model_routes_outside_allowed_next_nodes",
            "safety_merge_authoring_plan_proposals_before_method_writing",
        ],
    )


def hard_rule_texts() -> list[str]:
    return [rule.description for rule in build_agentic_decision_policy().hard_rules]


def write_agentic_decision_policy(path: str | Path, policy: AgenticDecisionPolicy) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_agentic_decision_policy(path: str | Path) -> AgenticDecisionPolicy:
    return AgenticDecisionPolicy.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
