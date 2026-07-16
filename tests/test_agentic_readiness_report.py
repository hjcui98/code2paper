from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decision_policy import build_agentic_decision_policy
from code2paper.agentic.readiness_report import (
    build_run_readiness_report,
    load_run_readiness_report,
    write_run_readiness_report,
)


class AgenticReadinessReportTests(unittest.TestCase):
    def test_report_passes_for_minimal_successful_evidence_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "agentic_decision_policy": _write_json(root, "policy.json", {"mode": "policy"}),
                "agentic_graph_catalog": _write_json(root, "graph.json", {"mode": "graph"}),
                "agentic_tool_catalog": _write_json(root, "tools.json", {"mode": "tools"}),
                "agentic_langchain_tool_manifest": _write_json(root, "langchain_tools.json", {"mode": "langchain-tools"}),
                "agentic_architecture_manifest": _write_json(root, "architecture.json", {"mode": "architecture"}),
                "agentic_contract_audit": _write_json(root, "contract_audit.json", {"passed": True}),
                "evidence": _write_json(root, "evidence.json", {"project_id": "demo"}),
                "claims": _write_json(root, "claims.json", {"claims": []}),
                "claim_verification": _write_json(root, "claim_verification.json", {"claims": []}),
                "evidence_sufficiency_report": _write_json(root, "evidence_sufficiency_report.json", {"hard_gate_passed": True}),
                "evidence_sufficiency_decision_trace": _write_json(
                    root,
                    "evidence_sufficiency_trace.json",
                    {"node": "evidence_sufficiency", "final_decision": {"recommended_next": "grounding"}},
                ),
                "traceability_ledger": _write_json(root, "ledger.json", {"hard_gate_passed": True}),
                "agentic_invariant_audit": _write_json(root, "audit.json", {"passed": True, "blocking_failures": 0}),
            }
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        self.assertTrue(report.passed)
        self.assertEqual(report.blocking_failures, 0)
        self.assertEqual(report.recommended_actions, ["agentic_run_is_ready_for_review"])

    def test_report_requires_trace_for_coverage_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["coverage_critic_decision"] = _write_json(root, "coverage_decision.json", {"next_node": "analysis"})
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("coverage critic decision", check.message)

    def test_report_requires_coverage_trace_attention_for_high_priority_rescan_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["retrieval_coverage"] = _write_json(root, "coverage.json", {"overall_score": 0.2})
            artifacts["retrieval_decision_context"] = _write_json(root, "retrieval_context.json", {"coverage_score": 0.2})
            artifacts["retrieval_rescan_plan"] = _write_json(root, "rescan_plan.json", {"items": []})
            artifacts["retrieval_rescan_report"] = _write_json(
                root,
                "rescan_report.json",
                {
                    "missing_items": 1,
                    "high_priority_missing_items": 1,
                    "items": [{"item_id": "RS1", "status": "missing", "priority": "high"}],
                },
            )
            artifacts["coverage_critic_decision"] = _write_json(root, "coverage_decision.json", {"recommended_next": "intake"})
            artifacts["coverage_critic_decision_trace"] = _write_json(
                root,
                "coverage_trace.json",
                _decision_trace("coverage_critic", {"recommended_next": "intake"}),
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("coverage critic trace does not expose high-priority rescan attention", check.message)

    def test_report_requires_policy_prompt_inputs_in_decision_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["agentic_decision_policy"] = _write_json(
                root,
                "policy.json",
                build_agentic_decision_policy().model_dump(mode="json"),
            )
            artifacts["coverage_critic_decision"] = _write_json(root, "coverage_decision.json", {"recommended_next": "analysis"})
            artifacts["coverage_critic_decision_trace"] = _write_json(
                root,
                "coverage_trace.json",
                _decision_trace("coverage_critic", {"recommended_next": "analysis"}),
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("coverage_critic decision trace missing policy prompt inputs", check.message)
        self.assertIn("retrieval_rescan_attention", check.message)

    def test_report_requires_policy_hard_rules_in_decision_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            policy = build_agentic_decision_policy()
            required_inputs = next(node.required_prompt_inputs for node in policy.node_policies if node.node == "coverage_critic")
            trace = _decision_trace("coverage_critic", {"recommended_next": "analysis"})
            trace["prompt"]["inputs"] = {input_key: {} for input_key in required_inputs}
            artifacts = _base_artifacts(root)
            artifacts["agentic_decision_policy"] = _write_json(root, "policy.json", policy.model_dump(mode="json"))
            artifacts["coverage_critic_decision"] = _write_json(root, "coverage_decision.json", {"recommended_next": "analysis"})
            artifacts["coverage_critic_decision_trace"] = _write_json(root, "coverage_trace.json", trace)
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("coverage_critic decision trace missing policy hard rules", check.message)

    def test_report_requires_passing_contract_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["agentic_contract_audit"] = _write_json(root, "contract_audit.json", {"passed": False})
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "orchestration_catalogs")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("agentic_contract_audit did not pass", check.message)

    def test_report_requires_agentic_architecture_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts.pop("agentic_architecture_manifest")
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "orchestration_catalogs")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("agentic_architecture_manifest", check.message)

    def test_report_requires_retrieval_rescan_report_with_retrieval_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["retrieval_coverage"] = _write_json(root, "coverage.json", {"overall_score": 0.3})
            artifacts["retrieval_decision_context"] = _write_json(root, "retrieval_context.json", {"coverage_score": 0.3})
            artifacts["retrieval_rescan_plan"] = _write_json(root, "rescan_plan.json", {"items": []})
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "retrieval_decision_context")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("retrieval_rescan_report", check.message)

    def test_report_requires_retrieval_strategy_manifest_with_retrieval_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["retrieval_coverage"] = _write_json(root, "coverage.json", {"overall_score": 0.3})
            artifacts["symbol_index"] = _write_json(root, "symbol_index.json", {"indexed_symbols": 1})
            artifacts["retrieval_decision_context"] = _write_json(root, "retrieval_context.json", {"coverage_score": 0.3})
            artifacts["retrieval_rescan_plan"] = _write_json(root, "rescan_plan.json", {"items": []})
            artifacts["retrieval_rescan_report"] = _write_json(root, "rescan_report.json", {"items": []})
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "retrieval_decision_context")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("retrieval_strategy_manifest", check.message)

    def test_report_requires_authoring_context_for_method_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["text_md"] = _write_text(root, "method.md", "Method text")
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "authoring_context_contract")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("authoring_context", check.message)

    def test_report_requires_text_claims_to_follow_authoring_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            plan = {
                "hard_gate_passed": True,
                "sections": [{"section_id": "AP-S1", "claim_ids": ["C1"], "evidence_ids": ["E1"], "caveat_required": False}],
            }
            artifacts["authoring_context"] = _write_json(root, "authoring_context.json", {"hard_gate_passed": True})
            artifacts["authoring_constraints"] = _write_json(root, "authoring_constraints.json", {"excluded_claim_ids": []})
            artifacts["authoring_plan"] = _write_json(root, "authoring_plan.json", plan)
            artifacts["authoring_plan_decision_trace"] = _write_json(
                root,
                "authoring_plan_trace.json",
                _decision_trace("authoring_planner", plan),
            )
            artifacts["text_md"] = _write_text(root, "method.md", "Method text")
            artifacts["text_claims"] = _write_json(
                root,
                "text_claims.json",
                {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C2"], "evidence_span_ids": ["E2"]}]},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "authoring_context_contract")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("text claim ids outside authoring plan: C2", check.message)
        self.assertIn("text evidence ids outside authoring plan: E2", check.message)

    def test_report_requires_trace_for_authoring_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["authoring_plan"] = _write_json(root, "authoring_plan.json", {"sections": []})
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("authoring plan", check.message)

    def test_report_rejects_stale_authoring_plan_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            plan = {
                "hard_gate_passed": True,
                "sections": [{"section_id": "AP-S1", "claim_ids": ["C1"], "evidence_ids": ["E1"], "caveat_required": False}],
            }
            stale_plan = {
                "hard_gate_passed": True,
                "sections": [{"section_id": "AP-S1", "claim_ids": ["C404"], "evidence_ids": ["E1"], "caveat_required": False}],
            }
            artifacts["authoring_plan"] = _write_json(root, "authoring_plan.json", plan)
            artifacts["authoring_plan_decision_trace"] = _write_json(
                root,
                "authoring_plan_trace.json",
                _decision_trace("authoring_planner", stale_plan),
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("authoring_plan decision trace final_decision does not match", check.message)

    def test_report_requires_trace_for_figure_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["figure_plan"] = _write_json(
                root,
                "method_overview.intent.json",
                {"hard_gate_passed": True, "nodes": [{"node_id": "N1", "evidence_ids": ["E1"]}], "edges": []},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("figure plan", check.message)

    def test_report_rejects_stale_figure_plan_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            plan = {
                "hard_gate_passed": True,
                "nodes": [{"node_id": "N1", "stage_id": "S1", "claim_ids": ["C1"], "evidence_ids": ["E1"]}],
                "edges": [],
            }
            stale_plan = {
                "hard_gate_passed": True,
                "nodes": [{"node_id": "N1", "stage_id": "S1", "claim_ids": ["C1"], "evidence_ids": ["E404"]}],
                "edges": [],
            }
            artifacts["figure_plan"] = _write_json(root, "method_overview.intent.json", plan)
            artifacts["figure_plan_decision_trace"] = _write_json(
                root,
                "method_overview.intent.decision_trace.json",
                _decision_trace("figure_planner", stale_plan),
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("figure_plan decision trace final_decision does not match", check.message)

    def test_report_requires_analysis_repair_tasks_for_repair_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["evidence_repair_focus"] = _write_json(
                root,
                "repair_focus.json",
                {"focus_claim_ids": ["C2"], "claim_targets": [{"claim_id": "C2", "candidates": []}]},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "analysis_repair_tasks_contract")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("analysis repair tasks", check.message)

    def test_report_accepts_analysis_repair_tasks_covering_focus_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["evidence_repair_focus"] = _write_json(
                root,
                "repair_focus.json",
                {"focus_claim_ids": ["C2"], "claim_targets": [{"claim_id": "C2", "candidates": []}]},
            )
            artifacts["analysis_repair_tasks"] = _write_json(
                root,
                "repair_tasks.json",
                {"tasks": [{"claim_id": "C2", "candidates": [{"path": "src/model.py", "evidence_ids": ["E1"]}]}]},
            )
            artifacts["analysis_repair_router_decision"] = _write_json(
                root,
                "repair_router_decision.json",
                {"decision": "reassess_existing_repair_task_evidence", "recommended_next": "evidence"},
            )
            artifacts["analysis_repair_router_decision_trace"] = _write_json(
                root,
                "repair_router_trace.json",
                {"node": "analysis_repair_router", "final_decision": {"recommended_next": "evidence"}},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "analysis_repair_tasks_contract")
        self.assertTrue(report.passed)
        self.assertTrue(check.passed)

    def test_report_requires_router_decision_for_analysis_repair_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["evidence_repair_focus"] = _write_json(
                root,
                "repair_focus.json",
                {"focus_claim_ids": ["C2"], "claim_targets": [{"claim_id": "C2", "candidates": []}]},
            )
            artifacts["analysis_repair_tasks"] = _write_json(
                root,
                "repair_tasks.json",
                {"tasks": [{"claim_id": "C2", "candidates": [{"path": "src/model.py", "evidence_ids": ["E1"]}]}]},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        check = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(check.passed)
        self.assertIn("analysis repair tasks", check.message)

    def test_report_requires_router_trace_for_analysis_repair_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = _base_artifacts(root)
            artifacts["evidence_repair_focus"] = _write_json(
                root,
                "repair_focus.json",
                {"focus_claim_ids": ["C2"], "claim_targets": [{"claim_id": "C2", "candidates": []}]},
            )
            artifacts["analysis_repair_tasks"] = _write_json(
                root,
                "repair_tasks.json",
                {"tasks": [{"claim_id": "C2", "candidates": [{"path": "src/model.py", "evidence_ids": ["E1"]}]}]},
            )
            artifacts["analysis_repair_router_decision"] = _write_json(
                root,
                "repair_router_decision.json",
                {"decision": "reassess_existing_repair_task_evidence", "recommended_next": "evidence"},
            )
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=artifacts)

            report = build_run_readiness_report(state)

        contract = _check(report, "analysis_repair_tasks_contract")
        traces = _check(report, "agentic_decision_traces")
        self.assertFalse(report.passed)
        self.assertFalse(contract.passed)
        self.assertFalse(traces.passed)
        self.assertIn("router decision trace", contract.message)

    def test_report_round_trips_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=root, out_root=root / "out", artifacts=_base_artifacts(root))
            path = root / "agentic_run_readiness_report.json"

            write_run_readiness_report(path, build_run_readiness_report(state))
            loaded = load_run_readiness_report(path)

        self.assertTrue(loaded.passed)
        self.assertEqual(loaded.mode, "agentic-run-readiness-report")


def _base_artifacts(root: Path) -> dict[str, str]:
    return {
        "agentic_decision_policy": _write_json(root, "policy.json", {"mode": "policy"}),
        "agentic_graph_catalog": _write_json(root, "graph.json", {"mode": "graph"}),
        "agentic_tool_catalog": _write_json(root, "tools.json", {"mode": "tools"}),
        "agentic_langchain_tool_manifest": _write_json(root, "langchain_tools.json", {"mode": "langchain-tools"}),
        "agentic_architecture_manifest": _write_json(root, "architecture.json", {"mode": "architecture"}),
        "agentic_contract_audit": _write_json(root, "contract_audit.json", {"passed": True}),
        "evidence": _write_json(root, "evidence.json", {"project_id": "demo"}),
        "claims": _write_json(root, "claims.json", {"claims": []}),
        "claim_verification": _write_json(root, "claim_verification.json", {"claims": []}),
        "evidence_sufficiency_report": _write_json(root, "evidence_sufficiency_report.json", {"hard_gate_passed": True}),
        "evidence_sufficiency_decision_trace": _write_json(
            root,
            "evidence_sufficiency_trace.json",
            {"node": "evidence_sufficiency", "final_decision": {"recommended_next": "grounding"}},
        ),
        "traceability_ledger": _write_json(root, "ledger.json", {"hard_gate_passed": True}),
        "agentic_invariant_audit": _write_json(root, "audit.json", {"passed": True, "blocking_failures": 0}),
    }


def _write_json(root: Path, name: str, payload: dict[str, object]) -> str:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _write_text(root: Path, name: str, text: str) -> str:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _decision_trace(node: str, final_decision: dict[str, object]) -> dict[str, object]:
    return {
        "mode": "agentic-decision-trace",
        "node": node,
        "provider_status": "deterministic_fallback",
        "prompt": {"node": node, "objective": "test", "hard_rules": [], "inputs": {}, "fallback_decision": {}},
        "provider_payload": {},
        "parsed_proposal": {},
        "final_decision": final_decision,
        "safety_notes": [],
    }


def _check(report, name: str):
    for check in report.checks:
        if check.name == name:
            return check
    raise AssertionError(f"missing check: {name}")


if __name__ == "__main__":
    unittest.main()
