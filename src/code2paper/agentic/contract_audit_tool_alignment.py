from __future__ import annotations

from code2paper.agentic.graph_catalog import AgenticGraphCatalog
from code2paper.agentic.langchain_tools import LangChainStageToolManifest
from code2paper.agentic.tools import AgenticToolCatalog


def graph_stage_tool_alignment_problems(
    graph_catalog: AgenticGraphCatalog,
    tool_catalog: AgenticToolCatalog,
) -> list[str]:
    tools_by_stage = {tool.stage: tool for tool in tool_catalog.tools}
    problems: list[str] = []
    for node in graph_catalog.nodes:
        if node.kind != "stage":
            continue
        tool = tools_by_stage.get(node.stage)
        if tool is None:
            problems.append(f"{node.name}: missing stage tool contract")
            continue
        if node.tool_name != tool.name:
            problems.append(f"{node.name}: tool_name mismatch")
        if node.evidence_policy != tool.evidence_policy:
            problems.append(f"{node.name}: evidence_policy mismatch")
        if node.hard_gate != tool.hard_gate:
            problems.append(f"{node.name}: hard_gate mismatch")
        if node.allow_model_decision != tool.allow_model_decision:
            problems.append(f"{node.name}: allow_model_decision mismatch")
        if set(node.input_artifacts) != set(tool.input_artifacts):
            problems.append(f"{node.name}: input_artifacts mismatch")
        if set(node.output_artifacts) != set(tool.output_artifacts):
            problems.append(f"{node.name}: output_artifacts mismatch")
    return problems


def langchain_tool_manifest_alignment_problems(
    tool_catalog: AgenticToolCatalog,
    manifest: LangChainStageToolManifest,
) -> list[str]:
    exports_by_stage = {tool.stage: tool for tool in manifest.tools}
    problems: list[str] = []
    if manifest.tool_count != len(manifest.tools):
        problems.append("manifest: tool_count mismatch")
    for tool in tool_catalog.tools:
        exported = exports_by_stage.get(tool.stage)
        if exported is None:
            problems.append(f"{tool.stage}: missing LangChain tool export")
            continue
        if exported.name != tool.name:
            problems.append(f"{tool.stage}: tool name mismatch")
        if exported.args_schema_name != "StageToolInvokeInput":
            problems.append(f"{tool.stage}: args_schema_name mismatch")
        if "state" not in exported.args_schema.get("properties", {}):
            problems.append(f"{tool.stage}: args_schema missing state")
        if exported.evidence_policy != tool.evidence_policy.value:
            problems.append(f"{tool.stage}: evidence_policy mismatch")
        if exported.allow_model_decision != tool.allow_model_decision:
            problems.append(f"{tool.stage}: allow_model_decision mismatch")
        if exported.hard_gate != tool.hard_gate:
            problems.append(f"{tool.stage}: hard_gate mismatch")
        if set(exported.input_artifacts) != set(tool.input_artifacts):
            problems.append(f"{tool.stage}: input_artifacts mismatch")
        if set(exported.output_artifacts) != set(tool.output_artifacts):
            problems.append(f"{tool.stage}: output_artifacts mismatch")
        if set(exported.required_output_artifacts) != set(tool.required_output_artifacts):
            problems.append(f"{tool.stage}: required_output_artifacts mismatch")
    expected_model_tools = {tool.name for tool in tool_catalog.tools if tool.allow_model_decision}
    if set(manifest.model_decision_tool_names) != expected_model_tools:
        problems.append("manifest: model_decision_tool_names mismatch")
    expected_hard_gate_tools = {tool.name for tool in tool_catalog.tools if tool.hard_gate}
    if set(manifest.hard_gate_tool_names) != expected_hard_gate_tools:
        problems.append("manifest: hard_gate_tool_names mismatch")
    return problems
