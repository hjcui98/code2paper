"""R4.5 tests for the generic fact compiler (R4.2).

Verifies that ``compile_facts_from_behavior_graph``:

- maps every ``BEHAVIOR_PREDICATES`` entry to a ``FactPredicate``;
- produces stable ``canonical_identity`` for the same behavior graph;
- rejects nodes whose ``source_authority`` is weaker than the input floor;
- never anchors a positive fact on an unresolved relation;
- derives ``calls_in_order`` facts from ``NEXT_CONTROL`` chains of ``CALL``
  nodes inside a single symbol;
- derives ``configured_by`` facts from ``CONFIGURED_BY`` relations;
- contains no project-specific literals in source (R4.5 hard constraint).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    UnresolvedRelationV1,
)
from code2paper.agentic.generic_fact_compiler import (
    BEHAVIOR_PREDICATE_TO_FACT,
    FactCompilerInputV1,
    compile_facts_from_behavior_graph,
)
from code2paper.agentic.evidence_compiler_v3 import CodeFactV1


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"


def _node(
    *,
    node_id: str,
    symbol_id: str = "sym:module.func",
    predicate: str = "READ",
    operands: tuple[str, ...] = ("x",),
    result: str = "",
    guard: str = "",
    source_span_id: str = "span:module.py:1:10",
    source_authority: str = "executable_hard",
    operation_id: str = "op-1",
) -> BehaviorNodeV1:
    return BehaviorNodeV1(
        node_id=node_id,
        symbol_id=symbol_id,
        operation_id=operation_id,
        predicate=predicate,
        operands=operands,
        result=result,
        guard=guard,
        source_span_id=source_span_id,
        source_authority=source_authority,  # type: ignore[arg-type]
    )


def _relation(
    *,
    relation_id: str,
    kind: str = "NEXT_CONTROL",
    source_node_id: str = "node:a",
    target_node_id: str = "node:b",
    source_symbol_id: str = "sym:module.func",
    target_symbol_id: str = "",
    source_span_id: str = "span:module.py:1:10",
    target_span_id: str = "",
    guard: str = "",
) -> BehaviorRelationV1:
    return BehaviorRelationV1(
        relation_id=relation_id,
        kind=kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        source_symbol_id=source_symbol_id,
        target_symbol_id=target_symbol_id,
        source_span_id=source_span_id,
        target_span_id=target_span_id,
        guard=guard,
    )


def _graph(
    nodes: list[BehaviorNodeV1] | None = None,
    relations: list[BehaviorRelationV1] | None = None,
    unresolved: list[UnresolvedRelationV1] | None = None,
) -> CodeBehaviorGraphV1:
    return CodeBehaviorGraphV1(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        language="python",
        nodes=nodes or [],
        relations=relations or [],
        unresolved_relations=unresolved or [],
    ).with_digest()


def _compile(
    graph: CodeBehaviorGraphV1,
    *,
    node_ids: list[str],
    relation_ids: list[str] | None = None,
    guards: list[str] | None = None,
    source_authority: str = "executable_hard",
    obligation_id: str = "obl-1",
):
    return compile_facts_from_behavior_graph(
        graph,
        FactCompilerInputV1(
            obligation_id=obligation_id,
            behavior_node_ids=node_ids,
            behavior_relation_ids=relation_ids or [],
            evidence_span_ids=[],
            guards=guards or [],
            source_authority=source_authority,  # type: ignore[arg-type]
        ),
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        evidence_packet_digest="sha256:packets",
    )


# ---------------------------------------------------------------------------
# Predicate mapping coverage
# ---------------------------------------------------------------------------


class TestPredicateMapping:
    def test_every_behavior_predicate_is_mapped(self) -> None:
        for predicate in BEHAVIOR_PREDICATES:
            assert predicate in BEHAVIOR_PREDICATE_TO_FACT, (
                f"predicate {predicate!r} has no fact predicate mapping"
            )

    def test_mapping_does_not_reference_unknown_predicates(self) -> None:
        for predicate in BEHAVIOR_PREDICATE_TO_FACT:
            assert predicate in BEHAVIOR_PREDICATES

    def test_mapping_covers_all_27_predicates(self) -> None:
        assert len(BEHAVIOR_PREDICATE_TO_FACT) == len(BEHAVIOR_PREDICATES) == 27


# ---------------------------------------------------------------------------
# Stable canonical identity
# ---------------------------------------------------------------------------


class TestStableFactIdentity:
    def test_same_graph_produces_same_fact_identities(self) -> None:
        node = _node(node_id="node:r1", predicate="READ", operands=("x",), result="y")
        graph = _graph(nodes=[node])
        result1 = _compile(graph, node_ids=["node:r1"])
        result2 = _compile(graph, node_ids=["node:r1"])
        assert [f.canonical_identity for f in result1.facts] == [
            f.canonical_identity for f in result2.facts
        ]
        assert [f.fact_id for f in result1.facts] == [
            f.fact_id for f in result2.facts
        ]

    def test_different_object_produces_different_identity(self) -> None:
        # ``_node_object`` prefers ``result`` over ``operands``, so we vary
        # the result to produce different objects (and therefore different
        # canonical identities).
        node_a = _node(node_id="node:a", predicate="READ", result="y_a")
        node_b = _node(node_id="node:b", predicate="READ", result="y_b")
        graph_a = _graph(nodes=[node_a])
        graph_b = _graph(nodes=[node_b])
        result_a = _compile(graph_a, node_ids=["node:a"])
        result_b = _compile(graph_b, node_ids=["node:b"])
        assert result_a.facts[0].canonical_identity != result_b.facts[0].canonical_identity

    def test_different_guard_produces_different_identity(self) -> None:
        node_a = _node(node_id="node:a", predicate="READ", guard="training_mode")
        node_b = _node(node_id="node:b", predicate="READ", guard="eval_mode")
        graph_a = _graph(nodes=[node_a])
        graph_b = _graph(nodes=[node_b])
        result_a = _compile(graph_a, node_ids=["node:a"])
        result_b = _compile(graph_b, node_ids=["node:b"])
        assert result_a.facts[0].canonical_identity != result_b.facts[0].canonical_identity

    def test_value_producing_operation_preserves_operands_and_result(self) -> None:
        node = _node(
            node_id="node:volume",
            predicate="REDUCE",
            operands=("torch.prod", "scales", "dim=1"),
            result="f_p_volume",
        )

        result = _compile(_graph(nodes=[node]), node_ids=[node.node_id])

        assert result.facts[0].object == [
            "torch.prod", "scales", "dim=1", "result=f_p_volume",
        ]


# ---------------------------------------------------------------------------
# Source authority rejection
# ---------------------------------------------------------------------------


class TestSourceAuthorityRejection:
    def test_hint_only_node_is_rejected(self) -> None:
        node = _node(
            node_id="node:hint",
            predicate="READ",
            source_authority="semantic_hint",
        )
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:hint"])
        assert len(result.facts) == 1
        fact = result.facts[0]
        assert fact.validation_status == "rejected"
        assert any("weak_source_authority" in f for f in fact.validation_failures)

    def test_executable_hard_node_is_supported(self) -> None:
        node = _node(
            node_id="node:hard",
            predicate="READ",
            source_authority="executable_hard",
        )
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:hard"])
        assert result.facts[0].validation_status == "supported"

    def test_author_intent_node_below_floor_is_rejected(self) -> None:
        node = _node(
            node_id="node:author",
            predicate="READ",
            source_authority="author_intent",
        )
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:author"])
        assert result.facts[0].validation_status == "rejected"


# ---------------------------------------------------------------------------
# Unresolved relation anti-hallucination
# ---------------------------------------------------------------------------


class TestUnresolvedRelationAntiHallucination:
    def test_configured_by_on_unresolved_relation_is_dropped(self) -> None:
        node = _node(node_id="node:cfg", predicate="CONSTRUCT")
        unresolved = UnresolvedRelationV1(
            relation_id="rel:unresolved-cfg",
            kind="CONFIGURED_BY",
            source_node_id="node:cfg",
            source_symbol_id="sym:module.func",
            source_span_id="span:module.py:1:10",
            reason="dynamic_call",
            target_hint="external_config",
        )
        graph = _graph(nodes=[node], unresolved=[unresolved])
        result = _compile(
            graph,
            node_ids=["node:cfg"],
            relation_ids=["rel:unresolved-cfg"],
        )
        # No configured_by fact should be emitted for an unresolved relation.
        configured_facts = [
            f for f in result.facts if f.predicate == "configured_by"
        ]
        assert configured_facts == []

    def test_node_with_unresolved_relation_is_flagged(self) -> None:
        node = _node(node_id="node:call", predicate="CALL")
        unresolved = UnresolvedRelationV1(
            relation_id="rel:unresolved-call",
            kind="CALLS",
            source_node_id="node:call",
            source_symbol_id="sym:module.func",
            source_span_id="span:module.py:1:10",
            reason="dynamic_call",
            target_hint="external_fn",
        )
        graph = _graph(nodes=[node], unresolved=[unresolved])
        result = _compile(
            graph,
            node_ids=["node:call"],
            relation_ids=["rel:unresolved-call"],
        )
        # The CALL fact should record the unresolved relation as a failure.
        call_facts = [f for f in result.facts if f.predicate == "calls"]
        assert len(call_facts) == 1
        assert any(
            "unresolved_relation" in fail for fail in call_facts[0].validation_failures
        )


# ---------------------------------------------------------------------------
# calls_in_order chain detection
# ---------------------------------------------------------------------------


class TestCallsInOrderChain:
    def test_two_call_nodes_with_next_control_form_chain(self) -> None:
        node_a = _node(
            node_id="node:call-a",
            predicate="CALL",
            operands=("fn_a",),
            result="r_a",
        )
        node_b = _node(
            node_id="node:call-b",
            predicate="CALL",
            operands=("fn_b",),
            result="r_b",
        )
        rel = _relation(
            relation_id="rel:next",
            kind="NEXT_CONTROL",
            source_node_id="node:call-a",
            target_node_id="node:call-b",
        )
        graph = _graph(nodes=[node_a, node_b], relations=[rel])
        result = _compile(
            graph,
            node_ids=["node:call-a", "node:call-b"],
            relation_ids=["rel:next"],
        )
        calls_in_order = [f for f in result.facts if f.predicate == "calls_in_order"]
        assert len(calls_in_order) == 1
        assert isinstance(calls_in_order[0].object, list)
        assert len(calls_in_order[0].object) == 2

    def test_single_call_node_becomes_calls_fact(self) -> None:
        node = _node(
            node_id="node:call-solo",
            predicate="CALL",
            operands=("fn",),
            result="r",
        )
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:call-solo"])
        calls_facts = [f for f in result.facts if f.predicate == "calls"]
        calls_in_order = [f for f in result.facts if f.predicate == "calls_in_order"]
        assert len(calls_facts) == 1
        assert calls_in_order == []


# ---------------------------------------------------------------------------
# configured_by relation facts
# ---------------------------------------------------------------------------


class TestConfiguredByFacts:
    def test_configured_by_relation_yields_fact(self) -> None:
        node = _node(node_id="node:cfg", predicate="CONSTRUCT")
        rel = _relation(
            relation_id="rel:cfg",
            kind="CONFIGURED_BY",
            source_node_id="node:cfg",
            target_node_id="",
            source_symbol_id="sym:module.func",
            target_symbol_id="sym:config.flags",
            source_span_id="span:module.py:1:10",
            target_span_id="span:config.py:5:8",
            guard="use_feature_x=True",
        )
        graph = _graph(nodes=[node], relations=[rel])
        result = _compile(
            graph,
            node_ids=["node:cfg"],
            relation_ids=["rel:cfg"],
        )
        cfg_facts = [f for f in result.facts if f.predicate == "configured_by"]
        assert len(cfg_facts) == 1
        assert cfg_facts[0].object == "sym:config.flags"
        assert "use_feature_x=True" in cfg_facts[0].conditions

    def test_configured_by_fact_preserves_exact_target_load_object(self) -> None:
        operation = _node(node_id="node:mask", predicate="MASK")
        config_load = _node(
            node_id="node:config-load",
            predicate="LOAD",
            operands=("self.config.iteration_threshold",),
        )
        rel = _relation(
            relation_id="rel:exact-config",
            kind="CONFIGURED_BY",
            source_node_id=operation.node_id,
            target_node_id=config_load.node_id,
            source_symbol_id=operation.symbol_id,
            target_symbol_id=config_load.symbol_id,
        )
        graph = _graph(nodes=[operation, config_load], relations=[rel])

        result = _compile(
            graph,
            node_ids=[operation.node_id],
            relation_ids=[rel.relation_id],
        )

        fact = next(item for item in result.facts if item.predicate == "configured_by")
        assert fact.object == ["self.config.iteration_threshold"]
        assert "self.config.iteration_threshold" in fact.semantic_context


# ---------------------------------------------------------------------------
# Fact id / predicate structure
# ---------------------------------------------------------------------------


class TestFactStructure:
    def test_fact_id_starts_with_obligation_prefix(self) -> None:
        node = _node(node_id="node:r", predicate="READ")
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:r"], obligation_id="obl-42")
        assert result.facts[0].fact_id.startswith("fact-obl-42-")

    def test_read_predicate_maps_to_reads(self) -> None:
        node = _node(node_id="node:read", predicate="READ")
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:read"])
        assert result.facts[0].predicate == "reads"

    def test_sort_predicate_maps_to_sorts_by(self) -> None:
        node = _node(node_id="node:sort", predicate="SORT")
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:sort"])
        assert result.facts[0].predicate == "sorts_by"

    def test_content_digest_is_stable(self) -> None:
        node = _node(node_id="node:r", predicate="READ")
        graph = _graph(nodes=[node])
        r1 = _compile(graph, node_ids=["node:r"])
        r2 = _compile(graph, node_ids=["node:r"])
        assert r1.content_digest == r2.content_digest


# ---------------------------------------------------------------------------
# R4.5 hard constraint: no project-specific literals in source
# ---------------------------------------------------------------------------


class TestNoProjectSpecificLiterals:
    @pytest.fixture
    def generic_compiler_sources(self) -> list[Path]:
        root = Path(__file__).resolve().parent.parent / "src" / "code2paper" / "agentic"
        return [
            root / "generic_fact_compiler.py",
            root / "generic_evidence_compiler.py",
            root / "generic_claim_compiler.py",
            root / "equation_claims.py",
        ]

    @pytest.mark.parametrize("forbidden", ["F-RAP-", "C-RAP-", "EBCAR", "DyG-Mamba", "LinearRAG"])
    def test_no_forbidden_literal_in_generic_sources(
        self, generic_compiler_sources: list[Path], forbidden: str
    ) -> None:
        for path in generic_compiler_sources:
            text = path.read_text(encoding="utf-8")
            # The docstring mentions the forbidden literals as a constraint
            # to *enforce*; that's allowed.  We only fail when the literal
            # appears in *code* (outside docstrings/comments).  As a simple
            # heuristic, strip triple-quoted docstrings and ``#`` comments.
            stripped = _strip_docstrings_and_comments(text)
            assert forbidden not in stripped, (
                f"forbidden literal {forbidden!r} appears in {path.name}"
            )


def _strip_docstrings_and_comments(text: str) -> str:
    """Remove triple-quoted strings and ``#`` comments for the literal scan."""

    import re

    # Remove triple-quoted strings (docstrings / multi-line strings).
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    text = re.sub(r"'''[\s\S]*?'''", "", text)
    # Remove ``#`` comments.
    lines = []
    for line in text.splitlines():
        if "#" in line:
            line = line.split("#", 1)[0]
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Q1 — exact condition ownership (plan 19.5.3)
# ---------------------------------------------------------------------------


class TestExactConditionOwnership:
    def test_unguarded_operation_before_guarded_branch_keeps_no_condition(self) -> None:
        transform = _node(
            node_id="node:transform", predicate="TRANSFORM", operands=("x",), result="y"
        )
        branch = _node(node_id="node:branch", predicate="BRANCH", guard="loss_i.shape[0] == 0")
        inside = _node(node_id="node:inside", predicate="REDUCE", operands=("loss",))
        rel = _relation(
            relation_id="rel:control",
            kind="CONTROL_DEPENDS_ON",
            source_node_id="node:branch",
            target_node_id="node:inside",
            guard="loss_i.shape[0] == 0",
        )
        graph = _graph(nodes=[transform, branch, inside], relations=[rel])
        result = _compile(
            graph,
            node_ids=["node:transform", "node:branch", "node:inside"],
            relation_ids=["rel:control"],
            guards=["loss_i.shape[0] == 0"],
        )
        transform_fact = next(f for f in result.facts if f.predicate == "transforms")
        assert transform_fact.conditions == []
        inside_fact = next(f for f in result.facts if f.predicate == "reduces")
        assert "loss_i.shape[0] == 0" in inside_fact.conditions

    def test_packet_guard_union_is_metadata_not_fact_truth_scope(self) -> None:
        node = _node(node_id="node:plain", predicate="READ", operands=("x",), result="y")
        graph = _graph(nodes=[node])
        result = _compile(graph, node_ids=["node:plain"], guards=["loss empty", "training_mode"])
        assert result.facts[0].conditions == []

    def test_same_obligation_adjacency_never_infers_a_condition(self) -> None:
        first = _node(node_id="node:first", predicate="READ", operands=("a",))
        second = _node(node_id="node:second", predicate="READ", operands=("b",))
        branch = _node(node_id="node:branch", predicate="BRANCH", guard="mode_is_eval")
        graph = _graph(nodes=[first, second, branch])
        result = _compile(
            graph,
            node_ids=["node:first", "node:second", "node:branch"],
            guards=["mode_is_eval"],
        )
        for fact in result.facts:
            if fact.predicate == "reads":
                assert fact.conditions == []

    def test_control_dependence_attaches_guard_only_to_its_exact_target(self) -> None:
        other = _node(node_id="node:other", predicate="READ", operands=("z",))
        branch = _node(node_id="node:branch", predicate="BRANCH", guard="training_mode")
        inside = _node(node_id="node:inside", predicate="COMPUTE", operands=("loss",))
        rel = _relation(
            relation_id="rel:control",
            kind="TRUE_BRANCH",
            source_node_id="node:branch",
            target_node_id="node:inside",
        )
        graph = _graph(nodes=[other, branch, inside], relations=[rel])
        result = _compile(
            graph,
            node_ids=["node:other", "node:branch", "node:inside"],
            relation_ids=["rel:control"],
            guards=["training_mode"],
        )
        other_fact = next(f for f in result.facts if f.predicate == "reads")
        assert other_fact.conditions == []
        inside_fact = next(f for f in result.facts if f.predicate == "computes_formula")
        assert "training_mode" in inside_fact.conditions
