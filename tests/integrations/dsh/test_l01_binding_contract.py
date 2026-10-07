"""L01 source-backed paragraph contracts through the original parser/assessor."""
import json
import socket
from pathlib import Path

import pytest

from code2paper.agentic.digest import digest_bytes
from code2paper.agentic.publication_transaction_contract import assess_paragraph_transaction
from code2paper.llm.client import LLMResponse
from code2paper.llm.section_writer import (
    assess_publication_content_acceptance,
    parse_publication_writer_response,
)
from .fixtures.completed_formalizer_fixture import build_fixture


@pytest.fixture
def material(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("L01 binding qualification performs no network/LLM call")
    monkeypatch.setattr(socket.socket, "connect", refused)
    from code2paper.llm.client import LLMClient
    monkeypatch.setattr(LLMClient, "complete", refused)
    values = {}
    build_fixture(material_sink=values, require_atom_targets=True, readable_atom_targets=True)
    return values


def test_closed_targets_keep_source_owner_and_verified_explanation(material):
    row = material["narrative"].sections[0].paragraphs[0]
    targets = row.witness_contract["targets"]
    details = {atom.payload["detail_id"]: atom.payload for atom in material["archive"].detail_atoms}
    package, = material["formalizer"].accepted_packages
    atom_targets = [target for target in targets if target["target_kind"] == "atom"]
    assert len(atom_targets) == 1
    for target in atom_targets:
        detail = details[target["detail_id"]]
        owned, = [atom for atom in detail["witness_atoms"] if atom["atom_id"] == target["target_id"]]
        assert target["allowed_exact_excerpts"] == list(owned["exact_excerpts"])
        assert target["detail_id"] in package.source_detail_ids
        assert set(owned["source_operation_ids"]).issubset(package.bound_operation_ids)
        assert target["semantic_atom"] == package.prose_explanation
        assert target["render_policy"] == "required"


def test_writer_projection_keeps_formalizer_semantics_and_binder_ownership(material):
    from code2paper.llm.section_writer import _llm_visible_section_payload
    from code2paper.agentic.digest import digest_json
    private_before = digest_json(material["section"].prompt_payload)
    visible = _llm_visible_section_payload(material["section"])
    contract = visible["narrative_plan"]["paragraphs"][0]["witness_contract"]
    canonical = material["narrative"].sections[0].paragraphs[0].witness_contract["targets"]
    assert len(contract["targets"]) == 1
    assert contract["binder_owned"] == {"owner": "binder", "target_count": 1}
    assert len(contract["semantic_requirements"]) == 1
    for projected in [*contract["targets"], *contract["semantic_requirements"]]:
        target, = [row for row in canonical if row["target_id"] == projected["target_id"]]
        assert projected["semantic_atom"] == target["semantic_atom"]
        assert projected["render_policy"] == target["render_policy"] == "required"
        assert "allowed_exact_excerpts" not in projected
        assert "allowed_anchor_ids" not in projected
    assert digest_json(material["section"].prompt_payload) == private_before


@pytest.mark.parametrize("clause,accepted", [
    ("The output y is the scalar a times the input x.", True),
    ("The output y equals a times x.", True),
    ("The output y equals x times a.", True),
    ("The transformation multiplies the input x by the scalar factor a, yielding the rescaled output y.", True),
    ("The operation multiplies the scalar a by the input x, producing the output y.", True),
    ("The transformation multiplies the input z by the scalar factor a, yielding the rescaled output y.", False),
    ("The transformation multiplies the input X by the scalar factor a, yielding the rescaled output y.", False),
    ("The transformation multiplies the input xs by the scalar factor a, yielding the rescaled output y.", False),
    ("The transformation multiplies the scalar x by the input a, yielding the rescaled output y.", False),
    ("The transformation multiplies the input x by the scalar factor a, yielding the rescaled output z.", False),
    ("The transformation multiplies the input x by the scalar factor a, yielding the rescaled output Y.", False),
    ("The transformation multiplies the input x by the scalar factor a times z, yielding the rescaled output y.", False),
    ("The transformation multiplies the input x by twice the scalar factor a, yielding the rescaled output y.", False),
    ("The transformation multiplies the input x by the scalar factor a, yielding the rescaled output y plus z.", False),
    ("The transformation does not multiply the input x by the scalar factor a, yielding the rescaled output y.", False),
    ("The transformation multiplies the input x by the scalar factor a, yielding the rescaled output y when x is positive.", False),
    # This wording omits the supplied scalar/input semantic anchor. A later
    # metadata Binder may handle it; single-request qualification stays closed.
    ("The output y is obtained by multiplying a and x.", False),
    ("The output y equals a plus x.", False),
    ("The output y equals a times z.", False),
    ("The output y equals a times z, with input x.", False),
    ("The output y equals a times x times z.", False),
    ("The output y equals a times x divided by z.", False),
    ("The output y equals a times x - z.", False),
    ("The output y equals a times x squared.", False),
    ("The output y equals twice a times x.", False),
    ("The output y equals a times x^2.", False),
    ("The output y equals a times X.", False),
    ("The output y equals a times xs.", False),
    ("The output y is not a times x.", False),
    ("The output y is obtained without multiplying a and x.", False),
    ("The output y equals a divided by x.", False),
    ("An unrelated operation is described.", False),
])
def test_original_parser_and_assessor_preserve_operation_and_both_operands(material, clause, accepted):
    value = json.loads(material["writer_raw"])
    row = value["paragraphs"][0]
    package, = material["section"].prompt_payload["formula_packages"]
    row["paragraph_markdown"] = (
        clause + " The transformation produces an output quantity using its input and scalar factor."
        + "\n\n[[FORMULA:" + package["package_id"] + "]]"
    )
    row["witnesses"] = [{"witness_kind": "detail", "target_id": "d:rescale", "exact_text": clause}]
    value["section_markdown"] = ""
    text = json.dumps(value)
    response = parse_publication_writer_response(
        LLMResponse(text=text, response_hash=digest_bytes(text.encode())),
        request=material["request"], private_section=material["section"],
    )
    actual, metrics = assess_publication_content_acceptance(material["section"], response)
    assert actual is accepted
    assert metrics["required_atom_count"] == 1
    if accepted:
        assert not response.blocked_reason and not metrics["failures"]
        assert metrics["valid_atom_count"] == 1
    else:
        assert response.blocked_reason or metrics["failures"]


def test_reader_semantics_cannot_remove_required_atoms():
    with pytest.raises(ValueError, match="full atom contract"):
        build_fixture(readable_atom_targets=True)


@pytest.mark.parametrize('replacement',[None,'$$ output = factor * input $$',
    'The formula package is {package_id}.','[[FORMULA:foreign-package]]'])
def test_formula_metadata_never_replaces_frozen_placeholder(material,replacement):
    value=json.loads(material['writer_raw'])
    package,=material['section'].prompt_payload['formula_packages']
    original='[[FORMULA:'+package['package_id']+']]'
    replacement='' if replacement is None else replacement.replace('{package_id}',package['package_id'])
    for row in value['paragraphs']:
        row['paragraph_markdown']=row['paragraph_markdown'].replace(original,replacement)
    value['section_markdown']=value['section_markdown'].replace(original,replacement)
    text=json.dumps(value)
    response=parse_publication_writer_response(LLMResponse(text=text,response_hash=digest_bytes(text.encode())),
        request=material['request'],private_section=material['section'])
    actual,metrics=assess_publication_content_acceptance(material['section'],response)
    assert not actual and (response.blocked_reason or metrics['failures'])


def test_prompt_has_one_explicit_outer_contract_without_rewriting_original_section():
    from code2paper.integrations.dsh.facade import TERMINAL_INSTRUCTION
    assert 'schema_version="WriterTaskResultV1"' in TERMINAL_INSTRUCTION
    assert 'apply only to result.draft' in TERMINAL_INSTRUCTION
    assert '[[FORMULA:<package_id>]]' in TERMINAL_INSTRUCTION


def test_native_writer_instruction_resolves_binder_scope_without_target_exemption(material):
    from code2paper.integrations.dsh.facade import TERMINAL_INSTRUCTION
    from code2paper.llm.section_writer import _llm_visible_section_payload
    visible = _llm_visible_section_payload(material["section"])
    assert visible["paragraph_transaction_required"] is True
    contract = visible["narrative_plan"]["paragraphs"][0]["witness_contract"]
    assert {row["target_kind"] for row in contract["targets"]} == {"detail"}
    assert contract["binder_owned"]["target_count"] == 1
    assert "Earlier instructions that the separate Binder supplies witnesses apply only to Binder-owned atom" in TERMINAL_INSTRUCTION
    assert "required Writer-owned detail" in TERMINAL_INSTRUCTION
    assert "frozen witness_contract.targets" in TERMINAL_INSTRUCTION
    assert "even when rendered_detail_ids is empty or omitted" in TERMINAL_INSTRUCTION
    assert "Do not invent Binder-owned atom witnesses" in TERMINAL_INSTRUCTION


@pytest.mark.parametrize('damage',['missing-version','wrong-version','string-result','extra-field','wrong-branch'])
def test_full_python_terminal_wrapper_stays_strict(damage):
    from code2paper.integrations.dsh.protocol import ProtocolError,parse_model
    from code2paper.integrations.dsh.writer_contract import WriterTaskResultV1
    value={'schema_version':'WriterTaskResultV1','result':{'outcome':'blocked','reason':'missing evidence','recovery_action':'owner review'}}
    if damage=='missing-version':value.pop('schema_version')
    elif damage=='wrong-version':value['schema_version']='different'
    elif damage=='string-result':value['result']=json.dumps(value['result'])
    elif damage=='extra-field':value['extra']='untrusted'
    else:value['result']['outcome']='accepted'
    with pytest.raises(ProtocolError):parse_model(json.dumps(value).encode(),WriterTaskResultV1)


def test_original_packet10_raw_is_immutable_schema_rejection():
    from code2paper.integrations.dsh.protocol import ProtocolError,parse_model
    from code2paper.integrations.dsh.writer_contract import WriterTaskResultV1
    raw=(Path(__file__).parent/'fixtures/packet10-rejected-terminal.json').read_bytes()
    assert digest_bytes(raw)=='sha256:335194b5e7ad149d022daada3110c35f15f0746ef26ed8a9d3e1667133c59c0c'
    with pytest.raises(ProtocolError,match='schema_invalid'):parse_model(raw,WriterTaskResultV1)


@pytest.mark.parametrize("left,right", [("amount", "gain"), ("signal", "scale_factor"), ("u", "v")])
@pytest.mark.parametrize("substitute", [False, True])
def test_product_gate_uses_each_closed_source_expression(left, right, substitute):
    clause = f"The output equals {left} times {'other_value' if substitute else right}."
    if substitute:
        clause += f" The input {right} is also mentioned."
    plan = {
        "paragraph_id": "paragraph:any", "required_detail_ids": ["detail:any"],
        "witness_contract": {"targets": [{
            "target_kind": "detail", "target_id": "detail:any",
            "semantic_atom": f"{left} times {right}", "paper_role": "operation",
            "allowed_exact_excerpts": [f"return {left} * {right}"],
        }]},
    }
    result = assess_paragraph_transaction({
        "paragraph_id": "paragraph:any", "paragraph_markdown": clause,
        "rendered_detail_ids": ["detail:any"],
        "witnesses": [{"witness_kind": "detail", "target_id": "detail:any", "exact_text": clause}],
    }, plan_row=plan)
    assert result.valid is (not substitute)


@pytest.mark.parametrize("left,right,result", [
    ("amount", "gain", "scaled_amount"), ("signal", "scale_factor", "scaled_signal"), ("u", "v", "w"),
])
@pytest.mark.parametrize("damage", [None, "input", "result", "roles", "extra", "ambiguous-result"])
def test_active_product_clause_binds_source_operands_roles_and_result(left, right, result, damage):
    clause = (f"The transformation multiplies the input {left} by the scalar factor {right}, "
              f"yielding the rescaled output {result}.")
    if damage == "input":
        clause = clause.replace(f"input {left}", "input other_value")
    elif damage == "result":
        clause = clause.replace(f"output {result}", "output other_result")
    elif damage == "roles":
        clause = clause.replace(f"input {left}", f"scalar {left}")
    elif damage == "extra":
        clause = clause.removesuffix(".") + " divided by divisor."
    semantic = f"The output {result} is the scalar {right} times the input {left}."
    if damage == "ambiguous-result":
        semantic += " The output other_result is also described."
    plan = {
        "paragraph_id": "paragraph:any", "required_detail_ids": ["detail:any"],
        "witness_contract": {"targets": [{
            "target_kind": "detail", "target_id": "detail:any", "semantic_atom": semantic,
            "paper_role": "operation", "allowed_exact_excerpts": [f"return {left} * {right}"],
        }]},
    }
    assessment = assess_paragraph_transaction({
        "paragraph_id": "paragraph:any", "paragraph_markdown": clause,
        "rendered_detail_ids": ["detail:any"],
        "witnesses": [{"witness_kind": "detail", "target_id": "detail:any", "exact_text": clause}],
    }, plan_row=plan)
    assert assessment.valid is (damage is None)


@pytest.mark.parametrize("damage", [None, "sibling-detail", "wrong-input", "wrong-result", "atom-disagrees", "detail-disagrees", "duplicate-text", "missing-witness"])
def test_binder_reuses_only_same_detail_validated_writer_clause(material, damage):
    from code2paper.agentic.publication_transaction_contract import bind_paragraph_witnesses
    clause = "The transformation multiplies the input x by the scalar factor a, yielding the rescaled output y"
    if damage == "wrong-input":
        clause = clause.replace("input x", "input z")
    elif damage == "wrong-result":
        clause = clause.replace("output y", "output z")
    plan = material["narrative"].sections[0].paragraphs[0].model_dump(mode="json")
    targets = plan["witness_contract"]["targets"]
    if damage in {"atom-disagrees", "detail-disagrees"}:
        for target in targets:
            if target["target_kind"] == ("atom" if damage == "atom-disagrees" else "detail"):
                target["allowed_exact_excerpts"] = ["return a * z"]
    tx = {
        "paragraph_id": plan["paragraph_id"],
        # The complete sentence intentionally extends beyond the supplied
        # complete arithmetic clause. No substring is invented by Binder.
        "paragraph_markdown": clause + ", as described by the accepted formula.",
        "rendered_detail_ids": ["d:rescale"],
        "witnesses": [{"witness_kind": "detail", "target_id": "detail:sibling" if damage == "sibling-detail" else "d:rescale", "exact_text": clause}],
    }
    if damage == "duplicate-text":
        tx["paragraph_markdown"] += " " + clause
    elif damage == "missing-witness":
        tx["witnesses"] = []
    before = json.dumps(tx, sort_keys=True)
    bound = bind_paragraph_witnesses(tx, plan_row=plan)
    atoms = [w for w in bound["witnesses"] if w["witness_kind"] == "atom"]
    assert bool(atoms) is (damage is None)
    if atoms:
        assert atoms[0]["exact_text"] == clause
    assert bound["paragraph_markdown"] == tx["paragraph_markdown"]
    assert json.dumps(tx, sort_keys=True) == before


def test_original_full_parser_binds_complete_clause_before_formula_reference(material):
    value = json.loads(material["writer_raw"])
    row = value["paragraphs"][0]
    package, = material["section"].prompt_payload["formula_packages"]
    clause = "The transformation multiplies the input x by the scalar factor a, yielding the rescaled output y"
    row["paragraph_markdown"] = (
        "The rescale mechanism applies a scalar factor to an input to produce a rescaled output. "
        + clause + ", as given by [[FORMULA:" + package["package_id"] + "]]. "
        + "In this expression, y denotes the rescaled output, a the scalar factor, and x the input."
    )
    row["witnesses"] = [{"witness_kind": "detail", "target_id": "d:rescale", "exact_text": clause}]
    value["section_markdown"] = ""
    raw = json.dumps(value)
    parsed = parse_publication_writer_response(
        LLMResponse(text=raw, response_hash=digest_bytes(raw.encode())),
        request=material["request"], private_section=material["section"],
    )
    accepted, metrics = assess_publication_content_acceptance(material["section"], parsed)
    assert accepted and not parsed.blocked_reason and not metrics["failures"]
    assert metrics["valid_atom_count"] == metrics["required_atom_count"] == 1
    assert metrics["formula_exact_body_count"] == metrics["formula_consumed_count"] == 1
