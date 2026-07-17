from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.readiness_decision_traces import check_decision_traces
from code2paper.agentic.readiness_io import artifact_exists, artifact_json, has_any_artifact, string_list
from code2paper.agentic.readiness_models import AgenticRunReadinessReport, ReadinessCheck
from code2paper.agentic.readiness_output_contracts import (
    check_authoring_context_contract,
    check_invariant_audit_contract,
    check_traceability_ledger_contract,
)


def build_run_readiness_report(state: AgenticRunState) -> AgenticRunReadinessReport:
    """Check the run-level artifacts that make an agentic run auditable."""

    checks = [
        _check_run_not_blocked(state),
        _check_orchestration_catalogs(state),
        _check_frozen_evidence_contract(state),
        _check_evidence_sufficiency_contract(state),
        _check_analysis_repair_tasks_contract(state),
        _check_retrieval_decision_context(state),
        check_decision_traces(state),
        check_authoring_context_contract(state),
        check_traceability_ledger_contract(state),
        check_invariant_audit_contract(state),
    ]
    blocking_failures = sum(1 for check in checks if check.blocking and not check.passed)
    return AgenticRunReadinessReport(
        passed=blocking_failures == 0,
        blocking_failures=blocking_failures,
        checks=checks,
        recommended_actions=_recommended_actions(checks),
    )


def write_run_readiness_report(path: str | Path, report: AgenticRunReadinessReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_run_readiness_report(path: str | Path) -> AgenticRunReadinessReport:
    return AgenticRunReadinessReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _check_run_not_blocked(state: AgenticRunState) -> ReadinessCheck:
    passed = not bool(state.blocked_reason)
    return ReadinessCheck(
        name="run_status",
        passed=passed,
        message="Agentic run reached a non-blocked final state."
        if passed
        else f"Agentic run is blocked: {state.blocked_reason}",
    )


def _check_orchestration_catalogs(state: AgenticRunState) -> ReadinessCheck:
    required = [
        "agentic_decision_policy",
        "agentic_graph_catalog",
        "agentic_tool_catalog",
        "agentic_langchain_tool_manifest",
        "agentic_architecture_manifest",
        "agentic_contract_audit",
    ]
    missing = [key for key in required if not artifact_json(state, key)]
    contract_audit = artifact_json(state, "agentic_contract_audit")
    contract_failed = bool(contract_audit) and not bool(contract_audit.get("passed"))
    problems: list[str] = []
    if missing:
        problems.append("Missing or unreadable orchestration policy/catalog artifacts: " + ", ".join(missing))
    if contract_failed:
        problems.append("agentic_contract_audit did not pass")
    return ReadinessCheck(
        name="orchestration_catalogs",
        passed=not problems,
        message="Decision policy, graph topology, stage tool catalog, LangChain tool manifest, architecture manifest, and contract audit are present and consistent."
        if not problems
        else "; ".join(problems),
        artifact_keys=required,
    )


def _check_frozen_evidence_contract(state: AgenticRunState) -> ReadinessCheck:
    formal_v2 = artifact_exists(state, "repo_snapshot")
    required = ["evidence", "claims", "claim_verification"]
    if formal_v2:
        required.extend(["intent_spec", "repo_snapshot", "evidence_snapshot_v2", "atomic_claims_v2", "artifact_freshness"])
    missing = [key for key in required if not artifact_json(state, key)]
    problems: list[str] = []
    if missing:
        problems.append("missing or unreadable artifacts: " + ", ".join(missing))
    if formal_v2 and not missing:
        repo = artifact_json(state, "repo_snapshot")
        evidence = artifact_json(state, "evidence_snapshot_v2")
        atomic = artifact_json(state, "atomic_claims_v2")
        freshness = artifact_json(state, "artifact_freshness")
        if evidence.get("repo_snapshot_id") != repo.get("snapshot_id"):
            problems.append("EvidenceSnapshotV2 repo_snapshot_id mismatch")
        if evidence.get("project_tree_hash") != repo.get("project_tree_hash"):
            problems.append("EvidenceSnapshotV2 project_tree_hash mismatch")
        if atomic.get("evidence_snapshot_id") != evidence.get("evidence_snapshot_id"):
            problems.append("AtomicClaimSetV2 evidence_snapshot_id mismatch")
        if atomic.get("evidence_snapshot_digest") != evidence.get("content_digest"):
            problems.append("AtomicClaimSetV2 evidence_snapshot_digest mismatch")
        if freshness.get("status") != "passed" or freshness.get("source_drift"):
            problems.append("artifact freshness did not pass or source drift was detected")
    return ReadinessCheck(
        name="frozen_evidence_contract",
        passed=not problems,
        message="Frozen repo snapshot, exact EvidenceSnapshotV2, verified AtomicClaimSetV2, and freshness gate are consistent."
        if formal_v2 and not problems
        else "Frozen code evidence, claim map, and claim verification are present."
        if not problems
        else "; ".join(problems),
        artifact_keys=required,
    )


def _check_evidence_sufficiency_contract(state: AgenticRunState) -> ReadinessCheck:
    if not has_any_artifact(state, "evidence", "claims", "claim_verification"):
        return ReadinessCheck(
            name="evidence_sufficiency_contract",
            passed=True,
            blocking=False,
            message="Frozen evidence was not produced; evidence sufficiency review is not required.",
            artifact_keys=["evidence_sufficiency_report", "evidence_sufficiency_decision_trace"],
        )
    required = ["evidence_sufficiency_report", "evidence_sufficiency_decision_trace"]
    missing = [key for key in required if not artifact_json(state, key)]
    return ReadinessCheck(
        name="evidence_sufficiency_contract",
        passed=not missing,
        message="Evidence sufficiency report and decision trace are present."
        if not missing
        else "Frozen evidence exists but sufficiency review artifacts are missing or unreadable: " + ", ".join(missing),
        artifact_keys=[*required, "evidence", "claims", "claim_verification"],
    )


def _check_analysis_repair_tasks_contract(state: AgenticRunState) -> ReadinessCheck:
    focus = artifact_json(state, "evidence_repair_focus")
    if not focus:
        return ReadinessCheck(
            name="analysis_repair_tasks_contract",
            passed=True,
            blocking=False,
            message="No evidence repair focus was produced; analysis repair tasks are not required.",
            artifact_keys=["evidence_repair_focus", "analysis_repair_tasks", "analysis_repair_router_decision_trace"],
        )
    tasks = artifact_json(state, "analysis_repair_tasks")
    router_trace = artifact_json(state, "analysis_repair_router_decision_trace")
    focus_claim_ids = string_list(focus.get("focus_claim_ids"))
    task_claim_ids = {
        str(task.get("claim_id") or "").strip()
        for task in tasks.get("tasks", [])
        if isinstance(task, dict) and str(task.get("claim_id") or "").strip()
    }
    missing_claim_ids = [claim_id for claim_id in focus_claim_ids if claim_id not in task_claim_ids]
    malformed_tasks = [
        str(task.get("claim_id") or index)
        for index, task in enumerate(tasks.get("tasks", []), start=1)
        if isinstance(task, dict) and "candidates" not in task
    ]
    problems: list[str] = []
    if not tasks:
        problems.append("analysis repair tasks artifact is missing or unreadable")
    if tasks and not router_trace:
        problems.append("analysis repair tasks have no readable router decision trace")
    if missing_claim_ids:
        problems.append("repair tasks missing focus claims: " + ", ".join(missing_claim_ids))
    if malformed_tasks:
        problems.append("repair tasks missing candidate lists: " + ", ".join(malformed_tasks))
    return ReadinessCheck(
        name="analysis_repair_tasks_contract",
        passed=not problems,
        message="Evidence repair focus has claim-level analysis repair tasks."
        if not problems
        else "; ".join(problems),
        artifact_keys=["evidence_repair_focus", "analysis_repair_tasks", "analysis_repair_router_decision_trace"],
    )


def _check_retrieval_decision_context(state: AgenticRunState) -> ReadinessCheck:
    required = [
        "retrieval_decision_context",
        "retrieval_rescan_plan",
        "retrieval_rescan_report",
        "retrieval_strategy_manifest",
    ]
    if not artifact_exists(state, "retrieval_coverage") and not artifact_exists(state, "symbol_index"):
        return ReadinessCheck(
            name="retrieval_decision_context",
            passed=True,
            blocking=False,
            message="No retrieval coverage or symbol index artifact was produced; retrieval context is not required.",
            artifact_keys=required,
        )
    missing = [key for key in required if not artifact_json(state, key)]
    return ReadinessCheck(
        name="retrieval_decision_context",
        passed=not missing,
        message="Retrieval decision context, bounded rescan plan, rescan outcome report, and retrieval strategy manifest are present for coverage criticism."
        if not missing
        else "Retrieval coverage exists but retrieval decision artifacts are missing or unreadable: " + ", ".join(missing),
        artifact_keys=[
            "retrieval_coverage",
            "symbol_index",
            *required,
        ],
    )


def _recommended_actions(checks: list[ReadinessCheck]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.passed or not check.blocking:
            continue
        actions.append(f"repair_{check.name}")
    if not actions:
        actions.append("agentic_run_is_ready_for_review")
    return actions
