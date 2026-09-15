from __future__ import annotations

import pytest
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
    NarrativeParagraphPlanV3,
    NarrativePlanV3,
    NarrativeSectionPlanV3,
    NarrativeUnitV1,
)
from code2paper.agentic.method_content_trace import (
    MethodContentTraceV2,
    build_method_content_trace_v2,
)
from code2paper.agentic.publication_transaction_contract import (
    ParagraphTransactionAssessmentV1,
    assess_paragraph_transaction,
    bind_paragraph_witnesses,
    required_anchors_from_plan_row,
    required_targets_from_plan_row,
)


def _make_context_set() -> MechanismContextSetV1:
    op = EvidenceOperationV1(
        operation_id="op:1",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        source_span_id="span:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:1",
        mechanism_id="mech_loss",
        operation_nodes=(op,),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:1",
                disposition="absorbed_by_detail",
                detail_ids=("d:loss",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:1",),
    )
    detail = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_loss",
        order_index=0,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="compute loss",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        formalizable=True,
        source_operation_ids=("op:1",),
        active_path_status="active_default",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:loss",
                atom_kind="formal_relation",
                semantic_anchor="loss computation",
                source_operation_ids=("op:1",),
            ),
        ),
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_loss",
        mechanism_name="Loss Function",
        scientific_role="objective",
        reader_question="What is the objective?",
        purpose="Model optimization",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:loss",),
        details=(detail,),
    )
    return MechanismContextSetV1(
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:align",
        research_digest="sha256:research",
        contexts=(ctx,),
    )


def test_required_targets_and_detail_atom_transaction_assessment() -> None:
    plan_row = {
        "paragraph_id": "sec_1_p1",
        "required_detail_ids": ("d:loss",),
        "witness_atoms": [
            {
                "atom_id": "atom:loss",
                "detail_id": "d:loss",
                "semantic_anchor": "loss computation",
                "exact_excerpts": ["loss = compute_loss(logits, labels)"],
            }
        ],
    }

    # Verify required targets projection
    targets = required_targets_from_plan_row(plan_row)
    assert "detail" in targets
    assert targets["detail"] == ("d:loss",)
    assert "slot" not in targets

    # Valid transaction: has witness for atom or detail
    tx_valid = {
        "paragraph_id": "sec_1_p1",
        "paragraph_markdown": "The objective optimizes loss = compute_loss(logits, labels) across all batches.",
        "rendered_detail_ids": ["d:loss"],
        "witnesses": [
            {
                "witness_kind": "atom",
                "target_id": "atom:loss",
                "exact_text": "loss = compute_loss(logits, labels)",
            }
        ],
    }
    assessment = assess_paragraph_transaction(tx_valid, plan_row=plan_row)
    assert assessment.valid is True
    assert "d:loss" in assessment.witnessed_by_kind.get("detail", ())

    # Invalid transaction: missing witness
    tx_invalid = {
        "paragraph_id": "sec_1_p1",
        "paragraph_markdown": "Some generic text without formula or operation witness.",
        "rendered_detail_ids": ["d:loss"],
        "witnesses": [],
    }
    assessment_invalid = assess_paragraph_transaction(tx_invalid, plan_row=plan_row)
    assert assessment_invalid.valid is False
    assert "d:loss" in assessment_invalid.missing_by_kind.get("detail", ())


@pytest.mark.parametrize(
    ("body", "valid"),
    [
        ("The embeddings are multiplied by the bias and residual.", False),
        ("The embeddings, bias, and residual are added together.", True),
        ("The embeddings and bias are added together.", False),
        ("The embeddings, bias, and residual are not added together.", False),
        ("The result = embeddings + bias + residual is used.", True),
    ],
)
def test_additive_atom_binding_requires_operation_and_operands(
    body: str, valid: bool,
) -> None:
    row = {
        "paragraph_id": "p1",
        "required_detail_ids": ["detail:aggregate"],
        "witness_contract": {"targets": [{
            "target_kind": "atom",
            "target_id": "atom:sum",
            "detail_id": "detail:aggregate",
            "semantic_atom": "additive aggregation",
            "required": True,
            "allowed_exact_excerpts": ["result = embeddings + bias + residual"],
        }]},
    }
    transaction = {"paragraph_id": "p1", "paragraph_markdown": body, "witnesses": []}
    bound = bind_paragraph_witnesses(transaction, plan_row=row)
    assessment = assess_paragraph_transaction(
        bound, plan_row=row, required_anchors=required_anchors_from_plan_row(row)
    )
    assert assessment.valid is valid
    assert ("detail:aggregate" in bound.get("rendered_detail_ids", ())) is valid
    if not valid:
        declared = {
            **transaction,
            "rendered_detail_ids": ["detail:aggregate"],
            "witnesses": [{
                "witness_kind": "atom",
                "target_id": "atom:sum",
                "exact_text": body,
            }],
        }
        direct = assess_paragraph_transaction(
            declared, plan_row=row, required_anchors=required_anchors_from_plan_row(row)
        )
        assert direct.valid is False


def test_method_content_trace_v2_and_information_funnel() -> None:
    context_set = _make_context_set()
    para_plan = NarrativeParagraphPlanV3(
        paragraph_id="sec_1_p1",
        section_id="sec_1",
        role="training_objective",
        mechanism_id="mech_loss",
        required_detail_ids=("d:loss",),
    )
    sec_plan = NarrativeSectionPlanV3(
        section_id="sec_1",
        heading="Loss",
        mechanism_ids=("mech_loss",),
        paragraphs=(para_plan,),
    )
    unit = NarrativeUnitV1(
        unit_id="unit_1",
        section_id="sec_1",
        mechanism_context_ids=("mech_loss",),
        rhetorical_role="objective",
        reader_question="How is it trained?",
        paragraph_ids=("sec_1_p1",),
        required_detail_ids=("d:loss",),
        optional_detail_ids=(),
        formula_obligation_ids=(),
        suggested_depth="standard",
    )
    narrative_plan = NarrativePlanV3(
        plan_id="plan_1",
        sections=(sec_plan,),
        narrative_units=(unit,),
    )

    assessment = ParagraphTransactionAssessmentV1(
        paragraph_id="sec_1_p1",
        section_id="sec_1",
        status="valid",
        valid=True,
        required_by_kind={"detail": ("d:loss",)},
        declared_by_kind={"detail": ("d:loss",)},
        witnessed_by_kind={"detail": ("d:loss",)},
        missing_by_kind={},
    )

    trace = build_method_content_trace_v2(
        contexts=context_set,
        narrative_plan=narrative_plan,
        paragraph_assessments={"sec_1_p1": assessment},
        verified_detail_ids={"d:loss"},
    )
    assert isinstance(trace, MethodContentTraceV2)
    assert len(trace.rows) == 1
    row = trace.rows[0]
    assert row.detail_id == "d:loss"
    assert row.writer_witnessed is True
    assert row.candidate_included is True
    assert row.verified_status == "verified"
    assert row.terminal_state == "validated"

    assert trace.funnel is not None
    assert trace.funnel.total_research_operations == 1
    assert trace.funnel.total_context_details == 1
    assert trace.funnel.core_context_details == 1
    assert trace.funnel.architect_planned_details == 1
    assert trace.funnel.writer_rendered_details == 1
    assert trace.funnel.candidate_accepted_details == 1
    assert trace.funnel.verified_validated_details == 1
    assert trace.funnel.funnel_survival_rates["candidate_to_verified"] == 1.0
    assert row.primary_loss_layer == ""


def test_discovery_recall_requires_an_independent_expected_population() -> None:
    """R3: the closure is never its own discovery denominator."""

    context_set = _make_context_set()

    # No population supplied: the recall is unknown, not perfect.
    no_population = build_method_content_trace_v2(contexts=context_set)
    assert no_population.funnel.discovery_recall_status == "not_measured"
    assert no_population.funnel.mechanism_discovery_recall is None
    assert no_population.funnel.expected_operation_count is None
    assert no_population.funnel.discovery_population_source == ""

    # An explicitly supplied but empty population has no denominator.
    empty_population = build_method_content_trace_v2(
        contexts=context_set,
        expected_operation_ids=[],
        expected_operation_source="fixture:empty",
    )
    assert empty_population.funnel.discovery_recall_status == "not_applicable"
    assert empty_population.funnel.mechanism_discovery_recall is None
    assert empty_population.funnel.expected_operation_count == 0

    # A missing expected operation lowers the measured recall.
    partial = build_method_content_trace_v2(
        contexts=context_set,
        expected_operation_ids=["op:1", "op:missing"],
        expected_operation_source="fixture:independent",
    )
    assert partial.funnel.discovery_recall_status == "measured"
    assert partial.funnel.mechanism_discovery_recall == 0.5
    assert partial.funnel.expected_operation_count == 2
    assert partial.funnel.discovery_population_source == "fixture:independent"

    # A complete population measures a full recall without touching the
    # closure retention metric, which has its own denominator.
    complete = build_method_content_trace_v2(
        contexts=context_set,
        expected_operation_ids=["op:1"],
        expected_operation_source="fixture:independent",
    )
    assert complete.funnel.discovery_recall_status == "measured"
    assert complete.funnel.mechanism_discovery_recall == 1.0
    assert complete.funnel.closure_retention_status == "measured"
    assert complete.funnel.closure_retention == 1.0
    # The legacy numeric rate keeps its historical value, but the funnel says
    # which rates had no sample instead of letting 1.0 read as measured.
    assert "candidate_to_verified" in complete.funnel.zero_denominator_metrics
    assert complete.funnel.funnel_survival_rates["candidate_to_verified"] == 1.0


def test_extended_loss_taxonomy_classification() -> None:
    from code2paper.agentic.method_content_trace import (
        LOSS_TAXONOMY_LAYERS_V2,
        LOSS_TAXONOMY_DESCRIPTIONS_V2,
        classify_primary_loss_layer,
    )

    assert len(LOSS_TAXONOMY_LAYERS_V2) == 13
    assert len(LOSS_TAXONOMY_DESCRIPTIONS_V2) == 13

    # R0a: search never triggered
    assert classify_primary_loss_layer(
        validated=False, discovered=False, closed_in_evidence=False,
        annotated=False, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, search_triggered=False,
    ) == "R0a"

    # R0b: discovered not read
    assert classify_primary_loss_layer(
        validated=False, discovered=False, closed_in_evidence=False,
        annotated=False, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, search_triggered=True, candidate_read=False,
    ) == "R0b"

    # R0c: read but not closed in evidence
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=False,
        annotated=False, projected=False, writer_delivered=False,
        rendered=False, p_valid=False,
    ) == "R0c"

    # R0d: promotion attempted but typed rejection
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=False, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, rejection_code="ownership_role_not_target_method",
    ) == "R0d"

    # R1a: ownership misclassified
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, ownership_misclassified=True,
    ) == "R1a"

    # R1b: stage/mechanism routing miss
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=False, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, routing_miss=True,
    ) == "R1b"

    # R2a: active path unknown / missing closure edges
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=False, writer_delivered=False,
        rendered=False, p_valid=False, active_path_status="unknown",
    ) == "R2a"

    # R2b: detail compression loss (not projected)
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=False, writer_delivered=False,
        rendered=False, p_valid=False,
    ) == "R2b"

    # R2c: formula obligation compile loss
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=False,
        rendered=False, p_valid=False, has_formula_loss=True,
    ) == "R2c"

    # R3a: payload undelivered to writer
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=False,
        rendered=False, p_valid=False,
    ) == "R3a"

    # R3b: writer failed to realize delivered detail
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=True,
        rendered=False, p_valid=False,
    ) == "R3b"

    # R4: rendering / LaTeX / control char damage
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=True,
        rendered=True, p_valid=False, control_char_damage=True,
    ) == "R4"

    # R5: binder rejection
    assert classify_primary_loss_layer(
        validated=False, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=True,
        rendered=True, p_valid=False, binder_rejected=True,
    ) == "R5"

    # Validated: no loss
    assert classify_primary_loss_layer(
        validated=True, discovered=True, closed_in_evidence=True,
        annotated=True, projected=True, writer_delivered=True,
        rendered=True, p_valid=True,
    ) == ""
