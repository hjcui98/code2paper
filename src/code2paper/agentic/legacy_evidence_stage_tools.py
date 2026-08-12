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
    EvidenceCompilerV3Result,
    load_atomic_claims_v3,
    load_code_facts_v1,
    load_evidence_packets_v3,
    validate_evidence_compiler_v3,
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
    # D2 authority cutover: the legacy stage may consume the canonical
    # generic research chain, but it must never synthesize facts or claims
    # from a project profile.  The V3 research owner has already persisted
    # these artifacts before this compatibility stage runs.
    compiler_v3 = _load_generic_research_chain(state, repo_snapshot)
    if compiler_v3 is not None:
        compiler_failures = validate_evidence_compiler_v3(compiler_v3, repo_snapshot)
        if compiler_failures:
            return StageToolResult(
                stage="evidence",
                status=StageStatus.BLOCKED,
                blocked_reason="evidence_compiler_v3_validation_failed",
                summary="; ".join(compiler_failures),
            )
        artifacts.update(
            {
                key: state.artifacts[key]
                for key in (
                    "evidence_packets_v3",
                    "code_facts_v1",
                    "atomic_claims_v3",
                    "generic_research_compilation_manifest",
                )
                if state.artifacts.get(key)
            }
        )
        canonical_coverage = state.artifacts.get("obligation_coverage_v2", "")
        if canonical_coverage and Path(canonical_coverage).is_file():
            artifacts["obligation_coverage_v2"] = canonical_coverage
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
                        "generic_research_compilation_manifest",
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
            "compiled_v3_profile_id": "",
        },
    )


def _load_generic_research_chain(
    state: AgenticRunState,
    repo_snapshot,
) -> EvidenceCompilerV3Result | None:
    """Load only the V3 research owner's persisted generic chain.

    Absence is not repaired here: the owning research agent must produce or
    repair the chain.  This prevents the legacy evidence stage from silently
    replacing it with profile-authored facts.
    """

    paths = {
        key: state.artifacts.get(key, "")
        for key in (
            "evidence_packets_v3",
            "code_facts_v1",
            "atomic_claims_v3",
        )
    }
    if any(not value or not Path(value).is_file() for value in paths.values()):
        return None
    try:
        result = EvidenceCompilerV3Result(
            packets=load_evidence_packets_v3(paths["evidence_packets_v3"]),
            facts=load_code_facts_v1(paths["code_facts_v1"]),
            claims=load_atomic_claims_v3(paths["atomic_claims_v3"]),
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if validate_evidence_compiler_v3(result, repo_snapshot):
        return None
    producer_versions = {
        result.packets.producer_version,
        result.facts.producer_version,
        result.claims.producer_version,
    }
    if not all("generic" in value.lower() for value in producer_versions):
        return None
    return result


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
