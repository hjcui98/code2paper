from __future__ import annotations

from typing import Any

from code2paper.agentic.author_intent_summary import author_intent_summary_from_state
from code2paper.agentic.authoring_constraints import apply_authoring_constraints, write_authoring_constraints
from code2paper.agentic.authoring_context import build_authoring_context, write_authoring_context
from code2paper.agentic.authoring_plan import write_authoring_plan
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace
from code2paper.agentic.claim_verifier import build_claim_verification_report, load_claim_verification_report, write_claim_verification_report
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.decision_core import DecisionProvider, write_decision_trace
from code2paper.agentic.evidence_repair import build_evidence_repair_focus, write_evidence_repair_focus
from code2paper.agentic.evidence_sufficiency import (
    build_evidence_sufficiency_report,
    evidence_sufficiency_trace,
    write_evidence_sufficiency_report,
)
from code2paper.agentic.figure_planner import figure_plan_trace, write_figure_plan
from code2paper.agentic.graph_routes import FROZEN_EVIDENCE_KEYS
from code2paper.agentic.graph_state_io import claim_verification_path, read_json
from code2paper.agentic.routing import load_symbol_index, write_router_decision
from code2paper.core.output_names import artifact_dir, final_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


def evidence_sufficiency_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        if state.blocked_reason:
            return state.model_copy(update={"next_node": "blocked"}).model_dump(mode="json")
        if not FROZEN_EVIDENCE_KEYS.issubset(set(state.artifacts)):
            return state.model_copy(
                update={
                    "blocked_reason": state.blocked_reason or "frozen_evidence_required_for_evidence_sufficiency",
                    "next_node": "blocked",
                }
            ).model_dump(mode="json")
        method_evidence = MethodEvidence.model_validate(read_json(method_output(state.method_root, "evidence")))
        claim_map = ClaimEvidenceMap.model_validate(read_json(method_output(state.method_root, "claims")))
        verification = load_claim_verification_report(state.artifacts["claim_verification"])
        report = build_evidence_sufficiency_report(method_evidence, verification)
        report_path = artifact_dir(state.method_root, "05_grounding") / "agentic_evidence_sufficiency_report.json"
        write_evidence_sufficiency_report(report_path, report)
        decision, trace = evidence_sufficiency_trace(
            report,
            author_intent_summary=author_intent_summary_from_state(state),
            evidence_revision_round=int(state.loop_counters.get("evidence_revision", 0)),
            max_evidence_revision_rounds=state.max_evidence_revision_rounds,
            decision_provider=decision_provider,
        )
        decision_path = artifact_dir(state.method_root, "10_run") / "evidence_sufficiency_decision.json"
        write_router_decision(decision_path, decision)
        trace_path = artifact_dir(state.method_root, "10_run") / "evidence_sufficiency_decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts = {
            **state.artifacts,
            "evidence_sufficiency_report": str(report_path),
            "evidence_sufficiency_decision": str(decision_path),
            "evidence_sufficiency_decision_trace": str(trace_path),
        }
        repair_focus_path = ""
        if decision.recommended_next == "analysis":
            symbol_index = load_symbol_index(state.artifacts.get("symbol_index", ""))
            repair_focus = build_evidence_repair_focus(
                decision=decision,
                report=report,
                claim_verification=verification,
                claim_map=claim_map,
                symbol_index=symbol_index,
                source_decision=str(decision_path),
            )
            repair_focus_path = artifact_dir(state.method_root, "03_analysis") / "agentic_evidence_repair_focus.json"
            write_evidence_repair_focus(repair_focus_path, repair_focus)
            artifacts["evidence_repair_focus"] = str(repair_focus_path)
        updated = state.model_copy(
            update={
                "artifacts": artifacts,
                "decisions": [
                    *state.decisions,
                    AgentDecision(
                        node="evidence_sufficiency",
                        decision=decision.decision,
                        rationale=decision.rationale,
                        artifact_keys=[*decision.artifact_keys, *(["evidence_repair_focus"] if repair_focus_path else [])],
                    ),
                ],
                "next_node": decision.recommended_next,
            }
        )
        if decision.recommended_next == "analysis":
            updated = updated.increment_loop("evidence_revision")
        if decision.recommended_next == "blocked":
            updated = updated.model_copy(update={"blocked_reason": state.blocked_reason or "evidence_sufficiency_failed"})
        return updated.model_dump(mode="json")

    return _run


def authoring_planner_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        if not FROZEN_EVIDENCE_KEYS.issubset(set(state.artifacts)):
            return state.model_copy(
                update={
                    "blocked_reason": state.blocked_reason or "frozen_evidence_required_for_authoring_planner",
                    "next_node": "blocked",
                }
            ).model_dump(mode="json")
        method_evidence = MethodEvidence.model_validate(read_json(method_output(state.method_root, "evidence")))
        claim_map = ClaimEvidenceMap.model_validate(read_json(method_output(state.method_root, "claims")))
        verification_path = claim_verification_path(state)
        if verification_path:
            verification = load_claim_verification_report(verification_path)
        else:
            verification = build_claim_verification_report(method_evidence, claim_map)
            verification_path = artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"
            write_claim_verification_report(verification_path, verification)
        _constrained_evidence, _constrained_claim_map, constraints = apply_authoring_constraints(
            method_evidence=method_evidence,
            claim_map=claim_map,
            report=verification,
        )
        authoring_dir = artifact_dir(state.method_root, "06_authoring")
        constraints_path = authoring_dir / "agentic_authoring_constraints.json"
        write_authoring_constraints(constraints_path, constraints)
        authoring_context = build_authoring_context(
            method_evidence=method_evidence,
            claim_map=claim_map,
            verification=verification,
            constraints=constraints,
        )
        context_path = authoring_dir / "agentic_authoring_context.json"
        write_authoring_context(context_path, authoring_context)
        authoring_plan, trace = authoring_plan_trace(
            authoring_context,
            author_intent_summary=author_intent_summary_from_state(state),
            decision_provider=decision_provider,
        )
        plan_path = authoring_dir / "agentic_authoring_plan.json"
        write_authoring_plan(plan_path, authoring_plan)
        trace_path = authoring_dir / "agentic_authoring_plan_decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts = {
            **state.artifacts,
            "claim_verification": str(verification_path),
            "authoring_constraints": str(constraints_path),
            "authoring_context": str(context_path),
            "authoring_plan": str(plan_path),
            "authoring_plan_decision_trace": str(trace_path),
        }
        decision = AgentDecision(
            node="authoring_planner",
            decision="authoring_plan_ready" if authoring_plan.hard_gate_passed else "authoring_plan_blocked",
            rationale="; ".join(authoring_plan.recommended_actions),
            evidence_ids=sorted({evidence_id for section in authoring_plan.sections for evidence_id in section.evidence_ids}),
            artifact_keys=[
                "authoring_plan",
                "authoring_plan_decision_trace",
                "authoring_context",
                "authoring_constraints",
                "claim_verification",
            ],
        )
        updates = {
            "artifacts": artifacts,
            "decisions": [*state.decisions, decision],
            "next_node": "authoring" if authoring_plan.hard_gate_passed else "blocked",
        }
        if not authoring_plan.hard_gate_passed:
            updates["blocked_reason"] = state.blocked_reason or "authoring_plan_failed_evidence_gate"
        return state.model_copy(update=updates).model_dump(mode="json")

    return _run


def figure_planner_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        if not FROZEN_EVIDENCE_KEYS.issubset(set(state.artifacts)):
            return state.model_copy(
                update={
                    "blocked_reason": state.blocked_reason or "frozen_evidence_required_for_figure_planner",
                    "next_node": "blocked",
                }
            ).model_dump(mode="json")
        method_evidence = MethodEvidence.model_validate(read_json(method_output(state.method_root, "evidence")))
        claim_map = ClaimEvidenceMap.model_validate(read_json(method_output(state.method_root, "claims")))
        verification_path = claim_verification_path(state)
        if verification_path:
            verification = load_claim_verification_report(verification_path)
        else:
            verification = build_claim_verification_report(method_evidence, claim_map)
            verification_path = artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"
            write_claim_verification_report(verification_path, verification)
        figure_plan, trace = figure_plan_trace(
            method_evidence=method_evidence,
            claim_map=claim_map,
            claim_verification=verification,
            author_intent_summary=author_intent_summary_from_state(state),
            decision_provider=decision_provider,
        )
        figure_root = final_dir(state.method_root, "figures")
        figure_plan_path = figure_root / "method_overview.intent.json"
        write_figure_plan(figure_plan_path, figure_plan)
        trace_path = figure_root / "method_overview.intent.decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts = {
            **state.artifacts,
            "claim_verification": str(verification_path),
            "figure_plan": str(figure_plan_path),
            "figure_plan_decision_trace": str(trace_path),
        }
        decision = AgentDecision(
            node="figure_planner",
            decision="figure_plan_ready" if figure_plan.hard_gate_passed else "figure_plan_blocked",
            rationale="; ".join(figure_plan.recommended_actions),
            evidence_ids=sorted({evidence_id for node in figure_plan.nodes for evidence_id in node.evidence_ids}),
            artifact_keys=["figure_plan", "figure_plan_decision_trace", "claim_verification"],
        )
        updates = {
            "artifacts": artifacts,
            "decisions": [*state.decisions, decision],
            "next_node": "invariant_audit" if figure_plan.hard_gate_passed else "blocked",
        }
        if not figure_plan.hard_gate_passed:
            updates["blocked_reason"] = state.blocked_reason or "figure_plan_missing_supported_evidence"
        return state.model_copy(update=updates).model_dump(mode="json")

    return _run
