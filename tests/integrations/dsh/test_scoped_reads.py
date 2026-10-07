"""Real immutable bytes and TaskStore transactions, no model/network calls."""
import json
import multiprocessing

import pytest

from code2paper.agentic.digest import digest_bytes
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.scoped_reads import ScopedReads
from code2paper.integrations.dsh.task_store import TaskStore

SCOPE = TaskScope('execution:read', 'task:writer', 0)
STATE = (3, 5, digest_bytes(b'snapshot'))


def owner(root, *, max_calls=6, max_bytes=4096):
    artifacts = ArtifactStore(root, SCOPE)
    tasks = TaskStore(root, SCOPE)
    contract = artifacts.put_json({'fixture': 'contract'})
    tasks.prepare(workflow_id='workflow:read', node_id='writer', scope_id='section:one',
                  contract_ref=contract.model_dump(mode='json'), content_revision=3,
                  content_fence=5, snapshot_digest=STATE[2])
    claim = tasks.claim('host:read')
    tasks.bind(claim, child_id='child:writer', session_id='session:writer')
    reads = ScopedReads(tasks, artifacts, lambda: STATE)
    ref = artifacts.put('完整 source α = x\n'.encode(), media_type='text/plain')
    reads.configure(claim, session_id='session:writer', max_calls=max_calls, max_bytes=max_bytes,
                    read_set=[{'ref':ref.model_dump(mode='json'),'kind':kind,'start':0,'end':ref.byte_length}
                              for kind in ('exact_excerpt','navigation')])
    grant = reads.issue(claim, session_id='session:writer', ref=ref, kind='exact_excerpt', start=0, end=ref.byte_length)
    return reads, claim, ref, grant


def request(reads, claim, grant, **kwargs):
    return reads.read(claim, session_id='session:writer', grant_id=grant, offset=0, length=6, **kwargs)


def test_only_issued_range_and_full_actual_json_bytes_count(tmp_path):
    reads, claim, ref, grant = owner(tmp_path)
    result = request(reads, claim, grant)
    body = json.loads(result['model_text'])
    assert body['text'] == '完整' and body['kind'] == 'exact_excerpt'
    assert body['source_digest'] == ref.bytes_digest
    assert result['delivered_bytes'] == len(result['model_text'].encode()) > 6
    denied = json.loads(request(reads, claim, '/etc/passwd')['model_text'])
    assert denied == {'error': 'read_grant_unavailable'}
    denied2 = reads.read(claim, session_id='session:writer', grant_id=grant, offset=ref.byte_length - 1, length=2)
    assert json.loads(denied2['model_text'])['error'] == 'read_range_outside_grant'
    status = reads.status(claim, session_id='session:writer')
    assert status['calls'] == 3
    assert status['delivered_bytes'] == result['delivered_bytes'] + len(b'{"error":"read_grant_unavailable"}') + denied2['delivered_bytes']


def test_navigation_summary_retains_issuer_kind_and_model_cannot_relabel(tmp_path):
    reads, claim, ref, _ = owner(tmp_path)
    grant = reads.issue(claim, session_id='session:writer', ref=ref, kind='navigation', start=0, end=ref.byte_length)
    assert json.loads(request(reads, claim, grant)['model_text'])['kind'] == 'navigation'
    with pytest.raises(TypeError):
        request(reads, claim, grant, kind='exact_excerpt')
    from code2paper.integrations.dsh.worker import ReadGrantParams
    with pytest.raises(ValueError):
        ReadGrantParams.model_validate({**SCOPE.__dict__, 'grant_id': grant, 'offset': 0, 'length': 6, 'kind': 'exact_excerpt'})


@pytest.mark.parametrize('changed', [(4,5,STATE[2]), (3,6,STATE[2]), (3,5,digest_bytes(b'new snapshot'))])
def test_original_owner_revision_fence_snapshot_invalidates_old_view(tmp_path, changed):
    reads, claim, _, grant = owner(tmp_path)
    reads.current_state = lambda: changed
    with pytest.raises(ProtocolError, match='task_revision_or_fence_stale'):
        request(reads, claim, grant)


def test_cross_epoch_artifact_and_cross_session_closed_claim_rejected(tmp_path):
    reads, claim, ref, grant = owner(tmp_path)
    with pytest.raises(ProtocolError, match='artifact_scope_mismatch'):
        reads.issue(claim, session_id='session:writer', ref=ref.model_copy(update={'task_epoch': 1}), kind='exact_excerpt', start=0, end=6)
    with pytest.raises(ProtocolError, match='read_session_binding_invalid'):
        reads.read(claim, session_id='session:other', grant_id=grant, offset=0, length=6)
    reads.tasks.cancel(claim)
    with pytest.raises(ProtocolError, match='task_mutation_closed'):
        request(reads, claim, grant)


def test_utf8_split_refused_and_counted(tmp_path):
    reads, claim, _, grant = owner(tmp_path)
    result = reads.read(claim, session_id='session:writer', grant_id=grant, offset=0, length=1)
    assert json.loads(result['model_text']) == {'error': 'read_range_not_utf8'}
    assert reads.status(claim, session_id='session:writer')['calls'] == 1


def test_restart_and_reconfigure_never_reset_epoch_budget(tmp_path):
    reads, claim, ref, grant = owner(tmp_path, max_calls=1)
    request(reads, claim, grant)
    restored = ScopedReads(TaskStore(tmp_path,SCOPE), ArtifactStore(tmp_path,SCOPE), lambda: STATE)
    restored.configure(claim, session_id='session:writer', max_calls=1, max_bytes=4096, read_set=[{'ref':ref.model_dump(mode='json'),'kind':kind,'start':0,'end':ref.byte_length} for kind in ('exact_excerpt','navigation')])
    with pytest.raises(ProtocolError, match='read_epoch_exhausted'):
        request(restored, claim, grant)
    with pytest.raises(ProtocolError, match='read_limits_conflict'):
        restored.configure(claim, session_id='session:writer', max_calls=2, max_bytes=4096, read_set=[{'ref':ref.model_dump(mode='json'),'kind':kind,'start':0,'end':ref.byte_length} for kind in ('exact_excerpt','navigation')])


def test_actual_rendered_bytes_exhaustion_persists_without_delivery(tmp_path):
    reads, claim, _, grant = owner(tmp_path, max_bytes=64)
    with pytest.raises(ProtocolError, match='read_epoch_exhausted'):
        request(reads, claim, grant)
    assert reads.status(claim, session_id='session:writer') == {'max_calls':6,'max_bytes':64,'calls':1,'delivered_bytes':0,'closed':True}
    with pytest.raises(ProtocolError, match='read_epoch_exhausted'):
        request(reads, claim, '/tmp/private')


def process_read(root, claim, grant, barrier, queue):
    reads = ScopedReads(TaskStore(root,SCOPE), ArtifactStore(root,SCOPE), lambda: STATE)
    barrier.wait(timeout=20)
    try:
        request(reads, claim, grant)
        queue.put('delivered')
    except ProtocolError as error:
        queue.put(error.code)


def test_two_real_processes_share_one_call_quota(tmp_path):
    reads, claim, _, grant = owner(tmp_path, max_calls=1)
    ctx = multiprocessing.get_context('spawn')
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    children = [ctx.Process(target=process_read,args=(tmp_path,claim,grant,barrier,queue)) for _ in range(2)]
    for child in children: child.start()
    results = [queue.get(timeout=30) for _ in children]
    for child in children:
        child.join(timeout=30)
        assert child.exitcode == 0
    assert sorted(results) == ['delivered','read_epoch_exhausted']
    assert reads.status(claim, session_id='session:writer')['calls'] == 1


def test_new_host_artifact_is_not_automatically_in_read_set(tmp_path):
    reads, claim, _, _ = owner(tmp_path)
    private = reads.artifacts.put(b'private binder context',media_type='text/plain')
    with pytest.raises(ProtocolError,match='read_outside_issued_set'):
        reads.issue(claim,session_id='session:writer',ref=private,kind='exact_excerpt',start=0,end=private.byte_length)


from .test_composition_identity import composition  # noqa: E402,F401


def test_actual_worker_rpc_reads_only_issued_grant_and_restart_keeps_quota(tmp_path, composition):
    from .stage04_support import durable_material, start_worker, prepare_and_claim
    facade, contract, frozen, projection, _, bootstrap = durable_material(tmp_path, composition)
    child = start_worker(bootstrap, facade)
    try:
        scope, claim, _ = prepare_and_claim(child, facade, contract, frozen, projection)
        reads = ScopedReads(facade.task_store, facade.store, facade.current_state)
        ref = facade.store.put(b'Kernel-issued navigation',media_type='text/plain')
        member = {'ref':ref.model_dump(mode='json'),'kind':'navigation','start':0,'end':ref.byte_length}
        reads.configure(claim,session_id=facade.context.session_id,max_calls=1,max_bytes=4096,read_set=[member])
        grant = reads.issue(claim,session_id=facade.context.session_id,ref=ref,kind='navigation',start=0,end=ref.byte_length)
        with pytest.raises(ProtocolError,match='read_outside_issued_set'):
            reads.issue(claim,session_id=facade.context.session_id,ref=ref,kind='exact_excerpt',start=0,end=ref.byte_length)
        params = {**scope,'grant_id':grant,'offset':0,'length':ref.byte_length}
        assert child.call('task.read_grant',{**params,'path':'/etc/passwd'})['error']['message'] == 'schema_invalid'
        response = child.call('task.read_grant',params)
        assert json.loads(response['result']['model_text'])['kind'] == 'navigation'
        assert response['result']['delivered_bytes'] == len(response['result']['model_text'].encode())
    finally:
        child.close()
    restarted = start_worker(bootstrap, facade)
    try:
        assert 'result' in restarted.call('task.resume',{**scope,'claim':claim})
        assert restarted.call('task.read_grant',params)['error']['message'] == 'read_epoch_exhausted'
        assert restarted.call('task.read_grant',{**params,'task_epoch':scope['task_epoch']+1})['error']['message'] == 'rpc_scope_mismatch'
        assert restarted.call('task.issue_read',scope)['error']['message'] == 'method_unavailable'
    finally:
        restarted.close()


def promotion_ref(store, *, complete=True):
    """Explicit UNIT sealed Research-owner output, not model-provided facts."""
    from code2paper.agentic.research_promotion import ObservationPromotionLedgerV1, ObservationPromotionRecordV1
    record = ObservationPromotionRecordV1(
        observation_id='observation:revision', obligation_id='obligation:revision', tool_name='inspect',
        status='claim_promoted' if complete else 'observed_unpromoted',
        rejection_code='' if complete else 'evidence_missing',
        behavior_node_ids=('behavior:revision',) if complete else (),
        packet_ids=('packet:revision',) if complete else (),
        fact_ids=('fact:revision',) if complete else (),
        claim_ids=('claim:revision',) if complete else ())
    ledger = ObservationPromotionLedgerV1(records=(record,))
    return store.put_json(ledger.model_dump(mode='json'))


def test_incomplete_promotion_cannot_invalidate_or_expand_read_set(tmp_path):
    reads, claim, _, grant = owner(tmp_path)
    with pytest.raises(ProtocolError, match='content_promotion_not_complete'):
        reads.tasks.invalidate_after_promotion(claim, promotion_ref=promotion_ref(reads.artifacts, complete=False))
    assert reads.tasks.current_content_state(STATE) == STATE
    assert json.loads(request(reads, claim, grant)['model_text'])['text'] == '完整'


def test_actual_worker_old_view_refused_after_private_owner_promotion_and_restart(tmp_path, composition):
    from .stage04_support import durable_material, start_worker, prepare_and_claim
    facade, contract, frozen, projection, _, bootstrap = durable_material(tmp_path, composition)
    child = start_worker(bootstrap, facade)
    try:
        scope, claim, contract_ref = prepare_and_claim(child, facade, contract, frozen, projection)
        reads = ScopedReads(facade.task_store, facade.store, facade.current_state)
        ref = facade.store.put(b'original navigation', media_type='text/plain')
        member = {'ref': ref.model_dump(mode='json'), 'kind':'navigation', 'start':0, 'end':ref.byte_length}
        reads.configure(claim, session_id=facade.context.session_id, max_calls=3, max_bytes=4096, read_set=[member])
        grant = reads.issue(claim, session_id=facade.context.session_id, ref=ref, kind='navigation', start=0, end=ref.byte_length)
        params = {**scope, 'grant_id':grant, 'offset':0, 'length':ref.byte_length}
        assert 'result' in child.call('task.read_grant', params)
        before = facade.task_store.read()
        promoted = promotion_ref(facade.store)
        invalidation = facade.task_store.invalidate_after_promotion(claim, promotion_ref=promoted)
        assert invalidation['current'][:2] == [facade.context.content_revision+1, facade.context.fence+1]
        assert facade.task_store.invalidate_after_promotion(claim, promotion_ref=promoted) == invalidation
        assert facade.task_store.read() == before  # claim, original binding and receipt unchanged
        assert child.call('task.read_grant',params)['error']['message'] == 'task_revision_or_fence_stale'
        assert child.call('task.invalidate_after_promotion',{**scope,'promotion_ref':promoted.model_dump(mode='json')})['error']['message'] == 'method_unavailable'
    finally:
        child.close()
    restarted = start_worker(bootstrap, facade)
    try:
        assert 'result' in restarted.call('task.resume',{**scope,'claim':claim})
        assert restarted.call('task.read_grant',params)['error']['message'] == 'task_revision_or_fence_stale'
        assert restarted.call('context.materials',{**scope,'contract_ref':contract_ref})['error']['message'] == 'task_revision_or_fence_stale'
    finally:
        restarted.close()
