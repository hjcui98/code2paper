"""Deterministic owner routing for publication-authoring issues.

Validation identifies a problem; it does not grant every repair owner
permission to edit it.  This module keeps evidence, formula, content,
cross-section, and paper-language failures on their responsible paths so a
Rewrite call cannot silently delete an unresolved mechanism.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.research_models import TextRepairIssueV1


IssueOwnerV1 = Literal[
    "research_continuation",
    "formalizer",
    "writer",
    "editor",
    "rewrite",
    "review",
]


class PublicationIssueOwnerRouteV1(BaseModel):
    """One immutable primary-owner decision for a typed publication issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str = Field(min_length=1)
    section_id: str = ""
    owner: IssueOwnerV1
    failure_type: str = ""
    reason: str = Field(min_length=1)
    attempt: int = Field(default=0, ge=0)
    input_digest: str = ""
    output_digest: str = ""
    stop_reason: str = ""


_RESEARCH_FAILURES = frozenset({
    "evidence_gap",
    "wrong_span_role",
    "direct_evidence_semantically_unrelated",
    "direct_evidence_missing",
    "missing_relation",
    "semantic_verifier_exhausted",
    "unsupported_rationale",
})
_FORMALIZER_FAILURES = frozenset({
    "formula_unsupported",
    "formula_not_rendered",
})
_WRITER_FAILURES = frozenset({
    "authority_framing",
    "missing_core_facet",
    "no_semantically_matching_projected_claim",
    "supported_claim_not_rendered",
    "missing_qualifier",
    "comparison_polarity_flipped",
    "allowed_wording_boundary_exceeded",
})
_EDITOR_FAILURE_PREFIXES = (
    "cross_section_",
    "document_structure_",
)
_EDITOR_FAILURES = frozenset({
    "section_structure",
    "heading_tail_leaked_into_body",
})
_REWRITE_FAILURES = frozenset({
    "code_trace_prose",
    "code_trace_prose_not_method_language",
    "method_language_style",
    "reader_facing_internal_id",
})


def _issue_value(issue: TextRepairIssueV1 | Mapping[str, Any] | str, key: str) -> Any:
    if isinstance(issue, str):
        return issue if key == "failure_type" else ""
    if isinstance(issue, Mapping):
        return issue.get(key, "")
    return getattr(issue, key, "")


def _owner_for_failure(failure_type: str, scope: str) -> tuple[IssueOwnerV1, str]:
    failure = failure_type.strip()
    if failure in _FORMALIZER_FAILURES or failure.startswith("formula_"):
        return "formalizer", "formula authority or rendering is incomplete"
    if failure in _RESEARCH_FAILURES or failure in {"direct_evidence_missing", "missing_relation"}:
        return "research_continuation", "repository evidence or relation support is incomplete"
    if failure in _WRITER_FAILURES:
        return "writer", "the Writer must restore the missing authorized content"
    if failure in _EDITOR_FAILURES or failure.startswith(_EDITOR_FAILURE_PREFIXES):
        return "editor", "the issue crosses section boundaries"
    if failure in _REWRITE_FAILURES:
        return "rewrite", "the issue is a bounded paper-language or local wording repair"
    if scope == "sentence_atomicity" and failure in _REWRITE_FAILURES:
        return "rewrite", "the issue is a bounded paper-language or local wording repair"
    if scope == "formula_rendering":
        return "formalizer", "formula rendering belongs to the Formalizer"
    if scope in {"packet_relation", "code_search"}:
        return "research_continuation", "the issue requires repository-side evidence work"
    if scope in {"claim_decomposition"}:
        return "writer", "content organization belongs to the Writer owner"
    return "review", "no safe automatic owner is defined for this issue"


def route_publication_issue(
    issue: TextRepairIssueV1 | Mapping[str, Any] | str,
    *,
    section_id: str = "",
    attempt: int = 0,
    input_digest: str = "",
    output_digest: str = "",
    stop_reason: str = "",
) -> PublicationIssueOwnerRouteV1:
    """Assign exactly one primary owner to one publication issue."""

    failure_type = str(_issue_value(issue, "failure_type") or "").strip()
    scope = str(_issue_value(issue, "allowed_repair_scope") or "").strip()
    issue_id = str(
        _issue_value(issue, "issue_id")
        or
        _issue_value(issue, "atomic_claim_id")
        or _issue_value(issue, "sentence_id")
        or failure_type
    ).strip()
    if not issue_id:
        issue_id = "publication-issue"
    resolved_section_id = str(
        _issue_value(issue, "section_id") or section_id or ""
    ).strip()
    owner, reason = _owner_for_failure(failure_type, scope)
    return PublicationIssueOwnerRouteV1(
        issue_id=issue_id,
        section_id=resolved_section_id,
        owner=owner,
        failure_type=failure_type,
        reason=reason,
        attempt=max(0, int(attempt)),
        input_digest=str(
            _issue_value(issue, "input_digest") or input_digest or ""
        ),
        output_digest=str(
            _issue_value(issue, "output_digest") or output_digest or ""
        ),
        stop_reason=str(
            _issue_value(issue, "stop_reason") or stop_reason or ""
        ),
    )


def route_publication_issues(
    issues: Iterable[TextRepairIssueV1 | Mapping[str, Any] | str],
    *,
    section_id: str = "",
    attempt: int = 0,
    input_digest: str = "",
    output_digest: str = "",
    stop_reason: str = "",
) -> tuple[PublicationIssueOwnerRouteV1, ...]:
    """Route each issue independently and preserve input order."""

    return tuple(
        route_publication_issue(
            issue,
            section_id=section_id,
            attempt=attempt,
            input_digest=input_digest,
            output_digest=output_digest,
            stop_reason=stop_reason,
        )
        for issue in issues
    )


def rewrite_owned_issues(
    issues: Iterable[TextRepairIssueV1],
    *,
    section_id: str = "",
    attempt: int = 0,
) -> tuple[TextRepairIssueV1, ...]:
    """Return only issues whose deterministic owner is Rewrite."""

    issue_list = tuple(issues)
    selected: list[TextRepairIssueV1] = []
    for issue, route in zip(
        issue_list,
        route_publication_issues(issue_list, section_id=section_id, attempt=attempt),
        strict=True,
    ):
        if route.owner == "rewrite":
            selected.append(issue)
    return tuple(selected)


__all__ = [
    "IssueOwnerV1",
    "PublicationIssueOwnerRouteV1",
    "route_publication_issue",
    "route_publication_issues",
    "rewrite_owned_issues",
]
