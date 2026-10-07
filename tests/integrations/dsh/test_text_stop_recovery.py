"""UNIT operator recovery on real Worker/ledger/admission fixtures.

All transport/review/grant rows here are explicitly synthetic, never canonical
approval. The real packet11 is verified separately read-only and by independent QA.
"""
import json
import sqlite3
from pathlib import Path
import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events,read_run_budget_state
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.text_stop_recovery import OPERATION,EFFECTS,verify_original,recover_text_stop
from code2paper.integrations.dsh.suite_runner import _identity
from .test_host_recovery_boundaries import recovery_kernel,_ledger
from .test_native_rejection_retirement import _package as native_package
from .test_text_stop_transport_proof import frames,encode,session,session_bytes
from .test_composition_identity import composition
from .stage04_support import ROOT


def package(kernel,tmp_path):
    facade,old,_,_=native_package(kernel,tmp_path)
    ledger=_ledger(facade)
    for p in ledger.glob('*/attempt-0001.dsh-event-*.json'):
        if int(p.name.split('dsh-event-')[1].split('.')[0])>=6:p.unlink()
    with sqlite3.connect(facade.task_store.path) as db:db.execute('UPDATE tasks SET captured_source=NULL')
    task=facade.task_store.read();inv=old['request_id'];prefix=read_dsh_invocation_events(ledger,inv)
    assert [f.kind for f in prefix]==['reserve','dispatch-recorded','adapter-attempt','usage','cancel']
    out=tmp_path/'text-stop-recovery';out.mkdir()
    def bound(p):
        b=p.read_bytes();return {'path':str(p),'bytes_digest':digest_bytes(b),'byte_length':len(b)}
    def write(name,value):
        p=out/name;p.write_bytes(value if isinstance(value,bytes) else canonical_json_bytes(value));return p
    files={k:v for k,v in old['files'].items() if k not in {'packet','grant','original_plan','sse','provider','session'}}
    wire=json.loads(Path(files['wire']['path']).read_bytes());model=wire['model'];usage={'prompt_tokens':40,'completion_tokens':3,'total_tokens':43}
    es=frames()
    for e in es:e['model']=model
    es[-1]['usage']=usage
    text=es[2]['choices'][0]['delta']['content'];reasoning=es[1]['choices'][0]['delta']['reasoning']
    rows,error=session(text,reasoning,usage);rows[0]['id']=task['binding']['session_id']
    actual=json.loads(Path(files['calibration']['path']).read_bytes())['loop'];config={k:actual[k] for k in
        ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
    for row in rows[3:]:row['seq']+=2
    rows[3:3]=[{'seq':3,'type':'request/header','data':{'header':{'config':config,'tools':actual['tools']}}},
        {'seq':4,'type':'request/context','data':{'provider':actual.get('provider'),'model':actual['model']}}]
    files['sse']=bound(write('response.sse',encode(es)));files['session']=bound(write('session.jsonl',session_bytes(rows)))
    files['provider']=bound(write('provider.json',{'http_status':200,'usage':usage,'finish_reasons':['stop']}))
    files['calibration']=bound(write('calibration.json',{'loop':actual,'actual_provider_body':files['wire'],'calibration_sends':1}))
    files['failure']=bound(write('failure.json',{'message':error,'request_counts':{'primary':1,'isolated_offline':0,'tokenize':1,'auxiliary':0},'cleanup_failures':[]}))
    files['cleanup']=bound(write('cleanup.json',{'worker_scope_quiescent':True,'errors':[],
        'sentinel':{'state':'closed','probe_refused':True,'model_calls':0,'network_calls':0}}))
    files['launch']=bound(write('launch.json',{'mode':'live','inference_authorized':True}))
    files['started']=bound(write('started.json',{'inference_requests':0}))
    files['packet']=bound(write('packet.json',{'engine_digest':old['historical_identity']['engine_digest'],
        'frozen_files':[files[k] for k in ('producer','bootstrap','descriptor','wire','calibration')]}))
    files['original_plan']=bound(write('original-plan.json',{'packet_digest':files['packet']['bytes_digest']}))
    files['grant']=bound(write('grant.json',{'schema_version':'L01ExplicitUserGrantRecordV1','packet_digest':files['packet']['bytes_digest'],
        'execution_plan_digest':files['original_plan']['bytes_digest'],'authorization':{'approved':True,'primary_requests':1,'retries':0,
        'packet_digest':files['packet']['bytes_digest'],'model':model,'input_token_cap':32768,'max_output_tokens':wire['max_tokens'],'wall_seconds':180},
        'additional_authorized_scope':'UNIT observed fees settlement and normal-finish release grant fixture'}))
    grant=json.loads(Path(files['grant']['path']).read_bytes())
    original_auth=bound(write('original-authorization.json',grant['authorization']))
    files['started']=bound(write('started.json',{'authorization':original_auth,'tokenizer':files['tokenizer']}))
    files['launch']=bound(write('launch.json',{'mode':'live','inference_authorized':True,'output':str(out)}))
    att={'schema_version':'DshTextStopRecoveryAttestationV1',**{k:old[k] for k in ('owner','state_root','task_scope','historical_identity')},
        'task_view_digest':digest_json(task),'task_db':bound(facade.task_store.path),'original_ledger':[f.model_dump(mode='json') for f in prefix],
        'ledger_digest':digest_json([f.model_dump(mode='json') for f in prefix]),'original_budget':read_run_budget_state(ledger),'files':files}
    ap=write('attestation.json',att);pp=out/'plan.json';rp=out/'review.json';auth=out/'authorization.json'
    snapshot,validator=_identity(ROOT);identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    plan={'schema_version':'DshTextStopRecoveryPlanV1','operation':OPERATION,'attestation':bound(ap),'implementation_identity':identity,
        'command':['python','-m','code2paper.integrations.dsh.text_stop_recovery','--engine-root',str(ROOT),'--plan',str(pp),
            '--review',str(rp),'--authorization',str(auth)],'new_provider_requests':0,'authorized_effects':EFFECTS};write('plan.json',plan)
    write('review.json',{'schema_version':'DshTextStopRecoveryReviewV1','decision':'PASS','operation':OPERATION,
        'plan_digest':bound(pp)['bytes_digest'],'attestation_digest':bound(ap)['bytes_digest'],'implementation_identity':identity,
        'producer_digest':files['producer']['bytes_digest'],'producer_protocol':'fetch-reader-done/archive-before-error-v1'})
    write('authorization.json',{'schema_version':'DshTextStopRecoveryAuthorizationV1','approved':True,'operation':OPERATION,
        'plan_digest':bound(pp)['bytes_digest'],'review_digest':bound(rp)['bytes_digest'],'grant_digest':files['grant']['bytes_digest'],
        'owner':att['owner'],'task_scope':att['task_scope'],'authorized_effects':EFFECTS,'new_provider_requests':0})
    return facade,att,{k:Path(v['path']).read_bytes() for k,v in files.items()},dict(engine_root=ROOT,plan_path=pp,review_path=rp,authorization_path=auth)


def test_original_observed_fees_retire_once_without_changing_task_or_domain(recovery_kernel,tmp_path):
    facade,att,_,kwargs=package(recovery_kernel,tmp_path);task=facade.task_store.read();db_bytes=facade.task_store.path.read_bytes()
    r=recover_text_stop(facade.backend_admission,**kwargs)
    assert r['operation']==OPERATION and r['schema_version']=='DshTextStopBackendReleaseV1'
    assert recover_text_stop(facade.backend_admission,**kwargs)==r
    assert facade.task_store.read()==task and facade.task_store.path.read_bytes()==db_bytes
    assert task['captured_source'] is task['receipt'] is task['provider_quiescence'] is None
    budget=read_run_budget_state(_ledger(facade));assert budget['spent_input_tokens']==40 and budget['pending_input_tokens']==0
    other=tmp_path/'other';other.mkdir();new=facade.backend_admission.acquire(execution_id='execution:new',run_root=other)
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):recover_text_stop(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']==new


@pytest.mark.parametrize('damage',['scope','resource','ledger','grant','grant_bool','tokenizer','session','sse','task','history','review','authorization','started','launch'])
def test_wrong_original_authority_or_transport_has_no_fee_or_owner_effect(recovery_kernel,tmp_path,damage):
    facade,att,raw,kwargs=package(recovery_kernel,tmp_path);before=read_run_budget_state(_ledger(facade));owner=att['owner']
    if damage=='scope':att['task_scope']['task_epoch']+=1
    elif damage=='resource':att['owner']['resource_key']='other'
    elif damage=='ledger':att['ledger_digest']='sha256:'+'0'*64
    elif damage=='grant':z=json.loads(raw['grant']);z['additional_authorized_scope']='none';raw['grant']=canonical_json_bytes(z)
    elif damage=='grant_bool':z=json.loads(raw['grant']);z['authorization']['primary_requests']=True;raw['grant']=canonical_json_bytes(z)
    elif damage=='tokenizer':z=json.loads(raw['tokenizer']);z['input_tokens']=0;raw['tokenizer']=canonical_json_bytes(z)
    elif damage=='session':raw['session']=raw['session'].replace(b'PI_AI_ERROR',b'OTHER_ERROR')
    elif damage=='sse':raw['sse']=raw['sse'].replace(b'"stop"',b'"length"')
    elif damage=='started':raw['started']=canonical_json_bytes({'authorization':{},'tokenizer':att['files']['tokenizer']})
    elif damage=='launch':z=json.loads(raw['launch']);z['mode']='offline';raw['launch']=canonical_json_bytes(z)
    elif damage=='task':att['task_view_digest']='sha256:'+'0'*64
    elif damage=='history':
        with facade.backend_admission._transaction() as db:
            db.execute('CREATE TABLE release_history (release_key TEXT PRIMARY KEY,receipt BLOB NOT NULL)');db.execute('INSERT INTO release_history VALUES (?,?)',('bad',b'{}'))
    elif damage=='review':kwargs['review_path'].write_bytes(b'{}')
    elif damage=='authorization':kwargs['authorization_path'].write_bytes(b'{}')
    with pytest.raises(ProtocolError):
        if damage in {'history','review','authorization'}:recover_text_stop(facade.backend_admission,**kwargs)
        else:verify_original(facade.backend_admission,att,raw)
    assert read_run_budget_state(_ledger(facade))==before
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']['execution_id']==owner['execution_id']


@pytest.mark.parametrize('cut',['terminal','settlement','history_delete'])
def test_crash_cuts_resume_original_fees_without_double_settlement(recovery_kernel,tmp_path,monkeypatch,cut):
    import code2paper.integrations.dsh.text_stop_recovery as mod
    facade,att,_,kwargs=package(recovery_kernel,tmp_path);original=mod.publish_dsh_invocation_event;done=False
    def fail_after(root,event):
        nonlocal done
        result=original(root,event)
        if not done and event.kind==cut:done=True;raise RuntimeError('UNIT process cut after immutable event')
        return result
    if cut!='history_delete':monkeypatch.setattr(mod,'publish_dsh_invocation_event',fail_after)
    else:
        with facade.backend_admission._transaction() as db:db.execute("CREATE TRIGGER unit_cut BEFORE DELETE ON admission BEGIN SELECT RAISE(ABORT,'UNIT history/delete cut'); END")
    with pytest.raises((RuntimeError,sqlite3.DatabaseError)):recover_text_stop(facade.backend_admission,**kwargs)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    monkeypatch.setattr(mod,'publish_dsh_invocation_event',original)
    if cut=='history_delete':
        with facade.backend_admission._transaction() as db:db.execute('DROP TRIGGER unit_cut')
    receipt=recover_text_stop(facade.backend_admission,**kwargs);assert recover_text_stop(facade.backend_admission,**kwargs)==receipt
    budget=read_run_budget_state(_ledger(facade));assert budget['spent_input_tokens']==40 and budget['pending_input_tokens']==0
