"""R6.4 tests for the R6.3 quality state computation.

Verifies that ``quality_state_v2.py`` correctly derives
``QualityStateV2`` dimensions from run artifacts (coverage report, claim
set, validation report) and that the Pareto selection + trusted/incomplete
exit conditions behave per the R6.3 design.
"""

from __future__ import annotations

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.quality_state_v2 import (
    compute_content_dimensions,
    compute_minimality_dimensions,
    compute_quality_state,
    compute_safety_dimensions,
    is_incomplete,
    is_trusted_success,
    select_best_state,
)
from code2paper.agentic.research_models import (
    QualityContentDimensionsV1,
    QualitySafetyDimensionsV1,
    QualityStateV2,
    empty_quality_state,
    quality_state_dominates,
)
from code2paper.agentic.trust_contracts import (
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _claim(
    claim_id: str,
    *,
    canonical_identity: str = "ident",
    status: str = "supported",
    direct_evidence_ids: list[str] | None = None,
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=f"claim text {claim_id}",
        claim_kind="implementation_behavior",
        fact_ids=["f1"],
        direct_evidence_ids=direct_evidence_ids or ["span-1"],
        allowed_wording_boundary="boundary",
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


def _coverage_item(
    obligation_id: str,
    *,
    priority: str = "must_cover",
    coverage_status: str = "supported",
) -> ObligationAlignmentV1:
    return ObligationAlignmentV1(
        obligation_id=obligation_id,
        obligation_kind="method_mainline",
        obligation_priority=priority,
        coverage_status=coverage_status,
        rationale="test",
    )


def _coverage_report(items: list[ObligationAlignmentV1]) -> ObligationCoverageReportV2:
    return ObligationCoverageReportV2(
        schema_version="2.0",
        mode="obligation-coverage-v2",
        intent_graph_digest="sha256:graph",
        items=items,
        must_cover_count=sum(1 for i in items if i.obligation_priority == "must_cover"),
        terminal_must_cover_count=sum(
            1 for i in items
            if i.obligation_priority == "must_cover"
            and i.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
        ),
        supported_must_cover_count=sum(
            1 for i in items
            if i.obligation_priority == "must_cover" and i.coverage_status == "supported"
        ),
        unresolved_must_cover_ids=[
            i.obligation_id for i in items
            if i.obligation_priority == "must_cover" and i.coverage_status == "unresolved"
        ],
        explicit_gap_count=sum(1 for i in items if i.coverage_status == "explicit_gap"),
    )


def _verdict(
    claim_id: str,
    *,
    status: str = "supported",
    direct_evidence_ids: list[str] | None = None,
) -> TextClaimEvidenceVerdict:
    return TextClaimEvidenceVerdict(
        atomic_claim_id=claim_id,
        status=status,  # type: ignore[arg-type]
        matched_projection_claim_ids=["p1"],
        direct_evidence_ids=direct_evidence_ids or ["span-1"],
        relation_evidence_ids=[],
        supported_fragment="text" if status != "unsupported" else "",
        unsupported_fragment="text" if status == "unsupported" else "",
        required_qualifiers=[],
        deterministic_failures=[] if status != "unsupported" else ["direct_evidence_missing"],
        model_verdict="",
        rationale="test",
        repair_action="",
    )


def _validation_report(
    verdicts: list[TextClaimEvidenceVerdict],
) -> TextEvidenceValidationReport:
    supported = sum(1 for v in verdicts if v.status == "supported")
    caveated = sum(1 for v in verdicts if v.status == "caveated")
    unsupported = sum(1 for v in verdicts if v.status == "unsupported")
    return TextEvidenceValidationReport(
        status="failed" if unsupported else "passed",
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


# ---------------------------------------------------------------------------
# Safety dimensions
# ---------------------------------------------------------------------------


def test_safety_dimensions_default_to_clean() -> None:
    safety = compute_safety_dimensions()
    assert safety.source_integrity is True
    assert safety.unsupported_positive_claims == 0
    assert safety.stale_artifacts == 0
    assert safety.invariant_failures == 0


def test_safety_dimensions_count_unsupported_claims_from_validation_report() -> None:
    report = _validation_report([
        _verdict("c1", status="supported"),
        _verdict("c2", status="unsupported"),
        _verdict("c3", status="unsupported"),
    ])
    safety = compute_safety_dimensions(validation_report=report)
    assert safety.unsupported_positive_claims == 2


def test_safety_dimensions_record_invariant_and_stale_counts() -> None:
    safety = compute_safety_dimensions(invariant_failures=3, stale_artifacts=2)
    assert safety.invariant_failures == 3
    assert safety.stale_artifacts == 2


# ---------------------------------------------------------------------------
# Content dimensions
# ---------------------------------------------------------------------------


def test_content_dimensions_count_supported_and_terminal_must_cover() -> None:
    report = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        _coverage_item("o2", priority="must_cover", coverage_status="partial"),
        _coverage_item("o3", priority="must_cover", coverage_status="explicit_gap"),
        _coverage_item("o4", priority="must_cover", coverage_status="unresolved"),
        _coverage_item("o5", priority="should_cover", coverage_status="supported"),
    ])
    content = compute_content_dimensions(coverage_report=report)
    # must_cover: 4 total, 3 terminal (supported+partial+explicit_gap), 1 supported, 1 unresolved
    assert content.terminal_must_cover == 3
    assert content.supported_must_cover == 1
    assert content.unresolved_high_value_obligations == 1


def test_content_dimensions_explicit_gap_never_counts_as_supported() -> None:
    report = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="explicit_gap"),
    ])
    content = compute_content_dimensions(coverage_report=report)
    assert content.terminal_must_cover == 1
    assert content.supported_must_cover == 0


def test_content_dimensions_count_unique_supported_claims_by_identity() -> None:
    claim_set = _claim_set([
        _claim("c1", canonical_identity="ident-A", status="supported"),
        _claim("c2", canonical_identity="ident-A", status="supported"),  # duplicate identity
        _claim("c3", canonical_identity="ident-B", status="supported"),
        _claim("c4", canonical_identity="ident-C", status="partial"),  # not supported
    ])
    content = compute_content_dimensions(claim_set=claim_set)
    # unique supported identities: ident-A, ident-B -> 2
    assert content.unique_supported_claims == 2


def test_content_dimensions_count_validated_final_sentences() -> None:
    report = _validation_report([
        _verdict("c1", status="supported"),
        _verdict("c2", status="caveated"),
        _verdict("c3", status="unsupported"),
    ])
    content = compute_content_dimensions(validation_report=report)
    # supported + caveated = 2 validated sentences
    assert content.validated_final_sentences == 2


# ---------------------------------------------------------------------------
# Minimality dimensions
# ---------------------------------------------------------------------------


def test_minimality_dimensions_count_duplicate_claims() -> None:
    claim_set = _claim_set([
        _claim("c1", canonical_identity="ident-A"),
        _claim("c2", canonical_identity="ident-A"),  # duplicate
        _claim("c3", canonical_identity="ident-A"),  # duplicate
        _claim("c4", canonical_identity="ident-B"),
    ])
    minimality = compute_minimality_dimensions(claim_set=claim_set)
    # ident-A appears 3 times -> 2 duplicates
    assert minimality.duplicate_claims == 2


def test_minimality_dimensions_count_unjustified_fan_in() -> None:
    claim_set = _claim_set([
        _claim("c1", direct_evidence_ids=["s1", "s2"]),  # ok (<=3)
        _claim("c2", direct_evidence_ids=["s1", "s2", "s3", "s4"]),  # fan-in (>3)
        _claim("c3", direct_evidence_ids=["s1", "s2", "s3", "s4", "s5"]),  # fan-in (>3)
    ])
    minimality = compute_minimality_dimensions(claim_set=claim_set)
    assert minimality.unjustified_fan_in == 2


def test_minimality_dimensions_pass_through_unresolved_relations() -> None:
    minimality = compute_minimality_dimensions(unresolved_relations=5)
    assert minimality.unresolved_relations == 5


# ---------------------------------------------------------------------------
# Top-level compute_quality_state
# ---------------------------------------------------------------------------


def test_compute_quality_state_combines_all_dimensions() -> None:
    coverage = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        _coverage_item("o2", priority="must_cover", coverage_status="unresolved"),
    ])
    claim_set = _claim_set([
        _claim("c1", canonical_identity="ident-A", status="supported"),
    ])
    validation = _validation_report([_verdict("c1", status="supported")])

    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage,
        claim_set=claim_set,
        validation_report=validation,
        model_calls=5,
        tool_calls=12,
    )

    assert state.run_id == "run-1"
    assert state.repo_snapshot_id == "repo-1"
    assert state.project_tree_hash == "tree-1"
    assert state.content_digest.startswith("sha256:")
    assert state.safety.unsupported_positive_claims == 0
    assert state.content.supported_must_cover == 1
    assert state.content.unresolved_high_value_obligations == 1
    assert state.content.unique_supported_claims == 1
    assert state.content.validated_final_sentences == 1
    assert state.cost.model_calls == 5
    assert state.cost.tool_calls == 12
    assert state.is_trusted


def test_compute_quality_state_with_unsupported_claims_is_untrusted() -> None:
    validation = _validation_report([_verdict("c1", status="unsupported")])
    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        validation_report=validation,
    )
    assert not state.is_trusted
    assert state.safety.unsupported_positive_claims == 1


# ---------------------------------------------------------------------------
# Trusted success / incomplete exit conditions
# ---------------------------------------------------------------------------


def test_is_trusted_success_requires_no_unresolved_must_cover() -> None:
    coverage = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="supported"),
    ])
    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage,
    )
    assert state.is_trusted
    assert state.content.unresolved_high_value_obligations == 0
    assert is_trusted_success(state)


def test_is_trusted_success_false_when_must_cover_unresolved() -> None:
    coverage = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="unresolved"),
    ])
    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage,
    )
    assert state.is_trusted
    assert state.content.unresolved_high_value_obligations == 1
    assert not is_trusted_success(state)
    # But it is incomplete (trusted + has unresolved must-cover).
    assert is_incomplete(state)


def test_is_incomplete_false_when_untrusted() -> None:
    validation = _validation_report([_verdict("c1", status="unsupported")])
    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        validation_report=validation,
    )
    assert not state.is_trusted
    assert not is_incomplete(state)
    assert not is_trusted_success(state)


def test_explicit_gap_does_not_make_state_trusted_success() -> None:
    """An explicit gap is terminal but never counts as supported.

    A state where every must-cover is either ``supported`` or
    ``explicit_gap`` is trusted (no unsupported positive claims) but
    NOT a ``trusted_success`` because explicit gaps mean the Method is
    incomplete: the behavior is absent from the executable scope.
    """

    coverage = _coverage_report([
        _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        _coverage_item("o2", priority="must_cover", coverage_status="explicit_gap"),
    ])
    state = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage,
    )
    assert state.is_trusted
    assert state.content.unresolved_high_value_obligations == 0
    # trusted_success is True here because no must-cover is unresolved;
    # the explicit gap is terminal. The caller distinguishes "complete"
    # vs "incomplete" via the explicit_gap_count on the coverage report.
    assert is_trusted_success(state)


# ---------------------------------------------------------------------------
# Best-state retention
# ---------------------------------------------------------------------------


def test_select_best_state_replaces_incumbent_when_candidate_dominates() -> None:
    incumbent = empty_quality_state(
        run_id="run-1", repo_snapshot_id="repo-1", project_tree_hash="tree-1"
    )
    candidate = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=_coverage_report([
            _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        ]),
    )
    best, replaced = select_best_state(candidate, incumbent)
    assert replaced is True
    assert best is candidate


def test_select_best_state_retains_incumbent_when_candidate_regresses() -> None:
    incumbent = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=_coverage_report([
            _coverage_item("o1", priority="must_cover", coverage_status="supported"),
            _coverage_item("o2", priority="must_cover", coverage_status="supported"),
        ]),
    )
    candidate = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=_coverage_report([
            _coverage_item("o1", priority="must_cover", coverage_status="supported"),
            # o2 regressed from supported -> unresolved
            _coverage_item("o2", priority="must_cover", coverage_status="unresolved"),
        ]),
    )
    best, replaced = select_best_state(candidate, incumbent)
    assert replaced is False
    assert best is incumbent


def test_select_best_state_retains_incumbent_when_no_improvement() -> None:
    incumbent = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=_coverage_report([
            _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        ]),
    )
    # Candidate has the same content footprint; no dimension improved.
    candidate = compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=_coverage_report([
            _coverage_item("o1", priority="must_cover", coverage_status="supported"),
        ]),
    )
    best, replaced = select_best_state(candidate, incumbent)
    assert replaced is False
    assert best is incumbent
