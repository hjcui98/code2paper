"""Stage 2 compiler tests: bounded clusters -> phrase concept cards."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
)
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
)
from code2paper.agentic.method_concept_card_compiler import (
    build_concept_candidate_clusters,
    compile_method_concept_cards,
)
from code2paper.agentic.method_concept_card_models import (
    ConceptCardBindingV1,
    ConceptCardEvidenceVerdictV1,
    ConceptCardFieldJudgmentV1,
    MethodConceptCardProposalBatchV1,
    MethodConceptCardProposalV1,
    MethodConceptCardSetV1,
    MethodConceptCardV1,
)
from code2paper.agentic.method_product_models import AuthorStoryNodeV1


def _claims(**overrides):
    claim = AtomicClaimV3(
        claim_id="C1",
        canonical_text="The per-primitive descriptor concatenates local z-score, global z-score, and RGB color.",
        fact_ids=["F1"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S1"],
        relation_evidence_ids=["RV1"],
        allowed_wording_boundary="only the descriptor composition",
        canonical_identity="sha256:claim",
    )
    claim_partial = AtomicClaimV3(
        claim_id="C2",
        canonical_text="The combined descriptor is percentile-clipped and rescaled between the 0.01 and 0.99 quantiles.",
        fact_ids=["F2"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S2"],
        relation_evidence_ids=["RV1"],
        status="partial",
        allowed_wording_boundary="only the normalization step",
        canonical_identity="sha256:claim2",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim, claim_partial],
        content_digest="sha256:claims",
    )
    return claims


def _supported_only_claims():
    """Repository cluster without any partial claim (verified-eligible).

    Two claims connected by one relation, exactly like the RAP descriptor ->
    normalizer data flow, so the closed fragment set has frag-1 and frag-2.
    """
    claim = AtomicClaimV3(
        claim_id="C1",
        canonical_text="The per-primitive descriptor concatenates local z-score, global z-score, and RGB color.",
        fact_ids=["F1"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S1"],
        relation_evidence_ids=["RV1"],
        allowed_wording_boundary="only the descriptor composition",
        canonical_identity="sha256:claim",
    )
    claim_norm = AtomicClaimV3(
        claim_id="C3",
        canonical_text="The combined descriptor is percentile-clipped and rescaled between the 0.01 and 0.99 quantiles.",
        fact_ids=["F3"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S3"],
        relation_evidence_ids=["RV1"],
        allowed_wording_boundary="only the normalization step",
        canonical_identity="sha256:claim3",
    )
    return AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim, claim_norm],
        content_digest="sha256:claims",
    )


def _completeness():
    return MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="O-FEATURE", role="feature extraction",
            statement="Construct a compact per-primitive descriptor and normalize it.",
            status="supported_by_repository",
            matched_fact_ids=("F1",), matched_span_ids=("S1",),
        ),
        MethodCompletenessItemV1(
            obligation_id="O-INFERENCE", role="deployment",
            statement="At deployment, the intended path avoids rendering.",
            status="author_confirmation_required",
            reason="repository evidence is not yet available",
        ),
    ))


def _spine():
    return (
        AuthorStoryNodeV1(
            story_node_id="ST-F", title="Feature extraction",
            author_statement="Build the descriptor.",
            linked_obligation_ids=("O-FEATURE",),
            evidence_lane="repository_verified",
        ),
        AuthorStoryNodeV1(
            story_node_id="ST-D", title="Deployment",
            author_statement="Avoid rendering.",
            linked_obligation_ids=("O-INFERENCE",),
            evidence_lane="author_intent_unverified",
        ),
    )


def _architect(cluster):
    if cluster.origin == "repository":
        return MethodConceptCardProposalBatchV1(
            cluster_id=cluster.cluster_id,
            proposals=(
                MethodConceptCardProposalV1(
                    cluster_id=cluster.cluster_id,
                    method_subject="per-primitive descriptor",
                    operation="concatenates local and global statistics and RGB color",
                    inputs=("raw Gaussian attributes",),
                    outputs=("normalized feature tensor",),
                    evidence_fragment_refs=("frag-1", "frag-2"),
                    story_node=cluster.story_node,
                ),
            ),
        )
    return MethodConceptCardProposalV1(
        cluster_id=cluster.cluster_id,
        method_subject="deployment path",
        operation="intended to avoid rendering",
        candidate_caveat="author-attested; no repository witness yet",
        missing_parts=("rendering-free inference is not closed in code",),
    )


def test_build_clusters_repository_and_author_intent():
    clusters = build_concept_candidate_clusters(
        claims=_claims(),
        story_spine=_spine(),
        completeness=_completeness(),
    )
    origins = {cluster.origin for cluster in clusters}
    assert origins == {"repository", "author_intent"}
    repo = next(c for c in clusters if c.origin == "repository")
    assert repo.source_fragments
    assert repo.source_span_ids
    assert repo.story_node == "Feature extraction"
    author = next(c for c in clusters if c.origin == "author_intent")
    assert author.source_fragments
    assert not author.source_span_ids


def test_repository_cluster_bounds_fragments():
    clusters = build_concept_candidate_clusters(
        claims=_claims(),
        story_spine=_spine(),
        completeness=_completeness(),
    )
    repo = next(c for c in clusters if c.origin == "repository")
    assert len(repo.source_fragments) <= len(_claims().claims) * 2
    assert repo.low_level_fact_count >= 1
    # Predicates are derived from typed behavior targets when the claim set
    # carries them; a fixture without targets legitimately yields an empty
    # tuple rather than inventing predicates.
    assert isinstance(repo.low_level_predicates, tuple)


def test_compile_cards_repository_and_author_separated():
    card_set, clusters = compile_method_concept_cards(
        claims=_supported_only_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    assert len(clusters) == 2
    assert len(card_set.cards) == 2
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    author_card = next(c for c in card_set.cards if c.authority_lane == "author_intent")
    assert repo_card.may_enter_verified
    assert not author_card.may_enter_verified
    assert repo_card.evidence_fragment_refs == ("frag-1", "frag-2")
    assert author_card.candidate_caveat
    assert card_set.content_digest.startswith("sha256:")
    assert len(card_set.bindings) == 2


def test_partial_repository_claim_blocks_verified():
    # Regression for the W diagnostic: a repository cluster containing a
    # partial claim must never enter the verified lane even when the
    # Architect proposes a confident card.
    card_set, _clusters = compile_method_concept_cards(
        claims=_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    assert not repo_card.may_enter_verified
    # Partial repository closure is a harness-visible caveat obligation, not
    # reader-facing missing parts (the model did not supply any).
    assert repo_card.requires_caveat


def test_compile_without_architect_emits_typed_gaps():
    card_set, clusters = compile_method_concept_cards(
        claims=_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=None,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    assert len(card_set.cards) == 0
    assert len(card_set.gaps) == len(clusters)
    assert all(gap.reason == "proposal_missing" for gap in card_set.gaps)


def test_compile_rejects_fragment_not_in_closed_set():
    def bad_architect(cluster):
        if cluster.origin == "author_intent":
            return MethodConceptCardProposalV1(
                cluster_id=cluster.cluster_id,
                method_subject="descriptor",
                operation="claimed by the author",
                candidate_caveat="author-attested",
            )
        return MethodConceptCardProposalV1(
            cluster_id=cluster.cluster_id,
            method_subject="descriptor",
            operation="concatenates statistics",
            evidence_fragment_refs=("frag-99",),  # not in closed set
        )

    card_set, _clusters = compile_method_concept_cards(
        claims=_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=bad_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    # After one repair attempt the bad card is dropped and a typed gap is emitted.
    assert len(card_set.gaps) >= 1
    assert any("fragment_not_closed" in gap.detail for gap in card_set.gaps)


def test_compile_rejects_authority_expansion_in_repository_card():
    def bad_architect(cluster):
        if cluster.origin == "author_intent":
            return MethodConceptCardProposalV1(
                cluster_id=cluster.cluster_id,
                method_subject="descriptor",
                operation="claimed by the author",
                candidate_caveat="author-attested",
            )
        return MethodConceptCardProposalV1(
            cluster_id=cluster.cluster_id,
            method_subject="descriptor",
            operation="concatenates statistics to enable pruning",
            evidence_fragment_refs=("frag-1",),
        )

    card_set, _clusters = compile_method_concept_cards(
        claims=_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=bad_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    assert any("authority_expansion" in gap.detail for gap in card_set.gaps)


def test_compile_deduplicates_identical_cards():
    def dup_architect(cluster):
        if cluster.origin == "author_intent":
            return MethodConceptCardProposalV1(
                cluster_id=cluster.cluster_id,
                method_subject="descriptor",
                operation="claimed by the author",
                candidate_caveat="author-attested",
            )
        proposal = MethodConceptCardProposalV1(
            cluster_id=cluster.cluster_id,
            method_subject="descriptor",
            operation="concatenates statistics",
            evidence_fragment_refs=("frag-1",),
        )
        return MethodConceptCardProposalBatchV1(
            cluster_id=cluster.cluster_id,
            proposals=(proposal, proposal.model_copy()),
        )

    card_set, _clusters = compile_method_concept_cards(
        claims=_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=dup_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_cards = [c for c in card_set.cards if c.authority_lane == "repository"]
    assert len(repo_cards) == 1


def test_compile_with_evidence_judge_gates_verified():
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardFieldJudgmentV1,
    )

    def judge(cards, cluster):
        return tuple(
            ConceptCardEvidenceVerdictV1(
                concept_key=card.concept_key,
                field_judgments=(
                    ConceptCardFieldJudgmentV1(
                        field_name="method_subject",
                        proposed_value=card.method_subject,
                        verdict="entailed",
                        evidence_fragment_refs=("frag-1",),
                        rationale="frag-1 establishes the subject",
                    ),
                    ConceptCardFieldJudgmentV1(
                        field_name="operation",
                        proposed_value=card.operation,
                        verdict=(
                            "entailed" if card.authority_lane == "repository"
                            else "not_found"
                        ),
                        evidence_fragment_refs=(
                            ("frag-1", "frag-2")
                            if card.authority_lane == "repository" else ()
                        ),
                        rationale=(
                            "frag-1 and frag-2 establish the operation"
                            if card.authority_lane == "repository"
                            else "no repository witness"
                        ),
                    ),
                ),
                overall_verdict=(
                    "entailed" if card.authority_lane == "repository" else "not_found"
                ),
                rationale=(
                    "every field entailed" if card.authority_lane == "repository"
                    else "no repository witness"
                ),
            )
            for card in cards
        )

    card_set, _clusters = compile_method_concept_cards(
        claims=_supported_only_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        evidence_judge=judge,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    assert repo_card.evidence_verdict == "entailed"
    assert repo_card.may_enter_verified
    author_card = next(c for c in card_set.cards if c.authority_lane == "author_intent")
    assert author_card.evidence_verdict == "not_found"
    assert not author_card.may_enter_verified
    assert len(card_set.evidence_verdicts) == 2


def test_compile_judge_contradiction_blocks_verified():
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardFieldJudgmentV1,
    )

    def contradict_judge(cards, cluster):
        return tuple(
            ConceptCardEvidenceVerdictV1(
                concept_key=card.concept_key,
                field_judgments=(
                    ConceptCardFieldJudgmentV1(
                        field_name="method_subject",
                        proposed_value=card.method_subject,
                        verdict="entailed",
                        evidence_fragment_refs=("frag-1",),
                        rationale="frag-1 establishes the subject",
                    ),
                    ConceptCardFieldJudgmentV1(
                        field_name="operation",
                        proposed_value=card.operation,
                        verdict="contradicted",
                        evidence_fragment_refs=("frag-2",),
                        rationale="frag-2 contradicts the proposed operation",
                    ),
                ),
                overall_verdict="contradicted",
                rationale="the excerpt contradicts the proposed operation",
            )
            for card in cards
        )

    card_set, _clusters = compile_method_concept_cards(
        claims=_supported_only_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        evidence_judge=contradict_judge,
        require_evidence_judge=True,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    assert repo_card.evidence_verdict == "contradicted"
    assert not repo_card.may_enter_verified


def test_phrase_budget_enforced_in_persisted_card():
    from code2paper.agentic.method_concept_card_models import MethodConceptCardV1

    with pytest.raises(ValidationError):
        MethodConceptCardV1(
            concept_key="CK-1",
            authority_lane="repository",
            method_subject="descriptor",
            operation="performs a long sequence of operations that continues beyond any reasonable phrase budget for a single operation field " * 3,
            may_enter_verified=False,
        )


def test_cards_are_readable_without_function_names():
    card_set, _clusters = compile_method_concept_cards(
        claims=_supported_only_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    surface = " ".join((repo_card.method_subject, repo_card.operation))
    # Reader-facing phrasing must not leak raw identifiers or harness meta-language.
    assert "frag-" not in surface
    assert "sym:" not in surface
    assert "binding" not in surface.casefold()
    assert repo_card.method_subject  # subject is human-readable


# ---------------------------------------------------------------------------
# Stage 3: per-field evidence judgment and precise field binding
# ---------------------------------------------------------------------------


def test_field_judgment_requires_rationale_for_non_not_found():
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardFieldJudgmentV1,
    )

    with pytest.raises(ValidationError):
        ConceptCardFieldJudgmentV1(
            field_name="operation",
            proposed_value="sorts scales",
            verdict="entailed",
            evidence_fragment_refs=("frag-1",),
            rationale="",  # mandatory
        )


def test_field_judgment_entailed_requires_fragment_refs():
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardFieldJudgmentV1,
    )

    with pytest.raises(ValidationError):
        ConceptCardFieldJudgmentV1(
            field_name="operation",
            proposed_value="sorts scales",
            verdict="entailed",
            evidence_fragment_refs=(),
            rationale="no refs",
        )
    # not_found without refs is allowed.
    ok = ConceptCardFieldJudgmentV1(
        field_name="purpose",
        proposed_value="for pruning",
        verdict="not_found",
        rationale="no caller/data-flow fragment",
    )
    assert ok.verdict == "not_found"


def test_verdict_requires_field_judgments_and_unique_fields():
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardFieldJudgmentV1,
    )

    with pytest.raises(ValidationError):
        ConceptCardEvidenceVerdictV1(
            concept_key="CK-1",
            field_judgments=(),
            overall_verdict="not_found",
            rationale="",
        )
    with pytest.raises(ValidationError):
        ConceptCardEvidenceVerdictV1(
            concept_key="CK-1",
            field_judgments=(
                ConceptCardFieldJudgmentV1(
                    field_name="operation", proposed_value="x",
                    verdict="not_found", rationale="no witness",
                ),
                ConceptCardFieldJudgmentV1(
                    field_name="operation", proposed_value="x",
                    verdict="not_found", rationale="no witness",
                ),
            ),
            overall_verdict="not_found",
            rationale="",
        )


def test_purpose_field_without_evidence_cannot_be_entailed():
    # Stage 3 rule: purpose/downstream claims without caller/data-flow
    # evidence must be partial/not_found — the harness downgrades an
    # entailed purpose judgment, so author motivation never becomes
    # repository fact.
    from code2paper.agentic.method_concept_card_compiler import (
        _enforce_purpose_evidence_rule,
    )
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardCandidateClusterV1,
        ConceptCardFieldJudgmentV1,
    )

    cluster = ConceptCardCandidateClusterV1(
        cluster_id="CC-P",
        origin="repository",
        research_question="How is the descriptor built?",
        source_fragments=(
            "input_features = torch.cat((local_z, global_z, rgb), dim=1)",
        ),
        source_span_ids=("span-1",),
    )
    verdict = ConceptCardEvidenceVerdictV1(
        concept_key="CK-P",
        field_judgments=(
            ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="concatenates",
                verdict="entailed",
                evidence_fragment_refs=("frag-1",),
                rationale="frag-1 concatenates",
            ),
            ConceptCardFieldJudgmentV1(
                field_name="outputs", proposed_value="for pruning",
                verdict="entailed",
                evidence_fragment_refs=("frag-1",),
                rationale="frag-1 mentions the descriptor",
            ),
        ),
        overall_verdict="entailed",
        rationale="all entailed",
    )
    enforced = _enforce_purpose_evidence_rule(verdict, cluster)
    assert enforced.overall_verdict == "partial"
    by_name = {item.field_name: item for item in enforced.field_judgments}
    assert by_name["outputs"].verdict == "partial"
    assert "no caller/data-flow evidence" in by_name["outputs"].rationale
    # With a caller/data-flow witness the purpose judgment survives.
    cluster_call = ConceptCardCandidateClusterV1(
        cluster_id="CC-P2",
        origin="repository",
        research_question="How is the descriptor consumed?",
        source_fragments=(
            "scores = predictor(input_features)",
        ),
        source_span_ids=("span-2",),
    )
    verdict_ok = ConceptCardEvidenceVerdictV1(
        concept_key="CK-P2",
        field_judgments=(
            ConceptCardFieldJudgmentV1(
                field_name="outputs", proposed_value="as a predictor input",
                verdict="entailed",
                evidence_fragment_refs=("frag-1",),
                rationale="frag-1 shows the predictor consuming the descriptor",
            ),
        ),
        overall_verdict="entailed",
        rationale="caller witness present",
    )
    kept = _enforce_purpose_evidence_rule(verdict_ok, cluster_call)
    assert kept.overall_verdict == "entailed"


def test_binder_binds_fields_to_exact_fragments_only():
    # Stage 3 exit condition: a volume/product card binds only its own
    # fragments, never sibling anisotropy/percentile fragments.
    from code2paper.agentic.method_concept_card_compiler import _bind_concept_card
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardCandidateClusterV1,
    )

    cluster = ConceptCardCandidateClusterV1(
        cluster_id="CC-VOL",
        origin="repository",
        research_question="How is volume derived?",
        source_fragments=(
            "volume = torch.prod(scales, dim=1, keepdim=True)",
            "anisotropy = energy from SH coefficients",
            "normalized = (clipped - lower) / (upper - lower)",
        ),
        source_span_ids=("span-1", "span-2", "span-3"),
    )
    proposal = MethodConceptCardProposalV1(
        cluster_id="CC-VOL",
        method_subject="scale-derived volume",
        operation="computes the product of scale statistics",
        outputs=("volume",),
        evidence_fragment_refs=("frag-1", "frag-2", "frag-3"),
    )
    binding = _bind_concept_card(cluster, proposal, concept_key="CK-VOL")
    by_field = dict(binding.field_bindings)
    # operation must bind ONLY frag-1 (product/scale) — not anisotropy
    # (frag-2) or percentile (frag-3).
    assert by_field["operation"] == ("frag-1",)
    assert "frag-2" not in by_field.get("operation", ())
    assert "frag-3" not in by_field.get("operation", ())
    # method_subject binds the fragment mentioning volume/scales.
    assert by_field["method_subject"] == ("frag-1",)


def test_binder_no_common_token_expansion():
    # Sibling evidence must not expand merely because it shares a mechanism
    # label with another field of the same card.
    from code2paper.agentic.method_concept_card_compiler import _bind_concept_card
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardCandidateClusterV1,
    )

    cluster = ConceptCardCandidateClusterV1(
        cluster_id="CC-NORM",
        origin="repository",
        research_question="How is the descriptor normalized?",
        source_fragments=(
            "normalized = (clipped - lower) / (upper - lower)",
            "percentile bounds 0.01 and 0.99 are used",
        ),
        source_span_ids=("span-1", "span-2"),
    )
    proposal = MethodConceptCardProposalV1(
        cluster_id="CC-NORM",
        method_subject="percentile normalization",
        operation="rescales between percentile bounds",
        numeric_constraints=("0.01", "0.99"),
        evidence_fragment_refs=("frag-1", "frag-2"),
    )
    binding = _bind_concept_card(cluster, proposal, concept_key="CK-NORM")
    by_field = dict(binding.field_bindings)
    assert "frag-1" in by_field["operation"]
    assert "frag-2" in by_field["numeric_constraints"]


def test_judge_failure_downgrades_repository_card_fail_closed():
    # A repository card whose per-field judge call fails must not keep its
    # initial verified eligibility: missing verdicts are not evidence.
    def failing_judge(cards, cluster):
        raise RuntimeError("judge transport failure")

    card_set, _clusters = compile_method_concept_cards(
        claims=_supported_only_claims(),
        completeness=_completeness(),
        story_spine=_spine(),
        architect=_architect,
        evidence_judge=failing_judge,
        require_evidence_judge=True,
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    repo_card = next(c for c in card_set.cards if c.authority_lane == "repository")
    assert not repo_card.may_enter_verified
    assert repo_card.evidence_verdict == "not_found"
    assert repo_card.requires_caveat
    assert any(gap.reason == "evidence_judge_failed" for gap in card_set.gaps)


# ---------------------------------------------------------------------------
# Stage 4 part 2: WriterView concept layer
# ---------------------------------------------------------------------------


def test_writer_view_from_concept_cards_separates_verified_and_caveated():
    from code2paper.agentic.writer_view_projection import (
        build_writer_view_from_concept_cards,
    )

    cards = [
        MethodConceptCardV1(
            concept_key="CK-V", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="per-primitive descriptor",
            operation="concatenates local and global statistics",
            numeric_constraints=("15",),
            may_enter_verified=True,
            evidence_verdict="entailed",
            realizes_story_node=True,
        ),
        MethodConceptCardV1(
            concept_key="CK-A", cluster_id="CC-2",
            authority_lane="author_intent",
            method_subject="intended pruning",
            operation="claimed by the author",
            candidate_caveat="author-attested; not yet closed in code",
            requires_caveat=True,
            missing_parts=("predictor interface",),
        ),
    ]
    view = build_writer_view_from_concept_cards(
        heading="Feature descriptor",
        reader_question="How is the descriptor built?",
        section_goal="Explain the descriptor and its intended use.",
        cards=cards,
        callback_opportunities=[],
    )
    assert len(view.positive_concepts) == 1
    assert len(view.caveated_concepts) == 1
    assert view.positive_concepts[0].concept_key == "CK-V"
    assert view.positive_concepts[0].numeric_constraints == ("15",)
    caveated = view.caveated_concepts[0]
    assert caveated.concept_key == "CK-A"
    assert caveated.required_caveat_kind == "author_intent"
    assert caveated.candidate_caveat
    # Closed allowed/required concept sets.
    assert set(view.allowed_concept_keys) == {"CK-V", "CK-A"}
    assert set(view.required_concept_keys) == {"CK-A"}
    assert view.view_digest.startswith("sha256:")


def test_writer_view_story_nodes_are_caveated_and_non_story_cards_are_not_required():
    from types import SimpleNamespace

    from code2paper.agentic.writer_view_projection import (
        build_writer_view_from_concept_cards,
    )

    cards = [
        MethodConceptCardV1(
            concept_key="CK-IMPL", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="filter layer forward",
            operation="applies the discrete filter step",
            may_enter_verified=True,
            evidence_verdict="entailed",
            realizes_story_node=False,
        ),
    ]
    view = build_writer_view_from_concept_cards(
        heading="Redesign",
        reader_question="How is the SSM redesigned?",
        section_goal="Redefine Delta t and A.",
        cards=cards,
        callback_opportunities=[],
        story_nodes=(
            SimpleNamespace(
                story_node_id="redesign",
                title="Redesign Delta t and A",
                author_statement="Redefine the step size and state matrix.",
            ),
        ),
    )
    assert view.positive_concepts[0].concept_key == "CK-IMPL"
    assert "CK-IMPL" not in view.required_concept_keys
    story = next(item for item in view.caveated_concepts if item.concept_key == "story:redesign")
    assert story.lane == "author_intent_unverified"
    assert story.required_caveat_kind == "author_intent"
    assert "repository implementation not verified" in story.candidate_caveat
    assert "story:redesign" in view.required_concept_keys


def test_writer_view_concept_constraints_carry_immutable_numbers():
    from code2paper.agentic.writer_view_projection import (
        build_writer_view_from_concept_cards,
    )

    cards = [
        MethodConceptCardV1(
            concept_key="CK-N", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="percentile normalization",
            operation="rescales between percentile bounds",
            numeric_constraints=("0.01", "0.99"),
            formula_constraints=("(clipped - lower) / (upper - lower)",),
            may_enter_verified=True,
            evidence_verdict="entailed",
        ),
    ]
    view = build_writer_view_from_concept_cards(
        heading="Normalization",
        reader_question="How is the descriptor normalized?",
        section_goal="Explain normalization.",
        cards=cards,
        callback_opportunities=[],
    )
    assert len(view.concept_constraints) == 1
    constraint = view.concept_constraints[0]
    assert constraint.concept_key == "CK-N"
    assert constraint.numeric_constraints == ("0.01", "0.99")
    assert constraint.formula_constraints


def test_wp1_writer_view_orders_primary_before_supporting() -> None:
    from code2paper.agentic.writer_view_projection import (
        build_writer_view_from_concept_cards,
    )

    cards = [
        MethodConceptCardV1(
            concept_key="CK-SUPPORT",
            cluster_id="CC-1",
            authority_lane="repository",
            method_subject="tensor padding",
            operation="pads the batch tensor",
            may_enter_verified=True,
            evidence_verdict="entailed",
        ),
        MethodConceptCardV1(
            concept_key="CK-PRIMARY",
            cluster_id="CC-2",
            authority_lane="repository",
            method_subject="core ranking",
            operation="ranks primitives by score",
            may_enter_verified=True,
            evidence_verdict="entailed",
            realized_story_node_ids=("story:rank",),
        ),
    ]
    view = build_writer_view_from_concept_cards(
        heading="Ranking",
        reader_question="How are primitives ranked?",
        section_goal="Explain ranking.",
        cards=cards,
        callback_opportunities=[],
        primary_concept_keys=("CK-PRIMARY",),
        supporting_concept_keys=("CK-SUPPORT",),
    )
    assert view.positive_concepts[0].concept_key == "CK-PRIMARY"
    assert view.required_concept_keys == ("CK-PRIMARY",)


def test_wp1_writer_view_excludes_audit_only_from_allowed_set() -> None:
    from code2paper.agentic.writer_view_projection import (
        build_writer_view_from_concept_cards,
    )

    cards = [
        MethodConceptCardV1(
            concept_key="CK-AUDIT",
            cluster_id="CC-1",
            authority_lane="repository",
            method_subject="chunk index bookkeeping",
            operation="iterates chunk indices",
            may_enter_verified=True,
            evidence_verdict="entailed",
        ),
        MethodConceptCardV1(
            concept_key="CK-MAIN",
            cluster_id="CC-2",
            authority_lane="repository",
            method_subject="ranking descriptor",
            operation="assembles per-primitive statistics",
            may_enter_verified=True,
            evidence_verdict="entailed",
        ),
    ]
    view = build_writer_view_from_concept_cards(
        heading="Ranking",
        reader_question="How are primitives ranked?",
        section_goal="Explain ranking.",
        cards=cards,
        callback_opportunities=[],
        audit_only_concept_keys=("CK-AUDIT",),
        primary_concept_keys=("CK-MAIN",),
    )
    assert "CK-AUDIT" not in view.allowed_concept_keys
    assert view.positive_concepts[0].concept_key == "CK-MAIN"


def test_realized_story_node_ids_are_digest_bound() -> None:
    base = MethodConceptCardV1(
        concept_key="CK-1",
        cluster_id="CC-1",
        authority_lane="repository",
        method_subject="ranking descriptor",
        operation="assembles per-primitive statistics",
        may_enter_verified=True,
        evidence_verdict="entailed",
    )
    bound = MethodConceptCardV1(
        concept_key="CK-1",
        cluster_id="CC-1",
        authority_lane="repository",
        method_subject="ranking descriptor",
        operation="assembles per-primitive statistics",
        may_enter_verified=True,
        evidence_verdict="entailed",
        realized_story_node_ids=("story:rank",),
    )
    assert bound.content_digest != base.content_digest
    assert bound.realizes_story_node is True


def test_writer_view_rejects_both_propositions_and_concepts():
    from code2paper.agentic.writer_view_projection import WriterViewV1

    with pytest.raises(ValidationError):
        WriterViewV1(
            purpose={"heading": "H", "reader_question": "Q", "section_goal": "G"},
            positive_propositions=(
                {"proposition_id": "MP-1", "reader_subject": "s",
                 "transformation": "t"},
            ),
            positive_concepts=(
                {"concept_key": "CK-1", "method_subject": "m", "operation": "o"},
            ),
            allowed_proposition_ids=("MP-1",),
            required_proposition_ids=("MP-1",),
            allowed_concept_keys=("CK-1",),
            required_concept_keys=("CK-1",),
        )


def test_writer_section_inputs_use_concept_view_when_cards_bound():
    """Stage 4 part 2: a section whose units carry concept cards gets a
    concept-based WriterView (positive/caveated concepts), not propositions."""
    from code2paper.agentic.evidence_compiler_v3 import (
        AtomicClaimV3,
        AtomicClaimSetV3,
    )
    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        MethodArgumentUnitV1,
        MethodCompletenessItemV1,
        MethodCompletenessMatrixV1,
        MethodSectionPlanV2,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
    )
    from code2paper.agentic.publication_method_writer import _writer_section_inputs
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        ConceptCardEvidenceVerdictV1,
        ConceptCardFieldJudgmentV1,
        MethodConceptCardSetV1,
    )
    from code2paper.agentic.equation_claims import EquationClaimSetV1

    claim = AtomicClaimV3(
        claim_id="C1",
        canonical_text="The per-primitive descriptor concatenates local z-score, global z-score, and RGB color.",
        fact_ids=["F1"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S1"],
        relation_evidence_ids=["RV1"],
        allowed_wording_boundary="only the descriptor composition",
        canonical_identity="sha256:claim",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree",
        evidence_packet_digest="sha256:p", code_fact_digest="sha256:f",
        claims=[claim], content_digest="sha256:c",
    )
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        items=[MethodCompletenessItemV1(
            obligation_id="O-FEATURE", role="feature extraction",
            statement="Construct the descriptor.", status="supported_by_repository",
        )],
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the descriptor built?",
        design_objective="Explain descriptor construction.",
        claim_ids=("C1",),
        source_obligation_ids=("O-FEATURE",),
        concept_card_ids=("CK-V",),
        verified_concept_card_ids=("CK-V",),
        caveated_concept_card_ids=(),
        concept_card_order=("CK-V",),
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-1",
        argument_units=[unit],
        sections=[SectionArgumentGraphV1(
            section_id="MA-S1", heading="Feature descriptor",
            reader_question="How is the descriptor built?",
            argument_unit_ids=("U1",),
            moves=[SectionArgumentMoveV1(move="mechanism_overview", required=True)],
        )],
        audience="method readers", method_name="Method",
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-V", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="per-primitive descriptor",
            operation="concatenates local and global statistics and RGB color",
            numeric_constraints=("15",),
            may_enter_verified=True,
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-V",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="concatenates",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the operation",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-V",
            field_bindings=(("operation", ("frag-1",)),),
            source_obligation_ids=("O-FEATURE",),
        )],
    )
    inputs = _writer_section_inputs(
        plan=plan, claims=claims,
        equations=EquationClaimSetV1(
            repo_snapshot_id="snap", project_tree_hash="tree",
            code_fact_digest="sha256:f", equations=[], content_digest="sha256:e",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="snap", project_tree_hash="tree",
        ),
        propositions=None,
        concept_cards=card_set,
    )
    assert len(inputs) == 1
    payload = inputs[0].prompt_payload
    writer_view = payload.get("writer_view")
    assert writer_view is not None
    assert writer_view["positive_concepts"][0]["concept_key"] == "CK-V"
    assert writer_view["positive_concepts"][0]["numeric_constraints"] == ["15"]
    binding = payload["binding_contract"]
    assert "CK-V" in binding["allowed_concept_keys"]
    assert "CK-V" in writer_view["allowed_concept_keys"]
    # The writer instruction mentions concepts.
    assert "positive_concepts" in payload["content_first_instruction"]


def test_concept_claim_ids_map_via_exact_span_bindings():
    """Stage 4 / WP2: concept->claim map uses exact span overlap only."""
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.publication_method_writer import _concept_claim_ids

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-1", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="descriptor",
            operation="concatenates statistics",
            may_enter_verified=True,
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-1",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="concatenates",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the operation",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-1",
            field_bindings=(("operation", ("frag-1",)),),
            source_obligation_ids=("O-FEATURE",),
            source_span_ids=("S1",),
        )],
    )
    claim_set = _supported_only_claims()
    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="F1",
            subject="sym:desc",
            predicate="concatenates",
            object="statistics",
            scope="sym:desc",
            direct_span_ids=["S1"],
            exact_source_digest="sha256:s",
            canonical_identity="sha256:f1",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )
    mapping = _concept_claim_ids(
        concept_cards=card_set, claims=claim_set, facts=facts,
    )
    assert mapping["CK-1"] == ("C1",)


def test_concept_claim_ids_do_not_expand_across_obligation_neighbors():
    """WP2: guard claim must not authorize core transformation on same obligation."""
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.publication_method_writer import _concept_claim_ids

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-GUARD", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="empty guard",
            operation="checks tensor is non-empty",
            may_enter_verified=True,
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-GUARD",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation",
                proposed_value="checks",
                verdict="entailed",
                evidence_fragment_refs=("frag-guard",),
                rationale="guard fragment",
            )],
            overall_verdict="entailed",
            rationale="entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-GUARD",
            source_span_ids=("span:guard",),
        )],
    )
    guard_claim = AtomicClaimV3(
        claim_id="claim-guard",
        canonical_text="The method guards against empty tensors.",
        fact_ids=["fact-guard"],
        covers_obligation_ids=["obl-1"],
        direct_evidence_ids=["span:guard"],
        allowed_wording_boundary="guard only",
        canonical_identity="sha256:guard",
    )
    transform_claim = AtomicClaimV3(
        claim_id="claim-transform",
        canonical_text="The method applies a core transformation.",
        fact_ids=["fact-transform"],
        covers_obligation_ids=["obl-1"],
        direct_evidence_ids=["span:transform"],
        allowed_wording_boundary="transform only",
        canonical_identity="sha256:transform",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[guard_claim, transform_claim],
        content_digest="sha256:claims",
    )
    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact-guard",
                subject="sym:g",
                predicate="branches_on",
                object="empty",
                scope="sym:g",
                direct_span_ids=["span:guard"],
                exact_source_digest="sha256:sg",
                canonical_identity="sha256:fg",
                validation_status="supported",
            ),
            CodeFactV1(
                fact_id="fact-transform",
                subject="sym:t",
                predicate="computes",
                object="tensor",
                scope="sym:t",
                direct_span_ids=["span:transform"],
                exact_source_digest="sha256:st",
                canonical_identity="sha256:ft",
                validation_status="supported",
            ),
        ],
        content_digest="sha256:facts",
    )
    mapping = _concept_claim_ids(
        concept_cards=card_set, claims=claims, facts=facts,
    )
    assert mapping["CK-GUARD"] == ("claim-guard",)
    assert "claim-transform" not in mapping["CK-GUARD"]


def test_concept_claim_ids_exclude_candidate_only_cards():
    """Stage 4 fail-closed: candidate-only concepts supply no claim IDs.

    A caveated card whose obligations still map to frozen claims must not
    leak repository claim IDs into the validation surface.  If it did, the
    reverse validator would find matches, skip the candidate-only branch
    (``not matches``), evaluate the prose as a repository claim and judge
    it ``unsupported`` instead of ``caveated``.
    """
    from code2paper.agentic.publication_method_writer import _concept_claim_ids

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[
            MethodConceptCardV1(
                concept_key="CK-V", cluster_id="CC-1",
                authority_lane="repository",
                method_subject="descriptor",
                operation="concatenates statistics",
                may_enter_verified=True,
                evidence_verdict="entailed",
            ),
            MethodConceptCardV1(
                concept_key="CK-C", cluster_id="CC-2",
                authority_lane="repository",
                method_subject="standardization",
                operation="combines statistics into a standardized descriptor",
                may_enter_verified=False,
                requires_caveat=True,
                candidate_caveat="author-intended; repository implementation not verified",
                evidence_verdict="entailed",
            ),
        ],
        evidence_verdicts=[
            ConceptCardEvidenceVerdictV1(
                concept_key="CK-V",
                field_judgments=[ConceptCardFieldJudgmentV1(
                    field_name="operation", proposed_value="concatenates",
                    verdict="entailed", evidence_fragment_refs=("frag-1",),
                    rationale="frag-1 establishes the operation",
                )],
                overall_verdict="entailed", rationale="all entailed",
            ),
            ConceptCardEvidenceVerdictV1(
                concept_key="CK-C",
                field_judgments=[ConceptCardFieldJudgmentV1(
                    field_name="operation", proposed_value="combines",
                    verdict="entailed", evidence_fragment_refs=("frag-1",),
                    rationale="frag-1 establishes the combination",
                )],
                overall_verdict="entailed", rationale="all entailed",
            ),
        ],
        bindings=[
            ConceptCardBindingV1(
                concept_key="CK-V",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("O-FEATURE",),
                source_span_ids=("S1",),
            ),
            ConceptCardBindingV1(
                concept_key="CK-C",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("O-FEATURE",),
                source_span_ids=("S1",),
            ),
        ],
    )
    claim_set = _supported_only_claims()
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="F1",
            subject="sym:desc",
            predicate="concatenates",
            object="statistics",
            scope="sym:desc",
            direct_span_ids=["S1"],
            exact_source_digest="sha256:s",
            canonical_identity="sha256:f1",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )
    mapping = _concept_claim_ids(
        concept_cards=card_set, claims=claim_set, facts=facts,
    )
    assert "CK-V" in mapping
    assert mapping["CK-V"] == ("C1",)
    # CK-C has the same obligation->claim path as CK-V, but it is
    # candidate-only, so it must not appear in the repository claim map.
    assert "CK-C" not in mapping


def test_align_final_claims_to_concept_cards_matches_section_concepts():
    """Stage 4: final-text claims bind to their section's concept keys."""
    from code2paper.agentic.publication_method_writer import (
        _align_final_claims_to_concept_cards,
    )
    from code2paper.agentic.trust_contracts import FinalAtomicClaim, FinalTextClaims

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-V", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="per-primitive descriptor",
            operation="concatenates local and global statistics and RGB color",
            may_enter_verified=True,
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-V",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="concatenates",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the operation",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-V",
            field_bindings=(("operation", ("frag-1",)),),
            source_obligation_ids=("O-FEATURE",),
        )],
    )
    claim = FinalAtomicClaim(
        atomic_claim_id="FC-1",
        unit_id="MA-S1",
        text="The per-primitive descriptor concatenates local z-score, global z-score, and RGB color.",
        normalized_text="the per-primitive descriptor concatenates local z-score, global z-score, and rgb color",
        line_start=0,
        line_end=2,
        char_start=0,
        char_end=80,
        candidate_direct_evidence_ids=["S1"],
        claim_digest="sha256:fc",
    )
    final_claims = FinalTextClaims(
        input_text_digest="sha256:text",
        atomic_claims=[claim],
    )
    aligned = _align_final_claims_to_concept_cards(
        final_claims=final_claims,
        accepted=[("MA-S1", "## H\n\nThe per-primitive descriptor concatenates local z-score, global z-score, and RGB color.", "ref-1")],
        plan=_concept_bound_plan(),
        concept_cards=card_set,
        llm_config=None,
    )
    assert aligned.atomic_claims[0].candidate_method_proposition_ids == ["CK-V"]


def _concept_bound_plan():
    from code2paper.agentic.method_argument_models import (
        MethodArgumentUnitV1,
        MethodSectionPlanV2,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
    )

    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the descriptor built?",
        claim_ids=("C1",),
        source_obligation_ids=("O-FEATURE",),
        concept_card_ids=("CK-V",),
        verified_concept_card_ids=("CK-V",),
        concept_card_order=("CK-V",),
    )
    return MethodSectionPlanV2(
        plan_id="plan-1",
        argument_units=[unit],
        sections=[SectionArgumentGraphV1(
            section_id="MA-S1", heading="Feature descriptor",
            reader_question="How is the descriptor built?",
            argument_unit_ids=("U1",),
            moves=[SectionArgumentMoveV1(move="mechanism_overview", required=True)],
        )],
        audience="method readers", method_name="Method",
    )


def test_heading_break_normalization_splits_fused_heading():
    from code2paper.agentic.publication_method_writer import (
        _normalize_section_heading_breaks,
    )

    fused = "## Transformation and output  Scale and opacity statistics sort scale values."
    normalized = _normalize_section_heading_breaks(fused)
    assert normalized == (
        "## Transformation and output\n\n"
        "Scale and opacity statistics sort scale values."
    )
    # Clean headings and body lines stay untouched.
    clean = "## Feature descriptor\n\nBody text."
    assert _normalize_section_heading_breaks(clean) == clean


def test_heading_break_normalization_splits_at_expected_heading_boundary():
    """Stage 4/5 fail-closed: a heading fused to its body WITHOUT whitespace
    (``## Transformation and outputScale values...``) must still split at the
    Architect's expected heading boundary, or the whole factual paragraph is
    classified as a heading and leaks into the verified document as
    scaffolding."""
    from code2paper.agentic.publication_method_writer import (
        _normalize_section_heading_breaks,
    )

    fused = (
        "## Transformation and outputScale values undergo sorting, and volume "
        "computation follows product reduction across the scale dimensions. "
        "This descriptor construction relies on author-intended descriptor "
        "composition and normalization; repository implementation not verified."
    )
    normalized = _normalize_section_heading_breaks(
        fused, expected_heading="Transformation and output"
    )
    assert normalized.startswith("## Transformation and output\n\n")
    assert "Scale values undergo sorting" in normalized
    # The body must be a separate line so the extractor sees factual prose.
    body_line = normalized.split("\n\n", 1)[1]
    assert body_line.startswith("Scale values undergo sorting")
    assert "author-intended" in body_line
    # Without the expected heading the fused form is NOT split (no whitespace
    # boundary exists), but with it the split is exact and deterministic.
    assert _normalize_section_heading_breaks(fused) == fused
    # A long sentence heading (MA-S2 style) splits at its own boundary.
    long_heading = (
        "From raw Gaussian attributes, extract a compact 15-dimensional "
        "per-primitive feature descriptor and normalize it before"
    )
    fused2 = (
        "## From raw Gaussian attributes, extract a compact 15-dimensional "
        "per-primitive feature descriptor and normalize it before"
        "Gaussian Primitive Descriptor Extraction transforms raw Gaussian "
        "attributes into a normalized 15-dimensional feature descriptor."
    )
    normalized2 = _normalize_section_heading_breaks(
        fused2, expected_heading=long_heading
    )
    assert normalized2.startswith("## " + long_heading + "\n\n")
    assert normalized2.split("\n\n", 1)[1].startswith(
        "Gaussian Primitive Descriptor Extraction transforms"
    )


def test_heading_break_normalization_strips_hash_prefix_on_expected_heading():
    """Gate 6B DyG 085518: Writer heading_text included ``## ``, so acceptance
    passed that string as expected_heading and the fuse-split never fired."""
    from code2paper.agentic.publication_method_writer import (
        _markdown_has_non_heading_body,
        _normalize_section_heading_breaks,
        _section_output_acceptable,
    )

    plan_heading = (
        "Motivation: limitations of vanilla SSMs – they ignore irregular "
        "timespans and are vulnerable to input noise Motivation"
    )
    fused_two_space = (
        f"## {plan_heading}  Vanilla state-space models assume uniform step "
        "sizes and treat all input features with equal weight."
    )
    for expected in (plan_heading, f"## {plan_heading}"):
        normalized = _normalize_section_heading_breaks(
            fused_two_space, expected_heading=expected
        )
        assert normalized.startswith("## " + plan_heading + "\n\n")
        assert "Vanilla state-space models" in normalized.split("\n\n", 1)[1]
        assert _markdown_has_non_heading_body(normalized)
        assert _section_output_acceptable(
            fused_two_space, expected_heading=plan_heading
        ) is False  # duplicate trailing Motivation is residual

    downstream = (
        "Downstream adaptation: link prediction and node classification setups"
    )
    fused_no_space = (
        f"## {downstream}Downstream task adaptation applies learned node "
        "representations to link prediction and node classification tasks."
    )
    for expected in (downstream, f"## {downstream}"):
        normalized = _normalize_section_heading_breaks(
            fused_no_space, expected_heading=expected
        )
        assert normalized.startswith("## " + downstream + "\n\n")
        assert normalized.split("\n\n", 1)[1].startswith("Downstream task adaptation")
        assert _section_output_acceptable(
            fused_no_space, expected_heading=downstream
        )


def test_concept_alignment_prefers_caveated_when_semantics_overlap():
    """Stage 4 fail-closed: a sentence that also matches a caveated concept
    must not ride on a verified concept alone."""
    from code2paper.agentic.publication_method_writer import (
        _align_final_claims_to_concept_cards,
    )
    from code2paper.agentic.trust_contracts import FinalAtomicClaim, FinalTextClaims

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=(
            MethodConceptCardV1(
                concept_key="CK-V", cluster_id="CC-1",
                authority_lane="repository",
                method_subject="descriptor composition",
                operation="concatenates local and global statistics",
                may_enter_verified=True,
                evidence_verdict="entailed",
            ),
            MethodConceptCardV1(
                concept_key="CK-A", cluster_id="CC-2",
                authority_lane="author_intent",
                method_subject="intended standardization",
                operation="standardizes inputs prior to prediction",
                candidate_caveat="author-intended",
                requires_caveat=True,
            ),
        ),
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-V",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="concatenates",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the operation",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=(
            ConceptCardBindingV1(
                concept_key="CK-V",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("O-FEATURE",),
            ),
            ConceptCardBindingV1(
                concept_key="CK-A",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("O-FEATURE",),
            ),
        ),
    )
    claim = FinalAtomicClaim(
        atomic_claim_id="FC-1",
        unit_id="MA-S1",
        text="This standardization step standardizes the inputs prior to prediction; the exact formula remains author-intended and unverified.",
        normalized_text="this standardization step standardizes the inputs prior to prediction the exact formula remains author-intended and unverified",
        line_start=0, line_end=2, char_start=0, char_end=110,
        candidate_direct_evidence_ids=["S1"],
        claim_digest="sha256:fc",
    )
    final_claims = FinalTextClaims(
        input_text_digest="sha256:text",
        atomic_claims=[claim],
    )
    from code2paper.agentic.method_argument_models import (
        MethodArgumentUnitV1,
        MethodSectionPlanV2,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
    )

    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the descriptor built?",
        claim_ids=("C1",),
        source_obligation_ids=("O-FEATURE",),
        concept_card_ids=("CK-V", "CK-A"),
        verified_concept_card_ids=("CK-V",),
        caveated_concept_card_ids=("CK-A",),
        concept_card_order=("CK-V", "CK-A"),
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-1",
        argument_units=[unit],
        sections=[SectionArgumentGraphV1(
            section_id="MA-S1", heading="Feature descriptor",
            reader_question="How is the descriptor built?",
            argument_unit_ids=("U1",),
            moves=[SectionArgumentMoveV1(move="mechanism_overview", required=True)],
        )],
        audience="method readers", method_name="Method",
    )
    aligned = _align_final_claims_to_concept_cards(
        final_claims=final_claims,
        accepted=[(
            "MA-S1",
            "## Transformation and output\n\nThis standardization step standardizes the inputs prior to prediction.",
            "ref-1",
        )],
        plan=plan,
        concept_cards=card_set,
        llm_config=None,
    )
    # The sentence strongly matches the caveated standardization concept, so
    # it must bind CK-A, not the verified composition concept.
    assert aligned.atomic_claims[0].candidate_method_proposition_ids == ["CK-A"]


# ---------------------------------------------------------------------------
# Stage 5: concept-bearing writing research callbacks
# ---------------------------------------------------------------------------


def test_writing_research_request_carries_concept_payload_and_digest():
    """Stage 5: a request may name the caveated concept and its missing parts."""
    from code2paper.agentic.method_argument_models import WritingResearchRequestV1

    plain = WritingResearchRequestV1(
        request_id="request:MA-S1:limitations_or_mismatch",
        section_id="MA-S1",
        argument_unit_id="U1",
        missing_rhetorical_move="limitations_or_mismatch",
        exact_question="Which evidence resolves the standardization formula?",
        required_authority_lane="executable_hard",
    )
    assert plain.concept_key == ""
    assert plain.missing_parts == ()
    assert plain.evidence_refs_used == ()

    concept_bound = WritingResearchRequestV1(
        request_id="request:MA-S1:limitations_or_mismatch",
        section_id="MA-S1",
        argument_unit_id="U1",
        missing_rhetorical_move="limitations_or_mismatch",
        exact_question="Which evidence resolves the standardization formula?",
        required_authority_lane="executable_hard",
        concept_key="CK-C",
        missing_parts=("exact standardization formula", "normalization bounds"),
        evidence_refs_used=("frag-1",),
    )
    assert concept_bound.concept_key == "CK-C"
    assert concept_bound.missing_parts == (
        "exact standardization formula", "normalization bounds",
    )
    assert concept_bound.evidence_refs_used == ("frag-1",)
    # Concept fields are digest-covered: changing them changes the digest.
    assert concept_bound.content_digest != plain.content_digest
    altered = WritingResearchRequestV1(
        request_id="request:MA-S1:limitations_or_mismatch",
        section_id="MA-S1",
        argument_unit_id="U1",
        missing_rhetorical_move="limitations_or_mismatch",
        exact_question="Which evidence resolves the standardization formula?",
        required_authority_lane="executable_hard",
        concept_key="CK-OTHER",
        missing_parts=("exact standardization formula", "normalization bounds"),
        evidence_refs_used=("frag-1",),
    )
    assert altered.content_digest != concept_bound.content_digest


def test_concept_callback_prototype_payload_covers_only_caveated_cards():
    """Stage 5: prototype payload binds caveated concepts with missing parts."""
    from code2paper.agentic.publication_method_writer import (
        _concept_callback_prototype_payload,
    )

    verified = MethodConceptCardV1(
        concept_key="CK-V", cluster_id="CC-1",
        authority_lane="repository",
        method_subject="descriptor",
        operation="concatenates statistics",
        may_enter_verified=True,
        evidence_verdict="entailed",
    )
    caveated = MethodConceptCardV1(
        concept_key="CK-C", cluster_id="CC-2",
        authority_lane="repository",
        method_subject="standardization",
        operation="combines statistics into a standardized descriptor",
        may_enter_verified=False,
        requires_caveat=True,
        candidate_caveat="author-intended; repository implementation not verified",
        missing_parts=("exact standardization formula", "normalization bounds"),
        evidence_fragment_refs=("frag-1",),
        known_parts=("15-dimensional composition",),
        evidence_verdict="entailed",
    )
    payload = _concept_callback_prototype_payload(
        section_concepts=[verified, caveated]
    )
    assert "concept_binding" in payload
    assert payload["concept_binding"][0]["concept_key"] == "CK-C"
    assert payload["concept_binding"][0]["missing_parts"] == [
        "exact standardization formula", "normalization bounds",
    ]
    assert payload["concept_binding"][0]["evidence_refs_used"] == ["frag-1"]
    assert payload["exact_question"]
    # A section with only verified concepts produces no concept payload.
    assert _concept_callback_prototype_payload(section_concepts=[verified]) == {}
    # A caveated card without missing parts still requires a caveat, so it
    # stays eligible: the researcher may resolve the caveat itself.
    bare_caveated = caveated.model_copy(update={"missing_parts": ()})
    payload2 = _concept_callback_prototype_payload(
        section_concepts=[verified, bare_caveated]
    )
    assert payload2["concept_binding"][0]["concept_key"] == "CK-C"


def test_writing_callback_contract_rejects_invented_concept_key():
    """Stage 5 fail-closed: a request may name only section-closed concepts."""
    from code2paper.agentic.method_argument_models import (
        MethodArgumentUnitV1,
        MethodSectionPlanV2,
        MoveAuthorityProofV1,
        ObligationMoveAssignmentV1,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
        SemanticArgumentFrameV1,
        SemanticFlowSlotV1,
    )
    from code2paper.agentic.publication_method_writer import (
        _check_writing_callback_contract,
    )
    from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1

    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the descriptor built?",
        claim_ids=("C1",),
        source_obligation_ids=("O-FEATURE",),
        concept_card_ids=("CK-C",),
        caveated_concept_card_ids=("CK-C",),
        semantic_frame=SemanticArgumentFrameV1(
            frame_id="frame:U1",
            argument_unit_id="U1",
            slots=[SemanticFlowSlotV1(
                slot_id="slot:1", role="transformation",
                subject="standardization", predicate="applies",
                operands=("scale_statistics",),
                fact_ids=("F1",), claim_ids=("C1",),
            )],
            ordered_slot_ids=("slot:1",),
            fact_ids=("F1",), claim_ids=("C1",),
        ),
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S1", heading="Standardization",
        reader_question="How is the descriptor standardized?",
        argument_unit_ids=("U1",),
        moves=[SectionArgumentMoveV1(
            move="limitations_or_mismatch",
            argument_unit_ids=("U1",),
            required=True,
        )],
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-1",
        method_name="Method",
        argument_units=[unit],
        sections=[graph],
        move_authority_proofs=[MoveAuthorityProofV1(
            section_id="MA-S1",
            argument_unit_ids=("U1",),
            move="limitations_or_mismatch",
            required=True,
            unresolved_obligation_ids=("O-FEATURE",),
            required_authority_lane="executable_hard",
            state="open",
        )],
        obligation_assignments=[ObligationMoveAssignmentV1(
            obligation_id="O-FEATURE",
            importance="critical",
            status="partially_supported_by_repository",
            authority_lane="executable_hard",
            section_id="MA-S1",
            argument_unit_id="U1",
            required_move="limitations_or_mismatch",
            placement_state="assigned",
        )],
        audience="method readers",
    )
    unit_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    authority_proofs = plan.proofs_by_key()

    def _output(requests):
        return PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            section_markdown="## Standardization\n\nThe standardization remains intended.",
            new_research_requests=requests,
        )

    closed_request = [{
        "request_id": "request:MA-S1:limitations_or_mismatch",
        "section_id": "MA-S1",
        "argument_unit_id": "U1",
        "missing_rhetorical_move": "limitations_or_mismatch",
        "exact_question": "Which evidence resolves the normalization bounds?",
        "required_authority_lane": "executable_hard",
        "candidate_symbols_or_terms": ["standardization", "scale_statistics"],
        "concept_key": "CK-C",
        "missing_parts": ["normalization bounds"],
        "evidence_refs_used": ["frag-1"],
        "status": "open",
    }]
    failures: list[str] = []
    _check_writing_callback_contract(
        failures,
        output=_output(closed_request),
        graph=graph,
        unit_by_id=unit_by_id,
        authority_proofs=authority_proofs,
    )
    assert "invalid_writing_research_callback" not in "|".join(failures)
    assert not any(item.startswith("missing_writing_research_callback") for item in failures)

    invented = [{
        **closed_request[0],
        "concept_key": "CK-INVENTED",
    }]
    failures2: list[str] = []
    _check_writing_callback_contract(
        failures2,
        output=_output(invented),
        graph=graph,
        unit_by_id=unit_by_id,
        authority_proofs=authority_proofs,
    )
    assert any(
        item.startswith("invalid_writing_research_callback") for item in failures2
    )
    assert any(
        item.startswith("missing_writing_research_callback") for item in failures2
    )


def test_writer_inputs_carry_concept_bearing_callback_prototype():
    """Stage 5: an open move prototype names the caveated concept's missing parts."""
    from code2paper.agentic.evidence_compiler_v3 import (
        AtomicClaimV3,
        AtomicClaimSetV3,
    )
    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        MethodArgumentUnitV1,
        MethodCompletenessItemV1,
        MethodCompletenessMatrixV1,
        MethodSectionPlanV2,
        MoveAuthorityProofV1,
        ObligationMoveAssignmentV1,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
    )
    from code2paper.agentic.publication_method_writer import _writer_section_inputs
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        ConceptCardEvidenceVerdictV1,
        ConceptCardFieldJudgmentV1,
        MethodConceptCardSetV1,
    )
    from code2paper.agentic.equation_claims import EquationClaimSetV1

    claim = AtomicClaimV3(
        claim_id="C1",
        canonical_text="The per-primitive descriptor concatenates local z-score, global z-score, and RGB color.",
        fact_ids=["F1"],
        covers_obligation_ids=["O-FEATURE"],
        direct_evidence_ids=["S1"],
        relation_evidence_ids=["RV1"],
        allowed_wording_boundary="only the descriptor composition",
        canonical_identity="sha256:claim",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap", project_tree_hash="tree",
        evidence_packet_digest="sha256:p", code_fact_digest="sha256:f",
        claims=[claim], content_digest="sha256:c",
    )
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        items=[MethodCompletenessItemV1(
            obligation_id="O-FEATURE", role="feature extraction",
            statement="Construct the descriptor.",
            status="partially_supported_by_repository",
        )],
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the descriptor built?",
        design_objective="Explain descriptor construction.",
        claim_ids=("C1",),
        source_obligation_ids=("O-FEATURE",),
        concept_card_ids=("CK-C",),
        caveated_concept_card_ids=("CK-C",),
        concept_card_order=("CK-C",),
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S1", heading="Feature descriptor",
        reader_question="How is the descriptor built?",
        argument_unit_ids=("U1",),
        moves=[SectionArgumentMoveV1(
            move="limitations_or_mismatch",
            argument_unit_ids=("U1",),
            required=True,
        )],
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-1",
        method_name="Method",
        argument_units=[unit],
        sections=[graph],
        move_authority_proofs=[MoveAuthorityProofV1(
            section_id="MA-S1",
            argument_unit_ids=("U1",),
            move="limitations_or_mismatch",
            required=True,
            unresolved_obligation_ids=("O-FEATURE",),
            required_authority_lane="executable_hard",
            state="open",
        )],
        obligation_assignments=[ObligationMoveAssignmentV1(
            obligation_id="O-FEATURE",
            importance="critical",
            status="partially_supported_by_repository",
            authority_lane="executable_hard",
            section_id="MA-S1",
            argument_unit_id="U1",
            required_move="limitations_or_mismatch",
            placement_state="assigned",
        )],
        audience="method readers",
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-C", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="standardization",
            operation="combines statistics into a standardized descriptor",
            may_enter_verified=False,
            requires_caveat=True,
            candidate_caveat="author-intended; repository implementation not verified",
            missing_parts=("exact standardization formula", "normalization bounds"),
            evidence_fragment_refs=("frag-1",),
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-C",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="combines",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the combination",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-C",
            field_bindings=(("operation", ("frag-1",)),),
            source_obligation_ids=("O-FEATURE",),
        )],
    )
    inputs = _writer_section_inputs(
        plan=plan, claims=claims,
        equations=EquationClaimSetV1(
            repo_snapshot_id="snap", project_tree_hash="tree",
            code_fact_digest="sha256:f", equations=[], content_digest="sha256:e",
        ),
        configurations=ConfigurationClaimSetV1(
            repo_snapshot_id="snap", project_tree_hash="tree",
        ),
        propositions=None,
        concept_cards=card_set,
    )
    payload = inputs[0].prompt_payload
    prototypes = payload["response_protocol"]["callback_request_prototypes"]
    assert len(prototypes) == 1
    proto = prototypes[0]
    assert proto["missing_rhetorical_move"] == "limitations_or_mismatch"
    binding = proto["concept_binding"]
    assert binding[0]["concept_key"] == "CK-C"
    assert binding[0]["missing_parts"] == [
        "exact standardization formula", "normalization bounds",
    ]
    assert binding[0]["evidence_refs_used"] == ["frag-1"]
    # The callback shape tells the writer to copy the concept fields.
    shape = payload["response_protocol"]["callback_request_shape"]
    assert shape["concept_key"] == (
        "one concept key from callback_request_prototypes[].concept_binding"
    )
    assert "concept_binding" in payload["content_first_instruction"]


def test_concept_lane_callback_candidates_authorized_by_card_surface():
    """Stage 6 generalization: when a unit's semantic frame is empty (thin
    research), the callback candidates must still be authorized by the bound
    concept card's reader surface — otherwise every request is rejected as
    invalid and the section can never complete."""
    from code2paper.agentic.method_argument_models import (
        MethodArgumentUnitV1,
        MethodSectionPlanV2,
        MoveAuthorityProofV1,
        ObligationMoveAssignmentV1,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
    )
    from code2paper.agentic.publication_method_writer import (
        _check_writing_callback_contract,
    )
    from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1

    # Unit WITHOUT a semantic frame (degraded research), but with a bound
    # caveated concept card whose reader surface authorizes search terms.
    unit = MethodArgumentUnitV1(
        argument_unit_id="U1", section_role="stage",
        research_question="How is the reranker trained?",
        claim_ids=(),
        source_obligation_ids=("O-STAGE-01",),
        concept_card_ids=("CK-C",),
        caveated_concept_card_ids=("CK-C",),
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S1", heading="Training",
        reader_question="How is the reranker trained?",
        argument_unit_ids=("U1",),
        moves=[SectionArgumentMoveV1(
            move="limitations_or_mismatch",
            argument_unit_ids=("U1",),
            required=True,
        )],
    )
    plan = MethodSectionPlanV2(
        plan_id="plan-1",
        method_name="Method",
        argument_units=[unit],
        sections=[graph],
        move_authority_proofs=[MoveAuthorityProofV1(
            section_id="MA-S1",
            argument_unit_ids=("U1",),
            move="limitations_or_mismatch",
            required=True,
            unresolved_obligation_ids=("O-STAGE-01",),
            required_authority_lane="executable_hard",
            state="open",
        )],
        obligation_assignments=[ObligationMoveAssignmentV1(
            obligation_id="O-STAGE-01",
            importance="critical",
            status="partially_supported_by_repository",
            authority_lane="executable_hard",
            section_id="MA-S1",
            argument_unit_id="U1",
            required_move="limitations_or_mismatch",
            placement_state="assigned",
        )],
        audience="method readers",
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap", project_tree_hash="tree",
        cards=[MethodConceptCardV1(
            concept_key="CK-C", cluster_id="CC-1",
            authority_lane="repository",
            method_subject="contrastive reranker training",
            operation="computes reranker loss from query and passage identifiers",
            inputs=("query", "passage"),
            outputs=("training loss",),
            known_parts=("dedicated attention flag",),
            may_enter_verified=False,
            requires_caveat=True,
            candidate_caveat="author-intended; repository implementation not verified",
            missing_parts=("temperature scaling",),
            evidence_verdict="entailed",
        )],
        evidence_verdicts=[ConceptCardEvidenceVerdictV1(
            concept_key="CK-C",
            field_judgments=[ConceptCardFieldJudgmentV1(
                field_name="operation", proposed_value="computes reranker loss",
                verdict="entailed", evidence_fragment_refs=("frag-1",),
                rationale="frag-1 establishes the operation",
            )],
            overall_verdict="entailed", rationale="all entailed",
        )],
        bindings=[ConceptCardBindingV1(
            concept_key="CK-C",
            field_bindings=(("operation", ("frag-1",)),),
            source_obligation_ids=("O-STAGE-01",),
        )],
    )
    unit_by_id = {item.argument_unit_id: item for item in plan.argument_units}
    authority_proofs = plan.proofs_by_key()

    # The request names candidates from the card's own surface (no frame
    # exists), e.g. the model copied "dedicated attention flag" from
    # known_parts or "training loss" from outputs.
    card_surface_request = [{
        "request_id": "request:MA-S1:limitations_or_mismatch",
        "section_id": "MA-S1",
        "argument_unit_id": "U1",
        "missing_rhetorical_move": "limitations_or_mismatch",
        "exact_question": "Which evidence resolves the temperature scaling?",
        "required_authority_lane": "executable_hard",
        "candidate_symbols_or_terms": ["dedicated attention flag", "training loss"],
        "concept_key": "CK-C",
        "missing_parts": ["temperature scaling"],
        "evidence_refs_used": ["frag-1"],
        "status": "open",
    }]
    failures: list[str] = []
    _check_writing_callback_contract(
        failures,
        output=PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            section_markdown="## Training\n\nThe reranker training remains intended.",
            new_research_requests=card_surface_request,
        ),
        graph=graph,
        unit_by_id=unit_by_id,
        authority_proofs=authority_proofs,
        concept_cards=card_set,
    )
    assert not any(item.startswith("invalid_writing_research_callback") for item in failures)
    assert not any(item.startswith("missing_writing_research_callback") for item in failures)

    # Without the concept cards the same request is invalid (frame is empty
    # and the candidates are not authorized) — the concept lane is what
    # authorizes them.
    failures2: list[str] = []
    _check_writing_callback_contract(
        failures2,
        output=PublicationMethodSectionOutputV1(
            section_id="MA-S1",
            section_markdown="## Training\n\nThe reranker training remains intended.",
            new_research_requests=card_surface_request,
        ),
        graph=graph,
        unit_by_id=unit_by_id,
        authority_proofs=authority_proofs,
        concept_cards=None,
    )
    assert any(item.startswith("invalid_writing_research_callback") for item in failures2)


def test_concept_card_set_digest_ignores_live_audit_projection_fields() -> None:
    """Frozen research cards omit writing_role / realizes_story_node.

    Those fields are classified on load for the Writer path and must not
    rewrite the persisted set digest, or frozen authoring replay cannot
    bind the cards.
    """

    card = MethodConceptCardV1(
        concept_key="CK-V",
        cluster_id="CC-1",
        authority_lane="repository",
        method_subject="per-primitive descriptor",
        operation="concatenates local and global statistics",
    )
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        cards=(card,),
    )
    frozen = json.loads(card_set.model_dump_json())
    for item in frozen["cards"]:
        item.pop("writing_role", None)
        item.pop("realizes_story_node", None)
    reloaded = MethodConceptCardSetV1.model_validate(frozen)
    assert reloaded.content_digest == card_set.content_digest
    assert reloaded.cards[0].writing_role is not None
    assert reloaded.cards[0].content_digest == card.content_digest
