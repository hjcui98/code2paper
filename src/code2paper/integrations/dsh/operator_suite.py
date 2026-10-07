"""Original owner of core verification and isolated executable qualification.

The complete core certificate unlocks only the isolated offline qualifier. The
normal Host entry continues to require the final receipt, which also binds the
actual executable run and its original ledger and reader artifacts.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.authoring_execution_identity import validate_execution_composition
from code2paper.agentic.live_admission_preflight import (
    build_machine_offline_suite_receipt, write_offline_suite_receipt,
)
from .host_admission import _bootstrap_spec, _read, _validate_launch_read_set
from .protocol import ProtocolError, strict_json_loads
from .qualification import network_namespace_identity
from .suite_plan import build_suite_plan
from .suite_runner import _artifact_identity, _identity, execute_suite_plan


def _stop_owned_process(process: subprocess.Popen) -> None:
    """Stop only this owner's process group; cleanup grants no fee release."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def _wait_ready(process: subprocess.Popen, operator_root: Path, deadline: float) -> Path:
    while time.monotonic() < deadline:
        matches=sorted(operator_root.glob('stage04-provider-*/operator-ready.json'))
        if len(matches) > 1:
            raise ProtocolError('offline_operator_preparation_ambiguous')
        if matches:
            ready=matches[0]
            if ready.resolve() != ready or ready.parent.parent != operator_root:
                raise ProtocolError('offline_operator_preparation_scope_invalid')
            return ready
        if process.poll() is not None:
            raise ProtocolError('offline_operator_preparation_failed')
        time.sleep(0.1)
    raise ProtocolError('offline_operator_preparation_timeout')


def _artifact(path: Path) -> dict:
    if path.resolve() != path or not path.is_file():
        raise ProtocolError('offline_operator_artifact_invalid')
    digest,length=_artifact_identity(path)
    return {'path':str(path),'bytes_digest':digest,'byte_length':length}


def _tree_artifacts(root: Path) -> list[dict]:
    if root.resolve() != root or not root.is_dir():
        raise ProtocolError('offline_operator_artifact_tree_invalid')
    files=sorted(path for path in root.rglob('*') if path.is_file())
    if any(path.is_symlink() or not path.resolve().is_relative_to(root) for path in files):
        raise ProtocolError('offline_operator_artifact_tree_invalid')
    return [_artifact(path) for path in files]


def execute_managed_stage04(*, engine_root: Path, python_executable: str,
        output_root: Path, candidate: str, timeout_seconds: float,
        core_reuse_path: Path | None = None) -> tuple[dict,list[dict],object]:
    """Run one bounded original core and one real isolated CLI qualification.

    The operator child is started before core verification so its frozen
    composition is included in both plans. Its original preparation does not
    prepare the task or consume its run budget. No caller can supply a ready
    artifact or choose another executable command.
    """
    if (not 0 < timeout_seconds < float('inf') or not candidate
            or Path(candidate).name != candidate or candidate in {'.','..'}):
        raise ProtocolError('offline_managed_qualification_arguments_invalid')
    root=engine_root.resolve()
    if not output_root.is_absolute() or output_root.resolve() != output_root:
        raise ProtocolError('offline_output_root_invalid')
    deadline=time.monotonic()+timeout_seconds
    parent_namespace=network_namespace_identity()
    before,validator_before=_identity(root)
    operator_root=output_root/'operator'
    report=operator_root/'node-events.jsonl'
    output=output_root/'operator-output.log'
    if operator_root.exists() or output.exists():
        raise ProtocolError('offline_output_not_fresh')
    entry=root/'integrations/dsh/tests/host-provider.test.ts'
    command=[python_executable,str(root/'scripts/dsh_dev.py'),'--candidate',candidate,
        'test','--operator-package','--qualification-root',str(output_root),
        '--output-root',str(operator_root),
        '--report-path',str(report),str(entry)]
    if core_reuse_path is not None:
        command[-1:-1]=['--core-reuse-readonly',str(core_reuse_path)]
    environment=dict(os.environ)
    for key in ('OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY'):
        environment.pop(key,None)
    environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(root/'src'),
        C2P_DSH_CANDIDATE=candidate,C2P_DSH_DEV_ROOT=str(root/'.dsh-dev/candidates'/candidate))
    process=None
    with output.open('xb') as stream:
        try:
            process=subprocess.Popen(command,cwd=root,env=environment,stdout=stream,
                stderr=subprocess.STDOUT,start_new_session=True)
            ready_path=_wait_ready(process,operator_root,min(deadline,time.monotonic()+120))
            ready=strict_json_loads(_read(ready_path),max_bytes=32 << 20)
            task_root=ready_path.parent
            expected={'bootstrap':str(task_root/'bootstrap.json'),
                'launch':str(task_root/'operator-launch.json'),
                'core_receipt':str(task_root/'operator-core-receipt.json'),
                'receipt':str(task_root/'operator-offline-receipt.json'),
                'task_root':str(task_root),'candidate':candidate}
            if (not isinstance(ready,dict) or ready.get('schema_version') != 'Stage04OperatorPreparationV1'
                    or any(ready.get(key) != value for key,value in expected.items())
                    or ready.get('task_prepared') is not False
                    or type(ready.get('task_not_prepared_observed_ms')) is not int
                    or ready['task_not_prepared_observed_ms'] <= 0
                    or type(ready.get('calibration_sends')) is not int
                    or ready['calibration_sends'] != 1):
                raise ProtocolError('offline_operator_preparation_invalid')
            initial_budget=ready.get('original_budget_state')
            if (not isinstance(initial_budget,dict) or any(type(initial_budget.get(key)) is not int
                    or initial_budget[key] != 0 for key in
                    ('call_count','spent_input_tokens','pending_input_tokens'))
                    or Path(expected['core_receipt']).exists()
                    or Path(expected['receipt']).exists()):
                raise ProtocolError('offline_operator_preparation_not_fresh')
            bootstrap=Path(expected['bootstrap'])
            bootstrap_raw=_read(bootstrap)
            frozen=strict_json_loads(bootstrap_raw,max_bytes=32 << 20)
            spec=_bootstrap_spec(frozen,root)
            launch_path=Path(expected['launch'])
            launch_raw=_read(launch_path)
            launch=strict_json_loads(launch_raw,max_bytes=32 << 20)
            binding=frozen.get('host_launch_binding')
            if (not isinstance(binding,dict) or set(binding) != {'schema_version','path','bytes_digest','byte_length'}
                    or binding.get('schema_version') != 'DshHostLaunchBindingV1'
                    or binding.get('path') != str(launch_path)
                    or type(binding.get('byte_length')) is not int
                    or binding['byte_length'] != len(launch_raw)
                    or binding.get('bytes_digest') != digest_bytes(launch_raw)
                    or not isinstance(launch,dict)):
                raise ProtocolError('offline_operator_launch_binding_invalid')
            _validate_launch_read_set(launch,spec)
            def verify():
                if _read(bootstrap) != bootstrap_raw or _read(launch_path) != launch_raw:
                    raise ProtocolError('offline_bootstrap_changed')
                return validate_execution_composition(spec,frozen['composition'],engine_root=root)['composition_digest']
            composition=verify()
            stage=strict_json_loads(_read(spec.files['stage']),max_bytes=32 << 20)
            dev_root=(root/'.dsh-dev/candidates'/candidate).resolve()
            if (not isinstance(stage,dict) or stage.get('candidate') != candidate
                    or stage.get('dev_root') != str(dev_root)
                    or spec.files['stage'].resolve() != dev_root/'staging.json'):
                raise ProtocolError('offline_candidate_mismatch')
            config={'marker':'not live_llm','suite_plan':'dsh-stage04',
                'runtime':spec.effective_config,'bootstrap_digest':digest_bytes(bootstrap_raw),
                'candidate':candidate,'dsh_dev_root':str(dev_root),
                'qualification_parent_namespace':parent_namespace,'operator_task_root':str(task_root)}
            arguments=dict(engine_root=root,python_executable=python_executable,output_root=output_root,
                engine_digest=before.source_digest,validator_digest=validator_before.digest,
                composition_digest=composition,candidate=candidate,node_executable=str(spec.files['node']),
                core_reuse_path=core_reuse_path)
            core=build_suite_plan(name='dsh-stage04-core',effective_config={**config,'suite_plan':'dsh-stage04-core'},**arguments)
            plan=build_suite_plan(name='dsh-stage04',effective_config=config,**arguments)
            suite=plan['suites'][-1]
            if suite['launch_argv'] != command:
                raise ProtocolError('offline_operator_command_mismatch')
            (output_root/'plan.json').write_bytes(canonical_json_bytes(plan))
            (output_root/'core-plan.json').write_bytes(canonical_json_bytes(core))
            if core_reuse_path is None:
                runs,final=execute_suite_plan(core,timeout_seconds=max(0.001,deadline-time.monotonic()),verify_composition=verify)
            else:
                # Reuse is verified evidence, never a caller-supplied PASS or a
                # replay of the interrupted operator. Qualification stays fresh.
                from .core_reuse import bind_reused_core
                runs=bind_reused_core(core,core_reuse_path)
                final,_=_identity(root)
                verify()
            (output_root/'core-suite-runs.json').write_bytes(canonical_json_bytes(runs))
            core_receipt=build_machine_offline_suite_receipt(plan=core,runs=runs,engine_snapshot=final)
            write_offline_suite_receipt(Path(expected['core_receipt']),core_receipt)
            exit_code=124
            if core_receipt.passed and time.monotonic() < deadline:
                try:
                    exit_code=process.wait(timeout=deadline-time.monotonic())
                except subprocess.TimeoutExpired:
                    _stop_owned_process(process)
            else:
                _stop_owned_process(process)
                exit_code=process.returncode if process.returncode not in (None,0) else 1
            stream.flush();os.fsync(stream.fileno())
            after,validator_after=_identity(root)
            composition_after=verify()
            report_digest,report_bytes=_artifact_identity(report,allow_missing=True)
            output_digest,output_bytes=_artifact_identity(output)
            run={key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')}
            run.update(report_digest=report_digest,report_bytes=report_bytes,
                output_path=str(output),output_digest=output_digest,output_bytes=output_bytes,exit_code=exit_code,
                engine_before=before.source_digest,engine_after=after.source_digest,
                validator_before=validator_before.digest,validator_after=validator_after.digest,
                composition_before=composition,composition_after=composition_after,
                effective_config_digest=digest_json(suite['effective_config']),
                operation_evidence={},budget_artifacts=[],run_artifacts=[])
            # Capture only after the native operator process has exited. Missing
            # closure artifacts preserve an actual failed run; never invent one.
            if exit_code == 0:
                keys=('bootstrap_path','launch_path','core_receipt_path','ready_path','result_path',
                    'cleanup_path','provider_observations_path','cli_stdout_path','cli_stderr_path',
                    'sentinel_path','task_store_path')
                try:
                    run['operation_evidence']={key:_artifact(Path(plan['operator'][key])) for key in keys}
                    run['budget_artifacts']=_tree_artifacts(Path(plan['operator']['budget_root']))
                    run['run_artifacts']=_tree_artifacts(task_root/'run')
                except (ProtocolError,OSError,KeyError):
                    # Final original validator identifies missing/tampered
                    # evidence. Preserve native exit, report and captured facts.
                    pass
            runs.append(run)
            (output_root/'suite-runs.json').write_bytes(canonical_json_bytes(runs))
            return plan,runs,after
        finally:
            if process is not None:
                _stop_owned_process(process)
