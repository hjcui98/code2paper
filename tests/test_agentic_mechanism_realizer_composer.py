from code2paper.agentic.formalization_agent import MechanismFormulaPackageV2
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    MechanismContextV1,
    MechanismDetailV1,
)
from code2paper.agentic.mechanism_context_projection import build_mechanism_context_slices
from code2paper.agentic.mechanism_realizer_composer import (
    MechanismDraftV1,
    MechanismRealizer,
    SectionComposer,
    SectionCompositionV1,
    sanitize_representation_only,
)
from code2paper.agentic.method_architect import NarrativeSectionPlanV3
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig


def test_sanitize_representation_only() -> None:
    text_with_control_char = "Method\x00 description\x1f with formula."
    cleaned, diff_class = sanitize_representation_only(text_with_control_char)
    assert "\x00" not in cleaned
    assert "\x1f" not in cleaned
    assert diff_class == "control_chars_removed"

    clean_text = "Clean method prose."
    cleaned2, diff_class2 = sanitize_representation_only(clean_text)
    assert cleaned2 == clean_text
    assert diff_class2 == "none"


def test_mechanism_realizer_and_composer_two_step() -> None:
    detail1 = MechanismDetailV1(
        detail_id="d:1",
        primary_mechanism_id="mech_densify",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="densify points based on gradient",
        witness_atoms=(
            DetailWitnessAtomV1(atom_id="atom:1", atom_kind="operation", semantic_anchor="densify"),
        ),
    )
    detail2 = MechanismDetailV1(
        detail_id="d:2",
        primary_mechanism_id="mech_densify",
        order_index=1,
        role="condition",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_partial",
        publication_policy="clean_candidate",
        semantic_atom="prune points exceeding threshold",
        witness_atoms=(),
    )
    from code2paper.agentic.mechanism_context_models import MechanismEvidenceClosureV1

    closure = MechanismEvidenceClosureV1(
        closure_id="closure:densify",
        mechanism_id="mech_densify",
        operation_nodes=(),
        operation_dispositions=(),
        source_operation_terminal_coverage=0.0,
        exact_span_ids=(),
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_densify",
        mechanism_name="Gaussian Densification and Pruning",
        scientific_role="transformation",
        reader_question="How are Gaussians densified?",
        purpose="Scene optimization",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:1", "d:2"),
        details=(detail1, detail2),
    )

    pkg = MechanismFormulaPackageV2(
        package_id="pkg:vcd",
        mechanism_id="mech_densify",
        source_detail_ids=("d:1",),
        satisfied_obligation_ids=("obl:1",),
        latex=r"\Delta p = \frac{\nabla L}{\tau}",
        prose_explanation="Offset proportional to gradient divided by threshold.",
    )

    # A missing caller is fail-closed: the harness cannot manufacture the
    # paragraph or its witnesses.
    blocked = MechanismRealizer().realize_draft(
        context=ctx,
        page_index=0,
        page_slice=build_mechanism_context_slices(ctx)[0],
        formula_packages=(pkg,),
    )
    assert blocked.status == "blocked"
    assert blocked.draft_markdown == ""
    assert blocked.realized_detail_ids == ()
    assert blocked.witnesses == ()

    # Step 1: Mechanism Realizer through the actual caller boundary.
    calls: list[LLMRequest] = []

    def caller(_config: LLMConfig, request: LLMRequest) -> LLMResponse:
        calls.append(request)
        markdown = (
            "Densify points based on gradient and prune points exceeding threshold. "
            r"The update is \Delta p = \frac{\nabla L}{\tau}."
        )
        return LLMResponse(
            text=__import__("json").dumps({
                "draft_markdown": markdown,
                "rendered_detail_ids": ["d:1", "d:2"],
                "used_formula_package_ids": ["pkg:vcd"],
                "witnesses": [
                    {"witness_kind": "detail", "target_id": "d:1", "exact_text": "Densify points based on gradient"},
                    {"witness_kind": "detail", "target_id": "d:2", "exact_text": "prune points exceeding threshold"},
                    {"witness_kind": "formula", "target_id": "pkg:vcd", "exact_text": r"\Delta p = \frac{\nabla L}{\tau}"},
                ],
            }),
            response_hash="sha256:test",
            finish_reason="stop",
        )

    page = build_mechanism_context_slices(ctx)[0]
    realizer = MechanismRealizer(llm_config=LLMConfig(model="test-realizer"))
    draft = realizer.realize_draft(
        context=ctx,
        page_index=0,
        page_slice=page,
        formula_packages=(pkg,),
        caller=caller,
    )

    assert isinstance(draft, MechanismDraftV1)
    assert draft.mechanism_id == "mech_densify"
    assert "d:1" in draft.realized_detail_ids
    assert "d:2" in draft.realized_detail_ids
    assert "pkg:vcd" in draft.formula_package_ids
    # Authority rules
    assert draft.status == "accepted"
    assert draft.witnesses
    assert calls
    assert calls[0].input_payload["shared_page_bytes"] == page.serialized_payload.decode("utf-8")
    # Formula package is verbatim included without formula rewrite
    assert r"\Delta p = \frac{\nabla L}{\tau}" in draft.draft_markdown

    # Step 2: Section Composer
    sec_plan = NarrativeSectionPlanV3(
        section_id="sec_method",
        heading="Methodology",
        mechanism_ids=("mech_densify",),
    )
    composer = SectionComposer()
    section = composer.compose_section(
        section_plan=sec_plan,
        drafts=(draft,),
    )

    assert isinstance(section, SectionCompositionV1)
    assert section.section_id == "sec_method"
    assert section.heading == "Methodology"
    assert "## Methodology" in section.section_markdown
    assert draft.draft_id in section.used_mechanism_draft_ids
    assert len(section.paragraphs) == 1
    assert section.paragraphs[0]["mechanism_id"] == "mech_densify"
