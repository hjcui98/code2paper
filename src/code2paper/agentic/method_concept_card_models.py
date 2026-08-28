"""Method Concept Card contracts (Stage 2 of the pause-diagnosis plan).

Replaces the free-form ``transformation`` prose field of the old
``MethodPropositionV1`` with a structured, atomic concept card whose fields
are all *phrases*, never paragraphs:

``MethodConceptCardV1``
    concept_key               # harness 生成
    authority_lane           # repository / author_intent / external / formalization
    research_question
    method_subject
    operation
    inputs[]
    outputs[]
    conditions[]
    numeric_constraints[]
    formula_constraints[]
    evidence_fragment_refs[] # 模型从当前有界 source fragments 中选择
    story_node
    known_parts[]
    missing_parts[]
    candidate_caveat

Hard rules (from ``autonomous_method_agent_pause_diagnosis_and_handoff_20260813.md``
Stage 2):

- No field may carry an entire paragraph of prose; every field is a bounded
  phrase.  The old ``transformation`` escape hatch is gone.
- Repository cards are compiled only from repository observations; author
  purpose must never enter a repository card.
- Author-intent cards are compiled separately and can never
  ``may_enter_verified``.
- One card may cover several genuinely related low-level facts; there is no
  quota requiring every ``calls/reduces/sorts`` predicate to become a card.
- Unused low-level facts stay in the evidence ledger.
- ``evidence_fragment_refs`` are chosen by the model from a bounded closed
  fragment set exposed by the harness; the harness owns all opaque IDs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConceptAuthorityLaneV1 = Literal[
    "repository",
    "author_intent",
    "external",
    "formalization",
]

ConceptCardStatusV1 = Literal["ready", "partial", "gap"]

# Phrase budgets: strictly bounded so no field can smuggle in a paragraph.
_SUBJECT_MAX = 160
_OPERATION_MAX = 200
_PHRASE_MAX = 80
_CAVEAT_MAX = 240
_ARRAY_MAX = 12
_CARD_AUDIT_DIGEST_EXCLUDE = frozenset({"writing_role"})


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )


class _ConceptModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConceptCardCandidateClusterV1(_ConceptModel):
    """Closed, bounded input envelope for one concept-card proposal.

    This is the Stage 2 replacement for ``PropositionCandidateClusterV1``:
    the model only ever sees *bounded source fragments* (exact statements /
    spans), never raw fact/claim JSON, and never IDs it could echo back.
    """

    cluster_id: str
    origin: ConceptAuthorityLaneV1
    obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    research_question: str = ""
    source_fragments: tuple[str, ...] = Field(default_factory=tuple)
    source_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    low_level_fact_count: int = 0
    low_level_predicates: tuple[str, ...] = Field(default_factory=tuple)
    story_node: str = ""
    author_term_hints: tuple[str, ...] = Field(default_factory=tuple)
    section_hints: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    uncertainty_notes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("cluster_id")
    @classmethod
    def _id_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("concept cluster id must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "ConceptCardCandidateClusterV1":
        for name in (
            "obligation_ids", "source_fragments", "source_span_ids",
            "low_level_predicates", "author_term_hints", "section_hints",
            "required_qualifiers", "uncertainty_notes",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        if self.origin == "repository" and not self.source_fragments:
            raise ValueError("repository concept clusters require bounded source fragments")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("concept cluster digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class MethodConceptCardProposalV1(_ConceptModel):
    """Model-owned concept fields; binding identity stays harness-owned.

    Every field is a bounded phrase.  ``evidence_fragment_refs`` must be
    chosen from the closed fragment set supplied by the harness (fragment
    keys, not internal IDs).
    """

    cluster_id: str
    method_subject: str = Field(min_length=2, max_length=_SUBJECT_MAX)
    operation: str = Field(min_length=3, max_length=_OPERATION_MAX)
    inputs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    outputs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    numeric_constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    formula_constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    evidence_fragment_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    story_node: str = Field(default="", max_length=_SUBJECT_MAX)
    known_parts: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    missing_parts: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    candidate_caveat: str = Field(default="", max_length=_CAVEAT_MAX)

    @field_validator(
        "method_subject", "operation",
        "inputs", "outputs", "conditions",
        "numeric_constraints", "formula_constraints",
        "evidence_fragment_refs", "known_parts", "missing_parts",
        "candidate_caveat", "story_node",
    )
    @classmethod
    def _phrase_bounds(cls, value: Any) -> Any:
        if isinstance(value, str):
            cleaned = value.strip()
            # Phrases only: no newline paragraphs.  Semicolons/commas are
            # legitimate within a phrase; only sentence terminators at the
            # end are rejected.
            if "\n" in cleaned or "\r" in cleaned:
                raise ValueError("concept fields must be single-line phrases")
            if cleaned.endswith((".", "!", "?")):
                raise ValueError("concept fields must be phrases, not sentences")
            return cleaned
        return value

    @model_validator(mode="after")
    def _bounded_arrays(self) -> "MethodConceptCardProposalV1":
        for name in (
            "inputs", "outputs", "conditions", "numeric_constraints",
            "formula_constraints", "evidence_fragment_refs",
            "known_parts", "missing_parts",
        ):
            values = tuple(
                dict.fromkeys(str(item).strip() for item in getattr(self, name) if str(item).strip())
            )
            for item in values:
                if len(item) > _PHRASE_MAX:
                    raise ValueError(
                        f"concept array field {name} contains an over-long phrase"
                    )
            object.__setattr__(self, name, values)
        if not self.method_subject.strip() or not self.operation.strip():
            raise ValueError("concept card requires method_subject and operation")
        return self


class MethodConceptCardProposalBatchV1(_ConceptModel):
    """One closed cluster decomposed into 1-3 atomic concept cards."""

    cluster_id: str
    proposals: tuple[MethodConceptCardProposalV1, ...]

    @model_validator(mode="after")
    def _same_cluster_and_bounded(self) -> "MethodConceptCardProposalBatchV1":
        if not self.cluster_id.strip():
            raise ValueError("concept proposal batch cluster id must not be empty")
        if not 1 <= len(self.proposals) <= 3:
            raise ValueError("one cluster must yield at most 3 concept cards")
        if any(item.cluster_id != self.cluster_id for item in self.proposals):
            raise ValueError("concept proposal batch contains a foreign cluster id")
        return self


class MethodConceptCardV1(_ConceptModel):
    """A persisted, digest-covered Method concept card (Stage 2 unit)."""

    concept_key: str
    cluster_id: str = ""
    authority_lane: ConceptAuthorityLaneV1
    research_question: str = ""
    method_subject: str = Field(min_length=2, max_length=_SUBJECT_MAX)
    operation: str = Field(min_length=3, max_length=_OPERATION_MAX)
    inputs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    outputs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    numeric_constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    formula_constraints: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    evidence_fragment_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    story_node: str = Field(default="", max_length=_SUBJECT_MAX)
    known_parts: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    missing_parts: tuple[str, ...] = Field(default_factory=tuple, max_length=_ARRAY_MAX)
    candidate_caveat: str = Field(default="", max_length=_CAVEAT_MAX)
    requires_caveat: bool = False
    may_enter_verified: bool = False
    evidence_verdict: str = "not_checked"
    writing_role: Literal["method_positive", "method_conditional", "audit_only"] | None = None
    realized_story_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    realizes_story_node: bool = False
    content_digest: str = ""

    @field_validator("concept_key")
    @classmethod
    def _key_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("concept key must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _authority_and_digest(self) -> "MethodConceptCardV1":
        for name in (
            "inputs", "outputs", "conditions", "numeric_constraints",
            "formula_constraints", "evidence_fragment_refs",
            "known_parts", "missing_parts", "realized_story_node_ids",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        realized_ids = tuple(
            str(item).strip()
            for item in self.realized_story_node_ids
            if str(item).strip()
        )
        object.__setattr__(self, "realized_story_node_ids", realized_ids)
        object.__setattr__(self, "realizes_story_node", bool(realized_ids))
        if self.authority_lane != "repository" and self.may_enter_verified:
            raise ValueError("only repository cards may enter verified output")
        if self.authority_lane == "author_intent" and not (
            self.candidate_caveat or self.missing_parts
        ):
            raise ValueError("author-intent cards require a caveat or missing parts")
        if (
            self.may_enter_verified
            and (self.requires_caveat or self.candidate_caveat)
        ):
            raise ValueError("verified cards must not require a caveat")
        if (
            self.may_enter_verified
            and self.evidence_verdict not in {"entailed", "not_checked"}
        ):
            raise ValueError("verified cards require an entailed evidence verdict")
        payload = self.model_dump(
            mode="json",
            exclude={"content_digest", *_CARD_AUDIT_DIGEST_EXCLUDE},
        )
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("concept card digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        if self.writing_role is None:
            from code2paper.agentic.publication_relevance import (
                classify_concept_card_writing_role,
            )

            object.__setattr__(
                self,
                "writing_role",
                classify_concept_card_writing_role(self),
            )
        return self


class ConceptCardFieldJudgmentV1(_ConceptModel):
    """One per-field evidence judgment (Stage 3).

    The judge evaluates ONE semantic field of ONE card against the exact
    closed fragments of its cluster.  ``proposed_value`` is the card's
    field text, ``evidence_fragment_refs`` the fragments that support (or
    fail to support) that field, and ``rationale`` explains why.  The
    rationale is mandatory for every verdict other than ``not_found`` with
    an empty ref list — the judge must say *which* fragment supports the
    field, not just that the field is supported.
    """

    field_name: str
    proposed_value: str = ""
    verdict: Literal["entailed", "partial", "contradicted", "not_found"] = "not_found"
    evidence_fragment_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    rationale: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ConceptCardFieldJudgmentV1":
        if not self.field_name.strip():
            raise ValueError("field judgment requires a field name")
        object.__setattr__(self, "field_name", self.field_name.strip())
        object.__setattr__(
            self,
            "evidence_fragment_refs",
            _clean(self.evidence_fragment_refs),
        )
        if self.verdict != "not_found" and not self.rationale.strip():
            raise ValueError("field judgment requires a rationale")
        if self.verdict in {"entailed", "partial"} and not self.evidence_fragment_refs:
            raise ValueError(
                "entailed/partial field judgments require evidence fragment refs"
            )
        return self


class ConceptCardEvidenceVerdictV1(_ConceptModel):
    """Per-field evidence judgment for one concept card (Stage 3 unit).

    The card may enter the verified lane only when EVERY positive semantic
    field (method_subject, operation, inputs, outputs, conditions,
    numeric_constraints, formula_constraints) is individually entailed.
    One card cannot pass on the mere presence of unrelated facts.

    Purpose/downstream judgments (e.g. "for pruning") require caller or
    data-flow evidence; the compiler resolves the frag-N refs to fragment
    text and rejects an entailed purpose without such a witness.
    """

    concept_key: str
    field_judgments: tuple[ConceptCardFieldJudgmentV1, ...] = Field(default_factory=tuple)
    overall_verdict: Literal[
        "entailed", "partial", "contradicted", "not_found"
    ] = "not_found"
    rationale: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ConceptCardEvidenceVerdictV1":
        if not self.concept_key.strip():
            raise ValueError("concept evidence verdict requires concept_key")
        if not self.field_judgments:
            raise ValueError("concept evidence verdict requires field judgments")
        field_values = [
            (item.field_name, item.proposed_value)
            for item in self.field_judgments
        ]
        if len(field_values) != len(set(field_values)):
            raise ValueError("duplicate field judgments")
        if self.overall_verdict == "entailed" and any(
            item.verdict != "entailed" for item in self.field_judgments
        ):
            raise ValueError(
                "entailed overall verdict requires every field judgment entailed"
            )
        if self.overall_verdict != "not_found" and not self.rationale.strip():
            raise ValueError("concept evidence verdict requires a rationale")
        return self


class ConceptCardBindingV1(_ConceptModel):
    """field -> exact source fragment refs (Stage 3 unit).

    Each binding maps one semantic field of one card to the exact closed
    fragments that support it.  A card never binds to a whole cluster of
    unrelated facts.
    """

    concept_key: str
    field_bindings: tuple[tuple[str, tuple[str, ...]], ...] = Field(default_factory=tuple)
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "ConceptCardBindingV1":
        if not self.concept_key.strip():
            raise ValueError("concept binding requires concept_key")
        normalized: list[tuple[str, tuple[str, ...]]] = []
        for field_name, refs in self.field_bindings:
            field_name = str(field_name).strip()
            refs = _clean(tuple(refs))
            if not field_name:
                raise ValueError("concept binding field name must not be empty")
            normalized.append((field_name, refs))
        object.__setattr__(self, "field_bindings", tuple(normalized))
        object.__setattr__(self, "source_obligation_ids", _clean(self.source_obligation_ids))
        object.__setattr__(self, "source_span_ids", _clean(self.source_span_ids))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("concept binding digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class ConceptCardGapV1(_ConceptModel):
    gap_id: str
    cluster_id: str
    reason: Literal[
        "proposal_missing", "proposal_schema_failed", "fragment_not_closed",
        "phrase_budget_exceeded", "authority_expansion", "empty_concept",
        "evidence_judge_failed",
    ]
    detail: str
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)


class MethodConceptCardSetV1(_ConceptModel):
    """Digest-covered collection of concept cards for one repository snapshot."""

    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    cards: tuple[MethodConceptCardV1, ...] = Field(default_factory=tuple)
    evidence_verdicts: tuple[ConceptCardEvidenceVerdictV1, ...] = Field(default_factory=tuple)
    bindings: tuple[ConceptCardBindingV1, ...] = Field(default_factory=tuple)
    gaps: tuple[ConceptCardGapV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "MethodConceptCardSetV1":
        keys = [item.concept_key for item in self.cards]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate concept card keys")
        verdict_keys = [item.concept_key for item in self.evidence_verdicts]
        if len(verdict_keys) != len(set(verdict_keys)):
            raise ValueError("duplicate concept verdict keys")
        if set(verdict_keys) - set(keys):
            raise ValueError("concept verdict references an unknown card")
        binding_keys = [item.concept_key for item in self.bindings]
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("duplicate concept binding keys")
        if set(binding_keys) - set(keys):
            raise ValueError("concept binding references an unknown card")
        verdict_by_key = {item.concept_key: item for item in self.evidence_verdicts}
        for card in self.cards:
            if card.may_enter_verified:
                verdict = verdict_by_key.get(card.concept_key)
                if (
                    card.evidence_verdict != "not_checked"
                    and (verdict is None or verdict.overall_verdict != "entailed")
                ):
                    raise ValueError("verified card lacks an entailed overall verdict")
        computed = _digest(self.model_dump(
            mode="json",
            exclude={
                "content_digest": True,
                "cards": {
                    "__all__": {name: True for name in _CARD_AUDIT_DIGEST_EXCLUDE},
                },
            },
        ))
        if self.content_digest and self.content_digest != computed:
            raise ValueError("concept card set digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self
