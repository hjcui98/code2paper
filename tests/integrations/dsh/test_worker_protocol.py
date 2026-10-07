"""C04 real child stdio, bounded frames and private scope permission checks."""
import base64
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

from code2paper.agentic.digest import canonical_json_bytes,digest_bytes
from code2paper.agentic.unified_context_models import conservative_token_meter
from code2paper.integrations.dsh.protocol import MAX_FRAME_BYTES
from code2paper.integrations.dsh.worker import rpc_schema_digest
from code2paper.integrations.dsh.result_ingest import ingest_key
from .stage03_support import ROOT,local_test_facade,observed_output,terminal_raw
from .test_composition_identity import composition


class Child:
    def __init__(self,bootstrap,*,module="code2paper.integrations.dsh.worker",extra_env=None):
        self.bootstrap=bootstrap
        self.process=subprocess.Popen([sys.executable,"-m",module,"--bootstrap",str(bootstrap)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT,start_new_session=True,
            env={**os.environ,"PYTHONPATH":str(ROOT/"src"),"PYTHONDONTWRITEBYTECODE":"1",**(extra_env or {})})
        self.sequence=0
    def raw(self,raw):
        self.process.stdin.write(raw+b"\n");self.process.stdin.flush()
        ready,_,_=select.select([self.process.stdout],[],[],15)
        assert ready, "worker did not return bounded RPC"
        result=json.loads(self.process.stdout.readline());assert result["jsonrpc"]=="2.0"
        return result
    def call(self,method,params):
        self.sequence+=1
        return self.raw(canonical_json_bytes({"jsonrpc":"2.0","id":self.sequence,"method":method,"params":params}))
    def close(self):
        if self.process.poll() is None:self.process.stdin.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(self.process.pid,15);self.process.wait(timeout=5)
        stderr=self.process.stderr.read().decode();self.process.stdout.close();self.process.stderr.close()
        assert self.process.returncode==0,stderr
        with pytest.raises(ProcessLookupError):os.killpg(self.process.pid,0)
        assert not stderr


@pytest.fixture
def worker(tmp_path,composition):
    facade,contract,material,frozen=local_test_facade(tmp_path,composition)
    context=asdict(facade.context);context.pop("scope")
    spec={"files":{k:str(p) for k,p in composition.files.items()},"trees":{k:str(p) for k,p in composition.trees.items()},
          "effective_config":dict(composition.effective_config),"upstream_source_sha":None}
    bootstrap=tmp_path/"bootstrap.json"
    bootstrap.write_bytes(canonical_json_bytes(dict(artifact_root=str(facade.store.root),engine_root=str(ROOT),scope=asdict(facade.context.scope),
        context=context,composition_spec=spec,composition=facade.composition,meter=conservative_token_meter().model_dump(mode="json"))))
    child=Child(bootstrap)
    try:
        handshake=child.call("initialize",dict(protocol_version="c2p-dsh/1",schema_digest=rpc_schema_digest(),
            validator_digest=facade.composition["validator_digest"],max_frame_bytes=MAX_FRAME_BYTES))
        assert "result" in handshake,handshake
        yield child,facade,contract,material,frozen
    finally:
        child.close()


def scope(facade):return asdict(facade.context.scope)


@pytest.mark.parametrize('damage', ['none','digest','length','extra-field','changed-file'])
def test_worker_startup_rechecks_optional_operator_launch_binding(worker,tmp_path,damage):
    from code2paper.agentic.digest import digest_bytes
    child,facade,_,_,_=worker
    launch=tmp_path/'operator-launch.json'
    raw=canonical_json_bytes({'schema_version':'UNIT-bootstrap-binding-only'})
    launch.write_bytes(raw)
    values=json.loads(child.bootstrap.read_text())
    binding={'schema_version':'DshHostLaunchBindingV1','path':str(launch),
        'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}
    if damage == 'digest':binding['bytes_digest']=digest_bytes(b'wrong')
    if damage == 'length':binding['byte_length']=len(raw)+1
    if damage == 'extra-field':binding['permission']='send'
    if damage == 'changed-file':launch.write_bytes(raw+b' ')
    values['host_launch_binding']=binding
    bootstrap=tmp_path/'bound-bootstrap.json';bootstrap.write_bytes(canonical_json_bytes(values))
    if damage == 'none':
        restarted=Child(bootstrap)
        try:
            result=restarted.call('initialize',dict(protocol_version='c2p-dsh/1',schema_digest=rpc_schema_digest(),
                validator_digest=facade.composition['validator_digest'],max_frame_bytes=MAX_FRAME_BYTES))
            assert 'result' in result,result
            assert restarted.call('worker.status',scope(facade))['result']['model_calls'] == 0
        finally:restarted.close()
    else:
        result=subprocess.run([sys.executable,'-m','code2paper.integrations.dsh.worker','--bootstrap',str(bootstrap)],
            cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1'},
            input=b'',capture_output=True,timeout=30)
        assert result.returncode != 0 and not result.stdout
        assert b'bootstrap_host_launch_' in result.stderr


@pytest.mark.parametrize("raw,code",[(b'{"jsonrpc":"2.0","id":1,"id":2,"method":"worker.status","params":{}}',"duplicate_json_key"),
    (b'{"jsonrpc":"2.0","id":NaN,"method":"worker.status","params":{}}',"non_finite_number"),
    (b'{"jsonrpc":"2.0","id":Infinity,"method":"worker.status","params":{}}',"non_finite_number"),
    (b'{"jsonrpc":"2.0","id":9007199254740992,"method":"worker.status","params":{}}',"integer_out_of_range"),
    (b'{"jsonrpc":"3.0","id":1,"method":"worker.status","params":{}}',"schema_invalid"),
    (b'{"jsonrpc":"2.0","id":1,"method":"worker.status","params":{},"path":"/etc/passwd"}',"schema_invalid")])
def test_real_process_bad_wire(worker,raw,code):
    child,*_=worker
    assert child.raw(raw)["error"]["message"]==code


def test_oversized_frame_is_drained_then_next_valid_rpc_succeeds(worker):
    child,facade,*_=worker
    assert child.raw(b" "*(MAX_FRAME_BYTES+1))["error"]["message"]=="frame_too_large"
    assert child.call("worker.status",scope(facade))["result"]["state"]=="idle"


@pytest.mark.parametrize("field",["execution_id","task_id","task_epoch"])
def test_scope_cannot_be_spoofed(worker,field):
    child,facade,*_=worker
    values=scope(facade);values[field]=1 if field=="task_epoch" else "other"
    assert child.call("worker.status",values)["error"]["message"]=="rpc_scope_mismatch"


def test_private_methods_paths_and_claims_are_unavailable(worker):
    child,facade,*_=worker
    for method in ("task.claim","request.reserve","request.dispatch","request.settle","eval","import","read_path","c2p_read_artifact"):
        assert child.call(method,scope(facade))["error"]["message"]=="method_unavailable"
    assert child.call("artifact.record",{**scope(facade),"path":"/etc/passwd"})["error"]["message"]=="schema_invalid"


def test_record_ingest_original_reader_and_cache_scope_through_real_process(worker):
    child,facade,contract,material,_=worker
    contract_ref=facade.store.put_json(contract)
    envelope=observed_output(facade,terminal_raw(material))
    response=child.call("task.record_output",{**scope(facade),"contract_ref":contract_ref.model_dump(mode="json"),"envelope":envelope.model_dump(mode="json")})
    assert "result" in response,response
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    output=ArtifactRefV1.model_validate(response["result"])
    params={**scope(facade),"contract_ref":contract_ref.model_dump(mode="json"),"output_ref":output.model_dump(mode="json"),"idempotency_key":ingest_key(contract,output)}
    first=child.call("task.ingest",params);assert first["result"]["domain_status"]=="pending_validation"
    assert child.call("task.ingest",params)["result"]==first["result"]
    assert child.call("task.ingest",{**params,"task_id":"other"})["error"]["message"]=="rpc_scope_mismatch"
    assert child.call("task.ingest",{**params,"idempotency_key":digest_bytes(b"bad")})["error"]["message"]=="idempotency_key_mismatch"


def test_cancel_read_preserves_worker_and_shutdown_does_not_claim_provider_quiescence(worker):
    child,facade,*_=worker
    # Cancel one consumer wait without signalling or destroying the worker.
    pending={"jsonrpc":"2.0","id":1000,"method":"worker.status","params":scope(facade)}
    child.process.stdin.write(canonical_json_bytes(pending)+b"\n");child.process.stdin.flush()
    # The request remains owned by the worker; observe its eventual terminal.
    ready,_,_=select.select([child.process.stdout],[],[],10);assert ready
    assert json.loads(child.process.stdout.readline())["id"] == 1000
    started=time.monotonic();assert child.call("worker.status",scope(facade))["result"]["model_calls"]==0
    assert time.monotonic()-started<5
    stopped=child.call("worker.shutdown",scope(facade))["result"]
    assert stopped["provider_scope_quiescence"]=="not_proven_by_worker"
    child.process.wait(timeout=10)
    with pytest.raises(ProcessLookupError):os.killpg(child.process.pid,0)


@pytest.mark.parametrize("observed",[False,None,0,1,"true"])
def test_only_true_cleanup_result_proves_provider_scope(observed):
    from code2paper.integrations.dsh.protocol import require_provider_quiescence,ProtocolError
    with pytest.raises(ProtocolError,match="provider_scope_not_quiescent"):require_provider_quiescence(observed)


def test_slow_external_provider_does_not_occupy_worker_rpc(worker):
    child,facade,*_=worker
    provider=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True)
    try:
        assert provider.poll() is None
        start=time.monotonic();result=child.call("worker.status",scope(facade))
        assert result["result"]["state"] == "idle" and time.monotonic()-start < 5
    finally:
        os.killpg(provider.pid,15);provider.wait(timeout=5)
    from code2paper.integrations.dsh.protocol import require_provider_quiescence
    # Independent cleanup signal; observe process group disappearance, not only
    # request cancellation or parent completion.
    with pytest.raises(ProcessLookupError):os.killpg(provider.pid,0)
    require_provider_quiescence(True)


@pytest.mark.parametrize('changes',[{'content_revision':2},{'fence':1},
    {'snapshot_digest':digest_bytes(b'new snapshot')},
    {'content_revision':2,'fence':1,'snapshot_digest':digest_bytes(b'new snapshot')}])
def test_real_worker_rejects_old_frozen_input_at_prepare(worker,tmp_path,changes):
    child,facade,contract,_,frozen=worker
    boot=json.loads(child.bootstrap.read_text());boot['context'].update(changes)
    path=tmp_path/'fresh-host.json';path.write_bytes(canonical_json_bytes(boot))
    fresh=Child(path)
    try:
        assert 'result' in fresh.call('initialize',dict(protocol_version='c2p-dsh/1',schema_digest=rpc_schema_digest(),
            validator_digest=facade.composition['validator_digest'],max_frame_bytes=MAX_FRAME_BYTES))
        reply=fresh.call('task.prepare',{**scope(facade),'frozen_ref':frozen.model_dump(mode='json'),
            'projection_ref':contract.dsh_wire_contract_ref.model_dump(mode='json'),'cap':4096})
        assert reply['error']['message']=='frozen_revision_snapshot_or_fence_stale'
        assert fresh.call('worker.status',scope(facade))['result']['model_calls']==0
    finally:fresh.close()


@pytest.mark.parametrize('outcome',['draft','research_required','blocked'])
def test_real_worker_new_outcomes_reject_complete_dependency_damage_matrix(worker,outcome):
    from .test_result_provenance import closure_refs,raw_outcome
    from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
    child,facade,contract,material,_=worker
    contract_ref=facade.store.put_json(contract).model_dump(mode='json')
    refs=closure_refs(facade,contract)
    envelope=observed_output(facade,raw_outcome(material,outcome))
    recorded=child.call('task.record_output',{**scope(facade),'contract_ref':contract_ref,'envelope':envelope.model_dump(mode='json')})
    assert 'result' in recorded,recorded
    output=ArtifactRefV1.model_validate(recorded['result'])
    params={**scope(facade),'contract_ref':contract_ref,'output_ref':recorded['result'],'idempotency_key':ingest_key(contract,output)}
    for role,ref in refs.items():
        path=facade.store.directory/ref.artifact_id.split(':')[1];original=path.read_bytes()
        for damage,code in [('missing','artifact_unavailable'),('corrupt','artifact_bytes_mismatch')]:
            try:
                if damage=='missing':path.unlink()
                else:path.write_bytes(b'damaged private test copy')
                reply=child.call('task.ingest',params)
                assert reply['error']['message']==code,(outcome,role,damage,reply)
                root=facade.store.root/'dsh-local-outcomes'
                assert all(path.name=='.stage03-local-outcome.lock' for path in root.rglob('*') if path.is_file())
            finally:path.write_bytes(original)
    assert child.call('worker.status',scope(facade))['result']['model_calls']==0
    # All original immutable bytes restored: positive completion and lost reply.
    receipt=child.call('task.ingest',params)['result']
    assert receipt['domain_status']=={'draft':'pending_validation','research_required':'waiting','blocked':'blocked'}[outcome]
    ref=refs['projection'];(facade.store.directory/ref.artifact_id.split(':')[1]).unlink()
    assert child.call('task.ingest',params)['result']==receipt


@pytest.mark.parametrize('mode,code',[('state_change','task_revision_or_fence_stale'),
    ('stale_recompile','frozen_revision_snapshot_or_fence_stale')])
def test_true_stdio_prepare_lifecycle_rejects_host_transition_and_stale_owner_recompile(worker,tmp_path,mode,code):
    from code2paper.integrations.dsh.writer_contract import seal_projection
    child,facade,contract,_,frozen=worker
    fault={'mode':mode};projection_ref=contract.dsh_wire_contract_ref
    if mode=='stale_recompile':
        stale=facade.store.read_json(frozen);stale['fence']=99
        fault['frozen_ref']=facade.store.put_json(stale).model_dump(mode='json')
        projection=facade.store.read_json(projection_ref)
        from code2paper.integrations.dsh.writer_contract import ArtifactRefV1
        measure=facade.store.read_json(ArtifactRefV1.model_validate(projection['measurement_ref']))
        measure['context_tokens']=measure['measured_input_tokens']+512+1024
        projection['measurement_ref']=facade.store.put_json(measure)
        projection_ref=facade.store.put_json(seal_projection(projection))
    path=tmp_path/'lifecycle-fault.json';path.write_bytes(canonical_json_bytes(fault))
    fresh=Child(child.bootstrap,module='tests.integrations.dsh.fixtures.prepare_lifecycle_worker',
        extra_env={'C2P_TEST_LIFECYCLE_FAULT':str(path)})
    try:
        assert 'result' in fresh.call('initialize',dict(protocol_version='c2p-dsh/1',schema_digest=rpc_schema_digest(),
            validator_digest=facade.composition['validator_digest'],max_frame_bytes=MAX_FRAME_BYTES))
        reply=fresh.call('task.prepare',{**scope(facade),'frozen_ref':frozen.model_dump(mode='json'),
            'projection_ref':projection_ref.model_dump(mode='json'),'cap':4096})
        assert reply['error']['message']==code,reply
        assert fresh.call('worker.status',scope(facade))['result']['model_calls']==0
    finally:fresh.close()
