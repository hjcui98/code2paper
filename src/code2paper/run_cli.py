"""One-command story-first Phase 1-5 pipeline plus method-fidelity validation."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from code2paper.export.run_manifest import build_run_manifest, hash_file, write_run_manifest
from code2paper.figures.backend_fallback import generate_fallback_figure
from code2paper.figures.backend_paperbanana import PaperBananaBackendError, generate_paperbanana_figure
from code2paper.llm.providers import load_llm_config_from_env
from code2paper.pipeline.stage1_code_intake import run_stage1_code_intake
from code2paper.pipeline.stage2_code_analyze import run_stage2_code_analyze
from code2paper.pipeline.stage3_method_evidence import run_stage3_method_evidence
from code2paper.pipeline.stage4_author import run_stage4_author
from code2paper.schemas import (
    ArtifactHash,
    ClaimEvidenceMap,
    CodeMethodAnalysis,
    LLMProvider,
    RawEvidencePack,
)
from code2paper.validators.fidelity_validator import validate_method_fidelity
from code2paper.agentic.cutover import CutoverDecisionV2, LegacyTrustContractV1
from code2paper.agentic.tool_runtime import atomic_write_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-run",
        description="Run code2paper Phase 1-5 and fidelity validation in one command.",
    )
    parser.add_argument("project_root")
    parser.add_argument("--author", dest="author_markers_path", required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--out-root", required=True)
    parser.add_argument(
        "--mode", choices=("legacy", "agentic", "shadow"), default=None,
        help="Explicit route override. Without this flag, legacy remains the default unless an authorized --cutover-decision activates agentic.",
    )
    parser.add_argument(
        "--cutover-decision", default="",
        help="CutoverDecisionV2 JSON. Only a clean default_ready decision may change the implicit default to agentic.",
    )
    parser.add_argument("--run-id", default="", help="Stable agentic run identity.")
    parser.add_argument("--max-retrieval-rounds", type=int, default=0)
    parser.add_argument("--max-evidence-revision-rounds", type=int, default=0)
    parser.add_argument("--max-authoring-revision-rounds", type=int, default=0)
    parser.add_argument("--max-figure-revision-rounds", type=int, default=0)
    parser.add_argument("--max-semantic-verifier-calls", type=int, default=0)
    parser.add_argument("--fail-on-blocked", action="store_true")
    parser.add_argument(
        "--llm-provider",
        choices=[provider.value for provider in LLMProvider] + ["moonshot", "aihubmix", "kimi"],
        default=None,
    )
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help="Run only Phase 1 intake and emit prompt/context stubs for Phase 2-4.",
    )
    parser.add_argument(
        "--allow-fidelity-fail",
        action="store_true",
        help="Write all artifacts but return 0 even when method fidelity validation fails.",
    )
    parser.add_argument(
        "--skip-figure",
        action="store_true",
        help="Skip Phase 5 method overview figure generation.",
    )
    parser.add_argument(
        "--figure-backend",
        choices=["paperbanana", "fallback"],
        default="paperbanana",
        help="Phase 5 figure backend. Defaults to PaperBanana.",
    )
    parser.add_argument(
        "--paperbanana-root",
        default="/home/cuihengjia/agent/PosterGen/PaperBanana",
        help="PaperBanana root used when --figure-backend=paperbanana.",
    )
    parser.add_argument(
        "--retrieval-setting",
        choices=["auto", "manual", "random", "none"],
        default="random",
        help="PaperBanana retrieval setting. Defaults to random for more visual variation.",
    )
    parser.add_argument("--num-candidates", type=int, default=1)
    parser.add_argument("--aspect-ratio", choices=["21:9", "16:9", "3:2"], default="16:9")
    parser.add_argument("--exp-mode", choices=["demo_full", "demo_planner_critic"], default="demo_full")
    parser.add_argument("--figure-model", default="")
    parser.add_argument("--figure-image-model", default="")
    parser.add_argument("--figure-chat-api-url", default="")
    parser.add_argument("--figure-api-key", default="")
    parser.add_argument(
        "--fallback-on-figure-error",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fallback to deterministic SVG if PaperBanana fails. Default is no fallback.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed per-phase artifact paths and debug summaries.",
    )
    args = parser.parse_args(argv)
    args.mode, activation = _resolve_mode(args.mode, args.cutover_decision)
    if activation:
        atomic_write_json(Path(args.out_root) / "cutover_activation.json", activation)
    if args.mode == "agentic":
        return _run_agentic_mode(args, out_root=Path(args.out_root))
    if args.mode == "shadow":
        _run_shadow_agentic(args)
    verbose_console = args.verbose or _bool_env("CODE2PAPER_VERBOSE_CONSOLE", False)

    project_root = Path(args.project_root)
    out_root = Path(args.out_root)
    paper_root = out_root / "paper"
    method_root = paper_root / "method"
    method_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(method_root / "legacy_trust_contract.json", LegacyTrustContractV1())

    paths = PipelinePaths(
        raw_evidence=method_root / "raw_evidence_pack.json",
        comment_index=method_root / "comment_index.json",
        raw_context_index=method_root / "raw_context_index.json",
        context_map=method_root / "context_map.json",
        context_pack_entrypoints=method_root / "context_packs" / "entrypoints.json",
        context_pack_configs=method_root / "context_packs" / "configs.json",
        context_pack_source_core_candidates=method_root / "context_packs" / "source_core_candidates.json",
        context_pack_author_hints=method_root / "context_packs" / "author_hints.json",
        phase1_manifest=method_root / "phase1_manifest.json",
        navigation_plan=method_root / "analysis_navigation_plan.json",
        targeted_tracing=method_root / "targeted_code_tracing.json",
        alignment=method_root / "code_alignment_ir.json",
        code_method_analysis=method_root / "code_method_analysis.json",
        author_marker_method_summary=method_root / "author_marker_method_summary.json",
        code_sources=method_root / "code_sources.json",
        core_snippets=method_root / "core_snippets.json",
        method_code_alignment=method_root / "method_code_alignment.json",
        code_intake_report=method_root / "code_intake_report.json",
        code_facts=method_root / "code_facts.json",
        code_ir=method_root / "code_ir.json",
        entity_links=method_root / "entity_links.json",
        code_analysis_report=method_root / "code_analysis_report.json",
        phase2_code_report=method_root / "phase2_code_report.json",
        phase2_manifest=method_root / "phase2_manifest.json",
        phase2_blocked_report=method_root / "phase2_blocked_report.json",
        method_evidence=method_root / "method_evidence.json",
        method_evidence_review=method_root / "method_evidence_review.md",
        phase3_manifest=method_root / "phase3_manifest.json",
        claim_map=paper_root / "claim_evidence_map.json",
        method_draft_md=method_root / "method_draft.md",
        method_draft_tex=method_root / "method_draft.tex",
        method_authoring_prompt=method_root / "method_authoring_prompt.md",
        method_authoring_sidecar=method_root / "method_authoring_sidecar.json",
        method_outline=method_root / "method_outline.json",
        terminology_table=method_root / "terminology_table.json",
        draft_claim_map=method_root / "draft_claim_map.json",
        phase4_manifest=method_root / "phase4_manifest.json",
        phase4_blocked_report=method_root / "phase4_blocked_report.json",
        fidelity_report=method_root / "method_fidelity_report.json",
        run_report=method_root / "code2paper_run_report.json",
        run_manifest=method_root / "code2paper_run_manifest.json",
    )

    raw_pack: RawEvidencePack | None = None
    llm_config = load_llm_config_from_env(provider=args.llm_provider, model=args.llm_model)
    print(f"[code2paper-run] Phase 1 story-first code intake: {project_root}")
    raw_pack, _comment_index, _raw_context_index, _context_map, _phase1_paths = run_stage1_code_intake(
        project_root=project_root,
        method_root=method_root,
        author_markers_path=args.author_markers_path,
        llm_config=llm_config,
        project_id=args.project_id,
    )
    _print_phase_status(
        phase_name="phase1",
        manifest_path=paths.phase1_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("raw_evidence_pack", paths.raw_evidence),
            ("code_sources", paths.code_sources),
            ("core_snippets", paths.core_snippets),
            ("method_code_alignment", paths.method_code_alignment),
            ("code_intake_report", paths.code_intake_report),
        ],
        verbose=verbose_console,
    )
    if args.inspect_only:
        inspect_paths = _write_inspect_only_prompts(method_root=method_root, raw_pack=raw_pack)
        run_report = {
            "project_root": str(project_root),
            "project_id": raw_pack.project_id,
            "author_markers_path": str(args.author_markers_path or ""),
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
            author_input_path=args.author_markers_path,
            llm=llm_config,
            phase_inputs={"phase1": [str(project_root), str(args.author_markers_path or "")]},
            output_paths={
                "raw_evidence_pack": paths.raw_evidence,
                "code_sources": paths.code_sources,
                "core_snippets": paths.core_snippets,
                "method_code_alignment": paths.method_code_alignment,
                "code_intake_report": paths.code_intake_report,
                "phase1_manifest": paths.phase1_manifest,
                "inspect_only_phase2_prompt": method_root / "phase2_prompt_context.md",
                "inspect_only_phase3_prompt": method_root / "phase3_prompt_context.md",
                "inspect_only_phase4_prompt": method_root / "phase4_prompt_context.md",
                "run_report": paths.run_report,
                "legacy_trust_contract": method_root / "legacy_trust_contract.json",
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
                ("phase2_prompt_context", method_root / "phase2_prompt_context.md"),
                ("phase3_prompt_context", method_root / "phase3_prompt_context.md"),
                ("phase4_prompt_context", method_root / "phase4_prompt_context.md"),
            ],
            verbose=verbose_console,
        )
        print(f"[code2paper-run] run_manifest={paths.run_manifest}")
        return _finish_shadow_record(args, 0)

    print("[code2paper-run] Phase 2 story-first code analyzer")
    alignment, _phase2_paths = run_stage2_code_analyze(
        project_root=project_root,
        method_root=method_root,
        author_markers_path=args.author_markers_path,
        llm_config=llm_config,
        project_id=args.project_id,
    )
    raw_pack = RawEvidencePack.model_validate(json.loads(paths.raw_evidence.read_text(encoding="utf-8")))
    phase2_key_outputs = [
        ("raw_evidence_pack", paths.raw_evidence),
        ("code_alignment_ir", paths.alignment),
        ("code_method_analysis", paths.code_method_analysis),
        ("code_facts", paths.code_facts),
        ("code_analysis_report", paths.code_analysis_report),
    ]
    _print_phase_status(
        phase_name="phase2",
        manifest_path=paths.phase2_manifest,
        blocked_report_path=paths.phase2_blocked_report,
        key_outputs=phase2_key_outputs,
        verbose=verbose_console,
    )
    print("[code2paper-run] Phase 3 method evidence")
    if raw_pack is None:
        raw_pack = RawEvidencePack.model_validate(json.loads(paths.raw_evidence.read_text(encoding="utf-8")))
    code_method_analysis = CodeMethodAnalysis.model_validate(
        json.loads(paths.code_method_analysis.read_text(encoding="utf-8"))
    )
    code_facts = _read_json_if_exists(paths.code_facts) or None
    method_evidence, _phase3_paths = run_stage3_method_evidence(
        method_root=method_root,
        paper_root=paper_root,
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        code_facts=code_facts,
        llm_config=llm_config,
    )
    _print_phase_status(
        phase_name="phase3",
        manifest_path=paths.phase3_manifest,
        blocked_report_path=None,
        key_outputs=[
            ("method_evidence", paths.method_evidence),
            ("claim_evidence_map", paths.claim_map),
            ("method_evidence_review", paths.method_evidence_review),
        ],
        verbose=verbose_console,
    )
    print("[code2paper-run] Claim grounding")
    claim_map = ClaimEvidenceMap.model_validate(json.loads(paths.claim_map.read_text(encoding="utf-8")))
    print(f"[code2paper-run] claim_evidence_map={paths.claim_map}")

    preflight_blocked_reason = _phase4_preflight_blocked_reason(
        phase2_manifest_path=paths.phase2_manifest,
        phase3_manifest_path=paths.phase3_manifest,
    )
    print("[code2paper-run] Phase 4 method draft")
    markdown, tex, _phase4_paths = run_stage4_author(
        method_root=method_root,
        method_evidence=method_evidence,
        claim_map=claim_map,
        llm_config=llm_config,
        alignment=alignment,
        preflight_blocked_reason=preflight_blocked_reason,
    )
    _print_phase_status(
        phase_name="phase4",
        manifest_path=paths.phase4_manifest,
        blocked_report_path=paths.phase4_blocked_report,
        key_outputs=[
            ("method_authoring_prompt", paths.method_authoring_prompt),
            ("method_draft_md", paths.method_draft_md),
            ("method_draft_tex", paths.method_draft_tex),
        ],
        verbose=verbose_console,
    )
    if markdown is None and verbose_console:
        _print_phase4_blocked_debug(
            claim_evidence_report_path=method_root / "claim_evidence_report.json",
            numeric_fact_report_path=method_root / "numeric_fact_report.json",
            equation_support_report_path=method_root / "equation_support_report.json",
            terminology_consistency_report_path=method_root / "terminology_consistency_report.json",
            latex_smoke_report_path=method_root / "latex_smoke_report.json",
        )
    fidelity_passed = False
    validator_reports = []
    if markdown is not None:
        print("[code2paper-run] Fidelity validation")
        fidelity_report = validate_method_fidelity(
            raw_pack=raw_pack,
            method_evidence=method_evidence,
            draft_markdown=markdown,
            claim_map=claim_map,
        )
        _write_json(paths.fidelity_report, fidelity_report.model_dump(mode="json"))
        fidelity_passed = fidelity_report.passed
        validator_reports.append(str(paths.fidelity_report))
        print(f"[code2paper-run] fidelity_passed={fidelity_passed} report={paths.fidelity_report}")
    else:
        print("[code2paper-run] Phase 4 blocked; skipping fidelity validation.")

    figure_meta: dict | None = None
    figure_root = paper_root / "figures" / "method_overview"
    if markdown is not None and not args.skip_figure:
        print(f"[code2paper-run] Phase 5 method overview figure backend={args.figure_backend}")
        draft_for_figure = paths.method_draft_tex if paths.method_draft_tex.exists() else paths.method_draft_md
        try:
            if args.figure_backend == "paperbanana":
                figure_meta = generate_paperbanana_figure(
                    draft_path=draft_for_figure,
                    out_dir=figure_root,
                    method_evidence_path=paths.method_evidence,
                    claim_map_path=paths.claim_map,
                    paperbanana_root=args.paperbanana_root,
                    chat_api_url=args.figure_chat_api_url,
                    api_key=args.figure_api_key,
                    model=args.figure_model,
                    image_model=args.figure_image_model,
                    retrieval_setting=args.retrieval_setting,
                    exp_mode=args.exp_mode,
                    aspect_ratio=args.aspect_ratio,
                    num_candidates=args.num_candidates,
                    clean_tex_to_txt=True,
                )
            else:
                figure_meta = generate_fallback_figure(
                    draft_for_figure,
                    out_dir=figure_root,
                    method_evidence_path=paths.method_evidence,
                    claim_map_path=paths.claim_map,
                )
        except PaperBananaBackendError as exc:
            if not args.fallback_on_figure_error:
                raise
            print(f"[code2paper-run] PaperBanana failed; falling back to deterministic SVG: {exc}")
            figure_meta = generate_fallback_figure(
                draft_for_figure,
                out_dir=figure_root,
                method_evidence_path=paths.method_evidence,
                claim_map_path=paths.claim_map,
            )
            figure_meta["paperbanana_error"] = str(exc)
        print(f"[code2paper-run] method_overview_input={figure_root / 'method_overview.paperbanana_input.txt'}")
        print(f"[code2paper-run] method_overview_meta={figure_root / 'method_overview.meta.json'}")
        if (figure_root / "method_overview.png").exists():
            print(f"[code2paper-run] method_overview_png={figure_root / 'method_overview.png'}")
        if (figure_root / "method_overview.svg").exists():
            print(f"[code2paper-run] method_overview_svg={figure_root / 'method_overview.svg'}")

    run_report = {
        "project_root": str(project_root),
        "project_id": raw_pack.project_id,
        "author_markers_path": str(args.author_markers_path or ""),
        "author_mode": raw_pack.author_mode.value,
        "author_confirmation_required": raw_pack.author_confirmation_required,
        "fidelity_passed": fidelity_passed,
        "phase4_blocked": markdown is None,
        "phase5_figure": figure_meta or {},
        "outputs": paths.as_dict(),
    }
    _write_json(paths.run_report, run_report)

    phase_inputs = {
        "story_first_code_agents": [
            str(project_root),
            str(args.author_markers_path or ""),
        ],
        "phase3": [str(paths.raw_evidence), str(paths.alignment), str(paths.code_method_analysis)],
        "phase4": [str(paths.method_evidence), str(paths.claim_map), str(paths.method_evidence_review)],
    }
    output_paths = {
        "raw_evidence_pack": paths.raw_evidence,
        **({"phase1_manifest": paths.phase1_manifest} if paths.phase1_manifest.exists() else {}),
        "code_alignment_ir": paths.alignment,
        "code_method_analysis": paths.code_method_analysis,
        **({"author_marker_method_summary": paths.author_marker_method_summary} if paths.author_marker_method_summary.exists() else {}),
        **({"code_sources": paths.code_sources} if paths.code_sources.exists() else {}),
        **({"core_snippets": paths.core_snippets} if paths.core_snippets.exists() else {}),
        **({"method_code_alignment": paths.method_code_alignment} if paths.method_code_alignment.exists() else {}),
        **({"code_intake_report": paths.code_intake_report} if paths.code_intake_report.exists() else {}),
        **({"code_facts": paths.code_facts} if paths.code_facts.exists() else {}),
        **({"code_ir": paths.code_ir} if paths.code_ir.exists() else {}),
        **({"entity_links": paths.entity_links} if paths.entity_links.exists() else {}),
        **({"code_analysis_report": paths.code_analysis_report} if paths.code_analysis_report.exists() else {}),
        "phase2_manifest": paths.phase2_manifest,
        "method_evidence": paths.method_evidence,
        "method_evidence_review": paths.method_evidence_review,
        "phase3_manifest": paths.phase3_manifest,
        "claim_evidence_map": paths.claim_map,
        "method_authoring_prompt": paths.method_authoring_prompt,
        "phase4_manifest": paths.phase4_manifest,
        **({"method_outline": paths.method_outline} if paths.method_outline.exists() else {}),
        **({"terminology_table": paths.terminology_table} if paths.terminology_table.exists() else {}),
        **({"method_draft_md": paths.method_draft_md} if paths.method_draft_md.exists() else {}),
        **({"method_draft_tex": paths.method_draft_tex} if paths.method_draft_tex.exists() else {}),
        **({"method_authoring_sidecar": paths.method_authoring_sidecar} if paths.method_authoring_sidecar.exists() else {}),
        **({"draft_claim_map": paths.draft_claim_map} if paths.draft_claim_map.exists() else {}),
        **({"method_fidelity_report": paths.fidelity_report} if paths.fidelity_report.exists() else {}),
        **({"method_overview_paperbanana_input": figure_root / "method_overview.paperbanana_input.txt"} if (figure_root / "method_overview.paperbanana_input.txt").exists() else {}),
        **({"method_overview_meta": figure_root / "method_overview.meta.json"} if (figure_root / "method_overview.meta.json").exists() else {}),
        **({"method_overview_svg": figure_root / "method_overview.svg"} if (figure_root / "method_overview.svg").exists() else {}),
        **({"method_overview_png": figure_root / "method_overview.png"} if (figure_root / "method_overview.png").exists() else {}),
        "run_report": paths.run_report,
        "legacy_trust_contract": method_root / "legacy_trust_contract.json",
        **({"phase4_blocked_report": paths.phase4_blocked_report} if paths.phase4_blocked_report.exists() else {}),
    }
    manifest = build_run_manifest(
        project_root=project_root,
        readme_policy=raw_pack.readme_policy,
        author_input_path=args.author_markers_path,
        llm=llm_config,
        phase_inputs=phase_inputs,
        output_paths=output_paths,
        final_draft_path=paths.method_draft_tex if paths.method_draft_tex.exists() else None,
        validator_reports=validator_reports,
    )
    write_run_manifest(paths.run_manifest, manifest)

    if paths.method_draft_md.exists():
        print(f"[code2paper-run] method_draft_md={paths.method_draft_md}")
    if paths.method_draft_tex.exists():
        print(f"[code2paper-run] method_draft_tex={paths.method_draft_tex}")
    if paths.fidelity_report.exists():
        print(f"[code2paper-run] fidelity_report={paths.fidelity_report}")
    print(f"[code2paper-run] run_manifest={paths.run_manifest}")
    if markdown is None:
        print("[code2paper-run] Phase 4 authoring blocked. Inspect phase4_blocked_report.json.")
        return _finish_shadow_record(args, 0)
    if not fidelity_passed:
        print("[code2paper-run] Fidelity validation failed. Inspect method_fidelity_report.json.")
        return _finish_shadow_record(args, 0 if args.allow_fidelity_fail else 1)
    print("[code2paper-run] Fidelity validation passed.")
    return _finish_shadow_record(args, 0)


def _run_agentic_mode(args, *, out_root: Path) -> int:
    from code2paper.cli.agentic_run import main as agentic_main

    command = [
        str(args.project_root),
        "--author", str(args.author_markers_path),
        "--out-root", str(out_root),
        "--run-id", str(args.run_id or uuid.uuid4()),
        "--max-retrieval-rounds", str(max(0, args.max_retrieval_rounds)),
        "--max-evidence-revision-rounds", str(max(0, args.max_evidence_revision_rounds)),
        "--max-authoring-revision-rounds", str(max(0, args.max_authoring_revision_rounds)),
        "--max-figure-revision-rounds", str(max(0, args.max_figure_revision_rounds)),
        "--max-semantic-verifier-calls", str(max(0, args.max_semantic_verifier_calls)),
    ]
    if args.project_id:
        command.extend(["--project-id", str(args.project_id)])
    if args.llm_provider:
        command.extend(["--llm-provider", str(args.llm_provider)])
    if args.llm_model:
        command.extend(["--llm-model", str(args.llm_model)])
    if args.fail_on_blocked:
        command.append("--fail-on-blocked")
    return agentic_main(command)


def _run_shadow_agentic(args) -> None:
    legacy_out = Path(args.out_root)
    shadow_out = legacy_out / "shadow_agentic"
    code = _run_agentic_mode(args, out_root=shadow_out)
    record = {
        "schema_version": "2.0",
        "mode": "shadow",
        "status": "legacy_pending",
        "delivery_route": "legacy",
        "shadow_route": "agentic",
        "shadow_exit_code": code,
        "shadow_out_root": str(shadow_out),
        "claim_of_completion_allowed": False,
        "legacy_contract_version": LegacyTrustContractV1().contract_version,
        "artifacts": {},
        "comparison_ready_for_named_review": False,
    }
    atomic_write_json(legacy_out / "shadow_comparison.json", record)
    print(f"[code2paper-run] shadow_agentic_exit_code={code} shadow_record={legacy_out / 'shadow_comparison.json'}")


def _finish_shadow_record(args, legacy_exit_code: int) -> int:
    if args.mode != "shadow":
        return legacy_exit_code
    out_root = Path(args.out_root)
    record_path = out_root / "shadow_comparison.json"
    record = _read_json_if_exists(record_path)
    agentic_root = out_root / "shadow_agentic"
    candidates = {
        "legacy_run_report": out_root / "paper/method/code2paper_run_report.json",
        "legacy_run_manifest": out_root / "paper/method/code2paper_run_manifest.json",
        "legacy_trust_contract": out_root / "paper/method/legacy_trust_contract.json",
        "agentic_run_summary": agentic_root / "artifacts/10_run/agentic_run_summary.json",
        "agentic_completion_report": agentic_root / "artifacts/10_run/agentic_run_completion_report.json",
        "agentic_package_manifest": agentic_root / "final/package_manifest.json",
    }
    artifacts = {
        key: {"path": str(path), "hash": hash_file(path)}
        for key, path in candidates.items()
        if path.is_file()
    }
    required = set(candidates)
    record.update({
        "status": "completed",
        "legacy_exit_code": legacy_exit_code,
        "artifacts": artifacts,
        "comparison_ready_for_named_review": (
            legacy_exit_code == 0
            and int(record.get("shadow_exit_code", 1)) == 0
            and required.issubset(artifacts)
        ),
    })
    atomic_write_json(record_path, record)
    return legacy_exit_code


def _resolve_mode(explicit_mode: str | None, decision_path: str) -> tuple[str, dict[str, object]]:
    if explicit_mode:
        return explicit_mode, {}
    if not decision_path:
        return "legacy", {}
    path = Path(decision_path).expanduser().resolve()
    activation: dict[str, object] = {
        "schema_version": "2.0",
        "decision_path": str(path),
        "decision_digest": hash_file(path) if path.is_file() else "",
        "authorized": False,
        "resolved_mode": "legacy",
        "reason": "cutover_decision_missing_or_invalid",
    }
    try:
        decision = CutoverDecisionV2.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "legacy", activation
    authorized = (
        decision.status == "default_ready"
        and decision.default_mode == "agentic"
        and decision.hard_gates_passed
        and not decision.failures
    )
    activation.update({
        "decision_status": decision.status,
        "authorized": authorized,
        "resolved_mode": "agentic" if authorized else "legacy",
        "reason": "default_ready_cutover_authorized" if authorized else "cutover_decision_not_default_ready",
    })
    return ("agentic" if authorized else "legacy"), activation


class PipelinePaths:
    def __init__(
        self,
        *,
        raw_evidence: Path,
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
        code_method_analysis: Path,
        author_marker_method_summary: Path,
        code_sources: Path,
        core_snippets: Path,
        method_code_alignment: Path,
        code_intake_report: Path,
        code_facts: Path,
        code_ir: Path,
        entity_links: Path,
        code_analysis_report: Path,
        phase2_code_report: Path,
        phase2_manifest: Path,
        phase2_blocked_report: Path,
        method_evidence: Path,
        method_evidence_review: Path,
        phase3_manifest: Path,
        claim_map: Path,
        method_draft_md: Path,
        method_draft_tex: Path,
        method_authoring_prompt: Path,
        method_authoring_sidecar: Path,
        method_outline: Path,
        terminology_table: Path,
        draft_claim_map: Path,
        phase4_manifest: Path,
        phase4_blocked_report: Path,
        fidelity_report: Path,
        run_report: Path,
        run_manifest: Path,
    ) -> None:
        self.raw_evidence = raw_evidence
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
        self.code_method_analysis = code_method_analysis
        self.author_marker_method_summary = author_marker_method_summary
        self.code_sources = code_sources
        self.core_snippets = core_snippets
        self.method_code_alignment = method_code_alignment
        self.code_intake_report = code_intake_report
        self.code_facts = code_facts
        self.code_ir = code_ir
        self.entity_links = entity_links
        self.code_analysis_report = code_analysis_report
        self.phase2_code_report = phase2_code_report
        self.phase2_manifest = phase2_manifest
        self.phase2_blocked_report = phase2_blocked_report
        self.method_evidence = method_evidence
        self.method_evidence_review = method_evidence_review
        self.phase3_manifest = phase3_manifest
        self.claim_map = claim_map
        self.method_draft_md = method_draft_md
        self.method_draft_tex = method_draft_tex
        self.method_authoring_prompt = method_authoring_prompt
        self.method_authoring_sidecar = method_authoring_sidecar
        self.method_outline = method_outline
        self.terminology_table = terminology_table
        self.draft_claim_map = draft_claim_map
        self.phase4_manifest = phase4_manifest
        self.phase4_blocked_report = phase4_blocked_report
        self.fidelity_report = fidelity_report
        self.run_report = run_report
        self.run_manifest = run_manifest

    def as_dict(self) -> dict[str, str]:
        return {
            "raw_evidence_pack": str(self.raw_evidence),
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
            "code_alignment_ir": str(self.alignment),
            "code_method_analysis": str(self.code_method_analysis),
            "author_marker_method_summary": str(self.author_marker_method_summary) if self.author_marker_method_summary.exists() else "",
            "code_sources": str(self.code_sources) if self.code_sources.exists() else "",
            "core_snippets": str(self.core_snippets) if self.core_snippets.exists() else "",
            "method_code_alignment": str(self.method_code_alignment) if self.method_code_alignment.exists() else "",
            "code_intake_report": str(self.code_intake_report) if self.code_intake_report.exists() else "",
            "code_facts": str(self.code_facts) if self.code_facts.exists() else "",
            "code_ir": str(self.code_ir) if self.code_ir.exists() else "",
            "entity_links": str(self.entity_links) if self.entity_links.exists() else "",
            "code_analysis_report": str(self.code_analysis_report) if self.code_analysis_report.exists() else "",
            "phase2_code_report": str(self.phase2_code_report) if self.phase2_code_report.exists() else "",
            "phase2_manifest": str(self.phase2_manifest),
            "phase2_blocked_report": str(self.phase2_blocked_report) if self.phase2_blocked_report.exists() else "",
            "method_evidence": str(self.method_evidence),
            "method_evidence_review": str(self.method_evidence_review),
            "phase3_manifest": str(self.phase3_manifest),
            "claim_evidence_map": str(self.claim_map),
            "method_authoring_prompt": str(self.method_authoring_prompt),
            "method_outline": str(self.method_outline) if self.method_outline.exists() else "",
            "terminology_table": str(self.terminology_table) if self.terminology_table.exists() else "",
            "method_draft_md": str(self.method_draft_md) if self.method_draft_md.exists() else "",
            "method_draft_tex": str(self.method_draft_tex) if self.method_draft_tex.exists() else "",
            "method_authoring_sidecar": str(self.method_authoring_sidecar) if self.method_authoring_sidecar.exists() else "",
            "draft_claim_map": str(self.draft_claim_map) if self.draft_claim_map.exists() else "",
            "phase4_manifest": str(self.phase4_manifest) if self.phase4_manifest.exists() else "",
            "phase4_blocked_report": str(self.phase4_blocked_report) if self.phase4_blocked_report.exists() else "",
            "method_fidelity_report": str(self.fidelity_report) if self.fidelity_report.exists() else "",
            "run_report": str(self.run_report),
            "run_manifest": str(self.run_manifest),
        }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _print_phase4_blocked_debug(
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
            "[code2paper-run] phase4 claim_evidence "
            f"passed={claim_report.get('passed', False)} "
            f"checked_paragraphs={claim_report.get('checked_paragraphs', 0)} "
            f"issues={len(issues)}"
        )
        for issue in issues[:12]:
            if not isinstance(issue, dict):
                continue
            print(
                "[code2paper-run] phase4 claim_issue "
                f"{issue.get('issue_id', '?')} category={issue.get('category', '')} "
                f"paragraph={issue.get('paragraph_id', '')} message={issue.get('message', '')}"
            )
        if len(issues) > 12:
            print(f"[code2paper-run] phase4 claim_issue_more={len(issues) - 12}")

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
            print(f"[code2paper-run] phase4 {label} passed={passed}")


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


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _write_inspect_only_prompts(*, method_root: Path, raw_pack: object) -> list[str]:
    phase2_prompt = method_root / "phase2_prompt_context.md"
    phase3_prompt = method_root / "phase3_prompt_context.md"
    phase4_prompt = method_root / "phase4_prompt_context.md"
    phase2_prompt.write_text(
        "\n".join(
            [
                "# Phase 2 Prompt Context",
                "",
                "Inputs:",
                "- paper/method/raw_evidence_pack.json",
                "- paper/method/code_sources.json",
                "- paper/method/core_snippets.json",
                "- paper/method/method_code_alignment.json",
                "- paper/method/code_intake_report.json",
                "",
                "Task:",
                "- Build code_facts.json",
                "- Build code_alignment_ir.json",
                "- Build code_method_analysis.json",
            ]
        ),
        encoding="utf-8",
    )
    phase3_prompt.write_text(
        "\n".join(
            [
                "# Phase 3 Prompt Context",
                "",
                "Inputs:",
                "- paper/method/code_method_analysis.json",
                "- paper/method/code_alignment_ir.json",
                "",
                "Task:",
                "- Build method_evidence.json",
                "- Build claim_evidence_map.json",
            ]
        ),
        encoding="utf-8",
    )
    project_id = getattr(raw_pack, "project_id", "")
    phase4_prompt.write_text(
        "\n".join(
            [
                "# Phase 4 Prompt Context",
                "",
                f"Project ID: {project_id}",
                "",
                "Inputs:",
                "- paper/method/method_evidence.json",
                "- paper/claim_evidence_map.json",
                "",
                "Task:",
                "- Build method_outline.json",
                "- Build terminology_table.json",
                "- Build method_draft.md / method_draft.tex",
                "- Build draft_claim_map.json and authoring sidecar",
            ]
        ),
        encoding="utf-8",
    )
    return [str(phase2_prompt), str(phase3_prompt), str(phase4_prompt)]


if __name__ == "__main__":
    raise SystemExit(main())
