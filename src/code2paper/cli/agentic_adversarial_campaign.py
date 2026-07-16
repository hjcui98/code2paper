from __future__ import annotations

import argparse
import hashlib
import json

from code2paper.agentic.adversarial_campaign import run_adversarial_campaign_v2
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2, validate_gold_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-agentic-adversarial-campaign")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--out-root", required=True)
    args = parser.parse_args(argv)
    dataset = load_benchmark_dataset_v2(args.gold)
    failures = validate_gold_evidence(dataset, args.workspace_root)
    if failures:
        parser.error(failures[0])
    try:
        case = next(item for item in dataset.cases if item.case_id == args.case)
    except StopIteration:
        parser.error(f"unknown case:{args.case}")
    paths = run_adversarial_campaign_v2(case, workspace_root=args.workspace_root, out_root=args.out_root)
    payload = [{
        "path": str(path), "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "detected": json.loads(path.read_text(encoding="utf-8"))["detected"],
    } for path in paths]
    print(json.dumps(payload, indent=2))
    return 0 if all(item["detected"] for item in payload) else 1


if __name__ == "__main__":
    raise SystemExit(main())
