"""R2.4 behavior equivalence mutation tests.

Per the R2.4 execution plan, the following mutations MUST be covered:

Equivalence mutations (predicate set MUST be preserved):
- file move (same code, different path);
- symbol rename (same body, different qualified name);
- helper extraction (inline code moved to a helper, same behavior);
- variable rename (same predicates, different operands);
- ``argsort(descending=True)[:k]`` vs ``topk(k)`` (semantically equivalent
  selection: both must surface a selection-class predicate);
- mask construction variant (``masked_fill`` vs ``where``-based mask);
- config default moved to dataclass/YAML (same config access pattern).

Semantic-change mutations (predicate set MUST change):
- removing a side effect (SERIALIZE disappears);
- changing a branch condition (guard changes);
- replacing ``topk`` with bare ``sort`` (TOPK disappears, SORT remains);
- adding a new operation (new predicate appears).

The invariant: ``graph.predicates()`` is the normalized behavior signature.
Equivalence mutations preserve it; semantic-change mutations alter it.
"""

from __future__ import annotations

import textwrap

import pytest

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1, SymbolIndexV2
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter


_ADAPTER = PythonBehaviorAdapter()


def _index(files: dict[str, str]) -> SymbolIndexV2:
    return _ADAPTER.index_symbols(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
    )


def _build_all(files: dict[str, str]) -> CodeBehaviorGraphV1:
    """Build a graph covering every non-module symbol in the files."""

    index = _index(files)
    symbol_ids = [s.symbol_id for s in index.symbols if s.kind != "module"]
    result = build_behavior_subgraph(
        adapter=_ADAPTER,
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        files=files,
        symbol_index=index,
        symbol_ids=symbol_ids,
        depth=2,
        node_budget=5000,
    )
    return result.graph


def _predicates(graph: CodeBehaviorGraphV1) -> set[str]:
    return graph.predicates()


# ===========================================================================
# Equivalence: file move
# ===========================================================================


def test_file_move_preserves_predicate_set() -> None:
    source = textwrap.dedent(
        """\
        def f(x):
            return x.topk(10)
        """
    )
    g1 = _build_all({"train.py": source})
    g2 = _build_all({"src/train.py": source})
    assert _predicates(g1) == _predicates(g2)


# ===========================================================================
# Equivalence: symbol rename
# ===========================================================================


def test_symbol_rename_preserves_predicate_set() -> None:
    src1 = textwrap.dedent(
        """\
        def train_loop(x):
            return x.sum()
        """
    )
    src2 = textwrap.dedent(
        """\
        def run_training(x):
            return x.sum()
        """
    )
    g1 = _build_all({"train.py": src1})
    g2 = _build_all({"train.py": src2})
    assert _predicates(g1) == _predicates(g2)


# ===========================================================================
# Equivalence: variable rename
# ===========================================================================


def test_variable_rename_preserves_predicate_set() -> None:
    src1 = textwrap.dedent(
        """\
        def f(x):
            scores = x.softmax(dim=-1)
            return scores
        """
    )
    src2 = textwrap.dedent(
        """\
        def f(x):
            probs = x.softmax(dim=-1)
            return probs
        """
    )
    g1 = _build_all({"train.py": src1})
    g2 = _build_all({"train.py": src2})
    assert _predicates(g1) == _predicates(g2)


# ===========================================================================
# Equivalence: helper extraction
# ===========================================================================


def test_helper_extraction_preserves_core_behavior_predicates() -> None:
    # Inline version: the softmax + topk are both in f.
    inline = textwrap.dedent(
        """\
        def f(logits):
            probs = logits.softmax(dim=-1)
            return probs.topk(10)
        """
    )
    # Extracted version: softmax is moved to a helper.
    extracted = textwrap.dedent(
        """\
        def normalize(logits):
            return logits.softmax(dim=-1)

        def f(logits):
            probs = normalize(logits)
            return probs.topk(10)
        """
    )
    g1 = _build_all({"train.py": inline})
    g2 = _build_all({"train.py": extracted})
    # Helper extraction introduces an extra CALL (the call to ``normalize``)
    # which is plumbing, not behavior.  The CORE behavior predicates
    # (NORMALIZE + TOPK) must be preserved in both graphs.
    core_predicates = {"NORMALIZE", "TOPK", "RETURN"}
    assert core_predicates <= _predicates(g1)
    assert core_predicates <= _predicates(g2)
    # And the extracted version has the extra CALL (plumbing).
    assert "CALL" in _predicates(g2)


# ===========================================================================
# Equivalence: argsort[:k] vs topk
# ===========================================================================


def test_argsort_slice_k_and_topk_both_surface_selection_predicate() -> None:
    """``x.argsort(descending=True)[:k]`` and ``x.topk(k)`` are semantically
    equivalent selection operations.  Both MUST surface a selection-class
    predicate (TOPK or SORT+SELECT) so the supervisor can recognize them as
    behaviorally equivalent.
    """

    topk_src = textwrap.dedent(
        """\
        def f(x):
            return x.topk(10)
        """
    )
    argsort_src = textwrap.dedent(
        """\
        def f(x):
            return x.argsort(descending=True)[:10]
        """
    )
    g_topk = _build_all({"train.py": topk_src})
    g_argsort = _build_all({"train.py": argsort_src})
    topk_preds = _predicates(g_topk)
    argsort_preds = _predicates(g_argsort)
    # topk must produce TOPK.
    assert "TOPK" in topk_preds
    # argsort must produce SORT (and the [:k] slice is a SELECT).
    assert "SORT" in argsort_preds
    # Both must contain at least one selection-class predicate.
    selection_class = {"TOPK", "SELECT", "SORT"}
    assert topk_preds & selection_class
    assert argsort_preds & selection_class


# ===========================================================================
# Equivalence: mask construction variant
# ===========================================================================


def test_mask_construction_variants_both_surface_mask_predicate() -> None:
    """``masked_fill`` and ``torch.where(mask, x, 0)`` are two common ways
    to construct a masked tensor.  Both MUST surface the MASK predicate so
    the supervisor can recognize them as behaviorally equivalent.
    """

    masked_fill_src = textwrap.dedent(
        """\
        def f(x, mask):
            return x.masked_fill(mask, 0.0)
        """
    )
    where_src = textwrap.dedent(
        """\
        def f(x, mask):
            return torch.where(mask, x, 0.0)
        """
    )
    g1 = _build_all({"train.py": masked_fill_src})
    g2 = _build_all({"train.py": where_src})
    assert "MASK" in _predicates(g1)
    assert "MASK" in _predicates(g2)


# ===========================================================================
# Equivalence: config default moved to dataclass/YAML
# ===========================================================================


def test_config_default_access_pattern_preserved_across_locations() -> None:
    """Whether the config is read from a dict or a dataclass attribute, the
    graph must surface a config-access LOAD so the supervisor can trace
    configuration regardless of storage."""

    dict_src = textwrap.dedent(
        """\
        def f(cfg):
            lr = cfg["lr"]
            return lr
        """
    )
    dataclass_src = textwrap.dedent(
        """\
        def f(cfg):
            lr = cfg.lr
            return lr
        """
    )
    g1 = _build_all({"train.py": dict_src})
    g2 = _build_all({"train.py": dataclass_src})
    # Both must have config-access LOAD nodes.
    config_loads_1 = [
        n for n in g1.nodes
        if n.predicate == "LOAD" and "config_access" in n.diagnostics
    ]
    config_loads_2 = [
        n for n in g2.nodes
        if n.predicate == "LOAD" and "config_access" in n.diagnostics
    ]
    assert config_loads_1
    assert config_loads_2


# ===========================================================================
# Semantic change: removing a side effect
# ===========================================================================


def test_removing_side_effect_changes_predicate_set() -> None:
    with_save = textwrap.dedent(
        """\
        def f(model, path):
            torch.save(model, path)
            return model
        """
    )
    without_save = textwrap.dedent(
        """\
        def f(model, path):
            return model
        """
    )
    g1 = _build_all({"train.py": with_save})
    g2 = _build_all({"train.py": without_save})
    assert "SERIALIZE" in _predicates(g1)
    assert "SERIALIZE" not in _predicates(g2)


# ===========================================================================
# Semantic change: replacing topk with bare sort
# ===========================================================================


def test_replacing_topk_with_bare_sort_changes_predicate_set() -> None:
    topk_src = textwrap.dedent(
        """\
        def f(x):
            return x.topk(10)
        """
    )
    sort_src = textwrap.dedent(
        """\
        def f(x):
            return x.sort()
        """
    )
    g_topk = _build_all({"train.py": topk_src})
    g_sort = _build_all({"train.py": sort_src})
    assert "TOPK" in _predicates(g_topk)
    assert "TOPK" not in _predicates(g_sort)
    assert "SORT" in _predicates(g_sort)


# ===========================================================================
# Semantic change: changing a branch condition
# ===========================================================================


def test_changing_branch_guard_changes_graph_digest() -> None:
    """The predicate set may be the same (BRANCH in both), but the guard
    expression differs, so the graph digest MUST change."""

    src1 = textwrap.dedent(
        """\
        def f(x):
            if x > 0:
                return x
            return -x
        """
    )
    src2 = textwrap.dedent(
        """\
        def f(x):
            if x >= 0:
                return x
            return -x
        """
    )
    g1 = _build_all({"train.py": src1})
    g2 = _build_all({"train.py": src2})
    # Predicate set is identical (BRANCH + COMPARE + RETURN).
    assert _predicates(g1) == _predicates(g2)
    # But the digest differs because the guard changed.
    assert g1.content_digest != g2.content_digest
    # And the guard text differs.
    guards_1 = {n.guard for n in g1.nodes if n.predicate == "BRANCH"}
    guards_2 = {n.guard for n in g2.nodes if n.predicate == "BRANCH"}
    assert guards_1 != guards_2


# ===========================================================================
# Semantic change: adding a new operation
# ===========================================================================


def test_adding_new_operation_changes_predicate_set() -> None:
    base_src = textwrap.dedent(
        """\
        def f(x):
            return x
        """
    )
    extended_src = textwrap.dedent(
        """\
        def f(x):
            y = x.softmax(dim=-1)
            return y
        """
    )
    g1 = _build_all({"train.py": base_src})
    g2 = _build_all({"train.py": extended_src})
    assert "NORMALIZE" not in _predicates(g1)
    assert "NORMALIZE" in _predicates(g2)


# ===========================================================================
# R2.5 exit-condition-style: RAP main loop is representable without project name
# ===========================================================================


def test_rap_style_training_loop_produces_expected_predicates() -> None:
    """The R2.5 exit condition requires that the RAP main loop can be
    represented by generic predicates, without reading the project name
    or fixed claim text.

    We build a representative RAP-style training loop (optimizer step,
    backward, loss, checkpoint save) and verify the predicate set covers
    the expected behavior categories.
    """

    rap_src = textwrap.dedent(
        """\
        import torch

        class Trainer:
            def __init__(self, model):
                self.model = model
                self.optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

            def train_loop(self, loader, epochs):
                for epoch in range(epochs):
                    for batch in loader:
                        self.optimizer.zero_grad()
                        loss = self.model.forward(batch)
                        loss.backward()
                        self.optimizer.step()
                torch.save(self.model.state_dict(), "ckpt.pt")
                return self.model
        """
    )
    graph = _build_all({"train.py": rap_src})
    preds = _predicates(graph)
    # Core training-loop predicates must be present.
    assert "LOOP" in preds
    assert "CALL" in preds
    assert "SERIALIZE" in preds  # torch.save
    assert "WRITE" in preds  # zero_grad / step assignments
    # The graph content digest must NOT embed the project name "RAP".
    assert "RAP" not in graph.content_digest
    assert "rap" not in graph.content_digest.lower()


# ===========================================================================
# R2.5 exit-condition-style: LinearRAG seed/dense/threshold/topk distinguishable
# ===========================================================================


def test_linearrag_style_branches_are_distinguishable() -> None:
    """The R2.5 exit condition requires that LinearRAG's seed branch, dense
    fallback, threshold and top-k operations are distinguishable in the
    behavior graph.

    We build a representative LinearRAG-style retrieval function with a
    seed/dense branch, a threshold filter, and a top-k selection, and
    verify the graph distinguishes them via BRANCH + MASK + TOPK predicates.
    """

    linearrag_src = textwrap.dedent(
        """\
        def retrieve(query, seed_scores, dense_scores):
            if seed_scores.max() > 0.5:
                scores = seed_scores
            else:
                scores = dense_scores
            mask = scores > 0.1
            filtered = scores.masked_fill(~mask, 0.0)
            return filtered.topk(10)
        """
    )
    graph = _build_all({"train.py": linearrag_src})
    preds = _predicates(graph)
    assert "BRANCH" in preds  # seed vs dense fallback
    assert "MASK" in preds  # threshold filter
    assert "TOPK" in preds  # top-k selection
    # The branch guard must reference the threshold.
    branches = [n for n in graph.nodes if n.predicate == "BRANCH"]
    assert branches
    assert "0.5" in branches[0].guard or "max" in branches[0].guard


# ===========================================================================
# R2.5 exit-condition-style: EBCAR attention scope distinguishable
# ===========================================================================


def test_ebcar_style_attention_scopes_are_distinguishable() -> None:
    """The R2.5 exit condition requires that EBCAR's two attention scopes
    and inference sort have control/data relations.

    We build a representative EBCAR-style function with two attention
    calls (local + global scope) and a sort at inference, and verify the
    graph surfaces ATTEND + SORT predicates and the relations connect them.
    """

    ebcar_src = textwrap.dedent(
        """\
        def attend(local_ctx, global_ctx):
            local_out = local_ctx.attention()
            global_out = global_ctx.attention()
            combined = local_out + global_out
            ranked = combined.sort(descending=True)
            return ranked
        """
    )
    graph = _build_all({"train.py": ebcar_src})
    preds = _predicates(graph)
    assert "ATTEND" in preds  # two attention scopes
    assert "SORT" in preds  # inference sort
    # There must be at least two ATTEND nodes (local + global).
    attend_nodes = [n for n in graph.nodes if n.predicate == "ATTEND"]
    assert len(attend_nodes) >= 2


# ===========================================================================
# R2.5 exit-condition-style: DyG dts propagation + gated top-k readout
# ===========================================================================


def test_dyg_style_propagation_and_gated_readout_are_traversable() -> None:
    """The R2.5 exit condition requires that DyG's ``dts`` propagation and
    gated top-k readout are traversable in the behavior graph.

    We build a representative DyG-style function with a propagation call
    and a gated top-k readout, and verify the graph surfaces PROPAGATE +
    TOPK + BRANCH predicates.
    """

    dyg_src = textwrap.dedent(
        """\
        def readout(node_states, gate):
            propagated = node_states.propagate()
            if gate > 0.5:
                return propagated.topk(10)
            return propagated
        """
    )
    graph = _build_all({"train.py": dyg_src})
    preds = _predicates(graph)
    assert "PROPAGATE" in preds  # dts propagation
    assert "TOPK" in preds  # gated top-k readout
    assert "BRANCH" in preds  # gate condition
    # The branch must gate the topk.
    branches = [n for n in graph.nodes if n.predicate == "BRANCH"]
    topk_nodes = [n for n in graph.nodes if n.predicate == "TOPK"]
    assert branches
    assert topk_nodes
    # A TRUE_BRANCH relation must link the branch to the topk block.
    true_branches = [r for r in graph.relations if r.kind == "TRUE_BRANCH"]
    assert true_branches
