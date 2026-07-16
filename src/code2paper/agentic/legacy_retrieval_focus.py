from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evidence_repair import focus_to_retrieval_overlay, load_evidence_repair_focus
from code2paper.agentic.retrieval import AgenticRetrievalPlan, RetrievalTarget, load_retrieval_rescan_plan
from code2paper.agentic.retrieval_summary import (
    RetrievalPriorityTarget,
    load_retrieval_evidence_summary,
)


def rescan_focus_from_state(state: AgenticRunState) -> dict[str, Any]:
    focus = coverage_rescan_focus_from_state(state)
    rescan_plan_overlay = retrieval_rescan_plan_overlay_from_state(state)
    if rescan_plan_overlay:
        focus = merge_focus(focus, rescan_plan_overlay)
    priority_overlay = retrieval_summary_priority_overlay_from_state(state)
    if priority_overlay:
        focus = merge_focus(focus, priority_overlay)
    repair_overlay = evidence_repair_overlay_from_state(state)
    if repair_overlay:
        focus = merge_focus(focus, repair_overlay)
    return focus


def coverage_rescan_focus_from_state(state: AgenticRunState) -> dict[str, Any]:
    decision_path = state.artifacts.get("coverage_critic_decision", "")
    if not decision_path:
        return {}
    payload = read_json_if_exists(Path(decision_path))
    if not payload or str(payload.get("decision") or "") != "rescan_intake":
        return {}
    paths = dedupe_strings(as_string_list(payload.get("recommended_paths")))
    symbols = dedupe_strings(as_string_list(payload.get("recommended_symbols")))
    queries = dedupe_strings(as_string_list(payload.get("recommended_queries")))
    symbol_targets = [
        {"path": path, "symbol": symbol, "source": "coverage_critic_rescan"}
        for path in paths
        for symbol in symbols
    ]
    focus = {
        "priority_paths": paths,
        "claim_support_files": paths,
        "symbol_targets": symbol_targets,
        "search_keywords": queries,
        "source_decision": str(decision_path),
    }
    return {key: value for key, value in focus.items() if value}


def evidence_repair_focus_payload(state: AgenticRunState) -> dict[str, Any]:
    focus_path = state.artifacts.get("evidence_repair_focus", "")
    if not focus_path:
        return {}
    focus = load_evidence_repair_focus(focus_path)
    return focus.model_dump(mode="json") if focus else {}


def analysis_repair_tasks_payload(state: AgenticRunState) -> dict[str, Any]:
    tasks_path = state.artifacts.get("analysis_repair_tasks", "")
    if not tasks_path:
        return {}
    return read_json_if_exists(Path(tasks_path))


def evidence_repair_overlay_from_state(state: AgenticRunState) -> dict[str, Any]:
    focus_path = state.artifacts.get("evidence_repair_focus", "")
    if not focus_path:
        return {}
    focus = load_evidence_repair_focus(focus_path)
    return focus_to_retrieval_overlay(focus) if focus else {}


def retrieval_rescan_plan_overlay_from_state(state: AgenticRunState) -> dict[str, Any]:
    plan_path = state.artifacts.get("retrieval_rescan_plan", "")
    if not plan_path:
        return {}
    plan = load_retrieval_rescan_plan(plan_path)
    if not plan or not plan.items:
        return {}
    symbol_targets = [
        {"path": item.path, "symbol": item.symbol, "source": "retrieval_rescan_plan"}
        for item in plan.items
        if item.path and item.symbol
    ]
    overlay = {
        "priority_paths": plan.recommended_paths,
        "claim_support_files": plan.recommended_paths,
        "symbol_targets": symbol_targets,
        "search_keywords": plan.recommended_queries,
        "source_decision": str(plan_path),
    }
    return {key: value for key, value in overlay.items() if value}


def retrieval_summary_priority_overlay_from_state(state: AgenticRunState) -> dict[str, Any]:
    summary_path = state.artifacts.get("retrieval_summary", "")
    if not summary_path:
        return {}
    summary = load_retrieval_evidence_summary(summary_path)
    if not summary or not summary.prioritized_targets:
        return {}

    targets = [target for target in summary.prioritized_targets if should_rescan_priority_target(target)]
    if not targets:
        return {}

    paths = dedupe_strings([target.path for target in targets if target.path])
    queries = dedupe_strings([target.query for target in targets if target.query])
    focus_claim_ids = dedupe_strings([target.claim_id for target in targets if target.claim_id])
    symbol_targets = [
        {
            "path": target.path,
            "symbol": target.symbol,
            "source": "retrieval_priority_summary",
            "target_id": target.target_id,
            "claim_id": target.claim_id,
            "status": target.status,
            "priority": target.priority,
            "score": target.score,
        }
        for target in targets
        if target.path and target.symbol
    ]
    claim_targets = priority_targets_to_claim_targets(targets)
    overlay = {
        "priority_paths": paths,
        "claim_support_files": paths,
        "symbol_targets": symbol_targets,
        "search_keywords": queries,
        "focus_claim_ids": focus_claim_ids,
        "claim_targets": claim_targets,
        "source_decision": str(summary_path),
    }
    return {key: value for key, value in overlay.items() if value}


def merge_focus(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in ("priority_paths", "claim_support_files", "search_keywords", "focus_claim_ids"):
        merged[key] = dedupe_strings(as_string_list(merged.get(key)) + as_string_list(right.get(key)))
    merged["symbol_targets"] = [
        item
        for item in [*(merged.get("symbol_targets") or []), *(right.get("symbol_targets") or [])]
        if isinstance(item, dict)
    ]
    merged["claim_targets"] = [
        item
        for item in [*(merged.get("claim_targets") or []), *(right.get("claim_targets") or [])]
        if isinstance(item, dict)
    ]
    if right.get("source_decision"):
        merged["source_decision"] = str(right["source_decision"])
    return {key: value for key, value in merged.items() if value}


def apply_rescan_focus(plan: AgenticRetrievalPlan, focus: dict[str, Any]) -> AgenticRetrievalPlan:
    paths = dedupe_strings(as_string_list(focus.get("priority_paths")))
    queries = dedupe_strings(as_string_list(focus.get("search_keywords")))
    symbol_targets = [
        item
        for item in focus.get("symbol_targets", [])
        if isinstance(item, dict) and str(item.get("path") or "").strip() and str(item.get("symbol") or "").strip()
    ]
    next_id = len(plan.targets) + 1
    targets: list[RetrievalTarget] = list(plan.targets)
    for path in paths:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="agentic_rescan",
                query=Path(path).stem.replace("_", " "),
                paths=[path],
                symbols=[
                    str(item.get("symbol"))
                    for item in symbol_targets
                    if str(item.get("path") or "").strip() == path and str(item.get("symbol") or "").strip()
                ],
                rationale="Targeted rescan requested by agentic coverage, retrieval summary, or evidence repair focus.",
                priority="high",
            )
        )
        next_id += 1
    for query in queries:
        targets.append(
            RetrievalTarget(
                target_id=f"RT{next_id}",
                target_type="agentic_rescan_query",
                query=query,
                paths=[],
                rationale="Targeted keyword query requested by agentic coverage, retrieval summary, or evidence repair focus.",
                priority="high",
            )
        )
        next_id += 1
    return plan.model_copy(
        update={
            "priority_files": dedupe_strings(list(plan.priority_files) + paths),
            "search_keywords": dedupe_strings(list(plan.search_keywords) + queries)[:120],
            "targets": targets[:260],
            "llm_decision_note": (plan.llm_decision_note + " " if plan.llm_decision_note else "")
            + "Coverage critic rescan focus, retrieval summary focus, or evidence repair focus merged into retrieval plan.",
        }
    )


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def should_rescan_priority_target(target: RetrievalPriorityTarget) -> bool:
    return target.status in {"missing", "partial"} or not target.evidence_ids


def priority_targets_to_claim_targets(targets: list[RetrievalPriorityTarget]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for target in targets:
        if not target.claim_id:
            continue
        claim = grouped.setdefault(
            target.claim_id,
            {
                "claim_id": target.claim_id,
                "claim_query": target.query,
                "source": "retrieval_priority_summary",
                "candidates": [],
            },
        )
        if target.query and not claim.get("claim_query"):
            claim["claim_query"] = target.query
        if target.path or target.symbol:
            claim["candidates"].append(
                {
                    "path": target.path,
                    "symbol": target.symbol,
                    "score": target.score,
                    "evidence_ids": list(target.evidence_ids),
                    "status": target.status,
                    "priority": target.priority,
                }
            )
    return list(grouped.values())


def as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
