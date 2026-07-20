"""R5.4 multilingual tests for the V2 intent compiler.

R5.4 exit condition: ``同一意图的中文、英文、同义改写和 stage 重排必须形成
等价 behavior targets``.  This module verifies the *中文 vs 英文* half: an
author YAML written in Chinese must compile to the same typed behavior target
signature as the semantically equivalent English YAML.

The concept registry in ``intent_compiler_v2.py`` carries both English and
Chinese trigger terms for every concept, so ``训练损失`` and ``training loss``
both resolve to the ``training_objective`` concept with scope=``training``.
This test module enforces that parity.
"""

from __future__ import annotations

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.intent_compiler_v2 import (
    compile_intent_obligation_graph_v2,
    typed_targets_signature,
)


def _english_summary() -> AuthorIntentSummary:
    """A RAP-style summary written in English."""

    return AuthorIntentSummary(
        project_goal="Predict primitive importance without using paper text as evidence.",
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


def _chinese_summary() -> AuthorIntentSummary:
    """The semantically equivalent summary written in Chinese."""

    return AuthorIntentSummary(
        project_goal="在不使用论文文本作为证据的情况下预测基元重要性。",
        method_goal="对低重要性基元打分并剪枝。",
        implementation_scope="仅提供推理入口。",
        method_mainline=(
            "加载预测器，计算每个基元的重要性分数，并对低排名基元进行剪枝。"
        ),
        story_order=["特征构建", "分数预测", "剪枝"],
        priority_files=["prune_percent.py"],
        module_roles=[
            "utils/net_utils.py::PrunePredictor: 为每个基元预测一个重要性分数",
        ],
        pipeline_steps=[
            "特征构建：构建每个基元的描述子",
            "剪枝：对分数排序，构造掩码，并移除低排名基元",
        ],
        design_intents=["在受限推理函数中避免渲染。"],
        innovation_claims=["三个训练损失学习重要性预测器。"],
    )


# ---------------------------------------------------------------------------
# Full bilingual parity
# ---------------------------------------------------------------------------


def test_chinese_and_english_summaries_produce_equivalent_targets() -> None:
    """The full R5.4 multilingual exit condition."""

    en_graph = compile_intent_obligation_graph_v2(_english_summary())
    cn_graph = compile_intent_obligation_graph_v2(_chinese_summary())

    sig_en = typed_targets_signature(en_graph.obligations)
    sig_cn = typed_targets_signature(cn_graph.obligations)
    assert sig_en == sig_cn, (
        "Chinese and English summaries that express the same intent must "
        "produce the same typed target signature.\n"
        f"english:  {sorted(sig_en)}\n"
        f"chinese:  {sorted(sig_cn)}"
    )


# ---------------------------------------------------------------------------
# Per-concept bilingual parity
# ---------------------------------------------------------------------------


def test_training_language_parity() -> None:
    """``训练损失`` and ``training loss`` both produce training-scoped targets."""

    en = AuthorIntentSummary(
        project_goal="Train.",
        method_goal="Train with losses.",
        implementation_scope="Training.",
        method_mainline="Train a model with training losses.",
        story_order=["Train"],
        priority_files=["m.py"],
        module_roles=["m.py::M: train"],
        pipeline_steps=["Train with training losses."],
        design_intents=[],
        innovation_claims=["Three training losses learn the predictor."],
    )
    cn = AuthorIntentSummary(
        project_goal="训练。",
        method_goal="用损失训练。",
        implementation_scope="训练。",
        method_mainline="用训练损失训练模型。",
        story_order=["训练"],
        priority_files=["m.py"],
        module_roles=["m.py::M: 训练"],
        pipeline_steps=["用训练损失训练。"],
        design_intents=[],
        innovation_claims=["三个训练损失学习预测器。"],
    )

    sig_en = typed_targets_signature(compile_intent_obligation_graph_v2(en).obligations)
    sig_cn = typed_targets_signature(compile_intent_obligation_graph_v2(cn).obligations)
    assert sig_en == sig_cn, (
        "Training language must produce the same signature in EN and CN.\n"
        f"english:  {sorted(sig_en)}\n"
        f"chinese:  {sorted(sig_cn)}"
    )

    # Both must have at least one training-scoped target.
    training_targets_en = {
        t for t in sig_en if "training" in t[3]
    }
    training_targets_cn = {
        t for t in sig_cn if "training" in t[3]
    }
    assert training_targets_en, "English summary must produce at least one training target"
    assert training_targets_cn, "Chinese summary must produce at least one training target"
    assert training_targets_en == training_targets_cn


def test_inference_language_parity() -> None:
    """``推理`` and ``inference`` both produce inference-scoped targets."""

    en = AuthorIntentSummary(
        project_goal="Infer.",
        method_goal="Infer without gradients.",
        implementation_scope="Inference.",
        method_mainline="Infer scores at deployment without gradients.",
        story_order=["Infer"],
        priority_files=["m.py"],
        module_roles=["m.py::M: infer"],
        pipeline_steps=["Infer scores at deployment."],
        design_intents=[],
        innovation_claims=[],
    )
    cn = AuthorIntentSummary(
        project_goal="推理。",
        method_goal="无梯度推理。",
        implementation_scope="推理。",
        method_mainline="在部署时无梯度推理分数。",
        story_order=["推理"],
        priority_files=["m.py"],
        module_roles=["m.py::M: 推理"],
        pipeline_steps=["在部署时推理分数。"],
        design_intents=[],
        innovation_claims=[],
    )

    sig_en = typed_targets_signature(compile_intent_obligation_graph_v2(en).obligations)
    sig_cn = typed_targets_signature(compile_intent_obligation_graph_v2(cn).obligations)
    assert sig_en == sig_cn, (
        "Inference language must produce the same signature in EN and CN.\n"
        f"english:  {sorted(sig_en)}\n"
        f"chinese:  {sorted(sig_cn)}"
    )


def test_ranking_language_parity() -> None:
    """``排序`` and ``sort`` both produce ranking predicates."""

    en = AuthorIntentSummary(
        project_goal="Rank.",
        method_goal="Sort and select.",
        implementation_scope="Inference.",
        method_mainline="Sort scores and select top-k.",
        story_order=["Sort", "Select"],
        priority_files=["r.py"],
        module_roles=["r.py::R: sort and select"],
        pipeline_steps=["Sort scores.", "Select top-k."],
        design_intents=[],
        innovation_claims=[],
    )
    cn = AuthorIntentSummary(
        project_goal="排序。",
        method_goal="排序并选择。",
        implementation_scope="推理。",
        method_mainline="对分数排序并选择前k个。",
        story_order=["排序", "选择"],
        priority_files=["r.py"],
        module_roles=["r.py::R: 排序并选择"],
        pipeline_steps=["对分数排序。", "选择前k个。"],
        design_intents=[],
        innovation_claims=[],
    )

    sig_en = typed_targets_signature(compile_intent_obligation_graph_v2(en).obligations)
    sig_cn = typed_targets_signature(compile_intent_obligation_graph_v2(cn).obligations)
    assert sig_en == sig_cn, (
        "Ranking language must produce the same signature in EN and CN.\n"
        f"english:  {sorted(sig_en)}\n"
        f"chinese:  {sorted(sig_cn)}"
    )


# ---------------------------------------------------------------------------
# Mixed-language summary (author writes some fields in CN, some in EN)
# ---------------------------------------------------------------------------


def test_mixed_language_summary_matches_pure_english() -> None:
    """A summary mixing CN and EN fields must match the pure-EN equivalent."""

    en = _english_summary()
    mixed = AuthorIntentSummary(
        project_goal=en.project_goal,  # English
        method_goal="对低重要性基元打分并剪枝。",  # Chinese
        implementation_scope=en.implementation_scope,  # English
        method_mainline="加载预测器，计算每个基元分数，并剪枝低排名基元。",  # Chinese
        story_order=["Feature construction", "分数预测", "Pruning"],  # Mixed
        priority_files=en.priority_files,
        module_roles=[
            "utils/net_utils.py::PrunePredictor: 为每个基元预测一个重要性分数",  # Chinese
        ],
        pipeline_steps=[
            "Feature construction: build per-primitive descriptors",  # English
            "剪枝：对分数排序，构造掩码，并移除低排名基元",  # Chinese
        ],
        design_intents=["Avoid rendering in the scoped inference function."],  # English
        innovation_claims=["三个训练损失学习重要性预测器。"],  # Chinese
    )

    sig_en = typed_targets_signature(compile_intent_obligation_graph_v2(en).obligations)
    sig_mixed = typed_targets_signature(compile_intent_obligation_graph_v2(mixed).obligations)
    assert sig_en == sig_mixed, (
        "Mixed-language summary must produce the same signature as pure-EN.\n"
        f"english:  {sorted(sig_en)}\n"
        f"mixed:    {sorted(sig_mixed)}"
    )
