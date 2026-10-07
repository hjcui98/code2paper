"""Read-only Stage A Host admission over original composition and reports.

This establishes offline coverage only. It is neither a model permit nor live
authorization; dispatch still belongs to the original worker and adapter seam.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from code2paper.agentic.authoring_execution_identity import (
    CompositionSpecV1, capture_engine_source_snapshot,
    capture_validator_bundle_snapshot, validate_execution_composition,
)
from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from .protocol import ProtocolError, strict_json_loads

MAX_ADMISSION_BYTES = 32 << 20


def _read(path: Path) -> bytes:
    with path.open('rb') as stream:
        raw=stream.read(MAX_ADMISSION_BYTES+1)
    if not raw or len(raw)>MAX_ADMISSION_BYTES:
        raise ProtocolError('host_admission_artifact_size_invalid')
    return raw


def _bootstrap_spec(bootstrap: object, root: Path) -> CompositionSpecV1:
    if (not isinstance(bootstrap,dict) or not isinstance(bootstrap.get('engine_root'),str)
            or Path(bootstrap['engine_root']).resolve() != root):
        raise ProtocolError('host_admission_engine_mismatch')
    values=bootstrap.get('composition_spec')
    if (not isinstance(values,dict) or not {'files','trees','effective_config'}.issubset(values)
            or set(values)-{'files','trees','effective_config','upstream_source_sha'}
            or not isinstance(values['effective_config'],dict)
            or not isinstance(bootstrap.get('composition'),dict)):
        raise ProtocolError('host_admission_composition_invalid')
    for key in ('files','trees'):
        paths=values[key]
        if (not isinstance(paths,dict) or any(not isinstance(name,str) or not name
                or not isinstance(value,str) or not value or not Path(value).is_absolute()
                for name,value in paths.items())):
            raise ProtocolError('host_admission_composition_invalid')
    if 'stage' not in values['files']:
        raise ProtocolError('host_admission_candidate_mismatch')
    if values.get('upstream_source_sha') is not None and not isinstance(values['upstream_source_sha'],str):
        raise ProtocolError('host_admission_composition_invalid')
    return CompositionSpecV1(files={key:Path(value) for key,value in values['files'].items()},
        trees={key:Path(value) for key,value in values['trees'].items()},effective_config=values['effective_config'],
        upstream_source_sha=values.get('upstream_source_sha'))


def _validate_launch_read_set(launch: dict, spec: CompositionSpecV1) -> None:
    config=launch.get('config_path');overlays=launch.get('overlay_paths')
    if (not isinstance(config,str) or not config or not isinstance(overlays,list)
            or any(not isinstance(value,str) or not value for value in overlays)):
        raise ProtocolError('host_admission_launch_invalid')
    frozen_paths={str(value) for value in spec.files.values()}
    for value in [config,*overlays]:
        if not Path(value).is_absolute() or value not in frozen_paths:
            raise ProtocolError('host_admission_launch_config_not_frozen')


def _validate_admission(*, bootstrap_path: Path, receipt_path: Path,
                            candidate: str, parallel_agents: bool = False,
                            launch_path: Path | None = None, qualification_only: bool = False) -> dict:
    if type(parallel_agents) is not bool:raise ProtocolError('execution_parallel_flag_invalid')
    if parallel_agents:raise ProtocolError('parallel_execution_unsupported')
    if not candidate or Path(candidate).name != candidate or candidate in {'.','..'}:
        raise ProtocolError('host_admission_candidate_invalid')
    root=Path(__file__).resolve().parents[4]
    receipt_raw=_read(receipt_path)
    receipt=OfflineSuiteReceiptV1.model_validate(strict_json_loads(receipt_raw,max_bytes=MAX_ADMISSION_BYTES))
    plan=receipt.machine_plan
    from .suite_plan import PLAN_VERSIONS
    expected_plan='dsh-stage04-core' if qualification_only else 'dsh-stage04'
    if qualification_only and launch_path is None:raise ProtocolError('qualification_launch_required')
    if (receipt.schema_version != '2.0' or not receipt.passed or receipt.exit_code != 0
            or not isinstance(plan,dict) or plan.get('name') != expected_plan
            or plan.get('version') != PLAN_VERSIONS[expected_plan] or plan.get('candidate') != candidate):
        raise ProtocolError('host_admission_full_dsh_receipt_required')
    bootstrap_raw=_read(bootstrap_path)
    bootstrap=strict_json_loads(bootstrap_raw,max_bytes=MAX_ADMISSION_BYTES)
    spec=_bootstrap_spec(bootstrap,root)
    current=validate_execution_composition(spec,bootstrap['composition'],engine_root=root)
    dev_root=(root/'.dsh-dev/candidates'/candidate).resolve()
    if spec.files['stage'].resolve() != dev_root/'staging.json':
        raise ProtocolError('host_admission_candidate_mismatch')
    stage=strict_json_loads(_read(spec.files['stage']),max_bytes=MAX_ADMISSION_BYTES)
    if (not isinstance(stage,dict) or stage.get('candidate') != candidate
            or not isinstance(stage.get('dev_root'),str) or Path(stage['dev_root']).resolve() != dev_root):
        raise ProtocolError('host_admission_candidate_mismatch')
    if plan.get('composition_digest') != current['composition_digest']:
        raise ProtocolError('host_admission_composition_mismatch')
    launch_digest=''
    launch_raw=None
    if launch_path is not None:
        binding=bootstrap.get('host_launch_binding')
        if (not isinstance(binding,dict) or set(binding) != {'schema_version','path','bytes_digest','byte_length'}
                or binding['schema_version'] != 'DshHostLaunchBindingV1'
                or not launch_path.is_absolute() or launch_path.resolve() != launch_path
                or binding['path'] != str(launch_path)):
            raise ProtocolError('host_admission_launch_binding_required')
        launch_raw=_read(launch_path)
        launch_digest=digest_bytes(launch_raw)
        if (type(binding['byte_length']) is not int or binding['byte_length'] != len(launch_raw)
                or binding['bytes_digest'] != launch_digest):
            raise ProtocolError('host_admission_launch_changed')
        from .suite_plan import _public_config
        launch=strict_json_loads(launch_raw)
        _public_config(launch)
        if (not isinstance(launch,dict) or set(launch) != {'schema_version','config_path','overlay_paths','cwd',
                'scope','run_id','owner','budget_ref','frozen_ref','projection_ref','input','projection','initialize','provider_config'}
                or launch['schema_version'] != 'DshSingleWriterLaunchV1'
                or launch['scope'] != bootstrap['scope']
                or not isinstance(launch['input'],dict) or not isinstance(launch['projection'],dict)
                or launch['input'].get('composition_digest') != current['composition_digest']
                or launch['projection'].get('composition_digest') != current['composition_digest']):
            raise ProtocolError('host_admission_launch_invalid')
        _validate_launch_read_set(launch,spec)
    config={'marker':'not live_llm','suite_plan':expected_plan,'runtime':spec.effective_config,
        'bootstrap_digest':digest_bytes(bootstrap_raw),'candidate':candidate,'dsh_dev_root':str(dev_root),
        'qualification_parent_namespace':plan.get('effective_config',{}).get('qualification_parent_namespace'),
        'operator_task_root':str(bootstrap_path.parent)}
    if plan.get('effective_config') != config:
        raise ProtocolError('host_admission_effective_config_mismatch')
    engine=capture_engine_source_snapshot(root);validator=capture_validator_bundle_snapshot(root)
    if (not engine.is_usable or engine.unstable or not validator.is_usable
            or not receipt.matches(engine,validator_bundle_digest=validator.digest,
                effective_config_digest=digest_json(config))):
        raise ProtocolError('host_admission_receipt_stale_or_incomplete')
    # Recheck the operator inputs and runtime after reading all report/log
    # dependencies. This does not replace the seam's send-time revalidation.
    if _read(bootstrap_path) != bootstrap_raw or _read(receipt_path) != receipt_raw:
        raise ProtocolError('host_admission_inputs_changed')
    if launch_path is not None and _read(launch_path) != launch_raw:
        raise ProtocolError('host_admission_launch_changed')
    validate_execution_composition(spec,bootstrap['composition'],engine_root=root)
    namespace=None
    if qualification_only:
        from .qualification import assert_offline_qualification_namespace,assert_frozen_loopback_provider
        namespace=assert_offline_qualification_namespace(config['qualification_parent_namespace'])
        assert_frozen_loopback_provider(launch)
    result={'schema_version':'DshHostAdmissionV1','admitted':True,
        'scope':'dsh-stage04-qualification' if qualification_only else 'dsh-stage04-offline',
        'model_execution_authorized':False,'candidate':candidate,'engine_digest':engine.source_digest,
        'validator_digest':validator.digest,'composition_digest':current['composition_digest'],
        'effective_config_digest':digest_json(config),'bootstrap_digest':digest_bytes(bootstrap_raw),
        'receipt_digest':digest_bytes(receipt_raw),'parallel_agents':False,'launch_digest':launch_digest}
    if qualification_only:
        result.update(qualification_only=True,normal_entry_authorized=False,network_namespace=namespace)
    return result


def validate_host_admission(*, bootstrap_path: Path, receipt_path: Path, candidate: str,
        parallel_agents: bool = False, launch_path: Path | None = None) -> dict:
    # A complete coverage certificate and fresh target binding are both required.
    from .target_admission import validate_target_admission
    return validate_target_admission(bootstrap_path=bootstrap_path,receipt_path=receipt_path,candidate=candidate,
        parallel_agents=parallel_agents,launch_path=launch_path)


def validate_qualification_admission(*, bootstrap_path: Path, receipt_path: Path, candidate: str,
        parallel_agents: bool = False, launch_path: Path | None = None) -> dict:
    # This separate operation requires actual OS isolation and a complete core
    # certificate; it never authorizes the normal entry or an external model.
    return _validate_admission(bootstrap_path=bootstrap_path,receipt_path=receipt_path,candidate=candidate,
        parallel_agents=parallel_agents,launch_path=launch_path,qualification_only=True)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap',type=Path,required=True)
    parser.add_argument('--offline-receipt',type=Path,required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--parallel-agents',choices=('false','true'),default='false')
    parser.add_argument('--launch-file',type=Path)
    parser.add_argument('--qualification-core',action='store_true')
    args=parser.parse_args(argv)
    try:
        validate=validate_qualification_admission if args.qualification_core else validate_host_admission
        result=validate(bootstrap_path=args.bootstrap,receipt_path=args.offline_receipt,
            candidate=args.candidate,parallel_agents=args.parallel_agents == 'true',launch_path=args.launch_file)
    except (ProtocolError,OSError,ValueError,KeyError,TypeError) as error:
        # Never echo bootstrap values, provider configuration or credentials.
        result={'schema_version':'DshHostAdmissionV1','admitted':False,
            'reason':error.code if isinstance(error,ProtocolError) else 'host_admission_unavailable_or_invalid'}
        print(canonical_json_bytes(result).decode())
        return 2
    print(canonical_json_bytes(result).decode())
    return 0


if __name__ == '__main__':raise SystemExit(main())
