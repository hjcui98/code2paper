from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.legacy_late_stage_tools import run_finalize
from code2paper.agentic.legacy_stage_tools import _run_rendering
from code2paper.agentic.tools import canonical_stage_tool_specs
from code2paper.core.output_names import artifact_dir, method_output
from tests.test_agentic_figure_planner import _claim_map, _method_evidence


def _authorize_pre_render(state: AgenticRunState) -> AgenticRunState:
    auth_dir = artifact_dir(state.method_root, "10_run")
    audit_path = auth_dir / "agentic_invariant_audit.json"
    ledger_path = auth_dir / "agentic_traceability_ledger.json"
    audit_path.write_text(json.dumps({"passed": True, "blocking_failures": 0, "checks": []}), encoding="utf-8")
    ledger_path.write_text(json.dumps({"hard_gate_passed": True}), encoding="utf-8")
    return state.model_copy(
        update={"artifacts": {"agentic_invariant_audit": str(audit_path), "traceability_ledger": str(ledger_path)}}
    )


class AgenticRenderAuthorizationTests(unittest.TestCase):
    def test_rendering_blocks_without_pre_render_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            text_path = method_output(state.method_root, "text_clean_md")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text("Evidence-backed method text.", encoding="utf-8")

            result = _run_rendering(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "pre_render_authorization_missing")
        self.assertIn("agentic_invariant_audit", result.summary)
        self.assertIn("traceability_ledger", result.summary)

    def test_rendering_writes_figure_plan_after_pre_render_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            method_output(state.method_root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(state.method_root, "evidence").write_text(
                _method_evidence().model_dump_json(indent=2),
                encoding="utf-8",
            )
            method_output(state.method_root, "claims").write_text(
                _claim_map().model_dump_json(indent=2),
                encoding="utf-8",
            )
            method_output(state.method_root, "text_md").write_text("# Method\n\nEvidence-backed draft.\n", encoding="utf-8")
            state = _authorize_pre_render(state)

            result = _run_rendering(state)
            plan_path = Path(result.artifacts["figure_plan"])
            trace_path = Path(result.artifacts["figure_plan_decision_trace"])
            manifest = json.loads(Path(result.artifacts["rendering_manifest"]).read_text(encoding="utf-8"))
            plan_exists = plan_path.exists()
            trace_exists = trace_path.exists()

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertTrue(plan_exists)
        self.assertTrue(trace_exists)
        self.assertEqual(manifest["figure"]["intent_path"], str(plan_path))
        self.assertEqual(manifest["figure"]["decision_trace_path"], str(trace_path))
        self.assertEqual(manifest["outputs"]["method_overview_intent"]["path"], str(plan_path))

    def test_finalize_blocks_without_pre_render_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            text_path = method_output(state.method_root, "text_clean_tex")
            text_path.parent.mkdir(parents=True, exist_ok=True)
            text_path.write_text("\\subsection{Method}\nEvidence-backed method text.", encoding="utf-8")

            result = run_finalize(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "pre_render_authorization_missing")
        self.assertIn("agentic_invariant_audit", result.summary)
        self.assertIn("traceability_ledger", result.summary)

    def test_finalize_writes_final_package_after_pre_render_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            text_tex = method_output(state.method_root, "text_clean_tex")
            text_tex.write_text("\\subsection{Overview}\nEvidence-backed method text.\n", encoding="utf-8")
            state = _authorize_pre_render(state)

            result = run_finalize(state)

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertIn("final_tex", result.artifacts)
        self.assertIn("final_pdf_report", result.artifacts)
        self.assertIn("finalize_manifest", result.artifacts)
        self.assertEqual(result.decisions[0].node, "finalize_packager")

    def test_rendering_and_finalize_specs_require_pre_render_authorization(self) -> None:
        specs = {spec.stage: spec for spec in canonical_stage_tool_specs()}

        self.assertIn("agentic_invariant_audit", specs["rendering"].input_artifacts)
        self.assertIn("traceability_ledger", specs["rendering"].input_artifacts)
        self.assertTrue(specs["rendering"].hard_gate)
        self.assertIn("agentic_invariant_audit", specs["finalize"].input_artifacts)
        self.assertIn("traceability_ledger", specs["finalize"].input_artifacts)
        self.assertTrue(specs["finalize"].hard_gate)


if __name__ == "__main__":
    unittest.main()
