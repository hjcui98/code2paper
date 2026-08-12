from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from code2paper.agentic.decision_core import DecisionProvider
from code2paper.agentic.graph_evidence_nodes import (
    authoring_planner_node as _authoring_planner_node,
    evidence_sufficiency_node as _evidence_sufficiency_node,
    figure_planner_node as _figure_planner_node,
)
from code2paper.agentic.graph_retrieval_nodes import (
    _empty_coverage,
    analysis_repair_router_node as _analysis_repair_router_node,
    coverage_critic_node as _coverage_critic_node,
)
from code2paper.agentic.graph_revision_nodes import revision_router_node as _revision_router_node
from code2paper.agentic.graph_routes import (
    FROZEN_EVIDENCE_KEYS,
    VALIDATION_KEYS,
    evidence_gate,
    record_router_decision,
    route_after_analysis_repair_router as _route_after_analysis_repair_router,
    route_after_authoring_planner as _route_after_authoring_planner,
    route_after_coverage_critic as _route_after_coverage_critic,
    route_after_evidence as _route_after_evidence,
    route_after_evidence_sufficiency as _route_after_evidence_sufficiency,
    route_after_figure_planner as _route_after_figure_planner,
    route_after_invariant_audit as _route_after_invariant_audit,
    route_after_rendering as _route_after_rendering,
    route_after_final_invariant_audit as _route_after_final_invariant_audit,
    route_after_revision_router as _route_after_revision_router,
    route_after_text_trace_builder as _route_after_text_trace_builder,
    route_after_local_text_repair as _route_after_local_text_repair,
    route_after_packet_binding_repair as _route_after_packet_binding_repair,
    validation_router,
)
from code2paper.agentic.graph_stage_nodes import (
    blocked_node as _blocked_node,
    invariant_audit_node as _invariant_audit_node,
    final_invariant_audit_node as _final_invariant_audit_node,
    stage_node as _stage_node,
)
from code2paper.agentic.graph_text_trust_nodes import (
    final_text_claim_extractor_node as _final_text_claim_extractor_node,
    text_evidence_validator_node as _text_evidence_validator_node,
    text_trace_builder_node as _text_trace_builder_node,
    local_text_repair_node as _local_text_repair_node,
    packet_binding_repair_node as _packet_binding_repair_node,
)
from code2paper.agentic.graph_topology import (
    CONDITIONAL_ROUTE_SPECS,
    DIRECT_EDGE_SPECS,
    ENTRY_POINT,
    STAGE_NODE_NAMES,
    TERMINAL_EDGE_SPECS,
)
from code2paper.agentic.graph_state_io import (
    claim_verification_path as _claim_verification_path,
    path_exists as _path_exists,
    read_json as _read_json,
    read_json_if_exists as _read_json_if_exists,
    string_mapping as _string_mapping,
)
from code2paper.agentic.tools import Code2PaperStageTool
from code2paper.agentic.text_evidence_validator import SemanticVerifier
from code2paper.agentic.state_v2 import AgenticRunStateV2


RouteFn = Callable[[dict[str, Any]], str]


def build_code2paper_graph(
    tool_registry: Mapping[str, Code2PaperStageTool],
    *,
    decision_provider: DecisionProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    local_rewrite_agent: Any | None = None,
    packet_repair_owner: Any | None = None,
    checkpointer: Any | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
):
    """Build a LangGraph app from registered Code2Paper tools.

    This is the first graph-shaped shell over the legacy pipeline. It remains
    conservative: the authoring branch is unreachable until MethodEvidence and
    claim maps have been produced.
    """

    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "Install the optional agentic extra to build the graph: "
            "pip install -e .[agentic]"
        ) from exc

    graph = StateGraph(AgenticRunStateV2)
    for stage in STAGE_NODE_NAMES:
        graph.add_node(stage, _stage_node(stage, tool_registry))
    graph.add_node("coverage_critic", _coverage_critic_node(decision_provider=decision_provider))
    graph.add_node("analysis_repair_router", _analysis_repair_router_node(decision_provider=decision_provider))
    graph.add_node("evidence_sufficiency", _evidence_sufficiency_node(decision_provider=decision_provider))
    graph.add_node("authoring_planner", _authoring_planner_node(decision_provider=decision_provider))
    graph.add_node("revision_router", _revision_router_node(decision_provider=decision_provider))
    graph.add_node("final_text_claim_extractor", _final_text_claim_extractor_node)
    graph.add_node(
        "text_evidence_validator",
        lambda state: _text_evidence_validator_node(state, semantic_verifier=semantic_verifier),
    )
    graph.add_node("text_trace_builder", _text_trace_builder_node)
    graph.add_node(
        "local_text_repair",
        lambda state: _local_text_repair_node(state, rewrite_agent=local_rewrite_agent),
    )
    graph.add_node(
        "packet_binding_repair",
        lambda state: _packet_binding_repair_node(state, repair_owner=packet_repair_owner),
    )
    graph.add_node("figure_planner", _figure_planner_node(decision_provider=decision_provider))
    graph.add_node("invariant_audit", _invariant_audit_node)
    graph.add_node("final_invariant_audit", _final_invariant_audit_node)
    graph.add_node("blocked", _blocked_node)

    graph.set_entry_point(ENTRY_POINT)
    for edge in DIRECT_EDGE_SPECS:
        graph.add_edge(edge.source, edge.target)
    routers = _route_functions()
    for route in CONDITIONAL_ROUTE_SPECS:
        graph.add_conditional_edges(route.source, routers[route.router], dict(route.routes))
    for edge in TERMINAL_EDGE_SPECS:
        graph.add_edge(edge.source, END)
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
    )


def _route_functions() -> dict[str, RouteFn]:
    return {
        "_route_after_coverage_critic": _route_after_coverage_critic,
        "_route_after_analysis_repair_router": _route_after_analysis_repair_router,
        "_route_after_evidence_sufficiency": _route_after_evidence_sufficiency,
        "_route_after_authoring_planner": _route_after_authoring_planner,
        "_route_after_revision_router": _route_after_revision_router,
        "_route_after_text_trace_builder": _route_after_text_trace_builder,
        "_route_after_local_text_repair": _route_after_local_text_repair,
        "_route_after_packet_binding_repair": _route_after_packet_binding_repair,
        "_route_after_figure_planner": _route_after_figure_planner,
        "_route_after_invariant_audit": _route_after_invariant_audit,
        "_route_after_rendering": _route_after_rendering,
        "_route_after_final_invariant_audit": _route_after_final_invariant_audit,
    }
