from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.authoring_constraints import apply_authoring_constraints, write_authoring_constraints
from code2paper.agentic.authoring_authorization import check_pre_authoring_authorization, pre_authoring_blocked_result
from code2paper.agentic.authoring_context import (
    authoring_context_brief,
    build_authoring_context,
    write_authoring_context,
)
from code2paper.agentic.authoring_plan import authoring_plan_brief, load_authoring_plan, write_authoring_plan
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace
from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    projected_writer_inputs,
    projection_writer_brief,
    write_authoring_projection,
)
from code2paper.agentic.atomic_claim_v2 import load_atomic_claims_v2
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.claim_verifier import (
    build_claim_verification_report,
    load_claim_verification_report,
    write_claim_verification_report,
)
from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.decision_core import write_decision_trace
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, CodeAlignmentIR, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import load_llm_config_from_env, with_node_output_budget
from code2paper.pipeline.stages.authoring import write_phase5_artifacts


def run_authoring(state: AgenticRunState) -> StageToolResult:
    if not _has_frozen_evidence(state):
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            blocked_reason="frozen_evidence_required",
            summary="Authoring cannot run before MethodEvidence and claim_evidence_map exist.",
        )
    authorization = check_pre_authoring_authorization(state)
    if not authorization.passed:
        return pre_authoring_blocked_result(authorization)
    method_evidence = MethodEvidence.model_validate(_read_json(method_output(state.method_root, "evidence")))
    claim_map = ClaimEvidenceMap.model_validate(_read_json(method_output(state.method_root, "claims")))
    verification_path = _claim_verification_path(state)
    if verification_path.exists():
        verification = load_claim_verification_report(verification_path)
    else:
        verification = build_claim_verification_report(method_evidence, claim_map)
        write_claim_verification_report(verification_path, verification)
    constrained_evidence, constrained_claim_map, constraints = apply_authoring_constraints(
        method_evidence=method_evidence,
        claim_map=claim_map,
        report=verification,
    )
    projection = build_authoring_projection(
        method_evidence=method_evidence,
        claim_map=claim_map,
        verification=verification,
        raw_evidence=(
            RawEvidencePack.model_validate(_read_json(Path(state.artifacts["evidence_raw"])))
            if state.artifacts.get("evidence_raw") and Path(state.artifacts["evidence_raw"]).exists()
            else None
        ),
        evidence_snapshot_v2=(
            load_evidence_snapshot_v2(state.artifacts["evidence_snapshot_v2"])
            if state.artifacts.get("evidence_snapshot_v2") and Path(state.artifacts["evidence_snapshot_v2"]).exists()
            else None
        ),
        atomic_claims_v2=(
            load_atomic_claims_v2(state.artifacts["atomic_claims_v2"])
            if state.artifacts.get("atomic_claims_v2") and Path(state.artifacts["atomic_claims_v2"]).exists()
            else None
        ),
    )
    projection_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_input_projection.json"
    write_authoring_projection(projection_path, projection)
    constrained_evidence, constrained_claim_map = projected_writer_inputs(projection, template=constrained_evidence)
    constraints_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_constraints.json"
    write_authoring_constraints(constraints_path, constraints)
    authoring_context = build_authoring_context(
        method_evidence=method_evidence,
        claim_map=claim_map,
        verification=verification,
        constraints=constraints,
    )
    authoring_context_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_context.json"
    write_authoring_context(authoring_context_path, authoring_context)
    authoring_plan_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_plan.json"
    existing_plan_path = state.artifacts.get("authoring_plan", "")
    if existing_plan_path and Path(existing_plan_path).exists():
        authoring_plan = load_authoring_plan(existing_plan_path)
        authoring_plan_path = Path(existing_plan_path)
        authoring_plan_trace_path = state.artifacts.get("authoring_plan_decision_trace", "")
    else:
        authoring_plan, plan_trace = authoring_plan_trace(
            authoring_context,
            projection=projection,
        )
        write_authoring_plan(authoring_plan_path, authoring_plan)
        trace_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_plan_decision_trace.json"
        write_decision_trace(trace_path, plan_trace)
        authoring_plan_trace_path = str(trace_path)
    pre_authoring_artifacts = {
        "claim_verification": str(verification_path),
        "authoring_constraints": str(constraints_path),
        "authoring_context": str(authoring_context_path),
        "authoring_plan": str(authoring_plan_path),
        "authoring_projection": str(projection_path),
    }
    if authoring_plan_trace_path:
        pre_authoring_artifacts["authoring_plan_decision_trace"] = str(authoring_plan_trace_path)
    if not authoring_plan.hard_gate_passed:
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            artifacts=pre_authoring_artifacts,
            blocked_reason="authoring_plan_failed_evidence_gate",
            summary="Authoring plan did not pass the evidence gate; method text was not written.",
            decisions=[
                AgentDecision(
                    node="authoring_planner",
                    decision="authoring_plan_blocked",
                    rationale="; ".join(authoring_plan.recommended_actions),
                    artifact_keys=[
                        "authoring_plan",
                        "authoring_plan_decision_trace",
                        "authoring_context",
                        "authoring_constraints",
                        "claim_verification",
                    ],
                )
            ],
            metrics={
                "allowed_claims": len(constraints.allowed_claim_ids),
                "caveated_claims": len(constraints.caveated_claim_ids),
                "excluded_claims": len(constraints.excluded_claim_ids),
                "authoring_plan_sections": len(authoring_plan.sections),
            },
        )
    if authoring_plan.projection_digest != projection.projection_digest:
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            artifacts=pre_authoring_artifacts,
            blocked_reason="authoring_plan_projection_digest_mismatch",
            summary="Authoring plan is not bound to the current authoring projection.",
        )
    alignment_path = method_output(state.method_root, "alignment")
    alignment = CodeAlignmentIR.model_validate(_read_json(alignment_path)) if alignment_path.exists() else None
    grounding_context = _join_context_blocks(
        projection_writer_brief(projection),
        authoring_plan_brief(authoring_plan, include_exclusions=False),
    )
    markdown, _tex, paths = write_phase5_artifacts(
        method_root=state.method_root,
        method_evidence=constrained_evidence,
        claim_map=constrained_claim_map,
        llm_config=_llm_config(state),
        alignment=alignment,
        grounding_context_markdown=grounding_context,
        equations_tex=_read_text(method_output(state.method_root, "equations_tex")),
        symbols_tex=_read_text(method_output(state.method_root, "symbols_tex")),
    )
    artifacts = _existing_paths(paths)
    artifacts.update(pre_authoring_artifacts)
    if markdown is None:
        blocked_reason = _blocked_reason(paths.get("phase5_blocked"))
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            artifacts=artifacts,
            blocked_reason=blocked_reason or "authoring_blocked",
            summary="Authoring did not produce method text.",
            decisions=[
                AgentDecision(
                    node="authoring_constraint_builder",
                    decision="authoring_blocked_after_constraints",
                    rationale="; ".join([*authoring_context.recommended_actions, *authoring_plan.recommended_actions]),
                    artifact_keys=[
                        "authoring_plan",
                        "authoring_plan_decision_trace",
                        "authoring_context",
                        "authoring_constraints",
                        "claim_verification",
                    ],
                )
            ],
        )
    return StageToolResult(
        stage="authoring",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary="Wrote evidence-backed method draft using verified claim constraints.",
        decisions=[
            AgentDecision(
                node="authoring_constraint_builder",
                decision="constrained_authoring_inputs",
                rationale=(
                    f"allowed={len(constraints.allowed_claim_ids)}, "
                    f"caveated={len(constraints.caveated_claim_ids)}, "
                    f"excluded={len(constraints.excluded_claim_ids)}, "
                    f"context_gate={authoring_context.hard_gate_passed}, "
                    f"plan_gate={authoring_plan.hard_gate_passed}"
                ),
                artifact_keys=[
                    "authoring_plan",
                    "authoring_plan_decision_trace",
                    "authoring_context",
                    "authoring_constraints",
                    "claim_verification",
                ],
            )
        ],
        metrics={
            "allowed_claims": len(constraints.allowed_claim_ids),
            "caveated_claims": len(constraints.caveated_claim_ids),
            "excluded_claims": len(constraints.excluded_claim_ids),
            "authoring_plan_sections": len(authoring_plan.sections),
        },
    )


def _llm_config(state: AgenticRunState):
    return with_node_output_budget(
        load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model),
        "authoring",
        4096,
    )


def _has_frozen_evidence(state: AgenticRunState) -> bool:
    return method_output(state.method_root, "evidence").exists() and method_output(state.method_root, "claims").exists()


def _claim_verification_path(state: AgenticRunState) -> Path:
    artifact = state.artifacts.get("claim_verification", "")
    if artifact:
        return Path(artifact)
    return artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"


def _existing_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items() if path.exists()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _join_context_blocks(*blocks: str) -> str:
    return "\n\n".join(block.strip() for block in blocks if str(block or "").strip())


def _blocked_reason(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("blocked_reason") or "")
