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


def test_binding_term_extraction_is_deterministic() -> None:
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
