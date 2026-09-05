from __future__ import annotations

import pytest
from code2paper.llm.section_writer import WriterSectionInput, _llm_visible_section_payload


def test_writer_v3_shared_context_projection_preserves_byte_identity() -> None:
    raw_payload_str = "{\"mechanism_id\": \"mech_loss\", \"details\": [{\"detail_id\": \"d:1\"}]}"
    section = WriterSectionInput(
        section_id="sec_1",
        heading="Loss Objective",
        prompt_payload={
            "section_id": "sec_1",
            "heading": "Loss Objective",
            "narrative_plan": {"section_id": "sec_1", "paragraphs": []},
            "shared_contexts": [raw_payload_str],
            "formula_packages": [{"package_id": "pkg:1"}],
            "authoring_packets_v2": [{"legacy": "should_be_bypassed"}],
        },
    )

    visible = _llm_visible_section_payload(section)
    assert visible["section_id"] == "sec_1"
    assert visible["heading"] == "Loss Objective"
    assert visible["narrative_plan"] == {"section_id": "sec_1", "paragraphs": []}
    # Exact byte identity preserved
    assert visible["shared_contexts"] == [raw_payload_str]
    assert visible["formula_packages"] == [{"package_id": "pkg:1"}]
    # authoring_packets_v2 completely excluded from visible payload
    assert "authoring_packets_v2" not in visible
