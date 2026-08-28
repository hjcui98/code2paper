from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.completion_report import (
    build_run_completion_report,
    load_run_completion_report,
    write_run_completion_report,
)
from code2paper.agentic.contracts import AgenticRunState


class AgenticCompletionReportTests(unittest.TestCase):
    def test_report_marks_evidence_only_run_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "evidence": _write_json(root, "evidence.json", {}),
                    "claims": _write_json(root, "claims.json", {"claims": []}),
                    "claim_verification": _write_json(root, "claim_verification.json", {"claims": []}),
                    "traceability_ledger": _write_json(root, "ledger.json", {"hard_gate_passed": True}),
                },
            )

            report = build_run_completion_report(state)

        self.assertEqual(report.status, "incomplete")
        self.assertFalse(report.complete)
        self.assertIn("method_text", report.missing_deliverables)
        self.assertIn("method_figure", report.missing_deliverables)
        self.assertIn("final_package", report.missing_deliverables)
        self.assertIn("produce_evidence_backed_method_text", report.recommended_actions)

    def test_report_marks_traceable_method_package_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "evidence": _write_json(root, "evidence.json", {}),
                    "claims": _write_json(root, "claims.json", {"claims": []}),
                    "claim_verification": _write_json(root, "claim_verification.json", {"claims": []}),
                    "text_md": _write_text(root, "method.md", "method"),
                    "text_claims": _write_json(root, "text_claims.json", {"paragraphs": []}),
                    "final_text_claims": _write_json(root, "final_text_claims.json", {"input_text_digest": "sha256:text"}),
                    "text_evidence_validation": _write_json(
                        root,
                        "text_evidence_validation.json",
                        {"status": "passed", "input_text_digest": "sha256:text"},
                    ),
                    "final_text_trace": _write_json(
                        root,
                        "final_text_trace.json",
                        {"hard_gate_passed": True, "input_text_digest": "sha256:text"},
                    ),
                    "figure_plan": _write_json(root, "figure_plan.json", {"hard_gate_passed": True, "nodes": []}),
                    "figure_plan_decision_trace": _write_json(root, "figure_trace.json", {"node": "figure_planner"}),
                    "validation_manifest": _write_json(root, "validation.json", {"status": "passed"}),
                    "traceability_ledger": _write_json(root, "ledger.json", {"hard_gate_passed": True}),
                    "agentic_invariant_audit": _write_json(root, "audit.json", {"passed": True}),
                    "agentic_run_readiness_report": _write_json(root, "readiness.json", {"passed": True}),
                    "final_tex": _write_text(root, "final.tex", "\\section{Method}"),
                    "finalize_manifest": _write_json(root, "finalize.json", {"status": "success"}),
                },
            )

            report = build_run_completion_report(state)

        self.assertEqual(report.status, "complete")
        self.assertTrue(report.complete)
        self.assertEqual(report.missing_deliverables, [])
        self.assertEqual(report.recommended_actions, ["agentic_run_completion_ready"])

    def test_report_round_trips_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=root, out_root=root / "out")
            path = root / "completion.json"

            write_run_completion_report(path, build_run_completion_report(state))
            loaded = load_run_completion_report(path)

        self.assertEqual(loaded.mode, "agentic-run-completion-report")
        self.assertEqual(loaded.status, "incomplete")

    def test_report_accepts_durable_candidate_with_warnings(self) -> None:
        # Q0: method_usability reads the independent candidate-first fields; a
        # durable editable candidate with warnings is a usable deliverable even
        # before the run reaches publication_ready.
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "publication_writer_result_v1": _write_json(root, "writer_result.json", {
                        "candidate_available": True,
                        "candidate_generation_status": "generated",
                        "candidate_validation_status": "warnings",
                        "verified_validation_status": "incomplete",
                        "publication_ready": False,
                    }),
                    "publication_quality_report_v1": _write_json(root, "quality.json", {
                        "status": "incomplete",
                        "final_integrity_gate_passed": False,
                    }),
                },
            )

            report = build_run_completion_report(state)

        usability = next(check for check in report.checks if check.name == "method_usability")
        self.assertTrue(usability.passed)
        self.assertNotIn("method_usability", report.missing_deliverables)

    def test_report_fails_usability_without_durable_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "publication_writer_result_v1": _write_json(root, "writer_result.json", {
                        "candidate_available": False,
                        "candidate_generation_status": "failed",
                    }),
                    "publication_quality_report_v1": _write_json(root, "quality.json", {"status": "blocked"}),
                },
            )

            report = build_run_completion_report(state)

        usability = next(check for check in report.checks if check.name == "method_usability")
        self.assertFalse(usability.passed)
        self.assertIn("method_usability", report.missing_deliverables)

    def test_report_does_not_call_trustworthy_but_uncovered_method_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=root,
                out_root=root / "out",
                artifacts={
                    "authoring_obligation_coverage": _write_json(
                        root,
                        "coverage.json",
                        {
                            "must_cover_count": 5,
                            "candidate_covered_must_cover_count": 1,
                            "unresolved_must_cover_ids": ["O2", "O3", "O4", "O5"],
                            "unique_projected_claim_count": 1,
                        },
                    ),
                },
            )

            report = build_run_completion_report(state)

        usability = next(check for check in report.checks if check.name == "method_usability")
        self.assertFalse(usability.passed)
        self.assertIn("covered 1/5", usability.message)
        self.assertIn("method_usability", report.missing_deliverables)
        self.assertIn(
            "resolve_must_cover_author_obligations_or_record_terminal_code_gaps",
            report.recommended_actions,
        )


def _write_json(root: Path, name: str, payload: dict[str, object]) -> str:
    path = root / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _write_text(root: Path, name: str, text: str) -> str:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    unittest.main()
