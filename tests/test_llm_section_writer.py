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

import json
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
    _decode_publication_binding_tokens,
    _decode_publication_callback_moves,
    _decode_publication_research_requests,
    default_section_system_prompt,
    dynamic_writer_cumulative_budget,
    write_publication_method_by_sections,
    write_method_by_sections,
)
from code2paper.llm.response_schemas import (
    PublicationMethodSectionOutputV1,
    json_schema_for,
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

    if completion_tokens is None:
        token_usage = None
    else:
        token_usage = {"completion_tokens": completion_tokens} if not blocked_reason else {}
    return LLMResponse(
        text=text,
        response_hash=hash_text(text),
        finish_reason=finish_reason,
        token_usage=token_usage,
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
    def test_estimated_output_tokens_is_zero_only_for_empty_text(self) -> None:
        from code2paper.llm.section_writer import _estimated_output_tokens

        self.assertEqual(_estimated_output_tokens(""), 0)
        self.assertEqual(_estimated_output_tokens(None), 0)
        # Every non-empty response is charged at least one token, including
        # one-to-three character bodies such as the schema-failed ``{}``.
        for text in ("{}", "x", "ab", "123", "a" * 4, "a" * 400):
            self.assertGreaterEqual(_estimated_output_tokens(text), 1)
        self.assertEqual(_estimated_output_tokens("a" * 400), 100)
        self.assertEqual(_estimated_output_tokens("abcd"), 1)

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

    def test_short_nonempty_response_without_usage_counts_at_least_one(self) -> None:
        # A one-to-three character non-empty response must never consume zero
        # budget: it is charged the shared minimum estimate of one token.
        from code2paper.export.run_manifest import hash_text

        response = LLMResponse(
            text="{}",
            response_hash=hash_text("{}"),
            finish_reason="stop",
            token_usage=None,
        )
        caller = _RecordingCaller([response])
        result = write_method_by_sections(
            _base_config(),
            [_section("a")],
            llm_caller=caller,
        )
        self.assertEqual(result.cumulative_budget_consumed, 1)

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


class DynamicPublicationBudgetTests(unittest.TestCase):
    def test_compact_research_callback_is_bound_to_current_section(self) -> None:
        text, fields = _decode_publication_research_requests(
            json.dumps({
                "new_research_requests": [{
                    "move": "inference_and_output",
                    "reason": "Which validated artifact establishes the returned output?",
                    "status": "unresolved",
                }]
            }),
            section_id="MA-S1",
            argument_graph={
                "argument_unit_ids": ["MA-S1:unit"],
                "moves": [{
                    "move": "inference_and_output",
                    "allowed_authority_lanes": ["executable_hard"],
                }],
            },
        )
        payload = json.loads(text)
        request = payload["new_research_requests"][0]
        self.assertEqual(fields, ["new_research_requests[0]"])
        self.assertEqual(request["request_id"], "request:MA-S1:inference_and_output:1")
        self.assertEqual(request["section_id"], "MA-S1")
        self.assertEqual(request["argument_unit_id"], "MA-S1:unit")
        self.assertEqual(request["status"], "open")
        self.assertEqual(request["required_authority_lane"], "executable_hard")

    def test_scalar_binding_tokens_bridge_back_to_exact_arrays(self) -> None:
        contract = {
            "used_claim_ids": ["claim:1", "claim:2"],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }
        text, fields = _decode_publication_binding_tokens(
            json.dumps({
                "section_id": "mechanism",
                "section_markdown": "A sufficiently grounded section.",
                "used_claim_ids": '["claim:1","claim:2"]',
                "completed_rhetorical_moves": '["mechanism_overview"]',
            }),
            contract,
        )
        payload = json.loads(text)
        self.assertEqual(payload["used_claim_ids"], ["claim:1", "claim:2"])
        self.assertEqual(payload["completed_rhetorical_moves"], ["mechanism_overview"])
        self.assertEqual(fields, ["used_claim_ids", "completed_rhetorical_moves"])

    def test_fulfilled_callback_move_metadata_is_bridged_without_reopening_request(self) -> None:
        text, fields = _decode_publication_callback_moves(
            json.dumps({
                "section_markdown": "The author-confirmed objective is stated here.",
                "completed_rhetorical_moves": [],
                "new_research_requests": [],
            }),
            resolution={
                "fulfilled_moves": [{
                    "move": "design_objective",
                    "argument_unit_id": "MA-S1:unit",
                    "authority_lane": "author_attested",
                }],
            },
        )
        payload = json.loads(text)
        assert payload["completed_rhetorical_moves"] == ["design_objective"]
        assert fields == ["completed_rhetorical_moves:design_objective"]

        untouched, untouched_fields = _decode_publication_callback_moves(
            json.dumps({
                "completed_rhetorical_moves": [],
                "new_research_requests": [{
                    "missing_rhetorical_move": "design_objective",
                }],
            }),
            resolution={"fulfilled_moves": [{"move": "design_objective"}]},
        )
        assert json.loads(untouched)["completed_rhetorical_moves"] == []
        assert untouched_fields == []

    def test_publication_schema_closes_binding_ids_and_required_moves(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1", "claim:2"],
                    "used_equation_ids": [],
                    "used_configuration_ids": ["config:1"],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                }
            },
            argument_graph={
                "moves": [
                    {"move": "mechanism_overview", "required": True},
                    {"move": "transition_to_next_section", "required": False},
                ]
            },
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertEqual(schema["properties"]["section_id"]["const"], "mechanism")
        self.assertEqual(schema["properties"]["section_markdown"]["minLength"], 800)
        self.assertEqual(schema["properties"]["section_markdown"]["maxLength"], 2400)
        claims = schema["properties"]["used_claim_ids"]
        self.assertEqual(claims["type"], "array")
        self.assertEqual(claims["items"]["enum"], ["claim:1", "claim:2"])
        self.assertEqual(schema["properties"]["used_equation_ids"]["items"], {"type": "string"})
        moves = schema["properties"]["completed_rhetorical_moves"]
        self.assertEqual(moves["items"]["enum"], ["mechanism_overview"])
        self.assertEqual(list(schema["properties"])[-1], "section_markdown")

    def test_publication_schema_allows_bounded_subsets_when_callback_is_required(self) -> None:
        section = WriterSectionInput(
            section_id="callback",
            heading="Callback",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview", "inference_and_output"],
                },
                "grounding_contract": {"callback_required": True},
            },
            argument_graph={"moves": [{"paragraph_budget": 1}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response()])

        write_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
            response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
            publication_mode=True,
        )

        schema = caller.calls[0][1].response_json_schema
        self.assertEqual(schema["properties"]["used_claim_ids"]["type"], "array")
        self.assertEqual(
            schema["properties"]["completed_rhetorical_moves"]["items"]["enum"],
            ["mechanism_overview", "inference_and_output"],
        )

    def test_stop_response_with_wrong_section_binding_is_rejected(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "other-section",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(result.outputs, [])
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertIn("publication_section_binding_failed", result.aggregate.sections[0].blocked_reason)

    def test_empty_section_binding_is_recovered_from_scoped_call(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            # Qwen-class JSON-object responses can omit this metadata field;
            # the request's scoped section is the only safe recovery source.
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_id, "mechanism")
        self.assertFalse(result.aggregate.sections[0].incomplete)

    def test_publication_length_retry_exposes_only_accepted_attempt(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            _response(
                text=payload("A short attempt."),
                finish_reason="length",
                completion_tokens=8192,
            ),
            _response(
                text=payload("A longer accepted mechanism sentence."),
                finish_reason="stop",
                completion_tokens=9000,
            ),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(
            result.outputs[0].section_markdown,
            "A longer accepted mechanism sentence.",
        )
        self.assertEqual(result.aggregate.research_requests, [])
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_schema_binding_failure_triggers_owner_retry(self) -> None:
        """A finish_reason=stop response that fails schema/binding must
        trigger one bounded owner retry carrying the parse error.

        Regression: the section writer only retried on
        ``finish_reason=length``, so a wrong-section binding (or an empty
        JSON object ``{}``) with ``finish_reason=stop`` produced an
        incomplete section with no second chance — the owning Agent never
        got to see its own error and regenerate.
        """
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str, markdown: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: wrong section_id -> binding failure, finish_reason=stop.
            _response(text=payload("other-section", "wrong section binding.")),
            # Retry: correct section_id -> binding passes.
            _response(text=payload("mechanism", "A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls: default + owner retry.
        self.assertEqual(len(caller.calls), 2)
        # The retry request carries the parse error from the first attempt.
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_binding_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        # The retry resolved the failure: the section is accepted.
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_id, "mechanism")
        self.assertFalse(result.aggregate.sections[0].incomplete)
        # Both attempts are recorded as traces.
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_request_exposes_exact_heading_to_writer(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Feature extraction and normalization",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": [],
                    "used_claim_ids": [],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": [],
                },
            },
            argument_graph={"moves": []},
            publication_mode=True,
        )

        def caller(_config, request):
            self.assertEqual(
                request.input_payload["heading"],
                "Feature extraction and normalization",
            )
            return _response(text=json.dumps({
                "section_id": "mechanism",
                "section_markdown": "## Feature extraction and normalization\n\nMethod prose.",
                "used_argument_unit_ids": [],
                "used_claim_ids": [],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": [],
                "new_research_requests": [],
            }))

        result = write_publication_method_by_sections(
            _base_config(), [section], llm_caller=caller,
        )
        self.assertEqual(len(result.outputs), 1)

    def test_publication_schema_binding_retry_failure_keeps_incomplete(self) -> None:
        """When the owner retry also fails schema/binding, the section must
        stay a credible incomplete — the rule layer never patches prose."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": "binding mismatch.",
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: wrong section binding.
            _response(text=payload("other-section")),
            # Retry: still wrong section binding — second failure.
            _response(text=payload("still-wrong")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls happened (default + retry), but the section stays incomplete.
        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_empty_object_schema_failure_triggers_owner_retry(self) -> None:
        """An empty JSON object ``{}`` with finish_reason=stop is a schema
        failure; one bounded owner retry carrying the parse error must
        regenerate a valid section (exactly two calls, two traces)."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: empty object -> schema failure, finish_reason=stop.
            _response(text="{}"),
            # Retry: valid section object -> schema passes.
            _response(text=payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        # Two calls: default + owner retry.
        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_schema_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        # The retry resolved the schema failure.
        self.assertEqual(len(result.outputs), 1)
        self.assertEqual(result.outputs[0].section_markdown, "A grounded mechanism explanation.")
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_empty_object_schema_failure_twice_keeps_incomplete(self) -> None:
        """Two empty-object schema failures remain incomplete after exactly
        two calls — no unbounded third path."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="{}"),
            _response(text="{}"),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 2)

    def _publication_section(self) -> WriterSectionInput:
        return WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

    def _publication_payload(self, markdown: str) -> str:
        return json.dumps({
            "section_id": "mechanism",
            "section_markdown": markdown,
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
            "new_research_requests": [],
        })

    def test_publication_schema_failure_counts_raw_text_estimate_when_usage_absent(self) -> None:
        """A schema-failed publication call that generated non-empty output
        must count its deterministic raw-text estimate toward the cumulative
        budget even when the provider reports no token usage.

        Regression: ``structured_caller`` cleared the invalid text before
        ``_output_tokens_used`` ran, so a streaming provider without usage
        produced a zero token delta and an unauthorized retry could fire after
        the real budget was exhausted."""
        section = self._publication_section()
        raw_text = "x" * 400  # 100 tokens via the len(text)//4 fallback.
        caller = _RecordingCaller([
            _response(text=raw_text, completion_tokens=None),  # schema failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        # The failed first call consumed its raw-text estimate (100), and the
        # retry consumed additional tokens: cumulative accounting is monotonic.
        self.assertGreaterEqual(result.aggregate.cumulative_budget_consumed, 100)
        trace0 = result.aggregate.traces[0]
        trace1 = result.aggregate.traces[1]
        self.assertGreaterEqual(trace0.cumulative_budget_consumed, 100)
        self.assertGreater(trace1.cumulative_budget_consumed, trace0.cumulative_budget_consumed)

    def test_publication_binding_failure_counts_raw_text_estimate_when_usage_absent(self) -> None:
        """A binding-failed publication call with non-empty output and no
        provider usage counts its raw-text estimate toward the budget (same
        accounting invariant as the schema-failure path)."""
        section = self._publication_section()
        raw_text = "y" * 200  # 50 tokens via the len(text)//4 fallback.
        wrong_binding = json.dumps({
            "section_id": "other-section",
            "section_markdown": "wrong binding.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:1"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": ["mechanism_overview"],
            "new_research_requests": [],
        })
        caller = _RecordingCaller([
            _response(text=wrong_binding, completion_tokens=None),  # binding failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        self.assertGreaterEqual(result.aggregate.cumulative_budget_consumed, 50)
        self.assertGreater(
            result.aggregate.traces[1].cumulative_budget_consumed,
            result.aggregate.traces[0].cumulative_budget_consumed,
        )

    def test_publication_empty_object_schema_failure_without_usage_counts_at_least_one(self) -> None:
        """A schema-failed ``{}`` response with no provider usage is charged
        the shared minimum estimate of one token, not zero.

        Regression: the fallback was ``max(0, len(text) // 4)``, so the
        two-character ``{}`` body produced a zero-token delta and an owner
        retry could be authorized without accounting for the failed call."""
        section = self._publication_section()
        caller = _RecordingCaller([
            _response(text="{}", completion_tokens=None),  # schema failure, no usage
            _response(text=self._publication_payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        trace0 = result.aggregate.traces[0]
        trace1 = result.aggregate.traces[1]
        # The failed first attempt consumed at least one token.
        self.assertGreaterEqual(trace0.cumulative_budget_consumed, 1)
        # Cumulative accounting is strictly monotonic across the retry.
        self.assertGreater(trace1.cumulative_budget_consumed, trace0.cumulative_budget_consumed)

    def test_publication_minimum_charge_consuming_remaining_budget_prevents_retry(self) -> None:
        """When the minimum one-token charge of a failed ``{}`` response
        consumes the remaining budget, the owner retry must not be authorized.

        Boundary case: the shared minimum estimate must be enforced for the
        exhausted-budget decision exactly like any larger raw-text estimate."""
        def section_input(section_id: str) -> WriterSectionInput:
            return WriterSectionInput(
                section_id=section_id,
                heading="Section",
                prompt_payload={
                    "binding_contract": {
                        "used_argument_unit_ids": ["unit:1"],
                        "used_claim_ids": ["claim:1"],
                        "used_equation_ids": [],
                        "used_configuration_ids": [],
                        "completed_rhetorical_moves": ["mechanism_overview"],
                    },
                },
                argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
                publication_mode=True,
            )

        def payload(section_id: str, markdown: str) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        first = section_input("first")
        second = section_input("second")
        cap = dynamic_writer_cumulative_budget([first, second])
        pre_consume = cap - 1
        caller = _RecordingCaller([
            # First section consumes cap-1 tokens (valid response).
            _response(text=payload("first", "first section."), completion_tokens=pre_consume),
            # Second section: failed ``{}`` with no usage -> minimum charge 1
            # reaches the cap, so the owner retry must not fire.
            _response(text="{}", completion_tokens=None),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [first, second],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertTrue(result.aggregate.sections[1].incomplete)
        self.assertEqual(len(result.outputs), 1)  # only the first section accepted
        self.assertEqual(len(result.aggregate.traces), 2)
        self.assertGreaterEqual(
            result.aggregate.traces[1].cumulative_budget_consumed,
            cap,
        )

    def test_publication_schema_failure_consuming_remaining_budget_prevents_retry(self) -> None:
        """A failed raw response whose estimate consumes the remaining budget
        must prevent the unauthorized owner retry (no third call beyond the
        budget)."""
        section = self._publication_section()
        cap = dynamic_writer_cumulative_budget([section])
        # Raw text long enough that the estimate alone reaches the cap.
        raw_text = "z" * (cap * 4)
        caller = _RecordingCaller([
            _response(text=raw_text, completion_tokens=None),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)
        self.assertEqual(len(result.aggregate.traces), 1)
        self.assertGreaterEqual(
            result.aggregate.traces[0].cumulative_budget_consumed,
            cap,
        )

    def test_publication_owner_retry_skipped_when_budget_exhausted(self) -> None:
        """When the first call consumes the entire cumulative budget, a
        schema/binding failure must not trigger a second call — the section
        stays a credible incomplete."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="{}", completion_tokens=24576),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.cumulative_budget_exhausted)
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.outputs), 0)

    def test_publication_hard_provider_block_not_retried_by_owner_path(self) -> None:
        """A hard non-schema provider block (content filtering) with
        finish_reason=stop must not trigger the schema/binding owner retry —
        only typed schema/binding failures are repairable by the owning
        Agent."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([
            _response(text="", completion_tokens=0, blocked_reason="content_filter"),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertTrue(result.aggregate.sections[0].incomplete)

    def test_publication_owner_retry_discards_failed_attempt_metadata(self) -> None:
        """Research/callback metadata from a discarded wrong-binding attempt
        is not consumed or duplicated into the aggregate after the owner
        retry succeeds."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(section_id: str, markdown: str, research=()) -> str:
            return json.dumps({
                "section_id": section_id,
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": list(research),
            })

        caller = _RecordingCaller([
            _response(text=payload("other-section", "wrong.", research=[{
                "move": "mechanism_overview",
                "reason": "why?",
                "status": "open",
            }])),
            _response(text=payload("mechanism", "right.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        self.assertEqual(len(result.outputs), 1)
        # The discarded attempt's callback metadata is not consumed.
        self.assertEqual(result.aggregate.research_requests, [])

    def test_publication_structured_complete_schema_failure_triggers_owner_retry(self) -> None:
        """A schema failure carried by the streaming client's
        ``structured_complete`` finish reason must still trigger the one
        bounded owner retry.

        Regression: the owner-retry gate required ``finish_reason ==
        "stop"``, so live streaming responses that failed schema validation
        (``finish_reason="structured_complete"``) became incomplete with no
        second chance for the owning Agent."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:1"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(markdown: str) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": markdown,
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": ["claim:1"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: malformed JSON -> schema failure carried with the
            # streaming client's structured_complete finish reason.
            _response(text='{"section_markdown": "truncated', finish_reason="structured_complete"),
            # Retry: valid response.
            _response(text=payload("A grounded mechanism explanation.")),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_schema_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)

    def test_publication_closed_set_claim_binding_failure_triggers_owner_retry(self) -> None:
        """A near-miss closed-set claim id (transposed characters) is a
        binding failure at the writer boundary and receives one bounded
        owner retry.

        Regression: closed-set claim/equation/config ids were only checked
        after the writer returned, so an invented or transposed id produced
        an unbounded run-level rejection with no owner repair."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123", "claim:def456"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )

        def payload(claim_ids) -> str:
            return json.dumps({
                "section_id": "mechanism",
                "section_markdown": "A grounded mechanism explanation.",
                "used_argument_unit_ids": ["unit:1"],
                "used_claim_ids": list(claim_ids),
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "new_research_requests": [],
            })

        caller = _RecordingCaller([
            # First attempt: claim id with a transposed character -> closed-set
            # binding failure at the writer boundary.
            _response(text=payload(["claim:abc123", "claim:def465"])),
            # Retry: exact authorized claim ids -> binding passes.
            _response(text=payload(["claim:abc123", "claim:def456"])),
        ])
        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 2)
        retry_payload = caller.calls[1][1].input_payload
        self.assertIn("previous_attempt_error", retry_payload)
        self.assertIn(
            "publication_section_binding_failed",
            str(retry_payload["previous_attempt_error"]),
        )
        self.assertIn("unknown_claims", str(retry_payload["previous_attempt_error"]))
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(len(result.aggregate.traces), 2)


    def test_publication_missing_bindings_are_not_writer_failures(self) -> None:
        """Content-first writer semantics: the prose call is never required to
        complete every full id/config/equation/move binding.  A response that
        omits binding ids (or binds only a subset) passes the writer boundary;
        post-processing / validation decides verified inclusion."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123", "claim:def456"],
                    "used_equation_ids": [],
                    "used_configuration_ids": ["config:1"],
                    "completed_rhetorical_moves": ["mechanism_overview", "inference_and_output"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "mechanism",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            # Only one of the two authorized claims is bound; none of the
            # equations/configurations/moves metadata is completed.
            "used_claim_ids": ["claim:abc123"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": [],
            "new_research_requests": [],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(len(caller.calls), 1)
        self.assertEqual(len(result.outputs), 1)
        self.assertFalse(result.aggregate.sections[0].incomplete)
        self.assertEqual(result.outputs[0].used_claim_ids, ["claim:abc123"])

    def test_publication_unknown_binding_id_still_fails_closed(self) -> None:
        """Missing ids are post-processing concerns, but an *invented* id is
        a representation defect: the harness never accepts an id the author
        never authorized."""
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "binding_contract": {
                    "used_argument_unit_ids": ["unit:1"],
                    "used_claim_ids": ["claim:abc123"],
                    "used_equation_ids": [],
                    "used_configuration_ids": [],
                    "completed_rhetorical_moves": ["mechanism_overview"],
                },
            },
            argument_graph={"moves": [{"move": "mechanism_overview", "required": True}]},
            publication_mode=True,
        )
        caller = _RecordingCaller([_response(text=json.dumps({
            "section_id": "mechanism",
            "section_markdown": "A grounded mechanism explanation.",
            "used_argument_unit_ids": ["unit:1"],
            "used_claim_ids": ["claim:invented"],
            "used_equation_ids": [],
            "used_configuration_ids": [],
            "completed_rhetorical_moves": [],
            "new_research_requests": [],
        }))])

        result = write_publication_method_by_sections(
            _base_config(),
            [section],
            llm_caller=caller,
        )

        self.assertEqual(result.outputs, [])
        self.assertTrue(result.aggregate.sections[0].incomplete)
        self.assertIn(
            "unknown_claims",
            result.aggregate.sections[0].blocked_reason,
        )


    def test_argument_plan_sets_dynamic_budget_below_global_cap(self) -> None:
        section = WriterSectionInput(
            section_id="mechanism",
            heading="Mechanism",
            prompt_payload={
                "equation_ids": ["eq:1"],
                "configuration_ids": ["cfg:1", "cfg:2"],
            },
            argument_graph={
                "argument_unit_ids": ["unit:1", "unit:2"],
                "moves": [
                    {"paragraph_budget": 1},
                    {"paragraph_budget": 2},
                ],
            },
            publication_mode=True,
        )

        budget = dynamic_writer_cumulative_budget([section])

        self.assertGreater(budget, 2048)
        self.assertLess(budget, writer_cumulative_budget())

    def test_legacy_inputs_keep_audited_global_cap(self) -> None:
        self.assertEqual(
            dynamic_writer_cumulative_budget([_section("legacy")]),
            writer_cumulative_budget(),
        )


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
