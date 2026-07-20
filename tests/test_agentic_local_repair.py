"""R6.4 tests for the R6 local repair loop integration.

The R6.4 exit conditions are:

- a single sentence failure MUST NOT trigger a full rerun of the
  intake/analysis/authoring pipeline;
- writer sentence-split changes MUST NOT break the claim trace (the
  trace is keyed by ``atomic_claim_id``, not by sentence id);
- repair rollback MUST restore the best state when a repair turn
  regresses quality;
- the final unsupported rate MUST be zero for a ``trusted_success``
  exit;
- an incomplete Method MUST be safely emittable as incomplete, never
  pretending to be complete.

These tests exercise the integration of ``text_repair_supervisor.py``
(R6.2) with ``quality_state_v2.py`` (R6.3).  The text-repair
supervisor's per-failure mapping is already covered by
``test_agentic_text_repair_supervisor.py``; here we focus on the
behaviour the R6.4 exit conditions require.
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
    compute_quality_state,
    is_incomplete,
    is_trusted_success,
    select_best_state,
)
from code2paper.agentic.research_models import (
    TextRepairIssueV1,
    empty_quality_state,
    quality_state_dominates,
)
from code2paper.agentic.text_repair_supervisor import (
    derive_repair_issues,
    group_repair_issues_by_scope,
    most_permissive_scope,
)
from code2paper.agentic.trust_contracts import (
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _verdict(
    claim_id: str,
    *,
    failures: list[str],
    unsupported_fragment: str = "",
    direct_evidence_ids: list[str] | None = None,
    relation_evidence_ids: list[str] | None = None,
    matched_projection_claim_ids: list[str] | None = None,
) -> TextClaimEvidenceVerdict:
    return TextClaimEvidenceVerdict(
        atomic_claim_id=claim_id,
        status="unsupported" if failures else "supported",
        matched_projection_claim_ids=matched_projection_claim_ids or [],
        direct_evidence_ids=direct_evidence_ids or [],
        relation_evidence_ids=relation_evidence_ids or [],
        supported_fragment="" if failures else "supported text",
        unsupported_fragment=unsupported_fragment or ("unsupported text" if failures else ""),
        required_qualifiers=[] if not failures else ["qualifier A"],
        deterministic_failures=failures,
        model_verdict="",
        rationale="; ".join(failures) if failures else "passed",
        repair_action="test",
    )


def _report(verdicts: list[TextClaimEvidenceVerdict]) -> TextEvidenceValidationReport:
    return TextEvidenceValidationReport(
        status="failed" if any(v.status == "unsupported" for v in verdicts) else "passed",
        input_text_digest="sha256:test",
        projection_digest="sha256:proj",
        checked_factual_claims=len(verdicts),
        supported_claims=sum(1 for v in verdicts if v.status == "supported"),
        caveated_claims=0,
        unsupported_claims=sum(1 for v in verdicts if v.status == "unsupported"),
        unverified_claims=0,
        semantic_verifier_calls=0,
        verdicts=verdicts,
        recommended_actions=[],
    )


def _coverage_item(
    obligation_id: str,
    *,
    priority: str = "must_cover",
    coverage_status: str = "supported",
) -> ObligationAlignmentV1:
    return ObligationAlignmentV1(
        obligation_id=obligation_id,
        obligation_kind="stage",
        obligation_priority=priority,
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


def _claim(claim_id: str, *, canonical_identity: str = "ident") -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=f"claim text {claim_id}",
        claim_kind="implementation_behavior",
        fact_ids=["f1"],
        direct_evidence_ids=["span-1"],
        allowed_wording_boundary="boundary",
        canonical_identity=canonical_identity,
    )


def _state(
    *,
    validation_report: TextEvidenceValidationReport | None = None,
    coverage_report: ObligationCoverageReportV2 | None = None,
    claim_set: AtomicClaimSetV3 | None = None,
):
    return compute_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        coverage_report=coverage_report,
        claim_set=claim_set,
        validation_report=validation_report,
    )


# ---------------------------------------------------------------------------
# R6.4: a single sentence failure does not trigger a full rerun
# ---------------------------------------------------------------------------


def test_single_sentence_failure_only_produces_local_repair_issues() -> None:
    """A report with five supported verdicts and one failed verdict produces
    repair issues ONLY for the failed verdict.  The repair supervisor never
    asks for a full rerun: the most permissive scope is bounded by the
    single failure's allowed_repair_scope.
    """

    verdicts = [
        _verdict(f"C-{i}", failures=[]) for i in range(5)
    ] + [
        _verdict("C-bad", failures=["required_qualifier_missing"]),
    ]
    report = _report(verdicts)

    issues = derive_repair_issues(report)

    # Exactly one issue (for the single failed verdict).
    assert len(issues) == 1
    assert issues[0].atomic_claim_id == "C-bad"
    assert issues[0].allowed_repair_scope == "wording_only"
    # Most permissive scope is bounded by the single failure.
    assert most_permissive_scope(issues) == "wording_only"
    # Grouping produces only the wording_only bucket.
    grouped = group_repair_issues_by_scope(issues)
    assert set(grouped.keys()) == {"wording_only"}
    # No "full rerun" scope exists in the vocabulary; the most permissive
    # scope is drop_or_gap, which is still a local repair.
    assert most_permissive_scope(issues) in {
        "wording_only", "sentence_atomicity", "claim_decomposition",
        "packet_relation", "code_search", "drop_or_gap",
    }


def test_repair_issues_for_distinct_sentences_do_not_leak() -> None:
    """Issues for one sentence never affect the scope of another sentence."""

    verdicts = [
        _verdict("C-A", failures=["required_qualifier_missing"]),  # wording_only
        _verdict("C-B", failures=["direct_evidence_missing"]),     # drop_or_gap
    ]
    report = _report(verdicts)

    issues = derive_repair_issues(report, sentence_id_by_claim={
        "C-A": "S1", "C-B": "S2",
    })

    by_sentence: dict[str, list[TextRepairIssueV1]] = {}
    for issue in issues:
        by_sentence.setdefault(issue.sentence_id, []).append(issue)

    assert set(by_sentence.keys()) == {"S1", "S2"}
    # Each sentence's scope is bounded by its own failure.
    assert by_sentence["S1"][0].allowed_repair_scope == "wording_only"
    assert by_sentence["S2"][0].allowed_repair_scope == "drop_or_gap"
    # The aggregate most-permissive scope is drop_or_gap (the maximum),
    # but each sentence is still repaired locally.
    assert most_permissive_scope(issues) == "drop_or_gap"


def test_local_repair_never_requests_pipeline_rerun() -> None:
    """No combination of validator failures produces a scope outside the
    local-repair vocabulary.  In particular, no failure maps to a
    "return_to_intake" or "full_rerun" action: the supervisor must
    always act locally or escalate to drop_or_gap.
    """

    verdicts = [
        _verdict("C-1", failures=["no_semantically_matching_projected_claim"]),
        _verdict("C-2", failures=["direct_evidence_semantically_unrelated"]),
        _verdict("C-3", failures=["direct_evidence_missing"]),
        _verdict("C-4", failures=["required_qualifier_missing"]),
        _verdict("C-5", failures=["allowed_wording_boundary_exceeded"]),
        _verdict("C-6", failures=["numeric_token_not_in_direct_evidence"]),
        _verdict("C-7", failures=["formula_not_in_direct_evidence"]),
        _verdict("C-8", failures=["author_context_cannot_be_direct_code_evidence"]),
        _verdict("C-9", failures=["semantic_verifier_unavailable"]),
        _verdict("C-10", failures=["semantic_verifier_budget_exhausted"]),
        _verdict("C-11", failures=["semantic_verifier_rejected_claim"]),
        _verdict("C-12", failures=["unknown_future_failure_string"]),
    ]
    report = _report(verdicts)

    issues = derive_repair_issues(report)

    # Every issue's scope is within the local-repair vocabulary.
    valid_scopes = {
        "wording_only", "sentence_atomicity", "claim_decomposition",
        "packet_relation", "code_search", "drop_or_gap",
    }
    for issue in issues:
        assert issue.allowed_repair_scope in valid_scopes
    # The most permissive scope never exceeds drop_or_gap.
    assert most_permissive_scope(issues) == "drop_or_gap"


# ---------------------------------------------------------------------------
# R6.4: writer sentence-split changes do not break the claim trace
# ---------------------------------------------------------------------------


def test_sentence_split_preserves_claim_trace() -> None:
    """When the writer splits one sentence into two atomic claims, each
    claim keeps its own verdict.  The repair supervisor addresses each
    verdict independently using ``atomic_claim_id`` as the trace key, so
    re-splitting a sentence never breaks the trace.
    """

    # Before split: one claim C-1 in sentence S1, supported.
    before_split_verdicts = [
        _verdict("C-1", failures=[]),
    ]
    before_report = _report(before_split_verdicts)

    # After split: the writer split S1 into S1a (C-1, still supported)
    # and S1b (new C-2, has a qualifier failure).
    after_split_verdicts = [
        _verdict("C-1", failures=[]),
        _verdict("C-2", failures=["required_qualifier_missing"]),
    ]
    after_report = _report(after_split_verdicts)

    # Issues are derived per-claim, so only C-2 produces an issue.
    after_issues = derive_repair_issues(
        after_report,
        sentence_id_by_claim={"C-1": "S1a", "C-2": "S1b"},
    )
    assert len(after_issues) == 1
    assert after_issues[0].atomic_claim_id == "C-2"
    assert after_issues[0].sentence_id == "S1b"
    # The trace for C-1 is untouched: it stays supported.
    assert all(v.atomic_claim_id == "C-2" for v in after_report.verdicts if v.deterministic_failures)


def test_claim_trace_survives_sentence_id_remap() -> None:
    """Re-mapping a sentence id (e.g., after a writer revision) does not
    lose the repair issue: the issue is keyed by ``atomic_claim_id``
    and the sentence_id is just a diagnostic.
    """

    verdicts = [
        _verdict("C-X", failures=["direct_evidence_missing"]),
    ]
    report = _report(verdicts)

    # First derivation: no sentence mapping (uses claim id as sentence id).
    issues_default = derive_repair_issues(report)
    assert issues_default[0].sentence_id == "C-X"
    assert issues_default[0].atomic_claim_id == "C-X"

    # Second derivation: explicit sentence mapping.
    issues_mapped = derive_repair_issues(
        report, sentence_id_by_claim={"C-X": "S-final"}
    )
    assert issues_mapped[0].sentence_id == "S-final"
    # The atomic_claim_id is stable across the remap.
    assert issues_mapped[0].atomic_claim_id == "C-X"
    # The scope is the same.
    assert issues_default[0].allowed_repair_scope == issues_mapped[0].allowed_repair_scope


# ---------------------------------------------------------------------------
# R6.4: repair rollback restores best state
# ---------------------------------------------------------------------------


def test_repair_turn_regression_retains_best_state() -> None:
    """A repair turn that introduces an unsupported claim regresses quality.
    ``select_best_state`` MUST retain the incumbent best state and NOT
    replace it with the regressed candidate.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])

    # Incumbent: clean state, one supported claim, no unsupported.
    incumbent_report = _report([_verdict("C-1", failures=[])])
    incumbent = _state(
        validation_report=incumbent_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    # Candidate: repair turn regressed -- C-1 is now unsupported.
    candidate_report = _report([
        _verdict("C-1", failures=["direct_evidence_missing"]),
    ])
    candidate = _state(
        validation_report=candidate_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    best, replaced = select_best_state(candidate, incumbent)

    assert not replaced
    assert best is incumbent
    # The candidate is untrusted because of the unsupported claim.
    assert not candidate.is_trusted
    assert candidate.safety.unsupported_positive_claims == 1
    # The incumbent remains trusted.
    assert incumbent.is_trusted
    assert incumbent.safety.unsupported_positive_claims == 0


def test_repair_turn_improvement_replaces_best_state() -> None:
    """A repair turn that resolves an unsupported claim improves quality
    (fewer unsupported_positive_claims).  ``select_best_state`` MUST
    replace the incumbent with the candidate.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])

    # Incumbent: one unsupported claim (regressed state from a prior
    # repair attempt).  safety.unsupported_positive_claims = 1.
    incumbent_report = _report([
        _verdict("C-1", failures=["direct_evidence_missing"]),
    ])
    incumbent = _state(
        validation_report=incumbent_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert incumbent.safety.unsupported_positive_claims == 1
    assert not incumbent.is_trusted

    # Candidate: repair resolved the failure -> fully supported.
    # safety.unsupported_positive_claims drops from 1 to 0, which is a
    # safety improvement and dominates the incumbent.
    candidate_report = _report([_verdict("C-1", failures=[])])
    candidate = _state(
        validation_report=candidate_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert candidate.safety.unsupported_positive_claims == 0
    assert candidate.is_trusted

    best, replaced = select_best_state(candidate, incumbent)

    assert replaced
    assert best is candidate
    # The candidate improved: fewer unsupported positive claims.
    assert (
        candidate.safety.unsupported_positive_claims
        < incumbent.safety.unsupported_positive_claims
    )


def test_repair_turn_no_op_retains_incumbent() -> None:
    """A repair turn that does not improve or regress quality is a no-op:
    the incumbent is retained and ``replaced`` is ``False``.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])

    incumbent_report = _report([_verdict("C-1", failures=[])])
    incumbent = _state(
        validation_report=incumbent_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    # Candidate: identical state.
    candidate_report = _report([_verdict("C-1", failures=[])])
    candidate = _state(
        validation_report=candidate_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    best, replaced = select_best_state(candidate, incumbent)

    # No improvement -> not replaced.
    assert not replaced
    assert best is incumbent


# ---------------------------------------------------------------------------
# R6.4: final unsupported rate must be 0 for trusted success
# ---------------------------------------------------------------------------


def test_trusted_success_requires_zero_unsupported() -> None:
    """``is_trusted_success`` is True only when there are no unsupported
    positive claims AND no unresolved must-cover obligations.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])

    # Clean state: 0 unsupported.
    clean_report = _report([_verdict("C-1", failures=[])])
    clean_state = _state(
        validation_report=clean_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert is_trusted_success(clean_state)

    # State with 1 unsupported claim: NOT trusted success.
    bad_report = _report([
        _verdict("C-1", failures=["direct_evidence_missing"]),
    ])
    bad_state = _state(
        validation_report=bad_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert not is_trusted_success(bad_state)
    assert bad_state.safety.unsupported_positive_claims == 1


def test_trusted_success_requires_no_unresolved_must_cover() -> None:
    """Even with zero unsupported claims, an unresolved must_cover
    obligation prevents ``is_trusted_success``.
    """

    coverage_unresolved = _coverage_report([
        _coverage_item("O-1", coverage_status="unresolved"),
    ])
    coverage_supported = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])
    clean_report = _report([_verdict("C-1", failures=[])])

    unresolved_state = _state(
        validation_report=clean_report,
        coverage_report=coverage_unresolved,
        claim_set=claim_set,
    )
    supported_state = _state(
        validation_report=clean_report,
        coverage_report=coverage_supported,
        claim_set=claim_set,
    )

    assert not is_trusted_success(unresolved_state)
    assert is_trusted_success(supported_state)
    assert unresolved_state.content.unresolved_high_value_obligations == 1


# ---------------------------------------------------------------------------
# R6.4: incomplete Method can be safely emitted as incomplete
# ---------------------------------------------------------------------------


def test_incomplete_state_is_trusted_but_has_unresolved_must_cover() -> None:
    """``is_incomplete`` is True when the state is trusted (no unsupported
    positive claims) but has unresolved must-cover obligations.  This is
    the safe exit: emit the Method as incomplete, never pretending it is
    complete.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="unresolved"),
    ])
    claim_set = _claim_set([_claim("C-1")])
    clean_report = _report([_verdict("C-1", failures=[])])

    state = _state(
        validation_report=clean_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert state.is_trusted  # No unsupported claims.
    assert state.content.unresolved_high_value_obligations == 1
    assert is_incomplete(state)
    assert not is_trusted_success(state)


def test_untrusted_state_is_neither_trusted_success_nor_incomplete() -> None:
    """A state with unsupported claims is neither trusted success nor
    incomplete: it MUST NOT be emitted as a complete Method and MUST NOT
    be emitted as an incomplete Method either.  The supervisor must
    continue repairing.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])
    bad_report = _report([
        _verdict("C-1", failures=["direct_evidence_missing"]),
    ])

    state = _state(
        validation_report=bad_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert not state.is_trusted
    assert not is_trusted_success(state)
    assert not is_incomplete(state)


def test_explicit_gap_must_cover_is_terminal_but_not_supported() -> None:
    """An explicit_gap must_cover obligation is terminal (counts toward
    ``terminal_must_cover``) but never counts toward
    ``supported_must_cover``.  This is the R6.3 rule that prevents an
    explicit gap from masquerading as a supported claim.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="explicit_gap"),
    ])
    claim_set = _claim_set([])
    clean_report = _report([])

    state = _state(
        validation_report=clean_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert state.is_trusted  # No unsupported claims.
    assert state.content.terminal_must_cover == 1
    assert state.content.supported_must_cover == 0
    # No unresolved must_cover (explicit_gap is terminal), so this is
    # actually a trusted success -- but with zero supported claims.
    assert is_trusted_success(state)


# ---------------------------------------------------------------------------
# Repair scope ordering
# ---------------------------------------------------------------------------


def test_repair_scope_ordering_wording_only_is_least_permissive() -> None:
    """When a sentence has both a wording_only and a drop_or_gap issue,
    the most permissive scope is drop_or_gap.  This matches the R6.2
    ordering: wording_only < ... < drop_or_gap.
    """

    verdicts = [
        _verdict("C-word", failures=["required_qualifier_missing"]),
        _verdict("C-drop", failures=["direct_evidence_missing"]),
    ]
    report = _report(verdicts)

    issues = derive_repair_issues(report, sentence_id_by_claim={
        "C-word": "S1", "C-drop": "S1",  # Same sentence.
    })
    # Both issues are for the same sentence.
    assert all(issue.sentence_id == "S1" for issue in issues)
    # Most permissive scope is drop_or_gap.
    assert most_permissive_scope(issues) == "drop_or_gap"


def test_repair_scope_ordering_unknown_failure_is_drop_or_gap() -> None:
    """Unknown failure strings fall back to drop_or_gap (safest local repair)."""

    verdicts = [
        _verdict("C-unknown", failures=["some_new_future_failure"]),
    ]
    report = _report(verdicts)

    issues = derive_repair_issues(report)
    assert len(issues) == 1
    assert issues[0].allowed_repair_scope == "drop_or_gap"
    assert issues[0].failure_type == "unsupported_rationale"


# ---------------------------------------------------------------------------
# End-to-end local repair scenario
# ---------------------------------------------------------------------------


def test_end_to_end_local_repair_scenario() -> None:
    """End-to-end scenario:

    1. Initial validation has one unsupported claim (C-bad).
    2. ``derive_repair_issues`` produces one issue with the right scope.
    3. The repair turn resolves C-bad (now supported).
    4. ``select_best_state`` replaces the incumbent with the repaired state.
    5. The final state is a trusted success.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1"), _claim("C-2")])

    # 1. Initial validation: C-1 supported, C-2 unsupported.
    initial_report = _report([
        _verdict("C-1", failures=[]),
        _verdict("C-2", failures=["required_qualifier_missing"]),
    ])
    initial_state = _state(
        validation_report=initial_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert not is_trusted_success(initial_state)
    assert initial_state.safety.unsupported_positive_claims == 1

    # 2. Derive repair issues.
    issues = derive_repair_issues(initial_report)
    assert len(issues) == 1
    assert issues[0].atomic_claim_id == "C-2"
    assert issues[0].allowed_repair_scope == "wording_only"

    # 3. Repair turn: C-2 is now supported (qualifier added).
    repaired_report = _report([
        _verdict("C-1", failures=[]),
        _verdict("C-2", failures=[]),
    ])
    repaired_state = _state(
        validation_report=repaired_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    # 4. select_best_state replaces incumbent with repaired candidate.
    best, replaced = select_best_state(repaired_state, initial_state)
    assert replaced
    assert best is repaired_state

    # 5. The final state is a trusted success.
    assert is_trusted_success(best)
    assert best.safety.unsupported_positive_claims == 0
    assert best.content.validated_final_sentences == 2


def test_end_to_end_repair_rollback_scenario() -> None:
    """End-to-end rollback scenario:

    1. Initial validation: all supported.
    2. A repair turn introduces a new unsupported claim (regression).
    3. ``select_best_state`` retains the incumbent.
    4. The supervisor can retry from the incumbent.
    """

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1"), _claim("C-2")])

    # 1. Initial: both supported.
    initial_report = _report([
        _verdict("C-1", failures=[]),
        _verdict("C-2", failures=[]),
    ])
    initial_state = _state(
        validation_report=initial_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert is_trusted_success(initial_state)

    # 2. Repair turn regresses: C-2 becomes unsupported.
    regressed_report = _report([
        _verdict("C-1", failures=[]),
        _verdict("C-2", failures=["direct_evidence_missing"]),
    ])
    regressed_state = _state(
        validation_report=regressed_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    assert not is_trusted_success(regressed_state)

    # 3. select_best_state retains the incumbent (rollback).
    best, replaced = select_best_state(regressed_state, initial_state)
    assert not replaced
    assert best is initial_state
    assert is_trusted_success(best)

    # 4. The supervisor can re-derive issues from the regressed report
    #    without losing the incumbent best state.
    issues = derive_repair_issues(regressed_report)
    assert len(issues) == 1
    assert issues[0].atomic_claim_id == "C-2"
    assert issues[0].allowed_repair_scope == "drop_or_gap"


# ---------------------------------------------------------------------------
# Empty state seeding
# ---------------------------------------------------------------------------


def test_empty_quality_state_is_the_initial_incumbent() -> None:
    """The run seeds best-state retention with an empty quality state.
    Any non-empty candidate dominates it.
    """

    empty = empty_quality_state(
        run_id="run-1", repo_snapshot_id="repo-1", project_tree_hash="tree-1",
    )

    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])
    clean_report = _report([_verdict("C-1", failures=[])])
    candidate = _state(
        validation_report=clean_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    best, replaced = select_best_state(candidate, empty)
    assert replaced
    assert best is candidate
    assert is_trusted_success(best)


def test_empty_state_is_trusted_but_empty() -> None:
    """An empty quality state has no unsupported claims and no unresolved
    must_cover, so it technically satisfies ``is_trusted_success`` -- but
    with zero content.  The supervisor MUST seed with the empty state
    and immediately replace it once any real candidate arrives.
    """

    empty = empty_quality_state(
        run_id="run-1", repo_snapshot_id="repo-1", project_tree_hash="tree-1",
    )
    assert empty.is_empty
    assert empty.is_trusted
    # The empty state has no content, so a real candidate dominates it.
    coverage = _coverage_report([
        _coverage_item("O-1", coverage_status="supported"),
    ])
    claim_set = _claim_set([_claim("C-1")])
    clean_report = _report([_verdict("C-1", failures=[])])
    candidate = _state(
        validation_report=clean_report,
        coverage_report=coverage,
        claim_set=claim_set,
    )
    best, replaced = select_best_state(candidate, empty)
    assert replaced
    assert best is candidate
