from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.cli.main import main as cli_main
from code2paper.core.output_names import method_output
from tests.tempdir_support import workspace_tempdir


class MainCliTests(unittest.TestCase):
    def test_run_subcommand_forwards_template_input(self) -> None:
        with patch("code2paper.cli.main.run_main", return_value=0) as run_main:
            code = cli_main(
                [
                    "run",
                    "--project",
                    "repo",
                    "--draft",
                    "draft.yaml",
                    "--out-root",
                    "out",
                ]
            )

        self.assertEqual(code, 0)
        forwarded = run_main.call_args.args[0]
        self.assertIn("--draft", forwarded)
        self.assertIn("draft.yaml", forwarded)
        self.assertNotIn("--author", forwarded)

    def test_run_subcommand_forwards_author_input(self) -> None:
        with patch("code2paper.cli.main.run_main", return_value=0) as run_main:
            code = cli_main(
                [
                    "run",
                    "--project",
                    "repo",
                    "--author",
                    "author.yaml",
                ]
            )

        self.assertEqual(code, 0)
        forwarded = run_main.call_args.args[0]
        self.assertIn("--author", forwarded)
        self.assertIn("author.yaml", forwarded)

    def test_agentic_run_subcommand_forwards_agentic_options(self) -> None:
        with patch("code2paper.cli.main.agentic_run_main", return_value=0) as agentic_run:
            code = cli_main(
                [
                    "agentic-run",
                    "--project",
                    "repo",
                    "--draft",
                    "draft.yaml",
                    "--out-root",
                    "out",
                    "--max-retrieval-rounds",
                    "2",
                    "--max-evidence-revision-rounds",
                    "1",
                    "--max-authoring-revision-rounds",
                    "2",
                    "--max-figure-revision-rounds",
                    "3",
                    "--max-semantic-verifier-calls",
                    "4",
                    "--fail-on-blocked",
                ]
            )

        self.assertEqual(code, 0)
        forwarded = agentic_run.call_args.args[0]
        self.assertEqual(forwarded[0], "repo")
        self.assertIn("--draft", forwarded)
        self.assertIn("draft.yaml", forwarded)
        self.assertIn("--max-retrieval-rounds", forwarded)
        self.assertIn("2", forwarded)
        self.assertIn("--max-evidence-revision-rounds", forwarded)
        self.assertIn("--max-authoring-revision-rounds", forwarded)
        self.assertIn("--max-figure-revision-rounds", forwarded)
        self.assertIn("--max-semantic-verifier-calls", forwarded)
        self.assertIn("--fail-on-blocked", forwarded)

    def test_agentic_benchmark_subcommand_forwards_reports(self) -> None:
        with patch("code2paper.cli.main.agentic_benchmark_main", return_value=0) as benchmark:
            code = cli_main(
                [
                    "agentic-benchmark",
                    "--run",
                    "agentic=case1=agentic_eval.json",
                    "fixed_eval.json",
                    "--out",
                    "benchmark.json",
                ]
            )

        self.assertEqual(code, 0)
        forwarded = benchmark.call_args.args[0]
        self.assertIn("--run", forwarded)
        self.assertIn("agentic=case1=agentic_eval.json", forwarded)
        self.assertIn("fixed_eval.json", forwarded)
        self.assertEqual(forwarded[-2:], ["--out", "benchmark.json"])

    def test_analyze_subcommand_prefers_explicit_project_root(self) -> None:
        with workspace_tempdir() as tmpdir, patch("code2paper.cli.main.run_phase2_analysis", return_value=(None, {})) as analyze:
            out_root = Path(tmpdir) / "out"
            method_root = out_root / "paper" / "method"
            method_root.mkdir(parents=True, exist_ok=True)
            method_output(method_root, "evidence_raw").write_text(
                json.dumps({"project_root": "stale_repo_path"}),
                encoding="utf-8",
            )

            code = cli_main(
                [
                    "analyze",
                    "--project",
                    "fresh_repo_path",
                    "--out-root",
                    str(out_root),
                    "--resolved-markers",
                    "author.yaml",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(analyze.call_args.kwargs["project_root"], Path("fresh_repo_path"))

    def test_prepare_subcommand_calls_refiner(self) -> None:
        with patch("code2paper.cli.main.run_prepare", return_value={"exit_code": 0, "refined_markers": "markers.yaml"}) as refine:
            code = cli_main(
                [
                    "prepare",
                    "--project",
                    "repo",
                    "--draft",
                    "draft.yaml",
                    "--out-root",
                    "out",
                    "--core-top-k",
                    "9",
                ]
            )

        self.assertEqual(code, 0)
        self.assertEqual(refine.call_args.kwargs["project_root"], Path("repo"))
        self.assertEqual(refine.call_args.kwargs["draft_path"], Path("draft.yaml"))
        self.assertEqual(refine.call_args.kwargs["core_top_k"], 9)

    def test_run_subcommand_does_not_forward_out_root_when_omitted(self) -> None:
        with patch("code2paper.cli.main.run_main", return_value=0) as run_main:
            code = cli_main(
                [
                    "run",
                    "--project",
                    "repo",
                    "--author",
                    "author.yaml",
                ]
            )

        self.assertEqual(code, 0)
        forwarded = run_main.call_args.args[0]
        self.assertNotIn("--out-root", forwarded)


if __name__ == "__main__":
    unittest.main()
