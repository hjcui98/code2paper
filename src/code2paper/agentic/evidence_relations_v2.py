from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2, is_direct_code_span
from code2paper.core.schemas import MethodEvidence


class RelationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRelationV2(RelationModel):
    relation_id: str
    relation_type: Literal[
        "data_flow", "call_flow", "control_flow", "configuration_activates",
        "consumes", "produces", "wraps", "delegates", "transforms",
        "conditional_branch", "temporal_stage_order",
    ]
    source_entity_id: str
    target_entity_id: str
    semantic_statement: str
    conditions: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    support_status: Literal["supported", "unsupported"] = "supported"
    rationale: str = ""


class EvidenceRelationSetV2(RelationModel):
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p2"
    repo_snapshot_id: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    relations: list[EvidenceRelationV2] = Field(default_factory=list)
    content_digest: str


def build_evidence_relations_v2(
    method_evidence: MethodEvidence,
    evidence_snapshot: EvidenceSnapshotV2,
    *,
    code_graph: dict[str, Any] | None = None,
) -> EvidenceRelationSetV2:
    """Build only relations with evidence that directly states the relation."""

    spans = {span.evidence_id: span for span in evidence_snapshot.spans if is_direct_code_span(span)}
    stage_evidence = {
        stage.stage_id: {
            evidence_id
            for mechanism in stage.mechanisms
            for evidence_id in mechanism.evidence_ids
            if evidence_id in spans
        }
        for stage in method_evidence.stages
    }
    relations: list[EvidenceRelationV2] = []

    config_stages = [
        stage.stage_id for stage in method_evidence.stages
        if any(spans[eid].source_type == "config" for eid in stage_evidence.get(stage.stage_id, set()))
    ]
    source_stages = [
        stage.stage_id for stage in method_evidence.stages
        if any(spans[eid].source_type == "source" for eid in stage_evidence.get(stage.stage_id, set()))
    ]
    shell_spans = [
        span for span in spans.values()
        if span.source_type in {"bash", "shell"} and ".py" in span.exact_excerpt and "--config" in span.exact_excerpt
    ]
    if len(config_stages) == 1 and len(source_stages) == 1 and shell_spans:
        relations.append(
            EvidenceRelationV2(
                relation_id="R1",
                relation_type="configuration_activates",
                source_entity_id=config_stages[0],
                target_entity_id=source_stages[0],
                semantic_statement="The shell entrypoint passes a configuration to the training program.",
                direct_evidence_ids=[shell_spans[0].evidence_id],
                rationale="The exact shell excerpt contains both the Python entrypoint and --config argument.",
            )
        )

    graph = code_graph or {}
    for edge in graph.get("edges", []) if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        evidence_ids = [str(item) for item in edge.get("evidence_refs", []) if str(item) in spans]
        source = str(edge.get("source_entity_id") or edge.get("from") or "")
        target = str(edge.get("target_entity_id") or edge.get("to") or "")
        if not source or not target or not evidence_ids:
            continue
        relations.append(
            EvidenceRelationV2(
                relation_id=f"R{len(relations) + 1}",
                relation_type=_relation_type(str(edge.get("relation_type") or edge.get("label") or "")),
                source_entity_id=source,
                target_entity_id=target,
                semantic_statement=str(edge.get("semantic_statement") or edge.get("label") or "direct code relation"),
                direct_evidence_ids=evidence_ids,
                rationale="Code graph edge carries explicit EvidenceSpanV2 references.",
            )
        )

    payload = [relation.model_dump(mode="json") for relation in relations]
    return EvidenceRelationSetV2(
        repo_snapshot_id=evidence_snapshot.repo_snapshot_id,
        evidence_snapshot_id=evidence_snapshot.evidence_snapshot_id,
        evidence_snapshot_digest=evidence_snapshot.content_digest,
        relations=relations,
        content_digest=_digest(payload),
    )


def write_evidence_relations_v2(path: str | Path, relations: EvidenceRelationSetV2) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(relations.model_dump_json(indent=2), encoding="utf-8")
    return output


def load_evidence_relations_v2(path: str | Path) -> EvidenceRelationSetV2:
    return EvidenceRelationSetV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _relation_type(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    allowed = {item for item in EvidenceRelationV2.model_fields["relation_type"].annotation.__args__}
    return normalized if normalized in allowed else "data_flow"


def _digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()
