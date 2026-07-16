from __future__ import annotations

import sys
import types
import unittest

from code2paper.agentic.tools import (
    StageToolInvokeInput,
    build_langchain_stage_tools,
    build_stage_tool_registry,
    build_tool_catalog,
)
from code2paper.agentic.langchain_tools import build_langchain_stage_tool_manifest
from code2paper.agentic.decision_tool_guidance import stage_tool_guidance_for_decision


class AgenticToolGuidanceTests(unittest.TestCase):
    def test_tool_catalog_exposes_invocation_guidance(self) -> None:
        catalog = build_tool_catalog()

        authoring = catalog.tool_guidance["authoring"]
        rendering = catalog.tool_guidance["rendering"]

        self.assertIn("evidence_sufficiency_report", authoring.required_inputs)
        self.assertIn("traceability_ledger", rendering.required_inputs)
        self.assertIn("rendering", catalog.model_decision_stages)
        self.assertIn("hard evidence gate", rendering.invocation_contract)
        self.assertIn("blocked_reason", rendering.blocked_recovery)

    def test_langchain_tool_metadata_contains_guidance(self) -> None:
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
            by_name = {tool.name: tool for tool in tools}
            rendering = by_name["code2paper_rendering"]

            self.assertIs(rendering.args_schema, StageToolInvokeInput)
            self.assertIn("guidance", rendering.metadata)
            self.assertTrue(rendering.metadata["allow_model_decision"])
            self.assertIn("traceability_ledger", rendering.metadata["guidance"]["required_inputs"])
            self.assertIn("hard evidence gate", rendering.metadata["guidance"]["invocation_contract"])
            self.assertIn("Required inputs", rendering.description)
        finally:
            if old_parent is None:
                sys.modules.pop("langchain_core", None)
            else:
                sys.modules["langchain_core"] = old_parent
            if old_tools is None:
                sys.modules.pop("langchain_core.tools", None)
            else:
                sys.modules["langchain_core.tools"] = old_tools

    def test_langchain_tool_manifest_records_schema_and_evidence_policy(self) -> None:
        manifest = build_langchain_stage_tool_manifest(build_stage_tool_registry())
        by_stage = {tool.stage: tool for tool in manifest.tools}

        self.assertEqual(manifest.mode, "agentic-langchain-tool-manifest")
        self.assertEqual(manifest.tool_count, len(by_stage))
        self.assertIn("code2paper_rendering", manifest.hard_gate_tool_names)
        self.assertIn("code2paper_authoring", manifest.model_decision_tool_names)
        self.assertEqual(by_stage["rendering"].name, "code2paper_rendering")
        self.assertEqual(by_stage["rendering"].args_schema_name, "StageToolInvokeInput")
        self.assertIn("state", by_stage["rendering"].args_schema["properties"])
        self.assertEqual(by_stage["rendering"].evidence_policy, "consumes_frozen_evidence")
        self.assertTrue(by_stage["rendering"].hard_gate)

    def test_decision_prompt_tool_guidance_selects_relevant_stages(self) -> None:
        guidance = stage_tool_guidance_for_decision(["intake", "rendering", "unknown_stage"])

        self.assertEqual(sorted(guidance), ["intake", "rendering"])
        self.assertIn("retrieval_summary", guidance["intake"]["produced_outputs"])
        self.assertIn("traceability_ledger", guidance["rendering"]["required_inputs"])


if __name__ == "__main__":
    unittest.main()
