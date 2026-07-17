from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from code2paper.agentic.benchmark_protocol import load_benchmark_protocol_v2
from code2paper.agentic.repo_snapshot import build_repo_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="code2paper-agentic-benchmark-run",
        description="Execute a frozen P4 protocol without changing its commands or environment contract.",
    )
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--index-out", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--repeat", action="append", type=int, default=[])
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)
    protocol = load_benchmark_protocol_v2(args.protocol)
    code_root = Path(protocol.code_root)
    _require_clean_commit(code_root, protocol.workspace_commit)
    selected = [spec for spec in protocol.specs if (
        (not args.case or spec.case_id in args.case)
        and (not args.variant or spec.variant in args.variant)
        and (not args.repeat or spec.repeat_index in args.repeat)
    )]
    records: list[dict] = []
    for spec in selected:
        profile_failure = _capability_profile_failure(spec)
        if profile_failure:
            records.append(_blocked_record(spec, profile_failure))
            if not args.continue_on_error:
                break
            continue
        current = build_repo_snapshot(spec.repo_root)
        if current.snapshot_id != spec.repo_snapshot_id:
            records.append(_blocked_record(spec, "repo_snapshot_drift_before_run"))
            if not args.continue_on_error:
                break
            continue
        output = Path(spec.out_root)
        output.mkdir(parents=True, exist_ok=True)
        log_path = output / "p4_protocol_run.log"
        started = time.monotonic()
        environment = os.environ.copy()
        environment.update(spec.environment)
        result = subprocess.run(
            spec.command, cwd=code_root, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        log_path.write_text(result.stdout, encoding="utf-8")
        records.append({
            "case_id": spec.case_id, "variant": spec.variant, "intent_id": spec.intent_id,
            "repeat_index": spec.repeat_index, "run_id": spec.run_id,
            "out_root": spec.out_root, "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "log_path": str(log_path), "log_digest": _digest(log_path),
            "repo_snapshot_id": spec.repo_snapshot_id,
            "status": "finished" if result.returncode == 0 else "infrastructure_or_cli_failure",
        })
        _write_index(args.index_out, protocol, records, selected)
        if result.returncode != 0 and not args.continue_on_error:
            break
    _write_index(args.index_out, protocol, records, selected)
    return 0 if len(records) == len(selected) and all(item["status"] == "finished" for item in records) else 1


def _require_clean_commit(code_root: Path, expected_commit: str) -> None:
    commit = subprocess.run(
        ["git", "-C", str(code_root), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "-C", str(code_root), "status", "--porcelain", "--untracked-files=no"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if commit != expected_commit or dirty:
        raise RuntimeError("protocol code root is not the frozen clean commit")


def _blocked_record(spec, reason: str) -> dict:
    return {
        "case_id": spec.case_id, "variant": spec.variant, "intent_id": spec.intent_id,
        "repeat_index": spec.repeat_index, "run_id": spec.run_id, "out_root": spec.out_root,
        "exit_code": None, "duration_seconds": 0.0, "log_path": "", "log_digest": "",
        "repo_snapshot_id": spec.repo_snapshot_id, "status": reason,
    }


def _capability_profile_failure(spec) -> str:
    if spec.variant not in {"fixed_legacy", "agentic_gemma4_mtp"}:
        return ""
    path = Path(spec.capability_profile_path)
    if not path.is_file():
        return "capability_profile_missing_before_run"
    if _digest(path) != spec.capability_profile_digest:
        return "capability_profile_drift_before_run"
    if spec.environment.get("CODE2PAPER_LLM_CAPABILITY_PROFILE") != str(path):
        return "capability_profile_environment_mismatch"
    return ""


def _write_index(path: str, protocol, records: list[dict], selected) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0",
        "protocol_digest": "sha256:" + hashlib.sha256(protocol.model_dump_json().encode("utf-8")).hexdigest(),
        "workspace_commit": protocol.workspace_commit, "gold_digest": protocol.gold_digest,
        "selected_runs": len(selected), "completed_records": len(records), "runs": records,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
