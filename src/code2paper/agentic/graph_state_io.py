from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgenticRunState


def claim_verification_path(state: AgenticRunState) -> str:
    path = state.artifacts.get("claim_verification", "")
    return path if path and path_exists(path) else ""


def read_json(path: str | Any) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_json_if_exists(path: str | Any) -> dict[str, Any]:
    if not path:
        return {}
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def string_mapping(payload: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value) for key, value in payload.items() if str(key).strip() and str(value).strip()}


def path_exists(path: str) -> bool:
    try:
        return bool(path and Path(path).exists())
    except OSError:
        return False
