from __future__ import annotations

import json
import unittest
from pathlib import Path

from code2paper.schemas import CodeAlignmentIR, MethodEvidence
from code2paper.validators.config_value_validator import validate_config_values


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4ConfigValueTests(unittest.TestCase):
    def _alignment(self) -> CodeAlignmentIR:
        return CodeAlignmentIR.model_validate(load_json(EXAMPLES / "attention_code_alignment_ir.generated.json"))

    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.generated.json"))

    def _draft(self) -> str:
        return (EXAMPLES / "attention_method_draft.generated.md").read_text(encoding="utf-8")

    def test_config_value_validator_passes_generated_attention_draft(self) -> None:
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=self._draft(),
        )

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.issues, [])
        self.assertGreater(report.checked_values, 0)

    def test_config_value_validator_flags_architecture_parameter_mismatch(self) -> None:
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=self._draft().replace("d_model=512", "d_model=999", 1),
        )

        self.assertFalse(report.passed)
        self.assertIn("quantitative_value_mismatch", {issue.category for issue in report.issues})
        mismatch = next(issue for issue in report.issues if issue.key == "d_model")
        self.assertEqual(mismatch.written_value, 999)
        self.assertIn(512, mismatch.expected_values)

    def test_config_value_validator_flags_config_resolution_mismatch(self) -> None:
        draft = (
            "# Method\n\n"
            "## Training\n"
            "<!-- c2p: stage=S3; mechanisms=MECH3; evidence=E2; confidence=high -->\n"
            "The training launch uses batch_size=999.\n"
        )
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
        )

        self.assertFalse(report.passed)
        mismatch = next(issue for issue in report.issues if issue.key == "batch_size")
        self.assertEqual(mismatch.category, "quantitative_value_mismatch")
        self.assertIn(256, mismatch.expected_values)

    def test_config_value_validator_flags_unknown_assignment_key(self) -> None:
        draft = (
            "# Method\n\n"
            "## Mechanism\n"
            "<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->\n"
            "The model uses imaginary_hidden_dim=123.\n"
        )
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
        )

        self.assertFalse(report.passed)
        self.assertIn("unknown_quantitative_key", {issue.category for issue in report.issues})

    def test_config_value_validator_checks_natural_language_numeric_claims(self) -> None:
        draft = (
            "# Method\n\n"
            "## Mechanism\n"
            "<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->\n"
            "The model uses 6 encoder layers and 8 attention heads.\n"
        )
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
        )

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.checked_values, 2)

    def test_config_value_validator_flags_natural_language_numeric_mismatch(self) -> None:
        draft = (
            "# Method\n\n"
            "## Mechanism\n"
            "<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->\n"
            "The model uses 9 encoder layers and 8 attention heads.\n"
        )
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
        )

        self.assertFalse(report.passed)
        mismatch = next(issue for issue in report.issues if issue.key == "n_layers")
        self.assertEqual(mismatch.category, "quantitative_value_mismatch")
        self.assertIn(6, mismatch.expected_values)

    def test_config_value_validator_ignores_math_and_grounding_comments(self) -> None:
        draft = (
            "# Method\n\n"
            "## Mechanism\n"
            "<!-- c2p: stage=S2; mechanisms=MECH2; evidence=E81; confidence=high -->\n"
            "$$\n"
            "N=999\n"
            "$$\n"
            "The model uses d_model=512.\n"
        )
        report = validate_config_values(
            alignment=self._alignment(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
        )

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.checked_values, 1)


if __name__ == "__main__":
    unittest.main()
