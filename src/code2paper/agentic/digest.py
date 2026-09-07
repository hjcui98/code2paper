"""Canonical JSON identity helpers used by cross-stage hand-offs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence, Set
from typing import Any

from pydantic import BaseModel


def canonical_json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return canonical_json_value(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {
            str(key): canonical_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [canonical_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [canonical_json_value(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ))
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_json(value: Any) -> str:
    return digest_bytes(canonical_json_bytes(value))


__all__ = [
    "canonical_json_value",
    "canonical_json_bytes",
    "digest_bytes",
    "digest_json",
]
