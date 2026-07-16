"""Adapters from story-first author markers to embedded code-agent inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _slug(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip().lower()).strip("_")
    return slug or fallback


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _symbol_target(path: str, symbol: str, *, source: str, role: str = "") -> dict[str, Any]:
    return {
        "path": path,
        "symbol": symbol,
        "source": source,
        "role": role,
    }


def to_method_summary(author_markers: Any) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    symbol_targets: list[dict[str, Any]] = []
    for idx, role in enumerate(author_markers.module_roles, start=1):
        module_name = (role.role or role.symbol or Path(role.path).stem).strip()
        module_id = f"M{idx}"
        modules.append(
            {
                "module_id": module_id,
                "name": module_name,
                "path": role.path,
                "symbol": role.symbol,
                "role": role.role,
                "importance": _enum_value(role.importance),
                "is_novel": role.is_novel,
                "notes": role.notes,
                "io": {},
                "verification": {
                    "expected_path": role.path,
                    "expected_symbol": role.symbol,
                    "support_status": "unverified",
                    "evidence_policy": "must_match_symbol_when_available",
                },
            }
        )
        if role.symbol:
            symbol_targets.append(_symbol_target(role.path, role.symbol, source=f"module:{module_id}", role=role.role))

    steps: list[dict[str, Any]] = []
    stage_files: list[dict[str, Any]] = []
    for idx, step in enumerate(author_markers.pipeline_steps, start=1):
        step_id = f"S{idx}"
        steps.append(
            {
                "step_id": step_id,
                "name": step.name,
                "description": step.purpose,
                "purpose": step.purpose,
                "inputs": list(step.input),
                "outputs": list(step.output),
                "related_files": list(step.related_files),
                "role_key": _slug(step.name, f"step_{idx}"),
                "highlight_level": _enum_value(step.highlight_level),
                "include_in_main_figure": not step.omit_from_main_figure,
                "verification": {
                    "support_status": "unverified",
                    "required_files": list(step.related_files),
                    "evidence_policy": "at_least_one_related_file_or_symbol",
                },
            }
        )
        for path in step.related_files:
            stage_files.append({"step_id": step_id, "step_name": step.name, "path": path})

    losses: list[dict[str, Any]] = []
    for idx, claim in enumerate(author_markers.innovation_claims, start=1):
        text = claim.claim.lower()
        if "loss" in text or "objective" in text:
            losses.append({"name": claim.claim, "formula_ref": f"EQ{idx}", "source_claim_id": f"C{idx}"})

    innovations: list[dict[str, Any]] = []
    claim_support_files: list[str] = []
    for idx, claim in enumerate(author_markers.innovation_claims[:30], start=1):
        claim_id = f"C{idx}"
        innovations.append(
            {
                "claim_id": claim_id,
                "what": claim.claim,
                "supporting_files": list(claim.supporting_files),
                "supporting_functions": list(claim.supporting_functions),
                "confidence": _enum_value(claim.confidence),
                "caveats": list(claim.caveats),
                "support_status": "unverified",
            }
        )
        claim_support_files.extend(claim.supporting_files)
        for path in claim.supporting_files:
            for symbol in claim.supporting_functions:
                symbol_targets.append(_symbol_target(path, symbol, source=f"claim:{claim_id}"))

    design_intents: list[dict[str, Any]] = []
    for idx, intent in enumerate(author_markers.design_intents[:30], start=1):
        intent_id = f"I{idx}"
        design_intents.append(
            {
                "intent_id": intent_id,
                "intent": intent.intent,
                "rationale": intent.rationale,
                "supporting_files": list(intent.supporting_files),
                "supporting_functions": list(intent.supporting_functions),
                "confidence": _enum_value(intent.confidence),
                "caveats": list(intent.caveats),
                "support_status": "unverified",
            }
        )
        claim_support_files.extend(intent.supporting_files)
        for path in intent.supporting_files:
            for symbol in intent.supporting_functions:
                symbol_targets.append(_symbol_target(path, symbol, source=f"intent:{intent_id}"))

    potential_mismatches = [
        {
            "mismatch_id": f"R{idx}",
            "description": mismatch.description,
            "files": list(mismatch.files),
            "severity": _enum_value(mismatch.severity),
            "guard_policy": "do_not_promote_to_verified_claim_without_direct_evidence",
        }
        for idx, mismatch in enumerate(author_markers.potential_mismatches[:30], start=1)
    ]

    priority_paths = _dedupe(
        list(author_markers.priority_files)
        + [role.path for role in author_markers.module_roles]
        + [path for step in author_markers.pipeline_steps for path in step.related_files]
        + claim_support_files
    )
    symbol_targets = [
        target
        for target in symbol_targets
        if target.get("path") and target.get("symbol")
    ]

    return {
        "meta": {
            "version": "story-first-method-summary-v2",
            "source": "author_markers.yaml",
            "conversion_policy": "author_intent_must_be_verified_by_code",
        },
        "scope": {
            "project_goal": author_markers.project_goal,
            "paper_method_goal": author_markers.paper_method_goal,
            "implementation_scope": author_markers.implementation_scope,
            "priority_files": list(author_markers.priority_files),
            "ignore_files": list(author_markers.ignore_files),
            "deemphasize_details": list(author_markers.deemphasize_details),
            "latex_expression_preference": _enum_value(author_markers.latex_expression_preference),
        },
        "method": {
            "task_setting": author_markers.project_goal,
            "paper_method_goal": author_markers.paper_method_goal,
            "mainline": author_markers.method_mainline,
            "story_order": list(author_markers.paper_story_order),
            "modules": modules,
            "pipeline_steps": steps,
            "losses": losses,
            "innovations": innovations,
            "design_intents": design_intents,
            "potential_mismatches": potential_mismatches,
            "deemphasize_details": list(author_markers.deemphasize_details),
            "latex_expression_preference": _enum_value(author_markers.latex_expression_preference),
        },
        "retrieval_hints": {
            "priority_paths": priority_paths,
            "symbol_targets": symbol_targets,
            "stage_files": stage_files,
            "claim_support_files": _dedupe(claim_support_files),
            "negative_globs": list(author_markers.ignore_files),
        },
        "verification_plan": {
            "must_verify": [
                {
                    "target_id": module["module_id"],
                    "target_type": "module",
                    "description": module["role"],
                    "paths": [module["path"]],
                    "symbols": [module["symbol"]] if module.get("symbol") else [],
                }
                for module in modules
            ]
            + [
                {
                    "target_id": step["step_id"],
                    "target_type": "pipeline_step",
                    "description": step["name"],
                    "paths": list(step["related_files"]),
                    "symbols": [],
                }
                for step in steps
            ],
            "soft_claims": innovations + design_intents,
            "known_risks": potential_mismatches,
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
