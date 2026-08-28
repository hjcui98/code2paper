from __future__ import annotations

from code2paper.agentic.publication_issue_owner_router import route_publication_issue
from code2paper.agentic.research_models import TextRepairIssueV1
from code2paper.agentic.text_evidence_validator import (
    _comparison_polarity_flipped,
    _licensed_effect_match,
)
from code2paper.agentic.trust_contracts import ProjectedClaim
from code2paper.agentic.writing_callback_fulfillment import (
    WritingCallbackFulfillmentBudgetV1,
    fulfill_and_resume_writing_callbacks,
)
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
from code2paper.agentic.equation_claims import infer_formula_role


def test_fac_polarity_detects_eligible_if_less() -> None:
    match = ProjectedClaim(
        claim_id="l2-1",
        claim_text="Expansion excludes entities whose score fails the threshold.",
        support_status="supported",
        direct_evidence_ids=["S1"],
        supported_fragment="Expansion excludes entities whose score fails the threshold.",
        allowed_wording_boundary="effect interpretation licensed; polarity must match parent comparison units",
        inference_level="E2",
        input_digest="sha256:" + "a" * 64,
    )
    assert _comparison_polarity_flipped(
        "Entities remain eligible if entity_score < iteration_threshold.",
        [match],
    )
    assert not _comparison_polarity_flipped(
        "Thresholding excludes entities whose score fails the minimum.",
        [match],
    )
    assert _licensed_effect_match(
        "Thresholding excludes low-scoring frontier entities.",
        [match],
    )


def test_fac_wording_boundary_does_not_enable_rewrite_owner() -> None:
    route = route_publication_issue(
        TextRepairIssueV1(
            sentence_id="s-wording",
            failure_type="missing_qualifier",
            allowed_repair_scope="wording_only",
        ),
        section_id="MA-S4",
    )
    assert route.owner == "writer"


def test_lone_binary_formula_is_incidental() -> None:
    fact = CodeFactV1(
        fact_id="F1",
        subject="entity_score",
        predicate="computes_formula",
        object=["entity_score", "top_sentence_score"],
        scope="activate",
        direct_span_ids=["S1"],
        exact_source_digest="sha256:e",
        canonical_identity="sha256:f",
        semantic_context=["*"],
    )
    assert infer_formula_role(fact=fact, diagnostic="mult") == "incidental"


def test_callback_env_zero_short_circuits(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CODE2PAPER_MAX_CALLBACK_ROUNDS", "0")
    _paths, _status, _blocked, result = fulfill_and_resume_writing_callbacks(
        runtime=None,
        out_root=tmp_path,
        artifact_paths={},
        writer_paths={},
        llm_config=None,
        budget=WritingCallbackFulfillmentBudgetV1(max_callback_rounds=3),
    )
    assert result.stopped_reason == "callback_gated_off"
    assert result.rounds_attempted == 0


def test_callback_skips_compile_of_symbols_already_in_fact_store() -> None:
    from code2paper.agentic.writing_callback_fulfillment import (
        _BudgetedRepositoryCallbackProvider,
        WritingCallbackFulfillmentBudgetV1,
    )

    facts = CodeFactSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:p",
        facts=[
            CodeFactV1(
                fact_id="F-ppr",
                subject="run_ppr",
                predicate="computes",
                object="passage_scores",
                scope="ppr",
                direct_span_ids=["S1"],
                exact_source_digest="sha256:e",
                canonical_identity="sha256:f",
                semantic_context=["PersonalizedPageRank"],
            )
        ],
        content_digest="sha256:facts",
    )
    provider = _BudgetedRepositoryCallbackProvider(
        runtime=None,
        facts=facts,
        plan=None,
        callback_root=None,  # type: ignore[arg-type]
        budget=WritingCallbackFulfillmentBudgetV1(),
    )
    names = provider._known_symbol_names()
    assert "run_ppr" in names
    assert "personalizedpagerank" in names


def test_ppr_claim_does_not_license_first_retrieval_brief() -> None:
    from code2paper.agentic.evidence_compiler_v3 import AtomicClaimV3
    from code2paper.agentic.method_argument_brief_compiler import _claim_fits_story_node
    from code2paper.agentic.method_product_models import AuthorStoryNodeV1

    claim = AtomicClaimV3(
        claim_id="c-ppr",
        canonical_text="run_ppr aggregates hybrid passage scores with damping",
        fact_ids=["F1"],
        covers_obligation_ids=["O-STAGE-03"],
        direct_evidence_ids=["S1"],
        allowed_wording_boundary="exact",
        canonical_identity="sha256:c",
    )
    node = AuthorStoryNodeV1(
        story_node_id="story:first",
        title="First retrieval: local activation via semantic bridging",
        author_statement="Entity activation via local semantic bridging",
        linked_obligation_ids=("O-ORGANIZATION-04",),
    )
    assert _claim_fits_story_node(claim, node, ()) is False
