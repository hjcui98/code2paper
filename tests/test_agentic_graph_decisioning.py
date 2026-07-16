from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decisioning import AgenticDecisionPrompt
from code2paper.agentic.graph import (
    _analysis_repair_router_node,
    _coverage_critic_node,
    _figure_planner_node,
    _revision_router_node,
    _route_after_analysis_repair_router,
    _route_after_figure_planner,
)
from code2paper.agentic.retrieval import CoverageItem, RetrievalCoverageReport
from code2paper.core.output_names import method_output
from code2paper.core.schemas import ClaimEvidenceItem, ClaimEvidenceMap, Mechanism, MethodEvidence, MethodStageEvidence, SupportStatus


class AgenticGraphDecisioningTests(unittest.TestCase):
    def test_analysis_repair_router_returns_to_intake_for_unbound_repair_tasks_with_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "analysis_repair_tasks.json"
            tasks_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "claim_id": "C2",
                                "recommended_next": "rescan_candidate_code",
                                "candidates": [{"path": "src/model.py", "evidence_ids": []}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                max_retrieval_rounds=1,
                artifacts={"analysis_repair_tasks": str(tasks_path)},
            )

            updated = AgenticRunState.model_validate(_analysis_repair_router_node()(state.model_dump(mode="json")))
            decision_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(updated.next_node, "intake")
        self.assertEqual(_route_after_analysis_repair_router(updated.model_dump(mode="json")), "intake")
        self.assertEqual(updated.loop_counters["retrieval"], 1)
        self.assertEqual(updated.decisions[-1].node, "analysis_repair_router")
        self.assertEqual(updated.decisions[-1].decision, "rescan_candidate_code")
        self.assertIn("analysis_repair_router_decision_trace", updated.decisions[-1].artifact_keys)
        self.assertEqual(decision_payload["recommended_next"], "intake")
        self.assertEqual(decision_payload["unbound_task_count"], 1)
        self.assertEqual(trace_payload["node"], "analysis_repair_router")
        self.assertEqual(trace_payload["provider_status"], "deterministic_fallback")

    def test_analysis_repair_router_continues_to_evidence_for_existing_repair_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "analysis_repair_tasks.json"
            tasks_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "claim_id": "C2",
                                "recommended_next": "reassess_existing_evidence",
                                "candidates": [{"path": "src/model.py", "evidence_ids": ["E1"]}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                max_retrieval_rounds=1,
                artifacts={"analysis_repair_tasks": str(tasks_path)},
            )

            updated = AgenticRunState.model_validate(_analysis_repair_router_node()(state.model_dump(mode="json")))
            decision_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(updated.next_node, "evidence")
        self.assertEqual(_route_after_analysis_repair_router(updated.model_dump(mode="json")), "evidence")
        self.assertNotIn("retrieval", updated.loop_counters)
        self.assertEqual(updated.decisions[-1].decision, "reassess_existing_repair_task_evidence")
        self.assertEqual(decision_payload["recommended_next"], "evidence")
        self.assertEqual(decision_payload["task_count"], 1)
        self.assertEqual(trace_payload["final_decision"]["recommended_next"], "evidence")

    def test_analysis_repair_router_rewrites_model_evidence_route_when_unbound_tasks_have_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "analysis_repair_tasks.json"
            tasks_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "claim_id": "C2",
                                "recommended_next": "rescan_candidate_code",
                                "candidates": [{"path": "src/model.py", "evidence_ids": []}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            prompts: list[AgenticDecisionPrompt] = []
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                max_retrieval_rounds=1,
                artifacts={"analysis_repair_tasks": str(tasks_path)},
            )

            updated = AgenticRunState.model_validate(
                _analysis_repair_router_node(
                    decision_provider=lambda prompt: (
                        prompts.append(prompt)
                        or {
                            "decision": "skip_rescan",
                            "recommended_next": "evidence",
                            "rationale": "Model thinks evidence freeze can reassess it.",
                        }
                    )
                )(state.model_dump(mode="json"))
            )
            decision_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["analysis_repair_router_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(prompts[0].node, "analysis_repair_router")
        self.assertEqual(updated.next_node, "intake")
        self.assertEqual(updated.loop_counters["retrieval"], 1)
        self.assertEqual(decision_payload["recommended_next"], "intake")
        self.assertEqual(decision_payload["decision"], "rescan_candidate_code")
        attention = prompts[0].inputs["analysis_repair_attention"]
        self.assertEqual(attention["task_count"], 1)
        self.assertEqual(attention["unbound_task_count"], 1)
        self.assertEqual(attention["retrieval_budget_remaining"], 1)
        self.assertEqual(attention["unbound_tasks"][0]["claim_id"], "C2")
        self.assertEqual(attention["unbound_tasks"][0]["candidate_paths"], ["src/model.py"])
        self.assertEqual(trace_payload["provider_status"], "model_proposal_merged")
        self.assertEqual(trace_payload["parsed_proposal"]["recommended_next"], "evidence")
        self.assertEqual(trace_payload["final_decision"]["recommended_next"], "intake")
        self.assertTrue(any("rewritten" in note for note in trace_payload["safety_notes"]))

    def test_coverage_critic_node_uses_injected_decision_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            coverage_path = root / "coverage.json"
            coverage_path.write_text(
                RetrievalCoverageReport(
                    overall_score=1.0,
                    covered_targets=1,
                    items=[
                        CoverageItem(
                            target_id="RT1",
                            query="covered target",
                            support_status="covered",
                            matched_paths=["train.py"],
                        )
                    ],
                ).model_dump_json(),
                encoding="utf-8",
            )
            prompts: list[AgenticDecisionPrompt] = []

            def provider(prompt: AgenticDecisionPrompt):
                prompts.append(prompt)
                return {
                    "decision": "rescan_intake",
                    "recommended_next": "intake",
                    "rationale": "Model wants an extra pass over optimizer symbols.",
                    "recommended_symbols": ["build_optimizer"],
                }

            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                max_retrieval_rounds=1,
                artifacts={"retrieval_coverage": str(coverage_path)},
            )

            updated = AgenticRunState.model_validate(
                _coverage_critic_node(decision_provider=provider)(state.model_dump(mode="json"))
            )
            decision_payload = json.loads(Path(updated.artifacts["coverage_critic_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["coverage_critic_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(prompts[0].node, "coverage_critic")
        self.assertIsNotNone(prompts[0].inputs["retrieval_decision_context"])
        self.assertIsNotNone(prompts[0].inputs["retrieval_rescan_plan"])
        self.assertIsNotNone(prompts[0].inputs["retrieval_rescan_report"])
        self.assertIsNotNone(prompts[0].inputs["retrieval_summary"])
        tool_guidance = prompts[0].inputs["stage_tool_guidance"]
        self.assertIn("intake", tool_guidance)
        self.assertIn("analysis", tool_guidance)
        self.assertIn("evidence", tool_guidance)
        self.assertIn("retrieval_summary", tool_guidance["intake"]["produced_outputs"])
        self.assertIn("hard evidence gate", tool_guidance["evidence"]["invocation_contract"])
        self.assertIn("retrieval_decision_context", updated.artifacts)
        self.assertIn("retrieval_rescan_plan", updated.artifacts)
        self.assertIn("retrieval_rescan_report", updated.artifacts)
        self.assertIn("retrieval_summary", updated.artifacts)
        self.assertEqual(updated.next_node, "intake")
        self.assertEqual(updated.loop_counters["retrieval"], 1)
        self.assertEqual(updated.decisions[-1].node, "coverage_critic")
        self.assertIn("build_optimizer", decision_payload["recommended_symbols"])
        self.assertEqual(trace_payload["node"], "coverage_critic")
        self.assertEqual(trace_payload["provider_status"], "model_proposal_merged")
        self.assertEqual(trace_payload["parsed_proposal"]["recommended_next"], "intake")
        self.assertEqual(trace_payload["final_decision"]["recommended_next"], "intake")

    def test_revision_router_node_rejects_provider_rendering_without_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompts: list[AgenticDecisionPrompt] = []
            state = AgenticRunState(project_root=Path("."), out_root=root)

            updated = AgenticRunState.model_validate(
                _revision_router_node(
                    decision_provider=lambda prompt: (
                        prompts.append(prompt)
                        or {
                            "decision": "rendering",
                            "recommended_next": "rendering",
                            "rationale": "Model says the draft is ready.",
                        }
                    )
                )(state.model_dump(mode="json"))
            )
            decision_payload = json.loads(Path(updated.artifacts["revision_router_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["revision_router_decision_trace"]).read_text(encoding="utf-8"))
            context_payload = json.loads(Path(updated.artifacts["revision_decision_context"]).read_text(encoding="utf-8"))

        self.assertIsNotNone(prompts[0].inputs["revision_decision_context"])
        self.assertEqual(context_payload["mode"], "revision-decision-context")
        self.assertEqual(updated.next_node, "validation")
        self.assertEqual(updated.decisions[-1].decision, "run_validation")
        self.assertIn("Rendering cannot bypass validation", decision_payload["rationale"])
        self.assertEqual(trace_payload["node"], "revision_router")
        self.assertEqual(trace_payload["parsed_proposal"]["recommended_next"], "rendering")
        self.assertEqual(trace_payload["final_decision"]["recommended_next"], "validation")
        self.assertTrue(any("rewritten" in note for note in trace_payload["safety_notes"]))

    def test_revision_router_rewrites_model_tool_selection_when_stage_inputs_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompts: list[AgenticDecisionPrompt] = []
            state = AgenticRunState(project_root=Path("."), out_root=root)

            updated = AgenticRunState.model_validate(
                _revision_router_node(
                    decision_provider=lambda prompt: (
                        prompts.append(prompt)
                        or {
                            "decision": "revise_authoring",
                            "recommended_next": "authoring",
                            "selected_stage": "authoring",
                            "rationale": "Model wants to rewrite before validation.",
                        }
                    )
                )(state.model_dump(mode="json"))
            )
            trace_payload = json.loads(Path(updated.artifacts["revision_router_decision_trace"]).read_text(encoding="utf-8"))

        selection_context = prompts[0].inputs["stage_tool_selection_context"]
        authoring = next(item for item in selection_context["stages"] if item["stage"] == "authoring")
        self.assertFalse(authoring["can_invoke"])
        self.assertIn("evidence", authoring["missing_required_inputs"])
        self.assertEqual(updated.next_node, "validation")
        self.assertEqual(trace_payload["parsed_proposal"]["selected_stage"], "authoring")
        self.assertEqual(trace_payload["final_decision"]["selected_stage"], "validation")
        self.assertTrue(any("selected stage" in note for note in trace_payload["safety_notes"]))

    def test_revision_router_keeps_model_tool_selection_when_stage_inputs_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prompts: list[AgenticDecisionPrompt] = []
            ready_artifacts = {
                "evidence": "method_evidence.json",
                "claims": "claim_map.json",
                "claim_verification": "claim_verification.json",
                "evidence_sufficiency_report": "sufficiency.json",
                "evidence_sufficiency_decision_trace": "sufficiency_trace.json",
                "grounding_context": "grounding.md",
                "validation_manifest": "validation.json",
                "fidelity": "fidelity.json",
            }
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                blocked_reason="fidelity_validation_failed",
                artifacts=ready_artifacts,
                max_authoring_revision_rounds=1,
            )

            updated = AgenticRunState.model_validate(
                _revision_router_node(
                    decision_provider=lambda prompt: (
                        prompts.append(prompt)
                        or {
                            "decision": "revise_authoring",
                            "recommended_next": "authoring",
                            "selected_stage": "authoring",
                            "rationale": "Revise the method text against validator feedback.",
                        }
                    )
                )(state.model_dump(mode="json"))
            )
            trace_payload = json.loads(Path(updated.artifacts["revision_router_decision_trace"]).read_text(encoding="utf-8"))

        selection_context = prompts[0].inputs["stage_tool_selection_context"]
        authoring = next(item for item in selection_context["stages"] if item["stage"] == "authoring")
        self.assertTrue(authoring["can_invoke"])
        self.assertEqual(authoring["missing_required_inputs"], [])
        self.assertEqual(updated.next_node, "authoring")
        self.assertEqual(trace_payload["final_decision"]["selected_stage"], "authoring")

    def test_figure_planner_node_filters_model_proposal_to_frozen_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = AgenticRunState(project_root=Path("."), out_root=root)
            evidence_path = method_output(state.method_root, "evidence")
            claims_path = method_output(state.method_root, "claims")
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            method_evidence = MethodEvidence(
                project_id="demo",
                method_name="Demo",
                method_goal="Explain the supported implementation step.",
                implementation_scope="core implementation",
                stages=[
                    MethodStageEvidence(
                        stage_id="S1",
                        name="Encode",
                        purpose="Extract evidence-backed features.",
                        mechanisms=[
                            Mechanism(
                                mechanism_id="MECH1",
                                description="Supported implementation step.",
                                support_status=SupportStatus.SUPPORTED,
                                evidence_ids=["E1"],
                            )
                        ],
                    )
                ],
            )
            claim_map = ClaimEvidenceMap(
                claims=[
                    ClaimEvidenceItem(
                        claim_id="C1",
                        claim_text="Supported implementation step.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                        mechanism_ids=["MECH1"],
                    )
                ]
            )
            evidence_path.write_text(method_evidence.model_dump_json(indent=2), encoding="utf-8")
            claims_path.write_text(claim_map.model_dump_json(indent=2), encoding="utf-8")
            prompts: list[AgenticDecisionPrompt] = []
            state = state.model_copy(
                update={"artifacts": {"evidence": str(evidence_path), "claims": str(claims_path), "claim_verification": "missing"}}
            )

            updated = AgenticRunState.model_validate(
                _figure_planner_node(
                    decision_provider=lambda prompt: (
                        prompts.append(prompt)
                        or {
                            "rationale": "Add an extra unsupported node.",
                            "nodes": [
                                {
                                    "node_id": "N1",
                                    "stage_id": "S1",
                                    "label": "Encoded features",
                                    "claim_ids": ["C1", "C404"],
                                    "evidence_ids": ["E1", "E404"],
                                },
                                {"node_id": "N404", "stage_id": "S404", "evidence_ids": ["E404"]},
                            ],
                        }
                    )
                )(state.model_dump(mode="json"))
            )
            plan_payload = json.loads(Path(updated.artifacts["figure_plan"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["figure_plan_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(prompts[0].node, "figure_planner")
        self.assertEqual(updated.next_node, "invariant_audit")
        self.assertEqual(_route_after_figure_planner(updated.model_dump(mode="json")), "invariant_audit")
        self.assertEqual(updated.decisions[-1].node, "figure_planner")
        self.assertEqual(updated.decisions[-1].decision, "figure_plan_ready")
        self.assertEqual(plan_payload["nodes"][0]["claim_ids"], ["C1"])
        self.assertEqual(plan_payload["nodes"][0]["evidence_ids"], ["E1"])
        self.assertEqual(trace_payload["provider_status"], "model_proposal_merged")
        self.assertIn("figure_plan_decision_trace", updated.artifacts)


if __name__ == "__main__":
    unittest.main()
