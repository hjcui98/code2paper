#!/usr/bin/env python3
"""Retry wrapper for the story-first code2paper pipeline."""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="code2paper-run-retry")
    parser.add_argument("--project", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--author", default="", help="story-first author_markers YAML")
    parser.add_argument("--llm-provider", default="openai")
    parser.add_argument("--llm-model", default="")
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--max-attempts", type=int, default=8)
    parser.add_argument("--initial-wait-seconds", type=int, default=30)
    parser.add_argument("--backoff-multiplier", type=float, default=2.0)
    parser.add_argument("--max-wait-seconds", type=int, default=600)
    parser.add_argument("--jitter-seconds", type=int, default=5)
    parser.add_argument("--strict-json-model", default="")
    parser.add_argument("--user-focus", default="")
    parser.add_argument("--llm-cache-dir", default="/tmp/code2paper_llm_cache")
    parser.add_argument("--clear-llm-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--disable-llm-cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--extra-run-args", nargs=argparse.REMAINDER)
    return parser.parse_args(argv)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _blocked_reason(method_root: Path, phase: str) -> str:
    manifest = _read_json(method_root / f"{phase}_manifest.json")
    blocked_reason = str(manifest.get("blocked_reason", "") or "")
    if blocked_reason:
        return blocked_reason
    blocked_report = _read_json(method_root / f"{phase}_blocked_report.json")
    return str(blocked_report.get("blocked_reason", "") or "")


def _retryable_failure(method_root: Path, *, rc: int) -> bool:
    combined = "\n".join(
        _blocked_reason(method_root, phase).lower()
        for phase in ("phase1", "phase2", "phase3", "phase4")
    )
    transient_markers = (
        "provider_http_error:408",
        "provider_http_error:409",
        "provider_http_error:429",
        "provider_http_error:500",
        "provider_http_error:502",
        "provider_http_error:503",
        "provider_http_error:504",
        "provider_network_error",
        "provider_timeout_error",
        "provider_unknown_error",
        "incomplete_read",
    )
    if any(marker in combined for marker in transient_markers):
        return True
    return rc != 0 and not (method_root / "phase2_manifest.json").exists()


def _pipeline_ready(out_root: Path) -> tuple[bool, str, str, bool, bool]:
    method_root = out_root / "paper" / "method"
    phase2_mode = str(_read_json(method_root / "phase2_manifest.json").get("mode", ""))
    phase3_mode = str(_read_json(method_root / "phase3_manifest.json").get("mode", ""))
    draft_exists = (method_root / "method_draft.md").exists()
    figure_input_exists = (out_root / "paper" / "figures" / "method_overview" / "method_overview.paperbanana_input.txt").exists()
    ok = phase2_mode in {"story-first-code-analyzer", "full-llm"} and phase3_mode in {
        "evidence-freeze",
        "author-marker-freeze",
    } and draft_exists
    return ok, phase2_mode, phase3_mode, draft_exists, figure_input_exists


def _clear_llm_cache(cache_dir: str) -> None:
    path = Path(cache_dir)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _build_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    if args.disable_llm_cache:
        env["CODE2PAPER_LLM_CACHE"] = "0"
    if args.strict_json_model.strip():
        env["CODE2PAPER_ENFORCE_STRICT_JSON_MODEL"] = "1"
        env["CODE2PAPER_STRICT_JSON_MODEL"] = args.strict_json_model.strip()
    if args.user_focus.strip():
        env["CODE2PAPER_USER_FOCUS"] = args.user_focus.strip()
    if args.llm_cache_dir.strip():
        env["CODE2PAPER_LLM_CACHE_DIR"] = args.llm_cache_dir.strip()
    return env


def _run_once(args: argparse.Namespace, *, env: dict[str, str]) -> int:
    cmd = [
        args.python_bin,
        "-m",
        "code2paper.main_cli",
        "run",
        "--project",
        args.project,
        "--out-root",
        args.out_root,
        "--llm-provider",
        args.llm_provider,
    ]
    if args.author.strip():
        cmd.extend(["--author", args.author.strip()])
    if args.llm_model.strip():
        cmd.extend(["--llm-model", args.llm_model.strip()])
    if args.extra_run_args:
        cmd.extend(args.extra_run_args)
    print("[retry-wrapper] exec:", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=False, env=env).returncode


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_root = Path(args.out_root)
    method_root = out_root / "paper" / "method"
    env = _build_env(args)
    if args.clear_llm_cache:
        _clear_llm_cache(args.llm_cache_dir)

    wait_seconds = max(1, args.initial_wait_seconds)
    for attempt in range(1, args.max_attempts + 1):
        print(f"[retry-wrapper] attempt {attempt}/{args.max_attempts}", flush=True)
        rc = _run_once(args, env=env)
        ok, phase2_mode, phase3_mode, draft_exists, figure_input_exists = _pipeline_ready(out_root)
        print(
            f"[retry-wrapper] phase2_mode={phase2_mode or 'missing'} phase3_mode={phase3_mode or 'missing'} "
            f"method_draft_md={'yes' if draft_exists else 'no'} figure_input={'yes' if figure_input_exists else 'no'} rc={rc}",
            flush=True,
        )
        if ok:
            print("[retry-wrapper] success: story-first pipeline produced method draft.", flush=True)
            return 0
        if not _retryable_failure(method_root, rc=rc):
            print("[retry-wrapper] stop: non-retryable failure.", flush=True)
            return rc if rc != 0 else 1
        if attempt == args.max_attempts:
            print("[retry-wrapper] stop: max attempts reached.", flush=True)
            return rc if rc != 0 else 2

        jitter = random.randint(0, max(0, args.jitter_seconds))
        sleep_for = min(args.max_wait_seconds, wait_seconds + jitter)
        print(f"[retry-wrapper] transient failure detected; sleeping {sleep_for}s before retry.", flush=True)
        time.sleep(sleep_for)
        wait_seconds = min(args.max_wait_seconds, int(wait_seconds * args.backoff_multiplier))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
