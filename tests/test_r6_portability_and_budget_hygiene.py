"""R6: portability, atomicity and callback-artifact hygiene.

These are the independent compatibility fixes of the unified repair plan
section 11.2 that do not belong to the budget contract itself.
"""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.agentic.writing_callback_fulfillment import (
    _portable_callback_filename,
    _write_callback_artifact,
)
from code2paper.validators.latex_smoke_validator import validate_latex_smoke


def test_atomic_write_bytes_replaces_in_place_without_leftovers(
    tmp_path: Path,
) -> None:
    target = tmp_path / "artifact.json"
    payload = json.dumps({"b": 2, "a": 1}, sort_keys=True).encode("utf-8")

    written = atomic_write_bytes(target, payload)
    assert written == target
    assert target.read_bytes() == payload

    # A shorter temporary prefix must not change the final target or digest.
    replacement = b'{"b": 3}'
    atomic_write_bytes(target, replacement)
    assert target.read_bytes() == replacement
    assert hashlib.sha256(target.read_bytes()).hexdigest() == hashlib.sha256(
        replacement
    ).hexdigest()
    assert [path.name for path in tmp_path.iterdir()] == ["artifact.json"]


def test_callback_artifact_filename_is_portable_and_identity_is_kept(
    tmp_path: Path,
) -> None:
    artifact_id = "writing-callback:req/with:unsafe\\chars:0123456789ab"
    payload = {"artifact_id": artifact_id, "value": 1}
    path, digest = _write_callback_artifact(
        tmp_path / "writing_callbacks" / "req",
        artifact_id=artifact_id,
        payload=payload,
    )
    assert ":" not in path.name and "\\" not in path.name and "/" not in path.name
    assert path.name == _portable_callback_filename(artifact_id)
    assert json.loads(path.read_text(encoding="utf-8"))["artifact_id"] == artifact_id
    assert digest == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_callback_artifact_rewrite_is_idempotent_and_never_overwrites(
    tmp_path: Path,
) -> None:
    artifact_id = "writing-callback:req:0123456789ab"
    directory = tmp_path / "writing_callbacks"
    first = {"artifact_id": artifact_id, "value": 1}

    path, digest = _write_callback_artifact(
        directory, artifact_id=artifact_id, payload=first
    )
    same_path, same_digest = _write_callback_artifact(
        directory, artifact_id=artifact_id, payload=dict(first)
    )
    assert (same_path, same_digest) == (path, digest)

    # Different content under the same truncated identity is written beside
    # the original rather than silently replacing it.
    conflicting = {"artifact_id": artifact_id, "value": 2}
    other_path, other_digest = _write_callback_artifact(
        directory, artifact_id=artifact_id, payload=conflicting
    )
    assert other_path != path
    assert other_digest != digest
    assert json.loads(path.read_text(encoding="utf-8"))["value"] == 1
    assert json.loads(other_path.read_text(encoding="utf-8"))["value"] == 2

    # A file already holding unrelated bytes at the disambiguated name fails
    # closed instead of being replaced.
    other_path.write_text("unrelated", encoding="utf-8")
    with pytest.raises(ValueError, match="writing_callback_artifact_conflict"):
        _write_callback_artifact(
            directory, artifact_id=artifact_id, payload=conflicting
        )


def test_latex_smoke_writes_lf_and_decodes_engine_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = tmp_path / "pdflatex"
    engine.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, pathlib\n"
        "text = pathlib.Path(sys.argv[-1]).read_text(encoding='utf-8')\n"
        "assert '\\r' not in text\n"
        "sys.stdout.write('engine-ok-\\u00e9\\n')\n"
        "sys.exit(1 if 'bad' in text else 0)\n",
        encoding="utf-8",
        newline="\n",
    )
    engine.chmod(engine.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(
        "code2paper.validators.latex_smoke_validator.shutil.which",
        lambda name: str(engine),
    )

    passed = validate_latex_smoke("good line")
    assert passed["passed"] is True
    assert passed["status"] == "compiled"

    failed = validate_latex_smoke("bad line")
    assert failed["passed"] is False
    assert failed["status"] == "failed"
    first_issue = failed["issues"][0]
    assert first_issue["category"] == "compile_failed"
    # The engine output was decoded explicitly rather than through a locale
    # default codec.
    assert "engine-ok-\u00e9" in first_issue["message"]


def test_snapshot_content_identity_excludes_capture_observations() -> None:
    """R6: a capture timestamp must not change a closure/archive identity."""

    from code2paper.agentic.repo_snapshot import (
        RepoSnapshot,
        SnapshotFile,
        repo_snapshot_identity_digest,
    )

    def _snapshot(*, created_at: str, digest: str) -> RepoSnapshot:
        return RepoSnapshot(
            snapshot_id="repo:tree",
            project_root="/tmp/first-root",
            project_tree_hash="sha256:tree",
            created_at=created_at,
            included_files=[
                SnapshotFile(path="pkg/b.py", content_digest=digest),
                SnapshotFile(path="pkg/a.py", content_digest=digest),
            ],
        )

    first = _snapshot(created_at="2026-09-12T00:00:00+00:00", digest="sha256:file")
    second = _snapshot(created_at="2026-09-12T23:59:59+00:00", digest="sha256:file")
    assert first.content_digest == second.content_digest
    assert repo_snapshot_identity_digest(first) == repo_snapshot_identity_digest(second)

    changed = _snapshot(created_at="2026-09-12T00:00:00+00:00", digest="sha256:other")
    assert changed.content_digest != first.content_digest


def test_source_digest_never_hashes_an_object_address() -> None:
    """R6: an unidentified provider must not destabilize the closure digest."""

    from code2paper.agentic.mechanism_context_compiler import _source_digest

    class _OpaqueProvider:
        pass

    assert _source_digest(_OpaqueProvider()) == _source_digest(_OpaqueProvider())


def test_verified_reader_digest_is_stable_across_instances(tmp_path: Path) -> None:
    """R6: the production reader exposes a deterministic revision identity."""

    from code2paper.agentic.repo_snapshot import (
        RepoSnapshot,
        SnapshotFile,
        read_verified_snapshot_sources,
    )
    from code2paper.agentic.source_inventory import (
        RepositorySourceEntryV1,
        RepositorySourceManifestV1,
    )

    source_path = tmp_path / "model.py"
    source_path.write_text("VALUE = 1\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
    snapshot = RepoSnapshot(
        snapshot_id="repo:tree",
        project_root=str(tmp_path),
        project_tree_hash="sha256:tree",
        included_files=[SnapshotFile(path="model.py", content_digest=digest)],
    )
    manifest = RepositorySourceManifestV1(
        repo_snapshot_id="repo:tree",
        project_tree_hash="sha256:tree",
        entries=(RepositorySourceEntryV1(
            path="model.py",
            source_kind="first_party_executable",
            ownership_role="target_core",
            executable_authority=True,
            content_digest=digest,
            classification_reason="fixture",
        ),),
        target_core_paths=("model.py",),
    )

    def _reader_digest() -> str:
        reader = read_verified_snapshot_sources(
            project_root=tmp_path,
            source_manifest=manifest,
            repo_snapshot=snapshot,
        )
        assert reader.read_file("model.py") == "VALUE = 1\n"
        return reader.content_digest

    first, second = _reader_digest(), _reader_digest()
    assert first == second

    source_path.write_text("VALUE = 2\n", encoding="utf-8")
    drifted = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert drifted.read_file("model.py") == ""
    assert drifted.content_digest == first
