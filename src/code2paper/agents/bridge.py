"""Converters from embedded code-agent artifacts to code2paper schemas."""

from __future__ import annotations

import fnmatch
import hashlib
import re
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
    evidence_repair_focus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path_to_ids = _build_path_to_evidence_ids(raw_pack)
    all_evidence_ids: list[str] = list(dict.fromkeys(eid for ids in path_to_ids.values() for eid in ids))
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
    author_steps_by_name = {
        " ".join(str(step.name or "").lower().replace("_", " ").split()): step
        for step in author_markers.pipeline_steps
        if str(step.name or "").strip()
    }
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
        # A directed rescan may replace snippet ids after code_facts were
        # produced. Rebind author-named stages to their explicitly scoped files
        # before any fallback, preventing unrelated evidence from being chosen.
        normalized_name = " ".join(str(step.get("name") or "").lower().replace("_", " ").split())
        author_step = author_steps_by_name.get(normalized_name)
        if author_step is not None:
            scoped_ids = [
                evidence_id
                for path in author_step.related_files
                for evidence_id in _lookup_evidence_ids(path_to_ids, path)
            ]
            support_ids = [*scoped_ids, *support_ids]
        # Evidence repair is claim-driven and may discover a better code span
        # without changing the analyzer's stale snippet ids. Rebind a repaired
        # claim to the matching mechanism by claim text, not by the ephemeral
        # C<number> assigned by a particular evidence freeze.
        repair_ids = _repair_evidence_ids_for_mechanism(
            mechanism_text=" ".join(
                str(value or "")
                for value in (step.get("name"), step.get("description"))
            ),
            evidence_repair_focus=evidence_repair_focus,
            path_to_ids=path_to_ids,
        )
        support_ids = [*repair_ids, *support_ids]
        # A bounded rescan can add the right implementation after the embedded
        # analyzer has already emitted stale snippet references.  Prefer spans
        # whose *code content* matches the mechanism over those stale refs.  A
        # multi-concept threshold keeps a merely recommended path from becoming
        # positive evidence on its own.
        content_ids = _content_evidence_ids_for_mechanism(
            mechanism_text=" ".join(
                str(value or "")
                for value in (step.get("name"), step.get("description"))
            ),
            core_snippets=core_snippets,
            snippet_to_evidence=snippet_to_evidence,
        )
        if content_ids:
            support_ids = content_ids
        support_ids = list(dict.fromkeys(support_ids))
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


def _repair_evidence_ids_for_mechanism(
    *,
    mechanism_text: str,
    evidence_repair_focus: dict[str, Any] | None,
    path_to_ids: dict[str, list[str]],
) -> list[str]:
    if not evidence_repair_focus or not path_to_ids:
        return []
    mechanism_tokens = _repair_match_tokens(mechanism_text)
    if not mechanism_tokens:
        return []
    evidence_ids: list[str] = []
    for target in evidence_repair_focus.get("claim_targets", []):
        if not isinstance(target, dict):
            continue
        query_tokens = _repair_match_tokens(str(target.get("claim_query") or ""))
        overlap = mechanism_tokens & query_tokens
        if len(overlap) < 2 or len(overlap) / max(1, min(len(mechanism_tokens), len(query_tokens))) < 0.35:
            continue
        for candidate in target.get("candidates", []):
            if isinstance(candidate, dict):
                evidence_ids.extend(
                    _lookup_evidence_ids(path_to_ids, str(candidate.get("path") or ""))
                )
    return list(dict.fromkeys(evidence_ids))


def _repair_match_tokens(text: str) -> set[str]:
    stop = {
        "claim", "compute", "computation", "method", "stage", "using",
        "from", "into", "with", "this", "that", "then", "only",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", str(text or "").lower())
        if len(token) >= 3 and token not in stop and not re.fullmatch(r"c\d+", token)
    }


_MECHANISM_CONCEPT_ALIASES: dict[str, set[str]] = {
    "aggregate": {"aggregate", "aggregated", "aggregation", "average", "averaged", "sum", "stack"},
    "bounded": {"few", "fewshot", "small"},
    "data": {"data", "dataset", "demonstration", "demonstrations", "example", "sample", "samples", "sampling"},
    "domain": {"domain", "domains", "mixed", "multi"},
    "expert": {"expert", "experts", "idx", "idxs", "indices"},
    "gating": {"gate", "gating", "router", "routing"},
    "moe": {"moe", "mixture", "rmoe", "smoe", "fullmoe"},
    "norm": {"l2", "norm", "normalization", "normalize", "normalized", "norms", "magnitude"},
    "output": {"out", "output", "outputs", "expert_out"},
    "product": {"multiply", "multiplied", "product"},
    "representation": {"hidden", "representation", "state", "states", "x_before", "x_before_moe", "x_after", "x_after_moe"},
    "score": {"importance", "score", "scores", "weight", "weights"},
    "select": {"keep", "mask", "prune", "pruned", "pruning", "retain", "retained", "scatter", "select", "selection", "target_number", "top", "topk"},
    "similarity": {"cos", "cosine", "similarity", "simibr"},
}


def _content_evidence_ids_for_mechanism(
    *,
    mechanism_text: str,
    core_snippets: dict[str, Any],
    snippet_to_evidence: dict[str, str],
) -> list[str]:
    mechanism_concepts = _mechanism_concepts(mechanism_text)
    if len(mechanism_concepts) < 2:
        return []
    ranked: list[tuple[float, int, bool, str, str]] = []
    snippets = core_snippets.get("snippets", []) if isinstance(core_snippets.get("snippets"), list) else []
    mechanism_tokens = _code_match_tokens(mechanism_text)
    for snippet in snippets:
        if not isinstance(snippet, dict):
            continue
        snippet_id = str(snippet.get("snippet_id") or "").strip()
        evidence_id = snippet_to_evidence.get(snippet_id)
        if not evidence_id:
            continue
        source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
        searchable = " ".join(
            str(value or "")
            for value in (
                source.get("path"), source.get("symbol"), snippet.get("text"),
                snippet.get("content"), snippet.get("code"), snippet.get("summary"),
            )
        )
        snippet_concepts = _mechanism_concepts(searchable)
        if "product" in mechanism_concepts and "*" in searchable:
            snippet_concepts.add("product")
        if "norm" in mechanism_concepts and re.search(
            r"\bscore\s*=\s*score\s*/\s*(?:torch\.)?sum\s*\(", searchable, flags=re.IGNORECASE
        ):
            snippet_concepts.add("norm")
        bounded_data_slice = bool(re.search(
            r"\b(?:data|samples?)\s*\[[^\]\n]*:\s*\d+\s*\]", searchable,
            flags=re.IGNORECASE,
        ))
        if "bounded" in mechanism_concepts and bounded_data_slice:
            snippet_concepts.add("bounded")
        if {"bounded", "data"}.issubset(mechanism_concepts) and not bounded_data_slice:
            continue
        required_signatures = mechanism_concepts & {
            "aggregate", "bounded", "data", "norm", "select", "similarity"
        }
        if required_signatures - snippet_concepts:
            continue
        if {"gating", "norm", "output", "expert"}.issubset(mechanism_concepts):
            compact = searchable.lower().replace(" ", "")
            if "norm(expert_out" not in compact and "norm(expertoutput" not in compact:
                continue
        shared = mechanism_concepts & snippet_concepts
        coverage = len(shared) / len(mechanism_concepts)
        if len(shared) < 2 or (coverage < 0.5 and len(shared) < 3):
            continue
        direct_overlap = len(mechanism_tokens & _code_match_tokens(searchable))
        path_overlap = len(mechanism_tokens & _code_match_tokens(str(source.get("path") or "")))
        path_concept_overlap = len(
            mechanism_concepts & _mechanism_concepts(str(source.get("path") or ""))
        )
        line_count = max(1, searchable.count("\n") + 1)
        breadth_penalty = min(2.0, max(0, line_count - 120) / 200.0)
        is_directed_rescan = snippet.get("role") == "agentic_rescan_symbol_index"
        role_bonus = 0.25 if is_directed_rescan else 0.0
        score = (
            len(shared) * 2.0 + coverage + min(direct_overlap, 6) * 0.1
            + min(path_overlap, 3) * 0.5 + min(path_concept_overlap, 3) * 0.5
            + role_bonus - breadth_penalty
        )
        ranked.append((score, len(shared), is_directed_rescan, str(source.get("path") or ""), evidence_id))
    if not ranked:
        return []
    # Once a directed rescan produces a content-matching span, compare within
    # that bounded result set.  Earlier generic snippets can contain vocabulary
    # such as "expert" or "weight" without implementing the requested method.
    if any(item[2] for item in ranked):
        ranked = [item for item in ranked if item[2]]
    ranked.sort(key=lambda item: (-item[0], -item[1], item[3], item[4]))
    best_score = ranked[0][0]
    return list(dict.fromkeys(item[4] for item in ranked if item[0] >= best_score - 0.5))[:4]


def _mechanism_concepts(text: str) -> set[str]:
    tokens = _code_match_tokens(text)
    return {
        concept
        for concept, aliases in _MECHANISM_CONCEPT_ALIASES.items()
        if tokens & aliases
    }


def _code_match_tokens(text: str) -> set[str]:
    expanded = re.sub(r"\bMoE\b", "moe", str(text or ""), flags=re.IGNORECASE)
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", expanded)
    compound_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+(?:_[a-z0-9]+)+", expanded.lower())
        if len(token) >= 2
    }
    split_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", expanded.replace("_", " ").lower())
        if len(token) >= 2
    }
    return compound_tokens | split_tokens


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []
