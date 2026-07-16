from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from code2paper.agentic.benchmark_protocol import build_benchmark_protocol_v2, write_benchmark_protocol_v2
from code2paper.agentic.benchmark_v2 import load_benchmark_dataset_v2, validate_gold_evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark-protocol",
        description="Freeze the P4 fixed/agentic/Gemma repeat matrix before running it.",
    )
    parser.add_argument("--gold", required=True)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument(
        "--code-root", default="",
        help="Clean tracked worktree containing the benchmark implementation; defaults to workspace root.",
    )
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--author", action="append", default=[], required=True, metavar="CASE[:INTENT]=PATH",
        help="Author marker mapping; repeat for every case/intent.",
    )
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--capability-profile-digest", required=True)
    args = parser.parse_args(argv)
    dataset = load_benchmark_dataset_v2(args.gold)
    failures = validate_gold_evidence(dataset, args.workspace_root)
    if failures:
        parser.error(failures[0])
    authors = _parse_authors(args.author)
    code_root = Path(args.code_root or args.workspace_root).resolve()
    commit = subprocess.run(
        ["git", "-C", str(code_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(code_root), "status", "--porcelain", "--untracked-files=no"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if dirty:
        parser.error("--code-root has tracked changes; formal P4 protocols require a clean commit")
    protocol = build_benchmark_protocol_v2(
        dataset,
        workspace_root=args.workspace_root,
        code_root=code_root,
        out_root=args.out_root,
        author_markers=authors,
        workspace_commit=commit,
        model_id=args.model_id,
        capability_profile_digest=args.capability_profile_digest,
    )
    output = write_benchmark_protocol_v2(args.out, protocol)
    print(json.dumps({
        "protocol": str(output), "run_count": len(protocol.specs),
        "workspace_commit": protocol.workspace_commit, "gold_digest": protocol.gold_digest,
    }, indent=2))
    return 0


def _parse_authors(values: list[str]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"invalid --author mapping:{value}")
        identity, path = value.split("=", 1)
        case_id, separator, intent_id = identity.partition(":")
        key = (case_id, intent_id if separator else "")
        if key in result:
            raise ValueError(f"duplicate --author mapping:{identity}")
        result[key] = path
    return result


if __name__ == "__main__":
    raise SystemExit(main())
