"""Effective LLM-call config trace (R8 API provenance and audit evidence).

Records the *effective* sampling config that was actually applied to a
single LLM call, plus token usage and finish reason.  This is the
authoritative evidence used by the R8 acceptance checker to verify that
required roles made real, non-cached API calls with non-empty responses.
Sampling, output budgets, and thinking budgets are checked against the
resolved run profile; deployment topology remains auditable metadata.

The trace is intentionally a separate model from ``LLMCallLog`` so it
can be emitted even when full call logging is disabled (e.g., during
fixture runs that exercise only the sampling path).
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.schemas import LLMConfig
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.capabilities import sanitized_origin
from code2paper.llm.providers import openai_compatible_base_url


# A small process-local collector gives every LLM call site (legacy stages
# included) one
# auditable trace channel without threading mutable state through every stage
# tool signature.  The runner resets it at the start of each project run.
_RUN_GENERATION_TRACES: list[dict[str, Any]] = []


def reset_run_generation_traces() -> None:
    _RUN_GENERATION_TRACES.clear()


def record_run_generation_trace(trace: "GenerationCallTrace") -> None:
    _RUN_GENERATION_TRACES.append(trace.model_dump(mode="json"))


def get_run_generation_traces() -> list[dict[str, Any]]:
    return [dict(item) for item in _RUN_GENERATION_TRACES]


class EffectiveSamplingConfig(BaseModel):
    """Snapshot of the sampling config that was applied to a call."""

    model_config = ConfigDict(extra="forbid")

    role: str = ""
    temperature: float
    max_output_tokens: int
    reasoning_effort: str = ""
    thinking_token_budget: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    max_input_tokens: int | None = None
    prompt_template_version: str = ""


class GenerationCallTrace(BaseModel):
    """Per-call trace combining effective config + token usage + finish reason."""

    model_config = ConfigDict(extra="forbid")

    call_id: str
    prompt_template_id: str
    role: str = ""
    provider: str = ""
    model: str = ""
    endpoint_origin: str = ""
    effective_config: EffectiveSamplingConfig
    finish_reason: str = ""
    token_usage: dict[str, int] = Field(default_factory=dict)
    blocked_reason: str = ""
    cached: bool = False
    response_mode: str = ""
    schema_name: str = ""
    input_hash: str = ""
    response_hash: str = ""
    prompt_chars: int = 0
    input_payload_chars: int = 0
    schema_chars: int = 0
    thinking_chars: int = 0
    # Per-role extension state (only meaningful for the method_writer
    # role).  ``extended_budget_used`` is True when the call used the
    # extended budget (12288) instead of the default (8192).
    extended_budget_used: bool = False
    # Cumulative writer budget consumed *after* this call (only set for
    # the method_writer role).
    cumulative_budget_consumed: int | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_effective_sampling_config(config: LLMConfig) -> EffectiveSamplingConfig:
    """Snapshot the effective sampling config from an :class:`LLMConfig`.

    The returned object records the values that were actually applied
    (after role-config overrides), so callers that have already
    invoked :func:`apply_role_config` will see the role-specific
    values here.
    """

    return EffectiveSamplingConfig(
        role=config.role,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        reasoning_effort=config.reasoning_effort,
        thinking_token_budget=config.thinking_token_budget,
        top_p=config.top_p,
        top_k=config.top_k,
        seed=config.seed,
        max_input_tokens=config.max_input_tokens,
        prompt_template_version=config.prompt_template_version,
    )


def build_generation_call_trace(
    *,
    call_id: str,
    config: LLMConfig,
    request: LLMRequest,
    response: LLMResponse,
    extended_budget_used: bool = False,
    cumulative_budget_consumed: int | None = None,
) -> GenerationCallTrace:
    """Build a :class:`GenerationCallTrace` from a completed LLM call.

    Use this immediately after ``LLMClient.complete`` returns to record
    the call for R8 acceptance.  ``call_id`` should be a stable
    identifier (e.g., ``"LLM-writer-section-0"``) so the trace can be
    correlated across the run summary, SQLite checkpoint and R8 report.
    """

    payload_text = json.dumps(request.input_payload, ensure_ascii=False, default=str)
    schema_text = json.dumps(request.response_json_schema or {}, ensure_ascii=False, default=str)
    usage = response.token_usage or {}
    return GenerationCallTrace(
        call_id=call_id,
        prompt_template_id=request.prompt_template_id,
        role=config.role,
        provider=getattr(config.provider, "value", str(config.provider)),
        model=config.model,
        endpoint_origin=endpoint_origin_for_config(config),
        effective_config=build_effective_sampling_config(config),
        finish_reason=response.finish_reason,
        token_usage=usage,
        blocked_reason=response.blocked_reason,
        cached=response.cached,
        response_mode=response.response_mode,
        schema_name=request.schema_name,
        input_hash=request.input_hash,
        response_hash=response.response_hash,
        prompt_chars=len(request.prompt or ""),
        input_payload_chars=len(payload_text),
        schema_chars=len(schema_text),
        thinking_chars=int(usage.get("thinking_chars") or 0),
        extended_budget_used=extended_budget_used,
        cumulative_budget_consumed=cumulative_budget_consumed,
    )


def endpoint_origin_for_config(config: LLMConfig) -> str:
    """Return a credential-free API origin for call provenance."""

    provider = getattr(config.provider, "value", str(config.provider))
    if provider in {"openai", "openrouter"}:
        return sanitized_origin(openai_compatible_base_url(config))
    if provider == "anthropic":
        return "https://api.anthropic.com"
    if provider == "google":
        return "https://generativelanguage.googleapis.com"
    return ""


def trace_matches_role_protocol(
    trace: GenerationCallTrace,
    *,
    expected_temperature: float,
    tolerance: float = 1e-6,
) -> tuple[bool, str]:
    """Verify a trace's effective temperature matches the role protocol.

    Returns ``(ok, reason)``.  ``reason`` is a short human-readable
    string suitable for inclusion in an R8 acceptance report.
    """

    actual = trace.effective_config.temperature
    if abs(actual - expected_temperature) > tolerance:
        return False, (
            f"temperature_mismatch:role={trace.role or 'unknown'} "
            f"actual={actual} expected={expected_temperature}"
        )
    return True, (
        f"temperature_match:role={trace.role or 'unknown'} value={actual}"
    )


__all__ = [
    "EffectiveSamplingConfig",
    "GenerationCallTrace",
    "build_effective_sampling_config",
    "build_generation_call_trace",
    "endpoint_origin_for_config",
    "get_run_generation_traces",
    "record_run_generation_trace",
    "reset_run_generation_traces",
    "trace_matches_role_protocol",
]
