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
    formulas: tuple[str, ...] = (),
    placeholders: tuple[str, ...] = (),
    targets: tuple[dict[str, object], ...] = (),
    witnesses: tuple[dict[str, object], ...] = (),
    surfaces: tuple[dict[str, str], ...] = (),
) -> dict[str, object]:
    return {
        "paragraph_id": paragraph_id,
        "reader_goal": reader_goal,
        "required_detail_ids": list(details),
        "formula_package_ids": list(packages),
        "formula_obligation_ids": list(formulas),
        "formula_placeholder_ids": list(placeholders),
        "witness_contract": {"targets": [*targets, *witnesses]},
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
    """审计 §C.3：仅"非空字典"不算标定——profile 必须自证身份与方法。"""

    paragraphs = [_paragraph("MA-S1:P1", details=("detail:1",))]
    uncalibrated = estimate_writer_output_workload(paragraphs)
    assert uncalibrated.confidence == "uncalibrated"
    assert "no_calibrated_profile" in uncalibrated.unknown_reasons

    # 只给系数、不给身份与样本范围 → 仍是 uncalibrated，且如实报出缺了什么。
    bare = estimate_writer_output_workload(
        paragraphs,
        calibrated_profile={
            "per_paragraph_json_tokens": 200,
            "safety_reserve_tokens": 2_048,
        },
    )
    assert bare.confidence == "uncalibrated"
    assert any(
        reason.startswith("calibration_profile_incomplete:")
        for reason in bare.unknown_reasons
    )
    assert bare.estimated_output_tokens > uncalibrated.estimated_output_tokens

    calibrated = estimate_writer_output_workload(
        paragraphs,
        calibrated_profile={
            "per_paragraph_json_tokens": 200,
            "safety_reserve_tokens": 2_048,
            "model_identity": "qwen38-27b-nvfp4",
            "tokenizer_identity": "vllm-openai-chat-template-v1",
            "schema_or_prompt_identity": "unified_writer_page_v2/1.0",
            "sample_scope": "2026-09-17 incident archive, 24 writer requests",
            "method": "max successful paragraphs + provider token accounting",
        },
    )
    assert calibrated.confidence == "calibrated"
    # 字符代理估算器仍被如实标出（calibrated 只描述系数来源，不假装 tokenizer 精确）。
    assert "token_estimator_is_character_proxy" in calibrated.unknown_reasons
    assert not any(
        reason.startswith("calibration_profile_incomplete:")
        for reason in calibrated.unknown_reasons
    )
    assert calibrated.estimated_output_tokens == bare.estimated_output_tokens

    # 提供真实 tokenizer 估算器后，未标定原因应完全消失。
    exact = estimate_writer_output_workload(
        paragraphs,
        calibrated_profile={
            "model_identity": "qwen38-27b-nvfp4",
            "tokenizer_identity": "vllm-openai-chat-template-v1",
            "schema_or_prompt_identity": "unified_writer_page_v2/1.0",
            "sample_scope": "2026-09-17 incident archive, 24 writer requests",
            "method": "max successful paragraphs + provider token accounting",
        },
        token_estimator=lambda text: max(1, len(text) // 4),
    )
    assert exact.confidence == "calibrated"
    assert exact.unknown_reasons == ()


def test_writer_witness_occurrences_are_charged_to_the_estimate() -> None:
    """审计最小反例：段数/detail/goal 不变，只增加合法 witness → 估量必须增加。"""

    from code2paper.agentic.writer_output_workload import (
        estimate_writer_output_workload,
    )

    plain = [_paragraph("MA-S1:P1", details=("detail:1",))]
    with_witnesses = [_paragraph(
        "MA-S1:P1",
        details=("detail:1",),
        witnesses=(
            {"target_kind": "detail", "target_id": "detail:1", "exact_span": "encoder reads input"},
            {"target_kind": "detail", "target_id": "detail:2", "exact_span": "decoder writes output"},
        ),
    )]
    base = estimate_writer_output_workload(plain)
    charged = estimate_writer_output_workload(with_witnesses)

    assert charged.writer_owned_witness_count == 2
    assert charged.writer_witness_tokens > 0
    assert charged.estimated_output_tokens > base.estimated_output_tokens

    # Binder-owned atom 不计入 Writer 负担：同一页增加 atom witness 不改变估量。
    atoms_only = [_paragraph(
        "MA-S1:P1",
        details=("detail:1",),
        witnesses=(
            {"target_kind": "atom", "target_id": "atom:1", "required": True},
            {"target_kind": "atom", "target_id": "atom:2", "required": True},
        ),
    )]
    atom_estimate = estimate_writer_output_workload(atoms_only)
    assert atom_estimate.writer_owned_witness_count == 0
    assert atom_estimate.binder_owned_witness_count == 2
    assert atom_estimate.estimated_output_tokens == base.estimated_output_tokens


def test_formula_package_and_obligation_are_not_double_counted() -> None:
    """同一输出引用同时出现在 package 与 obligation 列表时只能计一次。"""

    from code2paper.agentic.writer_output_workload import (
        estimate_writer_output_workload,
    )

    shared = estimate_writer_output_workload(
        [_paragraph("MA-S1:P1", details=("detail:1",), packages=("pkg:1",), formulas=("pkg:1",))]
    )
    package_only = estimate_writer_output_workload(
        [_paragraph("MA-S1:P1", details=("detail:1",), packages=("pkg:1",))]
    )
    assert shared.formula_reference_tokens == package_only.formula_reference_tokens

    placeholders = estimate_writer_output_workload(
        [_paragraph("MA-S1:P1", details=("detail:1",), placeholders=("ph:1", "ph:2"))]
    )
    assert placeholders.formula_placeholder_count == 2
    assert placeholders.formula_placeholder_tokens > 0


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


def test_repage_budget_failure_code_distinguishes_revised_plan() -> None:
    """方案 §8.5：拆页后的预算不足必须可解释，且不掩盖普通超预算。"""

    from code2paper.agentic.unified_context_compiler import (
        _repage_budget_failure_code,
    )
    from code2paper.agentic.unified_context_models import (
        UNIFIED_INVOCATION_BUDGET_EXCEEDED,
        UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE,
    )

    assert _repage_budget_failure_code(1, exceeded=False) is None
    assert (
        _repage_budget_failure_code(1, exceeded=True)
        == UNIFIED_INVOCATION_BUDGET_EXCEEDED
    )
    # plan_revision > 1 表示这是分页/修订后的 plan：报"拆页后预算不足"。
    assert (
        _repage_budget_failure_code(2, exceeded=True)
        == UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE
    )
    assert _repage_budget_failure_code("bad", exceeded=True) == UNIFIED_INVOCATION_BUDGET_EXCEEDED


def test_repage_budget_insufficiency_blocks_without_truncating_obligations() -> None:
    """§C.05：重分页后**总预算不足**必须阻断（typed failure），且不得截尾义务。

    走真实准入评估器 `evaluate_unified_live_admission_v1`：同一个 manifest/plan，
    只把总输入预算压到不足以覆盖预留量，并对比 plan_revision=1 与 =2 的失败码。
    """

    from code2paper.agentic.unified_context_compiler import (
        build_consumer_invocation_plan_v1,
        build_consumer_workset_manifest_v2,
        evaluate_unified_live_admission_v1,
    )
    from code2paper.agentic.unified_context_models import (
        UNIFIED_INVOCATION_BUDGET_EXCEEDED,
        UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE,
    )
    from tests.test_agentic_unified_context_compiler import (
        _budget_envelope,
        _two_mechanism_fixture,
    )

    archive, obligations = _two_mechanism_fixture()
    envelope = _budget_envelope()
    manifest = build_consumer_workset_manifest_v2(
        archive,
        obligations,
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = build_consumer_invocation_plan_v1(
        manifest,
        envelope,
        phase="formalizer",
        profile_digest=envelope.profile_digest,
        model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=envelope.model_context_tokens,
    )
    assert plan.invocations, "夹具必须真的产生 invocation 计划"
    assert plan.reserved_input_tokens_by_role
    required_before = {
        page.page_id: tuple(page.atom_ids) for page in manifest.pages
    }

    # 把总输入预算压到低于预留总量 → 重分页后的计划装不下。
    reserved_total = sum(int(value) for value in plan.reserved_input_tokens_by_role.values())
    assert reserved_total > 0
    squeezed = envelope.model_copy(
        update={"max_total_input_tokens": max(1, reserved_total - 1)}
    )
    revised = plan.model_copy(update={"plan_revision": 2, "parent_plan_digest": plan.content_digest})

    admission = evaluate_unified_live_admission_v1(
        phase="formalizer",
        plan=revised,
        envelope=squeezed,
        archive=archive,
        manifest=manifest,
        run_digest="sha256:run",
        model_context_tokens=squeezed.model_context_tokens,
    )
    codes = [
        code
        for gate in admission.gates
        for code in gate.failure_codes
    ]
    assert any(
        code.startswith(UNIFIED_INVOCATION_BUDGET_EXCEEDED + ":total_input_tokens:")
        for code in codes
    ), codes
    assert any(
        code.startswith(
            UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE + ":total_input_tokens:"
        )
        for code in codes
    ), codes
    assert admission.status != "pass"

    # 不截尾：失败是"拒绝发送"，manifest 的义务集合原样保留。
    required_after = {
        page.page_id: tuple(page.atom_ids) for page in manifest.pages
    }
    assert required_after == required_before

    # 对照：同样的超预算在初次计划（revision=1）只报普通超预算，不冒充"拆页后不足"。
    first = evaluate_unified_live_admission_v1(
        phase="formalizer",
        plan=plan,
        envelope=squeezed,
        archive=archive,
        manifest=manifest,
        run_digest="sha256:run",
        model_context_tokens=squeezed.model_context_tokens,
    )
    first_codes = [
        code for gate in first.gates for code in gate.failure_codes
    ]
    assert not any(
        code.startswith(UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE)
        for code in first_codes
    ), first_codes
