"""R2 regressions: artifact-manifest handoff and verified source bytes.

Covers the slice exit evidence from the unified repair execution plan:
- a reused output directory cannot inject stale artifacts into this revision;
- legacy directory discovery is an explicit opt-in, never a silent fallback;
- the resolver's source bytes are digest-verified and frozen per revision;
- drift, path escape, unlisted paths, binary payloads and excluded partitions
  are auditable failures instead of empty text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from code2paper.agentic.autonomous_method_agent import _writer_artifact_paths
from code2paper.agentic.repo_snapshot import (
    RepoSnapshot,
    SnapshotFile,
    VerifiedSourceBytes,
    read_verified_snapshot_sources,
)
from code2paper.agentic.source_inventory import (
    RepositorySourceEntryV1,
    RepositorySourceManifestV1,
)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _manifest_entry(
    path: str,
    data: bytes,
    *,
    source_kind: str = "first_party_executable",
) -> RepositorySourceEntryV1:
    first_party = source_kind == "first_party_executable"
    return RepositorySourceEntryV1(
        path=path,
        source_kind=source_kind,
        ownership_role="target_core" if first_party else "unknown",
        executable_authority=first_party,
        content_digest=_digest(data),
        classification_reason=f"fixture:{source_kind}",
    )


def _snapshot(root: Path, files: dict[str, bytes]) -> RepoSnapshot:
    included = [
        SnapshotFile(
            path=path,
            kind="file",
            size=len(data),
            content_digest=_digest(data),
        )
        for path, data in sorted(files.items())
    ]
    tree_hash = "sha256:" + hashlib.sha256(
        repr([(item.path, item.content_digest) for item in included]).encode()
    ).hexdigest()
    return RepoSnapshot(
        snapshot_id="repo:" + tree_hash.removeprefix("sha256:"),
        project_root=str(root),
        project_tree_hash=tree_hash,
        included_files=included,
    )


def _manifest(
    root: Path,
    files: dict[str, bytes],
    *,
    kinds: dict[str, str] | None = None,
) -> RepositorySourceManifestV1:
    kinds = kinds or {}
    return RepositorySourceManifestV1(
        repo_snapshot_id="repo:fixture",
        project_tree_hash="sha256:tree",
        entries=tuple(
            _manifest_entry(path, data, source_kind=kinds.get(path, "first_party_executable"))
            for path, data in sorted(files.items())
        ),
        target_core_paths=tuple(sorted(files)),
    )


# ---------------------------------------------------------------------------
# R2.1 artifact manifest handoff
# ---------------------------------------------------------------------------

def test_manifest_handoff_excludes_stale_directory_artifacts(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    # Files left behind by an earlier run in the same output directory.
    stale = artifacts / "candidate_handoff_v1.json"
    stale.write_text('{"stale": true}', encoding="utf-8")
    (artifacts / "method_propositions_v1.json").write_text("{}", encoding="utf-8")

    current = artifacts / "code_facts_v1.json"
    current.write_text('{"facts": []}', encoding="utf-8")

    resolved = _writer_artifact_paths(
        tmp_path,
        persisted_paths={"code_facts_v1": str(current)},
    )

    assert resolved == {"code_facts_v1": str(current)}
    assert "candidate_handoff_v1" not in resolved
    assert "method_propositions_v1" not in resolved


def test_manifest_handoff_never_substitutes_a_same_named_stale_file(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    stale = artifacts / "candidate_handoff_v1.json"
    stale.write_text('{"stale": true}', encoding="utf-8")

    # The manifest points at a file that no longer exists; the colliding
    # directory file must not silently replace it.
    resolved = _writer_artifact_paths(
        tmp_path,
        persisted_paths={"candidate_handoff_v1": str(tmp_path / "missing.json")},
    )

    assert resolved == {}


def test_legacy_discovery_requires_an_explicit_marker(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "symbol_index_v2.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="writer_artifact_manifest_required"):
        _writer_artifact_paths(tmp_path)

    legacy = _writer_artifact_paths(tmp_path, allow_legacy_discovery=True)
    assert set(legacy) == {"symbol_index_v2"}


def test_manifest_handoff_binds_only_existing_manifest_paths(tmp_path: Path) -> None:
    present = tmp_path / "artifacts" / "repo_snapshot_v2.json"
    present.parent.mkdir(parents=True)
    present.write_text("{}", encoding="utf-8")

    resolved = _writer_artifact_paths(
        tmp_path,
        persisted_paths={
            "repo_snapshot_v2": str(present),
            "symbol_index_v2": "",
            "code_facts_v1": str(tmp_path / "absent.json"),
        },
    )

    assert resolved == {"repo_snapshot_v2": str(present)}


# ---------------------------------------------------------------------------
# R2.3 verified, revision-frozen source bytes
# ---------------------------------------------------------------------------

def test_verified_reader_freezes_bytes_and_reports_drift(tmp_path: Path) -> None:
    source = tmp_path / "src" / "helper.py"
    source.parent.mkdir(parents=True)
    original = b"def helper():\n    return 1\n"
    source.write_bytes(original)
    files = {"src/helper.py": original}
    manifest = _manifest(tmp_path, files)
    snapshot = _snapshot(tmp_path, files)

    reader = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert reader.read_file("src/helper.py") == original.decode("utf-8")
    assert reader.read_span("src/helper.py", 1, 1) == "def helper():"

    # Editing the working tree after the revision was loaded must not change
    # the bytes already verified for that revision.
    source.write_bytes(b"def helper():\n    return 999\n")
    assert reader.read_file("src/helper.py") == original.decode("utf-8")
    assert reader.failures == []

    # A new load of the same revision reports the drift instead of reading
    # the changed file as if it were the frozen source.
    reloaded = VerifiedSourceBytes(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert reloaded.read_file("src/helper.py") == ""
    assert reloaded.failures == [
        "unified_source_content_digest_mismatch:src/helper.py",
    ]


def test_verified_reader_rejects_unlisted_paths_and_escapes(tmp_path: Path) -> None:
    source = tmp_path / "src" / "allowed.py"
    source.parent.mkdir(parents=True)
    allowed = b"allowed = True\n"
    source.write_bytes(allowed)
    other = tmp_path / "src" / "unlisted.py"
    other.write_bytes(b"unlisted = True\n")
    outside = tmp_path.parent / "outside.py"
    outside.write_bytes(b"outside = True\n")
    files = {"src/allowed.py": allowed}
    manifest = _manifest(tmp_path, files)
    snapshot = _snapshot(tmp_path, files)

    reader = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert reader.read_file("src/unlisted.py") == ""
    assert reader.read_file("../outside.py") == ""
    assert reader.read_file(str(outside)) == ""
    assert "unified_source_path_not_in_manifest:src/unlisted.py" in reader.failures
    assert any(item.startswith("unified_source_path_invalid:") for item in reader.failures)
    # The allowed partition still reads normally.
    assert reader.read_file("src/allowed.py") == allowed.decode("utf-8")


def test_verified_reader_verifies_but_never_returns_binary_or_excluded(tmp_path: Path) -> None:
    binary = tmp_path / "assets" / "blob.bin"
    binary.parent.mkdir(parents=True)
    binary_bytes = b"\x00\x01\x02binary"
    binary.write_bytes(binary_bytes)
    vendor = tmp_path / "vendor" / "lib.py"
    vendor.parent.mkdir(parents=True)
    vendor_bytes = b"vendored = True\n"
    vendor.write_bytes(vendor_bytes)
    files = {"assets/blob.bin": binary_bytes, "vendor/lib.py": vendor_bytes}
    manifest = _manifest(
        tmp_path,
        files,
        kinds={"vendor/lib.py": "vendor"},
    )
    snapshot = _snapshot(tmp_path, files)

    reader = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert reader.read_file("assets/blob.bin") == ""
    assert reader.read_file("vendor/lib.py") == ""
    assert sorted(reader.failures) == [
        "unified_source_binary_not_text:assets/blob.bin",
        "unified_source_partition_excluded:vendor/lib.py",
    ]


def test_verified_reader_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "secret.py"
    outside.write_text("secret = 1\n", encoding="utf-8")
    link = root / "src" / "link.py"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)

    files = {"src/link.py": b"secret = 1\n"}
    manifest = _manifest(root, files)
    snapshot = _snapshot(root, files)

    reader = read_verified_snapshot_sources(
        project_root=root,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    assert reader.read_file("src/link.py") == ""
    assert reader.failures == ["unified_source_symlink_escape:src/link.py"]


def test_verified_reader_files_view_cannot_bypass_verification(tmp_path: Path) -> None:
    source = tmp_path / "src" / "helper.py"
    source.parent.mkdir(parents=True)
    original = b"value = 1\n"
    source.write_bytes(original)
    files = {"src/helper.py": original}
    manifest = _manifest(tmp_path, files)
    snapshot = _snapshot(tmp_path, files)

    reader = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    )
    mapping = reader.files
    assert mapping["src/helper.py"] == original.decode("utf-8")

    source.write_bytes(b"value = 2\n")
    # The mapping routes through the same digest check, so a reader loaded
    # before the change cannot serve the changed bytes.
    fresh = read_verified_snapshot_sources(
        project_root=tmp_path,
        source_manifest=manifest,
        repo_snapshot=snapshot,
    ).files
    assert fresh["src/helper.py"] == ""


# ---------------------------------------------------------------------------
# R2.2 cross-run evidence identity
# ---------------------------------------------------------------------------

def test_evidence_identity_refuses_a_foreign_or_stale_artifact() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.publication_method_writer import (
        _evidence_identity_failures,
    )

    snapshot = SimpleNamespace(
        snapshot_id="repo:this-run",
        project_tree_hash="sha256:this-tree",
    )
    matching = SimpleNamespace(
        repo_snapshot_id="repo:this-run",
        project_tree_hash="sha256:this-tree",
    )
    foreign = SimpleNamespace(
        repo_snapshot_id="repo:other-run",
        project_tree_hash="sha256:other-tree",
    )
    declared_by_key_only = SimpleNamespace(
        repo_snapshot_id="repo:this-run",
        project_tree_hash="sha256:other-tree",
    )
    legacy_without_identity = SimpleNamespace()

    assert _evidence_identity_failures(
        snapshot=snapshot, facts=matching, claims=matching, equations=matching
    ) == ()
    assert _evidence_identity_failures(
        snapshot=snapshot, facts=foreign, claims=matching, equations=matching
    ) == (
        "unified_code_facts_snapshot_mismatch",
        "unified_code_facts_tree_hash_mismatch",
    )
    assert _evidence_identity_failures(
        snapshot=snapshot, facts=matching, claims=declared_by_key_only, equations=matching
    ) == ("unified_atomic_claims_tree_hash_mismatch",)
    # Legacy artifacts that declare no identity stay readable.
    assert _evidence_identity_failures(
        snapshot=snapshot,
        facts=legacy_without_identity,
        claims=legacy_without_identity,
        equations=legacy_without_identity,
    ) == ()


def test_partition_exclusion_is_not_an_integrity_failure(tmp_path: Path) -> None:
    """A declared partition exclusion must not abort the unified source gate.

    R2 keeps every integrity failure fatal; a path the frozen manifest already
    classified as vendor/generated/submodule/dataset was never source
    authority, so the reader's record of it stays visible without claiming
    damaged evidence.
    """

    from code2paper.agentic.publication_method_writer import (
        _persist_source_partition_exclusions,
        _unified_source_read_failures,
    )
    from code2paper.agentic.repo_snapshot import split_source_read_failures
    from code2paper.core.output_names import method_output

    class _Reader:
        def __init__(self, failures: tuple[str, ...]) -> None:
            self.failures = failures

    blocking, excluded = split_source_read_failures([
        "unified_source_partition_excluded:conf/dataset/msmarco_v2.yaml",
        "unified_source_partition_excluded:src/dataset/ebcar_dataset.py",
    ])
    assert blocking == ()
    assert excluded == (
        "unified_source_partition_excluded:conf/dataset/msmarco_v2.yaml",
        "unified_source_partition_excluded:src/dataset/ebcar_dataset.py",
    )

    # Mixed input: integrity failures stay blocking, deduplicated and in order.
    blocking, excluded = _unified_source_read_failures(_Reader((
        "unified_source_partition_excluded:vendor/lib.py",
        "unified_source_content_digest_mismatch:src/core.py",
        "unified_source_path_escape:../secret.py",
        "unified_source_partition_excluded:vendor/lib.py",
        "unified_source_file_missing:src/gone.py",
    )))
    assert excluded == ("unified_source_partition_excluded:vendor/lib.py",)
    assert blocking == (
        "unified_source_content_digest_mismatch:src/core.py",
        "unified_source_path_escape:../secret.py",
        "unified_source_file_missing:src/gone.py",
    )

    # A reader without failures yields two empty tuples, never a crash.
    assert _unified_source_read_failures(None) == ((), ())

    path = _persist_source_partition_exclusions(tmp_path, excluded)
    assert path == str(
        method_output(tmp_path, "unified_source_partition_exclusions_v1")
    )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    assert payload["excluded_paths"] == ["vendor/lib.py"]
    assert payload["failure_code"] == "unified_source_partition_excluded"
    assert payload["content_digest"].startswith("sha256:")
