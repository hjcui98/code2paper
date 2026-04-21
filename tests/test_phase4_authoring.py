from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from code2paper import phase4_authoring
from code2paper.phase4_authoring import write_phase4_artifacts
from code2paper.schemas import ClaimEvidenceMap, CodeAlignmentIR, LLMConfig, MethodEvidence


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4AuthoringTests(unittest.TestCase):
    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.generated.json"))

    def _claim_map(self) -> ClaimEvidenceMap:
        return ClaimEvidenceMap.model_validate(load_json(EXAMPLES / "attention_claim_evidence_map.generated.json"))

    def _alignment(self) -> CodeAlignmentIR:
        return CodeAlignmentIR.model_validate(load_json(EXAMPLES / "attention_code_alignment_ir.generated.json"))

    def test_phase4_writes_draft_without_api(self) -> None:
        with TemporaryDirectory() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="none"),
            )
            manifest = json.loads(paths["phase4_manifest"].read_text(encoding="utf-8"))
            prompt_exists = paths["method_authoring_prompt"].exists()
            blocked_exists = paths["phase4_blocked_report"].exists()
            draft_exists = paths["method_draft_md"].exists()

        self.assertIsNotNone(markdown)
        self.assertIsNotNone(tex)
        self.assertTrue(prompt_exists)
        self.assertFalse(blocked_exists)
        self.assertTrue(draft_exists)
        self.assertEqual(manifest["mode"], "deterministic-authoring")
        self.assertEqual(len(manifest["llm_call_logs"]), 0)

    def test_phase4_uses_deterministic_authoring_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase4_manifest"].read_text(encoding="utf-8"))
            sidecar = json.loads(paths["method_authoring_sidecar"].read_text(encoding="utf-8"))
            numeric_report = json.loads(paths["numeric_fact_report"].read_text(encoding="utf-8"))
            equation_report = json.loads(paths["equation_support_report"].read_text(encoding="utf-8"))
            outline_exists = paths["method_outline"].exists()
            terminology_exists = paths["terminology_table"].exists()
            draft_claim_map_exists = paths["draft_claim_map"].exists()

        complete.assert_not_called()
        self.assertIn("# Method", markdown or "")
        self.assertIn("Transformer Translation Training Pipeline", markdown or "")
        self.assertIn("\\section{Method}", tex or "")
        self.assertTrue(outline_exists)
        self.assertTrue(terminology_exists)
        self.assertTrue(draft_claim_map_exists)
        self.assertEqual(manifest["mode"], "deterministic-authoring")
        self.assertEqual(len(manifest["llm_call_logs"]), 0)
        self.assertEqual(sidecar["paragraphs"][0]["llm_call_id"], "deterministic-authoring")
        self.assertTrue(numeric_report["passed"])
        self.assertIn("passed", equation_report)

    def test_phase4_ignores_revision_cycle_and_keeps_single_deterministic_pass(self) -> None:
        with TemporaryDirectory() as tmpdir, patch.dict(
            "os.environ", {"CODE2PAPER_PHASE4_ENABLE_REVISION_CYCLE": "1"}
        ), patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase4_manifest"].read_text(encoding="utf-8"))
            sidecar = json.loads(paths["method_authoring_sidecar"].read_text(encoding="utf-8"))

        complete.assert_not_called()
        self.assertIn("# Method", markdown or "")
        self.assertIn("\\section{Method}", tex or "")
        self.assertEqual(len(manifest["llm_call_logs"]), 0)
        self.assertEqual(sidecar["draft_version"], 1)
        self.assertEqual(sidecar["revision_history"], [])

    def test_phase4_deterministic_claim_mapping_uses_stage_mechanism_evidence_when_frozen_sparse(self) -> None:
        method_evidence = self._method_evidence()
        for mechanism in method_evidence.frozen_mechanisms:
            mechanism.evidence_span_ids = []
            mechanism.parent_stage_id = ""

        with TemporaryDirectory() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase4_artifacts(
                method_root=method_root,
                method_evidence=method_evidence,
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="none", require_api_for_writing=False),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase4_manifest"].read_text(encoding="utf-8"))
            claim_report = json.loads(paths["claim_evidence_report"].read_text(encoding="utf-8"))
            draft_claim_map = json.loads(paths["draft_claim_map"].read_text(encoding="utf-8"))

        self.assertIsNotNone(markdown)
        self.assertIsNotNone(tex)
        self.assertEqual(manifest["mode"], "deterministic-authoring")
        self.assertTrue(claim_report["passed"])
        self.assertTrue(draft_claim_map["paragraphs"])
        self.assertTrue(all(paragraph["evidence_span_ids"] for paragraph in draft_claim_map["paragraphs"]))

    def test_latex_smoke_report_uses_real_compile_command(self) -> None:
        with patch("code2paper.validators.latex_smoke_validator.shutil.which", return_value="/usr/bin/pdflatex"), patch(
            "code2paper.validators.latex_smoke_validator.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="ok"),
        ) as run:
            report = phase4_authoring.validate_latex_smoke("\\section{Method}\nText.")

        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "compiled")
        self.assertIn("-halt-on-error", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
