"""Non-authorizing content-regression diagnostics for frozen project fixtures."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


class MethodContentUnitFixtureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    required_alias_groups: tuple[tuple[str, ...], ...]
    source: str = "paper_structure_reference"
    repo_snapshot_sha: str = ""
    repo_verifiable: bool = False
    active_path_status: str = "unknown"
    runtime_authority: str = "diagnostic_non_authorizing"


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


class MethodSynthesisProjectBaselineV1(BaseModel):
    """Non-authorizing source-to-render counters for one frozen replay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facet_status_counts: dict[str, int]
    draft_nonempty: bool
    writer_call_count: int = Field(ge=0)
    writer_repair_rounds: int = Field(ge=0)
    writer_repair_commits: int = Field(ge=0)
    formalizer_call_count: int = Field(ge=0)
    formula_package_count: int = Field(ge=0)
    used_equation_count: int = Field(ge=0)
    planned_paragraph_count: int = Field(ge=0)
    rendered_paragraph_count: int = Field(ge=0)
    content_states: dict[str, int] = Field(default_factory=dict)
    dropped_section_ids: tuple[str, ...] = ()
    # Diagnostic efficiency counters.  They are never used as authority or
    # readiness gates; zero is an honest value for legacy frozen baselines.
    total_tokens: int = Field(default=0, ge=0)
    total_tokens_per_candidate: int = Field(default=0, ge=0)
    callback_tokens: int = Field(default=0, ge=0)
    formalizer_input_tokens: int = Field(default=0, ge=0)
    writer_input_tokens: int = Field(default=0, ge=0)
    shared_payload_tokens: int = Field(default=0, ge=0)
    validated_core_detail_count: int = Field(default=0, ge=0)
    validated_paragraph_count: int = Field(default=0, ge=0)
    tokens_per_validated_core_detail: float = Field(default=0.0, ge=0.0)
    calls_per_validated_paragraph: float = Field(default=0.0, ge=0.0)
    callback_token_fraction: float = Field(default=0.0, ge=0.0, le=1.0)


class MethodSynthesisBaselineV1(BaseModel):
    """Frozen protocol and project counters used only for diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    protocol: dict[str, Any]
    projects: dict[str, MethodSynthesisProjectBaselineV1]


class MethodSynthesisBaselinesV1(BaseModel):
    """Typed loader for the funnel's source-to-render baseline sidecar."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    authority: str
    notes: str = ""
    baselines: tuple[dict[str, Any], ...] = ()
    source_to_render_baseline: MethodSynthesisBaselineV1

    @model_validator(mode="after")
    def _non_authorizing(self) -> "MethodSynthesisBaselinesV1":
        if self.authority != "diagnostic_non_authorizing":
            raise ValueError("synthesis baselines must be diagnostic and non-authorizing")
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


class MethodAuthoringOracleUnitV1(BaseModel):
    """One non-authorizing semantic unit from an original-paper oracle.

    The oracle stores aliases and placement expectations only.  It never
    stores paper prose, source facts, or evidence references, and therefore
    cannot grant a Method claim authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    story_role: str = ""
    expected_heading_aliases: tuple[str, ...] = ()
    required_alias_groups: tuple[tuple[str, ...], ...] = ()
    formula_alias_groups: tuple[tuple[str, ...], ...] = ()
    require_display_math: bool = False
    polarity: str = ""
    source: str = "paper_structure_reference"
    repo_snapshot_sha: str = ""
    repo_verifiable: bool = False
    active_path_status: str = "unknown"
    runtime_authority: str = "diagnostic_non_authorizing"


class MethodAuthoringOracleProjectV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    units: tuple[MethodAuthoringOracleUnitV1, ...]


class MethodAuthoringOracleV1(BaseModel):
    """Offline original-paper comparison fixture (diagnostic only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    authority: str
    prose_copied_from_paper: bool = False
    projects: dict[str, MethodAuthoringOracleProjectV1]

    @model_validator(mode="after")
    def _non_authorizing(self) -> "MethodAuthoringOracleV1":
        if self.authority != "diagnostic_non_authorizing":
            raise ValueError("authoring oracle must be diagnostic and non-authorizing")
        if self.prose_copied_from_paper:
            raise ValueError("authoring oracle must not copy original paper prose")
        return self


class MethodAuthoringOracleUnitResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unit_id: str
    story_role: str = ""
    original_covered: bool
    candidate_covered: bool
    candidate_missing_alias_groups: tuple[tuple[str, ...], ...] = ()
    candidate_missing_formula_groups: tuple[tuple[str, ...], ...] = ()
    candidate_heading_found: bool = False
    candidate_has_display_math: bool = False
    polarity_ok: bool = True


class MethodAuthoringOracleReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    fixture_authority: str = "diagnostic_non_authorizing"
    units: tuple[MethodAuthoringOracleUnitResultV1, ...]
    original_covered_units: int
    candidate_covered_units: int
    total_units: int
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "MethodAuthoringOracleReportV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        object.__setattr__(
            self,
            "content_digest",
            "sha256:" + hashlib.sha256(encoded).hexdigest(),
        )
        return self


def load_method_content_fixture(path: str | Path) -> MethodContentRegressionFixtureV1:
    return MethodContentRegressionFixtureV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def load_method_synthesis_baselines(path: str | Path) -> MethodSynthesisBaselinesV1:
    """Load source-to-render counters without granting them fact authority."""

    return MethodSynthesisBaselinesV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def load_method_authoring_oracle(path: str | Path) -> MethodAuthoringOracleV1:
    """Load aliases for an offline original-paper comparison."""

    return MethodAuthoringOracleV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def evaluate_method_authoring_oracle(
    *,
    oracle: MethodAuthoringOracleV1,
    project_id: str,
    candidate_text: str,
    original_text: str,
) -> MethodAuthoringOracleReportV1:
    """Compare candidate structure/atoms to the offline paper oracle.

    This deliberately uses alias groups rather than exact paper wording.  The
    original text is an evaluation-only baseline and is never returned as a
    fact or passed to a Writer prompt.
    """

    project = oracle.projects.get(project_id)
    if project is None:
        raise ValueError(f"unknown authoring-oracle project: {project_id}")
    original_haystack = str(original_text or "").lower()
    candidate_haystack = str(candidate_text or "").lower()
    heading_text = "\n".join(
        line.strip().lstrip("#").strip()
        for line in candidate_text.splitlines()
        if line.lstrip().startswith("#")
    ).lower()
    display_math = bool(re.search(
        r"(?s)(?:\\\[.*?\\\]|\\begin\{(?:equation|aligned|gather|split|cases)\}.*?\\end\{(?:equation|aligned|gather|split|cases)\}|\$\$.*?\$\$)",
        candidate_text,
    ))
    results: list[MethodAuthoringOracleUnitResultV1] = []
    for unit in project.units:
        original_missing = [
            group for group in unit.required_alias_groups
            if not any(_contains_alias(original_haystack, alias) for alias in group)
        ]
        candidate_missing = [
            group for group in unit.required_alias_groups
            if not any(_contains_alias(candidate_haystack, alias) for alias in group)
        ]
        formula_missing = [
            group for group in unit.formula_alias_groups
            if not any(_contains_alias(candidate_haystack, alias) for alias in group)
        ]
        heading_found = not unit.expected_heading_aliases or any(
            _contains_alias(heading_text, alias)
            for alias in unit.expected_heading_aliases
        )
        polarity_ok = _oracle_polarity_ok(candidate_haystack, unit.polarity)
        original_covered = not original_missing
        candidate_covered = (
            not candidate_missing
            and not formula_missing
            and heading_found
            and (display_math if unit.require_display_math else True)
            and polarity_ok
        )
        results.append(MethodAuthoringOracleUnitResultV1(
            unit_id=unit.unit_id,
            story_role=unit.story_role,
            original_covered=original_covered,
            candidate_covered=candidate_covered,
            candidate_missing_alias_groups=tuple(candidate_missing),
            candidate_missing_formula_groups=tuple(formula_missing),
            candidate_heading_found=heading_found,
            candidate_has_display_math=display_math,
            polarity_ok=polarity_ok,
        ))
    return MethodAuthoringOracleReportV1(
        project_id=project_id,
        fixture_authority=oracle.authority,
        units=tuple(results),
        original_covered_units=sum(item.original_covered for item in results),
        candidate_covered_units=sum(item.candidate_covered for item in results),
        total_units=len(results),
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


def _oracle_polarity_ok(haystack: str, polarity: str) -> bool:
    """Check only the small set of generic polarity contracts in fixtures."""

    name = str(polarity or "").strip().casefold()
    if not name:
        return True
    if name == "exclude_below_threshold":
        has_below = bool(re.search(
            r"(?:below|less than|under|<)\W{0,24}(?:the\W+)?(?:threshold|tau|τ)",
            haystack,
        ))
        has_exclude = bool(re.search(
            r"(?:below|less than|under|<).{0,100}(?:exclude|prun|discard|drop|reject|fail|continue)",
            haystack,
        ))
        has_admit = bool(re.search(
            r"(?:below|less than|under|<).{0,100}(?:keep|admit|retain|include|accept)",
            haystack,
        ))
        return (has_exclude or not has_below) and not has_admit
    if name == "larger_gap_larger_step":
        has_gap = bool(re.search(r"(?:larger|greater|longer).{0,80}(?:gap|timespan)", haystack))
        has_step = bool(re.search(r"(?:larger|greater|increase).{0,80}(?:step|delta|Δ)", haystack))
        return has_gap and has_step
    return True


def evaluate_mechanism_detail_recall(
    contexts: Any,
    rendered_text: str,
) -> dict[str, Any]:
    """Measure recall of mechanism details in rendered text (diagnostic only)."""
    haystack = str(rendered_text or "").lower()
    all_details = [
        d for ctx in getattr(contexts, "contexts", ())
        for d in getattr(ctx, "details", ())
    ]
    core_details = [d for d in all_details if getattr(d, "importance", "") == "core"]
    supporting_details = [d for d in all_details if getattr(d, "importance", "") == "supporting"]

    def _is_covered(d: Any) -> bool:
        anchor = getattr(d, "semantic_atom", "") or getattr(d, "predicate", "")
        if not anchor:
            return False
        tokens = [t.lower() for t in re.findall(r"\w+", anchor) if len(t) > 3]
        if not tokens:
            return True
        return sum(1 for t in tokens if t in haystack) >= max(1, len(tokens) // 2)

    core_covered = sum(1 for d in core_details if _is_covered(d))
    supp_covered = sum(1 for d in supporting_details if _is_covered(d))

    return {
        "core_detail_count": len(core_details),
        "core_detail_covered": core_covered,
        "core_detail_recall": core_covered / len(core_details) if core_details else 1.0,
        "supporting_detail_count": len(supporting_details),
        "supporting_detail_covered": supp_covered,
        "supporting_detail_recall": supp_covered / len(supporting_details) if supporting_details else 1.0,
    }


def evaluate_context_writer_delivery(
    contexts: Any,
    writer_views: tuple[Any, ...] | Any,
) -> dict[str, Any]:
    """Verify that all core details in contexts reached writer shared views without loss."""
    all_core = {
        d.detail_id
        for ctx in getattr(contexts, "contexts", ())
        for d in getattr(ctx, "details", ())
        if getattr(d, "importance", "") == "core" and getattr(d, "publication_policy", "") == "clean_candidate"
    }
    views = writer_views if isinstance(writer_views, (tuple, list)) else (writer_views,)
    delivered_details: set[str] = set()
    for v in views:
        for d in getattr(v, "ordered_details", ()):
            if isinstance(d, Mapping):
                did = str(d.get("detail_id") or "")
            else:
                did = getattr(d, "detail_id", "")
            if did:
                delivered_details.add(did)

    missing_core = all_core - delivered_details
    core_count = len(all_core)
    delivered_core = core_count - len(missing_core)
    loss_rate = len(missing_core) / core_count if core_count else 0.0

    return {
        "context_core_count": core_count,
        "delivered_core_count": delivered_core,
        "missing_core_ids": tuple(sorted(missing_core)),
        "context_to_writer_core_loss_rate": loss_rate,
        "delivery_complete": len(missing_core) == 0,
    }


def evaluate_mechanism_contamination(
    contexts: Any,
    rendered_sections: Mapping[str, str],
) -> dict[str, Any]:
    """Detect cross-mechanism operator/concept leakage across distinct sections."""
    contamination_events: list[dict[str, Any]] = []
    mech_tokens: dict[str, set[str]] = {}
    for ctx in getattr(contexts, "contexts", ()):
        mid = getattr(ctx, "mechanism_id", "")
        tokens = {
            t.lower()
            for d in getattr(ctx, "details", ())
            for t in re.findall(r"\w+", getattr(d, "predicate", "") + " " + getattr(d, "semantic_atom", ""))
            if len(t) > 4
        }
        mech_tokens[mid] = tokens

    mech_list = list(mech_tokens.keys())
    for i, m1 in enumerate(mech_list):
        for m2 in mech_list[i + 1:]:
            s1_text = rendered_sections.get(m1, "").lower()
            unique_to_m2 = mech_tokens[m2] - mech_tokens[m1]
            leaked = [t for t in unique_to_m2 if t in s1_text]
            if len(leaked) >= 3:
                contamination_events.append({
                    "mechanism_section": m1,
                    "foreign_mechanism": m2,
                    "leaked_tokens": leaked[:5],
                })

    return {
        "contamination_event_count": len(contamination_events),
        "contamination_events": tuple(contamination_events),
        "cross_mechanism_contamination_free": len(contamination_events) == 0,
    }


def evaluate_formula_fidelity(
    packages: tuple[Any, ...],
    contexts: Any,
) -> dict[str, Any]:
    """Check formula fidelity against mechanism contexts."""
    known_mechs = {getattr(ctx, "mechanism_id", "") for ctx in getattr(contexts, "contexts", ())}
    valid_pkgs = 0
    mismatches: list[str] = []
    for pkg in packages:
        mid = getattr(pkg, "mechanism_id", "")
        if mid and known_mechs and mid not in known_mechs:
            mismatches.append(f"package {getattr(pkg, 'package_id', '')} references unknown mechanism {mid}")
        else:
            valid_pkgs += 1

    return {
        "package_count": len(packages),
        "valid_package_count": valid_pkgs,
        "mismatch_count": len(mismatches),
        "mismatches": tuple(mismatches),
        "formula_fidelity_ok": len(mismatches) == 0,
    }


def compute_method_synthesis_efficiency_metrics(
    *,
    total_tokens: int = 0,
    callback_tokens: int = 0,
    formalizer_input_tokens: int = 0,
    writer_input_tokens: int = 0,
    shared_payload_tokens: int = 0,
    validated_core_detail_count: int = 0,
    validated_paragraph_count: int = 0,
    writer_call_count: int = 0,
    formalizer_call_count: int = 0,
    call_count: int | None = None,
) -> dict[str, Any]:
    """Compute WP-0 efficiency diagnostics without authorizing a run.

    The helper is intentionally pure so frozen replay baselines and live
    traces use the same denominator rules.  A zero denominator returns zero
    for a per-unit cost; it is never converted into a successful quality
    score.
    """

    total = max(0, int(total_tokens or 0))
    callback = max(0, int(callback_tokens or 0))
    validated_core = max(0, int(validated_core_detail_count or 0))
    validated_paragraphs = max(0, int(validated_paragraph_count or 0))
    writers = max(0, int(writer_call_count or 0))
    formalizers = max(0, int(formalizer_call_count or 0))
    calls = max(0, int(call_count if call_count is not None else writers + formalizers))
    return {
        "total_tokens_per_candidate": total,
        "total_tokens": total,
        "callback_tokens": callback,
        "formalizer_input_tokens": max(0, int(formalizer_input_tokens or 0)),
        "writer_input_tokens": max(0, int(writer_input_tokens or 0)),
        "shared_payload_tokens": max(0, int(shared_payload_tokens or 0)),
        "validated_core_detail_count": validated_core,
        "validated_paragraph_count": validated_paragraphs,
        "writer_call_count": writers,
        "formalizer_call_count": formalizers,
        "call_count": calls,
        "tokens_per_validated_core_detail": (
            round(total / validated_core, 4) if validated_core else 0.0
        ),
        "calls_per_validated_paragraph": (
            round(calls / validated_paragraphs, 4) if validated_paragraphs else 0.0
        ),
        "callback_token_fraction": (
            round(callback / total, 4) if total else 0.0
        ),
    }


__all__ = [
    "MethodAuthoringOracleProjectV1",
    "MethodAuthoringOracleReportV1",
    "MethodAuthoringOracleUnitResultV1",
    "MethodAuthoringOracleUnitV1",
    "MethodAuthoringOracleV1",
    "MethodContentProjectFixtureV1",
    "MethodContentRegressionFixtureV1",
    "MethodContentRegressionReportV1",
    "MethodContentUnitFixtureV1",
    "MethodContentUnitResultV1",
    "MethodSynthesisBaselinesV1",
    "MethodSynthesisProjectBaselineV1",
    "MethodSynthesisBaselineV1",
    "build_python_behavior_inventory",
    "compute_method_synthesis_efficiency_metrics",
    "evaluate_context_writer_delivery",
    "evaluate_formula_fidelity",
    "evaluate_mechanism_contamination",
    "evaluate_mechanism_detail_recall",
    "evaluate_method_authoring_oracle",
    "evaluate_method_content_artifacts",
    "load_method_authoring_oracle",
    "load_method_content_fixture",
    "load_method_synthesis_baselines",
]
