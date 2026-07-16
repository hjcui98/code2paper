from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evaluation_report import (
    build_run_evaluation_report,
    load_run_evaluation_report,
    write_run_evaluation_report,
)


class AgenticEvaluationReportTests(unittest.TestCase):
    def test_report_derives_benchmark_metrics_from_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "retrieval_coverage": _write_json(
                    root,
                    "coverage.json",
                    {
                        "overall_score": 0.75,
                        "target_coverage_score": 0.75,
                        "legacy_alignment_score": 0.25,
                        "score_basis": "retrieval_targets",
                    },
                ),
                "retrieval_rescan_plan": _write_json(
                    root,
                    "rescan_plan.json",
                    {
                        "items": [
                            {"item_id": "RS1", "source": "coverage_gap", "path": "src/config.py"},
                            {"item_id": "RS2", "source": "analysis_repair_task", "path": "src/encoder.py"},
                        ]
                    },
                ),
                "retrieval_rescan_report": _write_json(
                    root,
                    "rescan_report.json",
                    {
                        "covered_items": 1,
                        "partial_items": 0,
                        "missing_items": 1,
                        "high_priority_missing_items": 1,
                        "coverage_score": 0.5,
                    },
                ),
                "retrieval_strategy_manifest": _write_json(
                    root,
                    "retrieval_strategy.json",
                    {
                        "coverage_score_basis": "retrieval_targets",
                        "evidence_guardrails": [
                            "retrieval_can_prioritize_candidates_but_cannot_write_claims",
                            "evidence_freeze_decides_claim_support",
                        ],
                        "summary_uses": ["code_evidence_alignment", "next_intake_focus"],
                    },
                ),
                "claim_verification": _write_json(
                    root,
                    "claim_verification.json",
                    {
                        "claims": [
                            {"claim_id": "c1", "support_status": "supported"},
                            {"claim_id": "c2", "support_status": "partial"},
                            {"claim_id": "c3", "support_status": "unsupported"},
                        ]
                    },
                ),
                "evidence_sufficiency_report": _write_json(root, "evidence_sufficiency.json", {"support_rate": 0.5}),
                "evidence_repair_focus": _write_json(
                    root,
                    "evidence_repair_focus.json",
                    {
                        "focus_claim_ids": ["c3"],
                        "claim_targets": [
                            {
                                "claim_id": "c3",
                                "claim_query": "c3: unsupported claim",
                                "candidates": [
                                    {"path": "src/encoder.py", "symbol": "Encoder.forward"},
                                    {"path": "src/config.py", "symbol": "load_config"},
                                ],
                            }
                        ],
                    },
                ),
                "analysis_repair_tasks": _write_json(
                    root,
                    "analysis_repair_tasks.json",
                    {
                        "tasks": [
                            {
                                "claim_id": "c3",
                                "candidates": [
                                    {"path": "src/encoder.py", "evidence_ids": ["E1"]},
                                    {"path": "src/config.py", "evidence_ids": []},
                                ],
                            }
                        ]
                    },
                ),
                "validation_manifest": _write_json(root, "validation_manifest.json", {"status": "success"}),
                "traceability_ledger": _write_json(root, "ledger.json", {"hard_gate_passed": True}),
                "agentic_invariant_audit": _write_json(root, "audit.json", {"passed": True}),
                "agentic_run_readiness_report": _write_json(root, "readiness.json", {"passed": True}),
            }
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts=artifacts,
                loop_counters={"retrieval": 2, "evidence_revision": 1, "revision": 1},
            )

            report = build_run_evaluation_report(state)

        self.assertEqual(report.mode, "agentic-run-evaluation-report")
        self.assertEqual(report.status, "success")
        self.assertEqual(report.evidence_coverage_score, 0.75)
        self.assertEqual(report.evidence_target_coverage_score, 0.75)
        self.assertEqual(report.legacy_alignment_score, 0.25)
        self.assertEqual(report.evidence_coverage_basis, "retrieval_targets")
        self.assertEqual(report.evidence_support_rate, 0.5)
        self.assertEqual(report.evidence_repair_focus_claims, 1)
        self.assertEqual(report.evidence_repair_candidate_count, 2)
        self.assertEqual(report.evidence_repair_task_count, 1)
        self.assertEqual(report.evidence_repair_tasks_with_existing_evidence, 1)
        self.assertEqual(report.evidence_repair_candidates_with_existing_evidence, 1)
        self.assertEqual(report.unsupported_claim_rate, 0.3333)
        self.assertEqual(report.partial_claim_rate, 0.3333)
        self.assertEqual(report.retrieval_loops, 2)
        self.assertEqual(report.retrieval_rescan_plan_items, 2)
        self.assertEqual(report.retrieval_rescan_covered_items, 1)
        self.assertEqual(report.retrieval_rescan_missing_items, 1)
        self.assertEqual(report.retrieval_rescan_high_priority_missing_items, 1)
        self.assertEqual(report.retrieval_rescan_coverage_score, 0.5)
        self.assertEqual(report.retrieval_strategy_guardrails, 2)
        self.assertEqual(report.retrieval_strategy_summary_uses, 2)
        self.assertEqual(report.retrieval_strategy_coverage_basis, "retrieval_targets")
        self.assertEqual(report.evidence_revision_loops, 1)
        self.assertEqual(report.revision_loops, 1)
        self.assertTrue(report.validation_passed)
        self.assertTrue(report.invariant_audit_passed)
        self.assertTrue(report.readiness_passed)
        self.assertTrue(report.traceability_passed)
        metric_values = {metric.name: metric.value for metric in report.metrics}
        self.assertEqual(metric_values["retrieval_strategy_guardrails"], 2)
        self.assertEqual(metric_values["retrieval_strategy_summary_uses"], 2)
        self.assertIn("improve_author_intent_retrieval_coverage", report.recommended_actions)
        self.assertIn("continue_high_priority_rescan_for_missing_evidence", report.recommended_actions)
        self.assertIn("continue_bounded_rescan_for_missing_rescan_items", report.recommended_actions)
        self.assertIn("remove_or_retrieve_evidence_for_unsupported_claims", report.recommended_actions)
        self.assertIn("reassess_existing_repair_task_evidence_before_rescan", report.recommended_actions)

    def test_report_marks_missing_core_metrics_for_benchmark_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=root, out_root=root / "out", blocked_reason="method_text_missing")

            report = build_run_evaluation_report(state)

        metric_values = {metric.name: metric.value for metric in report.metrics}
        self.assertEqual(report.status, "blocked")
        self.assertEqual(metric_values["evidence_coverage_score"], "missing")
        self.assertEqual(metric_values["evidence_target_coverage_score"], "missing")
        self.assertEqual(metric_values["legacy_alignment_score"], "missing")
        self.assertEqual(metric_values["evidence_support_rate"], "missing")
        self.assertEqual(metric_values["unsupported_claim_rate"], "missing")
        self.assertEqual(metric_values["retrieval_strategy_guardrails"], "missing")
        self.assertIn("inspect_blocked_reason_and_router_trace", report.recommended_actions)
        self.assertIn("emit_retrieval_coverage_for_benchmark_comparison", report.recommended_actions)
        self.assertIn("emit_retrieval_strategy_manifest_for_benchmark_comparison", report.recommended_actions)

    def test_report_round_trips_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "retrieval_decision_context": _write_json(root, "retrieval_context.json", {"coverage_score": 1.0}),
                    "claim_verification": _write_json(root, "claim_verification.json", {"claims": []}),
                },
            )
            path = root / "agentic_run_evaluation_report.json"

            write_run_evaluation_report(path, build_run_evaluation_report(state))
            loaded = load_run_evaluation_report(path)

        self.assertEqual(loaded.evidence_coverage_score, 1.0)
        self.assertEqual(loaded.mode, "agentic-run-evaluation-report")


def _write_json(root: Path, name: str, payload: dict[str, object]) -> str:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    unittest.main()
