"""Writer research route execution: closed-lane fulfillment and external queues."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.formalization_agent import formalize_code_facts
from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    ConfigurationClaimV1,
    WritingResearchCallbackArtifactV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.writer_research_router import (
    execute_open_requests_for_routes,
    execute_writing_research_route,
    route_writing_research_request,
)


def _request(
    *,
    lane: str,
    candidates: tuple[str, ...] = ("configured_symbol",),
) -> WritingResearchRequestV1:
    return WritingResearchRequestV1(
        request_id=f"request:{lane}",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="configuration_and_branches",
        exact_question="Which configuration value applies here?",
        required_authority_lane=lane,
        candidate_symbols_or_terms=candidates,
        why_needed_for_reader="The reader needs the exact branch value.",
        priority="high",
    )


def _configuration_claims() -> ConfigurationClaimSetV1:
    claim = ConfigurationClaimV1(
        configuration_id="config:knn",
        key="knn_method",
        value="ivf",
        state="default",
        source_fact_ids=["fact:config"],
        canonical_identity="sha256:config:knn",
    )
    return ConfigurationClaimSetV1(
        repo_snapshot_id="repo:router",
        project_tree_hash="sha256:tree",
        claims=(claim,),
        content_digest="sha256:configs",
    )


def test_configuration_route_executes_from_frozen_claims() -> None:
    request = _request(lane="configuration_resolved", candidates=("knn_method",))
    route = route_writing_research_request(request)
    assert route.owner == "configuration_tools"

    artifact = execute_writing_research_route(
        route, request, configuration_claims=_configuration_claims()
    )

    assert artifact is not None
    assert artifact.artifact_id == "config:config:knn"
    assert artifact.artifact_digest.startswith("sha256:")
    assert artifact.validated is True
    assert artifact.artifact_ref == "config:knn"


def test_configuration_route_without_match_stays_pending() -> None:
    request = _request(lane="configuration_resolved", candidates=("unrelated_term",))
    route = route_writing_research_request(request)

    artifact = execute_writing_research_route(
        route, request, configuration_claims=_configuration_claims()
    )

    assert artifact is None


def test_repository_route_requires_validated_provider_output() -> None:
    request = _request(lane="executable_hard")

    without_provider = execute_writing_research_route(
        route_writing_research_request(request), request
    )
    assert without_provider is None

    def provider(_request):
        return {
            "artifact_id": "artifact:span",
            "authority_lane": "executable_hard",
            "artifact_ref": "span:model.py:2:2",
            "artifact_digest": "sha256:return-span",
        }

    with_provider = execute_writing_research_route(
        route_writing_research_request(request), request, repository_provider=provider
    )
    assert with_provider is not None
    assert with_provider.validated is True
    assert with_provider.request_id == "request:executable_hard"

    def broken_provider(_request):
        return {"artifact_id": "", "authority_lane": "executable_hard", "artifact_ref": "", "artifact_digest": "sha256:x"}

    assert execute_writing_research_route(
        route_writing_research_request(request), request, repository_provider=broken_provider
    ) is None


def test_repository_route_rejects_empty_search_terms() -> None:
    request = _request(lane="executable_hard", candidates=())
    with pytest.raises(ValueError, match="non-empty candidate_symbols_or_terms"):
        route_writing_research_request(request)


def test_repository_route_fills_terms_from_missing_parts() -> None:
    from code2paper.agentic.writer_research_router import (
        fill_writing_research_search_terms,
    )

    request = WritingResearchRequestV1(
        request_id="request:executable_hard",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="mechanism_overview",
        exact_question=(
            "Which repository evidence or author confirmation resolves the "
            "unlicensed clause(s) or empty mechanism draft listed in brief_binding?"
        ),
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=(),
        missing_parts=(
            "Directly couple the SSM step size Δt to the irregular timespans.",
            "empty mechanism draft",
        ),
        why_needed_for_reader=(
            "A required move needs unlicensed author intent resolved before "
            "its prose can leave the candidate lane."
        ),
        priority="high",
    )
    filled = fill_writing_research_search_terms(request)
    assert "Δt" in filled.candidate_symbols_or_terms or "SSM" in filled.candidate_symbols_or_terms
    assert "timespans" in filled.candidate_symbols_or_terms or "timespan" in {
        term.casefold() for term in filled.candidate_symbols_or_terms
    }
    assert "which repository evidence or author confirmation" not in (
        filled.exact_question.casefold()
    )
    assert "before its prose can leave the candidate lane" not in (
        filled.why_needed_for_reader.casefold()
    )
    route = route_writing_research_request(request)
    assert route.owner == "repository_tools"
    assert route.scope


def test_directed_search_terms_prefer_formula_tokens_over_heading_english() -> None:
    from code2paper.agentic.writer_research_router import (
        directed_search_terms_from_texts,
        fill_writing_research_search_terms,
    )

    missing_parts = (
        "Dynamic graph encoding: how interaction sequences are represented "
        "with heterogeneous features and aligned.",
        "empty mechanism draft",
        "Pass the aligned encoding through a continuous SSM.",
        "Redefine the SSM step size Δt as a learnable, monotonically "
        "increasing function of the time gap.",
    )
    terms = directed_search_terms_from_texts(*missing_parts)
    folded = {term.casefold() for term in terms}
    assert "Δt" in terms or "ΔT" in terms
    assert "SSM" in terms
    assert "how" not in folded
    assert terms.index("SSM") < terms.index("Dynamic") if "Dynamic" in terms else True
    request = WritingResearchRequestV1(
        request_id="request:ranked-terms",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="mechanism_overview",
        exact_question=(
            "Which repository spans, symbols, or functions implement: "
            "Dynamic, graph, encoding, how?"
        ),
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=(
            "Dynamic", "graph", "encoding", "how", "interaction",
        ),
        missing_parts=missing_parts,
        priority="high",
    )
    filled = fill_writing_research_search_terms(request)
    assert "Δt" in filled.candidate_symbols_or_terms
    assert "SSM" in filled.candidate_symbols_or_terms
    assert "how" not in {
        term.casefold() for term in filled.candidate_symbols_or_terms
    }
    assert filled.candidate_symbols_or_terms.index("SSM") < 8
    assert "Δt" in filled.exact_question or "SSM" in filled.exact_question


def test_open_requests_execute_after_filling_empty_executable_terms() -> None:
    request = WritingResearchRequestV1(
        request_id="request:dt",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="mechanism_overview",
        exact_question="Which repository evidence resolves the unlicensed clause?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=(),
        missing_parts=("Redefine the SSM step size Δt as a learnable function.",),
        priority="high",
    )
    seen: list[tuple[str, ...]] = []

    def provider(item):
        seen.append(tuple(item.candidate_symbols_or_terms))
        return {
            "artifact_id": "span:models/time.py:1:2",
            "authority_lane": "executable_hard",
            "artifact_ref": "span:models/time.py:1:2",
            "artifact_digest": "sha256:" + "a" * 64,
        }

    artifacts = execute_open_requests_for_routes(
        (request,),
        repository_provider=provider,
    )
    assert list(artifacts) == ["request:dt"]
    assert seen and any("Δt" in term or "SSM" in term for term in seen[0])


def test_author_empirical_literature_lanes_stay_in_external_queue() -> None:
    for lane in ("author_attested", "empirical_artifact", "external_literature"):
        request = _request(lane=lane)
        artifact = execute_writing_research_route(
            route_writing_research_request(request), request
        )
        assert artifact is None, lane


def test_open_request_executor_fulfills_only_owned_routes() -> None:
    executable = _request(lane="executable_hard", candidates=())
    configuration = _request(lane="configuration_resolved", candidates=("knn_method",))
    author = _request(lane="author_attested", candidates=())

    artifacts = execute_open_requests_for_routes(
        (executable, configuration, author),
        configuration_claims=_configuration_claims(),
    )

    assert list(artifacts) == ["request:configuration_resolved"]
    assert artifacts["request:configuration_resolved"][0].artifact_digest.startswith("sha256:")


def test_formalization_route_binds_section_package_not_global_digest() -> None:
    request = _request(lane="formal_derivation", candidates=("equation:score",))
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.formalization_agent import (
        FormalizationSectionResultV1,
        SectionFormulaPackageV1,
        formalize_code_facts,
    )

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:router",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:score",
            subject="compute_knn_score",
            predicate="computes_formula",
            object="feature_scores",
            scope="sym:compute_knn_score",
            direct_span_ids=["span:model.py:1:2"],
            semantic_context=["SCORE"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:score",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )
    formalization = formalize_code_facts(facts=facts)
    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Score.",
        latex="s = w @ x + b",
        prose_explanation="The score combines weights and features.",
        symbol_definitions=(("s", "score"), ("w", "weights"), ("x", "features")),
        authority_status="author_intent",
        review_question="Which equation licenses the score?",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
    )
    section_result = FormalizationSectionResultV1(
        section_id="MA-S1",
        packages=(package,),
    )

    assert execute_writing_research_route(
        route_writing_research_request(request),
        request,
        formalization=formalization,
    ) is None

    artifact = execute_writing_research_route(
        route_writing_research_request(request),
        request,
        formalization_sections=(section_result,),
    )

    assert artifact is not None
    assert artifact.authority_lane == "formal_derivation"
    assert artifact.artifact_ref == "fp:MA-S1:1"
    assert artifact.artifact_digest == package.content_digest
    assert artifact.artifact_digest != formalization.content_digest
    assert artifact.validated is True


def test_external_queue_builder_materializes_author_literature_empirical() -> None:
    """F2: external-lane requests are never silently dropped — they become
    explicit queue artifacts with an exact question and a truthful proposed
    body; local lanes stay out of the queue."""
    from code2paper.agentic.writer_research_router import build_external_research_queue_items

    requests = [
        _request(lane="author_attested"),
        _request(lane="empirical_artifact"),
        _request(lane="external_literature"),
        _request(lane="executable_hard"),
        _request(lane="configuration_resolved"),
    ]
    items = build_external_research_queue_items(requests)

    assert len(items) == 3
    assert {item.lane for item in items} == {
        "author_attested", "empirical_artifact", "external_literature",
    }
    for item in items:
        assert item.status == "queued"
        assert item.exact_question
        assert item.proposed_body
        assert item.request_id.startswith("request:")
        assert item.content_digest.startswith("sha256:")


def test_author_request_becomes_review_candidate_with_proposed_body() -> None:
    """F2 author lane: the request is converted into a MethodReviewCandidateV1
    carrying an editable proposed body and an exact question; it blocks
    verified inclusion only."""
    from code2paper.agentic.writer_research_router import (
        build_review_candidates_from_requests,
    )

    author = _request(lane="author_attested")
    literature = _request(lane="external_literature")
    local = _request(lane="executable_hard")

    items = build_review_candidates_from_requests((author, literature, local))

    assert len(items) == 1
    item = items[0]
    assert item.candidate_id == "review-request:request:author_attested"
    assert item.proposed_body
    assert item.confirmation_question
    assert item.lane == "author_intent_unverified"
    assert item.blocks_verified is True
    assert item.blocks_candidate is False
