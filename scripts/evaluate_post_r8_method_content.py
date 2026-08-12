#!/usr/bin/env python3
"""Evaluate one completed run against the frozen D2.5 content fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.method_content_regression import (
    evaluate_method_content_artifacts,
    load_method_content_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", choices=("rap", "ebcar", "dyg", "linearrag"))
    parser.add_argument("run_root", type=Path)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/post_r8_method_content_regression_v1.json"),
    )
    args = parser.parse_args()
    keys = {
        "facts": (
            "artifacts/04_evidence/code_facts_v1.json",
            "artifacts/code_facts_v1_v3.json",
        ),
        "claims": (
            "artifacts/04_evidence/atomic_claims_v3.json",
            "artifacts/atomic_claims_v3_v3.json",
        ),
        "equations": (
            "artifacts/05_grounding/equation_claims_v1.json",
            "artifacts/equation_claims_v1_v3.json",
        ),
        "configurations": ("artifacts/configuration_claims_v1.json",),
        "sections": ("artifacts/method_section_plan_v2.json",),
        "publication": ("artifacts/06_authoring/publication_writer_result_v1.json",),
        "inventory": ("artifacts/repository_behavior_inventory_v1.json",),
    }
    artifacts = {}
    for key, candidates in keys.items():
        for relative in candidates:
            path = args.run_root / relative
            if path.is_file():
                artifacts[key] = json.loads(path.read_text(encoding="utf-8"))
                break
    report = evaluate_method_content_artifacts(
        fixture=load_method_content_fixture(args.fixture),
        project_id=args.project_id,
        artifacts=artifacts,
    )
    output = args.run_root / "artifacts" / "10_run" / "method_content_regression_v1.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(report.model_dump_json(indent=2))
    return 0 if report.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
