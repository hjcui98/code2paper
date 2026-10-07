"""Real process contention and durable lifecycle, without a model provider."""
import multiprocessing
from dataclasses import replace

import pytest

from code2paper.agentic.authoring_execution_identity import acquire_run_lease
from code2paper.agentic.digest import digest_bytes
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.task_store import TaskStore, SerialBackendAdmission
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES
from code2paper.integrations.dsh.worker import rpc_schema_digest
from code2paper.agentic.digest import canonical_json_bytes
from .stage03_support import ROOT, local_test_facade
from .test_composition_identity import composition
from .test_worker_protocol import Child, scope
from dataclasses import asdict

SCOPE = TaskScope("execution:test", "task:writer", 2)


def prepare(root):
    store = TaskStore(root, SCOPE)
    ref = ArtifactStore(root, SCOPE).put_json({"contract": "lifecycle-test"})
    view = store.prepare(workflow_id="workflow:writer", node_id="writer", scope_id="section:one",
        contract_ref=ref.model_dump(mode="json"), content_revision=3, content_fence=5,
        snapshot_digest=digest_bytes(b"snapshot"))
    return store, view


def contender(root, barrier, queue, owner):
    store = TaskStore(root, SCOPE)
    barrier.wait(timeout=20)
    try:
        queue.put(("claimed", store.claim(owner)))
    except ProtocolError as error:
        queue.put(("rejected", error.code))


def read_in_process(root, queue, claim=None):
    store = TaskStore(root, SCOPE)
    queue.put(store.read() if claim is None else store.authorize(claim))


def backend_owner(root, run_root, queue):
    admission = SerialBackendAdmission(root, "test-provider:shared")
    queue.put(admission.acquire(execution_id="execution:one", run_root=run_root))


def test_lost_capability_recovery_is_settlement_only_and_never_persists_secrets(tmp_path):
    store,initial=prepare(tmp_path)
    original=store.claim("host:original")
    store.bind(original,child_id="child:original",session_id="session:original")
    recovered=TaskStore(tmp_path,SCOPE).recover_for_settlement("host:recovery")
    assert recovered["claim_fence"] == original["claim_fence"]+1
    assert recovered["epoch_started_ms"] == initial["epoch_started_ms"]
    with pytest.raises(ProtocolError,match="task_claim_stale"):
        store.authorize(original)
    assert store.authorize(recovered)["grant_mode"] == "settlement-only"
    with pytest.raises(ProtocolError,match="task_recovery_cannot_dispatch"):
        store.authorize(recovered,require_execute=True)
    assert original["capability"].encode() not in store.path.read_bytes()
    assert recovered["capability"].encode() not in store.path.read_bytes()


@pytest.mark.parametrize('column,value,error', [
    ('fence',(1 << 53),'task_store_fence_invalid'),
    ('fence',-1,'task_store_fence_invalid'),
    ('claim_lineage',b'[{}]','task_store_claim_lineage_invalid'),
    ('claim_lineage',b'[]','task_store_claim_lineage_invalid'),
    ('state','idle','task_store_lifecycle_invalid'),
    ('grant_mode','execute-anything','task_store_lifecycle_invalid'),
])
def test_restart_refuses_corrupt_durable_authority_before_new_grant(tmp_path,column,value,error):
    import sqlite3
    store,_=prepare(tmp_path)
    claim=store.claim('host:original')
    with sqlite3.connect(store.path) as db:
        # The columns come only from the fixed parameterized test cases.
        db.execute(f'UPDATE tasks SET {column}=? WHERE task_key=?',(value,store.key))
    restored=TaskStore(tmp_path,SCOPE)
    for operation in (restored.read,lambda:restored.authorize(claim),
            lambda:restored.recover_for_settlement('host:restart')):
        with pytest.raises(ProtocolError,match=error):operation()


def test_two_hosts_claim_exactly_once_and_process_restart_preserves_epoch(tmp_path):
    store, before = prepare(tmp_path)
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(2)
    queue = ctx.Queue()
    processes = [ctx.Process(target=contender, args=(tmp_path, barrier, queue, f"host:{i}")) for i in range(2)]
    for process in processes:
        process.start()
    results = [queue.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert sorted(row[0] for row in results) == ["claimed", "rejected"]
    claim = next(row[1] for row in results if row[0] == "claimed")
    process = ctx.Process(target=read_in_process, args=(tmp_path, queue, claim))
    process.start()
    resumed = queue.get(timeout=30)
    process.join(timeout=30)
    assert process.exitcode == 0
    assert resumed["epoch_started_ms"] == before["epoch_started_ms"]
    assert resumed["prepared"] == before["prepared"]
    assert resumed["prepared"]["task_epoch"] == 2
    assert resumed["prepared"]["content_fence"] == 5
    assert resumed["claim_fence"] == 1
    # Exit of both Host processes is not quiescence or permission to steal.
    with pytest.raises(ProtocolError, match="task_claim_held"):
        store.claim("host:restart")


def test_prepare_outbox_survives_restart_and_conflicting_prepare_fails(tmp_path):
    store, first = prepare(tmp_path)
    second, repeated = prepare(tmp_path)
    assert repeated == first
    assert second.read()["state"] == "outbox"
    ref = ArtifactStore(tmp_path, SCOPE).put_json({"changed": True})
    with pytest.raises(ProtocolError, match="task_prepare_conflict"):
        store.prepare(workflow_id="workflow:writer", node_id="writer", scope_id="section:one",
            contract_ref=ref.model_dump(mode="json"), content_revision=3, content_fence=5,
            snapshot_digest=digest_bytes(b"snapshot"))


def test_private_capability_fence_and_cancel_are_enforced_before_replay(tmp_path):
    store, _ = prepare(tmp_path)
    claim = store.claim("host:one")
    forged = {**claim, "capability": "self-reported"}
    with pytest.raises(ProtocolError, match="task_claim_stale"):
        store.authorize(forged)
    with pytest.raises(ProtocolError, match="task_claim_stale"):
        store.authorize({**claim, "claim_fence": 0})
    store.bind(claim, child_id="child:one", session_id="session:one")
    with pytest.raises(ProtocolError, match="child_binding_conflict"):
        store.bind(claim, child_id="child:two", session_id="session:two")
    store.cancel(claim)
    with pytest.raises(ProtocolError, match="task_mutation_closed"):
        store.bind(claim, child_id="child:one", session_id="session:one")
    with pytest.raises(ProtocolError, match="task_mutation_closed"):
        store.commit(claim, {"receipt": "late"})


def test_commit_idempotence_remains_authorized_and_conflict_is_rejected(tmp_path):
    store, _ = prepare(tmp_path)
    claim = store.claim("host:one")
    receipt = {"receipt": "immutable"}
    assert store.commit(claim, receipt) == receipt
    assert TaskStore(tmp_path, SCOPE).commit(claim, receipt) == receipt
    with pytest.raises(ProtocolError, match="task_terminal_conflict"):
        store.commit(claim, {"receipt": "other"})
    with pytest.raises(ProtocolError, match="task_claim_stale"):
        store.commit({**claim, "owner": "host:other"}, receipt)


def test_store_cannot_rebind_execution_or_release_borrowed_run_lease(tmp_path):
    lease = acquire_run_lease(tmp_path, execution_id=SCOPE.execution_id)
    try:
        store, _ = prepare(tmp_path)
        assert lease._handle is not None
        store.read()
        assert lease._handle is not None
        with pytest.raises(Exception, match="run_lease_held"):
            TaskStore(tmp_path, replace(SCOPE, execution_id="execution:other"))
    finally:
        lease.release()
    with pytest.raises(ProtocolError, match="task_store_identity_mismatch"):
        TaskStore(tmp_path, replace(SCOPE, execution_id="execution:other"))


def test_backend_owner_survives_process_exit_and_rejects_second_run(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=backend_owner, args=(tmp_path / "backend", tmp_path / "run-one", queue))
    process.start()
    owner = queue.get(timeout=30)
    process.join(timeout=30)
    assert process.exitcode == 0
    admission = SerialBackendAdmission(tmp_path / "backend", "test-provider:shared")
    assert admission.acquire(execution_id="execution:one", run_root=tmp_path / "run-one") == owner
    with pytest.raises(ProtocolError, match="backend_run_admission_held"):
        admission.acquire(execution_id="execution:two", run_root=tmp_path / "run-two")
    with pytest.raises(ProtocolError, match="backend_run_admission_held"):
        admission.acquire(execution_id="execution:one", run_root=tmp_path / "different-root")


def test_durable_claim_bind_cancel_and_resume_use_real_worker_rpc(tmp_path, composition):
    # Compiler material and C00 structural UNIT double are inherited from the
    # accepted local tests. This tests actual claim RPC, not V01 provider wire.
    composition.effective_config.update(backend_state_root=str(tmp_path / "shared-backend"),
        backend_resource_key="test-provider:shared")
    facade, contract, _, frozen = local_test_facade(tmp_path, composition)
    context = asdict(replace(facade.context, claim_mode="dsh-durable-claim/1"))
    context.pop("scope")
    spec = {"files": {key: str(path) for key, path in composition.files.items()},
        "trees": {key: str(path) for key, path in composition.trees.items()},
        "effective_config": dict(composition.effective_config), "upstream_source_sha": None}
    from code2paper.agentic.unified_context_models import conservative_token_meter
    bootstrap = tmp_path / "durable-bootstrap.json"
    bootstrap.write_bytes(canonical_json_bytes({"artifact_root": str(facade.store.root), "engine_root": str(ROOT),
        "scope": asdict(facade.context.scope), "context": context, "composition_spec": spec,
        "composition": facade.composition, "meter": conservative_token_meter().model_dump(mode="json")}))
    params = scope(facade)
    def start():
        child = Child(bootstrap)
        handshake = child.call("initialize", {"protocol_version": "c2p-dsh/1", "schema_digest": rpc_schema_digest(),
            "validator_digest": facade.composition["validator_digest"], "max_frame_bytes": MAX_FRAME_BYTES})
        assert "result" in handshake, handshake
        assert handshake["result"]["scope_mode"] == "dsh-durable-claim/1"
        return child
    child = start()
    try:
        prepared = child.call("task.prepare", {**params, "frozen_ref": frozen.model_dump(mode="json"),
            "projection_ref": contract.dsh_wire_contract_ref.model_dump(mode="json"), "cap": 4096})
        assert "result" in prepared, prepared
        first = child.call("task.read", params)["result"]
        claim = child.call("task.claim", {**params, "owner": "host:real-worker"})["result"]
        assert child.call("task.claim", {**params, "owner": "host:second"})["error"]["message"] == "task_claim_held"
        bound = child.call("task.bind", {**params, "claim": claim, "child_id": "child:durable", "session_id": "session:durable"})
        assert bound["result"]["binding"]["child_id"] == "child:durable"
    finally:
        child.close()
    # All recovery RPCs now run in a fresh Python process; no process-local
    # facade state, fake claim authority, or receipt grants survive this exit.
    child = start()
    try:
        resumed = child.call("task.resume", {**params, "claim": claim})["result"]
        assert resumed["epoch_started_ms"] == first["epoch_started_ms"]
        assert resumed["prepared"]["content_fence"] == first["prepared"]["content_fence"]
        assert resumed["binding"] == {"child_id": "child:durable", "session_id": "session:durable"}
        assert child.call("task.resume", {**params, "claim": {**claim, "claim_fence": 0}})["error"]["message"] == "schema_invalid"
        assert child.call("task.cancel", {**params, "claim": claim})["result"]["state"] == "cancelled"
        assert child.call("task.bind", {**params, "claim": claim, "child_id": "late", "session_id": "late"})["error"]["message"] == "task_mutation_closed"
    finally:
        child.close()
