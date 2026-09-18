"""WP3：Writer/Binder witness 责任统一与两阶段验收（方案 §7、§12）。"""

from __future__ import annotations

from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
)

EXACT = "loss = compute_loss(logits, labels)"
BODY = f"The objective optimizes {EXACT} across all batches."


def _plan_row(atom_required: bool = True) -> dict[str, object]:
    return {
        "paragraph_id": "sec_1_p1",
        "required_detail_ids": ("d:loss",),
        "witness_atoms": [
            {
                "atom_id": "atom:loss",
                "detail_id": "d:loss",
                "semantic_anchor": "loss computation",
                "exact_excerpts": [EXACT],
                "required": atom_required,
            }
        ],
    }


def _tx(witnesses: list[dict[str, str]]) -> dict[str, object]:
    return {
        "paragraph_id": "sec_1_p1",
        "paragraph_markdown": BODY,
        "rendered_detail_ids": ["d:loss"],
        "witnesses": witnesses,
    }


def test_writer_stage_accepts_detail_witness_without_atom_enumeration() -> None:
    assessment = assess_paragraph_transaction(
        _tx([{"witness_kind": "detail", "target_id": "d:loss", "exact_text": EXACT}]),
        plan_row=_plan_row(),
        validation_stage="writer_content",
    )
    assert assessment.valid is True, assessment.failures
    assert assessment.validation_stage == "writer_content"
    assert assessment.failures == ()


def test_atom_declaration_does_not_complete_detail_for_writer() -> None:
    assessment = assess_paragraph_transaction(
        _tx([{"witness_kind": "atom", "target_id": "atom:loss", "exact_text": EXACT}]),
        plan_row=_plan_row(),
        validation_stage="writer_content",
    )
    assert assessment.valid is False
    codes = {(failure.code, failure.target_kind, failure.target_id) for failure in assessment.failures}
    assert ("detail_witness_missing", "detail", "d:loss") in codes, assessment.failures
    # 该失败由 Writer 修复，而不是被 Binder 的 atom 数量掩盖。
    assert all(
        failure.repairable_by == "writer_content"
        for failure in assessment.failures
        if failure.code == "detail_witness_missing"
    )


def test_final_bound_still_requires_atoms_or_complete_set() -> None:
    detail_only = assess_paragraph_transaction(
        _tx([{"witness_kind": "detail", "target_id": "d:loss", "exact_text": EXACT}]),
        plan_row=_plan_row(),
        validation_stage="final_bound",
    )
    assert detail_only.valid is False
    assert detail_only.missing_by_kind.get("detail") == ("d:loss",)

    complete = assess_paragraph_transaction(
        _tx([{"witness_kind": "atom", "target_id": "atom:loss", "exact_text": EXACT}]),
        plan_row=_plan_row(),
        validation_stage="final_bound",
    )
    assert complete.valid is True
    assert "d:loss" in complete.witnessed_by_kind.get("detail", ())


def test_exact_span_not_in_body_is_structured() -> None:
    assessment = assess_paragraph_transaction(
        _tx([
            {
                "witness_kind": "detail",
                "target_id": "d:loss",
                "exact_text": "this sentence is not in the paragraph",
            }
        ]),
        plan_row=_plan_row(),
        validation_stage="writer_content",
    )
    assert assessment.valid is False
    assert any(
        failure.code == "exact_span_not_in_body" for failure in assessment.failures
    ), assessment.failures


def test_unknown_stage_is_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="unknown validation_stage"):
        assess_paragraph_transaction(
            _tx([]), plan_row=_plan_row(), validation_stage="not_a_stage"
        )
