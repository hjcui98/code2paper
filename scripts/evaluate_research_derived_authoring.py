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


def _ratio(rendered: int, planned: int) -> float | None:
    if planned <= 0:
        return None
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
    formula_funnel = report.get("formula_funnel") or {}
    candidate_surface = report.get("candidate_surface") or {}
    verified = report.get("verified_leakage") or {}
    execution = report.get("execution") or {}
    structural_exit = report.get("structural_exit") or {}
    quality = report.get("quality") or {}
    artifact_presence = report.get("artifact_presence") or {}
    failure = report.get("failure") or {}

    # A replay is accepted only when the process, all required durable
    # products, the Writer transaction, the structural exit, quality gates,
    # and every planned coverage denominator agree.  Diagnostics remain useful
    # for failed/partial runs, but their cleanliness is not acceptance.
    common_required_artifact_keys = (
        "method_section_plan_v2",
        "formalization_section_results_v1",
        "publication_writer_result_v1",
        "publication_candidate_method",
        "repository_verified_method",
        "text_evidence_validation",
        "method_content_trace_v1",
        "publication_paragraph_transaction_assessments_v1",
        "publication_paragraph_checkpoint_v1",
        "authoring_structural_exit_v1",
        "research_mechanism_dossiers_v1",
        "derivation_records_v1",
        "candidate_authority_validation_v1",
        "publication_candidate_annotations_v1",
    )
    artifact_presence = report.get("artifact_presence") or {}
    if bool(artifact_presence.get("method_argument_briefs_v1")):
        authoring_route = "argument_briefs"
        route_required_artifact_keys = (
            "method_argument_briefs_v1",
            "method_argument_facets_v1",
            "facet_evidence_alignments_v1",
            "candidate_facet_policies_v1",
            "method_argument_facet_alignment_trace_v1",
        )
    elif bool(artifact_presence.get("method_propositions_v1")):
        authoring_route = "propositions"
        route_required_artifact_keys = (
            "method_propositions_v1",
            "method_proposition_alignment_v1",
        )
    else:
        authoring_route = "missing"
        # Keep the failure explicit while allowing the evaluator to report
        # which mutually exclusive Candidate authority lane is absent.
        route_required_artifact_keys = (
            "method_argument_briefs_v1|method_propositions_v1",
        )
    required_artifact_keys = (
        *common_required_artifact_keys,
        *route_required_artifact_keys,
    )
    missing_artifacts = [
        key for key in required_artifact_keys
        if not (
            bool(artifact_presence.get(key))
            or key == "method_argument_briefs_v1|method_propositions_v1"
            and (
                bool(artifact_presence.get("method_argument_briefs_v1"))
                or bool(artifact_presence.get("method_propositions_v1"))
            )
        )
    ]
    coverage_failures: list[str] = []
    for key, item in coverage.items():
        planned = int(item["planned"])
        rendered = int(item["rendered"])
        if planned <= 0:
            coverage_failures.append(f"coverage_not_run:{key}")
        elif rendered < planned:
            coverage_failures.append(
                f"coverage_below_threshold:{key}:{rendered}/{planned}"
            )
    formula_failures: list[str] = []
    formula_planned = int(coverage["formula"]["planned"])
    if formula_planned > 0:
        routed = int(formula_funnel.get("routed_obligations") or 0)
        accepted = int(formula.get("accepted_packages") or 0)
        consumed = int(formula.get("consumed_packages") or 0)
        exact = int(formula.get("exact_body_validated_packages") or 0)
        if routed < formula_planned:
            formula_failures.append(
                f"formula_routed_below_threshold:{routed}/{formula_planned}"
            )
        if accepted <= 0:
            formula_failures.append("formula_accepted_zero")
        if consumed != accepted:
            formula_failures.append(f"formula_consumed_mismatch:{consumed}/{accepted}")
        if exact != accepted:
            formula_failures.append(f"formula_exact_body_mismatch:{exact}/{accepted}")
    elif formula_planned <= 0:
        # The general coverage loop records the required not-run state; keep
        # this branch explicit so a future formula-only check cannot turn an
        # absent denominator into a pass.
        formula_failures.append("formula_coverage_not_run")

    execution_exit = execution.get("exit_code")
    execution_failures: list[str] = []
    if execution_exit != 0:
        execution_failures.append(
            "process_exit_code:" + (
                str(execution_exit) if execution_exit is not None else "missing"
            )
        )
    if missing_artifacts:
        execution_failures.append("required_artifacts_missing:" + ",".join(missing_artifacts))
    writer_status = str(execution.get("writer_status") or "")
    if writer_status != "success":
        execution_failures.append(
            "writer_not_complete:" + (writer_status or "missing")
        )
    if not bool(structural_exit.get("eligible")):
        reasons = ";".join(str(item) for item in structural_exit.get("reasons") or ())
        execution_failures.append(
            "structural_exit_not_eligible" + (":" + reasons if reasons else "")
        )
    quality_status = str(quality.get("status") or "not_run")
    if quality_status != "publication_ready":
        execution_failures.append("quality_not_ready:" + quality_status)
    if str(report.get("reverse_validation", {}).get("status") or "not_run") != "passed":
        execution_failures.append(
            "reverse_validation_not_passed:" + str(
                report.get("reverse_validation", {}).get("status") or "not_run"
            )
        )
    execution_failures.extend(coverage_failures)
    execution_failures.extend(formula_failures)
    if failure:
        failure_stage = str(failure.get("terminal_stage") or "replay")
        failure_code = str(failure.get("error_code") or "authoring_failure")
        failure_reason = str(failure.get("terminal_reason") or "")
        execution_failures.insert(
            0,
            ":".join(item for item in (failure_stage, failure_code, failure_reason) if item),
        )

    first_failed_stage = ""
    if failure:
        first_failed_stage = str(failure.get("terminal_stage") or "replay")
    elif execution_exit != 0 or execution_exit is None:
        first_failed_stage = "execution"
    elif missing_artifacts:
        first_failed_stage = "artifacts"
    elif writer_status != "success":
        first_failed_stage = "writer"
    elif not bool(structural_exit.get("eligible")):
        first_failed_stage = "structural_exit"
    elif quality_status != "publication_ready":
        first_failed_stage = "quality"
    elif coverage_failures or formula_failures:
        first_failed_stage = "coverage"

    manifest_result = _manifest_expectations(
        report=report,
        candidate_text=candidate_text,
        manifest=manifest or {},
    )
    diagnostic_cleanliness_passed = bool(
        manifest_result["passed"]
        and candidate_surface.get("authority_status") == "passed"
        and int(candidate_surface.get("internal_audit_term_count") or 0) == 0
        and not candidate_surface.get("violations")
        and int(verified.get("count") or 0) == 0
    )
    acceptance_passed = not execution_failures
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
        "execution": execution,
        "failure": failure or None,
        "required_artifacts": {
            "keys": list(required_artifact_keys),
            "missing": missing_artifacts,
            "passed": not missing_artifacts,
            "authoring_route": authoring_route,
        },
        "diagnostic_cleanliness_passed": diagnostic_cleanliness_passed,
        "acceptance_passed": acceptance_passed,
        "first_failed_stage": first_failed_stage or None,
        "failure_reasons": list(dict.fromkeys(execution_failures)),
        "observations": report.get("authoring_observations") or {},
        "manifest": manifest_result,
    }
    # Keep the historical key for callers, but make it the strict acceptance
    # verdict instead of the old diagnostic-only verdict.
    result["passed"] = acceptance_passed
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
