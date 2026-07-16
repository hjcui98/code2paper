"""Section planning for Phase 5 method drafts."""

from __future__ import annotations

from dataclasses import dataclass

from code2paper.core.schemas import MethodEvidence


@dataclass(frozen=True)
class SectionPlan:
    key: str
    title: str


def plan_method_sections(method_evidence: MethodEvidence) -> list[SectionPlan]:
    """Choose a conservative method-section outline from MethodEvidence."""

    names = {stage.name.lower() for stage in method_evidence.stages}
    procedure_title = "Training Objective" if any("optimization" in name for name in names) else "Method Flow"
    return [
        SectionPlan("overview", "Overview"),
        SectionPlan("pipeline", "Method Framework"),
        SectionPlan("components", "Core Components"),
        SectionPlan("procedure", procedure_title),
        SectionPlan("notes", "Additional Implementation Context"),
    ]
