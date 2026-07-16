from __future__ import annotations

from typing import Any


def analysis_repair_attention(
    repair_tasks_payload: dict[str, Any],
    *,
    retrieval_round: int,
    max_retrieval_rounds: int,
) -> dict[str, Any]:
    tasks = [task for task in repair_tasks_payload.get("tasks", []) if isinstance(task, dict)]
    unbound_tasks = [task for task in tasks if _needs_rescan(task)]
    existing_evidence_tasks = [task for task in tasks if task not in unbound_tasks]
    return {
        "task_count": len(tasks),
        "unbound_task_count": len(unbound_tasks),
        "tasks_with_existing_evidence": len(existing_evidence_tasks),
        "retrieval_budget_remaining": max(0, max_retrieval_rounds - retrieval_round),
        "unbound_tasks": [_task_attention(task) for task in unbound_tasks[:12]],
        "existing_evidence_tasks": [_task_attention(task) for task in existing_evidence_tasks[:12]],
    }


def _needs_rescan(task: dict[str, Any]) -> bool:
    candidates = [candidate for candidate in task.get("candidates", []) if isinstance(candidate, dict)]
    if not candidates:
        return True
    return not any(candidate.get("evidence_ids") for candidate in candidates)


def _task_attention(task: dict[str, Any]) -> dict[str, Any]:
    candidates = [candidate for candidate in task.get("candidates", []) if isinstance(candidate, dict)]
    return {
        "claim_id": str(task.get("claim_id") or ""),
        "recommended_next": str(task.get("recommended_next") or ""),
        "candidate_paths": _dedupe([str(candidate.get("path") or "") for candidate in candidates if candidate.get("path")]),
        "candidate_symbols": _dedupe([str(candidate.get("symbol") or "") for candidate in candidates if candidate.get("symbol")]),
        "candidate_evidence_ids": _dedupe(
            [
                str(evidence_id)
                for candidate in candidates
                for evidence_id in (candidate.get("evidence_ids") or [])
                if str(evidence_id).strip()
            ]
        ),
    }


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
