"""One-command story-first Stage 1-9 pipeline."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path

from code2paper.export.run_manifest import build_run_manifest, hash_file, write_run_manifest
from code2paper.rendering.figures.backend_paperbanana import generate_paperbanana_figure
from code2paper.llm.providers import (
    DEFAULT_FIGURE_IMAGE_MODEL,
    DEFAULT_TEXT_MODEL,
    load_llm_config_from_env,
    openai_compatible_base_url,
)
from code2paper.rendering.method_pdf import build_method_section_pdf
from code2paper.core.output_names import artifact_dir, final_dir, method_output
from code2paper.core.output_paths import resolve_out_root, resolve_project_id
from code2paper.pipeline.stages.input_resolution import run_input_resolution
from code2paper.pipeline.stages.grounding import write_phase4_artifacts
from code2paper.pipeline.stages.validation import write_phase6_validation_manifest
from code2paper.pipeline.stages.rendering import write_phase7_rendering_manifest
from code2paper.pipeline.stages.finalize import write_phase8_artifacts
from code2paper.pipeline.stages.intake import run_phase1_intake
from code2paper.pipeline.stages.analysis import run_phase2_analysis
from code2paper.pipeline.stages.evidence import run_phase3_evidence
from code2paper.pipeline.stages.authoring import write_phase5_artifacts
from code2paper.core.schemas import (
    ArtifactHash,
    ClaimEvidenceMap,
    CodeMethodAnalysis,
    LLMProvider,
    RawEvidencePack,
)
from code2paper.validation.fidelity_validator import validate_method_fidelity


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-run",
        description="Run code2paper Stage 1-9 in one command.",
    )
    parser.add_argument("project_root")
    parser.add_argument("--author", dest="author_markers_path", default="")
    parser.add_argument(
        "--draft",
        "--intent",
        "--template",
        dest="draft_path",
        default="",
        help="Rough author intent YAML. It is treated as the primary narrative spec and is grounded to code via code2flow-style candidate retrieval.",
    )
    parser.add_argument("--project-id")
    parser.add_argument(
        "--out-root",
        default="",
        help="Output root. Defaults to ./outputs/<repo_name>_<timestamp>/",
    )
    parser.add_argument(
        "--core-top-k",
        type=int,
        default=12,
        help="How many ranked core files to use for code2flow candidate retrieval and internal marker generation.",
    )
    parser.add_argument(
        "--skip-draft-bootstrap",
        action="store_true",
        help="Skip draft bootstrap Phase 1/2 intake+analysis when --draft/--intent is used.",
    )
    parser.add_argument(
        "--llm-provider",
        choices=[provider.value for provider in LLMProvider] + ["moonshot", "aihubmix", "kimi"],
        default=None,
    )
    parser.add_argument("--llm-model", default="")
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Run only Phase 1 intake and emit prompt/context stubs for Phase 2, 3, and 5.",
    )
    parser.add_argument(
        "--allow-fidelity-fail",
        action="store_true",
        default=True,
        help="Write all artifacts and return 0 even when method fidelity validation fails. Enabled by default.",
    )
    parser.add_argument(
        "--fail-on-fidelity-fail",
        dest="allow_fidelity_fail",
        action="store_false",
        help="Return a non-zero exit code when fidelity validation fails.",
    )
    parser.add_argument(
        "--skip-figure",
        action="store_true",
        help="Skip Phase 7 method overview figure rendering.",
    )
    parser.add_argument(
        "--figure-backend",
        choices=["paperbanana"],
        default="paperbanana",
        help="Phase 7 figure backend. Defaults to PaperBanana.",
    )
    parser.add_argument(
        "--paperbanana-root",
        default="",
        help="Optional PaperBanana root. Defaults to PAPERBANANA_ROOT or ./paperbanana_single_shot.",
    )
    parser.add_argument(
        "--retrieval-setting",
        choices=["auto", "manual", "random", "none"],
        default="auto",
        help="PaperBanana retrieval setting. Defaults to auto for relevant reference selection.",
    )
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    parser.add_argument(
        "--exp-mode",
        choices=["demo_full", "demo_planner_critic", "demo_stylist_once"],
        default="demo_stylist_once",
    )
    parser.add_argument("--figure-model", default="")
    parser.add_argument(
        "--figure-retrieval-model",
        default="",
        help="Optional PaperBanana Retriever-only model. Falls back to --figure-model/main model when omitted.",
    )
    parser.add_argument(
        "--figure-retrieval-ref-limit",
        type=int,
        default=40,
        help="Maximum PaperBanana reference candidates shown to the auto retriever. Defaults to 40 to avoid context overflow.",
    )
    parser.add_argument("--figure-image-model", default="")
    parser.add_argument(
        "--figure-image-model-preset",
        choices=["default", "chat-image-2.0", "aihubmix-gpt-image-2"],
        default="chat-image-2.0",
        help="Convenience preset for PaperBanana image model. 'chat-image-2.0' maps to --figure-image-model aihubmix/chat-image-2.0.",
    )
    parser.add_argument("--figure-chat-api-url", default="")
    parser.add_argument(
        "--figure-require-fidelity-pass",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Only run Phase 7 figure rendering when fidelity validation passes. Disabled by default so full runs can still produce figures when --allow-fidelity-fail is used.",
    )
    parser.add_argument(
        "--figure-optimize-rounds",
        type=int,
        default=1,
        help="Deprecated compatibility option. PaperBanana is called once.",
    )
    parser.add_argument(
        "--figure-semantic-anchor",
        default="",
        help="Optional semantic anchor used to force image/text example consistency in multimodal figures (e.g., panda).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed per-phase artifact paths and debug summaries.",
    )
    parser.add_argument(
        "--method-pdf",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Build standalone text.pdf from text.tex and the generated figure when possible.",
    )
    parser.add_argument(
        "--method-pdf-compiler",
        default="",
        help="Optional LaTeX compiler override (tectonic/xelatex/pdflatex).",
    )
    parser.add_argument(
        "--method-pdf-timeout",
        type=int,
        default=300,
        help="Timeout in seconds for method PDF compilation.",
    )
    args = parser.parse_args(argv)
    if not args.llm_model:
        args.llm_model = os.environ.get("CODE2PAPER_LLM_MODEL", "") or DEFAULT_TEXT_MODEL
    if not args.figure_model:
        args.figure_model = (
            os.environ.get("CODE2PAPER_FIGURE_LLM_MODEL", "")
            or os.environ.get("CODE2PAPER_LLM_MODEL", "")
            or DEFAULT_TEXT_MODEL
        )
    if not args.figure_chat_api_url:
        args.figure_chat_api_url = (
            os.environ.get("CODE2PAPER_FIGURE_OPENAI_BASE_URL", "")
            or os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "")
        )
    if args.figure_image_model_preset == "chat-image-2.0":
        if not args.figure_image_model:
            args.figure_image_model = DEFAULT_FIGURE_IMAGE_MODEL
        elif str(args.figure_image_model).strip() in {"chat-image-2.0", "chat image2.0"}:
            args.figure_image_model = DEFAULT_FIGURE_IMAGE_MODEL
    elif args.figure_image_model_preset == "aihubmix-gpt-image-2":
        if not args.figure_image_model:
            args.figure_image_model = "aihubmix/gpt-image-2"
        elif str(args.figure_image_model).strip() == "gpt-image-2":
            args.figure_image_model = "aihubmix/gpt-image-2"
    verbose_console = args.verbose or _bool_env("CODE2PAPER_VERBOSE_CONSOLE", False)

    raw_author = str(args.author_markers_path or "").strip()
    raw_draft = str(args.draft_path or "").strip()
    if raw_author and raw_draft:
        parser.error("--author and --draft/--intent are mutually exclusive")
    if not raw_author and not raw_draft:
        parser.error("one of --author or --draft/--intent is required")

    project_root = Path(args.project_root)
    project_id = resolve_project_id(args.project_id, project_root=project_root, intent_path=args.draft_path)
    out_root = resolve_out_root(args.out_root, project_root=project_root, intent_path=args.draft_path)
    method_root = out_root / "artifacts"
    method_root.mkdir(parents=True, exist_ok=True)
    llm_config = load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model)
    print(f"[code2paper-run] out_root={out_root}")
    try:
        print("[code2paper-run] Stage 1 input resolution")
        author_input = run_input_resolution(
            author_markers_path=args.author_markers_path,
            intent_path=args.draft_path,
            project_root=project_root,
            out_root=out_root,
            project_id=project_id,
            core_top_k=args.core_top_k,
            annotation_required=False,
            llm_config=llm_config,
            skip_draft_bootstrap=args.skip_draft_bootstrap,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    effective_author_markers_path = str(author_input.effective_author_markers_path)
    original_author_input_path = str(author_input.intent_path or args.author_markers_path or "")
    if author_input.generated_author_markers_path:
        print(f"[code2paper-run] generated_author_markers={author_input.generated_author_markers_path}")

    paths = PipelinePaths(
        evidence_raw=method_output(method_root, "evidence_raw"),
        comment_index=artifact_dir(method_root, "02_intake") / "comment_index.json",
        raw_context_index=artifact_dir(method_root, "02_intake") / "raw_context_index.json",
        context_map=artifact_dir(method_root, "02_intake") / "context_map.json",
        context_pack_entrypoints=artifact_dir(method_root, "02_intake") / "context_packs" / "entrypoints.json",
        context_pack_configs=artifact_dir(method_root, "02_intake") / "context_packs" / "configs.json",
        context_pack_source_core_candidates=artifact_dir(method_root, "02_intake") / "context_packs" / "source_core_candidates.json",
        context_pack_author_hints=artifact_dir(method_root, "02_intake") / "context_packs" / "author_hints.json",
        phase1_manifest=method_output(method_root, "phase1_manifest"),
        navigation_plan=artifact_dir(method_root, "03_analysis") / "analysis_navigation_plan.json",
        targeted_tracing=artifact_dir(method_root, "03_analysis") / "targeted_code_tracing.json",
        alignment=method_output(method_root, "alignment"),
        analysis=method_output(method_root, "analysis"),
        author_summary=method_output(method_root, "author_summary"),
        sources=method_output(method_root, "sources"),
        snippets=method_output(method_root, "snippets"),
        intake_alignment=method_output(method_root, "intake_alignment"),
        intake_report=method_output(method_root, "intake_report"),
        facts=method_output(method_root, "facts"),
        code_graph=method_output(method_root, "code_graph"),
        entity_map=method_output(method_root, "entity_map"),
        analysis_report=method_output(method_root, "analysis_report"),
        phase2_code_report=method_output(method_root, "phase2_code_report"),
        phase2_manifest=method_output(method_root, "phase2_manifest"),
        phase2_blocked_report=method_output(method_root, "phase2_blocked_report"),
        evidence=method_output(method_root, "evidence"),
        evidence_notes=method_output(method_root, "evidence_notes"),
        grounding_context=method_output(method_root, "grounding_context"),
        equations_tex=method_output(method_root, "equations_tex"),
        symbols_tex=method_output(method_root, "symbols_tex"),
        phase4_manifest=method_output(method_root, "phase4_manifest"),
        phase3_manifest=method_output(method_root, "phase3_manifest"),
        claims=method_output(method_root, "claims"),
        text_md=method_output(method_root, "text_md"),
        text_clean_md=method_output(method_root, "text_clean_md"),
        text_tex=method_output(method_root, "text_tex"),
        text_clean_tex=method_output(method_root, "text_clean_tex"),
        write_prompt=method_output(method_root, "write_prompt"),
        text_sidecar=method_output(method_root, "text_sidecar"),
        outline=method_output(method_root, "outline"),
        terms=method_output(method_root, "terms"),
        text_claims=method_output(method_root, "text_claims"),
        phase5_manifest=method_output(method_root, "phase5_manifest"),
        phase5_blocked=method_output(method_root, "phase5_blocked"),
        fidelity=method_output(method_root, "fidelity"),
        phase6_manifest=method_output(method_root, "phase6_manifest"),
        pdf_report=method_output(method_root, "pdf_report"),
        text_pdf=method_output(method_root, "text_pdf"),
        phase7_manifest=method_output(method_root, "phase7_manifest"),
        final_tex=method_output(method_root, "final_tex"),
        final_pdf=method_output(method_root, "final_pdf"),
        final_pdf_report=method_output(method_root, "final_pdf_report"),
        phase8_manifest=method_output(method_root, "phase8_manifest"),
        run_report=method_output(method_root, "run_report"),
        run_manifest=method_output(method_root, "run_manifest"),
    )

    raw_pack: RawEvidencePack | None = None
    if verbose_console and llm_config.provider in {LLMProvider.OPENAI, LLMProvider.OPENROUTER}:
        print(f"[code2paper-run] llm_endpoint={openai_compatible_base_url(llm_config)}")
    print(f"[code2paper-run] Stage 2 intake: {project_root}")
    raw_pack, _comment_index, _raw_context_index, _context_map, _phase1_paths = run_phase1_intake(
        project_root=project_root,
        method_root=method_root,
        author_markers_path=effective_author_markers_path,
        llm_config=llm_config,
        project_id=project_id,
    )
    _print_phase_status(
        phase_name="stage2_intake",
        manifest_path=paths.phase1_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("evidence_raw", paths.evidence_raw),
            ("sources", paths.sources),
            ("snippets", paths.snippets),
            ("intake_alignment", paths.intake_alignment),
            ("intake_report", paths.intake_report),
        ],
        verbose=verbose_console,
    )
    if args.inspect_only:
        inspect_paths = _write_inspect_only_prompts(method_root=method_root, raw_pack=raw_pack)
        run_report = {
            "project_root": str(project_root),
            "project_id": raw_pack.project_id,
            "author_input_mode": author_input.source,
            "author_markers_path": effective_author_markers_path,
            "intent_path": str(author_input.intent_path or ""),
            "template_path": str(author_input.intent_path or ""),
            "author_mode": raw_pack.author_mode.value,
            "author_confirmation_required": raw_pack.author_confirmation_required,
            "inspect_only": True,
            "outputs": paths.as_dict(),
            "inspect_prompt_artifacts": inspect_paths,
        }
        _write_json(paths.run_report, run_report)
        llm_config = load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model)
        manifest = build_run_manifest(
            project_root=project_root,
            readme_policy=raw_pack.readme_policy,
            author_input_path=original_author_input_path,
            llm=llm_config,
            phase_inputs={
                "input_resolution": [str(project_root), original_author_input_path],
                "intake": [str(project_root), effective_author_markers_path],
                **({"coarse_intent": [str(author_input.intent_path)]} if author_input.intent_path else {}),
            },
            output_paths={
                "evidence_raw": paths.evidence_raw,
                "sources": paths.sources,
                "snippets": paths.snippets,
                "intake_alignment": paths.intake_alignment,
                "intake_report": paths.intake_report,
                "input_manifest": method_output(method_root, "input_manifest"),
                "intake_manifest": paths.phase1_manifest,
                **({"generated_author_markers": author_input.generated_author_markers_path} if author_input.generated_author_markers_path else {}),
                "inspect_only_analysis_prompt": artifact_dir(method_root, "03_analysis") / "analysis_prompt_context.md",
                "inspect_only_evidence_prompt": artifact_dir(method_root, "04_evidence") / "evidence_prompt_context.md",
                "inspect_only_authoring_prompt": artifact_dir(method_root, "06_authoring") / "authoring_prompt_context.md",
                "run_report": paths.run_report,
            },
            final_draft_path=None,
            validator_reports=[],
        )
        write_run_manifest(paths.run_manifest, manifest)
        print("[code2paper-run] Inspect-only mode completed.")
        _print_phase_status(
            phase_name="inspect-only",
            manifest_path=paths.run_manifest,
            blocked_report_path=None,
            key_outputs=[
                ("analysis_prompt_context", artifact_dir(method_root, "03_analysis") / "analysis_prompt_context.md"),
                ("evidence_prompt_context", artifact_dir(method_root, "04_evidence") / "evidence_prompt_context.md"),
                ("authoring_prompt_context", artifact_dir(method_root, "06_authoring") / "authoring_prompt_context.md"),
            ],
            verbose=verbose_console,
        )
        print(f"[code2paper-run] run_manifest={paths.run_manifest}")
        return 0

    print("[code2paper-run] Stage 3 analysis")
    alignment, _phase2_paths = run_phase2_analysis(
        project_root=project_root,
        method_root=method_root,
        author_markers_path=effective_author_markers_path,
        llm_config=llm_config,
        project_id=project_id,
    )
    raw_pack = RawEvidencePack.model_validate(json.loads(paths.evidence_raw.read_text(encoding="utf-8")))
    phase2_key_outputs = [
        ("evidence_raw", paths.evidence_raw),
        ("alignment", paths.alignment),
        ("analysis", paths.analysis),
        ("facts", paths.facts),
        ("analysis_report", paths.analysis_report),
    ]
    _print_phase_status(
        phase_name="stage3_analysis",
        manifest_path=paths.phase2_manifest,
        blocked_report_path=paths.phase2_blocked_report,
        key_outputs=phase2_key_outputs,
        verbose=verbose_console,
    )
    print("[code2paper-run] Stage 4 evidence")
    if raw_pack is None:
        raw_pack = RawEvidencePack.model_validate(json.loads(paths.evidence_raw.read_text(encoding="utf-8")))
    code_method_analysis = CodeMethodAnalysis.model_validate(
        json.loads(paths.analysis.read_text(encoding="utf-8"))
    )
    code_facts = _read_json_if_exists(paths.facts) or None
    method_evidence, _phase3_paths = run_phase3_evidence(
        method_root=method_root,
        paper_root=out_root,
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        code_facts=code_facts,
        llm_config=llm_config,
    )
    _print_phase_status(
        phase_name="stage4_evidence",
        manifest_path=paths.phase3_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("evidence", paths.evidence),
            ("claims", paths.claims),
            ("evidence_notes", paths.evidence_notes),
        ],
        verbose=verbose_console,
    )
    print("[code2paper-run] Claim grounding")
    claim_map = ClaimEvidenceMap.model_validate(json.loads(paths.claims.read_text(encoding="utf-8")))
    print(f"[code2paper-run] claims={paths.claims}")
    print("[code2paper-run] Stage 5 grounding")
    phase4_paths = write_phase4_artifacts(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
    )
    _print_phase_status(
        phase_name="stage5_grounding",
        manifest_path=paths.phase4_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("grounding_context", paths.grounding_context),
            ("equations_tex", paths.equations_tex),
            ("symbols_tex", paths.symbols_tex),
        ],
        verbose=verbose_console,
    )

    preflight_blocked_reason = _phase5_preflight_blocked_reason(
        phase2_manifest_path=paths.phase2_manifest,
        phase3_manifest_path=paths.phase3_manifest,
    )
    print("[code2paper-run] Stage 6 authoring")
    markdown, tex, _phase5_paths = write_phase5_artifacts(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
        alignment=alignment,
        preflight_blocked_reason=preflight_blocked_reason,
        grounding_context_markdown=paths.grounding_context.read_text(encoding="utf-8") if paths.grounding_context.exists() else "",
        equations_tex=paths.equations_tex.read_text(encoding="utf-8") if paths.equations_tex.exists() else "",
        symbols_tex=paths.symbols_tex.read_text(encoding="utf-8") if paths.symbols_tex.exists() else "",
    )
    _print_phase_status(
        phase_name="stage6_authoring",
        manifest_path=paths.phase5_manifest,
        blocked_report_path=paths.phase5_blocked,
        key_outputs=[
            ("write_prompt", paths.write_prompt),
            ("text_md", paths.text_md),
            ("text_clean_md", paths.text_clean_md),
            ("text_tex", paths.text_tex),
            ("text_clean_tex", paths.text_clean_tex),
        ],
        verbose=verbose_console,
    )
    if markdown is None and verbose_console:
        _print_phase5_blocked_debug(
            claim_evidence_report_path=method_output(method_root, "qa_claims"),
            numeric_fact_report_path=method_output(method_root, "qa_numbers"),
            equation_support_report_path=method_output(method_root, "qa_equations"),
            terminology_consistency_report_path=method_output(method_root, "qa_terms"),
            latex_smoke_report_path=method_output(method_root, "qa_latex"),
        )
    fidelity_passed = False
    validator_reports = []
    if markdown is not None:
        _copy_user_method_outputs(paths)
        print("[code2paper-run] Stage 7 validation")
        fidelity_report = validate_method_fidelity(
            raw_pack=raw_pack,
            method_evidence=method_evidence,
            draft_markdown=markdown,
            claim_map=claim_map,
        )
        _write_json(paths.fidelity, fidelity_report.model_dump(mode="json"))
        fidelity_passed = fidelity_report.passed
        validator_reports.append(str(paths.fidelity))
        print(f"[code2paper-run] fidelity_passed={fidelity_passed} report={paths.fidelity}")
    else:
        print("[code2paper-run] Stage 6 blocked; skipping Stage 7 validation.")
    validation_report = write_phase6_validation_manifest(
        method_root=method_root,
        fidelity_passed=fidelity_passed,
        validation_skipped_reason="phase5_blocked" if markdown is None else "",
    )
    _print_phase_status(
        phase_name="stage7_validation",
        manifest_path=paths.phase6_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("fidelity", paths.fidelity),
            ("qa_claims", method_output(method_root, "qa_claims")),
            ("qa_latex", method_output(method_root, "qa_latex")),
        ],
        verbose=verbose_console,
    )

    figure_meta: dict | None = None
    figure_skipped_reason = ""
    figure_root = final_dir(method_root, "figures")
    if markdown is None:
        figure_skipped_reason = "phase5_blocked"
    elif args.skip_figure:
        figure_skipped_reason = "user_skip_figure"
    elif args.figure_require_fidelity_pass and not fidelity_passed:
        figure_skipped_reason = "fidelity_not_passed"
        print(
            "[code2paper-run] Stage 8 skipped: fidelity did not pass; "
            "skip expensive figure generation. Use --no-figure-require-fidelity-pass to override."
        )

    if not figure_skipped_reason:
        print(f"[code2paper-run] Stage 8 rendering backend={args.figure_backend}")
        draft_for_figure = (
            paths.text_clean_md
            if paths.text_clean_md.exists()
            else paths.text_clean_tex
            if paths.text_clean_tex.exists()
            else paths.text_tex
            if paths.text_tex.exists()
            else paths.text_md
        )
        figure_meta = generate_paperbanana_figure(
            draft_path=draft_for_figure,
            out_dir=figure_root,
            method_evidence_path=paths.evidence,
            claim_map_path=paths.claims,
            paperbanana_root=args.paperbanana_root,
            chat_api_url=args.figure_chat_api_url,
            model=args.figure_model,
            retrieval_model=args.figure_retrieval_model,
            retrieval_ref_limit=args.figure_retrieval_ref_limit,
            image_model=args.figure_image_model,
            retrieval_setting=args.retrieval_setting,
            exp_mode=args.exp_mode,
            aspect_ratio=args.aspect_ratio,
            num_candidates=args.num_candidates,
            clean_tex_to_txt=True,
            semantic_anchor=args.figure_semantic_anchor,
            optimize_rounds=1,
        )
        print(f"[code2paper-run] method_overview_input={figure_root / 'method_overview.paperbanana_input.txt'}")
        print(f"[code2paper-run] method_overview_meta={figure_root / 'method_overview.meta.json'}")
        if (figure_root / "method_overview.png").exists():
            print(f"[code2paper-run] method_overview_png={figure_root / 'method_overview.png'}")
        if (figure_root / "method_overview.svg").exists():
            print(f"[code2paper-run] method_overview_svg={figure_root / 'method_overview.svg'}")

    method_pdf_report: dict | None = None
    if markdown is not None and args.method_pdf:
        figure_caption = _method_framework_caption(method_evidence)
        figure_asset_basename = _method_framework_asset_basename(method_evidence)
        figure_candidates = [
            figure_root / "method_overview.png",
            figure_root / "method_overview.pdf",
            figure_root / "method_overview.svg",
        ]
        method_pdf_report = build_method_section_pdf(
            method_tex_path=paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex,
            output_dir=paths.text_pdf.parent,
            figure_candidates=figure_candidates,
            compiler=str(args.method_pdf_compiler or "").strip() or None,
            timeout_seconds=int(args.method_pdf_timeout),
            output_basename="method",
            figure_caption=figure_caption,
            figure_asset_basename=figure_asset_basename,
        )
        _copy_standalone_tex_report(method_pdf_report, method_output(method_root, "method_standalone_tex"))
        _write_json(paths.pdf_report, method_pdf_report)
        print(
            "[code2paper-run] method_pdf_status="
            f"{method_pdf_report.get('status', 'unknown')} reason={method_pdf_report.get('reason', '')}"
        )
    rendering_report = write_phase7_rendering_manifest(
        method_root=method_root,
        figure_root=figure_root,
        figure_meta=figure_meta,
        figure_skipped_reason=figure_skipped_reason,
        method_pdf_report=method_pdf_report,
    )
    _print_phase_status(
        phase_name="stage8_rendering",
        manifest_path=paths.phase7_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("method_overview_meta", figure_root / "method_overview.meta.json"),
            ("text_pdf", paths.text_pdf),
            ("pdf_report", paths.pdf_report),
        ],
        verbose=verbose_console,
    )

    phase8_report: dict | None = None
    if markdown is not None:
        print("[code2paper-run] Stage 9 finalize")
        phase8_report = write_phase8_artifacts(
            method_root=method_root,
            method_tex_path=paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex,
            figure_candidates=[
                figure_root / "method_overview.png",
                figure_root / "method_overview.pdf",
                figure_root / "method_overview.svg",
            ],
            equations_tex_path=paths.equations_tex,
            symbols_tex_path=paths.symbols_tex,
            compiler=str(args.method_pdf_compiler or "").strip() or None,
            timeout_seconds=int(args.method_pdf_timeout),
            figure_caption=_method_framework_caption(method_evidence),
            figure_asset_basename=_method_framework_asset_basename(method_evidence),
        )
        _print_phase_status(
            phase_name="stage9_finalize",
            manifest_path=paths.phase8_manifest,
            blocked_report_path=None,
            key_outputs=[
                ("final_tex", paths.final_tex),
                ("final_pdf", paths.final_pdf),
                ("final_pdf_report", paths.final_pdf_report),
            ],
            verbose=verbose_console,
        )

    run_report = {
        "project_root": str(project_root),
        "project_id": raw_pack.project_id,
        "author_input_mode": author_input.source,
        "author_markers_path": effective_author_markers_path,
        "intent_path": str(author_input.intent_path or ""),
        "template_path": str(author_input.intent_path or ""),
        "author_mode": raw_pack.author_mode.value,
        "author_confirmation_required": raw_pack.author_confirmation_required,
        "fidelity_passed": fidelity_passed,
        "authoring_blocked": markdown is None,
        "rendering_skipped_reason": figure_skipped_reason,
        "grounding": {name: str(path) for name, path in phase4_paths.items()},
        "validation": validation_report,
        "rendering": rendering_report,
        "figure": figure_meta or {},
        "method_pdf": method_pdf_report or {},
        "final_package": phase8_report or {},
        "outputs": paths.as_dict(),
    }
    _write_json(paths.run_report, run_report)
    _write_run_report_md(method_output(method_root, "run_report_md"), run_report)

    phase_inputs = {
        "input_resolution": [str(project_root), original_author_input_path],
        "intake": [str(project_root), effective_author_markers_path],
        "analysis": [str(paths.evidence_raw), str(paths.sources), str(paths.snippets), str(paths.intake_alignment)],
        "evidence": [str(paths.evidence_raw), str(paths.alignment), str(paths.analysis), str(paths.facts)],
        "grounding": [str(paths.evidence), str(paths.claims)],
        "authoring": [str(paths.evidence), str(paths.claims), str(paths.evidence_notes), str(paths.grounding_context)],
        "validation": [str(paths.text_clean_md if paths.text_clean_md.exists() else paths.text_md), str(paths.evidence), str(paths.claims)],
        "rendering": [str(paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex)],
        "finalize": [str(paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex)],
        **({"coarse_intent": [str(author_input.intent_path)]} if author_input.intent_path else {}),
    }
    output_paths = {
        "evidence_raw": paths.evidence_raw,
        **({"input_manifest": method_output(method_root, "input_manifest")} if method_output(method_root, "input_manifest").exists() else {}),
        **({"intake_manifest": paths.phase1_manifest} if paths.phase1_manifest.exists() else {}),
        **({"generated_author_markers": author_input.generated_author_markers_path} if author_input.generated_author_markers_path else {}),
        **({"resolved_author_markers": method_output(method_root, "resolved_author_markers_yaml")} if method_output(method_root, "resolved_author_markers_yaml").exists() else {}),
        "alignment": paths.alignment,
        "analysis": paths.analysis,
        **({"author_summary": paths.author_summary} if paths.author_summary.exists() else {}),
        **({"sources": paths.sources} if paths.sources.exists() else {}),
        **({"snippets": paths.snippets} if paths.snippets.exists() else {}),
        **({"intake_alignment": paths.intake_alignment} if paths.intake_alignment.exists() else {}),
        **({"intake_report": paths.intake_report} if paths.intake_report.exists() else {}),
        **({"facts": paths.facts} if paths.facts.exists() else {}),
        **({"code_graph": paths.code_graph} if paths.code_graph.exists() else {}),
        **({"entity_map": paths.entity_map} if paths.entity_map.exists() else {}),
        **({"analysis_report": paths.analysis_report} if paths.analysis_report.exists() else {}),
        "analysis_manifest": paths.phase2_manifest,
        "evidence": paths.evidence,
        "evidence_notes": paths.evidence_notes,
        "evidence_manifest": paths.phase3_manifest,
        "claims": paths.claims,
        "grounding_context": paths.grounding_context,
        "equations_tex": paths.equations_tex,
        "symbols_tex": paths.symbols_tex,
        "grounding_manifest": paths.phase4_manifest,
        "write_prompt": paths.write_prompt,
        "authoring_manifest": paths.phase5_manifest,
        **({"outline": paths.outline} if paths.outline.exists() else {}),
        **({"terms": paths.terms} if paths.terms.exists() else {}),
        **({"text_md": paths.text_md} if paths.text_md.exists() else {}),
        **({"text_clean_md": paths.text_clean_md} if paths.text_clean_md.exists() else {}),
        **({"text_tex": paths.text_tex} if paths.text_tex.exists() else {}),
        **({"text_clean_tex": paths.text_clean_tex} if paths.text_clean_tex.exists() else {}),
        **({"text_sidecar": paths.text_sidecar} if paths.text_sidecar.exists() else {}),
        **({"text_claims": paths.text_claims} if paths.text_claims.exists() else {}),
        **({"fidelity": paths.fidelity} if paths.fidelity.exists() else {}),
        **({"root_method_md": method_output(method_root, "root_method_md")} if method_output(method_root, "root_method_md").exists() else {}),
        **({"root_method_tex": method_output(method_root, "root_method_tex")} if method_output(method_root, "root_method_tex").exists() else {}),
        **({"validation_manifest": paths.phase6_manifest} if paths.phase6_manifest.exists() else {}),
        **({"pdf_report": paths.pdf_report} if paths.pdf_report.exists() else {}),
        **({"method_pdf": paths.text_pdf} if paths.text_pdf.exists() else {}),
        **({"rendering_manifest": paths.phase7_manifest} if paths.phase7_manifest.exists() else {}),
        **({"final_tex": paths.final_tex} if paths.final_tex.exists() else {}),
        **({"final_pdf": paths.final_pdf} if paths.final_pdf.exists() else {}),
        **({"final_pdf_report": paths.final_pdf_report} if paths.final_pdf_report.exists() else {}),
        **({"finalize_manifest": paths.phase8_manifest} if paths.phase8_manifest.exists() else {}),
        **({"method_overview_paperbanana_input": figure_root / "method_overview.paperbanana_input.txt"} if (figure_root / "method_overview.paperbanana_input.txt").exists() else {}),
        **({"method_overview_meta": figure_root / "method_overview.meta.json"} if (figure_root / "method_overview.meta.json").exists() else {}),
        **({"method_overview_svg": figure_root / "method_overview.svg"} if (figure_root / "method_overview.svg").exists() else {}),
        **({"method_overview_png": figure_root / "method_overview.png"} if (figure_root / "method_overview.png").exists() else {}),
        "run_report": paths.run_report,
        **({"run_report_md": method_output(method_root, "run_report_md")} if method_output(method_root, "run_report_md").exists() else {}),
        **({"authoring_blocked": paths.phase5_blocked} if paths.phase5_blocked.exists() else {}),
    }
    manifest = build_run_manifest(
        project_root=project_root,
        readme_policy=raw_pack.readme_policy,
        author_input_path=original_author_input_path,
        llm=llm_config,
        phase_inputs=phase_inputs,
        output_paths=output_paths,
        final_draft_path=paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex if paths.text_tex.exists() else None,
        validator_reports=validator_reports,
    )
    write_run_manifest(paths.run_manifest, manifest)

    if method_output(method_root, "root_method_md").exists():
        print(f"[code2paper-run] method_md={method_output(method_root, 'root_method_md')}")
    if paths.text_md.exists():
        print(f"[code2paper-run] method_draft_md={paths.text_md}")
    if paths.text_clean_md.exists():
        print(f"[code2paper-run] method_clean_md={paths.text_clean_md}")
    if paths.text_tex.exists():
        print(f"[code2paper-run] method_draft_tex={paths.text_tex}")
    if paths.text_clean_tex.exists():
        print(f"[code2paper-run] method_clean_tex={paths.text_clean_tex}")
    if paths.fidelity.exists():
        print(f"[code2paper-run] fidelity={paths.fidelity}")
    if paths.text_pdf.exists():
        print(f"[code2paper-run] method_pdf={paths.text_pdf}")
    if paths.final_pdf.exists():
        print(f"[code2paper-run] final_pdf={paths.final_pdf}")
    print(f"[code2paper-run] run_manifest={paths.run_manifest}")
    if markdown is None:
        _print_llm_endpoint_hint(llm_config=llm_config, blocked_report_path=paths.phase5_blocked)
        print("[code2paper-run] Stage 6 authoring blocked. Inspect authoring_blocked.json.")
        return 0
    if not fidelity_passed:
        print("[code2paper-run] Fidelity validation failed. Inspect fidelity_report.json.")
        return 0 if args.allow_fidelity_fail else 1
    print("[code2paper-run] Fidelity validation passed.")
    return 0


class PipelinePaths:
    def __init__(
        self,
        *,
        evidence_raw: Path,
        comment_index: Path,
        raw_context_index: Path,
        context_map: Path,
        context_pack_entrypoints: Path,
        context_pack_configs: Path,
        context_pack_source_core_candidates: Path,
        context_pack_author_hints: Path,
        phase1_manifest: Path,
        navigation_plan: Path,
        targeted_tracing: Path,
        alignment: Path,
        analysis: Path,
        author_summary: Path,
        sources: Path,
        snippets: Path,
        intake_alignment: Path,
        intake_report: Path,
        facts: Path,
        code_graph: Path,
        entity_map: Path,
        analysis_report: Path,
        phase2_code_report: Path,
        phase2_manifest: Path,
        phase2_blocked_report: Path,
        evidence: Path,
        evidence_notes: Path,
        grounding_context: Path,
        equations_tex: Path,
        symbols_tex: Path,
        phase4_manifest: Path,
        phase3_manifest: Path,
        claims: Path,
        text_md: Path,
        text_clean_md: Path,
        text_tex: Path,
        text_clean_tex: Path,
        write_prompt: Path,
        text_sidecar: Path,
        outline: Path,
        terms: Path,
        text_claims: Path,
        phase5_manifest: Path,
        phase5_blocked: Path,
        fidelity: Path,
        phase6_manifest: Path,
        pdf_report: Path,
        text_pdf: Path,
        phase7_manifest: Path,
        final_tex: Path,
        final_pdf: Path,
        final_pdf_report: Path,
        phase8_manifest: Path,
        run_report: Path,
        run_manifest: Path,
    ) -> None:
        self.evidence_raw = evidence_raw
        self.comment_index = comment_index
        self.raw_context_index = raw_context_index
        self.context_map = context_map
        self.context_pack_entrypoints = context_pack_entrypoints
        self.context_pack_configs = context_pack_configs
        self.context_pack_source_core_candidates = context_pack_source_core_candidates
        self.context_pack_author_hints = context_pack_author_hints
        self.phase1_manifest = phase1_manifest
        self.navigation_plan = navigation_plan
        self.targeted_tracing = targeted_tracing
        self.alignment = alignment
        self.analysis = analysis
        self.author_summary = author_summary
        self.sources = sources
        self.snippets = snippets
        self.intake_alignment = intake_alignment
        self.intake_report = intake_report
        self.facts = facts
        self.code_graph = code_graph
        self.entity_map = entity_map
        self.analysis_report = analysis_report
        self.phase2_code_report = phase2_code_report
        self.phase2_manifest = phase2_manifest
        self.phase2_blocked_report = phase2_blocked_report
        self.evidence = evidence
        self.evidence_notes = evidence_notes
        self.grounding_context = grounding_context
        self.equations_tex = equations_tex
        self.symbols_tex = symbols_tex
        self.phase4_manifest = phase4_manifest
        self.phase3_manifest = phase3_manifest
        self.claims = claims
        self.text_md = text_md
        self.text_clean_md = text_clean_md
        self.text_tex = text_tex
        self.text_clean_tex = text_clean_tex
        self.write_prompt = write_prompt
        self.text_sidecar = text_sidecar
        self.outline = outline
        self.terms = terms
        self.text_claims = text_claims
        self.phase5_manifest = phase5_manifest
        self.phase5_blocked = phase5_blocked
        self.fidelity = fidelity
        self.phase6_manifest = phase6_manifest
        self.pdf_report = pdf_report
        self.text_pdf = text_pdf
        self.phase7_manifest = phase7_manifest
        self.final_tex = final_tex
        self.final_pdf = final_pdf
        self.final_pdf_report = final_pdf_report
        self.phase8_manifest = phase8_manifest
        self.run_report = run_report
        self.run_manifest = run_manifest

    def as_dict(self) -> dict[str, str]:
        return {
            "evidence_raw": str(self.evidence_raw),
            "comment_index": str(self.comment_index),
            "raw_context_index": str(self.raw_context_index),
            "context_map": str(self.context_map),
            "context_pack_entrypoints": str(self.context_pack_entrypoints) if self.context_pack_entrypoints.exists() else "",
            "context_pack_configs": str(self.context_pack_configs) if self.context_pack_configs.exists() else "",
            "context_pack_source_core_candidates": str(self.context_pack_source_core_candidates) if self.context_pack_source_core_candidates.exists() else "",
            "context_pack_author_hints": str(self.context_pack_author_hints) if self.context_pack_author_hints.exists() else "",
            "phase1_manifest": str(self.phase1_manifest) if self.phase1_manifest.exists() else "",
            "analysis_navigation_plan": str(self.navigation_plan),
            "targeted_code_tracing": str(self.targeted_tracing),
            "alignment": str(self.alignment),
            "analysis": str(self.analysis),
            "author_summary": str(self.author_summary) if self.author_summary.exists() else "",
            "sources": str(self.sources) if self.sources.exists() else "",
            "snippets": str(self.snippets) if self.snippets.exists() else "",
            "intake_alignment": str(self.intake_alignment) if self.intake_alignment.exists() else "",
            "intake_report": str(self.intake_report) if self.intake_report.exists() else "",
            "facts": str(self.facts) if self.facts.exists() else "",
            "code_graph": str(self.code_graph) if self.code_graph.exists() else "",
            "entity_map": str(self.entity_map) if self.entity_map.exists() else "",
            "analysis_report": str(self.analysis_report) if self.analysis_report.exists() else "",
            "phase2_code_report": str(self.phase2_code_report) if self.phase2_code_report.exists() else "",
            "phase2_manifest": str(self.phase2_manifest),
            "phase2_blocked_report": str(self.phase2_blocked_report) if self.phase2_blocked_report.exists() else "",
            "evidence": str(self.evidence),
            "evidence_notes": str(self.evidence_notes),
            "grounding_context": str(self.grounding_context) if self.grounding_context.exists() else "",
            "equations_tex": str(self.equations_tex) if self.equations_tex.exists() else "",
            "symbols_tex": str(self.symbols_tex) if self.symbols_tex.exists() else "",
            "phase4_manifest": str(self.phase4_manifest) if self.phase4_manifest.exists() else "",
            "phase3_manifest": str(self.phase3_manifest),
            "claims": str(self.claims),
            "write_prompt": str(self.write_prompt),
            "outline": str(self.outline) if self.outline.exists() else "",
            "terms": str(self.terms) if self.terms.exists() else "",
            "text_md": str(self.text_md) if self.text_md.exists() else "",
            "text_clean_md": str(self.text_clean_md) if self.text_clean_md.exists() else "",
            "text_tex": str(self.text_tex) if self.text_tex.exists() else "",
            "text_clean_tex": str(self.text_clean_tex) if self.text_clean_tex.exists() else "",
            "text_sidecar": str(self.text_sidecar) if self.text_sidecar.exists() else "",
            "text_claims": str(self.text_claims) if self.text_claims.exists() else "",
            "phase5_manifest": str(self.phase5_manifest) if self.phase5_manifest.exists() else "",
            "phase5_blocked": str(self.phase5_blocked) if self.phase5_blocked.exists() else "",
            "root_method_md": str(method_output(self.run_report, "root_method_md")) if method_output(self.run_report, "root_method_md").exists() else "",
            "root_method_tex": str(method_output(self.run_report, "root_method_tex")) if method_output(self.run_report, "root_method_tex").exists() else "",
            "fidelity": str(self.fidelity) if self.fidelity.exists() else "",
            "phase6_manifest": str(self.phase6_manifest) if self.phase6_manifest.exists() else "",
            "pdf_report": str(self.pdf_report) if self.pdf_report.exists() else "",
            "text_pdf": str(self.text_pdf) if self.text_pdf.exists() else "",
            "phase7_manifest": str(self.phase7_manifest) if self.phase7_manifest.exists() else "",
            "final_tex": str(self.final_tex) if self.final_tex.exists() else "",
            "final_pdf": str(self.final_pdf) if self.final_pdf.exists() else "",
            "final_pdf_report": str(self.final_pdf_report) if self.final_pdf_report.exists() else "",
            "phase8_manifest": str(self.phase8_manifest) if self.phase8_manifest.exists() else "",
            "run_report": str(self.run_report),
            "run_manifest": str(self.run_manifest),
        }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_user_method_outputs(paths: PipelinePaths) -> None:
    method_md = paths.text_clean_md if paths.text_clean_md.exists() else paths.text_md
    method_tex = paths.text_clean_tex if paths.text_clean_tex.exists() else paths.text_tex
    root_md = method_output(paths.run_report, "root_method_md")
    root_tex = method_output(paths.run_report, "root_method_tex")
    if method_md.exists():
        root_md.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(method_md, root_md)
    if method_tex.exists():
        root_tex.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(method_tex, root_tex)


def _copy_standalone_tex_report(report: dict | None, target: Path) -> None:
    if not report:
        return
    source = Path(str(report.get("standalone_tex_path") or ""))
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write_run_report_md(path: Path, run_report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    outputs = run_report.get("outputs") if isinstance(run_report.get("outputs"), dict) else {}
    lines = [
        "# Code2Paper Run Report",
        "",
        f"- Project: {run_report.get('project_root', '')}",
        f"- Author input: {run_report.get('author_input_mode', '')}",
        f"- Fidelity passed: {run_report.get('fidelity_passed', False)}",
        f"- Authoring blocked: {run_report.get('authoring_blocked', False)}",
        f"- Rendering skipped: {run_report.get('rendering_skipped_reason', '')}",
        "",
        "## User Results",
        "",
        f"- method.md: {outputs.get('root_method_md', '')}",
        f"- method.tex: {outputs.get('root_method_tex', '')}",
        f"- method.pdf: {outputs.get('text_pdf', '')}",
        f"- final_method.pdf: {outputs.get('final_pdf', '')}",
        "",
        "## Debug Artifacts",
        "",
        f"- run_report.json: {outputs.get('run_report', '')}",
        f"- run_manifest.json: {outputs.get('run_manifest', '')}",
    ]
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _method_framework_caption(method_evidence: MethodEvidence) -> str:
    name = _clean_caption_method_name(getattr(method_evidence, "method_name", ""))
    if name:
        return f"Overall framework of {name}."
    return "Overall framework of the proposed method."


def _method_framework_asset_basename(method_evidence: MethodEvidence) -> str:
    name = _clean_caption_method_name(getattr(method_evidence, "method_name", ""))
    if not name:
        return "method_framework"
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return f"{cleaned}_framework" if cleaned else "method_framework"


def _clean_caption_method_name(value: object) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or text.lower() in {"story-first method pipeline", "method", "method overview"}:
        return ""
    return text[:80]


def _read_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _print_phase_status(
    *,
    phase_name: str,
    manifest_path: Path,
    blocked_report_path: Path | None,
    key_outputs: list[tuple[str, Path]],
    verbose: bool = False,
) -> None:
    manifest = _read_json_if_exists(manifest_path)
    mode = str(manifest.get("mode", "missing")) if manifest else "missing"
    blocked_reason = str(manifest.get("blocked_reason", "")).strip()

    if blocked_report_path is not None and blocked_report_path.exists():
        blocked_report = _read_json_if_exists(blocked_report_path)
        if not blocked_reason:
            blocked_reason = str(blocked_report.get("blocked_reason", "")).strip()

    status = "ok"
    if blocked_reason:
        status = "blocked"
    elif mode in {"inspect-only", "blocked_with_insufficient_analysis"}:
        status = "degraded"

    print(f"[code2paper-run] {phase_name} status={status} mode={mode}")
    if blocked_reason:
        print(f"[code2paper-run] {phase_name} blocked_reason={blocked_reason}")
    if verbose:
        for label, output_path in key_outputs:
            state = "ok" if output_path.exists() else "missing"
            print(f"[code2paper-run] {phase_name} output {label}={state} path={output_path}")
    else:
        missing_labels = [label for label, output_path in key_outputs if not output_path.exists()]
        if missing_labels:
            print(f"[code2paper-run] {phase_name} missing_outputs={','.join(missing_labels)}")


def _print_phase5_blocked_debug(
    *,
    claim_evidence_report_path: Path,
    numeric_fact_report_path: Path,
    equation_support_report_path: Path,
    terminology_consistency_report_path: Path,
    latex_smoke_report_path: Path,
) -> None:
    claim_report = _read_json_if_exists(claim_evidence_report_path)
    if claim_report:
        issues = claim_report.get("issues", [])
        print(
            "[code2paper-run] phase5 claim_evidence "
            f"passed={claim_report.get('passed', False)} "
            f"checked_paragraphs={claim_report.get('checked_paragraphs', 0)} "
            f"issues={len(issues)}"
        )
        for issue in issues[:12]:
            if not isinstance(issue, dict):
                continue
            print(
                "[code2paper-run] phase5 claim_issue "
                f"{issue.get('issue_id', '?')} category={issue.get('category', '')} "
                f"paragraph={issue.get('paragraph_id', '')} message={issue.get('message', '')}"
            )
        if len(issues) > 12:
            print(f"[code2paper-run] phase5 claim_issue_more={len(issues) - 12}")

    for label, report_path in [
        ("numeric_fact", numeric_fact_report_path),
        ("equation_support", equation_support_report_path),
        ("terminology_consistency", terminology_consistency_report_path),
        ("latex_smoke", latex_smoke_report_path),
    ]:
        report = _read_json_if_exists(report_path)
        if not report:
            continue
        passed = report.get("passed", None)
        if isinstance(passed, bool):
            print(f"[code2paper-run] phase5 {label} passed={passed}")


def _print_llm_endpoint_hint(*, llm_config: object, blocked_report_path: Path) -> None:
    blocked = _read_json_if_exists(blocked_report_path)
    blocked_reason = str(blocked.get("blocked_reason", "")).strip()
    if "provider_http_error:404" not in blocked_reason:
        return
    provider_value = getattr(getattr(llm_config, "provider", None), "value", "")
    if provider_value not in {"openai", "openrouter"}:
        return
    try:
        endpoint = openai_compatible_base_url(llm_config)
    except Exception:
        endpoint = ""
    print("[code2paper-run] hint=Phase 5 hit a 404 from the text-model endpoint.")
    if endpoint:
        print(f"[code2paper-run] hint_text_endpoint={endpoint}")
    if provider_value == "openai":
        print(
            "[code2paper-run] hint=Set CODE2PAPER_OPENAI_BASE_URL to your text-model relay. "
            "Do not rely on AIHUBMIX_BASE_URL when it points to an image-only endpoint."
        )


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


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _write_inspect_only_prompts(*, method_root: Path, raw_pack: object) -> list[str]:
    analysis_prompt = artifact_dir(method_root, "03_analysis") / "analysis_prompt_context.md"
    evidence_prompt = artifact_dir(method_root, "04_evidence") / "evidence_prompt_context.md"
    authoring_prompt = artifact_dir(method_root, "06_authoring") / "authoring_prompt_context.md"
    analysis_prompt.parent.mkdir(parents=True, exist_ok=True)
    evidence_prompt.parent.mkdir(parents=True, exist_ok=True)
    authoring_prompt.parent.mkdir(parents=True, exist_ok=True)
    analysis_prompt.write_text(
        "\n".join(
            [
                "# Stage 3 Analysis Prompt Context",
                "",
                "Inputs:",
                "- artifacts/02_intake/evidence_raw.json",
                "- artifacts/02_intake/sources.json",
                "- artifacts/02_intake/snippets.json",
                "- artifacts/02_intake/intake_alignment.json",
                "- artifacts/02_intake/intake_report.json",
                "",
                "Task:",
                "- Build code_facts.json",
                "- Build code_alignment.json",
                "- Build code_analysis.json",
            ]
        ),
        encoding="utf-8",
    )
    evidence_prompt.write_text(
        "\n".join(
            [
                "# Stage 4 Evidence Prompt Context",
                "",
                "Inputs:",
                "- artifacts/03_analysis/code_analysis.json",
                "- artifacts/03_analysis/code_alignment.json",
                "",
                "Task:",
                "- Build method_evidence.json",
                "- Build claim_evidence_map.json",
            ]
        ),
        encoding="utf-8",
    )
    project_id = getattr(raw_pack, "project_id", "")
    authoring_prompt.write_text(
        "\n".join(
            [
                "# Stage 6 Authoring Prompt Context",
                "",
                f"Project ID: {project_id}",
                "",
                "Inputs:",
                "- artifacts/04_evidence/method_evidence.json",
                "- artifacts/04_evidence/claim_evidence_map.json",
                "",
                "Task:",
                "- Build method_outline.json",
                "- Build terminology_table.json",
                "- Build method_draft.md / method_draft.tex",
                "- Build method_claim_map.json and method_sidecar.json",
            ]
        ),
        encoding="utf-8",
    )
    return [str(analysis_prompt), str(evidence_prompt), str(authoring_prompt)]


if __name__ == "__main__":
    raise SystemExit(main())
