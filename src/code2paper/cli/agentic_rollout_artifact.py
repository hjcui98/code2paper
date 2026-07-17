from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2
from code2paper.agentic.rollout_evidence import materialize_rollout_trial, validate_rollout_artifacts
from code2paper.agentic.tool_runtime import atomic_write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-agentic-rollout-artifact")
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--stage", choices=("shadow", "opt_in", "canary"), required=True)
    materialize.add_argument("--case", required=True)
    materialize.add_argument("--authorization-decision", required=True)
    materialize.add_argument("--agentic-run-summary", required=True)
    materialize.add_argument("--legacy-run-summary", default="")
    materialize.add_argument("--protocol", required=True)
    materialize.add_argument("--out", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--artifact", action="append", required=True)
    validate.add_argument("--gold", required=True)
    validate.add_argument("--protocol", required=True)
    validate.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    protocol = load_benchmark_protocol_v2(args.protocol)
    if args.command == "materialize":
        output = materialize_rollout_trial(
            stage=args.stage,
            case_id=args.case,
            authorization_decision_path=args.authorization_decision,
            agentic_run_summary_path=args.agentic_run_summary,
            legacy_run_summary_path=args.legacy_run_summary or None,
            out_path=args.out,
            protocol_commit=protocol.workspace_commit,
            gold_digest=protocol.gold_digest,
        )
        print(json.dumps({"artifact": str(output), "status": "human_review_required"}, indent=2))
        return 0
    dataset = load_benchmark_dataset_v2(args.gold)
    evidence = validate_rollout_artifacts(
        args.artifact,
        expected_case_ids={item.case_id for item in dataset.cases},
        protocol_commit=protocol.workspace_commit,
        gold_digest=protocol.gold_digest,
    )
    output = Path(args.out).expanduser().resolve()
    atomic_write_json(output, evidence)
    print(json.dumps({
        "evidence": str(output),
        "shadow_cases": len(evidence.shadow_case_ids),
        "opt_in_cases": len(evidence.opt_in_case_ids),
        "canary_cases": len(evidence.canary_case_ids),
        "canary_incidents": evidence.canary_incidents,
    }, indent=2))
    return 0
