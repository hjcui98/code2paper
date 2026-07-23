"""Tests for ``code2paper.llm.generation_trace`` (Phase 1 R8 evidence).

Verifies that ``EffectiveSamplingConfig`` and ``GenerationCallTrace``
correctly snapshot the LLM config, that ``build_generation_call_trace``
captures the response's finish reason / token usage / hashes, and that
``trace_matches_role_protocol`` accepts compliant traces and rejects
temperature mismatches.
"""

from __future__ import annotations

import unittest

from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.generation_trace import (
    EffectiveSamplingConfig,
    GenerationCallTrace,
    build_effective_sampling_config,
    build_generation_call_trace,
    trace_matches_role_protocol,
)
from code2paper.llm.role_config import (
    METHOD_WRITER,
    RESEARCH_SUPERVISOR,
    ROLE_GENERATION_CONFIGS,
)
from code2paper.schemas import LLMConfig, LLMProvider


def _config(**overrides) -> LLMConfig:
    defaults = dict(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        temperature=0.20,
        max_output_tokens=1536,
        cache=False,
        role=RESEARCH_SUPERVISOR,
        top_p=0.9,
        top_k=20,
        seed=42,
        max_input_tokens=90000,
        prompt_template_version="v1",
    )
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _request() -> LLMRequest:
    return LLMRequest(
        prompt_template_id="phase5_method_writer_section_v1",
        prompt="system prompt",
        input_payload={"section": "overview"},
        schema_name="DraftMarkdownOutput",
    )


def _response(**overrides) -> LLMResponse:
    defaults = dict(
        text="## Overview\nThe model computes a softmax.",
        response_hash="sha256:resp",
        finish_reason="stop",
        token_usage={"completion_tokens": 100, "prompt_tokens": 200, "total_tokens": 300},
        response_mode="prompt_only",
    )
    defaults.update(overrides)
    return LLMResponse(**defaults)


class EffectiveSamplingConfigTests(unittest.TestCase):
    def test_build_effective_sampling_config_snapshots_all_fields(self) -> None:
        cfg = _config()
        eff = build_effective_sampling_config(cfg)
        self.assertEqual(eff.role, RESEARCH_SUPERVISOR)
        self.assertEqual(eff.temperature, 0.20)
        self.assertEqual(eff.max_output_tokens, 1536)
        self.assertEqual(eff.top_p, 0.9)
        self.assertEqual(eff.top_k, 20)
        self.assertEqual(eff.seed, 42)
        self.assertEqual(eff.max_input_tokens, 90000)
        self.assertEqual(eff.prompt_template_version, "v1")

    def test_effective_sampling_config_optional_fields_default_to_none(self) -> None:
        cfg = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="m",
            temperature=0.0,
            max_output_tokens=1,
        )
        eff = build_effective_sampling_config(cfg)
        self.assertIsNone(eff.top_p)
        self.assertIsNone(eff.top_k)
        self.assertIsNone(eff.seed)
        self.assertIsNone(eff.max_input_tokens)

    def test_effective_sampling_config_rejects_extra_fields(self) -> None:
        with self.assertRaises(Exception):
            EffectiveSamplingConfig(  # type: ignore[call-arg]
                temperature=0.0,
                max_output_tokens=1,
                unknown_field="x",
            )


class BuildGenerationCallTraceTests(unittest.TestCase):
    def test_build_trace_captures_role_and_config(self) -> None:
        cfg = _config()
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=cfg,
            request=_request(),
            response=_response(),
        )
        self.assertEqual(trace.call_id, "LLM-1")
        self.assertEqual(trace.role, RESEARCH_SUPERVISOR)
        self.assertEqual(trace.effective_config.role, RESEARCH_SUPERVISOR)
        self.assertEqual(trace.effective_config.temperature, 0.20)

    def test_build_trace_captures_finish_reason(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(finish_reason="length"),
        )
        self.assertEqual(trace.finish_reason, "length")

    def test_build_trace_captures_token_usage(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(token_usage={"completion_tokens": 500, "total_tokens": 1000}),
        )
        self.assertEqual(trace.token_usage["completion_tokens"], 500)
        self.assertEqual(trace.token_usage["total_tokens"], 1000)

    def test_build_trace_captures_blocked_reason(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(blocked_reason="content_filter"),
        )
        self.assertEqual(trace.blocked_reason, "content_filter")

    def test_build_trace_captures_cached_flag(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(cached=True),
        )
        self.assertTrue(trace.cached)

    def test_build_trace_captures_response_mode(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(response_mode="native_json_schema"),
        )
        self.assertEqual(trace.response_mode, "native_json_schema")

    def test_build_trace_captures_schema_name(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
        )
        self.assertEqual(trace.schema_name, "DraftMarkdownOutput")

    def test_build_trace_captures_input_hash(self) -> None:
        request = _request()
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=request,
            response=_response(),
        )
        self.assertEqual(trace.input_hash, request.input_hash)

    def test_build_trace_captures_response_hash(self) -> None:
        response = _response()
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=response,
        )
        self.assertEqual(trace.response_hash, response.response_hash)

    def test_build_trace_default_extended_budget_used_is_false(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
        )
        self.assertFalse(trace.extended_budget_used)

    def test_build_trace_extended_budget_used_can_be_set_true(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
            extended_budget_used=True,
        )
        self.assertTrue(trace.extended_budget_used)

    def test_build_trace_default_cumulative_budget_consumed_is_none(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
        )
        self.assertIsNone(trace.cumulative_budget_consumed)

    def test_build_trace_cumulative_budget_consumed_can_be_set(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
            cumulative_budget_consumed=12000,
        )
        self.assertEqual(trace.cumulative_budget_consumed, 12000)

    def test_build_trace_prompt_template_id_from_request(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
        )
        self.assertEqual(trace.prompt_template_id, "phase5_method_writer_section_v1")


class GenerationCallTraceSerializationTests(unittest.TestCase):
    def test_to_json_dict_round_trips(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(),
            request=_request(),
            response=_response(),
            cumulative_budget_consumed=5000,
        )
        data = trace.to_json_dict()
        restored = GenerationCallTrace.model_validate(data)
        self.assertEqual(restored, trace)


class TraceMatchesRoleProtocolTests(unittest.TestCase):
    def test_match_returns_true_with_exact_temperature(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(temperature=0.20),
            request=_request(),
            response=_response(),
        )
        ok, reason = trace_matches_role_protocol(trace, expected_temperature=0.20)
        self.assertTrue(ok)
        self.assertIn("temperature_match", reason)

    def test_mismatch_returns_false(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(temperature=0.20),
            request=_request(),
            response=_response(),
        )
        ok, reason = trace_matches_role_protocol(trace, expected_temperature=0.70)
        self.assertFalse(ok)
        self.assertIn("temperature_mismatch", reason)
        self.assertIn("actual=0.2", reason)
        self.assertIn("expected=0.7", reason)

    def test_match_within_tolerance(self) -> None:
        trace = build_generation_call_trace(
            call_id="LLM-1",
            config=_config(temperature=0.200001),
            request=_request(),
            response=_response(),
        )
        ok, _ = trace_matches_role_protocol(trace, expected_temperature=0.20, tolerance=1e-4)
        self.assertTrue(ok)

    def test_match_with_writer_protocol_temperature(self) -> None:
        writer_cfg = _config(
            role=METHOD_WRITER,
            temperature=ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
            max_output_tokens=ROLE_GENERATION_CONFIGS[METHOD_WRITER].max_output_tokens_default,
        )
        trace = build_generation_call_trace(
            call_id="LLM-writer-1",
            config=writer_cfg,
            request=_request(),
            response=_response(),
        )
        ok, _ = trace_matches_role_protocol(
            trace,
            expected_temperature=ROLE_GENERATION_CONFIGS[METHOD_WRITER].temperature,
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
