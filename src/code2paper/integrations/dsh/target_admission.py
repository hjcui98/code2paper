"""Original-owner read-only admission of a fresh offline target under full coverage."""
from __future__ import annotations

from pathlib import Path
from code2paper.agentic.authoring_execution_identity import validate_execution_composition
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1, RunInvocationBudgetEnvelopeV1
from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
from .artifacts import ArtifactStore, TaskScope
from .facade import ControlledHostContext, WriterFacade
from .protocol import ProtocolError, parse_model, strict_json_loads
from .task_store import TaskStore, SerialBackendAdmission
from .writer_contract import ArtifactRefV1, WriterWireProjectionV1

STABLE_FILES = frozenset({'loader','peer','bundle_source','bundle_lock','build_input','bundle_js',
    'build_receipt','stage','node','preset','persona','tool_schema','renderer','python_dependencies',
    'worker','python_executable','python_environment','tokenizer','meter','host_profile','host_profile_package','host_profile_patch',
    'host_offline_policy','test_worker_refusal_sentinel'})
LOCAL_FILES = frozenset({'test_worker_launcher','host_config','host_overlay'})
TREES = frozenset({'runtime','dependencies','python_runtime','host_profile_runtime','staged_bundle'})
CONFIG_KEYS = frozenset({'model','options','worker_version','renderer_version','tokenizer_version',
    'meter_version','backend_resource_key','backend_state_root'})


def runtime_authority_projection(bootstrap: dict, launch: dict, candidate: str) -> dict:
    """Project only explicitly enumerated shared authority; reject unknown inputs."""
    composition=bootstrap['composition'];spec=bootstrap['composition_spec']
    if (set(spec['files']) != STABLE_FILES | LOCAL_FILES or set(spec['trees']) != TREES
            or set(spec['effective_config']) != CONFIG_KEYS
            or set(composition['files']) != STABLE_FILES | LOCAL_FILES
            or set(composition['trees']) != TREES or set(composition['effective_config']) != CONFIG_KEYS):
        raise ProtocolError('target_authority_schema_invalid')
    config=spec['effective_config']
    versions={key:config[key] for key in ('worker_version','renderer_version','tokenizer_version','meter_version')}
    return {'schema_version':'Stage04RuntimeAuthorityProjectionV1',
        'engine_digest':composition['engine_digest'],'validator_digest':composition['validator_digest'],
        'candidate':candidate,'dsh_dev_root':str(Path(spec['files']['stage']).parent),
        'stable_files':{key:composition['files'][key] for key in sorted(STABLE_FILES)},
        'trees':composition['trees'],'upstream_source_sha':composition['upstream_source_sha'],
        'versions':versions,'protocol':launch['initialize'],
        'qualified_profile':{'model':config['model'],'options':config['options'],
            'provider_config':launch['provider_config'],'backend_resource_key':config['backend_resource_key']}}



def validate_local_transport(qualified_spec, target_spec, qualified_root: Path, target_root: Path):
    """Validate the three enumerated relocatable files against certified bytes.

    Only the owned sentinel and persistence locations may change. Content and
    command additions do not become authority merely because I01 hashed them.
    """
    from .host_admission import _read
    for spec,owned in ((qualified_spec,qualified_root),(target_spec,target_root)):
        for key in LOCAL_FILES:
            path=spec.files[key]
            if path.resolve() != path or path.is_symlink() or not path.is_relative_to(owned):
                raise ProtocolError('target_local_binding_invalid')
    if _read(target_spec.files['host_config']) != _read(qualified_spec.files['host_config']):
        raise ProtocolError('target_host_config_changed')
    old_launcher=_read(qualified_spec.files['test_worker_launcher'])
    old_sentinel=str(qualified_root/'python-sentinel.json').encode()
    new_sentinel=str(target_root/'python-sentinel.json').encode()
    if old_launcher.count(old_sentinel) != 1 or _read(target_spec.files['test_worker_launcher']) != old_launcher.replace(old_sentinel,new_sentinel):
        raise ProtocolError('target_worker_launcher_changed')
    old_overlay=strict_json_loads(_read(qualified_spec.files['host_overlay']))
    new_overlay=strict_json_loads(_read(target_spec.files['host_overlay']))
    # This is the current certified offline profile's versioned relocation
    # contract, not a recursive arbitrary-key/path filter.
    def relocation(overlay,owned):
        if (not isinstance(overlay,list) or len(overlay) != 2
                or overlay[0] != {'id':'web-runtime','config':{'printUrl':False,'openBrowser':False,
                    'surfaceContext':False,'trustedHosts':[]}}
                or overlay[1] != {'id':'session-persistence-jsonl','config':{
                    'root':str(owned/'sessions'),'compression':'none'}}):
            raise ProtocolError('target_host_overlay_changed')
    relocation(old_overlay,qualified_root);relocation(new_overlay,target_root)


def _launch(bootstrap, spec, current, path):
    from .host_admission import _read, _validate_launch_read_set
    raw=_read(path);binding=bootstrap.get('host_launch_binding')
    if binding != {'schema_version':'DshHostLaunchBindingV1','path':str(path),
            'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}:
        raise ProtocolError('host_admission_launch_changed')
    value=strict_json_loads(raw)
    from .suite_plan import _public_config
    _public_config(value)
    if (not isinstance(value,dict) or set(value) != {'schema_version','config_path','overlay_paths','cwd',
            'scope','run_id','owner','budget_ref','frozen_ref','projection_ref','input','projection','initialize','provider_config'}
            or value['schema_version'] != 'DshSingleWriterLaunchV1' or value['scope'] != bootstrap['scope']
            or value['input'].get('composition_digest') != current['composition_digest']
            or value['projection'].get('composition_digest') != current['composition_digest']):
        raise ProtocolError('host_admission_launch_invalid')
    _validate_launch_read_set(value,spec)
    return value,raw


def validate_target_admission(*, bootstrap_path: Path, receipt_path: Path, candidate: str,
        parallel_agents: bool=False, launch_path: Path | None=None):
    from .host_admission import _read, _bootstrap_spec, _validate_admission
    if type(parallel_agents) is not bool:raise ProtocolError('execution_parallel_flag_invalid')
    if parallel_agents:raise ProtocolError('parallel_execution_unsupported')
    if any(not path.is_absolute() or path.resolve() != path or path.is_symlink()
            for path in (bootstrap_path,receipt_path)):
        raise ProtocolError('target_path_invalid')
    root=Path(__file__).resolve().parents[4]
    receipt_raw=_read(receipt_path)
    receipt=OfflineSuiteReceiptV1.model_validate(strict_json_loads(receipt_raw,max_bytes=32 << 20))
    plan=receipt.machine_plan
    from .suite_plan import PLAN_VERSIONS
    if (receipt.schema_version != '2.0' or not receipt.passed or receipt.exit_code != 0
            or not isinstance(plan,dict) or plan.get('name') != 'dsh-stage04'
            or plan.get('version') != PLAN_VERSIONS['dsh-stage04']
            or plan.get('candidate') != candidate or not isinstance(plan.get('operator'),dict)):
        raise ProtocolError('host_admission_full_dsh_receipt_required')
    if launch_path is None:raise ProtocolError('host_admission_launch_binding_required')
    if not launch_path.is_absolute() or launch_path.resolve() != launch_path or launch_path.is_symlink():
        raise ProtocolError('target_path_invalid')
    operator=plan['operator']
    qualified_bootstrap_path=Path(operator['bootstrap_path']);qualified_launch_path=Path(operator['launch_path'])
    # Full original certificate, reports, execution proof and exact qualified I01.
    coverage=_validate_admission(bootstrap_path=qualified_bootstrap_path,receipt_path=receipt_path,
        candidate=candidate,parallel_agents=False,launch_path=qualified_launch_path)
    qualified_raw=_read(qualified_bootstrap_path);qualified=strict_json_loads(qualified_raw,max_bytes=32 << 20)
    qualified_spec=_bootstrap_spec(qualified,root)
    qualified_current=validate_execution_composition(qualified_spec,qualified['composition'],engine_root=root)
    qualified_launch,qualified_launch_raw=_launch(qualified,qualified_spec,qualified_current,qualified_launch_path)
    bootstrap_raw=_read(bootstrap_path);bootstrap=strict_json_loads(bootstrap_raw,max_bytes=32 << 20)
    if (not isinstance(bootstrap,dict) or set(bootstrap) != {'artifact_root','engine_root','scope','context',
            'composition_spec','composition','meter','host_launch_binding'}
            or not isinstance(bootstrap.get('scope'),dict)
            or set(bootstrap['scope']) != {'execution_id','task_id','task_epoch'}
            or any(not isinstance(bootstrap['scope'][key],str) or not bootstrap['scope'][key]
                   for key in ('execution_id','task_id'))
            or type(bootstrap['scope']['task_epoch']) is not int
            or not 0 <= bootstrap['scope']['task_epoch'] <= (1 << 53)-1):
        raise ProtocolError('target_bootstrap_schema_invalid')
    spec=_bootstrap_spec(bootstrap,root)
    current=validate_execution_composition(spec,bootstrap['composition'],engine_root=root)
    launch,launch_raw=_launch(bootstrap,spec,current,launch_path)
    shared=runtime_authority_projection(qualified,qualified_launch,candidate)
    if runtime_authority_projection(bootstrap,launch,candidate) != shared:
        raise ProtocolError('target_runtime_authority_mismatch')
    task_root=bootstrap_path.parent;run_root=task_root/'run';backend_root=task_root/'backend'
    if (launch['cwd'] != str(task_root) or any(not isinstance(launch[key],str) or not launch[key]
            for key in ('owner','run_id')) or bootstrap.get('artifact_root') != str(run_root)
            or spec.effective_config['backend_state_root'] != str(backend_root)
            or any(path.resolve() != path for path in (task_root,run_root,backend_root))
            or bootstrap['scope']['execution_id'] == qualified['scope']['execution_id']):
        raise ProtocolError('target_fresh_scope_required')
    if (spec.files['host_config'] != Path(launch['config_path'])
            or launch['overlay_paths'] != [str(spec.files['host_overlay'])]
            or not all(path.resolve().is_relative_to(task_root) for path in
                (spec.files[key] for key in LOCAL_FILES))):
        raise ProtocolError('target_local_binding_invalid')
    validate_local_transport(qualified_spec,spec,qualified_bootstrap_path.parent,task_root)
    if bootstrap.get('meter') != qualified.get('meter'):raise ProtocolError('target_meter_configuration_changed')
    from .qualification import assert_offline_qualification_namespace,assert_frozen_loopback_provider
    namespace=assert_offline_qualification_namespace(plan['effective_config']['qualification_parent_namespace'])
    assert_frozen_loopback_provider(launch)
    scope=TaskScope(**bootstrap['scope'])
    store=ArtifactStore.open_readonly(run_root,scope)
    tasks=TaskStore.observe_initial(run_root,scope)
    backend,binding=SerialBackendAdmission.observe_initial(backend_root,spec.effective_config['backend_resource_key'],
        execution_id=scope.execution_id,run_root=run_root)
    context=ControlledHostContext(scope=scope,**bootstrap['context'])
    if context.claim_mode != 'dsh-durable-claim/1':raise ProtocolError('durable_claim_required')
    from code2paper.agentic.unified_context_compiler import measure_unified_tokens
    from code2paper.agentic.unified_context_models import UnifiedTokenMeterV1
    if bootstrap['meter'].get('kind') == 'controlled-utf8-byte-id/1':
        from .local_meter import bind_controlled_meter
        meter=bind_controlled_meter(spec.effective_config)
    else:
        meter_model=UnifiedTokenMeterV1.model_validate(bootstrap['meter'])
        if meter_model.method != 'conservative_utf8_bytes_div_4':raise ProtocolError('local_tokenizer_unavailable')
        meter=lambda wire:measure_unified_tokens(wire.decode('utf-8'),meter=meter_model)
    facade=WriterFacade(store=store,context=context,composition_spec=spec,composition=current,
        engine_root=root,request_meter=meter,task_store=tasks,backend_admission=backend)
    def ref(key):return parse_model(canonical_json_bytes(launch[key]),ArtifactRefV1)
    frozen_ref=ref('frozen_ref');projection_ref=ref('projection_ref');budget_ref=ref('budget_ref')
    frozen=facade.check_frozen_current(frozen_ref)
    expected_input=facade.render_input(frozen_ref,cap=launch['input']['post_clamp_max_output_tokens'])
    if expected_input.model_dump(mode='json') != launch['input']:
        raise ProtocolError('target_input_rebuild_mismatch')
    projection=parse_model(canonical_json_bytes(store.read_json(projection_ref)),WriterWireProjectionV1)
    if projection.model_dump(mode='json') != launch['projection']:
        raise ProtocolError('target_projection_binding_mismatch')
    facade._verify_projection(expected_input,projection)
    envelope=RunInvocationBudgetEnvelopeV1.model_validate(store.read_json(budget_ref))
    invocation_plan=ConsumerInvocationPlanV1.model_validate(store.read_json(
        parse_model(canonical_json_bytes(frozen['refs']['plan']),ArtifactRefV1)))
    if (envelope.content_digest != invocation_plan.envelope_digest
            or envelope.profile_digest != invocation_plan.profile_digest
            or envelope.model_identity_digest != invocation_plan.model_identity_digest
            or envelope.profile_digest != frozen['identity']['profile_digest']
            or envelope.model_identity_digest != frozen['identity']['model_digest']
            or envelope.run_digest != digest_json(scope.execution_id)):
        raise ProtocolError('dsh_budget_envelope_binding_mismatch')
    budget_root=run_root/'artifacts/06_authoring/invocations'
    initial=read_run_budget_state(budget_root)
    def initial_budget(value):
        return (value.get('status') == 'pass' and value.get('failure_codes') == []
            and value.get('provider_usage_status') == 'validated'
            and value.get('provider_usage_missing_receipts') == []
            and all(type(value.get(key)) is int and value[key] == 0 for key in
                ('call_count','completed_call_count','pending_call_count','spent_input_tokens',
                 'pending_input_tokens','provider_usage_missing_call_count','provider_usage_missing_input_tokens')))
    if not initial_budget(initial):raise ProtocolError('target_budget_not_initial')
    # Reconsume all original immutable closure and both I01 identities after
    # reading proof dependencies. No directory, task, reservation or lease is made.
    facade.render_input(frozen_ref,cap=expected_input.post_clamp_max_output_tokens)
    facade._verify_projection(expected_input,projection)
    store.read_json(budget_ref)
    TaskStore.observe_initial(run_root,scope)
    _,binding_after=SerialBackendAdmission.observe_initial(backend_root,spec.effective_config['backend_resource_key'],
        execution_id=scope.execution_id,run_root=run_root)
    if binding_after != binding or read_run_budget_state(budget_root) != initial:
        raise ProtocolError('target_initial_state_changed')
    for path,raw in ((bootstrap_path,bootstrap_raw),(launch_path,launch_raw),(receipt_path,receipt_raw),
            (qualified_bootstrap_path,qualified_raw),(qualified_launch_path,qualified_launch_raw)):
        if _read(path) != raw:raise ProtocolError('host_admission_inputs_changed')
    validate_execution_composition(qualified_spec,qualified['composition'],engine_root=root)
    validate_execution_composition(spec,bootstrap['composition'],engine_root=root)
    # Recheck original full proof (including reports and operation evidence).
    again=_validate_admission(bootstrap_path=qualified_bootstrap_path,receipt_path=receipt_path,
        candidate=candidate,parallel_agents=False,launch_path=qualified_launch_path)
    if again != coverage:raise ProtocolError('host_admission_inputs_changed')
    return {'schema_version':'DshTargetAdmissionV1','admitted':True,'scope':'dsh-stage04-offline',
        'qualification_only':False,'normal_entry_authorized':True,'model_execution_authorized':False,
        'parallel_agents':False,'candidate':candidate,'engine_digest':current['engine_digest'],
        'validator_digest':current['validator_digest'],'composition_digest':current['composition_digest'],
        'effective_config_digest':digest_json(spec.effective_config),'bootstrap_digest':digest_bytes(bootstrap_raw),
        'launch_digest':digest_bytes(launch_raw),'receipt_digest':digest_bytes(receipt_raw),
        'coverage_receipt_digest':digest_bytes(receipt_raw),'runtime_authority_digest':digest_json(shared),
        'target_scope':bootstrap['scope'],'domain_read_set_digest':digest_json(frozen['refs']),
        'model_config_digest':digest_json(shared['qualified_profile']),'backend_binding_digest':digest_json(binding),
        'network_namespace':namespace}
