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
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    SymbolIndexV2,
    SymbolRefV1,
    UnresolvedRelationV1,
    make_span_id,
    LanguageBehaviorAdapter,
)
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
    adapter: LanguageBehaviorAdapter,
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
    attribute_types = _adapter_instance_attribute_types(adapter, files)
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
            instance_attribute_types=attribute_types,
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
    graph = _bind_resolved_call_target_nodes(graph)
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


def _bind_resolved_call_target_nodes(
    graph: CodeBehaviorGraphV1,
) -> CodeBehaviorGraphV1:
    """Bind symbol-level CALLS edges to the callee's first AST operation.

    ``target_symbol_id`` is the authoritative inter-symbol binding.  When a
    callee body was included by the requested depth, adding its first
    operation as ``target_node_id`` makes the edge traversable by downstream
    closure compilers.  A depth-zero graph intentionally keeps the target
    node empty because no callee body was observed.
    """

    first_node_by_symbol: dict[str, BehaviorNodeV1] = {}
    for node in sorted(
        graph.nodes,
        key=lambda item: (item.symbol_id, _span_sort_key(item.source_span_id), item.node_id),
    ):
        first_node_by_symbol.setdefault(node.symbol_id, node)
    changed = False
    relations: list[BehaviorRelationV1] = []
    seen_ids: set[str] = set()
    for relation in graph.relations:
        target_node = relation.target_node_id
        if relation.kind == "CALLS" and not target_node and relation.target_symbol_id:
            target = first_node_by_symbol.get(relation.target_symbol_id)
            if target is not None:
                target_node = target.node_id
        if target_node == relation.target_node_id:
            updated = relation
        else:
            updated = relation.model_copy(update={
                "target_node_id": target_node,
                "relation_id": BehaviorRelationV1.make_relation_id(
                    kind=relation.kind,
                    source_node_id=relation.source_node_id,
                    target_node_id=target_node,
                    seq=0,
                ),
            })
            changed = True
        if updated.relation_id in seen_ids:
            continue
        seen_ids.add(updated.relation_id)
        relations.append(updated)
    if not changed and len(relations) == len(graph.relations):
        return graph
    return CodeBehaviorGraphV1(
        schema_version=graph.schema_version,
        repo_snapshot_id=graph.repo_snapshot_id,
        project_tree_hash=graph.project_tree_hash,
        language=graph.language,
        nodes=list(graph.nodes),
        relations=relations,
        unresolved_relations=list(graph.unresolved_relations),
        warnings=list(graph.warnings),
    ).with_digest()


def _span_sort_key(span_id: str) -> tuple[str, int, int]:
    parts = str(span_id or "").rsplit(":", 2)
    if len(parts) == 3:
        try:
            return parts[0], int(parts[1]), int(parts[2])
        except ValueError:
            pass
    return str(span_id or ""), 10**9, 10**9


def _resolve_call_target(
    *,
    symbol: SymbolRefV1,
    target_name: str,
    by_short_name: dict[str, list[SymbolRefV1]],
    by_qualified_name: dict[str, list[SymbolRefV1]],
    by_parent_name: dict[str, list[SymbolRefV1]] | None = None,
    instance_attribute_types: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[SymbolRefV1 | None, str]:
    """Resolve a Python call using lexical ownership before short names.

    A final-component lookup is unsafe for methods because every model layer
    commonly defines ``forward``.  ``self.method`` is therefore restricted
    to the current class; a bare call prefers the current file and lexical
    parent; qualified calls require an exact qualified-name match.  Multiple
    remaining candidates are returned as an explicit ambiguity rather than
    guessed.
    """

    raw = str(target_name or "").strip()
    if not raw:
        return None, "dynamic_call"
    short = raw.split(".")[-1]
    candidates = list(by_short_name.get(short, ()))
    candidates = [item for item in candidates if item.symbol_id != symbol.symbol_id]
    if not candidates and not (
        raw.startswith("self.") and raw.count(".") == 1
    ):
        return None, _classify_unresolved_reason(raw)

    if raw.startswith("self."):
        # ``self.<method>`` is a same-class call.  ``self.<attr>.<method>`` is a
        # submodule/attribute chain: without instance attribute type
        # resolution it must stay unresolved instead of binding to the
        # caller's own method of the same name.
        if raw.count(".") > 1:
            return None, "dynamic_call"
        parent_id = str(symbol.parent_symbol_id or "")
        same_parent = [
            item for item in candidates
            if item.kind == "method" and parent_id and item.parent_symbol_id == parent_id
        ]
        if len(same_parent) == 1:
            return same_parent[0], ""
        if len(same_parent) > 1:
            return None, "ambiguous_call_target"
        # ``self.<attr>(...)`` on an instance attribute: bind it to the
        # submodule class's ``forward`` when the class body assigned the
        # attribute to a same-file class constructor.
        submodule = _resolve_submodule_call_target(
            symbol=symbol,
            attribute=raw.split(".", 1)[1],
            by_parent_name=by_parent_name or {},
            instance_attribute_types=instance_attribute_types or {},
        )
        if submodule is not None:
            return submodule, ""
        return None, "dynamic_call"

    if raw.startswith("super(") or raw.startswith("super()."):
        return None, "dynamic_call"

    exact = [item for item in by_qualified_name.get(raw, ()) if item.symbol_id != symbol.symbol_id]
    if len(exact) == 1:
        return exact[0], ""
    if len(exact) > 1:
        return None, "ambiguous_call_target"

    # A dotted receiver that is neither ``self`` nor ``super()`` is an
    # attribute call on another object or module.  Same-file/same-class
    # short-name binding would fabricate an edge (``other.forward`` -> this
    # class's ``forward``), so it must be resolved from the receiver itself.
    if "." in raw:
        receiver_leaf = raw.rsplit(".", 1)[0].split(".")[-1]
        module_matches = [
            item for item in candidates
            if _receiver_matches_symbol(receiver_leaf, item)
        ]
        if len(module_matches) == 1:
            return module_matches[0], ""
        if len(module_matches) > 1:
            return None, "ambiguous_call_target"
        return None, _classify_unresolved_reason(raw)

    same_file = [item for item in candidates if item.path == symbol.path]
    same_parent = [
        item for item in same_file
        if symbol.parent_symbol_id
        and item.parent_symbol_id == symbol.parent_symbol_id
    ]
    # A bare method call inside a class is bound to a same-class method.  A
    # module-level bare function is bound to a unique same-file definition.
    if len(same_parent) == 1:
        return same_parent[0], ""
    if len(same_parent) > 1:
        return None, "ambiguous_call_target"
    if len(same_file) == 1:
        return same_file[0], ""
    if len(same_file) > 1:
        return None, "ambiguous_call_target"
    if len(candidates) == 1:
        return candidates[0], ""
    return None, "ambiguous_call_target"


def _receiver_matches_symbol(receiver_leaf: str, symbol: SymbolRefV1) -> bool:
    """Whether a dotted receiver name identifies this symbol's module/class.

    ``utils.helper()`` may bind to ``helper`` only when the receiver names the
    symbol's module stem or its lexical parent.  This keeps cross-module calls
    resolvable without ever guessing from a globally unique short name.
    """

    receiver = str(receiver_leaf or "").strip()
    if not receiver:
        return False
    parent_name = str(symbol.parent_symbol_id or "").strip()
    qualified_parent = (
        symbol.qualified_name.rsplit(".", 1)[0]
        if "." in symbol.qualified_name
        else ""
    )
    module_stem = str(symbol.path or "").rsplit("/", 1)[-1]
    if module_stem.endswith(".py"):
        module_stem = module_stem[:-3]
    return receiver in {
        qualified_parent.split(".")[-1],
        module_stem,
        parent_name,
    } and bool(receiver)


def _resolve_submodule_call_target(
    *,
    symbol: SymbolRefV1,
    attribute: str,
    by_parent_name: Mapping[str, list[SymbolRefV1]],
    instance_attribute_types: Mapping[str, Mapping[str, str]],
) -> SymbolRefV1 | None:
    """Resolve ``self.<attribute>(...)`` through its assigned class.

    ``self.model = Encoder(...)`` makes ``self.model(x)`` a call of
    ``Encoder.__call__`` (``forward`` in PyTorch modules).  The binding is only
    accepted when the same file declares exactly one such method; anything
    else stays unresolved.
    """

    caller_class = (
        symbol.qualified_name.rsplit(".", 1)[0]
        if "." in symbol.qualified_name
        else ""
    )
    if not caller_class:
        return None
    attribute_types = instance_attribute_types.get(
        f"{symbol.path}::{caller_class.split('.')[-1]}", {}
    )
    target_key = str(attribute_types.get(attribute, "") or "").strip()
    if "::" not in target_key:
        return None
    target_path, target_class = target_key.split("::", 1)
    members = [
        item
        for parent_name, items in by_parent_name.items()
        if parent_name.split(".")[-1] == target_class
        for item in items
        if item.path == target_path and item.kind == "method"
    ]
    forward = [
        item for item in members
        if item.qualified_name.rsplit(".", 1)[-1] == "forward"
    ]
    call_method = [
        item for item in members
        if item.qualified_name.rsplit(".", 1)[-1] == "__call__"
    ]
    chosen = forward or call_method
    if len(chosen) == 1:
        return chosen[0]
    return None


def _adapter_instance_attribute_types(
    adapter: Any, files: Mapping[str, str]
) -> dict[str, dict[str, str]]:
    """Return ``adapter.instance_attribute_types(files)`` when supported."""

    extractor = getattr(adapter, "instance_attribute_types", None)
    if not callable(extractor):
        return {}
    try:
        return dict(extractor(files) or {})
    except Exception:
        return {}


def _extract_interprocedural_calls(
    *,
    symbol: SymbolRefV1,
    nodes: list[BehaviorNodeV1],
    symbol_index: SymbolIndexV2,
    instance_attribute_types: Mapping[str, Mapping[str, str]] | None = None,
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
    by_qualified_name: dict[str, list[SymbolRefV1]] = {}
    by_parent_name: dict[str, list[SymbolRefV1]] = {}
    for sym in symbol_index.symbols:
        short = sym.qualified_name.split(".")[-1]
        by_short_name.setdefault(short, []).append(sym)
        by_qualified_name.setdefault(sym.qualified_name, []).append(sym)
        if "." in sym.qualified_name:
            by_parent_name.setdefault(
                sym.qualified_name.rsplit(".", 1)[0], []
            ).append(sym)
    for node in nodes:
        if not _is_call_derived(node):
            continue
        if not node.operands:
            continue
        target_name = node.operands[0]
        # Strip "self." / "cls." prefixes and module qualifiers.
        short = target_name.split(".")[-1]
        target_sym, unresolved_reason = _resolve_call_target(
            symbol=symbol,
            target_name=target_name,
            by_short_name=by_short_name,
            by_qualified_name=by_qualified_name,
            by_parent_name=by_parent_name,
            instance_attribute_types=instance_attribute_types,
        )
        if target_sym is None:
            # Could be a builtin, an external library call, or a dynamic call.
            unresolved.append(
                UnresolvedRelationV1(
                    relation_id=f"unres:{node.node_id}:CALLS",
                    kind="CALLS",
                    source_node_id=node.node_id,
                    source_symbol_id=symbol.symbol_id,
                    source_span_id=node.source_span_id,
                    reason=unresolved_reason or _classify_unresolved_reason(target_name),
                    target_hint=target_name,
                )
            )
            continue
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
