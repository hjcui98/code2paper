#!/usr/bin/env python3
"""Force Phase4 authoring without preflight blocking from phase2/phase3 modes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.llm.providers import load_llm_config_from_env
from code2paper.phase4_authoring import write_phase4_artifacts
from code2paper.schemas import ClaimEvidenceMap, CodeAlignmentIR, MethodEvidence


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="force-phase4-author")
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--llm-provider", default=None)
    parser.add_argument("--llm-model", default=None)
    return parser.parse_args()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _parse_args()
    out_root = Path(args.out_root).resolve()
    method_root = out_root / "paper" / "method"

    method_evidence = MethodEvidence.model_validate(_read_json(method_root / "method_evidence.json"))
    claim_map = ClaimEvidenceMap.model_validate(_read_json(out_root / "paper" / "claim_evidence_map.json"))
    alignment = None
    alignment_path = method_root / "code_alignment_ir.json"
    if alignment_path.exists():
        alignment = CodeAlignmentIR.model_validate(_read_json(alignment_path))

    llm_config = load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model)
    markdown, tex, paths = write_phase4_artifacts(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
        alignment=alignment,
        preflight_blocked_reason="",
    )
    _ = (markdown, tex)
    print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
