from __future__ import annotations

import pytest
from code2paper.agentic.formalization_agent import (
    MechanismFormulaPackageV2,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)
from code2paper.agentic.method_architect import (
    NarrativePlanV3,
    build_narrative_plan_v3,
    validate_narrative_plan,
)


def _make_context_set() -> MechanismContextSetV1:
    op1 = EvidenceOperationV1(
        operation_id="op:enc",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_span_id="span:enc:1",
        active_path_status="active_default",
    )
    op2 = EvidenceOperationV1(
        operation_id="op:loss",
        predicate="compute_loss",
        operands=("emb", "labels"),
        result="loss",
        source_span_id="span:loss:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:main",
        mechanism_id="mech_main",
        operation_nodes=(op1, op2),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:enc",
                disposition="absorbed_by_detail",
                detail_ids=("d:enc",),
            ),
            SourceOperationDispositionV1(
                operation_id="op:loss",
                disposition="absorbed_by_detail",
                detail_ids=("d:loss",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:enc:1", "span:loss:1"),
    )
    d_enc = MechanismDetailV1(
        detail_id="d:enc",
        primary_mechanism_id="mech_main",
        order_index=0,
        role="representation",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="encode input tokens into embeddings",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_operation_ids=("op:enc",),
        active_path_status="active_default",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:enc",
                atom_kind="operation",
                semantic_anchor="token encoding",
                source_operation_ids=("op:enc",),
            ),
        ),
    )
    d_loss = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_main",
        order_index=1,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="compute loss objective",
        predicate="compute_loss",
        operands=("emb", "labels"),
        result="loss",
        formalizable=True,
        source_operation_ids=("op:loss",),
        active_path_status="active_default",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:loss",
                atom_kind="formal_relation",
                semantic_anchor="loss formula",
                source_operation_ids=("op:loss",),
            ),
        ),
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_main",
        mechanism_name="Main Method Architecture",
        scientific_role="core_model",
        reader_question="How does the main model process data and train?",
        purpose="Complete end-to-end processing and optimization",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:enc", "d:loss"),
        details=(d_enc, d_loss),
    )
    return MechanismContextSetV1(
        repo_snapshot_id="repo:main",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:align",
        research_digest="sha256:research",
        contexts=(ctx,),
    )


def test_build_narrative_plan_v3_and_validation() -> None:
    context_set = _make_context_set()
    pkg = MechanismFormulaPackageV2(
        package_id="pkg:loss",
        mechanism_id="mech_main",
        source_detail_ids=("d:loss",),
        satisfied_obligation_ids=("ob:loss",),
        latex="loss = \\operatorname{compute_loss}(emb, labels)",
        prose_explanation="Computes loss.",
        symbol_definitions=(("emb", "embeddings"), ("labels", "ground truth")),
        evidence_authority="repository_verified",
        formula_lane="repository_derived",
        review_status="accepted",
        source_context_digest=context_set.contexts[0].source_context_digest,
    )

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        formula_packages=(pkg,),
    )
    assert isinstance(plan, NarrativePlanV3)
    assert len(plan.sections) == 1
    assert plan.sections[0].mechanism_ids == ("mech_main",)
    assert len(plan.sections[0].paragraphs) >= 2
    assert trace["sections_planned"] == 1
    assert trace["formula_placements_count"] == 1

    # Validate the generated plan passes all gates
    failures = validate_narrative_plan(plan, context_set)
    assert failures == ()


def test_validate_narrative_plan_catches_violations() -> None:
    context_set = _make_context_set()
    plan, _ = build_narrative_plan_v3(contexts=context_set)

    # 1. Unknown mechanism ID failure
    bad_sec = plan.sections[0].model_copy(update={"mechanism_ids": ("unknown_mech",)})
    bad_plan = plan.model_copy(update={"sections": (bad_sec,)})
    failures = validate_narrative_plan(bad_plan, context_set)
    assert any("unknown_mechanism_id:unknown_mech" in f for f in failures)

    # 2. Unknown detail ID failure
    p0 = plan.sections[0].paragraphs[0]
    bad_p0 = p0.model_copy(update={"required_detail_ids": ("unknown_detail",)})
    bad_sec2 = plan.sections[0].model_copy(update={"paragraphs": (bad_p0, *plan.sections[0].paragraphs[1:])})
    bad_plan2 = plan.model_copy(update={"sections": (bad_sec2,)})
    failures2 = validate_narrative_plan(bad_plan2, context_set)
    assert any("unknown_detail_id:unknown_detail" in f for f in failures2)

    # 3. Missing core detail failure
    empty_p = [p.model_copy(update={"required_detail_ids": ()}) for p in plan.sections[0].paragraphs]
    bad_sec3 = plan.sections[0].model_copy(update={"paragraphs": tuple(empty_p)})
    bad_plan3 = plan.model_copy(update={"sections": (bad_sec3,)})
    failures3 = validate_narrative_plan(bad_plan3, context_set)
    assert any("missing_core_detail" in f for f in failures3)
