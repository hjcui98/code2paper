from __future__ import annotations

from code2paper.agentic.contracts import EvidencePolicy
from code2paper.agentic.graph_catalog_models import AgenticGraphNode


def control_nodes() -> list[AgenticGraphNode]:
    return [
        AgenticGraphNode(
            name="coverage_critic",
            kind="router",
            description="Critique retrieval coverage and decide whether to follow a bounded rescan plan or continue to analysis.",
            input_artifacts=[
                "retrieval_coverage",
                "symbol_index",
                "retrieval_decision_context",
                "retrieval_rescan_plan",
                "retrieval_rescan_report",
            ],
            output_artifacts=[
                "coverage_critic_decision",
                "coverage_critic_decision_trace",
                "retrieval_decision_context",
                "retrieval_rescan_plan",
                "retrieval_rescan_report",
            ],
            evidence_policy=EvidencePolicy.RETRIEVES_EVIDENCE,
            allow_model_decision=True,
        ),
        AgenticGraphNode(
            name="analysis_repair_router",
            kind="router",
            description=(
                "Safety-merge model proposals after analysis based on claim-level repair tasks: rescan "
                "candidate code or continue to evidence freeze."
            ),
            input_artifacts=["analysis_repair_tasks", "evidence_repair_focus"],
            output_artifacts=["analysis_repair_router_decision", "analysis_repair_router_decision_trace"],
            evidence_policy=EvidencePolicy.ANALYZES_EVIDENCE,
            allow_model_decision=True,
        ),
        AgenticGraphNode(
            name="evidence_sufficiency",
            kind="critic",
            description="Review frozen evidence and claim verification before grounding or bounded code-candidate evidence repair.",
            input_artifacts=["evidence", "claims", "claim_verification", "symbol_index"],
            output_artifacts=[
                "evidence_sufficiency_report",
                "evidence_sufficiency_decision",
                "evidence_sufficiency_decision_trace",
                "evidence_repair_focus",
            ],
            evidence_policy=EvidencePolicy.VALIDATES_EVIDENCE,
            allow_model_decision=True,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="authoring_planner",
            kind="planner",
            description="Plan Method sections from author intent and verified claims, then safety-merge model proposals against evidence ids.",
            input_artifacts=["evidence", "claims", "claim_verification", "authoring_constraints", "authoring_context"],
            output_artifacts=["authoring_plan", "authoring_plan_decision_trace"],
            evidence_policy=EvidencePolicy.CONSUMES_FROZEN_EVIDENCE,
            allow_model_decision=True,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="final_text_claim_extractor",
            kind="extractor",
            description="Extract factual atomic claims from the exact final delivery candidate after authoring and post-processing.",
            input_artifacts=["text_clean_md", "text_md", "authoring_projection"],
            output_artifacts=["final_text_claims", "final_text_candidate"],
            evidence_policy=EvidencePolicy.CONSUMES_FROZEN_EVIDENCE,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="text_evidence_validator",
            kind="validator",
            description="Validate every final factual atomic claim against projection boundaries and direct code evidence.",
            input_artifacts=["final_text_claims", "authoring_projection", "evidence_raw"],
            output_artifacts=["text_evidence_validation"],
            evidence_policy=EvidencePolicy.VALIDATES_EVIDENCE,
            allow_model_decision=True,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="text_trace_builder",
            kind="audit",
            description="Build the authoritative post-hoc final text trace only from supported or caveated verdicts.",
            input_artifacts=["final_text_claims", "text_evidence_validation", "authoring_projection"],
            output_artifacts=["final_text_trace"],
            evidence_policy=EvidencePolicy.VALIDATES_EVIDENCE,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="revision_router",
            kind="router",
            description="Route post-validation revisions while preserving evidence and validation gates.",
            input_artifacts=[
                "validation_manifest",
                "fidelity",
                "agentic_invariant_audit",
                "traceability_ledger",
                "revision_decision_context",
            ],
            output_artifacts=[
                "revision_decision_context",
                "revision_router_decision",
                "revision_router_decision_trace",
            ],
            evidence_policy=EvidencePolicy.VALIDATES_EVIDENCE,
            allow_model_decision=True,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="figure_planner",
            kind="planner",
            description=(
                "Plan method overview figures from verified claims and frozen MethodEvidence, then safety-merge "
                "model proposals against evidence ids before invariant audit."
            ),
            input_artifacts=["evidence", "claims", "claim_verification"],
            output_artifacts=["figure_plan", "figure_plan_decision_trace"],
            evidence_policy=EvidencePolicy.CONSUMES_FROZEN_EVIDENCE,
            allow_model_decision=True,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="invariant_audit",
            kind="audit",
            description="Block rendering unless frozen evidence, text traces, validation, and figure plans are aligned.",
            input_artifacts=[
                "evidence",
                "claims",
                "claim_verification",
                "authoring_constraints",
                "authoring_context",
                "authoring_plan",
                "text_claims",
                "validation_manifest",
                "figure_plan",
                "figure_plan_decision_trace",
            ],
            output_artifacts=["traceability_ledger", "agentic_invariant_audit"],
            evidence_policy=EvidencePolicy.VALIDATES_EVIDENCE,
            hard_gate=True,
        ),
        AgenticGraphNode(
            name="blocked",
            kind="terminal",
            description="Terminal blocked state for failed safety, validation, or evidence gates.",
        ),
    ]
