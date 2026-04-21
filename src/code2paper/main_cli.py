"""Unified code2paper CLI with phase subcommands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.author_questionnaire import load_author_markers
from code2paper.method_evidence import write_phase3_artifacts
from code2paper.pipeline.stage1_code_intake import run_stage1_code_intake
from code2paper.pipeline.stage2_code_analyze import run_stage2_code_analyze
from code2paper.phase4_authoring import write_phase4_artifacts
from code2paper.run_cli import main as run_main
from code2paper.schemas import ClaimEvidenceMap, CodeMethodAnalysis, CodeAlignmentIR, LLMProvider, MethodEvidence, RawEvidencePack
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.validators.fidelity_validator import validate_method_fidelity_from_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code2paper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--project", dest="project_root", required=True)
    run_parser.add_argument("--author", required=True)
    run_parser.add_argument("--project-id")
    run_parser.add_argument("--out-root", required=True)
    run_parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    run_parser.add_argument("--llm-model", default=None)
    run_parser.add_argument("--inspect-only", action="store_true")
    run_parser.add_argument("--allow-fidelity-fail", action="store_true")
    run_parser.add_argument("--skip-figure", action="store_true")
    run_parser.add_argument("--figure-backend", choices=["paperbanana", "fallback"], default="paperbanana")
    run_parser.add_argument("--paperbanana-root", default="/home/cuihengjia/agent/PosterGen/PaperBanana")
    run_parser.add_argument("--retrieval-setting", choices=["auto", "manual", "random", "none"], default="random")
    run_parser.add_argument("--num-candidates", type=int, default=1)
    run_parser.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    run_parser.add_argument("--exp-mode", choices=["demo_full", "demo_planner_critic"], default="demo_full")
    run_parser.add_argument("--figure-model", default="")
    run_parser.add_argument("--figure-image-model", default="")
    run_parser.add_argument("--figure-chat-api-url", default="")
    run_parser.add_argument("--figure-api-key", default="")
    run_parser.add_argument("--fallback-on-figure-error", action=argparse.BooleanOptionalAction, default=False)
    run_parser.add_argument("--verbose", action="store_true")

    intake_parser = subparsers.add_parser("intake")
    intake_parser.add_argument("--project", dest="project_root", required=True)
    intake_parser.add_argument("--author", required=True)
    intake_parser.add_argument("--project-id")
    intake_parser.add_argument("--out-root", required=True)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--out-root", required=True)
    analyze_parser.add_argument("--author", required=True)
    analyze_parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    analyze_parser.add_argument("--llm-model", default=None)

    evidence_parser = subparsers.add_parser("evidence")
    evidence_parser.add_argument("--out-root", required=True)
    evidence_parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    evidence_parser.add_argument("--llm-model", default=None)

    author_parser = subparsers.add_parser("author")
    author_parser.add_argument("--out-root", required=True)
    author_parser.add_argument("--llm-provider", choices=[provider.value for provider in LLMProvider], default=None)
    author_parser.add_argument("--llm-model", default=None)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--out-root", required=True)

    args = parser.parse_args(argv)
    if args.command == "run":
        run_args = [
            args.project_root,
            "--out-root",
            args.out_root,
        ]
        run_args.extend(["--author", args.author])
        if args.project_id:
            run_args.extend(["--project-id", args.project_id])
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
        if args.figure_image_model:
            run_args.extend(["--figure-image-model", args.figure_image_model])
        if args.figure_chat_api_url:
            run_args.extend(["--figure-chat-api-url", args.figure_chat_api_url])
        if args.figure_api_key:
            run_args.extend(["--figure-api-key", args.figure_api_key])
        if args.fallback_on_figure_error:
            run_args.append("--fallback-on-figure-error")
        if args.verbose:
            run_args.append("--verbose")
        return run_main(run_args)

    if args.command == "intake":
        method_root = Path(args.out_root) / "paper" / "method"
        _, _, _, _, paths = run_stage1_code_intake(
            project_root=Path(args.project_root),
            method_root=method_root,
            author_markers_path=args.author,
            project_id=args.project_id,
            llm_config=load_llm_config_from_env(provider=None, model=None),
        )
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "analyze":
        method_root = Path(args.out_root) / "paper" / "method"
        _, paths = run_stage2_code_analyze(
            project_root=Path(_read_json(method_root / "raw_evidence_pack.json").get("project_root", ".")),
            method_root=method_root,
            author_markers_path=args.author,
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
            raw_pack=RawEvidencePack.model_validate(_read_json(method_root / "raw_evidence_pack.json")),
            alignment=CodeAlignmentIR.model_validate(_read_json(method_root / "code_alignment_ir.json")),
            code_method_analysis=CodeMethodAnalysis.model_validate(_read_json(method_root / "code_method_analysis.json")),
            code_facts=_read_json(method_root / "code_facts.json") if (method_root / "code_facts.json").exists() else None,
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
        )
        _ = method_evidence
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "author":
        method_root = Path(args.out_root) / "paper" / "method"
        preflight_blocked_reason = _phase4_preflight_blocked_reason(
            phase2_manifest_path=method_root / "phase2_manifest.json",
            phase3_manifest_path=method_root / "phase3_manifest.json",
        )
        markdown, tex, paths = write_phase4_artifacts(
            method_root=method_root,
            method_evidence=MethodEvidence.model_validate(_read_json(method_root / "method_evidence.json")),
            claim_map=ClaimEvidenceMap.model_validate(_read_json(Path(args.out_root) / "paper" / "claim_evidence_map.json")),
            llm_config=load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model),
            alignment=CodeAlignmentIR.model_validate(_read_json(method_root / "code_alignment_ir.json"))
            if (method_root / "code_alignment_ir.json").exists()
            else None,
            preflight_blocked_reason=preflight_blocked_reason,
        )
        _ = (markdown, tex)
        print(json.dumps({name: str(path) for name, path in paths.items()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        method_root = Path(args.out_root) / "paper" / "method"
        report = validate_method_fidelity_from_files(
            raw_evidence_path=method_root / "raw_evidence_pack.json",
            method_evidence_path=method_root / "method_evidence.json",
            draft_markdown_path=method_root / "method_draft.md",
            claim_map_path=Path(args.out_root) / "paper" / "claim_evidence_map.json",
        )
        text = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
        print(text)
        return 0 if report.passed else 1

    return 1


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _phase4_preflight_blocked_reason(*, phase2_manifest_path: Path, phase3_manifest_path: Path) -> str:
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
