#!/usr/bin/env python3
"""Compare one Candidate Method to an offline original-paper oracle.

The original paper is read only for evaluation.  Its text never enters the
Code2Paper generation path or any evidence artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from code2paper.agentic.method_content_regression import (
    evaluate_method_authoring_oracle,
    load_method_authoring_oracle,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_id", choices=("linearrag", "dyg", "ebcar"))
    parser.add_argument("candidate", type=Path, help="Candidate Method markdown")
    parser.add_argument("original", type=Path, help="offline original Method markdown")
    parser.add_argument(
        "--oracle",
        type=Path,
        default=ROOT / "tests/fixtures/method_synthesis_funnel/original_oracle_v1.json",
    )
    args = parser.parse_args(argv)
    oracle = load_method_authoring_oracle(args.oracle)
    report = evaluate_method_authoring_oracle(
        oracle=oracle,
        project_id=args.project_id,
        candidate_text=args.candidate.read_text(encoding="utf-8"),
        original_text=args.original.read_text(encoding="utf-8"),
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
