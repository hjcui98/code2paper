from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import (
    AgenticRunState,
    StageHandler,
    StageStatus,
    StageToolResult,
    StageToolSpec,
)
from code2paper.agentic.tool_specs import canonical_stage_tool_specs


class AgenticToolCatalog(BaseModel):
    """Serializable catalog of LangChain-style stage tool contracts."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-tool-catalog"
    tool_count: int = 0
    tools: list[StageToolSpec] = Field(default_factory=list)
    hard_gates: list[str] = Field(default_factory=list)
    model_decision_stages: list[str] = Field(default_factory=list)
    evidence_policies: dict[str, str] = Field(default_factory=dict)
    tool_guidance: dict[str, "StageToolGuidance"] = Field(default_factory=dict)


class StageToolGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_inputs: list[str] = Field(default_factory=list)
    required_outputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    invocation_contract: str = ""
    evidence_guardrail: str = ""
    blocked_recovery: str = ""
    decision_scope: str = ""


class StageToolInvokeInput(BaseModel):
    """LangChain-facing input schema for invoking one stage tool."""

    model_config = ConfigDict(extra="forbid")

    state: dict[str, Any]


def build_tool_catalog(
    registry: Mapping[str, "Code2PaperStageTool"] | None = None,
) -> AgenticToolCatalog:
    """Build an auditable catalog from the canonical or active tool registry."""

    if registry is None:
        specs = canonical_stage_tool_specs()
    else:
        specs = [tool.spec for _stage, tool in sorted(registry.items())]
    return AgenticToolCatalog(
        tool_count=len(specs),
        tools=specs,
        hard_gates=[spec.stage for spec in specs if spec.hard_gate],
        model_decision_stages=[spec.stage for spec in specs if spec.allow_model_decision],
        evidence_policies={spec.stage: spec.evidence_policy.value for spec in specs},
        tool_guidance={spec.stage: _stage_tool_guidance(spec) for spec in specs},
    )


def write_tool_catalog(path: str | Path, catalog: AgenticToolCatalog) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_tool_catalog(path: str | Path) -> AgenticToolCatalog:
    return AgenticToolCatalog.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class Code2PaperStageTool:
    """Small LangChain-compatible wrapper around an existing Code2Paper stage."""

    spec: StageToolSpec
    handler: StageHandler | None = None

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def description(self) -> str:
        return _stage_tool_description(self.spec)

    def invoke(self, state: AgenticRunState | dict) -> StageToolResult:
        run_state = state if isinstance(state, AgenticRunState) else AgenticRunState.model_validate(state)
        missing_inputs = _missing_hard_gate_inputs(self.spec, run_state)
        if missing_inputs:
            return StageToolResult(
                stage=self.spec.stage,
                status=StageStatus.BLOCKED,
                blocked_reason="missing_required_input_artifacts",
                summary=(
                    f"{self.spec.stage} requires input artifacts before this hard gate can run: "
                    + ", ".join(missing_inputs)
                ),
            )
        if self.handler is None:
            return StageToolResult(
                stage=self.spec.stage,
                status=StageStatus.BLOCKED,
                blocked_reason="stage_handler_not_configured",
                summary=f"No handler has been registered for {self.spec.stage}.",
            )
        result = self.handler(run_state)
        missing_outputs = _missing_hard_gate_outputs(self.spec, result)
        if missing_outputs:
            return result.model_copy(
                update={
                    "status": StageStatus.BLOCKED,
                    "blocked_reason": "missing_required_output_artifacts",
                    "summary": (
                        f"{self.spec.stage} reported success but did not produce required "
                        "hard-gate artifacts: " + ", ".join(missing_outputs)
                    ),
                }
            )
        return result

    def to_langchain_tool(self):
        """Adapt this wrapper to a LangChain StructuredTool when installed."""

        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError(
                "Install the optional agentic extra to export LangChain tools: "
                "pip install -e .[agentic]"
            ) from exc

        def _run(state: dict[str, Any]) -> dict[str, Any]:
            return self.invoke(state).model_dump(mode="json")

        return StructuredTool.from_function(
            func=_run,
            name=self.name,
            description=self.description,
            args_schema=StageToolInvokeInput,
            metadata=_stage_tool_metadata(self.spec),
        )


def build_stage_tool_registry(
    handlers: Mapping[str, StageHandler] | None = None,
) -> dict[str, Code2PaperStageTool]:
    """Build tools keyed by canonical stage name."""

    handler_map = dict(handlers or {})
    return {
        spec.stage: Code2PaperStageTool(spec=spec, handler=handler_map.get(spec.stage))
        for spec in canonical_stage_tool_specs()
    }


def build_langchain_stage_tools(
    registry: Mapping[str, Code2PaperStageTool] | None = None,
) -> list[Any]:
    """Export the active stage registry as LangChain StructuredTool objects."""

    active_registry = registry or build_stage_tool_registry()
    return [tool.to_langchain_tool() for _stage, tool in sorted(active_registry.items())]


def _missing_hard_gate_inputs(spec: StageToolSpec, state: AgenticRunState) -> list[str]:
    if not spec.hard_gate:
        return []
    return [
        artifact
        for artifact in spec.input_artifacts
        if artifact not in state.artifacts or not state.artifacts[artifact].strip()
    ]


def _missing_hard_gate_outputs(spec: StageToolSpec, result: StageToolResult) -> list[str]:
    if not spec.hard_gate or result.status != StageStatus.SUCCESS:
        return []
    return [
        artifact
        for artifact in spec.required_output_artifacts
        if artifact not in result.artifacts or not result.artifacts[artifact].strip()
    ]


def _stage_tool_metadata(spec: StageToolSpec) -> dict[str, Any]:
    guidance = _stage_tool_guidance(spec)
    return {
        "mode": "code2paper-stage-tool-metadata",
        "stage": spec.stage,
        "input_artifacts": list(spec.input_artifacts),
        "output_artifacts": list(spec.output_artifacts),
        "required_output_artifacts": list(spec.required_output_artifacts),
        "evidence_policy": spec.evidence_policy.value,
        "allow_model_decision": spec.allow_model_decision,
        "hard_gate": spec.hard_gate,
        "guidance": guidance.model_dump(mode="json"),
    }


def _stage_tool_description(spec: StageToolSpec) -> str:
    guidance = _stage_tool_guidance(spec)
    return "\n".join(
        [
            spec.description,
            f"Required inputs: {', '.join(guidance.required_inputs) if guidance.required_inputs else 'none'}.",
            f"Required outputs: {', '.join(guidance.required_outputs) if guidance.required_outputs else 'none'}.",
            f"Invocation contract: {guidance.invocation_contract}",
            f"Evidence guardrail: {guidance.evidence_guardrail}",
            f"Blocked recovery: {guidance.blocked_recovery}",
            f"Decision scope: {guidance.decision_scope}",
        ]
    )


def _stage_tool_guidance(spec: StageToolSpec) -> StageToolGuidance:
    required_inputs = list(spec.input_artifacts)
    required_outputs = list(spec.required_output_artifacts)
    return StageToolGuidance(
        required_inputs=required_inputs,
        required_outputs=required_outputs,
        produced_outputs=list(spec.output_artifacts),
        invocation_contract=_invocation_contract(spec, required_inputs, required_outputs),
        evidence_guardrail=_evidence_guardrail(spec),
        blocked_recovery=_blocked_recovery(spec),
        decision_scope=_decision_scope(spec),
    )


def _invocation_contract(spec: StageToolSpec, required_inputs: list[str], required_outputs: list[str]) -> str:
    if not required_inputs:
        base = "May be called without prior artifacts."
    else:
        base = "Call only after required input artifacts exist: " + ", ".join(required_inputs) + "."
    if spec.hard_gate:
        required_output_text = ", ".join(required_outputs) if required_outputs else "its declared hard-gate outputs"
        return base + " This stage is a hard evidence gate and must return: " + required_output_text + "."
    return base


def _evidence_guardrail(spec: StageToolSpec) -> str:
    policy = spec.evidence_policy.value
    if policy == "none":
        return "Does not consume or create evidence; preserve any existing evidence artifacts unchanged."
    if policy == "retrieves_evidence":
        return "Retrieve implementation evidence and keep outputs traceable to source files and symbols."
    if policy == "analyzes_evidence":
        return "Analyze retrieved code evidence without inventing unsupported mechanisms."
    if policy == "freezes_evidence":
        return "Freeze only verified code evidence into MethodEvidence and claim maps."
    if policy == "validates_evidence":
        return "Validate text and claims against frozen evidence before downstream rendering."
    return "Consume only frozen, validated evidence artifacts; do not introduce new unsupported claims."


def _blocked_recovery(spec: StageToolSpec) -> str:
    if spec.stage in {"rendering", "finalize"}:
        return "If blocked, inspect blocked_reason plus invariant audit and traceability ledger before retrying."
    if spec.stage == "authoring":
        return "If blocked, inspect blocked_reason plus evidence sufficiency, authoring context, and authoring plan."
    if spec.stage in {"evidence", "validation"}:
        return "If blocked, return to analysis or repair evidence before retrying this hard gate."
    return "If blocked, inspect blocked_reason and artifact_keys, then route to the stage that can repair the missing input."


def _decision_scope(spec: StageToolSpec) -> str:
    if spec.allow_model_decision:
        return "Model may propose routing or planning choices, but the tool must enforce evidence gates."
    return "Deterministic stage execution; model should not override evidence gates or hard prerequisites."
