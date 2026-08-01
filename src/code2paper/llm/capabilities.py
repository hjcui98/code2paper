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
    assistant_model_name: str = ""
    max_model_len: int = 0


def builtin_capability_profile(*, provider: str, model: str) -> LLMCapabilityProfile:
    """Return the conservative built-in profile for a second provider path.

    Capability selection changes transport/response formatting only.  It does
    not alter evidence, claim authorization, or final-text gates.
    """

    provider_value = str(provider or "").strip().lower()
    model_value = str(model or "").strip()
    if provider_value == "anthropic":
        return LLMCapabilityProfile(
            profile_name="anthropic-structured-json-v1",
            provider=provider_value,
            model=model_value,
            response_mode=StructuredResponseMode.JSON_OBJECT,
            source="builtin",
        )
    if provider_value in {"openrouter", "google"}:
        return LLMCapabilityProfile(
            profile_name=f"{provider_value}-prompt-json-v1",
            provider=provider_value,
            model=model_value,
            response_mode=StructuredResponseMode.JSON_OBJECT,
            source="builtin",
        )
    return LLMCapabilityProfile(
        profile_name="default-native-json-v1",
        provider=provider_value,
        model=model_value,
        response_mode=StructuredResponseMode.NATIVE_JSON_SCHEMA,
        source="builtin",
    )


def load_capability_profile(*, provider: str, model: str) -> LLMCapabilityProfile:
    """Load an explicit JSON profile or use the conservative provider default."""

    raw = os.environ.get("CODE2PAPER_LLM_CAPABILITY_PROFILE", "").strip()
    if raw:
        path = Path(raw).expanduser()
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else json.loads(raw)
        return LLMCapabilityProfile.model_validate(_runtime_profile_payload(payload, source=str(path) if path.is_file() else "inline"))
    return builtin_capability_profile(provider=provider, model=model)


def _runtime_profile_payload(payload: object, *, source: str) -> object:
    if not isinstance(payload, dict) or not isinstance(payload.get("deployment_expectations"), dict):
        return payload
    deployment = payload["deployment_expectations"]
    return {
        "profile_name": payload.get("profile_name", "default"),
        "provider": payload.get("provider", ""),
        "model": payload.get("model", ""),
        "response_mode": payload.get("response_mode", StructuredResponseMode.NATIVE_JSON_SCHEMA.value),
        "source": source,
        "inference_mode": deployment.get("inference_mode", ""),
        "tensor_parallel_size": deployment.get("tensor_parallel_size", 0),
        "speculative_tokens": deployment.get("speculative_tokens", 0),
        "draft_tensor_parallel_size": deployment.get("draft_tensor_parallel_size", 0),
        "assistant_model_name": deployment.get("mtp_assistant_model_name", ""),
        "max_model_len": deployment.get("max_model_len", 0),
    }


def sanitized_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


__all__ = [
    "LLMCapabilityProfile",
    "StructuredResponseMode",
    "builtin_capability_profile",
    "is_loopback_url",
    "load_capability_profile",
    "sanitized_origin",
]
