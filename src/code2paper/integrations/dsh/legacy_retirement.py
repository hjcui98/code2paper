"""Explicit operator migration for a historical, failed, EOF-observed send.

No Worker RPC imports this operation. It uses the original task/fee readers
and SerialBackendAdmission transaction; it never accepts Writer output,
mints provider_quiescence, changes a claim, or performs a provider request.
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
from .protocol import ProtocolError, parse_model, strict_json_loads
from .writer_contract import ArtifactRefV1,WriterWireProjectionV1,WriterWireEquivalenceV1


FILES = frozenset({'packet','descriptor','bootstrap','original_authorization',
    'live_started','launch','dispatch','wire','calibration','sse','provider','session','cleanup','producer','manifest'})
LEGACY_RECEIPT_KEYS = frozenset({'schema_version','operation','owner','task_scope',
    'attestation_digest','authorization_digest','review_digest','plan_digest',
    'historical_identity','implementation_identity','task_view_digest',
    'ledger_digest','budget_digest','released_at_ms','receipt_digest'})
LEGACY_BINDING_KEYS = frozenset({'operation','owner','task_scope','attestation_digest',
    'authorization_digest','review_digest','plan_digest','historical_identity','implementation_identity'})
EXECUTION_FILE_KEYS = frozenset({'entry_point','settlement_launcher','settlement_worker',
    'mount_manifest','python_module_manifest','python_test_manifest','node_test_manifest'})


def refuse(code='backend_legacy_transport_unproven'):
    raise ProtocolError(code)


def read_file(path: Path) -> bytes:
    path=Path(path)
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():refuse()
    try:
        if not path.is_file() or path.stat().st_size > 32 << 20:refuse()
        return path.read_bytes()
    except OSError as error:
        raise ProtocolError('backend_legacy_transport_unproven') from error


def read_bound(binding: dict) -> bytes:
    if (not isinstance(binding,dict) or set(binding) != {'path','bytes_digest','byte_length'}
            or type(binding['byte_length']) is not int):refuse()
    raw=read_file(Path(binding['path']))
    if len(raw) != binding['byte_length'] or digest_bytes(raw) != binding['bytes_digest']:refuse()
    return raw


def json_object(raw: bytes) -> dict:
    value=strict_json_loads(raw,max_bytes=32 << 20)
    if not isinstance(value,dict):refuse()
    return value


def verify_execution_mounts(plan):
    """Recheck overlay bytes and tree closure before either mutation phase."""
    files=plan['execution_files']
    rows=strict_json_loads(read_bound(files['mount_manifest']),max_bytes=32 << 20)
    if not isinstance(rows,list) or not rows or len(rows)>10000:refuse()
    file_mounts=[]
    for row in rows:
        if not isinstance(row,dict) or set(row) != {'source','mount_target','bytes_digest','byte_length'}:refuse()
        read_bound({'path':row['source'],'bytes_digest':row['bytes_digest'],'byte_length':row['byte_length']})
        file_mounts.append((row['source'],row['mount_target']))
    directory_mounts=[]
    for key in ('python_module_manifest','python_test_manifest','node_test_manifest'):
        tree=json_object(read_bound(files[key]))
        if set(tree) != {'source','mount_target','files'} or not isinstance(tree['files'],list) or not tree['files']:refuse()
        source=Path(tree['source']);target=Path(tree['mount_target'])
        if (not source.is_absolute() or source.resolve()!=source or not source.is_dir() or source.is_symlink()
                or not target.is_absolute() or target.resolve()!=target):refuse()
        expected_files=set();expected_dirs={source}
        for item in tree['files']:
            if not isinstance(item,dict) or set(item) != {'path','historical_path','bytes_digest','byte_length'}:refuse()
            path=Path(item['path'])
            if not path.is_relative_to(source) or path in expected_files:refuse()
            if item['historical_path'] != str(target/path.relative_to(source)):refuse()
            read_bound({k:item[k] for k in ('path','bytes_digest','byte_length')})
            expected_files.add(path)
            parent=path.parent
            while parent.is_relative_to(source):
                expected_dirs.add(parent)
                if parent==source:break
                parent=parent.parent
        actual_files=set();actual_dirs={source}
        for path in source.rglob('*'):
            if path.is_symlink():refuse()
            if path.is_dir():actual_dirs.add(path)
            elif path.is_file():actual_files.add(path)
            else:refuse()
        if actual_files != expected_files or actual_dirs != expected_dirs:refuse()
        directory_mounts.append((str(source),str(target)))
    projection=directory_mounts+file_mounts
    if len({target for _,target in projection}) != len(projection):refuse()
    command=plan['commands']['settlement']
    try:separator=command.index('--')
    except ValueError:refuse()
    observed=[]
    all_mounts=[]
    i=1
    while i<separator:
        part=command[i]
        if part in {'--bind','--ro-bind'}:
            if i+2>=separator:refuse()
            pair=(command[i+1],command[i+2]);all_mounts.append((i,part,pair))
            if pair in projection:
                if part != '--ro-bind':refuse()
                observed.append(pair)
            i+=3
        elif part in {'--tmpfs','--proc','--dev'}:
            if i+1>=separator:refuse()
            all_mounts.append((i,part,(part,command[i+1])));i+=2
        elif part=='--chdir':
            if i+1>=separator:refuse()
            i+=2
        elif part in {'--die-with-parent','--new-session','--unshare-pid','--unshare-net'}:
            i+=1
        else:
            # The reviewed v1 launcher has no other mount syntax. Reject
            # extensions rather than silently overlooking their destinations.
            refuse()
    if observed != projection:refuse()
    positions={pair:i for i,_,pair in all_mounts if pair in projection}
    for i,_,pair in all_mounts:
        if pair in projection:continue
        destination=Path(pair[1])
        if not destination.is_absolute() or destination.resolve()!=destination:refuse()
        for projected in projection:
            target=Path(projected[1])
            if destination.is_relative_to(target):refuse()
            if target.is_relative_to(destination) and i>positions[projected]:refuse()
    for _,target in projection:
        path=Path(target)
        if not path.is_absolute() or path.resolve()!=path:refuse()
        matching=[(i,kind,pair) for i,kind,pair in all_mounts if path.is_relative_to(Path(pair[1]))]
        if not matching or matching[-1][1:] != ('--ro-bind',next(pair for pair in projection if pair[1]==target)):refuse()


def verify_package(engine_root, attestation_path, authorization_path):
    """Review and operator authorization bind bytes, not caller idle flags."""
    from .suite_runner import _identity
    att=json_object(read_file(attestation_path));auth=json_object(read_file(authorization_path))
    if (set(att) != {'schema_version','owner','task_scope','historical_identity',
                    'request_id','request_digest','files','historical_paths','task_binding'}
            or att['schema_version'] != 'DshLegacyTransportAttestationV1'
            or not isinstance(att['files'],dict) or set(att['files']) != FILES
            or not isinstance(att['historical_paths'],dict)
            or set(att['historical_paths']) != FILES-{'manifest'}):refuse()
    if (set(auth) != {'schema_version','purpose','approved','authorized_effects',
                     'new_provider_requests','state_root','owner','task_scope',
                     'historical_identity','implementation_identity','attestation_digest',
                     'review_binding','plan_binding'}
            or auth['schema_version'] != 'DshLegacyRetirementAuthorizationV1'
            or auth['purpose'] != 'legacy-observed-transport-retirement'
            or auth['approved'] is not True
            or auth['authorized_effects'] != ['local-settlement','legacy-backend-retirement']
            or type(auth['new_provider_requests']) is not int or auth['new_provider_requests'] != 0
            or auth['attestation_digest'] != digest_json(att)
            or any(auth[key] != att[key] for key in ('owner','task_scope','historical_identity'))):
        refuse('backend_legacy_authorization_required')
    snapshot,validator=_identity(Path(engine_root))
    implementation={'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}
    if (not snapshot.is_usable or snapshot.unstable
            or auth['implementation_identity'] != implementation):refuse('backend_legacy_identity_drift')
    plan_raw=read_bound(auth['plan_binding']);plan=json_object(plan_raw)
    review_raw=read_bound(auth['review_binding']);review=json_object(review_raw)
    expected_plan = {'schema_version':'DshLegacyRetirementPlanV1',
                 'attestation_digest':digest_json(att),'owner':att['owner'],
                 'task_scope':att['task_scope'],'historical_identity':att['historical_identity'],
                 'implementation_identity':implementation,'new_provider_requests':0}
    if (set(plan) != set(expected_plan) | {'execution_files','commands'}
            or any(plan[key] != value for key,value in expected_plan.items())
            or not isinstance(plan['execution_files'],dict)
            or set(plan['execution_files']) != EXECUTION_FILE_KEYS
            or not isinstance(plan['commands'],dict)
            or set(plan['commands']) != {'settlement','retirement'}
            or any(not isinstance(command,list) or not command
                   or any(not isinstance(part,str) or not part for part in command)
                   for command in plan['commands'].values())
            or review != {'schema_version':'DshLegacyRetirementReviewV1','decision':'PASS',
                 'plan_digest':digest_bytes(plan_raw),'attestation_digest':digest_json(att),
                 'implementation_identity':implementation,
                 'eof_producer_protocol':'fetch-reader-done/archive-before-error-v1',
                 'eof_producer_digest':att['files']['producer']['bytes_digest']}):
        refuse('backend_legacy_review_required')
    for binding in plan['execution_files'].values():
        read_bound(binding)
    verify_execution_mounts(plan)
    raw={key:read_bound(value) for key,value in att['files'].items()}
    manifest=strict_json_loads(raw['manifest'],max_bytes=32 << 20)
    if not isinstance(manifest,list):refuse()
    entries={}
    for row in manifest:
        if (not isinstance(row,dict) or set(row) != {'path','bytes_digest','byte_length'}
                or row['path'] in entries):refuse()
        entries[row['path']]=row
    for key,historical in att['historical_paths'].items():
        binding=att['files'][key]
        if entries.get(historical) != {**binding,'path':historical}:refuse()
    return att,auth,raw,{'authorization_digest':digest_json(auth),
        'review_digest':digest_bytes(review_raw),'plan_digest':digest_bytes(plan_raw),
        'implementation_identity':implementation}


def verify_stream(raw: bytes, model: str, *, expected_finish: str = 'tool_calls'):
    if expected_finish not in {'tool_calls', 'stop'}:refuse()
    lines=[line for line in raw.splitlines() if line]
    if (not lines or lines[-1] != b'data: [DONE]'
            or any(not line.startswith(b'data: ') for line in lines)
            or sum(line == b'data: [DONE]' for line in lines) != 1):refuse()
    events=[json_object(line[6:]) for line in lines[:-1]]
    if not events or len({event.get('id') for event in events}) != 1:refuse()
    if any(not isinstance(e.get('id'),str) or not e['id'] or e.get('model') != model for e in events):refuse()
    usage=[e['usage'] for e in events if e.get('usage') is not None]
    if (len(usage) != 1 or not isinstance(usage[0],dict)
            or any(type(usage[0].get(k)) is not int for k in ('prompt_tokens','completion_tokens','total_tokens'))
            or usage[0]['prompt_tokens'] <= 0 or usage[0]['completion_tokens'] < 0
            or usage[0]['total_tokens'] != usage[0]['prompt_tokens']+usage[0]['completion_tokens']):refuse()
    calls={};finishes=[];finished=False
    for event in events:
        choices=event.get('choices')
        if not isinstance(choices,list) or len(choices)>1 or (finished and choices):refuse()
        for choice in choices:
            if not isinstance(choice,dict):refuse()
            if type(choice.get('index')) is not int or choice['index'] != 0:refuse()
            delta=choice.get('delta',{})
            if not isinstance(delta,dict):refuse()
            for tool in delta.get('tool_calls',[]):
                if not isinstance(tool,dict) or finished or type(tool.get('index')) is not int or tool['index'] != 0:refuse()
                call=calls.setdefault(0,{'ids':set(),'name':'','arguments':''})
                if tool.get('id'):call['ids'].add(tool['id'])
                function=tool.get('function',{})
                if not isinstance(function,dict):refuse()
                for field in ('name','arguments'):
                    value=function.get(field,'')
                    if not isinstance(value,str):refuse()
                    call[field]+=value
            if choice.get('finish_reason') is not None:
                finishes.append(choice['finish_reason']);finished=True
    if finishes != [expected_finish] or len(calls) != 1:refuse()
    call=calls[0]
    if len(call['ids']) != 1 or not call['name'] or not call['arguments']:refuse()
    return call['arguments'].encode(),next(iter(call['ids'])),call['name'],usage[0]


def verify_session(raw, session_id, arguments, call_id, name, usage, *, reserved_input_tokens):
    rows=[json_object(line) for line in raw.splitlines()]
    if not rows or rows[0].get('type') != 'session' or rows[0].get('version') != 4 or rows[0].get('id') != session_id:refuse()
    seq=[r.get('seq') for r in rows[1:]]
    if any(type(s) is not int for s in seq) or seq != sorted(set(seq)):refuse()
    attempts=[r for r in rows if r.get('type')=='assistant/attempt']
    if len(attempts) != 1 or any(r.get('type') in {'tool/call','assistant/message'} for r in rows):refuse()
    attempt=attempts[0];data=attempt.get('data',{});stream=data.get('stream')
    if type(data.get('turn')) is not int or type(data.get('step')) is not int or not isinstance(stream,list):refuse()
    if any(not isinstance(x,dict) or (x.get('type')=='chunk' and not isinstance(x.get('chunk'),dict)) for x in stream):refuse()
    chunks=[(i,x['chunk']) for i,x in enumerate(stream) if x.get('type')=='chunk']
    batch=[(i,x) for i,x in enumerate(stream) if x.get('type')=='tool-call-chunks']
    used=[(i,x) for i,x in chunks if x.get('type')=='usage']
    finished=[(i,x) for i,x in chunks if x.get('type')=='finish']
    if (len(batch) != 1 or len(used) != 1 or len(finished) != 1
            or any(x.get('type')=='block-end' for _,x in chunks)):refuse()
    i,tool=batch[0];j,used_chunk=used[0];k,finish=finished[0]
    if (not i<j<k or k != len(stream)-1 or tool.get('id') != call_id or tool.get('name') != name
            or type(tool.get('index')) is not int or not isinstance(tool.get('args'),list)
            or any(not isinstance(x,str) for x in tool['args'])
            or ''.join(tool['args']).encode() != arguments):refuse()
    starts=[(n,x) for n,x in chunks if x.get('type')=='block-start' and x.get('blockType')=='tool-call']
    if len(starts) != 1 or starts[0][0] >= i or starts[0][1].get('index') != tool['index']:refuse()
    if used_chunk.get('usage') != {'inputTokens':usage['prompt_tokens'],'outputTokens':usage['completion_tokens'],'totalTokens':usage['total_tokens']}:refuse()
    reason=finish.get('reason')
    if (type(reserved_input_tokens) is not int or reserved_input_tokens <= 0
            or reserved_input_tokens == usage['prompt_tokens']):refuse()
    failure = {'code':'PI_AI_ERROR','message':
        f"actual usage must match exact-wire tokenizer\n\n{usage['prompt_tokens']} !== {reserved_input_tokens}\n"}
    if reason != {'kind':'error','failure':failure}:refuse()
    def event(kind):
        selected=[r for r in rows if r.get('type')==kind]
        if len(selected) != 1:return None
        return selected[0]
    start,step,end,closed=[event(kind) for kind in ('turn/start','step/start','step/end','turn/end')]
    if (any(x is None for x in (start,step,end,closed))
            or not start['seq']<step['seq']<attempt['seq']<end['seq']<closed['seq']
            or any(x.get('data',{}).get('turn') != data['turn'] for x in (start,step,end,closed))
            or any(x.get('data',{}).get('step') != data['step'] for x in (step,end))
            or closed.get('data',{}).get('reason') != {'kind':'error','error':reason['failure']}):refuse()


def verify_historical_transport(att,raw,task, *, reserved_input_tokens):
    packet,descriptor,bootstrap,original,started,launch,dispatch,wire,provider,cleanup=[json_object(raw[k])
        for k in ('packet','descriptor','bootstrap','original_authorization','live_started','launch','dispatch','wire','provider','cleanup')]
    old=att['historical_identity'];composition=bootstrap.get('composition',{})
    calibration=json_object(raw['calibration'])
    if (set(old) != {'engine_digest','validator_digest','composition_digest'}
            or any(composition.get(k) != value for k,value in old.items())
            or packet.get('engine_digest') != old['engine_digest']
            or descriptor.get('composition_digest') != old['composition_digest']
            or descriptor.get('scope') != att['task_scope']
            or bootstrap.get('scope') != att['task_scope']
            or original.get('schema_version') != 'L01OperatorAuthorizationV1'
            or original.get('approved') is not True or original.get('primary_requests') != 1
            or original.get('retries') != 0 or original.get('packet_digest') != digest_bytes(raw['packet'])
            or original.get('model') != wire.get('model')
            or started.get('authorization') != att['files']['original_authorization']
            or launch.get('mode') != 'live' or launch.get('inference_authorized') is not True
            or dispatch.get('requests') != 1 or dispatch.get('body') != att['files']['wire']
            or calibration.get('actual_provider_body') != att['files']['wire']
            or calibration.get('calibration_sends') != 1):refuse()
    args,call_id,name,usage=verify_stream(raw['sse'],wire['model'])
    tools=wire.get('tools',[])
    if not any(t.get('function',{}).get('name')==name for t in tools):refuse()
    if provider != {'http_status':200,'usage':usage,'finish_reasons':['tool_calls']}:refuse()
    binding=task['binding']
    if (not isinstance(binding,dict) or set(binding) != {'child_id','session_id'}
            or any(not isinstance(v,str) or not v for v in binding.values())
            or binding != att['task_binding']):refuse()
    verify_session(raw['session'],binding['session_id'],args,call_id,name,usage,
                   reserved_input_tokens=reserved_input_tokens)
    sentinel=cleanup.get('sentinel',{})
    if (cleanup.get('worker_scope_quiescent') is not True or cleanup.get('errors') != []
            or cleanup.get('remote_provider_quiescence') != 'stream ended'
            or sentinel.get('state') != 'closed' or sentinel.get('probe_refused') is not True
            or type(sentinel.get('model_calls')) is not int or sentinel['model_calls'] != 0
            or type(sentinel.get('network_calls')) is not int or sentinel['network_calls'] != 0):refuse()
    return bootstrap,args,usage,calibration['loop']


def validate_legacy_release_receipt(value):
    if (set(value) != LEGACY_RECEIPT_KEYS or value.get('operation') != 'legacy-observed-transport-retirement'
            or value.get('schema_version') != 'DshLegacySerialBackendReleaseV1'
            or value.get('receipt_digest') != digest_json({k:v for k,v in value.items() if k!='receipt_digest'})
            or type(value.get('released_at_ms')) is not int or value['released_at_ms'] <= 0):refuse('backend_release_history_invalid')
    owner=value['owner'];scope=value['task_scope']
    if (not isinstance(owner,dict) or set(owner) != {'schema_version','execution_id','run_root','resource_key'}
            or owner['schema_version'] != 'serial-backend-admission/1'
            or any(not isinstance(owner[k],str) or not owner[k] for k in ('execution_id','run_root','resource_key'))
            or not Path(owner['run_root']).is_absolute()
            or not isinstance(scope,dict) or set(scope) != {'execution_id','task_id','task_epoch'}
            or scope['execution_id'] != owner['execution_id']
            or not isinstance(scope['task_id'],str) or not scope['task_id']
            or type(scope['task_epoch']) is not int or scope['task_epoch'] < 0):refuse('backend_release_history_invalid')
    digests=[value[k] for k in ('attestation_digest','authorization_digest','review_digest','plan_digest',
                              'task_view_digest','ledger_digest','budget_digest')]
    for identity,keys in ((value['historical_identity'],{'engine_digest','validator_digest','composition_digest'}),
                          (value['implementation_identity'],{'engine_digest','validator_digest'})):
        if not isinstance(identity,dict) or set(identity) != keys:refuse('backend_release_history_invalid')
        digests.extend(identity.values())
    if any(not isinstance(d,str) or re.fullmatch(r'sha256:[0-9a-f]{64}',d) is None for d in digests):
        refuse('backend_release_history_invalid')


def verify_reserved_request_material(store, contract, actual_ref, request_digest, loop, wire):
    """Reapply the original reserve owner's immutable assembly contract."""
    if actual_ref.semantic_digest != request_digest:refuse()
    projection=parse_model(canonical_json_bytes(store.read_json(parse_model(
        canonical_json_bytes(contract['dsh_wire_contract_ref']),ArtifactRefV1))),WriterWireProjectionV1)
    equivalence=parse_model(canonical_json_bytes(store.read_json(projection.wire_equivalence_ref)),WriterWireEquivalenceV1)
    if store.read_json(equivalence.loop_request_ref) != loop or store.read(equivalence.provider_wire_ref) != wire:refuse()
    from .invocation_adapter import _assembly_material
    if (_assembly_material(store.read_json(actual_ref),equivalence.transport_whitelist)
            != _assembly_material(loop,equivalence.transport_whitelist)):refuse()


def retire_legacy_observed_transport(owner, *, engine_root, attestation_path, authorization_path):
    from .task_store import TaskStore
    from .suite_runner import _identity
    att,auth,raw,authority=verify_package(engine_root,attestation_path,authorization_path)
    scope=TaskScope(**att['task_scope']);root=Path(att['owner']['run_root']).resolve(strict=True)
    expected={'schema_version':'serial-backend-admission/1','execution_id':scope.execution_id,
              'run_root':str(root),'resource_key':owner.resource_key}
    if att['owner'] != expected or auth['state_root'] != str(owner.root):refuse('backend_legacy_owner_mismatch')
    with scoped_run_lease(root,execution_id=scope.execution_id,blocking=True):
        task=TaskStore.read_persisted(root,scope)
        if (task['state'] != 'cancelled' or task['receipt'] is not None
                or task['captured_source'] is not None or task['provider_quiescence'] is not None
                or task['grant_mode'] != 'settlement-only' or not task['binding']):refuse('backend_legacy_task_state_invalid')
        with sqlite3.connect((root/'dsh-tasks.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] != 1:refuse('backend_legacy_task_state_invalid')
        ledger=root/'artifacts/06_authoring/invocations'
        paths=list(ledger.glob('*/attempt-0001.dsh-event-000001.json'))
        if len(paths) != 1:refuse()
        facts=read_dsh_invocation_events(ledger,json_object(paths[0].read_bytes())['invocation_id'])
        if not facts or not task['claim_lineage'] or facts[0].claim_digest != task['claim_lineage'][0]:refuse()
        bootstrap,args,usage,loop=verify_historical_transport(att,raw,task,
            reserved_input_tokens=facts[0].reserved_input_tokens)
        config=bootstrap['composition_spec']['effective_config']
        if (bootstrap.get('artifact_root') != str(root) or config.get('backend_state_root') != str(owner.root)
                or config.get('backend_resource_key') != owner.resource_key):refuse('backend_legacy_owner_mismatch')
        budget=read_run_budget_state(ledger)
        if (budget['status'] != 'pass' or budget['provider_usage_status'] != 'validated'
                or budget['failure_codes'] or budget['pending_call_count'] or budget['pending_input_tokens']
                or budget['provider_usage_missing_call_count'] or budget['provider_usage_missing_input_tokens']
                or budget['provider_usage_missing_receipts'] or budget['call_count'] != 1
                or budget['completed_call_count'] != 1 or budget['spent_input_tokens'] != usage['prompt_tokens']):
            refuse('backend_release_accounting_unsettled')
        if ([(f.kind) for f in facts] != ['reserve','dispatch-recorded','adapter-attempt','usage','cancel','terminal','settlement']
                or facts[0].invocation_id != att['request_id'] or facts[0].request_digest != att['request_digest']
                or any((f.execution_id,f.task_id,f.task_epoch)!=(scope.execution_id,scope.task_id,scope.task_epoch) for f in facts)
                or facts[3].usage_input_tokens != usage['prompt_tokens']
                or facts[3].usage_output_tokens != usage['completion_tokens']):refuse()
        store=ArtifactStore.open_readonly(root,scope)
        descriptor=json_object(raw['descriptor'])
        frozen=store.read_json(parse_model(canonical_json_bytes(descriptor['frozen_ref']),ArtifactRefV1))
        contract=store.read_json(parse_model(canonical_json_bytes(task['prepared']['contract_ref']),ArtifactRefV1))
        if (not isinstance(frozen,dict) or frozen.get('schema_version') != 'FrozenWriterInputV1'
                or frozen.get('snapshot_digest') != task['prepared']['snapshot_digest']
                or not isinstance(frozen.get('identity'),dict)
                or any(frozen['identity'].get(k) != v for k,v in att['historical_identity'].items())
                or not isinstance(contract,dict)
                or facts[0].contract_digest != contract.get('task_digest')):refuse()
        reserved=store.read_json(parse_model(canonical_json_bytes(facts[0].evidence_ref),ArtifactRefV1))
        if not isinstance(reserved,dict) or reserved.get('schema_version') != 'DshReserveEvidenceV1':refuse()
        actual_ref=parse_model(canonical_json_bytes(reserved['actual_request_ref']),ArtifactRefV1)
        # Reuse the original reserve owner's frozen transport whitelist. Local
        # session/message ids differ between calibration and the actual child;
        # model-facing content, tools and options remain compared in full.
        verify_reserved_request_material(store,contract,actual_ref,att['request_digest'],loop,raw['wire'])
        finish=[store.read_json(parse_model(canonical_json_bytes(f.evidence_ref),ArtifactRefV1)) for f in facts[-2:]]
        observation=finish[0]
        if (observation != finish[1] or set(observation) != {'schema_version','request_digest','finish_reason','stream_complete','raw_ref','session_ref'}
                or observation['schema_version'] != 'DshFinishObservationV1'
                or observation['request_digest'] != att['request_digest'] or observation['finish_reason'] != 'tool_calls'
                or observation['stream_complete'] is not True
                or store.read(parse_model(canonical_json_bytes(observation['raw_ref']),ArtifactRefV1)) != args
                or store.read(parse_model(canonical_json_bytes(observation['session_ref']),ArtifactRefV1)) != raw['session']):refuse()
        binding={'operation':'legacy-observed-transport-retirement','owner':expected,'task_scope':att['task_scope'],
                 'attestation_digest':digest_json(att),**authority,'historical_identity':att['historical_identity']}
        key=digest_json(binding)
        snapshot,validator=_identity(Path(engine_root))
        if snapshot.unstable or not snapshot.is_usable or binding['implementation_identity'] != {
                'engine_digest':snapshot.source_digest,'validator_digest':validator.digest}:refuse('backend_legacy_identity_drift')
        with owner._transaction() as db:
            row=db.execute('SELECT owner FROM admission WHERE resource=?',(owner.resource_key,)).fetchone()
            if row is not None and row[0] != canonical_json_bytes(expected):refuse('backend_release_owner_mismatch')
            db.execute('CREATE TABLE IF NOT EXISTS release_history (release_key TEXT PRIMARY KEY, receipt BLOB NOT NULL)')
            retired=owner._released_owner(db,expected)
            previous=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
            if previous:
                if row is not None:refuse('backend_release_owner_reacquired')
                value=json_object(previous[0])
                projection=owner._release_binding(value,key)
                if projection != binding:refuse('backend_release_history_invalid')
                return value
            if row is None or retired:refuse('backend_release_owner_missing')
            receipt={'schema_version':'DshLegacySerialBackendReleaseV1',**binding,'task_view_digest':digest_json(task),
                     'ledger_digest':digest_json([f.model_dump(mode='json') for f in facts]),
                     'budget_digest':digest_json(budget),'released_at_ms':time.time_ns()//1_000_000}
            receipt['receipt_digest']=digest_json(receipt);validate_legacy_release_receipt(receipt)
            db.execute('INSERT INTO release_history VALUES (?,?)',(key,canonical_json_bytes(receipt)))
            if db.execute('DELETE FROM admission WHERE resource=? AND owner=?',(owner.resource_key,canonical_json_bytes(expected))).rowcount != 1:
                refuse('backend_release_owner_mismatch')
            return receipt
