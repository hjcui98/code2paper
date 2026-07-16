from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_relations_v2 import EvidenceRelationSetV2
from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2
from code2paper.agentic.figure_scene import FigureSceneGraph


class FigureRelationValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2.0"
    status: str
    relation_set_digest: str
    scene_digest: str
    checked_edges: int = 0
    supported_edges: int = 0
    failures: list[str] = Field(default_factory=list)
    hard_gate_passed: bool


def validate_figure_relations(
    scene: FigureSceneGraph,
    relations: EvidenceRelationSetV2,
    evidence: EvidenceSnapshotV2,
) -> FigureRelationValidation:
    known_evidence = {span.evidence_id for span in evidence.spans if span.status == "valid"}
    supported = {item.relation_id: item for item in relations.relations if item.support_status == "supported"}
    node_ids = {node.element_id for node in scene.nodes}
    failures: list[str] = []
    for edge in scene.edges:
        relation = supported.get(edge.relation_id)
        if relation is None:
            failures.append(f"unknown_or_unsupported_relation:{edge.element_id}")
            continue
        if edge.source_element_id not in node_ids or edge.target_element_id not in node_ids:
            failures.append(f"unknown_edge_endpoint:{edge.element_id}")
        if not edge.direct_evidence_ids or any(item not in known_evidence for item in edge.direct_evidence_ids):
            failures.append(f"missing_direct_relation_evidence:{edge.element_id}")
        if set(edge.direct_evidence_ids) - set(relation.direct_evidence_ids):
            failures.append(f"edge_evidence_not_from_relation:{edge.element_id}")
        if edge.label != relation.semantic_statement:
            failures.append(f"edge_label_outside_relation_boundary:{edge.element_id}")
    passed = not failures and scene.hard_gate_passed
    return FigureRelationValidation(
        status="passed" if passed else "failed", relation_set_digest=relations.content_digest,
        scene_digest=scene.content_digest, checked_edges=len(scene.edges),
        supported_edges=len(scene.edges) - len({item.split(":")[-1] for item in failures}),
        failures=failures, hard_gate_passed=passed,
    )


def write_figure_relation_validation(path: str | Path, report: FigureRelationValidation) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8"); return output
