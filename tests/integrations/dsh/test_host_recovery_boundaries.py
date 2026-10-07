"""Actual private worker recovery and integrity boundaries, without provider I/O.

UNIT projections and injected adapter-entry/usage facts exercise the original
kernel owner. They do not establish HTTP arrival, native DSH Session behavior,
or remote provider quiescence. No model client or network service is started.
"""
import json

import pytest

from code2paper.agentic.unified_invocation_ledger import (
    read_dsh_invocation_events,
    read_run_budget_state,
)
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES
from code2paper.integrations.dsh.worker import rpc_schema_digest
from .stage04_support import durable_material, prepare_and_claim, start_worker
from .test_composition_identity import composition
from .test_worker_protocol import Child


@pytest.fixture
def recovery_kernel(tmp_path, composition):
    facade, contract, frozen, projection, budget, bootstrap = durable_material(tmp_path, composition)
    child = start_worker(bootstrap, facade)
    try:
        scope, claim, contract_ref = prepare_and_claim(child, facade, contract, frozen, projection)
        request = {
            **scope,
            'contract_ref': contract_ref,
            'budget_ref': budget.model_dump(mode='json'),
            'actual_request_ref': facade.store.read_json(projection.wire_equivalence_ref)['loop_request_ref'],
            'event_id': 'boundaries:reserve',
        }
        yield child, facade, contract, claim, request, bootstrap
    finally:
        if not child.process.stderr.closed:
            child.close()


def _ledger(facade):
    return facade.store.root / 'artifacts' / '06_authoring' / 'invocations'


def _scope(request):
    return {name: request[name] for name in ('execution_id', 'task_id', 'task_epoch')}


def _params(request, reservation):
    return {**_scope(request), 'contract_ref': request['contract_ref'], 'reservation': reservation}


def _result(response):
    assert 'result' in response, response
    return response['result']


def _completed_finish(recovery_kernel, *, close_task=True, record_owner=True, stop_after=None,
                      native_blocked=False, damage=None):
    # Structured UNIT owner observation verifies bindings only. The separate
    # native offline chain is required to prove the actual completion seam.
    child,facade,_,claim,request,_=recovery_kernel
    reservation=_result(child.call('request.reserve',request))
    _enter(child,request,reservation)
    raw=facade.store.put(b'{"result":{},"result":{"outcome":"blocked"}}' if damage=='duplicate-key' else
        b'{"result":{"outcome":"blocked"}}' if native_blocked
        else b'UNIT rejected raw arguments, retained unchanged')
    capture={'schema_version':'DshRawCaptureV1',**_scope(request),
        'child_id':facade.context.child_id,'session_id':facade.context.session_id,
        'request_id':reservation['request_id'],'tool_call_id':'release:tool','stream_index':1,
        'source':'adapter_tool_arguments_delta','arguments_completion':'block-ended',
        'arguments_ref':raw.model_dump(mode='json')}
    _result(child.call('task.capture_raw',{**_scope(request),'capture':capture}))
    usage={'inputTokens':40,'outputTokens':3,'totalTokens':43}
    streams=[{'type':'tool-call-chunks','index':2,'id':'release:tool','name':'c2p_terminal',
        'args':[facade.store.read(raw).decode()]},
        {'type':'chunk','chunk':{'type':'block-end','index':2,'block':{
            'type':'tool-call','id':'release:tool','name':'c2p_terminal','arguments':facade.store.read(raw).decode()}}},
        {'type':'chunk','chunk':{'type':'usage','usage':usage}},
        {'type':'chunk','chunk':{'type':'finish','reason':{'kind':'tool-calls'}}}]
    events=[{'type':'turn/start','seq':8,'data':{'turn':1}},
        {'type':'step/start','seq':9,'data':{'turn':1,'step':1}},
        {'type':'assistant/message','seq':10,'data':{'turn':1,'step':1,
        'message':{'role':'assistant','source':{'kind':'model'}},'usage':usage,'stream':streams}}]
    if native_blocked:
        events.extend([
            {'type':'tool/call','seq':11,'data':{'turn':1,'step':1,'callId':'release:tool',
                'name':'c2p_terminal','arguments':facade.store.read(raw).decode()}},
            {'type':'tool/result','seq':12,'sourceEventSeqs':[11],'data':{'turn':1,'step':1,
                'message':{'role':'tool','source':{'kind':'tool','callId':'release:tool'},
                    'toolCallId':'release:tool','isError':True,
                    'content':[{'type':'text','text':'Error: schema_invalid'}]}}},
            {'type':'step/end','seq':13,'data':{'turn':1,'step':1}},
            {'type':'turn/end','seq':14,'data':{'turn':1,'reason':{'kind':'blocked'}}}])
        call=events[3];result=events[4]
        if damage=='missing-result':events.remove(result)
        elif damage=='missing-call':events.remove(call)
        elif damage=='success-result':result['data']['message']['isError']=False
        elif damage=='wrong-call':result['data']['message']['toolCallId']='other:tool'
        elif damage=='wrong-source':result['data']['message']['source']['callId']='other:tool'
        elif damage=='wrong-step':result['data']['step']=2
        elif damage=='wrong-arguments':call['data']['arguments']='different'
        elif damage=='wrong-event-link':result['sourceEventSeqs']=[10]
        elif damage=='after-step':result['seq']=15;events.sort(key=lambda e:e['seq'])
        elif damage=='missing-error':result['data']['message']['content']=[]
        elif damage=='duplicate-result':events.insert(5,{**result,'seq':13});events[6]['seq']=14;events[7]['seq']=15
        elif damage=='usage-before-block':streams[0],streams[2]=streams[2],streams[0]
        elif damage=='after-finish':streams.append({'type':'tool-call-chunks','index':2,'args':['late']})
        elif damage=='total-mismatch':usage['totalTokens']+=1
    else:
        events.extend([{'type':'step/end','seq':11,'data':{'turn':1,'step':1}},
            {'type':'turn/end','seq':12,'data':{'turn':1,'reason':{'kind':'error','error':{'message':'UNIT rejected'}}}}])
    session=facade.store.put_json({'schema_version':'DshSessionCaptureV1',
        'session_id':facade.context.session_id,'format_version':'SessionFileV4',
        'events':events})
    _result(child.call('request.settle',_usage(facade,request,reservation)))
    quiescence=facade.store.put_json({'schema_version':'DshProviderQuiescenceV1',**_scope(request),
        'request_id':reservation['request_id'],'request_digest':reservation['request_digest'],
        'session_id':facade.context.session_id,'source':'gated-adapter-natural-exhaustion/1',
        'finish_reason':'tool-calls','raw_ref':raw.model_dump(mode='json'),'session_ref':session.model_dump(mode='json')})
    if record_owner:
        _result(child.call('backend.observe_quiescence',{**_scope(request),'quiescence_ref':quiescence.model_dump(mode='json')}))
    if stop_after=='quiescence':return facade,quiescence
    if close_task:_result(child.call('task.cancel',{**_scope(request),'claim':claim}))
    evidence=facade.store.put_json({'schema_version':'DshFinishObservationV1',
        'request_digest':reservation['request_digest'],'finish_reason':'tool-calls','stream_complete':True,
        'raw_ref':raw.model_dump(mode='json'),'session_ref':session.model_dump(mode='json')})
    for kind in ('terminal','settlement'):
        _result(child.call('request.settle',{**_params(request,reservation),
            'event_id':'release:observed-'+kind,'kind':kind,'evidence_ref':evidence.model_dump(mode='json')}))
        if stop_after==kind:break
    return facade,quiescence


def test_bound_native_blocked_error_can_register_finish_and_release_without_domain_receipt(recovery_kernel):
    facade,q=_completed_finish(recovery_kernel,native_blocked=True)
    before=read_run_budget_state(_ledger(facade))
    receipt=facade.backend_admission.release_observed_finish(run_root=facade.store.root,
        scope=facade.store.scope,quiescence_ref=q)
    assert receipt['task_state']=='cancelled'
    assert facade.task_store.read()['receipt'] is None
    assert read_run_budget_state(_ledger(facade))==before
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']=='empty'


@pytest.mark.parametrize('damage',['missing-result','missing-call','success-result','wrong-call',
    'wrong-source','wrong-step','wrong-arguments','wrong-event-link','after-step','missing-error',
    'duplicate-result','usage-before-block','after-finish','duplicate-key','total-mismatch'])
def test_blocked_label_never_replaces_exact_native_rejection_proof(recovery_kernel,damage):
    facade,q=_completed_finish(recovery_kernel,native_blocked=True,damage=damage,
        record_owner=False,stop_after='quiescence')
    response=recovery_kernel[0].call('backend.observe_quiescence',{
        **facade.store.scope.__dict__,'quiescence_ref':q.model_dump(mode='json')})
    assert response['error']['message']==('duplicate_json_key' if damage=='duplicate-key'
        else 'backend_release_quiescence_unproven')
    assert facade.task_store.read()['provider_quiescence'] is None
    assert facade.backend_admission.read_persisted(facade.backend_admission.root,
        facade.backend_admission.resource_key)['state']=='owned'


def test_exact_owner_release_is_atomic_durable_and_stale_replay_cannot_clear_new_owner(recovery_kernel,tmp_path):
    from code2paper.integrations.dsh.protocol import ProtocolError
    from code2paper.integrations.dsh.task_store import SerialBackendAdmission
    facade,finish=_completed_finish(recovery_kernel)
    admission=facade.backend_admission;kwargs={'run_root':facade.store.root,
        'scope':facade.store.scope,'quiescence_ref':finish}
    before=read_run_budget_state(_ledger(facade))
    receipt=admission.release_observed_finish(**kwargs)
    assert receipt['task_state']=='cancelled' and facade.task_store.read()['receipt'] is None
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='empty'
    reopened=SerialBackendAdmission(admission.root,admission.resource_key)
    assert reopened.release_observed_finish(**kwargs)==receipt
    new_root=tmp_path/'new-owner';new_root.mkdir()
    new_owner=reopened.acquire(execution_id='execution:next',run_root=new_root)
    with pytest.raises(ProtocolError,match='backend_release_owner_mismatch'):
        reopened.release_observed_finish(**kwargs)
    assert reopened.read_persisted(reopened.root,reopened.resource_key)['owner']==new_owner
    assert read_run_budget_state(_ledger(facade))==before


def test_backend_release_refuses_settled_fees_while_task_remains_open(recovery_kernel):
    from code2paper.integrations.dsh.protocol import ProtocolError
    facade,finish=_completed_finish(recovery_kernel,close_task=False)
    admission=facade.backend_admission
    with pytest.raises(ProtocolError,match='backend_release_task_open'):
        admission.release_observed_finish(run_root=facade.store.root,scope=facade.store.scope,
            quiescence_ref=finish)
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='owned'


@pytest.mark.parametrize('damage',['caller-idle-flag','wrong-finish','wrong-epoch','arbitrary-session','usage-mismatch','raw-mismatch','unfinished-session'])
def test_backend_release_keeps_owner_when_quiescence_or_binding_is_invalid(recovery_kernel,damage):
    from dataclasses import replace
    from code2paper.integrations.dsh.protocol import ProtocolError
    facade,finish=_completed_finish(recovery_kernel,record_owner=False,stop_after='quiescence')
    admission=facade.backend_admission;scope=facade.store.scope
    if damage=='wrong-epoch':scope=replace(scope,task_epoch=scope.task_epoch+1)
    else:
        value=facade.store.read_json(finish)
        if damage=='caller-idle-flag':value['stream_complete']=True
        elif damage=='wrong-finish':value['finish_reason']='different-finish'
        elif damage=='raw-mismatch':value['raw_ref']=facade.store.put(b'changed').model_dump(mode='json')
        elif damage=='arbitrary-session':value['session_ref']=facade.store.put_json({'stream_complete':True}).model_dump(mode='json')
        else:
            from code2paper.integrations.dsh.protocol import parse_model
            from code2paper.agentic.digest import canonical_json_bytes
            from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
            session=facade.store.read_json(parse_model(canonical_json_bytes(value['session_ref']),ArtifactRefV1))
            if damage=='usage-mismatch':session['events'][2]['data']['usage']['inputTokens']=41
            else:session['events']=session['events'][:-1]
            value['session_ref']=facade.store.put_json(session).model_dump(mode='json')
        finish=facade.store.put_json(value)
    child=recovery_kernel[0]
    response=child.call('backend.observe_quiescence',{**scope.__dict__,'quiescence_ref':finish.model_dump(mode='json')})
    assert 'error' in response, 'invalid Session/raw/source must not register owner quiescence'
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='owned'


def test_pending_send_cannot_release_backend_with_a_caller_supplied_finish_flag(recovery_kernel):
    from code2paper.integrations.dsh.protocol import ProtocolError
    child,facade,_,claim,request,_=recovery_kernel
    reservation=_result(child.call('request.reserve',request));_enter(child,request,reservation)
    _result(child.call('task.cancel',{**_scope(request),'claim':claim}))
    finish=facade.store.put_json({'stream_complete':True})
    admission=facade.backend_admission
    with pytest.raises(ProtocolError,match='backend_release_accounting_unsettled'):
        admission.release_observed_finish(run_root=facade.store.root,scope=facade.store.scope,
            quiescence_ref=finish)
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='owned'



def test_original_worker_release_replay_and_recovery_do_not_reacquire_retired_backend(recovery_kernel,tmp_path):
    facade,q=_completed_finish(recovery_kernel)
    child,_,_,_,request,bootstrap=recovery_kernel
    args={**_scope(request),'quiescence_ref':q.model_dump(mode='json')}
    receipt=_result(child.call('backend.release',args))
    assert _result(child.call('backend.release',args))==receipt
    admission=facade.backend_admission
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='empty'
    refused=child.call('task.claim',{**_scope(request),'owner':'host:cannot-reclaim'})
    assert refused['error']['message']=='task_claim_held'
    assert admission.read_persisted(admission.root,admission.resource_key)['state']=='empty'
    child.close()
    recovered=start_worker(bootstrap,facade)
    try:
        _result(recovered.call('task.recover',{**_scope(request),'owner':'host:read-released'}))
        _result(recovered.call('request.status',{**_scope(request),'contract_ref':request['contract_ref']}))
        assert _result(recovered.call('backend.release',args))==receipt
        assert admission.read_persisted(admission.root,admission.resource_key)['state']=='empty'
        new_root=tmp_path/'later';new_root.mkdir()
        new_owner=admission.acquire(execution_id='execution:later',run_root=new_root)
        _result(recovered.call('request.status',{**_scope(request),'contract_ref':request['contract_ref']}))
        refusal=recovered.call('backend.release',args)
        assert refusal['error']['message']=='backend_release_owner_mismatch'
        assert admission.read_persisted(admission.root,admission.resource_key)['owner']==new_owner
    finally:recovered.close()


def test_settlement_only_recovery_cannot_mint_fully_shaped_quiescence(recovery_kernel):
    facade,q=_completed_finish(recovery_kernel,record_owner=False)
    child,_,_,_,request,bootstrap=recovery_kernel;child.close()
    recovered=start_worker(bootstrap,facade)
    try:
        _result(recovered.call('task.recover',{**_scope(request),'owner':'host:forge-refused'}))
        value=facade.store.read_json(q)
        import base64
        forged=_result(recovered.call('artifact.record',{**_scope(request),'media_type':'application/json',
            'raw_base64':base64.b64encode(json.dumps(value).encode()).decode()}))
        assert recovered.call('backend.observe_quiescence',{**_scope(request),'quiescence_ref':forged})['error']['message']=='provider_observation_execute_claim_required'
        assert recovered.call('backend.release',{**_scope(request),'quiescence_ref':forged})['error']['message']=='backend_release_owner_observation_required'
        assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='owned'
    finally:recovered.close()


@pytest.mark.parametrize('cut',['quiescence','terminal','settlement'])
def test_persisted_owner_quiescence_survives_new_worker_at_original_settlement_cuts(recovery_kernel,cut):
    facade,q=_completed_finish(recovery_kernel,stop_after=cut)
    child,_,_,_,request,bootstrap=recovery_kernel;child.close()
    recovered=start_worker(bootstrap,facade)
    try:
        claim=_result(recovered.call('task.recover',{**_scope(request),'owner':'host:cut-recovery'}))
        view=_result(recovered.call('task.read',_scope(request)))
        assert view['provider_quiescence']['quiescence_ref']==q.model_dump(mode='json')
        _result(recovered.call('task.cancel',{**_scope(request),'claim':claim}))
        reservation=_result(recovered.call('request.status',{**_scope(request),'contract_ref':request['contract_ref']}))['reservation']
        value=facade.store.read_json(q)
        finish=facade.store.put_json({'schema_version':'DshFinishObservationV1',
            'request_digest':value['request_digest'],'finish_reason':'tool-calls','stream_complete':True,
            'raw_ref':value['raw_ref'],'session_ref':value['session_ref']})
        for kind in ('terminal','settlement'):
            _result(recovered.call('request.settle',{**_params(request,reservation),
                'event_id':'release:observed-'+kind,'kind':kind,'evidence_ref':finish.model_dump(mode='json')}))
        before=read_run_budget_state(_ledger(facade))
        _result(recovered.call('backend.release',{**_scope(request),'quiescence_ref':q.model_dump(mode='json')}))
        assert read_run_budget_state(_ledger(facade))==before
        assert before['call_count']==1 and before['spent_input_tokens']==40 and before['pending_input_tokens']==0
        assert facade.backend_admission.read_persisted(facade.backend_admission.root,facade.backend_admission.resource_key)['state']=='empty'
    finally:recovered.close()

def _enter(child, request, reservation):
    # Private kernel event injection; this is deliberately not dispatch-confirmed.
    for kind in ('dispatch-recorded', 'adapter-attempt'):
        _result(child.call('request.dispatch', {
            **_params(request, reservation), 'event_id': 'boundaries:' + kind, 'kind': kind,
        }))


def _usage(facade, request, reservation):
    evidence = facade.store.put_json({
        'schema_version': 'DshAdapterUsageV1', 'request_digest': reservation['request_digest'],
        'input_tokens': 40, 'output_tokens': 3, 'source': 'adapter-usage',
    })
    return {
        **_params(request, reservation), 'event_id': 'boundaries:late-usage', 'kind': 'usage',
        'usage_input_tokens': 40, 'usage_output_tokens': 3,
        'evidence_ref': evidence.model_dump(mode='json'),
    }


def test_cancelled_original_epoch_late_usage_settles_locally_after_new_worker(recovery_kernel):
    child, facade, _, claim, request, bootstrap = recovery_kernel
    reservation = _result(child.call('request.reserve', request))
    _enter(child, request, reservation)
    _result(child.call('task.cancel', {**_scope(request), 'claim': claim}))
    before = read_run_budget_state(_ledger(facade))
    assert before['pending_call_count'] == 1 and before['pending_input_tokens'] > 0
    child.close()
    recovered = start_worker(bootstrap, facade)
    try:
        rebound = _result(recovered.call('task.recover', {**_scope(request), 'owner': 'host:late-observer'}))
        assert rebound['epoch_started_ms'] == claim['epoch_started_ms']
        assert rebound['claim_fence'] == claim['claim_fence'] + 1
        assert read_run_budget_state(_ledger(facade)) == before
        usage = _usage(facade, request, reservation)
        observed = _result(recovered.call('request.settle', usage))
        assert _result(recovered.call('request.settle', usage)) == observed
        after_usage = read_run_budget_state(_ledger(facade))
        assert after_usage['pending_call_count'] == 1
        assert facade.task_store.read()['receipt'] is None
        raw = facade.store.put(b'private finish observation, not a valid Writer result')
        session = facade.store.put(b'UNIT local session observation; not native Session evidence')
        finish = facade.store.put_json({
            'schema_version': 'DshFinishObservationV1', 'request_digest': reservation['request_digest'],
            'finish_reason': 'stop', 'stream_complete': True,
            'raw_ref': raw.model_dump(mode='json'), 'session_ref': session.model_dump(mode='json'),
        })
        for kind in ('terminal', 'settlement'):
            settled = _result(recovered.call('request.settle', {
                **_params(request, reservation), 'event_id': 'boundaries:late-' + kind,
                'kind': kind, 'evidence_ref': finish.model_dump(mode='json'),
            }))
        after = read_run_budget_state(_ledger(facade))
        assert after['call_count'] == 1 and after['spent_input_tokens'] == 40
        assert after['pending_call_count'] == 0 and after['pending_input_tokens'] == 0
        assert settled['recovery']['accepted'] is False
        assert facade.task_store.read()['receipt'] is None
        assert facade.task_store.read()['state'] == 'cancelled'
        facts = read_dsh_invocation_events(_ledger(facade), reservation['request_id'])
        assert [fact.kind for fact in facts] == [
            'reserve', 'dispatch-recorded', 'adapter-attempt', 'cancel', 'usage', 'terminal', 'settlement',
        ]
        assert {fact.task_epoch for fact in facts} == {request['task_epoch']}
        assert len({fact.claim_digest for fact in facts}) == 1
        denied = recovered.call('request.reserve', {**request, 'event_id': 'boundaries:retry'})
        assert denied['error']['message'] == 'task_mutation_closed'
        assert read_run_budget_state(_ledger(facade)) == after
    finally:
        recovered.close()


def test_wrong_epoch_late_observation_cannot_change_original_fees(recovery_kernel):
    child, facade, _, claim, request, bootstrap = recovery_kernel
    reservation = _result(child.call('request.reserve', request))
    _enter(child, request, reservation)
    _result(child.call('task.cancel', {**_scope(request), 'claim': claim}))
    child.close()
    recovered = start_worker(bootstrap, facade)
    try:
        _result(recovered.call('task.recover', {**_scope(request), 'owner': 'host:epoch-boundary'}))
        before = read_run_budget_state(_ledger(facade))
        facts_before = read_dsh_invocation_events(_ledger(facade), reservation['request_id'])
        refused = recovered.call('request.settle', {
            **_usage(facade, request, reservation), 'task_epoch': request['task_epoch'] + 1,
        })
        assert refused['error']['message'] == 'rpc_scope_mismatch'
        assert read_run_budget_state(_ledger(facade)) == before
        assert read_dsh_invocation_events(_ledger(facade), reservation['request_id']) == facts_before
        assert facade.task_store.read()['receipt'] is None
        status = _result(recovered.call('request.status', {
            **_scope(request), 'contract_ref': request['contract_ref'],
        }))
        assert status['reservation'] == reservation
        assert status['recovery']['state'] == 'send_outcome_unknown'
        assert before['pending_call_count'] == 1 and before['pending_input_tokens'] > 0
    finally:
        recovered.close()


DEPENDENCIES = (
    'frozen_input', 'projection', 'measurement', 'wire_equivalence', 'comparison', 'loop_request',
    'provider_wire', 'domain_request', 'domain_section', 'domain_page', 'domain_narrative',
    'domain_manifest', 'domain_plan', 'domain_formalizer',
)


@pytest.mark.parametrize('damage', ['missing', 'changed'])
@pytest.mark.parametrize('boundary', ['reserve', 'adapter-entry'])
def test_prepared_dependency_damage_refuses_new_effect_and_keeps_fees(
    recovery_kernel, subtests, damage, boundary,
):
    child, facade, contract, _, request, _ = recovery_kernel
    closure = facade.verify_contract_dependencies(contract)
    assert set(closure['dependencies']) == set(DEPENDENCIES)
    reservation = None
    if boundary == 'adapter-entry':
        reservation = _result(child.call('request.reserve', request))
        _result(child.call('request.dispatch', {
            **_params(request, reservation), 'kind': 'dispatch-recorded', 'event_id': 'boundaries:dispatch',
        }))
    before = read_run_budget_state(_ledger(facade))
    # Four actual prepared workers cover both boundaries and damage modes.
    # Restore each reference before trying another one; no successful second
    # reservation or adapter permit is requested in the loop.
    for dependency in DEPENDENCIES:
        with subtests.test(dependency=dependency, damage=damage, boundary=boundary):
            ref = closure['dependencies'][dependency]
            path = facade.store.directory / ref['artifact_id'].removeprefix('sha256:')
            original = path.read_bytes()
            try:
                if damage == 'missing':
                    path.unlink()
                else:
                    # Keep length identical; hash validation must still reject.
                    assert original
                    path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                if boundary == 'reserve':
                    refused = child.call('request.reserve', request)
                else:
                    refused = child.call('request.dispatch', {
                        **_params(request, reservation), 'kind': 'adapter-attempt',
                        'event_id': 'boundaries:adapter',
                    })
                assert refused['error']['message'] == (
                    'artifact_unavailable' if damage == 'missing' else 'artifact_bytes_mismatch'
                )
                assert read_run_budget_state(_ledger(facade)) == before
                assert facade.task_store.read()['receipt'] is None
                if reservation is None:
                    assert before['call_count'] == 0 and before['pending_call_count'] == 0
                else:
                    assert before['call_count'] == 1 and before['pending_call_count'] == 1
                    assert before['pending_input_tokens'] > 0
                    assert [fact.kind for fact in read_dsh_invocation_events(
                        _ledger(facade), reservation['request_id'],
                    )] == ['reserve', 'dispatch-recorded']
            finally:
                path.write_bytes(original)


@pytest.mark.parametrize('source', ['bundle_js', 'renderer', 'node', 'dependencies'])
def test_new_worker_composition_drift_refuses_recovery_without_refunding_unknown(
    recovery_kernel, source,
):
    child, facade, _, claim, request, bootstrap = recovery_kernel
    reservation = _result(child.call('request.reserve', request))
    _enter(child, request, reservation)
    _result(child.call('request.mark_unknown', {
        **_params(request, reservation), 'kind': 'send-outcome-unknown',
        'event_id': 'boundaries:unknown', 'reason': 'original-response-unavailable',
    }))
    before = read_run_budget_state(_ledger(facade))
    child.close()
    recovered = start_worker(bootstrap, facade)
    try:
        # Initialize is genuinely valid first; the byte changes happen afterwards.
        target = (facade.spec.trees['dependencies'] / 'module.js'
                  if source == 'dependencies' else facade.spec.files[source])
        target.write_bytes(b'changed actual composition bytes')
        refused = recovered.call('task.recover', {**_scope(request), 'owner': 'host:drifted'})
        assert refused['error']['message'] == 'composition_drift'
        resumed = recovered.call('task.resume', {**_scope(request), 'claim': claim})
        assert resumed['error']['message'] == 'composition_drift'
        view = _result(recovered.call('task.read', _scope(request)))
        assert view['claim_fence'] == claim['claim_fence']
        assert view['epoch_started_ms'] == claim['epoch_started_ms']
        assert view['receipt'] is None
        assert read_run_budget_state(_ledger(facade)) == before
        assert before['pending_call_count'] == 1 and before['pending_input_tokens'] > 0
        # A further real worker cannot initialize against the same stale bootstrap.
        refused_worker = Child(bootstrap)
        try:
            handshake = refused_worker.call('initialize', {
                'protocol_version': 'c2p-dsh/1', 'schema_digest': rpc_schema_digest(),
                'validator_digest': facade.composition['validator_digest'], 'max_frame_bytes': MAX_FRAME_BYTES,
            })
            assert handshake['error']['message'] == 'composition_drift'
        finally:
            refused_worker.close()
        assert read_run_budget_state(_ledger(facade)) == before
    finally:
        recovered.close()


def test_claimed_worker_composition_drift_refuses_adapter_entry_with_original_reserve(recovery_kernel):
    child, facade, _, _, request, _ = recovery_kernel
    reservation = _result(child.call('request.reserve', request))
    _result(child.call('request.dispatch', {
        **_params(request, reservation), 'kind': 'dispatch-recorded', 'event_id': 'boundaries:dispatch',
    }))
    before = read_run_budget_state(_ledger(facade))
    facade.spec.files['renderer'].write_bytes(b'changed renderer before adapter permit')
    denied = child.call('request.dispatch', {
        **_params(request, reservation), 'kind': 'adapter-attempt', 'event_id': 'boundaries:adapter',
    })
    assert denied['error']['message'] == 'composition_drift'
    assert read_run_budget_state(_ledger(facade)) == before
    assert before['pending_call_count'] == 1 and before['pending_input_tokens'] > 0
    assert [fact.kind for fact in read_dsh_invocation_events(_ledger(facade), reservation['request_id'])] == [
        'reserve', 'dispatch-recorded',
    ]
    assert facade.task_store.read()['receipt'] is None


def _commit_unit_blocked_receipt(child, facade, request, reservation):
    """Original capture, recording and publication with explicitly UNIT Session."""
    _enter(child, request, reservation)
    _result(child.call('request.settle', _usage(facade, request, reservation)))
    raw = json.dumps({
        'schema_version': 'WriterTaskResultV1',
        'result': {'outcome': 'blocked', 'reason': 'private recovery boundary fixture',
                   'recovery_action': 'new scoped task'},
    })
    raw_ref = facade.store.put(raw.encode()).model_dump(mode='json')
    _result(child.call('task.capture_raw', {
        **_scope(request), 'capture': {
            **_scope(request), 'schema_version': 'DshRawCaptureV1',
            'child_id': facade.context.child_id, 'session_id': facade.context.session_id,
            'request_id': reservation['request_id'], 'tool_call_id': 'call:boundary', 'stream_index': 1,
            'source': 'adapter_tool_arguments_delta', 'arguments_completion': 'block-ended',
            'arguments_ref': raw_ref,
        },
    }))
    session = facade.store.put_json({
        'schema_version': 'DshSessionCaptureV1', 'session_id': facade.context.session_id,
        'format_version': 'SessionFileV4', 'events': [
            {'type': 'tool/call', 'data': {'turn': 0, 'step': 1, 'callId': 'call:boundary',
                                         'name': 'c2p_terminal', 'arguments': raw}},
            {'type': 'tool/result', 'data': {'turn': 0, 'step': 1, 'message': {
                'role': 'tool', 'toolCallId': 'call:boundary', 'isError': False,
            }}},
            {'type': 'turn/end', 'data': {'turn': 0, 'reason': {'kind': 'completed'}}},
        ],
    })
    params = {**_scope(request), 'contract_ref': request['contract_ref']}
    output = _result(child.call('task.record_output', {
        **params, 'envelope': {
            **_scope(request), 'schema_version': 'OutputEnvelopeV1',
            'child_id': facade.context.child_id, 'session_id': facade.context.session_id,
            'turn_id': 0, 'step_id': 1, 'tool_call_id': 'call:boundary',
            'request_id': reservation['request_id'], 'source': 'adapter_tool_arguments_delta',
            'arguments_complete': True, 'provider_http': {'status': 'not_observed', 'ref': None},
            'adapter_arguments': {'status': 'observed', 'ref': raw_ref},
            'normalized_arguments': {'status': 'observed', 'ref': raw_ref},
            'stop_reason': 'completed', 'usage': None, 'session_capture_ref': session.model_dump(mode='json'),
        },
    }))
    key = _result(child.call('task.ingest_key', {**params, 'output_ref': output}))['idempotency_key']
    ingest_params = {**params, 'output_ref': output, 'idempotency_key': key}
    return _result(child.call('task.ingest', ingest_params)), ingest_params


@pytest.mark.parametrize('damage', ['dependency-missing', 'dependency-changed', 'composition-changed'])
def test_authorized_original_receipt_replay_survives_new_effect_dependency_drift(recovery_kernel, damage):
    child, facade, contract, claim, request, bootstrap = recovery_kernel
    reservation = _result(child.call('request.reserve', request))
    receipt, ingest_params = _commit_unit_blocked_receipt(child, facade, request, reservation)
    assert receipt['domain_status'] == 'blocked'
    before = read_run_budget_state(_ledger(facade))
    assert before['call_count'] == 1 and before['spent_input_tokens'] == 40
    assert before['pending_call_count'] == 0
    child.close()
    recovered = start_worker(bootstrap, facade)
    try:
        rebound = _result(recovered.call('task.recover', {
            **_scope(request), 'owner': 'host:immutable-receipt-reader',
        }))
        assert rebound['epoch_started_ms'] == claim['epoch_started_ms']
        if damage == 'composition-changed':
            facade.spec.files['renderer'].write_bytes(b'changed runtime after original receipt')
        else:
            # Domain preparation input is not needed to read the committed result.
            path = facade.store.directory / contract.private_input_ref.artifact_id.removeprefix('sha256:')
            if damage == 'dependency-missing':
                path.unlink()
            else:
                original = path.read_bytes()
                path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        replay = _result(recovered.call('task.ingest', ingest_params))
        assert replay == receipt
        assert _result(recovered.call('task.read', _scope(request)))['receipt'] == receipt
        assert read_run_budget_state(_ledger(facade)) == before
        assert recovered.call('request.reserve', request)['error']['message'] == 'task_mutation_closed'
        assert read_run_budget_state(_ledger(facade)) == before
    finally:
        recovered.close()
