"""Phase 5 method planning and authoring."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from code2paper.export.run_manifest import hash_file
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.response_schemas import (
    METHOD_DRAFT_SCHEMA,
    METHOD_PLAN_SCHEMA,
    json_schema_for,
    try_parse_structured_response,
)
from code2paper.core.schemas import (
    ArtifactHash,
    ClaimEvidenceMap,
    CodeAlignmentIR,
    DraftMarkdownOutput,
    DraftClaimMap,
    LLMConfig,
    LLMProvider,
    MethodAuthoringSidecar,
    MethodAuthoringSidecarParagraph,
    MethodEvidence,
    MethodOutline,
    MethodOutlineParagraph,
    MethodPlanEquation,
    MethodPlanOutput,
    MethodPlanSection,
    Phase5BlockedReport,
    Phase5CriticIssue,
    Phase5Manifest,
    SelfCriticReport,
    Severity,
    TerminologyTable,
    TerminologyTerm,
)
from code2paper.validation.equation_support_validator import validate_equation_support
from code2paper.validation.claim_evidence_validator import validate_claim_evidence
from code2paper.validation.latex_smoke_validator import validate_latex_smoke
from code2paper.validation.numeric_fact_validator import validate_numeric_facts
from code2paper.core.output_names import method_output
from code2paper.validation.paper_readiness_validator import validate_paper_readiness
from code2paper.validation.terminology_validator import validate_terminology_consistency
from code2paper.authoring.writing.md_formatter import grounding_comment
from code2paper.authoring.writing.method_writer import build_method_draft_markdown
from code2paper.authoring.writing.tex_formatter import format_method_draft_tex

_META_STAGE_HINTS = (
    "overview",
    "prelim",
    "introduction",
    "setup",
    "parse",
    "argument",
    "config",
    "entrypoint",
    "cli",
    "notes",
    "report",
    "ablation",
    "implementation details",
    "environment",
)

_IMPLEMENTATION_LEAKAGE_RE = re.compile(
    r"(?i)([A-Za-z]:\\|/home/|\.(?:py|sh|ps1|bat)\b|python\s+-m|--[A-Za-z0-9_\-]+|"
    r"\b[a-z_]\w*(?:\.[A-Za-z_]\w*){2,}\b|__init__|run_net|"
    r"\b(?:script|shell command|command line|cli argument|entrypoint|launcher)\b)"
)


def write_phase5_artifacts(
    *,
    method_root: Path,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    llm_config: LLMConfig,
    alignment: CodeAlignmentIR | None = None,
    preflight_blocked_reason: str = "",
    grounding_context_markdown: str = "",
    equations_tex: str = "",
    symbols_tex: str = "",
) -> tuple[str | None, str | None, dict[str, Path]]:
    method_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "write_prompt": method_output(method_root, "write_prompt"),
        "phase5_blocked": method_output(method_root, "phase5_blocked"),
        "outline": method_output(method_root, "outline"),
        "method_plan": method_output(method_root, "method_plan"),
        "method_plan_quality": method_output(method_root, "method_plan_quality"),
        "semantic_issues": method_output(method_root, "semantic_issues"),
        "terms": method_output(method_root, "terms"),
        "text_md": method_output(method_root, "text_md"),
        "text_clean_md": method_output(method_root, "text_clean_md"),
        "text_tex": method_output(method_root, "text_tex"),
        "text_clean_tex": method_output(method_root, "text_clean_tex"),
        "text_claims": method_output(method_root, "text_claims"),
        "text_sidecar": method_output(method_root, "text_sidecar"),
        "self_check": method_output(method_root, "self_check"),
        "self_check_clean": method_output(method_root, "self_check_clean"),
        "qa_claims": method_output(method_root, "qa_claims"),
        "qa_numbers": method_output(method_root, "qa_numbers"),
        "qa_equations": method_output(method_root, "qa_equations"),
        "qa_terms": method_output(method_root, "qa_terms"),
        "qa_latex": method_output(method_root, "qa_latex"),
        "phase5_manifest": method_output(method_root, "phase5_manifest"),
    }
    _remove_stale_phase5_outputs(paths)
    authoring_prompt = _authoring_prompt(method_evidence, claim_map)
    paths["write_prompt"].write_text(authoring_prompt, encoding="utf-8")

    if preflight_blocked_reason:
        _write_blocked_phase5(
            paths=paths,
            method_evidence=method_evidence,
            mode="blocked_with_insufficient_analysis",
            blocked_reason=preflight_blocked_reason,
            llm_available=False,
        )
        return None, None, paths

    outline = _outline_scaffold(method_evidence)
    terminology = _terminology_scaffold(method_evidence)
    claim_map_output = _draft_claim_map_scaffold(outline)
    claim_map_output = _normalize_draft_claim_map(
        draft_claim_map=claim_map_output,
        outline=outline,
        method_evidence=method_evidence,
        claim_map=claim_map,
    )
    _write_json(paths["outline"], outline.model_dump(mode="json"))
    _write_json(paths["terms"], terminology.model_dump(mode="json"))
    _write_json(paths["text_claims"], claim_map_output.model_dump(mode="json"))

    if _is_projection_writer_input(method_evidence):
        # The graph-level authoring planner already decides claim order/grouping.
        # Keep the compatibility writer deterministic so legacy free-text
        # expansion cannot reopen a positive-fact channel outside projection.
        method_plan = _method_plan_scaffold(method_evidence, equations_tex=equations_tex)
        _write_json(paths["method_plan"], method_plan.model_dump(mode="json"))
        _write_json(paths["method_plan_quality"], _method_plan_quality_report(method_plan))
        markdown = build_method_draft_markdown(
            method_evidence=method_evidence,
            claim_map=claim_map,
            supplemental_equations_tex=equations_tex,
        )
        latex = format_method_draft_tex(markdown)
        _write_phase5_success_outputs(
            paths=paths,
            method_evidence=method_evidence,
            claim_map=claim_map,
            alignment=alignment,
            outline=outline,
            terminology=terminology,
            claim_map_output=claim_map_output,
            markdown=markdown,
            latex=latex,
            llm_call_id="",
            manifest_mode="projection-constrained-deterministic-writer",
            llm_available=llm_config.provider != LLMProvider.NONE,
            llm_call_logs=[],
            supplemental_equations_tex=equations_tex,
            method_plan=method_plan,
        )
        return markdown, latex, paths

    if llm_config.provider == LLMProvider.NONE:
        method_plan = _method_plan_scaffold(method_evidence, equations_tex=equations_tex)
        _write_json(paths["method_plan"], method_plan.model_dump(mode="json"))
        _write_json(paths["method_plan_quality"], _method_plan_quality_report(method_plan))
        markdown = build_method_draft_markdown(
            method_evidence=method_evidence,
            claim_map=claim_map,
            supplemental_equations_tex=equations_tex,
        )
        if not _is_projection_writer_input(method_evidence):
            markdown = _maybe_compact_display_equations(markdown)
            markdown = _paper_prose_postprocess(markdown, method_evidence, equations_tex=equations_tex)
            markdown = _repair_structural_readiness_if_needed(
                markdown=markdown,
                method_evidence=method_evidence,
                equations_tex=equations_tex,
            )
        readiness_report = validate_paper_readiness(markdown)
        if _paper_readiness_blocks(readiness_report):
            _write_json(paths["self_check"], _readiness_to_self_critic(readiness_report).model_dump(mode="json"))
            _write_blocked_phase5(
                paths=paths,
                method_evidence=method_evidence,
                mode="blocked_paper_readiness_fallback",
                blocked_reason=_paper_readiness_block_reason(readiness_report),
                llm_available=False,
                validator_reports=[str(paths["self_check"])],
            )
            return None, None, paths
        latex = format_method_draft_tex(markdown)
        _write_phase5_success_outputs(
            paths=paths,
            method_evidence=method_evidence,
            claim_map=claim_map,
            alignment=alignment,
            outline=outline,
            terminology=terminology,
            claim_map_output=claim_map_output,
            markdown=markdown,
            latex=latex,
            llm_call_id="",
            manifest_mode="deterministic-authoring-fallback",
            llm_available=False,
            llm_call_logs=[],
            supplemental_equations_tex=equations_tex,
            method_plan=method_plan,
        )
        return markdown, latex, paths

    plan_payload = _phase5_llm_payload(
        authoring_prompt=authoring_prompt,
        grounding_context_markdown=grounding_context_markdown,
        equations_tex=equations_tex,
        symbols_tex=symbols_tex,
        outline=outline,
        terminology=terminology,
        claim_map_output=claim_map_output,
    )
    plan_request = LLMRequest(
        prompt_template_id="phase5_method_plan_v1",
        prompt=_method_plan_llm_prompt(),
        input_payload=plan_payload,
        schema_name=METHOD_PLAN_SCHEMA,
        response_json_schema=json_schema_for(MethodPlanOutput),
    )
    plan_response = _complete_phase5_with_retries(llm_config, plan_request)
    method_plan, plan_parse_error = try_parse_structured_response(plan_response.text, MethodPlanOutput)
    draft_from_plan_response, _draft_from_plan_error = try_parse_structured_response(plan_response.text, DraftMarkdownOutput)
    reuse_plan_response_as_draft = bool(
        plan_response.blocked_reason
        or (draft_from_plan_response is not None and draft_from_plan_response.markdown.strip())
        or method_plan is None
        or not method_plan.sections
    )
    if method_plan is None or not method_plan.sections:
        method_plan = _method_plan_scaffold(method_evidence, equations_tex=equations_tex)
        plan_note = plan_response.blocked_reason or plan_parse_error or "empty_method_plan"
    else:
        plan_note = ""
    plan_json = method_plan.model_dump(mode="json")
    if plan_note:
        plan_json["fallback_note"] = plan_note
    _write_json(paths["method_plan"], plan_json)
    _write_json(paths["method_plan_quality"], _method_plan_quality_report(method_plan))
    plan_call_logs = [plan_response.response_hash] if plan_response.response_hash else []

    phase5_request = LLMRequest(
        prompt_template_id="phase5_method_authoring_v2",
        prompt=_method_draft_llm_prompt(),
        input_payload=_phase5_llm_payload(
            authoring_prompt=authoring_prompt,
            grounding_context_markdown=grounding_context_markdown,
            equations_tex=equations_tex,
            symbols_tex=symbols_tex,
            outline=outline,
            terminology=terminology,
            claim_map_output=claim_map_output,
            method_plan=method_plan,
        ),
        schema_name=METHOD_DRAFT_SCHEMA,
        response_json_schema=json_schema_for(DraftMarkdownOutput),
    )
    llm_response = plan_response if reuse_plan_response_as_draft else _complete_phase5_with_retries(llm_config, phase5_request)
    initial_call_logs = list(plan_call_logs)
    if llm_response.response_hash and llm_response.response_hash not in initial_call_logs:
        initial_call_logs.append(llm_response.response_hash)
    if llm_response.blocked_reason:
        if _should_use_deterministic_fallback(llm_response.blocked_reason):
            markdown = build_method_draft_markdown(
                method_evidence,
                claim_map,
                supplemental_equations_tex=equations_tex,
            )
            markdown = _maybe_compact_display_equations(markdown)
            markdown = _paper_prose_postprocess(markdown, method_evidence, equations_tex=equations_tex)
            markdown = _repair_structural_readiness_if_needed(
                markdown=markdown,
                method_evidence=method_evidence,
                equations_tex=equations_tex,
            )
            readiness_report = validate_paper_readiness(markdown)
            if _paper_readiness_blocks(readiness_report):
                _write_json(paths["self_check"], _readiness_to_self_critic(readiness_report).model_dump(mode="json"))
                _write_blocked_phase5(
                    paths=paths,
                    method_evidence=method_evidence,
                    mode="blocked_paper_readiness_fallback",
                    blocked_reason=_paper_readiness_block_reason(readiness_report),
                    llm_available=False,
                    llm_call_logs=initial_call_logs,
                    validator_reports=[str(paths["self_check"])],
                )
                return None, None, paths
            latex = format_method_draft_tex(markdown)
            _write_phase5_success_outputs(
                paths=paths,
                method_evidence=method_evidence,
                claim_map=claim_map,
                alignment=alignment,
                outline=outline,
                terminology=terminology,
                claim_map_output=claim_map_output,
                markdown=markdown,
                latex=latex,
                llm_call_id="",
                manifest_mode="deterministic-authoring-fallback",
                llm_available=False,
                llm_call_logs=initial_call_logs,
                supplemental_equations_tex=equations_tex,
                method_plan=method_plan,
            )
            return markdown, latex, paths
        _write_blocked_phase5(
            paths=paths,
            method_evidence=method_evidence,
            mode="blocked_llm_required",
            blocked_reason=llm_response.blocked_reason,
            llm_available=False,
            llm_call_logs=initial_call_logs,
        )
        return None, None, paths

    draft_output, parse_error = try_parse_structured_response(llm_response.text, DraftMarkdownOutput)
    if draft_output is None or not draft_output.markdown.strip():
        fallback_reason = parse_error or "empty_method_draft_markdown"
        if _should_use_deterministic_fallback(fallback_reason):
            markdown = build_method_draft_markdown(
                method_evidence,
                claim_map,
                supplemental_equations_tex=equations_tex,
            )
            markdown = _maybe_compact_display_equations(markdown)
            markdown = _paper_prose_postprocess(markdown, method_evidence, equations_tex=equations_tex)
            markdown = _repair_structural_readiness_if_needed(
                markdown=markdown,
                method_evidence=method_evidence,
                equations_tex=equations_tex,
            )
            readiness_report = validate_paper_readiness(markdown)
            if _paper_readiness_blocks(readiness_report):
                _write_json(paths["self_check"], _readiness_to_self_critic(readiness_report).model_dump(mode="json"))
                _write_blocked_phase5(
                    paths=paths,
                    method_evidence=method_evidence,
                    mode="blocked_paper_readiness_fallback",
                    blocked_reason=_paper_readiness_block_reason(readiness_report),
                    llm_available=True,
                    llm_call_logs=initial_call_logs,
                    validator_reports=[str(paths["self_check"])],
                )
                return None, None, paths
            latex = format_method_draft_tex(markdown)
            _write_phase5_success_outputs(
                paths=paths,
                method_evidence=method_evidence,
                claim_map=claim_map,
                alignment=alignment,
                outline=outline,
                terminology=terminology,
                claim_map_output=claim_map_output,
                markdown=markdown,
                latex=latex,
                llm_call_id=llm_response.response_hash,
                manifest_mode="deterministic-authoring-fallback",
                llm_available=True,
                llm_call_logs=initial_call_logs,
                supplemental_equations_tex=equations_tex,
                method_plan=method_plan,
            )
            return markdown, latex, paths
        _write_blocked_phase5(
            paths=paths,
            method_evidence=method_evidence,
            mode="blocked_llm_response_invalid",
            blocked_reason=fallback_reason,
            llm_available=True,
            llm_call_logs=initial_call_logs,
        )
        return None, None, paths

    draft_markdown = _augment_markdown_with_equation_chain(
        markdown=draft_output.markdown,
        equations_tex=equations_tex,
    )
    markdown = _normalize_markdown_grounding_comments(
        markdown=draft_markdown,
        draft_claim_map=claim_map_output,
        method_evidence=method_evidence,
        claim_map=claim_map,
    )
    markdown = _maybe_compact_display_equations(markdown)
    markdown = _paper_prose_postprocess(markdown, method_evidence, equations_tex=equations_tex)
    _write_json(paths["semantic_issues"], _semantic_method_issues(markdown, method_plan))
    markdown, llm_call_logs, manifest_mode = _revise_until_paper_ready(
        markdown=markdown,
        llm_config=llm_config,
        base_request=phase5_request,
        method_evidence=method_evidence,
        claim_map=claim_map,
        grounding_context_markdown=grounding_context_markdown,
        equations_tex=equations_tex,
        symbols_tex=symbols_tex,
        draft_claim_map=claim_map_output,
        method_plan=method_plan,
        initial_call_logs=initial_call_logs,
        manifest_mode="llm-authoring",
    )
    markdown = _repair_structural_readiness_if_needed(
        markdown=markdown,
        method_evidence=method_evidence,
        equations_tex=equations_tex,
    )
    _write_json(paths["semantic_issues"], _semantic_method_issues(markdown, method_plan))
    readiness_report = validate_paper_readiness(markdown)
    if _paper_readiness_blocks(readiness_report):
        _write_json(paths["self_check"], _readiness_to_self_critic(readiness_report).model_dump(mode="json"))
        _write_blocked_phase5(
            paths=paths,
            method_evidence=method_evidence,
            mode="blocked_paper_readiness",
            blocked_reason=_paper_readiness_block_reason(readiness_report),
            llm_available=True,
            llm_call_logs=llm_call_logs,
            validator_reports=[str(paths["self_check"])],
        )
        return None, None, paths
    latex = format_method_draft_tex(markdown)
    _write_phase5_success_outputs(
        paths=paths,
        method_evidence=method_evidence,
        claim_map=claim_map,
        alignment=alignment,
        outline=outline,
        terminology=terminology,
        claim_map_output=claim_map_output,
        markdown=markdown,
        latex=latex,
        llm_call_id=llm_response.response_hash,
        manifest_mode=manifest_mode,
        llm_available=True,
        llm_call_logs=llm_call_logs,
        supplemental_equations_tex=equations_tex,
        method_plan=method_plan,
    )
    return markdown, latex, paths


def _write_blocked_phase5(
    *,
    paths: dict[str, Path],
    method_evidence: MethodEvidence,
    mode: str,
    blocked_reason: str,
    llm_available: bool,
    llm_call_logs: list[str] | None = None,
    validator_reports: list[str] | None = None,
) -> None:
    blocked_report = Phase5BlockedReport(
        project_id=method_evidence.project_id,
        blocked_reason=blocked_reason,
        generated_prompt_artifacts=[str(paths["write_prompt"])],
    )
    _write_json(paths["phase5_blocked"], blocked_report.model_dump(mode="json"))
    manifest = Phase5Manifest(
        project_id=method_evidence.project_id,
        mode=mode,
        llm_available=llm_available,
        blocked_reason=blocked_reason,
        outputs=_artifact_hashes(paths, existing_only=True, exclude={"phase5_manifest"}),
        llm_call_logs=llm_call_logs or [],
        validator_reports=validator_reports or [],
    )
    _write_json(paths["phase5_manifest"], manifest.model_dump(mode="json"))


def _complete_phase5_with_retries(llm_config: LLMConfig, request: LLMRequest):
    attempts = max(1, int(os.environ.get("CODE2PAPER_PHASE5_LLM_EMPTY_ROUNDS", os.environ.get("CODE2PAPER_PHASE4_LLM_EMPTY_ROUNDS", "2")) or "2"))
    response = LLMClient(llm_config).complete(request)
    for _ in range(1, attempts):
        if not _should_use_deterministic_fallback(response.blocked_reason):
            return response
        response = LLMClient(llm_config).complete(request)
    return response


def _method_plan_scaffold(method_evidence: MethodEvidence, *, equations_tex: str) -> MethodPlanOutput:
    packets = _stage_authoring_packets(method_evidence)
    aliases = _dedupe(
        [
            alias.alias
            for alias in method_evidence.paper_module_aliases
            if alias.alias and alias.evidence_span_ids
        ]
    )
    equations = _extract_equation_tex_blocks(equations_tex)
    plan_equations = [
        MethodPlanEquation(
            equation_id=f"EQ{index}",
            purpose=_equation_explanation(equation),
            source_family=_equation_family(equation),
            required=index <= 6,
        )
        for index, equation in enumerate(equations[:10], start=1)
    ]
    sections = [
        MethodPlanSection(
            section_id="PLAN-OVERVIEW",
            heading="Overview",
            purpose="State the baseline problem, the method response, and the main module flow.",
            role="overview",
            stage_ids=[str(packet.get("stage_id") or "") for packet in packets if str(packet.get("stage_id") or "")],
            mechanism_ids=_dedupe(
                [
                    mechanism_id
                    for packet in packets
                    for mechanism_id in _clean_list(packet.get("primary_mechanism_ids"))
                ]
            )[:8],
            evidence_span_ids=_dedupe(
                [
                    evidence_id
                    for packet in packets
                    for evidence_id in _clean_list(packet.get("primary_evidence_ids"))
                ]
            )[:20],
            required_mechanisms=[_paper_stage_name(str(packet.get("name") or "")) for packet in packets[:4]],
            input_operation_output="Summarize how the method transforms the input representation into prediction and reconstruction signals.",
            input_representation="method input representation",
            operation="summarize the supported method flow and distinguish core transformations from runtime protocol",
            output_representation="paper-facing method narrative",
            figure_role="omit",
            priority=98,
        )
    ]
    for index, packet in enumerate(packets[:6], start=1):
        heading = _paper_stage_name(str(packet.get("name") or "")) or f"Method Stage {index}"
        section_role = _plan_section_role(heading, str(packet.get("purpose") or ""))
        input_repr, operation, output_repr = _plan_io_parts(packet)
        section_equations = [
            equation.equation_id
            for equation in plan_equations
            if equation.source_family in _section_equation_families(heading, str(packet.get("purpose") or ""))
        ][:3]
        sections.append(
            MethodPlanSection(
                section_id=f"PLAN-S{index}",
                heading=_objective_section_title(heading) if _looks_like_objective_packet(packet) else heading,
                purpose=str(packet.get("purpose") or f"Explain {heading}."),
                role=section_role,
                stage_ids=[str(packet.get("stage_id") or "")],
                mechanism_ids=_clean_list(packet.get("primary_mechanism_ids"))[:8],
                evidence_span_ids=_clean_list(packet.get("primary_evidence_ids"))[:20],
                required_mechanisms=_clean_list(packet.get("key_operations"))[:6],
                input_operation_output=_plan_io_contract(packet),
                input_representation=input_repr,
                operation=operation,
                output_representation=output_repr,
                figure_role=_plan_figure_role(section_role, heading, str(packet.get("purpose") or "")),
                priority=_plan_priority(section_role, index),
                required_equation_ids=section_equations,
                forbidden_details=["local paths", "script names", "CLI flags", "validation or testing protocol"],
            )
        )
    if not any(section.role in {"core", "objective"} for section in sections):
        first_input, _first_operation, _first_output = _plan_io_parts(packets[0]) if packets else ("method input", "", "")
        last_input, _last_operation, last_output = _plan_io_parts(packets[-1]) if packets else ("", "", "method output")
        sections.append(
            MethodPlanSection(
                section_id="PLAN-CORE-SUPPORTED-PATH",
                heading="Evidence-backed Method Path",
                purpose="Summarize the supported method path without promoting setup protocol into the main figure.",
                role="core",
                stage_ids=[str(packet.get("stage_id") or "") for packet in packets if str(packet.get("stage_id") or "")],
                mechanism_ids=_dedupe(
                    [
                        mechanism_id
                        for packet in packets
                        for mechanism_id in _clean_list(packet.get("primary_mechanism_ids"))
                    ]
                )[:8],
                evidence_span_ids=_dedupe(
                    [
                        evidence_id
                        for packet in packets
                        for evidence_id in _clean_list(packet.get("primary_evidence_ids"))
                    ]
                )[:20],
                input_operation_output=(
                    f"Input: {first_input or 'method input'}. Operation: organize the supported settings and training steps into a conservative method path. "
                    f"Output: {last_output or last_input or 'method output'}."
                ),
                input_representation=first_input or "method input",
                operation="organize the supported settings and training steps into a conservative method path",
                output_representation=last_output or last_input or "method output",
                figure_role="omit",
                priority=88,
                forbidden_details=["local paths", "script names", "CLI flags", "validation or testing protocol"],
            )
        )
    if _has_objective_evidence(method_evidence) and not any(
        "objective" in section.heading.lower() or "loss" in section.heading.lower() for section in sections
    ):
        sections.append(
            MethodPlanSection(
                section_id="PLAN-OBJECTIVE",
                heading="Reconstruction and Objective",
                purpose="Bind the prediction, reconstruction, and loss terms to concrete supervised quantities.",
                role="objective",
                input_operation_output=(
                    "Input: predicted or decoded method representation. Operation: bind supported loss terms to their concrete supervised targets. "
                    "Output: training objective used to optimize the method."
                ),
                input_representation="predicted or decoded method representation",
                operation="bind supported loss terms to concrete supervised targets",
                output_representation="training objective used to optimize the method",
                figure_role="optional",
                priority=84,
                required_equation_ids=[
                    equation.equation_id
                    for equation in plan_equations
                    if equation.source_family in {"prediction_loss", "reconstruction_loss", "set_distance", "total_objective"}
                ][:4],
                forbidden_details=["evaluation metrics", "checkpoint loading", "dataset split bookkeeping"],
            )
        )
    return MethodPlanOutput(
        method_family=_infer_method_family(method_evidence),
        overview_focus=_clean_goal(method_evidence.method_goal),
        baseline_problem="The evidence should identify the limitation or missing signal the method addresses.",
        method_response="Describe the supported representation transformation rather than runtime orchestration.",
        figure_module_names=aliases,
        sections=sections,
        equations=plan_equations,
        global_forbidden_details=[
            "absolute local paths",
            "script filenames",
            "CLI invocations",
            "validator or evidence-freeze process",
            "unsupported downstream claims",
        ],
        revision_checklist=[
            "Overview names the core contribution.",
            "Every core section states input, operation, and output.",
            "Objective names concrete prediction/reconstruction targets.",
            "Figure module names are used consistently when code-supported.",
            "Implementation leakage is rewritten rather than silently deleted.",
        ],
    )


def _section_equation_families(heading: str, purpose: str) -> set[str]:
    text = f"{heading} {purpose}".lower()
    families: set[str] = set()
    if any(token in text for token in ("group", "patch", "mask", "sample")):
        families.update({"grouping", "normalization", "partition"})
    if any(token in text for token in ("embed", "encoder", "encoding")):
        families.update({"embedding", "positional_module", "encoder"})
    if any(token in text for token in ("predict", "center", "condition")):
        families.update({"prediction", "attention_transfer", "stop_gradient"})
    if any(token in text for token in ("decode", "reconstruct", "objective", "loss", "train")):
        families.update({"decoder", "head", "prediction_loss", "reconstruction_loss", "set_distance", "total_objective"})
    return families


def _looks_like_objective_packet(packet: dict) -> bool:
    text = " ".join(
        [
            str(packet.get("name") or ""),
            str(packet.get("purpose") or ""),
            str(packet.get("stage_claim") or ""),
            " ".join(_clean_list(packet.get("key_operations"))),
        ]
    ).lower()
    return any(token in text for token in ("objective", "loss", "reconstruct", "decode", "prediction", "supervis"))


def _plan_io_contract(packet: dict) -> str:
    inputs, operation, outputs = _plan_io_parts(packet)
    return f"Input: {inputs}. Operation: {operation}. Output: {outputs}."


def _plan_io_parts(packet: dict) -> tuple[str, str, str]:
    inputs = _join_phrase(_clean_list(packet.get("inputs"))) or "the previous representation"
    outputs = _join_phrase(_clean_list(packet.get("outputs"))) or "the next method representation"
    purpose = str(packet.get("purpose") or "").strip()
    operation = purpose or "explain the supported transformation"
    return inputs, operation, outputs


def _plan_section_role(heading: str, purpose: str) -> str:
    text = f"{heading} {purpose}".lower()
    if any(token in text for token in ("objective", "loss", "criterion", "reconstruct")):
        return "objective"
    if any(token in text for token in ("evaluation", "validation", "testing", "benchmark", "metric", "voting", "fine-tune", "finetune", "downstream")):
        return "evaluation"
    if any(token in text for token in ("setup", "config", "entrypoint", "cli", "launch", "checkpoint")):
        return "setup"
    if any(token in text for token in ("dataset", "dataloader", "preprocess", "augment")):
        return "data"
    if any(token in text for token in ("transfer", "protocol", "report", "note")):
        return "supporting"
    return "core"


def _plan_figure_role(role: str, heading: str, purpose: str) -> str:
    text = f"{role} {heading} {purpose}".lower()
    if role in {"overview", "setup", "evaluation"}:
        return "omit"
    if any(token in text for token in ("entrypoint", "cli", "validation", "testing", "benchmark", "voting", "fine-tune", "finetune", "downstream")):
        return "omit"
    if role in {"supporting", "data", "objective"}:
        return "optional"
    return "include"


def _plan_priority(role: str, index: int) -> int:
    defaults = {
        "overview": 98,
        "core": 90,
        "objective": 84,
        "data": 64,
        "supporting": 45,
        "evaluation": 24,
        "setup": 14,
    }
    return max(0, defaults.get(role, 50) - index)


def _infer_method_family(method_evidence: MethodEvidence) -> str:
    text = " ".join(
        [
            method_evidence.method_name,
            method_evidence.method_goal,
            " ".join(stage.name + " " + stage.purpose for stage in method_evidence.stages),
            " ".join(mechanism.mechanism_name + " " + mechanism.mechanism_description for mechanism in method_evidence.frozen_mechanisms),
        ]
    ).lower()
    if "mask" in text and ("reconstruct" in text or "autoencoder" in text):
        return "masked autoencoder / self-supervised reconstruction"
    if "attention" in text:
        return "attention-based representation learning"
    return "implementation-grounded method"


def _method_plan_quality_report(method_plan: MethodPlanOutput) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    core_sections = [section for section in method_plan.sections if section.role in {"core", "objective"}]
    if not core_sections:
        issues.append(
            {
                "issue": "no_core_method_sections",
                "severity": "medium",
                "suggestion": "At least one section should be role=core or role=objective.",
            }
        )
    for section in method_plan.sections:
        text = f"{section.heading} {section.purpose} {section.operation}".lower()
        missing_io = [
            field
            for field, value in (
                ("input_representation", section.input_representation),
                ("operation", section.operation),
                ("output_representation", section.output_representation),
            )
            if not str(value or "").strip()
        ]
        if section.role in {"core", "objective"} and missing_io:
            issues.append(
                {
                    "issue": "core_section_missing_io_contract",
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "missing": missing_io,
                    "severity": "medium",
                    "suggestion": "Core method sections should state input, operation, and output explicitly.",
                }
            )
        if any(token in text for token in ("evaluation", "validation", "testing", "benchmark", "metric", "voting", "fine-tune", "finetune", "downstream")):
            if section.role == "core" or section.figure_role == "include":
                issues.append(
                    {
                        "issue": "protocol_section_promoted_to_core_or_figure",
                        "section_id": section.section_id,
                        "heading": section.heading,
                        "role": section.role,
                        "figure_role": section.figure_role,
                        "severity": "medium",
                        "suggestion": "Evaluation, transfer, and benchmark protocol should default to supporting text and stay out of the main method figure unless contribution-backed.",
                    }
                )
        if section.role == "objective" and not any(token in text for token in ("target", "loss", "objective", "prediction", "reconstruction", "supervis")):
            issues.append(
                {
                    "issue": "objective_missing_target_binding",
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "severity": "low",
                    "suggestion": "Objective sections should bind each loss to the supervised prediction or reconstruction target.",
                }
            )
        if section.role in {"setup", "evaluation"} and section.figure_role == "include":
            issues.append(
                {
                    "issue": "non_method_section_in_main_figure",
                    "section_id": section.section_id,
                    "heading": section.heading,
                    "severity": "low",
                    "suggestion": "Setup and evaluation protocol normally belong outside the main method figure.",
                }
            )
    score = max(0, 100 - 18 * sum(1 for issue in issues if issue.get("severity") == "medium") - 8 * sum(1 for issue in issues if issue.get("severity") == "low"))
    return {
        "passed": not issues,
        "score": score,
        "issue_count": len(issues),
        "issues": issues,
        "report_only": True,
    }


def _semantic_method_issues(markdown: str, method_plan: MethodPlanOutput) -> dict[str, object]:
    text = str(markdown or "")
    visible = re.sub(r"<!--\s*c2p:.*?-->", "", text, flags=re.DOTALL)
    lowered = visible.lower()
    issues: list[dict[str, object]] = []
    for sentence in re.split(r"(?<=[.!?])\s+", visible):
        stripped = sentence.strip()
        if not stripped:
            continue
        if _looks_like_implementation_leakage_sentence(stripped):
            issues.append(
                {
                    "issue": "implementation_leakage",
                    "sentence": stripped,
                    "suggestion": "Rewrite with a paper-facing method term instead of deleting the sentence.",
                }
            )
    headings = [heading.lower() for heading in re.findall(r"^\s{0,3}#{1,4}\s+(.+?)\s*$", visible, flags=re.MULTILINE)]
    for module_name in method_plan.figure_module_names:
        if module_name and module_name.lower() not in lowered:
            issues.append(
                {
                    "issue": "figure_text_name_mismatch",
                    "module": module_name,
                    "suggestion": "Use this code-supported figure/module name in the relevant Method section.",
                }
            )
    return {
        "passed": not issues,
        "issue_count": len(issues),
        "issues": issues[:80],
    }


def _revise_until_paper_ready(
    *,
    markdown: str,
    llm_config: LLMConfig,
    base_request: LLMRequest,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    grounding_context_markdown: str,
    equations_tex: str,
    symbols_tex: str,
    draft_claim_map: DraftClaimMap,
    method_plan: MethodPlanOutput,
    initial_call_logs: list[str],
    manifest_mode: str,
) -> tuple[str, list[str], str]:
    """Use the writing model to repair drafts that read like notes or audits."""

    call_logs = list(initial_call_logs)
    current = markdown
    max_rounds = max(0, int(os.environ.get("CODE2PAPER_PHASE5_PAPER_READY_REWRITE_ROUNDS", os.environ.get("CODE2PAPER_PHASE4_PAPER_READY_REWRITE_ROUNDS", "3")) or "3"))
    if max_rounds <= 0 or llm_config.provider == LLMProvider.NONE:
        return current, call_logs, manifest_mode

    for round_index in range(max_rounds):
        readiness = validate_paper_readiness(current)
        semantic_issues = _semantic_method_issues(current, method_plan)
        semantic_passed = bool(semantic_issues.get("passed"))
        if readiness.get("passed") and semantic_passed:
            return current, call_logs, manifest_mode if round_index == 0 else f"{manifest_mode}-paper-ready-revised"
        if int(readiness.get("high_issue_count", 0)) <= 0 and int(readiness.get("score", 0)) >= 78 and semantic_passed:
            return current, call_logs, manifest_mode if round_index == 0 else f"{manifest_mode}-paper-ready-revised"

        revision_request = LLMRequest(
            prompt_template_id=f"phase5_method_authoring_paper_ready_revision_v{round_index + 1}",
            prompt=_paper_readiness_revision_prompt(),
            input_payload={
                "original_authoring_request": base_request.input_payload,
                "current_markdown": current,
                "paper_readiness_report": readiness,
                "semantic_method_issues": semantic_issues,
                "method_plan": method_plan.model_dump(mode="json"),
                "method_evidence": method_evidence.model_dump(mode="json"),
                "claim_evidence_map": claim_map.model_dump(mode="json"),
                "grounding_context": grounding_context_markdown,
                "equations_tex": equations_tex,
                "symbols_tex": symbols_tex,
                "draft_claim_map": draft_claim_map.model_dump(mode="json"),
            },
            schema_name=METHOD_DRAFT_SCHEMA,
            response_json_schema=json_schema_for(DraftMarkdownOutput),
        )
        response = LLMClient(llm_config).complete(revision_request)
        if response.response_hash:
            call_logs.append(response.response_hash)
        if response.blocked_reason:
            break
        revised, _parse_error = try_parse_structured_response(response.text, DraftMarkdownOutput)
        if revised is None or not revised.markdown.strip():
            break
        revised_markdown = _augment_markdown_with_equation_chain(
            markdown=revised.markdown,
            equations_tex=equations_tex,
        )
        current = _normalize_markdown_grounding_comments(
            markdown=revised_markdown,
            draft_claim_map=draft_claim_map,
            method_evidence=method_evidence,
            claim_map=claim_map,
        )
        current = _maybe_compact_display_equations(current)
        current = _paper_prose_postprocess(current, method_evidence, equations_tex=equations_tex)
    return current, call_logs, f"{manifest_mode}-paper-ready-attempted"


def _repair_structural_readiness_if_needed(
    *,
    markdown: str,
    method_evidence: MethodEvidence,
    equations_tex: str,
) -> str:
    """Deterministically expand drafts that failed only because they are under-shaped."""

    readiness = validate_paper_readiness(markdown)
    if not _needs_structural_expansion(readiness):
        return markdown
    expanded = _force_structural_method_shape(
        markdown=markdown,
        method_evidence=method_evidence,
        equations_tex=equations_tex,
    )
    expanded = _paper_prose_postprocess(expanded, method_evidence, equations_tex=equations_tex)
    expanded_readiness = validate_paper_readiness(expanded)
    if int(expanded_readiness.get("score", 0) or 0) >= int(readiness.get("score", 0) or 0):
        return expanded
    return markdown


def _needs_structural_expansion(report: dict[str, object]) -> bool:
    issues = report.get("issues", []) if isinstance(report.get("issues"), list) else []
    high_ids = {
        str(issue.get("issue_id") or "")
        for issue in issues
        if isinstance(issue, dict) and str(issue.get("severity", "")).lower() == "high"
    }
    return bool(high_ids & {"PR1", "PR3", "PR5"})


def _force_structural_method_shape(
    *,
    markdown: str,
    method_evidence: MethodEvidence,
    equations_tex: str,
) -> str:
    packets = _stage_authoring_packets(method_evidence)
    aliases = [
        alias.alias
        for alias in method_evidence.paper_module_aliases
        if alias.alias and alias.evidence_span_ids
    ]
    alias_text = f" The named module {', '.join(_dedupe(aliases[:4]))} is preserved where its code support is explicit." if aliases else ""
    stage_summary = _stage_summary_sentence(packets)
    equations = _structural_equation_blocks(markdown=markdown, equations_tex=equations_tex, min_count=3, max_count=6)
    first_equations = equations[:2]
    objective_equations = equations[2:] if len(equations) > 2 else equations

    overview = (
        f"{_paper_method_name(method_evidence)} addresses {_lower_first(_clean_goal(method_evidence.method_goal))}. "
        f"{stage_summary}{alias_text} "
        f"{_overview_method_path_sentence(method_evidence, packets)} "
        "Each subsection therefore follows the same contract: it identifies the representation entering the stage, the operation applied by the supported module, and the representation exposed to the next stage. "
        "This makes the method readable as a single computational path rather than as a list of source-code artifacts. "
        "The section also separates method-defining choices from interchangeable training infrastructure, so the reader can distinguish the contribution from the surrounding execution environment. "
        "Routine runtime details such as launch commands, logging, and benchmark bookkeeping are outside the method pipeline itself."
    )

    sections = [
        "# Method",
        "## Overview",
        _grounding_for_packet(None, packets) + overview,
    ]

    body_packets, objective_packet = _select_structural_body_packets(packets)
    inserted_first_equations = False
    for index, packet in enumerate(body_packets):
        title = _paper_stage_name(str(packet.get("name") or "")) or f"Method Stage {index + 1}"
        if objective_packet is not None and packet is objective_packet:
            title = _objective_section_title(title)
            paragraph = _objective_paragraph(packet, method_evidence=method_evidence)
        else:
            paragraph = _stage_paragraph(
                packet,
                fallback_name=title,
                fallback_purpose=_generic_stage_fallback_purpose(index, len(body_packets)),
                emphasis="Describe the supported transformation in paper prose.",
            )
        sections.extend([f"## {title}", _grounding_for_packet(packet, packets) + paragraph])
        if index == 0 and first_equations:
            sections.extend(first_equations)
            inserted_first_equations = True

    if not body_packets:
        sections.extend(
            [
                "## Method Pipeline",
                _grounding_for_packet(None, packets)
                + _stage_paragraph(
                    None,
                    fallback_name="Method pipeline",
                    fallback_purpose="The method converts inputs into an intermediate representation and then optimizes the supported objective.",
                    emphasis="Describe the supported transformation in paper prose.",
                ),
            ]
        )
    if first_equations and not inserted_first_equations:
        sections.extend(first_equations)
    if objective_packet is None and _has_objective_evidence(method_evidence):
        sections.extend(
            [
                "## Objective",
                _grounding_for_packet(None, packets)
                + _objective_paragraph(
                    None,
                    method_evidence=method_evidence,
                ),
            ]
        )
    if objective_equations:
        sections.extend(objective_equations)
    return "\n\n".join(part.strip() for part in sections if str(part).strip()) + "\n"


def _select_structural_body_packets(packets: list[dict]) -> tuple[list[dict], dict | None]:
    supported = [
        packet
        for packet in packets
        if packet.get("primary_evidence_ids")
        or packet.get("module_actions")
        or packet.get("key_operations")
        or not _is_placeholder_stage_text(str(packet.get("purpose") or ""))
    ]
    if not supported:
        return [], None
    objective_packet = _best_packet(supported, ("objective", "loss", "optimiz", "reconstruct", "decode"))
    body: list[dict] = []
    for packet in supported:
        if packet not in body:
            body.append(packet)
    if objective_packet is not None and objective_packet not in body:
        body.append(objective_packet)
    return body[:6], objective_packet


def _objective_section_title(title: str) -> str:
    normalized = title.lower()
    if "objective" in normalized or "loss" in normalized:
        return title
    return f"{title} and Objective"


def _generic_stage_fallback_purpose(index: int, total: int) -> str:
    if index == 0:
        return "The method first converts the raw or previous input into the representation consumed by the core model."
    if index >= max(0, total - 1):
        return "The final method stage produces the evidence-backed representation or output used by the paper-facing method account."
    return "The stage transforms the intermediate representation and passes the result to the next method component."


def _overview_method_path_sentence(method_evidence: MethodEvidence, packets: list[dict]) -> str:
    if _has_objective_evidence(method_evidence) or _best_packet(packets, ("objective", "loss", "optimiz", "reconstruct", "decode")):
        return (
            "The method description is organized around the transformations applied to the representation: the input is converted into structured units, "
            "the visible context is encoded, and the evidence-backed objective or reconstruction terms are introduced only where the code support makes them explicit."
        )
    return (
        "The method description stays at the level supported by the available code evidence: it names the evidence-backed inputs, operations, and outputs without adding prediction, decoder, or loss components that are not present in the frozen evidence."
    )


def _has_objective_evidence(method_evidence: MethodEvidence) -> bool:
    objective_terms = ("objective", "loss", "optim", "reconstruct", "decode", "prediction")
    if method_evidence.equation_candidates:
        return True
    if _is_raw_evidence_fallback_method(method_evidence):
        return False
    return any(
        any(term in contract.claim_intent.lower() for term in objective_terms)
        for contract in method_evidence.claim_contracts
        if str(contract.support_status.value) != "unsupported"
    )


def _is_raw_evidence_fallback_method(method_evidence: MethodEvidence) -> bool:
    if len(method_evidence.stages) != 1:
        return False
    stage = method_evidence.stages[0]
    if _normalize_story_name(stage.name) != "implementation evidence":
        return False
    if stage.modules or method_evidence.behavior_patterns:
        return False
    mechanism_descriptions = [
        mechanism.description
        for mechanism in stage.mechanisms
        if mechanism.description.strip()
    ]
    return bool(mechanism_descriptions) and all(
        description.lower().startswith("hard implementation evidence covers")
        for description in mechanism_descriptions
    )


def _stage_summary_sentence(packets: list[dict]) -> str:
    names = [_paper_stage_name(str(packet.get("name") or "").strip()) for packet in packets if str(packet.get("name") or "").strip()]
    names = [name for name in names if name]
    if not names:
        return "The available evidence supports a sequence of method stages from representation construction through objective optimization."
    return "The supported flow contains " + ", ".join(names[:5]) + "."


def _best_packet(packets: list[dict], keywords: tuple[str, ...]) -> dict | None:
    best = None
    best_score = -1
    for packet in packets:
        name_text = str(packet.get("name") or "").lower()
        text = " ".join(
            [
                str(packet.get("name") or ""),
                str(packet.get("purpose") or ""),
                str(packet.get("stage_claim") or ""),
                " ".join(str(item) for item in packet.get("key_operations", []) if str(item).strip()),
                " ".join(
                    " ".join([str(action.get("name") or ""), str(action.get("role") or ""), str(action.get("key_logic") or "")])
                    for action in packet.get("module_actions", [])
                    if isinstance(action, dict)
                ),
            ]
        ).lower()
        score = sum(text.count(keyword) for keyword in keywords) + 3 * sum(name_text.count(keyword) for keyword in keywords)
        if score > best_score:
            best = packet
            best_score = score
    return best if best_score > 0 else None


def _stage_paragraph(packet: dict | None, *, fallback_name: str, fallback_purpose: str, emphasis: str) -> str:
    if not packet:
        return (
            f"{fallback_name} begins from the representation produced by the previous stage. {fallback_purpose} "
            "Because no narrower implementation packet is available, the description remains conservative and focuses on the supported input/output transformation. "
            "The subsection therefore names the algorithmic role of the stage, explains how information is carried forward, and avoids turning runtime helpers into method contributions. "
            "This keeps the method narrative complete while leaving unsupported implementation details out of the paper-facing account."
        )
    name = _paper_stage_name(str(packet.get("name") or fallback_name).strip()) or fallback_name
    raw_purpose = str(packet.get("purpose") or "").strip()
    purpose = fallback_purpose if _is_placeholder_stage_text(raw_purpose) else raw_purpose or fallback_purpose
    module_actions = [action for action in packet.get("module_actions", []) if isinstance(action, dict)]
    raw_mechanisms = (packet.get("frozen_mechanisms") or []) + (packet.get("mechanisms") or [])
    if _is_placeholder_stage_text(raw_purpose) and not module_actions and _only_generic_mechanisms(raw_mechanisms):
        return _stage_paragraph(
            None,
            fallback_name=fallback_name,
            fallback_purpose=fallback_purpose,
            emphasis=emphasis,
        )
    inputs = _clean_list(packet.get("inputs"))
    outputs = _clean_list(packet.get("outputs"))
    module_fragments = _module_action_fragments(module_actions)
    mechanisms = [
        str(mechanism.get("description") or mechanism.get("name") or "").strip()
        for mechanism in raw_mechanisms
        if isinstance(mechanism, dict)
    ]
    if not mechanisms:
        mechanisms = _clean_list(packet.get("key_operations"))
    mechanisms = [
        item
        for item in mechanisms
        if item
        and not _is_generic_stage_mechanism(item)
        and _normalize_story_name(item) != _normalize_story_name(purpose)
    ]
    io_sentence = ""
    if inputs or outputs:
        io_sentence = f" It consumes {_join_phrase(inputs) or 'the previous representation'} and produces {_join_phrase(outputs) or 'the transformed representation'}."
    module_sentence = ""
    if module_fragments:
        module_sentence = " " + " ".join(module_fragments[:3])
    mechanism_sentence = f" The main operations are {_join_phrase([_lower_first(item) for item in mechanisms[:4]])}." if mechanisms else ""
    transition_sentence = (
        "This transformation is presented as part of the main method path because it defines an evidence-backed input, operation, or output used by the method narrative."
    )
    representation_sentence = (
        "The subsection keeps the notation tied to the stage outputs so the following stage can be read as a continuation of the same computational graph rather than as an independent implementation detail."
    )
    method_sentence = (
        "When several helper operations support the same transformation, the prose groups them by their algorithmic effect instead of exposing low-level orchestration."
    )
    return " ".join(
        part.strip()
        for part in [
            _stage_opening_sentence(name, purpose),
            io_sentence,
            module_sentence,
            mechanism_sentence,
            transition_sentence,
            representation_sentence,
            method_sentence,
        ]
        if part and part.strip()
    )


def _objective_paragraph(packet: dict | None, *, method_evidence: MethodEvidence) -> str:
    stage_text = _stage_paragraph(
        packet,
        fallback_name="Reconstruction and objective",
        fallback_purpose=(
            "The decoder uses the predicted conditioning signal to reconstruct the held-out target, and training combines the reconstruction term with the supported prediction term."
        ),
        emphasis=(
            "The objective identifies the supervised quantities, the reconstructed output, and the way the available loss terms are combined."
        ),
    )
    contracts = [
        contract.claim_intent
        for contract in method_evidence.claim_contracts
        if str(contract.support_status.value) != "unsupported" and any(token in contract.claim_intent.lower() for token in ("loss", "objective", "reconstruct", "prediction"))
    ]
    if contracts:
        return stage_text + " The loss terms are introduced only when they are supported by the frozen claim contracts, with reconstruction and prediction targets kept separate before the final objective is stated. This keeps auxiliary supervision distinct from the main output criterion while still showing how the training signal binds the pipeline together."
    return stage_text + " The objective is stated as the training signal that links the predicted representation to the final reconstructed or task-level output. The paragraph emphasizes what quantity is supervised, what prediction or reconstruction it is compared against, and how this supervision feeds back into the modules described above."


def _grounding_for_packet(packet: dict | None, packets: list[dict]) -> str:
    evidence_ids: list[str] = []
    stage_id = "ALL"
    if packet:
        stage_id = str(packet.get("stage_id") or "S")
        evidence_ids = _clean_list(packet.get("primary_evidence_ids"))[:8]
    else:
        mechanism_ids = _dedupe(
            [
                mechanism_id
                for item in packets
                for mechanism_id in _clean_list(item.get("primary_mechanism_ids"))
            ]
        )[:8]
        evidence_ids = _dedupe([eid for item in packets for eid in _clean_list(item.get("primary_evidence_ids"))])[:8]
    if packet:
        mechanism_ids = _clean_list(packet.get("primary_mechanism_ids"))[:8]
    if not evidence_ids or not mechanism_ids:
        return ""
    return f"<!-- c2p: stage={stage_id}; mechanisms={','.join(mechanism_ids)}; evidence={','.join(evidence_ids)}; confidence=medium -->\n"


def _structural_equation_blocks(*, markdown: str, equations_tex: str, min_count: int, max_count: int) -> list[str]:
    equations = _extract_markdown_display_equations(markdown) + _extract_equation_tex_blocks(equations_tex)
    deduped: list[str] = []
    seen: set[str] = set()
    for equation in equations:
        normalized = _normalize_equation_text(equation)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(equation.strip())
    deduped.sort(key=_display_equation_priority)
    selected = deduped[:max_count]
    if len(selected) < min_count:
        selected = deduped[: min(max_count, len(deduped))]
    return [f"$$\n{equation}\n$$" for equation in selected]


def _clean_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def _join_phrase(items: list[str]) -> str:
    clean = _dedupe([_strip_audit_prefix(item) for item in items if str(item).strip()])
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    if len(clean) == 2:
        return f"{clean[0]} and {clean[1]}"
    return ", ".join(clean[:-1]) + f", and {clean[-1]}"


def _strip_audit_prefix(text: str) -> str:
    return re.sub(r"^(mechanism|stage|module)\s*[:\-]\s*", "", str(text or "").strip(), flags=re.IGNORECASE)


def _rstrip_period(text: str) -> str:
    return str(text or "").strip().rstrip(".")


def _lower_first(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return ""
    return stripped[:1].lower() + stripped[1:]


def _paper_method_name(method_evidence: MethodEvidence) -> str:
    name = str(method_evidence.method_name or "").strip()
    goal = str(method_evidence.method_goal or "").strip()
    goal_match = re.search(r"\bDescribe\s+([A-Za-z0-9][A-Za-z0-9_\-+ ]{1,80}?)\s+as\b", goal)
    if goal_match:
        return goal_match.group(1).strip()
    if name.lower().endswith(" method pipeline"):
        name = name[: -len(" method pipeline")].strip()
    return name or "The method"


def _clean_goal(goal: str) -> str:
    text = str(goal or "").strip().rstrip(".")
    text = re.sub(r"^Describe\s+[^.]*?\s+as\s+", "", text, flags=re.IGNORECASE)
    if not text:
        return "the target method behavior"
    return text


def _paper_stage_name(name: str) -> str:
    text = str(name or "").strip().rstrip(".")
    if ":" in text:
        prefix, detail = text.split(":", 1)
        prefix = prefix.strip()
        detail = detail.strip()
        if prefix and len(prefix.split()) <= 6:
            return prefix
        return _sentence_to_short_title(detail)
    return _sentence_to_short_title(text)


def _sentence_to_short_title(text: str) -> str:
    text = str(text or "").strip().rstrip(".")
    text = re.sub(r"^(describe|explain|briefly state|state|represent)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(as|the|a|an)\s+(paper-facing|method)\s+(stage|module)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return ""
    if len(text.split()) > 8:
        text = " ".join(text.split()[:8])
    return text[:1].upper() + text[1:]


def _is_placeholder_stage_text(text: str) -> bool:
    normalized = str(text or "").lower()
    return (
        "represent the paper-facing stage named" in normalized
        or "author marker method stage" in normalized
        or normalized.strip() in {"", "unspecified"}
    )


def _only_generic_mechanisms(mechanisms: object) -> bool:
    if not isinstance(mechanisms, list) or not mechanisms:
        return True
    descriptions = [
        str(mechanism.get("description") or mechanism.get("name") or "").strip()
        for mechanism in mechanisms
        if isinstance(mechanism, dict)
    ]
    return not descriptions or all(_is_generic_stage_mechanism(text) for text in descriptions)


def _is_generic_stage_mechanism(text: str) -> bool:
    normalized = _normalize_story_name(text)
    return normalized in {
        "this stage performs the core representation transformation that drives the method behavior",
        "this stage executes an evidence backed method transformation in the pipeline",
    }


def _stage_opening_sentence(name: str, purpose: str) -> str:
    clean_name = _rstrip_period(name)
    clean_purpose = _paper_facing_stage_purpose(purpose)
    if not clean_purpose:
        return f"{clean_name} carries the method representation forward."
    return f"The {clean_name.lower()} step defines an evidence-backed method operation: {_lower_first(clean_purpose)}."


def _paper_facing_stage_purpose(purpose: str) -> str:
    text = _rstrip_period(purpose)
    replacements = [
        (r"\bbase config\b", "base settings"),
        (r"\blauncher overrides\b", "method-level overrides"),
        (r"\btraining entrypoint\b", "training path"),
        (r"\bentrypoint\b", "method path"),
        (r"\blauncher\b", "method controller"),
        (r"\bLaunch\b", "Activate"),
        (r"\blaunch\b", "activate"),
        (r"\bCLI\b", "interface"),
        (r"\bcommand line\b", "interface"),
        (r"\bscript\b", "procedure"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text.strip()


def _module_action_fragments(actions: list[dict]) -> list[str]:
    fragments: list[str] = []
    for action in actions:
        name = _clean_component_label(str(action.get("name") or ""))
        role = _rstrip_period(str(action.get("role") or "").strip())
        logic = _rstrip_period(str(action.get("key_logic") or "").strip())
        if role and name:
            fragments.append(f"{name} serves as the {_lower_first(role)}.")
        elif role:
            fragments.append(role + ".")
        if logic and name:
            if _normalize_story_name(logic).startswith(_normalize_story_name(name)):
                fragments.append(logic + ".")
            else:
                fragments.append(f"{name} { _lower_first(logic) }.")
        elif logic:
            fragments.append(logic + ".")
    return [_clean_sentence_fragment(fragment) for fragment in fragments if _clean_sentence_fragment(fragment)]


def _clean_component_label(text: str) -> str:
    label = str(text or "").strip()
    label = label.replace("_", " ")
    return label


def _clean_sentence_fragment(text: str) -> str:
    cleaned = re.sub(r"`([^`]+)`", lambda match: match.group(1).replace("_", " "), str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:]


def _paper_prose_postprocess(
    markdown: str,
    method_evidence: MethodEvidence,
    *,
    equations_tex: str = "",
    destructive_cleanup: bool = False,
) -> str:
    text = _sanitize_paper_audit_vocabulary(markdown)
    text = _sanitize_inline_code_spans(text)
    text = _remove_audit_style_blocks(text)
    text = _remove_unselected_helper_equations(text, equations_tex)
    text = _remove_helper_equations_when_core_present(text)
    if destructive_cleanup:
        text = _remove_low_priority_implementation_sentences(text)
        text = _remove_implementation_leakage_sentences(text)
    text = _remove_empty_markdown_sections(text)
    readiness = validate_paper_readiness(text)
    if any(
        isinstance(issue, dict) and issue.get("issue_id") == "PR7" and issue.get("severity") == "high"
        for issue in readiness.get("issues", [])
        if isinstance(issue, dict)
    ):
        metrics = readiness.get("metrics", {}) if isinstance(readiness.get("metrics"), dict) else {}
        equation_budget = int(metrics.get("adaptive_equation_budget", 8) or 8)
        text = _compact_display_equations(text, max_equations=equation_budget)
    text = _remove_dangling_helper_introductions(text)
    text = _clean_orphan_equation_explanations(text)
    text = _remove_empty_markdown_sections(text)
    text = _ensure_overview_subsection(text, method_evidence)
    text = _ensure_grounding_before_content_blocks(text)
    text = _finalize_internal_method_markdown(text)
    return text.strip() + "\n"


def _finalize_internal_method_markdown(markdown: str) -> str:
    """Deterministic final cleanup for the evidence-bearing internal draft."""

    text = _repair_mojibake_punctuation(str(markdown or ""))
    text = _move_grounding_comments_before_equation_explanations(text)
    text = _remove_context_incompatible_helper_equation_section(text)
    text = _soften_transfer_and_performance_claims(text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip() + "\n"


def _build_clean_method_markdown(markdown: str) -> str:
    """Build the paper-facing Method markdown without internal grounding comments."""

    text = _strip_grounding_comments(markdown)
    text = _repair_mojibake_punctuation(text)
    text = _soften_transfer_and_performance_claims(text)
    text = _clean_orphan_equation_explanations(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _strip_grounding_comments(markdown: str) -> str:
    return re.sub(r"<!--\s*c2p:.*?-->\s*\n?", "", str(markdown or ""), flags=re.DOTALL)


def _repair_mojibake_punctuation(markdown: str) -> str:
    text = str(markdown or "")
    replacements = {
        "鈥?": "-",
        "鈥搕": "-t",
        "鈥搕ile": "-tile",
        "鈥擵": "V",
        "鈥攖": " t",
        "鈥攁": " a",
        "鈥攑": " p",
        "鈥": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = text.replace("每", "-")
    text = re.sub(r"\s+每\s+", " - ", text)
    text = re.sub(r"(?<=\))\s*每\s*", " - ", text)
    text = re.sub(r"\s+-\s+", " - ", text)
    return text


def _move_grounding_comments_before_equation_explanations(markdown: str) -> str:
    """Keep c2p comments before equations, not between equations and their explanations."""

    pattern = re.compile(
        r"(?P<eq>\$\$\s*.*?\s*\$\$)"
        r"(?P<gap>[ \t]*(?:\r?\n)+)"
        r"(?P<comment><!--\s*c2p:.*?-->)"
        r"(?P<after>[ \t]*(?:\r?\n)+(?=(?:where|Here|here|In this expression|This equation)\b))",
        flags=re.DOTALL,
    )

    def replace(match: re.Match[str]) -> str:
        before = markdown[: match.start()]
        previous_block = before.rstrip().split("\n")[-1] if before.rstrip() else ""
        comment = match.group("comment").strip()
        eq = match.group("eq").strip()
        if previous_block.strip().startswith("<!-- c2p:"):
            return eq + match.group("gap") + match.group("after")
        return comment + "\n" + eq + match.group("gap") + match.group("after")

    previous = None
    text = str(markdown or "")
    while previous != text:
        previous = text
        text = pattern.sub(replace, text)
    text = re.sub(
        r"(<!--\s*c2p:.*?-->\s*){2,}(?=\$\$)",
        lambda match: re.findall(r"<!--\s*c2p:.*?-->", match.group(0), flags=re.DOTALL)[-1] + "\n",
        text,
        flags=re.DOTALL,
    )
    return text


def _remove_context_incompatible_helper_equation_section(markdown: str) -> str:
    """Remove generic helper equations appended to drafts for a different method family."""

    text = str(markdown or "")
    heading_match = re.search(r"(?im)^\s*#{2,4}\s+Training Objective\s*$", text)
    if not heading_match:
        return text
    section = text[heading_match.start():]
    before = text[: heading_match.start()].rstrip()
    equations = _extract_markdown_display_equations(section)
    if not equations:
        return text
    families = {_equation_family(equation) for equation in equations if _equation_family(equation)}
    helper_families = {"grouping", "prediction", "stop_gradient", "decoder", "head", "embedding", "encoder"}
    core_families = {
        "task_loss",
        "regularization_loss",
        "prediction_loss",
        "reconstruction_loss",
        "set_distance",
        "total_objective",
        "photometric_loss",
        "view_error_mask",
    }
    context = _strip_grounding_comments(before).lower()
    helper_context_terms = ("predictor", "decoder", "masked autoencoder", "token", "latent", "embedding")
    if families and families <= helper_families and not any(term in context for term in helper_context_terms):
        return before.strip() + "\n"
    if families and not families.intersection(core_families) and len(equations) >= 3:
        return before.strip() + "\n"
    return text


def _soften_transfer_and_performance_claims(markdown: str) -> str:
    """Downgrade unsupported transfer/performance phrasing in method prose."""

    text = str(markdown or "")
    replacements = [
        (
            r"(?i)\bhighly robust and generalize well to unseen data\b",
            "intended to provide transferable representations for downstream tasks",
        ),
        (
            r"(?i)\blearns more robust and transferable representations\b",
            "is intended to encourage representations that can be reused downstream",
        ),
        (
            r"(?i)\bachieves state-of-the-art\b",
            "is designed to improve",
        ),
        (
            r"(?i)\bsignificantly outperforms\b",
            "is designed to compare favorably with",
        ),
        (
            r"(?i)\bachieves high-quality ([^.]*?) with drastically reduced training time\b",
            r"is designed to preserve \1 while reducing training time",
        ),
        (
            r"(?i)\bachieve rapid training convergence while maintaining state-of-the-art rendering quality\b",
            "support faster training while preserving rendering quality",
        ),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    def soften_sentence(match: re.Match[str]) -> str:
        sentence = match.group(0)
        lowered = sentence.lower()
        if not any(term in lowered for term in ("downstream", "transfer", "classification", "segmentation", "unseen")):
            return sentence
        if not any(term in lowered for term in ("robust", "generalize", "superior", "state-of-the-art", "outperform", "improves", "better", "highly")):
            return sentence
        softened = re.sub(r"(?i)\bhighly\s+", "", sentence)
        softened = re.sub(r"(?i)\bgeneralize[s]?\s+well\b", "is intended to transfer", softened)
        softened = re.sub(r"(?i)\bimproves?\b", "is intended to support", softened)
        softened = re.sub(r"(?i)\bbetter\b", "more reusable", softened)
        softened = re.sub(r"(?i)\bsuperior\b", "usable", softened)
        softened = re.sub(r"(?i)\bstate-of-the-art\b", "competitive", softened)
        softened = re.sub(r"(?i)\boutperforms?\b", "is evaluated against", softened)
        return softened

    return re.sub(r"[^.\n]*\b(?:downstream|transfer|classification|segmentation|unseen)\b[^.\n]*\.", soften_sentence, text, flags=re.IGNORECASE)


def _ensure_grounding_before_content_blocks(markdown: str) -> str:
    """Keep paragraph-level grounding intact after prose/equation cleanup."""

    blocks = re.split(r"(\n\s*\n)", str(markdown or ""))
    result: list[str] = []
    last_grounding = ""
    pending_grounding = False
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            result.append(block)
            continue
        if re.fullmatch(r"(?:<!--\s*c2p:.*?-->\s*)+", stripped, flags=re.DOTALL):
            comments = re.findall(r"<!--\s*c2p:.*?-->", stripped, flags=re.DOTALL)
            if comments:
                last_grounding = comments[-1].strip()
                pending_grounding = True
                result.append(block)
            continue
        if stripped.startswith("#"):
            pending_grounding = False
            result.append(block)
            continue
        if stripped.startswith("<!--"):
            comments = re.findall(r"<!--\s*c2p:.*?-->", block, flags=re.DOTALL)
            if comments:
                last_grounding = comments[-1].strip()
                pending_grounding = True
        if _is_markdown_paragraph_line(stripped) or _paragraph_display_equation(stripped):
            if last_grounding and not pending_grounding and not stripped.startswith("<!--"):
                result.append(last_grounding + "\n")
            pending_grounding = False
        result.append(block)
    cleaned = "".join(result)
    cleaned = re.sub(r"(<!--\s*c2p:.*?-->\s*){4,}", lambda m: "\n".join(re.findall(r"<!--\s*c2p:.*?-->", m.group(0))[-1:]) + "\n", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _remove_audit_style_blocks(markdown: str) -> str:
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    keep = [True] * len(paragraphs)
    audit_patterns = (
        r"(?i)^#+\s+code-backed mechanism details\b",
        r"(?i)^#+\s+method procedure\b",
        r"(?i)^#+\s+evidence-grounded pipeline\b",
        r"(?i)^\*\*submech\d+\.",
        r"(?i)^equation candidate\b",
        r"(?i)^generated from a recognized code pattern\b",
        r"(?i)^\*\*grounded objective fragment\s+\d+\.",
        r"(?i)^\*\*code-supported relation\.",
    )
    for index, part in enumerate(paragraphs):
        stripped = re.sub(r"<!--\s*c2p:.*?-->", "", part, flags=re.DOTALL).strip()
        if any(re.search(pattern, stripped) for pattern in audit_patterns):
            keep[index] = False
            following = _next_content_index(paragraphs, index)
            if following is not None and paragraphs[following].strip().startswith("$$"):
                keep[following] = False
                after_equation = _next_content_index(paragraphs, following)
                if after_equation is not None and _explains_removed_equation(paragraphs[after_equation]):
                    keep[after_equation] = False
    cleaned = "".join(part for part, should_keep in zip(paragraphs, keep) if should_keep)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _remove_helper_equations_when_core_present(markdown: str) -> str:
    """Remove helper-only formulas once the draft already contains core method equations."""

    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    equation_indices = [
        index
        for index, part in enumerate(paragraphs)
        if _paragraph_display_equation(part)
    ]
    core_count = sum(
        1
        for index in equation_indices
        if not _is_helper_display_equation(_paragraph_display_equation(paragraphs[index]) or "")
    )
    if core_count < 3:
        return markdown
    keep = [True] * len(paragraphs)
    for index in equation_indices:
        equation = _paragraph_display_equation(paragraphs[index]) or ""
        if not _is_helper_display_equation(equation):
            continue
        keep[index] = False
        previous = _previous_content_index(paragraphs, index)
        if previous is not None and _introduces_helper_equation(paragraphs[previous]):
            keep[previous] = False
        following = _next_content_index(paragraphs, index)
        if following is not None and _explains_removed_equation(paragraphs[following]):
            keep[following] = False
    cleaned = "".join(part for part, should_keep in zip(paragraphs, keep) if should_keep)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _paragraph_display_equation(paragraph: str) -> str:
    stripped = re.sub(r"<!--\s*c2p:.*?-->", "", str(paragraph or ""), flags=re.DOTALL).strip()
    if not stripped.startswith("$$") or not stripped.endswith("$$"):
        return ""
    return stripped.strip("$").strip()


def _sanitize_paper_audit_vocabulary(markdown: str) -> str:
    text = str(markdown or "")
    replacements = {
        "conservatively stated by discovered evidence,": "",
        "conservatively stated by implementation evidence,": "",
        "conservatively stated by discovered evidence": "",
        "conservatively stated by implementation evidence": "",
        "evidence-backed stages": "method stages",
        "evidence-backed stage": "method stage",
        "evidence-backed mechanisms": "implementation-grounded mechanisms",
        "evidence-backed mechanism": "implementation-grounded mechanism",
        "evidence-backed": "implementation-grounded",
        "partially supported": "conservatively stated",
        "partially-supported": "conservatively stated",
    }
    for source, target in replacements.items():
        text = re.sub(re.escape(source), target, text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def _sanitize_inline_code_spans(markdown: str) -> str:
    """Paper prose should name concepts, not render implementation identifiers as code."""

    def replace(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        if not content:
            return ""
        if _IMPLEMENTATION_LEAKAGE_RE.search(content):
            return content
        return content.replace("_", " ")

    return re.sub(r"`([^`\n]+)`", replace, str(markdown or ""))


def _ensure_overview_subsection(markdown: str, method_evidence: MethodEvidence) -> str:
    text = str(markdown or "").strip()
    headings = [heading.strip() for heading in re.findall(r"^\s{0,3}#{1,4}\s+(.+?)\s*$", text, flags=re.MULTILINE)]
    if any("overview" in heading.lower() or "framework" in heading.lower() for heading in headings):
        return text

    all_mechanisms = [mechanism for stage in method_evidence.stages for mechanism in stage.mechanisms]
    mechanism_ids = _dedupe([mechanism.mechanism_id for mechanism in all_mechanisms])
    evidence_ids = _dedupe([evidence_id for mechanism in all_mechanisms for evidence_id in mechanism.evidence_ids])
    confidence = "high" if evidence_ids else "medium"
    stage_names = [stage.name for stage in method_evidence.stages if stage.name]
    stage_sentence = ""
    if stage_names:
        stage_sentence = " It proceeds through " + _join_for_sentence(stage_names[:6]) + "."
    goal = str(method_evidence.method_goal or "").strip().rstrip(".")
    if goal:
        overview_sentence = f"{method_evidence.method_name} targets {goal[0].lower() + goal[1:]}."
    else:
        overview_sentence = f"{method_evidence.method_name} defines the method pipeline summarized in this section."
    overview = "\n".join(
        [
            "## Method Overview",
            "",
            grounding_comment(
                stage_id="ALL",
                mechanism_ids=mechanism_ids,
                evidence_ids=evidence_ids,
                confidence=confidence,
            ),
            overview_sentence + stage_sentence,
            "",
        ]
    )
    method_heading = re.match(r"^\s*#\s+Method\s*$", text, flags=re.MULTILINE)
    if method_heading:
        insert_at = method_heading.end()
        return text[:insert_at].rstrip() + "\n\n" + overview + text[insert_at:].lstrip()
    return overview + text


def _remove_unselected_helper_equations(markdown: str, equations_tex: str) -> str:
    selected = {_normalize_equation_text(equation) for equation in _extract_equation_tex_blocks(equations_tex)}
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    keep = [True] * len(paragraphs)
    for index, part in enumerate(paragraphs):
        stripped = part.strip()
        if not stripped.startswith("$$") or not stripped.endswith("$$"):
            continue
        equation = stripped.strip("$").strip()
        normalized = _normalize_equation_text(equation)
        if normalized in selected or not _is_helper_display_equation(equation):
            continue
        keep[index] = False
        previous = _previous_content_index(paragraphs, index)
        if previous is not None and _introduces_helper_equation(paragraphs[previous]):
            keep[previous] = False
        following = _next_content_index(paragraphs, index)
        if following is not None and _explains_removed_equation(paragraphs[following]):
            keep[following] = False
    cleaned = "".join(part for part, should_keep in zip(paragraphs, keep) if should_keep)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _remove_dangling_helper_introductions(markdown: str) -> str:
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    keep = [True] * len(paragraphs)
    for index, part in enumerate(paragraphs):
        stripped = re.sub(r"<!--\s*c2p:.*?-->", "", part, flags=re.DOTALL).strip()
        lowered = stripped.lower()
        if not stripped.endswith(":"):
            continue
        if any(term in lowered for term in ("positional encoding", "sinusoidal", "feed-forward", "attention kernel")):
            keep[index] = False
    cleaned = "".join(part for part, should_keep in zip(paragraphs, keep) if should_keep)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _is_helper_display_equation(equation: str) -> bool:
    lowered = _normalize_equation_text(equation).lower()
    helper_terms = (
        "\\mathrm{pe}_{",
        "\\mathrm{pe}_{(pos",
        "\\operatorname{pe}(",
        "\\mathrm{ffn}",
        "h_q=\\mathrm{softmax}",
        "softmax(qk",
        "softmax(qk_c",
        "softmax(qk_c^t",
        "softmax(qk^t",
        "softmax(qk",
        "\\operatorname{attention}(q,k,v)",
        "\\operatorname{attn}(q,k,v)",
        "\\mathrm{attention}(q,k,v)",
        "\\mathrm{multibranch}",
    )
    return any(term in lowered for term in helper_terms)


def _remove_low_priority_implementation_sentences(markdown: str) -> str:
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    cleaned_parts: list[str] = []
    for part in paragraphs:
        if not part.strip() or part.strip().startswith("#") or part.strip().startswith("$$"):
            cleaned_parts.append(part)
            continue
        visible = re.sub(r"<!--\s*c2p:.*?-->", "", part, flags=re.DOTALL)
        if not visible.strip():
            cleaned_parts.append(part)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", visible.strip())
        kept: list[str] = []
        for sentence in sentences:
            lowered = sentence.lower()
            low_priority = any(
                term in lowered
                for term in (
                    "parsing configuration",
                    "parsing configurations",
                    "building datasets",
                    "building datasets and models",
                    "deciding the task mode",
                    "experimental setup begins",
                    "global entrypoint",
                    "entrypoint",
                    "regularization techniques, such as dropout",
                    "dropout",
                    "pointwise transformations",
                    "representation injection",
                    "checkpoint",
                    "logger",
                    "ddp",
                    "voting mechanism",
                    "validation",
                    "performance metrics",
                    "accuracy and intersection over union",
                    "intersection over union",
                    "iou score",
                    "iou scores",
                    "transfer protocol",
                    "downstream tasks",
                    "downstream transfer tasks",
                    "downstream applications",
                    "fine-tuned",
                    "finetuning",
                    "fine tuning",
                    "evaluated on standard",
                    "evaluation flow",
                    "parameter overhead",
                    "representation and projection components",
                )
            ) or _looks_like_experiment_protocol_sentence(lowered)
            if low_priority:
                continue
            kept.append(sentence)
        if kept:
            comments = re.findall(r"<!--\s*c2p:.*?-->", part, flags=re.DOTALL)
            prefix = ("\n".join(comment.strip() for comment in comments) + "\n") if comments else ""
            cleaned_parts.append(prefix + " ".join(kept))
    cleaned = "".join(cleaned_parts)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _remove_implementation_leakage_sentences(markdown: str) -> str:
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    cleaned_parts: list[str] = []
    for part in paragraphs:
        stripped = part.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("$$"):
            cleaned_parts.append(part)
            continue
        visible = re.sub(r"<!--\s*c2p:.*?-->", "", part, flags=re.DOTALL)
        if not visible.strip():
            cleaned_parts.append(part)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", visible.strip())
        kept = [
            sentence
            for sentence in sentences
            if sentence.strip() and not _looks_like_implementation_leakage_sentence(sentence)
        ]
        if kept:
            comments = re.findall(r"<!--\s*c2p:.*?-->", part, flags=re.DOTALL)
            prefix = ("\n".join(comment.strip() for comment in comments) + "\n") if comments else ""
            cleaned_parts.append(prefix + " ".join(kept))
    cleaned = "".join(cleaned_parts)
    cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned)
    return cleaned.strip() + "\n"


def _looks_like_implementation_leakage_sentence(sentence: str) -> bool:
    text = str(sentence or "")
    if not text.strip():
        return False
    return bool(_IMPLEMENTATION_LEAKAGE_RE.search(text))


def _looks_like_experiment_protocol_sentence(lowered_sentence: str) -> bool:
    """Detect evaluation/setup protocol text that should not dominate a Method section."""

    sentence = str(lowered_sentence or "")
    if not sentence:
        return False
    hard_protocol_terms = (
        "downstream classification",
        "downstream segmentation",
        "downstream transfer",
        "fine-tuning",
        "fine-tuned",
        "finetuning",
        "evaluation",
        "evaluated",
        "target dataset",
        "pretrained weights initialize",
        "pre-trained weights initialize",
    )
    if any(term in sentence for term in hard_protocol_terms):
        return True
    protocol_terms = (
        "validation",
        "testing",
        "performance metric",
        "accuracy",
        "intersection over union",
        "iou",
        "voting",
        "vote",
        "fine-tune",
        "finetune",
        "fine tune",
        "downstream classification",
        "downstream segmentation",
        "target dataset",
        "downstream dataset",
        "downstream datasets",
        "fine-tuning",
        "fine-tuned",
        "fine tuning",
        "transfer protocol",
        "downstream task",
        "downstream tasks",
        "downstream application",
        "downstream applications",
        "standard metric",
        "standard metrics",
        "evaluated on standard",
    )
    contribution_terms = (
        "loss",
        "objective",
        "head",
        "module",
        "decoder",
        "encoder",
        "prediction",
        "reconstruction",
        "alignment",
        "fusion",
    )
    return any(term in sentence for term in protocol_terms) and not any(
        term in sentence for term in contribution_terms
    )


def _remove_empty_markdown_sections(markdown: str) -> str:
    """Drop headings whose entire content was removed by prose cleanup."""

    lines = str(markdown or "").splitlines()
    if not lines:
        return ""
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    remove_line_indices: set[int] = set()
    heading_indices = [index for index, line in enumerate(lines) if heading_re.match(line.strip())]
    for pos, start in enumerate(heading_indices):
        match = heading_re.match(lines[start].strip())
        if match and len(match.group(1)) == 1:
            continue
        end = heading_indices[pos + 1] if pos + 1 < len(heading_indices) else len(lines)
        body = "\n".join(lines[start + 1 : end])
        visible = re.sub(r"<!--\s*c2p:.*?-->", "", body, flags=re.DOTALL)
        visible = re.sub(r"\$\$\s*\$\$", "", visible, flags=re.DOTALL)
        if not visible.strip():
            remove_line_indices.update(range(start, end))
    if not remove_line_indices:
        return markdown
    cleaned = "\n".join(line for index, line in enumerate(lines) if index not in remove_line_indices)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip() + "\n"


def _introduces_helper_equation(paragraph: str) -> bool:
    lowered = re.sub(r"<!--\s*c2p:.*?-->", "", str(paragraph or ""), flags=re.DOTALL).lower()
    return bool(
        re.search(
            r"(positional|sinusoidal|feed-forward|attention|multi-branch).{0,120}(defined as|formulated as|written as|given by)\s*:\s*$",
            lowered,
            flags=re.DOTALL,
        )
        or re.search(
            r"(attention|query|queries|keys|values).{0,180}:\s*$",
            lowered,
            flags=re.DOTALL,
        )
    )


def _explains_removed_equation(paragraph: str) -> bool:
    stripped = re.sub(r"<!--\s*c2p:.*?-->", "", str(paragraph or ""), flags=re.DOTALL).strip()
    return bool(re.match(r"(?i)^(where|here|in this expression|this equation)\b", stripped))


def _previous_content_index(parts: list[str], index: int) -> int | None:
    for cursor in range(index - 1, -1, -1):
        if parts[cursor].strip():
            return cursor
    return None


def _next_content_index(parts: list[str], index: int) -> int | None:
    for cursor in range(index + 1, len(parts)):
        if parts[cursor].strip():
            return cursor
    return None


def _join_for_sentence(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _paper_readiness_blocks(report: dict[str, object]) -> bool:
    if not _bool_env("CODE2PAPER_PHASE5_REQUIRE_PAPER_READY", _bool_env("CODE2PAPER_PHASE4_REQUIRE_PAPER_READY", False)):
        return False
    if bool(report.get("passed")):
        return False
    high_count = int(report.get("high_issue_count", 0) or 0)
    score = int(report.get("score", 0) or 0)
    return high_count > 0 or score < 82


def _is_projection_writer_input(method_evidence: MethodEvidence) -> bool:
    return "The projection is the writer's only positive method-fact input." in method_evidence.writing_constraints


def _paper_readiness_block_reason(report: dict[str, object]) -> str:
    metrics = report.get("metrics", {}) if isinstance(report.get("metrics"), dict) else {}
    issues = report.get("issues", []) if isinstance(report.get("issues"), list) else []
    issue_ids = [
        str(issue.get("issue_id"))
        for issue in issues
        if isinstance(issue, dict) and str(issue.get("severity", "")).lower() == "high"
    ]
    return (
        "paper_readiness_failed:"
        f"score={report.get('score', 0)};"
        f"high={report.get('high_issue_count', 0)};"
        f"words={metrics.get('word_count', 0)};"
        f"equations={metrics.get('display_equation_count', 0)};"
        f"issues={','.join(issue_ids[:8])}"
    )


def _phase5_llm_payload(
    *,
    authoring_prompt: str,
    grounding_context_markdown: str,
    equations_tex: str,
    symbols_tex: str,
    outline: MethodOutline,
    terminology: TerminologyTable,
    claim_map_output: DraftClaimMap,
    method_plan: MethodPlanOutput | None = None,
) -> dict[str, object]:
    """Keep Phase 4 model input compact; authoring_prompt already embeds evidence and claim context."""

    payload: dict[str, object] = {
        "authoring_prompt": authoring_prompt,
        "grounding_context": grounding_context_markdown,
        "equations_tex": equations_tex,
        "symbols_tex": symbols_tex,
        "method_outline": outline.model_dump(mode="json"),
        "terminology_table": terminology.model_dump(mode="json"),
        "draft_claim_map": claim_map_output.model_dump(mode="json"),
    }
    if method_plan is not None:
        payload["method_plan"] = method_plan.model_dump(mode="json")
    return payload


def _remove_stale_phase5_outputs(paths: dict[str, Path]) -> None:
    for name in (
        "phase5_blocked",
        "method_plan",
        "method_plan_quality",
        "semantic_issues",
        "text_md",
        "text_clean_md",
        "text_tex",
        "text_clean_tex",
        "text_sidecar",
        "self_check",
        "self_check_clean",
        "qa_claims",
        "qa_numbers",
        "qa_equations",
        "qa_terms",
        "qa_latex",
        "phase5_manifest",
    ):
        path = paths.get(name)
        if path and path.exists():
            path.unlink()


def _write_phase5_success_outputs(
    *,
    paths: dict[str, Path],
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    alignment: CodeAlignmentIR | None,
    outline: MethodOutline,
    terminology: TerminologyTable,
    claim_map_output: DraftClaimMap,
    markdown: str,
    latex: str,
    llm_call_id: str,
    manifest_mode: str,
    llm_available: bool,
    llm_call_logs: list[str],
    supplemental_equations_tex: str = "",
    method_plan: MethodPlanOutput | None = None,
) -> None:
    markdown = _finalize_internal_method_markdown(markdown)
    latex = format_method_draft_tex(markdown)
    clean_markdown = _build_clean_method_markdown(markdown)
    clean_latex = format_method_draft_tex(clean_markdown)
    sidecar = MethodAuthoringSidecar(
        draft_version=1,
        method_outline_path="paper/method/outline.json",
        terminology_table_path="paper/method/terms.json",
        draft_claim_map_path="paper/method/text_claims.json",
        paragraphs=[
            MethodAuthoringSidecarParagraph(
                paragraph_id=paragraph.paragraph_id,
                claim_ids=paragraph.claim_ids,
                evidence_span_ids=paragraph.evidence_span_ids,
                llm_call_id=llm_call_id,
                validator_status="pending",
            )
            for paragraph in claim_map_output.paragraphs
        ],
    )
    claim_report, numeric_report, equation_report, terminology_report, latex_report = _run_quality_checks(
        method_evidence=method_evidence,
        terminology=terminology,
        markdown=markdown,
        latex=latex,
        alignment=alignment,
        draft_claim_map=claim_map_output,
        supplemental_equations_tex=supplemental_equations_tex,
    )
    readiness_report = validate_paper_readiness(markdown)
    clean_readiness_report = validate_paper_readiness(clean_markdown)
    if method_plan is not None:
        _write_json(paths["semantic_issues"], _semantic_method_issues(markdown, method_plan))
        if "method_plan_quality" in paths:
            _write_json(paths["method_plan_quality"], _method_plan_quality_report(method_plan))
    elif "semantic_issues" in paths and not paths["semantic_issues"].exists():
        _write_json(
            paths["semantic_issues"],
            {
                "passed": True,
                "issue_count": 0,
                "issues": [],
                "note": "semantic_method_issues_not_available_for_this_authoring_path",
            },
        )
    paths["text_md"].write_text(markdown, encoding="utf-8")
    paths["text_clean_md"].write_text(clean_markdown, encoding="utf-8")
    paths["text_tex"].write_text(latex, encoding="utf-8")
    paths["text_clean_tex"].write_text(clean_latex, encoding="utf-8")
    _write_json(paths["text_sidecar"], sidecar.model_dump(mode="json"))
    _write_json(paths["self_check"], _readiness_to_self_critic(readiness_report).model_dump(mode="json"))
    _write_json(paths["self_check_clean"], _readiness_to_self_critic(clean_readiness_report).model_dump(mode="json"))
    _write_json(paths["qa_claims"], claim_report)
    _write_json(paths["qa_numbers"], numeric_report.model_dump(mode="json"))
    _write_json(paths["qa_equations"], equation_report.model_dump())
    _write_json(paths["qa_terms"], terminology_report.model_dump())
    _write_json(paths["qa_latex"], latex_report)
    manifest = Phase5Manifest(
        project_id=method_evidence.project_id,
        mode=manifest_mode,
        llm_available=llm_available,
        outputs=_artifact_hashes(paths, existing_only=True, exclude={"phase5_manifest", "phase5_blocked"}),
        llm_call_logs=llm_call_logs,
        validator_reports=[],
    )
    _write_json(paths["phase5_manifest"], manifest.model_dump(mode="json"))


def _readiness_to_self_critic(report: dict[str, object]) -> SelfCriticReport:
    issues = []
    for item in report.get("issues", []) if isinstance(report, dict) else []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"low", "medium", "high"}:
            severity = "medium"
        issues.append(
            Phase5CriticIssue(
                issue_id=str(item.get("issue_id") or f"PR{len(issues) + 1}"),
                severity=Severity(severity),
                category=str(item.get("category") or "paper_readiness"),
                message=str(item.get("message") or "Paper-readiness issue."),
                paragraph_id=str(item.get("paragraph_id") or ""),
            )
        )
    return SelfCriticReport(issues=issues)


def _should_use_deterministic_fallback(reason: str) -> bool:
    lowered = str(reason or "").strip().lower()
    if not lowered:
        return False
    return any(
        token in lowered
        for token in (
            "provider_response_missing_content",
            "provider_response_empty_content",
            "provider_response_not_json",
            "schema_validation_failed",
            "empty_method_draft_markdown",
        )
    )


def _method_plan_llm_prompt() -> str:
    return "\n".join(
        [
            "You are planning a publication-grade Method section from frozen code evidence.",
            "Return only JSON matching the provided MethodPlanOutput schema.",
            "No markdown wrapper, no explanations, no extra keys.",
            "",
            "Planning contract:",
            "- Treat authoring_prompt, claim_evidence_map, stage_packets, and author_intent_spine as the truth boundary.",
            "- Build a section plan before prose: each section needs a heading, purpose, evidence ids, required mechanisms, and an input -> operation -> output contract.",
            "- Each section must include role, input_representation, operation, output_representation, figure_role, and priority.",
            "- Valid role values are overview, core, objective, data, supporting, evaluation, or setup.",
            "- Valid figure_role values are include, optional, or omit.",
            "- Downstream evaluation, validation/testing, fine-tuning, voting, benchmark, metric, setup, config, CLI, and launcher sections default to role=supporting/evaluation/setup and figure_role=omit unless evidence proves they are method-defining contributions.",
            "- Select equations by semantic role, not by count. Prefer equations that define the method flow and objective.",
            "- Assign each selected equation to the section whose mechanism it defines; do not plan a detached equation-only section.",
            "- Put generic attention, positional encoding, FFN, setup/config, and evaluation protocol in forbidden_details unless they are explicitly method-defining.",
            "- Preserve code-supported paper module aliases as figure_module_names.",
            "- Include checklist items for paper quality: overview contribution, baseline problem -> method response, core modules, objective target binding, and figure/text naming consistency.",
            "- Do not draft the Method prose here.",
        ]
    )


def _method_draft_llm_prompt() -> str:
    return "\n".join(
        [
            "You are writing a publication-grade Method section from a structured Method plan.",
            "Return only JSON matching this schema: {\"markdown\": \"...\"}.",
            "No markdown wrapper, no explanations, no extra keys.",
            "",
            "Truth boundary:",
            "- method_plan is the writing contract; authoring_prompt and evidence only resolve factual details.",
            "- Never invent unsupported modules, losses, equations, datasets, numbers, ablations, or novelty claims.",
            "- Preserve existing c2p grounding comments only when they are already present in input text; do not invent custom c2p tags.",
            "",
            "Writing requirements:",
            "- Follow method_plan.sections in order unless evidence makes a section impossible.",
            "- Start with `# Method`; use the planned headings as `##` subsections.",
            "- Each core subsection must state input, operation, and output in connected conference-paper prose.",
            "- The overview must name the baseline problem and the method response when method_plan provides them.",
            "- The objective/loss subsection must bind each loss to its concrete prediction or reconstruction target.",
            "- Use method_plan.equations selectively. Include required equations only when their symbols can be explained from equations_tex/symbols_tex.",
            "- Place each equation inside the subsection whose operation it defines, with a lead-in sentence before the display equation and a symbol/role explanation immediately after it.",
            "- Do not collect equations in a detached opening block, closing block, or generic Training Objective subsection unless the equation specifically defines the training objective.",
            "- Rewrite implementation leakage into paper-facing terms instead of dropping the method detail.",
            "- Do not promote setup/config/CLI, validation/testing, voting, checkpoint loading, or dataset bookkeeping into method mechanisms.",
            "- Avoid bullet lists, audit vocabulary, meta-writing phrases, inline code formatting, file paths, script names, import paths, and CLI flags.",
            "- Keep the section natural and dense. Length should follow the method complexity; do not pad merely to satisfy a word target.",
            "",
            "Quality bar:",
            "- The result should read like a normal conference paper Method section, not a compliance report.",
            "- It should satisfy method_plan.revision_checklist on the first attempt.",
            "- Prefer semantic completeness over rigid word, heading, or equation counts.",
        ]
    )


def _paper_readiness_revision_prompt() -> str:
    return "\n".join(
        [
            "You are revising a generated Method section into directly usable conference-paper prose.",
            "Return only JSON matching this schema: {\"markdown\": \"...\"}.",
            "No markdown wrapper, no explanations, no extra keys.",
            "",
            "Revision rules:",
            "- Fix every high-severity issue in paper_readiness_report.",
            "- Also fix semantic_method_issues. For implementation_leakage, rewrite the sentence as paper-facing method prose instead of silently deleting the detail.",
            "- Use method_plan as the authority for section order, core mechanisms, required equations, forbidden details, and figure/text module names.",
            "- If paper_readiness_report includes PR1, expand to at least 850 words by adding mechanism detail, not experiment protocol.",
            "- If paper_readiness_report includes PR3, rewrite with `# Method` plus multiple `##` subsections.",
            "- If paper_readiness_report includes PR5, add a dedicated objective/loss subsection with the supported objective terms and their roles.",
            "- Use this default repair shape when applicable: `## Overview`, one or more `##` core transformation sections, `## Objective`, and a short supporting usage note only when evidence requires it.",
            "- Follow author_intent_spine.preferred_section_flow from the original authoring request when it is code-supported.",
            "- Preserve code-supported author module aliases as paper-facing names, not file names.",
            "- Aim for roughly 750-1200 words by explaining inputs, transformations, outputs, objectives, and innovation-bearing mechanisms.",
            "- Keep all factual content within method_evidence and claim_evidence_map.",
            "- Preserve c2p grounding comments, but attach them to coherent paragraphs.",
            "- Remove all meta-writing residue such as 'defines one paper-facing subsection', 'this paragraph should', 'this subsection must', 'represent the paper-facing stage', 'supported claims', and 'generated Method section'.",
            "- The returned markdown must contain only paper text plus existing c2p grounding comments.",
            "- Remove audit/report vocabulary such as 'evidence-backed', 'partially supported', 'mechanism formulation', and file/script references.",
            "- Remove all .py filenames, import paths, command names, CLI flags, local paths, and inline-code formatting.",
            "- Replace bullet-heavy writing with connected paper prose.",
            "- Keep the equations needed for the method, selecting core definitions and objective terms rather than enforcing a fixed count.",
            "- Preserve natural placement: each retained equation should stay near the paragraph that describes the corresponding module, score, selection rule, loss, or culling operation.",
            "- Prefer concrete operation equations from equations_tex over generic attention, positional-encoding, FFN, dropout, or normalization formulas.",
            "- Remove setup/config parsing, initializer behavior, checkpointing, logging, and dropout sentences unless they define the method contribution.",
            "- Remove validation/testing/voting/metric aggregation protocol unless it defines the method contribution.",
            "- The result should read as a self-contained Method section that can be placed in a paper.",
        ]
    )

def _outline_scaffold(method_evidence: MethodEvidence) -> MethodOutline:
    ordered_stages = _ordered_stages_for_authoring(method_evidence)
    sections = [
        MethodOutlineParagraph(
            paragraph_id="P1",
            purpose="Overview of the evidence-backed method.",
            stage_ids=[stage.stage_id for stage in ordered_stages],
            mechanism_ids=[],
            claim_ids=[contract.claim_id for contract in method_evidence.claim_contracts if contract.support_status.value != "unsupported"][:3],
            evidence_span_ids=[],
        )
    ]
    for index, stage in enumerate(ordered_stages, start=2):
        stage_frozen_mechanisms = [
            mechanism
            for mechanism in method_evidence.frozen_mechanisms
            if mechanism.parent_stage_id == stage.stage_id
        ]
        stage_frozen_mechanism_ids = [mechanism.mechanism_id for mechanism in stage_frozen_mechanisms if mechanism.mechanism_id]
        stage_method_mechanism_ids = [mechanism.mechanism_id for mechanism in stage.mechanisms if mechanism.mechanism_id]
        stage_mechanism_ids = _dedupe(stage_frozen_mechanism_ids + stage_method_mechanism_ids)
        stage_evidence_ids = _dedupe(
            [eid for mechanism in stage_frozen_mechanisms for eid in mechanism.evidence_span_ids]
            + [eid for mechanism in stage.mechanisms for eid in mechanism.evidence_ids]
        )
        sections.append(
            MethodOutlineParagraph(
                paragraph_id=f"P{index}",
                purpose=f"Describe {stage.name}.",
                stage_ids=[stage.stage_id],
                mechanism_ids=stage_mechanism_ids,
                claim_ids=[contract.claim_id for contract in method_evidence.claim_contracts if stage.name in contract.claim_intent],
                evidence_span_ids=stage_evidence_ids,
            )
        )
    return MethodOutline(
        sections=sections,
        author_logic_order=method_evidence.author_logic_mapping.author_proposed_flow
        or method_evidence.author_logic_mapping.author_supported_flow,
    )


def _ordered_stages_for_authoring(method_evidence: MethodEvidence) -> list:
    stages = list(method_evidence.stages)
    if not stages:
        return stages
    desired = method_evidence.author_logic_mapping.author_proposed_flow or method_evidence.author_logic_mapping.author_supported_flow
    if not desired:
        return stages
    by_normalized = {_normalize_story_name(stage.name): stage for stage in stages}
    ordered = []
    for story_item in desired:
        stage = by_normalized.get(_normalize_story_name(story_item))
        if stage and stage not in ordered:
            ordered.append(stage)
    for stage in stages:
        if stage not in ordered:
            ordered.append(stage)
    process_stages = [stage for stage in ordered if not _is_meta_stage_name(stage.name)]
    if len(process_stages) >= 2:
        return process_stages
    return ordered


def _normalize_story_name(value: str) -> str:
    lowered = value.lower().replace("_", " ").replace("-", " ")
    return " ".join(lowered.split())


def _is_meta_stage_name(name: str) -> bool:
    normalized = _normalize_story_name(name)
    if not normalized:
        return True
    if normalized in {"method", "method overview", "method overview and preliminaries"}:
        return True
    return any(hint in normalized for hint in _META_STAGE_HINTS)


def _terminology_scaffold(method_evidence: MethodEvidence) -> TerminologyTable:
    terms: list[TerminologyTerm] = []
    for index, stage in enumerate(method_evidence.stages, start=1):
        terms.append(
            TerminologyTerm(
                term_id=f"TERM-STAGE-{index}",
                canonical=stage.name,
                term_type="stage",
                source_ids=[stage.stage_id],
                evidence_span_ids=_dedupe([eid for mechanism in stage.mechanisms for eid in mechanism.evidence_ids]),
            )
        )
    for index, mechanism in enumerate(method_evidence.frozen_mechanisms, start=1):
        terms.append(
            TerminologyTerm(
                term_id=f"TERM-MECH-{index}",
                canonical=mechanism.mechanism_name,
                term_type="mechanism",
                source_ids=[mechanism.mechanism_id],
                evidence_span_ids=mechanism.evidence_span_ids,
            )
        )
    for index, alias in enumerate(method_evidence.paper_module_aliases, start=1):
        terms.append(
            TerminologyTerm(
                term_id=f"TERM-ALIAS-{index}",
                canonical=alias.expansion,
                term_type="paper-module-alias",
                allowed_synonyms=[alias.alias],
                source_ids=alias.source_ids,
                evidence_span_ids=alias.evidence_span_ids,
            )
        )
    return TerminologyTable(terms=terms)


def _draft_claim_map_scaffold(outline: MethodOutline) -> DraftClaimMap:
    return DraftClaimMap(
        paragraphs=[
            {
                "paragraph_id": paragraph.paragraph_id,
                "claim_ids": paragraph.claim_ids,
                "mechanism_ids": paragraph.mechanism_ids,
                "evidence_span_ids": paragraph.evidence_span_ids,
            }
            for paragraph in outline.sections
        ]
    )


def _normalize_draft_claim_map(
    *,
    draft_claim_map: DraftClaimMap,
    outline: MethodOutline,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
) -> DraftClaimMap:
    contracts = list(method_evidence.claim_contracts)
    known_claim_ids = {contract.claim_id for contract in contracts}
    max_claim_ids_per_paragraph = 6
    max_evidence_ids_per_paragraph = 80
    max_mechanism_ids_per_paragraph = 8
    supported_claim_ids = [
        contract.claim_id
        for contract in contracts
        if contract.claim_id in known_claim_ids and contract.support_status.value != "unsupported"
    ]
    known_mechanism_ids = {
        mechanism.mechanism_id
        for mechanism in method_evidence.frozen_mechanisms
        if mechanism.mechanism_id
    }
    mechanism_evidence: dict[str, list[str]] = {}
    stage_mechanisms_by_stage: dict[str, list[str]] = {stage.stage_id: [] for stage in method_evidence.stages}
    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            if not mechanism.mechanism_id:
                continue
            known_mechanism_ids.add(mechanism.mechanism_id)
            stage_mechanisms_by_stage.setdefault(stage.stage_id, []).append(mechanism.mechanism_id)
            mechanism_evidence.setdefault(mechanism.mechanism_id, [])
            mechanism_evidence[mechanism.mechanism_id].extend(
                [evidence_id for evidence_id in mechanism.evidence_ids if evidence_id]
            )
    for mechanism in method_evidence.frozen_mechanisms:
        if not mechanism.mechanism_id:
            continue
        mechanism_evidence.setdefault(mechanism.mechanism_id, [])
        mechanism_evidence[mechanism.mechanism_id].extend(
            [evidence_id for evidence_id in mechanism.evidence_span_ids if evidence_id]
        )
    mechanism_evidence = {
        mechanism_id: _dedupe(evidence_ids)
        for mechanism_id, evidence_ids in mechanism_evidence.items()
    }
    stage_mechanisms_by_stage = {
        stage_id: _dedupe(mechanism_ids)
        for stage_id, mechanism_ids in stage_mechanisms_by_stage.items()
    }
    mechanism_to_stage: dict[str, str] = {
        mechanism_id: stage_id
        for stage_id, mechanism_ids in stage_mechanisms_by_stage.items()
        for mechanism_id in mechanism_ids
        if mechanism_id
    }
    for mechanism in method_evidence.frozen_mechanisms:
        if mechanism.mechanism_id and mechanism.parent_stage_id:
            mechanism_to_stage.setdefault(mechanism.mechanism_id, mechanism.parent_stage_id)
    known_evidence_ids = {
        evidence_id
        for evidence_ids in mechanism_evidence.values()
        for evidence_id in evidence_ids
    }
    known_evidence_ids.update(
        {
            evidence_id
            for contract in contracts
            for evidence_id in contract.evidence_span_ids
            if evidence_id
        }
    )

    claim_to_evidence = {
        contract.claim_id: [evidence_id for evidence_id in contract.evidence_span_ids if evidence_id in known_evidence_ids]
        for contract in contracts
        if contract.claim_id in known_claim_ids
    }
    claim_to_mechanisms: dict[str, list[str]] = {claim_id: [] for claim_id in known_claim_ids}
    mechanism_to_claims: dict[str, list[str]] = {mechanism_id: [] for mechanism_id in known_mechanism_ids}
    for claim_entry in claim_map.claims:
        claim_id = claim_entry.claim_id
        if claim_id not in known_claim_ids:
            continue
        for mechanism_id in claim_entry.mechanism_ids:
            if mechanism_id not in known_mechanism_ids:
                continue
            claim_to_mechanisms.setdefault(claim_id, []).append(mechanism_id)
            mechanism_to_claims.setdefault(mechanism_id, []).append(claim_id)
    claim_to_mechanisms = {claim_id: _dedupe(values) for claim_id, values in claim_to_mechanisms.items()}
    mechanism_to_claims = {mechanism_id: _dedupe(values) for mechanism_id, values in mechanism_to_claims.items()}

    stage_names = {stage.stage_id: stage.name for stage in method_evidence.stages}
    claim_ids_by_stage: dict[str, list[str]] = {stage_id: [] for stage_id in stage_names}
    for contract in contracts:
        claim_id = contract.claim_id
        if claim_id not in known_claim_ids:
            continue
        normalized_intent = _normalize_story_name(contract.claim_intent)
        for stage_id, stage_name in stage_names.items():
            if _normalize_story_name(stage_name) in normalized_intent:
                claim_ids_by_stage[stage_id].append(claim_id)
    claim_ids_by_stage = {stage_id: _dedupe(values) for stage_id, values in claim_ids_by_stage.items()}

    outline_by_paragraph = {paragraph.paragraph_id: paragraph for paragraph in outline.sections}
    source_paragraphs = list(draft_claim_map.paragraphs) or _draft_claim_map_scaffold(outline).paragraphs
    normalized_paragraphs: list[dict] = []
    seen_paragraph_ids: set[str] = set()

    for index, paragraph in enumerate(source_paragraphs, start=1):
        paragraph_id = paragraph.paragraph_id or f"P{index}"
        seen_paragraph_ids.add(paragraph_id)
        outline_paragraph = outline_by_paragraph.get(paragraph_id)

        mechanism_ids = _dedupe(
            [mechanism_id for mechanism_id in paragraph.mechanism_ids if mechanism_id in known_mechanism_ids]
            + (
                [
                    mechanism_id
                    for mechanism_id in (outline_paragraph.mechanism_ids if outline_paragraph else [])
                    if mechanism_id in known_mechanism_ids
                ]
            )
        )[:max_mechanism_ids_per_paragraph]
        evidence_ids = _dedupe(
            [evidence_id for evidence_id in paragraph.evidence_span_ids if evidence_id in known_evidence_ids]
            + (
                [
                    evidence_id
                    for evidence_id in (outline_paragraph.evidence_span_ids if outline_paragraph else [])
                    if evidence_id in known_evidence_ids
                ]
            )
            + [evidence_id for mechanism_id in mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
        )[:max_evidence_ids_per_paragraph]

        claim_ids = _dedupe([claim_id for claim_id in paragraph.claim_ids if claim_id in known_claim_ids])
        if not claim_ids:
            claim_candidates: list[str] = []
            if outline_paragraph:
                outline_claims = [claim_id for claim_id in outline_paragraph.claim_ids if claim_id in known_claim_ids]
                claim_candidates.extend(outline_claims)
            if not claim_candidates:
                for mechanism_id in mechanism_ids:
                    claim_candidates.extend(mechanism_to_claims.get(mechanism_id, []))
            if not claim_candidates and evidence_ids:
                evidence_set = set(evidence_ids)
                for claim_id in supported_claim_ids:
                    claim_evidence = set(claim_to_evidence.get(claim_id, []))
                    if claim_evidence and claim_evidence.intersection(evidence_set):
                        claim_candidates.append(claim_id)
            if not claim_candidates and outline_paragraph:
                for stage_id in outline_paragraph.stage_ids:
                    claim_candidates.extend(claim_ids_by_stage.get(stage_id, []))
            claim_ids = _dedupe(claim_candidates)[:max_claim_ids_per_paragraph]

        if not mechanism_ids:
            mechanism_ids = _dedupe(
                [mechanism_id for claim_id in claim_ids for mechanism_id in claim_to_mechanisms.get(claim_id, [])]
            )[:max_mechanism_ids_per_paragraph]
            if not mechanism_ids and outline_paragraph:
                mechanism_ids = _dedupe(
                    [
                        mechanism_id
                        for mechanism_id in outline_paragraph.mechanism_ids
                        if mechanism_id in known_mechanism_ids
                    ]
                )[:max_mechanism_ids_per_paragraph]
            if not mechanism_ids and outline_paragraph:
                mechanism_ids = _dedupe(
                    [
                        mechanism_id
                        for stage_id in outline_paragraph.stage_ids
                        for mechanism_id in stage_mechanisms_by_stage.get(stage_id, [])
                        if mechanism_id in known_mechanism_ids
                    ]
                )[:max_mechanism_ids_per_paragraph]

        if not evidence_ids:
            evidence_ids = _dedupe(
                [evidence_id for claim_id in claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
            )[:max_evidence_ids_per_paragraph]
            if not evidence_ids:
                evidence_ids = _dedupe(
                    [evidence_id for mechanism_id in mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
                )[:max_evidence_ids_per_paragraph]

        normalized_paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "claim_ids": claim_ids,
                "mechanism_ids": mechanism_ids,
                "evidence_span_ids": evidence_ids,
            }
        )

    for outline_paragraph in outline.sections:
        if outline_paragraph.paragraph_id in seen_paragraph_ids:
            continue
        fallback_claim_ids = _dedupe(
            [claim_id for claim_id in outline_paragraph.claim_ids if claim_id in known_claim_ids]
        )[:max_claim_ids_per_paragraph]
        fallback_mechanism_ids = _dedupe(
            [
                mechanism_id
                for mechanism_id in outline_paragraph.mechanism_ids
                if mechanism_id in known_mechanism_ids
            ]
        )[:max_mechanism_ids_per_paragraph]
        if not fallback_mechanism_ids:
            fallback_mechanism_ids = _dedupe(
                [
                    mechanism_id
                    for stage_id in outline_paragraph.stage_ids
                    for mechanism_id in stage_mechanisms_by_stage.get(stage_id, [])
                    if mechanism_id in known_mechanism_ids
                ]
            )[:max_mechanism_ids_per_paragraph]
        fallback_evidence_ids = _dedupe(
            [
                evidence_id
                for evidence_id in outline_paragraph.evidence_span_ids
                if evidence_id in known_evidence_ids
            ]
            or [evidence_id for claim_id in fallback_claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
            or [evidence_id for mechanism_id in fallback_mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
        )[:max_evidence_ids_per_paragraph]
        normalized_paragraphs.append(
            {
                "paragraph_id": outline_paragraph.paragraph_id,
                "claim_ids": fallback_claim_ids,
                "mechanism_ids": fallback_mechanism_ids,
                "evidence_span_ids": fallback_evidence_ids,
            }
        )

    covered_stage_ids = {
        mechanism_to_stage.get(mechanism_id, "")
        for paragraph in normalized_paragraphs
        for mechanism_id in paragraph["mechanism_ids"]
        if mechanism_to_stage.get(mechanism_id, "")
    }
    existing_paragraph_ids = {paragraph["paragraph_id"] for paragraph in normalized_paragraphs}
    next_paragraph_index = len(normalized_paragraphs) + 1
    for stage in method_evidence.stages:
        if stage.stage_id in covered_stage_ids:
            continue
        stage_mechanism_ids = _dedupe(
            [mechanism_id for mechanism_id in stage_mechanisms_by_stage.get(stage.stage_id, []) if mechanism_id in known_mechanism_ids]
        )[:max_mechanism_ids_per_paragraph]
        if not stage_mechanism_ids:
            continue
        fallback_claim_ids = _dedupe(claim_ids_by_stage.get(stage.stage_id, []))[:max_claim_ids_per_paragraph]
        fallback_evidence_ids = _dedupe(
            [evidence_id for mechanism_id in stage_mechanism_ids for evidence_id in mechanism_evidence.get(mechanism_id, [])]
            or [evidence_id for claim_id in fallback_claim_ids for evidence_id in claim_to_evidence.get(claim_id, [])]
        )[:max_evidence_ids_per_paragraph]
        paragraph_id = f"P{next_paragraph_index}"
        while paragraph_id in existing_paragraph_ids:
            next_paragraph_index += 1
            paragraph_id = f"P{next_paragraph_index}"
        normalized_paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "claim_ids": fallback_claim_ids,
                "mechanism_ids": stage_mechanism_ids,
                "evidence_span_ids": fallback_evidence_ids,
            }
        )
        existing_paragraph_ids.add(paragraph_id)
        next_paragraph_index += 1

    return DraftClaimMap(paragraphs=normalized_paragraphs)


def _latex_style_instruction(style: str) -> str:
    normalized = (style or "balanced").strip().lower()
    if normalized == "implementation-faithful":
        return (
            "Writing style preference is implementation-faithful: prioritize concrete implementation behavior, "
            "explicit modules, tensors, and update flow over abstract framing."
        )
    if normalized == "paper-abstract":
        return (
            "Writing style preference is paper-abstract: emphasize conceptual method logic and concise abstraction, "
            "while keeping all claims evidence-grounded."
        )
    return (
        "Writing style preference is balanced: combine conceptual explanation with implementation-grounded details."
    )


def _latex_constraints(method_evidence: MethodEvidence) -> list[str]:
    constraints = [
        "Use section/subsection/paragraph commands.",
        "Do not introduce new claims.",
    ]
    style = method_evidence.latex_expression_preference.value
    if style == "implementation-faithful":
        constraints.append("Prefer explicit implementation-level phrasing and concrete module references.")
    elif style == "paper-abstract":
        constraints.append("Prefer concise abstract phrasing and avoid unnecessary low-level implementation digressions.")
    else:
        constraints.append("Balance abstract explanation with concrete implementation details.")
    return constraints


def _method_evidence_for_authoring(method_evidence: MethodEvidence) -> dict:
    """Build a role-aware view for generation without deleting valid evidence."""

    stage_packets = _stage_authoring_packets(method_evidence)
    author_intent_spine = _author_intent_spine(method_evidence, stage_packets)
    return {
        "project_id": method_evidence.project_id,
        "method_name": method_evidence.method_name,
        "method_goal": method_evidence.method_goal,
        "implementation_scope": method_evidence.implementation_scope,
        "latex_expression_preference": method_evidence.latex_expression_preference.value,
        "author_logic_priority": method_evidence.author_logic_priority,
        "author_logic_mapping": method_evidence.author_logic_mapping.model_dump(mode="json"),
        "author_intent_spine": author_intent_spine,
        "authoring_policy": {
            "primary_rule": "Write from stage_packets.primary_mechanisms and primary_evidence_ids first.",
            "author_spine_rule": "Use author_intent_spine as the default section order and preferred module naming plan when entries have code-backed stage or alias evidence.",
            "supporting_rule": "Use supporting behavior/equation evidence only when it is linked to a stage, mechanism, or claim.",
            "background_rule": "Background/backbone evidence may be mentioned as implementation context, but must not be promoted to contribution unless a stage or claim explicitly binds it.",
            "excluded_rule": "Generated artifacts and pretrained asset packaging are not method evidence.",
            "overview_rule": "The overview should summarize stage logic and should not enumerate low-level backbone internals.",
        },
        "paper_module_aliases": [alias.model_dump(mode="json") for alias in method_evidence.paper_module_aliases],
        "stage_packets": stage_packets,
        "frozen_mechanisms": [mechanism.model_dump(mode="json") for mechanism in method_evidence.frozen_mechanisms],
        "claim_contracts": [contract.model_dump(mode="json") for contract in method_evidence.claim_contracts],
        "behavior_patterns_by_role": _behavior_authoring_roles(method_evidence, stage_packets),
        "equation_candidates_by_role": _equation_authoring_roles(method_evidence, stage_packets),
        "architecture_parameters": [param.model_dump(mode="json") for param in method_evidence.architecture_parameters[:80]],
        "tensor_roles": [tensor.model_dump(mode="json") for tensor in method_evidence.tensor_roles[:80]],
        "writing_constraints": method_evidence.writing_constraints,
        "negative_scope": method_evidence.negative_scope,
        "alignment_notes": method_evidence.alignment_notes,
        "excluded_sources": [source.model_dump(mode="json") for source in method_evidence.excluded_sources],
    }


def _author_intent_spine(method_evidence: MethodEvidence, stage_packets: list[dict]) -> dict:
    """Expose the user-provided method flow as a code-checked writing spine."""

    supported_stage_names = [str(packet.get("name") or "").strip() for packet in stage_packets if str(packet.get("name") or "").strip()]
    proposed_flow = [item for item in method_evidence.author_logic_mapping.author_proposed_flow if str(item).strip()]
    supported_flow = [item for item in method_evidence.author_logic_mapping.author_supported_flow if str(item).strip()]
    preferred_flow = proposed_flow or supported_flow or supported_stage_names
    alias_items = []
    for alias in method_evidence.paper_module_aliases:
        if not alias.evidence_span_ids:
            continue
        alias_items.append(
            {
                "alias": alias.alias,
                "expansion": alias.expansion,
                "matched_name": alias.matched_name,
                "matched_role": alias.matched_role,
                "evidence_span_ids": alias.evidence_span_ids,
                "confidence": alias.confidence.value,
            }
        )
    return {
        "preferred_section_flow": preferred_flow,
        "code_supported_stage_names": supported_stage_names,
        "code_supported_module_aliases": alias_items,
        "unsupported_author_parts": method_evidence.author_logic_mapping.author_unsupported_parts
        or method_evidence.unsupported_author_parts,
        "instructions": [
            "Treat preferred_section_flow as the intended Method narrative order unless code evidence contradicts it.",
            "Use code_supported_module_aliases as paper-facing module names, but only for the mechanisms tied to their evidence IDs.",
            "Do not replace author-facing module names with raw file names or script names in prose.",
            "If a proposed flow item has no supported stage or evidence, omit it or phrase it as outside the current method scope.",
        ],
    }


def _stage_authoring_packets(method_evidence: MethodEvidence) -> list[dict]:
    raw_packets = [
        packet
        for packet in method_evidence.stage_packets
        if isinstance(packet, dict)
    ]
    raw_by_stage = {
        str(packet.get("stage_id") or ""): packet
        for packet in raw_packets
        if str(packet.get("stage_id") or "")
    }
    raw_by_name = {
        _normalize_story_name(str(packet.get("name") or "")): packet
        for packet in raw_packets
        if str(packet.get("name") or "")
    }
    frozen_by_stage: dict[str, list] = {stage.stage_id: [] for stage in method_evidence.stages}
    for mechanism in method_evidence.frozen_mechanisms:
        if mechanism.parent_stage_id:
            frozen_by_stage.setdefault(mechanism.parent_stage_id, []).append(mechanism)

    claim_ids_by_stage: dict[str, list[str]] = {stage.stage_id: [] for stage in method_evidence.stages}
    for contract in method_evidence.claim_contracts:
        normalized_intent = _normalize_story_name(contract.claim_intent)
        for stage in method_evidence.stages:
            if _normalize_story_name(stage.name) in normalized_intent:
                claim_ids_by_stage.setdefault(stage.stage_id, []).append(contract.claim_id)

    packets: list[dict] = []
    for stage in _ordered_stages_for_authoring(method_evidence):
        raw_packet = raw_by_stage.get(stage.stage_id) or raw_by_name.get(_normalize_story_name(stage.name)) or {}
        stage_mechanisms = list(stage.mechanisms)
        frozen_mechanisms = frozen_by_stage.get(stage.stage_id, [])
        primary_evidence_ids = _dedupe(
            [evidence_id for mechanism in stage_mechanisms for evidence_id in mechanism.evidence_ids]
            + [evidence_id for mechanism in frozen_mechanisms for evidence_id in mechanism.evidence_span_ids]
        )
        if "The projection is the writer's only positive method-fact input." in method_evidence.writing_constraints:
            authorized_evidence_ids = {
                evidence_id
                for contract in method_evidence.claim_contracts
                for evidence_id in contract.evidence_span_ids
            }
            primary_evidence_ids = _dedupe(
                primary_evidence_ids
                + [
                    str(evidence_id)
                    for evidence_id in raw_packet.get("primary_evidence_ids", [])
                    if str(evidence_id) in authorized_evidence_ids
                ]
            )
        primary_mechanism_ids = _dedupe(
            [mechanism.mechanism_id for mechanism in frozen_mechanisms if mechanism.mechanism_id]
            + [mechanism.mechanism_id for mechanism in stage_mechanisms if mechanism.mechanism_id]
        )
        packets.append(
            {
                "stage_id": stage.stage_id,
                "name": raw_packet.get("name") or stage.name,
                "purpose": raw_packet.get("purpose") or stage.purpose,
                "inputs": raw_packet.get("inputs") or stage.inputs,
                "outputs": raw_packet.get("outputs") or stage.outputs,
                "primary_mechanism_ids": primary_mechanism_ids,
                "primary_evidence_ids": primary_evidence_ids,
                "claim_ids": _dedupe(claim_ids_by_stage.get(stage.stage_id, [])),
                "modules": [module.model_dump(mode="json") for module in stage.modules],
                "mechanisms": [mechanism.model_dump(mode="json") for mechanism in stage_mechanisms],
                "frozen_mechanisms": [mechanism.model_dump(mode="json") for mechanism in frozen_mechanisms],
                "module_actions": raw_packet.get("module_actions") or [],
                "key_operations": raw_packet.get("key_operations") or [],
                "stage_claim": raw_packet.get("stage_claim") or "",
                "writing_instruction": (
                    "Use this packet as the main source for the stage paragraph. "
                    "Do not replace this stage's author-facing purpose with unbound backbone internals."
                ),
            }
        )
    return packets


def _behavior_authoring_roles(method_evidence: MethodEvidence, stage_packets: list[dict]) -> dict[str, list[dict]]:
    stage_context = _stage_context_from_packets(stage_packets)
    grouped: dict[str, list[dict]] = {"primary": [], "supporting": [], "background": [], "excluded": []}
    for pattern in method_evidence.behavior_patterns:
        role, stage_ids, reason = _classify_evidence_for_authoring(
            path=pattern.path,
            evidence_ids=pattern.evidence_ids,
            stage_context=stage_context,
        )
        item = pattern.model_dump(mode="json")
        item["authoring_role"] = role
        item["stage_ids"] = stage_ids
        item["role_reason"] = reason
        grouped[role].append(item)
    return {role: items[:80] for role, items in grouped.items()}


def _equation_authoring_roles(method_evidence: MethodEvidence, stage_packets: list[dict]) -> dict[str, list[dict]]:
    stage_context = _stage_context_from_packets(stage_packets)
    grouped: dict[str, list[dict]] = {"primary": [], "supporting": [], "background": [], "excluded": []}
    for equation in method_evidence.equation_candidates:
        role, stage_ids, reason = _classify_evidence_for_authoring(
            path="",
            evidence_ids=equation.evidence_ids,
            stage_context=stage_context,
        )
        if not equation.evidence_ids and role != "excluded":
            role = "background"
            reason = "No direct stage/claim evidence binding; use only if a claim contract explicitly requires it."
        item = equation.model_dump(mode="json")
        item["authoring_role"] = role
        item["stage_ids"] = stage_ids
        item["role_reason"] = reason
        grouped[role].append(item)
    return {role: items[:80] for role, items in grouped.items()}


def _stage_context_from_packets(stage_packets: list[dict]) -> dict:
    evidence_to_stage: dict[str, list[str]] = {}
    path_to_stage: dict[str, list[str]] = {}
    for packet in stage_packets:
        stage_id = str(packet.get("stage_id") or "")
        for evidence_id in packet.get("primary_evidence_ids", []):
            evidence_to_stage.setdefault(str(evidence_id), []).append(stage_id)
        for module in packet.get("modules", []):
            path = _normalize_path(str(module.get("path") or ""))
            if path:
                path_to_stage.setdefault(path, []).append(stage_id)
    return {
        "evidence_to_stage": {key: _dedupe(value) for key, value in evidence_to_stage.items()},
        "path_to_stage": {key: _dedupe(value) for key, value in path_to_stage.items()},
    }


def _classify_evidence_for_authoring(*, path: str, evidence_ids: list[str], stage_context: dict) -> tuple[str, list[str], str]:
    normalized_path = _normalize_path(path)
    if _is_generated_or_asset_path(normalized_path):
        return "excluded", [], "Generated artifact or pretrained asset packaging; not method evidence."
    evidence_to_stage = stage_context["evidence_to_stage"]
    path_to_stage = stage_context["path_to_stage"]
    stage_ids = _dedupe(
        [stage_id for evidence_id in evidence_ids for stage_id in evidence_to_stage.get(evidence_id, [])]
        + [
            stage_id
            for module_path, stage_ids_for_path in path_to_stage.items()
            if normalized_path
            and (
                normalized_path == module_path
                or normalized_path.endswith("/" + module_path)
                or module_path.endswith("/" + normalized_path)
            )
            for stage_id in stage_ids_for_path
        ]
    )
    if stage_ids and evidence_ids:
        return "primary", stage_ids, "Evidence IDs are directly bound to stage mechanisms."
    if stage_ids:
        return "supporting", stage_ids, "Path is bound to a stage module, but evidence IDs are not directly mechanism-bound."
    return "background", [], "No direct author-stage binding; keep as implementation/backbone context only."


def _is_generated_or_asset_path(path: str) -> bool:
    lowered = path.lower()
    return (
        "swark-output/" in lowered
        or "/code2paper_agent/output/" in lowered
        or lowered.startswith("code2paper_agent/output/")
        or "/.codeboarding/" in lowered
        or lowered.startswith(".codeboarding/")
        or "pretrained_weight/" in lowered
        or lowered.endswith((".safetensors", ".bin", ".pt", ".pth", ".ckpt"))
    )


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _authoring_prompt(method_evidence: MethodEvidence, claim_map: ClaimEvidenceMap) -> str:
    authoring_view = _method_evidence_for_authoring(method_evidence)
    writing_rules = [
        "Write from authoring_view.author_intent_spine and stage_packets first; use other fields as support.",
        "Treat author_intent_spine.preferred_section_flow as the default Method narrative order when the items are supported by stage_packets or code_supported_module_aliases.",
        "Preserve author-facing module names from code_supported_module_aliases in headings/prose when they have evidence_span_ids; do not replace them with filenames, import paths, or script names.",
        "Prioritize supported and partially-supported claims; unsupported claims must be omitted.",
        "If author intent conflicts with code evidence, follow code evidence and note conservative wording.",
        "Avoid generic filler; each subsection should be tied to concrete mechanisms/evidence.",
        "Use subsection-level point-wise structure so readers can follow modules/stages quickly.",
        "Avoid literal local file paths and shell/script invocation details in the method prose.",
        "Keep paragraph-level structure close to: overview -> stage-1 -> stage-2 -> ... -> training/inference notes.",
        "Prioritize algorithmic mechanism flow over runtime orchestration details.",
        "Treat setup/config/CLI/launcher/data-loading details as low-priority support unless they implement the core method; summarize them briefly in notes instead of giving them equal stage weight.",
        "Include a dedicated objective paragraph when objective/loss/equation evidence exists; show the full available mathematical expression rather than only naming the loss.",
        "Explicitly unpack innovation-bearing or distinguishing mechanisms: state what they consume, what transformation they perform, what they output, and why that changes the pipeline.",
        "When equations_tex/symbols_tex are present, align variable names and symbols exactly.",
        "Whenever you introduce an equation, explain symbols inline nearby; do not add a separate symbol table section.",
        "Do not invent formulas or novelty claims; if a formula/mechanism is only partial in evidence, label it as the implemented fragment rather than completing it from domain assumptions.",
        "Use paper_module_aliases as preferred paper-facing module names only when their evidence_span_ids are non-empty; never introduce an acronym from README/author text without linked code evidence.",
        "When author intent contains a module name plus code evidence confirms the corresponding mechanism, write the module as a named algorithmic component.",
    ]
    latex_constraints = _latex_constraints(method_evidence)
    latex_style = _latex_style_instruction(method_evidence.latex_expression_preference.value)
    return "\n".join(
        [
            "# Phase 5 Method Authoring Prompt",
            "",
            "Use frozen Method Evidence, claim contracts, and negative scope to author the Method section.",
            "This prompt is repo-agnostic: do not assume any task/domain beyond evidence in the JSON.",
            "",
            f"- latex_expression_preference: {method_evidence.latex_expression_preference.value}",
            "",
            "## Writing Protocol",
            *[f"- {rule}" for rule in writing_rules],
            "",
            "## LaTeX Constraints",
            *[f"- {rule}" for rule in latex_constraints],
            f"- {latex_style}",
            "",
            "## Authoring View",
            "```json",
            json.dumps(authoring_view, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Claim Evidence Map",
            "```json",
            json.dumps(claim_map.model_dump(mode="json"), ensure_ascii=False, indent=2),
            "```",
            "",
            "## Output Contract",
            "- Output must be valid JSON with a single `markdown` field.",
            "- Markdown must be directly compilable by downstream formatter.",
            "- Do not include unsupported claims even if they appear in author intent.",
        ]
    )


def _run_quality_checks(
    *,
    method_evidence: MethodEvidence,
    terminology: TerminologyTable,
    markdown: str,
    latex: str,
    alignment: CodeAlignmentIR | None,
    draft_claim_map: DraftClaimMap,
    supplemental_equations_tex: str = "",
):
    claim_report = validate_claim_evidence(
        method_evidence=method_evidence,
        draft_claim_map=draft_claim_map,
    )
    numeric_report = validate_numeric_facts(
        method_evidence=method_evidence,
        draft_markdown=markdown,
        alignment=alignment,
    )
    equation_report = validate_equation_support(
        method_evidence=method_evidence,
        draft_markdown=markdown,
        draft_latex=latex,
        supplemental_equations_tex=supplemental_equations_tex,
    )
    terminology_report = validate_terminology_consistency(
        terminology_table=terminology,
        draft_markdown=markdown,
        draft_latex=latex,
    )
    latex_report = validate_latex_smoke(latex)
    return claim_report, numeric_report, equation_report, terminology_report, latex_report


def _artifact_hashes(paths: dict[str, Path], *, existing_only: bool, exclude: set[str]) -> dict[str, ArtifactHash]:
    result = {}
    for name, path in paths.items():
        if name in exclude:
            continue
        if existing_only and not path.exists():
            continue
        result[name] = ArtifactHash(path=str(path), hash=hash_file(path))
    return result


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_markdown_grounding_comments(
    *,
    markdown: str,
    draft_claim_map: DraftClaimMap,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
) -> str:
    normalized_markdown = _canonicalize_markdown_from_llm(markdown)
    normalized_markdown = _sanitize_unsupported_claim_text(
        markdown=normalized_markdown,
        claim_map=claim_map,
    )
    lines = normalized_markdown.splitlines()
    paragraphs = list(draft_claim_map.paragraphs)
    mechanism_to_stage = {
        mechanism.mechanism_id: mechanism.parent_stage_id
        for mechanism in method_evidence.frozen_mechanisms
    }
    normalized: list[str] = []
    in_math = False
    paragraph_index = 0
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped == "$$":
            in_math = not in_math
            normalized.append(line)
            continue
        if in_math:
            normalized.append(line)
            continue
        if stripped.startswith("<!-- c2p:"):
            paragraph = _paragraph_for_index(paragraphs, paragraph_index)
            if paragraph is None:
                normalized.append("<!-- c2p: stage=ALL; mechanisms=none; evidence=none; confidence=low -->")
            else:
                normalized.append(_grounding_comment_for_paragraph(paragraph, mechanism_to_stage))
            continue
        if _is_single_line_display_math(stripped):
            if not _last_non_empty_line(normalized).startswith("<!-- c2p:"):
                paragraph = _paragraph_for_index(paragraphs, paragraph_index)
                if paragraph is None:
                    normalized.append("<!-- c2p: stage=ALL; mechanisms=none; evidence=none; confidence=low -->")
                else:
                    normalized.append(_grounding_comment_for_paragraph(paragraph, mechanism_to_stage))
            normalized.append(line)
            paragraph_index += 1
            continue
        if _is_markdown_paragraph_line(stripped):
            if not _last_non_empty_line(normalized).startswith("<!-- c2p:"):
                paragraph = _paragraph_for_index(paragraphs, paragraph_index)
                if paragraph is None:
                    normalized.append("<!-- c2p: stage=ALL; mechanisms=none; evidence=none; confidence=low -->")
                else:
                    normalized.append(_grounding_comment_for_paragraph(paragraph, mechanism_to_stage))
            normalized.append(line)
            paragraph_index += 1
            continue
        normalized.append(line)
    return "\n".join(normalized).rstrip() + "\n"


def _grounding_comment_for_paragraph(
    paragraph: object,
    mechanism_to_stage: dict[str, str],
) -> str:
    mechanisms = _dedupe([mechanism_id for mechanism_id in paragraph.mechanism_ids if mechanism_id])
    evidences = _dedupe([evidence_id for evidence_id in paragraph.evidence_span_ids if evidence_id])
    stage_ids = _dedupe([mechanism_to_stage.get(mechanism_id, "") for mechanism_id in mechanisms if mechanism_to_stage.get(mechanism_id, "")])
    stage_id = "ALL" if len(stage_ids) != 1 else stage_ids[0]
    mechanism_text = ",".join(mechanisms) if mechanisms else "none"
    evidence_text = ",".join(evidences) if evidences else "none"
    confidence = "high" if evidences else "low"
    return (
        f"<!-- c2p: stage={stage_id}; mechanisms={mechanism_text}; "
        f"evidence={evidence_text}; confidence={confidence} -->"
    )


def _is_markdown_paragraph_line(line: str) -> bool:
    if not line:
        return False
    if line.startswith("#"):
        return False
    if line.startswith("- "):
        return False
    if line.startswith("<!--"):
        return False
    if line.startswith("$$"):
        return False
    if line.startswith("\\"):
        return False
    return True


def _is_single_line_display_math(line: str) -> bool:
    stripped = str(line or "").strip()
    return stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4


def _sanitize_unsupported_claim_text(*, markdown: str, claim_map: ClaimEvidenceMap) -> str:
    text = str(markdown or "")
    for claim in claim_map.claims:
        if claim.support_status.value != "unsupported":
            continue
        claim_text = str(claim.claim_text or "").strip()
        if len(claim_text) < 12:
            continue
        pattern = re.compile(re.escape(claim_text), flags=re.IGNORECASE)
        text = pattern.sub("this unsupported behavior (omitted from claim-level description)", text)
    return text


def _last_non_empty_line(lines: list[str]) -> str:
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return ""


def _paragraph_for_index(paragraphs: list[object], index: int) -> object | None:
    if not paragraphs:
        return None
    if index < 0:
        return paragraphs[0]
    if index < len(paragraphs):
        return paragraphs[index]
    return paragraphs[-1]


def _canonicalize_markdown_from_llm(markdown: str) -> str:
    text = str(markdown or "")
    text = re.sub(r"<!--\s*c2p:.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"\s+and\s+Transfer Protocol", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+with a transfer protocol", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+and downstream predictions", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+and task-specific predictions", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+before transferring the encoder for downstream tasks", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+and subsequently transfer the encoder for downstream tasks", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?im)^(\s*#+\s+.+?)\s+and\s+Transfer Protocol\s*$", r"\1", text)
    text = re.sub(
        r"(?i)\s*Following pretraining, [^.]*\b(voting|validation|testing|evaluation|downstream)\b[^.]*\.",
        "",
        text,
    )
    text = re.sub(
        r"(?i)\s*The implementation relies on a global entrypoint[^.]*\.",
        "",
        text,
    )
    text = re.sub(r"^\s*\*\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\section\*?\{([^{}]+)\}\s*$", r"# \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\subsection\*?\{([^{}]+)\}\s*$", r"## \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\subsubsection\*?\{([^{}]+)\}\s*$", r"### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\paragraph\*?\{([^{}]+)\}\s*$", r"### \1", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\begin\{equation\*?\}\s*$", "$$", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\end\{equation\*?\}\s*$", "$$", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\\[\s*$", "$$", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\\\]\s*$", "$$", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _augment_markdown_with_equation_chain(*, markdown: str, equations_tex: str) -> str:
    """Ensure core equations survive LLM compression near the text they explain."""

    equation_records = _extract_equation_tex_records(equations_tex)
    if not equation_records:
        return markdown
    existing = {_normalize_equation_text(equation) for equation in _extract_markdown_display_equations(markdown)}
    if len(existing) >= 4:
        return markdown
    missing: list[dict[str, str]] = []
    seen_missing: set[str] = set()
    present_families = {
        _equation_family(equation)
        for equation in _extract_markdown_display_equations(markdown)
        if _equation_family(equation)
    }
    for record in equation_records:
        equation = record["latex"]
        family = _equation_family(equation)
        if not _equation_family_matches_draft_context(family, markdown):
            continue
        if family and family in present_families:
            continue
        key = _normalize_equation_text(equation)
        if key in existing or key in seen_missing:
            continue
        seen_missing.add(key)
        missing.append(record)

    if not missing:
        return markdown
    max_total_equations = 6
    add_limit = max(0, max_total_equations - len(existing))
    added_records = _rank_missing_equation_records(missing)[:add_limit]
    if not added_records:
        return markdown
    return _insert_equations_into_matching_sections(markdown, added_records)


def _rank_missing_equation_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    preferred = {family: index for index, family in enumerate(_preferred_equation_families())}

    def key(record: dict[str, str]) -> tuple[int, int, str]:
        equation = record.get("latex", "")
        family = _equation_family(equation)
        source = str(record.get("source") or "").lower()
        evidence = str(record.get("evidence") or record.get("evidence_ids") or "")
        source_priority = 0 if "llm_grounded" in source else 1
        evidence_priority = 0 if evidence else 1
        family_priority = preferred.get(family, len(preferred))
        return (source_priority + evidence_priority, family_priority, str(record.get("name") or ""))

    return sorted(records, key=key)


def _extract_equation_tex_records(equations_tex: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    pending_meta: dict[str, str] = {}
    lines = str(equations_tex or "").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("%") and "|" in line:
            pending_meta = _parse_equation_meta_comment(line)
            index += 1
            continue
        if re.fullmatch(r"\\begin\{equation\*?\}", line):
            block: list[str] = []
            index += 1
            while index < len(lines) and not re.fullmatch(r"\\end\{equation\*?\}", lines[index].strip()):
                block.append(lines[index])
                index += 1
            latex = "\n".join(block).strip()
            if latex and not latex.startswith("%"):
                record = dict(pending_meta)
                record["latex"] = latex
                records.append(record)
            pending_meta = {}
        index += 1
    if records:
        return records
    return [{"latex": equation} for equation in _extract_equation_tex_blocks(equations_tex)]


def _parse_equation_meta_comment(line: str) -> dict[str, str]:
    text = str(line or "").lstrip("%").strip()
    parts = [part.strip() for part in text.split("|") if part.strip()]
    record: dict[str, str] = {}
    if parts:
        record["equation_id"] = parts[0]
    if len(parts) >= 2:
        record["name"] = parts[1]
    for part in parts[2:]:
        if "=" in part:
            key, value = part.split("=", 1)
            record[key.strip()] = value.strip()
    return record


def _insert_equations_into_matching_sections(markdown: str, records: list[dict[str, str]]) -> str:
    text = str(markdown or "").rstrip()
    if not text:
        return markdown
    inserted = text
    for record in records:
        equation = record.get("latex", "").strip()
        if not equation:
            continue
        updated = _insert_one_equation_into_best_section(inserted, record)
        if updated == inserted:
            continue
        inserted = updated
    return re.sub(r"\n{4,}", "\n\n\n", inserted).strip() + "\n"


def _insert_one_equation_into_best_section(markdown: str, record: dict[str, str]) -> str:
    equation = record.get("latex", "").strip()
    sections = _markdown_sections(markdown)
    if not sections:
        return markdown
    best: tuple[int, dict[str, int | str]] | None = None
    family = _equation_family(equation)
    for section in sections:
        score = _section_equation_match_score(section["heading"], section["body"], record, family)
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, section)
    if best is None:
        return markdown
    section = best[1]
    body_start = int(section["body_start"])
    body_end = int(section["end"])
    insert_at = _section_equation_insert_offset(markdown, body_start, body_end)
    if insert_at <= body_start:
        return markdown
    block = _equation_context_block(record)
    return markdown[:insert_at].rstrip() + "\n\n" + block.rstrip() + "\n\n" + markdown[insert_at:].lstrip()


def _markdown_sections(markdown: str) -> list[dict[str, int | str]]:
    matches = list(re.finditer(r"(?m)^(#{2,4})\s+(.+?)\s*$", markdown))
    sections: list[dict[str, int | str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections.append(
            {
                "heading": match.group(2).strip(),
                "start": match.start(),
                "body_start": match.end(),
                "end": end,
                "body": markdown[match.end():end],
            }
        )
    return sections


def _section_equation_insert_offset(markdown: str, body_start: int, body_end: int) -> int:
    body = markdown[body_start:body_end]
    paragraph_matches = list(re.finditer(r"\n\s*\n", body))
    cursor = body_start
    for separator in paragraph_matches[:4]:
        paragraph = markdown[cursor : body_start + separator.start()].strip()
        cursor = body_start + separator.end()
        visible = re.sub(r"<!--\s*c2p:.*?-->", "", paragraph, flags=re.DOTALL).strip()
        if visible and not visible.startswith("$$") and len(visible) > 80:
            return body_start + separator.end()
    visible_body = re.sub(r"<!--\s*c2p:.*?-->", "", body, flags=re.DOTALL).strip()
    if visible_body:
        return body_end
    return body_start


def _section_equation_match_score(heading: str, body: object, record: dict[str, str], family: str) -> int:
    text = f"{heading} {body} {record.get('name', '')} {record.get('role', '')} {record.get('place', '')}".lower()
    terms = _equation_section_terms(family)
    score = sum(3 for term in terms if term in text)
    placement = str(record.get("place") or "").lower()
    if placement and any(token in text for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", placement)):
        score += 4
    if "overview" in str(heading).lower() and family not in {"total_objective"}:
        score -= 2
    return score


def _equation_section_terms(family: str) -> tuple[str, ...]:
    terms = {
        "score_accumulation": ("score", "importance", "accumulation", "multi-view", "view", "footprint", "pixel"),
        "threshold_mask": ("mask", "threshold", "error", "high-error", "selection"),
        "selection_rule": ("selection", "threshold", "densification", "densify", "pruning", "prune", "active", "culling"),
        "distance_culling": ("distance", "mahalanobis", "culling", "raster", "tile", "box", "pair"),
        "photometric_loss": ("photometric", "reconstruction", "objective", "loss", "render"),
        "total_objective": ("objective", "loss", "training", "optimization"),
    }
    return terms.get(family, _equation_family_context_terms(family))


def _equation_family_context_terms(family: str) -> tuple[str, ...]:
    if not family:
        return ()
    return tuple(term for term in re.split(r"[_\W]+", family.lower()) if len(term) >= 4)


def _equation_context_block(record: dict[str, str]) -> str:
    equation = record.get("latex", "").strip()
    family = _equation_family(equation)
    role = str(record.get("role") or record.get("name") or "").strip()
    intro = _equation_intro_sentence(family, role=role)
    explanation = _equation_explanation(equation, role=role)
    return "\n".join([intro, "$$", equation, "$$", explanation])


def _equation_intro_sentence(family: str, *, role: str = "") -> str:
    intros = {
        "score_accumulation": "The score used by this stage can be written as an accumulation over the supported observations.",
        "threshold_mask": "The stage first converts the local discrepancy signal into a selection mask.",
        "selection_rule": "This score is then turned into a discrete selection rule for the affected elements.",
        "distance_culling": "The culling decision is expressed through a distance score between the element and candidate region.",
        "photometric_loss": "The corresponding training signal combines the supported reconstruction terms.",
        "total_objective": "The final objective combines the selected method losses into a single optimization target.",
    }
    if family in intros:
        return intros[family]
    if role:
        return f"The {role} can be written as the following evidence-grounded relation."
    return "The same operation can be summarized by the following evidence-grounded relation."


def _maybe_compact_display_equations(markdown: str) -> str:
    max_equations = int(os.environ.get("CODE2PAPER_PHASE5_MAX_DISPLAY_EQUATIONS", os.environ.get("CODE2PAPER_PHASE4_MAX_DISPLAY_EQUATIONS", "0")) or "0")
    if max_equations <= 0:
        return _clean_orphan_equation_explanations(markdown)
    return _compact_display_equations(markdown, max_equations=max_equations)


def _clean_orphan_equation_explanations(markdown: str) -> str:
    paragraphs = re.split(r"(\n\s*\n)", str(markdown or ""))
    cleaned: list[str] = []
    previous_was_equation = False
    for part in paragraphs:
        if not part.strip():
            cleaned.append(part)
            continue
        stripped = part.strip()
        visible = re.sub(r"<!--\s*c2p:.*?-->", "", stripped, flags=re.DOTALL).strip()
        is_comment_only = bool(stripped) and not visible
        if is_comment_only:
            cleaned.append(part)
            continue
        is_equation = visible.startswith("$$") and visible.endswith("$$")
        starts_like_explanation = bool(
            re.match(r"(?i)^(where|here|in this expression|this equation)\b", visible)
        )
        if starts_like_explanation and not previous_was_equation:
            previous_was_equation = False
            continue
        cleaned.append(part)
        previous_was_equation = is_equation
    return re.sub(r"\n{4,}", "\n\n\n", "".join(cleaned)).strip() + "\n"


def _compact_display_equations(markdown: str, *, max_equations: int) -> str:
    """Keep a paper-sized set of display equations, prioritizing method-defining operations."""

    blocks = list(re.finditer(r"\$\$\s*(.*?)\s*\$\$", str(markdown or ""), flags=re.DOTALL))
    if len(blocks) <= max_equations:
        return markdown
    ranked = sorted(
        enumerate(blocks),
        key=lambda item: (_display_equation_priority(item[1].group(1)), item[0]),
    )
    keep = {index for index, _match in ranked[:max_equations]}
    pieces: list[str] = []
    cursor = 0
    for index, match in enumerate(blocks):
        pieces.append(str(markdown or "")[cursor:match.start()])
        if index in keep:
            pieces.append(str(markdown or "")[match.start():match.end()])
            cursor = match.end()
        else:
            cursor = _skip_removed_equation_explanation(str(markdown or ""), match.end())
    pieces.append(str(markdown or "")[cursor:])
    return re.sub(r"\n{4,}", "\n\n\n", "".join(pieces)).strip() + "\n"


def _skip_removed_equation_explanation(text: str, cursor: int) -> int:
    pos = cursor
    while True:
        match = re.match(r"(\s*<!--\s*c2p:.*?-->\s*)", text[pos:], flags=re.DOTALL)
        if not match:
            break
        pos += match.end()
    match = re.match(
        r"(\s*(?:where|Here|here|In this expression|This equation)\b.*?)(?=\n\s*\n|$)",
        text[pos:],
        flags=re.DOTALL,
    )
    if match:
        return pos + match.end()
    return cursor


def _display_equation_priority(equation: str) -> int:
    lowered = str(equation or "").lower()
    priority_terms = (
        ("operatorname{fps}", 0),
        ("operatorname{knn}", 0),
        ("operatorname{sample}", 1),
        ("operatorname{group}", 1),
        ("mlp}_{\\mathrm{pos", 2),
        ("mlp_{\\mathrm{pos", 2),
        ("operatorname{mlp}_{\\mathrm{pos", 2),
        ("ffn}_{\\mathrm{pred", 3),
        ("ffn_{\\mathrm{pred", 3),
        ("operatorname{ffn}_{\\mathrm{pred", 3),
        ("operatorname{pred", 3),
        ("proj", 3),
        ("operatorname{dec}", 4),
        ("conv1d", 4),
        ("operatorname{head}", 4),
        ("chamfer", 5),
        ("\\min", 5),
        ("\\mathcal{l}_{\\mathrm{rec}", 6),
        ("\\mathcal{l}_{\\mathrm{pred}", 7),
        ("\\mathcal{l}_{\\mathrm{aux}", 7),
        ("\\mathcal{l}_{2}", 7),
        ("\\mathcal{l}_{\\mathrm{total}", 8),
        ("\\mathcal{l}=", 8),
        ("\\mathcal{l} =", 8),
    )
    for term, priority in priority_terms:
        if term in lowered:
            return priority
    if "softmax" in lowered or "attn" in lowered:
        return 30
    if "\\mathrm{pe}" in lowered or "10000" in lowered or "\\mathrm{ffn}" in lowered:
        return 31
    return 20


def _extract_equation_tex_blocks(equations_tex: str) -> list[str]:
    return [
        match.strip()
        for match in re.findall(
            r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}",
            str(equations_tex or ""),
            flags=re.DOTALL,
        )
        if match.strip() and not match.strip().startswith("%")
    ]


def _extract_markdown_display_equations(markdown: str) -> list[str]:
    equations: list[str] = []
    in_block = False
    block_lines: list[str] = []
    for raw_line in str(markdown or "").splitlines():
        line = raw_line.strip()
        single_line = re.fullmatch(r"\$\$\s*(.+?)\s*\$\$", line, flags=re.DOTALL)
        if single_line:
            equation = single_line.group(1).strip()
            if equation:
                equations.append(equation)
            continue
        if line == "$$":
            if in_block:
                equation = "\n".join(block_lines).strip()
                if equation:
                    equations.append(equation)
                block_lines = []
            in_block = not in_block
            continue
        if in_block:
            block_lines.append(raw_line)
    return equations


def _normalize_equation_text(equation: str) -> str:
    equation = re.sub(r"%.*", "", str(equation or ""))
    return re.sub(r"\s+", "", equation)


def _preferred_equation_families() -> tuple[str, ...]:
    return (
        "representation_projection",
        "residual_low_rank_projection",
        "representation_injection",
        "dual_branch_logits",
        "logit_fusion",
        "task_loss",
        "regularization_loss",
        "photometric_loss",
        "threshold_mask",
        "score_accumulation",
        "selection_rule",
        "distance_culling",
        "grouping",
        "normalization",
        "partition",
        "embedding",
        "positional_module",
        "encoder",
        "attention_transfer",
        "attention_kernel",
        "prediction",
        "stop_gradient",
        "decoder",
        "head",
        "prediction_loss",
        "reconstruction_loss",
        "set_distance",
        "total_objective",
    )


def _equation_family_matches_draft_context(family: str, markdown: str) -> bool:
    """Avoid appending generic equations from an unrelated method family."""

    text = _strip_grounding_comments(markdown).lower()
    context_terms = {
        "representation_projection": ("projection", "representation", "adapter", "residual"),
        "residual_low_rank_projection": ("low-rank", "lora", "adapter", "residual"),
        "representation_injection": ("inject", "injection", "representation"),
        "dual_branch_logits": ("branch", "logit", "fusion"),
        "logit_fusion": ("fusion", "logit", "score"),
        "task_loss": ("cross-entropy", "task", "classification", "supervised"),
        "regularization_loss": ("regularizer", "regularization", "reference"),
        "grouping": ("group", "sample", "patch", "neighborhood", "point cloud"),
        "normalization": ("normalize", "normalization", "center"),
        "partition": ("mask", "visible", "held-out", "partition"),
        "embedding": ("embed", "embedding", "token"),
        "positional_module": ("position", "positional"),
        "encoder": ("encoder", "encode"),
        "attention_transfer": ("attention", "query", "key", "value"),
        "attention_kernel": ("attention", "query", "key", "value"),
        "prediction": ("predict", "prediction", "target representation"),
        "stop_gradient": ("stop-gradient", "stop gradient", "detach"),
        "decoder": ("decoder", "decode", "reconstruct"),
        "head": ("head", "prediction head"),
        "prediction_loss": ("prediction loss", "auxiliary", "target representation"),
        "reconstruction_loss": ("reconstruction", "reconstruct", "photometric", "render"),
        "set_distance": ("chamfer", "set distance", "point set"),
        "total_objective": ("objective", "loss", "optimize", "training"),
        "photometric_loss": ("photometric", "ssim", "l1", "render"),
        "view_error_mask": ("error mask", "high-error", "view", "pixel"),
        "threshold_mask": ("mask", "threshold", "error", "high-error", "selection"),
        "score_accumulation": ("score", "importance", "multi-view", "view", "footprint", "pixel"),
        "selection_rule": ("selection", "threshold", "densification", "densify", "pruning", "prune"),
        "distance_culling": ("distance", "mahalanobis", "culling", "raster", "tile", "box"),
    }
    terms = context_terms.get(family)
    if not terms:
        return True
    return any(term in text for term in terms)


def _equation_family(equation: str) -> str:
    lowered = _normalize_equation_text(equation).lower()
    if "m^{(v)}" in lowered and "\\mathbb{1}" in lowered and "\\tau_e" in lowered:
        return "threshold_mask"
    if lowered.startswith("s_i=") and "\\sum" in lowered and ("\\mathcal{v}" in lowered or "\\omega" in lowered):
        return "score_accumulation"
    if "d_{ij}" in lowered and ("\\sigma_i^{-1}" in lowered or "\\top" in lowered or "\\tau_c" in lowered):
        return "distance_culling"
    if lowered.startswith("\\mathcal{d}=") or lowered.startswith("\\mathcal{p}=") or lowered.startswith("\\mathcal{a}="):
        return "selection_rule"
    if "ssim" in lowered and ("\\mathcal{l}" in lowered or "l_1" in lowered or "l1" in lowered):
        return "photometric_loss"
    if "m_k" in lowered and ("tau" in lowered or "loss" in lowered) and ("1" in lowered and "0" in lowered):
        return "view_error_mask"
    if "r^{(\\ell)}" in lowered and ("a^{(\\ell)}_t" in lowered or "a^{(\\ell)}_v" in lowered):
        return "representation_projection"
    if "u^{(\\ell)}v^{(\\ell)}" in lowered or "w+u" in lowered:
        return "residual_low_rank_projection"
    if "operatorname{inject}" in lowered:
        return "representation_injection"
    if "\\bar{f}_{\\mathrm{img}}" in lowered or "\\bar{f}_{\\mathrm{rep}}" in lowered:
        return "dual_branch_logits"
    if "s_{\\mathrm{fuse}}" in lowered:
        return "logit_fusion"
    if "operatorname{ce}" in lowered or "\\mathcal{l}_{\\mathrm{task}}" in lowered:
        return "task_loss"
    if "\\mathcal{l}_{\\mathrm{reg}}" in lowered or "\\cos(" in lowered:
        return "regularization_loss"
    if "operatorname{sample}" in lowered or "operatorname{group}" in lowered:
        return "grouping"
    if "\\bar{p}" in lowered or "-c_{" in lowered or "-c_i" in lowered:
        return "normalization"
    if "\\cup" in lowered and "\\cap" in lowered:
        return "partition"
    if "operatorname{embed}" in lowered or "pointnet" in lowered:
        return "embedding"
    if "operatorname{pem}" in lowered or "operatorname{pe}" in lowered:
        return "positional_module"
    if "operatorname{enc}" in lowered:
        return "encoder"
    if "operatorname{attn}" in lowered and ("[z_v" in lowered or "x_m" in lowered or "q_m" in lowered):
        return "attention_transfer"
    if "softmax" in lowered and "qk" in lowered:
        return "attention_kernel"
    if "operatorname{pred}" in lowered:
        return "prediction"
    if "operatorname{sg}" in lowered or "detach" in lowered or "stop" in lowered:
        return "stop_gradient"
    if "operatorname{dec}" in lowered:
        return "decoder"
    if "operatorname{head}" in lowered:
        return "head"
    if "\\mathcal{l}_{\\mathrm{rec}}" in lowered:
        return "reconstruction_loss"
    if "\\mathcal{l}_{\\mathrm{aux}}" in lowered or "\\mathcal{l}_{\\mathrm{pred}}" in lowered:
        return "prediction_loss"
    if "\\min" in lowered and "\\sum" in lowered and "\\lVert" in lowered:
        return "set_distance"
    if lowered.startswith("\\mathcal{l}=") or lowered.startswith("\\mathcal{l} ="):
        return "total_objective"
    return ""


def _equation_explanation(equation: str, *, role: str = "") -> str:
    family = _equation_family(equation)
    explanations = {
        "representation_projection": "Here, a learned projection maps an intermediate representation into the space required by the next computation block.",
        "residual_low_rank_projection": "Here, the projection adapts a base weight with a low-rank residual update.",
        "representation_injection": "Here, an auxiliary representation is inserted or mixed into the hidden sequence with coefficient $\\beta$.",
        "dual_branch_logits": "Here, two feature branches produce comparable scores before later selection or fusion.",
        "logit_fusion": "Here, the final score interpolates two branch scores through coefficient $\\alpha$.",
        "task_loss": "Here, the task objective combines supervised losses from the available prediction branches.",
        "regularization_loss": "Here, the regularizer constrains adapted features relative to a reference representation.",
        "grouping": "Here, the input sample is organized into local or structured groups before later processing.",
        "normalization": "Here, each grouped observation is normalized so that the following module receives a stable local representation.",
        "partition": "Here, the observed and held-out subsets form a disjoint partition used by the self-supervised pipeline.",
        "embedding": "Here, the embedding map converts grouped observations into token-level or feature-level representations.",
        "positional_module": "Here, positional or structural features are encoded and transformed before being used by later blocks.",
        "encoder": "Here, the encoder maps the available input representation into a latent state.",
        "attention_transfer": "Here, a query stream gathers context from another available feature stream through attention.",
        "attention_kernel": "Here, attention uses the standard scaled dot-product kernel over query, key, and value matrices.",
        "prediction": "Here, the prediction module estimates a target representation from the encoded context.",
        "stop_gradient": "Here, $\\operatorname{sg}(\\cdot)$ denotes a stop-gradient copy used when the predicted condition is passed to the decoder.",
        "decoder": "Here, the decoder reconstructs an output from the latent representation and any predicted conditioning signal.",
        "head": "Here, the prediction head maps decoder features back into the output space supervised by reconstruction.",
        "prediction_loss": "Here, the prediction term aligns the estimated representation with its target.",
        "reconstruction_loss": "Here, the reconstruction term measures discrepancy between decoded held-out outputs and their targets.",
        "set_distance": "Here, $d(A,B)$ denotes a bidirectional discrepancy between two unordered sets.",
        "total_objective": "Here, the total objective combines the primary task objective with the weighted auxiliary or regularization term.",
        "photometric_loss": "Here, the photometric objective combines pixel-level reconstruction error with a structural similarity term.",
        "view_error_mask": "Here, the binary mask selects pixels whose normalized reconstruction error exceeds the chosen threshold.",
        "threshold_mask": "Here, $e^{(v)}(p)$ denotes the discrepancy at position $p$ in observation $v$, and the indicator keeps only positions above the evidence threshold.",
        "score_accumulation": "Here, $\\Omega_i^{(v)}$ is the region associated with element $i$ under observation $v$, so $S_i$ grows when the element is repeatedly implicated by the mask.",
        "selection_rule": "Here, the threshold turns the continuous score into the selected set used by the corresponding update or culling step.",
        "distance_culling": "Here, $u_j$ denotes a candidate region or tile representative, while $\\mu_i$ and $\\Sigma_i$ define the element-local distance geometry.",
    }
    if family in explanations:
        return explanations[family]
    if role:
        return f"Here, the symbols denote the quantities used for {role} in the surrounding method text."
    return "Here, the symbols follow the notation introduced in the surrounding method text."


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
