from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class AgenticDecisionPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: str
    objective: str
    hard_rules: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    fallback_decision: dict[str, Any] = Field(default_factory=dict)


class AgenticDecisionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-decision-trace"
    node: str
    provider_status: str = "deterministic_fallback"
    prompt: AgenticDecisionPrompt
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    parsed_proposal: dict[str, Any] = Field(default_factory=dict)
    final_decision: dict[str, Any] = Field(default_factory=dict)
    safety_notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class DecisionProviderResult:
    proposal: Mapping[str, Any] | BaseModel | None
    response_metadata: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        if self.proposal is None:
            raise AttributeError(name)
        return getattr(self.proposal, name)


DecisionProvider = Callable[[AgenticDecisionPrompt], Mapping[str, Any] | BaseModel | DecisionProviderResult | None]


def build_langchain_decision_provider(runnable: Any) -> DecisionProvider:
    if not hasattr(runnable, "invoke"):
        raise TypeError("LangChain decision provider requires an object with invoke()")

    def _provider(prompt: AgenticDecisionPrompt) -> Mapping[str, Any] | BaseModel | None:
        response = runnable.invoke(prompt.model_dump(mode="json"))
        return _coerce_provider_payload(response)

    return _provider


def write_decision_trace(path: str | Path, trace: AgenticDecisionTrace) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_decision_trace(path: str | Path) -> AgenticDecisionTrace:
    return AgenticDecisionTrace.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _call_provider(
    provider: DecisionProvider,
    prompt: AgenticDecisionPrompt,
    schema: type[BaseModel],
) -> BaseModel | None:
    try:
        raw = provider(prompt)
    except Exception:
        return None
    if isinstance(raw, DecisionProviderResult):
        raw = raw.proposal
    if raw is None:
        return None
    payload = _coerce_provider_payload(raw)
    if payload is None:
        return None
    try:
        return schema.model_validate(payload)
    except (TypeError, ValueError, ValidationError):
        return None


def _call_provider_for_trace(
    provider: DecisionProvider,
    prompt: AgenticDecisionPrompt,
    schema: type[BaseModel],
) -> tuple[str, dict[str, Any], BaseModel | None]:
    try:
        raw = provider(prompt)
    except Exception as exc:
        return "provider_error", {"error": exc.__class__.__name__}, None
    response_metadata: dict[str, Any] = {}
    if isinstance(raw, DecisionProviderResult):
        response_metadata = dict(raw.response_metadata)
        raw = raw.proposal
    if raw is None:
        if response_metadata:
            return "provider_no_decision", {"response_metadata": response_metadata}, None
        return "provider_no_decision", {}, None
    payload = _coerce_provider_payload(raw)
    if payload is None:
        return "provider_unparseable", {"raw_type": raw.__class__.__name__}, None
    payload_dict = _model_or_mapping_to_dict(payload)
    trace_payload = dict(payload_dict)
    if response_metadata:
        trace_payload["response_metadata"] = response_metadata
    try:
        return "model_proposal_merged", trace_payload, schema.model_validate(payload)
    except (TypeError, ValueError, ValidationError) as exc:
        invalid_payload = dict(payload_dict)
        if response_metadata:
            invalid_payload["response_metadata"] = response_metadata
        invalid_payload["validation_error"] = exc.__class__.__name__
        return "provider_invalid_schema", invalid_payload, None


def _coerce_provider_payload(raw: Any) -> Mapping[str, Any] | BaseModel | None:
    if raw is None:
        return None
    if isinstance(raw, BaseModel):
        return raw
    if isinstance(raw, Mapping):
        return raw
    content = getattr(raw, "content", None)
    if content is not None:
        return _coerce_provider_payload(content)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, Mapping) else None
    try:
        return dict(raw)
    except (TypeError, ValueError):
        return None


def _build_decision_trace(
    *,
    prompt: AgenticDecisionPrompt,
    provider_status: str,
    final_decision: BaseModel,
    provider_payload: dict[str, Any] | None = None,
    parsed_proposal: BaseModel | None = None,
    safety_notes: list[str] | None = None,
) -> AgenticDecisionTrace:
    return AgenticDecisionTrace(
        node=prompt.node,
        provider_status=provider_status,
        prompt=prompt,
        provider_payload=provider_payload or {},
        parsed_proposal=parsed_proposal.model_dump(mode="json") if parsed_proposal else {},
        final_decision=final_decision.model_dump(mode="json"),
        safety_notes=safety_notes or [],
    )


def _model_or_mapping_to_dict(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump(mode="json"))
    return _json_safe(dict(value))


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        if isinstance(value, Mapping):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        return str(value)
