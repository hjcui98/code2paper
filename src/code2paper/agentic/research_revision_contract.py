"""R10 (§15): research hypotheses may be revised, author constraints may not shrink.

The contract separates three things that used to be conflated:

* **Author constraints** — the original goal/constraint text, the exact target
  identities and the predicates/relations/conditions they require.  They are
  captured once, independently of any proposal, and every later revision is
  measured against that captured set.  Only the original text being kept while
  every predicate is swapped is *not* preservation.
* **Provenance** — every target records whether it came from the author, from a
  system inference or from a research sub-question.  Legacy records whose
  provenance cannot be proven are ``unproven`` and therefore *not* deletable.
* **Revision proposals** — an owner (the LLM) may only *propose*: parent
  obligation, before/after target ids, source type, exact observation/relation
  references, reason, unresolved impact and budget.  It can never write
  ``supported``/``verified``/status, choose fact authority, or sign its own
  semantic review.

The harness validates the proposal, applies an accepted revision atomically and
records one journal entry that binds the digests of every changed object, so a
resumed run cannot re-apply the same revision and an old handoff cannot be used
under new targets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.mechanism_context_models import (
    canonical_json_bytes,
    sha256_digest,
)


TargetProvenanceV1 = Literal[
    "author_explicit",
    "author_derived",
    "system_inferred",
    "research_subquestion",
    "unproven",
]

#: Only a system inference may be replaced or dropped.  An author constraint, a
#: target that deterministically carries one, and a legacy record whose
#: provenance cannot be proven are all non-deletable.
DELETABLE_PROVENANCE: frozenset[str] = frozenset({"system_inferred"})

#: Provenance a proposer may claim for itself.  ``author_explicit`` and
#: ``author_derived`` are harness-assigned: neither can be self-declared.
PROPOSABLE_PROVENANCE: tuple[str, ...] = (
    "system_inferred",
    "research_subquestion",
    "unproven",
)

#: Predicates that describe *that* something is computed without saying what.
#: They cannot stand in for a specific author-required predicate.
GENERIC_PREDICATES: frozenset[str] = frozenset({
    "COMPUTE", "GENERIC_COMPUTE", "TRANSFORM", "PROCESS", "OPERATION", "ANY",
})

RevisionVerdict = Literal["accepted", "rejected", "pending_review"]


def _digest(payload: Any) -> str:
    return sha256_digest(canonical_json_bytes(payload))


class AuthorTargetRequirementsV1(BaseModel):
    """The frozen requirement payload of one author target.

    It is captured *before* any enrichment replaces the deterministic targets,
    so protection no longer depends on a mutable graph still carrying the
    author's ``provenance``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    obligation_id: str
    role: str = ""
    predicates: tuple[str, ...] = Field(default_factory=tuple)
    predicate_groups: tuple[tuple[str, ...], ...] = Field(default_factory=tuple)
    relations: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    transformations: tuple[str, ...] = Field(default_factory=tuple)
    decisions: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    #: Slot *kinds* the author target requires (entrypoint, transformation,
    #: condition, output, relation, decision).
    semantic_slots: tuple[str, ...] = Field(default_factory=tuple)


class AuthorObligationRequirementsV1(BaseModel):
    """Per-obligation author boundary, independent of the live target list."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    author_text: str = ""
    target_ids: tuple[str, ...] = Field(default_factory=tuple)
    predicates: tuple[str, ...] = Field(default_factory=tuple)
    relations: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    transformations: tuple[str, ...] = Field(default_factory=tuple)
    decisions: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    semantic_slots: tuple[str, ...] = Field(default_factory=tuple)


def _slot_signature(target: Any) -> tuple[str, ...]:
    """Semantic slot *structure* of a target, independent of its target id.

    ``slot_id`` is ``<target_id>:slot:<kind>``, so an enriched target carrying
    the same requirements under a different id would otherwise look like it
    dropped every slot.  Slot terms are not compared here: the derivation
    prefers ``transformations`` over ``desired_predicates`` for the
    transformation slot, so the same requirement legitimately appears as a
    different term.  Terms are conserved field by field (predicates, relations,
    conditions, inputs, transformations, decisions, outputs) instead.
    """

    return tuple(
        sorted({
            str(getattr(slot, "slot_kind", "") or "")
            for slot in (getattr(target, "semantic_slots", ()) or ())
            if str(getattr(slot, "slot_kind", "") or "").strip()
        })
    )


def _target_requirement_payload(target: Any) -> dict[str, tuple[str, ...]]:
    return {
        "predicates": tuple(
            str(value) for value in (getattr(target, "desired_predicates", ()) or ())
        ),
        "relations": tuple(
            str(value) for value in (getattr(target, "required_relations", ()) or ())
        ),
        "conditions": tuple(
            str(value) for value in (getattr(target, "conditions", ()) or ())
        ),
        "inputs": tuple(str(value) for value in (getattr(target, "inputs", ()) or ())),
        "transformations": tuple(
            str(value) for value in (getattr(target, "transformations", ()) or ())
        ),
        "decisions": tuple(
            str(value) for value in (getattr(target, "decisions", ()) or ())
        ),
        "outputs": tuple(str(value) for value in (getattr(target, "outputs", ()) or ())),
        "semantic_slots": _slot_signature(target),
    }


def target_preserves_author_requirements(
    current: Any,
    frozen: AuthorTargetRequirementsV1,
) -> bool:
    """Whether a live target still carries every frozen author requirement."""

    payload = _target_requirement_payload(current)
    if not set(frozen.predicates).issubset(payload["predicates"]):
        return False
    if not set(frozen.relations).issubset(payload["relations"]):
        return False
    if not set(frozen.conditions).issubset(payload["conditions"]):
        return False
    if not set(frozen.inputs).issubset(payload["inputs"]):
        return False
    if not set(frozen.transformations).issubset(payload["transformations"]):
        return False
    if not set(frozen.decisions).issubset(payload["decisions"]):
        return False
    if not set(frozen.outputs).issubset(payload["outputs"]):
        return False
    if not set(frozen.semantic_slots).issubset(payload["semantic_slots"]):
        return False
    return True


class AuthorConstraintSetV1(BaseModel):
    """The author's original, independently captured constraint boundary.

    The set is captured from the compiled intent graph *before* any target
    enrichment, then carried by the runtime, the checkpoint and every revision
    assessment.  A later stage must never rebuild author authority from the
    mutable graph: enrichment legitimately replaces every deterministic target
    with an inferred one, which would otherwise erase the boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    constraint_id: str
    project_goal: str = ""
    method_goal: str = ""
    constraint_texts: tuple[str, ...] = Field(default_factory=tuple)
    target_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_predicates: tuple[str, ...] = Field(default_factory=tuple)
    required_relations: tuple[str, ...] = Field(default_factory=tuple)
    required_conditions: tuple[str, ...] = Field(default_factory=tuple)
    author_texts: tuple[str, ...] = Field(default_factory=tuple)
    # Frozen per-target/per-obligation requirements (R10 §15.1).
    author_targets: tuple[AuthorTargetRequirementsV1, ...] = Field(
        default_factory=tuple
    )
    obligations: tuple[AuthorObligationRequirementsV1, ...] = Field(
        default_factory=tuple
    )
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "AuthorConstraintSetV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("author constraint set content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    def obligation_requirements(
        self, obligation_id: str
    ) -> AuthorObligationRequirementsV1 | None:
        return next(
            (
                item
                for item in self.obligations
                if item.obligation_id == str(obligation_id)
            ),
            None,
        )

    def author_targets_for(
        self, obligation_id: str
    ) -> tuple[AuthorTargetRequirementsV1, ...]:
        return tuple(
            item
            for item in self.author_targets
            if item.obligation_id == str(obligation_id)
        )

    def author_target_map(self, graph: Any) -> dict[str, tuple[str, ...]]:
        """Map each frozen author target to the live targets that still carry it.

        The mapping is re-derived from requirement containment, so it cannot go
        stale against the mutable graph; an author target with no live
        representation maps to the empty tuple and stays protected by id.
        """

        mapping: dict[str, list[str]] = {
            item.target_id: [] for item in self.author_targets
        }
        if not mapping:
            return {}
        obligations = {
            str(getattr(obligation, "obligation_id", "") or ""): obligation
            for obligation in (getattr(graph, "obligations", ()) or ())
        }
        for frozen in self.author_targets:
            obligation = obligations.get(frozen.obligation_id)
            if obligation is None:
                continue
            mapping[frozen.target_id] = [
                str(getattr(target, "target_id", "") or "")
                for target in (
                    getattr(obligation, "typed_behavior_targets", ()) or ()
                )
                if str(getattr(target, "target_id", "") or "")
                and target_preserves_author_requirements(target, frozen)
            ]
        return {
            key: tuple(dict.fromkeys(value)) for key, value in mapping.items()
        }

    def non_deletable_target_ids(self, graph: Any) -> tuple[str, ...]:
        """Return every target id this constraint set protects.

        A frozen author target is represented either by the live targets that
        still carry its requirements, or -- when the live graph dropped the
        provenance *and* the requirements -- by its own id.  The denominator
        therefore cannot shrink below the author's original target set.
        """

        protected: list[str] = list(self.target_ids)
        for obligation in (getattr(graph, "obligations", ()) or ()):
            for target in (getattr(obligation, "typed_behavior_targets", ()) or ()):
                provenance = str(getattr(target, "provenance", "unproven"))
                if provenance not in DELETABLE_PROVENANCE:
                    target_id = str(getattr(target, "target_id", "") or "")
                    if target_id and target_id not in protected:
                        protected.append(target_id)
        if self.author_targets:
            for frozen, live_ids in self.author_target_map(graph).items():
                for target_id in live_ids or (frozen,):
                    if target_id not in protected:
                        protected.append(target_id)
        return tuple(protected)


class RevisionTargetV1(BaseModel):
    """One target the revision wants to introduce or replace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    role: str = ""
    desired_predicates: tuple[str, ...] = Field(default_factory=tuple)
    required_relations: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    transformations: tuple[str, ...] = Field(default_factory=tuple)
    decisions: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    search_terms: tuple[str, ...] = Field(default_factory=tuple)
    provenance: TargetProvenanceV1 = "unproven"
    replaces_target_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _identity(self) -> "RevisionTargetV1":
        if not self.target_id.strip():
            raise ValueError("revision target requires target_id")
        if self.provenance == "author_explicit":
            # A proposer cannot promote its own output into author authority.
            raise ValueError(
                "revision target cannot claim author_explicit provenance"
            )
        return self


class RevisionProposalV1(BaseModel):
    """A proposal only: it carries no authority and no status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    proposal_id: str
    parent_obligation_id: str
    source_type: TargetProvenanceV1 = "system_inferred"
    before_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    after_targets: tuple[RevisionTargetV1, ...] = Field(default_factory=tuple)
    observation_refs: tuple[str, ...] = Field(default_factory=tuple)
    relation_refs: tuple[str, ...] = Field(default_factory=tuple)
    reason: str = ""
    unresolved_impact: tuple[str, ...] = Field(default_factory=tuple)
    budget_requests: int = 0
    subquestion_parent_id: str = ""
    author_constraint_digest: str = ""
    revision_id: str = ""

    @model_validator(mode="after")
    def _compute_revision_id(self) -> "RevisionProposalV1":
        if not self.proposal_id.strip() or not self.parent_obligation_id.strip():
            raise ValueError("revision proposal requires proposal/parent ids")
        if self.budget_requests < 0:
            raise ValueError("revision proposal budget must be >= 0")
        expected = _digest(self.model_dump(mode="json", exclude={"revision_id"}))
        if self.revision_id and self.revision_id != expected:
            raise ValueError("revision proposal revision_id mismatch")
        object.__setattr__(self, "revision_id", expected)
        return self


class RevisionAssessmentV1(BaseModel):
    """The harness verdict; the proposal and its review cannot self-sign."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    assessment_id: str
    proposal_id: str
    revision_id: str
    parent_obligation_id: str
    verdict: RevisionVerdict
    failures: tuple[str, ...] = Field(default_factory=tuple)
    author_constraint_digest: str = ""
    coverage_denominator_ids: tuple[str, ...] = Field(default_factory=tuple)
    semantic_review: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "RevisionAssessmentV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("revision assessment content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class RevisionJournalEntryV1(BaseModel):
    """One applied revision, bound to every object it changed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    revision_id: str
    parent_revision_id: str = ""
    proposal_id: str
    parent_obligation_id: str
    object_digests: dict[str, str] = Field(default_factory=dict)
    coverage_denominator_ids: tuple[str, ...] = Field(default_factory=tuple)
    applied_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    removed_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    handoff_invalidated: bool = False
    #: Research budget the proposal requested for the revised targets.  It is
    #: recorded here (not on the proposal) so a resume recomputes the run's
    #: remaining allowance from the append-only journal.
    requested_budget: int = 0
    #: Harness charge for applying this revision.  Always 1; the application
    #: count is what a run's revision limit bounds.
    application_charge: int = 1
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "RevisionJournalEntryV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("revision journal entry content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class RevisionJournalV1(BaseModel):
    """Append-only revision history used for resume and handoff validity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    entries: tuple[RevisionJournalEntryV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "RevisionJournalV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("revision journal content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    def has_applied(self, revision_id: str) -> bool:
        return any(
            entry.revision_id == str(revision_id) for entry in self.entries
        )

    def current_revision_id(self) -> str:
        return self.entries[-1].revision_id if self.entries else ""

    def append(self, entry: RevisionJournalEntryV1) -> "RevisionJournalV1":
        if self.has_applied(entry.revision_id):
            raise ValueError(
                f"revision already applied: {entry.revision_id}"
            )
        return RevisionJournalV1(entries=(*self.entries, entry))

    def handoff_is_current(self, handoff_revision_id: str) -> bool:
        """An old handoff may not be reused once a revision invalidated it."""

        return str(handoff_revision_id or "") == self.current_revision_id()


# ---------------------------------------------------------------------------
# Author constraint capture
# ---------------------------------------------------------------------------


def author_target_requirements(
    target: Any,
    obligation_id: str,
) -> AuthorTargetRequirementsV1:
    """Capture one target's frozen requirement payload."""

    return AuthorTargetRequirementsV1(
        target_id=str(getattr(target, "target_id", "") or ""),
        obligation_id=str(obligation_id or ""),
        role=str(getattr(target, "role", "") or ""),
        predicates=tuple(
            str(value) for value in (
                getattr(target, "desired_predicates", ()) or ()
            )
        ),
        predicate_groups=tuple(
            tuple(str(value) for value in group)
            for group in (getattr(target, "predicate_groups", ()) or ())
        ),
        relations=tuple(
            str(value) for value in (
                getattr(target, "required_relations", ()) or ()
            )
        ),
        conditions=tuple(
            str(value) for value in (getattr(target, "conditions", ()) or ())
        ),
        inputs=tuple(
            str(value) for value in (getattr(target, "inputs", ()) or ())
        ),
        transformations=tuple(
            str(value) for value in (
                getattr(target, "transformations", ()) or ()
            )
        ),
        decisions=tuple(
            str(value) for value in (getattr(target, "decisions", ()) or ())
        ),
        outputs=tuple(
            str(value) for value in (getattr(target, "outputs", ()) or ())
        ),
        semantic_slots=_slot_signature(target),
    )


def build_author_constraint_set(graph: Any) -> AuthorConstraintSetV1:
    """Capture the author's original boundary independently of any proposal.

    Call this on the *compiled* graph, before enrichment replaces the
    deterministic targets.  The returned set is the frozen authority for every
    later revision, coverage decision and resume.
    """

    target_ids: list[str] = []
    predicates: list[str] = []
    relations: list[str] = []
    conditions: list[str] = []
    author_texts: list[str] = []
    author_targets: list[AuthorTargetRequirementsV1] = []
    obligations_payload: list[AuthorObligationRequirementsV1] = []
    for obligation in (getattr(graph, "obligations", ()) or ()):
        obligation_id = str(getattr(obligation, "obligation_id", "") or "")
        author_text = str(getattr(obligation, "author_text", "") or "").strip()
        if author_text:
            author_texts.append(author_text)
        obligation_target_ids: list[str] = []
        obligation_predicates: list[str] = []
        obligation_relations: list[str] = []
        obligation_conditions: list[str] = []
        obligation_inputs: list[str] = []
        obligation_transformations: list[str] = []
        obligation_decisions: list[str] = []
        obligation_outputs: list[str] = []
        obligation_slots: list[str] = []
        for target in (getattr(obligation, "typed_behavior_targets", ()) or ()):
            provenance = str(getattr(target, "provenance", "unproven"))
            if provenance in DELETABLE_PROVENANCE:
                continue
            target_id = str(getattr(target, "target_id", "") or "").strip()
            if target_id:
                target_ids.append(target_id)
                obligation_target_ids.append(target_id)
            target_predicates = tuple(
                str(value) for value in (
                    getattr(target, "desired_predicates", ()) or ()
                )
            )
            target_relations = tuple(
                str(value) for value in (
                    getattr(target, "required_relations", ()) or ()
                )
            )
            target_conditions = tuple(
                str(value) for value in (getattr(target, "conditions", ()) or ())
            )
            predicates.extend(target_predicates)
            relations.extend(target_relations)
            conditions.extend(target_conditions)
            obligation_predicates.extend(target_predicates)
            obligation_relations.extend(target_relations)
            obligation_conditions.extend(target_conditions)
            obligation_inputs.extend(
                str(value) for value in (getattr(target, "inputs", ()) or ())
            )
            obligation_transformations.extend(
                str(value)
                for value in (getattr(target, "transformations", ()) or ())
            )
            obligation_decisions.extend(
                str(value) for value in (getattr(target, "decisions", ()) or ())
            )
            obligation_outputs.extend(
                str(value) for value in (getattr(target, "outputs", ()) or ())
            )
            slots = _slot_signature(target)
            obligation_slots.extend(slots)
            if target_id:
                author_targets.append(AuthorTargetRequirementsV1(
                    target_id=target_id,
                    obligation_id=obligation_id,
                    role=str(getattr(target, "role", "") or ""),
                    predicates=target_predicates,
                    predicate_groups=tuple(
                        tuple(str(value) for value in group)
                        for group in (
                            getattr(target, "predicate_groups", ()) or ()
                        )
                    ),
                    relations=target_relations,
                    conditions=target_conditions,
                    inputs=tuple(
                        str(value)
                        for value in (getattr(target, "inputs", ()) or ())
                    ),
                    transformations=tuple(
                        str(value)
                        for value in (getattr(target, "transformations", ()) or ())
                    ),
                    decisions=tuple(
                        str(value)
                        for value in (getattr(target, "decisions", ()) or ())
                    ),
                    outputs=tuple(
                        str(value)
                        for value in (getattr(target, "outputs", ()) or ())
                    ),
                    semantic_slots=slots,
                ))
        if obligation_target_ids:
            obligations_payload.append(AuthorObligationRequirementsV1(
                obligation_id=obligation_id,
                author_text=author_text,
                target_ids=tuple(dict.fromkeys(obligation_target_ids)),
                predicates=tuple(dict.fromkeys(obligation_predicates)),
                relations=tuple(dict.fromkeys(obligation_relations)),
                conditions=tuple(dict.fromkeys(obligation_conditions)),
                inputs=tuple(dict.fromkeys(obligation_inputs)),
                transformations=tuple(
                    dict.fromkeys(obligation_transformations)
                ),
                decisions=tuple(dict.fromkeys(obligation_decisions)),
                outputs=tuple(dict.fromkeys(obligation_outputs)),
                semantic_slots=tuple(dict.fromkeys(obligation_slots)),
            ))
    constraint_texts = tuple(
        dict.fromkeys(value for value in author_texts if value)
    )
    return AuthorConstraintSetV1(
        constraint_id=_digest({
            "project_goal": str(getattr(graph, "project_goal", "") or ""),
            "method_goal": str(getattr(graph, "method_goal", "") or ""),
            "texts": list(constraint_texts),
        }),
        project_goal=str(getattr(graph, "project_goal", "") or ""),
        method_goal=str(getattr(graph, "method_goal", "") or ""),
        constraint_texts=constraint_texts,
        target_ids=tuple(dict.fromkeys(target_ids)),
        required_predicates=tuple(dict.fromkeys(predicates)),
        required_relations=tuple(dict.fromkeys(relations)),
        required_conditions=tuple(dict.fromkeys(conditions)),
        author_texts=constraint_texts,
        author_targets=tuple(author_targets),
        obligations=tuple(obligations_payload),
    )


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


def _graph_targets(graph: Any) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    for obligation in (getattr(graph, "obligations", ()) or ()):
        for target in (getattr(obligation, "typed_behavior_targets", ()) or ()):
            target_id = str(getattr(target, "target_id", "") or "")
            if target_id:
                targets[target_id] = target
    return targets


def _obligation_by_id(graph: Any) -> dict[str, Any]:
    return {
        str(getattr(obligation, "obligation_id", "") or ""): obligation
        for obligation in (getattr(graph, "obligations", ()) or ())
    }


def _registered_predicate_vocabulary() -> tuple[str, ...]:
    from code2paper.agentic.behavior_graph import BEHAVIOR_PREDICATES

    return tuple(BEHAVIOR_PREDICATES)


def _registered_relation_vocabulary() -> tuple[str, ...]:
    from code2paper.agentic.behavior_graph import BEHAVIOR_RELATION_KINDS

    return tuple(BEHAVIOR_RELATION_KINDS)


def _projected_slots(target: RevisionTargetV1) -> tuple[str, ...]:
    """Derive the semantic slots a proposed target will carry once applied.

    ``RevisionTargetV1`` has no slot field: slots are derived from the target's
    own requirements by ``TypedBehaviorTargetV1``.  Conservation therefore
    compares the *projected* slots, not an empty set.
    """

    try:
        from code2paper.agentic.research_models import TypedBehaviorTargetV1
    except Exception:  # pragma: no cover - import guard for isolated tests
        return ()
    payload = target.model_dump(mode="json")
    payload.pop("replaces_target_ids", None)
    try:
        projected = TypedBehaviorTargetV1(**payload)
    except (TypeError, ValueError):  # pragma: no cover - invalid payload
        return ()
    return _slot_signature(projected)


def _frozen_target_represented(
    frozen: AuthorTargetRequirementsV1,
    *,
    kept_targets: Iterable[Any],
    after_targets: Iterable[RevisionTargetV1],
) -> bool:
    """Whether some resulting target still carries a frozen author target."""

    for target in kept_targets:
        if target_preserves_author_requirements(target, frozen):
            return True
    for target in after_targets:
        if not set(frozen.predicates).issubset(set(target.desired_predicates)):
            continue
        if not set(frozen.relations).issubset(set(target.required_relations)):
            continue
        if not set(frozen.conditions).issubset(set(target.conditions)):
            continue
        if not set(frozen.inputs).issubset(set(target.inputs)):
            continue
        if not set(frozen.transformations).issubset(set(target.transformations)):
            continue
        if not set(frozen.decisions).issubset(set(target.decisions)):
            continue
        if not set(frozen.outputs).issubset(set(target.outputs)):
            continue
        if not set(frozen.semantic_slots).issubset(set(_projected_slots(target))):
            continue
        return True
    return False


def assess_revision_proposal(
    proposal: RevisionProposalV1,
    *,
    graph: Any,
    author_constraints: AuthorConstraintSetV1,
    observed_ref_ids: Iterable[str] = (),
    remaining_budget: int | None = None,
    semantic_verifier: Callable[[Any, RevisionTargetV1], bool] | None = None,
    previous_journal: RevisionJournalV1 | None = None,
    registered_predicates: Iterable[str] | None = None,
    registered_relations: Iterable[str] | None = None,
    observed_ref_predicates: Mapping[str, Iterable[str]] | None = None,
) -> RevisionAssessmentV1:
    """Validate one revision proposal against the frozen author boundary.

    The proposal may revise *inferred* hypotheses.  It may not delete or replace
    an author constraint (or a legacy record whose provenance cannot be proven),
    substitute a generic predicate for a specific one, cite unobserved evidence,
    exceed its budget, reuse another obligation's target, or apply twice.
    """

    failures: list[str] = []
    pending: list[str] = []
    obligations = _obligation_by_id(graph)
    targets = _graph_targets(graph)

    parent = obligations.get(proposal.parent_obligation_id)
    if parent is None:
        failures.append(
            f"revision_unknown_parent:{proposal.parent_obligation_id}"
        )
    if proposal.author_constraint_digest and (
        proposal.author_constraint_digest != author_constraints.content_digest
    ):
        failures.append("revision_author_constraint_mismatch")

    # 1. Recompute the revision identity: a forged id is not a revision.
    expected_revision_id = _digest(
        proposal.model_dump(mode="json", exclude={"revision_id"})
    )
    if proposal.revision_id != expected_revision_id:
        failures.append("revision_forged_identity")

    # 2. Duplicate resume must not re-apply the same revision.
    if previous_journal is not None and previous_journal.has_applied(
        proposal.revision_id
    ):
        failures.append(f"revision_already_applied:{proposal.revision_id}")

    # 3. Research allowance.  This is the *requested* research budget for the
    #    revised targets, not the number of revisions the run may apply: that
    #    count is charged harness-side (one per application).
    if remaining_budget is not None and proposal.budget_requests > int(
        remaining_budget
    ):
        failures.append(
            "revision_research_allowance_exhausted:"
            f"{proposal.budget_requests}>{int(remaining_budget)}"
        )

    # 3b. The target vocabulary is closed.  A proposal cannot invent predicates
    #     or relation kinds the behavior graph cannot express; the harness
    #     rejects them instead of storing an unverifiable requirement.
    registered_predicates = (
        set(registered_predicates)
        if registered_predicates is not None
        else set(_registered_predicate_vocabulary())
    )
    registered_relations = (
        set(registered_relations)
        if registered_relations is not None
        else set(_registered_relation_vocabulary())
    )
    for target in proposal.after_targets:
        for predicate in target.desired_predicates:
            if str(predicate) not in registered_predicates:
                failures.append(
                    f"revision_predicate_unregistered:{predicate}"
                )
        for relation in target.required_relations:
            if str(relation) not in registered_relations:
                failures.append(
                    f"revision_relation_unregistered:{relation}"
                )

    # 4. Provenance: an unproven record cannot justify a change, and a
    #    sub-question must carry its parent.
    if proposal.source_type == "unproven":
        failures.append("revision_provenance_unproven")
    if proposal.source_type == "research_subquestion":
        if proposal.subquestion_parent_id != proposal.parent_obligation_id:
            failures.append("revision_subquestion_parent_missing")

    # 5. Before ids must exist on the parent obligation.
    parent_target_ids = (
        {
            str(getattr(target, "target_id", "") or "")
            for target in (getattr(parent, "typed_behavior_targets", ()) or ())
        }
        if parent is not None else set()
    )
    for target_id in proposal.before_target_ids:
        if target_id not in parent_target_ids:
            failures.append(f"revision_unknown_before_target:{target_id}")

    # 6. After ids are new, or belong to the parent obligation.  A proposal may
    #    not steal another obligation's target.
    for target in proposal.after_targets:
        existing = targets.get(target.target_id)
        if existing is None:
            continue
        owner = next(
            (
                str(getattr(obligation, "obligation_id", "") or "")
                for obligation in (getattr(graph, "obligations", ()) or ())
                if any(
                    str(getattr(item, "target_id", "") or "") == target.target_id
                    for item in (
                        getattr(obligation, "typed_behavior_targets", ()) or ()
                    )
                )
            ),
            "",
        )
        if owner and owner != proposal.parent_obligation_id:
            failures.append(f"revision_target_owned_elsewhere:{target.target_id}")

    # 7. Deletion rules and author-constraint conservation.
    replaced = {
        value
        for target in proposal.after_targets
        for value in target.replaces_target_ids
    }
    after_ids = {target.target_id for target in proposal.after_targets}
    before_ids = set(proposal.before_target_ids)
    removed: list[str] = []
    for target_id in proposal.before_target_ids:
        if target_id in after_ids or target_id in replaced:
            continue
        removed.append(target_id)
        provenance = str(
            getattr(targets.get(target_id), "provenance", "unproven")
        )
        if provenance not in DELETABLE_PROVENANCE:
            failures.append(f"revision_author_constraint_deleted:{target_id}")

    after_predicates = {
        value for target in proposal.after_targets
        for value in target.desired_predicates
    }
    after_relations = {
        value for target in proposal.after_targets
        for value in target.required_relations
    }
    after_conditions = {
        value for target in proposal.after_targets for value in target.conditions
    }
    after_inputs = {
        value for target in proposal.after_targets for value in target.inputs
    }
    after_transformations = {
        value
        for target in proposal.after_targets
        for value in target.transformations
    }
    after_decisions = {
        value for target in proposal.after_targets for value in target.decisions
    }
    after_outputs = {
        value for target in proposal.after_targets for value in target.outputs
    }
    after_slots = {
        slot
        for target in proposal.after_targets
        for slot in _projected_slots(target)
    }
    protected_predicates = set(author_constraints.required_predicates)
    protected_relations = set(author_constraints.required_relations)
    protected_conditions = set(author_constraints.required_conditions)
    frozen_obligation = author_constraints.obligation_requirements(
        proposal.parent_obligation_id
    )
    if frozen_obligation is not None or (
        parent_target_ids and (proposal.after_targets or removed)
    ):
        # Conservation is measured on the *resulting* obligation, not on the
        # proposal alone.  The required side is the frozen author boundary when
        # one exists: enrichment legitimately replaces every deterministic
        # target with an inferred one, so rebuilding author authority from the
        # live graph would let a later revision delete the author's
        # requirements by deleting the inferred target that carries them.
        dropped = {
            target_id
            for target_id in removed
            if str(getattr(targets.get(target_id), "provenance", "unproven"))
            in DELETABLE_PROVENANCE
        }
        kept_target_ids = parent_target_ids - after_ids - dropped
        kept_targets = [
            targets[target_id]
            for target_id in sorted(kept_target_ids)
            if targets.get(target_id) is not None
        ]
        result_predicates = set(after_predicates) | {
            value
            for target in kept_targets
            for value in (getattr(target, "desired_predicates", ()) or ())
        }
        result_relations = set(after_relations) | {
            value
            for target in kept_targets
            for value in (getattr(target, "required_relations", ()) or ())
        }
        result_conditions = set(after_conditions) | {
            value
            for target in kept_targets
            for value in (getattr(target, "conditions", ()) or ())
        }
        result_inputs = set(after_inputs) | {
            value
            for target in kept_targets
            for value in (getattr(target, "inputs", ()) or ())
        }
        result_transformations = set(after_transformations) | {
            value
            for target in kept_targets
            for value in (getattr(target, "transformations", ()) or ())
        }
        result_decisions = set(after_decisions) | {
            value
            for target in kept_targets
            for value in (getattr(target, "decisions", ()) or ())
        }
        result_outputs = set(after_outputs) | {
            value
            for target in kept_targets
            for value in (getattr(target, "outputs", ()) or ())
        }
        result_slots = set(after_slots) | {
            slot for target in kept_targets for slot in _slot_signature(target)
        }
        if frozen_obligation is not None:
            parent_predicates = set(frozen_obligation.predicates)
            parent_relations = set(frozen_obligation.relations)
            parent_conditions = set(frozen_obligation.conditions)
            parent_inputs = set(frozen_obligation.inputs)
            parent_transformations = set(frozen_obligation.transformations)
            parent_decisions = set(frozen_obligation.decisions)
            parent_outputs = set(frozen_obligation.outputs)
            parent_slots = set(frozen_obligation.semantic_slots)
        else:
            parent_predicates = {
                value
                for target_id in parent_target_ids
                for value in (
                    getattr(targets.get(target_id), "desired_predicates", ()) or ()
                )
            } & protected_predicates
            parent_relations = {
                value
                for target_id in parent_target_ids
                for value in (
                    getattr(targets.get(target_id), "required_relations", ()) or ()
                )
            } & protected_relations
            parent_conditions = {
                value
                for target_id in parent_target_ids
                for value in (
                    getattr(targets.get(target_id), "conditions", ()) or ()
                )
            } & protected_conditions
            parent_inputs = set()
            parent_transformations = set()
            parent_decisions = set()
            parent_outputs = set()
            parent_slots = set()
        missing_predicates = parent_predicates - result_predicates
        generic_present = bool(result_predicates & GENERIC_PREDICATES)
        for value in sorted(missing_predicates):
            # A generic placeholder standing in for a specific author predicate
            # is a substitution, not a revision of the inferred layer.
            if generic_present or value not in result_predicates and (
                after_predicates & GENERIC_PREDICATES
            ):
                failures.append(f"revision_generic_substitution:{value}")
            else:
                failures.append(f"revision_author_predicate_dropped:{value}")
        for value in sorted(parent_relations - result_relations):
            failures.append(
                f"revision_author_relation_dropped:{value}"
            )
        for value in sorted(parent_conditions - result_conditions):
            failures.append(
                f"revision_author_condition_dropped:{value}"
            )
        for value in sorted(parent_inputs - result_inputs):
            failures.append(
                f"revision_author_input_dropped:{value}"
            )
        for value in sorted(parent_transformations - result_transformations):
            failures.append(
                f"revision_author_transformation_dropped:{value}"
            )
        for value in sorted(parent_decisions - result_decisions):
            failures.append(
                f"revision_author_decision_dropped:{value}"
            )
        for value in sorted(parent_outputs - result_outputs):
            failures.append(
                f"revision_author_output_dropped:{value}"
            )
        for value in sorted(parent_slots - result_slots):
            failures.append(
                f"revision_author_slot_dropped:{value}"
            )
        # Per-target conservation: every frozen author target must still be
        # represented by some resulting target, otherwise the coverage
        # denominator would silently shrink.
        for frozen in author_constraints.author_targets_for(
            proposal.parent_obligation_id
        ):
            if not _frozen_target_represented(
                frozen,
                kept_targets=kept_targets,
                after_targets=proposal.after_targets,
            ):
                failures.append(
                    f"revision_author_target_dropped:{frozen.target_id}"
                )

    # 8. Evidence references must be exact and observed.
    observed = {str(value) for value in observed_ref_ids if str(value).strip()}
    cited = tuple(
        str(value)
        for value in (*proposal.observation_refs, *proposal.relation_refs)
        if str(value).strip()
    )
    requirements_changed = bool(removed) or bool(after_ids - before_ids)
    if not requirements_changed:
        for target in proposal.after_targets:
            before_target = targets.get(target.target_id)
            if before_target is None:
                requirements_changed = True
                break
            if not _same_requirement_set(
                _target_payload(before_target), target.model_dump(mode="json")
            ):
                requirements_changed = True
                break
    if requirements_changed and not cited:
        # A content change without an exact observation/relation reference is
        # an assertion, not a revision.
        failures.append("revision_evidence_refs_missing")
    if observed:
        missing = sorted({value for value in cited if value not in observed})
        for value in missing[:5]:
            failures.append(f"revision_ref_unobserved:{value}")

    # 8b. Relevance.  Membership in the authenticated evidence set proves the
    #     run *read* something; it does not prove the read supports the change.
    #     When the harness has a predicate-support index, every predicate the
    #     revision adds must be supported by at least one cited reference --
    #     otherwise the revision goes to independent review instead of being
    #     applied on the proposer's own reason.
    if observed_ref_predicates is not None:
        support: dict[str, set[str]] = {}
        for ref, predicates in observed_ref_predicates.items():
            support[str(ref)] = {
                str(value) for value in predicates if str(value).strip()
            }
        kept_predicates_for_obligation = {
            value
            for target_id in parent_target_ids
            if target_id not in after_ids
            for value in (
                getattr(targets.get(target_id), "desired_predicates", ()) or ()
            )
        }
        cited_refs = tuple(dict.fromkeys((*proposal.observation_refs, *proposal.relation_refs)))
        for target in proposal.after_targets:
            added_predicates = {
                str(value) for value in target.desired_predicates
            } - kept_predicates_for_obligation
            if not added_predicates:
                continue
            supported = {
                value
                for ref in cited_refs
                for value in support.get(str(ref), set())
            }
            unsupported = sorted(added_predicates - supported)
            if not unsupported:
                continue
            if not supported:
                pending.append(
                    f"revision_ref_unsupportive:{target.target_id}"
                )
            for predicate in unsupported:
                pending.append(
                    f"revision_predicate_unsupported:{target.target_id}:{predicate}"
                )

    # 9. A reason alone is not a revision.
    if not after_ids and not removed:
        failures.append("revision_no_target_change")
    elif not removed and after_ids == before_ids:
        before_payloads = {
            target_id: _target_payload(targets.get(target_id))
            for target_id in sorted(before_ids)
        }
        after_payloads = {
            target.target_id: target.model_dump(mode="json")
            for target in proposal.after_targets
            if target.target_id in before_payloads
        }
        if before_payloads and all(
            _same_requirement_set(before_payloads[key], after_payloads.get(key))
            for key in before_payloads
        ):
            failures.append("revision_no_target_change")

    # 10. Replacing an author constraint in place needs an independent review.
    replaced_protected = [
        target
        for target in proposal.after_targets
        if target.target_id in author_constraints.target_ids
        or str(getattr(targets.get(target.target_id), "provenance", ""))
        == "author_explicit"
    ]
    semantic_review = ""
    if replaced_protected:
        if semantic_verifier is None:
            pending.append("revision_semantic_review_unavailable")
        else:
            for target in replaced_protected:
                try:
                    equivalent = bool(
                        semantic_verifier(targets.get(target.target_id), target)
                    )
                except Exception as exc:  # noqa: BLE001 — review is not self-signed
                    failures.append(
                        f"revision_semantic_review_failed:{type(exc).__name__}"
                    )
                    equivalent = False
                if not equivalent:
                    failures.append(
                        f"revision_semantic_not_equivalent:{target.target_id}"
                    )
            semantic_review = "independent_verifier"

    denominator = author_constraints.non_deletable_target_ids(graph)
    verdict: RevisionVerdict = "accepted"
    if failures:
        verdict = "rejected"
    elif pending:
        verdict = "pending_review"
    return RevisionAssessmentV1(
        assessment_id=_digest({
            "proposal_id": proposal.proposal_id,
            "revision_id": proposal.revision_id,
            "failures": failures,
            "pending": pending,
        }),
        proposal_id=proposal.proposal_id,
        revision_id=proposal.revision_id,
        parent_obligation_id=proposal.parent_obligation_id,
        verdict=verdict,
        failures=tuple(dict.fromkeys((*failures, *pending))),
        author_constraint_digest=author_constraints.content_digest,
        coverage_denominator_ids=denominator,
        semantic_review=semantic_review,
    )


def _target_payload(target: Any) -> dict[str, Any]:
    if target is None:
        return {}
    if hasattr(target, "model_dump"):
        return dict(target.model_dump(mode="json"))
    return dict(target) if isinstance(target, Mapping) else {}


def _same_requirement_set(before: Mapping[str, Any], after: Any) -> bool:
    if not isinstance(after, Mapping):
        return False
    keys = (
        "desired_predicates", "required_relations", "conditions",
        "inputs", "transformations", "decisions", "outputs",
    )
    for key in keys:
        before_values = before.get(key) or ()
        after_values = after.get(key) or ()
        if isinstance(before_values, str) or isinstance(after_values, str):
            return False
        if sorted(str(value) for value in before_values) != sorted(
            str(value) for value in after_values
        ):
            return False
    return True


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_revision(
    *,
    graph: Any,
    proposal: RevisionProposalV1,
    assessment: RevisionAssessmentV1,
    previous_journal: RevisionJournalV1 | None = None,
    object_digests: Mapping[str, str] | None = None,
    parent_revision_id: str = "",
) -> tuple[Any, RevisionJournalV1, tuple[str, ...]]:
    """Apply an accepted revision atomically and journal it.

    Only ``system_inferred`` targets may be replaced or dropped; author
    constraints and unproven records are preserved, so a revision can never
    shrink the coverage denominator.  Every changed object digest is bound to
    the journal entry and the handoff is marked invalidated.
    """

    if assessment.verdict != "accepted":
        return graph, (previous_journal or RevisionJournalV1()), (
            f"revision_not_accepted:{assessment.verdict}",
        )
    journal = previous_journal or RevisionJournalV1()
    if journal.has_applied(proposal.revision_id):
        return graph, journal, (
            f"revision_already_applied:{proposal.revision_id}",
        )

    try:
        from code2paper.agentic.research_models import TypedBehaviorTargetV1
    except Exception:  # pragma: no cover - import guard for isolated tests
        TypedBehaviorTargetV1 = None  # type: ignore[assignment]

    new_obligations: list[Any] = []
    applied_ids: list[str] = []
    removed_ids: list[str] = []
    for obligation in (getattr(graph, "obligations", ()) or ()):
        if str(getattr(obligation, "obligation_id", "")) != (
            proposal.parent_obligation_id
        ):
            new_obligations.append(obligation)
            continue
        existing = {
            str(getattr(target, "target_id", "")): target
            for target in (
                getattr(obligation, "typed_behavior_targets", ()) or ()
            )
        }
        replaced = {
            value
            for target in proposal.after_targets
            for value in target.replaces_target_ids
        }
        after_ids = {target.target_id for target in proposal.after_targets}
        kept: list[Any] = []
        for target_id, target in existing.items():
            if target_id in after_ids:
                continue
            if target_id in replaced or target_id in proposal.before_target_ids:
                provenance = str(getattr(target, "provenance", "unproven"))
                if provenance in DELETABLE_PROVENANCE:
                    removed_ids.append(target_id)
                    continue
            kept.append(target)
        converted: list[Any] = []
        for target in proposal.after_targets:
            payload = target.model_dump(mode="json")
            payload.pop("replaces_target_ids", None)
            if TypedBehaviorTargetV1 is None:
                converted.append(payload)
                continue
            existing_target = existing.get(target.target_id)
            if existing_target is not None:
                # An in-place revision keeps the declared id and provenance of
                # the record it replaces; the proposal cannot promote itself.
                payload["provenance"] = str(
                    getattr(existing_target, "provenance", "unproven")
                )
                payload["target_id"] = target.target_id
            converted.append(TypedBehaviorTargetV1(**payload))
            applied_ids.append(target.target_id)
        new_obligations.append(obligation.model_copy(update={
            "typed_behavior_targets": tuple((*kept, *converted)),
        }))

    # Rebuild through the model constructor so the content digest is
    # recomputed: ``model_copy`` skips validators, which would leave the old
    # digest on a changed graph and hide the revision from every consumer.
    try:
        enriched = type(graph)(
            schema_version=str(getattr(graph, "schema_version", "2.0")),
            mode=str(getattr(graph, "mode", "intent-obligation-graph-v2")),
            project_goal=str(getattr(graph, "project_goal", "") or ""),
            method_goal=str(getattr(graph, "method_goal", "") or ""),
            implementation_scope=str(
                getattr(graph, "implementation_scope", "") or ""
            ),
            obligations=list(new_obligations),
            relations=list(getattr(graph, "relations", ()) or ()),
        )
    except (TypeError, ValueError):
        enriched = graph.model_copy(update={"obligations": tuple(new_obligations)})
    entry = RevisionJournalEntryV1(
        revision_id=proposal.revision_id,
        parent_revision_id=str(parent_revision_id or journal.current_revision_id()),
        proposal_id=proposal.proposal_id,
        parent_obligation_id=proposal.parent_obligation_id,
        requested_budget=max(0, int(proposal.budget_requests)),
        object_digests={
            str(key): str(value)
            for key, value in dict(object_digests or {}).items()
        } | {
            "intent_obligation_graph_v2": str(
                getattr(enriched, "content_digest", "") or ""
            ),
            "intent_target_identity": str(
                getattr(enriched, "target_identity_digest", "") or ""
            ),
        },
        coverage_denominator_ids=assessment.coverage_denominator_ids,
        applied_target_ids=tuple(dict.fromkeys(applied_ids)),
        removed_target_ids=tuple(dict.fromkeys(removed_ids)),
        handoff_invalidated=True,
    )
    return enriched, journal.append(entry), ()


class RevisionApplicationV1(BaseModel):
    """The result of applying one revision to a live research state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    assessment: RevisionAssessmentV1
    journal: RevisionJournalV1
    graph: Any | None = None
    agenda: Any | None = None
    revalidation_rows: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    failures: tuple[str, ...] = Field(default_factory=tuple)


class ResearchRevisionBindingV1(BaseModel):
    """The revision identity a checkpoint/resume must agree on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    revision_id: str = ""
    journal_digest: str = ""
    intent_graph_digest: str = ""
    target_identity_digest: str = ""
    agenda_digest: str = ""
    coverage_denominator_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "ResearchRevisionBindingV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("research revision binding content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def build_revision_proposal(
    *,
    proposal_id: str,
    parent_obligation_id: str,
    before_target_ids: Iterable[str] = (),
    new_target: RevisionTargetV1 | None = None,
    source_type: TargetProvenanceV1 = "system_inferred",
    observation_refs: Iterable[str] = (),
    relation_refs: Iterable[str] = (),
    reason: str = "",
    unresolved_impact: Iterable[str] = (),
    budget_requests: int = 0,
    subquestion_parent_id: str = "",
    author_constraint_digest: str = "",
) -> RevisionProposalV1:
    """Build a proposal for the single ingestion point.

    §15.2: an owner (model or deterministic fallback) may only *submit* a
    proposal.  This helper keeps the submitted shape identical for both, so the
    harness — not the producer — decides identity, provenance, conservation and
    budget.
    """

    after = (new_target,) if new_target is not None else ()
    return RevisionProposalV1(
        proposal_id=proposal_id,
        parent_obligation_id=parent_obligation_id,
        source_type=source_type,
        before_target_ids=tuple(before_target_ids),
        after_targets=tuple(after),
        observation_refs=tuple(observation_refs),
        relation_refs=tuple(relation_refs),
        reason=reason,
        unresolved_impact=tuple(unresolved_impact),
        budget_requests=int(budget_requests),
        subquestion_parent_id=subquestion_parent_id,
        author_constraint_digest=author_constraint_digest,
    )


def build_subquestion_target(
    *,
    target_id: str,
    predicates: Iterable[str],
    evidence_graph: Any = None,
    role: str = "subquestion",
) -> RevisionTargetV1:
    """Build one inferred sub-question target from observed predicates only.

    Predicates must belong to the registered behavior vocabulary and, when an
    evidence graph is supplied, must have been observed in it.  An owner cannot
    invent a predicate to make coverage easier.
    """

    from code2paper.agentic.behavior_graph import BEHAVIOR_PREDICATES

    normalized = tuple(
        dict.fromkeys(
            str(value).strip().upper()
            for value in predicates
            if str(value).strip()
        )
    )
    unknown = sorted(set(normalized) - set(BEHAVIOR_PREDICATES))
    if unknown:
        raise ValueError(f"unknown behavior predicates: {unknown}")
    if evidence_graph is not None:
        observed: set[str] = set()
        for node in (getattr(evidence_graph, "nodes", ()) or ()):
            predicate = str(getattr(node, "predicate", "") or "").strip().upper()
            if predicate:
                observed.add(predicate)
        unobserved = sorted(set(normalized) - observed)
        if unobserved:
            raise ValueError(f"unobserved behavior predicates: {unobserved}")
    return RevisionTargetV1(
        target_id=target_id,
        role=role,
        desired_predicates=normalized,
        provenance="research_subquestion",
    )


def bind_research_revision(
    *,
    journal: RevisionJournalV1,
    graph: Any = None,
    agenda: Any = None,
    coverage_denominator_ids: Iterable[str] = (),
) -> ResearchRevisionBindingV1:
    """Bind one revision identity to the objects that must agree with it."""

    return ResearchRevisionBindingV1(
        revision_id=journal.current_revision_id(),
        journal_digest=journal.content_digest,
        intent_graph_digest=str(getattr(graph, "content_digest", "") or ""),
        target_identity_digest=str(
            getattr(graph, "target_identity_digest", "") or ""
        ),
        agenda_digest=str(getattr(agenda, "content_digest", "") or ""),
        coverage_denominator_ids=tuple(
            dict.fromkeys(str(value) for value in coverage_denominator_ids)
        ),
    )


def revision_resume_failures(
    *,
    binding: ResearchRevisionBindingV1 | None,
    journal: RevisionJournalV1,
    revision_id: str = "",
    graph: Any = None,
    agenda: Any = None,
) -> tuple[str, ...]:
    """Failures that make a resume unsafe under the current revision.

    A resume may not re-apply a revision the journal already holds, and it may
    not continue from a checkpoint whose bound revision or target identity no
    longer matches the live objects.
    """

    failures: list[str] = []
    if revision_id and journal.has_applied(revision_id):
        failures.append(f"revision_already_applied:{revision_id}")
    if binding is None:
        return tuple(dict.fromkeys(failures))
    if binding.revision_id != journal.current_revision_id():
        failures.append(
            "revision_binding_stale:"
            f"{binding.revision_id or 'unversioned'}"
            f"!={journal.current_revision_id() or 'unversioned'}"
        )
    if binding.journal_digest and binding.journal_digest != journal.content_digest:
        failures.append("revision_binding_journal_digest_mismatch")
    if graph is not None and binding.intent_graph_digest and (
        binding.intent_graph_digest != str(getattr(graph, "content_digest", "") or "")
    ):
        failures.append("revision_binding_intent_graph_mismatch")
    if graph is not None and binding.target_identity_digest and (
        binding.target_identity_digest
        != str(getattr(graph, "target_identity_digest", "") or "")
    ):
        failures.append("revision_binding_target_identity_mismatch")
    if agenda is not None and binding.agenda_digest and (
        binding.agenda_digest != str(getattr(agenda, "content_digest", "") or "")
    ):
        failures.append("revision_binding_agenda_mismatch")
    return tuple(dict.fromkeys(failures))


def revise_research_targets(
    *,
    runtime: Any,
    proposal: RevisionProposalV1,
    observed_ref_ids: Iterable[str] = (),
    remaining_budget: int | None = None,
    semantic_verifier: Callable[[Any, RevisionTargetV1], bool] | None = None,
    previous_journal: RevisionJournalV1 | None = None,
    fact_set: Any | None = None,
    claim_set: Any | None = None,
    object_digests: Mapping[str, str] | None = None,
    author_constraints: AuthorConstraintSetV1 | None = None,
    observed_ref_predicates: Mapping[str, Iterable[str]] | None = None,
) -> RevisionApplicationV1:
    """Apply one accepted revision to a live research state and re-evaluate it.

    §15.6: a revision changes the intent graph *and* everything that depended
    on the old targets.  Obligations whose targets changed are re-aligned
    against the frozen facts; when a target no longer resolves, the obligation
    loses its promoted claims and is marked for re-research instead of keeping
    a support decision that the new targets do not justify.  Claims covering a
    changed obligation are marked for re-verification.
    """

    graph = getattr(runtime, "intent_graph", None)
    agenda = getattr(runtime, "agenda", None)
    if graph is None or agenda is None:
        return RevisionApplicationV1(
            assessment=RevisionAssessmentV1(
                assessment_id=_digest({"proposal": proposal.proposal_id}),
                proposal_id=proposal.proposal_id,
                revision_id=proposal.revision_id,
                parent_obligation_id=proposal.parent_obligation_id,
                verdict="rejected",
                failures=("revision_research_state_missing",),
            ),
            journal=previous_journal or RevisionJournalV1(),
            failures=("revision_research_state_missing",),
        )

    # §15.1: the frozen boundary wins.  Rebuilding it from the live graph would
    # let enrichment (which replaces every deterministic target with an inferred
    # one) erase the author's protection before the revision is even assessed.
    constraints = (
        author_constraints
        or getattr(runtime, "author_constraints", None)
        or build_author_constraint_set(graph)
    )
    assessment = assess_revision_proposal(
        proposal,
        graph=graph,
        author_constraints=constraints,
        observed_ref_ids=observed_ref_ids,
        remaining_budget=remaining_budget,
        semantic_verifier=semantic_verifier,
        previous_journal=previous_journal,
        observed_ref_predicates=observed_ref_predicates,
    )
    if assessment.verdict != "accepted":
        return RevisionApplicationV1(
            assessment=assessment,
            journal=previous_journal or RevisionJournalV1(),
            graph=graph,
            agenda=agenda,
            failures=assessment.failures,
        )

    enriched, journal, failures = apply_revision(
        graph=graph,
        proposal=proposal,
        assessment=assessment,
        previous_journal=previous_journal,
        object_digests=object_digests,
    )
    if failures:
        return RevisionApplicationV1(
            assessment=assessment,
            journal=journal,
            graph=graph,
            agenda=agenda,
            failures=failures,
        )

    revalidation_rows, updated_agenda, revalidation_failures = (
        _revalidate_after_revision(
            graph=graph,
            enriched=enriched,
            agenda=agenda,
            proposal=proposal,
            fact_set=fact_set,
            claim_set=claim_set,
        )
    )
    if revalidation_failures:
        # The graph moved but the objects that actually consume it could not be
        # brought along.  Nothing is committed: no journal entry, no runtime
        # rebind, and the graph is returned unchanged.
        return RevisionApplicationV1(
            assessment=assessment,
            journal=previous_journal or RevisionJournalV1(),
            graph=graph,
            agenda=agenda,
            revalidation_rows=tuple(revalidation_rows),
            failures=revalidation_failures,
        )
    binding = bind_research_revision(
        journal=journal,
        graph=enriched,
        agenda=updated_agenda,
        coverage_denominator_ids=assessment.coverage_denominator_ids,
    )
    bound_digests = dict(object_digests or {}) | {
        "research_agenda_v1": str(
            getattr(updated_agenda, "content_digest", "") or ""
        ),
        "intent_obligation_graph_v2": str(
            getattr(enriched, "content_digest", "") or ""
        ),
        "intent_target_identity": str(
            getattr(enriched, "target_identity_digest", "") or ""
        ),
        "research_revision_binding_v1": binding.content_digest,
    }
    # Rebuild through the constructor so the entry digest covers the final
    # object map (``model_copy`` skips the digest validator).
    last = journal.entries[-1]
    entry = RevisionJournalEntryV1(
        revision_id=last.revision_id,
        parent_revision_id=last.parent_revision_id,
        proposal_id=last.proposal_id,
        parent_obligation_id=last.parent_obligation_id,
        object_digests=bound_digests,
        coverage_denominator_ids=last.coverage_denominator_ids,
        applied_target_ids=last.applied_target_ids,
        removed_target_ids=last.removed_target_ids,
        handoff_invalidated=last.handoff_invalidated,
        requested_budget=last.requested_budget,
        application_charge=last.application_charge,
    )
    journal = RevisionJournalV1(entries=(*journal.entries[:-1], entry))
    return RevisionApplicationV1(
        assessment=assessment,
        journal=journal,
        graph=enriched,
        agenda=updated_agenda,
        revalidation_rows=tuple(revalidation_rows),
        failures=(),
    )


def _revalidate_after_revision(
    *,
    graph: Any,
    enriched: Any,
    agenda: Any,
    proposal: RevisionProposalV1,
    fact_set: Any | None,
    claim_set: Any | None,
) -> tuple[list[dict[str, Any]], Any, tuple[str, ...]]:
    """Re-evaluate coverage/claim applicability for changed obligations.

    §15.6/P1-B: the agenda item is what the compiler and the coverage
    alignment actually read, so the revised target *payload* is written into
    it here, in the same transaction as the graph change.  The function fails
    closed when the two objects cannot be made to agree.
    """

    changed_obligations = {proposal.parent_obligation_id}
    failures: list[str] = []
    obligations_by_id = {
        str(getattr(obligation, "obligation_id", "") or ""): obligation
        for obligation in (getattr(enriched, "obligations", ()) or ())
    }
    facts = tuple(getattr(fact_set, "facts", ()) or ())
    claims = tuple(getattr(claim_set, "claims", ()) or ())
    rows: list[dict[str, Any]] = []
    items: list[Any] = []
    seen_changed: set[str] = set()
    for item in (getattr(agenda, "items", ()) or ()):
        obligation_id = str(getattr(item, "obligation_id", "") or "")
        if obligation_id not in changed_obligations:
            items.append(item)
            continue
        seen_changed.add(obligation_id)
        obligation = obligations_by_id.get(obligation_id)
        unresolved_targets: list[str] = []
        if obligation is not None:
            for target in (getattr(obligation, "typed_behavior_targets", ()) or ()):
                if fact_set is None:
                    unresolved_targets.append(
                        str(getattr(target, "target_id", "") or "")
                    )
                    continue
                try:
                    from code2paper.agentic.obligation_fact_alignment import (
                        align_target_to_facts,
                    )

                    alignment = align_target_to_facts(target, facts)
                    status = str(getattr(alignment, "status", "") or "")
                except Exception:  # noqa: BLE001 — unknown applicability is unresolved
                    status = ""
                if status != "resolved":
                    unresolved_targets.append(
                        str(getattr(target, "target_id", "") or "")
                    )
        claim_ids = tuple(
            str(getattr(claim, "claim_id", "") or "")
            for claim in claims
            if obligation_id in {
                str(value)
                for value in (getattr(claim, "covers_obligation_ids", ()) or ())
            }
        )
        markers = [
            f"revision_revalidation_required:{obligation_id}",
            *(
                f"revision_target_unresolved:{target_id}"
                for target_id in unresolved_targets
                if target_id
            ),
            *(
                f"revision_claim_revalidation_required:{claim_id}"
                for claim_id in claim_ids
                if claim_id
            ),
        ]
        update: dict[str, Any] = {
            "missing_information": list(dict.fromkeys(
                [*(getattr(item, "missing_information", ()) or ()), *markers]
            )),
            # The revised target payload is the contract the compiler and the
            # obligation/claim alignment read.  Leaving the pre-revision
            # targets here while binding the new graph digest is what let a
            # revision look applied and still be ignored.
            "typed_behavior_targets": (
                list(getattr(obligation, "typed_behavior_targets", ()) or ())
                if obligation is not None
                else list(getattr(item, "typed_behavior_targets", ()) or ())
            ),
        }
        if unresolved_targets or claim_ids:
            # The new targets do not justify the previous support decision.
            update["supported_claim_ids"] = []
            update["status"] = "in_progress"
        items.append(item.model_copy(update=update))
        rows.append({
            "obligation_id": obligation_id,
            "unresolved_target_ids": unresolved_targets,
            "claim_ids_requiring_revalidation": list(claim_ids),
            "status_after": update.get("status", str(getattr(item, "status", ""))),
            "markers": markers,
        })
    missing_items = sorted(changed_obligations - seen_changed)
    for obligation_id in missing_items:
        failures.append(f"revision_agenda_item_missing:{obligation_id}")
    try:
        updated_agenda = agenda.model_copy(update={"items": items})
        # The agenda was built from the pre-revision graph.  Once the targets
        # changed, its link must name the revised graph, otherwise a resume
        # compares the agenda against the wrong intent identity.
        revised_graph_digest = str(
            getattr(enriched, "content_digest", "") or ""
        )
        if revised_graph_digest:
            updated_agenda.intent_graph_digest = revised_graph_digest
        refresh = getattr(updated_agenda, "refresh_content_digest", None)
        if callable(refresh):
            refresh()
    except Exception as exc:  # pragma: no cover - defensive: keep the old agenda
        failures.append(f"revision_agenda_sync_failed:{type(exc).__name__}")
        return rows, agenda, tuple(dict.fromkeys(failures))
    # Every changed obligation must end with the agenda carrying exactly the
    # revised target payload; a digest that matches while the payload does not
    # is not a binding.
    agenda_items_by_id = {
        str(getattr(item, "obligation_id", "") or ""): item
        for item in (getattr(updated_agenda, "items", ()) or ())
    }
    for obligation_id in sorted(changed_obligations):
        obligation = obligations_by_id.get(obligation_id)
        item = agenda_items_by_id.get(obligation_id)
        if obligation is None or item is None:
            continue
        obligation_targets = [
            target.model_dump(mode="json")
            for target in (
                getattr(obligation, "typed_behavior_targets", ()) or ()
            )
        ]
        agenda_targets = [
            target.model_dump(mode="json")
            for target in (getattr(item, "typed_behavior_targets", ()) or ())
        ]
        if obligation_targets != agenda_targets:
            failures.append(
                f"revision_agenda_target_mismatch:{obligation_id}"
            )
    return rows, updated_agenda, tuple(dict.fromkeys(failures))


#: Every object that must be re-bound under one revision (§15.6).
REVISION_BOUND_OBJECT_KEYS: tuple[str, ...] = (
    "research_agenda_v1",
    "intent_obligation_graph_v2",
    "obligation_coverage_v2",
    "atomic_claims_v3",
    "observation_promotion_ledger_v1",
    "candidate_handoff_v1",
    "research_stage_checkpoint_v1",
    "method_section_plan_v2",
)

#: Fields a live graph receives when a revision is bound to it.  The digest
#: fields are copied from the revised object so the identity that every other
#: revision-bound artifact compares against is the revised one.
_REVISION_GRAPH_REBIND_FIELDS: tuple[str, ...] = (
    "schema_version",
    "mode",
    "project_goal",
    "method_goal",
    "implementation_scope",
    "obligations",
    "relations",
    "content_digest",
    "target_identity_digest",
)

_REVISION_AGENDA_REBIND_FIELDS: tuple[str, ...] = (
    "items",
    "intent_graph_digest",
    "content_digest",
)


def rebind_revision_in_place(
    *,
    runtime_intent_graph: Any,
    runtime_agenda: Any,
    revised_graph: Any,
    revised_agenda: Any,
) -> tuple[str, ...]:
    """Bind an applied revision to the live (shared) graph and agenda objects.

    ``ResearchGraphRuntime`` is frozen, so an applied revision cannot replace
    ``runtime.intent_graph``/``runtime.agenda``; every holder of the runtime
    would keep reading the pre-revision targets.  The revised objects are
    therefore copied onto the live ones field by field.  A live object that
    refuses the update is a typed failure: the journal then describes a
    revision the running research state does not actually use.
    """

    failures: list[str] = []
    for label, target, source, fields in (
        (
            "intent_graph",
            runtime_intent_graph,
            revised_graph,
            _REVISION_GRAPH_REBIND_FIELDS,
        ),
        ("agenda", runtime_agenda, revised_agenda, _REVISION_AGENDA_REBIND_FIELDS),
    ):
        if source is None:
            failures.append(f"revision_rebind_source_missing:{label}")
            continue
        if target is None or target is source:
            continue
        for field in fields:
            if not hasattr(source, field):
                continue
            try:
                setattr(target, field, getattr(source, field))
            except Exception as exc:  # noqa: BLE001 — a frozen live object
                failures.append(
                    f"revision_rebind_failed:{label}:{field}:{type(exc).__name__}"
                )
                break
    return tuple(dict.fromkeys(failures))


def object_digest(value: Any) -> str:
    """Digest one revision-bound object without trusting caller bookkeeping."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = {
            key: getattr(value, key)
            for key in REVISION_BOUND_OBJECT_KEYS
            if hasattr(value, key)
        }
    digest = ""
    if isinstance(payload, Mapping):
        digest = str(payload.get("content_digest") or "")
    return digest or _digest(payload)


def build_object_digests(objects: Mapping[str, Any]) -> dict[str, str]:
    """Return ``{object_key: digest}`` for every provided revision object.

    Callers pass the objects they actually hold; a missing object stays absent
    rather than being silently replaced by an empty digest.
    """

    return {
        str(key): object_digest(value)
        for key, value in (objects or {}).items()
        if value is not None
    }


def missing_bound_objects(digests: Mapping[str, str]) -> tuple[str, ...]:
    """Return the §15.6 objects that are not bound in this revision."""

    return tuple(
        key for key in REVISION_BOUND_OBJECT_KEYS if not str(digests.get(key) or "")
    )


def write_revision_journal(out_root: Any, journal: RevisionJournalV1) -> Any:
    """Persist the journal so resume and handoff can bind to the revision."""

    from code2paper.core.output_names import method_output

    path = method_output(Path(out_root), "research_revision_journal_v1")
    path.write_text(
        journal.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return path


def load_revision_journal(path: Any) -> RevisionJournalV1:
    """Load a persisted journal; a missing file is an empty history."""

    from pathlib import Path as _Path

    target = _Path(str(path or ""))
    if not target.is_file():
        return RevisionJournalV1()
    return RevisionJournalV1.model_validate_json(
        target.read_text(encoding="utf-8")
    )


def handoff_matches_revision(handoff: Any, journal: RevisionJournalV1) -> bool:
    """Return whether a Candidate handoff may still be used.

    A handoff created before a revision must not stay usable under the new
    targets, even when its own digests are intact.
    """

    handoff_revision = str(getattr(handoff, "revision_id", "") or "")
    current = journal.current_revision_id()
    if not current:
        return not handoff_revision
    return handoff_revision == current


__all__ = [
    "DELETABLE_PROVENANCE",
    "ResearchRevisionBindingV1",
    "RevisionApplicationV1",
    "GENERIC_PREDICATES",
    "AuthorConstraintSetV1",
    "RevisionAssessmentV1",
    "RevisionJournalEntryV1",
    "RevisionJournalV1",
    "RevisionProposalV1",
    "RevisionTargetV1",
    "RevisionVerdict",
    "TargetProvenanceV1",
    "REVISION_BOUND_OBJECT_KEYS",
    "apply_revision",
    "assess_revision_proposal",
    "bind_research_revision",
    "build_revision_proposal",
    "build_subquestion_target",
    "build_author_constraint_set",
    "build_object_digests",
    "handoff_matches_revision",
    "load_revision_journal",
    "missing_bound_objects",
    "object_digest",
    "rebind_revision_in_place",
    "revision_resume_failures",
    "revise_research_targets",
    "write_revision_journal",
]
