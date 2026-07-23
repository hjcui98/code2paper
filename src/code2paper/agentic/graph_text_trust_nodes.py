from __future__ import annotations

from pathlib import Path
from typing import Any
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
    compile_evidence_v3,
    load_atomic_claims_v3,
    load_code_facts_v1,
    load_evidence_packets_v3,
    write_compiler_v3_artifacts,
)
from code2paper.agentic.equation_claims import (
    compile_equation_claims,
    write_equation_claims,
)
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.final_text_claims import extract_final_text_claims, load_final_text_claims, write_final_text_claims
from code2paper.agentic.text_evidence_validator import (
    SemanticVerifier,
    load_text_evidence_validation,
    validate_text_evidence,
    write_text_evidence_validation,
)
from code2paper.agentic.text_trace_builder import build_final_text_trace, write_final_text_trace
from code2paper.agentic.text_repair_supervisor import derive_repair_issues
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
from code2paper.agentic.obligation_fact_alignment import (
    bind_claims_to_obligations,
    build_obligation_coverage_v2,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.quality_state_v2 import compute_quality_state, select_best_state
from code2paper.agentic.research_models import PacketRepairRequestV1, QualityStateV2
from code2paper.agentic.repo_snapshot import load_repo_snapshot, snapshot_is_current
from code2paper.agentic.trust_contracts import TextClaimEvidenceVerdict
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, RawEvidencePack


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
        trace_output.write_text(json.dumps({"calls": traces}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
    next_node, blocked_reason = _next_after_text_gate(state, validation.status, validation.recommended_actions)
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


def _next_after_text_gate(state: AgenticRunState, status: str, actions: list[str]) -> tuple[str, str]:
    if status == "passed":
        return "validation", ""
    if any("packet_binding_repair" in action for action in actions):
        if int(state.loop_counters.get("local_text_repair") or 0) < state.max_authoring_revision_rounds:
            return "local_text_repair", ""
        return "blocked", "text_claim_packet_binding_repair_budget_exhausted"
    needs_evidence = any("analysis" in action or "direct_evidence" in action for action in actions)
    if needs_evidence:
        if int(state.loop_counters.get("local_text_repair") or 0) < state.max_authoring_revision_rounds:
            return "local_text_repair", ""
        return "blocked", "text_claim_direct_evidence_missing_budget_exhausted"
    if int(state.loop_counters.get("local_text_repair") or 0) < state.max_authoring_revision_rounds:
        return "local_text_repair", ""
    return "blocked", "text_claim_authoring_revision_budget_exhausted"


def local_text_repair_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    """Apply only sentence/claim-scoped safe repairs to the current Method text."""

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

    attempt = int(state.loop_counters.get("local_text_repair") or 0) + 1
    sentence_ids = {claim.atomic_claim_id: claim.unit_id for claim in final_claims.atomic_claims}
    issues = [issue.model_copy(update={"attempt": attempt}) for issue in derive_repair_issues(
        validation, sentence_id_by_claim=sentence_ids
    )]
    claim_by_id = {claim.atomic_claim_id: claim for claim in final_claims.atomic_claims}
    projected_by_id = {claim.claim_id: claim for claim in projection.projected_claims}
    packet_requests: list[PacketRepairRequestV1] = []
    replacements: dict[tuple[int, int], str] = {}
    insertions: list[tuple[str, str]] = []

    plan_path = state.artifacts.get("authoring_plan_v3", "")
    if plan_path and Path(plan_path).exists():
        try:
            plan_payload = json.loads(Path(plan_path).read_text(encoding="utf-8"))
            section_by_claim = {
                claim_id: str(section.get("heading") or "Method")
                for section in plan_payload.get("sections", [])
                for claim_id in section.get("claim_ids", [])
            }
            for action in validation.recommended_actions:
                prefix = "insert_planned_claim_locally:"
                if not action.startswith(prefix):
                    continue
                claim_id = action[len(prefix):]
                projected = projected_by_id.get(claim_id)
                if projected is not None:
                    fragment = projected.supported_fragment.strip()
                    missing = [
                        qualifier for qualifier in projected.required_qualifiers
                        if qualifier.lower() not in fragment.lower()
                    ]
                    if missing:
                        fragment = f"{fragment.rstrip('.')} under {'; '.join(missing)}."
                    insertions.append((section_by_claim.get(claim_id, "Method"), fragment))
        except (OSError, json.JSONDecodeError):
            insertions = []

    packets = None
    if state.artifacts.get("evidence_packets_v3"):
        try:
            packets = load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
        except (OSError, ValueError):
            packets = None

    verdict_by_id = {item.atomic_claim_id: item for item in validation.verdicts}
    for issue in issues:
        claim = claim_by_id.get(issue.atomic_claim_id)
        verdict = verdict_by_id.get(issue.atomic_claim_id)
        if claim is None or verdict is None:
            continue
        if issue.allowed_repair_scope in {"packet_relation", "code_search"}:
            packet_requests.append(_packet_repair_request(issue, verdict, packets))
            continue
        replacement = ""
        if issue.allowed_repair_scope == "wording_only" and issue.matched_claim_ids:
            matched_ids = set(issue.matched_claim_ids)
            supported_sibling_exists = any(
                sibling.atomic_claim_id != claim.atomic_claim_id
                and sibling.unit_id == claim.unit_id
                and (sibling_verdict := verdict_by_id.get(sibling.atomic_claim_id)) is not None
                and sibling_verdict.status in {"supported", "caveated"}
                and bool(matched_ids.intersection(sibling_verdict.matched_projection_claim_ids))
                for sibling in final_claims.atomic_claims
            )
            # Compound-sentence extraction can expose a redundant unsupported
            # sub-clause beside an already supported sub-clause for the same
            # projected claim. Replacing that small span with the whole
            # projected fragment duplicates the sentence on every repair
            # round. In this case exact deletion is the only monotonic local
            # repair: the supported sibling retains the claim and its trace.
            if not supported_sibling_exists:
                projected = projected_by_id.get(issue.matched_claim_ids[0])
                if projected is not None:
                    replacement = projected.supported_fragment.strip()
                    missing = [
                        qualifier for qualifier in projected.required_qualifiers
                        if qualifier.lower() not in replacement.lower()
                    ]
                    if missing:
                        replacement = f"{replacement.rstrip('.')} under {'; '.join(missing)}."
        # For unsupported formulae, missing evidence, or an unsafe decomposition,
        # deletion of the exact atomic fragment is the only deterministic local
        # action that cannot invent a new positive claim.
        replacements[(claim.char_start, claim.char_end)] = replacement

    repair_dir = artifact_dir(state.method_root, "07_validation")
    requests_path = repair_dir / "agentic_packet_repair_requests_v1.json"
    requests_path.write_text(
        json.dumps({"attempt": attempt, "requests": [item.model_dump(mode="json") for item in packet_requests]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    issues_path = repair_dir / "agentic_text_repair_issues_v1.json"
    issues_path.write_text(
        json.dumps({"attempt": attempt, "issues": [item.model_dump(mode="json") for item in issues]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifacts = {
        **state.artifacts,
        "text_repair_issues_v1": str(issues_path),
        "packet_repair_requests_v1": str(requests_path),
    }
    counters = {**state.loop_counters, "local_text_repair": attempt}

    if replacements or insertions:
        text = text_path.read_text(encoding="utf-8")
        for (start, end), replacement in sorted(replacements.items(), reverse=True):
            text = text[:start] + replacement + text[end:]
        for heading, fragment in insertions:
            text = _insert_into_markdown_section(text, heading, fragment)
        text_path.write_text(_clean_local_repair_text(text), encoding="utf-8")
        return state.model_copy(
            update={
                "artifacts": artifacts,
                "loop_counters": counters,
                "next_node": "final_text_claim_extractor",
                "blocked_reason": "",
                "decisions": [*state.decisions, AgentDecision(
                    node="local_text_repair",
                    decision="local_text_rewritten",
                    rationale=(
                        f"Applied {len(replacements)} exact-span repairs and "
                        f"{len(insertions)} authorized planned-claim insertions; unaffected Method text was not regenerated."
                    ),
                    artifact_keys=["text_repair_issues_v1", "packet_repair_requests_v1", "final_text_candidate"],
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


def packet_binding_repair_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    """Recompile only the requested packet dependency slice.

    The profile/generic compiler may inspect the frozen repository snapshot,
    but the repair is accepted only when every packet, fact and claim outside
    the requested dependency slice is byte-for-byte unchanged.  This provides
    a real success path without silently expanding into intake, analysis or a
    whole-Method rewrite.
    """

    state = AgenticRunState.model_validate(raw_state)
    request_path = state.artifacts.get("packet_repair_requests_v1", "")
    if not request_path or not Path(request_path).exists():
        return _blocked_packet_repair(state, "packet_repair_request_missing")
    try:
        request_payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
        requests = [PacketRepairRequestV1.model_validate(item) for item in request_payload.get("requests", [])]
    except (OSError, ValueError, json.JSONDecodeError):
        return _blocked_packet_repair(state, "packet_scoped_repair_inputs_invalid")
    if not requests or any(not item.packet_id for item in requests):
        return _blocked_packet_repair(state, "packet_scoped_repair_target_unknown")
    required = ("repo_snapshot", "evidence_packets_v3", "code_facts_v1", "atomic_claims_v3", "evidence")
    if any(not state.artifacts.get(key) for key in required):
        return _blocked_packet_repair(state, "packet_scoped_repair_inputs_missing")
    try:
        snapshot = load_repo_snapshot(state.artifacts["repo_snapshot"])
        if not snapshot_is_current(snapshot):
            return _blocked_packet_repair(state, "packet_scoped_repair_snapshot_stale")
        old_packets = load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
        old_facts = load_code_facts_v1(state.artifacts["code_facts_v1"])
        old_claims = load_atomic_claims_v3(state.artifacts["atomic_claims_v3"])
        fresh = compile_evidence_v3(snapshot)
    except (OSError, ValueError, json.JSONDecodeError):
        return _blocked_packet_repair(state, "packet_scoped_repair_inputs_invalid")
    if fresh is None:
        return _blocked_packet_repair(state, "packet_scoped_repair_compiler_unavailable")
    intent_graph = None
    intent_path = state.artifacts.get("intent_obligation_graph_v2", "")
    if intent_path and Path(intent_path).exists():
        try:
            intent_graph = IntentObligationGraphV2.model_validate_json(
                Path(intent_path).read_text(encoding="utf-8")
            )
            fresh = fresh.model_copy(update={
                "claims": bind_claims_to_obligations(
                    intent_graph,
                    fact_set=fresh.facts,
                    claim_set=fresh.claims,
                )
            })
        except (OSError, ValueError):
            return _blocked_packet_repair(state, "packet_scoped_repair_intent_rebind_failed")

    target_packet_ids = {item.packet_id for item in requests}
    old_packet_by_id = {item.packet_id: item for item in old_packets.packets}
    fresh_packet_by_id = {item.packet_id: item for item in fresh.packets.packets}
    if not target_packet_ids.issubset(old_packet_by_id) or not target_packet_ids.issubset(fresh_packet_by_id):
        return _blocked_packet_repair(state, "packet_scoped_repair_target_missing")
    affected_span_ids = {
        span.span_id
        for packet_id in target_packet_ids
        for span in old_packet_by_id[packet_id].spans
    }
    affected_fact_ids = {
        fact.fact_id
        for fact in old_facts.facts
        if affected_span_ids.intersection([*fact.direct_span_ids, *fact.relation_span_ids])
    }
    affected_claim_ids = {
        claim.claim_id
        for claim in old_claims.claims
        if affected_fact_ids.intersection(claim.fact_ids)
    }
    if not _unaffected_items_equal(old_packets.packets, fresh.packets.packets, "packet_id", target_packet_ids):
        return _blocked_packet_repair(state, "packet_scoped_repair_would_modify_unrelated_packets")
    if not _unaffected_items_equal(old_facts.facts, fresh.facts.facts, "fact_id", affected_fact_ids):
        return _blocked_packet_repair(state, "packet_scoped_repair_would_modify_unrelated_facts")
    if not _unaffected_items_equal(old_claims.claims, fresh.claims.claims, "claim_id", affected_claim_ids):
        return _blocked_packet_repair(state, "packet_scoped_repair_would_modify_unrelated_claims")
    if all(
        old_packet_by_id[item].model_dump(mode="json") == fresh_packet_by_id[item].model_dump(mode="json")
        for item in target_packet_ids
    ):
        return _blocked_packet_repair(state, "packet_scoped_repair_no_progress")

    attempt = max(item.attempt for item in requests)
    repair_dir = artifact_dir(state.method_root, "07_validation")
    written = write_compiler_v3_artifacts(repair_dir, fresh, suffix=f"_repair{attempt}")
    repaired_equations, _equation_reports = compile_equation_claims(
        [],
        fresh.facts,
        repo_snapshot_id=fresh.facts.repo_snapshot_id,
        project_tree_hash=fresh.facts.project_tree_hash,
    )
    equation_path = repair_dir / f"equation_claims_v1_repair{attempt}.json"
    write_equation_claims(equation_path, repaired_equations)
    written["equation_claims_v1"] = str(equation_path)
    try:
        method_payload = MethodEvidence.model_validate_json(Path(state.artifacts["evidence"]).read_text(encoding="utf-8"))
        evidence_snapshot = (
            load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
            if state.artifacts.get("evidence_snapshot_v2")
            else None
        )
        projection = build_authoring_projection(
            method_evidence=method_payload,
            claim_map=ClaimEvidenceMap(claims=[]),
            verification=ClaimVerificationReport(claims=[]),
            evidence_snapshot_v2=evidence_snapshot,
            atomic_claims_v3=fresh.claims,
            evidence_packets_v3=fresh.packets,
            equation_claims_v1=repaired_equations,
        )
        projection_path = repair_dir / f"agentic_authoring_input_projection_repair{attempt}.json"
        write_authoring_projection(projection_path, projection)
    except (OSError, ValueError):
        return _blocked_packet_repair(state, "packet_scoped_repair_projection_failed")
    report_path = repair_dir / f"agentic_packet_scoped_repair_report_v1_r{attempt}.json"
    report_path.write_text(json.dumps({
        "status": "repaired",
        "attempt": attempt,
        "packet_ids": sorted(target_packet_ids),
        "affected_fact_ids": sorted(affected_fact_ids),
        "affected_claim_ids": sorted(affected_claim_ids),
        "forbidden_global_reruns": ["intake", "analysis", "authoring"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifacts = {
        **state.artifacts,
        **written,
        "authoring_projection": str(projection_path),
        "packet_scoped_repair_report_v1": str(report_path),
    }
    if intent_graph is not None:
        coverage = build_obligation_coverage_v2(
            intent_graph,
            fact_set=fresh.facts,
            claim_set=fresh.claims,
            explicit_gaps=fresh.claims.explicit_code_gaps,
        )
        coverage_path = repair_dir / f"obligation_coverage_v2_repair{attempt}.json"
        coverage_path.write_text(coverage.model_dump_json(indent=2) + "\n", encoding="utf-8")
        artifacts["obligation_coverage_v2"] = str(coverage_path)
        if state.artifacts.get("authoring_plan_v3"):
            plan = build_authoring_plan_v3(
                run_id=state.run_id or "packet-scoped-repair",
                repo_snapshot_id=snapshot.snapshot_id,
                project_tree_hash=snapshot.project_tree_hash,
                intent_graph=intent_graph,
                coverage_report=coverage,
                claim_set=fresh.claims,
                explicit_gaps=fresh.claims.explicit_code_gaps,
                method_name=method_payload.method_name,
                author_goal=method_payload.method_goal,
            )
            plan_path = repair_dir / f"agentic_authoring_plan_v3_repair{attempt}.json"
            write_authoring_plan_v3(str(plan_path), plan)
            artifacts["authoring_plan_v3"] = str(plan_path)
    legacy_plan_path = state.artifacts.get("authoring_plan", "")
    if legacy_plan_path and Path(legacy_plan_path).exists():
        try:
            legacy_plan = json.loads(Path(legacy_plan_path).read_text(encoding="utf-8"))
            legacy_plan["projection_digest"] = projection.projection_digest
            repaired_plan_path = repair_dir / f"agentic_authoring_plan_repair{attempt}.json"
            repaired_plan_path.write_text(
                json.dumps(legacy_plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            artifacts["authoring_plan"] = str(repaired_plan_path)
        except (OSError, json.JSONDecodeError):
            return _blocked_packet_repair(state, "packet_scoped_repair_legacy_plan_failed")
    return state.model_copy(update={
        "artifacts": artifacts,
        "next_node": "final_text_claim_extractor",
        "blocked_reason": "",
        "decisions": [*state.decisions, AgentDecision(
            node="packet_binding_repair",
            decision="scoped_packet_recompiled",
            rationale=(
                f"Recompiled packets {sorted(target_packet_ids)} and their dependency slice; "
                "all unrelated packets, facts and claims were unchanged."
            ),
            artifact_keys=["packet_repair_requests_v1", "packet_scoped_repair_report_v1", "authoring_projection"],
        )],
    }).model_dump(mode="json")


def _unaffected_items_equal(old_items, fresh_items, identity_field: str, affected_ids: set[str]) -> bool:
    old = {getattr(item, identity_field): item.model_dump(mode="json") for item in old_items if getattr(item, identity_field) not in affected_ids}
    fresh = {getattr(item, identity_field): item.model_dump(mode="json") for item in fresh_items if getattr(item, identity_field) not in affected_ids}
    return old == fresh


def _blocked_packet_repair(state: AgenticRunState, reason: str) -> dict[str, Any]:
    return state.model_copy(update={
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
    current_path.write_text(candidate.model_dump_json(indent=2) + "\n", encoding="utf-8")
    best_path = quality_dir / "agentic_quality_state_best_v2.json"
    best_text_path = quality_dir / "agentic_best_final_text_candidate.md"
    replaced = False
    restored = False
    if best_path.exists() and best_text_path.exists():
        incumbent = QualityStateV2.model_validate_json(best_path.read_text(encoding="utf-8"))
        best, replaced = select_best_state(candidate, incumbent)
        if replaced:
            best_path.write_text(best.model_dump_json(indent=2) + "\n", encoding="utf-8")
            best_text_path.write_text(text_path.read_text(encoding="utf-8"), encoding="utf-8")
        elif text_path.read_text(encoding="utf-8") != best_text_path.read_text(encoding="utf-8"):
            text_path.write_text(best_text_path.read_text(encoding="utf-8"), encoding="utf-8")
            restored = True
    else:
        best_path.write_text(candidate.model_dump_json(indent=2) + "\n", encoding="utf-8")
        best_text_path.write_text(text_path.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "quality_state_current_v2": str(current_path),
        "quality_state_best_v2": str(best_path),
        "best_final_text_candidate": str(best_text_path),
    }, restored


def _clean_local_repair_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line.strip()) + "\n"


def _insert_into_markdown_section(text: str, heading: str, fragment: str) -> str:
    lines = text.splitlines()
    target = f"## {heading}".strip().lower()
    start = next(
        (index for index, line in enumerate(lines) if line.strip().lower() == target),
        None,
    )
    if start is None:
        return text.rstrip() + f"\n\n## {heading}\n{fragment}\n"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    lines.insert(end, fragment)
    return "\n".join(lines) + "\n"


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
