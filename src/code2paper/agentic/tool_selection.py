from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.contracts import AgenticRunState


TRUST_TOOL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "build_authoring_projection": ("evidence_snapshot_v2", "atomic_claims_v2", "claim_verification"),
    "extract_final_text_claims": ("authoring_projection",),
    "validate_claim_against_evidence": ("final_text_claims", "authoring_projection", "evidence_snapshot_v2"),
    "build_text_trace": ("final_text_claims", "text_evidence_validation", "authoring_projection"),
    "check_artifact_freshness": ("repo_snapshot", "evidence_snapshot_v2"),
    "build_evidence_relation": ("evidence_snapshot_v2",),
    "validate_figure_relation": ("figure_scene", "evidence_relations_v2", "evidence_snapshot_v2"),
    "render_structured_figure": ("figure_scene", "pre_render_audit"),
    "validate_rendered_figure": ("figure_scene", "rendering_manifest"),
}


class ToolReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    allowed: bool
    missing_artifacts: list[str] = Field(default_factory=list)
    denial_reasons: list[str] = Field(default_factory=list)


class RestrictedToolSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str = "restricted-trust-tool-selection-v2"
    allowed_tools: list[str] = Field(default_factory=list)
    readiness: list[ToolReadiness] = Field(default_factory=list)


def build_restricted_tool_selection(state: AgenticRunState) -> RestrictedToolSelection:
    readiness: list[ToolReadiness] = []
    stale = _failed_report(state.artifacts.get("artifact_freshness", ""))
    text_failed = _failed_report(state.artifacts.get("text_evidence_validation", ""))
    figure_failed = _failed_report(state.artifacts.get("figure_relation_validation", ""))
    for name, requirements in TRUST_TOOL_REQUIREMENTS.items():
        missing = [key for key in requirements if not state.artifacts.get(key)]
        reasons: list[str] = []
        if stale and name not in {"check_artifact_freshness", "build_authoring_projection", "build_evidence_relation"}:
            reasons.append("stale_artifacts_must_return_to_producer")
        if text_failed and name in {"render_structured_figure", "validate_rendered_figure"}:
            reasons.append("text_semantic_gate_failed")
        if figure_failed and name == "render_structured_figure":
            reasons.append("figure_relation_gate_failed")
        if name == "build_text_trace" and not _passed_report(state.artifacts.get("text_evidence_validation", "")):
            reasons.append("text_validation_not_passed")
        if name == "render_structured_figure" and not _passed_report(state.artifacts.get("pre_render_audit", "")):
            reasons.append("pre_render_audit_not_passed")
        allowed = not missing and not reasons and not state.blocked_reason
        readiness.append(ToolReadiness(tool_name=name, allowed=allowed, missing_artifacts=missing, denial_reasons=reasons))
    return RestrictedToolSelection(
        allowed_tools=[item.tool_name for item in readiness if item.allowed],
        readiness=readiness,
    )


def enforce_tool_proposal(state: AgenticRunState, proposed_tool: str) -> str:
    """Deterministic safety merge: a model proposal never grants a capability."""

    proposal = proposed_tool.strip()
    if proposal in {"finalize", "shell", "filesystem", "write_file"}:
        raise PermissionError(f"tool_not_exposed_to_model:{proposal}")
    selection = build_restricted_tool_selection(state)
    if proposal not in selection.allowed_tools:
        raise PermissionError(f"tool_preconditions_not_met:{proposal}")
    return proposal


def _read_report(path: str) -> dict:
    if not path or not Path(path).exists():
        return {}
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "failed"}
    return value if isinstance(value, dict) else {"status": "failed"}


def _failed_report(path: str) -> bool:
    report = _read_report(path)
    return bool(report) and report.get("status") != "passed" and not report.get("hard_gate_passed", False)


def _passed_report(path: str) -> bool:
    report = _read_report(path)
    return report.get("status") == "passed" or report.get("hard_gate_passed") is True
