from __future__ import annotations

import argparse
import json

from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2, validate_gold_evidence
from code2paper.agentic.legacy_v2_audit import audit_legacy_run_against_gold_v2, write_legacy_v2_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-agentic-legacy-v2-audit")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--legacy-out-root", required=True)
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    dataset = load_benchmark_dataset_v2(args.gold)
    failures = validate_gold_evidence(dataset, args.workspace_root)
    if failures:
        parser.error(failures[0])
    try:
        case = next(item for item in dataset.cases if item.case_id == args.case)
    except StopIteration:
        parser.error(f"unknown case:{args.case}")
    report = audit_legacy_run_against_gold_v2(
        case, workspace_root=args.workspace_root, legacy_out_root=args.legacy_out_root,
        scratch_root=args.scratch_root,
    )
    output = write_legacy_v2_audit(args.out, report)
    print(json.dumps({"report": str(output), **report.model_dump(mode="json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
