from __future__ import annotations

import json
import os
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
from code2paper.agentic.authoring_plan_v3 import (
    authoring_plan_v3_brief,
    build_authoring_plan_v3,
    write_authoring_plan_v3,
)
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace
from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    projected_writer_inputs,
    projection_writer_brief,
    restrict_projection_for_authoring_revision,
    write_authoring_projection,
)
from code2paper.agentic.atomic_claim_v2 import load_atomic_claims_v2
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.evidence_compiler_v3 import load_atomic_claims_v3, load_evidence_packets_v3
from code2paper.agentic.equation_claims import load_equation_claims
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
from code2paper.agentic.publication_method_writer import run_publication_method_writer
from code2paper.agentic.claim_verifier import (
    build_claim_verification_report,
    load_claim_verification_report,
    write_claim_verification_report,
)
from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.decision_core import write_decision_trace
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, CodeAlignmentIR, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stages.authoring import write_phase5_artifacts


def run_authoring(state: AgenticRunState) -> StageToolResult:
    if not _has_frozen_evidence(state):
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            blocked_reason="frozen_evidence_required",
            summary="Authoring cannot run before MethodEvidence and claim_evidence_map exist.",
        )
    if os.environ.get("CODE2PAPER_AGENTIC_RESEARCH_V3", "").strip().lower() in {
        "1", "true", "yes", "on"
    }:
        required_v3 = ("evidence_packets_v3", "atomic_claims_v3")
        missing_v3 = [
            key
            for key in required_v3
            if not state.artifacts.get(key)
            or not Path(state.artifacts[key]).exists()
        ]
        if missing_v3:
            return StageToolResult(
                stage="authoring",
                status=StageStatus.BLOCKED,
                blocked_reason="generic_path_compilation_required",
                summary=(
                    "V3 Method authoring is fail-closed because validated "
                    f"V3 artifacts are missing: {', '.join(missing_v3)}."
                ),
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
        atomic_claims_v3=(
            load_atomic_claims_v3(state.artifacts["atomic_claims_v3"])
            if state.artifacts.get("atomic_claims_v3") and Path(state.artifacts["atomic_claims_v3"]).exists()
            else None
        ),
        evidence_packets_v3=(
            load_evidence_packets_v3(state.artifacts["evidence_packets_v3"])
            if state.artifacts.get("evidence_packets_v3") and Path(state.artifacts["evidence_packets_v3"]).exists()
            else None
        ),
        equation_claims_v1=(
            load_equation_claims(state.artifacts["equation_claims_v1"])
            if state.artifacts.get("equation_claims_v1") and Path(state.artifacts["equation_claims_v1"]).exists()
            else None
        ),
    )
    projection_path = artifact_dir(state.method_root, "06_authoring") / "agentic_authoring_input_projection.json"
    write_authoring_projection(projection_path, projection)
    v3_plan = None
    v3_plan_path: Path | None = None
    intent_v2_path = state.artifacts.get("intent_obligation_graph_v2", "")
    coverage_v2_path = state.artifacts.get("obligation_coverage_v2", "")
    claims_v3_path = state.artifacts.get("atomic_claims_v3", "")
    if all(
        path and Path(path).exists()
        for path in (intent_v2_path, coverage_v2_path, claims_v3_path)
    ):
        intent_v2 = IntentObligationGraphV2.model_validate_json(
            Path(intent_v2_path).read_text(encoding="utf-8")
        )
        coverage_v2 = ObligationCoverageReportV2.model_validate_json(
            Path(coverage_v2_path).read_text(encoding="utf-8")
        )
        claims_v3 = load_atomic_claims_v3(claims_v3_path)
        # Older/minimal graph states do not always carry a run id.  The V3
        # plan contract is intentionally strict, so derive a stable id from
        # the immutable claim-set digest instead of weakening the schema.
        v3_run_id = state.run_id.strip() or f"run-{claims_v3.content_digest.removeprefix('sha256:')[:16]}"
        v3_plan = build_authoring_plan_v3(
            run_id=v3_run_id,
            repo_snapshot_id=claims_v3.repo_snapshot_id,
            project_tree_hash=claims_v3.project_tree_hash,
            intent_graph=intent_v2,
            coverage_report=coverage_v2,
            claim_set=claims_v3,
            explicit_gaps=claims_v3.explicit_code_gaps,
            method_name=method_evidence.method_name,
            author_goal=method_evidence.method_goal,
        )
        v3_plan_path = (
            artifact_dir(state.method_root, "06_authoring")
            / "agentic_authoring_plan_v3.json"
        )
        write_authoring_plan_v3(str(v3_plan_path), v3_plan)
    revision_excluded_ids = _revision_excluded_projection_claim_ids(state)
    writer_projection = restrict_projection_for_authoring_revision(
        projection, revision_excluded_ids
    )
    constrained_evidence, constrained_claim_map = projected_writer_inputs(
        writer_projection, template=constrained_evidence
    )
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
    if v3_plan_path is not None:
        pre_authoring_artifacts["authoring_plan_v3"] = str(v3_plan_path)
    if authoring_plan_trace_path:
        pre_authoring_artifacts["authoring_plan_decision_trace"] = str(authoring_plan_trace_path)
    # In V3 runs the typed obligation/claim plan is authoritative.  The legacy
    # plan remains persisted for compatibility and diagnostics, but it must not
    # veto a V3 plan that passed its stricter typed gate.
    if v3_plan is None and not authoring_plan.hard_gate_passed:
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
    if v3_plan is not None and not v3_plan.plan_gate_passed:
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            artifacts=pre_authoring_artifacts,
            blocked_reason="authoring_plan_v3_failed_evidence_gate",
            summary="V3 authoring plan did not satisfy typed obligation and minimality gates.",
            decisions=[
                AgentDecision(
                    node="authoring_planner_v3",
                    decision="authoring_plan_v3_blocked",
                    rationale="; ".join(v3_plan.gate_failures),
                    artifact_keys=[
                        "authoring_plan_v3",
                        "obligation_coverage_v2",
                        "atomic_claims_v3",
                    ],
                )
            ],
        )
    if authoring_plan.projection_digest != projection.projection_digest:
        return StageToolResult(
            stage="authoring",
            status=StageStatus.BLOCKED,
            artifacts=pre_authoring_artifacts,
            blocked_reason="authoring_plan_projection_digest_mismatch",
            summary="Authoring plan is not bound to the current authoring projection.",
        )
    publication_setting = os.environ.get("CODE2PAPER_PUBLICATION_WRITER_V1", "").strip().lower()
    publication_inputs = (
        "atomic_claims_v3", "code_facts_v1", "equation_claims_v1",
        "configuration_claims_v1", "method_completeness_matrix_v1",
        "method_section_plan_v2",
    )
    publication_writer_enabled = (
        publication_setting in {"1", "true", "yes", "on"}
        or (
            publication_setting not in {"0", "false", "no", "off"}
            and all(
                (path := state.artifacts.get(key, "")) and Path(path).is_file()
                for key in publication_inputs
            )
        )
    )
    if publication_writer_enabled:
        publication_result, publication_paths = run_publication_method_writer(
            out_root=state.out_root,
            artifact_paths={**state.artifacts, **pre_authoring_artifacts},
            llm_config=_llm_config(state),
        )
        publication_artifacts = {
            **state.artifacts,
            **pre_authoring_artifacts,
            **publication_paths,
        }
        if publication_result.status == "blocked":
            # A rerun may share an output directory with an earlier accepted
            # Writer result.  Do not let old candidate paths survive in the
            # current blocked state; the durable Writer result/review sidecar
            # are the only consumable outputs for a blocked stage.
            for key in (
                "repository_verified_method",
                "publication_candidate_method",
                "text_md",
                "text_clean_md",
            ):
                publication_artifacts.pop(key, None)
            return StageToolResult(
                stage="authoring",
                status=StageStatus.BLOCKED,
                artifacts=publication_artifacts,
                blocked_reason=publication_result.blocked_reason or "publication_writer_blocked",
                summary="Publication Method Writer did not pass binding and lexical-authorship gates.",
                decisions=[AgentDecision(
                    node="publication_method_writer",
                    decision="blocked",
                    rationale="; ".join(publication_result.binding_failures) or publication_result.blocked_reason,
                    artifact_keys=[
                        "publication_writer_result_v1",
                        "author_review_candidates",
                        "writing_research_routes_v1",
                        "writing_research_callback_artifacts_v1",
                    ],
                )],
            )
        return StageToolResult(
            stage="authoring",
            status=StageStatus.SUCCESS,
            artifacts=publication_artifacts,
            summary=(
                "Wrote publication Method sections with complete claim/equation/configuration bindings."
                if publication_result.status == "success"
                else "Wrote the validated publication Method subset and recorded incomplete sections for review."
            ),
            decisions=[AgentDecision(
                node="publication_method_writer",
                decision=publication_result.status,
                rationale=(
                    f"accepted_sections={len(publication_result.accepted_section_ids)}, "
                    f"incomplete_sections={len(publication_result.incomplete_section_ids)}, "
                    f"authorship={publication_result.authorship_ledger_digest}"
                ),
                artifact_keys=[
                    "method_section_plan_v2",
                    "publication_writer_result_v1",
                    "repository_verified_method",
                    "publication_candidate_method",
                    "author_review_candidates",
                    "final_text_authorship_ledger_v1",
                    "final_text_claims",
                    "text_evidence_validation",
                    "publication_quality_report_v1",
                    "publication_section_checkpoint_v1",
                    "writing_research_routes_v1",
                    "writing_research_callback_artifacts_v1",
                ],
            )],
            metrics={
                "publication_sections": len(publication_result.accepted_section_ids),
                "publication_incomplete_sections": len(publication_result.incomplete_section_ids),
            },
        )
    alignment_path = method_output(state.method_root, "alignment")
    alignment = CodeAlignmentIR.model_validate(_read_json(alignment_path)) if alignment_path.exists() else None
    grounding_context = _join_context_blocks(
        projection_writer_brief(writer_projection),
        authoring_plan_v3_brief(v3_plan, include_exclusions=False)
        if v3_plan is not None
        else "",
        (
            authoring_plan_brief(authoring_plan, include_exclusions=False)
            if writer_projection.projection_digest == projection.projection_digest
            else ""
        ),
        _behavior_template_organization_brief(state),
        _text_revision_brief(state),
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
    # Role-tagged authoring calls apply their own audited budgets in
    # ``apply_role_config`` (planner=2048, writer=8192, then 12288 only on
    # a length retry).  The historical stage-wide 4096 clamp made the base
    # config look explicit and therefore prevented the writer policy from
    # taking effect in the production V3 wrapper.
    return load_llm_config_from_env(
        provider=state.llm_provider,
        model=state.llm_model,
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


def _behavior_template_organization_brief(state: AgenticRunState) -> str:
    """Return non-authorizing organization hints derived from behavior structure."""

    path = state.artifacts.get("behavior_template_matches_v1", "")
    if not path or not Path(path).exists():
        return ""
    try:
        payload = _read_json(Path(path))
    except (OSError, json.JSONDecodeError):
        return ""
    return json.dumps(
        {
            "behavior_template_stage_hints": payload.get("stage_hints", []),
            "hard_rule": (
                "These hints may only order already-authorized plan claims. "
                "They must not add claims, evidence ids, equations, or positive facts."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def _text_revision_brief(state: AgenticRunState) -> str:
    path = state.artifacts.get("text_evidence_validation", "")
    if not path or not Path(path).exists():
        return ""
    try:
        payload = _read_json(Path(path))
    except (OSError, json.JSONDecodeError):
        return ""
    issues = [
        {
            "atomic_claim_id": verdict.get("atomic_claim_id", ""),
            "matched_projection_claim_ids": verdict.get("matched_projection_claim_ids", []),
            "keep_supported_fragment": verdict.get("supported_fragment", ""),
            "remove_or_rewrite_text": verdict.get("unsupported_fragment", ""),
            "failures": verdict.get("deterministic_failures", []),
            "repair_action": verdict.get("repair_action", ""),
        }
        for verdict in payload.get("verdicts", [])
        if verdict.get("status") not in {"supported", "caveated"}
    ]
    if not issues:
        return ""
    return json.dumps(
        {
            "authoring_revision_feedback": issues,
            "rule": (
                "For each issue, either use keep_supported_fragment verbatim or delete the "
                "entire atomic claim. Never reintroduce remove_or_rewrite_text. Remove factual "
                "text with no projected-claim match; do not retrieve evidence for model-added prose."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def _revision_excluded_projection_claim_ids(state: AgenticRunState) -> set[str]:
    path = state.artifacts.get("text_evidence_validation", "")
    if not path or not Path(path).exists():
        return set()
    try:
        payload = _read_json(Path(path))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        str(claim_id)
        for verdict in payload.get("verdicts", [])
        if verdict.get("status") not in {"supported", "caveated"}
        and str(verdict.get("repair_action") or "").startswith("revise_authoring")
        for claim_id in verdict.get("matched_projection_claim_ids", [])
        if str(claim_id)
    }


def _blocked_reason(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("blocked_reason") or "")
