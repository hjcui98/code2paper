from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from code2paper.agents.code_analyzer import CodeAnalyzerAgent
from code2paper.agents.code_intake import CodeIntakeAgent
from code2paper.agents.langgraph_utils import AgentResponse, LangGraphAgent
from code2paper.agents.state.poster_state import ModelConfig, create_state
from code2paper.llm.client import LLMResponse


class AgentJsonRetryTests(unittest.TestCase):
    def _state(self):
        state = create_state(
            pdf_path="/tmp/author.yaml",
            text_model="kimi-k2.5",
            vision_model="kimi-k2.5",
            output_dir="/tmp/out",
            text_provider="openai",
            vision_provider="openai",
        )
        state["structured_sections"] = {}
        state["paper_objects"] = {}
        state["method_experiment_structured_summary"] = {"method": {}}
        return state

    def test_code_intake_retrieval_plan_retries_twice_before_success(self) -> None:
        agent = CodeIntakeAgent()
        state = self._state()
        plan = {"status": "ok", "priority_files": ["model.py"], "symbol_targets": []}
        calls = {"count": 0}

        def fake_step(_self, _message):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] < 3:
                raise ValueError("expected JSON object")
            return AgentResponse(json.dumps(plan), input_tokens=5, output_tokens=7)

        with patch.object(LangGraphAgent, "step", new=fake_step):
            result, input_tokens, output_tokens = agent._llm_retrieval_plan(
                code_sources={"project_files": [], "repo_structure_hints": {}},
                method_summary={"method": {}},
                structured_sections={},
                keyword_bank=[],
                state=state,
            )

        self.assertEqual(calls["count"], 3)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["priority_files"], ["model.py"])
        self.assertEqual(input_tokens, 5)
        self.assertEqual(output_tokens, 7)

    def test_code_intake_review_enhanced_degrades_after_three_json_failures(self) -> None:
        agent = CodeIntakeAgent()
        state = self._state()
        calls = {"count": 0}

        def fake_step(_self, _message):  # noqa: ANN001
            calls["count"] += 1
            raise ValueError("expected JSON object")

        with patch.object(LangGraphAgent, "step", new=fake_step):
            result, input_tokens, output_tokens = agent._llm_review_enhanced(
                code_sources={},
                core_snippets={"snippets": []},
                method_summary={"method": {}},
                paper_objects={},
                alignment={"coverage_report": {"overall_score": 0}},
                dynamic_roles=set(),
                state=state,
            )

        self.assertEqual(calls["count"], 3)
        self.assertIsNone(result)
        self.assertEqual(input_tokens, 0)
        self.assertEqual(output_tokens, 0)

    def test_code_analyzer_synthesis_retries_twice_before_success(self) -> None:
        agent = CodeAnalyzerAgent()
        state = self._state()
        result_payload = {"modules": [{"name": "Encoder"}], "pipeline_steps": []}
        calls = {"count": 0}

        def fake_step(_self, _message):  # noqa: ANN001
            calls["count"] += 1
            if calls["count"] < 3:
                raise ValueError("expected JSON object")
            return AgentResponse(json.dumps(result_payload), input_tokens=11, output_tokens=13)

        with patch.object(LangGraphAgent, "step", new=fake_step):
            result, input_tokens, output_tokens = agent._llm_synthesis(
                core_snippets={"snippets": []},
                method_code_alignment={},
                paper_objects={},
                method_summary={},
                detailed_analysis={},
                dynamic_roles=[],
                state=state,
            )

        self.assertEqual(calls["count"], 3)
        self.assertEqual(result["modules"][0]["name"], "Encoder")
        self.assertEqual(input_tokens, 11)
        self.assertEqual(output_tokens, 13)

    def test_embedded_agents_emit_their_own_audited_sampling_roles(self) -> None:
        seen = []

        def fake_complete(client, _request):  # noqa: ANN001
            seen.append(client.config)
            return LLMResponse(text="{}", response_hash="sha256:test")

        config = ModelConfig(model_name="gemma4-31b-nvfp4", provider="openai")
        with patch("code2paper.agents.langgraph_utils.LLMClient.complete", new=fake_complete):
            LangGraphAgent("sys", config, agent_name="code_intake").step("message")
            LangGraphAgent("sys", config, agent_name="code_analyzer").step("message")

        self.assertEqual([item.role for item in seen], ["code_intake", "code_analyzer"])
        self.assertEqual([item.max_output_tokens for item in seen], [4096, 4096])
        self.assertEqual([item.temperature for item in seen], [0.20, 0.20])


if __name__ == "__main__":
    unittest.main()
