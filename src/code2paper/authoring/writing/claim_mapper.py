"""Draft claim mapping helpers."""

from __future__ import annotations

from code2paper.core.schemas import DraftClaimMap, MethodOutline


def build_draft_claim_map_from_outline(outline: MethodOutline) -> DraftClaimMap:
    return DraftClaimMap(
        paragraphs=[
            {
                "paragraph_id": paragraph.paragraph_id,
                "claim_ids": paragraph.claim_ids,
                "mechanism_ids": paragraph.mechanism_ids,
                "evidence_span_ids": paragraph.evidence_span_ids,
            }
            for paragraph in outline.sections
        ]
    )
