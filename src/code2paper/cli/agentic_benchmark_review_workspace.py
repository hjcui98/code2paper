from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2
from code2paper.agentic.benchmark_review_workspace import (
    materialize_review_workspace,
    validate_review_workspace,
)
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2
from code2paper.agentic.tool_runtime import atomic_write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark-review-workspace",
        description="Materialize or validate digest-pinned named-human P4 review files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize", help="Create one non-overwriting review file per queue entry.")
    materialize.add_argument("--queue", required=True)
    materialize.add_argument("--out-root", required=True)
    validate = subparsers.add_parser("validate", help="Validate exact review coverage and artifact bindings.")
    validate.add_argument("--queue", required=True)
    validate.add_argument("--workspace", required=True)
    validate.add_argument("--gold", required=True)
    validate.add_argument("--protocol", required=True)
    validate.add_argument("--report-out", required=True)
    validate.add_argument("--observations-out", default="")
    args = parser.parse_args(argv)
    if args.command == "materialize":
        manifest = materialize_review_workspace(args.queue, args.out_root)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        print(json.dumps({
            "workspace_manifest": str(manifest),
            "expected_reviews": payload["expected_reviews"],
            "status": payload["status"],
        }, ensure_ascii=False, indent=2))
        return 0
    report, observations = validate_review_workspace(
        args.queue,
        args.workspace,
        load_benchmark_dataset_v2(args.gold),
        load_benchmark_protocol_v2(args.protocol),
    )
    atomic_write_json(args.report_out, report)
    if report["hard_gate_passed"] and args.observations_out:
        atomic_write_json(args.observations_out, [item.model_dump(mode="json") for item in observations])
    print(json.dumps({
        "report": str(Path(args.report_out).resolve()),
        "status": report["status"],
        "validated": report["validated_review_count"],
        "pending": report["pending_review_count"],
        "invalid": report["invalid_review_count"],
        "observations_emitted": report["observations_emitted"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["hard_gate_passed"] else (1 if report["status"] == "pending_human_review" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
