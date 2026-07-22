from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.decision_core import load_decision_trace
from code2paper.agentic.evidence_sufficiency import EvidenceSufficiencyReport

PRE_AUTHORING_AUTHORIZATION_KEYS = ("evidence_sufficiency_report", "evidence_sufficiency_decision_trace")


class PreAuthoringAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    blocked_reason: str = ""
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=lambda: list(PRE_AUTHORING_AUTHORIZATION_KEYS))


def check_pre_authoring_authorization(state: AgenticRunState) -> PreAuthoringAuthorization:
    missing = _missing_authorization_artifacts(state)
    if missing:
        return PreAuthoringAuthorization(
            passed=False,
            blocked_reason="pre_authoring_authorization_missing",
            message="Authoring requires evidence sufficiency authorization artifacts: " + ", ".join(missing),
        )
    try:
        report = EvidenceSufficiencyReport.model_validate_json(
            Path(state.artifacts["evidence_sufficiency_report"]).read_text(encoding="utf-8")
        )
        trace = load_decision_trace(state.artifacts["evidence_sufficiency_decision_trace"])
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return PreAuthoringAuthorization(
            passed=False,
            blocked_reason="pre_authoring_authorization_unreadable",
            message=f"Authoring authorization artifacts are unreadable: {exc}",
        )
    problems: list[str] = []
    if not report.hard_gate_passed:
        problems.append("evidence_sufficiency_report did not approve writable claims")
    recommended_next = str(trace.final_decision.get("recommended_next") or "")
    if recommended_next not in {"grounding", "authoring"}:
        problems.append("evidence_sufficiency_decision_trace did not authorize grounding/authoring")
    if problems:
        return PreAuthoringAuthorization(
            passed=False,
            blocked_reason="pre_authoring_authorization_failed",
            message="; ".join(problems),
        )
    return PreAuthoringAuthorization(
        passed=True,
        message="Evidence sufficiency review authorizes grounding and method authoring.",
    )


def pre_authoring_blocked_result(authorization: PreAuthoringAuthorization) -> StageToolResult:
    return StageToolResult(
        stage="authoring",
        status=StageStatus.BLOCKED,
        blocked_reason=authorization.blocked_reason,
        summary=authorization.message,
        decisions=[
            AgentDecision(
                node="pre_authoring_authorization",
                decision="blocked",
                rationale=authorization.message,
                artifact_keys=authorization.artifact_keys,
            )
        ],
    )


def _missing_authorization_artifacts(state: AgenticRunState) -> list[str]:
    missing: list[str] = []
    for key in PRE_AUTHORING_AUTHORIZATION_KEYS:
        artifact = state.artifacts.get(key, "")
        if not artifact or not Path(artifact).exists():
            missing.append(key)
    return missing
