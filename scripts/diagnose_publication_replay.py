#!/usr/bin/env python3
"""Print read-only publication replay diagnostics as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from code2paper.agentic.publication_replay_diagnostics import diagnose_publication_replay


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs="+", help="Fresh or frozen Code2Paper run roots")
    arguments = parser.parse_args()
    payload = [diagnose_publication_replay(root) for root in arguments.roots]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
