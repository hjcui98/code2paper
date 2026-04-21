"""Phase 3 method evidence freeze.

This module compresses Phase 2 code-method analysis into a writing-ready,
auditable Method Evidence IR. The older CodeAlignmentIR path is retained as a
compatibility fallback for downstream Phase 4 code.
"""

from __future__ import annotations

import json
import os
import ast
from pathlib import Path

from .schemas import (
    AlignedModuleRole,
    AuthorMode,
    AuthorLogicMapping,
    ClaimContract,
    CodeAlignmentIR,
    CodeMethodAnalysis,
    CodeMethodModule,
    ConfidenceLevel,
    ConflictStatus,
    FrozenMechanism,
    LLMConfig,
    MethodImplementationAnchor,
    MethodEvidence,
    MethodModule,
    MethodStageAlignment,
    MethodStageEvidence,
    Mechanism,
    ModuleCategory,
    Phase3Manifest,
    RawEvidencePack,
    SubMechanism,
    SupportStatus,
    ArtifactHash,
)
from .symbol_behavior_extractor import extract_symbol_mechanisms
from .export.run_manifest import hash_file
from .user_focus import is_boilerplate_text, load_focus_terms, relevance_score

PHASE3_COMMENT_INSIGHT_CLAIM_LIMIT = int(os.environ.get("CODE2PAPER_PHASE3_COMMENT_INSIGHT_CLAIM_LIMIT", "120"))


def build_method_evidence(
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None = None,
) -> MethodEvidence:
    """Build a conservative MethodEvidence object from raw and alignment IR."""

    ordered_method_stages = _ordered_method_stages(
        alignment=alignment,
        code_method_analysis=code_method_analysis,
    )
    modules_by_stage = _modules_by_method_stage(alignment)
    symbol_mechanisms = extract_symbol_mechanisms(raw_pack, alignment)
    stages: list[MethodStageEvidence] = []
    mechanism_counter = 1

    for index, method_stage in enumerate(ordered_method_stages, start=1):
        stage_id = f"S{index}"
        modules = modules_by_stage.get(method_stage.stage_id, [])
        method_modules = _analysis_modules_for_stage(
            code_method_analysis=code_method_analysis,
            evidence_ids=method_stage.related_evidence_ids,
        ) or [_to_method_module(role) for role in modules]
        analysis_mechanisms = _analysis_mechanisms_for_stage(
            code_method_analysis=code_method_analysis,
            method_stage=method_stage,
            stage_id=stage_id,
            start_index=mechanism_counter,
            author_mode=raw_pack.author_mode,
            submechanisms=symbol_mechanisms.submechanisms,
        )
        if analysis_mechanisms:
            mechanisms = analysis_mechanisms
            mechanism_counter += len(analysis_mechanisms)
        else:
            mechanism = _mechanism_for_stage(
                method_stage,
                stage_id=stage_id,
                mechanism_id=f"MECH{mechanism_counter}",
                evidence_ids=method_stage.related_evidence_ids,
                author_mode=raw_pack.author_mode,
                submechanisms=_submechanisms_for_evidence(symbol_mechanisms.submechanisms, method_stage.related_evidence_ids),
            )
            mechanisms = [mechanism]
            mechanism_counter += 1
        stage_io = _analysis_stage_io(code_method_analysis=code_method_analysis, stage_name=method_stage.name)
        stages.append(
            MethodStageEvidence(
                stage_id=stage_id,
                name=_human_stage_name(method_stage.name),
                purpose=method_stage.purpose,
                inputs=stage_io.get("inputs") or _stage_inputs(method_stage.name),
                outputs=stage_io.get("outputs") or _stage_outputs(method_stage.name),
                modules=method_modules,
                mechanisms=mechanisms,
            )
        )

    phase3_freeze = _phase3_freeze_fields(
        raw_pack=raw_pack,
        alignment=alignment,
        method_stages=stages,
        code_method_analysis=code_method_analysis,
    )

    return MethodEvidence(
        project_id=alignment.project_id,
        author_mode=raw_pack.author_mode,
        author_confirmation_required=raw_pack.author_confirmation_required,
        method_name=_method_name(alignment, code_method_analysis),
        method_goal=_method_goal(raw_pack, alignment, code_method_analysis),
        implementation_scope="current codebase only",
        latex_expression_preference=alignment.author_alignment.latex_expression_preference,
        entrypoints=[f"{entry.path}:{entry.symbol}" for entry in alignment.entrypoints],
        stages=stages,
        behavior_patterns=symbol_mechanisms.behavior_patterns,
        equation_candidates=symbol_mechanisms.equation_candidates,
        architecture_parameters=symbol_mechanisms.architecture_parameters,
        tensor_roles=symbol_mechanisms.tensor_roles,
        innovation_candidates=[],
        writing_constraints=_writing_constraints(raw_pack),
        alignment_notes=_alignment_notes(alignment),
        excluded_sources=raw_pack.excluded_sources,
        **phase3_freeze,
    )


def build_method_evidence_from_files(
    raw_evidence_path: str | Path,
    alignment_path: str | Path,
    code_method_analysis_path: str | Path | None = None,
) -> MethodEvidence:
    raw_pack = RawEvidencePack.model_validate(json.loads(Path(raw_evidence_path).read_text(encoding="utf-8")))
    alignment = CodeAlignmentIR.model_validate(json.loads(Path(alignment_path).read_text(encoding="utf-8")))
    code_method_analysis = None
    if code_method_analysis_path is not None and Path(code_method_analysis_path).exists():
        code_method_analysis = CodeMethodAnalysis.model_validate(
            json.loads(Path(code_method_analysis_path).read_text(encoding="utf-8"))
        )
    return build_method_evidence(raw_pack, alignment, code_method_analysis)


def write_phase3_artifacts(
    *,
    method_root: Path,
    paper_root: Path,
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None = None,
    code_facts: dict | None = None,
    llm_config: LLMConfig | None = None,
) -> tuple[MethodEvidence, dict[str, Path]]:
    from .claim_grounder import build_claim_evidence_map

    # Kept for CLI/API compatibility. Phase 3 no longer makes schema-gated LLM
    # subcalls; code_facts and author markers are the writing-facing inputs.
    _ = llm_config
    method_root.mkdir(parents=True, exist_ok=True)
    paper_root.mkdir(parents=True, exist_ok=True)
    method_evidence = build_method_evidence(raw_pack, alignment, code_method_analysis)
    if code_facts:
        method_evidence.method_overview = _method_overview_from_code_facts(code_facts)
        method_evidence.stage_packets = _stage_packets_from_code_facts(
            method_evidence=method_evidence,
            code_facts=code_facts,
            code_method_analysis=code_method_analysis,
        )
    author_marker_freeze = _is_author_marker_code_report_analysis(code_method_analysis)
    llm_call_logs: list[str] = []
    blocked_reason = ""
    claim_map = build_claim_evidence_map(method_evidence, alignment)
    paths = {
        "method_evidence": method_root / "method_evidence.json",
        "claim_evidence_map": paper_root / "claim_evidence_map.json",
        "method_evidence_review": method_root / "method_evidence_review.md",
        "phase3_manifest": method_root / "phase3_manifest.json",
    }
    _write_json(paths["method_evidence"], method_evidence.model_dump(mode="json"))
    _write_json(paths["claim_evidence_map"], claim_map.model_dump(mode="json"))
    paths["method_evidence_review"].write_text(_method_evidence_review(method_evidence), encoding="utf-8")
    manifest = Phase3Manifest(
        project_id=method_evidence.project_id,
        mode="author-marker-freeze" if author_marker_freeze else "evidence-freeze",
        llm_available=False,
        blocked_reason=blocked_reason,
        inputs={
            "raw_evidence_pack": "paper/method/raw_evidence_pack.json",
            "code_alignment_ir": "paper/method/code_alignment_ir.json",
            "code_method_analysis": "paper/method/code_method_analysis.json" if code_method_analysis else "",
            "code_facts": "paper/method/code_facts.json" if code_facts else "",
        },
        outputs={
            name: ArtifactHash(path=str(path), hash=hash_file(path))
            for name, path in paths.items()
            if name != "phase3_manifest"
        },
        llm_call_logs=llm_call_logs,
        review_questions=[
            contract.review_question_id
            for contract in method_evidence.claim_contracts
            if contract.review_question_id
        ],
    )
    _write_json(paths["phase3_manifest"], manifest.model_dump(mode="json"))
    return method_evidence, paths


def _is_author_marker_code_report_analysis(code_method_analysis: CodeMethodAnalysis | None) -> bool:
    if not code_method_analysis:
        return False
    return any(flow.flow_id == "FLOW-author-marker-mainline" for flow in code_method_analysis.execution_flows)


def _method_overview_from_code_facts(code_facts: dict) -> dict:
    overview = code_facts.get("overview") if isinstance(code_facts.get("overview"), dict) else {}
    allowed = ("implementation_summary", "architecture_summary", "training_summary", "alignment_summary")
    return {key: str(overview.get(key) or "").strip() for key in allowed if str(overview.get(key) or "").strip()}


def _stage_packets_from_code_facts(
    *,
    method_evidence: MethodEvidence,
    code_facts: dict,
    code_method_analysis: CodeMethodAnalysis | None,
) -> list[dict]:
    pipeline_steps = [step for step in code_facts.get("pipeline_steps", []) if isinstance(step, dict)]
    modules = [module for module in code_facts.get("modules", []) if isinstance(module, dict)]
    module_by_name = {_normalize_name(str(module.get("name") or "")): module for module in modules}
    analysis_module_evidence = _analysis_module_evidence_lookup(code_method_analysis)
    candidate_by_name = {
        _normalize_name(candidate.name): candidate
        for candidate in (code_method_analysis.candidate_mechanisms if code_method_analysis else [])
    }
    step_by_name = {_normalize_name(str(step.get("name") or "")): step for step in pipeline_steps}
    packets: list[dict] = []
    for stage in method_evidence.stages:
        step = step_by_name.get(_normalize_name(stage.name), {})
        candidate = candidate_by_name.get(_normalize_name(stage.name))
        stage_evidence = _dedupe(
            (candidate.supporting_span_ids if candidate else [])
            + [evidence_id for mechanism in stage.mechanisms for evidence_id in mechanism.evidence_ids]
        )
        involved_names = _as_clean_str_list(step.get("involved_modules"))
        module_actions = []
        for name in involved_names:
            module = module_by_name.get(_normalize_name(name))
            if module:
                role = str(module.get("role") or name).strip()
                key_logic = str(module.get("key_logic") or "").strip()
                confidence = module.get("confidence")
                evidence_ids = analysis_module_evidence.get(_normalize_name(name), [])
            else:
                role = name
                key_logic = ""
                confidence = None
                evidence_ids = []
            module_actions.append(
                {
                    "name": name,
                    "role": role,
                    "key_logic": key_logic,
                    "evidence_ids": _dedupe(evidence_ids or stage_evidence),
                    "support_status": "supported" if (evidence_ids or stage_evidence) else "needs_review",
                    "confidence": confidence,
                }
            )
        packets.append(
            {
                "stage_id": stage.stage_id,
                "name": stage.name,
                "purpose": str(step.get("description") or stage.purpose).strip(),
                "inputs": _clean_analysis_io_items(_as_clean_str_list(step.get("input_data")) or stage.inputs),
                "outputs": _clean_analysis_io_items(_as_clean_str_list(step.get("output_data")) or stage.outputs),
                "module_actions": module_actions,
                "data_flow": step.get("data_flow") if isinstance(step.get("data_flow"), list) else [],
                "key_operations": _as_clean_str_list(step.get("key_operations")),
                "stage_claim": candidate.description if candidate else str(step.get("description") or stage.purpose).strip(),
                "evidence_ids": stage_evidence,
                "support_status": "supported" if stage_evidence else "needs_review",
                "confidence": step.get("confidence"),
            }
        )
    return packets


def _analysis_module_evidence_lookup(code_method_analysis: CodeMethodAnalysis | None) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    if not code_method_analysis:
        return lookup
    for module in code_method_analysis.method_modules:
        names = [_normalize_name(symbol) for symbol in module.symbols]
        if module.paper_role:
            names.append(_normalize_name(module.paper_role))
        for name in names:
            if not name:
                continue
            lookup[name] = _dedupe(lookup.get(name, []) + module.evidence_span_ids)
    return lookup


def _as_clean_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _is_author_guided_analysis(code_method_analysis: CodeMethodAnalysis | None) -> bool:
    if not code_method_analysis:
        return False
    return bool(code_method_analysis.author_alignment.author_proposed_flow) or _is_author_marker_code_report_analysis(code_method_analysis)


def _modules_by_method_stage(alignment: CodeAlignmentIR) -> dict[str, list[AlignedModuleRole]]:
    evidence_to_stage: dict[str, str] = {}
    for stage in alignment.method_stages:
        for evidence_id in stage.related_evidence_ids:
            evidence_to_stage[evidence_id] = stage.stage_id

    grouped: dict[str, list[AlignedModuleRole]] = {stage.stage_id: [] for stage in alignment.method_stages}
    method_stage_by_evidence = {
        evidence_id: stage
        for stage in alignment.method_stages
        for evidence_id in stage.related_evidence_ids
    }
    for role in alignment.module_roles:
        for evidence_id in role.evidence_ids:
            stage = method_stage_by_evidence.get(evidence_id)
            stage_id = evidence_to_stage.get(evidence_id)
            if not stage_id:
                continue
            if role.category != ModuleCategory.METHOD_CORE and not _allow_support_module_in_stage(role, stage):
                continue
            grouped[stage_id].append(role)
            break
    for stage_id, roles in grouped.items():
        grouped[stage_id] = _dedupe_roles(roles)
    return grouped


def _phase3_freeze_fields(
    *,
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    method_stages: list[MethodStageEvidence],
    code_method_analysis: CodeMethodAnalysis | None,
) -> dict:
    frozen_mechanisms = _frozen_mechanisms(method_stages, code_method_analysis)
    distinguishing = [
        mechanism.mechanism_id
        for mechanism in frozen_mechanisms
        if mechanism.distinguishing_level in {"main", "secondary"}
    ]
    author_mapping = _author_logic_mapping(alignment, code_method_analysis)
    unsupported_author_parts = _dedupe(
        author_mapping.author_unsupported_parts
        + alignment.author_alignment.unsupported_claims
        + (code_method_analysis.author_alignment.author_unsupported_parts if code_method_analysis else [])
    )
    negative_scope = _negative_scope(
        raw_pack=raw_pack,
        alignment=alignment,
        code_method_analysis=code_method_analysis,
        unsupported_author_parts=unsupported_author_parts,
    )
    claim_contracts = _claim_contracts(
        frozen_mechanisms=frozen_mechanisms,
        method_stages=method_stages,
        unsupported_author_parts=unsupported_author_parts,
        code_method_analysis=code_method_analysis,
    )
    return {
        "author_logic_priority": raw_pack.author_mode != AuthorMode.NONE,
        "frozen_mechanisms": frozen_mechanisms,
        "distinguishing_mechanisms": distinguishing,
        "author_logic_mapping": author_mapping,
        "unsupported_author_parts": unsupported_author_parts,
        "claim_contracts": claim_contracts,
        "negative_scope": negative_scope,
    }


def _frozen_mechanisms(
    method_stages: list[MethodStageEvidence],
    code_method_analysis: CodeMethodAnalysis | None,
) -> list[FrozenMechanism]:
    stage_by_index = {index: stage for index, stage in enumerate(method_stages)}
    if code_method_analysis and code_method_analysis.candidate_mechanisms:
        result: list[FrozenMechanism] = []
        distinguishing_names = {name.lower() for name in code_method_analysis.candidate_distinguishing_mechanisms}
        module_by_evidence = {
            evidence_id: module
            for module in code_method_analysis.method_modules
            if not _is_unknown_module_path(module.path)
            and not _is_ambiguous_low_confidence_module(module, code_method_analysis)
            for evidence_id in module.evidence_span_ids
        }
        for index, mechanism in enumerate(code_method_analysis.candidate_mechanisms):
            parent_stage = stage_by_index.get(min(index, max(stage_by_index.keys(), default=0)))
            anchor_module = next(
                (
                    module_by_evidence[evidence_id]
                    for evidence_id in mechanism.supporting_span_ids
                    if evidence_id in module_by_evidence
                ),
                None,
            )
            result.append(
                FrozenMechanism(
                    mechanism_id=mechanism.mechanism_id,
                    mechanism_name=mechanism.name or f"Mechanism {index + 1}",
                    mechanism_description=mechanism.description,
                    parent_stage_id=parent_stage.stage_id if parent_stage else "",
                    inputs=_clean_analysis_io_items(mechanism.inputs),
                    outputs=_clean_analysis_io_items(mechanism.outputs),
                    implementation_anchor=MethodImplementationAnchor(
                        path=anchor_module.path if anchor_module else "",
                        symbols=anchor_module.symbols if anchor_module else [],
                    ),
                    distinguishing_level="main" if mechanism.name.lower() in distinguishing_names else "none",
                    author_claim_relation=_mechanism_author_relation(mechanism.supporting_span_ids),
                    evidence_span_ids=mechanism.supporting_span_ids,
                )
            )
        return result

    result = []
    for stage in method_stages:
        for mechanism in stage.mechanisms:
            anchor_module = next((module for module in stage.modules if module.category == ModuleCategory.METHOD_CORE), None)
            result.append(
                FrozenMechanism(
                    mechanism_id=mechanism.mechanism_id,
                    mechanism_name=stage.name,
                    mechanism_description=mechanism.description,
                    parent_stage_id=stage.stage_id,
                    inputs=stage.inputs,
                    outputs=stage.outputs,
                    implementation_anchor=MethodImplementationAnchor(
                        path=anchor_module.path if anchor_module else "",
                        symbols=anchor_module.symbols if anchor_module else [],
                    ),
                    distinguishing_level=_fallback_distinguishing_level(stage.name, mechanism.description),
                    author_claim_relation=_support_to_conflict(mechanism.support_status),
                    evidence_span_ids=mechanism.evidence_ids,
                )
        )
    return result


def _mechanism_author_relation(evidence_ids: list[str]) -> ConflictStatus:
    return ConflictStatus.SUPPORTED if evidence_ids else ConflictStatus.AMBIGUOUS_DUE_TO_MISSING_CONTEXT


def _fallback_distinguishing_level(stage_name: str, description: str) -> str:
    text = f"{stage_name} {description}".lower()
    if any(term in text for term in {"attention", "scheduled", "label smoothing", "positional"}):
        return "secondary"
    return "none"


def _support_to_conflict(status: SupportStatus) -> ConflictStatus:
    if status == SupportStatus.SUPPORTED:
        return ConflictStatus.SUPPORTED
    if status == SupportStatus.PARTIAL:
        return ConflictStatus.PARTIALLY_SUPPORTED
    return ConflictStatus.UNSUPPORTED


def _author_logic_mapping(
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None,
) -> AuthorLogicMapping:
    if code_method_analysis:
        return AuthorLogicMapping(
            author_proposed_flow=code_method_analysis.author_alignment.author_proposed_flow,
            author_supported_flow=code_method_analysis.author_alignment.author_supported_flow,
            author_unsupported_parts=code_method_analysis.author_alignment.author_unsupported_parts,
        )
    return AuthorLogicMapping(
        author_proposed_flow=alignment.author_alignment.author_story_order
        or (alignment.author_alignment.matched_steps + alignment.author_alignment.mismatched_steps),
        author_supported_flow=alignment.author_alignment.matched_steps,
        author_unsupported_parts=alignment.author_alignment.mismatched_steps + alignment.author_alignment.unsupported_claims,
    )


def _ordered_method_stages(
    *,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None,
) -> list[MethodStageAlignment]:
    analysis_stages = _analysis_ordered_method_stages(code_method_analysis)
    if analysis_stages:
        return analysis_stages
    stages = list(alignment.method_stages)
    preferred_ids = alignment.author_alignment.preferred_method_stage_ids
    if not preferred_ids:
        return stages
    by_id = {stage.stage_id: stage for stage in stages}
    ordered: list[MethodStageAlignment] = []
    for stage_id in preferred_ids:
        stage = by_id.get(stage_id)
        if stage and stage not in ordered:
            ordered.append(stage)
    for stage in stages:
        if stage not in ordered:
            ordered.append(stage)
    return ordered


def _analysis_ordered_method_stages(code_method_analysis: CodeMethodAnalysis | None) -> list[MethodStageAlignment]:
    if not code_method_analysis:
        return []
    proposed = code_method_analysis.author_alignment.author_proposed_flow
    if not proposed:
        for flow in code_method_analysis.execution_flows:
            proposed.extend(flow.ordered_steps)
    proposed = _dedupe(proposed)
    if not proposed:
        return []
    mechanisms_by_name = {
        _normalize_name(mechanism.name): mechanism
        for mechanism in code_method_analysis.candidate_mechanisms
    }
    mechanisms_by_index = {
        index: mechanism
        for index, mechanism in enumerate(code_method_analysis.candidate_mechanisms)
    }
    stages: list[MethodStageAlignment] = []
    for index, name in enumerate(proposed):
        mechanism = mechanisms_by_name.get(_normalize_name(name)) or mechanisms_by_index.get(index)
        evidence_ids = mechanism.supporting_span_ids if mechanism else []
        purpose = mechanism.description if mechanism else _purpose_for_analysis_stage(name, code_method_analysis)
        stages.append(
            MethodStageAlignment(
                stage_id=f"M{index + 1}",
                name=name,
                purpose=purpose or f"Author-marker method stage: {name}.",
                related_evidence_ids=evidence_ids,
            )
        )
    return stages


def _purpose_for_analysis_stage(stage_name: str, code_method_analysis: CodeMethodAnalysis) -> str:
    normalized = _normalize_name(stage_name)
    for flow in code_method_analysis.execution_flows:
        if normalized in {_normalize_name(step) for step in flow.ordered_steps}:
            return flow.purpose
    return ""


def _analysis_stage_io(*, code_method_analysis: CodeMethodAnalysis | None, stage_name: str) -> dict[str, list[str]]:
    if not code_method_analysis:
        return {"inputs": [], "outputs": []}
    normalized = _normalize_name(stage_name)
    for mechanism in code_method_analysis.candidate_mechanisms:
        if _normalize_name(mechanism.name) == normalized:
            return {
                "inputs": _clean_analysis_io_items(mechanism.inputs),
                "outputs": _clean_analysis_io_items(mechanism.outputs),
            }
    return {"inputs": [], "outputs": []}


def _clean_analysis_io_items(items: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        value: object = item
        stripped = str(item).strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                value = ast.literal_eval(stripped)
            except (SyntaxError, ValueError):
                value = stripped
        if isinstance(value, list):
            cleaned.extend(str(part).strip() for part in value if str(part).strip())
        else:
            text = str(value).strip()
            if text:
                cleaned.append(text)
    return _dedupe(cleaned)


def _analysis_modules_for_stage(
    *,
    code_method_analysis: CodeMethodAnalysis | None,
    evidence_ids: list[str],
) -> list[MethodModule]:
    if not code_method_analysis or not evidence_ids:
        return []
    stage_evidence = set(evidence_ids)
    modules: list[MethodModule] = []
    for module in code_method_analysis.method_modules:
        if _is_unknown_module_path(module.path):
            continue
        if not stage_evidence.intersection(module.evidence_span_ids):
            continue
        if _is_ambiguous_low_confidence_module(module, code_method_analysis):
            continue
        modules.append(
            MethodModule(
                path=module.path,
                symbols=module.symbols,
                role=module.paper_role,
                category=module.module_class,
                is_novel=False,
            )
        )
    return _dedupe_method_modules(modules)


def _is_unknown_module_path(path: str) -> bool:
    normalized = str(path or "").strip().lower()
    return not normalized or normalized in {"unknown", "unknown.py"}


def _is_ambiguous_low_confidence_module(module: CodeMethodModule, code_method_analysis: CodeMethodAnalysis) -> bool:
    if module.llm_confidence == ConfidenceLevel.HIGH:
        return False
    module_evidence = set(module.evidence_span_ids)
    if not module_evidence:
        return False
    supported_stage_hits = 0
    for mechanism in code_method_analysis.candidate_mechanisms:
        if module_evidence.intersection(mechanism.supporting_span_ids):
            supported_stage_hits += 1
    return supported_stage_hits > 1


def _analysis_mechanisms_for_stage(
    *,
    code_method_analysis: CodeMethodAnalysis | None,
    method_stage: MethodStageAlignment,
    stage_id: str,
    start_index: int,
    author_mode: AuthorMode,
    submechanisms: list[SubMechanism],
) -> list[Mechanism]:
    if not code_method_analysis:
        return []
    normalized = _normalize_name(method_stage.name)
    stage_evidence = set(method_stage.related_evidence_ids)
    exact_candidates = [
        mechanism
        for mechanism in code_method_analysis.candidate_mechanisms
        if _normalize_name(mechanism.name) == normalized
    ]
    candidates = exact_candidates
    if not candidates:
        candidates = [
            mechanism
            for mechanism in code_method_analysis.candidate_mechanisms
            if bool(stage_evidence.intersection(mechanism.supporting_span_ids))
        ][:1]
    result: list[Mechanism] = []
    for offset, candidate in enumerate(candidates):
        evidence_ids = candidate.supporting_span_ids
        result.append(
            Mechanism(
                mechanism_id=candidate.mechanism_id if candidate.mechanism_id.startswith("MECH") else f"MECH{start_index + offset}",
                description=candidate.description or f"The {stage_id} stage implements {method_stage.purpose.rstrip('.').lower()}.",
                support_status=SupportStatus.SUPPORTED if evidence_ids else SupportStatus.PARTIAL,
                evidence_ids=evidence_ids,
                confidence=_mechanism_confidence(evidence_ids, author_mode),
                submechanisms=_submechanisms_for_evidence(submechanisms, evidence_ids),
            )
        )
    return result


def _dedupe_method_modules(modules: list[MethodModule]) -> list[MethodModule]:
    grouped: dict[tuple[str, str, ModuleCategory], MethodModule] = {}
    for module in modules:
        key = (module.path, module.role, module.category)
        if key not in grouped:
            grouped[key] = module.model_copy(deep=True)
            continue
        grouped[key].symbols = sorted(set(grouped[key].symbols + module.symbols))
    return list(grouped.values())


def _normalize_name(value: str) -> str:
    return " ".join((value or "").replace("_", " ").lower().split())


def _negative_scope(
    *,
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None,
    unsupported_author_parts: list[str],
) -> list[str]:
    scope = [
        "README-only statements cannot enter method prose.",
        "Logger, checkpoint, seed, cache, path handling, and distributed setup are infrastructure unless tied to hard method evidence.",
        "Comments and author hints are navigation signals, not standalone fact evidence.",
    ]
    utility_modules = [
        f"{role.path}::{role.symbol}"
        for role in alignment.module_roles
        if role.category in {ModuleCategory.INFRA_UTILITY, ModuleCategory.EXPERIMENT_SUPPORT}
    ]
    if utility_modules:
        scope.append("Do not present these support/utility symbols as method mechanisms: " + ", ".join(utility_modules[:20]))
    for part in unsupported_author_parts:
        scope.append(f"Unsupported author part: {part}")
    if code_method_analysis:
        for gap in code_method_analysis.gaps:
            scope.append(f"Analysis gap: {gap}")
        for insight in code_method_analysis.comment_driven_insights:
            if insight.verification_status in {
                ConflictStatus.UNSUPPORTED,
                ConflictStatus.AMBIGUOUS_DUE_TO_MISSING_CONTEXT,
            }:
                scope.append(f"Do not write comment-only insight without review: {insight.insight}")
    if raw_pack.author_mode == AuthorMode.NONE:
        scope.append("No author markers were provided; author confirmation is required before claiming method intent.")
    return _dedupe(scope)


def _claim_contracts(
    *,
    frozen_mechanisms: list[FrozenMechanism],
    method_stages: list[MethodStageEvidence],
    unsupported_author_parts: list[str],
    code_method_analysis: CodeMethodAnalysis | None,
) -> list[ClaimContract]:
    contracts: list[ClaimContract] = []
    focus_terms = load_focus_terms()
    for stage in method_stages:
        evidence_ids = _dedupe(
            [
                evidence_id
                for mechanism in stage.mechanisms
                for evidence_id in mechanism.evidence_ids
            ]
        )
        status = ConflictStatus.SUPPORTED if evidence_ids else ConflictStatus.PARTIALLY_SUPPORTED
        contracts.append(
            ClaimContract(
                claim_id=f"C{len(contracts) + 1}",
                claim_intent=f"The method contains a paper-facing stage named {stage.name}.",
                support_status=status,
                evidence_span_ids=evidence_ids,
                allowed_wording_boundary=f"Describe {stage.name} only using its listed evidence-backed inputs, outputs, modules, and mechanisms.",
                required_qualifiers=[] if status == ConflictStatus.SUPPORTED else ["partially supported by discovered evidence"],
                review_question_id="" if status == ConflictStatus.SUPPORTED else f"RQ-{len(contracts) + 1}",
            )
        )
    for mechanism in frozen_mechanisms:
        status = ConflictStatus.SUPPORTED if mechanism.evidence_span_ids else mechanism.author_claim_relation
        contracts.append(
            ClaimContract(
                claim_id=f"C{len(contracts) + 1}",
                claim_intent=mechanism.mechanism_description,
                support_status=status,
                evidence_span_ids=mechanism.evidence_span_ids,
                allowed_wording_boundary="Do not add behavior beyond the cited implementation anchors and evidence spans.",
                required_qualifiers=[] if status == ConflictStatus.SUPPORTED else ["limit wording to observed implementation behavior"],
                review_question_id="" if status == ConflictStatus.SUPPORTED else f"RQ-{len(contracts) + 1}",
            )
        )
    if code_method_analysis:
        for insight in _prioritized_comment_insights(
            code_method_analysis.comment_driven_insights,
            focus_terms=focus_terms,
            limit=max(20, PHASE3_COMMENT_INSIGHT_CLAIM_LIMIT),
        ):
            evidence_ids = insight.verified_by_hard_span_ids
            if insight.verification_status == ConflictStatus.SUPPORTED and not evidence_ids:
                continue
            contracts.append(
                ClaimContract(
                    claim_id=f"C{len(contracts) + 1}",
                    claim_intent=insight.insight,
                    support_status=insight.verification_status,
                    evidence_span_ids=evidence_ids,
                    allowed_wording_boundary="Use only if hard evidence spans verify the comment-driven insight.",
                    required_qualifiers=_qualifiers_for_conflict(insight.verification_status),
                    review_question_id="" if insight.verification_status == ConflictStatus.SUPPORTED else f"RQ-{len(contracts) + 1}",
                )
            )
    for part in unsupported_author_parts:
        contracts.append(
            ClaimContract(
                claim_id=f"C{len(contracts) + 1}",
                claim_intent=part,
                support_status=ConflictStatus.UNSUPPORTED,
                evidence_span_ids=[],
                allowed_wording_boundary="Do not include in method prose unless the author supplies hard supporting evidence.",
                required_qualifiers=["unsupported by current code evidence"],
                review_question_id=f"RQ-{len(contracts) + 1}",
            )
        )
    return contracts


def _prioritized_comment_insights(
    insights: list,
    *,
    focus_terms: list[str],
    limit: int,
) -> list:
    ranked = sorted(
        insights,
        key=lambda insight: (
            0 if _comment_focus_score(insight.insight, focus_terms=focus_terms) > 0 else 1,
            1 if is_boilerplate_text(insight.insight) else 0,
            0 if insight.verification_status in {ConflictStatus.SUPPORTED, ConflictStatus.PARTIALLY_SUPPORTED} else 1,
            -len(insight.verified_by_hard_span_ids),
        ),
    )
    selected: list = []
    for insight in ranked:
        score = _comment_focus_score(insight.insight, focus_terms=focus_terms)
        if score == 0 and is_boilerplate_text(insight.insight):
            continue
        if (
            focus_terms
            and score == 0
            and insight.verification_status in {ConflictStatus.UNSUPPORTED, ConflictStatus.AMBIGUOUS_DUE_TO_MISSING_CONTEXT}
        ):
            continue
        selected.append(insight)
        if len(selected) >= limit:
            break
    return selected


def _comment_focus_score(text: str, *, focus_terms: list[str]) -> int:
    return relevance_score(text, focus_terms=focus_terms)


def _qualifiers_for_conflict(status: ConflictStatus) -> list[str]:
    if status == ConflictStatus.PARTIALLY_SUPPORTED:
        return ["partially supported by implementation evidence"]
    if status == ConflictStatus.UNSUPPORTED:
        return ["unsupported by implementation evidence"]
    if status == ConflictStatus.AMBIGUOUS_DUE_TO_MISSING_CONTEXT:
        return ["requires author review due to missing context"]
    return []


def _dedupe_roles(roles: list[AlignedModuleRole]) -> list[AlignedModuleRole]:
    seen: set[tuple[str, str]] = set()
    result: list[AlignedModuleRole] = []
    for role in roles:
        key = (role.path, role.symbol)
        if key in seen:
            continue
        seen.add(key)
        result.append(role)
    return result


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _method_evidence_review(method_evidence: MethodEvidence) -> str:
    lines = [
        "# Method Evidence Review",
        "",
        f"- project_id: {method_evidence.project_id}",
        f"- author_confirmation_required: {str(method_evidence.author_confirmation_required).lower()}",
        f"- stages: {len(method_evidence.stages)}",
        f"- frozen_mechanisms: {len(method_evidence.frozen_mechanisms)}",
        f"- claim_contracts: {len(method_evidence.claim_contracts)}",
        "",
        "## Author Logic",
        "",
        "- proposed: " + (", ".join(method_evidence.author_logic_mapping.author_proposed_flow) or "none"),
        "- supported: " + (", ".join(method_evidence.author_logic_mapping.author_supported_flow) or "none"),
        "- unsupported: " + (", ".join(method_evidence.author_logic_mapping.author_unsupported_parts) or "none"),
        "",
        "## Review Questions",
        "",
    ]
    review_contracts = [contract for contract in method_evidence.claim_contracts if contract.review_question_id]
    if not review_contracts:
        lines.append("- none")
    for contract in review_contracts:
        lines.append(
            f"- {contract.review_question_id}: Confirm whether '{contract.claim_intent}' can be supported by additional hard evidence."
        )
    lines.extend(["", "## Negative Scope", ""])
    for item in method_evidence.negative_scope:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _allow_support_module_in_stage(role: AlignedModuleRole, stage: MethodStageAlignment | None) -> bool:
    if stage is None:
        return False
    if stage.name == "input_preparation" and role.path == "preprocess.py":
        return role.symbol in {"main", "compile_files", "encode_files", "encode_file"}
    return False


def _to_method_module(role: AlignedModuleRole) -> MethodModule:
    return MethodModule(
        path=role.path,
        symbols=[role.symbol] if role.symbol else [],
        role=role.role,
        category=role.category,
        is_novel=False,
    )


def _mechanism_for_stage(
    method_stage: MethodStageAlignment,
    *,
    stage_id: str,
    mechanism_id: str,
    evidence_ids: list[str],
    author_mode: AuthorMode,
    submechanisms: list[SubMechanism] | None = None,
) -> Mechanism:
    description = _mechanism_description(method_stage.name)
    if not description:
        description = f"The {stage_id} stage implements {method_stage.purpose.rstrip('.').lower()}."
    return Mechanism(
        mechanism_id=mechanism_id,
        description=description,
        support_status=SupportStatus.SUPPORTED if evidence_ids else SupportStatus.PARTIAL,
        evidence_ids=evidence_ids,
        confidence=_mechanism_confidence(evidence_ids, author_mode),
        submechanisms=submechanisms or [],
    )


def _submechanisms_for_evidence(submechanisms: list[SubMechanism], evidence_ids: list[str]) -> list[SubMechanism]:
    stage_evidence = set(evidence_ids)
    return [submechanism for submechanism in submechanisms if stage_evidence.intersection(submechanism.evidence_ids)]


def _mechanism_confidence(evidence_ids: list[str], author_mode: AuthorMode) -> ConfidenceLevel:
    if not evidence_ids:
        return ConfidenceLevel.MEDIUM
    if author_mode == AuthorMode.NONE:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.HIGH


def _mechanism_description(stage_name: str) -> str:
    if stage_name == "input_preparation":
        return (
            "The pipeline prepares translation data by converting raw corpora into tokenized, "
            "filtered, vocabulary-backed serialized training artifacts."
        )
    if stage_name == "transformer_computation":
        return (
            "The method computes sequence representations with Transformer encoder/decoder "
            "components built from attention and position-wise feed-forward sublayers."
        )
    if stage_name == "scheduled_optimization":
        return (
            "Training optimizes model parameters by combining forward prediction, loss computation, "
            "backpropagation, and the scheduled learning-rate update."
        )
    return ""


def _stage_inputs(stage_name: str) -> list[str]:
    if stage_name == "input_preparation":
        return ["raw corpus files", "BPE settings", "maximum sequence length"]
    if stage_name == "transformer_computation":
        return ["source token sequence", "target prefix sequence", "model hyperparameters"]
    if stage_name == "scheduled_optimization":
        return ["model predictions", "target tokens", "optimizer settings", "warmup steps"]
    return []


def _stage_outputs(stage_name: str) -> list[str]:
    if stage_name == "input_preparation":
        return ["serialized data", "vocabulary", "filtered train and validation examples"]
    if stage_name == "transformer_computation":
        return ["decoder predictions", "attention representations"]
    if stage_name == "scheduled_optimization":
        return ["updated parameters", "training metrics", "validation metrics", "checkpoints"]
    return []


def _human_stage_name(stage_name: str) -> str:
    if "_" not in stage_name and any(char.isupper() for char in stage_name):
        return stage_name
    words = stage_name.replace("_", " ").split()
    roman = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    normalized: list[str] = []
    for word in words:
        suffix = ""
        while word and word[-1] in {":", ",", "."}:
            suffix = word[-1] + suffix
            word = word[:-1]
        lowered = word.lower()
        if lowered in roman:
            token = lowered.upper()
        elif lowered == "llm":
            token = "LLM"
        else:
            token = lowered.capitalize()
        normalized.append(token + suffix)
    return " ".join(normalized)


def _method_name(alignment: CodeAlignmentIR, code_method_analysis: CodeMethodAnalysis | None = None) -> str:
    if code_method_analysis and code_method_analysis.author_alignment.author_proposed_flow:
        flow = [name for name in code_method_analysis.author_alignment.author_proposed_flow if name.strip()]
        if flow:
            return "Author-Marker Grounded Method Pipeline"
    names = {stage.name for stage in alignment.method_stages}
    if "transformer_computation" in names:
        return "Transformer Translation Training Pipeline"
    return "Implementation-Grounded Method Pipeline"


def _method_goal(
    raw_pack: RawEvidencePack,
    alignment: CodeAlignmentIR,
    code_method_analysis: CodeMethodAnalysis | None = None,
) -> str:
    author_goal = _author_goal_from_raw_pack(raw_pack)
    if author_goal:
        return author_goal
    if code_method_analysis and code_method_analysis.execution_flows:
        flow = code_method_analysis.execution_flows[0]
        if flow.purpose and not _is_generic_bridge_flow_purpose(flow.purpose):
            return flow.purpose
    if code_method_analysis and code_method_analysis.candidate_mechanisms:
        descriptions = [
            _rstrip_period(mechanism.description)
            for mechanism in code_method_analysis.candidate_mechanisms
            if mechanism.description.strip()
        ][:4]
        if descriptions:
            return "Coordinate a method pipeline that " + "; then ".join(_third_person_phrase(text) for text in descriptions) + "."
    if code_method_analysis and code_method_analysis.execution_flows:
        flow = code_method_analysis.execution_flows[0]
        if flow.ordered_steps:
            return "Describe the implementation-grounded method pipeline: " + " -> ".join(flow.ordered_steps) + "."
    names = {stage.name for stage in alignment.method_stages}
    if {"input_preparation", "transformer_computation", "scheduled_optimization"}.issubset(names):
        return (
            "Train a Transformer sequence-to-sequence model from prepared translation data "
            "with architecture-level attention components and scheduled optimization."
        )
    return "Describe the method implemented by the current codebase using grounded evidence."


def _is_generic_bridge_flow_purpose(purpose: str) -> bool:
    lowered = purpose.strip().lower()
    return lowered in {
        "execution flow from postergen codeanalyzer output pipeline steps",
        "execution flow from postergen codeanalyzer output pipeline steps.",
    }


def _rstrip_period(value: str) -> str:
    return str(value).strip().rstrip(".")


def _lower_first(value: str) -> str:
    text = str(value).strip()
    if not text:
        return text
    return text[0].lower() + text[1:]


def _third_person_phrase(value: str) -> str:
    text = _lower_first(value)
    replacements = {
        "establish ": "establishes ",
        "expand ": "expands ",
        "use ": "uses ",
        "control ": "controls ",
        "connect ": "connects ",
        "show ": "shows ",
        "train ": "trains ",
    }
    for prefix, replacement in replacements.items():
        if text.startswith(prefix):
            return replacement + text[len(prefix) :]
    return text


def _author_goal_from_raw_pack(raw_pack: RawEvidencePack) -> str:
    for item in raw_pack.evidence_items:
        if item.source_type != "author":
            continue
        text = item.content_summary
        for prefix in ("Paper method goal:", "Project goal:"):
            marker = prefix.lower()
            lower = text.lower()
            if marker not in lower:
                continue
            start = lower.index(marker) + len(marker)
            tail = text[start:].strip()
            sentence = tail.split(". ", 1)[0].strip().rstrip(".")
            if sentence:
                return sentence + "."
    return ""


def _writing_constraints(raw_pack: RawEvidencePack) -> list[str]:
    constraints = [
        "Do not mention README-only information.",
        "Do not claim academic novelty without author confirmation.",
        "Do not promote comment-only hints into main method claims.",
    ]
    if raw_pack.author_mode == AuthorMode.NONE:
        constraints.append("No author markers were provided; treat method evidence as needing author confirmation.")
    for source in raw_pack.excluded_sources:
        constraints.append(f"Excluded source: {source.path} ({source.reason}).")
    return constraints


def _alignment_notes(alignment: CodeAlignmentIR) -> list[str]:
    notes: list[str] = []
    notes.append(
        "Execution stages and method stages are separated; method prose should follow method stages, not raw execution order."
    )
    if alignment.stage_mappings:
        notes.append(
            "Stage mappings connect implementation execution steps to paper-facing method stages."
        )
    if alignment.author_alignment.matched_steps:
        notes.append(
            "Author-provided pipeline steps matched: " + ", ".join(alignment.author_alignment.matched_steps) + "."
        )
    if alignment.author_alignment.unsupported_claims:
        notes.append(
            "Unsupported author claims should remain out of the method draft: "
            + ", ".join(alignment.author_alignment.unsupported_claims)
            + "."
        )
    return notes
