from __future__ import annotations

from code2paper.agentic.legacy_authoring_stage_tool import run_authoring as _run_authoring
from code2paper.agentic.legacy_evidence_stage_tools import (
    run_evidence as _run_evidence,
    run_grounding as _run_grounding,
)
from code2paper.agentic.legacy_late_stage_tools import (
    run_finalize as _run_finalize,
    run_rendering as _run_rendering,
    run_validation as _run_validation,
)
from code2paper.agentic.legacy_intake_stage_tool import run_intake as _run_intake
from code2paper.agentic.legacy_pre_evidence_stage_tools import (
    run_analysis as _run_analysis,
    run_input_resolution_stage as _run_input_resolution,
)
from code2paper.agentic.tools import build_stage_tool_registry


def build_legacy_stage_tool_registry():
    """Expose existing deterministic stages through the agentic tool contract."""

    return build_stage_tool_registry(
        {
            "input_resolution": _run_input_resolution,
            "intake": _run_intake,
            "analysis": _run_analysis,
            "evidence": _run_evidence,
            "grounding": _run_grounding,
            "authoring": _run_authoring,
            "validation": _run_validation,
            "rendering": _run_rendering,
            "finalize": _run_finalize,
        }
    )
