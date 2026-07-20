"""R2.2 incremental behavior subgraph builder.

Implements ``build_behavior_subgraph(symbol_ids, depth, node_budget)``
from design section 7.2 and the R2.2 execution plan:

- only parses the selected symbols (and their callees up to ``depth``);
- node and relation ids are stable across calls (derived from
  snapshot/symbol/span), so repeated calls deduplicate via
  ``CodeBehaviorGraphV1.merge``;
- respects ``node_budget``: when the budget is hit, the build truncates
  and records a warning rather than silently exceeding the budget;
- interprocedural CALLS relations are resolved through the symbol index;
  dynamic / external calls are recorded as ``UnresolvedRelationV1``.

This is the bridge between the V3 research tools (which locate symbols)
and the V3 fact compiler (which needs a behavior graph to derive claims).
The supervisor calls this tool after ``find_entrypoints`` /
``search_symbols`` / ``read_symbol`` have identified the symbols worth
modeling, and before ``query_behavior_graph`` / ``trace_call_path``
query the resulting subgraph.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    SymbolIndexV2,
    SymbolRefV1,
    UnresolvedRelationV1,
    make_span_id,
)
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter
from code2paper.agentic.source_authority import classify_source_authority


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class BehaviorSubgraphResult(BaseModel):
    """Result of ``build_behavior_subgraph``."""

    model_config = ConfigDict(extra="forbid")

    graph: CodeBehaviorGraphV1
    covered_symbol_ids: tuple[str, ...] = ()
    truncated: bool = False
    node_count: int = 0
    relation_count: int = 0
    unresolved_count: int = 0
    warnings: tuple[str, ...] = ()
    depth_reached: int = 0


# ---------------------------------------------------------------------------
# Input schema (for the StructuredTool wrapper in R2.5)
# ---------------------------------------------------------------------------


class BuildBehaviorSubgraphInput(BaseModel):
    """Input schema for the ``build_behavior_subgraph`` StructuredTool."""

    model_config = ConfigDict(extra="forbid")

    tool_call_id: str
    obligation_id: str
    goal: str
    repo_snapshot_id: str
    path_scope: tuple[str, ...] = ()
    top_k: int = 0
    depth: int = 0
    node_budget: int = 1000
    symbol_ids: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def build_behavior_subgraph(
    *,
    adapter: PythonBehaviorAdapter,
    repo_snapshot_id: str,
    project_tree_hash: str,
    files: dict[str, str],
    symbol_index: SymbolIndexV2,
    symbol_ids: list[str] | tuple[str, ...],
    depth: int = 0,
    node_budget: int = 1000,
) -> BehaviorSubgraphResult:
    """Build an incremental behavior subgraph for the requested symbols.

    Parameters
    ----------
    adapter
        The language adapter (Python for R2).
    repo_snapshot_id, project_tree_hash
        Identity of the snapshot the subgraph is bound to.  The resulting
        graph records these so a checkpoint resume can detect drift.
    files
        ``{relative_path: source_text}`` for every file in the snapshot.
        Only files referenced by the selected symbols are parsed.
    symbol_index
        The V2 symbol index produced by ``adapter.index_symbols``.  Used
        to resolve interprocedural call targets.
    symbol_ids
        The starting set of symbol ids to parse.
    depth
        How many hops of interprocedural callees to follow.  ``depth=0``
        parses only the requested symbols; ``depth=1`` adds their direct
        callees; etc.
    node_budget
        Hard cap on total nodes.  When hit, the build truncates and
        records a warning.
    """

    if depth < 0:
        raise ValueError(f"depth must be non-negative, got {depth}")
    if node_budget <= 0:
        raise ValueError(f"node_budget must be positive, got {node_budget}")

    worklist: deque[tuple[str, int]] = deque()
    seen_symbols: set[str] = set()
    for sid in symbol_ids:
        if sid not in seen_symbols:
            seen_symbols.add(sid)
            worklist.append((sid, 0))

    graph = CodeBehaviorGraphV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        language=adapter.language,
    )
    warnings: list[str] = []
    truncated = False
    depth_reached = 0
    total_nodes = 0

    while worklist:
        symbol_id, current_depth = worklist.popleft()
        if total_nodes >= node_budget:
            truncated = True
            warnings.append(
                f"node_budget_reached:{node_budget}:skipped:{symbol_id}"
            )
            continue
        sym = symbol_index.find(symbol_id)
        if sym is None:
            warnings.append(f"symbol_not_in_index:{symbol_id}")
            continue
        source = files.get(sym.path)
        if source is None:
            warnings.append(f"source_not_found:{sym.path}")
            continue
        # Extract nodes and intra-symbol relations for this symbol.
        nodes = adapter.extract_operations(sym, source)
        relations = adapter.extract_relations(sym, source, nodes)
        # Bound by remaining node budget.
        remaining = node_budget - total_nodes
        if len(nodes) > remaining:
            nodes = nodes[:remaining]
            relations = _filter_relations_for_nodes(relations, nodes)
            truncated = True
            warnings.append(
                f"node_budget_truncated:{sym.qualified_name}:{remaining}"
            )
        # Extract interprocedural relations (CALLS / RETURNS_TO).
        inter_calls, inter_unresolved, callee_ids = _extract_interprocedural_calls(
            symbol=sym,
            nodes=nodes,
            symbol_index=symbol_index,
        )
        sym_graph = CodeBehaviorGraphV1(
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            language=adapter.language,
            nodes=nodes,
            relations=[*relations, *inter_calls],
            unresolved_relations=inter_unresolved,
        )
        graph = graph.merge(sym_graph)
        total_nodes = len(graph.nodes)
        depth_reached = max(depth_reached, current_depth)
        # Queue callee symbols for the next depth hop.
        if current_depth < depth:
            for callee_id in callee_ids:
                if callee_id not in seen_symbols:
                    seen_symbols.add(callee_id)
                    worklist.append((callee_id, current_depth + 1))

    graph = graph.with_digest()
    return BehaviorSubgraphResult(
        graph=graph,
        covered_symbol_ids=tuple(sorted(seen_symbols)),
        truncated=truncated,
        node_count=len(graph.nodes),
        relation_count=len(graph.relations),
        unresolved_count=len(graph.unresolved_relations),
        warnings=tuple(warnings),
        depth_reached=depth_reached,
    )


# ---------------------------------------------------------------------------
# Interprocedural call resolution
# ---------------------------------------------------------------------------


def _extract_interprocedural_calls(
    *,
    symbol: SymbolRefV1,
    nodes: list[BehaviorNodeV1],
    symbol_index: SymbolIndexV2,
) -> tuple[list[BehaviorRelationV1], list[UnresolvedRelationV1], list[str]]:
    """Resolve call-derived nodes to interprocedural CALLS relations.

    Returns ``(relations, unresolved, callee_symbol_ids)``.  A call is
    resolved when the target name matches a symbol in the index; otherwise
    it is recorded as ``unresolved`` with a reason.

    A node is "call-derived" if it was produced from an ``ast.Call``.  The
    Python adapter tags every such node with a diagnostic starting with
    ``qualified:``, ``method:``, ``attr:``, ``name:`` or ``unknown_func`` /
    ``open_call`` / ``file_open_*`` / ``print_call`` / ``file_write:*``.
    Specialized predicates (SORT / TOPK / NORMALIZE / ...) are all
    call-derived and MUST be considered here so that, e.g.,
    ``torch.softmax`` is recorded as an unresolved external call.
    """

    relations: list[BehaviorRelationV1] = []
    unresolved: list[UnresolvedRelationV1] = []
    callee_ids: list[str] = []
    # Build a name -> SymbolRefV1 lookup from the index.  We match on the
    # final component of the qualified name (e.g. ``Trainer.train_loop``
    # matches calls to ``train_loop`` and ``self.train_loop``).
    by_short_name: dict[str, list[SymbolRefV1]] = {}
    for sym in symbol_index.symbols:
        short = sym.qualified_name.split(".")[-1]
        by_short_name.setdefault(short, []).append(sym)
    for node in nodes:
        if not _is_call_derived(node):
            continue
        if not node.operands:
            continue
        target_name = node.operands[0]
        # Strip "self." / "cls." prefixes and module qualifiers.
        short = target_name.split(".")[-1]
        candidates = by_short_name.get(short, [])
        # Exclude self-calls (a symbol calling itself is intra-symbol).
        candidates = [c for c in candidates if c.symbol_id != symbol.symbol_id]
        if not candidates:
            # Could be a builtin, an external library call, or a dynamic call.
            unresolved.append(
                UnresolvedRelationV1(
                    relation_id=f"unres:{node.node_id}:CALLS",
                    kind="CALLS",
                    source_node_id=node.node_id,
                    source_symbol_id=symbol.symbol_id,
                    source_span_id=node.source_span_id,
                    reason=_classify_unresolved_reason(target_name),
                    target_hint=target_name,
                )
            )
            continue
        # Prefer an exact qualified-name match; otherwise take the first candidate.
        target_sym = candidates[0]
        for c in candidates:
            if c.qualified_name == target_name:
                target_sym = c
                break
        rel = BehaviorRelationV1(
            relation_id=BehaviorRelationV1.make_relation_id(
                kind="CALLS",
                source_node_id=node.node_id,
                target_node_id="",
                seq=0,
            ),
            kind="CALLS",
            source_node_id=node.node_id,
            target_node_id="",
            source_symbol_id=symbol.symbol_id,
            target_symbol_id=target_sym.symbol_id,
            source_span_id=node.source_span_id,
            target_span_id=make_span_id(target_sym.path, target_sym.start_line, target_sym.end_line),
            argument_binding={},
            confidence=0.9,
        )
        relations.append(rel)
        callee_ids.append(target_sym.symbol_id)
    return relations, unresolved, callee_ids


_CALL_DERIVED_DIAGNOSTIC_PREFIXES: tuple[str, ...] = (
    "qualified:",
    "method:",
    "attr:",
    "name:",
    "unknown_func",
    "open_call",
    "file_open_",
    "print_call",
    "file_write:",
)


def _is_call_derived(node: BehaviorNodeV1) -> bool:
    """Return True if the node was produced from an ``ast.Call``."""

    for diag in node.diagnostics:
        for prefix in _CALL_DERIVED_DIAGNOSTIC_PREFIXES:
            if diag.startswith(prefix) or diag == prefix:
                return True
    return False


def _classify_unresolved_reason(target_name: str) -> str:
    """Classify why a call target could not be resolved statically."""

    short = target_name.split(".")[-1]
    # Builtins and common external libraries.
    if short in {"print", "len", "range", "int", "float", "str", "list", "dict", "set", "tuple", "bool", "open", "isinstance", "issubclass", "super", "type"}:
        return "builtin"
    # Common ML / scientific libraries that are not part of the snapshot.
    qualifier = target_name.split(".")[0] if "." in target_name else ""
    if qualifier in {"torch", "torchvision", "numpy", "np", "scipy", "sklearn", "pandas", "pd", "matplotlib", "plt", "tqdm", "PIL", "cv2", "transformers", "datasets", "accelerate"}:
        return "external_module"
    if "getattr" in target_name or "setattr" in target_name or "eval" in target_name or "exec" in target_name:
        return "reflection"
    return "dynamic_call"


def _filter_relations_for_nodes(
    relations: list[BehaviorRelationV1],
    kept_nodes: list[BehaviorNodeV1],
) -> list[BehaviorRelationV1]:
    """Keep only relations whose source/target node is in ``kept_nodes``."""

    kept_ids = {n.node_id for n in kept_nodes}
    return [
        r
        for r in relations
        if r.source_node_id in kept_ids
        and (not r.target_node_id or r.target_node_id in kept_ids)
    ]


__all__ = [
    "BehaviorSubgraphResult",
    "BuildBehaviorSubgraphInput",
    "build_behavior_subgraph",
]
