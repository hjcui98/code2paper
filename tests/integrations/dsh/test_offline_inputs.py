"""Transport closure UNIT tests; no successful certificate or Host is fabricated."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from code2paper.agentic.digest import canonical_json_bytes
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from code2paper.integrations.dsh import offline_inputs
from code2paper.integrations.dsh.operator_evidence import EVIDENCE_KEYS
from code2paper.integrations.dsh.protocol import ProtocolError
from .test_composition_identity import composition


@pytest.fixture
def closure(tmp_path, composition):
    task = tmp_path / 'qualified'
    run = task / 'run'
    budget = run / 'invocations'
    budget.mkdir(parents=True)
    operator = {'task_root': str(task), 'budget_root': str(budget)}
    for key in EVIDENCE_KEYS:
        path = task / key
        path.write_bytes(b'UNIT transport bytes')
        operator[key] = str(path)
    bootstrap = {'engine_root': str(tmp_path), 'composition': {}, 'composition_spec': {
        'files': {key: str(path) for key, path in composition.files.items()},
        'trees': {key: str(path) for key, path in composition.trees.items()},
        'effective_config': composition.effective_config}}
    Path(operator['bootstrap_path']).write_bytes(canonical_json_bytes(bootstrap))
    receipt = tmp_path / 'certificate-locator'
    receipt.write_bytes(b'UNIT locator, not a certificate')
    report = tmp_path / 'native-report'
    report.write_bytes(b'UNIT report locator, not a native report')
    output = tmp_path / 'native-output'
    output.write_bytes(b'UNIT output locator')
    leaf = run / 'original-material'
    leaf.write_bytes(b'UNIT original material bytes')
    event = budget / 'original-event'
    event.write_bytes(b'UNIT fee transport bytes')
    # No passed flag/schema/grant. Only the transport enumerator is exercised;
    # production calls it after the complete original certificate verifier.
    observation = SimpleNamespace(machine_runs=[{'report_path': str(report), 'output_path': str(output),
        'operation_evidence': {key: {'path': value} for key, value in operator.items() if key in EVIDENCE_KEYS},
        'run_artifacts': [{'path': str(leaf)}, {'path': str(event)}],
        'budget_artifacts': [{'path': str(event)}]}])
    return receipt, observation, {'operator': operator}, tmp_path, composition


def test_all_transitive_transport_dependencies_and_directory_enumeration(closure):
    receipt, observation, plan, root, spec = closure
    inputs = offline_inputs._coverage_read_closure(receipt, observation, plan, root)
    expected = {receipt, *(Path(plan['operator'][key]) for key in EVIDENCE_KEYS),
        root / 'qualified/run', root / 'qualified/run/invocations', root / 'native-report', root / 'native-output',
        root / 'qualified/run/original-material', root / 'qualified/run/invocations/original-event',
        *spec.files.values(), *spec.trees.values()}
    assert set(inputs) == expected
    assert inputs == sorted(expected, key=lambda path: (len(path.parts), str(path)))
    assert len(inputs) == len(set(inputs))
    assert not hasattr(observation, 'passed')


@pytest.mark.parametrize('key', sorted(EVIDENCE_KEYS))
def test_missing_bound_operation_file_fails_before_sandbox(closure, key):
    receipt, observation, plan, root, _ = closure
    Path(plan['operator'][key]).unlink()
    with pytest.raises(ProtocolError, match='offline_input_path_invalid'):
        offline_inputs._coverage_read_closure(receipt, observation, plan, root)


def test_symlinked_operation_file_is_not_a_mount_authority(closure):
    receipt, observation, plan, root, _ = closure
    path = Path(plan['operator']['launch_path'])
    path.unlink()
    path.symlink_to(root / 'native-output')
    with pytest.raises(ProtocolError, match='offline_input_path_invalid'):
        offline_inputs._coverage_read_closure(receipt, observation, plan, root)


def test_nonpassing_receipt_rejected_before_qualified_owner_or_mount_derivation(tmp_path, monkeypatch):
    receipt = tmp_path / 'failed.json'
    receipt.write_bytes(canonical_json_bytes(OfflineSuiteReceiptV1().model_dump(mode='json')))
    def forbidden(*args, **kwargs):
        pytest.fail('failed coverage cannot reach the qualified owner or transport derivation')
    monkeypatch.setattr(offline_inputs, '_validate_admission', forbidden)
    monkeypatch.setattr(offline_inputs, '_coverage_read_closure', forbidden)
    with pytest.raises(ProtocolError, match='host_admission_full_dsh_receipt_required'):
        offline_inputs.coverage_readonly_inputs(receipt, candidate='unit', engine_root=tmp_path)


@pytest.mark.parametrize('change', ['profile-package', 'profile-patch', 'staged-cli',
                                   'staged-transitive', 'staged-new-module'])
def test_complete_profile_and_staged_trees_reject_real_byte_drift(composition, tmp_path, change):
    """Original I01 hashes actual tree bytes; no certificate or Host is granted."""
    from code2paper.agentic.authoring_execution_identity import (
        capture_execution_composition, validate_execution_composition,
    )
    from .test_composition_identity import ROOT
    profile = tmp_path / 'profile'
    profile.mkdir()
    staged = tmp_path / 'staged'
    (staged / 'lib').mkdir(parents=True)
    members = {'profile-package': profile / 'package.json', 'profile-patch': profile / 'cordis.patch.yml',
               'staged-cli': staged / 'lib/cli.js', 'staged-transitive': staged / 'lib/workflow-driver.js'}
    for path in members.values():
        path.write_bytes(b'UNIT original runtime bytes')
    composition.trees.update(host_profile_runtime=profile, staged_bundle=staged)
    composition.files.update(host_profile_package=members['profile-package'], host_profile_patch=members['profile-patch'])
    expected = capture_execution_composition(composition, engine_root=ROOT)
    changed = staged / 'lib/new-module.js' if change == 'staged-new-module' else members[change]
    changed.write_bytes(b'UNIT changed executable or profile bytes')
    observed = capture_execution_composition(composition, engine_root=ROOT)
    tree = 'host_profile_runtime' if change.startswith('profile') else 'staged_bundle'
    assert observed['trees'][tree] != expected['trees'][tree]
    assert observed['engine_digest'] == expected['engine_digest']
    assert observed['validator_digest'] == expected['validator_digest']
    with pytest.raises(ValueError, match='^composition_drift$'):
        validate_execution_composition(composition, expected, engine_root=ROOT)


@pytest.mark.parametrize('change', ['symlink-target', 'canonical-bytes', 'venv-config'])
def test_original_i01_pins_python_command_target_and_environment(composition, tmp_path, change):
    from code2paper.agentic.authoring_execution_identity import (
        capture_execution_composition, validate_execution_composition,
    )
    from .test_composition_identity import ROOT
    canonical = tmp_path / 'base-python'
    alternate = tmp_path / 'alternate-python'
    # Equal bytes make retarget refusal depend on alias identity, not content.
    canonical.write_bytes(b'UNIT interpreter bytes')
    alternate.write_bytes(canonical.read_bytes())
    command = tmp_path / 'python-command'
    command.symlink_to(canonical)
    environment = tmp_path / 'pyvenv.cfg'
    environment.write_bytes(b'UNIT frozen environment')
    composition.files.update(python_executable=command, python_environment=environment)
    expected = capture_execution_composition(composition, engine_root=ROOT)
    if change == 'symlink-target':
        command.unlink()
        command.symlink_to(alternate)
    elif change == 'canonical-bytes':
        canonical.write_bytes(b'UNIT changed interpreter bytes')
    else:
        environment.write_bytes(b'UNIT changed environment')
    actual = capture_execution_composition(composition, engine_root=ROOT)
    key = 'python_environment' if change == 'venv-config' else 'python_executable'
    assert actual['files'][key] != expected['files'][key]
    assert actual['engine_digest'] == expected['engine_digest']
    assert actual['validator_digest'] == expected['validator_digest']
    with pytest.raises(ValueError, match='^composition_drift$'):
        validate_execution_composition(composition, expected, engine_root=ROOT)
