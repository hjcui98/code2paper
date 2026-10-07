"""Operator-only terminated execution retirement with UNKNOWN fee retention.

This proposed contract needs a distinct reviewed authorization and a bound
service-owner termination confirmation. It cannot accept a normal-finish grant,
mint private execute provenance, settle provider usage, or restart a service.
The old run remains permanently quarantined with its full authorized input
liability retained in the original budget reader. Only then may its exact
physical permit be retired under the explicitly approved operator contract.
"""
from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import time

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from .legacy_retirement import read_bound, read_file, json_object
from .protocol import ProtocolError

OPERATION = 'terminated-provider-unknown-retirement/1'
EFFECTS = ['conservative-unknown-budget-hold', 'exact-terminated-owner-retirement', 'immutable-abort-history']
POLICY = 'retain-authorized-input-cap;unknown-not-provider-spend;old-run-no-resume/1'
MARKER = 'attempt-0001.dsh-unknown-disposition.json'
BINDING_KEYS = frozenset({'operation','owner','task_scope','plan_digest','review_digest','authorization_digest',
    'termination_digest','disposition','implementation_identity'})


def refuse(code='backend_unknown_abort_unproven'):
    raise ProtocolError(code)


def _sealed(value, schema, keys):
    if (not isinstance(value,dict) or set(value) != set(keys)|{'schema_version','content_digest'}
            or value['schema_version'] != schema
            or value['content_digest'] != digest_json({k:v for k,v in value.items() if k!='content_digest'})):
        refuse()
    return value


def _seal(value):
    return {**value,'content_digest':digest_json(value)}


def _digest(value):
    return isinstance(value,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',value) is not None


def _same_json(left, right):
    """Bind JSON values including their types; Python treats False == 0."""
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _implementation(value):
    return (isinstance(value,dict) and set(value)=={'engine_digest','validator_digest'}
        and all(_digest(v) for v in value.values()))


def _owner_scope(owner,scope):
    if (not isinstance(owner,dict) or set(owner)!={'schema_version','execution_id','run_root','resource_key'}
            or owner['schema_version']!='serial-backend-admission/1'
            or not all(isinstance(owner[k],str) and owner[k] for k in ('execution_id','run_root','resource_key'))
            or not Path(owner['run_root']).is_absolute()
            or str(Path(owner['run_root']).resolve())!=owner['run_root']
            or not isinstance(scope,dict) or set(scope)!={'execution_id','task_id','task_epoch'}
            or scope['execution_id']!=owner['execution_id']
            or not isinstance(scope['task_id'],str) or not scope['task_id']
            or type(scope['task_epoch']) is not int or scope['task_epoch']<0):
        refuse('backend_release_history_invalid')


def validate_termination(value, att):
    """Positive service-owner authority, never inferred from idle or an SSE log.

    The issuer and whole epoch evidence are reviewed and separately approved
    by digest. A fixture confirmation is valid only inside isolation; creating
    that fixture is not a service operation or real operator consent.
    """
    _owner_scope(att['owner'],att['task_scope'])
    _sealed(value,'DshServiceOwnerTerminationConfirmationV1',{
        'authority','issuer','subject','server_epoch_digest','server_evidence',
        'admission_closed','whole_epoch_stopped','gpu_execution_drained','confirmed_at_ms'})
    if (value['authority'] != 'service-owner-confirmed-full-epoch-stop/1'
            or not isinstance(value['issuer'],str) or not value['issuer']
            or not _same_json(value['subject'], {k:att[k] for k in ('owner','task_scope','request_id','provider_request_id','request_digest','session_id')})
            or value['server_epoch_digest'] != att['server_epoch_digest']
            or any(value[k] is not True for k in ('admission_closed','whole_epoch_stopped','gpu_execution_drained'))
            or type(value['confirmed_at_ms']) is not int or value['confirmed_at_ms'] <= 0):
        refuse('backend_unknown_abort_termination_required')
    evidence=json_object(read_bound(value['server_evidence']))
    if (evidence.get('schema_version') != 'DshServiceEpochStopEvidenceV1'
            or evidence.get('server_epoch_digest') != att['server_epoch_digest']
            or not _same_json(evidence.get('affected_processes'), att['server_processes'])
            or evidence.get('affected_gpu_uuid') != att['gpu_uuid']
            or evidence.get('remaining_epoch_processes') != []
            or evidence.get('remaining_epoch_gpu_contexts') != []
            or evidence.get('old_listener_present') is not False
            or evidence.get('service_owner_identity') != value['issuer']):
        refuse('backend_unknown_abort_termination_required')
    # Evidence is authoritative only when its producing stop operation and
    # closure (including shared-client impact) have independent review and
    # explicit service-owner authorization. The migration cannot fabricate it.
    stop_auth=json_object(read_bound(evidence.get('stop_authorization')))
    if (stop_auth.get('schema_version') != 'DshServiceEpochStopAuthorizationV1'
            or stop_auth.get('approved') is not True or stop_auth.get('issuer') != value['issuer']
            or stop_auth.get('server_epoch_digest') != att['server_epoch_digest']
            or not _same_json(stop_auth.get('affected_processes'), att['server_processes'])
            or stop_auth.get('gpu_uuid') != att['gpu_uuid']
            or stop_auth.get('affected_service') != att['resource_key']
            or stop_auth.get('acknowledged_all_service_clients_interrupted') is not True
            or digest_json(stop_auth) != evidence.get('stop_operation_authorization_digest')):
        refuse('backend_unknown_abort_termination_required')


def verify_package(engine_root, plan_path, review_path, authorization_path):
    from .suite_runner import _identity
    plan_raw=read_file(plan_path);plan=json_object(plan_raw)
    if (set(plan) != {'schema_version','operation','attestation','termination','implementation_identity',
            'command','authorized_effects','budget_policy','new_provider_requests','isolation_parent_namespace'}
            or plan['schema_version'] != 'DshUnknownAbortRetirementPlanV1'
            or plan['operation'] != OPERATION or plan['authorized_effects'] != EFFECTS
            or plan['budget_policy'] != POLICY or type(plan['new_provider_requests']) is not int
            or plan['new_provider_requests'] != 0):refuse()
    if plan['isolation_parent_namespace'] is not None:
        from .qualification import assert_offline_qualification_namespace
        assert_offline_qualification_namespace(plan['isolation_parent_namespace'])
    att_raw=read_bound(plan['attestation']);att=json_object(att_raw)
    _sealed(att,'DshUnknownAbortHistoricalAttestationV1',{'owner','state_root','resource_key','task_scope',
        'request_id','provider_request_id','request_digest','session_id','task_view_digest','ledger_digest','history_digest',
        'input_cap','output_cap','server_epoch_digest','server_processes','gpu_uuid','files','frozen_inputs'})
    termination_raw=read_bound(plan['termination']);termination=json_object(termination_raw)
    validate_termination(termination,att)
    e,v=_identity(Path(engine_root));identity={'engine_digest':e.source_digest,'validator_digest':v.digest}
    if e.unstable or not e.is_usable or not _same_json(identity, plan['implementation_identity']):
        refuse('backend_unknown_abort_identity_drift')
    command=['python','-m','code2paper.integrations.dsh.unknown_abort_recovery','--engine-root',
        str(Path(engine_root).resolve()),'--plan',str(plan_path),'--review',str(review_path),
        '--authorization',str(authorization_path)]
    if plan['command'] != command:refuse()
    review_raw=read_file(review_path);review=json_object(review_raw)
    expected_review={'schema_version':'DshUnknownAbortRetirementReviewV1','decision':'PASS','operation':OPERATION,
        'plan_digest':digest_bytes(plan_raw),'attestation_digest':digest_bytes(att_raw),
        'termination_digest':digest_bytes(termination_raw),'implementation_identity':identity,
        'budget_policy':POLICY,'authorized_effects':EFFECTS}
    if not _same_json(review, expected_review):refuse('backend_unknown_abort_review_required')
    auth_raw=read_file(authorization_path);auth=json_object(auth_raw)
    if not _same_json(auth, {'schema_version':'DshUnknownAbortRetirementAuthorizationV1','approved':True,'operation':OPERATION,
            'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),
            'termination_digest':digest_bytes(termination_raw),'owner':att['owner'],'task_scope':att['task_scope'],
            'budget_policy':POLICY,'authorized_effects':EFFECTS,'new_provider_requests':0}):
        refuse('backend_unknown_abort_authorization_required')
    # bools must never pass as integer request limits.
    _owner_scope(auth['owner'],auth['task_scope'])
    if auth['approved'] is not True or type(auth['new_provider_requests']) is not int:refuse('backend_unknown_abort_authorization_required')
    raw={k:read_bound(b) for k,b in att['files'].items()}
    binding={'operation':OPERATION,'owner':att['owner'],'task_scope':att['task_scope'],
        'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),
        'authorization_digest':digest_bytes(auth_raw),'termination_digest':digest_bytes(termination_raw),
        'implementation_identity':identity}
    return plan,att,raw,binding


def verify_history(owner, att, raw, *, exclude_release_key=None):
    from .task_store import TaskStore
    from .artifacts import TaskScope,ArtifactStore
    from .writer_contract import ArtifactRefV1
    from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events
    _owner_scope(att['owner'],att['task_scope'])
    scope=TaskScope(**att['task_scope']);root=Path(att['owner']['run_root'])
    expected={'schema_version':'serial-backend-admission/1','execution_id':scope.execution_id,
        'run_root':str(root.resolve()),'resource_key':owner.resource_key}
    if (not _same_json(att['owner'], expected) or att['state_root'] != str(owner.root) or att['resource_key'] != owner.resource_key
            or type(att['input_cap']) is not int or type(att['output_cap']) is not int
            or att['input_cap'] <= 0 or att['output_cap'] <= 0):refuse('backend_release_owner_mismatch')
    task=TaskStore.read_persisted(root,scope)
    if (digest_json(task) != att['task_view_digest'] or task['state'] != 'cancelled'
            or any(task[k] is not None for k in ('receipt','captured_source','provider_quiescence'))
            or task.get('binding',{}).get('session_id') != att['session_id']):refuse()
    ledger=root/'artifacts/06_authoring/invocations';facts=read_dsh_invocation_events(ledger,att['request_id'])
    if ([f.kind for f in facts] != ['reserve','dispatch-recorded','adapter-attempt','usage','cancel','terminal','settlement']
            or digest_json([f.model_dump(mode='json') for f in facts]) != att['ledger_digest']
            or facts[0].request_digest != att['request_digest'] or facts[0].claim_digest != task['claim_lineage'][0]
            or any((f.execution_id,f.task_id,f.task_epoch)!=(scope.execution_id,scope.task_id,scope.task_epoch) for f in facts)
            or (facts[3].usage_input_tokens,facts[3].usage_output_tokens)!=(0,0)
            or att['input_cap'] < facts[0].reserved_input_tokens or att['output_cap'] < facts[0].reserved_output_tokens):refuse()
    packet=json_object(raw['packet']);boot=json_object(raw['bootstrap']);descriptor=json_object(raw['descriptor'])
    if (boot['artifact_root'] != str(root) or not _same_json(boot['scope'], scope.__dict__) or not _same_json(descriptor['scope'], scope.__dict__)
            or boot['composition_spec']['effective_config']['backend_state_root'] != str(owner.root)
            or boot['composition_spec']['effective_config']['backend_resource_key'] != owner.resource_key
            or not isinstance(packet['scope'],str) or not packet['scope'] or packet['profile']['input_token_cap'] != att['input_cap']
            or packet['profile']['max_output_tokens'] != att['output_cap']):refuse()
    if len(att['frozen_inputs']) != len(packet['frozen_files']):refuse()
    for original,bound in zip(packet['frozen_files'],att['frozen_inputs'],strict=True):
        archived=read_bound(bound)
        if len(archived)!=original['byte_length'] or digest_bytes(archived)!=original['bytes_digest']:refuse()
    frames=raw['sse'].splitlines()
    if frames[-2:] != [b'data: [DONE]',b'']:refuse()
    events=[json_object(line[6:]) for line in frames if line.startswith(b'data: ') and line!=b'data: [DONE]']
    errors=[e for e in events if 'error' in e]
    ids={e.get('id') for e in events if 'id' in e}
    if (len(errors)!=1 or events[-1]!=errors[0] or ids!={att['provider_request_id']}
            or any('usage' in e for e in events)
            or any(c.get('finish_reason') is not None or c.get('delta',{}).get('tool_calls')
                for e in events for c in e.get('choices',[]))):refuse()
    rows=[json_object(line) for line in raw['session'].splitlines()]
    if (rows[0].get('id')!=att['session_id'] or rows[0].get('version')!=4
            or any(r.get('type') in {'tool/call','tool/result','assistant/message'} for r in rows)
            or not any(r.get('type')=='turn/end' and r.get('data',{}).get('reason',{}).get('kind')=='error' for r in rows)):
        refuse()
    from .legacy_retirement import verify_reserved_request_material
    store=ArtifactStore.open_readonly(root,scope)
    reserved=store.read_json(ArtifactRefV1.model_validate(facts[0].evidence_ref))
    contract=store.read_json(ArtifactRefV1.model_validate(task['prepared']['contract_ref']))
    actual_ref=ArtifactRefV1.model_validate(reserved['actual_request_ref'])
    verify_reserved_request_material(store,contract,actual_ref,facts[0].request_digest,
        json_object(raw['calibration'])['loop'],raw['wire'])
    with sqlite3.connect(owner.path.as_uri()+'?mode=ro',uri=True) as db:
        history=[]
        if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='release_history'").fetchone():
            for key,value in db.execute('SELECT release_key,receipt FROM release_history ORDER BY release_key'):
                owner._release_binding(json_object(value),key)
                history.append((key,digest_bytes(value)))
    # Replays may add only this contract's own history; all old rows remain bound.
    old=[(key,dig) for key,dig in history if key != exclude_release_key]
    if digest_json(old)!=att['history_digest']:refuse('backend_release_history_invalid')
    return task,facts


def validate_disposition(value, facts):
    _sealed(value,'DshUnknownUsageDispositionV1',{'operation','budget_policy','actual_usage','old_run_resumable',
        'owner','task_scope','request_id','request_digest','ledger_digest','input_liability','output_liability',
        'plan','review','authorization','termination'})
    reserve=facts[0]
    if (value['operation']!=OPERATION or value['budget_policy']!=POLICY or value['actual_usage']!='UNKNOWN'
            or value['old_run_resumable'] is not False or value['request_id']!=reserve.invocation_id
            or value['request_digest']!=reserve.request_digest
            or not _same_json(value['task_scope'], {'execution_id':reserve.execution_id,'task_id':reserve.task_id,'task_epoch':reserve.task_epoch})
            or value['ledger_digest']!=digest_json([f.model_dump(mode='json') for f in facts])
            or type(value['input_liability']) is not int or value['input_liability']<reserve.reserved_input_tokens
            or type(value['output_liability']) is not int or value['output_liability']<reserve.reserved_output_tokens
            or not any(f.kind=='usage' and (f.usage_input_tokens,f.usage_output_tokens)==(0,0) for f in facts)):
        refuse()
    plan=json_object(read_bound(value['plan']));review=json_object(read_bound(value['review']));auth=json_object(read_bound(value['authorization']))
    att=json_object(read_bound(plan['attestation']));termination=json_object(read_bound(value['termination']))
    _owner_scope(value['owner'],value['task_scope'])
    _sealed(att,'DshUnknownAbortHistoricalAttestationV1',{'owner','state_root','resource_key','task_scope',
        'request_id','provider_request_id','request_digest','session_id','task_view_digest','ledger_digest','history_digest',
        'input_cap','output_cap','server_epoch_digest','server_processes','gpu_uuid','files','frozen_inputs'})
    if (set(plan)!={'schema_version','operation','attestation','termination','implementation_identity',
            'command','authorized_effects','budget_policy','new_provider_requests','isolation_parent_namespace'}
            or plan['schema_version']!='DshUnknownAbortRetirementPlanV1'
            or not _implementation(plan['implementation_identity'])
            or type(plan['new_provider_requests']) is not int or plan['new_provider_requests']!=0
            or not _same_json(review, {'schema_version':'DshUnknownAbortRetirementReviewV1','decision':'PASS','operation':OPERATION,
                'plan_digest':value['plan']['bytes_digest'],'attestation_digest':plan['attestation']['bytes_digest'],
                'termination_digest':value['termination']['bytes_digest'],'implementation_identity':plan['implementation_identity'],
                'budget_policy':POLICY,'authorized_effects':EFFECTS})
            or not _same_json(auth, {'schema_version':'DshUnknownAbortRetirementAuthorizationV1','approved':True,'operation':OPERATION,
                'plan_digest':value['plan']['bytes_digest'],'review_digest':value['review']['bytes_digest'],
                'termination_digest':value['termination']['bytes_digest'],'owner':value['owner'],'task_scope':value['task_scope'],
                'budget_policy':POLICY,'authorized_effects':EFFECTS,'new_provider_requests':0})
            or type(auth['new_provider_requests']) is not int
            or not _same_json(att['owner'], value['owner']) or not _same_json(att['task_scope'], value['task_scope'])
            or att['request_id']!=value['request_id'] or att['request_digest']!=value['request_digest']
            or att['ledger_digest']!=value['ledger_digest']):
        refuse()
    if plan.get('isolation_parent_namespace') is not None:
        from .qualification import assert_offline_qualification_namespace
        assert_offline_qualification_namespace(plan['isolation_parent_namespace'])
    validate_termination(termination,att)
    if (plan['operation']!=OPERATION or plan['budget_policy']!=POLICY or plan['authorized_effects']!=EFFECTS
            or not _same_json(plan['termination'], value['termination']) or review['decision']!='PASS'
            or review['plan_digest']!=value['plan']['bytes_digest'] or auth['approved'] is not True
            or auth['schema_version']!='DshUnknownAbortRetirementAuthorizationV1'
            or auth['operation']!=OPERATION or auth['plan_digest']!=value['plan']['bytes_digest']
            or auth['review_digest']!=value['review']['bytes_digest'] or auth['termination_digest']!=value['termination']['bytes_digest']
            or not _same_json(auth['owner'], value['owner']) or not _same_json(auth['task_scope'], value['task_scope']) or auth['budget_policy']!=POLICY
            or auth['authorized_effects']!=EFFECTS or auth['new_provider_requests']!=0
            or type(att['input_cap']) is not int or type(att['output_cap']) is not int
            or att['input_cap']!=value['input_liability'] or att['output_cap']!=value['output_liability']):refuse()
    return value


def read_disposition(directory, facts):
    path=Path(directory)/MARKER
    if not path.exists():return None
    return validate_disposition(json_object(read_file(path)),facts)


def _bound(path):
    raw=read_file(path)
    return {'path':str(Path(path)),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}


def validate_receipt(value):
    keys=BINDING_KEYS|{'schema_version','task_view_digest','ledger_digest','budget_digest','released_at_ms','receipt_digest'}
    if (not isinstance(value,dict) or set(value)!=keys or value['schema_version']!='DshUnknownAbortBackendReleaseV1'
            or value['operation']!=OPERATION or type(value['released_at_ms']) is not int or value['released_at_ms']<=0
            or not _implementation(value['implementation_identity'])
            or not all(_digest(value[k]) for k in ('plan_digest','review_digest','authorization_digest',
                'termination_digest','task_view_digest','ledger_digest','budget_digest','receipt_digest'))
            or value['receipt_digest']!=digest_json({k:v for k,v in value.items() if k!='receipt_digest'})):refuse('backend_release_history_invalid')
    _owner_scope(value['owner'],value['task_scope'])
    marker=json_object(read_bound(value['disposition']))
    from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events,read_run_budget_state
    from .task_store import TaskStore
    from .artifacts import TaskScope
    ledger=Path(value['owner']['run_root'])/'artifacts/06_authoring/invocations'
    facts=read_dsh_invocation_events(ledger,marker['request_id']);validate_disposition(marker,facts)
    plan=json_object(read_bound(marker['plan']));review=json_object(read_bound(marker['review']))
    att=json_object(read_bound(plan['attestation']))
    task=TaskStore.read_persisted(Path(value['owner']['run_root']),TaskScope(**value['task_scope']))
    budget=read_run_budget_state(ledger)
    if (not _same_json(marker['owner'], value['owner']) or not _same_json(marker['task_scope'], value['task_scope'])
            or marker['ledger_digest']!=value['ledger_digest']
            or not _same_json(value['implementation_identity'], plan['implementation_identity'])
            or not _same_json(value['implementation_identity'], review['implementation_identity'])
            or not _same_json(value['owner'], att['owner']) or not _same_json(value['task_scope'], att['task_scope'])
            or value['task_view_digest']!=att['task_view_digest'] or value['task_view_digest']!=digest_json(task)
            or budget['status']!='pass' or budget['provider_usage_status']!='partial'
            or budget['pending_call_count']!=1 or budget['completed_call_count']!=0
            or budget['pending_input_tokens']!=marker['input_liability']
            or value['budget_digest']!=digest_json(budget)
            or any(marker[k]['bytes_digest']!=value[k+'_digest'] for k in ('plan','review','authorization','termination'))):
        refuse('backend_release_history_invalid')


def retire_unknown_abort(owner, *, engine_root, plan_path, review_path, authorization_path, _cut=None):
    from .task_store import SerialBackendAdmission
    from code2paper.agentic.unified_invocation_ledger import invocation_dir,read_run_budget_state
    plan,att,raw,binding=verify_package(engine_root,plan_path,review_path,authorization_path)
    ledger=Path(att['owner']['run_root'])/'artifacts/06_authoring/invocations'
    marker=invocation_dir(ledger,att['request_id'])/MARKER
    binding['disposition']=_bound(marker) if marker.exists() else None
    # Keep the old run lease through the marker and exact-owner transaction.
    with scoped_run_lease(Path(att['owner']['run_root']),execution_id=att['owner']['execution_id'],blocking=True):
        task,facts=verify_history(owner,att,raw,
            exclude_release_key=digest_json(binding) if marker.exists() else None)
        disposition=_seal({'schema_version':'DshUnknownUsageDispositionV1','operation':OPERATION,'budget_policy':POLICY,
            'actual_usage':'UNKNOWN','old_run_resumable':False,'owner':att['owner'],'task_scope':att['task_scope'],
            'request_id':att['request_id'],'request_digest':att['request_digest'],'ledger_digest':att['ledger_digest'],
            'input_liability':att['input_cap'],'output_liability':att['output_cap'],
            'plan':_bound(plan_path),'review':_bound(review_path),'authorization':_bound(authorization_path),
            'termination':plan['termination']})
        validate_disposition(disposition,facts)
        # The whole closed package and implementation must still match at
        # the effect boundary, after taking the original run lease.
        verify_package(engine_root,plan_path,review_path,authorization_path)
        with owner._transaction() as db:
            expected=canonical_json_bytes(att['owner']);row=db.execute('SELECT owner FROM admission WHERE resource=?',(owner.resource_key,)).fetchone()
            if marker.exists():
                if read_file(marker)!=canonical_json_bytes(disposition):refuse('backend_unknown_abort_disposition_conflict')
            elif row is None:refuse('backend_release_owner_missing')
            elif row[0]!=expected:refuse('backend_release_owner_mismatch')
            else:
                import os, tempfile
                fd,name=tempfile.mkstemp(prefix='.'+MARKER+'-',dir=marker.parent)
                try:
                    with os.fdopen(fd,'wb') as f:f.write(canonical_json_bytes(disposition));f.flush();os.fsync(f.fileno())
                    os.link(name,marker)
                finally:os.unlink(name)
                fd=os.open(marker.parent,os.O_RDONLY|os.O_DIRECTORY)
                try:os.fsync(fd)
                finally:os.close(fd)
            if _cut is not None:_cut('disposition-durable')
            binding['disposition']=_bound(marker);key=digest_json(binding)
            db.execute('CREATE TABLE IF NOT EXISTS release_history (release_key TEXT PRIMARY KEY, receipt BLOB NOT NULL)')
            previous=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
            if previous:
                value=json_object(previous[0]);owner._release_binding(value,key)
                if row is not None and row[0]==expected:refuse('backend_release_owner_reacquired')
                return value
            if row is not None and row[0]!=expected:refuse('backend_release_owner_mismatch')
            if row is None or owner._released_owner(db,att['owner']):refuse('backend_release_owner_missing')
            budget=read_run_budget_state(ledger)
            if (budget['status']!='pass' or budget['provider_usage_status']!='partial' or budget['pending_call_count']!=1
                    or budget['completed_call_count']!=0 or budget['pending_input_tokens']!=att['input_cap']):refuse()
            receipt={'schema_version':'DshUnknownAbortBackendReleaseV1',**binding,'task_view_digest':digest_json(task),
                'ledger_digest':att['ledger_digest'],'budget_digest':digest_json(budget),'released_at_ms':time.time_ns()//1_000_000}
            receipt['receipt_digest']=digest_json(receipt);validate_receipt(receipt)
            db.execute('INSERT INTO release_history VALUES (?,?)',(key,canonical_json_bytes(receipt)))
            if _cut is not None:_cut('history-inserted')
            if db.execute('DELETE FROM admission WHERE resource=? AND owner=?',(owner.resource_key,expected)).rowcount!=1:refuse('backend_release_owner_mismatch')
            if _cut is not None:_cut('owner-deleted')
            return receipt


def main():
    import argparse
    from .task_store import SerialBackendAdmission
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('engine-root','plan','review','authorization'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();_,att,_,_=verify_package(args.engine_root,args.plan,args.review,args.authorization)
    owner=object.__new__(SerialBackendAdmission);owner.root=Path(att['state_root']).resolve(strict=True)
    owner.path=owner.root/'serial-backend.sqlite3';owner.resource_key=att['resource_key']
    print(canonical_json_bytes(retire_unknown_abort(owner,engine_root=args.engine_root,plan_path=args.plan,
        review_path=args.review,authorization_path=args.authorization)).decode())


if __name__=='__main__':main()
