from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


def _to_list_str(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                out.append(text)
        return out
    text = str(value or "").strip()
    return [text] if text else []


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _enum_latex_preference(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"implementation-faithful", "balanced", "paper-abstract"}:
        return text
    if text in {"faithful", "implementation"}:
        return "implementation-faithful"
    if text in {"abstract", "paper"}:
        return "paper-abstract"
    return "balanced"


def _looks_like_repo_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(ch in text for ch in ("/", "\\", "*", "?")):
        return True
    return Path(text).suffix.lower() in {
        ".py",
        ".sh",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".txt",
        ".md",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".js",
        ".ts",
    }


def _module_roles_from_template(template: dict[str, Any]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    blocks = template.get("key_building_blocks")
    if not isinstance(blocks, list):
        return roles
    for block in blocks:
        if not isinstance(block, dict):
            continue
        name = str(block.get("name") or "").strip()
        role = str(block.get("role") or name or "core_component").strip()
        if not name and not role:
            continue
        path = str(block.get("path") or block.get("related_file") or "").strip()
        emphasis = str(block.get("emphasis") or "high").strip().lower()
        importance = "core" if emphasis in {"high", "main", "critical"} else ("supporting" if emphasis in {"medium", "mid"} else "utility")
        keep_name = _as_bool(block.get("keep_name"), default=True)
        symbol = str(block.get("symbol") or "").strip()
        if not symbol:
            symbol = name if keep_name else ""
        notes_parts = [f"from_template_block:{name}" if name else "from_template_block"]
        explicit_alias = str(block.get("paper_alias") or "").strip()
        if explicit_alias:
            notes_parts.append(f"paper_alias:{explicit_alias}")
        roles.append(
            {
                "path": path,
                "symbol": symbol,
                "role": role,
                "importance": importance,
                "is_novel": False,
                "notes": "; ".join(notes_parts),
            }
        )
    return roles


def _pipeline_steps_from_template(template: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    raw = template.get("pipeline_steps")
    if not isinstance(raw, list):
        return steps
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        purpose = str(item.get("purpose") or "").strip()
        if not name and not purpose:
            continue
        explicit_related_files = _to_list_str(item.get("related_files"))
        legacy_related_components = _to_list_str(item.get("related_components"))
        related_files = _merge_nonempty(
            explicit_related_files,
            [value for value in legacy_related_components if _looks_like_repo_path(value)],
        )
        component_hints = [value for value in legacy_related_components if not _looks_like_repo_path(value)]
        purpose_text = purpose or name or "pipeline step"
        if component_hints:
            purpose_text = f"{purpose_text} Related components: {', '.join(component_hints)}."
        steps.append(
            {
                "name": name or "unnamed_step",
                "purpose": purpose_text,
                "input": [],
                "output": [],
                "related_files": related_files,
                "highlight_level": "main",
                "omit_from_main_figure": False,
            }
        )
    return steps


def _design_intents_from_template(template: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in template.get("design_intents") or []:
        if not isinstance(item, dict):
            continue
        intent = str(item.get("intent") or "").strip()
        rationale = str(item.get("rationale") or "").strip()
        if not intent:
            continue
        out.append(
            {
                "intent": intent,
                "rationale": rationale,
                "supporting_files": [],
                "supporting_functions": [],
                "confidence": "medium",
                "caveats": [],
            }
        )
    return out


def _innovation_claims_from_template(template: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for text in _to_list_str(template.get("possible_distinguishing_points")):
        claims.append(
            {
                "claim": text,
                "supporting_files": [],
                "supporting_functions": [],
                "confidence": "low",
                "caveats": ["needs_hard_code_evidence"],
            }
        )
    return claims


def _annotation_design_intents(annotation_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in annotation_items:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        for annotation in item.get("annotations") or []:
            if annotation.get("kind") != "mark":
                continue
            mark_type = str(annotation.get("mark_type") or "").strip().lower()
            if mark_type != "design-intent":
                continue
            target = str(annotation.get("target") or "").strip()
            text = str(annotation.get("text") or "").strip()
            if not text:
                continue
            key = (path, target, text)
            if key in seen:
                continue
            seen.add(key)
            intents.append(
                {
                    "intent": text,
                    "rationale": target,
                    "supporting_files": [path],
                    "supporting_functions": [],
                    "confidence": "medium",
                    "caveats": [],
                }
            )
    return intents


def _annotation_innovation_claims(annotation_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in annotation_items:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        for annotation in item.get("annotations") or []:
            if annotation.get("kind") != "mark":
                continue
            mark_type = str(annotation.get("mark_type") or "").strip().lower()
            if mark_type != "innovation-hint":
                continue
            target = str(annotation.get("target") or "").strip()
            text = str(annotation.get("text") or "").strip()
            if not text:
                continue
            key = (path, target, text)
            if key in seen:
                continue
            seen.add(key)
            caveats = ["needs_hard_code_evidence"]
            if target:
                caveats.append(f"annotation_target:{target}")
            claims.append(
                {
                    "claim": text,
                    "supporting_files": [path],
                    "supporting_functions": [],
                    "confidence": "medium",
                    "caveats": caveats,
                }
            )
    return claims


def _annotation_deemphasize_details(annotation_items: list[dict[str, Any]]) -> list[str]:
    details: list[str] = []
    seen: set[str] = set()
    for item in annotation_items:
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        for annotation in item.get("annotations") or []:
            if annotation.get("kind") != "mark":
                continue
            mark_type = str(annotation.get("mark_type") or "").strip().lower()
            if mark_type != "deemphasize":
                continue
            target = str(annotation.get("target") or "").strip()
            text = str(annotation.get("text") or "").strip()
            if not text:
                continue
            combined = f"{text} [source: {path}]"
            if target:
                combined = f"{combined} [target: {target}]"
            if combined in seen:
                continue
            seen.add(combined)
            details.append(combined)
    return details


def _merge_nonempty(base: list[str], extra: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in base + extra:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _tokenize_hint(text: Any) -> set[str]:
    parts = re.findall(r"[A-Za-z0-9_+#.-]+", str(text or "").lower())
    return {part for part in parts if len(part) >= 3}


def _normalize_mainline(value: Any) -> str:
    if isinstance(value, list):
        parts = [str(item or "").strip() for item in value if str(item or "").strip()]
        return " -> ".join(parts)
    return str(value or "").strip()


def _run_code2flow_scan(
    *,
    project_root: Path,
    core_top_k: int,
    mechanism_keywords: list[str] | None = None,
) -> dict[str, Any]:
    src_root = Path(__file__).resolve().parents[2]
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    try:
        from code2flow.defaults import ScanConfig
        from code2flow.scanner import scan_repository
    except Exception:
        return {}

    cfg = ScanConfig(core_top_k=int(core_top_k))
    try:
        return scan_repository(
            project_root,
            cfg,
            mechanism_keywords=list(mechanism_keywords or []),
            annotation_priority="balanced",
        )
    except Exception:
        return {}


def _suggest_mechanism_keywords(template: dict[str, Any], limit: int = 24) -> list[str]:
    texts: list[str] = []
    texts.extend(_to_list_str(template.get("method_mainline")))
    texts.extend(_to_list_str(template.get("possible_distinguishing_points")))
    for block in _as_dict_list(template.get("key_building_blocks")):
        texts.append(str(block.get("name") or ""))
        texts.append(str(block.get("role") or ""))
    for step in _as_dict_list(template.get("pipeline_steps")):
        texts.append(str(step.get("name") or ""))
        texts.append(str(step.get("purpose") or ""))
        texts.extend(_to_list_str(step.get("related_components")))

    freq: dict[str, int] = {}
    stopwords = {
        "the", "and", "for", "with", "from", "into", "using", "based", "stage",
        "step", "method", "module", "model", "system", "data", "task", "paper",
    }
    for text in texts:
        for token in _tokenize_hint(text):
            if token in stopwords:
                continue
            freq[token] = freq.get(token, 0) + 1
    return [token for token, _ in sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:limit]]


def _build_scan_candidates(scan_report: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for item in scan_report.get("core_files") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if path:
            candidates.append({"path": path, "text": f"{path} {' '.join(_to_list_str(item.get('reasons')))}"})
    for item in scan_report.get("targeted_mechanism_evidence") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        topic = str(item.get("topic") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        candidates.append({"path": path, "text": f"{path} {topic} {snippet}"})
    for item in scan_report.get("annotated_snippets_selected") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        annotation = str(item.get("annotation") or "").strip()
        if path:
            candidates.append({"path": path, "text": f"{path} {annotation}"})
    dedup: dict[str, str] = {}
    for item in candidates:
        path = item["path"]
        dedup[path] = (dedup.get(path, "") + " " + item.get("text", "")).strip()
    return [{"path": path, "text": text} for path, text in dedup.items()]


def _best_paths_for_query(query: str, candidates: list[dict[str, str]], top_k: int = 3) -> list[str]:
    terms = _tokenize_hint(query)
    if not terms:
        return []
    scored: list[tuple[int, str]] = []
    for item in candidates:
        text_tokens = _tokenize_hint(item.get("text", ""))
        overlap = len(terms & text_tokens)
        if overlap > 0:
            scored.append((overlap, item["path"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    output: list[str] = []
    for _, path in scored:
        if path not in output:
            output.append(path)
        if len(output) >= top_k:
            break
    return output


def _candidate_paths(top_core: list[str], pipeline_steps: list[dict[str, Any]]) -> list[str]:
    candidates = list(top_core)
    for step in pipeline_steps:
        for path in step.get("related_files") or []:
            text = str(path or "").strip()
            if text and text not in candidates:
                candidates.append(text)
    return candidates


def _best_role_path(
    *,
    role: dict[str, Any],
    candidate_paths: list[str],
    pipeline_steps: list[dict[str, Any]],
) -> str:
    explicit = str(role.get("path") or "").strip()
    if explicit:
        return explicit
    symbol = str(role.get("symbol") or "").strip()
    role_text = str(role.get("role") or "").strip()
    notes = str(role.get("notes") or "").strip()
    hints = _tokenize_hint(symbol) | _tokenize_hint(role_text) | _tokenize_hint(notes)
    if not candidate_paths:
        return ""
    if symbol and _looks_like_repo_path(symbol):
        normalized_symbol = symbol.replace("\\", "/").lower()
        for path in candidate_paths:
            normalized_path = str(path).replace("\\", "/").lower()
            if normalized_path == normalized_symbol or normalized_path.endswith("/" + normalized_symbol):
                return path

    best_path = ""
    best_score = -1
    for path in candidate_paths:
        normalized_path = str(path).replace("\\", "/")
        path_tokens = _tokenize_hint(Path(normalized_path).stem) | _tokenize_hint(normalized_path)
        score = 0
        if symbol:
            symbol_lower = symbol.lower()
            stem_lower = Path(normalized_path).stem.lower()
            if symbol_lower == normalized_path.lower():
                score += 120
            if symbol_lower == stem_lower:
                score += 110
            if symbol_lower in normalized_path.lower():
                score += 60
        overlap = hints & path_tokens
        score += len(overlap) * 14
        for step in pipeline_steps:
            related = {str(item or "").strip() for item in step.get("related_files") or []}
            if path not in related:
                continue
            step_tokens = _tokenize_hint(step.get("name")) | _tokenize_hint(step.get("purpose"))
            score += len(hints & step_tokens) * 10
        lower_path = normalized_path.lower()
        if "trainer" in hints and any(token in lower_path for token in ("train", "trainer", "runner", "engine", "main")):
            score += 22
        if "aligner" in hints and any(token in lower_path for token in ("align", "project", "adapter", "proj")):
            score += 18
        if "token" in hints and any(token in lower_path for token in ("token", "mask", "patch", "encoder", "decoder")):
            score += 16
        if "composition" in hints and any(token in lower_path for token in ("compose", "fusion", "transformer", "layer", "model")):
            score += 14
        if "fusion" in hints and any(token in lower_path for token in ("fusion", "merge", "aggregate", "logit")):
            score += 15
        if score > best_score:
            best_score = score
            best_path = path
    return best_path


def _default_story_order(steps: list[dict[str, Any]]) -> list[str]:
    return [str(step.get("name") or "").strip() for step in steps if str(step.get("name") or "").strip()]


def _fallback_role_path(idx: int) -> str:
    return f"__auto_generated__/module_{idx + 1}.py"


def _path_stem_label(path: str) -> str:
    stem = Path(str(path or "")).stem.replace("_", " ").replace("-", " ").strip()
    return stem or "core component"


def _default_module_roles_from_core(top_core: list[str]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for path in top_core[:8]:
        roles.append(
            {
                "path": path,
                "symbol": "",
                "role": f"{_path_stem_label(path)} implementation anchor",
                "importance": "core",
                "is_novel": False,
                "notes": "auto-generated-from-core-scan",
            }
        )
    return roles


def _default_pipeline_steps_from_core(top_core: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, path in enumerate(top_core[:6], start=1):
        label = _path_stem_label(path).title()
        steps.append(
            {
                "name": f"Core Step {index}: {label}",
                "purpose": f"Implementation step grounded in core file {path}.",
                "input": [],
                "output": [],
                "related_files": [path],
                "highlight_level": "main",
                "omit_from_main_figure": False,
            }
        )
    return steps


def _build_code2flow_driven_markers(
    *,
    template_payload: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    tpl = dict(template_payload or {})
    mechanism_keywords = _suggest_mechanism_keywords(tpl)
    scan_report = _run_code2flow_scan(
        project_root=project_root,
        core_top_k=max(12, len(_to_list_str(tpl.get("priority_files"))) or 12),
        mechanism_keywords=mechanism_keywords,
    )
    scan_candidates = _build_scan_candidates(scan_report)
    top_core = [str(item.get("path") or "").strip() for item in (scan_report.get("core_files") or []) if isinstance(item, dict) and str(item.get("path") or "").strip()]

    project_goal = str(tpl.get("project_goal") or "").strip() or f"Implementation-grounded method extraction for {project_root.name}"
    paper_method_goal = str(tpl.get("paper_method_goal") or "").strip() or project_goal
    method_mainline = _normalize_mainline(tpl.get("method_mainline"))
    paper_story_order = _to_list_str(tpl.get("paper_story_order"))
    deemphasize_details = _to_list_str(tpl.get("deemphasize_details"))

    module_roles = _module_roles_from_template(tpl)
    if not module_roles:
        module_roles = _default_module_roles_from_core(top_core)
    for idx, role in enumerate(module_roles):
        if str(role.get("path") or "").strip():
            continue
        role_name = str(role.get("role") or "").strip()
        symbol = str(role.get("symbol") or "").strip()
        notes = str(role.get("notes") or "").strip()
        query = " ".join(part for part in [symbol, role_name, notes] if part).strip()
        matched = _best_paths_for_query(query, scan_candidates, top_k=1)
        if matched:
            role["path"] = matched[0]
        elif idx < len(top_core):
            role["path"] = top_core[idx]
        elif top_core:
            role["path"] = top_core[0]
        else:
            role["path"] = _fallback_role_path(idx)

    pipeline_steps = _pipeline_steps_from_template(tpl)
    if not pipeline_steps:
        pipeline_steps = _default_pipeline_steps_from_core(top_core)
    for idx, step in enumerate(pipeline_steps):
        related_files = _to_list_str(step.get("related_files"))
        if related_files:
            continue
        query = " ".join(
            [
                str(step.get("name") or ""),
                str(step.get("purpose") or ""),
                " ".join(_to_list_str(step.get("input"))),
                " ".join(_to_list_str(step.get("output"))),
            ]
        ).strip()
        matched = _best_paths_for_query(query, scan_candidates, top_k=4)
        if matched:
            step["related_files"] = matched
        elif idx < len(top_core):
            step["related_files"] = [top_core[idx]]
        elif top_core:
            step["related_files"] = [top_core[0]]

    design_intents = _design_intents_from_template(tpl)
    innovation_claims = _innovation_claims_from_template(tpl)

    priority_files = _merge_nonempty(top_core, _to_list_str(tpl.get("priority_files")))[:32]
    ignore_files = _to_list_str(tpl.get("ignore_files"))
    if not paper_story_order:
        paper_story_order = _default_story_order(pipeline_steps)
    if not method_mainline:
        method_mainline = " -> ".join(paper_story_order[:6]) if paper_story_order else "implementation-grounded method flow"

    return {
        "project_goal": project_goal,
        "paper_method_goal": paper_method_goal,
        "implementation_scope": (
            f"Use executable evidence under {project_root}; "
            "this marker file is generated from draft/template intent and code2flow scan hints."
        ),
        "method_mainline": method_mainline,
        "paper_story_order": paper_story_order,
        "deemphasize_details": deemphasize_details,
        "latex_expression_preference": _enum_latex_preference(tpl.get("latex_expression_preference")),
        "priority_files": priority_files,
        "ignore_files": ignore_files,
        "module_roles": module_roles,
        "pipeline_steps": pipeline_steps,
        "design_intents": design_intents,
        "innovation_claims": innovation_claims,
        "potential_mismatches": [],
    }


def build_generated_author_markers(
    *,
    template_payload: dict[str, Any],
    annotation_report: dict[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    tpl = dict(template_payload or {})
    _ = annotation_report
    if tpl:
        generated = _build_code2flow_driven_markers(
            template_payload=tpl,
            project_root=project_root,
        )
        if generated.get("module_roles") or generated.get("pipeline_steps") or generated.get("priority_files"):
            return generated

    project_goal = str(tpl.get("project_goal") or "").strip() or f"Implementation-grounded method extraction for {project_root.name}"
    paper_method_goal = str(tpl.get("paper_method_goal") or "").strip() or project_goal

    mainline_list = _to_list_str(tpl.get("method_mainline"))
    method_mainline = " -> ".join(mainline_list) if mainline_list else str(tpl.get("method_mainline") or "").strip()
    paper_story_order = _to_list_str(tpl.get("paper_story_order"))

    module_roles = _module_roles_from_template(tpl)
    pipeline_steps = _pipeline_steps_from_template(tpl)
    design_intents = _design_intents_from_template(tpl)
    innovation_claims = _innovation_claims_from_template(tpl)

    scan_report = _run_code2flow_scan(
        project_root=project_root,
        core_top_k=max(12, len(_to_list_str(tpl.get("priority_files"))) or 12),
        mechanism_keywords=_suggest_mechanism_keywords(tpl),
    )
    top_core = [
        str(item.get("path") or "").strip()
        for item in (scan_report.get("core_files") or [])
        if isinstance(item, dict) and str(item.get("path") or "").strip()
    ]
    candidate_paths = _candidate_paths(top_core, pipeline_steps)

    if not module_roles:
        module_roles = _default_module_roles_from_core(top_core)
    if not pipeline_steps:
        pipeline_steps = _default_pipeline_steps_from_core(top_core)

    # Bind template module blocks to likely code paths using template hints and pipeline files.
    for idx, role in enumerate(module_roles):
        if role.get("path"):
            continue
        matched = _best_role_path(
            role=role,
            candidate_paths=candidate_paths,
            pipeline_steps=pipeline_steps,
        )
        if matched:
            role["path"] = matched
        elif top_core:
            role["path"] = top_core[min(idx, len(top_core) - 1)]
        else:
            role["path"] = _fallback_role_path(idx)

    # Fill pipeline related files with core files if absent.
    for idx, step in enumerate(pipeline_steps):
        rel = step.get("related_files") or []
        if rel:
            continue
        if idx < len(top_core):
            step["related_files"] = [top_core[idx]]
            step["_auto_related_files"] = True
        elif top_core:
            step["related_files"] = [top_core[0]]
            step["_auto_related_files"] = True

    for step in pipeline_steps:
        level = str(step.get("highlight_level") or "main").strip().lower()
        step["highlight_level"] = level if level in {"main", "secondary", "omit"} else "main"
        step["omit_from_main_figure"] = _as_bool(step.get("omit_from_main_figure"), default=False)
    previous_output = "input representation"
    for index, step in enumerate(pipeline_steps):
        if not _to_list_str(step.get("input")):
            step["input"] = [previous_output if index > 0 else "raw or prepared input representation"]
        if not _to_list_str(step.get("output")):
            step["output"] = ["method output or training signal" if index == len(pipeline_steps) - 1 else "intermediate method representation"]
        previous = _to_list_str(step.get("output"))
        if previous:
            previous_output = previous[-1]
    for step in pipeline_steps:
        step.pop("_auto_related_files", None)

    if not paper_story_order:
        paper_story_order = _default_story_order(pipeline_steps)

    if not method_mainline:
        method_mainline = " -> ".join(paper_story_order[:6]) if paper_story_order else "implementation-grounded method flow"

    scope_constraints = tpl.get("scope_constraints")
    scope_lines: list[str] = []
    if isinstance(scope_constraints, dict):
        for key, val in scope_constraints.items():
            if _as_bool(val, default=False):
                scope_lines.append(str(key))
    scope_lines = _merge_nonempty(scope_lines, ["current_codebase_only"])
    implementation_scope = "; ".join(scope_lines) if scope_lines else "current codebase only"

    deemphasize = _to_list_str(tpl.get("deemphasize_details"))

    generated = {
        "project_goal": project_goal,
        "paper_method_goal": paper_method_goal,
        "implementation_scope": implementation_scope,
        "method_mainline": method_mainline,
        "paper_story_order": paper_story_order,
        "deemphasize_details": deemphasize,
        "latex_expression_preference": _enum_latex_preference(tpl.get("latex_expression_preference")),
        "priority_files": top_core,
        "ignore_files": [],
        "module_roles": module_roles,
        "pipeline_steps": pipeline_steps,
        "design_intents": design_intents,
        "innovation_claims": innovation_claims,
        "potential_mismatches": [],
    }
    return generated


def save_generated_author_markers(
    *,
    generated_markers: dict[str, Any],
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "author_markers.generated.yaml"
    out_path.write_text(
        yaml.safe_dump(generated_markers, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (out_dir / "author_markers.generated.json").write_text(
        json.dumps(generated_markers, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out_path


def load_template_payload(path: Path) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"template file not found: {resolved}")
    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"template YAML must contain a non-empty mapping: {resolved}")
    return payload
