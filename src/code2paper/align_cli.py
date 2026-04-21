"""CLI for Phase 2 code alignment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .alignment import align_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-align")
    parser.add_argument("raw_evidence_path")
    parser.add_argument("--author", dest="author_markers_path")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    alignment = align_from_files(args.raw_evidence_path, author_markers_path=args.author_markers_path)
    payload = alignment.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

