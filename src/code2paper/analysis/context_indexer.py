"""Phase 1B context indexing.

This module builds lightweight navigation indexes from raw evidence and comment
triage. It intentionally emits likely candidates only, not method conclusions.
"""

from __future__ import annotations

from code2paper.core.schemas import (
    CommentIndex,
    CommentType,
    ContextMap,
    EvidenceItem,
    NavigationWeight,
    RawContextIndex,
    RawEvidencePack,
    SourceType,
)


METHOD_TAGS = {"model", "attention", "optimization", "preprocess", "data", "train", "method"}
ENTRYPOINT_TAGS = {"entrypoint"}


def build_raw_context_index(raw_pack: RawEvidencePack) -> RawContextIndex:
    return RawContextIndex(
        project_id=raw_pack.project_id,
        entrypoint_candidates=_paths_for_tags(raw_pack.evidence_items, source_type=SourceType.BASH, tags=ENTRYPOINT_TAGS),
        config_candidates=sorted(
            {item.path for item in raw_pack.evidence_items if item.source_type == SourceType.CONFIG}
        ),
        source_span_index=_source_span_index(raw_pack.evidence_items),
        author_hint_spans=[
            item.evidence_id for item in raw_pack.evidence_items if item.source_type == SourceType.AUTHOR
        ],
        excluded_sources=raw_pack.excluded_sources,
        token_budget={
            "total_index_tokens": _rough_token_estimate(raw_pack.evidence_items),
            "recommended_phase2_context_tokens": min(24000, _rough_token_estimate(raw_pack.evidence_items)),
        },
    )


def build_context_map(raw_pack: RawEvidencePack, comment_index: CommentIndex) -> ContextMap:
    method_comments = [
        comment.comment_id
        for comment in comment_index.comments
        if comment.navigation_weight in {NavigationWeight.HIGH, NavigationWeight.MEDIUM}
        and comment.comment_type != CommentType.STALE_OR_UNTRUSTED
    ]
    low_priority_comments = [
        comment.comment_id
        for comment in comment_index.comments
        if comment.navigation_weight == NavigationWeight.LOW
        or comment.comment_type in {CommentType.EXPERIMENT_ENGINEERING, CommentType.STALE_OR_UNTRUSTED}
    ]
    return ContextMap(
        likely_entrypoints=_paths_for_tags(raw_pack.evidence_items, source_type=SourceType.BASH, tags=ENTRYPOINT_TAGS),
        likely_config_candidates=sorted(
            {item.path for item in raw_pack.evidence_items if item.source_type == SourceType.CONFIG}
        ),
        method_relevant_comments=method_comments,
        author_related_symbols=_author_related_symbols(raw_pack.evidence_items),
        method_affecting_config_keys=_method_affecting_config_keys(raw_pack.evidence_items),
        source_trace_seeds=_source_trace_seeds(raw_pack.evidence_items),
        ignore_or_low_priority=low_priority_comments,
    )


def _paths_for_tags(
    items: list[EvidenceItem],
    *,
    source_type: SourceType,
    tags: set[str],
) -> list[str]:
    return sorted(
        {
            item.path
            for item in items
            if item.source_type == source_type and bool(set(item.tags) & tags)
        }
    )


def _source_span_index(items: list[EvidenceItem]) -> list[str]:
    spans = []
    for item in items:
        if item.source_type != SourceType.SOURCE:
            continue
        symbol = f"::{item.symbol}" if item.symbol else ""
        line = f":{item.line_start}-{item.line_end}" if item.line_start and item.line_end else ""
        spans.append(f"{item.evidence_id}:{item.path}{symbol}{line}")
    return spans


def _author_related_symbols(items: list[EvidenceItem]) -> list[str]:
    symbols = {
        f"{item.path}::{item.symbol}"
        for item in items
        if item.source_type == SourceType.SOURCE and item.symbol and set(item.tags) & METHOD_TAGS
    }
    return sorted(symbols)


def _method_affecting_config_keys(items: list[EvidenceItem]) -> list[str]:
    candidates = []
    for item in items:
        if item.source_type != SourceType.CONFIG:
            continue
        if item.config_key:
            candidates.append(item.config_key)
        else:
            candidates.append(item.path)
    return sorted(set(candidates))


def _source_trace_seeds(items: list[EvidenceItem]) -> list[str]:
    seeds = {
        f"{item.path}::{item.symbol}"
        for item in items
        if item.source_type == SourceType.SOURCE
        and item.symbol
        and (set(item.tags) & METHOD_TAGS or any(marker in item.symbol.lower() for marker in METHOD_TAGS))
    }
    return sorted(seeds)


def _rough_token_estimate(items: list[EvidenceItem]) -> int:
    words = sum(len(item.content_summary.split()) + len(item.tags) for item in items)
    return max(1, int(words * 1.4))

