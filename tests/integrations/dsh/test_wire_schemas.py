"""C01 byte parsing and private contract identity, with exportable goldens."""
import copy
import json
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.integrations.dsh.protocol import ProtocolError, parse_model, strict_json_loads
from code2paper.integrations.dsh.writer_contract import (
    ArtifactRefV1, WriterTaskContractV1, WriterTaskResultV1, seal_contract, terminal_schema,
)


def contract_values():
    digest = digest_bytes(b"test-scoped fixture")
    ref = dict(schema_version="ArtifactRefV1", artifact_id=digest, execution_id="e1", task_id="t1",
               task_epoch=0, media_type="application/json", byte_length=19, bytes_digest=digest, semantic_digest=None)
    return dict(schema_version="WriterTaskContractV1", protocol_version="c2p-dsh/1",
                workflow_version="writer-single-request/1", accounting_version="c2p-dsh-task-loop-v1",
                storage_version="publication-generation/1", parser_version="publication-writer/1",
                execution_id="e1", workflow_id="w1", node_id="writer", task_id="t1", scope_id="作者／λ",
                task_epoch=0, expected_state_revision=2,
                **{name: copy.deepcopy(ref) for name in ("writer_request_ref", "private_input_ref", "formalizer_receipt_ref",
                    "narrative_ref", "manifest_ref", "plan_ref", "resolved_snapshot_ref", "dsh_wire_contract_ref")},
                read_set=[ref], author_surface_digest=digest, binding_contract_digest=digest, technical_bytes_digest=digest,
                identity={name: digest for name in ("engine_digest", "target_digest", "intent_digest", "claims_digest",
                    "profile_digest", "model_digest", "validator_digest", "composition_digest", "renderer_digest", "tokenizer_digest")},
                renderer_version="native-text/1", model="test-only", effective_options={"temperature":0.1,"thinking":None},
                terminal_schema_digest=digest_json(terminal_schema()), post_clamp_max_output_tokens=1024,
                epoch_limits=dict(max_model_requests=1,max_input_tokens=32768,max_output_tokens=2048,max_tool_calls=0,max_wall_seconds=60))


def golden_cases():
    contract = seal_contract(contract_values())
    blocked = {"schema_version":"WriterTaskResultV1", "result":{"outcome":"blocked","reason":"材料缺失","recovery_action":"重新准备 λ"}}
    draft = {"schema_version":"WriterTaskResultV1", "result":{"outcome":"draft","draft":{"section_id":"节一","section_markdown":"Unicode：λ / 😀"}}}
    cases = [{"name":"contract_unicode_null","model":"WriterTaskContractV1","raw":canonical_json_bytes(contract).decode(),"expected":"ok"},
             {"name":"blocked_unicode","model":"WriterTaskResultV1","raw":canonical_json_bytes(blocked).decode(),"expected":"ok"},
             {"name":"draft","model":"WriterTaskResultV1","raw":canonical_json_bytes(draft).decode(),"expected":"ok"}]
    for name, raw, code in [
        ("duplicate",'{"schema_version":"WriterTaskResultV1","schema_version":"WriterTaskResultV1"}',"duplicate_json_key"),
        ("nan",'{"x":NaN}',"non_finite_number"),("infinity",'{"x":1e999}',"non_finite_number"),
        ("unsafe_integer",'{"x":9007199254740992}',"integer_out_of_range"),
        ("surrogate",'{"x":"\\ud800"}',"invalid_unicode"),
        ("absent",'{"schema_version":"WriterTaskResultV1"}',"schema_invalid"),
        ("null",'{"schema_version":"WriterTaskResultV1","result":null}',"schema_invalid"),
        ("accepted",'{"schema_version":"WriterTaskResultV1","result":{"outcome":"accepted"}}',"schema_invalid"),
        ("extra",json.dumps({**blocked,"accepted":True}),"schema_invalid"),
        ("union",'{"schema_version":"WriterTaskResultV1","result":{"outcome":"blocked","draft":{}}}',"schema_invalid"),
    ]:
        cases.append(dict(name=name,model="WriterTaskResultV1",raw=raw,expected=code))
    research = {"schema_version":"WriterTaskResultV1","result":{"outcome":"research_required","requests":[{
        "request_id":"rq:1","section_id":"scope:1","argument_unit_id":"unit:1",
        "missing_rhetorical_move":"implementation_realization","exact_question":"Which branch applies?",
        "required_authority_lane":"executable_hard"}]}}
    cases.append(dict(name="research_required",model="WriterTaskResultV1",raw=canonical_json_bytes(research).decode(),expected="ok"))
    raw_contract=canonical_json_bytes(contract).decode()
    for name,raw in (("integral_float_counter",raw_contract.replace('"task_epoch":0','"task_epoch":0.0')),
                     ("integral_exponent_counter",raw_contract.replace('"task_epoch":0','"task_epoch":0e0')),
                     ("float_literal_request_limit",raw_contract.replace('"max_model_requests":1','"max_model_requests":1.0')),
                     ("bool_literal_request_limit",raw_contract.replace('"max_model_requests":1','"max_model_requests":true'))):
        cases.append(dict(name=name,model="WriterTaskContractV1",raw=raw,expected="schema_invalid"))
    whitespace = ["\t\n\v\f\r ", "\u0085", "\u00a0", "\u1680", "\u2000\u200a", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000"]
    strings = [("ascii", "ok", "ok"), ("cjk", "中文", "ok"), ("bom", "\ufeff", "ok"),
        ("control_001c", "\x1c", "ok"), ("nonbmp", "😀", "ok"), ("empty", "", "schema_invalid"),
        ("length_256", "😀" * 256, "ok"), ("length_257", "😀" * 257, "schema_invalid")]
    for i, text in enumerate(whitespace):
        strings.extend([(f"whitespace_{i}", text, "schema_invalid"), (f"whitespace_text_{i}", text + "字", "ok")])
    for name, text, code in strings:
        value = {"schema_version":"WriterTaskResultV1", "result":{"outcome":"blocked", "reason":text,"recovery_action":"new task"}}
        cases.append(dict(name="identifier_"+name,model="WriterTaskResultV1",raw=canonical_json_bytes(value).decode(),expected=code))
    return cases


@pytest.mark.parametrize("case",golden_cases(),ids=lambda c:c["name"])
def test_wire_cases(case):
    model = {"WriterTaskContractV1":WriterTaskContractV1,"WriterTaskResultV1":WriterTaskResultV1}[case["model"]]
    if case["expected"] == "ok":
        parsed = parse_model(case["raw"],model)
        assert digest_bytes(case["raw"].encode()) and digest_json(parsed)
    else:
        with pytest.raises(ProtocolError,match=case["expected"]):
            parse_model(case["raw"],model)


@pytest.mark.parametrize("field",["author_surface_digest","technical_bytes_digest","model","terminal_schema_digest","effective_options"])
def test_content_changes_identity(field):
    values = contract_values(); first = seal_contract(values)
    values[field] = {"temperature":0.2} if field == "effective_options" else ("other-model" if field == "model" else digest_bytes(b"changed"))
    assert seal_contract(values).task_digest != first.task_digest


def test_accounting_sequence_is_not_content_revision():
    contract = seal_contract(contract_values())
    # Accounting is carried independently; it cannot be slipped into the private content contract.
    changed = contract.model_dump(mode="json"); changed["accounting_sequence"] = 3
    with pytest.raises(ProtocolError,match="schema_invalid"):
        parse_model(canonical_json_bytes(changed),WriterTaskContractV1)
    assert contract.expected_state_revision == 2


def test_artifact_extra_path_scope_and_digest_rejected():
    ref = contract_values()["read_set"][0]
    with pytest.raises(ProtocolError):
        parse_model(canonical_json_bytes({**ref,"path":"/etc/passwd"}),ArtifactRefV1)
    values=contract_values(); values["plan_ref"]["task_id"]="another-task"
    with pytest.raises(ProtocolError): seal_contract(values)
    with pytest.raises(ProtocolError):
        parse_model(canonical_json_bytes({**ref,"artifact_id":digest_bytes(b"other")}),ArtifactRefV1)


def export_wire_package(root: Path):
    root.mkdir(parents=True,exist_ok=True)
    from code2paper.integrations.dsh.writer_contract import (WriterInputRefV1, WriterMeasurementV1,
        WriterWireEquivalenceV1, WriterWireProjectionV1, native_terminal_schema,
        IDENTIFIER_CHARACTER_RULE, IDENTIFIER_WHITESPACE_RANGES, IDENTIFIER_PATTERN)
    from code2paper.integrations.dsh.result_ingest import OutputEnvelopeV1
    for model in (WriterTaskContractV1, WriterTaskResultV1, ArtifactRefV1, WriterInputRefV1,
                  WriterMeasurementV1, WriterWireEquivalenceV1, WriterWireProjectionV1, OutputEnvelopeV1):
        (root/f"{model.__name__}.schema.json").write_bytes(canonical_json_bytes(model.model_json_schema())+b"\n")
    native, enforcement = native_terminal_schema()
    (root/"native-terminal.schema.json").write_bytes(canonical_json_bytes(native)+b"\n")
    (root/"native-terminal.enforcement.json").write_bytes(canonical_json_bytes(enforcement)+b"\n")
    (root/"character-rules.json").write_bytes(canonical_json_bytes({"schema_version":"WireCharacterRulesV1",
        "rule":IDENTIFIER_CHARACTER_RULE,"pattern":IDENTIFIER_PATTERN,
        "whitespace_ranges":IDENTIFIER_WHITESPACE_RANGES,"length_unit":"unicode-code-point"})+b"\n")
    cases=golden_cases()
    for case in cases:
        case["wire_digest"]=digest_bytes(case["raw"].encode())
        if case["expected"] == "ok": case["semantic_digest"]=digest_json(strict_json_loads(case["raw"]))
    (root/"goldens.json").write_bytes(canonical_json_bytes(cases)+b"\n")


def test_explicit_character_rule_preserves_entire_python_regex_domain():
    from typing import Annotated
    from pydantic import Field, TypeAdapter
    from code2paper.integrations.dsh.writer_contract import IDENTIFIER_PATTERN
    old=TypeAdapter(Annotated[str,Field(pattern=r"\S")])
    new=TypeAdapter(Annotated[str,Field(pattern=IDENTIFIER_PATTERN)])
    # Exhaustive scalar census: includes all controls, BOM and non-BMP codepoints.
    for cp in range(0x110000):
        if 0xd800 <= cp <= 0xdfff: continue
        outcomes=[]
        for adapter in (old,new):
            try: adapter.validate_python(chr(cp)); outcomes.append(True)
            except ValueError: outcomes.append(False)
        assert outcomes[0] == outcomes[1], hex(cp)


if __name__ == "__main__":
    import sys
    export_wire_package(Path(sys.argv[1]))
