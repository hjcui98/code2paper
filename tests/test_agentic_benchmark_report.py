from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.benchmark_report import (
    AgenticBenchmarkRunSpec,
    build_agentic_benchmark_report,
    load_agentic_benchmark_report,
    write_agentic_benchmark_report,
)


class AgenticBenchmarkReportTests(unittest.TestCase):
    def test_benchmark_prefers_evidence_safe_variant_over_unsupported_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            agentic = _write_eval(
                root,
                "agentic.json",
                {
                    "status": "success",
                    "evidence_coverage_score": 0.9,
                    "evidence_support_rate": 0.9,
                    "unsupported_claim_rate": 0.0,
                    "partial_claim_rate": 0.1,
                    "retrieval_loops": 1,
                    "retrieval_rescan_plan_items": 2,
                    "retrieval_rescan_covered_items": 2,
                    "retrieval_rescan_missing_items": 0,
                    "retrieval_rescan_high_priority_missing_items": 0,
                    "retrieval_rescan_coverage_score": 1.0,
                    "evidence_revision_loops": 1,
                    "evidence_repair_focus_claims": 1,
                    "evidence_repair_candidate_count": 2,
                    "evidence_repair_task_count": 1,
                    "evidence_repair_tasks_with_existing_evidence": 1,
                    "evidence_repair_candidates_with_existing_evidence": 1,
                    "revision_loops": 0,
                    "validation_passed": True,
                    "contract_audit_passed": True,
                    "invariant_audit_passed": True,
                    "readiness_passed": True,
                    "traceability_passed": True,
                },
            )
            fixed = _write_eval(
                root,
                "fixed.json",
                {
                    "status": "success",
                    "evidence_coverage_score": 1.0,
                    "evidence_support_rate": 0.4,
                    "unsupported_claim_rate": 0.25,
                    "partial_claim_rate": 0.0,
                    "retrieval_loops": 0,
                    "retrieval_rescan_plan_items": 1,
                    "retrieval_rescan_covered_items": 0,
                    "retrieval_rescan_missing_items": 1,
                    "retrieval_rescan_high_priority_missing_items": 1,
                    "retrieval_rescan_coverage_score": 0.0,
                    "evidence_revision_loops": 0,
                    "evidence_repair_focus_claims": 0,
                    "evidence_repair_candidate_count": 0,
                    "evidence_repair_task_count": 1,
                    "evidence_repair_tasks_with_existing_evidence": 0,
                    "evidence_repair_candidates_with_existing_evidence": 0,
                    "revision_loops": 0,
                    "validation_passed": True,
                    "contract_audit_passed": False,
                    "invariant_audit_passed": True,
                    "readiness_passed": True,
                    "traceability_passed": True,
                },
            )

            report = build_agentic_benchmark_report(
                [
                    AgenticBenchmarkRunSpec(path=agentic, variant="agentic", label="agentic-1"),
                    AgenticBenchmarkRunSpec(path=fixed, variant="fixed", label="fixed-1"),
                ]
            )

        self.assertEqual(report.run_count, 2)
        self.assertEqual(report.best_variant, "agentic")
        fixed_summary = next(summary for summary in report.variant_summaries if summary.variant == "fixed")
        self.assertIn("unsupported_claims_present", fixed_summary.risk_flags)
        self.assertIn("weak_evidence_support_present", fixed_summary.risk_flags)
        self.assertEqual(fixed_summary.avg_evidence_support_rate, 0.4)
        self.assertEqual(fixed_summary.avg_evidence_revision_loops, 0.0)
        self.assertEqual(fixed_summary.contract_audit_pass_rate, 0.0)
        self.assertIn("contract_audit_failures_present", fixed_summary.risk_flags)
        self.assertEqual(fixed_summary.avg_retrieval_rescan_plan_items, 1.0)
        self.assertEqual(fixed_summary.avg_retrieval_rescan_missing_items, 1.0)
        self.assertEqual(fixed_summary.avg_retrieval_rescan_high_priority_missing_items, 1.0)
        self.assertIn("rescan_items_still_missing", fixed_summary.risk_flags)
        self.assertIn("high_priority_rescan_items_missing", fixed_summary.risk_flags)
        self.assertEqual(fixed_summary.avg_evidence_repair_focus_claims, 0.0)
        self.assertEqual(fixed_summary.avg_evidence_repair_candidate_count, 0.0)
        self.assertEqual(fixed_summary.avg_evidence_repair_task_count, 1.0)
        self.assertIn("repair_tasks_need_rescan", fixed_summary.risk_flags)
        self.assertIn("fixed:repair_or_retrieve_evidence_for_unsupported_claims", report.recommended_actions)
        self.assertIn("fixed:improve_evidence_support_before_authoring", report.recommended_actions)
        self.assertIn("fixed:rescan_candidate_code_for_repair_tasks", report.recommended_actions)
        self.assertIn("fixed:prioritize_high_priority_rescan_items", report.recommended_actions)
        self.assertIn("fixed:continue_bounded_retrieval_for_missing_rescan_items", report.recommended_actions)
        self.assertIn("fixed:repair_agentic_contract_drift_before_benchmarking", report.recommended_actions)

    def test_benchmark_round_trips_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = _write_eval(
                root,
                "agentic.json",
                {
                    "status": "blocked",
                    "blocked_reason": "invariant_audit_failed",
                    "evidence_coverage_score": None,
                    "evidence_support_rate": None,
                    "unsupported_claim_rate": None,
                    "partial_claim_rate": None,
                    "retrieval_loops": 0,
                    "retrieval_rescan_plan_items": 0,
                    "retrieval_rescan_covered_items": 0,
                    "retrieval_rescan_missing_items": 0,
                    "retrieval_rescan_high_priority_missing_items": 0,
                    "retrieval_rescan_coverage_score": None,
                    "evidence_revision_loops": 0,
                    "evidence_repair_focus_claims": 0,
                    "evidence_repair_candidate_count": 0,
                    "evidence_repair_task_count": 0,
                    "evidence_repair_tasks_with_existing_evidence": 0,
                    "evidence_repair_candidates_with_existing_evidence": 0,
                    "revision_loops": 0,
                    "validation_passed": None,
                    "contract_audit_passed": False,
                    "invariant_audit_passed": False,
                    "readiness_passed": False,
                    "traceability_passed": False,
                },
            )
            output = root / "agentic_benchmark_report.json"

            write_agentic_benchmark_report(
                output,
                build_agentic_benchmark_report([AgenticBenchmarkRunSpec(path=path, variant="agentic")]),
            )
            loaded = load_agentic_benchmark_report(output)

        self.assertEqual(loaded.mode, "agentic-benchmark-report")
        self.assertEqual(loaded.run_count, 1)
        self.assertEqual(loaded.variant_summaries[0].blocked_rate, 1.0)
        self.assertIn("traceability_failures_present", loaded.variant_summaries[0].risk_flags)

    def test_benchmark_uses_adjacent_completion_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            complete = _write_eval_case(root, "complete", {"status": "success"}, {"status": "complete", "complete": True})
            incomplete = _write_eval_case(
                root,
                "incomplete",
                {"status": "success"},
                {"status": "incomplete", "complete": False, "missing_deliverables": ["method_text", "final_package"]},
            )

            report = build_agentic_benchmark_report(
                [
                    AgenticBenchmarkRunSpec(path=complete, variant="complete"),
                    AgenticBenchmarkRunSpec(path=incomplete, variant="incomplete"),
                ]
            )

        complete_run = next(run for run in report.runs if run.variant == "complete")
        incomplete_summary = next(summary for summary in report.variant_summaries if summary.variant == "incomplete")
        self.assertTrue(complete_run.completion_complete)
        self.assertEqual(incomplete_summary.completion_pass_rate, 0.0)
        self.assertIn("incomplete_runs_present", incomplete_summary.risk_flags)
        self.assertIn("incomplete:complete_agentic_final_deliverables_before_benchmarking", report.recommended_actions)


def _write_eval(root: Path, name: str, payload: dict[str, object]) -> str:
    path = root / name
    base = {
        "mode": "agentic-run-evaluation-report",
        "scope": "single_run",
        "blocked_reason": "",
        "metrics": [],
        "recommended_actions": [],
    }
    base.update(payload)
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


def _write_eval_case(root: Path, name: str, eval_payload: dict[str, object], completion_payload: dict[str, object]) -> str:
    case_root = root / name
    case_root.mkdir()
    eval_path = _write_eval(case_root, "agentic_run_evaluation_report.json", eval_payload)
    completion_base = {"mode": "agentic-run-completion-report", "blocked_reason": "", "checks": [], "recommended_actions": []}
    completion_base.update(completion_payload)
    (case_root / "agentic_run_completion_report.json").write_text(json.dumps(completion_base), encoding="utf-8")
    return eval_path


if __name__ == "__main__":
    unittest.main()
