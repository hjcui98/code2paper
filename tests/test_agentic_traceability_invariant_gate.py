from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.invariant_audit import build_invariant_audit


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


class AgenticTraceabilityInvariantGateTests(unittest.TestCase):
    def test_audit_blocks_failed_traceability_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            artifacts = {
                "evidence": _write_json(root / "evidence.json", {"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}),
                "claims": _write_json(root / "claims.json", {"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}),
                "claim_verification": _write_json(
                    root / "claim_verification.json",
                    {"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]},
                ),
                "traceability_ledger": _write_json(
                    root / "agentic_traceability_ledger.json",
                    {
                        "hard_gate_passed": False,
                        "entries_with_missing_evidence": 1,
                        "entries_with_unknown_claims": 0,
                        "entries_with_forbidden_claims": 0,
                    },
                ),
            }
            state = AgenticRunState(project_root=Path("."), out_root=root, artifacts=artifacts)

            audit = build_invariant_audit(state)

        ledger_check = next(check for check in audit.checks if check.name == "traceability_ledger")
        self.assertFalse(ledger_check.passed)
        self.assertTrue(ledger_check.blocking)
        self.assertEqual(audit.blocking_failures, 1)
        self.assertIn("missing/unknown evidence", ledger_check.message)
        self.assertIn("rebuild_traceability_ledger_from_frozen_evidence", audit.recommended_actions)


if __name__ == "__main__":
    unittest.main()
