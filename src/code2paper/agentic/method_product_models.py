"""Shared product contracts for the autonomous Method Agent flow.

This module is the P0 thin contract layer.  It defines the single set of
product-level lanes, plan-readiness states, review-candidate items, output
policy, draft bundle, author story spine nodes, and the per-plan product
readiness report that every other subsystem (projection, Architect, Writer,
output splitter, callback router, CLI) must share.  It deliberately contains
no proof/placement/hash machinery: exact placement, move authority and
semantic frames remain audit/verified metadata owned by
``method_argument_models`` and the Architect, and they never block candidate
generation here.

Authority rules implemented as defaults:

- ``repository_verified`` is the only lane that may enter verified positive
  implementation facts by default.
- ``repository_partial`` may enter verified only when the qualifier-preserving
  gate passes; it is never silently promoted.
- ``author_intent_unverified`` may enter candidate but must correspond to a
  review item and blocks verified inclusion.
- ``literature_pending`` / ``empirical_pending`` / ``formalization_pending``
  may enter candidate caveats or review, never repository verified facts.
- ``repository_mismatch`` can never be written as a positive implementation
  fact; candidate may expose it as an explicit mismatch warning.
- Only a risk that an unsupported positive would be written without a caveat
  raises ``blocked_for_safety``; ordinary missing evidence must become a
  review/callback item instead.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    ReferenceMethodAgendaV1,
)


MethodEvidenceLane = Literal[
    "repository_verified",
    "repository_partial",
    "repository_mismatch",
    "author_intent_unverified",
    "author_confirmed",
    "literature_pending",
    "empirical_pending",
    "formalization_pending",
    "out_of_scope",
]

METHOD_EVIDENCE_LANES: tuple[MethodEvidenceLane, ...] = (
    "repository_verified",
    "repository_partial",
    "repository_mismatch",
    "author_intent_unverified",
    "author_confirmed",
    "literature_pending",
    "empirical_pending",
    "formalization_pending",
    "out_of_scope",
)

MethodPlanReadiness = Literal[
    "verified_ready",
    "candidate_ready",
    "candidate_ready_with_review",
    "blocked_for_safety",
]

METHOD_PLAN_READINESS_STATES: tuple[MethodPlanReadiness, ...] = (
    "verified_ready",
    "candidate_ready",
    "candidate_ready_with_review",
    "blocked_for_safety",
)

StoryNodeRoleV1 = Literal[
    "motivation",
    "setup",
    "algorithm_step",
    "training",
    "inference",
    "evaluation",
    "ablation",
    "limitation",
]

STORY_NODE_ROLES: tuple[StoryNodeRoleV1, ...] = (
    "motivation",
    "setup",
    "algorithm_step",
    "training",
    "inference",
    "evaluation",
    "ablation",
    "limitation",
)

#: Completeness rows that carry positive repository support.
_POSITIVE_REFERENCE_STATUSES = frozenset({
    "supported_by_repository",
    "partially_supported_by_repository",
})


class _ProductModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean_tuple(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


# ---------------------------------------------------------------------------
# Lane mapping helpers (stable, project-agnostic)
# ---------------------------------------------------------------------------


def method_lane_from_reference_status(status: str) -> MethodEvidenceLane:
    """Map a completeness/reference status onto the product lane vocabulary.

    ``unverified_by_repository`` and ``explicit_code_gap`` remain
    author-intent lanes awaiting confirmation; they never imply repository
    support.  ``author_confirmation_required`` is not ``author_confirmed``.
    """

    if status == "supported_by_repository":
        return "repository_verified"
    if status == "partially_supported_by_repository":
        return "repository_partial"
    if status == "paper_code_mismatch":
        return "repository_mismatch"
    if status == "external_evidence_required":
        return "literature_pending"
    if status == "formalization_required":
        return "formalization_pending"
    if status == "out_of_scope":
        return "out_of_scope"
    return "author_intent_unverified"


def method_lane_from_authority_lane(lane: str) -> MethodEvidenceLane:
    """Map the legacy authority lane onto the product lane vocabulary.

    ``executable_hard`` and ``configuration_resolved`` are repository
    authority lanes; whether their content is actually verified is decided by
    the completeness/claims state, not by the lane alone.
    """

    if lane == "configuration_resolved":
        return "repository_verified"
    if lane == "author_attested":
        return "author_intent_unverified"
    if lane == "formal_derivation":
        return "formalization_pending"
    if lane == "empirical_artifact":
        return "empirical_pending"
    if lane == "external_literature":
        return "literature_pending"
    if lane == "expository_bridge":
        return "out_of_scope"
    return "repository_verified"


#: Lane severity for a unit's dominant lane (worst lane wins).  A mismatch is
#: the most severe because it must never be written as a positive fact; an
#: out-of-scope row is the least informative.
_LANE_SEVERITY: dict[str, int] = {
    "repository_mismatch": 7,
    "formalization_pending": 6,
    "literature_pending": 5,
    "empirical_pending": 4,
    "author_intent_unverified": 3,
    "repository_partial": 2,
    "repository_verified": 1,
    "author_confirmed": 0,
    "out_of_scope": 0,
}


# ---------------------------------------------------------------------------
# Author story spine
# ---------------------------------------------------------------------------


class AuthorStoryNodeV1(_ProductModel):
    """One node of the author-intent-first story spine.

    The spine is the organization authority for the Method section plan: the
    Architect orders sections from the spine before any code-order grouping.
    ``author_statement`` is author wording and never a repository fact; it is
    the candidate/review authority.  ``evidence_lane`` records what the
    evidence currently says about the node (default: unverified author
    intent), so a node never silently becomes a verified implementation fact.
    """

    story_node_id: str
    title: str
    author_statement: str
    intended_role: StoryNodeRoleV1 = "algorithm_step"
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    linked_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    linked_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_lane: MethodEvidenceLane = "author_intent_unverified"
    notes: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("story_node_id", "title", "author_statement")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("story node identifiers and text must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _clean_lists(self) -> "AuthorStoryNodeV1":
        object.__setattr__(self, "source_refs", _clean_tuple(self.source_refs))
        object.__setattr__(self, "linked_obligation_ids", _clean_tuple(self.linked_obligation_ids))
        object.__setattr__(self, "linked_claim_ids", _clean_tuple(self.linked_claim_ids))
        object.__setattr__(self, "notes", _clean_tuple(self.notes))
        return self


# ---------------------------------------------------------------------------
# Review candidates and output policy
# ---------------------------------------------------------------------------


class MethodReviewCandidateV1(_ProductModel):
    """One author-facing review item with editable proposed body text.

    ``blocks_verified`` and ``blocks_candidate`` are independent by design:
    an unverified author-intent point blocks verified inclusion but never
    candidate generation.  ``proposed_body`` must be non-empty; the review
    loop is the user's edit surface, not an empty shell.
    """

    candidate_id: str
    source_obligation_id: str | None = None
    source_claim_id: str | None = None
    section_id: str | None = None
    argument_unit_id: str | None = None
    lane: MethodEvidenceLane = "author_intent_unverified"
    status: str = "unverified"
    proposed_body: str
    confirmation_question: str
    needed_evidence: tuple[str, ...] = Field(default_factory=tuple)
    suggested_action: str = ""
    blocks_verified: bool = True
    blocks_candidate: bool = False
    trace_refs: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("candidate_id", "proposed_body", "confirmation_question")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("review candidate id, proposed body and question must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _clean(self) -> "MethodReviewCandidateV1":
        object.__setattr__(self, "needed_evidence", _clean_tuple(self.needed_evidence))
        object.__setattr__(self, "trace_refs", _clean_tuple(self.trace_refs))
        return self


class MethodOutputPolicyV1(_ProductModel):
    """Output-lane policy shared by Architect, Writer and validation.

    The defaults implement the fail-closed verified / candidate-permissive
    split: only repository-verified (or qualifier-guarded partial) facts enter
    the verified document, while ordinary unresolved items never block the
    candidate document.
    """

    verified_positive_lanes: tuple[MethodEvidenceLane, ...] = (
        "repository_verified",
        "repository_partial",
    )
    candidate_allowed_lanes: tuple[MethodEvidenceLane, ...] = (
        "repository_verified",
        "repository_partial",
        "repository_mismatch",
        "author_intent_unverified",
        "author_confirmed",
        "literature_pending",
        "empirical_pending",
        "formalization_pending",
    )
    review_required_lanes: tuple[MethodEvidenceLane, ...] = (
        "author_intent_unverified",
        "repository_mismatch",
        "literature_pending",
        "empirical_pending",
        "formalization_pending",
        "out_of_scope",
    )
    unsupported_positive_blocks_verified: bool = True
    unresolved_blocks_candidate: bool = False

    @model_validator(mode="after")
    def _known_lanes(self) -> "MethodOutputPolicyV1":
        known = set(METHOD_EVIDENCE_LANES)
        for field in ("verified_positive_lanes", "candidate_allowed_lanes", "review_required_lanes"):
            values = getattr(self, field)
            unknown = set(values) - known
            if unknown:
                raise ValueError(f"output policy contains unknown lanes: {sorted(unknown)}")
        if not set(self.verified_positive_lanes) <= set(self.candidate_allowed_lanes):
            raise ValueError("verified lanes must be a subset of candidate-allowed lanes")
        if "repository_verified" in set(self.review_required_lanes):
            raise ValueError("repository_verified must never be review-required")
        if set(self.review_required_lanes) & set(self.verified_positive_lanes):
            raise ValueError("review-required lanes must not overlap verified positive lanes")
        if "repository_verified" not in self.verified_positive_lanes:
            raise ValueError("repository_verified must remain a verified positive lane")
        return self


def build_default_method_output_policy() -> MethodOutputPolicyV1:
    return MethodOutputPolicyV1()


class MethodDraftBundleV1(_ProductModel):
    """The three-way output bundle produced by one Method run.

    ``candidate_markdown`` is the author-intent-first editable draft (it may
    carry clearly marked unresolved material); ``verified_markdown`` contains
    only repository-supported positive implementation facts; ``review_items``
    carry proposed body text and exact questions for everything that blocked
    verified inclusion.  ``plan_readiness`` states why the run stopped where
    it stopped.
    """

    candidate_markdown: str
    verified_markdown: str
    review_items: tuple[MethodReviewCandidateV1, ...] = Field(default_factory=tuple)
    plan_readiness: MethodPlanReadiness = "candidate_ready_with_review"
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)
    validation_split_report: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _readiness_consistency(self) -> "MethodDraftBundleV1":
        if self.plan_readiness == "blocked_for_safety" and not self.blocked_reasons:
            raise ValueError("blocked_for_safety bundles require blocked reasons")
        if self.plan_readiness == "verified_ready" and not self.verified_markdown.strip():
            raise ValueError("verified_ready bundles require non-empty verified markdown")
        return self


# ---------------------------------------------------------------------------
# Per-plan product readiness
# ---------------------------------------------------------------------------


class MethodSectionReadinessV1(_ProductModel):
    """Candidate/verified readiness for one Method section."""

    section_id: str
    candidate_ready: bool = True
    verified_ready: bool = False
    blocked_for_safety_reasons: tuple[str, ...] = Field(default_factory=tuple)
    review_required_ids: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _clean(self) -> "MethodSectionReadinessV1":
        object.__setattr__(self, "blocked_for_safety_reasons", _clean_tuple(self.blocked_for_safety_reasons))
        object.__setattr__(self, "review_required_ids", _clean_tuple(self.review_required_ids))
        return self


class MethodUnitProductStatusV1(_ProductModel):
    """Lane and eligibility status for one argument unit.

    ``evidence_status`` is the originating completeness status when one
    exists; ``lane`` is the dominant product lane.  ``can_enter_candidate``
    is false only for a safety block; ``can_enter_verified`` is false for any
    review-required or unbound positive content.
    """

    argument_unit_id: str
    section_id: str = ""
    lane: MethodEvidenceLane = "author_intent_unverified"
    can_enter_candidate: bool = True
    can_enter_verified: bool = False
    requires_review: bool = False
    requires_callback: bool = False
    evidence_status: str = ""
    bound_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("argument_unit_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("unit product status requires an argument unit id")
        return value.strip()

    @model_validator(mode="after")
    def _clean(self) -> "MethodUnitProductStatusV1":
        object.__setattr__(self, "bound_obligation_ids", _clean_tuple(self.bound_obligation_ids))
        return self


class MethodPlanProductReadinessV1(_ProductModel):
    """Sidecar readiness report accompanying a ``MethodSectionPlanV2``.

    This is the D-package contract: exact placement, move authority proofs and
    semantic-frame closure are *audit* metadata (``audit_warnings``) and never
    candidate blockers.  A plan is ``blocked_for_safety`` only when an
    unsupported positive could be written without a caveat route.
    """

    schema_version: str = "1.0"
    plan_id: str
    readiness: MethodPlanReadiness
    section_readiness: tuple[MethodSectionReadinessV1, ...] = Field(default_factory=tuple)
    unit_status: tuple[MethodUnitProductStatusV1, ...] = Field(default_factory=tuple)
    verified_positive_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    candidate_allowed_unit_ids: tuple[str, ...] = Field(default_factory=tuple)
    review_required_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    blocked_for_safety_reasons: tuple[str, ...] = Field(default_factory=tuple)
    review_candidates: tuple[MethodReviewCandidateV1, ...] = Field(default_factory=tuple)
    audit_warnings: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MethodPlanProductReadinessV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


def _unit_bound_rows(
    unit: MethodArgumentUnitV1,
    matrix_by_id: dict[str, MethodCompletenessItemV1],
) -> list[MethodCompletenessItemV1]:
    """Bind completeness rows to a unit via exact ids only.

    A row binds through its persisted obligation assignment, through exact
    claim-id membership in the unit, or through the unit's source obligation
    ids.  Vocabulary overlap is never a binding.
    """

    unit_claim_ids = set(unit.claim_ids)
    unit_obligation_ids = set(unit.source_obligation_ids)
    assigned_obligation_ids = {
        item.obligation_id
        for item in unit.obligation_assignments
        if item.argument_unit_id == unit.argument_unit_id
    }
    rows: list[MethodCompletenessItemV1] = []
    for row in matrix_by_id.values():
        if row.obligation_id in assigned_obligation_ids:
            rows.append(row)
        elif set(row.claim_ids) & unit_claim_ids:
            rows.append(row)
        elif row.obligation_id in unit_obligation_ids:
            rows.append(row)
    return rows


def _unit_lane(
    rows: list[MethodCompletenessItemV1],
    unit: MethodArgumentUnitV1,
) -> MethodEvidenceLane:
    """Dominant product lane of a unit: the most severe bound row wins."""

    if rows:
        lanes = [method_lane_from_reference_status(str(item.status)) for item in rows]
        dominant = max(lanes, key=lambda lane: _LANE_SEVERITY.get(lane, 0))
        return dominant
    lanes = [
        method_lane_from_authority_lane(str(lane))
        for lane in unit.authority_lanes
    ]
    dominant = max(lanes, key=lambda lane: _LANE_SEVERITY.get(lane, 0))
    if all(unit.authority_lanes) and dominant == "repository_verified" and not unit.supported:
        return "author_intent_unverified"
    return dominant


def assess_plan_product_readiness(
    *,
    plan: MethodSectionPlanV2,
    completeness: MethodCompletenessMatrixV1 | None = None,
    claims: Any | None = None,
    policy: MethodOutputPolicyV1 | None = None,
) -> MethodPlanProductReadinessV1:
    """Compute the graded candidate/verified readiness of one Method plan.

    Missing evidence is never a failure here: unverified, mismatch, external
    and formalization content becomes review-required material that blocks
    verified inclusion only.  ``blocked_for_safety`` is raised only when a
    unit would write positive repository wording whose supporting rows are
    absent or non-positive AND the unit has no caveat route
    (``limitations_or_mismatch`` move), i.e. an unsupported positive could
    not be distinguished safely.

    A plan without a completeness matrix cannot establish verified positives;
    it stays candidate-capable with an audit warning.
    """

    policy = policy or build_default_method_output_policy()
    matrix_by_id = completeness.by_id() if completeness is not None else {}
    claim_by_id = {
        str(item.claim_id): item
        for item in (claims.claims if claims is not None else ())
    }
    section_by_unit = {
        unit_id: section.section_id
        for section in plan.sections
        for unit_id in section.argument_unit_ids
    }
    unit_status: list[MethodUnitProductStatusV1] = []
    review_required_obligation_ids: list[str] = []
    unsafe_unit_ids: list[str] = []
    audit_warnings: list[str] = []

    for unit in plan.argument_units:
        rows = _unit_bound_rows(unit, matrix_by_id)
        row_statuses = {str(item.status) for item in rows}
        positive_rows = [item for item in rows if item.status in _POSITIVE_REFERENCE_STATUSES]
        non_positive_rows = [item for item in rows if item.status not in _POSITIVE_REFERENCE_STATUSES]
        lane = _unit_lane(rows, unit)
        has_caveat_move = "limitations_or_mismatch" in unit.allowed_expository_moves

        positive_claim_ids = [
            claim_id
            for claim_id in unit.claim_ids
            if claim_id in claim_by_id
            and str(getattr(claim_by_id[claim_id], "status", "") or "") in {"supported", "partial"}
        ]
        bound_positive_obligations = {item.obligation_id for item in positive_rows}
        unbound_positive = bool(positive_claim_ids) and not bound_positive_obligations

        requires_review = bool(non_positive_rows) or lane in policy.review_required_lanes
        requires_callback = any(
            item.status in {
                "unverified_by_repository",
                "external_evidence_required",
                "formalization_required",
            }
            for item in non_positive_rows
        )

        # Verified eligibility: the unit must bind at least one positive row,
        # every bound row must be positive, the unit must not be incomplete,
        # and no review-required lane may dominate.  ``repository_partial``
        # additionally requires a qualifying row record; without one the unit
        # stays candidate-only (audit warning).
        can_enter_verified = False
        if positive_rows and not non_positive_rows and unit.supported and lane not in policy.review_required_lanes:
            if lane == "repository_partial":
                if any(item.status == "partially_supported_by_repository" for item in positive_rows):
                    can_enter_verified = True
                else:
                    audit_warnings.append(
                        f"unit {unit.argument_unit_id}: partial lane without a qualifying row; "
                        "verified inclusion requires a preserved qualifier"
                    )
            else:
                can_enter_verified = True
        elif not rows and completeness is None:
            audit_warnings.append(
                f"unit {unit.argument_unit_id}: no completeness matrix; verified inclusion unavailable"
            )

        # Safety block: positive repository wording whose supporting rows are
        # absent or non-positive and no caveat route exists.
        can_enter_candidate = True
        if completeness is not None and unbound_positive and not has_caveat_move:
            can_enter_candidate = False
            unsafe_unit_ids.append(unit.argument_unit_id)
        if can_enter_verified and not positive_rows:
            can_enter_verified = False
            audit_warnings.append(
                f"unit {unit.argument_unit_id}: verified claim lacks a positive completeness row"
            )

        bound_obligation_ids = tuple(dict.fromkeys(
            item.obligation_id for item in rows
        ))
        for item in rows:
            if (
                item.obligation_id not in review_required_obligation_ids
                and method_lane_from_reference_status(str(item.status)) in policy.review_required_lanes
            ):
                review_required_obligation_ids.append(item.obligation_id)
        unit_status.append(MethodUnitProductStatusV1(
            argument_unit_id=unit.argument_unit_id,
            section_id=section_by_unit.get(unit.argument_unit_id, ""),
            lane=lane,
            can_enter_candidate=can_enter_candidate,
            can_enter_verified=can_enter_verified,
            requires_review=requires_review,
            requires_callback=requires_callback,
            evidence_status=",".join(sorted(row_statuses)),
            bound_obligation_ids=bound_obligation_ids,
        ))

    status_by_unit = {item.argument_unit_id: item for item in unit_status}
    section_readiness: list[MethodSectionReadinessV1] = []
    for section in plan.sections:
        section_units = [
            status_by_unit[unit_id] for unit_id in section.argument_unit_ids
            if unit_id in status_by_unit
        ]
        review_ids = tuple(dict.fromkeys(
            item
            for unit in section_units
            for item in unit.bound_obligation_ids
            if item in review_required_obligation_ids
        ))
        section_readiness.append(MethodSectionReadinessV1(
            section_id=section.section_id,
            candidate_ready=bool(section_units) and all(
                unit.can_enter_candidate for unit in section_units
            ),
            verified_ready=bool(section_units) and all(
                unit.can_enter_verified for unit in section_units
            ) and not review_ids,
            blocked_for_safety_reasons=tuple(
                f"unsupported positive risk: {unit_id}"
                for unit_id in unsafe_unit_ids
                if any(unit.argument_unit_id == unit_id for unit in section_units)
            ),
            review_required_ids=review_ids,
        ))

    verified_positive_unit_ids = tuple(
        item.argument_unit_id for item in unit_status if item.can_enter_verified
    )
    candidate_allowed_unit_ids = tuple(
        item.argument_unit_id for item in unit_status if item.can_enter_candidate
    )
    review_required_obligation_ids = tuple(dict.fromkeys(review_required_obligation_ids))

    # Audit-only warnings (D4): exact proofs/placements stay verified/audit
    # metadata and never block candidate generation.
    audit_warnings.extend(_plan_audit_warnings(plan))

    if unsafe_unit_ids:
        readiness: MethodPlanReadiness = "blocked_for_safety"
        blocked_reasons = [
            f"unsupported positive risk: {unit_id}" for unit_id in unsafe_unit_ids
        ]
    elif (
        bool(verified_positive_unit_ids)
        and not review_required_obligation_ids
        and all(section.verified_ready for section in section_readiness)
    ):
        readiness = "verified_ready"
        blocked_reasons = []
    elif not review_required_obligation_ids:
        readiness = "candidate_ready"
        blocked_reasons = []
    else:
        readiness = "candidate_ready_with_review"
        blocked_reasons = []

    review_candidates = build_review_candidates_from_completeness(
        completeness,
        plan=plan,
        policy=policy,
    )

    return MethodPlanProductReadinessV1(
        plan_id=plan.plan_id,
        readiness=readiness,
        section_readiness=tuple(section_readiness),
        unit_status=tuple(unit_status),
        verified_positive_unit_ids=verified_positive_unit_ids,
        candidate_allowed_unit_ids=candidate_allowed_unit_ids,
        review_required_obligation_ids=review_required_obligation_ids,
        blocked_for_safety_reasons=tuple(blocked_reasons),
        review_candidates=review_candidates,
        audit_warnings=tuple(dict.fromkeys(audit_warnings)),
    )


def _plan_audit_warnings(plan: MethodSectionPlanV2) -> list[str]:
    """Exact proof/placement status as audit metadata, never a candidate gate."""

    warnings: list[str] = []
    for proof in plan.move_authority_proofs:
        if proof.state in {"open", "external_pending"}:
            warnings.append(
                f"move authority not closed: {proof.section_id}/{proof.move} "
                f"({proof.state})"
            )
    for unit in plan.argument_units:
        frame = unit.semantic_frame
        if frame is not None and frame.unresolved_relation_ids:
            warnings.append(
                f"semantic frame {frame.frame_id}: unresolved relations "
                + ",".join(frame.unresolved_relation_ids)
            )
    for assignment in plan.obligation_assignments:
        if assignment.placement_state == "unplaced":
            warnings.append(
                f"obligation {assignment.obligation_id} remains unplaced (audit only)"
            )
    return warnings


def build_review_candidates_from_completeness(
    completeness: MethodCompletenessMatrixV1 | None,
    *,
    agenda: ReferenceMethodAgendaV1 | None = None,
    plan: MethodSectionPlanV2 | None = None,
    policy: MethodOutputPolicyV1 | None = None,
) -> tuple[MethodReviewCandidateV1, ...]:
    """Build author-facing review items for every non-positive completeness row.

    ``proposed_body`` is a cautious rephrasing of the author's obligation
    statement (never a repository fact) so the author has editable prose;
    when no statement exists a truthful template sentence is used.  Ordinary
    evidence gaps produce review items that block verified inclusion only.
    """

    policy = policy or build_default_method_output_policy()
    if completeness is None:
        return ()
    obligations_by_id = {
        str(item.obligation_id): item
        for item in (agenda.obligations if agenda is not None else ())
    }
    assignments_by_obligation = plan.assignments_by_obligation() if plan is not None else {}
    # Fallback binding when the plan predates persisted assignments: resolve
    # the section/unit through exact claim membership or source obligation ids.
    section_by_unit = {
        unit_id: section.section_id
        for section in (plan.sections if plan is not None else ())
        for unit_id in section.argument_unit_ids
    }
    unit_by_obligation: dict[str, MethodArgumentUnitV1] = {}
    for unit in (plan.argument_units if plan is not None else ()):
        for obligation_id in unit.source_obligation_ids:
            unit_by_obligation.setdefault(str(obligation_id), unit)
        for claim_id in unit.claim_ids:
            unit_by_obligation.setdefault("claim:" + str(claim_id), unit)
    candidates: list[MethodReviewCandidateV1] = []
    for row in completeness.items:
        lane = method_lane_from_reference_status(str(row.status))
        if lane not in policy.review_required_lanes:
            continue
        obligation = obligations_by_id.get(row.obligation_id)
        statement = str(getattr(obligation, "statement", "") or row.statement or "").strip()
        if statement:
            proposed_body = (
                "The method is intended to address the following point, which "
                "currently awaits repository or author confirmation: "
                + statement.rstrip(".") + "."
            )
            confirmation_question = (
                "Should the Method confirm that " + statement.rstrip(".").lower()
                + "?"
            )
        else:
            proposed_body = (
                f"The author-intended method point for obligation "
                f"{row.obligation_id} awaits evidence or author confirmation "
                "and is not asserted as a repository-verified implementation fact."
            )
            confirmation_question = (
                f"Confirm the author-intended method point for obligation "
                f"{row.obligation_id}."
            )
        assignment = assignments_by_obligation.get(row.obligation_id)
        bound_unit = (
            unit_by_obligation.get(row.obligation_id)
            or unit_by_obligation.get("claim:" + str(next(iter(row.claim_ids), "")))
        )
        needed_evidence = tuple(dict.fromkeys(
            value for value in (
                str(row.next_action or ""),
                str(row.reason or ""),
            ) if str(value).strip()
        ))
        candidates.append(MethodReviewCandidateV1(
            candidate_id=f"review:{row.obligation_id}",
            source_obligation_id=row.obligation_id,
            section_id=(
                assignment.section_id
                if assignment is not None and assignment.section_id
                else (section_by_unit.get(bound_unit.argument_unit_id) if bound_unit is not None else None)
            ),
            argument_unit_id=(
                assignment.argument_unit_id
                if assignment is not None and assignment.argument_unit_id
                else (bound_unit.argument_unit_id if bound_unit is not None else None)
            ),
            lane=lane,
            status=str(row.status),
            proposed_body=proposed_body,
            confirmation_question=confirmation_question,
            needed_evidence=needed_evidence,
            suggested_action=str(row.next_action or "confirm_author_intent_or_provide_evidence"),
            blocks_verified=True,
            blocks_candidate=False,
            trace_refs=(row.obligation_id,),
        ))
    return tuple(candidates)


__all__ = [
    "AuthorStoryNodeV1",
    "METHOD_EVIDENCE_LANES",
    "METHOD_PLAN_READINESS_STATES",
    "MethodDraftBundleV1",
    "MethodEvidenceLane",
    "MethodOutputPolicyV1",
    "MethodPlanProductReadinessV1",
    "MethodPlanReadiness",
    "MethodReviewCandidateV1",
    "MethodSectionReadinessV1",
    "MethodUnitProductStatusV1",
    "STORY_NODE_ROLES",
    "StoryNodeRoleV1",
    "ReaderFacingClaimV1",
    "assess_plan_product_readiness",
    "extract_code_binding_terms",
    "build_default_method_output_policy",
    "build_review_candidates_from_completeness",
    "method_lane_from_authority_lane",
    "method_lane_from_reference_status",
]


# ---------------------------------------------------------------------------
# Reader-facing claim surface (W)
# ---------------------------------------------------------------------------


class ReaderFacingClaimV1(_ProductModel):
    """One paper-language claim surface for the Writer.

    ``paper_statement`` is the sentence-plan authority: for supported rows it
    is a safe paraphrase of repository-supported facts; for candidate rows it
    is author/statement wording that must carry ``requires_caveat=True``.
    ``code_binding_terms`` preserve the raw identifiers as *bindings* so the
    Writer keeps factual fidelity without making them the grammatical center
    of every sentence.  ``may_enter_verified`` is decided by the evidence
    state, never by wording.
    """

    claim_id: str = ""
    obligation_id: str = ""
    section_id: str = ""
    lane: MethodEvidenceLane = "author_intent_unverified"
    paper_statement: str
    code_binding_terms: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    may_enter_verified: bool = False
    requires_caveat: bool = False

    @field_validator("paper_statement")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reader-facing claim statements must not be empty")
        return value.strip()

    @model_validator(mode="after")
    def _clean(self) -> "ReaderFacingClaimV1":
        object.__setattr__(self, "code_binding_terms", _clean_tuple(self.code_binding_terms))
        object.__setattr__(self, "required_qualifiers", _clean_tuple(self.required_qualifiers))
        object.__setattr__(self, "evidence_refs", _clean_tuple(self.evidence_refs))
        return self


def extract_code_binding_terms(text: str) -> tuple[str, ...]:
    """Extract raw code identifiers from a statement as binding terms only.

    ``self._features_dc``, ``GaussianModel.capture``, dotted attribute chains
    and snake_case identifiers are candidates; English prose tokens are not.
    The returned terms are for binding fidelity, never sentence subjects.
    """

    found: list[str] = []
    for match in re.finditer(
        r"(?:self\.[A-Za-z_][A-Za-z0-9_]*|"
        r"[A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*|"
        r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*|"
        r"[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+)",
        str(text or ""),
    ):
        token = match.group(0).strip(".")
        if token and token not in found:
            found.append(token)
    return tuple(found)
