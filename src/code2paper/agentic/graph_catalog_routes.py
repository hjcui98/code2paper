from __future__ import annotations

from code2paper.agentic.graph_catalog_models import AgenticGraphConditionalRoute, AgenticGraphGate
from code2paper.agentic.graph_topology import (
    CONDITIONAL_ROUTE_SPECS,
    EVIDENCE_GATE_SPECS,
    ConditionalRouteSpec,
    EvidenceGateSpec,
)


def conditional_routes() -> list[AgenticGraphConditionalRoute]:
    return [_conditional_route(spec) for spec in CONDITIONAL_ROUTE_SPECS]


def evidence_gates() -> list[AgenticGraphGate]:
    return [_evidence_gate(spec) for spec in EVIDENCE_GATE_SPECS]


def _conditional_route(spec: ConditionalRouteSpec) -> AgenticGraphConditionalRoute:
    return AgenticGraphConditionalRoute(
        source=spec.source,
        router=spec.router,
        routes=dict(spec.routes),
        safety_note=spec.safety_note,
    )


def _evidence_gate(spec: EvidenceGateSpec) -> AgenticGraphGate:
    return AgenticGraphGate(
        name=spec.name,
        node=spec.node,
        required_artifacts=list(spec.required_artifacts),
        rationale=spec.rationale,
    )
