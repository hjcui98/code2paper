from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgenticRunState


def artifact_exists(state: AgenticRunState, key: str) -> bool:
    path = state.artifacts.get(key, "")
    return bool(path and Path(path).exists())


def artifact_json(state: AgenticRunState, key: str) -> dict[str, Any]:
    path = state.artifacts.get(key, "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def has_any_artifact(state: AgenticRunState, *keys: str) -> bool:
    return any(artifact_exists(state, key) for key in keys)


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
