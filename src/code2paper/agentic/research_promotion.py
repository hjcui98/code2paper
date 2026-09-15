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
    "superseded",
    "not_selected",
    "deferred",
]
EvidenceLaneV1 = Literal[
    "executable_behavior",
    "configuration",
    "discovery_hint",
]

INCOMPLETE_PROMOTION_STATUSES: frozenset[str] = frozenset({
    "observed_unpromoted",
    "behavior_built",
    "packet_promoted",
    "fact_promoted",
})
TERMINAL_PROMOTION_DISPOSITIONS: frozenset[str] = frozenset({
    "claim_promoted",
    "discovered_only",
    "rejected",
    "superseded",
    "not_selected",
    "deferred",
})


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
    disposition_reason: str = ""
    superseding_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    superseding_compile_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ObservationPromotionRecordV1":
        if not self.observation_id.strip() or not self.obligation_id.strip():
            raise ValueError("promotion record requires observation and obligation ids")
        if self.status in {"observed_unpromoted", "rejected"} and not self.rejection_code.strip():
            raise ValueError("unpromoted observation requires a typed rejection code")
        if self.status in {"superseded", "not_selected", "deferred"} and not (
            self.disposition_reason.strip()
        ):
            raise ValueError(
                "terminal observation disposition requires a disposition_reason"
            )
        if self.status == "superseded" and not (
            self.superseding_claim_ids or self.superseding_compile_digest.strip()
        ):
            raise ValueError(
                "superseded observation requires a superseding claim or compile digest"
            )
        if self.status == "claim_promoted" and not (
            self.behavior_node_ids and self.packet_ids and self.fact_ids and self.claim_ids
        ):
            raise ValueError("claim promotion requires the complete graph/packet/fact/claim chain")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("observation promotion record digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "ObservationPromotionRecordV1":
        """Reject validator-skipping updates that would stale the digest.

        Status transitions must go through ``_replace_promotion_record`` so
        the record is revalidated and ``content_digest`` is recomputed.
        """

        if update:
            raise ValueError(
                "ObservationPromotionRecordV1 updates must be revalidated, "
                "not applied through model_copy(update=...)"
            )
        return super().model_copy(update=update, deep=deep)


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


def promotion_record_blocks_strict_research(
    record: Any,
    agenda_item: Any | None = None,
) -> bool:
    """Strict/Verified lane: every incomplete observation blocks.

    The strict lane deliberately ignores Candidate dispositions.  A record
    explicitly superseded or not selected remains an audit fact there, but
    strict research does not close on Candidate convenience.
    """

    return str(_value(record, "status", "") or "") in INCOMPLETE_PROMOTION_STATUSES


def promotion_record_blocks_candidate(
    record: Any,
    handoff: Any | None = None,
    agenda_item: Any | None = None,
) -> bool:
    """Candidate lane: explicit dispositions may be consumed, claims may not.

    ``superseded``/``not_selected``/``deferred`` records carry an explicit
    terminal disposition and do not block Candidate generation.  An
    incomplete record still blocks when it is bound to the authenticated
    handoff lineage or belongs to a must-cover obligation in the Candidate
    lane.  Non-core deferred work and obligations outside the handoff are
    warnings/review items, not Candidate blockers.
    """

    status = str(_value(record, "status", "") or "")
    if status not in INCOMPLETE_PROMOTION_STATUSES:
        return False
    if str(_value(record, "disposition_reason", "") or "").strip():
        # An explicit terminal disposition owns this record even if a legacy
        # status string was not migrated.
        return False
    obligation_id = str(_value(record, "obligation_id", "") or "")
    if handoff is not None and bool(_value(handoff, "eligible", False)):
        bound_claim_ids = {
            str(_value(binding, "claim_id", "") or "").strip()
            for binding in (_value(handoff, "claim_bindings", ()) or ())
            if str(_value(binding, "claim_id", "") or "").strip()
        }
        record_claim_ids = {
            str(value).strip()
            for value in (_value(record, "claim_ids", ()) or ())
            if str(value).strip()
        }
        if record_claim_ids and record_claim_ids & bound_claim_ids:
            return True
        consumed = {
            str(value).strip()
            for value in (_value(handoff, "must_cover_obligation_ids", ()) or ())
            if str(value).strip()
        }
        if obligation_id not in consumed:
            return False
        if agenda_item is not None and str(
            _value(agenda_item, "priority", "must_cover") or "must_cover"
        ) != "must_cover":
            return False
    return True


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


def _candidate_match_index(
    refs: set[str],
    spans: set[str],
    *,
    symbols: Iterable[Any] = (),
    nodes: Iterable[Any] = (),
) -> tuple[tuple[tuple[str, int, int], ...], frozenset[str], bool]:
    """Resolve one observation's identity once for the whole behavior graph.

    The identity binding of an observation does not depend on which candidate
    node is being tested.  ``_node_matches`` previously repeated the full
    node-index resolution for every node, which made promotion-ledger
    construction quadratic in behavior-graph size and could stall a live
    research turn for minutes once the graph grew.  The returned tuple is
    ``(authoritative_ranges, matched_node_ids, rejected)``.
    """

    symbol_items = tuple(symbols)
    node_items = tuple(nodes)
    candidate_refs = (*sorted(refs), *sorted(spans))
    authoritative_ranges: list[tuple[str, int, int]] = []
    for ref in candidate_refs:
        if _location_ref_parts(ref) is None:
            continue
        location_binding = resolve_candidate_binding(
            ref,
            symbols=symbol_items,
            behavior_nodes=(),
            exact_span_ids=(),
            mode="promotion",
        )
        # A failed/ambiguous typed location must not be rescued by the
        # observation's independent broad span ref.  This is the promotion
        # side of the same identity gate used by acquisition and compile.
        if location_binding.ambiguous or location_binding.rejection_code:
            return (), frozenset(), True
        authoritative_ranges.extend(location_binding.symbol_ranges)
    matched_node_ids: set[str] = set()
    for ref in candidate_refs:
        binding = resolve_candidate_binding(
            ref,
            symbols=symbol_items,
            behavior_nodes=node_items,
            exact_span_ids=spans,
            mode="promotion",
        )
        if binding.ambiguous or binding.rejection_code:
            continue
        matched_node_ids.update(binding.behavior_node_ids)
    return (
        tuple(dict.fromkeys(authoritative_ranges)),
        frozenset(matched_node_ids),
        False,
    )


def _node_matches(
    node: Any,
    refs: set[str],
    spans: set[str],
    *,
    symbols: Iterable[Any] = (),
    nodes: Iterable[Any] = (),
    match_index: tuple[
        tuple[tuple[str, int, int], ...], frozenset[str], bool
    ] | None = None,
) -> bool:
    """Match one observation to a node through the shared identity resolver.

    Exact span ids are source intervals, not opaque strings.  A wide read
    such as ``span:file.py:180:250`` therefore binds statement-level nodes
    inside that interval, while a sibling outside the interval remains
    excluded.  ``resolve_candidate_binding`` also rejects ambiguous leaf
    symbols instead of silently widening to a path.  Callers that test many
    nodes for one observation pass a precomputed ``match_index`` from
    ``_candidate_match_index`` so the resolution runs once per observation.
    """

    node_id = str(_value(node, "node_id", "") or "")
    if match_index is None:
        match_index = _candidate_match_index(
            refs,
            spans,
            symbols=symbols,
            nodes=tuple(nodes) or (node,),
        )
    authoritative_ranges, matched_node_ids, rejected = match_index
    if rejected:
        return False
    node_interval = _span_interval(_value(node, "source_span_id", ""))
    if authoritative_ranges and node_interval is not None and not any(
        source_intervals_overlap(node_interval, item)
        for item in authoritative_ranges
    ):
        return False
    return bool(node_id) and node_id in matched_node_ids


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


def _compiled_promotion_lineage(compiled: Any) -> dict[str, Any] | None:
    """Return the frozen lineage of one compiled obligation.

    The promotion ledger uses this only to give an already-compiled
    obligation's older observations an explicit terminal disposition.  It
    never creates evidence: the packet/fact/claim ids already exist in the
    compiled sidecar and are copied as provenance.
    """

    if compiled is None:
        return None
    packet_set = _value(compiled, "packet_set", None)
    fact_set = _value(compiled, "fact_set", None)
    claim_set = _value(compiled, "claim_set", None)
    packets = tuple(_value(packet_set, "packets", ()) or ())
    facts = tuple(_value(fact_set, "facts", ()) or ())
    claims = tuple(_value(claim_set, "claims", ()) or ())
    claim_ids = tuple(dict.fromkeys(
        str(_value(claim, "claim_id", "") or "").strip()
        for claim in claims
        if str(_value(claim, "claim_id", "") or "").strip()
    ))
    if not claim_ids:
        return None
    fact_ids: set[str] = set()
    fact_claim_ids: dict[str, set[str]] = {}
    for claim in claims:
        claim_id = str(_value(claim, "claim_id", "") or "").strip()
        for value in (_value(claim, "fact_ids", ()) or ()):
            fact_id = str(value).strip()
            if not fact_id:
                continue
            fact_ids.add(fact_id)
            fact_claim_ids.setdefault(fact_id, set()).add(claim_id)
    if not fact_ids:
        return None
    packet_ids: set[str] = set()
    span_ids: set[str] = set()
    for packet in packets:
        packet_id = str(_value(packet, "packet_id", "") or "").strip()
        if packet_id:
            packet_ids.add(packet_id)
        span_ids.update(_span_ids(packet))
    for fact in facts:
        span_ids.update(_span_ids(fact))
    digest = str(_value(claim_set, "content_digest", "") or "").strip()
    return {
        "packet_ids": packet_ids,
        "fact_ids": fact_ids,
        "claim_ids": set(claim_ids),
        "fact_claim_ids": fact_claim_ids,
        "span_ids": span_ids,
        "digest": digest,
    }


def _replace_promotion_record(
    record: ObservationPromotionRecordV1,
    updates: Mapping[str, Any],
) -> ObservationPromotionRecordV1:
    """Return a terminal record with a freshly computed content digest.

    ``model_copy(update=...)`` skips validators and would leave the old
    ``content_digest`` in place, so the next ledger validation (checkpoint
    reload or Writer preadmission) would report a digest mismatch.  A JSON
    round-trip through ``model_validate`` recomputes the digest.
    """

    payload = record.model_dump(mode="json")
    payload.update(dict(updates))
    payload["content_digest"] = ""
    return ObservationPromotionRecordV1.model_validate(payload)


def _apply_terminal_promotion_dispositions(
    records: list[ObservationPromotionRecordV1],
    *,
    compiled_by_obligation: Mapping[str, Any],
    nodes: tuple[Any, ...],
    agenda_by_id: Mapping[str, Any],
) -> None:
    """Give older incomplete observations an explicit terminal disposition.

    Only obligations that already carry an authenticated compiled claim
    chain are touched.  An observation whose own facts were consumed by the
    compile is promoted; a behavior-only read that the compile replaced is
    superseded; alternative reads and searches are not-selected; non-core
    work is deferred.  A must-cover record that cannot be tied to the
    compiled lineage stays incomplete (fail-closed for its obligation).
    """

    node_span_ids = {
        str(_value(node, "node_id", "") or ""): str(
            _value(node, "source_span_id", "") or ""
        )
        for node in nodes
        if str(_value(node, "node_id", "") or "")
    }
    for index, record in enumerate(records):
        if record.status not in INCOMPLETE_PROMOTION_STATUSES:
            continue
        lineage = _compiled_promotion_lineage(
            compiled_by_obligation.get(record.obligation_id)
        )
        if lineage is None:
            continue
        agenda_item = agenda_by_id.get(record.obligation_id)
        record_spans = {
            span
            for span in (
                str(value).strip() for value in record.observation_refs
            )
            if span.startswith("span:")
        }
        consumed_node_ids = {
            node_id
            for node_id in record.behavior_node_ids
            if node_span_ids.get(node_id) in lineage["span_ids"]
        }
        if record.fact_ids and set(record.fact_ids) & lineage["fact_ids"]:
            matched_claim_ids = tuple(dict.fromkeys(
                claim_id
                for fact_id in record.fact_ids
                for claim_id in sorted(lineage["fact_claim_ids"].get(fact_id, ()))
            ))
            if matched_claim_ids:
                records[index] = _replace_promotion_record(record, {
                    "status": "claim_promoted",
                    "packet_ids": tuple(dict.fromkeys(
                        (*record.packet_ids, *sorted(lineage["packet_ids"]))
                    )),
                    "claim_ids": matched_claim_ids,
                    "rejection_code": "",
                })
                continue
            # The record's facts are part of the compiled lineage but the
            # claim mapping is incomplete: keep it open (fail-closed) rather
            # than inventing a promotion.
            continue
        if consumed_node_ids or (record_spans and record_spans & lineage["span_ids"]):
            records[index] = _replace_promotion_record(record, {
                "status": "superseded",
                "disposition_reason": "replaced_by_compiled_evidence",
                "superseding_claim_ids": tuple(sorted(lineage["claim_ids"])),
                "superseding_compile_digest": str(lineage["digest"]),
                "rejection_code": "",
            })
            continue
        if record.behavior_node_ids or record.evidence_lane in {
            "configuration",
            "discovery_hint",
        }:
            # A read/search/config observation the final compile did not
            # consume is an alternative, not evidence.
            records[index] = _replace_promotion_record(record, {
                "status": "not_selected",
                "disposition_reason": "observation_not_selected_for_compile",
                "rejection_code": "",
            })
            continue
        if agenda_item is not None and str(
            _value(agenda_item, "priority", "must_cover") or "must_cover"
        ) != "must_cover":
            records[index] = _replace_promotion_record(record, {
                "status": "deferred",
                "disposition_reason": "non_core_observation_deferred_to_review",
                "rejection_code": "",
            })
            continue
        if agenda_item is not None:
            # A must-cover executable probe that never bound to a behavior
            # node (a YAML read or a control-flow probe) and was not consumed
            # by the obligation's frozen compile is an alternative read, not
            # evidence.  Leaving it open would permanently block the Candidate
            # lane on a non-evidence observation even though the obligation's
            # support and strict terminal proof are evaluated from the
            # compiled claim chain.  Verified stays fail-closed because that
            # strict proof is unchanged.
            records[index] = _replace_promotion_record(record, {
                "status": "not_selected",
                "disposition_reason": "observation_not_selected_for_compile",
                "rejection_code": "",
            })


def remap_promotion_ledger_claim_ids(
    ledger: ObservationPromotionLedgerV1,
    claim_id_map: Mapping[str, str],
) -> ObservationPromotionLedgerV1:
    """Re-key claim lineage through the merged product claim identity map.

    Product evidence merges duplicate claims across obligations and can remap
    claim ids.  A ledger that downstream validation compares against that
    merged set must reference the same canonical ids; otherwise a handoff
    that was eligible against per-obligation compiles becomes unreproducible
    and the Candidate lane is blocked by an identity mismatch rather than by
    missing evidence.
    """

    if not claim_id_map:
        return ledger
    records: list[ObservationPromotionRecordV1] = []
    changed = False
    for record in ledger.records:
        claim_ids = tuple(dict.fromkeys(
            claim_id_map.get(str(value), str(value))
            for value in record.claim_ids
            if str(value).strip()
        ))
        superseding_claim_ids = tuple(dict.fromkeys(
            claim_id_map.get(str(value), str(value))
            for value in record.superseding_claim_ids
            if str(value).strip()
        ))
        if (
            claim_ids == record.claim_ids
            and superseding_claim_ids == record.superseding_claim_ids
        ):
            records.append(record)
            continue
        changed = True
        records.append(_replace_promotion_record(record, {
            "claim_ids": claim_ids,
            "superseding_claim_ids": superseding_claim_ids,
        }))
    if not changed:
        return ledger
    remapped = ObservationPromotionLedgerV1(
        repo_snapshot_id=ledger.repo_snapshot_id,
        project_tree_hash=ledger.project_tree_hash,
        records=tuple(records),
    )
    return ObservationPromotionLedgerV1.model_validate_json(remapped.model_dump_json())


def build_observation_promotion_ledger(
    *,
    observations: Iterable[Any] = (),
    behavior_graph: Any | None = None,
    compiled_by_obligation: Mapping[str, Any] | None = None,
    symbols: Iterable[Any] = (),
    agenda_items: Iterable[Any] = (),
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> ObservationPromotionLedgerV1:
    """Classify each observation at the strongest validated promotion stage."""

    compiled_by_obligation = compiled_by_obligation or {}
    nodes = tuple(getattr(behavior_graph, "nodes", ()) or ()) if behavior_graph is not None else ()
    symbol_items = tuple(symbols)
    agenda_by_id = {
        str(_value(item, "obligation_id", "") or ""): item
        for item in agenda_items
        if str(_value(item, "obligation_id", "") or "")
    }
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
        elif tool_name in {
            "search_symbols",
            "search_code",
            "find_entrypoints",
            "list_repository_tree",
            "search_semantic_hints",
        }:
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
        match_index = _candidate_match_index(
            ref_set,
            spans,
            symbols=symbol_items,
            nodes=nodes,
        )
        node_ids = tuple(dict.fromkeys(
            str(_value(node, "node_id", "") or "")
            for node in nodes
            if _node_matches(
                node,
                ref_set,
                spans,
                symbols=symbol_items,
                nodes=nodes,
                match_index=match_index,
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

    _apply_terminal_promotion_dispositions(
        records,
        compiled_by_obligation=compiled_by_obligation,
        nodes=nodes,
        agenda_by_id=agenda_by_id,
    )

    # A compile transaction is itself an evidence-plane boundary.  In some
    # deterministic paths the source read that produced a packet is carried
    # by the compiler transaction rather than a separate ResearchObservation;
    # leaving that claim set absent from the promotion ledger would make a
    # valid per-obligation compile look unpromoted.  Record only the already
    # materialized packet/fact/claim chain, and only when its source spans map
    # to owned behavior nodes.  This creates provenance, not evidence or
    # claims, and therefore cannot turn an incomplete compile into support.
    existing_promoted: dict[str, set[str]] = {}
    for record in records:
        if record.status != "claim_promoted":
            continue
        existing_promoted.setdefault(record.obligation_id, set()).update(
            record.claim_ids
        )
    for obligation_id, compiled in sorted(compiled_by_obligation.items()):
        packet_set = _value(compiled, "packet_set", None)
        fact_set = _value(compiled, "fact_set", None)
        claim_set = _value(compiled, "claim_set", None)
        packets = tuple(_value(packet_set, "packets", ()) or ())
        facts = tuple(_value(fact_set, "facts", ()) or ())
        claims = tuple(_value(claim_set, "claims", ()) or ())
        claim_ids = tuple(dict.fromkeys(
            str(_value(claim, "claim_id", "") or "").strip()
            for claim in claims
            if str(_value(claim, "claim_id", "") or "").strip()
        ))
        missing_claim_ids = tuple(
            claim_id for claim_id in claim_ids
            if claim_id not in existing_promoted.get(str(obligation_id), set())
        )
        if not missing_claim_ids:
            continue
        packet_ids = tuple(dict.fromkeys(
            str(_value(packet, "packet_id", "") or "").strip()
            for packet in packets
            if str(_value(packet, "packet_id", "") or "").strip()
        ))
        fact_ids = tuple(dict.fromkeys(
            str(_value(fact, "fact_id", "") or "").strip()
            for fact in facts
            if str(_value(fact, "fact_id", "") or "").strip()
        ))
        source_span_ids = set(
            str(_value(span, "span_id", "") or "").strip()
            for packet in packets
            for span in (tuple(_value(packet, "spans", ()) or ()))
            if str(_value(span, "span_id", "") or "").strip()
        )
        for fact in facts:
            source_span_ids.update(
                str(value).strip()
                for field in ("direct_span_ids", "relation_span_ids")
                for value in (_value(fact, field, ()) or ())
                if str(value).strip()
            )
        behavior_node_ids = tuple(dict.fromkeys(
            str(_value(node, "node_id", "") or "").strip()
            for node in nodes
            if str(_value(node, "node_id", "") or "").strip()
            and str(_value(node, "source_span_id", "") or "").strip()
            in source_span_ids
        ))
        if not behavior_node_ids or not packet_ids or not fact_ids:
            # The ordinary observation records remain the only promotion
            # authority when this compile cannot prove its own source lineage.
            continue
        claim_digest = str(_value(claim_set, "content_digest", "") or "").strip()
        compile_observation_id = (
            f"compile_candidate:{obligation_id}:{claim_digest or digest_json(claim_ids)}"
        )
        if any(record.observation_id == compile_observation_id for record in records):
            continue
        records.append(ObservationPromotionRecordV1(
            observation_id=compile_observation_id,
            obligation_id=str(obligation_id),
            tool_name="compile_candidate",
            status="claim_promoted",
            evidence_lane="executable_behavior",
            source_authority="compiled_evidence",
            observation_refs=tuple(sorted(source_span_ids)),
            behavior_node_ids=behavior_node_ids,
            packet_ids=packet_ids,
            fact_ids=fact_ids,
            claim_ids=missing_claim_ids,
        ))
    ledger = ObservationPromotionLedgerV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        records=tuple(records),
    )
    # Construction recomputes each record digest, but only a full JSON
    # round-trip proves that the ledger digest and every nested record digest
    # agree with the bytes a checkpoint reload or Writer preadmission will
    # parse.  Fail closed here instead of leaving a mismatched ledger behind.
    return ObservationPromotionLedgerV1.model_validate_json(ledger.model_dump_json())


__all__ = [
    "PromotionStatusV1",
    "EvidenceLaneV1",
    "ObservationPromotionRecordV1",
    "ObservationPromotionLedgerV1",
    "build_observation_promotion_ledger",
    "remap_promotion_ledger_claim_ids",
]
