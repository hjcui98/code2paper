from __future__ import annotations

import pytest
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)
from code2paper.agentic.mechanism_context_projection import (
    assert_consumer_shared_payload_identity,
    build_mechanism_context_slices,
    build_mechanism_context_view,
    serialize_shared_mechanism_payload,
)


def _make_context() -> MechanismContextV1:
    op1 = EvidenceOperationV1(
        operation_id="op:1",
        predicate="encode",
        operands=("x",),
        result="h",
        source_span_id="span:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:1",
        mechanism_id="mech:mamba",
        operation_nodes=(op1,),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:1",
                disposition="absorbed_by_detail",
                detail_ids=("d:1",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:1",),
    )
    d1 = MechanismDetailV1(
        detail_id="d:1",
        primary_mechanism_id="mech:mamba",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="encode x to h",
        source_operation_ids=("op:1",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:1",
                atom_kind="operation",
                semantic_anchor="encode",
                source_operation_ids=("op:1",),
            ),
        ),
    )
    return MechanismContextV1(
        mechanism_id="mech:mamba",
        mechanism_name="Mamba",
        scientific_role="encoding",
        reader_question="How?",
        purpose="SSM",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:1",),
        details=(d1,),
    )


def test_shared_projection_and_slice_identity() -> None:
    ctx = _make_context()
    view = build_mechanism_context_view(ctx)
    assert view.mechanism_id == "mech:mamba"
    assert len(view.ordered_details) == 1
    assert view.ordered_details[0]["detail_id"] == "d:1"

    slices_f = build_mechanism_context_slices(view)
    slices_w = build_mechanism_context_slices(view)

    # Invariant I8: Byte-identical and digest-identical
    assert_consumer_shared_payload_identity(slices_f, slices_w)

    f_bytes = serialize_shared_mechanism_payload(slices_f)
    w_bytes = serialize_shared_mechanism_payload(slices_w)
    assert f_bytes == w_bytes


def test_shared_projection_divergence_fails() -> None:
    ctx = _make_context()
    view = build_mechanism_context_view(ctx)
    slices1 = build_mechanism_context_slices(view)

    # Corrupted slice with different detail_ids
    corrupted_slice = slices1[0].model_copy(update={"detail_ids": ("d:mutated",)})
    with pytest.raises(ValueError, match="Invariant I8 violation"):
        assert_consumer_shared_payload_identity(slices1, (corrupted_slice,))
