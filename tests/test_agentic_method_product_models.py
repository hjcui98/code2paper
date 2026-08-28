"""P0 shared product contract tests.

Verifies that the lane vocabulary, review candidates, output policy, draft
bundle and plan-readiness report are stable, JSON-roundtrippable and enforce
the fail-closed verified / candidate-permissive split.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
    MethodSectionPlanV2,
    SectionArgumentGraphV1,
)
from code2paper.agentic.method_product_models import (
    METHOD_EVIDENCE_LANES,
    METHOD_PLAN_READINESS_STATES,
    AuthorStoryNodeV1,
    MethodDraftBundleV1,
    MethodEvidenceLane,
    MethodOutputPolicyV1,
    MethodPlanReadiness,
    MethodPlanProductReadinessV1,
    MethodReviewCandidateV1,
    assess_plan_product_readiness,
    build_default_method_output_policy,
    build_review_candidates_from_completeness,
    method_lane_from_authority_lane,
    method_lane_from_reference_status,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    SemanticStageGroupV1,
)


def _review_candidate(**overrides) -> MethodReviewCandidateV1:
    payload = {
        "candidate_id": "review:test",
        "proposed_body": "The method is intended to rank primitives.",
        "confirmation_question": "Should the Method claim that it ranks primitives?",
    }
    payload.update(overrides)
    return MethodReviewCandidateV1(**payload)


def test_review_candidate_proposed_body_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        _review_candidate(proposed_body="   ")
    with pytest.raises(ValidationError):
        _review_candidate(confirmation_question="")


def test_review_candidate_blocks_verified_does_not_imply_blocks_candidate() -> None:
    item = _review_candidate()
    assert item.blocks_verified is True
    assert item.blocks_candidate is False


def test_review_candidate_json_roundtrip() -> None:
    item = _review_candidate(
        lane="author_intent_unverified",
        needed_evidence=["repository symbol", "config value"],
        blocks_verified=True,
        blocks_candidate=False,
    )
    restored = MethodReviewCandidateV1.model_validate_json(item.model_dump_json())
    assert restored == item


def test_lane_enum_and_policy_defaults_are_stable() -> None:
    assert len(METHOD_EVIDENCE_LANES) == 9
    assert "repository_verified" in METHOD_EVIDENCE_LANES
    assert "author_intent_unverified" in METHOD_EVIDENCE_LANES
    assert "formalization_pending" in METHOD_EVIDENCE_LANES
    assert len(METHOD_PLAN_READINESS_STATES) == 4
    for state in ("verified_ready", "candidate_ready", "candidate_ready_with_review", "blocked_for_safety"):
        assert state in METHOD_PLAN_READINESS_STATES

    policy = build_default_method_output_policy()
    assert "repository_verified" in policy.verified_positive_lanes
    assert "repository_partial" not in policy.verified_positive_lanes
    assert "repository_partial" in policy.review_required_lanes
    assert policy.unsupported_positive_blocks_verified is True
    assert policy.unresolved_blocks_candidate is False
    # An ordinary unresolved item is review-required but never candidate-blocking.
    assert "author_intent_unverified" in policy.review_required_lanes
    assert "repository_verified" not in policy.review_required_lanes


def test_output_policy_rejects_unknown_lanes_and_verified_not_in_candidate() -> None:
    with pytest.raises(ValidationError):
        MethodOutputPolicyV1(verified_positive_lanes=("made_up_lane",))
    with pytest.raises(ValidationError):
        MethodOutputPolicyV1(
            verified_positive_lanes=("author_intent_unverified",),
            review_required_lanes=(),
        )
    with pytest.raises(ValidationError):
        MethodOutputPolicyV1(
            review_required_lanes=("repository_verified",),
            candidate_allowed_lanes=("repository_verified",),
        )


def test_lane_mapping_from_reference_status_is_stable() -> None:
    assert method_lane_from_reference_status("supported_by_repository") == "repository_verified"
    assert method_lane_from_reference_status("partially_supported_by_repository") == "repository_partial"
    assert method_lane_from_reference_status("paper_code_mismatch") == "repository_mismatch"
    assert method_lane_from_reference_status("unverified_by_repository") == "author_intent_unverified"
    assert method_lane_from_reference_status("external_evidence_required") == "literature_pending"
    assert method_lane_from_reference_status("formalization_required") == "formalization_pending"
    assert method_lane_from_reference_status("out_of_scope") == "out_of_scope"
    assert method_lane_from_authority_lane("executable_hard") == "repository_verified"
    assert method_lane_from_authority_lane("author_attested") == "author_intent_unverified"
    assert method_lane_from_authority_lane("formal_derivation") == "formalization_pending"
    assert method_lane_from_authority_lane("external_literature") == "literature_pending"


def test_story_node_defaults_to_unverified_author_intent() -> None:
    node = AuthorStoryNodeV1(
        story_node_id="story:o1",
        title="Scoring",
        author_statement="Score each primitive.",
        linked_obligation_ids=("o1",),
    )
    assert node.evidence_lane == "author_intent_unverified"
    assert node.intended_role == "algorithm_step"
    assert AuthorStoryNodeV1.model_validate_json(node.model_dump_json()) == node


def test_draft_bundle_readiness_consistency() -> None:
    with pytest.raises(ValidationError):
        MethodDraftBundleV1(
            candidate_markdown="candidate",
            verified_markdown="",
            plan_readiness="verified_ready",
        )
    bundle = MethodDraftBundleV1(
        candidate_markdown="candidate",
        verified_markdown="verified",
        review_items=[_review_candidate()],
        plan_readiness="candidate_ready_with_review",
    )
    assert bundle.review_items[0].proposed_body
    assert MethodDraftBundleV1.model_validate_json(bundle.model_dump_json()) == bundle


def _claim_set(status: str = "supported") -> AtomicClaimSetV3:
    return AtomicClaimSetV3(
        repo_snapshot_id="repo:product-models",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[AtomicClaimV3(
            claim_id="claim-a",
            canonical_text="The implementation ranks the primitives.",
            fact_ids=["fact-a"],
            covers_obligation_ids=["obl-a"],
            direct_evidence_ids=["span:a.py:1:2"],
            allowed_wording_boundary="ranks primitives only",
            canonical_identity="sha256:claim-a",
            status=status,
        )],
        semantic_stage_groups=[SemanticStageGroupV1(
            stage_id="stage-a",
            name="Ranking stage",
            purpose="Explain the ranking.",
            ordered_claim_ids=["claim-a"],
            covers_obligation_ids=["obl-a"],
        )],
        content_digest="sha256:claims",
    )


def _completeness_matrix(status: str) -> MethodCompletenessMatrixV1:
    return MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:product-models",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="obl-a",
                status=status,
                claim_ids=("claim-a",),
                importance="critical",
                reason="fixture",
                next_action="run scoped repository research",
            ),
        ],
    )


def _plan(
    claim_set: AtomicClaimSetV3,
    completeness: MethodCompletenessMatrixV1 | None = None,
) -> MethodSectionPlanV2:
    from code2paper.agentic.method_architect import build_method_section_plan

    return build_method_section_plan(claims=claim_set, completeness=completeness)


def test_supported_unit_readiness_is_verified_ready() -> None:
    claim_set = _claim_set()
    completeness = _completeness_matrix("supported_by_repository")
    plan = _plan(claim_set, completeness)
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claim_set,
    )
    assert readiness.readiness == "verified_ready"
    assert readiness.verified_positive_unit_ids == (plan.argument_units[0].argument_unit_id,)
    assert readiness.review_required_obligation_ids == ()
    assert readiness.blocked_for_safety_reasons == ()
    assert all(section.verified_ready for section in readiness.section_readiness)


def test_unverified_author_unit_is_candidate_ready_with_review_not_verified() -> None:
    claim_set = _claim_set()
    completeness = _completeness_matrix("unverified_by_repository")
    plan = _plan(claim_set, completeness)
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claim_set,
    )
    assert readiness.readiness == "candidate_ready_with_review"
    assert readiness.verified_positive_unit_ids == ()
    assert readiness.review_required_obligation_ids == ("obl-a",)
    unit_status = readiness.unit_status[0]
    assert unit_status.lane == "author_intent_unverified"
    assert unit_status.can_enter_candidate is True
    assert unit_status.can_enter_verified is False
    assert unit_status.requires_review is True


def test_mismatch_unit_is_candidate_warning_never_verified_positive() -> None:
    claim_set = _claim_set()
    completeness = _completeness_matrix("paper_code_mismatch")
    plan = _plan(claim_set, completeness)
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=completeness,
        claims=claim_set,
    )
    assert readiness.readiness == "candidate_ready_with_review"
    assert readiness.verified_positive_unit_ids == ()
    unit_status = readiness.unit_status[0]
    assert unit_status.lane == "repository_mismatch"
    assert unit_status.can_enter_candidate is True
    assert readiness.review_candidates
    assert readiness.review_candidates[0].lane == "repository_mismatch"


def test_unsupported_positive_without_caveat_is_blocked_for_safety() -> None:
    claim_set = _claim_set()
    plan = _plan(claim_set)
    # The matrix covers a different obligation: the positive claim has no
    # supporting row and the unit has no caveat move -> blocked for safety.
    completeness = MethodCompletenessMatrixV1(
        repo_snapshot_id="repo:product-models",
        project_tree_hash="sha256:tree",
        items=[
            MethodCompletenessItemV1(
                obligation_id="other-obl",
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


def test_review_candidates_from_completeness_have_nonempty_proposed_body() -> None:
    completeness = _completeness_matrix("unverified_by_repository")
    plan = _plan(_claim_set())
    candidates = build_review_candidates_from_completeness(completeness, plan=plan)
    assert len(candidates) == 1
    item = candidates[0]
    assert item.proposed_body.strip()
    assert item.confirmation_question.strip()
    assert item.blocks_verified is True
    assert item.blocks_candidate is False
    assert item.section_id == plan.sections[0].section_id


def test_readiness_json_roundtrip_and_digest() -> None:
    claim_set = _claim_set()
    plan = _plan(claim_set)
    readiness = assess_plan_product_readiness(
        plan=plan,
        completeness=_completeness_matrix("supported_by_repository"),
        claims=claim_set,
    )
    assert readiness.content_digest.startswith("sha256:")
    restored = MethodPlanProductReadinessV1.model_validate_json(readiness.model_dump_json())
    assert restored.content_digest == readiness.content_digest


def test_plan_without_completeness_is_candidate_ready_with_audit_warning() -> None:
    claim_set = _claim_set()
    plan = _plan(claim_set)
    readiness = assess_plan_product_readiness(plan=plan, claims=claim_set)
    assert readiness.readiness == "candidate_ready"
    assert readiness.verified_positive_unit_ids == ()
    assert any("completeness" in warning for warning in readiness.audit_warnings)
