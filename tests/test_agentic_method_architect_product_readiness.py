"""D-package tests: Method Architect as argument organizer with graded gates.

Verifies that the Architect consumes the author story spine for section
organization, keeps exact proof/placement machinery as audit metadata, and
produces the four-state product readiness without blocking candidate
generation on ordinary unresolved evidence.
"""

from __future__ import annotations

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    SemanticStageGroupV1,
)
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    SectionArgumentGraphV1,
)
from code2paper.agentic.method_architect import (
    build_method_section_plan_with_product_readiness,
    build_method_section_plan_with_trace,
)
from code2paper.agentic.method_product_models import (
    AuthorStoryNodeV1,
    MethodPlanProductReadinessV1,
    MethodReviewCandidateV1,
    assess_plan_product_readiness,
)


def _claim(
    claim_id: str,
    *,
    text: str,
    obligation_id: str,
    status: str = "supported",
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=text,
        fact_ids=[f"fact-{claim_id}"],
        covers_obligation_ids=[obligation_id],
        direct_evidence_ids=[f"span:{claim_id}.py:1:2"],
        allowed_wording_boundary=f"{claim_id} behavior only",
        canonical_identity=f"sha256:{claim_id}",
        status=status,
    )


def _claim_set() -> AtomicClaimSetV3:
    return AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim("claim-1", text="The method ranks the primitives.", obligation_id="obl-1"),
            _claim("claim-2", text="The method prunes the lowest-ranked primitives.", obligation_id="obl-2"),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-1",
                name="Ranking stage",
                purpose="Explain the ranking.",
                ordered_claim_ids=["claim-1"],
                covers_obligation_ids=["obl-1"],
                organization_priority=1,
            ),
            SemanticStageGroupV1(
                stage_id="stage-2",
                name="Pruning stage",
                purpose="Explain the pruning.",
                ordered_claim_ids=["claim-2"],
                covers_obligation_ids=["obl-2"],
                organization_priority=2,
            ),
        ],
        content_digest="sha256:claims",
    )


def _matrix(statuses: dict[str, str]) -> MethodCompletenessMatrixV1:
    return MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                status=status,
                claim_ids=(f"claim-{obligation_id.split('-')[-1]}",),
                importance="critical",
                reason="fixture",
                next_action="run scoped repository research",
            )
            for obligation_id, status in statuses.items()
        ],
    )


def test_supported_unit_is_candidate_and_verified_ready() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    plan, readiness, trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    assert readiness.readiness == "verified_ready"
    assert len(plan.sections) == 2
    assert set(readiness.verified_positive_unit_ids) == {
        unit.argument_unit_id for unit in plan.argument_units
    }
    assert readiness.review_required_obligation_ids == ()
    assert isinstance(trace["product_readiness"], dict)


def test_unverified_author_unit_is_candidate_ready_with_review_and_not_verified() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "unverified_by_repository"})
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    assert readiness.readiness == "candidate_ready_with_review"
    assert readiness.review_required_obligation_ids == ("obl-2",)
    unit_status_by_id = {item.argument_unit_id: item for item in readiness.unit_status}
    for unit in plan.argument_units:
        status = unit_status_by_id[unit.argument_unit_id]
        assert status.can_enter_candidate is True
    assert readiness.verified_positive_unit_ids
    assert "obl-2" not in {
        obligation_id
        for status in readiness.unit_status
        if status.can_enter_verified
        for obligation_id in status.bound_obligation_ids
    }
    assert readiness.review_candidates
    assert all(isinstance(item, MethodReviewCandidateV1) and item.proposed_body for item in readiness.review_candidates)


def test_mismatch_unit_is_candidate_warning_not_positive_verified() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "paper_code_mismatch", "obl-2": "supported_by_repository"})
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    assert readiness.readiness == "candidate_ready_with_review"
    mismatch_status = next(
        item for item in readiness.unit_status if item.lane == "repository_mismatch"
    )
    assert mismatch_status.can_enter_candidate is True
    assert mismatch_status.can_enter_verified is False
    assert mismatch_status.requires_review is True
    assert all(
        item.argument_unit_id != mismatch_status.argument_unit_id
        for item in readiness.unit_status
        if item.can_enter_verified
    )


def test_open_move_authority_is_audit_warning_not_candidate_blocker() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    plan, _trace = build_method_section_plan_with_trace(
        claims=claim_set,
        completeness=completeness,
    )
    # Attach exact-proof metadata (as ``replan_moves_with_trace`` would) with
    # one open move-authority proof and one unplaced assignment.  These are
    # verified/audit records and must not change the candidate/verified gates.
    from code2paper.agentic.method_argument_models import (
        MethodSectionPlanV2,
        MoveAuthorityProofV1,
        ObligationMoveAssignmentV1,
    )

    section = plan.sections[0]
    unit_id = section.argument_unit_ids[0]
    move = section.moves[0].move
    assignment = ObligationMoveAssignmentV1(
        obligation_id="obl-1",
        importance="critical",
        status="supported_by_repository",
        placement_state="assigned",
        section_id=section.section_id,
        argument_unit_id=unit_id,
        required_move=move,
        unresolved_reason="",
        supporting_anchor_ids=("claim-1",),
    )
    open_proof = MoveAuthorityProofV1(
        section_id=section.section_id,
        argument_unit_ids=(unit_id,),
        move=move,
        required=False,
        unresolved_obligation_ids=("obl-1",),
        state="open",
    )
    unplaced = ObligationMoveAssignmentV1(
        obligation_id="obl-extra",
        importance="critical",
        status="unverified_by_repository",
        placement_state="unplaced",
        unresolved_reason="no closed target in the fixture",
    )
    upgraded = MethodSectionPlanV2.model_validate(plan.model_copy(update={
        "obligation_assignments": (assignment, unplaced),
        "move_authority_proofs": (open_proof,),
    }).model_dump(mode="json"))
    readiness = assess_plan_product_readiness(
        plan=upgraded,
        completeness=completeness,
        claims=claim_set,
    )
    # Exact proofs stay audit metadata: candidate/verified states unchanged.
    assert readiness.readiness == "verified_ready"
    assert readiness.blocked_for_safety_reasons == ()
    assert any("move authority not closed" in warning for warning in readiness.audit_warnings)
    assert any("remains unplaced (audit only)" in warning for warning in readiness.audit_warnings)


def test_unsupported_positive_without_caveat_route_is_blocked_for_safety() -> None:
    claim_set = _claim_set()
    # The matrix does not cover the unit's obligation at all: the positive
    # claim is unbound and the plan (built without completeness) has no caveat
    # move, so the unsafe positive cannot be distinguished safely.
    plan, _trace = build_method_section_plan_with_trace(claims=claim_set)
    completeness = _matrix({"obl-other": "unverified_by_repository"})
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            MethodCompletenessItemV1(
                obligation_id="obl-other",
                status="unverified_by_repository",
                claim_ids=(),
                importance="critical",
            ),
        ],
    )
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claim_set,
    )
    assert readiness.readiness == "blocked_for_safety"
    assert readiness.blocked_for_safety_reasons
    assert readiness.candidate_allowed_unit_ids == ()
    assert isinstance(readiness, MethodPlanProductReadinessV1)


def test_author_story_order_changes_section_order() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    # Author story: pruning comes before ranking (reverse of compiler priority).
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:prune",
            title="Prune first",
            author_statement="Start by pruning low-ranked primitives.",
            linked_obligation_ids=("obl-2",),
            linked_claim_ids=("claim-2",),
        ),
        AuthorStoryNodeV1(
            story_node_id="story:rank",
            title="Rank first",
            author_statement="Then rank the remaining primitives.",
            linked_obligation_ids=("obl-1",),
            linked_claim_ids=("claim-1",),
        ),
    ]
    plan_with_spine, _readiness, trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    assert len(plan_with_spine.sections) == 2
    assert plan_with_spine.sections[0].heading == "Pruning stage"
    assert trace["story_spine"][0]["story_node_id"] == "story:prune"
    assert trace["story_spine"][0]["realized_sections"] == ["MA-S1"]

    # Without the spine, the compiler priority order (ranking first) is kept.
    plan_plain, _readiness_plain, trace_plain = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    assert plan_plain.sections[0].heading == "Ranking stage"
    assert trace_plain["input_digests"]["story_spine"]["used"] is False


def test_story_spine_unrealized_author_point_is_recorded_not_dropped() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:absent",
            title="An unimplemented author point",
            author_statement="The method should also support live visualization.",
            linked_obligation_ids=("obl-absent",),
        ),
    ]
    _plan, _readiness, trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    assert trace["story_spine"][0]["realized_sections"] == ["unrealized"]
    assert trace["story_spine"][0]["evidence_lane"] == "author_intent_unverified"


def test_organization_spine_consolidates_candidate_points_without_dropping_units() -> None:
    claim_set = _claim_set()
    extra_rows = [
        MethodCompletenessItemV1(
            obligation_id=f"O-COMPONENT-{index:02d}",
            role="component",
            statement=(
                "Normalize ranking features" if index <= 3
                else "Apply pruning and export outputs"
            ),
            status="author_confirmation_required",
            importance="high",
        )
        for index in range(1, 9)
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            *_matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"}).items,
            MethodCompletenessItemV1(
                obligation_id="O-ORGANIZATION-01",
                role="organization",
                statement="Feature ranking",
                status="author_confirmation_required",
                importance="high",
            ),
            MethodCompletenessItemV1(
                obligation_id="O-ORGANIZATION-02",
                role="organization",
                statement="Pruning and output",
                status="author_confirmation_required",
                importance="high",
            ),
            *extra_rows,
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:O-ORGANIZATION-01",
            title="Feature ranking",
            author_statement="Normalize and rank the input features.",
            linked_obligation_ids=("O-ORGANIZATION-01",),
        ),
        AuthorStoryNodeV1(
            story_node_id="story:O-ORGANIZATION-02",
            title="Pruning and output",
            author_statement="Apply pruning and export the result.",
            linked_obligation_ids=("O-ORGANIZATION-02",),
        ),
        *[
            AuthorStoryNodeV1(
                story_node_id=f"story:O-COMPONENT-{index:02d}",
                title=(
                    "Normalize ranking features" if index <= 3
                    else "Apply pruning and export outputs"
                ),
                author_statement=(
                    "Normalize ranking features" if index <= 3
                    else "Apply pruning and export outputs"
                ),
                linked_obligation_ids=(f"O-COMPONENT-{index:02d}",),
            )
            for index in range(1, 9)
        ],
    ]

    plan, _readiness, trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )

    assert len(plan.sections) == 2
    expected_obligations = {
        "obl-1", "obl-2", "O-ORGANIZATION-01", "O-ORGANIZATION-02",
        *(f"O-COMPONENT-{index:02d}" for index in range(1, 9)),
    }
    realized = {
        obligation_id
        for unit in plan.argument_units
        for obligation_id in unit.source_obligation_ids
    }
    assert expected_obligations <= realized
    assert all(row["realized_sections"] != ["unrealized"] for row in trace["story_spine"])


# ---------------------------------------------------------------------------
# Package P: candidate units from story/completeness rows
# ---------------------------------------------------------------------------


def test_partial_row_without_claim_ids_materializes_candidate_section() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id="obl-partial",
                role="score_prediction",
                statement="Score each primitive by its learned importance.",
                status="partially_supported_by_repository",
                claim_ids=(),
                matched_fact_ids=("fact-partial-1",),
                importance="high",
                reason="partial fixture",
            ),
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:score",
            title="Score Prediction",
            author_statement="Predict an importance score for each primitive.",
            linked_obligation_ids=("obl-partial",),
        ),
    ]
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    headings = [section.heading for section in plan.sections]
    assert any("Score Prediction" in heading for heading in headings)
    partial_unit = next(
        unit for unit in plan.argument_units
        if "obl-partial" in unit.source_obligation_ids
    )
    assert partial_unit.claim_ids == ()
    assert partial_unit.supported is False
    assert partial_unit.unresolved_inputs == ("obl-partial:partially_supported_by_repository",)
    assert partial_unit.source_artifact_ids == ("fact-partial-1",)
    assert "limitations_or_mismatch" in partial_unit.allowed_expository_moves
    # A partial lane is candidate-permitted and review-optional by the P0
    # contract (partial may enter verified only with preserved qualifiers);
    # it never blocks the candidate and never enters verified unqualified.
    assert readiness.readiness == "candidate_ready"
    assert readiness.candidate_allowed_unit_ids
    assert "obl-partial" not in readiness.verified_positive_unit_ids


def test_author_confirmation_row_becomes_candidate_review_not_verified_fact() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id="obl-author",
                role="rationale",
                statement="Rendering is avoided in the inference function.",
                status="author_confirmation_required",
                claim_ids=(),
                importance="medium",
                next_action="request an explicit author confirmation artifact",
            ),
        ],
    )
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    author_unit = next(
        unit for unit in plan.argument_units
        if "obl-author" in unit.source_obligation_ids
    )
    assert author_unit.authority_lanes == ("author_attested",)
    assert author_unit.supported is False
    assert readiness.readiness == "candidate_ready_with_review"
    assert "obl-author" not in readiness.verified_positive_unit_ids
    assert any(
        candidate.source_obligation_id == "obl-author"
        and candidate.blocks_candidate is False
        for candidate in readiness.review_candidates
    )


def test_explicit_code_gap_row_materializes_with_caveat_move() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id="obl-gap",
                role="inference",
                statement="Deploy the trained scorer without per-view rendering.",
                status="explicit_code_gap",
                claim_ids=(),
                importance="critical",
                next_action="ask the author to accept the scoped code gap",
            ),
        ],
    )
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    gap_unit = next(
        unit for unit in plan.argument_units
        if "obl-gap" in unit.source_obligation_ids
    )
    assert "limitations_or_mismatch" in gap_unit.allowed_expository_moves
    assert gap_unit.supported is False
    assert readiness.readiness == "candidate_ready_with_review"
    assert readiness.blocked_for_safety_reasons == ()


def test_out_of_scope_row_is_not_materialized_as_candidate_prose() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"})
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id="obl-scope",
                role="marketing",
                statement="Industry-scale deployment notes.",
                status="out_of_scope",
                claim_ids=(),
                importance="low",
            ),
        ],
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    assert not any(
        "obl-scope" in unit.source_obligation_ids for unit in plan.argument_units
    )
