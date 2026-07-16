from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.decision_policy import (
    build_agentic_decision_policy,
    hard_rule_texts,
    load_agentic_decision_policy,
    write_agentic_decision_policy,
)
from code2paper.agentic.decisioning import coverage_decision_trace
from code2paper.agentic.retrieval import RetrievalCoverageReport


class AgenticDecisionPolicyTests(unittest.TestCase):
    def test_policy_declares_model_decision_boundaries(self) -> None:
        policy = build_agentic_decision_policy()
        nodes = {node.node: node for node in policy.node_policies}

        self.assertEqual(policy.mode, "agentic-decision-policy")
        self.assertIn("coverage_critic", nodes)
        self.assertIn("analysis_repair_router", nodes)
        self.assertIn("evidence_sufficiency", nodes)
        self.assertIn("authoring_planner", nodes)
        self.assertIn("figure_planner", nodes)
        self.assertIn("revision_router", nodes)
        self.assertTrue(nodes["coverage_critic"].model_may_propose)
        self.assertEqual(nodes["coverage_critic"].allowed_next_nodes, ["intake", "analysis", "blocked"])
        self.assertIn("rendering", nodes["coverage_critic"].forbidden_next_nodes)
        self.assertIn("retrieval_rescan_plan", nodes["coverage_critic"].required_context_artifacts)
        self.assertIn("retrieval_rescan_report", nodes["coverage_critic"].required_context_artifacts)
        self.assertIn("retrieval_rescan_attention", nodes["coverage_critic"].required_prompt_inputs)
        self.assertTrue(nodes["analysis_repair_router"].model_may_propose)
        self.assertEqual(nodes["analysis_repair_router"].allowed_next_nodes, ["intake", "evidence", "blocked"])
        self.assertIn("analysis_repair_tasks", nodes["analysis_repair_router"].required_context_artifacts)
        self.assertIn("analysis_repair_attention", nodes["analysis_repair_router"].required_prompt_inputs)
        self.assertIn("analysis_repair_router_decision_trace", nodes["analysis_repair_router"].required_gate_artifacts)
        self.assertTrue(nodes["evidence_sufficiency"].model_may_propose)
        self.assertEqual(nodes["evidence_sufficiency"].allowed_next_nodes, ["grounding", "analysis", "blocked"])
        self.assertIn("evidence_sufficiency_attention", nodes["evidence_sufficiency"].required_prompt_inputs)
        self.assertIn("evidence_sufficiency_decision_trace", nodes["evidence_sufficiency"].required_gate_artifacts)
        self.assertTrue(nodes["authoring_planner"].model_may_propose)
        self.assertIn("authoring_evidence_attention", nodes["authoring_planner"].required_prompt_inputs)
        self.assertIn("authoring_plan_decision_trace", nodes["authoring_planner"].required_gate_artifacts)
        self.assertTrue(nodes["figure_planner"].model_may_propose)
        self.assertEqual(nodes["figure_planner"].allowed_next_nodes, ["invariant_audit", "blocked"])
        self.assertIn("figure_evidence_attention", nodes["figure_planner"].required_prompt_inputs)
        self.assertIn("figure_plan_decision_trace", nodes["figure_planner"].required_gate_artifacts)
        self.assertIn("rendering", nodes["figure_planner"].forbidden_next_nodes)
        self.assertTrue(nodes["revision_router"].safety_merge_required)
        self.assertIn("figure_planner", nodes["revision_router"].allowed_next_nodes)
        self.assertIn("revision_validation_attention", nodes["revision_router"].required_prompt_inputs)
        self.assertIn("validation_manifest", nodes["revision_router"].required_gate_artifacts)
        self.assertFalse(nodes["invariant_audit"].model_may_propose)

    def test_decision_prompt_uses_policy_hard_rules(self) -> None:
        coverage = RetrievalCoverageReport(overall_score=1.0, covered_targets=1)
        _decision, trace = coverage_decision_trace(coverage)

        self.assertEqual(trace.prompt.hard_rules, hard_rule_texts())
        self.assertIn("Rendering is allowed only after validation", " ".join(trace.prompt.hard_rules))

    def test_model_decision_policies_require_stage_tool_guidance(self) -> None:
        policy = build_agentic_decision_policy()

        for node in policy.node_policies:
            if node.model_may_propose:
                with self.subTest(node=node.node):
                    self.assertIn("stage_tool_guidance", node.required_prompt_inputs)

    def test_policy_round_trips_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_decision_policy.json"

            write_agentic_decision_policy(path, build_agentic_decision_policy())
            loaded = load_agentic_decision_policy(path)

        self.assertEqual(loaded.mode, "agentic-decision-policy")
        self.assertIn("claim_verification", loaded.invariant_artifacts)


if __name__ == "__main__":
    unittest.main()
