"""Phase 7 rendering manifest for figures and standalone Method PDF."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.export.run_manifest import hash_file
from code2paper.core.output_names import method_output


def write_phase7_rendering_manifest(
    *,
    method_root: Path,
    figure_root: Path,
    figure_meta: dict[str, Any] | None,
    figure_skipped_reason: str,
    method_pdf_report: dict[str, Any] | None,
) -> dict[str, Any]:
    outputs: dict[str, dict[str, str]] = {}
    for name, path in {
        "method_overview_paperbanana_input": figure_root / "method_overview.paperbanana_input.txt",
        "method_overview_intent": figure_root / "method_overview.intent.json",
        "method_overview_meta": figure_root / "method_overview.meta.json",
        "method_overview_svg": figure_root / "method_overview.svg",
        "method_overview_png": figure_root / "method_overview.png",
        "method_overview_pdf": figure_root / "method_overview.pdf",
        "pdf_report": method_output(method_root, "pdf_report"),
        "text_pdf": method_output(method_root, "text_pdf"),
    }.items():
        if path.exists():
            outputs[name] = {"path": str(path), "hash": hash_file(path)}
    manifest = {
        "mode": "method-rendering",
        "status": _rendering_status(
            figure_meta=figure_meta,
            figure_skipped_reason=figure_skipped_reason,
            method_pdf_report=method_pdf_report,
        ),
        "figure_skipped_reason": figure_skipped_reason,
        "figure": figure_meta or {},
        "method_pdf": method_pdf_report or {},
        "outputs": outputs,
    }
    manifest_path = method_output(method_root, "phase7_manifest")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _rendering_status(
    *,
    figure_meta: dict[str, Any] | None,
    figure_skipped_reason: str,
    method_pdf_report: dict[str, Any] | None,
) -> str:
    if figure_skipped_reason:
        return "skipped"
    figure_status = str((figure_meta or {}).get("status") or "")
    pdf_status = str((method_pdf_report or {}).get("status") or "")
    if figure_status.startswith("success") and pdf_status in {"success", "fallback"}:
        return "success"
    if figure_status.startswith("success"):
        return "partial"
    return "unknown"
