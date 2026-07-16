from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.claim_verifier import build_claim_verification_report, write_claim_verification_report
from code2paper.agentic.contracts import AgentDecision, AgenticRunState, StageStatus, StageToolResult
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
    artifacts = _existing_paths(paths)
    artifacts["claim_verification"] = str(verification_path)
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
                artifact_keys=["claim_verification", "claims", "evidence"],
            )
        ],
        metrics={
            "checked_claims": verification.checked_claims,
            "supported_claims": verification.supported_claims,
            "partial_claims": verification.partial_claims,
            "unsupported_claims": verification.unsupported_claims,
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
