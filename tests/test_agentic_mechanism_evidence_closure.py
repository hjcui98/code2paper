from __future__ import annotations

import pytest
from code2paper.agentic.behavior_graph import SymbolIndexV2, SymbolRefV1
from code2paper.agentic.mechanism_context_compiler import (
    DefinitionResolver,
    compile_mechanism_evidence_closures,
    resolve_active_path_status,
)


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
