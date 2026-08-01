"""Typed contracts between research evidence and publication writing.

The research plane deliberately keeps atomic claims small.  A publication
writer needs a second representation: a supported method point, the reader
question it answers, and the rhetorical moves needed to explain it.  This
module contains that representation together with the reference-method and
completeness contracts introduced by the publication writer design.

The contracts are project-agnostic.  They do not contain repository names,
symbol literals, or paper-specific claim text.  A claim may be used as input
only when its authority lane and source artifact are carried along with the
unit that consumes it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.source_authority import SourceAuthorityV1


AuthorityLaneV1 = Literal[
    "executable_hard",
    "configuration_resolved",
    "author_attested",
    "formal_derivation",
    "empirical_artifact",
    "external_literature",
    "expository_bridge",
]

AUTHORITY_LANES: tuple[AuthorityLaneV1, ...] = (
    "executable_hard",
    "configuration_resolved",
    "author_attested",
    "formal_derivation",
    "empirical_artifact",
    "external_literature",
    "expository_bridge",
)

ReferenceMethodStatusV1 = Literal[
    "supported_by_repository",
    "partially_supported_by_repository",
    "paper_code_mismatch",
    "unverified_by_repository",
    "author_confirmation_required",
    "external_evidence_required",
    "formalization_required",
    "explicit_code_gap",
    "out_of_scope",
]

REFERENCE_METHOD_STATUSES: tuple[ReferenceMethodStatusV1, ...] = (
    "supported_by_repository",
    "partially_supported_by_repository",
    "paper_code_mismatch",
    "unverified_by_repository",
    "author_confirmation_required",
    "external_evidence_required",
    "formalization_required",
    "explicit_code_gap",
    "out_of_scope",
)

MethodArgumentKindV1 = Literal[
    "implementation",
    "configuration",
    "equation",
    "rationale",
    "empirical",
    "capability",
    "limitation",
]

RhetoricalMoveV1 = Literal[
    "problem_or_local_context",
    "design_objective",
    "mechanism_overview",
    "intuition_or_rationale",
    "formal_objects_and_notation",
    "equation_or_derivation",
    "algorithm_or_data_flow",
    "implementation_realization",
    "configuration_and_branches",
    "training_objective",
    "inference_and_output",
    "complexity_or_boundary_conditions",
    "limitations_or_mismatch",
    "transition_to_next_section",
]

RHETORICAL_MOVES: tuple[RhetoricalMoveV1, ...] = (
    "problem_or_local_context",
    "design_objective",
    "mechanism_overview",
    "intuition_or_rationale",
    "formal_objects_and_notation",
    "equation_or_derivation",
    "algorithm_or_data_flow",
    "implementation_realization",
    "configuration_and_branches",
    "training_objective",
    "inference_and_output",
    "complexity_or_boundary_conditions",
    "limitations_or_mismatch",
    "transition_to_next_section",
)

ConfigurationStateV1 = Literal["actual", "default", "conditional", "unreachable"]


class _MethodModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


class ReferenceMethodObligationV1(_MethodModel):
    """One reference-method unit that must be resolved or explicitly classified."""

    obligation_id: str
    role: str
    statement: str
    obligation_class: str = Field(
        default="implementation",
        validation_alias=AliasChoices("obligation_class", "class", "class_"),
    )
    authority_lane: AuthorityLaneV1 = "executable_hard"
    research_queries: tuple[str, ...] = Field(default_factory=tuple)
    importance: Literal["critical", "high", "medium", "low"] = "medium"
    source_obligation_id: str = ""
    candidate_symbols: tuple[str, ...] = Field(default_factory=tuple)
    status: ReferenceMethodStatusV1 = "unverified_by_repository"
    notes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("obligation_id", "role", "statement")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reference obligation identifiers and text must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _digest(self) -> "ReferenceMethodObligationV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class ReferenceMethodAgendaV1(_MethodModel):
    """Content-addressed reference-method agenda used by the Architect."""

    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    author_goal: str = ""
    obligations: tuple[ReferenceMethodObligationV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ReferenceMethodAgendaV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self

    @property
    def critical_obligations(self) -> tuple[ReferenceMethodObligationV1, ...]:
        return tuple(item for item in self.obligations if item.importance == "critical")


class MethodCompletenessItemV1(_MethodModel):
    """One row in the nine-state completeness matrix."""

    obligation_id: str
    role: str = ""
    statement: str = ""
    importance: Literal["critical", "high", "medium", "low"] = "medium"
    status: ReferenceMethodStatusV1 = "unverified_by_repository"
    authority_lane: AuthorityLaneV1 = "executable_hard"
    source_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""
    next_action: str = ""

    @property
    def terminal(self) -> bool:
        return self.status != "unverified_by_repository"


class MethodCompletenessMatrixV1(_MethodModel):
    """Reference coverage with explicit, non-collapsed terminal states."""

    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    agenda_digest: str = ""
    items: tuple[MethodCompletenessItemV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodCompletenessMatrixV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self

    @property
    def unresolved_critical_ids(self) -> tuple[str, ...]:
        return tuple(
            item.obligation_id
            for item in self.items
            if item.importance in {"critical", "high"}
            and item.status == "unverified_by_repository"
        )

    @property
    def supported_ids(self) -> tuple[str, ...]:
        return tuple(
            item.obligation_id
            for item in self.items
            if item.status in {"supported_by_repository", "partially_supported_by_repository"}
        )

    def by_id(self) -> dict[str, MethodCompletenessItemV1]:
        return {item.obligation_id: item for item in self.items}


class ConfigurationClaimV1(_MethodModel):
    """A configuration value traced from definition to a real entrypoint."""

    configuration_id: str
    key: str
    value: str | int | float | bool | None
    state: ConfigurationStateV1
    definition_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    entrypoint_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    override_chain: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    source_authority: SourceAuthorityV1 = "executable_hard"
    authority_lane: Literal["configuration_resolved"] = "configuration_resolved"
    active: bool = True
    unresolved_reason: str = ""
    canonical_identity: str = ""
    content_digest: str = ""

    @field_validator("configuration_id", "key")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("configuration id and key must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _state_consistency(self) -> "ConfigurationClaimV1":
        if self.state == "actual" and not self.entrypoint_span_ids:
            raise ValueError("actual configuration claims require an entrypoint span")
        if self.state == "unreachable" and self.active:
            raise ValueError("unreachable configuration claims cannot be active")
        identity = self.canonical_identity or _digest({
            "key": self.key,
            "value": self.value,
            "state": self.state,
            "definitions": self.definition_span_ids,
            "entrypoints": self.entrypoint_span_ids,
            "overrides": self.override_chain,
            "conditions": self.conditions,
        })
        object.__setattr__(self, "canonical_identity", identity)
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


class ConfigurationClaimSetV1(_MethodModel):
    schema_version: str = "1.0"
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    claims: tuple[ConfigurationClaimV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ConfigurationClaimSetV1":
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


class MethodArgumentUnitV1(_MethodModel):
    """The smallest publication-level argument that can span several facts."""

    argument_unit_id: str
    section_role: str
    research_question: str
    design_objective: str = ""
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    author_rationale_ids: tuple[str, ...] = Field(default_factory=tuple)
    empirical_ids: tuple[str, ...] = Field(default_factory=tuple)
    literature_ids: tuple[str, ...] = Field(default_factory=tuple)
    behavior_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_expository_moves: tuple[RhetoricalMoveV1, ...] = Field(default_factory=tuple)
    unresolved_inputs: tuple[str, ...] = Field(default_factory=tuple)
    authority_lanes: tuple[AuthorityLaneV1, ...] = Field(default_factory=("executable_hard",))
    source_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    supported: bool = True
    information_weight: float = 1.0
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodArgumentUnitV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class SectionArgumentMoveV1(_MethodModel):
    move: RhetoricalMoveV1
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    paragraph_budget: int = 1
    information_budget: float = 1.0
    allowed_authority_lanes: tuple[AuthorityLaneV1, ...] = Field(default_factory=("executable_hard",))
    required: bool = False
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("paragraph_budget")
    @classmethod
    def _positive_budget(cls, value: int) -> int:
        return max(0, value)


class SectionArgumentGraphV1(_MethodModel):
    """Rhetorical graph for one Method section; no final prose is stored."""

    section_id: str
    heading: str
    reader_question: str
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    moves: tuple[SectionArgumentMoveV1, ...] = Field(default_factory=tuple)
    dependencies: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_inputs: tuple[str, ...] = Field(default_factory=tuple)
    depth_budget: int = 1
    page_budget: float = 1.0
    incomplete: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "SectionArgumentGraphV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self

    @property
    def required_moves(self) -> tuple[SectionArgumentMoveV1, ...]:
        return tuple(move for move in self.moves if move.required)


class WritingResearchRequestV1(_MethodModel):
    """A scoped request emitted while a section is being written."""

    request_id: str
    section_id: str
    argument_unit_id: str
    missing_rhetorical_move: RhetoricalMoveV1
    exact_question: str
    required_authority_lane: AuthorityLaneV1
    candidate_symbols_or_terms: tuple[str, ...] = Field(default_factory=tuple)
    current_known_facts: tuple[str, ...] = Field(default_factory=tuple)
    why_needed_for_reader: str = ""
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    status: Literal["open", "fulfilled", "author_review", "blocked"] = "open"
    fulfilled_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "WritingResearchRequestV1":
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


class ProofObligationV1(_MethodModel):
    """Formalization request that separates code equivalence from theory."""

    proof_obligation_id: str
    statement: str
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    conclusion: str
    supporting_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    derivation_steps: tuple[str, ...] = Field(default_factory=tuple)
    status: Literal["supported", "partial", "unproved", "rejected"] = "unproved"
    authority_lane: Literal["formal_derivation"] = "formal_derivation"
    limitations: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ProofObligationV1":
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


class MethodSectionPlanV2(_MethodModel):
    """Architect output: section graph plus dynamic budget, no final text."""

    plan_id: str
    method_name: str = ""
    sections: tuple[SectionArgumentGraphV1, ...] = Field(default_factory=tuple)
    argument_units: tuple[MethodArgumentUnitV1, ...] = Field(default_factory=tuple)
    venue: str = ""
    audience: str = ""
    total_page_budget: float = 0.0
    incomplete_sections: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodSectionPlanV2":
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


def build_reference_method_agenda(
    intent_graph: Any,
    *,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
    author_goal: str = "",
) -> ReferenceMethodAgendaV1:
    """Convert the typed intent graph into reference obligations.

    Author wording remains a question/diagnostic field.  It is never copied
    into a positive claim without a later authority-bearing artifact.
    """

    obligations: list[ReferenceMethodObligationV1] = []
    for item in getattr(intent_graph, "obligations", ()):
        targets = tuple(getattr(item, "typed_behavior_targets", ()))
        role = next((target.role for target in targets if target.role), str(getattr(item, "kind", "method")))
        target_queries = tuple(query for target in targets for query in getattr(target, "search_terms", ()))
        queries = tuple(dict.fromkeys([*getattr(item, "retrieval_queries", ()), *target_queries]))
        kind = str(getattr(item, "kind", "implementation"))
        if kind in {"rationale_check", "high_risk_claim", "mismatch_check"}:
            lane: AuthorityLaneV1 = "author_attested"
            obligation_class = "rationale" if kind == "rationale_check" else "capability"
        elif kind == "organization":
            lane = "expository_bridge"
            obligation_class = "capability"
        else:
            lane = "executable_hard"
            obligation_class = "implementation"
        priority = str(getattr(item, "priority", "should_cover"))
        importance = "critical" if priority == "must_cover" and kind == "method_mainline" else (
            "high" if priority in {"must_cover", "should_cover"} else "medium"
        )
        obligations.append(ReferenceMethodObligationV1(
            obligation_id=str(item.obligation_id),
            role=role or kind,
            statement=str(getattr(item, "author_text", "")) or role or kind,
            obligation_class=obligation_class,
            authority_lane=lane,
            research_queries=queries,
            importance=importance,
            source_obligation_id=str(item.obligation_id),
            candidate_symbols=tuple(getattr(item, "candidate_paths", ())),
            status="unverified_by_repository",
        ))
    return ReferenceMethodAgendaV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        author_goal=author_goal or str(getattr(intent_graph, "method_goal", "")),
        obligations=tuple(obligations),
    )


def build_completeness_matrix(
    agenda: ReferenceMethodAgendaV1,
    coverage_report: Any | None = None,
    *,
    claim_set: Any | None = None,
    equation_ids_by_obligation: dict[str, tuple[str, ...]] | None = None,
    configuration_ids_by_obligation: dict[str, tuple[str, ...]] | None = None,
) -> MethodCompletenessMatrixV1:
    """Map research coverage into the full nine-state reference contract."""

    coverage_by_id = {
        str(item.obligation_id): item
        for item in getattr(coverage_report, "items", ())
    }
    claims = tuple(getattr(claim_set, "claims", ()))
    equations = equation_ids_by_obligation or {}
    configurations = configuration_ids_by_obligation or {}
    items: list[MethodCompletenessItemV1] = []
    for obligation in agenda.obligations:
        coverage = coverage_by_id.get(obligation.obligation_id)
        coverage_status = str(getattr(coverage, "coverage_status", "unresolved"))
        status_map: dict[str, ReferenceMethodStatusV1] = {
            "supported": "supported_by_repository",
            "partial": "partially_supported_by_repository",
            "explicit_gap": "explicit_code_gap",
            "blocked": "unverified_by_repository",
            "unresolved": "unverified_by_repository",
        }
        status = status_map.get(coverage_status, "unverified_by_repository")
        claim_ids = tuple(
            str(claim.claim_id)
            for claim in claims
            if obligation.obligation_id in tuple(getattr(claim, "covers_obligation_ids", ()))
        )
        if status == "supported_by_repository" and not claim_ids:
            status = "partially_supported_by_repository"
        reason = str(getattr(coverage, "rationale", "")) if coverage is not None else "No coverage artifact is available."
        next_action = "" if status != "unverified_by_repository" else "run scoped repository research"
        items.append(MethodCompletenessItemV1(
            obligation_id=obligation.obligation_id,
            role=obligation.role,
            statement=obligation.statement,
            importance=obligation.importance,
            status=status,
            authority_lane=obligation.authority_lane,
            source_artifact_ids=tuple(
                dict.fromkeys(
                    evidence_id
                    for claim in claims
                    if obligation.obligation_id in tuple(getattr(claim, "covers_obligation_ids", ()))
                    for evidence_id in (
                        *tuple(getattr(claim, "direct_evidence_ids", ())),
                        *tuple(getattr(claim, "relation_evidence_ids", ())),
                    )
                )
            ),
            claim_ids=claim_ids,
            equation_ids=equations.get(obligation.obligation_id, ()),
            configuration_ids=configurations.get(obligation.obligation_id, ()),
            reason=reason,
            next_action=next_action,
        ))
    return MethodCompletenessMatrixV1(
        repo_snapshot_id=agenda.repo_snapshot_id,
        project_tree_hash=agenda.project_tree_hash,
        agenda_digest=agenda.content_digest,
        items=tuple(items),
    )


__all__ = [
    "AUTHORITY_LANES",
    "AuthorityLaneV1",
    "ConfigurationClaimSetV1",
    "ConfigurationClaimV1",
    "ConfigurationStateV1",
    "MethodArgumentKindV1",
    "MethodArgumentUnitV1",
    "MethodCompletenessItemV1",
    "MethodCompletenessMatrixV1",
    "MethodSectionPlanV2",
    "ProofObligationV1",
    "REFERENCE_METHOD_STATUSES",
    "ReferenceMethodAgendaV1",
    "ReferenceMethodObligationV1",
    "ReferenceMethodStatusV1",
    "RHETORICAL_MOVES",
    "RhetoricalMoveV1",
    "SectionArgumentGraphV1",
    "SectionArgumentMoveV1",
    "WritingResearchRequestV1",
    "build_completeness_matrix",
    "build_reference_method_agenda",
]
