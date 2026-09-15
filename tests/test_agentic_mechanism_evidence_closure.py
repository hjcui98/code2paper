from __future__ import annotations

import pytest
from code2paper.agentic.behavior_graph import SymbolIndexV2, SymbolRefV1
from code2paper.agentic.mechanism_context_compiler import (
    DefinitionResolver,
    _reachable_graph_nodes,
    compile_mechanism_evidence_closures,
    resolve_active_path_status,
)
from code2paper.agentic.research_models import ImplementationScopeV1


def test_definition_resolver_finds_exact_and_unique_qname() -> None:
    symbols = [
        SymbolRefV1(
            symbol_id="sym:model:forward",
            path="src/model.py",
            qualified_name="Model.forward",
            kind="method",
            start_line=10,
            end_line=25,
        ),
        SymbolRefV1(
            symbol_id="sym:utils:run_ppr",
            path="src/utils.py",
            qualified_name="run_ppr",
            kind="function",
            start_line=1,
            end_line=15,
        ),
    ]
    index = SymbolIndexV2(
        repo_snapshot_id="snap:1",
        project_tree_hash="hash:1",
        symbols=symbols,
    )
    def dummy_provider(path: str, start: int, end: int) -> str:
        return f"# code in {path} lines {start}-{end}"

    resolver = DefinitionResolver(symbol_index=index, source_provider=dummy_provider)

    # 1. Exact symbol_id
    res1 = resolver.resolve_symbol("sym:model:forward")
    assert res1 is not None
    assert res1.qualified_name == "Model.forward"
    body1 = resolver.read_definition_body(res1)
    assert "src/model.py lines 10-25" in body1

    # 2. Globally unique tail
    res2 = resolver.resolve_symbol("run_ppr")
    assert res2 is not None
    assert res2.path == "src/utils.py"

    # 3. Unknown symbol never guesses
    res3 = resolver.resolve_symbol("unknown_function")
    assert res3 is None


def test_active_path_resolution_precedence() -> None:
    # 1. Debug/logging is unreachable
    assert resolve_active_path_status(symbol_name="debug_logging") == "unreachable"

    # 2. Vectorized alternative is inactive_default unless configured
    assert resolve_active_path_status(symbol_name="calculate_scores_vectorized") == "inactive_default"
    assert resolve_active_path_status(
        symbol_name="calculate_scores_vectorized",
        author_config_overrides={"mode": "vectorized"},
    ) == "active_selected"

    # 3. Guard implies conditional
    assert resolve_active_path_status(symbol_name="forward", guard="dim > 0") == "conditional"

    # 4. Standard active default
    assert resolve_active_path_status(symbol_name="forward") == "active_default"


def test_mechanism_graph_projection_does_not_walk_executable_edges_backward() -> None:
    nodes = {
        "upstream": {"node_id": "upstream", "symbol_id": "sym:up"},
        "downstream": {"node_id": "downstream", "symbol_id": "sym:down"},
    }
    relations = {
        "rel:call": {
            "relation_id": "rel:call",
            "kind": "CALLS",
            "source_node_id": "upstream",
            "target_node_id": "downstream",
        },
    }

    selected, selected_relations = _reachable_graph_nodes(
        nodes=nodes,
        relations=relations,
        entry_symbols=(),
        selected_seed_ids=("downstream",),
    )

    assert selected == {"downstream"}
    assert selected_relations == set()


def test_each_scope_entry_creates_a_distinct_owner_seed() -> None:
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=("sym:entry-a", "sym:entry-b"),
        target_core_symbol_ids=("sym:entry-a", "sym:entry-b"),
    )
    facts = [
        {
            "fact_id": "fact:a",
            "subject": "sym:entry-a",
            "scope": "sym:entry-a",
            "predicate": "transform",
            "operands": ["x"],
            "result": "a",
            "direct_span_ids": ["span:a.py:1:2"],
        },
        {
            "fact_id": "fact:b",
            "subject": "sym:entry-b",
            "scope": "sym:entry-b",
            "predicate": "transform",
            "operands": ["y"],
            "result": "b",
            "direct_span_ids": ["span:b.py:1:2"],
        },
    ]

    closures = compile_mechanism_evidence_closures(
        facts=facts,
        implementation_scope=scope,
    )

    assert {closure.owner_anchor_id for closure in closures} == {
        "sym:entry-a",
        "sym:entry-b",
    }
    assert all(closure.seed_kind == "executable" for closure in closures)


def test_compile_mechanism_evidence_closures_lossless_membership() -> None:
    mock_facts = [
        {
            "fact_id": "fact:1",
            "subject": "input_tensor",
            "predicate": "encode",
            "operands": ["nodes", "edges"],
            "result": "embeddings",
            "direct_span_ids": ["span:model.py:10:15"],
            "scope": "Model.forward",
        },
        {
            "fact_id": "fact:2",
            "subject": "embeddings",
            "predicate": "selective_scan",
            "operands": ["embeddings", "delta"],
            "result": "states",
            "direct_span_ids": ["span:model.py:20:30"],
            "scope": "Model.forward",
        },
    ]
    facets = [
        {
            "facet_id": "facet:encoding",
            "mechanism_id": "mech_mamba_ssm",
            "author_statement": "Four-channel continuous state-space modeling.",
        },
    ]
    alignments = [
        {
            "facet_id": "facet:encoding",
            "bound_fact_ids": ["fact:1", "fact:2"],
            "bound_span_ids": ["span:model.py:10:15", "span:model.py:20:30"],
        },
    ]

    closures = compile_mechanism_evidence_closures(
        facets=facets,
        facet_alignments=alignments,
        facts=mock_facts,
    )

    assert len(closures) == 1
    closure = closures[0]
    assert closure.mechanism_id == "mech_mamba_ssm"
    assert len(closure.operation_nodes) == 2
    op_predicates = [op.predicate for op in closure.operation_nodes]
    assert op_predicates == ["encode", "selective_scan"]
    assert "span:model.py:10:15" in closure.exact_span_ids
    assert "span:model.py:20:30" in closure.exact_span_ids
    assert closure.default_activation == "active_default"


# ---------------------------------------------------------------------------
# R1: canonical operation / guard / status alignment across the fact and graph
# views.  The fixtures are project-neutral; they mirror the frozen Run E shape
# (a guarded call whose graph node carries no local guard but is dominated by
# a typed TRUE_BRANCH edge) without importing any project path or symbol.
# ---------------------------------------------------------------------------

_DUAL_SPAN = "span:src/model.py:146:149"
_DUAL_BRANCH_SPAN = "span:src/model.py:145:174"


def _dual_view_facts(
    *,
    guard: str = "self.cfg.use_dedicated_attention",
    predicate: str = "calls",
    operands: tuple[str, ...] = ("torch.zeros", "shape", "device=self.device"),
) -> list[dict[str, object]]:
    return [{
        "fact_id": "fact:dual:zero-mask",
        "subject": "Model.forward",
        "predicate": predicate,
        "operands": list(operands),
        "result": "dedicated_attention_mask",
        "conditions": [guard] if guard else [],
        "scope": "sym:model_forward",
        "direct_span_ids": [_DUAL_SPAN],
        "relation_evidence_ids": ["rel:true-branch-mask"],
        "relation_kinds": ["TRUE_BRANCH"],
        "validation_status": "supported",
        "validation_failures": [],
    }]


def _dual_view_graph(
    *,
    branch_guard: str = "self.cfg.use_dedicated_attention",
    branch_span: str = _DUAL_BRANCH_SPAN,
    call_guard: str = "",
    call_predicate: str = "CALL",
    call_operands: tuple[str, ...] = ("torch.zeros", "shape", "device=self.device"),
    include_call: bool = True,
    extra_relations: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    nodes: list[dict[str, object]] = [{
        "node_id": "node:branch-mask",
        "symbol_id": "sym:model_forward",
        "predicate": "BRANCH",
        "operands": [branch_guard],
        "result": "",
        "guard": branch_guard,
        "source_span_id": branch_span,
    }]
    relations: list[dict[str, object]] = [{
        "relation_id": "rel:true-branch-mask",
        "kind": "TRUE_BRANCH",
        "source_node_id": "node:branch-mask",
        "target_node_id": "node:call-zeros",
        "source_span_id": branch_span,
        "target_span_id": _DUAL_SPAN,
        "guard": branch_guard,
    }]
    if include_call:
        nodes.append({
            "node_id": "node:call-zeros",
            "symbol_id": "sym:model_forward",
            "predicate": call_predicate,
            "operands": list(call_operands),
            "result": "dedicated_attention_mask",
            "guard": call_guard,
            "source_span_id": _DUAL_SPAN,
        })
    relations.extend(extra_relations)
    return {"nodes": nodes, "relations": relations}


def _dual_scope() -> ImplementationScopeV1:
    return ImplementationScopeV1(
        target_entry_symbol_ids=("sym:model_forward",),
        target_core_symbol_ids=("sym:model_forward",),
    )


def _operations_at_dual_span(closures: tuple[object, ...]) -> list[object]:
    return [
        operation
        for closure in closures
        for operation in closure.operation_nodes  # type: ignore[attr-defined]
        if operation.source_span_id == _DUAL_SPAN
    ]


def test_graph_branch_dominance_recovers_guard_from_typed_true_branch() -> None:
    closures = compile_mechanism_evidence_closures(
        facts=_dual_view_facts(),
        behavior_graph=_dual_view_graph(),
        implementation_scope=_dual_scope(),
    )

    graph_ops = {
        operation.operation_id: operation
        for operation in _operations_at_dual_span(closures)
        if str(operation.operation_id).startswith("graph-operation:")
    }
    call = graph_ops["graph-operation:node:call-zeros"]
    # The node carried no local guard; the typed TRUE_BRANCH edge and the
    # enclosing branch span prove the conditional execution and are recorded
    # as the activation basis.
    assert call.guard == "self.cfg.use_dedicated_attention"
    assert call.active_path_status == "conditional"
    assert call.activation_basis_ids == ("rel:true-branch-mask",)


def test_graph_branch_dominance_extends_over_next_control_within_span() -> None:
    graph = _dual_view_graph()
    graph["nodes"].append({
        "node_id": "node:write-mask",
        "symbol_id": "sym:model_forward",
        "predicate": "WRITE",
        "operands": ["dedicated_attention_mask"],
        "result": "dedicated_attention_mask",
        "guard": "",
        "source_span_id": "span:src/model.py:146:146",
    })
    graph["relations"].append({
        "relation_id": "rel:next-control",
        "kind": "NEXT_CONTROL",
        "source_node_id": "node:call-zeros",
        "target_node_id": "node:write-mask",
        "source_span_id": _DUAL_SPAN,
        "target_span_id": "span:src/model.py:146:146",
        "guard": "",
    })

    closures = compile_mechanism_evidence_closures(
        facts=_dual_view_facts(),
        behavior_graph=graph,
        implementation_scope=_dual_scope(),
    )

    write = next(
        operation
        for closure in closures
        for operation in closure.operation_nodes
        if operation.source_span_id == "span:src/model.py:146:146"
    )
    assert write.guard == "self.cfg.use_dedicated_attention"
    assert write.active_path_status == "conditional"
    assert write.activation_basis_ids == ("rel:next-control",)


def test_graph_branch_dominance_reports_polarity_conflict() -> None:
    graph = _dual_view_graph(extra_relations=({
        "relation_id": "rel:false-branch-mask",
        "kind": "FALSE_BRANCH",
        "source_node_id": "node:branch-mask",
        "target_node_id": "node:call-zeros",
        "source_span_id": _DUAL_BRANCH_SPAN,
        "target_span_id": _DUAL_SPAN,
        "guard": "self.cfg.use_dedicated_attention",
    },))

    closures = compile_mechanism_evidence_closures(
        facts=_dual_view_facts(),
        behavior_graph=graph,
        implementation_scope=_dual_scope(),
    )

    call = next(
        operation
        for operation in _operations_at_dual_span(closures)
        if str(operation.operation_id).startswith("graph-operation:")
    )
    # The same frozen guard claiming both polarities is a graph conflict: the
    # operation stays unknown and the claim stays auditable.
    assert call.guard == ""
    assert call.active_path_status == "unknown"
    assert "path_polarity_conflict:self.cfg.use_dedicated_attention" in call.activation_basis_ids
    assert "rel:true-branch-mask" in call.activation_basis_ids
    assert "rel:false-branch-mask" in call.activation_basis_ids


def test_graph_branch_dominance_gap_is_not_aligned() -> None:
    graph = _dual_view_graph(branch_span="span:src/model.py:100:110")

    closures = compile_mechanism_evidence_closures(
        facts=_dual_view_facts(),
        behavior_graph=graph,
        implementation_scope=_dual_scope(),
    )

    call = next(
        operation
        for operation in _operations_at_dual_span(closures)
        if str(operation.operation_id).startswith("graph-operation:")
    )
    # A guarded typed edge whose branch span does not contain the node span
    # proves nothing about this operation; the gap is reported instead.
    assert call.guard == ""
    assert call.active_path_status == "active_default"
    assert call.activation_basis_ids == (
        "unproven_dominance:self.cfg.use_dedicated_attention",
        "rel:true-branch-mask",
    )


def test_graph_reverse_branch_preserves_negative_polarity() -> None:
    graph = {
        "nodes": [
            {
                "node_id": "node:branch-mask",
                "symbol_id": "sym:model_forward",
                "predicate": "BRANCH",
                "operands": ["self.cfg.use_dedicated_attention"],
                "result": "",
                "guard": "self.cfg.use_dedicated_attention",
                "source_span_id": _DUAL_BRANCH_SPAN,
            },
            {
                "node_id": "node:call-zeros",
                "symbol_id": "sym:model_forward",
                "predicate": "CALL",
                "operands": ["torch.zeros", "shape", "device=self.device"],
                "result": "dedicated_attention_mask",
                "guard": "",
                "source_span_id": _DUAL_SPAN,
            },
        ],
        "relations": [{
            "relation_id": "rel:false-branch-mask",
            "kind": "FALSE_BRANCH",
            "source_node_id": "node:branch-mask",
            "target_node_id": "node:call-zeros",
            "source_span_id": _DUAL_BRANCH_SPAN,
            "target_span_id": _DUAL_SPAN,
            "guard": "self.cfg.use_dedicated_attention",
        }],
    }

    closures = compile_mechanism_evidence_closures(
        facts=_dual_view_facts(guard=""),
        behavior_graph=graph,
        implementation_scope=_dual_scope(),
    )

    call = next(
        operation
        for operation in _operations_at_dual_span(closures)
        if str(operation.operation_id).startswith("graph-operation:")
    )
    assert call.active_path_status == "conditional"
    assert call.guard == "not (self.cfg.use_dedicated_attention)"
    assert call.activation_basis_ids == ("rel:false-branch-mask",)


def test_graph_nested_conjunction_is_order_invariant() -> None:
    def nested(relations: list[dict[str, object]], nodes: list[dict[str, object]]):
        return compile_mechanism_evidence_closures(
            facts=_dual_view_facts(guard=""),
            behavior_graph={"nodes": nodes, "relations": relations},
            implementation_scope=_dual_scope(),
        )

    nodes = [
        {
            "node_id": "node:outer",
            "symbol_id": "sym:model_forward",
            "predicate": "BRANCH",
            "operands": ["G1"],
            "result": "",
            "guard": "G1",
            "source_span_id": "span:src/model.py:100:200",
        },
        {
            "node_id": "node:inner",
            "symbol_id": "sym:model_forward",
            "predicate": "BRANCH",
            "operands": ["G2"],
            "result": "",
            "guard": "G2",
            "source_span_id": "span:src/model.py:120:160",
        },
        {
            "node_id": "node:entry-op",
            "symbol_id": "sym:model_forward",
            "predicate": "CALL",
            "operands": ["embedding"],
            "result": "entry_value",
            "guard": "",
            "source_span_id": "span:src/model.py:121:121",
        },
        {
            "node_id": "node:call-zeros",
            "symbol_id": "sym:model_forward",
            "predicate": "CALL",
            "operands": ["torch.zeros", "shape", "device=self.device"],
            "result": "dedicated_attention_mask",
            "guard": "",
            "source_span_id": _DUAL_SPAN,
        },
    ]
    relations = [
        {
            "relation_id": "rel:outer",
            "kind": "TRUE_BRANCH",
            "source_node_id": "node:outer",
            "target_node_id": "node:entry-op",
            "source_span_id": "span:src/model.py:100:200",
            "target_span_id": "span:src/model.py:121:121",
            "guard": "G1",
        },
        {
            "relation_id": "rel:inner",
            "kind": "TRUE_BRANCH",
            "source_node_id": "node:inner",
            "target_node_id": "node:call-zeros",
            "source_span_id": "span:src/model.py:120:160",
            "target_span_id": _DUAL_SPAN,
            "guard": "G2",
        },
        {
            "relation_id": "rel:next",
            "kind": "NEXT_CONTROL",
            "source_node_id": "node:entry-op",
            "target_node_id": "node:call-zeros",
            "source_span_id": "span:src/model.py:121:121",
            "target_span_id": _DUAL_SPAN,
            "guard": "",
        },
    ]

    forward = _operations_at_dual_span(nested(relations, nodes))
    reversed_result = _operations_at_dual_span(
        nested(list(reversed(relations)), list(reversed(nodes)))
    )

    forward_guards = sorted(
        operation.guard
        for operation in forward
        if str(operation.operation_id).startswith("graph-operation:")
    )
    reversed_guards = sorted(
        operation.guard
        for operation in reversed_result
        if str(operation.operation_id).startswith("graph-operation:")
    )
    # Nested conditions keep the required conjunction; the normalized text is
    # traversal-order independent (sorted conjuncts).
    assert forward_guards == ["G1 and G2"]
    assert reversed_guards == ["G1 and G2"]
