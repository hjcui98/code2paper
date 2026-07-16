from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.contracts import AgentDecision
from code2paper.agentic.runner import AgenticRunResult, AgenticRunSummary
from code2paper.cli.agentic_run import main as agentic_run_main


class AgenticRunCliTests(unittest.TestCase):
    def test_agentic_run_cli_builds_state_and_prints_summary(self) -> None:
        captured = {}

        def fake_run(state):
            captured["state"] = state
            summary_path = state.out_root / "artifacts" / "10_run" / "agentic_run_summary.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text("{}", encoding="utf-8")
            summary = AgenticRunSummary(
                status="success",
                project_root=str(state.project_root),
                out_root=str(state.out_root),
                invariant_audit_passed=True,
                decisions=[AgentDecision(node="fake", decision="done")],
            )
            return AgenticRunResult(
                state=state.model_copy(update={"artifacts": {"agentic_run_summary": str(summary_path)}}),
                summary=summary,
                summary_path=summary_path,
            )

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.cli.agentic_run.run_agentic_code2paper",
            side_effect=fake_run,
        ):
            project_root = Path(tmpdir) / "repo"
            project_root.mkdir()
            out_root = Path(tmpdir) / "out"
            code = agentic_run_main(
                [
                    str(project_root),
                    "--out-root",
                    str(out_root),
                    "--project-id",
                    "demo",
                    "--llm-provider",
                    "none",
                    "--max-retrieval-rounds",
                    "2",
                    "--max-evidence-revision-rounds",
                    "3",
                    "--max-authoring-revision-rounds",
                    "4",
                    "--max-figure-revision-rounds",
                    "5",
                    "--max-semantic-verifier-calls",
                    "6",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(captured["state"].project_id, "demo")
        self.assertEqual(captured["state"].out_root, out_root.resolve())
        self.assertEqual(captured["state"].llm_provider, "none")
        self.assertEqual(captured["state"].max_retrieval_rounds, 2)
        self.assertEqual(
            captured["state"].budgets,
            {
                "max_retrieval_rounds": 2,
                "max_evidence_revision_rounds": 3,
                "max_authoring_revision_rounds": 4,
                "max_figure_revision_rounds": 5,
                "max_semantic_verifier_calls": 6,
            },
        )

    def test_agentic_run_cli_prints_completion_status_when_report_exists(self) -> None:
        def fake_run(state):
            summary_path = state.out_root / "artifacts" / "10_run" / "agentic_run_summary.json"
            completion_path = summary_path.with_name("agentic_run_completion_report.json")
            completion_path.parent.mkdir(parents=True, exist_ok=True)
            completion_path.write_text(
                json.dumps(
                    {
                        "mode": "agentic-run-completion-report",
                        "status": "incomplete",
                        "complete": False,
                        "blocked_reason": "",
                        "missing_deliverables": ["method_text", "final_package"],
                        "checks": [],
                        "recommended_actions": ["produce_evidence_backed_method_text"],
                    }
                ),
                encoding="utf-8",
            )
            summary = AgenticRunSummary(
                status="success",
                project_root=str(state.project_root),
                out_root=str(state.out_root),
                invariant_audit_passed=True,
            )
            return AgenticRunResult(
                state=state.model_copy(
                    update={"artifacts": {"agentic_run_completion_report": str(completion_path)}}
                ),
                summary=summary,
                summary_path=summary_path,
            )

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.cli.agentic_run.run_agentic_code2paper",
            side_effect=fake_run,
        ):
            project_root = Path(tmpdir) / "repo"
            project_root.mkdir()
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = agentic_run_main([str(project_root), "--out-root", str(Path(tmpdir) / "out")])

        output = stdout.getvalue()
        payload = json.loads(output[output.index("{") :])
        self.assertEqual(code, 0)
        self.assertIn("[code2paper-agentic-run] completion_status=incomplete complete=False", output)
        self.assertIn("[code2paper-agentic-run] missing_deliverables=method_text,final_package", output)
        self.assertEqual(payload["completion_status"], "incomplete")
        self.assertFalse(payload["completion_complete"])
        self.assertEqual(payload["missing_deliverables"], ["method_text", "final_package"])

    def test_agentic_run_cli_can_fail_on_blocked(self) -> None:
        def fake_run(state):
            summary_path = state.out_root / "artifacts" / "10_run" / "agentic_run_summary.json"
            summary = AgenticRunSummary(
                status="blocked",
                project_root=str(state.project_root),
                out_root=str(state.out_root),
                blocked_reason="method_text_missing",
                invariant_blocking_failures=1,
            )
            return AgenticRunResult(state=state, summary=summary, summary_path=summary_path)

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.cli.agentic_run.run_agentic_code2paper",
            side_effect=fake_run,
        ):
            project_root = Path(tmpdir) / "repo"
            project_root.mkdir()
            code = agentic_run_main([str(project_root), "--out-root", str(Path(tmpdir) / "out"), "--fail-on-blocked"])

        self.assertEqual(code, 1)

    def test_agentic_run_cli_reports_missing_agentic_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.cli.agentic_run.run_agentic_code2paper",
            side_effect=RuntimeError("Install the optional agentic extra"),
        ):
            project_root = Path(tmpdir) / "repo"
            project_root.mkdir()
            code = agentic_run_main([str(project_root), "--out-root", str(Path(tmpdir) / "out")])

        self.assertEqual(code, 2)

    def test_agentic_run_cli_rejects_missing_project_root_before_running_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.cli.agentic_run.run_agentic_code2paper"
        ) as run:
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = agentic_run_main(
                    [
                        str(Path(tmpdir) / "missing"),
                        "--out-root",
                        str(Path(tmpdir) / "out"),
                    ]
                )

        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertIn("project_root_not_found", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
