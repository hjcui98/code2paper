"""Author/code alignment facade."""

from __future__ import annotations

from .alignment import _align_author
from .schemas import AuthorAlignment, AuthorMarkers, EvidenceItem, MethodStageAlignment


def align_author_to_code(
    author_markers: AuthorMarkers,
    evidence: list[EvidenceItem],
    method_stages: list[MethodStageAlignment],
) -> AuthorAlignment:
    return _align_author(author_markers, evidence, method_stages)

