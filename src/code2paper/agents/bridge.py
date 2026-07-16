"""Converters from embedded code-agent artifacts to code2paper schemas."""

from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path
from typing import Any

from code2paper.schemas import (
    AuthorMode,
    EvidenceItem,
    ExcludedSource,
    RawEvidencePack,
    ReadmePolicy,
    SourceType,
)

DEFAULT_BRIDGE_EXCLUDE_GLOBS = {
    ".codeboarding/**",
    "swark-output/**",
    "pretrained_weight/**",
    "media/**",
    "README*",
    "*.safetensors",
    "*.bin",
    "*.pt",
    "*.pth",
    "*.ckpt",
}


def _norm_path(path: str) -> str:
    return str(Path(path)).replace("\\", "/")


def _relative_repo_path(path: str, repo: Path) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    candidate = Path(raw)
    try:
        if candidate.is_absolute():
            return candidate.resolve().relative_to(repo).as_posix()
    except ValueError:
        pass
    normalized = _norm_path(raw)
    repo_text = _norm_path(str(repo))
    if normalized.startswith(repo_text + "/"):
        return normalized[len(repo_text) + 1 :]
    return normalized


def _bridge_exclude_globs(author_markers: Any) -> set[str]:
    patterns = set(DEFAULT_BRIDGE_EXCLUDE_GLOBS)
    patterns.update(str(item) for item in getattr(author_markers, "ignore_files", []) if str(item).strip())
    return patterns


def _is_bridge_excluded_path(path: str, *, repo: Path, exclude_globs: set[str]) -> bool:
    rel = _relative_repo_path(path, repo)
    if not rel:
        return False
    name = Path(rel).name
    return name in exclude_globs or any(fnmatch.fnmatch(rel, pattern) for pattern in exclude_globs)


def _filter_postergen_outputs(
    *,
    repo: Path,
    author_markers: Any,
    code_sources: dict[str, Any],
    core_snippets: dict[str, Any],
    code_facts: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], set[str]]:
    exclude_globs = _bridge_exclude_globs(author_markers)
    removed_snippet_ids: set[str] = set()

    filtered_sources = dict(code_sources)
    project_files = filtered_sources.get("project_files")
    if isinstance(project_files, list):
        filtered_sources["project_files"] = [
            item
            for item in project_files
            if not _is_bridge_excluded_path(str(item.get("path") if isinstance(item, dict) else item), repo=repo, exclude_globs=exclude_globs)
        ]

    filtered_snippets = dict(core_snippets)
    snippets: list[Any] = []
    for snippet in core_snippets.get("snippets", []) if isinstance(core_snippets.get("snippets"), list) else []:
        if not isinstance(snippet, dict):
            continue
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        path = str(source.get("path") or snippet.get("path") or "")
        snippet_id = str(snippet.get("snippet_id") or "")
        if _is_bridge_excluded_path(path, repo=repo, exclude_globs=exclude_globs):
            if snippet_id:
                removed_snippet_ids.add(snippet_id)
            continue
        snippets.append(snippet)
    filtered_snippets["snippets"] = snippets

    def _filter_refs(value: object) -> list[str]:
        refs = [str(ref) for ref in value] if isinstance(value, list) else []
        return [ref for ref in refs if ref not in removed_snippet_ids]

    filtered_facts = dict(code_facts)
    modules: list[dict[str, Any]] = []
    for module in code_facts.get("modules", []) if isinstance(code_facts.get("modules"), list) else []:
        if not isinstance(module, dict):
            continue
        refs = _filter_refs(module.get("evidence_refs"))
        if module.get("evidence_refs") and not refs:
            continue
        updated = dict(module)
        updated["evidence_refs"] = refs
        modules.append(updated)
    filtered_facts["modules"] = modules

    steps: list[dict[str, Any]] = []
    for step in code_facts.get("pipeline_steps", []) if isinstance(code_facts.get("pipeline_steps"), list) else []:
        if not isinstance(step, dict):
            continue
        updated = dict(step)
        updated["evidence_refs"] = _filter_refs(step.get("evidence_refs"))
        steps.append(updated)
    filtered_facts["pipeline_steps"] = steps
    return filtered_sources, filtered_snippets, filtered_facts, removed_snippet_ids


def _filter_raw_pack(raw_pack: RawEvidencePack, *, repo: Path, author_markers: Any) -> RawEvidencePack:
    exclude_globs = _bridge_exclude_globs(author_markers)
    filtered = [
        item
        for item in raw_pack.evidence_items
        if not _is_bridge_excluded_path(item.path, repo=repo, exclude_globs=exclude_globs)
    ]
    return raw_pack.model_copy(update={"evidence_items": filtered})


def _infer_source_type(path: str) -> SourceType:
    lowered = str(path or "").lower()
    if lowered.endswith(".sh"):
        return SourceType.BASH
    if lowered.endswith((".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", "makefile")):
        return SourceType.CONFIG
    return SourceType.SOURCE


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _snippet_line_span(snippet: dict[str, Any]) -> tuple[int | None, int | None]:
    source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
    start = (
        _to_int(source.get("start_line"))
        or _to_int(source.get("line_start"))
        or _to_int(snippet.get("start_line"))
        or _to_int(snippet.get("line_start"))
    )
    end = (
        _to_int(source.get("end_line"))
        or _to_int(source.get("line_end"))
        or _to_int(snippet.get("end_line"))
        or _to_int(snippet.get("line_end"))
    )
    if start is None and end is not None:
        start = end
    if end is None and start is not None:
        end = start
    if start is not None and end is not None and end < start:
        end = start
    return start, end


def _snippet_summary(snippet: dict[str, Any], path: str, snippet_id: str) -> str:
    summary_fields = (
        snippet.get("summary"),
        snippet.get("reason"),
        snippet.get("rationale"),
        snippet.get("role"),
    )
    for candidate in summary_fields:
        text = str(candidate or "").strip()
        if text:
            return text
    return f"Story-first code-agent snippet {snippet_id} from {path}."


def _snippet_hash(snippet: dict[str, Any]) -> str:
    parts = []
    for key in ("content", "code", "snippet", "text"):
        value = snippet.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
    for key in ("path", "symbol", "start_line", "end_line"):
        value = source.get(key)
        if value is not None:
            parts.append(str(value))
    payload = "\n".join(parts).strip()
    if not payload:
        return ""
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_raw_pack_from_snippets(
    *,
    repo: Path,
    author_markers: Any,
    core_snippets: dict[str, Any],
    project_id: str,
) -> tuple[RawEvidencePack, dict[str, str]]:
    snippets = core_snippets.get("snippets", []) if isinstance(core_snippets.get("snippets"), list) else []
    evidence_items: list[EvidenceItem] = []
    snippet_to_evidence: dict[str, str] = {}
    excluded_sources: list[ExcludedSource] = []
    exclude_globs = _bridge_exclude_globs(author_markers)

    next_id = 1
    for index, snippet in enumerate(snippets, start=1):
        if not isinstance(snippet, dict):
            continue
        snippet_id = str(snippet.get("snippet_id") or f"SNP{index}")
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        path = str(source.get("path") or snippet.get("path") or "").strip()
        if not path:
            continue
        rel_path = _relative_repo_path(path, repo)
        if not rel_path:
            continue
        if _is_bridge_excluded_path(rel_path, repo=repo, exclude_globs=exclude_globs):
            excluded_sources.append(
                ExcludedSource(path=rel_path, reason="excluded by bridge ignore policy")
            )
            continue
        evidence_id = f"E{next_id}"
        next_id += 1
        start_line, end_line = _snippet_line_span(snippet)
        symbol = str(source.get("symbol") or snippet.get("symbol") or "").strip() or None
        confidence = snippet.get("confidence")
        try:
            parsed_confidence = float(confidence) if confidence is not None else 0.85
        except (TypeError, ValueError):
            parsed_confidence = 0.85
        parsed_confidence = max(0.0, min(1.0, parsed_confidence))
        source_type = _infer_source_type(rel_path)
        role = str(snippet.get("role") or "")
        tags = (
            ["agentic_rescan", "symbol_index", f"snippet_id:{snippet_id}"]
            if role == "agentic_rescan_symbol_index"
            else ["postergen_bridge", "snippet", f"snippet_id:{snippet_id}"]
        )
        item = EvidenceItem(
            evidence_id=evidence_id,
            source_type=source_type,
            path=rel_path,
            symbol=symbol,
            line_start=start_line,
            line_end=end_line,
            content_summary=_snippet_summary(snippet, rel_path, snippet_id),
            tags=tags,
            confidence=parsed_confidence,
            excerpt_hash=_snippet_hash(snippet),
            config_key=symbol if getattr(source_type, "value", str(source_type)) == "config" else None,
            shell_command_segment=symbol if getattr(source_type, "value", str(source_type)) == "bash" else None,
        )
        evidence_items.append(item)
        snippet_to_evidence[snippet_id] = evidence_id

    raw_pack = RawEvidencePack(
        project_id=project_id,
        project_root=str(repo),
        author_mode=AuthorMode.ENHANCED,
        author_confirmation_required=False,
        readme_policy=ReadmePolicy.EXCLUDE,
        evidence_items=evidence_items,
        excluded_sources=excluded_sources,
    )
    return raw_pack, snippet_to_evidence


def _build_path_to_evidence_ids(raw_pack: RawEvidencePack | None) -> dict[str, list[str]]:
    if raw_pack is None:
        return {}
    mapping: dict[str, list[str]] = {}
    for item in raw_pack.evidence_items:
        key = _norm_path(item.path)
        mapping.setdefault(key, []).append(item.evidence_id)
    return mapping


def _lookup_evidence_ids(path_to_ids: dict[str, list[str]], path: str) -> list[str]:
    if not path_to_ids:
        return []
    target = _norm_path(path)
    if target in path_to_ids:
        return path_to_ids[target]
    hits: list[str] = []
    for key, values in path_to_ids.items():
        if target.endswith(key) or key.endswith(target):
            hits.extend(values)
    seen: set[str] = set()
    deduped: list[str] = []
    for value in hits:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _build_code_method_analysis_payload(
    *,
    code_facts: dict[str, Any],
    core_snippets: dict[str, Any],
    author_markers: Any,
    snippet_to_evidence: dict[str, str],
    raw_pack: RawEvidencePack | None,
) -> dict[str, Any]:
    path_to_ids = _build_path_to_evidence_ids(raw_pack)
    all_evidence_ids: list[str] = list({eid for ids in path_to_ids.values() for eid in ids})
    fallback_evidence = all_evidence_ids[:1]

    snippet_by_id: dict[str, dict[str, Any]] = {
        str(sn.get("snippet_id")): sn for sn in core_snippets.get("snippets", []) if isinstance(sn, dict)
    }

    navigation_questions: list[dict[str, Any]] = []
    for idx, step in enumerate(author_markers.pipeline_steps, start=1):
        targets = list(step.related_files or [])
        navigation_questions.append(
            {
                "question_id": f"Q{idx}",
                "question": f"What implementation evidence supports stage '{step.name}'?",
                "driven_by": ["author", "bridge"],
                "seed_span_ids": [],
                "target_paths_or_symbols": targets,
                "priority": "high" if step.highlight_level.value == "main" else "medium",
            }
        )

    execution_flows: list[dict[str, Any]] = [
        {
            "flow_id": "FLOW-story-first-code-agents",
            "purpose": str(
                getattr(author_markers, "paper_method_goal", "")
                or getattr(author_markers, "project_goal", "")
                or "Execution flow from PosterGen CodeAnalyzer output pipeline steps."
            ),
            "ordered_steps": [
                str(step.get("name") or "") for step in code_facts.get("pipeline_steps", []) if str(step.get("name") or "").strip()
            ],
            "entrypoint_span_ids": [],
            "config_resolution_span_ids": [],
        }
    ]

    method_modules: list[dict[str, Any]] = []
    for module in code_facts.get("modules", [])[:200]:
        if not isinstance(module, dict):
            continue
        refs = module.get("evidence_refs") if isinstance(module.get("evidence_refs"), list) else []
        module_paths: list[str] = []
        module_evidence_ids: list[str] = []
        for ref in refs:
            evidence_id = snippet_to_evidence.get(str(ref))
            if evidence_id:
                module_evidence_ids.append(evidence_id)
            snippet = snippet_by_id.get(str(ref))
            if not snippet:
                continue
            source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
            path = str(source.get("path") or "")
            if path:
                module_paths.append(path)
                module_evidence_ids.extend(_lookup_evidence_ids(path_to_ids, path))
        if not module_evidence_ids:
            module_evidence_ids = list(fallback_evidence)
        if not module_paths:
            module_paths = [""]
        symbol_candidates = module.get("methods") if isinstance(module.get("methods"), list) else []
        method_modules.append(
            {
                "path": module_paths[0] or "unknown.py",
                "symbols": [str(symbol) for symbol in symbol_candidates[:6]],
                "module_class": "method-core",
                "paper_role": str(module.get("role") or module.get("name") or "implementation module"),
                "evidence_span_ids": module_evidence_ids[:20],
                "llm_confidence": "medium",
            }
        )

    candidate_mechanisms: list[dict[str, Any]] = []
    mech_index = 1
    for step in code_facts.get("pipeline_steps", [])[:120]:
        if not isinstance(step, dict):
            continue
        refs = step.get("evidence_refs") if isinstance(step.get("evidence_refs"), list) else []
        support_ids: list[str] = []
        for ref in refs:
            evidence_id = snippet_to_evidence.get(str(ref))
            if evidence_id:
                support_ids.append(evidence_id)
            snippet = snippet_by_id.get(str(ref))
            if not snippet:
                continue
            source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
            path = str(source.get("path") or "")
            support_ids.extend(_lookup_evidence_ids(path_to_ids, path))
        if not support_ids:
            support_ids = list(fallback_evidence)
        if not support_ids:
            continue
        name = str(step.get("name") or f"pipeline_step_{mech_index}")
        candidate_mechanisms.append(
            {
                "mechanism_id": f"MECH{mech_index}",
                "name": name,
                "description": str(step.get("description") or f"Implementation mechanism for {name}."),
                "inputs": _string_list(step.get("input_data") or ["input"]),
                "outputs": _string_list(step.get("output_data") or ["output"]),
                "supporting_span_ids": support_ids[:20],
                "unsupported_parts": [],
            }
        )
        mech_index += 1

    evidence_spans: list[dict[str, Any]] = []
    if raw_pack is not None:
        for item in raw_pack.evidence_items[:400]:
            evidence_spans.append(
                {
                    "evidence_id": item.evidence_id,
                    "source_type": item.source_type.value,
                    "path": item.path,
                    "symbol": item.symbol,
                    "line_start": item.line_start,
                    "line_end": item.line_end,
                    "config_key": item.config_key,
                    "shell_command_segment": item.shell_command_segment,
                    "excerpt_hash": item.excerpt_hash,
                    "evidence_strength": item.evidence_strength.value if item.evidence_strength else None,
                    "confidence": item.confidence,
                }
            )

    return {
        "navigation_questions": navigation_questions,
        "execution_flows": execution_flows,
        "method_modules": method_modules,
        "candidate_mechanisms": candidate_mechanisms,
        "comment_driven_insights": [],
        "author_alignment": {
            "author_proposed_flow": [str(name) for name in author_markers.paper_story_order],
            "author_supported_flow": [
                str(step.get("name") or "") for step in code_facts.get("pipeline_steps", []) if str(step.get("name") or "").strip()
            ],
            "author_unsupported_parts": [],
        },
        "candidate_distinguishing_mechanisms": [str(claim.claim) for claim in author_markers.innovation_claims[:30]],
        "evidence_spans": evidence_spans,
        "gaps": [],
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
