from __future__ import annotations

import unittest

from code2paper.evidence.claim_grounder import build_claim_evidence_map
from code2paper.pipeline.stages.evidence import build_method_evidence
from code2paper.core.schemas import (
    AuthorAlignment,
    AuthorClaimAssessment,
    ClaimSupportLevel,
    CodeAlignmentIR,
    CodeMethodAnalysis,
    EvidenceItem,
    EvidenceStrength,
    RawEvidencePack,
    SourceType,
    SupportStatus,
)


class Phase3EvidenceFallbackTests(unittest.TestCase):
    def test_build_method_evidence_preserves_hard_raw_evidence_when_analysis_has_no_mechanisms(self) -> None:
        raw_pack = RawEvidencePack(
            project_id="demo",
            project_root="/repo",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E1",
                    source_type=SourceType.SOURCE,
                    path="train.py",
                    line_start=1,
                    line_end=4,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="training_loop",
                ),
                EvidenceItem(
                    evidence_id="E2",
                    source_type=SourceType.BASH,
                    path="scripts/train.sh",
                    line_start=1,
                    line_end=3,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="config",
                ),
            ],
        )
        alignment = CodeAlignmentIR(project_id="demo")
        analysis = CodeMethodAnalysis(evidence_spans=raw_pack.evidence_items)

        method_evidence = build_method_evidence(raw_pack, alignment, analysis)
        claim_map = build_claim_evidence_map(method_evidence, alignment)

        self.assertEqual([mechanism.mechanism_id for mechanism in method_evidence.frozen_mechanisms], ["MECH1"])
        self.assertEqual(method_evidence.frozen_mechanisms[0].evidence_span_ids, ["E1", "E2"])
        self.assertEqual(method_evidence.claim_contracts[0].support_status.value, "supported")
        self.assertEqual(claim_map.claims[0].support_status, SupportStatus.SUPPORTED)
        self.assertEqual(claim_map.claims[0].evidence_ids, ["E1", "E2"])

    def test_author_claim_drops_evidence_ids_outside_frozen_method_evidence(self) -> None:
        raw_pack = RawEvidencePack(
            project_id="demo",
            project_root="/repo",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E1", source_type=SourceType.SOURCE, path="method.py",
                    line_start=1, line_end=5, evidence_strength=EvidenceStrength.HARD,
                    confidence=0.9, content_summary="implemented method",
                )
            ],
        )
        alignment = CodeAlignmentIR(
            project_id="demo",
            author_alignment=AuthorAlignment(
                claim_assessments=[
                    AuthorClaimAssessment(
                        claim_text="Unsupported extension.",
                        support_status=SupportStatus.UNSUPPORTED,
                        support_level=ClaimSupportLevel.NONE,
                        evidence_ids=["E404"],
                    )
                ]
            ),
        )
        method_evidence = build_method_evidence(
            raw_pack, alignment, CodeMethodAnalysis(evidence_spans=raw_pack.evidence_items)
        )

        claim_map = build_claim_evidence_map(method_evidence, alignment)
        author_claim = next(claim for claim in claim_map.claims if claim.source.startswith("author_claim:"))

        self.assertEqual(author_claim.support_status, SupportStatus.UNSUPPORTED)
        self.assertEqual(author_claim.evidence_ids, [])


if __name__ == "__main__":
    unittest.main()
