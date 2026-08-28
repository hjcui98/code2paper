"""Package W tests: reader-facing Writer surface and paper-language quality."""

from __future__ import annotations

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    SemanticStageGroupV1,
)
from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.final_text_authorship import FinalTextAuthorshipLedgerV1
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    MethodArgumentUnitV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    SectionArgumentGraphV1,
)
from code2paper.agentic.method_architect import build_method_section_plan
from code2paper.agentic.method_product_models import extract_code_binding_terms
from code2paper.agentic.publication_method_writer import _writer_section_inputs
from code2paper.agentic.publication_quality import (
    _claim_rendered_in,
    evaluate_publication_method_quality,
)
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1


def _claim_set() -> AtomicClaimSetV3:
    return AtomicClaimSetV3(
        repo_snapshot_id="repo:writer-quality",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            AtomicClaimV3(
                claim_id="claim-1",
                canonical_text=(
                    "The encoder loads the DC feature component through "
                    "GaussianModel.capture and assembles the attribute list."
                ),
                fact_ids=["fact-1"],
                covers_obligation_ids=["obl-1"],
                direct_evidence_ids=["span:enc.py:1:2"],
                allowed_wording_boundary="loads and assembles features only",
                canonical_identity="sha256:claim-1",
                status="supported",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-1",
                name="Encoding stage",
                purpose="Explain the encoding.",
                ordered_claim_ids=["claim-1"],
                covers_obligation_ids=["obl-1"],
            ),
        ],
        content_digest="sha256:claims",
    )


def test_writer_section_payload_contains_reader_facing_claims_with_bindings() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    inputs = _writer_section_inputs(
        plan=plan,
        claims=claim_set,
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            equations=[],
            code_fact_digest="sha256:facts",
            content_digest="sha256:equations",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            claims=[],
            content_digest="sha256:configs",
        ),
    )
    assert inputs, "writer section inputs must exist"
    payload = inputs[0].prompt_payload
    reader_claims = payload["reader_facing_claims"]
    assert reader_claims, "reader-facing claims must be exposed"
    claim = reader_claims[0]
    assert claim["paper_statement"]
    assert "GaussianModel.capture" in claim["code_binding_terms"]
    assert claim["may_enter_verified"] is True
    assert claim["requires_caveat"] is False
    assert claim["lane"] == "repository_verified"
    assert payload["paper_term_hints"]


def test_writer_payload_marks_candidate_only_units_as_caveated() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    candidate_unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S9:unit",
        section_role="stage",
        research_question="Score prediction",
        design_objective="Learn a mapping from features to importance scores.",
        allowed_expository_moves=(
            "mechanism_overview",
            "limitations_or_mismatch",
            "transition_to_next_section",
        ),
        unresolved_inputs=("obl-score:partially_supported_by_repository",),
        source_obligation_ids=("obl-score",),
        supported=False,
    )
    plan = MethodSectionPlanV2.model_validate(plan.model_copy(update={
        "sections": (
            *plan.sections,
            SectionArgumentGraphV1(
                section_id="MA-S9",
                heading="Score Prediction",
                reader_question="How are scores predicted?",
                argument_unit_ids=("MA-S9:unit",),
                unresolved_inputs=("obl-score:partially_supported_by_repository",),
                incomplete=True,
            ),
        ),
        "argument_units": (*plan.argument_units, candidate_unit),
    }).model_dump(mode="json"))
    inputs = _writer_section_inputs(
        plan=plan,
        claims=claim_set,
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            equations=[],
            code_fact_digest="sha256:facts",
            content_digest="sha256:equations",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            claims=[],
            content_digest="sha256:configs",
        ),
    )
    candidate_payload = next(
        item.prompt_payload for item in inputs if item.section_id == "MA-S9"
    )
    assert candidate_payload["section_candidate_points"]
    point = candidate_payload["section_candidate_points"][0]
    assert point["obligation_id"] == "obl-score"
    assert point["lane"] == "repository_partial"
    assert point["required_caveat"] is True
    assert point["review_question_ids"] == ["review:obl-score"]


def test_code_trace_prose_triggers_style_quality_issue() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:writer-quality",
        project_tree_hash="sha256:tree",
        items=[],
    )
    ledger = FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text")
    code_trace = (
        "The mechanism overview begins with GaussianModel.capture loading weights "
        "from self._features_dc. GaussianModel.construct_list_of_attributes then "
        "loads self._features_dc and self._features_rest. The routine invokes "
        "range with self._features_dc.shape[1] * self._features_dc.shape[2] and "
        "passes normalized to percentile_cutoff_normalize."
    )
    report = evaluate_publication_method_quality(
        final_text=code_trace,
        plan=plan,
        completeness=completeness,
        section_outputs=[],
        ledger=ledger,
    )
    codes = {issue.code for issue in report.issues}
    assert "code_trace_prose_not_method_language" in codes


def test_paper_language_prose_is_not_flagged() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:writer-quality",
        project_tree_hash="sha256:tree",
        items=[],
    )
    ledger = FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text")
    clean = (
        "The feature representation is assembled by iterating over the available "
        "feature channels and then applying the recorded normalization step before "
        "downstream scoring."
    )
    report = evaluate_publication_method_quality(
        final_text=clean,
        plan=plan,
        completeness=completeness,
        section_outputs=[],
        ledger=ledger,
    )
    assert "code_trace_prose_not_method_language" not in {
        issue.code for issue in report.issues
    }


def test_normal_words_facts_and_spans_are_not_internal_bookkeeping_ids() -> None:
    claim_set = _claim_set()
    report = evaluate_publication_method_quality(
        final_text="The verified facts are grounded in repository spans.",
        plan=build_method_section_plan(claims=claim_set),
        completeness=MethodCompletenessMatrixV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            items=[],
        ),
        section_outputs=[],
        ledger=FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text"),
    )
    assert "internal_bookkeeping_exposed" not in {
        issue.code for issue in report.issues
    }


def test_parenthetical_code_bindings_are_valid_method_language() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown=(
            "Feature normalization prepares a stable representation. The direct-current "
            "features (`self._features_dc`) are scaled by a percentile cutoff "
            "(`percentile_cutoff_normalize`) before attribute construction. The iteration "
            "extent is the product of the two feature dimensions "
            "(`self._features_dc.shape[1] * self._features_dc.shape[2]`)."
        ),
        used_argument_unit_ids=[plan.argument_units[0].argument_unit_id],
        used_claim_ids=[],
        completed_rhetorical_moves=[],
    )
    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=MethodCompletenessMatrixV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            items=[],
        ),
        section_outputs=[output],
        ledger=FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text"),
    )
    assert "code_trace_prose_not_method_language" not in {
        issue.code for issue in report.issues
    }


def test_required_qualifier_self_attributes_are_not_code_trace_subjects() -> None:
    """A required qualifier such as ``when self.cfg.add_positional_encoding is
    enabled`` must not be flagged as code-trace prose.

    Regression (fresh EBCAR run): the style detector counted every
    ``self.`` occurrence in the section, so adding the exact repository
    qualifier the reverse validator demands pushed ``self_as_subject`` over
    the threshold and every qualifier repair was rejected as
    ``method_style_regressed``."""
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown=(
            "Passage structural augmentation injects document identity and positional "
            "signals into passage embeddings, producing augmented passage embeddings, "
            "when self.cfg.add_positional_encoding is enabled. Query-passage "
            "concatenation joins query and passage representations along the sequence "
            "dimension, when self.cfg.add_positional_encoding is enabled. Reranker "
            "evaluation invokes the reranker with query embeddings, when document_id "
            "not in unique_document_ids."
        ),
        used_argument_unit_ids=[plan.argument_units[0].argument_unit_id],
        used_claim_ids=[],
        completed_rhetorical_moves=[],
    )
    report = evaluate_publication_method_quality(
        final_text=output.section_markdown,
        plan=plan,
        completeness=MethodCompletenessMatrixV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            items=[],
        ),
        section_outputs=[output],
        ledger=FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text"),
    )
    assert "code_trace_prose_not_method_language" not in {
        issue.code for issue in report.issues
    }
    terms = extract_code_binding_terms(
        "The encoder reads self._features_dc through GaussianModel.capture."
    )
    assert "self._features_dc" in terms
    assert "GaussianModel.capture" in terms
    assert extract_code_binding_terms("The method ranks the primitives.") == ()


def test_supported_claim_rendering_allows_reader_facing_explanation() -> None:
    claim = _claim_set().claims[0]
    prose = (
        "The encoder assembles a direct-current feature representation before "
        "passing it downstream, loading the DC component through the capture "
        "operation (GaussianModel.capture) and constructing the attribute list."
    )
    assert _claim_rendered_in(prose, claim) is True


# ---------------------------------------------------------------------------
# Q3 — four-layer Writer payload and paper-language integration (plan 19.7)
# ---------------------------------------------------------------------------


def test_llm_visible_payload_is_four_layers_with_formula_packages() -> None:
    from code2paper.llm.section_writer import (
        WriterSectionInput,
        _llm_visible_section_payload,
    )

    payload = {
        "section_id": "MA-S1",
        "heading": "Encoder",
        "writer_view": {
            "purpose": {"heading": "Encoder", "reader_question": "How does it read?"},
            "positive_propositions": [],
            "caveated_propositions": [],
            "immutable_constraints": [],
            "allowed_proposition_ids": (),
            "required_proposition_ids": (),
            "view_digest": "sha256:view",
        },
        "formula_packages": [{
            "purpose": "Score.",
            "latex": "s = w x",
            "prose_explanation": "Score.",
            "symbol_definitions": [],
            "material_conditions": [],
            "assumptions": [],
            "authority_status": "code_verified",
            "risks": [],
            "review_question": "",
        }],
        "argument_units": [{"claim_ids": ["claim-x"]}],
        "argument_flow": {"semantic_frames": [{"content_digest": "sha256:f"}]},
        "validation_constraints": {"claims": [{"claim_id": "claim-x"}]},
        "reader_facing_claims": [],
        "formalization": {},
        "required_qualifier_bindings": ["mode == train"],
        "binding_contract": {},
        "grounding_contract": {},
    }
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Encoder",
        prompt_payload=payload,
        publication_mode=True,
    )
    visible = _llm_visible_section_payload(section)
    # Only the four layers plus scoped qualifier/formula channels reach the
    # model; internal ids, frames and validator vocabulary stay harness-side.
    assert set(visible) == {
        "section_id", "heading", "writer_view", "formula_packages",
        "required_qualifier_bindings",
    }
    assert "argument_units" not in visible
    assert "argument_flow" not in visible
    assert "validation_constraints" not in visible
    assert "reader_facing_claims" not in visible
    assert "formalization" not in visible
    assert "binding_contract" not in visible
    assert visible["formula_packages"][0]["latex"] == "s = w x"


def test_writer_section_inputs_expose_mechanism_section_contract() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    graph = plan.sections[0].model_copy(update={
        "primary_concept_keys": ("CK-CORE",),
        "supporting_concept_keys": ("CK-GUARD",),
        "formula_obligation_ids": ("formula:equation:core",),
        "required_dataflow_relation_ids": ("rel:input-to-core",),
    })
    plan = MethodSectionPlanV2.model_validate(plan.model_copy(update={
        "sections": (graph, *plan.sections[1:]),
    }).model_dump(mode="json"))
    inputs = _writer_section_inputs(
        plan=plan,
        claims=claim_set,
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            equations=[],
            code_fact_digest="sha256:facts",
            content_digest="sha256:equations",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="repo:writer-quality",
            project_tree_hash="sha256:tree",
            claims=[],
            content_digest="sha256:configs",
        ),
    )
    mechanism = inputs[0].prompt_payload.get("mechanism_section") or {}
    assert mechanism.get("primary_concept_keys") == ["CK-CORE"]
    assert mechanism.get("formula_obligation_ids") == ["formula:equation:core"]
    assert "ordered_primary_concepts" in mechanism
    assert "accepted_formulas" in mechanism
    assert "formula_obligations" in inputs[0].prompt_payload


def test_mechanism_section_visible_when_present_in_payload() -> None:
    from code2paper.llm.section_writer import (
        _llm_visible_section_payload,
        WriterSectionInput,
    )

    payload = {
        "writer_view": {"positive_concepts": [], "caveated_concepts": []},
        "formula_packages": [],
        "formula_obligations": [{"obligation_id": "formula:1", "outcome": "unresolved"}],
        "mechanism_section": {"reader_question": "How?", "primary_concept_keys": ["CK"]},
        "required_qualifier_bindings": [],
    }
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Core",
        prompt_payload=payload,
        publication_mode=True,
    )
    visible = _llm_visible_section_payload(section)
    assert "mechanism_section" in visible
    assert "formula_obligations" in visible


def test_caveated_propositions_carry_substantive_narrative_targets() -> None:
    from code2paper.agentic.method_proposition_models import MethodPropositionV1
    from code2paper.agentic.writer_view_projection import build_writer_view

    intended = MethodPropositionV1(
        proposition_id="MP-I", origin="author_intent",
        evidence_lane="author_intent_unverified", requires_caveat=True,
        reader_subject="the deployment path",
        transformation="is intended to avoid rendering",
        inputs=("latent",), outputs=("query",),
        missing_or_uncertain_parts=("exact standardization formula",),
        writing_role="method_positive",
    )
    view = build_writer_view(
        heading="Deployment", reader_question="How is inference deployed?",
        section_goal="Explain the deployment path.",
        propositions=[intended],
        callback_opportunities=[],
    )
    assert view.caveated_propositions
    caveated = view.caveated_propositions[0]
    assert caveated.intended_subject == "the deployment path"
    assert caveated.intended_transformation == "is intended to avoid rendering"
    assert "exact standardization formula" in caveated.missing_parts
    assert caveated.required_caveat_kind == "author_intent"


def test_writer_skill_treats_design_objective_as_caveated_content() -> None:
    from code2paper.authoring.writer_skill import PublicationMethodWriterSkillV1

    skill = PublicationMethodWriterSkillV1()
    assert skill.version == "1.12"
    joined = " ".join(skill.style_rules)
    assert "design_objective and story caveated concepts are caveated content sources" in joined
    assert "realizes_story_node=false is implementation-binding material only" in joined
    assert "first answer the section's author-intended mechanism" in joined


def test_primary_concept_nests_supporting_facts() -> None:
    from code2paper.agentic.method_concept_card_models import MethodConceptCardV1
    from code2paper.agentic.writer_view_projection import build_writer_view_from_concept_cards

    primary = MethodConceptCardV1(
        concept_key="CK-CORE",
        authority_lane="repository",
        method_subject="hybrid attention",
        operation="mixes token and graph context",
        may_enter_verified=True,
        realized_story_node_ids=("story:attn",),
    )
    supporting = MethodConceptCardV1(
        concept_key="CK-GUARD",
        authority_lane="repository",
        method_subject="shape guard",
        operation="asserts tensor rank",
        may_enter_verified=True,
    )
    view = build_writer_view_from_concept_cards(
        heading="Attention",
        reader_question="How does attention mix context?",
        section_goal="Explain hybrid attention.",
        cards=[primary, supporting],
        callback_opportunities=[],
        primary_concept_keys=("CK-CORE",),
        supporting_concept_keys=("CK-GUARD",),
    )
    core = next(item for item in view.positive_concepts if item.concept_key == "CK-CORE")
    assert any(fact.concept_key == "CK-GUARD" for fact in core.supporting_facts)
    assert core.supporting_facts[0].role == "supporting"
    assert all(item.concept_key != "CK-GUARD" for item in view.positive_concepts)


def test_supporting_facts_nest_only_under_matching_primary() -> None:
    from code2paper.agentic.method_concept_card_models import MethodConceptCardV1
    from code2paper.agentic.writer_view_projection import build_writer_view_from_concept_cards

    core = MethodConceptCardV1(
        concept_key="CK-CORE",
        authority_lane="repository",
        method_subject="hybrid attention",
        operation="mixes token and graph context",
        may_enter_verified=True,
        realized_story_node_ids=("story:attn",),
    )
    other = MethodConceptCardV1(
        concept_key="CK-OTHER",
        authority_lane="repository",
        method_subject="graph construction",
        operation="builds heterogeneous edges",
        may_enter_verified=True,
        realized_story_node_ids=("story:graph",),
    )
    supporting = MethodConceptCardV1(
        concept_key="CK-GUARD",
        authority_lane="repository",
        method_subject="shape guard",
        operation="asserts tensor rank",
        may_enter_verified=True,
        realized_story_node_ids=("story:attn",),
    )
    view = build_writer_view_from_concept_cards(
        heading="Attention",
        reader_question="How does attention mix context?",
        section_goal="Explain hybrid attention.",
        cards=[core, other, supporting],
        callback_opportunities=[],
        primary_concept_keys=("CK-CORE", "CK-OTHER"),
        supporting_concept_keys=("CK-GUARD",),
    )
    by_key = {item.concept_key: item for item in view.positive_concepts}
    assert any(fact.concept_key == "CK-GUARD" for fact in by_key["CK-CORE"].supporting_facts)
    assert not any(fact.concept_key == "CK-GUARD" for fact in by_key["CK-OTHER"].supporting_facts)


def test_story_primary_coverage_ignores_guard_only_witnesses() -> None:
    claim_set = _claim_set()
    plan = build_method_section_plan(claims=claim_set)
    graph = plan.sections[0].model_copy(update={
        "primary_concept_keys": ("CK-CORE",),
        "supporting_concept_keys": ("CK-GUARD",),
        "formula_obligation_ids": ("formula:equation:core",),
    })
    plan = MethodSectionPlanV2.model_validate(plan.model_copy(update={
        "sections": (graph, *plan.sections[1:]),
    }).model_dump(mode="json"))
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:writer-quality",
        project_tree_hash="sha256:tree",
        items=[],
    )
    ledger = FinalTextAuthorshipLedgerV1(final_text_digest="sha256:text")
    core = PublicationMethodSectionOutputV1(
        section_id=graph.section_id,
        heading_text="Hybrid attention",
        section_markdown=(
            "## Hybrid attention\n\nHybrid attention mixes token and graph context."
        ),
        rendered_concept_keys=["CK-CORE"],
        used_equation_ids=["equation:core"],
    )
    guards_only = PublicationMethodSectionOutputV1(
        section_id=graph.section_id,
        heading_text="Padding check",
        section_markdown="## Padding check\n\nA padding check rejects empty batches.",
        rendered_concept_keys=["CK-GUARD"],
        used_equation_ids=[],
        completed_rhetorical_moves=["equation_or_derivation"],
    )
    core_report = evaluate_publication_method_quality(
        final_text=core.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=[core],
        ledger=ledger,
    )
    guard_report = evaluate_publication_method_quality(
        final_text=guards_only.section_markdown,
        plan=plan,
        completeness=completeness,
        section_outputs=[guards_only],
        ledger=ledger,
    )
    assert core_report.utility.story_primary_coverage == 1.0
    assert guard_report.utility.story_primary_coverage == 0.0
    assert core_report.utility.formula_obligation_coverage == 1.0
    assert guard_report.utility.formula_obligation_coverage == 0.0
