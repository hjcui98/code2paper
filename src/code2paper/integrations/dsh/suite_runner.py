"""Bounded operator execution of a frozen offline plan, once per suite.

No resends, model admission, or budget decisions. Timeouts remain failed;
process cleanup cannot refund reservations left by an interrupted test.
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
import signal
import stat
import subprocess
import time

from code2paper.agentic.authoring_execution_identity import (
    capture_engine_source_snapshot, capture_validator_bundle_snapshot,
)
from code2paper.agentic.digest import digest_json
from .protocol import ProtocolError
from .offline_admission import validate_suite_plan


def _identity(root):
    engine=capture_engine_source_snapshot(root)
    validator=capture_validator_bundle_snapshot(root)
    if not engine.is_usable or engine.unstable or not validator.is_usable:
        raise ProtocolError('offline_source_identity_unavailable')
    return engine,validator


def _artifact_identity(path: Path, *, allow_missing: bool = False) -> tuple[str, int]:
    """Record the entire artifact without allocating its untrusted length.

    The consumer still enforces its report/log size ceiling. An oversized
    artifact gets its real digest and length, never a passing truncated prefix.
    """
    hasher=hashlib.sha256()
    length=0
    try:
        stream=path.open('rb')
    except FileNotFoundError:
        if allow_missing:return 'sha256:'+hasher.hexdigest(),0
        raise
    with stream:
        before=os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ProtocolError('offline_artifact_not_regular')
        remaining=before.st_size+1
        while remaining and (chunk := stream.read(min(1 << 20,remaining))):
            hasher.update(chunk);length+=len(chunk)
            remaining-=len(chunk)
        after=os.fstat(stream.fileno())
        current=path.stat()
    def signature(stat):
        return stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns
    if signature(before) != signature(after) or signature(after) != signature(current) or length != after.st_size:
        raise ProtocolError('offline_artifact_changed_during_capture')
    return 'sha256:'+hasher.hexdigest(),length


def execute_suite_plan(plan: dict, *, timeout_seconds: float, verify_composition=None) -> tuple[list[dict], object]:
    if not 0 < timeout_seconds < float('inf'):raise ProtocolError('offline_timeout_invalid')
    validate_suite_plan(plan)
    if plan['name'] == 'dsh-stage04':raise ProtocolError('offline_managed_qualification_required')
    root=Path(plan['engine_root'])
    deadline=time.monotonic()+timeout_seconds
    runs=[]
    for suite in plan['suites']:
        before,validator_before=_identity(root)
        if before.source_digest != plan['engine_digest'] or validator_before.digest != plan['validator_digest']:
            raise ProtocolError('offline_source_changed_before_suite')
        composition_before=verify_composition() if verify_composition is not None else ''
        if composition_before != plan['composition_digest']:raise ProtocolError('offline_composition_changed')
        output=Path(plan['suites'][0]['report_path']).parent/f"{suite['suite_id']}-output.log"
        if output.exists() or Path(suite['report_path']).exists():raise ProtocolError('offline_output_not_fresh')
        remaining=deadline-time.monotonic()
        exit_code=124
        # Only fixed plan commands reach this owner. Environment values are
        # never copied into reports; API keys are removed from child processes.
        environment=dict(os.environ)
        for key in ('OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY'):
            environment.pop(key,None)
        environment['PYTHONDONTWRITEBYTECODE']='1'
        environment['PYTHONPATH']=str(root/'src')
        if plan['name'] in {'dsh-stage04','dsh-stage04-core'}:
            environment['C2P_DSH_CANDIDATE']=plan['candidate']
            environment['C2P_DSH_DEV_ROOT']=plan['effective_config']['dsh_dev_root']
        command=suite.get('launch_argv',suite['argv'])
        with output.open('xb') as stream:
            if remaining > 0:
                try:
                    process=subprocess.Popen(command,cwd=root if 'launch_argv' in suite else suite['cwd'],
                        env=environment,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                    try:exit_code=process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        try:os.killpg(process.pid,signal.SIGTERM)
                        except ProcessLookupError:pass
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            try:os.killpg(process.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                            process.wait(timeout=5)
                        exit_code=124
                except OSError:
                    stream.write(b'offline suite launch failed\n');exit_code=126
            else:stream.write(b'offline plan deadline exhausted before launch\n')
            stream.flush();os.fsync(stream.fileno())
        after,validator_after=_identity(root)
        composition_after=verify_composition() if verify_composition is not None else ''
        report=Path(suite['report_path'])
        report_digest,report_bytes=_artifact_identity(report,allow_missing=True)
        output_digest,output_bytes=_artifact_identity(output)
        run={key:suite[key] for key in ('suite_id','argv','cwd','runner','report_path')}
        run.update(report_digest=report_digest,report_bytes=report_bytes,
            output_path=str(output),output_digest=output_digest,output_bytes=output_bytes,exit_code=exit_code,
            engine_before=before.source_digest,engine_after=after.source_digest,
            validator_before=validator_before.digest,validator_after=validator_after.digest,
            composition_before=composition_before,composition_after=composition_after,
            effective_config_digest=digest_json(suite.get('effective_config',plan['effective_config'])))
        runs.append(run)
        if exit_code != 0 or before.source_digest != after.source_digest or validator_before.digest != validator_after.digest:
            break
        if composition_before != composition_after:break
    final,_=_identity(root)
    # Validation is performed by the original receipt builder/consumer, too.
    # This runner records failures rather than manufacturing missing reports.
    return runs,final
