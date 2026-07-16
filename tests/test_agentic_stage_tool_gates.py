from __future__ import annotations

import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.tools import build_stage_tool_registry


class AgenticStageToolGateTests(unittest.TestCase):
    def test_hard_gate_stage_blocks_before_handler_when_required_artifacts_are_missing(self) -> None:
        calls: list[str] = []
        registry = build_stage_tool_registry(
            {
                "evidence": lambda _state: calls.append("evidence")
                or StageToolResult(stage="evidence", status=StageStatus.SUCCESS)
            }
        )
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))

        result = registry["evidence"].invoke(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "missing_required_input_artifacts")
        self.assertIn("evidence_raw", result.summary)
        self.assertEqual(calls, [])

    def test_hard_gate_stage_invokes_handler_when_required_artifacts_are_present(self) -> None:
        registry = build_stage_tool_registry(
            {
                "evidence": lambda _state: StageToolResult(
                    stage="evidence",
                    status=StageStatus.SUCCESS,
                    artifacts={
                        "evidence": "/tmp/evidence.json",
                        "claims": "/tmp/claims.json",
                        "claim_verification": "/tmp/claim-verification.json",
                    },
                )
            }
        )
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-test"),
            artifacts={
                "evidence_raw": "/tmp/raw.json",
                "alignment": "/tmp/alignment.json",
                "analysis": "/tmp/analysis.json",
            },
        )

        result = registry["evidence"].invoke(state)

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(result.artifacts["evidence"], "/tmp/evidence.json")

    def test_hard_gate_stage_blocks_success_result_when_required_outputs_are_missing(self) -> None:
        registry = build_stage_tool_registry(
            {
                "evidence": lambda _state: StageToolResult(
                    stage="evidence",
                    status=StageStatus.SUCCESS,
                    artifacts={"evidence": "/tmp/evidence.json"},
                )
            }
        )
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-test"),
            artifacts={
                "evidence_raw": "/tmp/raw.json",
                "alignment": "/tmp/alignment.json",
                "analysis": "/tmp/analysis.json",
            },
        )

        result = registry["evidence"].invoke(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "missing_required_output_artifacts")
        self.assertIn("claims", result.summary)
        self.assertIn("claim_verification", result.summary)
        self.assertEqual(result.artifacts["evidence"], "/tmp/evidence.json")

    def test_non_hard_gate_stage_keeps_existing_flexible_invocation(self) -> None:
        registry = build_stage_tool_registry(
            {
                "intake": lambda _state: StageToolResult(
                    stage="intake",
                    status=StageStatus.SUCCESS,
                    artifacts={"retrieval_plan": "/tmp/plan.json"},
                )
            }
        )
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))

        result = registry["intake"].invoke(state)

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(result.artifacts["retrieval_plan"], "/tmp/plan.json")


if __name__ == "__main__":
    unittest.main()
