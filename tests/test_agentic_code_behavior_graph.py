"""R2.1 tests for the CodeBehaviorGraph core contracts.

Covers:

- ``BehaviorNodeV1`` / ``BehaviorRelationV1`` / ``CodeBehaviorGraphV1``
  enforce ``extra="forbid"`` and reject unknown predicates / relation kinds;
- ``make_node_id`` / ``make_relation_id`` are stable for stable inputs;
- ``CodeBehaviorGraphV1.content_digest`` is deterministic and changes when
  the graph changes;
- ``CodeBehaviorGraphV1.merge`` deduplicates by id and refuses to merge
  graphs from different snapshots;
- ``SymbolRefV1`` / ``SymbolIndexV2`` / ``ReferenceSetV1`` enforce their
  contracts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_GRAPH_SCHEMA_VERSION,
    BEHAVIOR_PREDICATES,
    BEHAVIOR_RELATION_KINDS,
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


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


def test_behavior_predicates_contain_all_r21_categories() -> None:
    expected = {
        "READ", "WRITE", "CALL", "CONSTRUCT", "LOAD", "RETURN",
        "TRANSFORM", "CONCAT", "STACK", "NORMALIZE", "REDUCE", "AGGREGATE",
        "COMPUTE", "COMPARE", "BRANCH", "LOOP", "SELECT", "TOPK",
        "SORT", "MASK", "FILTER", "RESHAPE", "PROJECT", "ATTEND",
        "SAMPLE", "PROPAGATE", "SERIALIZE",
    }
    assert set(BEHAVIOR_PREDICATES) == expected
    assert len(BEHAVIOR_PREDICATES) == 27


def test_behavior_relation_kinds_contain_all_design_relations() -> None:
    expected = {
        "CONTAINS", "NEXT_CONTROL", "TRUE_BRANCH", "FALSE_BRANCH",
        "CALLS", "RETURNS_TO", "DATA_DEPENDS_ON", "CONTROL_DEPENDS_ON",
        "CONFIGURED_BY", "READS_FROM", "WRITES_TO", "ALIAS_OF",
        "OVERRIDES", "IMPLEMENTS",
    }
    assert set(BEHAVIOR_RELATION_KINDS) == expected
    assert len(BEHAVIOR_RELATION_KINDS) == 14


def test_assert_valid_predicate_rejects_unknown() -> None:
    assert_valid_predicate("READ")
    with pytest.raises(ValueError, match="unknown behavior predicate"):
        assert_valid_predicate("NOT_A_REAL_PREDICATE")


def test_assert_valid_relation_kind_rejects_unknown() -> None:
    assert_valid_relation_kind("CALLS")
    with pytest.raises(ValueError, match="unknown behavior relation kind"):
        assert_valid_relation_kind("NOT_A_REAL_RELATION")


# ---------------------------------------------------------------------------
# Stable IDs
# ---------------------------------------------------------------------------


def test_make_span_id_format() -> None:
    assert make_span_id("train.py", 10, 20) == "span:train.py:10:20"


def test_make_symbol_id_is_stable() -> None:
    s1 = make_symbol_id("train.py", "Trainer.train_loop", 15)
    s2 = make_symbol_id("train.py", "Trainer.train_loop", 15)
    assert s1 == s2
    assert s1.startswith("sym:")
    # Different inputs produce different ids.
    s3 = make_symbol_id("train.py", "Trainer.train_loop", 16)
    assert s1 != s3
    s4 = make_symbol_id("train.py", "Other", 15)
    assert s1 != s4


def test_node_id_is_stable_for_same_inputs() -> None:
    n1 = BehaviorNodeV1.make_node_id(
        symbol_id="sym:abc",
        source_span_id="span:train.py:1:5",
        predicate="WRITE",
        seq=1,
    )
    n2 = BehaviorNodeV1.make_node_id(
        symbol_id="sym:abc",
        source_span_id="span:train.py:1:5",
        predicate="WRITE",
        seq=1,
    )
    assert n1 == n2
    assert n1.startswith("node:")


def test_relation_id_is_stable_for_same_inputs() -> None:
    r1 = BehaviorRelationV1.make_relation_id(
        kind="CALLS",
        source_node_id="node:a",
        target_node_id="node:b",
        seq=0,
    )
    r2 = BehaviorRelationV1.make_relation_id(
        kind="CALLS",
        source_node_id="node:a",
        target_node_id="node:b",
        seq=0,
    )
    assert r1 == r2
    assert r1.startswith("rel:")


# ---------------------------------------------------------------------------
# BehaviorNodeV1 contract
# ---------------------------------------------------------------------------


def _sample_node(**overrides) -> BehaviorNodeV1:
    base = dict(
        node_id="node:test1",
        symbol_id="sym:test",
        operation_id="op-1",
        predicate="WRITE",
        operands=("x",),
        result="x",
        source_span_id="span:train.py:1:1",
    )
    base.update(overrides)
    return BehaviorNodeV1(**base)


def test_behavior_node_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _sample_node(totally_unknown_field="oops")


def test_behavior_node_rejects_unknown_predicate() -> None:
    with pytest.raises(ValidationError):
        _sample_node(predicate="NOT_A_PREDICATE")


def test_behavior_node_rejects_confidence_out_of_range() -> None:
    with pytest.raises(ValidationError):
        _sample_node(confidence=1.5)
    with pytest.raises(ValidationError):
        _sample_node(confidence=-0.1)


def test_behavior_node_is_frozen() -> None:
    node = _sample_node()
    with pytest.raises(ValidationError):
        node.predicate = "READ"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BehaviorRelationV1 contract
# ---------------------------------------------------------------------------


def _sample_relation(**overrides) -> BehaviorRelationV1:
    base = dict(
        relation_id="rel:test1",
        kind="CALLS",
        source_node_id="node:a",
        target_node_id="node:b",
        source_symbol_id="sym:a",
        target_symbol_id="sym:b",
        source_span_id="span:a.py:1:1",
        target_span_id="span:b.py:2:2",
    )
    base.update(overrides)
    return BehaviorRelationV1(**base)


def test_behavior_relation_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _sample_relation(totally_unknown_field="oops")


def test_behavior_relation_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        _sample_relation(kind="NOT_A_RELATION")


def test_behavior_relation_is_frozen() -> None:
    rel = _sample_relation()
    with pytest.raises(ValidationError):
        rel.kind = "RETURNS_TO"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# UnresolvedRelationV1 contract
# ---------------------------------------------------------------------------


def test_unresolved_relation_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        UnresolvedRelationV1(
            relation_id="rel:unres1",
            kind="CALLS",
            source_node_id="node:a",
            source_symbol_id="sym:a",
            source_span_id="span:a.py:1:1",
            reason="dynamic_call",
            totally_unknown_field="oops",
        )


def test_unresolved_relation_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        UnresolvedRelationV1(
            relation_id="rel:unres1",
            kind="NOT_A_RELATION",
            source_node_id="node:a",
            source_symbol_id="sym:a",
            source_span_id="span:a.py:1:1",
            reason="dynamic_call",
        )


# ---------------------------------------------------------------------------
# CodeBehaviorGraphV1
# ---------------------------------------------------------------------------


def _sample_graph(**overrides) -> CodeBehaviorGraphV1:
    base = dict(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        nodes=[_sample_node()],
        relations=[_sample_relation()],
    )
    base.update(overrides)
    return CodeBehaviorGraphV1(**base).with_digest()


def test_code_behavior_graph_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CodeBehaviorGraphV1(
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            totally_unknown_field="oops",
        )


def test_code_behavior_graph_content_digest_is_stable() -> None:
    g1 = _sample_graph()
    g2 = _sample_graph()
    assert g1.content_digest == g2.content_digest
    assert g1.content_digest.startswith("sha256:")


def test_code_behavior_graph_content_digest_changes_with_nodes() -> None:
    g1 = _sample_graph()
    g2 = _sample_graph(
        nodes=[
            _sample_node(),
            _sample_node(node_id="node:test2", operation_id="op-2", predicate="READ"),
        ]
    )
    assert g1.content_digest != g2.content_digest


def test_code_behavior_graph_content_digest_changes_with_relations() -> None:
    g1 = _sample_graph()
    g2 = _sample_graph(
        relations=[
            _sample_relation(),
            _sample_relation(
                relation_id="rel:test2",
                kind="RETURNS_TO",
                target_node_id="",
                target_symbol_id="",
            ),
        ]
    )
    assert g1.content_digest != g2.content_digest


def test_code_behavior_graph_nodes_for_symbol() -> None:
    g = _sample_graph(
        nodes=[
            _sample_node(node_id="node:a", symbol_id="sym:a"),
            _sample_node(node_id="node:b", symbol_id="sym:b", predicate="READ"),
        ]
    )
    assert len(g.nodes_for_symbol("sym:a")) == 1
    assert len(g.nodes_for_symbol("sym:b")) == 1
    assert g.nodes_for_symbol("sym:missing") == []


def test_code_behavior_graph_predicates_set() -> None:
    g = _sample_graph(
        nodes=[
            _sample_node(predicate="WRITE"),
            _sample_node(node_id="node:test2", operation_id="op-2", predicate="READ"),
        ]
    )
    assert g.predicates() == {"WRITE", "READ"}


def test_code_behavior_graph_merge_deduplicates() -> None:
    n1 = _sample_node()
    g1 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        nodes=[n1],
    ).with_digest()
    g2 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        nodes=[n1, _sample_node(node_id="node:test2", operation_id="op-2", predicate="READ")],
    ).with_digest()
    merged = g1.merge(g2)
    assert len(merged.nodes) == 2  # n1 deduplicated
    assert {n.node_id for n in merged.nodes} == {"node:test1", "node:test2"}


def test_code_behavior_graph_merge_rejects_different_snapshots() -> None:
    g1 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:a",
        project_tree_hash="sha256:a",
    ).with_digest()
    g2 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:b",
        project_tree_hash="sha256:b",
    ).with_digest()
    with pytest.raises(ValueError, match="different snapshots"):
        g1.merge(g2)


def test_code_behavior_graph_merge_rejects_different_tree_hash() -> None:
    g1 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:a",
        project_tree_hash="sha256:a",
    ).with_digest()
    g2 = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:a",
        project_tree_hash="sha256:b",
    ).with_digest()
    with pytest.raises(ValueError, match="different project_tree_hash"):
        g1.merge(g2)


# ---------------------------------------------------------------------------
# SymbolIndexV2 / SymbolRefV1 / ReferenceSetV1
# ---------------------------------------------------------------------------


def _sample_symbol(**overrides) -> SymbolRefV1:
    base = dict(
        symbol_id="sym:test",
        path="train.py",
        qualified_name="Trainer",
        kind="class",
        start_line=1,
        end_line=10,
    )
    base.update(overrides)
    return SymbolRefV1(**base)


def test_symbol_ref_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _sample_symbol(totally_unknown_field="oops")


def test_symbol_ref_is_frozen() -> None:
    sym = _sample_symbol()
    with pytest.raises(ValidationError):
        sym.path = "other.py"  # type: ignore[misc]


def test_symbol_index_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SymbolIndexV2(
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            totally_unknown_field="oops",
        )


def test_symbol_index_find_returns_matching_symbol() -> None:
    index = SymbolIndexV2(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        symbols=[_sample_symbol(), _sample_symbol(symbol_id="sym:other", qualified_name="Other")],
    )
    assert index.find("sym:test") is not None
    assert index.find("sym:test").qualified_name == "Trainer"
    assert index.find("sym:missing") is None


def test_reference_site_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ReferenceSiteV1(
            path="train.py",
            line=1,
            kind="import",
            span_id="span:train.py:1:1",
            totally_unknown_field="oops",
        )


def test_reference_set_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ReferenceSetV1(
            symbol_id="sym:test",
            qualified_name="Trainer",
            totally_unknown_field="oops",
        )
