from __future__ import annotations

import unittest

from code2paper.evidence.claim_grounder import build_claim_evidence_map
from code2paper.pipeline.stages.evidence import (
    _stage_match_score,
    _submechanisms_for_stage,
    build_method_evidence,
)
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
    SubMechanism,
    SupportStatus,
)


class Phase3EvidenceFallbackTests(unittest.TestCase):
    def test_stage_matching_normalizes_unicode_hyphens_for_mixed_domain_extension(self) -> None:
        mixed_score = _stage_match_score(
            "Extension to mixed‑domain pruning (optional).",
            "Multi‑domain extension (optional)",
        )
        generic_score = _stage_match_score(
            "Extension to mixed‑domain pruning (optional).",
            "Expert pruning",
        )

        self.assertGreater(mixed_score, generic_score)

    def test_stage_matching_connects_few_shot_motivation_to_data_sampling(self) -> None:
        sampling_score = _stage_match_score(
            "Motivation from few‑shot expert localization phenomenon.",
            "Data sampling",
        )
        generic_score = _stage_match_score(
            "Motivation from few‑shot expert localization phenomenon.",
            "Expert pruning",
        )

        self.assertGreater(sampling_score, generic_score)

    def test_stage_matching_preserves_distinctive_compound_acronyms(self) -> None:
        cmoe_score = _stage_match_score(
            "Cross Mixture-of-Experts (C-MoE) decoder: condition router and grouped filtering.",
            "Domain-specific decompression via C-MoE",
        )
        generic_moe_score = _stage_match_score(
            "Cross Mixture-of-Experts decoder",
            "Generic MoE training",
        )

        self.assertGreaterEqual(cmoe_score, 0.72)
        self.assertLess(generic_moe_score, 0.72)

    def test_cmoe_stage_collects_only_matching_operator_submechanisms(self) -> None:
        submechanisms = [
            SubMechanism(
                submechanism_id="SUBMECH1",
                description=(
                    "Packs expert kernels into a single group convolution for parallel execution."
                ),
                evidence_ids=["E1"],
            ),
            SubMechanism(
                submechanism_id="SUBMECH2",
                description=(
                    "Implements an MoE-in-MoE composition from a shared base-expert bank."
                ),
                evidence_ids=["E2"],
            ),
            SubMechanism(
                submechanism_id="SUBMECH3",
                description="Applies an unrelated image normalization transform.",
                evidence_ids=["E3"],
            ),
            SubMechanism(
                submechanism_id="SUBMECH4",
                description="Retains top-k experts and renormalizes their routing weights.",
                evidence_ids=["E4"],
            ),
        ]

        matched = _submechanisms_for_stage(
            submechanisms,
            stage_text=(
                "Cross Mixture-of-Experts (C-MoE) decoder: MoE-in-MoE structure, "
                "grouped dynamic filtering."
            ),
        )

        self.assertEqual([item.submechanism_id for item in matched], ["SUBMECH1", "SUBMECH2"])

        topk_matched = _submechanisms_for_stage(
            submechanisms,
            stage_text="Sparse routing with normalized top-k expert selection.",
        )
        self.assertIn("SUBMECH4", [item.submechanism_id for item in topk_matched])

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
