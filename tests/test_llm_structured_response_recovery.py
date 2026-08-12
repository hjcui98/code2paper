from __future__ import annotations

import pytest

from code2paper.llm.response_schemas import (
    PublicationMethodSectionOutputV1,
    try_parse_structured_response,
    try_parse_structured_response_with_trace,
)


@pytest.mark.parametrize(
    ("response", "expected_operation"),
    [
        (
            '```json\n{"section_markdown":"Mechanism."}\n```',
            "strip_outer_markdown_fence",
        ),
        (
            '{"section_markdown":"Mechanism.",}',
            "remove_trailing_comma",
        ),
        (
            '{"section_markdown":"Mechanism.","used_claim_ids":[]',
            "close_unambiguous_container_suffix",
        ),
    ],
)
def test_representation_recovery_is_lossless_and_traced(
    response: str,
    expected_operation: str,
) -> None:
    parsed, trace, error = try_parse_structured_response_with_trace(
        response,
        PublicationMethodSectionOutputV1,
    )

    assert error == ""
    assert parsed is not None
    assert parsed.section_markdown == "Mechanism."
    assert trace.applied
    assert expected_operation in trace.operations
    assert trace.original_text_digest.startswith("sha256:")
    assert trace.parsed_payload_digest.startswith("sha256:")


def test_strict_json_has_a_trace_but_no_recovery_operation() -> None:
    parsed, trace, error = try_parse_structured_response_with_trace(
        '{"section_markdown":"Mechanism."}',
        PublicationMethodSectionOutputV1,
    )

    assert parsed is not None and error == ""
    assert not trace.applied
    assert trace.operations == ()


def test_deeply_nested_response_fails_closed_without_crashing() -> None:
    pathological = '{"section_markdown": ' + "[" * 20000 + '1' + "]" * 20000 + "}"

    parsed, error = try_parse_structured_response(
        pathological,
        PublicationMethodSectionOutputV1,
    )

    assert parsed is None
    assert error.startswith("schema_validation_failed:")
