"""CLI for Phase 5 method overview figure generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from code2paper.figures.backend_fallback import generate_fallback_figure
from code2paper.figures.backend_paperbanana import PaperBananaBackendError, generate_paperbanana_figure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper-figure")
    parser.add_argument("method_draft_path")
    parser.add_argument("--method-evidence")
    parser.add_argument("--claim-map")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--backend", choices=["paperbanana", "fallback"], default="paperbanana")
    parser.add_argument("--fallback-on-error", action="store_true")
    parser.add_argument("--paperbanana-root")
    parser.add_argument("--chat-api-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--image-model", default="")
    parser.add_argument("--graph-type", default="tech_route")
    parser.add_argument("--language", default="en")
    parser.add_argument("--style", default="academic")
    parser.add_argument("--figure-complex", default="easy")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--retrieval-setting", default="none", choices=["auto", "manual", "random", "none"])
    parser.add_argument("--exp-mode", default="demo_full", choices=["demo_full", "demo_planner_critic"])
    parser.add_argument("--aspect-ratio", default="16:9", choices=["21:9", "16:9", "3:2"])
    parser.add_argument("--max-critic-rounds", type=int, default=3)
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--clean-tex-to-txt", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.backend == "fallback":
            meta = generate_fallback_figure(
                args.method_draft_path,
                out_dir=args.out_dir,
                method_evidence_path=args.method_evidence,
                claim_map_path=args.claim_map,
            )
        else:
            meta = generate_paperbanana_figure(
                draft_path=args.method_draft_path,
                out_dir=args.out_dir,
                method_evidence_path=args.method_evidence,
                claim_map_path=args.claim_map,
                paperbanana_root=args.paperbanana_root,
                chat_api_url=args.chat_api_url,
                api_key=args.api_key,
                model=args.model,
                image_model=args.image_model,
                graph_type=args.graph_type,
                language=args.language,
                style=args.style,
                figure_complex=args.figure_complex,
                resolution=args.resolution,
                retrieval_setting=args.retrieval_setting,
                exp_mode=args.exp_mode,
                aspect_ratio=args.aspect_ratio,
                max_critic_rounds=args.max_critic_rounds,
                num_candidates=args.num_candidates,
                clean_tex_to_txt=args.clean_tex_to_txt,
            )
    except PaperBananaBackendError as exc:
        if not args.fallback_on_error:
            _write_paperbanana_error_meta(args, str(exc))
            print(f"code2paper-figure: {exc}")
            return 2
        meta = generate_fallback_figure(
            args.method_draft_path,
            out_dir=args.out_dir,
            method_evidence_path=args.method_evidence,
            claim_map_path=args.claim_map,
        )
        meta["paperbanana_error"] = str(exc)
        meta_path = Path(args.out_dir) / "method_overview.meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def _write_paperbanana_error_meta(args: argparse.Namespace, error: str) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "backend": "paperbanana",
        "status": "error",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "draft_path": args.method_draft_path,
            "method_evidence_path": args.method_evidence or "",
            "claim_map_path": args.claim_map or "",
            "paperbanana_root": args.paperbanana_root or "",
            "clean_tex_to_txt": args.clean_tex_to_txt,
        },
        "paperbanana": {
            "retrieval_setting": args.retrieval_setting,
            "exp_mode": args.exp_mode,
            "aspect_ratio": args.aspect_ratio,
            "max_critic_rounds": args.max_critic_rounds,
            "num_candidates": args.num_candidates,
            "model": args.model,
            "image_model": args.image_model,
        },
        "error": error,
        "outputs": {"svg": "", "png": "", "pdf": "", "pptx": "", "drawio": ""},
    }
    meta_path = out_dir / "method_overview.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
