"""Deterministic shared LLM projection for Formalizer and Writer.

Enforces Invariant I8: Shared Context Must Be Provably Identical.
Formalizer and Writer receive byte-identical shared technical payloads for each mechanism.
Role-specific tasks (e.g. formalize vs write_method) may differ in consumer_request_digest,
but the shared_payload_digest and payload bytes MUST remain identical.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from code2paper.agentic.mechanism_context_models import (
    MechanismContextSliceV1,
    MechanismContextV1,
    MechanismContextViewV1,
    MechanismDetailV1,
    canonical_json_bytes,
    compute_shared_payload_digest,
    compute_slice_digest,
    compute_view_digest,
    sha256_digest,
)

MAX_SUPPORTING_DETAILS_PER_SLICE = 24
MAX_EXACT_EXCERPT_TOKENS_PER_SLICE = 12_000
MAX_MECHANISM_SLICES = 4


def build_mechanism_context_view(context: MechanismContextV1) -> MechanismContextViewV1:
    """Construct the consumer-neutral scientific projection of a MechanismContextV1."""

    # Extract scientific goal
    scientific_goal = {
        "mechanism_id": context.mechanism_id,
        "mechanism_name": context.mechanism_name,
        "scientific_role": context.scientific_role,
        "reader_question": context.reader_question,
        "purpose": context.purpose,
        "importance": context.importance,
    }

    # Extract author intent
    author_intent = {
        "statements": list(context.author_statements),
        "notation_hints": list(context.notation_hints),
        "story_node_ids": list(context.story_node_ids),
        "brief_ids": list(context.brief_ids),
        "facet_ids": list(context.facet_ids),
    }

    # Project ordered details preserving core details unconditionally
    ordered_details: list[dict[str, Any]] = []
    for detail in context.details:
        d_dict = {
            "detail_id": detail.detail_id,
            "role": detail.role,
            "importance": detail.importance,
            "claim_kind": detail.claim_kind,
            "evidence_authority": detail.evidence_authority,
            "publication_policy": detail.publication_policy,
            "semantic_atom": detail.semantic_atom,
            "predicate": detail.predicate,
            "operands": list(detail.operands),
            "result": detail.result,
            "conditions": list(detail.conditions),
            "polarity": detail.polarity,
            "active_path_status": detail.active_path_status,
            "source_operation_ids": list(detail.source_operation_ids),
            "source_span_ids": list(detail.source_span_ids),
            "witness_atom_ids": [a.atom_id for a in detail.witness_atoms],
        }
        ordered_details.append(d_dict)

    # Project edges
    edges: list[dict[str, Any]] = [
        {
            "edge_id": e.edge_id,
            "source_detail_id": e.source_detail_id,
            "target_detail_id": e.target_detail_id,
            "relation": e.relation,
        }
        for e in context.edges
    ]

    # Project configurations from evidence closure
    closure = context.evidence_closure
    configurations: list[dict[str, Any]] = list(closure.configuration_bindings)

    # Exact evidence
    exact_evidence: list[dict[str, Any]] = [
        {
            "span_id": sp_id,
            "excerpt": closure.exact_excerpts[i] if i < len(closure.exact_excerpts) else "",
        }
        for i, sp_id in enumerate(closure.exact_span_ids)
    ]

    return MechanismContextViewV1(
        mechanism_id=context.mechanism_id,
        scientific_goal=scientific_goal,
        author_intent=author_intent,
        ordered_details=tuple(ordered_details),
        edges=tuple(edges),
        configurations=tuple(configurations),
        exact_evidence=tuple(exact_evidence),
        unresolved_items=context.unresolved_items,
        source_context_digest=context.source_context_digest,
    )


def build_mechanism_context_slices(
    view: MechanismContextViewV1 | MechanismContextV1,
    *,
    max_supporting_per_slice: int = MAX_SUPPORTING_DETAILS_PER_SLICE,
    max_slices: int = MAX_MECHANISM_SLICES,
) -> tuple[MechanismContextSliceV1, ...]:
    """Divide MechanismContextView into ordered slices with all core details preserved."""
    if not isinstance(view, MechanismContextViewV1):
        view = build_mechanism_context_view(view)

    all_details = view.ordered_details
    core_details = [d for d in all_details if d.get("importance") == "core"]
    supporting_details = [d for d in all_details if d.get("importance") != "core"]

    # All core details must be present in slice 0
    slice_0_detail_ids = [d["detail_id"] for d in core_details]
    remaining_supporting = list(supporting_details)

    # Fill slice 0 up to max_supporting_per_slice
    initial_supporting = remaining_supporting[:max_supporting_per_slice]
    slice_0_detail_ids.extend(d["detail_id"] for d in initial_supporting)
    remaining_supporting = remaining_supporting[max_supporting_per_slice:]

    slices: list[MechanismContextSliceV1] = []
    evidence_ids = [e["span_id"] for e in view.exact_evidence if "span_id" in e]

    s0 = MechanismContextSliceV1(
        mechanism_id=view.mechanism_id,
        slice_index=0,
        detail_ids=tuple(slice_0_detail_ids),
        exact_evidence_ids=tuple(evidence_ids[:10]),
        view_digest=view.view_digest,
    )
    slices.append(s0)

    slice_idx = 1
    while remaining_supporting and slice_idx < max_slices:
        chunk = remaining_supporting[:max_supporting_per_slice]
        remaining_supporting = remaining_supporting[max_supporting_per_slice:]
        s = MechanismContextSliceV1(
            mechanism_id=view.mechanism_id,
            slice_index=slice_idx,
            detail_ids=tuple(d["detail_id"] for d in chunk),
            exact_evidence_ids=tuple(evidence_ids[10 * slice_idx: 10 * (slice_idx + 1)]),
            view_digest=view.view_digest,
        )
        slices.append(s)
        slice_idx += 1

    return tuple(slices)


def serialize_shared_mechanism_payload(
    slices: Sequence[MechanismContextSliceV1],
) -> bytes:
    """Canonical deterministic serialization of shared payload for LLM consumption."""
    return canonical_json_bytes([s.model_dump(mode="json") for s in slices])


def assert_consumer_shared_payload_identity(
    formalizer_slices: Sequence[MechanismContextSliceV1],
    writer_slices: Sequence[MechanismContextSliceV1],
) -> None:
    """Verify that Formalizer and Writer receive byte-identical shared payload."""
    f_bytes = serialize_shared_mechanism_payload(formalizer_slices)
    w_bytes = serialize_shared_mechanism_payload(writer_slices)

    if f_bytes != w_bytes:
        raise ValueError(
            "Invariant I8 violation: Formalizer and Writer shared payload bytes differ!"
        )

    f_digest = compute_shared_payload_digest(tuple(formalizer_slices))
    w_digest = compute_shared_payload_digest(tuple(writer_slices))

    if f_digest != w_digest:
        raise ValueError(
            f"Invariant I8 violation: shared_payload_digest mismatch: {f_digest} != {w_digest}"
        )

    f_core = [
        did for s in formalizer_slices for did in s.detail_ids
    ]
    w_core = [
        did for s in writer_slices for did in s.detail_ids
    ]
    if f_core != w_core:
        raise ValueError(
            "Invariant I8 violation: consumer detail IDs sequence mismatch."
        )


__all__ = [
    "MAX_SUPPORTING_DETAILS_PER_SLICE",
    "MAX_EXACT_EXCERPT_TOKENS_PER_SLICE",
    "MAX_MECHANISM_SLICES",
    "build_mechanism_context_view",
    "build_mechanism_context_slices",
    "serialize_shared_mechanism_payload",
    "assert_consumer_shared_payload_identity",
]
