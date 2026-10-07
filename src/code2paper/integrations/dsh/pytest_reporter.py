"""Actual pytest discovery/outcome reporter for operator offline suite runs.

Loaded explicitly with -p, never by the private worker. A missing phase result
stays not-run; a successful call cannot hide setup/teardown failure.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

_nodes: dict[str, dict] = {}
_deselected: set[str] = set()
_collection_errors: list[str] = []
_PRIORITY = {'passed': 0, 'skipped': 1, 'failed': 2, 'error': 3}


def pytest_addoption(parser):
    parser.addoption('--c2p-suite-report', action='store', default=None)


def pytest_sessionstart(session):
    _nodes.clear()
    _deselected.clear()
    _collection_errors.clear()


def pytest_deselected(items):
    _deselected.update(item.nodeid for item in items)


def pytest_collectreport(report):
    if report.failed:
        _collection_errors.append(report.nodeid)


def pytest_collection_finish(session):
    for item in session.items:
        _nodes[item.nodeid] = {'node_id': item.nodeid, 'status': 'not-run', 'phases': []}


def pytest_runtest_logreport(report):
    row = _nodes.setdefault(report.nodeid, {'node_id': report.nodeid, 'status': 'not-run', 'phases': []})
    status = 'error' if report.failed and report.when != 'call' else report.outcome
    phase='subtest' if hasattr(report,'context') else report.when
    row['phases'].append({'phase': phase, 'status': status})
    if report.when == 'call' or status in {'failed', 'error', 'skipped'}:
        if row['status'] == 'not-run' or _PRIORITY[status] > _PRIORITY[row['status']]:
            row['status'] = status


def pytest_sessionfinish(session, exitstatus):
    destination = session.config.getoption('--c2p-suite-report')
    if destination is None:
        return
    report = {'schema_version': 'C2pPytestReportV1', 'runner': 'pytest',
        'argv': [sys.executable, *sys.orig_argv[1:]], 'cwd': os.getcwd(), 'rootdir': str(session.config.rootpath),
        'exit_code': int(exitstatus), 'collected_node_ids': sorted(_nodes),
        'discovered_node_ids': sorted(set(_nodes) | _deselected),
        'deselected_node_ids': sorted(_deselected),
        'nodes': [_nodes[key] for key in sorted(_nodes)],
        'collection_errors': sorted(_collection_errors)}
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.tmp-{os.getpid()}')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
