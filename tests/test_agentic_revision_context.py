from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.revision_context import (
    build_revision_decision_context,
    load_revision_decision_context,
    write_revision_decision_context,
)


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


class AgenticRevisionContextTests(unittest.TestCase):
    def test_revision_context_summarizes_fidelity_issues_for_authoring(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                blocked_reason="fidelity_validation_failed",
                artifacts={
                    "validation_manifest": _write_json(root / "validation.json", {"status": "blocked"}),
                    "fidelity": _write_json(
                        root / "fidelity.json",
                        {
                            "passed": False,
                            "issues": [
                                {
                                    "category": "claim",
                                    "severity": "high",
                                    "message": "Paragraph overstates claim C1.",
                                    "evidence_ids": ["E1"],
                                }
                            ],
                        },
                    ),
                },
            )

            context = build_revision_decision_context(state)

        self.assertEqual(context.recommended_next, "authoring")
        self.assertEqual(context.issue_count, 1)
        self.assertEqual(context.issues[0].source_artifact, "fidelity")
        self.assertIn("Paragraph overstates", context.summary)

    def test_revision_context_summarizes_traceability_failures_for_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                blocked_reason="invariant_audit_failed",
                artifacts={
                    "agentic_invariant_audit": _write_json(
                        root / "audit.json",
                        {
                            "passed": False,
                            "checks": [
                                {
                                    "name": "text_claim_traceability",
                                    "passed": False,
                                    "blocking": True,
                                    "message": "unknown evidence ids: E404",
                                }
                            ],
                        },
                    ),
                    "traceability_ledger": _write_json(
                        root / "ledger.json",
                        {
                            "hard_gate_passed": False,
                            "entries": [
                                {
                                    "entry_id": "text:P1",
                                    "trace_status": "missing_evidence",
                                    "evidence_ids": ["E404"],
                                    "notes": ["unknown evidence ids: E404"],
                                }
                            ],
                        },
                    ),
                },
            )

            context = build_revision_decision_context(state)

        self.assertEqual(context.recommended_next, "analysis")
        self.assertGreaterEqual(context.issue_count, 2)
        self.assertIn("return_to_analysis_or_retrieval_for_evidence_repair", context.recommended_actions)

    def test_revision_context_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "revision_decision_context.json"
            context = build_revision_decision_context(AgenticRunState(project_root=Path("."), out_root=root))
            write_revision_decision_context(path, context)
            loaded = load_revision_decision_context(path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.mode, "revision-decision-context")


if __name__ == "__main__":
    unittest.main()
