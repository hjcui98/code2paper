"""Pipeline orchestrator helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stage1_code_intake import run_stage1_code_intake
from code2paper.pipeline.stage2_code_analyze import run_stage2_code_analyze
from code2paper.pipeline.stage3_method_evidence import run_stage3_method_evidence
from code2paper.pipeline.stage4_author import run_stage4_author
from code2paper.schemas import ClaimEvidenceMap, CodeMethodAnalysis, LLMProvider


@dataclass(frozen=True)
class OrchestratorArgs:
    project_root: Path
    out_root: Path
    author_markers_path: str | None = None
    project_id: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


def run_orchestrator(args: OrchestratorArgs) -> dict[str, Path]:
    paper_root = args.out_root / "paper"
    method_root = paper_root / "method"
    if not args.author_markers_path:
        raise ValueError("story-first orchestrator requires author_markers_path")
    llm_config = load_llm_config_from_env(
        provider=args.llm_provider if args.llm_provider in {provider.value for provider in LLMProvider} else None,
        model=args.llm_model,
    )
    raw_pack, _comment_index, _raw_context_index, _context_map, phase1_paths = run_stage1_code_intake(
        project_root=args.project_root,
        method_root=method_root,
        author_markers_path=args.author_markers_path,
        project_id=args.project_id,
        llm_config=llm_config,
    )
    alignment, phase2_paths = run_stage2_code_analyze(
        project_root=args.project_root,
        method_root=method_root,
        author_markers_path=args.author_markers_path,
        project_id=args.project_id,
        llm_config=llm_config,
    )
    code_method_analysis = CodeMethodAnalysis.model_validate(
        json.loads((method_root / "code_method_analysis.json").read_text(encoding="utf-8"))
    )
    code_facts_path = method_root / "code_facts.json"
    code_facts = json.loads(code_facts_path.read_text(encoding="utf-8")) if code_facts_path.exists() else None
    method_evidence, phase3_paths = run_stage3_method_evidence(
        method_root=method_root,
        paper_root=paper_root,
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        code_facts=code_facts,
        llm_config=llm_config,
    )
    claim_map = ClaimEvidenceMap.model_validate(
        json.loads((paper_root / "claim_evidence_map.json").read_text(encoding="utf-8"))
    )
    _markdown, _tex, phase4_paths = run_stage4_author(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
        alignment=alignment,
    )
    return {**phase1_paths, **phase2_paths, **phase3_paths, **phase4_paths}
