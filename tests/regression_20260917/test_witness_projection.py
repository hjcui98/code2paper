"""WP3：Writer/Binder witness 责任统一与两阶段验收（方案 §7、§12）。"""

from __future__ import annotations

from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
)
from code2paper.llm.section_writer import _compact_writer_witness_contract_for_llm

from . import incident_archive

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


def test_writer_view_drops_binder_owned_atoms() -> None:
    """方案 §7.1：atom 由 Binder 负责，不能同时是 Writer 的必填 witness。"""

    contract = {
        "schema_version": "1.0",
        "paragraph_id": "MA-S3:P1__f1",
        "rhetorical_goal": "step_sequence",
        "targets": [
            {"target_id": "detail:mech:15", "target_kind": "detail", "required": True},
            {"target_id": "detail:mech:76", "target_kind": "detail", "required": True},
            {"target_id": "atom:detail:mech:15:operation:x", "target_kind": "atom", "required": True},
            {"target_id": "atom:detail:mech:15:operand:x:0", "target_kind": "atom", "required": True},
        ],
    }
    compact = _compact_writer_witness_contract_for_llm(contract)

    assert [target["target_kind"] for target in compact["targets"]] == ["detail", "detail"]
    assert compact["binder_owned"] == {"owner": "binder", "target_count": 2}
    # canonical 合同不被改写：Binder 仍拿到完整 atom 集合。
    assert sum(
        1 for target in contract["targets"] if target["target_kind"] == "atom"
    ) == 2


def test_incident_request_atoms_are_not_writer_required() -> None:
    """事故请求里 P1__f1 同时暴露 detail 与必需 atom；修复后 Writer 只看到 detail。"""

    request = incident_archive.read_json("attempt_0002_request")
    paragraph = next(
        item
        for item in request["input_payload"]["narrative_plan"]["paragraphs"]
        if item["paragraph_id"] == "MA-S3:P1__f1"
    )
    # 事故请求里确实存在必需 atom target（冻结事实）。
    assert any(
        target.get("target_kind") == "atom" and target.get("required") is True
        for target in paragraph["witness_contract"]["targets"]
    )

    compact = _compact_writer_witness_contract_for_llm(paragraph["witness_contract"])
    assert compact["targets"], "detail 目标必须保留"
    assert all(target["target_kind"] == "detail" for target in compact["targets"])
    assert compact["binder_owned"]["target_count"] > 0
