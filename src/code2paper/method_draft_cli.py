"""CLI for Phase 4 method draft writing."""

from __future__ import annotations

import argparse
from pathlib import Path

from .writing.method_writer import build_method_draft_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-method-draft")
    parser.add_argument("method_evidence_path")
    parser.add_argument("--claim-map")
    parser.add_argument("--out-md")
    parser.add_argument("--out-tex")
    args = parser.parse_args(argv)

    markdown, tex = build_method_draft_from_files(args.method_evidence_path, claim_map_path=args.claim_map)
    if args.out_md:
        Path(args.out_md).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    if args.out_tex:
        Path(args.out_tex).write_text(tex, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
