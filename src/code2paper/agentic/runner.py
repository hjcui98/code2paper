from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.architecture_manifest import (
    build_agentic_architecture_manifest,
    write_agentic_architecture_manifest,
)
from code2paper.agentic.artifact_freshness import check_artifact_freshness, write_artifact_freshness_report
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.agentic.completion_report import build_run_completion_report, write_run_completion_report
from code2paper.agentic.contract_audit import build_agentic_contract_audit, write_agentic_contract_audit
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.decision_core import DecisionProvider
from code2paper.agentic.decision_policy import build_agentic_decision_policy, write_agentic_decision_policy
from code2paper.agentic.evaluation_report import build_run_evaluation_report, write_run_evaluation_report
from code2paper.agentic.graph import build_code2paper_graph
from code2paper.agentic.graph_catalog import build_graph_catalog, write_graph_catalog
from code2paper.agentic.invariant_audit import AgenticInvariantAudit, build_invariant_audit, write_invariant_audit
from code2paper.agentic.langchain_tools import build_langchain_stage_tool_manifest, write_langchain_stage_tool_manifest
from code2paper.agentic.legacy_stage_tools import build_legacy_stage_tool_registry
from code2paper.agentic.llm_decision_provider import build_llm_decision_provider
from code2paper.agentic.semantic_verifier_provider import build_llm_semantic_verifier
from code2paper.agentic.text_evidence_validator import SemanticVerifier
from code2paper.agentic.readiness_report import build_run_readiness_report, write_run_readiness_report
from code2paper.agentic.tools import Code2PaperStageTool, build_tool_catalog, write_tool_catalog
from code2paper.agentic.traceability_ledger import build_traceability_ledger, write_traceability_ledger
from code2paper.core.output_names import artifact_dir
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.export.run_manifest import build_run_manifest, hash_file, write_run_manifest


class AgenticArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    hash: str = ""


class AgenticRunSummary(BaseModel):
    """Run summary for LangGraph-orchestrated Code2Paper executions."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-code2paper-run"
    status: str
    project_root: str
    out_root: str
    blocked_reason: str = ""
    next_node: str = ""
    invariant_audit_passed: bool = False
    invariant_blocking_failures: int = 0
    artifacts: dict[str, AgenticArtifactRecord] = Field(default_factory=dict)
    decisions: list[AgentDecision] = Field(default_factory=list)
    loop_counters: dict[str, int] = Field(default_factory=dict)
    budgets: dict[str, int] = Field(default_factory=dict)


class AgenticRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    state: AgenticRunState
    summary: AgenticRunSummary
    summary_path: Path


GraphInvoker = Callable[[dict[str, Any]], dict[str, Any]]


def run_agentic_code2paper(
    initial_state: AgenticRunState | dict[str, Any],
    *,
    tool_registry: Mapping[str, Code2PaperStageTool] | None = None,
    graph_app: Any | None = None,
    decision_provider: DecisionProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
) -> AgenticRunResult:
    """Run Code2Paper through the agentic graph and persist a decision summary."""

    state = initial_state if isinstance(initial_state, AgenticRunState) else AgenticRunState.model_validate(initial_state)
    app = graph_app
    active_registry: Mapping[str, Code2PaperStageTool] | None = None
    if app is None:
        active_registry = tool_registry or build_legacy_stage_tool_registry()
        provider = decision_provider or _default_decision_provider(state)
        verifier = semantic_verifier or _default_semantic_verifier(state)
        app = build_code2paper_graph(active_registry, decision_provider=provider, semantic_verifier=verifier)
    final_payload = _invoke_graph(app, state.model_dump(mode="json"))
    final_state = AgenticRunState.model_validate(final_payload)
    final_state = _persist_freshness_report(final_state)
    policy = build_agentic_decision_policy()
    policy_path = artifact_dir(final_state.method_root, "10_run") / "agentic_decision_policy.json"
    write_agentic_decision_policy(policy_path, policy)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_decision_policy": str(policy_path)}}
    )
    graph_catalog = build_graph_catalog(active_registry)
    graph_catalog_path = artifact_dir(final_state.method_root, "10_run") / "agentic_graph_catalog.json"
    write_graph_catalog(graph_catalog_path, graph_catalog)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_graph_catalog": str(graph_catalog_path)}}
    )
    tool_catalog = build_tool_catalog(active_registry)
    tool_catalog_path = artifact_dir(final_state.method_root, "10_run") / "agentic_tool_catalog.json"
    write_tool_catalog(tool_catalog_path, tool_catalog)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_tool_catalog": str(tool_catalog_path)}}
    )
    langchain_tool_manifest = build_langchain_stage_tool_manifest(active_registry)
    langchain_tool_manifest_path = artifact_dir(final_state.method_root, "10_run") / "agentic_langchain_tool_manifest.json"
    write_langchain_stage_tool_manifest(langchain_tool_manifest_path, langchain_tool_manifest)
    final_state = final_state.model_copy(
        update={
            "artifacts": {
                **final_state.artifacts,
                "agentic_langchain_tool_manifest": str(langchain_tool_manifest_path),
            }
        }
    )
    architecture_manifest_path = artifact_dir(final_state.method_root, "10_run") / "agentic_architecture_manifest.json"
    write_agentic_architecture_manifest(architecture_manifest_path, build_agentic_architecture_manifest())
    final_state = final_state.model_copy(
        update={
            "artifacts": {**final_state.artifacts, "agentic_architecture_manifest": str(architecture_manifest_path)}
        }
    )
    contract_audit = build_agentic_contract_audit(
        graph_catalog=graph_catalog,
        decision_policy=policy,
        tool_catalog=tool_catalog,
        langchain_tool_manifest=langchain_tool_manifest,
    )
    contract_audit_path = artifact_dir(final_state.method_root, "10_run") / "agentic_contract_audit.json"
    write_agentic_contract_audit(contract_audit_path, contract_audit)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_contract_audit": str(contract_audit_path)}}
    )
    if not contract_audit.passed and not final_state.blocked_reason:
        final_state = final_state.model_copy(update={"blocked_reason": "agentic_contract_audit_failed"})
    ledger_path = artifact_dir(final_state.method_root, "10_run") / "agentic_traceability_ledger.json"
    write_traceability_ledger(ledger_path, build_traceability_ledger(final_state))
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "traceability_ledger": str(ledger_path)}}
    )
    audit = build_invariant_audit(final_state)
    audit_path = artifact_dir(final_state.method_root, "10_run") / "agentic_invariant_audit.json"
    write_invariant_audit(audit_path, audit)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_invariant_audit": str(audit_path)}}
    )
    final_state = _apply_audit_status(final_state, audit)
    readiness_path = artifact_dir(final_state.method_root, "10_run") / "agentic_run_readiness_report.json"
    write_run_readiness_report(readiness_path, build_run_readiness_report(final_state))
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_run_readiness_report": str(readiness_path)}}
    )
    completion_path = artifact_dir(final_state.method_root, "10_run") / "agentic_run_completion_report.json"
    write_run_completion_report(completion_path, build_run_completion_report(final_state))
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_run_completion_report": str(completion_path)}}
    )
    evaluation_path = artifact_dir(final_state.method_root, "10_run") / "agentic_run_evaluation_report.json"
    write_run_evaluation_report(evaluation_path, build_run_evaluation_report(final_state))
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_run_evaluation_report": str(evaluation_path)}}
    )
    summary = build_agentic_run_summary(final_state)
    summary_path = artifact_dir(final_state.method_root, "10_run") / "agentic_run_summary.json"
    write_agentic_run_summary(summary_path, summary)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_run_summary": str(summary_path)}}
    )
    run_manifest_path = artifact_dir(final_state.method_root, "10_run") / "run_manifest.json"
    write_agentic_run_manifest(run_manifest_path, final_state)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "run_manifest": str(run_manifest_path)}}
    )
    summary = build_agentic_run_summary(final_state)
    write_agentic_run_summary(summary_path, summary)
    return AgenticRunResult(state=final_state, summary=summary, summary_path=summary_path)


def build_agentic_run_summary(state: AgenticRunState) -> AgenticRunSummary:
    artifacts = {
        name: AgenticArtifactRecord(path=str(path), hash=hash_file(path))
        for name, path in sorted(state.artifacts.items())
        if str(path).strip()
    }
    status = "blocked" if state.blocked_reason else "success"
    return AgenticRunSummary(
        status=status,
        project_root=str(state.project_root),
        out_root=str(state.out_root),
        blocked_reason=state.blocked_reason,
        next_node=state.next_node,
        invariant_audit_passed=_audit_passed(state),
        invariant_blocking_failures=_audit_blocking_failures(state),
        artifacts=artifacts,
        decisions=state.decisions,
        loop_counters=state.loop_counters,
        budgets=state.budgets,
    )


def write_agentic_run_summary(path: str | Path, summary: AgenticRunSummary) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return output


def write_agentic_run_manifest(path: str | Path, state: AgenticRunState) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_run_manifest(
        project_root=state.project_root,
        author_input_path=state.effective_author_markers_path or state.intent_path or None,
        llm=load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model),
        phase_inputs=_agentic_phase_inputs(state),
        output_paths={name: artifact_path for name, artifact_path in state.artifacts.items() if artifact_path},
        final_draft_path=_first_existing_artifact(state, "text_clean_tex", "text_tex", "text_clean_md", "text_md"),
        validator_reports=[
            path
            for key, path in state.artifacts.items()
            if key
            in {
                "agentic_invariant_audit",
                "agentic_contract_audit",
                "fidelity",
                "qa_claims",
                "qa_numbers",
                "qa_equations",
                "qa_terms",
                "qa_latex",
                "validation_manifest",
            }
            and path
        ],
        agentic_budgets=state.budgets,
    )
    write_run_manifest(output, manifest)
    return output


def load_agentic_run_summary(path: str | Path) -> AgenticRunSummary:
    return AgenticRunSummary.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _agentic_phase_inputs(state: AgenticRunState) -> dict[str, list[str]]:
    return {
        "input_resolution": _existing_values([str(state.project_root), state.author_markers_path, state.intent_path]),
        "intake": _existing_values(
            [
                str(state.project_root),
                state.artifacts.get("resolved_author_markers", ""),
                state.artifacts.get("retrieval_decision_context", ""),
                state.artifacts.get("retrieval_rescan_plan", ""),
                state.artifacts.get("retrieval_rescan_report", ""),
                state.artifacts.get("retrieval_summary", ""),
                state.artifacts.get("retrieval_strategy_manifest", ""),
            ]
        ),
        "analysis": _artifact_values(
            state,
            "evidence_raw",
            "sources",
            "snippets",
            "intake_alignment",
            "evidence_repair_focus",
            "analysis_repair_tasks",
        ),
        "evidence": _artifact_values(
            state, "repo_snapshot", "evidence_raw", "alignment", "analysis", "facts", "evidence_snapshot_v2"
        ),
        "grounding": _artifact_values(state, "evidence_snapshot_v2", "evidence", "atomic_claims_v2", "claims"),
        "evidence_sufficiency": _artifact_values(
            state,
            "evidence",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "claims",
            "claim_verification",
            "evidence_sufficiency_report",
            "evidence_sufficiency_decision_trace",
        ),
        "authoring": _artifact_values(
            state,
            "evidence",
            "repo_snapshot",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "claims",
            "claim_verification",
            "authoring_context",
            "authoring_plan",
            "authoring_plan_decision_trace",
            "grounding_context",
        ),
        "validation": _artifact_values(
            state,
            "text_clean_md",
            "text_md",
            "repo_snapshot",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "authoring_projection",
            "authoring_plan",
            "final_text_claims",
            "text_evidence_validation",
            "final_text_trace",
        ),
        "figure_planner": _artifact_values(
            state,
            "evidence",
            "repo_snapshot",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "artifact_freshness",
            "claims",
            "claim_verification",
            "figure_plan",
            "figure_plan_decision_trace",
        ),
        "invariant_audit": _artifact_values(
            state,
            "repo_snapshot",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "artifact_freshness",
            "evidence",
            "claims",
            "claim_verification",
            "text_claims",
            "figure_plan",
            "figure_plan_decision_trace",
        ),
        "traceability_ledger": _artifact_values(
            state,
            "repo_snapshot",
            "evidence_snapshot_v2",
            "atomic_claims_v2",
            "artifact_freshness",
            "evidence",
            "claims",
            "claim_verification",
            "authoring_constraints",
            "authoring_plan",
            "authoring_plan_decision_trace",
            "text_claims",
            "figure_plan",
            "figure_plan_decision_trace",
        ),
        "rendering": _artifact_values(
            state,
            "text_clean_tex",
            "text_tex",
            "evidence",
            "claims",
            "claim_verification",
            "figure_plan",
            "figure_plan_decision_trace",
        ),
        "finalize": _artifact_values(
            state,
            "text_clean_tex",
            "text_tex",
            "figure_plan",
            "figure_plan_decision_trace",
            "rendering_manifest",
        ),
        "agentic_orchestration": _artifact_values(
            state,
            "agentic_decision_policy",
            "agentic_graph_catalog",
            "agentic_tool_catalog",
            "agentic_langchain_tool_manifest",
            "agentic_contract_audit",
        ),
        "agentic_decisioning": _artifact_values(
            state,
            "agentic_decision_policy",
            "agentic_contract_audit",
            "coverage_critic_decision",
            "coverage_critic_decision_trace",
            "retrieval_decision_context",
            "retrieval_rescan_plan",
            "retrieval_rescan_report",
            "evidence_index",
            "evidence_sufficiency_report",
            "evidence_sufficiency_decision",
            "evidence_sufficiency_decision_trace",
            "evidence_repair_focus",
            "analysis_repair_tasks",
            "analysis_repair_router_decision",
            "analysis_repair_router_decision_trace",
            "authoring_plan_decision_trace",
            "figure_plan_decision_trace",
            "revision_decision_context",
            "revision_router_decision",
            "revision_router_decision_trace",
        ),
        "agentic_readiness": _artifact_values(
            state,
            "agentic_decision_policy",
            "agentic_graph_catalog",
            "agentic_tool_catalog",
            "agentic_contract_audit",
            "traceability_ledger",
            "agentic_invariant_audit",
            "retrieval_decision_context",
            "retrieval_rescan_plan",
            "retrieval_rescan_report",
            "evidence_sufficiency_report",
            "evidence_sufficiency_decision_trace",
            "evidence_repair_focus",
            "analysis_repair_tasks",
            "analysis_repair_router_decision",
            "analysis_repair_router_decision_trace",
            "authoring_plan_decision_trace",
            "figure_plan_decision_trace",
            "revision_decision_context",
            "coverage_critic_decision_trace",
            "revision_router_decision_trace",
        ),
        "agentic_evaluation": _artifact_values(
            state,
            "retrieval_coverage",
            "retrieval_decision_context",
            "retrieval_rescan_plan",
            "retrieval_rescan_report",
            "evidence_sufficiency_report",
            "evidence_repair_focus",
            "analysis_repair_tasks",
            "analysis_repair_router_decision",
            "analysis_repair_router_decision_trace",
            "claim_verification",
            "validation_manifest",
            "traceability_ledger",
            "figure_plan_decision_trace",
            "agentic_invariant_audit",
            "agentic_run_readiness_report",
            "agentic_run_completion_report",
            "agentic_contract_audit",
        ),
    }


def _artifact_values(state: AgenticRunState, *keys: str) -> list[str]:
    return _existing_values([state.artifacts.get(key, "") for key in keys])


def _existing_values(values: list[str]) -> list[str]:
    return [value for value in values if str(value or "").strip()]


def _first_existing_artifact(state: AgenticRunState, *keys: str) -> str | None:
    for key in keys:
        path = state.artifacts.get(key, "")
        if path and Path(path).exists():
            return path
    return None


def _invoke_graph(graph_app: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if hasattr(graph_app, "invoke"):
        result = graph_app.invoke(payload)
    else:
        result = graph_app(payload)
    if not isinstance(result, dict):
        raise TypeError("agentic graph must return a state dict")
    return result


def _default_decision_provider(state: AgenticRunState) -> DecisionProvider | None:
    if not _agentic_llm_decision_enabled(state):
        return None
    config = load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)
    return build_llm_decision_provider(config)


def _persist_freshness_report(state: AgenticRunState) -> AgenticRunState:
    repo_path = state.artifacts.get("repo_snapshot", "")
    evidence_path = state.artifacts.get("evidence_snapshot_v2", "")
    if not repo_path or not evidence_path or not Path(repo_path).exists() or not Path(evidence_path).exists():
        return state
    report = check_artifact_freshness(
        repo_snapshot=load_repo_snapshot(repo_path),
        evidence_snapshot=load_evidence_snapshot_v2(evidence_path),
        artifacts=state.artifacts,
    )
    path = artifact_dir(state.method_root, "10_run") / "agentic_artifact_freshness_report.json"
    write_artifact_freshness_report(path, report)
    blocked_reason = state.blocked_reason
    if report.status == "failed" and (not blocked_reason or report.source_drift):
        blocked_reason = "source_drift" if report.source_drift else "stale_artifact"
    return state.model_copy(
        update={
            "artifacts": {**state.artifacts, "artifact_freshness": str(path)},
            "blocked_reason": blocked_reason,
        }
    )


def _default_semantic_verifier(state: AgenticRunState):
    if state.max_semantic_verifier_calls <= 0 or not _agentic_llm_decision_enabled(state):
        return None
    config = load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)
    return build_llm_semantic_verifier(config)


def _agentic_llm_decision_enabled(state: AgenticRunState) -> bool:
    provider = str(state.llm_provider or "").strip().lower()
    if provider and provider != "none":
        return True
    setting = os.environ.get("CODE2PAPER_AGENTIC_DECISION_PROVIDER", "").strip().lower()
    return setting in {"1", "true", "yes", "on", "llm", "model"}


def _apply_audit_status(state: AgenticRunState, audit: AgenticInvariantAudit) -> AgenticRunState:
    if audit.blocking_failures <= 0 or state.blocked_reason:
        return state
    rationale = (
        f"Invariant audit found {audit.blocking_failures} blocking evidence-gate failures: "
        + "; ".join(audit.recommended_actions)
    )
    return state.model_copy(
        update={
            "blocked_reason": "invariant_audit_failed",
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
    )


def _audit_passed(state: AgenticRunState) -> bool:
    path = state.artifacts.get("agentic_invariant_audit", "")
    if not path:
        return False
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("passed"))


def _audit_blocking_failures(state: AgenticRunState) -> int:
    path = state.artifacts.get("agentic_invariant_audit", "")
    if not path:
        return 0
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return int(payload.get("blocking_failures") or 0)
