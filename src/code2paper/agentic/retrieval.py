from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import shlex
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agents.utils.code_scan import scan_repo
from code2paper.agents.utils.retrieval_strategy import derive_orchestrator_symbol_targets
from code2paper.core.author_questionnaire import load_author_markers
from code2paper.core.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response


class RetrievalTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    target_type: str
    query: str
    paths: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    rationale: str = ""
    priority: str = "medium"


class AgenticRetrievalPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "deterministic"
    author_goal: str = ""
    priority_files: list[str] = Field(default_factory=list)
    ignore_files: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    targets: list[RetrievalTarget] = Field(default_factory=list)
    llm_decision_note: str = ""
    blocked_reason: str = ""


class CoverageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    query: str
    support_status: str
    matched_paths: list[str] = Field(default_factory=list)
    matched_snippet_ids: list[str] = Field(default_factory=list)
    missing_paths: list[str] = Field(default_factory=list)
    rationale: str = ""


class RetrievalCoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "retrieval-coverage"
    overall_score: float = Field(ge=0.0, le=1.0)
    target_coverage_score: float | None = None
    legacy_alignment_score: float | None = None
    score_basis: str = "retrieval_targets"
    covered_targets: int = 0
    partial_targets: int = 0
    missing_targets: int = 0
    items: list[CoverageItem] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class SymbolIndexEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str
    kind: str
    start_line: int = 1
    end_line: int = 1
    parent: str = ""
    docstring: str = ""
    text_hash: str = ""
    matched_target_ids: list[str] = Field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class SymbolIndexReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-symbol-index"
    project_root: str
    indexed_files: int = 0
    indexed_symbols: int = 0
    candidates: list[SymbolIndexEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RetrievalDecisionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str = ""
    kind: str = ""
    start_line: int = 1
    end_line: int = 1
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    matched_target_ids: list[str] = Field(default_factory=list)


class RetrievalDecisionGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    query: str
    support_status: str
    missing_paths: list[str] = Field(default_factory=list)
    matched_paths: list[str] = Field(default_factory=list)
    suggested_candidates: list[RetrievalDecisionCandidate] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)


class RetrievalDecisionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "retrieval-decision-context"
    coverage_score: float = Field(ge=0.0, le=1.0)
    covered_targets: int = 0
    partial_targets: int = 0
    missing_targets: int = 0
    gaps: list[RetrievalDecisionGap] = Field(default_factory=list)
    top_candidates: list[RetrievalDecisionCandidate] = Field(default_factory=list)
    recommended_paths: list[str] = Field(default_factory=list)
    recommended_symbols: list[str] = Field(default_factory=list)
    recommended_queries: list[str] = Field(default_factory=list)
    summary: str = ""


class RetrievalRescanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    source: str
    priority: str = "medium"
    query: str = ""
    path: str = ""
    symbol: str = ""
    target_id: str = ""
    claim_id: str = ""
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class RetrievalRescanPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "retrieval-rescan-plan"
    coverage_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_artifacts: list[str] = Field(default_factory=list)
    items: list[RetrievalRescanItem] = Field(default_factory=list)
    recommended_paths: list[str] = Field(default_factory=list)
    recommended_symbols: list[str] = Field(default_factory=list)
    recommended_queries: list[str] = Field(default_factory=list)
    summary: str = ""


class RetrievalRescanGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = "coverage_critic_decision"
    priority: str = "high"
    recommended_paths: list[str] = Field(default_factory=list)
    recommended_symbols: list[str] = Field(default_factory=list)
    recommended_queries: list[str] = Field(default_factory=list)


class RetrievalRescanOutcomeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    source: str
    status: str
    priority: str = "medium"
    query: str = ""
    path: str = ""
    symbol: str = ""
    target_id: str = ""
    claim_id: str = ""
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    matched_paths: list[str] = Field(default_factory=list)
    matched_snippet_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class RetrievalRescanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "retrieval-rescan-report"
    item_count: int = 0
    covered_items: int = 0
    partial_items: int = 0
    missing_items: int = 0
    high_priority_missing_items: int = 0
    coverage_score: float = Field(default=1.0, ge=0.0, le=1.0)
    items: list[RetrievalRescanOutcomeItem] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    summary: str = ""


def build_agentic_retrieval_plan(
    *,
    author_markers_path: str | Path,
    llm_config: LLMConfig | None = None,
) -> AgenticRetrievalPlan:
    """Create an auditable retrieval plan from author intent.

    The deterministic plan is the source of truth. An LLM may conservatively add
    targets or keywords, but it cannot delete author-provided paths or ignore
    patterns.
    """

    markers = load_author_markers(str(author_markers_path))
    deterministic = _deterministic_plan(markers)
    revised = _llm_revised_plan(deterministic, llm_config)
    if revised is None:
        return deterministic
    return _merge_plans(base=deterministic, revised=revised)


def build_symbol_index(
    *,
    project_root: str | Path,
    plan: AgenticRetrievalPlan,
    max_files: int = 120,
    max_candidates: int = 200,
) -> SymbolIndexReport:
    """Build a deterministic symbol/ranking view for agentic retrieval decisions."""

    root = Path(project_root).expanduser().resolve()
    warnings: list[str] = []
    entries: list[SymbolIndexEntry] = []
    files = _candidate_indexable_files(root=root, plan=plan, max_files=max_files, warnings=warnings)
    for rel_path in files:
        full_path = root / rel_path
        try:
            text = full_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            warnings.append(f"read_failed:{rel_path}:{exc.__class__.__name__}")
            continue
        if len(text.encode("utf-8", errors="ignore")) > 512 * 1024:
            warnings.append(f"oversized_file:{rel_path}")
            continue
        if rel_path.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                warnings.append(f"syntax_error:{rel_path}:{exc.lineno or 0}")
                continue
            entries.extend(_extract_python_symbol_entries(tree=tree, text=text, rel_path=rel_path, plan=plan))
        elif _is_config_path(rel_path):
            entries.extend(_extract_config_entries(text=text, rel_path=rel_path, plan=plan, warnings=warnings))
        elif _is_shell_path(rel_path):
            entries.extend(_extract_shell_entries(text=text, rel_path=rel_path, plan=plan))
    entries.sort(key=lambda entry: (-entry.score, entry.path, entry.start_line, entry.symbol))
    return SymbolIndexReport(
        project_root=str(root),
        indexed_files=len(files),
        indexed_symbols=len(entries),
        candidates=entries[:max_candidates],
        warnings=warnings,
    )


def enrich_plan_with_orchestrator_targets(
    *,
    project_root: str | Path,
    plan: AgenticRetrievalPlan,
) -> AgenticRetrievalPlan:
    root = Path(project_root).expanduser().resolve()
    code_sources = scan_repo(
        str(root),
        filters={
            "excluded_dirs": [".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist", "output", "hf"],
            "priority_files": list(plan.priority_files),
            "excluded_globs": list(plan.ignore_files),
        },
        budgets={"max_total_files": 240, "max_total_bytes": 24 * 1024 * 1024, "max_single_file_bytes": 768 * 1024},
    )
    file_index = code_sources.get("project_files", [])
    if not isinstance(file_index, list):
        return plan
    derived = derive_orchestrator_symbol_targets(file_index, list(plan.priority_files))
    if not derived:
        return plan

    targets = list(plan.targets)
    next_id = len(targets) + 1
    target_paths: list[str] = []
    target_symbols: list[str] = []
    for item in derived:
        path = _repo_rel_path(root, str(item.get("path") or ""))
        symbol = str(item.get("symbol") or "").strip()
        if not path or not symbol or _plan_has_symbol_target(plan, path, symbol):
            continue
        target_paths.append(path)
        target_symbols.append(symbol)
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="orchestrator_symbol",
                query=symbol,
                paths=[path],
                symbols=[symbol],
                rationale=str(item.get("reason") or "Code entrypoint imports and instantiates this symbol."),
                priority="high",
            )
        )
        next_id += 1

    if len(targets) == len(plan.targets):
        return plan
    note = "Code-derived orchestrator symbol targets merged into retrieval plan."
    return plan.model_copy(
        update={
            "priority_files": _dedupe(list(plan.priority_files) + target_paths),
            "search_keywords": _dedupe(list(plan.search_keywords) + target_symbols)[:120],
            "targets": targets[:260],
            "llm_decision_note": (plan.llm_decision_note + " " if plan.llm_decision_note else "") + note,
        }
    )


def build_retrieval_coverage_report(
    *,
    plan: AgenticRetrievalPlan,
    snippets_payload: dict[str, Any],
    alignment_payload: dict[str, Any] | None = None,
) -> RetrievalCoverageReport:
    snippets = [
        snippet
        for snippet in snippets_payload.get("snippets", [])
        if isinstance(snippet, dict)
    ]
    snippet_records = [_snippet_record(snippet) for snippet in snippets]
    items: list[CoverageItem] = []
    for target in plan.targets:
        matched_paths: list[str] = []
        matched_snippet_ids: list[str] = []
        for record in snippet_records:
            if _target_matches_record(target, record):
                if record["path"]:
                    matched_paths.append(record["path"])
                if record["snippet_id"]:
                    matched_snippet_ids.append(record["snippet_id"])
        matched_paths = _dedupe(matched_paths)
        matched_snippet_ids = _dedupe(matched_snippet_ids)
        missing_paths = [
            path for path in target.paths if path and not _path_is_matched(path, matched_paths)
        ]
        if matched_snippet_ids and not missing_paths:
            support_status = "covered"
        elif matched_snippet_ids:
            support_status = "partial"
        else:
            support_status = "missing"
        items.append(
            CoverageItem(
                target_id=target.target_id,
                query=target.query,
                support_status=support_status,
                matched_paths=matched_paths,
                matched_snippet_ids=matched_snippet_ids,
                missing_paths=missing_paths,
                rationale=_coverage_rationale(target, support_status, matched_paths),
            )
        )
    covered = sum(1 for item in items if item.support_status == "covered")
    partial = sum(1 for item in items if item.support_status == "partial")
    missing = sum(1 for item in items if item.support_status == "missing")
    alignment_score = _alignment_score(alignment_payload or {})
    if items:
        target_score = (covered + 0.5 * partial) / len(items)
        target_coverage_score = round(min(1.0, max(0.0, target_score)), 4)
        score = target_coverage_score
        score_basis = "retrieval_targets"
    elif alignment_score is not None:
        target_coverage_score = None
        score = round(min(1.0, max(0.0, alignment_score)), 4)
        score_basis = "legacy_alignment_fallback"
    else:
        target_coverage_score = None
        score = 0.0
        score_basis = "no_retrieval_targets"
    actions = []
    if missing:
        actions.append("rescan_missing_paths_or_symbols")
    if partial:
        actions.append("ask_coverage_critic_for_targeted_queries")
    if not items:
        actions.append("build_retrieval_plan_from_author_intent")
    return RetrievalCoverageReport(
        overall_score=score,
        target_coverage_score=target_coverage_score,
        legacy_alignment_score=alignment_score,
        score_basis=score_basis,
        covered_targets=covered,
        partial_targets=partial,
        missing_targets=missing,
        items=items,
        recommended_actions=actions,
    )


def build_retrieval_decision_context(
    *,
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport | None = None,
    max_candidates_per_gap: int = 5,
    max_top_candidates: int = 20,
) -> RetrievalDecisionContext:
    """Build a compact, model-facing context for coverage critic decisions."""

    candidates = list((symbol_index.candidates if symbol_index else []) or [])
    top_candidates = [_decision_candidate(candidate) for candidate in candidates[:max_top_candidates]]
    weak_items = [item for item in coverage.items if item.support_status in {"missing", "partial"}]
    gaps: list[RetrievalDecisionGap] = []
    recommended_paths: list[str] = []
    recommended_symbols: list[str] = []
    recommended_queries: list[str] = []
    for item in weak_items:
        gap_candidates = [
            candidate
            for candidate in candidates
            if item.target_id in candidate.matched_target_ids
            or any(_path_matches_hint(candidate.path, missing_path) for missing_path in item.missing_paths)
        ][:max_candidates_per_gap]
        suggested_candidates = [_decision_candidate(candidate) for candidate in gap_candidates]
        suggested_queries = _dedupe([item.query, *[candidate.symbol for candidate in gap_candidates if candidate.symbol]])[:8]
        gaps.append(
            RetrievalDecisionGap(
                target_id=item.target_id,
                query=item.query,
                support_status=item.support_status,
                missing_paths=item.missing_paths,
                matched_paths=item.matched_paths,
                suggested_candidates=suggested_candidates,
                suggested_queries=suggested_queries,
            )
        )
        recommended_paths.extend(item.missing_paths)
        recommended_paths.extend(candidate.path for candidate in gap_candidates)
        recommended_symbols.extend(candidate.symbol for candidate in gap_candidates if candidate.symbol)
        recommended_queries.extend(suggested_queries)
    return RetrievalDecisionContext(
        coverage_score=coverage.overall_score,
        covered_targets=coverage.covered_targets,
        partial_targets=coverage.partial_targets,
        missing_targets=coverage.missing_targets,
        gaps=gaps,
        top_candidates=top_candidates,
        recommended_paths=_dedupe(recommended_paths)[:30],
        recommended_symbols=_dedupe(recommended_symbols)[:30],
        recommended_queries=_dedupe(recommended_queries)[:30],
        summary=_retrieval_decision_summary(coverage=coverage, gaps=gaps, candidates=top_candidates),
    )


def build_retrieval_rescan_plan(
    *,
    coverage: RetrievalCoverageReport,
    context: RetrievalDecisionContext,
    repair_tasks_payload: dict[str, Any] | None = None,
    max_items: int = 40,
) -> RetrievalRescanPlan:
    """Build an auditable queue for the next bounded retrieval pass.

    This plan is advisory only: it tells intake what to inspect next, while
    evidence freeze and validators still decide which claims can be written.
    """

    items: list[RetrievalRescanItem] = []
    next_id = 1
    for gap in context.gaps:
        gap_priority = "high" if gap.support_status == "missing" else "medium"
        if gap.suggested_candidates:
            for candidate in gap.suggested_candidates:
                items.append(
                    RetrievalRescanItem(
                        item_id=f"RS{next_id}",
                        source="coverage_gap",
                        priority=gap_priority,
                        query=gap.query,
                        path=candidate.path,
                        symbol=candidate.symbol,
                        target_id=gap.target_id,
                        score=candidate.score,
                        reasons=_dedupe([f"gap_status:{gap.support_status}", *candidate.reasons])[:12],
                    )
                )
                next_id += 1
        else:
            for path in gap.missing_paths or [""]:
                items.append(
                    RetrievalRescanItem(
                        item_id=f"RS{next_id}",
                        source="coverage_gap",
                        priority=gap_priority,
                        query=gap.query,
                        path=path,
                        target_id=gap.target_id,
                        reasons=[f"gap_status:{gap.support_status}", "no_ranked_symbol_candidate"],
                    )
                )
                next_id += 1
        for query in gap.suggested_queries:
            if query and query != gap.query:
                items.append(
                    RetrievalRescanItem(
                        item_id=f"RS{next_id}",
                        source="coverage_gap_query",
                        priority=gap_priority,
                        query=query,
                        target_id=gap.target_id,
                        reasons=[f"gap_status:{gap.support_status}", "suggested_query"],
                    )
                )
                next_id += 1
    repair_tasks = [
        task
        for task in (repair_tasks_payload or {}).get("tasks", [])
        if isinstance(task, dict)
    ]
    for task in repair_tasks:
        claim_id = str(task.get("claim_id") or "").strip()
        claim_query = str(task.get("claim_query") or "").strip()
        for candidate in task.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            if _as_list(candidate.get("evidence_ids")):
                continue
            path = str(candidate.get("path") or "").strip()
            symbol = str(candidate.get("symbol") or "").strip()
            if not path and not symbol and not claim_query:
                continue
            items.append(
                RetrievalRescanItem(
                    item_id=f"RS{next_id}",
                    source="analysis_repair_task",
                    priority="high",
                    query=claim_query,
                    path=path,
                    symbol=symbol,
                    claim_id=claim_id,
                    score=_float_or_zero(candidate.get("score")),
                    reasons=_dedupe(["needs_rescan", *_as_list(candidate.get("reasons"))])[:12],
                )
            )
            next_id += 1
    items = [_ranked_rescan_item(item) for item in _dedupe_rescan_items(items)]
    items.sort(key=_rescan_sort_key)
    items = items[:max_items]
    return RetrievalRescanPlan(
        coverage_score=coverage.overall_score,
        source_artifacts=_dedupe(
            [
                "retrieval_coverage",
                "retrieval_decision_context",
                *(["analysis_repair_tasks"] if repair_tasks else []),
            ]
        ),
        items=items,
        recommended_paths=_dedupe([item.path for item in items if item.path])[:30],
        recommended_symbols=_dedupe([item.symbol for item in items if item.symbol])[:30],
        recommended_queries=_dedupe([item.query for item in items if item.query])[:30],
        summary=_retrieval_rescan_summary(coverage=coverage, items=items),
    )


def augment_retrieval_rescan_plan_with_guidance(
    *,
    plan: RetrievalRescanPlan,
    guidance: RetrievalRescanGuidance,
    max_items: int = 40,
) -> RetrievalRescanPlan:
    guidance_items = _guidance_rescan_items(guidance=guidance, start_index=len(plan.items) + 1)
    if not guidance_items:
        return plan
    existing_keys = {_rescan_content_key(item) for item in plan.items}
    new_items: list[RetrievalRescanItem] = []
    for item in guidance_items:
        key = _rescan_content_key(item)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        new_items.append(item)
    if not new_items:
        return plan
    items = [_ranked_rescan_item(item) for item in _dedupe_rescan_items([*plan.items, *new_items])]
    items.sort(key=_rescan_sort_key)
    items = items[:max_items]
    return plan.model_copy(
        update={
            "source_artifacts": _dedupe([*plan.source_artifacts, guidance.source]),
            "items": items,
            "recommended_paths": _dedupe([item.path for item in items if item.path])[:30],
            "recommended_symbols": _dedupe([item.symbol for item in items if item.symbol])[:30],
            "recommended_queries": _dedupe([item.query for item in items if item.query])[:30],
            "summary": _guided_rescan_summary(plan.summary, guidance.source, len(new_items)),
        }
    )


def build_retrieval_rescan_report(
    *,
    plan: RetrievalRescanPlan,
    snippets_payload: dict[str, Any],
    snippet_to_evidence: dict[str, str] | None = None,
    symbol_index: SymbolIndexReport | None = None,
) -> RetrievalRescanReport:
    """Evaluate whether a bounded rescan plan was covered by current intake output."""

    snippet_records = [
        _snippet_record(snippet)
        for snippet in snippets_payload.get("snippets", [])
        if isinstance(snippet, dict)
    ]
    symbol_records = [_symbol_index_record(entry) for entry in symbol_index.candidates] if symbol_index else []
    evidence_by_snippet = snippet_to_evidence or {}
    outcomes: list[RetrievalRescanOutcomeItem] = []
    for item in plan.items:
        matched = [record for record in [*snippet_records, *symbol_records] if _rescan_item_matches_record(item, record)]
        matched_ids = _dedupe([record["snippet_id"] for record in matched if record["snippet_id"]])
        evidence_ids = _dedupe([evidence_by_snippet[snippet_id] for snippet_id in matched_ids if snippet_id in evidence_by_snippet])
        if evidence_ids:
            status = "covered"
        elif matched:
            status = "partial"
        else:
            status = "missing"
        outcomes.append(
            RetrievalRescanOutcomeItem(
                item_id=item.item_id,
                source=item.source,
                status=status,
                priority=item.priority,
                query=item.query,
                path=item.path,
                symbol=item.symbol,
                target_id=item.target_id,
                claim_id=item.claim_id,
                score=item.score,
                reasons=list(item.reasons),
                matched_paths=_dedupe([record["path"] for record in matched if record["path"]]),
                matched_snippet_ids=matched_ids,
                evidence_ids=evidence_ids,
                rationale=_rescan_outcome_rationale(
                    item,
                    status,
                    matched_ids,
                    evidence_ids,
                    _dedupe([record["path"] for record in matched if record["path"]]),
                ),
            )
        )
    covered = sum(1 for item in outcomes if item.status == "covered")
    partial = sum(1 for item in outcomes if item.status == "partial")
    missing = sum(1 for item in outcomes if item.status == "missing")
    high_priority_missing = sum(1 for item in outcomes if item.status == "missing" and item.priority == "high")
    total = len(outcomes)
    score = 1.0 if total == 0 else round((covered + 0.5 * partial) / total, 4)
    return RetrievalRescanReport(
        item_count=total,
        covered_items=covered,
        partial_items=partial,
        missing_items=missing,
        high_priority_missing_items=high_priority_missing,
        coverage_score=score,
        items=outcomes,
        recommended_actions=_rescan_report_actions(
            total=total,
            partial=partial,
            missing=missing,
            high_priority_missing=high_priority_missing,
        ),
        summary=_retrieval_rescan_report_summary(
            total=total,
            covered=covered,
            partial=partial,
            missing=missing,
            high_priority_missing=high_priority_missing,
            score=score,
        ),
    )


def write_retrieval_plan(path: Path, plan: AgenticRetrievalPlan) -> Path:
    _write_json(path, plan.model_dump(mode="json"))
    return path


def write_coverage_report(path: Path, report: RetrievalCoverageReport) -> Path:
    _write_json(path, report.model_dump(mode="json"))
    return path


def write_symbol_index(path: Path, report: SymbolIndexReport) -> Path:
    _write_json(path, report.model_dump(mode="json"))
    return path


def write_retrieval_decision_context(path: Path, context: RetrievalDecisionContext) -> Path:
    _write_json(path, context.model_dump(mode="json"))
    return path


def write_retrieval_rescan_plan(path: Path, plan: RetrievalRescanPlan) -> Path:
    _write_json(path, plan.model_dump(mode="json"))
    return path


def write_retrieval_rescan_report(path: Path, report: RetrievalRescanReport) -> Path:
    _write_json(path, report.model_dump(mode="json"))
    return path


def load_retrieval_decision_context(path: str | Path) -> RetrievalDecisionContext | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RetrievalDecisionContext.model_validate(payload)
    except Exception:
        return None


def load_retrieval_rescan_plan(path: str | Path) -> RetrievalRescanPlan | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RetrievalRescanPlan.model_validate(payload)
    except Exception:
        return None


def load_retrieval_rescan_report(path: str | Path) -> RetrievalRescanReport | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RetrievalRescanReport.model_validate(payload)
    except Exception:
        return None


def _deterministic_plan(markers: Any) -> AgenticRetrievalPlan:
    priority_files = _dedupe(
        list(getattr(markers, "priority_files", []) or [])
        + [role.path for role in getattr(markers, "module_roles", []) if getattr(role, "path", "")]
        + [
            path
            for step in getattr(markers, "pipeline_steps", [])
            for path in list(getattr(step, "related_files", []) or [])
        ]
        + [
            path
            for claim in getattr(markers, "innovation_claims", [])
            for path in list(getattr(claim, "supporting_files", []) or [])
        ]
        + [
            path
            for intent in getattr(markers, "design_intents", [])
            for path in list(getattr(intent, "supporting_files", []) or [])
        ]
    )
    targets: list[RetrievalTarget] = []
    next_id = 1
    for role in getattr(markers, "module_roles", [])[:80]:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="module_role",
                query=str(role.role or role.symbol or role.path),
                paths=[role.path] if role.path else [],
                symbols=[role.symbol] if role.symbol else [],
                rationale="Verify author-specified module role against code.",
                priority="high" if _enum_text(getattr(role, "importance", "")) == "core" else "medium",
            )
        )
        next_id += 1
    for step in getattr(markers, "pipeline_steps", [])[:80]:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="pipeline_step",
                query=f"{step.name}: {step.purpose}".strip(": "),
                paths=list(step.related_files or []),
                rationale="Verify author-specified method step and related implementation files.",
                priority="high" if _enum_text(getattr(step, "highlight_level", "")) == "main" else "medium",
            )
        )
        next_id += 1
    for claim in getattr(markers, "innovation_claims", [])[:40]:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="innovation_claim",
                query=claim.claim,
                paths=list(claim.supporting_files or []),
                symbols=list(claim.supporting_functions or []),
                rationale="Verify author claim before it can be promoted into prose.",
                priority="high",
            )
        )
        next_id += 1
    for intent in getattr(markers, "design_intents", [])[:40]:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="design_intent",
                query=intent.intent,
                paths=list(intent.supporting_files or []),
                symbols=list(intent.supporting_functions or []),
                rationale="Check whether design intent has implementation support.",
                priority="medium",
            )
        )
        next_id += 1
    if not targets:
        for index, path in enumerate(priority_files[:24], start=1):
            targets.append(
                RetrievalTarget(
                    target_id=f"RT{index}",
                    target_type="priority_file",
                    query=Path(path).stem.replace("_", " "),
                    paths=[path],
                    rationale="Fallback target from priority file.",
                    priority="medium",
                )
            )
    keywords = _keyword_bank(
        [
            getattr(markers, "project_goal", ""),
            getattr(markers, "paper_method_goal", ""),
            getattr(markers, "method_mainline", ""),
            " ".join(getattr(markers, "paper_story_order", []) or []),
            " ".join(target.query for target in targets),
        ]
    )
    return AgenticRetrievalPlan(
        mode="deterministic",
        author_goal=str(getattr(markers, "paper_method_goal", "") or getattr(markers, "project_goal", "")),
        priority_files=priority_files,
        ignore_files=list(getattr(markers, "ignore_files", []) or []),
        search_keywords=keywords,
        targets=targets,
    )


def _llm_revised_plan(plan: AgenticRetrievalPlan, llm_config: LLMConfig | None) -> AgenticRetrievalPlan | None:
    if llm_config is None or llm_config.provider == LLMProvider.NONE:
        return None
    if not has_provider_api_key(llm_config):
        return None
    request = LLMRequest(
        prompt_template_id="agentic_retrieval_planner_v1",
        prompt=_retrieval_planner_prompt(),
        input_payload={"deterministic_plan": plan.model_dump(mode="json")},
        schema_name="agentic_retrieval_plan",
        response_json_schema=json_schema_for(AgenticRetrievalPlan),
    )
    response = LLMClient(llm_config).complete(request)
    if response.blocked_reason:
        return plan.model_copy(update={"blocked_reason": response.blocked_reason})
    parsed, _error = try_parse_structured_response(response.text, AgenticRetrievalPlan)
    return parsed


def _merge_plans(*, base: AgenticRetrievalPlan, revised: AgenticRetrievalPlan) -> AgenticRetrievalPlan:
    targets_by_key: dict[tuple[str, str], RetrievalTarget] = {
        (target.target_type, _norm(target.query)): target for target in base.targets
    }
    for target in revised.targets:
        key = (target.target_type, _norm(target.query))
        if key not in targets_by_key:
            targets_by_key[key] = target
    return base.model_copy(
        update={
            "mode": "llm-assisted",
            "priority_files": _dedupe(base.priority_files + revised.priority_files),
            "ignore_files": _dedupe(base.ignore_files + revised.ignore_files),
            "search_keywords": _dedupe(base.search_keywords + revised.search_keywords)[:120],
            "targets": list(targets_by_key.values())[:220],
            "llm_decision_note": revised.llm_decision_note or "LLM revised retrieval plan conservatively.",
            "blocked_reason": revised.blocked_reason,
        }
    )


def _retrieval_planner_prompt() -> str:
    return (
        "You are planning retrieval for an implementation-grounded code-to-paper agent.\n"
        "You may add missing targets, keywords, paths, or symbols, but do not delete author-provided evidence targets.\n"
        "Do not invent file paths. If uncertain, add keyword targets rather than fake paths.\n"
        "The plan is used before evidence freeze; every later Method claim must still be validated by code evidence.\n"
        "Return only JSON matching the provided schema."
    )


def _snippet_record(snippet: dict[str, Any]) -> dict[str, str]:
    source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
    path = str(source.get("path") or snippet.get("path") or "").replace("\\", "/")
    symbol = str(source.get("symbol") or snippet.get("symbol") or "")
    text = " ".join(
        str(snippet.get(key) or "")
        for key in ("snippet_id", "role", "summary", "reason", "text", "content", "code")
    )
    return {
        "snippet_id": str(snippet.get("snippet_id") or ""),
        "path": path,
        "symbol": symbol,
        "text": text.lower(),
    }


def _symbol_index_record(entry: SymbolIndexEntry) -> dict[str, str]:
    text = " ".join([entry.kind, entry.symbol, entry.docstring, " ".join(entry.reasons)])
    return {
        "snippet_id": "",
        "path": entry.path.replace("\\", "/"),
        "symbol": entry.symbol,
        "text": text.lower(),
    }


def _target_matches_record(target: RetrievalTarget, record: dict[str, str]) -> bool:
    if target.paths:
        if not any(_path_is_matched(path, [record["path"]]) for path in target.paths):
            return False
        if not target.symbols:
            return True
        return any(symbol and symbol.lower() in record["symbol"].lower() + " " + record["text"] for symbol in target.symbols)
    query_terms = [term for term in _keyword_bank([target.query]) if len(term) >= 4][:8]
    return bool(query_terms) and sum(1 for term in query_terms if term in record["text"] or term in record["path"].lower()) >= min(2, len(query_terms))


def _plan_has_symbol_target(plan: AgenticRetrievalPlan, path: str, symbol: str) -> bool:
    return any(
        symbol in target.symbols and any(_path_matches_hint(path, target_path) for target_path in target.paths)
        for target in plan.targets
    )


def _candidate_indexable_files(
    *,
    root: Path,
    plan: AgenticRetrievalPlan,
    max_files: int,
    warnings: list[str],
) -> list[str]:
    candidates: list[str] = []
    for path in list(plan.priority_files) + [target_path for target in plan.targets for target_path in target.paths]:
        rel_path = _repo_rel_path(root, path)
        if rel_path and _is_indexable_path(rel_path) and not _ignored(rel_path, plan.ignore_files):
            candidates.append(rel_path)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _is_indexable_path(path.as_posix()):
            continue
        rel_path = _repo_rel_path(root, path)
        if not rel_path or _ignored(rel_path, plan.ignore_files):
            continue
        if any(part in {".git", "__pycache__", ".venv", "venv", "node_modules", "build", "dist"} for part in Path(rel_path).parts):
            continue
        candidates.append(rel_path)
        if len(_dedupe(candidates)) >= max_files:
            break
    deduped = _dedupe(candidates)[:max_files]
    if not deduped:
        warnings.append("no_indexable_files_indexed")
    return deduped


def _extract_python_symbol_entries(
    *,
    tree: ast.AST,
    text: str,
    rel_path: str,
    plan: AgenticRetrievalPlan,
) -> list[SymbolIndexEntry]:
    lines = text.splitlines()
    entries: list[SymbolIndexEntry] = []

    def visit(body: list[ast.stmt], parents: list[str]) -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = ".".join(parents + [node.name])
                start = int(getattr(node, "lineno", 1) or 1)
                end = int(getattr(node, "end_lineno", start) or start)
                snippet = "\n".join(lines[max(0, start - 1):end])
                entry = SymbolIndexEntry(
                    path=rel_path,
                    symbol=symbol,
                    kind=_ast_symbol_kind(node),
                    start_line=start,
                    end_line=end,
                    parent=".".join(parents),
                    docstring=(ast.get_docstring(node) or "").strip()[:400],
                    text_hash=_sha256_text(snippet),
                )
                entries.append(_score_symbol_entry(entry, snippet, plan))
                visit(list(getattr(node, "body", []) or []), parents + [node.name])
            else:
                visit(list(getattr(node, "body", []) or []), parents)

    visit(list(getattr(tree, "body", []) or []), [])
    return entries


def _extract_config_entries(
    *,
    text: str,
    rel_path: str,
    plan: AgenticRetrievalPlan,
    warnings: list[str],
) -> list[SymbolIndexEntry]:
    payload = _parse_config_payload(text=text, rel_path=rel_path, warnings=warnings)
    key_paths = _flatten_config_keys(payload)
    if not key_paths:
        key_paths = _line_config_keys(text)
    entries: list[SymbolIndexEntry] = []
    lines = text.splitlines()
    for key_path, value_preview in key_paths[:120]:
        line_no = _first_key_line(lines, key_path)
        snippet = _line_window(lines, line_no, radius=2)
        symbol = key_path or Path(rel_path).stem
        entry = SymbolIndexEntry(
            path=rel_path,
            symbol=symbol,
            kind="config_key",
            start_line=line_no,
            end_line=line_no,
            docstring=value_preview[:400],
            text_hash=_sha256_text(snippet or symbol),
        )
        entries.append(_score_symbol_entry(entry, snippet or f"{symbol} {value_preview}", plan))
    return entries


def _extract_shell_entries(
    *,
    text: str,
    rel_path: str,
    plan: AgenticRetrievalPlan,
) -> list[SymbolIndexEntry]:
    lines = text.splitlines()
    entries: list[SymbolIndexEntry] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        function_name = _shell_function_name(stripped)
        if function_name:
            snippet = _line_window(lines, index, radius=4)
            entry = SymbolIndexEntry(
                path=rel_path,
                symbol=function_name,
                kind="shell_function",
                start_line=index,
                end_line=index,
                docstring=stripped[:400],
                text_hash=_sha256_text(snippet),
            )
            entries.append(_score_symbol_entry(entry, snippet, plan))
            continue
        if _looks_like_shell_entrypoint(stripped):
            symbol = _shell_command_symbol(stripped)
            snippet = _line_window(lines, index, radius=2)
            entry = SymbolIndexEntry(
                path=rel_path,
                symbol=symbol,
                kind="shell_entrypoint",
                start_line=index,
                end_line=index,
                docstring=stripped[:400],
                text_hash=_sha256_text(snippet),
            )
            entries.append(_score_symbol_entry(entry, snippet, plan))
    return entries


def _score_symbol_entry(entry: SymbolIndexEntry, snippet: str, plan: AgenticRetrievalPlan) -> SymbolIndexEntry:
    haystack = f"{entry.path} {entry.symbol} {entry.kind} {entry.docstring} {snippet[:4000]}".lower()
    matched_target_ids: list[str] = []
    score = 0.0
    reasons: list[str] = []
    for target in plan.targets:
        target_score = 0.0
        if any(_path_is_matched(path, [entry.path]) for path in target.paths):
            target_score += 2.0
            reasons.append(f"path:{target.target_id}")
        if any(symbol and symbol.lower() in entry.symbol.lower() for symbol in target.symbols):
            target_score += 3.0
            reasons.append(f"symbol:{target.target_id}")
        query_terms = [term for term in _keyword_bank([target.query]) if len(term) >= 4][:10]
        keyword_hits = sum(1 for term in query_terms if term in haystack)
        if keyword_hits:
            target_score += min(2.0, keyword_hits * 0.3)
            reasons.append(f"query:{target.target_id}:{keyword_hits}")
        if target.priority == "high" and target_score:
            target_score += 0.5
        if target_score:
            matched_target_ids.append(target.target_id)
            score += target_score
    if entry.kind == "class":
        score += 0.25
    if entry.symbol.split(".")[-1] in {"forward", "train", "main", "fit", "loss", "evaluate", "predict"}:
        score += 0.5
        reasons.append("method_name_signal")
    if any(_path_is_matched(path, [entry.path]) for path in plan.priority_files):
        score += 0.5
        reasons.append("author_priority_file")
    return entry.model_copy(
        update={
            "matched_target_ids": _dedupe(matched_target_ids),
            "score": round(score, 4),
            "reasons": _dedupe(reasons)[:20],
        }
    )


def _ast_symbol_kind(node: ast.AST) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    return "function"


def _is_indexable_path(path: str) -> bool:
    return path.endswith(".py") or _is_config_path(path) or _is_shell_path(path)


def _is_config_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".yaml", ".yml", ".json", ".toml"))


def _is_shell_path(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith((".sh", ".bash", ".zsh", ".slurm", ".sbatch")) or Path(lowered).name in {
        "makefile",
        "dockerfile",
    }


def _parse_config_payload(*, text: str, rel_path: str, warnings: list[str]) -> Any:
    lowered = rel_path.lower()
    try:
        if lowered.endswith(".json"):
            return json.loads(text)
        if lowered.endswith(".toml"):
            if tomllib is None:
                warnings.append(f"toml_unavailable:{rel_path}")
                return None
            return tomllib.loads(text)
        if lowered.endswith((".yaml", ".yml")):
            try:
                import yaml
            except ImportError:
                warnings.append(f"yaml_unavailable:{rel_path}")
                return None
            return yaml.safe_load(text)
    except Exception as exc:
        warnings.append(f"config_parse_failed:{rel_path}:{exc.__class__.__name__}")
    return None


def _flatten_config_keys(payload: Any, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(payload, dict):
        entries: list[tuple[str, str]] = []
        for key, value in payload.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            child_prefix = f"{prefix}.{key_text}" if prefix else key_text
            entries.append((child_prefix, _value_preview(value)))
            entries.extend(_flatten_config_keys(value, child_prefix))
        return entries
    if isinstance(payload, list):
        entries: list[tuple[str, str]] = []
        for index, value in enumerate(payload[:20]):
            child_prefix = f"{prefix}[{index}]" if prefix else f"[{index}]"
            entries.extend(_flatten_config_keys(value, child_prefix))
        return entries
    return []


def _line_config_keys(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue
        match = re.match(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*(.*)$", stripped)
        if match:
            entries.append((match.group(1), match.group(2)[:120]))
    return entries


def _first_key_line(lines: list[str], key_path: str) -> int:
    candidates = [part.split("[", 1)[0] for part in key_path.split(".") if part]
    for part in reversed(candidates):
        pattern = re.compile(rf"^\s*[\"']?{re.escape(part)}[\"']?\s*[:=]")
        for index, line in enumerate(lines, start=1):
            if pattern.search(line):
                return index
    return 1


def _line_window(lines: list[str], line_no: int, *, radius: int) -> str:
    start = max(0, line_no - 1 - radius)
    end = min(len(lines), line_no + radius)
    return "\n".join(lines[start:end])


def _shell_function_name(line: str) -> str:
    match = re.match(r"(?:function\s+)?([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\(\))?\s*\{", line)
    return match.group(1) if match else ""


def _looks_like_shell_entrypoint(line: str) -> bool:
    lowered = line.lower()
    markers = ("python", "torchrun", "accelerate", "deepspeed", "bash ", "sh ", "sbatch", "srun", "make ")
    return any(marker in lowered for marker in markers)


def _shell_command_symbol(line: str) -> str:
    try:
        parts = shlex.split(line, comments=True)
    except ValueError:
        parts = line.split()
    for part in parts:
        clean = part.strip()
        if not clean or "=" in clean and clean.split("=", 1)[0].isupper():
            continue
        if clean in {"python", "python3", "torchrun", "accelerate", "deepspeed", "bash", "sh", "sbatch", "srun", "make"}:
            return clean
        if clean.endswith((".py", ".sh")):
            return Path(clean).name
    return parts[0] if parts else "shell_entrypoint"


def _value_preview(value: Any) -> str:
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)[:400]
        except TypeError:
            return str(value)[:400]
    return str(value)[:400]


def _path_is_matched(path: str, matched_paths: list[str]) -> bool:
    wanted = str(path or "").replace("\\", "/").strip("/")
    if not wanted:
        return False
    return any(candidate.endswith(wanted) or wanted.endswith(candidate.strip("/")) for candidate in matched_paths)


def _repo_rel_path(root: Path, path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return ""


def _ignored(rel_path: str, patterns: list[str]) -> bool:
    rel = rel_path.replace("\\", "/").strip("/")
    return any(fnmatch.fnmatch(rel, pattern.strip("/")) or rel.endswith(pattern.strip("/")) for pattern in patterns if pattern)


def _coverage_rationale(target: RetrievalTarget, status: str, matched_paths: list[str]) -> str:
    if status == "covered":
        return f"Target is covered by snippets from {', '.join(matched_paths[:4])}."
    if status == "partial":
        return "Target has some snippet support but not all requested paths or symbols were matched."
    return "No matching snippet support was found for this target."


def _decision_candidate(candidate: SymbolIndexEntry) -> RetrievalDecisionCandidate:
    return RetrievalDecisionCandidate(
        path=candidate.path,
        symbol=candidate.symbol,
        kind=candidate.kind,
        start_line=candidate.start_line,
        end_line=candidate.end_line,
        score=candidate.score,
        reasons=candidate.reasons[:8],
        matched_target_ids=candidate.matched_target_ids[:12],
    )


def _path_matches_hint(candidate_path: str, hint_path: str) -> bool:
    candidate = str(candidate_path or "").replace("\\", "/").strip("/")
    hint = str(hint_path or "").replace("\\", "/").strip("/")
    return bool(candidate and hint and (candidate.endswith(hint) or hint.endswith(candidate)))


def _retrieval_decision_summary(
    *,
    coverage: RetrievalCoverageReport,
    gaps: list[RetrievalDecisionGap],
    candidates: list[RetrievalDecisionCandidate],
) -> str:
    parts = [
        f"coverage={coverage.overall_score:.2f}",
        f"covered={coverage.covered_targets}",
        f"partial={coverage.partial_targets}",
        f"missing={coverage.missing_targets}",
    ]
    if gaps:
        parts.append("weak_targets=" + ", ".join(gap.target_id for gap in gaps[:8]))
    if candidates:
        parts.append(
            "top_candidates="
            + ", ".join(
                f"{candidate.path}:{candidate.symbol or candidate.kind}" for candidate in candidates[:5]
            )
        )
    return "; ".join(parts)


def _retrieval_rescan_summary(
    *,
    coverage: RetrievalCoverageReport,
    items: list[RetrievalRescanItem],
) -> str:
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source] = by_source.get(item.source, 0) + 1
    source_text = ", ".join(f"{source}={count}" for source, count in sorted(by_source.items()))
    parts = [
        f"coverage={coverage.overall_score:.2f}",
        f"rescan_items={len(items)}",
    ]
    if source_text:
        parts.append(source_text)
    if items:
        parts.append(
            "top="
            + ", ".join(
                item.path or item.symbol or item.query for item in items[:5]
            )
        )
    return "; ".join(parts)


def _retrieval_rescan_report_summary(
    *,
    total: int,
    covered: int,
    partial: int,
    missing: int,
    high_priority_missing: int,
    score: float,
) -> str:
    return "; ".join(
        [
            f"items={total}",
            f"covered={covered}",
            f"partial={partial}",
            f"missing={missing}",
            f"high_priority_missing={high_priority_missing}",
            f"coverage={score:.2f}",
        ]
    )


def _rescan_report_actions(*, total: int, partial: int, missing: int, high_priority_missing: int) -> list[str]:
    if total == 0:
        return ["no_rescan_items_pending"]
    actions: list[str] = []
    if high_priority_missing:
        actions.append("continue_high_priority_rescan_for_missing_items")
    if missing:
        actions.append("continue_bounded_rescan_for_missing_items")
    if partial:
        actions.append("map_matched_rescan_snippets_to_evidence_ids")
    if not actions:
        actions.append("rescan_items_covered_by_current_intake")
    return actions


def _rescan_item_matches_record(item: RetrievalRescanItem, record: dict[str, str]) -> bool:
    path_match = not item.path or _path_matches_hint(record["path"], item.path)
    if not path_match:
        return False
    if item.symbol:
        haystack = f"{record['symbol']} {record['text']}".lower()
        if item.symbol.lower() not in haystack:
            return False
    query_terms = [term for term in _keyword_bank([item.query]) if len(term) >= 4][:8]
    if not item.path and not item.symbol and query_terms:
        hits = sum(1 for term in query_terms if term in record["text"] or term in record["path"].lower())
        return hits >= min(2, len(query_terms))
    return True


def _rescan_outcome_rationale(
    item: RetrievalRescanItem,
    status: str,
    matched_snippet_ids: list[str],
    evidence_ids: list[str],
    matched_paths: list[str],
) -> str:
    if status == "covered":
        return f"Rescan item {item.item_id} matched snippets and evidence ids: {', '.join(evidence_ids[:6])}."
    if status == "partial":
        if matched_snippet_ids:
            return f"Rescan item {item.item_id} matched snippets without evidence ids: {', '.join(matched_snippet_ids[:6])}."
        if matched_paths:
            return f"Rescan item {item.item_id} matched symbol-index locations without frozen evidence ids: {', '.join(matched_paths[:6])}."
        return f"Rescan item {item.item_id} matched snippets without evidence ids: {', '.join(matched_snippet_ids[:6])}."
    return f"Rescan item {item.item_id} did not match current intake snippets."


def _guidance_rescan_items(*, guidance: RetrievalRescanGuidance, start_index: int) -> list[RetrievalRescanItem]:
    paths = _dedupe(guidance.recommended_paths)
    symbols = _dedupe(guidance.recommended_symbols)
    queries = _dedupe(guidance.recommended_queries)
    item_count = max(len(paths), len(symbols), len(queries))
    items: list[RetrievalRescanItem] = []
    for index in range(item_count):
        path = paths[index] if index < len(paths) else ""
        symbol = symbols[index] if index < len(symbols) else ""
        query = queries[index] if index < len(queries) else queries[0] if queries else ""
        if not path and not symbol and not query:
            continue
        reasons = ["model_recommended_rescan"]
        if path:
            reasons.append("model_recommended_path")
        if symbol:
            reasons.append("model_recommended_symbol")
        if query:
            reasons.append("model_recommended_query")
        items.append(
            RetrievalRescanItem(
                item_id=f"RS{start_index + len(items)}",
                source=guidance.source,
                priority=guidance.priority,
                query=query,
                path=path,
                symbol=symbol,
                reasons=reasons,
            )
        )
    return items


def _rescan_content_key(item: RetrievalRescanItem) -> tuple[str, str, str]:
    return (item.path, item.symbol, item.query)


def _guided_rescan_summary(base_summary: str, source: str, item_count: int) -> str:
    guidance = f"{source}={item_count}"
    if not base_summary:
        return guidance
    if guidance in base_summary:
        return base_summary
    return f"{base_summary}; {guidance}"


def _dedupe_rescan_items(items: list[RetrievalRescanItem]) -> list[RetrievalRescanItem]:
    result: list[RetrievalRescanItem] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for item in items:
        key = (item.source, item.target_id or item.claim_id, item.path, item.symbol, item.query)
        if key in seen:
            continue
        seen.add(key)
        result.append(item.model_copy(update={"item_id": f"RS{len(result) + 1}"}))
    return result


def _ranked_rescan_item(item: RetrievalRescanItem) -> RetrievalRescanItem:
    reasons = list(item.reasons)
    if item.source == "analysis_repair_task":
        reasons.append("rank:claim_evidence_repair")
    elif item.source == "coverage_gap" and "gap_status:missing" in item.reasons:
        reasons.append("rank:missing_coverage_target")
    elif item.source == "coverage_gap_query":
        reasons.append("rank:query_expansion")
    return item.model_copy(update={"reasons": _dedupe(reasons)[:12]})


def _rescan_sort_key(item: RetrievalRescanItem) -> tuple[int, int, float, str, str, str]:
    return (_priority_rank(item.priority), _source_rank(item.source), -item.score, item.path, item.symbol, item.query)


def _source_rank(source: str) -> int:
    return {"analysis_repair_task": 0, "coverage_critic_decision": 1, "coverage_gap": 2, "coverage_gap_query": 3}.get(source, 4)


def _priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(str(priority or "").lower(), 1)


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _alignment_score(payload: dict[str, Any]) -> float | None:
    if not isinstance(payload, dict):
        return None
    for key_path in (
        ("coverage_report", "overall_score"),
        ("method_code_alignment", "coverage_score"),
    ):
        current: Any = payload
        for key in key_path:
            current = current.get(key) if isinstance(current, dict) else None
        if isinstance(current, (int, float)):
            return max(0.0, min(1.0, float(current)))
    return None


def _keyword_bank(texts: list[str]) -> list[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "that",
        "this",
        "method",
        "paper",
        "code",
        "using",
        "used",
        "before",
        "after",
    }
    keywords: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_+\-]{2,}", str(text or "")):
            lowered = token.lower().strip("_-")
            if len(lowered) < 3 or lowered in stopwords or lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(lowered)
    return keywords[:120]


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", str(text or "").lower()).strip()


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
