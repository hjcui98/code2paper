"""R8.1 tests for the R8 acceptance criteria checker.

Verifies that ``r8_acceptance.py`` correctly checks all eight R8.2
per-project acceptance criteria and the R8.1 execution protocol
settings.  Tests use synthetic fixtures (no GPU, no real Gemma) so
they run in the deterministic test environment.

R8.2 acceptance criteria verified:

1. ``gap_driven_tool_selection`` -- a decision with a gap indicator
   AND a tool-calling action passes; ``RECORD_GAP`` alone fails;
   no decisions fails.
2. ``code_mainline_in_method`` -- a supported claim covering a
   ``must_cover`` obligation plus a non-zero validation count passes;
   missing any of these fails.
3. ``no_project_specific_claim_literals`` -- claim text and Method
   text without project literals passes; with any forbidden literal
   fails.
4. ``unsupported_final_sentences_zero`` -- ``unsupported_claims=0``
   passes; any non-zero value fails.
5. ``must_cover_terminal`` -- all must_cover obligations terminal
   passes; any ``unresolved`` fails.
6. ``no_evidence_free_equations`` -- Method text with only authorized
   equation tokens passes; unauthorized tokens fail.
7. ``trace_reproducible`` -- recorded digest matches recomputed
   digest passes; mismatch fails; no recorded digest skips.
8. ``checkpoint_resume_consistent`` -- matching final state digests
   pass; mismatch fails; no digests skip.

R8.1 protocol checks verified:

- role-specific sampling traces (global temperature is only a compatibility sentinel);
- ``CODE2PAPER_LLM_CACHE=0``;
- TP=2 on 2 GPUs;
- serial execution (no parallel projects);
- paper/README/TeX/PDF not promoted to ``executable_hard``.

R8.1 hard constraint: this test module's source MUST NOT contain
project-specific literals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.contracts import AgentDecision
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.r8_acceptance import (
    R8AcceptanceCriterion,
    R8AcceptanceReport,
    R8ProtocolSettings,
    check_r8_acceptance,
    check_r8_acceptance_from_run_dir,
    compute_trace_digest,
    extract_equation_tokens,
    has_gap_driven_tool_selection,
    load_r8_acceptance_report,
    scan_claims_for_project_literals,
    scan_text_for_project_literals,
    unauthorized_equation_tokens,
    verify_checkpoint_resume_consistency,
    verify_trace_reproducibility,
    write_r8_acceptance_report,
)
from code2paper.agentic.trust_contracts import (
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)
from code2paper.llm.generation_trace import (
    EffectiveSamplingConfig,
    GenerationCallTrace,
)
from code2paper.llm.role_config import (
    AUTHORING_PLANNER,
    CODE_ANALYZER,
    CODE_INTAKE,
    DETERMINISTIC_COMPILER,
    LLM_CALLING_ROLES,
    LOCAL_REWRITE,
    METHOD_WRITER,
    RESEARCH_SUPERVISOR,
    ROLE_GENERATION_CONFIGS,
    SEMANTIC_VERIFIER,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _claim(
    claim_id: str,
    *,
    canonical_text: str = "claim text",
    covers_obligation_ids: list[str] | None = None,
    allowed_wording_boundary: str = "boundary",
    status: str = "supported",
    canonical_identity: str | None = None,
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=canonical_text,
        claim_kind="implementation_behavior",
        fact_ids=["f1"],
        covers_obligation_ids=list(covers_obligation_ids or []),
        direct_evidence_ids=["span-1"],
        relation_evidence_ids=[],
        required_qualifiers=[],
        unsupported_author_fragments=[],
        allowed_wording_boundary=allowed_wording_boundary,
        canonical_identity=canonical_identity or f"ident-{claim_id}",
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
    matched_claim_ids: tuple[str, ...] = (),
    matched_gap_ids: tuple[str, ...] = (),
) -> ObligationAlignmentV1:
    return ObligationAlignmentV1(
        obligation_id=obligation_id,
        obligation_kind="method_mainline",
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


def _validation_report(
    *,
    unsupported: int = 0,
    supported: int = 1,
    caveated: int = 0,
) -> TextEvidenceValidationReport:
    verdicts: list[TextClaimEvidenceVerdict] = []
    for i in range(supported):
        verdicts.append(
            TextClaimEvidenceVerdict(
                atomic_claim_id=f"claim-s{i}",
                status="supported",
                direct_evidence_ids=["span-1"],
            )
        )
    for i in range(caveated):
        verdicts.append(
            TextClaimEvidenceVerdict(
                atomic_claim_id=f"claim-c{i}",
                status="caveated",
                direct_evidence_ids=["span-1"],
                required_qualifiers=["qualifier"],
            )
        )
    for i in range(unsupported):
        verdicts.append(
            TextClaimEvidenceVerdict(
                atomic_claim_id=f"claim-u{i}",
                status="unsupported",
            )
        )
    return TextEvidenceValidationReport(
        mode="agentic-text-evidence-validation-v1",
        status="passed" if unsupported == 0 else "failed",
        input_text_digest="sha256:text",
        projection_digest="sha256:proj",
        checked_factual_claims=len(verdicts),
        supported_claims=supported,
        caveated_claims=caveated,
        unsupported_claims=unsupported,
        verdicts=verdicts,
    )


def _agent_decision(
    *,
    node: str = "research_supervisor",
    decision: str = "SEARCH_SYMBOLS",
    rationale: str = "issue_driven:missing_anchor",
    evidence_ids: list[str] | None = None,
) -> AgentDecision:
    return AgentDecision(
        node=node,
        decision=decision,
        rationale=rationale,
        evidence_ids=list(evidence_ids or []),
    )


def _trace(
    role: str,
    *,
    call_id: str | None = None,
    temperature: float | None = None,
    prompt_template_id: str = "phase5_method_writer_section_v1",
) -> GenerationCallTrace:
    """Build a :class:`GenerationCallTrace` for the given role.

    By default the effective temperature is the role's protocol default
    from :data:`ROLE_GENERATION_CONFIGS`, so the trace passes the
    ``per_role_sampling_config_evidenced`` criterion.
    """

    if temperature is None:
        temperature = ROLE_GENERATION_CONFIGS[role].temperature
    return GenerationCallTrace(
        call_id=call_id or f"LLM-{role}-1",
        prompt_template_id=prompt_template_id,
        role=role,
        effective_config=EffectiveSamplingConfig(
            role=role,
            temperature=temperature,
            max_output_tokens=ROLE_GENERATION_CONFIGS[role].max_output_tokens_default,
            top_p=ROLE_GENERATION_CONFIGS[role].top_p,
            top_k=ROLE_GENERATION_CONFIGS[role].top_k,
        ),
        finish_reason="stop",
    )


def _compliant_traces_for_all_llm_roles() -> list[GenerationCallTrace]:
    """Return one trace per LLM-calling role, all temperature-compliant."""

    return [_trace(role) for role in LLM_CALLING_ROLES]


# ---------------------------------------------------------------------------
# A passing full report
# ---------------------------------------------------------------------------


def _passing_report_kwargs() -> dict[str, Any]:
    """Return kwargs for ``check_r8_acceptance`` that produce an accepted report.

    The baseline exercises EVERY criterion (no skips): trace digest
    matches, checkpoint/resume digests are present and consistent, and
    the paper-read-only-at-end protocol evidence is recorded.  This
    reflects the tightened R8 checker where ``skipped`` counts as
    failure for acceptance.
    """

    claim = _claim(
        "claim-1",
        canonical_text="the model computes a softmax over the class dimension",
        covers_obligation_ids=["obl-1"],
        allowed_wording_boundary="softmax over the class dimension",
    )
    claim_set = _claim_set([claim])
    coverage = _coverage_report([_coverage_item("obl-1", coverage_status="supported", matched_claim_ids=("claim-1",))])
    validation = _validation_report(unsupported=0, supported=1)
    decision = _agent_decision(
        decision="SEARCH_SYMBOLS",
        rationale="issue_driven:missing_anchor",
        evidence_ids=["tc-1", "tc-2"],
    )
    decisions = [decision]
    tool_refs = ["tc-1", "tc-2"]
    recorded_trace_digest = compute_trace_digest(decisions, tool_refs)
    final_state_digest = "sha256:final-state-1"
    return {
        "run_id": "run-pass-1",
        "project_id": "proj-1",
        "decisions": decisions,
        "tool_call_trace_refs": tool_refs,
        "recorded_trace_digest": recorded_trace_digest,
        "coverage_report": coverage,
        "claim_set": claim_set,
        "validation_report": validation,
        "method_text": "The model computes a softmax over the class dimension.",
        "original_final_state_digest": final_state_digest,
        "resumed_final_state_digest": final_state_digest,
        "run_environment": {
            "CODE2PAPER_LLM_CACHE": "0",
            "CODE2PAPER_TP_SIZE": "2",
            "CODE2PAPER_NUM_GPUS": "2",
            "CODE2PAPER_PARALLEL_PROJECTS": "0",
        },
        "run_temperature": 0.0,
        "source_authority_policy": {"code": "executable_hard", "tests": "test_scoped"},
        "paper_read_only_at_end": True,
        "generation_call_traces": _compliant_traces_for_all_llm_roles(),
        "intent_target_proposal_report": {
            "attempted": True,
            "accepted": True,
            "enriched_graph_digest": "sha256:intent-proposal",
        },
        "v3_error": "",
        "completion_report": _fake_completion_report(complete=True),
        "readiness_report": _fake_readiness_report(passed=True),
        "validation_manifest": {"status": "passed"},
        "method_clean_path": __file__,
    }


def _fake_completion_report(complete: bool):
    """Return a dict matching AgenticRunCompletionReport shape."""
    return {
        "mode": "agentic-run-completion-report",
        "status": "complete" if complete else "blocked",
        "complete": complete,
        "blocked_reason": "",
        "missing_deliverables": [],
        "checks": [],
        "recommended_actions": [],
    }


def _fake_readiness_report(passed: bool):
    """Return a dict matching AgenticRunReadinessReport shape."""
    return {
        "mode": "agentic-run-readiness-report",
        "passed": passed,
        "blocking_failures": 0 if passed else 1,
        "checks": [],
        "recommended_actions": [],
    }


def test_passing_run_produces_accepted_report():
    """A run that satisfies every criterion produces an accepted report."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.accepted is True
    assert report.protocol_check_passed is True
    # Every non-skipped criterion must have passed.  The trace and
    # checkpoint criteria are "skipped" when no digests are provided,
    # which does not block acceptance.
    for key, criterion in report.criteria.items():
        assert criterion.status in ("passed", "skipped"), (
            f"criterion {key!r} status={criterion.status!r} reason={criterion.reason!r}"
        )
    assert report.content_digest.startswith("sha256:")
    # All sixteen criteria must be present in the report.
    expected_keys = {
        "gap_driven_tool_selection",
        "code_mainline_in_method",
        "no_project_specific_claim_literals",
        "unsupported_final_sentences_zero",
        "must_cover_terminal",
        "no_evidence_free_equations",
        "trace_reproducible",
        "checkpoint_resume_consistent",
        "per_role_sampling_config_evidenced",
        "v3_research_succeeded",
        "typed_intent_proposal_accepted",
        "completion_complete",
        "readiness_passed",
        "validation_manifest_passed",
        "method_clean_exists",
        "method_has_supported_mainline",
    }
    assert set(report.criteria.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 1. gap_driven_tool_selection
# ---------------------------------------------------------------------------


def test_gap_driven_tool_selection_passes_with_gap_indicator_and_tool_action():
    """A decision whose rationale contains a gap indicator and whose action
    is a tool-calling action passes the criterion."""

    decision = _agent_decision(
        decision="SEARCH_SYMBOLS",
        rationale="issue_driven:missing_anchor",
    )
    found, evidence = has_gap_driven_tool_selection([decision])
    assert found is True
    assert evidence  # non-empty decision identifier


def test_gap_driven_tool_selection_fails_with_record_gap_only():
    """A ``RECORD_GAP`` action alone (no tool call) does not count."""

    decision = _agent_decision(
        decision="RECORD_GAP",
        rationale="issue_driven:missing_anchor",
    )
    found, _ = has_gap_driven_tool_selection([decision])
    assert found is False


def test_gap_driven_tool_selection_fails_with_no_gap_indicator():
    """A tool-calling action without a gap indicator does not count."""

    decision = _agent_decision(
        decision="SEARCH_SYMBOLS",
        rationale="routine exploration",
    )
    found, _ = has_gap_driven_tool_selection([decision])
    assert found is False


def test_gap_driven_tool_selection_fails_with_no_decisions():
    found, _ = has_gap_driven_tool_selection([])
    assert found is False


def test_gap_driven_tool_selection_passes_with_various_gap_indicators():
    """Every gap indicator substring should be recognized."""

    for indicator in (
        "gap",
        "missing",
        "unresolved",
        "no_progress",
        "missing_anchor",
        "missing_relation",
        "missing_condition",
        "wrong_span_role",
        "branch_ambiguity",
        "config_ambiguity",
        "no_information_gain",
        "truncated_observation",
        "ambiguous_observation",
        "hint_code_conflict",
        "formula_unsupported",
        "sentence_claim_atomicity",
        "direct_evidence_semantically_unrelated",
        "no_semantically_matching_projected_claim",
        "budget_exhausted",
        "quality_regression",
    ):
        decision = _agent_decision(
            decision="READ_CANDIDATE",
            rationale=f"selected because {indicator}",
        )
        found, _ = has_gap_driven_tool_selection([decision])
        assert found is True, f"indicator {indicator!r} not recognized"


def test_gap_driven_tool_selection_recognizes_research_decision_v1_fields():
    """``ResearchDecisionV1``-like objects with ``action`` / ``goal`` /
    ``issue_id`` / ``expected_information_gain`` fields are also recognized."""

    class _FakeResearchDecision:
        decision_id = "decision-fake-1"
        action = "TRACE_CALLS"
        rationale = ""
        goal = "resolve missing_relation for obligation=obl-1"
        issue_id = ""
        expected_information_gain = ""

    found, evidence = has_gap_driven_tool_selection([_FakeResearchDecision()])
    assert found is True
    assert evidence == "decision-fake-1"


# ---------------------------------------------------------------------------
# 2. code_mainline_in_method
# ---------------------------------------------------------------------------


def test_code_mainline_in_method_passes_with_supported_must_cover_claim():
    """A supported claim covering a must_cover obligation with validated
    sentences passes."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.criteria["code_mainline_in_method"].status == "passed"


def test_code_mainline_in_method_fails_when_no_supported_must_cover():
    """When no must_cover obligation reached status=supported, the criterion
    fails."""

    kwargs = _passing_report_kwargs()
    kwargs["coverage_report"] = _coverage_report([
        _coverage_item("obl-1", coverage_status="partial", matched_claim_ids=("claim-1",))
    ])
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["code_mainline_in_method"].status == "failed"
    assert "no must_cover obligation reached status=supported" in report.criteria["code_mainline_in_method"].reason


def test_code_mainline_in_method_fails_when_no_supported_claim_for_must_cover():
    """When the must_cover is supported but no claim covers it, the criterion
    fails."""

    kwargs = _passing_report_kwargs()
    # Claim no longer covers obl-1.
    kwargs["claim_set"] = _claim_set([
        _claim("claim-1", covers_obligation_ids=["obl-other"])
    ])
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["code_mainline_in_method"].status == "failed"


def test_code_mainline_in_method_fails_when_validation_records_zero_claims():
    """When the validation report records zero supported/caveated claims, the
    criterion fails (the Method text has no validated claims)."""

    kwargs = _passing_report_kwargs()
    kwargs["validation_report"] = _validation_report(unsupported=0, supported=0, caveated=0)
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["code_mainline_in_method"].status == "failed"


def test_code_mainline_in_method_fails_when_missing_artifacts():
    """When coverage_report / claim_set / validation_report are missing, the
    criterion fails."""

    report = check_r8_acceptance(
        run_id="run-1",
        decisions=[_agent_decision(rationale="issue_driven:missing_anchor")],
    )
    assert report.criteria["code_mainline_in_method"].status == "failed"


# ---------------------------------------------------------------------------
# 3. no_project_specific_claim_literals
# ---------------------------------------------------------------------------


def test_no_project_specific_claim_literals_passes_with_clean_text():
    """Claim and Method text without project literals passes."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.criteria["no_project_specific_claim_literals"].status == "passed"


def test_scan_text_for_project_literals_finds_forbidden_literal():
    """The scanner flags project literals using word boundaries."""

    # The forbidden set includes "rap", "ebcar", etc.
    matches = scan_text_for_project_literals("the rap model computes scores")
    assert "rap" in matches


def test_scan_text_for_project_literals_does_not_match_substring():
    """``rap`` inside ``PageRank`` is NOT flagged (word boundary)."""

    matches = scan_text_for_project_literals("PageRank computes scores")
    assert "rap" not in matches


def test_scan_text_for_project_literals_finds_hyphenated_literal():
    """Hyphenated project literals like ``dyg-mamba`` are flagged."""

    matches = scan_text_for_project_literals("the dyg-mamba model uses Mamba")
    # ``dyg-mamba`` and ``dyg_mamba`` and ``dygmamba`` are all forbidden.
    found_lowered = [m.lower() for m in matches]
    assert any("dyg" in m and "mamba" in m for m in found_lowered)


def test_scan_text_for_project_literals_finds_underscore_literal():
    """``ebcar`` inside ``ebcar_stage`` IS flagged (underscore is a
    separator)."""

    matches = scan_text_for_project_literals("the ebcar_stage computes attention")
    assert any("ebcar" in m for m in matches)


def test_scan_claims_for_project_literals_flags_claim_text():
    """Claims with project literals are flagged."""

    claim = _claim(
        "claim-bad",
        canonical_text="the rap model computes a softmax",
    )
    flagged = scan_claims_for_project_literals([claim])
    assert "claim-bad" in flagged
    assert "rap" in flagged["claim-bad"]


def test_no_project_specific_claim_literals_fails_when_claim_has_literal():
    """A claim with a project literal fails the criterion."""

    kwargs = _passing_report_kwargs()
    kwargs["claim_set"] = _claim_set([
        _claim(
            "claim-1",
            canonical_text="the rap model computes a softmax",
            covers_obligation_ids=["obl-1"],
            allowed_wording_boundary="softmax",
        )
    ])
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["no_project_specific_claim_literals"]
    assert criterion.status == "failed"
    assert any("claim-1" in e for e in criterion.evidence)


def test_no_project_specific_claim_literals_fails_when_method_has_literal():
    """Method text with a project literal fails the criterion."""

    kwargs = _passing_report_kwargs()
    kwargs["method_text"] = "The rap model computes a softmax."
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["no_project_specific_claim_literals"]
    assert criterion.status == "failed"
    assert any("method" in e for e in criterion.evidence)


def test_no_project_specific_claim_literals_passes_with_pagerank():
    """``PageRank`` does NOT trigger the ``rap`` literal (word boundary)."""

    kwargs = _passing_report_kwargs()
    kwargs["method_text"] = "The model uses PageRank to compute scores."
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["no_project_specific_claim_literals"].status == "passed"


# ---------------------------------------------------------------------------
# 4. unsupported_final_sentences_zero
# ---------------------------------------------------------------------------


def test_unsupported_final_sentences_zero_passes_with_zero():
    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.criteria["unsupported_final_sentences_zero"].status == "passed"


def test_unsupported_final_sentences_zero_fails_with_nonzero():
    kwargs = _passing_report_kwargs()
    kwargs["validation_report"] = _validation_report(unsupported=2, supported=1)
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["unsupported_final_sentences_zero"]
    assert criterion.status == "failed"
    assert "unsupported_claims=2" in criterion.reason


def test_unsupported_final_sentences_zero_passes_with_missing_validation_report():
    """When no validation report is provided, the criterion defaults to
    ``unsupported=0`` and passes (the caller may skip this check)."""

    kwargs = _passing_report_kwargs()
    kwargs["validation_report"] = None
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["unsupported_final_sentences_zero"].status == "passed"


# ---------------------------------------------------------------------------
# 5. must_cover_terminal
# ---------------------------------------------------------------------------


def test_must_cover_terminal_passes_when_all_terminal():
    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.criteria["must_cover_terminal"].status == "passed"


def test_must_cover_terminal_passes_with_explicit_gap():
    """An ``explicit_gap`` status is terminal and passes."""

    kwargs = _passing_report_kwargs()
    kwargs["coverage_report"] = _coverage_report([
        _coverage_item("obl-1", coverage_status="explicit_gap", matched_gap_ids=("gap-1",))
    ])
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["must_cover_terminal"].status == "passed"


def test_must_cover_terminal_fails_with_unresolved():
    """An ``unresolved`` must_cover fails the criterion."""

    kwargs = _passing_report_kwargs()
    kwargs["coverage_report"] = _coverage_report([
        _coverage_item("obl-1", coverage_status="unresolved"),
        _coverage_item("obl-2", coverage_status="supported", matched_claim_ids=("claim-1",)),
    ])
    # Need a claim that covers obl-2 so the mainline check still has data.
    kwargs["claim_set"] = _claim_set([
        _claim("claim-1", covers_obligation_ids=["obl-2"])
    ])
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["must_cover_terminal"]
    assert criterion.status == "failed"
    assert "obl-1" in criterion.evidence


def test_must_cover_terminal_fails_when_missing_coverage_report():
    kwargs = _passing_report_kwargs()
    kwargs["coverage_report"] = None
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["must_cover_terminal"].status == "failed"


# ---------------------------------------------------------------------------
# 6. no_evidence_free_equations
# ---------------------------------------------------------------------------


def test_no_evidence_free_equations_passes_with_authorized_tokens():
    """Equation tokens that appear in a claim's boundary pass."""

    kwargs = _passing_report_kwargs()
    kwargs["claim_set"] = _claim_set([
        _claim(
            "claim-1",
            canonical_text="the model computes s = softmax(x)",
            covers_obligation_ids=["obl-1"],
            allowed_wording_boundary="softmax s",
        )
    ])
    kwargs["method_text"] = "The model computes $s = \\mathrm{softmax}(x)$."
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["no_evidence_free_equations"].status == "passed"


def test_no_evidence_free_equations_passes_with_explicit_formula_permission():
    """A boundary containing ``equation`` or ``formula`` permits any formula."""

    kwargs = _passing_report_kwargs()
    kwargs["claim_set"] = _claim_set([
        _claim(
            "claim-1",
            canonical_text="the model computes s = softmax(x)",
            covers_obligation_ids=["obl-1"],
            allowed_wording_boundary="formula permitted",
        )
    ])
    kwargs["method_text"] = "The model computes $s = \\mathrm{softmax}(x)$."
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["no_evidence_free_equations"].status == "passed"


def test_no_evidence_free_equations_fails_with_unauthorized_token():
    """An equation token not in any claim boundary fails."""

    kwargs = _passing_report_kwargs()
    kwargs["claim_set"] = _claim_set([
        _claim(
            "claim-1",
            canonical_text="the model computes a softmax",
            covers_obligation_ids=["obl-1"],
            allowed_wording_boundary="softmax",
        )
    ])
    # ``foo`` is an equation token not authorized by any claim.
    kwargs["method_text"] = "The model computes $foo = \\mathrm{bar}(x)$."
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["no_evidence_free_equations"]
    assert criterion.status == "failed"
    assert "foo" in criterion.evidence


def test_no_evidence_free_equations_skipped_with_empty_method_text():
    """When no Method text is provided, the criterion is skipped (passes)."""

    kwargs = _passing_report_kwargs()
    kwargs["method_text"] = ""
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["no_evidence_free_equations"].status == "passed"


def test_extract_equation_tokens_finds_inline_math():
    tokens = extract_equation_tokens("The score is $s = \\mathrm{softmax}(x)$.")
    assert "s" in tokens
    assert "softmax" in tokens
    assert "x" in tokens


def test_extract_equation_tokens_finds_display_math():
    tokens = extract_equation_tokens("$$\\mathrm{loss} = -\\log(p)$$")
    assert "loss" in tokens
    # LaTeX command tokens (mathrm, log, etc.) are filtered out.
    assert "log" not in tokens
    assert "p" in tokens


def test_extract_equation_tokens_finds_name_eq_pattern():
    tokens = extract_equation_tokens("We set learning_rate = 0.001.")
    assert "learning_rate" in tokens


def test_unauthorized_equation_tokens_returns_empty_when_authorized():
    claim = _claim(
        "claim-1",
        allowed_wording_boundary="softmax s x",
    )
    unauthorized = unauthorized_equation_tokens(
        "The model computes $s = \\mathrm{softmax}(x)$.",
        [claim],
    )
    assert unauthorized == []


def test_unauthorized_equation_tokens_returns_unauthorized():
    claim = _claim(
        "claim-1",
        allowed_wording_boundary="softmax",
    )
    unauthorized = unauthorized_equation_tokens(
        "The model computes $foo = \\mathrm{bar}(x)$.",
        [claim],
    )
    assert "foo" in unauthorized
    assert "bar" in unauthorized


# ---------------------------------------------------------------------------
# 7. trace_reproducible
# ---------------------------------------------------------------------------


def test_trace_reproducible_skipped_when_no_recorded_digest():
    """When no recorded digest is provided, the criterion is skipped."""

    kwargs = _passing_report_kwargs()
    kwargs["recorded_trace_digest"] = ""
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["trace_reproducible"].status == "skipped"


def test_trace_reproducible_passes_when_digest_matches():
    """A recorded digest that matches the recomputed digest passes."""

    decision = _agent_decision(
        decision="SEARCH_SYMBOLS",
        rationale="issue_driven:missing_anchor",
    )
    recorded = compute_trace_digest([decision], ["tc-1", "tc-2"])
    kwargs = _passing_report_kwargs()
    kwargs["decisions"] = [decision]
    kwargs["tool_call_trace_refs"] = ["tc-1", "tc-2"]
    kwargs["recorded_trace_digest"] = recorded
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["trace_reproducible"].status == "passed"


def test_trace_reproducible_fails_when_digest_mismatches():
    """A recorded digest that does NOT match the recomputed digest fails."""

    decision = _agent_decision(
        decision="SEARCH_SYMBOLS",
        rationale="issue_driven:missing_anchor",
    )
    kwargs = _passing_report_kwargs()
    kwargs["decisions"] = [decision]
    kwargs["tool_call_trace_refs"] = ["tc-1", "tc-2"]
    kwargs["recorded_trace_digest"] = "sha256:deadbeef"
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["trace_reproducible"].status == "failed"


def test_compute_trace_digest_is_deterministic():
    """The same decisions + tool refs produce the same digest."""

    decision = _agent_decision(rationale="issue_driven:missing_anchor")
    d1 = compute_trace_digest([decision], ["tc-1"])
    d2 = compute_trace_digest([decision], ["tc-1"])
    assert d1 == d2


def test_compute_trace_digest_changes_with_different_decisions():
    decision1 = _agent_decision(rationale="issue_driven:missing_anchor")
    decision2 = _agent_decision(rationale="issue_driven:missing_relation")
    d1 = compute_trace_digest([decision1], ["tc-1"])
    d2 = compute_trace_digest([decision2], ["tc-1"])
    assert d1 != d2


def test_verify_trace_reproducibility_returns_true_when_recorded_empty():
    """An empty recorded digest skips the check (returns True)."""

    match, recomputed = verify_trace_reproducibility("", [], [])
    assert match is True
    assert recomputed == ""


# ---------------------------------------------------------------------------
# 8. checkpoint_resume_consistent
# ---------------------------------------------------------------------------


def test_checkpoint_resume_consistent_skipped_when_no_digests():
    kwargs = _passing_report_kwargs()
    kwargs["original_final_state_digest"] = ""
    kwargs["resumed_final_state_digest"] = ""
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["checkpoint_resume_consistent"].status == "skipped"


def test_checkpoint_resume_consistent_passes_when_digests_match():
    kwargs = _passing_report_kwargs()
    kwargs["original_final_state_digest"] = "sha256:state-1"
    kwargs["resumed_final_state_digest"] = "sha256:state-1"
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["checkpoint_resume_consistent"].status == "passed"


def test_checkpoint_resume_consistent_fails_when_digests_mismatch():
    kwargs = _passing_report_kwargs()
    kwargs["original_final_state_digest"] = "sha256:state-1"
    kwargs["resumed_final_state_digest"] = "sha256:state-2"
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["checkpoint_resume_consistent"].status == "failed"


def test_checkpoint_resume_consistent_skipped_when_only_one_digest():
    kwargs = _passing_report_kwargs()
    kwargs["original_final_state_digest"] = "sha256:state-1"
    kwargs["resumed_final_state_digest"] = ""
    # resumed_final_state_digest is empty.
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["checkpoint_resume_consistent"].status == "skipped"


def test_verify_checkpoint_resume_consistency_returns_true_when_match():
    consistent, reason = verify_checkpoint_resume_consistency("sha256:a", "sha256:a")
    assert consistent is True
    assert reason == "match"


def test_verify_checkpoint_resume_consistency_returns_false_when_mismatch():
    consistent, reason = verify_checkpoint_resume_consistency("sha256:a", "sha256:b")
    assert consistent is False
    assert "mismatch" in reason


# ---------------------------------------------------------------------------
# 9. per_role_sampling_config_evidenced (Phase 1 R8.1 protocol check)
# ---------------------------------------------------------------------------


def test_per_role_sampling_config_passes_with_compliant_traces_for_all_roles():
    """One compliant trace per LLM-calling role passes the criterion."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.criteria["per_role_sampling_config_evidenced"].status == "passed"
    assert report.accepted is True


def test_per_role_sampling_config_fails_when_no_traces_provided():
    """No traces at all -> every unconditional live role is missing."""

    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = []
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "missing_role_traces" in criterion.reason
    for role in (
        CODE_INTAKE,
        CODE_ANALYZER,
        RESEARCH_SUPERVISOR,
        AUTHORING_PLANNER,
        METHOD_WRITER,
    ):
        assert role in criterion.reason
    assert report.accepted is False


def test_per_role_sampling_config_allows_uninvoked_conditional_role():
    """A clean run need not manufacture a semantic-verifier call."""

    traces = [_trace(role) for role in LLM_CALLING_ROLES if role != SEMANTIC_VERIFIER]
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "passed"
    assert report.accepted is True


def test_per_role_sampling_config_fails_when_required_role_missing():
    traces = [_trace(role) for role in LLM_CALLING_ROLES if role != METHOD_WRITER]
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert METHOD_WRITER in criterion.reason


def test_per_role_sampling_config_fails_when_temperature_mismatches():
    """A trace whose effective temperature doesn't match the role protocol fails."""

    # Build 5 compliant traces plus one with the wrong temperature.
    traces = _compliant_traces_for_all_llm_roles()
    # Replace the writer trace with a wrong-temperature variant.
    traces = [t for t in traces if t.role != METHOD_WRITER]
    traces.append(_trace(METHOD_WRITER, temperature=0.10))  # should be 0.70
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "temperature_mismatch" in criterion.reason
    assert METHOD_WRITER in criterion.reason
    assert "actual=0.1" in criterion.reason
    assert "expected=0.7" in criterion.reason


def test_per_role_sampling_config_fails_when_top_p_mismatches():
    traces = _compliant_traces_for_all_llm_roles()
    writer = next(item for item in traces if item.role == METHOD_WRITER)
    traces = [item for item in traces if item.role != METHOD_WRITER]
    traces.append(writer.model_copy(update={
        "effective_config": writer.effective_config.model_copy(update={"top_p": 0.5})
    }))
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "top_p_mismatch" in criterion.reason


def test_per_role_sampling_config_fails_above_the_role_output_ceiling():
    traces = _compliant_traces_for_all_llm_roles()
    supervisor = next(item for item in traces if item.role == RESEARCH_SUPERVISOR)
    traces = [item for item in traces if item.role != RESEARCH_SUPERVISOR]
    traces.append(supervisor.model_copy(update={
        "effective_config": supervisor.effective_config.model_copy(
            update={"max_output_tokens": 1537}
        )
    }))
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "max_output_tokens_out_of_range" in criterion.reason


def test_per_role_sampling_config_fails_when_deterministic_role_has_trace():
    """A trace tagged with a deterministic role is a hard failure."""

    traces = _compliant_traces_for_all_llm_roles()
    # Add a forbidden deterministic-role trace.
    traces.append(_trace(DETERMINISTIC_COMPILER, temperature=0.0))
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "deterministic_role_has_trace" in criterion.reason
    assert DETERMINISTIC_COMPILER in criterion.reason


def test_per_role_sampling_config_accepts_dict_traces_from_json():
    """The helper accepts JSON dicts (as loaded from run summary)."""

    traces = [t.model_dump(mode="json") for t in _compliant_traces_for_all_llm_roles()]
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["per_role_sampling_config_evidenced"].status == "passed"
    assert report.accepted is True


def test_per_role_sampling_config_fails_when_dict_trace_missing_role():
    """A dict trace missing the ``role`` field is flagged as a parse error."""

    traces = [t.model_dump(mode="json") for t in _compliant_traces_for_all_llm_roles()]
    # Remove the role from one trace.
    bad_trace = dict(traces[0])
    bad_trace["role"] = ""
    traces[0] = bad_trace
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    # Either missing role or missing role trace (since role="" doesn't match any known role).
    assert "trace_0_missing_role" in criterion.reason or "missing_role_traces" in criterion.reason


def test_per_role_sampling_config_fails_when_dict_trace_missing_temperature():
    """A dict trace missing ``effective_config.temperature`` is a parse error."""

    traces = [t.model_dump(mode="json") for t in _compliant_traces_for_all_llm_roles()]
    bad_trace = dict(traces[0])
    bad_trace["effective_config"] = {"role": bad_trace["role"]}
    traces[0] = bad_trace
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert "trace_0_missing_temperature" in criterion.reason or "missing_role_traces" in criterion.reason


def test_per_role_sampling_config_fails_with_unrecognized_trace_shape():
    """A non-object, non-dict trace is a parse error."""

    traces = _compliant_traces_for_all_llm_roles()
    traces.append("not-a-trace")  # type: ignore[arg-type]
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert f"trace_{len(LLM_CALLING_ROLES)}_unrecognized_shape" in criterion.reason


def test_per_role_sampling_config_accepts_multiple_traces_per_role():
    """Multiple traces per role are fine as long as all are compliant."""

    traces = _compliant_traces_for_all_llm_roles()
    # Add an extra compliant writer trace.
    traces.append(_trace(METHOD_WRITER, call_id="LLM-writer-2"))
    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = traces
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["per_role_sampling_config_evidenced"].status == "passed"
    assert report.accepted is True


def test_per_role_sampling_config_evidence_is_non_empty_on_failure():
    """Failure evidence is populated for downstream diagnostics."""

    kwargs = _passing_report_kwargs()
    kwargs["generation_call_traces"] = []
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["per_role_sampling_config_evidenced"]
    assert criterion.status == "failed"
    assert len(criterion.evidence) > 0


# ---------------------------------------------------------------------------
# 10. v3_research_succeeded (R8.1 Phase 2 V3 research integrity check)
# ---------------------------------------------------------------------------


def test_v3_research_succeeded_passes_when_v3_error_empty():
    """Empty ``v3_error`` means V3 research succeeded (or V3 not enabled)."""

    kwargs = _passing_report_kwargs()
    kwargs["v3_error"] = ""
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["v3_research_succeeded"].status == "passed"
    assert report.accepted is True


def test_v3_research_succeeded_passes_when_v3_error_none():
    """``None`` is normalized to empty string and treated as success."""

    kwargs = _passing_report_kwargs()
    kwargs["v3_error"] = None  # type: ignore[assignment]
    report = check_r8_acceptance(**kwargs)
    assert report.criteria["v3_research_succeeded"].status == "passed"
    assert report.accepted is True


def test_v3_research_succeeded_fails_when_v3_error_nonempty():
    """Non-empty ``v3_error`` means V3 failed and the run must be rejected."""

    kwargs = _passing_report_kwargs()
    kwargs["v3_error"] = "RuntimeError: subgraph did not produce a result"
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["v3_research_succeeded"]
    assert criterion.status == "failed"
    assert "V3 research subgraph failed" in criterion.reason
    assert criterion.evidence == ("RuntimeError: subgraph did not produce a result",)
    # Top-level acceptance must be False even when all other criteria pass.
    assert report.accepted is False


def test_v3_research_succeeded_fails_with_long_error_truncated():
    """Long error messages are truncated in the reason but preserved in evidence."""

    kwargs = _passing_report_kwargs()
    long_error = "E" * 500
    kwargs["v3_error"] = long_error
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["v3_research_succeeded"]
    assert criterion.status == "failed"
    # Reason is truncated to 300 chars + "...".
    assert "..." in criterion.reason
    assert len(criterion.reason) < 400
    # Full error is preserved in the evidence tuple.
    assert criterion.evidence == (long_error,)
    assert report.accepted is False


def test_v3_research_succeeded_fails_when_v3_error_whitespace_only():
    """Whitespace-only ``v3_error`` is NOT treated as failure (normalized to empty)."""

    kwargs = _passing_report_kwargs()
    # Note: the checker normalizes falsy values (including empty string)
    # but a whitespace-only string is truthy in Python.  We document
    # this behavior: callers should pass an empty string when V3
    # succeeded, not a whitespace-only string.
    kwargs["v3_error"] = "   "
    report = check_r8_acceptance(**kwargs)
    # Whitespace-only is truthy -> fails.
    assert report.criteria["v3_research_succeeded"].status == "failed"
    assert report.accepted is False


def test_v3_research_succeeded_in_criteria_keys():
    """The criterion appears in the report's criteria map."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert "v3_research_succeeded" in report.criteria


# ---------------------------------------------------------------------------
# 11. typed_intent_proposal_accepted (Gemma Intent Agent protocol check)
# ---------------------------------------------------------------------------


def test_typed_intent_proposal_passes_when_complete_proposal_is_accepted():
    report = check_r8_acceptance(**_passing_report_kwargs())
    criterion = report.criteria["typed_intent_proposal_accepted"]
    assert criterion.status == "passed"
    assert criterion.evidence == ("sha256:intent-proposal",)


def test_typed_intent_proposal_fails_when_missing_or_rejected():
    kwargs = _passing_report_kwargs()
    kwargs["intent_target_proposal_report"] = {
        "attempted": True,
        "accepted": False,
        "failure": "proposal_parse_failed",
    }
    report = check_r8_acceptance(**kwargs)
    criterion = report.criteria["typed_intent_proposal_accepted"]
    assert criterion.status == "failed"
    assert "proposal_parse_failed" in criterion.reason
    assert report.accepted is False


# ---------------------------------------------------------------------------
# Protocol settings check
# ---------------------------------------------------------------------------


def test_protocol_check_passes_with_default_settings():
    report = check_r8_acceptance(**_passing_report_kwargs())
    assert report.protocol_check_passed is True


def test_protocol_check_uses_role_traces_not_global_temperature():
    kwargs = _passing_report_kwargs()
    kwargs["run_temperature"] = 0.3
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is True
    assert report.accepted is True


def test_protocol_check_fails_when_llm_cache_not_off():
    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {
        "CODE2PAPER_LLM_CACHE": "1",
        "CODE2PAPER_TP_SIZE": "2",
        "CODE2PAPER_NUM_GPUS": "2",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_tp_size_not_2():
    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {
        "CODE2PAPER_LLM_CACHE": "0",
        "CODE2PAPER_TP_SIZE": "1",
        "CODE2PAPER_NUM_GPUS": "2",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_num_gpus_not_2():
    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {
        "CODE2PAPER_LLM_CACHE": "0",
        "CODE2PAPER_TP_SIZE": "2",
        "CODE2PAPER_NUM_GPUS": "4",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_parallel_projects_nonzero():
    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {
        "CODE2PAPER_LLM_CACHE": "0",
        "CODE2PAPER_TP_SIZE": "2",
        "CODE2PAPER_NUM_GPUS": "2",
        "CODE2PAPER_PARALLEL_PROJECTS": "4",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_paper_promoted_to_hard_evidence():
    kwargs = _passing_report_kwargs()
    kwargs["source_authority_policy"] = {
        "code": "executable_hard",
        "paper": "executable_hard",  # forbidden promotion
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_passes_when_paper_is_semantic_hint():
    """paper as ``semantic_hint`` is fine; only ``executable_hard`` is forbidden."""

    kwargs = _passing_report_kwargs()
    kwargs["source_authority_policy"] = {
        "code": "executable_hard",
        "paper": "semantic_hint",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is True


def test_protocol_check_fails_when_tp_size_absent():
    """When TP size / num GPUs env vars are absent, the check fails: an
    acceptance run must positively evidence TP=2 on 2 GPUs rather than
    rely on absence."""

    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {"CODE2PAPER_LLM_CACHE": "0"}
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_does_not_require_a_global_temperature():
    """Only the per-role trace records are authoritative sampling evidence."""

    kwargs = _passing_report_kwargs()
    kwargs["run_temperature"] = None
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is True


def test_protocol_check_fails_when_source_authority_absent():
    """An empty source authority policy is a failure."""

    kwargs = _passing_report_kwargs()
    kwargs["source_authority_policy"] = {}
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_paper_read_only_at_end_not_evidenced():
    """Missing paper-read-only-at-end evidence is a failure."""

    kwargs = _passing_report_kwargs()
    kwargs["paper_read_only_at_end"] = None
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


def test_protocol_check_fails_when_paper_read_only_at_end_violated():
    """Explicitly evidencing that the paper was read BEFORE authoring
    (``paper_read_only_at_end=False``) is a failure."""

    kwargs = _passing_report_kwargs()
    kwargs["paper_read_only_at_end"] = False
    report = check_r8_acceptance(**kwargs)
    assert report.protocol_check_passed is False


# ---------------------------------------------------------------------------
# Report structure and serialization
# ---------------------------------------------------------------------------


def test_report_has_sixteen_criteria():
    """The report has 16 criteria including the R8.2 subset, R8.1 protocol,
    V3 integrity, typed Intent Agent gate, and R8.3 completion/readiness gates."""

    report = check_r8_acceptance(**_passing_report_kwargs())
    assert len(report.criteria) == 16


def test_report_digest_is_stable():
    """The same inputs produce the same content digest."""

    report1 = check_r8_acceptance(**_passing_report_kwargs())
    report2 = check_r8_acceptance(**_passing_report_kwargs())
    assert report1.content_digest == report2.content_digest


def test_report_digest_changes_when_criterion_changes():
    """A failing criterion produces a different digest."""

    report1 = check_r8_acceptance(**_passing_report_kwargs())
    kwargs = _passing_report_kwargs()
    kwargs["validation_report"] = _validation_report(unsupported=1, supported=1)
    report2 = check_r8_acceptance(**kwargs)
    assert report1.content_digest != report2.content_digest


def test_write_and_load_report_round_trip(tmp_path: Path):
    report = check_r8_acceptance(**_passing_report_kwargs())
    path = tmp_path / "r8_acceptance.json"
    written = write_r8_acceptance_report(path, report)
    assert written == path
    loaded = load_r8_acceptance_report(path)
    assert loaded.run_id == report.run_id
    assert loaded.accepted == report.accepted
    assert loaded.content_digest == report.content_digest
    assert set(loaded.criteria.keys()) == set(report.criteria.keys())


def test_criterion_model_is_frozen():
    """R8AcceptanceCriterion is frozen (immutable)."""

    criterion = R8AcceptanceCriterion(
        criterion_id="test",
        description="test",
        status="passed",
    )
    with pytest.raises(Exception):
        criterion.status = "failed"  # type: ignore[misc]


def test_protocol_settings_default_is_frozen():
    """R8ProtocolSettings is frozen with the R8.1 defaults."""

    settings = R8ProtocolSettings()
    assert settings.temperature is None
    assert settings.llm_cache_env == "0"
    assert settings.single_tp2_instance is True
    assert settings.serial_execution is True
    assert settings.paper_promoted_to_hard_evidence is False
    with pytest.raises(Exception):
        settings.temperature = 0.5  # type: ignore[misc]


def test_report_rejects_extra_fields():
    """R8AcceptanceReport rejects extra fields (extra='forbid')."""

    with pytest.raises(Exception):
        R8AcceptanceReport(
            run_id="run-1",
            extra_field="not allowed",  # type: ignore[call-arg]
        )


# ---------------------------------------------------------------------------
# Run-directory scanner
# ---------------------------------------------------------------------------


def _write_run_dir(tmp_path: Path, **overrides: Any) -> Path:
    """Write a synthetic run directory with the standard artifacts."""

    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True)
    kwargs = _passing_report_kwargs()

    # Write agentic_run_summary.json (with decisions).
    summary: dict[str, Any] = {
        "run_id": kwargs["run_id"],
        "decisions": [d.model_dump(mode="json") for d in kwargs["decisions"]],
        "environment": kwargs["run_environment"],
        "temperature": kwargs["run_temperature"],
        "source_authority_policy": kwargs["source_authority_policy"],
        "paper_read_only_at_end": kwargs["paper_read_only_at_end"],
        "trace_digest": kwargs["recorded_trace_digest"],
        "tool_call_trace_refs": kwargs["tool_call_trace_refs"],
        "generation_call_traces": [
            trace.model_dump(mode="json")
            for trace in kwargs["generation_call_traces"]
        ],
        "final_state_digest": kwargs["original_final_state_digest"],
    }
    summary.update(overrides.pop("summary_overrides", {}))
    (run_dir / "agentic_run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    # Write atomic_claims_v3.json.
    (run_dir / "atomic_claims_v3.json").write_text(
        kwargs["claim_set"].model_dump_json(indent=2), encoding="utf-8"
    )

    # Write obligation_coverage_v2.json.
    (run_dir / "obligation_coverage_v2.json").write_text(
        kwargs["coverage_report"].model_dump_json(indent=2), encoding="utf-8"
    )

    # Write text_evidence_validation.json.
    (run_dir / "text_evidence_validation.json").write_text(
        kwargs["validation_report"].model_dump_json(indent=2), encoding="utf-8"
    )

    # Write Method text.
    (run_dir / "text_clean.md").write_text(
        kwargs["method_text"], encoding="utf-8"
    )

    (run_dir / "intent_target_proposal_report_v1.json").write_text(
        json.dumps(kwargs["intent_target_proposal_report"], indent=2),
        encoding="utf-8",
    )

    # Write completion_report, readiness_report, validation_manifest.
    artifacts_10_run = run_dir / "artifacts" / "10_run"
    artifacts_10_run.mkdir(parents=True, exist_ok=True)
    (artifacts_10_run / "agentic_run_completion_report.json").write_text(
        json.dumps(kwargs["completion_report"], indent=2), encoding="utf-8"
    )
    (artifacts_10_run / "agentic_run_readiness_report.json").write_text(
        json.dumps(kwargs["readiness_report"], indent=2), encoding="utf-8"
    )
    (artifacts_10_run / "validation_manifest.json").write_text(
        json.dumps(kwargs["validation_manifest"], indent=2), encoding="utf-8"
    )
    # Write method_clean.md in the authoring artifacts directory.
    authoring_dir = run_dir / "artifacts" / "06_authoring"
    authoring_dir.mkdir(parents=True, exist_ok=True)
    method_clean = authoring_dir / "method_clean.md"
    method_clean.write_text(kwargs["method_text"], encoding="utf-8")
    # Update the summary's artifacts map to include the new files.
    summary["artifacts"] = {
        **(summary.get("artifacts") or {}),
        "agentic_run_completion_report": str(artifacts_10_run / "agentic_run_completion_report.json"),
        "agentic_run_readiness_report": str(artifacts_10_run / "agentic_run_readiness_report.json"),
        "validation_manifest": str(artifacts_10_run / "validation_manifest.json"),
        "text_clean_md": str(method_clean),
    }
    (run_dir / "agentic_run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    return run_dir


def test_check_r8_acceptance_from_run_dir_loads_artifacts(tmp_path: Path):
    """The run-dir scanner loads artifacts and produces a report."""

    run_dir = _write_run_dir(tmp_path)
    report = check_r8_acceptance_from_run_dir(run_dir)
    assert report.run_id == "run-pass-1"
    # The scanner reads decisions from the summary, so the gap-driven
    # check should find the AgentDecision with ``issue_driven:missing_anchor``.
    assert report.criteria["gap_driven_tool_selection"].status == "passed"
    assert report.criteria["code_mainline_in_method"].status == "passed"
    assert report.criteria["must_cover_terminal"].status == "passed"
    assert report.criteria["unsupported_final_sentences_zero"].status == "passed"
    assert report.criteria["typed_intent_proposal_accepted"].status == "passed"
    assert report.criteria["per_role_sampling_config_evidenced"].status == "passed"
    assert report.protocol_check_passed is True


def test_check_r8_acceptance_from_run_dir_handles_missing_files(tmp_path: Path):
    """Missing artifact files degrade gracefully (criterion fails)."""

    run_dir = tmp_path / "empty-run"
    run_dir.mkdir(parents=True)
    # No summary file, no artifacts -- run_id falls back to dir name.
    report = check_r8_acceptance_from_run_dir(run_dir)
    assert report.run_id == "empty-run"
    # With no decisions, the gap-driven check fails.
    assert report.criteria["gap_driven_tool_selection"].status == "failed"
    # With no coverage report, the must_cover check fails.
    assert report.criteria["must_cover_terminal"].status == "failed"


def test_check_r8_acceptance_from_run_dir_reads_resumed_run(tmp_path: Path):
    """When ``resumed_run_dir`` is provided, the resume check uses its
    final state digest."""

    original_dir = _write_run_dir(tmp_path)
    # Write the original summary with a final_state_digest.
    original_summary_path = original_dir / "agentic_run_summary.json"
    original_summary = json.loads(original_summary_path.read_text(encoding="utf-8"))
    original_summary["final_state_digest"] = "sha256:state-1"
    original_summary_path.write_text(json.dumps(original_summary, indent=2), encoding="utf-8")

    # Write a resumed run dir with a matching digest.
    resumed_dir = tmp_path / "run-1-resumed"
    resumed_dir.mkdir(parents=True)
    resumed_summary = {"run_id": "run-pass-1-resumed", "final_state_digest": "sha256:state-1"}
    (resumed_dir / "agentic_run_summary.json").write_text(
        json.dumps(resumed_summary, indent=2), encoding="utf-8"
    )

    report = check_r8_acceptance_from_run_dir(original_dir, resumed_run_dir=resumed_dir)
    assert report.criteria["checkpoint_resume_consistent"].status == "passed"


def test_check_r8_acceptance_from_run_dir_detects_resume_mismatch(tmp_path: Path):
    """A resumed run with a different final state digest fails the check."""

    original_dir = _write_run_dir(tmp_path)
    original_summary_path = original_dir / "agentic_run_summary.json"
    original_summary = json.loads(original_summary_path.read_text(encoding="utf-8"))
    original_summary["final_state_digest"] = "sha256:state-1"
    original_summary_path.write_text(json.dumps(original_summary, indent=2), encoding="utf-8")

    resumed_dir = tmp_path / "run-1-resumed"
    resumed_dir.mkdir(parents=True)
    resumed_summary = {"run_id": "run-pass-1-resumed", "final_state_digest": "sha256:state-2"}
    (resumed_dir / "agentic_run_summary.json").write_text(
        json.dumps(resumed_summary, indent=2), encoding="utf-8"
    )

    report = check_r8_acceptance_from_run_dir(original_dir, resumed_run_dir=resumed_dir)
    assert report.criteria["checkpoint_resume_consistent"].status == "failed"


# ---------------------------------------------------------------------------
# Top-level accepted flag
# ---------------------------------------------------------------------------


def test_accepted_is_false_when_any_criterion_fails():
    kwargs = _passing_report_kwargs()
    kwargs["validation_report"] = _validation_report(unsupported=1, supported=1)
    report = check_r8_acceptance(**kwargs)
    assert report.accepted is False


def test_accepted_is_false_when_protocol_check_fails():
    kwargs = _passing_report_kwargs()
    kwargs["run_environment"] = {
        "CODE2PAPER_LLM_CACHE": "1",
        "CODE2PAPER_TP_SIZE": "2",
        "CODE2PAPER_NUM_GPUS": "2",
    }
    report = check_r8_acceptance(**kwargs)
    assert report.accepted is False


def test_accepted_is_false_when_criteria_skipped():
    """Skipped criteria (trace / checkpoint with no digests) block
    acceptance under the tightened R8 checker: an acceptance run must
    positively evidence every criterion, not rely on absence."""

    kwargs = _passing_report_kwargs()
    # Drop the digests so trace_reproducible and checkpoint_resume_consistent
    # become "skipped".
    kwargs["recorded_trace_digest"] = ""
    kwargs["original_final_state_digest"] = ""
    kwargs["resumed_final_state_digest"] = ""
    report = check_r8_acceptance(**kwargs)
    assert report.accepted is False
    assert report.criteria["trace_reproducible"].status == "skipped"
    assert report.criteria["checkpoint_resume_consistent"].status == "skipped"


# ---------------------------------------------------------------------------
# Project-agnostic source constraint
# ---------------------------------------------------------------------------


def test_r8_acceptance_source_has_no_project_literals():
    """The R8 acceptance module source MUST NOT contain project-specific
    literals (R8.1 hard constraint).

    Tests deliberately reference forbidden literals to verify detection,
    so this constraint applies only to the production module, not to
    the test file.
    """

    source_path = Path(__file__).resolve().parent.parent / "src" / "code2paper" / "agentic" / "r8_acceptance.py"
    source_text = source_path.read_text(encoding="utf-8")
    matches = scan_text_for_project_literals(source_text)
    project_names = {"rap", "ebcar", "dyg-mamba", "dyg_mamba", "dygmamba", "linear rag", "linearrag", "linear_rag"}
    forbidden = [m for m in matches if m in project_names]
    assert not forbidden, f"r8_acceptance.py source contains project literals: {forbidden}"
