"""Deterministic repository source inventory for unified Method authoring.

The inventory is a boundary contract, not evidence.  It classifies snapshot
files before retrieval/closure compilation so executable implementation facts,
configuration qualifiers, tests, documentation, and excluded material cannot
silently share one authority lane.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json

SourceKindV1 = Literal[
    "first_party_executable",
    "configuration",
    "test",
    "documentation",
    "generated",
    "vendor",
    "submodule",
    "dataset_or_checkpoint",
    "paper_or_draft",
]

SourceOwnershipRoleV1 = Literal[
    "target_core",
    "target_support",
    "comparand",
    "evaluation",
    "unknown",
]

_EXECUTABLE_SUFFIXES = frozenset({
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".m", ".mm", ".swift",
    ".kt", ".kts", ".scala", ".rb", ".php", ".sh", ".bash",
})
_CONFIG_SUFFIXES = frozenset({".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"})
_DATA_SUFFIXES = frozenset({
    ".pt", ".pth", ".ckpt", ".checkpoint", ".bin", ".safetensors", ".onnx",
    ".npy", ".npz", ".parquet", ".arrow", ".pkl", ".pickle", ".h5", ".hdf5",
})
_DOC_SUFFIXES = frozenset({".md", ".rst", ".txt", ".adoc", ".tex", ".bib"})
_VENDOR_PARTS = frozenset({
    "vendor", "vendors", "third_party", "third-party", "external", "externals",
    "node_modules", "site-packages", "dist-packages", "deps", "vendored",
    "sglang", "sglang_full", "sglang_pruned", "submodules",
})
_GENERATED_PARTS = frozenset({
    "generated", "gen", "build", "dist", "out", "target", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
})
_DATA_PARTS = frozenset({
    "data", "dataset", "datasets", "checkpoint", "checkpoints", "weights",
    "models", "artifacts", "runs", "outputs", "results",
})
_TEST_PARTS = frozenset({"test", "tests", "testing", "unit_tests", "integration_tests"})
_PAPER_PARTS = frozenset({"paper", "papers", "manuscript", "draft", "drafts", "latex", "tex"})
_COMPARAND_TERMS = frozenset({"baseline", "baselines", "comparand", "comparison", "reference"})
_EVALUATION_TERMS = frozenset({"eval", "evals", "evaluation", "benchmark", "metrics", "ablation"})


def normalize_source_path(value: str) -> str:
    """Normalize a repository-relative path without damaging hidden names."""

    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    normalized = PurePosixPath(raw).as_posix()
    # ``str.lstrip("./")`` removes the leading dot from ``.gitignore`` and
    # other valid hidden files.  Only remove explicit current-directory
    # prefixes; the filename itself must remain byte-identical.
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return "" if normalized == "." else normalized


def _clean_path(value: str) -> str:
    return normalize_source_path(value)


def _is_data_container_path(parts: tuple[str, ...], suffix: str) -> bool:
    """Whether a path belongs to the data/checkpoint partition.

    A data-suffix artifact (weights, arrays, checkpoints) is always data.  For
    everything else the container directory decides, and for *executable
    source* only a top-level data container does: ``data/real/x/preprocess.py``
    is dataset tooling, while ``src/dataset/ebcar_dataset.py`` or
    ``src/models/foo.py`` is the project's own implementation that merely uses
    a name from the data vocabulary.  Classifying the latter as data excluded
    first-party method code from the readable source partition -- and from the
    configuration evidence whose definition spans live in those modules.
    """

    if suffix in _DATA_SUFFIXES:
        return True
    if not parts:
        return False
    if suffix in _EXECUTABLE_SUFFIXES:
        return parts[0] in _DATA_PARTS
    return any(part in _DATA_PARTS for part in parts)


def classify_source_kind(path: str) -> SourceKindV1:
    """Classify a snapshot-relative path without inspecting project names."""

    clean = _clean_path(path)
    parts = tuple(part.casefold() for part in PurePosixPath(clean).parts)
    name = parts[-1] if parts else ""
    suffix = PurePosixPath(name).suffix.casefold()
    stem = PurePosixPath(name).stem.casefold()
    if any(part in _VENDOR_PARTS for part in parts):
        return "vendor"
    if any(part in _GENERATED_PARTS for part in parts):
        return "generated"
    if _is_data_container_path(parts, suffix):
        return "dataset_or_checkpoint"
    if any(part in _PAPER_PARTS for part in parts) or suffix in {".tex", ".bib"}:
        return "paper_or_draft"
    if any(part in _TEST_PARTS for part in parts) or stem.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if suffix in _CONFIG_SUFFIXES or any(
        token in stem.split("_") for token in ("config", "settings", "options", "params", "arguments")
    ):
        return "configuration"
    if suffix in _DOC_SUFFIXES:
        return "documentation"
    if suffix in _EXECUTABLE_SUFFIXES:
        return "first_party_executable"
    return "documentation"


class RepositorySourceEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    source_kind: SourceKindV1
    ownership_role: SourceOwnershipRoleV1 = "unknown"
    executable_authority: bool = False
    content_digest: str = ""
    symbol_ids: tuple[str, ...] = Field(default_factory=tuple)
    classification_reason: str = ""

    @model_validator(mode="after")
    def _safe_authority(self) -> "RepositorySourceEntryV1":
        normalized_path = _clean_path(self.path)
        if not normalized_path or normalized_path != self.path:
            raise ValueError(
                f"repository source path must be normalized and relative: {self.path!r}"
            )
        if not self.content_digest.strip():
            raise ValueError(
                f"repository source entry {self.path} is missing content_digest"
            )
        if self.source_kind in {
            "vendor", "generated", "submodule", "dataset_or_checkpoint",
        }:
            if self.executable_authority:
                raise ValueError("excluded source cannot carry executable authority")
            if self.ownership_role != "unknown":
                raise ValueError("excluded source cannot carry target ownership")
        if self.executable_authority and self.source_kind != "first_party_executable":
            raise ValueError("only first-party executable source may be executable authority")
        if self.ownership_role in {"target_core", "target_support"} and not self.executable_authority:
            raise ValueError("target-owned source must be first-party executable")
        return self


class RepositorySourceManifestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repo_snapshot_id: str
    project_tree_hash: str
    entries: tuple[RepositorySourceEntryV1, ...] = Field(default_factory=tuple)
    target_core_paths: tuple[str, ...] = Field(default_factory=tuple)
    target_support_paths: tuple[str, ...] = Field(default_factory=tuple)
    comparand_paths: tuple[str, ...] = Field(default_factory=tuple)
    evaluation_paths: tuple[str, ...] = Field(default_factory=tuple)
    excluded_paths: tuple[str, ...] = Field(default_factory=tuple)
    anomaly_codes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed_digest(self) -> "RepositorySourceManifestV1":
        if not self.repo_snapshot_id.strip() or not self.project_tree_hash.strip():
            raise ValueError(
                "repository source manifest requires snapshot and project tree identities"
            )
        paths = tuple(item.path for item in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("repository source manifest contains duplicate paths")
        known = set(paths)
        for field_name in (
            "target_core_paths", "target_support_paths", "comparand_paths",
            "evaluation_paths", "excluded_paths",
        ):
            unknown = set(getattr(self, field_name)) - known
            if unknown:
                raise ValueError(f"{field_name} references unknown paths: {sorted(unknown)}")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("repository source manifest content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    def entry_for(self, path: str) -> RepositorySourceEntryV1 | None:
        target = _clean_path(path)
        return next((item for item in self.entries if item.path == target), None)


def _symbol_role(scope: Any | None, symbol_id: str) -> SourceOwnershipRoleV1:
    if scope is None:
        return "unknown"
    role = str(scope.role_for(symbol_id) or "unknown")
    if role == "target_dependency":
        return "target_support"
    if role in {"target_core", "comparand", "evaluation"}:
        return role  # type: ignore[return-value]
    return "unknown"


def build_repository_source_manifest(
    repo_snapshot: Any,
    *,
    symbols: Iterable[Any] = (),
    implementation_scope: Any | None = None,
) -> RepositorySourceManifestV1:
    """Build a manifest from the frozen snapshot, symbol index, and scope."""

    symbols = tuple(symbols)
    symbols_by_path: dict[str, list[str]] = {}
    for symbol in symbols:
        symbol_id = str(getattr(symbol, "symbol_id", "") or "").strip()
        path = _clean_path(str(getattr(symbol, "path", "") or ""))
        if symbol_id and path:
            symbols_by_path.setdefault(path, []).append(symbol_id)

    entries: list[RepositorySourceEntryV1] = []
    anomalies: list[str] = []
    seen_normalized_paths: set[str] = set()
    for item in sorted(getattr(repo_snapshot, "included_files", ()) or (), key=lambda value: str(getattr(value, "path", ""))):
        raw_path = str(getattr(item, "path", "") or "")
        path = _clean_path(raw_path)
        if not path:
            anomalies.append("source_entry_path_missing")
            continue
        if raw_path != path:
            anomalies.append(f"source_path_normalization_conflict:{raw_path}")
        if path in seen_normalized_paths:
            anomalies.append(f"source_path_duplicate_after_normalization:{path}")
            continue
        seen_normalized_paths.add(path)
        content_digest = str(getattr(item, "content_digest", "") or "")
        if not content_digest.strip():
            anomalies.append(f"source_entry_digest_missing:{path}")
            continue
        source_kind = "submodule" if str(getattr(item, "kind", "file")) == "submodule" else classify_source_kind(path)
        symbol_ids = tuple(dict.fromkeys(symbols_by_path.get(path, ())))
        roles = {_symbol_role(implementation_scope, symbol_id) for symbol_id in symbol_ids}
        if source_kind in {"vendor", "generated", "submodule", "dataset_or_checkpoint"}:
            role: SourceOwnershipRoleV1 = "unknown"
        elif "target_core" in roles:
            role = "target_core"
        elif "target_support" in roles:
            role = "target_support"
        elif "evaluation" in roles or any(term in path.casefold().split("/") for term in _EVALUATION_TERMS):
            role = "evaluation"
        elif "comparand" in roles or any(term in path.casefold().split("/") for term in _COMPARAND_TERMS):
            role = "comparand"
        else:
            role = "unknown"
        executable = source_kind == "first_party_executable" and role in {"target_core", "target_support", "unknown", "comparand", "evaluation"}
        reason = source_kind
        if source_kind in {"vendor", "generated", "submodule", "dataset_or_checkpoint"}:
            reason += ":excluded_from_fact_authority"
        elif not symbol_ids and source_kind == "first_party_executable":
            reason += ":no_indexed_symbol"
        entry = RepositorySourceEntryV1(
            path=path,
            source_kind=source_kind,  # type: ignore[arg-type]
            ownership_role=role,
            executable_authority=executable,
            content_digest=content_digest,
            symbol_ids=symbol_ids,
            classification_reason=reason,
        )
        entries.append(entry)

    snapshot_paths = {
        _clean_path(str(getattr(item, "path", "") or ""))
        for item in (getattr(repo_snapshot, "included_files", ()) or ())
        if _clean_path(str(getattr(item, "path", "") or ""))
    }
    for symbol in symbols:
        symbol_path = _clean_path(str(getattr(symbol, "path", "") or ""))
        if symbol_path and symbol_path not in snapshot_paths:
            anomalies.append(f"source_span_unmapped:{symbol_path}")

    entry_ids = set(getattr(implementation_scope, "target_entry_symbol_ids", ()) or ())
    indexed_entry_ids = {
        symbol_id
        for entry in entries
        for symbol_id in entry.symbol_ids
        if symbol_id in entry_ids
    }
    if entry_ids - indexed_entry_ids:
        anomalies.append("target_entrypoint_not_in_source_inventory")
    if implementation_scope is not None and not getattr(implementation_scope, "target_core_symbol_ids", ()):
        anomalies.append("target_core_scope_empty")

    by_role = {
        "target_core": tuple(item.path for item in entries if item.ownership_role == "target_core"),
        "target_support": tuple(item.path for item in entries if item.ownership_role == "target_support"),
        "comparand": tuple(item.path for item in entries if item.ownership_role == "comparand"),
        "evaluation": tuple(item.path for item in entries if item.ownership_role == "evaluation"),
    }
    excluded = tuple(
        item.path for item in entries
        if item.source_kind in {"vendor", "generated", "submodule", "dataset_or_checkpoint"}
    )
    return RepositorySourceManifestV1(
        repo_snapshot_id=str(getattr(repo_snapshot, "snapshot_id", "") or ""),
        project_tree_hash=str(getattr(repo_snapshot, "project_tree_hash", "") or ""),
        entries=tuple(entries),
        target_core_paths=by_role["target_core"],
        target_support_paths=by_role["target_support"],
        comparand_paths=by_role["comparand"],
        evaluation_paths=by_role["evaluation"],
        excluded_paths=excluded,
        anomaly_codes=tuple(dict.fromkeys(anomalies)),
    )


def source_manifest_snapshot_failures(
    manifest: RepositorySourceManifestV1,
    repo_snapshot: Any,
) -> tuple[str, ...]:
    """Compare a source manifest with the exact snapshot it claims to classify.

    The manifest is an authority partition over snapshot files, not an
    independent file list.  A replay must therefore reject missing, extra or
    digest-mutated entries before closure compilation.  The returned codes
    are deliberately small and deterministic so callers can persist them in
    an admission record without exposing exception text.
    """

    failures: list[str] = []
    snapshot_id = str(getattr(repo_snapshot, "snapshot_id", "") or "")
    tree_hash = str(getattr(repo_snapshot, "project_tree_hash", "") or "")
    if manifest.repo_snapshot_id != snapshot_id:
        failures.append("unified_repo_snapshot_id_mismatch")
    if manifest.project_tree_hash != tree_hash:
        failures.append("unified_project_tree_hash_mismatch")

    snapshot_files = {
        _clean_path(str(getattr(item, "path", "") or "")): str(
            getattr(item, "content_digest", "") or ""
        )
        for item in (getattr(repo_snapshot, "included_files", ()) or ())
    }
    manifest_entries = {
        _clean_path(str(entry.path)): str(entry.content_digest)
        for entry in manifest.entries
    }
    for path in sorted(set(snapshot_files) - set(manifest_entries)):
        failures.append(f"unified_source_entry_missing:{path}")
    for path in sorted(set(manifest_entries) - set(snapshot_files)):
        failures.append(f"unified_source_entry_unknown:{path}")
    for path in sorted(set(snapshot_files) & set(manifest_entries)):
        if snapshot_files[path] != manifest_entries[path]:
            failures.append(f"unified_source_entry_digest_mismatch:{path}")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "SourceKindV1",
    "SourceOwnershipRoleV1",
    "RepositorySourceEntryV1",
    "RepositorySourceManifestV1",
    "classify_source_kind",
    "normalize_source_path",
    "build_repository_source_manifest",
    "source_manifest_snapshot_failures",
]
