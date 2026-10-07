"""Whole Writer/compaction V2 epoch proof over original Session, tool sources and fees.

Compaction requires its separately issued original binding and full child log. Unknown, unfinished or unlisted requests prevent release.
"""
from typing import Literal
from code2paper.agentic.digest import canonical_json_bytes
from .protocol import WireModel, ProtocolError, parse_model
from .writer_contract import ArtifactRefV1,Identifier,Counter
from .step_completion import verify_step_completion
from .epoch_accounting import epoch_requests


class EpochQuiescenceV2(WireModel):
    schema_version: Literal['DshEpochProviderQuiescenceV2']
    execution_id: Identifier
    task_id: Identifier
    task_epoch: Counter
    session_id: Identifier
    source: Literal['gated-adapter-epoch-natural-exhaustion/2']
    session_ref: ArtifactRefV1
    steps: tuple[ArtifactRefV1,...]
    auxiliary_sessions: tuple[ArtifactRefV1,...] = ()


def verify_epoch_quiescence(facade,contract,value,*,require_settlement):
    def refuse():raise ProtocolError('dsh_epoch_quiescence_unproven')
    proof=parse_model(canonical_json_bytes(value),EpochQuiescenceV2)
    if (contract.schema_version!='WriterTaskContractV2' or not proof.steps
            or (proof.execution_id,proof.task_id,proof.task_epoch)!=(contract.execution_id,contract.task_id,contract.task_epoch)):
        refuse()
    store=facade.store
    def read(ref):return store.read_json(parse_model(canonical_json_bytes(ref),ArtifactRefV1))
    session=read(proof.session_ref.model_dump(mode='json'));view=facade.task_store.read()
    if (not isinstance(session,dict) or set(session)!={'schema_version','session_id','format_version','events'}
            or session['schema_version']!='DshSessionCaptureV1' or session['format_version']!='SessionFileV4'
            or session['session_id']!=proof.session_id or not view['binding']
            or view['binding']['session_id']!=proof.session_id or not isinstance(session['events'],list)):
        refuse()
    captures={proof.session_id:session}
    for ref in proof.auxiliary_sessions:
        child=read(ref.model_dump(mode='json'))
        if (not isinstance(child,dict) or set(child)!={'schema_version','session_id','format_version','events'}
                or child.get('schema_version')!='DshSessionCaptureV1' or child.get('format_version')!='SessionFileV4'
                or not isinstance(child.get('session_id'),str) or child['session_id'] in captures
                or not isinstance(child.get('events'),list)):refuse()
        captures[child['session_id']]=child
    for capture in captures.values():
        rows=capture['events']
        if (not rows or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in rows)
                or any(a['seq']>=b['seq'] for a,b in zip(rows,rows[1:]))):refuse()
    events=session['events']
    if (not events or any(not isinstance(e,dict) or type(e.get('seq')) is not int for e in events)
            or any(a['seq']>=b['seq'] for a,b in zip(events,events[1:]))):refuse()
    root=store.root/'artifacts/06_authoring/invocations';requests=epoch_requests(root,contract)
    if len(requests)!=len(proof.steps):refuse()
    by_id={facts[0].invocation_id:facts for facts in requests};seen=set();sessions={}
    for index,ref in enumerate(proof.steps):
        evidence=read(ref.model_dump(mode='json'));request_id=evidence.get('request_id');facts=by_id.get(request_id)
        if facts is None or request_id in seen or evidence.get('session_id') not in captures:refuse()
        seen.add(request_id);verify_step_completion(facade,contract,evidence,facts)
        reserve=read(facts[0].evidence_ref);step=read(reserve['step_ref'])
        if step.get('sequence')!=index+1:refuse()
        sid=evidence['session_id'];events=captures[sid]['events']
        previous=sessions.get(sid,{'last_end':-1,'count':0})
        prefix=read(evidence['session_ref'])['events']
        if not prefix or prefix[-1]['seq']<=previous['last_end'] or prefix!=[e for e in events if e['seq']<=prefix[-1]['seq']]:refuse()
        sessions[sid]={'last_end':prefix[-1]['seq'],'last':evidence,'count':previous['count']+1}
        if (step['role']=='writer')!=(sid==proof.session_id):refuse()
        terminal=[f for f in facts if f.kind=='terminal'];settlement=[f for f in facts if f.kind=='settlement']
        if require_settlement or index<len(proof.steps)-1 or step['role']=='compaction':
            if len(terminal)!=1 or len(settlement)!=1:refuse()
            recorded=read(terminal[0].evidence_ref)
            if recorded.get('schema_version')=='DshStepFinishObservationV2':
                if terminal[0].evidence_ref!=ref.model_dump(mode='json') or settlement[0].evidence_ref!=terminal[0].evidence_ref:refuse()
            elif index==len(proof.steps)-1 and recorded.get('schema_version')=='RecordedWriterOutputV1':
                envelope=recorded.get('envelope',{});captured=view.get('captured_source')
                if (recorded.get('contract_digest')!=contract.task_digest or not captured
                        or envelope.get('request_id')!=request_id or captured.get('request_id')!=request_id
                        or envelope.get('session_id')!=proof.session_id or envelope.get('tool_call_id')!=captured.get('tool_call_id')
                        or envelope.get('adapter_arguments',{}).get('ref')!=captured.get('arguments_ref')):refuse()
                receipt=read(settlement[0].evidence_ref)
                if receipt.get('schema_version')=='LocalWriterReceiptV1':
                    if receipt.get('task_digest')!=contract.task_digest or receipt.get('payload_digest')!=parse_model(canonical_json_bytes(terminal[0].evidence_ref),ArtifactRefV1).bytes_digest:refuse()
                elif receipt.get('schema_version')=='DshRejectedOutputObservationV1':
                    if receipt.get('contract_digest')!=contract.task_digest or receipt.get('output_ref')!=terminal[0].evidence_ref:refuse()
                else:refuse()
            else:refuse()
        elif terminal or settlement:refuse()
    if set(sessions)!=set(captures):refuse()
    for sid,observed in sessions.items():
        events=captures[sid]['events'];last=observed['last'];last_end=observed['last_end']
        ends=[e for e in events if e.get('type')=='turn/end' and isinstance(e.get('data'),dict) and e['data'].get('turn')==last['turn_id']]
        if (len(ends)!=1 or ends[0]['seq']<=last_end or not isinstance(ends[0]['data'].get('reason'),dict)
                or ends[0]['data']['reason'].get('kind') not in ({'completed','blocked','error'} if sid==proof.session_id else {'completed'})
                or not 1<=len([e for e in events if e.get('type')=='request/header'])<=observed['count']
                or len([e for e in events if e.get('type')=='assistant/message'])!=observed['count']
                or any(e.get('type') in {'step/start','assistant/attempt'} for e in events if e['seq']>last_end)):refuse()
    return len(requests)
