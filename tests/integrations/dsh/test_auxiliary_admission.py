"""Original Worker aux bindings/ledger; explicitly UNIT Session/wire observations."""
from copy import deepcopy
import pytest
from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
from code2paper.integrations.dsh.epoch_accounting import epoch_totals
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_composition_identity import composition
from .test_step_admission import owner, observe, reserve, finish, completion_ref

PROFILE=dict(extra_roles='compaction',max_compaction_calls=1,output_token_reserve_compaction=256,
    max_request_input_tokens_compaction=32768,scaffolding_token_reserve_compaction=512)


def issue(d,**changes):
    f=d['f'];view=d['child'].call('task.read',d['scope'])['result']
    parent={'schema_version':'DshSessionCaptureV1','session_id':view['binding']['session_id'],
        'format_version':'SessionFileV4','events':[{'seq':1,'type':'compaction/start','data':{'compactionId':'unit:compact'}}]}
    params={**d['scope'],'contract_ref':d['contract_ref'],'budget_ref':d['budget'].model_dump(mode='json'),
        'parent_session_ref':f.store.put_json(parent).model_dump(mode='json'),
        'input_ref':f.store.put_json({'messages':[{'role':'user','content':[{'type':'text','text':'UNIT input to summarize.'}]}]}).model_dump(mode='json'),
        'child_id':'unit:compaction-child','session_id':'unit:compaction-child','output_tokens':256,**changes}
    return d['child'].call('task.bind_auxiliary',params)


def measure(d,issued,sequence,damage=None):
    loop=deepcopy(d['loop']);wire=deepcopy(d['wire']);binding=issued['binding']
    loop.update(maxTokens=256,tools=[],messages=[loop['messages'][0],{'role':'user','content':[{'type':'text','text':binding['prompt_text']}]}])
    from code2paper.integrations.dsh.auxiliary_admission import COMPACTION_SYSTEM
    loop['messages'][0]={'role':'system','content':[{'type':'text','text':COMPACTION_SYSTEM}]}
    loop.pop('toolHistory',None)
    wire.update(max_tokens=256,messages=[wire['messages'][0],{'role':'user','content':binding['prompt_text']}]);wire.pop('tools',None);wire.pop('tool_choice',None)
    wire['messages'][0]={'role':'system','content':COMPACTION_SYSTEM}
    if damage=='input':loop['messages'][1]['content'][0]['text']='Unissued input.';wire['messages'][1]['content']='Unissued input.'
    if damage=='tools':loop['tools']=d['loop']['tools'];wire['tools']=d['wire']['tools']
    return d['child'].call('request.measure_auxiliary',{**d['scope'],'contract_ref':d['contract_ref'],
        'binding_ref':issued['binding_ref'],'sequence':sequence,'actual_request_ref':d['f'].store.put_json(loop).model_dump(mode='json'),
        'provider_wire_ref':d['f'].store.put_json(wire).model_dump(mode='json')})


def test_undeclared_auxiliary_role_cannot_obtain_a_send(owner):
    assert issue(owner)['error']['message']=='dsh_aux_role_undeclared'
    assert read_run_budget_state(owner['f'].store.root/'artifacts/06_authoring/invocations')['call_count']==0


@pytest.mark.parametrize('owner',[PROFILE],indirect=True)
def test_compaction_keeps_writer_binding_and_original_epoch_fees(owner):
    d=owner;before=d['child'].call('task.read',d['scope'])['result']['binding']
    first=reserve(d,observe(d)['result']['step_ref'])['result'];finish(d,first)
    issued=issue(d);assert 'result' in issued,issued
    step=measure(d,issued['result'],2);assert 'result' in step,step
    auxiliary=reserve(d,step['result']['step_ref']);assert 'result' in auxiliary,auxiliary
    finish(d,auxiliary['result'])
    assert d['child'].call('task.read',d['scope'])['result']['binding']==before
    third=reserve(d,observe(d,3)['result']['step_ref']);assert 'result' in third,third
    finish(d,third['result'])
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    assert epoch_totals(root,d['contract'])=={'model_requests':3,'input_tokens':300,'output_tokens':21,'pending_requests':0}
    assert read_run_budget_state(root)['call_count_by_role']['compaction']==1
    assert observe(d,4)['error']['message']=='dsh_epoch_request_budget_exceeded'


@pytest.mark.parametrize('owner',[PROFILE],indirect=True)
@pytest.mark.parametrize('damage',['input','tools','same-child','different-child','cap'])
def test_auxiliary_input_binding_tool_and_cap_damage_refuses(owner,damage):
    d=owner
    if damage=='same-child':
        binding=d['child'].call('task.read',d['scope'])['result']['binding']
        result=issue(d,**binding)
    elif damage=='cap':result=issue(d,output_tokens=257)
    else:
        issued=issue(d);assert 'result' in issued,issued
        if damage=='different-child':result=issue(d,child_id='other',session_id='other')
        else:result=measure(d,issued['result'],1,damage)
    assert 'error' in result,result
    assert read_run_budget_state(d['f'].store.root/'artifacts/06_authoring/invocations')['call_count']==0
