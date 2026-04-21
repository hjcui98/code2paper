"""Adapters from story-first author markers to embedded code-agent inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def to_method_summary(author_markers: Any) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    for idx, role in enumerate(author_markers.module_roles, start=1):
        module_name = (role.role or role.symbol or Path(role.path).stem).strip()
        modules.append(
            {
                "module_id": f"M{idx}",
                "name": module_name,
                "path": role.path,
                "symbol": role.symbol,
                "role": role.role,
                "importance": role.importance.value if hasattr(role.importance, "value") else str(role.importance),
                "is_novel": role.is_novel,
                "io": {},
            }
        )

    steps: list[dict[str, Any]] = []
    for idx, step in enumerate(author_markers.pipeline_steps, start=1):
        steps.append(
            {
                "step_id": f"S{idx}",
                "name": step.name,
                "description": step.purpose,
                "purpose": step.purpose,
                "inputs": list(step.input),
                "outputs": list(step.output),
                "related_files": list(step.related_files),
                "highlight_level": step.highlight_level.value,
                "include_in_main_figure": not step.omit_from_main_figure,
            }
        )

    losses: list[dict[str, Any]] = []
    for idx, claim in enumerate(author_markers.innovation_claims, start=1):
        text = claim.claim.lower()
        if "loss" in text or "objective" in text:
            losses.append({"name": claim.claim, "formula_ref": f"EQ{idx}"})

    return {
        "method": {
            "task_setting": author_markers.project_goal,
            "paper_method_goal": author_markers.paper_method_goal,
            "mainline": author_markers.method_mainline,
            "story_order": list(author_markers.paper_story_order),
            "modules": modules,
            "pipeline_steps": steps,
            "losses": losses,
            "innovations": [{"what": claim.claim} for claim in author_markers.innovation_claims[:30]],
            "design_intents": [
                {
                    "intent": intent.intent,
                    "supporting_files": list(intent.supporting_files),
                    "supporting_functions": list(intent.supporting_functions),
                }
                for intent in author_markers.design_intents[:30]
            ],
            "potential_mismatches": [
                {"description": mismatch.description, "files": list(mismatch.files)}
                for mismatch in author_markers.potential_mismatches[:30]
            ],
            "deemphasize_details": list(author_markers.deemphasize_details),
            "latex_expression_preference": author_markers.latex_expression_preference.value,
        }
    }


def to_structured_sections(author_markers: Any) -> dict[str, Any]:
    lines = [
        f"Goal: {author_markers.project_goal}",
        f"Method goal: {author_markers.paper_method_goal}",
        f"Mainline: {author_markers.method_mainline}",
    ]
    for step in author_markers.pipeline_steps:
        lines.append(f"{step.name}: {step.purpose}")
    for role in author_markers.module_roles:
        lines.append(f"{role.role}: {role.path}::{role.symbol}".rstrip(":"))
    return {
        "paper_sections": [
            {
                "section_type": "method",
                "section_name": "Method",
                "content": "\n".join(line for line in lines if line.strip()),
            }
        ]
    }
