"""CLI for method fidelity validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.validation.fidelity_validator import validate_method_fidelity_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-fidelity")
    parser.add_argument("raw_evidence_path")
    parser.add_argument("method_evidence_path")
    parser.add_argument("draft_markdown_path")
    parser.add_argument("--claim-map")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    report = validate_method_fidelity_from_files(
        raw_evidence_path=args.raw_evidence_path,
        method_evidence_path=args.method_evidence_path,
        draft_markdown_path=args.draft_markdown_path,
        claim_map_path=args.claim_map,
    )
    text = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
