"""WP1：执行身份、引擎内容指纹与目录准入（方案 §5、§12）。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from code2paper.agentic import authoring_execution_identity as identity_mod
from code2paper.agentic.authoring_execution_identity import (
    ENGINE_ROOT_UNRESOLVED,
    RESEARCH_IMPORT_UNVERIFIABLE,
    RESUME_EXHAUSTED_INVOCATION,
    RESUME_IDENTITY_LEGACY,
    RESUME_IDENTITY_MISMATCH,
    RUN_DIRECTORY_NOT_EMPTY,
    EngineSourceSnapshot,
    RunLeaseHeld,
    RunOpenRejected,
    acquire_run_lease,
    build_execution_identity,
    capture_engine_source_snapshot,
    create_or_validate_execution_identity,
    load_execution_identity,
    scan_exhausted_invocations,
    validate_run_open,
)

from . import incident_archive


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _engine_repo(tmp_path: Path, name: str = "engine") -> Path:
    """构造一个可解析的引擎根：pyproject + src/code2paper + 一次提交。"""

    root = tmp_path / name
    (root / "src" / "code2paper").mkdir(parents=True)
    (root / "src" / "code2paper" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
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


def _identity(**overrides: object):
    payload: dict[str, object] = {
        "target_repo_snapshot_digest": "repo:target",
        "target_project_tree_hash": "sha256:tree",
        "intent_content_digest": "sha256:intent-a",
        "claims_digest": "sha256:claims",
        "profile_digest": "sha256:profile",
        "model_identity_digest": "sha256:model",
        "prompt_bundle_digest": "sha256:prompt",
        "tokenizer_contract_digest": "sha256:tokenizer",
        "validator_bundle_digest": "sha256:validator",
        "engine_snapshot": EngineSourceSnapshot(
            engine_root="/engine",
            commit_sha="a" * 40,
            branch="main",
            source_digest="sha256:engine",
        ),
    }
    payload.update(overrides)
    return build_execution_identity(**payload)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 引擎内容指纹
# --------------------------------------------------------------------------- #


def test_dirty_content_changes_same_status(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_context_contract import dirty_manifest_digest

    root = _engine_repo(tmp_path)
    dirty = root / "src" / "code2paper" / "engine.py"
    dirty.write_text("VALUE = 1\n", encoding="utf-8")
    legacy_first = dirty_manifest_digest(root)
    first = capture_engine_source_snapshot(root)

    dirty.write_text("VALUE = 2\n", encoding="utf-8")
    legacy_second = dirty_manifest_digest(root)
    second = capture_engine_source_snapshot(root)

    assert first.source_digest != second.source_digest
    assert [(item.path, item.status) for item in first.entries] == [
        (item.path, item.status) for item in second.entries
    ]
    # 旧的 porcelain 状态摘要对内容变化是盲的——这正是它不能用于 resume 的原因。
    assert legacy_first == legacy_second
    assert first.entries[0].digest != second.entries[0].digest


def test_engine_digest_ignores_run_outputs_and_caches(tmp_path: Path) -> None:
    root = _engine_repo(tmp_path)
    baseline = capture_engine_source_snapshot(root)

    for relative in (
        "artifacts/runs/2026-09-17-demo/run_summary.json",
        "logs/run.log",
        "outputs/paper.md",
        ".pytest_cache/v/cache/lastfailed",
        "src/code2paper/__pycache__/engine.cpython-313.pyc",
        ".env.local",
        "state.sqlite",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")

    after = capture_engine_source_snapshot(root)
    assert after.source_digest == baseline.source_digest
    assert after.excluded_count >= 7


def test_engine_digest_is_path_independent(tmp_path: Path) -> None:
    first_root = _engine_repo(tmp_path, "engine-a")
    second_root = tmp_path / "engine-b"
    shutil.copytree(first_root, second_root)

    for root in (first_root, second_root):
        (root / "src" / "code2paper" / "dirty.py").write_text("X = 1\n", encoding="utf-8")

    first = capture_engine_source_snapshot(first_root)
    second = capture_engine_source_snapshot(second_root)
    assert first.engine_root != second.engine_root
    assert first.source_digest == second.source_digest


def test_engine_root_unresolved_is_reported(tmp_path: Path) -> None:
    snapshot = capture_engine_source_snapshot(tmp_path)
    assert snapshot.failure_code == ENGINE_ROOT_UNRESOLVED
    assert snapshot.is_usable is False
    with pytest.raises(ValueError, match="engine_identity_unavailable"):
        build_execution_identity(
            target_repo_snapshot_digest="repo:target",
            target_project_tree_hash="sha256:tree",
            intent_content_digest="sha256:intent",
            claims_digest="sha256:claims",
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
            engine_snapshot=snapshot,
        )


# --------------------------------------------------------------------------- #
# 身份模型
# --------------------------------------------------------------------------- #


def test_identity_is_deterministic_and_intent_sensitive() -> None:
    first = _identity()
    second = _identity()
    assert first.execution_id == second.execution_id
    assert first.content_digest == second.content_digest

    changed = _identity(intent_content_digest="sha256:intent-b")
    assert changed.execution_id != first.execution_id
    assert changed.content_digest != first.content_digest

    # engine_root 只作诊断，不参与身份。
    moved = _identity(
        engine_snapshot=EngineSourceSnapshot(
            engine_root="/elsewhere",
            commit_sha="a" * 40,
            branch="main",
            source_digest="sha256:engine",
        )
    )
    assert moved.content_digest == first.content_digest


def test_identity_rejects_missing_required_digest() -> None:
    with pytest.raises(ValueError, match="requires claims_digest"):
        build_execution_identity(
            target_repo_snapshot_digest="repo:target",
            target_project_tree_hash="sha256:tree",
            intent_content_digest="sha256:intent",
            claims_digest="",
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
            engine_snapshot=EngineSourceSnapshot(
                engine_root="/engine",
                commit_sha="a" * 40,
                branch="main",
                source_digest="sha256:engine",
            ),
        )


# --------------------------------------------------------------------------- #
# 目录准入状态机
# --------------------------------------------------------------------------- #


def test_new_mode_rejects_nonempty_root(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    out_root.mkdir()
    (out_root / "artifacts").mkdir()
    (out_root / "artifacts" / "run_summary.json").write_text("{}", encoding="utf-8")

    decision = validate_run_open(out_root, "new", _identity())
    assert decision.allowed is False
    assert decision.code == RUN_DIRECTORY_NOT_EMPTY
    assert decision.allowed_next_action == "use_resume_fork_or_empty_directory"
    # 拒绝不写任何东西
    assert sorted(item.name for item in out_root.rglob("*")) == [
        "artifacts",
        "run_summary.json",
    ]


def test_new_mode_allows_empty_or_missing_root(tmp_path: Path) -> None:
    decision = validate_run_open(tmp_path / "fresh", "new", _identity())
    assert decision.allowed is True
    assert decision.effective_mode == "new"
    assert decision.allowed_next_action == "run"
    assert (tmp_path / "fresh").exists() is False


def test_resume_matches_identity_and_preserves_budget(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    out_root.mkdir()
    identity = _identity(creation_mode="new")
    path, status = create_or_validate_execution_identity(out_root, identity)
    assert status == "created"
    before = Path(path).read_bytes()

    assert load_execution_identity(out_root) is not None
    decision = validate_run_open(out_root, "resume", identity)
    assert decision.allowed is True
    assert decision.code == "resume_identity_matched"
    assert decision.allowed_next_action == "resume"

    # 再次打开是 validate，不改写身份、不刷新预算。
    path_again, status_again = create_or_validate_execution_identity(out_root, identity)
    assert status_again == "validated"
    assert Path(path_again).read_bytes() == before


def test_resume_identity_mismatch_reports_fields(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    out_root.mkdir()
    create_or_validate_execution_identity(out_root, _identity())

    changed = _identity(
        engine_snapshot=EngineSourceSnapshot(
            engine_root="/engine",
            commit_sha="b" * 40,
            branch="main",
            source_digest="sha256:engine",
        )
    )
    decision = validate_run_open(out_root, "resume", changed)
    assert decision.allowed is False
    assert decision.code == RESUME_IDENTITY_MISMATCH
    assert decision.mismatched_fields == ("engine_commit_sha",)
    assert decision.allowed_next_action == "fork_authoring_or_explicit_new"

    with pytest.raises(ValueError, match=RESUME_IDENTITY_MISMATCH):
        create_or_validate_execution_identity(out_root, changed)


def test_resume_reports_exhausted_invocation(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    out_root.mkdir()
    identity = _identity()
    create_or_validate_execution_identity(out_root, identity)

    decision = validate_run_open(
        out_root, "resume", identity, exhausted_invocations=("inv:writer:MA-S3:page:x",)
    )
    assert decision.allowed is False
    assert decision.code == RESUME_EXHAUSTED_INVOCATION
    assert decision.allowed_next_action == "fork_authoring_with_new_contract"
    assert decision.exhausted_invocations == ("inv:writer:MA-S3:page:x",)


def test_legacy_identity_cannot_be_strictly_resumed(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    (out_root / "artifacts" / "research_product").mkdir(parents=True)
    (out_root / "artifacts" / "research_product" / "run_identity_v1.json").write_text(
        json.dumps({"schema_version": "1.0"}), encoding="utf-8"
    )

    decision = validate_run_open(out_root, "resume", _identity())
    assert decision.allowed is False
    assert decision.code == RESUME_IDENTITY_LEGACY
    assert decision.allowed_next_action == "explicit_fork_authoring"

    auto = validate_run_open(out_root, "auto", _identity())
    assert auto.allowed is False
    assert auto.code == RUN_DIRECTORY_NOT_EMPTY


def test_fork_requires_empty_directory_and_verifiable_research(tmp_path: Path) -> None:
    out_root = tmp_path / "fork"
    verifiable = validate_run_open(
        out_root, "fork_authoring", _identity(creation_mode="fork_authoring")
    )
    assert verifiable.allowed is True
    assert verifiable.effective_mode == "fork_authoring"

    unverifiable = validate_run_open(
        out_root,
        "fork_authoring",
        _identity(creation_mode="fork_authoring"),
        research_import_verifiable=False,
    )
    assert unverifiable.allowed is False
    assert unverifiable.code == RESEARCH_IMPORT_UNVERIFIABLE

    out_root.mkdir()
    (out_root / "leftover.json").write_text("{}", encoding="utf-8")
    blocked = validate_run_open(
        out_root, "fork_authoring", _identity(creation_mode="fork_authoring")
    )
    assert blocked.allowed is False
    assert blocked.code == RUN_DIRECTORY_NOT_EMPTY


# --------------------------------------------------------------------------- #
# 单写者租约
# --------------------------------------------------------------------------- #


def test_lease_is_idempotent_in_process_and_exclusive_after_release(
    tmp_path: Path,
) -> None:
    out_root = tmp_path / "run"
    lease = acquire_run_lease(out_root, execution_id="exec-a")
    try:
        # 同一进程重复获取返回同一租约（该进程本来就是写者）。
        assert acquire_run_lease(out_root, execution_id="exec-b") is lease
    finally:
        lease.release()

    second = acquire_run_lease(out_root, execution_id="exec-b")
    assert second is not lease
    second.release()


def test_lease_is_exclusive_across_processes(tmp_path: Path) -> None:
    out_root = tmp_path / "run"
    workspace = Path(__file__).resolve().parents[2]
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import sys, time;"
                "from pathlib import Path;"
                "sys.path.insert(0, 'src');"
                "from code2paper.agentic.authoring_execution_identity import acquire_run_lease;"
                f"lease = acquire_run_lease(Path(r'{out_root}'), execution_id='child');"
                "print('locked', flush=True);"
                "time.sleep(30)"
            ),
        ],
        cwd=str(workspace),
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert "locked" in child.stdout.readline()
        with pytest.raises(RunLeaseHeld):
            acquire_run_lease(out_root, execution_id="parent")
    finally:
        child.terminate()
        child.wait(timeout=30)

    released = acquire_run_lease(out_root, execution_id="parent")
    released.release()


def test_resume_refuses_unknown_engine_identity(tmp_path: Path) -> None:
    """引擎指纹不可用时不能冒充严格 resume（但新执行仍可继续）。"""

    out_root = tmp_path / "run"
    out_root.mkdir()
    unknown_engine = _identity(
        engine_snapshot=EngineSourceSnapshot(
            engine_root="",
            commit_sha="unknown",
            branch="",
            source_digest="",
            failure_code=ENGINE_ROOT_UNRESOLVED,
        ),
        require_usable_engine=False,
    )
    create_or_validate_execution_identity(out_root, unknown_engine)

    decision = validate_run_open(out_root, "resume", unknown_engine)
    assert decision.allowed is False
    assert decision.code == "resume_engine_identity_unavailable"
    assert decision.allowed_next_action == "explicit_fork_authoring_or_restore_engine_fingerprint"

    # 新执行允许继续，但身份如实记录 unknown 引擎。
    fresh = validate_run_open(tmp_path / "fresh", "new", unknown_engine)
    assert fresh.allowed is True


def test_fork_requires_verifiable_research_import(tmp_path: Path) -> None:
    from code2paper.agentic.authoring_execution_identity import (
        preflight_run_open,
        verify_research_import,
    )

    checkpoint = (
        incident_archive.archive_root()
        / "artifacts/research_product/research_stage_checkpoint_v1.json"
    )
    verifiable, digest, _detail = verify_research_import(checkpoint)
    assert verifiable is True
    assert digest.startswith("sha256:")

    target = _engine_repo(tmp_path, "target")
    allowed = preflight_run_open(
        tmp_path / "fork",
        "fork_authoring",
        repo_path=target,
        research_import_path=checkpoint,
    )
    assert allowed.allowed is True
    assert allowed.effective_mode == "fork_authoring"

    stub = tmp_path / "stub.json"
    stub.write_text("{}", encoding="utf-8")
    refused = preflight_run_open(
        tmp_path / "fork-stub",
        "fork_authoring",
        repo_path=target,
        research_import_path=stub,
    )
    assert refused.allowed is False
    assert refused.code == RESEARCH_IMPORT_UNVERIFIABLE

    missing = preflight_run_open(
        tmp_path / "fork-missing",
        "fork_authoring",
        repo_path=target,
        research_import_path=tmp_path / "nope.json",
    )
    assert missing.allowed is False
    assert missing.code == RESEARCH_IMPORT_UNVERIFIABLE


# --------------------------------------------------------------------------- #
# 真实事故归档：已耗尽的旧目录不能再被当作新实验
# --------------------------------------------------------------------------- #


def test_incident_archive_reports_exhausted_invocation() -> None:
    exhausted = scan_exhausted_invocations(incident_archive.archive_root())
    assert exhausted == (incident_archive.INCIDENT_INVOCATION,)


def test_incident_archive_refuses_resume_and_auto_open() -> None:
    root = incident_archive.archive_root()
    before = sorted(str(item.relative_to(root)) for item in root.rglob("*"))

    resume = validate_run_open(root, "resume", _identity())
    assert resume.allowed is False
    assert resume.code == RESUME_IDENTITY_LEGACY
    assert resume.exhausted_invocations == (incident_archive.INCIDENT_INVOCATION,)

    auto = validate_run_open(root, "auto", _identity())
    assert auto.allowed is False
    assert auto.code == RUN_DIRECTORY_NOT_EMPTY

    new = validate_run_open(root, "new", _identity())
    assert new.allowed is False
    assert new.code == RUN_DIRECTORY_NOT_EMPTY

    after = sorted(str(item.relative_to(root)) for item in root.rglob("*"))
    assert after == before, "目录准入拒绝时不得写入或删除任何文件"


# --------------------------------------------------------------------------- #
# 产品入口接线：准入先于任何模型调用与产物写入
# --------------------------------------------------------------------------- #


def test_wrapper_refuses_open_before_impl(tmp_path: Path, monkeypatch) -> None:
    from code2paper.agentic import autonomous_method_agent as agent_mod

    calls: list[str] = []

    def _spy(**kwargs: object) -> None:
        calls.append("impl")
        raise AssertionError("准入被拒绝时不得进入实现体")

    monkeypatch.setattr(agent_mod, "_run_autonomous_method_agent_impl", _spy)

    out_root = tmp_path / "run"
    (out_root / "artifacts").mkdir(parents=True)
    (out_root / "artifacts" / "run_summary.json").write_text("{}", encoding="utf-8")
    target = _engine_repo(tmp_path, "target")

    with pytest.raises(RunOpenRejected) as excinfo:
        agent_mod.run_autonomous_method_agent(
            repo_path=target, out_root=out_root, run_open_mode="new"
        )
    assert excinfo.value.decision.code == RUN_DIRECTORY_NOT_EMPTY
    assert calls == []


def test_wrapper_creates_identity_on_fresh_root(tmp_path: Path, monkeypatch) -> None:
    from code2paper.agentic import autonomous_method_agent as agent_mod

    monkeypatch.setattr(
        agent_mod, "_run_autonomous_method_agent_impl", lambda **kwargs: "stub-result"
    )
    out_root = tmp_path / "fresh"
    target = _engine_repo(tmp_path, "target")

    assert (
        agent_mod.run_autonomous_method_agent(
            repo_path=target, out_root=out_root, run_open_mode="new"
        )
        == "stub-result"
    )
    identity = load_execution_identity(out_root)
    assert identity is not None
    assert identity.engine_commit_sha != "unknown"
    assert identity.target_repo_snapshot_digest not in {"", "unknown"}
    assert identity.creation_mode == "new"


def test_wrapper_auto_resume_keeps_identity_bytes(tmp_path: Path, monkeypatch) -> None:
    from code2paper.agentic import autonomous_method_agent as agent_mod
    from code2paper.agentic.authoring_execution_identity import execution_identity_path

    monkeypatch.setattr(
        agent_mod, "_run_autonomous_method_agent_impl", lambda **kwargs: "stub-result"
    )
    out_root = tmp_path / "run"
    target = _engine_repo(tmp_path, "target")

    agent_mod.run_autonomous_method_agent(
        repo_path=target, out_root=out_root, run_open_mode="new"
    )
    path = execution_identity_path(out_root)
    before = path.read_bytes()

    agent_mod.run_autonomous_method_agent(
        repo_path=target, out_root=out_root, run_open_mode="auto"
    )
    assert path.read_bytes() == before, "resume 不得改写已冻结的执行身份"
