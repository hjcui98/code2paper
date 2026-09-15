"""Branch-aware NEXT_CONTROL: an arm boundary is not an execution order.

The mechanism compiler recovers branch guards by walking ``NEXT_CONTROL``
inside a branch span.  When the adapter chained the end of an ``if`` body to
the first statement of its ``else``, the true-arm guard propagated into the
else arm, which then received the opposite polarity and was reported as a
``path_polarity_conflict`` for perfectly legal code.
"""

from __future__ import annotations

from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


_ADAPTER = PythonBehaviorAdapter()


def _graph(source: str):
    files = {"sample.py": source}
    index = _ADAPTER.index_symbols(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
    )
    symbol = next(
        item for item in index.symbols if item.qualified_name == "choose"
    )
    return build_behavior_subgraph(
        adapter=_ADAPTER,
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
        symbol_index=index,
        symbol_ids=[symbol.symbol_id],
    )


_SOURCE = '''\
def choose(flag):
    if flag:
        value = 1
        other = value + 1
    else:
        value = 2
        other = value + 2
    return other
'''


def test_sequential_control_never_crosses_exclusive_arms() -> None:
    result = _graph(_SOURCE)
    graph = result.graph
    nodes = {node.node_id: node for node in graph.nodes}

    def lines(node_id: str) -> tuple[int, int]:
        parts = nodes[node_id].source_span_id.split(":")
        return int(parts[-2]), int(parts[-1])

    true_arm = [(3, 4)]
    false_arm = [(6, 7)]
    for relation in graph.relations:
        if str(relation.kind) != "NEXT_CONTROL":
            continue
        source = lines(str(relation.source_node_id))
        target = lines(str(relation.target_node_id))
        assert not (
            true_arm[0][0] <= source[0] <= true_arm[0][1]
            and false_arm[0][0] <= target[0] <= false_arm[0][1]
        ), (source, target)
        assert not (
            false_arm[0][0] <= source[0] <= false_arm[0][1]
            and true_arm[0][0] <= target[0] <= true_arm[0][1]
        ), (source, target)


def test_each_arm_joins_the_statement_after_the_if() -> None:
    result = _graph(_SOURCE)
    graph = result.graph
    nodes = {node.node_id: node for node in graph.nodes}

    def lines(node_id: str) -> tuple[int, int]:
        parts = nodes[node_id].source_span_id.split(":")
        return int(parts[-2]), int(parts[-1])

    edges = {
        (str(relation.source_node_id), str(relation.target_node_id))
        for relation in graph.relations
        if str(relation.kind) == "NEXT_CONTROL"
    }
    join_nodes = [
        node_id for node_id in nodes if lines(node_id)[0] >= 8
    ]
    assert join_nodes, "the return statement must be in the graph"
    for arm in ((3, 4), (6, 7)):
        arm_nodes = [
            node_id
            for node_id in nodes
            if arm[0] <= lines(node_id)[0] and lines(node_id)[1] <= arm[1]
        ]
        assert arm_nodes
        assert any(
            (arm_node, join_node) in edges
            for arm_node in arm_nodes
            for join_node in join_nodes
        ), (arm, arm_nodes)


def test_nested_if_arms_keep_the_full_ancestor_identity() -> None:
    source = '''\
def choose(flag, inner):
    if flag:
        if inner:
            value = 1
        else:
            value = 2
        other = value + 1
    else:
        value = 3
        other = value + 3
    return other
'''
    graph = _graph(source).graph
    nodes = {node.node_id: node for node in graph.nodes}

    def lines(node_id: str) -> tuple[int, int]:
        parts = nodes[node_id].source_span_id.split(":")
        return int(parts[-2]), int(parts[-1])

    for relation in graph.relations:
        if str(relation.kind) != "NEXT_CONTROL":
            continue
        source_lines = lines(str(relation.source_node_id))
        target_lines = lines(str(relation.target_node_id))
        # Inner true/false arms are mutually exclusive even though both are
        # nested inside the outer true arm.
        assert not (
            source_lines[0] == 4
            and target_lines[0] == 6
        ), (source_lines, target_lines)
        assert not (
            source_lines[0] == 6
            and target_lines[0] == 4
        ), (source_lines, target_lines)
        # The outer arms must remain exclusive as well.
        assert not (
            3 <= source_lines[0] <= 8
            and 9 <= target_lines[0] <= 10
        ), (source_lines, target_lines)
        assert not (
            9 <= source_lines[0] <= 10
            and 3 <= target_lines[0] <= 8
        ), (source_lines, target_lines)


def test_elif_is_a_nested_exclusive_chain() -> None:
    source = '''\
def choose(first, second):
    if first:
        value = 1
    elif second:
        value = 2
    else:
        value = 3
    return value
'''
    graph = _graph(source).graph
    nodes = {node.node_id: node for node in graph.nodes}

    def line(node_id: str) -> int:
        return int(nodes[node_id].source_span_id.split(":")[-2])

    for relation in graph.relations:
        if str(relation.kind) != "NEXT_CONTROL":
            continue
        source_line = line(str(relation.source_node_id))
        target_line = line(str(relation.target_node_id))
        assert not (source_line == 3 and target_line in {4, 5, 6})
        assert not (source_line == 6 and target_line == 4)
        assert not (source_line == 4 and target_line == 6)


def test_return_does_not_gain_a_post_branch_join_edge() -> None:
    source = '''\
def choose(flag):
    if flag:
        return 1
    else:
        value = 2
    return value
'''
    graph = _graph(source).graph
    nodes = {node.node_id: node for node in graph.nodes}
    return_ids = {
        node_id for node_id, node in nodes.items() if node.predicate == "RETURN"
    }
    assert return_ids
    assert all(
        not (
            str(relation.kind) == "NEXT_CONTROL"
            and str(relation.source_node_id) in return_ids
        )
        for relation in graph.relations
    )
