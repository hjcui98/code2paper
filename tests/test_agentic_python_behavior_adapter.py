"""R2.1 tests for the Python AST behavior adapter.

Covers every R2.1 predicate category:

- module / class / function / method indexing;
- assignment, attribute/subscript read/write;
- call + argument binding + specialized method predicates
  (SORT / TOPK / MASK / FILTER / RESHAPE / CONCAT / STACK / REDUCE /
  NORMALIZE / COMPUTE / SERIALIZE);
- if/else guard (BRANCH);
- for/while loop (LOOP);
- return (RETURN);
- compare (COMPARE);
- arithmetic / matmul (COMPUTE);
- file write / serialization (WRITE / SERIALIZE);
- config / default access (LOAD with config_access diagnostic).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from code2paper.agentic.behavior_graph import (
    BehaviorNodeV1,
    CodeBehaviorGraphV1,
    SymbolRefV1,
    make_symbol_id,
)
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_ADAPTER = PythonBehaviorAdapter()


def _index_files(files: dict[str, str]):
    return _ADAPTER.index_symbols(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
    )


def _extract(symbol: SymbolRefV1, source: str):
    nodes = _ADAPTER.extract_operations(symbol, source)
    relations = _ADAPTER.extract_relations(symbol, source, nodes)
    return nodes, relations


def _first_symbol(index, qualified_name: str) -> SymbolRefV1:
    for sym in index.symbols:
        if sym.qualified_name == qualified_name:
            return sym
    raise AssertionError(f"symbol {qualified_name} not found in index")


# ---------------------------------------------------------------------------
# index_symbols
# ---------------------------------------------------------------------------


def test_index_symbols_finds_module_class_function_method() -> None:
    source = textwrap.dedent(
        """\
        class Trainer:
            def train_loop(self):
                pass

        def main():
            pass
        """
    )
    index = _index_files({"train.py": source})
    names = {s.qualified_name for s in index.symbols}
    assert "<module>" in names
    assert "Trainer" in names
    assert "Trainer.train_loop" in names
    assert "main" in names
    # Kinds are correctly assigned.
    kinds = {s.qualified_name: s.kind for s in index.symbols}
    assert kinds["<module>"] == "module"
    assert kinds["Trainer"] == "class"
    assert kinds["Trainer.train_loop"] == "method"
    assert kinds["main"] == "function"


def test_index_symbols_skips_non_python_files() -> None:
    index = _index_files({"train.py": "x = 1\n", "readme.md": "# readme\n"})
    assert index.indexed_files == 1
    assert index.indexed_symbols >= 1


def test_index_symbols_records_syntax_errors_as_warnings() -> None:
    index = _index_files({"broken.py": "def (\n"})
    assert any("syntax_error:broken.py" in w for w in index.warnings)


def test_index_symbols_is_content_addressed() -> None:
    files = {"train.py": "def f():\n    pass\n"}
    i1 = _index_files(files)
    i2 = _index_files(files)
    assert i1.content_digest == i2.content_digest
    assert i1.content_digest.startswith("sha256:")


# ---------------------------------------------------------------------------
# extract_operations: assignment / attribute / subscript
# ---------------------------------------------------------------------------


def test_extract_operations_assign_emits_write_node() -> None:
    source = "def f():\n    x = 1\n"
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    writes = [n for n in nodes if n.predicate == "WRITE"]
    assert writes, f"expected WRITE node, got {[n.predicate for n in nodes]}"
    assert writes[0].result == "x"


def test_extract_operations_preserves_global_file_line_numbers() -> None:
    source = "import os\n\n\ndef f():\n    return compute_value()\n"
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, relations = _extract(sym, source)

    call = next(node for node in nodes if node.predicate == "CALL")
    assert call.source_span_id == "span:train.py:5:5"
    assert all(
        relation.source_span_id.startswith("span:train.py:")
        for relation in relations
    )


def test_extract_operations_attribute_write() -> None:
    source = textwrap.dedent(
        """\
        def f(obj):
            obj.attr = 1
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    attr_writes = [n for n in nodes if n.predicate == "WRITE" and "attr_write" in n.diagnostics]
    assert attr_writes


def test_extract_operations_subscript_write() -> None:
    source = textwrap.dedent(
        """\
        def f(d):
            d["key"] = 1
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    sub_writes = [n for n in nodes if n.predicate == "WRITE" and "subscript_write" in n.diagnostics]
    assert sub_writes


def test_extract_operations_attribute_read_emits_load() -> None:
    source = textwrap.dedent(
        """\
        def f(obj):
            return obj.value
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    loads = [n for n in nodes if n.predicate == "LOAD" and "attr_read" in n.diagnostics]
    assert loads


def test_extract_operations_config_access_is_tagged() -> None:
    source = textwrap.dedent(
        """\
        def f(cfg):
            return cfg["lr"]
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    config_loads = [
        n for n in nodes if n.predicate == "LOAD" and "config_access" in n.diagnostics
    ]
    assert config_loads


def test_operation_using_config_value_emits_configured_by_relation() -> None:
    source = textwrap.dedent(
        """\
        def filter_scores(scores, config):
            return torch.where(scores >= config.threshold, scores, 0)
        """
    )
    index = _index_files({"filter.py": source})
    nodes, relations = _extract(_first_symbol(index, "filter_scores"), source)
    by_id = {node.node_id: node for node in nodes}
    relation = next(
        item for item in relations
        if item.kind == "CONFIGURED_BY"
        and by_id[item.source_node_id].predicate == "MASK"
    )

    assert by_id[relation.source_node_id].predicate == "MASK"
    assert by_id[relation.target_node_id].predicate == "LOAD"
    assert "config_access" in by_id[relation.target_node_id].diagnostics


def test_extract_operations_parameter_default_is_source_configuration() -> None:
    source = textwrap.dedent(
        """\
        def build(input_dim=15, *, enabled=True):
            return input_dim
        """
    )
    index = _index_files({"model.py": source})
    sym = _first_symbol(index, "build")
    nodes, _ = _extract(sym, source)
    defaults = [
        node
        for node in nodes
        if node.predicate == "READ" and "parameter_default" in node.diagnostics
    ]

    assert {node.result for node in defaults} == {"input_dim=15", "enabled=True"}
    assert all("config_access" in node.diagnostics for node in defaults)


# ---------------------------------------------------------------------------
# extract_operations: calls and specialized predicates
# ---------------------------------------------------------------------------


def test_extract_operations_generic_call_emits_call_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f():
            result = compute(1, 2)
            return result
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    calls = [n for n in nodes if n.predicate == "CALL"]
    assert calls
    # The call operands must include the function name and its arguments.
    operands = calls[0].operands
    assert calls[0].result == "result"
    assert "compute" in operands[0]


def test_value_producing_reduction_keeps_assignment_target() -> None:
    source = textwrap.dedent(
        """\
        def volume(scales):
            f_p_volume = torch.prod(scales, dim=1)
            return f_p_volume
        """
    )
    index = _index_files({"features.py": source})
    nodes, _ = _extract(_first_symbol(index, "volume"), source)

    reduction = next(node for node in nodes if node.predicate == "REDUCE")
    assert reduction.result == "f_p_volume"
    assert reduction.operands == ("torch.prod", "scales", "dim=1")


def test_extract_operations_torch_topk_emits_topk_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(scores):
            return scores.topk(10)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    topk_nodes = [n for n in nodes if n.predicate == "TOPK"]
    assert topk_nodes


def test_extract_operations_torch_sort_emits_sort_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(scores):
            return scores.sort(descending=True)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    sort_nodes = [n for n in nodes if n.predicate == "SORT"]
    assert sort_nodes


def test_extract_operations_torch_cat_emits_concat_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(a, b):
            return torch.cat([a, b], dim=0)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    concat_nodes = [n for n in nodes if n.predicate == "CONCAT"]
    assert concat_nodes


def test_extract_operations_torch_stack_emits_stack_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(a, b):
            return torch.stack([a, b])
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    stack_nodes = [n for n in nodes if n.predicate == "STACK"]
    assert stack_nodes


def test_extract_operations_softmax_emits_normalize_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(logits):
            return logits.softmax(dim=-1)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    norm_nodes = [n for n in nodes if n.predicate == "NORMALIZE"]
    assert norm_nodes


def test_extract_operations_named_division_emits_normalize_predicate() -> None:
    source = textwrap.dedent(
        """\
        def percentile_cutoff_normalize(clipped, lower, upper):
            normalized = (clipped - lower) / (upper - lower)
            return normalized
        """
    )
    index = _index_files({"features.py": source})
    sym = _first_symbol(index, "percentile_cutoff_normalize")

    nodes, _ = _extract(sym, source)

    normalized = [node for node in nodes if node.predicate == "NORMALIZE"]
    assert len(normalized) == 1
    assert normalized[0].result == "normalized"
    assert normalized[0].source_span_id.endswith(":2:2")


def test_extract_operations_sum_mean_emits_reduce_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return x.sum(), x.mean()
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    reduce_nodes = [n for n in nodes if n.predicate == "REDUCE"]
    assert len(reduce_nodes) >= 2


def test_extract_operations_masked_fill_emits_mask_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(x, mask):
            return x.masked_fill(mask, 0.0)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    mask_nodes = [n for n in nodes if n.predicate == "MASK"]
    assert mask_nodes


def test_extract_operations_reshape_view_emits_reshape_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return x.reshape(2, 3), x.view(3, 2)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    reshape_nodes = [n for n in nodes if n.predicate == "RESHAPE"]
    assert len(reshape_nodes) >= 2


def test_extract_operations_matmul_emits_compute_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(a, b):
            return a @ b
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    compute_nodes = [n for n in nodes if n.predicate == "COMPUTE" and "matmul" in n.diagnostics]
    assert compute_nodes


def test_graph_matrix_multiply_emits_compute_and_propagate_predicates() -> None:
    source = textwrap.dedent(
        """\
        def propagate(entity_scores, entity_to_sentence_sparse):
            return entity_scores @ entity_to_sentence_sparse
        """
    )
    index = _index_files({"graph.py": source})
    nodes, _ = _extract(_first_symbol(index, "propagate"), source)
    predicates = {node.predicate for node in nodes}
    assert {"COMPUTE", "PROPAGATE"} <= predicates


def test_sorted_and_pagerank_calls_emit_semantic_predicates() -> None:
    source = textwrap.dedent(
        """\
        def rank(graph, seeds):
            scores = nx.pagerank(graph, personalization=seeds)
            return sorted(scores.items(), key=lambda item: item[1])
        """
    )
    index = _index_files({"graph.py": source})
    nodes, _ = _extract(_first_symbol(index, "rank"), source)
    predicates = {node.predicate for node in nodes}
    assert {"PROPAGATE", "SORT"} <= predicates


def test_extract_operations_arithmetic_emits_compute_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(a, b):
            return a + b * c
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    compute_nodes = [n for n in nodes if n.predicate == "COMPUTE"]
    assert len(compute_nodes) >= 2  # one for *, one for +


# ---------------------------------------------------------------------------
# extract_operations: control flow
# ---------------------------------------------------------------------------


def test_extract_operations_if_emits_branch_with_guard() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                return x
            else:
                return -x
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    branches = [n for n in nodes if n.predicate == "BRANCH"]
    assert branches
    assert branches[0].guard == "x > 0"


def test_guarded_continue_emits_filter_with_exact_guard() -> None:
    source = textwrap.dedent(
        """\
        def retain(scores, threshold):
            kept = []
            for score in scores:
                if score < threshold:
                    continue
                kept.append(score)
            return kept
        """
    )
    index = _index_files({"filter.py": source})
    sym = _first_symbol(index, "retain")
    nodes, _ = _extract(sym, source)

    filters = [node for node in nodes if node.predicate == "FILTER"]

    assert len(filters) == 1
    assert filters[0].operands == ("score < threshold",)
    assert filters[0].guard == "score < threshold"
    assert filters[0].diagnostics == ("guarded_continue",)


def test_selective_scan_primitive_emits_filter_operation() -> None:
    source = textwrap.dedent(
        """\
        def forward(x, state):
            return selective_scan_fn(x, state)
        """
    )
    index = _index_files({"ssm.py": source})
    sym = _first_symbol(index, "forward")
    nodes, _ = _extract(sym, source)

    filters = [node for node in nodes if node.predicate == "FILTER"]

    assert len(filters) == 1
    assert filters[0].operands[0] == "selective_scan_fn"


def test_extract_operations_for_emits_loop_with_iteration_context() -> None:
    source = textwrap.dedent(
        """\
        def f(items):
            for item in items:
                process(item)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    loops = [n for n in nodes if n.predicate == "LOOP"]
    assert loops
    assert "for item in items" in loops[0].iteration_context


def test_current_next_assignment_emits_level_synchronous_propagation() -> None:
    source = textwrap.dedent(
        """\
        def propagate(current_scores, steps):
            for step in range(steps):
                next_scores = update(current_scores)
                current_scores = compact(next_scores)
            return current_scores
        """
    )
    index = _index_files({"propagate.py": source})
    sym = _first_symbol(index, "propagate")
    nodes, _ = _extract(sym, source)

    propagation = [node for node in nodes if node.predicate == "PROPAGATE"]

    assert len(propagation) == 1
    assert propagation[0].operands == (
        "breadth first level synchronous frontier propagation",
        "current_scores",
        "next_scores",
    )
    assert propagation[0].diagnostics == ("current_next_frontier",)


def test_extract_operations_while_emits_loop_with_guard() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            while x > 0:
                x = x - 1
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    loops = [n for n in nodes if n.predicate == "LOOP"]
    assert loops
    assert loops[0].guard == "x > 0"


def test_extract_operations_recognizes_level_synchronous_frontier_propagation() -> None:
    source = textwrap.dedent(
        """\
        def traverse(frontier):
            while len(frontier) > 0:
                next_frontier = {}
                for key, value in frontier.items():
                    next_frontier[key] = value + 1
                frontier = next_frontier.copy()
            return frontier
        """
    )
    index = _index_files({"graph.py": source})
    sym = _first_symbol(index, "traverse")
    nodes, _ = _extract(sym, source)

    propagation = [node for node in nodes if node.predicate == "PROPAGATE"]

    assert len(propagation) == 1
    assert propagation[0].operands == (
        "breadth first frontier propagation",
        "frontier",
        "next_frontier",
    )
    assert propagation[0].diagnostics == ("level_synchronous_frontier",)


def test_extract_operations_does_not_label_plain_while_loop_breadth_first() -> None:
    source = textwrap.dedent(
        """\
        def countdown(x):
            while x > 0:
                x = x - 1
            return x
        """
    )
    index = _index_files({"plain.py": source})
    sym = _first_symbol(index, "countdown")
    nodes, _ = _extract(sym, source)

    assert not [node for node in nodes if node.predicate == "PROPAGATE"]


def test_extract_operations_return_emits_return_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f():
            return 42
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    returns = [n for n in nodes if n.predicate == "RETURN"]
    assert returns


def test_extract_operations_compare_emits_compare_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(a, b):
            if a < b:
                return a
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    compares = [n for n in nodes if n.predicate == "COMPARE"]
    assert compares


# ---------------------------------------------------------------------------
# extract_operations: file write / serialization
# ---------------------------------------------------------------------------


def test_extract_operations_open_write_emits_write_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(path):
            with open(path, "w") as f:
                f.write("hello")
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    write_nodes = [n for n in nodes if n.predicate == "WRITE"]
    assert write_nodes
    # At least one write must be tagged as a file open write.
    assert any("file_open_write" in n.diagnostics for n in write_nodes)


def test_extract_operations_torch_save_emits_serialize_predicate() -> None:
    source = textwrap.dedent(
        """\
        def f(model, path):
            torch.save(model.state_dict(), path)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, _ = _extract(sym, source)
    serialize_nodes = [n for n in nodes if n.predicate == "SERIALIZE"]
    assert serialize_nodes


# ---------------------------------------------------------------------------
# extract_relations: branches and loops
# ---------------------------------------------------------------------------


def test_extract_relations_if_emits_true_and_false_branch() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                a = 1
            else:
                a = 2
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, relations = _extract(sym, source)
    true_branches = [r for r in relations if r.kind == "TRUE_BRANCH"]
    false_branches = [r for r in relations if r.kind == "FALSE_BRANCH"]
    assert true_branches
    assert false_branches


def test_extract_relations_for_loop_emits_next_control() -> None:
    source = textwrap.dedent(
        """\
        def f(items):
            for item in items:
                process(item)
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, relations = _extract(sym, source)
    next_ctrl = [r for r in relations if r.kind == "NEXT_CONTROL"]
    assert next_ctrl


def test_extract_relations_return_emits_returns_to() -> None:
    source = textwrap.dedent(
        """\
        def f():
            return 42
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes, relations = _extract(sym, source)
    returns_to = [r for r in relations if r.kind == "RETURNS_TO"]
    assert returns_to


# ---------------------------------------------------------------------------
# resolve_references
# ---------------------------------------------------------------------------


def test_resolve_references_finds_imports_and_usages() -> None:
    files = {
        "model.py": textwrap.dedent(
            """\
            class Model:
                pass
            """
        ),
        "train.py": textwrap.dedent(
            """\
            from model import Model

            def f():
                return Model()
            """
        ),
    }
    index = _index_files(files)
    model_sym = _first_symbol(index, "Model")
    refs = _ADAPTER.resolve_references(model_sym, index, files)
    paths = {site.path for site in refs.sites}
    assert "train.py" in paths
    # The definition site in model.py must NOT appear (it's not a reference).
    assert "model.py" not in paths


# ---------------------------------------------------------------------------
# Stable IDs and determinism
# ---------------------------------------------------------------------------


def test_extract_operations_is_deterministic_across_calls() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                return x.topk(10)
            return None
        """
    )
    index = _index_files({"train.py": source})
    sym = _first_symbol(index, "f")
    nodes1, rels1 = _extract(sym, source)
    nodes2, rels2 = _extract(sym, source)
    assert [n.node_id for n in nodes1] == [n.node_id for n in nodes2]
    assert [r.relation_id for r in rels1] == [r.relation_id for r in rels2]


def test_extract_operations_node_ids_are_stable_for_same_source() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return x + 1
        """
    )
    index1 = _index_files({"train.py": source})
    index2 = _index_files({"train.py": source})
    sym1 = _first_symbol(index1, "f")
    sym2 = _first_symbol(index2, "f")
    assert sym1.symbol_id == sym2.symbol_id
    nodes1, _ = _extract(sym1, source)
    nodes2, _ = _extract(sym2, source)
    assert [n.node_id for n in nodes1] == [n.node_id for n in nodes2]


# ---------------------------------------------------------------------------
# Full graph build (index + extract for all symbols)
# ---------------------------------------------------------------------------


def test_full_graph_build_for_typical_training_file() -> None:
    """End-to-end: index a training file, extract all symbol subgraphs,
    merge into a single CodeBehaviorGraphV1, and verify the predicate set
    covers the RAP-style training loop without reading any project name."""

    source = textwrap.dedent(
        """\
        import torch
        import torch.nn as nn

        from model import GaussianModel


        class Trainer:
            def __init__(self):
                self.model = GaussianModel()
                self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-4)

            def train_loop(self, dataset, epochs):
                last_loss = None
                for epoch in range(epochs):
                    for batch in dataset:
                        self.optimizer.zero_grad()
                        loss = self.model.forward(batch)
                        loss.backward()
                        self.optimizer.step()
                        last_loss = loss
                torch.save(self.model.state_dict(), "ckpt.pt")
                return last_loss


        def main():
            trainer = Trainer()
            trainer.train_loop(range(10), 100)
            return trainer
        """
    )
    files = {"train.py": source}
    index = _index_files(files)
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        language="python",
    )
    for sym in index.symbols:
        if sym.kind == "module":
            continue
        nodes = _ADAPTER.extract_operations(sym, source)
        relations = _ADAPTER.extract_relations(sym, source, nodes)
        sym_graph = CodeBehaviorGraphV1(
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            language="python",
            nodes=nodes,
            relations=relations,
        )
        graph = graph.merge(sym_graph)
    graph = graph.with_digest()
    # The graph must cover the core training-loop predicates.
    preds = graph.predicates()
    assert "LOOP" in preds
    assert "CALL" in preds
    assert "RETURN" in preds
    assert "WRITE" in preds  # zero_grad / step
    assert "SERIALIZE" in preds  # torch.save
    # The graph must NOT carry the project name as a predicate.
    assert "RAP" not in graph.content_digest
    # And the content digest must be stable.
    assert graph.content_digest.startswith("sha256:")
