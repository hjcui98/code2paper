from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class FineGrainedToolContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    producer_version: str = "code2paper-agentic-p3"
    input_schema: str
    output_schema: str
    artifact_requirements: list[str] = Field(default_factory=list)
    evidence_policy: str
    side_effects: list[str] = Field(default_factory=list)
    idempotency_fields: list[str] = Field(default_factory=list)
    timeout_class: str = "local_short"
    cost_class: str = "deterministic"
    hard_failure: str
    safe_recovery: str
    hard_gate: bool = False


def atomic_write_bytes(path: str | Path, data: bytes) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return output


def atomic_write_json(path: str | Path, value: BaseModel | dict[str, Any]) -> Path:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return atomic_write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def tool_cache_key(
    *,
    tool_name: str,
    producer_version: str,
    repo_snapshot_id: str,
    input_digests: dict[str, str],
    model_profile: dict[str, Any] | None = None,
    configuration: dict[str, Any] | None = None,
    schema_version: str = "2.0",
) -> str:
    payload = {
        "tool_name": tool_name,
        "producer_version": producer_version,
        "repo_snapshot_id": repo_snapshot_id,
        "input_digests": input_digests,
        "model_profile": model_profile or {},
        "configuration": configuration or {},
        "schema_version": schema_version,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class IdempotentToolCache:
    """Small auditable cache; only successful results are committed."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def invoke(self, key: str, operation: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], bool]:
        path = self.root / f"{key.removeprefix('sha256:')}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")), True
        result = operation()
        atomic_write_json(path, result)
        return result, False
