from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class AgenticArchitectureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-architecture-manifest"
    orchestration: str = "langgraph"
    tool_protocol: str = "langchain_structured_tools"
    decision_scope: list[str] = Field(default_factory=list)
    hard_invariants: list[str] = Field(default_factory=list)
    evidence_gates: list[str] = Field(default_factory=list)
    authoring_contracts: list[str] = Field(default_factory=list)
    traceability_contracts: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)


def build_agentic_architecture_manifest() -> AgenticArchitectureManifest:
    return AgenticArchitectureManifest(
        decision_scope=[
            "model_may_choose_next_graph_node_within_policy_routes",
            "model_may_prioritize_retrieval_and_repair_focus",
            "model_may_plan_authoring_from_verified_claims",
            "model_may_not_write_or_render_unsupported_method_claims",
        ],
        hard_invariants=[
            "code_evidence_must_be_frozen_before_authoring",
            "claims_must_reference_known_evidence_ids",
            "method_text_must_follow_authoring_context_and_plan",
            "method_figures_must_use_frozen_evidence_ids",
        ],
        evidence_gates=[
            "frozen_evidence_gate",
            "claim_verification",
            "evidence_sufficiency_gate",
            "traceability_ledger",
            "figure_evidence_plan",
        ],
        authoring_contracts=[
            "author_intent_guides_section_plan",
            "authoring_context_filters_to_supported_or_caveated_claims",
            "authoring_constraints_exclude_unsupported_claims",
        ],
        traceability_contracts=[
            "paragraphs_link_to_claim_ids_and_evidence_span_ids",
            "figures_link_nodes_and_edges_to_evidence_ids",
            "run_readiness_requires_auditable_decision_traces",
        ],
        source_artifacts=[
            "agentic_decision_policy",
            "agentic_graph_catalog",
            "agentic_tool_catalog",
            "agentic_langchain_tool_manifest",
            "agentic_contract_audit",
            "agentic_invariant_audit",
        ],
    )


def write_agentic_architecture_manifest(path: str | Path, manifest: AgenticArchitectureManifest) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_agentic_architecture_manifest(path: str | Path) -> AgenticArchitectureManifest:
    return AgenticArchitectureManifest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
