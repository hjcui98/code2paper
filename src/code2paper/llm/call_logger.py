"""LLM call logging utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.schemas import LLMCallLog, LLMConfig


def build_call_log(
    *,
    call_id: str,
    config: LLMConfig,
    request: LLMRequest,
    response: LLMResponse,
    schema_validation_passed: bool = False,
) -> LLMCallLog:
    return LLMCallLog(
        call_id=call_id,
        provider=config.provider,
        model=config.model,
        prompt_template_id=request.prompt_template_id,
        prompt_template_version=config.prompt_template_version,
        input_hash=request.input_hash,
        response_hash=response.response_hash,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        schema_name=request.schema_name,
        schema_validation_passed=schema_validation_passed,
        blocked_reason=response.blocked_reason,
        cached=response.cached,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def write_call_log(path: str | Path, call_log: LLMCallLog) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(call_log.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
