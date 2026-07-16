"""Provider capability contract for structured LLM responses.

Capabilities only select the transport used to obtain a proposal. They never
change evidence policy or validator outcomes.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict


class StructuredResponseMode(str, Enum):
    NATIVE_JSON_SCHEMA = "native_json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_ONLY = "prompt_only"


class LLMCapabilityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_name: str = "default"
    provider: str = ""
    model: str = ""
    response_mode: StructuredResponseMode = StructuredResponseMode.NATIVE_JSON_SCHEMA
    source: str = "default"
    inference_mode: str = ""
    tensor_parallel_size: int = 0
    speculative_tokens: int = 0
    draft_tensor_parallel_size: int = 0


def load_capability_profile(*, provider: str, model: str) -> LLMCapabilityProfile:
    """Load an explicit JSON profile or use the conservative provider default."""

    raw = os.environ.get("CODE2PAPER_LLM_CAPABILITY_PROFILE", "").strip()
    if raw:
        path = Path(raw).expanduser()
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else json.loads(raw)
        return LLMCapabilityProfile.model_validate(payload)
    return LLMCapabilityProfile(provider=provider, model=model)


def sanitized_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}
