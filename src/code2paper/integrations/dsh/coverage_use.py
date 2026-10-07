"""Registered cold normal CLI use of an already complete offline certificate.

This companion consumes coverage; it never recursively contributes to the
certificate it consumes. Original task, budget and domain owners remain sole
fact authority. Missing native execution or closure is a failed use receipt.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import shutil
import time

from code2paper.agentic.authoring_execution_identity import validate_execution_composition
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from .host_admission import _bootstrap_spec, _read
from .offline_admission import read_bound_report, validate_node_report
from .operator_evidence import EVIDENCE_KEYS, read_evidence, validate_completed_operation, validate_evidence_tree
from .operator_suite import _artifact, _stop_owned_process, _tree_artifacts, _wait_ready
from .protocol import ProtocolError, strict_json_loads
from .suite_runner import _artifact_identity, _identity

USE_EVIDENCE_KEYS=EVIDENCE_KEYS-{'core_receipt_path'}
USE_VERSION='dsh-stage04-cold-use/1'


def build_coverage_use_plan(*, certificate_path: Path, certificate: OfflineSuiteReceiptV1,
        output_root: Path, task_root: Path, python_executable: str) -> dict:
    """Fixed native entry and command; caller cannot replace the discovered test."""
    qualified=certificate.machine_plan
    if not isinstance(qualified,dict) or qualified.get('name') != 'dsh-stage04':
        raise ProtocolError('coverage_use_full_certificate_required')
    root=Path(qualified['engine_root'])
    if (any(not path.is_absolute() or path.resolve() != path for path in (certificate_path,output_root,task_root))
            or task_root.parent != output_root or not task_root.name.startswith('stage04-provider-')
            or not Path(python_executable).is_absolute()):
        raise ProtocolError('coverage_use_scope_invalid')
    report=output_root/'node-events.jsonl'
    output=output_root/'operator-output.log'
    entry=root/'integrations/dsh/tests/host-provider.test.ts'
    node=qualified['suites'][1]['argv'][0]
    operator={key:str(task_root/name) for key,name in {
        'ready_path':'operator-ready.json','bootstrap_path':'bootstrap.json','launch_path':'operator-launch.json',
        'core_receipt_path':'operator-core-receipt.json','result_path':'operator-result.json',
        'cleanup_path':'cleanup.json','provider_observations_path':'provider-observations.json',
        'cli_stdout_path':'operator-cli-output.log','cli_stderr_path':'operator-cli-error.log',
        'sentinel_path':'python-sentinel.json','task_store_path':'run/dsh-tasks.sqlite3'}.items()}
    operator.update(task_root=str(task_root),budget_root=str(task_root/'run/artifacts/06_authoring/invocations'))
    value={'schema_version':'DshStage04CoverageUsePlanV1','version':USE_VERSION,
        'engine_root':str(root),'engine_digest':qualified['engine_digest'],'validator_digest':qualified['validator_digest'],
        'candidate':qualified['candidate'],'certificate_path':str(certificate_path),
        'certificate_digest':digest_bytes(_read(certificate_path)),
        'output_root':str(output_root),'operator':operator,'python_executable':python_executable,
        'suite_id':'node-normal','runner':'node','cwd':str(root/'integrations/dsh'),
        'discovered_files':[str(entry)],'source_files':{str(entry):digest_bytes(entry.read_bytes())},
        'report_path':str(report),'output_path':str(output),
        'argv':[node,'--test','--test-concurrency=1','--test-reporter=spec',
            '--test-reporter='+str(root/'integrations/dsh/dev/toolchain/suite-reporter.mjs'),
            '--test-reporter-destination=stdout','--test-reporter-destination='+str(report),str(entry)],
        'launch_argv':[python_executable,str(root/'scripts/dsh_dev.py'),'--candidate',qualified['candidate'],
            'test','--coverage-receipt',str(certificate_path),'--output-root',str(output_root),
            '--report-path',str(report),str(entry)]}
    return {**value,'plan_digest':digest_json(value)}



TARGET_PERMIT_KEYS = frozenset({'schema_version','admitted','scope','qualification_only',
    'normal_entry_authorized','model_execution_authorized','parallel_agents','candidate',
    'engine_digest','validator_digest','composition_digest','effective_config_digest',
    'bootstrap_digest','launch_digest','receipt_digest','coverage_receipt_digest',
    'runtime_authority_digest','target_scope','domain_read_set_digest','model_config_digest',
    'backend_binding_digest','network_namespace'})


def _validate_target_permit(plan: dict, result: dict, operation: dict) -> dict:
    permit=operation.get('admission') if isinstance(operation,dict) else None
    if (not isinstance(operation,dict) or set(operation) != {'schema_version','admission','admission_completed_ms','receipt'} or operation.get('schema_version') != 'DshHostExecutionResultV1'
            or result.get('normal_cli_result') != operation or result.get('target_admission') != permit
            or not isinstance(permit,dict) or set(permit) != TARGET_PERMIT_KEYS
            or permit.get('schema_version') != 'DshTargetAdmissionV1'
            or permit.get('admitted') is not True or permit.get('normal_entry_authorized') is not True
            or permit.get('qualification_only') is not False or permit.get('model_execution_authorized') is not False
            or permit.get('parallel_agents') is not False or permit.get('scope') != 'dsh-stage04-offline'
            or result.get('admission_scope') != permit['scope']
            or result.get('coverage_receipt') != plan['certificate_path']
            or permit.get('coverage_receipt_digest') != plan['certificate_digest']
            or permit.get('receipt_digest') != plan['certificate_digest']):
        raise ProtocolError('coverage_use_target_permit_invalid')
    return permit


def verify_finished_backend(*, task_root: Path, scope: dict, resource_key: str,
        backend_binding_digest: str) -> dict:
    """Read-only proof of the completed Host's original owner retirement."""
    from .artifacts import ArtifactStore,TaskScope
    from .writer_contract import ArtifactRefV1
    from .protocol import parse_model
    from .task_store import SerialBackendAdmission
    store=ArtifactStore.open_readonly(task_root/'run',TaskScope(**scope))
    admission,backend=SerialBackendAdmission.observe_initial(task_root/'backend',resource_key,
        execution_id=scope['execution_id'],run_root=task_root/'run')
    original_owner={'schema_version':'serial-backend-admission/1','execution_id':scope['execution_id'],
        'run_root':str(task_root/'run'),'resource_key':resource_key}
    if (backend['state'] != 'empty'
            or backend_binding_digest not in {
                digest_json({'state':'empty','owner':None}),digest_json({'state':'owned','owner':original_owner})}):
        raise ProtocolError('coverage_use_original_binding_changed')
    # The finished Host retires its owner. Validate its original immutable
    # retirement rather than requiring the old admission row to remain held.
    from .task_store import TaskStore
    from code2paper.agentic.unified_invocation_ledger import read_dsh_invocation_events
    task=TaskStore.read_persisted(task_root/'run',TaskScope(**scope))
    quiescence=task['provider_quiescence']
    if quiescence is None:raise ProtocolError('coverage_use_backend_retirement_unproven')
    ref=parse_model(canonical_json_bytes(quiescence['quiescence_ref']),ArtifactRefV1)
    finish=store.read_json(ref)
    facts=read_dsh_invocation_events(task_root/'run/artifacts/06_authoring/invocations',finish['request_id'])
    admission._verify_native_quiescence(store,task,finish,facts)
    import sqlite3
    key=digest_json({'owner':original_owner,'task_scope':scope,'quiescence_ref':ref.model_dump(mode='json')})
    with sqlite3.connect(admission.path.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT receipt FROM release_history WHERE release_key=?',(key,)).fetchone()
    if row is None:raise ProtocolError('coverage_use_backend_retirement_unproven')
    release=strict_json_loads(row[0])
    if (release.get('schema_version') != 'DshSerialBackendReleaseV1'
            or admission._release_binding(release,key) != {
                'owner':original_owner,'task_scope':scope,'quiescence_ref':ref.model_dump(mode='json')}):
        raise ProtocolError('coverage_use_backend_retirement_unproven')
    return release


def validate_coverage_use(plan: dict, run: dict) -> dict:
    raw_certificate=_read(Path(plan['certificate_path']))
    certificate=OfflineSuiteReceiptV1.model_validate(strict_json_loads(raw_certificate,max_bytes=32 << 20))
    expected=build_coverage_use_plan(certificate_path=Path(plan['certificate_path']),certificate=certificate,
        output_root=Path(plan['output_root']),task_root=Path(plan['operator']['task_root']),
        python_executable=plan['python_executable'])
    if plan != expected:raise ProtocolError('coverage_use_plan_changed')
    before,validator=_identity(Path(plan['engine_root']))
    if (digest_bytes(raw_certificate) != plan['certificate_digest']
            or not certificate.matches(before,validator_bundle_digest=validator.digest)):
        raise ProtocolError('coverage_use_certificate_stale_or_incomplete')
    keys={'suite_id','runner','cwd','argv','report_path','report_digest','report_bytes','output_path','output_digest',
        'output_bytes','exit_code','engine_before','engine_after','validator_before','validator_after',
        'composition_before','composition_after','operation_evidence','run_artifacts','budget_artifacts'}
    if (set(run) != keys or any(run.get(key) != plan[key] for key in ('suite_id','runner','cwd','argv','report_path','output_path'))
            or type(run.get('exit_code')) is not int or run['exit_code'] != 0
            or any(run[key] != plan['engine_digest'] for key in ('engine_before','engine_after'))
            or any(run[key] != plan['validator_digest'] for key in ('validator_before','validator_after'))):
        raise ProtocolError('coverage_use_run_binding_invalid')
    report=read_bound_report(run['report_path'],bytes_digest=run['report_digest'],byte_length=run['report_bytes'])
    read_bound_report(run['output_path'],bytes_digest=run['output_digest'],byte_length=run['output_bytes'])
    coverage=validate_node_report(report,cwd=plan['cwd'],argv=[plan['argv'][0],*plan['discovered_files']],
        exec_argv=plan['argv'][1:-len(plan['discovered_files'])])
    if coverage['entry_files'] != plan['discovered_files']:
        raise ProtocolError('coverage_use_native_entry_missing')
    operator=plan['operator'];bindings=run['operation_evidence']
    if not isinstance(bindings,dict) or set(bindings) != USE_EVIDENCE_KEYS:
        raise ProtocolError('coverage_use_evidence_missing')
    raw={key:read_evidence(bindings[key],Path(operator[key]),allow_empty=key == 'cli_stderr_path')
        for key in USE_EVIDENCE_KEYS}
    task_root=Path(operator['task_root'])
    validate_evidence_tree(task_root/'run',run['run_artifacts'])
    validate_evidence_tree(Path(operator['budget_root']),run['budget_artifacts'])
    values={key:strict_json_loads(value,max_bytes=32 << 20) for key,value in raw.items()
        if key not in {'task_store_path','cli_stdout_path','cli_stderr_path'}}
    bootstrap=values['bootstrap_path'];result=values['result_path'];launch=values['launch_path']
    ready=values['ready_path'];cleanup=values['cleanup_path'];sentinel=values['sentinel_path']
    if any(not isinstance(value,dict) for value in (bootstrap,result,launch,ready,cleanup,sentinel)):
        raise ProtocolError('coverage_use_record_invalid')
    lines=raw['cli_stdout_path'].splitlines()
    if not lines:raise ProtocolError('coverage_use_cli_output_missing')
    operation=strict_json_loads(lines[-1]);permit=operation.get('admission') if isinstance(operation,dict) else None
    permit=_validate_target_permit(plan,result,operation)
    scope=bootstrap.get('scope')
    qualified_bootstrap=strict_json_loads(_read(Path(certificate.machine_plan['operator']['bootstrap_path'])),max_bytes=32 << 20)
    if (permit.get('target_scope') != scope or not isinstance(scope,dict)
            or scope.get('execution_id') == qualified_bootstrap['scope']['execution_id']):
        raise ProtocolError('coverage_use_target_not_fresh')
    spec=_bootstrap_spec(bootstrap,Path(plan['engine_root']))
    composition=validate_execution_composition(spec,bootstrap['composition'],engine_root=Path(plan['engine_root']))
    from .target_admission import _launch, runtime_authority_projection, validate_local_transport
    actual_launch,_=_launch(bootstrap,spec,composition,Path(operator['launch_path']))
    qualified_spec=_bootstrap_spec(qualified_bootstrap,Path(plan['engine_root']))
    qualified_launch=strict_json_loads(_read(Path(certificate.machine_plan['operator']['launch_path'])))
    stable=runtime_authority_projection(qualified_bootstrap,qualified_launch,plan['candidate'])
    if runtime_authority_projection(bootstrap,actual_launch,plan['candidate']) != stable:
        raise ProtocolError('coverage_use_runtime_authority_changed')
    validate_local_transport(qualified_spec,spec,Path(certificate.machine_plan['operator']['task_root']),task_root)
    from .qualification import assert_frozen_loopback_provider
    assert_frozen_loopback_provider(launch)
    expected_digests={'engine_digest':plan['engine_digest'],'validator_digest':plan['validator_digest'],
        'candidate':plan['candidate'],'bootstrap_digest':digest_bytes(raw['bootstrap_path']),
        'launch_digest':digest_bytes(raw['launch_path']),'composition_digest':composition['composition_digest'],
        'effective_config_digest':digest_json(spec.effective_config),'runtime_authority_digest':digest_json(stable),
        'model_config_digest':digest_json(stable['qualified_profile'])}
    if (any(permit.get(key) != value for key,value in expected_digests.items())
            or run['composition_before'] != composition['composition_digest']
            or run['composition_after'] != composition['composition_digest']):
        raise ProtocolError('coverage_use_target_binding_changed')
    executable=str(Path(certificate.machine_plan['effective_config']['dsh_dev_root'])/
        'home/profiles/node_modules/@code2paper/dsh-bundle/lib/cli.js')
    argv=[executable,'run','--experimental-dsh','--candidate',plan['candidate'],'--python',
        str(spec.files['test_worker_launcher']),'--engine-root',plan['engine_root'],'--bootstrap',operator['bootstrap_path'],
        '--offline-receipt',plan['certificate_path'],'--launch-file',operator['launch_path']]
    if (result.get('schema_version') != 'Stage04OperatorResultV1' or result.get('actual_cli_executable') is not True
            or result.get('argv') != argv or result.get('executable') != executable or result.get('cwd') != plan['engine_root']
            or type(result.get('exit_code')) is not int or result['exit_code'] != 0
            or ready.get('receipt') != plan['certificate_path']):
        raise ProtocolError('coverage_use_executable_invalid')
    namespace=result.get('actual_network_namespace')
    if (not isinstance(namespace,dict) or set(namespace) != {'device','inode'}
            or any(type(namespace[key]) is not int or namespace[key] <= 0 for key in namespace)
            or namespace != permit.get('network_namespace')
            or namespace == certificate.machine_plan['effective_config']['qualification_parent_namespace']):
        raise ProtocolError('coverage_use_namespace_invalid')
    completed=validate_completed_operation(operator,bootstrap,result,operation,ready,cleanup,sentinel,
        values['provider_observations_path'])
    from .artifacts import ArtifactStore,TaskScope
    from .writer_contract import ArtifactRefV1
    from .protocol import parse_model
    from .task_store import SerialBackendAdmission
    store=ArtifactStore.open_readonly(task_root/'run',TaskScope(**scope))
    frozen=store.read_json(parse_model(canonical_json_bytes(launch['frozen_ref']),ArtifactRefV1))
    if permit.get('domain_read_set_digest') != digest_json(frozen['refs']):
        raise ProtocolError('coverage_use_original_binding_changed')
    verify_finished_backend(task_root=task_root,scope=scope,
        resource_key=spec.effective_config['backend_resource_key'],
        backend_binding_digest=permit.get('backend_binding_digest'))
    if _read(Path(plan['certificate_path'])) != raw_certificate:
        raise ProtocolError('coverage_use_certificate_changed')
    return {'passed_count':coverage['counts']['tests'],'target_admission_digest':digest_json(permit),
        'target_scope':scope,'receipt_digest':digest_json(completed['receipt']),
        'budget_digest':digest_json(completed['budget'])}


def execute_coverage_use(*, certificate_path: Path, output_root: Path, python_executable: str,
        timeout_seconds: float) -> dict:
    if type(timeout_seconds) not in (int,float) or not 0 < timeout_seconds < float('inf'):
        raise ProtocolError('coverage_use_timeout_invalid')
    certificate_raw=_read(certificate_path)
    certificate=OfflineSuiteReceiptV1.model_validate(strict_json_loads(certificate_raw,max_bytes=32 << 20))
    qualified=certificate.machine_plan
    if not isinstance(qualified,dict):raise ProtocolError('coverage_use_full_certificate_required')
    root=Path(qualified['engine_root']);before,validator_before=_identity(root)
    if not certificate.matches(before,validator_bundle_digest=validator_before.digest):
        raise ProtocolError('coverage_use_certificate_stale_or_incomplete')
    if output_root.exists() or not output_root.is_absolute() or output_root.resolve() != output_root:
        raise ProtocolError('offline_output_not_fresh')
    # The original launcher creates this fresh root, retaining its usual
    # read-only source/runtime mounts and independent network namespace.
    output=output_root.parent/'normal-launch-output.log'
    if output.exists():raise ProtocolError('offline_output_not_fresh')
    report=output_root/'node-events.jsonl'
    command=[python_executable,str(root/'scripts/dsh_dev.py'),'--candidate',qualified['candidate'],
        'test','--coverage-receipt',str(certificate_path),'--output-root',str(output_root),
        '--report-path',str(report),str(root/'integrations/dsh/tests/host-provider.test.ts')]
    environment=dict(os.environ)
    for key in ('OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY'):environment.pop(key,None)
    environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(root/'src'),
        C2P_DSH_CANDIDATE=qualified['candidate'],C2P_DSH_DEV_ROOT=qualified['effective_config']['dsh_dev_root'])
    deadline=time.monotonic()+timeout_seconds;process=None;plan=None;run=None;failure=''
    with output.open('xb') as stream:
        try:
            process=subprocess.Popen(command,cwd=root,env=environment,stdout=stream,
                stderr=subprocess.STDOUT,start_new_session=True)
            ready_path=_wait_ready(process,output_root,min(deadline,time.monotonic()+120))
            task_root=ready_path.parent
            plan=build_coverage_use_plan(certificate_path=certificate_path,certificate=certificate,
                output_root=output_root,task_root=task_root,python_executable=python_executable)
            if plan['launch_argv'] != command:raise ProtocolError('coverage_use_command_mismatch')
            bootstrap=strict_json_loads(_read(Path(plan['operator']['bootstrap_path'])),max_bytes=32 << 20)
            spec=_bootstrap_spec(bootstrap,root)
            composition=validate_execution_composition(spec,bootstrap['composition'],engine_root=root)['composition_digest']
            try:exit_code=process.wait(timeout=max(.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:_stop_owned_process(process);exit_code=124
            stream.flush();os.fsync(stream.fileno())
            after,validator_after=_identity(root)
            composition_after=validate_execution_composition(spec,bootstrap['composition'],engine_root=root)['composition_digest']
            # Mirror the actual launcher output into the fixed plan report
            # dependency only after it exited; this is a byte-for-byte copy.
            bound_output=Path(plan['output_path']);shutil.copyfile(output,bound_output)
            report_digest,report_bytes=_artifact_identity(report,allow_missing=True)
            output_digest,output_bytes=_artifact_identity(bound_output)
            run={key:plan[key] for key in ('suite_id','runner','cwd','argv','report_path','output_path')}
            run.update(report_digest=report_digest,report_bytes=report_bytes,output_digest=output_digest,
                output_bytes=output_bytes,exit_code=exit_code,engine_before=before.source_digest,engine_after=after.source_digest,
                validator_before=validator_before.digest,validator_after=validator_after.digest,
                composition_before=composition,composition_after=composition_after,
                operation_evidence={},run_artifacts=[],budget_artifacts=[])
            if exit_code == 0:
                operator=plan['operator']
                run['operation_evidence']={key:_artifact(Path(operator[key])) for key in USE_EVIDENCE_KEYS}
                run['run_artifacts']=_tree_artifacts(task_root/'run')
                run['budget_artifacts']=_tree_artifacts(Path(operator['budget_root']))
            coverage=validate_coverage_use(plan,run)
        except (ProtocolError,OSError,ValueError,KeyError,TypeError,IndexError) as error:
            coverage={};failure=error.code if isinstance(error,ProtocolError) else 'coverage_use_unavailable_or_invalid'
        finally:
            if process is not None:_stop_owned_process(process)
    receipt={'schema_version':'DshStage04CoverageUseReceiptV1','version':USE_VERSION,'passed':not failure,
        'coverage_failure_code':failure,'coverage_receipt_path':str(certificate_path),
        'coverage_receipt_digest':digest_bytes(certificate_raw),'machine_plan':plan,'machine_run':run,**coverage}
    (output_root.parent/'normal-use-receipt.json').write_bytes(canonical_json_bytes(receipt))
    return receipt
