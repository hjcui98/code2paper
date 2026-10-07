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
from code2paper.integrations.dsh.native_stop_retirement import (
    OPERATION,verify_original_finish,retire_native_stop_finish,
)
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.suite_runner import _identity
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_host_recovery_boundaries import recovery_kernel,_ledger,_result,_scope,_params
from .test_host_recovery_boundaries import _enter,_usage
from .test_composition_identity import composition
from .stage04_support import ROOT


def _native_completion(kernel):
    """UNIT original Worker captures/rejects a valid draft and settles six facts."""
    from .fixtures.completed_formalizer_fixture import build_fixture
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    child,facade,contract,claim,request,_=kernel
    reservation=_result(child.call('request.reserve',request));_enter(child,request,reservation)
    material={};build_fixture(material_sink=material,require_atom_targets=True)
    draft=json.loads(material['writer_raw'])
    draft['paragraphs'][0]['paragraph_markdown']='An unrelated operation is performed.'
    draft['section_markdown']='An unrelated operation is performed.'
    args=canonical_json_bytes({'schema_version':'WriterTaskResultV1','result':{'outcome':'draft','draft':draft}})
    raw=facade.store.put(args);scope=_scope(request);sid=facade.context.session_id;call_id='UNIT:native-stop'
    _result(child.call('task.capture_raw',{**scope,'capture':{'schema_version':'DshRawCaptureV1',**scope,
        'child_id':facade.context.child_id,'session_id':sid,'request_id':reservation['request_id'],
        'tool_call_id':call_id,'stream_index':1,'source':'adapter_tool_arguments_delta',
        'arguments_completion':'block-ended','arguments_ref':raw.model_dump(mode='json')}}))
    usage={'inputTokens':40,'outputTokens':3,'totalTokens':43}
    streams=[{'type':'tool-call-chunks','index':0,'id':call_id,'name':'c2p_terminal','args':[args.decode()]},
        {'type':'chunk','chunk':{'type':'block-end','index':0,'block':{'type':'tool-call','id':call_id,'name':'c2p_terminal','arguments':args.decode()}}},
        {'type':'chunk','chunk':{'type':'usage','usage':usage}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'stop'}}}]
    events=[{'type':'turn/start','seq':1,'data':{'turn':1}},
        {'type':'step/start','seq':2,'data':{'turn':1,'step':1}},
        {'type':'assistant/message','seq':3,'data':{'turn':1,'step':1,'message':{'role':'assistant','source':{'kind':'model'}},'usage':usage,'stream':streams}},
        {'type':'tool/call','seq':4,'data':{'turn':1,'step':1,'callId':call_id,'name':'c2p_terminal','arguments':args.decode()}},
        {'type':'tool/result','seq':5,'sourceEventSeqs':[4],'data':{'turn':1,'step':1,'message':{'role':'tool','source':{'kind':'tool','callId':call_id},'toolCallId':call_id,'isError':False,'content':[]}}},
        {'type':'step/end','seq':6,'data':{'turn':1,'step':1}},
        {'type':'turn/end','seq':7,'data':{'turn':1,'reason':{'kind':'completed'}}}]
    session=facade.store.put_json({'schema_version':'DshSessionCaptureV1','session_id':sid,'format_version':'SessionFileV4','events':events})
    _result(child.call('request.settle',_usage(facade,request,reservation)))
    params={**scope,'contract_ref':request['contract_ref']}
    output=_result(child.call('task.record_output',{**params,'envelope':{'schema_version':'OutputEnvelopeV1',**scope,
        'child_id':facade.context.child_id,'session_id':sid,'turn_id':1,'step_id':1,'tool_call_id':call_id,
        'request_id':reservation['request_id'],'source':'adapter_tool_arguments_delta','arguments_complete':True,
        'provider_http':{'status':'not_observed','ref':None},'adapter_arguments':{'status':'observed','ref':raw.model_dump(mode='json')},
        'normalized_arguments':{'status':'observed','ref':raw.model_dump(mode='json')},'stop_reason':'completed','usage':usage,
        'session_capture_ref':session.model_dump(mode='json')}}))
    key=_result(child.call('task.ingest_key',{**params,'output_ref':output}))['idempotency_key']
    rejected=child.call('task.ingest',{**params,'output_ref':output,'idempotency_key':key})
    assert rejected.get('error'),rejected
    _result(child.call('task.cancel',{**scope,'claim':claim}))
    proof=facade.store.put_json({'schema_version':'DshHistoricalNativeStopProofV1',**scope,
        'request_id':reservation['request_id'],'request_digest':reservation['request_digest'],'session_id':sid,
        'source':'operator-reviewed-original-native-stream/1','finish_reason':'stop','raw_ref':raw.model_dump(mode='json'),
        'session_ref':session.model_dump(mode='json')})
    return facade,proof


def _package(kernel,tmp_path):
    facade,q=_native_completion(kernel)
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
    finish=facade.store.read_json(q);args=facade.store.read(ArtifactRefV1.model_validate(finish['raw_ref']))
    session=facade.store.read_json(ArtifactRefV1.model_validate(finish['session_ref']))
    contract=facade.store.read_json(ArtifactRefV1.model_validate(task['prepared']['contract_ref']))
    projection=facade.store.read_json(ArtifactRefV1.model_validate(contract['dsh_wire_contract_ref']))
    eq=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    wire=facade.store.read(ArtifactRefV1.model_validate(eq['provider_wire_ref']))
    loop=facade.store.read_json(ArtifactRefV1.model_validate(eq['loop_request_ref']))
    model=json.loads(wire)['model'];call_id=task['captured_source']['tool_call_id']
    usage={'prompt_tokens':40,'completion_tokens':3,'total_tokens':43}
    sse=[{'id':'UNIT:response','model':model,'choices':[{'index':0,'delta':{'tool_calls':[
        {'index':0,'id':call_id,'function':{'name':'c2p_terminal','arguments':args.decode()}}]},'finish_reason':None}]},
        {'id':'UNIT:response','model':model,'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]},
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
    files['failure']=bound(write('failure.json',{'actual_model_inference_requests':1,
        'terminal_observation':{'request_id':facts[0].invocation_id,'raw_ref':finish['raw_ref'],'session_ref':finish['session_ref']}}))
    files['bootstrap']=bound(kernel[5])
    files['descriptor']=bound(write('descriptor.json',{'scope':scope.__dict__,
        'composition_digest':boot['composition']['composition_digest'],
        'frozen_ref':frozen_ref}))
    files['wire']=bound(write('wire.json',wire))
    files['calibration']=bound(write('calibration.json',{'loop':loop}))
    files['producer']=bound(write('producer.mjs',b'// UNIT reviewed natural-exhaustion producer fixture\n'))
    files['dispatch']=bound(write('dispatch.json',{'requests':1,'body':files['wire']}))
    files['provider']=bound(write('provider.json',{'http_status':200,'usage':usage,'finish_reasons':['stop'],'provider_errors':[]}))
    files['tokenizer']=bound(write('tokenizer.json',{'origin':'vllm_tokenize_exact_messages_tools',
        'wire_digest':digest_bytes(wire),'model':model,'input_tokens':40}))
    files['sse']=bound(write('response.sse',b''.join(b'data: '+canonical_json_bytes(e)+b'\n\n' for e in sse)+b'data: [DONE]\n\n'))
    files['session']=bound(write('session.jsonl',b''.join(canonical_json_bytes(e)+b'\n' for e in [
        {'type':'session','version':4,'id':finish['session_id']},*session['events']])))
    old={k:boot['composition'][k] for k in ('engine_digest','validator_digest','composition_digest')}
    files['packet']=bound(write('packet.json',{'engine_digest':old['engine_digest'],'frozen_files':[
        files[k] for k in ('bootstrap','descriptor','wire','calibration','producer')]}))
    files['original_plan']=bound(write('original-plan.json',{'packet_digest':files['packet']['bytes_digest']}))
    files['grant']=bound(write('grant.json',{'schema_version':'L01ExplicitUserGrantRecordV1',
        'packet_digest':files['packet']['bytes_digest'],'execution_plan_digest':files['original_plan']['bytes_digest'],
        'authorization':{'approved':True,'primary_requests':1,'retries':0,'packet_digest':files['packet']['bytes_digest'],'model':model},
        'additional_authorized_scope':'UNIT original normal-finish release grant fixture'}))
    owner=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']
    att={'schema_version':'DshNativeStopRetirementAttestationV1','owner':owner,
        'state_root':str(facade.backend_admission.root),'task_scope':scope.__dict__,'historical_identity':old,
        'request_id':facts[0].invocation_id,'request_digest':facts[0].request_digest,'finish_observation':finish,'prior_history_digest':digest_json([]),
        'task_view_digest':digest_json(task),'ledger_digest':digest_json([f.model_dump(mode='json') for f in facts]),
        'budget_digest':digest_json(budget),'files':files}
    att_path=write('attestation.json',att)
    snapshot,validator=_identity(ROOT);identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    plan_path=out/'plan.json';review_path=out/'review.json';auth_path=out/'authorization.json'
    plan={'schema_version':'DshNativeStopRetirementPlanV1','operation':OPERATION,'attestation':bound(att_path),
        'implementation_identity':identity,'command':['python','-m','code2paper.integrations.dsh.native_stop_retirement',
            '--engine-root',str(ROOT),'--plan',str(plan_path),'--review',str(review_path),'--authorization',str(auth_path)],
        'new_provider_requests':0,'authorized_effects':['exact-owner-release','immutable-release-history']}
    write('plan.json',plan)
    write('review.json',{'schema_version':'DshNativeStopRetirementReviewV1','decision':'PASS','operation':OPERATION,
        'plan_digest':bound(plan_path)['bytes_digest'],'attestation_digest':bound(att_path)['bytes_digest'],
        'implementation_identity':identity,'producer_digest':files['producer']['bytes_digest'],
        'producer_protocol':'fetch-reader-done/archive-before-error-v1'})
    write('authorization.json',{'schema_version':'DshNativeStopRetirementAuthorizationV1','approved':True,'operation':OPERATION,
        'plan_digest':bound(plan_path)['bytes_digest'],'review_digest':bound(review_path)['bytes_digest'],
        'grant_digest':files['grant']['bytes_digest'],'owner':owner,'task_scope':scope.__dict__,
        'authorized_effects':plan['authorized_effects'],'new_provider_requests':0})
    return facade,att,{k:Path(v['path']).read_bytes() for k,v in files.items()},dict(engine_root=ROOT,
        plan_path=plan_path,review_path=review_path,authorization_path=auth_path)


def test_native_stop_retirement_only_releases_original_owner_and_keeps_failure_and_fees(recovery_kernel,tmp_path):
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    before_task=facade.task_store.read();before_budget=read_run_budget_state(_ledger(facade))
    receipt=retire_native_stop_finish(facade.backend_admission,**kwargs)
    assert receipt['operation']==OPERATION
    assert retire_native_stop_finish(facade.backend_admission,**kwargs)==receipt
    assert facade.task_store.read()==before_task
    assert read_run_budget_state(_ledger(facade))==before_budget
    assert before_task['receipt'] is None and before_task['provider_quiescence'] is None
    with pytest.raises(ProtocolError,match='backend_owner_retired'):
        facade.backend_admission.acquire(execution_id=att['owner']['execution_id'],run_root=facade.store.root)
    other=tmp_path/'new-owner';other.mkdir()
    new=facade.backend_admission.acquire(execution_id='execution:new',run_root=other)
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):
        retire_native_stop_finish(facade.backend_admission,**kwargs)
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
    elif damage=='finish':raw['sse']=raw['sse'].replace(b'stop',b'tool_calls')
    elif damage=='session':raw['session']=raw['session'].replace(b'completed',b'blocked')
    elif damage=='raw':raw['sse']=raw['sse'].replace(b'outcome',b'changed')
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
        if damage=='history':retire_native_stop_finish(facade.backend_admission,**kwargs)
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
        retire_native_stop_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']==('owned' if cut=='before-commit' else 'empty')
    monkeypatch.setattr(facade.backend_admission,'_transaction',original)
    receipt=retire_native_stop_finish(facade.backend_admission,**kwargs)
    assert retire_native_stop_finish(facade.backend_admission,**kwargs)==receipt
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
    with pytest.raises(ProtocolError):retire_native_stop_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']=='owned'


@pytest.mark.parametrize('damage',['missing-call','missing-result','error-result','foreign-call','foreign-step',
    'wrong-event-link','changed-arguments','duplicate-result','after-step','wrong-end'])
def test_completed_label_never_substitutes_successful_bound_tool_result(recovery_kernel,tmp_path,damage):
    import copy
    from code2paper.integrations.dsh.native_stop_retirement import verify_completed_tool
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    facade,att,raw,_=_package(recovery_kernel,tmp_path)
    finish=att['finish_observation'];task=facade.task_store.read()
    session=copy.deepcopy(facade.store.read_json(ArtifactRefV1.model_validate(finish['session_ref'])))
    events=session['events'];call=events[3];result=events[4]
    if damage=='missing-call':events.remove(call)
    elif damage=='missing-result':events.remove(result)
    elif damage=='error-result':result['data']['message']['isError']=True
    elif damage=='foreign-call':result['data']['message']['toolCallId']='foreign'
    elif damage=='foreign-step':result['data']['step']=2
    elif damage=='wrong-event-link':result['sourceEventSeqs']=[3]
    elif damage=='changed-arguments':call['data']['arguments']='{}'
    elif damage=='duplicate-result':events.append(copy.deepcopy(result))
    elif damage=='after-step':result['seq']=7
    else:events[-1]['data']['reason']={'kind':'error'}
    args=facade.store.read(ArtifactRefV1.model_validate(finish['raw_ref']))
    with pytest.raises(ProtocolError):verify_completed_tool(session,task,finish,args)
    assert facade.task_store.read()==task
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'


def test_reviewed_prior_history_digest_must_match_at_exact_owner_mutation(recovery_kernel,tmp_path):
    facade,att,raw,kwargs=_package(recovery_kernel,tmp_path)
    plan_path=kwargs['plan_path'];review_path=kwargs['review_path'];auth_path=kwargs['authorization_path']
    plan=json.loads(plan_path.read_bytes());att_path=Path(plan['attestation']['path'])
    att['prior_history_digest']=digest_json(['unrelated history'])
    att_path.write_bytes(canonical_json_bytes(att));b=att_path.read_bytes()
    plan['attestation'].update(bytes_digest=digest_bytes(b),byte_length=len(b));plan_path.write_bytes(canonical_json_bytes(plan))
    review=json.loads(review_path.read_bytes());review.update(plan_digest=digest_bytes(plan_path.read_bytes()),attestation_digest=digest_bytes(b))
    review_path.write_bytes(canonical_json_bytes(review))
    auth=json.loads(auth_path.read_bytes());auth.update(plan_digest=digest_bytes(plan_path.read_bytes()),review_digest=digest_bytes(review_path.read_bytes()))
    auth_path.write_bytes(canonical_json_bytes(auth))
    with pytest.raises(ProtocolError,match='backend_release_history_drift'):retire_native_stop_finish(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
