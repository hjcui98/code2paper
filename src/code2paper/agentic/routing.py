from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.retrieval import RetrievalCoverageReport, SymbolIndexReport


class CoverageCriticDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    rationale: str
    coverage_score: float = Field(ge=0.0, le=1.0)
    missing_targets: int = 0
    partial_targets: int = 0
    recommended_next: str = ""
    recommended_paths: list[str] = Field(default_factory=list)
    recommended_symbols: list[str] = Field(default_factory=list)
    recommended_queries: list[str] = Field(default_factory=list)
    artifact_keys: list[str] = Field(default_factory=list)


class RevisionRouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    rationale: str
    blocked_reason: str = ""
    recommended_next: str = ""
    selected_stage: str = ""
    artifact_keys: list[str] = Field(default_factory=list)


class AnalysisRepairRouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    rationale: str
    recommended_next: str = ""
    task_count: int = 0
    unbound_task_count: int = 0
    retrieval_round: int = 0
    max_retrieval_rounds: int = 0
    artifact_keys: list[str] = Field(default_factory=list)


def critique_coverage(
    coverage: RetrievalCoverageReport,
    *,
    symbol_index: SymbolIndexReport | None = None,
    retrieval_round: int = 0,
    max_retrieval_rounds: int = 0,
    min_score: float = 0.55,
) -> CoverageCriticDecision:
    """Decide whether retrieval coverage is strong enough to analyze."""

    recommendations = _targeted_retrieval_recommendations(coverage, symbol_index)
    if not coverage.items:
        return CoverageCriticDecision(
            decision="rescan_or_block",
            recommended_next="intake" if retrieval_round < max_retrieval_rounds else "analysis",
            rationale="No retrieval targets were covered; build or refresh the retrieval plan before evidence freeze.",
            coverage_score=coverage.overall_score,
            missing_targets=coverage.missing_targets,
            partial_targets=coverage.partial_targets,
            recommended_paths=recommendations["paths"],
            recommended_symbols=recommendations["symbols"],
            recommended_queries=recommendations["queries"],
            artifact_keys=_coverage_artifact_keys(symbol_index),
        )
    if coverage.missing_targets > 0 and retrieval_round < max_retrieval_rounds:
        return CoverageCriticDecision(
            decision="rescan_intake",
            recommended_next="intake",
            rationale=(
                f"{coverage.missing_targets} retrieval targets are missing and rescan budget remains. "
                + _recommendation_rationale(recommendations)
            ).strip(),
            coverage_score=coverage.overall_score,
            missing_targets=coverage.missing_targets,
            partial_targets=coverage.partial_targets,
            recommended_paths=recommendations["paths"],
            recommended_symbols=recommendations["symbols"],
            recommended_queries=recommendations["queries"],
            artifact_keys=_coverage_artifact_keys(symbol_index),
        )
    if coverage.overall_score < min_score or coverage.missing_targets > 0:
        return CoverageCriticDecision(
            decision="proceed_with_caveats",
            recommended_next="analysis",
            rationale=(
                "Coverage is incomplete; proceed only because rescan budget is exhausted or disabled. "
                "Downstream evidence freeze and validators must keep unsupported claims out of prose."
            ),
            coverage_score=coverage.overall_score,
            missing_targets=coverage.missing_targets,
            partial_targets=coverage.partial_targets,
            recommended_paths=recommendations["paths"],
            recommended_symbols=recommendations["symbols"],
            recommended_queries=recommendations["queries"],
            artifact_keys=_coverage_artifact_keys(symbol_index),
        )
    return CoverageCriticDecision(
        decision="proceed_to_analysis",
        recommended_next="analysis",
        rationale="Retrieval coverage is sufficient for code analysis.",
        coverage_score=coverage.overall_score,
        missing_targets=coverage.missing_targets,
        partial_targets=coverage.partial_targets,
        recommended_paths=recommendations["paths"],
        recommended_symbols=recommendations["symbols"],
        recommended_queries=recommendations["queries"],
        artifact_keys=_coverage_artifact_keys(symbol_index),
    )


def route_analysis_repair(
    repair_tasks_payload: dict[str, Any],
    *,
    retrieval_round: int = 0,
    max_retrieval_rounds: int = 0,
) -> AnalysisRepairRouterDecision:
    """Route after analysis using deterministic evidence repair task status."""

    tasks = [item for item in repair_tasks_payload.get("tasks", []) if isinstance(item, dict)]
    unbound_tasks = [task for task in tasks if _repair_task_needs_rescan(task)]
    artifact_keys = ["analysis_repair_tasks"] if tasks else []
    if unbound_tasks and retrieval_round < max_retrieval_rounds:
        return AnalysisRepairRouterDecision(
            decision="rescan_candidate_code",
            recommended_next="intake",
            rationale=(
                f"{len(unbound_tasks)} analysis repair tasks have no existing evidence-bound candidates; "
                "return to intake for a bounded candidate rescan."
            ),
            task_count=len(tasks),
            unbound_task_count=len(unbound_tasks),
            retrieval_round=retrieval_round,
            max_retrieval_rounds=max_retrieval_rounds,
            artifact_keys=[*artifact_keys, "evidence_repair_focus"],
        )
    if unbound_tasks:
        return AnalysisRepairRouterDecision(
            decision="proceed_to_evidence_with_unbound_repair_tasks",
            recommended_next="evidence",
            rationale=(
                f"{len(unbound_tasks)} repair tasks still need rescan, but retrieval budget is exhausted; "
                "continue to evidence freeze so sufficiency and validators can block or caveat unsupported claims."
            ),
            task_count=len(tasks),
            unbound_task_count=len(unbound_tasks),
            retrieval_round=retrieval_round,
            max_retrieval_rounds=max_retrieval_rounds,
            artifact_keys=artifact_keys,
        )
    if tasks:
        return AnalysisRepairRouterDecision(
            decision="reassess_existing_repair_task_evidence",
            recommended_next="evidence",
            rationale="Analysis repair tasks have existing evidence-bound candidates; continue to evidence freeze for reassessment.",
            task_count=len(tasks),
            unbound_task_count=0,
            retrieval_round=retrieval_round,
            max_retrieval_rounds=max_retrieval_rounds,
            artifact_keys=artifact_keys,
        )
    return AnalysisRepairRouterDecision(
        decision="no_analysis_repair_tasks",
        recommended_next="evidence",
        rationale="No analysis repair tasks are present; continue to evidence freeze.",
        retrieval_round=retrieval_round,
        max_retrieval_rounds=max_retrieval_rounds,
    )


def route_revision(state: AgenticRunState) -> RevisionRouterDecision:
    """Route validation or authoring blocks without bypassing evidence gates."""

    reason = str(state.blocked_reason or "").strip()
    if not reason:
        if "validation_manifest" not in state.artifacts:
            return RevisionRouterDecision(
                decision="run_validation",
                recommended_next="validation",
                selected_stage="validation",
                rationale="Validation has not produced a manifest yet.",
                artifact_keys=["validation_manifest"],
            )
        return RevisionRouterDecision(
            decision="rendering",
            recommended_next="rendering",
            selected_stage="rendering",
            rationale="No blocked reason is present; continue toward rendering.",
            artifact_keys=["validation_manifest"],
        )
    lowered = reason.lower()
    if any(token in lowered for token in ("evidence", "coverage", "missing", "unsupported")):
        return RevisionRouterDecision(
            decision="return_to_analysis",
            recommended_next="analysis",
            selected_stage="analysis",
            blocked_reason=reason,
            rationale="The block points to weak or missing evidence; return to analysis/retrieval before rewriting.",
            artifact_keys=["retrieval_coverage", "validation_manifest"],
        )
    if any(token in lowered for token in ("fidelity", "claim", "latex", "number", "term", "equation")):
        if int(state.loop_counters.get("revision") or 0) >= state.max_authoring_revision_rounds:
            return RevisionRouterDecision(
                decision="blocked",
                recommended_next="blocked",
                selected_stage="blocked",
                blocked_reason=reason,
                rationale="Authoring revision budget is exhausted; keep the validation failure visible instead of looping.",
                artifact_keys=["validation_manifest", "fidelity"],
            )
        return RevisionRouterDecision(
            decision="revise_authoring",
            recommended_next="authoring",
            selected_stage="authoring",
            blocked_reason=reason,
            rationale="Validator failure is tied to draft content; revise authoring while preserving frozen evidence.",
            artifact_keys=["validation_manifest", "fidelity"],
        )
    if "llm_api_key_missing" in lowered or "llm_required" in lowered:
        return RevisionRouterDecision(
            decision="blocked",
            recommended_next="blocked",
            blocked_reason=reason,
            rationale="Authoring requires a model provider in this configuration.",
            artifact_keys=["authoring_manifest"],
        )
    return RevisionRouterDecision(
        decision="blocked",
        recommended_next="blocked",
        blocked_reason=reason,
        rationale="No safe automatic revision route matched this blocked reason.",
    )


def decision_to_agent_decision(
    node: str,
    decision: CoverageCriticDecision | AnalysisRepairRouterDecision | RevisionRouterDecision,
) -> AgentDecision:
    rationale = decision.rationale
    if isinstance(decision, CoverageCriticDecision):
        extra = _recommendation_rationale(
            {
                "paths": decision.recommended_paths,
                "symbols": decision.recommended_symbols,
                "queries": decision.recommended_queries,
            }
        )
        if extra and extra not in rationale:
            rationale = f"{rationale} {extra}".strip()
    return AgentDecision(
        node=node,
        decision=decision.decision,
        rationale=rationale,
        artifact_keys=list(decision.artifact_keys),
    )


def load_coverage_report(path: str | Path) -> RetrievalCoverageReport | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RetrievalCoverageReport.model_validate(payload)
    except Exception:
        return None


def load_symbol_index(path: str | Path) -> SymbolIndexReport | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return SymbolIndexReport.model_validate(payload)
    except Exception:
        return None


def write_router_decision(
    path: Path,
    decision: CoverageCriticDecision | AnalysisRepairRouterDecision | RevisionRouterDecision,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _targeted_retrieval_recommendations(
    coverage: RetrievalCoverageReport,
    symbol_index: SymbolIndexReport | None,
) -> dict[str, list[str]]:
    weak_target_ids = {
        item.target_id
        for item in coverage.items
        if item.support_status in {"missing", "partial"}
    }
    paths: list[str] = []
    symbols: list[str] = []
    queries: list[str] = []
    for item in coverage.items:
        if item.target_id not in weak_target_ids:
            continue
        paths.extend(item.missing_paths)
        queries.append(item.query)
    if symbol_index is not None:
        for candidate in symbol_index.candidates:
            if not weak_target_ids.intersection(candidate.matched_target_ids):
                continue
            if candidate.path:
                paths.append(candidate.path)
            if candidate.symbol:
                symbols.append(candidate.symbol)
    return {
        "paths": _dedupe(paths)[:20],
        "symbols": _dedupe(symbols)[:20],
        "queries": _dedupe(queries)[:20],
    }


def _recommendation_rationale(recommendations: dict[str, list[str]]) -> str:
    parts: list[str] = []
    paths = recommendations.get("paths", [])
    symbols = recommendations.get("symbols", [])
    queries = recommendations.get("queries", [])
    if paths:
        parts.append("target_paths=" + ", ".join(paths[:5]))
    if symbols:
        parts.append("target_symbols=" + ", ".join(symbols[:5]))
    if queries:
        parts.append("target_queries=" + ", ".join(queries[:3]))
    return "Targeted rescan hints: " + "; ".join(parts) + "." if parts else ""


def _coverage_artifact_keys(symbol_index: SymbolIndexReport | None) -> list[str]:
    keys = ["retrieval_coverage"]
    if symbol_index is not None:
        keys.append("symbol_index")
    return keys


def _repair_task_needs_rescan(task: dict[str, Any]) -> bool:
    recommended_next = str(task.get("recommended_next") or "").strip()
    if recommended_next == "rescan_candidate_code":
        return True
    candidates = task.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return True
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        evidence_ids = candidate.get("evidence_ids")
        if isinstance(evidence_ids, list) and any(str(evidence_id).strip() for evidence_id in evidence_ids):
            return False
    return True


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
