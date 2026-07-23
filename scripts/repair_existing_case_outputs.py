from __future__ import annotations

import argparse
import json
from pathlib import Path

from code2paper.authoring.writing.tex_formatter import format_method_draft_tex
from code2paper.core.output_names import method_output
from code2paper.pipeline.stages.finalize import write_phase8_artifacts
from code2paper.rendering.method_pdf import build_method_section_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair existing Code2Paper case outputs by regenerating TeX from Markdown and rebuilding PDFs."
    )
    parser.add_argument("paths", nargs="+", help="Case directories or batch root directories.")
    parser.add_argument(
        "--compiler",
        default="",
        help="Optional LaTeX compiler override (tectonic/xelatex/pdflatex).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Timeout for each PDF build.",
    )
    args = parser.parse_args()

    case_dirs = list(_iter_case_dirs([Path(item) for item in args.paths]))
    if not case_dirs:
        print("No valid case directories found.")
        return 1

    for case_dir in case_dirs:
        try:
            report = repair_case(
                case_dir,
                compiler=str(args.compiler or "").strip() or None,
                timeout_seconds=int(args.timeout_seconds),
            )
        except Exception as exc:  # pragma: no cover - operational safety net
            print(f"[ERROR] {case_dir}: {exc}")
            continue
        print(json.dumps(report, ensure_ascii=False))
    return 0


def repair_case(case_dir: Path, *, compiler: str | None, timeout_seconds: int) -> dict[str, object]:
    artifacts_root = case_dir / "artifacts"
    authoring_root = artifacts_root / "06_authoring"
    if not authoring_root.exists():
        raise FileNotFoundError("missing artifacts/06_authoring")

    markdown_path, tex_path = _repair_authoring_tex(authoring_root)
    figure_candidates = [
        case_dir / "final" / "figures" / "method_overview.png",
        case_dir / "final" / "figures" / "method_overview.pdf",
        case_dir / "final" / "figures" / "method_overview.svg",
    ]
    for stale_pdf in (case_dir / "final" / "method.pdf", case_dir / "final" / "final_method.pdf"):
        if stale_pdf.exists():
            stale_pdf.unlink()

    method_root = artifacts_root
    method_pdf_report = build_method_section_pdf(
        method_tex_path=tex_path,
        output_dir=case_dir / "final",
        figure_candidates=figure_candidates,
        compiler=compiler,
        timeout_seconds=timeout_seconds,
        output_basename="method",
        figure_caption="Overall framework of the proposed method.",
        figure_asset_basename="method_framework",
    )
    method_pdf_report_path = method_output(method_root, "pdf_report")
    method_pdf_report_path.write_text(json.dumps(method_pdf_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    final_report = write_phase8_artifacts(
        method_root=method_root,
        method_tex_path=tex_path,
        figure_candidates=figure_candidates,
        equations_tex_path=method_output(method_root, "equations_tex"),
        symbols_tex_path=method_output(method_root, "symbols_tex"),
        compiler=compiler,
        timeout_seconds=timeout_seconds,
        figure_caption="Overall framework of the proposed method.",
        figure_asset_basename="method_framework",
    )

    return {
        "case_dir": str(case_dir),
        "markdown_source": str(markdown_path),
        "tex_output": str(tex_path),
        "method_pdf_status": method_pdf_report.get("status", ""),
        "method_pdf_reason": method_pdf_report.get("reason", ""),
        "final_pdf_status": final_report.get("status", ""),
        "final_pdf_reason": final_report.get("reason", ""),
        "method_pdf": str(case_dir / "final" / "method.pdf"),
        "final_pdf": str(case_dir / "final" / "final_method.pdf"),
    }


def _repair_authoring_tex(authoring_root: Path) -> tuple[Path, Path]:
    clean_md = authoring_root / "method_clean.md"
    draft_md = authoring_root / "method_draft.md"
    clean_tex = authoring_root / "method_clean.tex"
    draft_tex = authoring_root / "method_draft.tex"

    if clean_md.exists():
        markdown_path = clean_md
        tex_path = clean_tex
    elif draft_md.exists():
        markdown_path = draft_md
        tex_path = draft_tex
    else:
        raise FileNotFoundError("missing method_clean.md and method_draft.md")

    markdown = markdown_path.read_text(encoding="utf-8")
    tex = format_method_draft_tex(markdown)
    tex_path.write_text(tex, encoding="utf-8")

    if markdown_path == clean_md and draft_tex.exists():
        draft_markdown = draft_md.read_text(encoding="utf-8") if draft_md.exists() else markdown
        draft_tex.write_text(format_method_draft_tex(draft_markdown), encoding="utf-8")

    return markdown_path, tex_path


def _iter_case_dirs(paths: list[Path]):
    for path in paths:
        if (path / "artifacts" / "06_authoring").exists():
            yield path
            continue
        if not path.exists() or not path.is_dir():
            continue
        for child in sorted(path.iterdir()):
            if (child / "artifacts" / "06_authoring").exists():
                yield child


if __name__ == "__main__":
    raise SystemExit(main())
