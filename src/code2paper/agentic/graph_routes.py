from __future__ import annotations

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.graph_topology import EVIDENCE_GATE_SPECS, EvidenceGateSpec
from code2paper.agentic.routing import route_revision


def _gate_spec(name: str) -> EvidenceGateSpec:
    return next(gate for gate in EVIDENCE_GATE_SPECS if gate.name == name)


FROZEN_EVIDENCE_KEYS = set(_gate_spec("frozen_evidence_gate").required_artifacts)
VALIDATION_KEYS = set(_gate_spec("validation_gate").required_artifacts)


def evidence_gate(state: AgenticRunState | dict) -> str:
    run_state = state if isinstance(state, AgenticRunState) else AgenticRunState.model_validate(state)
    if FROZEN_EVIDENCE_KEYS.issubset(set(run_state.artifacts)):
        return "grounding"
    return "evidence"


def validation_router(state: AgenticRunState | dict) -> str:
    run_state = state if isinstance(state, AgenticRunState) else AgenticRunState.model_validate(state)
    return route_revision(run_state).recommended_next or "blocked"


def record_router_decision(state: AgenticRunState, *, node: str, decision: str, rationale: str) -> AgenticRunState:
    return state.model_copy(
        update={
            "decisions": [
                *state.decisions,
                AgentDecision(node=node, decision=decision, rationale=rationale),
            ],
            "next_node": decision,
        }
    )


def route_after_evidence(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    if state.blocked_reason:
        return "blocked"
    return evidence_gate(state)


def route_after_evidence_sufficiency(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    if state.blocked_reason:
        return "blocked"
    return state.next_node if state.next_node in {"grounding", "analysis", "blocked"} else "blocked"


def route_after_coverage_critic(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return state.next_node if state.next_node in {"analysis", "intake", "blocked"} else "analysis"


def route_after_analysis_repair_router(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return state.next_node if state.next_node in {"evidence", "intake", "blocked"} else "evidence"


def route_after_revision_router(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    if state.next_node in {"rendering", "invariant_audit"}:
        return "figure_planner"
    return state.next_node if state.next_node in {"authoring", "analysis", "figure_planner", "blocked", "validation"} else "blocked"


def route_after_authoring_planner(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return state.next_node if state.next_node in {"authoring", "blocked"} else "blocked"


def route_after_text_trace_builder(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return state.next_node if state.next_node in {"validation", "authoring", "analysis", "blocked"} else "blocked"


def route_after_figure_planner(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return state.next_node if state.next_node in {"invariant_audit", "blocked"} else "blocked"


def route_after_invariant_audit(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return "blocked" if state.blocked_reason else "rendering"


def route_after_rendering(raw_state: dict) -> str:
    state = AgenticRunState.model_validate(raw_state)
    return "blocked" if state.blocked_reason else "finalize"
