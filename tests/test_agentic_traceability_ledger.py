from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.traceability_ledger import (
    build_traceability_ledger,
    load_traceability_ledger,
    write_traceability_ledger,
)


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


class AgenticTraceabilityLedgerTests(unittest.TestCase):
    def test_ledger_maps_claims_text_and_figures_to_frozen_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "evidence": _write_json(
                        root / "evidence.json",
                        {"stages": [{"mechanisms": [{"mechanism_id": "M1", "evidence_ids": ["E1"]}]}]},
                    ),
                    "claims": _write_json(
                        root / "claims.json",
                        {"claims": [{"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]}]},
                    ),
                    "claim_verification": _write_json(
                        root / "claim_verification.json",
                        {"claims": [{"claim_id": "C1", "support_status": "supported"}]},
                    ),
                    "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": []}),
                    "text_claims": _write_json(
                        root / "text_claims.json",
                        {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]},
                    ),
                    "figure_plan": _write_json(
                        root / "method_overview.intent.json",
                        {
                            "hard_gate_passed": True,
                            "nodes": [{"node_id": "N1", "claim_ids": ["C1"], "evidence_ids": ["E1"]}],
                            "edges": [{"edge_id": "FE1", "evidence_ids": ["E1"]}],
                        },
                    ),
                },
            )

            ledger = build_traceability_ledger(state)

        self.assertTrue(ledger.hard_gate_passed)
        self.assertEqual(ledger.entries_with_missing_evidence, 0)
        self.assertEqual(ledger.entries_with_forbidden_claims, 0)
        entry_ids = {entry.entry_id for entry in ledger.entries}
        self.assertIn("claim:C1", entry_ids)
        self.assertIn("text:P1", entry_ids)
        self.assertIn("figure_node:N1", entry_ids)
        self.assertIn("figure_edge:FE1", entry_ids)
        self.assertEqual(ledger.recommended_actions, ["all_text_claim_and_figure_entries_trace_to_frozen_code_evidence"])

    def test_ledger_flags_unknown_evidence_and_unsupported_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                    "claims": _write_json(
                        root / "claims.json",
                        {
                            "claims": [
                                {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                                {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                            ]
                        },
                    ),
                    "claim_verification": _write_json(
                        root / "claim_verification.json",
                        {
                            "claims": [
                                {"claim_id": "C1", "support_status": "supported"},
                                {"claim_id": "C2", "support_status": "unsupported"},
                            ]
                        },
                    ),
                    "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                    "text_claims": _write_json(
                        root / "text_claims.json",
                        {"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C2"], "evidence_span_ids": ["E404"]}]},
                    ),
                },
            )

            ledger = build_traceability_ledger(state)

        self.assertFalse(ledger.hard_gate_passed)
        self.assertGreaterEqual(ledger.entries_with_missing_evidence, 1)
        self.assertGreaterEqual(ledger.entries_with_forbidden_claims, 1)
        text_entry = next(entry for entry in ledger.entries if entry.entry_id == "text:P1")
        self.assertEqual(text_entry.trace_status, "invalid_trace")
        self.assertTrue(any("unknown evidence ids: E404" in note for note in text_entry.notes))
        self.assertTrue(any("excluded or unsupported claim ids: C2" in note for note in text_entry.notes))

    def test_ledger_flags_figure_entries_without_verified_code_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                    "claims": _write_json(
                        root / "claims.json",
                        {
                            "claims": [
                                {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                                {"claim_id": "C2", "support_status": "unsupported", "evidence_ids": []},
                            ]
                        },
                    ),
                    "claim_verification": _write_json(
                        root / "claim_verification.json",
                        {
                            "claims": [
                                {"claim_id": "C1", "support_status": "supported"},
                                {"claim_id": "C2", "support_status": "unsupported"},
                            ]
                        },
                    ),
                    "authoring_constraints": _write_json(root / "authoring_constraints.json", {"excluded_claim_ids": ["C2"]}),
                    "figure_plan": _write_json(
                        root / "method_overview.intent.json",
                        {
                            "hard_gate_passed": True,
                            "nodes": [{"node_id": "N1", "claim_ids": ["C2"], "evidence_ids": ["E404"]}],
                            "edges": [{"edge_id": "FE1", "evidence_ids": ["E404"]}],
                        },
                    ),
                },
            )

            ledger = build_traceability_ledger(state)

        self.assertFalse(ledger.hard_gate_passed)
        self.assertGreaterEqual(ledger.entries_with_missing_evidence, 2)
        self.assertGreaterEqual(ledger.entries_with_forbidden_claims, 1)
        node_entry = next(entry for entry in ledger.entries if entry.entry_id == "figure_node:N1")
        edge_entry = next(entry for entry in ledger.entries if entry.entry_id == "figure_edge:FE1")
        self.assertEqual(node_entry.trace_status, "invalid_trace")
        self.assertEqual(edge_entry.trace_status, "missing_evidence")
        self.assertTrue(any("unknown evidence ids: E404" in note for note in node_entry.notes))
        self.assertTrue(any("excluded or unsupported claim ids: C2" in note for note in node_entry.notes))

    def test_forbidden_claim_inventory_is_nonblocking_when_final_trace_does_not_use_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."), out_root=root,
                artifacts={
                    "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                    "claims": _write_json(root / "claims.json", {"claims": [
                        {"claim_id": "C1", "support_status": "supported", "evidence_ids": ["E1"]},
                        {"claim_id": "C2", "support_status": "supported", "evidence_ids": ["E1"]},
                    ]}),
                    "claim_verification": _write_json(root / "verification.json", {"claims": [
                        {"claim_id": "C1", "support_status": "supported"},
                        {"claim_id": "C2", "support_status": "unsupported"},
                    ]}),
                    "authoring_constraints": _write_json(root / "constraints.json", {"excluded_claim_ids": []}),
                    "final_text_trace": _write_json(root / "trace.json", {"entries": [{
                        "atomic_claim_id": "FAC1", "projection_claim_ids": ["C1"],
                        "direct_evidence_ids": ["E1"], "verdict_status": "supported",
                    }]}),
                },
            )
            ledger = build_traceability_ledger(state)

        self.assertTrue(ledger.hard_gate_passed)
        inventory = next(item for item in ledger.entries if item.entry_id == "claim:C2")
        self.assertEqual(inventory.trace_status, "excluded_claim")
        self.assertEqual(ledger.entries_with_forbidden_claims, 0)

    def test_ledger_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=Path("."), out_root=root)
            path = root / "agentic_traceability_ledger.json"
            write_traceability_ledger(path, build_traceability_ledger(state))
            loaded = load_traceability_ledger(path)

        self.assertEqual(loaded.mode, "agentic-evidence-traceability-ledger")
        self.assertTrue(loaded.hard_gate_passed)


if __name__ == "__main__":
    unittest.main()
