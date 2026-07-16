from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from code2paper.agentic.figure_planner import EvidenceBackedFigurePlan


def figure_evidence_attention(plan: EvidenceBackedFigurePlan) -> dict[str, Any]:
    return {
        "allowed_node_count": len(plan.nodes),
        "allowed_edge_count": len(plan.edges),
        "nodes": [
            {
                "node_id": node.node_id,
                "stage_id": node.stage_id,
                "label": node.label,
                "mechanism_ids": node.mechanism_ids,
                "claim_ids": node.claim_ids,
                "evidence_ids": node.evidence_ids,
            }
            for node in plan.nodes[:20]
        ],
        "edges": [
            {
                "edge_id": edge.edge_id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "evidence_ids": edge.evidence_ids,
            }
            for edge in plan.edges[:20]
        ],
        "omitted_mechanism_ids": plan.omitted_mechanism_ids[:20],
        "omitted_claim_ids": plan.omitted_claim_ids[:20],
    }
