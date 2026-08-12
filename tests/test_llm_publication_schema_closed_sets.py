"""Publication section closed-set schema must never emit an empty enum (engine-fatal)."""

from __future__ import annotations

import json

from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1, json_schema_for
from code2paper.llm.section_writer import WriterSectionInput, _closed_set_publication_schema


def _writer_section(*, callback_required: bool) -> WriterSectionInput:
    return WriterSectionInput(
        section_id="MA-S1",
        heading="Encoder",
        prompt_payload={
            "binding_contract": {
                "used_argument_unit_ids": ["MA-S1:unit"],
                "used_claim_ids": ["claim-a"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
                "anchored_required_rhetorical_moves": ["mechanism_overview"],
            },
            "grounding_contract": {"callback_required": callback_required},
        },
        publication_mode=True,
        argument_graph={
            "moves": [],
            "argument_unit_ids": ["MA-S1:unit"],
        },
    )


def _find_empty_enums(schema: dict) -> list[str]:
    found: list[str] = []
    text = json.dumps(schema)
    import re

    for match in re.finditer(r'"enum"\s*:\s*\[\s*\]', text):
        found.append(text[max(0, match.start() - 60):match.end()])
    return found


def test_callback_required_schema_with_empty_closed_sets_has_no_empty_enum() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_writer_section(callback_required=True),
    )

    assert _find_empty_enums(schema) == []
    assert schema is not None
    for field in ("used_equation_ids", "used_configuration_ids"):
        assert schema["properties"][field]["items"] == {"type": "string"}
        assert "enum" not in schema["properties"][field]["items"]


def test_callback_required_schema_keeps_enums_for_nonempty_closed_sets() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_writer_section(callback_required=True),
    )

    assert schema["properties"]["used_claim_ids"]["items"]["enum"] == ["claim-a"]
    assert schema["properties"]["used_argument_unit_ids"]["items"]["enum"] == ["MA-S1:unit"]
    assert schema["properties"]["completed_rhetorical_moves"]["items"]["enum"] == [
        "mechanism_overview"
    ]


def test_non_callback_schema_keeps_enum_arrays_for_content_first_binding() -> None:
    """Content-first writer semantics: the prose call is never forced to
    complete every id/move.  Closed sets stay enum arrays (subsets always
    legal, unknown ids rejected); the const-string form is gone."""
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_writer_section(callback_required=False),
    )

    for field in (
        "used_argument_unit_ids",
        "used_claim_ids",
        "used_equation_ids",
        "used_configuration_ids",
        "completed_rhetorical_moves",
    ):
        assert schema["properties"][field]["type"] == "array"
        assert "const" not in schema["properties"][field]
    assert schema["properties"]["used_claim_ids"]["items"]["enum"] == ["claim-a"]
    assert schema["properties"]["completed_rhetorical_moves"]["items"]["enum"] == [
        "mechanism_overview"
    ]
