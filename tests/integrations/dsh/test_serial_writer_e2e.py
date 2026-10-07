"""Actual staged Host/worker/HTTP/Session loop, through the offline launcher.

This target requires the provisioned, current staged candidate and bubblewrap.
It cannot skip an unavailable runtime or replace the chain with fixture facts.
The retained output proves this blocked serial sample, not all V01 admission.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

from code2paper.integrations.dsh.offline_admission import MAX_REPORT_BYTES, validate_node_report
from code2paper.integrations.dsh.protocol import strict_json_loads


ROOT = Path(__file__).resolve().parents[3]
# The complete plan supplies its frozen candidate; standalone use retains the
# original baseline. This test must exercise that same staged runtime/peer.
CANDIDATE = os.environ.get("C2P_DSH_CANDIDATE", "0.2.0-rc.1+loop-origin.1")
TIMEOUT_SECONDS = 420


def _json_artifact(path: Path):
    # Bound actual artifacts rather than trusting a missing/truncated report.
    with path.open("rb") as stream:
        raw = stream.read(MAX_REPORT_BYTES + 1)
    assert 0 < len(raw) <= MAX_REPORT_BYTES, f"invalid artifact size: {path}"
    return strict_json_loads(raw, max_bytes=MAX_REPORT_BYTES)


def _stop_owned_invocation(child: subprocess.Popen) -> None:
    """Reap only this test's new process group; this is no fee-release proof."""
    for action in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(child.pid, action)
        except ProcessLookupError:
            return
        try:
            child.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue
    raise AssertionError("owned offline launcher did not exit after termination")


def test_actual_serial_writer_blocked_and_new_process_recovery():
    dev_root = ROOT / ".dsh-dev" / "candidates" / CANDIDATE
    manifest = _json_artifact(dev_root / "manifest.json")
    assert manifest["dsh_version"] == CANDIDATE
    staged = dev_root / "home/profiles/node_modules/@code2paper/dsh-bundle"
    assert (staged / "lib/build-receipt.json").is_file(), "current staged candidate required"
    assert (dev_root / "pyworker/bin/python").is_file(), "locked worker required"

    # The launcher creates its own fresh direct child. Preserve both parent log
    # and inner /tmp bind after successful, failed, or interrupted execution.
    evidence = Path(tempfile.mkdtemp(prefix="c2p-dsh-python-e2e-", dir="/tmp")).resolve()
    output_root = evidence / "run"
    report_path = output_root / "node-events.jsonl"
    log_path = evidence / "launcher.log"
    entry = ROOT / "integrations/dsh/tests/host-provider.test.ts"
    command = [sys.executable, str(ROOT / "scripts/dsh_dev.py"), "--candidate", CANDIDATE,
        "test", "--output-root", str(output_root), "--report-path", str(report_path), str(entry)]
    environment = os.environ.copy()
    # Fixed controlled outcome and candidate cannot inherit another matrix lane.
    for key in ("C2P_DSH_CANDIDATE", "C2P_DSH_DEV_ROOT", "C2P_DSH_RUN_ROOT",
            "C2P_STAGE04_TEST_RECOVERY_CUT", "C2P_STAGE04_TEST_OUTCOME", "C2P_STAGE04_TEST_PAGE_KIND",
            "C2P_STAGE04_TEST_ONLY_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY",
            "GOOGLE_API_KEY", "GEMINI_API_KEY", "AZURE_OPENAI_API_KEY"):
        environment.pop(key, None)
    environment.update(C2P_STAGE04_TEST_RECOVERY_CUT="receipt", C2P_STAGE04_TEST_OUTCOME="blocked",
        C2P_STAGE04_TEST_PAGE_KIND="technical", PYTHONDONTWRITEBYTECODE="1")
    print(f"DSH_SERIAL_WRITER_E2E_OUTPUT={evidence}")
    with log_path.open("xb") as log:
        child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            exit_code = child.wait(timeout=TIMEOUT_SECONDS)
        except BaseException:
            _stop_owned_invocation(child)
            raise
    assert exit_code == 0, f"actual offline launcher exit {exit_code}; retained log: {log_path}"

    with report_path.open("rb") as stream:
        report_raw = stream.read(MAX_REPORT_BYTES + 1)
    node_exec_args = ["--test", "--test-concurrency=1", "--test-reporter=spec",
        "--test-reporter=" + str(ROOT / "integrations/dsh/dev/toolchain/suite-reporter.mjs"),
        "--test-reporter-destination=stdout", "--test-reporter-destination=" + str(report_path)]
    coverage = validate_node_report(report_raw, cwd=str(ROOT / "integrations/dsh"),
        argv=[manifest["node"], str(entry)], exec_argv=node_exec_args)
    assert coverage["entry_files"] == [str(entry)]
    assert coverage["counts"]["tests"] == 1
    assert coverage["node_version"] == manifest["node_version"]

    host_roots = sorted(output_root.glob("stage04-provider-*"))
    assert len(host_roots) == 1, "one actual controlled Host sample required"
    host_root = host_roots[0]
    result = _json_artifact(host_root / "result.json")
    receipt = result["receipt"]
    assert receipt["schema_version"] == "LocalWriterReceiptV1"
    assert receipt["domain_status"] == "blocked" and receipt["local_only"] is True
    assert receipt["detail"]["reason"] == "controlled offline refusal"
    budget = result["budget"]
    assert budget["call_count"] == 1
    assert budget["spent_input_tokens"] == 17 and budget["pending_input_tokens"] == 0
    assert result["calibration_sends"] == 1 and result["task_sends"] == 1
    assert result["recovery"] == {"cut": "receipt", "new_worker": True,
        "lost_capability": True, "receipt_identical": True, "additional_sends": 0}
    observations = _json_artifact(host_root / "provider-observations.json")
    assert isinstance(observations, list) and len(observations) == 2
    assert all(isinstance(row["body"], str) and row["body"] and
        isinstance(row["sse"], str) and row["sse"] for row in observations)
    cleanup = _json_artifact(host_root / "cleanup.json")
    assert cleanup["worker_scope_quiescent"] is True
    assert cleanup["provider_is_offline_fake"] is True and cleanup["provider_port_rebound"] is True
    assert cleanup["sentinel"] == _json_artifact(host_root / "python-sentinel.json")
    assert cleanup["sentinel"]["state"] == "closed"
    assert cleanup["sentinel"]["probe_refused"] is True
    assert cleanup["sentinel"]["model_calls"] == 0 and cleanup["sentinel"]["network_calls"] == 0
    assert result["sentinel"]["probe_refused"] is True
    assert result["sentinel"]["model_calls"] == 0 and result["sentinel"]["network_calls"] == 0
