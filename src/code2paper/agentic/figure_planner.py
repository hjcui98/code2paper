from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.claim_verifier import ClaimVerificationReport, build_claim_verification_report
from code2paper.agentic.decision_core import AgenticDecisionPrompt, AgenticDecisionTrace, DecisionProvider, _call_provider_for_trace
from code2paper.agentic.decision_policy import hard_rule_texts
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision
from code2paper.agentic.figure_attention import figure_evidence_attention
from code2paper.agentic.evidence_relations_v2 import EvidenceRelationSetV2
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, SupportStatus


class FigurePlanNode(BaseModel):
    """One visual element that may appear in the method overview figure."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    label: str
    kind: str = "stage"
    stage_id: str = ""
    mechanism_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class FigurePlanEdge(BaseModel):
    """One evidence-backed relation between figure nodes."""

    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_node_id: str
    target_node_id: str
    label: str = "then"
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class EvidenceBackedFigurePlan(BaseModel):
    """Auditable plan for method overview figures."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "evidence-backed-figure-plan"
    nodes: list[FigurePlanNode] = Field(default_factory=list)
    edges: list[FigurePlanEdge] = Field(default_factory=list)
    omitted_mechanism_ids: list[str] = Field(default_factory=list)
    omitted_claim_ids: list[str] = Field(default_factory=list)
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)


class FigurePlanNodeProposal(BaseModel):
    """Model proposal for one visual node, before evidence safety overlay."""

    model_config = ConfigDict(extra="ignore")

    node_id: str = ""
    stage_id: str = ""
    label: str = ""
    kind: str = "stage"
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class FigurePlanEdgeProposal(BaseModel):
    """Model proposal for one visual edge, before evidence safety overlay."""

    model_config = ConfigDict(extra="ignore")

    edge_id: str = ""
    source_node_id: str = ""
    target_node_id: str = ""
    label: str = "then"
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class FigurePlanProposal(BaseModel):
    """Model proposal for method figure structure, before evidence safety overlay."""

    model_config = ConfigDict(extra="ignore")

    rationale: str = ""
    nodes: list[FigurePlanNodeProposal] = Field(default_factory=list)
    edges: list[FigurePlanEdgeProposal] = Field(default_factory=list)


def build_evidence_backed_figure_plan(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    claim_verification: ClaimVerificationReport | None = None,
    evidence_relations: EvidenceRelationSetV2 | None = None,
) -> EvidenceBackedFigurePlan:
    """Select only evidence-backed method elements for the overview figure."""

    verification = claim_verification or build_claim_verification_report(method_evidence, claim_map)
    verified_claims = {claim.claim_id: claim for claim in verification.claims}
    claim_ids_by_mechanism = _claim_ids_by_mechanism(claim_map, verified_claims)
    known_evidence_ids = _known_evidence_ids(method_evidence)

    nodes: list[FigurePlanNode] = []
    omitted_mechanisms: list[str] = []
    for stage in method_evidence.stages:
        stage_evidence: list[str] = []
        mechanism_ids: list[str] = []
        claim_ids: list[str] = []
        for mechanism in stage.mechanisms:
            evidence_ids = _unique(mechanism.evidence_ids)
            if mechanism.support_status == SupportStatus.UNSUPPORTED or not evidence_ids:
                omitted_mechanisms.append(mechanism.mechanism_id)
                continue
            if any(evidence_id not in known_evidence_ids for evidence_id in evidence_ids):
                omitted_mechanisms.append(mechanism.mechanism_id)
                continue
            stage_evidence.extend(evidence_ids)
            mechanism_ids.append(mechanism.mechanism_id)
            claim_ids.extend(claim_ids_by_mechanism.get(mechanism.mechanism_id, []))
        if stage_evidence:
            nodes.append(
                FigurePlanNode(
                    node_id=f"N{len(nodes) + 1}",
                    label=_short_label(stage.name or stage.purpose or stage.stage_id),
                    stage_id=stage.stage_id,
                    mechanism_ids=_unique(mechanism_ids),
                    claim_ids=_unique(claim_ids),
                    evidence_ids=_unique(stage_evidence),
                    rationale="Stage has supported mechanism evidence in frozen MethodEvidence.",
                )
            )

    node_by_stage = {node.stage_id: node for node in nodes}
    edges: list[FigurePlanEdge] = []
    for relation in evidence_relations.relations if evidence_relations else []:
        source = node_by_stage.get(relation.source_entity_id)
        target = node_by_stage.get(relation.target_entity_id)
        if relation.support_status != "supported" or not relation.direct_evidence_ids or not source or not target:
            continue
        edges.append(FigurePlanEdge(
            edge_id=f"FE{len(edges) + 1}", source_node_id=source.node_id, target_node_id=target.node_id,
            label=relation.semantic_statement, evidence_ids=relation.direct_evidence_ids,
            rationale=f"Direct EvidenceRelationV2 {relation.relation_id}.",
        ))

    omitted_claims = [
        claim.claim_id
        for claim in verification.claims
        if claim.support_status == SupportStatus.UNSUPPORTED or claim.recommended_action != "allow_in_prose"
    ]
    hard_gate_passed = bool(nodes) and all(node.evidence_ids for node in nodes) and all(edge.evidence_ids for edge in edges)
    actions = _recommended_actions(nodes=nodes, edges=edges, omitted_claims=omitted_claims, omitted_mechanisms=omitted_mechanisms)
    return EvidenceBackedFigurePlan(
        nodes=nodes,
        edges=edges,
        omitted_mechanism_ids=_unique(omitted_mechanisms),
        omitted_claim_ids=_unique(omitted_claims),
        hard_gate_passed=hard_gate_passed,
        recommended_actions=actions,
    )


def figure_plan_trace(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    claim_verification: ClaimVerificationReport | None = None,
    author_intent_summary: AuthorIntentSummary | None = None,
    decision_provider: DecisionProvider | None = None,
    evidence_relations: EvidenceRelationSetV2 | None = None,
) -> tuple[EvidenceBackedFigurePlan, AgenticDecisionTrace]:
    """Build a safe figure plan plus an auditable model/fallback trace."""

    verification = claim_verification or build_claim_verification_report(method_evidence, claim_map)
    fallback = build_evidence_backed_figure_plan(
        method_evidence=method_evidence,
        claim_map=claim_map,
        claim_verification=verification,
        evidence_relations=evidence_relations,
    )
    prompt = AgenticDecisionPrompt(
        node="figure_planner",
        objective=(
            "Propose a concise method overview figure from author intent, verified claims, and frozen code evidence. "
            "The final figure plan may only contain supported stage nodes, verified claim ids, and frozen evidence ids."
        ),
        hard_rules=_figure_plan_rules(),
        inputs={
            "method_evidence": method_evidence.model_dump(mode="json"),
            "claim_map": claim_map.model_dump(mode="json"),
            "claim_verification": verification.model_dump(mode="json"),
            "author_intent_summary": author_intent_summary.model_dump(mode="json") if author_intent_summary else None,
            "figure_evidence_attention": figure_evidence_attention(fallback),
            "allowed_stage_ids": [node.stage_id for node in fallback.nodes],
            "allowed_node_ids": [node.node_id for node in fallback.nodes],
            "allowed_claim_ids": _unique([claim_id for node in fallback.nodes for claim_id in node.claim_ids]),
            "allowed_evidence_ids": _unique([evidence_id for node in fallback.nodes for evidence_id in node.evidence_ids]),
            "stage_tool_guidance": stage_tool_guidance_for_decision(["rendering"]),
        },
        fallback_decision=fallback.model_dump(mode="json"),
    )
    if decision_provider is None:
        return fallback, _trace(
            prompt=prompt,
            provider_status="deterministic_fallback",
            final_plan=fallback,
            safety_notes=["No decision provider was configured; deterministic figure plan was used."],
        )
    provider_status, provider_payload, proposal = _call_provider_for_trace(decision_provider, prompt, FigurePlanProposal)
    if not isinstance(proposal, FigurePlanProposal):
        return fallback, _trace(
            prompt=prompt,
            provider_status=provider_status,
            provider_payload=provider_payload,
            final_plan=fallback,
            safety_notes=["Provider proposal was unavailable or invalid; deterministic figure plan was used."],
        )
    final_plan, safety_notes = _merge_figure_plan(fallback=fallback, proposal=proposal)
    return final_plan, _trace(
        prompt=prompt,
        provider_status=provider_status,
        provider_payload=provider_payload,
        parsed_proposal=proposal,
        final_plan=final_plan,
        safety_notes=safety_notes,
    )


def write_figure_plan(path: str | Path, plan: EvidenceBackedFigurePlan) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return output


def load_figure_plan(path: str | Path) -> EvidenceBackedFigurePlan:
    return EvidenceBackedFigurePlan.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def figure_plan_brief(plan: EvidenceBackedFigurePlan) -> str:
    """Render a compact natural-language contract for figure-generation prompts."""

    if not plan.nodes:
        return ""
    lines = [
        "Evidence-backed visual contract:",
        "- Draw only the nodes and transitions listed here; omit unsupported or unverified claims.",
    ]
    for node in plan.nodes:
        evidence = ", ".join(node.evidence_ids[:5])
        claims = ", ".join(node.claim_ids[:5]) or "none"
        lines.append(f"- Node {node.node_id}: {node.label}; evidence={evidence}; claims={claims}.")
    for edge in plan.edges:
        evidence = ", ".join(edge.evidence_ids[:5])
        lines.append(f"- Edge {edge.edge_id}: {edge.source_node_id} -> {edge.target_node_id}; evidence={evidence}.")
    if plan.omitted_claim_ids:
        lines.append("- Omit unverified claim ids: " + ", ".join(plan.omitted_claim_ids[:12]) + ".")
    return "\n".join(lines)


def _merge_figure_plan(
    *,
    fallback: EvidenceBackedFigurePlan,
    proposal: FigurePlanProposal,
) -> tuple[EvidenceBackedFigurePlan, list[str]]:
    fallback_by_stage = {node.stage_id: node for node in fallback.nodes if node.stage_id}
    fallback_by_node = {node.node_id: node for node in fallback.nodes}
    final_nodes: list[FigurePlanNode] = []
    covered_fallback_node_ids: set[str] = set()
    proposal_node_to_final: dict[str, str] = {}
    dropped_nodes = 0
    rewritten_node_evidence = False
    rewritten_node_claims = False

    for proposed in proposal.nodes:
        fallback_node = fallback_by_stage.get(proposed.stage_id) or fallback_by_node.get(proposed.node_id)
        if fallback_node is None:
            dropped_nodes += 1
            continue
        if fallback_node.node_id in covered_fallback_node_ids:
            dropped_nodes += 1
            continue
        evidence_ids = [item for item in _unique(proposed.evidence_ids) if item in set(fallback_node.evidence_ids)]
        claim_ids = [item for item in _unique(proposed.claim_ids) if item in set(fallback_node.claim_ids)]
        if evidence_ids != _unique(proposed.evidence_ids):
            rewritten_node_evidence = True
        if claim_ids != _unique(proposed.claim_ids):
            rewritten_node_claims = True
        if not evidence_ids:
            evidence_ids = fallback_node.evidence_ids
        if not claim_ids and fallback_node.claim_ids:
            claim_ids = fallback_node.claim_ids
        proposed_label = _short_label(proposed.label or fallback_node.label)
        safe_label = proposed_label if _label_within_boundary(proposed_label, fallback_node.label) else fallback_node.label
        if safe_label != proposed_label:
            rewritten_node_claims = True
        final_node = FigurePlanNode(
            node_id=fallback_node.node_id,
            label=safe_label,
            kind=_short_label(proposed.kind or fallback_node.kind, limit=32),
            stage_id=fallback_node.stage_id,
            mechanism_ids=fallback_node.mechanism_ids,
            claim_ids=claim_ids,
            evidence_ids=evidence_ids,
            rationale=proposed.rationale.strip() or fallback_node.rationale,
        )
        final_nodes.append(final_node)
        covered_fallback_node_ids.add(fallback_node.node_id)
        if proposed.node_id:
            proposal_node_to_final[proposed.node_id] = fallback_node.node_id
        if proposed.stage_id:
            proposal_node_to_final[proposed.stage_id] = fallback_node.node_id

    appended_nodes: list[str] = []
    for fallback_node in fallback.nodes:
        if fallback_node.node_id in covered_fallback_node_ids:
            continue
        appended_nodes.append(fallback_node.node_id)
        final_nodes.append(fallback_node)
        covered_fallback_node_ids.add(fallback_node.node_id)

    final_node_ids = {node.node_id for node in final_nodes}
    final_node_by_id = {node.node_id: node for node in final_nodes}
    fallback_edges_by_pair = {(edge.source_node_id, edge.target_node_id): edge for edge in fallback.edges}
    final_edges: list[FigurePlanEdge] = []
    covered_edge_pairs: set[tuple[str, str]] = set()
    dropped_edges = 0
    rewritten_edge_evidence = False

    for proposed in proposal.edges:
        source = _normalize_node_ref(proposed.source_node_id, proposal_node_to_final, final_node_ids)
        target = _normalize_node_ref(proposed.target_node_id, proposal_node_to_final, final_node_ids)
        if not source or not target or source == target:
            dropped_edges += 1
            continue
        fallback_edge = fallback_edges_by_pair.get((source, target))
        if fallback_edge is None:
            dropped_edges += 1
            continue
        allowed_evidence = list(fallback_edge.evidence_ids)
        evidence_ids = [item for item in _unique(proposed.evidence_ids) if item in set(allowed_evidence)]
        if evidence_ids != _unique(proposed.evidence_ids):
            rewritten_edge_evidence = True
        if not evidence_ids:
            evidence_ids = fallback_edge.evidence_ids
        if not evidence_ids:
            dropped_edges += 1
            continue
        covered_edge_pairs.add((source, target))
        final_edges.append(
            FigurePlanEdge(
                edge_id=f"FE{len(final_edges) + 1}",
                source_node_id=source,
                target_node_id=target,
                label=fallback_edge.label,
                evidence_ids=evidence_ids,
                rationale=proposed.rationale.strip()
                or fallback_edge.rationale,
            )
        )

    appended_edges: list[str] = []
    for fallback_edge in fallback.edges:
        pair = (fallback_edge.source_node_id, fallback_edge.target_node_id)
        if pair in covered_edge_pairs or fallback_edge.source_node_id not in final_node_ids or fallback_edge.target_node_id not in final_node_ids:
            continue
        appended_edges.append(fallback_edge.edge_id)
        final_edges.append(fallback_edge.model_copy(update={"edge_id": f"FE{len(final_edges) + 1}"}))
        covered_edge_pairs.add(pair)

    hard_gate_passed = bool(final_nodes) and all(node.evidence_ids for node in final_nodes) and all(
        edge.evidence_ids for edge in final_edges
    )
    final_plan = EvidenceBackedFigurePlan(
        nodes=final_nodes,
        edges=final_edges,
        omitted_mechanism_ids=fallback.omitted_mechanism_ids,
        omitted_claim_ids=fallback.omitted_claim_ids,
        hard_gate_passed=hard_gate_passed,
        recommended_actions=_recommended_actions(
            nodes=final_nodes,
            edges=final_edges,
            omitted_claims=fallback.omitted_claim_ids,
            omitted_mechanisms=fallback.omitted_mechanism_ids,
        ),
    )
    notes = ["Model proposal was merged through figure-plan evidence safety rules."]
    if dropped_nodes:
        notes.append(f"Dropped {dropped_nodes} proposed node(s) outside supported frozen evidence stages.")
    if rewritten_node_evidence:
        notes.append("Rewrote proposed node evidence ids to frozen ids allowed by the fallback figure plan.")
    if rewritten_node_claims:
        notes.append("Rewrote proposed node claim ids to verified ids allowed by the fallback figure plan.")
    if appended_nodes:
        notes.append("Appended fallback figure nodes omitted by the proposal: " + ", ".join(appended_nodes) + ".")
    if dropped_edges:
        notes.append(f"Dropped {dropped_edges} proposed edge(s) with unknown endpoints or no supported evidence.")
    if rewritten_edge_evidence:
        notes.append("Rewrote proposed edge evidence ids to frozen ids allowed by connected nodes.")
    if appended_edges:
        notes.append("Appended fallback figure edges omitted by the proposal: " + ", ".join(appended_edges) + ".")
    return final_plan, notes


def _trace(
    *,
    prompt: AgenticDecisionPrompt,
    provider_status: str,
    final_plan: EvidenceBackedFigurePlan,
    provider_payload: dict[str, Any] | None = None,
    parsed_proposal: FigurePlanProposal | None = None,
    safety_notes: list[str] | None = None,
) -> AgenticDecisionTrace:
    return AgenticDecisionTrace(
        node="figure_planner",
        provider_status=provider_status,
        prompt=prompt,
        provider_payload=provider_payload or {},
        parsed_proposal=parsed_proposal.model_dump(mode="json") if parsed_proposal else {},
        final_decision=final_plan.model_dump(mode="json"),
        safety_notes=safety_notes or [],
    )


def _figure_plan_rules() -> list[str]:
    return [
        *hard_rule_texts(),
        "Figure nodes may reorder or relabel supported method stages, but may not introduce unsupported stages.",
        "Every figure node and edge must carry frozen evidence ids from the supported fallback plan.",
        "Excluded and unsupported claims must remain outside method figures.",
    ]


def _normalize_node_ref(value: str, aliases: dict[str, str], final_node_ids: set[str]) -> str:
    text = str(value or "").strip()
    if text in final_node_ids:
        return text
    return aliases.get(text, "")


def _claim_ids_by_mechanism(
    claim_map: ClaimEvidenceMap,
    verified_claims: dict[str, object],
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for claim in claim_map.claims:
        verified = verified_claims.get(claim.claim_id)
        status = getattr(verified, "support_status", claim.support_status)
        action = getattr(verified, "recommended_action", "")
        if status == SupportStatus.UNSUPPORTED or action == "drop_or_retrieve_more_evidence":
            continue
        for mechanism_id in claim.mechanism_ids:
            result.setdefault(mechanism_id, []).append(claim.claim_id)
    return {key: _unique(values) for key, values in result.items()}


def _known_evidence_ids(method_evidence: MethodEvidence) -> set[str]:
    found: set[str] = set()
    _collect_evidence_ids(method_evidence.model_dump(mode="json"), found)
    return found


def _collect_evidence_ids(value: object, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "span_id"} and isinstance(item, str):
                found.add(item)
            elif key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids"} and isinstance(item, list):
                found.update(str(element) for element in item if str(element).strip())
            else:
                _collect_evidence_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_evidence_ids(item, found)


def _recommended_actions(
    *,
    nodes: list[FigurePlanNode],
    edges: list[FigurePlanEdge],
    omitted_claims: list[str],
    omitted_mechanisms: list[str],
) -> list[str]:
    actions: list[str] = []
    if not nodes:
        actions.append("block_figure_until_supported_mechanism_evidence_exists")
    if nodes and not edges:
        actions.append("draw_single_evidence_backed_module_without_pipeline_arrows")
    if omitted_claims:
        actions.append("omit_unverified_claims_from_figure")
    if omitted_mechanisms:
        actions.append("omit_unsupported_or_evidence_missing_mechanisms")
    if not actions:
        actions.append("figure_plan_ready_for_evidence_backed_rendering")
    return actions


def _short_label(value: str, *, limit: int = 52) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "."


def _label_within_boundary(proposed: str, boundary: str) -> bool:
    def tokens(value: str) -> set[str]:
        return {item.lower() for item in value.replace("_", " ").split() if len(item) > 2}
    proposed_tokens = tokens(proposed)
    boundary_tokens = tokens(boundary)
    return bool(proposed_tokens) and proposed_tokens.issubset(boundary_tokens)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
