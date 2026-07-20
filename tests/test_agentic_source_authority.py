"""R0.2 source authority contract tests.

Exit conditions covered:
- all schemas use ``extra="forbid"``;
- invalid path / unknown authority / authority upgrade are rejected;
- classification hierarchy is deterministic and matches design 3.1.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.source_authority import (
    SOURCE_AUTHORITY_LEVELS,
    AuthorityClassifiedFile,
    SourceAuthorityClassification,
    SourceAuthorityPolicy,
    SourceAuthorityV1,
    assert_authority_allows_positive_claim,
    authority_rank,
    can_support_positive_claim,
    can_support_test_scoped_claim,
    classify_snapshot_files,
    classify_source_authority,
    default_source_authority_policy,
    is_hint_or_intent,
    merge_authority_sets,
)


def test_source_authority_levels_are_canonical() -> None:
    assert SOURCE_AUTHORITY_LEVELS == (
        "executable_hard",
        "test_scoped",
        "semantic_hint",
        "author_intent",
    )


def test_default_policy_is_content_addressed_and_stable() -> None:
    first = default_source_authority_policy()
    second = default_source_authority_policy()
    assert first.content_digest.startswith("sha256:")
    assert first.content_digest == second.content_digest
    assert first.schema_version == "1.0"
    assert first.policy_id == "source-authority-v1"


def test_policy_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SourceAuthorityPolicy(unknown_field=1)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "path, expected",
    [
        ("src/code2paper/agentic/source_authority.py", "executable_hard"),
        ("pyproject.toml", "executable_hard"),
        ("Makefile", "executable_hard"),
        ("Dockerfile", "executable_hard"),
        ("tests/test_agentic_source_authority.py", "test_scoped"),
        ("test/conftest.py", "test_scoped"),
        ("fixtures/data.json", "test_scoped"),
        ("README.md", "semantic_hint"),
        ("docs/design.tex", "semantic_hint"),
        ("paper.pdf", "semantic_hint"),
        ("author.yaml", "author_intent"),
        ("author_intent.yml", "author_intent"),
    ],
)
def test_classify_source_authority_default_paths(path: str, expected: SourceAuthorityV1) -> None:
    assert classify_source_authority(path) == expected


def test_classify_source_authority_unknown_file_defaults_to_executable_hard() -> None:
    # Files without a recognised suffix/filename default to executable_hard so
    # configuration or build files do not silently drop out of the hard tier.
    assert classify_source_authority("config/settings") == "executable_hard"


def test_authority_rank_orders_strong_to_weak() -> None:
    assert authority_rank("executable_hard") < authority_rank("test_scoped")
    assert authority_rank("test_scoped") < authority_rank("semantic_hint")
    assert authority_rank("semantic_hint") < authority_rank("author_intent")


def test_can_support_positive_claim_only_executable_hard() -> None:
    assert can_support_positive_claim("executable_hard") is True
    for level in ("test_scoped", "semantic_hint", "author_intent"):
        assert can_support_positive_claim(level) is False


def test_can_support_test_scoped_claim_executable_and_test() -> None:
    assert can_support_test_scoped_claim("executable_hard") is True
    assert can_support_test_scoped_claim("test_scoped") is True
    assert can_support_test_scoped_claim("semantic_hint") is False
    assert can_support_test_scoped_claim("author_intent") is False


def test_is_hint_or_intent_detects_soft_authorities() -> None:
    assert is_hint_or_intent("semantic_hint") is True
    assert is_hint_or_intent("author_intent") is True
    assert is_hint_or_intent("executable_hard") is False
    assert is_hint_or_intent("test_scoped") is False


def test_assert_authority_allows_positive_claim_rejects_soft_authorities() -> None:
    # executable_hard passes silently.
    assert_authority_allows_positive_claim("executable_hard")
    for level in ("test_scoped", "semantic_hint", "author_intent"):
        with pytest.raises(ValueError, match="executable_hard"):
            assert_authority_allows_positive_claim(level, context=f"ctx-{level}")


def test_explicit_override_refuses_authority_upgrade() -> None:
    # README.md is semantic_hint by default; trying to upgrade it to
    # executable_hard must fail closed when classify() is invoked.
    policy = SourceAuthorityPolicy(explicit_overrides={"README.md": "executable_hard"})
    with pytest.raises(ValueError, match="upgrades authority"):
        policy.classify("README.md")


def test_explicit_override_allows_downgrade() -> None:
    # Marking a .py file as test_scoped is a downgrade and is allowed.
    policy = SourceAuthorityPolicy(explicit_overrides={"src/helper.py": "test_scoped"})
    assert policy.classify("src/helper.py") == "test_scoped"


def test_explicit_override_rejects_unknown_authority() -> None:
    with pytest.raises(ValidationError):
        SourceAuthorityPolicy(explicit_overrides={"src/x.py": "rumor"})  # type: ignore[dict-item]


def test_classify_snapshot_files_returns_content_addressed_classification() -> None:
    paths = [
        "src/main.py",
        "tests/test_main.py",
        "README.md",
        "author.yaml",
        "pyproject.toml",
    ]
    result = classify_snapshot_files(
        paths,
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
    )
    assert isinstance(result, SourceAuthorityClassification)
    assert result.schema_version == "1.0"
    assert result.repo_snapshot_id == "repo:abc"
    assert result.project_tree_hash == "sha256:tree"
    assert result.content_digest.startswith("sha256:")
    assert result.counts["executable_hard"] == 2  # main.py + pyproject.toml
    assert result.counts["test_scoped"] == 1
    assert result.counts["semantic_hint"] == 1
    assert result.counts["author_intent"] == 1
    by_path = {item.path: item for item in result.files}
    assert by_path["src/main.py"].authority == "executable_hard"
    assert by_path["tests/test_main.py"].authority == "test_scoped"
    assert by_path["README.md"].authority == "semantic_hint"
    assert by_path["author.yaml"].authority == "author_intent"


def test_classify_snapshot_files_is_deterministic() -> None:
    paths = ["src/main.py", "tests/test_main.py", "README.md"]
    first = classify_snapshot_files(paths, repo_snapshot_id="r1", project_tree_hash="h1")
    second = classify_snapshot_files(paths, repo_snapshot_id="r1", project_tree_hash="h1")
    assert first.content_digest == second.content_digest


def test_authority_classified_file_rejects_unknown_authority() -> None:
    with pytest.raises(ValidationError):
        AuthorityClassifiedFile(path="src/x.py", authority="rumor")  # type: ignore[arg-type]


def test_authority_classified_file_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuthorityClassifiedFile(path="src/x.py", authority="executable_hard", extra="no")  # type: ignore[call-arg]


def test_source_authority_classification_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SourceAuthorityClassification(schema_version="1.0", surprise=True)  # type: ignore[call-arg]


def test_merge_authority_sets_requires_same_policy() -> None:
    left = classify_snapshot_files(["a.py"], repo_snapshot_id="r", project_tree_hash="h")
    # Build a right set with a different policy digest by mutating policy_id.
    right = left.model_copy(update={"policy_id": "different-policy"})
    with pytest.raises(ValueError, match="different policies"):
        merge_authority_sets(left, right)


def test_merge_authority_sets_right_biased() -> None:
    left = classify_snapshot_files(["a.py", "b.py"], repo_snapshot_id="r", project_tree_hash="h")
    right = classify_snapshot_files(["b.py", "c.py"], repo_snapshot_id="r", project_tree_hash="h")
    merged = merge_authority_sets(left, right)
    paths = {item.path for item in merged.files}
    assert paths == {"a.py", "b.py", "c.py"}
