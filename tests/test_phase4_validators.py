from __future__ import annotations

import json
import unittest
from pathlib import Path

from code2paper.schemas import CodeAlignmentIR, MethodEvidence, TerminologyTable
from code2paper.validators.equation_support_validator import validate_equation_support
from code2paper.validators.numeric_fact_validator import validate_numeric_facts
from code2paper.validators.terminology_validator import validate_terminology_consistency


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4ValidatorTests(unittest.TestCase):
    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.generated.json"))

    def _alignment(self) -> CodeAlignmentIR:
        return CodeAlignmentIR.model_validate(load_json(EXAMPLES / "attention_code_alignment_ir.generated.json"))

    def test_numeric_fact_validator_flags_bad_architecture_number(self) -> None:
        draft = (
            "# Method\n\n"
            "## Overview\n"
            "<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->\n"
            "The model uses d_model=999 and 8 attention heads.\n"
        )
        report = validate_numeric_facts(
            method_evidence=self._method_evidence(),
            alignment=self._alignment(),
            draft_markdown=draft,
        )

        self.assertFalse(report.passed)
        self.assertIn("quantitative_value_mismatch", {issue.category for issue in report.issues})

    def test_equation_support_validator_passes_candidate_equation(self) -> None:
        evidence = self._method_evidence()
        equation = next(item for item in evidence.equation_candidates if item.evidence_ids)
        report = validate_equation_support(
            method_evidence=evidence,
            draft_markdown=f"# Method\n\n## Equation\n$$\n{equation.latex}\n$$\n",
        )

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.checked_equations, 1)

    def test_equation_support_validator_flags_unsupported_equation(self) -> None:
        report = validate_equation_support(
            method_evidence=self._method_evidence(),
            draft_markdown="# Method\n\n## Equation\n$$\ny = imaginary(x) + 42\n$$\n",
        )

        self.assertFalse(report.passed)
        self.assertIn("unsupported_equation", {issue.category for issue in report.issues})

    def test_terminology_validator_flags_forbidden_replacement(self) -> None:
        table = TerminologyTable.model_validate(
            {
                "terms": [
                    {
                        "term_id": "TERM-1",
                        "canonical": "scaled dot-product attention",
                        "term_type": "mechanism",
                        "forbidden_replacements": ["magic attention"],
                    }
                ]
            }
        )
        report = validate_terminology_consistency(
            terminology_table=table,
            draft_markdown="The method uses magic attention in the core block.",
        )

        self.assertFalse(report.passed)
        self.assertEqual(report.issues[0].category, "forbidden_replacement_used")


if __name__ == "__main__":
    unittest.main()
