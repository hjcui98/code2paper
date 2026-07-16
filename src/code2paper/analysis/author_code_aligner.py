"""Author/code alignment facade."""

from __future__ import annotations

from code2paper.analysis.alignment import _align_author
from code2paper.core.schemas import AuthorAlignment, AuthorMarkers, EvidenceItem, MethodStageAlignment


def align_author_to_code(
    author_markers: AuthorMarkers,
    evidence: list[EvidenceItem],
    method_stages: list[MethodStageAlignment],
) -> AuthorAlignment:
    return _align_author(author_markers, evidence, method_stages)

