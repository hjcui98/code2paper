from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.claim_verifier import (
    build_claim_verification_report,
    load_claim_verification_report,
    write_claim_verification_report,
)
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo Method",
        method_goal="Explain the implementation.",
        implementation_scope="core implementation",
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Encode",
                purpose="Extract features.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="Feature encoder uses the configured attention block.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1", "E2"],
                    )
                ],
            )
        ],
    )


class AgenticClaimVerifierTests(unittest.TestCase):
    def test_supported_claim_is_allowed_when_evidence_id_is_known(self) -> None:
        claim_map = ClaimEvidenceMap(
            claims=[
                ClaimEvidenceItem(
                    claim_id="C1",
                    claim_text="The encoder uses attention.",
                    support_status=SupportStatus.SUPPORTED,
                    evidence_ids=["E1"],
                    source="author_claim:mechanism",
                )
            ]
        )

        report = build_claim_verification_report(_method_evidence(), claim_map)

        self.assertTrue(report.hard_gate_passed)
        self.assertEqual(report.supported_claims, 1)
        self.assertEqual(report.claims[0].recommended_action, "allow_in_prose")

    def test_missing_evidence_id_downgrades_claim_to_unsupported(self) -> None:
        claim_map = ClaimEvidenceMap(
            claims=[
                ClaimEvidenceItem(
                    claim_id="C2",
                    claim_text="The encoder has an unobserved behavior.",
                    support_status=SupportStatus.SUPPORTED,
                    evidence_ids=["E404"],
                    source="author_claim:mechanism",
                )
            ]
        )

        report = build_claim_verification_report(_method_evidence(), claim_map)

        self.assertFalse(report.hard_gate_passed)
        self.assertEqual(report.unsupported_claims, 1)
        self.assertEqual(report.claims_with_missing_evidence, 1)
        self.assertEqual(report.claims[0].support_status, SupportStatus.UNSUPPORTED)
        self.assertEqual(report.claims[0].recommended_action, "drop_or_retrieve_more_evidence")

    def test_partial_claim_requires_caveat(self) -> None:
        claim_map = ClaimEvidenceMap(
            claims=[
                ClaimEvidenceItem(
                    claim_id="C3",
                    claim_text="The encoder likely uses attention-like weighting.",
                    support_status=SupportStatus.PARTIAL,
                    evidence_ids=["E2"],
                    source="method_mechanism",
                    caveats=["Only the weighting operation is visible."],
                )
            ]
        )

        report = build_claim_verification_report(_method_evidence(), claim_map)

        self.assertTrue(report.hard_gate_passed)
        self.assertEqual(report.partial_claims, 1)
        self.assertEqual(report.claims[0].recommended_action, "caveat_only")

    def test_report_round_trips_to_json(self) -> None:
        claim_map = ClaimEvidenceMap(
            claims=[
                ClaimEvidenceItem(
                    claim_id="C1",
                    claim_text="The encoder uses attention.",
                    support_status=SupportStatus.SUPPORTED,
                    evidence_ids=["E1"],
                    source="author_claim:mechanism",
                )
            ]
        )
        report = build_claim_verification_report(_method_evidence(), claim_map)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "claim_verification.json"
            write_claim_verification_report(output, report)
            loaded = load_claim_verification_report(output)

        self.assertEqual(loaded.checked_claims, 1)
        self.assertEqual(loaded.claims[0].claim_id, "C1")


if __name__ == "__main__":
    unittest.main()
