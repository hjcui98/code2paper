from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evidence_sufficiency import (
    build_evidence_sufficiency_report,
    critique_evidence_sufficiency,
    evidence_sufficiency_trace,
    load_evidence_sufficiency_report,
    write_evidence_sufficiency_report,
)
from code2paper.agentic.evidence_repair import focus_to_retrieval_overlay, load_evidence_repair_focus
from code2paper.agentic.graph_evidence_nodes import evidence_sufficiency_node
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport, write_symbol_index
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


class AgenticEvidenceSufficiencyTests(unittest.TestCase):
    def test_report_summarizes_verified_claim_support(self) -> None:
        verification = build_claim_verification_report(_method_evidence(), _claim_map())

        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        self.assertTrue(report.hard_gate_passed)
        self.assertEqual(report.safe_claim_ids, ["C1"])
        self.assertEqual(report.caveated_claim_ids, ["C2"])
        self.assertEqual(report.unsupported_claim_ids, ["C3"])
        self.assertEqual(report.missing_evidence_claim_ids, ["C3"])
        self.assertEqual(report.support_rate, 0.5)
        self.assertIn("exclude_unsupported_claims_or_return_to_analysis", report.recommended_actions)

    def test_deterministic_decision_uses_revision_budget_before_grounding_with_exclusions(self) -> None:
        verification = build_claim_verification_report(_method_evidence(), _claim_map())
        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        repair = critique_evidence_sufficiency(report, evidence_revision_round=0, max_evidence_revision_rounds=1)
        no_budget = critique_evidence_sufficiency(report, evidence_revision_round=1, max_evidence_revision_rounds=1)

        self.assertEqual(repair.recommended_next, "analysis")
        self.assertEqual(repair.decision, "return_to_analysis")
        self.assertEqual(no_budget.recommended_next, "grounding")
        self.assertEqual(no_budget.decision, "proceed_with_exclusions")

    def test_model_proposal_is_safety_merged_against_budget_and_hard_gate(self) -> None:
        verification = build_claim_verification_report(_method_evidence(), _claim_map())
        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        decision, trace = evidence_sufficiency_trace(
            report,
            evidence_revision_round=1,
            max_evidence_revision_rounds=1,
            decision_provider=lambda _prompt: {
                "decision": "return_to_analysis",
                "recommended_next": "analysis",
                "rationale": "Model wants another analysis pass.",
                "focus_claim_ids": ["C3", "C404"],
            },
        )

        self.assertEqual(decision.recommended_next, "grounding")
        self.assertEqual(decision.focus_claim_ids, ["C3"])
        self.assertEqual(trace.node, "evidence_sufficiency")
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertTrue(any("rewritten" in note or "authoritative" in note for note in trace.safety_notes))

    def test_trace_prompt_exposes_evidence_sufficiency_attention(self) -> None:
        verification = build_claim_verification_report(_method_evidence(), _claim_map())
        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        _decision, trace = evidence_sufficiency_trace(report, evidence_revision_round=0, max_evidence_revision_rounds=1)

        attention = trace.prompt.inputs["evidence_sufficiency_attention"]
        self.assertEqual(attention["safe_claim_ids"], ["C1"])
        self.assertEqual(attention["caveated_claim_ids"], ["C2"])
        self.assertEqual(attention["repair_focus_claim_ids"], ["C3"])
        self.assertEqual(attention["missing_evidence_claim_ids"], ["C3"])
        self.assertEqual(attention["revision_budget_remaining"], 1)
        guidance = trace.prompt.inputs["stage_tool_guidance"]
        self.assertIn("analysis", guidance)

    def test_graph_writes_model_selected_evidence_repair_focus(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        verification = build_claim_verification_report(method_evidence, claim_map)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            method_output(root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(root, "evidence").write_text(method_evidence.model_dump_json(), encoding="utf-8")
            method_output(root, "claims").write_text(claim_map.model_dump_json(), encoding="utf-8")
            verification_path = artifact_dir(root, "04_evidence") / "agentic_claim_verification.json"
            verification_path.write_text(verification.model_dump_json(), encoding="utf-8")
            symbol_index_path = artifact_dir(root, "02_intake") / "agentic_symbol_index.json"
            write_symbol_index(symbol_index_path, _symbol_index())
            state = AgenticRunState(
                project_root=root,
                out_root=root,
                project_id="demo",
                artifacts={
                    "evidence": str(method_output(root, "evidence")),
                    "claims": str(method_output(root, "claims")),
                    "claim_verification": str(verification_path),
                    "symbol_index": str(symbol_index_path),
                },
                max_evidence_revision_rounds=1,
            )

            result = evidence_sufficiency_node(
                decision_provider=lambda _prompt: {
                    "decision": "return_to_analysis",
                    "recommended_next": "analysis",
                    "rationale": "repair unsupported extra behavior before grounding",
                    "focus_claim_ids": ["C3", "C404"],
                }
            )(state.model_dump(mode="json"))

            updated = AgenticRunState.model_validate(result)
            focus = load_evidence_repair_focus(updated.artifacts["evidence_repair_focus"])
            overlay = focus_to_retrieval_overlay(focus)

        self.assertEqual(updated.next_node, "analysis")
        self.assertEqual(focus.focus_claim_ids, ["C3"])
        self.assertEqual(focus.priority_paths, ["src/encoder_extra.py"])
        self.assertEqual(overlay["focus_claim_ids"], ["C3"])
        self.assertEqual(overlay["claim_targets"][0]["candidates"][0]["symbol"], "Encoder.extra_behavior")

    def test_report_blocks_when_no_writable_claims_exist(self) -> None:
        verification = build_claim_verification_report(
            _method_evidence(),
            ClaimEvidenceMap(
                claims=[
                    ClaimEvidenceItem(
                        claim_id="C3",
                        claim_text="Unsupported extra behavior.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E404"],
                    )
                ]
            ),
        )
        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        decision, _trace = evidence_sufficiency_trace(report)

        self.assertFalse(report.hard_gate_passed)
        self.assertEqual(decision.recommended_next, "blocked")
        self.assertEqual(decision.decision, "block_evidence_insufficient")

    def test_report_round_trips_json(self) -> None:
        verification = build_claim_verification_report(_method_evidence(), _claim_map())
        report = build_evidence_sufficiency_report(_method_evidence(), verification)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_evidence_sufficiency_report.json"
            write_evidence_sufficiency_report(path, report)
            loaded = load_evidence_sufficiency_report(path)

        self.assertEqual(loaded.mode, "evidence-sufficiency-report")
        self.assertEqual(loaded.safe_claim_ids, ["C1"])


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
                claim_text="The encoder exposes partial weighting.",
                support_status=SupportStatus.PARTIAL,
                evidence_ids=["E1"],
            ),
            ClaimEvidenceItem(
                claim_id="C3",
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
                path="src/encoder_extra.py",
                symbol="Encoder.extra_behavior",
                kind="function",
                start_line=10,
                end_line=20,
                parent="Encoder",
                docstring="Encoder unsupported extra behavior implementation.",
                score=4.0,
                reasons=["keyword:encoder"],
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
