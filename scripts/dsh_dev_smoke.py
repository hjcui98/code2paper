#!/usr/bin/env python3
"""Start the isolated DSH UI, check real HTTP assets, and stop it; no model turn."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request

import dsh_dev as dev


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        default=os.environ.get(dev.CANDIDATE_ENV),
        help=(
            "use the isolated root .dsh-dev/candidates/<version> instead of the "
            f"default development environment (env {dev.CANDIDATE_ENV})"
        ),
    )
    parser.add_argument("--composition", choices=sorted(dev.COMPOSITIONS), default="web")
    parser.add_argument("--evidence-dir", type=Path, default=None, help="override directory for smoke evidence")
    args = parser.parse_args()
    dev.assert_selection_agreement(args.candidate)
    dev.select_candidate(args.candidate)
    if dev.CANDIDATE is not None:
        dev.require_candidate_ready("smoke")
    manifest = dev.read_manifest(args.composition)
    staging = dev.require_compat_bundle() if args.composition == "compat" else (
        dev.verify_staging() if dev.STAGING_RECEIPT.is_file() else None
    )
    staging_identity = None
    if staging is not None:
        record = dev.read_json(dev.STAGING_RECEIPT)
        staging_identity = {
            "staging_tree_sha256": staging["tree_sha256"],
            "staged_build_receipt_sha256": dev.digest_file(dev.BUNDLE_STAGING / "lib/build-receipt.json"),
            "staging_receipt_sha256": dev.digest_file(dev.STAGING_RECEIPT),
        }
        dev.require(staging_identity["staged_build_receipt_sha256"] == record["build_receipt_sha256"], "smoke staging receipt mismatch")
    proc = subprocess.Popen(
        dev.command(manifest, ["--host", "127.0.0.1", "--port", "0", "--no-open"], composition=args.composition),
        env=dev.child_env(manifest["node"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines: list[str] = []
    pending: queue.Queue[str] = queue.Queue()

    def reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            pending.put(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    result: dict = {"model_turns_submitted": 0, "ready": False}
    try:
        deadline = time.monotonic() + 40
        ready_url = None
        while time.monotonic() < deadline:
            try:
                line = pending.get(timeout=0.2)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            lines.append(line)
            if "dsh web:" in line:
                match = re.search(r"https?://[^\s\x1b]+", line)
                if match:
                    ready_url = match.group(0)
                    break
        dev.require(ready_url is not None, f"Web readiness not reached; exit={proc.poll()}")
        # Keep the authenticated startup URL and cookie only in memory.
        parsed = urllib.parse.urlsplit(ready_url)
        dev.require(parsed.hostname == "127.0.0.1", "unexpected bind address")
        result["port"] = parsed.port
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        with opener.open(ready_url, timeout=10) as response:
            body = response.read().decode()
            dev.require(response.status == 200 and "<html" in body.lower(), "invalid HTML response")
            result.update({"http_status": response.status, "html_bytes": len(body)})
        assets = re.findall(r'(?:src|href)="([^"\s]+\.(?:js|css)(?:\?[^"\s]*)?)"', body)
        dev.require(bool(assets), "frontend assets missing")
        checked = []
        for asset in assets[:4]:
            url = urllib.parse.urljoin(ready_url, asset)
            asset_url = urllib.parse.urlsplit(url)
            dev.require((asset_url.scheme, asset_url.netloc) == (parsed.scheme, parsed.netloc), "unexpected external asset")
            with opener.open(url, timeout=10) as response:
                size = len(response.read())
                dev.require(response.status == 200 and size > 0, "invalid frontend asset")
                checked.append({"path": asset_url.path, "status": response.status, "bytes": size})
        result.update({"frontend_assets": checked, "ready": True, "bind_host": parsed.hostname})
    except Exception as exc:
        result["error"] = re.sub(r"https?://[^\s]+", "[URL REDACTED]", str(exc))
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        thread.join(timeout=2)
        while not pending.empty():
            lines.append(pending.get())
        result["shutdown_exit"] = proc.returncode
    if "port" in result:
        with socket.socket() as probe:
            probe.settimeout(1)
            result["port_closed_after_shutdown"] = probe.connect_ex(("127.0.0.1", result["port"])) != 0
    result["passed"] = result["ready"] and result.get("port_closed_after_shutdown", False)
    result["composition"] = args.composition
    result["profile"] = dev.PROFILE_NAMES[args.composition]
    result["candidate"] = dev.CANDIDATE
    result["runtime_tree_sha256"] = manifest.get("runtime_tree_sha256")
    result["staging_proof_scope"] = "verified_staged_bundle" if staging_identity else "web_runtime_only"
    if staging_identity:
        result.update(staging_identity)
        try:
            current = dev.verify_staging()
            dev.require(current["tree_sha256"] == staging_identity["staging_tree_sha256"], "smoke staging changed during run")
            dev.require(dev.digest_file(dev.STAGING_RECEIPT) == staging_identity["staging_receipt_sha256"], "smoke receipt changed during run")
        except (RuntimeError, OSError, ValueError) as exc:
            result["passed"] = False
            result["error"] = str(exc)
    evidence_dir = args.evidence_dir or dev.EVIDENCE_DIR
    evidence_dir.mkdir(parents=True, exist_ok=True)
    redacted = re.sub(r"https?://[^\s\x1b]+", "[URL REDACTED]", "".join(lines))
    (evidence_dir / f"{args.composition}-smoke.redacted.log").write_text(redacted)
    dev.write_json(evidence_dir / f"{args.composition}-smoke.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        print(redacted[-6000:])
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
