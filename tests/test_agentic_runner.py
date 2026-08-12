from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.runner import (
    _reconcile_publication_quality_with_final_validation,
    build_agentic_run_summary,
    load_agentic_run_summary,
    run_agentic_code2paper,
)
from code2paper.agentic.publication_quality import (
    EpistemicSafetyMetricsV1,
    PublicationQualityReportV1,
    PublicationUtilityMetricsV1,
)
from code2paper.agentic.final_text_authorship import FinalTextAuthorshipLedgerV1
from code2paper.agentic.publication_method_writer import PublicationWriterRunResultV1
from code2paper.agentic.trust_contracts import TextEvidenceValidationReport
from code2paper.core.output_names import artifact_dir


class AgenticRunnerTests(unittest.TestCase):
    def test_runner_reconciles_pending_publication_quality_from_final_reverse_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            quality_path = root / "quality.json"
            validation_path = root / "validation.json"
            ledger_path = root / "ledger.json"
            writer_result_path = root / "writer_result.json"
            quality = PublicationQualityReportV1(
                status="incomplete",
                plan_gate_passed=True,
                final_integrity_gate_passed=False,
                safety=EpistemicSafetyMetricsV1(
                    authorship_gate_passed=True,
                    binding_gate_passed=True,
                    final_text_validation_status="pending",
                    hard_gate_passed=False,
                ),
                utility=PublicationUtilityMetricsV1(utility_gate_passed=True),
            )
            ledger = FinalTextAuthorshipLedgerV1(
                final_text_digest="sha256:final",
                hard_gate_passed=True,
            )
            validation = TextEvidenceValidationReport(
                status="passed",
                input_text_digest=ledger.final_text_digest,
                projection_digest="sha256:projection",
                checked_factual_claims=1,
                supported_claims=1,
            )
            quality_path.write_text(quality.model_dump_json(), encoding="utf-8")
            validation_path.write_text(validation.model_dump_json(), encoding="utf-8")
            ledger_path.write_text(ledger.model_dump_json(), encoding="utf-8")
            writer_result_path.write_text(
                PublicationWriterRunResultV1(
                    status="incomplete",
                    plan_digest="sha256:plan",
                    claim_digest="sha256:claims",
                ).model_dump_json(),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "publication_quality_report_v1": str(quality_path),
                    "text_evidence_validation": str(validation_path),
                    "final_text_authorship_ledger_v1": str(ledger_path),
                    "publication_writer_result_v1": str(writer_result_path),
                },
            )

            _reconcile_publication_quality_with_final_validation(state)
            reconciled = PublicationQualityReportV1.model_validate_json(
                quality_path.read_text(encoding="utf-8")
            )
            self.assertEqual(reconciled.status, "publication_ready")
            self.assertEqual(reconciled.safety.final_text_validation_status, "passed")
            self.assertTrue(reconciled.safety.hard_gate_passed)
            self.assertTrue(reconciled.final_integrity_gate_passed)
            writer_ready = PublicationWriterRunResultV1.model_validate_json(
                writer_result_path.read_text(encoding="utf-8")
            )
            self.assertEqual(writer_ready.status, "success")

            validation_path.write_text(validation.model_copy(update={
                "status": "failed",
                "supported_claims": 0,
                "unsupported_claims": 1,
            }).model_dump_json(), encoding="utf-8")
            quality_path.write_text(quality.model_dump_json(), encoding="utf-8")
            _reconcile_publication_quality_with_final_validation(state)
            failed = PublicationQualityReportV1.model_validate_json(
                quality_path.read_text(encoding="utf-8")
            )
            self.assertEqual(failed.status, "blocked")
            self.assertEqual(failed.safety.unsupported_positive_claims, 1)
            self.assertFalse(failed.final_integrity_gate_passed)
            writer_blocked = PublicationWriterRunResultV1.model_validate_json(
                writer_result_path.read_text(encoding="utf-8")
            )
            self.assertEqual(writer_blocked.status, "blocked")
            self.assertIn(
                "publication_final_reverse_validation_failed",
                writer_blocked.binding_failures,
            )

    def test_runner_blocks_when_invariant_audit_fails(self) -> None:
        def fake_graph(payload):
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
            ).model_dump(mode="json")

        with tempfile.TemporaryDirectory() as tmpdir:
            initial = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            result = run_agentic_code2paper(initial, graph_app=fake_graph)
            loaded = load_agentic_run_summary(result.summary_path)
            self.assertTrue(Path(result.state.artifacts["run_manifest"]).exists())
            run_manifest = json.loads(Path(result.state.artifacts["run_manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["terminal_state"], "BLOCKED")
            self.assertTrue(run_manifest["source_commit"])
            self.assertIsInstance(run_manifest["source_dirty"], bool)
            self.assertTrue(run_manifest["run_summary_digest"].startswith("sha256:"))

        self.assertEqual(result.summary.status, "blocked")
        self.assertEqual(result.summary.blocked_reason, "invariant_audit_failed")
        self.assertEqual(result.state.blocked_reason, "invariant_audit_failed")
        self.assertEqual(result.state.artifacts["agentic_run_summary"], str(result.summary_path))
        self.assertIn("agentic_decision_policy", result.summary.artifacts)
        self.assertIn("agentic_invariant_audit", result.summary.artifacts)
        self.assertIn("agentic_graph_catalog", result.summary.artifacts)
        self.assertIn("agentic_tool_catalog", result.summary.artifacts)
        self.assertIn("agentic_langchain_tool_manifest", result.summary.artifacts)
        self.assertIn("agentic_architecture_manifest", result.summary.artifacts)
        self.assertIn("agentic_contract_audit", result.summary.artifacts)
        self.assertIn("traceability_ledger", result.summary.artifacts)
        self.assertIn("agentic_run_readiness_report", result.summary.artifacts)
        self.assertIn("agentic_run_evaluation_report", result.summary.artifacts)
        self.assertIn("agentic_run_completion_report", result.summary.artifacts)
        self.assertIn("run_manifest", result.summary.artifacts)
        self.assertFalse(result.summary.invariant_audit_passed)
        self.assertGreater(result.summary.invariant_blocking_failures, 0)
        self.assertEqual(loaded.decisions[0].node, "fake_node")
        self.assertEqual(loaded.decisions[-1].node, "invariant_auditor")
        self.assertIn("traceability_ledger", loaded.decisions[-1].artifact_keys)
        self.assertEqual(loaded.artifacts["fake_artifact"].hash[:7], "sha256:")
        self.assertIn("fake_artifact", run_manifest["phase_outputs"])
        self.assertIn("agentic_decision_policy", run_manifest["phase_outputs"])
        self.assertIn("agentic_graph_catalog", run_manifest["phase_outputs"])
        self.assertIn("agentic_tool_catalog", run_manifest["phase_outputs"])
        self.assertIn("agentic_langchain_tool_manifest", run_manifest["phase_outputs"])
        self.assertIn("agentic_architecture_manifest", run_manifest["phase_outputs"])
        self.assertIn("agentic_contract_audit", run_manifest["phase_outputs"])
        self.assertIn("traceability_ledger", run_manifest["phase_outputs"])
        self.assertIn("agentic_invariant_audit", run_manifest["phase_outputs"])
        self.assertIn("agentic_run_readiness_report", run_manifest["phase_outputs"])
        self.assertIn("agentic_run_evaluation_report", run_manifest["phase_outputs"])
        self.assertIn("agentic_run_completion_report", run_manifest["phase_outputs"])
        self.assertIn("agentic_run_summary", run_manifest["phase_outputs"])

    def test_runner_allows_success_when_core_evidence_invariants_pass(self) -> None:
        def fake_graph(payload):
            state = AgenticRunState.model_validate(payload)
            evidence_path = artifact_dir(state.method_root, "04_evidence") / "method_evidence.json"
            claims_path = artifact_dir(state.method_root, "04_evidence") / "claim_evidence_map.json"
            verification_path = artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"
            evidence_path.write_text('{"project_id":"demo"}', encoding="utf-8")
            claims_path.write_text('{"claims":[]}', encoding="utf-8")
            verification_path.write_text('{"claims_with_missing_evidence":0,"claims":[]}', encoding="utf-8")
            return state.model_copy(
                update={
                    "artifacts": {
                        "evidence": str(evidence_path),
                        "claims": str(claims_path),
                        "claim_verification": str(verification_path),
                    },
                    "next_node": "rendering",
                }
            ).model_dump(mode="json")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_agentic_code2paper(
                AgenticRunState(project_root=Path("."), out_root=Path(tmpdir)),
                graph_app=fake_graph,
            )

        self.assertEqual(result.summary.status, "success")
        self.assertTrue(result.summary.invariant_audit_passed)
        self.assertEqual(result.summary.invariant_blocking_failures, 0)
        self.assertFalse(result.summary.blocked_reason)
        self.assertIn("agentic_decision_policy", result.state.artifacts)
        self.assertIn("agentic_graph_catalog", result.state.artifacts)
        self.assertIn("agentic_tool_catalog", result.state.artifacts)
        self.assertIn("agentic_langchain_tool_manifest", result.state.artifacts)
        self.assertIn("agentic_architecture_manifest", result.state.artifacts)
        self.assertIn("agentic_contract_audit", result.state.artifacts)
        self.assertIn("traceability_ledger", result.state.artifacts)
        self.assertIn("agentic_run_readiness_report", result.state.artifacts)
        self.assertIn("agentic_run_evaluation_report", result.state.artifacts)
        self.assertIn("agentic_run_completion_report", result.state.artifacts)
        self.assertIn("run_manifest", result.state.artifacts)

    def test_runner_summary_marks_blocked_state(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-runner"),
            blocked_reason="method_text_missing",
        )

        summary = build_agentic_run_summary(state)

        self.assertEqual(summary.status, "blocked")
        self.assertEqual(summary.blocked_reason, "method_text_missing")

    def test_runner_persists_all_agentic_budgets(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-runner"),
            max_retrieval_rounds=1,
            max_evidence_revision_rounds=2,
            max_authoring_revision_rounds=3,
            max_figure_revision_rounds=4,
            max_semantic_verifier_calls=5,
        )

        summary = build_agentic_run_summary(state)

        self.assertEqual(summary.budgets, state.budgets)

    def test_runner_surfaces_langgraph_dependency_guard(self) -> None:
        with patch("code2paper.agentic.runner.build_code2paper_graph", side_effect=RuntimeError("agentic extra missing")):
            with self.assertRaisesRegex(RuntimeError, "agentic extra"):
                run_agentic_code2paper(AgenticRunState(project_root=Path("."), out_root=Path("/tmp/agentic-runner")))

    def test_runner_forwards_decision_provider_to_graph_builder(self) -> None:
        def fake_provider(_prompt):
            return None

        with patch("code2paper.agentic.runner.build_legacy_stage_tool_registry", return_value={}), patch(
            "code2paper.agentic.runner.build_code2paper_graph",
            side_effect=RuntimeError("stop after graph build"),
        ) as build_graph:
            with self.assertRaisesRegex(RuntimeError, "stop after graph build"):
                run_agentic_code2paper(
                    AgenticRunState(project_root=Path("."), out_root=Path("/tmp/agentic-runner")),
                    decision_provider=fake_provider,
                )

        self.assertIs(build_graph.call_args.kwargs["decision_provider"], fake_provider)

    def test_runner_builds_llm_decision_provider_when_llm_provider_is_explicit(self) -> None:
        def fake_provider(_prompt):
            return None

        with patch("code2paper.agentic.runner.build_legacy_stage_tool_registry", return_value={}), patch(
            "code2paper.agentic.runner.build_llm_decision_provider",
            return_value=fake_provider,
        ) as build_provider, patch(
            "code2paper.agentic.runner.build_code2paper_graph",
            side_effect=RuntimeError("stop after graph build"),
        ) as build_graph:
            with self.assertRaisesRegex(RuntimeError, "stop after graph build"):
                run_agentic_code2paper(
                    AgenticRunState(
                        project_root=Path("."),
                        out_root=Path("/tmp/agentic-runner"),
                        llm_provider="openai",
                        llm_model="gpt-test",
                    )
                )

        self.assertEqual(build_provider.call_args.args[0].provider.value, "openai")
        self.assertEqual(build_provider.call_args.args[0].model, "gpt-test")
        self.assertIs(build_graph.call_args.kwargs["decision_provider"], fake_provider)


if __name__ == "__main__":
    unittest.main()
