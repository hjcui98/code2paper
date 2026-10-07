"""UNIT target integration; synthetic upstream certificate is never coverage evidence.

Only the expensive upstream full-suite certificate checker is isolated. Target
I01, immutable material, reconstruction, SQLite observers, original budget and
actual isolated-network checks all run their original implementations.
"""
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from code2paper.agentic.authoring_execution_identity import CompositionSpecV1
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from code2paper.agentic.unified_context_models import DshInvocationEventV1
from code2paper.agentic.unified_invocation_ledger import publish_dsh_invocation_event, read_run_budget_state
from code2paper.integrations.dsh.artifacts import TaskScope
from code2paper.integrations.dsh.qualification import network_namespace_identity
from code2paper.integrations.dsh.target_admission import STABLE_FILES, TREES, validate_target_admission
from code2paper.integrations.dsh.worker import rpc_schema_digest
from .stage03_support import ROOT, unit_projection
from .stage04_support import durable_material


def _shared_material(root):
    shared=root/'shared';shared.mkdir()
    files={}
    for key in STABLE_FILES:
        path=shared/key;path.write_bytes(('UNIT stable '+key).encode());files[key]=path
    trees={}
    for key in TREES:
        path=shared/key;path.mkdir();(path/'module').write_bytes(b'UNIT runtime');trees[key]=path
    return files,trees


def _target(root,shared,scope,*,model='unit-model',temperature=0.4):
    root.mkdir()
    files,trees=shared
    files=dict(files)
    config=root/'host-config.json';config.write_bytes(b'{"UNIT":"offline"}')
    overlay=root/'host-overlay.json';overlay.write_bytes(canonical_json_bytes([
        {'id':'web-runtime','config':{'printUrl':False,'openBrowser':False,'surfaceContext':False,'trustedHosts':[]}},
        {'id':'session-persistence-jsonl','config':{'root':str(root/'sessions'),'compression':'none'}}]))
    launcher=root/'worker-launcher';launcher.write_text('UNIT worker '+str(root/'python-sentinel.json'))
    files.update(host_config=config,host_overlay=overlay,test_worker_launcher=launcher)
    spec=CompositionSpecV1(files=files,trees=trees,effective_config={
        'model':model,'options':{'temperature':temperature},'worker_version':'1','renderer_version':'1',
        'tokenizer_version':'1','meter_version':'1','backend_resource_key':'UNIT:offline-provider',
        'backend_state_root':str(root/'backend')})
    facade,_,frozen,input_ref,budget,bootstrap=durable_material(root,spec,prepare_contract=False,scope=scope)
    projection=unit_projection(facade,input_ref)
    launch={'schema_version':'DshSingleWriterLaunchV1','config_path':str(config),'overlay_paths':[str(overlay)],
        'cwd':str(root),'scope':asdict(scope),'run_id':'UNIT:run','owner':'UNIT:owner',
        'budget_ref':budget.model_dump(mode='json'),'frozen_ref':frozen.model_dump(mode='json'),
        'projection_ref':facade.store.put_json(projection).model_dump(mode='json'),
        'input':input_ref.model_dump(mode='json'),'projection':projection.model_dump(mode='json'),
        'initialize':{'protocol_version':'c2p-dsh/1','schema_digest':rpc_schema_digest()},
        'provider_config':{'providers':{'unit':{'baseURL':'http://127.0.0.1:12345/v1'}}}}
    launch_path=root/'launch.json';raw=canonical_json_bytes(launch);launch_path.write_bytes(raw)
    bootstrap_value=json.loads(bootstrap.read_bytes())
    bootstrap_value['host_launch_binding']={'schema_version':'DshHostLaunchBindingV1',
        'path':str(launch_path),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}
    bootstrap.write_bytes(canonical_json_bytes(bootstrap_value))
    return facade,frozen,projection,bootstrap,launch_path


def _unit_certificate_call(bootstrap,receipt,launch):
    """Invoked in actual bwrap namespace; no fake certificate escapes this helper."""
    from code2paper.integrations.dsh import host_admission
    from code2paper.integrations.dsh.protocol import ProtocolError
    patch=pytest.MonkeyPatch()
    calls=[]
    def unit_upstream_certificate(**kwargs):
        calls.append(kwargs)
        return {'UNIT_not_a_certificate':True}
    patch.setattr(host_admission,'_validate_admission',unit_upstream_certificate)
    try:
        result=validate_target_admission(bootstrap_path=Path(bootstrap),receipt_path=Path(receipt),
            candidate='UNIT-candidate',launch_path=Path(launch))
        return {'result':result,'upstream_unit_calls':len(calls)}
    except ProtocolError as error:
        return {'error':error.code,'upstream_unit_calls':len(calls)}
    finally:
        patch.undo()


def _run_isolated(root,bootstrap,receipt,launch):
    bwrap=shutil.which('bwrap')
    assert bwrap is not None,'target offline admission requires the installed isolating launcher'
    code=('import sys,json;sys.path.insert(0,'+repr(str(ROOT))+');sys.path.insert(0,'+repr(str(ROOT/'src'))+');'
        'from tests.integrations.dsh.test_target_admission_integration import _unit_certificate_call;'
        'print(json.dumps(_unit_certificate_call('+','.join(repr(str(path)) for path in (bootstrap,receipt,launch))+')))')
    result=subprocess.run([bwrap,'--ro-bind','/','/','--bind',str(root),str(root),'--unshare-net',
        '--proc','/proc','--dev','/dev','--setenv','PYTHONDONTWRITEBYTECODE','1',sys.executable,'-c',code],
        capture_output=True,timeout=180)
    assert result.returncode == 0,result.stderr.decode()
    return json.loads(result.stdout)


def _file_state(root):
    return {str(path.relative_to(root)):(digest_bytes(path.read_bytes()),path.stat().st_mtime_ns)
        for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('case,expected',[
    ('fresh',None),('model-drift','target_runtime_authority_mismatch'),
    ('options-drift','target_runtime_authority_mismatch'),
    ('provider-drift','target_runtime_authority_mismatch'),
    ('prepared','target_task_already_prepared'),('spent-budget','target_budget_not_initial'),
])
def test_actual_target_readonly_admission_under_unit_upstream_certificate(tmp_path,case,expected):
    shared=_shared_material(tmp_path)
    _,_,_,qualified,qualified_launch=_target(tmp_path/'qualified',shared,TaskScope('UNIT:qualified','writer',0))
    facade,frozen,projection,target,launch=_target(tmp_path/'target',shared,TaskScope('UNIT:fresh','writer',0),
        model='different-unit-model' if case == 'model-drift' else 'unit-model',
        temperature=0.8 if case == 'options-drift' else 0.4)
    if case == 'provider-drift':
        launch_value=json.loads(launch.read_bytes())
        launch_value['provider_config']['providers']['unit']['baseURL']='http://127.0.0.1:12346/v1'
        launch_raw=canonical_json_bytes(launch_value);launch.write_bytes(launch_raw)
        bootstrap_value=json.loads(target.read_bytes())
        bootstrap_value['host_launch_binding'].update(bytes_digest=digest_bytes(launch_raw),byte_length=len(launch_raw))
        target.write_bytes(canonical_json_bytes(bootstrap_value))
    if case == 'prepared':
        contract=facade.prepare(frozen,cap=4096,project=lambda _:projection)
        facade.task_store.prepare(workflow_id='UNIT:workflow',node_id='writer',scope_id='UNIT:section',
            contract_ref=facade.store.put_json(contract).model_dump(mode='json'),
            content_revision=facade.context.content_revision,content_fence=facade.context.fence,
            snapshot_digest=facade.context.snapshot_digest)
    if case == 'spent-budget':
        # Controlled prior accounting observation, published by the real owner;
        # this is not a provider send or a domain acceptance declaration.
        evidence=facade.store.put_json({'UNIT':'prior observed usage'}).model_dump(mode='json')
        base=dict(invocation_id='UNIT:prior',attempt=1,execution_id=facade.context.scope.execution_id,
            task_id='writer',task_epoch=0,claim_digest=digest_json('UNIT:claim'),
            request_digest=digest_json('UNIT:request'),contract_digest=digest_json('UNIT:contract'),
            plan_digest=digest_json('UNIT:plan'),consumer_role='writer')
        ledger=facade.store.root/'artifacts/06_authoring/invocations'
        for kind in ('reserve','dispatch-recorded','adapter-attempt','usage','terminal','settlement'):
            values=dict(base,event_id='UNIT:'+kind,kind=kind,
                source='kernel' if kind in {'reserve','settlement'} else 'host-adapter')
            if kind == 'reserve':values.update(reserved_input_tokens=10,reserved_output_tokens=1)
            if kind == 'usage':values.update(usage_input_tokens=10,usage_output_tokens=1)
            if kind in {'usage','terminal','settlement'}:values['evidence_ref']=evidence
            publish_dsh_invocation_event(ledger,DshInvocationEventV1(**values))
        assert read_run_budget_state(ledger)['spent_input_tokens'] == 10
    # Intentionally insufficient synthetic receipt: only the helper's clearly
    # marked UNIT upstream seam accepts it. No final certificate is fabricated.
    receipt=OfflineSuiteReceiptV1(schema_version='2.0',passed=True,exit_code=0,machine_plan={
        'name':'dsh-stage04','version':'dsh-stage04-offline/12','candidate':'UNIT-candidate',
        'operator':{'bootstrap_path':str(qualified),'launch_path':str(qualified_launch)},
        'effective_config':{'qualification_parent_namespace':network_namespace_identity()}})
    receipt_path=tmp_path/'UNIT-not-certificate.json';receipt_path.write_text(receipt.model_dump_json())
    before=_file_state(tmp_path)
    observation=_run_isolated(tmp_path,target,receipt_path,launch)
    assert _file_state(tmp_path) == before
    if expected:
        assert observation['error'] == expected
    else:
        result=observation['result']
        assert result['admitted'] is True and result['normal_entry_authorized'] is True
        assert result['model_execution_authorized'] is False and result['qualification_only'] is False
        assert result['target_scope'] == asdict(facade.context.scope)
        assert result['network_namespace'] != network_namespace_identity()
        assert observation['upstream_unit_calls'] == 2
