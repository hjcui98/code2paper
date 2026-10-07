"""UNIT operator packages over actual original Worker/ledger/SQLite owners.

Transport and review artifacts here are explicit structural fixtures. They
are not native EOF, independent approval, operator consent, or live evidence.
"""
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.unified_invocation_ledger import read_run_budget_state,read_dsh_invocation_events
from code2paper.integrations.dsh.legacy_retirement import verify_stream,verify_session,verify_historical_transport
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.suite_runner import _identity
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_host_recovery_boundaries import recovery_kernel,_result,_enter,_usage,_params,_scope,_ledger
from .test_composition_identity import composition
from .stage04_support import start_worker,ROOT


def _transport(model,session_id,reserved_input_tokens=41):
    args=b'{"schema_version":"WriterTaskResultV1","result":"UNIT rejected string"}'
    usage={'prompt_tokens':40,'completion_tokens':3,'total_tokens':43}
    rows=[{'id':'unit:response','model':model,'choices':[{'index':0,'delta':{'tool_calls':[
        {'index':0,'id':'unit:call','function':{'name':'c2p_terminal','arguments':args.decode()}}]},'finish_reason':None}]},
        {'id':'unit:response','model':model,'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}]},
        {'id':'unit:response','model':model,'choices':[],'usage':usage}]
    sse=b''.join(b'data: '+canonical_json_bytes(row)+b'\n\n' for row in rows)+b'data: [DONE]\n\n'
    error={'code':'PI_AI_ERROR','message':f'actual usage must match exact-wire tokenizer\n\n40 !== {reserved_input_tokens}\n'}
    session=[{'type':'session','version':4,'id':session_id},
        {'type':'turn/start','seq':1,'data':{'turn':1}},
        {'type':'step/start','seq':2,'data':{'turn':1,'step':1}},
        {'type':'assistant/attempt','seq':3,'data':{'turn':1,'step':1,'stream':[
            {'type':'chunk','chunk':{'type':'block-start','blockType':'tool-call','index':0}},
            {'type':'tool-call-chunks','index':0,'id':'unit:call','name':'c2p_terminal','args':[args.decode()]},
            {'type':'chunk','chunk':{'type':'usage','usage':{'inputTokens':40,'outputTokens':3,'totalTokens':43}}},
            {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'error','failure':error}}}]}},
        {'type':'step/end','seq':4,'data':{'turn':1,'step':1}},
        {'type':'turn/end','seq':5,'data':{'turn':1,'reason':{'kind':'error','error':error}}}]
    return args,usage,sse,b''.join(canonical_json_bytes(row)+b'\n' for row in session)


def _package(kernel,tmp_path,*,settle=True,observe_usage=True):
    child,facade,contract,claim,request,bootstrap=kernel
    reservation=_result(child.call('request.reserve',request));_enter(child,request,reservation)
    if observe_usage:_result(child.call('request.settle',_usage(facade,request,reservation)))
    _result(child.call('task.cancel',{**_scope(request),'claim':claim}));child.close()
    loop=facade.store.read_json(ArtifactRefV1.model_validate(request['actual_request_ref']))
    projection=facade.store.read_json(contract.dsh_wire_contract_ref)
    equivalence=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    calibration_loop=facade.store.read_json(ArtifactRefV1.model_validate(equivalence['loop_request_ref']))
    provider_wire=facade.store.read(ArtifactRefV1.model_validate(equivalence['provider_wire_ref']))
    reserved=read_dsh_invocation_events(_ledger(facade),reservation['request_id'])[0].reserved_input_tokens
    args,usage,sse,session=_transport(loop['model'],facade.context.session_id,reserved)
    recovered=start_worker(bootstrap,facade)
    try:
        _result(recovered.call('task.recover',{**_scope(request),'owner':'host:UNIT-legacy-settlement'}))
        if settle:
            raw_ref=facade.store.put(args);session_ref=facade.store.put(session)
            finish=facade.store.put_json({'schema_version':'DshFinishObservationV1',
                'request_digest':reservation['request_digest'],'finish_reason':'tool_calls','stream_complete':True,
                'raw_ref':raw_ref.model_dump(mode='json'),'session_ref':session_ref.model_dump(mode='json')})
            for kind in ('terminal','settlement'):
                _result(recovered.call('request.settle',{**_params(request,reservation),
                    'event_id':'unit:legacy:'+kind,'kind':kind,'evidence_ref':finish.model_dump(mode='json')}))
    finally:recovered.close()
    out=tmp_path/'operator-unit';out.mkdir()
    def write(name,value):
        p=out/name;p.write_bytes(value if isinstance(value,bytes) else canonical_json_bytes(value));return p
    def bound(p):
        raw=p.read_bytes();return {'path':str(p),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}
    boot=json.loads(bootstrap.read_bytes());old={k:boot['composition'][k] for k in ('engine_digest','validator_digest','composition_digest')}
    owner=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']
    files={};files['packet']=bound(write('packet.json',{'engine_digest':old['engine_digest']}))
    files['descriptor']=bound(write('descriptor.json',{'scope':_scope(request),'composition_digest':old['composition_digest'],
        'frozen_ref':contract.resolved_snapshot_ref.model_dump(mode='json')}))
    files['bootstrap']=bound(bootstrap)
    files['original_authorization']=bound(write('original-authorization.json',{'schema_version':'L01OperatorAuthorizationV1',
        'approved':True,'primary_requests':1,'retries':0,'packet_digest':files['packet']['bytes_digest'],'model':loop['model']}))
    files['live_started']=bound(write('started.json',{'authorization':files['original_authorization']}))
    files['launch']=bound(write('launch.json',{'mode':'live','inference_authorized':True}))
    files['wire']=bound(write('wire.json',provider_wire))
    files['dispatch']=bound(write('dispatch.json',{'requests':1,'body':files['wire']}))
    files['calibration']=bound(write('calibration.json',{'actual_provider_body':files['wire'],'calibration_sends':1,'loop':calibration_loop}))
    files['sse']=bound(write('response.sse',sse));files['session']=bound(write('session.jsonl',session))
    files['provider']=bound(write('provider.json',{'http_status':200,'usage':usage,'finish_reasons':['tool_calls']}))
    files['cleanup']=bound(write('cleanup.json',{'worker_scope_quiescent':True,'errors':[],'remote_provider_quiescence':'stream ended',
        'sentinel':{'state':'closed','probe_refused':True,'model_calls':0,'network_calls':0}}))
    files['producer']=bound(write('producer.js',b'UNIT reviewed EOF producer stand-in; not native evidence'))
    historical={k:v['path'] for k,v in files.items()}
    files['manifest']=bound(write('manifest.json',list(files.values())))
    att={'schema_version':'DshLegacyTransportAttestationV1','owner':owner,'task_scope':_scope(request),
         'task_binding':facade.task_store.read()['binding'],
         'historical_identity':old,'request_id':reservation['request_id'],'request_digest':reservation['request_digest'],
         'files':files,'historical_paths':historical}
    att_path=write('attestation.json',att)
    snapshot,validator=_identity(ROOT);identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    executable=write('unit-entry.py',b'UNIT non-executed entry point')
    target=write('unit-mount-target.py',b'UNIT target placeholder')
    execution_files={key:bound(executable) for key in ('entry_point','settlement_launcher','settlement_worker')}
    mounts=[]
    for key in ('python_module_manifest','python_test_manifest','node_test_manifest'):
        source=out/(key+'-source');source.mkdir()
        destination=out/(key+'-target');destination.mkdir()
        member=source/'unit.txt';member.write_bytes(b'UNIT immutable overlay member')
        execution_files[key]=bound(write(key+'.json',{'source':str(source),'mount_target':str(destination),
            'files':[{**bound(member),'historical_path':str(destination/'unit.txt')}]}))
        mounts+=['--ro-bind',str(source),str(destination)]
    execution_files['mount_manifest']=bound(write('mounts.json',[{'source':str(executable),
        'mount_target':str(target),'bytes_digest':bound(executable)['bytes_digest'],'byte_length':len(executable.read_bytes())}]))
    mounts+=['--ro-bind',str(executable),str(target)]
    plan=write('plan.json',{'schema_version':'DshLegacyRetirementPlanV1','attestation_digest':digest_json(att),'owner':owner,
        'task_scope':_scope(request),'historical_identity':old,'implementation_identity':identity,'new_provider_requests':0})
    plan_value=json.loads(plan.read_bytes())
    plan_value.update(execution_files=execution_files,commands={
        'settlement':['UNIT-no-execute',*mounts,'--','UNIT-no-execute'],'retirement':['UNIT-no-execute']})
    plan.write_bytes(canonical_json_bytes(plan_value))
    review=write('review.json',{'schema_version':'DshLegacyRetirementReviewV1','decision':'PASS','plan_digest':digest_bytes(plan.read_bytes()),
        'attestation_digest':digest_json(att),'implementation_identity':identity,
        'eof_producer_protocol':'fetch-reader-done/archive-before-error-v1','eof_producer_digest':files['producer']['bytes_digest']})
    auth=write('authorization.json',{'schema_version':'DshLegacyRetirementAuthorizationV1','purpose':'legacy-observed-transport-retirement',
        'approved':True,'authorized_effects':['local-settlement','legacy-backend-retirement'],'new_provider_requests':0,
        'state_root':str(facade.backend_admission.root),'owner':owner,'task_scope':_scope(request),'historical_identity':old,
        'implementation_identity':identity,'attestation_digest':digest_json(att),'review_binding':bound(review),'plan_binding':bound(plan)})
    return facade,att_path,auth


def test_unit_original_owner_legacy_retirement_is_atomic_durable_and_cannot_reacquire(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path);backend=facade.backend_admission
    before=read_run_budget_state(_ledger(facade));task=facade.task_store.read()
    receipt=backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert receipt['schema_version']=='DshLegacySerialBackendReleaseV1'
    assert backend.read_persisted(backend.root,backend.resource_key)['state']=='empty'
    assert backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)==receipt
    assert read_run_budget_state(_ledger(facade))==before and facade.task_store.read()==task
    assert task['state']=='cancelled' and task['receipt'] is None and task['provider_quiescence'] is None
    with pytest.raises(ProtocolError,match='backend_owner_retired'):
        backend.acquire(execution_id=facade.context.scope.execution_id,run_root=facade.store.root)
    another=backend.acquire(execution_id='execution:UNIT-another',run_root=tmp_path/'another')
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):
        backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert backend.read_persisted(backend.root,backend.resource_key)['owner']==another


def test_unit_legacy_retirement_refuses_pending_original_fees_without_mutating_owner(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path,settle=False);backend=facade.backend_admission
    before=backend.read_persisted(backend.root,backend.resource_key)
    with pytest.raises(ProtocolError,match='backend_release_accounting_unsettled'):
        backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert backend.read_persisted(backend.root,backend.resource_key)==before


def test_unit_legacy_retirement_does_not_invent_missing_original_usage(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path,settle=False,observe_usage=False);backend=facade.backend_admission
    before=backend.read_persisted(backend.root,backend.resource_key);budget=read_run_budget_state(_ledger(facade))
    with pytest.raises(ProtocolError,match='backend_release_accounting_unsettled'):
        backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert backend.read_persisted(backend.root,backend.resource_key)==before
    assert read_run_budget_state(_ledger(facade))==budget


@pytest.mark.parametrize('damage',['missing_done','after_done','wrong_usage','wrong_model','wrong_tool','after_finish'])
def test_legacy_transport_parser_keeps_incomplete_or_misbound_streams_closed(damage):
    args,usage,sse,session=_transport('UNIT-model','UNIT-session')
    if damage=='missing_done':sse=sse.replace(b'data: [DONE]\n\n',b'')
    if damage=='after_done':sse+=b'data: {}\n\n'
    if damage=='wrong_usage':sse=sse.replace(b'"total_tokens":43',b'"total_tokens":42')
    if damage=='wrong_model':sse=sse.replace(b'UNIT-model',b'UNIT-other',1)
    if damage=='after_finish':
        extra={'id':'unit:response','model':'UNIT-model','choices':[{'index':0,'delta':{'content':'UNIT late content'}}]}
        sse=sse.replace(b'data: [DONE]',b'data: '+canonical_json_bytes(extra)+b'\n\ndata: [DONE]')
    if damage=='wrong_tool':
        first,separator,rest=sse.partition(b'\n\n');event=json.loads(first[6:])
        event['choices'][0]['delta']['tool_calls'][0]['index']=1
        sse=b'data: '+canonical_json_bytes(event)+separator+rest
    with pytest.raises(ProtocolError):verify_stream(sse,'UNIT-model')


def test_legacy_error_attempt_is_distinct_from_natural_completion_and_preserves_argument_bytes():
    args,usage,sse,session=_transport('UNIT-model','UNIT-session')
    actual,call_id,name,counts=verify_stream(sse,'UNIT-model');assert actual==args and counts==usage
    def check(raw=session,identity='UNIT-session',arguments=actual,reserved=41):
        verify_session(raw,identity,arguments,call_id,name,counts,reserved_input_tokens=reserved)
    check()
    with pytest.raises(ProtocolError):check(identity='UNIT-other')
    with pytest.raises(ProtocolError):check(arguments=actual+b'}')
    with pytest.raises(ProtocolError):check(raw=session.replace(b'PI_AI_ERROR',b'UNIT_OTHER'))
    with pytest.raises(ProtocolError):check(raw=session.replace(b'40 !== 41',b'other nonempty error'))
    with pytest.raises(ProtocolError):check(reserved=42)
    rows=[json.loads(line) for line in session.splitlines()]
    rows[3]['data']['stream'].insert(2,{'type':'chunk','chunk':{'type':'block-end','index':0,'block':{'type':'tool-call'}}})
    with pytest.raises(ProtocolError):check(raw=b''.join(canonical_json_bytes(row)+b'\n' for row in rows))


def test_unit_operator_grant_is_scope_and_effect_bound_without_releasing(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path);backend=facade.backend_admission
    original=auth.read_bytes();value=json.loads(original);before=backend.read_persisted(backend.root,backend.resource_key)
    for patch in ({'approved':False},{'authorized_effects':['local-settlement']},
                  {'purpose':'live-only'},{'new_provider_requests':1},
                  {'attestation_digest':'sha256:'+'0'*64}):
        auth.write_bytes(canonical_json_bytes({**value,**patch}))
        with pytest.raises(ProtocolError,match='backend_legacy_authorization_required'):
            backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
        assert backend.read_persisted(backend.root,backend.resource_key)==before
    auth.write_bytes(original)


@pytest.mark.parametrize('damage',['wrong_key','different_binding','unknown_normal_field'])
def test_unit_history_corruption_refuses_replay_and_reacquire(recovery_kernel,tmp_path,damage):
    facade,att,auth=_package(recovery_kernel,tmp_path)
    backend=facade.backend_admission
    backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    with sqlite3.connect(backend.path) as db:
        key,raw=db.execute('SELECT release_key,receipt FROM release_history').fetchone()
        value=json.loads(raw)
        if damage=='wrong_key':
            db.execute('UPDATE release_history SET release_key=?',('sha256:'+'0'*64,))
        elif damage=='different_binding':
            value['attestation_digest']='sha256:'+'0'*64
            value['receipt_digest']=digest_json({k:v for k,v in value.items() if k!='receipt_digest'})
            db.execute('UPDATE release_history SET receipt=?',(canonical_json_bytes(value),))
        else:
            value={'schema_version':'DshSerialBackendReleaseV1','owner':value['owner'],
                'task_scope':value['task_scope'],'quiescence_ref':{},'task_state':'cancelled',
                'task_view_digest':value['task_view_digest'],'budget_digest':value['budget_digest'],
                'released_at_ms':value['released_at_ms'],'unexpected':'UNIT corruption'}
            value['receipt_digest']=digest_json(value)
            db.execute('UPDATE release_history SET receipt=?',(canonical_json_bytes(value),))
    with pytest.raises(ProtocolError,match='backend_release_history_invalid'):
        backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    with pytest.raises(ProtocolError,match='backend_release_history_invalid'):
        backend.acquire(execution_id=facade.context.scope.execution_id,run_root=facade.store.root)
    assert backend.read_persisted(backend.root,backend.resource_key)['state']=='empty'


def test_unit_sealed_execution_file_drift_refuses_before_mutation(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path)
    authorization=json.loads(auth.read_bytes())
    plan=json.loads(Path(authorization['plan_binding']['path']).read_bytes())
    Path(plan['execution_files']['entry_point']['path']).write_bytes(b'UNIT changed executable')
    before=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)
    with pytest.raises(ProtocolError):
        facade.backend_admission.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)==before


def test_unit_historical_bootstrap_and_child_are_cross_bound(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path)
    package=json.loads(att.read_bytes())
    raw={k:Path(v['path']).read_bytes() for k,v in package['files'].items()}
    task=facade.task_store.read()
    event=next(_ledger(facade).glob('*/attempt-0001.dsh-event-000001.json'))
    reserved=json.loads(event.read_bytes())['event']['reserved_input_tokens']
    verify_historical_transport(package,raw,task,reserved_input_tokens=reserved)
    bootstrap=json.loads(raw['bootstrap'])
    bootstrap['scope']={**bootstrap['scope'],'task_id':'task:UNIT-other'}
    with pytest.raises(ProtocolError):
        verify_historical_transport(package,{**raw,'bootstrap':canonical_json_bytes(bootstrap)},task,
                                    reserved_input_tokens=reserved)
    with pytest.raises(ProtocolError):
        verify_historical_transport(package,raw,{**task,'binding':{**task['binding'],'child_id':'UNIT-other'}},
                                    reserved_input_tokens=reserved)
    before=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)
    with sqlite3.connect(facade.store.root/'dsh-tasks.sqlite3') as db:
        lineage=list(task['claim_lineage']);lineage[0]='sha256:'+'0'*64
        db.execute('UPDATE tasks SET claim_lineage=?',(canonical_json_bytes(lineage),))
    with pytest.raises(ProtocolError):
        facade.backend_admission.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)==before


def test_unit_execution_tree_members_and_mount_projection_rechecked_before_retirement(recovery_kernel,tmp_path):
    facade,att,auth=_package(recovery_kernel,tmp_path)
    authorization=json.loads(auth.read_bytes())
    plan=json.loads(Path(authorization['plan_binding']['path']).read_bytes())
    tree=json.loads(Path(plan['execution_files']['python_module_manifest']['path']).read_bytes())
    member=Path(tree['files'][0]['path']);original=member.read_bytes()
    backend=facade.backend_admission
    before=backend.read_persisted(backend.root,backend.resource_key)
    def refused():
        with pytest.raises(ProtocolError):
            backend.retire_legacy_observed_transport(engine_root=ROOT,attestation_path=att,authorization_path=auth)
        assert backend.read_persisted(backend.root,backend.resource_key)==before
    member.write_bytes(b'UNIT changed overlay member');refused();member.write_bytes(original)
    extra=member.parent/'extra.txt';extra.write_bytes(b'UNIT unsealed extra');refused();extra.unlink()
    member.unlink();refused();member.write_bytes(original)
    # Isolate command projection validation from authorization/self-digest gates.
    from code2paper.integrations.dsh.legacy_retirement import verify_execution_mounts
    verify_execution_mounts(plan)
    command=list(plan['commands']['settlement']);command[command.index('--ro-bind')]='--bind'
    with pytest.raises(ProtocolError):
        verify_execution_mounts({**plan,'commands':{**plan['commands'],'settlement':command}})

    for flag in ('--bind','--ro-bind','--ro-bind-try','--dev-bind'):
        command=list(plan['commands']['settlement']);index=command.index('--')
        command[index:index]=[flag,str(member),str(Path(tree['mount_target'])/'unsealed-child.py')]
        with pytest.raises(ProtocolError):
            verify_execution_mounts({**plan,'commands':{**plan['commands'],'settlement':command}})
    command=list(plan['commands']['settlement']);index=command.index('--')
    command[index:index]=['--tmpfs',str(Path(tree['mount_target'])/'unsealed-dir')]
    with pytest.raises(ProtocolError):
        verify_execution_mounts({**plan,'commands':{**plan['commands'],'settlement':command}})


def test_unit_original_whitelist_allows_only_transport_metadata_not_model_material(recovery_kernel,tmp_path):
    from code2paper.integrations.dsh.legacy_retirement import verify_reserved_request_material
    facade,att,auth=_package(recovery_kernel,tmp_path)
    package=json.loads(att.read_bytes());calibration=json.loads(Path(package['files']['calibration']['path']).read_bytes())
    contract=facade.store.read_json(ArtifactRefV1.model_validate(facade.task_store.read()['prepared']['contract_ref']))
    wire=Path(package['files']['wire']['path']).read_bytes();loop=calibration['loop']
    actual=deepcopy(loop);actual.pop('sessionId',None)
    for index,message in enumerate(actual['messages']):message['id']='UNIT actual child message '+str(index)
    ref=facade.store.put_json(actual)
    # This fixture initially freezes no message-id exemption: it must refuse.
    with pytest.raises(ProtocolError):
        verify_reserved_request_material(facade.store,contract,ref,ref.semantic_digest,loop,wire)
    # Construct a separately scoped UNIT projection with an explicit exemption,
    # as the historical native renderer did. No TaskStore contract is changed.
    projection=facade.store.read_json(ArtifactRefV1.model_validate(contract['dsh_wire_contract_ref']))
    equivalence=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    equivalence['transport_whitelist']=['request.signal','request.sessionId','messages.id','messages.createdAt']
    projection['wire_equivalence_ref']=facade.store.put_json(equivalence).model_dump(mode='json')
    projection['projection_digest']=digest_json({k:v for k,v in projection.items() if k!='projection_digest'})
    contract={**contract,'dsh_wire_contract_ref':facade.store.put_json(projection).model_dump(mode='json')}
    verify_reserved_request_material(facade.store,contract,ref,ref.semantic_digest,loop,wire)
    for key in ('messages','tools','temperature'):
        changed=deepcopy(actual)
        if key=='messages':changed['messages'][0]['content'][0]['text']+=' UNIT model text changed'
        elif key=='tools':changed['tools']=[]
        else:changed['temperature']=0.123
        ref=facade.store.put_json(changed)
        with pytest.raises(ProtocolError):
            verify_reserved_request_material(facade.store,contract,ref,ref.semantic_digest,loop,wire)
