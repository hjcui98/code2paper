"""Non-authorizing content-regression diagnostics for frozen project fixtures."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


class MethodContentUnitFixtureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    required_alias_groups: tuple[tuple[str, ...], ...]


class MethodContentProjectFixtureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    units: tuple[MethodContentUnitFixtureV1, ...]


class MethodContentRegressionFixtureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    authority: str
    prose_copied_from_paper: bool = False
    projects: dict[str, MethodContentProjectFixtureV1]

    @model_validator(mode="after")
    def _non_authorizing(self) -> "MethodContentRegressionFixtureV1":
        if self.authority != "diagnostic_non_authorizing":
            raise ValueError("content fixture must be diagnostic and non-authorizing")
        if self.prose_copied_from_paper:
            raise ValueError("content fixture must not copy original paper prose")
        return self


class MethodContentUnitResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    covered: bool
    matched_aliases: tuple[str, ...] = ()
    missing_alias_groups: tuple[tuple[str, ...], ...] = ()


class MethodContentRegressionReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    fixture_authority: str = "diagnostic_non_authorizing"
    units: tuple[MethodContentUnitResultV1, ...]
    covered_units: int
    total_units: int
    complete: bool
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodContentRegressionReportV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def load_method_content_fixture(path: str | Path) -> MethodContentRegressionFixtureV1:
    return MethodContentRegressionFixtureV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def evaluate_method_content_artifacts(
    *,
    fixture: MethodContentRegressionFixtureV1,
    project_id: str,
    artifacts: dict[str, Any],
) -> MethodContentRegressionReportV1:
    """Evaluate authorized artifacts without promoting fixture text to facts."""

    project = fixture.projects.get(project_id)
    if project is None:
        raise ValueError(f"unknown content-regression project: {project_id}")
    # The repository-wide inventory is useful for diagnosing whether a miss
    # exists in source at all, but it is deliberately non-authorizing.  D2.5
    # content coverage must be visible in facts/claims/equations/configuration
    # or the section plan that the Writer can actually consume.
    authorizing_artifacts = {
        key: value for key, value in artifacts.items() if key != "inventory"
    }
    haystack = _artifact_haystack(authorizing_artifacts)
    results: list[MethodContentUnitResultV1] = []
    for unit in project.units:
        matched: list[str] = []
        missing: list[tuple[str, ...]] = []
        for group in unit.required_alias_groups:
            alias = next((item for item in group if _contains_alias(haystack, item)), "")
            if alias:
                matched.append(alias)
            else:
                missing.append(group)
        results.append(MethodContentUnitResultV1(
            unit_id=unit.unit_id,
            covered=not missing,
            matched_aliases=tuple(matched),
            missing_alias_groups=tuple(missing),
        ))
    covered = sum(item.covered for item in results)
    return MethodContentRegressionReportV1(
        project_id=project_id,
        units=tuple(results),
        covered_units=covered,
        total_units=len(results),
        complete=covered == len(results),
    )


def build_python_behavior_inventory(
    *,
    files: dict[str, str],
    repo_snapshot_id: str,
    project_tree_hash: str,
) -> dict[str, Any]:
    """Build an exact-source diagnostic inventory without creating claims."""

    adapter = PythonBehaviorAdapter()
    index = adapter.index_symbols(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        files=files,
    )
    operations: list[dict[str, Any]] = []
    for symbol in index.symbols:
        if symbol.kind not in {"function", "method"}:
            continue
        source = files.get(symbol.path)
        if source is None:
            continue
        for node in adapter.extract_operations(symbol, source):
            operations.append({
                "symbol": symbol.qualified_name,
                "predicate": node.predicate,
                "operands": list(node.operands),
                "result": node.result,
                "guard": node.guard,
                "diagnostics": list(node.diagnostics),
                "source_span_id": node.source_span_id,
            })
    payload = {
        "schema_version": "1.0",
        "authority": "executable_hard_diagnostic_inventory",
        "repo_snapshot_id": repo_snapshot_id,
        "project_tree_hash": project_tree_hash,
        "operation_descriptors": operations,
    }
    payload["content_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def _artifact_haystack(artifacts: dict[str, Any]) -> str:
    allowed_keys = {
        "facts", "claims", "equations", "configurations", "sections", "publication",
        "inventory",
        "argument_units", "section_markdown", "canonical_text", "semantic_context",
        "subject", "object", "predicate", "conditions", "expression", "heading",
        "reader_question", "key", "value", "operation_descriptors",
        "symbol", "result", "operands", "guard", "diagnostics",
    }

    def project(value: Any, key: str = "") -> Any:
        if isinstance(value, dict):
            return {
                child_key: project(child, child_key)
                for child_key, child in value.items()
                if child_key in allowed_keys
            }
        if isinstance(value, list):
            return [project(item, key) for item in value]
        return value if isinstance(value, (str, int, float, bool)) else ""

    return json.dumps(project(artifacts), ensure_ascii=False, sort_keys=True).lower()


def _contains_alias(haystack: str, alias: str) -> bool:
    normalized = alias.strip().lower()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9_]+", normalized):
        # Code-native identifiers use underscores as semantic separators
        # (``knn_k``, ``time_mamba``).  The diagnostic should recognize the
        # requested unit without requiring publication prose to copy the
        # identifier byte-for-byte.
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", haystack))
    return normalized in haystack


__all__ = [
    "MethodContentRegressionFixtureV1",
    "MethodContentRegressionReportV1",
    "build_python_behavior_inventory",
    "evaluate_method_content_artifacts",
    "load_method_content_fixture",
]
