"""R4: the authoring replay records a durable execution record.

The replay script must persist the exact command, per-command exit code,
pre/post runtime state, and a final code-state binding so acceptance can
verify what ran and on which code state.  These tests exercise the
record-writing boundary without starting the LLM runtime.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "run_authoring_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_authoring_replay", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_execution_record_contains_command_exit_code_and_code_binding(
    tmp_path: Path,
) -> None:
    module = _load_script()
    args = argparse.Namespace(
        run_id="replay-test",
        resume=["MA-S2"],
        profile="absent-profile.env",
        frozen_root=str(tmp_path / "frozen"),
        fresh_root=str(tmp_path / "fresh"),
    )
    module._write_execution_record(
        frozen=tmp_path / "frozen",
        fresh=tmp_path / "fresh",
        arguments=args,
        exit_code=2,
        runtime_start={"health": 200, "models": ["qwen36-27b-nvfp4"], "running": 1},
        runtime_end={"health": 200, "models": ["qwen36-27b-nvfp4"], "running": 0},
        telemetry={
            "reused_fulfilled_callback_ids": ["request:MA-S2:limitations_or_mismatch"],
            "writer_resumed_section_ids": [],
            "writer_status": "incomplete",
            "writer_blocked_reason": "",
        },
    )
    record_path = tmp_path / "fresh" / "execution_record.json"
    assert record_path.is_file()
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["run_id"] == "replay-test"
    assert record["exit_code"] == 2
    assert record["command"]
    assert isinstance(record["argv"], list) and record["argv"]
    assert record["resume_section_ids"] == ["MA-S2"]
    assert record["code_state_digest"].startswith("sha256:")
    assert record["reused_fulfilled_callback_ids"] == [
        "request:MA-S2:limitations_or_mismatch"
    ]
    assert record["writer_resumed_section_ids"] == []
    assert record["writer_status"] == "incomplete"
    assert record["runtime"]["start"]["health"] == 200
    assert record["runtime"]["start"]["running"] == 1
    assert record["runtime"]["end"]["running"] == 0


def test_authoring_failure_marks_completed_failed_and_not_run_stages(
    tmp_path: Path,
) -> None:
    module = _load_script()
    fresh = tmp_path / "fresh-failure"
    path = module._write_authoring_failure(
        fresh=fresh,
        terminal_stage="writer",
        terminal_reason="writer_status:incomplete",
        error_code="writer_boundary_failed",
    )

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["terminal_stage"] == "writer"
    assert payload["downstream_stages"] == {
        "research": "completed",
        "formalizer": "completed",
        "writer": "failed",
    }

    path = module._write_authoring_failure(
        fresh=tmp_path / "research-failure",
        terminal_stage="research",
        terminal_reason="research_not_ready",
        error_code="research_boundary_failed",
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["downstream_stages"] == {
        "research": "failed",
        "formalizer": "not_run",
        "writer": "not_run",
    }


def test_code_state_digest_is_deterministic_and_read_only(tmp_path: Path) -> None:
    module = _load_script()
    first = module._code_state_digest()
    second = module._code_state_digest()
    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64


def test_callback_transaction_rejects_structural_regression() -> None:
    module = _load_script()
    incumbent = {
        "required_paragraphs": 7,
        "valid_required_paragraphs": 5,
        "invalid_paragraphs": 2,
        "required_targets": 29,
        "valid_targets": 25,
        "required_slots": 9,
        "witnessed_slots": 7,
        "required_edges": 0,
        "witnessed_edges": 0,
        "accepted_formula_packages": 3,
        "consumed_formula_packages": 0,
        "blocked_representation": 0,
        "invalid_witnesses": 1,
    }
    regressed = {**incumbent, "valid_required_paragraphs": 2,
                 "valid_targets": 8, "witnessed_slots": 2,
                 "invalid_paragraphs": 5, "blocked_representation": 4,
                 "invalid_witnesses": 6}
    committed, reason = module._callback_transaction_decision(incumbent, regressed)
    assert committed is False
    assert "coverage_regressed" in reason or "increased" in reason


def test_callback_transaction_accepts_only_safe_gain() -> None:
    module = _load_script()
    incumbent = {
        "required_paragraphs": 7,
        "valid_required_paragraphs": 5,
        "invalid_paragraphs": 2,
        "required_targets": 29,
        "valid_targets": 25,
        "required_slots": 9,
        "witnessed_slots": 7,
        "required_edges": 0,
        "witnessed_edges": 0,
        "accepted_formula_packages": 3,
        "consumed_formula_packages": 0,
        "blocked_representation": 0,
        "invalid_witnesses": 1,
    }
    improved = {**incumbent, "valid_required_paragraphs": 6,
                "valid_targets": 27, "invalid_paragraphs": 1,
                "invalid_witnesses": 0}
    committed, reason = module._callback_transaction_decision(incumbent, improved)
    assert committed is True
    assert "gain" in reason or "reduced" in reason


def test_replay_fails_closed_on_missing_frozen_artifacts(tmp_path: Path) -> None:
    """A frozen root without the required research artifacts exits 2 before
    any LLM call, and the record still carries the exit code."""
    module = _load_script()
    frozen = tmp_path / "frozen-root"
    frozen.mkdir(parents=True)
    fresh = tmp_path / "fresh-root"
    args = argparse.Namespace(
        run_id="replay-missing",
        resume=[],
        profile=str(tmp_path / "absent-profile.env"),
        frozen_root=str(frozen),
        fresh_root=str(fresh),
    )
    exit_code = module._replay(
        frozen=frozen,
        fresh=fresh,
        arguments=args,
        telemetry={},
    )
    assert exit_code == 2
    # No writer artifacts were produced and nothing was copied.
    assert not (fresh / "artifacts" / "atomic_claims_v3.json").exists()


def test_frozen_artifacts_exclude_derived_authoring_names() -> None:
    module = _load_script()
    derived = set(module.DERIVED_AUTHORING_ARTIFACTS)
    assert "authoring_projection_v1" in derived
    assert "method_section_plan_v2" in derived
    assert "method_argument_briefs_v1" in derived
    assert "writing_research_callback_artifacts_v1" in derived
    for name in module.FROZEN_ARTIFACTS:
        assert name not in derived


def test_replay_does_not_copy_callbacks_without_reuse_flag(tmp_path: Path) -> None:
    module = _load_script()
    frozen = tmp_path / "frozen"
    artifacts = frozen / "artifacts"
    artifacts.mkdir(parents=True)
    for name in module.RESEARCH_COPY_ARTIFACTS:
        (artifacts / f"{name}.json").write_text(
            json.dumps({"schema_version": "1.0", "content_digest": "sha256:stub"}),
            encoding="utf-8",
        )
    callback_bundle = {
        "schema_version": "1.0",
        "requests": [],
        "artifacts": {},
        "resume_section_ids": [],
    }
    (artifacts / "writing_research_callback_artifacts_v1.json").write_text(
        json.dumps(callback_bundle), encoding="utf-8"
    )
    (artifacts / "method_section_plan_v2.json").write_text(
        json.dumps({"schema_version": "1.0", "content_digest": "sha256:plan"}),
        encoding="utf-8",
    )
    fresh = tmp_path / "fresh"
    profile = tmp_path / "profile.env"
    profile.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    args = argparse.Namespace(
        run_id="replay-no-callback-copy",
        resume=[],
        profile=str(profile),
        frozen_root=str(frozen),
        fresh_root=str(fresh),
        repo="",
        callback_rounds=1,
        callback_tool_turns=1,
        rebuild_authoring=False,
        reuse_authoring_callbacks=False,
        persist_authoring_rebuild_manifest=False,
    )
    exit_code = module._replay(
        frozen=frozen,
        fresh=fresh,
        arguments=args,
        telemetry={},
    )
    assert exit_code == 2
    assert not (fresh / "artifacts" / "writing_research_callback_artifacts_v1.json").exists()


def test_replay_continuation_trigger_is_issue_driven(tmp_path: Path) -> None:
    module = _load_script()
    fresh = tmp_path / "fresh"
    authoring = fresh / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    bundle_path = authoring / "writing_research_callback_artifacts_v1.json"
    bundle_path.write_text(
        json.dumps({
            "schema_version": "1.0",
            "requests": [{"status": "open"}],
            "artifacts": {},
            "resume_section_ids": [],
        }),
        encoding="utf-8",
    )
    assert module._authoring_continuation_needed(fresh) is True

    bundle_path.unlink()
    validation_path = fresh / "artifacts" / "07_validation" / (
        "agentic_text_evidence_validation.json"
    )
    validation_path.parent.mkdir(parents=True)
    validation_path.write_text(
        json.dumps({
            "status": "failed",
            "unsupported_claims": 1,
            "unverified_claims": 0,
        }),
        encoding="utf-8",
    )
    assert module._authoring_continuation_needed(fresh) is True

    validation_path.write_text(
        json.dumps({
            "status": "passed",
            "unsupported_claims": 0,
            "unverified_claims": 0,
        }),
        encoding="utf-8",
    )
    assert module._authoring_continuation_needed(fresh) is False


def test_callback_one_is_not_authorized_before_research_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A structurally incomplete writer result must not enter callback=1.

    The replay still leaves a durable Candidate digest and records an explicit
    not-authorized status, but no Research runtime/continuation seed may be
    constructed.
    """
    module = _load_script()
    frozen = tmp_path / "frozen"
    artifacts = frozen / "artifacts"
    artifacts.mkdir(parents=True)
    for name in module.RESEARCH_COPY_ARTIFACTS:
        (artifacts / f"{name}.json").write_text("{}", encoding="utf-8")
    fresh = tmp_path / "fresh"
    profile = tmp_path / "profile.env"
    profile.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(module, "_apply_live_profile", lambda _path: None)
    import code2paper.llm.providers as providers
    monkeypatch.setattr(providers, "load_llm_config_from_env", lambda: object())

    def fake_writer(**_kwargs):
        return SimpleNamespace(
            status="success",
            blocked_reason="",
            resumed_section_ids=(),
        ), {}

    import code2paper.agentic.publication_method_writer as writer_module
    monkeypatch.setattr(writer_module, "run_publication_method_writer", fake_writer)
    monkeypatch.setattr(
        module, "_record_method_content_trace",
        lambda **_kwargs: "trace.json",
    )
    monkeypatch.setattr(module, "_record_product_authoring_state", lambda **_kwargs: None)
    monkeypatch.setattr(
        module, "_record_authoring_structural_exit",
        lambda *, fresh, paths, telemetry: {
            "eligible": False,
            "reasons": ["required_target_coverage_incomplete"],
            "content_digest": "sha256:structural",
        },
    )
    monkeypatch.setattr(module, "_candidate_digest_for_root", lambda _root: "sha256:candidate")

    def fail_if_constructed(**_kwargs):
        raise AssertionError("callback=1 constructed a Research continuation before structural exit")

    monkeypatch.setattr(module, "_build_replay_continuation_context", fail_if_constructed)
    args = argparse.Namespace(
        run_id="callback-one-gated",
        resume=[],
        profile=str(profile),
        frozen_root=str(frozen),
        fresh_root=str(fresh),
        repo=str(repo),
        callback_rounds=1,
        callback_tool_turns=1,
        rebuild_authoring=False,
        reuse_authoring_callbacks=False,
        persist_authoring_rebuild_manifest=False,
    )
    telemetry: dict = {}
    assert module._replay(frozen=frozen, fresh=fresh, arguments=args, telemetry=telemetry) == 2
    assert telemetry["callback_fulfillment"]["status"] == "not_authorized"
    assert telemetry["callback_fulfillment"]["stopped_reason"] == "callback1_not_authorized"
    # Structural authorization is a downstream gate; it must not rewrite the
    # already-complete Writer transaction into an incomplete Writer state.
    assert telemetry["writer_status"] == "success"


def test_callback_one_requires_complete_writer_even_when_structure_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script()
    frozen = tmp_path / "frozen"
    artifacts = frozen / "artifacts"
    artifacts.mkdir(parents=True)
    for name in module.RESEARCH_COPY_ARTIFACTS:
        (artifacts / f"{name}.json").write_text("{}", encoding="utf-8")
    fresh = tmp_path / "fresh"
    profile = tmp_path / "profile.env"
    profile.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(module, "_apply_live_profile", lambda _path: None)
    import code2paper.llm.providers as providers
    monkeypatch.setattr(providers, "load_llm_config_from_env", lambda: object())

    def fake_writer(**_kwargs):
        return SimpleNamespace(
            status="incomplete",
            blocked_reason="",
            resumed_section_ids=(),
        ), {}

    import code2paper.agentic.publication_method_writer as writer_module
    monkeypatch.setattr(writer_module, "run_publication_method_writer", fake_writer)
    monkeypatch.setattr(
        module, "_record_method_content_trace", lambda **_kwargs: "trace.json",
    )
    monkeypatch.setattr(module, "_record_product_authoring_state", lambda **_kwargs: None)
    monkeypatch.setattr(
        module, "_record_authoring_structural_exit",
        lambda *, fresh, paths, telemetry: {
            "eligible": True,
            "reasons": [],
            "content_digest": "sha256:structural",
        },
    )
    monkeypatch.setattr(module, "_candidate_digest_for_root", lambda _root: "sha256:candidate")

    def fail_if_constructed(**_kwargs):
        raise AssertionError("callback=1 must not construct Research for an incomplete Writer")

    monkeypatch.setattr(module, "_build_replay_continuation_context", fail_if_constructed)
    args = argparse.Namespace(
        run_id="callback-one-writer-incomplete",
        resume=[],
        profile=str(profile),
        frozen_root=str(frozen),
        fresh_root=str(fresh),
        repo=str(repo),
        callback_rounds=1,
        callback_tool_turns=1,
        rebuild_authoring=False,
        reuse_authoring_callbacks=False,
        persist_authoring_rebuild_manifest=False,
    )
    telemetry: dict = {}
    assert module._replay(frozen=frozen, fresh=fresh, arguments=args, telemetry=telemetry) == 2
    assert telemetry["callback_fulfillment"]["status"] == "not_authorized"
    assert telemetry["callback_fulfillment"]["stopped_reason"] == "callback1_not_authorized"
    assert telemetry["writer_status"] == "incomplete"


def test_rebuild_authoring_without_runtime_entry_fails_closed(tmp_path: Path) -> None:
    module = _load_script()
    frozen = tmp_path / "frozen"
    artifacts = frozen / "artifacts"
    artifacts.mkdir(parents=True)
    for name in module.RESEARCH_COPY_ARTIFACTS:
        (artifacts / f"{name}.json").write_text(
            json.dumps({"schema_version": "1.0", "content_digest": "sha256:stub"}),
            encoding="utf-8",
        )
    fresh = tmp_path / "fresh"
    profile = tmp_path / "missing-profile.env"
    args = argparse.Namespace(
        run_id="replay-rebuild-fail",
        resume=[],
        profile=str(profile),
        frozen_root=str(frozen),
        fresh_root=str(fresh),
        repo="",
        callback_rounds=1,
        callback_tool_turns=1,
        rebuild_authoring=True,
        reuse_authoring_callbacks=False,
        persist_authoring_rebuild_manifest=True,
    )
    exit_code = module._replay(
        frozen=frozen,
        fresh=fresh,
        arguments=args,
        telemetry={},
    )
    assert exit_code == 2
    assert not (artifacts / "method_section_plan_v2.json").exists()


def test_method_evidence_rebuild_template_maps_snapshot_fields(tmp_path: Path) -> None:
    """WP6 Gate 6B: frozen snapshot identity is not a MethodEvidence field."""

    from code2paper.core.schemas import MethodEvidence

    module = _load_script()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "method_evidence.json").write_text(
        json.dumps({
            "method_name": "Present the method.",
            "repo_snapshot_id": "repo:9b7808f3467cadeb628e63ff",
            "project_tree_hash": "sha256:9b7808f3467cadeb6",
        }),
        encoding="utf-8",
    )
    intent = type(
        "Intent",
        (),
        {
            "method_goal": "Explain the dynamic graph encoder.",
            "project_goal": "Study dynamic graphs.",
            "implementation_scope": "/repo/DyG",
        },
    )()
    claims = type("Claims", (), {"repo_snapshot_id": "repo:9b7808f3467cadeb628e63ff"})()
    template = module._method_evidence_rebuild_template(
        artifacts=artifacts,
        intent_graph=intent,
        claims=claims,
    )
    assert isinstance(template, MethodEvidence)
    assert template.project_id == "repo:9b7808f3467cadeb628e63ff"
    assert template.method_name == "Present the method."
    assert template.method_goal == "Explain the dynamic graph encoder."
    assert template.implementation_scope == "/repo/DyG"
    dumped = template.model_dump(mode="python")
    assert "repo_snapshot_id" not in dumped
    assert "project_tree_hash" not in dumped


def test_method_evidence_rebuild_template_keeps_valid_frozen_file(tmp_path: Path) -> None:
    from code2paper.core.schemas import MethodEvidence

    module = _load_script()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    frozen = MethodEvidence(
        project_id="repo:frozen",
        method_name="DyG-Mamba",
        method_goal="Model continuous state on dynamic graphs.",
        implementation_scope="/repo/DyG",
    )
    (artifacts / "method_evidence.json").write_text(
        frozen.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    intent = type(
        "Intent",
        (),
        {
            "method_goal": "unused",
            "project_goal": "unused",
            "implementation_scope": "unused",
        },
    )()
    claims = type("Claims", (), {"repo_snapshot_id": "repo:other"})()
    template = module._method_evidence_rebuild_template(
        artifacts=artifacts,
        intent_graph=intent,
        claims=claims,
    )
    assert template.project_id == "repo:frozen"
    assert template.method_name == "DyG-Mamba"
    assert template.method_goal == "Model continuous state on dynamic graphs."
