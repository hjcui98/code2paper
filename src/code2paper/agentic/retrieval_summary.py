from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.retrieval import (
    RetrievalCoverageReport,
    RetrievalDecisionContext,
    RetrievalRescanOutcomeItem,
    RetrievalRescanReport,
    SymbolIndexReport,
)


class RankedRetrievalSymbol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str = ""
    kind: str = ""
    score: float = 0.0
    matched_target_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RetrievalGapSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = ""
    query: str = ""
    support_status: str = ""
    missing_paths: list[str] = Field(default_factory=list)
    suggested_paths: list[str] = Field(default_factory=list)
    suggested_symbols: list[str] = Field(default_factory=list)


class RetrievalPriorityTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = ""
    claim_id: str = ""
    query: str = ""
    path: str = ""
    symbol: str = ""
    status: str = ""
    priority: str = "medium"
    score: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RetrievalEvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-retrieval-evidence-summary"
    coverage_score: float = 0.0
    covered_targets: int = 0
    partial_targets: int = 0
    missing_targets: int = 0
    indexed_symbols: int = 0
    top_symbols: list[RankedRetrievalSymbol] = Field(default_factory=list)
    gaps: list[RetrievalGapSummary] = Field(default_factory=list)
    prioritized_targets: list[RetrievalPriorityTarget] = Field(default_factory=list)
    rescan_missing_items: int = 0
    rescan_covered_items: int = 0
    evidence_ids_found: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str = ""


def build_retrieval_evidence_summary(
    *,
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport,
    context: RetrievalDecisionContext,
    rescan_report: RetrievalRescanReport,
    max_symbols: int = 12,
    max_gaps: int = 12,
    max_priority_targets: int = 16,
) -> RetrievalEvidenceSummary:
    top_symbols = [
        RankedRetrievalSymbol(
            path=candidate.path,
            symbol=candidate.symbol,
            kind=candidate.kind,
            score=candidate.score,
            matched_target_ids=list(candidate.matched_target_ids),
            reasons=list(candidate.reasons),
        )
        for candidate in symbol_index.candidates[:max_symbols]
    ]
    gaps = [
        RetrievalGapSummary(
            target_id=gap.target_id,
            query=gap.query,
            support_status=gap.support_status,
            missing_paths=list(gap.missing_paths),
            suggested_paths=_dedupe([candidate.path for candidate in gap.suggested_candidates]),
            suggested_symbols=_dedupe([candidate.symbol for candidate in gap.suggested_candidates if candidate.symbol]),
        )
        for gap in context.gaps[:max_gaps]
    ]
    evidence_ids = _dedupe([evidence_id for item in rescan_report.items for evidence_id in item.evidence_ids])
    priority_targets = _prioritized_targets(
        context=context,
        rescan_report=rescan_report,
        max_items=max_priority_targets,
    )
    return RetrievalEvidenceSummary(
        coverage_score=coverage.overall_score,
        covered_targets=coverage.covered_targets,
        partial_targets=coverage.partial_targets,
        missing_targets=coverage.missing_targets,
        indexed_symbols=symbol_index.indexed_symbols,
        top_symbols=top_symbols,
        gaps=gaps,
        prioritized_targets=priority_targets,
        rescan_missing_items=rescan_report.missing_items,
        rescan_covered_items=rescan_report.covered_items,
        evidence_ids_found=evidence_ids,
        recommended_actions=_summary_actions(coverage=coverage, rescan_report=rescan_report, evidence_ids=evidence_ids),
        summary=_summary_line(coverage=coverage, symbol_index=symbol_index, rescan_report=rescan_report),
    )


def _prioritized_targets(
    *,
    context: RetrievalDecisionContext,
    rescan_report: RetrievalRescanReport,
    max_items: int,
) -> list[RetrievalPriorityTarget]:
    targets = [_target_from_rescan_item(item) for item in rescan_report.items]
    known_keys = {_target_key(target) for target in targets}
    for gap in context.gaps:
        for candidate in gap.suggested_candidates:
            target = RetrievalPriorityTarget(
                target_id=gap.target_id,
                query=gap.query,
                path=candidate.path,
                symbol=candidate.symbol,
                status=gap.support_status,
                priority="high" if gap.support_status == "missing" else "medium",
                score=candidate.score,
                reasons=_dedupe([f"gap_status:{gap.support_status}", *candidate.reasons])[:12],
            )
            key = _target_key(target)
            if key in known_keys:
                continue
            targets.append(target)
            known_keys.add(key)
    targets.sort(key=_priority_sort_key)
    return targets[:max_items]


def _target_from_rescan_item(item: RetrievalRescanOutcomeItem) -> RetrievalPriorityTarget:
    return RetrievalPriorityTarget(
        target_id=item.target_id,
        claim_id=item.claim_id,
        query=item.query,
        path=item.path,
        symbol=item.symbol,
        status=item.status,
        priority=item.priority,
        score=item.score,
        evidence_ids=list(item.evidence_ids),
        reasons=_dedupe([f"rescan_status:{item.status}", *item.reasons])[:12],
    )


def _priority_sort_key(target: RetrievalPriorityTarget) -> tuple[int, int, float, str, str]:
    return (
        _priority_rank(target.priority),
        _status_rank(target.status),
        -target.score,
        target.path,
        target.symbol,
    )


def _priority_rank(priority: str) -> int:
    ranks = {"high": 0, "medium": 1, "low": 2}
    return ranks.get(priority, 3)


def _status_rank(status: str) -> int:
    ranks = {"missing": 0, "partial": 1, "covered": 2}
    return ranks.get(status, 3)


def _target_key(target: RetrievalPriorityTarget) -> tuple[str, str, str, str]:
    return (target.target_id, target.claim_id, target.path, target.symbol)


def write_retrieval_evidence_summary(path: str | Path, summary: RetrievalEvidenceSummary) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_retrieval_evidence_summary(path: str | Path) -> RetrievalEvidenceSummary | None:
    if not str(path).strip():
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return RetrievalEvidenceSummary.model_validate(payload)


def _summary_actions(
    *,
    coverage: RetrievalCoverageReport,
    rescan_report: RetrievalRescanReport,
    evidence_ids: list[str],
) -> list[str]:
    actions: list[str] = []
    if coverage.missing_targets:
        actions.append("route_coverage_gaps_to_targeted_rescan")
    if rescan_report.missing_items:
        actions.append("prioritize_missing_rescan_items_before_evidence_freeze")
    if not evidence_ids:
        actions.append("map_retrieved_snippets_to_evidence_ids_before_authoring")
    if not actions:
        actions.append("retrieval_summary_ready_for_evidence_freeze")
    return actions


def _summary_line(
    *,
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport,
    rescan_report: RetrievalRescanReport,
) -> str:
    return (
        f"coverage={coverage.overall_score:.2f}; "
        f"covered={coverage.covered_targets}; partial={coverage.partial_targets}; missing={coverage.missing_targets}; "
        f"ranked_symbols={len(symbol_index.candidates)}; "
        f"rescan_covered={rescan_report.covered_items}; rescan_missing={rescan_report.missing_items}"
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
