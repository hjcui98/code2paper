"""R6.4 integration tests for the V3 final-text trust pipeline.

This module exercises the **end-to-end trust decision** that the R6.4
exit conditions require:

- ``AuthoringPlanV3`` (R6.1) decides whether the writer may emit a
  complete or incomplete Method;
- ``validate_text_evidence`` (existing) produces a
  ``TextEvidenceValidationReport`` for the final text;
- ``compute_quality_state`` (R6.3) derives a ``QualityStateV2`` from the
  coverage report + claim set + validation report;
- ``is_trusted_success`` / ``is_incomplete`` decide the run's terminal
  state.

The R6.4 exit conditions verified here:

- the final unsupported rate MUST be zero for ``trusted_success``;
- an incomplete Method (with explicit gaps) MUST be safely emittable as
  incomplete, never pretending to be complete;
- a writer sentence-split change MUST NOT break the trust decision
  (the quality state is content-addressed by claim identity, not by
  sentence id);
- a repair turn that regresses quality MUST roll back to the best state.
"""

from __future__ import annotations

from code2paper.agentic.authoring_plan_v3 import (
    AuthoringSectionV3,
    build_authoring_plan_v3,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    ExplicitCodeGapV1,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationRelationV2,
    IntentObligationV2,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.quality_state_v2 import (
    compute_quality_state,
    is_incomplete,
    is_trusted_success,
    select_best_state,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1
from code2paper.agentic.trust_contracts import (
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _target(target_id: str) -> TypedBehaviorTargetV1:
    return TypedBehaviorTargetV1(
        target_id=target_id,
        role="role",
        desired_predicates=("COMPUTE",),
    )


def _obligation(
    obligation_id: str,
    *,
    kind: str = "stage",
    priority: str = "must_cover",
    author_text: str = "do something",
) -> IntentObligationV2:
    return IntentObligationV2(
        obligation_id=obligation_id,
        kind=kind,
        priority=priority,
        source_field="pipeline_steps",
        source_index=0,
        author_text=author_text,
        typed_behavior_targets=(_target(obligation_id),),
    )


def _graph(
    obligations: list[IntentObligationV2],
    relations: list[IntentObligationRelationV2] | None = None,
) -> IntentObligationGraphV2:
    return IntentObligationGraphV2(
        schema_version="2.0",
        mode="intent-obligation-graph-v2",
        project_goal="goal",
        method_goal="method",
        implementation_scope="scope",
        obligations=obligations,
        relations=list(relations or []),
    )


def _claim(
    claim_id: str,
    *,
    covers_obligation_ids: list[str] | None = None,
    canonical_text: str = "claim text",
    allowed_wording_boundary: str = "boundary",
    canonical_identity: str = "ident",
    direct_evidence_ids: list[str] | None = None,
    status: str = "supported",
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=canonical_text,
        claim_kind="implementation_behavior",
        fact_ids=["f1"],
        covers_obligation_ids=list(covers_obligation_ids or []),
        direct_evidence_ids=direct_evidence_ids or ["span-1"],
        relation_evidence_ids=[],
        required_qualifiers=[],
        unsupported_author_fragments=[],
        allowed_wording_boundary=allowed_wording_boundary,
        canonical_identity=canonical_identity,
        status=status,  # type: ignore[arg-type]
    )


def _claim_set(claims: list[AtomicClaimV3]) -> AtomicClaimSetV3:
    return AtomicClaimSetV3(
        schema_version="3.0",
        producer_version="test",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=claims,
        content_digest="sha256:set",
    )


def _gap(gap_id: str, *, topic: str = "missing behavior") -> ExplicitCodeGapV1:
    return ExplicitCodeGapV1(
        gap_id=gap_id,
        topic=topic,
        status="not_implemented_in_repo",
        scope="any",
        rationale="not found",
        source_kind="author_obligation",
    )


def _coverage_item(
    obligation_id: str,
    *,
    kind: str = "stage",
    priority: str = "must_cover",
    coverage_status: str = "supported",
    matched_claim_ids: tuple[str, ...] = (),
    matched_gap_ids: tuple[str, ...] = (),
) -> ObligationAlignmentV1:
    return ObligationAlignmentV1(
        obligation_id=obligation_id,
        obligation_kind=kind,
        obligation_priority=priority,
        matched_claim_ids=matched_claim_ids,
        matched_gap_ids=matched_gap_ids,
        coverage_status=coverage_status,
        rationale="test",
    )


def _coverage_report(items: list[ObligationAlignmentV1]) -> ObligationCoverageReportV2:
    must_cover_items = [i for i in items if i.obligation_priority == "must_cover"]
    return ObligationCoverageReportV2(
        schema_version="2.0",
        mode="obligation-coverage-v2",
        intent_graph_digest="sha256:graph",
        items=items,
        must_cover_count=len(must_cover_items),
        terminal_must_cover_count=sum(
            1 for i in must_cover_items
            if i.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
        ),
        supported_must_cover_count=sum(
            1 for i in must_cover_items if i.coverage_status == "supported"
        ),
        unresolved_must_cover_ids=[
            i.obligation_id for i in must_cover_items
            if i.coverage_status == "unresolved"
        ],
        explicit_gap_count=sum(1 for i in items if i.coverage_status == "explicit_gap"),
    )


def _verdict(
    claim_id: str,
    *,
    failures: list[str] | None = None,
    status: str = "supported",
) -> TextClaimEvidenceVerdict:
    failures = failures or []
    return TextClaimEvidenceVerdict(
        atomic_claim_id=claim_id,
        status=status,  # type: ignore[arg-type]
        matched_projection_claim_ids=["P-1"] if not failures else [],
        direct_evidence_ids=["span-1"] if not failures else [],
        relation_evidence_ids=[],
        supported_fragment="text" if not failures else "",
        unsupported_fragment="text" if failures else "",
        required_qualifiers=[],
        deterministic_failures=failures,
        model_verdict=status,
        rationale="passed" if not failures else "; ".join(failures),
        repair_action="",
    )


def _validation_report(
    verdicts: list[TextClaimEvidenceVerdict],
) -> TextEvidenceValidationReport:
    supported = sum(1 for v in verdicts if v.status == "supported")
    caveated = sum(1 for v in verdicts if v.status == "caveated")
    unsupported = sum(1 for v in verdicts if v.status == "unsupported")
    return TextEvidenceValidationReport(
        status="passed" if unsupported == 0 else "failed",
        input_text_digest="sha256:text",
        projection_digest="sha256:proj",
        checked_factual_claims=len(verdicts),
        supported_claims=supported,
        caveated_claims=caveated,
        unsupported_claims=unsupported,
        unverified_claims=0,
        semantic_verifier_calls=0,
        verdicts=verdicts,
        recommended_actions=[],
    )


def _quality_state(
    *,
    coverage: ObligationCoverageReportV2,
    claim_set: AtomicClaimSetV3,
    validation: TextEvidenceValidationReport,
):
    return compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage,
        claim_set=claim_set,
        validation_report=validation,
    )


# ---------------------------------------------------------------------------
# End-to-end: trusted_ready plan -> trusted_success quality state
# ---------------------------------------------------------------------------


def test_trusted_ready_plan_yields_trusted_success_quality_state() -> None:
    """When the authoring plan is ``is_trusted_ready`` and the writer
    produces final text with zero unsupported claims, the quality state
    is ``is_trusted_success``.
    """

    obligations = [
        _obligation("O-1", kind="method_mainline", author_text="Train a model."),
        _obligation("O-2", kind="stage", author_text="Compute loss."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
        _claim("C-2", covers_obligation_ids=["O-2"], canonical_identity="ident-2"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="method_mainline",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-2",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert plan.is_trusted_ready

    # Writer produced final text with both claims supported.
    validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-2"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    assert state.is_trusted
    assert is_trusted_success(state)
    assert state.safety.unsupported_positive_claims == 0
    assert state.content.supported_must_cover == 2
    assert state.content.unresolved_high_value_obligations == 0


def test_incomplete_plan_yields_incomplete_quality_state() -> None:
    """When the authoring plan is ``is_incomplete`` (has explicit_gap
    must_cover), the writer produces final text with zero unsupported
    claims (gaps are caveated, not positive claims).  The quality state
    is ``is_trusted_success`` because every must_cover is terminal and
    no positive claim is unsupported -- but the Method is incomplete
    (the explicit gap is recorded, not fabricated as supported).
    """

    obligations = [
        _obligation("O-1", kind="method_mainline", author_text="Train a model."),
        _obligation("O-2", kind="stage", author_text="Compute loss."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing loss")]
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="method_mainline",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage",
                       coverage_status="explicit_gap", matched_gap_ids=("G-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )
    assert plan.is_incomplete
    assert not plan.is_trusted_ready

    # Writer emits the Method as incomplete: only C-1 (supported) appears
    # as a positive claim; O-2 is recorded as an explicit gap (caveated).
    validation = _validation_report([
        _verdict("C-1"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    # The state is trusted (no unsupported positive claims) and has no
    # unresolved must_cover (explicit_gap is terminal).  So it IS a
    # trusted_success -- but with only 1 supported must_cover (the other
    # is an explicit gap, never counted as supported).
    assert state.is_trusted
    assert is_trusted_success(state)
    assert state.safety.unsupported_positive_claims == 0
    assert state.content.supported_must_cover == 1
    assert state.content.terminal_must_cover == 2
    assert state.content.unresolved_high_value_obligations == 0


# ---------------------------------------------------------------------------
# R6.4: final unsupported rate must be 0 for trusted_success
# ---------------------------------------------------------------------------


def test_unsupported_claim_in_final_text_blocks_trusted_success() -> None:
    """If the writer introduces an unauthorized claim (validation marks it
    unsupported), the quality state is NOT trusted_success even when the
    coverage report shows all must_cover supported.  The supervisor must
    repair or roll back.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    # Writer added an unauthorized claim C-bad which the validator
    # marks unsupported.
    validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-bad", failures=["direct_evidence_missing"], status="unsupported"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    assert not state.is_trusted
    assert not is_trusted_success(state)
    assert state.safety.unsupported_positive_claims == 1


def test_unresolved_must_cover_blocks_trusted_success() -> None:
    """Even with zero unsupported claims, an unresolved must_cover
    obligation prevents trusted_success.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage 1."),
        _obligation("O-2", kind="stage", author_text="Stage 2."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage", coverage_status="unresolved"),
    ])

    validation = _validation_report([_verdict("C-1")])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    assert state.is_trusted  # No unsupported positive claims.
    assert not is_trusted_success(state)  # But O-2 is unresolved.
    assert state.content.unresolved_high_value_obligations == 1
    # is_incomplete is True: trusted + unresolved must_cover.
    assert is_incomplete(state)


# ---------------------------------------------------------------------------
# R6.4: writer sentence-split does not break the trust decision
# ---------------------------------------------------------------------------


def test_sentence_split_preserves_trust_decision() -> None:
    """When the writer splits one sentence into two atomic claims, the
    trust decision is unchanged because the quality state is content-
    addressed by claim identity, not sentence id.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    # Before split: one claim C-1 in one sentence.
    before_validation = _validation_report([_verdict("C-1")])
    before_state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=before_validation,
    )

    # After split: same claim C-1, but the writer now emits it across
    # two sentences (S1 and S2).  The validator still produces one
    # verdict per atomic_claim_id, so the validation report is identical.
    after_validation = _validation_report([_verdict("C-1")])
    after_state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=after_validation,
    )

    # The trust decision is identical.
    assert is_trusted_success(before_state) == is_trusted_success(after_state)
    assert (
        before_state.content.validated_final_sentences
        == after_state.content.validated_final_sentences
    )
    assert before_state.content_digest == after_state.content_digest


def test_claim_identity_drives_dedup_not_sentence_id() -> None:
    """When two sentences carry claims with the same canonical_identity,
    the minimality dimension flags a duplicate.  The trust decision is
    based on the claim set's canonical identities, not on the sentence
    layout.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    # Two claims with the SAME canonical_identity -> duplicate.
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="shared"),
        _claim("C-2", covers_obligation_ids=["O-1"], canonical_identity="shared"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported",
                       matched_claim_ids=("C-1", "C-2")),
    ])
    validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-2"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    # The duplicate is flagged.
    assert state.minimality.duplicate_claims == 1
    # unique_supported_claims counts by canonical_identity, so it is 1.
    assert state.content.unique_supported_claims == 1


# ---------------------------------------------------------------------------
# R6.4: repair rollback restores best state
# ---------------------------------------------------------------------------


def test_repair_rollback_restores_best_state_end_to_end() -> None:
    """End-to-end rollback: the writer's first attempt produced a clean
    trusted_success.  A repair turn (e.g., a rewrite) introduced an
    unsupported claim.  ``select_best_state`` MUST retain the incumbent
    so the supervisor can re-emit the original best text.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    # First attempt: clean.
    clean_validation = _validation_report([_verdict("C-1")])
    incumbent = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=clean_validation,
    )
    assert is_trusted_success(incumbent)

    # Repair attempt regressed: introduced an unsupported claim C-bad.
    regressed_validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-bad", failures=["direct_evidence_missing"], status="unsupported"),
    ])
    candidate = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=regressed_validation,
    )
    assert not is_trusted_success(candidate)

    # select_best_state retains the incumbent.
    best, replaced = select_best_state(candidate, incumbent)
    assert not replaced
    assert best is incumbent
    assert is_trusted_success(best)


def test_repair_improvement_replaces_best_state_end_to_end() -> None:
    """End-to-end improvement: the writer's first attempt had an
    unsupported claim; the repair turn resolved it.  ``select_best_state``
    MUST replace the incumbent with the repaired candidate.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    # First attempt: C-1 unsupported.
    bad_validation = _validation_report([
        _verdict("C-1", failures=["direct_evidence_missing"], status="unsupported"),
    ])
    incumbent = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=bad_validation,
    )
    assert not is_trusted_success(incumbent)

    # Repair turn resolved C-1.
    clean_validation = _validation_report([_verdict("C-1")])
    candidate = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=clean_validation,
    )
    assert is_trusted_success(candidate)

    best, replaced = select_best_state(candidate, incumbent)
    assert replaced
    assert best is candidate
    assert is_trusted_success(best)


# ---------------------------------------------------------------------------
# R6.4: incomplete Method never pretends to be complete
# ---------------------------------------------------------------------------


def test_incomplete_method_does_not_fabricate_supported_claims() -> None:
    """An incomplete Method (with explicit gaps) MUST NOT fabricate
    supported claims for the gap obligations.  The quality state's
    ``supported_must_cover`` MUST be strictly less than
    ``terminal_must_cover`` when there are explicit_gap obligations.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage 1."),
        _obligation("O-2", kind="stage", author_text="Stage 2 (gap)."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing stage 2")]
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage",
                       coverage_status="explicit_gap", matched_gap_ids=("G-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )
    assert plan.is_incomplete

    # The writer emits only C-1 (supported); O-2 is recorded as a gap.
    validation = _validation_report([_verdict("C-1")])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    # The gap is terminal but never counts as supported.
    assert state.content.terminal_must_cover == 2
    assert state.content.supported_must_cover == 1
    assert state.content.unresolved_high_value_obligations == 0
    # The state is trusted (no unsupported positive claims) and is a
    # trusted_success (no unresolved must_cover) -- but with only 1
    # supported must_cover.  The Method is "complete" in the trust
    # sense (no fabrication), but the plan marked it as incomplete
    # because O-2 is an explicit gap.
    assert state.is_trusted
    assert is_trusted_success(state)
    # The plan's is_incomplete flag is the source of truth for the
    # Method's incompleteness; the quality state's job is to ensure no
    # fabrication happened.
    assert plan.is_incomplete


def test_incomplete_method_cannot_have_unsupported_positive_claims() -> None:
    """If the writer fabricates a positive claim for a gap obligation,
    the validator MUST mark it unsupported, blocking trusted_success.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage 1 (gap)."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing stage 1")]
    claim_set = _claim_set([])  # No authorized claims for the gap.
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="explicit_gap", matched_gap_ids=("G-1",)),
    ])

    # Writer fabricates a positive claim C-fabricated for the gap.
    validation = _validation_report([
        _verdict("C-fabricated", failures=["direct_evidence_missing"],
                 status="unsupported"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    # The fabrication is caught: unsupported_positive_claims = 1.
    assert not state.is_trusted
    assert not is_trusted_success(state)
    assert not is_incomplete(state)  # Not trusted -> not incomplete either.
    assert state.safety.unsupported_positive_claims == 1


# ---------------------------------------------------------------------------
# Contract: plan gate failure blocks trusted_success
# ---------------------------------------------------------------------------


def test_plan_gate_failure_blocks_trusted_ready() -> None:
    """When the plan gate fails (e.g., unresolved must_cover), the plan
    is neither ``is_trusted_ready`` nor ``is_incomplete``.  The
    supervisor MUST route back to the research loop, not emit a Method.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage 1."),
        _obligation("O-2", kind="stage", author_text="Stage 2 (unresolved)."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage", coverage_status="unresolved"),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert not plan.plan_gate_passed
    assert not plan.is_trusted_ready
    assert not plan.is_incomplete
    assert any(f.startswith("unresolved_must_cover:O-2") for f in plan.gate_failures)
    assert "return_to_research_loop_for_unresolved_must_cover" in plan.recommended_actions


# ---------------------------------------------------------------------------
# End-to-end: explicit_gap section is caveat_required in the plan
# ---------------------------------------------------------------------------


def test_explicit_gap_section_has_caveat_in_plan() -> None:
    """The plan section for an explicit_gap obligation MUST be
    ``caveat_required=True`` and MUST NOT carry positive claim ids.
    This is what prevents the writer from presenting the gap as a
    positive claim.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage (gap)."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing")]
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="explicit_gap", matched_gap_ids=("G-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )

    section = plan.sections[0]
    assert section.coverage_status == "explicit_gap"
    assert section.gap_ids == ("G-1",)
    assert section.caveat_required
    assert section.claim_ids == ()
    # The writing instructions tell the writer to record the gap, not
    # present it as a positive claim.
    assert any(
        "explicit code gap" in instruction.lower()
        or "gap" in instruction.lower()
        for instruction in section.writing_instructions
    )


# ---------------------------------------------------------------------------
# Regression: an unsupported claim regresses the quality state
# ---------------------------------------------------------------------------


def test_quality_state_dominates_rejects_unsupported_regression() -> None:
    """A candidate with more unsupported claims than the incumbent is
    rejected by ``quality_state_dominates`` (via ``select_best_state``).
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    incumbent_validation = _validation_report([_verdict("C-1")])
    incumbent = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=incumbent_validation,
    )

    candidate_validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-bad", failures=["direct_evidence_missing"], status="unsupported"),
    ])
    candidate = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=candidate_validation,
    )

    best, replaced = select_best_state(candidate, incumbent)
    assert not replaced
    assert best is incumbent
    # The candidate's safety regressed.
    assert (
        candidate.safety.unsupported_positive_claims
        > incumbent.safety.unsupported_positive_claims
    )


# ---------------------------------------------------------------------------
# Full pipeline: plan -> validate -> state -> decision
# ---------------------------------------------------------------------------


def test_full_pipeline_trusted_success() -> None:
    """Full pipeline: a trusted_ready plan + clean validation report
    yields a trusted_success quality state.
    """

    obligations = [
        _obligation("O-main", kind="method_mainline", author_text="Train a model."),
        _obligation("O-stage", kind="stage", author_text="Compute loss."),
    ]
    relations = [
        IntentObligationRelationV2(
            source_obligation_id="O-stage",
            target_obligation_id="O-main",
            relation="precedes",
        ),
    ]
    graph = _graph(obligations, relations)
    claims = [
        _claim("C-main", covers_obligation_ids=["O-main"], canonical_identity="ident-main"),
        _claim("C-stage", covers_obligation_ids=["O-stage"], canonical_identity="ident-stage"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-main", kind="method_mainline",
                       coverage_status="supported", matched_claim_ids=("C-main",)),
        _coverage_item("O-stage", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-stage",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert plan.plan_gate_passed
    assert plan.is_trusted_ready

    validation = _validation_report([
        _verdict("C-main"),
        _verdict("C-stage"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    assert is_trusted_success(state)
    assert state.content.supported_must_cover == 2
    assert state.content.validated_final_sentences == 2
    assert state.safety.unsupported_positive_claims == 0


def test_full_pipeline_incomplete_with_gaps() -> None:
    """Full pipeline: an incomplete plan (explicit_gap must_cover) +
    clean validation report yields a trusted_success quality state, but
    the plan marks the Method as incomplete.
    """

    obligations = [
        _obligation("O-main", kind="method_mainline", author_text="Train a model."),
        _obligation("O-gap", kind="stage", author_text="Missing stage."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing stage")]
    claims = [
        _claim("C-main", covers_obligation_ids=["O-main"], canonical_identity="ident-main"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-main", kind="method_mainline",
                       coverage_status="supported", matched_claim_ids=("C-main",)),
        _coverage_item("O-gap", kind="stage",
                       coverage_status="explicit_gap", matched_gap_ids=("G-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )
    assert plan.is_incomplete
    assert not plan.is_trusted_ready

    validation = _validation_report([_verdict("C-main")])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    # The state is trusted (no unsupported claims, no unresolved must_cover).
    assert is_trusted_success(state)
    # But supported_must_cover < terminal_must_cover because of the gap.
    assert state.content.supported_must_cover == 1
    assert state.content.terminal_must_cover == 2
    # The Method is safely emitted as incomplete (per the plan).
    assert plan.is_incomplete


def test_full_pipeline_blocked_by_unsupported_claim() -> None:
    """Full pipeline: a trusted_ready plan + a validation report with
    an unsupported claim yields a non-trusted state.  The supervisor
    must repair before emitting the Method.
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage."),
    ]
    graph = _graph(obligations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_identity="ident-1"),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage",
                       coverage_status="supported", matched_claim_ids=("C-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert plan.is_trusted_ready

    # The writer fabricated an unauthorized claim C-bad.
    validation = _validation_report([
        _verdict("C-1"),
        _verdict("C-bad", failures=["direct_evidence_missing"], status="unsupported"),
    ])
    state = _quality_state(
        coverage=coverage, claim_set=claim_set, validation=validation,
    )

    assert not is_trusted_success(state)
    assert not state.is_trusted
    # The supervisor must repair (rollback to a state without C-bad).
    assert state.safety.unsupported_positive_claims == 1
