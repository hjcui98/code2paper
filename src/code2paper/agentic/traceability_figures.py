from __future__ import annotations

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.traceability_artifacts import artifact_json, as_list, as_string_list
from code2paper.agentic.traceability_models import TraceabilityLedgerEntry


def figure_entries(state: AgenticRunState) -> list[TraceabilityLedgerEntry]:
    entries: list[TraceabilityLedgerEntry] = []
    scene = artifact_json(state, "figure_scene")
    if scene:
        for node in as_list(scene.get("nodes")):
            if not isinstance(node, dict) or not str(node.get("element_id") or ""): continue
            entries.append(TraceabilityLedgerEntry(
                entry_id=f"figure_node:{node['element_id']}", kind="figure_node", source_artifact="figure_scene",
                claim_ids=as_string_list(node.get("claim_ids")), evidence_ids=as_string_list(node.get("direct_evidence_ids")),
            ))
        for edge in as_list(scene.get("edges")):
            if not isinstance(edge, dict) or not str(edge.get("element_id") or ""): continue
            entries.append(TraceabilityLedgerEntry(
                entry_id=f"figure_edge:{edge['element_id']}", kind="figure_edge", source_artifact="figure_scene",
                evidence_ids=as_string_list(edge.get("direct_evidence_ids")), notes=[f"relation_id:{edge.get('relation_id', '')}"],
            ))
        return entries
    plan = artifact_json(state, "figure_plan")
    for node in as_list(plan.get("nodes")):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "")
        if not node_id:
            continue
        entries.append(
            TraceabilityLedgerEntry(
                entry_id=f"figure_node:{node_id}",
                kind="figure_node",
                source_artifact="figure_plan",
                claim_ids=as_string_list(node.get("claim_ids")),
                evidence_ids=as_string_list(node.get("evidence_ids")),
            )
        )
    for edge in as_list(plan.get("edges")):
        if not isinstance(edge, dict):
            continue
        edge_id = str(edge.get("edge_id") or "")
        if not edge_id:
            continue
        entries.append(
            TraceabilityLedgerEntry(
                entry_id=f"figure_edge:{edge_id}",
                kind="figure_edge",
                source_artifact="figure_plan",
                evidence_ids=as_string_list(edge.get("evidence_ids")),
            )
        )
    return entries
