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

PromotionStatusV1 = Literal[
    "discovered_only",
    "observed_unpromoted",
    "behavior_built",
    "packet_promoted",
    "fact_promoted",
    "claim_promoted",
    "rejected",
]


class ObservationPromotionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    obligation_id: str
    tool_name: str
    status: PromotionStatusV1
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


def _node_matches(node: Any, refs: set[str], spans: set[str]) -> bool:
    node_id = str(_value(node, "node_id", "") or "")
    symbol_id = str(_value(node, "symbol_id", "") or "")
    span_id = str(_value(node, "source_span_id", "") or "")
    return bool({node_id, symbol_id}.intersection(refs) or span_id in spans)


def build_observation_promotion_ledger(
    *,
    observations: Iterable[Any] = (),
    behavior_graph: Any | None = None,
    compiled_by_obligation: Mapping[str, Any] | None = None,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> ObservationPromotionLedgerV1:
    """Classify each observation at the strongest validated promotion stage."""

    compiled_by_obligation = compiled_by_obligation or {}
    nodes = tuple(getattr(behavior_graph, "nodes", ()) or ()) if behavior_graph is not None else ()
    records: list[ObservationPromotionRecordV1] = []
    for observation in observations:
        observation_id = str(_value(observation, "observation_id", "") or "").strip()
        obligation_id = str(_value(observation, "obligation_id", "") or "").strip()
        if not observation_id or not obligation_id:
            continue
        tool_name = str(_value(observation, "tool_name", "") or "")
        status_value = str(_value(observation, "status", "") or "")
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
            if _node_matches(node, ref_set, spans) and str(_value(node, "node_id", "") or "")
        ))
        compiled = compiled_by_obligation.get(obligation_id)
        packet_set = _value(compiled, "packet_set", None)
        fact_set = _value(compiled, "fact_set", None)
        claim_set = _value(compiled, "claim_set", None)
        packet_ids = tuple(dict.fromkeys(
            str(_value(packet, "packet_id", "") or "")
            for packet in (_value(packet_set, "packets", ()) or ())
            if str(_value(packet, "packet_id", "") or "")
        ))
        fact_ids = tuple(dict.fromkeys(
            str(_value(fact, "fact_id", "") or "")
            for fact in (_value(fact_set, "facts", ()) or ())
            if str(_value(fact, "fact_id", "") or "")
        ))
        claim_ids = tuple(dict.fromkeys(
            str(_value(claim, "claim_id", "") or "")
            for claim in (_value(claim_set, "claims", ()) or ())
            if str(_value(claim, "claim_id", "") or "")
        ))
        exact_read = tool_name in {"read_symbol", "read_code_span", "build_behavior_subgraph"}
        if tool_name in {"search_symbols", "search_code", "find_entrypoints"}:
            promotion_status: PromotionStatusV1 = "discovered_only"
            rejection_code = "discovery_refs_are_not_evidence"
        elif status_value != "success":
            promotion_status = "rejected"
            rejection_code = "observation_failed"
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
    "ObservationPromotionRecordV1",
    "ObservationPromotionLedgerV1",
    "build_observation_promotion_ledger",
]
