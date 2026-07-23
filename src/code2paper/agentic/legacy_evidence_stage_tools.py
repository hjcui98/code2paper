from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.claim_verifier import (
    bind_claim_verification_to_evidence_v2,
    build_claim_verification_report,
    write_claim_verification_report,
)
from code2paper.agentic.atomic_claim_v2 import convert_claims_to_v2, verify_atomic_claims_v2, write_atomic_claims_v2
from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
from code2paper.agentic.evidence_v2 import (
    build_evidence_snapshot_v2,
    load_evidence_snapshot_v2,
    write_evidence_snapshot_v2,
)
from code2paper.agentic.evidence_compiler_v3 import (
    compile_evidence_v3,
    validate_evidence_compiler_v3,
    write_compiler_v3_artifacts,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.obligation_fact_alignment import (
    bind_claims_to_obligations,
    build_obligation_coverage_v2,
)
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.core.output_names import artifact_dir, method_output
from code2paper.core.schemas import ClaimEvidenceMap, CodeAlignmentIR, CodeMethodAnalysis, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stages.evidence import run_phase3_evidence
from code2paper.pipeline.stages.grounding import write_phase4_artifacts


def run_evidence(state: AgenticRunState) -> StageToolResult:
    raw_pack = RawEvidencePack.model_validate(_read_json(method_output(state.method_root, "evidence_raw")))
    alignment = CodeAlignmentIR.model_validate(_read_json(method_output(state.method_root, "alignment")))
    analysis_path = method_output(state.method_root, "analysis")
    code_method_analysis = CodeMethodAnalysis.model_validate(_read_json(analysis_path)) if analysis_path.exists() else None
    facts_path = method_output(state.method_root, "facts")
    facts = _read_json(facts_path) if facts_path.exists() else None
    method_evidence, paths = run_phase3_evidence(
        method_root=state.method_root,
        paper_root=state.out_root,
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        code_facts=facts,
        llm_config=_llm_config(state),
    )
    claim_map = ClaimEvidenceMap.model_validate(_read_json(paths["claims"]))
    verification = build_claim_verification_report(method_evidence, claim_map)
    verification_path = artifact_dir(state.method_root, "04_evidence") / "agentic_claim_verification.json"
    write_claim_verification_report(verification_path, verification)
    repo_snapshot_path = state.artifacts.get("repo_snapshot", "")
    if not repo_snapshot_path or not Path(repo_snapshot_path).exists():
        return StageToolResult(
            stage="evidence",
            status=StageStatus.BLOCKED,
            blocked_reason="repo_snapshot_required_for_evidence_v2",
            summary="Evidence V2 requires a frozen repository snapshot.",
        )
    repo_snapshot = load_repo_snapshot(repo_snapshot_path)
    parent_path = state.artifacts.get("evidence_snapshot_v2", "") or state.artifacts.get(
        "parent_evidence_snapshot_v2", ""
    )
    parent = (
        load_evidence_snapshot_v2(parent_path)
        if parent_path and Path(parent_path).exists()
        else None
    )
    evidence_v2 = build_evidence_snapshot_v2(
        raw_pack,
        repo_snapshot,
        parent=parent,
        repair_reason="bounded_evidence_repair" if parent else "initial_v1_compatibility_conversion",
    )
    verification = bind_claim_verification_to_evidence_v2(
        verification,
        repo_snapshot_id=repo_snapshot.snapshot_id,
        evidence_snapshot_id=evidence_v2.evidence_snapshot_id,
        evidence_snapshot_digest=evidence_v2.content_digest,
    )
    write_claim_verification_report(verification_path, verification)
    version_suffix = f"_r{evidence_v2.snapshot_version}" if parent else ""
    evidence_v2_path = artifact_dir(state.method_root, "04_evidence") / f"evidence_snapshot_v2{version_suffix}.json"
    write_evidence_snapshot_v2(evidence_v2_path, evidence_v2)
    atomic_claims_v2_unverified = convert_claims_to_v2(claim_map, verification, evidence_v2)
    atomic_claims_v2_unverified_path = (
        artifact_dir(state.method_root, "04_evidence")
        / f"atomic_claims_v2_unverified{version_suffix}.json"
    )
    write_atomic_claims_v2(atomic_claims_v2_unverified_path, atomic_claims_v2_unverified)
    atomic_claims_v2 = verify_atomic_claims_v2(atomic_claims_v2_unverified, evidence_v2)
    atomic_claims_v2_path = artifact_dir(state.method_root, "04_evidence") / f"atomic_claims_v2{version_suffix}.json"
    write_atomic_claims_v2(atomic_claims_v2_path, atomic_claims_v2)
    artifacts = _existing_paths(paths)
    artifacts["claim_verification"] = str(verification_path)
    artifacts["evidence_snapshot_v2"] = str(evidence_v2_path)
    artifacts["atomic_claims_v2"] = str(atomic_claims_v2_path)
    artifacts["atomic_claims_v2_unverified"] = str(atomic_claims_v2_unverified_path)
    compiler_v3 = compile_evidence_v3(repo_snapshot)
    if compiler_v3 is not None:
        intent_v2_path = state.artifacts.get("intent_obligation_graph_v2", "")
        coverage_path: Path | None = None
        if intent_v2_path and Path(intent_v2_path).exists():
            intent_v2 = IntentObligationGraphV2.model_validate_json(
                Path(intent_v2_path).read_text(encoding="utf-8")
            )
            rebound_claims = bind_claims_to_obligations(
                intent_v2,
                fact_set=compiler_v3.facts,
                claim_set=compiler_v3.claims,
            )
            compiler_v3 = compiler_v3.model_copy(
                update={"claims": rebound_claims}
            )
            coverage = build_obligation_coverage_v2(
                intent_v2,
                fact_set=compiler_v3.facts,
                claim_set=compiler_v3.claims,
                explicit_gaps=compiler_v3.claims.explicit_code_gaps,
            )
            coverage_path = (
                artifact_dir(state.method_root, "04_evidence")
                / f"obligation_coverage_v2{version_suffix}.json"
            )
            coverage_path.write_text(
                json.dumps(
                    coverage.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        compiler_failures = validate_evidence_compiler_v3(compiler_v3, repo_snapshot)
        if compiler_failures:
            return StageToolResult(
                stage="evidence",
                status=StageStatus.BLOCKED,
                blocked_reason="evidence_compiler_v3_validation_failed",
                summary="; ".join(compiler_failures),
            )
        artifacts.update(
            write_compiler_v3_artifacts(
                artifact_dir(state.method_root, "04_evidence"),
                compiler_v3,
                suffix=version_suffix,
            )
        )
        if coverage_path is not None:
            artifacts["obligation_coverage_v2"] = str(coverage_path)
    if parent_path:
        artifacts["previous_evidence_snapshot_v2"] = str(parent_path)
    decision = "claims_verified" if verification.hard_gate_passed else "claims_need_caveats_or_more_evidence"
    return StageToolResult(
        stage="evidence",
        status=StageStatus.SUCCESS,
        artifacts=artifacts,
        summary="Froze verified evidence into MethodEvidence, claim maps, and claim verification report.",
        decisions=[
            AgentDecision(
                node="claim_verifier",
                decision=decision,
                rationale="; ".join(verification.recommended_actions),
                artifact_keys=[
                    "claim_verification", "evidence_snapshot_v2", "atomic_claims_v2",
                    *(list((
                        "evidence_packets_v3",
                        "code_facts_v1",
                        "atomic_claims_v3",
                        "evidence_profile_match",
                    )) if compiler_v3 else []),
                    "claims", "evidence",
                ],
            )
        ],
        metrics={
            "checked_claims": verification.checked_claims,
            "supported_claims": verification.supported_claims,
            "partial_claims": verification.partial_claims,
            "unsupported_claims": verification.unsupported_claims,
            "compiled_v3_facts": len(compiler_v3.facts.facts) if compiler_v3 else 0,
            "compiled_v3_claims": len(compiler_v3.claims.claims) if compiler_v3 else 0,
            "compiled_v3_profile_id": compiler_v3.profile_id if compiler_v3 else "",
        },
    )


def run_grounding(state: AgenticRunState) -> StageToolResult:
    method_evidence = MethodEvidence.model_validate(_read_json(method_output(state.method_root, "evidence")))
    claim_map = ClaimEvidenceMap.model_validate(_read_json(method_output(state.method_root, "claims")))
    paths = write_phase4_artifacts(
        method_root=state.method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=_llm_config(state),
    )
    return StageToolResult(
        stage="grounding",
        status=StageStatus.SUCCESS,
        artifacts=_existing_paths(paths),
        summary="Grounded equations, symbols, and authoring context.",
    )


def _llm_config(state: AgenticRunState):
    return load_llm_config_from_env(provider=state.llm_provider, model=state.llm_model)


def _existing_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {name: str(path) for name, path in paths.items() if path.exists()}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
