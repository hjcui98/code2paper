from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.contracts import AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.contract_audit import build_agentic_contract_audit, load_agentic_contract_audit, write_agentic_contract_audit
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.decision_policy import build_agentic_decision_policy
from code2paper.agentic.graph import (
    _authoring_planner_node,
    _evidence_sufficiency_node,
    _invariant_audit_node,
    _route_after_authoring_planner,
    _route_after_evidence_sufficiency,
    _route_after_invariant_audit,
    _route_after_rendering,
    _route_after_revision_router,
    evidence_gate,
    validation_router,
)
from code2paper.agentic.graph_catalog import build_graph_catalog, load_graph_catalog, write_graph_catalog
from code2paper.agentic.graph_stage_nodes import stage_node
from code2paper.agentic.langchain_tools import build_langchain_stage_tool_manifest
from code2paper.agentic.legacy_stage_tools import build_legacy_stage_tool_registry
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport
from code2paper.agentic.tools import (
    StageToolInvokeInput,
    build_langchain_stage_tools,
    build_stage_tool_registry,
    build_tool_catalog,
    canonical_stage_tool_specs,
    load_tool_catalog,
    write_tool_catalog,
)
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


class AgenticContractsTests(unittest.TestCase):
    def test_canonical_specs_include_evidence_gate_contracts(self) -> None:
        specs = {spec.stage: spec for spec in canonical_stage_tool_specs()}

        self.assertIn("evidence", specs)
        self.assertIn("authoring", specs)
        self.assertIn("retrieval_plan", specs["intake"].output_artifacts)
        self.assertIn("symbol_index", specs["intake"].output_artifacts)
        self.assertIn("retrieval_coverage", specs["intake"].output_artifacts)
        self.assertIn("retrieval_decision_context", specs["intake"].output_artifacts)
        self.assertIn("retrieval_rescan_plan", specs["intake"].output_artifacts)
        self.assertIn("retrieval_rescan_report", specs["intake"].output_artifacts)
        self.assertIn("retrieval_summary", specs["intake"].output_artifacts)
        self.assertIn("retrieval_strategy_manifest", specs["intake"].output_artifacts)
        self.assertIn("analysis_repair_tasks", specs["analysis"].output_artifacts)
        self.assertIn("claim_verification", specs["evidence"].output_artifacts)
        self.assertIn("claim_verification", specs["evidence"].required_output_artifacts)
        self.assertTrue(specs["evidence"].hard_gate)
        self.assertIn("evidence", specs["authoring"].input_artifacts)
        self.assertIn("claims", specs["authoring"].input_artifacts)
        self.assertIn("claim_verification", specs["authoring"].input_artifacts)
        self.assertIn("authoring_constraints", specs["authoring"].output_artifacts)
        self.assertIn("authoring_context", specs["authoring"].output_artifacts)
        self.assertIn("authoring_plan_decision_trace", specs["authoring"].output_artifacts)
        self.assertIn("claim_verification", specs["rendering"].input_artifacts)
        self.assertIn("figure_plan", specs["rendering"].output_artifacts)
        self.assertIn("figure_plan", specs["rendering"].required_output_artifacts)
        self.assertIn("method_overview_svg", specs["rendering"].output_artifacts)
        self.assertIn("post_render_audit", specs["rendering"].output_artifacts)
        self.assertIn("figure_plan_decision_trace", specs["rendering"].output_artifacts)
        self.assertIn("finalize", specs)
        self.assertIn("final_tex", specs["finalize"].output_artifacts)
        self.assertIn("finalize_manifest", specs["finalize"].required_output_artifacts)

    def test_stage_tool_without_handler_blocks_explicitly(self) -> None:
        registry = build_stage_tool_registry()
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))

        result = registry["intake"].invoke(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "stage_handler_not_configured")

    def test_stage_node_records_invoked_tool_contract(self) -> None:
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

        updated = AgenticRunState.model_validate(stage_node("intake", registry)(state.model_dump(mode="json")))

        self.assertEqual(updated.decisions[-1].node, "stage_tool:intake")
        self.assertEqual(updated.decisions[-1].decision, "invoked")
        self.assertIn("agentic_tool_catalog", updated.decisions[-1].artifact_keys)
        self.assertIn("retrieval_plan", updated.decisions[-1].artifact_keys)
        self.assertIn("evidence_policy=retrieves_evidence", updated.decisions[-1].rationale)

    def test_stage_tool_exports_langchain_structured_tool_with_schema(self) -> None:
        fake_tools_module = types.ModuleType("langchain_core.tools")

        class FakeStructuredTool:
            @classmethod
            def from_function(cls, **kwargs):
                return types.SimpleNamespace(**kwargs)

        fake_tools_module.StructuredTool = FakeStructuredTool
        old_parent = sys.modules.get("langchain_core")
        old_tools = sys.modules.get("langchain_core.tools")
        sys.modules["langchain_core"] = types.ModuleType("langchain_core")
        sys.modules["langchain_core.tools"] = fake_tools_module
        try:
            registry = build_stage_tool_registry(
                {
                    "intake": lambda _state: StageToolResult(
                        stage="intake",
                        status=StageStatus.SUCCESS,
                        artifacts={"retrieval_plan": "/tmp/plan.json"},
                    )
                }
            )
            tool = registry["intake"].to_langchain_tool()
            state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))

            payload = tool.func(state=state.model_dump(mode="json"))

            self.assertEqual(tool.name, "code2paper_intake")
            self.assertIs(tool.args_schema, StageToolInvokeInput)
            self.assertEqual(tool.metadata["stage"], "intake")
            self.assertEqual(tool.metadata["evidence_policy"], "retrieves_evidence")
            self.assertTrue(tool.metadata["allow_model_decision"])
            self.assertIn("resolved_author_markers", tool.metadata["input_artifacts"])
            self.assertIn("retrieval_coverage", tool.metadata["output_artifacts"])
            self.assertEqual(tool.metadata["required_output_artifacts"], [])
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["artifacts"]["retrieval_plan"], "/tmp/plan.json")
        finally:
            if old_parent is None:
                sys.modules.pop("langchain_core", None)
            else:
                sys.modules["langchain_core"] = old_parent
            if old_tools is None:
                sys.modules.pop("langchain_core.tools", None)
            else:
                sys.modules["langchain_core.tools"] = old_tools

    def test_build_langchain_stage_tools_exports_registry(self) -> None:
        fake_tools_module = types.ModuleType("langchain_core.tools")

        class FakeStructuredTool:
            @classmethod
            def from_function(cls, **kwargs):
                return types.SimpleNamespace(**kwargs)

        fake_tools_module.StructuredTool = FakeStructuredTool
        old_parent = sys.modules.get("langchain_core")
        old_tools = sys.modules.get("langchain_core.tools")
        sys.modules["langchain_core"] = types.ModuleType("langchain_core")
        sys.modules["langchain_core.tools"] = fake_tools_module
        try:
            tools = build_langchain_stage_tools(build_stage_tool_registry())

            self.assertEqual(len(tools), len(canonical_stage_tool_specs()))
            self.assertTrue(all(tool.args_schema is StageToolInvokeInput for tool in tools))
        finally:
            if old_parent is None:
                sys.modules.pop("langchain_core", None)
            else:
                sys.modules["langchain_core"] = old_parent
            if old_tools is None:
                sys.modules.pop("langchain_core.tools", None)
            else:
                sys.modules["langchain_core.tools"] = old_tools

    def test_tool_catalog_serializes_evidence_policies_and_hard_gates(self) -> None:
        catalog = build_tool_catalog()

        self.assertEqual(catalog.mode, "agentic-tool-catalog")
        self.assertEqual(catalog.tool_count, len(canonical_stage_tool_specs()))
        self.assertIn("evidence", catalog.hard_gates)
        self.assertIn("validation", catalog.hard_gates)
        self.assertEqual(catalog.evidence_policies["evidence"], "freezes_evidence")
        self.assertIn("intake", catalog.model_decision_stages)

    def test_tool_catalog_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_tool_catalog.json"
            write_tool_catalog(path, build_tool_catalog())
            loaded = load_tool_catalog(path)

        self.assertEqual(loaded.tool_count, len(canonical_stage_tool_specs()))
        self.assertEqual(loaded.tools[0].stage, "input_resolution")

    def test_graph_catalog_records_topology_and_evidence_gates(self) -> None:
        catalog = build_graph_catalog()

        self.assertEqual(catalog.mode, "agentic-graph-catalog")
        self.assertEqual(catalog.entry_point, "input_resolution")
        self.assertIn("finalize", catalog.terminal_nodes)
        self.assertIn("blocked", catalog.terminal_nodes)
        route_map = {route.source: route for route in catalog.conditional_routes}
        self.assertEqual(route_map["evidence_sufficiency"].routes["grounding"], "grounding")
        self.assertEqual(route_map["evidence_sufficiency"].routes["analysis"], "analysis")
        self.assertEqual(route_map["analysis_repair_router"].routes["intake"], "intake")
        self.assertEqual(route_map["analysis_repair_router"].routes["evidence"], "evidence")
        self.assertEqual(route_map["revision_router"].routes["figure_planner"], "figure_planner")
        self.assertNotIn("invariant_audit", route_map["revision_router"].routes)
        self.assertNotIn("rendering", route_map["revision_router"].routes)
        self.assertEqual(route_map["figure_planner"].routes["invariant_audit"], "invariant_audit")
        self.assertEqual(route_map["invariant_audit"].routes["rendering"], "rendering")
        nodes = {node.name: node for node in catalog.nodes}
        self.assertIn("retrieval_decision_context", nodes["coverage_critic"].input_artifacts)
        self.assertIn("retrieval_rescan_plan", nodes["coverage_critic"].input_artifacts)
        self.assertIn("retrieval_rescan_report", nodes["coverage_critic"].input_artifacts)
        self.assertIn("coverage_critic_decision_trace", nodes["coverage_critic"].output_artifacts)
        self.assertIn("retrieval_rescan_plan", nodes["coverage_critic"].output_artifacts)
        self.assertIn("retrieval_rescan_report", nodes["coverage_critic"].output_artifacts)
        self.assertIn("analysis_repair_tasks", nodes["analysis_repair_router"].input_artifacts)
        self.assertIn("analysis_repair_router_decision", nodes["analysis_repair_router"].output_artifacts)
        self.assertIn("analysis_repair_router_decision_trace", nodes["analysis_repair_router"].output_artifacts)
        self.assertTrue(nodes["analysis_repair_router"].allow_model_decision)
        self.assertIn("symbol_index", nodes["evidence_sufficiency"].input_artifacts)
        self.assertIn("evidence_sufficiency_report", nodes["evidence_sufficiency"].output_artifacts)
        self.assertIn("evidence_repair_focus", nodes["evidence_sufficiency"].output_artifacts)
        self.assertTrue(nodes["evidence_sufficiency"].allow_model_decision)
        self.assertIn("authoring_plan_decision_trace", nodes["authoring_planner"].output_artifacts)
        self.assertTrue(nodes["authoring_planner"].allow_model_decision)
        self.assertIn("revision_decision_context", nodes["revision_router"].input_artifacts)
        self.assertIn("revision_router_decision_trace", nodes["revision_router"].output_artifacts)
        self.assertIn("figure_plan_decision_trace", nodes["figure_planner"].output_artifacts)
        self.assertTrue(nodes["figure_planner"].allow_model_decision)
        self.assertIn("traceability_ledger", nodes["invariant_audit"].output_artifacts)
        gates = {gate.name: gate for gate in catalog.evidence_gates}
        self.assertIn("claim_verification", gates["frozen_evidence_gate"].required_artifacts)
        self.assertIn("analysis_repair_router_decision_trace", gates["analysis_repair_router_gate"].required_artifacts)
        self.assertIn("evidence_sufficiency_decision_trace", gates["evidence_sufficiency_gate"].required_artifacts)
        self.assertIn("authoring_context", gates["authoring_context_gate"].required_artifacts)
        self.assertIn("authoring_plan_decision_trace", gates["authoring_context_gate"].required_artifacts)
        self.assertIn("revision_decision_context", gates["revision_context_gate"].required_artifacts)
        self.assertIn("traceability_ledger", gates["pre_render_invariant_gate"].required_artifacts)
        self.assertIn("text_claims", gates["pre_render_invariant_gate"].required_artifacts)
        self.assertIn("figure_plan_decision_trace", gates["pre_render_invariant_gate"].required_artifacts)
        self.assertIn("figure_plan_decision_trace", gates["figure_evidence_gate"].required_artifacts)
        self.assertEqual(catalog.loop_limits["retrieval"], "state.max_retrieval_rounds")
        self.assertEqual(catalog.loop_limits["evidence_revision"], "state.max_evidence_revision_rounds")
        self.assertEqual(catalog.loop_limits["authoring_revision"], "state.max_authoring_revision_rounds")
        self.assertEqual(catalog.loop_limits["figure_revision"], "state.max_figure_revision_rounds")
        self.assertEqual(catalog.loop_limits["semantic_verifier"], "state.max_semantic_verifier_calls")

    def test_graph_catalog_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_graph_catalog.json"
            write_graph_catalog(path, build_graph_catalog())
            loaded = load_graph_catalog(path)

        self.assertEqual(loaded.nodes[0].name, "input_resolution")
        self.assertEqual(loaded.conditional_routes[0].source, "coverage_critic")

    def test_contract_audit_passes_for_canonical_catalogs(self) -> None:
        audit = build_agentic_contract_audit(
            graph_catalog=build_graph_catalog(),
            decision_policy=build_agentic_decision_policy(),
            tool_catalog=build_tool_catalog(),
            langchain_tool_manifest=build_langchain_stage_tool_manifest(),
        )

        self.assertTrue(audit.passed)
        self.assertEqual(audit.recommended_actions, ["agentic_contracts_are_consistent"])
        self.assertIn("policy_prompt_hard_rules_resolve", {check.name for check in audit.checks})
        self.assertIn("langchain_tool_manifest_alignment", {check.name for check in audit.checks})

    def test_contract_audit_catches_langchain_tool_manifest_drift(self) -> None:
        manifest = build_langchain_stage_tool_manifest()
        tools = [
            tool.model_copy(update={"evidence_policy": "none"})
            if tool.stage == "rendering"
            else tool
            for tool in manifest.tools
        ]
        drifted_manifest = manifest.model_copy(update={"tools": tools})

        audit = build_agentic_contract_audit(
            graph_catalog=build_graph_catalog(),
            decision_policy=build_agentic_decision_policy(),
            tool_catalog=build_tool_catalog(),
            langchain_tool_manifest=drifted_manifest,
        )

        manifest_check = next(check for check in audit.checks if check.name == "langchain_tool_manifest_alignment")
        self.assertFalse(audit.passed)
        self.assertFalse(manifest_check.passed)
        self.assertIn("rendering", manifest_check.message)
        self.assertIn("evidence_policy mismatch", manifest_check.message)

    def test_contract_audit_catches_model_decision_schema_drift(self) -> None:
        with patch(
            "code2paper.agentic.contract_audit.supported_llm_decision_nodes",
            return_value=(
                "coverage_critic",
                "analysis_repair_router",
                "evidence_sufficiency",
                "revision_router",
                "authoring_planner",
            ),
        ):
            audit = build_agentic_contract_audit(
                graph_catalog=build_graph_catalog(),
                decision_policy=build_agentic_decision_policy(),
                tool_catalog=build_tool_catalog(),
            )

        schema_check = next(check for check in audit.checks if check.name == "model_decision_schema_coverage")
        self.assertFalse(audit.passed)
        self.assertFalse(schema_check.passed)
        self.assertIn("figure_planner", schema_check.message)

    def test_contract_audit_catches_required_prompt_input_drift(self) -> None:
        policy = build_agentic_decision_policy()
        policies = [
            node.model_copy(update={"required_prompt_inputs": [*node.required_prompt_inputs, "missing_attention_key"]})
            if node.node == "coverage_critic"
            else node
            for node in policy.node_policies
        ]
        drifted_policy = policy.model_copy(update={"node_policies": policies})

        audit = build_agentic_contract_audit(
            graph_catalog=build_graph_catalog(),
            decision_policy=drifted_policy,
            tool_catalog=build_tool_catalog(),
        )

        prompt_check = next(check for check in audit.checks if check.name == "policy_prompt_inputs_resolve")
        self.assertFalse(audit.passed)
        self.assertFalse(prompt_check.passed)
        self.assertIn("coverage_critic", prompt_check.message)
        self.assertIn("missing_attention_key", prompt_check.message)

    def test_contract_audit_catches_policy_hard_rule_prompt_drift(self) -> None:
        with patch(
            "code2paper.agentic.contract_audit.supported_decision_prompt_hard_rule_nodes",
            return_value=(
                "coverage_critic",
                "analysis_repair_router",
                "evidence_sufficiency",
                "revision_router",
                "authoring_planner",
            ),
        ):
            audit = build_agentic_contract_audit(
                graph_catalog=build_graph_catalog(),
                decision_policy=build_agentic_decision_policy(),
                tool_catalog=build_tool_catalog(),
            )

        hard_rule_check = next(check for check in audit.checks if check.name == "policy_prompt_hard_rules_resolve")
        self.assertFalse(audit.passed)
        self.assertFalse(hard_rule_check.passed)
        self.assertIn("figure_planner", hard_rule_check.message)

    def test_contract_audit_catches_policy_route_drift(self) -> None:
        policy = build_agentic_decision_policy()
        policies = [
            node.model_copy(update={"allowed_next_nodes": [*node.allowed_next_nodes, "rendering"]})
            if node.node == "revision_router"
            else node
            for node in policy.node_policies
        ]
        drifted_policy = policy.model_copy(update={"node_policies": policies})

        audit = build_agentic_contract_audit(
            graph_catalog=build_graph_catalog(),
            decision_policy=drifted_policy,
            tool_catalog=build_tool_catalog(),
        )

        route_check = next(check for check in audit.checks if check.name == "policy_routes_match_graph")
        self.assertFalse(audit.passed)
        self.assertFalse(route_check.passed)
        self.assertIn("revision_router", route_check.message)
        self.assertIn("rendering", route_check.message)

    def test_contract_audit_round_trips_to_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_contract_audit.json"
            write_agentic_contract_audit(
                path,
                build_agentic_contract_audit(
                    graph_catalog=build_graph_catalog(),
                    decision_policy=build_agentic_decision_policy(),
                    tool_catalog=build_tool_catalog(),
                ),
            )
            loaded = load_agentic_contract_audit(path)

        self.assertTrue(loaded.passed)
        self.assertEqual(loaded.mode, "agentic-contract-audit")

    def test_legacy_stage_registry_exposes_finalize_handler(self) -> None:
        registry = build_legacy_stage_tool_registry()

        self.assertIn("finalize", registry)
        self.assertEqual(registry["finalize"].spec.stage, "finalize")

    def test_agentic_state_merges_stage_result_artifacts(self) -> None:
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))
        result = StageToolResult(
            stage="evidence",
            status=StageStatus.SUCCESS,
            artifacts={"evidence": "/tmp/evidence.json", "claims": "/tmp/claims.json"},
        )

        updated = state.with_result(result)

        self.assertEqual(updated.artifacts["evidence"], "/tmp/evidence.json")
        self.assertEqual(updated.artifacts["claims"], "/tmp/claims.json")

    def test_evidence_gate_blocks_authoring_until_frozen_artifacts_exist(self) -> None:
        state = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))
        incomplete = state.model_copy(update={"artifacts": {"evidence": "e.json", "claims": "c.json"}})
        ready = state.model_copy(
            update={"artifacts": {"evidence": "e.json", "claims": "c.json", "claim_verification": "v.json"}}
        )

        self.assertEqual(evidence_gate(state), "evidence")
        self.assertEqual(evidence_gate(incomplete), "evidence")
        self.assertEqual(evidence_gate(ready), "grounding")

    def test_validation_router_sends_fidelity_failures_to_authoring(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-test"),
            blocked_reason="fidelity_validation_failed",
            max_authoring_revision_rounds=1,
        )

        self.assertEqual(validation_router(state), "authoring")

    def test_revision_router_routes_rendering_through_figure_planner(self) -> None:
        state = AgenticRunState(
            project_root=Path("."),
            out_root=Path("/tmp/code2paper-agentic-test"),
            next_node="rendering",
        )

        self.assertEqual(_route_after_revision_router(state.model_dump(mode="json")), "figure_planner")

    def test_evidence_sufficiency_node_rejects_unbudgeted_analysis_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            method_root = root / "artifacts"
            evidence = method_output(method_root, "evidence")
            claims = method_output(method_root, "claims")
            verification = method_root / "04_evidence" / "agentic_claim_verification.json"
            symbol_index = method_root / "02_intake" / "agentic_symbol_index.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            verification.parent.mkdir(parents=True, exist_ok=True)
            symbol_index.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                MethodEvidence(
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
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            claims.write_text(
                ClaimEvidenceMap(
                    claims=[
                        ClaimEvidenceItem(
                            claim_id="C1",
                            claim_text="Supported implementation step.",
                            support_status=SupportStatus.SUPPORTED,
                            evidence_ids=["E1"],
                        )
                    ]
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            verification.write_text(
                json.dumps(
                    {
                        "mode": "claim-verification",
                        "checked_claims": 1,
                        "supported_claims": 1,
                        "partial_claims": 0,
                        "unsupported_claims": 0,
                        "claims_with_missing_evidence": 0,
                        "hard_gate_passed": True,
                        "recommended_actions": ["all_claims_safe_for_evidence_constrained_authoring"],
                        "claims": [
                            {
                                "claim_id": "C1",
                                "claim_text": "Supported implementation step.",
                                "source": "",
                                "support_status": "supported",
                                "evidence_ids": ["E1"],
                                "missing_evidence_ids": [],
                                "caveats": [],
                                "recommended_action": "allow_in_prose",
                                "rationale": "Claim is supported by frozen code evidence.",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={"evidence": str(evidence), "claims": str(claims), "claim_verification": str(verification)},
            )

            updated = AgenticRunState.model_validate(
                _evidence_sufficiency_node(
                    decision_provider=lambda _prompt: {
                        "decision": "return_to_analysis",
                        "recommended_next": "analysis",
                        "rationale": "Model wants another evidence pass.",
                        "focus_claim_ids": ["C1"],
                    }
                )(state.model_dump(mode="json"))
            )
            decision_payload = json.loads(Path(updated.artifacts["evidence_sufficiency_decision"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["evidence_sufficiency_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(updated.next_node, "grounding")
        self.assertEqual(_route_after_evidence_sufficiency(updated.model_dump(mode="json")), "grounding")
        self.assertEqual(updated.decisions[-1].node, "evidence_sufficiency")
        self.assertEqual(decision_payload["recommended_next"], "grounding")
        self.assertEqual(trace_payload["node"], "evidence_sufficiency")
        self.assertTrue(any("rewritten" in note or "authoritative" in note for note in trace_payload["safety_notes"]))

    def test_evidence_sufficiency_node_writes_repair_focus_for_budgeted_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            method_root = root / "artifacts"
            evidence = method_output(method_root, "evidence")
            claims = method_output(method_root, "claims")
            verification = method_root / "04_evidence" / "agentic_claim_verification.json"
            symbol_index = method_root / "02_intake" / "agentic_symbol_index.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            verification.parent.mkdir(parents=True, exist_ok=True)
            symbol_index.parent.mkdir(parents=True, exist_ok=True)
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
                    ),
                    ClaimEvidenceItem(
                        claim_id="C2",
                        claim_text="Unsupported extra behavior.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E404"],
                    ),
                ]
            )
            evidence.write_text(method_evidence.model_dump_json(indent=2), encoding="utf-8")
            claims.write_text(claim_map.model_dump_json(indent=2), encoding="utf-8")
            verification.write_text(
                build_claim_verification_report(method_evidence, claim_map).model_dump_json(indent=2),
                encoding="utf-8",
            )
            symbol_index.write_text(
                SymbolIndexReport(
                    project_root=str(root),
                    indexed_files=1,
                    indexed_symbols=1,
                    candidates=[
                        SymbolIndexEntry(
                            path="src/encoder.py",
                            symbol="Encoder.extra_behavior",
                            kind="function",
                            start_line=12,
                            end_line=24,
                            parent="Encoder",
                            docstring="Unsupported extra behavior implementation.",
                            score=2.0,
                            reasons=["keyword:unsupported"],
                        )
                    ],
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                max_evidence_revision_rounds=1,
                artifacts={
                    "evidence": str(evidence),
                    "claims": str(claims),
                    "claim_verification": str(verification),
                    "symbol_index": str(symbol_index),
                },
            )

            updated = AgenticRunState.model_validate(_evidence_sufficiency_node()(state.model_dump(mode="json")))
            repair_payload = json.loads(Path(updated.artifacts["evidence_repair_focus"]).read_text(encoding="utf-8"))

        self.assertEqual(updated.next_node, "analysis")
        self.assertEqual(updated.loop_counters["evidence_revision"], 1)
        self.assertEqual(repair_payload["focus_claim_ids"], ["C2"])
        self.assertIn("C2: Unsupported extra behavior.", repair_payload["claim_queries"])
        self.assertEqual(repair_payload["priority_paths"], ["src/encoder.py"])
        self.assertEqual(repair_payload["claim_targets"][0]["candidates"][0]["symbol"], "Encoder.extra_behavior")

    def test_authoring_planner_node_safety_merges_provider_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            method_root = root / "artifacts"
            evidence = method_output(method_root, "evidence")
            claims = method_output(method_root, "claims")
            verification = method_root / "04_evidence" / "agentic_claim_verification.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            verification.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                MethodEvidence(
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
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            claims.write_text(
                ClaimEvidenceMap(
                    claims=[
                        ClaimEvidenceItem(
                            claim_id="C1",
                            claim_text="Supported implementation step.",
                            support_status=SupportStatus.SUPPORTED,
                            evidence_ids=["E1"],
                        )
                    ]
                ).model_dump_json(indent=2),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={"evidence": str(evidence), "claims": str(claims), "claim_verification": str(verification)},
            )

            updated = AgenticRunState.model_validate(
                _authoring_planner_node(
                    decision_provider=lambda _prompt: {
                        "rationale": "Group the verified implementation step.",
                        "sections": [
                            {
                                "heading": "Model proposed section",
                                "claim_ids": ["C1", "C404"],
                                "evidence_ids": ["E404"],
                            }
                        ],
                    }
                )(state.model_dump(mode="json"))
            )
            plan_payload = json.loads(Path(updated.artifacts["authoring_plan"]).read_text(encoding="utf-8"))
            trace_payload = json.loads(Path(updated.artifacts["authoring_plan_decision_trace"]).read_text(encoding="utf-8"))

        self.assertEqual(updated.next_node, "authoring")
        self.assertEqual(_route_after_authoring_planner(updated.model_dump(mode="json")), "authoring")
        self.assertEqual(updated.decisions[-1].node, "authoring_planner")
        self.assertEqual(plan_payload["sections"][0]["claim_ids"], ["C1"])
        self.assertEqual(plan_payload["sections"][0]["evidence_ids"], ["E1"])
        self.assertEqual(trace_payload["node"], "authoring_planner")
        self.assertEqual(trace_payload["provider_status"], "model_proposal_merged")
        self.assertTrue(any("Rewrote proposed evidence ids" in note for note in trace_payload["safety_notes"]))

    def test_invariant_audit_node_blocks_before_rendering_on_trace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            evidence = root / "evidence.json"
            claims = root / "claims.json"
            verification = root / "claim_verification.json"
            sufficiency = root / "evidence_sufficiency_report.json"
            sufficiency_trace = root / "evidence_sufficiency_trace.json"
            constraints = root / "authoring_constraints.json"
            context = root / "authoring_context.json"
            plan = root / "authoring_plan.json"
            text = root / "method.md"
            validation = root / "validation_manifest.json"
            evidence.write_text(json.dumps({"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}), encoding="utf-8")
            claims.write_text(json.dumps({"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}), encoding="utf-8")
            verification.write_text(
                json.dumps({"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]}),
                encoding="utf-8",
            )
            sufficiency.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "safe_claim_ids": ["C1"],
                        "caveated_claim_ids": [],
                        "support_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            sufficiency_trace.write_text(
                json.dumps(
                    {
                        "mode": "agentic-decision-trace",
                        "node": "evidence_sufficiency",
                        "provider_status": "deterministic_fallback",
                        "prompt": {
                            "node": "evidence_sufficiency",
                            "objective": "test",
                            "hard_rules": [],
                            "inputs": {},
                            "fallback_decision": {},
                        },
                        "provider_payload": {},
                        "parsed_proposal": {},
                        "final_decision": {"recommended_next": "grounding"},
                        "safety_notes": [],
                    }
                ),
                encoding="utf-8",
            )
            constraints.write_text(json.dumps({"excluded_claim_ids": []}), encoding="utf-8")
            context.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "allowed_claims": [
                            {
                                "claim_id": "C1",
                                "claim_text": "Supported claim.",
                                "support_status": "supported",
                                "evidence_ids": ["E1"],
                                "writing_boundary": "safe_to_write",
                            }
                        ],
                        "caveated_claims": [],
                        "excluded_claims": [],
                    }
                ),
                encoding="utf-8",
            )
            plan.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "sections": [{"section_id": "AP-S1", "claim_ids": ["C1"], "evidence_ids": ["E1"]}],
                        "excluded_claim_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            text.write_text("method text", encoding="utf-8")
            validation.write_text(json.dumps({"status": "success"}), encoding="utf-8")
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "evidence": str(evidence),
                    "claims": str(claims),
                    "claim_verification": str(verification),
                    "evidence_sufficiency_report": str(sufficiency),
                    "evidence_sufficiency_decision_trace": str(sufficiency_trace),
                    "authoring_constraints": str(constraints),
                    "authoring_context": str(context),
                    "authoring_plan": str(plan),
                    "text_md": str(text),
                    "validation_manifest": str(validation),
                },
            )

            updated = AgenticRunState.model_validate(_invariant_audit_node(state.model_dump(mode="json")))

        self.assertEqual(updated.blocked_reason, "invariant_audit_failed")
        self.assertEqual(updated.next_node, "blocked")
        self.assertEqual(_route_after_invariant_audit(updated.model_dump(mode="json")), "blocked")
        self.assertEqual(updated.decisions[-1].node, "invariant_auditor")
        self.assertEqual(updated.decisions[-1].decision, "blocked")

    def test_invariant_audit_node_allows_rendering_when_trace_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            evidence = root / "evidence.json"
            claims = root / "claims.json"
            verification = root / "claim_verification.json"
            sufficiency = root / "evidence_sufficiency_report.json"
            sufficiency_trace = root / "evidence_sufficiency_trace.json"
            constraints = root / "authoring_constraints.json"
            context = root / "authoring_context.json"
            plan = root / "authoring_plan.json"
            plan_trace = root / "authoring_plan_decision_trace.json"
            text = root / "method.md"
            text_claims = root / "text_claims.json"
            validation = root / "validation_manifest.json"
            evidence.write_text(json.dumps({"stages": [{"mechanisms": [{"evidence_ids": ["E1"]}]}]}), encoding="utf-8")
            claims.write_text(json.dumps({"claims": [{"claim_id": "C1", "evidence_ids": ["E1"]}]}), encoding="utf-8")
            verification.write_text(
                json.dumps({"claims_with_missing_evidence": 0, "claims": [{"claim_id": "C1", "support_status": "supported"}]}),
                encoding="utf-8",
            )
            sufficiency.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "safe_claim_ids": ["C1"],
                        "caveated_claim_ids": [],
                        "support_rate": 1.0,
                    }
                ),
                encoding="utf-8",
            )
            sufficiency_trace.write_text(
                json.dumps(
                    {
                        "mode": "agentic-decision-trace",
                        "node": "evidence_sufficiency",
                        "provider_status": "deterministic_fallback",
                        "prompt": {
                            "node": "evidence_sufficiency",
                            "objective": "test",
                            "hard_rules": [],
                            "inputs": {},
                            "fallback_decision": {},
                        },
                        "provider_payload": {},
                        "parsed_proposal": {},
                        "final_decision": {"recommended_next": "grounding"},
                        "safety_notes": [],
                    }
                ),
                encoding="utf-8",
            )
            constraints.write_text(json.dumps({"excluded_claim_ids": []}), encoding="utf-8")
            context.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "allowed_claims": [
                            {
                                "claim_id": "C1",
                                "claim_text": "Supported claim.",
                                "support_status": "supported",
                                "evidence_ids": ["E1"],
                                "writing_boundary": "safe_to_write",
                            }
                        ],
                        "caveated_claims": [],
                        "excluded_claims": [],
                    }
                ),
                encoding="utf-8",
            )
            plan_payload = {
                "hard_gate_passed": True,
                "sections": [{"section_id": "AP-S1", "claim_ids": ["C1"], "evidence_ids": ["E1"]}],
                "excluded_claim_ids": [],
            }
            plan.write_text(json.dumps(plan_payload), encoding="utf-8")
            plan_trace.write_text(
                json.dumps(
                    {
                        "mode": "agentic-decision-trace",
                        "node": "authoring_planner",
                        "provider_status": "deterministic_fallback",
                        "prompt": {
                            "node": "authoring_planner",
                            "objective": "test",
                            "hard_rules": [],
                            "inputs": {},
                            "fallback_decision": {},
                        },
                        "provider_payload": {},
                        "parsed_proposal": {},
                        "final_decision": plan_payload,
                        "safety_notes": [],
                    }
                ),
                encoding="utf-8",
            )
            text.write_text("method text", encoding="utf-8")
            text_claims.write_text(
                json.dumps({"paragraphs": [{"paragraph_id": "P1", "claim_ids": ["C1"], "evidence_span_ids": ["E1"]}]}),
                encoding="utf-8",
            )
            validation.write_text(json.dumps({"status": "success"}), encoding="utf-8")
            text_digest = "sha256:" + hashlib.sha256(text.read_bytes()).hexdigest()
            projection = root / "authoring_projection.json"
            final_claims = root / "final_text_claims.json"
            text_evidence_validation = root / "text_evidence_validation.json"
            final_text_trace = root / "final_text_trace.json"
            projection.write_text(json.dumps({"projection_digest": "sha256:projection"}), encoding="utf-8")
            final_claims.write_text(
                json.dumps({"input_text_digest": text_digest, "atomic_claims": [{"atomic_claim_id": "FAC1"}]}),
                encoding="utf-8",
            )
            text_evidence_validation.write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "input_text_digest": text_digest,
                        "projection_digest": "sha256:projection",
                        "verdicts": [{"atomic_claim_id": "FAC1", "status": "supported"}],
                    }
                ),
                encoding="utf-8",
            )
            final_text_trace.write_text(
                json.dumps(
                    {
                        "hard_gate_passed": True,
                        "input_text_digest": text_digest,
                        "projection_digest": "sha256:projection",
                        "entries": [{"atomic_claim_id": "FAC1", "projection_claim_ids": ["C1"], "direct_evidence_ids": ["E1"]}],
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                artifacts={
                    "evidence": str(evidence),
                    "claims": str(claims),
                    "claim_verification": str(verification),
                    "evidence_sufficiency_report": str(sufficiency),
                    "evidence_sufficiency_decision_trace": str(sufficiency_trace),
                    "authoring_constraints": str(constraints),
                    "authoring_context": str(context),
                    "authoring_plan": str(plan),
                    "authoring_plan_decision_trace": str(plan_trace),
                    "text_md": str(text),
                    "text_claims": str(text_claims),
                    "final_text_candidate": str(text),
                    "authoring_projection": str(projection),
                    "final_text_claims": str(final_claims),
                    "text_evidence_validation": str(text_evidence_validation),
                    "final_text_trace": str(final_text_trace),
                    "validation_manifest": str(validation),
                },
            )

            updated = AgenticRunState.model_validate(_invariant_audit_node(state.model_dump(mode="json")))

        self.assertFalse(updated.blocked_reason)
        self.assertEqual(updated.next_node, "rendering")
        self.assertEqual(_route_after_invariant_audit(updated.model_dump(mode="json")), "rendering")
        self.assertEqual(updated.decisions[-1].decision, "passed")

    def test_rendering_routes_to_final_invariant_audit_unless_blocked(self) -> None:
        ready = AgenticRunState(project_root=Path("."), out_root=Path("/tmp/code2paper-agentic-test"))
        blocked = ready.model_copy(update={"blocked_reason": "figure_plan_missing_supported_evidence"})

        self.assertEqual(_route_after_rendering(ready.model_dump(mode="json")), "final_invariant_audit")
        self.assertEqual(_route_after_rendering(blocked.model_dump(mode="json")), "blocked")

if __name__ == "__main__":
    unittest.main()
