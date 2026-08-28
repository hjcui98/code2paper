"""Route writing-time information requests to their owning evidence lane."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable
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

_SEARCH_TERM_RE = re.compile(r"[A-Za-zΔδ][A-Za-z0-9_Δδ-]*")
_SEARCH_TERM_STOP = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "had", "has", "have", "how", "in", "into", "is", "it", "its",
    "may", "not", "note", "of", "on", "or", "our", "out", "plus", "read",
    "than", "that", "the", "their", "them", "then", "these", "this",
    "those", "to", "via", "we", "what", "when", "where", "which", "why",
    "will", "with", "after", "all", "also", "apply", "author", "before",
    "both", "clause", "confirmation", "does", "draft", "each", "empty",
    "evidence", "functions", "implement", "intended", "mechanism",
    "pending", "repository", "setups", "spans", "such", "symbols",
    "through", "unlicensed", "use", "used", "using", "while", "must",
    "should",
})
_GENERIC_CALLBACK_QUESTION_MARKERS = (
    "which repository evidence or author confirmation resolves",
    "which repository evidence resolves the unlicensed",
    "replace this with one precise missing-information question",
    "which repository evidence binds this section formula obligation",
)
_DIRECTED_QUESTION_PREFIX = (
    "Which repository spans, symbols, or functions implement:"
)


def _iter_search_term_texts(texts: Iterable[Any]) -> Iterable[str]:
    for text in texts:
        if isinstance(text, (list, tuple, set)):
            yield from _iter_search_term_texts(text)
        else:
            yield str(text or "")


def _search_term_rank(token: str) -> int:
    """Prefer formula/symbol tokens over heading English in a closed set."""

    if any(character in token for character in "Δδ"):
        return 3
    if any(character.isdigit() for character in token) or "_" in token:
        return 3
    if len(token) >= 2 and token.isupper():
        return 3
    if any(character.isupper() for character in token[1:]):
        return 2
    if len(token) >= 8:
        return 1
    return 0


def directed_search_terms_from_texts(*texts: Any, limit: int = 16) -> tuple[str, ...]:
    """Extract directed repository search terms from closed-set author text.

    Tokens come only from caller-supplied strings (unlicensed clauses,
    missing parts, facet quotes).  The harness does not invent project
    names or known answers.  Distinctive symbol/formula tokens rank above
    generic heading English so a later clause is not truncated away.
    """

    ranked: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    order = 0
    for text in _iter_search_term_texts(texts):
        for match in _SEARCH_TERM_RE.findall(text):
            token = str(match).strip()
            key = token.casefold()
            if key in seen or key in _SEARCH_TERM_STOP:
                continue
            if len(token) < 3 and not (
                any(character in token for character in "Δδ")
                or any(character.isdigit() for character in token)
                or token.isupper()
            ):
                continue
            seen.add(key)
            ranked.append((-_search_term_rank(token), order, token))
            order += 1
    ranked.sort()
    return tuple(token for _, _, token in ranked[: max(0, int(limit))])


def directed_callback_question(terms: Iterable[str]) -> str:
    """Build a scoped search question from already-authorized terms."""

    shown = [str(term).strip() for term in terms if str(term).strip()][:8]
    if not shown:
        return ""
    return (
        "Which repository spans, symbols, or functions implement: "
        + ", ".join(shown)
        + "?"
    )


def _is_generic_callback_question(question: str) -> bool:
    folded = str(question or "").strip().casefold()
    return any(marker in folded for marker in _GENERIC_CALLBACK_QUESTION_MARKERS)


def fill_writing_research_search_terms(
    request: WritingResearchRequestV1,
) -> WritingResearchRequestV1:
    """Fill empty executable search terms from closed-set missing parts.

    WP-C: ``candidate_symbols_or_terms`` must come from ``search_terms`` /
    unlicensed clause text already on the request.  A generic question with
    an empty term list is not a legal repository route.
    """

    existing = tuple(
        str(term).strip()
        for term in request.candidate_symbols_or_terms
        if str(term).strip()
    )
    from_parts = directed_search_terms_from_texts(*request.missing_parts)
    existing_kept = tuple(
        term for term in existing if term.casefold() not in _SEARCH_TERM_STOP
    )
    merged: list[str] = []
    seen: set[str] = set()
    high_rank = [term for term in from_parts if _search_term_rank(term) >= 3]
    for token in (*high_rank, *existing_kept, *from_parts):
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(token)
        if len(merged) >= 16:
            break
    filled = tuple(merged) or existing_kept or existing
    question = str(request.exact_question or "").strip()
    if filled and _is_generic_callback_question(question):
        question = directed_callback_question(filled)
    elif (
        filled
        and filled != existing
        and question.startswith(_DIRECTED_QUESTION_PREFIX)
    ):
        question = directed_callback_question(filled)
    why = str(request.why_needed_for_reader or "").strip()
    if "before its prose can leave the candidate lane" in why.casefold():
        why = (
            "Directed repository search for unlicensed author-mechanism "
            "fields. Keep writing the full author-logic Candidate as author "
            "specification in parallel; do not omit the mechanism while this "
            "callback is open."
        )
    if (
        filled == tuple(request.candidate_symbols_or_terms)
        and question == str(request.exact_question or "")
        and why == str(request.why_needed_for_reader or "")
    ):
        return request
    return request.model_copy(update={
        "candidate_symbols_or_terms": filled,
        "exact_question": question or request.exact_question,
        "why_needed_for_reader": why or request.why_needed_for_reader,
    })


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

    request = fill_writing_research_search_terms(request)
    if (
        request.required_authority_lane == "executable_hard"
        and not any(str(term).strip() for term in request.candidate_symbols_or_terms)
    ):
        raise ValueError(
            "executable_hard callback requires non-empty candidate_symbols_or_terms"
        )
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
    # Route each request independently.  One malformed callback (for example
    # an executable request without search terms) must be rejected without
    # discarding otherwise valid callbacks from the same Writer response.
    routes: list[WritingResearchRouteV1] = []
    for request in requests:
        try:
            routes.append(route_writing_research_request(request))
        except ValueError:
            continue
    return tuple(routes)


def execute_writing_research_route(
    route: WritingResearchRouteV1,
    request: WritingResearchRequestV1,
    *,
    configuration_claims: ConfigurationClaimSetV1 | None = None,
    formalization: Any | None = None,
    formalization_sections: tuple[Any, ...] | list[Any] | None = None,
    equations: Any | None = None,
    facts: Any | None = None,
    repository_provider: Callable[[WritingResearchRequestV1], dict[str, Any] | None] | None = None,
) -> WritingResearchCallbackArtifactV1 | None:
    """Execute an owned route and produce one validated, digest-pinned artifact.

    Repository/configuration/formalization routes may execute existing
    authorized sources: configuration claims are matched from the frozen
    closed set, the formalization lane binds a section-scoped accepted
    formula package (never a global Formalization digest alone), and the
    repository lane consumes a supplied provider whose
    output must still pass the artifact validator.  Author, empirical, and
    literature lanes cannot be executed here: they stay in their explicit
    external queues and return ``None``.
    """

    if route.owner == "configuration_tools":
        return _execute_configuration_route(request, configuration_claims)
    if route.owner == "formalization_agent":
        return _execute_formalization_route(
            request,
            formalization_sections=formalization_sections,
            equations=equations,
            facts=facts,
        )
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
    formalization_sections: tuple[Any, ...] | list[Any] | None = None,
    equations: Any | None = None,
    facts: Any | None = None,
    repository_provider: Callable[[WritingResearchRequestV1], dict[str, Any] | None] | None = None,
) -> dict[str, tuple[WritingResearchCallbackArtifactV1, ...]]:
    """Route and execute every open request; external lanes stay pending."""
    artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] = {}
    for request in requests:
        if request.status not in {"open", "partial"}:
            continue
        request = fill_writing_research_search_terms(request)
        try:
            route = route_writing_research_request(request)
        except ValueError:
            # Invalid repository callbacks are rejected at the harness
            # boundary; they must not become a broad, unscoped search.
            continue
        artifact = execute_writing_research_route(
            route,
            request,
            configuration_claims=configuration_claims,
            formalization=formalization,
            formalization_sections=formalization_sections,
            equations=equations,
            facts=facts,
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
    *,
    formalization_sections: tuple[Any, ...] | list[Any] | None = None,
    equations: Any | None = None,
    facts: Any | None = None,
) -> WritingResearchCallbackArtifactV1 | None:
    if not formalization_sections:
        return None
    from code2paper.agentic.formalization_agent import (
        FormalizationSectionResultV1,
        resolve_formalization_route_artifact,
    )

    section_results: list[FormalizationSectionResultV1] = []
    for item in formalization_sections:
        if isinstance(item, FormalizationSectionResultV1):
            section_results.append(item)
            continue
        try:
            section_results.append(FormalizationSectionResultV1.model_validate(item))
        except (TypeError, ValueError):
            continue
    if not section_results:
        return None
    return resolve_formalization_route_artifact(
        request,
        section_results=tuple(section_results),
        equations=equations,
        facts=facts,
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
        if lane not in _EXTERNAL_QUEUE_LANES or request.status not in {"open", "partial"}:
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
    "directed_callback_question",
    "directed_search_terms_from_texts",
    "execute_open_requests_for_routes",
    "execute_writing_research_route",
    "fill_writing_research_search_terms",
    "route_writing_research_request",
    "route_writing_research_requests",
]
