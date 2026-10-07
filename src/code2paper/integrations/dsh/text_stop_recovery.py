"""Operator-only settlement and retirement of an EOF-observed text rejection.

No Worker RPC imports this command. It preserves original task/claim/content and
never registers an execute/provider observation. Only the observed original fee
completion facts, their named operator evidence and exact owner history change.
"""
from pathlib import Path
import sqlite3
import time

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes,digest_json
from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.unified_context_models import DshInvocationEventV1
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events,read_run_budget_state,publish_dsh_invocation_event
from .artifacts import ArtifactStore,TaskScope
from .legacy_retirement import read_file,read_bound,json_object,verify_reserved_request_material
from .native_rejection_retirement import BINDING_KEYS,RECEIPT_KEYS
from .protocol import ProtocolError,parse_model
from .writer_contract import ArtifactRefV1
from .text_stop_transport_proof import verify_text_stop_stream,verify_failed_text_session

OPERATION='text-stop-observed-fees-retirement/1'
EFFECTS=['observed-original-fees-settlement','exact-owner-release','immutable-release-history']
FILES={'packet','grant','original_plan','descriptor','wire','calibration','dispatch','sse','provider','tokenizer',
       'cleanup','failure','launch','started','bootstrap','producer','session'}


def refuse(code='historical_text_stop_recovery_unproven'):
    raise ProtocolError(code)


def validate_receipt(value):
    # Reuse structural checks, never the old operation/transport authority.
    from .native_rejection_retirement import validate_receipt as structural
    if (not isinstance(value,dict) or set(value)!=RECEIPT_KEYS
            or value.get('schema_version')!='DshTextStopBackendReleaseV1' or value.get('operation')!=OPERATION):
        refuse('backend_release_history_invalid')
    structural({**value,'schema_version':'DshNativeRejectedBackendReleaseV1','operation':'native-rejected-finish-retirement/1'})


def verify_package(engine_root,plan_path,review_path,authorization_path):
    from .suite_runner import _identity
    plan_raw=read_file(plan_path);plan=json_object(plan_raw)
    if (set(plan)!={'schema_version','operation','attestation','implementation_identity','command','new_provider_requests','authorized_effects'}
            or plan['schema_version']!='DshTextStopRecoveryPlanV1' or plan['operation']!=OPERATION
            or type(plan['new_provider_requests']) is not int or plan['new_provider_requests']!=0
            or plan['authorized_effects']!=EFFECTS):refuse()
    att_raw=read_bound(plan['attestation']);att=json_object(att_raw)
    if (set(att)!={'schema_version','owner','state_root','task_scope','historical_identity','task_view_digest','task_db',
                  'original_ledger','ledger_digest','original_budget','files'}
            or att['schema_version']!='DshTextStopRecoveryAttestationV1' or set(att['files'])!=FILES):refuse()
    snapshot,validator=_identity(Path(engine_root));identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    if snapshot.unstable or not snapshot.is_usable or plan['implementation_identity']!=identity:refuse('historical_text_stop_identity_drift')
    if plan['command']!=['python','-m','code2paper.integrations.dsh.text_stop_recovery','--engine-root',str(Path(engine_root).resolve()),
                         '--plan',str(plan_path),'--review',str(review_path),'--authorization',str(authorization_path)]:refuse()
    review_raw=read_file(review_path);review=json_object(review_raw)
    if review!={'schema_version':'DshTextStopRecoveryReviewV1','decision':'PASS','operation':OPERATION,
                'plan_digest':digest_bytes(plan_raw),'attestation_digest':digest_bytes(att_raw),'implementation_identity':identity,
                'producer_digest':att['files']['producer']['bytes_digest'],'producer_protocol':'fetch-reader-done/archive-before-error-v1'}:
        refuse('historical_text_stop_review_required')
    auth_raw=read_file(authorization_path);auth=json_object(auth_raw)
    if (auth.get('approved') is not True or type(auth.get('new_provider_requests')) is not int
            or auth!={'schema_version':'DshTextStopRecoveryAuthorizationV1','approved':True,'operation':OPERATION,
                'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),
                'grant_digest':att['files']['grant']['bytes_digest'],'owner':att['owner'],'task_scope':att['task_scope'],
                'authorized_effects':EFFECTS,'new_provider_requests':0}):refuse('historical_text_stop_authorization_required')
    raw={k:read_bound(v) for k,v in att['files'].items()}
    authority={'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),'authorization_digest':digest_bytes(auth_raw),
               'attestation_digest':digest_bytes(att_raw),'implementation_identity':identity}
    return plan,att,raw,authority


def verify_original(owner,att,raw):
    from .task_store import TaskStore
    scope=TaskScope(**att['task_scope']);root=Path(att['owner']['run_root']).resolve(strict=True)
    expected={'schema_version':'serial-backend-admission/1','execution_id':scope.execution_id,'run_root':str(root),'resource_key':owner.resource_key}
    if att['owner']!=expected or att['state_root']!=str(owner.root):refuse('backend_release_owner_mismatch')
    task=TaskStore.read_persisted(root,scope)
    if (task['state']!='cancelled' or task['receipt'] is not None or task['captured_source'] is not None
            or task['provider_quiescence'] is not None or not task['binding'] or not task['claim_lineage']
            or digest_json(task)!=att['task_view_digest'] or read_bound(att['task_db'])!=(root/'dsh-tasks.sqlite3').read_bytes()):refuse()
    with sqlite3.connect((root/'dsh-tasks.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]!=1:refuse()
    prefix=tuple(DshInvocationEventV1.model_validate(v) for v in att['original_ledger'])
    if ([f.kind for f in prefix]!=['reserve','dispatch-recorded','adapter-attempt','usage','cancel']
            or digest_json([f.model_dump(mode='json') for f in prefix])!=att['ledger_digest']
            or prefix[0].claim_digest!=task['claim_lineage'][0]
            or any((f.execution_id,f.task_id,f.task_epoch)!=(scope.execution_id,scope.task_id,scope.task_epoch) for f in prefix)):
        refuse()
    store=ArtifactStore.open_readonly(root,scope);boot=json_object(raw['bootstrap']);packet=json_object(raw['packet']);d=json_object(raw['descriptor'])
    old=att['historical_identity'];config=boot['composition_spec']['effective_config']
    if (set(old)!={'engine_digest','validator_digest','composition_digest'} or any(boot['composition'].get(k)!=v for k,v in old.items())
            or packet['engine_digest']!=old['engine_digest'] or d['composition_digest']!=old['composition_digest']
            or boot['scope']!=scope.__dict__ or d['scope']!=scope.__dict__ or boot['artifact_root']!=str(root)
            or config['backend_state_root']!=str(owner.root) or config['backend_resource_key']!=owner.resource_key):refuse()
    plan=json_object(raw['original_plan']);grant=json_object(raw['grant']);a=grant.get('authorization',{})
    if (grant.get('schema_version')!='L01ExplicitUserGrantRecordV1' or grant.get('packet_digest')!=digest_bytes(raw['packet'])
            or plan.get('packet_digest')!=digest_bytes(raw['packet']) or grant.get('execution_plan_digest')!=digest_bytes(raw['original_plan'])
            or a.get('approved') is not True or type(a.get('primary_requests')) is not int or a.get('primary_requests')!=1
            or type(a.get('retries')) is not int or a.get('retries')!=0 or a.get('packet_digest')!=digest_bytes(raw['packet'])
            or not isinstance(grant.get('additional_authorized_scope'),str)
            or 'fees settlement' not in grant['additional_authorized_scope'] or 'normal-finish' not in grant['additional_authorized_scope']):
        refuse('historical_text_stop_original_effects_not_authorized')
    wire=json_object(raw['wire']);text,reasoning,usage=verify_text_stop_stream(raw['sse'],wire['model'])
    if (a.get('model')!=wire['model'] or any(type(a.get(k)) is not int for k in ('input_token_cap','max_output_tokens','wall_seconds'))
            or usage['prompt_tokens']>a['input_token_cap'] or usage['completion_tokens']>a['max_output_tokens']
            or wire.get('max_tokens')!=a['max_output_tokens']
            or (prefix[3].usage_input_tokens,prefix[3].usage_output_tokens)!=(usage['prompt_tokens'],usage['completion_tokens'])):refuse()
    tokens=json_object(raw['tokenizer']);provider=json_object(raw['provider']);dispatch=json_object(raw['dispatch']);cal=json_object(raw['calibration'])
    if (tokens.get('origin')!='vllm_tokenize_exact_messages_tools' or tokens.get('wire_digest')!=digest_bytes(raw['wire'])
            or tokens.get('model')!=wire['model'] or tokens.get('input_tokens')!=usage['prompt_tokens']
            or provider!={'http_status':200,'usage':usage,'finish_reasons':['stop']}
            or type(dispatch.get('requests')) is not int or dispatch.get('requests')!=1 or dispatch.get('body')!=att['files']['wire']
            or cal.get('actual_provider_body')!=att['files']['wire']
            or type(cal.get('calibration_sends')) is not int or cal.get('calibration_sends')!=1):refuse()
    for k in ('producer','bootstrap','descriptor','wire','calibration'):
        if not any(v.get('bytes_digest')==att['files'][k]['bytes_digest'] and v.get('byte_length')==att['files'][k]['byte_length']
                   for v in packet.get('frozen_files',[])):refuse()
    started=json_object(raw['started']);launch=json_object(raw['launch'])
    if (launch.get('mode')!='live' or launch.get('inference_authorized') is not True
            or launch.get('output')!=str(Path(att['files']['packet']['path']).parent)
            or started.get('tokenizer')!=att['files']['tokenizer']
            or json_object(read_bound(started.get('authorization')))!=a):refuse()
    failure=json_object(raw['failure']);cleanup=json_object(raw['cleanup'])
    if (failure.get('request_counts')!={'primary':1,'isolated_offline':0,'tokenize':1,'auxiliary':0}
            or failure.get('cleanup_failures')!=[] or cleanup.get('worker_scope_quiescent') is not True or cleanup.get('errors')!=[]
            or cleanup.get('sentinel',{}).get('model_calls')!=0 or cleanup.get('sentinel',{}).get('network_calls')!=0):refuse()
    counts=failure.get('request_counts',{});sentinel=cleanup.get('sentinel',{})
    if (any(type(v) is not int for v in counts.values()) or sentinel.get('state')!='closed'
            or sentinel.get('probe_refused') is not True or any(type(sentinel.get(k)) is not int for k in ('model_calls','network_calls'))):refuse()
    rows=verify_failed_text_session(raw['session'],task['binding']['session_id'],text,reasoning,usage,failure['message'])
    ref=lambda v:parse_model(canonical_json_bytes(v),ArtifactRefV1)
    contract=store.read_json(ref(task['prepared']['contract_ref']));frozen=store.read_json(ref(d['frozen_ref']))
    if (contract.get('task_digest')!=prefix[0].contract_digest or contract['identity']!=frozen['identity']
            or any(frozen['identity'].get(k)!=v for k,v in old.items()) or frozen['snapshot_digest']!=task['prepared']['snapshot_digest']):refuse()
    reserve=store.read_json(ref(prefix[0].evidence_ref));actual_ref=ref(reserve['actual_request_ref']);actual=store.read_json(actual_ref)
    verify_reserved_request_material(store,contract,actual_ref,prefix[0].request_digest,cal['loop'],raw['wire'])
    headers=[r for r in rows if r.get('type')=='request/header'];contexts=[r for r in rows if r.get('type')=='request/context']
    if (len(headers)!=1 or len(contexts)!=1 or headers[0]['data']['header'].get('config')!={k:actual[k] for k in
            ('provider','model','maxTokens','temperature','reasoningEffort') if k in actual}
            or headers[0]['data']['header'].get('tools')!=actual.get('tools')
            or any(contexts[0]['data'].get(k)!=actual.get(k) for k in ('provider','model'))):refuse()
    return root,scope,task,prefix,usage


def recover_text_stop(owner,*,engine_root,plan_path,review_path,authorization_path):
    _,att,raw,authority=verify_package(engine_root,plan_path,review_path,authorization_path)
    root=Path(att['owner']['run_root']);scope=TaskScope(**att['task_scope'])
    with scoped_run_lease(root,execution_id=scope.execution_id,blocking=True):
        root,scope,task,prefix,usage=verify_original(owner,att,raw)
        binding={'operation':OPERATION,'owner':att['owner'],'task_scope':att['task_scope'],
                 'historical_identity':att['historical_identity'],**authority};key=digest_json(binding)
        evidence={'schema_version':'DshTextStopHistoricalSettlementV1',**binding,'original_ledger_digest':att['ledger_digest'],
                  'usage_input_tokens':usage['prompt_tokens'],'usage_output_tokens':usage['completion_tokens'],
                  'source':'operator-reviewed-original-fetch-EOF/1','domain_result':'rejected; no native terminal'}
        with owner._transaction() as db:
            expected=canonical_json_bytes(att['owner']);row=db.execute('SELECT owner FROM admission WHERE resource=?',(owner.resource_key,)).fetchone()
            if row is not None and row[0]!=expected:refuse('backend_release_owner_mismatch')
            db.execute('CREATE TABLE IF NOT EXISTS release_history (release_key TEXT PRIMARY KEY,receipt BLOB NOT NULL)')
            owner._released_owner(db,att['owner'])
            previous=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
            if row is None and previous is None:refuse('backend_release_owner_missing')
            raw_evidence=canonical_json_bytes(evidence);ed=digest_bytes(raw_evidence)
            evidence_ref=ArtifactRefV1(schema_version='ArtifactRefV1',**scope.__dict__,artifact_id=ed,
                bytes_digest=ed,byte_length=len(raw_evidence),media_type='application/json',semantic_digest=digest_json(evidence)).model_dump(mode='json')
            values=prefix[0].model_dump(mode='json');values.update(reserved_input_tokens=0,reserved_output_tokens=0,
                evidence_ref=evidence_ref,source='kernel',reason='reviewed operator accounting only; no execute observation',content_digest='')
            tails=tuple(DshInvocationEventV1(**{**values,'kind':kind,'event_id':f'text-stop-recovery:{key}:{kind}'}) for kind in ('terminal','settlement'))
            ledger=root/'artifacts/06_authoring/invocations';facts=read_dsh_invocation_events(ledger,prefix[0].invocation_id)
            if len(facts) not in {len(prefix),len(prefix)+1,len(prefix)+2} or facts!=prefix+tails[:len(facts)-len(prefix)]:refuse()
            budget_before=read_run_budget_state(ledger)
            if (budget_before['status']!='pass' or budget_before['provider_usage_status']!='validated'
                    or budget_before['failure_codes'] or budget_before['call_count']!=1
                    or budget_before['provider_usage_missing_call_count'] or budget_before['provider_usage_missing_receipts']
                    or len(list(ledger.glob('*/attempt-0001.dsh-event-000001.json')))!=1):refuse()
            if len(facts)==len(prefix) and budget_before!=att['original_budget']:refuse()

            _,new_att,new_raw,new_authority=verify_package(engine_root,plan_path,review_path,authorization_path)
            if new_att!=att or new_raw!=raw or new_authority!=authority:refuse()
            store=ArtifactStore(root,scope)
            if store.put_json(evidence).model_dump(mode='json')!=evidence_ref:refuse()
            for event in tails:publish_dsh_invocation_event(ledger,event)
            budget=read_run_budget_state(ledger)
            if (read_dsh_invocation_events(ledger,prefix[0].invocation_id)!=prefix+tails or budget['status']!='pass'
                    or budget['provider_usage_status']!='validated' or budget['failure_codes'] or budget['pending_input_tokens']
                    or budget['pending_call_count'] or budget['call_count']!=1 or budget['completed_call_count']!=1
                    or budget['spent_input_tokens']!=usage['prompt_tokens']):refuse()
            if previous is not None:
                if row is not None:refuse('backend_release_owner_reacquired')
                receipt=json_object(previous[0])
                if owner._release_binding(receipt,key)!=binding:refuse('backend_release_history_invalid')
                return receipt
            receipt={'schema_version':'DshTextStopBackendReleaseV1',**binding,'task_view_digest':digest_json(task),
                     'ledger_digest':digest_json([f.model_dump(mode='json') for f in prefix+tails]),
                     'budget_digest':digest_json(budget),'released_at_ms':time.time_ns()//1_000_000}
            receipt['receipt_digest']=digest_json(receipt);validate_receipt(receipt)
            db.execute('INSERT INTO release_history VALUES (?,?)',(key,canonical_json_bytes(receipt)))
            if db.execute('DELETE FROM admission WHERE resource=? AND owner=?',(owner.resource_key,expected)).rowcount!=1:refuse('backend_release_owner_mismatch')
            return receipt


def main():
    import argparse
    from .task_store import SerialBackendAdmission
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('engine-root','plan','review','authorization'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();_,att,_,_=verify_package(args.engine_root,args.plan,args.review,args.authorization)
    owner=object.__new__(SerialBackendAdmission);owner.root=Path(att['state_root']).resolve(strict=True)
    owner.path=owner.root/'serial-backend.sqlite3';owner.resource_key=att['owner']['resource_key']
    SerialBackendAdmission.read_persisted(owner.root,owner.resource_key)
    print(canonical_json_bytes(recover_text_stop(owner,engine_root=args.engine_root,plan_path=args.plan,
        review_path=args.review,authorization_path=args.authorization)).decode())


if __name__=='__main__':main()
