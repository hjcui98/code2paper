from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.architecture_manifest import (
    build_agentic_architecture_manifest,
    write_agentic_architecture_manifest,
)
from code2paper.agentic.artifact_freshness import check_artifact_freshness, write_artifact_freshness_report
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.repo_snapshot import build_repo_snapshot, load_repo_snapshot
from code2paper.agentic.completion_report import build_run_completion_report, write_run_completion_report
from code2paper.agentic.contract_audit import build_agentic_contract_audit, write_agentic_contract_audit
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.checkpointing import (
    CheckpointMetadataV2,
    checkpoint_config,
    checkpoint_thread_id,
    validate_resume_state,
)
from code2paper.agentic.decision_core import DecisionProvider
from code2paper.agentic.decision_policy import build_agentic_decision_policy, write_agentic_decision_policy
from code2paper.agentic.execution_profile import (
    execution_profile_from_env,
    load_execution_profile,
)
from code2paper.agentic.evaluation_report import build_run_evaluation_report, write_run_evaluation_report
from code2paper.agentic.graph import build_code2paper_graph
from code2paper.agentic.graph_catalog import build_graph_catalog, write_graph_catalog
from code2paper.agentic.invariant_audit import AgenticInvariantAudit, build_invariant_audit, write_invariant_audit
from code2paper.agentic.langchain_tools import build_langchain_stage_tool_manifest, write_langchain_stage_tool_manifest
from code2paper.agentic.legacy_stage_tools import build_legacy_stage_tool_registry
from code2paper.agentic.llm_decision_provider import build_llm_decision_provider
from code2paper.agentic.semantic_verifier_provider import build_llm_semantic_verifier
from code2paper.agentic.text_evidence_validator import SemanticVerifier
from code2paper.agentic.r8_acceptance import (
    R8ProtocolSettings,
    check_r8_acceptance,
    compute_trace_digest,
    write_r8_acceptance_report,
)
from code2paper.agentic.readiness_report import build_run_readiness_report, write_run_readiness_report
from code2paper.agentic.tools import Code2PaperStageTool, build_tool_catalog, write_tool_catalog
from code2paper.agentic.traceability_ledger import build_traceability_ledger, write_traceability_ledger
from code2paper.agentic.trust_tools import write_trust_tool_manifest
from code2paper.core.output_names import artifact_dir
from code2paper.llm.role_config import (
    LLM_CALLING_ROLES,
    METHOD_WRITER,
    apply_role_config,
    writer_cumulative_budget,
)
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
    # R8.1 protocol fields: trace digest, tool-call trace refs, final
    # state digest, environment, temperature, source authority policy.
    # These are populated by ``build_agentic_run_summary`` so the R8
    # acceptance checker can verify trace reproducibility, checkpoint
    # consistency, and protocol compliance from the run directory.
    run_id: str = ""
    project_id: str = ""
    trace_digest: str = ""
    tool_call_trace_refs: list[str] = Field(default_factory=list)
    final_state_digest: str = ""
    resumed_from_final_state_digest: str = ""
    environment: dict[str, str] = Field(default_factory=dict)
    temperature: float | None = None
    source_authority_policy: dict[str, Any] = Field(default_factory=dict)
    # R8.1 protocol evidence: paper was read only AFTER Method authoring
    # (for diagnostic comparison).  ``None`` means the run did not
    # record this evidence, which fails the protocol check.
    paper_read_only_at_end: bool | None = None
    # R8.1 Phase 1 protocol evidence: per-role LLM generation call
    # traces.  Each entry is a ``GenerationCallTrace.model_dump()``
    # dict.  The R8 acceptance checker verifies each LLM-calling role
    # has at least one trace with the protocol-mandated effective
    # temperature.  Empty list means the run did not evidence per-role
    # sampling config (which fails the ``per_role_sampling_config_evidenced``
    # criterion).
    generation_call_traces: list[dict[str, Any]] = Field(default_factory=list)
    # The configured per-role protocol is recorded alongside individual
    # GenerationCallTrace entries.  The maps make the intended envelope easy
    # to audit; traces remain the evidence of calls that actually occurred.
    temperature_by_role: dict[str, float] = Field(default_factory=dict)
    top_p_by_role: dict[str, float | None] = Field(default_factory=dict)
    top_k_by_role: dict[str, int | None] = Field(default_factory=dict)
    max_output_tokens_by_role: dict[str, int] = Field(default_factory=dict)
    # R8 Phase 2 protocol evidence: V3 research error.  When non-empty,
    # the V3 research subgraph failed and the run must NOT be accepted
    # by the R8 checker (the V3 evidence chain is broken).  Empty string
    # means V3 research succeeded (or V3 was not enabled).
    v3_error: str = ""
    # R8 Phase 2.5 protocol evidence: V3 node execution trace.  Each
    # entry records a node's execution (node name, timestamp, duration,
    # turn index, status, error) so the R8 checker can verify the
    # multi-node LangGraph topology actually executed.  Empty list means
    # V3 was not enabled or V3 research failed before producing a trace.
    v3_node_trace: list[dict[str, Any]] = Field(default_factory=list)


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
    checkpointer: Any | None = None,
    resume: bool = False,
    checkpoint_backend: str = "",
) -> AgenticRunResult:
    """Run Code2Paper through the agentic graph and persist a decision summary."""

    from code2paper.llm.generation_trace import reset_run_generation_traces

    reset_run_generation_traces()
    state = initial_state if isinstance(initial_state, AgenticRunState) else AgenticRunState.model_validate(initial_state)
    baseline_summary: AgenticRunSummary | None = None
    graph_config: dict[str, Any] | None = None
    if checkpointer is not None:
        state, graph_config = _prepare_checkpoint_execution(
            state,
            graph_app=graph_app,
            resume=resume,
            checkpoint_backend=checkpoint_backend or type(checkpointer).__name__,
        )
    app = graph_app
    active_registry: Mapping[str, Code2PaperStageTool] | None = None
    if app is None:
        active_registry = tool_registry or build_legacy_stage_tool_registry()
        provider = decision_provider or _default_decision_provider(state)
        verifier = semantic_verifier or _default_semantic_verifier(state)
        if _is_v3_research_enabled():
            app = _build_v3_graph_for_state(
                state,
                active_registry,
                decision_provider=provider,
                semantic_verifier=verifier,
                checkpointer=checkpointer,
                # Reuse the legacy checkpointer for the V3 research
                # subgraph.  The V3 thread_id (derived from
                # checkpoint_thread_id_v3) is namespaced differently
                # from the legacy thread_id (checkpoint_thread_id), so
                # V3 research checkpoints do not collide with legacy
                # pipeline checkpoints in the same SQLite database.
                v3_checkpointer=checkpointer,
            )
        else:
            app = build_code2paper_graph(
                active_registry,
                decision_provider=provider,
                semantic_verifier=verifier,
                checkpointer=checkpointer,
            )
    if checkpointer is not None and resume:
        checkpoint_state = app.get_state(graph_config).values
        state, metadata = validate_resume_state(checkpoint_state)
        state = state.model_copy(update={"checkpoint_metadata": metadata.model_dump(mode="json")})
        final_payload = _invoke_graph(app, None, config=graph_config)
    else:
        final_payload = _invoke_graph(app, state.model_dump(mode="json"), config=graph_config)
    # Load the baseline summary AFTER validate_resume_state so we use
    # the checkpoint's method_root (which points to the original run's
    # output directory), not the CLI's --out-root which may differ when
    # the caller directs the resume to a separate directory.
    if resume:
        baseline_path = artifact_dir(state.method_root, "10_run") / "agentic_run_summary.json"
        if baseline_path.exists():
            try:
                baseline_summary = load_agentic_run_summary(baseline_path)
            except (OSError, ValueError):
                baseline_summary = None
    # Extract V3 tool_call_trace_refs before validating as AgenticRunState
    # (AgenticRunState uses extra="forbid" and drops V3-specific channels).
    tool_call_trace_refs: list[str] = list(final_payload.pop("tool_call_trace_refs", []) or [])
    # Extract V3 error before validating as AgenticRunState.  When V3
    # research fails, the V3GraphWrapper surfaces the error in the
    # payload's ``v3_error`` field so the R8 acceptance checker can
    # fail the run instead of silently downgrading.
    v3_error: str = str(final_payload.pop("v3_error", "") or "")
    # Extract V3 node execution trace (Phase 2.5) before validating as
    # AgenticRunState (extra="forbid" would drop it).
    v3_node_trace: list[dict[str, Any]] = list(
        final_payload.pop("v3_node_trace", []) or []
    )
    if baseline_summary is not None:
        if not tool_call_trace_refs:
            tool_call_trace_refs = list(baseline_summary.tool_call_trace_refs)
        if not v3_error:
            v3_error = baseline_summary.v3_error
        if not v3_node_trace:
            v3_node_trace = list(baseline_summary.v3_node_trace)
    final_state = AgenticRunState.model_validate(final_payload)
    final_state = _persist_freshness_report(final_state)
    final_state = _reconcile_publication_quality_with_final_validation(final_state)
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
    trust_tool_manifest_path = artifact_dir(final_state.method_root, "10_run") / "agentic_trust_tool_manifest.json"
    write_trust_tool_manifest(trust_tool_manifest_path)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_trust_tool_manifest": str(trust_tool_manifest_path)}}
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
    summary = build_agentic_run_summary(final_state, tool_call_trace_refs=tool_call_trace_refs, v3_error=v3_error, v3_node_trace=v3_node_trace)
    resume_model_call_delta = len(summary.generation_call_traces) if resume else None
    summary = _merge_resume_summary_evidence(summary, baseline_summary)
    summary_path = artifact_dir(final_state.method_root, "10_run") / "agentic_run_summary.json"
    write_agentic_run_summary(summary_path, summary)
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "agentic_run_summary": str(summary_path)}}
    )
    run_manifest_path = artifact_dir(final_state.method_root, "10_run") / "run_manifest.json"
    write_agentic_run_manifest(
        run_manifest_path,
        final_state,
        summary_path=summary_path,
        resume_model_call_delta=resume_model_call_delta,
    )
    final_state = final_state.model_copy(
        update={"artifacts": {**final_state.artifacts, "run_manifest": str(run_manifest_path)}}
    )
    summary = build_agentic_run_summary(final_state, tool_call_trace_refs=tool_call_trace_refs, v3_error=v3_error, v3_node_trace=v3_node_trace)
    summary = _merge_resume_summary_evidence(summary, baseline_summary)
    write_agentic_run_summary(summary_path, summary)
    # R8.1: optionally emit an R8 acceptance report alongside the run
    # summary.  Enabled via ``CODE2PAPER_R8_ACCEPTANCE=1`` so default
    # runs are not affected.  The report is written next to the run
    # summary so ``check_r8_acceptance_from_run_dir`` can scan the
    # same directory.
    if os.environ.get("CODE2PAPER_R8_ACCEPTANCE", "").strip().lower() in {"1", "true", "yes", "on"}:
        r8_report_path = artifact_dir(final_state.method_root, "10_run") / "r8_acceptance_report.json"
        try:
            r8_report = _build_r8_acceptance_report(final_state, summary, tool_call_trace_refs)
            write_r8_acceptance_report(r8_report_path, r8_report)
            final_state = final_state.model_copy(
                update={"artifacts": {**final_state.artifacts, "r8_acceptance_report": str(r8_report_path)}}
            )
            write_agentic_run_manifest(
                run_manifest_path,
                final_state,
                summary_path=summary_path,
                acceptance_report_path=r8_report_path,
                resume_model_call_delta=resume_model_call_delta,
            )
        except Exception:
            # R8 acceptance report generation must never block a run.
            pass
    return AgenticRunResult(state=final_state, summary=summary, summary_path=summary_path)


def _merge_resume_summary_evidence(
    summary: AgenticRunSummary,
    baseline: AgenticRunSummary | None,
) -> AgenticRunSummary:
    """Carry immutable first-run evidence into a no-call checkpoint resume."""

    if baseline is None:
        return summary
    return summary.model_copy(update={
        "generation_call_traces": list(baseline.generation_call_traces),
        "temperature_by_role": dict(baseline.temperature_by_role),
        "top_p_by_role": dict(baseline.top_p_by_role),
        "top_k_by_role": dict(baseline.top_k_by_role),
        "max_output_tokens_by_role": dict(baseline.max_output_tokens_by_role),
        # Preserve the true first-run digest across repeated resumes.  The
        # summary file is overwritten in place after each resume, so using
        # only baseline.final_state_digest would make a third invocation
        # compare against the second resume rather than the original run.
        "resumed_from_final_state_digest": (
            baseline.resumed_from_final_state_digest
            or baseline.final_state_digest
        ),
        "v3_error": baseline.v3_error,
        "v3_node_trace": list(baseline.v3_node_trace),
    })


def _reconcile_publication_quality_with_final_validation(
    state: AgenticRunState,
) -> AgenticRunState:
    """Upgrade pending Writer quality only from the final reverse validator."""

    quality_value = state.artifacts.get("publication_quality_report_v1", "")
    validation_value = state.artifacts.get("text_evidence_validation", "")
    ledger_value = state.artifacts.get("final_text_authorship_ledger_v1", "")
    if not quality_value or not validation_value or not ledger_value:
        return state
    quality_path = Path(quality_value)
    validation_path = Path(validation_value)
    ledger_path = Path(ledger_value)
    if not all(path.is_file() for path in (quality_path, validation_path, ledger_path)):
        return state
    try:
        from code2paper.agentic.final_text_authorship import FinalTextAuthorshipLedgerV1
        from code2paper.agentic.publication_quality import PublicationQualityIssueV1, PublicationQualityReportV1
        from code2paper.agentic.trust_contracts import TextEvidenceValidationReport

        quality = PublicationQualityReportV1.model_validate_json(quality_path.read_text(encoding="utf-8"))
        validation = TextEvidenceValidationReport.model_validate_json(validation_path.read_text(encoding="utf-8"))
        ledger = FinalTextAuthorshipLedgerV1.model_validate_json(ledger_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    checked = validation.checked_factual_claims
    supported = validation.supported_claims + validation.caveated_claims
    unsupported = validation.unsupported_claims + validation.unverified_claims
    digest_bound = validation.input_text_digest == ledger.final_text_digest
    validation_passed = validation.status == "passed" and unsupported == 0 and digest_bound
    safety_payload = quality.safety.model_dump(mode="json")
    safety_payload.update({
        "unsupported_positive_claims": unsupported,
        "support_precision": 1.0 if checked == 0 else round(supported / checked, 6),
        "source_integrity": bool(quality.safety.source_integrity and digest_bound),
        "final_text_validation_status": "passed" if validation_passed else "failed",
    })
    safety_payload["hard_gate_passed"] = bool(
        safety_payload["authorship_gate_passed"]
        and safety_payload["binding_gate_passed"]
        and safety_payload["source_integrity"]
        and unsupported == 0
        and validation_passed
    )
    issues = [
        item for item in quality.issues
        if item.code not in {"final_text_validation_pending", "final_text_validation_failed"}
    ]
    if not validation_passed:
        issues.append(PublicationQualityIssueV1(
            issue_id="safety-final-text-validation",
            axis="epistemic_safety",
            scope="document",
            code="final_text_validation_failed",
            message=(
                f"Final reverse validation status={validation.status}, unsupported={validation.unsupported_claims}, "
                f"unverified={validation.unverified_claims}, digest_bound={digest_bound}."
            ),
        ))
    final_gate = bool(
        safety_payload["hard_gate_passed"]
        and quality.plan_gate_passed
        and quality.utility.utility_gate_passed
    )
    payload = quality.model_dump(mode="json")
    payload.update({
        "status": "blocked" if not safety_payload["hard_gate_passed"] else (
            "publication_ready" if final_gate else "incomplete"
        ),
        "final_integrity_gate_passed": final_gate,
        "safety": safety_payload,
        "issues": [item.model_dump(mode="json") for item in issues],
        "content_digest": "",
    })
    reconciled = PublicationQualityReportV1.model_validate(payload)
    temporary = quality_path.with_suffix(quality_path.suffix + ".tmp")
    temporary.write_text(reconciled.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(quality_path)
    _reconcile_publication_writer_result_with_quality(
        state,
        quality=reconciled,
    )
    return state


def _reconcile_publication_writer_result_with_quality(
    state: AgenticRunState,
    *,
    quality: Any,
) -> None:
    """Keep the Writer result status aligned with the final quality gate.

    The Writer persists its result before the runner performs the final
    evidence reconciliation.  Without this hand-off, a run can carry a
    ``publication_writer_result_v1`` marked ``incomplete`` beside a quality
    report marked ``blocked`` (or ``publication_ready``), which makes a stale
    candidate appear resumable.  Only the typed terminal status is updated;
    section text and generation provenance remain untouched.
    """

    result_value = state.artifacts.get("publication_writer_result_v1", "")
    if not result_value:
        return
    result_path = Path(result_value)
    if not result_path.is_file():
        return
    try:
        from code2paper.agentic.publication_method_writer import PublicationWriterRunResultV1

        result = PublicationWriterRunResultV1.model_validate_json(
            result_path.read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return
    status = result.status
    blocked_reason = result.blocked_reason
    failures = list(result.binding_failures)
    candidate_complete = bool(result.candidate_complete)
    candidate_completion_status = result.candidate_completion_status
    candidate_blocking_reasons = list(result.candidate_blocking_reasons)
    verified_complete = bool(result.verified_complete)
    verified_blocking_reasons = list(result.verified_blocking_reasons)
    candidate_generated = bool(result.candidate_available) or result.candidate_generation_status == "generated"
    # Q0: derive the independent candidate/verified validation states from the
    # persisted final reverse-gate artifact when the runner knows it.
    validation_status = ""
    validation_value = state.artifacts.get("text_evidence_validation", "")
    if validation_value and Path(validation_value).is_file():
        try:
            validation_status = str(json.loads(Path(validation_value).read_text(encoding="utf-8")).get("status") or "")
        except (OSError, json.JSONDecodeError):
            validation_status = ""
    candidate_validation_status = (
        "not_run" if not validation_status else
        "passed" if validation_status == "passed" else "warnings"
    )
    verified_validation_status = (
        "not_run" if not validation_status else
        "passed" if validation_status == "passed" else "incomplete"
    )
    publication_ready = bool(
        quality.status == "publication_ready" and quality.final_integrity_gate_passed
    )
    if not candidate_generated:
        candidate_complete = False
        candidate_completion_status = "blocked"
        if "candidate_not_generated" not in candidate_blocking_reasons:
            candidate_blocking_reasons.append("candidate_not_generated")
    if not publication_ready:
        verified_complete = False
        if "publication_quality_gate_open" not in verified_blocking_reasons:
            verified_blocking_reasons.append("publication_quality_gate_open")
    if quality.status == "blocked":
        # Q0: a blocked quality gate is a warning/quality label; it never
        # flips a generated candidate run to blocked.  Only a true generation
        # failure (no durable candidate) keeps the run blocked.
        if not candidate_generated:
            status = "blocked"
            if not blocked_reason:
                blocked_reason = "publication_final_reverse_validation_failed"
            if "publication_final_reverse_validation_failed" not in failures:
                failures.append("publication_final_reverse_validation_failed")
        elif status == "success":
            # A blocked quality gate with a durable candidate is a warning
            # run: demote success, never erase the candidate.
            status = "incomplete"
    elif quality.status == "publication_ready":
        status = "success" if candidate_generated else status
        blocked_reason = ""
    elif status == "success":
        status = "incomplete"
    if (
        status == result.status
        and blocked_reason == result.blocked_reason
        and tuple(failures) == result.binding_failures
        and publication_ready == result.publication_ready
        and candidate_complete == result.candidate_complete
        and candidate_completion_status == result.candidate_completion_status
        and tuple(candidate_blocking_reasons) == result.candidate_blocking_reasons
        and verified_complete == result.verified_complete
        and tuple(verified_blocking_reasons) == result.verified_blocking_reasons
    ):
        return
    result_payload = result.model_dump(mode="json")
    result_payload.update({
        "status": status,
        "blocked_reason": blocked_reason,
        "binding_failures": failures,
        "publication_ready": publication_ready,
        "candidate_validation_status": candidate_validation_status,
        "verified_validation_status": verified_validation_status,
        "candidate_warnings_by_severity": dict(quality.candidate_warnings_by_severity or {}),
        "candidate_completion_status": candidate_completion_status,
        "candidate_complete": candidate_complete,
        "candidate_blocking_reasons": candidate_blocking_reasons,
        "verified_complete": verified_complete,
        "verified_blocking_reasons": verified_blocking_reasons,
        "content_digest": "",
    })
    updated = PublicationWriterRunResultV1.model_validate(result_payload)
    temporary = result_path.with_suffix(result_path.suffix + ".tmp")
    temporary.write_text(updated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(result_path)


def build_agentic_run_summary(
    state: AgenticRunState,
    *,
    tool_call_trace_refs: Iterable[str] | None = None,
    v3_error: str = "",
    v3_node_trace: Iterable[dict[str, Any]] | None = None,
) -> AgenticRunSummary:
    artifacts = {
        name: AgenticArtifactRecord(path=str(path), hash=hash_file(path))
        for name, path in sorted(state.artifacts.items())
        if str(path).strip()
    }
    status = "blocked" if state.blocked_reason else "success"
    tool_refs = list(tool_call_trace_refs or [])
    trace_digest = compute_trace_digest(state.decisions, tool_refs)
    final_state_digest = _compute_final_state_digest(state)
    environment = _collect_run_environment()
    temperature = _collect_run_temperature()
    source_authority_policy = _collect_source_authority_policy(state)
    paper_read_only_at_end = _collect_paper_read_only_at_end()
    sampling_config = _collect_role_sampling_config(state)
    from code2paper.llm.generation_trace import get_run_generation_traces

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
        run_id=state.run_id,
        project_id=state.project_id,
        trace_digest=trace_digest,
        tool_call_trace_refs=tool_refs,
        final_state_digest=final_state_digest,
        environment=environment,
        temperature=temperature,
        source_authority_policy=source_authority_policy,
        paper_read_only_at_end=paper_read_only_at_end,
        generation_call_traces=get_run_generation_traces(),
        temperature_by_role=sampling_config["temperature_by_role"],
        top_p_by_role=sampling_config["top_p_by_role"],
        top_k_by_role=sampling_config["top_k_by_role"],
        max_output_tokens_by_role=sampling_config["max_output_tokens_by_role"],
        v3_error=v3_error,
        v3_node_trace=list(v3_node_trace or []),
    )


def write_agentic_run_summary(path: str | Path, summary: AgenticRunSummary) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    return output


def write_agentic_run_manifest(
    path: str | Path,
    state: AgenticRunState,
    *,
    summary_path: str | Path | None = None,
    acceptance_report_path: str | Path | None = None,
    resume_model_call_delta: int | None = None,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    source_commit, source_dirty = _source_git_metadata()
    manifest = build_run_manifest(
        project_root=state.project_root,
        author_input_path=state.effective_author_markers_path or state.intent_path or None,
        llm=load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model),
        phase_inputs=_agentic_phase_inputs(state),
        output_paths={
            name: artifact_path
            for name, artifact_path in state.artifacts.items()
            if artifact_path and name != "run_manifest"
        },
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
        source_commit=source_commit,
        source_dirty=source_dirty,
        evidence_profile_digest=hash_file(
            state.artifacts.get("evidence_profile_match", "")
            or state.artifacts.get("generic_research_compilation_manifest", "")
        ),
        run_summary_digest=hash_file(summary_path) if summary_path else "",
        acceptance_report_digest=(
            hash_file(acceptance_report_path) if acceptance_report_path else ""
        ),
        checkpoint_digest=hash_file(
            str(state.checkpoint_metadata.get("checkpoint_path") or "")
        ),
        terminal_state="BLOCKED" if state.blocked_reason else "COMPLETED",
        resume_model_call_delta=resume_model_call_delta,
        execution_profile_digest=hash_file(
            state.artifacts.get("execution_profile", "")
            or state.artifacts.get("execution_profile_v1", "")
        ),
    )
    write_run_manifest(output, manifest)
    return output


def _source_git_metadata() -> tuple[str, bool | None]:
    """Return the Code2Paper source revision without consulting target code."""

    source_root = Path(__file__).resolve().parents[3]
    try:
        commit = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(source_root), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return "", None
    return commit, bool(status.strip())


def load_agentic_run_summary(path: str | Path) -> AgenticRunSummary:
    return AgenticRunSummary.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _agentic_phase_inputs(state: AgenticRunState) -> dict[str, list[str]]:
    return {
        "input_resolution": _existing_values([str(state.project_root), state.author_markers_path, state.intent_path]),
        "intake": _existing_values(
            [
                str(state.project_root),
                state.artifacts.get("resolved_author_markers", ""),
                state.artifacts.get("intent_spec", ""),
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


def _invoke_graph(
    graph_app: Any,
    payload: dict[str, Any] | None,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if hasattr(graph_app, "invoke"):
        result = graph_app.invoke(payload, config=config) if config else graph_app.invoke(payload)
    else:
        result = graph_app(payload)
    if not isinstance(result, dict):
        raise TypeError("agentic graph must return a state dict")
    return result


def _prepare_checkpoint_execution(
    state: AgenticRunState,
    *,
    graph_app: Any | None,
    resume: bool,
    checkpoint_backend: str,
) -> tuple[AgenticRunState, dict[str, Any]]:
    run_id = state.run_id.strip() or str(uuid.uuid4())
    frozen_path = state.repo_snapshot_ref or state.artifacts.get("repo_snapshot", "")
    if resume and not frozen_path:
        candidate = artifact_dir(state.method_root, "01_input") / "repo_snapshot.json"
        frozen_path = str(candidate) if candidate.exists() else ""
    repo_snapshot_id = (
        load_repo_snapshot(frozen_path).snapshot_id
        if frozen_path and Path(frozen_path).exists()
        else build_repo_snapshot(state.project_root).snapshot_id
    )
    thread_id = checkpoint_thread_id(run_id=run_id, repo_snapshot_id=repo_snapshot_id)
    metadata = CheckpointMetadataV2(
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        thread_id=thread_id,
        checkpoint_backend=checkpoint_backend,
        checkpoint_path=str(state.checkpoint_metadata.get("checkpoint_path") or ""),
        resumed=resume,
    )
    if resume and graph_app is not None and not hasattr(graph_app, "get_state"):
        raise TypeError("resume requires a compiled LangGraph app with get_state")
    return state.model_copy(
        update={"run_id": run_id, "checkpoint_metadata": metadata.model_dump(mode="json")}
    ), checkpoint_config(thread_id)


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


def _is_v3_research_enabled() -> bool:
    """Return True when ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set.

    When True, the runner builds a V3 graph wrapper (V3 research subgraph
    with ``GemmaSupervisorBackend`` + legacy pipeline) instead of the
    default ``build_code2paper_graph``.  This is the R8 wiring entry
    point.
    """

    raw = os.environ.get("CODE2PAPER_AGENTIC_RESEARCH_V3", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _build_v3_graph_for_state(
    state: AgenticRunState,
    tool_registry: Mapping[str, Code2PaperStageTool],
    *,
    decision_provider: DecisionProvider | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    checkpointer: Any = None,
    v3_checkpointer: Any = None,
    v3_thread_id: str | None = None,
) -> Any:
    """Build a V3 graph wrapper for the given run state.

    Constructs a ``ResearchGraphRuntime`` with ``GemmaSupervisorBackend``
    from the state's project_root + intent_path, then wraps the legacy
    pipeline so V3 research decisions are merged into the final state.

    ``v3_checkpointer`` and ``v3_thread_id`` are passed to the V3
    research subgraph so checkpoint/resume works for the V3 research
    phase.  When ``v3_thread_id`` is None, a stable V3 thread ID is
    derived from the run_id and repo_snapshot_id via
    ``checkpoint_thread_id_v3`` so the V3 research phase has a
    consistent checkpoint identity across invocations.
    """

    # Local import to avoid circular imports and keep the V3 wiring
    # isolated when the feature flag is off.
    from code2paper.agentic.state_v3 import checkpoint_thread_id_v3
    from code2paper.agentic.v3_runtime import build_code2paper_v3_graph, build_v3_research_runtime

    run_id = state.run_id.strip() or str(uuid.uuid4())
    llm_config = load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)
    execution_profile = _load_execution_profile_for_state(state)
    # Once the wrapper has persisted a route artifact, the checkpointed state
    # is authoritative.  Reading changed process environment variables during
    # resume would otherwise silently move a run between shadow/opt-in/canary.
    route_persisted = bool(
        state.artifacts.get("execution_route")
        or state.artifacts.get("execution_route_v1")
    )
    execution_opt_in = (
        bool(state.execution_opt_in)
        if route_persisted
        else bool(state.execution_opt_in) or _env_flag("CODE2PAPER_EXECUTION_OPT_IN")
    )
    execution_rollback = (
        bool(state.execution_rollback)
        if route_persisted
        else bool(state.execution_rollback) or _env_flag("CODE2PAPER_EXECUTION_ROLLBACK")
    )
    execution_canary_key = (
        (state.execution_canary_key or run_id)
        if route_persisted
        else state.execution_canary_key
        or os.environ.get("CODE2PAPER_EXECUTION_CANARY_KEY", run_id)
    )
    v3_runtime = build_v3_research_runtime(
        project_root=state.project_root,
        intent_path=state.intent_path or state.effective_author_markers_path,
        run_id=run_id,
        llm_config=llm_config,
        execution_profile=execution_profile,
        execution_opt_in=execution_opt_in,
        execution_canary_key=execution_canary_key,
        execution_rollback=execution_rollback,
    )
    # Derive a stable V3 thread ID when one is not provided.  This
    # ensures the V3 research subgraph has a consistent checkpoint
    # identity across invocations (and across resume).
    effective_v3_thread_id = v3_thread_id
    if effective_v3_thread_id is None:
        try:
            effective_v3_thread_id = checkpoint_thread_id_v3(
                run_id=run_id,
                repo_snapshot_id=v3_runtime.repo_snapshot.snapshot_id,
            )
        except ValueError:
            # When repo_snapshot_id is empty (should not happen in
            # production), fall back to None and skip V3 checkpointing.
            effective_v3_thread_id = None
    return build_code2paper_v3_graph(
        tool_registry,
        v3_runtime=v3_runtime,
        decision_provider=decision_provider,
        semantic_verifier=semantic_verifier,
        checkpointer=checkpointer,
        v3_checkpointer=v3_checkpointer,
        v3_thread_id=effective_v3_thread_id,
    )


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_execution_profile_for_state(state: AgenticRunState):
    """Load an explicitly requested D6 profile; absent means legacy behavior."""

    source = (
        state.artifacts.get("execution_profile")
        or state.artifacts.get("execution_profile_v1")
        or os.environ.get("CODE2PAPER_EXECUTION_PROFILE", "")
    )
    if source:
        return load_execution_profile(source)
    return execution_profile_from_env()


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


# ---------------------------------------------------------------------------
# R8.1 protocol helpers
# ---------------------------------------------------------------------------


#: Environment variables recorded in the run summary so the R8
#: acceptance checker can verify protocol provenance (cache off, single TP=2
#: instance, serial execution, and role-specific sampling overrides).
_R8_ENV_VARS: tuple[str, ...] = (
    "CODE2PAPER_LLM_CACHE",
    "CODE2PAPER_TP_SIZE",
    "CODE2PAPER_NUM_GPUS",
    "CODE2PAPER_R8_EXPECT_TP_SIZE",
    "CODE2PAPER_R8_EXPECT_NUM_GPUS",
    "CODE2PAPER_PARALLEL_PROJECTS",
    "CODE2PAPER_LLM_TEMPERATURE",
    "CODE2PAPER_PAPER_READ_ONLY_AT_END",
    "CODE2PAPER_LLM_TEMPERATURE_INTENT_COMPILER",
    "CODE2PAPER_LLM_TEMPERATURE_CODE_INTAKE",
    "CODE2PAPER_LLM_TEMPERATURE_CODE_ANALYZER",
    "CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR",
    "CODE2PAPER_LLM_TEMPERATURE_AUTHORING_PLANNER",
    "CODE2PAPER_LLM_TEMPERATURE_METHOD_WRITER",
    "CODE2PAPER_LLM_TEMPERATURE_LOCAL_REWRITE",
    "CODE2PAPER_LLM_TEMPERATURE_SEMANTIC_VERIFIER",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_INTENT_COMPILER",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_INTAKE",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_CODE_ANALYZER",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_RESEARCH_SUPERVISOR",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_AUTHORING_PLANNER",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_METHOD_WRITER_EXTENDED",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_LOCAL_REWRITE",
    "CODE2PAPER_LLM_MAX_OUTPUT_TOKENS_SEMANTIC_VERIFIER",
)


def _compute_final_state_digest(state: AgenticRunState) -> str:
    """Compute a content-addressed digest over the final run state.

    The digest covers the run id, decisions, loop counters, budgets,
    blocked reason, and artifact map.  Two runs that reach the same
    final state produce the same digest, which is what the
    ``checkpoint_resume_consistent`` R8 criterion compares.
    """

    import hashlib

    payload = {
        "run_id": state.run_id,
        "project_id": state.project_id,
        "decisions": [d.model_dump(mode="json") for d in state.decisions],
        "loop_counters": dict(state.loop_counters),
        "budgets": state.budgets,
        "blocked_reason": state.blocked_reason,
        "next_node": state.next_node,
        "artifacts": dict(sorted(state.artifacts.items())),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _collect_run_environment() -> dict[str, str]:
    """Collect R8-protocol-relevant environment variables."""

    return {name: os.environ.get(name, "") for name in _R8_ENV_VARS if os.environ.get(name, "")}


def _collect_run_temperature() -> float | None:
    """Read the run's LLM temperature from the environment.

    Returns ``None`` when not set so the R8 acceptance checker can
    distinguish "not recorded" from "explicitly zero".
    """

    raw = os.environ.get("CODE2PAPER_LLM_TEMPERATURE", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _collect_role_sampling_config(state: AgenticRunState) -> dict[str, dict[str, Any]]:
    """Resolve the formal per-role envelope once for the run summary.

    This is configuration provenance, not a claim that every optional role
    executed.  Actual calls are independently recorded in
    ``generation_call_traces`` and validated by R8.
    """

    try:
        base = load_llm_config_from_env(
            provider=state.llm_provider,
            model=state.llm_model,
        )
    except (TypeError, ValueError):
        return {
            "temperature_by_role": {},
            "top_p_by_role": {},
            "top_k_by_role": {},
            "max_output_tokens_by_role": {},
        }

    resolved = {
        role: apply_role_config(base, role)
        for role in LLM_CALLING_ROLES
    }
    extended_writer = apply_role_config(
        base, METHOD_WRITER, extended_writer_budget=True
    )
    return {
        "temperature_by_role": {
            role: config.temperature for role, config in resolved.items()
        },
        "top_p_by_role": {
            role: config.top_p for role, config in resolved.items()
        },
        "top_k_by_role": {
            role: config.top_k for role, config in resolved.items()
        },
        "max_output_tokens_by_role": {
            **{
                role: config.max_output_tokens
                for role, config in resolved.items()
            },
            "method_writer_extended": extended_writer.max_output_tokens,
            "method_cumulative_budget": writer_cumulative_budget(),
        },
    }


def _collect_paper_read_only_at_end() -> bool | None:
    """Read evidence that the paper was read only AFTER Method authoring.

    Returns ``True`` when ``CODE2PAPER_PAPER_READ_ONLY_AT_END`` is set to
    a truthy value (``"1"`` / ``"true"`` / ``"yes"``), ``False`` when set
    to a falsy value (``"0"`` / ``"false"`` / ``"no"``), and ``None`` when
    unset so the R8 acceptance checker fails the protocol check for
    missing evidence.
    """

    raw = os.environ.get("CODE2PAPER_PAPER_READ_ONLY_AT_END", "").strip().lower()
    if not raw:
        return None
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return None


def _collect_source_authority_policy(state: AgenticRunState) -> dict[str, Any]:
    """Load the source authority policy from the run's artifacts.

    Returns an empty dict when no policy artifact is available so the
    R8 acceptance checker's paper-promotion scan is a no-op.
    """

    for key in ("source_authority_policy", "agentic_source_authority_policy"):
        path = state.artifacts.get(key, "")
        if not path or not Path(path).exists():
            continue
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            # The policy file may wrap the mapping under a key like
            # ``policy`` or ``levels``; unwrap when present.
            for inner_key in ("policy", "levels", "source_authority_policy"):
                inner = payload.get(inner_key)
                if isinstance(inner, dict):
                    return inner
            return payload
    return {}


def _build_r8_acceptance_report(
    state: AgenticRunState,
    summary: AgenticRunSummary,
    tool_call_trace_refs: Iterable[str],
):
    """Build an R8 acceptance report from the run's final state.

    Loads the run's ``AtomicClaimSetV3``, ``ObligationCoverageReportV2``,
    ``TextEvidenceValidationReport``, and Method text from the artifact
    paths in ``state.artifacts`` so the acceptance checker can verify
    all eight R8.2 criteria.

    When the ``obligation_coverage_v2`` artifact is not present (the
    legacy pipeline does not always emit it), the coverage report is
    built on-the-fly from the intent graph + claim set + code facts
    using ``build_obligation_coverage_v2``.  This ensures the
    ``code_mainline_in_method`` and ``must_cover_terminal`` criteria
    can be evaluated even for runs that predate the V3 coverage
    artifact.
    """

    from code2paper.agentic.evidence_compiler_v3 import (
        load_atomic_claims_v3_or_v2,
        load_code_facts_v1,
    )
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
    from code2paper.agentic.obligation_fact_alignment import (
        ObligationCoverageReportV2,
        build_obligation_coverage_v2,
    )
    from code2paper.agentic.trust_contracts import TextEvidenceValidationReport

    claim_set = None
    claims_path = (
        state.artifacts.get("atomic_claims_v3", "")
        or state.artifacts.get("atomic_claims_v2", "")
        or state.artifacts.get("claims", "")
    )
    if claims_path and Path(claims_path).exists():
        try:
            claim_set = load_atomic_claims_v3_or_v2(claims_path)
        except Exception:
            claim_set = None

    coverage_report = None
    coverage_path = state.artifacts.get("obligation_coverage_v2", "")
    if coverage_path and Path(coverage_path).exists():
        try:
            coverage_report = ObligationCoverageReportV2.model_validate_json(
                Path(coverage_path).read_text(encoding="utf-8")
            )
        except Exception:
            coverage_report = None

    # Fallback: build the coverage report on-the-fly from the intent
    # graph + claim set + code facts.  This is required because the
    # legacy pipeline does not always emit an ``obligation_coverage_v2``
    # artifact, but the R8 acceptance checker needs it for the
    # ``code_mainline_in_method`` and ``must_cover_terminal`` criteria.
    if coverage_report is None:
        # Prefer the V3 wrapper's post-proposal graph.  The older legacy
        # intent artifact predates Gemma's rich typed targets and would
        # silently replay predicate-only coverage in an R8 report.
        intent_path = (
            state.artifacts.get("intent_obligation_graph_v2", "")
            or state.artifacts.get("intent_obligation_graph", "")
        )
        if intent_path and Path(intent_path).exists() and claim_set is not None:
            try:
                intent_graph = IntentObligationGraphV2.model_validate_json(
                    Path(intent_path).read_text(encoding="utf-8")
                )
                fact_set = None
                facts_path = state.artifacts.get("code_facts_v1", "")
                if facts_path and Path(facts_path).exists():
                    try:
                        fact_set = load_code_facts_v1(facts_path)
                    except Exception:
                        fact_set = None
                coverage_report = build_obligation_coverage_v2(
                    intent_graph,
                    fact_set=fact_set,
                    claim_set=claim_set,
                )
            except Exception:
                coverage_report = None

    validation_report = None
    validation_path = state.artifacts.get("text_evidence_validation", "")
    if validation_path and Path(validation_path).exists():
        try:
            validation_report = TextEvidenceValidationReport.model_validate_json(
                Path(validation_path).read_text(encoding="utf-8")
            )
        except Exception:
            validation_report = None

    method_text = ""
    for key in ("text_clean_md", "text_md", "text_clean_tex", "text_tex"):
        path = state.artifacts.get(key, "")
        if path and Path(path).exists():
            try:
                method_text = Path(path).read_text(encoding="utf-8")
            except OSError:
                pass
            break

    intent_target_proposal_report: dict[str, Any] = {}
    proposal_path = state.artifacts.get("intent_target_proposal_report_v1", "")
    if proposal_path and Path(proposal_path).exists():
        try:
            proposal_payload = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
            if isinstance(proposal_payload, dict):
                intent_target_proposal_report = proposal_payload
        except (OSError, json.JSONDecodeError):
            pass

    return check_r8_acceptance(
        run_id=state.run_id or summary.run_id,
        project_id=state.project_id,
        decisions=state.decisions,
        tool_call_trace_refs=tool_call_trace_refs,
        recorded_trace_digest=summary.trace_digest,
        coverage_report=coverage_report,
        claim_set=claim_set,
        validation_report=validation_report,
        method_text=method_text,
        original_final_state_digest=(
            summary.resumed_from_final_state_digest or summary.final_state_digest
        ),
        resumed_final_state_digest=(
            summary.final_state_digest
            if summary.resumed_from_final_state_digest
            else ""
        ),
        protocol_settings=R8ProtocolSettings(
            single_tp2_instance=(
                "CODE2PAPER_R8_EXPECT_TP_SIZE" not in summary.environment
                and "CODE2PAPER_R8_EXPECT_NUM_GPUS" not in summary.environment
            ),
            expected_tp_size=(
                int(summary.environment["CODE2PAPER_R8_EXPECT_TP_SIZE"])
                if summary.environment.get("CODE2PAPER_R8_EXPECT_TP_SIZE", "").isdigit()
                else None
            ),
            expected_num_gpus=(
                int(summary.environment["CODE2PAPER_R8_EXPECT_NUM_GPUS"])
                if summary.environment.get("CODE2PAPER_R8_EXPECT_NUM_GPUS", "").isdigit()
                else None
            ),
        ),
        run_environment=summary.environment,
        run_temperature=summary.temperature,
        source_authority_policy=summary.source_authority_policy,
        paper_read_only_at_end=summary.paper_read_only_at_end,
        generation_call_traces=summary.generation_call_traces,
        temperature_by_role=summary.temperature_by_role,
        top_p_by_role=summary.top_p_by_role,
        top_k_by_role=summary.top_k_by_role,
        max_output_tokens_by_role=summary.max_output_tokens_by_role,
        intent_target_proposal_report=intent_target_proposal_report,
        v3_error=summary.v3_error,
    )
