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


def test_no_callback_schema_forbids_invented_research_requests() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_writer_section(callback_required=False),
    )

    requests = schema["properties"]["new_research_requests"]
    assert requests["maxItems"] == 0
    assert "minItems" not in requests


def _concept_section(
    *,
    include_propositions: bool = False,
) -> WriterSectionInput:
    writer_view: dict = {
        "positive_concepts": [
            {
                "concept_key": "CK-A",
                "method_subject": "encoder",
                "operation": "embed",
            }
        ],
        "caveated_concepts": [],
    }
    if include_propositions:
        writer_view["positive_propositions"] = [
            {"proposition_id": "MP-1", "statement": "The encoder embeds events."}
        ]
    return WriterSectionInput(
        section_id="MA-S1",
        heading="Encoder",
        prompt_payload={
            "writer_view": writer_view,
            "binding_contract": {
                "allowed_concept_keys": ["CK-A", "CK-B"],
                "required_concept_keys": ["CK-A"],
                "allowed_proposition_ids": ["MP-1"] if include_propositions else [],
                "used_argument_unit_ids": ["MA-S1:unit"],
                "used_claim_ids": ["claim-a"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
            },
            "grounding_contract": {"callback_required": False},
        },
        publication_mode=True,
        argument_graph={
            "moves": [],
            "argument_unit_ids": ["MA-S1:unit"],
        },
    )


def test_concept_mode_schema_exposes_closed_concept_key_witness_fields() -> None:
    """WP2 witness fields must survive schema projection so guided decoding
    can emit rendered/deferred concept keys.  Concept-only sections must not
    keep unconstrained proposition-id arrays that accept formula obligation
    ids (Gate 6B DyG 003015: missing_required_concepts + unknown_deferred_propositions)."""
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_concept_section(),
    )

    assert schema is not None
    for field in ("rendered_concept_keys", "deferred_concept_keys"):
        assert schema["properties"][field]["items"]["enum"] == ["CK-A", "CK-B"]
        assert field in schema["required"]
    assert "heading_text" in schema["properties"]
    assert "deferred_proposition_ids" not in schema["properties"]
    assert "rendered_proposition_ids" not in schema["properties"]
    assert _find_empty_enums(schema) == []


def test_concept_and_proposition_mode_schema_keeps_both_closed_id_sets() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_concept_section(include_propositions=True),
    )

    assert schema is not None
    assert schema["properties"]["rendered_concept_keys"]["items"]["enum"] == ["CK-A", "CK-B"]
    assert schema["properties"]["deferred_proposition_ids"]["items"]["enum"] == ["MP-1"]
    assert "formula:equation:core" not in (
        schema["properties"]["deferred_proposition_ids"]["items"]["enum"]
    )


def _brief_section() -> WriterSectionInput:
    return WriterSectionInput(
        section_id="MA-S1",
        heading="Encoder",
        prompt_payload={
            "writer_view": {
                "positive_briefs": [
                    {
                        "brief_id": "brief:A",
                        "licensed_wording": "The encoder embeds events.",
                        "bound_claim_ids": ["claim-a"],
                    }
                ],
                "caveated_briefs": [
                    {
                        "brief_id": "brief:B",
                        "clause_id": "clause:B:0",
                        "text": "Inspired by cognitive theory.",
                        "required_caveat_kind": "author_intent",
                    }
                ],
            },
            "binding_contract": {
                "allowed_brief_ids": ["brief:A", "brief:B"],
                "required_brief_ids": ["brief:A"],
                "used_argument_unit_ids": ["MA-S1:unit"],
                "used_claim_ids": ["claim-a"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
            },
            "grounding_contract": {"callback_required": False},
        },
        publication_mode=True,
        argument_graph={
            "moves": [],
            "argument_unit_ids": ["MA-S1:unit"],
        },
    )


def test_brief_mode_callback_schema_forces_research_requests_without_unanchored_moves() -> None:
    """Brief-binding callbacks must force new_research_requests even when every
    required move is anchored but mechanism drafts are still empty."""
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Encoder",
        prompt_payload={
            "writer_view": {
                "positive_briefs": [
                    {
                        "brief_id": "brief:A",
                        "licensed_wording": "The encoder embeds events.",
                        "bound_claim_ids": ["claim-a"],
                    }
                ],
                "caveated_briefs": [],
            },
            "binding_contract": {
                "allowed_brief_ids": ["brief:A"],
                "required_brief_ids": ["brief:A"],
                "required_rhetorical_moves": ["mechanism_overview"],
                "used_argument_unit_ids": ["MA-S1:unit"],
                "used_claim_ids": ["claim-a"],
                "used_equation_ids": [],
                "used_configuration_ids": [],
                "completed_rhetorical_moves": ["mechanism_overview"],
            },
            "grounding_contract": {
                "callback_required": True,
                "unanchored_required_moves": [],
                "callback_request_prototypes": [
                    {
                        "request_id": "request:MA-S1:brief_slots",
                        "section_id": "MA-S1",
                        "argument_unit_id": "MA-S1:unit",
                        "missing_rhetorical_move": "mechanism_overview",
                        "exact_question": "Which evidence resolves the empty mechanism draft?",
                        "required_authority_lane": "executable_hard",
                        "status": "open",
                        "brief_binding": [
                            {
                                "brief_id": "brief:A",
                                "mechanism_draft_status": "empty",
                                "missing_parts": ["empty mechanism draft"],
                                "evidence_refs_used": ["claim:claim-a"],
                            }
                        ],
                        "target_brief_ids": ["brief:A"],
                        "target_clause_ids": [],
                        "missing_parts": ["empty mechanism draft"],
                        "evidence_refs_used": ["claim:claim-a"],
                    }
                ],
            },
        },
        publication_mode=True,
        argument_graph={
            "moves": [
                {
                    "move": "mechanism_overview",
                    "argument_unit_ids": ["MA-S1:unit"],
                    "required": True,
                }
            ],
            "argument_unit_ids": ["MA-S1:unit"],
        },
    )
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=section,
    )

    assert schema is not None
    assert "new_research_requests" in schema["required"]
    requests = schema["properties"]["new_research_requests"]
    assert requests["minItems"] == 1
    item = requests["items"]
    # These are private Harness sidecar bindings; the Writer is not required
    # to copy internal target IDs into its callback JSON.
    assert "target_brief_ids" not in item["required"]
    assert "target_clause_ids" not in item["required"]
    assert item["properties"]["target_brief_ids"]["minItems"] == 1
    assert item["properties"]["missing_rhetorical_move"]["enum"] == [
        "mechanism_overview"
    ]
    assert _find_empty_enums(schema) == []


def test_brief_mode_schema_exposes_closed_brief_id_witness_fields() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_brief_section(),
    )

    assert schema is not None
    for field in ("rendered_brief_ids", "deferred_brief_ids"):
        assert schema["properties"][field]["items"]["enum"] == ["brief:A", "brief:B"]
        assert field in schema["required"]
    assert "rendered_concept_keys" not in schema["properties"]
    assert _find_empty_enums(schema) == []


def _facet_section() -> WriterSectionInput:
    return WriterSectionInput(
        section_id="MA-S3",
        heading="State update",
        prompt_payload={
            "writer_view": {
                "positive_briefs": [],
                "caveated_briefs": [],
                "mechanism_authoring_packet": {
                    "facets": [
                        {
                            "facet_id": "facet:delta",
                            "exact_source_quote": "The interval controls the state update.",
                            "semantic_fields": {
                                "subject": "time interval",
                                "transformation": "controls the state update",
                            },
                            "required": True,
                        }
                    ],
                    "required_facet_ids": ["facet:delta"],
                    "facet_policies": [],
                },
            },
            "binding_contract": {
                "allowed_facet_ids": ["facet:delta"],
                "required_facet_ids": ["facet:delta"],
            },
            "grounding_contract": {"callback_required": False},
        },
        publication_mode=True,
        argument_graph={"moves": [], "argument_unit_ids": []},
    )


def test_facet_mode_schema_requires_closed_facet_witness_fields() -> None:
    schema = _closed_set_publication_schema(
        json_schema_for(PublicationMethodSectionOutputV1),
        section=_facet_section(),
    )

    assert schema is not None
    for field in ("rendered_from_facet_ids", "deferred_facet_ids"):
        assert schema["properties"][field]["items"]["enum"] == ["facet:delta"]
        assert field in schema["required"]
    assert schema["properties"]["rendered_from_facet_ids"]["minItems"] == 1
    assert _find_empty_enums(schema) == []


def test_missing_required_facet_is_completeness_warning_not_body_loss() -> None:
    from code2paper.llm.section_writer import (
        _hard_publication_binding_failures,
        _publication_contract_failures,
    )

    output = PublicationMethodSectionOutputV1(
        section_id="MA-S3",
        section_markdown="## State update\n\nThe state update uses the interval.",
    )
    failures = _publication_contract_failures(
        output,
        expected_section_id="MA-S3",
        contract={
            "allowed_facet_ids": ("facet:delta",),
            "required_facet_ids": ("facet:delta",),
        },
    )
    assert "missing_required_facets:facet:delta" in failures
    assert _hard_publication_binding_failures(failures) == []
