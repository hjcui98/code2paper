from __future__ import annotations

from typing import Any

from code2paper.agentic.readiness_io import list_value, string_list


def decision_trace_plan_mismatch(
    *,
    trace: dict[str, Any],
    plan: dict[str, Any],
    expected_node: str,
    signature_kind: str,
) -> str:
    if str(trace.get("node") or "") != expected_node:
        return f"{signature_kind} decision trace node is not {expected_node}"
    final_decision = trace.get("final_decision") if isinstance(trace.get("final_decision"), dict) else {}
    if not final_decision:
        return f"{signature_kind} decision trace final_decision is missing"
    if _plan_signature(final_decision, signature_kind) != _plan_signature(plan, signature_kind):
        return f"{signature_kind} decision trace final_decision does not match the current plan artifact"
    return ""


def _plan_signature(plan: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "authoring_plan":
        return {
            "hard_gate_passed": bool(plan.get("hard_gate_passed")),
            "sections": [
                {
                    "section_id": str(section.get("section_id") or ""),
                    "claim_ids": string_list(section.get("claim_ids")),
                    "evidence_ids": string_list(section.get("evidence_ids")),
                    "caveat_required": bool(section.get("caveat_required")),
                }
                for section in list_value(plan.get("sections"))
                if isinstance(section, dict)
            ],
        }
    if kind == "figure_plan":
        return {
            "hard_gate_passed": bool(plan.get("hard_gate_passed")),
            "nodes": [
                {
                    "node_id": str(node.get("node_id") or ""),
                    "stage_id": str(node.get("stage_id") or ""),
                    "claim_ids": string_list(node.get("claim_ids")),
                    "evidence_ids": string_list(node.get("evidence_ids")),
                }
                for node in list_value(plan.get("nodes"))
                if isinstance(node, dict)
            ],
            "edges": [
                {
                    "edge_id": str(edge.get("edge_id") or ""),
                    "source_node_id": str(edge.get("source_node_id") or ""),
                    "target_node_id": str(edge.get("target_node_id") or ""),
                    "evidence_ids": string_list(edge.get("evidence_ids")),
                }
                for edge in list_value(plan.get("edges"))
                if isinstance(edge, dict)
            ],
        }
    return {}
