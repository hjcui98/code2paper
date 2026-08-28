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
import json
import re
import shlex
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.language_adapter_registry import (
    LanguageAdapterRegistry,
    default_language_adapter_registry,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketV3,
)
from code2paper.agentic.generic_claim_compiler import (
    ClaimProposalV1,
    compile_atomic_claims,
)
from code2paper.agentic.generic_evidence_compiler import (
    EvidencePacketProposalV1,
    compile_evidence_packet_proposal,
)
from code2paper.agentic.generic_fact_compiler import (
    FactCompilerInputV1,
    compile_facts_from_behavior_graph,
)
from code2paper.agentic.research_models import (
    ResearchObservationDiagnosticsV1,
    ResearchObservationNotebookV1,
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
from code2paper.agentic.tool_runtime import atomic_write_json


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
    behavior_graph: CodeBehaviorGraphV1 | None = None
    artifact_root: Path | None = None
    adapter_registry: LanguageAdapterRegistry = Field(default_factory=default_language_adapter_registry)
    adapter_language: str = ""
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

    def language_adapter(self) -> Any:
        if self.adapter_language.strip():
            return self.adapter_registry.get(self.adapter_language)
        paths = {item.path: "" for item in self.repo_snapshot.included_files if item.kind == "file"}
        return self.adapter_registry.for_files(paths)

    def adapter_symbol_index(self) -> Any:
        files = {
            item.path: (_read_snapshot_file(self.repo_snapshot, item.path)[0] or "")
            for item in self.repo_snapshot.included_files
            if item.kind == "file"
        }
        return self.language_adapter().index_symbols(
            repo_snapshot_id=self.repo_snapshot.snapshot_id,
            project_tree_hash=self.repo_snapshot.project_tree_hash,
            files=files,
        )

    def artifact_path(self, kind: str, artifact_id: str) -> Path | None:
        """Resolve a content artifact without allowing ids to become paths."""

        if self.artifact_root is None:
            return None
        safe_id = hashlib.sha256(artifact_id.encode("utf-8")).hexdigest()
        return self.artifact_root / "research_tool_artifacts" / kind / f"{safe_id}.json"

    def write_artifact(self, kind: str, artifact_id: str, value: Any) -> Path | None:
        path = self.artifact_path(kind, artifact_id)
        if path is None:
            return None
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        atomic_write_json(path, payload)
        return path

    def read_artifact(self, kind: str, artifact_id: str) -> dict[str, Any] | None:
        path = self.artifact_path(kind, artifact_id)
        if path is None or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Per-tool input schemas (used by LangChain StructuredTool in R1.3)
# ---------------------------------------------------------------------------


def _bounded_excerpt(
    text: str,
    *,
    start_line: int,
    end_line: int,
    max_chars: int = 2400,
) -> str:
    """Return a numbered, bounded source window for model reasoning.

    This is a model-visible projection only.  Evidence authorization still
    uses the exact source span recorded on the observation.
    """

    lines = text.splitlines()
    start = max(1, start_line)
    end = min(len(lines), max(start, end_line))
    rendered = "\n".join(
        f"{line_no}: {lines[line_no - 1]}"
        for line_no in range(start, end + 1)
    )
    if len(rendered) <= max_chars:
        return rendered
    return rendered[:max_chars].rstrip() + "\n…"


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

    @model_validator(mode="after")
    def _ordered_lines(self) -> "ReadCodeSpanInput":
        if self.end_line and self.end_line < self.start_line:
            raise ValueError("end_line must be 0 or >= start_line")
        return self


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

    symbol: str
    direction: Literal["upstream", "downstream", "forward", "backward", "both"] = "both"

    @field_validator("symbol")
    @classmethod
    def _symbol_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("symbol must not be empty")
        return value


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
    packet_id: str = ""
    scope: str = ""
    anchor_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    semantic_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    behavior_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    behavior_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    composition_rationale: str = ""


class ValidateEvidencePacketInput(_ResearchToolInputBase):
    """Input schema for ``validate_evidence_packet``."""

    packet_id: str = ""


class CompileCodeFactsInput(_ResearchToolInputBase):
    """Input schema for ``compile_code_facts``."""

    packet_id: str = ""


class ValidateCodeFactsInput(_ResearchToolInputBase):
    """Input schema for ``validate_code_facts``."""

    fact_id: str = ""
    fact_set_id: str = ""


class DecomposeAtomicClaimsInput(_ResearchToolInputBase):
    """Input schema for ``decompose_atomic_claims``."""

    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_set_id: str = ""
    claim_proposals: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class AuthorizeAtomicClaimsInput(_ResearchToolInputBase):
    """Input schema for ``authorize_atomic_claims``."""

    claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    proposal_set_id: str = ""


class RecordExplicitCodeGapInput(_ResearchToolInputBase):
    """Input schema for ``record_explicit_code_gap``."""

    obligation_id_ref: str = ""
    termination_reason: str = ""
    search_scope: tuple[str, ...] = Field(default_factory=tuple)
    attempted_tools: tuple[str, ...] = Field(default_factory=tuple)
    missing_relations: tuple[str, ...] = Field(default_factory=tuple)
    search_complete: bool = False
    scope_exhausted: bool = False


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
    "index.js", "index.ts", "main.js", "main.ts", "server.js", "server.ts",
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

    adapter = ctx.language_adapter()
    if adapter.language == "python":
        index = ctx.ensure_symbol_index()
    else:
        adapter_index = ctx.adapter_symbol_index()
        index = SymbolIndexReport(
            project_root=str(ctx.repo_snapshot.project_root),
            indexed_files=adapter_index.indexed_files,
            indexed_symbols=adapter_index.indexed_symbols,
            candidates=[
                SymbolIndexEntry(
                    path=item.path,
                    symbol=item.qualified_name,
                    kind=item.kind,
                    start_line=item.start_line,
                    end_line=item.end_line,
                    text_hash=item.text_hash,
                    reasons=[f"language_adapter:{adapter.language}"],
                )
                for item in adapter_index.symbols
            ],
        )
    candidates = [
        entry
        for entry in index.candidates
        if _symbol_matches(entry, query, kind_filter, use_regex, scope_paths)
    ]
    if not candidates and not use_regex:
        source_cache: dict[str, list[str]] = {}
        scored = []
        for entry in index.candidates:
            if scope_paths and not any(
                entry.path == scope or entry.path.startswith(scope.rstrip("/") + "/")
                for scope in scope_paths
            ):
                continue
            if kind_filter and entry.kind not in kind_filter:
                continue
            identifier_score = _symbol_query_score(entry, query)
            source_score = 0
            if entry.kind != "class":
                source_score = _symbol_source_query_score(
                    ctx,
                    entry,
                    query,
                    source_cache=source_cache,
                )
            # Identifier matches are excellent exact hints, but path tokens
            # contribute only a one-point fallback inside
            # ``_symbol_query_score``. Multiplying that weak path hit by ten
            # caused every helper in ``feature_utils.py`` to outrank a longer
            # method whose body actually implemented the requested feature
            # assembly. Let exact/partial symbol hits dominate naturally while
            # keeping source-body semantics competitive with path-only noise.
            score = identifier_score * 4 + source_score * 3
            if score > 0:
                scored.append((score, entry))
        candidates = [
            entry
            for _score, entry in sorted(
                scored,
                key=lambda item: (
                    -item[0],
                    max(0, item[1].end_line - item[1].start_line),
                    item[1].path,
                    item[1].symbol,
                    item[1].start_line,
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
    symbol_names = tuple(
        f"{entry.path}::{entry.symbol}" for entry in selected[:10]
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Symbol search for {query!r} returned {len(selected)} ranked "
                "candidates. Select a concrete candidate to read, or change "
                "the query if these symbols do not answer the research question."
            ),
            discovered_symbols=symbol_names,
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
        adapter = ctx.language_adapter()
        if adapter.language != "python" and rel_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            index = ctx.adapter_symbol_index()
            matched = next((
                item for item in index.symbols
                if item.path == rel_path and item.qualified_name == symbol
            ), None)
            if matched is not None:
                start_line = max(1, matched.start_line - context_lines)
                end_line = matched.end_line + context_lines
                return make_observation(
                    tool_call=tool_call,
                    status="success",
                    source_authority=classify_source_authority(rel_path),
                    result_refs=(build_symbol_ref(rel_path, symbol, matched.start_line),),
                    exact_span_ids=(f"span:{rel_path}:{start_line}:{end_line}",),
                    diagnostics=ResearchObservationDiagnosticsV1(
                        candidate_count=1,
                        notes=(f"language_adapter={adapter.language}", f"symbol={symbol}", f"lines={start_line}-{end_line}"),
                    ),
                    notebook=ResearchObservationNotebookV1(
                        summary=(
                            f"Read {symbol} in {rel_path} at lines "
                            f"{start_line}-{end_line}."
                        ),
                        code_excerpt=_bounded_excerpt(
                            file_text,
                            start_line=start_line,
                            end_line=end_line,
                        ),
                        discovered_symbols=(f"{rel_path}::{symbol}",),
                    ),
                )
        # Unsupported text files are exposed as a single span so the
        # supervisor can still read them without inventing a symbol range.
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
            notebook=ResearchObservationNotebookV1(
                summary=f"Read non-Python source file {rel_path}.",
                code_excerpt=_bounded_excerpt(
                    file_text,
                    start_line=1,
                    end_line=line_count,
                ),
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Read {symbol} in {rel_path} at lines {start_line}-{end_line}. "
                "Use the excerpt to decide whether this code answers the active "
                "question and what caller, data, branch, or configuration to inspect next."
            ),
            code_excerpt=_bounded_excerpt(
                file_text,
                start_line=start_line,
                end_line=end_line,
            ),
            discovered_symbols=(f"{rel_path}::{symbol}",),
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Found {len(references)} usages of {symbol_name}; inspect a "
                "specific caller or use a trace when its role in the method is unclear."
            ),
            discovered_relations=tuple(
                f"usage:{path}:{line_no}" for path, line_no, _ in references[:12]
            ),
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
        notebook=ResearchObservationNotebookV1(
            summary=f"Listed {len(matched)} repository files in the requested scope.",
            discovered_symbols=tuple(matched[:20]),
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Code search for {query!r} returned {len(matches)} exact line hits. "
                "Read one or more relevant spans to understand their semantics."
            ),
            discovered_relations=tuple(
                f"text-hit:{path}:{line}" for path, line, _ in matches[:20]
            ),
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
    enclosing_refs: tuple[str, ...] = ()
    if rel_path.endswith(".py"):
        try:
            tree = ast.parse(file_text)
        except SyntaxError:
            tree = None
        if tree is not None:
            candidates = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and int(getattr(node, "lineno", 0) or 0) <= start_line
                <= int(getattr(node, "end_lineno", getattr(node, "lineno", 0)) or 0)
            ]
            if candidates:
                enclosing = min(
                    candidates,
                    key=lambda node: (
                        int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno),
                        -int(node.lineno),
                    ),
                )
                enclosing_refs = (
                    build_symbol_ref(rel_path, enclosing.name, int(enclosing.lineno)),
                )
    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority=authority,
        exact_span_ids=(f"span:{rel_path}:{start_line}:{end_line}",),
        result_refs=enclosing_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(f"path={rel_path}", f"lines={start_line}-{end_line}"),
        ),
        notebook=ResearchObservationNotebookV1(
            summary=f"Read {rel_path} lines {start_line}-{end_line}.",
            code_excerpt=_bounded_excerpt(
                file_text,
                start_line=start_line,
                end_line=end_line,
            ),
            discovered_symbols=tuple(
                ref.split(":", 1)[-1] for ref in enclosing_refs
            ),
            enclosing_symbol_refs=enclosing_refs,
        ),
    )


# ---------------------------------------------------------------------------
# inspect_configuration
# ---------------------------------------------------------------------------


def inspect_configuration(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Find configuration keys, defaults and build-entrypoint bindings.

    Scans for ``argparse`` defaults, dictionary literals assigned to
    config variables, and ``if``/``elif`` branches that gate config values
    in Python.  JavaScript/TypeScript additionally records runtime config
    reads (``process.env``, ``import.meta.env``, ``config``/``options``
    access), package scripts/dependencies, and common build-config files.
    Returns one ``config:`` result ref per detected binding.  These refs are
    discovery anchors only; a positive configuration claim still requires a
    packet, behavior relation and the generic fact/configuration compilers.
    """

    scope_paths = _scope_paths(ctx, tool_call)
    if scope_paths is None:
        return _invalid_request(tool_call, "path_scope contains snapshot-external paths")
    config_key = str(_arg_value(tool_call, "config_key", default="") or "")
    top_k = tool_call.top_k or 20

    bindings: list[tuple[str, int, SourceAuthorityV1, str]] = []
    truncated = False
    for rel_path in _iter_snapshot_files(ctx.repo_snapshot, scope_paths):
        file_text, read_error = _read_snapshot_file(ctx.repo_snapshot, rel_path)
        if read_error is not None:
            continue
        authority = classify_source_authority(rel_path)
        if rel_path.endswith(".py"):
            try:
                tree = ast.parse(file_text)
            except SyntaxError:
                continue
            found = _find_config_bindings(tree, config_key)
        elif rel_path.endswith((".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml", ".lock")):
            found = _find_javascript_config_bindings(rel_path, file_text, config_key)
        else:
            continue
        for line_no, key in found:
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
    build_count = sum(
        1
        for path, _line, _authority, key in bindings
        if _is_build_configuration_binding(path, key)
    )
    runtime_count = sum(
        1
        for path, _line, _authority, key in bindings
        if _is_runtime_configuration_binding(path, key)
    )
    return make_observation(
        tool_call=tool_call,
        status="success" if not truncated else "truncated",
        source_authority=weakest,
        result_refs=result_refs,
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(bindings),
            truncated=truncated,
            notes=(
                f"config_key={config_key or 'any'}",
                f"matches={len(bindings)}",
                f"build_bindings={build_count}",
                f"runtime_bindings={runtime_count}",
            ),
        ),
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Configuration inspection found {len(bindings)} bindings for "
                f"{config_key or 'the requested scope'}; read the relevant lines "
                "before describing defaults or runtime behavior."
            ),
            discovered_relations=tuple(
                f"config:{path}:{line}:{key}"
                for path, line, _, key in bindings[:20]
            ),
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
        adapter = ctx.language_adapter()
        if adapter.language != "python" and rel_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            index = ctx.adapter_symbol_index()
            matched = next((
                item for item in index.symbols
                if item.path == rel_path and (not symbol or item.qualified_name == symbol)
            ), None)
            if matched is not None:
                operations = adapter.extract_operations(matched, file_text)
                descriptor = f"{rel_path}:{matched.qualified_name}:{matched.start_line}"
                return make_observation(
                    tool_call=tool_call,
                    status="success" if len(operations) < node_budget else "truncated",
                    source_authority=classify_source_authority(rel_path),
                    result_refs=(f"behavior:{descriptor}",),
                    exact_span_ids=(f"span:{rel_path}:{matched.start_line}:{matched.end_line}",),
                    diagnostics=ResearchObservationDiagnosticsV1(
                        candidate_count=min(len(operations), node_budget),
                        truncated=len(operations) >= node_budget,
                        notes=(f"language_adapter={adapter.language}", f"symbol={matched.qualified_name}"),
                    ),
                    notebook=ResearchObservationNotebookV1(
                        summary=(
                            f"Extracted {min(len(operations), node_budget)} "
                            f"operations from {matched.qualified_name} in {rel_path}."
                        ),
                        code_excerpt=_bounded_excerpt(
                            file_text,
                            start_line=matched.start_line,
                            end_line=matched.end_line,
                        ),
                        discovered_relations=tuple(
                            f"operation:{item}" for item in operations[:20]
                        ),
                    ),
                )
        return make_observation(
            tool_call=tool_call,
            status="success_empty",
            source_authority=classify_source_authority(rel_path),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Extracted {len(nodes)} executable operations from {symbol} in "
                f"{rel_path}; use them to assess whether the active method question "
                "is answered or needs a relation/configuration trace."
            ),
            discovered_relations=tuple(f"operation:{node}" for node in nodes[:20]),
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
    # Legacy aliases stay readable in checkpoints and direct tool callers;
    # the model-visible contract uses upstream/downstream.
    direction = {"forward": "downstream", "backward": "upstream"}.get(
        direction, direction
    )
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Data-flow inspection for {symbol_name} found {len(flows)} "
                "assignment/return sites. Read the relevant windows before "
                "treating them as method evidence."
            ),
            discovered_relations=tuple(
                f"dataflow:{path}:{line}" for path, line, _ in flows[:12]
            ),
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
        notebook=ResearchObservationNotebookV1(
            summary=(
                f"Control-flow inspection found {len(branches)} branches or "
                f"loops in {symbol or rel_path}."
            ),
            discovered_relations=tuple(
                f"branch:{rel_path}:{line}:{kind}" for line, kind in branches[:12]
            ),
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
    """Persist an obligation-scoped packet proposal for deterministic validation."""

    obligation_tag = str(_arg_value(tool_call, "obligation_tag", default="") or "")
    anchor_span_ids = tuple(_arg_value(tool_call, "anchor_span_ids", default=()) or ())

    if not obligation_tag.strip():
        return _invalid_request(tool_call, "obligation_tag must not be empty")
    if not anchor_span_ids:
        return _invalid_request(tool_call, "anchor_span_ids must not be empty")
    if ctx.behavior_graph is None or ctx.artifact_root is None:
        return _invalid_request(
            tool_call,
            "packet data plane requires behavior_graph and artifact_root",
        )

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

    node_ids = tuple(_arg_value(tool_call, "behavior_node_ids", default=()) or ())
    if not node_ids:
        anchor_set = set(validated)
        node_ids = tuple(
            node.node_id
            for node in ctx.behavior_graph.nodes
            if node.source_span_id in anchor_set
        )
    if not node_ids:
        return _invalid_request(tool_call, "anchors have no behavior graph nodes")

    packet_id = str(_arg_value(tool_call, "packet_id", default="") or "").strip()
    if not packet_id:
        identity = json.dumps(
            [obligation_tag, sorted(validated), sorted(node_ids)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        packet_id = "packet-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    proposal = EvidencePacketProposalV1(
        packet_id=packet_id,
        obligation_id=obligation_tag,
        scope=str(_arg_value(tool_call, "scope", default="") or obligation_tag),
        anchor_span_ids=list(validated),
        relation_span_ids=list(_arg_value(tool_call, "relation_span_ids", default=()) or ()),
        semantic_span_ids=list(_arg_value(tool_call, "semantic_span_ids", default=()) or ()),
        behavior_node_ids=list(node_ids),
        behavior_relation_ids=list(
            _arg_value(tool_call, "behavior_relation_ids", default=()) or ()
        ),
        conditions=list(_arg_value(tool_call, "conditions", default=()) or ()),
        composition_rationale=str(
            _arg_value(tool_call, "composition_rationale", default="") or ""
        ),
    )
    artifact_path = ctx.write_artifact("packet_proposals", packet_id, proposal)
    assert artifact_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"packet:proposed:{packet_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(validated),
            notes=(
                f"obligation={obligation_tag}",
                f"anchors={len(validated)}",
                f"artifact={artifact_path}",
            ),
        ),
        output_payload=proposal.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# validate_evidence_packet
# ---------------------------------------------------------------------------


def validate_evidence_packet(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Compile and validate a persisted proposal against the frozen graph."""

    packet_id = str(_arg_value(tool_call, "packet_id", default="") or "")
    if not packet_id.strip():
        return _invalid_request(tool_call, "packet_id must not be empty")

    packet_id = packet_id.removeprefix("packet:proposed:")
    if ctx.behavior_graph is None or ctx.artifact_root is None:
        return _invalid_request(
            tool_call,
            "packet data plane requires behavior_graph and artifact_root",
        )
    raw = ctx.read_artifact("packet_proposals", packet_id)
    if raw is None:
        return _invalid_request(tool_call, f"unknown packet proposal: {packet_id}")
    proposal = EvidencePacketProposalV1.model_validate(raw)
    packet, report = compile_evidence_packet_proposal(
        proposal,
        ctx.behavior_graph,
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        project_tree_hash=ctx.repo_snapshot.project_tree_hash,
        repo_snapshot=ctx.repo_snapshot,
    )
    # A validated packet is an immutable data-plane artifact.  Re-running the
    # validator must replay the exact bytes produced from the proposal rather
    # than silently replacing a tampered sidecar.  This keeps the packet
    # digest/path in the observation trace meaningful across checkpoint
    # resumes and process restarts.
    persisted_packet = ctx.read_artifact("validated_packets", packet_id)
    if persisted_packet is not None:
        try:
            persisted_model = EvidencePacketV3.model_validate(persisted_packet)
        except Exception:
            persisted_model = None
            report = report.model_copy(
                update={
                    "failures": [*report.failures, "validated_packet_artifact_invalid"]
                }
            )
        if persisted_model is not None and packet is not None:
            if persisted_model.model_dump(mode="json") != packet.model_dump(mode="json"):
                report = report.model_copy(
                    update={
                        "failures": [*report.failures, "validated_packet_artifact_drift"]
                    }
                )
    report_path = ctx.write_artifact("packet_validation_reports", packet_id, report)
    assert report_path is not None
    if packet is None or not report.accepted:
        failures = tuple(report.failures)
        return make_observation(
            tool_call=tool_call,
            status="invalid_request",
            source_authority="executable_hard",
            error_message=";".join(failures) or "packet compilation failed",
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=failures + (f"validator_report={report_path}",),
            ),
            output_payload=report.model_dump(mode="json"),
        )
    packet_path = ctx.write_artifact("validated_packets", packet_id, packet)
    assert packet_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"packet:validated:{packet.packet_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(
                f"packet_id={packet_id}",
                "validation_passed",
                f"artifact={packet_path}",
                f"validator_report={report_path}",
            ),
        ),
        output_payload=packet.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# compile_code_facts
# ---------------------------------------------------------------------------


def _symbol_display_names_for_nodes(
    ctx: ResearchToolContext,
    node_ids: list[str],
) -> dict[str, str]:
    """Resolve opaque graph symbol ids to source-index-qualified names.

    Two resolution paths are used:

    1. **Adapter symbol index (primary)**: The language adapter's
       :meth:`index_symbols` returns :class:`SymbolRefV1` records that
       carry both ``symbol_id`` and ``qualified_name``.  Building a
       direct ``symbol_id -> qualified_name`` map from these records is
       the most reliable resolution, because ``symbol_id`` is derived
       from ``(path, qualified_name, start_line)`` — the same triple the
       adapter used to create it.

    2. **SymbolIndexReport span lookup (fallback)**: The legacy
       :class:`SymbolIndexReport` candidates are matched by ``path`` and
       line range from the node's ``source_span_id``.  This path can
       fail when the report's candidate list does not cover the node's
       source span (e.g. due to ``max_indexed_symbols`` truncation or a
       path-format mismatch), leaving ``fact.subject`` as the opaque
       ``sym:<digest>`` identifier.  When that happens, the canonical
       claim text becomes a mechanical template
       (``sym:abc123 loads weights foo``) that the Writer copies
       verbatim and the reverse validator rejects.
    """

    if ctx.behavior_graph is None:
        return {}
    requested = set(node_ids)
    display: dict[str, str] = {}

    # --- Path 1: adapter symbol index (direct symbol_id lookup) ------------
    adapter_symbols: list[Any] = []
    try:
        adapter_index = ctx.adapter_symbol_index()
        adapter_symbols = list(getattr(adapter_index, "symbols", None) or [])
    except Exception:  # pragma: no cover - adapter failures are non-fatal
        adapter_symbols = []
    for sym in adapter_symbols:
        sid = getattr(sym, "symbol_id", "") or ""
        qname = getattr(sym, "qualified_name", "") or ""
        if sid and qname and sid not in display:
            display[sid] = qname

    # Collect the set of symbol_ids that the adapter index already resolved
    # so the fallback path only touches unresolved nodes.
    resolved_by_adapter = set(display)

    # --- Path 2: SymbolIndexReport span lookup (fallback) ------------------
    index = ctx.ensure_symbol_index()
    for node in ctx.behavior_graph.nodes:
        if node.node_id not in requested or node.symbol_id in display:
            continue
        parts = node.source_span_id.rsplit(":", 2)
        if len(parts) != 3 or not parts[0].startswith("span:"):
            continue
        path = parts[0].removeprefix("span:")
        try:
            line = int(parts[1])
        except ValueError:
            continue
        matches = [
            entry
            for entry in index.candidates
            if entry.path == path and entry.start_line <= line <= entry.end_line
        ]
        if not matches:
            continue
        owner = min(
            matches,
            key=lambda entry: (
                entry.end_line - entry.start_line,
                -entry.start_line,
                entry.symbol,
            ),
        )
        display[node.symbol_id] = owner.symbol

    # If the adapter index resolved a symbol_id that the span lookup would
    # have overwritten with a shorter/less-qualified name, keep the adapter's
    # qualified_name (it includes class/module scope, e.g. ``Foo.bar``).
    for sid in resolved_by_adapter:
        if sid in display and display[sid] != _adapter_qualified_name(
            adapter_symbols, sid
        ):
            display[sid] = _adapter_qualified_name(adapter_symbols, sid)

    return display


def _adapter_qualified_name(
    adapter_symbols: list[Any],
    symbol_id: str,
) -> str:
    """Return the qualified_name from adapter symbols, or empty string."""

    for sym in adapter_symbols:
        if getattr(sym, "symbol_id", "") == symbol_id:
            return getattr(sym, "qualified_name", "") or ""
    return ""


def compile_code_facts(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Compile a real ``CodeFactSetV1`` from a validated packet and graph."""

    packet_id = str(_arg_value(tool_call, "packet_id", default="") or "")
    if not packet_id.strip():
        return _invalid_request(tool_call, "packet_id must not be empty")

    packet_id = packet_id.removeprefix("packet:validated:")
    if ctx.behavior_graph is None or ctx.artifact_root is None:
        return _invalid_request(
            tool_call,
            "fact data plane requires behavior_graph and artifact_root",
        )
    packet_raw = ctx.read_artifact("validated_packets", packet_id)
    proposal_raw = ctx.read_artifact("packet_proposals", packet_id)
    if packet_raw is None or proposal_raw is None:
        return _invalid_request(tool_call, f"packet is not validated: {packet_id}")
    packet = EvidencePacketV3.model_validate(packet_raw)
    proposal = EvidencePacketProposalV1.model_validate(proposal_raw)
    symbol_display_names = _symbol_display_names_for_nodes(
        ctx,
        proposal.behavior_node_ids,
    )
    fact_set = compile_facts_from_behavior_graph(
        ctx.behavior_graph,
        FactCompilerInputV1(
            obligation_id=proposal.obligation_id,
            behavior_node_ids=proposal.behavior_node_ids,
            behavior_relation_ids=proposal.behavior_relation_ids,
            evidence_span_ids=[span.span_id for span in packet.spans],
            guards=proposal.conditions,
            source_authority="executable_hard",
            symbol_display_names=symbol_display_names,
        ),
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        project_tree_hash=ctx.repo_snapshot.project_tree_hash,
        evidence_packet_digest=packet.source_digest,
    )
    if not fact_set.facts:
        return _invalid_request(tool_call, f"no facts compiled for packet: {packet_id}")
    fact_path = ctx.write_artifact("fact_sets", packet_id, fact_set)
    assert fact_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(f"fact:compiled:{fact.fact_id}" for fact in fact_set.facts),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(fact_set.facts),
            notes=(
                f"packet_id={packet_id}",
                f"fact_set_id={packet_id}",
                f"artifact={fact_path}",
            ),
        ),
        output_payload=fact_set.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# validate_code_facts
# ---------------------------------------------------------------------------


def validate_code_facts(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Replay provenance, span, guard and relation checks for a fact set."""

    fact_id = str(_arg_value(tool_call, "fact_id", default="") or "")
    if not fact_id.strip():
        return _invalid_request(tool_call, "fact_id must not be empty")

    if ctx.behavior_graph is None or ctx.artifact_root is None:
        return _invalid_request(
            tool_call,
            "fact data plane requires behavior_graph and artifact_root",
        )
    requested_fact_set_id = str(_arg_value(tool_call, "fact_set_id", default="") or "")
    lookup_id = requested_fact_set_id
    if not lookup_id:
        lookup_id = fact_id.removeprefix("fact:compiled:")
    raw = ctx.read_artifact("fact_sets", lookup_id)
    if raw is None:
        # A caller may pass an individual fact id; locate its set without
        # treating artifact filenames as semantic identifiers.
        root = ctx.artifact_root / "research_tool_artifacts" / "fact_sets"
        for path in sorted(root.glob("*.json")) if root.is_dir() else ():
            candidate = CodeFactSetV1.model_validate_json(path.read_text(encoding="utf-8"))
            if any(f.fact_id == lookup_id for f in candidate.facts):
                raw = candidate.model_dump(mode="json")
                break
    if raw is None:
        return _invalid_request(tool_call, f"unknown compiled fact or set: {fact_id}")
    fact_set = CodeFactSetV1.model_validate(raw)
    replay_failures: list[str] = []
    proposal_raw = ctx.read_artifact("packet_proposals", lookup_id)
    validated_packet_raw = ctx.read_artifact("validated_packets", lookup_id)
    if requested_fact_set_id and (proposal_raw is None or validated_packet_raw is None):
        replay_failures.append("fact_set_replay_inputs_missing")
    if proposal_raw is not None and validated_packet_raw is not None:
        try:
            proposal = EvidencePacketProposalV1.model_validate(proposal_raw)
            persisted_packet = EvidencePacketV3.model_validate(validated_packet_raw)
            expected_packet, packet_report = compile_evidence_packet_proposal(
                proposal,
                ctx.behavior_graph,
                repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
                project_tree_hash=ctx.repo_snapshot.project_tree_hash,
                repo_snapshot=ctx.repo_snapshot,
            )
            if expected_packet is None or not packet_report.accepted:
                replay_failures.extend(
                    f"packet_replay:{failure}" for failure in packet_report.failures
                )
            elif persisted_packet.model_dump(mode="json") != expected_packet.model_dump(mode="json"):
                replay_failures.append("validated_packet_replay_mismatch")
            if expected_packet is not None:
                symbol_display_names = _symbol_display_names_for_nodes(
                    ctx,
                    proposal.behavior_node_ids,
                )
                expected_fact_set = compile_facts_from_behavior_graph(
                    ctx.behavior_graph,
                    FactCompilerInputV1(
                        obligation_id=proposal.obligation_id,
                        behavior_node_ids=proposal.behavior_node_ids,
                        behavior_relation_ids=proposal.behavior_relation_ids,
                        evidence_span_ids=[span.span_id for span in expected_packet.spans],
                        guards=proposal.conditions,
                        source_authority="executable_hard",
                        symbol_display_names=symbol_display_names,
                    ),
                    repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
                    project_tree_hash=ctx.repo_snapshot.project_tree_hash,
                    evidence_packet_digest=expected_packet.source_digest,
                )
                if expected_fact_set.model_dump(mode="json") != fact_set.model_dump(mode="json"):
                    replay_failures.append("fact_set_replay_mismatch")
        except Exception as exc:
            replay_failures.append(f"fact_set_replay_invalid:{type(exc).__name__}")
    packet_span_ids: set[str] = set()
    packet_root = ctx.artifact_root / "research_tool_artifacts" / "validated_packets"
    for path in sorted(packet_root.glob("*.json")) if packet_root.is_dir() else ():
        try:
            packet = EvidencePacketV3.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if packet.source_digest == fact_set.evidence_packet_digest:
            packet_span_ids.update(span.span_id for span in packet.spans)
    if not packet_span_ids:
        return _invalid_request(
            tool_call,
            "fact set does not replay to its evidence packet digest",
        )
    graph_relation_ids = {relation.relation_id for relation in ctx.behavior_graph.relations}
    failures: list[str] = [*replay_failures]
    selected = [fact for fact in fact_set.facts if fact.fact_id == fact_id] or fact_set.facts
    for fact in selected:
        failures.extend(f"{fact.fact_id}:{failure}" for failure in fact.validation_failures)
        for span_id in fact.direct_span_ids + fact.relation_span_ids:
            if span_id not in packet_span_ids:
                failures.append(f"{fact.fact_id}:unknown_packet_span:{span_id}")
        for relation_id in fact.relation_evidence_ids:
            if relation_id not in graph_relation_ids:
                failures.append(f"{fact.fact_id}:unknown_graph_relation:{relation_id}")
    report = {"fact_ids": [fact.fact_id for fact in selected], "failures": failures}
    report_path = ctx.write_artifact("fact_validation_reports", fact_id, report)
    assert report_path is not None
    if failures:
        return make_observation(
            tool_call=tool_call,
            status="invalid_request",
            source_authority="executable_hard",
            error_message=";".join(failures),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=tuple(failures) + (f"validator_report={report_path}",),
            ),
            output_payload=report,
        )

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(f"fact:validated:{fact.fact_id}" for fact in selected),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(selected),
            notes=(f"fact_id={fact_id}", "validation_passed", f"validator_report={report_path}"),
        ),
        output_payload=report,
    )


# ---------------------------------------------------------------------------
# decompose_atomic_claims
# ---------------------------------------------------------------------------


def decompose_atomic_claims(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Persist Agent-proposed fact groupings as typed claim proposals."""

    fact_ids = tuple(_arg_value(tool_call, "fact_ids", default=()) or ())
    if not fact_ids:
        return _invalid_request(tool_call, "fact_ids must not be empty")

    if ctx.artifact_root is None:
        return _invalid_request(tool_call, "claim data plane requires artifact_root")
    fact_set_id = str(_arg_value(tool_call, "fact_set_id", default="") or "")
    raw = ctx.read_artifact("fact_sets", fact_set_id) if fact_set_id else None
    if raw is None:
        return _invalid_request(tool_call, "fact_set_id must name a compiled fact set")
    fact_set = CodeFactSetV1.model_validate(raw)
    facts_by_id = {fact.fact_id: fact for fact in fact_set.facts}
    missing = [fact_id for fact_id in fact_ids if fact_id not in facts_by_id]
    if missing:
        return _invalid_request(tool_call, f"unknown facts: {','.join(missing)}")
    proposal_payloads = list(_arg_value(tool_call, "claim_proposals", default=()) or ())
    if not proposal_payloads:
        return _invalid_request(tool_call, "claim_proposals must not be empty")
    try:
        proposals = [ClaimProposalV1.model_validate(value) for value in proposal_payloads]
    except Exception as exc:
        return _invalid_request(tool_call, f"invalid claim proposal: {exc}")
    proposed_fact_ids = {fid for proposal in proposals for fid in proposal.proposed_fact_ids}
    if not proposed_fact_ids.issubset(set(fact_ids)):
        return _invalid_request(tool_call, "claim proposal references facts outside fact_ids")
    proposal_set_id = "claim-proposals-" + hashlib.sha256(
        json.dumps(
            [proposal.model_dump(mode="json") for proposal in proposals],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    artifact = {
        "proposal_set_id": proposal_set_id,
        "fact_set_id": fact_set_id,
        "proposals": [proposal.model_dump(mode="json") for proposal in proposals],
    }
    proposal_path = ctx.write_artifact("claim_proposal_sets", proposal_set_id, artifact)
    assert proposal_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(f"claim:proposed:{proposal.claim_id}" for proposal in proposals),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(proposals),
            notes=(
                f"facts={len(fact_ids)}",
                f"proposal_set_id={proposal_set_id}",
                f"artifact={proposal_path}",
            ),
        ),
        output_payload=artifact,
    )


# ---------------------------------------------------------------------------
# authorize_atomic_claims
# ---------------------------------------------------------------------------


def authorize_atomic_claims(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Authorize persisted claim proposals against their exact fact set."""

    claim_ids = tuple(_arg_value(tool_call, "claim_ids", default=()) or ())
    if not claim_ids:
        return _invalid_request(tool_call, "claim_ids must not be empty")

    if ctx.artifact_root is None:
        return _invalid_request(tool_call, "claim data plane requires artifact_root")
    proposal_set_id = str(_arg_value(tool_call, "proposal_set_id", default="") or "")
    raw = ctx.read_artifact("claim_proposal_sets", proposal_set_id)
    if raw is None:
        return _invalid_request(tool_call, "proposal_set_id must name claim proposals")
    proposals = [ClaimProposalV1.model_validate(value) for value in raw["proposals"]]
    requested = {claim_id.removeprefix("claim:proposed:") for claim_id in claim_ids}
    proposals = [proposal for proposal in proposals if proposal.claim_id in requested]
    if len(proposals) != len(requested):
        return _invalid_request(tool_call, "one or more claim ids are not in proposal set")
    fact_set_id = str(raw["fact_set_id"])
    fact_raw = ctx.read_artifact("fact_sets", fact_set_id)
    if fact_raw is None:
        return _invalid_request(tool_call, f"missing fact set: {fact_set_id}")
    facts = CodeFactSetV1.model_validate(fact_raw)
    claim_set, reports = compile_atomic_claims(
        proposals,
        facts,
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        project_tree_hash=ctx.repo_snapshot.project_tree_hash,
        evidence_packet_digest=facts.evidence_packet_digest,
    )
    report_payload = [report.model_dump(mode="json") for report in reports]
    report_path = ctx.write_artifact(
        "claim_authorization_reports", proposal_set_id, report_payload
    )
    assert report_path is not None
    failures = [
        failure
        for report in reports
        for failure in report.failures
    ]
    if failures and not claim_set.claims:
        return make_observation(
            tool_call=tool_call,
            status="invalid_request",
            source_authority="executable_hard",
            error_message=";".join(failures),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=tuple(failures) + (f"validator_report={report_path}",),
            ),
            output_payload=report_payload,
        )
    claim_path = ctx.write_artifact("authorized_claim_sets", proposal_set_id, claim_set)
    assert claim_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=tuple(
            f"claim:authorized:{claim.claim_id}" for claim in claim_set.claims
        ),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=len(claim_set.claims),
            notes=(
                f"claims={len(claim_set.claims)}",
                f"rejected_claims={sum(bool(report.failures) for report in reports)}",
                f"artifact={claim_path}",
                f"validator_report={report_path}",
                *(f"rejected:{failure}" for failure in failures),
            ),
        ),
        output_payload=claim_set.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# record_explicit_code_gap
# ---------------------------------------------------------------------------


def record_explicit_code_gap(
    ctx: ResearchToolContext,
    tool_call: ResearchToolCallV1,
) -> ResearchObservationV1:
    """Validate and persist one idempotent terminal gap per obligation."""

    obligation_id_ref = str(_arg_value(tool_call, "obligation_id_ref", default="") or "")
    termination_reason = str(_arg_value(tool_call, "termination_reason", default="") or "")
    if not obligation_id_ref.strip():
        return _invalid_request(tool_call, "obligation_id_ref must not be empty")
    if obligation_id_ref != tool_call.obligation_id:
        return _invalid_request(tool_call, "gap obligation does not match active obligation")
    if not termination_reason.strip():
        return _invalid_request(tool_call, "termination_reason must not be empty")
    if ctx.artifact_root is None:
        return _invalid_request(tool_call, "gap data plane requires artifact_root")
    search_scope = tuple(
        _arg_value(tool_call, "search_scope", default=())
        or tool_call.path_scope
        or ()
    )
    # ``search_scope`` is terminal-gap provenance. Normalize it through the
    # frozen snapshot resolver instead of trusting an absolute/external path.
    # Otherwise a caller could record an apparently exhaustive gap for files
    # that were never part of the researched tree.
    normalized_search_scope: list[str] = []
    for candidate in search_scope:
        normalized = ctx.resolve_snapshot_path(str(candidate))
        if normalized is None:
            failure = f"gap_search_scope_outside_snapshot:{candidate}"
            return make_observation(
                tool_call=tool_call,
                status="invalid_request",
                source_authority="executable_hard",
                error_message=failure,
                diagnostics=ResearchObservationDiagnosticsV1(
                    candidate_count=0,
                    notes=(failure,),
                ),
                output_payload={"failures": [failure]},
            )
        if normalized not in normalized_search_scope:
            normalized_search_scope.append(normalized)
    search_scope = tuple(normalized_search_scope)
    attempted_tools = tuple(
        _arg_value(tool_call, "attempted_tools", default=()) or ()
    )
    missing_relations = tuple(
        _arg_value(tool_call, "missing_relations", default=()) or ()
    )
    search_complete = bool(
        _arg_value(tool_call, "search_complete", default=False)
    )
    scope_exhausted = bool(
        _arg_value(tool_call, "scope_exhausted", default=False)
    )
    failures: list[str] = []
    if not search_scope:
        failures.append("gap_search_scope_missing")
    if not search_complete:
        failures.append("gap_search_not_complete")
    if not any(
        name in attempted_tools
        for name in ("search_code", "search_symbols", "find_entrypoints")
    ):
        failures.append("gap_search_strategy_missing_discovery")
    if not scope_exhausted and not any(
        name in attempted_tools
        for name in ("read_symbol", "read_code_span", "build_behavior_subgraph")
    ):
        failures.append("gap_search_strategy_missing_read")
    if missing_relations and not any(
        name in attempted_tools
        for name in (
            "find_references",
            "trace_call_path",
            "trace_data_flow",
            "inspect_control_flow",
            "inspect_configuration",
        )
    ):
        failures.append("gap_missing_relation_not_traced")

    claim_root = (
        ctx.artifact_root / "research_tool_artifacts" / "authorized_claim_sets"
    )
    for path in sorted(claim_root.glob("*.json")) if claim_root.is_dir() else ():
        claim_set = AtomicClaimSetV3.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if any(
            obligation_id_ref in claim.covers_obligation_ids
            and claim.status in {"supported", "partial"}
            for claim in claim_set.claims
        ):
            failures.append("gap_contradicts_authorized_positive_claim")
            break
    if failures:
        return make_observation(
            tool_call=tool_call,
            status="invalid_request",
            source_authority="executable_hard",
            error_message=";".join(failures),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=0,
                notes=tuple(failures),
            ),
            output_payload={"failures": failures},
        )

    gap_id = "gap-" + hashlib.sha256(
        f"{ctx.repo_snapshot.snapshot_id}:{obligation_id_ref}".encode("utf-8")
    ).hexdigest()[:16]
    payload = {
        "gap_id": gap_id,
        "obligation_id": obligation_id_ref,
        "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
        "project_tree_hash": ctx.repo_snapshot.project_tree_hash,
        "search_scope": list(search_scope),
        "attempted_tools": list(attempted_tools),
        "missing_relations": list(missing_relations),
        "termination_reason": termination_reason,
        "search_complete": True,
        "scope_exhausted": scope_exhausted,
        "terminal": True,
    }
    existing = ctx.read_artifact("terminal_gaps", obligation_id_ref)
    replayed = existing is not None
    if existing is not None and existing != payload:
        return _invalid_request(
            tool_call,
            "terminal gap already exists with different provenance",
        )
    gap_path = ctx.write_artifact("terminal_gaps", obligation_id_ref, payload)
    assert gap_path is not None

    return make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=(f"gap:{gap_id}",),
        diagnostics=ResearchObservationDiagnosticsV1(
            candidate_count=1,
            notes=(
                f"obligation={obligation_id_ref}",
                f"reason={termination_reason}",
                f"artifact={gap_path}",
                f"idempotent_replay={str(replayed).lower()}",
            ),
        ),
        output_payload=payload,
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
    normalized = raw.replace("\\", "/")
    # Do not turn an external path into an apparently snapshot-relative path.
    # ``lstrip('/.')`` used to accept ``/src/x.py`` and ``../src/x.py`` when
    # the stripped suffix happened to exist in the frozen repository.
    if normalized.startswith(("/", "//")) or re.match(r"^[A-Za-z]:/", normalized):
        return None
    if ".." in PurePosixPath(normalized).parts:
        return None
    while normalized.startswith("./"):
        normalized = normalized[2:]
    cleaned = normalized.rstrip("/")
    if not cleaned or cleaned == ".":
        return None
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
        return "javascript_entrypoint" if lowered.endswith((".js", ".ts")) else "python_entrypoint"
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
    normalized: list[str] = []
    for token in re.findall(r"[a-z0-9]+", expanded.casefold()):
        if not (len(token) >= 3 or token.isdigit() or token == "qa"):
            continue
        if token in _SYMBOL_QUERY_STOP_WORDS:
            continue
        normalized.append(
            "dimension" if token in {"dim", "dims", "dimensional"} else token
        )
    # Common repository identifiers compact an output width as ``f15``,
    # ``d128`` or ``dim256``.  Treat those as retrieval aliases for an author
    # phrase such as "15-dimensional"; this only ranks candidates and does
    # not authorize a dimensional claim.
    numeric_dimensions = [
        token
        for token in normalized
        if token.isdigit()
    ] if "dimension" in normalized else []
    for width in numeric_dimensions:
        for alias in (f"f{width}", f"d{width}", f"dim{width}"):
            if alias not in normalized:
                normalized.append(alias)
    return tuple(normalized)


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
            elif (
                min(len(query_token), len(symbol_token)) >= 4
                and (query_token in symbol_token or symbol_token in query_token)
            ):
                best = max(best, 5)
            elif _common_prefix_length(query_token, symbol_token) >= 4:
                best = max(best, 3)
        if best == 0 and any(
            query_token == path_token
            or (
                min(len(query_token), len(path_token)) >= 4
                and (query_token in path_token or path_token in query_token)
            )
            or _common_prefix_length(query_token, path_token) >= 4
            for path_token in path_tokens
        ):
            best = 1
        score += best
    return score


def _symbol_source_query_score(
    ctx: ResearchToolContext,
    entry: SymbolIndexEntry,
    query: str,
    *,
    source_cache: dict[str, list[str]],
) -> int:
    """Return a weak lexical retrieval score from one exact symbol body.

    This score only ranks symbol hints.  ``search_symbols`` still emits no
    exact spans, so positive evidence must pass through ``read_symbol``.
    Source-body matching lets abstract queries such as ``CONCAT`` retrieve a
    function implemented with ``torch.cat`` even when its identifier contains
    no form of the word "concatenate".
    """

    query_tokens = _identifier_tokens(query)
    if not query_tokens:
        return 0
    lines = source_cache.get(entry.path)
    if lines is None:
        text, error = _read_snapshot_file(ctx.repo_snapshot, entry.path)
        lines = [] if error is not None else text.splitlines()
        source_cache[entry.path] = lines
    if not lines:
        return 0
    start = max(0, entry.start_line - 1)
    end = min(len(lines), max(entry.end_line, entry.start_line))
    body_tokens = set(_identifier_tokens("\n".join(lines[start:end])))
    score = 0
    for query_token in query_tokens:
        if query_token in body_tokens:
            score += 3
        elif any(
            (
                min(len(query_token), len(token)) >= 4
                and (query_token in token or token in query_token)
            )
            or _common_prefix_length(query_token, token) >= 4
            for token in body_tokens
        ):
            score += 1
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


_JS_BUILD_CONFIG_NAMES = frozenset({
    "package.json",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "jsconfig.json",
    "webpack.config.js",
    "vite.config.js",
    "vite.config.ts",
    "rollup.config.js",
    "rollup.config.ts",
    "esbuild.config.js",
    "babel.config.js",
    "babel.config.cjs",
    "jest.config.js",
    "jest.config.ts",
})


def _find_javascript_config_bindings(
    rel_path: str,
    source: str,
    config_key: str,
) -> Iterable[tuple[int, str]]:
    """Yield conservative JS/TS runtime and build configuration bindings.

    This is deliberately lexical rather than a JavaScript evaluator.  The
    returned key records the observable access (for example ``env:PORT`` or
    ``config:batchSize``), while unresolved computed properties remain a
    discovery result and cannot become a positive fact without a behavior
    relation.  JSON build manifests are scanned by line so every result keeps
    an exact source span anchor.
    """

    key_lower = config_key.strip().lower()
    filename = Path(rel_path).name.lower()
    lines = source.splitlines()
    found: list[tuple[int, str]] = []

    def emit(line_no: int, key: str) -> None:
        clean = key.strip()
        if not clean:
            return
        if key_lower and key_lower not in clean.lower():
            return
        item = (line_no, clean)
        if item not in found:
            found.append(item)

    # JSON manifests/config files are executable build inputs under the
    # source-authority policy.  Keep only semantically useful keys rather than
    # every dependency leaf, which prevents a large package-lock from
    # drowning out entrypoint/configuration evidence.
    if rel_path.lower().endswith(".json"):
        useful = re.compile(
            r"\"(scripts|dependencies|devDependencies|peerDependencies|"
            r"optionalDependencies|main|module|exports|bin|type|engines|"
            r"build|compilerOptions|paths|baseUrl|target|module|jsx|include|"
            r"exclude|rootDir|outDir|extends|alias|plugins|resolve|loader)\""
            r"\s*:"
        )
        for line_no, line in enumerate(lines, start=1):
            for match in useful.finditer(line):
                emit(line_no, f"manifest:{match.group(1)}")
        if filename in _JS_BUILD_CONFIG_NAMES and not found:
            emit(1, f"build:{filename}")
        return found

    for line_no, line in enumerate(lines, start=1):
        # Runtime environment/configuration reads.
        for match in re.finditer(
            r"\bprocess\.env(?:\.([A-Za-z_$][\w$]*)|\[\s*['\"]([^'\"]+)['\"]\s*\])",
            line,
        ):
            emit(line_no, f"env:{match.group(1) or match.group(2)}")
        for match in re.finditer(
            r"\bimport\.meta\.env\.([A-Za-z_$][\w$]*)", line
        ):
            emit(line_no, f"env:{match.group(1)}")
        for match in re.finditer(
            r"\b(config|configuration|options?|argv|args)\s*\.\s*([A-Za-z_$][\w$]*)",
            line,
        ):
            emit(line_no, f"{match.group(1).lower()}:{match.group(2)}")
        if re.search(r"\bprocess\.argv\b|\bimport\.meta\.url\b", line):
            emit(line_no, "runtime:argv_or_module_url")

        # Common JS/TS configuration APIs and build entrypoint declarations.
        if re.search(r"\bdefineConfig\s*\(|\bloadConfigFromFile\s*\(", line):
            emit(line_no, f"build:{filename}:define_config")
        if re.search(r"\bdotenv\s*\.\s*config\s*\(", line):
            emit(line_no, "runtime:dotenv")
        if re.search(r"\byargs(?:\.option|\.options)\s*\(", line):
            emit(line_no, "runtime:cli_options")
        if re.search(r"\b(webpack|vite|rollup|esbuild|babel|jest)\b", line):
            emit(line_no, f"build:{filename}:tool_reference")

    if filename in _JS_BUILD_CONFIG_NAMES and not found:
        emit(1, f"build:{filename}")
    return found


def _is_build_configuration_binding(path: str, key: str) -> bool:
    filename = Path(path).name.lower()
    return filename in _JS_BUILD_CONFIG_NAMES or key.lower().startswith("build:") or key.lower().startswith("manifest:")


def _is_runtime_configuration_binding(path: str, key: str) -> bool:
    del path
    lowered = key.lower()
    return lowered.startswith(("env:", "runtime:", "config:", "configuration:", "option:", "options:", "argv:", "args:"))


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

    - ``downstream``: assignments where ``symbol_name`` is the target;
    - ``upstream``: return statements referencing ``symbol_name``;
    - ``both``: both directions.
    """

    for node in ast.walk(tree):
        if direction in ("downstream", "both") and isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == symbol_name:
                    yield int(getattr(node, "lineno", 0) or 0)
                elif isinstance(target, ast.Attribute) and target.attr == symbol_name:
                    yield int(getattr(node, "lineno", 0) or 0)
        if direction in ("upstream", "both") and isinstance(node, ast.Return):
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
