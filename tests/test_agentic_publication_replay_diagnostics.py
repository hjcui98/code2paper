from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.publication_replay_diagnostics import (
    _formula_funnel,
    diagnose_publication_replay,
)
from code2paper.core.output_names import method_output


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_diagnostics_extracts_comparable_replay_record(tmp_path: Path) -> None:
    candidate = method_output(tmp_path, "publication_candidate_method")
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text("## Method\n\nCandidate.", encoding="utf-8")
    method_output(tmp_path, "repository_verified_method").write_text(
        "## Method\n\nVerified.", encoding="utf-8"
    )
    _write_json(method_output(tmp_path, "method_propositions_v1"), {
        "propositions": [{"proposition_id": "MP-1"}], "gaps": [],
    })
    _write_json(method_output(tmp_path, "method_proposition_alignment_v1"), {
        "semantic_alignment_calls": 1,
        "sections": [{
            "section_id": "MA-S1",
            "validated_proposition_ids": ["MP-1"],
            "missing_proposition_ids": [],
        }],
    })
    _write_json(method_output(tmp_path, "text_evidence_validation"), {
        "status": "failed", "supported_claims": 1, "unsupported_claims": 1,
        "verdicts": [{"deterministic_failures": ["required_qualifier_missing"]}],
    })
    _write_json(method_output(tmp_path, "publication_section_checkpoint_v1"), {
        "section_outputs": {"MA-S1": {
            "section_id": "MA-S1", "section_markdown": "## Method\n\nCandidate.",
            "rendered_proposition_ids": ["MP-1"],
        }},
    })
    _write_json(method_output(tmp_path, "publication_rewrite_transitions_v1"), {
        "transitions": [{"status": "applied"}, {"status": "rejected"}],
    })
    _write_json(method_output(tmp_path, "candidate_authority_validation_v1"), {
        "schema_version": "1.0",
        "candidate_text_digest": "sha256:candidate",
        "validation": {
            "status": "passed",
            "violations": [],
            "warnings": [],
            "internal_audit_term_count": 0,
        },
        "content_digest": "sha256:wrapper",
    })

    result = diagnose_publication_replay(tmp_path)

    assert result["artifact_presence"]["method_propositions_v1"] is True
    assert result["propositions"]["planned"] == 1
    assert result["propositions"]["validated"] == 1
    assert result["reverse_validation"]["failures_by_type"] == {
        "required_qualifier_missing": 1,
    }
    assert result["transactions"]["rewrite_applied"] == 1
    assert result["sections"][0]["writer_text"].endswith("Candidate.")
    assert result["candidate_surface"]["authority_status"] == "passed"


def test_diagnostics_counts_rejected_formula_attempts_from_call_trace(
    tmp_path: Path,
) -> None:
    _write_json(method_output(tmp_path, "formalization_section_results_v1"), {
        "schema_version": "1.0",
        "sections": [{
            "section_id": "MA-S3",
            "formula_obligations": [{
                "obligation_id": "formula:section:MA-S3:derivation",
                "consumer_paragraph_id": "paragraph:MA-S3:1",
                "expectation": "required",
            }],
            "packages": [],
        }],
        "formalizer_call_traces": [{
            "section_id": "MA-S3",
            "call_traces": [
                {
                    "attempt": 1,
                    "proposed_package_count": 1,
                    "accepted_package_count": 0,
                    "status": "guards_failed",
                    "guard_failures": [
                        "pkg:one:formula_package_consumer_route_ambiguous",
                    ],
                },
                {
                    "attempt": 2,
                    "proposed_package_count": 1,
                    "accepted_package_count": 0,
                    "status": "guards_failed",
                    "guard_failures": [
                        "pkg:two:formula_package_consumer_route_ambiguous",
                    ],
                },
            ],
        }],
    })

    result = diagnose_publication_replay(tmp_path)

    funnel = result["formula_funnel"]
    assert result["formula_route_ambiguous_packages"] == 2
    assert funnel["proposed_packages"] == 2
    assert funnel["rejected_packages"] == 2
    assert funnel["route_ambiguous_failures"] == 2
    assert funnel["rejected_reason_counts"] == {
        "pkg:one:formula_package_consumer_route_ambiguous": 1,
        "pkg:two:formula_package_consumer_route_ambiguous": 1,
    }


def test_diagnostics_keeps_consumer_first_acceptance_counters_isolated(
    tmp_path: Path,
) -> None:
    _write_json(method_output(tmp_path, "formalization_section_results_v1"), {
        "schema_version": "1.0",
        "sections": [{"section_id": "MA-S3", "packages": []}],
        "formalizer_call_traces": [{
            "section_id": "MA-S3",
            "call_traces": [
                {
                    "attempt": 1,
                    "consumer_paragraph_id": "paragraph:MA-S3:1",
                    "proposed_package_count": 1,
                    "accepted_package_count": 1,
                    "status": "accepted",
                },
                {
                    "attempt": 1,
                    "consumer_paragraph_id": "paragraph:MA-S3:2",
                    "proposed_package_count": 1,
                    "accepted_package_count": 1,
                    "status": "accepted",
                },
            ],
        }],
    })

    funnel = diagnose_publication_replay(tmp_path)["formula_funnel"]

    assert funnel["proposed_packages"] == 2
    assert funnel["accepted_trace_packages"] == 2
    assert funnel["rejected_packages"] == 0


def test_diagnostics_does_not_count_invalid_declared_formula_as_consumed(
    tmp_path: Path,
) -> None:
    _write_json(method_output(tmp_path, "formalization_section_results_v1"), {
        "sections": [{
            "section_id": "MA-S3",
            "packages": [{
                "package_id": "pkg-ma-s3-01",
                "review_status": "accepted",
                "authority_status": "code_verified",
                "formula_lane": "repository_derived",
                "markdown_block": "$$x = y$$",
            }],
        }],
    })
    _write_json(method_output(tmp_path, "publication_paragraph_transaction_assessments_v1"), {
        "assessments": [{
            "section_id": "MA-S3",
            "paragraph_id": "paragraph:MA-S3:1",
            "valid": False,
            "declared_by_kind": {"formula": ["pkg-ma-s3-01"]},
            "witnessed_by_kind": {"formula": []},
        }],
    })
    _write_json(method_output(tmp_path, "method_content_trace_v1"), {
        "rows": [{
            "section_id": "MA-S3",
            "paragraph_id": "paragraph:MA-S3:1",
            "terminal_state": "rendered_invalid",
            "accepted_formula_package_ids": ["pkg-ma-s3-01"],
        }],
    })

    funnel = diagnose_publication_replay(tmp_path)["formula_funnel"]

    assert funnel["accepted_packages"] == 1
    assert funnel["consumed_packages"] == 0
    assert funnel["exact_body_validated_packages"] == 0


def test_diagnostics_does_not_promote_author_intent_package_to_accepted(
    tmp_path: Path,
) -> None:
    _write_json(method_output(tmp_path, "formalization_section_results_v1"), {
        "sections": [{
            "section_id": "MA-S1",
            "packages": [{
                "package_id": "pkg-intent-1",
                "review_status": "accepted",
                "authority_status": "author_intent",
                "formula_lane": "author_intent_academic",
                "markdown_block": "$$x = y$$",
            }],
        }],
    })

    funnel = diagnose_publication_replay(tmp_path)["formula_funnel"]

    assert funnel["accepted_packages"] == 0
    assert funnel["consumed_packages"] == 0


def test_formula_exact_body_is_scoped_to_unique_consumer_paragraph() -> None:
    block = "$$x = y$$"
    packages = [
        {
            "package_id": "pkg-owner-1",
            "consumer_paragraph_id": "paragraph:one",
            "markdown_block": block,
        },
        {
            "package_id": "pkg-owner-2",
            "consumer_paragraph_id": "paragraph:two",
            "markdown_block": block,
        },
    ]

    funnel = _formula_funnel(
        formalization_rows=(),
        formalizer_rows=(),
        package_items=packages,
        transaction_rows=(
            {
                "paragraph_id": "paragraph:one",
                "paragraph_markdown": f"Owner one. {block}",
            },
            {
                "paragraph_id": "paragraph:two",
                "paragraph_markdown": "Owner two. $x = y$.",
            },
        ),
        sections=(),
        accepted_package_ids={"pkg-owner-1", "pkg-owner-2"},
        consumed_package_ids={"pkg-owner-1", "pkg-owner-2"},
        candidate_text=block,
    )

    assert funnel["exact_body_validated_packages"] == 1
    assert funnel["exact_body_validated_package_ids"] == ["pkg-owner-1"]
