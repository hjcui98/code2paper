"""Source authority contracts for the robust LangGraph research agent.

Implements the authority hierarchy defined in
``docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`` section 3.1:

| level            | content                                        | allowed use                         |
| ---------------- | ---------------------------------------------- | ----------------------------------- |
| executable_hard  | source, run scripts, build files, config       | support implementation behavior     |
| test_scoped      | test source, fixtures                          | support test-scope expectations only|
| semantic_hint    | README, Markdown, paper drafts, TeX, PDF, text | search queries, term aliases only   |
| author_intent    | author YAML                                    | research priority, obligations only |

Every span, tool observation, evidence packet, code fact and atomic claim in
the V3 research plane MUST carry a ``SourceAuthorityV1`` tag.  Positive
implementation claims require an ``executable_hard`` anchor; ``semantic_hint``
and ``author_intent`` can never be upgraded to hard evidence.

This module is contracts-only in R0: it does not modify the existing V2
pipeline.  Downstream batches (R1+) integrate the policy into the research
tools, packet validator, fact compiler and claim authorizer.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SourceAuthorityV1 = Literal[
    "executable_hard",
    "test_scoped",
    "semantic_hint",
    "author_intent",
]


SOURCE_AUTHORITY_LEVELS: tuple[SourceAuthorityV1, ...] = (
    "executable_hard",
    "test_scoped",
    "semantic_hint",
    "author_intent",
)


class SourceAuthorityPolicy(BaseModel):
    """Declarative classification policy used by the V3 research plane.

    The policy is intentionally path-based and deterministic.  Project-specific
    overrides may be supplied via ``explicit_overrides`` but they MUST respect
    the hard rule below: an entry can only *lower* the authority of a file
    (e.g. mark a ``.py`` file as ``test_scoped``), never *upgrade* a hint or
    author-YAML file into ``executable_hard``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = "source-authority-v1"
    schema_version: str = "1.0"
    executable_suffixes: tuple[str, ...] = (
        ".py", ".pyi", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".scala",
        ".go", ".rs", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx", ".cu",
        ".swift", ".m", ".mm", ".rb", ".php", ".pl", ".lua", ".r", ".jl",
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        ".toml", ".cfg", ".ini", ".yaml", ".yml", ".json", ".xml", ".proto",
        ".dockerfile", ".makefile", ".cmake", ".scons", ".bazel", ".star",
        ".gradle", ".sbt", ".maven", ".pom",
    )
    build_filenames: tuple[str, ...] = (
        "Makefile", "makefile", "GNUmakefile", "CMakeLists.txt", "setup.py",
        "setup.cfg", "pyproject.toml", "requirements.txt", "Pipfile",
        "poetry.lock", "package.json", "package-lock.json", "yarn.lock",
        "tsconfig.json", "webpack.config.js", "vite.config.js", "rollup.config.js",
        "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "build.gradle",
        "pom.xml", "BUILD", "BUILD.bazel", "WORKSPACE", "Dockerfile",
        "docker-compose.yml", "docker-compose.yaml", ".dockerignore",
        "SConstruct", "Meson.build", "conanfile.txt", "conanfile.py",
        "environment.yml", "Tox.ini", "tox.ini",
    )
    test_path_patterns: tuple[str, ...] = (
        "tests/", "test/", "__tests__/", "test_", "_test/",
        "spec/", "specs/", "fixtures/", "fixture/", "mocks/", "mock/",
        "conftest.py", "test_conftest.py",
    )
    test_filename_patterns: tuple[str, ...] = (
        r"^test_.+\.pyi?$",
        r".*_test\.pyi?$",
        r".*\.test\.(js|ts|jsx|tsx)$",
        r".*\.spec\.(js|ts|jsx|tsx)$",
        r"^test_.+\.(go|rs|java)$",
        r".*_test\.(go|rs|java)$",
    )
    hint_suffixes: tuple[str, ...] = (
        ".md", ".markdown", ".mdx", ".rst", ".tex", ".bib", ".pdf", ".txt",
        ".text", ".org", ".adoc", ".asciidoc", ".wiki", ".ipynb",
    )
    hint_filenames: tuple[str, ...] = (
        "README", "README.md", "README.rst", "README.txt", "readme",
        "CHANGELOG", "CHANGELOG.md", "CHANGES", "CHANGES.md", "NEWS",
        "CONTRIBUTING", "CONTRIBUTING.md", "LICENSE", "NOTICE",
        "paperdraft", "paperdraft.md", "paperdraft.txt",
    )
    author_intent_filenames: tuple[str, ...] = (
        "author.yaml", "author.yml", "author_intent.yaml", "author_intent.yml",
        "intent.yaml", "intent.yml", "authors.yaml", "authors.yml",
        "author_markers.yaml", "author_markers.yml",
    )
    explicit_overrides: dict[str, SourceAuthorityV1] = Field(default_factory=dict)
    content_digest: str = ""

    @field_validator("explicit_overrides")
    @classmethod
    def _no_authority_upgrade(cls, value: dict[str, SourceAuthorityV1]) -> dict[str, SourceAuthorityV1]:
        for path, authority in value.items():
            if authority not in SOURCE_AUTHORITY_LEVELS:
                raise ValueError(f"unknown source authority level for {path}: {authority}")
        return value

    def classify(self, path: str) -> SourceAuthorityV1:
        """Classify a single repository-relative path.

        Order matters: explicit overrides win, then author-intent filenames,
        then test patterns, then hint filenames/suffixes, then executable
        suffixes/build filenames.  Anything unmatched defaults to
        ``executable_hard`` because the V3 research plane treats source-tree
        files as the implementation baseline unless explicitly marked otherwise.
        """

        normalized = _normalize_path(path)
        explicit = self.explicit_overrides.get(normalized) or self.explicit_overrides.get(path)
        if explicit:
            if not _is_upgrade_safe(_default_classification(self, normalized), explicit):
                raise ValueError(
                    f"explicit override for {path} upgrades authority; only downgrades are allowed"
                )
            return explicit
        return _default_classification(self, normalized)


def default_source_authority_policy() -> SourceAuthorityPolicy:
    """Return the canonical policy used by the V3 research plane."""

    payload = _policy_payload(SourceAuthorityPolicy())
    digest = _digest_payload(payload)
    return SourceAuthorityPolicy(content_digest=digest)


def classify_source_authority(
    path: str,
    *,
    policy: SourceAuthorityPolicy | None = None,
) -> SourceAuthorityV1:
    """Convenience classifier matching ``classify_source_authority(path)``.

    The function is deterministic and side-effect free so it can be used inside
    LangChain tool runtime, packet validators and freshness checks without
    injecting state.
    """

    return (policy or _ensure_default_policy()).classify(path)


def can_support_positive_claim(authority: SourceAuthorityV1) -> bool:
    """Only ``executable_hard`` may anchor a positive implementation claim."""

    return authority == "executable_hard"


def can_support_test_scoped_claim(authority: SourceAuthorityV1) -> bool:
    """``test_scoped`` may support test-boundary expectations, not mainline."""

    return authority in {"executable_hard", "test_scoped"}


def is_hint_or_intent(authority: SourceAuthorityV1) -> bool:
    """``semantic_hint`` and ``author_intent`` cannot become hard evidence."""

    return authority in {"semantic_hint", "author_intent"}


def authority_rank(authority: SourceAuthorityV1) -> int:
    """Lower number = stronger authority.  Useful for upgrade-refusal checks."""

    order = {
        "executable_hard": 0,
        "test_scoped": 1,
        "semantic_hint": 2,
        "author_intent": 3,
    }
    return order[authority]


def assert_authority_allows_positive_claim(
    authority: SourceAuthorityV1,
    *,
    context: str = "",
) -> None:
    """Hard gate for ``authorize_atomic_claims`` in R4.

    R0 only exposes the contract; the actual authorizer ships in R4.  Keeping
    the helper here means downstream batches import a single authority module.
    """

    if not can_support_positive_claim(authority):
        detail = f" ({context})" if context else ""
        raise ValueError(
            "positive implementation claims require an executable_hard anchor; "
            f"got {authority}{detail}"
        )


class AuthorityClassifiedFile(BaseModel):
    """A snapshot file annotated with its source authority level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    authority: SourceAuthorityV1
    classification_basis: str = ""

    @field_validator("authority")
    @classmethod
    def _known_authority(cls, value: SourceAuthorityV1) -> SourceAuthorityV1:
        if value not in SOURCE_AUTHORITY_LEVELS:
            raise ValueError(f"unknown source authority: {value}")
        return value


class SourceAuthorityClassification(BaseModel):
    """Aggregate classification result attached to a snapshot or observation set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    policy_id: str = "source-authority-v1"
    policy_digest: str = ""
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    files: list[AuthorityClassifiedFile] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    content_digest: str = ""


def classify_snapshot_files(
    paths: Iterable[str],
    *,
    policy: SourceAuthorityPolicy | None = None,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> SourceAuthorityClassification:
    """Classify an iterable of repository-relative paths in one pass.

    Used by the R1 repository indexer to attach authority tags to every
    observed file.  The result is content-addressed so freshness checks can
    detect policy drift.
    """

    active_policy = policy or _ensure_default_policy()
    files: list[AuthorityClassifiedFile] = []
    counts: dict[str, int] = {level: 0 for level in SOURCE_AUTHORITY_LEVELS}
    for path in paths:
        normalized = _normalize_path(path)
        basis, authority = _classify_with_basis(active_policy, normalized)
        files.append(
            AuthorityClassifiedFile(path=normalized, authority=authority, classification_basis=basis)
        )
        counts[authority] = counts.get(authority, 0) + 1
    payload = {
        "schema_version": "1.0",
        "policy_id": active_policy.policy_id,
        "policy_digest": active_policy.content_digest,
        "repo_snapshot_id": repo_snapshot_id,
        "project_tree_hash": project_tree_hash,
        "files": [item.model_dump(mode="json") for item in files],
        "counts": counts,
    }
    return SourceAuthorityClassification(
        schema_version="1.0",
        policy_id=active_policy.policy_id,
        policy_digest=active_policy.content_digest,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        files=files,
        counts=counts,
        content_digest=_digest_payload(payload),
    )


def merge_authority_sets(
    left: SourceAuthorityClassification,
    right: SourceAuthorityClassification,
) -> SourceAuthorityClassification:
    """Right-biased merge for incremental behavior-graph updates.

    R0 ships the helper so R2 ``build_behavior_subgraph`` can merge
    observations without redefining the contract.
    """

    if left.policy_id != right.policy_id or left.policy_digest != right.policy_digest:
        raise ValueError("cannot merge authority sets produced by different policies")
    by_path: dict[str, AuthorityClassifiedFile] = {item.path: item for item in left.files}
    for item in right.files:
        by_path[item.path] = item
    return classify_snapshot_files(
        by_path.keys(),
        policy=_policy_from_digest(right.policy_id, right.policy_digest),
        repo_snapshot_id=right.repo_snapshot_id,
        project_tree_hash=right.project_tree_hash,
    )


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


_DEFAULT_POLICY: SourceAuthorityPolicy | None = None


def _ensure_default_policy() -> SourceAuthorityPolicy:
    global _DEFAULT_POLICY
    if _DEFAULT_POLICY is None:
        _DEFAULT_POLICY = default_source_authority_policy()
    return _DEFAULT_POLICY


# Trigger default policy construction at import time so classify_source_authority
# is fast on first call and any policy-build error surfaces immediately.
_ENSURED = None
try:
    _ENSURED = _ensure_default_policy()
except Exception:  # pragma: no cover - defensive, should never happen
    _ENSURED = None


def _normalize_path(path: str) -> str:
    cleaned = (path or "").strip().replace("\\", "/")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    return cleaned.lstrip("./").lstrip("/")


def _matches_test_filename(name: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return True
    return False


def _is_author_intent_filename(name: str, author_intent_filenames: tuple[str, ...]) -> bool:
    lower = name.lower()
    return lower in {item.lower() for item in author_intent_filenames}


def _is_hint_filename(name: str, hint_filenames: tuple[str, ...]) -> bool:
    lower = name.lower()
    if lower in {item.lower() for item in hint_filenames}:
        return True
    if lower.startswith("readme") or lower.startswith("changelog") or lower.startswith("contributing"):
        return True
    return False


def _has_test_path_segment(path: str, test_path_patterns: tuple[str, ...]) -> bool:
    lower = path.lower()
    for pattern in test_path_patterns:
        if pattern in lower:
            return True
    return False


def _default_classification(policy: SourceAuthorityPolicy, path: str) -> SourceAuthorityV1:
    name = PurePosixPath(path).name
    suffix = PurePosixPath(path).suffix.lower()

    if _is_author_intent_filename(name, policy.author_intent_filenames):
        return "author_intent"

    if _has_test_path_segment(path, policy.test_path_patterns) or _matches_test_filename(
        name, policy.test_filename_patterns
    ):
        return "test_scoped"

    if _is_hint_filename(name, policy.hint_filenames) or suffix in policy.hint_suffixes:
        return "semantic_hint"

    if suffix in policy.executable_suffixes:
        return "executable_hard"

    if name in policy.build_filenames or name.lower() in {item.lower() for item in policy.build_filenames}:
        return "executable_hard"

    # Unknown file types default to executable_hard so the V3 plane does not
    # silently drop configuration or build files.  Hint-only suffixes are
    # enumerated explicitly above.
    return "executable_hard"


def _classify_with_basis(
    policy: SourceAuthorityPolicy,
    path: str,
) -> tuple[str, SourceAuthorityV1]:
    name = PurePosixPath(path).name
    suffix = PurePosixPath(path).suffix.lower()

    if path in policy.explicit_overrides:
        return "explicit_override", policy.explicit_overrides[path]

    if _is_author_intent_filename(name, policy.author_intent_filenames):
        return "author_intent_filename", "author_intent"

    if _has_test_path_segment(path, policy.test_path_patterns):
        return "test_path_segment", "test_scoped"
    if _matches_test_filename(name, policy.test_filename_patterns):
        return "test_filename_pattern", "test_scoped"

    if _is_hint_filename(name, policy.hint_filenames):
        return "hint_filename", "semantic_hint"
    if suffix in policy.hint_suffixes:
        return "hint_suffix", "semantic_hint"

    if suffix in policy.executable_suffixes:
        return "executable_suffix", "executable_hard"
    if name in policy.build_filenames or name.lower() in {item.lower() for item in policy.build_filenames}:
        return "build_filename", "executable_hard"

    return "default_executable", "executable_hard"


def _is_upgrade_safe(
    current: SourceAuthorityV1,
    target: SourceAuthorityV1,
) -> bool:
    """Explicit overrides may only lower authority, never upgrade it."""

    return authority_rank(target) >= authority_rank(current)


def _policy_from_digest(policy_id: str, _digest: str) -> SourceAuthorityPolicy:
    """Reconstruct a policy instance for merge_authority_sets.

    The default policy is canonical; project-specific overrides are restored by
    the caller when needed.  R0 only uses the default policy.
    """

    return _ensure_default_policy()


def _policy_payload(policy: SourceAuthorityPolicy) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "schema_version": policy.schema_version,
        "executable_suffixes": list(policy.executable_suffixes),
        "build_filenames": list(policy.build_filenames),
        "test_path_patterns": list(policy.test_path_patterns),
        "test_filename_patterns": list(policy.test_filename_patterns),
        "hint_suffixes": list(policy.hint_suffixes),
        "hint_filenames": list(policy.hint_filenames),
        "author_intent_filenames": list(policy.author_intent_filenames),
    }


def _digest_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "SOURCE_AUTHORITY_LEVELS",
    "SourceAuthorityV1",
    "SourceAuthorityPolicy",
    "SourceAuthorityClassification",
    "AuthorityClassifiedFile",
    "assert_authority_allows_positive_claim",
    "authority_rank",
    "can_support_positive_claim",
    "can_support_test_scoped_claim",
    "classify_snapshot_files",
    "classify_source_authority",
    "default_source_authority_policy",
    "is_hint_or_intent",
    "merge_authority_sets",
]
