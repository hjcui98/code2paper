from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class DirectEdgeSpec:
    source: str
    target: str
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class ConditionalRouteSpec:
    source: str
    router: str
    routes: tuple[tuple[str, str], ...]
    safety_note: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceGateSpec:
    name: str
    node: str
    required_artifacts: tuple[str, ...]
    rationale: str


ENTRY_POINT: Final[str] = "input_resolution"
STAGE_NODE_NAMES: Final[tuple[str, ...]] = (
    "input_resolution",
    "intake",
    "analysis",
    "evidence",
    "grounding",
    "authoring",
    "validation",
    "rendering",
    "finalize",
)
TEXT_TRUST_NODE_NAMES: Final[tuple[str, ...]] = (
    "final_text_claim_extractor",
    "text_evidence_validator",
    "text_trace_builder",
    "local_text_repair",
    "packet_binding_repair",
)
TERMINAL_NODE_NAMES: Final[tuple[str, ...]] = ("finalize", "blocked")
DIRECT_EDGE_SPECS: Final[tuple[DirectEdgeSpec, ...]] = (
    DirectEdgeSpec(source="input_resolution", target="intake"),
    DirectEdgeSpec(source="intake", target="coverage_critic"),
    DirectEdgeSpec(source="analysis", target="analysis_repair_router"),
    DirectEdgeSpec(source="evidence", target="evidence_sufficiency"),
    DirectEdgeSpec(source="grounding", target="authoring_planner"),
    DirectEdgeSpec(source="authoring", target="final_text_claim_extractor"),
    DirectEdgeSpec(source="final_text_claim_extractor", target="text_evidence_validator"),
    DirectEdgeSpec(source="text_evidence_validator", target="text_trace_builder"),
    DirectEdgeSpec(source="packet_binding_repair", target="blocked"),
    DirectEdgeSpec(source="validation", target="revision_router"),
)
TERMINAL_EDGE_SPECS: Final[tuple[DirectEdgeSpec, ...]] = (
    DirectEdgeSpec(source="finalize", target="END", rationale="Successful final packaging ends the run."),
    DirectEdgeSpec(source="blocked", target="END", rationale="Blocked runs stop without rendering unsafe output."),
)
CONDITIONAL_ROUTE_SPECS: Final[tuple[ConditionalRouteSpec, ...]] = (
    ConditionalRouteSpec(
        source="coverage_critic",
        router="_route_after_coverage_critic",
        routes=(("analysis", "analysis"), ("intake", "intake"), ("blocked", "blocked")),
        safety_note=(
            "Rescans are bounded by max_retrieval_rounds and carry targeted retrieval hints from "
            "retrieval_decision_context plus the explicit retrieval_rescan_plan queue."
        ),
    ),
    ConditionalRouteSpec(
        source="analysis_repair_router",
        router="_route_after_analysis_repair_router",
        routes=(("evidence", "evidence"), ("intake", "intake"), ("blocked", "blocked")),
        safety_note=(
            "Model proposals are safety-merged against repair task bindings and max_retrieval_rounds; "
            "when budget is exhausted, the graph continues to evidence freeze so evidence sufficiency can "
            "block unsupported claims."
        ),
    ),
    ConditionalRouteSpec(
        source="evidence_sufficiency",
        router="_route_after_evidence_sufficiency",
        routes=(("grounding", "grounding"), ("analysis", "analysis"), ("blocked", "blocked")),
        safety_note=(
            "Model proposals are safety-merged against claim verification; analysis repair is bounded by "
            "max_evidence_revision_rounds and grounding is blocked when no writable evidence-backed claims exist. "
            "When repair is chosen, evidence_repair_focus carries focus claim queries and symbol-index candidates "
            "into the next analysis pass."
        ),
    ),
    ConditionalRouteSpec(
        source="authoring_planner",
        router="_route_after_authoring_planner",
        routes=(("authoring", "authoring"), ("intake", "intake"), ("analysis", "analysis"), ("blocked", "blocked")),
        safety_note=(
            "Authoring starts only after the section plan hard gate passes; model-proposed sections are "
            "filtered to verified claim ids and frozen evidence ids. Unresolved must-cover author obligations "
            "can trigger a bounded, targeted evidence-repair pass before prose is written."
        ),
    ),
    ConditionalRouteSpec(
        source="text_trace_builder",
        router="_route_after_text_trace_builder",
        routes=(("validation", "validation"), ("local_text_repair", "local_text_repair"), ("final_text_claim_extractor", "final_text_claim_extractor"), ("blocked", "blocked")),
        safety_note="Final text reaches quality validation only after exact claim tracing. Failed sentences enter a bounded local repair loop and can never route to whole-stage intake, analysis, evidence, or authoring.",
    ),
    ConditionalRouteSpec(
        source="local_text_repair",
        router="_route_after_local_text_repair",
        routes=(("final_text_claim_extractor", "final_text_claim_extractor"), ("packet_binding_repair", "packet_binding_repair"), ("blocked", "blocked")),
        safety_note="Local repair may rewrite only exact final-text spans or emit a typed packet repair request; it cannot restart a global pipeline stage.",
    ),
    ConditionalRouteSpec(
        source="revision_router",
        router="_route_after_revision_router",
        routes=(
            ("authoring", "authoring"),
            ("analysis", "analysis"),
            ("figure_planner", "figure_planner"),
            ("blocked", "blocked"),
            ("validation", "validation"),
        ),
        safety_note=(
            "Revision proposals are informed by revision_decision_context; a request to render is remapped "
            "through figure_planner and invariant_audit before rendering is allowed."
        ),
    ),
    ConditionalRouteSpec(
        source="figure_planner",
        router="_route_after_figure_planner",
        routes=(("invariant_audit", "invariant_audit"), ("blocked", "blocked")),
        safety_note=(
            "Model-proposed figure nodes and edges are filtered to supported stage nodes, verified claim ids, "
            "and frozen evidence ids before invariant audit can run."
        ),
    ),
    ConditionalRouteSpec(
        source="invariant_audit",
        router="_route_after_invariant_audit",
        routes=(("rendering", "rendering"), ("blocked", "blocked")),
        safety_note="Rendering is blocked when traceability, validation, final-package, or figure invariants fail.",
    ),
    ConditionalRouteSpec(
        source="rendering",
        router="_route_after_rendering",
        routes=(("final_invariant_audit", "final_invariant_audit"), ("blocked", "blocked")),
        safety_note="Rendered assets must pass post-render audit before the final invariant audit.",
    ),
    ConditionalRouteSpec(
        source="final_invariant_audit",
        router="_route_after_final_invariant_audit",
        routes=(("finalize", "finalize"), ("blocked", "blocked")),
        safety_note="Final packaging is reachable only after post-render invariants pass.",
    ),
)
EVIDENCE_GATE_SPECS: Final[tuple[EvidenceGateSpec, ...]] = (
    EvidenceGateSpec(
        name="frozen_evidence_gate",
        node="evidence_sufficiency",
        required_artifacts=("evidence", "claims", "claim_verification"),
        rationale="Authoring must use claim-verified frozen MethodEvidence, not raw retrieval output.",
    ),
    EvidenceGateSpec(
        name="evidence_sufficiency_gate",
        node="evidence_sufficiency",
        required_artifacts=("evidence_sufficiency_report", "evidence_sufficiency_decision_trace", "claim_verification"),
        rationale="Grounding should start only after frozen claims have an auditable sufficiency decision.",
    ),
    EvidenceGateSpec(
        name="analysis_repair_router_gate",
        node="analysis_repair_router",
        required_artifacts=("analysis_repair_tasks", "analysis_repair_router_decision_trace"),
        rationale=(
            "Analysis repair rescans or evidence-freeze decisions must keep an auditable model/fallback "
            "merge trace when repair tasks exist."
        ),
    ),
    EvidenceGateSpec(
        name="final_text_evidence_gate",
        node="text_trace_builder",
        required_artifacts=("authoring_projection", "final_text_claims", "text_evidence_validation", "final_text_trace"),
        rationale="Every factual atomic claim in the exact final text must be validated against projected direct code evidence before quality validation.",
    ),
    EvidenceGateSpec(
        name="validation_gate",
        node="validation",
        required_artifacts=("fidelity", "validation_manifest"),
        rationale="Revision routing must inspect validation results before rendering can be considered.",
    ),
    EvidenceGateSpec(
        name="authoring_context_gate",
        node="authoring_planner",
        required_artifacts=(
            "authoring_constraints",
            "authoring_context",
            "authoring_plan",
            "authoring_plan_decision_trace",
            "claim_verification",
        ),
        rationale=(
            "Method prose must be guided by author intent, planned by verified claims, and bounded by evidence; "
            "any model section proposal must leave an auditable safety-merge trace."
        ),
    ),
    EvidenceGateSpec(
        name="pre_render_invariant_gate",
        node="invariant_audit",
        required_artifacts=(
            "evidence",
            "claims",
            "claim_verification",
            "authoring_context",
            "authoring_plan",
            "text_claims",
            "traceability_ledger",
            "validation_manifest",
            "figure_plan",
            "figure_plan_decision_trace",
        ),
        rationale=(
            "Rendering is allowed only after authored text remains traceable to frozen code evidence and "
            "authoring context constraints."
        ),
    ),
    EvidenceGateSpec(
        name="revision_context_gate",
        node="revision_router",
        required_artifacts=("revision_decision_context", "revision_router_decision_trace"),
        rationale="Model-assisted revision routing must be backed by validator and invariant issue context.",
    ),
    EvidenceGateSpec(
        name="figure_evidence_gate",
        node="figure_planner",
        required_artifacts=("evidence", "claims", "claim_verification", "figure_plan", "figure_plan_decision_trace"),
        rationale=(
            "Generated method figures must be planned from verified claims and backed by frozen evidence ids "
            "before rendering."
        ),
    ),
)
