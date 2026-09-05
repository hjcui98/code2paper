"""Deterministic shared LLM projection for Formalizer and Writer.

Enforces Invariant I8: Shared Context Must Be Provably Identical.
Formalizer and Writer receive byte-identical shared technical payloads for each mechanism.
Role-specific tasks (e.g. formalize vs write_method) may differ in consumer_request_digest,
but the shared_payload_digest and payload bytes MUST remain identical.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

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
    shared_slice_payload_record,
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

    # Keep the complete paper annotation, including source memberships and
    # atom contracts.  A projection that retained only detail ids/roles was a
    # second lossy compiler and made downstream ownership impossible to audit.
    ordered_details: list[dict[str, Any]] = [
        detail.model_dump(mode="json") for detail in context.details
    ]

    # Project edges
    edges: list[dict[str, Any]] = [e.model_dump(mode="json") for e in context.edges]

    # Project configurations from evidence closure
    closure = context.evidence_closure
    operations: list[dict[str, Any]] = [
        operation.model_dump(mode="json")
        for operation in closure.operation_nodes
    ]
    operation_dispositions: list[dict[str, Any]] = [
        disposition.model_dump(mode="json")
        for disposition in closure.operation_dispositions
    ]
    configurations: list[dict[str, Any]] = [
        dict(item) for item in closure.configuration_bindings
    ]

    # Exact evidence
    exact_evidence: list[dict[str, Any]] = []
    for i, span_id in enumerate(closure.exact_span_ids):
        exact_evidence.append({
            "span_id": span_id,
            "excerpt": (
                closure.exact_excerpts[i]
                if i < len(closure.exact_excerpts)
                else ""
            ),
            "source_context_digest": context.source_context_digest,
        })

    return MechanismContextViewV1(
        mechanism_id=context.mechanism_id,
        scientific_goal=scientific_goal,
        author_intent=author_intent,
        ordered_details=tuple(ordered_details),
        operations=tuple(operations),
        operation_dispositions=tuple(operation_dispositions),
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

    all_details = list(view.ordered_details)
    core_details = [d for d in all_details if d.get("importance") == "core"]
    supporting_details = [d for d in all_details if d.get("importance") != "core"]
    cap = max(1, int(max_supporting_per_slice))

    # Slice zero is the canonical core view.  Supporting details are chunked,
    # but no detail or evidence is silently discarded when the nominal slice
    # budget is reached: the final slice becomes an explicitly marked bounded
    # remainder.  This preserves the lossless closure while making pressure
    # visible to the caller.
    detail_chunks: list[list[dict[str, Any]]] = [list(core_details)]
    detail_chunks[0].extend(supporting_details[:cap])
    remaining = supporting_details[cap:]
    while remaining:
        detail_chunks.append(remaining[:cap])
        remaining = remaining[cap:]

    evidence = [
        item for item in view.exact_evidence
        if isinstance(item, dict) and str(item.get("span_id") or "").strip()
    ]
    evidence_by_id = {
        str(item["span_id"]): item for item in evidence
    }
    # One slice per evidence page is required even when all details fit in
    # slice zero. Evidence is lossless and therefore cannot be dropped
    # because there are fewer detail chunks.
    evidence_chunk_count = max(1, (len(evidence) + 9) // 10)
    target_chunk_count = max(len(detail_chunks), evidence_chunk_count)
    while len(detail_chunks) < target_chunk_count:
        detail_chunks.append([])
    all_core_ids = tuple(
        str(item.get("detail_id")) for item in core_details
        if str(item.get("detail_id") or "").strip()
    )
    detail_ids_by_chunk = [
        tuple(
            str(item.get("detail_id")) for item in chunk
            if str(item.get("detail_id") or "").strip()
        )
        for chunk in detail_chunks
    ]

    # Detail source memberships identify which operation/evidence records
    # belong in a materialized slice.  The full view metadata remains present
    # in every slice so each consumer can validate provenance without a
    # role-specific reconstruction.
    all_edges = list(view.edges)
    all_operations: dict[str, dict[str, Any]] = {}
    missing_operation_ids: set[str] = set()
    for operation in getattr(view, "operations", ()) or ():
        operation_dict = dict(operation)
        operation_id = str(operation_dict.get("operation_id") or "")
        if operation_id:
            all_operations[operation_id] = operation_dict
    for detail in all_details:
        for op_id in detail.get("source_operation_ids", ()) or ():
            operation_id = str(op_id).strip()
            if not operation_id:
                continue
            if operation_id not in all_operations:
                # A source operation reference without a materialized operation
                # is an integrity failure, not permission to synthesize an
                # empty fact-shaped placeholder.  Keep the absence explicit in
                # the shared payload so both consumers see the same boundary.
                missing_operation_ids.add(operation_id)
                continue
            all_operations[operation_id].setdefault("source_detail_ids", [])
            if str(detail.get("detail_id")) not in all_operations[operation_id]["source_detail_ids"]:
                all_operations[operation_id]["source_detail_ids"].append(str(detail.get("detail_id")))

    # Partition every materialized operation exactly once.  Operations with a
    # Detail are delivered with that Detail; terminally unresolved or
    # otherwise unowned operations are appended to the final bounded slice.
    # The old projection selected operations only through Detail references,
    # which made an explicitly unresolved closure node disappear before either
    # consumer could surface it.
    operation_ids_by_chunk: list[list[str]] = []
    assigned_operation_ids: set[str] = set()
    for chunk in detail_chunks:
        selected_ids = {
            str(op_id).strip()
            for detail in chunk
            for op_id in (detail.get("source_operation_ids", ()) or ())
            if str(op_id).strip()
        }
        selected_ids = {
            op_id for op_id in selected_ids if op_id in all_operations
        }
        operation_ids_by_chunk.append(sorted(selected_ids))
        assigned_operation_ids.update(selected_ids)
    unassigned_operation_ids = sorted(set(all_operations) - assigned_operation_ids)
    if unassigned_operation_ids:
        operation_ids_by_chunk[-1].extend(unassigned_operation_ids)

    slices: list[MechanismContextSliceV1] = []
    evidence_chunk_size = 10
    for slice_idx, (chunk, detail_ids) in enumerate(zip(detail_chunks, detail_ids_by_chunk)):
        selected_ids = set(detail_ids)
        selected_evidence = evidence[
            slice_idx * evidence_chunk_size : (slice_idx + 1) * evidence_chunk_size
        ]
        if slice_idx == 0 and len(evidence) > evidence_chunk_size:
            # Core evidence is never omitted merely because the first slice
            # contains many core details.  Subsequent slices still carry the
            # remaining exact evidence records.
            selected_evidence = evidence[:evidence_chunk_size]
        selected_edges = [
            edge for edge in all_edges
            if str(edge.get("source_detail_id") or "") in selected_ids
            or str(edge.get("target_detail_id") or "") in selected_ids
        ]
        payload = {
            "mechanism_id": view.mechanism_id,
            "slice_index": slice_idx,
            "source_context_digest": view.source_context_digest,
            "view_digest": view.view_digest,
            "scientific_goal": dict(view.scientific_goal),
            "author_intent": dict(view.author_intent),
            "details": [dict(item) for item in chunk],
            "operations": [
                dict(all_operations[op_id])
                for op_id in operation_ids_by_chunk[slice_idx]
                if op_id in all_operations
            ],
            "operation_dispositions": [
                dict(item)
                for item in view.operation_dispositions
                if str(item.get("operation_id") or "") in set(
                    operation_ids_by_chunk[slice_idx]
                )
            ],
            "edges": [dict(item) for item in selected_edges],
            "configurations": [dict(item) for item in view.configurations],
            "exact_evidence": [dict(item) for item in selected_evidence],
            "unresolved_items": list(view.unresolved_items),
            "missing_operation_ids": sorted(missing_operation_ids),
            "core_detail_ids": list(all_core_ids),
            "budget_exhausted": len(detail_chunks) > max_slices and slice_idx >= max_slices - 1,
        }
        slices.append(  # type: ignore[arg-type]
            MechanismContextSliceV1(
                mechanism_id=view.mechanism_id,
                slice_index=slice_idx,
                detail_ids=detail_ids,
                exact_evidence_ids=tuple(
                    str(item.get("span_id")) for item in selected_evidence
                ),
                view_digest=view.view_digest,
                technical_payload=payload,
                core_detail_ids=all_core_ids,
            )
        )

    if not slices:
        slices.append(MechanismContextSliceV1(
            mechanism_id=view.mechanism_id,
            slice_index=0,
            detail_ids=(),
            exact_evidence_ids=(),
            view_digest=view.view_digest,
            technical_payload={
                "mechanism_id": view.mechanism_id,
                "slice_index": 0,
                "source_context_digest": view.source_context_digest,
                "view_digest": view.view_digest,
                "scientific_goal": dict(view.scientific_goal),
                "author_intent": dict(view.author_intent),
                "details": [],
                "operations": [],
                "operation_dispositions": [],
                "edges": [],
                "configurations": [dict(item) for item in view.configurations],
                "exact_evidence": [],
                "unresolved_items": list(view.unresolved_items),
                "missing_operation_ids": [],
                "core_detail_ids": [],
                "budget_exhausted": False,
            },
            core_detail_ids=(),
        ))

    shared_digest = compute_shared_payload_digest(tuple(slices))
    return tuple(
        slice_obj.model_copy(update={"shared_payload_digest": shared_digest})
        for slice_obj in slices
    )


def serialize_shared_mechanism_payload(
    slices: Sequence[MechanismContextSliceV1],
) -> bytes:
    """Canonical deterministic serialization of shared payload for LLM consumption."""
    return canonical_json_bytes([
        shared_slice_payload_record(slice_obj) for slice_obj in slices
    ])


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

    for label, slices in (("Formalizer", formalizer_slices), ("Writer", writer_slices)):
        if tuple(item.slice_index for item in slices) != tuple(range(len(slices))):
            raise ValueError(
                f"Invariant I8 violation: {label} slice indices are not contiguous and ordered"
            )
        for item in slices:
            expected_slice_digest = compute_slice_digest(item)
            if item.slice_digest != expected_slice_digest:
                raise ValueError(
                    f"Invariant I8 violation: {label} slice digest mismatch at index {item.slice_index}"
                )
            payload = shared_slice_payload_record(item)
            materialized = payload.get("technical_payload")
            if not isinstance(materialized, Mapping):
                raise ValueError(
                    f"Invariant I8 violation: {label} slice has no materialized technical payload "
                    f"at index {item.slice_index}"
                )
            payload_detail_ids = tuple(
                str(row.get("detail_id"))
                for row in (materialized.get("details") or ())
                if isinstance(row, Mapping) and str(row.get("detail_id") or "").strip()
            )
            if payload_detail_ids != tuple(item.detail_ids):
                raise ValueError(
                    f"Invariant I8 violation: {label} materialized detail IDs differ at index {item.slice_index}"
                )

    f_digest = compute_shared_payload_digest(tuple(formalizer_slices))
    w_digest = compute_shared_payload_digest(tuple(writer_slices))

    if f_digest != w_digest:
        raise ValueError(
            f"Invariant I8 violation: shared_payload_digest mismatch: {f_digest} != {w_digest}"
        )

    for label, slices, expected in (
        ("Formalizer", formalizer_slices, f_digest),
        ("Writer", writer_slices, w_digest),
    ):
        declared = tuple(
            str(getattr(item, "shared_payload_digest", "") or "")
            for item in slices
        )
        if any(declared) and any(value != expected for value in declared):
            raise ValueError(
                f"Invariant I8 violation: {label} slice declared shared payload digest differs"
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

    f_declared_core = tuple(
        str(item) for slice_obj in formalizer_slices
        for item in (getattr(slice_obj, "core_detail_ids", ()) or ())
    )
    w_declared_core = tuple(
        str(item) for slice_obj in writer_slices
        for item in (getattr(slice_obj, "core_detail_ids", ()) or ())
    )
    if f_declared_core != w_declared_core:
        raise ValueError(
            "Invariant I8 violation: Formalizer and Writer core detail sets differ."
        )

    # The digest must be derived from the exact materialized payload and not
    # merely be a self-reported field on an ID index.  Compare the payload
    # records one more time after all structural checks so a replacement slice
    # with copied metadata cannot pass the identity gate.
    if any(
        shared_slice_payload_record(left) != shared_slice_payload_record(right)
        for left, right in zip(formalizer_slices, writer_slices)
    ) or len(formalizer_slices) != len(writer_slices):
        raise ValueError(
            "Invariant I8 violation: materialized shared slice records differ"
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
