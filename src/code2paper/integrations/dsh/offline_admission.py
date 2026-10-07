"""Offline machine-report validation. No model, budget, or publication authority.

The original preflight/CLI will own versioned plans and aggregate admission.
These readers preserve discovered/selected nodes and reject missing outcomes;
summary counts or caller-supplied labels cannot establish coverage.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from code2paper.agentic.digest import digest_bytes
from .protocol import ProtocolError, strict_json_loads


MAX_REPORT_BYTES = 32 * 1024 * 1024


def read_bound_report(path: str | Path, *, bytes_digest: str, byte_length: int) -> bytes:
    if type(byte_length) is not int or not 0 < byte_length <= MAX_REPORT_BYTES:
        raise ProtocolError('offline_report_size_invalid')
    # Read a single bounded snapshot. A changed/growing file must not turn an
    # untrusted receipt's declared length into an unbounded allocation.
    with Path(path).open('rb') as stream:
        raw = stream.read(byte_length + 1)
    if len(raw) != byte_length or digest_bytes(raw) != bytes_digest:
        raise ProtocolError('offline_report_bytes_changed')
    return raw


def validate_pytest_report(raw: bytes, *, cwd: str, argv: list[str]) -> dict[str, Any]:
    # This is a bounded report artifact, not a worker JSONL frame.
    value = strict_json_loads(raw,max_bytes=MAX_REPORT_BYTES)
    if (not isinstance(value, dict) or set(value) != {'schema_version','runner','argv','cwd','rootdir','exit_code',
            'collected_node_ids','discovered_node_ids','deselected_node_ids','nodes','collection_errors'}
            or value['schema_version'] != 'C2pPytestReportV1' or value['runner'] != 'pytest'
            or value['cwd'] != cwd or value['argv'] != argv or type(value['exit_code']) is not int
            or value['exit_code'] != 0 or value['collection_errors'] != []):
        raise ProtocolError('offline_pytest_report_invalid')
    selected, discovered, deselected = (value[key] for key in
        ('collected_node_ids','discovered_node_ids','deselected_node_ids'))
    for ids in (selected, discovered, deselected):
        if not isinstance(ids,list) or any(not isinstance(item,str) or not item for item in ids) or ids != sorted(set(ids)):
            raise ProtocolError('offline_discovery_invalid')
    if not selected or set(discovered) != set(selected) | set(deselected) or set(selected) & set(deselected):
        raise ProtocolError('offline_discovery_incomplete')
    rows=value['nodes']
    if not isinstance(rows,list) or [row.get('node_id') if isinstance(row,dict) else None for row in rows] != selected:
        raise ProtocolError('offline_node_coverage_incomplete')
    for row in rows:
        if set(row) != {'node_id','status','phases'} or row['status'] != 'passed' or not isinstance(row['phases'],list):
            raise ProtocolError('offline_required_node_not_passed')
        phases=row['phases']
        if (any(not isinstance(phase,dict) or set(phase) != {'phase','status'} or phase['status'] != 'passed' for phase in phases)
                or [phase['phase'] for phase in phases if phase['phase'] != 'subtest'] != ['setup','call','teardown']):
            raise ProtocolError('offline_required_phase_not_passed')
    return {'selected_node_ids':selected,'discovered_node_ids':discovered,'deselected_node_ids':deselected}


def validate_node_report(raw: bytes, *, cwd: str, argv: list[str], exec_argv: list[str]) -> dict[str, Any]:
    if len(raw) > MAX_REPORT_BYTES:
        raise ProtocolError('offline_report_size_invalid')
    lines=raw.splitlines()
    if not lines or any(not line for line in lines):
        raise ProtocolError('offline_node_report_empty')
    events=[strict_json_loads(line) for line in lines]
    meta=events.pop(0)
    if (not isinstance(meta,dict) or set(meta) != {'schema_version','argv','execArgv','cwd','node_version'}
            or meta['schema_version'] != 'C2pNodeRunMetadataV1' or meta['argv'] != argv or meta['execArgv'] != exec_argv
            or meta['cwd'] != cwd or not isinstance(meta['node_version'],str)):
        raise ProtocolError('offline_node_runner_mismatch')
    expected_keys={'schema_version','type','file','line','column','name','nesting','testNumber','skip','todo','details','counts'}
    nodes: dict[tuple, str] = {}
    summaries=[]
    file_entries=set()
    file_summaries={}
    for event in events:
        if (not isinstance(event,dict) or set(event) != expected_keys or event['schema_version'] != 'C2pNodeTestEventV1'
                or event['type'] not in {'test:enqueue','test:dequeue','test:pass','test:fail','test:summary'}):
            raise ProtocolError('offline_node_event_invalid')
        if event['type'] == 'test:summary':
            summaries.append(event['counts'])
            if event['file'] is not None:
                if event['file'] in file_summaries:raise ProtocolError('offline_node_summary_duplicate')
                file_summaries[event['file']]=event['counts']
            continue
        key=(event['file'],event['line'],event['column'],event['name'],event['nesting'])
        if (not isinstance(key[0],str) or not isinstance(key[3],str) or any(type(key[i]) is not int for i in (1,2,4))):
            raise ProtocolError('offline_node_id_invalid')
        if event['type'] == 'test:enqueue':
            if key in nodes:raise ProtocolError('offline_node_duplicate')
            nodes[key]='not-run'
            if key[0] == key[3] and key[1:] == (1,1,key[0],0):file_entries.add(key)
        elif event['type'] in {'test:pass','test:fail'}:
            if key not in nodes or nodes[key] != 'not-run':raise ProtocolError('offline_node_outcome_unbound')
            if (event['type'] != 'test:pass' or event['skip'] is not False or event['todo'] is not False
                    or not isinstance(event['details'],dict) or event['details'].get('errorType') is not None):
                raise ProtocolError('offline_required_node_not_passed')
            nodes[key]='passed'
    # Native process runner emits an enqueue/dequeue for each file container,
    # with its completion expressed as a per-file summary rather than a pass.
    # Require that positive summary; disappearance of the container is not exit.
    for key in file_entries:
        counts=file_summaries.get(key[0])
        if (not isinstance(counts,dict) or type(counts.get('tests')) is not int or counts['tests'] <= 0
                or any(type(counts.get(field)) is not int or counts[field] != 0 for field in ('failed','cancelled','skipped','todo'))
                or counts.get('passed') != counts['tests']):
            raise ProtocolError('offline_node_file_not_passed')
        if nodes[key] == 'not-run':nodes[key]='file-passed'
    if not nodes or any(status not in {'passed','file-passed'} for status in nodes.values()) or not summaries:
        raise ProtocolError('offline_node_coverage_incomplete')
    total=summaries[-1]
    if (not isinstance(total,dict) or any(type(total.get(key)) is not int for key in
            ('tests','failed','passed','cancelled','skipped','todo','suites'))
            or total['tests'] <= 0 or any(total[key] != 0 for key in ('failed','cancelled','skipped','todo'))
            or total['passed'] != total['tests'] or len(nodes)-len(file_entries) != total['tests']+total['suites']):
        raise ProtocolError('offline_node_summary_invalid')
    return {'node_ids':[list(key) for key in nodes if key not in file_entries],
        'entry_files':sorted(key[0] for key in file_entries),'counts':total,'node_version':meta['node_version']}


def validate_suite_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Rebuild registered commands and source discovery before any launch."""
    from .suite_plan import build_suite_plan
    expected=build_suite_plan(name=plan['name'],engine_root=Path(plan['engine_root']),
        python_executable=plan['suites'][0]['argv'][0],
        output_root=Path(plan['suites'][0]['report_path']).parent,
        effective_config=plan['effective_config'],engine_digest=plan['engine_digest'],
        validator_digest=plan['validator_digest'],composition_digest=plan['composition_digest'],
        candidate=plan['candidate'],node_executable=plan['suites'][1]['argv'][0] if len(plan['suites']) > 1 else '',
        core_reuse_path=Path(plan['core_reuse_path']) if 'core_reuse_path' in plan else None)
    if plan != expected:raise ProtocolError('offline_plan_changed_or_forged')
    return expected


def verify_suite_reports(plan: dict[str, Any], runs: list[dict[str, Any]], *, _reuse_cache=None) -> dict[str, Any]:
    """Recompute bound per-suite coverage; no aggregate passed flag is trusted."""
    from code2paper.agentic.digest import digest_json
    validate_suite_plan(plan)
    # Cache only within this synchronous validation, including its nested core
    # certificate. Separate admissions always read and validate anew.
    if _reuse_cache is None:_reuse_cache={}
    if len(runs) != len(plan['suites']) or [run.get('suite_id') for run in runs] != [suite['suite_id'] for suite in plan['suites']]:
        raise ProtocolError('offline_required_suite_missing')
    totals={'passed_count':0,'suite_node_ids':{},'test_plan_ids':[]}
    for suite,run in zip(plan['suites'],runs,strict=True):
        if 'evidence_reuse' in run:
            from .core_reuse import validate_reused_suite
            coverage=validate_reused_suite(plan,suite,run,_reuse_cache=_reuse_cache)
            totals['passed_count']+=coverage['passed_count']
            totals['suite_node_ids'][suite['suite_id']]=coverage['node_ids']
            totals['test_plan_ids'].extend(suite['required_targets'])
            continue
        keys={'suite_id','argv','cwd','runner','report_path','report_digest','report_bytes',
            'output_path','output_digest','output_bytes','exit_code','engine_before','engine_after',
            'validator_before','validator_after','composition_before','composition_after','effective_config_digest'}
        if suite['suite_id'] == 'node-cli':keys.update({'operation_evidence','budget_artifacts','run_artifacts'})
        if (set(run) != keys or any(run[key] != suite[key] for key in ('suite_id','argv','cwd','runner','report_path'))
                or type(run['exit_code']) is not int or run['exit_code'] != 0
                or any(run[key] != plan['engine_digest'] for key in ('engine_before','engine_after'))
                or any(run[key] != plan['validator_digest'] for key in ('validator_before','validator_after'))
                or any(run[key] != plan['composition_digest'] for key in ('composition_before','composition_after'))
                or run['effective_config_digest'] != digest_json(suite.get('effective_config',plan['effective_config']))):
            raise ProtocolError('offline_suite_binding_invalid')
        raw=read_bound_report(run['report_path'],bytes_digest=run['report_digest'],byte_length=run['report_bytes'])
        read_bound_report(run['output_path'],bytes_digest=run['output_digest'],byte_length=run['output_bytes'])
        if suite['runner'] == 'pytest':
            coverage=validate_pytest_report(raw,cwd=suite['cwd'],argv=suite['argv'])
            # Every discovered non-live file must actually contribute selected,
            # passing nodes. A label or command target alone cannot prove this.
            files={node.split('::',1)[0] for node in coverage['selected_node_ids']}
            missing=set(suite['discovered_files'])-files
            if missing:raise ProtocolError('offline_discovered_file_not_executed')
            totals['passed_count']+=len(coverage['selected_node_ids'])
            totals['suite_node_ids'][suite['suite_id']]=coverage['selected_node_ids']
        elif suite['runner'] == 'node':
            files=[str(Path(plan['engine_root'])/file) for file in suite['discovered_files']]
            coverage=validate_node_report(raw,cwd=suite['cwd'],argv=[suite['argv'][0],*files],
                exec_argv=suite['argv'][1:len(suite['argv'])-len(files)])
            if coverage['entry_files'] != sorted(files):raise ProtocolError('offline_node_entry_coverage_incomplete')
            totals['passed_count']+=coverage['counts']['tests']
            totals['suite_node_ids'][suite['suite_id']]=coverage['node_ids']
        else:raise ProtocolError('offline_runner_unknown')
        totals['test_plan_ids'].extend(suite['required_targets'])
    if plan['name'] == 'dsh-stage04':
        from .operator_evidence import validate_operator_evidence
        validate_operator_evidence(plan,runs,**({'_reuse_cache':_reuse_cache} if _reuse_cache else {}))
    return totals
