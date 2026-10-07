"""Versioned operator test plans. Missing required tests fail before execution.

Plans cover offline verification only; they cannot grant model/task authority.
Legacy and DSH remain separate scopes. Reports never backfill a missing suite.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import REQUIRED_OFFLINE_TEST_PLAN
from .protocol import ProtocolError, strict_json_loads

DSH_REQUIRED_PYTHON = (
    'tests/integrations/dsh/test_task_recovery.py',
    'tests/integrations/dsh/test_invocation_events.py',
    'tests/integrations/dsh/test_host_crash_recovery.py',
    'tests/integrations/dsh/test_host_recovery_boundaries.py',
    'tests/integrations/dsh/test_serial_writer_e2e.py',
    'tests/integrations/dsh/test_dsh_admission.py',
    'tests/integrations/dsh/test_qualification.py',
    'tests/integrations/dsh/test_operator_evidence.py',
    'tests/integrations/dsh/test_target_admission.py',
    'tests/integrations/dsh/test_target_admission_integration.py',
    'tests/integrations/dsh/test_coverage_use.py',
    'tests/integrations/dsh/test_offline_inputs.py',
    'tests/integrations/dsh/test_native_rejection_retirement.py',
    'tests/integrations/dsh/test_native_stop_retirement.py',
    'tests/integrations/dsh/test_text_rejection_completion.py',
    'tests/integrations/dsh/test_unknown_tool_completion.py',
    'tests/integrations/dsh/test_unknown_tool_retirement.py',
    'tests/integrations/dsh/test_unknown_abort_recovery.py',
    'tests/integrations/dsh/test_native_tool_choice_projection.py',
    'tests/integrations/dsh/test_native_parameter_schema.py',
    'tests/integrations/dsh/test_text_stop_transport_proof.py',
    'tests/integrations/dsh/test_text_stop_recovery.py',
    'tests/integrations/dsh/test_scoped_reads.py',
    'tests/integrations/dsh/test_multistep_context.py',
    'tests/integrations/dsh/test_multistep_accounting.py',
    'tests/integrations/dsh/test_step_admission.py',
    'tests/integrations/dsh/test_epoch_completion.py',
    'tests/integrations/dsh/test_auxiliary_admission.py',
    'tests/integrations/dsh/test_dynamic_wire_compat.py',
)
DSH_REQUIRED_NODE = (
    'integrations/dsh/tests/host.test.ts',
    'integrations/dsh/tests/serial-writer.test.ts',
    'integrations/dsh/tests/pi-ai-wire.test.ts',
    'integrations/dsh/tests/cli.test.ts',
    'integrations/dsh/tests/serial-writer-cancel.test.ts',
    'integrations/dsh/tests/provider-scope.test.ts',
    'integrations/dsh/tests/writer-formula-binding.test.ts',
    'integrations/dsh/tests/writer-atom-binding.test.ts',
    'integrations/dsh/tests/writer-cap-drift.test.ts',
    'integrations/dsh/tests/writer-composition-drift.test.ts',
    'integrations/dsh/tests/writer-budget-exhausted.test.ts',
    'integrations/dsh/tests/writer-raw-missing.test.ts',
    'integrations/dsh/tests/writer-raw-corrupt.test.ts',
    'integrations/dsh/tests/writer-release-failure.test.ts',
    'integrations/dsh/tests/writer-native-schema-rejection.test.ts',
    'integrations/dsh/tests/writer-inline-formula.test.ts',
    'integrations/dsh/tests/writer-formula-metadata.test.ts',
    'integrations/dsh/tests/writer-missing-witness.test.ts',
    'integrations/dsh/tests/writer-text-stop.test.ts',
    'integrations/dsh/tests/writer-native-stop.test.ts',
    'integrations/dsh/tests/writer-native-stop-rejected.test.ts',
    'integrations/dsh/tests/writer-unknown-tool.test.ts',
    'integrations/dsh/tests/writer-tool-choice-draft.test.ts',
    'integrations/dsh/tests/writer-tool-choice-formula-rejection.test.ts',
    'integrations/dsh/tests/writer-tool-choice-text-rejection.test.ts',
    'integrations/dsh/tests/writer-provider-error.test.ts',
    'integrations/dsh/tests/writer-provider-error-cached-usage.test.ts',
    'integrations/dsh/tests/writer-finish-without-usage.test.ts',
    'integrations/dsh/tests/writer-usage-without-finish.test.ts',
    'integrations/dsh/tests/writer-disconnect.test.ts',
    'integrations/dsh/tests/writer-timeout.test.ts',
    'integrations/dsh/tests/multistep.test.ts',
    'integrations/dsh/tests/context-replay.test.ts',
    'integrations/dsh/tests/epoch-compaction.test.ts',
    'integrations/dsh/tests/compaction-multistep.test.ts',
    'integrations/dsh/tests/compaction-budget.test.ts',
    'integrations/dsh/tests/step-renderer.test.ts',

)
PLAN_VERSIONS = {'legacy': 'legacy-offline/2', 'dsh-stage04-core':'dsh-stage04-core/12',
    'dsh-stage04': 'dsh-stage04-offline/12'}
DSH_PLANS = frozenset({'dsh-stage04-core','dsh-stage04'})


def _public_config(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if not isinstance(key,str) or key.replace('_','').replace('-','').lower() in {
                'apikey','authorization','password','secret','accesstoken','bearertoken','capability','credential','credentials'}:
                raise ProtocolError('offline_config_contains_credentials')
            _public_config(item)
    elif isinstance(value,list):
        for item in value:_public_config(item)


def _discover(root: Path, target: str, pattern: str) -> list[str]:
    path = root / target
    if not path.exists():raise ProtocolError('offline_required_test_missing')
    files=[path] if path.is_file() else sorted(path.rglob(pattern))
    if not files:raise ProtocolError('offline_required_test_empty')
    if any(not file.is_file() or not file.resolve().is_relative_to(root) for file in files):
        raise ProtocolError('offline_test_source_outside_engine')
    return [file.relative_to(root).as_posix() for file in files]


def build_suite_plan(*, name: str, engine_root: Path, python_executable: str,
        output_root: Path, effective_config: dict[str, Any], engine_digest: str,
        validator_digest: str, composition_digest: str = '', candidate: str = '',
        node_executable: str = '', core_reuse_path: Path | None = None) -> dict[str, Any]:
    if name not in PLAN_VERSIONS:raise ProtocolError('offline_plan_unknown')
    root=engine_root.resolve()
    if (not effective_config or not engine_digest or not validator_digest or not output_root.is_absolute()
            or not Path(python_executable).is_absolute()):raise ProtocolError('offline_plan_identity_missing')
    if any(re.fullmatch(r'sha256:[0-9a-f]{64}', value) is None for value in (engine_digest,validator_digest)):
        raise ProtocolError('offline_plan_digest_invalid')
    _public_config(effective_config)
    effective_config=strict_json_loads(canonical_json_bytes(effective_config))
    expected_keys={'marker','suite_plan'} if name == 'legacy' else {
        'marker','suite_plan','runtime','bootstrap_digest','candidate','dsh_dev_root',
        'qualification_parent_namespace','operator_task_root'}
    if set(effective_config) != expected_keys or effective_config.get('marker') != 'not live_llm' or effective_config.get('suite_plan') != name:
        raise ProtocolError('offline_effective_config_invalid')
    targets=list(REQUIRED_OFFLINE_TEST_PLAN)
    if name in DSH_PLANS:
        if not composition_digest or not candidate or not Path(node_executable).is_absolute():
            raise ProtocolError('offline_dsh_composition_missing')
        if re.fullmatch(r'sha256:[0-9a-f]{64}',composition_digest) is None:raise ProtocolError('offline_plan_digest_invalid')
        runtime=effective_config['runtime']
        if (not isinstance(runtime,dict) or not isinstance(runtime.get('model'),str) or not runtime['model']
                or not isinstance(runtime.get('options'),dict) or not runtime['options']
                or effective_config['candidate'] != candidate
                or not isinstance(effective_config['bootstrap_digest'],str)
                or re.fullmatch(r'sha256:[0-9a-f]{64}',effective_config['bootstrap_digest']) is None
                or Path(effective_config['dsh_dev_root']).resolve() != (root/'.dsh-dev/candidates'/candidate).resolve()):
            raise ProtocolError('offline_effective_config_invalid')
        parent_namespace=effective_config['qualification_parent_namespace']
        if (not isinstance(parent_namespace,dict) or set(parent_namespace) != {'device','inode'}
                or any(type(parent_namespace[key]) is not int or parent_namespace[key] <= 0 for key in parent_namespace)):
            raise ProtocolError('offline_qualification_namespace_invalid')
        task_root=Path(effective_config['operator_task_root'])
        if (not task_root.is_absolute() or task_root.resolve() != task_root
                or task_root.parent != output_root/'operator'):
            raise ProtocolError('offline_operator_scope_invalid')
        for target in (*DSH_REQUIRED_PYTHON,*DSH_REQUIRED_NODE):
            if not (root/target).is_file():raise ProtocolError('offline_required_test_missing:'+target)
        targets.extend(('tests/integrations/dsh','integrations/dsh/dev/tests'))
    python_files=sorted({file for target in targets for file in _discover(root,target,'test_*.py')})
    report=output_root/'python-report.json'
    suites=[{'suite_id':'python', 'runner':'pytest','cwd':str(root), 'required_targets':targets,
        'discovered_files':python_files,'report_path':str(report),
        'argv':[python_executable,'-m','pytest','-q','-m','not live_llm',
            '-p','code2paper.integrations.dsh.pytest_reporter','--c2p-suite-report',str(report),*targets]}]
    if name in DSH_PLANS:
        node_files=sorted({file for target in ('integrations/dsh/tests','integrations/dsh/dev/toolchain')
            for file in _discover(root,target,'*.test.ts')})
        node_root=output_root/'node'
        node_report=node_root/'node-events.jsonl'
        suites.append({'suite_id':'node','runner':'node','cwd':str(root/'integrations/dsh'),
            'required_targets':list(DSH_REQUIRED_NODE),'discovered_files':node_files,'report_path':str(node_report),
            'argv':[node_executable,'--test','--test-concurrency=1','--test-reporter=spec',
                '--test-reporter='+str(root/'integrations/dsh/dev/toolchain/suite-reporter.mjs'),
                '--test-reporter-destination=stdout','--test-reporter-destination='+str(node_report),
                *[str(root/file) for file in node_files]],
            'launch_argv':[python_executable,str(root/'scripts/dsh_dev.py'),'--candidate',candidate,
                'test','--output-root',str(node_root),'--report-path',str(node_report),*[str(root/file) for file in node_files]]})
    operator=None
    if name in DSH_PLANS:
        core_config={**effective_config,'suite_plan':'dsh-stage04-core'}
        for suite in suites:suite['effective_config']=core_config
        if name == 'dsh-stage04':
            operator_root=output_root/'operator'
            operator_report=operator_root/'node-events.jsonl'
            entry='integrations/dsh/tests/host-provider.test.ts'
            task_root=Path(effective_config['operator_task_root'])
            operator={'task_root':str(task_root),'output_root':str(operator_root),
                'ready_path':str(task_root/'operator-ready.json'),
                'bootstrap_path':str(task_root/'bootstrap.json'),'launch_path':str(task_root/'operator-launch.json'),
                'core_receipt_path':str(task_root/'operator-core-receipt.json'),
                'result_path':str(task_root/'operator-result.json'),'cleanup_path':str(task_root/'cleanup.json'),
                'provider_observations_path':str(task_root/'provider-observations.json'),
                'cli_stdout_path':str(task_root/'operator-cli-output.log'),
                'cli_stderr_path':str(task_root/'operator-cli-error.log'),
                'sentinel_path':str(task_root/'python-sentinel.json'),
                'task_store_path':str(task_root/'run/dsh-tasks.sqlite3'),
                'budget_root':str(task_root/'run/artifacts/06_authoring/invocations')}
            suites.append({'suite_id':'node-cli','runner':'node','cwd':str(root/'integrations/dsh'),
                'required_targets':[entry],'discovered_files':[entry],'report_path':str(operator_report),
                'output_path':str(output_root/'operator-output.log'),'effective_config':core_config,
                'argv':[node_executable,'--test','--test-concurrency=1','--test-reporter=spec',
                    '--test-reporter='+str(root/'integrations/dsh/dev/toolchain/suite-reporter.mjs'),
                    '--test-reporter-destination=stdout','--test-reporter-destination='+str(operator_report),str(root/entry)],
                'launch_argv':[python_executable,str(root/'scripts/dsh_dev.py'),'--candidate',candidate,
                    'test','--operator-package','--qualification-root',str(output_root),
                    '--output-root',str(operator_root),
                    '--report-path',str(operator_report),str(root/entry)]})
    files=sorted({file for suite in suites for file in suite['discovered_files']})
    plan={'schema_version':'OfflineSuitePlanV2','name':name,'version':PLAN_VERSIONS[name],
        'engine_root':str(root),'engine_digest':engine_digest,'validator_digest':validator_digest,
        'composition_digest':composition_digest,'effective_config':effective_config,'candidate':candidate,
        'source_files':{file:digest_bytes((root/file).read_bytes()) for file in files},'suites':suites}
    if operator is not None:plan['operator']=operator
    if core_reuse_path is not None:
        if (name not in DSH_PLANS or not core_reuse_path.is_absolute()
                or core_reuse_path.resolve() != core_reuse_path or not core_reuse_path.is_file()):
            raise ProtocolError('offline_reuse_binding_invalid')
        plan['core_reuse_path']=str(core_reuse_path)
        if operator is not None:
            command=plan['suites'][-1]['launch_argv']
            command[-1:-1]=['--core-reuse-readonly',str(core_reuse_path)]
    return {**plan,'plan_digest':digest_json(plan)}
