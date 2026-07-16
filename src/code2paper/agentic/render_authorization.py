from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.invariant_audit import load_invariant_audit
from code2paper.agentic.traceability_models import EvidenceTraceabilityLedger

PRE_RENDER_AUTHORIZATION_KEYS = ("agentic_invariant_audit", "traceability_ledger")


class PreRenderAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    blocked_reason: str = ""
    message: str = ""
    artifact_keys: list[str] = Field(default_factory=lambda: list(PRE_RENDER_AUTHORIZATION_KEYS))


def check_pre_render_authorization(state: AgenticRunState) -> PreRenderAuthorization:
    missing = _missing_authorization_artifacts(state)
    if missing:
        return PreRenderAuthorization(
            passed=False,
            blocked_reason="pre_render_authorization_missing",
            message="Pre-render authorization requires passed artifacts: " + ", ".join(missing),
        )
    try:
        audit = load_invariant_audit(state.artifacts["agentic_invariant_audit"])
        ledger = EvidenceTraceabilityLedger.model_validate_json(
            Path(state.artifacts["traceability_ledger"]).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return PreRenderAuthorization(
            passed=False,
            blocked_reason="pre_render_authorization_unreadable",
            message=f"Pre-render authorization artifacts are unreadable: {exc}",
        )
    problems: list[str] = []
    if not audit.passed or audit.blocking_failures:
        problems.append("agentic_invariant_audit has blocking failures")
    if not ledger.hard_gate_passed:
        problems.append("traceability_ledger hard gate failed")
    if problems:
        return PreRenderAuthorization(
            passed=False,
            blocked_reason="pre_render_authorization_failed",
            message="; ".join(problems),
        )
    return PreRenderAuthorization(
        passed=True,
        message="Invariant audit and traceability ledger authorize rendering/finalization.",
    )


def pre_render_blocked_result(stage: str, authorization: PreRenderAuthorization) -> StageToolResult:
    return StageToolResult(
        stage=stage,
        status=StageStatus.BLOCKED,
        blocked_reason=authorization.blocked_reason,
        summary=authorization.message,
        decisions=[
            AgentDecision(
                node="pre_render_authorization",
                decision="blocked",
                rationale=authorization.message,
                artifact_keys=authorization.artifact_keys,
            )
        ],
    )


def _missing_authorization_artifacts(state: AgenticRunState) -> list[str]:
    missing: list[str] = []
    for key in PRE_RENDER_AUTHORIZATION_KEYS:
        artifact = state.artifacts.get(key, "")
        if not artifact or not Path(artifact).exists():
            missing.append(key)
    return missing
