from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from code2paper.agentic.authoring_projection import load_authoring_projection
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.final_text_claims import extract_final_text_claims, load_final_text_claims, write_final_text_claims
from code2paper.agentic.text_evidence_validator import (
    SemanticVerifier,
    load_text_evidence_validation,
    validate_text_evidence,
    write_text_evidence_validation,
)
from code2paper.agentic.text_trace_builder import build_final_text_trace, write_final_text_trace
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import RawEvidencePack


def final_text_claim_extractor_node(raw_state: dict[str, Any]) -> dict[str, Any]:
    state = AgenticRunState.model_validate(raw_state)
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
    try:
        final_claims = load_final_text_claims(state.artifacts["final_text_claims"])
        projection = load_authoring_projection(state.artifacts["authoring_projection"])
        raw_evidence = RawEvidencePack.model_validate_json(Path(state.artifacts["evidence_raw"]).read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError):
        return state.model_copy(
            update={"blocked_reason": "text_evidence_validator_inputs_missing", "next_node": "blocked"}
        ).model_dump(mode="json")
    verifier_calls_used = int(state.loop_counters.get("semantic_verifier") or 0)
    verifier_calls_remaining = max(0, state.max_semantic_verifier_calls - verifier_calls_used)
    report = validate_text_evidence(
        final_claims=final_claims,
        projection=projection,
        raw_evidence=raw_evidence,
        semantic_verifier=semantic_verifier,
        max_semantic_verifier_calls=verifier_calls_remaining,
        require_semantic_verifier=state.max_semantic_verifier_calls > 0,
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
    if next_node == "authoring":
        updated = updated.increment_loop("revision")
    elif next_node == "analysis":
        updated = updated.increment_loop("evidence_revision")
    return updated.model_dump(mode="json")


def _next_after_text_gate(state: AgenticRunState, status: str, actions: list[str]) -> tuple[str, str]:
    if status == "passed":
        return "validation", ""
    needs_evidence = any("analysis" in action or "direct_evidence" in action for action in actions)
    if needs_evidence:
        if int(state.loop_counters.get("evidence_revision") or 0) < state.max_evidence_revision_rounds:
            return "analysis", ""
        return "blocked", "text_claim_direct_evidence_missing_budget_exhausted"
    if int(state.loop_counters.get("revision") or 0) < state.max_authoring_revision_rounds:
        return "authoring", ""
    return "blocked", "text_claim_authoring_revision_budget_exhausted"


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
