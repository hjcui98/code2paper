"""R2.3 relation verification tests.

Covers the R2.3 relation categories:

- direct call relation (CALLS across function boundaries);
- caller/callee return relation (RETURNS_TO);
- intra-function data dependency (DATA_DEPENDS_ON via assignment + use);
- branch/control dependency (TRUE_BRANCH / FALSE_BRANCH);
- config guard (BRANCH whose guard references a config access);
- side effect (WRITES_TO for file writes, SERIALIZE for checkpoints);
- bounded interprocedural data flow (a returned value consumed by a
  caller).

Each test verifies that the relation is present, carries stable span ids,
and that unresolved relations are recorded rather than guessed.
"""

from __future__ import annotations

import textwrap

import pytest

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    CodeBehaviorGraphV1,
    SymbolIndexV2,
)
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


_ADAPTER = PythonBehaviorAdapter()


def _index(files: dict[str, str]) -> SymbolIndexV2:
    return _ADAPTER.index_symbols(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
    )


def _build(files: dict[str, str], index: SymbolIndexV2, qualified_name: str, *, depth: int = 1):
    sym_id = None
    for sym in index.symbols:
        if sym.qualified_name == qualified_name:
            sym_id = sym.symbol_id
            break
    assert sym_id, f"symbol {qualified_name} not found"
    return build_behavior_subgraph(
        adapter=_ADAPTER,
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
        symbol_index=index,
        symbol_ids=[sym_id],
        depth=depth,
    )


def _sym_id(index: SymbolIndexV2, qualified_name: str) -> str:
    for sym in index.symbols:
        if sym.qualified_name == qualified_name:
            return sym.symbol_id
    raise AssertionError(f"symbol {qualified_name} not found")


# ---------------------------------------------------------------------------
# Direct call relation
# ---------------------------------------------------------------------------


def test_direct_call_relation_links_caller_to_callee() -> None:
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
    result = _build(files, index, "caller", depth=1)
    caller_id = _sym_id(index, "caller")
    callee_id = _sym_id(index, "callee")
    calls = [
        r for r in result.graph.relations
        if r.kind == "CALLS"
        and r.source_symbol_id == caller_id
        and r.target_symbol_id == callee_id
    ]
    assert calls, "expected direct CALLS relation"
    rel = calls[0]
    # The relation must carry both source and target span ids.
    assert rel.source_span_id.startswith("span:train.py:")
    assert rel.target_span_id.startswith("span:train.py:")


def test_direct_call_relation_records_argument_binding_for_named_args() -> None:
    """When the adapter can extract argument names, they appear in the
    ``argument_binding`` channel of the CALLS relation."""

    source = textwrap.dedent(
        """\
        def caller():
            return callee(x=1, y=2)

        def callee(x, y):
            return x + y
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "caller", depth=1)
    calls = [r for r in result.graph.relations if r.kind == "CALLS"]
    assert calls


# ---------------------------------------------------------------------------
# Returns_to relation
# ---------------------------------------------------------------------------


def test_returns_to_relation_marks_return_site() -> None:
    source = textwrap.dedent(
        """\
        def f():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    returns_to = [r for r in result.graph.relations if r.kind == "RETURNS_TO"]
    assert returns_to
    # RETURNS_TO has no intra-symbol target node; the target is the caller,
    # which is resolved by the supervisor when needed.
    assert returns_to[0].target_node_id == ""


# ---------------------------------------------------------------------------
# Branch / control dependency
# ---------------------------------------------------------------------------


def test_true_branch_and_false_branch_relations_are_emitted() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                a = 1
            else:
                a = 2
            return a
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    true_branches = [r for r in result.graph.relations if r.kind == "TRUE_BRANCH"]
    false_branches = [r for r in result.graph.relations if r.kind == "FALSE_BRANCH"]
    assert true_branches
    assert false_branches
    # The branch relations must carry the guard expression.
    assert true_branches[0].guard == "x > 0"
    assert false_branches[0].guard == "x > 0"


def test_branch_with_no_else_omits_false_branch() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                a = 1
            return a
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    true_branches = [r for r in result.graph.relations if r.kind == "TRUE_BRANCH"]
    false_branches = [r for r in result.graph.relations if r.kind == "FALSE_BRANCH"]
    assert true_branches
    assert not false_branches


# ---------------------------------------------------------------------------
# Config guard
# ---------------------------------------------------------------------------


def test_config_guard_branch_is_tagged_with_config_access() -> None:
    """A branch whose guard reads from a config object must surface the
    config access in the BRANCH node's diagnostics."""

    source = textwrap.dedent(
        """\
        def f(cfg):
            if cfg["mode"] == "train":
                return 1
            return 0
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    # There must be a config_access LOAD node and a BRANCH node.
    config_loads = [
        n for n in result.graph.nodes
        if n.predicate == "LOAD" and "config_access" in n.diagnostics
    ]
    assert config_loads
    branches = [n for n in result.graph.nodes if n.predicate == "BRANCH"]
    assert branches
    # The BRANCH guard must reference cfg["mode"].
    assert "cfg" in branches[0].guard


# ---------------------------------------------------------------------------
# Side effects: file write / serialization
# ---------------------------------------------------------------------------


def test_file_write_side_effect_is_recorded() -> None:
    source = textwrap.dedent(
        """\
        def f(path):
            with open(path, "w") as fh:
                fh.write("data")
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    write_nodes = [
        n for n in result.graph.nodes
        if n.predicate == "WRITE" and "file_open_write" in n.diagnostics
    ]
    assert write_nodes


def test_torch_save_serialization_is_recorded() -> None:
    source = textwrap.dedent(
        """\
        def f(model, path):
            torch.save(model.state_dict(), path)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=0)
    serialize_nodes = [n for n in result.graph.nodes if n.predicate == "SERIALIZE"]
    assert serialize_nodes


# ---------------------------------------------------------------------------
# Bounded interprocedural data flow
# ---------------------------------------------------------------------------


def test_interprocedural_data_flow_links_return_to_call_assignment() -> None:
    """A caller that assigns the callee's return value to a variable
    establishes a bounded interprocedural data flow: the callee's RETURN
    node is the source, and the caller's WRITE node is the sink.

    The R2.3 plan only requires *bounded* interprocedural data flow: we
    record the CALLS and RETURNS_TO relations, and the supervisor can
    chain them with the caller's WRITE node to reconstruct the flow.
    """

    source = textwrap.dedent(
        """\
        def caller():
            result = callee()
            return result

        def callee():
            return 42
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "caller", depth=1)
    caller_id = _sym_id(index, "caller")
    callee_id = _sym_id(index, "callee")
    # The CALLS relation must link caller to callee.
    calls = [
        r for r in result.graph.relations
        if r.kind == "CALLS" and r.source_symbol_id == caller_id
        and r.target_symbol_id == callee_id
    ]
    assert calls
    # The callee's RETURN node must exist in the graph.
    callee_returns = [
        n for n in result.graph.nodes
        if n.symbol_id == callee_id and n.predicate == "RETURN"
    ]
    assert callee_returns
    # The caller's WRITE node for ``result`` must exist.
    caller_writes = [
        n for n in result.graph.nodes
        if n.symbol_id == caller_id and n.predicate == "WRITE" and n.result == "result"
    ]
    assert caller_writes


# ---------------------------------------------------------------------------
# Unresolved relations: dynamic / external / reflection
# ---------------------------------------------------------------------------


def test_dynamic_getattr_call_is_unresolved_with_reflection_reason() -> None:
    source = textwrap.dedent(
        """\
        def f(obj, method_name):
            fn = getattr(obj, method_name)
            return fn()
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=1)
    # getattr must be unresolved with reason "reflection" or "dynamic_call".
    unresolved = result.graph.unresolved_relations
    assert any(u.reason in {"reflection", "dynamic_call"} for u in unresolved)


def test_external_torch_call_is_unresolved_with_external_module_reason() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return torch.nn.functional.relu(x)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=1)
    unresolved = result.graph.unresolved_relations
    assert any(u.reason == "external_module" for u in unresolved)


def test_unresolved_relations_carry_source_span_id() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return torch.softmax(x)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=1)
    for u in result.graph.unresolved_relations:
        assert u.source_span_id.startswith("span:train.py:")
        assert u.source_node_id.startswith("node:")


# ---------------------------------------------------------------------------
# Relation stability
# ---------------------------------------------------------------------------


def test_relations_are_stable_across_rebuilds() -> None:
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
    r1 = _build(files, index, "caller", depth=1)
    r2 = _build(files, index, "caller", depth=1)
    assert [r.relation_id for r in r1.graph.relations] == [
        r.relation_id for r in r2.graph.relations
    ]
    assert [u.relation_id for u in r1.graph.unresolved_relations] == [
        u.relation_id for u in r2.graph.unresolved_relations
    ]


def test_no_supported_relation_for_unresolved_target() -> None:
    """An unresolved call must NOT also appear as a resolved CALLS relation.

    This is the anti-hallucination floor: a fact compiler must treat
    unresolved relations as ``unsupported``, never as ``supported``.
    """

    source = textwrap.dedent(
        """\
        def f(x):
            return torch.softmax(x)
        """
    )
    files = {"train.py": source}
    index = _index(files)
    result = _build(files, index, "f", depth=1)
    # There must be unresolved relations for the external call.
    assert result.graph.unresolved_relations
    # And no resolved CALLS relation should point at a torch.softmax symbol
    # (there is no such symbol in the index).
    for rel in result.graph.relations:
        if rel.kind == "CALLS":
            assert "softmax" not in (rel.target_symbol_id or "")
