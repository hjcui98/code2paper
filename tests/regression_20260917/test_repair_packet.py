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
    assert packet.repair_kind in {"missing_detail_witness", "detail_semantic_mismatch"}
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


def test_formula_failure_allows_only_formula_edits() -> None:
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
    assert packet.escalation == "repair_in_place"
    assert "formula_references" in packet.allowed_edits
    assert "detail_witnesses" not in packet.allowed_edits
