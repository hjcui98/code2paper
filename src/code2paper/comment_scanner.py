"""Phase 1A comment indexing.

The scanner converts raw comment evidence into a separate comment index for
Phase 2 navigation. It does not promote comments to factual support.
"""

from __future__ import annotations

from code2paper.schemas import (
    CommentIndex,
    CommentIndexItem,
    CommentType,
    EvidenceItem,
    FreshnessSignal,
    FreshnessStatus,
    NavigationWeight,
    RawEvidencePack,
    SourceType,
)


METHOD_TAGS = {"@method", "@paper", "@idea", "@ablation", "method", "paper"}
STALE_MARKERS = {"todo", "fixme", "deprecated", "obsolete", "remove", "hack", "temporary"}
FLOW_MARKERS = {"pipeline", "stage", "step", "flow", "before", "after", "then", "first", "second"}
METHOD_MARKERS = {"method", "algorithm", "model", "attention", "loss", "objective", "architecture"}
ENGINEERING_MARKERS = {"debug", "logging", "checkpoint", "seed", "device", "cuda", "gpu", "path"}


def build_comment_index(raw_pack: RawEvidencePack) -> CommentIndex:
    comments = [
        _comment_item(index=index, item=item)
        for index, item in enumerate(raw_pack.evidence_items, start=1)
        if item.source_type == SourceType.COMMENT
    ]
    return CommentIndex(comments=comments)


def _comment_item(*, index: int, item: EvidenceItem) -> CommentIndexItem:
    comment_type = _classify_comment(item)
    freshness = _freshness_signal(item)
    trust_score = _trust_score(item=item, comment_type=comment_type, freshness=freshness)
    return CommentIndexItem(
        comment_id=f"CMT-{index:04d}",
        evidence_id=item.evidence_id,
        path=item.path,
        symbol=item.symbol or "",
        line_start=item.line_start,
        line_end=item.line_end,
        comment_type=comment_type,
        tags=item.tags,
        summary=item.content_summary,
        navigation_weight=_navigation_weight(comment_type=comment_type, trust_score=trust_score, freshness=freshness),
        trust_score=trust_score,
        freshness_or_staleness_signal=freshness,
        allowed_as_fact_evidence=False,
    )


def _classify_comment(item: EvidenceItem) -> CommentType:
    text = _lower_text(item)
    tags = {tag.lower() for tag in item.tags}
    if tags & {"todo", "fixme"} or any(marker in text for marker in STALE_MARKERS):
        return CommentType.STALE_OR_UNTRUSTED
    if "@method" in text or "@paper" in text or any(marker in text for marker in METHOD_MARKERS):
        return CommentType.METHOD_EXPLANATION
    if any(marker in text for marker in FLOW_MARKERS):
        return CommentType.FLOW_HINT
    if item.path.endswith(".sh") or any(marker in text for marker in ENGINEERING_MARKERS):
        return CommentType.EXPERIMENT_ENGINEERING
    return CommentType.IMPLEMENTATION_NOTE


def _freshness_signal(item: EvidenceItem) -> FreshnessSignal:
    text = _lower_text(item)
    reasons: list[str] = []
    if any(marker in text for marker in {"deprecated", "obsolete", "remove"}):
        reasons.append("contains stale marker")
        return FreshnessSignal(status=FreshnessStatus.STALE, reasons=reasons)
    if any(marker in text for marker in {"todo", "fixme", "hack", "temporary"}):
        reasons.append("contains unresolved work marker")
        return FreshnessSignal(status=FreshnessStatus.POSSIBLY_STALE, reasons=reasons)
    if any(tag.lower() in METHOD_TAGS for tag in item.tags) or "@method" in text or "@paper" in text:
        reasons.append("contains paper/method tag")
        return FreshnessSignal(status=FreshnessStatus.FRESH, reasons=reasons)
    return FreshnessSignal(status=FreshnessStatus.UNKNOWN, reasons=reasons)


def _trust_score(*, item: EvidenceItem, comment_type: CommentType, freshness: FreshnessSignal) -> float:
    score = 0.45
    if comment_type in {CommentType.METHOD_EXPLANATION, CommentType.FLOW_HINT}:
        score += 0.25
    elif comment_type == CommentType.IMPLEMENTATION_NOTE:
        score += 0.1
    elif comment_type == CommentType.EXPERIMENT_ENGINEERING:
        score -= 0.1
    elif comment_type == CommentType.STALE_OR_UNTRUSTED:
        score -= 0.25
    if "docstring" in item.tags:
        score += 0.05
    if any(tag.lower() in METHOD_TAGS for tag in item.tags):
        score += 0.1
    if freshness.status == FreshnessStatus.FRESH:
        score += 0.1
    elif freshness.status == FreshnessStatus.POSSIBLY_STALE:
        score -= 0.15
    elif freshness.status == FreshnessStatus.STALE:
        score -= 0.3
    return max(0.0, min(1.0, round(score, 3)))


def _navigation_weight(
    *,
    comment_type: CommentType,
    trust_score: float,
    freshness: FreshnessSignal,
) -> NavigationWeight:
    if comment_type == CommentType.STALE_OR_UNTRUSTED or freshness.status == FreshnessStatus.STALE:
        return NavigationWeight.LOW
    if comment_type in {CommentType.METHOD_EXPLANATION, CommentType.FLOW_HINT} and trust_score >= 0.65:
        return NavigationWeight.HIGH
    if comment_type == CommentType.IMPLEMENTATION_NOTE and trust_score >= 0.5:
        return NavigationWeight.MEDIUM
    return NavigationWeight.LOW


def _lower_text(item: EvidenceItem) -> str:
    return f"{item.content_summary} {' '.join(item.tags)} {item.path} {item.symbol or ''}".lower()

