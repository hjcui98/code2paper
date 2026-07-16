from __future__ import annotations

import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.graph import validation_router
from code2paper.agentic.retrieval import CoverageItem, RetrievalCoverageReport, SymbolIndexEntry, SymbolIndexReport
from code2paper.agentic.routing import critique_coverage, route_revision


def _state(**updates):
    base = {"project_root": Path("."), "out_root": Path("/tmp/code2paper-agentic-routing")}
    base.update(updates)
    return AgenticRunState(**base)


class AgenticRoutingTests(unittest.TestCase):
    def test_coverage_critic_requests_rescan_when_budget_remains(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.25,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="missing implementation",
                    support_status="missing",
                )
            ],
        )

        decision = critique_coverage(coverage, retrieval_round=0, max_retrieval_rounds=1)

        self.assertEqual(decision.decision, "rescan_intake")
        self.assertEqual(decision.recommended_next, "intake")

    def test_coverage_critic_uses_symbol_index_for_targeted_rescan_hints(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.25,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="training entrypoint",
                    support_status="missing",
                    missing_paths=["train.py"],
                )
            ],
        )
        symbol_index = SymbolIndexReport(
            project_root="/repo",
            indexed_files=1,
            indexed_symbols=1,
            candidates=[
                SymbolIndexEntry(
                    path="train.py",
                    symbol="main",
                    kind="function",
                    matched_target_ids=["RT1"],
                    score=4.0,
                )
            ],
        )

        decision = critique_coverage(
            coverage,
            symbol_index=symbol_index,
            retrieval_round=0,
            max_retrieval_rounds=1,
        )

        self.assertEqual(decision.decision, "rescan_intake")
        self.assertIn("train.py", decision.recommended_paths)
        self.assertIn("main", decision.recommended_symbols)
        self.assertIn("training entrypoint", decision.recommended_queries)
        self.assertIn("symbol_index", decision.artifact_keys)
        self.assertIn("target_symbols=main", decision.rationale)

    def test_coverage_critic_proceeds_with_caveats_when_rescan_disabled(self) -> None:
        coverage = RetrievalCoverageReport(
            overall_score=0.25,
            missing_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="missing implementation",
                    support_status="missing",
                )
            ],
        )

        decision = critique_coverage(coverage, retrieval_round=0, max_retrieval_rounds=0)

        self.assertEqual(decision.decision, "proceed_with_caveats")
        self.assertEqual(decision.recommended_next, "analysis")
        self.assertIn("unsupported claims", decision.rationale)

    def test_revision_router_runs_validation_before_rendering(self) -> None:
        decision = route_revision(_state())

        self.assertEqual(decision.decision, "run_validation")
        self.assertEqual(decision.recommended_next, "validation")

    def test_revision_router_sends_fidelity_failures_to_authoring(self) -> None:
        state = _state(
            blocked_reason="fidelity_validation_failed",
            artifacts={"validation_manifest": "validation.json"},
            max_authoring_revision_rounds=1,
        )

        decision = route_revision(state)

        self.assertEqual(decision.decision, "revise_authoring")
        self.assertEqual(validation_router(state), "authoring")

    def test_revision_router_allows_rendering_after_validation_manifest(self) -> None:
        decision = route_revision(_state(artifacts={"validation_manifest": "validation.json"}))

        self.assertEqual(decision.decision, "rendering")
        self.assertEqual(decision.recommended_next, "rendering")


if __name__ == "__main__":
    unittest.main()
