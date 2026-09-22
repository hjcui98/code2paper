"""PR E / §E.4：两阶段验收的负例矩阵——关系正确性不能被词汇重叠替代。

审计要求 `writer_content` 仍必须成立 detail/公式/正文义务（只是允许 Writer 不枚举
Binder-owned atom），`final_bound` 另验完整绑定与条件/极性/接口关系。这里用共享
assessor 收集审计点名的负例：

* 加了目标 ID 但没有相应正文；
* exact_text 不在段中；
* argmax 写成 argmin；
* 比较方向反转；
* 训练条件写成无条件推理行为；
* 维度/归一化轴错误；
* 两个相似 operation 串错来源。
"""

from __future__ import annotations

from code2paper.agentic.publication_transaction_contract import (
    _extremum_signature,
    assess_paragraph_transaction,
)

TARGET = "d:op"


def _plan(**target: object) -> dict:
    base = {
        "target_kind": "detail",
        "target_id": TARGET,
        "detail_id": TARGET,
        "required": True,
    }
    base.update(target)
    return {
        "paragraph_id": "P1",
        "required_detail_ids": (TARGET,),
        "witness_contract": {"targets": (base,)},
    }


def _tx(body: str, exact: str) -> dict:
    return {
        "paragraph_id": "P1",
        "paragraph_markdown": body,
        "rendered_detail_ids": [TARGET],
        "witnesses": [
            {"witness_kind": "detail", "target_id": TARGET, "exact_text": exact}
        ],
    }


def _assess(row: dict, transaction: dict):
    return assess_paragraph_transaction(
        transaction, plan_row=row, validation_stage="writer_content"
    )


def test_target_id_without_matching_prose_is_rejected() -> None:
    row = _plan(semantic_atom="loss computation over logits")
    assessment = _assess(
        row,
        _tx(
            "The encoder reads the configured input tensor.",
            "The encoder reads the configured input tensor.",
        ),
    )
    assert assessment.valid is False
    assert assessment.semantic_failures, "声明了 target 但没有对应正文必须被拒"


def test_exact_text_outside_the_paragraph_is_rejected() -> None:
    row = _plan(
        semantic_atom="loss computation over logits",
        exact_excerpts=("loss = compute_loss(logits, labels)",),
    )
    assessment = _assess(
        row,
        _tx(
            "The objective reduces the prediction error over all batches.",
            "loss = compute_loss(logits, labels)",
        ),
    )
    assert assessment.valid is False
    assert any(
        failure.code in {"exact_span_not_in_body", "detail_semantic_mismatch"}
        for failure in assessment.failures
    ), assessment.failures


def test_argmax_written_as_argmin_is_rejected() -> None:
    """§E.4 点名负例：动作词一致（都是 selects），只有极值方向被反转。"""

    row = _plan(
        semantic_atom="select the top scoring passage",
        required_polarity="argmax selects the highest score",
        exact_excerpts=("scores.argmax() selects the passage",),
    )
    flipped = _assess(
        row,
        _tx(
            "The method scores.argmin() selects the passage to keep.",
            "scores.argmin() selects the passage",
        ),
    )
    assert flipped.valid is False
    assert "condition_or_polarity_mismatch:detail:d:op" in flipped.semantic_failures

    # 正例仍然通过：同一个 argmax 关系。
    matching = _assess(
        row,
        _tx(
            "The method scores.argmax() selects the passage to keep.",
            "scores.argmax() selects the passage",
        ),
    )
    assert matching.valid is True, matching.failures


def test_comparison_direction_flip_is_rejected() -> None:
    row = _plan(
        semantic_atom="threshold comparison selects rows",
        required_polarity="comparison_gt_selects",
        exact_excerpts=("mask = scores > threshold",),
    )
    assessment = _assess(
        row,
        _tx("The rule mask = scores < threshold selects rows.", "mask = scores < threshold"),
    )
    assert assessment.valid is False
    assert "condition_or_polarity_mismatch:detail:d:op" in assessment.semantic_failures


def test_dropping_a_training_condition_is_rejected() -> None:
    row = _plan(
        semantic_atom="dropout applied during training",
        required_conditions=("only during training",),
        exact_excerpts=("x = dropout(x)",),
    )
    assessment = _assess(
        row,
        _tx("The implementation applies x = dropout(x) to every batch.", "x = dropout(x)"),
    )
    assert assessment.valid is False
    assert "condition_or_polarity_mismatch:detail:d:op" in assessment.semantic_failures


def test_wrong_normalization_axis_is_rejected() -> None:
    row = _plan(
        semantic_atom="normalize along the feature axis",
        exact_excerpts=("normalized = values / values.sum(dim=1, keepdim=True)",),
    )
    assessment = _assess(
        row,
        _tx(
            "The tensor is normalized = values / values.sum(dim=0, keepdim=True) before use.",
            "normalized = values / values.sum(dim=0, keepdim=True)",
        ),
    )
    assert assessment.valid is False


def test_two_similar_operations_may_not_swap_sources() -> None:
    row = _plan(
        semantic_atom="second reduction over the batch",
        source_anchor_ids=("operation:op_beta",),
        exact_excerpts=("total = batch.sum()",),
    )
    assessment = _assess(
        row,
        _tx("The code computes total = sequence.sum() over tokens.", "total = sequence.sum()"),
    )
    assert assessment.valid is False


def test_extremum_signature_has_no_lexical_false_positives() -> None:
    assert _extremum_signature("scores.argmax() keeps the best") == "max"
    assert _extremum_signature("arg min over the batch") == "min"
    assert _extremum_signature("keeps the lowest loss") == "min"
    assert _extremum_signature("top-k retrieval") == "max"
    assert _extremum_signature("ascending sort order") == "min"
    # 词内出现不算，方向同时出现时也不判定。
    assert _extremum_signature("administered minibatch normalization") == ""
    assert _extremum_signature("max minus min") == ""
    assert _extremum_signature("the encoder reads input") == ""
