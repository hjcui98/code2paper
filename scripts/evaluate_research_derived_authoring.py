#!/usr/bin/env python3
"""Read-only evaluator for a Research-Derived Method authoring replay.

The evaluator reports structural coverage and authority separation.  It never
uses a baseline paragraph as a string oracle and never writes into the replay
root.  An optional JSON manifest may describe semantic expectations such as
required mechanism categories, required surface modes, and forbidden
conclusions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from code2paper.agentic.publication_replay_diagnostics import (  # noqa: E402
    _artifact_path,
    _candidate_sentence_count,
    diagnose_publication_replay,
)


def _read_manifest(path: str | Path | None) -> Mapping[str, Any]:
    if not path:
        return {}
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("test manifest must contain a JSON object")
    return payload


def _ratio(rendered: int, planned: int) -> float:
    if planned <= 0:
        return 1.0
    return round(rendered / planned, 6)


def _candidate_text(root: str | Path) -> str:
    path = _artifact_path(root, "publication_candidate_method")
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _contains_any(text: str, values: Any) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    try:
        return tuple(
            str(value)
            for value in values
            if str(value) and str(value).casefold() in text.casefold()
        )
    except TypeError:
        return ()


def _manifest_expectations(
    *,
    report: Mapping[str, Any],
    candidate_text: str,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare only semantic manifest fields, never expected prose strings."""

    failures: list[str] = []
    observations = report.get("authoring_observations") or {}
    surface_modes = report.get("candidate_surface", {}).get("sentences_by_surface_mode", {})
    derivation_kinds = report.get("derivation_records_by_kind") or {}

    for mode in manifest.get("required_surface_modes") or ():
        if int(surface_modes.get(str(mode), 0)) <= 0:
            failures.append(f"required_surface_mode_missing:{mode}")
    for kind in manifest.get("required_derivation_kinds") or ():
        if int(derivation_kinds.get(str(kind), 0)) <= 0:
            failures.append(f"required_derivation_kind_missing:{kind}")
    for category in manifest.get("mechanism_categories") or ():
        if not _contains_any(candidate_text, (category,)):
            failures.append(f"mechanism_category_not_observed:{category}")
    for term in manifest.get("required_difference_terms") or ():
        if not _contains_any(candidate_text, (term,)):
            failures.append(f"required_difference_not_observed:{term}")
    for conclusion in manifest.get("forbidden_conclusions") or ():
        if _contains_any(candidate_text, (conclusion,)):
            failures.append(f"forbidden_conclusion_present:{conclusion}")
    expected_observations = manifest.get("required_observations") or {}
    if isinstance(expected_observations, Mapping):
        for key, expected in expected_observations.items():
            observed = observations.get(str(key))
            if observed != expected:
                failures.append(
                    f"observation_mismatch:{key}:expected={expected!r}:observed={observed!r}"
                )
    return {
        "provided": bool(manifest),
        "passed": not failures,
        "failures": failures,
    }


def evaluate_research_derived_authoring(
    root: str | Path,
    *,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one fresh/frozen replay without modifying its artifacts."""

    report = diagnose_publication_replay(root)
    summary = report.get("content_chain", {}).get("summary") or {}
    candidate_text = _candidate_text(root)
    coverage = {
        "story": {
            "planned": int(summary.get("planned_story_nodes") or 0),
            "rendered": int(summary.get("rendered_story_nodes") or 0),
        },
        "paragraph": {
            "planned": int(summary.get("planned_paragraphs") or 0),
            "rendered": int(summary.get("rendered_paragraphs") or 0),
        },
        "slot": {
            "planned": int(summary.get("planned_slots") or 0),
            "rendered": int(summary.get("rendered_slots") or 0),
        },
        "edge": {
            "planned": int(summary.get("planned_edges") or 0),
            "rendered": int(summary.get("rendered_edges") or 0),
        },
        "formula": {
            "planned": int(summary.get("formula_obligations") or 0),
            "rendered": int(summary.get("rendered_formula_obligations") or 0),
            "accepted_packages": int(report.get("accepted_formula_packages") or 0),
            "consumed_packages": int(report.get("consumed_formula_packages") or 0),
        },
    }
    for item in coverage.values():
        item["recall"] = _ratio(int(item["rendered"]), int(item["planned"]))
    formula = report.get("formula") or {}
    candidate_surface = report.get("candidate_surface") or {}
    verified = report.get("verified_leakage") or {}
    result = {
        "schema_version": "1.0",
        "run_root": report.get("run_root"),
        "coverage": coverage,
        "formula_renderability": {
            "accepted_packages": int(formula.get("accepted_packages") or 0),
            "consumed_packages": int(formula.get("consumed_packages") or 0),
            "renderable_packages": int(formula.get("renderable_packages") or 0),
            "unrenderable_packages": int(formula.get("unrenderable_packages") or 0),
            "route_ambiguous_packages": int(report.get("formula_route_ambiguous_packages") or 0),
        },
        "candidate_surface_cleanliness": {
            "sentence_count": _candidate_sentence_count(candidate_text)
            if candidate_text else 0,
            "internal_audit_term_count": int(
                candidate_surface.get("internal_audit_term_count") or 0
            ),
            "sentences_by_surface_mode": dict(
                candidate_surface.get("sentences_by_surface_mode") or {}
            ),
            "authority_status": candidate_surface.get("authority_status", "not_run"),
            "violations": list(candidate_surface.get("violations") or ()),
        },
        "candidate_authority_validation": {
            "status": candidate_surface.get("authority_status", "not_run"),
            "violations": list(candidate_surface.get("violations") or ()),
            "warnings": list(candidate_surface.get("warnings") or ()),
        },
        "verified_leakage": {
            "count": int(verified.get("count") or 0),
            "passed": int(verified.get("count") or 0) == 0,
        },
        "observations": report.get("authoring_observations") or {},
        "manifest": _manifest_expectations(
            report=report,
            candidate_text=candidate_text,
            manifest=manifest or {},
        ),
    }
    result["passed"] = bool(
        result["manifest"]["passed"]
        and result["candidate_surface_cleanliness"]["internal_audit_term_count"] == 0
        and result["verified_leakage"]["passed"]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Fresh or frozen Code2Paper run root")
    parser.add_argument(
        "--manifest",
        help="Optional JSON semantic expectation manifest; it must not contain baseline prose answers",
    )
    arguments = parser.parse_args()
    result = evaluate_research_derived_authoring(
        arguments.root,
        manifest=_read_manifest(arguments.manifest),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
