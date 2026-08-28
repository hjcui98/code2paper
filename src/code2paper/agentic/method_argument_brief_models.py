"""Method argument brief contracts (WP-A).

An argument brief is the deterministic compile target that replaces per-cluster
concept cards for live authoring rebuild.  Each brief carries full author wording,
clause-level licensing, closed evidence ids, and an optional mechanism draft slot
filled later by the Mechanism Planner (WP-C).

Final publication lexical tokens still originate only from Writer / Formalizer /
Editor / Rewrite; briefs are writing contracts, not candidate prose.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.method_argument_models import ReferenceMethodStatusV1
from code2paper.agentic.method_product_models import StoryNodeRoleV1


ClauseLicenseV1 = Literal[
    "positively_licensed",
    "partially_licensed",
    "unlicensed",
]

MechanismDraftStatusV1 = Literal[
    "not_required",
    "empty",
    "planner_filled",
    "planner_failed",
]

MechanismDraftAuthorityLaneV1 = Literal[
    "executable_hard",
    "formal_derivation",
    "expository_bridge",
]

ArgumentBriefGapKindV1 = Literal[
    "planner_failed",
    "planner_required",
    "empty_claim_closure",
]

FacetKindV1 = Literal[
    "mechanism",
    "motivation",
    "guarantee",
    "constraint",
    "interface",
    "formula",
]

FormulaExpectationV1 = Literal["required", "preferred", "none"]

FacetAlignmentStatusV1 = Literal[
    "entailed",
    "partial",
    "mismatch",
    "unresolved",
]

CandidateFacetProseModeV1 = Literal[
    "repository_statement",
    "author_specification",
    "mismatch_statement",
]

FacetReviewSeverityV1 = Literal["none", "minor", "major", "critical"]

FacetFieldStatusV1 = Literal["entailed", "partial", "mismatch", "unresolved"]

FacetFieldPolarityV1 = Literal[
    "positive",
    "negative",
    "threshold_lt_excludes",
    "threshold_lte_excludes",
    "threshold_gt_selects",
    "threshold_gte_selects",
    "conditional",
    "unknown",
]

PublicationFieldRenderPolicyV1 = Literal["required", "optional", "deferred"]


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


class _BriefModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorClauseLicenseV1(_BriefModel):
    clause_id: str
    text: str
    license: ClauseLicenseV1
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    missing_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    license_reason: str = ""

    @field_validator("clause_id", "text")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("clause id and text must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _closed_ids(self) -> "AuthorClauseLicenseV1":
        for name in (
            "bound_claim_ids",
            "bound_equation_ids",
            "bound_span_ids",
            "bound_target_ids",
            "missing_target_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"clause contains duplicate {name}")
        if self.license == "positively_licensed" and not (
            self.bound_claim_ids or self.bound_equation_ids
        ):
            raise ValueError(
                "positively licensed clauses require bound claim or equation ids"
            )
        if self.license == "partially_licensed" and not (
            self.bound_claim_ids or self.bound_target_ids or self.bound_equation_ids
        ):
            raise ValueError(
                "partially licensed clauses require bound claim, target, or equation ids"
            )
        if self.license == "unlicensed" and (
            self.bound_claim_ids
            or self.bound_equation_ids
            or self.bound_span_ids
            or self.bound_target_ids
        ):
            raise ValueError("unlicensed clauses must not carry bound evidence ids")
        return self


class FacetEvidenceExcerptV1(_BriefModel):
    """One exact repository excerpt carried by a facet alignment.

    The excerpt is deliberately a small, typed projection of an
    ``EvidenceSpanV3``.  It may be hydrated by the harness from a closed span
    index; an LLM is never trusted to invent its path, line range, or digest.
    """

    facet_id: str = ""
    span_id: str = ""
    path: str = ""
    symbol: str = ""
    line_start: int = 0
    line_end: int = 0
    exact_excerpt: str = ""
    excerpt_digest: str = ""
    file_digest: str = ""
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_atoms: tuple[str, ...] = Field(default_factory=tuple)
    equation_atoms: tuple[str, ...] = Field(default_factory=tuple)
    operation_atoms: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _closed_lists(self) -> "FacetEvidenceExcerptV1":
        for name in (
            "fact_ids",
            "equation_ids",
            "fact_atoms",
            "equation_atoms",
            "operation_atoms",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"facet evidence excerpt contains duplicate {name}")
        return self


class AuthorMechanismFacetV1(_BriefModel):
    """Smallest independently judgeable unit of an author mechanism claim."""

    facet_id: str
    clause_id: str
    exact_source_quote: str
    facet_kind: FacetKindV1
    brief_id: str = ""
    semantic_fields: dict[str, Any] = Field(default_factory=dict)
    formula_expectation: FormulaExpectationV1 = "none"
    search_terms: tuple[str, ...] = Field(default_factory=tuple)
    required: bool = False
    content_digest: str = ""

    @field_validator("facet_id", "clause_id", "exact_source_quote")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("facet identifiers and source quote must not be empty")
        return str(value).strip()

    @field_validator("search_terms")
    @classmethod
    def _clean_search_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _digest(self) -> "AuthorMechanismFacetV1":
        # Facet decomposition/alignment is a separate Candidate sidecar.  Its
        # references may be attached for convenience, but must not alter the
        # deterministic brief digest used by the Verified lane.
        payload = self.model_dump(
            mode="json",
            exclude={
                "content_digest",
                "facet_ids",
                "facet_alignment_ids",
                "facet_policy_ids",
                "facet_digest",
            },
        )
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class FacetEvidenceAlignmentV1(_BriefModel):
    """Harness-validated field-level evidence alignment proposal."""

    facet_id: str
    alignment_id: str = ""
    clause_id: str = ""
    status: FacetAlignmentStatusV1 = "unresolved"
    supported_fields: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
    # Field-level truth is additive to the aggregate status.  It preserves
    # evidence for a compound facet when one field is unresolved, while the
    # aggregate status remains fail-closed for Verified authorization.
    field_bindings: tuple["FacetFieldBindingV1", ...] = Field(default_factory=tuple)
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_excerpts: tuple[FacetEvidenceExcerptV1, ...] = Field(default_factory=tuple)
    search_terms: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str = ""
    evidence_digest: str = ""
    schema_failures: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("facet_id")
    @classmethod
    def _facet_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("facet alignment facet_id must not be empty")
        return str(value).strip()

    @field_validator(
        "supported_fields",
        "unsupported_fields",
        "bound_claim_ids",
        "bound_span_ids",
        "bound_equation_ids",
        "search_terms",
        "schema_failures",
    )
    @classmethod
    def _dedupe_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "FacetEvidenceAlignmentV1":
        if self.alignment_id.strip() == "":
            object.__setattr__(self, "alignment_id", f"alignment:{self.facet_id}")
        if not self.evidence_digest:
            evidence_payload = {
                "bound_claim_ids": list(self.bound_claim_ids),
                "bound_span_ids": list(self.bound_span_ids),
                "bound_equation_ids": list(self.bound_equation_ids),
                "exact_excerpts": [
                    item.model_dump(mode="json") for item in self.exact_excerpts
                ],
            }
            object.__setattr__(self, "evidence_digest", _digest(evidence_payload))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class FacetFieldBindingV1(_BriefModel):
    """Closed evidence result for one semantic field of an author facet.

    This is an observation/diagnostic contract.  It never grants Verified
    wording permission; that permission still comes from deterministic clause
    licensing and reverse validation.
    """

    field_name: str
    status: FacetFieldStatusV1 = "unresolved"
    polarity: FacetFieldPolarityV1 = "unknown"
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_excerpts: tuple[FacetEvidenceExcerptV1, ...] = Field(default_factory=tuple)
    active_path_conditions: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_reason: str = ""

    @field_validator("field_name")
    @classmethod
    def _field_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("facet field binding requires a field name")
        return str(value).strip()

    @field_validator(
        "bound_claim_ids",
        "bound_fact_ids",
        "bound_span_ids",
        "bound_equation_ids",
        "active_path_conditions",
    )
    @classmethod
    def _dedupe_field_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)


class PublicationFieldCandidateV1(_BriefModel):
    """Atomic, Writer-consumable projection of one aligned facet field.

    Aggregate facet status is retained for diagnostics, but publication
    planning consumes these atomic records.  A required candidate must carry
    a semantic atom and an exact authorized excerpt; otherwise it is demoted
    to ``optional``/``deferred`` rather than creating an impossible hard
    paragraph target.
    """

    schema_version: str = "1.0"
    candidate_id: str
    facet_id: str
    field_name: str
    semantic_atom: str
    authority_lane: str = "executable_hard"
    polarity: FacetFieldPolarityV1 = "unknown"
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    ownership_roles: tuple[str, ...] = Field(default_factory=tuple)
    render_policy: PublicationFieldRenderPolicyV1 = "deferred"
    defer_reason: str = ""
    content_digest: str = ""

    @field_validator(
        "candidate_id", "facet_id", "field_name", "semantic_atom",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("publication field candidate requires non-empty identity and semantic atom")
        return str(value).strip()

    @field_validator("authority_lane")
    @classmethod
    def _authority_lane_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("publication field candidate requires an authority lane")
        return str(value).strip()

    @field_validator(
        "conditions", "bound_claim_ids", "bound_fact_ids", "bound_span_ids",
        "bound_equation_ids", "exact_excerpts", "ownership_roles",
    )
    @classmethod
    def _dedupe_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _consistency_and_digest(self) -> "PublicationFieldCandidateV1":
        if self.render_policy == "required" and (
            not self.exact_excerpts
            or not (self.bound_claim_ids or self.bound_fact_ids or self.bound_span_ids or self.bound_equation_ids)
            or "unknown" in self.ownership_roles
            or "comparand" in self.ownership_roles
            or "evaluation" in self.ownership_roles
        ):
            raise ValueError("required publication field candidate is not consumable")
        if self.render_policy == "deferred" and not self.defer_reason.strip():
            raise ValueError("deferred publication field candidate requires a reason")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self

    @property
    def is_consumable(self) -> bool:
        return self.render_policy in {"required", "optional"} and not set(
            self.ownership_roles
        ).intersection({"unknown", "comparand", "evaluation"}) and bool(
            self.semantic_atom.strip()
            and self.authority_lane.strip()
            and self.exact_excerpts
            and (
                self.bound_claim_ids
                or self.bound_fact_ids
                or self.bound_span_ids
                or self.bound_equation_ids
            )
        )


class TypedFieldDeferredV1(_BriefModel):
    """Explicitly unresolved atomic field kept for research/review routing."""

    schema_version: str = "1.0"
    facet_id: str
    field_name: str
    unsupported_atom: str
    reason_code: str
    requested_search_terms: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("facet_id", "field_name", "unsupported_atom", "reason_code")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("typed deferred field requires non-empty fields")
        return str(value).strip()

    @field_validator("requested_search_terms")
    @classmethod
    def _dedupe_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _digest(self) -> "TypedFieldDeferredV1":
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class CandidateFacetPolicyV1(_BriefModel):
    """Deterministic Candidate/Verified policy for one author facet."""

    facet_id: str
    policy_id: str = ""
    alignment_id: str = ""
    clause_id: str = ""
    alignment_status: FacetAlignmentStatusV1 = "unresolved"
    prose_mode: CandidateFacetProseModeV1 = "author_specification"
    candidate_allowed: bool = True
    verified_directly_allowed: bool = False
    review_severity: FacetReviewSeverityV1 = "major"
    supported_fields: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
    field_bindings: tuple[FacetFieldBindingV1, ...] = Field(default_factory=tuple)
    bound_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_digest: str = ""
    rationale: str = ""
    schema_failures: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("facet_id")
    @classmethod
    def _facet_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("facet policy facet_id must not be empty")
        return str(value).strip()

    @field_validator(
        "supported_fields",
        "unsupported_fields",
        "bound_claim_ids",
        "bound_span_ids",
        "bound_equation_ids",
        "schema_failures",
    )
    @classmethod
    def _dedupe_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _policy_consistency_and_digest(self) -> "CandidateFacetPolicyV1":
        if not self.policy_id.strip():
            object.__setattr__(self, "policy_id", f"policy:{self.facet_id}")
        if self.verified_directly_allowed and (
            self.alignment_status != "entailed"
            or self.prose_mode != "repository_statement"
        ):
            # This is a fail-closed normalization, not an authorization path:
            # only the deterministic AuthorClauseLicenseV1 merge can set this
            # flag back to true.
            object.__setattr__(self, "verified_directly_allowed", False)
        # Facet decomposition/alignment is a separate Candidate sidecar.  Its
        # references may be attached for convenience, but must not alter the
        # deterministic brief digest used by the Verified lane.
        payload = self.model_dump(
            mode="json",
            exclude={
                "content_digest",
                "facet_ids",
                "facet_alignment_ids",
                "facet_policy_ids",
                "facet_digest",
            },
        )
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class MechanismAuthoringPacketV1(_BriefModel):
    """Writer-facing packet preserving facet policy and exact evidence."""

    packet_id: str = ""
    story_node_id: str = ""
    brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    facets: tuple[AuthorMechanismFacetV1, ...] = Field(default_factory=tuple)
    facet_policies: tuple[CandidateFacetPolicyV1, ...] = Field(default_factory=tuple)
    publication_field_candidates: tuple[PublicationFieldCandidateV1, ...] = Field(default_factory=tuple)
    typed_field_deferred: tuple[TypedFieldDeferredV1, ...] = Field(default_factory=tuple)
    exact_evidence_excerpts: tuple[FacetEvidenceExcerptV1, ...] = Field(
        default_factory=tuple
    )
    formula_packages: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    applicable_conditions: tuple[str, ...] = Field(default_factory=tuple)
    interfaces: tuple[str, ...] = Field(default_factory=tuple)
    required_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    search_terms_by_facet_id: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    organization_seed: str = ""
    content_digest: str = ""

    @field_validator(
        "brief_ids",
        "applicable_conditions",
        "interfaces",
        "required_facet_ids",
    )
    @classmethod
    def _clean_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "MechanismAuthoringPacketV1":
        facet_ids = tuple(item.facet_id for item in self.facets)
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("authoring packet contains duplicate facet ids")
        policy_ids = tuple(item.policy_id for item in self.facet_policies)
        if len(policy_ids) != len(set(policy_ids)):
            raise ValueError("authoring packet contains duplicate policy ids")
        known_facets = set(facet_ids)
        if set(self.required_facet_ids) - known_facets:
            raise ValueError("authoring packet requires an unknown facet")
        if {item.facet_id for item in self.facet_policies} - known_facets:
            raise ValueError("authoring packet policy references an unknown facet")
        if set(self.search_terms_by_facet_id) - known_facets:
            raise ValueError("authoring packet search terms reference an unknown facet")
        candidate_ids = [item.candidate_id for item in self.publication_field_candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("authoring packet contains duplicate publication field candidates")
        if any(item.facet_id not in known_facets for item in self.publication_field_candidates):
            raise ValueError("authoring packet field candidate references an unknown facet")
        if any(item.facet_id not in known_facets for item in self.typed_field_deferred):
            raise ValueError("authoring packet deferred field references an unknown facet")
        if self.brief_ids:
            unknown_briefs = {
                item.brief_id for item in self.facets if item.brief_id
            } - set(self.brief_ids)
            if unknown_briefs:
                raise ValueError("authoring packet facet references an unknown brief")
        if any(
            item.facet_id and item.facet_id not in known_facets
            for item in self.exact_evidence_excerpts
        ):
            raise ValueError("authoring packet excerpt references an unknown facet")
        if not self.packet_id.strip():
            object.__setattr__(
                self,
                "packet_id",
                "packet:" + _digest({
                    "story_node_id": self.story_node_id,
                    "facet_ids": list(facet_ids),
                })[7:23],
            )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        # Keep the set digest compatible with pre-WP-L deterministic briefs.
        for brief_payload in payload.get("briefs", ()):
            if isinstance(brief_payload, dict):
                for key in (
                    "facet_ids",
                    "facet_alignment_ids",
                    "facet_policy_ids",
                    "facet_digest",
                ):
                    brief_payload.pop(key, None)
        object.__setattr__(self, "content_digest", _digest(payload))
        return self

    @property
    def policies(self) -> tuple[CandidateFacetPolicyV1, ...]:
        return self.facet_policies

    @property
    def evidence_excerpts(self) -> tuple[FacetEvidenceExcerptV1, ...]:
        return self.exact_evidence_excerpts

    @property
    def planner_organization_seed(self) -> str:
        return self.organization_seed


class MechanismDraftV1(_BriefModel):
    draft_id: str
    brief_id: str
    text: str = ""
    cited_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    cited_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    covered_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_lane: MechanismDraftAuthorityLaneV1 = "executable_hard"
    caveat: str = ""
    status: MechanismDraftStatusV1 = "empty"

    @field_validator("draft_id", "brief_id")
    @classmethod
    def _ids_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("mechanism draft ids must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _status_consistency(self) -> "MechanismDraftV1":
        for name in ("cited_claim_ids", "cited_equation_ids", "covered_facet_ids"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"mechanism draft contains duplicate {name}")
        if self.status == "not_required" and self.text.strip():
            raise ValueError("not_required mechanism drafts must not carry text")
        if self.status in {"planner_filled", "planner_failed"} and not self.text.strip():
            raise ValueError("planner mechanism drafts require non-empty text")
        return self


class MethodArgumentBriefV1(_BriefModel):
    brief_id: str
    story_node_id: str
    intended_role: StoryNodeRoleV1 = "algorithm_step"
    obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    author_statement: str
    completeness_statuses: tuple[ReferenceMethodStatusV1, ...] = Field(default_factory=tuple)
    clauses: tuple[AuthorClauseLicenseV1, ...] = Field(default_factory=tuple)
    licensed_wording: str = ""
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    span_ids: tuple[str, ...] = Field(default_factory=tuple)
    mechanism_draft: MechanismDraftV1
    may_enter_verified: bool = False
    requires_caveat: bool = False
    facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    facet_alignment_ids: tuple[str, ...] = Field(default_factory=tuple)
    facet_policy_ids: tuple[str, ...] = Field(default_factory=tuple)
    facet_digest: str = ""
    content_digest: str = ""

    @field_validator("brief_id", "story_node_id", "author_statement")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("brief identifiers and author statement must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _closure(self) -> "MethodArgumentBriefV1":
        object.__setattr__(self, "obligation_ids", _clean_tuple(self.obligation_ids))
        for name in (
            "claim_ids",
            "equation_ids",
            "configuration_ids",
            "span_ids",
            "facet_ids",
            "facet_alignment_ids",
            "facet_policy_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"brief contains duplicate {name}")
        if self.mechanism_draft.brief_id != self.brief_id:
            raise ValueError("mechanism draft brief_id must match brief")
        licensed_parts = [
            clause.text
            for clause in self.clauses
            if clause.license == "positively_licensed"
        ]
        expected_wording = " ".join(licensed_parts).strip()
        if self.licensed_wording != expected_wording:
            raise ValueError("licensed_wording must equal positively licensed clause text")
        if any(
            clause.license in {"unlicensed", "partially_licensed"}
            for clause in self.clauses
        ) and self.may_enter_verified:
            raise ValueError("briefs with unlicensed or partial clauses cannot enter verified")
        if self.licensed_wording == self.author_statement and any(
            clause.license != "positively_licensed" for clause in self.clauses
        ):
            raise ValueError("licensed_wording cannot mirror full author statement when clauses differ")
        if not self.facet_digest and (
            self.facet_ids or self.facet_alignment_ids or self.facet_policy_ids
        ):
            object.__setattr__(
                self,
                "facet_digest",
                _digest({
                    "facet_ids": list(self.facet_ids),
                    "facet_alignment_ids": list(self.facet_alignment_ids),
                    "facet_policy_ids": list(self.facet_policy_ids),
                }),
            )
        # Facet decomposition/alignment is a separate Candidate sidecar.  Its
        # references may be attached for convenience, but must not alter the
        # deterministic brief digest used by the Verified lane.
        payload = self.model_dump(
            mode="json",
            exclude={
                "content_digest",
                "facet_ids",
                "facet_alignment_ids",
                "facet_policy_ids",
                "facet_digest",
            },
        )
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class ArgumentBriefGapV1(_BriefModel):
    gap_kind: ArgumentBriefGapKindV1
    brief_id: str = ""
    obligation_id: str = ""
    message: str

    @field_validator("message")
    @classmethod
    def _message_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("argument brief gap message must not be empty")
        return value.strip()


class MethodArgumentBriefSetV1(_BriefModel):
    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    claims_digest: str = ""
    completeness_digest: str = ""
    coverage_digest: str = ""
    intent_digest: str = ""
    briefs: tuple[MethodArgumentBriefV1, ...] = Field(default_factory=tuple)
    planner_used: bool = False
    gaps: tuple[ArgumentBriefGapV1, ...] = Field(default_factory=tuple)
    planner_call_traces: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodArgumentBriefSetV1":
        brief_ids = [brief.brief_id for brief in self.briefs]
        if len(brief_ids) != len(set(brief_ids)):
            raise ValueError("argument brief set contains duplicate brief ids")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        # Keep the set digest compatible with pre-WP-L deterministic briefs.
        for brief_payload in payload.get("briefs", ()):
            if isinstance(brief_payload, dict):
                for key in (
                    "facet_ids",
                    "facet_alignment_ids",
                    "facet_policy_ids",
                    "facet_digest",
                ):
                    brief_payload.pop(key, None)
        object.__setattr__(self, "content_digest", _digest(payload))
        return self
