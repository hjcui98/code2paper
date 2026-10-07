"""C02 shared parser/caller/response-unsettled checks. C00 admission is separate."""
import copy
import json
import socket
from pathlib import Path

import pytest

from code2paper.agentic.digest import digest_bytes
from code2paper.agentic.publication_method_writer import _settle_recorded_writer_attempt
from code2paper.agentic.unified_invocation_ledger import publish_provider_request,publish_provider_response
from code2paper.llm.client import LLMConfig,LLMProvider,LLMResponse
from code2paper.llm.section_writer import (
    WriterSectionInput,assess_publication_content_acceptance,build_publication_writer_request,
    parse_publication_writer_response,write_publication_method_by_sections,
)
from .fixtures import legacy_fixture_builder as b
from .fixtures.completed_formalizer_fixture import build_fixture


@pytest.fixture(autouse=True)
def no_network_or_python_llm(monkeypatch):
    def blocked(*args,**kwargs): raise AssertionError("no Python LLM/network in local prepare/settlement")
    monkeypatch.setattr(socket.socket,"connect",blocked)
    monkeypatch.setattr(socket.socket,"connect_ex",blocked)
    from code2paper.llm.client import LLMClient
    monkeypatch.setattr(LLMClient,"complete",blocked)
    monkeypatch.setenv("CODE2PAPER_LLM_WRITER_MAX_REPAIR_ROUNDS","0")


@pytest.fixture(scope="module")
def technical_material():
    material={};build_fixture(material_sink=material,require_atom_targets=True)
    assert material["formalizer"].accepted_packages and not material["formalizer"].task_failures
    return material


def mutation(raw,name):
    value=json.loads(raw)
    if name == "heading_only":
        value["paragraphs"][0]["paragraph_markdown"]="# Only a heading"
    elif name == "extra_paragraph":
        extra=copy.deepcopy(value["paragraphs"][0]);extra["paragraph_id"]="not-in-plan";value["paragraphs"].append(extra)
    elif name == "wrong_formula":
        value["paragraphs"][0]["paragraph_markdown"]=value["paragraphs"][0]["paragraph_markdown"].replace("[[FORMULA:","[[FORMULA:wrong:")
    elif name == "wrong_atom":
        value["paragraphs"][0]["witnesses"].append(dict(witness_kind="atom",target_id="atom:wrong",exact_excerpt="step for mech_rescale"))
    elif name == "missing_atom":
        value["paragraphs"][0]["paragraph_markdown"]="An unrelated mechanism is described here."
    elif name != "legal": raise ValueError(name)
    return json.dumps(value,ensure_ascii=False)


@pytest.mark.parametrize("case",["legal","heading_only","extra_paragraph","wrong_formula","wrong_atom","missing_atom"])
def test_shared_parser_and_real_unsettled_settlement(technical_material,tmp_path,case):
    m=technical_material;raw=mutation(m["writer_raw"],case)
    provider=LLMResponse(text=raw,response_hash=digest_bytes(raw.encode()),finish_reason="stop")
    parsed=parse_publication_writer_response(provider,request=m["request"],private_section=m["section"])
    accepted,metrics=assess_publication_content_acceptance(m["section"],parsed)
    accepted=accepted and not parsed.blocked_reason
    ledger=tmp_path/"artifacts/06_authoring/invocations";invocation=m["plan"].invocations[0].invocation_id
    config=LLMConfig(provider=LLMProvider.NONE,model="offline",max_output_tokens=4096,cache=False)
    publish_provider_request(ledger,invocation,1,m["request"],config)
    publish_provider_response(ledger,invocation,1,provider)
    result=_settle_recorded_writer_attempt(ledger_root=ledger,invocation_id=invocation,private_section=m["section"])
    assert result is not None and result[0] == accepted
    assert result[2] == parsed.text
    if parsed.metadata is not None:
        assert result[3].model_dump(mode="json") == parsed.metadata.model_dump(mode="json")
    assert bool(accepted) == (case == "legal")
    if case == "legal":
        assert metrics["required_atom_count"] == metrics["valid_atom_count"] == 1
        assert metrics["required_target_count"] > 0
    else:
        assert parsed.blocked_reason or metrics["failures"]


def test_old_caller_uses_same_decode_and_formula_splice(technical_material):
    m=technical_material;responses=[]
    config=LLMConfig(provider=LLMProvider.NONE,model="offline",max_output_tokens=4096,cache=False)
    def provider(_config,request):
        assert request.input_payload == m["request"].input_payload
        return LLMResponse(text=m["writer_raw"],response_hash=digest_bytes(m["writer_raw"].encode()),finish_reason="stop")
    result=write_publication_method_by_sections(config,[m["section"]],llm_caller=provider,
        response_attempt_sink=lambda section,response:responses.append(response))
    expected=parse_publication_writer_response(provider(config,m["request"]),request=m["request"],private_section=m["section"])
    assert result.outputs[0].model_dump(mode="json") == expected.metadata.model_dump(mode="json")
    assert result.aggregate.sections[0].text == expected.text
    assert responses and assess_publication_content_acceptance(m["section"],responses[0])[1] == assess_publication_content_acceptance(m["section"],expected)[1]


def test_author_header_without_atom_is_valid():
    archive,obligations=b._evidence_archive();plan=b._narrative_plan(archive)
    manifest,invocations,sections=b._writer_material(archive,obligations,plan,b._budget_envelope())
    section=next(s for s in sections if s.section_id == b.AUTHOR_NO_ATOM_SECTION_ID)
    request=build_publication_writer_request(section,system_prompt=section.system_prompt,schema_name=b.SCHEMA_NAME,
        response_json_schema=b.consumer_response_json_schema("writer",section_id=section.section_id))
    parsed=parse_publication_writer_response(b.offline_provider_response(section,request),request=request,private_section=section)
    accepted,metrics=assess_publication_content_acceptance(section,parsed)
    assert accepted and not parsed.blocked_reason and metrics["required_atom_count"] == 0


@pytest.mark.parametrize("case",["heading_only","extra_paragraph","wrong_formula","wrong_atom","missing_atom"])
def test_invalid_response_old_caller_metrics_and_failure_match_shared_owner(technical_material,case):
    m=technical_material;raw=mutation(m["writer_raw"],case);responses=[]
    config=LLMConfig(provider=LLMProvider.NONE,model="offline",max_output_tokens=4096,cache=False)
    def provider(_config,request):return LLMResponse(text=raw,response_hash=digest_bytes(raw.encode()),finish_reason="stop")
    write_publication_method_by_sections(config,[m["section"]],llm_caller=provider,
        response_attempt_sink=lambda section,response:responses.append(response))
    expected=parse_publication_writer_response(provider(config,m["request"]),request=m["request"],private_section=m["section"])
    assert responses
    assert responses[0].text == expected.text
    assert responses[0].blocked_reason == expected.blocked_reason
    assert assess_publication_content_acceptance(m["section"],responses[0])[1] == assess_publication_content_acceptance(m["section"],expected)[1]

# GC-2: all owner snapshots are checked at every preparation boundary.
from dataclasses import replace
from .stage03_support import local_test_facade,unit_projection
from .test_composition_identity import composition
from code2paper.integrations.dsh.protocol import ProtocolError


@pytest.mark.parametrize('changes',[{'content_revision':2},{'fence':1},{'snapshot_digest':digest_bytes(b'new')},
    {'content_revision':2,'fence':1,'snapshot_digest':digest_bytes(b'new')}])
def test_old_frozen_ref_rejected_before_projection(tmp_path,composition,changes):
    facade,_,_,frozen=local_test_facade(tmp_path,composition)
    facade.context=replace(facade.context,**changes)
    facade.current_state=lambda:(facade.context.content_revision,facade.context.fence,facade.context.snapshot_digest)
    def unavailable(_):raise AssertionError('stale input must not reach project')
    for operation in (lambda:facade.render_input(frozen,cap=4096),
                      lambda:facade.prepare(frozen,cap=4096,project=unavailable)):
        with pytest.raises(ProtocolError,match='frozen_revision_snapshot_or_fence_stale'):operation()


def test_prepare_rejects_state_change_during_projection(tmp_path,composition):
    facade,_,_,frozen=local_test_facade(tmp_path,composition)
    def project(input):
        projection=unit_projection(facade,input)
        facade.current_state=lambda:(2,0,facade.context.snapshot_digest)
        return projection
    with pytest.raises(ProtocolError,match='task_revision_or_fence_stale'):
        facade.prepare(frozen,cap=4096,project=project)


def test_cap_recompile_cannot_return_stale_frozen_input(tmp_path,composition):
    facade,_,_,frozen=local_test_facade(tmp_path,composition)
    def project(input):
        projection=unit_projection(facade,input)
        measure=facade.store.read_json(projection.measurement_ref)
        return unit_projection(facade,input,context_tokens=measure['measured_input_tokens']+512+1024)
    old=facade.store.read_json(frozen);old['fence']=9
    stale=facade.store.put_json(old)
    with pytest.raises(ProtocolError,match='frozen_revision_snapshot_or_fence_stale'):
        facade.prepare(frozen,cap=4096,project=project,recompile=lambda *_:stale)


def test_owner_refreeze_after_new_state_can_prepare(tmp_path,composition):
    facade,contract,material,_=local_test_facade(tmp_path,composition)
    facade.context=replace(facade.context,content_revision=2,fence=1,snapshot_digest=digest_bytes(b'fresh'))
    facade.current_state=lambda:(2,1,facade.context.snapshot_digest)
    # The owner freezes the actual complete material under the new state.
    frozen=facade.freeze_input(**{key:material[key] for key in ('section','page','narrative','manifest','plan','formalizer')},
        identity=contract.identity.model_dump(mode='json'),epoch_limits=contract.epoch_limits.model_dump(mode='json'))
    fresh=facade.prepare(frozen,cap=4096,project=lambda input:unit_projection(facade,input))
    assert fresh.expected_state_revision==2
    facade.check_contract_current(fresh)
