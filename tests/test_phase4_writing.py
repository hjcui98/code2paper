from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from code2paper.schemas import ClaimEvidenceItem, ClaimEvidenceMap, MethodEvidence
from code2paper.validators.reverse_outline_validator import validate_reverse_outline
from code2paper.writing.method_writer import (
    build_method_draft_from_files,
    build_method_draft_markdown,
    build_method_draft_tex,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4WritingTests(unittest.TestCase):
    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.generated.json"))

    def _claim_map(self) -> ClaimEvidenceMap:
        return ClaimEvidenceMap.model_validate(load_json(EXAMPLES / "attention_claim_evidence_map.generated.json"))

    def test_method_writer_generates_grounded_markdown_from_real_attention_project(self) -> None:
        evidence = self._method_evidence()
        draft = build_method_draft_markdown(evidence, self._claim_map())

        self.assertIn("# Method", draft)
        self.assertIn("## Evidence-Grounded Pipeline", draft)
        self.assertIn("## Code-Backed Mechanism Details", draft)
        self.assertIn("Transformer Computation", draft)
        self.assertIn("Equation candidate **Scaled Dot-Product Attention**", draft)
        self.assertIn(r"\mathrm{Attention}(Q,K,V)", draft)
        self.assertIn("d_model=512", draft)
        self.assertIn("<!-- c2p:", draft)
        self.assertNotIn("README", draft)
        self.assertNotIn("Core implementation symbols", draft)
        self.assertNotIn("implementation symbols categorized", draft)
        self.assertNotIn(".py:", draft)

        report = validate_reverse_outline(draft, evidence)
        self.assertTrue(report.passed, report)
        self.assertGreaterEqual(report.grounded_paragraphs, 4)

    def test_method_writer_excludes_unsupported_claims(self) -> None:
        evidence = self._method_evidence()
        claim_map = self._claim_map()
        claim_map.claims.append(
            ClaimEvidenceItem(
                claim_id="C999",
                claim_text="This unsupported imaginary attention module is a new academic contribution.",
                support_status="unsupported",
                evidence_ids=[],
                mechanism_ids=[],
                source="author_claim:none",
                caveats=[],
            )
        )

        draft = build_method_draft_markdown(evidence, claim_map)
        self.assertNotIn("imaginary attention", draft.lower())
        self.assertNotIn("new academic contribution", draft.lower())

    def test_tex_formatter_outputs_basic_latex(self) -> None:
        evidence = self._method_evidence()
        tex = build_method_draft_tex(evidence, self._claim_map())

        self.assertIn(r"\section{Method}", tex)
        self.assertIn(r"\subsection{Evidence-Grounded Pipeline}", tex)
        self.assertIn(r"\subsection{Code-Backed Mechanism Details}", tex)
        self.assertIn(r"\textbf{Transformer Computation.}", tex)
        self.assertIn(r"\[", tex)
        self.assertIn(r"\mathrm{Attention}(Q,K,V)", tex)
        self.assertIn("% c2p:", tex)

    def test_build_method_draft_from_files_writes_both_formats(self) -> None:
        with TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "method_draft.md"
            tex_path = Path(tmpdir) / "method_draft.tex"
            markdown, tex = build_method_draft_from_files(
                EXAMPLES / "attention_method_evidence.generated.json",
                claim_map_path=EXAMPLES / "attention_claim_evidence_map.generated.json",
            )
            md_path.write_text(markdown, encoding="utf-8")
            tex_path.write_text(tex, encoding="utf-8")

            self.assertTrue(md_path.read_text(encoding="utf-8").startswith("# Method"))
            self.assertTrue(tex_path.read_text(encoding="utf-8").startswith(r"\section{Method}"))

    def test_reverse_outline_validator_flags_ungrounded_sentence(self) -> None:
        evidence = self._method_evidence()
        bad_draft = "# Method\n\n## Overview\nThis sentence has no evidence metadata.\n"
        report = validate_reverse_outline(bad_draft, evidence)

        self.assertFalse(report.passed)
        self.assertEqual(report.ungrounded_paragraphs, ["This sentence has no evidence metadata."])

    def test_reverse_outline_validator_flags_unknown_evidence(self) -> None:
        evidence = self._method_evidence()
        bad_draft = (
            "# Method\n\n"
            "## Overview\n"
            "<!-- c2p: stage=S1; mechanisms=MECH1; evidence=E404; confidence=high -->\n"
            "This sentence points to missing evidence.\n"
        )
        report = validate_reverse_outline(bad_draft, evidence)

        self.assertFalse(report.passed)
        self.assertIn("unknown evidence: E404", report.unknown_references)


if __name__ == "__main__":
    unittest.main()
