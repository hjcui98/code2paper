from __future__ import annotations

import pytest
from code2paper.agentic.formalization_agent import (
    FormulaPlacementV1,
    MechanismFormulaObligationV1,
    MechanismFormulaPackageV2,
    compile_mechanism_formula_obligations,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)


def _make_context() -> MechanismContextV1:
    op1 = EvidenceOperationV1(
        operation_id="op:1",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        source_span_id="span:loss:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:loss",
        mechanism_id="mech_infonce",
        operation_nodes=(op1,),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:1",
                disposition="absorbed_by_detail",
                detail_ids=("d:loss",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:loss:1",),
    )
    d1 = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_infonce",
        order_index=0,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="compute InfoNCE contrastive loss",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        formalizable=True,
        source_operation_ids=("op:1",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:loss",
                atom_kind="formal_relation",
                semantic_anchor="loss formula",
                source_operation_ids=("op:1",),
            ),
        ),
    )
    return MechanismContextV1(
        mechanism_id="mech_infonce",
        mechanism_name="InfoNCE Loss",
        scientific_role="training_objective",
        reader_question="What is the optimization objective?",
        purpose="Contrastive learning objective",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:loss",),
        details=(d1,),
    )


def test_mechanism_formula_obligation_compiler_paragraph_independence() -> None:
    ctx = _make_context()
    obs = compile_mechanism_formula_obligations(ctx, author_formula_expectations=("InfoNCE",))
    assert len(obs) == 1
    ob = obs[0]
    assert ob.mechanism_id == "mech_infonce"
    assert ob.source_detail_ids == ("d:loss",)
    assert ob.expectation == "required"
    assert ob.content_digest.startswith("sha256:")

    # Verify no paragraph/section fields exist on MechanismFormulaObligationV1
    assert not hasattr(ob, "section_id")
    assert not hasattr(ob, "consumer_paragraph_id")
    assert not hasattr(ob, "paragraph_ids")


def test_mechanism_formula_package_v2_and_placement() -> None:
    pkg = MechanismFormulaPackageV2(
        package_id="pkg:infonce",
        mechanism_id="mech_infonce",
        source_detail_ids=("d:loss",),
        satisfied_obligation_ids=("ob:formula:mech_infonce",),
        latex=r"\mathcal{L} = -\log \frac{\exp(s_+ / \tau)}{\sum_i \exp(s_i / \tau)}",
        prose_explanation="InfoNCE loss function.",
        symbol_definitions=((r"\mathcal{L}", "contrastive loss"), (r"\tau", "temperature")),
    )
    assert pkg.content_digest.startswith("sha256:")
    assert pkg.markdown_block.startswith("$$")
    assert pkg.markdown_block.endswith("$$")

    # Formula placement is separated into narrative placement
    placement = FormulaPlacementV1(
        package_id="pkg:infonce",
        section_id="MA-S3",
        paragraph_id="p:loss",
    )
    assert placement.package_id == "pkg:infonce"
    assert placement.section_id == "MA-S3"
    assert placement.paragraph_id == "p:loss"
