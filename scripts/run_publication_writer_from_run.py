#!/usr/bin/env python3
"""Run only the Publication Method authoring stage from a frozen run.

The source run is copied to a fresh output root so the evidence snapshot remains
immutable.  Artifact references are rebound to the copy before invoking the
existing authoring stage.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.legacy_authoring_stage_tool import run_authoring


def _artifact_paths(summary: dict, source: Path, target: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for key, value in dict(summary.get("artifacts") or {}).items():
        raw = value.get("path", "") if isinstance(value, dict) else value
        if not raw:
            continue
        path = Path(str(raw))
        try:
            relative = path.relative_to(source)
        except ValueError:
            artifacts[str(key)] = str(path)
        else:
            artifacts[str(key)] = str(target / relative)
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run", type=Path)
    parser.add_argument("out_root", type=Path)
    parser.add_argument("--llm-provider", default=os.environ.get("CODE2PAPER_LLM_PROVIDER") or "openai")
    parser.add_argument("--llm-model", default=os.environ.get("CODE2PAPER_LLM_MODEL") or "")
    parser.add_argument("--editor", action="store_true")
    args = parser.parse_args()

    source = args.source_run.expanduser().resolve()
    target = args.out_root.expanduser().resolve()
    summary_path = source / "artifacts" / "10_run" / "agentic_run_summary.json"
    if not summary_path.is_file():
        parser.error(f"source run summary not found: {summary_path}")
    if target.exists():
        parser.error(f"output root already exists: {target}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    shutil.copytree(source, target)
    artifacts = _artifact_paths(summary, source, target)
    # These products are derived from the projection implementation.  Reusing
    # them after code changes would correctly trip the projection-digest gate,
    # so rebuild them from the frozen evidence instead.
    for stale_key in (
        "authoring_plan",
        "authoring_plan_decision_trace",
        "authoring_plan_v3",
        "authoring_projection",
    ):
        artifacts.pop(stale_key, None)
    state = AgenticRunState(
        project_root=Path(summary["project_root"]),
        out_root=target,
        project_id=source.name,
        run_id=f"{source.name}-publication-writer",
        llm_provider=args.llm_provider or None,
        llm_model=args.llm_model or None,
        artifacts=artifacts,
    )

    os.environ["CODE2PAPER_PUBLICATION_WRITER_V1"] = "1"
    os.environ["CODE2PAPER_PUBLICATION_EDITOR_V1"] = "1" if args.editor else "0"
    result = run_authoring(state)
    result_path = target / "artifacts" / "10_run" / "publication_writer_stage_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(f"status={result.status.value}")
    print(f"blocked_reason={result.blocked_reason}")
    print(f"summary={result.summary}")
    print(f"result={result_path}")
    for key in (
        "method_section_plan_v2",
        "formalization_result_v1",
        "publication_writer_result_v1",
        "final_text_authorship_ledger_v1",
        "repository_verified_method",
        "publication_candidate_method",
        "author_review_candidates",
    ):
        print(f"{key}={result.artifacts.get(key, '')}")
    return 0 if result.status.value == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
