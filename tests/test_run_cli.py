from __future__ import annotations

import json
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from code2paper.run_cli import main as run_main


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT.parent
ATTENTION_PROJECT = AGENT_ROOT / "PosterGen/data/attention/attention-is-all-you-need-pytorch"
AUTHOR_MARKERS = ROOT / "examples/attention_author_markers.yaml"


class RunCliTests(unittest.TestCase):
    def test_run_cli_generates_phase1_to_phase4_and_fidelity_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            out_root = Path(tmpdir) / "run"
            code = run_main(
                [
                    str(ATTENTION_PROJECT),
                    "--author",
                    str(AUTHOR_MARKERS),
                    "--project-id",
                    "attention_transformer_pytorch",
                    "--out-root",
                    str(out_root),
                    "--skip-figure",
                    "--allow-fidelity-fail",
                ]
            )

            self.assertEqual(code, 0)
            expected = [
                out_root / "paper/method/raw_evidence_pack.json",
                out_root / "paper/method/code_sources.json",
                out_root / "paper/method/core_snippets.json",
                out_root / "paper/method/method_code_alignment.json",
                out_root / "paper/method/code_alignment_ir.json",
                out_root / "paper/method/code_method_analysis.json",
                out_root / "paper/method/method_evidence.json",
                out_root / "paper/method/method_evidence_review.md",
                out_root / "paper/method/phase3_manifest.json",
                out_root / "paper/claim_evidence_map.json",
                out_root / "paper/method/method_authoring_prompt.md",
                out_root / "paper/method/method_draft.md",
                out_root / "paper/method/method_draft.tex",
                out_root / "paper/method/phase4_manifest.json",
                out_root / "paper/method/code2paper_run_report.json",
                out_root / "paper/method/code2paper_run_manifest.json",
            ]
            for path in expected:
                self.assertTrue(path.exists(), path)
            legacy_contract = json.loads(
                (out_root / "paper/method/legacy_trust_contract.json").read_text(encoding="utf-8")
            )
            self.assertEqual(legacy_contract["contract_version"], "legacy-v1-weaker-trust")
            self.assertFalse(legacy_contract["authoritative_v2_final_invariant"])

            report = json.loads((out_root / "paper/method/code2paper_run_report.json").read_text(encoding="utf-8"))
            self.assertIn("fidelity_passed", report)
            self.assertFalse(report["phase4_blocked"])
            self.assertEqual(report["project_id"], "attention_transformer_pytorch")
            manifest = json.loads(
                (out_root / "paper/method/code2paper_run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(manifest["final_draft_hash"])
            self.assertIn("code_sources", manifest["phase_outputs"])
            self.assertIn("core_snippets", manifest["phase_outputs"])
            self.assertIn("code_method_analysis", manifest["phase_outputs"])
            self.assertIn("phase3_manifest", manifest["phase_outputs"])
            self.assertIn("method_draft_md", manifest["phase_outputs"])
            self.assertEqual(manifest["llm"]["provider"], "none")

    def test_run_cli_agentic_mode_dispatches_to_v2_runner(self) -> None:
        captured = {}

        def fake_agentic(argv):
            captured["argv"] = argv
            return 7

        with TemporaryDirectory() as tmpdir, patch("code2paper.cli.agentic_run.main", side_effect=fake_agentic):
            code = run_main([
                str(Path(tmpdir)),
                "--author", str(AUTHOR_MARKERS),
                "--out-root", str(Path(tmpdir) / "agentic"),
                "--mode", "agentic",
                "--run-id", "mode-agentic-1",
                "--max-semantic-verifier-calls", "3",
                "--fail-on-blocked",
            ])

        self.assertEqual(code, 7)
        self.assertIn("--run-id", captured["argv"])
        self.assertIn("mode-agentic-1", captured["argv"])
        self.assertIn("--max-semantic-verifier-calls", captured["argv"])
        self.assertIn("3", captured["argv"])
        self.assertIn("--fail-on-blocked", captured["argv"])

    def test_shadow_mode_keeps_legacy_delivery_and_marks_agentic_non_delivery(self) -> None:
        with TemporaryDirectory() as tmpdir, patch("code2paper.cli.agentic_run.main", return_value=0):
            project = Path(tmpdir) / "repo"
            project.mkdir()
            (project / "train.py").write_text("def main():\n    pass\n", encoding="utf-8")
            out = Path(tmpdir) / "shadow"
            code = run_main([
                str(project),
                "--author", str(AUTHOR_MARKERS),
                "--out-root", str(out),
                "--mode", "shadow",
                "--inspect-only",
            ])
            record = json.loads((out / "shadow_comparison.json").read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(record["delivery_route"], "legacy")
        self.assertEqual(record["shadow_route"], "agentic")
        self.assertEqual(record["status"], "completed")
        self.assertFalse(record["claim_of_completion_allowed"])
        self.assertEqual(record["legacy_contract_version"], "legacy-v1-weaker-trust")
        self.assertFalse(record["comparison_ready_for_benchmark_evaluation"])
        self.assertTrue(record["artifacts"]["legacy_run_report"]["hash"])
        self.assertTrue(record["artifacts"]["legacy_run_manifest"]["hash"])
        self.assertTrue(record["artifacts"]["legacy_trust_contract"]["hash"])

    def test_default_ready_cutover_decision_activates_implicit_agentic_default(self) -> None:
        with TemporaryDirectory() as tmpdir, patch("code2paper.cli.agentic_run.main", return_value=0) as agentic:
            root = Path(tmpdir)
            decision = root / "cutover.json"
            decision.write_text(json.dumps({
                "schema_version": "2.3",
                "status": "default_ready",
                "default_mode": "agentic",
                "hard_gates_passed": True,
                "worst_case_metrics": {},
                "failures": [],
                "next_actions": [],
                "named_review_evidence": {
                    "source": "digest_pinned_review_artifacts",
                    "review_artifact_digests": ["sha256:" + "a" * 64],
                },
                "validated_benchmark_evidence": {
                    "source": "digest_pinned_observation_artifacts",
                    "artifact_digests": ["sha256:" + "f" * 64],
                    "observation_count": 25,
                },
                "validated_rollout_evidence": {
                    "source": "digest_pinned_rollout_artifacts",
                    "artifact_digests": [
                        "sha256:" + "b" * 64,
                        "sha256:" + "d" * 64,
                        "sha256:" + "e" * 64,
                    ],
                    "shadow_case_ids": ["case-1"],
                    "opt_in_case_ids": ["case-1"],
                    "canary_case_ids": ["case-1"],
                    "canary_incidents": 0,
                },
                "protocol_commit": "commit:test",
                "gold_digest": "sha256:" + "c" * 64,
                "benchmark_case_ids": ["case-1"],
            }), encoding="utf-8")
            out = root / "run"

            code = run_main([
                str(root), "--author", str(AUTHOR_MARKERS), "--out-root", str(out),
                "--cutover-decision", str(decision),
            ])
            activation = json.loads((out / "cutover_activation.json").read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        agentic.assert_called_once()
        self.assertTrue(activation["authorized"])
        self.assertEqual(activation["resolved_mode"], "agentic")
        self.assertTrue(activation["decision_digest"].startswith("sha256:"))

    def test_default_ready_without_validated_benchmark_artifacts_fails_closed(self) -> None:
        with TemporaryDirectory() as tmpdir, patch("code2paper.cli.agentic_run.main") as agentic:
            root = Path(tmpdir)
            project = root / "repo"
            project.mkdir()
            (project / "train.py").write_text("def main():\n    pass\n", encoding="utf-8")
            decision = root / "cutover.json"
            decision.write_text(json.dumps({
                "schema_version": "2.2",
                "status": "default_ready",
                "default_mode": "agentic",
                "hard_gates_passed": True,
                "worst_case_metrics": {},
                "failures": [],
                "next_actions": [],
            }), encoding="utf-8")
            out = root / "run"

            code = run_main([
                str(project), "--author", str(AUTHOR_MARKERS), "--out-root", str(out),
                "--cutover-decision", str(decision), "--inspect-only",
            ])
            activation = json.loads((out / "cutover_activation.json").read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        agentic.assert_not_called()
        self.assertFalse(activation["authorized"])
        self.assertEqual(activation["resolved_mode"], "legacy")
        self.assertEqual(activation["named_review_evidence_source"], "none")

    def test_non_ready_cutover_decision_fails_closed_to_legacy(self) -> None:
        with TemporaryDirectory() as tmpdir, patch("code2paper.cli.agentic_run.main") as agentic:
            root = Path(tmpdir)
            project = root / "repo"
            project.mkdir()
            (project / "train.py").write_text("def main():\n    pass\n", encoding="utf-8")
            decision = root / "cutover.json"
            decision.write_text(json.dumps({
                "schema_version": "2.0",
                "status": "hold",
                "default_mode": "legacy",
                "hard_gates_passed": False,
                "worst_case_metrics": {},
                "failures": ["named_review_missing"],
                "next_actions": ["keep_legacy_default"],
            }), encoding="utf-8")
            out = root / "run"

            code = run_main([
                str(project), "--author", str(AUTHOR_MARKERS), "--out-root", str(out),
                "--cutover-decision", str(decision), "--inspect-only",
            ])
            activation = json.loads((out / "cutover_activation.json").read_text(encoding="utf-8"))
            legacy_contract_exists = (out / "paper/method/legacy_trust_contract.json").exists()

        self.assertEqual(code, 0)
        agentic.assert_not_called()
        self.assertFalse(activation["authorized"])
        self.assertEqual(activation["resolved_mode"], "legacy")
        self.assertTrue(legacy_contract_exists)


if __name__ == "__main__":
    unittest.main()
