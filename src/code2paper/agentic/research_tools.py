"""R1.1 fine-grained LangChain research tools.

Implements the first four minimal read-only research tools defined in
``docs/agentic_method_quality_next_execution_plan_2026-07-19.md`` R1.1:

- ``find_entrypoints``: locate repository entrypoints (main.py, train.py,
  shell scripts, Makefile/Dockerfile) within a snapshot scope;
- ``search_symbols``: query the deterministic symbol index for matching
  classes/functions;
- ``read_symbol``: read the exact source span of a specific symbol;
- ``find_references``: find imports and usages of a symbol across the
  snapshot.

Every tool:

- takes a :class:`ResearchToolCallV1` (which already binds ``repo_snapshot_id``,
  ``obligation_id``, ``goal``, ``path_scope``, ``top_k`` / ``depth`` /
  ``node_budget``);
- returns a :class:`ResearchObservationV1` with ``status``,
  ``source_authority``, ``result_refs`` / ``exact_span_ids``,
  ``diagnostics`` and stable input/output digests;
- distinguishes ``success`` / ``success_empty`` / ``scope_exhausted`` /
  ``truncated`` / ``parse_failed`` / ``invalid_request`` so the supervisor
  cannot confuse an empty result with a tool error;
- refuses snapshot-external paths and never produces a hard-evidence
  ``result_ref`` for hint-only files (R1.4 security mutations).

The functions in this module are pure: they take a
:class:`ResearchToolContext` (snapshot + optional cached symbol index) and a
``ResearchToolCallV1`` and return a ``ResearchObservationV1``.  LangChain
``StructuredTool`` wrappers and the manifest writer ship in
``research_tool_manifest`` (R1.3).
"""

from __future__ import annotations

import ast
import hashlib
import re
import shlex
from pathlib import PurePosixPath
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.agentic.research_models import (
    ResearchObservationDiagnosticsV1,
    ResearchObservationV1,
    ResearchObservationStatus,
    ResearchToolCallV1,
    ToolKind,
    make_observation,
)
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport, build_symbol_index
from code2paper.agentic.source_authority import (
    SourceAuthorityV1,
    classify_source_authority,
)


# ---------------------------------------------------------------------------
# Tool names and kinds
# ---------------------------------------------------------------------------


RESEARCH_TOOL_NAMES: tuple[str, ...] = (
    "find_entrypoints",
    "search_symbols",
    "read_symbol",
    "find_references",
)


RESEARCH_TOOL_KINDS: dict[str, ToolKind] = {
    "find_entrypoints": "symbol_search",
    "search_symbols": "symbol_search",
    "read_symbol": "code_read",
    "find_references": "call_trace",
}


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


class ResearchToolContext(BaseModel):
    """Frozen execution context shared by all research tools.

    The context bundles the repo snapshot (for path validation and authority
    classification) with an optional cached symbol index.  Tools never read
    the working tree directly: every file access goes through the snapshot so
    a checkpoint resume cannot accidentally read source code that drifted
    after freeze time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    repo_snapshot: RepoSnapshot
    symbol_index: SymbolIndexReport | None = None
    max_indexed_files: int = 120
    max_indexed_symbols: int = 200

    def resolve_snapshot_path(self, candidate: str) -> str | None:
        """Return the snapshot-relative path if ``candidate`` is in-scope.

        Returns ``None`` for snapshot-external paths so tools can raise an
        ``invalid_request`` observation instead of silently reading outside
        the frozen tree.
        """

        return _resolve_snapshot_path(self.repo_snapshot, candidate)

    def ensure_symbol_index(self) -> SymbolIndexReport:
        """Return the cached symbol index, building it lazily if needed."""

        if self.symbol_index is not None:
            return self.symbol_index
        # Build a minimal plan-less symbol index.  ``build_symbol_index``
        # accepts an empty plan and still walks the snapshot files.
        from code2paper.agentic.retrieval import AgenticRetrievalPlan

        plan = AgenticRetrievalPlan()
        index = build_symbol_index(
            project_root=self.repo_snapshot.project_root,
            plan=plan,
            max_files=self.max_indexed_files,
            max_candidates=self.max_indexed_symbols,
        )
        # Context is frozen; callers that want to reuse the index should
        # construct a new context via model_copy(update={"symbol_index": index}).
        return index


# ---------------------------------------------------------------------------
# Per-tool input schemas (used by LangChain StructuredTool in R1.3)
# ---------------------------------------------------------------------------


class _ResearchToolInputBase(BaseModel):
    """Common fields every research tool input must carry (R1.2)."""

    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    obligation_id: str
    goal: str
    repo_snapshot_id: str
    path_scope: tuple[str, ...] = Field(default_factory=tuple)
    top_k: int = 10
    depth: int = 0
    node_budget: int = 0

    @field_validator("tool_call_id", "obligation_id", "goal", "repo_snapshot_id")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("top_k", "depth", "node_budget")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("budget fields must be nonnegative")
        return value


class FindEntrypointsInput(_ResearchToolInputBase):
    """Input schema for ``find_entrypoints``."""

    entrypoint_kinds: tuple[str, ...] = Field(default_factory=tuple)
    include_shell: bool = True
    include_config: bool = True


class SearchSymbolsInput(_ResearchToolInputBase):
    """Input schema for ``search_symbols``."""

    query: str
    kind_filter: tuple[str, ...] = Field(default_factory=tuple)
    regex: bool = False

    @field_validator("query")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


class ReadSymbolInput(_ResearchToolInputBase):
    """Input schema for ``read_symbol``."""

    path: str
    symbol: str
    context_lines: int = 0

    @field_validator("path", "symbol")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("context_lines")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("context_lines must be nonnegative")
        return value


class FindReferencesInput(_ResearchToolInputBase):
    """Input schema for ``find_references``."""

    symbol: str
    import_only: bool = False

    @field_validator("symbol")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("symbol must not be empty")
        return value


# ---------------------------------------------------------------------------
# find_entrypoints
# ---------------------------------------------------------------------------


_ENTRYPOINT_FILENAMES: tuple[str, ...] = (
    "main.py", "__main__.py", "app.py", "train.py", "eval.py",
    "infer.py", "run.py", "server.py", "cli.py", "predict.py",
    "demo.py", "serve.py",
)

_ENTRYPOINT_SHELL_MARKERS: tuple[str, ...] = (
    "python", "python3", "torchrun", "accelerate", "deepspeed",
    "sbatch", "srun", "bash", "sh ", "make ",
)


def find_entrypoints(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Locate repository entrypoints within ``path_scope``."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    kinds = _arg_value(tool_call, "entrypoint_kinds", default=()) or ()
    include_shell = bool(_arg_value(tool_call, "include_shell", default=True))
    include_config = bool(_arg_value(tool_call, "include_config", default=True))
    top_k = tool_call.top_k or 20

    matched: list[tuple[str, SourceAuthorityV1]] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        authority = classify_source_authority(rel_path)
        kind = _classify_entrypoint(rel_path, authority, include_shell, include_config)
        if kind is None:
            continue
        if kinds and kind not in kinds:
            continue
        matched.append((rel_path, authority))
        if len(matched) >= top_k:
            truncated = True
            break

    if not matched:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"scope={scope_paths or ('.',)}"),
            ),
        )

    # Weakest authority among matches is recorded so packet validators can
    # refuse hint-only anchors without re-classifying every span.
    weakest = _weakest_authority([authority for _, authority in matched])
    result_refs = tuple(f"entrypoint:{path}" for path, _ in matched)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(matched),
            truncated=truncated,
            notes=(f"matched={len(matched)}", f"scope={scope_paths or ('.',)}"),
        ),
    )


# ---------------------------------------------------------------------------
# search_symbols
# ---------------------------------------------------------------------------


def search_symbols(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Query the deterministic symbol index for matching symbols."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    query = str(_arg_value(tool_call, "query", default="") or "")
    if not query.strip():
        return _invalid_request(tool_call, "query must not be empty")
    kind_filter = tuple(_arg_value(tool_call, "kind_filter", default=()) or ())
    use_regex = bool(_arg_value(tool_call, "regex", default=False))
    top_k = tool_call.top_k or 10

    index = ctx.ensure_symbol_index()
    candidates = [
        entry
        for entry in index.candidates
        if _symbol_matches(entry, query, kind_filter, use_regex, scope_paths)
    ]
    if not candidates:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"query={query}"),
            ),
        )

    truncated = len(candidates) > top_k
    selected = candidates[:top_k]
    weakest = _weakest_authority(
        [classify_source_authority(entry.path) for entry in selected]
    )
    result_refs = tuple(
        f"symbol:{entry.path}:{entry.symbol}:{entry.start_line}" for entry in selected
    )
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(selected),
            truncated=truncated,
            ambiguous=_candidates_ambiguous(selected),
            notes=(f"total_matches={len(candidates)}", f"query={query}"),
        ),
    )


# ---------------------------------------------------------------------------
# read_symbol
# ---------------------------------------------------------------------------


def read_symbol(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Read the exact source span of a specific symbol."""

    path = str(_arg_value(tool_call, "path", default="") or "")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    if not path.strip() or not symbol.strip():
        return _invalid_request(tool_call, "path and symbol must not be empty")
    rel_path = ctx.resolve_snapshot_path(path)
    if rel_path is None:
        return _invalid_request(tool_call, f"path is outside repo snapshot: {path}")
    context_lines = int(_arg_value(tool_call, "context_lines", default=0) or 0)

    file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=read_error,
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
        )
    if not rel_path.endswith(".py"):
        # Non-Python files cannot be parsed for symbol spans; expose the
        # whole file as a single span so the supervisor can still read it.
        line_count = file_text.count("\n") + 1
        authority = classify_source_authority(rel_path)
        return make_observation(
            tool_call=tool_call,
            status="success",
            source_authority=authority,
            exact_span_ids=(f"span:{rel_path}:1:{line_count}",),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=1,
                notes=("non_python_file", f"path={rel_path}"),
            ),
        )

    try:
        tree = ast.parse(file_text)
    except SyntaxError as exc:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=f"SyntaxError: {exc.msg} (line {exc.lineno or 0})",
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
        )

    span = _locate_symbol_span(tree, symbol)
    if span is None:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("symbol_not_found", f"symbol={symbol}", f"path={rel_path}"),
            ),
        )

    start_line, end_line = span
    if context_lines:
        start_line = max(1, start_line - context_lines)
        end_line = end_line + context_lines
    authority = classify_source_authority(rel_path)
    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority=authority,
        exact_span_ids=(f"span:{rel_path}:{start_line}:{end_line}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"symbol={symbol}", f"lines={start_line}-{end_line}"),
        ),
    )


# ---------------------------------------------------------------------------
# find_references
# ---------------------------------------------------------------------------


def find_references(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Find imports and usages of ``symbol`` across the snapshot."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    if not symbol.strip():
        return _invalid_request(tool_call, "symbol must not be empty")
    import_only = bool(_arg_value(tool_call, "import_only", default=False))
    top_k = tool_call.top_k or 20

    symbol_name = symbol.split(".")[-1]
    references: list[tuple[str, int, SourceAuthorityV1]] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        if not rel_path.endswith(".py"):
            continue
        file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
        if read_error is not None:
            continue
        try:
            tree = ast.parse(file_text)
        except SyntaxError:
            continue
        authority = classify_source_authority(rel_path)
        for line_no in _find_symbol_usages(tree, symbol_name, import_only):
            references.append((rel_path, line_no, authority))
            if len(references) >= top_k:
                truncated = True
                break
        if truncated:
            break

    if not references:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"symbol={symbol_name}"),
            ),
        )

    weakest = _weakest_authority([authority for _, _, authority in references])
    result_refs = tuple(
        f"ref:{path}:{line_no}" for path, line_no, _ in references
    )
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(references),
            truncated=truncated,
            ambiguous=_references_ambiguous(references, symbol_name),
            notes=(f"symbol={symbol_name}", f"matches={len(references)}"),
        ),
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


RESEARCH_TOOL_EXECUTORS: dict[str, Any] = {
    "find_entrypoints": find_entrypoints,
    "search_symbols": search_symbols,
    "read_symbol": read_symbol,
    "find_references": find_references,
}


RESEARCH_TOOL_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "find_entrypoints": FindEntrypointsInput,
    "search_symbols": SearchSymbolsInput,
    "read_symbol": ReadSymbolInput,
    "find_references": FindReferencesInput,
}


def execute_research_tool(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Dispatch a ``ResearchToolCallV1`` to the registered executor.

    Used by the R3 research tool node.  Unknown tool names return an
    ``invalid_request`` observation so the supervisor can route to a
    deterministic fallback without raising.
    """

    executor = RESEARCH_TOOL_EXECUTORS.get(tool_call.tool_name)
    if executor is None:
        return _invalid_request(tool_call, f"unknown tool: {tool_call.tool_name}")
    if tool_call.repo_snapshot_id != ctx.repo_snapshot.snapshot_id:
        return _invalid_request(
            tool_call,
            f"tool_call.repo_snapshot_id mismatch: {tool_call.repo_snapshot_id}",
        )
    return executor(ctx, tool_call)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _arg_value(tool_call: ResearchToolCallV1, key: str, *, default: Any = None) -> Any:
    return dict(tool_call.arguments or {}).get(key, default)


def _invalid_request(tool_call: ResearchToolCallV1, message: str) -> ResearchObservationV1:
    return make_observation(
        tool_call=tool_call,
        status="invalid_request",
        source_authority="executable_hard",
        error_message=message,
        diagnostics=ResearchObservationDiagnosticsV1(notes=("invalid_request",)),
    )


def _scope_paths(ctx: ResearchToolContext, tool_call: ResearchToolCallV1) -> tuple[str, ...] | None:
    """Normalize ``path_scope`` to snapshot-relative paths.

    Returns ``None`` if any path is outside the snapshot so the caller can
    fail closed with an ``invalid_request`` observation.
    """

    raw_scope = tuple(tool_call.path_scope or ())
    if not raw_scope:
        return ()
    normalized: list[str] = []
    for candidate in raw_scope:
        rel = ctx.resolve_snapshot_path(candidate)
        if rel is None:
            return None
        normalized.append(rel)
    return tuple(normalized)


def _resolve_snapshot_path(snapshot: RepoSnapshot, candidate: str) -> str | None:
    raw = (candidate or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("\\", "/").lstrip("./").lstrip("/")
    known = {file.path for file in snapshot.included_files}
    if cleaned in known:
        return cleaned
    # Allow directory prefixes (e.g. "src/" matches "src/main.py").
    if not cleaned.endswith("/"):
        cleaned_dir = cleaned + "/"
    else:
        cleaned_dir = cleaned
    if any(file.path == cleaned or file.path.startswith(cleaned_dir) for file in snapshot.included_files):
        return cleaned
    return None


def _iter_snapshot_files(snapshot: RepoSnapshot, scope_paths: tuple[str, ...]) -> Iterable[str]:
    if not scope_paths:
        for file in snapshot.included_files:
            yield file.path
        return
    for file in snapshot.included_files:
        for scope in scope_paths:
            if file.path == scope or file.path.startswith(scope.rstrip("/") + "/"):
                yield file.path
                break


def _read_snapshot_file(snapshot: RepoSnapshot, rel_path: str) -> tuple[str, str | None]:
    """Read a file from the snapshot's project root.

    Returns ``(text, error_message)``.  ``error_message`` is ``None`` on
    success.  Tools never follow symlinks outside the snapshot.
    """

    from pathlib import Path

    root = Path(snapshot.project_root)
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return "", f"path escapes repo root: {rel_path}"
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return "", f"read_failed: {exc.__class__.__name__}"
    return text, None


def _classify_entrypoint(
    rel_path: str,
    authority: SourceAuthorityV1,
    include_shell: bool,
    include_config: bool,
) -> str | None:
    name = PurePosixPath(rel_path).name
    lowered = rel_path.lower()
    if name in _ENTRYPOINT_FILENAMES:
        return "python_entrypoint"
    if include_shell and (lowered.endswith((".sh", ".bash", ".zsh", ".slurm", ".sbatch"))):
        return "shell_entrypoint"
    if include_shell and name.lower() in {"makefile", "dockerfile"}:
        return "build_entrypoint"
    if include_config and lowered.endswith((".yaml", ".yml")) and name.lower() in {
        "train.yaml", "eval.yaml", "infer.yaml", "config.yaml", "server.yaml",
    }:
        return "config_entrypoint"
    return None


def _symbol_matches(
    entry: SymbolIndexEntry,
    query: str,
    kind_filter: tuple[str, ...],
    use_regex: bool,
    scope_paths: tuple[str, ...],
) -> bool:
    if scope_paths and not any(
        entry.path == scope or entry.path.startswith(scope.rstrip("/") + "/")
        for scope in scope_paths
    ):
        return False
    if kind_filter and entry.kind not in kind_filter:
        return False
    if use_regex:
        try:
            return bool(re.search(query, entry.symbol))
        except re.error:
            return False
    return query.lower() in entry.symbol.lower()


def _locate_symbol_span(tree: ast.AST, symbol: str) -> tuple[int, int] | None:
    """Find the line range of ``symbol`` (dotted path) in ``tree``."""

    parts = symbol.split(".")
    current_tree = tree
    for index, part in enumerate(parts):
        found = None
        for node in ast.walk(current_tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == part:
                    found = node
                    break
        if found is None:
            return None
        if index == len(parts) - 1:
            start = int(getattr(found, "lineno", 1) or 1)
            end = int(getattr(found, "end_lineno", start) or start)
            return (start, end)
        current_tree = found
    return None


def _find_symbol_usages(tree: ast.AST, symbol_name: str, import_only: bool) -> Iterable[int]:
    """Yield line numbers where ``symbol_name`` is imported or used."""

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == symbol_name or (alias.asname and alias.asname == symbol_name):
                    yield int(getattr(node, "lineno", 0) or 0)
                    break
            continue
        if import_only:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == symbol_name or alias.name.endswith("." + symbol_name):
                    yield int(getattr(node, "lineno", 0) or 0)
                    break
            continue
        if isinstance(node, ast.Name) and node.id == symbol_name:
            yield int(getattr(node, "lineno", 0) or 0)
        elif isinstance(node, ast.Attribute) and node.attr == symbol_name:
            yield int(getattr(node, "lineno", 0) or 0)


def _weakest_authority(authorities: list[SourceAuthorityV1]) -> SourceAuthorityV1:
    """Return the weakest authority among ``authorities`` (highest rank)."""

    from code2paper.agentic.source_authority import authority_rank

    if not authorities:
        return "executable_hard"
    return max(authorities, key=authority_rank)


def _candidates_ambiguous(candidates: list[SymbolIndexEntry]) -> bool:
    if len(candidates) < 2:
        return False
    symbols = {candidate.symbol for candidate in candidates}
    paths = {candidate.path for candidate in candidates}
    # Ambiguous: same symbol name in multiple files, or multiple distinct
    # symbols with the same prefix.
    return len(symbols) > 1 and len(paths) > 1


def _references_ambiguous(
    references: list[tuple[str, int, SourceAuthorityV1]],
    symbol_name: str,
) -> bool:
    if len(references) < 2:
        return False
    paths = {path for path, _, _ in references}
    # Ambiguous: the symbol name appears in many unrelated files.  The
    # supervisor should narrow path_scope before forming a packet.
    return len(paths) > 3


__all__ = [
    "RESEARCH_TOOL_EXECUTORS",
    "RESEARCH_TOOL_INPUT_SCHEMAS",
    "RESEARCH_TOOL_KINDS",
    "RESEARCH_TOOL_NAMES",
    "FindEntrypointsInput",
    "FindReferencesInput",
    "ReadSymbolInput",
    "ResearchToolContext",
    "SearchSymbolsInput",
    "execute_research_tool",
    "find_entrypoints",
    "find_references",
    "read_symbol",
    "search_symbols",
]
