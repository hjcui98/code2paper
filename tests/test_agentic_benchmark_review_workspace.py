from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from code2paper.agentic.benchmark_review_workspace import (
    materialize_review_workspace,
    validate_review_workspace,
)
from code2paper.agentic.benchmark_v2 import BenchmarkObservationV2
from code2paper.cli.agentic_benchmark_review_workspace import main as workspace_main


IDENTITY = ("toy_train", "fixed_legacy", "", 1)


def _template() -> dict:
    return {
        "schema_version": "2.0",
        "case_id": IDENTITY[0],
        "variant": IDENTITY[1],
        "repeat_index": IDENTITY[3],
        "intent_id": IDENTITY[2],
        "scope": "full_pipeline",
        "run_summary_path": "/tmp/frozen-run-summary.json",
        "run_summary_digest": "sha256:" + "1" * 64,
        "protocol_spec_digest": "sha256:" + "2" * 64,
        "repo_snapshot_id": "repo:test",
        "model_id": "gemma4-31b-nvfp4",
        "capability_profile_digest": "sha256:" + "3" * 64,
        "reviewer": "__REQUIRED_NAMED_HUMAN__",
        "reviewed_at": "__REQUIRED_ISO8601__",
        "blocked_reason_review": "",
        "claims": [],
        "figures": [],
        "mutation_trials": [],
        "expected_retrieval_targets_observed": [],
        "section_claim_order": [],
        "figure_claim_ids": [],
        "usable_completion": False,
        "latency_seconds": 1.5,
    }


def _queue() -> dict:
    return {
        "schema_version": "2.0",
        "protocol_commit": "commit:test",
        "entry_count": 1,
        "ready_for_cutover": False,
        "blocking_reason": "named_human_reviews_not_completed",
        "entries": [{
            "identity": list(IDENTITY),
            "status": "human_review_required",
            "review_template": _template(),
            "gold_claims": [{
                "claim_id": "T1",
                "text": "A directly grounded claim.",
                "direct_evidence_ids": ["E1"],
                "required_qualifiers": [],
                "high_risk": False,
            }],
            "gold_figure_relations": [],
            "legacy_v2_audit_path": "/tmp/legacy-audit.json",
            "legacy_v2_audit_digest": "sha256:" + "4" * 64,
            "review_instructions": ["Compare semantics before assigning T1."],
        }],
    }


def _write_queue(tmp_path: Path) -> Path:
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(_queue()), encoding="utf-8")
    return path


def _protocol():
    return SimpleNamespace(
        workspace_commit="commit:test",
        specs=[SimpleNamespace(
            case_id=IDENTITY[0], variant=IDENTITY[1], intent_id=IDENTITY[2], repeat_index=IDENTITY[3],
        )],
    )


def _dataset():
    return SimpleNamespace(cases=[SimpleNamespace(case_id=IDENTITY[0])])


def _review_path(workspace: Path) -> Path:
    return next((workspace / "reviews").glob("*.json"))


def _completed_review(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update({"reviewer": "Ada Reviewer", "reviewed_at": "2026-07-18T12:00:00+08:00"})
    path.write_text(json.dumps(payload), encoding="utf-8")


def _observation() -> BenchmarkObservationV2:
    return BenchmarkObservationV2(
        case_id=IDENTITY[0],
        variant=IDENTITY[1],
        repeat_index=IDENTITY[3],
        intent_id=IDENTITY[2],
        scope="full_pipeline",
        run_status="success",
    )


def test_materialize_creates_one_non_overwriting_review_and_context(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"

    manifest_path = materialize_review_workspace(queue, workspace)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads(_review_path(workspace).read_text(encoding="utf-8"))
    context = next((workspace / "contexts").glob("*.md")).read_text(encoding="utf-8")

    assert manifest["expected_reviews"] == 1
    assert manifest["status"] == "human_review_required"
    assert review["reviewer"] == "__REQUIRED_NAMED_HUMAN__"
    assert "A directly grounded claim" in context
    assert "paper reference is not evidence" in context
    with pytest.raises(FileExistsError, match="not empty"):
        materialize_review_workspace(queue, workspace)


def test_materialize_rejects_duplicate_or_missing_run_records(tmp_path: Path) -> None:
    queue = _queue()
    queue["entries"].append(queue["entries"][0])
    queue["entry_count"] = 2
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(json.dumps(queue), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate identities"):
        materialize_review_workspace(duplicate, tmp_path / "duplicate-workspace")

    queue = _queue()
    queue["entries"][0]["status"] = "run_record_missing"
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(queue), encoding="utf-8")
    with pytest.raises(ValueError, match="ready for human review"):
        materialize_review_workspace(missing, tmp_path / "missing-workspace")

    queue = _queue()
    queue["entries"][0]["review_template"]["case_id"] = "different-case"
    mismatch = tmp_path / "mismatch.json"
    mismatch.write_text(json.dumps(queue), encoding="utf-8")
    with pytest.raises(ValueError, match="identity contradicts template"):
        materialize_review_workspace(mismatch, tmp_path / "mismatch-workspace")


def test_validate_reports_placeholders_as_pending_without_emitting_observations(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)

    report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "pending_human_review"
    assert report["pending_review_count"] == 1
    assert report["invalid_review_count"] == 0
    assert not report["hard_gate_passed"]
    assert observations == []


def test_validate_extracts_only_complete_immutable_reviews(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    _completed_review(_review_path(workspace))

    with (
        patch(
            "code2paper.agentic.benchmark_review_workspace.extract_benchmark_observation_v2",
            return_value=_observation(),
        ) as extract,
        patch(
            "code2paper.agentic.benchmark_review_workspace.validate_protocol_observations_v2",
            return_value=[],
        ) as validate_protocol,
    ):
        report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "passed"
    assert report["validated_review_count"] == 1
    assert report["observations_emitted"]
    assert len(observations) == 1
    extract.assert_called_once()
    validate_protocol.assert_called_once()


def test_validate_rejects_immutable_binding_tamper_before_extraction(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)
    _completed_review(review_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["run_summary_digest"] = "sha256:" + "f" * 64
    review_path.write_text(json.dumps(payload), encoding="utf-8")

    with patch("code2paper.agentic.benchmark_review_workspace.extract_benchmark_observation_v2") as extract:
        report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "failed"
    assert "immutable_review_field_changed:run_summary_digest" in report["invalid_reviews"][0]["failures"]
    assert observations == []
    extract.assert_not_called()


def test_validate_rejects_queue_drift_and_review_path_escape(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    manifest_path = materialize_review_workspace(queue, workspace)
    changed_queue = json.loads(queue.read_text(encoding="utf-8"))
    changed_queue["blocking_reason"] = "changed-after-materialization"
    queue.write_text(json.dumps(changed_queue), encoding="utf-8")

    report, _ = validate_review_workspace(queue, workspace, _dataset(), _protocol())
    assert report["status"] == "failed"
    assert "review_queue_digest_drift" in report["global_failures"]

    queue.write_text(json.dumps(_queue()), encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["queue_digest"] = "sha256:" + __import__("hashlib").sha256(queue.read_bytes()).hexdigest()
    manifest["entries"][0]["review_path"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report, _ = validate_review_workspace(queue, workspace, _dataset(), _protocol())
    assert report["status"] == "failed"
    assert report["invalid_reviews"][0]["failures"] == ["review_path_escapes_workspace"]


def test_validate_reports_malformed_manifest_identity_instead_of_crashing(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    manifest_path = materialize_review_workspace(queue, workspace)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"][0]["identity"] = ["too", "short"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "failed"
    assert "workspace_manifest_contains_invalid_identity" in report["global_failures"]
    assert observations == []


def test_workspace_cli_materializes_review_files(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"

    exit_code = workspace_main(["materialize", "--queue", str(queue), "--out-root", str(workspace)])

    assert exit_code == 0
    assert (workspace / "review_workspace_manifest.json").is_file()
    assert len(list((workspace / "reviews").glob("*.json"))) == 1
