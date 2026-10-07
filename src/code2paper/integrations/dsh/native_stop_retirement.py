"""Operator-only retirement of a historically unregistered, naturally completed native stop.

This distinct migration never mints execute observations or calls a provider.
Only the exact original admission row and its immutable retirement history can
change; original task, raw bytes, fees and failed domain outcome stay intact.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import time
import re

from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events, read_run_budget_state
from .artifacts import ArtifactStore, TaskScope
from .legacy_retirement import read_bound, read_file, json_object, verify_stream, verify_reserved_request_material
from .protocol import ProtocolError, parse_model
from .writer_contract import ArtifactRefV1, WriterTaskResultV1

OPERATION = 'native-stop-finish-retirement/1'
FILES = frozenset({'packet','grant','original_plan','bootstrap','descriptor','wire','calibration',
                  'dispatch','sse','provider','tokenizer','session','producer','failure'})
BINDING_KEYS = frozenset({'operation','owner','task_scope','attestation_digest','plan_digest',
                         'review_digest','authorization_digest','historical_identity','implementation_identity','prior_history_digest'})
RECEIPT_KEYS = BINDING_KEYS | {'schema_version','task_view_digest','ledger_digest','budget_digest',
                             'released_at_ms','receipt_digest'}


def refuse(code='backend_native_stop_unproven'):
    raise ProtocolError(code)


def same(left, right):
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def history_digest(db):
    exists=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='release_history'").fetchone()
    rows=db.execute('SELECT release_key,receipt FROM release_history ORDER BY release_key').fetchall() if exists else []
    return digest_json([{'key':key,'receipt_digest':digest_bytes(raw)} for key,raw in rows])


def verify_completed_tool(session,task,finish,args):
    """Prove the successful native Tool/Result in the original completed turn."""
    events=session['events'];captured=task['captured_source']
    calls=[e for e in events if e.get('type')=='tool/call']
    results=[e for e in events if e.get('type')=='tool/result']
    messages=[e for e in events if e.get('type')=='assistant/message']
    ends=[e for e in events if e.get('type')=='turn/end']
    steps=[e for e in events if e.get('type')=='step/end']
    if any(len(v)!=1 for v in (calls,results,messages,ends,steps)):refuse()
    call,result,message,end,step=calls[0],results[0],messages[0],ends[0],steps[0]
    c=call.get('data',{});r=result.get('data',{});m=r.get('message',{})
    if (not isinstance(c,dict) or not isinstance(r,dict) or not isinstance(m,dict)
            or c.get('callId')!=captured['tool_call_id'] or c.get('name')!='c2p_terminal'
            or not isinstance(c.get('arguments'),str)
            or not same(json_object(c['arguments'].encode()),json_object(args))
            or any(type(v.get(k)) is not int or v[k]!=message['data'][k]
                   for v in (c,r) for k in ('turn','step'))
            or m.get('role')!='tool' or m.get('toolCallId')!=captured['tool_call_id']
            or m.get('isError') is not False
            or m.get('source')!={'kind':'tool','callId':captured['tool_call_id']}
            or result.get('sourceEventSeqs')!=[call['seq']]
            or end.get('data',{}).get('reason')!={'kind':'completed'}
            or not message['seq']<call['seq']<result['seq']<step['seq']<end['seq']):refuse()
    # _verify_native_quiescence separately binds raw/block/usage/finish/fees.


def validate_receipt(value):
    if (not isinstance(value,dict) or set(value) != RECEIPT_KEYS
            or value['schema_version'] != 'DshNativeStopBackendReleaseV1'
            or value['operation'] != OPERATION
            or type(value['released_at_ms']) is not int or value['released_at_ms'] <= 0):
        refuse('backend_release_history_invalid')
    owner=value['owner'];scope=value['task_scope']
    if (not isinstance(owner,dict) or set(owner) != {'schema_version','execution_id','run_root','resource_key'}
            or owner['schema_version'] != 'serial-backend-admission/1'
            or any(not isinstance(owner[k],str) or not owner[k] for k in ('execution_id','run_root','resource_key'))
            or not Path(owner['run_root']).is_absolute()
            or not isinstance(scope,dict) or set(scope) != {'execution_id','task_id','task_epoch'}
            or scope['execution_id'] != owner['execution_id'] or not isinstance(scope['task_id'],str) or not scope['task_id']
            or type(scope['task_epoch']) is not int or scope['task_epoch'] < 0):
        refuse('backend_release_history_invalid')
    digests=[value[k] for k in ('attestation_digest','plan_digest','review_digest','authorization_digest',
                              'task_view_digest','ledger_digest','budget_digest','receipt_digest','prior_history_digest')]
    for name,keys in (('historical_identity',{'engine_digest','validator_digest','composition_digest'}),
                      ('implementation_identity',{'engine_digest','validator_digest'})):
        identity=value[name]
        if not isinstance(identity,dict) or set(identity) != keys:refuse('backend_release_history_invalid')
        digests.extend(identity.values())
    if any(not isinstance(d,str) or re.fullmatch(r'sha256:[0-9a-f]{64}',d) is None for d in digests):
        refuse('backend_release_history_invalid')


def verify_package(engine_root, plan_path, review_path, authorization_path):
    from .suite_runner import _identity
    plan_raw=read_file(plan_path);plan=json_object(plan_raw)
    if (set(plan) != {'schema_version','operation','attestation','implementation_identity','command',
                     'new_provider_requests','authorized_effects'}
            or plan['schema_version'] != 'DshNativeStopRetirementPlanV1' or plan['operation'] != OPERATION
            or type(plan['new_provider_requests']) is not int or plan['new_provider_requests'] != 0
            or not same(plan['authorized_effects'],['exact-owner-release','immutable-release-history'])):refuse()
    att_raw=read_bound(plan['attestation']);att=json_object(att_raw)
    if (set(att) != {'schema_version','owner','state_root','task_scope','historical_identity','request_id',
                    'request_digest','finish_observation','task_view_digest','ledger_digest','budget_digest','prior_history_digest','files'}
            or att['schema_version'] != 'DshNativeStopRetirementAttestationV1'
            or not isinstance(att['files'],dict) or set(att['files']) != FILES):refuse()
    snapshot,validator=_identity(Path(engine_root))
    identity={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    if snapshot.unstable or not snapshot.is_usable or not same(plan['implementation_identity'],identity):
        refuse('backend_native_stop_identity_drift')
    # The reviewed command has no provider or fee-settlement action.
    if plan['command'] != ['python','-m','code2paper.integrations.dsh.native_stop_retirement',
            '--engine-root',str(Path(engine_root).resolve()),'--plan',str(plan_path),
            '--review',str(review_path),'--authorization',str(authorization_path)]:refuse()
    review_raw=read_file(review_path);review=json_object(review_raw)
    if not same(review, {'schema_version':'DshNativeStopRetirementReviewV1','decision':'PASS','operation':OPERATION,
                  'plan_digest':digest_bytes(plan_raw),'attestation_digest':digest_bytes(att_raw),
                  'implementation_identity':identity,'producer_digest':att['files']['producer']['bytes_digest'],
                  'producer_protocol':'fetch-reader-done/archive-before-error-v1'}):
        refuse('backend_native_stop_review_required')
    auth_raw=read_file(authorization_path);auth=json_object(auth_raw)
    if (auth.get('approved') is not True or type(auth.get('new_provider_requests')) is not int
            or not same(auth, {'schema_version':'DshNativeStopRetirementAuthorizationV1','approved':True,'operation':OPERATION,
                'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),
                'grant_digest':att['files']['grant']['bytes_digest'],'owner':att['owner'],'task_scope':att['task_scope'],
                'authorized_effects':plan['authorized_effects'],'new_provider_requests':0})):
        refuse('backend_native_stop_authorization_required')
    raw={key:read_bound(value) for key,value in att['files'].items()}
    return plan,att,raw,{'plan_digest':digest_bytes(plan_raw),'review_digest':digest_bytes(review_raw),
        'authorization_digest':digest_bytes(auth_raw),'attestation_digest':digest_bytes(att_raw),
        'implementation_identity':identity}


def verify_original_finish(owner, att, raw):
    from .task_store import TaskStore, SerialBackendAdmission
    scope=TaskScope(**att['task_scope']);root=Path(att['owner']['run_root']).resolve(strict=True)
    expected={'schema_version':'serial-backend-admission/1','execution_id':scope.execution_id,
              'run_root':str(root),'resource_key':owner.resource_key}
    if not same(att['owner'],expected) or att['state_root'] != str(owner.root):refuse('backend_release_owner_mismatch')
    task=TaskStore.read_persisted(root,scope)
    if (task['state'] != 'cancelled' or task['receipt'] is not None or task['provider_quiescence'] is not None
            or not task['captured_source'] or not task['binding'] or not task['claim_lineage']
            or digest_json(task) != att['task_view_digest']):refuse('backend_native_stop_task_state_invalid')
    with sqlite3.connect((root/'dsh-tasks.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] != 1:refuse()
    ledger=root/'artifacts/06_authoring/invocations'
    first=list(ledger.glob('*/attempt-0001.dsh-event-000001.json'))
    if len(first) != 1:refuse()
    facts=read_dsh_invocation_events(ledger,json_object(first[0].read_bytes())['invocation_id'])
    if ([f.kind for f in facts] != ['reserve','dispatch-recorded','adapter-attempt','usage','terminal','settlement']
            or facts[0].claim_digest != task['claim_lineage'][0]
            or facts[0].invocation_id != att['request_id'] or facts[0].request_digest != att['request_digest']
            or any((f.execution_id,f.task_id,f.task_epoch) != (scope.execution_id,scope.task_id,scope.task_epoch) for f in facts)
            or digest_json([f.model_dump(mode='json') for f in facts]) != att['ledger_digest']):refuse()
    budget=read_run_budget_state(ledger)
    if (budget['status'] != 'pass' or budget['provider_usage_status'] != 'validated' or budget['failure_codes']
            or any(budget[k] for k in ('pending_call_count','pending_input_tokens','provider_usage_missing_call_count',
                                     'provider_usage_missing_input_tokens','provider_usage_missing_receipts'))
            or budget['call_count'] != 1 or budget['completed_call_count'] != 1
            or digest_json(budget) != att['budget_digest']):refuse('backend_release_accounting_unsettled')
    boot=json_object(raw['bootstrap']);packet=json_object(raw['packet']);descriptor=json_object(raw['descriptor'])
    old=att['historical_identity'];config=boot['composition_spec']['effective_config']
    if (set(old) != {'engine_digest','validator_digest','composition_digest'}
            or any(boot['composition'].get(k) != v for k,v in old.items())
            or packet['engine_digest'] != old['engine_digest'] or descriptor['composition_digest'] != old['composition_digest']
            or boot['scope'] != scope.__dict__ or descriptor['scope'] != scope.__dict__
            or boot['artifact_root'] != str(root) or config['backend_state_root'] != str(owner.root)
            or config['backend_resource_key'] != owner.resource_key):refuse()
    original_plan=json_object(raw['original_plan']);grant=json_object(raw['grant'])
    authorization=grant.get('authorization',{})
    original_packet_digest=original_plan.get('packet_digest')
    if original_packet_digest is None:
        original_packet_digest=original_plan.get('packet',{}).get('bytes_digest')
    if (grant.get('schema_version') != 'L01ExplicitUserGrantRecordV1'
            or grant.get('packet_digest') != digest_bytes(raw['packet'])
            or original_packet_digest != digest_bytes(raw['packet'])
            or grant.get('execution_plan_digest') != digest_bytes(raw['original_plan'])
            or authorization.get('approved') is not True
            or type(authorization.get('primary_requests')) is not int or authorization.get('primary_requests') != 1
            or type(authorization.get('retries')) is not int or authorization.get('retries') != 0
            or authorization.get('packet_digest') != digest_bytes(raw['packet'])
            or not isinstance(grant.get('additional_authorized_scope'),str)
            or 'normal-finish release' not in grant['additional_authorized_scope']):
        refuse('backend_native_stop_original_release_not_authorized')
    wire=json_object(raw['wire']);args,call_id,name,usage=verify_stream(raw['sse'],wire['model'],expected_finish='stop')
    if (name != 'c2p_terminal' or authorization.get('model') != wire['model']
            or args == b'' or usage['prompt_tokens'] != facts[3].usage_input_tokens
            or usage['completion_tokens'] != facts[3].usage_output_tokens
            or budget['spent_input_tokens'] != usage['prompt_tokens']):refuse()
    tokens=json_object(raw['tokenizer']);provider=json_object(raw['provider']);dispatch=json_object(raw['dispatch'])
    if (tokens.get('origin') != 'vllm_tokenize_exact_messages_tools' or tokens.get('wire_digest') != digest_bytes(raw['wire'])
            or tokens.get('model') != wire['model'] or tokens.get('input_tokens') != usage['prompt_tokens']
            or not same(provider,{'http_status':200,'usage':usage,'finish_reasons':['stop'],'provider_errors':[]})
            or type(dispatch.get('requests')) is not int or dispatch.get('requests') != 1
            or dispatch.get('body') != att['files']['wire']):refuse()
    frozen_rows=packet.get('frozen_files',[])
    if any(not any(row.get('bytes_digest') == att['files'][key]['bytes_digest']
                   and row.get('byte_length') == att['files'][key]['byte_length'] for row in frozen_rows)
           for key in ('producer','bootstrap','descriptor','wire','calibration')):refuse()
    store=ArtifactStore.open_readonly(root,scope)
    def read_ref(value):return parse_model(canonical_json_bytes(value),ArtifactRefV1)
    finish=att['finish_observation']
    if not isinstance(finish,dict):refuse()
    failure=json_object(raw['failure'])
    observation=failure.get('terminal_observation',{})
    if (failure.get('actual_model_inference_requests') != 1
            or type(failure.get('actual_model_inference_requests')) is not int
            or observation.get('raw_ref') != finish.get('raw_ref')
            or observation.get('session_ref') != finish.get('session_ref')
            or observation.get('request_id') != att['request_id']):refuse()
    if (set(finish) != {'schema_version','execution_id','task_id','task_epoch','request_id','request_digest',
                       'session_id','source','finish_reason','raw_ref','session_ref'}
            or finish['schema_version'] != 'DshHistoricalNativeStopProofV1'
            or finish['source'] != 'operator-reviewed-original-native-stream/1' or finish['finish_reason'] != 'stop'
            or any(not same(finish[k],v) for k,v in scope.__dict__.items())
            or finish['request_id'] != att['request_id'] or finish['request_digest'] != att['request_digest']
            or finish['session_id'] != task['binding']['session_id']
            or task['captured_source']['tool_call_id'] != call_id
            or store.read(read_ref(finish['raw_ref'])) != args):refuse()
    # Valid native output can still fail domain acceptance. Never rewrite it.
    parse_model(args,WriterTaskResultV1)
    session=store.read_json(read_ref(finish['session_ref']))
    rows=[json_object(line) for line in raw['session'].splitlines() if line]
    if (not rows or rows[0].get('type') != 'session' or rows[0].get('version') != 4
            or rows[0].get('id') != finish['session_id']
            or session.get('events') != rows[1:]
            or not any(e.get('type') == 'turn/end' and e.get('data',{}).get('reason') == {'kind':'completed'} for e in rows[1:])):refuse()
    # Use the original pure verifier without storing or registering an execute
    # credential. The operator receipt retains its distinct historical source.
    SerialBackendAdmission._verify_native_quiescence(store,task,finish,facts)
    verify_completed_tool(session,task,finish,args)
    terminal=store.read_json(read_ref(facts[4].evidence_ref))
    settlement=store.read_json(read_ref(facts[5].evidence_ref))
    if (terminal.get('schema_version') != 'RecordedWriterOutputV1'
            or settlement.get('schema_version') != 'DshRejectedOutputObservationV1'
            or settlement.get('output_ref') != facts[4].evidence_ref):refuse()
    contract=store.read_json(read_ref(task['prepared']['contract_ref']))
    frozen=store.read_json(read_ref(descriptor['frozen_ref']))
    if (contract.get('task_digest') != facts[0].contract_digest
            or any(frozen['identity'].get(k) != v for k,v in old.items())
            or contract['identity'] != frozen['identity']
            or frozen['snapshot_digest'] != task['prepared']['snapshot_digest']):refuse()
    reserved=store.read_json(read_ref(facts[0].evidence_ref))
    calibration=json_object(raw['calibration'])
    verify_reserved_request_material(store,contract,read_ref(reserved['actual_request_ref']),att['request_digest'],
                                     calibration['loop'],raw['wire'])
    return task,facts,budget


def retire_native_stop_finish(owner, *, engine_root, plan_path, review_path, authorization_path):
    plan,att,raw,authority=verify_package(engine_root,plan_path,review_path,authorization_path)
    root=Path(att['owner']['run_root']).resolve(strict=True);scope=TaskScope(**att['task_scope'])
    with scoped_run_lease(root,execution_id=scope.execution_id,blocking=True):
        task,facts,budget=verify_original_finish(owner,att,raw)
        # Recheck sealed bytes and complete implementation identity at the
        # mutation boundary, after the original readers finish their work.
        _,current_att,current_raw,current_authority=verify_package(engine_root,plan_path,review_path,authorization_path)
        if current_att != att or current_raw != raw or current_authority != authority:refuse()
        binding={'operation':OPERATION,'owner':att['owner'],'task_scope':att['task_scope'],
                 'historical_identity':att['historical_identity'],'prior_history_digest':att['prior_history_digest'],**authority}
        key=digest_json(binding)
        with owner._transaction() as db:
            row=db.execute('SELECT owner FROM admission WHERE resource=?',(owner.resource_key,)).fetchone()
            expected=canonical_json_bytes(att['owner'])
            if row is not None and row[0] != expected:refuse('backend_release_owner_mismatch')
            db.execute('CREATE TABLE IF NOT EXISTS release_history (release_key TEXT PRIMARY KEY, receipt BLOB NOT NULL)')
            retired=owner._released_owner(db,att['owner'])
            previous=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
            if previous:
                if row is not None:refuse('backend_release_owner_reacquired')
                value=json_object(previous[0])
                if owner._release_binding(value,key) != binding:refuse('backend_release_history_invalid')
                return value
            if row is None or retired:refuse('backend_release_owner_missing')
            if history_digest(db) != att['prior_history_digest']:refuse('backend_release_history_drift')
            receipt={'schema_version':'DshNativeStopBackendReleaseV1',**binding,
                     'task_view_digest':digest_json(task),'ledger_digest':digest_json([f.model_dump(mode='json') for f in facts]),
                     'budget_digest':digest_json(budget),'released_at_ms':time.time_ns()//1_000_000}
            receipt['receipt_digest']=digest_json(receipt);validate_receipt(receipt)
            db.execute('INSERT INTO release_history VALUES (?,?)',(key,canonical_json_bytes(receipt)))
            if db.execute('DELETE FROM admission WHERE resource=? AND owner=?',(owner.resource_key,expected)).rowcount != 1:
                refuse('backend_release_owner_mismatch')
            return receipt


def main():
    import argparse
    from .task_store import SerialBackendAdmission
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('engine-root','plan','review','authorization'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    plan,att,_,_=verify_package(args.engine_root,args.plan,args.review,args.authorization)
    # Observe existing state without creating a replacement database/resource.
    owner=object.__new__(SerialBackendAdmission);owner.root=Path(att['state_root']).resolve(strict=True)
    owner.path=owner.root/'serial-backend.sqlite3';owner.resource_key=att['owner']['resource_key']
    SerialBackendAdmission.read_persisted(owner.root,owner.resource_key)
    receipt=retire_native_stop_finish(owner,engine_root=args.engine_root,plan_path=args.plan,
                                        review_path=args.review,authorization_path=args.authorization)
    print(canonical_json_bytes(receipt).decode())


if __name__ == '__main__':main()
