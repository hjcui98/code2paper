"""V2 cumulative budgets over actual original immutable invocation facts.

Journal tests do not substitute for real V2 loop/compaction integration.
"""
import multiprocessing

import pytest

from code2paper.agentic.digest import digest_json, canonical_json_bytes
from code2paper.agentic.unified_context_models import DshInvocationEventV1
from code2paper.agentic.unified_invocation_ledger import publish_dsh_invocation_event, read_run_budget_state
from code2paper.integrations.dsh.epoch_accounting import epoch_totals, assert_epoch_admission
from code2paper.integrations.dsh.protocol import ProtocolError, parse_model
from code2paper.integrations.dsh.writer_contract import WriterTaskContractV1, WriterTaskContractV2, parse_writer_contract
from .test_composition_identity import composition
from .stage04_support import durable_material

LIMITS = dict(max_model_requests=3,max_input_tokens=50000,max_output_tokens=6000,
              max_tool_calls=6,max_tool_return_bytes=8192,max_wall_seconds=120,max_terminal_candidates=1)


@pytest.fixture
def prepared(tmp_path,composition):
    facade,contract,*_ = durable_material(tmp_path,composition,workflow_version='writer-multistep/2',epoch_limits=LIMITS)
    assert isinstance(contract,WriterTaskContractV2)
    return facade,contract,facade.store.root/'artifacts/06_authoring/invocations'


def publish(facade,contract,root,invocation,*,role='writer',status='settled',usage=(40,7)):
    binding=dict(invocation_id=invocation,attempt=1,execution_id=contract.execution_id,task_id=contract.task_id,
                 task_epoch=contract.task_epoch,claim_digest=digest_json('claim'),request_digest=digest_json(invocation),
                 contract_digest=contract.task_digest,plan_digest=digest_json('plan'),consumer_role=role)
    def event(kind,**kw):
        fact=DshInvocationEventV1(event_id=invocation+':'+kind,kind=kind,source='kernel' if kind in {'reserve','dispatch-recorded'} else 'host-adapter',**binding,**kw)
        publish_dsh_invocation_event(root,fact)
    event('reserve',reserved_input_tokens=100,reserved_output_tokens=4096)
    evidence=facade.store.put_json({'unit_journal_evidence':True}).model_dump(mode='json')
    if status=='not_sent':
        event('proven-not-sent',evidence_ref=evidence)
        return
    for kind in ('dispatch-recorded','adapter-attempt'):event(kind)
    if status=='unknown':
        event('send-outcome-unknown',reason='provider stream unproven')
        return
    event('usage',usage_input_tokens=usage[0],usage_output_tokens=usage[1],evidence_ref=evidence)
    if status=='unfinished':return
    event('terminal',evidence_ref=evidence)
    event('settlement',evidence_ref=evidence)


def admission(root,contract,**kwargs):
    return assert_epoch_admission(root,contract,epoch_started_ms=1000,input_tokens=10,output_tokens=10,now_ms=1100,**kwargs)


def test_explicit_v2_contract_and_v1_single_request_limit_preserved(prepared):
    facade,contract,_=prepared
    raw=canonical_json_bytes(contract)
    assert parse_writer_contract(raw)==contract
    with pytest.raises(ProtocolError,match='schema_invalid'):parse_model(raw,WriterTaskContractV1)
    facade.check_contract_current(contract)
    v1=contract.model_dump(mode='json')
    v1.update(schema_version='WriterTaskContractV1',workflow_version='writer-single-request/1',accounting_version='c2p-dsh-task-loop-v1')
    v1['epoch_limits'].pop('max_tool_return_bytes');v1['epoch_limits'].pop('max_terminal_candidates')
    v1['task_digest']=digest_json({k:v for k,v in v1.items() if k!='task_digest'})
    with pytest.raises(ProtocolError,match='schema_invalid'):parse_writer_contract(canonical_json_bytes(v1))


@pytest.mark.parametrize('role',['writer','compaction','title'])
@pytest.mark.parametrize('outcome',['malformed','research_required','unfinished','unknown'])
def test_sent_outcomes_and_auxiliary_roles_never_erase_fees(prepared,role,outcome):
    facade,contract,root=prepared
    publish(facade,contract,root,'request:one',role=role,status=outcome if outcome in {'unfinished','unknown'} else 'settled')
    totals=epoch_totals(root,contract)
    budget=read_run_budget_state(root)
    assert budget['call_count_by_role'][role]==1
    if outcome in {'unfinished','unknown'}:
        assert totals==dict(model_requests=1,input_tokens=100,output_tokens=4096,pending_requests=1)
        with pytest.raises(ProtocolError,match='dsh_epoch_has_unsettled_request'):admission(root,contract)
        assert budget['pending_input_tokens']==100
    else:
        assert totals==dict(model_requests=1,input_tokens=40,output_tokens=7,pending_requests=0)
        assert budget['spent_input_tokens']==40
        assert admission(root,contract)==totals


def test_exact_proven_not_sent_is_not_a_content_attempt_or_model_debit(prepared):
    facade,contract,root=prepared
    publish(facade,contract,root,'request:cancelled',status='not_sent')
    assert epoch_totals(root,contract)==dict(model_requests=0,input_tokens=0,output_tokens=0,pending_requests=0)
    assert read_run_budget_state(root)['call_count']==0
    assert admission(root,contract)['model_requests']==0


def test_all_children_share_cumulative_output_and_request_caps(prepared):
    facade,contract,root=prepared
    publish(facade,contract,root,'request:child-one',usage=(40,3000))
    publish(facade,contract,root,'request:child-two',role='compaction',usage=(40,3000))
    with pytest.raises(ProtocolError,match='dsh_epoch_output_budget_exceeded'):admission(root,contract)
    assert epoch_totals(root,contract)['output_tokens']==6000


def test_cumulative_input_and_request_limits(prepared):
    facade,contract,root=prepared
    for i in range(3):publish(facade,contract,root,'request:'+str(i),usage=(100,7))
    with pytest.raises(ProtocolError,match='dsh_epoch_request_budget_exceeded'):admission(root,contract)
    assert epoch_totals(root,contract)['input_tokens']==300


def test_cumulative_input_limit(prepared):
    facade,contract,root=prepared
    publish(facade,contract,root,'request:large-usage',usage=(49995,7))
    with pytest.raises(ProtocolError,match='dsh_epoch_input_budget_exceeded'):
        admission(root,contract)


def test_deadline_never_restarts_with_a_new_child(prepared):
    _,contract,root=prepared
    with pytest.raises(ProtocolError,match='dsh_epoch_deadline_exceeded'):
        assert_epoch_admission(root,contract,epoch_started_ms=1000,input_tokens=10,output_tokens=10,now_ms=121000)


def restored_process(root,raw,queue):
    contract=parse_writer_contract(raw)
    queue.put(epoch_totals(root,contract))


def test_fresh_real_process_derives_same_original_fees(prepared):
    facade,contract,root=prepared
    publish(facade,contract,root,'request:before-restart',role='compaction',usage=(40,7))
    ctx=multiprocessing.get_context('spawn');queue=ctx.Queue()
    process=ctx.Process(target=restored_process,args=(root,canonical_json_bytes(contract),queue))
    process.start();observed=queue.get(timeout=30);process.join(timeout=30)
    assert process.exitcode==0
    assert observed==epoch_totals(root,contract)==dict(model_requests=1,input_tokens=40,output_tokens=7,pending_requests=0)


def tool_owner(prepared):
    from code2paper.integrations.dsh.epoch_tools import EpochTools,ToolCandidateV2
    facade,contract,root=prepared
    ref=facade.store.put_json(contract)
    tasks=facade.task_store
    tasks.prepare(workflow_id=contract.workflow_id,node_id=contract.node_id,scope_id=contract.scope_id,
                  contract_ref=ref.model_dump(mode='json'),content_revision=facade.context.content_revision,
                  content_fence=facade.context.fence,snapshot_digest=facade.context.snapshot_digest)
    claim=tasks.claim('host:tools')
    tasks.bind(claim,child_id=facade.context.child_id,session_id=facade.context.session_id)
    binding=dict(invocation_id='request:tool-stream',attempt=1,execution_id=contract.execution_id,
                 task_id=contract.task_id,task_epoch=contract.task_epoch,claim_digest=digest_json(claim),
                 request_digest=digest_json('actual-unit-request'),contract_digest=contract.task_digest,
                 plan_digest=digest_json('unit-plan'),consumer_role='writer')
    for kind in ('reserve','dispatch-recorded','adapter-attempt'):
        publish_dsh_invocation_event(root,DshInvocationEventV1(**binding,event_id='unit:'+kind,kind=kind,
            source='host-adapter' if kind=='adapter-attempt' else 'kernel',
            **(dict(reserved_input_tokens=100,reserved_output_tokens=4096) if kind=='reserve' else {})))
    raw=facade.store.put(b'not valid terminal JSON',media_type='application/octet-stream')
    source=ToolCandidateV2(schema_version='DshToolCandidateV2',execution_id=contract.execution_id,
        task_id=contract.task_id,task_epoch=contract.task_epoch,child_id=facade.context.child_id,
        session_id=facade.context.session_id,request_id='request:tool-stream',tool_call_id='call:first',
        stream_index=1,name='c2p_terminal',arguments_ref=raw,source='gated-adapter-tool-arguments-delta/2')
    return EpochTools(tasks,facade.store,facade.current_state),claim,contract,source


def test_invalid_first_native_terminal_consumes_epoch_candidate_before_schema_guard(prepared):
    tools,claim,contract,source=tool_owner(prepared)
    assert tools.record(claim,contract,source)['admitted']
    assert tools.status(claim,contract)==dict(observed=1,admitted=1,terminal_consumed=True,closed=False)
    assert tools.record(claim,contract,source)['admitted']  # exact replay, not a second candidate
    changed=source.model_copy(update={'tool_call_id':'call:repair'})
    with pytest.raises(ProtocolError,match='dsh_epoch_terminal_already_consumed'):
        tools.record(claim,contract,changed)
    assert tools.status(claim,contract)==dict(observed=2,admitted=1,terminal_consumed=True,closed=True)
    assert read_run_budget_state(prepared[2])['pending_input_tokens']==100


def test_tool_limit_counts_other_calls_and_denied_raw_without_dispatch(prepared):
    tools,claim,contract,source=tool_owner(prepared)
    for i in range(contract.epoch_limits.max_tool_calls):
        tools.record(claim,contract,source.model_copy(update={'name':'c2p_read','tool_call_id':'read:'+str(i)}))
    with pytest.raises(ProtocolError,match='dsh_epoch_tool_budget_exceeded'):
        tools.record(claim,contract,source.model_copy(update={'name':'unknown_tool','tool_call_id':'call:overflow'}))
    state=tools.status(claim,contract)
    assert state['observed']==7 and state['admitted']==6 and state['closed']


def test_tool_source_cannot_cross_request_or_session_or_change_replayed_bytes(prepared):
    tools,claim,contract,source=tool_owner(prepared)
    with pytest.raises(ProtocolError,match='tool_session_binding_invalid'):
        tools.record(claim,contract,source.model_copy(update={'session_id':'other'}))
    with pytest.raises(ProtocolError,match='tool_candidate_request_binding_invalid'):
        tools.record(claim,contract,source.model_copy(update={'request_id':'request:invented'}))
    tools.record(claim,contract,source)
    other=tools.artifacts.put(b'changed bytes',media_type='application/octet-stream')
    with pytest.raises(ProtocolError,match='tool_candidate_source_conflict'):
        tools.record(claim,contract,source.model_copy(update={'arguments_ref':other}))


def candidate_process(root,scope,raw,claim,source,current,barrier,queue):
    from code2paper.integrations.dsh.epoch_tools import EpochTools,ToolCandidateV2
    from code2paper.integrations.dsh.artifacts import TaskScope,ArtifactStore
    from code2paper.integrations.dsh.task_store import TaskStore
    scope=TaskScope(**scope)
    tools=EpochTools(TaskStore(root,scope),ArtifactStore(root,scope),lambda:current)
    barrier.wait(timeout=20)
    try:
        tools.record(claim,parse_writer_contract(raw),parse_model(canonical_json_bytes(source),ToolCandidateV2))
        queue.put('admitted')
    except ProtocolError as error:queue.put(error.code)


def test_real_process_race_admits_only_one_terminal_and_retains_second_source(prepared):
    tools,claim,contract,source=tool_owner(prepared)
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);queue=ctx.Queue()
    processes=[]
    for i in range(2):
        candidate=source.model_copy(update={'tool_call_id':'race:'+str(i)})
        processes.append(ctx.Process(target=candidate_process,args=(tools.tasks.root,tools.tasks.scope.__dict__,
            canonical_json_bytes(contract),claim,candidate.model_dump(mode='json'),tools.current_state(),barrier,queue)))
    for process in processes:process.start()
    results=[queue.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30);assert process.exitcode==0
    assert sorted(results)==['admitted','dsh_epoch_terminal_already_consumed']
    assert tools.status(claim,contract)==dict(observed=2,admitted=1,terminal_consumed=True,closed=True)


def test_tool_candidate_deadline_and_cancel_preserve_fees(prepared,monkeypatch):
    tools,claim,contract,source=tool_owner(prepared)
    from code2paper.integrations.dsh import epoch_tools
    started=tools.tasks.read()['epoch_started_ms']
    monkeypatch.setattr(epoch_tools.time,'time_ns',lambda:(started+contract.epoch_limits.max_wall_seconds*1000)*1_000_000)
    with pytest.raises(ProtocolError,match='dsh_epoch_deadline_exceeded'):
        tools.record(claim,contract,source)
    assert tools.status(claim,contract)['observed']==0
    tools.tasks.cancel(claim)
    assert tools.status(claim,contract)['closed']
    assert read_run_budget_state(prepared[2])['pending_input_tokens']==100


def test_tool_candidate_source_record_is_immutable_and_tamper_is_not_a_new_slot(prepared):
    import sqlite3,json
    tools,claim,contract,source=tool_owner(prepared)
    tools.record(claim,contract,source)
    with sqlite3.connect(tools.tasks.path) as db:
        record=json.loads(db.execute('SELECT payload FROM epoch_tool_candidates').fetchone()[0])
    path=tools.artifacts.directory/record['artifact_id'].split(':')[1]
    raw=path.read_bytes()
    path.write_bytes(raw.replace(b'c2p_terminal',b'c2p_read   '))
    with pytest.raises(ProtocolError,match='artifact_bytes_mismatch'):
        tools.status(claim,contract)
    with pytest.raises(ProtocolError,match='artifact_bytes_mismatch'):
        tools.record(claim,contract,source.model_copy(update={'tool_call_id':'repair:after-tamper'}))
