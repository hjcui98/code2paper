"""Durable single-Writer lifecycle; contains no token balance or debit reducer.

Claims never expire on a clock/PID heuristic. A crashed holder is recovered
using its private capability, or explicitly retired after positive quiescence.
Content fences belong to the publication owner; claim fences are independent.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import secrets
import re
import sqlite3
import time
from typing import Any

from code2paper.agentic.authoring_execution_identity import scoped_run_lease
from code2paper.agentic.digest import canonical_json_bytes, digest_json
from .artifacts import ArtifactStore, TaskScope
from .protocol import ProtocolError, parse_model, strict_json_loads
from .writer_contract import ArtifactRefV1


class SerialBackendAdmission:
    """One persistent run owner per configured backend resource.

    This is lifecycle admission, not a scheduler or fee ledger. The operator
    supplies the shared state root and resource key. No PID/TTL eviction exists.
    A completed, observed stream can release its exact owner only after the
    original invocation adapter has settled its bound finish evidence. Other
    owners, open tasks and unknown sends never gain a release capability.
    """
    def __init__(self, state_root: Path, resource_key: str):
        if not resource_key or len(resource_key) > 256:
            raise ProtocolError("backend_resource_key_invalid")
        self.root = Path(state_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "serial-backend.sqlite3"
        self.resource_key = resource_key
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS admission (resource TEXT PRIMARY KEY, owner BLOB NOT NULL)")

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def acquire(self, *, execution_id: str, run_root: Path) -> dict[str, Any]:
        owner = {"schema_version": "serial-backend-admission/1", "execution_id": execution_id,
                 "run_root": str(Path(run_root).resolve()), "resource_key": self.resource_key}
        raw = canonical_json_bytes(owner)
        with self._transaction() as db:
            if self._released_owner(db,owner):raise ProtocolError('backend_owner_retired')
            db.execute("INSERT OR IGNORE INTO admission VALUES (?,?)", (self.resource_key, raw))
            stored = db.execute("SELECT owner FROM admission WHERE resource=?", (self.resource_key,)).fetchone()[0]
            if stored != raw:
                raise ProtocolError("backend_run_admission_held")
            return owner

    @staticmethod
    def _release_binding(value, key):
        """Validate each history row's schema and immutable key projection."""
        if not isinstance(value,dict):raise ProtocolError('backend_release_history_invalid')
        if value.get('schema_version') == 'DshLegacySerialBackendReleaseV1':
            from .legacy_retirement import validate_legacy_release_receipt,LEGACY_BINDING_KEYS
            validate_legacy_release_receipt(value)
            projection={k:value[k] for k in LEGACY_BINDING_KEYS}
        elif value.get('schema_version') == 'DshNativeRejectedBackendReleaseV1':
            from .native_rejection_retirement import validate_receipt,BINDING_KEYS
            validate_receipt(value)
            projection={k:value[k] for k in BINDING_KEYS}
        elif value.get('schema_version') == 'DshNativeStopBackendReleaseV1':
            from .native_stop_retirement import validate_receipt,BINDING_KEYS
            validate_receipt(value)
            projection={k:value[k] for k in BINDING_KEYS}
        elif value.get('schema_version') == 'DshUnknownToolBackendReleaseV1':
            from .unknown_tool_retirement import validate_receipt,BINDING_KEYS
            validate_receipt(value)
            projection={k:value[k] for k in BINDING_KEYS}
        elif value.get('schema_version') == 'DshUnknownAbortBackendReleaseV1':
            from .unknown_abort_recovery import validate_receipt,BINDING_KEYS
            validate_receipt(value)
            projection={k:value[k] for k in BINDING_KEYS}
        elif value.get('schema_version') == 'DshTextStopBackendReleaseV1':
            from .text_stop_recovery import validate_receipt,BINDING_KEYS
            validate_receipt(value)
            projection={k:value[k] for k in BINDING_KEYS}
        elif value.get('schema_version') in {'DshSerialBackendReleaseV1','DshEpochSerialBackendReleaseV2'}:
            keys={'schema_version','owner','task_scope','quiescence_ref','task_state',
                  'task_view_digest','budget_digest','released_at_ms','receipt_digest'}
            if (set(value) != keys or value['task_state'] not in {'cancelled','terminal'}
                    or type(value['released_at_ms']) is not int or value['released_at_ms'] <= 0
                    or any(not isinstance(value[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',value[k])
                           for k in ('task_view_digest','budget_digest','receipt_digest'))):
                raise ProtocolError('backend_release_history_invalid')
            scope=value['task_scope'];owner=value['owner']
            if (not isinstance(scope,dict) or set(scope) != {'execution_id','task_id','task_epoch'}
                    or type(scope['task_epoch']) is not int or scope['task_epoch'] < 0
                    or not isinstance(owner,dict) or set(owner) != {'schema_version','execution_id','run_root','resource_key'}
                    or owner['schema_version'] != 'serial-backend-admission/1'
                    or any(not isinstance(owner[k],str) or not owner[k] for k in ('execution_id','run_root','resource_key'))
                    or not Path(owner['run_root']).is_absolute()
                    or scope['execution_id'] != owner['execution_id']
                    or not isinstance(scope['task_id'],str) or not scope['task_id']):
                raise ProtocolError('backend_release_history_invalid')
            ref=parse_model(canonical_json_bytes(value['quiescence_ref']),ArtifactRefV1)
            if any(getattr(ref,k) != scope[k] for k in ('execution_id','task_id','task_epoch')):
                raise ProtocolError('backend_release_history_invalid')
            projection={k:value[k] for k in ('owner','task_scope','quiescence_ref')}
        else:
            raise ProtocolError('backend_release_history_invalid')
        if (value.get('receipt_digest') != digest_json({k:v for k,v in value.items() if k!='receipt_digest'})
                or digest_json(projection) != key):
            raise ProtocolError('backend_release_history_invalid')
        return projection

    @staticmethod
    def _released_owner(db,expected):
        if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='release_history'").fetchone():
            return False
        retired=False
        for key,raw in db.execute('SELECT release_key,receipt FROM release_history'):
            value=strict_json_loads(raw)
            SerialBackendAdmission._release_binding(value,key)
            retired=retired or value.get('owner') == expected
        return retired

    def retire_legacy_observed_transport(self, *, engine_root: Path,
            attestation_path: Path, authorization_path: Path) -> dict[str, Any]:
        """Operator-only historical migration; never a Worker/model RPC.

        This does not mint execute-time observations or settle fees. The old
        composition must already have settled the same failed invocation.
        A separately reviewed, explicitly authorized transport package is the
        authority for this distinct retirement operation.
        """
        from .legacy_retirement import retire_legacy_observed_transport
        return retire_legacy_observed_transport(self, engine_root=engine_root,
            attestation_path=attestation_path,authorization_path=authorization_path)

    def authorize_observed_owner(self, *, execution_id: str, run_root: Path, local_replay: bool):
        """Observe an execution permit, or its retirement for local work only.

        Status, replay and settlement never INSERT an admission row. A retired
        execution can read its original facts while a different run owns the engine.
        """
        expected={'schema_version':'serial-backend-admission/1','execution_id':execution_id,
            'run_root':str(Path(run_root).resolve()),'resource_key':self.resource_key}
        try:
            with sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True) as db:
                db.execute('PRAGMA query_only=ON')
                row=db.execute('SELECT owner FROM admission WHERE resource=?',(self.resource_key,)).fetchone()
                if row is not None and row[0] == canonical_json_bytes(expected):return
                if local_replay and self._released_owner(db,expected):return
        except sqlite3.Error as error:
            raise ProtocolError('backend_admission_observation_invalid') from error
        raise ProtocolError('backend_run_admission_held')

    @classmethod
    def read_persisted(cls, state_root: Path, resource_key: str) -> dict[str, Any]:
        root=Path(state_root).resolve(strict=True)
        try:
            with sqlite3.connect((root/'serial-backend.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                db.execute('PRAGMA query_only=ON')
                row=db.execute('SELECT owner FROM admission WHERE resource=?',(resource_key,)).fetchone()
        except sqlite3.Error as error:
            raise ProtocolError('backend_admission_observation_invalid') from error
        owner=strict_json_loads(row[0]) if row else None
        if owner is not None and (not isinstance(owner,dict)
                or set(owner) != {'schema_version','execution_id','run_root','resource_key'}
                or owner['schema_version'] != 'serial-backend-admission/1'
                or owner['resource_key'] != resource_key
                or not isinstance(owner['execution_id'],str) or not owner['execution_id']
                or not isinstance(owner['run_root'],str) or not Path(owner['run_root']).is_absolute()):
            raise ProtocolError('backend_admission_observation_invalid')
        return {'state_root':str(root),'resource_key':resource_key,
            'state':'owned' if owner else 'empty','owner':owner}

    def release_observed_finish(self, *, run_root: Path, scope: TaskScope,
                                quiescence_ref: ArtifactRefV1) -> dict[str, Any]:
        """Private Host release for an original, locally settled finish.

        The private gated-adapter completion owner archives its naturally
        exhausted stream and the actual flushed Session. A domain receipt,
        arbitrary nonempty artifacts, or a caller finish/idle flag is insufficient.
        """
        from code2paper.agentic.unified_invocation_ledger import read_run_budget_state,read_dsh_invocation_events
        from .artifacts import ArtifactStore
        root=Path(run_root).resolve(strict=True)
        expected={'schema_version':'serial-backend-admission/1','execution_id':scope.execution_id,
            'run_root':str(root),'resource_key':self.resource_key}
        with scoped_run_lease(root,execution_id=scope.execution_id,blocking=True):
            task=TaskStore.read_persisted(root,scope)
            if task['state'] not in {'cancelled','terminal'}:
                raise ProtocolError('backend_release_task_open')
            with sqlite3.connect((root/'dsh-tasks.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                if db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0] != 1:
                    raise ProtocolError('backend_release_serial_task_scope_required')
            ledger=root/'artifacts/06_authoring/invocations'
            budget=read_run_budget_state(ledger)
            store=ArtifactStore.open_readonly(root,scope)
            finish=store.read_json(quiescence_ref)
            epoch_mode=isinstance(finish,dict) and finish.get('schema_version')=='DshEpochProviderQuiescenceV2'
            completed_count=len(finish['steps']) if epoch_mode and isinstance(finish.get('steps'),list) else 1
            if (budget['status'] != 'pass' or budget['provider_usage_status'] != 'validated'
                    or budget['failure_codes'] or budget['pending_call_count'] or budget['pending_input_tokens']
                    or budget['provider_usage_missing_call_count'] or budget['provider_usage_missing_input_tokens']
                    or budget['provider_usage_missing_receipts']
                    or budget['call_count'] != completed_count or budget['completed_call_count'] != completed_count):
                raise ProtocolError('backend_release_accounting_unsettled')
            store=ArtifactStore.open_readonly(root,scope)
            if (task['provider_quiescence'] is None
                    or task['provider_quiescence']['quiescence_ref'] != quiescence_ref.model_dump(mode='json')):
                raise ProtocolError('backend_release_owner_observation_required')
            if epoch_mode:
                from .epoch_completion import verify_epoch_quiescence
                from .writer_contract import parse_writer_contract
                from types import SimpleNamespace
                tasks=object.__new__(TaskStore);tasks.root=root;tasks.scope=scope;tasks.path=root/'dsh-tasks.sqlite3'
                contract=parse_writer_contract(canonical_json_bytes(store.read_json(parse_model(canonical_json_bytes(task['prepared']['contract_ref']),ArtifactRefV1))))
                facade=SimpleNamespace(store=store,task_store=tasks,current_state=lambda:None)
                verify_epoch_quiescence(facade,contract,finish,require_settlement=True)
            else:
                self._verify_single_release_finish(store,task,finish,ledger,scope)
            binding={'owner':expected,'task_scope':scope.__dict__,
                'quiescence_ref':quiescence_ref.model_dump(mode='json')}
            key=digest_json(binding)
            with self._transaction() as db:
                row=db.execute('SELECT owner FROM admission WHERE resource=?',(self.resource_key,)).fetchone()
                if row is not None and row[0] != canonical_json_bytes(expected):
                    raise ProtocolError('backend_release_owner_mismatch')
                db.execute('CREATE TABLE IF NOT EXISTS release_history (release_key TEXT PRIMARY KEY, receipt BLOB NOT NULL)')
                self._released_owner(db,expected)
                previous=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
                if previous:
                    if row is not None:raise ProtocolError('backend_release_owner_reacquired')
                    value=strict_json_loads(previous[0])
                    if self._release_binding(value,key) != binding:
                        raise ProtocolError('backend_release_history_invalid')
                    return value
                if row is None:raise ProtocolError('backend_release_owner_missing')
                receipt={'schema_version':'DshEpochSerialBackendReleaseV2' if epoch_mode else 'DshSerialBackendReleaseV1',**binding,
                    'task_state':task['state'],'task_view_digest':digest_json(task),
                    'budget_digest':digest_json(budget),'released_at_ms':time.time_ns()//1_000_000}
                receipt['receipt_digest']=digest_json(receipt)
                db.execute('INSERT INTO release_history VALUES (?,?)',(key,canonical_json_bytes(receipt)))
                changed=db.execute('DELETE FROM admission WHERE resource=? AND owner=?',
                    (self.resource_key,canonical_json_bytes(expected))).rowcount
                if changed != 1:raise ProtocolError('backend_release_owner_mismatch')
                return receipt

    @staticmethod
    def _verify_single_release_finish(store,task,finish,ledger,scope):
        from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events
        if (not isinstance(finish,dict)
                or set(finish) != {'schema_version','execution_id','task_id','task_epoch','request_id',
                    'request_digest','session_id','source','finish_reason','raw_ref','session_ref'}
                or (finish['schema_version'],finish['source'],finish['finish_reason']) not in {
                    ('DshProviderQuiescenceV1','gated-adapter-natural-exhaustion/1','tool-calls'),
                    ('DshProviderQuiescenceV1','gated-adapter-natural-exhaustion/1','stop'),
                    ('DshRejectedTextProviderQuiescenceV1','gated-adapter-natural-text-exhaustion/1','stop'),
                    ('DshRejectedUnknownToolProviderQuiescenceV1','gated-adapter-natural-unknown-tool-exhaustion/1','tool-calls')}
                or type(finish['task_epoch']) is not int
                or any(finish[name] != getattr(scope,name) for name in ('execution_id','task_id','task_epoch'))
                or not task['binding'] or finish['session_id'] != task['binding']['session_id']):
            raise ProtocolError('backend_release_quiescence_unproven')
        matched=[]
        for path in sorted(ledger.glob('*/attempt-0001.dsh-event-000001.json')):
            row=strict_json_loads(path.read_bytes())
            facts=read_dsh_invocation_events(ledger,row['invocation_id'])
            if (facts[0].request_digest==finish['request_digest']
                    and facts[0].invocation_id==finish['request_id']):matched.append(facts)
        if len(matched) != 1:raise ProtocolError('backend_release_finish_binding_invalid')
        facts=matched[0]
        if ((facts[0].execution_id,facts[0].task_id,facts[0].task_epoch) !=
                (scope.execution_id,scope.task_id,scope.task_epoch)
                or any(len([f for f in facts if f.kind==kind]) != 1 for kind in ('usage','terminal','settlement'))):
            raise ProtocolError('backend_release_finish_binding_invalid')
        SerialBackendAdmission._verify_native_quiescence(store,task,finish,facts)

    @staticmethod
    def _verify_native_quiescence(store,task,finish,facts,*,require_settlement=True):
        """Verify owner-produced native stream/Session facts against original fees.

        This is a Host-private observation verifier, not a model-authored tool.
        Only gatedAdapter's natural-exhaustion callback may mint its source.
        """
        if finish.get('schema_version') == 'DshRejectedUnknownToolProviderQuiescenceV1':
            from .unknown_tool_completion import verify_unknown_tool_rejection
            return verify_unknown_tool_rejection(store,task,finish,facts,require_settlement=require_settlement)
        if finish.get('schema_version') == 'DshRejectedTextProviderQuiescenceV1':
            from .text_rejection_completion import verify_text_rejection
            return verify_text_rejection(store,task,finish,facts,require_settlement=require_settlement)
        def refused():raise ProtocolError('backend_release_quiescence_unproven')
        raw_ref=parse_model(canonical_json_bytes(finish['raw_ref']),ArtifactRefV1)
        session_ref=parse_model(canonical_json_bytes(finish['session_ref']),ArtifactRefV1)
        raw=store.read(raw_ref);session=store.read_json(session_ref)
        captured=task['captured_source']
        if (not raw or not captured or type(captured.get('stream_index')) is not int or captured['stream_index'] != 1
                or captured['request_id'] != finish['request_id']
                or captured['session_id'] != finish['session_id']
                or captured['arguments_ref'] != finish['raw_ref']
                or not isinstance(session,dict)
                or set(session) != {'schema_version','session_id','format_version','events'}
                or session['schema_version'] != 'DshSessionCaptureV1'
                or session['format_version'] != 'SessionFileV4'
                or session['session_id'] != finish['session_id']
                or not isinstance(session['events'],list)):refused()
        events=session['events']
        if (not events or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
                or any(a['seq'] >= b['seq'] for a,b in zip(events,events[1:]))):refused()
        messages=[e for e in events if e.get('type') == 'assistant/message']
        if len(messages) != 1:refused()
        event=messages[0];data=event.get('data')
        if (not isinstance(data,dict) or not isinstance(data.get('message'),dict)
                or data['message'].get('role') != 'assistant'
                or not isinstance(data['message'].get('source'),dict)
                or data['message']['source'].get('kind') != 'model'
                or type(data.get('turn')) is not int or type(data.get('step')) is not int
                or not isinstance(data.get('stream'),list)):refused()
        ends=[e for e in events if e.get('type') == 'turn/end'
            and isinstance(e.get('data'),dict) and e['data'].get('turn') == data['turn']]
        if len(ends) != 1 or ends[0]['seq'] <= event['seq']:refused()
        reason=ends[0]['data'].get('reason')
        if not isinstance(reason,dict) or reason.get('kind') not in {'completed','error','blocked'}:refused()
        for kind in ('turn/start','step/start','step/end'):
            bound=[e for e in events if e.get('type') == kind and isinstance(e.get('data'),dict)
                and e['data'].get('turn') == data['turn']
                and (kind == 'turn/start' or e['data'].get('step') == data['step'])]
            if len(bound) != 1:refused()
            if kind.endswith('start') and bound[0]['seq'] >= event['seq']:refused()
            if kind == 'step/end' and not event['seq'] < bound[0]['seq'] < ends[0]['seq']:refused()
        streams=data['stream']
        if any(not isinstance(s,dict) for s in streams):refused()
        chunks=[s['chunk'] for s in streams if s.get('type') == 'chunk' and isinstance(s.get('chunk'),dict)]
        finishes=[c for c in chunks if c.get('type') == 'finish']
        usage=[c.get('usage') for c in chunks if c.get('type') == 'usage']
        observed=next(f for f in facts if f.kind == 'usage')
        if (len(finishes) != 1 or finishes[0].get('reason') != {'kind':finish['finish_reason']}
                or len(usage) != 1 or not isinstance(usage[0],dict)
                or type(usage[0].get('inputTokens')) is not int or type(usage[0].get('outputTokens')) is not int
                or type(usage[0].get('totalTokens')) is not int
                or usage[0]['totalTokens'] != usage[0]['inputTokens']+usage[0]['outputTokens']
                or (usage[0]['inputTokens'],usage[0]['outputTokens']) !=
                    (observed.usage_input_tokens,observed.usage_output_tokens)
                or data.get('usage') != usage[0]):refused()
        args=[s for s in streams if s.get('type') == 'tool-call-chunks']
        if (not args or type(args[0].get('index')) is not int
                or any(s.get('index') != args[0]['index']
                or not isinstance(s.get('args'),list) or any(not isinstance(v,str) for v in s['args'])
                or ('id' in s and s['id'] != captured['tool_call_id'])
                or ('name' in s and s['name'] != 'c2p_terminal') for s in args)
                or ''.join(v for s in args for v in s['args']).encode('utf-8') != raw):refused()
        blocks=[c for c in chunks if c.get('type') == 'block-end'
            and c.get('index') == args[0]['index']]
        if (len(blocks) != 1 or not isinstance(blocks[0].get('block'),dict)
                or blocks[0]['block'].get('type') != 'tool-call'
                or blocks[0]['block'].get('id') != captured['tool_call_id']
                or blocks[0]['block'].get('name') != 'c2p_terminal'):refused()
        block_arguments=blocks[0]['block'].get('arguments')
        if not isinstance(block_arguments,str):refused()
        if block_arguments.encode('utf-8') != raw:
            # Separate normalized representation, never repaired Writer content.
            if digest_json(strict_json_loads(block_arguments)) != digest_json(strict_json_loads(raw)):refused()
        # A native rejection can naturally exhaust the provider while the
        # Agent ends blocked. Prove the bound tool error and its order; the
        # blocked label alone is never a completion credential.
        if reason.get('kind') == 'blocked':
            # Even identical raw/normalized strings must retain strict JSON
            # identity: duplicate keys cannot be normalized into a credential.
            strict_json_loads(raw)
            strict_json_loads(block_arguments)
            calls=[e for e in events if e.get('type') == 'tool/call']
            results=[e for e in events if e.get('type') == 'tool/result']
            step_end=next(e for e in events if e.get('type') == 'step/end'
                and e.get('data',{}).get('turn') == data['turn']
                and e.get('data',{}).get('step') == data['step'])
            if len(calls) != 1 or len(results) != 1:refused()
            call=calls[0];result=results[0]
            c=call.get('data');r=result.get('data')
            if (not isinstance(c,dict) or not isinstance(r,dict)
                    or any(type(v.get(k)) is not int or v[k] != data[k]
                        for v in (c,r) for k in ('turn','step'))
                    or c.get('callId') != captured['tool_call_id'] or c.get('name') != 'c2p_terminal'
                    or c.get('arguments') != block_arguments
                    or not event['seq'] < call['seq'] < result['seq'] < step_end['seq'] < ends[0]['seq']):refused()
            message=r.get('message')
            if (not isinstance(message,dict) or message.get('role') != 'tool'
                    or message.get('toolCallId') != captured['tool_call_id'] or message.get('isError') is not True
                    or message.get('source') != {'kind':'tool','callId':captured['tool_call_id']}
                    or result.get('sourceEventSeqs') != [call['seq']]
                    or not isinstance(message.get('content'),list)
                    or not any(isinstance(b,dict) and b.get('type') == 'text'
                        and isinstance(b.get('text'),str) and b['text'].startswith('Error: ')
                        and len(b['text']) > len('Error: ') for b in message['content'])):refused()
        block_at=next(i for i,s in enumerate(streams) if s.get('type')=='chunk' and s.get('chunk') is blocks[0])
        usage_at=next(i for i,s in enumerate(streams) if s.get('type')=='chunk' and s.get('chunk',{}).get('type')=='usage')
        finish_at=next(i for i,s in enumerate(streams) if s.get('type')=='chunk' and s.get('chunk') is finishes[0])
        if (any(i >= block_at for i,s in enumerate(streams) if s.get('type')=='tool-call-chunks')
                or not block_at < usage_at < finish_at or finish_at != len(streams)-1
                or chunks[-1] is not finishes[0]):refused()
        if not require_settlement:return
        terminal=store.read_json(parse_model(canonical_json_bytes(next(f for f in facts if f.kind=='terminal').evidence_ref),ArtifactRefV1))
        settlement=store.read_json(parse_model(canonical_json_bytes(next(f for f in facts if f.kind=='settlement').evidence_ref),ArtifactRefV1))
        if not isinstance(terminal,dict) or not isinstance(settlement,dict):refused()
        if terminal.get('schema_version') == 'RecordedWriterOutputV1':
            envelope=terminal.get('envelope',{})
            if (envelope.get('request_id') != finish['request_id']
                    or envelope.get('session_capture_ref') != finish['session_ref']
                    or envelope.get('adapter_arguments') != {'status':'observed','ref':finish['raw_ref']}):refused()
            if settlement.get('schema_version') == 'LocalWriterReceiptV1':
                if task['receipt'] != settlement:refused()
            elif settlement.get('schema_version') == 'DshRejectedOutputObservationV1':
                if (task['receipt'] is not None or settlement.get('output_ref') !=
                        next(f for f in facts if f.kind=='terminal').evidence_ref):refused()
            else:refused()
        elif terminal.get('schema_version') == 'DshFinishObservationV1':
            if (settlement != terminal or terminal.get('request_digest') != finish['request_digest']
                    or terminal.get('finish_reason') != finish['finish_reason']
                    or terminal.get('raw_ref') != finish['raw_ref']
                    or terminal.get('session_ref') != finish['session_ref']):refused()
        else:refused()

    @classmethod
    def observe_initial(cls, state_root: Path, resource_key: str, *, execution_id: str, run_root: Path):
        owner = object.__new__(cls)
        owner.root = Path(state_root).resolve(strict=True)
        owner.path = owner.root / "serial-backend.sqlite3"
        owner.resource_key = resource_key
        expected = {"schema_version":"serial-backend-admission/1", "execution_id":execution_id,
                    "run_root":str(Path(run_root).resolve()), "resource_key":resource_key}
        try:
            with sqlite3.connect(owner.path.as_uri()+"?mode=ro", uri=True) as db:
                db.execute("PRAGMA query_only=ON")
                rows = db.execute("SELECT resource,owner FROM admission ORDER BY resource").fetchall()
                if rows not in ([], [(resource_key, canonical_json_bytes(expected))]):
                    raise ProtocolError("backend_run_admission_held")
        except sqlite3.Error as error:
            raise ProtocolError("backend_admission_observation_invalid") from error
        return owner, {"state":"empty" if not rows else "owned", "owner":expected if rows else None}


class TaskStore:
    storage_version = "dsh-task-store/3"
    max_fence = (1 << 53) - 1

    def __init__(self, run_root: Path, scope: TaskScope):
        self.root = Path(run_root).resolve()
        self.scope = scope
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "dsh-tasks.sqlite3"
        with self._transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            expected = {"version": self.storage_version, "execution_id": scope.execution_id}
            for key, value in expected.items():
                db.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", (key, value))
                if db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()[0] != value:
                    raise ProtocolError("task_store_identity_mismatch")
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                task_key TEXT PRIMARY KEY, payload BLOB NOT NULL, started_ms INTEGER NOT NULL,
                state TEXT NOT NULL, fence INTEGER NOT NULL DEFAULT 0,
                owner TEXT, capability_digest TEXT, binding BLOB, receipt BLOB,
                grant_mode TEXT NOT NULL DEFAULT 'execute', claim_lineage BLOB, captured_source BLOB,
                provider_quiescence BLOB)""")
            db.execute('''CREATE TABLE IF NOT EXISTS content_invalidations (
                task_key TEXT PRIMARY KEY, payload BLOB NOT NULL)''')
            # Additive private owner record; historical readonly rows decode as None.
            if 'provider_quiescence' not in {r[1] for r in db.execute('PRAGMA table_info(tasks)')}:
                db.execute('ALTER TABLE tasks ADD COLUMN provider_quiescence BLOB')

    @contextmanager
    def _transaction(self):
        with scoped_run_lease(self.root, execution_id=self.scope.execution_id, blocking=True):
            with self._database_transaction() as db:
                yield db

    @contextmanager
    def _database_transaction(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @property
    def key(self) -> str:
        return digest_json(self.scope.__dict__)

    def _row(self, db):
        row = db.execute("SELECT * FROM tasks WHERE task_key=?", (self.key,)).fetchone()
        if row is None:
            raise ProtocolError("task_not_prepared")
        if type(row['fence']) is not int or not 0 <= row['fence'] <= self.max_fence:
            raise ProtocolError('task_store_fence_invalid')
        if row['state'] not in {'outbox','claimed','cancelled','terminal'} or row['grant_mode'] not in {'execute','settlement-only'}:
            raise ProtocolError('task_store_lifecycle_invalid')
        lineage=strict_json_loads(row['claim_lineage']) if row['claim_lineage'] is not None else []
        if (not isinstance(lineage,list) or len(lineage) != row['fence']
                or any(not isinstance(value,str) or re.fullmatch(r'sha256:[0-9a-f]{64}',value) is None for value in lineage)
                or len(set(lineage)) != len(lineage)):
            raise ProtocolError('task_store_claim_lineage_invalid')
        if 'provider_quiescence' in row.keys() and row['provider_quiescence'] is not None:
            value=strict_json_loads(row['provider_quiescence'])
            if (not isinstance(value,dict) or set(value) != {'schema_version','task_scope','claim_fence','claim_digest','quiescence_ref'}
                    or value['schema_version'] != 'DshProviderQuiescenceBindingV1'
                    or value['task_scope'] != self.scope.__dict__ or type(value['claim_fence']) is not int
                    or not 1 <= value['claim_fence'] <= row['fence']
                    or value['claim_digest'] != lineage[value['claim_fence']-1]):
                raise ProtocolError('task_provider_observation_invalid')
            ref=parse_model(canonical_json_bytes(value['quiescence_ref']),ArtifactRefV1)
            if (ref.execution_id,ref.task_id,ref.task_epoch) != (self.scope.execution_id,self.scope.task_id,self.scope.task_epoch):
                raise ProtocolError('task_provider_observation_invalid')
        return row

    @classmethod
    def _next_fence(cls, row):
        if row['fence'] == cls.max_fence:raise ProtocolError('task_claim_fence_exhausted')
        return row['fence']+1

    @staticmethod
    def _identity_key(row) -> str:
        prepared = strict_json_loads(row["payload"])
        return digest_json({key: prepared[key] for key in (
            "schema_version", "execution_id", "workflow_id", "node_id", "scope_id", "task_id", "task_epoch")})

    @staticmethod
    def _view(row) -> dict[str, Any]:
        return {"task_key": TaskStore._identity_key(row), "prepared": strict_json_loads(row["payload"]),
                "epoch_started_ms": row["started_ms"], "state": row["state"],
                "claim_fence": row["fence"], "owner": row["owner"],
                "grant_mode":row["grant_mode"],
                "claim_lineage":strict_json_loads(row["claim_lineage"]) if row["claim_lineage"] else [],
                "captured_source":strict_json_loads(row["captured_source"]) if row["captured_source"] else None,
                "provider_quiescence":strict_json_loads(row['provider_quiescence'])
                    if 'provider_quiescence' in row.keys() and row['provider_quiescence'] is not None else None,
                "binding": strict_json_loads(row["binding"]) if row["binding"] else None,
                "receipt": strict_json_loads(row["receipt"]) if row["receipt"] else None}

    def prepare(self, *, workflow_id: str, node_id: str, scope_id: str,
                contract_ref: dict[str, Any], content_revision: int,
                content_fence: int, snapshot_digest: str) -> dict[str, Any]:
        ref = parse_model(canonical_json_bytes(contract_ref), ArtifactRefV1)
        if (ref.execution_id, ref.task_id, ref.task_epoch) != (
                self.scope.execution_id, self.scope.task_id, self.scope.task_epoch):
            raise ProtocolError("task_contract_scope_mismatch")
        payload = canonical_json_bytes({"schema_version": self.storage_version,
            **self.scope.__dict__, "workflow_id": workflow_id, "node_id": node_id,
            "scope_id": scope_id, "contract_ref": contract_ref,
            "content_revision": content_revision, "content_fence": content_fence,
            "snapshot_digest": snapshot_digest})
        with self._transaction() as db:
            db.execute("INSERT OR IGNORE INTO tasks (task_key,payload,started_ms,state) VALUES (?,?,?,?)",
                       (self.key, payload, time.time_ns() // 1_000_000, "outbox"))
            row = self._row(db)
            if row["payload"] != payload:
                raise ProtocolError("task_prepare_conflict")
            return self._view(row)

    def read(self) -> dict[str, Any]:
        with self._transaction() as db:
            return self._view(self._row(db))

    def current_content_state(self, fallback: tuple[int, int, str]) -> tuple[int, int, str]:
        """Read owner invalidation without opening a nested write transaction.

        Historical tasks have no invalidation. This pointer only withdraws an
        old view; it never prepares or licenses new facts or changes fees.
        """
        with sqlite3.connect(self.path, timeout=30) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_invalidations'").fetchone() is None:
                return fallback  # historical read-only store, no owner withdrawal
            row = db.execute('SELECT payload FROM content_invalidations WHERE task_key=?',
                             (self.key,)).fetchone()
        if row is None:
            return fallback
        value = strict_json_loads(row[0])
        if (not isinstance(value, dict) or set(value) != {'schema_version', 'scope', 'previous',
                'current', 'promotion_ref'} or value['schema_version'] != 'DshContentInvalidationV1'
                or value['scope'] != self.scope.__dict__
                or not isinstance(value['previous'], list) or len(value['previous']) != 3
                or not isinstance(value['current'], list) or len(value['current']) != 3):
            raise ProtocolError('content_invalidation_invalid')
        previous, current = value['previous'], value['current']
        if (any(type(v) is not int or not 0 <= v < self.max_fence for v in previous[:2])
                or current != [previous[0] + 1, previous[1] + 1, previous[2]]):
            raise ProtocolError('content_invalidation_invalid')
        store = ArtifactStore.open_readonly(self.root, self.scope)
        ref = parse_model(canonical_json_bytes(value['promotion_ref']), ArtifactRefV1)
        self._promoted_ledger(store, ref)
        return tuple(current)

    @staticmethod
    def _promoted_ledger(store, ref):
        # The original Python Research owner supplies its already sealed ledger.
        # This operation is absent from RPC/model tools and only invalidates.
        from code2paper.agentic.research_promotion import ObservationPromotionLedgerV1
        try:
            ledger = ObservationPromotionLedgerV1.model_validate(store.read_json(ref))
        except ValueError as error:
            raise ProtocolError('content_promotion_invalid') from error
        if not any(record.status == 'claim_promoted' for record in ledger.records):
            raise ProtocolError('content_promotion_not_complete')
        return ledger

    def invalidate_after_promotion(self, claim, *, promotion_ref: ArtifactRefV1):
        """Private original-owner handoff after Research promotion.

        Persist withdrawal for this affected task only. New content requires a
        fresh original compiler/freeze/epoch; no claim IDs extend a read grant.
        Original binding, invocation history, pending fees and slots remain.
        """
        store = ArtifactStore(self.root, self.scope)
        self._promoted_ledger(store, promotion_ref)
        with self._transaction() as db:
            row = self._row(db)
            self._authorize(row, claim)
            if row['grant_mode'] != 'execute':
                raise ProtocolError('content_promotion_execute_claim_required')
            prepared = self._view(row)['prepared']
            previous = [prepared['content_revision'], prepared['content_fence'], prepared['snapshot_digest']]
            if any(type(v) is not int or not 0 <= v < self.max_fence for v in previous[:2]):
                raise ProtocolError('content_revision_exhausted')
            value = {'schema_version': 'DshContentInvalidationV1', 'scope': self.scope.__dict__,
                     'previous': previous, 'current': [previous[0]+1, previous[1]+1, previous[2]],
                     'promotion_ref': promotion_ref.model_dump(mode='json')}
            raw = canonical_json_bytes(value)
            db.execute('INSERT OR IGNORE INTO content_invalidations VALUES (?,?)', (self.key, raw))
            if db.execute('SELECT payload FROM content_invalidations WHERE task_key=?',
                          (self.key,)).fetchone()[0] != raw:
                raise ProtocolError('content_promotion_conflict')
            return value

    def record_provider_quiescence(self,claim,ref:ArtifactRefV1):
        binding={'schema_version':'DshProviderQuiescenceBindingV1','task_scope':self.scope.__dict__,
            'claim_fence':claim['claim_fence'],'claim_digest':digest_json(claim),
            'quiescence_ref':ref.model_dump(mode='json')}
        raw=canonical_json_bytes(binding)
        with self._transaction() as db:
            row=self._row(db);self._authorize(row,claim)
            if row['grant_mode'] != 'execute':raise ProtocolError('provider_observation_execute_claim_required')
            if row['provider_quiescence'] is not None and row['provider_quiescence'] != raw:
                raise ProtocolError('provider_observation_conflict')
            db.execute('UPDATE tasks SET provider_quiescence=? WHERE task_key=?',(raw,self.key))
            return self._view(self._row(db))['provider_quiescence']

    @classmethod
    def observe_initial(cls, run_root: Path, scope: TaskScope):
        owner = object.__new__(cls)
        owner.root = Path(run_root).resolve(strict=True)
        owner.path = owner.root / "dsh-tasks.sqlite3"
        owner.scope = scope
        try:
            with sqlite3.connect(owner.path.as_uri()+"?mode=ro", uri=True) as db:
                db.execute("PRAGMA query_only=ON")
                if dict(db.execute("SELECT key,value FROM metadata")) != {
                        "version":cls.storage_version, "execution_id":scope.execution_id}:
                    raise ProtocolError("task_store_identity_mismatch")
                if db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] != 0:
                    raise ProtocolError("target_task_already_prepared")
        except sqlite3.Error as error:
            raise ProtocolError("task_store_observation_invalid") from error
        return owner

    @classmethod
    def read_persisted(cls, run_root: Path, scope: TaskScope) -> dict[str, Any]:
        """Observe original lifecycle data without creating a store or lease.

        Receipt validation must not mutate a completed test's bound database.
        Use the same metadata, row guards and decoder as the active owner.
        """
        owner = object.__new__(cls)
        owner.root = Path(run_root).resolve()
        owner.path = owner.root / "dsh-tasks.sqlite3"
        owner.scope = scope
        db = None
        try:
            db = sqlite3.connect(owner.path.as_uri() + "?mode=ro", uri=True, timeout=30)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            if metadata != {"version": cls.storage_version, "execution_id": scope.execution_id}:
                raise ProtocolError("task_store_identity_mismatch")
            return cls._view(owner._row(db))
        except sqlite3.Error as error:
            raise ProtocolError("task_store_observation_invalid") from error
        finally:
            if db is not None:db.close()

    def claim(self, owner: str) -> dict[str, Any]:
        if not owner or len(owner) > 256:
            raise ProtocolError("claim_owner_invalid")
        capability = secrets.token_urlsafe(32)
        with self._transaction() as db:
            row = self._row(db)
            if row["state"] != "outbox" or row["owner"] is not None:
                raise ProtocolError("task_claim_held")
            fence = self._next_fence(row)
            fact={"task_key": self._identity_key(row), "owner": owner, "claim_fence": fence,
                    "capability": capability, "epoch_started_ms": row["started_ms"]}
            db.execute("UPDATE tasks SET state='claimed',owner=?,capability_digest=?,fence=?,claim_lineage=? WHERE task_key=?",
                       (owner,digest_json(capability),fence,canonical_json_bytes([digest_json(fact)]),self.key))
            return fact

    def recover_for_settlement(self, owner: str) -> dict[str, Any]:
        """Trusted local operator rebind; never renews permission to dispatch.

        Only capability digests persist. The run lease, original task/epoch and
        backend occupancy remain intact even if the previous Host is alive.
        """
        if not owner or len(owner)>256:
            raise ProtocolError("claim_owner_invalid")
        capability=secrets.token_urlsafe(32)
        with self._transaction() as db:
            row=self._row(db)
            if row["state"] not in {"claimed","cancelled","terminal"} or not row["claim_lineage"]:
                raise ProtocolError("task_recovery_claim_required")
            fact={"task_key":self._identity_key(row),"owner":owner,"claim_fence":self._next_fence(row),
                "capability":capability,"epoch_started_ms":row["started_ms"]}
            lineage=strict_json_loads(row["claim_lineage"])
            lineage.append(digest_json(fact))
            db.execute("UPDATE tasks SET owner=?,capability_digest=?,fence=?,grant_mode='settlement-only',claim_lineage=? WHERE task_key=?",
                (owner,digest_json(capability),fact["claim_fence"],canonical_json_bytes(lineage),self.key))
            return fact

    def _authorize(self, row, claim, *, allow_terminal: bool = False):
        if (set(claim) != {"task_key", "owner", "claim_fence", "capability", "epoch_started_ms"}
                or claim["task_key"] != self._identity_key(row) or claim["owner"] != row["owner"]
                or type(claim["claim_fence"]) is not int or claim["claim_fence"] != row["fence"]
                or claim["epoch_started_ms"] != row["started_ms"]
                or digest_json(claim["capability"]) != row["capability_digest"]):
            raise ProtocolError("task_claim_stale")
        if row["state"] in {"cancelled", "terminal"} and not allow_terminal:
            raise ProtocolError("task_mutation_closed")

    def authorize(self, claim: dict[str, Any], *, allow_terminal: bool = False, require_execute: bool = False) -> dict[str, Any]:
        with self._transaction() as db:
            row = self._row(db)
            self._authorize(row, claim, allow_terminal=allow_terminal)
            if require_execute and row["grant_mode"] != "execute":
                raise ProtocolError("task_recovery_cannot_dispatch")
            return self._view(row)

    def accepts_recorded_claim(self, claim: dict[str,Any], recorded_digest: str) -> bool:
        view=self.authorize(claim,allow_terminal=True)
        return (recorded_digest == digest_json(claim) or
            (view["grant_mode"] == "settlement-only" and recorded_digest in view["claim_lineage"]))

    def capture_source(self, claim: dict[str,Any], source: dict[str,Any]) -> dict[str,Any]:
        raw=canonical_json_bytes(source)
        with self._transaction() as db:
            row=self._row(db)
            self._authorize(row,claim)
            if row["grant_mode"] != "execute":
                raise ProtocolError("task_recovery_cannot_capture_new_source")
            if row["captured_source"] is not None and row["captured_source"] != raw:
                raise ProtocolError("task_epoch_terminal_source_conflict")
            db.execute("UPDATE tasks SET captured_source=? WHERE task_key=?",(raw,self.key))
            return self._view(self._row(db))

    def bind(self, claim: dict[str, Any], *, child_id: str, session_id: str) -> dict[str, Any]:
        binding = canonical_json_bytes({"child_id": child_id, "session_id": session_id})
        if not child_id or not session_id:
            raise ProtocolError("child_binding_invalid")
        with self._transaction() as db:
            row = self._row(db)
            self._authorize(row, claim)
            if row["binding"] and row["binding"] != binding:
                raise ProtocolError("child_binding_conflict")
            db.execute("UPDATE tasks SET binding=? WHERE task_key=?", (binding, self.key))
            return self._view(self._row(db))

    def cancel(self, claim: dict[str, Any]) -> dict[str, Any]:
        with self._transaction() as db:
            row = self._row(db)
            self._authorize(row, claim, allow_terminal=True)
            if row["state"] == "terminal":
                return self._view(row)
            db.execute("UPDATE tasks SET state='cancelled' WHERE task_key=?", (self.key,))
            return self._view(self._row(db))

    def commit(self, claim: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
        raw = canonical_json_bytes(receipt)
        with self._transaction() as db:
            row = self._row(db)
            self._authorize(row, claim, allow_terminal=True)
            if row["receipt"] is not None:
                if row["receipt"] != raw:
                    raise ProtocolError("task_terminal_conflict")
                return strict_json_loads(row["receipt"])
            self._authorize(row, claim)
            db.execute("UPDATE tasks SET state='terminal',receipt=? WHERE task_key=?", (raw, self.key))
            return receipt

