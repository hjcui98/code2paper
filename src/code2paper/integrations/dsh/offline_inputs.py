"""Read-only transport closure of an original complete offline certificate.

This validates coverage and enumerates mounts. It grants no fresh task, Host,
worker, lease or model execution; target admission remains inside isolation.
"""
from __future__ import annotations

from pathlib import Path

from code2paper.agentic.digest import digest_bytes
from code2paper.agentic.live_admission_preflight import OfflineSuiteReceiptV1
from .host_admission import _bootstrap_spec, _read, _validate_admission
from .operator_evidence import EVIDENCE_KEYS
from .protocol import ProtocolError, strict_json_loads
from .suite_plan import PLAN_VERSIONS


def coverage_readonly_inputs(receipt_path: Path, *, candidate: str,
                            engine_root: Path) -> tuple[dict, list[Path]]:
    """Revalidate the complete original proof before deriving its read closure."""
    if (not receipt_path.is_absolute() or receipt_path.resolve() != receipt_path
            or receipt_path.is_symlink()):
        raise ProtocolError('offline_input_path_invalid')
    raw = _read(receipt_path)
    value = strict_json_loads(raw, max_bytes=32 << 20)
    receipt = OfflineSuiteReceiptV1.model_validate(value)
    plan = receipt.machine_plan
    if (receipt.schema_version != '2.0' or not receipt.passed or receipt.exit_code != 0
            or not isinstance(plan, dict) or plan.get('name') != 'dsh-stage04'
            or plan.get('version') != PLAN_VERSIONS['dsh-stage04']
            or plan.get('candidate') != candidate or plan.get('engine_root') != str(engine_root)
            or not isinstance(plan.get('operator'), dict)):
        raise ProtocolError('host_admission_full_dsh_receipt_required')
    operator = plan['operator']
    _validate_admission(bootstrap_path=Path(operator['bootstrap_path']), receipt_path=receipt_path,
                        candidate=candidate, launch_path=Path(operator['launch_path']))
    inputs = _coverage_read_closure(receipt_path, receipt, plan, engine_root)
    if digest_bytes(_read(receipt_path)) != digest_bytes(raw):
        raise ProtocolError('host_admission_inputs_changed')
    # Parent directory mounts precede explicit descendants. A directory is
    # included only when original I01/tree validation enumerated its contents.
    return value, inputs


def _coverage_read_closure(receipt_path: Path, receipt: OfflineSuiteReceiptV1,
                           plan: dict, engine_root: Path) -> list[Path]:
    """Transport enumeration only; caller must first validate original coverage."""
    operator = plan['operator']
    # Those original checks consume actual discovered reports, core coverage,
    # immutable qualified I01 and the entire operation/budget dependency trees.
    inputs = {receipt_path}

    def add(path: Path, *, directory: bool = False, resolved_material: bool = False) -> None:
        if resolved_material:
            path = path.resolve()
        if (not path.is_absolute() or path.resolve() != path or path.is_symlink()
                or not (path.is_dir() if directory else path.is_file())):
            raise ProtocolError('offline_input_path_invalid')
        inputs.add(path)

    for key in EVIDENCE_KEYS:
        add(Path(operator[key]))
    add(Path(operator['task_root']) / 'run', directory=True)
    add(Path(operator['budget_root']), directory=True)
    for run in receipt.machine_runs:
        if 'evidence_reuse' in run:
            from .core_reuse import reuse_readonly_paths
            for path in reuse_readonly_paths(run['evidence_reuse']):
                add(path,directory=path.is_dir())
            continue
        add(Path(run['report_path']))
        add(Path(run['output_path']))
        for binding in run.get('operation_evidence', {}).values():
            add(Path(binding['path']))
        for key in ('run_artifacts', 'budget_artifacts'):
            for binding in run.get(key, []):
                add(Path(binding['path']))
    bootstrap = strict_json_loads(_read(Path(operator['bootstrap_path'])), max_bytes=32 << 20)
    spec = _bootstrap_spec(bootstrap, engine_root)
    for path in spec.files.values():
        add(path, resolved_material=True)
    for path in spec.trees.values():
        add(path, directory=True, resolved_material=True)
    return sorted(inputs, key=lambda path: (len(path.parts), str(path)))
