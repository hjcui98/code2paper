"""Comment evidence helpers."""

from __future__ import annotations

from code2paper.core.schemas import EvidenceItem, SourceType


def filter_comment_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    return [item for item in items if item.source_type == SourceType.COMMENT]

