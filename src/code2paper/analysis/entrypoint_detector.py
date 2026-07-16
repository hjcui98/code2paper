"""Entrypoint detection facade."""

from __future__ import annotations

from code2paper.analysis.alignment import _detect_entrypoints
from code2paper.core.schemas import AuthorMarkers, Entrypoint, EvidenceItem


def detect_entrypoints(
    evidence: list[EvidenceItem],
    *,
    author_markers: AuthorMarkers | None = None,
) -> list[Entrypoint]:
    return _detect_entrypoints(evidence, author_markers=author_markers)

