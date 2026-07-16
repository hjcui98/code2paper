from __future__ import annotations

import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState, StageStatus, StageToolResult


class AgenticStateContractTests(unittest.TestCase):
    def test_successful_stage_result_clears_previous_blocked_reason(self) -> None:
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/demo"), blocked_reason="fidelity_validation_failed")
        result = StageToolResult(stage="authoring", status=StageStatus.SUCCESS)

        updated = state.with_result(result)

        self.assertEqual(updated.blocked_reason, "")


if __name__ == "__main__":
    unittest.main()
