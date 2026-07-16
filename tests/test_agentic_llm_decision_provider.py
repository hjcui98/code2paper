from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from code2paper.agentic.decisioning import AgenticDecisionPrompt, coverage_decision_with_model
from code2paper.agentic.llm_decision_provider import build_llm_decision_provider
from code2paper.agentic.retrieval import CoverageItem, RetrievalCoverageReport
from code2paper.core.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMResponse


class AgenticLLMDecisionProviderTests(unittest.TestCase):
    def test_provider_is_disabled_without_api_key(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)

        with patch.dict(os.environ, {}, clear=True):
            provider = build_llm_decision_provider(config)

        self.assertIsNone(provider)

    def test_provider_calls_llm_with_node_specific_schema(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        prompt = AgenticDecisionPrompt(
            node="coverage_critic",
            objective="decide retrieval route",
            inputs={"coverage": {"overall_score": 0.3}},
            fallback_decision={"decision": "rescan_intake"},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(
                text='{"decision":"rescan_intake","recommended_next":"intake","rationale":"Need more evidence."}',
                response_hash="sha256:test",
                response_mode="prompt_only",
                finish_reason="stop",
                token_usage={"completion_tokens": 24},
            ),
        ) as complete:
            provider = build_llm_decision_provider(config)
            proposal = provider(prompt) if provider else None

        request = complete.call_args.args[1]
        client = complete.call_args.args[0]
        self.assertEqual(request.prompt_template_id, "agentic_coverage_critic_decision_v1")
        self.assertEqual(request.schema_name, "CoverageCriticProposal")
        self.assertIn("properties", request.response_json_schema)
        self.assertEqual(proposal.decision, "rescan_intake")
        self.assertEqual(proposal.recommended_next, "intake")
        self.assertEqual(proposal.response_metadata["response_mode"], "prompt_only")
        self.assertEqual(proposal.response_metadata["finish_reason"], "stop")
        self.assertTrue(proposal.response_metadata["schema_validation_passed"])
        self.assertEqual(client.config.max_output_tokens, 512)

    def test_blocked_llm_response_falls_back_to_deterministic_decision(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        coverage = RetrievalCoverageReport(
            overall_score=1.0,
            covered_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="training loop",
                    support_status="covered",
                    matched_paths=["train.py"],
                )
            ],
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(text="", response_hash="sha256:empty", blocked_reason="provider_timeout_error"),
        ):
            provider = build_llm_decision_provider(config)
            decision = coverage_decision_with_model(coverage, decision_provider=provider)

        self.assertEqual(decision.decision, "proceed_to_analysis")
        self.assertEqual(decision.recommended_next, "analysis")

    def test_provider_supports_authoring_planner_schema(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        prompt = AgenticDecisionPrompt(
            node="authoring_planner",
            objective="plan method sections",
            inputs={"allowed_claim_ids": ["C1"]},
            fallback_decision={"sections": []},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(
                text='{"rationale":"Group verified claims.","sections":[{"heading":"Overview","claim_ids":["C1"],"evidence_ids":["E1"]}]}',
                response_hash="sha256:test",
            ),
        ) as complete:
            provider = build_llm_decision_provider(config)
            proposal = provider(prompt) if provider else None

        request = complete.call_args.args[1]
        self.assertEqual(request.prompt_template_id, "agentic_authoring_planner_decision_v1")
        self.assertEqual(request.schema_name, "AuthoringPlanProposal")
        self.assertEqual(proposal.sections[0].claim_ids, ["C1"])

    def test_provider_supports_evidence_sufficiency_schema(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        prompt = AgenticDecisionPrompt(
            node="evidence_sufficiency",
            objective="decide evidence sufficiency",
            inputs={"evidence_sufficiency_report": {"support_rate": 0.5}},
            fallback_decision={"decision": "proceed_with_exclusions"},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(
                text='{"decision":"return_to_analysis","recommended_next":"analysis","rationale":"Need better evidence.","focus_claim_ids":["C3"]}',
                response_hash="sha256:test",
            ),
        ) as complete:
            provider = build_llm_decision_provider(config)
            proposal = provider(prompt) if provider else None

        request = complete.call_args.args[1]
        self.assertEqual(request.prompt_template_id, "agentic_evidence_sufficiency_decision_v1")
        self.assertEqual(request.schema_name, "EvidenceSufficiencyProposal")
        self.assertEqual(proposal.recommended_next, "analysis")
        self.assertEqual(proposal.focus_claim_ids, ["C3"])

    def test_provider_supports_analysis_repair_router_schema(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        prompt = AgenticDecisionPrompt(
            node="analysis_repair_router",
            objective="decide analysis repair route",
            inputs={"analysis_repair_tasks": {"tasks": [{"claim_id": "C2"}]}},
            fallback_decision={"decision": "rescan_candidate_code"},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(
                text='{"decision":"rescan_candidate_code","recommended_next":"intake","rationale":"Need candidate evidence."}',
                response_hash="sha256:test",
            ),
        ) as complete:
            provider = build_llm_decision_provider(config)
            proposal = provider(prompt) if provider else None

        request = complete.call_args.args[1]
        self.assertEqual(request.prompt_template_id, "agentic_analysis_repair_router_decision_v1")
        self.assertEqual(request.schema_name, "AnalysisRepairRouterProposal")
        self.assertEqual(proposal.recommended_next, "intake")

    def test_provider_supports_figure_planner_schema(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)
        prompt = AgenticDecisionPrompt(
            node="figure_planner",
            objective="plan method figure",
            inputs={"allowed_stage_ids": ["S1"]},
            fallback_decision={"nodes": []},
        )

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), patch(
            "code2paper.agentic.llm_decision_provider.LLMClient.complete",
            autospec=True,
            return_value=LLMResponse(
                text='{"rationale":"Use one supported node.","nodes":[{"node_id":"N1","stage_id":"S1","evidence_ids":["E1"]}]}',
                response_hash="sha256:test",
            ),
        ) as complete:
            provider = build_llm_decision_provider(config)
            proposal = provider(prompt) if provider else None

        request = complete.call_args.args[1]
        self.assertEqual(request.prompt_template_id, "agentic_figure_planner_decision_v1")
        self.assertEqual(request.schema_name, "FigurePlanProposal")
        self.assertEqual(proposal.nodes[0].stage_id, "S1")

    def test_unknown_decision_node_returns_none(self) -> None:
        config = LLMConfig(provider=LLMProvider.OPENAI, model="gpt-test", cache=False)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            provider = build_llm_decision_provider(config)
            result = provider(
                AgenticDecisionPrompt(
                    node="unknown_node",
                    objective="unsupported",
                    inputs={},
                )
            )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
