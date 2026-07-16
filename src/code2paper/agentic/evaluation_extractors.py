from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class ClaimSupportCounts:
    total: int = 0
    supported: int = 0
    partial: int = 0
    unsupported: int = 0
    ambiguous: int = 0


@dataclass(frozen=True, slots=True)
class RepairTaskMetrics:
    task_count: int = 0
    tasks_with_existing_evidence: int = 0
    candidates_with_existing_evidence: int = 0


def claim_support_counts(payload: JsonObject) -> ClaimSupportCounts:
    claims = payload.get("claims", [])
    if not isinstance(claims, list):
        claims = []
    total = 0
    supported = 0
    partial = 0
    unsupported = 0
    ambiguous = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        total += 1
        status = str(claim.get("support_status") or "").strip().lower()
        if status == "supported":
            supported += 1
        elif status == "partial":
            partial += 1
        elif status == "unsupported":
            unsupported += 1
        elif status == "ambiguous":
            ambiguous += 1
        elif status:
            ambiguous += 1
    return ClaimSupportCounts(
        total=total,
        supported=supported,
        partial=partial,
        unsupported=unsupported,
        ambiguous=ambiguous,
    )


def repair_candidate_count(payload: JsonObject) -> int:
    claim_targets = payload.get("claim_targets")
    if not isinstance(claim_targets, list):
        return 0
    count = 0
    for target in claim_targets:
        if not isinstance(target, dict):
            continue
        candidates = target.get("candidates")
        if isinstance(candidates, list):
            count += sum(1 for candidate in candidates if isinstance(candidate, dict))
    return count


def repair_task_metrics(payload: JsonObject) -> RepairTaskMetrics:
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return RepairTaskMetrics()
    task_count = 0
    tasks_with_existing_evidence = 0
    candidates_with_existing_evidence = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_count += 1
        candidates = task.get("candidates")
        task_has_evidence = False
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                evidence_ids = candidate.get("evidence_ids")
                if isinstance(evidence_ids, list) and any(str(item).strip() for item in evidence_ids):
                    task_has_evidence = True
                    candidates_with_existing_evidence += 1
        if task_has_evidence:
            tasks_with_existing_evidence += 1
    return RepairTaskMetrics(
        task_count=task_count,
        tasks_with_existing_evidence=tasks_with_existing_evidence,
        candidates_with_existing_evidence=candidates_with_existing_evidence,
    )


def validation_passed(payload: JsonObject) -> bool | None:
    if not payload:
        return None
    status = str(payload.get("status") or payload.get("overall_status") or "").strip().lower()
    if status in {"success", "passed", "ok"}:
        return True
    if status in {"blocked", "failed", "error"}:
        return False
    if "passed" in payload:
        return bool(payload.get("passed"))
    return None


def float_or_none(value: JsonValue) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def int_or_zero(value: JsonValue) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def list_count(value: JsonValue) -> int:
    return len(value) if isinstance(value, list) else 0


def bool_or_none(value: JsonValue) -> bool | None:
    if value is None:
        return None
    return bool(value)


def rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)
