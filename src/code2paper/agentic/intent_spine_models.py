"""Versioned contracts for intent-first Method authoring.

These models separate narrative organization authority from executable
evidence ownership.  Historical V3/V2 artifacts remain readable; new
artifacts use the explicit versions defined here.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean_tuple(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


class _SpineModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


INTERNAL_HEADING_RE = re.compile(
    r"(?i)^\s*(?:sym:|mech_(?:sym:)?)[a-z0-9:_-]*\s*$"
)


def heading_is_internal_identifier(heading: str) -> bool:
    text = str(heading or "").strip()
    if not text:
        return True
    if INTERNAL_HEADING_RE.match(text):
        return True
    if re.fullmatch(r"[0-9a-f]{8,}", text, flags=re.IGNORECASE):
        return True
    return False


BindingStatusV1 = Literal["exact", "partial", "mismatch", "unresolved"]
AtomAuthorityExpectationV1 = Literal[
    "repository_implementation",
    "repository_compositional",
    "author_rationale",
    "author_specification",
]
SearchStatusV1 = Literal["searching", "terminal"]
EvidenceDispositionV1 = Literal[
    "repository_exact",
    "repository_partial",
    "author_spec_only",
    "mismatch",
    "bounded_not_found",
    "out_of_scope",
]
CandidateSurfaceStatusV1 = Literal["complete", "incomplete", "not_applicable"]
RepositoryProofStatusV1 = Literal[
    "exact", "partial", "mismatch", "unavailable", "not_applicable"
]
FormulaExpectationV2 = Literal["required", "preferred", "none"]
FormulaWorthinessV1 = Literal[
    "display", "inline", "prose_or_algorithm", "rejected"
]
ClaimVerificationStatusV2 = Literal[
    "exact_verified", "semantic_verified", "unresolved", "rejected"
]
SectionOrderSourceV1 = Literal["author_intent", "accepted_author_plan"]


class IntentNarrativeParagraphV4(_SpineModel):
    paragraph_id: str
    section_id: str
    role: str = "step_sequence"
    heading_intent: str = ""
    reader_goal: str = ""
    ordered_story_node_ids: tuple[str, ...] = ()
    ordered_argument_unit_ids: tuple[str, ...] = ()
    intent_atom_ids: tuple[str, ...] = ()
    mechanism_ids: tuple[str, ...] = ()
    mechanism_id: str = ""
    required_detail_ids: tuple[str, ...] = ()
    optional_detail_ids: tuple[str, ...] = ()
    required_intent_atom_ids: tuple[str, ...] = ()
    required_author_surface_ids: tuple[str, ...] = ()
    required_repository_proposition_ids: tuple[str, ...] = ()
    formula_obligation_ids: tuple[str, ...] = ()
    authority_surface: str = "author_specification"
    witness_contract: dict[str, Any] = Field(default_factory=dict)
    transition_from: str = ""
    transition_to: str = ""
    content_digest: str = ""

    @field_validator("paragraph_id", "section_id")
    @classmethod
    def _required_ids(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("paragraph and section identifiers must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _normalize(self) -> "IntentNarrativeParagraphV4":
        object.__setattr__(self, "ordered_story_node_ids", _clean_tuple(self.ordered_story_node_ids))
        object.__setattr__(self, "ordered_argument_unit_ids", _clean_tuple(self.ordered_argument_unit_ids))
        object.__setattr__(self, "intent_atom_ids", _clean_tuple(self.intent_atom_ids))
        object.__setattr__(self, "mechanism_ids", _clean_tuple(self.mechanism_ids))
        object.__setattr__(self, "required_detail_ids", _clean_tuple(self.required_detail_ids))
        object.__setattr__(self, "optional_detail_ids", _clean_tuple(self.optional_detail_ids))
        object.__setattr__(self, "required_intent_atom_ids", _clean_tuple(self.required_intent_atom_ids))
        object.__setattr__(self, "required_author_surface_ids", _clean_tuple(self.required_author_surface_ids))
        object.__setattr__(
            self,
            "required_repository_proposition_ids",
            _clean_tuple(self.required_repository_proposition_ids),
        )
        object.__setattr__(self, "formula_obligation_ids", _clean_tuple(self.formula_obligation_ids))
        if not self.mechanism_id and self.mechanism_ids:
            object.__setattr__(self, "mechanism_id", self.mechanism_ids[0])
        if self.mechanism_id and self.mechanism_id not in self.mechanism_ids:
            object.__setattr__(
                self, "mechanism_ids", (self.mechanism_id, *self.mechanism_ids)
            )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class IntentNarrativeSectionV4(_SpineModel):
    section_id: str
    heading_intent: str
    heading: str = ""
    reader_question: str = ""
    ordered_story_node_ids: tuple[str, ...] = ()
    ordered_argument_unit_ids: tuple[str, ...] = ()
    mechanism_ids: tuple[str, ...] = ()
    paragraphs: tuple[IntentNarrativeParagraphV4, ...] = ()
    content_digest: str = ""

    @field_validator("section_id", "heading_intent")
    @classmethod
    def _required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("section identity and heading intent must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _normalize(self) -> "IntentNarrativeSectionV4":
        heading = str(self.heading or "").strip() or self.heading_intent
        if heading_is_internal_identifier(heading):
            heading = self.heading_intent
        if heading_is_internal_identifier(heading):
            raise ValueError(
                f"section {self.section_id} cannot use an internal identifier as heading"
            )
        object.__setattr__(self, "heading", heading)
        object.__setattr__(self, "ordered_story_node_ids", _clean_tuple(self.ordered_story_node_ids))
        object.__setattr__(self, "ordered_argument_unit_ids", _clean_tuple(self.ordered_argument_unit_ids))
        object.__setattr__(self, "mechanism_ids", _clean_tuple(self.mechanism_ids))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class IntentNarrativePlanV4(_SpineModel):
    plan_id: str
    source_intent_digest: str = ""
    sections: tuple[IntentNarrativeSectionV4, ...]
    section_order_source: SectionOrderSourceV1 = "accepted_author_plan"
    content_digest: str = ""

    @field_validator("plan_id")
    @classmethod
    def _plan_id(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("intent narrative plan id must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _invariants(self) -> "IntentNarrativePlanV4":
        if not self.sections:
            raise ValueError("intent narrative plan requires at least one section")
        seen_sections: set[str] = set()
        seen_stories: set[str] = set()
        for section in self.sections:
            if section.section_id in seen_sections:
                raise ValueError(f"duplicate section identity:{section.section_id}")
            seen_sections.add(section.section_id)
            if heading_is_internal_identifier(section.heading):
                raise ValueError(f"internal identifier heading:{section.section_id}")
            for story_id in section.ordered_story_node_ids:
                if story_id in seen_stories:
                    raise ValueError(f"story node assigned to multiple sections:{story_id}")
                seen_stories.add(story_id)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class StoryMechanismBindingV1(_SpineModel):
    story_node_id: str
    intent_atom_ids: tuple[str, ...] = ()
    mechanism_ids: tuple[str, ...] = ()
    binding_basis_ids: tuple[str, ...] = ()
    binding_status: BindingStatusV1 = "unresolved"
    unresolved_atom_ids: tuple[str, ...] = ()
    content_digest: str = ""

    @field_validator("story_node_id")
    @classmethod
    def _story_id(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("story node id must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_row(self) -> "StoryMechanismBindingV1":
        object.__setattr__(self, "intent_atom_ids", _clean_tuple(self.intent_atom_ids))
        object.__setattr__(self, "mechanism_ids", _clean_tuple(self.mechanism_ids))
        object.__setattr__(self, "binding_basis_ids", _clean_tuple(self.binding_basis_ids))
        object.__setattr__(self, "unresolved_atom_ids", _clean_tuple(self.unresolved_atom_ids))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class IntentEvidenceAtomV1(_SpineModel):
    atom_id: str
    narrative_unit_id: str = ""
    story_node_id: str = ""
    source_quote: str
    source_quote_range: tuple[int, int] = (0, 0)
    subject: str
    predicate: str
    object_or_operands: tuple[str, ...] = ()
    polarity: Literal["positive", "negative", "unknown"] = "positive"
    quantifier: str = ""
    condition: str = ""
    boundary: str = ""
    authority_expectation: AtomAuthorityExpectationV1 = "repository_implementation"
    semantic_fields: dict[str, Any] = Field(default_factory=dict)
    splitter_candidate: bool = False
    unresolved_reason: str = ""
    content_digest: str = ""

    @field_validator("atom_id", "source_quote", "subject", "predicate")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("intent evidence atom required fields must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_atom(self) -> "IntentEvidenceAtomV1":
        object.__setattr__(self, "object_or_operands", _clean_tuple(self.object_or_operands))
        start, end = self.source_quote_range
        if start < 0 or end < start:
            raise ValueError("source quote range is invalid")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class FieldEvidenceProofV2(_SpineModel):
    proof_id: str
    conclusion_atom_id: str
    span_ids: tuple[str, ...] = ()
    relation_path_ids: tuple[str, ...] = ()
    snapshot_ids: tuple[str, ...] = ()
    call_path_ids: tuple[str, ...] = ()
    branch_conditions: tuple[str, ...] = ()
    layer_coverage: Literal["all", "partial", "unknown"] = "unknown"
    compatible: bool = False
    rejection_reason: str = ""
    content_digest: str = ""

    @field_validator("proof_id", "conclusion_atom_id")
    @classmethod
    def _ids(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("field evidence proof identifiers must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_proof(self) -> "FieldEvidenceProofV2":
        object.__setattr__(self, "span_ids", _clean_tuple(self.span_ids))
        object.__setattr__(self, "relation_path_ids", _clean_tuple(self.relation_path_ids))
        object.__setattr__(self, "snapshot_ids", _clean_tuple(self.snapshot_ids))
        object.__setattr__(self, "call_path_ids", _clean_tuple(self.call_path_ids))
        object.__setattr__(self, "branch_conditions", _clean_tuple(self.branch_conditions))
        if not self.compatible and not self.rejection_reason.strip():
            object.__setattr__(self, "rejection_reason", "proof_not_closed")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class IntentAtomClosureStatusV1(_SpineModel):
    atom_id: str
    search_status: SearchStatusV1 = "searching"
    evidence_disposition: EvidenceDispositionV1 | str = "bounded_not_found"
    candidate_surface_status: CandidateSurfaceStatusV1 = "incomplete"
    repository_proof_status: RepositoryProofStatusV1 = "unavailable"
    author_surface_receipt_id: str = ""
    stop_reason: str = ""
    review_binding_id: str = ""
    content_digest: str = ""

    @field_validator("atom_id")
    @classmethod
    def _atom_id(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("atom closure status requires an atom id")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_status(self) -> "IntentAtomClosureStatusV1":
        if self.evidence_disposition in {"author_spec_only", "out_of_scope"}:
            if self.candidate_surface_status == "complete" and not (
                self.stop_reason.strip()
                and self.author_surface_receipt_id.strip()
            ):
                object.__setattr__(self, "candidate_surface_status", "incomplete")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class CanonicalFormulaObligationV2(_SpineModel):
    canonical_formula_obligation_id: str
    source_author_formula_ids: tuple[str, ...] = ()
    source_mechanism_obligation_ids: tuple[str, ...] = ()
    source_intent_atom_ids: tuple[str, ...] = ()
    expectation: FormulaExpectationV2 = "preferred"
    source_proof_ids: tuple[str, ...] = ()
    formula_worthiness: FormulaWorthinessV1 = "prose_or_algorithm"
    disposition_reason: str = ""
    accepted_package_id: str = ""
    consumed_package_ids: tuple[str, ...] = ()
    committed_paragraph_ids: tuple[str, ...] = ()
    open: bool = True
    content_digest: str = ""

    @field_validator("canonical_formula_obligation_id")
    @classmethod
    def _id(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("canonical formula obligation id must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_formula(self) -> "CanonicalFormulaObligationV2":
        object.__setattr__(self, "source_author_formula_ids", _clean_tuple(self.source_author_formula_ids))
        object.__setattr__(
            self,
            "source_mechanism_obligation_ids",
            _clean_tuple(self.source_mechanism_obligation_ids),
        )
        object.__setattr__(self, "source_intent_atom_ids", _clean_tuple(self.source_intent_atom_ids))
        object.__setattr__(self, "source_proof_ids", _clean_tuple(self.source_proof_ids))
        object.__setattr__(self, "consumed_package_ids", _clean_tuple(self.consumed_package_ids))
        object.__setattr__(self, "committed_paragraph_ids", _clean_tuple(self.committed_paragraph_ids))
        if (
            self.expectation == "required"
            and self.formula_worthiness in {"prose_or_algorithm", "rejected"}
        ):
            object.__setattr__(self, "open", True)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class CandidateSectionTransactionV3(_SpineModel):
    section_id: str
    required_story_node_ids: tuple[str, ...] = ()
    required_argument_unit_ids: tuple[str, ...] = ()
    required_intent_atom_ids: tuple[str, ...] = ()
    required_repository_proposition_ids: tuple[str, ...] = ()
    required_author_surface_ids: tuple[str, ...] = ()
    required_canonical_formula_obligation_ids: tuple[str, ...] = ()
    required_paragraph_ids: tuple[str, ...] = ()
    completed_paragraph_receipt_digests: tuple[str, ...] = ()
    binder_status: Literal["complete", "partial", "rejected"] = "partial"
    content_digest: str = ""

    @field_validator("section_id")
    @classmethod
    def _section(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("candidate section transaction requires a section id")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_tx(self) -> "CandidateSectionTransactionV3":
        for name in (
            "required_story_node_ids",
            "required_argument_unit_ids",
            "required_intent_atom_ids",
            "required_repository_proposition_ids",
            "required_author_surface_ids",
            "required_canonical_formula_obligation_ids",
            "required_paragraph_ids",
            "completed_paragraph_receipt_digests",
        ):
            object.__setattr__(self, name, _clean_tuple(getattr(self, name)))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class ClaimVerificationReceiptV2(_SpineModel):
    claim_id: str
    paragraph_id: str = ""
    retrieved_proposition_ids: tuple[str, ...] = ()
    verification_status: ClaimVerificationStatusV2 = "unresolved"
    predicate_role_polarity_check: bool = False
    quantifier_condition_boundary_check: bool = False
    semantic_call_receipt_id: str = ""
    evidence_digest: str = ""
    content_digest: str = ""

    @field_validator("claim_id")
    @classmethod
    def _claim(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("claim verification receipt requires a claim id")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_receipt(self) -> "ClaimVerificationReceiptV2":
        object.__setattr__(
            self, "retrieved_proposition_ids", _clean_tuple(self.retrieved_proposition_ids)
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class MethodPropositionV2(_SpineModel):
    proposition_id: str
    surface: Literal["repository", "author_specification", "mismatch"] = "repository"
    subject: str
    predicate: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    polarity: Literal["positive", "negative", "unknown"] = "positive"
    quantifier: str = ""
    condition: str = ""
    boundary: str = ""
    required_qualifiers: tuple[str, ...] = ()
    immutable_numeric_tokens: tuple[str, ...] = ()
    immutable_formula_tokens: tuple[str, ...] = ()
    source_atom_ids: tuple[str, ...] = ()
    source_field_candidate_ids: tuple[str, ...] = ()
    source_detail_ids: tuple[str, ...] = ()
    may_enter_verified: bool = False
    requires_caveat: bool = False
    content_digest: str = ""

    @field_validator("proposition_id", "subject", "predicate")
    @classmethod
    def _required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("proposition identity and predicate fields must not be empty")
        return str(value).strip()

    @model_validator(mode="after")
    def _digest_prop(self) -> "MethodPropositionV2":
        for name in (
            "inputs", "outputs", "required_qualifiers", "immutable_numeric_tokens",
            "immutable_formula_tokens", "source_atom_ids",
            "source_field_candidate_ids", "source_detail_ids",
        ):
            object.__setattr__(self, name, _clean_tuple(getattr(self, name)))
        if self.surface != "repository":
            object.__setattr__(self, "may_enter_verified", False)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class MethodPropositionSetV2(_SpineModel):
    schema_version: str = "2.0"
    propositions: tuple[MethodPropositionV2, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest_set(self) -> "MethodPropositionSetV2":
        seen: set[str] = set()
        for item in self.propositions:
            if item.proposition_id in seen:
                raise ValueError(f"duplicate proposition id:{item.proposition_id}")
            seen.add(item.proposition_id)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self
