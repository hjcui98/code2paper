"""WP3 §7.3：定向修复包必须是有界的，位置类失败必须升级为 plan revision。"""

from __future__ import annotations

from code2paper.agentic.writer_repair_packet import (
    build_writer_repair_packet,
    contract_failures_from_legacy_strings,
)

from . import incident_archive


def test_incident_missing_details_produce_bounded_repair_packet() -> None:
    """事故 attempt-2 的两个 detail witness 缺失 → 只改该段、只补这两项。"""

    acceptance = incident_archive.read_json("attempt_0002_acceptance")
    failures = contract_failures_from_legacy_strings(acceptance["failures"])
    packet = build_writer_repair_packet(
        paragraph_id="MA-S3:P1__f1",
        section_id="MA-S3",
        failures=failures,
        paragraph_markdown="The dedicated-attention encoder ...",
        accepted_paragraph_digests={
            "MA-S3:P1__f1": "sha256:failed",
            "MA-S3:P3": "sha256:accepted-3",
            "MA-S3:P4": "sha256:accepted-4",
        },
        authority_refs=("detail:mech_sym:f6cf5bdfe2ae16f0:15",),
    )

    assert packet.escalation == "repair_in_place"
    # 审计 §E.1：canonical code 是 detail_witness_missing（历史别名在读取边界转换）。
    assert packet.repair_kind == "detail_witness_missing"
    ids = {(item.kind, item.id) for item in packet.missing_targets}
    assert ("detail", "mech_sym:f6cf5bdfe2ae16f0:15") in ids
    assert ("detail", "mech_sym:f6cf5bdfe2ae16f0:76") in ids

    # 只允许改失败段落；其余已接受段落被冻结。
    assert packet.allowed_paragraph_ids == ("MA-S3:P1__f1",)
    assert packet.preserve_other_paragraphs is True
    assert set(packet.frozen_paragraph_digests) == {"MA-S3:P3", "MA-S3:P4"}
    assert "detail_witnesses" in packet.allowed_edits

    payload = packet.as_request_payload()
    assert "frozen_paragraph_digests" not in payload
    assert payload["missing_targets"][0]["id"].startswith(("mech_sym:", "detail:"))
    # 审计 §E.2：修复必需的局部内容必须留下，只有内部摘要被隐藏。
    assert payload["paragraph_markdown"] == "The dedicated-attention encoder ..."
    assert payload["authority_refs"] == ["detail:mech_sym:f6cf5bdfe2ae16f0:15"]
    assert payload["allowed_paragraph_ids"] == ["MA-S3:P1__f1"]
    assert payload["missing_targets"][0]["reason_code"] == "detail_witness_missing"
    assert payload["escalation"] == "repair_in_place"


def test_authority_violation_escalates_instead_of_patching_prose() -> None:
    """§7.3 末句：归属本来就不对时不能硬加一句话过门，必须先 plan revision。"""

    packet = build_writer_repair_packet(
        paragraph_id="MA-S3:P1__f1",
        failures=[
            {
                "code": "authority_surface_violation",
                "target_kind": "detail",
                "target_id": "mech_sym:x:76",
            }
        ],
    )
    assert packet.escalation == "replan_required"
    assert "plan revision" in packet.escalation_reason
    assert packet.allowed_edits == ()
    assert packet.allowed_paragraph_ids == ()


def test_out_of_scope_target_also_escalates() -> None:
    packet = build_writer_repair_packet(
        paragraph_id="MA-S3:P9",
        failures=[
            {
                "code": "target_out_of_scope",
                "target_kind": "detail",
                "target_id": "mech_sym:other:3",
            }
        ],
    )
    assert packet.escalation == "replan_required"
    assert packet.repair_kind == "target_out_of_scope"


def test_packet_digest_tracks_body_and_is_deterministic() -> None:
    common = dict(
        paragraph_id="MA-S3:P1",
        failures=[
            {"code": "missing_detail_witness", "target_kind": "detail", "target_id": "d:1"}
        ],
    )
    first = build_writer_repair_packet(paragraph_markdown="original", **common)
    second = build_writer_repair_packet(paragraph_markdown="original", **common)
    changed = build_writer_repair_packet(paragraph_markdown="edited", **common)
    assert first.content_digest == second.content_digest
    assert first.content_digest != changed.content_digest


def test_formula_closure_mismatch_goes_to_the_planner_not_prose() -> None:
    """§E.1：consumer/source closure 不一致属于 Planner/Formalizer/Compiler。"""

    packet = build_writer_repair_packet(
        paragraph_id="MA-S4:P2",
        failures=[
            {
                "code": "formula_consumer_mismatch",
                "target_kind": "formula",
                "target_id": "obligation:1",
            }
        ],
    )
    assert packet.escalation == "replan_required"
    assert packet.repair_kind == "formula_consumer_mismatch"
    assert packet.allowed_edits == ()
    assert "Planner" in packet.escalation_reason or "planner" in packet.escalation_reason


def test_missing_formula_placeholder_is_a_writer_repair_without_formula_edits() -> None:
    """占位符缺失但 consumer 正确：Writer 只补合法引用，不自行改公式。"""

    packet = build_writer_repair_packet(
        paragraph_id="MA-S4:P2",
        failures=[
            {
                "code": "formula_placeholder_missing",
                "target_kind": "formula",
                "target_id": "obligation:1",
            }
        ],
    )
    assert packet.escalation == "repair_in_place"
    assert packet.repair_kind == "formula_placeholder_missing"
    assert "formula_references" in packet.allowed_edits
    assert "detail_witnesses" not in packet.allowed_edits


def test_unknown_failure_code_is_a_typed_block() -> None:
    """§E.1：未知失败码不得降级成默认 prose edit。"""

    packet = build_writer_repair_packet(
        paragraph_id="MA-S4:P9",
        failures=[{"code": "something_nobody_registered"}],
    )
    assert packet.escalation == "typed_block"
    assert packet.repair_kind == "unknown_failure"
    assert packet.allowed_edits == ()
    assert packet.allowed_paragraph_ids == ()
    assert "typed block" in packet.escalation_reason


def test_ledger_corruption_outranks_other_failures() -> None:
    packet = build_writer_repair_packet(
        paragraph_id="MA-S4:P9",
        failures=[
            {"code": "detail_witness_missing", "target_kind": "detail", "target_id": "d:1"},
            {"code": "ledger_corrupt"},
        ],
    )
    assert packet.escalation == "typed_block"
    assert packet.repair_kind == "ledger_corrupt"


def test_escalating_failure_outranks_the_first_code() -> None:
    """§E.1：多个失败时不能只看 codes[0]，升级类优先。"""

    packet = build_writer_repair_packet(
        paragraph_id="MA-S3:P1",
        failures=[
            {"code": "detail_witness_missing", "target_kind": "detail", "target_id": "d:1"},
            {"code": "target_out_of_scope", "target_kind": "detail", "target_id": "d:9"},
        ],
    )
    assert packet.escalation == "replan_required"
    assert packet.repair_kind == "target_out_of_scope"


def test_canonical_action_selection_table() -> None:
    from code2paper.agentic.publication_transaction_contract import (
        canonical_failure_code,
        canonical_failure_owner,
        select_failure_action,
    )

    # 历史别名在读取边界转换，owner 查表不猜。
    assert canonical_failure_code("missing_detail_witness") == "detail_witness_missing"
    assert canonical_failure_owner("missing_paragraph") == "writer_content"
    assert canonical_failure_owner("weird") == "system"
    assert canonical_failure_owner("atom_witness_missing") == "binder"
    assert canonical_failure_owner("transport_failure") == "execution_owner"

    selection = select_failure_action(["detail_witness_missing"])
    assert (selection.owner, selection.action) == ("writer_content", "writer_content_repair")
    selection = select_failure_action(["input_material_missing", "detail_witness_missing"])
    assert selection.action == "research_then_recompile"
    assert selection.escalation == "replan_required"
    assert selection.codes == ("input_material_missing", "detail_witness_missing")

    # 空集合（没有可归因失败）也不允许默认改正文。
    empty = select_failure_action(())
    assert empty.escalation == "typed_block"
    assert empty.owner == "system"


# --------------------------------------------------------------------------- #
# §E.1 生产 blocked_reason → canonical 归属（读取边界）
# --------------------------------------------------------------------------- #


def test_production_blocked_reasons_map_to_canonical_owners() -> None:
    from code2paper.agentic.publication_transaction_contract import (
        canonical_failure_codes_from_blocked_reason,
        classify_blocked_reason,
    )

    cases = {
        # 段落事务 lane 是内容 lane：细码决定 retry 类型，缺省仍是内容补写。
        "publication_paragraph_transaction_failed:MA-S1:P1:invalid_count": (
            ("detail_semantic_mismatch",),
            "writer_content_repair",
        ),
        "publication_paragraph_transaction_failed:response_blocked:paragraph_transaction": (
            ("paragraph_missing",),
            "writer_content_repair",
        ),
        # 段落 lane 里的 formula closure 字符串 = 占位符缺失（Writer 补引用）。
        "publication_paragraph_transaction_failed:MA-S1:P1:formula_consumer_mismatch": (
            ("formula_placeholder_missing",),
            "writer_content_repair",
        ),
        # 段落 lane 里的重复 witness 是表示缺陷，不是跨段权限问题。
        "publication_paragraph_transaction_failed:MA-S1:P1:duplicate_witness:detail:d1": (
            ("witness_representation_invalid",),
            "writer_content_repair",
        ),
        "publication_section_binding_failed:formula_placeholder:MA-S1:P1": (
            ("formula_placeholder_missing",),
            "writer_content_repair",
        ),
        # 闭集外 id / 缺材料归 planner / research，不能原地补写。
        "publication_section_binding_failed:unknown_claims": (
            ("target_out_of_scope",),
            "replan_required",
        ),
        "publication_section_binding_failed:missing_writing_research_callback:a,b": (
            ("input_material_missing",),
            "research_then_recompile",
        ),
        # 表示层损伤归 execution owner：有界补发，不算内容 repair。
        "provider_stream_ended_before_complete_json": (
            ("representation_damage",),
            "representation_repair",
        ),
        # 未注册的 reason 一律 typed block。
        "publication_section_schema_failed:section_markdown_empty": (
            ("unknown_failure",),
            "typed_block",
        ),
        "": (("unknown_failure",), "typed_block"),
    }
    for reason, (codes, action) in cases.items():
        assert canonical_failure_codes_from_blocked_reason(reason) == codes, reason
        selection = classify_blocked_reason(reason)
        assert selection.action == action, reason
        assert selection.owner == (
            "system" if action == "typed_block" else selection.owner
        )


def test_writer_repairable_actions_are_exactly_the_two_bounded_lanes() -> None:
    from code2paper.agentic.publication_transaction_contract import (
        WRITER_REPAIRABLE_ACTIONS,
        classify_blocked_reason,
    )

    assert WRITER_REPAIRABLE_ACTIONS == {
        "writer_content_repair",
        "representation_repair",
    }
    assert (
        classify_blocked_reason("provider_stream_done_without_json_content").action
        in WRITER_REPAIRABLE_ACTIONS
    )
    assert (
        classify_blocked_reason("publication_section_binding_failed:unknown_claims").action
        not in WRITER_REPAIRABLE_ACTIONS
    )
