"""UNIT historical migration over actual Worker/fee/admission owners.

Transport, grant and independent review are explicit fixtures, not consent or
live evidence. Native Loader/SSE rejection is tested separately in Node.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events,read_run_budget_state
from code2paper.integrations.dsh.unknown_tool_retirement import (
    OPERATION,verify_original_finish,retire_unknown_tool_finish,
)
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.suite_runner import _identity
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_host_recovery_boundaries import recovery_kernel,_ledger,_result,_enter,_usage,_params,_scope
from .test_composition_identity import composition
from .stage04_support import ROOT


def _historical_finish(kernel):
    # Fixture producer evidence, using the actual private Worker and original
    # accounting path. This does not represent operator consent or a live EOF.
    from copy import deepcopy
    from .test_unknown_tool_completion import fixture
    child,facade,_,claim,request,_=kernel
    reservation=_result(child.call('request.reserve',request));_enter(child,request,reservation)
    actual=facade.store.read_json(ArtifactRefV1.model_validate(request['actual_request_ref']))
    _,_,_,_,session,_,_=fixture()
    session=deepcopy(session);session['session_id']=facade.context.session_id
    events=session['events'];data=events[4]['data']
    data['message']['source']={'kind':'model','provider':actual.get('provider'),'model':actual['model']}
    usage={'inputTokens':40,'outputTokens':3,'totalTokens':43};data['usage']=usage
    data['stream'][3]['chunk']['usage']=usage
    events[2]['data']['header']={'config':{k:actual[k] for k in ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual},'tools':actual['tools']}
    events[3]['data']={'provider':actual.get('provider'),'model':actual['model']}
    session_ref=facade.store.put_json(session);raw=facade.store.put(b'')
    _result(child.call('request.settle',_usage(facade,request,reservation)))
    _result(child.call('task.cancel',{**_scope(request),'claim':claim}))
    evidence=facade.store.put_json({'schema_version':'DshFinishObservationV1',
        'request_digest':reservation['request_digest'],'finish_reason':'tool-calls','stream_complete':True,
        'raw_ref':raw.model_dump(mode='json'),'session_ref':session_ref.model_dump(mode='json')})
    for kind in ('terminal','settlement'):
        _result(child.call('request.settle',{**_params(request,reservation),'event_id':'unknown:observed-'+kind,
            'kind':kind,'evidence_ref':evidence.model_dump(mode='json')}))
    return facade,evidence


def _package(kernel,tmp_path):
    facade,q=_historical_finish(kernel)
    kernel[0].close()
    out=tmp_path/'native-retirement';out.mkdir()
    def write(name,value):
        p=out/name;p.write_bytes(value if isinstance(value,bytes) else canonical_json_bytes(value));return p
    def bound(p):
        b=p.read_bytes();return {'path':str(p),'bytes_digest':digest_bytes(b),'byte_length':len(b)}
    boot=json.loads(kernel[5].read_bytes());scope=facade.store.scope
    task=facade.task_store.read();ledger=_ledger(facade)
    path=next(ledger.glob('*/attempt-0001.dsh-event-000001.json'))
    facts=read_dsh_invocation_events(ledger,json.loads(path.read_bytes())['invocation_id'])
    budget=read_run_budget_state(ledger)
    finish=facade.store.read_json(q);args=b'{}'
    session=facade.store.read_json(ArtifactRefV1.model_validate(finish['session_ref']))
    contract=facade.store.read_json(ArtifactRefV1.model_validate(task['prepared']['contract_ref']))
    projection=facade.store.read_json(ArtifactRefV1.model_validate(contract['dsh_wire_contract_ref']))
    eq=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    wire=facade.store.read(ArtifactRefV1.model_validate(eq['provider_wire_ref']))
    loop=facade.store.read_json(ArtifactRefV1.model_validate(eq['loop_request_ref']))
    model=json.loads(wire)['model'];call_id=next(e['data']['callId'] for e in session['events'] if e['type']=='tool/call')
    name=next(e['data']['name'] for e in session['events'] if e['type']=='tool/call')
    usage={'prompt_tokens':40,'completion_tokens':3,'total_tokens':43}
    sse=[{'id':'UNIT:response','model':model,'choices':[{'index':0,'delta':{'tool_calls':[
        {'index':0,'id':call_id,'function':{'name':name,'arguments':args.decode()}}]},'finish_reason':None}]},
        {'id':'UNIT:response','model':model,'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}]},
        {'id':'UNIT:response','model':model,'choices':[],'usage':usage}]
    files={}
    frozen_ref=None
    for path in facade.store.directory.iterdir():
        try:value=json.loads(path.read_bytes())
        except (ValueError,UnicodeDecodeError):continue
        if isinstance(value,dict) and value.get('schema_version')=='FrozenWriterInputV1':
            frozen_ref=ArtifactRefV1(schema_version='ArtifactRefV1',artifact_id=digest_bytes(path.read_bytes()),
                **scope.__dict__,media_type='application/json',byte_length=path.stat().st_size,
                bytes_digest=digest_bytes(path.read_bytes()),semantic_digest=digest_json(value)).model_dump(mode='json')
            break
    assert frozen_ref is not None
    files['bootstrap']=bound(kernel[5])
    files['descriptor']=bound(write('descriptor.json',{'scope':scope.__dict__,
        'composition_digest':boot['composition']['composition_digest'],
        'frozen_ref':frozen_ref}))
    files['wire']=bound(write('wire.json',wire))
    files['calibration']=bound(write('calibration.json',{'loop':loop}))
    files['producer']=bound(write('producer.mjs',b'// UNIT reviewed natural-exhaustion producer fixture\n'))
    files['dispatch']=bound(write('dispatch.json',{'requests':1,'body':files['wire']}))
    files['provider']=bound(write('provider.json',{'http_status':200,'usage':usage,'finish_reasons':['tool_calls']}))
    files['tokenizer']=bound(write('tokenizer.json',{'origin':'vllm_tokenize_exact_messages_tools',
        'wire_digest':digest_bytes(wire),'model':model,'input_tokens':40}))
    files['sse']=bound(write('response.sse',b''.join(b'data: '+canonical_json_bytes(e)+b'\n\n' for e in sse)+b'data: [DONE]\n\n'))
    files['session']=bound(write('session.jsonl',b''.join(canonical_json_bytes(e)+b'\n' for e in [
        {'type':'session','version':4,'id':task['binding']['session_id']},*session['events']])))
    old={k:boot['composition'][k] for k in ('engine_digest','validator_digest','composition_digest')}
    files['packet']=bound(write('packet.json',{'engine_digest':old['engine_digest'],'frozen_files':[
        files[k] for k in ('bootstrap','descriptor','wire','calibration','producer')]}))
    files['original_plan']=bound(write('original-plan.json',{'packet_digest':files['packet']['bytes_digest']}))
    files['grant']=bound(write('grant.json',{'schema_version':'L01ExplicitUserGrantRecordV1',
        'packet_digest':files['packet']['bytes_digest'],'plan_digest':files['original_plan']['bytes_digest'],
        'authorization':{'approved':True,'primary_requests':1,'retries':0,'packet_digest':files['packet']['bytes_digest'],'model':model},
        'authorization_file':bound(write('original-auth.json',{'approved':True,'primary_requests':1,'retries':0,'packet_digest':files['packet']['bytes_digest'],'model':model})),
        'additional_authorized_scope':'UNIT trusted normal-finish exact-owner release fixture'}))
    files['launch']=bound(write('launch.json',{'mode':'live','output':str(facade.store.root.parent.parent),
        'scope':'UNIT original launch fixture','inference_authorized':True,
        'argv':['UNIT:producer','live',str(facade.store.root.parent.parent),'UNIT:coverage',str(out/'original-auth.json')]}))
    owner=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']
    att={'schema_version':'DshUnknownToolRetirementAttestationV1','owner':owner,
        'state_root':str(facade.backend_admission.root),'task_scope':scope.__dict__,'historical_identity':old,
        'request_id':facts[0].invocation_id,'request_digest':facts[0].request_digest,'session_id':task['binding']['session_id'],
        'task_view_digest':digest_json(task),'ledger_digest':digest_json([f.model_dump(mode='json') for f in facts]),
        'budget_digest':digest_json(budget),'files':files}
    att_path=write('attestation.json',att)
    snapshot,validator=_identity(ROOT);identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    plan_path=out/'plan.json';review_path=out/'review.json';auth_path=out/'authorization.json'
    plan={'schema_version':'DshUnknownToolRetirementPlanV1','operation':OPERATION,'attestation':bound(att_path),
        'implementation_identity':identity,'command':['python','-m','code2paper.integrations.dsh.unknown_tool_retirement',
            '--engine-root',str(ROOT),'--plan',str(plan_path),'--review',str(review_path),'--authorization',str(auth_path)],
        'new_provider_requests':0,'authorized_effects':['exact-owner-release','immutable-release-history']}
    write('plan.json',plan)
    write('review.json',{'schema_version':'DshUnknownToolRetirementReviewV1','decision':'PASS','operation':OPERATION,
        'plan_digest':bound(plan_path)['bytes_digest'],'attestation_digest':bound(att_path)['bytes_digest'],
        'implementation_identity':identity,'producer_digest':files['producer']['bytes_digest'],
        'producer_protocol':'fetch-reader-done/archive-before-error-v1'})
    write('authorization.json',{'schema_version':'DshUnknownToolRetirementAuthorizationV1','approved':True,'operation':OPERATION,
        'plan_digest':bound(plan_path)['bytes_digest'],'review_digest':bound(review_path)['bytes_digest'],
        'grant_digest':files['grant']['bytes_digest'],'owner':owner,'task_scope':scope.__dict__,
        'authorized_effects':plan['authorized_effects'],'new_provider_requests':0})
    return facade,att,{k:Path(v['path']).read_bytes() for k,v in files.items()},dict(engine_root=ROOT,
        plan_path=plan_path,review_path=review_path,authorization_path=auth_path)


def test_unknown_tool_retirement_only_releases_original_owner_and_keeps_failure_and_fees(recovery_kernel,tmp_path):
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    before_task=facade.task_store.read();before_budget=read_run_budget_state(_ledger(facade))
    receipt=retire_unknown_tool_finish(facade.backend_admission,**kwargs)
    assert receipt['operation']==OPERATION
    assert retire_unknown_tool_finish(facade.backend_admission,**kwargs)==receipt
    assert facade.task_store.read()==before_task
    assert read_run_budget_state(_ledger(facade))==before_budget
    assert before_task['receipt'] is None and before_task['provider_quiescence'] is None
    with pytest.raises(ProtocolError,match='backend_owner_retired'):
        facade.backend_admission.acquire(execution_id=att['owner']['execution_id'],run_root=facade.store.root)
    other=tmp_path/'new-owner';other.mkdir()
    new=facade.backend_admission.acquire(execution_id='execution:new',run_root=other)
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):
        retire_unknown_tool_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['owner']==new


@pytest.mark.parametrize('damage',['scope','resource','request','claim','usage','finish','session','raw','history','original-grant','grant-bool-count','dispatch-bool-count'])
def test_historical_native_proof_refuses_wrong_scope_transport_or_history(recovery_kernel,tmp_path,damage):
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    if damage=='scope':att['task_scope']['task_epoch']+=1
    elif damage=='resource':att['owner']['resource_key']='other'
    elif damage=='request':att['request_id']='other'
    elif damage=='claim':att['ledger_digest']='sha256:'+'0'*64
    elif damage=='usage':raw['tokenizer']=canonical_json_bytes({'origin':'vllm_tokenize_exact_messages_tools','input_tokens':0})
    elif damage=='finish':raw['sse']=raw['sse'].replace(b'tool_calls',b'stop')
    elif damage=='session':raw['session']=raw['session'].replace(b'blocked',b'completed')
    elif damage=='raw':raw['sse']=raw['sse'].replace(b'{}',b'{changed}')
    elif damage=='original-grant':
        value=json.loads(raw['grant']);value['additional_authorized_scope']='no local release granted'
        raw['grant']=canonical_json_bytes(value)
    elif damage=='grant-bool-count':
        value=json.loads(raw['grant']);value['authorization']['primary_requests']=True
        raw['grant']=canonical_json_bytes(value)
    elif damage=='dispatch-bool-count':
        value=json.loads(raw['dispatch']);value['requests']=True
        raw['dispatch']=canonical_json_bytes(value)
    else:
        with facade.backend_admission._transaction() as db:
            db.execute('CREATE TABLE release_history (release_key TEXT PRIMARY KEY, receipt BLOB NOT NULL)')
            db.execute('INSERT INTO release_history VALUES (?,?)',('damaged',b'{}'))
    with pytest.raises(ProtocolError):
        if damage=='history':retire_unknown_tool_finish(facade.backend_admission,**kwargs)
        else:verify_original_finish(facade.backend_admission,att,raw)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']=='owned'


@pytest.mark.parametrize('cut',['before-commit','after-commit'])
def test_native_retirement_history_and_release_recover_at_atomic_transaction_cuts(recovery_kernel,tmp_path,monkeypatch,cut):
    from contextlib import contextmanager
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    original=facade.backend_admission._transaction
    @contextmanager
    def interrupted():
        with original() as db:
            yield db
            if cut=='before-commit':raise ProtocolError('UNIT retirement cut')
        if cut=='after-commit':raise ProtocolError('UNIT lost retirement response')
    monkeypatch.setattr(facade.backend_admission,'_transaction',interrupted)
    with pytest.raises(ProtocolError,match='UNIT'):
        retire_unknown_tool_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']==('owned' if cut=='before-commit' else 'empty')
    monkeypatch.setattr(facade.backend_admission,'_transaction',original)
    receipt=retire_unknown_tool_finish(facade.backend_admission,**kwargs)
    assert retire_unknown_tool_finish(facade.backend_admission,**kwargs)==receipt
    assert facade.task_store.read()['receipt'] is None
    assert facade.task_store.read()['provider_quiescence'] is None


@pytest.mark.parametrize('damage',['not-approved','bool-request-count','extra-effect','drift-plan','drift-review','drift-attestation'])
def test_review_and_authorization_are_bound_to_exact_zero_send_release_plan(recovery_kernel,tmp_path,damage):
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    key='authorization_path'
    if damage=='drift-plan':key='plan_path'
    elif damage=='drift-review':key='review_path'
    p=kwargs[key];value=json.loads(p.read_bytes())
    if damage=='not-approved':value['approved']=1
    elif damage=='bool-request-count':value['new_provider_requests']=False
    elif damage=='extra-effect':value['authorized_effects'].append('settlement')
    elif damage=='drift-attestation':Path(json.loads(kwargs['plan_path'].read_bytes())['attestation']['path']).write_bytes(b'{}')
    else:value['new_field']='drift'
    p.write_bytes(canonical_json_bytes(value))
    with pytest.raises(ProtocolError):retire_unknown_tool_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']=='owned'


@pytest.mark.parametrize('damage',['delta_unknown','role','reasoning_type','reasoning_dual',
    'tool_type','tool_id','tool_unknown','function_unknown','function_type','calls_type',
    'choice_type','delta_type','response_id_type','missing_done','second_finish','usage_bool'])
def test_unknown_stream_representation_damage_is_refused(damage):
    from code2paper.integrations.dsh.unknown_tool_retirement import verify_unknown_stream
    events=[{'id':'UNIT:sse','model':'UNIT:model','choices':[{'index':0,'delta':{'tool_calls':[
        {'index':0,'id':'UNIT:tool','type':'function','function':{'name':'unknown','arguments':'{}'}}]},'finish_reason':None}]},
        {'id':'UNIT:sse','model':'UNIT:model','choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}]},
        {'id':'UNIT:sse','model':'UNIT:model','choices':[],'usage':{'prompt_tokens':7,'completion_tokens':3,'total_tokens':10}}]
    choice=events[0]['choices'][0];d=choice['delta'];tool=d['tool_calls'][0]
    if damage=='delta_unknown':d['other']='x'
    elif damage=='role':d['role']='user'
    elif damage=='reasoning_type':d['reasoning']=[]
    elif damage=='reasoning_dual':d.update(reasoning='x',reasoning_content='y')
    elif damage=='tool_type':tool['type']='other'
    elif damage=='tool_id':tool['id']=[]
    elif damage=='tool_unknown':tool['other']='x'
    elif damage=='function_unknown':tool['function']['other']='x'
    elif damage=='function_type':tool['function']=[]
    elif damage=='calls_type':d['tool_calls']=None
    elif damage=='choice_type':events[0]['choices']=[None]
    elif damage=='delta_type':choice['delta']=[]
    elif damage=='response_id_type':events[0]['id']=[]
    elif damage=='second_finish':events.insert(2,events[1])
    elif damage=='usage_bool':events[2]['usage']['prompt_tokens']=True
    raw=b''.join(b'data: '+canonical_json_bytes(e)+b'\n\n' for e in events)
    if damage!='missing_done':raw+=b'data: [DONE]\n\n'
    with pytest.raises(ProtocolError):verify_unknown_stream(raw,'UNIT:model')
