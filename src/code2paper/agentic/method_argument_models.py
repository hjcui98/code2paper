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

ConfigurationStateV1 = Literal["actual", "default", "conditional", "unreachable", "unresolved"]

MechanismResearchUnresolvedKindV1 = Literal[
    "missing_definition",
    "missing_call_path",
    "missing_data_flow",
    "missing_condition",
    "missing_configuration",
    "missing_formula_operand",
    "authority_conflict",
]


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
    """One row in the nine-state completeness matrix.

    ``matched_fact_ids`` / ``matched_relation_ids`` / ``matched_span_ids``
    preserve the coverage compiler's exact evidence handles for rows whose
    claim ids are empty (typically ``partially_supported_by_repository`` and
    other candidate rows).  They are backward compatible (default empty) and
    give the Architect enough material to materialize candidate units that
    are not empty prose shells.
    """

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
    matched_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    matched_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    matched_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""
    next_action: str = ""

    @property
    def terminal(self) -> bool:
        # All nine values are explicit completeness classifications.  In
        # particular, ``unverified_by_repository`` is a valid terminal report
        # state even though it remains unresolved and should trigger more
        # research (see ``unresolved_critical_ids`` below).
        return self.status in REFERENCE_METHOD_STATUSES


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
    source_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
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
        if self.state == "unresolved" and self.value is not None:
            raise ValueError("unresolved configuration accesses cannot carry a resolved value")
        if self.state == "unresolved" and not self.unresolved_reason:
            raise ValueError("unresolved configuration accesses require an unresolved reason")
        identity = self.canonical_identity or _digest({
            "key": self.key,
            "value": self.value,
            "state": self.state,
            "definitions": self.definition_span_ids,
            "entrypoints": self.entrypoint_span_ids,
            "overrides": self.override_chain,
            "conditions": self.conditions,
            "source_facts": self.source_fact_ids,
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


class SemanticFlowSlotV1(_MethodModel):
    """One closed semantic-flow slot: a single fact with its exact role.

    The slot is a typed binding, not a sentence plan.  ``operands`` preserves
    every scalar or list member of the fact's object; a list-valued
    transformation may never become an empty operand list.  ``exact_relation_ids``
    are only the relations closed-bound to this fact/claim, never the unit's
    whole relation set.
    """

    slot_id: str
    role: Literal["input", "transformation", "condition", "output"]
    subject: str
    predicate: str
    operands: tuple[str, ...] = Field(default_factory=tuple)
    produced_entities: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_lanes: tuple[AuthorityLaneV1, ...] = ("executable_hard",)
    content_digest: str = ""

    @field_validator("slot_id", "subject", "predicate")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("semantic flow slot binding fields must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _operand_closure(self) -> "SemanticFlowSlotV1":
        if self.role == "transformation" and not self.operands:
            raise ValueError("transformation slots must preserve every scalar/list operand")
        if not self.fact_ids and not self.claim_ids:
            raise ValueError("semantic flow slot must bind at least one fact or claim id")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class SemanticFlowEdgeV1(_MethodModel):
    """One authorized typed relation between two closed semantic slots."""

    relation_id: str
    relation_type: Literal["call_flow", "data_flow", "control_flow", "writes"]
    source_symbol: str
    target_symbol: str
    source_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    direct_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("relation_id", "source_symbol", "target_symbol")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("semantic flow edge binding fields must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _digest(self) -> "SemanticFlowEdgeV1":
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class SemanticArgumentFrameV1(_MethodModel):
    """Closed-ID semantic argument frame for one argument unit.

    Built exactly once by the Architect and consumed by the Writer; both
    sides must observe the same ``content_digest``.  Direction comes only
    from predicate roles and authorized typed relations, never from scalar
    JSON shape or token overlap.
    """

    frame_id: str
    argument_unit_id: str
    slots: tuple[SemanticFlowSlotV1, ...] = Field(default_factory=tuple)
    edges: tuple[SemanticFlowEdgeV1, ...] = Field(default_factory=tuple)
    ordered_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_binding_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_lanes: tuple[AuthorityLaneV1, ...] = ("executable_hard",)
    content_digest: str = ""

    @field_validator("frame_id", "argument_unit_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("semantic argument frame identifiers must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _closed_bindings(self) -> "SemanticArgumentFrameV1":
        slot_ids = [item.slot_id for item in self.slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("semantic argument frame contains duplicate slot IDs")
        known_slot_ids = set(slot_ids)
        if len(self.ordered_slot_ids) != len(set(self.ordered_slot_ids)):
            raise ValueError("semantic argument frame contains duplicate ordered slot IDs")
        unknown_ordered = sorted(set(self.ordered_slot_ids) - known_slot_ids)
        if unknown_ordered:
            raise ValueError(
                "semantic argument frame orders unknown slots: " + ",".join(unknown_ordered)
            )
        if known_slot_ids and set(self.ordered_slot_ids) != known_slot_ids:
            raise ValueError("semantic argument frame must order every closed slot exactly once")
        edge_relation_ids = [edge.relation_id for edge in self.edges]
        if len(edge_relation_ids) != len(set(edge_relation_ids)):
            raise ValueError("semantic argument frame contains duplicate edge relation IDs")
        if len(self.unresolved_relation_ids) != len(set(self.unresolved_relation_ids)):
            raise ValueError("semantic argument frame contains duplicate unresolved relation IDs")
        overlap = set(edge_relation_ids).intersection(self.unresolved_relation_ids)
        if overlap:
            raise ValueError(
                "semantic argument frame marks relations both resolved and unresolved: "
                + ",".join(sorted(overlap))
            )
        known_fact_ids = set(self.fact_ids)
        known_claim_ids = set(self.claim_ids)
        known_relation_ids = {
            edge.relation_id for edge in self.edges
        }.union(self.unresolved_relation_ids).union(self.configuration_binding_relation_ids)
        for slot in self.slots:
            unknown_facts = set(slot.fact_ids) - known_fact_ids
            if unknown_facts:
                raise ValueError(
                    f"semantic flow slot {slot.slot_id} binds unknown facts: "
                    + ",".join(sorted(unknown_facts))
                )
            unknown_claims = set(slot.claim_ids) - known_claim_ids
            if unknown_claims:
                raise ValueError(
                    f"semantic flow slot {slot.slot_id} binds unknown claims: "
                    + ",".join(sorted(unknown_claims))
                )
            unknown_relations = set(slot.exact_relation_ids) - known_relation_ids
            if unknown_relations:
                raise ValueError(
                    f"semantic flow slot {slot.slot_id} binds unknown relations: "
                    + ",".join(sorted(unknown_relations))
                )
        for edge in self.edges:
            if not edge.source_slot_ids or not edge.target_slot_ids:
                raise ValueError(
                    f"semantic flow edge {edge.relation_id} requires exact source and target slots"
                )
            unknown_sources = set(edge.source_slot_ids) - known_slot_ids
            unknown_targets = set(edge.target_slot_ids) - known_slot_ids
            if unknown_sources or unknown_targets:
                raise ValueError(
                    f"semantic flow edge {edge.relation_id} binds unknown slots: "
                    + ",".join(sorted(unknown_sources | unknown_targets))
                )
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class ObligationMoveAssignmentV1(_MethodModel):
    """Exact placement of one completeness row onto a section/unit/move.

    Every critical/high row occurs exactly once among the plan's assignments
    with its full status, authority lane, sources, next action, and reason
    intact.  ``assigned`` rows require a section/unit/move; ``external_pending``
    rows keep the original lane and wait outside Writer input; ``unplaced``
    rows carry the unresolved reason and fail the plan gate.
    """

    obligation_id: str
    importance: Literal["critical", "high", "medium", "low"] = "medium"
    status: ReferenceMethodStatusV1 = "unverified_by_repository"
    authority_lane: AuthorityLaneV1 = "executable_hard"
    source_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    next_action: str = ""
    unresolved_reason: str = ""
    section_id: str = ""
    argument_unit_id: str = ""
    required_move: str = ""
    supporting_anchor_ids: tuple[str, ...] = Field(default_factory=tuple)
    placement_state: Literal["assigned", "external_pending", "unplaced"] = "unplaced"
    content_digest: str = ""

    @field_validator("obligation_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("obligation assignment requires an obligation id")
        return value.strip()

    @model_validator(mode="after")
    def _placement_closure(self) -> "ObligationMoveAssignmentV1":
        if self.placement_state == "assigned" and (
            not self.section_id or not self.argument_unit_id or not self.required_move
        ):
            raise ValueError(
                "assigned obligation rows require a section, unit, and move target"
            )
        if self.placement_state == "external_pending" and not self.required_move:
            raise ValueError(
                "external_pending obligation rows require a move target"
            )
        if self.placement_state == "unplaced" and (
            self.section_id or self.argument_unit_id or self.required_move
        ):
            raise ValueError(
                "unplaced obligation rows must not carry placement targets"
            )
        if self.placement_state == "unplaced" and not self.unresolved_reason:
            raise ValueError("unplaced obligation rows require an unresolved reason")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class MoveAuthorityProofV1(_MethodModel):
    """Move-specific authority proof: exact anchors and callback ownership.

    ``state`` transitions are monotone: an anchored/bridge move needs no
    request; an ``open`` move has an exact unresolved assignment; ``fulfilled``
    requires matching validated artifacts and a rebuilt digest; external
    author/empirical/literature lanes stay ``external_pending``.
    """

    section_id: str
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    move: RhetoricalMoveV1
    required: bool = False
    anchor_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_authority_lane: AuthorityLaneV1 = "executable_hard"
    owner_route: str = ""
    state: Literal["anchored", "bridge", "open", "fulfilled", "external_pending"] = "open"
    request_ids: tuple[str, ...] = Field(default_factory=tuple)
    fulfillment_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    fulfillment_artifact_digest: str = ""
    unanchored: bool = False
    unanchored_owner: str = ""
    content_digest: str = ""

    @field_validator("section_id", "move")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("move authority proof binding fields must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _state_closure(self) -> "MoveAuthorityProofV1":
        for label, values in (
            ("argument unit", self.argument_unit_ids),
            ("anchor", self.anchor_ids),
            ("obligation", self.unresolved_obligation_ids),
            ("request", self.request_ids),
            ("artifact", self.fulfillment_artifact_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"move authority proof contains duplicate {label} IDs")
        if self.state == "fulfilled":
            if (
                not self.request_ids
                or not self.fulfillment_artifact_ids
                or not self.fulfillment_artifact_digest
            ):
                raise ValueError("fulfilled move authority proofs require validated artifacts")
            if not self.fulfillment_artifact_digest.startswith("sha256:"):
                raise ValueError("fulfilled move authority proof requires a sha256 artifact digest")
        elif self.fulfillment_artifact_ids or self.fulfillment_artifact_digest:
            raise ValueError("non-fulfilled move authority proofs cannot carry artifacts")
        if self.state in {"anchored", "bridge"} and self.unresolved_obligation_ids:
            raise ValueError("anchored/bridge move authority proofs cannot carry unresolved rows")
        if self.state == "open" and not self.unresolved_obligation_ids and not self.unanchored:
            raise ValueError("open move authority proofs require an unresolved obligation id")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class MethodArgumentUnitV1(_MethodModel):
    """The smallest publication-level argument that can span several facts."""

    argument_unit_id: str
    section_role: str
    research_question: str
    design_objective: str = ""
    proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    positive_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveated_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    proposition_order: tuple[str, ...] = Field(default_factory=tuple)
    proposition_dependencies: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    concept_card_ids: tuple[str, ...] = Field(default_factory=tuple)
    verified_concept_card_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveated_concept_card_ids: tuple[str, ...] = Field(default_factory=tuple)
    concept_card_order: tuple[str, ...] = Field(default_factory=tuple)
    brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    verified_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveated_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    brief_order: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    author_rationale_ids: tuple[str, ...] = Field(default_factory=tuple)
    empirical_ids: tuple[str, ...] = Field(default_factory=tuple)
    literature_ids: tuple[str, ...] = Field(default_factory=tuple)
    behavior_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_expository_moves: tuple[RhetoricalMoveV1, ...] = Field(default_factory=tuple)
    unresolved_inputs: tuple[str, ...] = Field(default_factory=tuple)
    authority_lanes: tuple[AuthorityLaneV1, ...] = ("executable_hard",)
    source_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    # Exact authoring obligations carried by the compiler-authored semantic
    # stage that produced this unit.  This is a planning binding, not factual
    # authority; persisting it prevents later placement from guessing via an
    # obligation-id prefix or vocabulary overlap.
    source_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    supported: bool = True
    information_weight: float = 1.0
    semantic_frame: SemanticArgumentFrameV1 | None = None
    obligation_assignments: tuple[ObligationMoveAssignmentV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodArgumentUnitV1":
        if len(self.source_obligation_ids) != len(set(self.source_obligation_ids)):
            raise ValueError("argument unit contains duplicate source obligation ids")
        for label, values in (
            ("proposition", self.proposition_ids),
            ("positive proposition", self.positive_proposition_ids),
            ("caveated proposition", self.caveated_proposition_ids),
            ("proposition order", self.proposition_order),
            ("concept card", self.concept_card_ids),
            ("verified concept card", self.verified_concept_card_ids),
            ("caveated concept card", self.caveated_concept_card_ids),
            ("concept card order", self.concept_card_order),
            ("brief", self.brief_ids),
            ("verified brief", self.verified_brief_ids),
            ("caveated brief", self.caveated_brief_ids),
            ("brief order", self.brief_order),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"argument unit contains duplicate {label} ids")
        typed = set(self.positive_proposition_ids) | set(self.caveated_proposition_ids)
        if set(self.positive_proposition_ids) & set(self.caveated_proposition_ids):
            raise ValueError("argument unit proposition authority classes overlap")
        if typed and typed != set(self.proposition_ids):
            raise ValueError("argument unit proposition classes are not closed")
        if self.proposition_order and set(self.proposition_order) != set(self.proposition_ids):
            raise ValueError("argument unit proposition order is not closed")
        typed_concepts = set(self.verified_concept_card_ids) | set(
            self.caveated_concept_card_ids
        )
        if set(self.verified_concept_card_ids) & set(self.caveated_concept_card_ids):
            raise ValueError("argument unit concept authority classes overlap")
        if typed_concepts and typed_concepts != set(self.concept_card_ids):
            raise ValueError("argument unit concept classes are not closed")
        if (
            self.concept_card_order
            and set(self.concept_card_order) != set(self.concept_card_ids)
        ):
            raise ValueError("argument unit concept card order is not closed")
        typed_briefs = set(self.verified_brief_ids) | set(self.caveated_brief_ids)
        if set(self.verified_brief_ids) & set(self.caveated_brief_ids):
            raise ValueError("argument unit brief authority classes overlap")
        if typed_briefs and typed_briefs != set(self.brief_ids):
            raise ValueError("argument unit brief classes are not closed")
        if self.brief_order and set(self.brief_order) != set(self.brief_ids):
            raise ValueError("argument unit brief order is not closed")
        if self.brief_ids and self.concept_card_ids:
            raise ValueError("argument unit cannot bind briefs and concept cards together")
        normalized_edges = tuple(dict.fromkeys(
            (str(parent).strip(), str(child).strip())
            for parent, child in self.proposition_dependencies
            if str(parent).strip() and str(child).strip()
        ))
        if any(parent == child for parent, child in normalized_edges):
            raise ValueError("argument unit proposition dependency contains a self-edge")
        if any(set(edge) - set(self.proposition_ids) for edge in normalized_edges):
            raise ValueError("argument unit proposition dependency is not closed")
        indegree = {item: 0 for item in self.proposition_ids}
        children = {item: [] for item in self.proposition_ids}
        for parent, child in normalized_edges:
            indegree[child] += 1
            children[parent].append(child)
        queue = [item for item in self.proposition_ids if indegree[item] == 0]
        visited = 0
        while queue:
            parent = queue.pop(0)
            visited += 1
            for child in children[parent]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if visited != len(self.proposition_ids):
            raise ValueError("argument unit proposition dependency graph is cyclic")
        object.__setattr__(self, "proposition_dependencies", normalized_edges)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class SectionContentOpenSlotV1(_MethodModel):
    """Typed open slot owned by a specific authority lane."""

    slot_id: str
    owner: str
    authority_lane: str
    target_concept_key: str = ""
    slot_kind: str
    blocking_for_candidate: bool = False
    blocking_for_verified: bool = False


class SectionArgumentMoveV1(_MethodModel):
    move: RhetoricalMoveV1
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    paragraph_budget: int = 1
    information_budget: float = 1.0
    allowed_authority_lanes: tuple[AuthorityLaneV1, ...] = ("executable_hard",)
    required: bool = False
    unanchored: bool = False
    unanchored_owner: str = ""
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("paragraph_budget")
    @classmethod
    def _positive_budget(cls, value: int) -> int:
        return max(0, value)


class MethodUnitV2(_MethodModel):
    """Reader-sized mechanism unit used between Research and the Writer.

    A method unit is deliberately larger than an atomic fact and smaller than
    a section.  It records the question, ordered operation atoms, and the
    authority ceiling that the downstream prose transaction may use.  Evidence
    ids are carried for deterministic binding only; they are never prose.
    """

    schema_version: str = "2.0"
    method_unit_id: str
    section_id: str
    reader_question: str
    purpose: str
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    ordered_operations: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    entry_symbol_ids: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    shape_or_type_hints: tuple[str, ...] = Field(default_factory=tuple)
    return_value_descriptors: tuple[str, ...] = Field(default_factory=tuple)
    formalizable_signatures: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    formula_roles: tuple[str, ...] = Field(default_factory=tuple)
    evidence_spans: tuple[str, ...] = Field(default_factory=tuple)
    authority: Literal[
        "code_equivalent",
        "intent_specification",
        "conventional_notation",
        "mismatch_pending",
    ] = "intent_specification"
    intent_code_status: str = "unspecified"
    author_statement: str = ""
    facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator(
        "inputs", "outputs", "entry_symbol_ids", "conditions", "shape_or_type_hints",
        "return_value_descriptors", "formula_roles", "evidence_spans",
        "facet_ids", "fact_ids", "claim_ids", "equation_ids", "paragraph_ids",
        "argument_unit_ids",
    )
    @classmethod
    def _dedupe_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @field_validator("method_unit_id", "section_id", "reader_question", "purpose")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("method unit requires stable ids and reader-facing purpose")
        return value

    @model_validator(mode="after")
    def _authority_ceiling(self) -> "MethodUnitV2":
        operations = tuple(item for item in self.ordered_operations if isinstance(item, dict))
        operation_spans = {
            str(item.get(key) or "").strip()
            for item in operations
            for key in ("source_span_id", "span_id", "exact_span_id")
            if str(item.get(key) or "").strip()
        }
        has_repository_anchor = bool(self.evidence_spans or operation_spans)
        has_intent_anchor = bool(self.author_statement.strip()) or (
            any(
                marker in self.intent_code_status.strip().casefold()
                for marker in ("intent", "specification", "mismatch", "partial")
            )
        )
        if not self.ordered_operations and not has_repository_anchor and not has_intent_anchor:
            raise ValueError("method unit cannot be an empty mechanism shell")
        if self.authority == "code_equivalent" and not has_repository_anchor:
            raise ValueError("code-equivalent method unit requires an evidence span")
        if self.authority == "code_equivalent" and not self.formalizable_signatures:
            raise ValueError("code-equivalent method unit requires a formalizable signature")
        if self.authority in {"intent_specification", "conventional_notation"} and not has_intent_anchor:
            raise ValueError("intent method unit requires an explicit author specification")
        if self.authority == "mismatch_pending" and not (has_repository_anchor or has_intent_anchor):
            raise ValueError("mismatch-pending method unit requires evidence or author intent")
        if any(not isinstance(item, dict) for item in self.ordered_operations):
            raise ValueError("method unit operations must be typed operation objects")
        if any(not isinstance(item, dict) for item in self.formalizable_signatures):
            raise ValueError("method unit formalizable signatures must be typed objects")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class ParagraphWitnessTargetV1(_MethodModel):
    """One paragraph-local semantic target visible to the Writer."""

    target_id: str
    target_kind: Literal[
        "detail",
        "atom",
        "facet",
        "field",
        "slot",
        "edge",
        "formula",
        "claim",
        "equation",
    ]
    semantic_atom: str = ""
    paper_role: str = ""
    required_polarity: str = "unknown"
    required_conditions: tuple[str, ...] = Field(default_factory=tuple)
    allowed_anchor_ids: tuple[str, ...] = Field(default_factory=tuple)
    allowed_exact_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    authority_lane: str = "executable_hard"
    # These two fields are the Writer-facing surface contract.  They are
    # deliberately independent of ``authority_lane``: a target may have a
    # closed repository span while still being only partially aligned with
    # the author's compound statement and therefore require an intent/caveat
    # surface.  Keeping the distinction in the paragraph sidecar prevents
    # each downstream stage from re-interpreting the same target differently.
    surface_mode: str = "repository_statement"
    render_policy: str = "required"

    @field_validator("target_id")
    @classmethod
    def _target_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("paragraph witness target requires an id")
        return str(value).strip()

    @field_validator(
        "required_conditions", "allowed_anchor_ids", "allowed_exact_excerpts",
    )
    @classmethod
    def _dedupe_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @model_validator(mode="after")
    def _authorized_anchor_required(self) -> "ParagraphWitnessTargetV1":
        # A closed target without any semantic/exact anchor would allow a
        # declared ID to become a witness by assertion alone.  Formula targets
        # may use their package route as the exact anchor, but still need an
        # obligation/package anchor id.
        if not (
            self.semantic_atom.strip()
            or self.required_conditions
            or self.allowed_anchor_ids
            or self.allowed_exact_excerpts
        ):
            raise ValueError("paragraph witness target requires a non-empty authorized anchor")
        object.__setattr__(self, "surface_mode", _earned_witness_surface_mode(self))
        return self


def _earned_witness_surface_mode(target: ParagraphWitnessTargetV1) -> str:
    """Keep ``repository_statement`` only when executable evidence earned it.

    Legacy MethodUnit dumps omitted ``surface_mode``.  The field default is
    ``repository_statement``, which would otherwise tell the Writer to state
    only supplied code operations for author-attested story facets.  Unearned
    defaults become Candidate ``author_specification`` so Motivation /
    framework units can expand author statements without claiming a closed
    implementation binding.
    """

    current = str(target.surface_mode or "").strip() or "repository_statement"
    if current != "repository_statement":
        return current
    lane = str(target.authority_lane or "").strip().casefold()
    has_anchor = bool(target.allowed_anchor_ids or target.allowed_exact_excerpts)
    executable_lanes = {
        "executable_hard",
        "configuration_resolved",
        "formal_derivation",
    }
    if lane in executable_lanes and has_anchor:
        return "repository_statement"
    return "author_specification"


class ParagraphWitnessContractV1(_MethodModel):
    """Closed paragraph-local contract shared by Writer and validators."""

    schema_version: str = "1.0"
    paragraph_id: str
    rhetorical_goal: str = ""
    targets: tuple[ParagraphWitnessTargetV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("paragraph_id")
    @classmethod
    def _paragraph_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("paragraph witness contract requires a paragraph id")
        return str(value).strip()

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "ParagraphWitnessContractV1":
        keys = [(item.target_kind, item.target_id) for item in self.targets]
        if len(keys) != len(set(keys)):
            raise ValueError("paragraph witness contract contains duplicate targets")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self

    @property
    def required_anchor_map(self) -> dict[tuple[str, str], tuple[str, ...]]:
        anchors: dict[tuple[str, str], tuple[str, ...]] = {}
        for item in self.targets:
            values = list(item.allowed_exact_excerpts)
            semantic_atom = str(item.semantic_atom or "").strip()
            # ``formal expression`` is a type label, not a source witness;
            # formula rendering is checked by the exact obligation/package
            # route instead.  All other semantic atoms and explicit
            # conditions are useful paragraph-local anchors even when the
            # Writer paraphrases the repository excerpt.
            if semantic_atom and semantic_atom.casefold() not in {
                "formal expression", "formula"
            }:
                values.append(semantic_atom)
            values.extend(item.required_conditions)
            values = list(dict.fromkeys(value.strip() for value in values if value.strip()))
            if values:
                anchors[(item.target_kind, item.target_id)] = tuple(values)
        return anchors

    @property
    def target_ids_by_kind(self) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        for item in self.targets:
            result.setdefault(item.target_kind, []).append(item.target_id)
        return {key: tuple(value) for key, value in result.items()}


class SectionParagraphPlanV1(_MethodModel):
    """Ordered paragraph contract derived from semantic slots.

    Paragraph plans organize Writer output; they do not authorize facts.  All
    positive content still requires the referenced semantic frame/evidence
    bindings and the normal Candidate/Verified gates.
    """

    paragraph_id: str
    paragraph_role: Literal[
        "overview",
        "construction",
        "step_sequence",
        "formula",
        "interface",
        "output",
        "mismatch",
    ] = "step_sequence"
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_field_candidate_ids: tuple[str, ...] = Field(default_factory=tuple)
    support_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_publication_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    ordered_semantic_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_edge_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    expected_sentence_range: tuple[int, int] = (1, 4)
    transition_from: str = ""
    transition_to: str = ""
    witness_contract: ParagraphWitnessContractV1 | None = None
    content_digest: str = ""

    @field_validator("paragraph_id")
    @classmethod
    def _paragraph_required(cls, value: str) -> str:
        if not str(value).strip():
            raise ValueError("paragraph plan requires a paragraph id")
        return str(value).strip()

    @field_validator(
        "argument_unit_ids",
        "required_facet_ids",
        "ordered_semantic_slot_ids",
        "required_edge_ids",
        "formula_obligation_ids",
        "required_field_candidate_ids",
        "support_slot_ids",
        "required_publication_slot_ids",
    )
    @classmethod
    def _dedupe_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _clean_tuple(value)

    @field_validator("expected_sentence_range")
    @classmethod
    def _sentence_range(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2 or value[0] < 1 or value[1] < value[0]:
            raise ValueError("paragraph plan sentence range must be increasing")
        return value

    @model_validator(mode="after")
    def _digest(self) -> "SectionParagraphPlanV1":
        ordered = set(self.ordered_semantic_slot_ids)
        if not set(self.support_slot_ids).issubset(ordered):
            raise ValueError("paragraph support slots are not present in ordered semantic slots")
        if not set(self.required_publication_slot_ids).issubset(ordered):
            raise ValueError("paragraph publication slots are not present in ordered semantic slots")
        if self.witness_contract is not None and self.witness_contract.paragraph_id != self.paragraph_id:
            raise ValueError("paragraph witness contract id does not match paragraph plan")
        object.__setattr__(self, "content_digest", _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        ))
        return self


class SectionArgumentGraphV1(_MethodModel):
    """Rhetorical graph for one Method section; no final prose is stored."""

    section_id: str
    heading: str
    reader_question: str
    argument_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    moves: tuple[SectionArgumentMoveV1, ...] = Field(default_factory=tuple)
    paragraphs: tuple[SectionParagraphPlanV1, ...] = Field(default_factory=tuple)
    dependencies: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_inputs: tuple[str, ...] = Field(default_factory=tuple)
    depth_budget: int = 1
    page_budget: float = 1.0
    incomplete: bool = False
    # WP1 section content contract (single authority within the plan graph).
    story_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    heading_constraints: tuple[str, ...] = Field(default_factory=tuple)
    primary_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    supporting_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    audit_only_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    primary_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    supporting_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_dataflow_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_not_applicable: bool = False
    formula_not_applicable_reason: str = ""
    open_slots: tuple[SectionContentOpenSlotV1, ...] = Field(default_factory=tuple)
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
    """A scoped request emitted while a section is being written.

    ``concept_key`` / ``missing_parts`` / ``evidence_refs_used`` are the
    Stage 5 concept-bearing payload: when the request targets a caveated
    concept card, they record which concept is unresolved, which parts of
    it are missing, and which evidence refs the card already binds.  They
    are optional (proposition-lane requests omit them) and digest-covered.
    """

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
    status: Literal["open", "partial", "fulfilled", "author_review", "blocked"] = "open"
    fulfilled_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    concept_key: str = ""
    missing_parts: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs_used: tuple[str, ...] = Field(default_factory=tuple)
    baseline_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_story_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    target_brief_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_clause_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    mandatory_missing_slots: tuple[str, ...] = Field(default_factory=tuple)
    baseline_fact_fingerprints: tuple[str, ...] = Field(default_factory=tuple)
    baseline_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    excluded_audit_concept_keys: tuple[str, ...] = Field(default_factory=tuple)
    satisfied_slots: tuple[str, ...] = Field(default_factory=tuple)
    remaining_slots: tuple[str, ...] = Field(default_factory=tuple)
    # Unified mechanism callback bindings.  They are optional on the legacy
    # request so old section-scoped artifacts remain readable, but when
    # present they identify the exact technical owner rather than granting a
    # whole section a new evidence scope.
    mechanism_id: str = ""
    target_detail_id: str = ""
    target_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_kind: MechanismResearchUnresolvedKindV1 | Literal[""] = ""
    baseline_context_digest: str = ""
    content_digest: str = ""

    @field_validator("request_id", "section_id", "argument_unit_id", "exact_question")
    @classmethod
    def _required_binding_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("writing research request binding text must not be empty")
        return value.strip()

    @field_validator("concept_key")
    @classmethod
    def _optional_concept_key(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def _digest(self) -> "WritingResearchRequestV1":
        object.__setattr__(self, "content_digest", _digest(self.model_dump(mode="json", exclude={"content_digest"})))
        return self


class WritingResearchCallbackArtifactV1(_MethodModel):
    """Validated artifact that authorizes resuming exactly one Writer request."""

    artifact_id: str
    request_id: str
    section_id: str
    argument_unit_id: str
    authority_lane: AuthorityLaneV1
    artifact_ref: str
    artifact_digest: str
    validated: bool = False
    # Optional V2 owner/delta metadata.  The old section/unit binding remains
    # required for legacy callback artifacts; unified callers can additionally
    # prove which mechanism/detail changed without widening the resume scope.
    mechanism_id: str = ""
    target_detail_id: str = ""
    target_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_kind: MechanismResearchUnresolvedKindV1 | Literal[""] = ""
    baseline_context_digest: str = ""
    current_context_digest: str = ""
    semantic_delta_digest: str = ""
    new_source_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_detail_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validated_binding(self) -> "WritingResearchCallbackArtifactV1":
        if not all((
            self.artifact_id.strip(), self.request_id.strip(), self.section_id.strip(),
            self.argument_unit_id.strip(), self.artifact_ref.strip(),
        )):
            raise ValueError("writing callback artifact binding fields must not be empty")
        if not self.artifact_digest.startswith("sha256:"):
            raise ValueError("writing callback artifact requires a sha256 digest")
        if not self.validated:
            raise ValueError("writing callback artifact must pass its owning validator")
        for field_name in (
            "baseline_context_digest",
            "current_context_digest",
            "semantic_delta_digest",
        ):
            value = getattr(self, field_name)
            if value and not value.startswith("sha256:"):
                raise ValueError(f"{field_name} must be a sha256 digest when present")
        return self


class MechanismResearchRequestV2(_MethodModel):
    """Mechanism/detail-owned callback request for an unresolved closure item.

    This is intentionally independent of section and paragraph ids.  A
    narrative plan may later locate the affected paragraph, but it cannot
    redefine the technical owner of the research request.
    """

    request_id: str
    mechanism_id: str
    target_detail_id: str = ""
    unresolved_kind: MechanismResearchUnresolvedKindV1
    exact_question: str
    candidate_symbols_or_terms: tuple[str, ...] = Field(default_factory=tuple)
    baseline_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    baseline_context_digest: str
    target_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    # Placement is derived from the frozen narrative plan and is used only to
    # select the smallest Writer resume scope.  It is deliberately separate
    # from the mechanism/detail owner above: a paragraph can consume a detail
    # but cannot redefine which source gap the callback owns.
    affected_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @field_validator("request_id", "mechanism_id", "exact_question")
    @classmethod
    def _required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mechanism callback binding text must not be empty")
        return value

    @field_validator("baseline_context_digest")
    @classmethod
    def _context_digest(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("sha256:"):
            raise ValueError("mechanism callback requires a sha256 baseline_context_digest")
        return value

    @model_validator(mode="after")
    def _digest(self) -> "MechanismResearchRequestV2":
        computed_digest = _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        )
        if self.content_digest and self.content_digest != computed_digest:
            raise ValueError("mechanism callback request content digest mismatch")
        object.__setattr__(
            self,
            "content_digest",
            computed_digest,
        )
        return self


class MechanismResearchCallbackArtifactV2(_MethodModel):
    """Validated mechanism-owned callback artifact carrying semantic delta."""

    artifact_id: str
    request_id: str
    mechanism_id: str
    target_detail_id: str = ""
    unresolved_kind: MechanismResearchUnresolvedKindV1
    artifact_ref: str
    artifact_digest: str
    baseline_context_digest: str
    current_context_digest: str
    semantic_delta_digest: str
    target_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_source_operation_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_source_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_condition_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_configuration_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_detail_ids: tuple[str, ...] = Field(default_factory=tuple)
    new_atom_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_count_before: int | None = Field(default=None, ge=0)
    unresolved_count_after: int | None = Field(default=None, ge=0)
    core_detail_count_before: int | None = Field(default=None, ge=0)
    core_detail_count_after: int | None = Field(default=None, ge=0)
    remaining_gap_ids_before: tuple[str, ...] = Field(default_factory=tuple)
    remaining_gap_ids_after: tuple[str, ...] = Field(default_factory=tuple)
    affected_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    affected_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    validated: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_artifact(self) -> "MechanismResearchCallbackArtifactV2":
        if not all((self.artifact_id.strip(), self.request_id.strip(), self.mechanism_id.strip(), self.artifact_ref.strip())):
            raise ValueError("mechanism callback artifact binding fields must not be empty")
        for field_name in (
            "artifact_digest",
            "baseline_context_digest",
            "current_context_digest",
            "semantic_delta_digest",
        ):
            if not getattr(self, field_name).startswith("sha256:"):
                raise ValueError(f"{field_name} must be a sha256 digest")
        if not self.validated:
            raise ValueError("mechanism callback artifact must pass its owning validator")
        if self.current_context_digest == self.baseline_context_digest:
            raise ValueError(
                "mechanism callback artifact must change the context digest"
            )
        unresolved_improved = (
            self.unresolved_count_before is not None
            and self.unresolved_count_after is not None
            and self.unresolved_count_after < self.unresolved_count_before
        )
        core_improved = (
            self.core_detail_count_before is not None
            and self.core_detail_count_after is not None
            and self.core_detail_count_after > self.core_detail_count_before
        )
        gaps_improved = bool(
            self.remaining_gap_ids_before
            and len(set(self.remaining_gap_ids_after))
            < len(set(self.remaining_gap_ids_before))
        )
        source_or_semantic_gain = any((
            self.new_source_operation_ids,
            self.new_source_span_ids,
            self.new_fact_ids,
            self.new_condition_ids,
            self.new_configuration_ids,
            self.new_detail_ids,
            self.new_atom_ids,
        ))
        if not (unresolved_improved or core_improved or gaps_improved or source_or_semantic_gain):
            raise ValueError(
                "mechanism callback artifact has no semantic delta"
            )
        computed_digest = _digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        )
        if self.content_digest and self.content_digest != computed_digest:
            raise ValueError("mechanism callback artifact content digest mismatch")
        object.__setattr__(
            self,
            "content_digest",
            computed_digest,
        )
        return self


class WritingResearchCallbackBundleV1(_MethodModel):
    """Persistent hand-off between a Writer turn and its owning researcher.

    The bundle is deliberately an artifact rather than an in-memory callback
    argument.  A blocked/incomplete authoring stage can therefore be resumed
    after the owning authority has validated a result, while the Writer still
    receives only the affected section and the exact request binding.
    """

    schema_version: str = "1.0"
    requests: tuple[WritingResearchRequestV1, ...] = Field(default_factory=tuple)
    mechanism_requests: tuple[MechanismResearchRequestV2, ...] = Field(default_factory=tuple)
    artifacts: dict[str, tuple[WritingResearchCallbackArtifactV1, ...]] = Field(
        default_factory=dict
    )
    mechanism_artifacts: dict[str, tuple[MechanismResearchCallbackArtifactV2, ...]] = Field(
        default_factory=dict
    )
    requested_resume_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    resume_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    mechanism_resume_section_ids: tuple[str, ...] = Field(default_factory=tuple)
    mechanism_resume_paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @property
    def _locally_owned_lanes(self) -> frozenset[str]:
        return frozenset({
            "executable_hard", "configuration_resolved", "formal_derivation",
        })

    @model_validator(mode="after")
    def _validate_bindings(self) -> "WritingResearchCallbackBundleV1":
        request_ids = [item.request_id for item in self.requests]
        mechanism_request_ids = [item.request_id for item in self.mechanism_requests]
        if len(request_ids) != len(set(request_ids)) or len(mechanism_request_ids) != len(set(mechanism_request_ids)):
            raise ValueError("writing callback bundle contains duplicate request IDs")
        if set(request_ids).intersection(mechanism_request_ids):
            raise ValueError("writing callback bundle contains duplicate request IDs across request lanes")
        requests_by_id = {item.request_id: item for item in self.requests}
        known_section_ids = {item.section_id for item in self.requests}
        # ``requested_resume_section_ids`` is truthful telemetry of the set the
        # previous run asked to resume; it may include sections without a
        # current request entry, so only the admitted set is restricted to
        # known sections.
        unknown_admitted_sections = sorted(
            set(self.resume_section_ids) - known_section_ids
        )
        if unknown_admitted_sections:
            raise ValueError(
                "writing callback bundle contains unknown resume sections: "
                + ",".join(unknown_admitted_sections)
            )
        # A section is resume-eligible (admitted) only when every blocking
        # locally owned request selected for it is fulfilled by a validated
        # artifact.  The persisted ``resume_section_ids`` marker is the
        # admission set: the writer clears it after a section is actually
        # regenerated, and it is never derived from request status alone here
        # (or fulfillment would force a full-document rewrite forever).
        # Open requests must not populate the marker; external-pending rows
        # stay pending and are never replayed as if fulfilled.
        # ``requested_resume_section_ids`` records the sections the previous
        # run asked to resume for truthful telemetry.
        open_local_sections = {
            item.section_id for item in self.requests
            if item.status == "open"
            and item.required_authority_lane in self._locally_owned_lanes
        }
        section_ids = set(self.resume_section_ids) - open_local_sections
        for request_id, items in self.artifacts.items():
            request = requests_by_id.get(request_id)
            if request is None:
                raise ValueError(f"callback artifact bundle contains unknown request: {request_id}")
            if request.status == "open":
                raise ValueError(
                    f"open callback request cannot contain validated artifacts: {request_id}"
                )
            for artifact in items:
                if (
                    artifact.request_id != request.request_id
                    or artifact.section_id != request.section_id
                    or artifact.argument_unit_id != request.argument_unit_id
                    or artifact.authority_lane != request.required_authority_lane
                ):
                    raise ValueError(
                        f"callback artifact does not match request binding: {request_id}"
                    )
        for request in self.requests:
            items = self.artifacts.get(request.request_id, ())
            artifact_ids = tuple(item.artifact_id for item in items)
            if request.status == "fulfilled":
                if not items or not request.fulfilled_artifact_ids:
                    raise ValueError(
                        f"fulfilled callback request lacks validated artifacts: {request.request_id}"
                    )
                if set(artifact_ids) != set(request.fulfilled_artifact_ids):
                    raise ValueError(
                        f"fulfilled callback artifact IDs do not match request: {request.request_id}"
                    )
            elif request.status == "partial":
                # Partial is real progress: remaining slots stay open, but any
                # recorded artifact IDs must still match the validated items.
                if request.fulfilled_artifact_ids and set(artifact_ids) != set(
                    request.fulfilled_artifact_ids
                ):
                    raise ValueError(
                        "partial callback artifact IDs do not match request: "
                        + request.request_id
                    )
            elif request.fulfilled_artifact_ids:
                raise ValueError(
                    f"non-fulfilled callback request contains fulfilled artifact IDs: {request.request_id}"
                )
        mechanism_requests_by_id = {
            item.request_id: item for item in self.mechanism_requests
        }
        for request_id, items in self.mechanism_artifacts.items():
            request = mechanism_requests_by_id.get(request_id)
            if request is None:
                raise ValueError(
                    f"mechanism callback artifact bundle contains unknown request: {request_id}"
                )
            for artifact in items:
                if (
                    artifact.request_id != request.request_id
                    or artifact.mechanism_id != request.mechanism_id
                    or artifact.target_detail_id != request.target_detail_id
                    or artifact.unresolved_kind != request.unresolved_kind
                    or artifact.baseline_context_digest != request.baseline_context_digest
                    or tuple(artifact.target_operation_ids) != tuple(request.target_operation_ids)
                    or tuple(artifact.target_atom_ids) != tuple(request.target_atom_ids)
                ):
                    raise ValueError(
                        f"mechanism callback artifact does not match request binding: {request_id}"
                    )
                if set(artifact.affected_section_ids) - set(request.affected_section_ids):
                    raise ValueError(
                        f"mechanism callback artifact widens affected sections: {request_id}"
                    )
                if set(artifact.affected_paragraph_ids) - set(request.affected_paragraph_ids):
                    raise ValueError(
                        f"mechanism callback artifact widens affected paragraphs: {request_id}"
                    )
        mechanism_artifact_ids = [
            artifact.artifact_id
            for items in self.mechanism_artifacts.values()
            for artifact in items
        ]
        if len(mechanism_artifact_ids) != len(set(mechanism_artifact_ids)):
            raise ValueError(
                "mechanism callback bundle contains duplicate artifact IDs"
            )
        known_mechanism_sections = {
            section_id
            for request in self.mechanism_requests
            for section_id in request.affected_section_ids
        }
        known_mechanism_sections.update(
            section_id
            for items in self.mechanism_artifacts.values()
            for artifact in items
            for section_id in artifact.affected_section_ids
        )
        unknown_mechanism_sections = sorted(
            set(self.mechanism_resume_section_ids) - known_mechanism_sections
        )
        if unknown_mechanism_sections:
            raise ValueError(
                "writing callback bundle contains unknown mechanism resume sections: "
                + ",".join(unknown_mechanism_sections)
            )
        known_mechanism_paragraphs = {
            paragraph_id
            for request in self.mechanism_requests
            for paragraph_id in request.affected_paragraph_ids
        }
        known_mechanism_paragraphs.update(
            paragraph_id
            for items in self.mechanism_artifacts.values()
            for artifact in items
            for paragraph_id in artifact.affected_paragraph_ids
        )
        unknown_mechanism_paragraphs = sorted(
            set(self.mechanism_resume_paragraph_ids) - known_mechanism_paragraphs
        )
        if unknown_mechanism_paragraphs:
            raise ValueError(
                "writing callback bundle contains unknown mechanism resume paragraphs: "
                + ",".join(unknown_mechanism_paragraphs)
            )
        object.__setattr__(self, "resume_section_ids", tuple(sorted(section_ids)))
        object.__setattr__(
            self,
            "mechanism_resume_section_ids",
            tuple(dict.fromkeys(str(item) for item in self.mechanism_resume_section_ids if str(item).strip())),
        )
        object.__setattr__(
            self,
            "mechanism_resume_paragraph_ids",
            tuple(dict.fromkeys(str(item) for item in self.mechanism_resume_paragraph_ids if str(item).strip())),
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed_digest = _digest(payload)
        if self.content_digest and self.content_digest != computed_digest:
            raise ValueError("writing callback bundle content digest mismatch")
        object.__setattr__(self, "content_digest", computed_digest)
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
    """Architect output: section graph plus dynamic budget, no final text.

    The plan binds every typed obligation assignment (assigned, external
    pending, and unplaced) and every move-specific authority proof so the
    digest covers the complete placement/authority surface, not only trace
    dictionaries.
    """

    plan_id: str
    method_name: str = ""
    sections: tuple[SectionArgumentGraphV1, ...] = Field(default_factory=tuple)
    argument_units: tuple[MethodArgumentUnitV1, ...] = Field(default_factory=tuple)
    method_units: tuple[MethodUnitV2, ...] = Field(default_factory=tuple)
    venue: str = ""
    audience: str = ""
    total_page_budget: float = 0.0
    incomplete_sections: tuple[str, ...] = Field(default_factory=tuple)
    obligation_assignments: tuple[ObligationMoveAssignmentV1, ...] = Field(default_factory=tuple)
    move_authority_proofs: tuple[MoveAuthorityProofV1, ...] = Field(default_factory=tuple)
    critical_high_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    completeness_digest: str = ""
    content_digest: str = ""

    def assignments_by_obligation(self) -> dict[str, ObligationMoveAssignmentV1]:
        return {item.obligation_id: item for item in self.obligation_assignments}

    def proofs_by_key(self) -> dict[tuple[str, str], MoveAuthorityProofV1]:
        return {(item.section_id, item.move): item for item in self.move_authority_proofs}

    @model_validator(mode="after")
    def _closed_bindings_and_digest(self) -> "MethodSectionPlanV2":
        section_ids = [item.section_id for item in self.sections]
        unit_ids = [item.argument_unit_id for item in self.argument_units]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("method section plan contains duplicate section IDs")
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("method section plan contains duplicate argument unit IDs")
        method_unit_ids = [item.method_unit_id for item in self.method_units]
        if len(method_unit_ids) != len(set(method_unit_ids)):
            raise ValueError("method section plan contains duplicate method unit IDs")
        known_sections = set(section_ids)
        known_units = set(unit_ids)
        paragraphs_by_section: dict[str, set[str]] = {
            section.section_id: {
                paragraph.paragraph_id for paragraph in section.paragraphs
            }
            for section in self.sections
        }
        sections_by_unit: dict[str, set[str]] = {}
        moves_by_section: dict[str, set[str]] = {}
        for section in self.sections:
            if len(section.argument_unit_ids) != len(set(section.argument_unit_ids)):
                raise ValueError(f"section {section.section_id} contains duplicate unit IDs")
            move_ids = [item.move for item in section.moves]
            if len(move_ids) != len(set(move_ids)):
                raise ValueError(f"section {section.section_id} contains duplicate moves")
            unknown_units = set(section.argument_unit_ids) - known_units
            if unknown_units:
                raise ValueError(
                    f"section {section.section_id} binds unknown units: "
                    + ",".join(sorted(unknown_units))
                )
            for unit_id in section.argument_unit_ids:
                sections_by_unit.setdefault(unit_id, set()).add(section.section_id)
            moves_by_section[section.section_id] = {item.move for item in section.moves}

        for method_unit in self.method_units:
            if method_unit.section_id not in known_sections:
                raise ValueError(
                    f"method unit {method_unit.method_unit_id} binds an unknown section"
                )
            if not method_unit.paragraph_ids:
                raise ValueError(
                    f"method unit {method_unit.method_unit_id} requires paragraph bindings"
                )
            unknown_paragraphs = set(method_unit.paragraph_ids) - paragraphs_by_section.get(
                method_unit.section_id, set()
            )
            if unknown_paragraphs:
                raise ValueError(
                    f"method unit {method_unit.method_unit_id} binds unknown paragraphs: "
                    + ",".join(sorted(unknown_paragraphs))
                )
            unknown_method_units = set(method_unit.argument_unit_ids) - known_units
            if unknown_method_units:
                raise ValueError(
                    f"method unit {method_unit.method_unit_id} binds unknown argument units: "
                    + ",".join(sorted(unknown_method_units))
                )
            if any(
                method_unit.section_id not in sections_by_unit.get(unit_id, set())
                for unit_id in method_unit.argument_unit_ids
            ):
                raise ValueError(
                    f"method unit {method_unit.method_unit_id} crosses an argument-unit section"
                )

        assignment_ids = [item.obligation_id for item in self.obligation_assignments]
        if len(assignment_ids) != len(set(assignment_ids)):
            raise ValueError("method section plan contains duplicate obligation assignments")
        assignment_by_id = {
            item.obligation_id: item for item in self.obligation_assignments
        }
        if len(self.critical_high_obligation_ids) != len(set(self.critical_high_obligation_ids)):
            raise ValueError("method section plan contains duplicate critical/high obligation IDs")
        if self.critical_high_obligation_ids:
            if not self.completeness_digest.startswith("sha256:"):
                raise ValueError("closed critical/high obligations require a completeness digest")
            if set(assignment_ids) != set(self.critical_high_obligation_ids):
                raise ValueError("method section plan obligation assignments are not complete")
        for assignment in self.obligation_assignments:
            if assignment.placement_state == "unplaced":
                continue
            if assignment.placement_state == "external_pending" and (
                not assignment.section_id and not assignment.argument_unit_id
            ):
                # A genuinely external owner (author/empirical/literature) may
                # wait outside the Writer input with no local section/unit
                # binding; the required move and original authority lane stay
                # intact so routing remains explicit.
                continue
            if assignment.section_id not in known_sections:
                raise ValueError(
                    f"obligation {assignment.obligation_id} binds unknown section"
                )
            if assignment.argument_unit_id not in known_units:
                raise ValueError(
                    f"obligation {assignment.obligation_id} binds unknown argument unit"
                )
            if assignment.section_id not in sections_by_unit.get(
                assignment.argument_unit_id, set()
            ):
                raise ValueError(
                    f"obligation {assignment.obligation_id} crosses its unit section binding"
                )
            if assignment.required_move not in moves_by_section.get(assignment.section_id, set()):
                raise ValueError(
                    f"obligation {assignment.obligation_id} binds an unknown section move"
                )

        proof_keys = [(item.section_id, item.move) for item in self.move_authority_proofs]
        if len(proof_keys) != len(set(proof_keys)):
            raise ValueError("method section plan contains duplicate move authority proofs")
        for proof in self.move_authority_proofs:
            if proof.section_id not in known_sections:
                raise ValueError("move authority proof binds an unknown section")
            if proof.move not in moves_by_section.get(proof.section_id, set()):
                raise ValueError("move authority proof binds an unknown section move")
            unknown_units = set(proof.argument_unit_ids) - known_units
            if unknown_units:
                raise ValueError(
                    "move authority proof binds unknown units: "
                    + ",".join(sorted(unknown_units))
                )
            if any(
                proof.section_id not in sections_by_unit.get(unit_id, set())
                for unit_id in proof.argument_unit_ids
            ):
                raise ValueError("move authority proof crosses a unit section binding")
            unknown_obligations = set(proof.unresolved_obligation_ids) - set(assignment_by_id)
            if unknown_obligations and not getattr(proof, "unanchored", False):
                raise ValueError(
                    "move authority proof binds unknown obligations: "
                    + ",".join(sorted(unknown_obligations))
                )
            for obligation_id in proof.unresolved_obligation_ids:
                assignment = assignment_by_id[obligation_id]
                if (
                    assignment.section_id != proof.section_id
                    or assignment.required_move != proof.move
                ):
                    raise ValueError(
                        f"move authority proof does not match obligation {obligation_id}"
                    )
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
        if kind in {"rationale_check", "mismatch_check"}:
            lane: AuthorityLaneV1 = "author_attested"
            obligation_class = "rationale" if kind == "rationale_check" else "capability"
        elif kind == "high_risk_claim":
            lane = "external_literature"
            obligation_class = "capability"
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
        status = _resolve_reference_status(
            obligation,
            coverage_status=coverage_status,
            coverage_reason=str(
                getattr(coverage, "rationale", "")
                or getattr(coverage, "reason", "")
            ),
        )
        matched_fact_ids, matched_relation_ids = _coverage_matched_evidence(coverage)
        claim_ids = tuple(
            str(claim.claim_id)
            for claim in claims
            if obligation.obligation_id in tuple(getattr(claim, "covers_obligation_ids", ()))
        )
        if status == "supported_by_repository" and not claim_ids:
            status = "partially_supported_by_repository"
        reason = str(getattr(coverage, "rationale", "")) if coverage is not None else "No coverage artifact is available."
        next_action = {
            "unverified_by_repository": "run scoped repository research",
            "paper_code_mismatch": "ask the author to reconcile the paper statement with the active code path",
            "author_confirmation_required": "request an explicit author confirmation artifact",
            "external_evidence_required": "collect and validate the required external or empirical evidence",
            "formalization_required": "run the Formalization Agent with explicit assumptions",
            "explicit_code_gap": "ask the author to accept the scoped code gap or authorize a wider search scope",
            "out_of_scope": "retain the unit in the review sidecar with its declared scope reason",
        }.get(status, "")
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
            matched_fact_ids=matched_fact_ids,
            matched_relation_ids=matched_relation_ids,
            reason=reason,
            next_action=next_action,
        ))
    return MethodCompletenessMatrixV1(
        repo_snapshot_id=agenda.repo_snapshot_id,
        project_tree_hash=agenda.project_tree_hash,
        agenda_digest=agenda.content_digest,
        items=tuple(items),
    )


def _coverage_matched_evidence(coverage: Any | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract the coverage compiler's matched fact/relation handles.

    The V2 coverage report carries per-target ``matched_fact_ids`` and
    ``matched_relations``; claim-bearing rows already expose their evidence
    through ``source_artifact_ids``, but claim-less partial/gap rows would
    otherwise lose every evidence handle.  Empty when no coverage artifact is
    available.
    """

    if coverage is None:
        return (), ()
    fact_ids: list[str] = []
    relation_ids: list[str] = []
    for target in getattr(coverage, "target_alignments", ()) or ():
        fact_ids.extend(
            str(item)
            for item in (getattr(target, "matched_fact_ids", ()) or ())
            if str(item)
        )
        relation_ids.extend(
            str(item)
            for item in (getattr(target, "matched_relations", ()) or ())
            if str(item)
        )
    return (
        tuple(dict.fromkeys(fact_ids)),
        tuple(dict.fromkeys(relation_ids)),
    )


def _resolve_reference_status(
    obligation: ReferenceMethodObligationV1,
    *,
    coverage_status: str,
    coverage_reason: str,
) -> ReferenceMethodStatusV1:
    """Preserve the full nine-state contract without authority collapse."""

    if obligation.status != "unverified_by_repository":
        return obligation.status
    if coverage_status == "supported":
        return "supported_by_repository"
    if coverage_status == "partial":
        return "partially_supported_by_repository"
    if coverage_status == "explicit_gap":
        return "explicit_code_gap"
    reason = coverage_reason.lower()
    if "mismatch" in reason or "contradict" in reason:
        return "paper_code_mismatch"
    if obligation.authority_lane == "author_attested":
        return "author_confirmation_required"
    if obligation.authority_lane in {"external_literature", "empirical_artifact"}:
        return "external_evidence_required"
    if obligation.authority_lane == "formal_derivation" or obligation.obligation_class == "equation":
        return "formalization_required"
    if obligation.authority_lane == "expository_bridge":
        return "out_of_scope"
    return "unverified_by_repository"


class SectionSentenceContentWitnessV1(_MethodModel):
    """Sentence-scoped content witness binding prose to exact repository evidence."""

    section_id: str
    char_start: int
    char_end: int
    sentence_text: str = ""
    concept_key: str = ""
    exact_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_or_formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    authority_lane: str = ""
    completed_move_ids: tuple[str, ...] = Field(default_factory=tuple)
    reverse_validation_status: str = "pending"
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "SectionSentenceContentWitnessV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class SectionContentWitnessSetV1(_MethodModel):
    schema_version: str = "1.0"
    witnesses: tuple[SectionSentenceContentWitnessV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "SectionContentWitnessSetV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


__all__ = [
    "AUTHORITY_LANES",
    "AuthorityLaneV1",
    "ConfigurationClaimSetV1",
    "ConfigurationClaimV1",
    "ConfigurationStateV1",
    "MechanismResearchUnresolvedKindV1",
    "MethodArgumentKindV1",
    "MethodArgumentUnitV1",
    "MethodCompletenessItemV1",
    "MethodCompletenessMatrixV1",
    "MethodSectionPlanV2",
    "MethodUnitV2",
    "ProofObligationV1",
    "REFERENCE_METHOD_STATUSES",
    "ReferenceMethodAgendaV1",
    "ReferenceMethodObligationV1",
    "ReferenceMethodStatusV1",
    "RHETORICAL_MOVES",
    "RhetoricalMoveV1",
    "SectionArgumentGraphV1",
    "SectionArgumentMoveV1",
    "SectionContentOpenSlotV1",
    "SectionContentWitnessSetV1",
    "SectionSentenceContentWitnessV1",
    "WritingResearchRequestV1",
    "MechanismResearchRequestV2",
    "WritingResearchCallbackArtifactV1",
    "MechanismResearchCallbackArtifactV2",
    "WritingResearchCallbackBundleV1",
    "build_completeness_matrix",
    "build_reference_method_agenda",
]
