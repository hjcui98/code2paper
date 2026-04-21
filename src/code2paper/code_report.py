"""Author-marker driven code intake and analysis reports.

This module adapts the PosterGen Code Intake / Code Analyzer design for the
code2paper pipeline.  The important difference is that method structure comes
from ``author_markers.yaml`` rather than parsed method prose, and every useful
snippet is mapped back to Phase 1 evidence span IDs so Phase 3 can freeze a
writing-ready Method Evidence IR.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code2paper.schemas import (
    AnalysisNavigationPlan,
    AuthorMarkers,
    CodeMethodAnalysis,
    CodeMethodExecutionFlow,
    CodeMethodModule,
    CandidateMechanism,
    ConfidenceLevel,
    ConflictStatus,
    EvidenceItem,
    EvidenceSpan,
    ModuleCategory,
    NavigationQuestion,
    NavigationWeight,
    Phase2AuthorAlignment,
    RawEvidencePack,
    SourceType,
    SupportStatus,
)

SOURCE_EXTS = {".py", ".sh", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "build",
    "dist",
    "output",
}
DEFAULT_IGNORE_GLOBS = {
    "README.md",
    "README*",
    "media/*",
    "media/**",
    "pretrained_weight/**",
    "swark-output/**",
    ".codeboarding/**",
    "*.pt",
    "*.pth",
    "*.ckpt",
    "*.bin",
    "*.safetensors",
}
BASE_ROLES = {
    "forward",
    "model_arch",
    "loss",
    "augmentation",
    "dataset",
    "training_loop",
    "config",
    "inference",
    "evaluation",
    "other",
}


@dataclass(frozen=True)
class _ScanBudget:
    max_total_files: int = 180
    max_total_bytes: int = 24 * 1024 * 1024
    max_single_file_bytes: int = 768 * 1024
    max_total_snippet_lines: int = 4200
    max_single_snippet_lines: int = 260
    top_k_per_role: int = 14


@dataclass(frozen=True)
class _EvidenceIndex:
    by_id: dict[str, EvidenceItem]
    by_path: dict[str, list[EvidenceItem]]
    by_path_symbol: dict[tuple[str, str], list[EvidenceItem]]


def write_author_marker_code_report_artifacts(
    *,
    method_root: Path,
    project_root: Path,
    raw_pack: RawEvidencePack,
    author_markers: AuthorMarkers | None,
    navigation_plan: AnalysisNavigationPlan | None = None,
) -> tuple[CodeMethodAnalysis | None, dict[str, Path]]:
    """Write author-marker code report artifacts and return Phase 3 analysis.

    If no author markers are provided, this stage intentionally does nothing:
    the older alignment/comment-based scaffold remains the fallback path.
    """

    if author_markers is None:
        return None, {}

    method_root.mkdir(parents=True, exist_ok=True)
    artifacts = build_author_marker_code_report(
        project_root=project_root,
        raw_pack=raw_pack,
        author_markers=author_markers,
        navigation_plan=navigation_plan,
    )
    paths = {
        "author_marker_method_summary": method_root / "author_marker_method_summary.json",
        "code_sources": method_root / "code_sources.json",
        "core_snippets": method_root / "core_snippets.json",
        "method_code_alignment": method_root / "method_code_alignment.json",
        "code_intake_report": method_root / "code_intake_report.json",
        "code_facts": method_root / "code_facts.json",
        "code_ir": method_root / "code_ir.json",
        "entity_links": method_root / "entity_links.json",
        "code_analysis_report": method_root / "code_analysis_report.json",
        "phase2_code_report": method_root / "phase2_code_report.json",
    }
    for name, path in paths.items():
        _write_json(path, artifacts[name])
    analysis = CodeMethodAnalysis.model_validate(artifacts["code_method_analysis"])
    return analysis, paths


def build_author_marker_code_report(
    *,
    project_root: Path,
    raw_pack: RawEvidencePack,
    author_markers: AuthorMarkers,
    navigation_plan: AnalysisNavigationPlan | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    budget = _budget_from_env()
    evidence_index = _build_evidence_index(raw_pack)
    method_summary = _author_method_summary(author_markers)
    code_sources = _scan_repo(root, author_markers=author_markers, budget=budget)
    keyword_bank, role_keywords = _keyword_bank(author_markers)
    candidate_files = _select_candidate_files(
        code_sources.get("project_files", []),
        keyword_bank=keyword_bank,
        author_markers=author_markers,
        top_k=140,
    )
    snippets = _extract_snippets(
        root=root,
        files=candidate_files,
        author_markers=author_markers,
        role_keywords=role_keywords,
        budget=budget,
    )
    for snippet in snippets:
        evidence_ids = _evidence_ids_for_snippet(snippet, evidence_index=evidence_index)
        snippet["evidence_ids"] = evidence_ids
        snippet.setdefault("relevance", {})["evidence_ids"] = evidence_ids

    core_snippets = _build_core_snippets(snippets, author_markers=author_markers)
    method_code_alignment = _align_author_markers_to_code(
        author_markers=author_markers,
        core_snippets=core_snippets,
        evidence_index=evidence_index,
    )
    code_intake_report = _build_intake_report(
        code_sources=code_sources,
        core_snippets=core_snippets,
        method_code_alignment=method_code_alignment,
        budget=budget,
    )
    code_facts = _build_code_facts(
        author_markers=author_markers,
        core_snippets=core_snippets,
        method_code_alignment=method_code_alignment,
    )
    code_ir = _build_code_ir(code_facts)
    entity_links = _build_entity_links(code_facts, method_code_alignment)
    code_analysis_report = _build_code_analysis_report(code_facts, core_snippets, method_code_alignment)
    analysis = _code_method_analysis_from_report(
        raw_pack=raw_pack,
        author_markers=author_markers,
        method_code_alignment=method_code_alignment,
        code_facts=code_facts,
        navigation_plan=navigation_plan,
        evidence_index=evidence_index,
    )
    phase2_code_report = {
        "meta": {
            "version": "author-marker-code-report-v1",
            "producer": "code2paper.code_report",
            "source_design": "PosterGen Code Intake / Code Analyzer adapted for author_markers.yaml",
            "project_id": raw_pack.project_id,
        },
        "author_marker_method_summary": method_summary,
        "code_intake_report": code_intake_report,
        "code_analysis_report": code_analysis_report,
        "phase3_input_contract": {
            "primary_artifact": "code_method_analysis.json",
            "supporting_artifacts": [
                "code_facts.json",
                "method_code_alignment.json",
                "core_snippets.json",
                "code_ir.json",
            ],
            "evidence_id_policy": "Snippet IDs are local; Phase 3 must ground claims using E-prefixed evidence_ids.",
        },
    }
    return {
        "author_marker_method_summary": method_summary,
        "code_sources": code_sources,
        "core_snippets": core_snippets,
        "method_code_alignment": method_code_alignment,
        "code_intake_report": code_intake_report,
        "code_facts": code_facts,
        "code_ir": code_ir,
        "entity_links": entity_links,
        "code_analysis_report": code_analysis_report,
        "phase2_code_report": phase2_code_report,
        "code_method_analysis": analysis.model_dump(mode="json"),
    }


def merge_code_report_analysis(
    *,
    code_report_analysis: CodeMethodAnalysis | None,
    scaffold_analysis: CodeMethodAnalysis,
) -> CodeMethodAnalysis:
    """Use the code report as primary Phase 2 analysis while keeping comments."""

    if code_report_analysis is None:
        return scaffold_analysis
    merged = code_report_analysis.model_copy(deep=True)
    merged.comment_driven_insights = [
        insight
        for insight in scaffold_analysis.comment_driven_insights
        if insight.verified_by_hard_span_ids
        and insight.verification_status in {ConflictStatus.SUPPORTED, ConflictStatus.PARTIALLY_SUPPORTED}
    ][:24]
    if not merged.navigation_questions:
        merged.navigation_questions = scaffold_analysis.navigation_questions
    else:
        existing = {question.question for question in merged.navigation_questions}
        for question in scaffold_analysis.navigation_questions:
            if question.question not in existing:
                merged.navigation_questions.append(question)
                existing.add(question.question)
    comment_evidence_ids = {
        evidence_id
        for insight in merged.comment_driven_insights
        for evidence_id in insight.verified_by_hard_span_ids
    }
    comment_spans = [
        span
        for span in scaffold_analysis.evidence_spans
        if span.evidence_id in comment_evidence_ids
    ]
    merged.evidence_spans = _dedupe_evidence_spans(merged.evidence_spans + comment_spans)
    return merged


def _budget_from_env() -> _ScanBudget:
    return _ScanBudget(
        max_total_files=_int_env("CODE2PAPER_CODE_REPORT_MAX_FILES", 180),
        max_total_bytes=_int_env("CODE2PAPER_CODE_REPORT_MAX_BYTES", 24 * 1024 * 1024),
        max_single_file_bytes=_int_env("CODE2PAPER_CODE_REPORT_MAX_SINGLE_FILE_BYTES", 768 * 1024),
        max_total_snippet_lines=_int_env("CODE2PAPER_CODE_REPORT_MAX_SNIPPET_LINES", 4200),
        max_single_snippet_lines=_int_env("CODE2PAPER_CODE_REPORT_MAX_SINGLE_SNIPPET_LINES", 260),
        top_k_per_role=_int_env("CODE2PAPER_CODE_REPORT_TOP_K_PER_ROLE", 14),
    )


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _build_evidence_index(raw_pack: RawEvidencePack) -> _EvidenceIndex:
    by_id = {item.evidence_id: item for item in raw_pack.evidence_items}
    by_path: dict[str, list[EvidenceItem]] = {}
    by_path_symbol: dict[tuple[str, str], list[EvidenceItem]] = {}
    for item in raw_pack.evidence_items:
        by_path.setdefault(item.path, []).append(item)
        if item.symbol:
            by_path_symbol.setdefault((item.path, item.symbol), []).append(item)
    return _EvidenceIndex(by_id=by_id, by_path=by_path, by_path_symbol=by_path_symbol)


def _author_method_summary(author_markers: AuthorMarkers) -> dict[str, Any]:
    return {
        "meta": {"version": "author-markers-v1", "source": "author_markers.yaml"},
        "project_goal": author_markers.project_goal,
        "paper_method_goal": author_markers.paper_method_goal,
        "implementation_scope": author_markers.implementation_scope,
        "method_mainline": author_markers.method_mainline,
        "paper_story_order": author_markers.paper_story_order,
        "method": {
            "modules": [
                {
                    "module_id": _slug(role.symbol or Path(role.path).stem or f"module_{index}"),
                    "name": role.symbol or Path(role.path).stem,
                    "path": role.path,
                    "role": role.role,
                    "importance": role.importance.value,
                    "is_novel": role.is_novel,
                    "notes": role.notes,
                }
                for index, role in enumerate(author_markers.module_roles, start=1)
            ],
            "pipeline_steps": [
                {
                    "step_id": f"A{index}",
                    "name": step.name,
                    "description": step.purpose,
                    "input": step.input,
                    "output": step.output,
                    "related_files": step.related_files,
                    "highlight_level": step.highlight_level.value,
                    "omit_from_main_figure": step.omit_from_main_figure,
                }
                for index, step in enumerate(author_markers.pipeline_steps, start=1)
            ],
            "losses": [],
            "innovations": [
                {"what": claim.claim, "confidence": claim.confidence.value, "caveats": claim.caveats}
                for claim in author_markers.innovation_claims
            ],
            "design_intents": [intent.model_dump(mode="json") for intent in author_markers.design_intents],
            "potential_mismatches": [mismatch.model_dump(mode="json") for mismatch in author_markers.potential_mismatches],
        },
    }


def _scan_repo(root: Path, *, author_markers: AuthorMarkers, budget: _ScanBudget) -> dict[str, Any]:
    ignored = set(author_markers.ignore_files) | DEFAULT_IGNORE_GLOBS
    priority_files = _expand_author_paths(root, author_markers.priority_files, ignored=ignored)
    related_files = _expand_author_paths(
        root,
        [path for step in author_markers.pipeline_steps for path in step.related_files]
        + [role.path for role in author_markers.module_roles]
        + [path for claim in author_markers.innovation_claims for path in claim.supporting_files]
        + [path for intent in author_markers.design_intents for path in intent.supporting_files],
        ignored=ignored,
    )
    ordered_seed = _dedupe_paths(priority_files + related_files)
    files: list[Path] = []
    seen = set()
    total_bytes = 0
    warnings: list[str] = []
    errors: list[str] = []

    def add_file(path: Path) -> None:
        nonlocal total_bytes
        if path in seen or not path.is_file() or not _is_scannable(path):
            return
        rel = path.relative_to(root).as_posix()
        if _is_ignored(rel, ignored) or any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            return
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"stat_failed:{rel}:{exc}")
            return
        if size > budget.max_single_file_bytes:
            warnings.append(f"oversized_file:{rel}:{size}")
            return
        if len(files) + 1 > budget.max_total_files:
            warnings.append("budget_stop:max_total_files")
            return
        if total_bytes + size > budget.max_total_bytes:
            warnings.append("budget_stop:max_total_bytes")
            return
        files.append(path)
        seen.add(path)
        total_bytes += size

    for path in ordered_seed:
        add_file(path)
    for path in sorted(root.rglob("*"), key=lambda p: _path_rank(p.relative_to(root).as_posix() if p.is_file() else str(p))):
        if len(files) >= budget.max_total_files or total_bytes >= budget.max_total_bytes:
            break
        add_file(path)

    project_files = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower()
        project_files.append(
            {
                "path": rel,
                "abs_path": str(path),
                "ext": ext,
                "language": _language_for_ext(ext),
                "size_bytes": path.stat().st_size,
                "sha1": _sha1_file(path),
                "kind": _kind_for_path(path),
                "author_priority": rel in set(author_markers.priority_files),
            }
        )
    return {
        "meta": {
            "repo_id": _sha1_text(str(root)),
            "root_path": str(root),
            "filters": {"ignored": sorted(ignored), "include_exts": sorted(SOURCE_EXTS)},
            "scan_stats": {
                "scanned_files": len(project_files),
                "scanned_bytes": total_bytes,
                "max_total_files": budget.max_total_files,
                "max_total_bytes": budget.max_total_bytes,
                "max_single_file_bytes": budget.max_single_file_bytes,
            },
        },
        "project_files": project_files,
        "repo_structure_hints": _repo_structure_hints(project_files),
        "errors": errors,
        "warnings": _dedupe_strings(warnings),
    }


def _expand_author_paths(root: Path, patterns: list[str], *, ignored: set[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in patterns:
        if not raw:
            continue
        pattern = raw.strip()
        if any(ch in pattern for ch in "*?["):
            for match in sorted(root.glob(pattern)):
                if match.is_file() and not _is_ignored(match.relative_to(root).as_posix(), ignored):
                    paths.append(match.resolve())
            continue
        path = (root / pattern).resolve()
        if path.is_file() and not _is_ignored(pattern, ignored):
            paths.append(path)
    return paths


def _is_scannable(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_EXTS or path.name.lower() == "makefile"


def _is_ignored(rel: str, ignored: set[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(Path(rel).name, pattern) for pattern in ignored)


def _path_rank(rel: str) -> tuple[int, int, str]:
    lowered = rel.lower()
    core = ("train", "model", "encoder", "decoder", "projector", "dataset", "data", "loss", "forward", "builder")
    noise = ("eval", "test", "docs", "example", "media", "readme")
    return (1 if any(term in lowered for term in noise) else 0, 0 if any(term in lowered for term in core) else 1, lowered)


def _select_candidate_files(
    files: list[dict[str, Any]],
    *,
    keyword_bank: list[str],
    author_markers: AuthorMarkers,
    top_k: int,
) -> list[dict[str, Any]]:
    priority_refs = set(author_markers.priority_files)
    related_refs = {
        path
        for step in author_markers.pipeline_steps
        for path in step.related_files
    } | {role.path for role in author_markers.module_roles}
    bank = [term.lower() for term in keyword_bank if len(term) >= 3][:240]
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in files:
        path = str(item.get("path") or "")
        abs_path = Path(str(item.get("abs_path") or path))
        score = 0.0
        if path in priority_refs:
            score += 100.0
        if path in related_refs:
            score += 70.0
        name = Path(path).name.lower()
        if any(term in name for term in ["train", "model", "encoder", "projector", "dataset", "data", "builder"]):
            score += 5.0
        try:
            sample = abs_path.read_text(encoding="utf-8", errors="ignore")[:30000].lower()
        except OSError:
            sample = ""
        score += min(sum(1 for term in bank if term in sample), 80) * 0.2
        if "def forward" in sample:
            score += 3.0
        if "class " in sample:
            score += 1.0
        scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("path", "")))
    selected = [item for score, item in scored if score > 0][:top_k]
    if not selected:
        selected = [item for _, item in scored[:top_k]]
    return selected


def _keyword_bank(author_markers: AuthorMarkers) -> tuple[list[str], dict[str, list[str]]]:
    bank: set[str] = set()
    role_keywords: dict[str, list[str]] = {}

    def add(text: str, role: str = "") -> None:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text or ""):
            normalized = token.lower().strip("_-")
            if not normalized:
                continue
            bank.add(normalized)
            if role:
                role_keywords.setdefault(role, [])
                if normalized not in role_keywords[role]:
                    role_keywords[role].append(normalized)

    add(author_markers.project_goal)
    add(author_markers.paper_method_goal)
    add(author_markers.method_mainline)
    for role in author_markers.module_roles:
        role_key = _normalize_role(role.role)
        add(role.path, role_key)
        add(role.symbol, role_key)
        add(role.role, role_key)
        add(role.notes, role_key)
    for step in author_markers.pipeline_steps:
        role_key = _normalize_role(step.name)
        add(step.name, role_key)
        add(step.purpose, role_key)
        for value in step.input + step.output + step.related_files:
            add(value, role_key)
    for claim in author_markers.innovation_claims:
        add(claim.claim)
        for value in claim.supporting_files + claim.supporting_functions:
            add(value)
    for intent in author_markers.design_intents:
        add(intent.intent)
        add(intent.rationale)
        for value in intent.supporting_files + intent.supporting_functions:
            add(value)
    for common in ["forward", "backbone", "encoder", "decoder", "projector", "loss", "dataset", "train", "optimizer"]:
        bank.add(common)
    return sorted(bank), role_keywords


def _extract_snippets(
    *,
    root: Path,
    files: list[dict[str, Any]],
    author_markers: AuthorMarkers,
    role_keywords: dict[str, list[str]],
    budget: _ScanBudget,
) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    used_lines = 0
    per_role_counts: dict[str, int] = {}
    seen: set[tuple[str, int, int, str]] = set()
    explicit_refs = _explicit_symbol_refs(author_markers)

    for item in files:
        rel = str(item.get("path") or "")
        abs_path = root / rel
        try:
            lines = abs_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        candidates = _python_candidates(lines, rel, author_markers, role_keywords) if abs_path.suffix.lower() == ".py" else []
        candidates.extend(_explicit_symbol_candidates(lines, rel, explicit_refs))
        if not candidates:
            candidates = _regex_candidates(lines, rel, author_markers)
        candidates = _dedupe_candidates(candidates)
        for role, symbol, start, end, signals in candidates:
            role = _normalize_role(role) or "other"
            if per_role_counts.get(role, 0) >= budget.top_k_per_role and rel not in author_markers.priority_files:
                continue
            start = max(1, start)
            end = min(len(lines), end)
            if end < start:
                continue
            if end - start + 1 > budget.max_single_snippet_lines:
                end = start + budget.max_single_snippet_lines - 1
            length = end - start + 1
            if used_lines + length > budget.max_total_snippet_lines:
                return snippets
            key = (rel, start, end, symbol)
            if key in seen:
                continue
            seen.add(key)
            snippet_id = f"sn{len(snippets) + 1}"
            text = "\n".join(lines[start - 1 : end])
            snippets.append(
                {
                    "snippet_id": snippet_id,
                    "role": role,
                    "symbol": symbol,
                    "source": {
                        "path": rel,
                        "start_line": start,
                        "end_line": end,
                        "sha1": str(item.get("sha1") or ""),
                    },
                    "text": text,
                    "signals": _dedupe_strings(signals),
                    "relevance": {"author_step_ids": [], "score": 0.0, "reason": ""},
                    "quality": {"parsable": True, "length_lines": length, "has_external_deps": False},
                }
            )
            used_lines += length
            per_role_counts[role] = per_role_counts.get(role, 0) + 1
    return snippets


def _python_candidates(
    lines: list[str],
    rel: str,
    author_markers: AuthorMarkers,
    role_keywords: dict[str, list[str]],
) -> list[tuple[str, str, int, int, list[str]]]:
    text = "\n".join(lines)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    candidates: list[tuple[str, str, int, int, list[str]]] = []
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbol = node.name
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            block = lines[start - 1 : end]
            role = _role_for_symbol(rel, symbol, block, author_markers, role_keywords)
            candidates.append((role, symbol, start, end, _signals(block, role)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            owner = parent.get(node)
            symbol = f"{owner.name}.{node.name}" if isinstance(owner, ast.ClassDef) else node.name
            start = getattr(node, "lineno", 1)
            end = getattr(node, "end_lineno", start)
            block = lines[start - 1 : end]
            role = _role_for_symbol(rel, symbol, block, author_markers, role_keywords)
            candidates.append((role, symbol, start, end, _signals(block, role)))
    candidates.sort(key=lambda item: (item[2], item[1]))
    return candidates


def _explicit_symbol_refs(author_markers: AuthorMarkers) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for role in author_markers.module_roles:
        if role.symbol:
            refs.setdefault(role.path, []).append(role.symbol)
    for claim in author_markers.innovation_claims:
        for path in claim.supporting_files:
            refs.setdefault(path, []).extend(claim.supporting_functions)
    for intent in author_markers.design_intents:
        for path in intent.supporting_files:
            refs.setdefault(path, []).extend(intent.supporting_functions)
    return {path: _dedupe_strings(symbols) for path, symbols in refs.items()}


def _explicit_symbol_candidates(
    lines: list[str],
    rel: str,
    explicit_refs: dict[str, list[str]],
) -> list[tuple[str, str, int, int, list[str]]]:
    refs = explicit_refs.get(rel, [])
    if not refs:
        return []
    candidates: list[tuple[str, str, int, int, list[str]]] = []
    for symbol in refs:
        leaf = symbol.split(".")[-1]
        pattern = re.compile(rf"^\s*(class|def|async\s+def)\s+{re.escape(leaf)}\b")
        for index, line in enumerate(lines, start=1):
            if pattern.search(line):
                start, end = _expand_block(lines, index)
                candidates.append((_normalize_role(symbol), symbol, start, end, ["author_explicit_symbol", symbol]))
                break
    return candidates


def _regex_candidates(lines: list[str], rel: str, author_markers: AuthorMarkers) -> list[tuple[str, str, int, int, list[str]]]:
    candidates: list[tuple[str, str, int, int, list[str]]] = []
    ext = Path(rel).suffix.lower()
    if ext in {".sh"}:
        role = "training_loop" if "train" in rel.lower() else "config"
        candidates.append((role, Path(rel).name, 1, min(len(lines), 160), ["script", role]))
        return candidates
    if ext in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}:
        candidates.append(("config", Path(rel).name, 1, min(len(lines), 160), ["config"]))
        return candidates
    for index, line in enumerate(lines, start=1):
        low = line.lower()
        if "def forward" in low:
            start, end = _expand_block(lines, index)
            candidates.append(("forward", "forward", start, end, ["def forward"]))
        elif "loss" in low and ("=" in low or "def " in low or "criterion" in low):
            start, end = _expand_window(lines, index, 24)
            candidates.append(("loss", "loss", start, end, ["loss"]))
        elif "dataset" in low or "dataloader" in low:
            start, end = _expand_window(lines, index, 28)
            candidates.append(("dataset", "dataset", start, end, ["dataset"]))
        elif "optimizer" in low or "backward" in low or "requires_grad" in low:
            start, end = _expand_window(lines, index, 32)
            candidates.append(("training_loop", "training_loop", start, end, ["optimizer/backward"]))
    return candidates


def _role_for_symbol(
    rel: str,
    symbol: str,
    block: list[str],
    author_markers: AuthorMarkers,
    role_keywords: dict[str, list[str]],
) -> str:
    symbol_low = symbol.lower()
    block_low = "\n".join(block).lower()
    for role in author_markers.module_roles:
        role_symbol = role.symbol.lower()
        if role.path == rel and role_symbol:
            if symbol_low == role_symbol or symbol_low == role_symbol.split(".")[-1] or symbol_low.endswith("." + role_symbol.split(".")[-1]):
                return role.role
            if role_symbol.split(".")[0] in symbol_low:
                return role.role
    for role_name, keywords in role_keywords.items():
        if any(keyword in symbol_low or keyword in block_low for keyword in keywords[:30]):
            return role_name
    if symbol_low.endswith("forward"):
        return "forward"
    if "loss" in symbol_low or "criterion" in block_low:
        return "loss"
    if "dataset" in symbol_low or "dataloader" in symbol_low:
        return "dataset"
    if "train" in symbol_low or "optimizer" in block_low or "backward" in block_low:
        return "training_loop"
    if "eval" in symbol_low or "metric" in symbol_low:
        return "evaluation"
    if "infer" in symbol_low or "generate" in symbol_low:
        return "inference"
    if "nn.module" in block_low or "module" in block_low or "model" in symbol_low:
        return "model_arch"
    return "other"


def _normalize_role(value: str) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    if text in BASE_ROLES:
        return text
    if any(term in text for term in ["loss", "objective"]):
        return "loss"
    if any(term in text for term in ["dataset", "data", "load", "supervision"]):
        return "dataset"
    if any(term in text for term in ["train", "stage", "optimizer", "orchestration", "freeze", "adapter"]):
        return "training_loop"
    if any(term in text for term in ["forward", "fusion", "inject", "project", "encoder", "decoder", "aggregation", "token", "backbone"]):
        return "model_arch"
    if any(term in text for term in ["eval", "metric"]):
        return "evaluation"
    if any(term in text for term in ["infer", "generation"]):
        return "inference"
    if any(term in text for term in ["config", "argument", "script"]):
        return "config"
    return re.sub(r"[^a-z0-9_]+", "_", text).strip("_")[:48] or "other"


def _signals(block: list[str], role: str) -> list[str]:
    sample = "\n".join(block).lower()
    signals = [role] if role else []
    for term in ["def forward", "nn.module", "requires_grad", "optimizer", "loss", "dataset", "projector", "point", "token"]:
        if term in sample:
            signals.append(term)
    return signals[:16]


def _expand_block(lines: list[str], lineno: int) -> tuple[int, int]:
    start = lineno
    indent = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip(" "))
    end = lineno
    for index in range(lineno, len(lines)):
        cur = lines[index]
        if not cur.strip():
            end = index + 1
            continue
        cur_indent = len(cur) - len(cur.lstrip(" "))
        if cur_indent <= indent and index + 1 > lineno:
            break
        end = index + 1
    return start, end


def _expand_window(lines: list[str], lineno: int, radius: int) -> tuple[int, int]:
    return max(1, lineno - radius), min(len(lines), lineno + radius)


def _dedupe_candidates(candidates: list[tuple[str, str, int, int, list[str]]]) -> list[tuple[str, str, int, int, list[str]]]:
    seen: set[tuple[str, int, int]] = set()
    result = []
    for item in sorted(candidates, key=lambda c: (c[2], c[3], c[1])):
        key = (item[1], item[2], item[3])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _evidence_ids_for_snippet(snippet: dict[str, Any], *, evidence_index: _EvidenceIndex) -> list[str]:
    source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
    path = str(source.get("path") or "")
    symbol = str(snippet.get("symbol") or "")
    start = int(source.get("start_line") or 0)
    end = int(source.get("end_line") or 0)
    candidates = list(evidence_index.by_path_symbol.get((path, symbol), []))
    if "." in symbol:
        candidates.extend(evidence_index.by_path_symbol.get((path, symbol.split(".")[-1]), []))
    candidates.extend(evidence_index.by_path.get(path, []))
    hard = [item for item in candidates if item.source_type in {SourceType.SOURCE, SourceType.BASH, SourceType.CONFIG}]
    scored: list[tuple[int, EvidenceItem]] = []
    for item in hard:
        score = 0
        if item.symbol and (item.symbol == symbol or item.symbol == symbol.split(".")[-1] or symbol.endswith("." + item.symbol)):
            score += 50
        if item.line_start and item.line_end and start and end:
            overlap = max(0, min(end, item.line_end) - max(start, item.line_start) + 1)
            if overlap:
                score += 30 + overlap
        elif item.path == path:
            score += 5
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].evidence_id))
    return _dedupe_strings([item.evidence_id for _, item in scored[:14]])


def _evidence_ids_for_path(path: str, *, evidence_index: _EvidenceIndex, symbols: list[str] | None = None) -> list[str]:
    symbols = symbols or []
    ids: list[str] = []
    for symbol in symbols:
        for item in evidence_index.by_path_symbol.get((path, symbol), []):
            if item.source_type in {SourceType.SOURCE, SourceType.BASH, SourceType.CONFIG}:
                ids.append(item.evidence_id)
    for item in evidence_index.by_path.get(path, []):
        if item.source_type in {SourceType.SOURCE, SourceType.BASH, SourceType.CONFIG}:
            ids.append(item.evidence_id)
    return _dedupe_strings(ids[:20])


def _build_core_snippets(snippets: list[dict[str, Any]], *, author_markers: AuthorMarkers) -> dict[str, Any]:
    roles_covered = sorted({str(sn.get("role")) for sn in snippets if sn.get("role")})
    expected_roles = sorted({_normalize_role(role.role) for role in author_markers.module_roles} | {_normalize_role(step.name) for step in author_markers.pipeline_steps} | BASE_ROLES)
    by_file: dict[str, int] = {}
    for sn in snippets:
        source = sn.get("source") if isinstance(sn.get("source"), dict) else {}
        path = str(source.get("path") or "")
        if path:
            by_file[path] = by_file.get(path, 0) + 1
    return {
        "meta": {
            "selection_version": "author-marker-v1",
            "selection_rules": {
                "author_priority_files_first": True,
                "method_text_input": "author_markers.yaml",
            },
        },
        "snippets": snippets,
        "coverage": {
            "roles_covered": roles_covered,
            "roles_missing": [role for role in expected_roles if role not in roles_covered],
            "top_files_by_snippet_count": [path for path, _ in sorted(by_file.items(), key=lambda pair: -pair[1])[:12]],
        },
        "warnings": [],
    }


def _align_author_markers_to_code(
    *,
    author_markers: AuthorMarkers,
    core_snippets: dict[str, Any],
    evidence_index: _EvidenceIndex,
) -> dict[str, Any]:
    snippets = [sn for sn in core_snippets.get("snippets", []) if isinstance(sn, dict)]
    modules = []
    for index, role in enumerate(author_markers.module_roles, start=1):
        matched = _match_snippets_for_author_ref(
            snippets,
            paths=[role.path],
            symbols=[role.symbol] if role.symbol else [],
            text_terms=[role.role, role.notes, role.symbol],
        )
        evidence_ids = _dedupe_strings(
            [eid for sn in matched for eid in sn.get("evidence_ids", [])]
            + _evidence_ids_for_path(role.path, evidence_index=evidence_index, symbols=[role.symbol] if role.symbol else [])
        )[:48]
        modules.append(
            {
                "module_id": f"AM{index}",
                "author_module": role.model_dump(mode="json"),
                "matched_snippets": [_snippet_ref(sn) for sn in matched[:8]],
                "evidence_ids": evidence_ids,
                "missing_implementation": not evidence_ids,
                "implementation_completeness": "supported" if evidence_ids else "missing",
            }
        )
    steps = []
    for index, step in enumerate(author_markers.pipeline_steps, start=1):
        matched = _match_snippets_for_author_ref(
            snippets,
            paths=step.related_files,
            symbols=[],
            text_terms=[step.name, step.purpose] + step.input + step.output,
        )
        evidence_ids = _dedupe_strings(
            [eid for sn in matched for eid in sn.get("evidence_ids", [])]
            + [eid for path in step.related_files for eid in _evidence_ids_for_path(path, evidence_index=evidence_index)]
        )[:96]
        steps.append(
            {
                "step_id": f"AS{index}",
                "author_step": step.model_dump(mode="json"),
                "matched_snippets": [_snippet_ref(sn) for sn in matched[:12]],
                "evidence_ids": evidence_ids,
                "missing_implementation": not evidence_ids,
                "coverage": "supported" if evidence_ids else "missing",
            }
        )
    claims = []
    claim_specs = [
        ("innovation_claim", claim.claim, claim.supporting_files, claim.supporting_functions, claim.caveats)
        for claim in author_markers.innovation_claims
    ] + [
        ("design_intent", intent.intent, intent.supporting_files, intent.supporting_functions, intent.caveats)
        for intent in author_markers.design_intents
    ]
    for index, (kind, text, files, symbols, caveats) in enumerate(claim_specs, start=1):
        evidence_ids = _dedupe_strings(
            [eid for path in files for eid in _evidence_ids_for_path(path, evidence_index=evidence_index, symbols=symbols)]
        )[:48]
        claims.append(
            {
                "claim_id": f"AC{index}",
                "kind": kind,
                "text": text,
                "supporting_files": files,
                "supporting_functions": symbols,
                "evidence_ids": evidence_ids,
                "support_status": "supported" if evidence_ids else "unsupported",
                "caveats": caveats,
            }
        )
    coverage_score = _coverage_score(modules, steps, claims)
    return {
        "meta": {"version": "author-marker-alignment-v1", "producer": "code2paper.code_report"},
        "modules": modules,
        "pipeline_steps": steps,
        "claims": claims,
        "coverage_report": {
            "overall_score": coverage_score,
            "modules_supported": sum(1 for item in modules if item["evidence_ids"]),
            "modules_total": len(modules),
            "pipeline_steps_supported": sum(1 for item in steps if item["evidence_ids"]),
            "pipeline_steps_total": len(steps),
            "claims_supported": sum(1 for item in claims if item["evidence_ids"]),
            "claims_total": len(claims),
            "missing_implementations": [
                item["author_module"]["role"] for item in modules if item["missing_implementation"]
            ] + [item["author_step"]["name"] for item in steps if item["missing_implementation"]],
        },
    }


def _match_snippets_for_author_ref(
    snippets: list[dict[str, Any]],
    *,
    paths: list[str],
    symbols: list[str],
    text_terms: list[str],
) -> list[dict[str, Any]]:
    path_set = set(paths)
    symbol_terms = [symbol.lower() for symbol in symbols if symbol]
    terms = [term.lower() for term in _tokens(" ".join(text_terms)) if len(term) >= 3]
    scored: list[tuple[float, dict[str, Any]]] = []
    for sn in snippets:
        source = sn.get("source") if isinstance(sn.get("source"), dict) else {}
        path = str(source.get("path") or "")
        symbol = str(sn.get("symbol") or "").lower()
        text = str(sn.get("text") or "").lower()
        score = 0.0
        if path in path_set:
            score += 4.0
        if any(symbol == term or symbol.endswith("." + term.split(".")[-1]) for term in symbol_terms):
            score += 5.0
        score += min(sum(1 for term in terms if term in text or term in symbol), 20) * 0.15
        if score > 0:
            scored.append((score, sn))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("snippet_id", "")))
    return [sn for _, sn in scored]


def _snippet_ref(snippet: dict[str, Any]) -> dict[str, Any]:
    source = snippet.get("source") if isinstance(snippet.get("source"), dict) else {}
    return {
        "snippet_id": snippet.get("snippet_id"),
        "role": snippet.get("role"),
        "symbol": snippet.get("symbol", ""),
        "file": source.get("path", ""),
        "lines": [source.get("start_line"), source.get("end_line")],
        "evidence_ids": snippet.get("evidence_ids", []),
    }


def _build_intake_report(
    *,
    code_sources: dict[str, Any],
    core_snippets: dict[str, Any],
    method_code_alignment: dict[str, Any],
    budget: _ScanBudget,
) -> dict[str, Any]:
    coverage = core_snippets.get("coverage", {}) if isinstance(core_snippets, dict) else {}
    alignment_coverage = method_code_alignment.get("coverage_report", {})
    status = "pass"
    blocking_reasons: list[str] = []
    if not core_snippets.get("snippets"):
        status = "fail"
        blocking_reasons.append("no_snippets")
    elif alignment_coverage.get("overall_score", 0) < 0.35:
        status = "warn"
    return {
        "status": status,
        "blocking_reasons": blocking_reasons,
        "coverage_check": {
            "roles_covered": coverage.get("roles_covered", []),
            "roles_missing": coverage.get("roles_missing", []),
            "author_alignment_score": alignment_coverage.get("overall_score", 0),
        },
        "quality_check": {"oversized_files": [], "low_signal_files": [], "unparsable_snippets": []},
        "consistency_check": {
            "method_input": "author_markers.yaml",
            "suspicious_mismatch": bool(alignment_coverage.get("missing_implementations")),
        },
        "budget_used": {
            "files": code_sources.get("meta", {}).get("scan_stats", {}).get("scanned_files", 0),
            "bytes": code_sources.get("meta", {}).get("scan_stats", {}).get("scanned_bytes", 0),
            "snippet_lines": sum(
                int(sn.get("quality", {}).get("length_lines", 0))
                for sn in core_snippets.get("snippets", [])
                if isinstance(sn, dict)
            ),
            "max_total_snippet_lines": budget.max_total_snippet_lines,
        },
        "recommended_actions": [
            f"Review missing author marker implementation: {item}"
            for item in alignment_coverage.get("missing_implementations", [])[:12]
        ],
    }


def _build_code_facts(
    *,
    author_markers: AuthorMarkers,
    core_snippets: dict[str, Any],
    method_code_alignment: dict[str, Any],
) -> dict[str, Any]:
    snippet_map = {sn.get("snippet_id"): sn for sn in core_snippets.get("snippets", []) if isinstance(sn, dict)}
    modules = []
    for module_alignment in method_code_alignment.get("modules", []):
        author_module = module_alignment.get("author_module", {})
        matched = module_alignment.get("matched_snippets", [])
        first = matched[0] if matched else {}
        snippet = snippet_map.get(first.get("snippet_id"), {}) if isinstance(first, dict) else {}
        text = snippet.get("text", "") if isinstance(snippet, dict) else ""
        class_info = _class_or_function_info(text)
        modules.append(
            {
                "name": author_module.get("symbol") or class_info.get("name") or Path(author_module.get("path", "")).stem,
                "role": author_module.get("role", ""),
                "method_ref": author_module.get("role", ""),
                "path": author_module.get("path", ""),
                "importance": author_module.get("importance", "core"),
                "is_novel": bool(author_module.get("is_novel", False)),
                "interfaces": class_info.get("methods", [])[:8],
                "attributes": class_info.get("attributes", [])[:12],
                "methods": class_info.get("methods", [])[:12],
                "input_spec": _input_spec(text),
                "output_spec": _output_spec(text),
                "key_logic": _key_logic(text),
                "evidence_refs": module_alignment.get("evidence_ids", []),
                "snippet_refs": [item.get("snippet_id") for item in matched if item.get("snippet_id")],
                "confidence": 0.86 if module_alignment.get("evidence_ids") else 0.35,
            }
        )
    pipeline_steps = []
    for step_alignment in method_code_alignment.get("pipeline_steps", []):
        step = step_alignment.get("author_step", {})
        related_files = step.get("related_files", []) if isinstance(step.get("related_files"), list) else []
        involved = [module["name"] for module in modules if module.get("path") in related_files]
        pipeline_steps.append(
            {
                "step_id": step_alignment.get("step_id", ""),
                "name": step.get("name", ""),
                "description": step.get("purpose", ""),
                "input_data": step.get("input", []),
                "output_data": step.get("output", []),
                "related_files": related_files,
                "involved_modules": involved,
                "data_flow": " -> ".join([str(v) for v in step.get("input", []) + step.get("output", [])]),
                "key_operations": _tokens(step.get("purpose", ""))[:10],
                "evidence_refs": step_alignment.get("evidence_ids", []),
                "confidence": 0.82 if step_alignment.get("evidence_ids") else 0.3,
            }
        )
    training_detail = _training_detail(core_snippets)
    data_detail = _data_detail(core_snippets)
    losses = _losses(core_snippets)
    alignment_validation = {
        "overall_score": method_code_alignment.get("coverage_report", {}).get("overall_score", 0),
        "missing_implementations": method_code_alignment.get("coverage_report", {}).get("missing_implementations", []),
        "uncertainties": [],
    }
    overview = {
        "implementation_summary": _join_sentences(
            [author_markers.paper_method_goal or author_markers.project_goal, author_markers.method_mainline]
        ),
        "architecture_summary": _join_sentences([
            "Core modules: " + ", ".join(module["name"] for module in modules[:8]) if modules else "",
            "Pipeline: " + " -> ".join(step["name"] for step in pipeline_steps) if pipeline_steps else "",
        ]),
        "training_summary": _training_summary(training_detail),
        "alignment_summary": f"Author-marker-to-code alignment score is {alignment_validation['overall_score']:.2f}.",
    }
    return {
        "meta": {
            "version": "v2-author-marker",
            "producer": "code2paper.code_report",
            "total_snippets": len(core_snippets.get("snippets", [])),
            "alignment_score": alignment_validation["overall_score"],
            "method_input": "author_markers.yaml",
        },
        "overview": overview,
        "modules": modules,
        "pipeline_steps": pipeline_steps,
        "losses": losses,
        "training_detail": training_detail,
        "data_detail": data_detail,
        "alignment_validation": alignment_validation,
        "key_insights": _key_insights(author_markers, modules, pipeline_steps, method_code_alignment),
        "diagram_hints": {"ordered_stage_names": [step["name"] for step in pipeline_steps]},
        "missing_fields_report": {"missing_implementations": alignment_validation["missing_implementations"]},
    }


def _code_method_analysis_from_report(
    *,
    raw_pack: RawEvidencePack,
    author_markers: AuthorMarkers,
    method_code_alignment: dict[str, Any],
    code_facts: dict[str, Any],
    navigation_plan: AnalysisNavigationPlan | None,
    evidence_index: _EvidenceIndex,
) -> CodeMethodAnalysis:
    questions = list(navigation_plan.navigation_questions) if navigation_plan else []
    existing_questions = {q.question for q in questions}
    for index, step in enumerate(author_markers.pipeline_steps, start=1):
        question = f"What implementation evidence supports author-marker stage '{step.name}'?"
        if question in existing_questions:
            continue
        questions.append(
            NavigationQuestion(
                question_id=f"Q{len(questions) + 1}",
                question=question,
                driven_by=["author", "code_report"],
                target_paths_or_symbols=step.related_files,
                priority=NavigationWeight.HIGH if step.highlight_level.value == "main" else NavigationWeight.MEDIUM,
            )
        )
    module_items: list[CodeMethodModule] = []
    for module in code_facts.get("modules", []):
        if not isinstance(module, dict):
            continue
        evidence_ids = _dedupe_strings([str(eid) for eid in module.get("evidence_refs", []) if str(eid).startswith("E")])
        importance = str(module.get("importance") or "core")
        category = ModuleCategory.METHOD_CORE if importance == "core" else ModuleCategory.EXPERIMENT_SUPPORT
        module_items.append(
            CodeMethodModule(
                path=str(module.get("path") or ""),
                symbols=[str(module.get("name") or "")] if module.get("name") else [],
                module_class=category,
                paper_role=str(module.get("role") or ""),
                evidence_span_ids=evidence_ids,
                llm_confidence=ConfidenceLevel.HIGH if evidence_ids and category == ModuleCategory.METHOD_CORE else ConfidenceLevel.MEDIUM,
            )
        )
    mechanisms: list[CandidateMechanism] = []
    for index, step in enumerate(code_facts.get("pipeline_steps", []), start=1):
        if not isinstance(step, dict):
            continue
        evidence_ids = _dedupe_strings([str(eid) for eid in step.get("evidence_refs", []) if str(eid).startswith("E")])
        if not evidence_ids:
            continue
        mechanisms.append(
            CandidateMechanism(
                mechanism_id=f"MECH-{index:03d}",
                name=str(step.get("name") or f"Stage {index}"),
                description=str(step.get("description") or f"Implementation-backed stage {index}."),
                inputs=[str(value) for value in step.get("input_data", [])],
                outputs=[str(value) for value in step.get("output_data", [])],
                supporting_span_ids=evidence_ids[:120],
            )
        )
    supported_flow = [step["author_step"]["name"] for step in method_code_alignment.get("pipeline_steps", []) if step.get("evidence_ids")]
    proposed_flow = author_markers.paper_story_order or [step.name for step in author_markers.pipeline_steps]
    unsupported_flow = [name for name in proposed_flow if name not in supported_flow]
    gaps = [f"Missing implementation evidence for author marker: {name}" for name in unsupported_flow]
    for missing in method_code_alignment.get("coverage_report", {}).get("missing_implementations", []):
        gaps.append(f"Code report coverage gap: {missing}")
    evidence_ids = _dedupe_strings(
        [eid for module in module_items for eid in module.evidence_span_ids]
        + [eid for mechanism in mechanisms for eid in mechanism.supporting_span_ids]
    )
    evidence_spans = [_as_evidence_span(evidence_index.by_id[eid]) for eid in evidence_ids if eid in evidence_index.by_id]
    distinguishing = [
        module.paper_role
        for module in module_items
        if any(role.is_novel and role.role == module.paper_role for role in author_markers.module_roles)
    ] + [claim.claim for claim in author_markers.innovation_claims]
    return CodeMethodAnalysis(
        navigation_questions=questions,
        execution_flows=[
            CodeMethodExecutionFlow(
                flow_id="FLOW-author-marker-mainline",
                purpose=author_markers.method_mainline or author_markers.paper_method_goal or author_markers.project_goal,
                ordered_steps=proposed_flow,
                entrypoint_span_ids=[],
                config_resolution_span_ids=[],
            )
        ],
        method_modules=module_items,
        candidate_mechanisms=mechanisms,
        comment_driven_insights=[],
        author_alignment=Phase2AuthorAlignment(
            author_proposed_flow=proposed_flow,
            author_supported_flow=supported_flow,
            author_unsupported_parts=unsupported_flow,
        ),
        candidate_distinguishing_mechanisms=_dedupe_strings(distinguishing),
        evidence_spans=evidence_spans,
        gaps=_dedupe_strings(gaps),
    )


def _as_evidence_span(item: EvidenceItem) -> EvidenceSpan:
    return EvidenceSpan(
        evidence_id=item.evidence_id,
        source_type=item.source_type,
        path=item.path,
        symbol=item.symbol,
        line_start=item.line_start,
        line_end=item.line_end,
        config_key=item.config_key,
        shell_command_segment=item.shell_command_segment,
        excerpt_hash=item.excerpt_hash,
        evidence_strength=item.evidence_strength,
        confidence=item.confidence,
    )


def _build_code_ir(code_facts: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for module in code_facts.get("modules", []):
        node_id = "module:" + _slug(str(module.get("name") or module.get("path") or len(nodes)))
        nodes.append({"id": node_id, "type": "module", "label": module.get("name"), "evidence_refs": module.get("evidence_refs", [])})
    previous = ""
    for step in code_facts.get("pipeline_steps", []):
        node_id = "step:" + _slug(str(step.get("name") or len(nodes)))
        nodes.append({"id": node_id, "type": "pipeline_step", "label": step.get("name"), "evidence_refs": step.get("evidence_refs", [])})
        if previous:
            edges.append({"source": previous, "target": node_id, "type": "next_step"})
        previous = node_id
    return {"meta": {"version": "code-ir-author-marker-v1"}, "nodes": nodes, "edges": edges, "annotations": []}


def _build_entity_links(code_facts: dict[str, Any], method_code_alignment: dict[str, Any]) -> dict[str, Any]:
    links = []
    for module in method_code_alignment.get("modules", []):
        author_module = module.get("author_module", {})
        for evidence_id in module.get("evidence_ids", []):
            links.append(
                {
                    "entity_type": "author_module",
                    "entity_name": author_module.get("role") or author_module.get("symbol"),
                    "path": author_module.get("path", ""),
                    "evidence_id": evidence_id,
                }
            )
    for step in method_code_alignment.get("pipeline_steps", []):
        author_step = step.get("author_step", {})
        for evidence_id in step.get("evidence_ids", []):
            links.append(
                {
                    "entity_type": "author_pipeline_step",
                    "entity_name": author_step.get("name"),
                    "path": ",".join(author_step.get("related_files", [])),
                    "evidence_id": evidence_id,
                }
            )
    return {"meta": {"version": "entity-links-author-marker-v1"}, "links": links}


def _build_code_analysis_report(code_facts: dict[str, Any], core_snippets: dict[str, Any], method_code_alignment: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_snippets": len(core_snippets.get("snippets", [])),
        "modules_found": len(code_facts.get("modules", [])),
        "pipeline_steps_found": len(code_facts.get("pipeline_steps", [])),
        "losses_found": len(code_facts.get("losses", [])),
        "alignment_score": method_code_alignment.get("coverage_report", {}).get("overall_score", 0),
        "llm_used": False,
        "method_input": "author_markers.yaml",
    }


def _coverage_score(modules: list[dict[str, Any]], steps: list[dict[str, Any]], claims: list[dict[str, Any]]) -> float:
    total = len(modules) + len(steps) + len(claims)
    if total == 0:
        return 0.0
    supported = sum(1 for item in modules + steps + claims if item.get("evidence_ids"))
    return round(supported / total, 3)


def _class_or_function_info(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {"name": "", "methods": [], "attributes": []}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
            attrs = []
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name) and child.value.id == "self":
                    attrs.append(child.attr)
            return {"name": node.name, "methods": _dedupe_strings(methods), "attributes": _dedupe_strings(attrs)}
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return {"name": node.name, "methods": [node.name], "attributes": []}
    return {"name": "", "methods": [], "attributes": []}


def _input_spec(text: str) -> dict[str, str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [arg.arg for arg in node.args.args if arg.arg != "self"]
            return {arg: "argument" for arg in args[:8]}
    return {}


def _output_spec(text: str) -> dict[str, str]:
    if "return " in text:
        return {"return": "computed value"}
    return {}


def _key_logic(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if any(term in stripped.lower() for term in ["forward", "project", "token", "loss", "optimizer", "requires_grad", "return"]):
            lines.append(stripped[:160])
        if len(lines) >= 4:
            break
    return " | ".join(lines)


def _training_detail(core_snippets: dict[str, Any]) -> dict[str, Any]:
    snippets = [sn for sn in core_snippets.get("snippets", []) if isinstance(sn, dict) and sn.get("role") == "training_loop"]
    text = "\n".join(str(sn.get("text") or "") for sn in snippets)
    optimizers = re.findall(r"\b(AdamW?|SGD|RMSprop)\b", text)
    return {
        "type": "standard",
        "optimizer": {"name": optimizers[0]} if optimizers else {},
        "scheduler": {},
        "training_loop": {},
        "evidence_refs": _dedupe_strings([eid for sn in snippets for eid in sn.get("evidence_ids", [])]),
    }


def _training_summary(training_detail: dict[str, Any]) -> str:
    optimizer = training_detail.get("optimizer", {}).get("name") if isinstance(training_detail.get("optimizer"), dict) else ""
    return "Detected optimizer: " + optimizer if optimizer else "Training behavior is represented by author-marker aligned code evidence."


def _data_detail(core_snippets: dict[str, Any]) -> dict[str, Any]:
    datasets = []
    for sn in core_snippets.get("snippets", []):
        if not isinstance(sn, dict) or sn.get("role") != "dataset":
            continue
        info = _class_or_function_info(str(sn.get("text") or ""))
        datasets.append({"name": info.get("name") or sn.get("symbol") or "Dataset", "evidence_refs": sn.get("evidence_ids", [])})
    return {"datasets": datasets, "dataloader": {}}


def _losses(core_snippets: dict[str, Any]) -> list[dict[str, Any]]:
    losses = []
    for sn in core_snippets.get("snippets", []):
        if not isinstance(sn, dict) or sn.get("role") != "loss":
            continue
        losses.append({"name": sn.get("symbol") or "loss", "evidence_refs": sn.get("evidence_ids", []), "confidence": 0.6})
    return losses


def _key_insights(
    author_markers: AuthorMarkers,
    modules: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    method_code_alignment: dict[str, Any],
) -> list[dict[str, Any]]:
    insights = []
    if author_markers.method_mainline:
        insights.append({"insight": author_markers.method_mainline, "source": "author_mainline", "evidence_refs": []})
    for module in modules:
        if module.get("is_novel"):
            insights.append({"insight": f"Author marks {module.get('name')} as novel candidate.", "source": "author_module", "evidence_refs": module.get("evidence_refs", [])})
    for claim in method_code_alignment.get("claims", []):
        if claim.get("evidence_ids"):
            insights.append({"insight": claim.get("text"), "source": claim.get("kind"), "evidence_refs": claim.get("evidence_ids", [])})
    return insights[:24]


def _dedupe_evidence_spans(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    seen = set()
    result = []
    for span in spans:
        if span.evidence_id in seen:
            continue
        seen.add(span.evidence_id)
        result.append(span)
    return result


def _repo_structure_hints(files: list[dict[str, Any]]) -> dict[str, Any]:
    def paths_with(*terms: str) -> list[str]:
        return [str(item.get("path")) for item in files if any(term in str(item.get("path", "")).lower() for term in terms)][:20]

    return {
        "entry_candidates": paths_with("main", "train", "run"),
        "model_files_candidates": paths_with("model", "encoder", "decoder", "projector"),
        "training_files_candidates": paths_with("train", "trainer", "optim"),
        "data_pipeline_candidates": paths_with("data", "dataset", "loader"),
    }


def _language_for_ext(ext: str) -> str:
    return {
        ".py": "python",
        ".sh": "shell",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
    }.get(ext, "unknown")


def _kind_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".sh":
        return "script"
    if ext in {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}:
        return "config"
    if "test" in path.name.lower():
        return "test"
    return "source"


def _sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text or "")]


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower() or "item"


def _join_sentences(parts: list[str]) -> str:
    return " ".join(part.strip().rstrip(".") + "." for part in parts if part and part.strip())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_paths(values: list[Path]) -> list[Path]:
    seen = set()
    result = []
    for value in values:
        resolved = value.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        result.append(resolved)
    return result


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
