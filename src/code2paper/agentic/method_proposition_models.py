"""Reader-facing method propositions between research and publication prose.

Atomic claims deliberately describe small repository operations.  They are
excellent validation anchors but poor sentence plans.  These contracts group
closed evidence bindings into method-level conceptual cards without granting
the grouping layer authority to write final prose.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.method_product_models import MethodEvidenceLane


PropositionOriginV1 = Literal["repository_evidence", "author_intent"]
PropositionStatusV1 = Literal["ready", "partial", "gap"]
PropositionEvidenceStatusV1 = Literal[
    "entailed", "partial", "unsupported", "ambiguous", "not_checked"
]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


class _PropositionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PropositionCandidateClusterV1(_PropositionModel):
    """Closed input envelope for one low-temperature proposition proposal."""

    cluster_id: str
    origin: PropositionOriginV1
    obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_connectivity_edges: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    span_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_statements: tuple[str, ...] = Field(default_factory=tuple)
    uncertainty_notes: tuple[str, ...] = Field(default_factory=tuple)
    subjects: tuple[str, ...] = Field(default_factory=tuple)
    predicates: tuple[str, ...] = Field(default_factory=tuple)
    operands: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    claim_required_qualifiers: tuple[tuple[str, tuple[str, ...]], ...] = Field(
        default_factory=tuple
    )
    section_hints: tuple[str, ...] = Field(default_factory=tuple)
    author_term_hints: tuple[str, ...] = Field(default_factory=tuple)
    evidence_lane: MethodEvidenceLane
    content_digest: str = ""

    @field_validator("cluster_id")
    @classmethod
    def _id_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposition cluster id must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "PropositionCandidateClusterV1":
        for name in (
            "obligation_ids", "claim_ids", "fact_ids", "relation_ids", "span_ids",
            "source_statements", "uncertainty_notes", "subjects", "predicates", "operands", "conditions",
            "required_qualifiers", "section_hints",
            "author_term_hints",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        normalized_edges = tuple(dict.fromkeys(
            tuple(sorted((str(left).strip(), str(right).strip())))
            for left, right in self.fact_connectivity_edges
            if str(left).strip() and str(right).strip() and left != right
        ))
        if any(set(edge) - set(self.fact_ids) for edge in normalized_edges):
            raise ValueError("fact connectivity edge references an unknown fact")
        object.__setattr__(self, "fact_connectivity_edges", normalized_edges)
        normalized_claim_qualifiers = tuple(
            (str(claim_id).strip(), _clean(tuple(qualifiers)))
            for claim_id, qualifiers in self.claim_required_qualifiers
            if str(claim_id).strip()
        )
        if len({item[0] for item in normalized_claim_qualifiers}) != len(
            normalized_claim_qualifiers
        ):
            raise ValueError("duplicate claim qualifier bindings")
        if {item[0] for item in normalized_claim_qualifiers} - set(self.claim_ids):
            raise ValueError("claim qualifier binding references an unknown claim")
        object.__setattr__(
            self, "claim_required_qualifiers", normalized_claim_qualifiers
        )
        if self.origin == "repository_evidence" and (not self.claim_ids or not self.fact_ids or not self.span_ids):
            raise ValueError("repository proposition clusters require claims, facts and exact spans")
        if self.origin == "author_intent" and not self.source_statements:
            raise ValueError("author-intent proposition clusters require source statements")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("proposition cluster digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class MethodPropositionProposalV1(_PropositionModel):
    """Conceptual structure proposed by the Proposition Architect LLM.

    This is not publication prose.  All ID fields are checked against the
    candidate cluster before a proposition can be persisted.
    """

    cluster_id: str
    used_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    used_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    used_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    reader_subject: str
    transformation: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    boundary: str = ""
    paper_terms: tuple[str, ...] = Field(default_factory=tuple)
    implementation_binding_terms: tuple[str, ...] = Field(default_factory=tuple)
    source_statement_fragments: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("cluster_id", "reader_subject", "transformation")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposal binding and conceptual fields must not be empty")
        return value.strip()


class MethodPropositionProposalBatchV1(_PropositionModel):
    """One closed cluster decomposed into one or more atomic concept cards."""

    cluster_id: str
    proposals: tuple[MethodPropositionProposalV1, ...]

    @model_validator(mode="after")
    def _same_cluster_and_bounded(self) -> "MethodPropositionProposalBatchV1":
        if not self.cluster_id.strip():
            raise ValueError("proposal batch cluster id must not be empty")
        if not 1 <= len(self.proposals) <= 12:
            raise ValueError("proposal batch must contain 1 to 12 concept cards")
        if any(item.cluster_id != self.cluster_id for item in self.proposals):
            raise ValueError("proposal batch contains a foreign cluster id")
        return self


class PropositionBindingV1(_PropositionModel):
    proposition_id: str
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    span_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_digests: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest_binding(self) -> "PropositionBindingV1":
        for name in (
            "claim_ids", "fact_ids", "relation_ids", "span_ids",
            "equation_ids", "configuration_ids", "source_obligation_ids",
            "source_digests",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        if not self.proposition_id.strip():
            raise ValueError("proposition binding id must not be empty")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("proposition binding digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class MethodPropositionV1(_PropositionModel):
    proposition_id: str
    origin: PropositionOriginV1
    evidence_lane: MethodEvidenceLane
    status: PropositionStatusV1 = "ready"
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    may_enter_verified: bool = False
    evidence_verdict: PropositionEvidenceStatusV1 = "not_checked"
    requires_caveat: bool = False
    reader_subject: str
    transformation: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    boundary: str = ""
    paper_terms: tuple[str, ...] = Field(default_factory=tuple)
    implementation_binding_terms: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    immutable_numeric_tokens: tuple[str, ...] = Field(default_factory=tuple)
    immutable_formula_tokens: tuple[str, ...] = Field(default_factory=tuple)
    required_configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    section_hints: tuple[str, ...] = Field(default_factory=tuple)
    missing_or_uncertain_parts: tuple[str, ...] = Field(default_factory=tuple)
    # Q1 publication-relevance writing role (plan 19.5.4): a closed three-way
    # role derived deterministically from the bound fact context.  audit_only
    # propositions remain evidence but never enter Writer sentence plans,
    # supported-unit recall obligations, or qualifier Rewrite triggers.
    writing_role: Literal["method_positive", "method_conditional", "audit_only", "unclassified"] = "unclassified"
    content_digest: str = ""

    @field_validator("proposition_id", "reader_subject", "transformation")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("proposition id and conceptual fields must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _authority_and_digest(self) -> "MethodPropositionV1":
        for name in (
            "source_obligation_ids", "inputs", "outputs", "conditions", "paper_terms", "implementation_binding_terms",
            "required_qualifiers", "immutable_numeric_tokens", "immutable_formula_tokens",
            "required_configuration_ids", "section_hints", "missing_or_uncertain_parts",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        verified_lane = self.evidence_lane == "repository_verified"
        if self.may_enter_verified and not verified_lane:
            raise ValueError("only repository-verified propositions may enter verified output")
        if (
            self.may_enter_verified
            and self.evidence_verdict not in {"entailed", "not_checked"}
        ):
            raise ValueError("verified propositions require an entailed evidence verdict")
        if self.origin == "author_intent" and (self.may_enter_verified or not self.requires_caveat):
            raise ValueError("author-intent propositions are candidate-only and require caveats")
        if self.evidence_lane in {
            "repository_mismatch", "author_intent_unverified", "literature_pending",
            "empirical_pending", "formalization_pending",
        } and not self.requires_caveat:
            raise ValueError("non-verified proposition lanes require an explicit caveat")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = _digest(payload)
        if self.content_digest and self.content_digest != computed:
            raise ValueError("method proposition digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class PropositionEvidenceVerdictV1(_PropositionModel):
    """Independent semantic support judgment for a proposed Method concept."""

    proposition_id: str
    status: PropositionEvidenceStatusV1
    supported_fields: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    span_ids: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str = ""

    @model_validator(mode="after")
    def _closed_fields(self) -> "PropositionEvidenceVerdictV1":
        for name in (
            "supported_fields", "unsupported_fields", "claim_ids", "fact_ids",
            "relation_ids", "span_ids",
        ):
            object.__setattr__(self, name, _clean(getattr(self, name)))
        if not self.proposition_id.strip():
            raise ValueError("evidence verdict requires proposition_id")
        if self.status == "entailed" and self.unsupported_fields:
            raise ValueError("entailed verdict cannot contain unsupported fields")
        return self


class PropositionEvidenceJudgmentV1(_PropositionModel):
    """One ordinal verdict inside a cluster-level Evidence Judge call.

    The model sees a small 1-based ordinal instead of proposition, claim,
    fact, relation, or span IDs.  The harness owns all opaque identities and
    injects them after parsing the semantic decision.
    """

    judgment_index: int = Field(ge=1, le=12)
    status: PropositionEvidenceStatusV1
    supported_fields: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str = ""

    @model_validator(mode="after")
    def _closed_fields(self) -> "PropositionEvidenceJudgmentV1":
        object.__setattr__(self, "supported_fields", _clean(self.supported_fields))
        object.__setattr__(self, "unsupported_fields", _clean(self.unsupported_fields))
        if set(self.supported_fields) & set(self.unsupported_fields):
            raise ValueError("evidence judgment fields must be disjoint")
        if self.status == "entailed" and self.unsupported_fields:
            raise ValueError("entailed judgment cannot contain unsupported fields")
        return self


class PropositionEvidenceJudgmentBatchV1(_PropositionModel):
    judgments: tuple[PropositionEvidenceJudgmentV1, ...]

    @model_validator(mode="after")
    def _closed_batch(self) -> "PropositionEvidenceJudgmentBatchV1":
        if not 1 <= len(self.judgments) <= 12:
            raise ValueError("evidence judgment batch must contain 1 to 12 rows")
        indices = [item.judgment_index for item in self.judgments]
        if len(indices) != len(set(indices)):
            raise ValueError("evidence judgment batch contains duplicate indices")
        return self


class TypedPropositionGapV1(_PropositionModel):
    gap_id: str
    cluster_id: str
    reason: Literal[
        "proposal_missing", "proposal_schema_failed", "unknown_binding_id",
        "evidence_not_connected", "qualifier_weakened", "empty_concept",
        "source_fragment_not_closed", "condition_not_closed", "authority_expansion",
        "concept_fields_missing", "concept_coverage_missing", "author_semantics_missing",
        "concept_not_atomic", "evidence_judge_failed",
    ]
    detail: str
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)


class PropositionBindingSidecarV1(_PropositionModel):
    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    bindings: tuple[PropositionBindingV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "PropositionBindingSidecarV1":
        ids = [item.proposition_id for item in self.bindings]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate proposition binding ids")
        computed = _digest(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != computed:
            raise ValueError("proposition binding sidecar digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self


class MethodPropositionSetV1(_PropositionModel):
    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    propositions: tuple[MethodPropositionV1, ...] = Field(default_factory=tuple)
    evidence_verdicts: tuple[PropositionEvidenceVerdictV1, ...] = Field(default_factory=tuple)
    gaps: tuple[TypedPropositionGapV1, ...] = Field(default_factory=tuple)
    binding_sidecar_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "MethodPropositionSetV1":
        ids = [item.proposition_id for item in self.propositions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate method proposition ids")
        if self.propositions and not self.binding_sidecar_digest.startswith("sha256:"):
            raise ValueError("propositions require a digest-pinned binding sidecar")
        verdict_ids = [item.proposition_id for item in self.evidence_verdicts]
        if len(verdict_ids) != len(set(verdict_ids)):
            raise ValueError("duplicate proposition evidence verdict ids")
        if set(verdict_ids) - set(ids):
            raise ValueError("evidence verdict references an unknown proposition")
        verdict_by_id = {item.proposition_id: item for item in self.evidence_verdicts}
        for proposition in self.propositions:
            if proposition.may_enter_verified:
                verdict = verdict_by_id.get(proposition.proposition_id)
                # Legacy/frozen MethodPropositionV1 artifacts predate the
                # explicit verdict collection. Fresh production compilers
                # always set evidence_verdict and include the matching row.
                if (
                    proposition.evidence_verdict != "not_checked"
                    and (verdict is None or verdict.status != "entailed")
                ):
                    raise ValueError("verified proposition lacks an entailed evidence verdict")
        computed = _digest(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != computed:
            raise ValueError("method proposition set digest mismatch")
        object.__setattr__(self, "content_digest", computed)
        return self
