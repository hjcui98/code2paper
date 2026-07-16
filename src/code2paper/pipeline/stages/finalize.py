"""Phase 8 final packaging for a complete method PDF."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any

from code2paper.export.run_manifest import hash_file
from code2paper.rendering.method_pdf import build_method_section_pdf
from code2paper.core.output_names import method_output


def write_phase8_artifacts(
    *,
    method_root: Path,
    method_tex_path: Path,
    figure_candidates: list[Path] | None = None,
    equations_tex_path: Path | None = None,
    symbols_tex_path: Path | None = None,
    compiler: str | None = None,
    timeout_seconds: int = 300,
    figure_caption: str = "",
    figure_asset_basename: str = "method_framework",
    method_markdown_path: Path | None = None,
    lineage_artifacts: dict[str, Path] | None = None,
) -> dict[str, Any]:
    method_root.mkdir(parents=True, exist_ok=True)
    extra_tex_blocks = _load_optional_blocks(equations_tex_path, symbols_tex_path)
    final_pdf_path = method_output(method_root, "final_pdf")
    final_out_root = final_pdf_path.parent
    report = build_method_section_pdf(
        method_tex_path=method_tex_path,
        output_dir=final_out_root,
        figure_candidates=figure_candidates,
        compiler=compiler,
        timeout_seconds=timeout_seconds,
        output_basename="final_method",
        section_title="Method",
        figure_caption=figure_caption,
        figure_asset_basename=figure_asset_basename,
        extra_tex_blocks=extra_tex_blocks,
    )
    standalone_tex_path = Path(str(report.get("standalone_tex_path") or ""))
    final_tex_path = method_output(method_root, "final_tex")
    if standalone_tex_path.exists():
        final_tex_path.write_text(standalone_tex_path.read_text(encoding="utf-8"), encoding="utf-8")
    root_method_tex = method_output(method_root, "root_method_tex")
    if final_tex_path.exists():
        shutil.copyfile(final_tex_path, root_method_tex)
    root_method_md = method_output(method_root, "root_method_md")
    if method_markdown_path and method_markdown_path.exists():
        shutil.copyfile(method_markdown_path, root_method_md)
    report_path = method_output(method_root, "final_pdf_report")
    _write_json(report_path, report)
    manifest_path = method_output(method_root, "phase8_manifest")
    package_manifest_path = method_output(method_root, "package_manifest")
    lineage = {"source_text_tex": _artifact(method_tex_path)}
    lineage.update(
        {
            name: _artifact(path)
            for name, path in sorted((lineage_artifacts or {}).items())
        }
    )
    manifest = {
        "schema_version": "2.0",
        "mode": "final-method-package",
        "status": report.get("status", "unknown"),
        "reason": report.get("reason", ""),
        "lineage_complete": all(bool(item.get("hash")) for item in lineage.values()),
        "outputs": {
            "final_tex": _artifact(method_output(method_root, "final_tex")),
            "final_pdf": _artifact(method_output(method_root, "final_pdf")),
            "final_pdf_report": _artifact(report_path),
            "method_md": _artifact(root_method_md),
            "method_tex": _artifact(root_method_tex),
        },
        "inputs": {
            "text_tex": str(method_tex_path),
            "equations_tex": str(equations_tex_path) if equations_tex_path and equations_tex_path.exists() else "",
            "symbols_tex": str(symbols_tex_path) if symbols_tex_path and symbols_tex_path.exists() else "",
        },
        "lineage": lineage,
    }
    _write_json(manifest_path, manifest)
    _write_json(package_manifest_path, manifest)
    return report


def _load_optional_blocks(equations_tex_path: Path | None, symbols_tex_path: Path | None) -> list[str]:
    if not _bool_env("CODE2PAPER_FINALIZE_APPEND_GROUNDING", _bool_env("CODE2PAPER_PHASE8_APPEND_GROUNDING", _bool_env("CODE2PAPER_PHASE6_APPEND_GROUNDING", False))):
        return []
    blocks: list[str] = []
    if equations_tex_path and equations_tex_path.exists():
        equations = equations_tex_path.read_text(encoding="utf-8").strip()
        if equations:
            blocks.append("\\subsection*{Code-Grounded Equations}\n" + equations)
    if symbols_tex_path and symbols_tex_path.exists():
        symbols = symbols_tex_path.read_text(encoding="utf-8").strip()
        if symbols:
            blocks.append("\\subsection*{Code-Grounded Symbols}\n" + symbols)
    return blocks


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _artifact(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"path": str(path), "hash": ""}
    return {"path": str(path), "hash": hash_file(path)}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
