"""R4.2 generic fact compiler: ``CodeBehaviorGraphV1`` -> ``CodeFactV1``.

This module implements design section 9.1 (``FactCompilerV2``).  Unlike the
project-specific profile in ``evidence_compiler_v3.compile_evidence_v3``,
the generic compiler never hardcodes fact ids, subjects or objects: every
``CodeFactV1`` is derived from a ``BehaviorNodeV1`` or a typed
``BehaviorRelationV1`` in the supplied behavior graph.

Inputs (design 9.1)::

    FactCompilerInputV1
      obligation_id
      behavior_node_ids
      behavior_relation_ids
      evidence_span_ids
      guards
      source_authority

Outputs reuse the shared ``CodeFactV1`` / ``CodeFactSetV1`` models from
``evidence_compiler_v3`` so downstream claim compilers and validators do
not need a separate type hierarchy.

Deterministic invariants enforced here:

- the same behavior graph always produces the same ``canonical_identity``
  for the same (subject, predicate, object, conditions) tuple;
- a node whose ``source_authority`` is weaker than the input's
  ``source_authority`` floor is rejected (``validation_status="rejected"``)
  with a ``weak_source_authority`` failure;
- a relation that only appears in ``unresolved_relations`` cannot anchor a
  positive fact (anti-hallucination floor);
- ``configured_by`` facts come from ``CONFIGURED_BY`` relations, not from
  node predicates;
- ``calls_in_order`` facts come from an ordered chain of ``CALL`` nodes
  connected by ``NEXT_CONTROL`` relations inside the same symbol.

R4.5 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
The generic compiler only knows about behavior predicates and relation
kinds.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
)
from code2paper.agentic.evidence_compiler_v3 import (
    CodeFactSetV1,
    CodeFactV1,
    FactPredicate,
)
from code2paper.agentic.source_authority import SourceAuthorityV1


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
# Predicate mapping: BEHAVIOR_PREDICATES -> FactPredicate
# ---------------------------------------------------------------------------

#: Mapping from uppercase behavior predicates to lowercase fact predicates.
#: Every entry in ``BEHAVIOR_PREDICATES`` MUST appear here; if a predicate
#: has no first-batch mapping it still gets a generic fact predicate so the
#: compiler never silently drops a node.
BEHAVIOR_PREDICATE_TO_FACT: dict[str, FactPredicate] = {
    "READ": "reads",
    "WRITE": "writes",
    "CALL": "calls",
    "CONSTRUCT": "constructs",
    "LOAD": "loads_weights",
    "RETURN": "returns",
    "TRANSFORM": "transforms",
    "CONCAT": "concatenates",
    "STACK": "stacks",
    "NORMALIZE": "normalizes",
    "REDUCE": "reduces",
    "AGGREGATE": "aggregates",
    "COMPUTE": "computes_formula",
    "COMPARE": "compares",
    "BRANCH": "branches_on",
    "LOOP": "loops",
    "SELECT": "selects",
    "TOPK": "selects_top_k",
    "SORT": "sorts_by",
    "MASK": "constructs_mask",
    "FILTER": "filters_by",
    "RESHAPE": "reshapes",
    "PROJECT": "projects",
    "ATTEND": "attends",
    "SAMPLE": "samples",
    "PROPAGATE": "propagates",
    "SERIALIZE": "writes_artifact",
}

#: Relation kinds that yield their own fact predicate (rather than just
#: decorating a node fact).  ``CONFIGURED_BY`` is the canonical example: a
#: configuration fact is a relation-level fact, not a node-level fact.
RELATION_KIND_TO_FACT: dict[str, FactPredicate] = {
    "CONFIGURED_BY": "configured_by",
}


def _assert_complete_mapping() -> None:
    """Guard against drift between BEHAVIOR_PREDICATES and the mapping."""

    missing = [p for p in BEHAVIOR_PREDICATES if p not in BEHAVIOR_PREDICATE_TO_FACT]
    if missing:
        raise RuntimeError(
            f"BEHAVIOR_PREDICATE_TO_FACT is missing entries for: {missing}"
        )
    unknown = [p for p in BEHAVIOR_PREDICATE_TO_FACT if p not in BEHAVIOR_PREDICATES]
    if unknown:
        raise RuntimeError(
            f"BEHAVIOR_PREDICATE_TO_FACT references unknown predicates: {unknown}"
        )


_assert_complete_mapping()


# ---------------------------------------------------------------------------
# Input model (design 9.1)
# ---------------------------------------------------------------------------


class FactCompilerInputV1(BaseModel):
    """Input to the generic fact compiler.

    Matches design section 9.1: the caller (supervisor / evidence critic)
    supplies the obligation id, the selected behavior node/relation ids, the
    evidence span ids that anchor the packet, the guards that must hold for
    the behavior to be active, and the minimum source authority the facts
    may rely on.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    behavior_node_ids: list[str] = Field(default_factory=list)
    behavior_relation_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    guards: list[str] = Field(default_factory=list)
    source_authority: SourceAuthorityV1 = "executable_hard"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_object(value: str | list[str]) -> str | list[str]:
    if isinstance(value, str):
        return _normalize_text(value)
    return [_normalize_text(item) for item in value]


def _normalize_text(value: str) -> str:
    import re

    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


def _node_subject(node: BehaviorNodeV1) -> str:
    """Subject for a node-derived fact: the symbol that owns the node."""

    return node.symbol_id


def _node_object(node: BehaviorNodeV1) -> str | list[str]:
    """Object for a node-derived fact.

    Prefers ``result`` when set (the variable / attribute the operation
    produces), otherwise joins ``operands``.  When both are empty the
    object is the predicate itself in lowercase form so the fact is still
    well-formed.
    """

    if node.result:
        return node.result
    if node.operands:
        return list(node.operands)
    return BEHAVIOR_PREDICATE_TO_FACT[node.predicate]


def _node_conditions(node: BehaviorNodeV1, input_guards: list[str]) -> list[str]:
    conditions: list[str] = []
    if node.guard:
        conditions.append(node.guard)
    for guard in input_guards:
        if guard and guard not in conditions:
            conditions.append(guard)
    return conditions


def _node_semantic_context(node: BehaviorNodeV1) -> list[str]:
    """Return parsed, source-derived terms for deterministic alignment replay.

    Candidate-time alignment can see the selected behavior nodes directly.
    The final coverage and claim-binding passes only receive facts, so the
    node's symbol/result/operands must travel with the span-anchored fact.
    Nothing author supplied is copied into this field.
    """

    values = [
        node.symbol_id,
        node.predicate,
        node.result,
        node.guard,
        node.iteration_context,
        *node.operands,
    ]
    return [value for value in values if value]


def _node_span_ids(node: BehaviorNodeV1) -> list[str]:
    return [node.source_span_id] if node.source_span_id else []


def _relation_span_ids(relation: BehaviorRelationV1) -> list[str]:
    spans: list[str] = []
    if relation.source_span_id:
        spans.append(relation.source_span_id)
    if relation.target_span_id and relation.target_span_id not in spans:
        spans.append(relation.target_span_id)
    return spans


def _fact_id(prefix: str, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _node_fact_prefix(obligation_id: str) -> str:
    return f"fact-{obligation_id}-node"


def _relation_fact_prefix(obligation_id: str) -> str:
    return f"fact-{obligation_id}-rel"


def _calls_in_order_chain(
    graph: CodeBehaviorGraphV1,
    selected_nodes: list[BehaviorNodeV1],
) -> list[list[BehaviorNodeV1]]:
    """Detect ordered chains of CALL nodes inside a single symbol.

    Two CALL nodes are chained when a ``NEXT_CONTROL`` relation connects
    them and both belong to the same symbol.  Each chain becomes a single
    ``calls_in_order`` fact; standalone CALL nodes become ``calls`` facts.
    """

    nodes_by_id = {n.node_id: n for n in selected_nodes if n.predicate == "CALL"}
    if not nodes_by_id:
        return []
    next_map: dict[str, str] = {}
    for rel in graph.relations:
        if rel.kind != "NEXT_CONTROL":
            continue
        if rel.source_node_id in nodes_by_id and rel.target_node_id in nodes_by_id:
            next_map[rel.source_node_id] = rel.target_node_id
    # Find chain starts (nodes that are never a target).
    targets = set(next_map.values())
    starts = [nid for nid in nodes_by_id if nid not in targets]
    chains: list[list[BehaviorNodeV1]] = []
    for start in starts:
        chain: list[BehaviorNodeV1] = [nodes_by_id[start]]
        current = start
        while current in next_map:
            nxt = next_map[current]
            if nxt in {n.node_id for n in chain}:
                break  # defensive: avoid cycles
            chain.append(nodes_by_id[nxt])
            current = nxt
        if len(chain) >= 2:
            chains.append(chain)
    return chains


# ---------------------------------------------------------------------------
# Core compiler
# ---------------------------------------------------------------------------


def compile_facts_from_behavior_graph(
    graph: CodeBehaviorGraphV1,
    compiler_input: FactCompilerInputV1,
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
    evidence_packet_digest: str,
) -> CodeFactSetV1:
    """Compile ``CodeFactV1`` facts from a behavior graph.

    Parameters
    ----------
    graph
        The validated ``CodeBehaviorGraphV1`` produced by the research loop.
    compiler_input
        The obligation-scoped input (design 9.1).  Only nodes/relations
        whose ids appear in ``behavior_node_ids`` / ``behavior_relation_ids``
        are compiled; the rest of the graph is ignored.
    repo_snapshot_id, project_tree_hash, evidence_packet_digest
        Provenance fields for the resulting ``CodeFactSetV1``.

    Notes
    -----
    - Nodes whose ``source_authority`` is weaker than
      ``compiler_input.source_authority`` are emitted with
      ``validation_status="rejected"`` and a ``weak_source_authority``
      failure.  They are still included so a downstream claim compiler can
      explain *why* a claim is unsupported.
    - Relations that appear only in ``unresolved_relations`` are never
      compiled into positive facts.
    - ``calls_in_order`` facts are derived from ``NEXT_CONTROL`` chains of
      ``CALL`` nodes inside a single symbol.  A standalone ``CALL`` node
      yields a ``calls`` fact instead.
    - ``configured_by`` facts are derived from ``CONFIGURED_BY`` relations.
    """

    selected_node_ids = set(compiler_input.behavior_node_ids)
    selected_relation_ids = set(compiler_input.behavior_relation_ids)
    selected_nodes = [n for n in graph.nodes if n.node_id in selected_node_ids]
    selected_relations = [
        r for r in graph.relations if r.relation_id in selected_relation_ids
    ]
    # Also include unresolved relations whose ids were requested, so the
    # compiler can flag them as failures on the nodes they reference.
    selected_unresolved = [
        u for u in graph.unresolved_relations if u.relation_id in selected_relation_ids
    ]
    unresolved_ids = {u.relation_id for u in graph.unresolved_relations}

    authority_floor = _authority_rank(compiler_input.source_authority)
    facts: list[CodeFactV1] = []
    seen_identities: set[str] = set()

    # 1) Node-derived facts (one per node, except CALL nodes that are part
    #    of a calls_in_order chain).
    call_chain_node_ids: set[str] = set()
    for chain in _calls_in_order_chain(graph, selected_nodes):
        for node in chain:
            call_chain_node_ids.add(node.node_id)

    for node in selected_nodes:
        if node.predicate == "CALL" and node.node_id in call_chain_node_ids:
            continue  # will be emitted as part of a calls_in_order fact
        predicate = BEHAVIOR_PREDICATE_TO_FACT[node.predicate]
        subject = _node_subject(node)
        obj = _node_object(node)
        conditions = _node_conditions(node, compiler_input.guards)
        identity = _digest({
            "snapshot": repo_snapshot_id,
            "scope": node.symbol_id,
            "subject": subject,
            "predicate": predicate,
            "object": _normalize_object(obj),
            "conditions": sorted(conditions),
        })
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        failures: list[str] = []
        if _authority_rank(node.source_authority) < authority_floor:
            failures.append(
                f"weak_source_authority:{node.source_authority}<{compiler_input.source_authority}"
            )
        direct_spans = _node_span_ids(node)
        relation_span_ids: list[str] = []
        relation_evidence_ids: list[str] = []
        relation_kinds: list[str] = []
        # Attach resolved relations that reference this node.
        for rel in selected_relations:
            if rel.source_node_id == node.node_id or rel.target_node_id == node.node_id:
                if rel.relation_id in unresolved_ids:
                    failures.append(f"unresolved_relation:{rel.relation_id}")
                    continue
                relation_evidence_ids.append(rel.relation_id)
                if rel.kind not in relation_kinds:
                    relation_kinds.append(rel.kind)
                for span in _relation_span_ids(rel):
                    if span not in relation_span_ids:
                        relation_span_ids.append(span)
        # Flag unresolved relations that were explicitly requested and
        # reference this node (anti-hallucination floor).
        for unres in selected_unresolved:
            if unres.source_node_id == node.node_id:
                failures.append(f"unresolved_relation:{unres.relation_id}")
        exact_digest = _digest([span for span in direct_spans + relation_span_ids])
        facts.append(CodeFactV1(
            fact_id=_fact_id(_node_fact_prefix(compiler_input.obligation_id), identity),
            subject=subject,
            predicate=predicate,
            object=obj,
            conditions=conditions,
            scope=node.symbol_id,
            direct_span_ids=direct_spans,
            relation_span_ids=relation_span_ids,
            relation_evidence_ids=relation_evidence_ids,
            relation_kinds=relation_kinds,
            semantic_context=_node_semantic_context(node),
            exact_source_digest=exact_digest,
            canonical_identity=identity,
            validation_status="rejected" if failures else "supported",
            validation_failures=failures,
        ))

    # 2) calls_in_order facts (one per detected chain).
    for chain in _calls_in_order_chain(graph, selected_nodes):
        first = chain[0]
        subject = first.symbol_id
        obj = [n.result or n.operands[0] if n.operands else n.node_id for n in chain]
        conditions = _node_conditions(first, compiler_input.guards)
        identity = _digest({
            "snapshot": repo_snapshot_id,
            "scope": first.symbol_id,
            "subject": subject,
            "predicate": "calls_in_order",
            "object": _normalize_object(obj),
            "conditions": sorted(conditions),
            "chain": [n.node_id for n in chain],
        })
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        direct_spans: list[str] = []
        relation_evidence_ids: list[str] = []
        relation_span_ids: list[str] = []
        relation_kinds: list[str] = []
        failures: list[str] = []
        for node in chain:
            if _authority_rank(node.source_authority) < authority_floor:
                failures.append(
                    f"weak_source_authority:{node.source_authority}<{compiler_input.source_authority}"
                )
            for span in _node_span_ids(node):
                if span not in direct_spans:
                    direct_spans.append(span)
        # NEXT_CONTROL relations inside the chain.
        for rel in selected_relations:
            if rel.kind != "NEXT_CONTROL":
                continue
            if rel.source_node_id in {n.node_id for n in chain} and rel.target_node_id in {n.node_id for n in chain}:
                if rel.relation_id in unresolved_ids:
                    failures.append(f"unresolved_relation:{rel.relation_id}")
                    continue
                relation_evidence_ids.append(rel.relation_id)
                if rel.kind not in relation_kinds:
                    relation_kinds.append(rel.kind)
                for span in _relation_span_ids(rel):
                    if span not in relation_span_ids:
                        relation_span_ids.append(span)
        exact_digest = _digest(direct_spans + relation_span_ids)
        facts.append(CodeFactV1(
            fact_id=_fact_id(_node_fact_prefix(compiler_input.obligation_id), identity),
            subject=subject,
            predicate="calls_in_order",
            object=obj,
            conditions=conditions,
            scope=first.symbol_id,
            direct_span_ids=direct_spans,
            relation_span_ids=relation_span_ids,
            relation_evidence_ids=relation_evidence_ids,
            relation_kinds=relation_kinds,
            semantic_context=[
                value
                for node in chain
                for value in _node_semantic_context(node)
            ],
            exact_source_digest=exact_digest,
            canonical_identity=identity,
            validation_status="rejected" if failures else "supported",
            validation_failures=failures,
        ))

    # 3) Relation-derived facts (configured_by, and any future
    #    relation-level predicate).  These are separate from node facts
    #    because the relation itself is the anchor.
    for rel in selected_relations:
        if rel.kind not in RELATION_KIND_TO_FACT:
            continue
        if rel.relation_id in unresolved_ids:
            # Unresolved relations can never anchor a positive fact.
            continue
        predicate = RELATION_KIND_TO_FACT[rel.kind]
        subject = rel.source_symbol_id
        obj = rel.target_symbol_id or rel.target_node_id
        if not obj:
            continue
        conditions = list(compiler_input.guards)
        if rel.guard and rel.guard not in conditions:
            conditions.append(rel.guard)
        identity = _digest({
            "snapshot": repo_snapshot_id,
            "scope": rel.source_symbol_id,
            "subject": subject,
            "predicate": predicate,
            "object": _normalize_object(obj),
            "conditions": sorted(conditions),
            "relation": rel.relation_id,
        })
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        direct_spans = _relation_span_ids(rel)
        exact_digest = _digest(direct_spans)
        facts.append(CodeFactV1(
            fact_id=_fact_id(_relation_fact_prefix(compiler_input.obligation_id), identity),
            subject=subject,
            predicate=predicate,
            object=obj,
            conditions=conditions,
            scope=rel.source_symbol_id,
            direct_span_ids=direct_spans,
            relation_span_ids=[],
            relation_evidence_ids=[rel.relation_id],
            relation_kinds=[rel.kind],
            semantic_context=[
                value
                for value in (
                    rel.source_symbol_id,
                    rel.target_symbol_id,
                    rel.target_node_id,
                    rel.guard,
                )
                if value
            ],
            exact_source_digest=exact_digest,
            canonical_identity=identity,
            validation_status="supported",
            validation_failures=[],
        ))

    payload = [item.model_dump(mode="json") for item in facts]
    return CodeFactSetV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        evidence_packet_digest=evidence_packet_digest,
        facts=facts,
        content_digest=_digest(payload),
    )


__all__ = [
    "BEHAVIOR_PREDICATE_TO_FACT",
    "RELATION_KIND_TO_FACT",
    "FactCompilerInputV1",
    "compile_facts_from_behavior_graph",
]
