from __future__ import annotations

from typing import Any

from code2paper.agentic.author_intent_summary import author_intent_summary_from_state
from code2paper.agentic.authoring_constraints import apply_authoring_constraints, write_authoring_constraints
from code2paper.agentic.authoring_context import build_authoring_context, write_authoring_context
from code2paper.agentic.authoring_plan import write_authoring_plan
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace
from code2paper.agentic.authoring_projection import build_authoring_projection, write_authoring_projection
from code2paper.agentic.atomic_claim_v2 import load_atomic_claims_v2
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.evidence_compiler_v3 import load_atomic_claims_v3, load_evidence_packets_v3
from code2paper.agentic.evidence_relations_v2 import build_evidence_relations_v2, write_evidence_relations_v2
from code2paper.agentic.figure_scene import build_figure_scene_graph, write_figure_scene_graph
from code2paper.agentic.figure_relation_validator import validate_figure_relations, write_figure_relation_validation
from code2paper.agentic.artifact_freshness import check_artifact_freshness, write_artifact_freshness_report
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.agentic.claim_verifier import build_claim_verification_report, load_claim_verification_report, write_claim_verification_report
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.decision_core import DecisionProvider, write_decision_trace
from code2paper.agentic.evidence_repair import (
    EvidenceRepairClaimTarget,
    EvidenceRepairFocus,
    build_evidence_repair_focus,
    rank_evidence_repair_candidates,
    write_evidence_repair_focus,
)
from code2paper.agentic.evidence_sufficiency import (
    build_evidence_sufficiency_report,
    build_v3_evidence_sufficiency_report,
    evidence_sufficiency_trace,
    write_evidence_sufficiency_report,
)
from code2paper.agentic.figure_planner import figure_plan_trace, write_figure_plan
from code2paper.agentic.graph_routes import FROZEN_EVIDENCE_KEYS
from code2paper.agentic.graph_state_io import claim_verification_path, read_json
from code2paper.agentic.intent_obligations import (
    AuthoringObligationCoverageReport,
    IntentObligationGraphV1,
    build_authoring_obligation_coverage,
    compile_intent_obligation_graph,
    write_authoring_obligation_coverage,
    write_intent_obligation_graph,
)
from code2paper.agentic.routing import load_symbol_index, write_router_decision
from code2paper.agentic.traceability_artifacts import unsupported_claim_ids
from code2paper.core.output_names import artifact_dir, final_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, RawEvidencePack


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
        if state.artifacts.get("repo_snapshot") and not {
            "evidence_snapshot_v2", "atomic_claims_v2"
        }.issubset(set(state.artifacts)):
            return state.model_copy(
                update={
                    "blocked_reason": "formal_evidence_v2_required_for_evidence_sufficiency",
                    "next_node": "blocked",
                }
            ).model_dump(mode="json")
        method_evidence = MethodEvidence.model_validate(read_json(method_output(state.method_root, "evidence")))
        claim_map = ClaimEvidenceMap.model_validate(read_json(method_output(state.method_root, "claims")))
        verification = load_claim_verification_report(state.artifacts["claim_verification"])
        v3_available = bool(
            state.artifacts.get("atomic_claims_v3")
            and state.artifacts.get("evidence_packets_v3")
        )
        report = (
            build_v3_evidence_sufficiency_report(
                load_atomic_claims_v3(state.artifacts["atomic_claims_v3"]),
                load_evidence_packets_v3(state.artifacts["evidence_packets_v3"]),
            )
            if v3_available
            else build_evidence_sufficiency_report(method_evidence, verification)
        )
        report_path = artifact_dir(state.method_root, "05_grounding") / "agentic_evidence_sufficiency_report.json"
        write_evidence_sufficiency_report(report_path, report)
        decision, trace = evidence_sufficiency_trace(
            report,
            author_intent_summary=author_intent_summary_from_state(state),
            evidence_revision_round=int(state.loop_counters.get("evidence_revision", 0)),
            max_evidence_revision_rounds=(0 if v3_available else state.max_evidence_revision_rounds),
            decision_provider=(None if v3_available else decision_provider),
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
        if state.artifacts.get("repo_snapshot") and not {
            "evidence_snapshot_v2", "atomic_claims_v2"
        }.issubset(set(state.artifacts)):
            return state.model_copy(
                update={
                    "blocked_reason": "formal_evidence_v2_required_for_authoring_planner",
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
        author_intent_summary = author_intent_summary_from_state(state)
        projection = build_authoring_projection(
            method_evidence=method_evidence,
            claim_map=claim_map,
            verification=verification,
            raw_evidence=(
                RawEvidencePack.model_validate(read_json(state.artifacts["evidence_raw"]))
                if state.artifacts.get("evidence_raw")
                else None
            ),
            evidence_snapshot_v2=(
                load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
                if state.artifacts.get("evidence_snapshot_v2")
                else None
            ),
            atomic_claims_v2=(
                load_atomic_claims_v2(state.artifacts["atomic_claims_v2"])
                if state.artifacts.get("atomic_claims_v2")
                else None
            ),
            atomic_claims_v3=(
                load_atomic_claims_v3(state.artifacts["atomic_claims_v3"])
                if state.artifacts.get("atomic_claims_v3")
                else None
            ),
            evidence_packets_v3=(
                load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
                if state.artifacts.get("evidence_packets_v3")
                else None
            ),
        )
        projection_path = authoring_dir / "agentic_authoring_input_projection.json"
        write_authoring_projection(projection_path, projection)
        obligation_graph = compile_intent_obligation_graph(author_intent_summary)
        obligation_graph_path = artifact_dir(state.method_root, "01_input") / "agentic_intent_obligation_graph.json"
        write_intent_obligation_graph(obligation_graph_path, obligation_graph)
        obligation_coverage = build_authoring_obligation_coverage(obligation_graph, projection)
        obligation_coverage_path = authoring_dir / "agentic_authoring_obligation_coverage.json"
        write_authoring_obligation_coverage(obligation_coverage_path, obligation_coverage)
        authoring_plan, trace = authoring_plan_trace(
            authoring_context,
            projection=projection,
            author_intent_summary=author_intent_summary,
            obligation_coverage=obligation_coverage,
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
            "authoring_projection": str(projection_path),
            "intent_obligation_graph": str(obligation_graph_path),
            "authoring_obligation_coverage": str(obligation_coverage_path),
            "authoring_plan": str(plan_path),
            "authoring_plan_decision_trace": str(trace_path),
        }
        # Obligation repair is a distinct decision budget. Evidence sufficiency
        # often consumes its own revision budget before authoring coverage is even
        # observable; sharing that counter made the new author-intent decision
        # unreachable in the RAP sentinel.
        current_revision_round = int(state.loop_counters.get("obligation_revision", 0))
        quality_repair_requested = obligation_coverage.recommended_next in {
            "targeted_evidence_repair",
            "claim_expansion",
        }
        quality_repair_available = (
            quality_repair_requested
            and current_revision_round < state.max_evidence_revision_rounds
        )
        if quality_repair_available:
            repair_focus = _obligation_repair_focus(
                graph=obligation_graph,
                report=obligation_coverage,
                source_decision=str(obligation_coverage_path),
                symbol_index=load_symbol_index(state.artifacts.get("symbol_index", "")),
            )
            repair_focus_path = artifact_dir(state.method_root, "03_analysis") / "agentic_evidence_repair_focus.json"
            write_evidence_repair_focus(repair_focus_path, repair_focus)
            artifacts["evidence_repair_focus"] = str(repair_focus_path)
        decision = AgentDecision(
            node="authoring_planner",
            decision=(
                "authoring_obligation_repair"
                if quality_repair_available
                else "authoring_plan_ready"
                if authoring_plan.hard_gate_passed
                else "authoring_plan_blocked"
            ),
            rationale="; ".join([
                *authoring_plan.recommended_actions,
                *obligation_coverage.recommended_actions,
                (
                    f"obligation_revision_budget={current_revision_round}/{state.max_evidence_revision_rounds}"
                    if quality_repair_requested
                    else ""
                ),
            ]).strip("; "),
            evidence_ids=sorted({evidence_id for section in authoring_plan.sections for evidence_id in section.evidence_ids}),
            artifact_keys=[
                "authoring_plan",
                "authoring_plan_decision_trace",
                "authoring_context",
                "authoring_constraints",
                "authoring_projection",
                "intent_obligation_graph",
                "authoring_obligation_coverage",
                *(["evidence_repair_focus"] if quality_repair_available else []),
                "claim_verification",
            ],
        )
        if quality_repair_available:
            updated = state.model_copy(
                update={
                    "artifacts": artifacts,
                    "decisions": [*state.decisions, decision],
                    "pending_gaps": list(dict.fromkeys([
                        *state.pending_gaps,
                        *obligation_coverage.unresolved_must_cover_ids,
                    ])),
                    "next_node": "intake",
                }
            ).increment_loop("obligation_revision")
            return updated.model_dump(mode="json")
        updates = {
            "artifacts": artifacts,
            "decisions": [*state.decisions, decision],
            "next_node": "authoring" if authoring_plan.hard_gate_passed else "blocked",
        }
        if not authoring_plan.hard_gate_passed:
            updates["blocked_reason"] = state.blocked_reason or "authoring_plan_failed_evidence_gate"
        return state.model_copy(update=updates).model_dump(mode="json")

    return _run


def _obligation_repair_focus(
    *,
    graph: IntentObligationGraphV1,
    report: AuthoringObligationCoverageReport,
    source_decision: str,
    symbol_index=None,
) -> EvidenceRepairFocus:
    unresolved_ids = set(report.unresolved_must_cover_ids)
    if not unresolved_ids and report.recommended_next == "claim_expansion":
        unresolved_ids = {
            item.obligation_id
            for item in graph.obligations
            if item.priority in {"must_cover", "should_cover"}
        }
    obligations = [
        item for item in graph.obligations if item.obligation_id in unresolved_ids
    ]
    queries = [
        f"{item.obligation_id}: {item.author_text}"[:220]
        for item in obligations
    ]
    claim_targets = [
        EvidenceRepairClaimTarget(
            claim_id=item.obligation_id,
            claim_query=query,
            candidates=rank_evidence_repair_candidates(
                query=query,
                symbol_index=symbol_index,
            ),
        )
        for item, query in zip(obligations, queries)
    ]
    ranked_paths = [
        candidate.path
        for target in claim_targets
        for candidate in target.candidates
        if candidate.path
    ]
    priority_paths = list(dict.fromkeys([
        *ranked_paths,
        *(
        path for item in obligations for path in item.candidate_paths if path
        ),
    ]))[:40]
    symbol_targets = [
        {
            "claim_id": target.claim_id,
            "path": candidate.path,
            "symbol": candidate.symbol,
            "kind": candidate.kind,
            "source": "intent_obligation_graph",
        }
        for target in claim_targets
        for candidate in target.candidates
        if candidate.path and candidate.symbol
    ][:80]
    keywords = list(dict.fromkeys(
        token.lower().strip(".,:;()[]{}")
        for item in obligations
        for query in item.retrieval_queries
        for token in query.replace("_", " ").replace("-", " ").split()
        if len(token.strip(".,:;()[]{}")) >= 4
    ))[:80]
    return EvidenceRepairFocus(
        mode="obligation-evidence-repair-focus-v1",
        source_decision=source_decision,
        focus_claim_ids=[item.obligation_id for item in obligations],
        missing_evidence_claim_ids=[item.obligation_id for item in obligations],
        claim_queries=queries,
        search_keywords=keywords,
        priority_paths=priority_paths,
        claim_support_files=priority_paths,
        symbol_targets=symbol_targets,
        claim_targets=claim_targets,
        recommended_actions=[
            "retrieve_minimal_code_evidence_for_unresolved_author_obligations",
            "decompose_wide_author_wording_into_code_supported_subclaims",
        ],
    )


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
        formal_p2 = bool(state.artifacts.get("repo_snapshot"))
        if formal_p2 and not state.artifacts.get("evidence_snapshot_v2"):
            return state.model_copy(update={"blocked_reason": "evidence_v2_required_for_figure_scene", "next_node": "blocked"}).model_dump(mode="json")
        evidence_v2 = load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"]) if formal_p2 else None
        code_graph = read_json(state.artifacts["code_graph"]) if state.artifacts.get("code_graph") else {}
        relations = build_evidence_relations_v2(method_evidence, evidence_v2, code_graph=code_graph) if evidence_v2 else None
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
            evidence_relations=relations,
            forbidden_claim_ids=unsupported_claim_ids(state),
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
        relation_gate_passed = True
        if relations is not None and evidence_v2 is not None:
            relations_path = figure_root / "agentic_evidence_relations_v2.json"
            write_evidence_relations_v2(relations_path, relations)
            scene = build_figure_scene_graph(figure_plan, relations)
            scene_path = figure_root / "agentic_figure_scene_graph.json"
            write_figure_scene_graph(scene_path, scene)
            relation_validation = validate_figure_relations(scene, relations, evidence_v2)
            relation_validation_path = figure_root / "agentic_figure_relation_validation.json"
            write_figure_relation_validation(relation_validation_path, relation_validation)
            pre_render_path = figure_root / "agentic_pre_render_audit.json"
            write_figure_relation_validation(pre_render_path, relation_validation)
            artifacts.update({
                "evidence_relations_v2": str(relations_path), "figure_scene": str(scene_path),
                "figure_relation_validation": str(relation_validation_path), "pre_render_audit": str(pre_render_path),
            })
            relation_gate_passed = relation_validation.hard_gate_passed
            freshness = check_artifact_freshness(
                repo_snapshot=load_repo_snapshot(state.artifacts["repo_snapshot"]),
                evidence_snapshot=evidence_v2,
                artifacts=artifacts,
            )
            freshness_path = artifact_dir(state.method_root, "10_run") / "agentic_artifact_freshness_report.json"
            write_artifact_freshness_report(freshness_path, freshness)
            artifacts["artifact_freshness"] = str(freshness_path)
            if freshness.status != "passed":
                relation_gate_passed = False
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
            "next_node": "invariant_audit" if figure_plan.hard_gate_passed and relation_gate_passed else "blocked",
        }
        if not figure_plan.hard_gate_passed or not relation_gate_passed:
            updates["blocked_reason"] = state.blocked_reason or "figure_scene_relation_gate_failed"
        return state.model_copy(update=updates).model_dump(mode="json")

    return _run
