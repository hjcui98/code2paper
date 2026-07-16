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
