from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".venv", "venv", "node_modules", "outputs",
    "output", "results", "checkpoints", ".code2paper", ".llm_cache",
}
DEFAULT_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite-shm", ".sqlite-wal"}


class SnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SnapshotFile(SnapshotModel):
    path: str
    kind: Literal["file", "symlink"] = "file"
    size: int = 0
    content_digest: str
    link_target: str = ""


class RepoSnapshot(SnapshotModel):
    schema_version: str = "2.0"
    snapshot_id: str
    project_root: str
    project_tree_hash: str
    hash_algorithm: str = "sha256"
    producer_version: str = "code2paper-agentic-p1"
    created_at: str = ""
    included_files: list[SnapshotFile] = Field(default_factory=list)
    excluded_path_policy: list[str] = Field(default_factory=list)
    symlink_policy: str = "record_link_target_without_external_follow"
    submodule_policy: str = "hash_checked_out_worktree_excluding_nested_git_metadata"
    git_commit: str = ""
    git_branch: str = ""
    git_dirty: bool | None = None


def build_repo_snapshot(project_root: str | Path) -> RepoSnapshot:
    root = Path(project_root).resolve()
    files: list[SnapshotFile] = []
    for path in _iter_snapshot_paths(root):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            target = os.readlink(path)
            digest = _digest_bytes(("symlink:" + target).encode("utf-8"))
            files.append(SnapshotFile(path=relative, kind="symlink", content_digest=digest, link_target=target))
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        files.append(SnapshotFile(path=relative, size=len(data), content_digest=_digest_bytes(data)))
    files.sort(key=lambda item: item.path)
    tree_payload = [item.model_dump(mode="json") for item in files]
    tree_hash = _digest_json(tree_payload)
    commit, branch, dirty = _git_identity(root)
    return RepoSnapshot(
        snapshot_id="repo:" + tree_hash.removeprefix("sha256:"),
        project_root=str(root),
        project_tree_hash=tree_hash,
        created_at=datetime.now(timezone.utc).isoformat(),
        included_files=files,
        excluded_path_policy=sorted(DEFAULT_EXCLUDED_DIRS) + sorted(DEFAULT_EXCLUDED_SUFFIXES),
        git_commit=commit,
        git_branch=branch,
        git_dirty=dirty,
    )


def write_repo_snapshot(path: str | Path, snapshot: RepoSnapshot) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_repo_snapshot(path: str | Path) -> RepoSnapshot:
    return RepoSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))


def snapshot_is_current(snapshot: RepoSnapshot) -> bool:
    return build_repo_snapshot(snapshot.project_root).project_tree_hash == snapshot.project_tree_hash


def _iter_snapshot_paths(root: Path):
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirnames[:] = sorted(
            name for name in dirnames
            if name not in DEFAULT_EXCLUDED_DIRS and not _excluded_name(name)
        )
        for name in sorted(filenames):
            if _excluded_name(name):
                continue
            path = current_path / name
            if path.suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES:
                continue
            yield path
        for name in sorted(dirnames):
            path = current_path / name
            if path.is_symlink():
                yield path


def _excluded_name(name: str) -> bool:
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def _git_identity(root: Path) -> tuple[str, str, bool | None]:
    def run(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain") if commit else ""
    return commit, branch, bool(status) if commit else None


def _digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _digest_json(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _digest_bytes(data)
