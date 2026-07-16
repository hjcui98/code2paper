from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus
from code2paper.agentic.invariant_audit import build_invariant_audit, write_invariant_audit
from code2paper.agentic.tools import Code2PaperStageTool
from code2paper.agentic.traceability_ledger import build_traceability_ledger, write_traceability_ledger
from code2paper.core.output_names import artifact_dir


def stage_node(stage: str, registry: Mapping[str, Code2PaperStageTool]):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        tool = registry[stage]
        result = tool.invoke(state)
        updated = state.with_result(result)
        updated = updated.model_copy(
            update={
                "decisions": [
                    *updated.decisions,
                    AgentDecision(
                        node=f"stage_tool:{stage}",
                        decision="invoked",
                        rationale=(
                            f"Invoked {tool.name}; "
                            f"evidence_policy={tool.spec.evidence_policy.value}; "
                            f"hard_gate={tool.spec.hard_gate}; "
                            f"allow_model_decision={tool.spec.allow_model_decision}."
                        ),
                        artifact_keys=["agentic_tool_catalog", *result.artifacts],
                    ),
                ]
            }
        )
        if result.status == StageStatus.FAILED:
            updated = updated.model_copy(update={"blocked_reason": result.blocked_reason or f"{stage}_failed"})
        return updated.model_dump(mode="json")

    return _run


def blocked_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
    if not state.blocked_reason:
        state = state.model_copy(update={"blocked_reason": "agentic_graph_blocked"})
    return state.model_dump(mode="json")


def invariant_audit_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
    ledger_path = artifact_dir(state.method_root, "10_run") / "agentic_traceability_ledger.json"
    write_traceability_ledger(ledger_path, build_traceability_ledger(state))
    artifacts = dict(state.artifacts)
    artifacts["traceability_ledger"] = str(ledger_path)
    state = state.model_copy(update={"artifacts": artifacts})
    audit = build_invariant_audit(state)
    audit_path = artifact_dir(state.method_root, "10_run") / "agentic_invariant_audit.json"
    write_invariant_audit(audit_path, audit)
    artifacts = dict(state.artifacts)
    artifacts["agentic_invariant_audit"] = str(audit_path)
    if audit.blocking_failures:
        rationale = (
            f"Invariant audit found {audit.blocking_failures} blocking evidence-gate failures: "
            + "; ".join(audit.recommended_actions)
        )
        return state.model_copy(
            update={
                "artifacts": artifacts,
                "blocked_reason": state.blocked_reason or "invariant_audit_failed",
                "decisions": [
                    *state.decisions,
                    AgentDecision(
                        node="invariant_auditor",
                        decision="blocked",
                        rationale=rationale,
                        artifact_keys=["agentic_invariant_audit", "traceability_ledger"],
                    ),
                ],
                "next_node": "blocked",
            }
        ).model_dump(mode="json")
    return state.model_copy(
        update={
            "artifacts": artifacts,
            "decisions": [
                *state.decisions,
                AgentDecision(
                    node="invariant_auditor",
                    decision="passed",
                    rationale="Pre-render invariant audit passed.",
                    artifact_keys=["agentic_invariant_audit", "traceability_ledger"],
                ),
            ],
            "next_node": "rendering",
        }
    ).model_dump(mode="json")
