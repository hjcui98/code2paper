"""Strict byte-level wire decoding shared by contracts and the private worker."""
from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "c2p-dsh/1"
MAX_FRAME_BYTES = 1 << 20
MAX_READ_CHUNK = 64 << 10
MAX_SAFE_INTEGER = (1 << 53) - 1


class ProtocolError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ProtocolError("duplicate_json_key")
        result[key] = value
    return result


def validate_json_value(value: Any) -> None:
    if type(value) is int and abs(value) > MAX_SAFE_INTEGER:
        raise ProtocolError("integer_out_of_range")
    if type(value) is float and not math.isfinite(value):
        raise ProtocolError("non_finite_number")
    if isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as error:
            raise ProtocolError("invalid_unicode") from error
    if isinstance(value, dict):
        for key, item in value.items():
            validate_json_value(key)
            validate_json_value(item)
    if isinstance(value, list):
        for item in value:
            validate_json_value(item)


def strict_json_loads(raw: bytes | str, *, max_bytes: int = MAX_FRAME_BYTES) -> Any:
    try:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(data) > max_bytes:
            raise ProtocolError("frame_too_large")
        value = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ProtocolError("non_finite_number")))
        validate_json_value(value)
        return value
    except ProtocolError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ProtocolError("invalid_json") from error


def parse_model(raw: bytes | str, model: type[WireModel]) -> WireModel:
    from pydantic import ValidationError
    from code2paper.agentic.digest import canonical_json_bytes
    value = strict_json_loads(raw)
    try:
        # JSON mode preserves tuples and literal enums while keeping strict scalar types.
        return model.model_validate_json(canonical_json_bytes(value), strict=True)
    except ValidationError as error:
        raise ProtocolError("schema_invalid") from error


def require_provider_quiescence(wait_for_exit_result: Any) -> None:
    """Provider's bounded cleanup wait must positively prove scope exit."""
    if wait_for_exit_result is not True:
        raise ProtocolError("provider_scope_not_quiescent")
