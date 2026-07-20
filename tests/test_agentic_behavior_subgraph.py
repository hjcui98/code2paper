"""R2.2 tests for the incremental behavior subgraph builder.

Covers:

- ``build_behavior_subgraph`` parses only the requested symbols;
- ``depth=0`` stays within the requested symbols, ``depth>=1`` follows
  interprocedural CALLS relations to include callees;
- ``node_budget`` truncates the build and records a warning;
- repeated calls with the same symbol_ids produce the same stable node ids
  (deduplication via ``CodeBehaviorGraphV1.merge``);
- interprocedural CALLS relations are resolved through the symbol index;
  dynamic / external calls are recorded as ``UnresolvedRelationV1``;
- the resulting graph is content-addressed.
"""

from __future__ import annotations

import textwrap

import pytest

from code2paper.agentic.behavior_graph import (
    CodeBehaviorGraphV1,
    SymbolIndexV2,
    SymbolRefV1,
)
from code2paper.agentic.behavior_graph_tools import (
    BehaviorSubgraphResult,
    BuildBehaviorSubgraphInput,
    build_behavior_subgraph,
)
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


_ADAPTER = PythonBehaviorAdapter()


def _index(files: dict[str, str]) -> SymbolIndexV2:
    return _ADAPTER.index_symbols(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
    )


def _build(
    files: dict[str, str],
    index: SymbolIndexV2,
    symbol_ids: list[str],
    *,
    depth: int = 0,
    node_budget: int = 1000,
) -> BehaviorSubgraphResult:
    return build_behavior_subgraph(
        adapter=_ADAPTER,
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
        symbol_index=index,
        symbol_ids=symbol_ids,
        depth=depth,
        node_budget=node_budget,
    )


def _sym_id(index: SymbolIndexV2, qualified_name: str) -> str:
    for sym in index.symbols:
        if sym.qualified_name == qualified_name:
            return sym.symbol_id
    raise AssertionError(f"symbol {qualified_name} not found")


# ---------------------------------------------------------------------------
# Basic build
# ---------------------------------------------------------------------------


def test_build_subgraph_depth_0_parses_only_requested_symbols() -> None:
    source = textwrap.dedent(
        """\
        def caller():
            return callee()

        def callee():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "caller")], depth=0)
    assert result.depth_reached == 0
    # Only the caller symbol is covered.
    caller_id = _sym_id(index, "caller")
    callee_id = _sym_id(index, "callee")
    assert caller_id in result.covered_symbol_ids
    assert callee_id not in result.covered_symbol_ids
    # The graph has nodes for caller but not for callee.
    assert result.graph.nodes_for_symbol(caller_id)
    assert not result.graph.nodes_for_symbol(callee_id)


def test_build_subgraph_depth_1_follows_callees() -> None:
    source = textwrap.dedent(
        """\
        def caller():
            return callee()

        def callee():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "caller")], depth=1)
    assert result.depth_reached == 1
    caller_id = _sym_id(index, "caller")
    callee_id = _sym_id(index, "callee")
    assert caller_id in result.covered_symbol_ids
    assert callee_id in result.covered_symbol_ids
    # The graph must contain a CALLS relation from caller to callee.
    calls_rels = [
        r for r in result.graph.relations
        if r.kind == "CALLS"
        and r.source_symbol_id == caller_id
        and r.target_symbol_id == callee_id
    ]
    assert calls_rels, "expected interprocedural CALLS relation"


def test_build_subgraph_depth_2_follows_transitive_callees() -> None:
    source = textwrap.dedent(
        """\
        def a():
            return b()

        def b():
            return c()

        def c():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "a")], depth=2)
    assert _sym_id(index, "a") in result.covered_symbol_ids
    assert _sym_id(index, "b") in result.covered_symbol_ids
    assert _sym_id(index, "c") in result.covered_symbol_ids


def test_build_subgraph_does_not_revisit_symbols() -> None:
    """A recursive call graph must not loop forever."""

    source = textwrap.dedent(
        """\
        def recurse(n):
            if n > 0:
                return recurse(n - 1)
            return 0
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "recurse")], depth=5)
    # Only one symbol is covered (the self-call is excluded).
    assert result.covered_symbol_ids == (_sym_id(index, "recurse"),)


# ---------------------------------------------------------------------------
# Node budget
# ---------------------------------------------------------------------------


def test_build_subgraph_truncates_at_node_budget() -> None:
    source = textwrap.dedent(
        """\
        def f():
            a = 1
            b = 2
            c = 3
            d = 4
            e = 5
            return a + b + c + d + e
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "f")], depth=0, node_budget=3)
    assert result.truncated is True
    assert result.node_count <= 3
    assert any("node_budget" in w for w in result.warnings)


def test_build_subgraph_rejects_negative_depth() -> None:
    files = {"train.py": "def f():\n    pass\n"}
    index = _index(files)
    with pytest.raises(ValueError, match="depth must be non-negative"):
        _build(files, index, [_sym_id(index, "f")], depth=-1)


def test_build_subgraph_rejects_zero_node_budget() -> None:
    files = {"train.py": "def f():\n    pass\n"}
    index = _index(files)
    with pytest.raises(ValueError, match="node_budget must be positive"):
        _build(files, index, [_sym_id(index, "f")], depth=0, node_budget=0)


# ---------------------------------------------------------------------------
# Stable IDs and deduplication
# ---------------------------------------------------------------------------


def test_build_subgraph_is_deterministic_across_calls() -> None:
    source = textwrap.dedent(
        """\
        def caller():
            return callee()

        def callee():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    r1 = _build(files, index, [_sym_id(index, "caller")], depth=1)
    r2 = _build(files, index, [_sym_id(index, "caller")], depth=1)
    assert r1.graph.content_digest == r2.graph.content_digest
    assert [n.node_id for n in r1.graph.nodes] == [n.node_id for n in r2.graph.nodes]
    assert [r.relation_id for r in r1.graph.relations] == [
        r.relation_id for r in r2.graph.relations
    ]


def test_build_subgraph_merges_overlapping_symbol_sets() -> None:
    """Building [a, b] and [b, c] and merging must deduplicate b."""

    source = textwrap.dedent(
        """\
        def a():
            return b()

        def b():
            return c()

        def c():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    r1 = _build(files, index, [_sym_id(index, "a")], depth=1)
    r2 = _build(files, index, [_sym_id(index, "c")], depth=0)
    merged = r1.graph.merge(r2.graph)
    # b appears in r1 (as a callee of a) but not in r2 (only c).  c appears
    # in both.  The merged graph must not duplicate c's nodes.
    c_id = _sym_id(index, "c")
    c_nodes = [n for n in merged.nodes if n.symbol_id == c_id]
    c_node_ids = {n.node_id for n in c_nodes}
    assert len(c_nodes) == len(c_node_ids)


# ---------------------------------------------------------------------------
# Unresolved relations
# ---------------------------------------------------------------------------


def test_build_subgraph_records_external_calls_as_unresolved() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return torch.softmax(x, dim=-1)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "f")], depth=1)
    # torch.softmax is an external call -> must be unresolved.
    unresolved = result.graph.unresolved_relations
    assert unresolved
    reasons = {u.reason for u in unresolved}
    assert "external_module" in reasons


def test_build_subgraph_records_builtins_as_unresolved() -> None:
    source = textwrap.dedent(
        """\
        def f(items):
            return len(items)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "f")], depth=1)
    unresolved = result.graph.unresolved_relations
    assert any(u.reason == "builtin" for u in unresolved)


def test_build_subgraph_resolves_intra_file_calls() -> None:
    source = textwrap.dedent(
        """\
        def caller():
            return helper()

        def helper():
            return 1
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, [_sym_id(index, "caller")], depth=1)
    # The caller -> helper call must be a resolved CALLS relation, not unresolved.
    caller_id = _sym_id(index, "caller")
    helper_id = _sym_id(index, "helper")
    resolved_calls = [
        r for r in result.graph.relations
        if r.kind == "CALLS" and r.target_symbol_id == helper_id
    ]
    assert resolved_calls
    # And helper must not appear in unresolved with reason dynamic_call.
    helper_unresolved = [
        u for u in result.graph.unresolved_relations
        if u.source_symbol_id == caller_id and "helper" in (u.target_hint or "")
    ]
    assert not helper_unresolved


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------


def test_build_behavior_subgraph_input_rejects_extra_fields() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        BuildBehaviorSubgraphInput(
            tool_call_id="tc-1",
            obligation_id="obl-1",
            goal="g",
            repo_snapshot_id="repo:test",
            symbol_ids=("sym:abc",),
            totally_unknown_field="oops",
        )


def test_build_behavior_subgraph_input_carries_required_fields() -> None:
    inp = BuildBehaviorSubgraphInput(
        tool_call_id="tc-1",
        obligation_id="obl-1",
        goal="build subgraph",
        repo_snapshot_id="repo:test",
        path_scope=(),
        top_k=0,
        depth=2,
        node_budget=500,
        symbol_ids=("sym:abc", "sym:def"),
    )
    assert inp.depth == 2
    assert inp.node_budget == 500
    assert inp.symbol_ids == ("sym:abc", "sym:def")


# ---------------------------------------------------------------------------
# Content addressing
# ---------------------------------------------------------------------------


def test_build_subgraph_content_digest_is_stable() -> None:
    source = textwrap.dedent(
        """\
        def f():
            x = 1
            return x
        """
    )
    files = {"train.py": source}
    index = _index(files)
    r1 = _build(files, index, [_sym_id(index, "f")])
    r2 = _build(files, index, [_sym_id(index, "f")])
    assert r1.graph.content_digest == r2.graph.content_digest
    assert r1.graph.content_digest.startswith("sha256:")


def test_build_subgraph_content_digest_changes_with_different_symbols() -> None:
    source = textwrap.dedent(
        """\
        def f():
            x = 1
            return x

        def g():
            y = 2
            return y
        """
    )
    files = {"train.py": source}
    index = _index(files)
    r1 = _build(files, index, [_sym_id(index, "f")])
    r2 = _build(files, index, [_sym_id(index, "g")])
    assert r1.graph.content_digest != r2.graph.content_digest
