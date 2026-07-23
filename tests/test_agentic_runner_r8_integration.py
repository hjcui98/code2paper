"""R8.1 runner integration tests.

Verifies that ``runner.py`` correctly records the R8.1 protocol
fields in the run summary (``trace_digest``, ``final_state_digest``,
``environment``, ``temperature``, ``source_authority_policy``,
``tool_call_trace_refs``) and optionally emits an R8 acceptance
report when ``CODE2PAPER_R8_ACCEPTANCE=1``.

These tests use synthetic graph apps (no GPU, no real Gemma) so
they run in the deterministic test environment.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.runner import (
    AgenticRunSummary,
    _R8_ENV_VARS,
    _merge_resume_summary_evidence,
    build_agentic_run_summary,
    run_agentic_code2paper,
)
from code2paper.agentic.r8_acceptance import (
    R8AcceptanceReport,
    compute_trace_digest,
    load_r8_acceptance_report,
    check_r8_acceptance_from_run_dir,
)
from code2paper.core.output_names import artifact_dir


def _make_state(tmpdir: Path, **overrides: Any) -> AgenticRunState:
    """Build a minimal AgenticRunState for testing."""

    return AgenticRunState(
        project_root=Path("."),
        out_root=Path(tmpdir),
        **overrides,
    )


def _decision(node: str = "fake_node", decision: str = "continue") -> AgentDecision:
    return AgentDecision(
        node=node,
        decision=decision,
        rationale="test rationale",
        artifact_keys=["fake_artifact"],
    )


class BuildAgenticRunSummaryR8Tests(unittest.TestCase):
    """Tests for R8.1 fields in ``build_agentic_run_summary``."""

    def test_summary_records_trace_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir), decisions=[_decision()])
            summary = build_agentic_run_summary(state)
            self.assertTrue(summary.trace_digest.startswith("sha256:"))
            self.assertEqual(summary.trace_digest, summary.trace_digest)

    def test_trace_digest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state1 = _make_state(Path(tmpdir), decisions=[_decision()])
            state2 = _make_state(Path(tmpdir), decisions=[_decision()])
            summary1 = build_agentic_run_summary(state1)
            summary2 = build_agentic_run_summary(state2)
            self.assertEqual(summary1.trace_digest, summary2.trace_digest)

    def test_trace_digest_changes_with_different_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state1 = _make_state(Path(tmpdir), decisions=[_decision(node="node_a")])
            state2 = _make_state(Path(tmpdir), decisions=[_decision(node="node_b")])
            summary1 = build_agentic_run_summary(state1)
            summary2 = build_agentic_run_summary(state2)
            self.assertNotEqual(summary1.trace_digest, summary2.trace_digest)

    def test_trace_digest_matches_compute_trace_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir), decisions=[_decision()])
            summary = build_agentic_run_summary(state, tool_call_trace_refs=["tc-1", "tc-2"])
            expected = compute_trace_digest(state.decisions, ["tc-1", "tc-2"])
            self.assertEqual(summary.trace_digest, expected)

    def test_summary_records_tool_call_trace_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            refs = ["tc-alpha", "tc-beta", "tc-gamma"]
            summary = build_agentic_run_summary(state, tool_call_trace_refs=refs)
            self.assertEqual(summary.tool_call_trace_refs, refs)

    def test_summary_records_empty_tool_call_trace_refs_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            summary = build_agentic_run_summary(state)
            self.assertEqual(summary.tool_call_trace_refs, [])

    def test_summary_records_final_state_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir), run_id="run-1")
            summary = build_agentic_run_summary(state)
            self.assertTrue(summary.final_state_digest.startswith("sha256:"))

    def test_final_state_digest_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state1 = _make_state(Path(tmpdir), run_id="run-x")
            state2 = _make_state(Path(tmpdir), run_id="run-x")
            summary1 = build_agentic_run_summary(state1)
            summary2 = build_agentic_run_summary(state2)
            self.assertEqual(summary1.final_state_digest, summary2.final_state_digest)

    def test_final_state_digest_changes_with_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state1 = _make_state(Path(tmpdir), run_id="run-x")
            state2 = _make_state(Path(tmpdir), run_id="run-y")
            summary1 = build_agentic_run_summary(state1)
            summary2 = build_agentic_run_summary(state2)
            self.assertNotEqual(summary1.final_state_digest, summary2.final_state_digest)

    def test_summary_records_environment_when_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            old = os.environ.get("CODE2PAPER_LLM_CACHE", "")
            try:
                os.environ["CODE2PAPER_LLM_CACHE"] = "0"
                summary = build_agentic_run_summary(state)
                self.assertEqual(summary.environment.get("CODE2PAPER_LLM_CACHE"), "0")
            finally:
                if old:
                    os.environ["CODE2PAPER_LLM_CACHE"] = old
                else:
                    os.environ.pop("CODE2PAPER_LLM_CACHE", None)

    def test_summary_environment_empty_when_no_vars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            # Keep this in lockstep with the runner's provenance allowlist.
            keys = _R8_ENV_VARS
            old = {key: os.environ.get(key) for key in keys}
            try:
                for k in keys:
                    os.environ.pop(k, None)
                summary = build_agentic_run_summary(state)
                self.assertEqual(summary.environment, {})
            finally:
                for key, value in old.items():
                    if value is not None:
                        os.environ[key] = value
                    else:
                        os.environ.pop(key, None)

    def test_summary_records_temperature_when_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            old = os.environ.get("CODE2PAPER_LLM_TEMPERATURE", "")
            try:
                os.environ["CODE2PAPER_LLM_TEMPERATURE"] = "0.0"
                summary = build_agentic_run_summary(state)
                self.assertEqual(summary.temperature, 0.0)
            finally:
                if old:
                    os.environ["CODE2PAPER_LLM_TEMPERATURE"] = old
                else:
                    os.environ.pop("CODE2PAPER_LLM_TEMPERATURE", None)

    def test_summary_records_resolved_role_sampling_envelope(self) -> None:
        """The summary distinguishes the writer retry ceiling from 8192 default."""

        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(
                Path(tmpdir), llm_provider="openai", llm_model="local-gemma"
            )
            env = {
                "CODE2PAPER_LLM_TEMPERATURE": "0",
                "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS": "12000",
                "CODE2PAPER_LLM_TEMPERATURE_INTENT_COMPILER": "0.20",
                "CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER": "0.70",
                "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER": "8192",
                "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED": "12288",
            }
            old = {key: os.environ.get(key) for key in env}
            try:
                os.environ.update(env)
                summary = build_agentic_run_summary(state)
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        self.assertEqual(summary.temperature_by_role["intent_compiler"], 0.20)
        self.assertEqual(summary.temperature_by_role["method_writer"], 0.70)
        self.assertEqual(summary.max_output_tokens_by_role["method_writer"], 8192)
        self.assertEqual(
            summary.max_output_tokens_by_role["method_writer_extended"], 12288
        )
        self.assertEqual(
            summary.max_output_tokens_by_role["method_cumulative_budget"], 24576
        )

    def test_summary_temperature_none_when_not_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir))
            old = os.environ.get("CODE2PAPER_LLM_TEMPERATURE", "")
            try:
                os.environ.pop("CODE2PAPER_LLM_TEMPERATURE", None)
                summary = build_agentic_run_summary(state)
                self.assertIsNone(summary.temperature)
            finally:
                if old:
                    os.environ["CODE2PAPER_LLM_TEMPERATURE"] = old

    def test_summary_records_run_id_and_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir), run_id="run-abc", project_id="proj-xyz")
            summary = build_agentic_run_summary(state)
            self.assertEqual(summary.run_id, "run-abc")
            self.assertEqual(summary.project_id, "proj-xyz")

    def test_repeated_resume_preserves_original_first_run_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = _make_state(Path(tmpdir), run_id="run-resume")
            first = build_agentic_run_summary(state)
            second_current = build_agentic_run_summary(state)
            second = _merge_resume_summary_evidence(second_current, first)
            self.assertEqual(
                second.resumed_from_final_state_digest,
                first.final_state_digest,
            )

            third_current = build_agentic_run_summary(state)
            third = _merge_resume_summary_evidence(third_current, second)
            self.assertEqual(
                third.resumed_from_final_state_digest,
                first.final_state_digest,
            )


class RunAgenticCode2PaperR8Tests(unittest.TestCase):
    """Tests for R8 acceptance report generation in ``run_agentic_code2paper``."""

    def _fake_graph_with_tool_trace(self, payload: dict[str, Any]) -> dict[str, Any]:
        """A fake graph that adds a tool_call_trace_refs channel."""

        state = AgenticRunState.model_validate(payload)
        artifact_path = artifact_dir(state.method_root, "10_run") / "fake_artifact.txt"
        artifact_path.write_text("ok", encoding="utf-8")
        return state.model_copy(
            update={
                "artifacts": {"fake_artifact": str(artifact_path)},
                "decisions": [
                    AgentDecision(
                        node="fake_node",
                        decision="continue",
                        rationale="fake graph completed",
                        artifact_keys=["fake_artifact"],
                    )
                ],
                "next_node": "rendering",
            }
        ).model_dump(mode="json") | {"tool_call_trace_refs": ["tc-1", "tc-2"]}

    def _fake_graph_with_accepted_intent_report(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Synthetic graph preserving the V3 Intent Agent provenance path."""

        state = AgenticRunState.model_validate(payload)
        artifact_path = artifact_dir(state.method_root, "10_run") / "intent.json"
        artifact_path.write_text(
            json.dumps({
                "attempted": True,
                "accepted": True,
                "enriched_graph_digest": "sha256:intent-fixture",
            }),
            encoding="utf-8",
        )
        return state.model_copy(update={
            "artifacts": {"intent_target_proposal_report_v1": str(artifact_path)},
            "decisions": [
                AgentDecision(
                    node="research_supervisor",
                    decision="SEARCH_SYMBOLS",
                    rationale="issue_driven:missing_anchor",
                )
            ],
        }).model_dump(mode="json") | {"tool_call_trace_refs": ["tc-1"]}

    def test_runner_extracts_tool_call_trace_refs_from_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
            self.assertEqual(result.summary.tool_call_trace_refs, ["tc-1", "tc-2"])

    def test_runner_records_trace_digest_in_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
            summary_path = result.summary_path
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertTrue(data["trace_digest"].startswith("sha256:"))
            self.assertEqual(data["tool_call_trace_refs"], ["tc-1", "tc-2"])

    def test_runner_records_final_state_digest_in_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
            data = json.loads(result.summary_path.read_text(encoding="utf-8"))
            self.assertTrue(data["final_state_digest"].startswith("sha256:"))

    def test_runner_does_not_emit_r8_report_when_flag_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
            self.assertNotIn("r8_acceptance_report", result.state.artifacts)

    def test_runner_emits_r8_report_when_flag_set(self) -> None:
        old = os.environ.get("CODE2PAPER_R8_ACCEPTANCE", "")
        try:
            os.environ["CODE2PAPER_R8_ACCEPTANCE"] = "1"
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
                result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
                report_path = result.state.artifacts.get("r8_acceptance_report", "")
                self.assertTrue(report_path, "r8_acceptance_report artifact should be set")
                self.assertTrue(Path(report_path).exists(), "R8 report file should exist")
                report = load_r8_acceptance_report(report_path)
                self.assertIsInstance(report, R8AcceptanceReport)
                self.assertEqual(report.mode, "r8-acceptance-v1")
                # The synthetic run has no claims/coverage/validation, so
                # most criteria fail; the report should record that.
                self.assertIn("gap_driven_tool_selection", report.criteria)
                self.assertIn("trace_reproducible", report.criteria)
        finally:
            if old:
                os.environ["CODE2PAPER_R8_ACCEPTANCE"] = old
            else:
                os.environ.pop("CODE2PAPER_R8_ACCEPTANCE", None)

    def test_runner_passes_intent_agent_provenance_into_r8_report(self) -> None:
        old = os.environ.get("CODE2PAPER_R8_ACCEPTANCE", "")
        try:
            os.environ["CODE2PAPER_R8_ACCEPTANCE"] = "1"
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
                result = run_agentic_code2paper(
                    initial, graph_app=self._fake_graph_with_accepted_intent_report
                )
                report = load_r8_acceptance_report(
                    result.state.artifacts["r8_acceptance_report"]
                )
                self.assertEqual(
                    report.criteria["typed_intent_proposal_accepted"].status,
                    "passed",
                )
        finally:
            if old:
                os.environ["CODE2PAPER_R8_ACCEPTANCE"] = old
            else:
                os.environ.pop("CODE2PAPER_R8_ACCEPTANCE", None)

    def test_runner_r8_report_trace_reproducible_passes(self) -> None:
        """When the runner emits an R8 report, ``trace_reproducible`` passes.

        The runner records the trace digest in the summary, then builds
        the R8 report using the same digest as both the recorded and
        recomputed value, so the reproducibility check passes.
        """

        old = os.environ.get("CODE2PAPER_R8_ACCEPTANCE", "")
        try:
            os.environ["CODE2PAPER_R8_ACCEPTANCE"] = "1"
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
                result = run_agentic_code2paper(initial, graph_app=self._fake_graph_with_tool_trace)
                report_path = result.state.artifacts["r8_acceptance_report"]
                report = load_r8_acceptance_report(report_path)
                self.assertEqual(report.criteria["trace_reproducible"].status, "passed")
        finally:
            if old:
                os.environ["CODE2PAPER_R8_ACCEPTANCE"] = old
            else:
                os.environ.pop("CODE2PAPER_R8_ACCEPTANCE", None)


class R8AcceptanceRunDirScannerTests(unittest.TestCase):
    """End-to-end tests for ``check_r8_acceptance_from_run_dir`` on runner output."""

    def _fake_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(payload)
        artifact_path = artifact_dir(state.method_root, "10_run") / "fake_artifact.txt"
        artifact_path.write_text("ok", encoding="utf-8")
        return state.model_copy(
            update={
                "artifacts": {"fake_artifact": str(artifact_path)},
                "decisions": [
                    AgentDecision(
                        node="research_supervisor",
                        decision="SEARCH_SYMBOLS",
                        rationale="issue_driven:missing_anchor",
                        artifact_keys=["fake_artifact"],
                    )
                ],
                "next_node": "rendering",
            }
        ).model_dump(mode="json") | {"tool_call_trace_refs": ["tc-1", "tc-2"]}

    def test_run_dir_scanner_loads_summary_from_runner_output(self) -> None:
        """``check_r8_acceptance_from_run_dir`` scans the runner's output directory."""

        old = os.environ.get("CODE2PAPER_R8_ACCEPTANCE", "")
        try:
            os.environ["CODE2PAPER_R8_ACCEPTANCE"] = "1"
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(
                    project_root=Path("."),
                    out_root=Path(tmpdir),
                    run_id="run-scanner-test",
                )
                result = run_agentic_code2paper(initial, graph_app=self._fake_graph)
                run_dir = artifact_dir(result.state.method_root, "10_run")
                scanned = check_r8_acceptance_from_run_dir(run_dir)
                # The scanner should load the decisions from the summary
                # and find the gap-driven tool selection.
                self.assertEqual(scanned.run_id, "run-scanner-test")
                self.assertIn("gap_driven_tool_selection", scanned.criteria)
                self.assertIn("trace_reproducible", scanned.criteria)
                # The scanner's trace digest should match the runner's.
                self.assertEqual(
                    scanned.criteria["trace_reproducible"].status,
                    "passed",
                )
        finally:
            if old:
                os.environ["CODE2PAPER_R8_ACCEPTANCE"] = old
            else:
                os.environ.pop("CODE2PAPER_R8_ACCEPTANCE", None)

    def test_run_dir_scanner_trace_reproducible_passes_with_runner_digest(self) -> None:
        """The scanner recomputes the trace digest and matches the runner's."""

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph)
            run_dir = artifact_dir(result.state.method_root, "10_run")
            scanned = check_r8_acceptance_from_run_dir(run_dir)
            self.assertEqual(
                scanned.criteria["trace_reproducible"].status, "passed"
            )
            self.assertIn("sha256:", scanned.criteria["trace_reproducible"].reason)

    def test_run_dir_scanner_finds_gap_driven_decision(self) -> None:
        """The scanner detects the gap-driven tool selection from decisions."""

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=self._fake_graph)
            run_dir = artifact_dir(result.state.method_root, "10_run")
            scanned = check_r8_acceptance_from_run_dir(run_dir)
            self.assertEqual(
                scanned.criteria["gap_driven_tool_selection"].status, "passed"
            )

    def test_two_runs_with_same_decisions_produce_same_trace_digest(self) -> None:
        """Two runs with the same decisions produce the same trace digest.

        The trace digest is based on decisions and tool-call trace refs
        only (not absolute paths), so two runs with the same decisions
        produce the same trace digest.  The final-state digest includes
        absolute artifact paths and is only compared between an original
        and resumed run in the same directory.
        """

        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            initial1 = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir1))
            initial2 = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir2))
            result1 = run_agentic_code2paper(initial1, graph_app=self._fake_graph)
            result2 = run_agentic_code2paper(initial2, graph_app=self._fake_graph)
            self.assertEqual(result1.summary.trace_digest, result2.summary.trace_digest)


if __name__ == "__main__":
    unittest.main()
