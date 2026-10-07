"""Counterexamples to the private ordinary-text stop completion proof."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.integrations.dsh.artifacts import TaskScope
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.text_rejection_completion import verify_text_rejection
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1


class Store:
    scope=TaskScope('execution:text-fixture','task:writer',0)
    def __init__(self):self.values={}
    def put(self,value,media_type='application/json'):
        raw=canonical_json_bytes(value) if media_type=='application/json' else value.encode()
        digest=digest_bytes(raw)
        ref=ArtifactRefV1(schema_version='ArtifactRefV1',execution_id=self.scope.execution_id,
            task_id=self.scope.task_id,task_epoch=0,artifact_id=digest,bytes_digest=digest,byte_length=len(raw),
            media_type=media_type,semantic_digest=digest_json(value) if media_type=='application/json' else None)
        self.values[digest]=(raw,value)
        return ref.model_dump(mode='json')
    def read(self,ref):return self.values[ref.artifact_id][0]
    def read_json(self,ref):return self.values[ref.artifact_id][1]


def fixture():
    store=Store();actual={'provider':'fixture','model':'fixture-model','maxTokens':40,'tools':[]}
    request=digest_json(actual);actual_ref=store.put(actual)
    reserve_ref=store.put({'actual_request_ref':actual_ref})
    body='```json\n{"result":"ordinary Unicode 文🙂"}\n```'
    usage={'inputTokens':7,'outputTokens':9,'totalTokens':16}
    streams=[{'type':'chunk','chunk':{'type':'block-start','index':0,'blockType':'text'}},
        {'type':'text-chunks','index':0,'texts':[body[:10],body[10:]],'dt':[1]},
        {'type':'chunk','chunk':{'type':'block-end','index':0,'block':{'type':'text','text':body}}},
        {'type':'chunk','chunk':{'type':'usage','usage':usage}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'stop'}}}]
    def row(seq,kind,data):return {'seq':seq,'type':kind,'data':data}
    events=[row(1,'turn/start',{'turn':1}),row(2,'step/start',{'turn':1,'step':1}),
        row(3,'request/header',{'header':{'config':{k:v for k,v in actual.items() if k!='tools'},'tools':[]}}),
        row(4,'request/context',{'provider':'fixture','model':'fixture-model'}),
        row(5,'assistant/message',{'turn':1,'step':1,'message':{'role':'assistant','source':{'kind':'model','provider':'fixture','model':'fixture-model'},
            'content':[{'type':'text','text':body}]},'usage':usage,'stream':streams}),
        row(6,'step/end',{'turn':1,'step':1}),row(7,'turn/end',{'turn':1,'reason':{'kind':'completed'}})]
    session={'schema_version':'DshSessionCaptureV1','format_version':'SessionFileV4','session_id':'child:text','events':events}
    raw_ref=store.put(body,'text/plain');session_ref=store.put(session)
    finish={'schema_version':'DshRejectedTextProviderQuiescenceV1',**store.scope.__dict__,
        'request_id':'request:text','request_digest':request,'session_id':'child:text',
        'source':'gated-adapter-natural-text-exhaustion/1','finish_reason':'stop','raw_ref':raw_ref,'session_ref':session_ref}
    task={'captured_source':None,'receipt':None,'binding':{'child_id':'child:text','session_id':'child:text'}}
    def fact(kind,ref=None):return SimpleNamespace(kind=kind,invocation_id='request:text',request_digest=request,
        **store.scope.__dict__,evidence_ref=ref,usage_input_tokens=7,usage_output_tokens=9)
    evidence=store.put({'schema_version':'DshRejectedTextFinishObservationV1','request_digest':request,'finish_reason':'stop',
        'stream_complete':True,'raw_ref':raw_ref,'session_ref':session_ref})
    facts=[fact('reserve',reserve_ref),fact('dispatch-recorded'),fact('adapter-attempt'),fact('usage'),
           fact('terminal',evidence),fact('settlement',evidence)]
    return store,task,finish,facts,session


def test_text_is_only_completion_proof_not_a_tool_candidate():
    store,task,finish,facts,_=fixture()
    verify_text_rejection(store,task,finish,facts)
    verify_text_rejection(store,task,finish,facts[:4],require_settlement=False)
    assert task['receipt'] is None and task['captured_source'] is None


@pytest.mark.parametrize('damage',[
    'schema','source','request','session','task_epoch_bool','text_media','raw_bytes','captured_source','receipt',
    'seq_duplicate','missing_end','error_end','tool_call','attempt','wrong_model','wrong_cap','wrong_tools',
    'usage_missing','usage_duplicate','usage_wrong','usage_bool','usage_total','finish_missing','finish_duplicate',
    'finish_error','finish_not_last','unfinished_block','block_changed','duplicate_block','wrong_delta_index',
    'delta_after_end','delta_changed','wrong_dt','usage_before_block_end','settlement_missing','settlement_different',
])
def test_text_completion_proof_damages_fail_closed(damage):
    store,task,finish,facts,session=fixture();events=session['events'];data=events[4]['data'];stream=data['stream']
    if damage=='schema':finish['schema_version']='DshProviderQuiescenceV1'
    elif damage=='source':finish['source']='caller-says-idle'
    elif damage=='request':finish['request_digest']='sha256:'+'0'*64
    elif damage=='session':finish['session_id']='other'
    elif damage=='task_epoch_bool':finish['task_epoch']=False
    elif damage=='text_media':finish['raw_ref']=store.put('{}','application/octet-stream')
    elif damage=='raw_bytes':finish['raw_ref']=store.put('different','text/plain')
    elif damage=='captured_source':task['captured_source']={'source':'ordinary-text-as-tool'}
    elif damage=='receipt':task['receipt']={'domain_status':'accepted'}
    elif damage=='seq_duplicate':events[5]['seq']=events[4]['seq']
    elif damage=='missing_end':events.pop()
    elif damage=='error_end':events[-1]['data']['reason']={'kind':'error'}
    elif damage=='tool_call':events.insert(5,{'seq':5,'type':'tool/call','data':{}})
    elif damage=='attempt':events[4]['type']='assistant/attempt'
    elif damage=='wrong_model':events[3]['data']['model']='other'
    elif damage=='wrong_cap':events[2]['data']['header']['config']['maxTokens']=41
    elif damage=='wrong_tools':events[2]['data']['header']['tools']=[{'name':'other'}]
    elif damage=='usage_missing':stream.pop(3)
    elif damage=='usage_duplicate':stream.insert(3,deepcopy(stream[3]))
    elif damage=='usage_wrong':stream[3]['chunk']['usage']['inputTokens']=8
    elif damage=='usage_bool':stream[3]['chunk']['usage']['inputTokens']=True
    elif damage=='usage_total':stream[3]['chunk']['usage']['totalTokens']=99
    elif damage=='finish_missing':stream.pop()
    elif damage=='finish_duplicate':stream.append(deepcopy(stream[-1]))
    elif damage=='finish_error':stream[-1]['chunk']['reason']={'kind':'error'}
    elif damage=='finish_not_last':stream.append({'type':'chunk','chunk':{'type':'usage','usage':data['usage']}})
    elif damage=='unfinished_block':stream.pop(2)
    elif damage=='block_changed':stream[2]['chunk']['block']['text']='changed'
    elif damage=='duplicate_block':stream.insert(2,deepcopy(stream[2]))
    elif damage=='wrong_delta_index':stream[1]['index']=1
    elif damage=='delta_after_end':stream[1],stream[2]=stream[2],stream[1]
    elif damage=='delta_changed':stream[1]['texts'][0]='changed'
    elif damage=='wrong_dt':stream[1]['dt']=[True]
    elif damage=='usage_before_block_end':stream[2],stream[3]=stream[3],stream[2]
    elif damage=='settlement_missing':facts.pop()
    elif damage=='settlement_different':facts[-1].evidence_ref=store.put({'different':True})
    finish['session_ref']=store.put(session)
    with pytest.raises(ProtocolError):
        verify_text_rejection(store,task,finish,facts,require_settlement=damage.startswith('settlement_'))
