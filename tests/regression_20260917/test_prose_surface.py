"""WP3 §7.6：段落对象是唯一正文真源，section_markdown 只能是派生物。"""

from __future__ import annotations

import json

from code2paper.agentic.paragraph_prose_composer import (
    audit_prose_surface,
    compose_section_markdown,
    normalize_writer_section_payload,
)

from . import incident_archive


def _full_response() -> dict:
    """事故 attempt-2 的完整响应（含 section_markdown 与 16 个段落）。"""

    acceptance = incident_archive.read_json("attempt_0002_acceptance")
    return json.loads(acceptance["response_text"])


def test_incident_response_has_two_surfaces_and_paragraphs_win() -> None:
    response = _full_response()
    assert response.get("section_markdown")
    required = [row["paragraph_id"] for row in response["paragraphs"]]
    assert len(required) == 16

    audit = audit_prose_surface(response, required_paragraph_ids=required)
    assert audit.valid is True, audit.failures
    assert audit.paragraph_count == 16
    assert audit.section_markdown_present is True
    # 模型自带的那份只被当作派生物，不作为真源。
    assert audit.section_markdown_is_derivative_only is True
    assert audit.prose_source == "paragraph_objects"
    assert len(audit.paragraph_ids) == len(set(audit.paragraph_ids))

    normalized = normalize_writer_section_payload(
        response, required_paragraph_ids=required
    )
    assert normalized["prose_source"] == "paragraph_objects"
    assert normalized["section_markdown_derived"] is True
    assert normalized["prose_audit"]["valid"] is True


def test_derived_section_markdown_is_deterministic_and_ordered() -> None:
    response = _full_response()
    first = compose_section_markdown(response)
    second = compose_section_markdown(response)
    assert first == second

    unordered = {
        "paragraphs": [
            {"paragraph_id": "MA-S3:P10", "paragraph_markdown": "ten"},
            {"paragraph_id": "MA-S3:P2", "paragraph_markdown": "two"},
            {"paragraph_id": "MA-S3:P1", "paragraph_markdown": "one"},
        ]
    }
    composed = compose_section_markdown(unordered)
    assert composed.index("one") < composed.index("two") < composed.index("ten")


def test_missing_paragraphs_are_detected_locally() -> None:
    """事故第 1 次只写了 1 段：本地闭集校验必须报出 15 段缺失。"""

    fragment = json.loads(
        incident_archive.read_json("attempt_0002_response")["response_text"]
    )
    required = [row["paragraph_id"] for row in fragment["paragraphs"]]
    first_record = json.loads(
        incident_archive.incident_attempt_path(
            "attempt-0001.provider-response.json"
        ).read_text(encoding="utf-8")
    )
    first = json.loads(first_record["response_text"])

    audit = audit_prose_surface(first, required_paragraph_ids=required)
    assert audit.valid is False
    assert len(audit.missing_paragraph_ids) == 15
    assert any(item.startswith("paragraph_missing:") for item in audit.failures)


def test_duplicate_and_out_of_order_paragraphs_are_detected() -> None:
    payload = {
        "paragraphs": [
            {"paragraph_id": "MA-S3:P2", "paragraph_markdown": "two"},
            {"paragraph_id": "MA-S3:P2", "paragraph_markdown": "two again"},
            {"paragraph_id": "MA-S3:P1", "paragraph_markdown": "one"},
        ]
    }
    audit = audit_prose_surface(
        payload, required_paragraph_ids=["MA-S3:P1", "MA-S3:P2"]
    )
    assert audit.valid is False
    assert audit.duplicate_paragraph_ids == ("MA-S3:P2",)
    assert audit.order_matches_narrative_ordinal is False
    assert any(item.startswith("duplicate_paragraph:") for item in audit.failures)
    assert "paragraph_order_mismatch" in audit.failures


def test_unexpected_paragraph_ids_are_rejected() -> None:
    payload = {
        "paragraphs": [
            {"paragraph_id": "MA-S3:P1", "paragraph_markdown": "one"},
            {"paragraph_id": "MA-S9:P1", "paragraph_markdown": "other page"},
        ]
    }
    audit = audit_prose_surface(payload, required_paragraph_ids=["MA-S3:P1"])
    assert audit.valid is False
    assert audit.unexpected_paragraph_ids == ("MA-S9:P1",)
    assert any(item.startswith("target_out_of_scope:") for item in audit.failures)


def test_normalized_payload_drops_model_section_markdown() -> None:
    payload = {
        "section_id": "MA-S3",
        "heading_text": "Architecture",
        "section_markdown": "MODEL WRITTEN SECTION TEXT THAT MAY DRIFT",
        "paragraphs": [
            {"paragraph_id": "MA-S3:P1", "paragraph_markdown": "one"},
            {"paragraph_id": "MA-S3:P2", "paragraph_markdown": "two"},
        ],
    }
    normalized = normalize_writer_section_payload(
        payload, required_paragraph_ids=["MA-S3:P1", "MA-S3:P2"]
    )
    assert "MAY DRIFT" not in normalized["section_markdown"]
    assert normalized["section_markdown"].startswith("## Architecture")
    assert "one" in normalized["section_markdown"]
    assert normalized["section_markdown_derived"] is True
