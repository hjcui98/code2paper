"""CLI for Phase 3 method evidence building."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .llm.providers import load_llm_config_from_env
from .method_evidence import build_method_evidence_from_files, write_phase3_artifacts
from .schemas import CodeAlignmentIR, CodeMethodAnalysis, LLMProvider, RawEvidencePack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-method-evidence")
    parser.add_argument("raw_evidence_path")
    parser.add_argument("alignment_path")
    parser.add_argument("--code-method-analysis")
    parser.add_argument("--code-facts")
    parser.add_argument("--out-root")
    parser.add_argument("--out")
    parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    parser.add_argument("--llm-model", default=None)
    args = parser.parse_args(argv)

    if args.out_root:
        raw_pack = RawEvidencePack.model_validate(json.loads(Path(args.raw_evidence_path).read_text(encoding="utf-8")))
        alignment = CodeAlignmentIR.model_validate(json.loads(Path(args.alignment_path).read_text(encoding="utf-8")))
        analysis = None
        if args.code_method_analysis:
            analysis = CodeMethodAnalysis.model_validate(
                json.loads(Path(args.code_method_analysis).read_text(encoding="utf-8"))
            )
        code_facts = json.loads(Path(args.code_facts).read_text(encoding="utf-8")) if args.code_facts else None
        out_root = Path(args.out_root)
        method_evidence, paths = write_phase3_artifacts(
            method_root=out_root / "paper" / "method",
            paper_root=out_root / "paper",
            raw_pack=raw_pack,
            alignment=alignment,
            code_method_analysis=analysis,
            code_facts=code_facts,
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
        )
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    method_evidence = build_method_evidence_from_files(
        args.raw_evidence_path,
        args.alignment_path,
        code_method_analysis_path=args.code_method_analysis,
    )
    payload = method_evidence.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
