from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from code2paper.export.run_manifest import hash_text
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.response_schemas import parse_structured_response
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


class LLMRuntimeTests(unittest.TestCase):
    def test_openai_compatible_runtime_sends_json_schema_request(self) -> None:
        captured = {}

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.headers.get("Authorization")
            return _FakeHTTPResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", max_output_tokens=100, cache=False)
        request = LLMRequest(
            prompt_template_id="unit",
            prompt="Return JSON.",
            input_payload={"x": 1},
            schema_name="unit_schema",
            response_json_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            response = LLMClient(config).complete(request)

        self.assertEqual(response.text, '{"ok": true}')
        self.assertEqual(response.response_hash, hash_text('{"ok": true}'))
        self.assertEqual(captured["url"], "https://api.openai.com/v1/chat/completions")
        self.assertIn("json_schema", captured["payload"]["response_format"])
        self.assertEqual(captured["authorization"], "Bearer test-key")

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
