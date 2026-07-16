from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from code2paper.agentic.contracts import StageToolSpec
from code2paper.agentic.graph_catalog_models import (
    AgenticGraphCatalog,
    AgenticGraphConditionalRoute,
    AgenticGraphEdge,
    AgenticGraphGate,
    AgenticGraphNode,
)
from code2paper.agentic.graph_catalog_nodes import control_nodes
from code2paper.agentic.graph_catalog_routes import conditional_routes, evidence_gates
from code2paper.agentic.graph_topology import (
    DIRECT_EDGE_SPECS,
    STAGE_NODE_NAMES,
    TERMINAL_EDGE_SPECS,
    TERMINAL_NODE_NAMES,
    DirectEdgeSpec,
)
from code2paper.agentic.tools import Code2PaperStageTool, canonical_stage_tool_specs


def build_graph_catalog(
    registry: Mapping[str, Code2PaperStageTool] | None = None,
) -> AgenticGraphCatalog:
    """Build a JSON-safe graph topology catalog without importing LangGraph."""

    specs = _stage_specs(registry)
    return AgenticGraphCatalog(
        terminal_nodes=list(TERMINAL_NODE_NAMES),
        nodes=[
            *[_stage_node(specs[stage]) for stage in STAGE_NODE_NAMES],
            *control_nodes(),
        ],
        edges=[
            *[_direct_edge(edge) for edge in DIRECT_EDGE_SPECS],
            *[_direct_edge(edge) for edge in TERMINAL_EDGE_SPECS],
        ],
        conditional_routes=conditional_routes(),
        evidence_gates=evidence_gates(),
        loop_limits={
            "retrieval": "state.max_retrieval_rounds",
            "evidence_revision": "state.max_evidence_revision_rounds",
            "authoring_revision": "state.max_authoring_revision_rounds",
            "figure_revision": "state.max_figure_revision_rounds",
            "semantic_verifier": "state.max_semantic_verifier_calls",
        },
    )


def write_graph_catalog(path: str | Path, catalog: AgenticGraphCatalog) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_graph_catalog(path: str | Path) -> AgenticGraphCatalog:
    return AgenticGraphCatalog.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _stage_specs(registry: Mapping[str, Code2PaperStageTool] | None) -> dict[str, StageToolSpec]:
    if registry is None:
        return {spec.stage: spec for spec in canonical_stage_tool_specs()}
    return {stage: tool.spec for stage, tool in registry.items()}


def _stage_node(spec: StageToolSpec) -> AgenticGraphNode:
    return AgenticGraphNode(
        name=spec.stage,
        kind="stage",
        stage=spec.stage,
        tool_name=spec.name,
        description=spec.description,
        input_artifacts=spec.input_artifacts,
        output_artifacts=spec.output_artifacts,
        evidence_policy=spec.evidence_policy,
        allow_model_decision=spec.allow_model_decision,
        hard_gate=spec.hard_gate,
    )


def _direct_edge(edge: DirectEdgeSpec) -> AgenticGraphEdge:
    return AgenticGraphEdge(source=edge.source, target=edge.target, rationale=edge.rationale)
