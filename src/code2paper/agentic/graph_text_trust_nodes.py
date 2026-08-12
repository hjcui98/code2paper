from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    load_authoring_projection,
    write_authoring_projection,
)
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.authoring_plan_v3 import (
    build_authoring_plan_v3,
    write_authoring_plan_v3,
)
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.evidence_compiler_v3 import (
    load_atomic_claims_v3,
    load_evidence_packets_v3,
)
from code2paper.agentic.equation_claims import load_equation_claims
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.final_text_claims import extract_final_text_claims, load_final_text_claims, write_final_text_claims
from code2paper.agentic.final_text_authorship import (
    FinalTextAuthorshipLedgerV1,
    rewrite_final_text_authorship_ledger,
)
from code2paper.agentic.text_evidence_validator import (
    SemanticVerifier,
    load_text_evidence_validation,
    validate_text_evidence,
    write_text_evidence_validation,
)
from code2paper.agentic.text_trace_builder import build_final_text_trace, write_final_text_trace
from code2paper.agentic.text_repair_supervisor import derive_repair_issues
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
from code2paper.agentic.quality_state_v2 import compute_quality_state, select_best_state
from code2paper.agentic.research_models import PacketRepairRequestV1, QualityStateV2
from code2paper.agentic.rewrite_agent import (
    LocalRewriteAgent,
    RepairTransitionV1,
)
from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.agentic.trust_contracts import TextClaimEvidenceVerdict
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import load_llm_config_from_env


def final_text_claim_extractor_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
    if state.blocked_reason:
        return state.model_copy(update={"next_node": "blocked"}).model_dump(mode="json")
    projection_path = state.artifacts.get("authoring_projection", "")
    text_path = _final_text_path(state)
    if not projection_path or not Path(projection_path).exists() or text_path is None:
        return state.model_copy(
            update={"blocked_reason": "final_text_or_authoring_projection_missing", "next_node": "blocked"}
        ).model_dump(mode="json")
    projection = load_authoring_projection(projection_path)
    final_claims = extract_final_text_claims(text_path.read_text(encoding="utf-8"), projection)
    output = artifact_dir(state.method_root, "07_validation") / "agentic_final_text_claims.json"
    write_final_text_claims(output, final_claims)
    artifacts = {**state.artifacts, "final_text_claims": str(output), "final_text_candidate": str(text_path)}
    return state.model_copy(
        update={
            "artifacts": artifacts,
            "blocked_reason": "" if final_claims.deterministic_completeness_passed else "final_text_claim_extraction_incomplete",
            "decisions": [
                *state.decisions,
                AgentDecision(
                    node="final_text_claim_extractor",
                    decision="extracted" if final_claims.deterministic_completeness_passed else "incomplete",
                    rationale=(
                        f"Extracted {len(final_claims.atomic_claims)} factual atomic claims from exact final text "
                        f"digest {final_claims.input_text_digest}."
                    ),
                    artifact_keys=["final_text_claims", "final_text_candidate", "authoring_projection"],
                ),
            ],
        }
    ).model_dump(mode="json")


def text_evidence_validator_node(
    raw_state: dict[str, Any],
    *,
    semantic_verifier: SemanticVerifier | None = None,
) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
    if state.blocked_reason:
        return state.model_copy(update={"next_node": "blocked"}).model_dump(mode="json")
    if state.artifacts.get("repo_snapshot") and not state.artifacts.get("evidence_snapshot_v2"):
        return state.model_copy(
            update={"blocked_reason": "formal_evidence_v2_required_for_text_validation", "next_node": "blocked"}
        ).model_dump(mode="json")
    try:
        final_claims = load_final_text_claims(state.artifacts["final_text_claims"])
        projection = load_authoring_projection(state.artifacts["authoring_projection"])
        raw_evidence = RawEvidencePack.model_validate_json(Path(state.artifacts["evidence_raw"]).read_text(encoding="utf-8"))
        evidence_snapshot_v2 = (
            load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
            if state.artifacts.get("evidence_snapshot_v2")
            else None
        )
        evidence_packets_v3 = (
            load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
            if state.artifacts.get("evidence_packets_v3")
            else None
        )
    except (KeyError, OSError, ValueError):
        return state.model_copy(
            update={"blocked_reason": "text_evidence_validator_inputs_missing", "next_node": "blocked"}
        ).model_dump(mode="json")
    verifier_calls_used = int(state.loop_counters.get("semantic_verifier") or 0)
    verifier_calls_remaining = max(0, state.max_semantic_verifier_calls - verifier_calls_used)
    provider = str(getattr(state.llm_provider, "value", state.llm_provider) or "").strip().lower()
    verifier_required = state.max_semantic_verifier_calls > 0 and (
        semantic_verifier is not None or provider not in {"", "none"}
    )
    # AtomicClaimV3 has already passed exact-span, predicate-compatibility,
    # canonical-dedup, and relation validation. Requiring one model call per
    # final sentence would turn a run-level budget into a sentence-count cap and
    # block fuller Methods. V3 text remains subject to deterministic reverse
    # matching against its direct/relation evidence and wording boundaries.
    v3_compiled = bool(state.artifacts.get("atomic_claims_v3") and evidence_packets_v3)
    report = validate_text_evidence(
        final_claims=final_claims,
        projection=projection,
        raw_evidence=raw_evidence,
        evidence_snapshot_v2=evidence_snapshot_v2,
        evidence_packets_v3=evidence_packets_v3,
        semantic_verifier=None if v3_compiled else semantic_verifier,
        max_semantic_verifier_calls=0 if v3_compiled else verifier_calls_remaining,
        require_semantic_verifier=False if v3_compiled else verifier_required,
    )
    report = _enforce_planned_claim_coverage(
        state=state,
        report=report,
        projection=projection,
    )
    output = artifact_dir(state.method_root, "07_validation") / "agentic_text_evidence_validation.json"
    write_text_evidence_validation(output, report)
    artifacts = {**state.artifacts, "text_evidence_validation": str(output)}
    traces = list(getattr(semantic_verifier, "traces", []) or []) if semantic_verifier is not None else []
    if traces:
        trace_output = artifact_dir(state.method_root, "07_validation") / "agentic_semantic_verifier_call_trace.json"
        _atomic_write_text(
            trace_output,
            json.dumps({"calls": traces}, ensure_ascii=False, indent=2) + "\n",
        )
        artifacts["semantic_verifier_call_trace"] = str(trace_output)
    counters = dict(state.loop_counters)
    counters["semantic_verifier"] = verifier_calls_used + report.semantic_verifier_calls
    return state.model_copy(
        update={
            "artifacts": artifacts,
            "loop_counters": counters,
            "decisions": [
                *state.decisions,
                AgentDecision(
                    node="text_evidence_validator",
                    decision=report.status,
                    rationale=(
                        f"supported={report.supported_claims}, caveated={report.caveated_claims}, "
                        f"unsupported={report.unsupported_claims}, unverified={report.unverified_claims}."
                    ),
                    artifact_keys=["text_evidence_validation", "final_text_claims", "authoring_projection", "evidence_raw"],
                ),
            ],
        }
    ).model_dump(mode="json")


def text_trace_builder_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
    if state.blocked_reason:
        return state.model_copy(update={"next_node": "blocked"}).model_dump(mode="json")
    try:
        final_claims = load_final_text_claims(state.artifacts["final_text_claims"])
        projection = load_authoring_projection(state.artifacts["authoring_projection"])
        validation = load_text_evidence_validation(state.artifacts["text_evidence_validation"])
    except (KeyError, OSError, ValueError):
        return state.model_copy(
            update={"blocked_reason": "text_trace_builder_inputs_missing", "next_node": "blocked"}
        ).model_dump(mode="json")
    output = artifact_dir(state.method_root, "07_validation") / "agentic_final_text_claim_trace.json"
    trace = build_final_text_trace(
        final_claims=final_claims,
        validation=validation,
        projection=projection,
        validator_report_ref=state.artifacts["text_evidence_validation"],
        projection_ref=state.artifacts["authoring_projection"],
    )
    write_final_text_trace(output, trace)
    artifacts = {**state.artifacts, "final_text_trace": str(output)}
    quality_artifacts, restored_best = _retain_best_text_state(
        state=state,
        validation=validation,
    )
    artifacts.update(quality_artifacts)
    if restored_best:
        return state.model_copy(
            update={
                "artifacts": artifacts,
                "next_node": "final_text_claim_extractor",
                "blocked_reason": "",
                "decisions": [
                    *state.decisions,
                    AgentDecision(
                        node="text_trace_builder",
                        decision="best_state_restored",
                        rationale="The repaired candidate regressed a protected quality dimension; restored the retained best text artifact.",
                        artifact_keys=["quality_state_current_v2", "quality_state_best_v2", "best_final_text_candidate"],
                    ),
                ],
            }
        ).model_dump(mode="json")
    next_node, blocked_reason = _next_after_text_gate(state, validation)
    updated = state.model_copy(
        update={
            "artifacts": artifacts,
            "next_node": next_node,
            "blocked_reason": blocked_reason,
            "decisions": [
                *state.decisions,
                AgentDecision(
                    node="text_trace_builder",
                    decision="passed" if trace.hard_gate_passed else next_node,
                    rationale="Final text trace passed." if trace.hard_gate_passed else "; ".join(trace.failures + validation.recommended_actions),
                    artifact_keys=["final_text_trace", "text_evidence_validation", "final_text_claims", "authoring_projection"],
                ),
            ],
        }
    )
    return updated.model_dump(mode="json")


def _next_after_text_gate(
    state: AgenticRunState,
    validation,
) -> tuple[str, str]:
    """Route only when at least one failed claim retains its own budget.

    ``max_authoring_revision_rounds`` is an envelope per failed atomic claim,
    not a run-global sentence-count cap.  The aggregate counter remains for
    telemetry, while ``local_text_repair:<claim-id>`` counters carry authority.
    """

    if validation.status == "passed":
        return "validation", ""
    actions = validation.recommended_actions
    eligible = _eligible_repair_claim_ids(state, validation)
    if any("packet_binding_repair" in action for action in actions):
        if eligible:
            return "local_text_repair", ""
        return "blocked", "text_claim_packet_binding_repair_budget_exhausted"
    needs_evidence = any("analysis" in action or "direct_evidence" in action for action in actions)
    if needs_evidence:
        if eligible:
            return "local_text_repair", ""
        return "blocked", "text_claim_direct_evidence_missing_budget_exhausted"
    if eligible:
        return "local_text_repair", ""
    return "blocked", "text_claim_authoring_revision_budget_exhausted"


def _repair_claim_id(verdict) -> str:
    return str(verdict.atomic_claim_id or "").strip()


def _eligible_repair_claim_ids(state: AgenticRunState, validation) -> list[str]:
    if state.max_authoring_revision_rounds <= 0:
        return []
    claim_ids = sorted({
        _repair_claim_id(verdict)
        for verdict in validation.verdicts
        if verdict.deterministic_failures and _repair_claim_id(verdict)
    })
    return [
        claim_id for claim_id in claim_ids
        if int(state.loop_counters.get(f"local_text_repair:{claim_id}") or 0)
        < state.max_authoring_revision_rounds
    ]


def _select_round_robin_claim(
    state: AgenticRunState,
    validation,
) -> tuple[str, int]:
    eligible = _eligible_repair_claim_ids(state, validation)
    if not eligible:
        return "", int(state.loop_counters.get("local_text_repair_cursor") or 0)
    cursor = int(state.loop_counters.get("local_text_repair_cursor") or 0)
    return eligible[cursor % len(eligible)], cursor + 1


def local_text_repair_node(
    raw_state: dict[str, Any],
    *,
    rewrite_agent: LocalRewriteAgent | None = None,
) -> dict[str, Any]:
    """Delegate lexical mutation to the owning Rewrite Agent.

    The harness derives typed issues, validates exact response spans, and
    applies the returned bytes verbatim.  It never authors replacement prose.
    """

    state = AgenticRunState.model_validate(raw_state)
    try:
        validation = load_text_evidence_validation(state.artifacts["text_evidence_validation"])
        final_claims = load_final_text_claims(state.artifacts["final_text_claims"])
        projection = load_authoring_projection(state.artifacts["authoring_projection"])
        text_path = _final_text_path(state)
        if text_path is None:
            raise OSError("final text missing")
    except (KeyError, OSError, ValueError):
        return state.model_copy(
            update={"blocked_reason": "local_text_repair_inputs_missing", "next_node": "blocked"}
        ).model_dump(mode="json")

    selected_claim_id, next_cursor = _select_round_robin_claim(state, validation)
    if not selected_claim_id:
        return state.model_copy(update={
            "blocked_reason": "text_claim_authoring_revision_budget_exhausted",
            "next_node": "blocked",
        }).model_dump(mode="json")
    attempt = int(state.loop_counters.get(f"local_text_repair:{selected_claim_id}") or 0) + 1
    sentence_ids = {claim.atomic_claim_id: claim.unit_id for claim in final_claims.atomic_claims}
    issues = [
        issue.model_copy(update={"attempt": attempt})
        for issue in derive_repair_issues(validation, sentence_id_by_claim=sentence_ids)
        if issue.atomic_claim_id == selected_claim_id
    ]
    projected_by_id = {claim.claim_id: claim for claim in projection.projected_claims}
    packet_requests: list[PacketRepairRequestV1] = []
    plan_payload: dict[str, Any] = {}
    plan_path = state.artifacts.get("authoring_plan_v3", "")
    if plan_path and Path(plan_path).exists():
        try:
            plan_payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            plan_payload = {}

    packets = None
    if state.artifacts.get("evidence_packets_v3"):
        try:
            packets = load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
        except (OSError, ValueError):
            packets = None

    rewrite_issues = []
    for issue in issues:
        verdict = next(
            (item for item in validation.verdicts if item.atomic_claim_id == issue.atomic_claim_id),
            None,
        )
        if verdict is None:
            continue
        if issue.allowed_repair_scope in {"packet_relation", "code_search"}:
            packet_requests.append(_packet_repair_request(issue, verdict, packets))
            continue
        rewrite_issues.append(issue)

    repair_dir = artifact_dir(state.method_root, "07_validation")
    requests_path = repair_dir / "agentic_packet_repair_requests_v1.json"
    _atomic_write_text(
        requests_path,
        json.dumps({"attempt": attempt, "requests": [item.model_dump(mode="json") for item in packet_requests]}, ensure_ascii=False, indent=2) + "\n",
    )
    issues_path = repair_dir / "agentic_text_repair_issues_v1.json"
    _atomic_write_text(
        issues_path,
        json.dumps({"attempt": attempt, "issues": [item.model_dump(mode="json") for item in issues]}, ensure_ascii=False, indent=2) + "\n",
    )
    artifacts = {
        **state.artifacts,
        "text_repair_issues_v1": str(issues_path),
        "packet_repair_requests_v1": str(requests_path),
    }
    counters = {
        **state.loop_counters,
        "local_text_repair": int(state.loop_counters.get("local_text_repair") or 0) + 1,
        f"local_text_repair:{selected_claim_id}": attempt,
        "local_text_repair_cursor": next_cursor,
    }

    if rewrite_issues:
        incumbent_text = text_path.read_text(encoding="utf-8")
        agent = rewrite_agent or LocalRewriteAgent(config=load_llm_config_from_env(
            provider=state.llm_provider,
            model=state.llm_model,
        ))
        rewrite_result = agent.rewrite(
            incumbent_text,
            issues=rewrite_issues,
            section_context={
                "authoring_plan": plan_payload,
                "authorized_claims": [
                    projected.model_dump(mode="json")
                    for projected in projected_by_id.values()
                    if any(projected.claim_id in issue.matched_claim_ids for issue in rewrite_issues)
                ],
                "hard_rule": "Return exact replacement text; the harness will not edit it.",
            },
        )
        result_path = repair_dir / f"agentic_local_rewrite_result_attempt_{attempt}.json"
        _atomic_write_text(result_path, rewrite_result.model_dump_json(indent=2) + "\n")
        transition = RepairTransitionV1(
            transition_id=f"repair:local_rewrite:{attempt}",
            strategy=(
                "claim_decomposition"
                if any(issue.allowed_repair_scope == "claim_decomposition" for issue in rewrite_issues)
                else "local_rewrite"
            ),
            owner="rewrite",
            attempt=attempt,
            issue_ids=tuple(issue.atomic_claim_id or issue.sentence_id for issue in rewrite_issues),
            incumbent_digest=rewrite_result.incumbent_digest,
            candidate_digest=rewrite_result.candidate_digest,
            status=rewrite_result.status,
            reason=rewrite_result.blocked_reason or ";".join(rewrite_result.patch_failures),
            artifact_refs=(str(result_path),),
        )
        transition_path = repair_dir / f"agentic_repair_transition_attempt_{attempt}.json"
        _atomic_write_text(transition_path, transition.model_dump_json(indent=2) + "\n")
        artifacts.update({
            "local_rewrite_result_v1": str(result_path),
            "repair_transition_v1": str(transition_path),
        })
        if rewrite_result.status == "applied":
            gate_failures = _rewrite_candidate_gate_failures(
                state=state,
                candidate_text=rewrite_result.candidate_text,
                incumbent_validation=validation,
            )
            if gate_failures:
                rewrite_result = rewrite_result.model_copy(update={
                    "status": "rejected",
                    "candidate_text": incumbent_text,
                    "blocked_reason": "rewrite_candidate_hard_gate_failed",
                    "patch_failures": tuple(gate_failures),
                })
                _atomic_write_text(result_path, rewrite_result.model_dump_json(indent=2) + "\n")
                transition = transition.model_copy(update={
                    "status": "rejected",
                    "reason": ";".join(gate_failures),
                })
                _atomic_write_text(transition_path, transition.model_dump_json(indent=2) + "\n")
        rewritten_ledger = None
        ledger_path_value = state.artifacts.get("final_text_authorship_ledger_v1", "")
        if rewrite_result.status == "applied" and ledger_path_value:
            try:
                incumbent_ledger = FinalTextAuthorshipLedgerV1.model_validate_json(
                    Path(ledger_path_value).read_text(encoding="utf-8")
                )
                rewritten_ledger = rewrite_final_text_authorship_ledger(
                    incumbent_text=incumbent_text,
                    candidate_text=rewrite_result.candidate_text,
                    incumbent_ledger=incumbent_ledger,
                    patches=list(rewrite_result.output.patches if rewrite_result.output else ()),
                    response_ref=rewrite_result.response_ref,
                    generation_trace_id=str(rewrite_result.generation_trace.get("call_id") or ""),
                )
            except (OSError, ValueError) as exc:
                ledger_failure = f"authorship:{exc}"
                rewrite_result = rewrite_result.model_copy(update={
                    "status": "rejected",
                    "candidate_text": incumbent_text,
                    "blocked_reason": "rewrite_authorship_hard_gate_failed",
                    "patch_failures": (*rewrite_result.patch_failures, ledger_failure),
                })
                _atomic_write_text(result_path, rewrite_result.model_dump_json(indent=2) + "\n")
                transition = transition.model_copy(update={
                    "status": "rejected",
                    "reason": ledger_failure,
                })
                _atomic_write_text(transition_path, transition.model_dump_json(indent=2) + "\n")
        if rewrite_result.status != "applied":
            return state.model_copy(update={
                "artifacts": artifacts,
                "loop_counters": counters,
                "next_node": "blocked",
                "blocked_reason": rewrite_result.blocked_reason or "local_rewrite_not_applied",
                "decisions": [*state.decisions, AgentDecision(
                    node="local_text_repair",
                    decision="rewrite_candidate_rejected",
                    rationale="The owning Rewrite Agent did not produce a valid exact-span patch; the incumbent text was preserved.",
                    artifact_keys=["text_repair_issues_v1", "local_rewrite_result_v1", "repair_transition_v1"],
                )],
            }).model_dump(mode="json")
        _atomic_write_text(text_path, rewrite_result.candidate_text)
        if rewritten_ledger is not None:
            _atomic_write_text(
                Path(ledger_path_value),
                rewritten_ledger.model_dump_json(indent=2) + "\n",
            )
        return state.model_copy(
            update={
                "artifacts": artifacts,
                "loop_counters": counters,
                "next_node": "final_text_claim_extractor",
                "blocked_reason": "",
                "decisions": [*state.decisions, AgentDecision(
                    node="local_text_repair",
                    decision="local_rewrite_applied",
                    rationale=(
                        f"Applied {len(rewrite_result.output.patches) if rewrite_result.output else 0} "
                        "verbatim exact-span patches from the owning Rewrite Agent."
                    ),
                    artifact_keys=["text_repair_issues_v1", "local_rewrite_result_v1", "repair_transition_v1", "final_text_candidate"],
                )],
            }
        ).model_dump(mode="json")
    if packet_requests:
        return state.model_copy(update={
            "artifacts": artifacts,
            "loop_counters": counters,
            "next_node": "packet_binding_repair",
            "blocked_reason": "",
        }).model_dump(mode="json")
    return state.model_copy(update={
        "artifacts": artifacts,
        "loop_counters": counters,
        "next_node": "blocked",
        "blocked_reason": "no_safe_local_text_repair_available",
    }).model_dump(mode="json")


def _rewrite_candidate_gate_failures(
    *,
    state: AgenticRunState,
    candidate_text: str,
    incumbent_validation,
) -> list[str]:
    """Run deterministic atomic text gates before mutating the draft."""

    try:
        projection = load_authoring_projection(state.artifacts["authoring_projection"])
        raw_evidence = RawEvidencePack.model_validate_json(
            Path(state.artifacts["evidence_raw"]).read_text(encoding="utf-8")
        )
        evidence_snapshot_v2 = (
            load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
            if state.artifacts.get("evidence_snapshot_v2") else None
        )
        evidence_packets_v3 = (
            load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
            if state.artifacts.get("evidence_packets_v3") else None
        )
    except (KeyError, OSError, ValueError):
        return ["candidate_gate_inputs_missing"]
    claims = extract_final_text_claims(candidate_text, projection)
    if not claims.deterministic_completeness_passed:
        return ["candidate_claim_extraction_incomplete"]
    report = validate_text_evidence(
        final_claims=claims,
        projection=projection,
        raw_evidence=raw_evidence,
        evidence_snapshot_v2=evidence_snapshot_v2,
        evidence_packets_v3=evidence_packets_v3,
        semantic_verifier=None,
        max_semantic_verifier_calls=0,
        require_semantic_verifier=False,
    )
    report = _enforce_planned_claim_coverage(state=state, report=report, projection=projection)
    failures: list[str] = []
    incumbent_failed = incumbent_validation.unsupported_claims + incumbent_validation.unverified_claims
    candidate_failed = report.unsupported_claims + report.unverified_claims
    if candidate_failed >= incumbent_failed:
        failures.append("candidate_does_not_reduce_atomic_hard_gate_failures")
    if report.supported_claims < incumbent_validation.supported_claims:
        failures.append("candidate_loses_supported_claim")
    incumbent_claims = load_final_text_claims(state.artifacts["final_text_claims"])
    incumbent_duplicates = _duplicate_atomic_claim_count(incumbent_claims)
    candidate_duplicates = _duplicate_atomic_claim_count(claims)
    if candidate_duplicates > incumbent_duplicates:
        failures.append("candidate_adds_duplicate_claim")
    if any(
        failure in {"required_qualifier_missing", "allowed_wording_boundary_exceeded"}
        for verdict in report.verdicts
        for failure in verdict.deterministic_failures
    ):
        failures.append("candidate_has_qualifier_or_wording_failure")
    return list(dict.fromkeys(failures))


def _duplicate_atomic_claim_count(final_claims) -> int:
    counts: dict[str, int] = {}
    for claim in final_claims.atomic_claims:
        normalized = " ".join(claim.normalized_text.split())
        if normalized:
            counts[normalized] = counts.get(normalized, 0) + 1
    return sum(count - 1 for count in counts.values() if count > 1)


def packet_binding_repair_node(
    raw_state: dict[str, Any],
    *,
    repair_owner=None,
) -> dict[str, Any]:
    """Invoke the owning repository loop for the exact rejected packet."""

    state = AgenticRunState.model_validate(raw_state)
    request_path = state.artifacts.get("packet_repair_requests_v1", "")
    if not request_path or not Path(request_path).is_file():
        return _blocked_packet_repair(state, "packet_repair_requests_missing")
    try:
        request_payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
        requests = tuple(
            PacketRepairRequestV1.model_validate(item)
            for item in request_payload.get("requests", [])
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return _blocked_packet_repair(state, "packet_repair_requests_invalid")
    if not requests:
        return _blocked_packet_repair(state, "packet_repair_requests_empty")
    if repair_owner is None:
        return _blocked_packet_repair(
            state,
            "packet_scoped_repair_requires_research_owner",
        )
    try:
        result = repair_owner(state, requests)
    except Exception as exc:  # noqa: BLE001 - owner failure preserves incumbent
        return _blocked_packet_repair(
            state,
            f"packet_repair_owner_error:{exc.__class__.__name__}",
        )
    result_payload = (
        result.model_dump(mode="json")
        if hasattr(result, "model_dump")
        else dict(result or {})
    )
    status = str(result_payload.get("status") or "blocked")
    reason = str(result_payload.get("reason") or "")
    artifacts = {**state.artifacts, **dict(result_payload.get("artifact_paths") or {})}
    repair_dir = artifact_dir(state.method_root, "07_validation")
    result_path = repair_dir / "agentic_packet_repair_owner_result_v1.json"
    _atomic_write_text(
        result_path,
        json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n",
    )
    artifacts["packet_repair_owner_result_v1"] = str(result_path)
    incumbent_chain_digest = _json_content_digest(state.artifacts.get("atomic_claims_v3", ""))
    candidate_chain_digest = _json_content_digest(artifacts.get("atomic_claims_v3", ""))
    transition = RepairTransitionV1(
        transition_id=f"repair:packet_relation:{int(state.loop_counters.get('local_text_repair') or 0)}",
        strategy="packet_relation",
        owner="repository_tools",
        attempt=int(state.loop_counters.get("local_text_repair") or 0),
        issue_ids=tuple(request.claim_id for request in requests),
        incumbent_digest=incumbent_chain_digest,
        candidate_digest=candidate_chain_digest,
        status=(status if status in {"applied", "no_progress", "blocked"} else "rejected"),
        reason=reason,
        artifact_refs=(str(result_path),),
    )
    transition_path = repair_dir / (
        f"agentic_packet_repair_transition_attempt_{transition.attempt}.json"
    )
    _atomic_write_text(transition_path, transition.model_dump_json(indent=2) + "\n")
    artifacts["repair_transition_v1"] = str(transition_path)
    if status == "applied":
        refreshed = _refresh_authoring_projection_after_packet_repair(state, artifacts)
        if refreshed:
            artifacts["authoring_projection"] = refreshed
            updated = state.model_copy(update={
                "artifacts": artifacts,
                "next_node": "final_text_claim_extractor",
                "blocked_reason": "",
                "decisions": [*state.decisions, AgentDecision(
                    node="packet_binding_repair",
                    decision="scoped_repository_repair_applied",
                    rationale="The owning repository loop produced a changed validated packet/fact/claim chain; the original atomic text gate will rerun.",
                    evidence_ids=list(result_payload.get("tool_call_trace_refs") or []),
                    artifact_keys=["packet_repair_owner_result_v1", "evidence_packets_v3", "code_facts_v1", "atomic_claims_v3", "authoring_projection"],
                )],
            })
            return updated.model_dump(mode="json")
        reason = "packet_repair_projection_refresh_failed"
    return _blocked_packet_repair(
        state.model_copy(update={"artifacts": artifacts}),
        reason or f"packet_repair_owner_{status}",
    )


def _json_content_digest(path_value: str) -> str:
    if path_value and Path(path_value).is_file():
        try:
            payload = json.loads(Path(path_value).read_text(encoding="utf-8"))
            digest = str(payload.get("content_digest") or "")
            if digest.startswith("sha256:"):
                return digest
        except (OSError, json.JSONDecodeError):
            pass
    return "sha256:" + hashlib.sha256(b"").hexdigest()


def _refresh_authoring_projection_after_packet_repair(
    state: AgenticRunState,
    artifacts: dict[str, str],
) -> str:
    try:
        method_evidence = MethodEvidence.model_validate(
            _read_json(method_output(state.method_root, "evidence"))
        )
        claim_map = ClaimEvidenceMap.model_validate(
            _read_json(method_output(state.method_root, "claims"))
        )
        verification_path = artifacts.get("claim_verification", "")
        if not verification_path:
            verification_path = str(
                artifact_dir(state.method_root, "04_evidence")
                / "agentic_claim_verification.json"
            )
        verification = ClaimVerificationReport.model_validate_json(
            Path(verification_path).read_text(encoding="utf-8")
        )
        projection = build_authoring_projection(
            method_evidence=method_evidence,
            claim_map=claim_map,
            verification=verification,
            raw_evidence=(
                RawEvidencePack.model_validate_json(
                    Path(artifacts["evidence_raw"]).read_text(encoding="utf-8")
                )
                if artifacts.get("evidence_raw") else None
            ),
            evidence_snapshot_v2=(
                load_evidence_snapshot_v2(artifacts["evidence_snapshot_v2"])
                if artifacts.get("evidence_snapshot_v2") else None
            ),
            atomic_claims_v3=load_atomic_claims_v3(artifacts["atomic_claims_v3"]),
            evidence_packets_v3=load_evidence_packets_v3(artifacts["evidence_packets_v3"]),
            equation_claims_v1=(
                load_equation_claims(artifacts["equation_claims_v1"])
                if artifacts.get("equation_claims_v1") else None
            ),
        )
        output = Path(artifacts.get("authoring_projection") or (
            artifact_dir(state.method_root, "06_authoring")
            / "agentic_authoring_input_projection.json"
        ))
        write_authoring_projection(output, projection)
        return str(output)
    except (KeyError, OSError, ValueError):
        return ""

def _unaffected_items_equal(old_items, fresh_items, identity_field: str, affected_ids: set[str]) -> bool:
    old = {getattr(item, identity_field): item.model_dump(mode="json") for item in old_items if getattr(item, identity_field) not in affected_ids}
    fresh = {getattr(item, identity_field): item.model_dump(mode="json") for item in fresh_items if getattr(item, identity_field) not in affected_ids}
    return old == fresh


def _blocked_packet_repair(state: AgenticRunState, reason: str) -> dict[str, Any]:
    artifacts = dict(state.artifacts)
    if artifacts.get("repair_transition_v1") and Path(artifacts["repair_transition_v1"]).is_file():
        return state.model_copy(update={
            "artifacts": artifacts,
            "next_node": "blocked",
            "blocked_reason": reason,
            "decisions": [*state.decisions, AgentDecision(
                node="packet_binding_repair",
                decision="scoped_repair_blocked",
                rationale=f"{reason}; the typed owner transition was retained.",
                artifact_keys=["packet_repair_requests_v1", "repair_transition_v1"],
            )],
        }).model_dump(mode="json")
    request_ref = str(artifacts.get("packet_repair_requests_v1") or "")
    attempt = int(state.loop_counters.get("local_text_repair") or 0)
    text_path = _final_text_path(state)
    incumbent = text_path.read_text(encoding="utf-8") if text_path is not None else ""
    incumbent_digest = "sha256:" + hashlib.sha256(incumbent.encode("utf-8")).hexdigest()
    transition = RepairTransitionV1(
        transition_id=f"repair:packet_relation:{attempt}",
        strategy="packet_relation",
        owner="repository_tools",
        attempt=attempt,
        issue_ids=(),
        incumbent_digest=incumbent_digest,
        candidate_digest=incumbent_digest,
        status="blocked",
        reason=reason,
        artifact_refs=(request_ref,) if request_ref else (),
    )
    transition_path = (
        artifact_dir(state.method_root, "07_validation")
        / f"agentic_packet_repair_transition_attempt_{attempt}.json"
    )
    _atomic_write_text(transition_path, transition.model_dump_json(indent=2) + "\n")
    artifacts["repair_transition_v1"] = str(transition_path)
    return state.model_copy(update={
        "artifacts": artifacts,
        "next_node": "blocked",
        "blocked_reason": reason,
        "decisions": [*state.decisions, AgentDecision(
            node="packet_binding_repair",
            decision="scoped_repair_blocked",
            rationale=(
                f"{reason}; packet repair did not expand into intake, analysis, "
                "or whole-Method authoring."
            ),
            artifact_keys=["packet_repair_requests_v1"],
        )],
    }).model_dump(mode="json")


def _packet_repair_request(issue, verdict, packets) -> PacketRepairRequestV1:
    span_ids = tuple(dict.fromkeys([*verdict.direct_evidence_ids, *verdict.relation_evidence_ids]))
    packet_id = ""
    if packets is not None:
        for packet in packets.packets:
            known = {span.span_id for span in packet.spans}
            if known.intersection(span_ids):
                packet_id = packet.packet_id
                break
    return PacketRepairRequestV1(
        claim_id=issue.atomic_claim_id,
        source_claim_ids=tuple(verdict.matched_projection_claim_ids),
        packet_id=packet_id,
        failure_type=issue.failure_type,
        offending_span_ids=span_ids,
        missing_relation_type=issue.missing_fact_or_relation,
        requested_scope=issue.allowed_repair_scope,
        attempt=issue.attempt,
    )


def _enforce_planned_claim_coverage(*, state, report, projection):
    """Fail the reverse gate when the writer silently omits a planned claim."""

    plan_path = state.artifacts.get("authoring_plan_v3", "")
    if not plan_path or not Path(plan_path).exists():
        return report
    try:
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return report
    planned = {
        str(claim_id)
        for section in plan.get("sections", [])
        for claim_id in section.get("claim_ids", [])
        if str(claim_id)
    }
    covered = {
        claim_id
        for verdict in report.verdicts
        if verdict.status in {"supported", "caveated"}
        for claim_id in verdict.matched_projection_claim_ids
    }
    missing = sorted(planned - covered)
    if not missing:
        return report
    projected_by_id = {item.claim_id: item for item in projection.projected_claims}
    missing_verdicts = []
    for claim_id in missing:
        projected = projected_by_id.get(claim_id)
        missing_verdicts.append(TextClaimEvidenceVerdict(
            atomic_claim_id=f"MISSING:{claim_id}",
            status="unverified",
            matched_projection_claim_ids=[claim_id],
            direct_evidence_ids=(list(projected.direct_evidence_ids) if projected else []),
            relation_evidence_ids=(list(projected.relation_evidence_ids) if projected else []),
            supported_fragment=(projected.supported_fragment if projected else ""),
            required_qualifiers=(list(projected.required_qualifiers) if projected else []),
            deterministic_failures=["planned_claim_missing_from_final_text"],
            rationale="The V3 authoring plan authorized this claim, but no supported final-text claim covers it.",
            repair_action=f"insert_planned_claim_locally:{claim_id}",
        ))
    return report.model_copy(update={
        "status": "failed",
        "checked_factual_claims": report.checked_factual_claims + len(missing),
        "unverified_claims": report.unverified_claims + len(missing),
        "verdicts": [*report.verdicts, *missing_verdicts],
        "recommended_actions": [
            *report.recommended_actions,
            *[f"insert_planned_claim_locally:{claim_id}" for claim_id in missing],
        ],
    })


def _retain_best_text_state(*, state: AgenticRunState, validation) -> tuple[dict[str, str], bool]:
    text_path = _final_text_path(state)
    if text_path is None:
        return {}, False
    claim_set = None
    coverage = None
    try:
        if state.artifacts.get("atomic_claims_v3"):
            claim_set = load_atomic_claims_v3(state.artifacts["atomic_claims_v3"])
        if state.artifacts.get("obligation_coverage_v2"):
            coverage = ObligationCoverageReportV2.model_validate_json(
                Path(state.artifacts["obligation_coverage_v2"]).read_text(encoding="utf-8")
            )
    except (OSError, ValueError):
        # Quality retention remains useful for final-text safety even when an
        # optional research-plane metric is unavailable.
        claim_set = claim_set if claim_set is not None else None
        coverage = coverage if coverage is not None else None
    projection = load_authoring_projection(state.artifacts["authoring_projection"])
    repo_id = (claim_set.repo_snapshot_id if claim_set else projection.repo_snapshot_id) or "repo-unknown"
    tree_hash = (claim_set.project_tree_hash if claim_set else projection.project_tree_hash) or "tree-unknown"
    run_id = state.run_id.strip() or f"run-{tree_hash.removeprefix('sha256:')[:16]}"
    candidate = compute_quality_state(
        run_id=run_id,
        repo_snapshot_id=repo_id,
        project_tree_hash=tree_hash,
        coverage_report=coverage,
        claim_set=claim_set,
        validation_report=validation,
        model_calls=int(state.loop_counters.get("semantic_verifier") or 0),
        repeated_no_gain_calls=int(state.loop_counters.get("no_progress") or 0),
    )
    quality_dir = artifact_dir(state.method_root, "07_validation")
    current_path = quality_dir / "agentic_quality_state_current_v2.json"
    _atomic_write_text(current_path, candidate.model_dump_json(indent=2) + "\n")
    best_path = quality_dir / "agentic_quality_state_best_v2.json"
    best_text_path = quality_dir / "agentic_best_final_text_candidate.md"
    replaced = False
    restored = False
    if best_path.exists() and best_text_path.exists():
        incumbent = QualityStateV2.model_validate_json(best_path.read_text(encoding="utf-8"))
        best, replaced = select_best_state(candidate, incumbent)
        if replaced:
            _atomic_write_text(best_path, best.model_dump_json(indent=2) + "\n")
            _atomic_write_text(best_text_path, text_path.read_text(encoding="utf-8"))
        elif text_path.read_text(encoding="utf-8") != best_text_path.read_text(encoding="utf-8"):
            _atomic_write_text(text_path, best_text_path.read_text(encoding="utf-8"))
            restored = True
    else:
        _atomic_write_text(best_path, candidate.model_dump_json(indent=2) + "\n")
        _atomic_write_text(best_text_path, text_path.read_text(encoding="utf-8"))
    return {
        "quality_state_current_v2": str(current_path),
        "quality_state_best_v2": str(best_path),
        "best_final_text_candidate": str(best_text_path),
    }, restored


def _final_text_path(state: AgenticRunState) -> Path | None:
    for key in ("text_clean_md", "text_md"):
        candidate = state.artifacts.get(key, "")
        if candidate and Path(candidate).exists():
            return Path(candidate)
    for name in ("text_clean_md", "text_md"):
        candidate = method_output(state.method_root, name)
        if candidate.exists():
            return candidate
    return None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))
