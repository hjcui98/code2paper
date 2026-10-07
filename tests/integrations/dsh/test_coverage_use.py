"""UNIT rejection contracts; these fixtures never prove complete coverage or use."""
from copy import deepcopy
import sqlite3

import pytest

from code2paper.agentic.digest import digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from code2paper.integrations.dsh import coverage_use
from code2paper.integrations.dsh.protocol import ProtocolError
from .test_host_recovery_boundaries import recovery_kernel,_completed_finish
from .test_composition_identity import composition


def test_unit_finished_backend_requires_exact_original_retirement_not_held_or_missing_history(recovery_kernel,tmp_path):
    facade,quiescence=_completed_finish(recovery_kernel)
    backend=facade.backend_admission
    params={'task_root':tmp_path,'scope':facade.store.scope.__dict__,'resource_key':backend.resource_key,
            'backend_binding_digest':digest_json({'state':'empty','owner':None})}
    with pytest.raises(ProtocolError,match='coverage_use_original_binding_changed'):
        coverage_use.verify_finished_backend(**params)
    receipt=backend.release_observed_finish(run_root=facade.store.root,scope=facade.store.scope,quiescence_ref=quiescence)
    assert coverage_use.verify_finished_backend(**params)==receipt
    with pytest.raises(ProtocolError,match='coverage_use_original_binding_changed'):
        coverage_use.verify_finished_backend(**{**params,'backend_binding_digest':digest_json('UNIT unrelated permit')})
    with sqlite3.connect(backend.path) as db:db.execute('DELETE FROM release_history')
    with pytest.raises(ProtocolError,match='coverage_use_backend_retirement_unproven'):
        coverage_use.verify_finished_backend(**params)
    assert backend.read_persisted(backend.root,backend.resource_key)['state']=='empty'


@pytest.mark.parametrize('machine_plan',[None,{}, {'name':'legacy'}, {'name':'dsh-stage04-partial'}])
def test_non_full_plan_rejected_before_any_artifact_read(tmp_path,monkeypatch,machine_plan):
    def unexpected_read(*args,**kwargs):
        pytest.fail('non-full certificate must fail before artifact reads')
    monkeypatch.setattr(coverage_use,'_read',unexpected_read)
    certificate=OfflineSuiteReceiptV1(machine_plan=machine_plan)
    assert certificate.passed is False
    with pytest.raises(ProtocolError,match='coverage_use_full_certificate_required'):
        coverage_use.build_coverage_use_plan(certificate_path=tmp_path/'missing.json',certificate=certificate,
            output_root=tmp_path/'out',task_root=tmp_path/'out/stage04-provider-unit',
            python_executable='/unit/python')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('timeout',[0,-1,float('nan'),float('inf'),float('-inf'),True,False,None,'1'])
def test_invalid_timeout_rejected_before_read_or_spawn(tmp_path,monkeypatch,timeout):
    def unexpected_operation(*args,**kwargs):
        pytest.fail('invalid timeout must not read or start a child')
    monkeypatch.setattr(coverage_use,'_read',unexpected_operation)
    monkeypatch.setattr(coverage_use.subprocess,'Popen',unexpected_operation)
    with pytest.raises(ProtocolError,match='coverage_use_timeout_invalid'):
        coverage_use.execute_coverage_use(certificate_path=tmp_path/'missing.json',
            output_root=tmp_path/'out',python_executable='/unit/python',timeout_seconds=timeout)
    assert list(tmp_path.iterdir()) == []


def permit_inputs():
    """Syntactic UNIT records only: no native reports, files or usable certificate."""
    scope={'execution_id':'unit-execution','run_id':'unit-run','task_id':'unit-task','epoch':1}
    certificate_digest=digest_json('UNIT certificate bytes, never a full certificate')
    plan={'certificate_path':'/unit/certificate.json','certificate_digest':certificate_digest,
        'candidate':'unit-candidate','engine_digest':digest_json('unit engine'),
        'validator_digest':digest_json('unit validator')}
    permit={'schema_version':'DshTargetAdmissionV1','admitted':True,'scope':'dsh-stage04-offline',
        'qualification_only':False,'normal_entry_authorized':True,'model_execution_authorized':False,
        'parallel_agents':False,'candidate':plan['candidate'],'engine_digest':plan['engine_digest'],
        'validator_digest':plan['validator_digest'],'composition_digest':digest_json('unit composition'),
        'effective_config_digest':digest_json('unit configuration'),'bootstrap_digest':digest_json('unit bootstrap'),
        'launch_digest':digest_json('unit launch'),'receipt_digest':certificate_digest,
        'coverage_receipt_digest':certificate_digest,'runtime_authority_digest':digest_json('unit runtime'),
        'target_scope':scope,'domain_read_set_digest':digest_json('unit domain'),
        'model_config_digest':digest_json('unit model'),'backend_binding_digest':digest_json('unit backend'),
        'network_namespace':{'device':1,'inode':2}}
    operation={'schema_version':'DshHostExecutionResultV1','admission':permit,
        'admission_completed_ms':1,'receipt':{'unit':'not a domain receipt'}}
    result={'normal_cli_result':deepcopy(operation),'target_admission':deepcopy(permit),
        'admission_scope':permit['scope'],'coverage_receipt':plan['certificate_path']}
    return plan,result,operation


def test_permit_syntax_contract_is_not_a_coverage_certificate():
    plan,result,operation=permit_inputs()
    assert coverage_use._validate_target_permit(plan,result,operation) is operation['admission']
    assert 'machine_plan' not in plan
    assert 'machine_runs' not in plan
    assert 'passed' not in plan


@pytest.mark.parametrize('key',sorted(coverage_use.TARGET_PERMIT_KEYS))
def test_every_permit_key_is_required(key):
    plan,result,operation=permit_inputs()
    operation['admission'].pop(key)
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('key',['schema_version','admission','admission_completed_ms','receipt'])
def test_every_wrapper_key_is_required(key):
    plan,result,operation=permit_inputs()
    operation.pop(key)
    result['normal_cli_result']=deepcopy(operation)
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('key', ['admitted','normal_entry_authorized','qualification_only',
    'model_execution_authorized','parallel_agents'])
@pytest.mark.parametrize('replacement',[None,0,1,'true','false'])
def test_boolean_flags_require_exact_boolean_types(key,replacement):
    plan,result,operation=permit_inputs()
    operation['admission'][key]=replacement
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('key',['admitted','normal_entry_authorized','qualification_only',
    'model_execution_authorized','parallel_agents'])
def test_opposite_boolean_flag_rejected(key):
    plan,result,operation=permit_inputs()
    operation['admission'][key]=not operation['admission'][key]
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('where',['wrapper','permit'])
@pytest.mark.parametrize('mutation',['missing','extra'])
def test_wrapper_and_permit_exact_schema_keys(where,mutation):
    plan,result,operation=permit_inputs()
    value=operation if where == 'wrapper' else operation['admission']
    if mutation == 'missing':value.pop('schema_version')
    else:value['unregistered_authority']=True
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('where',['wrapper','permit'])
def test_wrong_schema_version_rejected(where):
    plan,result,operation=permit_inputs()
    value=operation if where == 'wrapper' else operation['admission']
    value['schema_version']='unregistered-v2'
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('key',['receipt_digest','coverage_receipt_digest'])
@pytest.mark.parametrize('replacement',['', 'sha256:wrong', digest_json('different certificate')])
def test_certificate_digest_binding_cannot_change(key,replacement):
    plan,result,operation=permit_inputs()
    operation['admission'][key]=replacement
    result['normal_cli_result']=deepcopy(operation)
    result['target_admission']=deepcopy(operation['admission'])
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)


@pytest.mark.parametrize('mutation',['wrapper_copy','permit_copy','scope','result_scope','certificate_path'])
def test_result_copies_and_scope_bind_exactly(mutation):
    plan,result,operation=permit_inputs()
    if mutation == 'wrapper_copy':result['normal_cli_result']['admission_completed_ms']=2
    elif mutation == 'permit_copy':result['target_admission']['target_scope']['execution_id']='different'
    elif mutation == 'scope':
        operation['admission']['scope']='dsh-stage04-qualification'
        result['normal_cli_result']=deepcopy(operation)
        result['target_admission']=deepcopy(operation['admission'])
        result['admission_scope']=operation['admission']['scope']
    elif mutation == 'result_scope':result['admission_scope']='different'
    else:result['coverage_receipt']='/unit/different-certificate.json'
    with pytest.raises(ProtocolError,match='coverage_use_target_permit_invalid'):
        coverage_use._validate_target_permit(plan,result,operation)
