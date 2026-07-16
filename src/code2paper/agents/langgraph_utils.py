"""Dependency-light compatibility layer for embedded PosterGen-style agents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from code2paper.agents.state.poster_state import ModelConfig
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.schemas import LLMConfig, LLMProvider


class AgentResponse:
    def __init__(self, content: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LangGraphAgent:
    """Small text-only wrapper matching the subset used by CodeIntakeAgent."""

    def __init__(self, system_msg: str, config: ModelConfig, state: dict[str, Any] | None = None, agent_name: str = "unknown") -> None:
        self.system_msg = system_msg
        self.config = config
        self.state = state
        self.agent_name = agent_name

    def reset(self) -> None:
        return None

    def step(self, message: str) -> AgentResponse:
        llm_config = _to_llm_config(self.config)
        response = LLMClient(llm_config).complete(
            LLMRequest(
                prompt_template_id=f"code2paper.agents.{self.agent_name}.v1",
                prompt=self.system_msg,
                input_payload={"message": message},
            )
        )
        if response.blocked_reason:
            raise RuntimeError(response.blocked_reason)
        input_tokens = max(1, len(message.split()))
        output_tokens = max(1, len(response.text.split()))
        timing = self.state.get("timing_metrics") if self.state else None
        if hasattr(timing, "add_api_call"):
            timing.add_api_call(self.agent_name, "text", input_tokens, output_tokens)
        return AgentResponse(response.text, input_tokens, output_tokens)


def extract_json(response: str) -> dict[str, Any]:
    text = response.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    parsed = None
    last_error: Exception | None = None
    for candidate in candidates:
        for attempt in (candidate, _repair_common_json(candidate)):
            try:
                parsed = json.loads(attempt)
                break
            except json.JSONDecodeError as exc:
                last_error = exc
        if parsed is not None:
            break
    if parsed is None:
        raise last_error or ValueError("no JSON object found")
    if not isinstance(parsed, dict):
        raise ValueError("expected JSON object")
    return parsed


def _repair_common_json(text: str) -> str:
    repaired = text.replace("\u201c", '"').replace("\u201d", '"')
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    # Insert the comma commonly omitted between a completed value and the
    # following quoted property. Local schema validation remains authoritative.
    return re.sub(r'([}\]"0-9])([ \t\r\n]+)("(?:[^"\\]|\\.)+"\s*:)', r"\1,\2\3", repaired)


def load_prompt(path: str) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parent / path
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    fallback = Path(__file__).resolve().parent / "config" / "prompts" / Path(path).name
    return fallback.read_text(encoding="utf-8") if fallback.exists() else ""


def _to_llm_config(config: ModelConfig) -> LLMConfig:
    provider = _provider(config.provider)
    return LLMConfig(
        provider=provider,
        model=config.model_name,
        temperature=config.temperature,
        max_output_tokens=config.max_tokens,
    )


def _provider(value: str) -> LLMProvider:
    lowered = (value or "").strip().lower()
    if lowered in {"moonshot", "aihubmix", "kimi", "alibaba"}:
        return LLMProvider.OPENAI
    if lowered == "openrouter":
        return LLMProvider.OPENROUTER
    if lowered == "anthropic":
        return LLMProvider.ANTHROPIC
    if lowered == "google":
        return LLMProvider.GOOGLE
    if lowered == "openai":
        return LLMProvider.OPENAI
    return LLMProvider.NONE
