"""Bounded private L01 meter refuses false provenance and changed actual wire."""
import importlib.util
import copy
import json
from pathlib import Path

import pytest

from code2paper.agentic.digest import digest_bytes
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.qualification import network_namespace_identity

SOURCE=Path(__file__).resolve().parents[1]/'l01_worker.py'
spec=importlib.util.spec_from_file_location('l01_dev_worker',SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_nonthinking_profile_resolves_explicit_off_without_budget():
    profile=json.loads((SOURCE.parents[3]/'tests/live/profiles/qwen38_dsh_l01.json').read_text())
    assert module.reasoning_mode(profile)==('off',0)
    assert profile['provider_config']['providers']['openai']['toolChoice']=={
        'type':'function','function':{'name':'c2p_terminal'}}
    assert module.tokenizer_request({'messages':[],'tools':[],
        'chat_template_kwargs':{'enable_thinking':False}})['chat_template_kwargs']=={'enable_thinking':False}


@pytest.mark.parametrize('change', ['missing-off','implicit-off','numeric-false','residual-budget','wrong-mode'])
def test_nonthinking_mode_refuses_implicit_or_contradictory_profile(change):
    provider={'reasoning':'off','compat':{'thinkingFormat':'chat-template',
        'chatTemplateKwargs':{'enable_thinking':False}}}
    if change=='missing-off':del provider['reasoning']
    elif change=='implicit-off':del provider['compat']['chatTemplateKwargs']
    elif change=='numeric-false':provider['compat']['chatTemplateKwargs']['enable_thinking']=0
    elif change=='residual-budget':provider['thinkingBudgets']={'low':1024}
    else:provider['reasoning']='high'
    with pytest.raises(ProtocolError):
        module.reasoning_mode({'provider_config':{'providers':{'openai':provider}}})


def receipt(tmp_path,wire=b'{"model":"qwen38-27b-nvfp4"}'):
    path=tmp_path/'receipt.json'
    value={'schema_version':'L01TokenizerReceiptV1','origin':'vllm_tokenize_exact_messages_tools',
        'model':module.MODEL,'base_url':module.BASE_URL,'meter_version':module.METER,
        'wire_digest':digest_bytes(wire),'input_tokens':13}
    path.write_text(json.dumps(value))
    return path,value,wire


def test_original_meter_uses_bound_wire_and_positive_count(tmp_path):
    path,value,wire=receipt(tmp_path)
    assert module.bound_meter(path)(wire)==13
    with pytest.raises(ProtocolError,match='l01_tokenizer_binding_invalid'):
        module.bound_meter(path)(wire+b' ')


@pytest.mark.parametrize('key,bad', [('model','different-model'),('base_url','http://other'),
    ('meter_version','unbound'),('meter_version','vllm-exact-dsh-wire-receipt/1'),
    ('input_tokens',True),('input_tokens',0),('input_tokens',32769)])
def test_unbound_or_unsafe_meter_never_grants_fee_input(tmp_path,key,bad):
    path,value,wire=receipt(tmp_path);value[key]=bad;path.write_text(json.dumps(value))
    with pytest.raises(ProtocolError,match='l01_tokenizer_binding_invalid'):
        module.bound_meter(path)(wire)


def test_offline_placeholder_cannot_be_used_in_its_parent_namespace(tmp_path):
    path,value,wire=receipt(tmp_path)
    value.update(origin='isolated_offline_placeholder',input_tokens=(len(wire)+3)//4,
        parent_namespace=network_namespace_identity())
    path.write_text(json.dumps(value))
    with pytest.raises(ProtocolError,match='qualification_network_not_isolated'):
        module.bound_meter(path)(wire)


def test_missing_meter_origin_is_not_model_measurement(tmp_path):
    path,value,wire=receipt(tmp_path);value.pop('origin');path.write_text(json.dumps(value))
    with pytest.raises(ProtocolError,match='l01_tokenizer_origin_invalid'):
        module.bound_meter(path)(wire)


@pytest.mark.parametrize('effort,explicit,expected',[
    ('low',None,{'reasoning_effort':'low','enable_thinking':True}),
    ('none',None,{'reasoning_effort':'none','enable_thinking':False}),
    ('low',{'enable_thinking':False},{'reasoning_effort':'low','enable_thinking':False}),
    ('low',{'reasoning_effort':'xhigh','other':'kept'},
        {'reasoning_effort':'low','enable_thinking':True,'other':'kept'}),
    (None,{'enable_thinking':False},{'enable_thinking':False}),
    (None,None,None),
])
def test_tokenizer_preserves_wire_and_mirrors_chat_template_merge(effort,explicit,expected):
    body={'model':module.MODEL,'messages':[{'role':'user','content':'mechanism'}],
        'tools':[{'type':'function','function':{'name':'terminal','parameters':{'type':'object'}}}]}
    if effort is not None:body['reasoning_effort']=effort
    if explicit is not None:body['chat_template_kwargs']=explicit
    before=copy.deepcopy(body)
    request=module.tokenizer_request(body)
    assert request['messages']==before['messages'] and request['tools']==before['tools']
    assert request.get('chat_template_kwargs')==expected
    assert body==before


@pytest.mark.parametrize('result',[
    {'outcome':'blocked','reason':'scoped gap','recovery_action':'owner review'},
    {'outcome':'draft','draft':{}},
    {'outcome':'research_required','requests':[{'request_id':'request:gap','section_id':'section:one',
        'argument_unit_id':'unit:one','missing_rhetorical_move':'mechanism_overview',
        'exact_question':'Which operation supplies the output?',
        'required_authority_lane':'executable_hard'}]},
])
def test_native_object_guidance_preserves_original_branch_guards(result):
    from code2paper.integrations.dsh.writer_contract import WriterTaskResultV1,native_terminal_schema
    from code2paper.integrations.dsh.protocol import parse_model
    from code2paper.agentic.digest import canonical_json_bytes
    native,_=native_terminal_schema();shape=native['properties']['result']
    assert 'type' not in shape and shape['description']
    assert [branch['properties']['outcome']['const'] for branch in shape['oneOf']]==[
        'draft','research_required','blocked']
    assert all(branch['type']=='object' and branch['additionalProperties'] is False
        and 'outcome' in branch['required'] for branch in shape['oneOf'])
    value={'schema_version':'WriterTaskResultV1','result':result}
    parse_model(canonical_json_bytes(value),WriterTaskResultV1)
    for bad in [json.dumps(result),{**result,'extra':True},{**result,'outcome':'unknown'}]:
        with pytest.raises(ProtocolError):
            parse_model(canonical_json_bytes({**value,'result':bad}),WriterTaskResultV1)
