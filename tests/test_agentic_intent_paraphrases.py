"""R5.4 paraphrase-invariance tests for the V2 intent compiler.

R5.4 exit condition: ``同一意图的中文、英文、同义改写和 stage 重排必须形成
等价 behavior targets``.  This module verifies the *同义改写* and *stage 重排*
halves.  The multilingual half lives in ``test_agentic_intent_multilingual.py``.

Equivalence is checked via ``typed_targets_signature``, which collapses each
typed target to a ``(kind, predicate_set, relation_set, condition_set)`` tuple.
Two summaries that compile to the same signature express the same semantic
intent regardless of wording or stage order.
"""

from __future__ import annotations

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.intent_compiler_v2 import (
    compile_intent_obligation_graph_v2,
    typed_targets_signature,
)


def _canonical_summary() -> AuthorIntentSummary:
    return AuthorIntentSummary(
        project_goal="Predict primitive importance without paper text as evidence.",
        method_goal="Score and prune low-importance primitives.",
        implementation_scope="Provided inference entrypoint.",
        method_mainline=(
            "Load a predictor, compute per-primitive scores, and prune "
            "low-ranked primitives."
        ),
        story_order=["Feature construction", "Score prediction", "Pruning"],
        priority_files=["prune_percent.py"],
        module_roles=[
            "utils/net_utils.py::PrunePredictor: predict one importance score per primitive",
        ],
        pipeline_steps=[
            "Feature construction: build per-primitive descriptors",
            "Pruning: sort scores, construct a mask, and remove low-ranked primitives",
        ],
        design_intents=["Avoid rendering in the scoped inference function."],
        innovation_claims=["Three training losses learn the importance predictor."],
    )


# ---------------------------------------------------------------------------
# Paraphrase invariance: same intent, different wording
# ---------------------------------------------------------------------------


def test_paraphrased_method_mainline_produces_equivalent_targets() -> None:
    """Paraphrasing the method_mainline must not change the typed targets."""

    canonical = _canonical_summary()
    paraphrased = AuthorIntentSummary(
        project_goal=canonical.project_goal,
        method_goal=canonical.method_goal,
        implementation_scope=canonical.implementation_scope,
        method_mainline=(
            # Same intent, different wording.  Avoid introducing new trigger
            # words (e.g. "inference") that would match additional concepts.
            "Load the predictor, produce one score per primitive, and then "
            "prune the low-ranked ones."
        ),
        story_order=canonical.story_order,
        priority_files=canonical.priority_files,
        module_roles=canonical.module_roles,
        pipeline_steps=canonical.pipeline_steps,
        design_intents=canonical.design_intents,
        innovation_claims=canonical.innovation_claims,
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(paraphrased).obligations
    )
    assert sig_a == sig_b, (
        "Paraphrasing method_mainline must produce the same typed target signature.\n"
        f"canonical:   {sorted(sig_a)}\n"
        f"paraphrased: {sorted(sig_b)}"
    )


def test_paraphrased_pipeline_steps_produce_equivalent_targets() -> None:
    """Paraphrasing each pipeline step must not change the typed targets."""

    canonical = _canonical_summary()
    paraphrased = AuthorIntentSummary(
        project_goal=canonical.project_goal,
        method_goal=canonical.method_goal,
        implementation_scope=canonical.implementation_scope,
        method_mainline=canonical.method_mainline,
        story_order=canonical.story_order,
        priority_files=canonical.priority_files,
        module_roles=canonical.module_roles,
        pipeline_steps=[
            # Same intent, different wording.
            "Build a per-primitive feature descriptor for each primitive.",
            "Sort the predictor scores, build a boolean mask, and drop the low-ranked primitives.",
        ],
        design_intents=canonical.design_intents,
        innovation_claims=canonical.innovation_claims,
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(paraphrased).obligations
    )
    assert sig_a == sig_b, (
        "Paraphrasing pipeline_steps must produce the same typed target signature.\n"
        f"canonical:   {sorted(sig_a)}\n"
        f"paraphrased: {sorted(sig_b)}"
    )


def test_paraphrased_innovation_claim_produces_equivalent_training_targets() -> None:
    """Paraphrasing the training-loss innovation claim must preserve training scope."""

    canonical = _canonical_summary()
    paraphrased = AuthorIntentSummary(
        project_goal=canonical.project_goal,
        method_goal=canonical.method_goal,
        implementation_scope=canonical.implementation_scope,
        method_mainline=canonical.method_mainline,
        story_order=canonical.story_order,
        priority_files=canonical.priority_files,
        module_roles=canonical.module_roles,
        pipeline_steps=canonical.pipeline_steps,
        design_intents=canonical.design_intents,
        innovation_claims=[
            # Same intent, different wording: training losses -> optimization objectives.
            "Three optimization objectives train the importance predictor.",
        ],
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(paraphrased).obligations
    )
    assert sig_a == sig_b, (
        "Paraphrasing the innovation claim must produce the same typed target signature.\n"
        f"canonical:   {sorted(sig_a)}\n"
        f"paraphrased: {sorted(sig_b)}"
    )


# ---------------------------------------------------------------------------
# Stage reorder invariance: same stages, different order
# ---------------------------------------------------------------------------


def test_reordered_pipeline_steps_produce_equivalent_targets() -> None:
    """Reordering pipeline_steps must not change the typed target signature.

    The signature collapses (kind, predicates, relations, conditions) without
    preserving order, so swapping two stages yields the same signature.  This
    is the R5.4 ``stage 重排`` exit condition.
    """

    canonical = _canonical_summary()
    reordered = AuthorIntentSummary(
        project_goal=canonical.project_goal,
        method_goal=canonical.method_goal,
        implementation_scope=canonical.implementation_scope,
        method_mainline=canonical.method_mainline,
        story_order=canonical.story_order,
        priority_files=canonical.priority_files,
        module_roles=canonical.module_roles,
        pipeline_steps=[
            # Swap the two stages.
            canonical.pipeline_steps[1],
            canonical.pipeline_steps[0],
        ],
        design_intents=canonical.design_intents,
        innovation_claims=canonical.innovation_claims,
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(reordered).obligations
    )
    assert sig_a == sig_b, (
        "Reordering pipeline_steps must produce the same typed target signature.\n"
        f"canonical:  {sorted(sig_a)}\n"
        f"reordered:  {sorted(sig_b)}"
    )


def test_reordered_story_order_produces_equivalent_targets() -> None:
    """Reordering story_order must not change the typed target signature."""

    canonical = _canonical_summary()
    reordered = AuthorIntentSummary(
        project_goal=canonical.project_goal,
        method_goal=canonical.method_goal,
        implementation_scope=canonical.implementation_scope,
        method_mainline=canonical.method_mainline,
        story_order=list(reversed(canonical.story_order)),
        priority_files=canonical.priority_files,
        module_roles=canonical.module_roles,
        pipeline_steps=canonical.pipeline_steps,
        design_intents=canonical.design_intents,
        innovation_claims=canonical.innovation_claims,
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(reordered).obligations
    )
    assert sig_a == sig_b, (
        "Reordering story_order must produce the same typed target signature.\n"
        f"canonical:  {sorted(sig_a)}\n"
        f"reordered:  {sorted(sig_b)}"
    )


# ---------------------------------------------------------------------------
# Negative control: different intent MUST produce different targets
# ---------------------------------------------------------------------------


def test_different_intent_produces_different_targets() -> None:
    """A genuinely different method must NOT produce the same signature.

    This is the negative control for the paraphrase tests: if two summaries
    express different behavior, their signatures must differ.
    """

    canonical = _canonical_summary()
    different = AuthorIntentSummary(
        project_goal="Train a graph neural network.",
        method_goal="Propagate messages and attend over neighbors.",
        implementation_scope="Training pipeline.",
        method_mainline=(
            "Propagate messages along edges and apply self-attention to aggregate "
            "neighbor features."
        ),
        story_order=["Message passing", "Attention"],
        priority_files=["gnn.py"],
        module_roles=["gnn.py::GNNLayer: propagate and attend"],
        pipeline_steps=[
            "Message passing: propagate features along edges",
            "Attention: attend over neighbor features",
        ],
        design_intents=["Stack layers for multi-hop aggregation."],
        innovation_claims=["A novel attention mechanism improves aggregation."],
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(different).obligations
    )
    assert sig_a != sig_b, (
        "Different methods must produce different typed target signatures.\n"
        f"canonical: {sorted(sig_a)}\n"
        f"different: {sorted(sig_b)}"
    )


# ---------------------------------------------------------------------------
# Synonym / hyphenation / inflection invariance
# ---------------------------------------------------------------------------


def test_synonym_variants_produce_equivalent_targets() -> None:
    """``top-k`` vs ``topk`` vs ``top k`` must produce the same signature."""

    canonical = AuthorIntentSummary(
        project_goal="Rank items.",
        method_goal="Select top-k items.",
        implementation_scope="Inference.",
        method_mainline="Sort items and select the top-k.",
        story_order=["Sort", "Select"],
        priority_files=["rank.py"],
        module_roles=["rank.py::ranker: sort and select"],
        pipeline_steps=[
            "Sort items by score.",
            "Select the top-k items.",
        ],
        design_intents=[],
        innovation_claims=[],
    )
    variant = AuthorIntentSummary(
        project_goal="Rank items.",
        method_goal="Select topk items.",
        implementation_scope="Inference.",
        method_mainline="Sort items and select the topk.",
        story_order=["Sort", "Select"],
        priority_files=["rank.py"],
        module_roles=["rank.py::ranker: sort and select"],
        pipeline_steps=[
            "Sort items by score.",
            "Select the topk items.",
        ],
        design_intents=[],
        innovation_claims=[],
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(canonical).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(variant).obligations
    )
    assert sig_a == sig_b, (
        "Hyphenation variants (top-k vs topk) must produce the same signature.\n"
        f"canonical: {sorted(sig_a)}\n"
        f"variant:   {sorted(sig_b)}"
    )


def test_inflection_variants_produce_equivalent_targets() -> None:
    """``sort`` vs ``sorts`` vs ``sorting`` must produce the same signature."""

    base = AuthorIntentSummary(
        project_goal="Rank primitives.",
        method_goal="Sort and prune.",
        implementation_scope="Inference.",
        method_mainline="Sort scores and prune.",
        story_order=["Sort", "Prune"],
        priority_files=["rank.py"],
        module_roles=["rank.py::ranker: sort and prune"],
        pipeline_steps=[
            "Sort scores.",
            "Prune low-ranked primitives.",
        ],
        design_intents=[],
        innovation_claims=[],
    )
    inflected = AuthorIntentSummary(
        project_goal="Rank primitives.",
        method_goal="Sort and prune.",
        implementation_scope="Inference.",
        method_mainline="Sorting scores and pruning.",
        story_order=["Sort", "Prune"],
        priority_files=["rank.py"],
        module_roles=["rank.py::ranker: sorts and prunes"],
        pipeline_steps=[
            "Sorting scores.",
            "Pruning low-ranked primitives.",
        ],
        design_intents=[],
        innovation_claims=[],
    )

    sig_a = typed_targets_signature(
        compile_intent_obligation_graph_v2(base).obligations
    )
    sig_b = typed_targets_signature(
        compile_intent_obligation_graph_v2(inflected).obligations
    )
    assert sig_a == sig_b, (
        "Inflection variants (sort/sorts/sorting) must produce the same signature.\n"
        f"base:      {sorted(sig_a)}\n"
        f"inflected: {sorted(sig_b)}"
    )
