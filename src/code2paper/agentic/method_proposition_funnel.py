"""Diagnostic Method-proposition funnel (non-authorizing).

Scores frozen content propositions against run artifacts.  The fixture is
test-only: alias groups are information-equivalence keys, not paper wording
and not production claim text.  Realization 0–4 is recorded from a closed
baseline table or from a deterministic alias-overlap heuristic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ImportanceV1 = Literal["critical", "major", "supporting", "optional"]
RealizationV1 = Literal[0, 1, 2, 3, 4]

_IMPORTANCE_WEIGHT: dict[str, float] = {
    "critical": 4.0,
    "major": 2.0,
    "supporting": 1.0,
    "optional": 0.5,
}


class MethodPropositionGoldV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposition_id: str
    importance: ImportanceV1
    stage1: bool = False
    expected_h2: str
    content_class: str
    required_alias_groups: tuple[tuple[str, ...], ...]
    polarity_exclude_below: bool = False


class MethodPropositionFunnelFixtureV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    authority: str
    prose_copied_from_paper: bool = False
    project_id: str
    propositions: tuple[MethodPropositionGoldV1, ...]

    @model_validator(mode="after")
    def _non_authorizing(self) -> "MethodPropositionFunnelFixtureV1":
        if self.authority != "diagnostic_non_authorizing":
            raise ValueError("funnel fixture must be diagnostic and non-authorizing")
        if self.prose_copied_from_paper:
            raise ValueError("funnel fixture must not copy original paper prose")
        return self


class MethodPropositionFunnelRowV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposition_id: str
    importance: ImportanceV1
    stage1: bool
    available: bool
    found: bool
    compiled: bool
    bound_correct_h2: bool
    delivered: bool
    used: bool
    realization: RealizationV1
    missing_alias_groups: tuple[tuple[str, ...], ...] = ()


class MethodPropositionFunnelReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    fixture_authority: str = "diagnostic_non_authorizing"
    rows: tuple[MethodPropositionFunnelRowV1, ...]
    counts: dict[str, int] = Field(default_factory=dict)
    weighted_coverage: float = 0.0
    mean_realization_used: float = 0.0
    stage1_ids: tuple[str, ...] = ()


class MethodPropositionBaselineV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    condition: str
    funnel_counts: dict[str, int]
    stage1_used: int
    stage1_total: int
    stage1_mean_realization: float
    notes: str = ""


def load_method_proposition_funnel_fixture(
    path: str | Path,
) -> MethodPropositionFunnelFixtureV1:
    return MethodPropositionFunnelFixtureV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def load_method_proposition_baselines(
    path: str | Path,
) -> tuple[MethodPropositionBaselineV1, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(
        MethodPropositionBaselineV1.model_validate(item)
        for item in raw.get("baselines", ())
    )


def _haystack_tokens(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, (int, float, bool)):
        return str(value).casefold()
    if isinstance(value, dict):
        return " ".join(_haystack_tokens(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_haystack_tokens(item) for item in value)
    return str(value).casefold()


def _contains_alias(haystack: str, alias: str) -> bool:
    needle = " ".join(str(alias or "").casefold().split())
    if not needle:
        return False
    return needle in haystack


def _groups_covered(
    haystack: str,
    groups: tuple[tuple[str, ...], ...],
) -> tuple[bool, tuple[tuple[str, ...], ...]]:
    missing: list[tuple[str, ...]] = []
    for group in groups:
        if not any(_contains_alias(haystack, alias) for alias in group):
            missing.append(group)
    return not missing, tuple(missing)


def heading_role(heading: str) -> str:
    text = str(heading or "").casefold()
    if "motivation" in text or "shortcoming" in text:
        return "motivation"
    if "overview" in text or "philosophy" in text:
        return "overview"
    if "offline" in text or "construction" in text:
        return "offline"
    if (
        "first retrieval" in text
        or "entity activation" in text
        or "semantic bridging" in text
    ):
        return "first_retrieval"
    if "second retrieval" in text or "pagerank" in text or "global importance" in text:
        return "second_retrieval"
    return "other"


def evaluate_method_proposition_funnel(
    *,
    fixture: MethodPropositionFunnelFixtureV1,
    yaml_or_code_text: str = "",
    claims: Any = None,
    plan_sections: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    writer_sections: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    realization_by_id: dict[str, int] | None = None,
) -> MethodPropositionFunnelReportV1:
    """Score propositions through available → used.

    ``realization_by_id`` records a frozen 0–4 score.  When omitted, used
    items receive heuristic 2 (identifier dump) vs 3 (alias fusion in prose).
    """

    yaml_hay = _haystack_tokens(yaml_or_code_text)
    claim_items = list(getattr(claims, "claims", claims) or [])
    claim_hay = _haystack_tokens([
        getattr(claim, "canonical_text", None)
        or (claim.get("canonical_text") if isinstance(claim, dict) else "")
        for claim in claim_items
    ])
    section_hays: list[tuple[str, str]] = []
    for section in plan_sections:
        heading = str(section.get("heading") or "")
        claim_ids = set(section.get("claim_ids") or ())
        bound_text = " ".join(
            str(
                getattr(claim, "canonical_text", "")
                or (claim.get("canonical_text") if isinstance(claim, dict) else "")
            )
            for claim in claim_items
            if (
                getattr(claim, "claim_id", None)
                or (claim.get("claim_id") if isinstance(claim, dict) else "")
            )
            in claim_ids
        )
        section_hays.append((heading_role(heading), _haystack_tokens(bound_text)))
    writer_by_role: dict[str, str] = {}
    full_writer = ""
    for section in writer_sections:
        heading = str(section.get("heading") or section.get("heading_text") or "")
        markdown = str(section.get("markdown") or section.get("section_markdown") or "")
        role = heading_role(heading)
        writer_by_role[role] = writer_by_role.get(role, "") + " " + markdown.casefold()
        full_writer += " " + markdown.casefold()
    rows: list[MethodPropositionFunnelRowV1] = []
    for item in fixture.propositions:
        if yaml_or_code_text.strip():
            available, _ = _groups_covered(yaml_hay, item.required_alias_groups)
        else:
            available = True
        compiled, _ = _groups_covered(claim_hay, item.required_alias_groups)
        found = compiled or (
            _groups_covered(yaml_hay + " " + claim_hay, item.required_alias_groups)[0]
            if yaml_or_code_text.strip()
            else compiled
        )
        bound = False
        for role, bound_text in section_hays:
            ok, _missing = _groups_covered(bound_text, item.required_alias_groups)
            if ok and role == item.expected_h2:
                bound = True
        writer_role = writer_by_role.get(item.expected_h2, "")
        used_correct, missing = _groups_covered(writer_role, item.required_alias_groups)
        used_anywhere, _ = _groups_covered(full_writer, item.required_alias_groups)
        used = used_correct
        if realization_by_id is not None and item.proposition_id in realization_by_id:
            realization = int(realization_by_id[item.proposition_id])
        elif used_correct:
            realization = 3 if any(
                token in writer_role for token in ("bridge", "propagat", "prun")
            ) else 2
        else:
            realization = 1 if used_anywhere else 0
        realization = max(0, min(4, realization))
        rows.append(MethodPropositionFunnelRowV1(
            proposition_id=item.proposition_id,
            importance=item.importance,
            stage1=item.stage1,
            available=available,
            found=found or compiled,
            compiled=compiled,
            bound_correct_h2=bound,
            delivered=bound,
            used=used,
            realization=realization,  # type: ignore[arg-type]
            missing_alias_groups=missing,
        ))
    counts = {
        "available": sum(row.available for row in rows),
        "found": sum(row.found for row in rows),
        "compiled": sum(row.compiled for row in rows),
        "bound_correct_h2": sum(row.bound_correct_h2 for row in rows),
        "delivered": sum(row.delivered for row in rows),
        "used": sum(row.used for row in rows),
        "total": len(rows),
    }
    weights = [_IMPORTANCE_WEIGHT[row.importance] for row in rows]
    covered = [
        _IMPORTANCE_WEIGHT[row.importance] * (1.0 if row.used else 0.0)
        for row in rows
    ]
    used_rows = [row for row in rows if row.used]
    return MethodPropositionFunnelReportV1(
        project_id=fixture.project_id,
        rows=tuple(rows),
        counts=counts,
        weighted_coverage=(sum(covered) / sum(weights)) if weights else 0.0,
        mean_realization_used=(
            sum(row.realization for row in used_rows) / len(used_rows)
            if used_rows else 0.0
        ),
        stage1_ids=tuple(row.proposition_id for row in rows if row.stage1),
    )
