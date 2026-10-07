"""Bind the actual executable qualification into the final offline certificate.

Native test reports establish execution; these dependencies establish which
core certificate, original task and accounting records that execution consumed.
No normal-entry, model, publication or new-send authority is granted here.
"""
from __future__ import annotations

from pathlib import Path

from code2paper.agentic.digest import digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
from .artifacts import TaskScope
from .offline_admission import MAX_REPORT_BYTES, read_bound_report
from .protocol import ProtocolError, strict_json_loads
from .suite_plan import build_suite_plan
from .task_store import TaskStore

EVIDENCE_KEYS = frozenset({'ready_path','bootstrap_path','launch_path','core_receipt_path',
    'result_path','cleanup_path','provider_observations_path','cli_stdout_path',
    'cli_stderr_path','sentinel_path','task_store_path'})


def read_evidence(binding: object, expected_path: Path, *, allow_empty: bool = False) -> bytes:
    if (not isinstance(binding,dict) or set(binding) != {'path','bytes_digest','byte_length'}
            or binding['path'] != str(expected_path) or expected_path.resolve() != expected_path
            or expected_path.is_symlink()):
        raise ProtocolError('offline_operator_evidence_binding_invalid')
    if allow_empty and binding['byte_length'] == 0 and type(binding['byte_length']) is int:
        with expected_path.open('rb') as stream:raw=stream.read(1)
        if raw or binding['bytes_digest'] != digest_bytes(b''):
            raise ProtocolError('offline_operator_evidence_changed')
        return raw
    return read_bound_report(expected_path,bytes_digest=binding['bytes_digest'],byte_length=binding['byte_length'])


def validate_evidence_tree(root: Path, bindings: object) -> None:
    if not isinstance(bindings,list) or not bindings:
        raise ProtocolError('offline_operator_tree_missing')
    files=sorted(path for path in root.rglob('*') if path.is_file())
    if (any(path.is_symlink() or not path.resolve().is_relative_to(root) for path in files)
            or any(path.is_symlink() for path in root.rglob('*'))
            or [row.get('path') if isinstance(row,dict) else None for row in bindings] != [str(path) for path in files]):
        raise ProtocolError('offline_operator_tree_changed')
    for path,binding in zip(files,bindings,strict=True):read_evidence(binding,path,allow_empty=True)


def _validate_core_certificate(plan: dict, runs: list[dict], raw: bytes, *, _reuse_cache=None) -> None:
    config=plan['effective_config'];core_config={**config,'suite_plan':'dsh-stage04-core'}
    core_plan=build_suite_plan(name='dsh-stage04-core',engine_root=Path(plan['engine_root']),
        python_executable=plan['suites'][0]['argv'][0],output_root=Path(plan['suites'][0]['report_path']).parent,
        effective_config=core_config,engine_digest=plan['engine_digest'],validator_digest=plan['validator_digest'],
        composition_digest=plan['composition_digest'],candidate=plan['candidate'],node_executable=plan['suites'][1]['argv'][0],
        core_reuse_path=Path(plan['core_reuse_path']) if 'core_reuse_path' in plan else None)
    core=OfflineSuiteReceiptV1.model_validate(strict_json_loads(raw,max_bytes=MAX_REPORT_BYTES))
    from .offline_admission import verify_suite_reports
    coverage=verify_suite_reports(core_plan,runs[:2],**({'_reuse_cache':_reuse_cache} if _reuse_cache else {}))
    from code2paper.agentic.authoring_execution_identity import capture_engine_source_snapshot
    snapshot=capture_engine_source_snapshot(Path(plan['engine_root']))
    if (not snapshot.is_usable or snapshot.unstable or not core.matches(snapshot,
            validator_bundle_digest=plan['validator_digest'],effective_config_digest=digest_json(core_config))):
        raise ProtocolError('offline_operator_core_receipt_invalid')
    if (core.schema_version != '2.0' or not core.passed or core.exit_code != 0
            or core.machine_plan != core_plan or list(core.machine_runs) != runs[:2]
            or core.passed_count != coverage['passed_count']):
        raise ProtocolError('offline_operator_core_receipt_invalid')


def validate_operator_evidence(plan: dict, runs: list[dict], *, _reuse_cache=None) -> None:
    operator=plan['operator'];run=runs[-1]
    bindings=run.get('operation_evidence')
    if run.get('suite_id') != 'node-cli' or not isinstance(bindings,dict) or set(bindings) != EVIDENCE_KEYS:
        raise ProtocolError('offline_operator_evidence_missing')
    raw={key:read_evidence(binding,Path(operator[key]),allow_empty=key == 'cli_stderr_path')
         for key,binding in bindings.items()}
    task_root=Path(operator['task_root'])
    validate_evidence_tree(task_root/'run',run.get('run_artifacts'))
    validate_evidence_tree(Path(operator['budget_root']),run.get('budget_artifacts'))
    values={key:strict_json_loads(raw[key],max_bytes=MAX_REPORT_BYTES) for key in EVIDENCE_KEYS
            if key not in {'cli_stdout_path','cli_stderr_path','task_store_path'}}
    ready=values['ready_path'];bootstrap=values['bootstrap_path'];launch=values['launch_path']
    result=values['result_path'];cleanup=values['cleanup_path'];sentinel=values['sentinel_path']
    if any(not isinstance(value,dict) for value in (ready,bootstrap,launch,result,cleanup,sentinel)):
        raise ProtocolError('offline_operator_record_invalid')
    config=plan['effective_config']
    _validate_core_certificate(plan,runs,raw['core_receipt_path'],**({'_reuse_cache':_reuse_cache} if _reuse_cache else {}))
    if digest_bytes(raw['bootstrap_path']) != config['bootstrap_digest']:
        raise ProtocolError('offline_operator_bootstrap_changed')
    binding=bootstrap.get('host_launch_binding')
    if binding != {'schema_version':'DshHostLaunchBindingV1','path':operator['launch_path'],
            'bytes_digest':digest_bytes(raw['launch_path']),'byte_length':len(raw['launch_path'])}:
        raise ProtocolError('offline_operator_launch_changed')
    # Original admission validated this frozen route inside a distinct OS
    # namespace. Recheck it when the final receipt's dependencies are consumed.
    from .qualification import assert_frozen_loopback_provider
    assert_frozen_loopback_provider(launch)
    executable=str(Path(config['dsh_dev_root'])/'home/profiles/node_modules/@code2paper/dsh-bundle/lib/cli.js')
    argv=result.get('argv')
    spec=bootstrap.get('composition_spec')
    files=spec.get('files') if isinstance(spec,dict) else None
    python_owner=files.get('test_worker_launcher') if isinstance(files,dict) else None
    if (result.get('schema_version') != 'Stage04OperatorResultV1' or result.get('actual_cli_executable') is not True
            or result.get('executable') != executable or result.get('cwd') != plan['engine_root']
            or type(result.get('exit_code')) is not int or result['exit_code'] != 0
            or not isinstance(argv,list) or len(argv) != 15
            or argv[:7] != [executable,'qualify','--experimental-dsh','--candidate',plan['candidate'],'--python',argv[6]]
            or not isinstance(python_owner,str) or not Path(python_owner).is_absolute()
            or argv[6] != python_owner
            or argv[7:] != ['--engine-root',plan['engine_root'],'--bootstrap',operator['bootstrap_path'],
                '--offline-receipt',operator['core_receipt_path'],'--launch-file',operator['launch_path']]):
        raise ProtocolError('offline_operator_executable_invalid')
    lines=raw['cli_stdout_path'].splitlines()
    if not lines:raise ProtocolError('offline_operator_executable_output_missing')
    qualification=strict_json_loads(lines[-1])
    if (not isinstance(qualification,dict) or qualification.get('schema_version') != 'DshHostQualificationResultV1'
            or qualification.get('admission_scope') != 'dsh-stage04-qualification'
            or qualification.get('qualification_only') is not True
            or qualification.get('normal_entry_authorized') is not False
            or qualification.get('model_execution_authorized') is not False
            or result.get('admission_scope') != qualification['admission_scope']):
        raise ProtocolError('offline_operator_qualification_scope_invalid')
    namespace=result.get('actual_network_namespace')
    if (not isinstance(namespace,dict) or set(namespace) != {'device','inode'}
            or any(type(namespace[key]) is not int or namespace[key] <= 0 for key in namespace)
            or namespace == config['qualification_parent_namespace']):
        raise ProtocolError('offline_operator_namespace_invalid')
    validate_completed_operation(operator,bootstrap,result,qualification,ready,cleanup,sentinel,
        values['provider_observations_path'])


def validate_completed_operation(operator: dict, bootstrap: dict, result: dict, operation: dict,
        ready: dict, cleanup: dict, sentinel: dict, observations: object) -> dict:
    """Read original completed task/fee facts for either registered offline lane."""
    task_root=Path(operator['task_root'])
    scope=bootstrap.get('scope')
    if not isinstance(scope,dict) or set(scope) != {'execution_id','task_id','task_epoch'}:
        raise ProtocolError('offline_operator_task_scope_invalid')
    state=TaskStore.read_persisted(task_root/'run',TaskScope(**scope))
    receipt=state['receipt']
    if (state['state'] != 'terminal' or not isinstance(receipt,dict) or receipt.get('local_only') is not True
            or receipt.get('schema_version') != 'LocalWriterReceiptV1'
            or any(receipt.get(key) != value for key,value in scope.items())
            or receipt != result.get('receipt') or receipt != operation.get('receipt')):
        raise ProtocolError('offline_operator_original_receipt_invalid')
    budget=read_run_budget_state(Path(operator['budget_root']))
    if (budget != result.get('original_budget_state') or budget.get('status') != 'pass'
            or budget.get('failure_codes') != []
            or any(type(budget.get(key)) is not int or budget[key] != expected
                   for key,expected in (('call_count',1),('completed_call_count',1),('pending_call_count',0),
                       ('provider_usage_missing_call_count',0),('provider_usage_missing_input_tokens',0)))
            or budget.get('provider_usage_status') != 'validated'
            or budget.get('provider_usage_missing_receipts') != []
            or type(budget.get('spent_input_tokens')) is not int or budget['spent_input_tokens'] <= 0
            or type(budget.get('pending_input_tokens')) is not int or budget['pending_input_tokens'] != 0):
        raise ProtocolError('offline_operator_original_accounting_invalid')
    times=[ready.get('task_not_prepared_observed_ms'),operation.get('admission_completed_ms'),state['epoch_started_ms']]
    if (any(type(value) is not int or value <= 0 for value in times) or times != sorted(times)
            or result.get('task_not_prepared_observed_ms') != times[0]
            or result.get('admission_completed_ms') != times[1] or result.get('task_epoch_started_ms') != times[2]
            or result.get('task_epoch_started_after_admission') is not True or ready.get('task_prepared') is not False
            or ready.get('core_receipt') != operator['core_receipt_path']):
        raise ProtocolError('offline_operator_admission_order_invalid')
    initial=ready.get('original_budget_state')
    if not isinstance(initial,dict) or any(type(initial.get(key)) is not int or initial[key] != 0 for key in ('call_count','spent_input_tokens','pending_input_tokens')):
        raise ProtocolError('offline_operator_preparation_accounting_invalid')
    if (not isinstance(observations,list) or len(observations) != 2
            or any(type(value) is not int or value != 1 for value in
                (ready.get('calibration_sends'),result.get('calibration_sends'),result.get('task_sends')))):
        raise ProtocolError('offline_operator_provider_observation_invalid')
    if (set(sentinel) != {'schema_version','state','probe_refused','model_calls','network_calls'}
            or sentinel.get('schema_version') != 'PythonLlmRefusalSentinelV1' or sentinel.get('state') != 'closed'
            or sentinel.get('probe_refused') is not True
            or any(type(sentinel.get(key)) is not int or sentinel[key] != 0 for key in ('model_calls','network_calls'))
            or sentinel != result.get('sentinel') or sentinel != cleanup.get('sentinel')
            or cleanup.get('worker_scope_quiescent') is not True or cleanup.get('provider_is_offline_fake') is not True
            or cleanup.get('provider_port_rebound') is not True):
        raise ProtocolError('offline_operator_cleanup_unverified')
    return {'task_state':state,'budget':budget,'receipt':receipt}
