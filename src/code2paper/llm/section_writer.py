"""Section-based Method writer (Phase 1 R8 writer protocol).

Implements the writer role's per-section generation protocol:

- Each Method section is a separate LLM call tagged
  ``role="method_writer"``.
- Per-call default budget is 8192 tokens
  (:func:`role_config.writer_default_budget`).
- When a section call returns ``finish_reason == "length"``, the call
  is retried once with the extended budget (12288 tokens).  This is
  the *only* permitted escalation path — non-length finish reasons
  never escalate.
- The cumulative output token budget across all section calls is
  capped at 24576 tokens
  (:func:`role_config.writer_cumulative_budget`).  Once the cap is
  reached, no further section calls are made; remaining sections are
  filled with a deterministic scaffold placeholder so the writer
  always produces a contiguous Method draft.
- Each call emits a :class:`GenerationCallTrace` for R8 acceptance
  evidence (role, effective config, finish reason, token usage,
  cumulative budget consumed).

This module is the authoritative writer protocol implementation.  The
legacy phase5 authoring path can opt into section-based generation by
calling :func:`write_method_by_sections` instead of issuing a single
``METHOD_DRAFT_SCHEMA`` call.

Hard rules:

- ``finish_reason`` values other than ``"length"`` (e.g., ``"stop"``,
  ``"content_filter"``) do NOT trigger escalation.
- The cumulative budget is measured in *output* tokens (sum of
  ``completion_tokens`` reported by the provider).  When the provider
  does not report token usage, we fall back to estimating output
  tokens as ``len(text) // 4`` so the cap is still enforced.
- A section whose LLM call is blocked (``blocked_reason`` non-empty)
  is filled with a deterministic placeholder; the writer does NOT
  retry blocked calls (retry is the LLM client's job).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.generation_trace import GenerationCallTrace, build_generation_call_trace
from code2paper.llm.role_config import (
    METHOD_WRITER,
    apply_role_config,
    writer_cumulative_budget,
)
from code2paper.schemas import LLMConfig

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriterSectionInput:
    """A single section to be rendered by the writer.

    ``section_id`` is a stable identifier (used in the trace ``call_id``).
    ``heading`` is the section heading (e.g., ``"Overview"``).
    ``prompt_payload`` is the per-section input payload (already
    projected from the authoring plan / evidence / claim map).
    ``system_prompt`` is the per-section system prompt; when empty,
    :func:`write_method_by_sections` uses :func:`default_section_system_prompt`.
    """

    section_id: str
    heading: str
    prompt_payload: dict[str, Any]
    system_prompt: str = ""


@dataclass
class WriterSectionResult:
    """Result of generating a single section."""

    section_id: str
    heading: str
    text: str
    finish_reason: str
    extended_budget_used: bool
    blocked_reason: str = ""
    trace: GenerationCallTrace | None = None


@dataclass
class WriterAggregateResult:
    """Aggregate result of a section-based writer run."""

    sections: list[WriterSectionResult] = field(default_factory=list)
    traces: list[GenerationCallTrace] = field(default_factory=list)
    cumulative_budget_consumed: int = 0
    cumulative_budget_cap: int = 0
    cumulative_budget_exhausted: bool = False
    concatenated_markdown: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "sections": [
                {
                    "section_id": s.section_id,
                    "heading": s.heading,
                    "text_length": len(s.text),
                    "finish_reason": s.finish_reason,
                    "extended_budget_used": s.extended_budget_used,
                    "blocked_reason": s.blocked_reason,
                }
                for s in self.sections
            ],
            "traces": [t.to_json_dict() for t in self.traces],
            "cumulative_budget_consumed": self.cumulative_budget_consumed,
            "cumulative_budget_cap": self.cumulative_budget_cap,
            "cumulative_budget_exhausted": self.cumulative_budget_exhausted,
            "concatenated_markdown_length": len(self.concatenated_markdown),
        }


# ---------------------------------------------------------------------------
# LLM client protocol (for testability)
# ---------------------------------------------------------------------------


class _LLMCaller(Protocol):
    """Callable signature for the LLM complete function."""

    def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse: ...


def _default_llm_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    return LLMClient(config).complete(request)


# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------


def default_section_system_prompt() -> str:
    """Return the default per-section system prompt for the method writer.

    The prompt instructs the model to render a single Method section
    from the provided projection payload, without inventing evidence
    or reintroducing unsupported claims.
    """

    return (
        "You are the Method writer inside Code2Paper's robust LangGraph "
        "research agent.  You are rendering ONE section of the Method "
        "from the provided projection payload.\n\n"
        "Hard constraints:\n"
        "- Use ONLY claims and evidence present in the projection payload.\n"
        "- Do NOT invent file paths, symbol names, span IDs or evidence IDs.\n"
        "- Do NOT reintroduce text that was previously flagged as unsupported.\n"
        "- Render the section as Markdown, starting with a level-2 heading.\n"
        "- Keep the section focused; do not describe other sections.\n"
    )


# ---------------------------------------------------------------------------
# Budget tracking
# ---------------------------------------------------------------------------


def _output_tokens_used(response: LLMResponse) -> int:
    """Return the number of output tokens consumed by a call.

    Falls back to ``len(text) // 4`` when the provider did not report
    token usage, so the cumulative cap is still enforced.
    """

    usage = response.token_usage or {}
    for key in ("completion_tokens", "output_tokens", "generated_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return max(0, len(response.text or "") // 4)


# ---------------------------------------------------------------------------
# Section-based writer
# ---------------------------------------------------------------------------


def write_method_by_sections(
    base_config: LLMConfig,
    sections: Iterable[WriterSectionInput],
    *,
    llm_caller: _LLMCaller | None = None,
    call_id_prefix: str = "LLM-writer-section",
    schema_name: str = "DraftMarkdownOutput",
    response_json_schema: dict[str, Any] | None = None,
) -> WriterAggregateResult:
    """Render a Method document by calling the writer once per section.

    See module docstring for the writer protocol (default 8192 budget,
    extended 12288 on ``finish_reason="length"``, cumulative 24576 cap).

    ``base_config`` is the base LLM config; per-call configs are
    derived by :func:`apply_role_config` with ``role="method_writer"``.
    The base config's ``role`` field is overwritten to
    ``"method_writer"`` on every call.

    ``llm_caller`` is injectable for testing; the default constructs a
    fresh :class:`LLMClient` per call.

    Returns a :class:`WriterAggregateResult` with the concatenated
    Markdown, per-section traces, and cumulative budget accounting.
    """

    caller = llm_caller or _default_llm_caller
    cap = writer_cumulative_budget()

    result = WriterAggregateResult(cumulative_budget_cap=cap)
    rendered_sections: list[str] = []

    for index, section in enumerate(sections):
        # Stop issuing LLM calls once the cumulative budget is exhausted.
        if result.cumulative_budget_consumed >= cap:
            result.cumulative_budget_exhausted = True
            placeholder = _placeholder_section(section, reason="cumulative_budget_exhausted")
            rendered_sections.append(placeholder)
            result.sections.append(
                WriterSectionResult(
                    section_id=section.section_id,
                    heading=section.heading,
                    text=placeholder,
                    finish_reason="skipped_cumulative_budget_exhausted",
                    extended_budget_used=False,
                )
            )
            continue

        system_prompt = section.system_prompt or default_section_system_prompt()
        request = LLMRequest(
            prompt_template_id=f"phase5_method_writer_section_v1",
            prompt=system_prompt,
            input_payload=section.prompt_payload,
            schema_name=schema_name,
            response_json_schema=response_json_schema,
        )

        # First attempt: default budget.
        call_config = apply_role_config(
            base_config, METHOD_WRITER, extended_writer_budget=False
        )
        call_config = call_config.model_copy(
            update={
                "max_output_tokens": min(
                    call_config.max_output_tokens,
                    cap - result.cumulative_budget_consumed,
                )
            }
        )
        call_id = f"{call_id_prefix}-{index}-{section.section_id}"
        response = _safe_call(caller, call_config, request)
        extended_used = False

        # Emit a trace for the default-budget call.  R8 protocol
        # requires "each call records effective sampling config"; even
        # when the call is later superseded by an extended-budget
        # retry, the default-budget call still happened and must be
        # evidenced in the trace list.
        default_used = _output_tokens_used(response)
        default_cumulative = min(cap, result.cumulative_budget_consumed + default_used)
        default_trace = build_generation_call_trace(
            call_id=call_id,
            config=call_config,
            request=request,
            response=response,
            extended_budget_used=False,
            cumulative_budget_consumed=default_cumulative,
        )
        result.traces.append(default_trace)
        accepted_trace: GenerationCallTrace = default_trace
        accepted_response = response
        # Cumulative budget always counts every token the LLM
        # generated, regardless of whether the response was accepted
        # -- the GPU spent those tokens either way.
        result.cumulative_budget_consumed = default_cumulative

        # Escalate only on finish_reason == "length".
        if (
            response.finish_reason == "length"
            and not response.blocked_reason
            and result.cumulative_budget_consumed < cap
        ):
            extended_config = apply_role_config(
                base_config, METHOD_WRITER, extended_writer_budget=True
            )
            extended_config = extended_config.model_copy(
                update={
                    "max_output_tokens": min(
                        extended_config.max_output_tokens,
                        cap - result.cumulative_budget_consumed,
                    )
                }
            )
            extended_call_id = f"{call_id_prefix}-{index}-{section.section_id}-ext"
            extended_response = _safe_call(caller, extended_config, request)
            extended_token_used = _output_tokens_used(extended_response)
            extended_cumulative = min(
                cap, result.cumulative_budget_consumed + extended_token_used
            )
            extended_trace = build_generation_call_trace(
                call_id=extended_call_id,
                config=extended_config,
                request=request,
                response=extended_response,
                extended_budget_used=True,
                cumulative_budget_consumed=extended_cumulative,
            )
            result.traces.append(extended_trace)
            # The extended call's tokens always count toward the
            # cumulative budget (the GPU spent them).
            result.cumulative_budget_consumed = extended_cumulative
            # Only accept the extended response if it actually produced
            # more content than the truncated default response.
            if len(extended_response.text or "") > len(response.text or ""):
                accepted_response = extended_response
                accepted_trace = extended_trace
                extended_used = True

        section_text = accepted_response.text or _placeholder_section(section, reason="empty_response")
        rendered_sections.append(section_text)
        result.sections.append(
            WriterSectionResult(
                section_id=section.section_id,
                heading=section.heading,
                text=section_text,
                finish_reason=accepted_response.finish_reason,
                extended_budget_used=extended_used,
                blocked_reason=accepted_response.blocked_reason,
                trace=accepted_trace,
            )
        )

        if result.cumulative_budget_consumed >= cap:
            result.cumulative_budget_exhausted = True

    result.concatenated_markdown = "\n\n".join(rendered_sections)
    return result


def _safe_call(
    caller: _LLMCaller, config: LLMConfig, request: LLMRequest
) -> LLMResponse:
    """Call ``caller`` and convert exceptions into a blocked response.

    The writer never raises from a single-section LLM failure; the
    section is filled with a placeholder and the run continues so the
    final Method is always contiguous.
    """

    try:
        return caller(config, request)
    except Exception as exc:  # noqa: BLE001 — writer must not crash on LLM errors
        _logger.warning("section_writer_llm_error: %s", exc)
        from code2paper.export.run_manifest import hash_text

        return LLMResponse(
            text="",
            response_hash=hash_text(""),
            blocked_reason=f"section_writer_llm_error:{exc.__class__.__name__}",
        )


def _placeholder_section(section: WriterSectionInput, *, reason: str) -> str:
    """Return a deterministic placeholder for a skipped section."""

    return (
        f"## {section.heading}\n\n"
        f"<!-- writer_placeholder: section_id={section.section_id} reason={reason} -->\n"
    )


__all__ = [
    "WriterAggregateResult",
    "WriterSectionInput",
    "WriterSectionResult",
    "default_section_system_prompt",
    "write_method_by_sections",
]
