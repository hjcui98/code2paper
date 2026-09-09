"""Shared repository-bound authoring artifact construction.

The product research graph and the frozen replay must derive the repository
snapshot, symbol index, implementation scope, and source manifest through the
same deterministic boundary.  Keeping this small builder in one module avoids
the two entry points slowly acquiring different source-authority rules.

This module only constructs input artifacts.  It does not call an LLM and it
does not write files; callers decide where the already validated models are
persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from code2paper.agentic.digest import digest_json
from code2paper.agentic.implementation_scope import infer_implementation_scope
from code2paper.agentic.language_adapter_registry import (
    LanguageAdapterRegistry,
    default_language_adapter_registry,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot
from code2paper.agentic.source_inventory import build_repository_source_manifest


REPOSITORY_AUTHORING_BUILDER_VERSION = "repository_authoring_artifacts_v1"


def read_snapshot_files(snapshot: RepoSnapshot) -> dict[str, str]:
    """Read the text files named by a validated snapshot.

    Snapshot paths are relative identities.  A missing file is an integrity
    failure rather than an empty source input, and symlinks are not followed
    because the snapshot records them as links rather than file contents.
    """

    root = Path(snapshot.project_root).expanduser().resolve()
    files: dict[str, str] = {}
    for entry in snapshot.included_files:
        if entry.kind != "file":
            continue
        relative = Path(entry.path)
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"repository snapshot path escapes project root: {entry.path}"
            ) from exc
        try:
            data = candidate.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"repository snapshot file is unavailable: {entry.path}"
            ) from exc
        files[entry.path] = data.decode("utf-8", errors="replace")
    expected_paths = {
        entry.path for entry in snapshot.included_files if entry.kind == "file"
    }
    missing = sorted(expected_paths - set(files))
    if missing:
        raise ValueError(
            "repository snapshot files could not be reconstructed: "
            + ",".join(missing)
        )
    return files


@dataclass(frozen=True)
class RepositoryAuthoringArtifacts:
    """The four source-bound models and their common construction identity."""

    snapshot: RepoSnapshot
    files: dict[str, str]
    language: str
    symbol_index: Any
    implementation_scope: Any
    source_manifest: Any
    builder_version: str = REPOSITORY_AUTHORING_BUILDER_VERSION

    @property
    def cross_digest(self) -> str:
        return digest_json({
            "builder_version": self.builder_version,
            "repo_snapshot_id": self.snapshot.snapshot_id,
            "project_tree_hash": self.snapshot.project_tree_hash,
            "symbol_index_digest": str(
                getattr(self.symbol_index, "content_digest", "") or ""
            ),
            "implementation_scope_digest": str(
                getattr(self.implementation_scope, "content_digest", "") or ""
            ),
            "source_manifest_digest": str(
                getattr(self.source_manifest, "content_digest", "") or ""
            ),
        })

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "builder_version": self.builder_version,
            "repo_snapshot_id": self.snapshot.snapshot_id,
            "project_tree_hash": self.snapshot.project_tree_hash,
            "symbol_index_digest": str(
                getattr(self.symbol_index, "content_digest", "") or ""
            ),
            "implementation_scope_digest": str(
                getattr(self.implementation_scope, "content_digest", "") or ""
            ),
            "source_manifest_digest": str(
                getattr(self.source_manifest, "content_digest", "") or ""
            ),
            "cross_digest": self.cross_digest,
        }


def repository_authoring_identity_payload(
    *,
    snapshot: RepoSnapshot,
    symbol_index: Any,
    implementation_scope: Any,
    source_manifest: Any,
    builder_version: str = REPOSITORY_AUTHORING_BUILDER_VERSION,
) -> dict[str, Any]:
    """Return the persisted cross-artifact identity without source contents."""

    identity = {
        "schema_version": "1.0",
        "builder_version": str(builder_version),
        "repo_snapshot_id": snapshot.snapshot_id,
        "project_tree_hash": snapshot.project_tree_hash,
        "symbol_index_digest": str(
            getattr(symbol_index, "content_digest", "") or ""
        ),
        "implementation_scope_digest": str(
            getattr(implementation_scope, "content_digest", "") or ""
        ),
        "source_manifest_digest": str(
            getattr(source_manifest, "content_digest", "") or ""
        ),
    }
    identity["cross_digest"] = digest_json(identity)
    return identity


def build_repository_authoring_artifacts(
    snapshot: RepoSnapshot,
    *,
    author_texts: Iterable[str] = (),
    entry_symbol_ids: Iterable[str] = (),
    adapter_registry: LanguageAdapterRegistry | None = None,
    adapter_language: str = "",
) -> RepositoryAuthoringArtifacts:
    """Build the product/replay source closure from one frozen snapshot.

    ``author_texts`` and ``entry_symbol_ids`` are only scope hints.  The
    resulting source manifest remains the authority boundary and can reject
    excluded or unmapped source material later in the unified compiler.
    """

    files = read_snapshot_files(snapshot)
    registry = adapter_registry or default_language_adapter_registry()
    adapter = (
        registry.get(adapter_language)
        if str(adapter_language).strip()
        else registry.for_files(files)
    )
    symbol_index = adapter.index_symbols(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        files=files,
    )
    symbol_index_digest = str(getattr(symbol_index, "content_digest", "") or "")
    if not symbol_index_digest:
        # Not every language adapter seals its index digest (the JavaScript
        # lane never did).  Seal it here with the same canonical payload the
        # Python adapter uses instead of failing the authoring boundary.
        import hashlib
        import json

        payload = {
            "schema_version": symbol_index.schema_version,
            "repo_snapshot_id": symbol_index.repo_snapshot_id,
            "project_tree_hash": symbol_index.project_tree_hash,
            "language": symbol_index.language,
            "symbols": [
                symbol.model_dump(mode="json") for symbol in symbol_index.symbols
            ],
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        symbol_index_digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
        symbol_index = symbol_index.model_copy(
            update={"content_digest": symbol_index_digest}
        )
    if not symbol_index_digest:
        raise ValueError("repository symbol index has no content digest")
    scope = infer_implementation_scope(
        symbol_index.symbols,
        author_texts=tuple(str(value) for value in author_texts if str(value).strip()),
        entry_symbol_ids=tuple(
            str(value) for value in entry_symbol_ids if str(value).strip()
        ),
        evidence_refs=(symbol_index_digest,),
    )
    source_manifest = build_repository_source_manifest(
        snapshot,
        symbols=symbol_index.symbols,
        implementation_scope=scope,
    )
    return RepositoryAuthoringArtifacts(
        snapshot=snapshot,
        files=files,
        language=str(getattr(adapter, "language", "") or ""),
        symbol_index=symbol_index,
        implementation_scope=scope,
        source_manifest=source_manifest,
    )


def rebuild_repository_authoring_artifacts(
    repo_path: str | Path,
    *,
    expected_project_tree_hash: str,
    author_texts: Iterable[str] = (),
    entry_symbol_ids: Iterable[str] = (),
    adapter_registry: LanguageAdapterRegistry | None = None,
    adapter_language: str = "",
) -> RepositoryAuthoringArtifacts:
    """Snapshot ``repo_path`` and rebuild its source closure after exact hash check."""

    snapshot = build_repo_snapshot(repo_path)
    expected = str(expected_project_tree_hash or "").strip()
    if not expected:
        raise ValueError("unified_project_tree_hash_missing")
    if snapshot.project_tree_hash != expected:
        raise ValueError(
            "unified_project_tree_hash_mismatch:"
            f"expected={expected}:actual={snapshot.project_tree_hash}"
        )
    return build_repository_authoring_artifacts(
        snapshot,
        author_texts=author_texts,
        entry_symbol_ids=entry_symbol_ids,
        adapter_registry=adapter_registry,
        adapter_language=adapter_language,
    )


__all__ = [
    "REPOSITORY_AUTHORING_BUILDER_VERSION",
    "RepositoryAuthoringArtifacts",
    "repository_authoring_identity_payload",
    "read_snapshot_files",
    "build_repository_authoring_artifacts",
    "rebuild_repository_authoring_artifacts",
]
