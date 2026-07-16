"""CLI for author confirmation question generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from code2paper.authoring.review import build_author_review_questions_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-author-review")
    parser.add_argument("raw_evidence_path")
    parser.add_argument("alignment_path")
    parser.add_argument("method_evidence_path")
    parser.add_argument("--claim-map")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    markdown = build_author_review_questions_from_files(
        raw_evidence_path=args.raw_evidence_path,
        alignment_path=args.alignment_path,
        method_evidence_path=args.method_evidence_path,
        claim_map_path=args.claim_map,
    )
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
