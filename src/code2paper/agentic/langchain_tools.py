from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.tools import Code2PaperStageTool, StageToolInvokeInput, build_stage_tool_registry


class LangChainStageToolExport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    stage: str
    description: str
    args_schema_name: str
    args_schema: dict[str, Any] = Field(default_factory=dict)
    evidence_policy: str
    allow_model_decision: bool = False
    hard_gate: bool = False
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    required_output_artifacts: list[str] = Field(default_factory=list)


class LangChainStageToolManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-langchain-tool-manifest"
    tool_count: int = 0
    tools: list[LangChainStageToolExport] = Field(default_factory=list)
    model_decision_tool_names: list[str] = Field(default_factory=list)
    hard_gate_tool_names: list[str] = Field(default_factory=list)


def build_langchain_stage_tool_manifest(
    registry: Mapping[str, Code2PaperStageTool] | None = None,
) -> LangChainStageToolManifest:
    active_registry = registry or build_stage_tool_registry()
    tools = [_export_record(tool) for _stage, tool in sorted(active_registry.items())]
    return LangChainStageToolManifest(
        tool_count=len(tools),
        tools=tools,
        model_decision_tool_names=[tool.name for tool in tools if tool.allow_model_decision],
        hard_gate_tool_names=[tool.name for tool in tools if tool.hard_gate],
    )


def write_langchain_stage_tool_manifest(path: str | Path, manifest: LangChainStageToolManifest) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_langchain_stage_tool_manifest(path: str | Path) -> LangChainStageToolManifest:
    return LangChainStageToolManifest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _export_record(tool: Code2PaperStageTool) -> LangChainStageToolExport:
    spec = tool.spec
    return LangChainStageToolExport(
        name=tool.name,
        stage=spec.stage,
        description=tool.description,
        args_schema_name=StageToolInvokeInput.__name__,
        args_schema=StageToolInvokeInput.model_json_schema(),
        evidence_policy=spec.evidence_policy.value,
        allow_model_decision=spec.allow_model_decision,
        hard_gate=spec.hard_gate,
        input_artifacts=list(spec.input_artifacts),
        output_artifacts=list(spec.output_artifacts),
        required_output_artifacts=list(spec.required_output_artifacts),
    )
