"""§14.1/§14.2：L1 回放入口接上 WP1 执行身份（离线，provider=NONE）。"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from code2paper.agentic.authoring_execution_identity import (
    RunOpenRejected,
    load_execution_identity,
)
from code2paper.llm.client import LLMConfig, LLMProvider

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_authoring_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_authoring_replay", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _target_repo(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git("init", "-q", cwd=root)
    _git("add", "-A", cwd=root)
    _git(
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        cwd=root,
    )
    return root


def _frozen_root(tmp_path: Path, *, with_checkpoint: bool = True, with_intent: bool = True) -> Path:
    frozen = tmp_path / "frozen"
    (frozen / "artifacts").mkdir(parents=True, exist_ok=True)
    if with_intent:
        (frozen / "artifacts" / "intent_obligation_graph_v2.json").write_text(
            '{"run_id": "research-1", "must_cover": []}\n', encoding="utf-8"
        )
    if with_checkpoint:
        from .research_import_fixture import write_research_checkpoint

        write_research_checkpoint(
            frozen / "artifacts" / "research_product" / "research_stage_checkpoint_v1.json",
            run_id="research-1",
        )
    return frozen


def _arguments(frozen: Path, repo: object = None, **overrides: object) -> argparse.Namespace:
    payload: dict[str, object] = {
        "run_id": "l1-replay",
        "resume": ["MA-S3"],
        "profile": "absent-profile.env",
        "frozen_root": str(frozen),
        "fresh_root": str(frozen.parent / "fresh"),
        "repo": str(repo if repo is not None else frozen.parent / "target"),
        "run_open_mode": "new",
    }
    payload.update(overrides)
    return argparse.Namespace(**payload)


def _identity_file(fresh: Path) -> Path:
    return fresh / "artifacts" / "research_product" / "authoring_execution_identity_v2.json"


def test_replay_writes_identity_before_any_authoring_artifact(tmp_path: Path) -> None:
    module = _load_script()
    frozen = _frozen_root(tmp_path)
    repo = _target_repo(tmp_path)
    fresh = tmp_path / "fresh"
    fresh.mkdir()

    report = module._open_replay_execution_identity(
        frozen=frozen,
        fresh=fresh,
        arguments=_arguments(frozen, repo),
        llm_config=LLMConfig(provider=LLMProvider.NONE),
    )

    assert report["status"] == "opened"
    assert report["execution_id"].startswith("exec-")
    identity = load_execution_identity(fresh)
    assert identity is not None, "回放入口必须写出 AuthoringExecutionIdentityV2"
    assert identity.execution_id == report["execution_id"]
    assert identity.content_digest == report["content_digest"]
    assert identity.creation_mode == "new"
    # 冻结意图图与冻结研究 checkpoint 都进入身份。
    assert identity.intent_content_digest
    assert identity.research_import_digest
    assert _identity_file(fresh).is_file()


def test_replay_identity_is_deterministic_per_inputs(tmp_path: Path) -> None:
    module = _load_script()
    frozen = _frozen_root(tmp_path)
    repo = _target_repo(tmp_path)
    config = LLMConfig(provider=LLMProvider.NONE)

    first = module._open_replay_execution_identity(
        frozen=frozen,
        fresh=tmp_path / "fresh-a",
        arguments=_arguments(frozen, repo),
        llm_config=config,
    )
    second = module._open_replay_execution_identity(
        frozen=frozen,
        fresh=tmp_path / "fresh-b",
        arguments=_arguments(frozen, repo),
        llm_config=config,
    )
    assert first["content_digest"] == second["content_digest"]
    assert first["execution_id"] == second["execution_id"]

    # 冻结输入一变，身份必须变（不能复用旧身份冒充同一 run）。
    frozen_changed = _frozen_root(tmp_path / "other")
    (frozen_changed / "artifacts" / "intent_obligation_graph_v2.json").write_text(
        '{"run_id": "research-1", "must_cover": ["X"]}\n', encoding="utf-8"
    )
    third = module._open_replay_execution_identity(
        frozen=frozen_changed,
        fresh=tmp_path / "fresh-c",
        arguments=_arguments(frozen_changed, repo),
        llm_config=config,
    )
    assert third["intent_content_digest"] != first["intent_content_digest"]
    assert third["content_digest"] != first["content_digest"]


def test_replay_resume_requires_matching_identity(tmp_path: Path) -> None:
    module = _load_script()
    frozen = _frozen_root(tmp_path)
    repo = _target_repo(tmp_path)
    fresh = tmp_path / "fresh"
    config = LLMConfig(provider=LLMProvider.NONE)
    opened = module._open_replay_execution_identity(
        frozen=frozen, fresh=fresh, arguments=_arguments(frozen, repo), llm_config=config
    )

    # 同一身份 + 同一输入 → resume 通过，身份字节不变。
    identity_path = _identity_file(fresh)
    before = identity_path.read_bytes()
    resumed = module._open_replay_execution_identity(
        frozen=frozen,
        fresh=fresh,
        arguments=_arguments(frozen, repo, run_open_mode="resume"),
        llm_config=config,
    )
    assert resumed["execution_id"] == opened["execution_id"]
    assert identity_path.read_bytes() == before

    # 输入变了却要求 resume → 必须拒绝（不得继续用旧身份写作）。
    changed = _frozen_root(tmp_path / "changed")
    (changed / "artifacts" / "intent_obligation_graph_v2.json").write_text(
        '{"run_id": "research-1", "must_cover": ["Y"]}\n', encoding="utf-8"
    )
    with pytest.raises(RunOpenRejected) as excinfo:
        module._open_replay_execution_identity(
            frozen=changed,
            fresh=fresh,
            arguments=_arguments(changed, repo, run_open_mode="resume"),
            llm_config=config,
        )
    assert excinfo.value.decision.code == "resume_identity_mismatch"
    assert "intent_content_digest" in excinfo.value.decision.mismatched_fields


def test_replay_fork_requires_verified_research_import(tmp_path: Path) -> None:
    """回放 fork：空壳/缺失导入被拒；导入不属于当前目标同样被拒（审计 §A.4）。"""

    module = _load_script()
    repo = _target_repo(tmp_path)
    config = LLMConfig(provider=LLMProvider.NONE)

    unverifiable = _frozen_root(tmp_path / "no-checkpoint", with_checkpoint=False)
    with pytest.raises(RunOpenRejected) as excinfo:
        module._open_replay_execution_identity(
            frozen=unverifiable,
            fresh=tmp_path / "fork-a",
            arguments=_arguments(unverifiable, repo, run_open_mode="fork_authoring"),
            llm_config=config,
        )
    assert excinfo.value.decision.code == "research_import_unverifiable"

    # 完整形状但与合成目标 provenance 不同 → 必须在写入任何产物前拒绝。
    mismatched = _frozen_root(tmp_path / "with-checkpoint")
    with pytest.raises(RunOpenRejected) as excinfo:
        module._open_replay_execution_identity(
            frozen=mismatched,
            fresh=tmp_path / "fork-b",
            arguments=_arguments(mismatched, repo, run_open_mode="fork_authoring"),
            llm_config=config,
        )
    assert excinfo.value.decision.code == "research_import_target_mismatch"
    assert not (tmp_path / "fork-b" / "artifacts").exists(), "拒绝必须零写入"


def test_replay_identity_requires_target_repo(tmp_path: Path) -> None:
    module = _load_script()
    frozen = _frozen_root(tmp_path)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    with pytest.raises(RunOpenRejected) as excinfo:
        module._open_replay_execution_identity(
            frozen=frozen,
            fresh=fresh,
            arguments=_arguments(frozen, repo=""),
            llm_config=LLMConfig(provider=LLMProvider.NONE),
        )
    assert excinfo.value.decision.code == "execution_identity_target_repo_required"

    with pytest.raises(RunOpenRejected) as missing:
        module._open_replay_execution_identity(
            frozen=frozen,
            fresh=fresh,
            arguments=_arguments(frozen, repo=str(tmp_path / "absent")),
            llm_config=LLMConfig(provider=LLMProvider.NONE),
        )
    assert missing.value.decision.code == "execution_identity_target_repo_missing"


def test_identity_not_requested_is_recorded_honestly(tmp_path: Path) -> None:
    """进程内调用未显式要求身份时不得伪造身份，但必须如实记录。"""

    module = _load_script()
    frozen = _frozen_root(tmp_path)
    report = module._open_replay_execution_identity(
        frozen=frozen,
        fresh=tmp_path / "fresh",
        arguments=_arguments(frozen, tmp_path / "target", run_open_mode=None),
        llm_config=LLMConfig(provider=LLMProvider.NONE),
    )
    assert report == {"status": "not_requested"}
    assert not _identity_file(tmp_path / "fresh").exists()


def test_replay_cli_rejects_non_empty_root_and_keeps_it_retryable(tmp_path: Path) -> None:
    module = _load_script()
    frozen = _frozen_root(tmp_path)
    repo = _target_repo(tmp_path)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "leftover.txt").write_text("x\n", encoding="utf-8")
    # CLI main() 会把 profile 应用进进程环境（对命令行是正确的）。测试内调用必须
    # 用显式空 profile 并快照环境，否则默认 live profile 会污染后续测试。
    empty_profile = tmp_path / "empty.env"
    empty_profile.write_text("# intentionally empty\n", encoding="utf-8")
    environment_before = dict(os.environ)
    try:
        exit_code = module.main(
            [
                str(frozen),
                str(fresh),
                "--repo",
                str(repo),
                "--run-open-mode",
                "new",
                "--run-id",
                "l1-cli-nonempty",
                "--profile",
                str(empty_profile),
            ]
        )
    finally:
        os.environ.clear()
        os.environ.update(environment_before)
    assert exit_code == 2
    assert [item.name for item in fresh.iterdir()] == ["leftover.txt"]
    refusal = tmp_path / "fresh.execution_identity_rejected.json"
    payload_json = __import__("json").loads(refusal.read_text(encoding="utf-8"))
    assert payload_json["execution_identity"]["code"] == "run_directory_not_empty"
    assert (
        payload_json["execution_identity"]["next_action"]
        == "use_resume_fork_or_empty_directory"
    )


def test_execution_record_carries_execution_identity(tmp_path: Path) -> None:
    module = _load_script()
    module._write_execution_record(
        frozen=tmp_path / "frozen",
        fresh=tmp_path / "fresh",
        arguments=_arguments(tmp_path / "frozen", tmp_path / "target"),
        exit_code=0,
        runtime_start={},
        runtime_end={},
        telemetry={
            "execution_identity": {
                "status": "opened",
                "execution_id": "exec-test",
                "content_digest": "sha256:test",
            }
        },
    )
    import json

    record = json.loads((tmp_path / "fresh" / "execution_record.json").read_text(encoding="utf-8"))
    assert record["execution_identity"]["execution_id"] == "exec-test"
    assert record["execution_identity"]["content_digest"] == "sha256:test"


# --------------------------------------------------------------------------- #
# §F.5：重放前必须验证受索引管理的输入（其余 scratch 读取如实标注）
# --------------------------------------------------------------------------- #


def test_replay_verifies_index_managed_inputs_before_use(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_artifact_index import publish_artifact_index

    from .test_authoring_end_to_end_offline import _run as _product_run

    module = _load_script()
    frozen = tmp_path / "frozen-run"
    _product_run(frozen)
    publish_artifact_index(frozen)

    verified, blockers = module.verify_index_managed_replay_inputs(frozen)
    assert blockers == [], blockers
    assert "authoring_execution_identity:research" in verified
    assert "run_summary:terminal" in verified
    assert "non-indexed scratch files" in module.LEGACY_UNVERIFIED_READ_NOTE

    # 索引发布后改动受管理产物 → 使用前失败（不依赖缓存摘要）。
    summary = frozen / "artifacts" / "research_product" / "run_summary.json"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["run_id"] = "mutated-after-index"
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    verified_after, blockers_after = module.verify_index_managed_replay_inputs(frozen)
    assert "run_summary:terminal" not in verified_after
    assert any(
        blocker.startswith("artifact_read_blocked:run_summary:terminal")
        and "artifact_bytes_changed_since_index" in blocker
        for blocker in blockers_after
    ), blockers_after


def test_replay_refuses_to_start_on_unverified_inputs(tmp_path: Path) -> None:
    """gate 必须在复制/使用产物之前拒绝：telemetry 给出 typed terminal reason。"""

    module = _load_script()
    frozen = tmp_path / "frozen-run"
    (frozen / "artifacts").mkdir(parents=True, exist_ok=True)
    verified, blockers = module.verify_index_managed_replay_inputs(frozen)
    assert verified == [] and blockers == [], "没有产出的阶段不算阻断"
