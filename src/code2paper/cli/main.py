"""Unified code2paper CLI with phase subcommands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.pipeline.stages.evidence import write_phase3_artifacts
from code2paper.core.output_names import method_output
from code2paper.core.output_paths import resolve_out_root, resolve_project_id
from code2paper.pipeline.stages.intake import run_phase1_intake
from code2paper.pipeline.stages.analysis import run_phase2_analysis
from code2paper.pipeline.stages.authoring import write_phase5_artifacts
from code2paper.cli.agentic_benchmark import main as agentic_benchmark_main
from code2paper.cli.prepare import run_prepare
from code2paper.cli.agentic_run import main as agentic_run_main
from code2paper.cli.run import main as run_main
from code2paper.core.schemas import ClaimEvidenceMap, CodeMethodAnalysis, CodeAlignmentIR, LLMProvider, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import DEFAULT_TEXT_MODEL, load_llm_config_from_env
from code2paper.validation.fidelity_validator import validate_method_fidelity_from_files


_LLM_PROVIDER_CHOICES = [provider.value for provider in LLMProvider] + ["moonshot", "aihubmix", "kimi"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--project", dest="project_root", required=True)
    run_parser.add_argument("--author", default="")
    run_parser.add_argument(
        "--draft",
        "--intent",
        "--template",
        dest="draft",
        default="",
        help="Rough author intent YAML used as the primary narrative spec and grounded to code with code2flow-style retrieval.",
    )
    run_parser.add_argument("--project-id")
    run_parser.add_argument("--out-root", default="")
    run_parser.add_argument("--core-top-k", type=int, default=12)
    run_parser.add_argument("--skip-draft-bootstrap", action="store_true")
    run_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    run_parser.add_argument("--llm-model", default=DEFAULT_TEXT_MODEL)
    run_parser.add_argument("--inspect-only", action="store_true")
    run_parser.add_argument("--allow-fidelity-fail", action="store_true")
    run_parser.add_argument("--skip-figure", action="store_true")
    run_parser.add_argument("--figure-backend", choices=["paperbanana"], default="paperbanana")
    run_parser.add_argument("--paperbanana-root", default="")
    run_parser.add_argument("--retrieval-setting", choices=["auto", "manual", "random", "none"], default="auto")
    run_parser.add_argument("--num-candidates", type=int, default=1)
    run_parser.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    run_parser.add_argument("--exp-mode", choices=["demo_full", "demo_planner_critic", "demo_stylist_once"], default="demo_stylist_once")
    run_parser.add_argument("--figure-model", default=DEFAULT_TEXT_MODEL)
    run_parser.add_argument("--figure-retrieval-model", default="")
    run_parser.add_argument("--figure-retrieval-ref-limit", type=int, default=40)
    run_parser.add_argument("--figure-image-model", default="")
    run_parser.add_argument(
        "--figure-image-model-preset",
        choices=["default", "chat-image-2.0", "aihubmix-gpt-image-2"],
        default="chat-image-2.0",
    )
    run_parser.add_argument("--figure-chat-api-url", default="")
    run_parser.add_argument("--verbose", action="store_true")
    run_parser.add_argument("--method-pdf", action=argparse.BooleanOptionalAction, default=True)
    run_parser.add_argument("--method-pdf-compiler", default="")
    run_parser.add_argument("--method-pdf-timeout", type=int, default=300)

    agentic_parser = subparsers.add_parser("agentic-run")
    agentic_parser.add_argument("--project", dest="project_root", required=True)
    agentic_parser.add_argument("--author", default="")
    agentic_parser.add_argument("--draft", "--intent", "--template", dest="draft", default="")
    agentic_parser.add_argument("--project-id", default="")
    agentic_parser.add_argument("--out-root", default="")
    agentic_parser.add_argument("--core-top-k", type=int, default=12)
    agentic_parser.add_argument("--skip-draft-bootstrap", action="store_true")
    agentic_parser.add_argument("--max-retrieval-rounds", type=int, default=0)
    agentic_parser.add_argument("--max-evidence-revision-rounds", type=int, default=0)
    agentic_parser.add_argument("--max-authoring-revision-rounds", type=int, default=0)
    agentic_parser.add_argument("--max-figure-revision-rounds", type=int, default=0)
    agentic_parser.add_argument("--max-semantic-verifier-calls", type=int, default=0)
    agentic_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    agentic_parser.add_argument("--llm-model", default=None)
    agentic_parser.add_argument("--fail-on-blocked", action="store_true")

    agentic_benchmark_parser = subparsers.add_parser("agentic-benchmark")
    agentic_benchmark_parser.add_argument("--run", action="append", default=[])
    agentic_benchmark_parser.add_argument("reports", nargs="*")
    agentic_benchmark_parser.add_argument("--out", required=True)

    intake_parser = subparsers.add_parser("intake")
    intake_parser.add_argument("--project", dest="project_root", required=True)
    intake_parser.add_argument("--resolved-markers", required=True)
    intake_parser.add_argument("--project-id")
    intake_parser.add_argument("--out-root", default="")

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--project", dest="project_root", default="")
    analyze_parser.add_argument("--out-root", required=True)
    analyze_parser.add_argument("--resolved-markers", required=True)
    analyze_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    analyze_parser.add_argument("--llm-model", default=None)

    evidence_parser = subparsers.add_parser("evidence")
    evidence_parser.add_argument("--out-root", required=True)
    evidence_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    evidence_parser.add_argument("--llm-model", default=None)

    author_parser = subparsers.add_parser("author")
    author_parser.add_argument("--out-root", required=True)
    author_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    author_parser.add_argument("--llm-model", default=None)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--out-root", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--project", dest="project_root", required=True)
    prepare_parser.add_argument("--draft", required=True)
    prepare_parser.add_argument("--out-root", default="")
    prepare_parser.add_argument("--project-id")
    prepare_parser.add_argument("--core-top-k", type=int, default=12)
    prepare_parser.add_argument("--skip-draft-bootstrap", action="store_true")
    prepare_parser.add_argument("--llm-provider", choices=_LLM_PROVIDER_CHOICES, default=None)
    prepare_parser.add_argument("--llm-model", default=None)

    args = parser.parse_args(argv)
    if args.command == "run":
        run_args = [args.project_root]
        if args.out_root:
            run_args.extend(["--out-root", args.out_root])
        if args.author:
            run_args.extend(["--author", args.author])
        if args.draft:
            run_args.extend(["--draft", args.draft])
        if args.project_id:
            run_args.extend(["--project-id", args.project_id])
        run_args.extend(["--core-top-k", str(args.core_top_k)])
        if args.skip_draft_bootstrap:
            run_args.append("--skip-draft-bootstrap")
        if args.llm_provider:
            run_args.extend(["--llm-provider", args.llm_provider])
        if args.llm_model:
            run_args.extend(["--llm-model", args.llm_model])
        if args.inspect_only:
            run_args.append("--inspect-only")
        if args.allow_fidelity_fail:
            run_args.append("--allow-fidelity-fail")
        if args.skip_figure:
            run_args.append("--skip-figure")
        run_args.extend(["--figure-backend", args.figure_backend])
        run_args.extend(["--paperbanana-root", args.paperbanana_root])
        run_args.extend(["--retrieval-setting", args.retrieval_setting])
        run_args.extend(["--num-candidates", str(args.num_candidates)])
        run_args.extend(["--aspect-ratio", args.aspect_ratio])
        run_args.extend(["--exp-mode", args.exp_mode])
        if args.figure_model:
            run_args.extend(["--figure-model", args.figure_model])
        if args.figure_retrieval_model:
            run_args.extend(["--figure-retrieval-model", args.figure_retrieval_model])
        run_args.extend(["--figure-retrieval-ref-limit", str(args.figure_retrieval_ref_limit)])
        if args.figure_image_model:
            run_args.extend(["--figure-image-model", args.figure_image_model])
        if args.figure_image_model_preset and args.figure_image_model_preset != "default":
            run_args.extend(["--figure-image-model-preset", args.figure_image_model_preset])
        if args.figure_chat_api_url:
            run_args.extend(["--figure-chat-api-url", args.figure_chat_api_url])
        if args.verbose:
            run_args.append("--verbose")
        if args.method_pdf:
            run_args.append("--method-pdf")
        else:
            run_args.append("--no-method-pdf")
        if args.method_pdf_compiler:
            run_args.extend(["--method-pdf-compiler", args.method_pdf_compiler])
        run_args.extend(["--method-pdf-timeout", str(args.method_pdf_timeout)])
        return run_main(run_args)

    if args.command == "agentic-run":
        run_args = [args.project_root]
        if args.author:
            run_args.extend(["--author", args.author])
        if args.draft:
            run_args.extend(["--draft", args.draft])
        if args.project_id:
            run_args.extend(["--project-id", args.project_id])
        if args.out_root:
            run_args.extend(["--out-root", args.out_root])
        run_args.extend(["--core-top-k", str(args.core_top_k)])
        if args.skip_draft_bootstrap:
            run_args.append("--skip-draft-bootstrap")
        run_args.extend(["--max-retrieval-rounds", str(args.max_retrieval_rounds)])
        run_args.extend(["--max-evidence-revision-rounds", str(args.max_evidence_revision_rounds)])
        run_args.extend(["--max-authoring-revision-rounds", str(args.max_authoring_revision_rounds)])
        run_args.extend(["--max-figure-revision-rounds", str(args.max_figure_revision_rounds)])
        run_args.extend(["--max-semantic-verifier-calls", str(args.max_semantic_verifier_calls)])
        if args.llm_provider:
            run_args.extend(["--llm-provider", args.llm_provider])
        if args.llm_model:
            run_args.extend(["--llm-model", args.llm_model])
        if args.fail_on_blocked:
            run_args.append("--fail-on-blocked")
        return agentic_run_main(run_args)

    if args.command == "agentic-benchmark":
        benchmark_args: list[str] = []
        for run in args.run:
            benchmark_args.extend(["--run", run])
        benchmark_args.extend(args.reports)
        benchmark_args.extend(["--out", args.out])
        return agentic_benchmark_main(benchmark_args)

    if args.command == "intake":
        out_root = resolve_out_root(args.out_root, project_root=Path(args.project_root))
        method_root = out_root / "paper" / "method"
        _, _, _, _, paths = run_phase1_intake(
            project_root=Path(args.project_root),
            method_root=method_root,
            author_markers_path=args.resolved_markers,
            project_id=args.project_id,
            llm_config=load_llm_config_from_env(provider=None, model=None),
        )
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "analyze":
        method_root = Path(args.out_root) / "paper" / "method"
        try:
            project_root = _resolve_project_root(args.project_root, method_root=method_root)
        except ValueError as exc:
            parser.error(str(exc))
        _, paths = run_phase2_analysis(
            project_root=project_root,
            method_root=method_root,
            author_markers_path=args.resolved_markers,
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
        )
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "evidence":
        method_root = Path(args.out_root) / "paper" / "method"
        paper_root = Path(args.out_root) / "paper"
        method_evidence, paths = write_phase3_artifacts(
            method_root=method_root,
            paper_root=paper_root,
            raw_pack=RawEvidencePack.model_validate(_read_json(method_output(method_root, "evidence_raw"))),
            alignment=CodeAlignmentIR.model_validate(_read_json(method_output(method_root, "alignment"))),
            code_method_analysis=CodeMethodAnalysis.model_validate(_read_json(method_output(method_root, "analysis"))),
            code_facts=_read_json(method_output(method_root, "facts")) if method_output(method_root, "facts").exists() else None,
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
        )
        _ = method_evidence
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "author":
        method_root = Path(args.out_root) / "paper" / "method"
        preflight_blocked_reason = _phase5_preflight_blocked_reason(
            phase2_manifest_path=method_root / "phase2_manifest.json",
            phase3_manifest_path=method_root / "phase3_manifest.json",
        )
        markdown, tex, paths = write_phase5_artifacts(
            method_root=method_root,
            method_evidence=MethodEvidence.model_validate(_read_json(method_output(method_root, "evidence"))),
            claim_map=ClaimEvidenceMap.model_validate(_read_json(method_output(method_root, "claims"))),
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
            alignment=CodeAlignmentIR.model_validate(_read_json(method_output(method_root, "alignment")))
            if method_output(method_root, "alignment").exists()
            else None,
            preflight_blocked_reason=preflight_blocked_reason,
        )
        _ = (markdown, tex)
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        method_root = Path(args.out_root) / "paper" / "method"
        report = validate_method_fidelity_from_files(
            raw_evidence_path=method_output(method_root, "evidence_raw"),
            method_evidence_path=method_output(method_root, "evidence"),
            draft_markdown_path=method_output(method_root, "text_md"),
            claim_map_path=method_output(method_root, "claims"),
        )
        text = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
        print(text)
        return 0 if report.passed else 1

    if args.command == "prepare":
        project_root = Path(args.project_root)
        project_id = resolve_project_id(args.project_id, project_root=project_root, intent_path=args.draft)
        out_root = resolve_out_root(args.out_root, project_root=project_root, intent_path=args.draft)
        result = run_prepare(
            project_root=project_root,
            draft_path=Path(args.draft),
            out_root=out_root,
            project_id=project_id,
            core_top_k=int(args.core_top_k),
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            skip_draft_bootstrap=args.skip_draft_bootstrap,
        )
        printable = {key: str(value) if isinstance(value, Path) else value for key, value in result.items()}
        print(json.dumps(printable, ensure_ascii=False, indent=2))
        return int(result.get("exit_code", 0))

    return 1


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_project_root(project_root: str, *, method_root: Path) -> Path:
    explicit = str(project_root or "").strip()
    if explicit:
        return Path(explicit)
    raw = str(_read_json(method_output(method_root, "evidence_raw")).get("project_root", "")).strip()
    if raw:
        return Path(raw)
    raise ValueError("Could not resolve project root from phase outputs. Pass --project explicitly.")


def _phase5_preflight_blocked_reason(*, phase2_manifest_path: Path, phase3_manifest_path: Path) -> str:
    phase2_mode = ""
    if phase2_manifest_path.exists():
        phase2_mode = str(json.loads(phase2_manifest_path.read_text(encoding="utf-8")).get("mode", ""))
    reasons: list[str] = []
    if phase2_mode == "inspect-only":
        reasons.append("phase2=inspect-only")
    if not reasons:
        return ""
    return "blocked_with_insufficient_analysis:" + ",".join(reasons)


if __name__ == "__main__":
    raise SystemExit(main())
