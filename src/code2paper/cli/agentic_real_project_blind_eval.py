from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.real_project_blind_eval import evaluate_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare code+intent Method generations with evaluation-only originals."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_manifest(
        args.manifest, data_root=args.data_root, runs_root=args.runs_root
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["reference_isolation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
