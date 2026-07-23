from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code2paper.core.schemas import AuthorMarkers, LLMConfig, LLMProvider
from code2paper.fusion.markers import (
    build_generated_author_markers,
    load_template_payload,
    save_generated_author_markers,
)
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.role_config import AUTHORING_PLANNER, apply_role_config
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response


@dataclass(frozen=True)
class ResolvedAuthorInput:
    source: str
    effective_author_markers_path: Path
    intent_path: Path | None = None
    generated_author_markers_path: Path | None = None

    @property
    def template_path(self) -> Path | None:
        """Compatibility alias for older callers and reports."""
        return self.intent_path


def resolve_author_input(
    *,
    intent_path: str | Path | None,
    project_root: Path,
    method_root: Path,
    core_top_k: int,
    annotation_required: bool,
    llm_config: LLMConfig | None = None,
) -> ResolvedAuthorInput:
    raw_intent = str(intent_path or "").strip()

    resolved_intent_path: Path | None = None
    template_payload: dict[str, Any] = {}
    source = "generated"
    if raw_intent:
        resolved_intent_path = Path(raw_intent).expanduser().resolve()
        template_payload = load_template_payload(resolved_intent_path)
        source = "intent"
    generated = build_generated_author_markers(
        template_payload=template_payload,
        annotation_report={},
        project_root=project_root,
    )
    llm_resolved = _resolve_author_markers_via_llm(
        project_root=project_root,
        template_payload=template_payload,
        annotation_report={},
        baseline_payload=generated,
        llm_config=llm_config,
    )
    if llm_resolved is not None:
        generated = llm_resolved
    validated_markers = AuthorMarkers.model_validate(generated)
    generated_markers_path = save_generated_author_markers(
        generated_markers=validated_markers.model_dump(mode="json"),
        out_dir=method_root,
    )
    return ResolvedAuthorInput(
        source=source,
        effective_author_markers_path=generated_markers_path,
        intent_path=resolved_intent_path,
        generated_author_markers_path=generated_markers_path,
    )


def _resolve_author_markers_via_llm(
    *,
    project_root: Path,
    template_payload: dict[str, Any],
    annotation_report: dict[str, Any],
    baseline_payload: dict[str, Any],
    llm_config: LLMConfig | None,
) -> dict[str, Any] | None:
    config = llm_config
    if not template_payload:
        return None
    if config is None or config.provider == LLMProvider.NONE:
        return None
    client = LLMClient(apply_role_config(config, AUTHORING_PLANNER))
    request = LLMRequest(
        prompt_template_id="input_resolution_author_markers_v1",
        prompt=_author_markers_resolution_prompt(),
        input_payload={
            "task_background": {
                "project_root": str(project_root),
                "goal": "Improve the original author YAML using the draft/template intent as the primary narrative spec, with code annotations used only as weak implementation hints.",
                "downstream_contract": "The result is read directly by Phase 2 as AuthorMarkers YAML. Keep the structure strict and implementation-grounded.",
            },
            "original_author_yaml": template_payload,
            "annotation_summary": _annotation_summary_for_llm(annotation_report),
            "baseline_author_markers": baseline_payload,
        },
        schema_name="author_markers",
        response_json_schema=json_schema_for(AuthorMarkers),
    )
    response = client.complete(request)
    if response.blocked_reason:
        return None
    parsed, _parse_error = try_parse_structured_response(response.text, AuthorMarkers)
    if parsed is None:
        return None
    return _merge_author_markers_with_baseline(
        baseline=AuthorMarkers.model_validate(baseline_payload).model_dump(mode="json"),
        revised=parsed.model_dump(mode="json"),
    )


def _annotation_summary_for_llm(annotation_report: dict[str, Any]) -> dict[str, Any]:
    core_files = []
    for item in annotation_report.get("core_files") or []:
        if not isinstance(item, dict):
            continue
        core_files.append(
            {
                "path": str(item.get("path") or "").strip(),
                "file_role": str(item.get("file_role") or "").strip(),
                "score": item.get("score", 0),
                "annotation_count": item.get("annotation_count", 0),
                "annotations": list(item.get("annotations") or []),
            }
        )
    annotated_files = []
    seen: set[str] = set()
    for bucket_name in (
        "method_core_files",
        "objective_support_files",
        "execution_support_files",
        "evaluation_support_files",
        "data_support_files",
        "infra_files",
    ):
        for item in annotation_report.get(bucket_name) or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if not path or path in seen or int(item.get("annotation_count", 0)) <= 0:
                continue
            seen.add(path)
            annotated_files.append(
                {
                    "path": path,
                    "file_role": str(item.get("file_role") or "").strip(),
                    "score": item.get("score", 0),
                    "annotations": list(item.get("annotations") or []),
                }
            )
    return {
        "repo_root": annotation_report.get("repo_root", ""),
        "core_top_k": annotation_report.get("core_top_k", 0),
        "annotated_file_count": annotation_report.get("annotated_file_count", 0),
        "scanned_code_files": annotation_report.get("scanned_code_files", 0),
        "core_missing_annotations": list(annotation_report.get("core_missing_annotations") or []),
        "core_files": core_files,
        "annotated_files": annotated_files,
    }


def _merge_author_markers_with_baseline(*, baseline: dict[str, Any], revised: dict[str, Any]) -> dict[str, Any]:
    merged = dict(revised)
    for key in ("project_goal", "paper_method_goal", "implementation_scope", "method_mainline"):
        if not str(merged.get(key) or "").strip():
            merged[key] = baseline.get(key, "")
    for key in ("paper_story_order", "priority_files", "ignore_files", "module_roles", "pipeline_steps", "design_intents", "innovation_claims", "potential_mismatches"):
        if not isinstance(merged.get(key), list) or len(merged.get(key) or []) == 0:
            merged[key] = list(baseline.get(key) or [])
    merged["deemphasize_details"] = _merge_unique_texts(
        list(baseline.get("deemphasize_details") or []),
        list(merged.get("deemphasize_details") or []),
    )
    if not str(merged.get("latex_expression_preference") or "").strip():
        merged["latex_expression_preference"] = baseline.get("latex_expression_preference", "balanced")
    return merged


def _merge_unique_texts(base: list[Any], extra: list[Any]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(base) + list(extra):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _author_markers_resolution_prompt() -> str:
    return (
        "You are improving an AuthorMarkers YAML used by a code-to-paper pipeline.\n"
        "Task background:\n"
        "- The input includes an original author YAML, extracted code annotations, and a deterministic baseline AuthorMarkers draft.\n"
        "- Your output is read directly by Phase 2 as a strict AuthorMarkers object.\n"
        "- Preserve the original YAML and baseline draft as the primary narrative source.\n"
        "- Use annotations only as weak implementation hints for path binding, support overlays, and conservative disambiguation.\n"
        "- Do not let annotations rewrite the mainline, story order, or high-level pipeline unless the original YAML is clearly empty or invalid.\n"
        "- Do not fabricate file paths, symbols, pipeline steps, or innovation claims not supported by the provided inputs.\n"
        "- Keep the result conservative, code-grounded, and paper-facing.\n"
        "Requirements:\n"
        "- Output only valid JSON for the AuthorMarkers schema.\n"
        "- Keep original non-empty sections when still plausible; refine them rather than dropping them.\n"
        "- Prefer the baseline AuthorMarkers draft for file/path grounding when it is already plausible.\n"
        "- Use annotated files in priority_files and related_files only when they help fill missing bindings or confirm ambiguous ones.\n"
        "- Map design-intent or innovation annotations only when the original YAML leaves those sections empty or underspecified.\n"
        "- Keep module_roles and pipeline_steps aligned with actual code paths without inflating annotation content into paper claims.\n"
        "- If a detail is uncertain, keep it conservative instead of inventing specifics."
    )
