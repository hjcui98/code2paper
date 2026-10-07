"""Frozen Writer-owned targets constrain native emission, never prose truth."""
from copy import deepcopy
from dataclasses import asdict

import pytest

from code2paper.integrations.dsh.writer_contract import native_terminal_schema
from .fixtures.completed_formalizer_fixture import build_fixture


def request():
    values = {}
    build_fixture(material_sink=values, require_atom_targets=True, readable_atom_targets=True)
    return asdict(values["request"])


def paragraph_schema(native):
    draft, = [branch for branch in native["properties"]["result"]["oneOf"] if "draft" in branch["properties"]]
    return draft["properties"]["draft"]["properties"]["paragraphs"]["items"]


def test_native_cardinality_comes_from_writer_detail_not_binder_atom():
    value = request()
    before = deepcopy(value)
    native, _ = native_terminal_schema(value)
    paragraph = paragraph_schema(native)
    assert paragraph["properties"]["paragraph_id"]["const"] == "MA-L1_p1"
    assert paragraph["properties"]["witnesses"]["minItems"] == 1
    assert "atom:rescale" not in str(native)
    assert "return a * x" not in str(native)
    assert value == before


def test_native_cardinality_preserves_mixed_paragraph_scopes_and_optional_targets():
    value = request()
    rows = value["input_payload"]["narrative_plan"]["paragraphs"]
    first = rows[0]
    second = deepcopy(first)
    second["paragraph_id"] = "paragraph:other"
    second["required_detail_ids"] = []
    second["witness_contract"]["targets"][0]["render_policy"] = "optional"
    rows.append(second)
    third = deepcopy(first["witness_contract"]["targets"][0])
    third["target_id"] = "detail:another"
    first["witness_contract"]["targets"].append(third)
    native, _ = native_terminal_schema(value)
    one, two = paragraph_schema(native)["oneOf"]
    assert one["properties"]["witnesses"]["minItems"] == 2
    assert "minItems" not in two["properties"]["witnesses"]
    assert two["properties"]["paragraph_id"]["const"] == "paragraph:other"


@pytest.mark.parametrize("damage", ["duplicate", "blank"])
def test_native_cardinality_rejects_ambiguous_paragraph_scope(damage):
    value = request()
    rows = value["input_payload"]["narrative_plan"]["paragraphs"]
    if damage == "duplicate":
        rows.append(deepcopy(rows[0]))
    else:
        rows[0]["paragraph_id"] = ""
    with pytest.raises(ValueError, match="native_paragraph_scope_invalid"):
        native_terminal_schema(value)


def test_unscoped_legacy_schema_is_still_available_without_new_task_obligations():
    native, _ = native_terminal_schema()
    paragraph = paragraph_schema(native)
    assert "minItems" not in paragraph["properties"]["witnesses"]
    assert "const" not in paragraph["properties"]["paragraph_id"]


def test_native_cardinality_keeps_required_sidecar_when_visible_targets_are_empty():
    values = {}
    build_fixture(material_sink=values, require_atom_targets=True)
    value = asdict(values["request"])
    row = value["input_payload"]["narrative_plan"]["paragraphs"][0]
    assert row["required_detail_ids"] == ["d:rescale"]
    assert row["witness_contract"]["targets"] == []
    native, _ = native_terminal_schema(value)
    assert paragraph_schema(native)["properties"]["witnesses"]["minItems"] == 1


def test_native_cardinality_deduplicates_same_required_detail_in_both_contract_forms():
    value = request()
    row = value["input_payload"]["narrative_plan"]["paragraphs"][0]
    row["required_detail_ids"] *= 2
    native, _ = native_terminal_schema(value)
    assert paragraph_schema(native)["properties"]["witnesses"]["minItems"] == 1
