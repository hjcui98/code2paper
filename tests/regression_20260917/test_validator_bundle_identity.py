"""不变量 I10：验收规则变更必须改变 validator/contract identity。

"不能在同一个 receipt digest 的名义下重新解释历史 accepted/rejected"——因此执行身份
必须绑定验收规则来源（`VALIDATOR_BUNDLE_SOURCES` 的逐文件内容指纹），而不是留
`unspecified`。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from code2paper.agentic.authoring_execution_identity import (
    VALIDATOR_BUNDLE_SOURCES,
    build_run_open_identity,
    capture_validator_bundle_snapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _engine_repo(tmp_path: Path) -> Path:
    """构造一个包含全部验收来源文件的临时引擎根。"""

    root = tmp_path / "engine"
    (root / "src" / "code2paper").mkdir(parents=True)
    (root / "src" / "code2paper" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for relative in VALIDATOR_BUNDLE_SOURCES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {relative}\nVALUE = 1\n", encoding="utf-8")
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


def test_all_declared_validator_sources_exist_in_this_repository() -> None:
    """封闭集合里的每个文件都必须真实存在——否则指纹会静默漏掉验收规则。"""

    missing = [
        relative for relative in VALIDATOR_BUNDLE_SOURCES if not (REPO_ROOT / relative).is_file()
    ]
    assert missing == [], f"VALIDATOR_BUNDLE_SOURCES 指向不存在的文件: {missing}"
    snapshot = capture_validator_bundle_snapshot(REPO_ROOT)
    assert snapshot.is_usable is True
    assert len(snapshot.entries) == len(VALIDATOR_BUNDLE_SOURCES)


def test_editing_a_validator_source_changes_the_bundle_digest(tmp_path: Path) -> None:
    """I10 本体：改验收规则 → 指纹必须变。"""

    root = _engine_repo(tmp_path)
    before = capture_validator_bundle_snapshot(root)
    target = root / "src/code2paper/agentic/publication_transaction_contract.py"
    target.write_text("# changed acceptance rule\nVALUE = 2\n", encoding="utf-8")
    after = capture_validator_bundle_snapshot(root)

    assert before.digest != after.digest
    assert before.is_usable and after.is_usable
    changed = dict(before.entries)["src/code2paper/agentic/publication_transaction_contract.py"]
    assert changed != dict(after.entries)[
        "src/code2paper/agentic/publication_transaction_contract.py"
    ]


def test_missing_validator_source_is_reported_not_silently_empty(tmp_path: Path) -> None:
    root = _engine_repo(tmp_path)
    (root / "src/code2paper/agentic/writer_output_workload.py").unlink()
    snapshot = capture_validator_bundle_snapshot(root)

    assert snapshot.is_usable is False
    assert snapshot.failure_code == "validator_source_missing"
    assert "src/code2paper/agentic/writer_output_workload.py" in snapshot.missing
    # 仍然给出稳定指纹（含 failure_code），不是空值。
    assert snapshot.digest.startswith("sha256:")
    assert snapshot.digest == capture_validator_bundle_snapshot(root).digest


def test_execution_identity_binds_the_validator_bundle(tmp_path: Path) -> None:
    """同一输入、不同验收规则 → 不同执行身份（不能冒充同一个 run 的续跑）。"""

    root = _engine_repo(tmp_path)
    target_repo = tmp_path / "target"
    (target_repo / "src").mkdir(parents=True)
    (target_repo / "src" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git("init", "-q", cwd=target_repo)
    _git("add", "-A", cwd=target_repo)
    _git(
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=test",
        "commit",
        "-q",
        "-m",
        "init",
        cwd=target_repo,
    )

    first = build_run_open_identity(
        repo_path=target_repo,
        validator_bundle=capture_validator_bundle_snapshot(root),
    )
    assert first.validator_bundle_digest == capture_validator_bundle_snapshot(root).digest
    assert first.validator_bundle_digest != "unspecified"

    (root / "src/code2paper/agentic/writer_attempt_ledger.py").write_text(
        "# changed ledger acceptance rule\nVALUE = 9\n", encoding="utf-8"
    )
    second = build_run_open_identity(
        repo_path=target_repo,
        validator_bundle=capture_validator_bundle_snapshot(root),
    )
    assert second.validator_bundle_digest != first.validator_bundle_digest
    assert second.content_digest != first.content_digest
    assert (
        "validator_bundle_digest"
        in {
            key
            for key in first.compatible_fields()
            if first.compatible_fields()[key] != second.compatible_fields()[key]
        }
    )


def test_real_identity_is_not_inert(tmp_path: Path) -> None:
    """真实仓库上的身份必须绑定真实指纹（回归"unspecified"占位）。"""

    identity = build_run_open_identity(repo_path=REPO_ROOT)
    assert identity.validator_bundle_digest == capture_validator_bundle_snapshot().digest
    assert identity.validator_bundle_digest != "unspecified"
    assert identity.tokenizer_contract_digest != ""
    with pytest.raises(ValueError):
        identity.validator_bundle_digest = "sha256:tampered"  # type: ignore[misc]
