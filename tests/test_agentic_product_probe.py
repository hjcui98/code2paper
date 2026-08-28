"""Plan 15.1.3: the maintained probe summarizer is deterministic and safe.

The one-off Round 7 snippets failed with ``str / Path`` TypeError.  The
maintained entry point converts every output-root value to ``Path`` once
at the command boundary, separates product execution from read-only
summarization, and never mutates candidate/verified/validation artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_agentic_product_probe import (
    summarize_run,
    write_probe_result,
)


def _make_run_root(tmp_path: Path) -> Path:
    root = tmp_path / "run"
    (root / "artifacts" / "research_product").mkdir(parents=True)
    (root / "artifacts" / "06_authoring").mkdir(parents=True)
    (root / "artifacts" / "07_validation").mkdir(parents=True)
    run_summary = {
        "run_id": "run-probe-test",
        "research": {
            "status": "degraded",
            "termination_reason": "all_obligations_terminal",
            "turns_executed": 7,
            "autonomous": False,
            "llm_decisions": 0,
            "deterministic_fallback_decisions": 4,
            "policy_fallback_decisions": 0,
            "degraded_reasons": ["llm_unavailable"],
        },
        "evidence": {
            "evidence_packets": 3,
            "verified_facts": 3,
            "supported_claims": 3,
            "typed_gaps": 0,
            "unresolved_obligations": 0,
            "synthetic_support_used": False,
        },
        "plan": {"plan_built": True, "readiness": "candidate_ready_with_review"},
    }
    (root / "artifacts" / "research_product" / "run_summary.json").write_text(
        json.dumps(run_summary), encoding="utf-8"
    )
    (root / "artifacts" / "06_authoring" / "publication_candidate_method.md").write_text(
        "## Encoder\n\nbody", encoding="utf-8"
    )
    (root / "artifacts" / "06_authoring" / "repository_verified_method.md").write_text(
        "## Encoder\n\nbody", encoding="utf-8"
    )
    (root / "artifacts" / "07_validation" / "agentic_text_evidence_validation.json").write_text(
        json.dumps({"status": "passed", "unsupported_claims": 0}), encoding="utf-8"
    )
    return root


def test_summarize_run_accepts_str_and_path_roots(tmp_path: Path) -> None:
    """Path composition must work for both str and Path roots (no / on str)."""
    root = _make_run_root(tmp_path)
    by_path = summarize_run(root)
    by_str = summarize_run(str(root))
    assert by_path == by_str
    assert by_path["run_id"] == "run-probe-test"
    assert by_path["research"]["termination_reason"] == "all_obligations_terminal"
    assert by_path["evidence"]["unresolved_obligations"] == 0
    assert by_path["missing_files"] == []
    assert by_path["artifacts"]["candidate_method"] == str(
        root / "artifacts" / "06_authoring" / "publication_candidate_method.md"
    )


def test_summarize_run_reports_missing_files_deterministically(
    tmp_path: Path,
) -> None:
    root = _make_run_root(tmp_path)
    (root / "artifacts" / "07_validation" / "agentic_text_evidence_validation.json").unlink(
        missing_ok=True
    )
    summary = summarize_run(root)
    missing = summary["missing_files"]
    assert len(missing) == 1
    assert missing[0].endswith("agentic_text_evidence_validation.json")
    assert summary["artifacts"]["text_evidence_validation"] is None
    # Deterministic: repeated calls return identical payloads.
    assert summarize_run(root) == summary


def test_summarizer_is_read_only(tmp_path: Path) -> None:
    root = _make_run_root(tmp_path)
    candidate = root / "artifacts" / "06_authoring" / "publication_candidate_method.md"
    verified = root / "artifacts" / "06_authoring" / "repository_verified_method.md"
    validation = (
        root / "artifacts" / "07_validation" / "agentic_text_evidence_validation.json"
    )
    validation.write_text(json.dumps({"status": "passed"}), encoding="utf-8")
    before = {
        path: path.read_bytes()
        for path in (candidate, verified, validation)
    }
    summarize_run(root)
    after = {
        path: path.read_bytes()
        for path in (candidate, verified, validation)
    }
    assert before == after


def test_write_probe_result_is_the_only_new_file(tmp_path: Path) -> None:
    root = _make_run_root(tmp_path)
    probe = write_probe_result(root, {"run_id": "run-probe-test"})
    assert probe == root / "probe_result.json"
    payload = json.loads(probe.read_text(encoding="utf-8"))
    assert payload == {"run_id": "run-probe-test"}
    # Only the probe file was added; the artifact set is unchanged.
    assert (root / "artifacts" / "06_authoring" / "publication_candidate_method.md").is_file()


def test_write_probe_result_never_overwrites_product_summary(tmp_path: Path) -> None:
    root = _make_run_root(tmp_path)
    run_summary = root / "artifacts" / "research_product" / "run_summary.json"
    original = run_summary.read_text(encoding="utf-8")
    write_probe_result(root, {"partial": True})
    assert run_summary.read_text(encoding="utf-8") == original
