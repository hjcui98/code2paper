"""Unknown native tool completion cannot authorize a registered terminal."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from code2paper.agentic.digest import digest_json
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.unknown_tool_completion import verify_unknown_tool_rejection
from tests.integrations.dsh.test_text_rejection_completion import Store


def fixture(name='"c2p_terminal"\n<parameter', arguments='{}'):
    store=Store();actual={'provider':'fixture','model':'fixture-model','maxTokens':40,'tools':[{'name':'c2p_terminal'}]}
    request=digest_json(actual);reserved=store.put({'actual_request_ref':store.put(actual)})
    raw={'schema_version':'DshRejectedUnknownToolCaptureV1','tool_call_id':'call:unknown',
         'name':name,'arguments':arguments}
    block={'type':'tool-call','id':raw['tool_call_id'],'name':raw['name'],'arguments':raw['arguments']}
    usage={'inputTokens':7,'outputTokens':9,'totalTokens':16}
    stream=[{'type':'chunk','chunk':{'type':'block-start','index':0,'blockType':'tool-call'}},
        {'type':'tool-call-chunks','index':0,'id':raw['tool_call_id'],'name':raw['name'],'args':['',arguments],'dt':[1]},
        {'type':'chunk','chunk':{'type':'block-end','index':0,'block':block}},
        {'type':'chunk','chunk':{'type':'usage','usage':usage}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'tool-calls'}}}]
    def row(seq,kind,data):return {'seq':seq,'type':kind,'data':data}
    events=[row(1,'turn/start',{'turn':1}),row(2,'step/start',{'turn':1,'step':1}),
        row(3,'request/header',{'header':{'config':{k:v for k,v in actual.items() if k!='tools'},'tools':actual['tools']}}),
        row(4,'request/context',{'provider':'fixture','model':'fixture-model'}),
        row(5,'assistant/message',{'turn':1,'step':1,'message':{'role':'assistant',
            'source':{'kind':'model','provider':'fixture','model':'fixture-model'},'content':[block]},'usage':usage,'stream':stream}),
        row(6,'tool/call',{'turn':1,'step':1,'callId':raw['tool_call_id'],'name':raw['name'],'arguments':raw['arguments']}),
        {**row(7,'tool/result',{'turn':1,'step':1,'message':{'role':'tool','source':{'kind':'tool','callId':raw['tool_call_id']},
            'toolCallId':raw['tool_call_id'],'isError':True,'content':[{'type':'text','text':f'Error: unknown tool "{raw["name"]}"'}]},
            'error':{'name':'ToolNotFoundError','code':'UNKNOWN_TOOL'}}),'sourceEventSeqs':[6]},
        row(8,'step/end',{'turn':1,'step':1}),row(9,'turn/end',{'turn':1,'reason':{'kind':'blocked'}})]
    session={'schema_version':'DshSessionCaptureV1','format_version':'SessionFileV4','session_id':'child:unknown','events':events}
    raw_ref=store.put(raw);session_ref=store.put(session)
    finish={'schema_version':'DshRejectedUnknownToolProviderQuiescenceV1',**store.scope.__dict__,
        'request_id':'request:unknown','request_digest':request,'session_id':'child:unknown',
        'source':'gated-adapter-natural-unknown-tool-exhaustion/1','finish_reason':'tool-calls',
        'raw_ref':raw_ref,'session_ref':session_ref}
    task={'captured_source':None,'receipt':None,'binding':{'child_id':'child:unknown','session_id':'child:unknown'}}
    def fact(kind,ref=None):return SimpleNamespace(kind=kind,invocation_id='request:unknown',request_digest=request,
        **store.scope.__dict__,evidence_ref=ref,usage_input_tokens=7,usage_output_tokens=9)
    evidence=store.put({'schema_version':'DshRejectedUnknownToolFinishObservationV1','request_digest':request,
        'finish_reason':'tool-calls','stream_complete':True,'raw_ref':raw_ref,'session_ref':session_ref})
    facts=[fact('reserve',reserved),fact('dispatch-recorded'),fact('adapter-attempt'),fact('usage'),
        fact('terminal',evidence),fact('settlement',evidence)]
    return store,task,finish,facts,session,raw,actual


@pytest.mark.parametrize('name,arguments',[('"c2p_terminal"\n<parameter','{}'),('other_function','not JSON'),(' c2p_terminal ','')])
def test_unknown_tool_completion_is_not_terminal_authority(name,arguments):
    store,task,finish,facts,*_=fixture(name,arguments)
    verify_unknown_tool_rejection(store,task,finish,facts)
    verify_unknown_tool_rejection(store,task,finish,facts[:4],require_settlement=False)
    assert task['receipt'] is None and task['captured_source'] is None


@pytest.mark.parametrize('damage',[
    'schema','source','request','session','epoch_bool','media','raw_scope','session_scope','capture','receipt','raw_name','raw_args',
    'seq','attempt','missing_end','wrong_end','wrong_model','wrong_cap','wrong_tools','offered_name',
    'second_call','call_name','call_id','call_args','result_code','result_error','result_source','result_call',
    'result_text','result_parent','wrong_step','wrong_turn','missing_delta','delta_id','delta_name','delta_args',
    'delta_index','delta_dt','duplicate_block','unfinished_block','block_args','block_id','block_name',
    'usage_missing','usage_duplicate','usage_wrong','usage_bool','usage_total','finish_missing','finish_duplicate',
    'finish_stop','finish_not_last','usage_before_end','settlement_missing','settlement_different',
])
def test_unknown_native_completion_damages_fail_closed(damage):
    store,task,finish,facts,session,raw,actual=fixture();e=session['events'];data=e[4]['data'];s=data['stream'];result=e[6]['data']
    if damage=='schema':finish['schema_version']='DshProviderQuiescenceV1'
    elif damage=='source':finish['source']='caller-normal-finish'
    elif damage=='request':finish['request_digest']='sha256:'+'0'*64
    elif damage=='session':finish['session_id']='other'
    elif damage=='epoch_bool':finish['task_epoch']=False
    elif damage=='media':finish['raw_ref']=store.put('{}','text/plain')
    elif damage=='raw_scope':finish['raw_ref']['task_id']='other'
    elif damage=='session_scope':finish['session_ref']['execution_id']='other'
    elif damage=='capture':task['captured_source']={'name':'c2p_terminal'}
    elif damage=='receipt':task['receipt']={'accepted':True}
    elif damage=='raw_name':raw['name']='c2p_terminal'
    elif damage=='raw_args':raw['arguments']='changed'
    elif damage=='seq':e[5]['seq']=e[4]['seq']
    elif damage=='attempt':e[4]['type']='assistant/attempt'
    elif damage=='missing_end':e.pop()
    elif damage=='wrong_end':e[-1]['data']['reason']={'kind':'completed'}
    elif damage=='wrong_model':data['message']['source']['model']='other'
    elif damage=='wrong_cap':e[2]['data']['header']['config']['maxTokens']=41
    elif damage=='wrong_tools':e[2]['data']['header']['tools']=[]
    elif damage=='offered_name':
        actual['tools'].append({'name':raw['name']})
        request=digest_json(actual);finish['request_digest']=request
        facts[0].evidence_ref=store.put({'actual_request_ref':store.put(actual)})
        for f in facts:f.request_digest=request
    elif damage=='second_call':e.insert(6,deepcopy(e[5]))
    elif damage=='call_name':e[5]['data']['name']='c2p_terminal'
    elif damage=='call_id':e[5]['data']['callId']='other'
    elif damage=='call_args':e[5]['data']['arguments']='changed'
    elif damage=='result_code':result['error']['code']='OTHER'
    elif damage=='result_error':result['message']['isError']=False
    elif damage=='result_source':result['message']['source']['kind']='caller'
    elif damage=='result_call':result['message']['toolCallId']='other'
    elif damage=='result_text':result['message']['content'][0]['text']='accepted'
    elif damage=='result_parent':e[6]['sourceEventSeqs']=[5]
    elif damage=='wrong_step':result['step']=False
    elif damage=='wrong_turn':result['turn']=2
    elif damage=='missing_delta':s.pop(1)
    elif damage=='delta_id':s[1]['id']='other'
    elif damage=='delta_name':s[1]['name']='c2p_terminal'
    elif damage=='delta_args':s[1]['args']=['wrong','{}']
    elif damage=='delta_index':s[1]['index']=1
    elif damage=='delta_dt':s[1]['dt']=[False]
    elif damage=='duplicate_block':s.insert(1,deepcopy(s[0]))
    elif damage=='unfinished_block':s.pop(2)
    elif damage=='block_args':s[2]['chunk']['block']['arguments']='wrong'
    elif damage=='block_id':s[2]['chunk']['block']['id']='other'
    elif damage=='block_name':s[2]['chunk']['block']['name']='c2p_terminal'
    elif damage=='usage_missing':s.pop(3)
    elif damage=='usage_duplicate':s.insert(3,deepcopy(s[3]))
    elif damage=='usage_wrong':s[3]['chunk']['usage']['inputTokens']=8
    elif damage=='usage_bool':s[3]['chunk']['usage']['inputTokens']=True
    elif damage=='usage_total':s[3]['chunk']['usage']['totalTokens']=99
    elif damage=='finish_missing':s.pop()
    elif damage=='finish_duplicate':s.append(deepcopy(s[-1]))
    elif damage=='finish_stop':s[-1]['chunk']['reason']={'kind':'stop'}
    elif damage=='finish_not_last':s.append({'type':'chunk','chunk':{'type':'usage','usage':data['usage']}})
    elif damage=='usage_before_end':s[2],s[3]=s[3],s[2]
    elif damage=='settlement_missing':facts.pop()
    elif damage=='settlement_different':facts[-1].evidence_ref=store.put({'wrong':True})
    structural=damage not in {'settlement_missing','settlement_different'}
    with pytest.raises(ProtocolError):verify_unknown_tool_rejection(store,task,finish,facts,require_settlement=not structural)
