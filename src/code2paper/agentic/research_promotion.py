"""Observation-to-evidence promotion ledger.

Every successful research observation gets an explicit outcome.  Discovery
refs alone remain discovery; only the typed graph -> packet -> fact -> claim
chain can produce a promotable record.  This sidecar makes a missing handoff
visible instead of allowing the research loop to appear complete because a
tool returned text.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.agentic.implementation_scope import (
    _location_ref_parts,
    _span_interval,
    resolve_candidate_binding,
    source_intervals_overlap,
)
from code2paper.agentic.typed_refs import split_span_ref

PromotionStatusV1 = Literal[
    "discovered_only",
    "observed_unpromoted",
    "behavior_built",
    "packet_promoted",
    "fact_promoted",
    "claim_promoted",
    "rejected",
]
EvidenceLaneV1 = Literal[
    "executable_behavior",
    "configuration",
    "discovery_hint",
]


class ObservationPromotionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    obligation_id: str
    tool_name: str
    status: PromotionStatusV1
    evidence_lane: EvidenceLaneV1 = "executable_behavior"
    source_authority: str = ""
    observation_refs: tuple[str, ...] = Field(default_factory=tuple)
    behavior_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    packet_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    rejection_code: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ObservationPromotionRecordV1":
        if not self.observation_id.strip() or not self.obligation_id.strip():
            raise ValueError("promotion record requires observation and obligation ids")
        if self.status in {"observed_unpromoted", "rejected"} and not self.rejection_code.strip():
            raise ValueError("unpromoted observation requires a typed rejection code")
        if self.status == "claim_promoted" and not (
            self.behavior_node_ids and self.packet_ids and self.fact_ids and self.claim_ids
        ):
            raise ValueError("claim promotion requires the complete graph/packet/fact/claim chain")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("observation promotion record digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class ObservationPromotionLedgerV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    records: tuple[ObservationPromotionRecordV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ObservationPromotionLedgerV1":
        ids = [item.observation_id for item in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("observation promotion ledger contains duplicate observations")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("observation promotion ledger digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    @property
    def unresolved_records(self) -> tuple[ObservationPromotionRecordV1, ...]:
        return tuple(item for item in self.records if item.status in {"observed_unpromoted", "rejected"})


def _value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _refs(observation: Any) -> tuple[str, ...]:
    notebook = _value(observation, "notebook", None)
    return tuple(dict.fromkeys(
        str(value).strip()
        for value in (
            *(_value(observation, "result_refs", ()) or ()),
            *(_value(observation, "exact_span_ids", ()) or ()),
            *(_value(notebook, "discovered_symbols", ()) or ()),
        )
        if str(value).strip()
    ))


def _node_matches(
    node: Any,
    refs: set[str],
    spans: set[str],
    *,
    symbols: Iterable[Any] = (),
    nodes: Iterable[Any] = (),
) -> bool:
    """Match one observation to a node through the shared identity resolver.

    Exact span ids are source intervals, not opaque strings.  A wide read
    such as ``span:file.py:180:250`` therefore binds statement-level nodes
    inside that interval, while a sibling outside the interval remains
    excluded.  ``resolve_candidate_binding`` also rejects ambiguous leaf
    symbols instead of silently widening to a path.
    """

    node_id = str(_value(node, "node_id", "") or "")
    node_items = tuple(nodes) or (node,)
    candidate_refs = (*sorted(refs), *sorted(spans))
    authoritative_ranges: list[tuple[str, int, int]] = []
    for ref in candidate_refs:
        if _location_ref_parts(ref) is None:
            continue
        location_binding = resolve_candidate_binding(
            ref,
            symbols=tuple(symbols),
            behavior_nodes=(),
            exact_span_ids=(),
            mode="promotion",
        )
        # A failed/ambiguous typed location must not be rescued by the
        # observation's independent broad span ref.  This is the promotion
        # side of the same identity gate used by acquisition and compile.
        if location_binding.ambiguous or location_binding.rejection_code:
            return False
        authoritative_ranges.extend(location_binding.symbol_ranges)
    authoritative_ranges = list(dict.fromkeys(authoritative_ranges))
    node_interval = _span_interval(_value(node, "source_span_id", ""))
    if authoritative_ranges and node_interval is not None and not any(
        source_intervals_overlap(node_interval, item)
        for item in authoritative_ranges
    ):
        return False
    for ref in candidate_refs:
        binding = resolve_candidate_binding(
            ref,
            symbols=tuple(symbols),
            behavior_nodes=node_items,
            exact_span_ids=spans,
            mode="promotion",
        )
        if (
            not binding.ambiguous
            and not binding.rejection_code
            and node_id in binding.behavior_node_ids
        ):
            return True
    return False


def _span_ids(item: Any) -> tuple[str, ...]:
    values: list[str] = []
    for field in (
        "anchor_span_ids",
        "relation_span_ids",
        "semantic_span_ids",
        "direct_span_ids",
    ):
        values.extend(
            str(value).strip()
            for value in (_value(item, field, ()) or ())
            if str(value).strip()
        )
    for span in (_value(item, "spans", ()) or ()):
        span_id = str(_value(span, "span_id", "") or "").strip()
        if span_id:
            values.append(span_id)
    return tuple(dict.fromkeys(values))


def _intervals(refs: Iterable[str]) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for ref in refs:
        parsed = split_span_ref(str(ref))
        if parsed is not None and parsed not in result:
            result.append(parsed)
    return tuple(result)


def _span_lineage_intersects(
    left_refs: Iterable[str],
    right_refs: Iterable[str],
) -> bool:
    left_ids = {str(value).strip() for value in left_refs if str(value).strip()}
    right_ids = {str(value).strip() for value in right_refs if str(value).strip()}
    if left_ids.intersection(right_ids):
        return True
    return any(
        source_intervals_overlap(left, right)
        for left in _intervals(left_ids)
        for right in _intervals(right_ids)
    )


def _packet_ids_for_nodes(
    packet_set: Any,
    *,
    node_ids: set[str],
    node_span_ids: set[str],
) -> tuple[tuple[str, ...], set[str]]:
    packet_ids: list[str] = []
    packet_span_ids: set[str] = set()
    packets = _value(packet_set, "packets", ()) or ()
    for packet in packets:
        packet_id = str(_value(packet, "packet_id", "") or "").strip()
        if not packet_id:
            continue
        packet_spans = set(_span_ids(packet))
        packet_node_ids: set[str] = set()
        for relation in (_value(packet, "relations", ()) or ()):
            for endpoint_name in ("source_endpoint", "target_endpoint"):
                endpoint = _value(relation, endpoint_name, None)
                endpoint_id = str(_value(endpoint, "node_id", "") or "").strip()
                if endpoint_id:
                    packet_node_ids.add(endpoint_id)
        matched = bool(node_ids.intersection(packet_node_ids)) or _span_lineage_intersects(
            packet_spans,
            {*node_span_ids},
        )
        # Older diagnostic mocks did not model span fields.  Keep those
        # records readable only when there is exactly one compiled packet;
        # real EvidencePacketV3 objects always carry the explicit span list
        # and therefore cannot take this compatibility shortcut.
        if not matched and not hasattr(packet, "spans") and isinstance(packet, Mapping):
            matched = len(tuple(packets)) == 1
        if matched:
            packet_ids.append(packet_id)
            packet_span_ids.update(packet_spans)
    return tuple(dict.fromkeys(packet_ids)), packet_span_ids


def _fact_ids_for_packets(
    fact_set: Any,
    *,
    packet_span_ids: set[str],
    node_span_ids: set[str],
) -> tuple[tuple[str, ...], set[str]]:
    fact_ids: list[str] = []
    selected: set[str] = set()
    facts = _value(fact_set, "facts", ()) or ()
    for fact in facts:
        fact_id = str(_value(fact, "fact_id", "") or "").strip()
        if not fact_id:
            continue
        fact_spans = set(_span_ids(fact))
        matched = _span_lineage_intersects(
            fact_spans,
            {*packet_span_ids, *node_span_ids},
        )
        if (
            not matched
            and not hasattr(fact, "direct_span_ids")
            and isinstance(fact, Mapping)
        ):
            matched = len(tuple(facts)) == 1 and bool(
                packet_span_ids or node_span_ids
            )
        if matched:
            fact_ids.append(fact_id)
            selected.add(fact_id)
    return tuple(dict.fromkeys(fact_ids)), selected


def _claim_ids_for_facts(claim_set: Any, fact_ids: set[str]) -> tuple[str, ...]:
    claims: list[str] = []
    claim_items = tuple(_value(claim_set, "claims", ()) or ())
    for claim in claim_items:
        claim_id = str(_value(claim, "claim_id", "") or "").strip()
        claim_facts = {
            str(value).strip()
            for value in (_value(claim, "fact_ids", ()) or ())
            if str(value).strip()
        }
        if (
            not claim_facts
            and isinstance(claim, Mapping)
            and "fact_ids" not in claim
            and len(claim_items) == 1
            and len(fact_ids) == 1
        ):
            # Compatibility for pre-lineage diagnostic mocks.  Production
            # AtomicClaimV3 records always carry fact_ids, so real claims
            # cannot take this shortcut.
            claim_facts = set(fact_ids)
        if claim_id and fact_ids.intersection(claim_facts):
            claims.append(claim_id)
    return tuple(dict.fromkeys(claims))


def build_observation_promotion_ledger(
    *,
    observations: Iterable[Any] = (),
    behavior_graph: Any | None = None,
    compiled_by_obligation: Mapping[str, Any] | None = None,
    symbols: Iterable[Any] = (),
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> ObservationPromotionLedgerV1:
    """Classify each observation at the strongest validated promotion stage."""

    compiled_by_obligation = compiled_by_obligation or {}
    nodes = tuple(getattr(behavior_graph, "nodes", ()) or ()) if behavior_graph is not None else ()
    symbol_items = tuple(symbols)
    records: list[ObservationPromotionRecordV1] = []
    for observation in observations:
        observation_id = str(_value(observation, "observation_id", "") or "").strip()
        obligation_id = str(_value(observation, "obligation_id", "") or "").strip()
        if not observation_id or not obligation_id:
            continue
        tool_name = str(_value(observation, "tool_name", "") or "")
        status_value = str(_value(observation, "status", "") or "")
        if tool_name == "inspect_configuration":
            evidence_lane: EvidenceLaneV1 = "configuration"
        elif tool_name in {"search_symbols", "search_code", "find_entrypoints", "search_semantic_hints"}:
            evidence_lane = "discovery_hint"
        else:
            evidence_lane = "executable_behavior"
        refs = _refs(observation)
        ref_set = set(refs)
        spans = {
            str(value).strip()
            for value in (_value(observation, "exact_span_ids", ()) or ())
            if str(value).strip()
        }
        node_ids = tuple(dict.fromkeys(
            str(_value(node, "node_id", "") or "")
            for node in nodes
            if _node_matches(
                node,
                ref_set,
                spans,
                symbols=symbol_items,
                nodes=nodes,
            ) and str(_value(node, "node_id", "") or "")
        ))
        compiled = compiled_by_obligation.get(obligation_id)
        packet_set = _value(compiled, "packet_set", None)
        fact_set = _value(compiled, "fact_set", None)
        claim_set = _value(compiled, "claim_set", None)
        node_span_ids = {
            str(_value(node, "source_span_id", "") or "").strip()
            for node in nodes
            if str(_value(node, "node_id", "") or "").strip() in set(node_ids)
            and str(_value(node, "source_span_id", "") or "").strip()
        }
        # For a symbol-scoped observation, the resolved symbol range is the
        # authoritative source boundary.  The human-readable read excerpt
        # may be wider, so carrying all observation spans into the packet
        # join would re-introduce sibling packets after node matching had
        # correctly excluded them.
        symbol_scoped = False
        for ref in (*sorted(ref_set), *sorted(spans)):
            if _location_ref_parts(ref) is None:
                continue
            location_binding = resolve_candidate_binding(
                ref,
                symbols=symbol_items,
                behavior_nodes=(),
                exact_span_ids=(),
                mode="promotion",
            )
            if (
                location_binding.symbol_ranges
                and not location_binding.ambiguous
                and not location_binding.rejection_code
            ):
                symbol_scoped = True
                break
        lineage_span_ids = node_span_ids if symbol_scoped else node_span_ids | spans
        packet_ids, packet_span_ids = _packet_ids_for_nodes(
            packet_set,
            node_ids=set(node_ids),
            node_span_ids=lineage_span_ids,
        )
        fact_ids, fact_set_ids = _fact_ids_for_packets(
            fact_set,
            packet_span_ids=packet_span_ids,
            node_span_ids=lineage_span_ids,
        )
        claim_ids = _claim_ids_for_facts(claim_set, fact_set_ids)
        exact_read = tool_name in {"read_symbol", "read_code_span", "build_behavior_subgraph"}
        if evidence_lane == "discovery_hint":
            promotion_status: PromotionStatusV1 = "discovered_only"
            rejection_code = "discovery_refs_are_not_evidence"
        elif status_value != "success":
            promotion_status = "rejected"
            if evidence_lane == "configuration":
                promotion_status = "observed_unpromoted"
                rejection_code = (
                    "configuration_key_not_found"
                    if status_value == "success_empty"
                    else "configuration_parser_unavailable"
                )
            else:
                rejection_code = "observation_failed"
        elif evidence_lane == "configuration":
            promotion_status = "observed_unpromoted"
            if not refs:
                rejection_code = "configuration_key_not_found"
            elif not spans:
                rejection_code = "configuration_unbound_to_executable_behavior"
            elif not node_ids:
                rejection_code = "configuration_consumer_unresolved"
            else:
                rejection_code = "configuration_unbound_to_executable_behavior"
        elif not exact_read or not spans:
            promotion_status = "observed_unpromoted"
            rejection_code = "exact_source_span_missing"
        elif not node_ids:
            promotion_status = "observed_unpromoted"
            rejection_code = "no_matching_behavior_node"
        elif not packet_ids:
            promotion_status = "behavior_built"
            rejection_code = "evidence_packet_not_emitted"
        elif not fact_ids:
            promotion_status = "packet_promoted"
            rejection_code = "code_fact_not_emitted"
        elif not claim_ids:
            promotion_status = "fact_promoted"
            rejection_code = "atomic_claim_not_emitted"
        else:
            promotion_status = "claim_promoted"
            rejection_code = ""
        records.append(ObservationPromotionRecordV1(
            observation_id=observation_id,
            obligation_id=obligation_id,
            tool_name=tool_name,
            status=promotion_status,
            evidence_lane=evidence_lane,
            source_authority=str(_value(observation, "source_authority", "") or ""),
            observation_refs=refs,
            behavior_node_ids=node_ids,
            packet_ids=packet_ids,
            fact_ids=fact_ids,
            claim_ids=claim_ids,
            rejection_code=rejection_code,
        ))
    return ObservationPromotionLedgerV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        records=tuple(records),
    )


__all__ = [
    "PromotionStatusV1",
    "EvidenceLaneV1",
    "ObservationPromotionRecordV1",
    "ObservationPromotionLedgerV1",
    "build_observation_promotion_ledger",
]
