"""PR A / F02、A.1、A.5：运行身份必须是**内容**身份，且不可用输入必须在发送前停止。

审计给出的最小反例：同一目标文件已处于 `M` 状态，从实现 A 改成 B——HEAD 与
porcelain 路径状态都不变，旧实现给出同一个"目标身份"，于是 resume 会接受已被修改的
目标仓库；反过来，把同一份内容复制到另一个路径又可能被误判为不同。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from code2paper.agentic.authoring_execution_identity import (
    TARGET_SNAPSHOT_UNAVAILABLE,
    VALIDATOR_BUNDLE_UNAVAILABLE,
    build_run_open_identity,
    capture_engine_source_snapshot,
    capture_target_identity,
    capture_validator_bundle_snapshot,
    preflight_run_open,
    validate_run_open,
)
from code2paper.agentic.authoring_run_config import (
    UNKNOWN_NARRATIVE_PLAN_MODE,
    UnknownNarrativePlanMode,
    capture_effective_config_digest,
    normalize_narrative_plan_mode,
)
from code2paper.llm.client import LLMConfig, LLMProvider

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _git_repo(tmp_path: Path, name: str = "target") -> Path:
    root = tmp_path / name
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "core.py").write_text("IMPLEMENTATION = 'A'\n", encoding="utf-8")
    (root / "src" / "aux.py").write_text("AUX = 1\n", encoding="utf-8")
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


# --------------------------------------------------------------------------- #
# F02：目标内容身份
# --------------------------------------------------------------------------- #


def test_target_identity_carries_content_not_commit(tmp_path: Path) -> None:
    root = _git_repo(tmp_path)
    identity = capture_target_identity(root)

    assert identity.is_usable is True
    assert identity.source_snapshot_digest.startswith("sha256:")
    assert identity.project_tree_hash.startswith("sha256:")
    assert identity.source_manifest_digest.startswith("sha256:")
    assert identity.file_count >= 2
    # 内容摘要不是 commit，也不是 porcelain 摘要。
    assert identity.source_snapshot_digest != identity.commit_sha
    assert identity.source_snapshot_digest != identity.dirty_digest


def test_target_dirty_content_change_invalidates_resume(tmp_path: Path) -> None:
    """审计最小反例：文件保持 M 状态、HEAD 不变，只改内容。"""

    root = _git_repo(tmp_path)
    target = root / "src" / "core.py"
    target.write_text("IMPLEMENTATION = 'B'\n", encoding="utf-8")

    first = capture_target_identity(root)
    # 状态与 commit 完全没变——旧实现因此给出同一身份。
    assert first.commit_sha
    target.write_text("IMPLEMENTATION = 'C'\n", encoding="utf-8")
    second = capture_target_identity(root)

    assert first.commit_sha == second.commit_sha
    assert first.source_snapshot_digest != second.source_snapshot_digest
    assert first.project_tree_hash != second.project_tree_hash

    out_root = tmp_path / "run"
    out_root.mkdir()
    from code2paper.agentic.authoring_execution_identity import (
        create_or_validate_execution_identity,
    )

    # 用**改动前**的内容建立身份并落盘，然后保持 M 状态改内容。
    original = build_run_open_identity(repo_path=root)
    assert validate_run_open(out_root, "new", original).allowed is True
    create_or_validate_execution_identity(out_root, original)
    target.write_text("IMPLEMENTATION = 'D'\n", encoding="utf-8")
    changed_identity = build_run_open_identity(repo_path=root)
    decision = validate_run_open(out_root, "resume", changed_identity)
    assert decision.allowed is False
    assert decision.code == "resume_identity_mismatch"
    assert "target_repo_snapshot_digest" in decision.mismatched_fields


def test_same_target_content_in_another_path_has_same_content_identity(tmp_path: Path) -> None:
    """路径是诊断信息，不参与"相同内容能否复用"（审计 §A.1.3）。"""

    root = _git_repo(tmp_path)
    (root / "src" / "core.py").write_text("IMPLEMENTATION = 'M'\n", encoding="utf-8")
    first = capture_target_identity(root)

    moved = tmp_path / "elsewhere" / "target"
    moved.parent.mkdir(parents=True)
    shutil.copytree(root, moved, symlinks=True)
    second = capture_target_identity(moved)

    assert first.project_root != second.project_root
    assert first.source_snapshot_digest == second.source_snapshot_digest
    assert first.project_tree_hash == second.project_tree_hash
    assert first.source_manifest_digest == second.source_manifest_digest

    left = build_run_open_identity(repo_path=root)
    right = build_run_open_identity(repo_path=moved)
    assert left.content_digest == right.content_digest, "同内容不同路径必须同身份"


def test_unusable_target_snapshot_is_not_a_fake_identity(tmp_path: Path) -> None:
    """取不到内容快照时不得给出"看起来可用"的 sha256（审计 §A.1.4）。"""

    missing = tmp_path / "not-a-repo"
    identity = capture_target_identity(missing)
    assert identity.is_usable is False
    assert identity.failure_code
    assert TARGET_SNAPSHOT_UNAVAILABLE in identity.failure_code
    with pytest.raises(ValueError, match=TARGET_SNAPSHOT_UNAVAILABLE):
        build_run_open_identity(repo_path=missing)
    # 预检路径把同一事实报成拒绝码，而不是抛穿。
    decision = preflight_run_open(missing, "new", repo_path=missing)
    assert decision.allowed is False
    assert decision.code.startswith(TARGET_SNAPSHOT_UNAVAILABLE)


# --------------------------------------------------------------------------- #
# A.1.5：验收规则来源不可用
# --------------------------------------------------------------------------- #


def test_missing_validator_source_blocks_before_provider_send(tmp_path: Path) -> None:
    bundle = capture_validator_bundle_snapshot(
        REPO_ROOT, sources=("src/code2paper/agentic/does_not_exist.py",)
    )
    assert bundle.is_usable is False
    assert bundle.digest.startswith("sha256:"), "仍给出稳定指纹，但不是可用身份"

    target = _git_repo(tmp_path)
    with pytest.raises(ValueError, match=VALIDATOR_BUNDLE_UNAVAILABLE):
        build_run_open_identity(repo_path=target, validator_bundle=bundle)

    decision = preflight_run_open(tmp_path / "run", "new", repo_path=target)
    assert decision.allowed is True, "preflight_run_open 自身不接收 bundle：它使用当前工作树的 bundle"

    from code2paper.agentic.live_admission_preflight import preflight_live_admission

    admission = preflight_live_admission(
        tmp_path / "run",
        repo_path=target,
        llm_config=LLMConfig(provider=LLMProvider.OPENAI, model="m"),
        run_open_mode="new",
        validator_bundle=bundle,
    )
    assert admission.ready is False
    assert "validator_bundle_unavailable" in admission.blockers
    gate = next(g for g in admission.gates if g.name == "validator_bundle_identity")
    assert gate.passed is False


# --------------------------------------------------------------------------- #
# A.1.6：有效配置身份
# --------------------------------------------------------------------------- #


def test_unknown_narrative_mode_is_rejected() -> None:
    assert normalize_narrative_plan_mode("") == "v3"
    assert normalize_narrative_plan_mode("V4") == "v4"
    assert normalize_narrative_plan_mode("shadow") == "shadow"
    with pytest.raises(UnknownNarrativePlanMode) as excinfo:
        normalize_narrative_plan_mode("v5")
    assert UNKNOWN_NARRATIVE_PLAN_MODE in str(excinfo.value)


def test_unknown_narrative_mode_is_rejected_by_the_plan_builder(monkeypatch) -> None:
    """计划选择 owner 本身必须拒绝未知值（不能只在身份层拒绝）。"""

    from code2paper.agentic.publication_method_writer import _build_narrative_plan_v3

    monkeypatch.setenv("CODE2PAPER_INTENT_NARRATIVE_PLAN", "v9")
    with pytest.raises(UnknownNarrativePlanMode):
        _build_narrative_plan_v3(contexts=(), story_spine=(), formula_packages=())


def test_unknown_narrative_mode_blocks_admission(tmp_path: Path) -> None:
    from code2paper.agentic.live_admission_preflight import preflight_live_admission

    target = _git_repo(tmp_path)
    admission = preflight_live_admission(
        tmp_path / "run",
        repo_path=target,
        llm_config=LLMConfig(provider=LLMProvider.OPENAI, model="m"),
        run_open_mode="new",
        narrative_plan_mode="v9",
    )
    assert admission.ready is False
    assert UNKNOWN_NARRATIVE_PLAN_MODE in admission.blockers


def test_effective_config_is_bound_into_identity(tmp_path: Path) -> None:
    """同一输入在不同 narrative/context 模式下不得共享执行身份（I2）。"""

    target = _git_repo(tmp_path)
    config = LLMConfig(provider=LLMProvider.NONE)
    engine = capture_engine_source_snapshot(REPO_ROOT)

    v3 = build_run_open_identity(
        repo_path=target,
        llm_config=config,
        engine_snapshot=engine,
        narrative_plan_mode="v3",
        authoring_context_mode="legacy",
    )
    v4 = build_run_open_identity(
        repo_path=target,
        llm_config=config,
        engine_snapshot=engine,
        narrative_plan_mode="v4",
        authoring_context_mode="unified",
    )
    assert v3.effective_config_digest != v4.effective_config_digest
    assert v3.content_digest != v4.content_digest
    assert "effective_config_digest" in v3.compatible_fields()
    # 模式未变时身份必须稳定（否则 resume 永远失败）。
    again = build_run_open_identity(
        repo_path=target,
        llm_config=config,
        engine_snapshot=engine,
        narrative_plan_mode="v3",
        authoring_context_mode="legacy",
    )
    assert again.content_digest == v3.content_digest


def test_effective_config_digest_covers_protocol_and_tokenizer() -> None:
    base = capture_effective_config_digest(
        narrative_plan_mode="v3",
        authoring_context_mode="unified",
        tokenizer_identity="tokenizer:a",
        validator_bundle_digest="sha256:v",
        environment={"CODE2PAPER_LLM_STREAM_STRUCTURED": "1"},
    )
    other_protocol = capture_effective_config_digest(
        narrative_plan_mode="v3",
        authoring_context_mode="unified",
        tokenizer_identity="tokenizer:a",
        validator_bundle_digest="sha256:v",
        environment={"CODE2PAPER_LLM_STREAM_STRUCTURED": "0"},
    )
    other_tokenizer = capture_effective_config_digest(
        narrative_plan_mode="v3",
        authoring_context_mode="unified",
        tokenizer_identity="tokenizer:b",
        validator_bundle_digest="sha256:v",
        environment={"CODE2PAPER_LLM_STREAM_STRUCTURED": "1"},
    )
    assert base["digest"] != other_protocol["digest"]
    assert base["digest"] != other_tokenizer["digest"]
    assert base["payload"]["narrative_plan_mode"] == "v3"
    json.dumps(base["payload"])  # 必须可序列化进身份/报告
