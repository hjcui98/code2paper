#!/usr/bin/env python3
"""Audit D2.5 reference coverage, configuration, equation, and section artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.evidence_compiler_v3 import GENERIC_RESEARCH_PRODUCER_VERSION
from code2paper.agentic.method_argument_models import REFERENCE_METHOD_STATUSES
from code2paper.agentic.tool_runtime import atomic_write_json


PROJECTS = ("rap", "ebcar", "dyg", "linearrag")


def _load(root: Path, *names: str) -> dict[str, Any] | None:
    for name in names:
        path = root / name
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def evaluate(base: Path) -> dict[str, Any]:
    project_reports: dict[str, Any] = {}
    all_equation_count = 0
    all_configuration_states: set[str] = set()
    for project in PROJECTS:
        root = base / f"code2paper-d1-{project}-static-current-20260802" / "artifacts"
        facts = _load(root, "code_facts_v1_v3.json", "code_facts_v1.json")
        equations = _load(root, "equation_claims_v1_v3.json", "equation_claims_v1.json")
        configurations = _load(root, "configuration_claims_v1.json")
        matrix = _load(root, "method_completeness_matrix_v1.json")
        section_plan = _load(root, "method_section_plan_v2.json")
        project_invariants = {
            "generic_fact_producer": bool(
                facts and facts.get("producer_version") == GENERIC_RESEARCH_PRODUCER_VERSION
            ),
            "equation_artifact_nonempty": bool(equations and equations.get("equations")),
            "equation_binds_fact_digest": bool(
                facts and equations
                and equations.get("code_fact_digest") == facts.get("content_digest")
            ),
            "configuration_artifact_present": configurations is not None,
            "completeness_uses_all_known_statuses": bool(
                matrix
                and matrix.get("items")
                and all(item.get("status") in REFERENCE_METHOD_STATUSES for item in matrix["items"])
                and all(
                    item.get("next_action")
                    for item in matrix["items"]
                    if item.get("status") not in {
                        "supported_by_repository",
                        "partially_supported_by_repository",
                    }
                )
            ),
            "section_plan_projects_argument_units": bool(
                section_plan and section_plan.get("argument_units")
            ),
        }
        equation_count = len((equations or {}).get("equations", []))
        states = {str(item.get("state")) for item in (configurations or {}).get("claims", [])}
        all_equation_count += equation_count
        all_configuration_states.update(states)
        project_reports[project] = {
            "root": str(root),
            "status": "passed" if all(project_invariants.values()) else "failed",
            "equation_count": equation_count,
            "configuration_states": sorted(states),
            "completeness_statuses": sorted(
                {item.get("status") for item in (matrix or {}).get("items", [])}
            ),
            "invariants": project_invariants,
        }
    invariants = {
        "all_projects_present": len(project_reports) == len(PROJECTS),
        "all_projects_pass": all(item["status"] == "passed" for item in project_reports.values()),
        "equations_not_all_zero": all_equation_count > 0,
        "configuration_branch_states_observed": {
            "actual", "default", "conditional"
        }.issubset(all_configuration_states),
        "section_and_completeness_chain_present": all(
            item["invariants"]["completeness_uses_all_known_statuses"]
            and item["invariants"]["section_plan_projects_argument_units"]
            for item in project_reports.values()
        ),
    }
    return {
        "schema_version": "d25_method_research_acceptance_v1",
        "status": "passed" if all(invariants.values()) else "failed",
        "base": str(base),
        "projects": project_reports,
        "aggregate": {
            "equation_count": all_equation_count,
            "configuration_states": sorted(all_configuration_states),
        },
        "invariants": invariants,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, default=Path("/tmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.base.resolve())
    atomic_write_json(args.output, report)
    if report["status"] != "passed":
        raise SystemExit(1)
    print(report["status"])


if __name__ == "__main__":
    main()
