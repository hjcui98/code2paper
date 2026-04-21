"""Pipeline stage 4: method authoring."""

from __future__ import annotations

from pathlib import Path

from code2paper.phase4_authoring import write_phase4_artifacts
from code2paper.schemas import ClaimEvidenceMap, CodeAlignmentIR, LLMConfig, MethodEvidence


def run_stage4_author(
    *,
    method_root: Path,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    llm_config: LLMConfig,
    alignment: CodeAlignmentIR | None = None,
    preflight_blocked_reason: str = "",
) -> tuple[str | None, str | None, dict[str, Path]]:
    return write_phase4_artifacts(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
        alignment=alignment,
        preflight_blocked_reason=preflight_blocked_reason,
    )
