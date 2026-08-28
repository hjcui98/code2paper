from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.publication_replay_diagnostics import diagnose_publication_replay
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

    result = diagnose_publication_replay(tmp_path)

    assert result["artifact_presence"]["method_propositions_v1"] is True
    assert result["propositions"]["planned"] == 1
    assert result["propositions"]["validated"] == 1
    assert result["reverse_validation"]["failures_by_type"] == {
        "required_qualifier_missing": 1,
    }
    assert result["transactions"]["rewrite_applied"] == 1
    assert result["sections"][0]["writer_text"].endswith("Candidate.")
