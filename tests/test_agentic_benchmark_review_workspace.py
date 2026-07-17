from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from code2paper.agentic.benchmark_review_workspace import (
    _review_context,
    materialize_review_workspace,
    record_claim_adjudication,
    record_figure_adjudication,
    record_run_adjudication,
    review_workspace_progress,
    sign_review,
    validate_review_workspace,
)
from code2paper.agentic.benchmark_observation import build_figure_review_inventory
from code2paper.agentic.benchmark_review_queue import _agentic_claim_templates, _agentic_figure_templates
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
        "intent_fields_reviewed": True,
        "usable_completion": False,
        "latency_seconds": 1.5,
    }


def _queue() -> dict:
    return {
        "schema_version": "2.0",
        "protocol_commit": "commit:test",
        "gold_digest": "sha256:" + "6" * 64,
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
            "gold_evidence_spans": [{
                "evidence_id": "E1",
                "path": "train.py",
                "line_start": 1,
                "line_end": 2,
                "exact_excerpt_digest": "sha256:" + "5" * 64,
            }],
            "gold_repo_root": "/tmp/frozen-toy-train",
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


def _bind_run_summary(queue: dict, tmp_path: Path, *, status: str = "success") -> Path:
    path = tmp_path / "frozen-run-summary.json"
    path.write_text(json.dumps({"status": status}), encoding="utf-8")
    template = queue["entries"][0]["review_template"]
    template["run_summary_path"] = str(path)
    template["run_summary_digest"] = "sha256:" + __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    return path


def _protocol():
    return SimpleNamespace(
        workspace_commit="commit:test",
        gold_digest="sha256:" + "6" * 64,
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
    assert manifest["entries"][0]["context_digest"].startswith("sha256:")
    assert review["reviewer"] == "__REQUIRED_NAMED_HUMAN__"
    assert "A directly grounded claim" in context
    assert "Gold code evidence spans" in context
    assert '"path": "train.py"' in context
    assert "/tmp/frozen-toy-train" in context
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

    queue = _queue()
    queue["entries"][0]["gold_evidence_spans"] = []
    missing_gold = tmp_path / "missing-gold-evidence.json"
    missing_gold.write_text(json.dumps(queue), encoding="utf-8")
    with pytest.raises(ValueError, match="references missing code evidence spans"):
        materialize_review_workspace(missing_gold, tmp_path / "missing-gold-workspace")


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


def test_validate_rejects_context_or_template_drift_before_human_review(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    manifest_path = materialize_review_workspace(queue, workspace)
    context_path = next((workspace / "contexts").glob("*.md"))
    context_path.write_text("tampered reviewer context", encoding="utf-8")

    report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "failed"
    assert "review_context_content_drift" in report["invalid_reviews"][0]["failures"]
    assert observations == []

    context_path.write_text(
        _review_context(_queue()["entries"][0]),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"][0]["template_digest"] = "sha256:" + "f" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report, _ = validate_review_workspace(queue, workspace, _dataset(), _protocol())
    assert "workspace_template_digest_mismatch" in report["invalid_reviews"][0]["failures"]


def test_validate_rejects_legacy_claim_inventory_deletion_while_review_is_pending(tmp_path: Path) -> None:
    queue_payload = _queue()
    queue_payload["entries"][0]["review_template"]["claims"] = [{
        "atomic_claim_id": "FAC1",
        "text": "Frozen legacy sentence.",
        "verdict": "unsupported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    queue = tmp_path / "legacy-queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["claims"] = []
    review_path.write_text(json.dumps(review), encoding="utf-8")

    report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "failed"
    assert "claim_inventory_or_validator_verdict_changed" in report["invalid_reviews"][0]["failures"]
    assert observations == []


def test_validate_keeps_unresolved_semantic_decisions_pending(tmp_path: Path) -> None:
    queue_payload = _queue()
    template = queue_payload["entries"][0]["review_template"]
    template["claims"] = [{
        "atomic_claim_id": "FAC1",
        "text": "Frozen legacy sentence.",
        "verdict": "unsupported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    template["usable_completion"] = None
    queue = tmp_path / "pending-decisions-queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    _completed_review(_review_path(workspace))

    report, observations = validate_review_workspace(queue, workspace, _dataset(), _protocol())

    assert report["status"] == "pending_human_review"
    assert report["pending_review_count"] == 1
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


def test_validate_rejects_gold_digest_not_bound_to_protocol(tmp_path: Path) -> None:
    queue = _write_queue(tmp_path)
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)

    protocol = _protocol()
    protocol.gold_digest = "sha256:" + "7" * 64
    report, observations = validate_review_workspace(queue, workspace, _dataset(), protocol)

    assert report["status"] == "failed"
    assert "review_queue_gold_digest_mismatch" in report["global_failures"]
    assert "workspace_gold_digest_mismatch" in report["global_failures"]
    assert observations == []


def test_review_progress_and_safe_claim_run_signing_workflow(tmp_path: Path) -> None:
    queue_payload = _queue()
    _bind_run_summary(queue_payload, tmp_path)
    template = queue_payload["entries"][0]["review_template"]
    template["claims"] = [{
        "atomic_claim_id": "FAC1",
        "text": "A directly grounded claim.",
        "verdict": "supported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    template["mutation_trials"] = [{
        "mutation_id": "TM1",
        "detected": True,
        "trial_artifact_path": "/tmp/tm1.json",
        "trial_artifact_digest": "sha256:" + "8" * 64,
    }]
    template["usable_completion"] = None
    template["intent_fields_reviewed"] = None
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)

    progress = review_workspace_progress(workspace)
    assert progress["reviews"] == 1
    assert progress["claims_pending"] == 1
    assert progress["run_decisions_pending"] == 1
    assert progress["reviews_pending"] == 1
    assert not progress["review_progress"][0]["ready_to_sign"]

    with pytest.raises(ValueError, match="decisions are incomplete"):
        sign_review(
            workspace,
            review_path.name,
            reviewer="Ada Reviewer",
            reviewed_at="2026-07-18T12:00:00+08:00",
        )

    record_claim_adjudication(
        workspace,
        review_path.name,
        "FAC1",
        semantic_match="matched",
        gold_claim_id="T1",
        mutation_match="no_match",
        mutation_id="",
        direct_evidence_support=True,
        qualifiers_preserved=True,
    )
    record_run_adjudication(
        workspace,
        review_path.name,
        usable_completion=True,
        intent_fields_reviewed=True,
    )
    progress = review_workspace_progress(workspace)
    assert progress["claims_pending"] == 0
    assert progress["run_decisions_pending"] == 0
    assert progress["review_progress"][0]["ready_to_sign"]

    sign_review(
        workspace,
        review_path.name,
        reviewer="Ada Reviewer",
        reviewed_at="2026-07-18T12:00:00+08:00",
    )
    signed = json.loads(review_path.read_text(encoding="utf-8"))
    assert signed["claims"][0]["gold_claim_id"] == "T1"
    assert signed["reviewer"] == "Ada Reviewer"
    assert review_workspace_progress(workspace)["signed_reviews"] == 1
    with pytest.raises(ValueError, match="signed review is immutable"):
        record_run_adjudication(
            workspace,
            review_path.name,
            usable_completion=False,
            intent_fields_reviewed=True,
        )


def test_safe_review_edits_reject_unknown_ids_drift_and_non_manifest_paths(tmp_path: Path) -> None:
    queue_payload = _queue()
    queue_payload["entries"][0]["review_template"]["claims"] = [{
        "atomic_claim_id": "FAC1",
        "text": "A directly grounded claim.",
        "verdict": "supported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)

    with pytest.raises(ValueError, match="unknown semantic match id"):
        record_claim_adjudication(
            workspace,
            review_path.name,
            "FAC1",
            semantic_match="matched",
            gold_claim_id="UNKNOWN",
            mutation_match="no_match",
            mutation_id="",
            direct_evidence_support=False,
            qualifiers_preserved=False,
        )
    with pytest.raises(ValueError, match="must not retain an id"):
        record_claim_adjudication(
            workspace,
            review_path.name,
            "FAC1",
            semantic_match="no_match",
            gold_claim_id="T1",
            mutation_match="no_match",
            mutation_id="",
            direct_evidence_support=False,
            qualifiers_preserved=False,
        )
    with pytest.raises(ValueError, match="selector must match exactly one"):
        record_run_adjudication(
            workspace,
            "../../outside.json",
            usable_completion=False,
            intent_fields_reviewed=False,
        )
    tampered = json.loads(review_path.read_text(encoding="utf-8"))
    tampered["run_summary_digest"] = "sha256:" + "f" * 64
    review_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="immutable binding drift"):
        review_workspace_progress(workspace)


def test_safe_figure_edit_requires_known_direct_relation(tmp_path: Path) -> None:
    queue_payload = _queue()
    entry = queue_payload["entries"][0]
    entry["gold_figure_relations"] = [{"relation_id": "R1"}]
    entry["review_template"]["figures"] = [{
        "element_id": "edge-1",
        "element_kind": "edge",
        "label": "",
        "scene_element_digest": "sha256:" + "9" * 64,
        "scene_relation_id": "scene-R1",
        "gold_claim_id": "",
        "relation_id": "",
        "semantically_supported": None,
        "direct_relation_evidence": None,
        "rendered_drift": None,
    }]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)

    with pytest.raises(ValueError, match="requires a gold relation id"):
        record_figure_adjudication(
            workspace,
            review_path.name,
            "edge-1",
            gold_claim_id="",
            relation_id="",
            semantically_supported=True,
            direct_relation_evidence=True,
            rendered_drift=False,
        )
    record_figure_adjudication(
        workspace,
        review_path.name,
        "edge-1",
        gold_claim_id="T1",
        relation_id="R1",
        semantically_supported=True,
        direct_relation_evidence=True,
        rendered_drift=False,
    )
    progress = review_workspace_progress(workspace)
    assert progress["figures_pending"] == 0


def test_review_workspace_cli_exposes_progress_and_strict_boolean_updates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    queue_payload = _queue()
    _bind_run_summary(queue_payload, tmp_path)
    queue_payload["entries"][0]["review_template"]["usable_completion"] = None
    queue_payload["entries"][0]["review_template"]["intent_fields_reviewed"] = None
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_name = _review_path(workspace).name

    assert workspace_main(["progress", "--workspace", str(workspace)]) == 0
    progress = json.loads(capsys.readouterr().out)
    assert progress["reviews_pending"] == 1
    assert workspace_main([
        "run",
        "--workspace", str(workspace),
        "--review", review_name,
        "--usable-completion", "false",
        "--intent-fields-reviewed", "true",
    ]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["updated"] == "run"

    with pytest.raises(SystemExit) as exc:
        workspace_main([
            "run",
            "--workspace", str(workspace),
            "--review", review_name,
            "--usable-completion", "yes",
            "--intent-fields-reviewed", "true",
        ])
    assert exc.value.code == 2


def test_run_adjudication_is_bound_to_blocked_status_and_paired_intent(tmp_path: Path) -> None:
    queue_payload = _queue()
    _bind_run_summary(queue_payload, tmp_path, status="blocked")
    entry = queue_payload["entries"][0]
    entry["identity"][2] = "training"
    entry["review_template"]["intent_id"] = "training"
    entry["review_template"]["usable_completion"] = None
    entry["review_template"]["intent_fields_reviewed"] = None
    entry["review_template"]["blocked_reason_review"] = "__REQUIRED_BLOCK_REVIEW__"
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_name = _review_path(workspace).name

    with pytest.raises(ValueError, match="blocked run requires"):
        record_run_adjudication(
            workspace,
            review_name,
            usable_completion=False,
            intent_fields_reviewed=True,
        )
    with pytest.raises(ValueError, match="paired-intent run requires"):
        record_run_adjudication(
            workspace,
            review_name,
            usable_completion=False,
            intent_fields_reviewed=False,
            blocked_reason_review="Budget exhausted after evidence-safe retries.",
            blocked_reason_classification="correct_repairable",
        )
    record_run_adjudication(
        workspace,
        review_name,
        usable_completion=False,
        intent_fields_reviewed=True,
        blocked_reason_review="Budget exhausted after evidence-safe retries.",
        blocked_reason_classification="correct_repairable",
    )
    saved = json.loads(_review_path(workspace).read_text(encoding="utf-8"))
    assert saved["blocked_reason_classification"] == "correct_repairable"


def test_sign_revalidates_manually_edited_match_ids(tmp_path: Path) -> None:
    queue_payload = _queue()
    _bind_run_summary(queue_payload, tmp_path)
    queue_payload["entries"][0]["review_template"]["claims"] = [{
        "atomic_claim_id": "FAC1",
        "text": "A directly grounded claim.",
        "verdict": "supported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    queue = tmp_path / "queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review["claims"][0].update({
        "semantic_match": "matched",
        "gold_claim_id": "UNKNOWN",
        "mutation_match": "no_match",
        "direct_evidence_support": True,
        "qualifiers_preserved": True,
    })
    review_path.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown semantic match id"):
        sign_review(
            workspace,
            review_path.name,
            reviewer="Ada Reviewer",
            reviewed_at="2026-07-18T12:00:00+08:00",
        )


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


def test_review_workspace_rejects_deleted_or_rebound_agentic_figure_inventory(tmp_path: Path) -> None:
    queue_payload = _queue()
    queue_payload["entries"][0]["identity"][1] = "agentic_deterministic"
    template = queue_payload["entries"][0]["review_template"]
    template["variant"] = "agentic_deterministic"
    template["model_id"] = ""
    template["capability_profile_digest"] = ""
    template["figures"] = build_figure_review_inventory({
        "nodes": [{"element_id": "scene-N1", "label": "Frozen node"}],
        "edges": [], "annotations": [], "groups": [],
    })
    queue = tmp_path / "agentic-queue.json"
    queue.write_text(json.dumps(queue_payload), encoding="utf-8")
    workspace = tmp_path / "workspace"
    materialize_review_workspace(queue, workspace)
    review_path = _review_path(workspace)
    _completed_review(review_path)
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    payload["figures"][0].update({"semantically_supported": True, "rendered_drift": False})
    review_path.write_text(json.dumps(payload), encoding="utf-8")
    protocol = SimpleNamespace(
        workspace_commit="commit:test",
        gold_digest="sha256:" + "6" * 64,
        specs=[SimpleNamespace(
            case_id=IDENTITY[0], variant="agentic_deterministic", intent_id=IDENTITY[2], repeat_index=IDENTITY[3],
        )],
    )

    with (
        patch(
            "code2paper.agentic.benchmark_review_workspace.extract_benchmark_observation_v2",
            return_value=_observation().model_copy(update={"variant": "agentic_deterministic"}),
        ),
        patch(
            "code2paper.agentic.benchmark_review_workspace.validate_protocol_observations_v2",
            return_value=[],
        ),
    ):
        report, _ = validate_review_workspace(queue, workspace, _dataset(), protocol)
    assert report["status"] == "passed"

    payload["figures"] = []
    review_path.write_text(json.dumps(payload), encoding="utf-8")
    report, observations = validate_review_workspace(queue, workspace, _dataset(), protocol)
    assert report["status"] == "failed"
    assert "figure_inventory_or_scene_binding_changed" in report["invalid_reviews"][0]["failures"]
    assert observations == []


def test_review_queue_figure_templates_are_scene_complete_and_digest_pinned(tmp_path: Path) -> None:
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(json.dumps({
        "nodes": [{"element_id": "scene-N1", "label": "Node"}],
        "edges": [{"element_id": "scene-E1", "label": "passes", "relation_id": "R1"}],
        "annotations": [],
        "groups": [],
    }), encoding="utf-8")
    scene_digest = "sha256:" + __import__("hashlib").sha256(scene_path.read_bytes()).hexdigest()
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps({
        "artifacts": {"figure_scene": {"path": str(scene_path), "hash": scene_digest}},
    }), encoding="utf-8")

    inventory = _agentic_figure_templates(summary_path)

    assert [item["element_kind"] for item in inventory] == ["node", "edge"]
    assert all(item["semantically_supported"] is None for item in inventory)
    assert inventory[1]["direct_relation_evidence"] is None
    scene_path.write_text('{"nodes":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="figure scene digest changed"):
        _agentic_figure_templates(summary_path)


def test_review_queue_claim_templates_are_complete_and_digest_pinned(tmp_path: Path) -> None:
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps({
        "atomic_claims": [{"atomic_claim_id": "FAC1", "text": "Frozen final claim."}],
    }), encoding="utf-8")
    validation_path = tmp_path / "validation.json"
    validation_path.write_text(json.dumps({
        "verdicts": [{"atomic_claim_id": "FAC1", "status": "supported"}],
    }), encoding="utf-8")
    digest = lambda path: "sha256:" + __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps({
        "artifacts": {
            "final_text_claims": {"path": str(claims_path), "hash": digest(claims_path)},
            "text_evidence_validation": {"path": str(validation_path), "hash": digest(validation_path)},
        },
    }), encoding="utf-8")

    inventory = _agentic_claim_templates(summary_path)

    assert inventory == [{
        "atomic_claim_id": "FAC1",
        "text": "Frozen final claim.",
        "verdict": "supported",
        "semantic_match": None,
        "gold_claim_id": "",
        "mutation_match": None,
        "mutation_id": "",
        "direct_evidence_support": None,
        "qualifiers_preserved": None,
        "high_risk": False,
    }]
    claims_path.write_text('{"atomic_claims":[]}', encoding="utf-8")
    with pytest.raises(ValueError, match="final_text_claims digest changed"):
        _agentic_claim_templates(summary_path)
