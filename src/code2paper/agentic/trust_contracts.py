from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_product_models import AuthorStoryNodeV1


class TrustModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectedClaim(TrustModel):
    claim_id: str
    claim_text: str
    support_status: Literal["supported", "partial"]
    direct_evidence_ids: list[str] = Field(default_factory=list)
    relation_evidence_ids: list[str] = Field(default_factory=list)
    supported_fragment: str
    required_qualifiers: list[str] = Field(default_factory=list)
    allowed_wording_boundary: str
    source: str = ""
    writing_role: Literal["method_positive", "method_conditional", "audit_only"] = "method_positive"
    inference_level: Literal["E0", "E1", "E2", "E3"] = "E0"
    parent_claim_ids: list[str] = Field(default_factory=list)
    input_digest: str

    @model_validator(mode="after")
    def _direct_evidence_required(self) -> "ProjectedClaim":
        if not self.direct_evidence_ids:
            raise ValueError("projected claims require direct_evidence_ids")
        if self.support_status == "partial" and not self.required_qualifiers:
            raise ValueError("partial projected claims require qualifiers")
        return self


class AuthorAttestedFragment(TrustModel):
    """A bounded author-owned statement that is not repository evidence.

    Author-attested prose may be rendered as a caveated statement after an
    owning callback has validated it, but it must never acquire executable
    evidence ids or be treated as a supported repository claim.
    """

    fragment_id: str
    supported_fragment: str
    allowed_wording_boundary: str
    source_ref: str
    input_digest: str

    @model_validator(mode="after")
    def _nonempty(self) -> "AuthorAttestedFragment":
        if not all((
            self.fragment_id.strip(),
            self.supported_fragment.strip(),
            self.allowed_wording_boundary.strip(),
            self.source_ref.strip(),
            self.input_digest.startswith("sha256:"),
        )):
            raise ValueError("author-attested fragment binding fields must not be empty")
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
    author_attested_fragments: list[AuthorAttestedFragment] = Field(default_factory=list)
    forbidden_claims: list[ForbiddenClaim] = Field(default_factory=list)
    stage_packets: list[dict[str, Any]] = Field(default_factory=list)
    safe_equations: list[dict[str, Any]] = Field(default_factory=list)
    safe_numeric_facts: list[dict[str, Any]] = Field(default_factory=list)
    safe_aliases: list[dict[str, Any]] = Field(default_factory=list)
    safe_intent_spine: list[str] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)
    dropped_positive_fields: list[str] = Field(default_factory=list)
    source_digests: dict[str, str] = Field(default_factory=dict)
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    evidence_snapshot_id: str = ""
    evidence_snapshot_digest: str = ""
    projection_digest: str
    hard_gate_passed: bool = True
    # Author-intent-first projection fields (reorientation C).  The author
    # story spine is the organization authority; the lane-aware facts below
    # separate repository-verified content from partial, mismatch,
    # author-intent-unverified, external-pending and formalization content so
    # the Writer/Architect never mistake author intent for repository fact.
    author_story_spine: list[AuthorStoryNodeV1] = Field(default_factory=list)
    repository_verified_facts: list[dict[str, Any]] = Field(default_factory=list)
    repository_partial_facts: list[dict[str, Any]] = Field(default_factory=list)
    repository_mismatches: list[dict[str, Any]] = Field(default_factory=list)
    author_intent_unverified_points: list[dict[str, Any]] = Field(default_factory=list)
    external_pending_points: list[dict[str, Any]] = Field(default_factory=list)
    formalization_needed_points: list[dict[str, Any]] = Field(default_factory=list)
    review_questions: list[dict[str, Any]] = Field(default_factory=list)
    writing_policy: list[str] = Field(default_factory=list)
    projection_trace: list[dict[str, Any]] = Field(default_factory=list)


class FinalTextUnit(TrustModel):
    unit_id: str
    kind: Literal["heading", "sentence", "list_item", "formula", "caption", "discourse", "expository_bridge"]
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
    # Closed conceptual cards selected before the evidence gate.  These IDs
    # are navigation metadata only: they can expand through the digest-bound
    # proposition sidecar to existing projection claims, but never authorize
    # evidence or a verdict by themselves.
    candidate_method_proposition_ids: list[str] = Field(default_factory=list)
    candidate_author_attested_ids: list[str] = Field(default_factory=list)
    # Candidate-only narrative points come from the author-intent,
    # repository-partial, mismatch, literature-pending, or formalization
    # lanes of ``AuthoringInputProjection``.  They are deliberately separate
    # from ``candidate_author_attested_ids``: a narrative point may authorize
    # a visibly caveated candidate sentence, but it never becomes repository
    # evidence and can never enter the verified Method.
    candidate_narrative_ids: list[str] = Field(default_factory=list)
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
    matched_method_proposition_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    relation_evidence_ids: list[str] = Field(default_factory=list)
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
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    evidence_snapshot_id: str = ""
    evidence_snapshot_digest: str = ""
    checked_factual_claims: int = 0
    supported_claims: int = 0
    caveated_claims: int = 0
    unsupported_claims: int = 0
    unverified_claims: int = 0
    semantic_verifier_calls: int = 0
    verification_mode: Literal["lexical_only", "semantic"] = "lexical_only"
    verdicts: list[TextClaimEvidenceVerdict] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class TextTraceEntry(TrustModel):
    trace_id: str
    atomic_claim_id: str
    final_text_span_digest: str
    claim_digest: str
    verdict_status: Literal["supported", "caveated"]
    direct_evidence_ids: list[str] = Field(default_factory=list)
    relation_evidence_ids: list[str] = Field(default_factory=list)
    projection_claim_ids: list[str] = Field(default_factory=list)
    validator_report_ref: str
    projection_ref: str


class FinalTextTrace(TrustModel):
    mode: str = "agentic-final-text-trace-v1"
    input_text_digest: str
    projection_digest: str
    validation_report_digest: str
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    evidence_snapshot_id: str = ""
    evidence_snapshot_digest: str = ""
    entries: list[TextTraceEntry] = Field(default_factory=list)
    hard_gate_passed: bool
    failures: list[str] = Field(default_factory=list)
