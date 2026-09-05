from __future__ import annotations

import pytest
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSliceV1,
    MechanismContextV1,
    MechanismContextViewV1,
    MechanismDetailV1,
    MechanismEdgeV1,
    MechanismEvidenceClosureV1,
    MechanismSeedV1,
    SharedDetailRefV1,
    SourceOperationDispositionV1,
    canonical_json_bytes,
    compute_consumer_request_digest,
    compute_shared_payload_digest,
    compute_slice_digest,
    compute_source_context_digest,
    compute_view_digest,
    sha256_digest,
)


def _sample_operation(op_id: str = "op:1", excerpt: str = "x = x + 1") -> EvidenceOperationV1:
    return EvidenceOperationV1(
        operation_id=op_id,
        predicate="add",
        operands=("x", "1"),
        result="x",
        source_span_id="span:test.py:1:2",
        active_path_status="active_default",
        exact_excerpt=excerpt,
    )


def _sample_closure(mech_id: str = "mech:test") -> MechanismEvidenceClosureV1:
    op1 = _sample_operation("op:1")
    op2 = _sample_operation("op:2", excerpt="y = norm(x)")
    disp1 = SourceOperationDispositionV1(
        operation_id="op:1",
        disposition="absorbed_by_detail",
        detail_ids=("detail:1",),
    )
    disp2 = SourceOperationDispositionV1(
        operation_id="op:2",
        disposition="classified_supporting",
        detail_ids=(),
    )
    return MechanismEvidenceClosureV1(
        closure_id=f"closure:{mech_id}",
        mechanism_id=mech_id,
        operation_nodes=(op1, op2),
        operation_dispositions=(disp1, disp2),
        source_operation_terminal_coverage=1.0,
        fact_ids=("fact:1",),
        exact_span_ids=("span:test.py:1:2",),
    )


def _sample_detail(
    detail_id: str = "detail:1",
    mech_id: str = "mech:test",
    importance: str = "core",
    policy: str = "clean_candidate",
    active_path: str = "active_default",
) -> MechanismDetailV1:
    atom = DetailWitnessAtomV1(
        atom_id=f"atom:{detail_id}:1",
        atom_kind="operation",
        semantic_anchor="add inputs",
        source_operation_ids=("op:1",),
    )
    return MechanismDetailV1(
        detail_id=detail_id,
        primary_mechanism_id=mech_id,
        order_index=0,
        role="transformation",
        importance=importance,
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy=policy,
        semantic_atom="add inputs and update state",
        active_path_status=active_path,
        source_operation_ids=("op:1",),
        witness_atoms=(atom,),
    )


def _sample_context(mech_id: str = "mech:test") -> MechanismContextV1:
    closure = _sample_closure(mech_id)
    detail = _sample_detail("detail:1", mech_id)
    return MechanismContextV1(
        mechanism_id=mech_id,
        mechanism_name="Test Mechanism",
        scientific_role="encoding",
        reader_question="How does it work?",
        purpose="Demonstrate lossless mechanism closure.",
        importance="core",
        evidence_closure=closure,
        input_detail_ids=(),
        ordered_detail_ids=("detail:1",),
        output_detail_ids=("detail:1",),
        details=(detail,),
    )


def test_mechanism_seed_digest_determinism() -> None:
    seed1 = MechanismSeedV1(
        seed_id="seed:1",
        author_statements=("Statement A", "Statement B"),
        bound_fact_ids=("fact:1", "fact:2"),
    )
    seed2 = MechanismSeedV1(
        seed_id="seed:1",
        author_statements=("Statement A", "Statement B"),
        bound_fact_ids=("fact:1", "fact:2"),
    )
    assert seed1.content_digest == seed2.content_digest
    assert seed1.content_digest.startswith("sha256:")


def test_evidence_closure_disposition_invariants() -> None:
    op1 = _sample_operation("op:1")
    op2 = _sample_operation("op:2")

    # Missing disposition for op:2 fails closed
    with pytest.raises(ValueError, match="operation_dispositions set must match operation_nodes exactly"):
        MechanismEvidenceClosureV1(
            closure_id="closure:bad",
            mechanism_id="mech:bad",
            operation_nodes=(op1, op2),
            operation_dispositions=(
                SourceOperationDispositionV1(
                    operation_id="op:1",
                    disposition="absorbed_by_detail",
                ),
            ),
        )


def test_detail_source_binding_invariant() -> None:
    # Invariant I3: repository_verified implementation detail must bind to source evidence
    with pytest.raises(ValueError, match="must bind to source operations/facts/spans/equations"):
        MechanismDetailV1(
            detail_id="detail:unbound",
            primary_mechanism_id="mech:test",
            order_index=0,
            role="transformation",
            importance="core",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="clean_candidate",
            semantic_atom="Unbound operation",
            source_operation_ids=(),
            source_fact_ids=(),
            source_span_ids=(),
            source_equation_ids=(),
        )


def test_detail_inactive_path_precedence_invariant() -> None:
    # Invariant I4: Inactive/unreachable paths cannot be clean core
    with pytest.raises(ValueError, match="cannot have importance='core' and publication_policy='clean_candidate'"):
        _sample_detail(
            detail_id="detail:inactive",
            importance="core",
            policy="clean_candidate",
            active_path="inactive_default",
        )


def test_detail_witness_atoms_source_subset_invariant() -> None:
    # Invariant I10: Witness atoms source operation IDs must be subset of detail source operations
    bad_atom = DetailWitnessAtomV1(
        atom_id="atom:bad",
        atom_kind="operation",
        semantic_anchor="Anchor",
        source_operation_ids=("op:unrelated",),
    )
    with pytest.raises(ValueError, match="references operation IDs.*not in detail"):
        MechanismDetailV1(
            detail_id="detail:bad_atom",
            primary_mechanism_id="mech:test",
            order_index=0,
            role="transformation",
            importance="supporting",
            claim_kind="implementation",
            evidence_authority="repository_verified",
            publication_policy="annotated_only",
            semantic_atom="Bad atom",
            source_operation_ids=("op:1",),
            witness_atoms=(bad_atom,),
        )


def test_shared_detail_ref_invariant() -> None:
    with pytest.raises(ValueError, match="primary and consumer mechanisms must differ"):
        SharedDetailRefV1(
            detail_id="detail:1",
            primary_mechanism_id="mech:same",
            consumer_mechanism_id="mech:same",
            role="shared_interface",
        )


def test_mechanism_context_paragraph_independence_invariant() -> None:
    # Invariant I2: Mechanism identity must be paragraph-independent
    with pytest.raises(ValueError, match="cannot contain paragraph or section identifiers"):
        _sample_context(mech_id="section_1_mech")

    with pytest.raises(ValueError, match="cannot contain paragraph or section identifiers"):
        _sample_context(mech_id="paragraph_2_mech")


def test_mechanism_context_core_detail_ordered_invariant() -> None:
    closure = _sample_closure("mech:test")
    core_detail = _sample_detail("detail:core", "mech:test", importance="core")
    with pytest.raises(ValueError, match="Core details.*must be included in ordered_detail_ids"):
        MechanismContextV1(
            mechanism_id="mech:test",
            mechanism_name="Test",
            scientific_role="encoding",
            reader_question="Q",
            purpose="P",
            importance="core",
            evidence_closure=closure,
            ordered_detail_ids=(),  # Missing core detail
            details=(core_detail,),
        )


def test_digest_hierarchy_closure() -> None:
    ctx = _sample_context("mech:digest")
    src_digest = compute_source_context_digest(ctx)
    assert src_digest.startswith("sha256:")
    assert ctx.source_context_digest == src_digest

    view = MechanismContextViewV1(
        mechanism_id="mech:digest",
        scientific_goal={"goal": "test"},
        author_intent={"intent": "test"},
        ordered_details=(),
        edges=(),
        configurations=(),
        exact_evidence=(),
        unresolved_items=(),
        source_context_digest=src_digest,
    )
    v_digest = compute_view_digest(view)
    assert v_digest.startswith("sha256:")
    assert view.view_digest == v_digest

    slice_obj = MechanismContextSliceV1(
        mechanism_id="mech:digest",
        slice_index=0,
        detail_ids=("detail:1",),
        exact_evidence_ids=("span:1",),
        view_digest=v_digest,
    )
    sl_digest = compute_slice_digest(slice_obj)
    assert sl_digest.startswith("sha256:")
    assert slice_obj.slice_digest == sl_digest

    payload_digest = compute_shared_payload_digest((slice_obj,))
    assert payload_digest.startswith("sha256:")

    formalizer_task = {"type": "formalize", "obligation_id": "ob:1"}
    writer_task = {"type": "write_method", "paragraph_id": "p:1"}

    f_req_digest = compute_consumer_request_digest(payload_digest, formalizer_task)
    w_req_digest = compute_consumer_request_digest(payload_digest, writer_task)

    # Invariant I8: Shared payload digest is identical between consumers,
    # while role-specific request digests differ because tasks differ.
    assert f_req_digest != w_req_digest
    assert f_req_digest.startswith("sha256:")
    assert w_req_digest.startswith("sha256:")
