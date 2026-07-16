from __future__ import annotations

import argparse
import json

from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2
from code2paper.agentic.benchmark_review_queue import build_review_queue_v2, write_review_queue_v2
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-agentic-benchmark-review-queue")
    parser.add_argument("--gold", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--run-index", action="append", required=True)
    parser.add_argument("--mutation-root", action="append", required=True, metavar="CASE=PATH")
    parser.add_argument("--legacy-audit-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    roots = dict(item.split("=", 1) for item in args.mutation_root)
    queue = build_review_queue_v2(
        load_benchmark_dataset_v2(args.gold), load_benchmark_protocol_v2(args.protocol), args.run_index,
        mutation_roots=roots, legacy_audit_root=args.legacy_audit_root,
    )
    output = write_review_queue_v2(args.out, queue)
    print(json.dumps({"queue": str(output), "entries": queue["entry_count"], "ready_for_cutover": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
