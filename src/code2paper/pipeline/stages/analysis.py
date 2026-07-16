"""Phase 2 Analysis: story-first code analysis with embedded CodeAnalyzerAgent."""

from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
from typing import Any

from code2paper.agents.bridge import (
    _build_code_method_analysis_payload,
    _build_raw_pack_from_snippets,
    _filter_postergen_outputs,
    _filter_raw_pack,
)
from code2paper.agents.code_analyzer import CodeAnalyzerAgent
from code2paper.agents.state.poster_state import create_state
from code2paper.analysis.alignment import align_code
from code2paper.core.author_questionnaire import load_author_markers
from code2paper.export.run_manifest import hash_file
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    AlignedModuleRole,
    AuthorAlignment,
    ArtifactHash,
    CodeAlignmentIR,
    CodeMethodAnalysis,
    Entrypoint,
    ExecutionStage,
    LLMConfig,
    LLMProvider,
    MethodStageAlignment,
    ModuleCategory,
    Phase2Manifest,
    RawEvidencePack,
    StageMapping,
)
from code2paper.core.story_first import to_method_summary, to_structured_sections


def run_phase2_analysis(
    *,
    project_root: Path,
    method_root: Path,
    author_markers_path: str,
    llm_config: LLMConfig,
    project_id: str | None = None,
    evidence_repair_focus: dict[str, Any] | None = None,
) -> tuple[CodeAlignmentIR, dict[str, Path]]:
    method_root.mkdir(parents=True, exist_ok=True)
    agent_root = method_root / "agent_workspace" / "code_analyzer"
    agent_root.mkdir(parents=True, exist_ok=True)

    author_markers = load_author_markers(author_markers_path)
    project_id_value = project_id or project_root.name.replace("-", "_")
    core_snippets = _read_json(method_output(method_root, "snippets"))
    code_sources = _read_json(method_output(method_root, "sources"))
    method_code_alignment = _read_json(method_output(method_root, "intake_alignment"))
    code_intake_report = _read_json(method_output(method_root, "intake_report"))

    state = create_state(
        pdf_path=str(Path(author_markers_path).resolve()),
        text_model=llm_config.model or "gpt-4.1-mini",
        vision_model=llm_config.model or "gpt-4.1-mini",
        width=54,
        height=36,
        output_dir=str(agent_root),
        poster_name="code2paper_code_analyzer",
        text_provider=_state_provider(llm_config),
        vision_provider=_state_provider(llm_config),
    )
    state["repo_path"] = str(project_root)
    state["code_sources"] = code_sources
    state["core_snippets"] = core_snippets
    state["method_code_alignment"] = method_code_alignment
    state["code_intake_report"] = code_intake_report
    state["method_experiment_structured_summary"] = to_method_summary(author_markers)
    if evidence_repair_focus:
        state["agentic_evidence_repair_focus"] = evidence_repair_focus
        state["method_experiment_structured_summary"] = _merge_repair_focus(
            state["method_experiment_structured_summary"],
            evidence_repair_focus,
        )
    state["structured_sections"] = to_structured_sections(author_markers)
    state["paper_objects"] = {}
    state["dynamic_roles"] = _dynamic_roles(method_code_alignment)
    state["enable_code_analyzer_llm"] = llm_config.provider != LLMProvider.NONE

    state = CodeAnalyzerAgent()(state)
    _raise_agent_errors(state)

    code_facts = state.get("code_facts") or _read_json(agent_root / "content" / "code_facts.json")
    code_ir = state.get("code_ir") or _read_json(agent_root / "content" / "code_ir.json")
    entity_links = state.get("entity_links") or _read_json(agent_root / "content" / "entity_links.json")
    code_analysis_report = state.get("code_analysis_report") or _read_json(agent_root / "content" / "code_analysis_report.json")

    code_sources, core_snippets, code_facts, _removed = _filter_postergen_outputs(
        repo=project_root,
        author_markers=author_markers,
        code_sources=code_sources,
        core_snippets=core_snippets,
        code_facts=code_facts,
    )
    raw_pack, snippet_to_evidence = _build_raw_pack_from_snippets(
        repo=project_root,
        author_markers=author_markers,
        core_snippets=core_snippets,
        project_id=project_id_value,
    )
    raw_pack = _filter_raw_pack(raw_pack, repo=project_root, author_markers=author_markers)
    base_alignment = CodeAlignmentIR.model_validate(align_code(raw_pack, author_markers=author_markers).model_dump(mode="json"))
    analysis_payload = _build_code_method_analysis_payload(
        code_facts=code_facts,
        core_snippets=core_snippets,
        author_markers=author_markers,
        snippet_to_evidence=snippet_to_evidence,
        raw_pack=raw_pack,
    )
    analysis = CodeMethodAnalysis.model_validate(analysis_payload)
    alignment = _merge_alignment_with_scan_outputs(
        base_alignment=base_alignment,
        raw_pack=raw_pack,
        code_method_analysis=analysis,
        code_facts=code_facts,
        author_markers=author_markers,
    )

    paths = {
        "evidence_raw": method_output(method_root, "evidence_raw"),
        "alignment": method_output(method_root, "alignment"),
        "analysis": method_output(method_root, "analysis"),
        "facts": method_output(method_root, "facts"),
        "code_graph": method_output(method_root, "code_graph"),
        "entity_map": method_output(method_root, "entity_map"),
        "analysis_report": method_output(method_root, "analysis_report"),
        "evidence_index": method_output(method_root, "evidence_index"),
        "phase2_manifest": method_output(method_root, "phase2_manifest"),
    }
    _write_json(paths["evidence_raw"], raw_pack.model_dump(mode="json"))
    _write_json(paths["alignment"], alignment.model_dump(mode="json"))
    _write_json(paths["analysis"], analysis.model_dump(mode="json"))
    _write_json(paths["facts"], code_facts)
    _write_json(paths["code_graph"], code_ir)
    _write_json(paths["entity_map"], entity_links)
    _write_json(paths["analysis_report"], code_analysis_report)
    _write_json(paths["evidence_index"], snippet_to_evidence)
    if evidence_repair_focus:
        paths["analysis_repair_focus"] = method_output(method_root, "analysis_repair_focus")
        _write_json(paths["analysis_repair_focus"], evidence_repair_focus)
        paths["analysis_repair_tasks"] = method_output(method_root, "analysis_repair_tasks")
        _write_json(
            paths["analysis_repair_tasks"],
            _build_analysis_repair_tasks(
                focus=evidence_repair_focus,
                core_snippets=core_snippets,
                snippet_to_evidence=snippet_to_evidence,
            ),
        )

    outputs = {
        name: ArtifactHash(path=str(path), hash=hash_file(path))
        for name, path in paths.items()
        if name != "phase2_manifest"
    }
    manifest = Phase2Manifest(
        project_id=project_id_value,
        llm_required=False,
        llm_available=llm_config.provider != LLMProvider.NONE,
        mode="story-first-code-analyzer",
        prompt_template_version=llm_config.prompt_template_version or "story-first-code-agents-v1",
        outputs=outputs,
        llm_call_logs=[],
        blocked_report="",
    )
    _write_json(paths["phase2_manifest"], manifest.model_dump(mode="json"))
    return alignment, paths


def _dynamic_roles(method_code_alignment: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    for role in method_code_alignment.get("dynamic_roles", []) if isinstance(method_code_alignment, dict) else []:
        if isinstance(role, str) and role.strip():
            roles.append(role.strip())
    return roles


def _state_provider(llm_config: LLMConfig) -> str:
    return llm_config.provider.value if llm_config.provider != LLMProvider.NONE else "openai"


def _merge_repair_focus(method_summary: dict[str, Any], focus: dict[str, Any]) -> dict[str, Any]:
    merged = dict(method_summary)
    retrieval_hints = merged.get("retrieval_hints") if isinstance(merged.get("retrieval_hints"), dict) else {}
    hints = dict(retrieval_hints)
    hints["search_keywords"] = _dedupe_strings(
        _as_string_list(hints.get("search_keywords")) + _as_string_list(focus.get("search_keywords"))
    )
    hints["claim_queries"] = _dedupe_strings(
        _as_string_list(hints.get("claim_queries")) + _as_string_list(focus.get("claim_queries"))
    )
    hints["focus_claim_ids"] = _dedupe_strings(
        _as_string_list(hints.get("focus_claim_ids")) + _as_string_list(focus.get("focus_claim_ids"))
    )
    hints["priority_paths"] = _dedupe_strings(
        _as_string_list(hints.get("priority_paths")) + _as_string_list(focus.get("priority_paths"))
    )
    hints["claim_support_files"] = _dedupe_strings(
        _as_string_list(hints.get("claim_support_files")) + _as_string_list(focus.get("claim_support_files"))
    )
    symbol_targets = [
        item
        for item in [
            *(hints.get("symbol_targets") or []),
            *(focus.get("symbol_targets") or []),
        ]
        if isinstance(item, dict)
    ]
    claim_targets = [
        item
        for item in [
            *(hints.get("claim_targets") or []),
            *(focus.get("claim_targets") or []),
        ]
        if isinstance(item, dict)
    ]
    if symbol_targets:
        hints["symbol_targets"] = symbol_targets[:80]
    if claim_targets:
        hints["claim_targets"] = claim_targets[:80]
    merged["retrieval_hints"] = {key: value for key, value in hints.items() if value}
    merged["agentic_evidence_repair_focus"] = focus
    return merged


def _build_analysis_repair_tasks(
    *,
    focus: dict[str, Any],
    core_snippets: dict[str, Any],
    snippet_to_evidence: dict[str, str],
) -> dict[str, Any]:
    claim_targets = [item for item in focus.get("claim_targets", []) if isinstance(item, dict)]
    snippet_records = _snippet_records(core_snippets)
    tasks: list[dict[str, Any]] = []
    for target in claim_targets:
        claim_id = str(target.get("claim_id") or "").strip()
        if not claim_id:
            continue
        candidates = [
            _repair_candidate_task(candidate, snippet_records=snippet_records, snippet_to_evidence=snippet_to_evidence)
            for candidate in target.get("candidates", [])
            if isinstance(candidate, dict)
        ]
        tasks.append(
            {
                "claim_id": claim_id,
                "claim_query": str(target.get("claim_query") or "").strip(),
                "issue_types": _claim_issue_types(claim_id, focus),
                "candidate_count": len(candidates),
                "candidates_with_existing_evidence": sum(1 for candidate in candidates if candidate["evidence_ids"]),
                "recommended_next": "reassess_existing_evidence" if any(candidate["evidence_ids"] for candidate in candidates) else "rescan_candidate_code",
                "candidates": candidates,
            }
        )
    return {
        "mode": "agentic-analysis-repair-tasks",
        "source_focus_mode": str(focus.get("mode") or ""),
        "source_decision": str(focus.get("source_decision") or ""),
        "focus_claim_ids": _dedupe_strings(_as_string_list(focus.get("focus_claim_ids"))),
        "task_count": len(tasks),
        "candidate_count": sum(len(task["candidates"]) for task in tasks),
        "priority_paths": _dedupe_strings(_as_string_list(focus.get("priority_paths"))),
        "symbol_targets": [item for item in focus.get("symbol_targets", []) if isinstance(item, dict)],
        "recommended_actions": _dedupe_strings(_as_string_list(focus.get("recommended_actions"))),
        "tasks": tasks,
    }


def _repair_candidate_task(
    candidate: dict[str, Any],
    *,
    snippet_records: list[dict[str, Any]],
    snippet_to_evidence: dict[str, str],
) -> dict[str, Any]:
    path = str(candidate.get("path") or "").strip()
    symbol = str(candidate.get("symbol") or "").strip()
    matched_snippets = [
        record["snippet_id"]
        for record in snippet_records
        if _candidate_matches_snippet(candidate, record)
    ]
    evidence_ids = _dedupe_strings(
        [snippet_to_evidence[snippet_id] for snippet_id in matched_snippets if snippet_id in snippet_to_evidence]
    )
    return {
        "path": path,
        "symbol": symbol,
        "kind": str(candidate.get("kind") or "").strip(),
        "start_line": _positive_int(candidate.get("start_line")),
        "end_line": _positive_int(candidate.get("end_line")),
        "score": _float_or_zero(candidate.get("score")),
        "reasons": _dedupe_strings(_as_string_list(candidate.get("reasons")))[:12],
        "matched_snippet_ids": matched_snippets,
        "evidence_ids": evidence_ids,
        "coverage_status": "existing_evidence" if evidence_ids else "needs_rescan",
    }


def _snippet_records(core_snippets: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    snippets = core_snippets.get("snippets", []) if isinstance(core_snippets.get("snippets"), list) else []
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        snippet_id = str(snippet.get("snippet_id") or "").strip()
        path = str(source.get("path") or snippet.get("path") or "").strip()
        if not snippet_id or not path:
            continue
        records.append(
            {
                "snippet_id": snippet_id,
                "path": _norm_path(path),
                "symbol": str(source.get("symbol") or snippet.get("symbol") or "").strip(),
                "start_line": _positive_int(source.get("start_line") or source.get("line_start") or snippet.get("start_line") or snippet.get("line_start")),
                "end_line": _positive_int(source.get("end_line") or source.get("line_end") or snippet.get("end_line") or snippet.get("line_end")),
            }
        )
    return records


def _candidate_matches_snippet(candidate: dict[str, Any], snippet: dict[str, Any]) -> bool:
    candidate_path = _norm_path(str(candidate.get("path") or ""))
    snippet_path = _norm_path(str(snippet.get("path") or ""))
    if not candidate_path or not snippet_path:
        return False
    if candidate_path != snippet_path and not snippet_path.endswith("/" + candidate_path):
        return False
    candidate_symbol = str(candidate.get("symbol") or "").strip()
    snippet_symbol = str(snippet.get("symbol") or "").strip()
    if candidate_symbol and snippet_symbol and candidate_symbol != snippet_symbol:
        return False
    return _line_spans_overlap(
        _positive_int(candidate.get("start_line")),
        _positive_int(candidate.get("end_line")),
        _positive_int(snippet.get("start_line")),
        _positive_int(snippet.get("end_line")),
    )


def _line_spans_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    if start_a <= 0 or end_a <= 0 or start_b <= 0 or end_b <= 0:
        return True
    return max(start_a, start_b) <= min(end_a, end_b)


def _claim_issue_types(claim_id: str, focus: dict[str, Any]) -> list[str]:
    issue_types: list[str] = []
    if claim_id in _as_string_list(focus.get("missing_evidence_claim_ids")):
        issue_types.append("missing_evidence")
    if claim_id in _as_string_list(focus.get("unsupported_claim_ids")):
        issue_types.append("unsupported")
    if claim_id in _as_string_list(focus.get("caveated_claim_ids")):
        issue_types.append("caveated")
    return issue_types or ["review"]


def _norm_path(path: str) -> str:
    return str(Path(path)).replace("\\", "/").lstrip("./")


def _positive_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _float_or_zero(value: object) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def _raise_agent_errors(state: dict[str, Any]) -> None:
    errors = [str(item) for item in state.get("errors", []) if str(item).strip()]
    if errors:
        raise RuntimeError("; ".join(errors[:8]))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _merge_alignment_with_scan_outputs(
    *,
    base_alignment: CodeAlignmentIR,
    raw_pack: RawEvidencePack,
    code_method_analysis: CodeMethodAnalysis,
    code_facts: dict[str, Any],
    author_markers: Any,
) -> CodeAlignmentIR:
    method_stages = _merged_method_stages(base_alignment, code_method_analysis, code_facts)
    execution_stages = _merged_execution_stages(base_alignment, method_stages)
    stage_mappings = _merged_stage_mappings(base_alignment, execution_stages, method_stages)
    module_roles = _merged_module_roles(base_alignment, code_method_analysis)
    entrypoints = _merged_entrypoints(base_alignment, raw_pack, author_markers)
    author_alignment = _merged_author_alignment(
        base_alignment=base_alignment,
        method_stages=method_stages,
        code_method_analysis=code_method_analysis,
        author_markers=author_markers,
    )
    return CodeAlignmentIR(
        project_id=base_alignment.project_id,
        author_mode=base_alignment.author_mode,
        author_confirmation_required=base_alignment.author_confirmation_required,
        entrypoints=entrypoints,
        execution_stages=execution_stages,
        method_stages=method_stages,
        stage_mappings=stage_mappings,
        config_resolutions=base_alignment.config_resolutions,
        module_roles=module_roles,
        role_conflicts=base_alignment.role_conflicts,
        author_alignment=author_alignment,
    )


def _merged_method_stages(
    base_alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis,
    code_facts: dict[str, Any],
) -> list[MethodStageAlignment]:
    stage_records = _scan_stage_records(code_method_analysis=code_method_analysis, code_facts=code_facts)
    if not stage_records:
        return list(base_alignment.method_stages)
    merged = list(base_alignment.method_stages)
    seen = {_normalize_stage_name(stage.name) for stage in merged}
    next_index = len(merged) + 1
    for record in stage_records:
        normalized = _normalize_stage_name(record["name"])
        if normalized in seen:
            continue
        merged.append(
            MethodStageAlignment(
                stage_id=f"M{next_index}",
                name=record["name"],
                purpose=record["purpose"],
                related_evidence_ids=record["evidence_ids"],
            )
        )
        seen.add(normalized)
        next_index += 1
    return merged


def _merged_execution_stages(
    base_alignment: CodeAlignmentIR,
    method_stages: list[MethodStageAlignment],
) -> list[ExecutionStage]:
    if base_alignment.execution_stages:
        return list(base_alignment.execution_stages)
    stages: list[ExecutionStage] = []
    for index, method_stage in enumerate(method_stages, start=1):
        stages.append(
            ExecutionStage(
                stage_id=f"X{index}",
                name=f"scan_stage_{index}",
                description=method_stage.purpose,
                related_evidence_ids=method_stage.related_evidence_ids,
            )
        )
    return stages


def _merged_stage_mappings(
    base_alignment: CodeAlignmentIR,
    execution_stages: list[ExecutionStage],
    method_stages: list[MethodStageAlignment],
) -> list[StageMapping]:
    if base_alignment.stage_mappings:
        return list(base_alignment.stage_mappings)
    count = min(len(execution_stages), len(method_stages))
    return [
        StageMapping(
            execution_stage_id=execution_stages[index].stage_id,
            method_stage_id=method_stages[index].stage_id,
            confidence=0.82,
        )
        for index in range(count)
    ]


def _merged_module_roles(
    base_alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis,
) -> list[AlignedModuleRole]:
    merged = list(base_alignment.module_roles)
    seen = {(role.path, role.symbol, role.role) for role in merged}
    for module in code_method_analysis.method_modules:
        category = module.module_class if isinstance(module.module_class, ModuleCategory) else ModuleCategory(module.module_class)
        confidence = _module_confidence_score(module.llm_confidence)
        symbols = list(module.symbols) or [""]
        for symbol in symbols:
            key = (module.path, symbol, module.paper_role)
            if key in seen:
                continue
            merged.append(
                AlignedModuleRole(
                    path=module.path,
                    symbol=symbol,
                    role=module.paper_role,
                    category=category,
                    confidence=confidence,
                    evidence_ids=list(module.evidence_span_ids),
                )
            )
            seen.add(key)
    return merged


def _merged_entrypoints(
    base_alignment: CodeAlignmentIR,
    raw_pack: RawEvidencePack,
    author_markers: Any,
) -> list[Entrypoint]:
    if base_alignment.entrypoints:
        return list(base_alignment.entrypoints)
    evidence_by_path = {}
    for item in raw_pack.evidence_items:
        evidence_by_path.setdefault(item.path, []).append(item.evidence_id)
    entrypoints: list[Entrypoint] = []
    seen: set[tuple[str, str]] = set()
    for role in getattr(author_markers, "module_roles", []):
        path = str(getattr(role, "path", "") or "").strip()
        symbol = str(getattr(role, "symbol", "") or "").strip()
        if not path:
            continue
        if "main" not in symbol.lower() and "entry" not in str(getattr(role, "role", "") or "").lower():
            continue
        key = (path, symbol or "main")
        if key in seen:
            continue
        entrypoints.append(
            Entrypoint(
                path=path,
                symbol=symbol or "main",
                called_by=[],
                confidence=0.72,
                evidence_ids=list(evidence_by_path.get(path, []))[:20],
            )
        )
        seen.add(key)
    return entrypoints


def _merged_author_alignment(
    *,
    base_alignment: CodeAlignmentIR,
    method_stages: list[MethodStageAlignment],
    code_method_analysis: CodeMethodAnalysis,
    author_markers: Any,
) -> AuthorAlignment:
    base = base_alignment.author_alignment
    story_order = list(base.author_story_order) or [str(name) for name in getattr(author_markers, "paper_story_order", []) if str(name).strip()]
    stage_ids_by_name = {stage.stage_id: stage.name for stage in method_stages}
    preferred_ids = list(base.preferred_method_stage_ids)
    matched_steps = list(base.matched_steps)
    mismatched_steps = list(base.mismatched_steps)
    supported_scan_steps = [
        str(name)
        for name in code_method_analysis.author_alignment.author_supported_flow
        if str(name).strip()
    ]
    if story_order:
        rematched: list[str] = []
        remismatched: list[str] = []
        resolved_ids: list[str] = []
        for story_step in story_order:
            stage_id = _best_matching_stage_id(story_step, method_stages)
            if stage_id:
                rematched.append(story_step)
                resolved_ids.append(stage_id)
            else:
                remismatched.append(story_step)
        matched_steps = _dedupe_strings(matched_steps + rematched)
        mismatched_steps = [step for step in _dedupe_strings(remismatched + mismatched_steps) if step not in matched_steps]
        preferred_ids = _dedupe_strings(preferred_ids + resolved_ids)
    elif supported_scan_steps:
        preferred_ids = _dedupe_strings(
            preferred_ids + [stage_id for stage_id, stage_name in stage_ids_by_name.items() if stage_name in supported_scan_steps]
        )
    return AuthorAlignment(
        matched_steps=matched_steps,
        mismatched_steps=mismatched_steps,
        unsupported_claims=list(base.unsupported_claims),
        author_story_order=story_order,
        preferred_method_stage_ids=preferred_ids,
        latex_expression_preference=base.latex_expression_preference,
        claim_assessments=list(base.claim_assessments),
    )


def _scan_stage_records(
    *,
    code_method_analysis: CodeMethodAnalysis,
    code_facts: dict[str, Any],
) -> list[dict[str, Any]]:
    step_by_name = {}
    for step in code_facts.get("pipeline_steps", []) if isinstance(code_facts.get("pipeline_steps"), list) else []:
        if not isinstance(step, dict):
            continue
        name = str(step.get("name") or "").strip()
        if not name:
            continue
        step_by_name[_normalize_stage_name(name)] = step
    records: list[dict[str, Any]] = []
    ordered_names: list[str] = []
    for name in code_method_analysis.author_alignment.author_supported_flow:
        text = str(name).strip()
        if text:
            ordered_names.append(text)
    if not ordered_names:
        for flow in code_method_analysis.execution_flows:
            ordered_names.extend(str(step).strip() for step in flow.ordered_steps if str(step).strip())
    ordered_names = _dedupe_strings(ordered_names)
    for name in ordered_names:
        mechanism = _best_matching_mechanism(name, code_method_analysis)
        step = step_by_name.get(_normalize_stage_name(name), {})
        if mechanism is None and not step:
            continue
        evidence_ids: list[str] = []
        purpose = ""
        if mechanism is not None:
            evidence_ids = list(mechanism.supporting_span_ids)
            purpose = str(mechanism.description or "").strip()
        if not purpose:
            purpose = str(step.get("description") or "").strip()
        if not evidence_ids:
            evidence_ids = _evidence_ids_from_step(step, code_method_analysis)
        records.append(
            {
                "name": name,
                "purpose": purpose or f"Recovered paper-facing stage for {name}.",
                "evidence_ids": _dedupe_strings(evidence_ids),
            }
        )
    return [record for record in records if record["evidence_ids"]]


def _best_matching_mechanism(stage_name: str, code_method_analysis: CodeMethodAnalysis):
    best = None
    best_score = 0.0
    for mechanism in code_method_analysis.candidate_mechanisms:
        score = _stage_similarity(stage_name, mechanism.name)
        if score > best_score:
            best = mechanism
            best_score = score
    return best if best_score >= 0.34 else None


def _evidence_ids_from_step(step: dict[str, Any], code_method_analysis: CodeMethodAnalysis) -> list[str]:
    name = str(step.get("name") or "").strip()
    mechanism = _best_matching_mechanism(name, code_method_analysis) if name else None
    if mechanism is not None:
        return list(mechanism.supporting_span_ids)
    return []


def _best_matching_stage_id(story_step: str, method_stages: list[MethodStageAlignment]) -> str:
    best_id = ""
    best_score = 0.0
    for stage in method_stages:
        score = _stage_similarity(story_step, stage.name)
        if score > best_score:
            best_id = stage.stage_id
            best_score = score
    return best_id if best_score >= 0.34 else ""


def _stage_similarity(left: str, right: str) -> float:
    left_norm = _normalize_stage_name(left)
    right_norm = _normalize_stage_name(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92
    left_terms = set(left_norm.split())
    right_terms = set(right_norm.split())
    term_overlap = len(left_terms & right_terms) / max(1, min(len(left_terms), len(right_terms)))
    seq = SequenceMatcher(None, left_norm, right_norm).ratio()
    if _looks_like_training_stage(left_terms) and _looks_like_training_stage(right_terms):
        term_overlap += 0.15
    if _looks_like_inference_stage(left_terms) and _looks_like_inference_stage(right_terms):
        term_overlap += 0.15
    if _looks_like_config_stage(left_terms) and _looks_like_config_stage(right_terms):
        term_overlap += 0.15
    if _looks_like_representation_stage(left_terms) and _looks_like_representation_stage(right_terms):
        term_overlap += 0.15
    if _looks_like_transformer_stage(left_terms) and _looks_like_transformer_stage(right_terms):
        term_overlap += 0.15
    return min(1.0, max(term_overlap, seq * 0.6 + term_overlap * 0.4))


def _normalize_stage_name(value: str) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").lower().split())


def _module_confidence_score(value: Any) -> float:
    lowered = str(value or "").strip().lower()
    if lowered == "high":
        return 0.9
    if lowered == "low":
        return 0.6
    return 0.75


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _looks_like_training_stage(terms: set[str]) -> bool:
    return bool(terms & {"training", "objective", "optimization", "regularized", "loss", "branch", "scoring", "train"})


def _looks_like_inference_stage(terms: set[str]) -> bool:
    return bool(terms & {"inference", "evaluation", "prediction", "protocol", "report", "task"})


def _looks_like_config_stage(terms: set[str]) -> bool:
    return bool(terms & {"configuration", "config", "setup", "assembly", "loading", "launcher", "override"})


def _looks_like_representation_stage(terms: set[str]) -> bool:
    return bool(terms & {"shared", "representation", "projection", "aligner", "align", "modality"})


def _looks_like_transformer_stage(terms: set[str]) -> bool:
    return bool(terms & {"interaction", "transformer", "compose"})
