"""Reuse passed core behavior after reviewed verification-only changes.

Original reports, identities and failures remain immutable. A reuse manifest
binds them to a source comparison, current focused tests and an independent
review. It never reuses an operator run, grants live permission, or changes a
domain, metering or backend-owner rule.
"""
from __future__ import annotations

from pathlib import Path
import re

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from .offline_admission import read_bound_report, validate_node_report, validate_pytest_report
from .protocol import ProtocolError, strict_json_loads

VERIFICATION_FILES = frozenset({
    'src/code2paper/integrations/dsh/core_reuse.py',
    'src/code2paper/integrations/dsh/runtime_inventory.py',
    'src/code2paper/integrations/dsh/offline_admission.py',
    'src/code2paper/integrations/dsh/operator_suite.py',
    'src/code2paper/integrations/dsh/operator_evidence.py',
    'src/code2paper/integrations/dsh/offline_inputs.py',
    'src/code2paper/integrations/dsh/suite_plan.py',
    'src/code2paper/agentic/authoring_execution_identity.py',
    'scripts/dsh_dev.py',
    'tests/integrations/dsh/test_core_reuse.py',
})


def _raw(binding):
    if not isinstance(binding,dict) or set(binding) != {'path','bytes_digest','byte_length'}:
        raise ProtocolError('offline_reuse_binding_invalid')
    path=Path(binding['path'])
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ProtocolError('offline_reuse_binding_invalid')
    return read_bound_report(path,bytes_digest=binding['bytes_digest'],byte_length=binding['byte_length'])


def _json(binding):
    return strict_json_loads(_raw(binding),max_bytes=32 << 20)


def validate_sequential_node_report(raw: bytes, *, cwd: str | None = None,
        argv: list[str] | None = None, exec_argv: list[str] | None = None) -> dict:
    """Validate each original serial file, retaining imported-test provenance.

    Names repeated in different entry files remain distinct. Duplicates inside
    one file, missing outcomes, skipped tests and inconsistent global totals
    still go through the original strict reader and fail closed.
    """
    rows=[strict_json_loads(line) for line in raw.splitlines()]
    if not rows:raise ProtocolError('offline_node_report_empty')
    meta=rows[0];containers={};groups={};active=None;total=None
    for event in rows[1:]:
        container=(event.get('file') == event.get('name') and event.get('line') == 1
            and event.get('column') == 1 and event.get('nesting') == 0)
        if container and event.get('type') == 'test:enqueue':
            name=event['file']
            if name in containers:raise ProtocolError('offline_node_duplicate')
            containers[name]=event
        elif container and event.get('type') == 'test:dequeue':
            name=event['file']
            if active is not None or name not in containers or name in groups:
                raise ProtocolError('offline_reuse_node_not_serial')
            active=name;groups[name]=[meta,containers[name],event]
        elif event.get('type') == 'test:summary' and event.get('file') is None:
            if active is not None or total is not None:raise ProtocolError('offline_node_summary_invalid')
            total=event['counts']
        else:
            if active is None or total is not None:raise ProtocolError('offline_reuse_node_not_serial')
            groups[active].append(event)
            if event.get('type') == 'test:summary':
                if event.get('file') != active:raise ProtocolError('offline_node_summary_invalid')
                active=None
    if active is not None or set(groups) != set(containers) or not isinstance(total,dict):
        raise ProtocolError('offline_node_coverage_incomplete')
    nodes=[];counts={key:0 for key in ('tests','passed','failed','cancelled','skipped','todo','suites')}
    for entry,events in groups.items():
        result=validate_node_report(b'\n'.join(canonical_json_bytes(row) for row in events),
            cwd=meta['cwd'] if cwd is None else cwd,argv=meta['argv'] if argv is None else argv,
            exec_argv=meta['execArgv'] if exec_argv is None else exec_argv)
        if result['entry_files'] != [entry]:raise ProtocolError('offline_node_entry_coverage_incomplete')
        nodes.extend([[entry,*node] for node in result['node_ids']])
        for key in counts:counts[key]+=result['counts'][key]
    if any(type(total.get(key)) is not int or total[key] != value for key,value in counts.items()):
        raise ProtocolError('offline_node_summary_invalid')
    return {'node_ids':nodes,'counts':counts,'entry_files':sorted(groups)}


def _validate_source_delta(manifest, plan):
    from .suite_runner import _identity
    root=Path(plan['engine_root']);engine,validator=_identity(root)
    review=_json(manifest['review']);old=_json(manifest['source_freeze'])['engine_snapshot']
    original_digest=digest_json({'schema_version':'1.0','commit_sha':old['commit_sha'],'entries':old['entries']})
    if (original_digest != old['source_digest'] or engine.commit_sha != old['commit_sha']
            or review.get('schema_version') != 'OfflineCoreReuseReviewV1'
            or review.get('decision') != 'VERIFICATION_ONLY'
            or review.get('independent') is not True
            or review.get('engine_digest') != engine.source_digest or engine.source_digest != plan['engine_digest']
            or review.get('validator_digest') != validator.digest or validator.digest != plan['validator_digest']):
        raise ProtocolError('offline_reuse_review_or_source_changed')
    before={item['path']:item for item in old['entries']}
    after={item.path:item.as_payload() for item in engine.entries}
    delta={path:{'before':before.get(path),'after':after.get(path)}
        for path in sorted(before.keys()|after.keys()) if before.get(path) != after.get(path)}
    if review.get('changed_files') != delta:raise ProtocolError('offline_reuse_review_scope_changed')
    labels=manifest['test_label_edits']
    if not isinstance(labels,dict):raise ProtocolError('offline_reuse_test_label_invalid')
    for path,change in delta.items():
        if path in VERIFICATION_FILES:continue
        if path.endswith('.md') and path.startswith(('docs/','.agent/')):continue
        if path not in labels or not path.endswith('.test.ts') or '/tests/' not in path:
            raise ProtocolError('offline_reuse_runtime_source_changed')
        edit=labels[path]
        if (set(edit) != {'insertion','offset'} or type(edit['offset']) is not int
                or re.fullmatch(r"\$\{[A-Za-z_$][\w$]* === '[^'\\\n]*' \? '[^'\\\n]*' : ''\}",edit['insertion']) is None):
            raise ProtocolError('offline_reuse_test_label_invalid')
        current=(root/path).read_text();offset=edit['offset'];insertion=edit['insertion']
        if current[offset:offset+len(insertion)] != insertion:
            raise ProtocolError('offline_reuse_test_label_invalid')
        line=current[:offset].rsplit('\n',1)[-1]
        if not line.startswith('test(`') or '`' in line[6:]:
            raise ProtocolError('offline_reuse_test_label_invalid')
        reconstructed=(current[:offset]+current[offset+len(insertion):]).encode()
        if change['before'] is None or digest_bytes(reconstructed) != change['before']['digest']:
            raise ProtocolError('offline_reuse_test_body_changed')
    if set(labels)-set(delta):raise ProtocolError('offline_reuse_test_label_invalid')
    return old


def _validated_manifest(binding, plan):
    manifest=_json(binding)
    keys={'schema_version','source_freeze','core_plan','core_runs','review','test_label_edits','runtime_bootstrap',
        'focused_node_report','verification_report'}
    if not isinstance(manifest,dict) or set(manifest) != keys or manifest['schema_version'] != 'OfflineCoreReuseV1':
        raise ProtocolError('offline_reuse_manifest_invalid')
    old=_validate_source_delta(manifest,plan)
    prior=_json(manifest['core_plan']);runs=_json(manifest['core_runs'])
    if (prior.get('name') != 'dsh-stage04-core' or prior.get('version') != plan['version'].replace('offline','core')
            or digest_json({k:v for k,v in prior.items() if k != 'plan_digest'}) != prior.get('plan_digest')
            or prior['engine_digest'] != old['source_digest'] or prior['candidate'] != plan['candidate']
            or prior['engine_root'] != plan['engine_root'] or [run.get('suite_id') for run in runs] != ['python','node']):
        raise ProtocolError('offline_reuse_original_plan_invalid')
    freeze=_json(manifest['source_freeze'])
    if prior['validator_digest'] != freeze['validator_digest']:
        raise ProtocolError('offline_reuse_original_plan_invalid')
    from .host_admission import _bootstrap_spec
    from code2paper.agentic.authoring_execution_identity import capture_execution_composition
    bootstrap=_json(manifest['runtime_bootstrap']);expected=bootstrap['composition']
    if (expected['composition_digest'] != prior['composition_digest']
            or digest_json({k:v for k,v in expected.items() if k != 'composition_digest'}) != prior['composition_digest']):
        raise ProtocolError('offline_reuse_runtime_changed')
    actual=capture_execution_composition(_bootstrap_spec(bootstrap,Path(plan['engine_root'])),engine_root=plan['engine_root'])
    if any(actual.get(key) != value for key,value in expected.items()
            if key not in {'engine_digest','validator_digest','composition_digest'}):
        raise ProtocolError('offline_reuse_runtime_changed')
    # The original randomized fixture port/task paths need not be repeated;
    # the immutable runtime tree, provider options and meters do.
    for key in ('candidate','dsh_dev_root','marker'):
        if prior['effective_config'][key] != plan['effective_config'][key]:
            raise ProtocolError('offline_reuse_runtime_changed')
    old_runtime=prior['effective_config']['runtime'];new_runtime=plan['effective_config']['runtime']
    for key in old_runtime.keys()|new_runtime.keys():
        if key not in {'backend_resource_key','backend_state_root'} and old_runtime.get(key) != new_runtime.get(key):
            raise ProtocolError('offline_reuse_runtime_changed')
    # All previously covered test bytes remain identical except the proven
    # display-only insertion. Added verification tests are covered separately.
    for path,old_digest in prior['source_files'].items():
        if path not in plan['source_files'] or (path not in manifest['test_label_edits'] and plan['source_files'][path] != old_digest):
            raise ProtocolError('offline_reuse_test_source_changed')
    verification_raw=_raw(manifest['verification_report']);verification=json_meta_pytest(verification_raw)
    verified=validate_pytest_report(verification_raw,cwd=verification['cwd'],argv=verification['argv'])
    added=set(plan['source_files'])-set(prior['source_files'])
    if added-VERIFICATION_FILES or added-{node.split('::',1)[0] for node in verified['selected_node_ids']}:
        raise ProtocolError('offline_reuse_added_tests_not_executed')
    focus_raw=_raw(manifest['focused_node_report']);focus_meta=strict_json_loads(focus_raw.splitlines()[0])
    focus=validate_node_report(focus_raw,cwd=focus_meta['cwd'],argv=focus_meta['argv'],exec_argv=focus_meta['execArgv'])
    if not set(focus['entry_files']).issubset({str(Path(plan['engine_root'])/p) for p in prior['source_files']}):
        raise ProtocolError('offline_reuse_focus_outside_plan')
    if {str(Path(plan['engine_root'])/p) for p in manifest['test_label_edits']}-{node[0] for node in focus['node_ids']}:
        raise ProtocolError('offline_reuse_changed_test_not_executed')
    return manifest,prior,runs,verified


def json_meta_pytest(raw):
    value=strict_json_loads(raw,max_bytes=32 << 20)
    if not isinstance(value,dict):raise ProtocolError('offline_pytest_report_invalid')
    return value


def bind_reused_core(plan: dict, path: Path) -> list[dict]:
    raw=path.read_bytes();binding={'path':str(path),'bytes_digest':digest_bytes(raw),'byte_length':len(raw)}
    _,prior,runs,_=_validated_manifest(binding,plan)
    result=[]
    for suite,original in zip(plan['suites'],runs,strict=True):
        run={key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')}
        run.update(exit_code=0,output_digest=original['output_digest'],evidence_reuse=binding)
        validate_reused_suite(plan,suite,run)
        result.append(run)
    return result


def validate_reused_suite(plan: dict, suite: dict, run: dict, *, _reuse_cache=None) -> dict:
    if (suite['suite_id'] not in {'python','node'} or set(run) != {
            'suite_id','argv','cwd','runner','report_path','exit_code','output_digest','evidence_reuse'}
            or any(run[key] != suite[key] for key in ('suite_id','argv','cwd','runner','report_path'))
            or type(run['exit_code']) is not int or run['exit_code'] != 0):
        raise ProtocolError('offline_reuse_suite_binding_invalid')
    cache={} if _reuse_cache is None else _reuse_cache
    binding=run['evidence_reuse']
    key=(binding['path'],binding['bytes_digest'],binding['byte_length'],plan['engine_digest'],
        plan['validator_digest'],plan['composition_digest'])
    if key not in cache:cache[key]=_validated_manifest(binding,plan)
    _,prior,runs,verified=cache[key]
    index=0 if suite['suite_id'] == 'python' else 1;original=runs[index];old_suite=prior['suites'][index]
    if (original['exit_code'] != 0 or run['output_digest'] != original['output_digest']
            or any(original[key] != old_suite[key] for key in ('suite_id','argv','cwd','runner','report_path'))
            or any(original[key] != prior['engine_digest'] for key in ('engine_before','engine_after'))
            or any(original[key] != prior['validator_digest'] for key in ('validator_before','validator_after'))
            or any(original[key] != prior['composition_digest'] for key in ('composition_before','composition_after'))):
        raise ProtocolError('offline_reuse_original_run_invalid')
    raw=read_bound_report(original['report_path'],bytes_digest=original['report_digest'],byte_length=original['report_bytes'])
    read_bound_report(original['output_path'],bytes_digest=original['output_digest'],byte_length=original['output_bytes'])
    if index == 0:
        result=validate_pytest_report(raw,cwd=original['cwd'],argv=original['argv'])
        nodes=sorted(set(result['selected_node_ids'])|set(verified['selected_node_ids']))
        if set(suite['discovered_files'])-{node.split('::',1)[0] for node in nodes}:
            raise ProtocolError('offline_discovered_file_not_executed')
        return {'passed_count':len(nodes),'node_ids':nodes}
    files=[str(Path(prior['engine_root'])/file) for file in old_suite['discovered_files']]
    result=validate_sequential_node_report(raw,cwd=old_suite['cwd'],argv=[old_suite['argv'][0],*files],
        exec_argv=old_suite['argv'][1:len(old_suite['argv'])-len(files)])
    if result['entry_files'] != sorted(str(Path(plan['engine_root'])/file) for file in suite['discovered_files']):
        raise ProtocolError('offline_node_entry_coverage_incomplete')
    return {'passed_count':result['counts']['tests'],'node_ids':result['node_ids']}


def reuse_readonly_paths(binding: dict) -> list[Path]:
    """Transport closure only; source/report checks remain at consumption."""
    manifest=_json(binding);paths={Path(binding['path'])}
    for key in ('source_freeze','core_plan','core_runs','review','focused_node_report','verification_report','runtime_bootstrap'):
        _raw(manifest[key]);paths.add(Path(manifest[key]['path']))
    for run in _json(manifest['core_runs']):
        paths.update(Path(run[key]) for key in ('report_path','output_path'))
    bootstrap=_json(manifest['runtime_bootstrap'])
    for category in ('files','trees'):
        paths.update(Path(value).resolve() for value in bootstrap['composition_spec'][category].values())
    return sorted(paths,key=str)
