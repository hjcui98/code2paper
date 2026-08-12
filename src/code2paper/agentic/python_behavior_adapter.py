"""R2.1 Python AST adapter for the generic CodeBehaviorGraph.

Implements ``PythonBehaviorAdapter`` from design section 6.4.  The adapter
walks a Python AST and emits ``BehaviorNodeV1`` records covering the
R2.1 predicate batch:

- module / class / function / method structure;
- assignment, attribute/subscript read/write;
- call + argument binding;
- if/else guard;
- for/while loop;
- return;
- compare;
- arithmetic / matmul;
- concat / stack / reshape;
- sort / topk / mask / filter;
- file write / serialization;
- config / default access.

The adapter is deliberately conservative: dynamic calls, reflection and
monkey-patching are recorded as ``UnresolvedRelationV1`` instead of being
guessed.  This is the anti-hallucination floor for the behavior graph.
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    ReferenceSetV1,
    ReferenceSiteV1,
    SymbolIndexV2,
    SymbolRefV1,
    UnresolvedRelationV1,
    assert_valid_predicate,
    assert_valid_relation_kind,
    make_span_id,
    make_symbol_id,
)
from code2paper.agentic.source_authority import classify_source_authority


# ---------------------------------------------------------------------------
# Known method -> predicate mapping (for CALL nodes that match common APIs)
# ---------------------------------------------------------------------------


_METHOD_PREDICATES: dict[str, str] = {
    # tensor shape ops
    "reshape": "RESHAPE",
    "view": "RESHAPE",
    "permute": "RESHAPE",
    "transpose": "RESHAPE",
    "unsqueeze": "RESHAPE",
    "squeeze": "RESHAPE",
    "flatten": "RESHAPE",
    # selection / filtering
    "topk": "TOPK",
    "sort": "SORT",
    "argsort": "SORT",
    "sorted": "SORT",
    "masked_fill": "MASK",
    "mask": "MASK",
    "where": "MASK",
    "filter": "FILTER",
    "selective_scan_fn": "FILTER",
    "selective_scan_ref": "FILTER",
    "select": "SELECT",
    "index_select": "SELECT",
    "gather": "SELECT",
    # reductions
    "sum": "REDUCE",
    "mean": "REDUCE",
    "max": "REDUCE",
    "min": "REDUCE",
    "prod": "REDUCE",
    "norm": "REDUCE",
    "std": "REDUCE",
    "var": "REDUCE",
    # normalization
    "softmax": "NORMALIZE",
    "log_softmax": "NORMALIZE",
    "normalize": "NORMALIZE",
    "layer_norm": "NORMALIZE",
    "batch_norm": "NORMALIZE",
    # combination
    "cat": "CONCAT",
    "concat": "CONCAT",
    "stack": "STACK",
    "hstack": "CONCAT",
    "vstack": "CONCAT",
    "dstack": "CONCAT",
    # projection
    "linear": "PROJECT",
    "matmul": "COMPUTE",
    "mm": "COMPUTE",
    "bmm": "COMPUTE",
    "einsum": "COMPUTE",
    # attention / propagation (high-level, must be composed but we tag the call)
    "attention": "ATTEND",
    "scaled_dot_product_attention": "ATTEND",
    "propagate": "PROPAGATE",
    "message": "PROPAGATE",
    "pagerank": "PROPAGATE",
    "pagerank_scipy": "PROPAGATE",
    "personalized_pagerank": "PROPAGATE",
    # sampling
    "sample": "SAMPLE",
    "randn": "SAMPLE",
    "rand": "SAMPLE",
    "randint": "SAMPLE",
    "randperm": "SAMPLE",
    # serialization
    "save": "SERIALIZE",
    "dump": "SERIALIZE",
    "to_json": "SERIALIZE",
    "to_csv": "SERIALIZE",
    # transform (generic)
    "apply": "TRANSFORM",
    "map": "TRANSFORM",
    "transform": "TRANSFORM",
}

# Bare function calls are normally repository-defined helpers and must remain
# CALL nodes. Only well-known function-level primitives belong here; method
# names such as ``normalize`` are intentionally excluded because a local
# ``normalize(...)`` helper is not necessarily the underlying operation.
_BARE_FUNCTION_PREDICATES: dict[str, str] = {
    "selective_scan_fn": "FILTER",
    "selective_scan_ref": "FILTER",
}


# Module-qualified function -> predicate (e.g. torch.save, json.dump)
_QUALIFIED_PREDICATES: dict[str, str] = {
    "torch.save": "SERIALIZE",
    "torch.cat": "CONCAT",
    "torch.stack": "STACK",
    "torch.sort": "SORT",
    "torch.topk": "TOPK",
    "torch.argsort": "SORT",
    "sorted": "SORT",
    "torch.where": "MASK",
    "torch.masked_fill": "MASK",
    "torch.randn": "SAMPLE",
    "torch.rand": "SAMPLE",
    "torch.randint": "SAMPLE",
    "torch.randperm": "SAMPLE",
    "torch.softmax": "NORMALIZE",
    "torch.log_softmax": "NORMALIZE",
    "torch.norm": "REDUCE",
    "torch.sum": "REDUCE",
    "torch.mean": "REDUCE",
    "torch.max": "REDUCE",
    "torch.min": "REDUCE",
    "torch.matmul": "COMPUTE",
    "torch.mm": "COMPUTE",
    "torch.bmm": "COMPUTE",
    "torch.einsum": "COMPUTE",
    "torch.reshape": "RESHAPE",
    "torch.view": "RESHAPE",
    "torch.permute": "RESHAPE",
    "torch.transpose": "RESHAPE",
    "torch.flatten": "RESHAPE",
    "torch.gather": "SELECT",
    "torch.index_select": "SELECT",
    "torch.linear": "PROJECT",
    "json.dump": "SERIALIZE",
    "json.dumps": "SERIALIZE",
    "pickle.dump": "SERIALIZE",
    "np.save": "SERIALIZE",
    "np.savetxt": "SERIALIZE",
    "open": "READ",  # open() for read by default; WRITE if mode="w"
}


_FILE_WRITE_NAMES: frozenset[str] = frozenset(
    {"write", "writelines", "writeline", "dump", "save", "to_csv", "to_json"}
)

_SERIALIZATION_OPEN_MODES: frozenset[str] = frozenset({"w", "wb", "a", "ab", "x", "xb"})


# ---------------------------------------------------------------------------
# PythonBehaviorAdapter
# ---------------------------------------------------------------------------


class PythonBehaviorAdapter:
    """Python AST -> BehaviorNodeV1 / BehaviorRelationV1 adapter.

    The adapter is stateless: every method takes its inputs and returns a
    value type.  ``index_symbols`` walks the snapshot files once;
    ``extract_operations`` / ``extract_relations`` are called per-symbol by
    the incremental graph builder.
    """

    language = "python"

    # ------------------------------------------------------------------
    # index_symbols
    # ------------------------------------------------------------------

    def index_symbols(
        self,
        *,
        repo_snapshot_id: str,
        project_tree_hash: str,
        files: dict[str, str],
    ) -> SymbolIndexV2:
        """Build a SymbolIndexV2 from ``{relative_path: source_text}``.

        Only Python files (``.py`` suffix) are indexed.  Parse errors are
        recorded as warnings, not crashes.
        """

        symbols: list[SymbolRefV1] = []
        warnings: list[str] = []
        for path, text in files.items():
            if not path.endswith(".py"):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                warnings.append(f"syntax_error:{path}:{exc.lineno or 0}")
                continue
            for sym in _walk_symbols(tree, path):
                symbols.append(sym)
        symbols.sort(key=lambda s: (s.path, s.start_line, s.qualified_name))
        index = SymbolIndexV2(
            repo_snapshot_id=repo_snapshot_id,
            project_tree_hash=project_tree_hash,
            language=self.language,
            indexed_files=sum(1 for p in files if p.endswith(".py")),
            indexed_symbols=len(symbols),
            symbols=symbols,
            warnings=warnings,
        )
        return index.model_copy(update={"content_digest": _index_digest(index)})

    # ------------------------------------------------------------------
    # extract_operations
    # ------------------------------------------------------------------

    def extract_operations(self, symbol: SymbolRefV1, source_text: str) -> list[BehaviorNodeV1]:
        """Extract all BehaviorNodeV1 records for a single symbol.

        The symbol's source span is sliced from ``source_text`` (the whole
        file) using ``start_line`` / ``end_line``.  The slice is parsed
        standalone so the visitor only sees the symbol's own body.
        """

        lines = source_text.splitlines()
        if symbol.start_line < 1 or symbol.end_line < symbol.start_line:
            return []
        if symbol.end_line > len(lines):
            return []
        # Slice 1-indexed inclusive range.
        slice_text = "\n".join(lines[symbol.start_line - 1 : symbol.end_line])
        # Dedent so the slice parses as a standalone module.
        slice_text = _dedent(slice_text)
        try:
            tree = ast.parse(slice_text)
        except SyntaxError:
            return []
        visitor = _BehaviorNodeVisitor(symbol=symbol)
        visitor.visit(tree)
        return visitor.nodes

    # ------------------------------------------------------------------
    # extract_relations
    # ------------------------------------------------------------------

    def extract_relations(
        self,
        symbol: SymbolRefV1,
        source_text: str,
        nodes: list[BehaviorNodeV1],
    ) -> list[BehaviorRelationV1]:
        """Extract intra-symbol relations (CONTAINS, NEXT_CONTROL, branches).

        Inter-symbol relations (CALLS across functions, RETURNS_TO) are
        produced by the graph builder, which has access to the full symbol
        index.  This method only handles relations within a single symbol's
        body.
        """

        lines = source_text.splitlines()
        if symbol.start_line < 1 or symbol.end_line < symbol.start_line:
            return []
        if symbol.end_line > len(lines):
            return []
        slice_text = _dedent("\n".join(lines[symbol.start_line - 1 : symbol.end_line]))
        try:
            tree = ast.parse(slice_text)
        except SyntaxError:
            return []
        visitor = _BehaviorRelationVisitor(symbol=symbol, nodes=nodes)
        visitor.visit(tree)
        visitor.add_configuration_relations()
        return visitor.relations

    # ------------------------------------------------------------------
    # resolve_references
    # ------------------------------------------------------------------

    def resolve_references(
        self,
        symbol: SymbolRefV1,
        index: SymbolIndexV2,
        files: dict[str, str],
    ) -> ReferenceSetV1:
        """Find imports and usages of ``symbol.qualified_name`` across files."""

        target_name = symbol.qualified_name.split(".")[-1]
        sites: list[ReferenceSiteV1] = []
        unresolved: list[str] = []
        for path, text in files.items():
            if not path.endswith(".py"):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for alias in node.names:
                        if alias.name == target_name:
                            sites.append(
                                ReferenceSiteV1(
                                    path=path,
                                    line=node.lineno,
                                    kind="import",
                                    span_id=make_span_id(path, node.lineno, node.lineno),
                                    source_authority=classify_source_authority(path),
                                    snippet=f"from {node.module} import {alias.name}",
                                )
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == target_name or alias.name.endswith("." + target_name):
                            sites.append(
                                ReferenceSiteV1(
                                    path=path,
                                    line=node.lineno,
                                    kind="import",
                                    span_id=make_span_id(path, node.lineno, node.lineno),
                                    source_authority=classify_source_authority(path),
                                    snippet=f"import {alias.name}",
                                )
                            )
                elif isinstance(node, ast.Name) and node.id == target_name:
                    sites.append(
                        ReferenceSiteV1(
                            path=path,
                            line=node.lineno,
                            kind="usage",
                            span_id=make_span_id(path, node.lineno, node.lineno),
                            source_authority=classify_source_authority(path),
                            snippet=target_name,
                        )
                    )
                elif isinstance(node, ast.Attribute) and node.attr == target_name:
                    sites.append(
                        ReferenceSiteV1(
                            path=path,
                            line=node.lineno,
                            kind="attribute",
                            span_id=make_span_id(path, node.lineno, node.lineno),
                            source_authority=classify_source_authority(path),
                            snippet=f"...{target_name}",
                        )
                    )
        # Deduplicate sites by (path, line, kind).
        seen: set[tuple[str, int, str]] = set()
        unique_sites: list[ReferenceSiteV1] = []
        for site in sites:
            key = (site.path, site.line, site.kind)
            if key not in seen:
                seen.add(key)
                unique_sites.append(site)
        # Remove the definition site itself (a class definition's ClassDef
        # node has the same name as the symbol and would be a false positive).
        unique_sites = [
            site
            for site in unique_sites
            if not (site.path == symbol.path and site.line == symbol.start_line)
        ]
        if not unique_sites and not unresolved:
            unresolved.append("no_static_references_found")
        return ReferenceSetV1(
            symbol_id=symbol.symbol_id,
            qualified_name=symbol.qualified_name,
            sites=tuple(unique_sites),
            unresolved=tuple(unresolved),
        )


# ---------------------------------------------------------------------------
# Symbol walking (for index_symbols)
# ---------------------------------------------------------------------------


def _walk_symbols(tree: ast.Module, path: str) -> list[SymbolRefV1]:
    """Walk a module AST and emit SymbolRefV1 for every def/class."""

    symbols: list[SymbolRefV1] = []

    def _visit(node: ast.AST, parent_id: str, prefix: str, in_class: bool = False) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qname = f"{prefix}.{node.name}" if prefix else node.name
            sym_id = make_symbol_id(path, qname, node.lineno)
            end_line = _symbol_end_line(node)
            symbols.append(
                SymbolRefV1(
                    symbol_id=sym_id,
                    path=path,
                    qualified_name=qname,
                    kind="method" if in_class else "function",
                    start_line=node.lineno,
                    end_line=end_line,
                    parent_symbol_id=parent_id,
                    docstring=ast.get_docstring(node) or "",
                )
            )
            for child in ast.iter_child_nodes(node):
                _visit(child, sym_id, qname, in_class=False)
        elif isinstance(node, ast.ClassDef):
            qname = f"{prefix}.{node.name}" if prefix else node.name
            sym_id = make_symbol_id(path, qname, node.lineno)
            end_line = _symbol_end_line(node)
            symbols.append(
                SymbolRefV1(
                    symbol_id=sym_id,
                    path=path,
                    qualified_name=qname,
                    kind="class",
                    start_line=node.lineno,
                    end_line=end_line,
                    parent_symbol_id=parent_id,
                    docstring=ast.get_docstring(node) or "",
                )
            )
            for child in ast.iter_child_nodes(node):
                _visit(child, sym_id, qname, in_class=True)

    # Module-level: also emit a module symbol.
    module_id = make_symbol_id(path, "<module>", 1)
    module_end = 1
    if tree.body:
        last = tree.body[-1]
        module_end = getattr(last, "end_lineno", None) or getattr(last, "lineno", 1)
    symbols.append(
        SymbolRefV1(
            symbol_id=module_id,
            path=path,
            qualified_name="<module>",
            kind="module",
            start_line=1,
            end_line=module_end,
            parent_symbol_id="",
            docstring=ast.get_docstring(tree) or "",
        )
    )
    for child in tree.body:
        _visit(child, module_id, "")
    return symbols


def _symbol_end_line(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int) and end >= getattr(node, "lineno", 1):
        return end
    return getattr(node, "lineno", 1)


# ---------------------------------------------------------------------------
# Behavior node visitor
# ---------------------------------------------------------------------------


def _breadth_first_frontier_transition(
    node: ast.While,
) -> tuple[str, str] | None:
    """Recognize a conservative level-synchronous frontier swap.

    The pattern requires all of the following executable structure inside
    one ``while`` loop: the current container occurs in the loop guard, a
    nested loop consumes that container, a distinct next container is reset
    to an empty collection, and the current container is finally replaced by
    ``next.copy()``.  This is strong enough to describe breadth-first frontier
    propagation without trusting comments, docstrings, or project names.
    """

    guard_names = {
        child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)
    }
    consumed_names: set[str] = set()
    empty_names: set[str] = set()
    transitions: list[tuple[str, str]] = []
    for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
        if isinstance(child, (ast.For, ast.comprehension)):
            iterator = child.iter
            if (
                isinstance(iterator, ast.Call)
                and isinstance(iterator.func, ast.Attribute)
                and iterator.func.attr in {"items", "keys", "values"}
                and isinstance(iterator.func.value, ast.Name)
            ):
                consumed_names.add(iterator.func.value.id)
            elif isinstance(iterator, ast.Name):
                consumed_names.add(iterator.id)
        if not isinstance(child, ast.Assign) or len(child.targets) != 1:
            continue
        target = child.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(child.value, (ast.List, ast.Set)) and not child.value.elts:
            empty_names.add(target.id)
        elif isinstance(child.value, ast.Dict) and not child.value.keys:
            empty_names.add(target.id)
        elif (
            isinstance(child.value, ast.Call)
            and isinstance(child.value.func, ast.Name)
            and child.value.func.id in {"dict", "list", "set"}
            and not child.value.args
            and not child.value.keywords
        ):
            empty_names.add(target.id)
        if (
            isinstance(child.value, ast.Call)
            and isinstance(child.value.func, ast.Attribute)
            and child.value.func.attr == "copy"
            and isinstance(child.value.func.value, ast.Name)
            and not child.value.args
            and not child.value.keywords
        ):
            transitions.append((target.id, child.value.func.value.id))
    for current_name, next_name in transitions:
        if (
            current_name != next_name
            and current_name in guard_names
            and current_name in consumed_names
            and next_name in empty_names
        ):
            return current_name, next_name
    return None


def _level_synchronous_frontier_transition(
    node: ast.For,
) -> tuple[str, tuple[str, ...]] | None:
    """Recognize a current/next frontier swap in a bounded iteration loop."""

    module = ast.Module(body=node.body, type_ignores=[])
    loaded_names = {
        child.id
        for child in ast.walk(module)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    for child in ast.walk(module):
        if not isinstance(child, ast.Assign) or len(child.targets) != 1:
            continue
        target = child.targets[0]
        if not isinstance(target, ast.Name) or "current" not in target.id.casefold():
            continue
        next_names = tuple(sorted({
            name.id
            for name in ast.walk(child.value)
            if isinstance(name, ast.Name)
            and isinstance(name.ctx, ast.Load)
            and "next" in name.id.casefold()
        }))
        if target.id in loaded_names and next_names:
            return target.id, next_names
    return None


@dataclass
class _BehaviorNodeVisitor(ast.NodeVisitor):
    """Walk a symbol's AST slice and emit BehaviorNodeV1 records."""

    symbol: SymbolRefV1
    nodes: list[BehaviorNodeV1] = field(default_factory=list)
    _seq: int = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _span_id(self, node: ast.AST) -> str:
        start = getattr(node, "lineno", 1)
        end = getattr(node, "end_lineno", start) or start
        # The slice was dedented, so add the symbol's start_line offset back.
        offset = self.symbol.start_line - 1
        return make_span_id(self.symbol.path, start + offset, end + offset)

    def _add_node(
        self,
        *,
        node: ast.AST,
        predicate: str,
        operands: tuple[str, ...] = (),
        result: str = "",
        guard: str = "",
        iteration_context: str = "",
        diagnostics: tuple[str, ...] = (),
    ) -> BehaviorNodeV1:
        assert_valid_predicate(predicate)
        span_id = self._span_id(node)
        node_id = BehaviorNodeV1.make_node_id(
            symbol_id=self.symbol.symbol_id,
            source_span_id=span_id,
            predicate=predicate,
            seq=self._next_seq(),
        )
        bn = BehaviorNodeV1(
            node_id=node_id,
            symbol_id=self.symbol.symbol_id,
            operation_id=f"op-{self._seq}",
            predicate=predicate,
            operands=operands,
            result=result,
            guard=guard,
            iteration_context=iteration_context,
            source_span_id=span_id,
            source_authority=classify_source_authority(self.symbol.path),
            confidence=1.0,
            diagnostics=diagnostics,
        )
        self.nodes.append(bn)
        return bn

    # ------------------------------------------------------------------
    # Function parameters -> source-defined configuration defaults
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_parameter_defaults(node.args)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_parameter_defaults(node.args)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for statement in node.body:
            self.visit(statement)

    def _visit_parameter_defaults(self, arguments: ast.arguments) -> None:
        positional = [*arguments.posonlyargs, *arguments.args]
        offset = len(positional) - len(arguments.defaults)
        pairs = [
            (argument, default)
            for argument, default in zip(positional[offset:], arguments.defaults)
        ]
        pairs.extend(
            (argument, default)
            for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
            if default is not None
        )
        for argument, default in pairs:
            # A definition-time default is executable source evidence, but it
            # is not proof that an entrypoint uses the value.  Emit a READ
            # node tagged as a configuration default so the downstream
            # configuration compiler preserves the distinction.
            self._add_node(
                node=default,
                predicate="READ",
                operands=(argument.arg, _expr_to_str(default)),
                result=f"{argument.arg}={_expr_to_str(default)}",
                diagnostics=("config_access", "parameter_default"),
            )

    # ------------------------------------------------------------------
    # Assign / AugAssign -> WRITE (+ COMPUTE for the RHS)
    # ------------------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        # RHS first (the value is computed before the assignment happens).
        self.visit(node.value)
        rhs_expr = _expr_to_str(node.value)
        for target in node.targets:
            target_str = _target_to_str(target)
            if (
                "normaliz" in target_str.casefold()
                and isinstance(node.value, ast.BinOp)
                and isinstance(node.value.op, ast.Div)
            ):
                # A named normalization result backed by an exact division
                # operation is stronger than name-only inference: both the
                # semantic role and executable transform are present in the
                # same source span.
                self._add_node(
                    node=node,
                    predicate="NORMALIZE",
                    operands=(rhs_expr,),
                    result=target_str,
                    diagnostics=("normalized_assignment",),
                )
            if isinstance(target, ast.Attribute):
                self._add_node(
                    node=target,
                    predicate="WRITE",
                    operands=(target_str,),
                    result=target_str,
                    diagnostics=("attr_write",),
                )
            elif isinstance(target, ast.Subscript):
                self._add_node(
                    node=target,
                    predicate="WRITE",
                    operands=(target_str,),
                    result=target_str,
                    diagnostics=("subscript_write",),
                )
            else:
                self._add_node(
                    node=target,
                    predicate="WRITE",
                    operands=(target_str,),
                    result=target_str,
                    diagnostics=("assign",),
                )

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        target_str = _target_to_str(node.target)
        self._add_node(
            node=node,
            predicate="WRITE",
            operands=(target_str, _expr_to_str(node.value)),
            result=target_str,
            diagnostics=("aug_assign",),
        )

    # ------------------------------------------------------------------
    # AnnAssign -> WRITE (typed)
    # ------------------------------------------------------------------

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
        target_str = _target_to_str(node.target)
        self._add_node(
            node=node,
            predicate="WRITE",
            operands=(target_str,),
            result=target_str,
            diagnostics=("ann_assign",),
        )

    # ------------------------------------------------------------------
    # Call -> CALL (+ specialized predicate for known methods)
    # ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        # Visit arguments first so operand reads are recorded before the call.
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)
        func = node.func
        func_str = _expr_to_str(func)
        predicate, diagnostics = _classify_call(func, node)
        operands: list[str] = [func_str]
        for arg in node.args:
            operands.append(_expr_to_str(arg))
        for kw in node.keywords:
            if kw.arg:
                operands.append(f"{kw.arg}={_expr_to_str(kw.value)}")
        # Detect file-write pattern: open(path, "w") followed by .write(...)
        if predicate == "READ" and _is_open_call(node):
            mode = _open_mode(node)
            if mode in _SERIALIZATION_OPEN_MODES:
                predicate = "WRITE"
                diagnostics = (*diagnostics, "file_open_write")
            else:
                diagnostics = (*diagnostics, "file_open_read")
        self._add_node(
            node=node,
            predicate=predicate,
            operands=tuple(operands),
            result="",
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------------
    # Return -> RETURN
    # ------------------------------------------------------------------

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self.visit(node.value)
        operands = (_expr_to_str(node.value),) if node.value is not None else ()
        self._add_node(
            node=node,
            predicate="RETURN",
            operands=operands,
        )

    # ------------------------------------------------------------------
    # If -> BRANCH (with guard)
    # ------------------------------------------------------------------

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        guard = _expr_to_str(node.test)
        self._add_node(
            node=node,
            predicate="BRANCH",
            operands=(guard,),
            guard=guard,
            diagnostics=("if",),
        )
        if not node.orelse and any(
            isinstance(child, ast.Continue)
            for statement in node.body
            for child in ast.walk(statement)
        ):
            self._add_node(
                node=node,
                predicate="FILTER",
                operands=(guard,),
                guard=guard,
                diagnostics=("guarded_continue",),
            )
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    # ------------------------------------------------------------------
    # For / While -> LOOP (with iteration context)
    # ------------------------------------------------------------------

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        target_str = _target_to_str(node.target)
        iter_str = _expr_to_str(node.iter)
        self._add_node(
            node=node,
            predicate="LOOP",
            operands=(target_str, iter_str),
            iteration_context=f"for {target_str} in {iter_str}",
            diagnostics=("for",),
        )
        frontier_transition = _level_synchronous_frontier_transition(node)
        if frontier_transition is not None:
            current_name, next_names = frontier_transition
            self._add_node(
                node=node,
                predicate="PROPAGATE",
                operands=(
                    "breadth first level synchronous frontier propagation",
                    current_name,
                    *next_names,
                ),
                iteration_context=f"for {target_str} in {iter_str}",
                diagnostics=("current_next_frontier",),
            )
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        guard = _expr_to_str(node.test)
        self._add_node(
            node=node,
            predicate="LOOP",
            operands=(guard,),
            guard=guard,
            iteration_context=f"while {guard}",
            diagnostics=("while",),
        )
        frontier_transition = _breadth_first_frontier_transition(node)
        if frontier_transition is not None:
            current_name, next_name = frontier_transition
            self._add_node(
                node=node,
                predicate="PROPAGATE",
                operands=(
                    "breadth first frontier propagation",
                    current_name,
                    next_name,
                ),
                guard=guard,
                iteration_context=f"while {guard}",
                diagnostics=("level_synchronous_frontier",),
            )
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    # ------------------------------------------------------------------
    # Compare -> COMPARE
    # ------------------------------------------------------------------

    def visit_Compare(self, node: ast.Compare) -> None:
        self.visit(node.left)
        for comp in node.comparators:
            self.visit(comp)
        operands = (_expr_to_str(node.left), *(_expr_to_str(c) for c in node.comparators))
        self._add_node(
            node=node,
            predicate="COMPARE",
            operands=operands,
        )

    # ------------------------------------------------------------------
    # BinOp -> COMPUTE (arithmetic / matmul / concat)
    # ------------------------------------------------------------------

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self.visit(node.left)
        self.visit(node.right)
        op_name = type(node.op).__name__
        operands = (_expr_to_str(node.left), _expr_to_str(node.right))
        if isinstance(node.op, ast.MatMult):
            predicate = "COMPUTE"
            diagnostics = ("matmul",)
        elif isinstance(node.op, ast.Add) and _looks_like_concat(node):
            predicate = "CONCAT"
            diagnostics = ("concat_add",)
        else:
            predicate = "COMPUTE"
            diagnostics = (op_name.lower(),)
        self._add_node(
            node=node,
            predicate=predicate,
            operands=operands,
            diagnostics=diagnostics,
        )
        if isinstance(node.op, ast.MatMult) and _looks_like_graph_propagation(operands):
            self._add_node(
                node=node,
                predicate="PROPAGATE",
                operands=operands,
                diagnostics=("graph_matrix_propagation",),
            )

    # ------------------------------------------------------------------
    # UnaryOp -> TRANSFORM (generic)
    # ------------------------------------------------------------------

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        self.visit(node.operand)
        self._add_node(
            node=node,
            predicate="TRANSFORM",
            operands=(_expr_to_str(node.operand),),
            diagnostics=(type(node.op).__name__.lower(),),
        )

    # ------------------------------------------------------------------
    # Attribute (read) -> LOAD
    # ------------------------------------------------------------------

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.visit(node.value)
        # Don't double-record: if this attribute is a call target, the Call
        # visitor will handle it.  We only record pure attribute reads here.
        if not isinstance(node.ctx, ast.Load):
            return
        attr_str = _expr_to_str(node)
        diagnostics = ("attr_read",)
        if _looks_like_config_attribute(node):
            diagnostics = ("config_access", *diagnostics)
        self._add_node(
            node=node,
            predicate="LOAD",
            operands=(attr_str,),
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------------
    # Subscript (read) -> LOAD
    # ------------------------------------------------------------------

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit(node.value)
        if isinstance(node.ctx, ast.Load):
            sub_str = _expr_to_str(node)
            # Config access pattern: config["key"] or cfg.key -> LOAD + config hint
            diagnostics = ("subscript_read",)
            if _looks_like_config_access(node):
                diagnostics = ("config_access", *diagnostics)
            self._add_node(
                node=node,
                predicate="LOAD",
                operands=(sub_str,),
                diagnostics=diagnostics,
            )

    # ------------------------------------------------------------------
    # Name (read) -> LOAD
    # ------------------------------------------------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._add_node(
                node=node,
                predicate="LOAD",
                operands=(node.id,),
                diagnostics=("name_read",),
            )

    # ------------------------------------------------------------------
    # Import / ImportFrom -> LOAD (module)
    # ------------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_node(
                node=node,
                predicate="LOAD",
                operands=(alias.name,),
                diagnostics=("import",),
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self._add_node(
                node=node,
                predicate="LOAD",
                operands=(f"{node.module}.{alias.name}",),
                diagnostics=("import_from",),
            )

    # ------------------------------------------------------------------
    # generic visit (walk children)
    # ------------------------------------------------------------------

    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)


# ---------------------------------------------------------------------------
# Behavior relation visitor (intra-symbol)
# ---------------------------------------------------------------------------


@dataclass
class _BehaviorRelationVisitor(ast.NodeVisitor):
    """Walk a symbol's AST slice and emit intra-symbol BehaviorRelationV1."""

    symbol: SymbolRefV1
    nodes: list[BehaviorNodeV1]
    relations: list[BehaviorRelationV1] = field(default_factory=list)
    _seq: int = 0
    _node_by_line: dict[int, list[BehaviorNodeV1]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for n in self.nodes:
            # Extract the start line from the span_id "span:<path>:<start>:<end>".
            parts = n.source_span_id.split(":")
            if len(parts) >= 4:
                try:
                    line = int(parts[-2])
                    self._node_by_line.setdefault(line, []).append(n)
                except ValueError:
                    pass

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _nodes_at(self, line: int) -> list[BehaviorNodeV1]:
        global_line = line + self.symbol.start_line - 1
        return list(self._node_by_line.get(global_line, []))

    def _add_relation(
        self,
        *,
        kind: str,
        source: BehaviorNodeV1,
        target: BehaviorNodeV1 | None = None,
        guard: str = "",
        argument_binding: dict[str, str] | None = None,
        span_node: ast.AST | None = None,
    ) -> BehaviorRelationV1 | None:
        assert_valid_relation_kind(kind)
        target_id = target.node_id if target else ""
        rel_id = BehaviorRelationV1.make_relation_id(
            kind=kind,
            source_node_id=source.node_id,
            target_node_id=target_id,
            seq=self._next_seq(),
        )
        if span_node is None:
            span_id = source.source_span_id
        else:
            start = getattr(span_node, "lineno", 1)
            end = getattr(span_node, "end_lineno", start) or start
            offset = self.symbol.start_line - 1
            span_id = make_span_id(
                self.symbol.path,
                start + offset,
                end + offset,
            )
        rel = BehaviorRelationV1(
            relation_id=rel_id,
            kind=kind,
            source_node_id=source.node_id,
            target_node_id=target_id,
            source_symbol_id=source.symbol_id,
            target_symbol_id=target.symbol_id if target else "",
            source_span_id=span_id,
            target_span_id=target.source_span_id if target else "",
            argument_binding=argument_binding or {},
            guard=guard,
        )
        self.relations.append(rel)
        return rel

    def add_configuration_relations(self) -> None:
        """Link an operation to exact config loads it consumes on its span."""

        existing = {
            (relation.kind, relation.source_node_id, relation.target_node_id)
            for relation in self.relations
        }
        for line_nodes in self._node_by_line.values():
            config_nodes = [
                node for node in line_nodes
                if node.predicate == "LOAD" and "config_access" in node.diagnostics
            ]
            if not config_nodes:
                continue
            for source in line_nodes:
                if source.predicate == "LOAD":
                    continue
                source_text = " ".join((
                    *source.operands, source.result, source.guard,
                ))
                for target in config_nodes:
                    config_text = " ".join((*target.operands, target.result))
                    if config_text and config_text not in source_text:
                        continue
                    key = ("CONFIGURED_BY", source.node_id, target.node_id)
                    if key in existing:
                        continue
                    self._add_relation(
                        kind="CONFIGURED_BY",
                        source=source,
                        target=target,
                    )
                    existing.add(key)

    def visit_If(self, node: ast.If) -> None:
        # TRUE_BRANCH / FALSE_BRANCH from the BRANCH node at this line.
        branch_nodes = [
            n for n in self._nodes_at(node.lineno) if n.predicate == "BRANCH"
        ]
        if branch_nodes:
            branch = branch_nodes[0]
            # First body statement -> TRUE_BRANCH
            if node.body:
                first_line = getattr(node.body[0], "lineno", node.lineno)
                true_targets = self._nodes_at(first_line)
                if true_targets:
                    self._add_relation(
                        kind="TRUE_BRANCH",
                        source=branch,
                        target=true_targets[0],
                        guard=branch.guard,
                        span_node=node,
                    )
            if node.orelse:
                first_else = node.orelse[0]
                first_line = getattr(first_else, "lineno", node.lineno)
                false_targets = self._nodes_at(first_line)
                if false_targets:
                    self._add_relation(
                        kind="FALSE_BRANCH",
                        source=branch,
                        target=false_targets[0],
                        guard=branch.guard,
                        span_node=node,
                    )
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        loop_nodes = [n for n in self._nodes_at(node.lineno) if n.predicate == "LOOP"]
        if loop_nodes and node.body:
            first_line = getattr(node.body[0], "lineno", node.lineno)
            body_targets = self._nodes_at(first_line)
            if body_targets:
                self._add_relation(
                    kind="NEXT_CONTROL",
                    source=loop_nodes[0],
                    target=body_targets[0],
                    span_node=node,
                )
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        loop_nodes = [n for n in self._nodes_at(node.lineno) if n.predicate == "LOOP"]
        if loop_nodes and node.body:
            first_line = getattr(node.body[0], "lineno", node.lineno)
            body_targets = self._nodes_at(first_line)
            if body_targets:
                self._add_relation(
                    kind="NEXT_CONTROL",
                    source=loop_nodes[0],
                    target=body_targets[0],
                    span_node=node,
                )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        ret_nodes = [n for n in self._nodes_at(node.lineno) if n.predicate == "RETURN"]
        if ret_nodes:
            # RETURNS_TO links the RETURN node to its enclosing symbol (no
            # intra-symbol target node; the inter-symbol caller is resolved
            # by the graph builder).
            self._add_relation(
                kind="RETURNS_TO",
                source=ret_nodes[0],
                target=None,
                span_node=node,
            )
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dedent(text: str) -> str:
    """Remove common leading whitespace from a code slice."""

    lines = text.splitlines()
    if not lines:
        return text
    indents = [
        len(line) - len(line.lstrip(" "))
        for line in lines
        if line.strip()
    ]
    if not indents:
        return text
    min_indent = min(indents)
    if min_indent == 0:
        return text
    return "\n".join(
        line[min_indent:] if len(line) >= min_indent else line
        for line in lines
    )


def _expr_to_str(node: ast.AST | None) -> str:
    """Best-effort textual rendering of an AST expression."""

    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _target_to_str(node: ast.AST) -> str:
    return _expr_to_str(node)


def _classify_call(func: ast.AST, call: ast.Call) -> tuple[str, tuple[str, ...]]:
    """Classify a Call node into (predicate, diagnostics).

    Returns the generic ``CALL`` predicate for unknown functions, and a
    specialized predicate (SORT / TOPK / MASK / ...) for known APIs.
    """

    # Qualified call: module.func(...) or obj.method(...)
    if isinstance(func, ast.Attribute):
        qualifier = _expr_to_str(func.value)
        method = func.attr
        qualified = f"{qualifier}.{method}" if qualifier else method
        if qualified in _QUALIFIED_PREDICATES:
            pred = _QUALIFIED_PREDICATES[qualified]
            return pred, (f"qualified:{qualified}",)
        if method in _METHOD_PREDICATES:
            pred = _METHOD_PREDICATES[method]
            return pred, (f"method:{method}",)
        if method in _FILE_WRITE_NAMES:
            return "WRITE", (f"file_write:{method}",)
        return "CALL", (f"attr:{method}",)
    # Bare call: name(...)
    if isinstance(func, ast.Name):
        name = func.id
        if name in _BARE_FUNCTION_PREDICATES:
            pred = _BARE_FUNCTION_PREDICATES[name]
            return pred, (f"function:{name}",)
        if name in _QUALIFIED_PREDICATES:
            pred = _QUALIFIED_PREDICATES[name]
            return pred, (f"name:{name}",)
        if name in {"open"}:
            return "READ", ("open_call",)
        if name in {"print"}:
            return "WRITE", ("print_call",)
        return "CALL", (f"name:{name}",)
    return "CALL", ("unknown_func",)


def _is_open_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "open":
        return True
    return False


def _open_mode(node: ast.Call) -> str:
    """Extract the mode argument from an open() call.  Default 'r'."""

    if len(node.args) >= 2:
        mode_node = node.args[1]
        if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
            return mode_node.value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return "r"


def _looks_like_concat(node: ast.BinOp) -> bool:
    """Heuristic: ``a + b`` where either operand is a list/tuple/list-call."""

    for operand in (node.left, node.right):
        if isinstance(operand, ast.List) or isinstance(operand, ast.Tuple):
            return True
        if isinstance(operand, ast.Call) and isinstance(operand.func, ast.Name) and operand.func.id == "list":
            return True
    return False


def _looks_like_graph_propagation(operands: tuple[str, ...]) -> bool:
    """Recognize matrix message passing without relying on project symbols."""

    tokens = {
        token
        for operand in operands
        for token in re.findall(r"[a-z][a-z0-9]+", operand.lower())
    }
    return bool(tokens & {
        "adj", "adjacency", "graph", "incidence", "message", "messages",
        "propagation", "sparse", "transition",
    })


def _looks_like_config_access(node: ast.Subscript) -> bool:
    """Heuristic: ``cfg["key"]`` or ``config["key"]`` patterns."""

    value = node.value
    if isinstance(value, ast.Name):
        return value.id.lower() in {"cfg", "config", "conf", "args", "opts", "settings"}
    if isinstance(value, ast.Attribute):
        return value.attr.lower() in {"cfg", "config", "conf", "args", "opts", "settings"}
    return False


def _looks_like_config_attribute(node: ast.Attribute) -> bool:
    """Heuristic: ``cfg.lr`` / ``config.lr`` / ``args.lr`` attribute access."""

    value = node.value
    if isinstance(value, ast.Name):
        return value.id.lower() in {"cfg", "config", "conf", "args", "opts", "settings"}
    if isinstance(value, ast.Attribute):
        return value.attr.lower() in {"cfg", "config", "conf", "args", "opts", "settings"}
    return False


def _index_digest(index: SymbolIndexV2) -> str:
    payload = {
        "schema_version": index.schema_version,
        "repo_snapshot_id": index.repo_snapshot_id,
        "project_tree_hash": index.project_tree_hash,
        "language": index.language,
        "symbols": [s.model_dump(mode="json") for s in index.symbols],
    }
    import json
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "PythonBehaviorAdapter",
]
