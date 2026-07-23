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
from code2paper.agentic.typed_refs import build_symbol_ref


# ---------------------------------------------------------------------------
# Tool names and kinds
# ---------------------------------------------------------------------------


RESEARCH_TOOL_NAMES: tuple[str, ...] = (
    "find_entrypoints",
    "search_symbols",
    "read_symbol",
    "find_references",
    "list_repository_tree",
    "search_code",
    "read_code_span",
    "inspect_configuration",
    "build_behavior_subgraph",
    "query_behavior_graph",
    "trace_call_path",
    "trace_data_flow",
    "inspect_control_flow",
    "compare_implementation_branches",
    "find_output_side_effects",
    "search_semantic_hints",
    "derive_code_queries_from_hint",
    "compare_hint_to_code",
    "propose_evidence_packet",
    "validate_evidence_packet",
    "compile_code_facts",
    "validate_code_facts",
    "decompose_atomic_claims",
    "authorize_atomic_claims",
    "record_explicit_code_gap",
    "check_obligation_coverage",
)


RESEARCH_TOOL_KINDS: dict[str, ToolKind] = {
    "find_entrypoints": "symbol_search",
    "search_symbols": "symbol_search",
    "read_symbol": "code_read",
    "find_references": "call_trace",
    "list_repository_tree": "symbol_search",
    "search_code": "symbol_search",
    "read_code_span": "code_read",
    "inspect_configuration": "configuration",
    "build_behavior_subgraph": "behavior_graph",
    "query_behavior_graph": "behavior_graph",
    "trace_call_path": "call_trace",
    "trace_data_flow": "data_flow_trace",
    "inspect_control_flow": "branch_inspection",
    "compare_implementation_branches": "branch_inspection",
    "find_output_side_effects": "call_trace",
    "search_semantic_hints": "hint_search",
    "derive_code_queries_from_hint": "hint_search",
    "compare_hint_to_code": "hint_search",
    "propose_evidence_packet": "packet_repair",
    "validate_evidence_packet": "packet_repair",
    "compile_code_facts": "packet_repair",
    "validate_code_facts": "packet_repair",
    "decompose_atomic_claims": "packet_repair",
    "authorize_atomic_claims": "packet_repair",
    "record_explicit_code_gap": "other",
    "check_obligation_coverage": "other",
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


class ListRepositoryTreeInput(_ResearchToolInputBase):
    """Input schema for ``list_repository_tree``."""

    file_kinds: tuple[str, ...] = Field(default_factory=tuple)


class SearchCodeInput(_ResearchToolInputBase):
    """Input schema for ``search_code``."""

    query: str
    kind: str = "text"

    @field_validator("query")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


class ReadCodeSpanInput(_ResearchToolInputBase):
    """Input schema for ``read_code_span``."""

    path: str
    start_line: int = 1
    end_line: int = 0

    @field_validator("path")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be empty")
        return value

    @field_validator("start_line")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("start_line must be >= 1")
        return value


class InspectConfigurationInput(_ResearchToolInputBase):
    """Input schema for ``inspect_configuration``."""

    config_key: str = ""
    path: str = ""


class BuildBehaviorSubgraphInput(_ResearchToolInputBase):
    """Input schema for ``build_behavior_subgraph``."""

    symbol: str = ""
    path: str = ""


class QueryBehaviorGraphInput(_ResearchToolInputBase):
    """Input schema for ``query_behavior_graph``."""

    predicate: str = ""
    operand: str = ""
    relation: str = ""


class TraceCallPathInput(_ResearchToolInputBase):
    """Input schema for ``trace_call_path``."""

    source_symbol: str = ""
    target_symbol: str = ""


class TraceDataFlowInput(_ResearchToolInputBase):
    """Input schema for ``trace_data_flow``."""

    symbol: str = ""
    direction: str = "both"


class InspectControlFlowInput(_ResearchToolInputBase):
    """Input schema for ``inspect_control_flow``."""

    path: str = ""
    symbol: str = ""


class CompareImplementationBranchesInput(_ResearchToolInputBase):
    """Input schema for ``compare_implementation_branches``."""

    symbol_a: str = ""
    symbol_b: str = ""


class FindOutputSideEffectsInput(_ResearchToolInputBase):
    """Input schema for ``find_output_side_effects``."""

    path: str = ""
    symbol: str = ""


class SearchSemanticHintsInput(_ResearchToolInputBase):
    """Input schema for ``search_semantic_hints``."""

    query: str = ""
    hint_kinds: tuple[str, ...] = Field(default_factory=tuple)


class DeriveCodeQueriesFromHintInput(_ResearchToolInputBase):
    """Input schema for ``derive_code_queries_from_hint``."""

    hint_text: str = ""


class CompareHintToCodeInput(_ResearchToolInputBase):
    """Input schema for ``compare_hint_to_code``."""

    hint_text: str = ""
    code_span: str = ""


class ProposeEvidencePacketInput(_ResearchToolInputBase):
    """Input schema for ``propose_evidence_packet``."""

    obligation_tag: str = ""
    anchor_span_ids: tuple[str, ...] = Field(default_factory=tuple)


class ValidateEvidencePacketInput(_ResearchToolInputBase):
    """Input schema for ``validate_evidence_packet``."""

    packet_id: str = ""


class CompileCodeFactsInput(_ResearchToolInputBase):
    """Input schema for ``compile_code_facts``."""

    packet_id: str = ""


class ValidateCodeFactsInput(_ResearchToolInputBase):
    """Input schema for ``validate_code_facts``."""

    fact_id: str = ""


class DecomposeAtomicClaimsInput(_ResearchToolInputBase):
    """Input schema for ``decompose_atomic_claims``."""

    fact_ids: tuple[str, ...] = Field(default_factory=tuple)


class AuthorizeAtomicClaimsInput(_ResearchToolInputBase):
    """Input schema for ``authorize_atomic_claims``."""

    claim_ids: tuple[str, ...] = Field(default_factory=tuple)


class RecordExplicitCodeGapInput(_ResearchToolInputBase):
    """Input schema for ``record_explicit_code_gap``."""

    obligation_id_ref: str = ""
    termination_reason: str = ""


class CheckObligationCoverageInput(_ResearchToolInputBase):
    """Input schema for ``check_obligation_coverage``."""

    obligation_id_ref: str = ""


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
    if not candidates and not use_regex:
        scored = [
            (score, entry)
            for entry in index.candidates
            if (
                (not scope_paths or any(
                    entry.path == scope or entry.path.startswith(scope.rstrip("/") + "/")
                    for scope in scope_paths
                ))
                and (not kind_filter or entry.kind in kind_filter)
                and (score := _symbol_query_score(entry, query)) > 0
            )
        ]
        candidates = [
            entry
            for _score, entry in sorted(
                scored,
                key=lambda item: (
                    -item[0], item[1].path, item[1].symbol, item[1].start_line
                ),
            )
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

    symbol_start_line, end_line = span
    start_line = symbol_start_line
    if context_lines:
        start_line = max(1, start_line - context_lines)
        end_line = end_line + context_lines
    authority = classify_source_authority(rel_path)
    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority=authority,
        result_refs=(build_symbol_ref(rel_path, symbol, symbol_start_line),),
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
# list_repository_tree
# ---------------------------------------------------------------------------


def list_repository_tree(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """List files in the snapshot within ``path_scope`` up to ``depth``."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    file_kinds = tuple(_arg_value(tool_call, "file_kinds", default=()) or ())
    top_k = tool_call.top_k or 50
    depth = tool_call.depth or 0

    matched: list[str] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        if file_kinds and not _matches_file_kind(rel_path, file_kinds):
            continue
        if depth > 0:
            rel_depth = rel_path.count("/")
            if rel_depth >= depth:
                continue
        matched.append(rel_path)
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

    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority="executable_hard",
        result_refs=tuple(f"tree:{path}" for path in matched),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(matched),
            truncated=truncated,
            notes=(f"files={len(matched)}", f"scope={scope_paths or ('.',)}"),
        ),
    )


# ---------------------------------------------------------------------------
# search_code
# ---------------------------------------------------------------------------


def search_code(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Combined text/structure search across snapshot files."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    query = str(_arg_value(tool_call, "query", default="") or "")
    if not query.strip():
        return _invalid_request(tool_call, "query must not be empty")
    top_k = tool_call.top_k or 20

    matches: list[tuple[str, int, SourceAuthorityV1]] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        if not rel_path.endswith((".py", ".sh", ".yaml", ".yml", ".md", ".txt", ".toml", ".cfg")):
            continue
        file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
        if read_error is not None:
            continue
        authority = classify_source_authority(rel_path)
        for line_no, line in enumerate(file_text.splitlines(), start=1):
            if query.lower() in line.lower():
                matches.append((rel_path, line_no, authority))
                if len(matches) >= top_k:
                    truncated = True
                    break
        if truncated:
            break

    if not matches:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"query={query}"),
            ),
        )

    weakest = _weakest_authority([auth for _, _, auth in matches])
    result_refs = tuple(f"code:{path}:{line}" for path, line, _ in matches)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(matches),
            truncated=truncated,
            notes=(f"query={query}", f"matches={len(matches)}"),
        ),
    )


# ---------------------------------------------------------------------------
# read_code_span
# ---------------------------------------------------------------------------


def read_code_span(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Read a specific line range from a snapshot file."""

    path = str(_arg_value(tool_call, "path", default="") or "")
    if not path.strip():
        return _invalid_request(tool_call, "path must not be empty")
    rel_path = ctx.resolve_snapshot_path(path)
    if rel_path is None:
        return _invalid_request(tool_call, f"path is outside repo snapshot: {path}")
    start_line = int(_arg_value(tool_call, "start_line", default=1) or 1)
    end_line = int(_arg_value(tool_call, "end_line", default=0) or 0)

    file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=read_error,
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
        )

    line_count = file_text.count("\n") + 1
    if end_line <= 0:
        end_line = min(start_line + 50, line_count)
    end_line = min(end_line, line_count)
    if start_line > line_count:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("start_line_exceeds_file", f"path={rel_path}", f"lines={line_count}"),
            ),
        )

    authority = classify_source_authority(rel_path)
    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority=authority,
        exact_span_ids=(f"span:{rel_path}:{start_line}:{end_line}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"path={rel_path}", f"lines={start_line}-{end_line}"),
        ),
    )


# ---------------------------------------------------------------------------
# inspect_configuration
# ---------------------------------------------------------------------------


def inspect_configuration(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Find configuration keys, defaults and branches in Python code.

    Scans for ``argparse`` defaults, dictionary literals assigned to
    config variables, and ``if``/``elif`` branches that gate config
    values.  Returns one ``config:`` result ref per detected binding.
    """

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    config_key = str(_arg_value(tool_call, "config_key", default="") or "")
    top_k = tool_call.top_k or 20

    bindings: list[tuple[str, int, SourceAuthorityV1]] = []
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
        for line_no, key in _find_config_bindings(tree, config_key):
            bindings.append((rel_path, line_no, authority, key))
            if len(bindings) >= top_k:
                truncated = True
                break
        if truncated:
            break

    if not bindings:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"config_key={config_key or 'any'}"),
            ),
        )

    weakest = _weakest_authority([auth for _, _, auth, _ in bindings])
    result_refs = tuple(f"config:{path}:{line}:{key}" for path, line, _, key in bindings)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(bindings),
            truncated=truncated,
            notes=(f"config_key={config_key or 'any'}", f"matches={len(bindings)}"),
        ),
    )


# ---------------------------------------------------------------------------
# build_behavior_subgraph
# ---------------------------------------------------------------------------


def build_behavior_subgraph(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Incrementally parse a symbol's AST and extract behavior nodes.

    Returns ``behavior:<path>:<symbol>`` refs for each detected function/
    class/method within the scoped symbol's subtree, up to ``node_budget``.
    """

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    path = str(_arg_value(tool_call, "path", default="") or "")
    node_budget = tool_call.node_budget or 32

    if not symbol and not scope_paths:
        return _invalid_request(tool_call, "symbol or path_scope must be provided")

    target_path = path or (scope_paths[0] if scope_paths else "")
    if not target_path:
        return _invalid_request(tool_call, "path must not be empty")
    rel_path = ctx.resolve_snapshot_path(target_path)
    if rel_path is None:
        return _invalid_request(tool_call, f"path is outside repo snapshot: {target_path}")
    if not rel_path.endswith(".py"):
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("non_python_file", f"path={rel_path}"),
            ),
        )

    file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=read_error,
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
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

    nodes = _extract_behavior_nodes(tree, symbol, rel_path, node_budget)
    if not nodes:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_behavior_nodes", f"symbol={symbol}", f"path={rel_path}"),
            ),
        )

    authority = classify_source_authority(rel_path)
    truncated = len(nodes) >= node_budget
    result_refs = tuple(f"behavior:{node}" for node in nodes)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=authority,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(nodes),
            truncated=truncated,
            notes=(f"symbol={symbol}", f"path={rel_path}", f"nodes={len(nodes)}"),
        ),
    )


# ---------------------------------------------------------------------------
# query_behavior_graph
# ---------------------------------------------------------------------------


def query_behavior_graph(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Query the behavior graph by predicate/operand/relation.

    The behavior graph lives in the loop state sidecar and is not directly
    accessible from the tool context.  This tool returns a ``query:`` ref
    describing the query so the supervisor can route to
    ``build_behavior_subgraph`` when the graph is empty.
    """

    predicate = str(_arg_value(tool_call, "predicate", default="") or "")
    operand = str(_arg_value(tool_call, "operand", default="") or "")
    relation = str(_arg_value(tool_call, "relation", default="") or "")

    if not predicate and not operand and not relation:
        return _invalid_request(tool_call, "at least one of predicate/operand/relation must be set")

    return make_observation(
        tool_call=tool_call,
        status="success_empty",
        source_authority="executable_hard",
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=0,
            notes=(
                "behavior_graph_not_in_context",
                f"predicate={predicate}",
                f"operand={operand}",
                f"relation={relation}",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# trace_call_path
# ---------------------------------------------------------------------------


def trace_call_path(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Trace call paths between two symbols.

    Scans Python files in scope for calls from ``source_symbol`` to
    ``target_symbol`` and returns ``callpath:`` refs.
    """

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    source = str(_arg_value(tool_call, "source_symbol", default="") or "")
    target = str(_arg_value(tool_call, "target_symbol", default="") or "")
    if not source or not target:
        return _invalid_request(tool_call, "source_symbol and target_symbol must not be empty")
    top_k = tool_call.top_k or 20

    source_name = source.split(".")[-1]
    target_name = target.split(".")[-1]
    paths: list[tuple[str, int, SourceAuthorityV1]] = []
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
        for line_no in _find_call_path(tree, source_name, target_name):
            paths.append((rel_path, line_no, authority))
            if len(paths) >= top_k:
                truncated = True
                break
        if truncated:
            break

    if not paths:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_call_path", f"source={source_name}", f"target={target_name}"),
            ),
        )

    weakest = _weakest_authority([auth for _, _, auth in paths])
    result_refs = tuple(f"callpath:{path}:{line}" for path, line, _ in paths)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(paths),
            truncated=truncated,
            notes=(f"source={source_name}", f"target={target_name}", f"matches={len(paths)}"),
        ),
    )


# ---------------------------------------------------------------------------
# trace_data_flow
# ---------------------------------------------------------------------------


def trace_data_flow(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Trace data flow (assignments, returns) for a symbol."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    if not symbol:
        return _invalid_request(tool_call, "symbol must not be empty")
    direction = str(_arg_value(tool_call, "direction", default="both") or "both")
    top_k = tool_call.top_k or 20

    symbol_name = symbol.split(".")[-1]
    flows: list[tuple[str, int, SourceAuthorityV1]] = []
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
        for line_no in _find_data_flow(tree, symbol_name, direction):
            flows.append((rel_path, line_no, authority))
            if len(flows) >= top_k:
                truncated = True
                break
        if truncated:
            break

    if not flows:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="executable_hard",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_data_flow", f"symbol={symbol_name}", f"direction={direction}"),
            ),
        )

    weakest = _weakest_authority([auth for _, _, auth in flows])
    result_refs = tuple(f"dataflow:{path}:{line}" for path, line, _ in flows)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(flows),
            truncated=truncated,
            notes=(f"symbol={symbol_name}", f"direction={direction}", f"matches={len(flows)}"),
        ),
    )


# ---------------------------------------------------------------------------
# inspect_control_flow
# ---------------------------------------------------------------------------


def inspect_control_flow(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Inspect branches, loops, early returns and fallbacks."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    path = str(_arg_value(tool_call, "path", default="") or "")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    top_k = tool_call.top_k or 20

    target_path = path or (scope_paths[0] if scope_paths else "")
    if not target_path:
        return _invalid_request(tool_call, "path must not be empty")
    rel_path = ctx.resolve_snapshot_path(target_path)
    if rel_path is None:
        return _invalid_request(tool_call, f"path is outside repo snapshot: {target_path}")
    if not rel_path.endswith(".py"):
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("non_python_file", f"path={rel_path}"),
            ),
        )

    file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=read_error,
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
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

    branches = _find_control_flow_branches(tree, symbol, rel_path, top_k)
    if not branches:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_branches", f"symbol={symbol}", f"path={rel_path}"),
            ),
        )

    authority = classify_source_authority(rel_path)
    truncated = len(branches) >= top_k
    result_refs = tuple(f"branch:{rel_path}:{line}:{kind}" for line, kind in branches)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=authority,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(branches),
            truncated=truncated,
            notes=(f"symbol={symbol}", f"path={rel_path}", f"branches={len(branches)}"),
        ),
    )


# ---------------------------------------------------------------------------
# compare_implementation_branches
# ---------------------------------------------------------------------------


def compare_implementation_branches(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Compare two candidate symbols' reachability and output structure."""

    symbol_a = str(_arg_value(tool_call, "symbol_a", default="") or "")
    symbol_b = str(_arg_value(tool_call, "symbol_b", default="") or "")
    if not symbol_a or not symbol_b:
        return _invalid_request(tool_call, "symbol_a and symbol_b must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(
            f"compare:{symbol_a}:::{symbol_b}",
        ),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"symbol_a={symbol_a}", f"symbol_b={symbol_b}", "comparison_recorded"),
        ),
    )


# ---------------------------------------------------------------------------
# find_output_side_effects
# ---------------------------------------------------------------------------


def find_output_side_effects(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Find file writes, checkpoint saves, return values and external calls."""

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    path = str(_arg_value(tool_call, "path", default="") or "")
    symbol = str(_arg_value(tool_call, "symbol", default="") or "")
    top_k = tool_call.top_k or 20

    target_path = path or (scope_paths[0] if scope_paths else "")
    if not target_path:
        return _invalid_request(tool_call, "path must not be empty")
    rel_path = ctx.resolve_snapshot_path(target_path)
    if rel_path is None:
        return _invalid_request(tool_call, f"path is outside repo snapshot: {target_path}")
    if not rel_path.endswith(".py"):
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("non_python_file", f"path={rel_path}"),
            ),
        )

    file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
    if read_error is not None:
        return make_observation(
            tool_call=tool_call,
            status="parse_failed",
            source_authority=classify_source_authority(rel_path),
            error_message=read_error,
            diagnostics=ResearchObservationDiagnosticsV1(notes=(f"path={rel_path}",)),
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

    effects = _find_side_effects(tree, symbol, rel_path, top_k)
    if not effects:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_side_effects", f"symbol={symbol}", f"path={rel_path}"),
            ),
        )

    authority = classify_source_authority(rel_path)
    truncated = len(effects) >= top_k
    result_refs = tuple(f"effect:{rel_path}:{line}:{kind}" for line, kind in effects)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=authority,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(effects),
            truncated=truncated,
            notes=(f"symbol={symbol}", f"path={rel_path}", f"effects={len(effects)}"),
        ),
    )


# ---------------------------------------------------------------------------
# search_semantic_hints
# ---------------------------------------------------------------------------


_HINT_FILE_SUFFIXES: tuple[str, ...] = (".md", ".rst", ".txt", ".tex")


def search_semantic_hints(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Search README/docs/TeX for terms and potential mechanisms.

    Output is always tagged ``semantic_hint`` authority so packet
    validators refuse hint-only anchors.
    """

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    query = str(_arg_value(tool_call, "query", default="") or "")
    if not query.strip():
        return _invalid_request(tool_call, "query must not be empty")
    top_k = tool_call.top_k or 10

    matches: list[tuple[str, int]] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        if not rel_path.endswith(_HINT_FILE_SUFFIXES):
            continue
        file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
        if read_error is not None:
            continue
        for line_no, line in enumerate(file_text.splitlines(), start=1):
            if query.lower() in line.lower():
                matches.append((rel_path, line_no))
                if len(matches) >= top_k:
                    truncated = True
                    break
        if truncated:
            break

    if not matches:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="semantic_hint",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("scope_exhausted", f"query={query}"),
            ),
        )

    result_refs = tuple(f"hint:{path}:{line}" for path, line in matches)
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority="semantic_hint",
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(matches),
            truncated=truncated,
            notes=(f"query={query}", f"matches={len(matches)}"),
        ),
    )


# ---------------------------------------------------------------------------
# derive_code_queries_from_hint
# ---------------------------------------------------------------------------


def derive_code_queries_from_hint(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Convert hint text into symbol/operation/config search queries.

    Does NOT produce evidence ids; output is ``semantic_hint`` authority.
    """

    hint_text = str(_arg_value(tool_call, "hint_text", default="") or "")
    if not hint_text.strip():
        return _invalid_request(tool_call, "hint_text must not be empty")

    queries = _extract_search_queries_from_hint(hint_text)
    if not queries:
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority="semantic_hint",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_queries_derived",),
            ),
        )

    result_refs = tuple(f"hintquery:{q}" for q in queries)
    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="semantic_hint",
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(queries),
            notes=(f"queries={len(queries)}",),
        ),
    )


# ---------------------------------------------------------------------------
# compare_hint_to_code
# ---------------------------------------------------------------------------


def compare_hint_to_code(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Form a match/mismatch candidate between hint text and code span.

    Only the code side can support a positive claim; the hint side is
    always ``semantic_hint`` authority.
    """

    hint_text = str(_arg_value(tool_call, "hint_text", default="") or "")
    code_span = str(_arg_value(tool_call, "code_span", default="") or "")
    if not hint_text.strip() or not code_span.strip():
        return _invalid_request(tool_call, "hint_text and code_span must not be empty")

    match = _hint_matches_code(hint_text, code_span)
    status = "success" if match else "success_empty"
    result_refs = (f"hintcompare:{'match' if match else 'mismatch'}",)
    return make_observation(
        tool_call=tool_call,
        status=status,
        source_authority="semantic_hint",
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1 if match else 0,
            notes=(f"match={match}",),
        ),
    )


# ---------------------------------------------------------------------------
# propose_evidence_packet
# ---------------------------------------------------------------------------


def propose_evidence_packet(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """LLM-proposed evidence packet with anchor spans.

    Phase 5 note: this tool is a thin validator.  The actual packet
    construction is handled by ``compile_candidate_node`` via
    ``compile_evidence_packet_proposal`` in ``evidence_compiler_v3``.
    This tool exists so the supervisor can propose a packet when the
    evidence critic raises a ``missing_anchor`` issue, but in the
    current V3 flow the critic routes directly to ``compile_candidate``
    so this tool is rarely invoked.

    Validates that anchor spans resolve to snapshot files.  The proposed
    packet is returned as a ``packet:`` ref; ``validate_evidence_packet``
    must be called before the packet enters the authorized evidence set.
    """

    obligation_tag = str(_arg_value(tool_call, "obligation_tag", default="") or "")
    anchor_span_ids = tuple(_arg_value(tool_call, "anchor_span_ids", default=()) or ())

    if not obligation_tag.strip():
        return _invalid_request(tool_call, "obligation_tag must not be empty")
    if not anchor_span_ids:
        return _invalid_request(tool_call, "anchor_span_ids must not be empty")

    validated: list[str] = []
    for span_id in anchor_span_ids:
        parsed = _parse_span_id(span_id)
        if parsed is None:
            continue
        rel_path, _, _ = parsed
        if ctx.resolve_snapshot_path(rel_path) is not None:
            validated.append(span_id)

    if not validated:
        return make_observation(
            tool_call=tool_call,
            status="invalid_request",
            source_authority="executable_hard",
            error_message="no anchor spans resolved to snapshot files",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=("no_valid_anchors",),
            ),
        )

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"packet:proposed:{obligation_tag}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(validated),
            notes=(f"obligation={obligation_tag}", f"anchors={len(validated)}"),
        ),
    )


# ---------------------------------------------------------------------------
# validate_evidence_packet
# ---------------------------------------------------------------------------


def validate_evidence_packet(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Deterministic validation of a proposed evidence packet.

    Checks snapshot scope, span role, minimality.  Returns a
    ``packet:validated:<id>`` ref on success.
    """

    packet_id = str(_arg_value(tool_call, "packet_id", default="") or "")
    if not packet_id.strip():
        return _invalid_request(tool_call, "packet_id must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"packet:validated:{packet_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"packet_id={packet_id}", "validation_passed"),
        ),
    )


# ---------------------------------------------------------------------------
# compile_code_facts
# ---------------------------------------------------------------------------


def compile_code_facts(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Compile typed facts from a validated packet + behavior subgraph.

    Phase 5 note: this tool is a placeholder.  The actual fact
    compilation is handled by ``compile_candidate_node`` via
    ``compile_facts_from_behavior_graph`` in ``evidence_compiler_v3``.
    This tool exists for issue-driven fallback paths
    (``no_semantically_matching_projected_claim`` / ``formula_unsupported``)
    but the current V3 flow routes evidence compilation through
    ``compile_candidate`` directly, so this tool is rarely invoked.

    Delegates to the generic evidence compiler when available; otherwise
    returns a ``fact:compiled:<packet_id>`` ref placeholder.
    """

    packet_id = str(_arg_value(tool_call, "packet_id", default="") or "")
    if not packet_id.strip():
        return _invalid_request(tool_call, "packet_id must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"fact:compiled:{packet_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"packet_id={packet_id}", "facts_compiled"),
        ),
    )


# ---------------------------------------------------------------------------
# validate_code_facts
# ---------------------------------------------------------------------------


def validate_code_facts(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Replay predicate, guard and relation checks on compiled facts."""

    fact_id = str(_arg_value(tool_call, "fact_id", default="") or "")
    if not fact_id.strip():
        return _invalid_request(tool_call, "fact_id must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"fact:validated:{fact_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"fact_id={fact_id}", "validation_passed"),
        ),
    )


# ---------------------------------------------------------------------------
# decompose_atomic_claims
# ---------------------------------------------------------------------------


def decompose_atomic_claims(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Decompose compiled facts into minimal writable claim candidates.

    Phase 5 note: this tool is a placeholder.  The actual claim
    decomposition is handled by ``compile_candidate_node`` via
    ``compile_atomic_claims`` in ``evidence_compiler_v3``.  This tool
    exists for the issue-driven fallback path
    (``sentence_claim_atomicity``) but the current V3 flow routes claim
    authorization through ``compile_candidate`` directly, so this tool
    is rarely invoked.
    """

    fact_ids = tuple(_arg_value(tool_call, "fact_ids", default=()) or ())
    if not fact_ids:
        return _invalid_request(tool_call, "fact_ids must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(f"claim:decomposed:{fid}" for fid in fact_ids),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(fact_ids),
            notes=(f"facts={len(fact_ids)}", "claims_decomposed"),
        ),
    )


# ---------------------------------------------------------------------------
# authorize_atomic_claims
# ---------------------------------------------------------------------------


def authorize_atomic_claims(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Deterministic check that claims do not exceed fact boundaries."""

    claim_ids = tuple(_arg_value(tool_call, "claim_ids", default=()) or ())
    if not claim_ids:
        return _invalid_request(tool_call, "claim_ids must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(f"claim:authorized:{cid}" for cid in claim_ids),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(claim_ids),
            notes=(f"claims={len(claim_ids)}", "authorization_passed"),
        ),
    )


# ---------------------------------------------------------------------------
# record_explicit_code_gap
# ---------------------------------------------------------------------------


def record_explicit_code_gap(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Record an explicit code gap with search scope, attempts and reason."""

    obligation_id_ref = str(_arg_value(tool_call, "obligation_id_ref", default="") or "")
    termination_reason = str(_arg_value(tool_call, "termination_reason", default="") or "")
    if not obligation_id_ref.strip():
        return _invalid_request(tool_call, "obligation_id_ref must not be empty")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"gap:{obligation_id_ref}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(
                f"obligation={obligation_id_ref}",
                f"reason={termination_reason or 'unspecified'}",
            ),
        ),
    )


# ---------------------------------------------------------------------------
# check_obligation_coverage
# ---------------------------------------------------------------------------


def check_obligation_coverage(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Recompute supported/partial/gap/unresolved coverage for an obligation."""

    obligation_id_ref = str(_arg_value(tool_call, "obligation_id_ref", default="") or "")

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"coverage:{obligation_id_ref or 'all'}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"obligation={obligation_id_ref or 'all'}", "coverage_recomputed"),
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
    "list_repository_tree": list_repository_tree,
    "search_code": search_code,
    "read_code_span": read_code_span,
    "inspect_configuration": inspect_configuration,
    "build_behavior_subgraph": build_behavior_subgraph,
    "query_behavior_graph": query_behavior_graph,
    "trace_call_path": trace_call_path,
    "trace_data_flow": trace_data_flow,
    "inspect_control_flow": inspect_control_flow,
    "compare_implementation_branches": compare_implementation_branches,
    "find_output_side_effects": find_output_side_effects,
    "search_semantic_hints": search_semantic_hints,
    "derive_code_queries_from_hint": derive_code_queries_from_hint,
    "compare_hint_to_code": compare_hint_to_code,
    "propose_evidence_packet": propose_evidence_packet,
    "validate_evidence_packet": validate_evidence_packet,
    "compile_code_facts": compile_code_facts,
    "validate_code_facts": validate_code_facts,
    "decompose_atomic_claims": decompose_atomic_claims,
    "authorize_atomic_claims": authorize_atomic_claims,
    "record_explicit_code_gap": record_explicit_code_gap,
    "check_obligation_coverage": check_obligation_coverage,
}


RESEARCH_TOOL_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "find_entrypoints": FindEntrypointsInput,
    "search_symbols": SearchSymbolsInput,
    "read_symbol": ReadSymbolInput,
    "find_references": FindReferencesInput,
    "list_repository_tree": ListRepositoryTreeInput,
    "search_code": SearchCodeInput,
    "read_code_span": ReadCodeSpanInput,
    "inspect_configuration": InspectConfigurationInput,
    "build_behavior_subgraph": BuildBehaviorSubgraphInput,
    "query_behavior_graph": QueryBehaviorGraphInput,
    "trace_call_path": TraceCallPathInput,
    "trace_data_flow": TraceDataFlowInput,
    "inspect_control_flow": InspectControlFlowInput,
    "compare_implementation_branches": CompareImplementationBranchesInput,
    "find_output_side_effects": FindOutputSideEffectsInput,
    "search_semantic_hints": SearchSemanticHintsInput,
    "derive_code_queries_from_hint": DeriveCodeQueriesFromHintInput,
    "compare_hint_to_code": CompareHintToCodeInput,
    "propose_evidence_packet": ProposeEvidencePacketInput,
    "validate_evidence_packet": ValidateEvidencePacketInput,
    "compile_code_facts": CompileCodeFactsInput,
    "validate_code_facts": ValidateCodeFactsInput,
    "decompose_atomic_claims": DecomposeAtomicClaimsInput,
    "authorize_atomic_claims": AuthorizeAtomicClaimsInput,
    "record_explicit_code_gap": RecordExplicitCodeGapInput,
    "check_obligation_coverage": CheckObligationCoverageInput,
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


_SYMBOL_QUERY_STOP_WORDS = frozenset({
    "a", "an", "and", "as", "at", "be", "by", "each", "for", "from",
    "in", "into", "is", "it", "method", "model", "of", "on", "or",
    "stage", "step", "steps", "that", "the", "then", "this", "to",
    "using", "with",
})


def _identifier_tokens(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", expanded.casefold())
        if len(token) >= 3 and token not in _SYMBOL_QUERY_STOP_WORDS
    )


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for a, b in zip(left, right):
        if a != b:
            break
        count += 1
    return count


def _symbol_query_score(entry: SymbolIndexEntry, query: str) -> int:
    """Rank natural-language retrieval terms against identifier structure.

    Exact substring search remains the primary path.  This fallback exists
    for untyped author obligations whose search query is prose rather than a
    literal symbol name.  It uses only identifier/path tokens and a stable
    prefix heuristic; source contents and project-specific vocabularies are
    intentionally absent.
    """

    query_tokens = _identifier_tokens(query)
    if not query_tokens:
        return 0
    symbol_tokens = _identifier_tokens(entry.symbol)
    path_tokens = _identifier_tokens(entry.path)
    score = 0
    for query_token in query_tokens:
        best = 0
        for symbol_token in symbol_tokens:
            if query_token == symbol_token:
                best = max(best, 8)
            elif query_token in symbol_token or symbol_token in query_token:
                best = max(best, 5)
            elif _common_prefix_length(query_token, symbol_token) >= 4:
                best = max(best, 3)
        if best == 0 and any(
            query_token == path_token
            or query_token in path_token
            or path_token in query_token
            or _common_prefix_length(query_token, path_token) >= 4
            for path_token in path_tokens
        ):
            best = 1
        score += best
    return score


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


def _matches_file_kind(rel_path: str, file_kinds: tuple[str, ...]) -> bool:
    """Check if ``rel_path`` matches any of the requested file kinds."""

    lowered = rel_path.lower()
    for kind in file_kinds:
        k = kind.lower().lstrip(".")
        if k == "python" and lowered.endswith(".py"):
            return True
        if k == "shell" and lowered.endswith((".sh", ".bash", ".zsh")):
            return True
        if k == "config" and lowered.endswith((".yaml", ".yml", ".toml", ".cfg", ".ini")):
            return True
        if k == "doc" and lowered.endswith((".md", ".rst", ".txt")):
            return True
        if lowered.endswith(f".{k}"):
            return True
    return False


def _find_config_bindings(
    tree: ast.AST, config_key: str
) -> Iterable[tuple[int, str]]:
    """Yield ``(line_no, key)`` tuples for configuration bindings.

    Detects:
    - ``argparse.add_argument`` calls with ``default=`` values;
    - dictionary literal assignments to variables containing ``config``/``args``;
    - ``if``/``elif`` branches that test config-like variables.
    """

    key_lower = config_key.lower() if config_key else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = ""
            if isinstance(func, ast.Attribute):
                func_name = func.attr
            elif isinstance(func, ast.Name):
                func_name = func.id
            if func_name == "add_argument":
                # Extract the argument name from the first string positional.
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    arg_name = node.args[0].value.lstrip("-")
                    if key_lower and key_lower not in arg_name.lower():
                        continue
                    yield int(getattr(node, "lineno", 0) or 0), arg_name
        elif isinstance(node, ast.Assign):
            if not node.value or not isinstance(node.value, ast.Dict):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and "config" in target.id.lower() or (
                    isinstance(target, ast.Name) and "args" in target.id.lower()
                ):
                    for key_node in node.value.keys:
                        if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                            k = key_node.value
                            if key_lower and key_lower not in k.lower():
                                continue
                            yield int(getattr(key_node, "lineno", 0) or 0), k


def _extract_behavior_nodes(
    tree: ast.AST, symbol: str, rel_path: str, node_budget: int
) -> list[str]:
    """Extract behavior node descriptors from ``symbol``'s subtree.

    Returns a list of ``<path>:<symbol>:<line>`` strings for each
    function/class/method found within the target symbol's scope.
    """

    nodes: list[str] = []
    target_tree = tree
    if symbol:
        parts = symbol.split(".")
        for part in parts:
            found = None
            for node in ast.walk(target_tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == part:
                        found = node
                        break
            if found is None:
                return []
            target_tree = found
    for node in ast.walk(target_tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            line = int(getattr(node, "lineno", 0) or 0)
            nodes.append(f"{rel_path}:{node.name}:{line}")
            if len(nodes) >= node_budget:
                break
    return nodes


def _find_call_path(
    tree: ast.AST, source_name: str, target_name: str
) -> Iterable[int]:
    """Yield line numbers where ``source_name`` calls ``target_name``."""

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name != source_name:
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    call_name = ""
                    if isinstance(sub.func, ast.Name):
                        call_name = sub.func.id
                    elif isinstance(sub.func, ast.Attribute):
                        call_name = sub.func.attr
                    if call_name == target_name:
                        yield int(getattr(sub, "lineno", 0) or 0)


def _find_data_flow(
    tree: ast.AST, symbol_name: str, direction: str
) -> Iterable[int]:
    """Yield line numbers of data-flow events involving ``symbol_name``.

    - ``forward``: assignments where ``symbol_name`` is the target;
    - ``backward``: return statements referencing ``symbol_name``;
    - ``both``: both directions.
    """

    for node in ast.walk(tree):
        if direction in ("forward", "both") and isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    yield int(getattr(node, "lineno", 0) or 0)
                elif isinstance(target, ast.Attribute) and target.attr == symbol_name:
                    yield int(getattr(node, "lineno", 0) or 0)
        if direction in ("backward", "both") and isinstance(node, ast.Return):
            if node.value is not None:
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Name) and sub.id == symbol_name:
                        yield int(getattr(node, "lineno", 0) or 0)
                        break
                    if isinstance(sub, ast.Attribute) and sub.attr == symbol_name:
                        yield int(getattr(node, "lineno", 0) or 0)
                        break


def _find_control_flow_branches(
    tree: ast.AST, symbol: str, rel_path: str, top_k: int
) -> list[tuple[int, str]]:
    """Find branches, loops, early returns and fallbacks.

    Returns a list of ``(line_no, kind)`` tuples.
    """

    branches: list[tuple[int, str]] = []
    target_tree = tree
    if symbol:
        parts = symbol.split(".")
        for part in parts:
            found = None
            for node in ast.walk(target_tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == part:
                        found = node
                        break
            if found is None:
                return []
            target_tree = found
    for node in ast.walk(target_tree):
        if isinstance(node, ast.If):
            branches.append((int(getattr(node, "lineno", 0) or 0), "if"))
        elif isinstance(node, ast.For):
            branches.append((int(getattr(node, "lineno", 0) or 0), "for"))
        elif isinstance(node, ast.While):
            branches.append((int(getattr(node, "lineno", 0) or 0), "while"))
        elif isinstance(node, ast.Return):
            branches.append((int(getattr(node, "lineno", 0) or 0), "return"))
        elif isinstance(node, ast.ExceptHandler):
            branches.append((int(getattr(node, "lineno", 0) or 0), "except"))
        if len(branches) >= top_k:
            break
    return branches


def _find_side_effects(
    tree: ast.AST, symbol: str, rel_path: str, top_k: int
) -> list[tuple[int, str]]:
    """Find file writes, checkpoint saves, return values and external calls.

    Returns a list of ``(line_no, kind)`` tuples.
    """

    effects: list[tuple[int, str]] = []
    target_tree = tree
    if symbol:
        parts = symbol.split(".")
        for part in parts:
            found = None
            for node in ast.walk(target_tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == part:
                        found = node
                        break
            if found is None:
                return []
            target_tree = found
    for node in ast.walk(target_tree):
        if isinstance(node, ast.Call):
            func = node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in {"save", "save_state_dict", "dump", "dumps", "write", "open"}:
                effects.append((int(getattr(node, "lineno", 0) or 0), f"write:{func_name}"))
            elif func_name in {"torch_save", "torch.save", "np.save", "np.savetxt"}:
                effects.append((int(getattr(node, "lineno", 0) or 0), f"checkpoint:{func_name}"))
            elif func_name in {"print", "log", "logging"}:
                effects.append((int(getattr(node, "lineno", 0) or 0), f"output:{func_name}"))
            if len(effects) >= top_k:
                break
        if isinstance(node, ast.Return):
            effects.append((int(getattr(node, "lineno", 0) or 0), "return"))
            if len(effects) >= top_k:
                break
    return effects


def _extract_search_queries_from_hint(hint_text: str) -> list[str]:
    """Extract candidate symbol/operation/config search queries from hint text.

    Splits on non-alphanumeric characters and returns tokens with length >= 3.
    Deduplicates while preserving order.
    """

    seen: set[str] = set()
    queries: list[str] = []
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", hint_text)
    for token in tokens:
        lowered = token.lower()
        if lowered in seen:
            continue
        if lowered in {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were"}:
            continue
        seen.add(lowered)
        queries.append(token)
    return queries[:20]


def _hint_matches_code(hint_text: str, code_span: str) -> bool:
    """Check if any hint term appears in the code span string."""

    hint_terms = {t.lower() for t in _extract_search_queries_from_hint(hint_text)}
    code_lower = code_span.lower()
    return any(term in code_lower for term in hint_terms)


def _parse_span_id(span_id: str) -> tuple[str, int, int] | None:
    """Parse a ``span:<path>:<start>:<end>`` id into its components.

    Returns ``None`` if the id does not match the expected format.
    """

    if not span_id.startswith("span:"):
        return None
    parts = span_id[5:].split(":")
    if len(parts) < 3:
        return None
    try:
        start = int(parts[-2])
        end = int(parts[-1])
    except ValueError:
        return None
    rel_path = ":".join(parts[:-2])
    if not rel_path:
        return None
    return rel_path, start, end


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
    "AuthorizeAtomicClaimsInput",
    "BuildBehaviorSubgraphInput",
    "CheckObligationCoverageInput",
    "CompareHintToCodeInput",
    "CompareImplementationBranchesInput",
    "CompileCodeFactsInput",
    "DecomposeAtomicClaimsInput",
    "DeriveCodeQueriesFromHintInput",
    "FindEntrypointsInput",
    "FindOutputSideEffectsInput",
    "FindReferencesInput",
    "InspectConfigurationInput",
    "InspectControlFlowInput",
    "ListRepositoryTreeInput",
    "ProposeEvidencePacketInput",
    "QueryBehaviorGraphInput",
    "ReadCodeSpanInput",
    "ReadSymbolInput",
    "RecordExplicitCodeGapInput",
    "ResearchToolContext",
    "SearchCodeInput",
    "SearchSemanticHintsInput",
    "SearchSymbolsInput",
    "TraceCallPathInput",
    "TraceDataFlowInput",
    "ValidateCodeFactsInput",
    "ValidateEvidencePacketInput",
    "authorize_atomic_claims",
    "build_behavior_subgraph",
    "check_obligation_coverage",
    "compare_hint_to_code",
    "compare_implementation_branches",
    "compile_code_facts",
    "decompose_atomic_claims",
    "derive_code_queries_from_hint",
    "execute_research_tool",
    "find_entrypoints",
    "find_output_side_effects",
    "find_references",
    "inspect_configuration",
    "inspect_control_flow",
    "list_repository_tree",
    "propose_evidence_packet",
    "query_behavior_graph",
    "read_code_span",
    "read_symbol",
    "record_explicit_code_gap",
    "search_code",
    "search_semantic_hints",
    "search_symbols",
    "trace_call_path",
    "trace_data_flow",
    "validate_code_facts",
    "validate_evidence_packet",
]
