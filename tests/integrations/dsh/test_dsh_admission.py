"""Admission regression: a successful local node cannot imply suite coverage.

This is the first A01 regression, not a DSH admission receipt or full plan proof.
"""
from code2paper.agentic.live_admission_preflight import (
    REQUIRED_OFFLINE_TEST_PLAN, build_offline_suite_receipt,
)


def test_single_pytest_node_never_defaults_to_full_offline_coverage():
    receipt = build_offline_suite_receipt(command='python -m pytest -q tests/example.py::test_one',
        exit_code=0, output='1 passed in 0.10s')
    assert receipt.passed  # only the local command succeeded
    assert receipt.test_plan_ids == ()
    assert receipt.missing_test_plan_ids() == REQUIRED_OFFLINE_TEST_PLAN


def test_failed_and_zero_test_runs_never_generate_passed_receipt():
    for exit_code, output in ((0, 'no tests ran'), (5, 'no tests ran'),
        (1, '1 failed, 1 passed'), (124, 'timeout')):
        assert not build_offline_suite_receipt(command='python -m pytest -q',
            exit_code=exit_code, output=output).passed


import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.integrations.dsh.offline_admission import read_bound_report, validate_pytest_report, validate_node_report
from code2paper.integrations.dsh.protocol import ProtocolError, strict_json_loads

ROOT = Path(__file__).resolve().parents[3]


def test_report_reader_bounds_declared_and_actual_bytes(tmp_path):
    from code2paper.integrations.dsh.offline_admission import MAX_REPORT_BYTES
    report=tmp_path/'report.json'
    report.write_bytes(b'{}')
    for length in (False,0,-1,MAX_REPORT_BYTES+1):
        with pytest.raises(ProtocolError,match='size_invalid'):
            read_bound_report(report,bytes_digest=digest_bytes(b'{}'),byte_length=length)
    # The extra byte proves a longer artifact is rejected even when its prefix
    # has the exact declared digest; no entire-file read is necessary.
    report.write_bytes(b'{} '+b'x'*1024)
    with pytest.raises(ProtocolError,match='bytes_changed'):
        read_bound_report(report,bytes_digest=digest_bytes(b'{}'),byte_length=2)


def test_runner_captures_full_oversized_artifact_without_unbounded_read(tmp_path,monkeypatch):
    from code2paper.integrations.dsh.suite_runner import _artifact_identity
    from code2paper.integrations.dsh.offline_admission import MAX_REPORT_BYTES
    artifact=tmp_path/'large.log'
    with artifact.open('wb') as stream:
        stream.seek(MAX_REPORT_BYTES+7);stream.write(b'end')
    original_open=Path.open
    reads=[]
    class BoundedReader:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def fileno(self):return self.stream.fileno()
        def read(self,size=-1):
            assert 0 < size <= 1 << 20
            reads.append(size)
            return self.stream.read(size)
    def tracked_open(path,*args,**kwargs):
        stream=original_open(path,*args,**kwargs)
        return BoundedReader(stream) if path == artifact and args == ('rb',) else stream
    monkeypatch.setattr(Path,'open',tracked_open)
    sha,length=_artifact_identity(artifact)
    assert length == MAX_REPORT_BYTES+10 and len(reads)>1
    # Original consumer refuses the actual length instead of trusting a prefix.
    with pytest.raises(ProtocolError,match='size_invalid'):
        read_bound_report(artifact,bytes_digest=sha,byte_length=length)
    missing=tmp_path/'missing.json'
    assert _artifact_identity(missing,allow_missing=True) == (digest_bytes(b''),0)
    with pytest.raises(FileNotFoundError):_artifact_identity(missing)


@pytest.mark.parametrize('mutation',[
    {'engine_root':None}, {'composition_spec':[]},
    {'composition_spec':{'files':[],'trees':{},'effective_config':{}}},
    {'composition_spec':{'files':{'stage':42},'trees':{},'effective_config':{}}},
    {'composition_spec':{'files':{'stage':'relative'},'trees':{},'effective_config':{}}},
    {'composition_spec':{'files':{'stage':'/tmp/stage'},'trees':None,'effective_config':{}}},
    {'composition_spec':{'files':{'stage':'/tmp/stage'},'trees':{},'effective_config':[]}},
    {'composition':[]},
])
def test_host_admission_rejects_malformed_nested_composition_without_python_traceback(mutation):
    from code2paper.integrations.dsh.host_admission import _bootstrap_spec
    bootstrap={'engine_root':str(ROOT),'composition':{},'composition_spec':{
        'files':{'stage':'/tmp/stage'},'trees':{},'effective_config':{}}}
    bootstrap.update(mutation)
    with pytest.raises(ProtocolError,match='host_admission_'):_bootstrap_spec(bootstrap,ROOT)


def test_launch_actual_loader_inputs_must_be_frozen_by_original_composition(tmp_path):
    from code2paper.agentic.authoring_execution_identity import CompositionSpecV1
    from code2paper.integrations.dsh.host_admission import _validate_launch_read_set
    config=tmp_path/'config.yml';overlay=tmp_path/'overlay.yml'
    config.write_text('controlled config');overlay.write_text('controlled overlay')
    spec=CompositionSpecV1(files={'config':config,'overlay':overlay},trees={},effective_config={})
    launch={'config_path':str(config),'overlay_paths':[str(overlay)]}
    _validate_launch_read_set(launch,spec)
    for changed in ({'config_path':str(tmp_path/'other-config.yml')},
                    {'overlay_paths':[str(tmp_path/'unfrozen-overlay.yml')]},
                    {'config_path':'relative.yml'}, {'overlay_paths':[str(overlay),None]},
                    {'overlay_paths':{}}, {'config_path':None}):
        with pytest.raises(ProtocolError,match='launch_config_not_frozen|launch_invalid'):
            _validate_launch_read_set({**launch,**changed},spec)


@pytest.mark.parametrize('source,accepted', [
    ('def test_one(): assert True\n', True),
    ('import pytest\n@pytest.mark.skip(reason="required")\ndef test_one(): pass\n', False),
    ('def test_one(): assert False\n', False),
    ('raise RuntimeError("collection failed")\n', False),
    ('# zero tests\n', False),
    ('def test_one(subtests):\n    with subtests.test(msg="passing subtest"): assert True\n', True),
    ('def test_one(subtests):\n    with subtests.test(msg="failed subtest"): assert False\n', False),
])
def test_actual_pytest_machine_report_preserves_bad_and_zero_outcomes(tmp_path, source, accepted):
    (tmp_path/'test_case.py').write_text(source)
    report=tmp_path/'report.json'
    argv=[sys.executable,'-m','pytest','-q','-p','code2paper.integrations.dsh.pytest_reporter',
        '--c2p-suite-report',str(report),'test_case.py']
    result=subprocess.run(argv,cwd=tmp_path,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},
        capture_output=True,timeout=30)
    raw=report.read_bytes()
    if accepted:
        assert result.returncode == 0
        parsed=validate_pytest_report(raw,cwd=str(tmp_path),argv=argv)
        assert parsed['selected_node_ids'] == ['test_case.py::test_one']
        with pytest.raises(ProtocolError,match='runner|report_invalid'):
            validate_pytest_report(raw,cwd=str(tmp_path),argv=[*argv,'--changed'])
        changed=strict_json_loads(raw)
        changed['nodes'][0]['phases'].pop()
        with pytest.raises(ProtocolError,match='phase_not_passed'):
            validate_pytest_report(canonical_json_bytes(changed),cwd=str(tmp_path),argv=argv)
        assert read_bound_report(report,bytes_digest=digest_bytes(raw),byte_length=len(raw)) == raw
        report.write_bytes(raw+b' ')
        with pytest.raises(ProtocolError,match='bytes_changed'):
            read_bound_report(report,bytes_digest=digest_bytes(raw),byte_length=len(raw))
    else:
        with pytest.raises(ProtocolError):validate_pytest_report(raw,cwd=str(tmp_path),argv=argv)


@pytest.mark.parametrize('body,accepted', [
    ("test('one',()=>assert.equal(1,1));", True),
    ("test('one',()=>assert.equal(1,2));", False),
    ("test('one',{skip:true},()=>{});", False),
    ('', False),
])
def test_actual_node_report_refuses_failed_skipped_and_zero_nodes(tmp_path, body, accepted):
    node=shutil.which('node')
    assert node is not None,'A01 Node reporter requires the installed Node runtime'
    test=tmp_path/'case.test.mjs'
    test.write_text("import {test} from 'node:test';\nimport assert from 'node:assert/strict';\n"+body+'\n')
    # Report-reader unit checks use native no-isolation mode to stay inside the
    # outer sandbox. Real DSH suites retain the launcher process isolation.
    command=[node,'--test','--test-isolation=none','--test-reporter',str(ROOT/'integrations/dsh/dev/toolchain/suite-reporter.mjs'),str(test)]
    result=subprocess.run(command,cwd=tmp_path,capture_output=True,timeout=30)
    meta=strict_json_loads(result.stdout.splitlines()[0])
    kwargs={'cwd':str(tmp_path),'argv':meta['argv'],'exec_argv':command[1:-1]}
    if accepted:
        assert result.returncode == 0
        parsed=validate_node_report(result.stdout,**kwargs)
        assert parsed['counts']['tests'] == 1
        with pytest.raises(ProtocolError,match='runner_mismatch'):
            validate_node_report(result.stdout,**{**kwargs,'exec_argv':['--changed']})
        rows=[strict_json_loads(line) for line in result.stdout.splitlines()]
        rows=[row for row in rows if row.get('type') != 'test:pass']
        with pytest.raises(ProtocolError,match='coverage_incomplete'):
            validate_node_report(b'\n'.join(canonical_json_bytes(row) for row in rows),**kwargs)
    else:
        with pytest.raises(ProtocolError):validate_node_report(result.stdout,**kwargs)


from code2paper.integrations.dsh.suite_plan import build_suite_plan, DSH_REQUIRED_PYTHON, DSH_REQUIRED_NODE


def _plan_tree(root):
    for target in REQUIRED_OFFLINE_TEST_PLAN:
        path=root/target
        if path.suffix == '.py':path.parent.mkdir(parents=True,exist_ok=True)
        else:path.mkdir(parents=True,exist_ok=True);path=path/'test_local.py'
        path.write_text('def test_local(): pass\n')


def _plan_options(root,output):
    return {'engine_root':root,'output_root':output,'python_executable':sys.executable,
        'effective_config':{'marker':'not live_llm','suite_plan':'legacy'},'engine_digest':digest_json('unit:engine'),'validator_digest':digest_json('unit:validator')}


def test_versioned_legacy_plan_binds_actual_targets_commands_and_file_bytes(tmp_path):
    root=tmp_path/'engine';root.mkdir();_plan_tree(root)
    options=_plan_options(root,tmp_path/'output')
    plan=build_suite_plan(name='legacy',**options)
    assert plan['version'] == 'legacy-offline/2'
    assert plan['suites'][0]['required_targets'] == list(REQUIRED_OFFLINE_TEST_PLAN)
    assert len(plan['source_files']) == 4
    assert build_suite_plan(name='legacy',**options) == plan
    (root/REQUIRED_OFFLINE_TEST_PLAN[0]/'test_local.py').write_text('def test_local(): assert True\n')
    assert build_suite_plan(name='legacy',**options)['plan_digest'] != plan['plan_digest']
    with pytest.raises(ProtocolError,match='identity_missing'):
        build_suite_plan(name='legacy',**{**options,'effective_config':{}})
    with pytest.raises(ProtocolError,match='credentials'):
        build_suite_plan(name='legacy',**{**options,'effective_config':{'options':{'api_key':'private-example'}}})


def _dsh_plan_options(root, output, *, name='dsh-stage04-core'):
    options={**_plan_options(root,output),'composition_digest':digest_json('unit:composition'),
        'candidate':'unit-candidate','node_executable':str(Path(shutil.which('node')).resolve())}
    options['effective_config']={'marker':'not live_llm','suite_plan':name,'candidate':'unit-candidate',
        'dsh_dev_root':str(root/'.dsh-dev/candidates/unit-candidate'),'bootstrap_digest':digest_json('unit:bootstrap'),
        'runtime':{'model':'unit-model','options':{'provider':'unit'}},
        'qualification_parent_namespace':{'device':1,'inode':2},
        'operator_task_root':str(output/'operator'/'unit-task')}
    return options


def _dsh_plan_tree(root):
    _plan_tree(root)
    for target in (*DSH_REQUIRED_PYTHON,*DSH_REQUIRED_NODE,'integrations/dsh/tests/host-provider.test.ts'):
        path=root/target;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('// UNIT source discovery fixture\n' if path.suffix == '.ts' else '# UNIT source discovery fixture\n')
    (root/'integrations/dsh/dev/tests').mkdir(parents=True)
    (root/'integrations/dsh/dev/tests/test_boundary.py').write_text('# UNIT\n')
    (root/'integrations/dsh/dev/toolchain').mkdir(parents=True)
    (root/'integrations/dsh/dev/toolchain/compile.test.ts').write_text('// UNIT\n')


def test_dsh_core_plan_does_not_backfill_missing_cli_or_required_files(tmp_path):
    root=tmp_path/'engine';root.mkdir();_plan_tree(root)
    options=_dsh_plan_options(root,tmp_path/'output')
    with pytest.raises(ProtocolError,match='required_test_missing'):
        build_suite_plan(name='dsh-stage04-core',**options)
    _dsh_plan_tree(root)
    plan=build_suite_plan(name='dsh-stage04-core',**options)
    assert plan['version'] == 'dsh-stage04-core/12'
    assert len(plan['suites']) == 2 and 'operator' not in plan
    assert plan['suites'][1]['required_targets'] == list(DSH_REQUIRED_NODE)
    assert '--report-path' in plan['suites'][1]['launch_argv']
    assert '--operator-package' not in plan['suites'][1]['launch_argv']
    (root/DSH_REQUIRED_NODE[-1]).unlink()
    with pytest.raises(ProtocolError,match='required_test_missing'):
        build_suite_plan(name='dsh-stage04-core',**options)


def test_final_dsh_plan_registers_actual_executable_operation_and_requires_its_run(tmp_path):
    root=tmp_path/'engine';root.mkdir();_dsh_plan_tree(root)
    output=tmp_path/'output'
    options=_dsh_plan_options(root,output,name='dsh-stage04')
    plan=build_suite_plan(name='dsh-stage04',**options)
    assert plan['version'] == 'dsh-stage04-offline/12'
    assert [suite['suite_id'] for suite in plan['suites']] == ['python','node','node-cli']
    operation=plan['suites'][2]
    assert operation['required_targets'] == ['integrations/dsh/tests/host-provider.test.ts']
    assert operation['discovered_files'] == operation['required_targets']
    assert '--operator-package' in operation['launch_argv']
    qualification_index=operation['launch_argv'].index('--qualification-root')
    assert operation['launch_argv'][qualification_index+1] == str(output)
    assert operation['argv'][-1] == str(root/'integrations/dsh/tests/host-provider.test.ts')
    assert plan['operator']['core_receipt_path'] == str(output/'operator/unit-task/operator-core-receipt.json')
    assert all(suite['effective_config']['suite_plan'] == 'dsh-stage04-core' for suite in plan['suites'])
    # A successful core command or a synthetic passed flag cannot replace the
    # separately registered executable run. This fails before report parsing.
    with pytest.raises(ProtocolError,match='offline_required_suite_missing'):
        verify_suite_reports(plan,[{'suite_id':'python','exit_code':0},{'suite_id':'node','exit_code':0}])
    forged={**plan,'suites':plan['suites'][:2]}
    with pytest.raises(ProtocolError,match='offline_plan_changed_or_forged'):
        verify_suite_reports(forged,[])


@pytest.mark.parametrize('namespace',[None,{}, {'device':True,'inode':2},
    {'device':1,'inode':0},{'device':1,'inode':2,'extra':3}])
def test_dsh_core_plan_rejects_unbound_parent_network_namespace(tmp_path,namespace):
    root=tmp_path/'engine';root.mkdir();_dsh_plan_tree(root)
    options=_dsh_plan_options(root,tmp_path/'output')
    options['effective_config']['qualification_parent_namespace']=namespace
    with pytest.raises(ProtocolError,match='offline_qualification_namespace_invalid'):
        build_suite_plan(name='dsh-stage04-core',**options)


@pytest.mark.parametrize('scope',['relative/task','outside','nested'])
def test_dsh_core_plan_rejects_operator_task_outside_owned_output(tmp_path,scope):
    root=tmp_path/'engine';root.mkdir();_dsh_plan_tree(root)
    output=tmp_path/'output';options=_dsh_plan_options(root,output)
    options['effective_config']['operator_task_root']={
        'relative/task':'relative/task','outside':str(tmp_path/'outside/task'),
        'nested':str(output/'operator/nested/task')}[scope]
    with pytest.raises(ProtocolError,match='offline_operator_scope_invalid'):
        build_suite_plan(name='dsh-stage04-core',**options)


@pytest.mark.parametrize('name,version',[
    ('dsh-stage04-core','dsh-stage04-core/4'),
    ('dsh-stage04','dsh-stage04-offline/2'),
])
def test_normal_host_entry_rejects_core_or_pre_qualification_receipt_before_reading_bootstrap(tmp_path,name,version):
    from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
    from code2paper.integrations.dsh.host_admission import validate_host_admission
    # Deliberately hostile declaration. Even declared success does not authorize
    # the normal entry when the proof scope or version lacks the actual CLI lane.
    receipt=OfflineSuiteReceiptV1(schema_version='2.0',passed=True,exit_code=0,
        machine_plan={'name':name,'version':version,'candidate':'unit-candidate'})
    receipt_path=tmp_path/'receipt.json';receipt_path.write_text(receipt.model_dump_json())
    bootstrap=tmp_path/'missing-bootstrap.json'
    assert not bootstrap.exists()
    with pytest.raises(ProtocolError,match='host_admission_full_dsh_receipt_required'):
        validate_host_admission(bootstrap_path=bootstrap,receipt_path=receipt_path,candidate='unit-candidate')


from code2paper.integrations.dsh.offline_admission import verify_suite_reports


def test_aggregate_recomputes_actual_report_and_rejects_partial_forgery_and_drift(tmp_path):
    root=tmp_path/'engine';root.mkdir();_plan_tree(root)
    (root/'tests/__init__.py').write_text('')
    for name in ('regression_20260917','regression_20260922'):
        (root/'tests'/name/'__init__.py').write_text('')
    output=tmp_path/'output';output.mkdir()
    plan=build_suite_plan(name='legacy',**_plan_options(root,output))
    suite=plan['suites'][0]
    result=subprocess.run(suite['argv'],cwd=root,env={**os.environ,'PYTHONPATH':str(ROOT/'src')},
        capture_output=True,timeout=30)
    assert result.returncode == 0,result.stdout+result.stderr
    report=Path(suite['report_path']);raw=report.read_bytes()
    log=output/'python-output.log';log_raw=result.stdout+b'\n'+result.stderr;log.write_bytes(log_raw)
    run={key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')}
    run.update(report_digest=digest_bytes(raw),report_bytes=len(raw),output_path=str(log),
        output_digest=digest_bytes(log_raw),output_bytes=len(log_raw),exit_code=result.returncode,
        engine_before=plan['engine_digest'],engine_after=plan['engine_digest'],
        validator_before=plan['validator_digest'],validator_after=plan['validator_digest'],
        composition_before=plan['composition_digest'],composition_after=plan['composition_digest'],
        effective_config_digest=digest_json(plan['effective_config']))
    coverage=verify_suite_reports(plan,[run])
    assert coverage['passed_count'] == 4
    assert coverage['test_plan_ids'] == list(REQUIRED_OFFLINE_TEST_PLAN)
    from code2paper.agentic.authoring_execution_identity import EngineSourceSnapshot
    from code2paper.agentic.live_admission_preflight import build_machine_offline_suite_receipt
    snapshot=EngineSourceSnapshot(engine_root=str(root),commit_sha='unit-commit',branch='unit',source_digest=plan['engine_digest'])
    receipt=build_machine_offline_suite_receipt(plan=plan,runs=[run],engine_snapshot=snapshot)
    assert receipt.schema_version == '2.0' and receipt.passed
    assert receipt.matches(snapshot,required_test_plan=REQUIRED_OFFLINE_TEST_PLAN)
    assert not receipt.model_copy(update={'passed_count':1}).matches(snapshot)
    assert not receipt.model_copy(update={'test_plan_digest':digest_json('forged')}).matches(snapshot)
    assert not receipt.model_copy(update={'machine_runs':()}).matches(snapshot)
    partial=build_machine_offline_suite_receipt(plan=plan,runs=[],engine_snapshot=snapshot)
    assert not partial.passed and partial.coverage_failure_code == 'offline_required_suite_missing'
    with pytest.raises(ProtocolError,match='suite_missing'):verify_suite_reports(plan,[])
    for updates in ({'argv':[sys.executable,'-m','pytest','test_one.py']},
        {'engine_after':digest_json('changed')},{'validator_after':digest_json('changed')},
        {'effective_config_digest':digest_json({})},{'exit_code':124}):
        with pytest.raises(ProtocolError,match='binding_invalid'):
            verify_suite_reports(plan,[{**run,**updates}])
    forged={**plan,'suites':[{**suite,'argv':[sys.executable,'-m','pytest','test_one.py']}]}
    with pytest.raises(ProtocolError,match='changed_or_forged'):verify_suite_reports(forged,[run])
    log.write_bytes(log_raw+b'changed')
    with pytest.raises(ProtocolError,match='bytes_changed'):verify_suite_reports(plan,[run])
    log.write_bytes(log_raw)
    (root/REQUIRED_OFFLINE_TEST_PLAN[0]/'test_local.py').write_text('def test_local(): assert True\n')
    with pytest.raises(ProtocolError,match='changed_or_forged'):verify_suite_reports(plan,[run])


def test_original_cli_explicit_single_target_records_partial_scope(tmp_path, capsys):
    from code2paper.cli.agentic_run import method_agent_main
    from code2paper.agentic.live_admission_preflight import read_offline_suite_receipt
    receipt_path=tmp_path/'receipt.json'
    code=method_agent_main(['record-offline-receipt','--out',str(receipt_path),
        '--pytest-target','tests/integrations/dsh/test_dsh_admission.py::test_single_pytest_node_never_defaults_to_full_offline_coverage',
        '--timeout-seconds','30'])
    assert code == 0
    receipt=read_offline_suite_receipt(receipt_path)
    assert receipt.passed_count == 1
    assert receipt.test_plan_ids == () and receipt.machine_plan is None
    assert 'coverage=partial' in capsys.readouterr().out


def test_registered_cli_missing_dsh_input_blocks_before_any_suite(tmp_path, capsys):
    from code2paper.cli.agentic_run import method_agent_main
    receipt=tmp_path/'receipt.json'
    output=tmp_path/'fresh-output'
    code=method_agent_main(['record-offline-receipt','--out',str(receipt),
        '--suite-plan','dsh-stage04','--output-root',str(output)])
    assert code == 2 and not receipt.exists()
    assert 'offline_managed_qualification_arguments_invalid' in capsys.readouterr().err
    assert not (output/'plan.json').exists()


@pytest.mark.parametrize('case',['passed','timeout','source-drift'])
def test_actual_registered_runner_timeout_and_source_drift_cannot_admit(monkeypatch,tmp_path,case):
    from types import SimpleNamespace
    from dataclasses import replace
    from code2paper.agentic.authoring_execution_identity import EngineSourceSnapshot
    from code2paper.agentic.live_admission_preflight import build_machine_offline_suite_receipt
    from code2paper.integrations.dsh import suite_runner
    root=tmp_path/'engine';root.mkdir();_plan_tree(root)
    (root/'tests/__init__.py').write_text('')
    for name in ('regression_20260917','regression_20260922'):
        (root/'tests'/name/'__init__.py').write_text('')
    (root/'src').symlink_to(ROOT/'src',target_is_directory=True)
    if case == 'timeout':
        (root/REQUIRED_OFFLINE_TEST_PLAN[0]/'test_local.py').write_text('import time\ndef test_local(): time.sleep(30)\n')
    output=tmp_path/'output';output.mkdir()
    plan=build_suite_plan(name='legacy',**_plan_options(root,output))
    snapshot=EngineSourceSnapshot(engine_root=str(root),commit_sha='unit-commit',branch='unit',source_digest=plan['engine_digest'])
    changed=replace(snapshot,source_digest=digest_json('unit:source-drift'))
    validator=SimpleNamespace(digest=plan['validator_digest'])
    calls=[]
    def identity(_root):
        calls.append(True)
        return (changed if case == 'source-drift' and len(calls)>1 else snapshot),validator
    # Only the source observer is UNIT-isolated. Popen, pytest, reports,
    # logs, deadline and process-group cleanup are the real production runner.
    monkeypatch.setattr(suite_runner,'_identity',identity)
    runs,final=suite_runner.execute_suite_plan(plan,timeout_seconds=0.1 if case == 'timeout' else 30)
    assert len(runs) == 1
    receipt=build_machine_offline_suite_receipt(plan=plan,runs=runs,engine_snapshot=final)
    if case == 'passed':
        assert runs[0]['exit_code'] == 0 and receipt.passed
        assert receipt.matches(snapshot)
    elif case == 'timeout':
        assert runs[0]['exit_code'] == 124 and not receipt.passed
    else:
        assert runs[0]['exit_code'] == 0 and not receipt.passed
        assert runs[0]['engine_before'] != runs[0]['engine_after']
        assert receipt.coverage_failure_code == 'offline_engine_changed'
