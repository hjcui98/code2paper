"""Writer research route execution: closed-lane fulfillment and external queues."""

from __future__ import annotations

import json
from pathlib import Path

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


def _request(*, lane: str, candidates: tuple[str, ...] = ()) -> WritingResearchRequestV1:
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


def test_formalization_route_binds_validated_result_digest() -> None:
    request = _request(lane="formal_derivation", candidates=("score",))
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

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

    artifact = execute_writing_research_route(
        route_writing_research_request(request),
        request,
        formalization=formalization,
    )

    assert artifact is not None
    assert artifact.authority_lane == "formal_derivation"
    assert artifact.artifact_digest == formalization.content_digest
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
