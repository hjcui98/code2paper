"""Template-first wrapper runner.

Workflow:
1) Resolve rough intent YAML into internal author markers.
2) Run code2paper Stage 1-9 from rough intent + code2flow retrieval.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from code2paper.core.output_paths import resolve_out_root
from code2paper.cli.run import main as run_main
from code2paper.llm.providers import DEFAULT_TEXT_MODEL


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="code2paper-fusion",
        description="Run template-first code2paper pipeline wrapper.",
    )
    p.add_argument("project_root", help="Target code repository")
    p.add_argument(
        "--out-root",
        default="",
        help="Pipeline output root. Defaults to ./outputs/<repo_name>_<timestamp>/",
    )
    p.add_argument(
        "--intent",
        "--template",
        dest="template",
        default="",
        help="Rough author intent YAML (project_goal/method_mainline/pipeline_steps/...)",
    )
    p.add_argument("--project-id", default="")
    p.add_argument("--core-top-k", type=int, default=12)
    p.add_argument("--llm-provider", default=None)
    p.add_argument("--llm-model", default=DEFAULT_TEXT_MODEL)
    p.add_argument("--allow-fidelity-fail", action="store_true")
    p.add_argument("--skip-figure", action="store_true")
    p.add_argument("--figure-backend", choices=["paperbanana"], default="paperbanana")
    p.add_argument("--paperbanana-root", default="")
    p.add_argument("--retrieval-setting", choices=["auto", "manual", "random", "none"], default="auto")
    p.add_argument("--num-candidates", type=int, default=1)
    p.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    p.add_argument(
        "--exp-mode",
        choices=["demo_full", "demo_planner_critic", "demo_stylist_once"],
        default="demo_stylist_once",
    )
    p.add_argument("--figure-model", default=DEFAULT_TEXT_MODEL)
    p.add_argument("--figure-retrieval-model", default="")
    p.add_argument("--figure-retrieval-ref-limit", type=int, default=40)
    p.add_argument("--figure-image-model", default="")
    p.add_argument(
        "--figure-image-model-preset",
        choices=["default", "chat-image-2.0", "aihubmix-gpt-image-2"],
        default="chat-image-2.0",
    )
    p.add_argument("--figure-chat-api-url", default="")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--method-pdf", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--method-pdf-compiler", default="")
    p.add_argument("--method-pdf-timeout", type=int, default=300)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    if str(args.template or "").strip():
        try:
            Path(args.template).expanduser().resolve().read_text(encoding="utf-8")
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
    out_root = resolve_out_root(args.out_root, project_root=project_root, intent_path=args.template)
    print(f"[fusion] out_root={out_root}")

    run_args = [
        str(project_root),
        "--out-root",
        str(out_root),
        "--core-top-k",
        str(args.core_top_k),
        "--figure-backend",
        str(args.figure_backend),
        "--paperbanana-root",
        str(args.paperbanana_root),
        "--retrieval-setting",
        str(args.retrieval_setting),
        "--num-candidates",
        str(args.num_candidates),
        "--aspect-ratio",
        str(args.aspect_ratio),
        "--exp-mode",
        str(args.exp_mode),
        "--figure-retrieval-ref-limit",
        str(args.figure_retrieval_ref_limit),
    ]
    if args.template:
        run_args.extend(["--intent", str(args.template)])
    if args.project_id:
        run_args.extend(["--project-id", str(args.project_id)])
    if args.llm_provider:
        run_args.extend(["--llm-provider", str(args.llm_provider)])
    if args.llm_model:
        run_args.extend(["--llm-model", str(args.llm_model)])
    if args.allow_fidelity_fail:
        run_args.append("--allow-fidelity-fail")
    if args.skip_figure:
        run_args.append("--skip-figure")
    if args.figure_model:
        run_args.extend(["--figure-model", str(args.figure_model)])
    if args.figure_retrieval_model:
        run_args.extend(["--figure-retrieval-model", str(args.figure_retrieval_model)])
    if args.figure_image_model:
        run_args.extend(["--figure-image-model", str(args.figure_image_model)])
    if args.figure_image_model_preset and args.figure_image_model_preset != "default":
        run_args.extend(["--figure-image-model-preset", str(args.figure_image_model_preset)])
    if args.figure_chat_api_url:
        run_args.extend(["--figure-chat-api-url", str(args.figure_chat_api_url)])
    if args.verbose:
        run_args.append("--verbose")
    if args.method_pdf:
        run_args.append("--method-pdf")
    else:
        run_args.append("--no-method-pdf")
    if args.method_pdf_compiler:
        run_args.extend(["--method-pdf-compiler", str(args.method_pdf_compiler)])
    run_args.extend(["--method-pdf-timeout", str(args.method_pdf_timeout)])

    return run_main(run_args)


if __name__ == "__main__":
    raise SystemExit(main())
