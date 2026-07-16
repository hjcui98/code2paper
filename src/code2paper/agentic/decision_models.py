from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CoverageCriticProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: str
    rationale: str = ""
    recommended_next: str = ""
    recommended_paths: list[str] = Field(default_factory=list)
    recommended_symbols: list[str] = Field(default_factory=list)
    recommended_queries: list[str] = Field(default_factory=list)


class RevisionRouterProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: str
    rationale: str = ""
    blocked_reason: str = ""
    recommended_next: str = ""
    selected_stage: str = ""


class EvidenceSufficiencyProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: str
    rationale: str = ""
    recommended_next: str = ""
    focus_claim_ids: list[str] = Field(default_factory=list)


class AnalysisRepairRouterProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    decision: str
    rationale: str = ""
    recommended_next: str = ""


class AuthoringPlanSectionProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    heading: str = ""
    purpose: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    caveat_required: bool = False
    writing_instructions: list[str] = Field(default_factory=list)


class AuthoringPlanProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rationale: str = ""
    sections: list[AuthoringPlanSectionProposal] = Field(default_factory=list)
