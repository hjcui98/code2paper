"""Section planning for Phase 4 method drafts."""

from __future__ import annotations

from dataclasses import dataclass

from code2paper.schemas import MethodEvidence


@dataclass(frozen=True)
class SectionPlan:
    key: str
    title: str


def plan_method_sections(method_evidence: MethodEvidence) -> list[SectionPlan]:
    """Choose a conservative method-section outline from MethodEvidence."""

    names = {stage.name.lower() for stage in method_evidence.stages}
    procedure_title = "Training Procedure" if any("optimization" in name for name in names) else "Method Procedure"
    return [
        SectionPlan("overview", "Overview"),
        SectionPlan("pipeline", "Evidence-Grounded Pipeline"),
        SectionPlan("components", "Core Components"),
        SectionPlan("procedure", procedure_title),
        SectionPlan("notes", "Implementation Notes and Configurable Behavior"),
    ]

