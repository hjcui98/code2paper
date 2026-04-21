"""Pipeline stage 3: method evidence freeze."""

from __future__ import annotations

from pathlib import Path

from code2paper.method_evidence import write_phase3_artifacts
from code2paper.schemas import CodeAlignmentIR, CodeMethodAnalysis, LLMConfig, MethodEvidence, RawEvidencePack


def run_stage3_method_evidence(
    *,
    method_root: Path,
    paper_root: Path,
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None = None,
    code_facts: dict | None = None,
    llm_config: LLMConfig | None = None,
) -> tuple[MethodEvidence, dict[str, Path]]:
    return write_phase3_artifacts(
        method_root=method_root,
        paper_root=paper_root,
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        code_facts=code_facts,
        llm_config=llm_config,
    )
