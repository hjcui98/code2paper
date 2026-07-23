"""Tests for ``code2paper.llm.section_writer`` (Phase 1 writer protocol).

Verifies the section-based Method writer:

- Per-section LLM calls are tagged ``role="method_writer"``.
- Default budget is 8192; extended budget (12288) is used only on
  ``finish_reason="length"`` and only when the extended response is
  actually longer.
- Cumulative 24576-token cap stops further section calls once reached;
  remaining sections are filled with deterministic placeholders.
- Each call emits a :class:`GenerationCallTrace` for R8 acceptance.
- Blocked LLM calls do NOT crash the writer; the section gets a
  placeholder and the run continues.
"""

from __future__ import annotations

import unittest
from typing import Any

from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.role_config import (
    METHOD_WRITER,
    ROLE_GENERATION_CONFIGS,
    writer_cumulative_budget,
)
from code2paper.llm.section_writer import (
    WriterAggregateResult,
    WriterSectionInput,
    WriterSectionResult,
    default_section_system_prompt,
    write_method_by_sections,
)
from code2paper.schemas import LLMConfig, LLMProvider


def _base_config(**overrides) -> LLMConfig:
    defaults = dict(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        temperature=0.2,
        max_output_tokens=12000,
        cache=False,
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _section(section_id: str, heading: str = "Section") -> WriterSectionInput:
    return WriterSectionInput(
        section_id=section_id,
        heading=heading,
        prompt_payload={"section_id": section_id, "evidence": []},
    )


class _RecordingCaller:
    """Records every LLM call and returns canned responses.

    Each call records ``(config, request)`` so tests can assert on the
    effective sampling config and prompt payload.  The list of canned
    responses is consumed in order; the same response is returned for
    every call once the canned list is exhausted.
    """

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[LLMConfig, LLMRequest]] = []

    def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse:
        self.calls.append((config, request))
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(
            text="## default",
            response_hash="sha256:default",
            finish_reason="stop",
            token_usage={"completion_tokens": 100},
        )


def _response(
    text: str = "## Section\ncontent",
    *,
    finish_reason: str = "stop",
    completion_tokens: int = 100,
    blocked_reason: str = "",
) -> LLMResponse:
    from code2paper.export.run_manifest import hash_text

    return LLMResponse(
        text=text,
        response_hash=hash_text(text),
        finish_reason=finish_reason,
        token_usage={"completion_tokens": completion_tokens} if not blocked_reason else {},
        blocked_reason=blocked_reason,
    )


class DefaultSystemPromptTests(unittest.TestCase):
    def test_default_section_system_prompt_mentions_constraints(self) -> None:
        prompt = default_section_system_prompt()
        self.assertIn("Method writer", prompt)
        self.assertIn("Hard constraints", prompt)


class WriteMethodBySectionsBasicTests(unittest.TestCase):
    def test_single_section_produces_concatenated_markdown(self) -> None:
        caller = _RecordingCaller([_response(text="## Overview\ncontent")])
        result = write_method_by_sections(
            _base_config(),
            [_section("overview", "Overview")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 1)
        self.assertEqual(result.sections[0].text, "## Overview\ncontent")
        self.assertEqual(result.concatenated_markdown, "## Overview\ncontent")

    def test_two_sections_concatenated_with_double_newline(self) -> None:
        caller = _RecordingCaller([
            _response(text="## A\ncontent-a"),
            _response(text="## B\ncontent-b"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a", "A"), _section("b", "B")],
            llm_caller=caller,
        )
        self.assertEqual(
            result.concatenated_markdown,
            "## A\ncontent-a\n\n## B\ncontent-b",
        )

    def test_each_call_tagged_with_method_writer_role(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        config, _ = caller.calls[0]
        self.assertEqual(config.role, METHOD_WRITER)

    def test_each_call_uses_writer_protocol_temperature(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        config, _ = caller.calls[0]
        self.assertEqual(
            config.temperature,
            ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        )

    def test_each_call_uses_default_writer_budget_8192(self) -> None:
        caller = _RecordingCaller([_response()])
        write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        config, _ = caller.calls[0]
        self.assertEqual(config.max_output_tokens, 8192)


class FinishReasonLengthEscalationTests(unittest.TestCase):
    def test_length_triggers_extended_budget_retry(self) -> None:
        # First call returns finish_reason=length with a short response;
        # the extended retry should produce a longer response.
        caller = _RecordingCaller([
            _response(text="## truncated", finish_reason="length", completion_tokens=8192),
            _response(text="## full content that is longer than truncated", finish_reason="stop", completion_tokens=9000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 2)
        # First call uses default budget; second uses extended.
        self.assertEqual(caller.calls[0][0].max_output_tokens, 8192)
        self.assertEqual(caller.calls[1][0].max_output_tokens, 12288)
        self.assertTrue(result.sections[0].extended_budget_used)
        self.assertEqual(result.sections[0].finish_reason, "stop")

    def test_length_does_not_trigger_extended_when_response_shorter(self) -> None:
        # Extended response is shorter than the original -> keep original.
        caller = _RecordingCaller([
            _response(text="## truncated long content here", finish_reason="length", completion_tokens=8192),
            _response(text="## short", finish_reason="stop", completion_tokens=100),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        # Two calls were made (default + extended retry), but the
        # original was kept because the extended was shorter.
        self.assertEqual(len(caller.calls), 2)
        self.assertFalse(result.sections[0].extended_budget_used)
        self.assertIn("truncated long content", result.sections[0].text)

    def test_stop_finish_reason_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="## content", finish_reason="stop"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)

    def test_content_filter_finish_reason_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="## content", finish_reason="content_filter"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)

    def test_blocked_response_does_not_trigger_extended(self) -> None:
        caller = _RecordingCaller([
            _response(text="", finish_reason="length", blocked_reason="content_filter"),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertFalse(result.sections[0].extended_budget_used)


class CumulativeBudgetTests(unittest.TestCase):
    def test_cumulative_budget_cap_is_24576(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_cap, 24576)
        self.assertEqual(result.cumulative_budget_cap, writer_cumulative_budget())

    def test_cumulative_budget_consumed_uses_completion_tokens(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=1000),
            _response(completion_tokens=2000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 3000)
        self.assertFalse(result.cumulative_budget_exhausted)

    def test_cumulative_budget_exhaustion_stops_further_calls(self) -> None:
        # First call consumes the entire 24576 budget; second section
        # should get a placeholder and no further LLM call.
        caller = _RecordingCaller([
            _response(completion_tokens=24576),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.cumulative_budget_exhausted)
        self.assertEqual(len(result.sections), 2)
        self.assertEqual(result.sections[0].finish_reason, "stop")
        self.assertEqual(result.sections[1].finish_reason, "skipped_cumulative_budget_exhausted")
        self.assertIn("writer_placeholder", result.sections[1].text)

    def test_cumulative_budget_exhaustion_uses_placeholder_text(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=24576),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b", "Background")],
            llm_caller=caller,
        )
        self.assertIn("## Background", result.sections[1].text)
        self.assertIn("cumulative_budget_exhausted", result.sections[1].text)

    def test_cumulative_budget_cap_clamps_consumed(self) -> None:
        # completion_tokens > cap should clamp to cap.
        caller = _RecordingCaller([
            _response(completion_tokens=99999),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 24576)
        self.assertTrue(result.cumulative_budget_exhausted)

    def test_next_call_is_limited_to_remaining_cumulative_budget(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=8000),
            _response(completion_tokens=8000),
            _response(completion_tokens=8000),
            _response(completion_tokens=576),
        ])
        write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b"), _section("c"), _section("d")],
            llm_caller=caller,
        )
        self.assertEqual(caller.calls[3][0].max_output_tokens, 576)


class TokenUsageFallbackTests(unittest.TestCase):
    def test_missing_completion_tokens_falls_back_to_text_length(self) -> None:
        # No token_usage -> fall back to len(text) // 4.
        from code2paper.export.run_manifest import hash_text

        text = "x" * 400  # 100 tokens via the // 4 fallback.
        response = LLMResponse(
            text=text,
            response_hash=hash_text(text),
            finish_reason="stop",
            token_usage=None,
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 100)

    def test_empty_token_usage_falls_back_to_text_length(self) -> None:
        from code2paper.export.run_manifest import hash_text

        text = "y" * 80  # 20 tokens via the // 4 fallback.
        response = LLMResponse(
            text=text,
            response_hash=hash_text(text),
            finish_reason="stop",
            token_usage={},
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 20)


class TraceEmissionTests(unittest.TestCase):
    def test_each_call_emits_a_trace(self) -> None:
        caller = _RecordingCaller([
            _response(),
            _response(),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.traces), 2)
        for trace in result.traces:
            self.assertEqual(trace.role, METHOD_WRITER)

    def test_trace_records_extended_budget_used(self) -> None:
        caller = _RecordingCaller([
            _response(text="short", finish_reason="length", completion_tokens=100),
            _response(text="much longer extended response content", finish_reason="stop", completion_tokens=200),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.traces), 2)
        self.assertFalse(result.traces[0].extended_budget_used)
        self.assertTrue(result.traces[1].extended_budget_used)

    def test_trace_records_cumulative_budget_consumed(self) -> None:
        caller = _RecordingCaller([
            _response(completion_tokens=1000),
            _response(completion_tokens=2000),
        ])
        result = write_method_by_sections(
            _base_config(),
            [_section("a"), _section("b")],
            llm_caller=caller,
        )
        self.assertEqual(result.traces[0].cumulative_budget_consumed, 1000)
        self.assertEqual(result.traces[1].cumulative_budget_consumed, 3000)

    def test_trace_records_effective_temperature(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(
            result.traces[0].effective_config.temperature,
            ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        )


class ErrorHandlingTests(unittest.TestCase):
    def test_llm_exception_does_not_crash_writer(self) -> None:
        class _ExplodingCaller:
            def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse:
                raise RuntimeError("boom")

        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=_ExplodingCaller(),  # type: ignore[arg-type]
        )
        self.assertEqual(len(result.sections), 1)
        self.assertTrue(result.sections[0].blocked_reason)
        self.assertIn("section_writer_llm_error", result.sections[0].blocked_reason)

    def test_empty_response_text_uses_placeholder(self) -> None:
        caller = _RecordingCaller([_response(text="")])
        result = write_method_by_sections(
            _base_config(),
            [_section("a", "Overview")],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 1)
        self.assertIn("## Overview", result.sections[0].text)
        self.assertIn("writer_placeholder", result.sections[0].text)


class AggregateResultTests(unittest.TestCase):
    def test_to_json_dict_has_expected_keys(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        data = result.to_json_dict()
        self.assertIn("sections", data)
        self.assertIn("traces", data)
        self.assertIn("cumulative_budget_consumed", data)
        self.assertIn("cumulative_budget_cap", data)
        self.assertIn("cumulative_budget_exhausted", data)
        self.assertIn("concatenated_markdown_length", data)

    def test_to_json_dict_section_entries_have_expected_fields(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        data = result.to_json_dict()
        section_entry = data["sections"][0]
        self.assertEqual(section_entry["section_id"], "a")
        self.assertIn("text_length", section_entry)
        self.assertIn("finish_reason", section_entry)
        self.assertIn("extended_budget_used", section_entry)
        self.assertIn("blocked_reason", section_entry)


class EmptySectionsTests(unittest.TestCase):
    def test_empty_sections_returns_empty_result(self) -> None:
        caller = _RecordingCaller([])
        result = write_method_by_sections(
            _base_config(),
            [],
            llm_caller=caller,
        )
        self.assertEqual(len(result.sections), 0)
        self.assertEqual(len(result.traces), 0)
        self.assertEqual(result.cumulative_budget_consumed, 0)
        self.assertFalse(result.cumulative_budget_exhausted)
        self.assertEqual(result.concatenated_markdown, "")


class CustomCallIdPrefixTests(unittest.TestCase):
    def test_custom_call_id_prefix_appears_in_traces(self) -> None:
        caller = _RecordingCaller([_response()])
        result = write_method_by_sections(
            _base_config(),
            [_section("overview")],
            llm_caller=caller,
            call_id_prefix="LLM-method-overview",
        )
        self.assertTrue(
            result.traces[0].call_id.startswith("LLM-method-overview"),
            f"call_id was {result.traces[0].call_id}",
        )


if __name__ == "__main__":
    unittest.main()
