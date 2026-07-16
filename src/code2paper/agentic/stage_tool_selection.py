from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState, StageToolSpec
from code2paper.agentic.tools import StageToolGuidance, build_tool_catalog


class StageToolReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: str
    tool_name: str
    can_invoke: bool
    required_inputs: list[str] = Field(default_factory=list)
    missing_required_inputs: list[str] = Field(default_factory=list)
    produced_outputs: list[str] = Field(default_factory=list)
    evidence_policy: str = ""
    allow_model_decision: bool = False
    hard_gate: bool = False
    guidance: StageToolGuidance


class StageToolSelectionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str = "stage-tool-selection-context"
    candidate_stages: list[str] = Field(default_factory=list)
    available_artifacts: list[str] = Field(default_factory=list)
    stages: list[StageToolReadiness] = Field(default_factory=list)

    def readiness_by_stage(self) -> dict[str, StageToolReadiness]:
        return {item.stage: item for item in self.stages}


def build_stage_tool_selection_context(
    state: AgenticRunState,
    *,
    candidate_stages: list[str],
) -> StageToolSelectionContext:
    catalog = build_tool_catalog()
    spec_by_stage = {spec.stage: spec for spec in catalog.tools}
    guidance_by_stage = catalog.tool_guidance
    available = sorted(state.artifacts)
    readiness = [
        _readiness_for_stage(
            spec=spec_by_stage[stage],
            guidance=guidance_by_stage[stage],
            available_artifacts=available,
        )
        for stage in candidate_stages
        if stage in spec_by_stage and stage in guidance_by_stage
    ]
    return StageToolSelectionContext(
        candidate_stages=[item.stage for item in readiness],
        available_artifacts=available,
        stages=readiness,
    )


def safe_stage_from_proposal(
    *,
    selection_context: StageToolSelectionContext,
    proposed_stage: str,
    fallback_stage: str,
) -> str:
    proposed = proposed_stage.strip()
    if not proposed:
        return fallback_stage
    readiness = selection_context.readiness_by_stage().get(proposed)
    if readiness is None or not readiness.can_invoke:
        return fallback_stage
    return proposed


def _readiness_for_stage(
    *,
    spec: StageToolSpec,
    guidance: StageToolGuidance,
    available_artifacts: list[str],
) -> StageToolReadiness:
    available = set(available_artifacts)
    missing = [artifact for artifact in spec.input_artifacts if artifact not in available]
    return StageToolReadiness(
        stage=spec.stage,
        tool_name=spec.name,
        can_invoke=not missing,
        required_inputs=list(spec.input_artifacts),
        missing_required_inputs=missing,
        produced_outputs=list(spec.output_artifacts),
        evidence_policy=spec.evidence_policy.value,
        allow_model_decision=spec.allow_model_decision,
        hard_gate=spec.hard_gate,
        guidance=guidance,
    )
