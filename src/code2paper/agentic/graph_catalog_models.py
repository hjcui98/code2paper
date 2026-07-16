from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import EvidencePolicy
from code2paper.agentic.graph_topology import ENTRY_POINT


class AgenticGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    stage: str = ""
    tool_name: str = ""
    description: str = ""
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    evidence_policy: EvidencePolicy = EvidencePolicy.NONE
    allow_model_decision: bool = False
    hard_gate: bool = False


class AgenticGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    edge_type: str = "direct"
    rationale: str = ""


class AgenticGraphConditionalRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    router: str
    routes: dict[str, str]
    safety_note: str = ""


class AgenticGraphGate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    node: str
    required_artifacts: list[str] = Field(default_factory=list)
    blocks_to: str = "blocked"
    rationale: str = ""


class AgenticGraphCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-graph-catalog"
    entry_point: str = ENTRY_POINT
    terminal_nodes: list[str] = Field(default_factory=list)
    nodes: list[AgenticGraphNode] = Field(default_factory=list)
    edges: list[AgenticGraphEdge] = Field(default_factory=list)
    conditional_routes: list[AgenticGraphConditionalRoute] = Field(default_factory=list)
    evidence_gates: list[AgenticGraphGate] = Field(default_factory=list)
    loop_limits: dict[str, str] = Field(default_factory=dict)
