"""Tests for the consolidated D5 matrix runner (no real API calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_d5_consolidated_matrix import (
    _fulfilled_artifacts,
    artifact_paths_for,
    build_matrix_summary,
    digest_bytes,
    digest_file,
    load_and_verify_manifest,
)


def _manifest(tmp_path: Path) -> dict:
    source = tmp_path / "d25" / "rap"
    source.mkdir(parents=True)
    payload = {"schema_version": "1.0", "repo_snapshot_id": "repo:rap"}
    for filename in (
        "atomic_claims_v3_v3.json",
        "code_facts_v1_v3.json",
        "equation_claims_v1_v3.json",
        "configuration_claims_v1.json",
        "method_completeness_matrix_v1.json",
        "method_section_plan_v2.json",
        "evidence_packets_v3_v3.json",
    ):
        (source / filename).write_text(
            json.dumps({**payload, "file": filename}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    files = {
        filename: {
            "path": str(source / filename),
            "digest": digest_file(source / filename),
            "schema_version": "1.0",
        }
        for filename in sorted(p.name for p in source.iterdir())
    }
    return {
        "manifest_id": "test-1",
        "projects": {"rap": {"artifact_dir": str(source), "files": files}},
    }


def test_manifest_verification_rejects_digest_mismatch(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = load_and_verify_manifest(manifest_path)
    assert loaded["projects"]["rap"]["files"]

    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = next(iter(tampered["projects"]["rap"]["files"].values()))
    first["digest"] = "sha256:" + "0" * 64
    tampered_path = tmp_path / "tampered_manifest.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="digest_mismatch"):
        load_and_verify_manifest(tampered_path)


def test_artifact_paths_are_generic_and_synthesize_method_evidence(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    out_root = tmp_path / "run"
    paths = artifact_paths_for(manifest["projects"]["rap"], out_root, "rap")

    for key, filename in (
        ("atomic_claims_v3", "atomic_claims_v3_v3.json"),
        ("evidence_packets_v3", "evidence_packets_v3_v3.json"),
    ):
        assert Path(paths[key]).is_file()
        assert Path(paths[key]).name == filename
    assert paths["method_evidence"].endswith("rap_method_evidence_for_final_validation.json")
    evidence = json.loads(Path(paths["method_evidence"]).read_text(encoding="utf-8"))
    assert evidence["project_id"] == "rap"
    assert set(evidence) == {"project_id", "method_name", "method_goal", "implementation_scope"}


def test_matrix_summary_aggregates_terminal_gates(tmp_path: Path) -> None:
    out_root = tmp_path / "matrix"
    results = {
        "ebcar": {
            "status": "success",
            "safety_hard_gate": True,
            "utility_gate": True,
            "final_integrity_gate": True,
            "accepted_section_ids": ["MA-S1", "MA-S2"],
            "incomplete_section_ids": [],
        },
        "rap": {
            "status": "incomplete",
            "safety_hard_gate": True,
            "utility_gate": False,
            "final_integrity_gate": False,
            "accepted_section_ids": ["MA-S1"],
            "incomplete_section_ids": ["MA-S2"],
        },
    }
    summary = build_matrix_summary(results, out_root)
    assert summary["aggregate"]["all_safety_gates"] is True
    assert summary["aggregate"]["all_utility_gates"] is False
    assert summary["aggregate"]["all_final_integrity_gates"] is False
    assert summary["aggregate"]["total_accepted_sections"] == 3
    assert summary["aggregate"]["total_incomplete_sections"] == 1
    assert (out_root / "matrix_summary.json").is_file()


def test_fulfilled_artifacts_rebuilds_bundle_map() -> None:
    bundle = {
        "requests": [{
            "request_id": "request:1",
            "status": "fulfilled",
            "fulfilled_artifact_ids": ["artifact:a"],
        }],
        "artifacts": {
            "request:1": [{
                "artifact_id": "artifact:a",
                "artifact_digest": "sha256:a",
                "validated": True,
            }]
        },
    }
    rebuilt = _fulfilled_artifacts(bundle)
    assert rebuilt == {"artifact:a": {
        "artifact_id": "artifact:a",
        "artifact_digest": "sha256:a",
        "validated": True,
    }}


def test_lease_conflicts_are_detected(tmp_path: Path) -> None:
    from scripts.run_d5_consolidated_matrix import EndpointLease

    out_root = tmp_path / "lease"
    first = EndpointLease(out_root)
    assert first.acquire("matrix:first") is True
    second = EndpointLease(out_root)
    assert second.acquire("matrix:second") is False
    first.release()
    third = EndpointLease(out_root)
    assert third.acquire("matrix:third") is True
    third.release()


def test_digest_bytes_is_deterministic() -> None:
    assert digest_bytes(b"abc") == digest_bytes(b"abc")
    assert digest_bytes(b"abc") != digest_bytes(b"abd")
    assert digest_bytes(b"abc").startswith("sha256:")


def test_manifest_identity_mismatch_fails_closed(tmp_path: Path, monkeypatch) -> None:
    """The runner must refuse to run when the manifest binds a different code state."""
    from scripts.run_d5_consolidated_matrix import main

    source = tmp_path / "d25"
    source.mkdir(parents=True)
    for filename in (
        "atomic_claims_v3_v3.json",
        "code_facts_v1_v3.json",
        "equation_claims_v1_v3.json",
        "configuration_claims_v1.json",
        "method_completeness_matrix_v1.json",
        "method_section_plan_v2.json",
        "evidence_packets_v3_v3.json",
    ):
        (source / filename).write_text(json.dumps({"file": filename}), encoding="utf-8")
    files = {
        filename: {"path": str(source / filename), "digest": digest_file(source / filename), "schema_version": "1.0"}
        for filename in sorted(p.name for p in source.iterdir())
    }
    manifest = {
        "manifest_id": "identity-test",
        "code_identity": {
            "git_head": "wrong-head",
            "diff_sha256": "sha256:" + "0" * 64,
            "untracked_file_digests": {},
        },
        "projects": {"rap": {"artifact_dir": str(source), "files": files}},
    }
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = main([
        "--manifest", str(manifest_path),
        "--out-root", str(tmp_path / "out"),
        "--projects", "rap",
        "--dry-run",
    ])

    assert exit_code == 2


def test_run_one_project_resume_reads_authoring_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resume must read the result and callback bundle under artifacts/06_authoring."""
    from types import SimpleNamespace

    from code2paper.core.schemas import LLMConfig

    from scripts.run_d5_consolidated_matrix import run_one_project

    manifest = _manifest(tmp_path)
    project_root = tmp_path / "out" / "rap"
    authoring = project_root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "publication_writer_result_v1.json").write_text(
        json.dumps({"incomplete_section_ids": ["MA-S1"]}), encoding="utf-8"
    )
    (authoring / "writing_research_callback_artifacts_v1.json").write_text(
        json.dumps({
            "requests": [{
                "request_id": "request:MA-S1:limitations_or_mismatch",
                "section_id": "MA-S1",
                "argument_unit_id": "MA-S1:unit",
                "missing_rhetorical_move": "limitations_or_mismatch",
                "exact_question": "q",
                "required_authority_lane": "executable_hard",
                "status": "fulfilled",
                "fulfilled_artifact_ids": ["artifact:1"],
            }],
            "artifacts": {
                "request:MA-S1:limitations_or_mismatch": [{
                    "artifact_id": "artifact:1",
                    "request_id": "request:MA-S1:limitations_or_mismatch",
                    "section_id": "MA-S1",
                    "argument_unit_id": "MA-S1:unit",
                    "authority_lane": "executable_hard",
                    "artifact_ref": "fact:f1",
                    "artifact_digest": "sha256:1",
                    "validated": True,
                }]
            },
        }),
        encoding="utf-8",
    )

    captured: dict = {}
    stub_result = SimpleNamespace(
        status="blocked",
        blocked_reason="probe",
        accepted_section_ids=["MA-S2"],
        incomplete_section_ids=["MA-S1"],
        binding_failures=[],
        resumed_section_ids=("MA-S1",),
        writer_aggregate={"cumulative_budget_consumed": 1, "cumulative_budget_cap": 3, "traces": []},
        response_recovery_traces=[],
    )

    def fake_writer(**kwargs):
        captured.update(kwargs)
        return stub_result, {}

    monkeypatch.setattr(
        "code2paper.agentic.publication_method_writer.run_publication_method_writer", fake_writer
    )
    monkeypatch.setattr(
        "code2paper.llm.providers.load_llm_config_from_env",
        lambda: LLMConfig(model="probe"),
    )

    summary = run_one_project(
        project_id="rap", project=manifest["projects"]["rap"],
        out_root=tmp_path / "out", resume=True,
    )

    assert captured["resume_section_ids"] == ("MA-S1",)
    assert list(captured["research_callback_artifacts"]) == [
        "request:MA-S1:limitations_or_mismatch"
    ]
    artifact = captured["research_callback_artifacts"]["request:MA-S1:limitations_or_mismatch"][0]
    assert artifact["artifact_id"] == "artifact:1"
    assert artifact["artifact_digest"] == "sha256:1"
    assert artifact["validated"] is True
    assert summary["admitted_resume_section_ids"] == ["MA-S1"]
    assert summary["status"] == "blocked"
