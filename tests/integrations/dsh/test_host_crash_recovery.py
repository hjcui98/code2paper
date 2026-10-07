"""Abrupt real-worker recovery before a response exists.

This is the private kernel/journal matrix. Actual provider arrival and native
Session recovery are tested separately by host-recovery-*.test.ts; an injected
adapter-entry fact here is not evidence of an HTTP send.
"""
from dataclasses import asdict

import pytest

from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
from .test_composition_identity import composition
from .stage04_support import durable_material, prepare_and_claim, start_worker


def _kill_worker(child):
    child.process.kill()
    child.process.wait(timeout=5)
    for stream in (child.process.stdin, child.process.stdout, child.process.stderr):
        stream.close()
    assert child.process.returncode != 0


@pytest.mark.parametrize('cut', ['before-reserve', 'after-reserve', 'after-dispatch', 'after-adapter'])
def test_abrupt_worker_recovery_keeps_epoch_budget_and_forbids_resend(tmp_path, composition, cut):
    facade, contract, frozen, projection, budget, bootstrap = durable_material(tmp_path, composition)
    child = start_worker(bootstrap, facade)
    params, claim, contract_ref = prepare_and_claim(child, facade, contract, frozen, projection)
    request = {**params, 'contract_ref': contract_ref, 'budget_ref': budget.model_dump(mode='json'),
        'actual_request_ref': facade.store.read_json(projection.wire_equivalence_ref)['loop_request_ref'],
        'event_id': 'reserve:primary'}
    reservation = None
    if cut != 'before-reserve':
        reservation = child.call('request.reserve', request)['result']
    if cut in {'after-dispatch', 'after-adapter'}:
        assert 'result' in child.call('request.dispatch', {**params, 'contract_ref': contract_ref,
            'reservation': reservation, 'event_id': 'dispatch:one', 'kind': 'dispatch-recorded'})
    if cut == 'after-adapter':
        assert 'result' in child.call('request.dispatch', {**params, 'contract_ref': contract_ref,
            'reservation': reservation, 'event_id': 'adapter:one', 'kind': 'adapter-attempt'})
    _kill_worker(child)
    ledger = facade.store.root / 'artifacts' / '06_authoring' / 'invocations'
    before = read_run_budget_state(ledger)
    recovered = start_worker(bootstrap, facade)
    try:
        new_claim = recovered.call('task.recover', {**params, 'owner': 'host:new-process'})['result']
        assert new_claim['claim_fence'] > claim['claim_fence']
        assert new_claim['epoch_started_ms'] == claim['epoch_started_ms']
        status = recovered.call('request.status', {**params, 'contract_ref': contract_ref})['result']
        assert status['reservation'] == reservation
        assert status['recorded_output_ref'] is None
        assert recovered.call('request.reserve', request)['error']['message'] == 'task_recovery_cannot_dispatch'
        if reservation is not None:
            denied = recovered.call('request.dispatch', {**params, 'contract_ref': contract_ref,
                'reservation': reservation, 'event_id': 'dispatch:retry', 'kind': 'dispatch-recorded'})
            assert denied['error']['message'] == 'dsh_recovery_cannot_redispatch'
            assert status['recovery']['state'] == 'send_outcome_unknown'
            assert before['call_count'] == 1 and before['pending_input_tokens'] > 0
        else:
            assert before['call_count'] == 0 and before['pending_input_tokens'] == 0
        assert read_run_budget_state(ledger) == before
        stale = recovered.call('task.resume', {**params, 'claim': claim})
        assert 'error' in stale
        view = recovered.call('task.read', asdict(facade.context.scope))['result']
        assert view['grant_mode'] == 'settlement-only'
    finally:
        recovered.close()
