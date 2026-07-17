from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.graph_revision_nodes import revision_router_node
from code2paper.agentic.routing import route_revision


class AgenticRevisionBudgetTests(unittest.TestCase):
    def test_revision_router_blocks_repeated_validation_failure_after_one_revision(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/demo"),
            blocked_reason="fidelity_validation_failed",
            artifacts={"validation_manifest": "validation.json"},
            loop_counters={"revision": 1},
        )

        decision = route_revision(state)

        self.assertEqual(decision.recommended_next, "blocked")
        self.assertEqual(decision.decision, "blocked")

    def test_revision_router_node_counts_authoring_revision_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(
                project_root=Path("."),
                out_root=Path(tmpdir),
                blocked_reason="fidelity_validation_failed",
                artifacts={"validation_manifest": "validation.json"},
                max_authoring_revision_rounds=1,
            )

            updated = AgenticRunState.model_validate(revision_router_node()(state.model_dump(mode="json")))

        self.assertEqual(updated.next_node, "authoring")
        self.assertEqual(updated.loop_counters["revision"], 1)

    def test_revision_router_blocks_evidence_return_when_budget_is_exhausted(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/demo"),
            blocked_reason="text_claim_direct_evidence_missing",
            artifacts={"validation_manifest": "validation.json"},
            max_evidence_revision_rounds=1,
            loop_counters={"evidence_revision": 1},
        )

        decision = route_revision(state)

        self.assertEqual(decision.recommended_next, "blocked")
        self.assertEqual(decision.decision, "blocked")

    def test_revision_router_node_counts_analysis_as_evidence_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(
                project_root=Path("."),
                out_root=Path(tmpdir),
                blocked_reason="text_claim_direct_evidence_missing",
                artifacts={"validation_manifest": "validation.json"},
                max_evidence_revision_rounds=1,
            )

            updated = AgenticRunState.model_validate(revision_router_node()(state.model_dump(mode="json")))

        self.assertEqual(updated.next_node, "analysis")
        self.assertEqual(updated.loop_counters["evidence_revision"], 1)
        self.assertNotIn("revision", updated.loop_counters)


if __name__ == "__main__":
    unittest.main()
