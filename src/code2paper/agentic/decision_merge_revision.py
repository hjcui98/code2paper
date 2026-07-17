from __future__ import annotations

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.decision_models import RevisionRouterProposal
from code2paper.agentic.routing import RevisionRouterDecision
from code2paper.agentic.stage_tool_selection import StageToolSelectionContext, safe_stage_from_proposal


def merge_revision_decision(
    *,
    state: AgenticRunState,
    fallback: RevisionRouterDecision,
    proposal: RevisionRouterProposal,
    selection_context: StageToolSelectionContext,
) -> RevisionRouterDecision:
    if fallback.recommended_next == "blocked":
        return fallback
    if _requires_evidence_return(state.blocked_reason) and (
        proposal.recommended_next.strip() == "authoring" or proposal.selected_stage.strip() == "authoring"
    ):
        return fallback.model_copy(
            update={"rationale": f"{fallback.rationale} Evidence-related blocks cannot be rewritten around."}
        )
    if (
        proposal.recommended_next.strip() == "authoring" or proposal.selected_stage.strip() == "authoring"
    ) and int(state.loop_counters.get("revision") or 0) >= state.max_authoring_revision_rounds:
        return fallback.model_copy(
            update={"rationale": f"{fallback.rationale} Model-proposed authoring revision rejected: budget exhausted."}
        )
    if (
        proposal.recommended_next.strip() == "analysis" or proposal.selected_stage.strip() == "analysis"
    ) and int(state.loop_counters.get("evidence_revision") or 0) >= state.max_evidence_revision_rounds:
        return fallback.model_copy(
            update={"rationale": f"{fallback.rationale} Model-proposed evidence revision rejected: budget exhausted."}
        )
    next_node = proposal.recommended_next.strip() or fallback.recommended_next
    decision = proposal.decision.strip() or fallback.decision
    rationale = proposal.rationale.strip() or fallback.rationale
    blocked_reason = proposal.blocked_reason.strip() or fallback.blocked_reason
    fallback_stage = fallback.selected_stage or _stage_from_next_node(fallback.recommended_next)
    proposed_stage = proposal.selected_stage.strip() or _stage_from_next_node(proposal.recommended_next)
    selected_stage = safe_stage_from_proposal(
        selection_context=selection_context,
        proposed_stage=proposed_stage,
        fallback_stage=fallback_stage,
    )
    if proposed_stage and selected_stage != proposed_stage:
        next_node = fallback.recommended_next
        decision = fallback.decision
        if proposed_stage == "rendering" and "validation_manifest" not in state.artifacts:
            rationale = f"{rationale} Rendering cannot bypass validation."
        else:
            rationale = f"{rationale} Unsafe selected stage rejected; using deterministic stage '{selected_stage}'."
    elif selected_stage:
        next_node = _next_node_from_stage(selected_stage)
    if next_node not in {"authoring", "analysis", "validation", "rendering", "figure_planner", "invariant_audit", "blocked"}:
        next_node = fallback.recommended_next
        decision = fallback.decision
        rationale = f"{rationale} Unsafe revision route rejected; using deterministic route."
        selected_stage = fallback_stage
    if "validation_manifest" not in state.artifacts and next_node in {"rendering", "figure_planner", "invariant_audit"}:
        next_node = "validation"
        decision = "run_validation"
        rationale = f"{rationale} Rendering cannot bypass validation."
        selected_stage = "validation"
    if _requires_evidence_return(state.blocked_reason) and next_node == "authoring":
        next_node = "analysis"
        decision = "return_to_analysis"
        rationale = f"{rationale} Evidence-related blocks must return to analysis before rewriting."
        selected_stage = "analysis"
    if _requires_human_or_config(state.blocked_reason):
        return fallback
    return RevisionRouterDecision(
        decision=decision,
        rationale=rationale,
        blocked_reason=blocked_reason,
        recommended_next=next_node,
        selected_stage=selected_stage,
        artifact_keys=fallback.artifact_keys,
    )


def revision_safety_notes(
    *,
    state: AgenticRunState,
    fallback: RevisionRouterDecision,
    proposal: RevisionRouterProposal,
    final: RevisionRouterDecision,
) -> list[str]:
    notes = ["Model proposal was merged through revision safety rules."]
    if proposal.recommended_next and proposal.recommended_next != final.recommended_next:
        notes.append(f"Proposed next node '{proposal.recommended_next}' was rewritten to '{final.recommended_next}'.")
    if proposal.decision and proposal.decision != final.decision:
        notes.append(f"Proposed decision '{proposal.decision}' was rewritten to '{final.decision}'.")
    if proposal.selected_stage and proposal.selected_stage != final.selected_stage:
        notes.append(f"Proposed selected stage '{proposal.selected_stage}' was rewritten to '{final.selected_stage}'.")
    if _requires_human_or_config(state.blocked_reason) and final == fallback:
        notes.append("Human/configuration block kept deterministic fallback authoritative.")
    return notes


def _requires_evidence_return(reason: str) -> bool:
    lowered = reason.lower()
    return any(token in lowered for token in ("evidence", "coverage", "missing", "unsupported"))


def _requires_human_or_config(reason: str) -> bool:
    lowered = reason.lower()
    return "llm_api_key_missing" in lowered or "llm_required" in lowered


def _stage_from_next_node(next_node: str) -> str:
    if next_node in {"figure_planner", "invariant_audit"}:
        return "rendering"
    if next_node in {"analysis", "authoring", "validation", "rendering"}:
        return next_node
    return ""


def _next_node_from_stage(stage: str) -> str:
    if stage in {"analysis", "authoring", "validation", "rendering"}:
        return stage
    return "blocked"
