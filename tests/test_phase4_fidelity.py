from __future__ import annotations

import json
import unittest
from pathlib import Path

from code2paper.schemas import ClaimEvidenceItem, ClaimEvidenceMap, MethodEvidence, RawEvidencePack
from code2paper.validators.fidelity_validator import validate_method_fidelity


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class Phase4FidelityTests(unittest.TestCase):
    def _raw_pack(self) -> RawEvidencePack:
        return RawEvidencePack.model_validate(load_json(EXAMPLES / "attention_raw_evidence_pack.generated.json"))

    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(EXAMPLES / "attention_method_evidence.generated.json"))

    def _claim_map(self) -> ClaimEvidenceMap:
        return ClaimEvidenceMap.model_validate(load_json(EXAMPLES / "attention_claim_evidence_map.generated.json"))

    def test_fidelity_validator_passes_generated_attention_draft(self) -> None:
        report = validate_method_fidelity(
            raw_pack=self._raw_pack(),
            method_evidence=self._method_evidence(),
            draft_markdown=(EXAMPLES / "attention_method_draft.generated.md").read_text(encoding="utf-8"),
            claim_map=self._claim_map(),
        )

        self.assertTrue(report.passed, report.model_dump())
        self.assertEqual(report.issues, [])
        self.assertGreater(report.grounded_paragraphs, 0)
        self.assertGreater(report.checked_claims, 0)

    def test_fidelity_validator_flags_ungrounded_paragraph(self) -> None:
        report = validate_method_fidelity(
            raw_pack=self._raw_pack(),
            method_evidence=self._method_evidence(),
            draft_markdown="# Method\n\n## Overview\nThis paragraph is not grounded.\n",
            claim_map=self._claim_map(),
        )

        self.assertFalse(report.passed)
        self.assertIn("ungrounded_paragraph", {issue.category for issue in report.issues})

    def test_fidelity_validator_flags_author_only_support(self) -> None:
        raw_pack = self._raw_pack()
        method_evidence = self._method_evidence()
        author_evidence_id = next(item.evidence_id for item in raw_pack.evidence_items if item.source_type == "author")
        draft = (
            "# Method\n\n"
            "## Overview\n"
            f"<!-- c2p: stage=ALL; mechanisms=MECH1; evidence={author_evidence_id}; confidence=medium -->\n"
            "This paragraph relies only on author hints.\n"
        )

        report = validate_method_fidelity(
            raw_pack=raw_pack,
            method_evidence=method_evidence,
            draft_markdown=draft,
            claim_map=self._claim_map(),
        )

        self.assertFalse(report.passed)
        self.assertIn("soft_or_author_only_support", {issue.category for issue in report.issues})

    def test_fidelity_validator_flags_unsupported_claim_leak(self) -> None:
        claim_map = self._claim_map()
        claim_map.claims.append(
            ClaimEvidenceItem(
                claim_id="C999",
                claim_text="Unsupported imaginary method claim",
                support_status="unsupported",
                evidence_ids=[],
                mechanism_ids=[],
                source="author_claim:none",
                caveats=[],
            )
        )
        draft = (
            "# Method\n\n"
            "## Overview\n"
            "<!-- c2p: stage=ALL; mechanisms=MECH1; evidence=E19; confidence=high -->\n"
            "Unsupported imaginary method claim\n"
        )

        report = validate_method_fidelity(
            raw_pack=self._raw_pack(),
            method_evidence=self._method_evidence(),
            draft_markdown=draft,
            claim_map=claim_map,
        )

        self.assertFalse(report.passed)
        self.assertIn("unsupported_claim_leaked", {issue.category for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
