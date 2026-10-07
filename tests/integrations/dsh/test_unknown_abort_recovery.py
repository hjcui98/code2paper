"""Proposed operator contract, using explicit UNIT stop/grant fixtures only.

The real packet14 protected-copy rehearsal is separate. These fixtures do not
authorize a service stop, canonical migration, or new inference.
"""
import json
import sqlite3
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.unified_invocation_ledger import (
    read_dsh_invocation_events,read_run_budget_state,publish_dsh_invocation_event,check_run_budget_before_send,
)
from code2paper.agentic.unified_context_models import DshInvocationEventV1
from code2paper.integrations.dsh.unknown_abort_recovery import (
    OPERATION,EFFECTS,POLICY,MARKER,_seal,_bound,retire_unknown_abort,validate_termination,
)
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.suite_runner import _identity
from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
from .test_host_recovery_boundaries import recovery_kernel,_ledger,_result,_enter,_scope
from .test_composition_identity import composition
from .stage04_support import ROOT


def package(kernel,tmp_path):
    child,facade,_,claim,request,_=kernel
    reservation=_result(child.call('request.reserve',request));_enter(child,request,reservation)
    ledger=_ledger(facade);reserve=read_dsh_invocation_events(ledger,reservation['request_id'])[0]
    def historical(kind,evidence,**extra):
        fields=reserve.model_dump(mode='json')
        fields.update(kind=kind,event_id='UNIT:old:'+kind,source='host-adapter',reserved_input_tokens=0,
            reserved_output_tokens=0,evidence_ref=evidence.model_dump(mode='json'),content_digest='',**extra)
        return publish_dsh_invocation_event(ledger,DshInvocationEventV1(**fields))
    # Explicitly reproduce the old publisher's default-zero facts. The current
    # private RPC refuses them and is tested independently.
    usage=facade.store.put_json({'schema_version':'DshAdapterUsageV1','request_digest':reserve.request_digest,
        'input_tokens':0,'output_tokens':0,'source':'adapter-usage'})
    historical('usage',usage,usage_input_tokens=0,usage_output_tokens=0)
    _result(child.call('task.cancel',{**_scope(request),'claim':claim}))
    evidence=facade.store.put_json({'schema_version':'UNIT historical erroneous finish'})
    historical('terminal',evidence);historical('settlement',evidence)
    task=facade.task_store.read();child.close()
    facts=read_dsh_invocation_events(ledger,reserve.invocation_id)
    out=tmp_path/'abort-contract';out.mkdir()
    def write(name,value):
        p=out/name;p.write_bytes(value if isinstance(value,bytes) else canonical_json_bytes(value));return p
    owner=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']
    contract=facade.store.read_json(ArtifactRefV1.model_validate(task['prepared']['contract_ref']))
    projection=facade.store.read_json(ArtifactRefV1.model_validate(contract['dsh_wire_contract_ref']))
    eq=facade.store.read_json(ArtifactRefV1.model_validate(projection['wire_equivalence_ref']))
    wire=facade.store.read(ArtifactRefV1.model_validate(eq['provider_wire_ref']))
    loop=facade.store.read_json(ArtifactRefV1.model_validate(eq['loop_request_ref']))
    files={'bootstrap':_bound(kernel[5]),'descriptor':_bound(write('descriptor.json',{'scope':facade.store.scope.__dict__}))}
    files['wire']=_bound(write('wire.json',wire));files['calibration']=_bound(write('calibration.json',{'loop':loop}))
    rows=[{'type':'session','version':4,'id':task['binding']['session_id']},
          {'seq':1,'type':'turn/end','data':{'reason':{'kind':'error','error':{'code':'PI_AI_ERROR'}}}}]
    files['session']=_bound(write('session.jsonl',b''.join(canonical_json_bytes(r)+b'\n' for r in rows)))
    frames=[{'id':'UNIT:provider-request','choices':[{'index':0,'delta':{'reasoning':'partial'},'finish_reason':None}]},
            {'error':{'type':'InternalServerError','message':'UNIT server error','code':500}}]
    files['sse']=_bound(write('response.sse',b''.join(b'data: '+canonical_json_bytes(r)+b'\n\n' for r in frames)+b'data: [DONE]\n\n'))
    packet={'scope':'UNIT historical execution scope','profile':{'input_token_cap':32768,'max_output_tokens':4096},'frozen_files':[files[k] for k in ('bootstrap','descriptor','wire','calibration')]}
    files['packet']=_bound(write('packet.json',packet))
    processes=[{'pid':1,'start_ticks':10,'pgrp':1}];epoch=digest_json({'UNIT:server-processes':processes})
    att=_seal({'schema_version':'DshUnknownAbortHistoricalAttestationV1','owner':owner,'state_root':str(facade.backend_admission.root),
        'resource_key':owner['resource_key'],'task_scope':facade.store.scope.__dict__,'request_id':reserve.invocation_id,
        'provider_request_id':'UNIT:provider-request','request_digest':reserve.request_digest,'session_id':task['binding']['session_id'],
        'task_view_digest':digest_json(task),'ledger_digest':digest_json([f.model_dump(mode='json') for f in facts]),
        'history_digest':digest_json([]),'input_cap':32768,'output_cap':4096,'server_epoch_digest':epoch,
        'server_processes':processes,'gpu_uuid':'UNIT:gpu','files':files,'frozen_inputs':packet['frozen_files']})
    stop_auth={'schema_version':'DshServiceEpochStopAuthorizationV1','approved':True,'issuer':'UNIT service owner',
        'server_epoch_digest':epoch,'affected_processes':processes,'gpu_uuid':'UNIT:gpu','affected_service':owner['resource_key'],
        'acknowledged_all_service_clients_interrupted':True}
    stop_path=write('stop-authorization.json',stop_auth)
    stop={'schema_version':'DshServiceEpochStopEvidenceV1','server_epoch_digest':epoch,'affected_processes':processes,
        'affected_gpu_uuid':'UNIT:gpu','remaining_epoch_processes':[],'remaining_epoch_gpu_contexts':[],
        'old_listener_present':False,'service_owner_identity':'UNIT service owner',
        'stop_operation_authorization_digest':digest_json(stop_auth),'stop_authorization':_bound(stop_path)}
    stop_evidence=write('stop-evidence.json',stop)
    confirmation=_seal({'schema_version':'DshServiceOwnerTerminationConfirmationV1','authority':'service-owner-confirmed-full-epoch-stop/1',
        'issuer':'UNIT service owner','subject':{k:att[k] for k in ('owner','task_scope','request_id','provider_request_id','request_digest','session_id')},
        'server_epoch_digest':epoch,'server_evidence':_bound(stop_evidence),'admission_closed':True,
        'whole_epoch_stopped':True,'gpu_execution_drained':True,'confirmed_at_ms':1})
    att_path=write('attestation.json',att);term_path=write('termination.json',confirmation)
    e,v=_identity(ROOT);identity={'engine_digest':e.source_digest,'validator_digest':v.digest}
    pp=out/'plan.json';rp=out/'review.json';ap=out/'authorization.json'
    plan={'schema_version':'DshUnknownAbortRetirementPlanV1','operation':OPERATION,'attestation':_bound(att_path),
        'termination':_bound(term_path),'implementation_identity':identity,'authorized_effects':EFFECTS,'budget_policy':POLICY,
        'new_provider_requests':0,'isolation_parent_namespace':None,'command':['python','-m','code2paper.integrations.dsh.unknown_abort_recovery','--engine-root',str(ROOT),
            '--plan',str(pp),'--review',str(rp),'--authorization',str(ap)]}
    write('plan.json',plan)
    review={'schema_version':'DshUnknownAbortRetirementReviewV1','decision':'PASS','operation':OPERATION,
        'plan_digest':_bound(pp)['bytes_digest'],'attestation_digest':_bound(att_path)['bytes_digest'],
        'termination_digest':_bound(term_path)['bytes_digest'],'implementation_identity':identity,
        'budget_policy':POLICY,'authorized_effects':EFFECTS}
    write('review.json',review)
    auth={'schema_version':'DshUnknownAbortRetirementAuthorizationV1','approved':True,'operation':OPERATION,
        'plan_digest':_bound(pp)['bytes_digest'],'review_digest':_bound(rp)['bytes_digest'],'termination_digest':_bound(term_path)['bytes_digest'],
        'owner':owner,'task_scope':facade.store.scope.__dict__,'budget_policy':POLICY,'authorized_effects':EFFECTS,'new_provider_requests':0}
    write('authorization.json',auth)
    return facade,att,confirmation,dict(engine_root=ROOT,plan_path=pp,review_path=rp,authorization_path=ap)


def test_unknown_fee_retirement_keeps_original_facts_and_quarantines_old_run(recovery_kernel,tmp_path):
    facade,att,_,args=package(recovery_kernel,tmp_path);before=read_dsh_invocation_events(_ledger(facade),att['request_id']);task=facade.task_store.read()
    receipt=retire_unknown_abort(facade.backend_admission,**args)
    state=read_run_budget_state(_ledger(facade))
    assert state['provider_usage_status']=='partial' and state['pending_input_tokens']==32768
    assert state['spent_input_tokens']==0 and state['pending_call_count']==1 and state['completed_call_count']==0
    assert read_dsh_invocation_events(_ledger(facade),att['request_id'])==before and facade.task_store.read()==task
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='empty'
    assert retire_unknown_abort(facade.backend_admission,**args)==receipt
    from types import SimpleNamespace
    errors=check_run_budget_before_send(_ledger(facade),SimpleNamespace(max_calls_by_role={'writer':4},max_input_tokens_by_role={'writer':65536},max_total_input_tokens=65536),role='writer',request_input_tokens=1)
    assert 'unified_run_quarantined:unknown_provider_usage' in errors
    facade.backend_admission.acquire(execution_id='new-execution',run_root=tmp_path/'new-run')
    new=facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)
    assert retire_unknown_abort(facade.backend_admission,**args)==receipt
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)==new
    with pytest.raises(ProtocolError,match='backend_owner_retired'):
        facade.backend_admission.acquire(execution_id=facade.store.scope.execution_id,run_root=facade.store.root)


@pytest.mark.parametrize('cut',['disposition-durable','history-inserted','owner-deleted'])
def test_abort_retirement_cut_is_held_until_atomic_resume(recovery_kernel,tmp_path,cut):
    facade,att,_,args=package(recovery_kernel,tmp_path)
    def crash(step):
        if step==cut:raise RuntimeError('UNIT cut')
    with pytest.raises(RuntimeError,match='UNIT cut'):retire_unknown_abort(facade.backend_admission,**args,_cut=crash)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    assert read_run_budget_state(_ledger(facade))['pending_input_tokens']==32768
    retire_unknown_abort(facade.backend_admission,**args)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='empty'


@pytest.mark.parametrize('field',['server_epoch_digest','admission_closed','whole_epoch_stopped','gpu_execution_drained','subject'])
def test_missing_or_wrong_termination_never_authorizes_retirement(recovery_kernel,tmp_path,field):
    facade,att,term,args=package(recovery_kernel,tmp_path)
    term[field]=False if field!='server_epoch_digest' else digest_json('old epoch')
    term=_seal({k:v for k,v in term.items() if k!='content_digest'})
    with pytest.raises(ProtocolError):validate_termination(term,att)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    assert not list(_ledger(facade).glob('*/'+MARKER))


def test_normal_finish_authorization_cannot_authorize_unknown_abort(recovery_kernel,tmp_path):
    facade,_,_,args=package(recovery_kernel,tmp_path)
    args['authorization_path'].write_bytes(canonical_json_bytes({'schema_version':'L01OperatorAuthorizationV1','approved':True,'primary_requests':1}))
    with pytest.raises(ProtocolError,match='backend_unknown_abort_authorization_required'):
        retire_unknown_abort(facade.backend_admission,**args)
    assert not list(_ledger(facade).glob('*/'+MARKER))


def test_foreign_owner_is_preserved_without_a_disposition_write(recovery_kernel,tmp_path):
    facade,att,_,args=package(recovery_kernel,tmp_path)
    foreign={**att['owner'],'execution_id':'UNIT:foreign-owner','run_root':str(tmp_path/'foreign')}
    with sqlite3.connect(facade.backend_admission.path) as db:
        db.execute('UPDATE admission SET owner=? WHERE resource=?',
            (canonical_json_bytes(foreign),facade.backend_admission.resource_key))
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):
        retire_unknown_abort(facade.backend_admission,**args)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['owner']==foreign
    assert not list(_ledger(facade).glob('*/'+MARKER))


def test_damaged_unknown_disposition_blocks_budget_and_future_admission(recovery_kernel,tmp_path):
    facade,_,_,args=package(recovery_kernel,tmp_path)
    retire_unknown_abort(facade.backend_admission,**args)
    marker=next(_ledger(facade).glob('*/'+MARKER));marker.write_bytes(b'{"actual_usage":"settled"}')
    assert read_run_budget_state(_ledger(facade))['status']=='fail'
    with pytest.raises(ProtocolError):
        facade.backend_admission.acquire(execution_id='UNIT:new-owner',run_root=tmp_path/'new')


@pytest.mark.parametrize('field,bad',[
    ('implementation_identity',None),('implementation_identity',{'engine_digest':'sha256:'+'0'*64,'validator_digest':'sha256:'+'1'*64}),
    ('task_view_digest',None),('task_view_digest','sha256:'+'0'*64),('budget_digest',None),('budget_digest','sha256:'+'0'*64),
    ('ledger_digest',None),('plan_digest','invalid'),('released_at_ms',True),
    ('owner',None),('task_scope',None),
])
def test_resealed_abort_history_rejects_unbound_metadata(recovery_kernel,tmp_path,field,bad):
    from code2paper.integrations.dsh.unknown_abort_recovery import BINDING_KEYS
    facade,_,_,args=package(recovery_kernel,tmp_path)
    receipt=retire_unknown_abort(facade.backend_admission,**args)
    valid_key=digest_json({k:receipt[k] for k in BINDING_KEYS})
    facade.backend_admission._release_binding(receipt,valid_key)
    changed={**receipt,field:bad}
    changed['receipt_digest']=digest_json({k:v for k,v in changed.items() if k!='receipt_digest'})
    key=digest_json({k:changed[k] for k in BINDING_KEYS})
    with pytest.raises(ProtocolError):facade.backend_admission._release_binding(changed,key)


@pytest.mark.parametrize('field,bad',[
    ('approved',1),('task_scope',{'task_epoch':False}),('new_provider_requests',False),
])
def test_type_changed_operator_authorization_refused_before_effects(recovery_kernel,tmp_path,field,bad):
    from code2paper.integrations.dsh.unknown_abort_recovery import verify_package
    facade,_,_,args=package(recovery_kernel,tmp_path)
    auth=json.loads(args['authorization_path'].read_bytes())
    auth[field]={**auth[field],**bad} if isinstance(bad,dict) else bad
    args['authorization_path'].write_bytes(canonical_json_bytes(auth))
    with pytest.raises(ProtocolError,match='backend_unknown_abort_authorization_required'):
        verify_package(**args)
    with pytest.raises(ProtocolError):retire_unknown_abort(facade.backend_admission,**args)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    assert not list(_ledger(facade).glob('*/'+MARKER))


@pytest.mark.parametrize('field',['subject','historical_scope','stop_evidence_process','stop_authorization_process'])
def test_resealed_termination_rejects_nested_boolean_integer_alias(recovery_kernel,tmp_path,field):
    from copy import deepcopy
    facade,att,term,_=package(recovery_kernel,tmp_path)
    att=deepcopy(att);term=deepcopy(term)
    if field in ('subject','historical_scope'):
        term['subject']['task_scope']['task_epoch']=False
        if field=='historical_scope':
            att['task_scope']['task_epoch']=False
            att=_seal({k:v for k,v in att.items() if k!='content_digest'})
    else:
        ep=Path(term['server_evidence']['path']);evidence=json.loads(ep.read_bytes())
        if field=='stop_evidence_process':evidence['affected_processes'][0]['pid']=True
        else:
            ap=Path(evidence['stop_authorization']['path']);auth=json.loads(ap.read_bytes())
            auth['affected_processes'][0]['pid']=True
            ap.write_bytes(canonical_json_bytes(auth));evidence['stop_authorization']=_bound(ap)
            evidence['stop_operation_authorization_digest']=digest_json(auth)
        ep.write_bytes(canonical_json_bytes(evidence));term['server_evidence']=_bound(ep)
    term=_seal({k:v for k,v in term.items() if k!='content_digest'})
    with pytest.raises(ProtocolError):validate_termination(term,att)
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    assert not list(_ledger(facade).glob('*/'+MARKER))


@pytest.mark.parametrize('field,bad',[('approved',1),('task_scope',{'task_epoch':False})])
def test_resealed_disposition_rejects_type_changed_bound_authorization(recovery_kernel,tmp_path,field,bad):
    from code2paper.integrations.dsh.unknown_abort_recovery import validate_disposition
    facade,att,_,args=package(recovery_kernel,tmp_path)
    retire_unknown_abort(facade.backend_admission,**args)
    marker=json.loads(next(_ledger(facade).glob('*/'+MARKER)).read_bytes())
    auth=json.loads(args['authorization_path'].read_bytes())
    auth[field]={**auth[field],**bad} if isinstance(bad,dict) else bad
    args['authorization_path'].write_bytes(canonical_json_bytes(auth))
    marker['authorization']=_bound(args['authorization_path'])
    marker=_seal({k:v for k,v in marker.items() if k!='content_digest'})
    with pytest.raises(ProtocolError):
        validate_disposition(marker,read_dsh_invocation_events(_ledger(facade),att['request_id']))
    assert read_run_budget_state(_ledger(facade))['status']=='fail'
