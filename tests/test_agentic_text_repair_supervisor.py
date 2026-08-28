"""R6.4 tests for the R6.2 text repair supervisor.

Verifies that ``text_repair_supervisor.py`` correctly maps final-validator
failures to typed ``TextRepairIssueV1`` instances with the right
``allowed_repair_scope``, and that the mapping is project-agnostic.
"""

from __future__ import annotations

from code2paper.agentic.research_models import (
    TEXT_REPAIR_FAILURE_TYPES,
    TEXT_REPAIR_SCOPES,
    TextRepairIssueV1,
)
from code2paper.agentic.text_repair_supervisor import (
    count_repair_issues_by_failure_type,
    derive_repair_issues,
    failure_to_repair_scope,
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


# ---------------------------------------------------------------------------
# failure_to_repair_scope unit tests
# ---------------------------------------------------------------------------


def test_no_semantically_matching_projected_claim_maps_to_claim_decomposition() -> None:
    failure_type, scope, _ = failure_to_repair_scope("no_semantically_matching_projected_claim")
    assert failure_type == "no_semantically_matching_projected_claim"
    assert scope == "claim_decomposition"


def test_direct_evidence_semantically_unrelated_maps_to_wrong_span_role() -> None:
    failure_type, scope, _ = failure_to_repair_scope("direct_evidence_semantically_unrelated")
    assert failure_type == "wrong_span_role"
    assert scope == "packet_relation"


def test_required_qualifier_missing_maps_to_missing_qualifier_wording_only() -> None:
    failure_type, scope, _ = failure_to_repair_scope("required_qualifier_missing")
    assert failure_type == "missing_qualifier"
    assert scope == "wording_only"


def test_formula_not_in_direct_evidence_maps_to_formula_unsupported_drop_or_gap() -> None:
    failure_type, scope, _ = failure_to_repair_scope("formula_not_in_direct_evidence")
    assert failure_type == "formula_unsupported"
    assert scope == "drop_or_gap"


def test_semantic_verifier_failures_map_to_semantic_verifier_exhausted_wording_only() -> None:
    for failure in ("semantic_verifier_unavailable", "semantic_verifier_budget_exhausted"):
        failure_type, scope, _ = failure_to_repair_scope(failure)
        assert failure_type == "semantic_verifier_exhausted"
        assert scope == "wording_only"


def test_unknown_failure_string_falls_back_to_drop_or_gap() -> None:
    failure_type, scope, _ = failure_to_repair_scope("totally_unknown_failure_code")
    assert failure_type == "unsupported_rationale"
    assert scope == "drop_or_gap"


def test_every_repair_scope_and_failure_type_is_in_canonical_vocabulary() -> None:
    from code2paper.agentic.text_repair_supervisor import _FAILURE_TO_REPAIR

    for failure_type, scope, _ in _FAILURE_TO_REPAIR.values():
        assert failure_type in TEXT_REPAIR_FAILURE_TYPES
        assert scope in TEXT_REPAIR_SCOPES


# ---------------------------------------------------------------------------
# derive_repair_issues tests
# ---------------------------------------------------------------------------


def test_derive_repair_issues_skips_clean_verdicts() -> None:
    report = _report([
        _verdict("c1", failures=[]),  # clean
        _verdict("c2", failures=["required_qualifier_missing"]),
    ])
    issues = derive_repair_issues(report)
    assert len(issues) == 1
    assert issues[0].atomic_claim_id == "c2"
    assert issues[0].failure_type == "missing_qualifier"
    assert issues[0].allowed_repair_scope == "wording_only"


def test_derive_repair_issues_emits_one_issue_per_failure() -> None:
    report = _report([
        _verdict("c1", failures=[
            "required_qualifier_missing",
            "allowed_wording_boundary_exceeded",
        ]),
    ])
    issues = derive_repair_issues(report)
    assert len(issues) == 2
    assert all(issue.atomic_claim_id == "c1" for issue in issues)
    assert all(issue.sentence_id == "c1" for issue in issues)
    assert {issue.failure_type for issue in issues} == {"missing_qualifier"}
    assert {issue.allowed_repair_scope for issue in issues} == {"wording_only"}


def test_derive_repair_issues_uses_sentence_id_by_claim_when_provided() -> None:
    report = _report([
        _verdict("claim-001", failures=["required_qualifier_missing"]),
    ])
    issues = derive_repair_issues(
        report,
        sentence_id_by_claim={"claim-001": "sentence-42"},
    )
    assert len(issues) == 1
    assert issues[0].sentence_id == "sentence-42"
    assert issues[0].atomic_claim_id == "claim-001"


def test_derive_repair_issues_records_offending_fragment() -> None:
    report = _report([
        _verdict("c1", failures=["no_semantically_matching_projected_claim"],
                 unsupported_fragment="the offending text"),
    ])
    issues = derive_repair_issues(report)
    assert issues[0].offending_fragment == "the offending text"


def test_derive_repair_issues_records_missing_relation_hint() -> None:
    report = _report([
        _verdict("c1", failures=["direct_evidence_missing"],
                 direct_evidence_ids=[], relation_evidence_ids=[]),
    ])
    issues = derive_repair_issues(report)
    assert "direct_evidence: none" in issues[0].missing_fact_or_relation
    assert "relation_evidence: none" in issues[0].missing_fact_or_relation


def test_derive_repair_issues_formula_hint_requires_verbatim_qualifier() -> None:
    """``formula_not_in_direct_evidence`` must carry the exact qualifier
    comparison tokens.

    The validator extracts comparison formulas greedily up to punctuation, so
    ``under i == 0 and case_study configuration`` becomes the formula token
    ``i == 0 and case_study configuration`` and no longer matches the frozen
    qualifier.  The repair hint must tell the Rewrite to reproduce the
    comparison verbatim and keep the general-path formula outside the branch
    scope."""
    report = _report([
        _verdict(
            "c1",
            failures=["formula_not_in_direct_evidence"],
            matched_projection_claim_ids=["proj-1"],
        ),
    ])
    issues = derive_repair_issues(report)
    hint = issues[0].missing_fact_or_relation
    assert "formula_comparison_must_be_verbatim" in hint
    assert "i == 0 and case_study" in hint
    assert "required_qualifiers" in hint
    assert "qualifier A" in hint


def test_derive_repair_issues_empty_report_produces_no_issues() -> None:
    report = _report([])
    issues = derive_repair_issues(report)
    assert issues == []


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def test_group_repair_issues_by_scope() -> None:
    report = _report([
        _verdict("c1", failures=["required_qualifier_missing"]),  # wording_only
        _verdict("c2", failures=["no_semantically_matching_projected_claim"]),  # claim_decomposition
        _verdict("c3", failures=["formula_not_in_direct_evidence"]),  # drop_or_gap
        _verdict("c4", failures=["allowed_wording_boundary_exceeded"]),  # wording_only
    ])
    issues = derive_repair_issues(report)
    grouped = group_repair_issues_by_scope(issues)
    assert set(grouped.keys()) == {"wording_only", "claim_decomposition", "drop_or_gap"}
    assert len(grouped["wording_only"]) == 2
    assert len(grouped["claim_decomposition"]) == 1
    assert len(grouped["drop_or_gap"]) == 1


def test_count_repair_issues_by_failure_type() -> None:
    report = _report([
        _verdict("c1", failures=["required_qualifier_missing",
                                  "allowed_wording_boundary_exceeded"]),  # 2x missing_qualifier
        _verdict("c2", failures=["formula_not_in_direct_evidence"]),  # 1x formula_unsupported
    ])
    issues = derive_repair_issues(report)
    counts = count_repair_issues_by_failure_type(issues)
    assert counts["missing_qualifier"] == 2
    assert counts["formula_unsupported"] == 1
    # Failure types with zero issues are still in the dict.
    assert counts["no_semantically_matching_projected_claim"] == 0


def test_most_permissive_scope_orders_from_least_to_most_permissive() -> None:
    # wording_only < sentence_atomicity < claim_decomposition < packet_relation
    # < code_search < drop_or_gap
    report = _report([
        _verdict("c1", failures=["required_qualifier_missing"]),  # wording_only
        _verdict("c2", failures=["no_semantically_matching_projected_claim"]),  # claim_decomposition
        _verdict("c3", failures=["formula_not_in_direct_evidence"]),  # drop_or_gap
    ])
    issues = derive_repair_issues(report)
    assert most_permissive_scope(issues) == "drop_or_gap"


def test_most_permissive_scope_returns_none_for_empty_list() -> None:
    assert most_permissive_scope([]) is None


# ---------------------------------------------------------------------------
# R6.2 contract: a single sentence failure never triggers a full rerun
# ---------------------------------------------------------------------------


def test_single_sentence_failure_stays_within_local_repair_scope() -> None:
    """A single sentence failure MUST NOT authorize a code_search rerun.

    The ``allowed_repair_scope`` for every issue derived from a single
    sentence failure is bounded: ``wording_only``, ``claim_decomposition``,
    ``packet_relation`` or ``drop_or_gap``.  None of these scopes
    authorize a full intake/analysis/authoring rerun.
    """

    report = _report([
        _verdict("c1", failures=["no_semantically_matching_projected_claim"]),
    ])
    issues = derive_repair_issues(report)
    assert len(issues) == 1
    scope = issues[0].allowed_repair_scope
    assert scope in {"wording_only", "sentence_atomicity", "claim_decomposition",
                     "packet_relation", "drop_or_gap"}, (
        f"single-sentence repair scope must be local; got {scope}"
    )
    # The supervisor never has authority to rerun the full pipeline from
    # a single sentence failure: the most permissive scope here should
    # not be code_search.
    assert most_permissive_scope(issues) != "code_search"


def test_repair_issue_contract_is_frozen_and_forbids_extra_fields() -> None:
    issue = TextRepairIssueV1(
        sentence_id="s1",
        atomic_claim_id="c1",
        failure_type="missing_qualifier",
        allowed_repair_scope="wording_only",
    )
    # frozen: cannot reassign
    import pydantic
    try:
        issue.sentence_id = "s2"  # type: ignore[misc]
        raise AssertionError("TextRepairIssueV1 should be frozen")
    except (pydantic.ValidationError, AttributeError, TypeError):
        pass
    # extra fields forbidden
    try:
        TextRepairIssueV1(  # type: ignore[call-arg]
            sentence_id="s1",
            failure_type="missing_qualifier",
            allowed_repair_scope="wording_only",
            surprise_field="no",  # type: ignore[call-arg]
        )
        raise AssertionError("TextRepairIssueV1 should forbid extra fields")
    except (pydantic.ValidationError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Plan 14.4: exact qualifier payload must reach the Rewrite owner
# ---------------------------------------------------------------------------


def test_required_qualifier_missing_carries_exact_qualifier_tokens() -> None:
    """The Rewrite owner needs the exact qualifier, not a generic hint."""
    verdict = TextClaimEvidenceVerdict(
        atomic_claim_id="FAC-Q1",
        status="unsupported",
        unsupported_fragment="The encoder reads the input.",
        required_qualifiers=["case_study", "mode == 'train'"],
        deterministic_failures=["required_qualifier_missing"],
        model_verdict="",
        rationale="required qualifier missing",
        repair_action="preserve_required_qualifiers",
    )
    issues = derive_repair_issues(_report([verdict]))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.failure_type == "missing_qualifier"
    assert issue.allowed_repair_scope == "wording_only"
    assert "case_study" in issue.missing_fact_or_relation
    assert "mode == 'train'" in issue.missing_fact_or_relation
    assert issue.offending_fragment == "The encoder reads the input."


def test_non_qualifier_failures_keep_evidence_hint() -> None:
    verdict = TextClaimEvidenceVerdict(
        atomic_claim_id="FAC-E1",
        status="unsupported",
        unsupported_fragment="The encoder reads the input.",
        required_qualifiers=[],
        deterministic_failures=["direct_evidence_missing"],
        model_verdict="",
        rationale="no evidence",
        repair_action="drop_or_gap",
    )
    issues = derive_repair_issues(_report([verdict]))
    assert len(issues) == 1
    assert issues[0].failure_type == "unsupported_rationale"
    assert "direct_evidence: none" in issues[0].missing_fact_or_relation
