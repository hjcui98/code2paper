"""Phase 6 validation manifest for Method artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.export.run_manifest import hash_file
from code2paper.core.output_names import method_output


def write_phase6_validation_manifest(
    *,
    method_root: Path,
    fidelity_passed: bool,
    validation_skipped_reason: str = "",
) -> dict[str, Any]:
    paths = {
        "method_plan_quality": method_output(method_root, "method_plan_quality"),
        "semantic_issues": method_output(method_root, "semantic_issues"),
        "self_check": method_output(method_root, "self_check"),
        "self_check_clean": method_output(method_root, "self_check_clean"),
        "qa_claims": method_output(method_root, "qa_claims"),
        "qa_numbers": method_output(method_root, "qa_numbers"),
        "qa_equations": method_output(method_root, "qa_equations"),
        "qa_terms": method_output(method_root, "qa_terms"),
        "qa_latex": method_output(method_root, "qa_latex"),
        "fidelity": method_output(method_root, "fidelity"),
    }
    reports = {name: _report_status(path) for name, path in paths.items() if path.exists()}
    failed = [
        name
        for name, report in reports.items()
        if report.get("passed") is False and _is_blocking_report_failure(name, report)
    ]
    advisory_failed = [
        name
        for name, report in reports.items()
        if report.get("passed") is False and not _is_blocking_report_failure(name, report)
    ]
    manifest = {
        "mode": "method-validation",
        "status": "skipped" if validation_skipped_reason else ("failed" if failed or not fidelity_passed else "passed"),
        "skipped_reason": validation_skipped_reason,
        "fidelity_passed": bool(fidelity_passed),
        "failed_reports": failed,
        "advisory_failed_reports": advisory_failed,
        "reports": reports,
        "outputs": {
            name: {"path": str(path), "hash": hash_file(path)}
            for name, path in paths.items()
            if path.exists()
        },
    }
    manifest_path = method_output(method_root, "phase6_manifest")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _is_blocking_report_failure(name: str, report: dict[str, Any]) -> bool:
    if name in {"self_check", "self_check_clean"}:
        return False
    if name == "qa_latex":
        return str(report.get("status") or "").strip().lower() != "unavailable"
    return True


def _report_status(path: Path) -> dict[str, Any]:
    status: dict[str, Any] = {"path": str(path), "hash": hash_file(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        status["passed"] = None
        return status
    if isinstance(payload, dict):
        if "passed" in payload:
            status["passed"] = bool(payload.get("passed"))
        elif "issues" in payload and isinstance(payload.get("issues"), list):
            status["passed"] = len(payload.get("issues") or []) == 0
        elif "status" in payload:
            status["passed"] = str(payload.get("status")) in {"compiled", "success", "ok"}
        else:
            status["passed"] = None
        if "issue_count" in payload:
            status["issue_count"] = payload.get("issue_count")
        elif isinstance(payload.get("issues"), list):
            status["issue_count"] = len(payload.get("issues") or [])
        if "status" in payload:
            status["status"] = payload.get("status")
    else:
        status["passed"] = None
    return status
