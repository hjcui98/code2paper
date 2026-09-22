"""审计 §13：A01–G06 全链测试矩阵的**可核对**覆盖映射。

每条矩阵行都指向仓库里真实存在的测试节点；本文件本身也是断言——映射不能悄悄腐烂
（行缺失、指向的函数被改名/删除都会失败）。矩阵行的"必须断言"原文见
`docs/Code2Paper_代码审计与修复执行方案_20260922.md` §13。
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: 矩阵行 → 证据测试节点（`相对路径::函数名`）。同一行可有多条证据。
MATRIX_EVIDENCE: dict[str, tuple[str, ...]] = {
    # A：运行身份与打开模式
    "A01": ("tests/regression_20260917/test_execution_identity.py::test_dirty_content_changes_same_status",),
    "A02": ("tests/regression_20260917/test_run_identity_content.py::test_target_dirty_content_change_invalidates_resume",),
    "A03": ("tests/regression_20260917/test_run_identity_content.py::test_same_target_content_in_another_path_has_same_content_identity",),
    "A04": ("tests/regression_20260917/test_run_identity_content.py::test_fork_authoring_can_resume_without_changing_birth_metadata",),
    "A05": ("tests/regression_20260917/test_run_identity_content.py::test_import_rejects_missing_or_mutated_dependency",),
    "A06": ("tests/regression_20260917/test_run_identity_content.py::test_missing_validator_source_blocks_before_provider_send",),
    "A07": ("tests/regression_20260917/test_run_identity_content.py::test_two_new_openers_cannot_both_admit_same_root",),
    "A08": ("tests/regression_20260917/test_run_identity_content.py::test_run_lease_released_on_success_and_exception",),
    # B：统一账本与恢复
    "B01": (
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_exhausted_content_budget_is_terminal",
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_two_real_failures_without_a_rejection_record_still_exhaust",
    ),
    "B02": ("tests/regression_20260917/test_ledger_recovery_matrix.py::test_two_presend_refusals_without_sends_are_not_exhausted",),
    "B03": (
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_request_without_completed_is_send_outcome_unknown",
        "tests/regression_20260922/test_crash_resume_boundaries.py::test_unknown_send_outcome_is_never_resent",
    ),
    "B04": (
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_response_without_completed_is_response_received_unsettled",
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_local_replay_settles_a_pending_validation",
        "tests/regression_20260922/test_crash_resume_boundaries.py::test_recorded_response_is_settled_without_a_second_call",
    ),
    "B05": ("tests/regression_20260917/test_ledger_recovery_matrix.py::test_completed_without_response_is_ledger_inconsistent",),
    "B06": ("tests/regression_20260917/test_ledger_recovery_matrix.py::test_corrupt_acceptance_is_ledger_corrupt",),
    "B07": ("tests/regression_20260917/test_ledger_recovery_matrix.py::test_acceptance_survives_residual_rejection_records",),
    "B08": (
        "tests/regression_20260917/test_transport_policy.py::test_retry_respects_run_call_budget",
        "tests/regression_20260917/test_transport_policy.py::test_send_outcome_unknown_preserves_reservation_and_never_retries",
        "tests/regression_20260917/test_ledger_recovery_matrix.py::test_unknown_send_outcome_keeps_its_reservation",
    ),
    # C：联合分页与最终请求
    "C01": (
        "tests/regression_20260917/test_page_contract_recheck.py::test_narrative_only_section_is_paged_by_the_candidate_contract",
        "tests/regression_20260917/test_output_feasibility.py::test_atom_free_bridge_page_has_nonzero_output_workload",
    ),
    "C02": (
        "tests/regression_20260917/test_page_contract_recheck.py::test_final_page_paragraph_set_is_checked_against_the_limit",
        "tests/regression_20260917/test_page_contract_recheck.py::test_page_payload_preserves_the_narrative_paragraph_order",
    ),
    "C03": ("tests/regression_20260917/test_output_feasibility.py::test_writer_witness_occurrences_are_charged_to_the_estimate",),
    "C04": (
        "tests/regression_20260917/test_output_feasibility.py::test_formula_package_and_obligation_are_not_double_counted",
        "tests/regression_20260917/test_page_contract_recheck.py::test_namespace_formula_package_is_spliced_not_crashed",
    ),
    "C05": ("tests/regression_20260917/test_output_feasibility.py::test_repage_budget_failure_code_distinguishes_revised_plan",),
    "C06": ("tests/regression_20260917/test_page_contract_recheck.py::test_adapter_appending_paragraphs_is_rejected",),
    "C07": ("tests/regression_20260917/test_page_contract_recheck.py::test_raising_the_output_cap_is_rejected",),
    # D：作者/实现语义保真
    "D01": ("tests/regression_20260917/test_authoring_unit_merge.py::test_merge_keeps_optional_details_and_obligations",),
    "D02": ("tests/regression_20260917/test_authoring_unit_merge.py::test_same_detail_id_with_different_content_is_a_conflict",),
    "D03": ("tests/regression_20260917/test_intent_writer_surface.py::test_reader_question_changes_the_intent_digest",),
    "D04": ("tests/regression_20260917/test_intent_writer_surface.py::test_paragraph_surface_digest_follows_the_rebuilt_surface",),
    "D05": ("tests/regression_20260917/test_intent_writer_surface.py::test_zero_overlap_is_organizational_fallback_only",),
    "D06": ("tests/regression_20260917/test_intent_writer_surface.py::test_zero_overlap_required_detail_becomes_a_typed_gap_but_keeps_coverage",),
    # E：失败分类、有界 repair、单正文
    "E01": ("tests/regression_20260917/test_repair_packet.py::test_incident_missing_details_produce_bounded_repair_packet",),
    "E02": ("tests/regression_20260917/test_repair_packet.py::test_formula_closure_mismatch_goes_to_the_planner_not_prose",),
    "E03": (
        "tests/regression_20260922/test_authoring_contract_closure.py::test_rejected_page_enters_one_bounded_repair_and_commits",
        "tests/regression_20260922/test_authoring_contract_closure.py::test_extra_paragraph_is_refused_and_never_published",
    ),
    "E04": (
        "tests/regression_20260917/test_witness_projection.py::test_final_bound_still_requires_atoms_or_complete_set",
        "tests/regression_20260917/test_witness_relation_matrix.py",
    ),
    "E05": (
        "tests/regression_20260917/test_prose_surface.py::test_incident_response_has_two_surfaces_and_paragraphs_win",
        "tests/regression_20260917/test_prose_surface.py::test_normalized_payload_drops_model_section_markdown",
    ),
    "E06": ("tests/regression_20260917/test_repair_packet.py::test_unknown_failure_code_is_a_typed_block",),
    # F：安全索引与阶段快照
    "F01": ("tests/regression_20260917/test_artifact_index.py::test_mutating_the_active_file_after_indexing_is_detected",),
    "F02": ("tests/regression_20260917/test_artifact_index.py::test_explicit_reference_with_zero_matches_does_not_fall_back",),
    "F03": (
        "tests/regression_20260917/test_artifact_index.py::test_unparsable_artifact_is_invalid_and_never_active",
        "tests/regression_20260917/test_artifact_index.py::test_unsupported_schema_version_is_invalid",
    ),
    "F04": (
        "tests/regression_20260917/test_artifact_registry.py::test_registered_new_generation_is_recognized_without_a_known_artifacts_row",
        "tests/regression_20260917/test_artifact_index.py::test_current_plan_generation_is_resolved_by_reference_digest",
    ),
    "F05": (
        "tests/regression_20260917/test_artifact_index.py::test_stage_snapshot_evidence_change_is_detected",
        "tests/regression_20260917/test_artifact_index.py::test_stage_snapshot_evidence_is_immutable_and_pointer_is_atomic",
    ),
    "F06": (
        "tests/regression_20260917/test_artifact_index.py::test_empty_artifact_is_judged_by_phase_and_required_units",
        "tests/regression_20260922/test_authoring_contract_closure.py::test_formalizer_phase_is_not_substituted_by_the_writer_manifest",
    ),
    # G：真正的写作链验收与质量对照
    "G01": ("tests/regression_20260922/test_authoring_contract_closure.py::test_first_legal_content_runs_the_real_composition_path",),
    "G02": ("tests/regression_20260922/test_authoring_contract_closure.py::test_rejected_page_enters_one_bounded_repair_and_commits",),
    "G03": (
        "tests/regression_20260922/test_crash_resume_boundaries.py::test_unknown_send_outcome_is_never_resent",
        "tests/regression_20260922/test_crash_resume_boundaries.py::test_writer_accepted_without_binder_reruns_only_the_binder",
    ),
    "G04": ("tests/regression_20260917/test_quality_comparison.py::test_empty_candidate_tokens_are_not_an_efficiency_gain",),
    "G05": ("tests/regression_20260917/test_quality_comparison.py::test_fewer_required_formulas_is_not_an_improvement",),
    "G06": (
        "tests/regression_20260917/test_quality_comparison.py::test_hiding_gaps_while_coverage_regresses_is_not_an_improvement",
        "tests/regression_20260917/test_quality_comparison.py::test_partial_evidence_and_unmeasured_dimensions_are_declared",
    ),
}

_EXPECTED_ROWS = tuple(
    f"{prefix}{index:02d}"
    for prefix, count in (("A", 8), ("B", 8), ("C", 7), ("D", 6), ("E", 6), ("F", 6), ("G", 6))
    for index in range(1, count + 1)
)


def test_every_matrix_row_is_mapped() -> None:
    assert set(MATRIX_EVIDENCE) == set(_EXPECTED_ROWS), (
        set(_EXPECTED_ROWS) ^ set(MATRIX_EVIDENCE)
    )


def test_every_mapped_evidence_exists() -> None:
    missing: list[str] = []
    for row, nodes in MATRIX_EVIDENCE.items():
        for node in nodes:
            path_text, _, name = node.partition("::")
            path = ROOT / path_text
            if not path.is_file():
                missing.append(f"{row}:{node}:file")
                continue
            if name and f"def {name}(" not in path.read_text(encoding="utf-8"):
                missing.append(f"{row}:{node}:function")
    assert not missing, missing


@pytest.mark.parametrize("row", _EXPECTED_ROWS)
def test_matrix_row_declares_what_it_asserts(row: str) -> None:
    """每条矩阵行都必须至少有一条证据，且证据不是同一个测试重复凑数。"""

    nodes = MATRIX_EVIDENCE[row]
    assert nodes, row
    assert len(set(nodes)) == len(nodes), row
