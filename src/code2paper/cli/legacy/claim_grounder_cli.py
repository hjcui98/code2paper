"""CLI for claim-evidence map generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.evidence.claim_grounder import build_claim_evidence_map_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-claim-ground")
    parser.add_argument("method_evidence_path")
    parser.add_argument("--alignment")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    claim_map = build_claim_evidence_map_from_files(args.method_evidence_path, args.alignment)
    payload = claim_map.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
