from __future__ import annotations

from typing import Any

from code2paper.agentic.analysis_repair_decisioning import analysis_repair_decision_trace
from code2paper.agentic.author_intent_summary import author_intent_summary_from_state
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.coverage_decisioning import coverage_decision_trace
from code2paper.agentic.decision_core import DecisionProvider, write_decision_trace
from code2paper.agentic.graph_state_io import read_json_if_exists, string_mapping
from code2paper.agentic.retrieval import (
    RetrievalCoverageReport,
    RetrievalRescanGuidance,
    augment_retrieval_rescan_plan_with_guidance,
    build_retrieval_decision_context,
    build_retrieval_rescan_plan,
    build_retrieval_rescan_report,
    load_retrieval_decision_context,
    load_retrieval_rescan_plan,
    load_retrieval_rescan_report,
    write_retrieval_decision_context,
    write_retrieval_rescan_plan,
    write_retrieval_rescan_report,
)
from code2paper.agentic.retrieval_summary import (
    build_retrieval_evidence_summary,
    load_retrieval_evidence_summary,
    write_retrieval_evidence_summary,
)
from code2paper.agentic.routing import decision_to_agent_decision, load_coverage_report, load_symbol_index, write_router_decision
from code2paper.core.output_names import artifact_dir


def coverage_critic_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        coverage = load_coverage_report(state.artifacts.get("retrieval_coverage", "")) or _empty_coverage()
        symbol_index = load_symbol_index(state.artifacts.get("symbol_index", ""))
        retrieval_context = load_retrieval_decision_context(state.artifacts.get("retrieval_decision_context", ""))
        retrieval_rescan_plan = load_retrieval_rescan_plan(state.artifacts.get("retrieval_rescan_plan", ""))
        retrieval_rescan_report = load_retrieval_rescan_report(state.artifacts.get("retrieval_rescan_report", ""))
        retrieval_summary = load_retrieval_evidence_summary(state.artifacts.get("retrieval_summary", ""))
        author_intent_summary = author_intent_summary_from_state(state)
        artifacts = dict(state.artifacts)
        if retrieval_context is None:
            retrieval_context = build_retrieval_decision_context(coverage=coverage, symbol_index=symbol_index)
            context_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_decision_context.json"
            write_retrieval_decision_context(context_path, retrieval_context)
            artifacts["retrieval_decision_context"] = str(context_path)
        if retrieval_rescan_plan is None:
            retrieval_rescan_plan = build_retrieval_rescan_plan(
                coverage=coverage,
                context=retrieval_context,
                repair_tasks_payload=read_json_if_exists(state.artifacts.get("analysis_repair_tasks", "")),
            )
            rescan_plan_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_rescan_plan.json"
            write_retrieval_rescan_plan(rescan_plan_path, retrieval_rescan_plan)
            artifacts["retrieval_rescan_plan"] = str(rescan_plan_path)
        if retrieval_rescan_report is None:
            retrieval_rescan_report = build_retrieval_rescan_report(
                plan=retrieval_rescan_plan,
                snippets_payload=read_json_if_exists(state.artifacts.get("snippets", "")),
                snippet_to_evidence=string_mapping(read_json_if_exists(state.artifacts.get("evidence_index", ""))),
                symbol_index=symbol_index,
            )
            rescan_report_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_rescan_report.json"
            write_retrieval_rescan_report(rescan_report_path, retrieval_rescan_report)
            artifacts["retrieval_rescan_report"] = str(rescan_report_path)
        if retrieval_summary is None:
            retrieval_summary = build_retrieval_evidence_summary(
                coverage=coverage,
                symbol_index=symbol_index or _empty_symbol_index(),
                context=retrieval_context,
                rescan_report=retrieval_rescan_report,
            )
            summary_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_summary.json"
            write_retrieval_evidence_summary(summary_path, retrieval_summary)
            artifacts["retrieval_summary"] = str(summary_path)
        decision, trace = coverage_decision_trace(
            coverage=coverage,
            symbol_index=symbol_index,
            retrieval_context=retrieval_context,
            retrieval_rescan_plan=retrieval_rescan_plan,
            retrieval_rescan_report=retrieval_rescan_report,
            retrieval_summary=retrieval_summary,
            author_intent_summary=author_intent_summary,
            retrieval_round=int(state.loop_counters.get("retrieval", 0)),
            max_retrieval_rounds=state.max_retrieval_rounds,
            decision_provider=decision_provider,
        )
        if decision.recommended_next == "intake":
            guided_plan = augment_retrieval_rescan_plan_with_guidance(
                plan=retrieval_rescan_plan,
                guidance=RetrievalRescanGuidance(
                    recommended_paths=list(decision.recommended_paths),
                    recommended_symbols=list(decision.recommended_symbols),
                    recommended_queries=list(decision.recommended_queries),
                ),
            )
            if guided_plan != retrieval_rescan_plan:
                retrieval_rescan_plan = guided_plan
                rescan_plan_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_rescan_plan.json"
                write_retrieval_rescan_plan(rescan_plan_path, retrieval_rescan_plan)
                artifacts["retrieval_rescan_plan"] = str(rescan_plan_path)
                retrieval_rescan_report = build_retrieval_rescan_report(
                    plan=retrieval_rescan_plan,
                    snippets_payload=read_json_if_exists(state.artifacts.get("snippets", "")),
                    snippet_to_evidence=string_mapping(read_json_if_exists(state.artifacts.get("evidence_index", ""))),
                    symbol_index=symbol_index,
                )
                rescan_report_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_rescan_report.json"
                write_retrieval_rescan_report(rescan_report_path, retrieval_rescan_report)
                artifacts["retrieval_rescan_report"] = str(rescan_report_path)
                retrieval_summary = build_retrieval_evidence_summary(
                    coverage=coverage,
                    symbol_index=symbol_index or _empty_symbol_index(),
                    context=retrieval_context,
                    rescan_report=retrieval_rescan_report,
                )
                summary_path = artifact_dir(state.method_root, "10_run") / "agentic_retrieval_summary.json"
                write_retrieval_evidence_summary(summary_path, retrieval_summary)
                artifacts["retrieval_summary"] = str(summary_path)
        decision_path = artifact_dir(state.method_root, "10_run") / "coverage_critic_decision.json"
        write_router_decision(decision_path, decision)
        trace_path = artifact_dir(state.method_root, "10_run") / "coverage_critic_decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts["coverage_critic_decision"] = str(decision_path)
        artifacts["coverage_critic_decision_trace"] = str(trace_path)
        updated = state.model_copy(
            update={
                "artifacts": artifacts,
                "decisions": [*state.decisions, decision_to_agent_decision("coverage_critic", decision)],
                "next_node": decision.recommended_next,
            }
        )
        if decision.recommended_next == "intake":
            updated = updated.increment_loop("retrieval")
        return updated.model_dump(mode="json")

    return _run


def analysis_repair_router_node(*, decision_provider: DecisionProvider | None = None):
    def _run(raw_state: dict[str, Any]) -> dict[str, Any]:
        state = AgenticRunState.model_validate(raw_state)
        if state.blocked_reason:
            return state.model_copy(update={"next_node": "blocked"}).model_dump(mode="json")

        tasks = read_json_if_exists(state.artifacts.get("analysis_repair_tasks", ""))
        decision, trace = analysis_repair_decision_trace(
            tasks,
            author_intent_summary=author_intent_summary_from_state(state),
            retrieval_round=int(state.loop_counters.get("retrieval", 0)),
            max_retrieval_rounds=state.max_retrieval_rounds,
            decision_provider=decision_provider,
        )
        decision_path = artifact_dir(state.method_root, "10_run") / "analysis_repair_router_decision.json"
        write_router_decision(decision_path, decision)
        trace_path = artifact_dir(state.method_root, "10_run") / "analysis_repair_router_decision_trace.json"
        write_decision_trace(trace_path, trace)
        artifacts = {
            **state.artifacts,
            "analysis_repair_router_decision": str(decision_path),
            "analysis_repair_router_decision_trace": str(trace_path),
        }
        agent_decision = decision_to_agent_decision("analysis_repair_router", decision)
        agent_decision = agent_decision.model_copy(
            update={"artifact_keys": [*agent_decision.artifact_keys, "analysis_repair_router_decision_trace"]}
        )
        if decision.recommended_next == "intake":
            updated = state.model_copy(
                update={
                    "artifacts": artifacts,
                    "decisions": [*state.decisions, agent_decision],
                    "next_node": decision.recommended_next,
                }
            ).increment_loop("retrieval")
            return updated.model_dump(mode="json")

        return state.model_copy(
            update={
                "artifacts": artifacts,
                "decisions": [*state.decisions, agent_decision],
                "next_node": decision.recommended_next,
            }
        ).model_dump(mode="json")

    return _run


def _empty_coverage() -> RetrievalCoverageReport:
    return RetrievalCoverageReport(overall_score=0.0, recommended_actions=["build_retrieval_plan_from_author_intent"])


def _empty_symbol_index():
    from code2paper.agentic.retrieval import SymbolIndexReport

    return SymbolIndexReport(project_root="", indexed_symbols=0)
