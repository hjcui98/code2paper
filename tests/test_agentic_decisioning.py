from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decisioning import (
    AgenticDecisionPrompt,
    build_langchain_decision_provider,
    coverage_decision_trace,
    coverage_decision_with_model,
    load_decision_trace,
    revision_decision_trace,
    revision_decision_with_model,
    write_decision_trace,
)
from code2paper.agentic.retrieval import (
    CoverageItem,
    RetrievalCoverageReport,
    RetrievalRescanItem,
    RetrievalRescanOutcomeItem,
    RetrievalRescanPlan,
    RetrievalRescanReport,
)
from code2paper.agentic.revision_context import RevisionDecisionContext, RevisionIssue


class AgenticDecisioningTests(unittest.TestCase):
    def test_langchain_runnable_adapter_feeds_structured_prompt_to_model_decision(self) -> None:
        class FakeRunnable:
            def __init__(self) -> None:
                self.payload = {}

            def invoke(self, payload):
                self.payload = payload
                return (
                    '{"decision":"rescan_intake","recommended_next":"intake",'
                    '"rationale":"Runnable selected another retrieval pass.",'
                    '"recommended_queries":["scheduler implementation"]}'
                )

        runnable = FakeRunnable()
        provider = build_langchain_decision_provider(runnable)
        coverage = RetrievalCoverageReport(
            overall_score=0.8,
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

        decision = coverage_decision_with_model(
            coverage,
            retrieval_round=0,
            max_retrieval_rounds=1,
            decision_provider=provider,
        )

        self.assertEqual(runnable.payload["node"], "coverage_critic")
        self.assertIn("fallback_decision", runnable.payload)
        self.assertEqual(decision.recommended_next, "intake")
        self.assertIn("scheduler implementation", decision.recommended_queries)

    def test_langchain_runnable_adapter_falls_back_on_unstructured_output(self) -> None:
        class BadRunnable:
            def invoke(self, _payload):
                return "just write the paper"

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

        decision = coverage_decision_with_model(
            coverage,
            decision_provider=build_langchain_decision_provider(BadRunnable()),
        )

        self.assertEqual(decision.decision, "proceed_to_analysis")
        self.assertEqual(decision.recommended_next, "analysis")

    def test_model_can_request_targeted_rescan_within_allowed_routes(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.45,
            partial_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="optimizer schedule",
                    support_status="partial",
                    matched_paths=["train.py"],
                )
            ],
        )

        def provider(prompt: AgenticDecisionPrompt):
            self.assertEqual(prompt.node, "coverage_critic")
            self.assertIn("code evidence decides", " ".join(prompt.hard_rules))
            return {
                "decision": "rescan_intake",
                "recommended_next": "intake",
                "rationale": "Need the scheduler implementation before analysis.",
                "recommended_paths": ["optim.py"],
                "recommended_symbols": ["build_scheduler"],
            }

        decision = coverage_decision_with_model(
            coverage,
            retrieval_round=0,
            max_retrieval_rounds=1,
            decision_provider=provider,
        )

        self.assertEqual(decision.decision, "rescan_intake")
        self.assertEqual(decision.recommended_next, "intake")
        self.assertEqual(decision.coverage_score, 0.45)
        self.assertIn("optim.py", decision.recommended_paths)
        self.assertIn("build_scheduler", decision.recommended_symbols)
        self.assertIn("retrieval_coverage", decision.artifact_keys)

    def test_coverage_fallback_uses_retrieval_rescan_plan_hints(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.25,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="optimizer schedule",
                    support_status="missing",
                )
            ],
        )
        rescan_plan = RetrievalRescanPlan(
            coverage_score=0.25,
            items=[
                RetrievalRescanItem(
                    item_id="RS1",
                    source="coverage_gap",
                    priority="high",
                    query="scheduler implementation",
                    path="optim.py",
                    symbol="build_scheduler",
                    target_id="RT1",
                    reasons=["gap_status:missing"],
                )
            ],
            recommended_paths=["optim.py"],
            recommended_symbols=["build_scheduler"],
            recommended_queries=["scheduler implementation"],
        )

        decision, trace = coverage_decision_trace(
            coverage,
            retrieval_rescan_plan=rescan_plan,
            retrieval_rescan_report=RetrievalRescanReport(
                item_count=1,
                covered_items=0,
                missing_items=1,
                high_priority_missing_items=1,
                coverage_score=0.0,
                items=[
                    RetrievalRescanOutcomeItem(
                        item_id="RS1",
                        source="coverage_gap",
                        status="missing",
                        priority="high",
                        query="scheduler implementation",
                        path="optim.py",
                        symbol="build_scheduler",
                        target_id="RT1",
                        reasons=["rank:missing_coverage_target"],
                    )
                ],
            ),
            retrieval_round=0,
            max_retrieval_rounds=1,
        )

        self.assertEqual(decision.recommended_next, "intake")
        self.assertIn("optim.py", decision.recommended_paths)
        self.assertIn("build_scheduler", decision.recommended_symbols)
        self.assertIn("scheduler implementation", decision.recommended_queries)
        self.assertIn("retrieval_rescan_plan", decision.artifact_keys)
        self.assertIn("retrieval_rescan_report", decision.artifact_keys)
        self.assertIsNotNone(trace.prompt.inputs["retrieval_rescan_plan"])
        self.assertIsNotNone(trace.prompt.inputs["retrieval_rescan_report"])
        self.assertEqual(trace.prompt.inputs["retrieval_rescan_attention"]["high_priority_missing_items"], 1)
        self.assertEqual(trace.prompt.inputs["retrieval_rescan_attention"]["missing_high_priority_items"][0]["item_id"], "RS1")
        self.assertIn("retrieval_rescan_plan", trace.final_decision["artifact_keys"])
        self.assertIn("retrieval_rescan_report", trace.final_decision["artifact_keys"])
        self.assertIn("missing bounded retrieval items", decision.rationale)
        self.assertIn("high-priority", decision.rationale)

    def test_model_cannot_route_coverage_directly_to_rendering(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.3,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="training loop",
                    support_status="missing",
                )
            ],
        )

        decision = coverage_decision_with_model(
            coverage,
            retrieval_round=0,
            max_retrieval_rounds=1,
            decision_provider=lambda _prompt: {
                "decision": "skip_to_rendering",
                "recommended_next": "rendering",
                "rationale": "The story is clear enough.",
            },
        )

        self.assertEqual(decision.recommended_next, "intake")
        self.assertEqual(decision.decision, "rescan_intake")
        self.assertIn("Unsafe coverage route rejected", decision.rationale)

    def test_coverage_decision_trace_records_prompt_proposal_and_safe_final_route(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.3,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="training loop",
                    support_status="missing",
                )
            ],
        )

        decision, trace = coverage_decision_trace(
            coverage,
            retrieval_round=0,
            max_retrieval_rounds=1,
            decision_provider=lambda _prompt: {
                "decision": "skip_to_rendering",
                "recommended_next": "rendering",
                "rationale": "The story is clear enough.",
            },
        )

        self.assertEqual(decision.recommended_next, "intake")
        self.assertEqual(trace.node, "coverage_critic")
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertEqual(trace.prompt.fallback_decision["recommended_next"], "intake")
        self.assertEqual(trace.parsed_proposal["recommended_next"], "rendering")
        self.assertEqual(trace.final_decision["recommended_next"], "intake")
        self.assertTrue(any("rewritten" in note for note in trace.safety_notes))

    def test_decision_trace_round_trips_to_json(self) -> None:
        coverage = RetrievalCoverageReport(overall_score=1.0)
        _decision, trace = coverage_decision_trace(coverage)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "decision_trace.json"
            write_decision_trace(path, trace)
            loaded = load_decision_trace(path)

        self.assertEqual(loaded.mode, "agentic-decision-trace")
        self.assertEqual(loaded.provider_status, "deterministic_fallback")
        self.assertEqual(loaded.final_decision["recommended_next"], "analysis")

    def test_model_cannot_bypass_validation_before_rendering(self) -> None:
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/agentic-decisioning"))

        decision = revision_decision_with_model(
            state,
            decision_provider=lambda _prompt: {
                "decision": "rendering",
                "recommended_next": "rendering",
                "rationale": "Draft is fine.",
            },
        )

        self.assertEqual(decision.decision, "run_validation")
        self.assertEqual(decision.recommended_next, "validation")
        self.assertIn("Rendering cannot bypass validation", decision.rationale)

    def test_revision_decision_trace_records_validation_bypass_rewrite(self) -> None:
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/agentic-decisioning"))
        context = RevisionDecisionContext(
            blocked_reason="",
            issue_count=1,
            issues=[
                RevisionIssue(
                    source_artifact="fidelity",
                    category="claim",
                    message="Draft needs validation before rendering.",
                    recommended_next="authoring",
                )
            ],
            recommended_next="authoring",
        )

        decision, trace = revision_decision_trace(
            state,
            revision_context=context,
            decision_provider=lambda _prompt: {
                "decision": "rendering",
                "recommended_next": "rendering",
                "rationale": "Draft is fine.",
            },
        )

        self.assertEqual(decision.recommended_next, "validation")
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertEqual(trace.prompt.inputs["revision_decision_context"]["recommended_next"], "authoring")
        attention = trace.prompt.inputs["revision_validation_attention"]
        self.assertEqual(attention["recommended_next"], "authoring")
        self.assertEqual(attention["issue_count"], 1)
        self.assertEqual(attention["top_issues"][0]["source_artifact"], "fidelity")
        self.assertEqual(attention["top_issues"][0]["recommended_next"], "authoring")
        self.assertEqual(trace.parsed_proposal["recommended_next"], "rendering")
        self.assertEqual(trace.final_decision["recommended_next"], "validation")
        self.assertIn("Rendering is allowed only after validation", " ".join(trace.prompt.hard_rules))

    def test_revision_budget_terminal_gate_skips_model_provider(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/agentic-decisioning"),
            blocked_reason="fidelity_claim_validation_failed",
            max_authoring_revision_rounds=0,
        )

        def provider_must_not_run(_prompt):
            self.fail("terminal revision gates must not call the model provider")

        decision, trace = revision_decision_trace(state, decision_provider=provider_must_not_run)

        self.assertEqual(decision.recommended_next, "blocked")
        self.assertEqual(trace.provider_status, "deterministic_terminal_gate")
        self.assertIn("provider was not called", " ".join(trace.safety_notes))

    def test_zero_revision_budget_rejects_model_rewrite_after_successful_validation(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/agentic-decisioning"),
            artifacts={"validation_manifest": "validation.json"},
            max_authoring_revision_rounds=0,
        )

        decision = revision_decision_with_model(
            state,
            decision_provider=lambda _prompt: {
                "decision": "revise_authoring",
                "recommended_next": "authoring",
                "selected_stage": "authoring",
                "rationale": "Polish the already validated draft.",
            },
        )

        self.assertEqual(decision.recommended_next, "rendering")
        self.assertIn("budget exhausted", decision.rationale)

    def test_model_cannot_rewrite_when_block_requires_more_evidence(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/agentic-decisioning"),
            blocked_reason="missing_evidence_for_claim",
            artifacts={"validation_manifest": "validation.json"},
            max_evidence_revision_rounds=1,
        )

        decision = revision_decision_with_model(
            state,
            decision_provider=lambda _prompt: {
                "decision": "revise_authoring",
                "recommended_next": "authoring",
                "rationale": "Rewrite around the missing support.",
            },
        )

        self.assertEqual(decision.decision, "return_to_analysis")
        self.assertEqual(decision.recommended_next, "analysis")
        self.assertIn("Evidence-related blocks", decision.rationale)


if __name__ == "__main__":
    unittest.main()
