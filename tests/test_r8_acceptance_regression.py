"""R8 acceptance regression tests for the Bootstrapping failure scenario.

Reproduces the exact artifact state from the Bootstrapping rejection:
0 claims, 0 evidence, 6 synthetic gaps, Method text only "# Method",
and asserts that code_mainline_in_method=failed and accepted=false.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from code2paper.agentic.r8_acceptance import (
    R8AcceptanceReport,
    _check_code_mainline_in_method,
    check_r8_acceptance,
    check_r8_acceptance_from_run_dir,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    ExplicitCodeGapV1,
)
from code2paper.agentic.trust_contracts import (
    TextEvidenceValidationReport,
    TextClaimEvidenceVerdict,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_bootstrapping_coverage_report() -> ObligationCoverageReportV2:
    """Build a coverage report matching the Bootstrapping failure:
    6 must_cover obligations, all explicit_gap, 0 supported/partial.
    """
    items = [
        ObligationAlignmentV1(
            obligation_id=f"obl_boot_{i:02d}",
            obligation_kind="implementation_behavior",
            obligation_priority="must_cover",
            coverage_status="explicit_gap",
            rationale="Research loop terminated before gap_finalizer accepted",
        )
        for i in range(1, 7)
    ]
    return ObligationCoverageReportV2(
        intent_graph_digest="test_bootstrapping",
        items=items,
        must_cover_count=6,
        terminal_must_cover_count=6,
        supported_must_cover_count=0,
        unresolved_must_cover_ids=[],
        explicit_gap_count=6,
    )


def _make_bootstrapping_claim_set() -> AtomicClaimSetV3:
    """Build a claim set with 0 factual claims and 6 synthetic gaps."""
    gaps = [
        ExplicitCodeGapV1(
            gap_id=f"gap:synthetic:obl_boot_{i:02d}",
            topic=f"Synthetic gap for obl_boot_{i:02d}",
            scope="any",
            rationale="Synthesized terminal gap",
            source_kind="author_obligation",
        )
        for i in range(1, 7)
    ]
    return AtomicClaimSetV3(
        repo_snapshot_id="test_snapshot",
        project_tree_hash="test_hash",
        evidence_packet_digest="test_ep_digest",
        code_fact_digest="test_cf_digest",
        claims=[],
        explicit_code_gaps=gaps,
        content_digest="test_claim_digest",
    )


def _make_bootstrapping_validation_report() -> TextEvidenceValidationReport:
    """Build a validation report with 0 supported/caveated claims."""
    return TextEvidenceValidationReport(
        status="passed",
        input_text_digest="test_input_digest",
        projection_digest="test_projection_digest",
        checked_factual_claims=0,
        supported_claims=0,
        caveated_claims=0,
        unsupported_claims=0,
        unverified_claims=0,
        semantic_verifier_calls=0,
        verdicts=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCodeMainlineInMethodRejectsEmptyMethod:
    """Regression: code_mainline_in_method must reject a Method with only
    a title and all explicit_gap must_cover obligations."""

    def test_empty_method_only_title_rejected(self):
        """Method text is only '# Method' — must fail."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()
        method_text = "# Method\n"

        ok, reason = _check_code_mainline_in_method(
            coverage, claims, validation, method_text
        )
        assert not ok, f"Expected failure, got ok=True with reason={reason}"
        assert "no factual units" in reason.lower() or "heading" in reason.lower(), (
            f"Reason should mention factual units or heading, got: {reason}"
        )

    def test_method_with_content_but_no_supported_claims_rejected(self):
        """Method has content but no supported claims cover must_cover."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()
        method_text = (
            "# Method\n\n"
            "This section describes the approach.\n\n"
            "The method uses a novel technique.\n"
        )

        ok, reason = _check_code_mainline_in_method(
            coverage, claims, validation, method_text
        )
        assert not ok, (
            f"Expected failure because no supported claim covers must_cover, "
            f"got ok=True with reason={reason}"
        )
        assert "no supported claim" in reason.lower(), (
            f"Reason should mention no supported claim, got: {reason}"
        )

    def test_all_explicit_gap_not_accepted_as_pass(self):
        """Regression: the removed explicit_gap bypass must NOT return True
        when all must_cover are explicit_gap."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()
        method_text = (
            "# Method\n\n"
            "The codebase does not implement the required behaviors.\n\n"
            "## Gap Analysis\n\n"
            "All must-cover obligations are explicit gaps.\n"
        )

        ok, reason = _check_code_mainline_in_method(
            coverage, claims, validation, method_text
        )
        assert not ok, (
            f"explicit_gap bypass must NOT return True; "
            f"got ok=True with reason={reason}"
        )


class TestCheckR8AcceptanceRejectsBootstrapping:
    """Regression: check_r8_acceptance must return accepted=false for the
    Bootstrapping scenario."""

    def test_full_acceptance_rejected(self):
        """Full acceptance check rejects the Bootstrapping artifacts."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()
        method_text = "# Method\n"

        report = check_r8_acceptance(
            run_id="test_bootstrapping",
            project_id="bootstrapping",
            coverage_report=coverage,
            claim_set=claims,
            validation_report=validation,
            method_text=method_text,
        )

        assert isinstance(report, R8AcceptanceReport)
        assert report.accepted is False, (
            f"Expected accepted=false, got accepted=true"
        )
        assert report.criteria["code_mainline_in_method"].status == "failed", (
            f"code_mainline_in_method should be failed, got "
            f"{report.criteria['code_mainline_in_method'].status}"
        )

    def test_code_mainline_criterion_failed(self):
        """code_mainline_in_method criterion is explicitly failed."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()
        method_text = "# Method\n"

        report = check_r8_acceptance(
            run_id="test_bootstrapping",
            project_id="bootstrapping",
            coverage_report=coverage,
            claim_set=claims,
            validation_report=validation,
            method_text=method_text,
        )

        criterion = report.criteria["code_mainline_in_method"]
        assert criterion.status == "failed", (
            f"code_mainline_in_method status={criterion.status}, reason={criterion.reason}"
        )
        assert "no factual units" in criterion.reason.lower() or "no supported claim" in criterion.reason.lower(), (
            f"Reason should indicate the failure, got: {criterion.reason}"
        )

    def test_completion_criterion_failed_when_no_report(self):
        """completion_complete is failed when no completion report is provided."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()

        report = check_r8_acceptance(
            run_id="test_bootstrapping",
            project_id="bootstrapping",
            coverage_report=coverage,
            claim_set=claims,
            validation_report=validation,
            method_text="# Method\n",
        )

        assert report.criteria["completion_complete"].status == "failed"
        assert "not found" in report.criteria["completion_complete"].reason.lower()

    def test_readiness_criterion_failed_when_no_report(self):
        """readiness_passed is failed when no readiness report is provided."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()

        report = check_r8_acceptance(
            run_id="test_bootstrapping",
            project_id="bootstrapping",
            coverage_report=coverage,
            claim_set=claims,
            validation_report=validation,
            method_text="# Method\n",
        )

        assert report.criteria["readiness_passed"].status == "failed"
        assert "not found" in report.criteria["readiness_passed"].reason.lower()

    def test_method_has_supported_mainline_failed(self):
        """method_has_supported_mainline is failed when count is 0."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()

        report = check_r8_acceptance(
            run_id="test_bootstrapping",
            project_id="bootstrapping",
            coverage_report=coverage,
            claim_set=claims,
            validation_report=validation,
            method_text="# Method\n",
        )

        assert report.criteria["method_has_supported_mainline"].status == "failed"
        assert "0" in report.criteria["method_has_supported_mainline"].reason


class TestSyntheticGapOnlyAcceptedGaps:
    """Regression: _synthesize_terminal_gaps must only synthesize for
    already-accepted explicit_gap, not for pending/in_progress/blocked."""

    @staticmethod
    def _make_minimal_runtime(status: str, obligation_id: str):
        """Build a minimal runtime with one agenda item."""
        from code2paper.agentic.research_models import (
            GapRequirementV1,
            ResearchAgendaItemV1,
            ResearchAgendaV1,
        )

        gap_reqs = (
            [GapRequirementV1(requirement_id="gap_req_01", description="test gap")]
            if status == "explicit_gap"
            else []
        )
        item = ResearchAgendaItemV1(
            obligation_id=obligation_id,
            priority="must_cover",
            status=status,  # type: ignore[arg-type]
            typed_behavior_targets=[],
            gap_requirements=gap_reqs,
        )
        agenda = ResearchAgendaV1(
            run_id="test_run",
            repo_snapshot_id="test_snapshot",
            project_tree_hash="test_hash",
            items=[item],
        )
        # Use a dataclass-like object instead of full ResearchGraphRuntime
        # to avoid all the required fields.
        from dataclasses import dataclass

        @dataclass
        class MinimalRuntime:
            agenda: ResearchAgendaV1

        return MinimalRuntime(agenda=agenda)

    def test_pending_not_synthesized_to_explicit_gap(self):
        """pending obligations are NOT converted to explicit_gap."""
        from code2paper.agentic.v3_runtime import _synthesize_terminal_gaps

        runtime = self._make_minimal_runtime("pending", "obl_pending_01")
        gaps, bindings = _synthesize_terminal_gaps(runtime)  # type: ignore[arg-type]
        assert len(gaps) == 0, (
            f"pending obligation should not be synthesized, got {len(gaps)} gaps"
        )

    def test_in_progress_not_synthesized_to_explicit_gap(self):
        """in_progress obligations are NOT converted to explicit_gap."""
        from code2paper.agentic.v3_runtime import _synthesize_terminal_gaps

        runtime = self._make_minimal_runtime("in_progress", "obl_in_progress_01")
        gaps, bindings = _synthesize_terminal_gaps(runtime)  # type: ignore[arg-type]
        assert len(gaps) == 0, (
            f"in_progress obligation should not be synthesized, got {len(gaps)} gaps"
        )

    def test_blocked_not_synthesized_to_explicit_gap(self):
        """blocked obligations are NOT converted to explicit_gap."""
        from code2paper.agentic.v3_runtime import _synthesize_terminal_gaps

        runtime = self._make_minimal_runtime("blocked", "obl_blocked_01")
        gaps, bindings = _synthesize_terminal_gaps(runtime)  # type: ignore[arg-type]
        assert len(gaps) == 0, (
            f"blocked obligation should not be synthesized, got {len(gaps)} gaps"
        )

    def test_explicit_gap_is_synthesized(self):
        """explicit_gap obligations ARE synthesized into gap objects."""
        from code2paper.agentic.v3_runtime import _synthesize_terminal_gaps

        runtime = self._make_minimal_runtime("explicit_gap", "obl_gap_01")
        gaps, bindings = _synthesize_terminal_gaps(runtime)  # type: ignore[arg-type]
        assert len(gaps) == 1, (
            f"explicit_gap obligation should be synthesized, got {len(gaps)} gaps"
        )
        assert gaps[0].gap_id == "gap:synthetic:obl_gap_01"
        assert "obl_gap_01" in bindings.get(gaps[0].gap_id, [])


class TestCheckR8AcceptanceFromRunDir:
    """Integration: check_r8_acceptance_from_run_dir with minimal artifacts."""

    def test_from_run_dir_rejects_bootstrapping(self):
        """Create a minimal run directory with Bootstrapping artifacts
        and verify acceptance is rejected."""
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            artifacts_dir = run_dir / "artifacts" / "10_run"
            artifacts_dir.mkdir(parents=True)

            # Write method_clean.md with only "# Method".
            method_clean = artifacts_dir / "method_clean.md"
            method_clean.write_text("# Method\n", encoding="utf-8")

            # Write the summary.
            summary = {
                "run_id": "test_bootstrapping",
                "artifacts": {
                    "text_clean_md": str(method_clean),
                },
            }
            summary_path = artifacts_dir / "agentic_run_summary.json"
            summary_path.write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # The check should fail because coverage_report and claim_set
            # are missing (code_mainline_in_method returns False).
            report = check_r8_acceptance_from_run_dir(
                run_dir,
                project_id="bootstrapping",
            )

            assert report.accepted is False, (
                f"Expected accepted=false for bootstrapping scenario, "
                f"got accepted=true"
            )


class TestMethodFactualUnitCheck:
    """Verify that the method factual unit check correctly rejects
    empty or title-only Methods."""

    @pytest.mark.parametrize("method_text,expected_ok", [
        ("", False),
        ("# Method\n", False),
        ("# Method\n\n", False),
        ("## Overview\n", False),
        ("# Method\n\nSome content here.\n", True),
        ("# Method\n\n## Section\n\nContent.\n", True),
    ])
    def test_method_content_detection(self, method_text, expected_ok):
        """Verify that the factual unit check works correctly."""
        coverage = _make_bootstrapping_coverage_report()
        claims = _make_bootstrapping_claim_set()
        validation = _make_bootstrapping_validation_report()

        # For the "has content" cases, we expect failure due to no supported
        # claims (not due to factual unit check).
        # For the "no content" cases, we expect failure due to factual unit check.
        ok, reason = _check_code_mainline_in_method(
            coverage, claims, validation, method_text
        )
        if not method_text.strip() or all(
            line.strip().startswith("#") or not line.strip()
            for line in method_text.strip().splitlines()
        ):
            # Should fail due to factual unit check.
            assert not ok, f"Empty/title-only method should fail: {reason}"
            assert "factual" in reason.lower() or "heading" in reason.lower(), (
                f"Reason should mention factual/heading: {reason}"
            )
        else:
            # Should fail due to no supported claims (not factual unit).
            assert not ok, f"Should fail due to no supported claims: {reason}"
            assert "no supported claim" in reason.lower(), (
                f"Reason should mention no supported claim: {reason}"
            )