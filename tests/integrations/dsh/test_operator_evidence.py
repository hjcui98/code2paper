"""Semantic UNIT coverage of the final operation-evidence boundary.

Only the upstream complete core-certificate verifier is isolated. No passing
full certificate or native report is manufactured. All remaining checks consume
real bound bytes, original TaskStore state and original invocation-ledger facts.
The managed CLI/native-report execution remains a separate acceptance obligation.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes
from code2paper.agentic.unified_invocation_ledger import read_run_budget_state
from code2paper.integrations.dsh import operator_evidence as evidence
from code2paper.integrations.dsh.artifacts import ArtifactStore, TaskScope
from code2paper.integrations.dsh.protocol import ProtocolError
from code2paper.integrations.dsh.task_store import TaskStore
from .test_invocation_events import journal


def _binding(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes_digest': digest_bytes(raw), 'byte_length': len(raw)}


class OperationFixture:
    def rebind(self):
        """Reach semantic validation after a controlled artifact mutation."""
        self.run['operation_evidence'] = {
            key: _binding(Path(self.operator[key])) for key in evidence.EVIDENCE_KEYS
        }
        self.run['run_artifacts'] = [
            _binding(path) for path in sorted(self.run_root.rglob('*')) if path.is_file()
        ]
        self.run['budget_artifacts'] = [
            _binding(path) for path in sorted(self.budget_root.rglob('*')) if path.is_file()
        ]

    def write(self, key, value):
        Path(self.operator[key]).write_bytes(canonical_json_bytes(value))

    def read(self, key):
        return json.loads(Path(self.operator[key]).read_bytes())

    def change(self, key, mutate):
        value = self.read(key)
        mutate(value)
        self.write(key, value)
        self.rebind()

    def update_budget_observation(self):
        self.change('result_path', lambda result: result.update(
            original_budget_state=read_run_budget_state(self.budget_root)))

    def validate(self):
        evidence.validate_operator_evidence(self.plan, self.runs)


@pytest.fixture
def operator_unit(tmp_path, monkeypatch, request):
    fixture = OperationFixture()
    task_root = tmp_path / 'operator' / 'stage04-provider-unit'
    task_root.mkdir(parents=True)
    fixture.run_root = task_root / 'run'
    fixture.scope = TaskScope('execution:test', 'task:writer', 0)
    store = TaskStore(fixture.run_root, fixture.scope)
    contract = ArtifactStore(fixture.run_root, fixture.scope).put_json(
        {'unit_contract': 'original lifecycle observation, no assessor authority'})
    prepared = store.prepare(workflow_id='workflow:writer', node_id='writer', scope_id='section:unit',
        contract_ref=contract.model_dump(mode='json'), content_revision=0, content_fence=0,
        snapshot_digest=digest_bytes(b'UNIT snapshot'))
    claim = store.claim('host:unit-observation')
    receipt = {'schema_version': 'LocalWriterReceiptV1', **fixture.scope.__dict__,
        'local_only': True, 'domain_status': 'blocked',
        'unit_only': 'original store terminal fixture; no domain assessor/full-certificate assertion'}
    store.commit(claim, receipt)
    _, fixture.budget_root, fixture.append = journal.__wrapped__(fixture.run_root)
    initial_budget = read_run_budget_state(fixture.budget_root)
    phases = ('reserve', 'dispatch-recorded', 'adapter-attempt')
    if getattr(request, 'param', 'settled') == 'settled':
        phases += ('usage', 'terminal', 'settlement')
    for kind in phases:
        if kind == 'usage':
            fixture.append(kind, usage_input_tokens=70, usage_output_tokens=4)
        else:
            fixture.append(kind)
    budget = read_run_budget_state(fixture.budget_root)
    assert budget['status'] == 'pass'
    assert budget['call_count'] == 1
    if getattr(request, 'param', 'settled') == 'settled':
        assert budget['completed_call_count'] == 1
        assert budget['pending_call_count'] == budget['pending_input_tokens'] == 0
        assert budget['provider_usage_status'] == 'validated'
    fixture.store = store
    fixture.operator = {'task_root': str(task_root), 'budget_root': str(fixture.budget_root),
        'task_store_path': str(store.path)}
    for key, filename in {
        'ready_path': 'operator-ready.json', 'bootstrap_path': 'bootstrap.json',
        'launch_path': 'operator-launch.json', 'core_receipt_path': 'operator-core-receipt.json',
        'result_path': 'operator-result.json', 'cleanup_path': 'cleanup.json',
        'provider_observations_path': 'provider-observations.json',
        'cli_stdout_path': 'operator-cli-output.log', 'cli_stderr_path': 'operator-cli-error.log',
        'sentinel_path': 'python-sentinel.json',
    }.items():
        fixture.operator[key] = str(task_root / filename)
    engine_root = str(tmp_path / 'unit-engine')
    candidate = 'unit-candidate'
    dev_root = str(tmp_path / 'unit-dev')
    python_owner = str(tmp_path / 'unit-frozen-guarded-launcher')
    fixture.executable = str(Path(dev_root) / 'home/profiles/node_modules/@code2paper/dsh-bundle/lib/cli.js')
    launch = {'provider_config': {'providers': {'offline_fake': {'baseURL': 'http://127.0.0.1:1234/v1'}}}}
    fixture.write('launch_path', launch)
    launch_bytes = Path(fixture.operator['launch_path']).read_bytes()
    bootstrap = {'scope': fixture.scope.__dict__,
        'composition_spec': {'files': {'test_worker_launcher': python_owner}},
        'host_launch_binding': {'schema_version': 'DshHostLaunchBindingV1',
            'path': fixture.operator['launch_path'], 'bytes_digest': digest_bytes(launch_bytes),
            'byte_length': len(launch_bytes)}}
    fixture.write('bootstrap_path', bootstrap)
    fixture.plan = {'operator': fixture.operator, 'engine_root': engine_root, 'candidate': candidate,
        'effective_config': {'dsh_dev_root': dev_root,
            'bootstrap_digest': digest_bytes(Path(fixture.operator['bootstrap_path']).read_bytes()),
            'qualification_parent_namespace': {'device': 1, 'inode': 100}}}
    epoch_started = prepared['epoch_started_ms']
    ready = {'task_not_prepared_observed_ms': epoch_started - 2, 'task_prepared': False,
        'core_receipt': fixture.operator['core_receipt_path'], 'calibration_sends': 1,
        'original_budget_state': initial_budget}
    fixture.write('ready_path', ready)
    qualification = {'schema_version': 'DshHostQualificationResultV1',
        'admission_scope': 'dsh-stage04-qualification', 'qualification_only': True,
        'normal_entry_authorized': False, 'model_execution_authorized': False,
        'admission_completed_ms': epoch_started - 1, 'receipt': receipt}
    sentinel = {'schema_version': 'PythonLlmRefusalSentinelV1', 'state': 'closed',
        'probe_refused': True, 'model_calls': 0, 'network_calls': 0}
    result = {'schema_version': 'Stage04OperatorResultV1', 'actual_cli_executable': True,
        'executable': fixture.executable, 'cwd': engine_root, 'exit_code': 0,
        'argv': [fixture.executable, 'qualify', '--experimental-dsh', '--candidate', candidate,
            '--python', python_owner, '--engine-root', engine_root,
            '--bootstrap', fixture.operator['bootstrap_path'], '--offline-receipt',
            fixture.operator['core_receipt_path'], '--launch-file', fixture.operator['launch_path']],
        'admission_scope': qualification['admission_scope'],
        'actual_network_namespace': {'device': 1, 'inode': 101},
        'receipt': receipt, 'original_budget_state': budget,
        'task_not_prepared_observed_ms': ready['task_not_prepared_observed_ms'],
        'admission_completed_ms': qualification['admission_completed_ms'],
        'task_epoch_started_ms': epoch_started, 'task_epoch_started_after_admission': True,
        'calibration_sends': 1, 'task_sends': 1, 'sentinel': sentinel}
    fixture.write('result_path', result)
    fixture.write('sentinel_path', sentinel)
    fixture.write('cleanup_path', {'sentinel': sentinel, 'worker_scope_quiescent': True,
        'provider_is_offline_fake': True, 'provider_port_rebound': True})
    fixture.write('provider_observations_path', [{'unit_http': 'calibration'}, {'unit_http': 'formal'}])
    fixture.write('core_receipt_path', {'unit_only': 'upstream boundary isolated; not a full certificate'})
    Path(fixture.operator['cli_stdout_path']).write_bytes(canonical_json_bytes(qualification) + b'\n')
    Path(fixture.operator['cli_stderr_path']).write_bytes(b'')
    fixture.run = {'suite_id': 'node-cli'}
    fixture.runs = [{'suite_id': 'unit-core-python'}, {'suite_id': 'unit-core-node'}, fixture.run]
    fixture.core_calls = []

    def isolated_core_verifier(plan, runs, raw):
        fixture.core_calls.append((plan, runs, deepcopy(raw)))

    monkeypatch.setattr(evidence, '_validate_core_certificate', isolated_core_verifier)
    fixture.rebind()
    return fixture


def test_semantic_unit_closure_uses_original_task_and_accounting_owners(operator_unit):
    operator_unit.validate()
    assert len(operator_unit.core_calls) == 1
    plan, runs, raw = operator_unit.core_calls[0]
    assert plan is operator_unit.plan
    assert runs is operator_unit.runs
    assert raw == Path(operator_unit.operator['core_receipt_path']).read_bytes()
    assert TaskStore.read_persisted(operator_unit.run_root, operator_unit.scope)['receipt'] == operator_unit.read('result_path')['receipt']


def test_upstream_core_failure_propagates_without_manufacturing_certificate(operator_unit, monkeypatch):
    operator_unit.change('core_receipt_path', lambda value: value.update(unit_only='wrong core scope'))
    calls = []

    def reject_core(plan, runs, raw):
        calls.append(raw)
        raise ProtocolError('offline_operator_core_receipt_invalid')

    monkeypatch.setattr(evidence, '_validate_core_certificate', reject_core)
    with pytest.raises(ProtocolError, match='core_receipt_invalid'):
        operator_unit.validate()
    assert calls == [Path(operator_unit.operator['core_receipt_path']).read_bytes()]


def test_rebound_failed_original_ledger_cannot_pass_numeric_success_counters(operator_unit):
    plan_root = operator_unit.budget_root / 'plans'
    plan_root.mkdir(parents=True, exist_ok=True)
    (plan_root / 'bad.json').write_bytes(b'{}')
    state = read_run_budget_state(operator_unit.budget_root)
    assert state['status'] == 'fail'
    assert state['failure_codes']
    assert state['call_count'] == 1 and state['spent_input_tokens'] == 70
    assert state['pending_input_tokens'] == 0
    operator_unit.update_budget_observation()
    with pytest.raises(ProtocolError, match='original_accounting_invalid'):
        operator_unit.validate()


@pytest.mark.parametrize('operator_unit', ['unsettled'], indirect=True)
def test_original_pending_missing_usage_cannot_be_cleanup_success(operator_unit):
    # Only reserve/dispatch/attempt facts were published through original APIs.
    # Missing usage is retained occupancy, not zero or completed accounting.
    state = read_run_budget_state(operator_unit.budget_root)
    assert state['pending_call_count'] == 1
    assert state['provider_usage_status'] == 'partial'
    assert state['provider_usage_missing_call_count'] == 1
    operator_unit.update_budget_observation()
    with pytest.raises(ProtocolError, match='original_accounting_invalid'):
        operator_unit.validate()


@pytest.mark.parametrize('key,field,value,error', [
    ('result_path', 'actual_cli_executable', False, 'executable_invalid'),
    ('result_path', 'actual_network_namespace', {'device': 1, 'inode': 100}, 'namespace_invalid'),
    ('result_path', 'actual_network_namespace', {'device': True, 'inode': 101}, 'namespace_invalid'),
    ('result_path', 'receipt', {'schema_version': 'LocalWriterReceiptV1', 'local_only': True}, 'original_receipt_invalid'),
    ('result_path', 'admission_scope', 'dsh-stage04-offline', 'qualification_scope_invalid'),
    ('result_path', 'task_epoch_started_after_admission', False, 'admission_order_invalid'),
    ('ready_path', 'task_prepared', True, 'admission_order_invalid'),
    ('ready_path', 'original_budget_state', {'call_count': 1, 'spent_input_tokens': 0, 'pending_input_tokens': 0}, 'preparation_accounting_invalid'),
    ('cleanup_path', 'worker_scope_quiescent', False, 'cleanup_unverified'),
    ('cleanup_path', 'provider_port_rebound', False, 'cleanup_unverified'),
])
def test_rebound_semantic_operation_refusals(operator_unit, key, field, value, error):
    operator_unit.change(key, lambda record: record.update({field: value}))
    with pytest.raises(ProtocolError, match=error):
        operator_unit.validate()
    assert len(operator_unit.core_calls) == 1


@pytest.mark.parametrize('field,value', [
    ('schema_version', 'UnknownSentinelV1'), ('state', 'installed'),
    ('probe_refused', False), ('model_calls', 1), ('network_calls', 1),
])
def test_rebound_consistent_sentinel_copies_still_require_closed_original_record(operator_unit, field, value):
    sentinel = operator_unit.read('sentinel_path')
    sentinel[field] = value
    operator_unit.write('sentinel_path', sentinel)
    for key in ('result_path', 'cleanup_path'):
        record = operator_unit.read(key)
        record['sentinel'] = sentinel
        operator_unit.write(key, record)
    operator_unit.rebind()
    with pytest.raises(ProtocolError, match='cleanup_unverified'):
        operator_unit.validate()


@pytest.mark.parametrize('index,replacement', [(1, 'run'), (6, '/tmp/unbound-guarded-owner'),
    (12, '/tmp/wrong-core-receipt')])
def test_rebound_executable_command_requires_exact_qualification_owners(operator_unit, index, replacement):
    operator_unit.change('result_path', lambda result: result['argv'].__setitem__(index, replacement))
    with pytest.raises(ProtocolError, match='executable_invalid'):
        operator_unit.validate()


@pytest.mark.parametrize('field,value', [('qualification_only', False),
    ('normal_entry_authorized', True), ('model_execution_authorized', True),
    ('admission_completed_ms', 1), ('receipt', {'unit_mismatch': True})])
def test_rebound_cli_stdout_scope_and_receipt_are_checked(operator_unit, field, value):
    path = Path(operator_unit.operator['cli_stdout_path'])
    qualification = json.loads(path.read_bytes())
    qualification[field] = value
    path.write_bytes(canonical_json_bytes(qualification) + b'\n')
    operator_unit.rebind()
    expected = ('admission_order_invalid' if field == 'admission_completed_ms' else
        'original_receipt_invalid' if field == 'receipt' else 'qualification_scope_invalid')
    with pytest.raises(ProtocolError, match=expected):
        operator_unit.validate()
