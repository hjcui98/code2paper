"""WP4：输出工作量估量与页契约联合评估（方案 §8.2、§8.6）。"""

from __future__ import annotations

from code2paper.agentic.writer_output_workload import (
    DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE,
    estimate_writer_output_workload,
    evaluate_page_contract,
    narrative_ordinal,
)

from . import incident_archive


def _paragraph(
    paragraph_id: str,
    *,
    reader_goal: str = "How does this setup work?",
    details: tuple[str, ...] = (),
    packages: tuple[str, ...] = (),
    targets: tuple[dict[str, object], ...] = (),
    surfaces: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    return {
        "paragraph_id": paragraph_id,
        "reader_goal": reader_goal,
        "required_detail_ids": list(details),
        "formula_package_ids": list(packages),
        "witness_contract": {"targets": list(targets)},
        "author_intent_surfaces": list(surfaces),
    }


def test_multi_paragraph_page_is_split_by_output_workload() -> None:
    """输入量很小但语义段落很多时，页必须因输出负担被拆（事故反向用例）。"""

    paragraphs = [
        _paragraph(f"MA-S3:P{index}") for index in range(1, 13)
    ]
    evaluation = evaluate_page_contract(
        paragraphs,
        input_tokens=2_000,          # 输入远低于页预算
        max_page_input_tokens=20_000,
        max_output_tokens=8_192,
        output_reserve_tokens=1_024,
    )
    assert evaluation.fits is False
    assert "semantic_paragraph_count_exceeds_candidate_limit" in evaluation.reasons
    assert evaluation.workload is not None
    assert evaluation.workload.semantic_paragraph_count == 12

    single = evaluate_page_contract(
        paragraphs[:2],
        input_tokens=2_000,
        max_page_input_tokens=20_000,
        max_output_tokens=8_192,
        output_reserve_tokens=1_024,
    )
    assert single.fits is True, single.reasons


def test_incident_page_shape_is_rejected_as_a_single_call() -> None:
    """事故页形状（16 段 + 7 个 allowed detail + atom witness）必须被判为不可行。"""

    request = incident_archive.read_json("attempt_0002_request")
    paragraphs = request["input_payload"]["narrative_plan"]["paragraphs"]
    details = request["input_payload"]["binding_contract"]["required_detail_ids"]

    evaluation = evaluate_page_contract(
        paragraphs,
        input_tokens=30_000,
        max_page_input_tokens=80_000,
        max_output_tokens=8_192,
        output_reserve_tokens=0,
    )
    assert evaluation.fits is False
    assert evaluation.workload is not None
    assert evaluation.workload.semantic_paragraph_count == len(paragraphs) == 16
    # 真实的必需 detail 义务被计入，Binder-owned atom 不计入 Writer 负担。
    assert evaluation.workload.required_detail_occurrences >= len(details)
    assert evaluation.workload.binder_owned_witness_count > 0


def test_binder_owned_atoms_do_not_count_as_writer_workload() -> None:
    atom_targets = (
        {"target_id": "atom:d:1", "target_kind": "atom", "required": True},
        {"target_id": "atom:d:2", "target_kind": "atom", "required": True},
    )
    detail_targets = (
        {"target_id": "detail:d:1", "target_kind": "detail", "required": True},
    )
    workload = estimate_writer_output_workload(
        [_paragraph("MA-S1:P1", details=("detail:d:1",), targets=atom_targets + detail_targets)]
    )
    assert workload.binder_owned_witness_count == 2
    assert workload.writer_owned_witness_count == 1


def test_atom_free_bridge_page_has_nonzero_output_workload() -> None:
    """合法无 atom 的组织/过渡页不是零成本，也不会被当作免费塞进第一页。"""

    workload = estimate_writer_output_workload(
        [
            _paragraph(
                "MA-S1:P1",
                reader_goal="Why does this architecture exist?",
                surfaces=(
                    {
                        "author_statement": "The design keeps retrieval cheap.",
                        "local_reader_goal": "Why this design?",
                    },
                ),
            )
        ]
    )
    assert workload.semantic_paragraph_count == 1
    assert workload.target_prose_tokens > 0
    assert workload.estimated_output_tokens > workload.safety_reserve_tokens


def test_unknown_output_budget_is_fail_closed() -> None:
    evaluation = evaluate_page_contract(
        [_paragraph("MA-S1:P1")],
        input_tokens=1_000,
        max_page_input_tokens=10_000,
        max_output_tokens=None,
    )
    assert evaluation.fits is False
    assert "output_budget_unknown" in evaluation.reasons

    relaxed = evaluate_page_contract(
        [_paragraph("MA-S1:P1")],
        input_tokens=1_000,
        max_page_input_tokens=10_000,
        max_output_tokens=None,
        require_output_budget=False,
    )
    assert relaxed.fits is True


def test_explicit_output_budget_can_reject_a_page() -> None:
    paragraphs = [
        _paragraph(f"MA-S1:P{index}", details=(f"detail:{index}",))
        for index in range(1, 5)
    ]
    evaluation = evaluate_page_contract(
        paragraphs,
        input_tokens=1_000,
        max_page_input_tokens=50_000,
        max_output_tokens=700,
        output_reserve_tokens=0,
    )
    assert evaluation.fits is False
    assert "estimated_output_exceeds_available_output_budget" in evaluation.reasons


def test_calibrated_profile_changes_estimate_and_confidence() -> None:
    paragraphs = [_paragraph("MA-S1:P1", details=("detail:1",))]
    uncalibrated = estimate_writer_output_workload(paragraphs)
    assert uncalibrated.confidence == "uncalibrated"
    assert "no_calibrated_profile" in uncalibrated.unknown_reasons

    calibrated = estimate_writer_output_workload(
        paragraphs,
        calibrated_profile={
            "per_paragraph_json_tokens": 200,
            "safety_reserve_tokens": 2_048,
        },
    )
    assert calibrated.confidence == "calibrated"
    assert calibrated.estimated_output_tokens > uncalibrated.estimated_output_tokens


def test_narrative_ordinal_orders_p2_before_p10() -> None:
    ids = ["MA-S3:P10", "MA-S3:P2", "MA-S3:P1", "MA-S3:P1__f2", "MA-S3:P1__f10"]
    assert sorted(ids, key=narrative_ordinal) == [
        "MA-S3:P1",
        "MA-S3:P1__f2",
        "MA-S3:P1__f10",
        "MA-S3:P2",
        "MA-S3:P10",
    ]
    assert DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE == 6


def test_occurrence_counting_keeps_shared_detail_obligations() -> None:
    """同一 detail 在两个段落承担不同义务时必须按 occurrence 计数（§8.4/I4）。"""

    workload = estimate_writer_output_workload(
        [
            _paragraph("MA-S1:P1", details=("detail:shared",)),
            _paragraph("MA-S1:P2", details=("detail:shared",)),
        ]
    )
    assert workload.required_detail_occurrences == 2


def test_page_paragraph_limit_knob_is_wired_and_overridable(monkeypatch) -> None:
    """WP4 §8.3：候选页接受点读得到语义段落上限，且可显式覆盖。"""

    from code2paper.agentic.unified_context_compiler import (
        _max_semantic_paragraphs_per_page,
    )

    monkeypatch.delenv("CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE", raising=False)
    assert _max_semantic_paragraphs_per_page() == DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE

    monkeypatch.setenv("CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE", "2")
    assert _max_semantic_paragraphs_per_page() == 2

    # 0 表示显式关闭该维度（只按输入预算），非法值回落到候选值。
    monkeypatch.setenv("CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE", "0")
    assert _max_semantic_paragraphs_per_page() == 0
    monkeypatch.setenv("CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE", "abc")
    assert _max_semantic_paragraphs_per_page() == DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE
