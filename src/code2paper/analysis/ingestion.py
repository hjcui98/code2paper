"""Minimal Phase 1 ingestion loader.

The loader intentionally stays conservative: it creates schema-valid raw
evidence items with file/line spans, but does not try to infer method claims.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import fnmatch
import hashlib
import io
import json as jsonlib
import os
from pathlib import Path
import tokenize
from typing import Iterable

import yaml

from code2paper.core.schemas import (
    AuthorMarkers,
    AuthorMode,
    EvidenceItem,
    EvidenceStrength,
    ExcludedSource,
    RawEvidencePack,
    ReadmePolicy,
    SourceType,
)


CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".cfg", ".ini"}
SOURCE_SUFFIXES = {".py"}
BASH_SUFFIXES = {".sh"}
NOTEBOOK_SUFFIXES = {".ipynb"}
MAKEFILE_NAMES = {"makefile"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist"}
NOISE_DIRS = {"tests", "test", "docs", "doc", "examples", "example", "notebooks", "eval", "evaluation", "benchmark", "benchmarks"}
GREENPLM_DEFAULT_EXCLUDE_GLOBS = [
    ".codeboarding/**",
    "swark-output/**",
    "pretrained_weight/**",
    "*/llava/eval/*",
    "*/playground/*",
    "*/docs/*",
    "*/tests/*",
    "*/test/*",
]


@dataclass(frozen=True)
class _IngestFilterConfig:
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...]
    max_files: int
    max_comment_items_per_file: int
    max_inline_comment_items_per_file: int


def ingest_project(
    project_root: str | Path,
    *,
    author_markers_path: str | Path | None = None,
    project_id: str | None = None,
    readme_policy: ReadmePolicy | str = ReadmePolicy.EXCLUDE,
) -> RawEvidencePack:
    """Build a RawEvidencePack from project files and optional author markers."""

    root = Path(project_root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"project root does not exist or is not a directory: {root}")

    readme_policy = ReadmePolicy(readme_policy)
    author_markers = _load_author_markers(author_markers_path) if author_markers_path else None
    ignored = set(author_markers.ignore_files if author_markers else [])
    priority_files = list(author_markers.priority_files if author_markers else [])
    filter_config = _load_filter_config(root)

    items: list[EvidenceItem] = []
    counter = _EvidenceCounter()

    if author_markers is not None and author_markers_path is not None:
        path = Path(author_markers_path)
        items.append(
            counter.item(
                source_type=SourceType.AUTHOR,
                path=_display_path(path, root),
                symbol=None,
                line_start=1,
                line_end=_line_count(path),
                content_summary=(
                    "Author markers provide semantic hints for priority files, module roles, "
                    "pipeline steps, claimed novelty, and potential mismatches. "
                    f"Project goal: {author_markers.project_goal}. "
                    f"Paper method goal: {author_markers.paper_method_goal or author_markers.project_goal}. "
                    f"Mainline: {author_markers.method_mainline}."
                ),
                tags=["author_markers", "semantic_hint"],
                confidence=0.7,
            )
        )

    files = _discover_files(root, priority_files=priority_files, ignored=ignored, filter_config=filter_config)
    excluded_sources = _excluded_sources(root, files, ignored, readme_policy)

    for path in files:
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        file_items: list[EvidenceItem] = []
        if suffix in BASH_SUFFIXES:
            file_items = _ingest_bash(path, rel, counter)
        elif path.name.lower() in MAKEFILE_NAMES:
            file_items = _ingest_makefile(path, rel, counter)
        elif suffix in NOTEBOOK_SUFFIXES:
            file_items = _ingest_notebook_metadata(path, rel, counter)
        elif suffix in CONFIG_SUFFIXES:
            file_items = [_ingest_config(path, rel, counter), *_ingest_config_comments(path, rel, counter)]
        elif suffix in SOURCE_SUFFIXES:
            file_items = _ingest_python_source(path, rel, counter)
        items.extend(_trim_comment_items(file_items, filter_config=filter_config))

    return RawEvidencePack(
        project_id=project_id or root.name.replace("-", "_"),
        project_root=str(root),
        author_mode=AuthorMode.ENHANCED if author_markers else AuthorMode.NONE,
        author_confirmation_required=author_markers is None,
        readme_policy=readme_policy,
        evidence_items=items,
        excluded_sources=excluded_sources,
    )


def _load_author_markers(path: str | Path) -> AuthorMarkers:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AuthorMarkers.model_validate(payload)


def _load_filter_config(root: Path) -> _IngestFilterConfig:
    rel_path = str(root).lower()
    is_greenplm = "greenplm" in rel_path
    include_globs = tuple(_csv_env("CODE2PAPER_INGEST_INCLUDE_GLOBS"))
    exclude_globs = list(_csv_env("CODE2PAPER_INGEST_EXCLUDE_GLOBS"))
    if is_greenplm:
        exclude_globs.extend(GREENPLM_DEFAULT_EXCLUDE_GLOBS)
    max_files = _int_env("CODE2PAPER_MAX_INGEST_FILES", 0 if not is_greenplm else 900)
    max_comment_items_per_file = _int_env("CODE2PAPER_MAX_COMMENT_ITEMS_PER_FILE", 0 if not is_greenplm else 28)
    max_inline_comment_items_per_file = _int_env("CODE2PAPER_MAX_INLINE_COMMENT_ITEMS_PER_FILE", 0 if not is_greenplm else 12)
    return _IngestFilterConfig(
        include_globs=include_globs,
        exclude_globs=tuple(_dedupe_strings(exclude_globs)),
        max_files=max_files,
        max_comment_items_per_file=max_comment_items_per_file,
        max_inline_comment_items_per_file=max_inline_comment_items_per_file,
    )


def _csv_env(name: str) -> list[str]:
    value = os.environ.get(name, "")
    return [part.strip() for part in value.split(",") if part.strip()]


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _dedupe_strings(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _discover_files(
    root: Path,
    *,
    priority_files: list[str],
    ignored: set[str],
    filter_config: _IngestFilterConfig,
) -> list[Path]:
    priority: list[Path] = []
    seen: set[Path] = set()
    for rel in priority_files:
        path = (root / rel).resolve()
        if path.exists() and path.is_file() and _is_ingestable(path) and not _is_ignored(path, root, ignored):
            if _is_filtered(path, root, filter_config):
                continue
            priority.append(path)
            seen.add(path)

    rest: list[Path] = []
    apply_noise_filter = bool(filter_config.exclude_globs or filter_config.max_files > 0 or filter_config.include_globs)
    for path in root.rglob("*"):
        if not path.is_file() or path in seen:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if apply_noise_filter and any(part.lower() in NOISE_DIRS for part in path.relative_to(root).parts):
            continue
        if _is_ignored(path, root, ignored):
            continue
        if _is_filtered(path, root, filter_config):
            continue
        if _is_ingestable(path):
            rest.append(path)
    if apply_noise_filter:
        ordered_rest = sorted(rest, key=lambda path: _file_rank(path.relative_to(root).as_posix()))
    else:
        ordered_rest = sorted(rest)
    files = priority + ordered_rest
    if filter_config.max_files > 0:
        files = files[: filter_config.max_files]
    return files


def _is_ingestable(path: Path) -> bool:
    return path.suffix.lower() in (CONFIG_SUFFIXES | SOURCE_SUFFIXES | BASH_SUFFIXES | NOTEBOOK_SUFFIXES) or path.name.lower() in MAKEFILE_NAMES


def _is_ignored(path: Path, root: Path, ignored: set[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    return (
        rel in ignored
        or path.name in ignored
        or any(fnmatch.fnmatch(rel, pattern) for pattern in ignored)
    )


def _is_filtered(path: Path, root: Path, filter_config: _IngestFilterConfig) -> bool:
    rel = path.relative_to(root).as_posix()
    if filter_config.include_globs and not any(fnmatch.fnmatch(rel, pattern) for pattern in filter_config.include_globs):
        return True
    if filter_config.exclude_globs and any(fnmatch.fnmatch(rel, pattern) for pattern in filter_config.exclude_globs):
        return True
    return False


def _file_rank(rel: str) -> tuple[int, int, str]:
    lowered = rel.lower()
    core_tokens = ("model", "attention", "encoder", "decoder", "forward", "loss", "train", "optim", "arch", "main")
    noise_tokens = ("eval", "test", "docs", "example", "notebook", "benchmark")
    core_score = 0 if any(token in lowered for token in core_tokens) else 1
    noise_score = 1 if any(token in lowered for token in noise_tokens) else 0
    return (noise_score, core_score, lowered)


def _excluded_sources(
    root: Path,
    included_files: list[Path],
    ignored: set[str],
    readme_policy: ReadmePolicy,
) -> list[ExcludedSource]:
    excluded: list[ExcludedSource] = []
    included = {path.resolve() for path in included_files}
    if readme_policy == ReadmePolicy.EXCLUDE:
        for path in root.rglob("README*"):
            if path.is_file() and path.resolve() not in included:
                excluded.append(
                    ExcludedSource(
                        path=path.relative_to(root).as_posix(),
                        reason="excluded from main evidence chain",
                    )
                )
    for rel in sorted(ignored):
        candidate = root / rel
        if candidate.exists() and candidate.is_file():
            excluded.append(ExcludedSource(path=rel, reason="ignored by author markers"))
    unique: dict[str, ExcludedSource] = {}
    for source in excluded:
        unique[source.path] = source
    return list(unique.values())


def _trim_comment_items(items: list[EvidenceItem], *, filter_config: _IngestFilterConfig) -> list[EvidenceItem]:
    max_comment = filter_config.max_comment_items_per_file
    max_inline = filter_config.max_inline_comment_items_per_file
    if max_comment <= 0 and max_inline <= 0:
        return items
    comment_items = [item for item in items if item.source_type == SourceType.COMMENT]
    if not comment_items:
        return items
    non_comment_items = [item for item in items if item.source_type != SourceType.COMMENT]
    inline = [item for item in comment_items if "inline_comment" in item.tags]
    non_inline = [item for item in comment_items if "inline_comment" not in item.tags]
    selected_non_inline = _pick_high_signal_comments(non_inline, limit=max_comment if max_comment > 0 else len(non_inline))
    inline_limit = max_inline if max_inline > 0 else len(inline)
    selected_inline = _pick_high_signal_comments(inline, limit=inline_limit)
    selected = selected_non_inline + selected_inline
    selected_ids = {item.evidence_id for item in selected}
    return [item for item in items if item.source_type != SourceType.COMMENT or item.evidence_id in selected_ids]


def _pick_high_signal_comments(items: list[EvidenceItem], *, limit: int) -> list[EvidenceItem]:
    if limit <= 0:
        return []
    if len(items) <= limit:
        return items
    keywords = ("method", "pipeline", "stage", "loss", "attention", "forward", "algorithm", "@method", "@paper")
    ranked = sorted(
        items,
        key=lambda item: (
            0 if "docstring" in item.tags else 1,
            0 if any(token in item.content_summary.lower() for token in keywords) else 1,
            item.line_start or 0,
        ),
    )
    return ranked[:limit]


def _ingest_bash(path: Path, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    lines = _read_lines(path)
    command_spans = _bash_command_spans(lines)
    if not command_spans:
        return [
            counter.item(
                source_type=SourceType.BASH,
                path=rel,
                symbol=None,
                line_start=1,
                line_end=max(1, len(lines)),
                content_summary="Shell script with no detected executable command block.",
                tags=["bash"],
                confidence=0.55,
            )
        ]

    items = []
    for start, end, command in command_spans:
        tags = ["bash"]
        if "python" in command:
            tags.append("entrypoint")
        if "train" in command:
            tags.append("train")
        if "$" in command or "${" in command:
            tags.append("shell_override")
        items.append(
            counter.item(
                source_type=SourceType.BASH,
                path=rel,
                symbol=None,
                line_start=start,
                line_end=end,
                content_summary=_summarize_bash_command(command),
                tags=tags,
                shell_command_segment=command,
                confidence=0.9,
            )
        )

    for start, end, text in _hash_comment_blocks(lines):
        items.append(
            counter.item(
                source_type=SourceType.COMMENT,
                path=rel,
                symbol=None,
                line_start=start,
                line_end=end,
                content_summary=f"Shell comment hint: {text}",
                tags=["comment", "soft_hint"],
                confidence=0.45,
            )
        )
    return items


def _bash_command_spans(lines: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    current: list[str] = []
    start: int | None = None
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if start is None:
            start = index
        current.append(stripped.rstrip("\\").strip())
        if not stripped.endswith("\\"):
            command = " ".join(part for part in current if part)
            spans.append((start, index, command))
            current = []
            start = None
    if current and start is not None:
        spans.append((start, len(lines), " ".join(current)))
    return spans


def _hash_comment_blocks(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    start: int | None = None
    comments: list[str] = []
    previous_line = 0
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            if start is None or previous_line != index - 1:
                if comments:
                    yield start or index, previous_line, " ".join(comments)
                start = index
                comments = []
            comments.append(stripped.lstrip("#").strip())
            previous_line = index
            continue
        if comments:
            yield start or index, previous_line, " ".join(comments)
            comments = []
            start = None
            previous_line = 0
    if comments:
        yield start or 1, previous_line or len(lines), " ".join(comments)


def _ingest_config(path: Path, rel: str, counter: "_EvidenceCounter") -> EvidenceItem:
    return counter.item(
        source_type=SourceType.CONFIG,
        path=rel,
        symbol=None,
        line_start=1,
        line_end=max(1, _line_count(path)),
        content_summary="Configuration file that may define runtime, model, data, or experiment settings.",
        tags=["config"],
        config_key=None,
        confidence=0.75,
    )


def _ingest_makefile(path: Path, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    lines = _read_lines(path)
    items: list[EvidenceItem] = [
        counter.item(
            source_type=SourceType.BASH,
            path=rel,
            symbol=None,
            line_start=1,
            line_end=max(1, len(lines)),
            content_summary="Makefile runbook with target-based execution flow hints.",
            tags=["bash", "makefile", "entrypoint"],
            confidence=0.72,
        )
    ]
    for start, end, text in _hash_comment_blocks(lines):
        items.append(
            counter.item(
                source_type=SourceType.COMMENT,
                path=rel,
                symbol=None,
                line_start=start,
                line_end=end,
                content_summary=f"Makefile comment hint: {text}",
                tags=["comment", "makefile_comment", "soft_hint"],
                confidence=0.4,
            )
        )
    return items


def _ingest_notebook_metadata(path: Path, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    try:
        payload = jsonlib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except jsonlib.JSONDecodeError:
        return [
            counter.item(
                source_type=SourceType.CONFIG,
                path=rel,
                symbol=None,
                line_start=1,
                line_end=max(1, _line_count(path)),
                content_summary="Notebook file present but metadata could not be parsed.",
                tags=["config", "notebook", "parse_error"],
                confidence=0.35,
            )
        ]
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    kernelspec = metadata.get("kernelspec", {}) if isinstance(metadata, dict) else {}
    language_info = metadata.get("language_info", {}) if isinstance(metadata, dict) else {}
    summary = "Notebook metadata"
    kernel_name = kernelspec.get("name") if isinstance(kernelspec, dict) else ""
    language = language_info.get("name") if isinstance(language_info, dict) else ""
    details = [piece for piece in [kernel_name, language] if piece]
    if details:
        summary = f"Notebook metadata with kernel/language hints: {', '.join(details)}."
    else:
        summary = "Notebook metadata file for execution environment hints."
    return [
        counter.item(
            source_type=SourceType.CONFIG,
            path=rel,
            symbol=None,
            line_start=1,
            line_end=1,
            content_summary=summary,
            tags=["config", "notebook", "metadata"],
            confidence=0.6,
        )
    ]


def _ingest_config_comments(path: Path, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for start, end, text in _hash_or_semicolon_comment_blocks(_read_lines(path)):
        if not text:
            continue
        items.append(
            counter.item(
                source_type=SourceType.COMMENT,
                path=rel,
                symbol=None,
                line_start=start,
                line_end=end,
                content_summary=f"Config comment hint: {text}",
                tags=["comment", "config_comment", "soft_hint"],
                confidence=0.4,
            )
        )
    return items


def _hash_or_semicolon_comment_blocks(lines: list[str]) -> Iterable[tuple[int, int, str]]:
    start: int | None = None
    comments: list[str] = []
    previous_line = 0
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("#") or stripped.startswith(";"):
            if start is None or previous_line != index - 1:
                if comments:
                    yield start or index, previous_line, " ".join(comments)
                start = index
                comments = []
            comments.append(stripped.lstrip("#;").strip())
            previous_line = index
            continue
        if comments:
            yield start or index, previous_line, " ".join(comments)
            comments = []
            start = None
            previous_line = 0
    if comments:
        yield start or 1, previous_line or len(lines), " ".join(comments)


def _ingest_python_source(path: Path, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    items: list[EvidenceItem] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [
            counter.item(
                source_type=SourceType.SOURCE,
                path=rel,
                symbol=None,
                line_start=1,
                line_end=max(1, len(lines)),
                content_summary="Python source file could not be parsed by ast; retained as file-level evidence.",
                tags=["source", "parse_error"],
                confidence=0.45,
            )
        ]

    module_doc = ast.get_docstring(tree)
    if module_doc:
        items.append(
            counter.item(
                source_type=SourceType.COMMENT,
                path=rel,
                symbol=None,
                line_start=1,
                line_end=_module_doc_end_line(tree),
                content_summary=f"Module docstring hint: {_single_line(module_doc)}",
                tags=["comment", "docstring", "soft_hint"],
                confidence=0.55,
            )
        )
    items.extend(_python_inline_comment_items(text, rel, counter))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            items.append(_python_symbol_item(path, rel, node, counter))
            doc = ast.get_docstring(node)
            if doc:
                items.append(
                    counter.item(
                        source_type=SourceType.COMMENT,
                        path=rel,
                        symbol=node.name,
                        line_start=node.lineno,
                        line_end=min(getattr(node, "end_lineno", node.lineno), node.lineno + 3),
                        content_summary=f"Docstring hint for {node.name}: {_single_line(doc)}",
                        tags=["comment", "docstring", "soft_hint"],
                        confidence=0.55,
                    )
                )
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    items.append(
                        _python_method_symbol_item(
                            path=path,
                            rel=rel,
                            class_node=node,
                            method_node=child,
                            counter=counter,
                        )
                    )
                    doc = ast.get_docstring(child)
                    if doc:
                        items.append(
                            counter.item(
                                source_type=SourceType.COMMENT,
                                path=rel,
                                symbol=f"{node.name}.{child.name}",
                                line_start=child.lineno,
                                line_end=min(getattr(child, "end_lineno", child.lineno), child.lineno + 3),
                                content_summary=f"Docstring hint for {node.name}.{child.name}: {_single_line(doc)}",
                                tags=["comment", "docstring", "soft_hint"],
                                confidence=0.55,
                            )
                        )
    items.extend(_python_call_chain_items(tree, rel, counter))
    return items


def _python_inline_comment_items(text: str, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    except tokenize.TokenError:
        return items
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        comment_text = token.string.lstrip("#").strip()
        if not comment_text or comment_text.lower().startswith(("type:", "noqa", "fmt:")):
            continue
        items.append(
            counter.item(
                source_type=SourceType.COMMENT,
                path=rel,
                symbol=None,
                line_start=token.start[0],
                line_end=token.end[0],
                content_summary=f"Python inline comment hint: {comment_text}",
                tags=["comment", "inline_comment", "soft_hint"],
                confidence=0.4,
            )
        )
    return items


def _python_symbol_item(
    path: Path,
    rel: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    counter: "_EvidenceCounter",
) -> EvidenceItem:
    tags = ["source", "class" if isinstance(node, ast.ClassDef) else "function"]
    lowered = f"{rel} {node.name}".lower()
    for keyword, tag in (
        ("train", "train"),
        ("preprocess", "preprocess"),
        ("optim", "optimization"),
        ("attention", "attention"),
        ("layer", "model"),
        ("model", "model"),
        ("dataloader", "data"),
    ):
        if keyword in lowered:
            tags.append(tag)
    return counter.item(
        source_type=SourceType.SOURCE,
        path=rel,
        symbol=node.name,
        line_start=node.lineno,
        line_end=getattr(node, "end_lineno", node.lineno),
        content_summary=_summarize_python_node(path, node),
        tags=sorted(set(tags)),
        confidence=0.82 if isinstance(node, ast.ClassDef) else 0.78,
    )


def _python_method_symbol_item(
    *,
    path: Path,
    rel: str,
    class_node: ast.ClassDef,
    method_node: ast.FunctionDef | ast.AsyncFunctionDef,
    counter: "_EvidenceCounter",
) -> EvidenceItem:
    symbol = f"{class_node.name}.{method_node.name}"
    tags = ["source", "function", "method", "class_member"]
    lowered = f"{rel} {symbol}".lower()
    for keyword, tag in (
        ("train", "train"),
        ("preprocess", "preprocess"),
        ("optim", "optimization"),
        ("attention", "attention"),
        ("layer", "model"),
        ("model", "model"),
        ("dataloader", "data"),
        ("forward", "model"),
        ("decode", "model"),
        ("encode", "model"),
    ):
        if keyword in lowered:
            tags.append(tag)
    args = [arg.arg for arg in method_node.args.args]
    arg_preview = ", ".join(args[:4]) if args else "no positional args"
    return counter.item(
        source_type=SourceType.SOURCE,
        path=rel,
        symbol=symbol,
        line_start=method_node.lineno,
        line_end=getattr(method_node, "end_lineno", method_node.lineno),
        content_summary=f"Defines method {symbol} with args ({arg_preview}).",
        tags=sorted(set(tags)),
        confidence=0.8,
    )


def _python_call_chain_items(tree: ast.Module, rel: str, counter: "_EvidenceCounter") -> list[EvidenceItem]:
    call_items: list[EvidenceItem] = []
    seen: set[tuple[str, str, int]] = set()
    for owner, function in _iter_scoped_functions(tree):
        owner_symbol = f"{owner}.{function.name}" if owner else function.name
        call_names = sorted(set(_called_symbol_names(function)))
        if not call_names:
            continue
        for call_name in call_names[:12]:
            key = (owner_symbol, call_name, function.lineno)
            if key in seen:
                continue
            seen.add(key)
            call_items.append(
                counter.item(
                    source_type=SourceType.SOURCE,
                    path=rel,
                    symbol=f"{owner_symbol}->{call_name}",
                    line_start=function.lineno,
                    line_end=min(getattr(function, "end_lineno", function.lineno), function.lineno + 2),
                    content_summary=f"Call chain evidence: {owner_symbol} calls {call_name}.",
                    tags=["source", "call_chain", "method_flow"],
                    confidence=0.66,
                )
            )
    return call_items


def _iter_scoped_functions(
    tree: ast.Module,
) -> Iterable[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield "", node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name, child


def _called_symbol_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names: list[str] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.append(node.func.attr)
    return names


def _summarize_python_node(path: Path, node: ast.AST) -> str:
    name = getattr(node, "name", "<anonymous>")
    if isinstance(node, ast.ClassDef):
        bases = [getattr(base, "id", getattr(base, "attr", "")) for base in node.bases]
        base_text = f" inheriting from {', '.join(filter(None, bases))}" if bases else ""
        return f"Defines class {name}{base_text}."
    return f"Defines function {name}."


def _summarize_bash_command(command: str) -> str:
    cleaned = " ".join(command.split())
    if len(cleaned) > 220:
        cleaned = cleaned[:217] + "..."
    return f"Shell command: {cleaned}"


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _line_count(path: Path) -> int:
    return len(_read_lines(path))


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _single_line(text: str) -> str:
    return " ".join(text.strip().split())


def _module_doc_end_line(tree: ast.Module) -> int:
    first = tree.body[0] if tree.body else None
    return getattr(first, "end_lineno", 1)


class _EvidenceCounter:
    def __init__(self) -> None:
        self._next_id = 1

    def item(
        self,
        *,
        source_type: SourceType,
        path: str,
        symbol: str | None,
        line_start: int | None,
        line_end: int | None,
        content_summary: str,
        tags: list[str],
        confidence: float,
        config_key: str | None = None,
        shell_command_segment: str | None = None,
    ) -> EvidenceItem:
        evidence_id = f"E{self._next_id}"
        self._next_id += 1
        evidence_strength = _evidence_strength(source_type)
        return EvidenceItem(
            evidence_id=evidence_id,
            source_type=source_type,
            path=path,
            symbol=symbol,
            line_start=line_start,
            line_end=line_end,
            config_key=config_key,
            shell_command_segment=shell_command_segment,
            excerpt_hash=_hash_text(content_summary),
            evidence_strength=evidence_strength,
            content_summary=content_summary,
            tags=tags,
            confidence=confidence,
        )


def _hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_strength(source_type: SourceType) -> EvidenceStrength:
    if source_type == SourceType.COMMENT:
        return EvidenceStrength.SOFT
    if source_type == SourceType.AUTHOR:
        return EvidenceStrength.SEMANTIC_HINT
    return EvidenceStrength.HARD
