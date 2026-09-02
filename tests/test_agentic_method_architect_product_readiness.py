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
    MethodArgumentUnitV1,
    SectionArgumentGraphV1,
    SectionArgumentMoveV1,
    SectionParagraphPlanV1,
)
from code2paper.agentic.method_argument_brief_models import (
    AuthorMechanismFacetV1,
    FacetEvidenceAlignmentV1,
)
from code2paper.agentic.method_architect import (
    _attach_method_unit_witness_contracts,
    build_method_section_plan_with_product_readiness,
    build_method_section_plan_with_trace,
)
from code2paper.agentic.method_product_models import (
    AuthorStoryNodeV1,
    MethodPlanProductReadinessV1,
    MethodReviewCandidateV1,
    assess_plan_product_readiness,
)
from code2paper.agentic.method_proposition_models import (
    MethodPropositionSetV1,
    MethodPropositionV1,
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


def test_anchored_move_authority_proof_clears_unresolved_for_partial_obligation() -> None:
    """WP-B: partial obligations must not ride on anchored proof unresolved rows."""

    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-1",
                text="The method ranks the primitives with partial coverage.",
                obligation_id="obl-1",
                status="partial",
            ),
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
        ],
        content_digest="sha256:claims",
    )
    completeness = _matrix({"obl-1": "partially_supported_by_repository"})
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claims,
        completeness=completeness,
    )
    for proof in plan.move_authority_proofs:
        if proof.state in {"anchored", "bridge"}:
            assert proof.unresolved_obligation_ids == ()


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


def test_closed_method_unit_slot_order_keeps_required_slots_after_display_budget() -> None:
    from code2paper.agentic.method_architect import _closed_method_unit_slots

    support, publication, ordered = _closed_method_unit_slots(
        section_id="MA-S1",
        paragraph_id="paragraph:MA-S1:method-unit-1",
        original_order=tuple(f"slot-{index}" for index in range(17)),
        support_slots=("support-required",),
        publication_slots=("publication-required",),
    )

    assert support == ("support-required",)
    assert publication == ("publication-required",)
    assert len(ordered) == 19
    assert ordered[-2:] == ("support-required", "publication-required")


def test_broad_claim_coverage_does_not_expand_stage_membership() -> None:
    """Claim evidence coverage is not a paragraph/brief ownership edge."""

    claim = AtomicClaimV3(
        claim_id="claim:broad",
        canonical_text="The stage performs the bounded transformation.",
        fact_ids=["fact:broad"],
        covers_obligation_ids=["obl:stage", "obl:other"],
        direct_evidence_ids=["span:broad.py:1:2"],
        allowed_wording_boundary="bounded transformation only",
        canonical_identity="sha256:claim-broad",
        status="supported",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[claim],
        semantic_stage_groups=[SemanticStageGroupV1(
            stage_id="stage:bounded",
            name="Bounded stage",
            purpose="Explain the bounded transformation.",
            ordered_claim_ids=[claim.claim_id],
            covers_obligation_ids=["obl:stage"],
            organization_priority=1,
        )],
        content_digest="sha256:claims-broad",
    )

    plan, _trace = build_method_section_plan_with_trace(claims=claims)

    assert plan.argument_units[0].source_obligation_ids == ("obl:stage",)


def test_partial_facet_target_carries_intent_surface_contract() -> None:
    """An exact span does not turn a compound partial facet into a fact."""

    facet = AuthorMechanismFacetV1(
        facet_id="facet:partial",
        clause_id="clause:partial",
        exact_source_quote="Use the encoder and guarantee stable forgetting.",
        facet_kind="mechanism",
        semantic_fields={"operation": "Encode the sequence."},
        required=True,
    )
    alignment = FacetEvidenceAlignmentV1(
        facet_id=facet.facet_id,
        status="partial",
        bound_span_ids=("span:encoder.py:10:12",),
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Encoding",
        reader_question="How is the sequence encoded?",
        argument_unit_ids=("unit:partial",),
        paragraphs=(SectionParagraphPlanV1(
            paragraph_id="paragraph:MA-S1:1",
            argument_unit_ids=("unit:partial",),
            required_facet_ids=(facet.facet_id,),
        ),),
    )
    enriched = _attach_method_unit_witness_contracts(
        [graph],
        [MethodArgumentUnitV1(
            argument_unit_id="unit:partial",
            section_role="stage",
            research_question="How?",
        )],
        argument_facets=(facet,),
        facet_alignments=(alignment,),
        publication_field_candidates=(),
    )

    target = enriched[0].paragraphs[0].witness_contract.targets[0]
    assert target.authority_lane == "author_attested"
    assert target.surface_mode == "author_specification"
    assert target.render_policy == "optional"


def test_replan_identity_is_assigned_once_when_new_paragraphs_share_a_unit() -> None:
    from code2paper.agentic.method_architect import _restore_prior_paragraph_identities

    prior = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Stage",
        reader_question="How?",
        paragraphs=(SectionParagraphPlanV1(
            paragraph_id="paragraph:MA-S1:old",
            argument_unit_ids=("unit:shared",),
            required_facet_ids=("facet:old",),
        ),),
    )
    rebuilt = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Stage",
        reader_question="How?",
        paragraphs=(
            SectionParagraphPlanV1(
                paragraph_id="paragraph:MA-S1:new-1",
                argument_unit_ids=("unit:shared",),
                required_facet_ids=("facet:new-1",),
            ),
            SectionParagraphPlanV1(
                paragraph_id="paragraph:MA-S1:new-2",
                argument_unit_ids=("unit:shared",),
                required_facet_ids=("facet:new-2",),
            ),
        ),
    )

    restored = _restore_prior_paragraph_identities(
        prior_sections=(prior,), rebuilt_sections=[rebuilt],
    )[0]
    facet_locations = [
        paragraph.paragraph_id
        for paragraph in restored.paragraphs
        if "facet:old" in paragraph.required_facet_ids
    ]
    assert facet_locations == ["paragraph:MA-S1:new-1"]


def test_remaining_claims_for_same_obligation_extend_stage_not_duplicate_section() -> None:
    claims = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-stage", text="The method builds the descriptor.",
                obligation_id="obl-feature",
            ),
            _claim(
                "claim-late", text="The method normalizes the descriptor.",
                obligation_id="obl-feature",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-feature",
                name="Implementation stage 1",
                purpose="Explain descriptor construction.",
                ordered_claim_ids=["claim-stage"],
                covers_obligation_ids=["obl-feature"],
                organization_priority=1,
            ),
        ],
        content_digest="sha256:claims-same-obligation",
    )
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=claims.repo_snapshot_id,
        project_tree_hash=claims.project_tree_hash,
        items=[
            MethodCompletenessItemV1(
                obligation_id="obl-feature",
                status="supported_by_repository",
                claim_ids=("claim-stage", "claim-late"),
                importance="critical",
            ),
        ],
    )

    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claims,
        completeness=completeness,
        method_name="Per-primitive feature descriptor",
    )

    assert [section.heading for section in plan.sections] == [
        "Per-primitive feature descriptor"
    ]
    assert len(plan.argument_units) == 1
    assert plan.argument_units[0].claim_ids == ("claim-stage", "claim-late")


def test_architect_persists_closed_positive_caveated_proposition_order() -> None:
    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "unverified_by_repository"})
    propositions = MethodPropositionSetV1(
        repo_snapshot_id=claim_set.repo_snapshot_id,
        project_tree_hash=claim_set.project_tree_hash,
        propositions=(
            MethodPropositionV1(
                proposition_id="MP-POS", origin="repository_evidence",
                evidence_lane="repository_verified", may_enter_verified=True,
                source_obligation_ids=("obl-1",), reader_subject="the method",
                transformation="ranks primitives",
            ),
            MethodPropositionV1(
                proposition_id="MP-CAND", origin="author_intent",
                evidence_lane="author_intent_unverified", requires_caveat=True,
                source_obligation_ids=("obl-2",), reader_subject="the intended method",
                transformation="prunes low-ranked primitives",
            ),
        ),
        binding_sidecar_digest="sha256:" + "a" * 64,
    )

    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set, completeness=completeness, propositions=propositions,
    )
    by_obligation = {
        unit.source_obligation_ids[0]: unit for unit in plan.argument_units
        if unit.source_obligation_ids
    }
    assert by_obligation["obl-1"].positive_proposition_ids == ("MP-POS",)
    assert by_obligation["obl-1"].proposition_order == ("MP-POS",)
    assert by_obligation["obl-2"].caveated_proposition_ids == ("MP-CAND",)
    assert by_obligation["obl-2"].proposition_order == ("MP-CAND",)


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


def test_long_organization_stage_titles_remain_separate_sections() -> None:
    claim_set = _claim_set()
    org_rows = [
        (
            "O-ORGANIZATION-01",
            "Offline graph construction from corpus units, adjacency matrices, "
            "and entity spans before any retrieval stage",
        ),
        (
            "O-ORGANIZATION-02",
            "First retrieval stage: relevant entity activation via local "
            "semantic bridging (initialization, iterative propagation, dynamic pruning)",
        ),
        (
            "O-ORGANIZATION-03",
            "Second retrieval stage: passage retrieval via global importance "
            "aggregation and ranking on the hierarchical graph",
        ),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            *_matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"}).items,
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="author_confirmation_required",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    assert len(plan.sections) == 3
    headings = " ".join(section.heading for section in plan.sections).casefold()
    assert "first" in headings or "activation" in headings or "bridging" in headings
    assert "second" in headings or "passage" in headings or "aggregation" in headings
    realized = {
        obligation_id
        for unit in plan.argument_units
        for obligation_id in unit.source_obligation_ids
    }
    assert {"O-ORGANIZATION-01", "O-ORGANIZATION-02", "O-ORGANIZATION-03"} <= realized


def test_unverified_organization_rows_still_become_section_anchors() -> None:
    claim_set = _claim_set()
    org_rows = [
        ("O-ORGANIZATION-01", "Motivation and problem setup"),
        ("O-ORGANIZATION-02", "Offline graph construction"),
        ("O-ORGANIZATION-03", "First retrieval via local activation"),
        ("O-ORGANIZATION-04", "Second retrieval via global ranking"),
        ("O-ORGANIZATION-05", "Overview of the two-stage retrieval"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            *_matrix({"obl-1": "supported_by_repository", "obl-2": "supported_by_repository"}).items,
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    headings = [section.heading for section in plan.sections]
    assert len(headings) == 5
    joined = " ".join(headings).casefold()
    assert "additional repository-verified" not in joined
    assert "motivation" in joined
    assert "offline" in joined
    realized = {
        obligation_id
        for unit in plan.argument_units
        for obligation_id in unit.source_obligation_ids
    }
    assert {"O-ORGANIZATION-01", "O-ORGANIZATION-02", "O-ORGANIZATION-03"} <= realized


def test_near_duplicate_activation_headings_merge_into_one_section() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-act-1",
                text="The method activates entities by local semantic bridging.",
                obligation_id="obl-act-1",
            ),
            _claim(
                "claim-act-2",
                text="The method activates entities by semantic bridging.",
                obligation_id="obl-act-2",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-act-1",
                name="Entity Activation via Local Semantic Bridging",
                purpose="Explain local activation.",
                ordered_claim_ids=["claim-act-1"],
                covers_obligation_ids=["obl-act-1"],
                organization_priority=1,
            ),
            SemanticStageGroupV1(
                stage_id="stage-act-2",
                name="Entity Activation via Semantic Bridging",
                purpose="Explain the activation pass.",
                ordered_claim_ids=["claim-act-2"],
                covers_obligation_ids=["obl-act-2"],
                organization_priority=2,
            ),
        ],
        content_digest="sha256:claims",
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
    )
    assert len(plan.sections) == 1
    realized = {
        obligation_id
        for unit in plan.argument_units
        for obligation_id in unit.source_obligation_ids
    }
    assert {"obl-act-1", "obl-act-2"} <= realized


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
    # Partial support may be caveated on the owning content move; it does not
    # make limitations_or_mismatch a required callback on the section.
    hosting = next(
        section for section in plan.sections
        if partial_unit.argument_unit_id in section.argument_unit_ids
    )
    assert all(
        move.move != "limitations_or_mismatch" or not move.required
        for move in hosting.moves
    )
    # A broad partial obligation keeps its supported subclaims available for
    # sentence-level verification but the whole unit remains review-visible.
    assert readiness.readiness == "candidate_ready_with_review"
    assert readiness.candidate_allowed_unit_ids
    assert partial_unit.argument_unit_id not in readiness.verified_positive_unit_ids
    assert "obl-partial" in readiness.review_required_obligation_ids


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


def test_architect_binds_concept_cards_verified_and_caveated_exactly_once() -> None:
    """Stage 4: concept cards bind to units by obligation, verified/caveated
    separated, and each card is placed on exactly one unit."""
    from code2paper.agentic.method_concept_card_models import (
        ConceptCardBindingV1,
        ConceptCardEvidenceVerdictV1,
        ConceptCardFieldJudgmentV1,
        MethodConceptCardSetV1,
        MethodConceptCardV1,
    )

    claim_set = _claim_set()
    completeness = _matrix({"obl-1": "supported_by_repository", "obl-2": "unverified_by_repository"})
    card_set = MethodConceptCardSetV1(
        repo_snapshot_id=claim_set.repo_snapshot_id,
        project_tree_hash=claim_set.project_tree_hash,
        cards=(
            MethodConceptCardV1(
                concept_key="CK-1", cluster_id="CC-1",
                authority_lane="repository",
                method_subject="ranking descriptor",
                operation="assembles per-primitive statistics",
                may_enter_verified=True,
                evidence_verdict="entailed",
            ),
            MethodConceptCardV1(
                concept_key="CK-2", cluster_id="CC-2",
                authority_lane="author_intent",
                method_subject="intended pruning",
                operation="claimed by the author",
                may_enter_verified=False,
                requires_caveat=True,
                candidate_caveat="author-attested",
            ),
        ),
        evidence_verdicts=(
            ConceptCardEvidenceVerdictV1(
                concept_key="CK-1",
                field_judgments=(
                    ConceptCardFieldJudgmentV1(
                        field_name="method_subject",
                        proposed_value="ranking descriptor",
                        verdict="entailed",
                        evidence_fragment_refs=("frag-1",),
                        rationale="frag-1 establishes the subject",
                    ),
                ),
                overall_verdict="entailed",
                rationale="all fields entailed",
            ),
        ),
        bindings=(
            ConceptCardBindingV1(
                concept_key="CK-1",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("obl-1",),
            ),
            ConceptCardBindingV1(
                concept_key="CK-2",
                field_bindings=(("operation", ("frag-1",)),),
                source_obligation_ids=("obl-2",),
            ),
        ),
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        concept_cards=card_set,
    )
    unit_by_obligation = {
        unit.source_obligation_ids[0]: unit
        for unit in plan.argument_units
        if unit.source_obligation_ids
    }
    unit_1 = unit_by_obligation["obl-1"]
    unit_2 = unit_by_obligation["obl-2"]
    assert unit_1.verified_concept_card_ids == ("CK-1",)
    assert unit_1.caveated_concept_card_ids == ()
    assert unit_2.caveated_concept_card_ids == ("CK-2",)
    assert unit_2.verified_concept_card_ids == ()
    # Each card placed exactly once and orders are closed.
    all_concepts = [
        key
        for unit in plan.argument_units
        for key in (*unit.verified_concept_card_ids, *unit.caveated_concept_card_ids)
    ]
    assert len(all_concepts) == 2
    assert len(set(all_concepts)) == 2
    for unit in plan.argument_units:
        assert set(unit.concept_card_ids) == (
            set(unit.verified_concept_card_ids) | set(unit.caveated_concept_card_ids)
        )
        assert set(unit.concept_card_order) == set(unit.concept_card_ids)


def test_architect_headings_and_reader_questions_are_story_derived() -> None:
    claim_set = _claim_set()
    completeness = _matrix({
        "obl-1": "supported_by_repository",
        "obl-2": "supported_by_repository",
    })
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:motivation",
            title=(
                "Motivation: limitations of vanilla SSMs – they ignore irregular "
                "timespans and are vulnerable to"
            ),
            author_statement=(
                "Vanilla SSMs ignore irregular timespans and are vulnerable to "
                "noisy interactions."
            ),
            intended_role="motivation",
            linked_obligation_ids=("obl-1",),
            linked_claim_ids=("claim-1",),
        ),
        AuthorStoryNodeV1(
            story_node_id="story:rank",
            title="Rank first",
            author_statement="Then rank the remaining primitives.",
            linked_obligation_ids=("obl-2",),
            linked_claim_ids=("claim-2",),
        ),
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    from code2paper.agentic.publication_quality import heading_is_truncated

    for section in plan.sections:
        assert not heading_is_truncated(section.heading)
        assert "transform its inputs into outputs" not in section.reader_question.lower()
        equation_moves = [move for move in section.moves if move.move == "equation_or_derivation"]
        assert equation_moves, section.moves
        assert all(move.unanchored and move.unanchored_owner == "Formalizer" for move in equation_moves)
        assert all(not move.required for move in equation_moves)


def test_wp1_section_content_contract_and_formula_truth() -> None:
    claim_set = _claim_set()
    completeness = _matrix({
        "obl-1": "supported_by_repository",
        "obl-2": "supported_by_repository",
    })
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    for section in plan.sections:
        assert section.heading_constraints
        assert "writer_must_produce_heading_text" in section.heading_constraints
        assert (
            section.formula_obligation_ids
            or (section.formula_not_applicable and section.formula_not_applicable_reason)
        )


def test_wp1_long_story_statement_not_used_as_truncated_heading() -> None:
    claim_set = _claim_set()
    completeness = _matrix({
        "obl-1": "supported_by_repository",
        "obl-2": "supported_by_repository",
    })
    long_statement = (
        "Architecture details enrich embeddings with document identifiers and positional "
        "signals before the Transformer encoder produces contextual representations."
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id="story:long",
            title=long_statement,
            author_statement=long_statement,
            intended_role="setup",
            linked_obligation_ids=("obl-1",),
            linked_claim_ids=("claim-1",),
        ),
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    from code2paper.agentic.publication_quality import heading_is_truncated

    ranking = next(section for section in plan.sections if section.section_id == "MA-S1")
    assert ranking.heading != long_statement
    assert not heading_is_truncated(ranking.heading)
    assert any(
        constraint.startswith("author_statement:")
        and long_statement in constraint
        for constraint in ranking.heading_constraints
    )


def test_wp1_motivation_role_not_appended_when_title_already_starts_with_motivation() -> None:
    from code2paper.agentic.method_architect import (
        _CandidateRowEntry,
        _planning_section_heading,
    )

    title = (
        "Motivation: limitations of vanilla SSMs – they ignore irregular "
        "timespans and are vulnerable to input noise Motivation"
    )
    node = AuthorStoryNodeV1(
        story_node_id="story:motivation",
        title=title,
        author_statement=title,
        intended_role="motivation",
        linked_obligation_ids=("obl-1",),
        linked_claim_ids=("claim-1",),
    )
    row = MethodCompletenessItemV1(
        obligation_id="obl-1",
        status="supported_by_repository",
        claim_ids=("claim-1",),
        importance="critical",
        reason="fixture",
        next_action="run scoped repository research",
    )
    heading, constraints = _planning_section_heading(
        title,
        bucket=[_CandidateRowEntry(row, node)],
    )
    from code2paper.agentic.publication_quality import heading_is_truncated

    assert not heading.endswith("Motivation")
    assert heading.lower().count("motivation") == 1
    assert not heading_is_truncated(heading)
    assert any(item.startswith("author_statement:") for item in constraints)


def test_formalization_required_row_routes_to_equation_not_limitations() -> None:
    claim_set = _claim_set()
    completeness = _matrix({
        "obl-1": "supported_by_repository",
        "obl-2": "supported_by_repository",
    })
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id=completeness.repo_snapshot_id,
        project_tree_hash=completeness.project_tree_hash,
        items=[
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id="obl-formula",
                role="loss",
                statement="The contrastive objective needs a derivation.",
                status="formalization_required",
                claim_ids=(),
                importance="high",
                next_action="formalize the loss expression",
            ),
        ],
    )
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
    )
    formula_unit = next(
        unit for unit in plan.argument_units
        if "obl-formula" in unit.source_obligation_ids
    )
    assert "equation_or_derivation" in formula_unit.allowed_expository_moves
    assert "limitations_or_mismatch" not in formula_unit.allowed_expository_moves
    assert "formal_derivation" in formula_unit.authority_lanes


def test_partial_row_routes_to_owning_content_move_not_limitations() -> None:
    """WP1: ordinary partial support is not the generic limitations bucket."""

    from code2paper.agentic.method_architect import _derive_move_and_lane

    class _Row:
        status = "partially_supported_by_repository"
        role = "encoder"
        next_action = ""
        authority_lane = "executable_hard"

    move, lane = _derive_move_and_lane(_Row())
    assert move == "algorithm_or_data_flow"
    assert move != "limitations_or_mismatch"
    assert lane == "executable_hard"


def test_author_confirmation_row_does_not_route_to_limitations() -> None:
    from code2paper.agentic.method_architect import _derive_move_and_lane

    class _Row:
        status = "author_confirmation_required"
        role = "rationale"
        next_action = "request an explicit author confirmation artifact"
        authority_lane = "author_attested"

    move, lane = _derive_move_and_lane(_Row())
    assert move != "limitations_or_mismatch"
    assert lane == "author_attested"


def test_stage_activation_claims_bind_to_first_retrieval_not_motivation() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-stage",
                text=(
                    "frontier expansion multiplies parent score by contextual "
                    "similarity then prunes scores below a threshold"
                ),
                obligation_id="O-STAGE-02",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-activate",
                name="Entity activation via local semantic bridging",
                purpose="Initialize, propagate, and prune frontier scores",
                ordered_claim_ids=["claim-stage"],
                covers_obligation_ids=["O-STAGE-02"],
                organization_priority=1,
            ),
        ],
        content_digest="sha256:claims",
    )
    org_rows = [
        ("O-ORGANIZATION-01", "Motivation: revisit graph retrieval shortcomings"),
        ("O-ORGANIZATION-02", "Overview: hierarchical graph and two-stage retrieval philosophy"),
        ("O-ORGANIZATION-03", "Offline construction of corpus units and adjacency"),
        ("O-ORGANIZATION-04", "First retrieval: local activation via semantic bridging"),
        ("O-ORGANIZATION-05", "Second retrieval: global rank aggregation"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-02",
                role="pipeline_step",
                statement="Entity activation via local semantic bridging",
                status="supported_by_repository",
                importance="critical",
            ),
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    bound = {
        section.heading: [
            claim_id
            for unit_id in section.argument_unit_ids
            for unit in plan.argument_units
            if unit.argument_unit_id == unit_id
            for claim_id in unit.claim_ids
        ]
        for section in plan.sections
    }
    first = next(
        heading for heading in bound
        if "first retrieval" in heading.casefold() or "activation" in heading.casefold()
    )
    motivation = next(heading for heading in bound if "motivation" in heading.casefold())
    assert "claim-stage" in bound[first]
    assert "claim-stage" not in bound[motivation]
    motivation_unit = next(
        unit for unit in plan.argument_units
        if "motivation" in unit.research_question.casefold()
        or unit.argument_unit_id.startswith("MA-S1")
    )
    assert "equation_or_derivation" not in set(motivation_unit.allowed_expository_moves)
    motivation_section = next(
        section for section in plan.sections if "motivation" in section.heading.casefold()
    )
    assert "mechanism_overview" not in {move.move for move in motivation_section.moves}
    assert "equation_or_derivation" not in {move.move for move in motivation_section.moves}


def test_stage_encoding_claims_fold_into_architecture_not_framework() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-hybrid",
                text=(
                    "The encoder applies shared full attention and a dedicated "
                    "masked attention over same-document passages."
                ),
                obligation_id="O-STAGE-08",
            ),
            _claim(
                "claim-aug",
                text=(
                    "Each passage embedding is augmented with a document identity "
                    "vector and a sinusoidal position encoding."
                ),
                obligation_id="O-STAGE-07",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-hybrid",
                name="Hybrid-attention encoding",
                purpose="Explain the hybrid attention encoder.",
                ordered_claim_ids=["claim-hybrid"],
                covers_obligation_ids=["O-STAGE-08"],
                organization_priority=1,
            ),
            SemanticStageGroupV1(
                stage_id="stage-aug",
                name="Structural augmentation of retrieved passages",
                purpose="Explain document-identity and position augmentation.",
                ordered_claim_ids=["claim-aug"],
                covers_obligation_ids=["O-STAGE-07"],
                organization_priority=2,
            ),
        ],
        content_digest="sha256:claims",
    )
    org_rows = [
        ("O-ORGANIZATION-01", "Motivation: efficiency and cross-passage inference"),
        (
            "O-ORGANIZATION-02",
            "Embedding-based ranking formulation and overall framework",
        ),
        (
            "O-ORGANIZATION-03",
            "Architecture details: enriching embeddings with document identity and position",
        ),
        ("O-ORGANIZATION-04", "Training objective"),
        ("O-ORGANIZATION-05", "Inference procedure"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-08",
                role="pipeline_step",
                statement="Hybrid-attention encoding",
                status="supported_by_repository",
                importance="critical",
            ),
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-07",
                role="pipeline_step",
                statement="Structural augmentation of retrieved passages",
                status="supported_by_repository",
                importance="critical",
            ),
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    headings = [section.heading for section in plan.sections]
    joined = " ".join(headings).casefold()
    assert "hybrid-attention encoding" not in joined
    assert "structural augmentation of retrieved" not in joined
    bound = {
        section.heading: [
            claim_id
            for unit_id in section.argument_unit_ids
            for unit in plan.argument_units
            if unit.argument_unit_id == unit_id
            for claim_id in unit.claim_ids
        ]
        for section in plan.sections
    }
    architecture = next(
        heading for heading in bound if "architecture" in heading.casefold()
    )
    framework = next(
        heading for heading in bound if "framework" in heading.casefold()
    )
    training = next(
        heading for heading in bound if "training" in heading.casefold()
    )
    motivation = next(
        heading for heading in bound if "motivation" in heading.casefold()
    )
    assert "claim-hybrid" in bound[architecture]
    assert "claim-aug" in bound[architecture]
    assert "claim-hybrid" not in bound[framework]
    assert "claim-aug" not in bound[framework]
    assert "claim-hybrid" not in bound[training]
    assert "claim-hybrid" not in bound[motivation]


def test_motivation_goal_text_does_not_steal_stage_activation() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-stage",
                text=(
                    "frontier expansion multiplies parent score by contextual "
                    "similarity then prunes scores below a threshold"
                ),
                obligation_id="O-STAGE-02",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-activate",
                name="Entity activation via local semantic bridging",
                purpose="Initialize, propagate, and prune frontier scores",
                ordered_claim_ids=["claim-stage"],
                covers_obligation_ids=["O-STAGE-02"],
                organization_priority=1,
            ),
        ],
        content_digest="sha256:claims",
    )
    org_rows = [
        (
            "O-ORGANIZATION-01",
            "Motivation: a two-stage retrieval approach (entity activation via semantic bridging)",
        ),
        ("O-ORGANIZATION-02", "Overview: hierarchical graph philosophy"),
        ("O-ORGANIZATION-03", "Offline construction of corpus units"),
        ("O-ORGANIZATION-04", "First retrieval: local activation via semantic bridging"),
        ("O-ORGANIZATION-05", "Second retrieval: global rank aggregation"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-02",
                role="pipeline_step",
                statement="Entity activation via local semantic bridging",
                status="supported_by_repository",
                importance="critical",
            ),
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    bound = {
        section.heading: [
            claim_id
            for unit_id in section.argument_unit_ids
            for unit in plan.argument_units
            if unit.argument_unit_id == unit_id
            for claim_id in unit.claim_ids
        ]
        for section in plan.sections
    }
    first = next(
        heading for heading in bound
        if "first retrieval" in heading.casefold() or "activation" in heading.casefold()
        and "motivation" not in heading.casefold()
    )
    motivation = next(heading for heading in bound if "motivation" in heading.casefold())
    assert "claim-stage" in bound[first]
    assert "claim-stage" not in bound[motivation]


def test_stage_claim_with_mainline_covers_still_binds_first_retrieval() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-stage",
                text=(
                    "frontier expansion multiplies parent score by contextual "
                    "similarity then prunes scores below a threshold"
                ),
                obligation_id="O-METHOD-MAINLINE-01",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-activate",
                name="Entity activation via local semantic bridging",
                purpose="Initialize, propagate, and prune frontier scores",
                ordered_claim_ids=["claim-stage"],
                covers_obligation_ids=["O-STAGE-02"],
                organization_priority=1,
            ),
        ],
        content_digest="sha256:claims",
    )
    org_rows = [
        (
            "O-ORGANIZATION-01",
            "Motivation: a two-stage retrieval approach (entity activation via semantic bridging)",
        ),
        ("O-ORGANIZATION-02", "Overview: hierarchical graph philosophy"),
        ("O-ORGANIZATION-03", "Offline construction of corpus units"),
        ("O-ORGANIZATION-04", "First retrieval: local activation via semantic bridging"),
        ("O-ORGANIZATION-05", "Second retrieval: global rank aggregation"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-02",
                role="pipeline_step",
                statement="Entity activation via local semantic bridging",
                status="supported_by_repository",
                importance="critical",
            ),
            MethodCompletenessItemV1(
                obligation_id="O-METHOD-MAINLINE-01",
                role="method_mainline",
                statement="Two-stage retrieval over an occurrence graph",
                status="supported_by_repository",
                importance="critical",
            ),
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    bound = {
        section.heading: [
            claim_id
            for unit_id in section.argument_unit_ids
            for unit in plan.argument_units
            if unit.argument_unit_id == unit_id
            for claim_id in unit.claim_ids
        ]
        for section in plan.sections
    }
    first = next(
        heading for heading in bound
        if "first retrieval" in heading.casefold() or (
            "activation" in heading.casefold() and "motivation" not in heading.casefold()
        )
    )
    motivation = next(heading for heading in bound if "motivation" in heading.casefold())
    assert "claim-stage" in bound[first]
    assert "claim-stage" not in bound[motivation]


def test_short_stage_encoding_heading_folds_into_long_organization_title() -> None:
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            _claim(
                "claim-encode",
                text="first-hop interaction sequences are encoded with node edge time and co-occurrence signals",
                obligation_id="O-STAGE-01",
            ),
        ],
        semantic_stage_groups=[
            SemanticStageGroupV1(
                stage_id="stage-encode",
                name="Dynamic graph encoding",
                purpose="Encode first-hop sequences.",
                ordered_claim_ids=["claim-encode"],
                covers_obligation_ids=["O-STAGE-01"],
                organization_priority=1,
            ),
        ],
        content_digest="sha256:claims",
    )
    org_rows = [
        (
            "O-ORGANIZATION-01",
            "Dynamic graph encoding: how interaction sequences are represented "
            "with heterogeneous features and aligned",
        ),
        ("O-ORGANIZATION-02", "Motivation: limitations of vanilla state space models"),
        ("O-ORGANIZATION-03", "Redesign: timespan-informed step size"),
    ]
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:architect-product",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="O-STAGE-01",
                role="pipeline_step",
                statement="Dynamic graph encoding",
                status="supported_by_repository",
                importance="critical",
            ),
            *[
                MethodCompletenessItemV1(
                    obligation_id=obligation_id,
                    role="organization",
                    statement=title,
                    status="unverified_by_repository",
                    importance="high",
                )
                for obligation_id, title in org_rows
            ],
        ],
    )
    spine = [
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title=title,
            author_statement=title,
            linked_obligation_ids=(obligation_id,),
        )
        for obligation_id, title in org_rows
    ]
    plan, _readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claim_set,
        completeness=completeness,
        story_spine=spine,
    )
    encoding_headings = [
        section.heading for section in plan.sections
        if "encoding" in section.heading.casefold()
    ]
    assert len(encoding_headings) == 1
    bound = {
        claim_id
        for unit in plan.argument_units
        for claim_id in unit.claim_ids
    }
    assert "claim-encode" in bound
    motivation = next(section.heading for section in plan.sections if "motivation" in section.heading.casefold())
    motivation_claims = [
        claim_id
        for section in plan.sections
        if section.heading == motivation
        for unit_id in section.argument_unit_ids
        for unit in plan.argument_units
        if unit.argument_unit_id == unit_id
        for claim_id in unit.claim_ids
    ]
    assert "claim-encode" not in motivation_claims


def test_optional_rationale_facet_survives_method_unit_compaction() -> None:
    from code2paper.agentic.method_architect import _build_method_units_v2

    rationale = AuthorMechanismFacetV1(
        facet_id="facet:rationale",
        clause_id="clause:rationale",
        exact_source_quote="Avoid explicit relation extraction entirely.",
        facet_kind="motivation",
        brief_id="brief:context",
        semantic_fields={"rationale": "Avoid explicit relation extraction entirely."},
        required=False,
    )
    mechanism = AuthorMechanismFacetV1(
        facet_id="facet:mechanism",
        clause_id="clause:mechanism",
        exact_source_quote="The hierarchical graph organizes entity and passage nodes.",
        facet_kind="mechanism",
        brief_id="brief:mechanism",
        semantic_fields={"operation": "Organize entity and passage nodes."},
        required=True,
    )
    audit = AuthorMechanismFacetV1(
        facet_id="facet:audit",
        clause_id="clause:audit",
        exact_source_quote="Cache the adjacency matrix for faster lookup.",
        facet_kind="constraint",
        brief_id="brief:mechanism",
        semantic_fields={"constraint": "Cache the adjacency matrix."},
        required=False,
    )
    context_unit = MethodArgumentUnitV1(
        argument_unit_id="unit:context",
        section_role="motivation",
        research_question="Why avoid explicit relation extraction?",
        design_objective="Avoid explicit relation extraction entirely.",
        brief_ids=("brief:context",),
        brief_order=("brief:context",),
        allowed_expository_moves=("problem_or_local_context", "design_objective"),
    )
    mechanism_unit = MethodArgumentUnitV1(
        argument_unit_id="unit:mechanism",
        section_role="stage",
        research_question="How is the graph organized?",
        brief_ids=("brief:mechanism",),
        brief_order=("brief:mechanism",),
        allowed_expository_moves=("algorithm_or_data_flow",),
    )
    graph = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Motivation and construction",
        reader_question="Why this graph, and how is it built?",
        argument_unit_ids=("unit:context", "unit:mechanism"),
        moves=(
            SectionArgumentMoveV1(
                move="problem_or_local_context",
                argument_unit_ids=("unit:context",),
            ),
            SectionArgumentMoveV1(
                move="algorithm_or_data_flow",
                argument_unit_ids=("unit:mechanism",),
            ),
        ),
    )
    units, graphs, _trace = _build_method_units_v2(
        [graph],
        [context_unit, mechanism_unit],
        argument_facets=(rationale, mechanism, audit),
        facet_alignments=(
            FacetEvidenceAlignmentV1(facet_id=rationale.facet_id, status="unresolved"),
            FacetEvidenceAlignmentV1(facet_id=mechanism.facet_id, status="unresolved"),
            FacetEvidenceAlignmentV1(facet_id=audit.facet_id, status="unresolved"),
        ),
        publication_field_candidates=(),
    )
    kept = {facet_id for unit in units for facet_id in unit.facet_ids}
    assert "facet:rationale" in kept
    assert "facet:mechanism" in kept
    assert "facet:audit" not in kept
    range_high = max(
        paragraph.expected_sentence_range[1]
        for graph in graphs
        for paragraph in graph.paragraphs
    )
    assert range_high >= 3


def test_pure_context_section_is_placed_before_mechanism_sections() -> None:
    from code2paper.agentic.method_architect import _build_method_units_v2

    encoding = AuthorMechanismFacetV1(
        facet_id="facet:encode",
        clause_id="clause:encode",
        exact_source_quote="Interaction sequences are padded and stacked.",
        facet_kind="mechanism",
        brief_id="brief:encode",
        semantic_fields={"operation": "Pad and stack interaction sequences."},
        required=True,
    )
    motivation = AuthorMechanismFacetV1(
        facet_id="facet:why",
        clause_id="clause:why",
        exact_source_quote="Vanilla state-space models ignore irregular timespans.",
        facet_kind="motivation",
        brief_id="brief:why",
        semantic_fields={"motivation": "Vanilla models ignore irregular timespans."},
        required=False,
    )
    encode_unit = MethodArgumentUnitV1(
        argument_unit_id="unit:encode",
        section_role="stage",
        research_question="How are sequences encoded?",
        brief_ids=("brief:encode",),
        brief_order=("brief:encode",),
        allowed_expository_moves=("algorithm_or_data_flow",),
    )
    why_unit = MethodArgumentUnitV1(
        argument_unit_id="unit:why",
        section_role="motivation",
        research_question="What limitation motivates the redesign?",
        brief_ids=("brief:why",),
        brief_order=("brief:why",),
        allowed_expository_moves=("problem_or_local_context",),
    )
    encoding_graph = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Sequence encoding",
        reader_question="How are sequences encoded?",
        argument_unit_ids=("unit:encode",),
        moves=(SectionArgumentMoveV1(
            move="algorithm_or_data_flow",
            argument_unit_ids=("unit:encode",),
        ),),
    )
    motivation_graph = SectionArgumentGraphV1(
        section_id="MA-S2",
        heading="Problem setting",
        reader_question="What limitation motivates the redesign?",
        argument_unit_ids=("unit:why",),
        moves=(SectionArgumentMoveV1(
            move="problem_or_local_context",
            argument_unit_ids=("unit:why",),
        ),),
    )
    _units, graphs, _trace = _build_method_units_v2(
        [encoding_graph, motivation_graph],
        [encode_unit, why_unit],
        argument_facets=(encoding, motivation),
        facet_alignments=(
            FacetEvidenceAlignmentV1(facet_id=encoding.facet_id, status="unresolved"),
            FacetEvidenceAlignmentV1(facet_id=motivation.facet_id, status="unresolved"),
        ),
        publication_field_candidates=(),
    )
    assert [graph.section_id for graph in graphs] == ["MA-S2", "MA-S1"]
