from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.retrieval import (
    AgenticRetrievalPlan,
    RetrievalCoverageReport,
    RetrievalRescanPlan,
    RetrievalRescanReport,
    SymbolIndexReport,
)
from code2paper.agentic.retrieval_summary import RetrievalEvidenceSummary


class RetrievalStrategyManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-retrieval-strategy-manifest"
    plan_mode: str = ""
    coverage_score_basis: str = ""
    symbol_ranking_signals: list[str] = Field(default_factory=list)
    rescan_queue_sources: list[str] = Field(default_factory=list)
    summary_uses: list[str] = Field(default_factory=list)
    evidence_guardrails: list[str] = Field(default_factory=list)
    target_count: int = 0
    indexed_symbols: int = 0
    rescan_item_count: int = 0
    rescan_coverage_score: float = 0.0
    recommended_actions: list[str] = Field(default_factory=list)


def build_retrieval_strategy_manifest(
    *,
    plan: AgenticRetrievalPlan,
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport,
    rescan_plan: RetrievalRescanPlan,
    rescan_report: RetrievalRescanReport,
    summary: RetrievalEvidenceSummary,
) -> RetrievalStrategyManifest:
    return RetrievalStrategyManifest(
        plan_mode=plan.mode,
        coverage_score_basis=coverage.score_basis,
        symbol_ranking_signals=_symbol_ranking_signals(plan),
        rescan_queue_sources=_rescan_queue_sources(rescan_plan),
        summary_uses=[
            "code_evidence_alignment",
            "coverage_gap_attention",
            "next_intake_focus",
        ],
        evidence_guardrails=[
            "retrieval_can_prioritize_candidates_but_cannot_write_claims",
            "evidence_freeze_decides_claim_support",
            "validators_check_authored_text_against_frozen_evidence",
        ],
        target_count=len(plan.targets),
        indexed_symbols=symbol_index.indexed_symbols,
        rescan_item_count=len(rescan_plan.items),
        rescan_coverage_score=rescan_report.coverage_score,
        recommended_actions=_dedupe(
            [
                *coverage.recommended_actions,
                *rescan_report.recommended_actions,
                *summary.recommended_actions,
            ]
        ),
    )


def write_retrieval_strategy_manifest(path: str | Path, manifest: RetrievalStrategyManifest) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_retrieval_strategy_manifest(path: str | Path) -> RetrievalStrategyManifest:
    return RetrievalStrategyManifest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _symbol_ranking_signals(plan: AgenticRetrievalPlan) -> list[str]:
    signals = ["author_intent_targets", "symbol_path_match", "symbol_name_match", "keyword_hits"]
    if plan.priority_files:
        signals.append("author_intent_priority_files")
    if any(target.priority == "high" for target in plan.targets):
        signals.append("high_priority_targets")
    if any(target.target_type == "orchestrator_symbol" for target in plan.targets):
        signals.append("orchestrator_symbol_targets")
    return signals


def _rescan_queue_sources(plan: RetrievalRescanPlan) -> list[str]:
    return _dedupe([item.source for item in plan.items])


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        ordered.append(value)
        seen.add(value)
    return ordered
