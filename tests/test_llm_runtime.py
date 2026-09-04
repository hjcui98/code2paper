from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from code2paper.export.run_manifest import hash_text
from code2paper.llm.client import (
    LLMClient,
    LLMRequest,
    LLMResponse,
    _ProviderResult,
    _first_complete_json,
    _incomplete_json_has_whitespace_padding,
    _post_openai_stream_until_complete_json,
    _set_response_read_timeout,
)
from code2paper.agentic.semantic_verifier_provider import LLMSemanticEvidenceVerifier
from code2paper.llm.capabilities import LLMCapabilityProfile, StructuredResponseMode, load_capability_profile
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.response_schemas import parse_structured_response
from code2paper.llm.retry_policy import RetryPolicy
from code2paper.schemas import (
    AnalysisNavigationPlan,
    DraftClaimMap,
    DraftLatexOutput,
    DraftMarkdownOutput,
    LLMConfig,
    LLMProvider,
    MethodOutline,
    Phase3MechanismBuilderOutput,
    Phase3StageBuilderOutput,
    TargetedRevisionOutput,
    TerminologyTable,
)


class _FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class _FakeStreamingResponse(_FakeHTTPResponse):
    def __iter__(self):
        for item in self.payload["events"]:
            yield f"data: {json.dumps(item)}\n".encode("utf-8")


class _FakeRawStreamingResponse(_FakeHTTPResponse):
    def __iter__(self):
        yield from self.payload["lines"]


class _BufferedSocket:
    def __init__(self) -> None:
        self.timeout = 0.0

    def settimeout(self, value: float) -> None:
        self.timeout = value


class _FakeBufferedStreamingResponse(_FakeHTTPResponse):
    def __init__(self, lines: list[bytes]) -> None:
        super().__init__({})
        self.lines = iter(lines)
        self.fp = type("FP", (), {})()
        self.fp.raw = type("Raw", (), {})()
        self.fp.raw._sock = _BufferedSocket()

    def readline(self) -> bytes:
        return next(self.lines, b"")

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        line = self.readline()
        if not line:
            raise StopIteration
        return line


class LLMRuntimeTests(unittest.TestCase):
    def test_complete_json_detector_ignores_braces_inside_strings(self) -> None:
        text = 'prefix [note] {"markdown":"a } and \\\"{\\\"", "ids":["x"]}{"repeat":true}'
        self.assertEqual(
            _first_complete_json(text),
            '{"markdown":"a } and \\\"{\\\"", "ids":["x"]}',
        )

    def test_complete_json_detector_never_promotes_nested_array(self) -> None:
        self.assertIsNone(_first_complete_json('{"ids":[1]'))
        self.assertEqual(_first_complete_json('{"ids":[1]}'), '{"ids":[1]}')

    def test_incomplete_json_whitespace_padding_is_transport_only(self) -> None:
        truncated = (
            '{"goal":"Find the SSM core","rationale":"I need to search for SSM-related or"'
            + ("\n" * 80)
        )
        self.assertTrue(_incomplete_json_has_whitespace_padding(truncated))
        self.assertFalse(
            _incomplete_json_has_whitespace_padding('{"ok":true}' + ("\n" * 80))
        )
        self.assertFalse(_incomplete_json_has_whitespace_padding('{"ok":true'))
        self.assertFalse(_incomplete_json_has_whitespace_padding("\n" * 80))

    def test_structured_stream_closes_on_incomplete_json_whitespace_padding(self) -> None:
        """Regression (DyG r3 callback): truncated JSON then a wall of
        newlines consumed the full supervisor budget before parse failed."""

        class PaddingThenMore(_FakeHTTPResponse):
            def __iter__(self):
                yield b'data: {"choices":[{"delta":{"content":"{\\"goal\\":\\"Find SSM"}}]}\n'
                yield (
                    b'data: {"choices":[{"delta":{"content":'
                    + json.dumps("\n" * 80).encode("utf-8")
                    + b"}}]}\n"
                )
                yield b'data: {"choices":[{"delta":{"content":"SHOULD_NOT_READ"}}]}\n'
                raise AssertionError("client read padding past whitespace abort")

        def fake_urlopen(_request, timeout=0):  # noqa: ANN001
            return PaddingThenMore({})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            text = _post_openai_stream_until_complete_json(
                "http://127.0.0.1:8003/v1/chat/completions",
                {"stream": True},
                headers={},
                timeout_seconds=10,
                retry_policy=RetryPolicy(max_attempts=1),
            )

        self.assertTrue(text.startswith('{"goal":"Find SSM'))
        self.assertNotIn("SHOULD_NOT_READ", text)
        self.assertGreaterEqual(len(text) - len(text.rstrip()), 64)

    def test_loopback_structured_stream_drains_terminal_usage_after_first_json(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeStreamingResponse({"events": [
                {"choices": [{"delta": {"content": '{"ok":'}}]},
                {"choices": [{"delta": {"content": "true}"}}]},
                {"choices": [{"delta": {"content": '{"repeat":true}'}}]},
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 7,
                        "total_tokens": 19,
                    },
                },
                {"choices": []},
            ]})

        config = LLMConfig(provider=LLMProvider.OPENAI, model="local-model", cache=False)
        profile = LLMCapabilityProfile(response_mode=StructuredResponseMode.NATIVE_JSON_SCHEMA)
        request = LLMRequest(
            prompt_template_id="unit-stream",
            prompt="Return JSON.",
            input_payload={},
            response_json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )
        env = {
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8003/v1",
            "CODE2PAPER_LLM_STREAM_STRUCTURED": "1",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config, capability_profile=profile).complete(request)

        self.assertTrue(captured["payload"]["stream"])
        self.assertEqual(response.text, '{"ok":true}')
        self.assertEqual(response.finish_reason, "structured_complete")
        self.assertEqual(
            response.token_usage,
            {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
        )

    def test_loopback_structured_stream_preserves_partial_text_on_premature_end(self) -> None:
        """When the provider ends the stream before a complete JSON value,
        the client must return the model's own accumulated bytes so the
        writer's representation recovery (e.g. closing an unambiguous
        container suffix) can attempt them, instead of discarding the text
        as a hard transport block.

        Regression: MA-S2 in the live RAP run ended with
        ``provider_stream_finished_before_complete_json`` and empty text;
        the owning Writer never saw the partial response."""
        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeStreamingResponse({"events": [
                {"choices": [{"delta": {"content": '{"ok":'}}]},
                {"choices": [{"delta": {"content": "true"}}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ]})

        config = LLMConfig(provider=LLMProvider.OPENAI, model="local-model", cache=False)
        profile = LLMCapabilityProfile(response_mode=StructuredResponseMode.NATIVE_JSON_SCHEMA)
        request = LLMRequest(
            prompt_template_id="unit-stream",
            prompt="Return JSON.",
            input_payload={},
            response_json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )
        env = {
            "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8003/v1",
            "CODE2PAPER_LLM_STREAM_STRUCTURED": "1",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config, capability_profile=profile).complete(request)

        # The accumulated model bytes are preserved, not discarded.
        self.assertEqual(response.text, '{"ok":true')
        self.assertFalse(response.blocked_reason)

    def test_structured_stream_stops_at_done_on_keep_alive_connection(self) -> None:
        """[DONE] is terminal even when the HTTP socket remains open."""

        class DoneThenOpen(_FakeHTTPResponse):
            def __iter__(self):
                yield b'data: {"choices":[{"delta":{"content":"{\\"ok\\":true"}}]}\n'
                yield b"data: [DONE]\n"
                raise AssertionError("client read beyond SSE terminal marker")

        def fake_urlopen(_request, timeout=0):  # noqa: ANN001
            return DoneThenOpen({})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            text = _post_openai_stream_until_complete_json(
                "http://127.0.0.1:8003/v1/chat/completions",
                {"stream": True},
                headers={},
                timeout_seconds=10,
                retry_policy=RetryPolicy(max_attempts=1),
            )

        self.assertEqual(text, '{"ok":true')

    def test_structured_stream_consumes_urllib_buffer_before_socket_readiness(self) -> None:
        response = _FakeBufferedStreamingResponse([
            b'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"}}]}\n',
            b"data: [DONE]\n",
        ])

        with patch("urllib.request.urlopen", return_value=response):
            text = _post_openai_stream_until_complete_json(
                "http://127.0.0.1:8003/v1/chat/completions",
                {"stream": True},
                headers={},
                timeout_seconds=10,
                retry_policy=RetryPolicy(max_attempts=1),
            )

        self.assertEqual(text, '{"ok":true}')
        self.assertGreater(response.fp.raw._sock.timeout, 0)
        self.assertTrue(_set_response_read_timeout(response, 3.0))
        self.assertEqual(response.fp.raw._sock.timeout, 3.0)

    def test_runtime_loads_tracked_nested_deployment_profile(self) -> None:
        profile_path = "tests/baselines/agentic/gemma4_mtp_vllm.profile.json"

        with patch.dict(os.environ, {"CODE2PAPER_LLM_CAPABILITY_PROFILE": profile_path}, clear=True):
            profile = load_capability_profile(provider="openai", model="gemma4-31b-nvfp4")

        self.assertEqual(profile.response_mode, StructuredResponseMode.PROMPT_ONLY)
        self.assertEqual(profile.inference_mode, "mtp")
        self.assertEqual(profile.tensor_parallel_size, 2)
        self.assertEqual(profile.speculative_tokens, 1)
        self.assertEqual(profile.draft_tensor_parallel_size, 2)
        self.assertEqual(profile.assistant_model_name, "Gemma-4-31B-it-assistant")
        self.assertEqual(profile.max_model_len, 131072)

    def test_semantic_verifier_trace_binds_runtime_profile_and_source_digest(self) -> None:
        profile_path = "tests/baselines/agentic/gemma4_mtp_vllm.profile.json"
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gemma4-31b-nvfp4", cache=False)
        response = LLMResponse(
            text='{"status":"supported","rationale":"direct evidence matches"}',
            response_hash="sha256:response",
            response_mode="prompt_only",
            finish_reason="stop",
            token_usage={"completion_tokens": 8},
        )

        with patch.dict(os.environ, {"CODE2PAPER_LLM_CAPABILITY_PROFILE": profile_path}, clear=True), patch.object(
            LLMClient, "complete", return_value=response
        ):
            verifier = LLMSemanticEvidenceVerifier(config)
            result = verifier({"claim": "The implementation calls train()."})

        self.assertEqual(result["status"], "supported")
        trace = verifier.traces[0]
        self.assertEqual(trace["model"], "gemma4-31b-nvfp4")
        self.assertEqual(trace["capability_profile"]["inference_mode"], "mtp")
        self.assertEqual(
            trace["capability_profile_source_digest"],
            "sha256:1dce0d3e1e07a6dda065309cdade03907f414187b97e3a401fb6038b737af3a7",
        )

    def test_cache_binds_prompt_and_capability_and_preserves_response_metadata(self) -> None:
        request = LLMRequest(prompt_template_id="cache-unit", prompt="Return JSON.", input_payload={"x": 1})
        base = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="local-model",
            prompt_template_version="v1",
            retry_max_attempts=1,
            cache=True,
        )
        native = LLMCapabilityProfile(profile_name="native", response_mode=StructuredResponseMode.NATIVE_JSON_SCHEMA)
        prompt_only = LLMCapabilityProfile(profile_name="prompt", response_mode=StructuredResponseMode.PROMPT_ONLY)
        calls = {"count": 0}

        def complete_provider(_client, _request):
            calls["count"] += 1
            return _ProviderResult(
                text='{"ok": true}', response_mode="native_json_schema", finish_reason="stop",
                token_usage={"completion_tokens": 4},
            )

        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {"CODE2PAPER_LLM_CACHE_DIR": tmpdir, "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1"},
            clear=True,
        ), patch.object(LLMClient, "_complete_provider", complete_provider):
            first = LLMClient(base, capability_profile=native).complete(request)
            cached = LLMClient(base, capability_profile=native).complete(request)
            changed_prompt = LLMClient(
                base.model_copy(update={"prompt_template_version": "v2"}), capability_profile=native
            ).complete(request)
            changed_capability = LLMClient(base, capability_profile=prompt_only).complete(request)

        self.assertFalse(first.cached)
        self.assertTrue(cached.cached)
        self.assertEqual(cached.response_mode, "native_json_schema")
        self.assertEqual(cached.finish_reason, "stop")
        self.assertEqual(cached.token_usage, {"completion_tokens": 4})
        self.assertFalse(changed_prompt.cached)
        self.assertFalse(changed_capability.cached)
        self.assertEqual(calls["count"], 3)

    def test_openai_compatible_runtime_sends_json_schema_request(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.headers.get("Authorization")
            return _FakeHTTPResponse(
                {
                    "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                }
            )

        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", max_output_tokens=100, cache=False)
        request = LLMRequest(
            prompt_template_id="unit",
            prompt="Return JSON.",
            input_payload={"x": 1},
            schema_name="unit_schema",
            response_json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "CODE2PAPER_LLM_STREAM_STRUCTURED": "0",
                "CODE2PAPER_OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
        ), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config).complete(request)

        self.assertEqual(response.text, '{"ok": true}')
        self.assertEqual(response.response_hash, hash_text('{"ok": true}'))
        self.assertEqual(captured["url"], "https://api.openai.com/v1/chat/completions")
        self.assertIn("json_schema", captured["payload"]["response_format"])
        self.assertEqual(captured["authorization"], "Bearer test-key")
        self.assertEqual(response.response_mode, "native_json_schema")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.token_usage, {"prompt_tokens": 10, "completion_tokens": 4})

    def test_loopback_openai_endpoint_strips_unique_items_from_json_schema(self) -> None:
        """Loopback vLLM rejects ``uniqueItems``; the client strips it while
        preserving ``enum``/``const`` so guided decoding still enforces the
        closed-set binding (preventing representation errors such as field
        names emitted as claim ids).
        """

        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeHTTPResponse(
                {"choices": [{"message": {"content": '{"section_id": "MA-S1"}'}, "finish_reason": "stop"}]}
            )

        config = LLMConfig(provider=LLMProvider.OPENAI, model="local-model", max_output_tokens=100, cache=False)
        request = LLMRequest(
            prompt_template_id="unit",
            prompt="Return JSON.",
            input_payload={"x": 1},
            schema_name="unit_schema",
            response_json_schema={
                "type": "object",
                "properties": {
                    "section_id": {"type": "string", "const": "MA-S1"},
                    "used_claim_ids": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["C1", "C2"]},
                        "maxItems": 2,
                        "uniqueItems": True,
                    },
                },
            },
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "dummy-local-vllm",
                "CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8003/v1",
                "CODE2PAPER_LLM_STREAM_STRUCTURED": "0",
            },
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            LLMClient(config).complete(request)

        schema = captured["payload"]["response_format"]["json_schema"]["schema"]
        # uniqueItems is stripped everywhere.
        self.assertNotIn("uniqueItems", schema["properties"]["used_claim_ids"])
        # enum/const are preserved so guided decoding still enforces the binding.
        self.assertEqual(schema["properties"]["section_id"]["const"], "MA-S1")
        self.assertEqual(schema["properties"]["used_claim_ids"]["items"]["enum"], ["C1", "C2"])
        self.assertEqual(schema["properties"]["used_claim_ids"]["maxItems"], 2)

    def test_remote_openai_endpoint_preserves_unique_items(self) -> None:
        """Remote (non-loopback) endpoints keep ``uniqueItems`` unchanged."""

        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeHTTPResponse(
                {"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}
            )

        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", max_output_tokens=100, cache=False)
        request = LLMRequest(
            prompt_template_id="unit",
            prompt="Return JSON.",
            input_payload={"x": 1},
            schema_name="unit_schema",
            response_json_schema={
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
                },
            },
        )

        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "CODE2PAPER_LLM_STREAM_STRUCTURED": "0",
                "CODE2PAPER_OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
        ), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            LLMClient(config).complete(request)

        schema = captured["payload"]["response_format"]["json_schema"]["schema"]
        self.assertTrue(schema["properties"]["ids"]["uniqueItems"])

    def test_openai_compatible_runtime_downgrades_to_json_object_mode(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _FakeHTTPResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        config = LLMConfig(provider=LLMProvider.OPENAI, model="local-model", cache=False)
        profile = LLMCapabilityProfile(response_mode=StructuredResponseMode.JSON_OBJECT)
        request = LLMRequest(
            prompt_template_id="unit",
            prompt="Return JSON.",
            input_payload={},
            response_json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config, capability_profile=profile).complete(request)

        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})
        self.assertIn("Return JSON matching this schema", captured["payload"]["messages"][0]["content"])
        self.assertEqual(response.response_mode, "json_object")

    def test_loopback_openai_endpoint_allows_nonsecret_dummy_key(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="local-model", cache=False)

        with patch.dict(
            os.environ,
            {"CODE2PAPER_OPENAI_BASE_URL": "http://127.0.0.1:8000/v1"},
            clear=True,
        ):
            self.assertTrue(has_provider_api_key(config))

    def test_openai_compatible_runtime_retries_empty_content(self) -> None:
        calls = {"count": 0}

        def fake_urlopen(_request, timeout=0):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] == 1:
                return _FakeHTTPResponse({"choices": [{"message": {"content": ""}}]})
            return _FakeHTTPResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-test",
            max_output_tokens=100,
            retry_max_attempts=2,
            retry_initial_delay_seconds=0,
            cache=False,
        )
        request = LLMRequest(prompt_template_id="unit", prompt="Return JSON.", input_payload={"x": 1})

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config).complete(request)

        self.assertEqual(response.text, '{"ok": true}')
        self.assertEqual(calls["count"], 2)

    def test_response_parser_repairs_fenced_json(self) -> None:
        parsed = parse_structured_response(
            """```json
{"author_logic_summary":"from llm","navigation_questions":[],"comment_triage":{}}
```""",
            AnalysisNavigationPlan,
        )

        self.assertEqual(parsed.author_logic_summary, "from llm")

    def test_response_parser_repairs_phase3_stage_legacy_extra_fields(self) -> None:
        parsed = parse_structured_response(
            json.dumps(
                {
                    "stages": [
                        {
                            "stage_id": "S1",
                            "name": "Stage One",
                            "purpose": "Do things",
                            "inputs": ["x"],
                            "outputs": ["y"],
                            "mechanism_ids": ["MECH1"],
                            "evidence_span_ids": ["E1"],
                        }
                    ]
                }
            ),
            Phase3StageBuilderOutput,
        )

        self.assertEqual(len(parsed.stages), 1)
        self.assertEqual(parsed.stages[0].stage_id, "S1")
        self.assertEqual(len(parsed.stages[0].mechanisms), 1)
        self.assertEqual(parsed.stages[0].mechanisms[0].mechanism_id, "MECH1")
        self.assertEqual(parsed.stages[0].mechanisms[0].evidence_ids, ["E1"])

    def test_response_parser_repairs_phase3_mechanism_legacy_shape(self) -> None:
        parsed = parse_structured_response(
            json.dumps(
                {
                    "frozen_mechanisms": [
                        {
                            "mechanism_id": "MECH1",
                            "name": "Stage I Bridge",
                            "description": "Projector-language alignment from legacy response.",
                            "status": "not_in_bounded_context",
                            "evidence_ids": ["E3622"],
                            "path": "pointllm/model/pointllm.py",
                            "symbol": "PointLLMLlamaModel",
                            "distinguishing_level": "primary",
                        }
                    ]
                }
            ),
            Phase3MechanismBuilderOutput,
        )

        self.assertEqual(len(parsed.frozen_mechanisms), 1)
        mechanism = parsed.frozen_mechanisms[0]
        self.assertEqual(mechanism.mechanism_id, "MECH1")
        self.assertEqual(mechanism.mechanism_name, "Stage I Bridge")
        self.assertEqual(
            mechanism.mechanism_description,
            "Projector-language alignment from legacy response.",
        )
        self.assertEqual(mechanism.author_claim_relation.value, "ambiguous_due_to_missing_context")
        self.assertEqual(mechanism.evidence_span_ids, ["E3622"])
        self.assertEqual(mechanism.implementation_anchor.path, "pointllm/model/pointllm.py")
        self.assertEqual(mechanism.implementation_anchor.symbols, ["PointLLMLlamaModel"])
        self.assertEqual(mechanism.distinguishing_level, "main")

    def test_response_parser_repairs_draft_claim_map_legacy_evidence_alias(self) -> None:
        parsed = parse_structured_response(
            json.dumps(
                {
                    "paragraphs": [
                        {
                            "paragraph_id": "P1",
                            "claim_ids": ["C1"],
                            "mechanisms": ["MECH1"],
                            "evidence_ids": ["E19"],
                        }
                    ]
                }
            ),
            DraftClaimMap,
        )

        self.assertEqual(len(parsed.paragraphs), 1)
        paragraph = parsed.paragraphs[0]
        self.assertEqual(paragraph.paragraph_id, "P1")
        self.assertEqual(paragraph.claim_ids, ["C1"])
        self.assertEqual(paragraph.mechanism_ids, ["MECH1"])
        self.assertEqual(paragraph.evidence_span_ids, ["E19"])

    def test_response_parser_repairs_phase4_terminology_extra_fields(self) -> None:
        parsed = parse_structured_response(
            json.dumps(
                {
                    "terms": [
                        {
                            "id": "TERM-STAGE-1",
                            "term": "input_preparation",
                            "type": "stage",
                            "definition": "Extra provider prose that is not part of the local schema.",
                            "synonyms": ["input stage"],
                            "evidence_ids": ["E1"],
                            "stage_ids": ["S1"],
                        }
                    ]
                }
            ),
            TerminologyTable,
        )

        self.assertEqual(len(parsed.terms), 1)
        term = parsed.terms[0]
        self.assertEqual(term.term_id, "TERM-STAGE-1")
        self.assertEqual(term.canonical, "input_preparation")
        self.assertEqual(term.term_type, "stage")
        self.assertEqual(term.allowed_synonyms, ["input stage"])
        self.assertEqual(term.source_ids, ["S1"])
        self.assertEqual(term.evidence_span_ids, ["E1"])

    def test_response_parser_repairs_phase4_outline_and_draft_aliases(self) -> None:
        outline = parse_structured_response(
            json.dumps(
                {
                    "paragraphs": [
                        {
                            "id": "P1",
                            "heading": "Overview",
                            "stages": ["S1"],
                            "mechanisms": ["MECH1"],
                            "claims": ["C1"],
                            "evidence_ids": ["E1"],
                        }
                    ],
                    "logic_order": ["S1"],
                }
            ),
            MethodOutline,
        )
        markdown = parse_structured_response(json.dumps({"content": "# Method"}), DraftMarkdownOutput)
        latex = parse_structured_response(json.dumps({"method_draft_tex": "\\section{Method}"}), DraftLatexOutput)
        revision = parse_structured_response(
            json.dumps(
                {
                    "revised_markdown": "# Revised",
                    "revised_latex": "\\section{Revised}",
                    "notes": ["fixed grounding"],
                    "resolved_issues": ["CE1"],
                }
            ),
            TargetedRevisionOutput,
        )

        self.assertEqual(outline.sections[0].paragraph_id, "P1")
        self.assertEqual(outline.sections[0].purpose, "Describe Overview.")
        self.assertEqual(outline.sections[0].evidence_span_ids, ["E1"])
        self.assertEqual(outline.author_logic_order, ["S1"])
        self.assertEqual(markdown.markdown, "# Method")
        self.assertEqual(latex.latex, "\\section{Method}")
        self.assertEqual(revision.markdown, "# Revised")
        self.assertEqual(revision.latex, "\\section{Revised}")
        self.assertEqual(revision.revision_notes, ["fixed grounding"])
        self.assertEqual(revision.resolved_issue_ids, ["CE1"])


if __name__ == "__main__":
    unittest.main()
