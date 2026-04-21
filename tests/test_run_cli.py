from __future__ import annotations

import json
import unittest
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


if __name__ == "__main__":
    unittest.main()
