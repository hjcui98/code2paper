from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_relations_v2 import EvidenceRelationSetV2
from code2paper.agentic.figure_planner import EvidenceBackedFigurePlan


class SceneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FigureSceneNode(SceneModel):
    element_id: str
    stage_id: str
    label: str
    kind: str = "stage"
    claim_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    visible_text_boundary: str


class FigureSceneEdge(SceneModel):
    element_id: str
    relation_id: str
    source_element_id: str
    target_element_id: str
    label: str
    direct_evidence_ids: list[str] = Field(default_factory=list)
    visible_text_boundary: str


class FigureSceneAnnotation(SceneModel):
    element_id: str
    label: str
    claim_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    visible_text_boundary: str


class FigureSceneGraph(SceneModel):
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p2"
    repo_snapshot_id: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    relation_set_digest: str
    layout: Literal["left_to_right", "top_to_bottom"] = "left_to_right"
    nodes: list[FigureSceneNode] = Field(default_factory=list)
    edges: list[FigureSceneEdge] = Field(default_factory=list)
    annotations: list[FigureSceneAnnotation] = Field(default_factory=list)
    groups: list[dict[str, str]] = Field(default_factory=list)
    omitted_elements: list[dict[str, str]] = Field(default_factory=list)
    content_digest: str
    hard_gate_passed: bool = True


def build_figure_scene_graph(
    plan: EvidenceBackedFigurePlan,
    relations: EvidenceRelationSetV2,
) -> FigureSceneGraph:
    nodes = [
        FigureSceneNode(
            element_id=f"scene-{node.node_id}", stage_id=node.stage_id, label=node.label,
            kind=node.kind, claim_ids=node.claim_ids, direct_evidence_ids=node.evidence_ids,
            visible_text_boundary=node.label,
        ) for node in plan.nodes
    ]
    by_stage = {node.stage_id: node.element_id for node in nodes}
    edges: list[FigureSceneEdge] = []
    omitted: list[dict[str, str]] = []
    for relation in relations.relations:
        source = by_stage.get(relation.source_entity_id)
        target = by_stage.get(relation.target_entity_id)
        if relation.support_status != "supported" or not relation.direct_evidence_ids or not source or not target:
            omitted.append({"relation_id": relation.relation_id, "reason": "unsupported_or_endpoint_not_visible"})
            continue
        edges.append(
            FigureSceneEdge(
                element_id=f"scene-edge-{relation.relation_id}", relation_id=relation.relation_id,
                source_element_id=source, target_element_id=target,
                label=relation.semantic_statement, direct_evidence_ids=relation.direct_evidence_ids,
                visible_text_boundary=relation.semantic_statement,
            )
        )
    return FigureSceneGraph(
        repo_snapshot_id=relations.repo_snapshot_id,
        evidence_snapshot_id=relations.evidence_snapshot_id,
        evidence_snapshot_digest=relations.evidence_snapshot_digest,
        relation_set_digest=relations.content_digest,
        nodes=nodes, edges=edges, omitted_elements=omitted,
        content_digest=figure_scene_content_digest(
            nodes=nodes, edges=edges, annotations=[], groups=[], omitted_elements=omitted, layout="left_to_right"
        ), hard_gate_passed=bool(nodes),
    )


def write_figure_scene_graph(path: str | Path, scene: FigureSceneGraph) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(scene.model_dump_json(indent=2), encoding="utf-8"); return output


def load_figure_scene_graph(path: str | Path) -> FigureSceneGraph:
    return FigureSceneGraph.model_validate_json(Path(path).read_text(encoding="utf-8"))


def figure_scene_content_digest(*, nodes, edges, annotations, groups, omitted_elements, layout: str) -> str:
    def dump(items):
        return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in items]
    return _digest({
        "nodes": dump(nodes), "edges": dump(edges), "annotations": dump(annotations),
        "groups": groups, "omitted_elements": omitted_elements, "layout": layout,
    })


def _digest(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()
