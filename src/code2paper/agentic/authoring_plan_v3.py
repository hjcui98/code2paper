"""R6.1 V3 authoring plan: build a Method writing plan from V3 obligations,
claims, and explicit gaps, and enforce the plan gate.

Implements design section 9 (R6.1).  The V1 ``EvidenceBoundAuthoringPlan``
in ``authoring_plan.py`` operated on the V1 ``AuthoringInputProjection``
contract.  This V3 module consumes the typed research-plane artifacts
produced by R4 / R5:

- ``IntentObligationGraphV2`` -- typed obligations and ``precedes``
  relations that define the data/control path the Method must follow;
- ``ObligationCoverageReportV2`` -- per-obligation coverage status
  (``supported`` / ``partial`` / ``explicit_gap`` / ``blocked`` /
  ``unresolved``);
- ``AtomicClaimSetV3`` -- authorized unique claims whose
  ``covers_obligation_ids`` field binds them to obligations;
- ``ExplicitCodeGapV1`` -- explicit gaps that may bound obligations and
  must be caveated, never written as positive claims.

The Gemma writer decides the prose organization, but the deterministic
plan gate enforces the R6.1 rules:

1. every ``must_cover`` obligation is terminal (``supported`` /
   ``partial`` / ``explicit_gap`` / ``blocked``), OR the plan is marked
   ``is_incomplete`` and the writer is allowed to emit an incomplete
   Method without pretending it is complete;
2. each planned section has at least one unique claim, or -- for
   ``explicit_gap`` obligations -- a recorded gap with
   ``caveat_required=True``;
3. section order respects the ``precedes`` relations from the intent
   obligation graph (i.e., the data/control path the author declared);
4. no claim appears in more than one section (no duplicates);
5. no hint / gap text leaks as a positive claim (gap-bound sections are
   caveat-only and their gap ids never appear in ``claim_ids``);
6. equations mentioned in a claim's ``canonical_text`` are authorized by
   the claim's ``allowed_wording_boundary`` (i.e., the equation token
   appears in the boundary, or the boundary explicitly permits
   equations);
7. each ``stage`` obligation section has at least one claim or gap (the
   stage intro cannot be empty).

R6.4 hard constraint: this module's source MUST NOT contain
project-specific literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``,
``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    ExplicitCodeGapV1,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
    IntentObligationRelationV2,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)


# ---------------------------------------------------------------------------
# Plan data models
# ---------------------------------------------------------------------------


class AuthoringSectionV3(BaseModel):
    """One planned Method section bound to a single obligation.

    A section is the unit the Gemma writer produces.  It carries the
    authorized claim ids, the explicit gap ids (if any), the qualifier
    template (for ``partial`` / ``explicit_gap`` obligations), and the
    writing instructions.  The writer MUST NOT introduce claims, evidence
    or equations that are not listed here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    heading: str
    purpose: str
    obligation_id: str
    obligation_kind: str
    obligation_priority: str
    coverage_status: str
    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    qualifier_template: tuple[str, ...] = Field(default_factory=tuple)
    gap_ids: tuple[str, ...] = Field(default_factory=tuple)
    caveat_required: bool = False
    allowed_wording_boundary: str = ""
    writing_instructions: tuple[str, ...] = Field(default_factory=tuple)
    organization_preference: str = ""

    @field_validator("section_id", "obligation_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("section_id / obligation_id must not be empty")
        return value


class AuthoringPlanV3(BaseModel):
    """Auditable V3 Method writing plan with a deterministic plan gate.

    The plan is content-addressed so a checkpoint resume can detect drift
    between the persisted plan and the re-built coverage / claim set.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "3.0"
    mode: str = "authoring-plan-v3"
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    intent_graph_digest: str = ""
    coverage_report_digest: str = ""
    claim_set_digest: str = ""
    method_name: str = ""
    author_goal: str = ""
    sections: list[AuthoringSectionV3] = Field(default_factory=list)
    excluded_claim_ids: list[str] = Field(default_factory=list)
    excluded_evidence_ids: list[str] = Field(default_factory=list)
    plan_gate_passed: bool = False
    is_incomplete: bool = False
    is_trusted_ready: bool = False
    gate_failures: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    content_digest: str = ""

    @field_validator("run_id", "repo_snapshot_id", "project_tree_hash")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _compute_digest(self) -> "AuthoringPlanV3":
        payload = {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "run_id": self.run_id,
            "repo_snapshot_id": self.repo_snapshot_id,
            "project_tree_hash": self.project_tree_hash,
            "intent_graph_digest": self.intent_graph_digest,
            "coverage_report_digest": self.coverage_report_digest,
            "claim_set_digest": self.claim_set_digest,
            "method_name": self.method_name,
            "author_goal": self.author_goal,
            "sections": [s.model_dump(mode="json") for s in self.sections],
            "excluded_claim_ids": list(self.excluded_claim_ids),
            "excluded_evidence_ids": list(self.excluded_evidence_ids),
        }
        digest = _digest_payload(payload)
        object.__setattr__(self, "content_digest", digest)
        return self


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------


def build_authoring_plan_v3(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    intent_graph: IntentObligationGraphV2,
    coverage_report: ObligationCoverageReportV2,
    claim_set: AtomicClaimSetV3,
    explicit_gaps: list[ExplicitCodeGapV1] | None = None,
    method_name: str = "",
    author_goal: str = "",
) -> AuthoringPlanV3:
    """Build a V3 authoring plan from typed obligations, claims and gaps.

    The plan is constructed deterministically from the coverage report.
    Authorable must/should-cover obligations become sections in data/control
    order. Organization preferences and verify-only diagnostics never force
    empty Method sections, and redundant obligations already represented by
    an earlier unique claim/gap are coalesced by omission.
    """

    gaps = list(explicit_gaps or [])
    gap_by_id: dict[str, ExplicitCodeGapV1] = {g.gap_id: g for g in gaps}
    claim_by_id: dict[str, AtomicClaimV3] = {c.claim_id: c for c in claim_set.claims}

    # Index coverage items by obligation id.
    coverage_by_obligation: dict[str, ObligationAlignmentV1] = {
        item.obligation_id: item for item in coverage_report.items
    }

    # Order obligations by the data/control path declared in the intent
    # graph.  ``precedes`` relations define a DAG: we topologically sort
    # so a section never appears before one of its prerequisites.
    ordered_obligations = _topological_order(intent_graph)

    sections: list[AuthoringSectionV3] = []
    used_claim_ids: set[str] = set()
    if claim_set.semantic_stage_groups:
        for group in sorted(
            claim_set.semantic_stage_groups,
            key=lambda item: (item.organization_priority, item.stage_id),
        ):
            section_claims = [
                claim_by_id[claim_id]
                for claim_id in group.ordered_claim_ids
                if claim_id in claim_by_id
                and claim_id not in used_claim_ids
                and claim_by_id[claim_id].status in {"supported", "partial"}
            ]
            if not section_claims:
                continue
            used_claim_ids.update(claim.claim_id for claim in section_claims)
            sections.append(AuthoringSectionV3(
                section_id=f"AP-S{len(sections) + 1}",
                heading=group.name,
                purpose=group.purpose,
                obligation_id=(
                    group.covers_obligation_ids[0]
                    if group.covers_obligation_ids
                    else f"stage-group:{group.stage_id}"
                ),
                obligation_kind="stage",
                obligation_priority="should_cover",
                coverage_status=(
                    "partial"
                    if any(claim.status == "partial" for claim in section_claims)
                    else "supported"
                ),
                claim_ids=tuple(claim.claim_id for claim in section_claims),
                evidence_ids=tuple(_dedupe(
                    evidence_id
                    for claim in section_claims
                    for evidence_id in claim.direct_evidence_ids
                )),
                relation_evidence_ids=tuple(_dedupe([
                    *group.relation_evidence_ids,
                    *[
                        evidence_id
                        for claim in section_claims
                        for evidence_id in claim.relation_evidence_ids
                    ],
                ])),
                qualifier_template=tuple(_dedupe(
                    qualifier
                    for claim in section_claims
                    for qualifier in claim.required_qualifiers
                )),
                caveat_required=any(claim.status == "partial" for claim in section_claims),
                allowed_wording_boundary=_merge_allowed_boundaries(
                    [claim.allowed_wording_boundary for claim in section_claims]
                ),
                writing_instructions=(
                    "Use only the listed authorized claims and evidence ids.",
                    "Preserve the stage-group claim order and all required qualifiers.",
                ),
                organization_preference=group.name,
            ))
        # Semantic stage groups are compiler-authorized organization metadata.
        # They replace one-section-per-obligation construction while the
        # coverage report independently enforces all must-cover obligations.
        ordered_obligations = []
    for obligation in ordered_obligations:
        if obligation.priority not in {"must_cover", "should_cover"}:
            continue
        coverage = coverage_by_obligation.get(obligation.obligation_id)
        if coverage is None:
            # No coverage information: treat as unresolved with no claims.
            coverage = ObligationAlignmentV1(
                obligation_id=obligation.obligation_id,
                obligation_kind=obligation.kind,
                obligation_priority=obligation.priority,
                coverage_status="unresolved",
                rationale="No coverage item for obligation.",
            )

        section_claims = [
            claim_by_id[c]
            for c in coverage.matched_claim_ids
            if c in claim_by_id and c not in used_claim_ids
        ]
        section_gaps = [
            gap_by_id[g]
            for g in coverage.matched_gap_ids
            if g in gap_by_id
        ]
        if coverage.coverage_status == "explicit_gap":
            # Terminal gaps authorize caveat text only.  An overlapping broad
            # claim must not leak into the same section as a positive claim.
            section_claims = []
        if not section_claims and not section_gaps:
            # Coverage remains visible in the coverage report.  Do not invent
            # an empty prose section merely to mirror the obligation graph.
            continue
        used_claim_ids.update(c.claim_id for c in section_claims)

        evidence_ids = _dedupe(
            [eid for c in section_claims for eid in c.direct_evidence_ids]
        )
        relation_evidence_ids = _dedupe(
            [eid for c in section_claims for eid in c.relation_evidence_ids]
        )
        qualifier_template = _dedupe(
            [q for c in section_claims for q in c.required_qualifiers]
        )
        # Gaps that bound this obligation also force a caveat.
        caveat_required = (
            coverage.coverage_status in {"partial", "explicit_gap", "blocked"}
            or bool(section_gaps)
        )
        allowed_boundary = _merge_allowed_boundaries(
            [c.allowed_wording_boundary for c in section_claims]
        )
        organization_preference = _organization_preference(obligation)

        sections.append(
            AuthoringSectionV3(
                section_id=f"AP-S{len(sections) + 1}",
                heading=_heading_for(obligation, section_claims, section_gaps),
                purpose=obligation.author_text or obligation.kind,
                obligation_id=obligation.obligation_id,
                obligation_kind=obligation.kind,
                obligation_priority=obligation.priority,
                coverage_status=coverage.coverage_status,
                claim_ids=tuple(c.claim_id for c in section_claims),
                evidence_ids=tuple(evidence_ids),
                relation_evidence_ids=tuple(relation_evidence_ids),
                qualifier_template=tuple(qualifier_template),
                gap_ids=tuple(g.gap_id for g in section_gaps),
                caveat_required=caveat_required,
                allowed_wording_boundary=allowed_boundary,
                writing_instructions=_writing_instructions_for(
                    obligation=obligation,
                    coverage=coverage,
                    section_claims=section_claims,
                    section_gaps=section_gaps,
                ),
                organization_preference=organization_preference,
            )
        )

    if gaps:
        sections.append(AuthoringSectionV3(
            section_id=f"AP-S{len(sections) + 1}",
            heading="Implementation boundaries",
            purpose="State requested behaviors that are not implemented in the inspected repository.",
            obligation_id="explicit-code-gaps",
            obligation_kind="gap_boundary",
            obligation_priority="verify_only",
            coverage_status="explicit_gap",
            gap_ids=tuple(gap.gap_id for gap in gaps),
            caveat_required=True,
            writing_instructions=(
                "Describe each listed item only as an explicit repository boundary.",
                "Do not turn a gap rationale into a positive implementation claim.",
            ),
            organization_preference="final caveat",
        ))

    excluded_claim_ids = [
        c.claim_id for c in claim_set.claims
        if c.claim_id not in used_claim_ids
    ]
    excluded_evidence_ids = _dedupe(
        eid for cid in excluded_claim_ids
        for eid in (
            claim_by_id[cid].direct_evidence_ids
            + claim_by_id[cid].relation_evidence_ids
            if cid in claim_by_id else []
        )
    )

    gate_passed, gate_failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage_report,
        claim_set=claim_set,
        explicit_gaps=gaps,
        intent_graph=intent_graph,
    )

    unresolved_must = bool(coverage_report.unresolved_must_cover_ids)
    has_terminal_gap_or_blocked = any(
        s.coverage_status in {"explicit_gap", "blocked"}
        and s.obligation_priority == "must_cover"
        for s in sections
    )
    # is_incomplete: every must_cover is terminal (no unresolved), but at
    # least one is explicit_gap or blocked.  The plan can be safely
    # output as an incomplete Method.
    is_incomplete = (not unresolved_must) and has_terminal_gap_or_blocked
    # is_trusted_ready: gate passed AND no unresolved must_cover AND no
    # explicit_gap/blocked must_cover (everything is supported, possibly
    # with partial caveats).
    is_trusted_ready = (
        gate_passed
        and not unresolved_must
        and not has_terminal_gap_or_blocked
    )

    recommended = _recommended_actions(
        gate_passed=gate_passed,
        unresolved_must=unresolved_must,
        has_terminal_gap_or_blocked=has_terminal_gap_or_blocked,
        excluded_claim_ids=excluded_claim_ids,
        sections=sections,
    )

    return AuthoringPlanV3(
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        intent_graph_digest=intent_graph.content_digest,
        coverage_report_digest=coverage_report.content_digest,
        claim_set_digest=claim_set.content_digest,
        method_name=method_name,
        author_goal=author_goal,
        sections=sections,
        excluded_claim_ids=excluded_claim_ids,
        excluded_evidence_ids=excluded_evidence_ids,
        plan_gate_passed=gate_passed,
        is_incomplete=is_incomplete,
        is_trusted_ready=is_trusted_ready,
        gate_failures=gate_failures,
        recommended_actions=recommended,
    )


# ---------------------------------------------------------------------------
# Plan gate
# ---------------------------------------------------------------------------


def check_plan_gate(
    *,
    sections: list[AuthoringSectionV3],
    coverage_report: ObligationCoverageReportV2,
    claim_set: AtomicClaimSetV3,
    explicit_gaps: list[ExplicitCodeGapV1],
    intent_graph: IntentObligationGraphV2,
) -> tuple[bool, list[str]]:
    """Evaluate the R6.1 plan gate rules.

    Returns ``(passed, failures)`` where ``failures`` is a sorted list of
    human-readable failure codes.  An empty list means the gate passed.

    The gate is intentionally conservative: any rule violation fails the
    gate, even when other rules pass.  The writer is then responsible
    for either repairing the offending section or routing the obligation
    back to the research loop.
    """

    failures: list[str] = []

    # 1. must_cover terminal or explicitly incomplete.
    #    Unresolved must_cover obligations fail the gate: the plan is
    #    not ready for trusted output and not safely incomplete either.
    unresolved_must = list(coverage_report.unresolved_must_cover_ids)
    if unresolved_must:
        for oid in unresolved_must:
            failures.append(f"unresolved_must_cover:{oid}")

    # Index obligations and relations for the order check.
    obligations_by_id = {
        o.obligation_id: o for o in intent_graph.obligations
    }
    section_index = {
        s.obligation_id: idx for idx, s in enumerate(sections)
    }
    claim_by_id = {c.claim_id: c for c in claim_set.claims}
    gap_ids = {g.gap_id for g in explicit_gaps}

    # 2. each section has at least one unique claim or gap.
    seen_claims: dict[str, str] = {}
    for section in sections:
        # 2a. stage intro must have a claim or a gap.
        if (
            section.obligation_kind == "stage"
            and not section.claim_ids
            and not section.gap_ids
        ):
            failures.append(
                f"stage_intro_missing_claim_or_gap:{section.section_id}"
            )
        # 2b. any section must have at least one claim or gap.
        if not section.claim_ids and not section.gap_ids:
            failures.append(
                f"section_without_claim_or_gap:{section.section_id}"
            )
        # 4. no duplicate claims across sections.
        for cid in section.claim_ids:
            if cid in seen_claims:
                failures.append(
                    f"duplicate_claim:{cid}:{seen_claims[cid]}:{section.section_id}"
                )
            else:
                seen_claims[cid] = section.section_id
        # 5. no hint/gap positive leakage.
        #    - gap-bound sections must be caveat_required.
        #    - gap ids must never appear in claim_ids.
        #    - a section whose coverage_status is explicit_gap must not
        #      have positive claim_ids (the gap is the only authorized
        #      content; any claim bound to an explicit_gap obligation is
        #      a leak).
        if section.gap_ids and not section.caveat_required:
            failures.append(
                f"gap_section_not_caveated:{section.section_id}"
            )
        if set(section.gap_ids) & set(section.claim_ids):
            failures.append(
                f"gap_id_in_claim_ids:{section.section_id}"
            )
        if (
            section.coverage_status == "explicit_gap"
            and section.claim_ids
        ):
            failures.append(
                f"explicit_gap_section_has_positive_claims:{section.section_id}"
            )
        # Validate gap ids reference real gaps.
        for gid in section.gap_ids:
            if gid not in gap_ids:
                failures.append(
                    f"unknown_gap_id:{gid}:{section.section_id}"
                )
        # 6. equation authorization.
        for cid in section.claim_ids:
            claim = claim_by_id.get(cid)
            if claim is None:
                failures.append(f"unknown_claim_id:{cid}:{section.section_id}")
                continue
            unauthorized = _unauthorized_equation_tokens(
                claim.canonical_text, claim.allowed_wording_boundary
            )
            for token in unauthorized:
                failures.append(
                    f"equation_unauthorized:{cid}:{token}"
                )

    # 3. order respects ``precedes`` relations.
    for relation in intent_graph.relations:
        if relation.relation != "precedes":
            continue
        src_idx = section_index.get(relation.source_obligation_id)
        tgt_idx = section_index.get(relation.target_obligation_id)
        if src_idx is None or tgt_idx is None:
            # An obligation may be excluded from the plan (e.g., it has
            # no typed targets and no claims).  Only fail when both
            # endpoints are present and out of order.
            continue
        if src_idx >= tgt_idx:
            failures.append(
                f"order_violation:{relation.source_obligation_id}->{relation.target_obligation_id}"
            )

    # 7. stage intro has claim -- already covered by rule 2a.

    return (not failures, sorted(set(failures)))


# ---------------------------------------------------------------------------
# Brief and helpers
# ---------------------------------------------------------------------------


def authoring_plan_v3_brief(plan: AuthoringPlanV3, *, include_exclusions: bool = True) -> str:
    """Render a short human-readable brief for the V3 authoring plan."""

    lines = [
        "V3 evidence-bound Method writing plan:",
        f"- Method: {plan.method_name or 'unspecified'}.",
        f"- Author goal: {plan.author_goal or 'unspecified'}.",
        f"- Plan gate passed: {plan.plan_gate_passed}.",
        f"- Trusted ready: {plan.is_trusted_ready}.",
        f"- Incomplete (safe to emit): {plan.is_incomplete}.",
    ]
    if plan.gate_failures:
        lines.append("- Gate failures:")
        for failure in plan.gate_failures[:20]:
            lines.append(f"  - {failure}")
    lines.append(
        "- Follow these planned sections only when their claim and evidence ids are present."
    )
    for section in plan.sections[:20]:
        caveat = " yes" if section.caveat_required else " no"
        lines.append(
            f"- {section.section_id} {section.heading}: "
            f"obligation={section.obligation_id}; "
            f"claims={', '.join(section.claim_ids) or 'none'}; "
            f"evidence={', '.join(section.evidence_ids) or 'none'}; "
            f"gaps={', '.join(section.gap_ids) or 'none'}; "
            f"coverage={section.coverage_status}; caveat_required={caveat}."
        )
        for instruction in section.writing_instructions[:3]:
            lines.append(f"  - {instruction}")
        if section.qualifier_template:
            lines.append(
                "  - Required qualifier template: " + "; ".join(section.qualifier_template)
            )
    if include_exclusions and plan.excluded_claim_ids:
        lines.append(
            "- Excluded claim ids not allowed: "
            + ", ".join(plan.excluded_claim_ids)
            + "."
        )
    return "\n".join(lines)


def write_authoring_plan_v3(path: str, plan: AuthoringPlanV3) -> str:
    """Persist a V3 authoring plan as JSON."""

    import json as _json
    from pathlib import Path

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        _json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(output)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _topological_order(
    intent_graph: IntentObligationGraphV2,
) -> list[IntentObligationV2]:
    """Return obligations in an order that respects ``precedes`` relations.

    Obligations not mentioned in any relation retain their original
    declaration order.  When a cycle is detected (which should not happen
    in a valid intent graph), the original declaration order is used as
    a tie-breaker and the cycle is broken arbitrarily.
    """

    obligations = list(intent_graph.obligations)
    if not obligations:
        return []
    obligations_by_id = {o.obligation_id: o for o in obligations}
    index_in_declaration = {
        o.obligation_id: idx for idx, o in enumerate(obligations)
    }

    # Build adjacency: edge src -> tgt means src precedes tgt, so src
    # must appear before tgt.
    successors: dict[str, list[str]] = {o.obligation_id: [] for o in obligations}
    in_degree: dict[str, int] = {o.obligation_id: 0 for o in obligations}
    for relation in intent_graph.relations:
        if relation.relation != "precedes":
            continue
        src = relation.source_obligation_id
        tgt = relation.target_obligation_id
        if src not in in_degree or tgt not in in_degree:
            continue
        successors[src].append(tgt)
        in_degree[tgt] += 1

    # Kahn's algorithm with declaration-order tie-breaking.
    pending = sorted(
        [oid for oid, deg in in_degree.items() if deg == 0],
        key=lambda oid: index_in_declaration[oid],
    )
    ordered_ids: list[str] = []
    emitted: set[str] = set()
    while pending:
        current = pending.pop(0)
        if current in emitted:
            continue
        emitted.add(current)
        ordered_ids.append(current)
        for successor in successors[current]:
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                # Insert in declaration order.
                pending.append(successor)
        pending.sort(key=lambda oid: index_in_declaration[oid])

    # Append any remaining obligations (cycle break).
    for obligation in obligations:
        if obligation.obligation_id not in emitted:
            ordered_ids.append(obligation.obligation_id)

    return [obligations_by_id[oid] for oid in ordered_ids if oid in obligations_by_id]


def _heading_for(
    obligation: IntentObligationV2,
    claims: list[AtomicClaimV3],
    gaps: list[ExplicitCodeGapV1],
) -> str:
    """Derive a short section heading from the obligation / claims / gaps."""

    if claims:
        text = claims[0].canonical_text.strip().rstrip(".")
    elif gaps:
        text = gaps[0].topic.strip()
    else:
        text = obligation.author_text.strip()
    if not text:
        return f"{obligation.kind} {obligation.obligation_id}"
    words = text.split()
    heading = " ".join(words[:7])
    return heading[:1].upper() + heading[1:]


def _writing_instructions_for(
    *,
    obligation: IntentObligationV2,
    coverage: ObligationAlignmentV1,
    section_claims: list[AtomicClaimV3],
    section_gaps: list[ExplicitCodeGapV1],
) -> tuple[str, ...]:
    """Compose deterministic writing instructions for a section."""

    instructions: list[str] = [
        "Write only the implementation behavior supported by the listed evidence ids.",
        "Do not add mechanisms, motivations, or results absent from the frozen code evidence.",
    ]
    if coverage.coverage_status == "partial":
        instructions.append(
            "Caveat this section: state the implemented fragment and omit unsupported extensions."
        )
    if section_gaps:
        gap_topics = "; ".join(g.topic for g in section_gaps[:3])
        instructions.append(
            f"Record explicit code gap(s) for: {gap_topics}. "
            "Do not present the gap as a positive Method claim."
        )
    if obligation.kind == "stage":
        instructions.append(
            "Use this section as a stage introduction: open with the claim that "
            "characterizes the stage behavior, then describe the evidence-backed mechanism."
        )
    if obligation.kind == "method_mainline":
        instructions.append(
            "Use this section as the Method mainline: summarize the data/control path "
            "in the order the author declared."
        )
    return tuple(instructions)


def _organization_preference(obligation: IntentObligationV2) -> str:
    """Extract the organization preference (stage hint) from typed targets."""

    for target in obligation.typed_behavior_targets:
        if target.organization_preference:
            return target.organization_preference
    return ""


def _merge_allowed_boundaries(boundaries: list[str]) -> str:
    """Merge multiple ``allowed_wording_boundary`` strings into one."""

    tokens: list[str] = []
    seen: set[str] = set()
    for boundary in boundaries:
        if not boundary:
            continue
        for token in boundary.split():
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
    return " ".join(tokens)


def _unauthorized_equation_tokens(canonical_text: str, allowed_boundary: str) -> list[str]:
    """Return equation tokens that appear in ``canonical_text`` but are not
    authorized by ``allowed_boundary``.

    Equation tokens are ``$...$`` formulas or ``name = expression`` style
    equations.  A token is authorized when either:

    - the exact equation string (whitespace-normalized) appears in the
      boundary, OR
    - the boundary explicitly permits equations (contains the literal
      ``equation`` or ``formula`` token).

    Python keyword arguments (e.g. ``prompt=prompt``, ``request_id=self``,
    ``sampling_params=sampling_params``) are excluded from equation
    detection because they are code syntax, not mathematical formulas.
    A ``name=value`` pattern is treated as a kwarg (not an equation)
    when it has no spaces around ``=`` and the RHS is a bare identifier,
    ``self``, ``None``, ``True``, ``False``, or a numeric literal.
    """

    formulas = re.findall(r"\$([^$]+)\$", canonical_text)
    raw_equations = re.findall(
        r"([A-Za-z_][A-Za-z0-9_]*\s*=\s*[^,.;]+)", canonical_text
    )
    # Filter out Python kwargs: patterns like ``name=value`` (no spaces
    # around ``=``) where the RHS *starts with* a bare identifier or
    # literal that is immediately followed by a kwarg terminator
    # (``)``, ``]``, ``}``, ``,``, whitespace, or end of string).  The
    # terminator lookahead is required because the RHS regex
    # ``[^,.;]+`` greedily captures trailing prose inside call
    # expressions, e.g. ``sampling_params=sampling_params) and returns
    # the output``.  Equations with operators in the RHS (e.g.
    # ``x=y+z``) are NOT matched because ``+`` is not a terminator.
    kwarg_rhs_pattern = re.compile(
        r"^(self|None|True|False|null|nil"
        r"|-[0-9]+(?:\.[0-9]+)?"
        r"|[0-9]+(?:\.[0-9]+)?"
        r"|0x[0-9A-Fa-f]+"
        r"|[A-Za-z_][A-Za-z0-9_]*)"
        r"(?=[\)\]\},\s]|$)"
    )
    inline_equations: list[str] = []
    for expr in raw_equations:
        # Split on the first ``=`` to check LHS/RHS.
        lhs, _, rhs = expr.partition("=")
        lhs_stripped = lhs.strip()
        rhs_stripped = rhs.strip()
        has_spaces = " = " in expr or expr.startswith(lhs_stripped + " =")
        if not has_spaces and kwarg_rhs_pattern.match(rhs_stripped):
            # ``name=value`` without spaces and RHS starts with a bare
            # identifier or literal followed by a kwarg terminator →
            # Python kwarg, not an equation.
            continue
        inline_equations.append(expr)
    needed = {f"$ {expr.strip()} $" for expr in formulas}
    for expr in inline_equations:
        compact = expr.replace(" ", "")
        needed.add(compact)
    if not needed:
        return []
    boundary_normalized = allowed_boundary.replace(" ", "")
    boundary_lower = allowed_boundary.lower()
    if "equation" in boundary_lower or "formula" in boundary_lower:
        return []
    unauthorized: list[str] = []
    for token in needed:
        compact_token = token.replace(" ", "")
        if compact_token in boundary_normalized:
            continue
        unauthorized.append(token)
    return unauthorized


def _recommended_actions(
    *,
    gate_passed: bool,
    unresolved_must: bool,
    has_terminal_gap_or_blocked: bool,
    excluded_claim_ids: list[str],
    sections: list[AuthoringSectionV3],
) -> list[str]:
    """Compose the ``recommended_actions`` list for a plan."""

    actions: list[str] = []
    if gate_passed:
        if has_terminal_gap_or_blocked:
            actions.append("emit_method_as_incomplete_with_explicit_gaps")
        else:
            actions.append("authoring_plan_ready_for_evidence_constrained_method_writing")
    else:
        if unresolved_must:
            actions.append("return_to_research_loop_for_unresolved_must_cover")
        if excluded_claim_ids:
            actions.append("review_or_drop_excluded_claims")
        if any(
            s.coverage_status == "explicit_gap" and s.claim_ids
            for s in sections
        ):
            actions.append("remove_positive_claims_from_explicit_gap_sections")
        if not actions:
            actions.append("repair_authoring_plan_sections")
    return actions


def _dedupe(values: Any) -> list[str]:
    """De-duplicate an iterable of string-like values, preserving order."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _digest_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AuthoringSectionV3",
    "AuthoringPlanV3",
    "build_authoring_plan_v3",
    "check_plan_gate",
    "authoring_plan_v3_brief",
    "write_authoring_plan_v3",
]
