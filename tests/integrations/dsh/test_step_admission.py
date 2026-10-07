"""Real Worker and original V2 reserve/fee journal. Wire is a UNIT observer.

Actual SDK dynamic rendering/loop evidence is separately required for Gate-M.
"""
from copy import deepcopy

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events,read_run_budget_state
from code2paper.integrations.dsh.epoch_accounting import epoch_totals
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_composition_identity import composition
from .test_multistep_accounting import LIMITS
from .stage04_support import durable_material,start_worker,prepare_and_claim


@pytest.fixture
def owner(tmp_path,composition,request):
    composition.effective_config['options']['provider']='openai'
    f,contract,frozen,projection,budget,bootstrap=durable_material(tmp_path,composition,
        profile_overrides=getattr(request,'param',None),workflow_version='writer-multistep/2',epoch_limits={**LIMITS,'max_input_tokens':100000,'max_wall_seconds':300})
    child=start_worker(bootstrap,f)
    scope,claim,_=prepare_and_claim(child,f,contract,frozen,projection)
    equivalent=f.store.read_json(projection.wire_equivalence_ref)
    loop=f.store.read_json(ArtifactRefV1.model_validate(equivalent['loop_request_ref']))
    wire=f.store.read_json(ArtifactRefV1.model_validate(equivalent['provider_wire_ref']))
    material=child.call('context.materials',{**scope,'contract_ref':f.store.put_json(contract).model_dump(mode='json')})['result']
    row=material['required'][0]
    source={'kind':'code2paper-material','scope':material['scope'],'materialId':row['id'],
        'materialKind':row['kind'],'bytesDigest':row['bytesDigest']}
    loop['messages'].append({'role':'user','source':source,'content':[{'type':'text','text':row['text']}]})
    wire['messages'].append({'role':'user','content':row['text']})
    data=dict(f=f,contract=contract,budget=budget,child=child,scope=scope,claim=claim,loop=loop,wire=wire,
        contract_ref=f.store.put_json(contract).model_dump(mode='json'),bootstrap=bootstrap)
    try:yield data
    finally:data['child'].close()


def observe(data,sequence=1,loop=None,wire=None):
    f=data['f']
    return data['child'].call('request.measure_step',{**data['scope'],'contract_ref':data['contract_ref'],
        'actual_request_ref':f.store.put_json(loop if loop is not None else data['loop']).model_dump(mode='json'),
        'provider_wire_ref':f.store.put_json(wire if wire is not None else data['wire']).model_dump(mode='json'),'sequence':sequence})


def reserve(data,step):
    return data['child'].call('request.reserve_step',{**data['scope'],'contract_ref':data['contract_ref'],
        'budget_ref':data['budget'].model_dump(mode='json'),'step_ref':step,'event_id':'reserve:step'})


def finish(data,reservation,*,usage=(100,7),status='settled'):
    params={**data['scope'],'contract_ref':data['contract_ref'],'reservation':reservation}
    for kind in ('dispatch-recorded','adapter-attempt'):
        result=data['child'].call('request.dispatch',{**params,'event_id':kind,'kind':kind})
        assert 'result' in result,result
    if status=='unknown':
        assert 'result' in data['child'].call('request.mark_unknown',{**params,'event_id':'unknown','kind':'send-outcome-unknown','reason':'unit observer stream unproven'})
        return
    evidence=data['f'].store.put_json({'schema_version':'DshAdapterUsageV1','request_digest':reservation['request_digest'],
        'input_tokens':usage[0],'output_tokens':usage[1],'source':'adapter-usage'})
    result=data['child'].call('request.settle',{**params,'event_id':'usage','kind':'usage','evidence_ref':evidence.model_dump(mode='json'),
        'usage_input_tokens':usage[0],'usage_output_tokens':usage[1]})
    assert 'result' in result,result
    if status=='unfinished':return
    finish_ref=completion_ref(data,reservation,usage=usage)

    for kind in ('terminal','settlement'):
        result=data['child'].call('request.settle',{**params,'event_id':kind,'kind':kind,'evidence_ref':finish_ref.model_dump(mode='json')})
        assert 'result' in result,result



def completion_ref(data,reservation,*,usage=(100,7),damage=None,native=None):
    """Explicit unit Session fixture; actual SDK proof is separately required."""
    f=data['f'];root=f.store.root/'artifacts/06_authoring/invocations'
    reserve_evidence=f.store.read_json(ArtifactRefV1.model_validate(read_dsh_invocation_events(root,reservation['request_id'])[0].evidence_ref))
    step=f.store.read_json(ArtifactRefV1.model_validate(reserve_evidence['step_ref']))
    actual=f.store.read_json(ArtifactRefV1.model_validate(step['actual_request_ref']))
    u=dict(inputTokens=usage[0],outputTokens=usage[1],totalTokens=sum(usage))
    content=[{'type':'text','text':'Step finished.'}]
    streams=[{'type':'chunk','chunk':{'type':'block-start','index':0,'blockType':'text'}},
        {'type':'text-chunks','index':0,'texts':['Step finished.'],'dt':[]},
        {'type':'chunk','chunk':{'type':'block-end','index':0,'block':content[0]}},
        {'type':'chunk','chunk':{'type':'usage','usage':u}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'stop'}}}]
    def row(seq,typ,data):return dict(seq=seq,type=typ,data=data)
    config={k:actual[k] for k in ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
    events=[row(1,'turn/start',{'turn':1}),row(2,'step/start',{'turn':1,'step':step['sequence']}),
        row(3,'request/header',{'header':{'config':config,'tools':actual['tools']}}),
        row(4,'request/context',{'provider':actual['provider'],'model':actual['model']}),
        row(5,'assistant/message',{'turn':1,'step':step['sequence'],
            'message':{'role':'assistant','source':{'kind':'model','provider':actual['provider'],'model':actual['model']},'content':content},
            'stream':streams,'usage':u}),row(6,'step/end',{'turn':1,'step':step['sequence']})]
    evidence={'schema_version':'DshStepFinishObservationV2','request_id':reservation['request_id'],
        'request_digest':reservation['request_digest'],'session_id':step['session_id'],'turn_id':1,'step_id':step['sequence'],
        'source':'gated-adapter-natural-exhaustion/2','finish_reason':'stop','stream_complete':True}
    if native is not None:
        call_id='unit:native-read';args='{"grant_id":"opaque","offset":0,"length":1}'
        block={'type':'tool-call','id':call_id,'name':'c2p_read','arguments':args}
        data_block=events[4]['data'];data_block['message']['content']=[block]
        data_block['stream']=[{'type':'chunk','chunk':{'type':'block-start','index':0,'blockType':'tool-call'}},
            {'type':'tool-call-chunks','index':0,'id':call_id,'name':'c2p_read','args':[args],'dt':[]},
            {'type':'chunk','chunk':{'type':'block-end','index':0,'block':block}},streams[-2],
            {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'tool-calls'}}}]
        events[-1]['seq']=8
        events[5:5]=[row(6,'tool/call',{'turn':1,'step':step['sequence'],'callId':call_id,'name':'c2p_read','arguments':args}),
            {**row(7,'tool/result',{'turn':1,'step':step['sequence'],'message':{'role':'tool','toolCallId':call_id,
                'isError':False,'source':{'kind':'tool','callId':call_id},'content':[{'type':'text','text':'UNIT navigation result.'}]}}),
                'sourceEventSeqs':[6]}]
        evidence['finish_reason']='tool-calls'
        if native!='missing-candidate':
            raw=f.store.put((args if native!='raw-mismatch' else 'different').encode(),media_type='application/octet-stream')
            result=data['child'].call('task.record_tool_candidate',{**data['scope'],'contract_ref':data['contract_ref'],
                'candidate':{'schema_version':'DshToolCandidateV2',**data['scope'],'child_id':step['child_id'],
                    'session_id':step['session_id'],'request_id':reservation['request_id'],'tool_call_id':call_id,
                    'stream_index':step['sequence'],'name':'c2p_read','arguments_ref':raw.model_dump(mode='json'),
                    'source':'gated-adapter-tool-arguments-delta/2'}})
            assert 'result' in result,result
        if native=='missing-result':events.pop(6)
        if native=='result-source':events[6]['sourceEventSeqs']=[1]
        if native=='result-role':events[6]['data']['message']['role']='user'
    if damage=='unfinished':events.pop()
    if damage=='usage':streams[-2]['chunk']['usage']={**u,'inputTokens':1,'totalTokens':1+u['outputTokens']}
    if damage=='finish':streams.pop()
    if damage=='tail':streams.append({'type':'chunk','chunk':{'type':'finish','reason':{'kind':'stop'}}})
    if damage=='foreign-model':events[3]['data']['model']='foreign'
    if damage=='sequence':evidence['step_id']+=1
    if damage=='source':evidence['source']='model-says-complete'
    if damage=='assembly':config['maxTokens']=1
    if damage=='stream-content':content[0]['text']='changed';streams[1]['texts']=['unchanged']
    if damage=='duplicate-assistant':events.insert(5,row(6,'assistant/message',deepcopy(events[4]['data'])));events[-1]['seq']=7
    if step['sequence']>1:
        from code2paper.integrations.dsh.epoch_accounting import epoch_requests
        previous=[]
        for facts in epoch_requests(root,data['contract']):
            terminal=next((row for row in facts if row.kind=='terminal'),None)
            if terminal:
                old=f.store.read_json(ArtifactRefV1.model_validate(terminal.evidence_ref))
                if old.get('schema_version')=='DshStepFinishObservationV2' and old.get('session_id')==step['session_id']:
                    prior=f.store.read_json(ArtifactRefV1.model_validate(old['session_ref']))['events']
                    if len(prior)>len(previous):previous=prior
        if previous:
            events=events[1:]
            for event in events:event['seq']+=previous[-1]['seq']
            events=deepcopy(previous)+events
    evidence['session_ref']=f.store.put_json({'schema_version':'DshSessionCaptureV1','session_id':step['session_id'],
        'format_version':'SessionFileV4','events':events})
    return f.store.put_json(evidence)


@pytest.mark.parametrize('damage',['unfinished','usage','finish','tail','foreign-model','sequence','source','assembly','stream-content','duplicate-assistant'])
def test_v2_completion_damage_retains_original_fees_and_blocks_next(owner,damage):
    d=owner;measurement=observe(d)['result'];r=reserve(d,measurement['step_ref'])['result'];finish(d,r,status='unfinished')
    evidence=completion_ref(d,r,damage=damage)
    result=d['child'].call('request.settle',{**d['scope'],'contract_ref':d['contract_ref'],'reservation':r,
        'kind':'terminal','event_id':'damaged-finish','evidence_ref':evidence.model_dump(mode='json')})
    assert result['error']['message']=='dsh_step_completion_unproven',result
    assert observe(d,2)['error']['message']=='dsh_epoch_has_unsettled_request'


def test_v2_refuses_v1_completion_even_with_existing_artifacts(owner):
    d=owner;measurement=observe(d)['result'];r=reserve(d,measurement['step_ref'])['result'];finish(d,r,status='unfinished')
    ref=d['f'].store.put_json({'schema_version':'DshFinishObservationV1','request_digest':r['request_digest'],
        'finish_reason':'stop','stream_complete':True,'raw_ref':d['f'].store.put_json({'unit':1}),
        'session_ref':d['f'].store.put_json({'unit':1})})
    result=d['child'].call('request.settle',{**d['scope'],'contract_ref':d['contract_ref'],'reservation':r,
        'kind':'terminal','event_id':'legacy-finish','evidence_ref':ref.model_dump(mode='json')})
    assert result['error']['message']=='dsh_step_completion_required'

def test_actual_worker_measures_reserves_next_step_and_keeps_original_fees(owner):
    d=owner;first=observe(d);assert 'result' in first,first
    reservation=reserve(d,first['result']['step_ref']);assert 'result' in reservation,reservation
    first_request=reservation['result'];finish(d,first_request)
    loop=deepcopy(d['loop']);wire=deepcopy(d['wire'])
    loop['messages'].append({'role':'assistant','content':[{'type':'text','text':'Navigation completed.'}]})
    wire['messages'].append({'role':'assistant','content':'Navigation completed.'})
    second=observe(d,2,loop,wire);assert 'result' in second,second
    second_request=reserve(d,second['result']['step_ref']);assert 'result' in second_request,second_request
    assert second_request['result']['request_id']!=first_request['request_id']
    assert second_request['result']['request_digest']!=first_request['request_digest']
    finish(d,second_request['result'],usage=(150,11))
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    assert epoch_totals(root,d['contract'])==dict(model_requests=2,input_tokens=250,output_tokens=18,pending_requests=0)
    budget=read_run_budget_state(root)
    assert not budget['failure_codes'] and budget['spent_input_tokens']==250 and budget['call_count_by_role']['writer']==2
    facts=read_dsh_invocation_events(root,second_request['result']['request_id'])
    assert facts[0].reserved_input_tokens>0 and facts[0].plan_digest!=read_dsh_invocation_events(root,first_request['request_id'])[0].plan_digest
    # The old single-request RPC does not become an unmetered V2 send route.
    rejected=d['child'].call('request.reserve',{**d['scope'],'contract_ref':d['contract_ref'],
        'budget_ref':d['budget'].model_dump(mode='json'),'actual_request_ref':d['f'].store.put_json(loop).model_dump(mode='json'),'event_id':'old-route'})
    assert rejected['error']['message']=='dsh_measured_step_required'


@pytest.mark.parametrize('damage',['summary','wrong-source','changed-system','wire-text','foreign-option','changed-tool','wire-option'])
def test_dynamic_actual_and_provider_material_damage_refuses_before_reserve(owner,damage):
    loop=deepcopy(owner['loop']);wire=deepcopy(owner['wire'])
    if damage=='summary':loop['messages'].pop();wire['messages'].pop()
    if damage=='wrong-source':loop['messages'][-1]['source']['scope']['revision']+=1
    if damage=='changed-system':loop['messages'][0]['content'][0]['text']='rewritten'
    if damage=='wire-text':wire['messages'][-1]['content']='summary'
    if damage=='foreign-option':loop['purpose']='unmetered auxiliary'
    if damage=='changed-tool':loop['tools'][0]['parameters']={'type':'object'}
    if damage=='wire-option':wire['max_tokens']=1
    result=observe(owner,loop=loop,wire=wire)
    assert 'error' in result,result
    assert read_run_budget_state(owner['f'].store.root/'artifacts/06_authoring/invocations')['call_count']==0


@pytest.mark.parametrize('status',['unknown','unfinished'])
def test_pending_liability_blocks_a_fresh_step_and_survives_fresh_worker(owner,status):
    d=owner;measurement=observe(d);assert 'result' in measurement,measurement
    reservation=reserve(d,measurement['result']['step_ref'])['result'];finish(d,reservation,status=status)
    assert observe(d,2)['error']['message']=='dsh_epoch_has_unsettled_request'
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    assert epoch_totals(root,d['contract'])['pending_requests']==1
    d['child'].close();d['child']=start_worker(d['bootstrap'],d['f'])
    resumed=d['child'].call('task.resume',{**d['scope'],'claim':d['claim']});assert 'result' in resumed,resumed
    assert observe(d,2)['error']['message']=='dsh_epoch_has_unsettled_request'
    assert read_run_budget_state(root)['pending_input_tokens']>0


def test_forged_step_output_and_sequence_cannot_underreserve_or_replay(owner):
    d=owner;observed=observe(d)['result']['step_ref']
    step=d['f'].store.read_json(ArtifactRefV1.model_validate(observed))
    step['output_tokens']=1
    assert reserve(d,d['f'].store.put_json(step).model_dump(mode='json'))['error']['message']=='dsh_step_binding_mismatch'
    step['output_tokens']=d['contract'].post_clamp_max_output_tokens;step['sequence']=2
    assert reserve(d,d['f'].store.put_json(step).model_dump(mode='json'))['error']['message']=='dsh_step_sequence_mismatch'
    actual=reserve(d,observed);assert 'result' in actual,actual
    assert reserve(d,observed)['error']['message']=='dsh_step_sequence_mismatch'
    assert read_run_budget_state(d['f'].store.root/'artifacts/06_authoring/invocations')['call_count']==1


def test_original_epoch_output_cap_stops_second_reserve_without_erasing_first_usage(owner):
    d=owner;step=observe(d)['result']['step_ref'];reservation=reserve(d,step)['result']
    finish(d,reservation,usage=(100,3000))
    assert observe(d,2)['error']['message']=='dsh_epoch_output_budget_exceeded'
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    assert epoch_totals(root,d['contract'])==dict(model_requests=1,input_tokens=100,output_tokens=3000,pending_requests=0)
    assert read_run_budget_state(root)['call_count']==1


def reserve_process(bootstrap,initialize,scope,claim,params,barrier,queue):
    from .test_worker_protocol import Child
    child=Child(bootstrap)
    try:
        assert 'result' in child.call('initialize',initialize)
        assert 'result' in child.call('task.resume',{**scope,'claim':claim})
        barrier.wait(timeout=30)
        queue.put(child.call('request.reserve_step',params))
    finally:child.close()


def test_two_real_worker_processes_cannot_double_reserve_same_epoch_sequence(owner):
    import multiprocessing
    from code2paper.integrations.dsh.worker import rpc_schema_digest
    d=owner;step=observe(d)['result']['step_ref']
    initialize=dict(protocol_version='c2p-dsh/1',schema_digest=rpc_schema_digest(),
        validator_digest=d['f'].composition['validator_digest'],max_frame_bytes=1048576)
    params={**d['scope'],'contract_ref':d['contract_ref'],'budget_ref':d['budget'].model_dump(mode='json'),
        'step_ref':step,'event_id':'reserve:race'}
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);queue=ctx.Queue()
    children=[ctx.Process(target=reserve_process,args=(d['bootstrap'],initialize,d['scope'],d['claim'],params,barrier,queue)) for _ in range(2)]
    for process in children:process.start()
    try:
        outcomes=[queue.get(timeout=60) for _ in children]
    finally:
        for process in children:
            process.join(timeout=30)
            if process.is_alive():process.terminate();process.join(timeout=10)
    assert all(process.exitcode==0 for process in children)
    assert len([outcome for outcome in outcomes if 'result' in outcome])==1,outcomes
    assert [outcome['error']['message'] for outcome in outcomes if 'error' in outcome]==['dsh_step_sequence_mismatch']
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    assert read_run_budget_state(root)['call_count']==1


def test_completed_session_cannot_close_a_new_request_with_identical_assembly(owner):
    d=owner;first=reserve(d,observe(d)['result']['step_ref'])['result'];finish(d,first)
    root=d['f'].store.root/'artifacts/06_authoring/invocations'
    old=next(f for f in read_dsh_invocation_events(root,first['request_id']) if f.kind=='terminal')
    old_evidence=d['f'].store.read_json(ArtifactRefV1.model_validate(old.evidence_ref))
    second=reserve(d,observe(d,2)['result']['step_ref'])['result'];finish(d,second,status='unfinished')
    assert second['request_digest']==first['request_digest']
    copied={**old_evidence,'request_id':second['request_id']}
    ref=d['f'].store.put_json(copied)
    result=d['child'].call('request.settle',{**d['scope'],'contract_ref':d['contract_ref'],'reservation':second,
        'kind':'terminal','event_id':'reused-session','evidence_ref':ref.model_dump(mode='json')})
    assert result['error']['message']=='dsh_step_completion_unproven'


@pytest.mark.parametrize('native',['valid','missing-candidate','raw-mismatch','missing-result','result-source','result-role'])
def test_native_navigation_step_requires_original_raw_observation_and_tool_end(owner,native):
    from code2paper.integrations.dsh.step_admission import READ_TOOL
    d=owner;loop=deepcopy(d['loop']);wire=deepcopy(d['wire'])
    loop['tools'].insert(0,deepcopy(READ_TOOL))
    wire['tools'].insert(0,{'type':'function','function':{**READ_TOOL,'strict':False}})
    measured=observe(d,loop=loop,wire=wire);assert 'result' in measured,measured
    r=reserve(d,measured['result']['step_ref'])['result'];finish(d,r,status='unfinished')
    evidence=completion_ref(d,r,native=native)
    params={**d['scope'],'contract_ref':d['contract_ref'],'reservation':r,'evidence_ref':evidence.model_dump(mode='json')}
    result=d['child'].call('request.settle',{**params,'kind':'terminal','event_id':'native:terminal'})
    if native!='valid':
        assert result['error']['message']=='dsh_step_completion_unproven',result
        assert observe(d,2)['error']['message']=='dsh_epoch_has_unsettled_request'
    else:
        assert 'result' in result,result
        assert 'result' in d['child'].call('request.settle',{**params,'kind':'settlement','event_id':'native:settlement'})
        assert epoch_totals(d['f'].store.root/'artifacts/06_authoring/invocations',d['contract'])['pending_requests']==0
