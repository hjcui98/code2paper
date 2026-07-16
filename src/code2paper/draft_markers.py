"""Draft-to-author-markers conversion and stage1/2 refinement helpers."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml
from pydantic import BaseModel, Field

from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.client import ProviderTimeoutError
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response
from code2paper.schemas import AuthorMarkers, LLMConfig, LLMProvider


DEFAULT_IGNORE_FILES = [
    "README.md",
    "paper.pdf",
    "__pycache__/**",
    ".git/**",
]


class _ModuleRoleSupportPatch(BaseModel):
    role: str
    supporting_files: list[str] = Field(default_factory=list)
    supporting_symbols: list[str] = Field(default_factory=list)
    support_confidence: str = "medium"
    caveats: list[str] = Field(default_factory=list)
    risky_details: list[str] = Field(default_factory=list)


class _PipelineStepSupportPatch(BaseModel):
    name: str
    supporting_files: list[str] = Field(default_factory=list)
    supporting_symbols: list[str] = Field(default_factory=list)
    support_confidence: str = "medium"
    caveats: list[str] = Field(default_factory=list)
    risky_details: list[str] = Field(default_factory=list)


class _DesignIntentSupportPatch(BaseModel):
    intent: str
    supporting_files: list[str] = Field(default_factory=list)
    supporting_functions: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    caveats: list[str] = Field(default_factory=list)


class _InnovationClaimSupportPatch(BaseModel):
    claim: str
    supporting_files: list[str] = Field(default_factory=list)
    supporting_functions: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    caveats: list[str] = Field(default_factory=list)


class _IgnoreFileReviewPatch(BaseModel):
    path: str
    decision: str
    rationale: str = ""


class _PotentialMismatchPatch(BaseModel):
    description: str
    files: list[str] = Field(default_factory=list)
    severity: str = "medium"


class DraftMarkersRefinementOutput(BaseModel):
    status: str = "ok"
    module_role_supports: list[_ModuleRoleSupportPatch] = Field(default_factory=list)
    pipeline_step_supports: list[_PipelineStepSupportPatch] = Field(default_factory=list)
    priority_files: list[str] = Field(default_factory=list)
    design_intent_supports: list[_DesignIntentSupportPatch] = Field(default_factory=list)
    innovation_claim_supports: list[_InnovationClaimSupportPatch] = Field(default_factory=list)
    ignore_file_reviews: list[_IgnoreFileReviewPatch] = Field(default_factory=list)
    potential_mismatches: list[_PotentialMismatchPatch] = Field(default_factory=list)
    rationale: str = ""


def load_yaml(path: str | Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def dump_yaml(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def validate_author_markers_payload(payload: dict[str, Any]) -> dict[str, Any]:
    markers = AuthorMarkers.model_validate(payload)
    validated = markers.model_dump(mode="json")
    if not _as_text(validated.get("project_goal")) or not _as_text(validated.get("paper_method_goal")) or not _as_text(validated.get("method_mainline")):
        raise ValueError("author core fields project_goal, paper_method_goal, and method_mainline must not be empty")
    roles = [_as_text(item.get("role")).lower() for item in _as_dict_list(validated.get("module_roles")) if _as_text(item.get("role"))]
    if len(roles) != len(set(roles)):
        raise ValueError("module_roles[*].role must be unique after validation")
    steps = [_as_text(item.get("name")).lower() for item in _as_dict_list(validated.get("pipeline_steps")) if _as_text(item.get("name"))]
    if len(steps) != len(set(steps)):
        raise ValueError("pipeline_steps[*].name must be unique after validation")
    return _resolve_priority_ignore_conflicts(validated)


def run_code2flow_scan(
    *,
    project_root: Path,
    code2flow_root: Path,
    core_top_k: int = 18,
    annotation_priority: str = "balanced",
    mechanism_keywords: list[str] | None = None,
) -> dict[str, Any]:
    src_root = code2flow_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    try:
        from code2flow.defaults import ScanConfig
        from code2flow.scanner import scan_repository
    except Exception as exc:
        raise RuntimeError(
            f"cannot import code2flow from {src_root}; please check --code2flow-root"
        ) from exc

    cfg = ScanConfig(core_top_k=core_top_k)
    return scan_repository(
        project_root,
        cfg,
        mechanism_keywords=list(mechanism_keywords or []),
        annotation_priority=annotation_priority,
    )


def build_coarse_markers_payload(
    *,
    draft_payload: dict[str, Any],
    scan_report: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    project_goal = _as_text(draft_payload.get("project_goal"))
    paper_method_goal = _as_text(draft_payload.get("paper_method_goal")) or project_goal
    method_mainline = _normalize_mainline(draft_payload.get("method_mainline"))
    paper_story_order = _as_text_list(draft_payload.get("paper_story_order"))
    deemphasize_details = _as_text_list(draft_payload.get("deemphasize_details"))
    latex_style = _as_text(draft_payload.get("latex_expression_preference")) or "balanced"

    candidates = _build_path_candidates(scan_report)
    key_blocks = _as_dict_list(draft_payload.get("key_building_blocks"))
    draft_steps = _as_dict_list(draft_payload.get("pipeline_steps"))

    module_roles = []
    fallback_module_path = candidates[0]["path"] if candidates else "main.py"
    for block in key_blocks:
        name = _as_text(block.get("name"))
        role = _as_text(block.get("role")) or name
        if not name and not role:
            continue
        query = " ".join(
            [
                name,
                role,
                " ".join(_as_text_list(block.get("related_components"))),
            ]
        ).strip()
        path = _best_paths_for_query(query, candidates, top_k=1)
        emphasis = _as_text(block.get("emphasis")).lower()
        importance = "core" if emphasis in {"high", "main", "core"} else "supporting"
        module_roles.append(
            {
                "path": path[0] if path else fallback_module_path,
                "symbol": "",
                "role": role or name,
                "importance": importance,
                "is_novel": _is_novel_text(name + " " + role),
                "notes": "Auto-generated from draft key_building_blocks; symbol pending stage1/stage2 refinement.",
            }
        )

    pipeline_steps = []
    for step in draft_steps:
        name = _as_text(step.get("name"))
        purpose = _as_text(step.get("purpose"))
        if not name or not purpose:
            continue
        query = " ".join(
            [
                name,
                purpose,
                " ".join(_as_text_list(step.get("related_components"))),
            ]
        ).strip()
        related_files = _best_paths_for_query(query, candidates, top_k=4)
        pipeline_steps.append(
            {
                "name": name,
                "purpose": purpose,
                "input": _as_text_list(step.get("input")),
                "output": _as_text_list(step.get("output")),
                "related_files": related_files,
                "highlight_level": "main",
                "omit_from_main_figure": False,
            }
        )

    innovation_claims = [
        {
            "claim": claim,
            "supporting_files": [],
            "supporting_functions": [],
            "confidence": "medium",
            "caveats": [],
        }
        for claim in _as_text_list(draft_payload.get("possible_distinguishing_points"))
        if claim
    ]
    design_intents = [
        {
            "intent": _as_text(intent.get("intent")),
            "rationale": _as_text(intent.get("rationale")),
            "supporting_files": [],
            "supporting_functions": [],
            "confidence": "medium",
            "caveats": [],
        }
        for intent in _as_dict_list(draft_payload.get("design_intents"))
        if _as_text(intent.get("intent"))
    ]

    potential_mismatches = _build_default_mismatches(draft_payload, deemphasize_details)
    priority_files = _build_coarse_priority_files(candidates, module_roles, pipeline_steps)

    scope_constraints = draft_payload.get("scope_constraints")
    ignore_files = _build_ignore_files(scope_constraints, deemphasize_details)

    payload = {
        "project_goal": project_goal,
        "paper_method_goal": paper_method_goal,
        "implementation_scope": (
            f"Use executable evidence under {project_root}; "
            "this marker file is auto-generated from draft intent + code2flow scan hints."
        ),
        "priority_files": priority_files,
        "ignore_files": ignore_files,
        "module_roles": module_roles,
        "pipeline_steps": pipeline_steps,
        "method_mainline": method_mainline,
        "paper_story_order": paper_story_order,
        "deemphasize_details": deemphasize_details,
        "latex_expression_preference": latex_style,
        "design_intents": design_intents,
        "innovation_claims": innovation_claims,
        "potential_mismatches": potential_mismatches,
    }
    return validate_author_markers_payload(payload)


def refine_markers_from_stage12(
    *,
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    core_snippets: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    snippet_map = _snippet_index(core_snippets)
    module_roles = _refine_module_roles(
        coarse_payload=coarse_payload,
        method_code_alignment=method_code_alignment,
        snippet_map=snippet_map,
        project_root=project_root,
    )
    pipeline_steps = _refine_pipeline_steps(
        coarse_payload=coarse_payload,
        method_code_alignment=method_code_alignment,
        snippet_map=snippet_map,
        project_root=project_root,
    )
    priority_files = _refine_priority_files(
        coarse_payload=coarse_payload,
        module_roles=module_roles,
        pipeline_steps=pipeline_steps,
        core_snippets=core_snippets,
    )
    design_intents = _attach_supports(
        entries=_as_dict_list(coarse_payload.get("design_intents")),
        text_field="intent",
        module_roles=module_roles,
        pipeline_steps=pipeline_steps,
    )
    innovation_claims = _attach_supports(
        entries=_as_dict_list(coarse_payload.get("innovation_claims")),
        text_field="claim",
        module_roles=module_roles,
        pipeline_steps=pipeline_steps,
    )

    payload = dict(coarse_payload)
    payload["priority_files"] = priority_files
    payload["module_roles"] = module_roles
    payload["pipeline_steps"] = pipeline_steps
    payload["design_intents"] = design_intents
    payload["innovation_claims"] = innovation_claims
    payload["potential_mismatches"] = _ensure_potential_mismatches(
        _as_dict_list(coarse_payload.get("potential_mismatches")),
        module_roles,
    )
    return validate_author_markers_payload(payload)


def refine_markers_with_llm(
    *,
    refined_payload: dict[str, Any],
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    core_snippets: dict[str, Any],
    code_facts: dict[str, Any] | None,
    project_root: Path,
    llm_config: LLMConfig | None,
) -> dict[str, Any]:
    if llm_config is None or llm_config.provider == LLMProvider.NONE:
        return refined_payload
    if not _as_dict_list(core_snippets.get("snippets")) and not _has_nonempty_code_facts(code_facts):
        return refined_payload

    request = LLMRequest(
        prompt_template_id="draft_markers_refinement_v1",
        prompt=_draft_markers_refinement_prompt(),
        input_payload=_build_llm_refinement_context(
            refined_payload=refined_payload,
            coarse_payload=coarse_payload,
            method_code_alignment=method_code_alignment,
            core_snippets=core_snippets,
            code_facts=code_facts,
            project_root=project_root,
        ),
        schema_name="draft_markers_refinement",
        response_json_schema=json_schema_for(DraftMarkersRefinementOutput),
    )
    try:
        response = LLMClient(llm_config).complete(request)
    except ProviderTimeoutError:
        # Bootstrap marker refinement is a best-effort overlay step. If the
        # provider times out, preserve the stage1/2-refined canonical markers
        # instead of aborting the whole pipeline.
        return refined_payload
    if response.blocked_reason:
        return refined_payload
    parsed, _parse_error = try_parse_structured_response(response.text, DraftMarkersRefinementOutput)
    if parsed is None or str(parsed.status or "ok").lower() == "blocked":
        return refined_payload
    return _merge_llm_refined_markers(
        refined_payload=refined_payload,
        llm_output=parsed,
        project_root=project_root,
    )


def suggest_mechanism_keywords(draft_payload: dict[str, Any], limit: int = 24) -> list[str]:
    texts: list[str] = []
    texts.extend(_as_text_list(draft_payload.get("method_mainline")))
    texts.extend(_as_text_list(draft_payload.get("possible_distinguishing_points")))
    for block in _as_dict_list(draft_payload.get("key_building_blocks")):
        texts.append(_as_text(block.get("name")))
        texts.append(_as_text(block.get("role")))
    for step in _as_dict_list(draft_payload.get("pipeline_steps")):
        texts.append(_as_text(step.get("name")))
        texts.append(_as_text(step.get("purpose")))
        texts.extend(_as_text_list(step.get("related_components")))

    freq: Counter[str] = Counter()
    for text in texts:
        for token in _tokens(text):
            if token in _STOPWORDS:
                continue
            freq[token] += 1
    return [token for token, _ in freq.most_common(limit)]


def load_stage_json(method_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    method_code_alignment_path = method_root / "method_code_alignment.json"
    core_snippets_path = method_root / "core_snippets.json"
    if not method_code_alignment_path.exists():
        raise FileNotFoundError(f"missing required file: {method_code_alignment_path}")
    if not core_snippets_path.exists():
        raise FileNotFoundError(f"missing required file: {core_snippets_path}")
    return (
        json.loads(method_code_alignment_path.read_text(encoding="utf-8")),
        json.loads(core_snippets_path.read_text(encoding="utf-8")),
    )


def load_stage_artifacts(method_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    method_code_alignment, core_snippets = load_stage_json(method_root)
    code_facts_path = method_root / "code_facts.json"
    code_facts = json.loads(code_facts_path.read_text(encoding="utf-8")) if code_facts_path.exists() else None
    return method_code_alignment, core_snippets, code_facts


def _draft_markers_refinement_prompt() -> str:
    return (
        "You are refining author_markers after bootstrap Stage 1/2 code analysis. "
        "Return only JSON matching the requested schema. "
        "Treat the current refined markers as the canonical narrative spec and apply only constrained evidence-backed support overlays. "
        "Allowed edits: "
        "(1) module_role_supports may update supporting_files/supporting_symbols/support_confidence/caveats/risky_details for an existing role; "
        "(2) pipeline_step_supports may update supporting_files/supporting_symbols/support_confidence/caveats/risky_details for an existing step name; "
        "(3) priority_files may be reordered/pruned/expanded using valid evidence-backed paths; "
        "(4) design_intent_supports may update supporting_files/supporting_functions/confidence/caveats for an existing intent; "
        "(5) innovation_claim_supports may update supporting_files/supporting_functions/confidence/caveats for an existing claim; "
        "(6) ignore_file_reviews may only decide keep/remove for explicit .py ignore entries after reading the provided file preview; "
        "(7) potential_mismatches may add or refine review warnings. "
        "Do not rewrite role text, role identity, step names, step purposes, goals, mainline text, or story order. "
        "Do not invent files, symbols, or claims. "
        "Prefer files that appear in snippets, alignment outputs, code_facts, or the repo-backed candidate lists. "
        "If evidence is weak, keep the existing value instead of forcing a change."
    )


def _build_llm_refinement_context(
    *,
    refined_payload: dict[str, Any],
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    core_snippets: dict[str, Any],
    code_facts: dict[str, Any] | None,
    project_root: Path,
) -> dict[str, Any]:
    valid_paths = _candidate_repo_paths(
        refined_payload=refined_payload,
        coarse_payload=coarse_payload,
        method_code_alignment=method_code_alignment,
        core_snippets=core_snippets,
        code_facts=code_facts,
        project_root=project_root,
    )
    return {
        "project_root": str(project_root),
        "current_refined_markers": {
            "module_roles": _as_dict_list(refined_payload.get("module_roles")),
            "pipeline_steps": _as_dict_list(refined_payload.get("pipeline_steps")),
            "priority_files": _as_text_list(refined_payload.get("priority_files")),
            "ignore_files": _as_text_list(refined_payload.get("ignore_files")),
            "design_intents": _as_dict_list(refined_payload.get("design_intents")),
            "innovation_claims": _as_dict_list(refined_payload.get("innovation_claims")),
            "potential_mismatches": _as_dict_list(refined_payload.get("potential_mismatches")),
        },
        "coarse_markers_reference": {
            "module_roles": _as_dict_list(coarse_payload.get("module_roles")),
            "pipeline_steps": _as_dict_list(coarse_payload.get("pipeline_steps")),
            "priority_files": _as_text_list(coarse_payload.get("priority_files")),
        },
        "author_core_fields": {
            "project_goal": _as_text(refined_payload.get("project_goal")),
            "paper_method_goal": _as_text(refined_payload.get("paper_method_goal")),
            "method_mainline": _as_text(refined_payload.get("method_mainline")),
            "paper_story_order": _as_text_list(refined_payload.get("paper_story_order")),
        },
        "method_code_alignment": {
            "modules": _as_dict_list(method_code_alignment.get("modules"))[:40],
            "pipeline_steps": _as_dict_list(method_code_alignment.get("pipeline_steps"))[:40],
            "coverage_report": method_code_alignment.get("coverage_report") if isinstance(method_code_alignment, dict) else {},
        },
        "code_facts": _trim_code_facts_for_llm(code_facts),
        "core_snippet_preview": _snippet_preview_for_llm(core_snippets, project_root=project_root),
        "ignore_file_py_review_candidates": _ignore_file_py_review_candidates(refined_payload, project_root),
        "valid_repo_paths": valid_paths[:160],
    }


def _merge_llm_refined_markers(
    *,
    refined_payload: dict[str, Any],
    llm_output: DraftMarkersRefinementOutput,
    project_root: Path,
) -> dict[str, Any]:
    payload = dict(refined_payload)
    payload["module_roles"] = _merge_module_role_supports(
        _as_dict_list(refined_payload.get("module_roles")),
        llm_output.module_role_supports,
        project_root=project_root,
    )
    payload["pipeline_steps"] = _merge_pipeline_step_supports(
        _as_dict_list(refined_payload.get("pipeline_steps")),
        llm_output.pipeline_step_supports,
        project_root=project_root,
    )
    payload["priority_files"] = _merge_priority_files(
        current_priority_files=_as_text_list(refined_payload.get("priority_files")),
        module_roles=_as_dict_list(payload.get("module_roles")),
        pipeline_steps=_as_dict_list(payload.get("pipeline_steps")),
        llm_priority_files=llm_output.priority_files,
        project_root=project_root,
    )
    payload["design_intents"] = _merge_design_intent_supports(
        _as_dict_list(refined_payload.get("design_intents")),
        llm_output.design_intent_supports,
        project_root=project_root,
    )
    payload["innovation_claims"] = _merge_innovation_claim_supports(
        _as_dict_list(refined_payload.get("innovation_claims")),
        llm_output.innovation_claim_supports,
        project_root=project_root,
    )
    payload["ignore_files"] = _merge_ignore_file_reviews(
        _as_text_list(refined_payload.get("ignore_files")),
        llm_output.ignore_file_reviews,
        project_root=project_root,
    )
    payload["potential_mismatches"] = _merge_potential_mismatches(
        _as_dict_list(refined_payload.get("potential_mismatches")),
        llm_output.potential_mismatches,
        project_root=project_root,
    )
    return validate_author_markers_payload(payload)


def _merge_module_role_supports(
    current: list[dict[str, Any]],
    patches: list[_ModuleRoleSupportPatch],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    patch_by_role = {str(patch.role).strip(): patch for patch in patches if str(patch.role).strip()}
    output: list[dict[str, Any]] = []
    for item in current:
        merged = dict(item)
        patch = patch_by_role.get(_as_text(item.get("role")))
        if patch:
            merged["supporting_files"] = _dedupe_nonempty(
                [
                    normalized
                    for normalized in (
                        _normalize_existing_repo_path(path, project_root)
                        for path in list(patch.supporting_files) + _as_text_list(item.get("supporting_files"))
                    )
                    if normalized
                ]
            )[:6]
            merged["supporting_symbols"] = _dedupe_nonempty(
                list(patch.supporting_symbols) + _as_text_list(item.get("supporting_symbols"))
            )[:6]
            merged["support_confidence"] = _normalize_confidence_value(
                patch.support_confidence,
                fallback=_as_text(item.get("support_confidence")) or "medium",
            )
            merged["caveats"] = _dedupe_nonempty(_as_text_list(item.get("caveats")) + list(patch.caveats))[:6]
            merged["risky_details"] = _dedupe_nonempty(
                _as_text_list(item.get("risky_details")) + list(patch.risky_details)
            )[:6]
        output.append(merged)
    return _dedupe_module_roles(output)


def _merge_pipeline_step_supports(
    current: list[dict[str, Any]],
    patches: list[_PipelineStepSupportPatch],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    patch_by_name = {str(patch.name).strip(): patch for patch in patches if str(patch.name).strip()}
    output: list[dict[str, Any]] = []
    for item in current:
        merged = dict(item)
        patch = patch_by_name.get(_as_text(item.get("name")))
        if patch:
            merged["supporting_files"] = _dedupe_nonempty(
                [
                    normalized
                    for normalized in (
                        _normalize_existing_repo_path(path, project_root)
                        for path in list(patch.supporting_files) + _as_text_list(item.get("supporting_files"))
                    )
                    if normalized
                ]
            )[:8]
            merged["supporting_symbols"] = _dedupe_nonempty(
                list(patch.supporting_symbols) + _as_text_list(item.get("supporting_symbols"))
            )[:8]
            merged["support_confidence"] = _normalize_confidence_value(
                patch.support_confidence,
                fallback=_as_text(item.get("support_confidence")) or "medium",
            )
            merged["caveats"] = _dedupe_nonempty(_as_text_list(item.get("caveats")) + list(patch.caveats))[:6]
            merged["risky_details"] = _dedupe_nonempty(
                _as_text_list(item.get("risky_details")) + list(patch.risky_details)
            )[:6]
        output.append(merged)
    return _dedupe_steps(output)


def _merge_priority_files(
    *,
    current_priority_files: list[str],
    module_roles: list[dict[str, Any]],
    pipeline_steps: list[dict[str, Any]],
    llm_priority_files: list[str],
    project_root: Path,
) -> list[str]:
    normalized_llm = [
        normalized
        for normalized in (_normalize_existing_repo_path(path, project_root) for path in llm_priority_files)
        if normalized
    ]
    normalized_current = [
        normalized
        for normalized in (_normalize_existing_repo_path(path, project_root) for path in current_priority_files)
        if normalized
    ]
    carry_paths = [_as_text(role.get("path")) for role in module_roles]
    for role in module_roles:
        carry_paths.extend(_as_text_list(role.get("supporting_files")))
    for step in pipeline_steps:
        carry_paths.extend(_as_text_list(step.get("related_files")))
        carry_paths.extend(_as_text_list(step.get("supporting_files")))
    normalized_carry = [
        normalized
        for normalized in (_normalize_existing_repo_path(path, project_root) for path in carry_paths)
        if normalized
    ]
    return _dedupe_nonempty(normalized_llm + normalized_carry + normalized_current)[:48]


def _merge_design_intent_supports(
    current: list[dict[str, Any]],
    patches: list[_DesignIntentSupportPatch],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    patch_by_intent = {str(patch.intent).strip(): patch for patch in patches if str(patch.intent).strip()}
    output: list[dict[str, Any]] = []
    for item in current:
        merged = dict(item)
        patch = patch_by_intent.get(_as_text(item.get("intent")))
        if patch:
            merged["supporting_files"] = _dedupe_nonempty(
                [
                    normalized
                    for normalized in (
                        _normalize_existing_repo_path(path, project_root)
                        for path in list(patch.supporting_files) + _as_text_list(item.get("supporting_files"))
                    )
                    if normalized
                ]
            )[:4]
            merged["supporting_functions"] = _dedupe_nonempty(
                _as_text_list(patch.supporting_functions) + _as_text_list(item.get("supporting_functions"))
            )[:5]
            merged["confidence"] = _normalize_confidence_value(patch.confidence, fallback=_as_text(item.get("confidence")) or "medium")
            merged["caveats"] = _dedupe_nonempty(_as_text_list(item.get("caveats")) + _as_text_list(patch.caveats))[:6]
        output.append(merged)
    return output


def _merge_innovation_claim_supports(
    current: list[dict[str, Any]],
    patches: list[_InnovationClaimSupportPatch],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    patch_by_claim = {str(patch.claim).strip(): patch for patch in patches if str(patch.claim).strip()}
    output: list[dict[str, Any]] = []
    for item in current:
        merged = dict(item)
        patch = patch_by_claim.get(_as_text(item.get("claim")))
        if patch:
            merged["supporting_files"] = _dedupe_nonempty(
                [
                    normalized
                    for normalized in (
                        _normalize_existing_repo_path(path, project_root)
                        for path in list(patch.supporting_files) + _as_text_list(item.get("supporting_files"))
                    )
                    if normalized
                ]
            )[:4]
            merged["supporting_functions"] = _dedupe_nonempty(
                _as_text_list(patch.supporting_functions) + _as_text_list(item.get("supporting_functions"))
            )[:5]
            merged["confidence"] = _normalize_confidence_value(patch.confidence, fallback=_as_text(item.get("confidence")) or "medium")
            merged["caveats"] = _dedupe_nonempty(_as_text_list(item.get("caveats")) + _as_text_list(patch.caveats))[:6]
        output.append(merged)
    return output


def _merge_ignore_file_reviews(
    current: list[str],
    reviews: list[_IgnoreFileReviewPatch],
    *,
    project_root: Path,
) -> list[str]:
    decisions = {
        _normalize_existing_repo_path(review.path, project_root): str(review.decision or "").strip().lower()
        for review in reviews
        if _normalize_existing_repo_path(review.path, project_root)
    }
    output: list[str] = []
    for item in current:
        normalized = _normalize_existing_repo_path(item, project_root) if _looks_like_explicit_python_file(item) else ""
        if normalized and decisions.get(normalized) == "remove":
            continue
        output.append(item)
    return _dedupe_nonempty(output)


def _merge_potential_mismatches(
    current: list[dict[str, Any]],
    patches: list[_PotentialMismatchPatch],
    *,
    project_root: Path,
) -> list[dict[str, Any]]:
    output = list(current)
    seen = {_as_text(item.get("description")) for item in current}
    for patch in patches:
        description = _as_text(patch.description)
        if not description or description in seen:
            continue
        files = _dedupe_nonempty(
            [
                normalized
                for normalized in (_normalize_existing_repo_path(path, project_root) for path in patch.files)
                if normalized
            ]
        )[:6]
        output.append(
            {
                "description": description,
                "files": files,
                "severity": _normalize_severity_value(patch.severity),
            }
        )
        seen.add(description)
    return output[:20]


def _trim_code_facts_for_llm(code_facts: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(code_facts, dict):
        return {}
    return {
        "overview": code_facts.get("overview") if isinstance(code_facts.get("overview"), dict) else {},
        "modules": _as_dict_list(code_facts.get("modules"))[:40],
        "pipeline_steps": _as_dict_list(code_facts.get("pipeline_steps"))[:40],
        "losses": _as_dict_list(code_facts.get("losses"))[:20],
        "key_insights": _as_dict_list(code_facts.get("key_insights"))[:20],
        "verified_facts": _as_dict_list(code_facts.get("verified_facts"))[:30],
        "blocked_or_risky_claims": _as_dict_list(code_facts.get("blocked_or_risky_claims"))[:30],
    }


def _snippet_preview_for_llm(core_snippets: dict[str, Any], *, project_root: Path) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for snippet in _as_dict_list(core_snippets.get("snippets"))[:30]:
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        path = _normalize_existing_repo_path(_as_text(source.get("path")), project_root) or _to_relpath(_as_text(source.get("path")), project_root)
        text = _as_text(snippet.get("text"))
        preview.append(
            {
                "snippet_id": _as_text(snippet.get("snippet_id")),
                "path": path,
                "symbol": _as_text(source.get("symbol")),
                "role": _as_text(snippet.get("role")),
                "preview": "\n".join(text.splitlines()[:20])[:2400],
            }
        )
    return preview


def _ignore_file_py_review_candidates(refined_payload: dict[str, Any], project_root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _as_text_list(refined_payload.get("ignore_files")):
        if not _looks_like_explicit_python_file(item):
            continue
        normalized = _normalize_existing_repo_path(item, project_root)
        if not normalized:
            continue
        preview_path = project_root / normalized
        try:
            text = preview_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        candidates.append(
            {
                "path": normalized,
                "preview": "\n".join(text.splitlines()[:80])[:5000],
            }
        )
    return candidates[:12]


def _candidate_repo_paths(
    *,
    refined_payload: dict[str, Any],
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    core_snippets: dict[str, Any],
    code_facts: dict[str, Any] | None,
    project_root: Path,
) -> list[str]:
    candidates: list[str] = []
    for role in _as_dict_list(refined_payload.get("module_roles")) + _as_dict_list(coarse_payload.get("module_roles")):
        candidates.append(_as_text(role.get("path")))
    for step in _as_dict_list(refined_payload.get("pipeline_steps")) + _as_dict_list(coarse_payload.get("pipeline_steps")):
        candidates.extend(_as_text_list(step.get("related_files")))
    candidates.extend(_as_text_list(refined_payload.get("priority_files")))
    candidates.extend(_as_text_list(coarse_payload.get("priority_files")))
    for item in _as_dict_list(method_code_alignment.get("modules")):
        method_module = item.get("method_module") if isinstance(item.get("method_module"), dict) else {}
        candidates.append(_as_text(method_module.get("path")))
    for item in _as_dict_list(method_code_alignment.get("pipeline_steps")):
        method_step = item.get("method_step") if isinstance(item.get("method_step"), dict) else {}
        candidates.extend(_as_text_list(method_step.get("related_files")))
    for snippet in _as_dict_list(core_snippets.get("snippets")):
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        candidates.append(_as_text(source.get("path")))
    if isinstance(code_facts, dict):
        for module in _as_dict_list(code_facts.get("modules")):
            candidates.append(_as_text(module.get("path")))
        for step in _as_dict_list(code_facts.get("pipeline_steps")):
            candidates.extend(_as_text_list(step.get("related_files")))
            candidates.append(_as_text(step.get("path")))
        for loss in _as_dict_list(code_facts.get("losses")):
            candidates.append(_as_text(loss.get("path")))
    normalized = [
        path
        for path in (_normalize_existing_repo_path(candidate, project_root) for candidate in candidates)
        if path
    ]
    return _dedupe_nonempty(normalized)


def _normalize_existing_repo_path(path: str, project_root: Path) -> str:
    raw = _as_text(path)
    if not raw:
        return ""
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
            rel = resolved.relative_to(project_root.resolve()).as_posix()
        except Exception:
            return ""
        return rel if resolved.is_file() else ""
    resolved = (project_root / raw).resolve()
    try:
        rel = resolved.relative_to(project_root.resolve()).as_posix()
    except Exception:
        return ""
    return rel if resolved.is_file() else ""


def _looks_like_explicit_python_file(path: str) -> bool:
    text = _as_text(path)
    return text.endswith(".py") and "*" not in text and "?" not in text


def _normalize_confidence_value(value: str, *, fallback: str = "medium") -> str:
    normalized = _as_text(value).lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    fallback_normalized = _as_text(fallback).lower()
    return fallback_normalized if fallback_normalized in {"low", "medium", "high"} else "medium"


def _normalize_severity_value(value: str) -> str:
    normalized = _as_text(value).lower()
    return normalized if normalized in {"low", "medium", "high"} else "medium"


def _has_nonempty_code_facts(code_facts: dict[str, Any] | None) -> bool:
    if not isinstance(code_facts, dict):
        return False
    for key in ("modules", "pipeline_steps", "losses", "verified_facts", "key_insights"):
        if _as_dict_list(code_facts.get(key)):
            return True
    return False


def _build_path_candidates(scan_report: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    core_files = scan_report.get("core_files") or []
    for item in core_files:
        if not isinstance(item, dict):
            continue
        path = _as_text(item.get("path"))
        if path:
            candidates.append({"path": path, "text": f"{path} {' '.join(_as_text_list(item.get('reasons')))}"})
    for item in (scan_report.get("targeted_mechanism_evidence") or []):
        if not isinstance(item, dict):
            continue
        path = _as_text(item.get("path"))
        if not path:
            continue
        topic = _as_text(item.get("topic"))
        snippet = _as_text(item.get("snippet"))
        candidates.append({"path": path, "text": f"{path} {topic} {snippet}"})
    for item in (scan_report.get("annotated_snippets_selected") or []):
        if not isinstance(item, dict):
            continue
        path = _as_text(item.get("path"))
        if not path:
            continue
        annotation = _as_text(item.get("annotation"))
        candidates.append({"path": path, "text": f"{path} {annotation}"})
    dedup: dict[str, str] = {}
    for item in candidates:
        path = item["path"]
        dedup[path] = (dedup.get(path, "") + " " + item.get("text", "")).strip()
    return [{"path": path, "text": text} for path, text in dedup.items()]


def _best_paths_for_query(query: str, candidates: list[dict[str, str]], top_k: int = 3) -> list[str]:
    terms = _tokens(query)
    if not terms:
        return []
    scored: list[tuple[int, str]] = []
    for item in candidates:
        text_tokens = set(_tokens(item.get("text", "")))
        overlap = len(terms & text_tokens)
        if overlap <= 0:
            continue
        scored.append((overlap, item["path"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    output: list[str] = []
    for _, path in scored:
        if path not in output:
            output.append(path)
        if len(output) >= top_k:
            break
    return output


def _build_coarse_priority_files(
    candidates: list[dict[str, str]],
    module_roles: list[dict[str, Any]],
    pipeline_steps: list[dict[str, Any]],
) -> list[str]:
    output: list[str] = []
    for item in candidates[:18]:
        output.append(item["path"])
    for role in module_roles:
        output.append(_as_text(role.get("path")))
    for step in pipeline_steps:
        output.extend(_as_text_list(step.get("related_files")))
    return _dedupe_nonempty(output)[:32]


def _build_default_mismatches(draft_payload: dict[str, Any], deemphasize_details: list[str]) -> list[dict[str, Any]]:
    mismatches = []
    constraints = draft_payload.get("scope_constraints")
    if isinstance(constraints, dict):
        if constraints.get("avoid_readme_only_claims"):
            mismatches.append(
                {
                    "description": "README-only statements should not be promoted to method claims without code evidence.",
                    "files": ["README.md"],
                    "severity": "high",
                }
            )
        if constraints.get("avoid_paper_only_novelty_claims"):
            mismatches.append(
                {
                    "description": "Paper-only novelty wording must be grounded in executable code evidence.",
                    "files": ["paper.pdf", "paper_full.txt"],
                    "severity": "high",
                }
            )
    for text in deemphasize_details[:4]:
        mismatches.append(
            {
                "description": f"Detail to de-emphasize during retrieval: {text}",
                "files": [],
                "severity": "medium",
            }
        )
    if not mismatches:
        mismatches.append(
            {
                "description": "Auto-generated markers require stage1/stage2 evidence checks before final method claims.",
                "files": [],
                "severity": "medium",
            }
        )
    return mismatches[:12]


def _build_ignore_files(scope_constraints: Any, deemphasize_details: list[str]) -> list[str]:
    ignores = list(DEFAULT_IGNORE_FILES)
    if isinstance(scope_constraints, dict) and scope_constraints.get("avoid_readme_only_claims"):
        ignores.append("README*")
    for text in deemphasize_details:
        lower = text.lower()
        if "checkpoint" in lower:
            ignores.extend(["**/checkpoint*/**", "**/*.ckpt"])
        if "demo" in lower or "serving" in lower:
            ignores.extend(["**/serve/**", "**/demo/**"])
        if "dataset" in lower and "prompt" in lower:
            ignores.append("**/prompts/**")
    return _dedupe_nonempty(ignores)[:40]


def _refine_module_roles(
    *,
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    snippet_map: dict[str, dict[str, Any]],
    project_root: Path,
) -> list[dict[str, Any]]:
    coarse_roles = _as_dict_list(coarse_payload.get("module_roles"))
    coarse_by_role = {_as_text(role.get("role")).lower(): dict(role) for role in coarse_roles if _as_text(role.get("role"))}
    refined: list[dict[str, Any]] = []

    for item in _as_dict_list(method_code_alignment.get("modules")):
        method_module = item.get("method_module")
        if not isinstance(method_module, dict):
            continue
        matched = sorted(
            [m for m in _as_dict_list(item.get("matched_snippets")) if _to_float(m.get("confidence")) >= 0.35],
            key=lambda m: _to_float(m.get("confidence")),
            reverse=True,
        )
        best = matched[0] if matched else {}
        best_id = _as_text(best.get("snippet_id"))
        snippet = snippet_map.get(best_id, {})

        path = _as_text(snippet.get("path")) or _as_text(best.get("file")) or _as_text(method_module.get("path"))
        path = _to_relpath(path, project_root)

        symbol = (
            _as_text(snippet.get("symbol"))
            or _as_text(method_module.get("symbol"))
            or _as_text(best.get("class_name"))
            or _as_text(best.get("function"))
        )
        role_text = _as_text(method_module.get("role")) or _as_text(method_module.get("name"))
        if not role_text:
            continue
        coarse = coarse_by_role.get(role_text.lower(), {})
        importance = _as_text(coarse.get("importance")) or _as_text(method_module.get("importance")) or "core"
        notes = _as_text(coarse.get("notes")) or _as_text(method_module.get("notes"))
        if matched:
            notes = (
                f"{notes} "
                f"[auto-refined from stage1/stage2; top_match={best_id}; confidence={_to_float(best.get('confidence')):.2f}]"
            ).strip()

        refined.append(
            {
                "path": _as_text(coarse.get("path")) or path,
                "symbol": _as_text(coarse.get("symbol")) or symbol,
                "role": role_text,
                "importance": importance,
                "is_novel": bool(coarse.get("is_novel", method_module.get("is_novel"))),
                "notes": notes,
                "supporting_files": _dedupe_nonempty(_as_text_list(coarse.get("supporting_files")) + ([path] if path else []))[:6],
                "supporting_symbols": _dedupe_nonempty(_as_text_list(coarse.get("supporting_symbols")) + ([symbol] if symbol else []))[:6],
                "support_confidence": _normalize_confidence_value(
                    "high" if _to_float(best.get("confidence")) >= 0.7 else "medium",
                    fallback=_as_text(coarse.get("support_confidence")) or "medium",
                ),
                "caveats": _as_text_list(coarse.get("caveats")),
                "risky_details": _as_text_list(coarse.get("risky_details")),
            }
        )

    if not refined:
        refined = coarse_roles
    else:
        existing_roles = {_as_text(item.get("role")).lower() for item in refined}
        for role in coarse_roles:
            role_key = _as_text(role.get("role")).lower()
            if role_key not in existing_roles:
                refined.append(role)
                existing_roles.add(role_key)
    return _dedupe_module_roles(refined)[:40]


def _refine_pipeline_steps(
    *,
    coarse_payload: dict[str, Any],
    method_code_alignment: dict[str, Any],
    snippet_map: dict[str, dict[str, Any]],
    project_root: Path,
) -> list[dict[str, Any]]:
    coarse_steps = _as_dict_list(coarse_payload.get("pipeline_steps"))
    coarse_by_name = {_as_text(step.get("name")).lower(): step for step in coarse_steps}
    refined: list[dict[str, Any]] = []

    for item in _as_dict_list(method_code_alignment.get("pipeline_steps")):
        method_step = item.get("method_step")
        if not isinstance(method_step, dict):
            continue
        name = _as_text(method_step.get("name"))
        if not name:
            continue
        related_files = _as_text_list(method_step.get("related_files"))
        for matched in _as_dict_list(item.get("matched_snippets")):
            if _to_float(matched.get("confidence")) < 0.35:
                continue
            snippet = snippet_map.get(_as_text(matched.get("snippet_id")), {})
            path = _to_relpath(_as_text(snippet.get("path")), project_root)
            if path:
                related_files.append(path)
        coarse = coarse_by_name.get(name.lower(), {})
        if not related_files and name.lower() in coarse_by_name:
            related_files.extend(_as_text_list(coarse_by_name[name.lower()].get("related_files")))
        supporting_symbols = []
        for matched in _as_dict_list(item.get("matched_snippets")):
            if _to_float(matched.get("confidence")) < 0.35:
                continue
            snippet = snippet_map.get(_as_text(matched.get("snippet_id")), {})
            symbol = _as_text(snippet.get("symbol")) or _as_text(matched.get("class_name")) or _as_text(matched.get("function"))
            if symbol:
                supporting_symbols.append(symbol)
        supporting_files = [
            normalized
            for normalized in (_normalize_existing_repo_path(path, project_root) for path in related_files)
            if normalized
        ]
        refined.append(
            {
                "name": name,
                "purpose": _as_text(coarse.get("purpose")) or _as_text(method_step.get("purpose")) or _as_text(method_step.get("description")),
                "input": _as_text_list(coarse.get("input")) or _as_text_list(method_step.get("inputs")),
                "output": _as_text_list(coarse.get("output")) or _as_text_list(method_step.get("outputs")),
                "related_files": _as_text_list(coarse.get("related_files")) or _dedupe_nonempty(related_files)[:8],
                "highlight_level": _as_text(coarse.get("highlight_level")) or _as_text(method_step.get("highlight_level")) or "main",
                "omit_from_main_figure": bool(coarse.get("omit_from_main_figure"))
                if "omit_from_main_figure" in coarse
                else not bool(method_step.get("include_in_main_figure", True)),
                "supporting_files": _dedupe_nonempty(_as_text_list(coarse.get("supporting_files")) + supporting_files)[:8],
                "supporting_symbols": _dedupe_nonempty(_as_text_list(coarse.get("supporting_symbols")) + supporting_symbols)[:8],
                "support_confidence": _normalize_confidence_value(
                    "high" if any(_to_float(m.get("confidence")) >= 0.7 for m in _as_dict_list(item.get("matched_snippets"))) else "medium",
                    fallback=_as_text(coarse.get("support_confidence")) or "medium",
                ),
                "caveats": _as_text_list(coarse.get("caveats")),
                "risky_details": _as_text_list(coarse.get("risky_details")),
            }
        )

    if not refined:
        refined = coarse_steps
    return _dedupe_steps(refined)[:40]


def _refine_priority_files(
    *,
    coarse_payload: dict[str, Any],
    module_roles: list[dict[str, Any]],
    pipeline_steps: list[dict[str, Any]],
    core_snippets: dict[str, Any],
) -> list[str]:
    priority_files = _as_text_list(coarse_payload.get("priority_files"))
    priority_files.extend([_as_text(role.get("path")) for role in module_roles])
    for role in module_roles:
        priority_files.extend(_as_text_list(role.get("supporting_files")))
    for step in pipeline_steps:
        priority_files.extend(_as_text_list(step.get("related_files")))
        priority_files.extend(_as_text_list(step.get("supporting_files")))

    coverage = core_snippets.get("coverage")
    if isinstance(coverage, dict):
        priority_files.extend(_as_text_list(coverage.get("top_files_by_snippet_count")))
    return _dedupe_nonempty(priority_files)[:48]


def _attach_supports(
    *,
    entries: list[dict[str, Any]],
    text_field: str,
    module_roles: list[dict[str, Any]],
    pipeline_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    supports = _build_support_candidates(module_roles, pipeline_steps)
    if not supports:
        return entries

    output = []
    for item in entries:
        text = _as_text(item.get(text_field))
        ranked = _rank_supports(text, supports)
        files = [_as_text(s.get("path")) for s in ranked[:3]]
        symbols = [_as_text(s.get("symbol")) for s in ranked[:3]]
        if not _dedupe_nonempty(files):
            files = [_as_text(s.get("path")) for s in supports[:2]]
            symbols = [_as_text(s.get("symbol")) for s in supports[:2]]
        merged = dict(item)
        merged["supporting_files"] = _dedupe_nonempty(_as_text_list(item.get("supporting_files")) + files)[:4]
        merged["supporting_functions"] = _dedupe_nonempty(_as_text_list(item.get("supporting_functions")) + symbols)[:5]
        output.append(merged)
    return output


def _build_support_candidates(
    module_roles: list[dict[str, Any]],
    pipeline_steps: list[dict[str, Any]],
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for role in module_roles:
        path = _as_text(role.get("path"))
        if not path:
            continue
        symbol = _as_text(role.get("symbol"))
        text = " ".join([_as_text(role.get("role")), symbol, path]).strip()
        candidates.append({"path": path, "symbol": symbol, "text": text})
        for support_path in _as_text_list(role.get("supporting_files")):
            candidates.append(
                {
                    "path": support_path,
                    "symbol": " ".join(_as_text_list(role.get("supporting_symbols"))),
                    "text": " ".join([_as_text(role.get("role")), support_path]).strip(),
                }
            )
    for step in pipeline_steps:
        for path in _as_text_list(step.get("related_files")):
            text = " ".join([_as_text(step.get("name")), _as_text(step.get("purpose")), path]).strip()
            candidates.append({"path": path, "symbol": "", "text": text})
        for support_path in _as_text_list(step.get("supporting_files")):
            candidates.append(
                {
                    "path": support_path,
                    "symbol": " ".join(_as_text_list(step.get("supporting_symbols"))),
                    "text": " ".join([_as_text(step.get("name")), _as_text(step.get("purpose")), support_path]).strip(),
                }
            )
    dedup: dict[tuple[str, str], dict[str, str]] = {}
    for cand in candidates:
        key = (cand["path"], cand["symbol"])
        dedup[key] = cand
    return list(dedup.values())


def _rank_supports(text: str, supports: list[dict[str, str]]) -> list[dict[str, str]]:
    query_tokens = _tokens(text)
    scored: list[tuple[int, dict[str, str]]] = []
    for support in supports:
        tokens = _tokens(support.get("text", ""))
        overlap = len(query_tokens & tokens)
        if overlap <= 0:
            continue
        scored.append((overlap, support))
    scored.sort(key=lambda x: (-x[0], x[1].get("path", "")))
    return [support for _, support in scored] or supports


def _ensure_potential_mismatches(
    mismatches: list[dict[str, Any]],
    module_roles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out = list(mismatches)
    unresolved = [role for role in module_roles if not _as_text(role.get("symbol"))]
    if unresolved:
        out.append(
            {
                "description": "Some auto-selected module roles still miss explicit symbols and should be verified manually.",
                "files": _dedupe_nonempty([_as_text(role.get("path")) for role in unresolved])[:6],
                "severity": "medium",
            }
        )
    return out[:20]


def _snippet_index(core_snippets: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for snippet in _as_dict_list(core_snippets.get("snippets")):
        snippet_id = _as_text(snippet.get("snippet_id"))
        if not snippet_id:
            continue
        source = snippet.get("source")
        if not isinstance(source, dict):
            source = {}
        index[snippet_id] = {
            "path": _as_text(source.get("path")),
            "symbol": _as_text(source.get("symbol")),
        }
    return index


def _dedupe_module_roles(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        role = _as_text(item.get("role"))
        path = _as_text(item.get("path"))
        if not role or not path:
            continue
        key = role.lower()
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(item)
            continue
        existing_score = _author_role_support_score(existing)
        candidate_score = _author_role_support_score(item)
        preferred = dict(item) if candidate_score > existing_score else existing
        other = existing if preferred is not existing else item
        preferred["supporting_files"] = _dedupe_nonempty(
            _as_text_list(preferred.get("supporting_files")) + _as_text_list(other.get("supporting_files"))
        )[:6]
        preferred["supporting_symbols"] = _dedupe_nonempty(
            _as_text_list(preferred.get("supporting_symbols")) + _as_text_list(other.get("supporting_symbols"))
        )[:6]
        preferred["caveats"] = _dedupe_nonempty(
            _as_text_list(preferred.get("caveats")) + _as_text_list(other.get("caveats"))
        )[:6]
        preferred["risky_details"] = _dedupe_nonempty(
            _as_text_list(preferred.get("risky_details")) + _as_text_list(other.get("risky_details"))
        )[:6]
        grouped[key] = preferred
    return list(grouped.values())


def _author_role_support_score(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        len(_as_text_list(item.get("supporting_files"))),
        1 if _as_text(item.get("symbol")) else 0,
        {"low": 0, "medium": 1, "high": 2}.get(_as_text(item.get("support_confidence")).lower(), 1),
    )


def _dedupe_steps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        name = _as_text(item.get("name"))
        purpose = _as_text(item.get("purpose"))
        if not name or not purpose:
            continue
        key = name.lower()
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(item)
            continue
        merged = dict(existing)
        merged["supporting_files"] = _dedupe_nonempty(
            _as_text_list(existing.get("supporting_files")) + _as_text_list(item.get("supporting_files"))
        )[:8]
        merged["supporting_symbols"] = _dedupe_nonempty(
            _as_text_list(existing.get("supporting_symbols")) + _as_text_list(item.get("supporting_symbols"))
        )[:8]
        merged["caveats"] = _dedupe_nonempty(_as_text_list(existing.get("caveats")) + _as_text_list(item.get("caveats")))[:6]
        merged["risky_details"] = _dedupe_nonempty(
            _as_text_list(existing.get("risky_details")) + _as_text_list(item.get("risky_details"))
        )[:6]
        grouped[key] = merged
    return list(grouped.values())


def _resolve_priority_ignore_conflicts(payload: dict[str, Any]) -> dict[str, Any]:
    ignore_entries = set(_as_text_list(payload.get("ignore_files")))
    if not ignore_entries:
        return payload
    original_priority = _as_text_list(payload.get("priority_files"))
    removed_priority = sorted(ignore_entries.intersection(original_priority))
    filtered_priority = [path for path in original_priority if path not in ignore_entries]
    if filtered_priority != original_priority:
        payload = dict(payload)
        payload["priority_files"] = filtered_priority
        mismatches = list(_as_dict_list(payload.get("potential_mismatches")))
        mismatches.append(
            {
                "description": "Priority files that also appeared in ignore_files were removed from priority_files during author-markers validation.",
                "files": removed_priority,
                "severity": "medium",
            }
        )
        payload["potential_mismatches"] = mismatches[:20]
    return payload


def _to_relpath(path: str, project_root: Path) -> str:
    raw = _as_text(path)
    if not raw:
        return ""
    p = Path(raw)
    if not p.is_absolute():
        return raw.replace("\\", "/")
    try:
        return p.resolve().relative_to(project_root.resolve()).as_posix()
    except Exception:
        return raw.replace("\\", "/")


def _normalize_mainline(value: Any) -> str:
    if isinstance(value, list):
        parts = _as_text_list(value)
        return " -> ".join(parts)
    return _as_text(value)


def _dedupe_nonempty(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _as_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _as_text(value: Any) -> str:
    text = str(value or "").strip()
    return text


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_as_text(item) for item in value if _as_text(item)]
    text = _as_text(value)
    return [text] if text else []


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", (text or "").lower())}


def _is_novel_text(text: str) -> bool:
    t = (text or "").lower()
    keys = ("novel", "new", "proposed", "pooling", "curriculum", "predict")
    return any(key in t for key in keys)


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "stage",
    "method",
    "mainline",
    "paper",
    "story",
    "order",
    "alignment",
    "through",
    "while",
    "without",
    "using",
    "used",
    "more",
    "less",
    "than",
    "when",
}

