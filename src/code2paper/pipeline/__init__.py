"""Pipeline stage wrappers for Phase 1-4 orchestration."""

from code2paper.pipeline.orchestrator import run_orchestrator
from code2paper.pipeline.stage1_code_intake import run_stage1_code_intake
from code2paper.pipeline.stage2_code_analyze import run_stage2_code_analyze
from code2paper.pipeline.stage3_method_evidence import run_stage3_method_evidence
from code2paper.pipeline.stage4_author import run_stage4_author

__all__ = [
    "run_orchestrator",
    "run_stage1_code_intake",
    "run_stage2_code_analyze",
    "run_stage3_method_evidence",
    "run_stage4_author",
]
