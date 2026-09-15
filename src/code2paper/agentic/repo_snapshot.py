from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.mechanism_context_models import (
    canonical_json_bytes,
    sha256_digest,
)


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

    @property
    def content_digest(self) -> str:
        """Content identity of the frozen revision, excluding observations.

        ``created_at``, the absolute ``project_root`` and the git observation
        fields describe when and where the snapshot was taken; they must not
        change the identity of the source a closure was compiled from.  The
        compiler's source-digest helper prefers this property, so a snapshot
        provider without it would otherwise leak its capture timestamp into
        the archive, page ids and plan digests.
        """

        identity = {
            "snapshot_id": str(self.snapshot_id),
            "project_tree_hash": str(self.project_tree_hash),
            "hash_algorithm": str(self.hash_algorithm),
            "producer_version": str(self.producer_version),
            "included_files": [
                {
                    "path": str(item.path),
                    "kind": str(item.kind),
                    "size": int(item.size),
                    "content_digest": str(item.content_digest),
                    "link_target": str(item.link_target),
                }
                for item in sorted(self.included_files, key=lambda item: item.path)
            ],
        }
        return sha256_digest(canonical_json_bytes(identity))


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


def repo_snapshot_identity_digest(snapshot: RepoSnapshot) -> str:
    """Return the stable digest that binds consumers to one snapshot.

    ``created_at``, ``project_root`` and git working-tree metadata describe
    where a snapshot was produced and must not change replay identity.  The
    included file records and their project-tree hash are the immutable
    repository boundary.  Keeping this helper beside the snapshot builder
    gives product and replay one canonical representation.
    """

    payload = {
        "schema_version": snapshot.schema_version,
        "snapshot_id": snapshot.snapshot_id,
        "project_tree_hash": snapshot.project_tree_hash,
        "hash_algorithm": snapshot.hash_algorithm,
        "included_files": [
            item.model_dump(mode="json")
            for item in sorted(snapshot.included_files, key=lambda value: value.path)
        ],
        "excluded_path_policy": tuple(snapshot.excluded_path_policy),
        "symlink_policy": snapshot.symlink_policy,
        "submodule_policy": snapshot.submodule_policy,
    }
    return _digest_json(payload)


def snapshot_is_current(snapshot: RepoSnapshot) -> bool:
    return build_repo_snapshot(snapshot.project_root).project_tree_hash == snapshot.project_tree_hash


#: Source partitions the verified reader may return as text.  Excluded kinds
#: still participate in digest verification (a caller can detect drift) but
#: are never handed to a consumer as repository source authority.
_EXCLUDED_SOURCE_KINDS = frozenset({
    "vendor", "generated", "submodule", "dataset_or_checkpoint",
})

#: Failure code the verified reader records when a consumer asks for a path
#: whose frozen manifest classifies it outside the readable source partition.
PARTITION_EXCLUSION_FAILURE_CODE = "unified_source_partition_excluded"


def split_source_read_failures(
    failures: Any,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split reader failures into (blocking, declared partition exclusions).

    A partition exclusion is a *classification outcome* of the frozen
    manifest: the consumer asked for a path that the revision already declared
    as vendor/generated/submodule/dataset-or-checkpoint.  It must stay visible,
    but it is not evidence that source bytes drifted.  Every other recorded
    failure (escape, unlisted path, missing/unreadable file, digest drift,
    symlink, non-text) keeps blocking the unified lane.
    """

    blocking: list[str] = []
    excluded: list[str] = []
    for item in failures or ():
        text = str(item or "").strip()
        if not text:
            continue
        if text.startswith(PARTITION_EXCLUSION_FAILURE_CODE + ":"):
            excluded.append(text)
        else:
            blocking.append(text)
    return tuple(dict.fromkeys(blocking)), tuple(dict.fromkeys(excluded))


def _normalize_relative_path(path: str) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    normalized = os.path.normpath(raw).replace("\\", "/")
    if normalized in {".", ""} or normalized.startswith("../") or normalized.startswith("/"):
        return ""
    if normalized == ".." or "/../" in normalized:
        return ""
    return normalized


class VerifiedSourceBytes:
    """Digest-verified source text for one frozen repository revision.

    The reader resolves every path against the snapshot root, checks the
    source manifest partition and path boundary, verifies the content digest
    against both the manifest entry and the snapshot record, and only then
    returns text.  Bytes are read once and cached, so the revision keeps the
    exact source it was loaded with: editing the working tree afterwards does
    not change an already-loaded revision, while a *new* reader reports the
    drift.  Binary payloads (or files that are not valid UTF-8) are verified
    by digest only and are never returned as source text.
    """

    def __init__(
        self,
        *,
        project_root: str | Path,
        source_manifest: object | None = None,
        repo_snapshot: RepoSnapshot | None = None,
        allowed_source_kinds: object | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.source_manifest = source_manifest
        self.repo_snapshot = repo_snapshot
        self.allowed_source_kinds = frozenset(
            str(item) for item in (allowed_source_kinds or ("first_party_executable",))
        )
        self.failures: list[str] = []
        self._cache: dict[str, str] = {}
        self._manifest_entries: dict[str, object] = {}
        for entry in (getattr(source_manifest, "entries", ()) or ()):
            path = _normalize_relative_path(str(getattr(entry, "path", "") or ""))
            if path:
                self._manifest_entries[path] = entry
        self._snapshot_files: dict[str, SnapshotFile] = {}
        for item in (getattr(repo_snapshot, "included_files", ()) or ()):
            path = _normalize_relative_path(str(getattr(item, "path", "") or ""))
            if path:
                self._snapshot_files[path] = item

    # -- identity ---------------------------------------------------------
    # The compiler may derive the closure's repository identity from its
    # source provider when the graph/symbol index do not carry it, so the
    # reader must expose the same identity as the snapshot it verifies.
    @property
    def repo_snapshot_id(self) -> str:
        return str(getattr(self.repo_snapshot, "snapshot_id", "") or "")

    @property
    def snapshot_id(self) -> str:
        return self.repo_snapshot_id

    @property
    def project_tree_hash(self) -> str:
        return str(getattr(self.repo_snapshot, "project_tree_hash", "") or "")

    @property
    def manifest_digest(self) -> str:
        return str(getattr(self.source_manifest, "content_digest", "") or "")

    @property
    def content_digest(self) -> str:
        """Deterministic identity of the verified revision this reader serves.

        The compiler's source-digest helper prefers ``content_digest`` when a
        provider exposes one.  Without this property the reader was serialized
        through ``str(object)``, so the closure digest, and therefore the
        archive, page ids and plan digests, changed on every process because
        the fallback embedded the object's memory address.
        """

        verified_paths = sorted({
            *self._manifest_entries,
            *self._snapshot_files,
        })
        identity = {
            "snapshot_id": self.repo_snapshot_id,
            "project_tree_hash": self.project_tree_hash,
            "manifest_digest": self.manifest_digest,
            "verified_paths": [
                [
                    path,
                    str(getattr(self._snapshot_files.get(path), "content_digest", "")),
                    str(getattr(self._manifest_entries.get(path), "content_digest", "")),
                ]
                for path in verified_paths
            ],
        }
        return sha256_digest(canonical_json_bytes(identity))

    # -- verification -----------------------------------------------------
    def _record(self, code: str, path: str) -> None:
        failure = f"{code}:{path}" if path else code
        if failure not in self.failures:
            self.failures.append(failure)

    def _resolve_within_root(self, path: str) -> Path | None:
        normalized = _normalize_relative_path(path)
        if not normalized or normalized != str(path).replace("\\", "/"):
            self._record("unified_source_path_invalid", str(path))
            return None
        candidate = self.project_root / normalized
        if candidate.is_symlink():
            target = os.path.realpath(candidate)
            try:
                Path(target).relative_to(self.project_root)
            except ValueError:
                self._record("unified_source_symlink_escape", normalized)
                return None
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            self._record("unified_source_path_escape", normalized)
            return None
        return resolved

    def read_file(self, path: str) -> str:
        raw = str(path or "").strip()
        if not raw:
            return ""
        normalized = _normalize_relative_path(raw)
        if not normalized:
            self._record("unified_source_path_invalid", raw)
            return ""
        if normalized in self._cache:
            return self._cache[normalized]
        text = self._read_and_verify(normalized)
        if text is not None:
            self._cache[normalized] = text
        return text or ""

    def read_span(self, path: str, start: int, end: int) -> str:
        source = self.read_file(path)
        if not source:
            return ""
        return "\n".join(source.splitlines()[max(0, int(start) - 1):int(end)])

    def read_text(self, path: str) -> str:
        return self.read_file(path)

    def source_for_path(self, path: str) -> str:
        return self.read_file(path)

    def verified_paths(self) -> tuple[str, ...]:
        """Paths whose bytes were successfully verified for this revision."""

        return tuple(sorted(self._cache))

    @property
    def files(self) -> "_VerifiedSourceFileMapping":
        """Mapping view over the manifest/snapshot paths.

        Values are read and verified on demand, so a consumer that only asks
        for some paths never reads the rest, and no consumer can bypass the
        digest check by taking the mapping instead of ``read_file``.
        """

        return _VerifiedSourceFileMapping(self)

    # -- internals --------------------------------------------------------
    def _read_and_verify(self, path: str) -> str | None:
        candidate = self._resolve_within_root(path)
        if candidate is None:
            return None
        entry = self._manifest_entries.get(path)
        if self.source_manifest is not None and entry is None:
            # Only files inside the authenticated source partition may be
            # read; an unlisted path is never silently promoted to authority.
            self._record("unified_source_path_not_in_manifest", path)
            return None
        if entry is not None and str(
            getattr(entry, "source_kind", "") or ""
        ) in _EXCLUDED_SOURCE_KINDS:
            self._record("unified_source_partition_excluded", path)
            return None
        if not candidate.is_file():
            self._record("unified_source_file_missing", path)
            return None
        try:
            data = candidate.read_bytes()
        except OSError:
            self._record("unified_source_file_unreadable", path)
            return None
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        expected_manifest = (
            str(getattr(entry, "content_digest", "") or "") if entry is not None else ""
        )
        if expected_manifest and expected_manifest != digest:
            self._record("unified_source_content_digest_mismatch", path)
            return None
        snapshot_file = self._snapshot_files.get(path)
        if snapshot_file is not None:
            if snapshot_file.kind == "symlink":
                self._record("unified_source_symlink_not_text", path)
                return None
            expected_snapshot = str(snapshot_file.content_digest or "")
            if expected_snapshot and expected_snapshot != digest:
                self._record("unified_source_snapshot_digest_mismatch", path)
                return None
        if b"\x00" in data:
            # Binary payloads are digest-verified but never source text.
            self._record("unified_source_binary_not_text", path)
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            self._record("unified_source_binary_not_text", path)
            return None


def read_verified_snapshot_sources(
    *,
    project_root: str | Path,
    source_manifest: object | None = None,
    repo_snapshot: RepoSnapshot | None = None,
    allowed_source_kinds: object | None = None,
) -> VerifiedSourceBytes:
    """Build a revision-frozen, digest-verified source reader."""

    return VerifiedSourceBytes(
        project_root=project_root,
        source_manifest=source_manifest,
        repo_snapshot=repo_snapshot,
        allowed_source_kinds=allowed_source_kinds,
    )


class _VerifiedSourceFileMapping(Mapping[str, str]):
    """Read-only mapping whose values pass through digest verification."""

    def __init__(self, reader: VerifiedSourceBytes) -> None:
        self._reader = reader
        paths = set(reader._manifest_entries) | set(reader._snapshot_files)
        self._paths = tuple(sorted(paths))

    def __getitem__(self, key: str) -> str:
        return self._reader.read_file(key)

    def __iter__(self):
        return iter(self._paths)

    def __len__(self) -> int:
        return len(self._paths)

    def get(self, key: str, default: str | None = None) -> str | None:
        value = self._reader.read_file(key)
        return value if value else (default if default is not None else "")


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
