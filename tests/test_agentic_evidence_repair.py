from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.evidence_repair import (
    build_evidence_repair_focus,
    focus_to_retrieval_overlay,
    load_evidence_repair_focus,
    write_evidence_repair_focus,
)
from code2paper.agentic.evidence_sufficiency import build_evidence_sufficiency_report, critique_evidence_sufficiency
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


class AgenticEvidenceRepairTests(unittest.TestCase):
    def test_repair_focus_turns_weak_claims_into_queries(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        verification = build_claim_verification_report(method_evidence, claim_map)
        report = build_evidence_sufficiency_report(method_evidence, verification)
        decision = critique_evidence_sufficiency(report, evidence_revision_round=0, max_evidence_revision_rounds=1)

        focus = build_evidence_repair_focus(
            decision=decision,
            report=report,
            claim_verification=verification,
            claim_map=claim_map,
            symbol_index=_symbol_index(),
            source_decision="/tmp/decision.json",
        )
        overlay = focus_to_retrieval_overlay(focus)

        self.assertEqual(focus.focus_claim_ids, ["C2"])
        self.assertEqual(focus.missing_evidence_claim_ids, ["C2"])
        self.assertIn("C2: The encoder has unsupported extra behavior.", focus.claim_queries)
        self.assertEqual(focus.priority_paths, ["src/encoder.py"])
        self.assertEqual(focus.claim_targets[0].claim_id, "C2")
        self.assertEqual(focus.claim_targets[0].candidates[0].symbol, "Encoder.extra_behavior")
        self.assertEqual(focus.symbol_targets[0]["claim_id"], "C2")
        self.assertIn("C2: The encoder has unsupported extra behavior.", overlay["search_keywords"])
        self.assertEqual(overlay["priority_paths"], ["src/encoder.py"])
        self.assertEqual(overlay["claim_targets"][0]["candidates"][0]["path"], "src/encoder.py")
        self.assertEqual(overlay["focus_claim_ids"], ["C2"])

    def test_repair_focus_round_trips_json(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        verification = build_claim_verification_report(method_evidence, claim_map)
        report = build_evidence_sufficiency_report(method_evidence, verification)
        decision = critique_evidence_sufficiency(report, evidence_revision_round=0, max_evidence_revision_rounds=1)
        focus = build_evidence_repair_focus(
            decision=decision,
            report=report,
            claim_verification=verification,
            claim_map=claim_map,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_evidence_repair_focus.json"
            write_evidence_repair_focus(path, focus)
            loaded = load_evidence_repair_focus(path)

        self.assertEqual(loaded.mode, "evidence-repair-focus")
        self.assertEqual(loaded.focus_claim_ids, ["C2"])


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo",
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
                        description="Feature encoder uses attention.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                    )
                ],
            )
        ],
    )


def _claim_map() -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder uses attention.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The encoder has unsupported extra behavior.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E404"],
            ),
        ]
    )


def _symbol_index() -> SymbolIndexReport:
    return SymbolIndexReport(
        project_root="/tmp/demo",
        indexed_files=1,
        indexed_symbols=1,
        candidates=[
            SymbolIndexEntry(
                path="src/encoder.py",
                symbol="Encoder.extra_behavior",
                kind="function",
                start_line=10,
                end_line=20,
                parent="Encoder",
                docstring="Encoder unsupported extra behavior implementation.",
                score=2.0,
                reasons=["keyword:encoder"],
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
