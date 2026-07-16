from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrustModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectedClaim(TrustModel):
    claim_id: str
    claim_text: str
    support_status: Literal["supported", "partial"]
    direct_evidence_ids: list[str] = Field(default_factory=list)
    supported_fragment: str
    required_qualifiers: list[str] = Field(default_factory=list)
    allowed_wording_boundary: str
    source: str = ""
    input_digest: str

    @model_validator(mode="after")
    def _direct_evidence_required(self) -> "ProjectedClaim":
        if not self.direct_evidence_ids:
            raise ValueError("projected claims require direct_evidence_ids")
        if self.support_status == "partial" and not self.required_qualifiers:
            raise ValueError("partial projected claims require qualifiers")
        return self


class ForbiddenClaim(TrustModel):
    claim_id: str
    reason: str
    source: str = ""
    repair_metadata: dict[str, Any] = Field(default_factory=dict)


class AuthoringInputProjection(TrustModel):
    mode: str = "agentic-authoring-input-projection-v1"
    project_id: str
    method_name: str
    author_goal: str
    implementation_scope: str
    projected_claims: list[ProjectedClaim] = Field(default_factory=list)
    forbidden_claims: list[ForbiddenClaim] = Field(default_factory=list)
    stage_packets: list[dict[str, Any]] = Field(default_factory=list)
    safe_equations: list[dict[str, Any]] = Field(default_factory=list)
    safe_numeric_facts: list[dict[str, Any]] = Field(default_factory=list)
    safe_aliases: list[dict[str, Any]] = Field(default_factory=list)
    safe_intent_spine: list[str] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)
    dropped_positive_fields: list[str] = Field(default_factory=list)
    source_digests: dict[str, str] = Field(default_factory=dict)
    projection_digest: str
    hard_gate_passed: bool = True


class FinalTextUnit(TrustModel):
    unit_id: str
    kind: Literal["heading", "sentence", "list_item", "formula", "caption", "discourse"]
    text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    factual: bool
    high_risk_markers: list[str] = Field(default_factory=list)
    span_digest: str


class FinalAtomicClaim(TrustModel):
    atomic_claim_id: str
    unit_id: str
    text: str
    normalized_text: str
    line_start: int
    line_end: int
    char_start: int
    char_end: int
    candidate_projection_claim_ids: list[str] = Field(default_factory=list)
    candidate_direct_evidence_ids: list[str] = Field(default_factory=list)
    high_risk_markers: list[str] = Field(default_factory=list)
    claim_digest: str


class FinalTextClaims(TrustModel):
    mode: str = "agentic-final-text-claims-v1"
    input_text_digest: str
    units: list[FinalTextUnit] = Field(default_factory=list)
    atomic_claims: list[FinalAtomicClaim] = Field(default_factory=list)
    deterministic_completeness_passed: bool = True
    completeness_failures: list[str] = Field(default_factory=list)


class TextClaimEvidenceVerdict(TrustModel):
    atomic_claim_id: str
    status: Literal["supported", "caveated", "unsupported", "unverified"]
    matched_projection_claim_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    supported_fragment: str = ""
    unsupported_fragment: str = ""
    required_qualifiers: list[str] = Field(default_factory=list)
    deterministic_failures: list[str] = Field(default_factory=list)
    model_verdict: str = ""
    rationale: str = ""
    repair_action: str = ""


class TextEvidenceValidationReport(TrustModel):
    mode: str = "agentic-text-evidence-validation-v1"
    status: Literal["passed", "failed", "blocked"]
    input_text_digest: str
    projection_digest: str
    checked_factual_claims: int = 0
    supported_claims: int = 0
    caveated_claims: int = 0
    unsupported_claims: int = 0
    unverified_claims: int = 0
    semantic_verifier_calls: int = 0
    verdicts: list[TextClaimEvidenceVerdict] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class TextTraceEntry(TrustModel):
    trace_id: str
    atomic_claim_id: str
    final_text_span_digest: str
    claim_digest: str
    verdict_status: Literal["supported", "caveated"]
    direct_evidence_ids: list[str] = Field(default_factory=list)
    projection_claim_ids: list[str] = Field(default_factory=list)
    validator_report_ref: str
    projection_ref: str


class FinalTextTrace(TrustModel):
    mode: str = "agentic-final-text-trace-v1"
    input_text_digest: str
    projection_digest: str
    validation_report_digest: str
    entries: list[TextTraceEntry] = Field(default_factory=list)
    hard_gate_passed: bool
    failures: list[str] = Field(default_factory=list)
