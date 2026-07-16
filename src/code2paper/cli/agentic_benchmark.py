"""Aggregate agentic run evaluation reports for benchmark comparison."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from code2paper.agentic.benchmark_report import (
    AgenticBenchmarkRunSpec,
    build_agentic_benchmark_report,
    write_agentic_benchmark_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark",
        description="Aggregate agentic_run_evaluation_report.json files into a benchmark report.",
    )
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        metavar="[variant=][label=]PATH",
        help="Evaluation report path. Optional prefixes set variant and label.",
    )
    parser.add_argument("reports", nargs="*", help="Evaluation report paths using variant=agentic and path stem labels.")
    parser.add_argument("--out", required=True, help="Output path for agentic_benchmark_report.json")
    args = parser.parse_args(argv)

    specs = [_parse_run_spec(raw) for raw in args.run]
    specs.extend(
        AgenticBenchmarkRunSpec(path=str(Path(path).expanduser().resolve()), variant="agentic", label=Path(path).stem)
        for path in args.reports
    )
    if not specs:
        parser.error("at least one --run or positional report path is required")
    missing_reports = [spec.path for spec in specs if not Path(spec.path).exists()]
    if missing_reports:
        print(f"[code2paper-agentic-benchmark] error=report_not_found:{missing_reports[0]}", file=sys.stderr)
        return 2
    report = build_agentic_benchmark_report(specs)
    output = write_agentic_benchmark_report(args.out, report)
    print(f"[code2paper-agentic-benchmark] report={output}")
    print(
        json.dumps(
            {
                "run_count": report.run_count,
                "variants": report.variants,
                "best_variant": report.best_variant,
                "recommended_actions": report.recommended_actions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _parse_run_spec(raw: str) -> AgenticBenchmarkRunSpec:
    parts = raw.split("=", 2)
    if len(parts) == 1:
        path = Path(parts[0]).expanduser().resolve()
        return AgenticBenchmarkRunSpec(path=str(path), variant="agentic", label=path.stem)
    if len(parts) == 2:
        variant, path_text = parts
        path = Path(path_text).expanduser().resolve()
        return AgenticBenchmarkRunSpec(path=str(path), variant=variant or "agentic", label=path.stem)
    variant, label, path_text = parts
    path = Path(path_text).expanduser().resolve()
    return AgenticBenchmarkRunSpec(path=str(path), variant=variant or "agentic", label=label or path.stem)


if __name__ == "__main__":
    raise SystemExit(main())
