"""Route writing-time information requests to their owning evidence lane."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_argument_models import (
    ConfigurationClaimSetV1,
    WritingResearchCallbackArtifactV1,
    WritingResearchRequestV1,
)
from code2paper.agentic.method_product_models import MethodReviewCandidateV1


RouteOwnerV1 = Literal[
    "repository_tools",
    "configuration_tools",
    "author_confirmation_queue",
    "empirical_artifact_tools",
    "external_literature_tools",
    "formalization_agent",
]

#: Lanes whose requests are *queued* for an external owner (author,
#: literature, empirical).  They can never be fulfilled by the local
#: repository/config/formalization machinery.
_EXTERNAL_QUEUE_LANES: frozenset[str] = frozenset({
    "author_attested",
    "empirical_artifact",
    "external_literature",
    "expository_bridge",
})

_QUEUE_LANE_LABELS: dict[str, str] = {
    "author_attested": "author_confirmation",
    "empirical_artifact": "empirical_evidence",
    "external_literature": "literature",
    "expository_bridge": "author_confirmation",
}


class ExternalResearchQueueItemV1(BaseModel):
    """One explicitly queued external request (F2 contract).

    Author, literature and empirical lanes cannot be executed by the local
    harness; instead of returning a silent ``None`` they emit this artifact
    so the request is visible, editable, and traceable.  ``proposed_body`` is
    a truthful rephrase of the exact question (never invented facts).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    lane: str
    section_id: str
    argument_unit_id: str = ""
    exact_question: str
    proposed_body: str
    needed_evidence: tuple[str, ...] = Field(default_factory=tuple)
    status: Literal["queued", "fulfilled", "cancelled"] = "queued"
    trace_refs: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ExternalResearchQueueItemV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


class WritingResearchRouteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str
    request_id: str
    owner: RouteOwnerV1
    section_id: str
    argument_unit_id: str
    scope: tuple[str, ...] = Field(default_factory=tuple)
    required_authority_lane: str
    rationale: str
    resume_section_only: bool = True
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "WritingResearchRouteV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def route_writing_research_request(request: WritingResearchRequestV1) -> WritingResearchRouteV1:
    """Select an owner without broadening the requested scope."""

    owner_by_lane: dict[str, RouteOwnerV1] = {
        "executable_hard": "repository_tools",
        "configuration_resolved": "configuration_tools",
        "author_attested": "author_confirmation_queue",
        "formal_derivation": "formalization_agent",
        "empirical_artifact": "empirical_artifact_tools",
        "external_literature": "external_literature_tools",
        # An unresolved bridge is not evidence that a repository tool can
        # authorize.  Keep the request in the author-confirmation lane until
        # the Writer can complete it without introducing factual content.
        "expository_bridge": "author_confirmation_queue",
    }
    owner = owner_by_lane[request.required_authority_lane]
    return WritingResearchRouteV1(
        route_id="route:" + hashlib.sha256(request.request_id.encode("utf-8")).hexdigest()[:20],
        request_id=request.request_id,
        owner=owner,
        section_id=request.section_id,
        argument_unit_id=request.argument_unit_id,
        scope=request.candidate_symbols_or_terms,
        required_authority_lane=request.required_authority_lane,
        rationale=(
            f"The requested move requires the {request.required_authority_lane} lane; "
            f"resume section {request.section_id} after the owning artifact is validated."
        ),
    )


def route_writing_research_requests(
    requests: list[WritingResearchRequestV1] | tuple[WritingResearchRequestV1, ...],
) -> tuple[WritingResearchRouteV1, ...]:
    return tuple(route_writing_research_request(request) for request in requests)


def execute_writing_research_route(
    route: WritingResearchRouteV1,
    request: WritingResearchRequestV1,
    *,
    configuration_claims: ConfigurationClaimSetV1 | None = None,
    formalization: Any | None = None,
    repository_provider: Callable[[WritingResearchRequestV1], dict[str, Any] | None] | None = None,
) -> WritingResearchCallbackArtifactV1 | None:
    """Execute an owned route and produce one validated, digest-pinned artifact.

    Repository/configuration/formalization routes may execute existing
    authorized sources: configuration claims are matched from the frozen
    closed set, the formalization lane binds the validated Formalization
    result digest, and the repository lane consumes a supplied provider whose
    output must still pass the artifact validator.  Author, empirical, and
    literature lanes cannot be executed here: they stay in their explicit
    external queues and return ``None``.
    """

    if route.owner == "configuration_tools":
        return _execute_configuration_route(request, configuration_claims)
    if route.owner == "formalization_agent":
        return _execute_formalization_route(request, formalization)
    if route.owner == "repository_tools":
        if repository_provider is None:
            return None
        raw = repository_provider(request)
        if not isinstance(raw, dict):
            return None
        try:
            return WritingResearchCallbackArtifactV1.model_validate({
                **raw,
                "request_id": str(raw.get("request_id") or request.request_id),
                "section_id": str(raw.get("section_id") or request.section_id),
                "argument_unit_id": str(raw.get("argument_unit_id") or request.argument_unit_id),
                "validated": True,
            })
        except (TypeError, ValueError):
            return None
    return None


def execute_open_requests_for_routes(
    requests: list[WritingResearchRequestV1] | tuple[WritingResearchRequestV1, ...],
    *,
    configuration_claims: ConfigurationClaimSetV1 | None = None,
    formalization: Any | None = None,
    repository_provider: Callable[[WritingResearchRequestV1], dict[str, Any] | None] | None = None,
) -> dict[str, tuple[WritingResearchCallbackArtifactV1, ...]]:
    """Route and execute every open request; external lanes stay pending."""
    artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] = {}
    for request in requests:
        if request.status != "open":
            continue
        route = route_writing_research_request(request)
        artifact = execute_writing_research_route(
            route,
            request,
            configuration_claims=configuration_claims,
            formalization=formalization,
            repository_provider=repository_provider,
        )
        if artifact is not None:
            artifacts.setdefault(request.request_id, []).append(artifact)
    return artifacts


def _execute_configuration_route(
    request: WritingResearchRequestV1,
    configuration_claims: ConfigurationClaimSetV1 | None,
) -> WritingResearchCallbackArtifactV1 | None:
    if configuration_claims is None:
        return None
    exact_candidates = {
        str(term).strip().lower() for term in request.candidate_symbols_or_terms
        if str(term).strip()
    }
    for claim in configuration_claims.claims:
        if not claim.active or claim.state not in {"actual", "default", "conditional"}:
            continue
        if (
            claim.configuration_id in exact_candidates
            or claim.key.lower() in exact_candidates
        ):
            return WritingResearchCallbackArtifactV1(
                artifact_id=f"config:{claim.configuration_id}",
                request_id=request.request_id,
                section_id=request.section_id,
                argument_unit_id=request.argument_unit_id,
                authority_lane="configuration_resolved",
                artifact_ref=claim.configuration_id,
                artifact_digest=claim.content_digest,
                validated=True,
            )
    return None


def _execute_formalization_route(
    request: WritingResearchRequestV1,
    formalization: Any | None,
) -> WritingResearchCallbackArtifactV1 | None:
    if formalization is None or not getattr(formalization, "content_digest", ""):
        return None
    return WritingResearchCallbackArtifactV1(
        artifact_id="formalization:result",
        request_id=request.request_id,
        section_id=request.section_id,
        argument_unit_id=request.argument_unit_id,
        authority_lane="formal_derivation",
        artifact_ref="formalization_result_v1",
        artifact_digest=formalization.content_digest,
        validated=True,
    )


def build_external_research_queue_items(
    requests: list[WritingResearchRequestV1] | tuple[WritingResearchRequestV1, ...],
) -> tuple[ExternalResearchQueueItemV1, ...]:
    """Materialize external-lane requests as explicit queue artifacts (F2).

    Author / literature / empirical requests can never be fulfilled by the
    local repository harness.  This is the replacement for the old silent
    ``None``: every open external request becomes a visible, editable queue
    item with an exact question and a truthful proposed body.
    """

    items: list[ExternalResearchQueueItemV1] = []
    for request in requests:
        lane = str(request.required_authority_lane or "")
        if lane not in _EXTERNAL_QUEUE_LANES or request.status != "open":
            continue
        question = str(request.exact_question or "").strip()
        if not question:
            continue
        label = _QUEUE_LANE_LABELS.get(lane, lane)
        items.append(ExternalResearchQueueItemV1(
            request_id=request.request_id,
            lane=lane,
            section_id=request.section_id,
            argument_unit_id=request.argument_unit_id,
            exact_question=question,
            proposed_body=(
                f"The {label} lane is asked to resolve the following Method point, "
                f"which is currently not asserted as a repository-verified fact: "
                + question.rstrip("?.") + "."
            ),
            needed_evidence=request.candidate_symbols_or_terms,
            status="queued",
            trace_refs=(request.request_id,),
        ))
    return tuple(items)


def build_review_candidates_from_requests(
    requests: list[WritingResearchRequestV1] | tuple[WritingResearchRequestV1, ...],
) -> tuple[MethodReviewCandidateV1, ...]:
    """Convert open author-lane requests into author-facing review items.

    The review item carries an editable proposed body and an exact
    confirmation question; it blocks verified inclusion only.  Literature and
    empirical requests stay in the external queue artifact and are not
    surfaced as author-confirmation review items.
    """

    items: list[MethodReviewCandidateV1] = []
    for request in requests:
        lane = str(request.required_authority_lane or "")
        if lane != "author_attested" or request.status != "open":
            continue
        question = str(request.exact_question or "").strip()
        if not question:
            continue
        items.append(MethodReviewCandidateV1(
            candidate_id=f"review-request:{request.request_id}",
            source_obligation_id="",
            section_id=request.section_id,
            argument_unit_id=request.argument_unit_id,
            lane="author_intent_unverified",
            status="unverified",
            proposed_body=(
                "The author-intended Method point behind this request awaits "
                "confirmation and is not a repository-verified fact: "
                + question.rstrip("?.") + "."
            ),
            confirmation_question=question,
            needed_evidence=request.candidate_symbols_or_terms,
            suggested_action="confirm_author_intent_or_provide_evidence",
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(request.request_id,),
        ))
    return tuple(items)


__all__ = [
    "ExternalResearchQueueItemV1",
    "RouteOwnerV1",
    "WritingResearchRouteV1",
    "build_external_research_queue_items",
    "build_review_candidates_from_requests",
    "execute_open_requests_for_routes",
    "execute_writing_research_route",
    "route_writing_research_request",
    "route_writing_research_requests",
]
