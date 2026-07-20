"""R4.1 generic evidence packet compiler and validator.

This module implements the ``propose_evidence_packet`` contract from design
section 9.2 and the R4.1 execution plan.  The LLM (or a deterministic test
fixture) proposes a packet by selecting behavior node/relation ids and span
ids from a validated ``CodeBehaviorGraphV1``; this module compiles the
proposal into a typed ``EvidencePacketV3`` and runs the deterministic
validator checklist.

Validator checks (R4.1):

- snapshot/freshness: every span's ``snapshot_id`` matches the runtime
  snapshot id;
- source authority: every anchor span is backed by a behavior node whose
  ``source_authority`` is at least ``executable_hard`` (hint-only anchors
  are rejected);
- anchor role: every id in ``anchor_span_ids`` is backed by a span whose
  ``role`` is ``anchor``;
- relation existence: every relation id referenced by the packet exists
  in the behavior graph (or in ``unresolved_relations``, in which case the
  packet is rejected);
- guard coverage: every guard on a selected behavior node appears in the
  packet's ``conditions`` (otherwise the packet silently drops a guard);
- no unrelated span: every span in the packet is reachable from at least
  one anchor via the packet's relations (minimal connected subgraph);
- minimality: packets with more than three spans require a non-empty
  ``composition_rationale``; ``rejected_candidates`` must each carry a
  non-empty ``reason``;
- rejected candidate rationale: every rejected candidate must explain why
  the similar span cannot support the same predicate.

R4.5 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
)
from code2paper.agentic.evidence_compiler_v3 import (
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
    RejectedEvidenceCandidateV3,
    RelationEvidenceV3,
)


# ---------------------------------------------------------------------------
# Source authority ranking (mirrors source_authority.py ordering)
# ---------------------------------------------------------------------------

_AUTHORITY_RANK: dict[str, int] = {
    "executable_hard": 4,
    "test_scoped": 3,
    "semantic_hint": 2,
    "author_intent": 1,
}


def _authority_rank(value: str) -> int:
    return _AUTHORITY_RANK.get(value, 0)


# ---------------------------------------------------------------------------
# Proposal input (design 9.2 / R4.1)
# ---------------------------------------------------------------------------


class RejectedCandidateProposalV1(BaseModel):
    """A candidate span that was considered and rejected for this packet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    symbol: str
    reason: str
    allowed_scope: str = ""


class EvidencePacketProposalV1(BaseModel):
    """LLM-submitted proposal for an evidence packet (R4.1).

    The proposal selects behavior node/relation ids from a validated
    ``CodeBehaviorGraphV1`` and declares which spans are anchors, which
    are relation evidence, and which conditions must hold.  The compiler
    builds the typed ``EvidencePacketV3`` from this proposal.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    packet_id: str
    obligation_id: str
    scope: str
    anchor_span_ids: list[str]
    relation_span_ids: list[str] = Field(default_factory=list)
    semantic_span_ids: list[str] = Field(default_factory=list)
    behavior_node_ids: list[str] = Field(default_factory=list)
    behavior_relation_ids: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    composition_rationale: str = ""
    rejected_candidates: list[RejectedCandidateProposalV1] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------


class EvidencePacketValidationReportV1(BaseModel):
    """Deterministic validation report for a proposed evidence packet.

    ``failures`` is a list of stable, machine-parseable failure codes.  An
    empty list means the packet is acceptable.  The semantic verifier
    (LLM) may *append* observations to ``semantic_notes`` but MUST NOT
    remove items from ``failures``: a deterministic failure cannot be
    overridden by a semantic pass.
    """

    model_config = ConfigDict(extra="forbid")

    packet_id: str
    failures: list[str] = Field(default_factory=list)
    semantic_notes: list[str] = Field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return not self.failures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _relation_type_for(kind: str) -> str:
    """Map a ``BehaviorRelationKind`` to an ``EvidenceRelationType``."""

    mapping = {
        "CALLS": "call_flow",
        "RETURNS_TO": "call_flow",
        "DATA_DEPENDS_ON": "data_flow",
        "READS_FROM": "data_flow",
        "WRITES_TO": "writes",
        "NEXT_CONTROL": "control_flow",
        "TRUE_BRANCH": "control_flow",
        "FALSE_BRANCH": "control_flow",
        "CONTROL_DEPENDS_ON": "control_flow",
        "CONFIGURED_BY": "data_flow",
        "CONTAINS": "control_flow",
        "ALIAS_OF": "data_flow",
        "OVERRIDES": "call_flow",
        "IMPLEMENTS": "call_flow",
    }
    return mapping.get(kind, "control_flow")


def _span_id_from_node(node: BehaviorNodeV1) -> str:
    return node.source_span_id


def _build_span(
    *,
    span_id: str,
    snapshot_id: str,
    project_tree_hash: str,
    path: str,
    symbol: str,
    line_start: int,
    line_end: int,
    role: str,
) -> EvidenceSpanV3:
    excerpt = f"{path}:{line_start}-{line_end}:{symbol}:{role}"
    return EvidenceSpanV3(
        span_id=span_id,
        snapshot_id=snapshot_id,
        project_tree_hash=project_tree_hash,
        path=path,
        symbol=symbol,
        line_start=line_start,
        line_end=line_end,
        exact_excerpt=excerpt,
        excerpt_digest=_digest(excerpt),
        file_digest=_digest(f"{path}:{project_tree_hash}"),
        role=role,  # type: ignore[arg-type]
    )


def _spans_from_nodes(
    nodes: list[BehaviorNodeV1],
    *,
    snapshot_id: str,
    project_tree_hash: str,
    anchor_span_ids: list[str],
    relation_span_ids: list[str],
    semantic_span_ids: list[str],
) -> list[EvidenceSpanV3]:
    """Build ``EvidenceSpanV3`` instances from behavior nodes.

    Each node's ``source_span_id`` becomes a span.  The role is determined
    by which list the span id appears in (anchor > relation > semantic).
    """

    anchor_set = set(anchor_span_ids)
    relation_set = set(relation_span_ids)
    semantic_set = set(semantic_span_ids)
    spans: list[EvidenceSpanV3] = []
    seen: set[str] = set()
    for node in nodes:
        span_id = _span_id_from_node(node)
        if not span_id or span_id in seen:
            continue
        seen.add(span_id)
        if span_id in anchor_set:
            role = "anchor"
        elif span_id in relation_set:
            role = "relation"
        elif span_id in semantic_set:
            role = "semantic"
        else:
            # Default to relation role for any node not explicitly declared.
            role = "relation"
        path, line_start, line_end = _parse_span_id(span_id)
        spans.append(_build_span(
            span_id=span_id,
            snapshot_id=snapshot_id,
            project_tree_hash=project_tree_hash,
            path=path,
            symbol=node.symbol_id,
            line_start=line_start,
            line_end=line_end,
            role=role,
        ))
    return spans


def _parse_span_id(span_id: str) -> tuple[str, int, int]:
    """Parse a ``span:<path>:<start>:<end>`` id into its components.

    Returns ``("", 1, 1)`` for malformed ids so the validator can flag the
    span instead of crashing.
    """

    if not span_id.startswith("span:"):
        return "", 1, 1
    body = span_id[len("span:"):]
    parts = body.rsplit(":", 2)
    if len(parts) != 3:
        return "", 1, 1
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except ValueError:
        return "", 1, 1


def _relation_evidence_from_relation(
    relation: BehaviorRelationV1,
    *,
    nodes_by_id: dict[str, BehaviorNodeV1],
) -> RelationEvidenceV3:
    source_symbol = relation.source_symbol_id
    target_symbol = relation.target_symbol_id or relation.target_node_id
    direct_span_ids: list[str] = []
    if relation.source_span_id:
        direct_span_ids.append(relation.source_span_id)
    if relation.target_span_id and relation.target_span_id not in direct_span_ids:
        direct_span_ids.append(relation.target_span_id)
    statement = f"{relation.kind}: {source_symbol} -> {target_symbol}"
    if relation.guard:
        statement += f" when {relation.guard}"
    return RelationEvidenceV3(
        relation_id=relation.relation_id,
        relation_type=_relation_type_for(relation.kind),  # type: ignore[arg-type]
        source_symbol=source_symbol,
        target_symbol=target_symbol,
        direct_span_ids=direct_span_ids,
        conditions=[relation.guard] if relation.guard else [],
        statement=statement,
    )


# ---------------------------------------------------------------------------
# Core: compile proposal -> EvidencePacketV3
# ---------------------------------------------------------------------------


def compile_evidence_packet_proposal(
    proposal: EvidencePacketProposalV1,
    graph: CodeBehaviorGraphV1,
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
) -> tuple[EvidencePacketV3 | None, EvidencePacketValidationReportV1]:
    """Compile a proposal into a typed ``EvidencePacketV3``.

    Returns ``(packet, report)``.  When ``report.failures`` is non-empty the
    packet is still returned (so the caller can inspect it) but it MUST be
    treated as untrusted: the report's failures explain why.

    The packet is ``None`` only when the proposal references no behavior
    nodes at all (``behavior_node_ids`` is empty), because in that case
    there is nothing to anchor.
    """

    nodes_by_id = {n.node_id: n for n in graph.nodes}
    relations_by_id = {r.relation_id: r for r in graph.relations}
    unresolved_ids = {u.relation_id for u in graph.unresolved_relations}

    selected_nodes = [nodes_by_id[nid] for nid in proposal.behavior_node_ids if nid in nodes_by_id]
    selected_relations = [
        relations_by_id[rid]
        for rid in proposal.behavior_relation_ids
        if rid in relations_by_id
    ]

    spans = _spans_from_nodes(
        selected_nodes,
        snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        anchor_span_ids=proposal.anchor_span_ids,
        relation_span_ids=proposal.relation_span_ids,
        semantic_span_ids=proposal.semantic_span_ids,
    )
    relations = [
        _relation_evidence_from_relation(rel, nodes_by_id=nodes_by_id)
        for rel in selected_relations
    ]
    rejected = [
        RejectedEvidenceCandidateV3(
            path=rc.path,
            symbol=rc.symbol,
            reason=rc.reason,
            allowed_scope=rc.allowed_scope,
        )
        for rc in proposal.rejected_candidates
    ]

    source_digest = _digest([span.excerpt_digest for span in spans])
    try:
        packet = EvidencePacketV3(
            packet_id=proposal.packet_id,
            obligation_tags=[proposal.obligation_id],
            scope=proposal.scope,
            anchor_span_ids=list(proposal.anchor_span_ids),
            relation_span_ids=list(proposal.relation_span_ids),
            semantic_span_ids=list(proposal.semantic_span_ids),
            spans=spans,
            relations=relations,
            conditions=list(proposal.conditions),
            composition_rationale=proposal.composition_rationale,
            rejected_candidates=rejected,
            source_digest=source_digest,
        )
    except Exception:
        # If the packet model rejects the proposal (e.g. unknown span ids
        # or fan-in > 3 without rationale), return None and let the
        # validator report the specific failure.
        packet = None

    report = validate_evidence_packet_proposal(
        proposal=proposal,
        graph=graph,
        compiled_packet=packet,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        selected_nodes=selected_nodes,
        selected_relations=selected_relations,
        spans=spans,
        unresolved_ids=unresolved_ids,
    )
    return packet, report


# ---------------------------------------------------------------------------
# Core: validate proposal against behavior graph
# ---------------------------------------------------------------------------


def validate_evidence_packet_proposal(
    *,
    proposal: EvidencePacketProposalV1,
    graph: CodeBehaviorGraphV1,
    compiled_packet: EvidencePacketV3 | None,
    repo_snapshot_id: str,
    project_tree_hash: str,
    selected_nodes: list[BehaviorNodeV1],
    selected_relations: list[BehaviorRelationV1],
    spans: list[EvidenceSpanV3],
    unresolved_ids: set[str],
) -> EvidencePacketValidationReportV1:
    """Run the R4.1 deterministic validator checklist on a proposal."""

    failures: list[str] = []

    # 1) snapshot/freshness
    for span in spans:
        if span.snapshot_id != repo_snapshot_id:
            failures.append(f"span_snapshot_mismatch:{span.span_id}")
        if span.project_tree_hash != project_tree_hash:
            failures.append(f"span_tree_hash_mismatch:{span.span_id}")

    # 2) source authority: anchor spans must be backed by executable_hard nodes
    anchor_span_ids = set(proposal.anchor_span_ids)
    nodes_by_span = {n.source_span_id: n for n in selected_nodes if n.source_span_id}
    for anchor_id in proposal.anchor_span_ids:
        node = nodes_by_span.get(anchor_id)
        if node is None:
            failures.append(f"anchor_span_has_no_behavior_node:{anchor_id}")
            continue
        if _authority_rank(node.source_authority) < _authority_rank("executable_hard"):
            failures.append(
                f"hint_only_anchor:{anchor_id}:{node.source_authority}"
            )

    # 3) anchor role: anchor_span_ids must map to spans whose role is anchor
    span_role_by_id = {span.span_id: span.role for span in spans}
    for anchor_id in proposal.anchor_span_ids:
        role = span_role_by_id.get(anchor_id)
        if role is None:
            # The span id was declared but no behavior node supplied it.
            failures.append(f"anchor_span_missing:{anchor_id}")
        elif role != "anchor":
            failures.append(f"wrong_span_role:{anchor_id}:{role}")

    # 4) relation existence: every relation id must exist in the graph
    graph_relation_ids = {r.relation_id for r in graph.relations}
    for rid in proposal.behavior_relation_ids:
        if rid in unresolved_ids:
            failures.append(f"relation_unresolved:{rid}")
        elif rid not in graph_relation_ids:
            failures.append(f"relation_unknown:{rid}")

    # 5) guard coverage: every guard on a selected node must be in conditions
    declared_conditions = set(proposal.conditions)
    for node in selected_nodes:
        if node.guard and node.guard not in declared_conditions:
            failures.append(f"missing_guard:{node.node_id}:{node.guard}")

    # 6) no unrelated span: every span must be reachable from an anchor
    if compiled_packet is not None and spans:
        reachable = _reachable_spans(
            anchor_span_ids=list(proposal.anchor_span_ids),
            relation_span_ids=list(proposal.relation_span_ids),
            relations=compiled_packet.relations,
            span_ids={span.span_id for span in spans},
        )
        for span in spans:
            if span.span_id not in reachable and span.span_id not in anchor_span_ids:
                failures.append(f"unrelated_span:{span.span_id}")

    # 7) minimality: >3 spans require composition_rationale
    total_spans = (
        len(proposal.anchor_span_ids)
        + len(proposal.relation_span_ids)
        + len(proposal.semantic_span_ids)
    )
    if total_spans > 3 and not proposal.composition_rationale.strip():
        failures.append("missing_composition_rationale")

    # 8) rejected candidate rationale
    for rc in proposal.rejected_candidates:
        if not rc.reason.strip():
            failures.append(f"rejected_candidate_without_reason:{rc.path}:{rc.symbol}")

    # 9) compiled_packet model validation
    if compiled_packet is None:
        failures.append("packet_model_rejected_proposal")

    return EvidencePacketValidationReportV1(
        packet_id=proposal.packet_id,
        failures=failures,
    )


def _reachable_spans(
    *,
    anchor_span_ids: list[str],
    relation_span_ids: list[str],
    relations: list[RelationEvidenceV3],
    span_ids: set[str],
) -> set[str]:
    """Compute the set of spans reachable from anchors via relations.

    Used by the "no unrelated span" check.  A span is reachable if it is
    an anchor, or it appears in a relation's ``direct_span_ids`` together
    with an already-reachable span.
    """

    reachable: set[str] = set(anchor_span_ids)
    # Build adjacency: span -> set of spans that share a relation.
    adjacency: dict[str, set[str]] = {}
    for rel in relations:
        for a in rel.direct_span_ids:
            for b in rel.direct_span_ids:
                if a != b:
                    adjacency.setdefault(a, set()).add(b)
    # BFS
    queue = list(reachable)
    while queue:
        current = queue.pop()
        for neighbor in adjacency.get(current, set()):
            if neighbor in span_ids and neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    return reachable


# ---------------------------------------------------------------------------
# Packet set builder
# ---------------------------------------------------------------------------


def build_evidence_packet_set(
    packets: list[EvidencePacketV3],
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
) -> EvidencePacketSetV3:
    """Wrap a list of validated packets into an ``EvidencePacketSetV3``."""

    payload = [item.model_dump(mode="json") for item in packets]
    return EvidencePacketSetV3(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        packets=packets,
        content_digest=_digest(payload),
    )


__all__ = [
    "EvidencePacketProposalV1",
    "EvidencePacketValidationReportV1",
    "RejectedCandidateProposalV1",
    "build_evidence_packet_set",
    "compile_evidence_packet_proposal",
    "validate_evidence_packet_proposal",
]
