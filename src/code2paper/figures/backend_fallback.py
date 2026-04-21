"""Dependency-light fallback method overview figure backend."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .method_draft_adapter import build_figure_brief_from_files, clean_method_draft, extract_section_titles, read_method_draft


def generate_fallback_figure(
    draft_path: str | Path,
    *,
    out_dir: str | Path,
    method_evidence_path: str | Path | None = None,
    claim_map_path: str | Path | None = None,
) -> dict:
    """Generate a simple SVG overview directly from the method draft."""

    draft_text = clean_method_draft(read_method_draft(draft_path))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    brief_path = out / "method_overview.paperbanana_input.txt"
    brief_path.write_text(
        build_figure_brief_from_files(
            draft_path,
            method_evidence_path=method_evidence_path,
            claim_map_path=claim_map_path,
        ),
        encoding="utf-8",
    )

    nodes = _fallback_nodes(draft_text)
    svg_path = out / "method_overview.svg"
    svg_path.write_text(_render_svg(nodes), encoding="utf-8")

    png_path = out / "method_overview.png"
    pdf_path = out / "method_overview.pdf"
    generated = {"svg": str(svg_path), "png": "", "pdf": ""}
    generated.update(_try_convert_svg(svg_path, png_path, pdf_path))

    meta = {
        "backend": "fallback",
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "draft_path": str(draft_path),
            "method_evidence_path": str(method_evidence_path) if method_evidence_path else "",
            "claim_map_path": str(claim_map_path) if claim_map_path else "",
            "paperbanana_input": str(brief_path),
        },
        "nodes": nodes,
        "outputs": generated,
        "notes": [
            "Fallback SVG is deterministic and draft-derived.",
            "PNG/PDF are only emitted when CairoSVG is available.",
        ],
    }
    meta_path = out / "method_overview.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def _fallback_nodes(draft_text: str) -> list[str]:
    titles = [title for title in extract_section_titles(draft_text) if "note" not in title.lower()]
    if titles:
        return titles[:6]

    bold_titles = re.findall(r"\*\*([^*.]{3,80})\.\*\*", draft_text)
    if bold_titles:
        return [title.strip() for title in bold_titles[:6]]
    return ["Evidence Ingestion", "Code Alignment", "Method Evidence", "Method Draft", "Overview Figure"]


def _render_svg(nodes: list[str]) -> str:
    width = 1080
    height = 260
    margin = 52
    gap = 28
    node_count = max(1, len(nodes))
    box_width = max(128, int((width - margin * 2 - gap * (node_count - 1)) / node_count))
    box_height = 92
    y = 86

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="52" y="42" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700" fill="#17202a">Method Overview</text>',
    ]
    for idx, node in enumerate(nodes):
        x = margin + idx * (box_width + gap)
        if idx > 0:
            prev_x = margin + (idx - 1) * (box_width + gap) + box_width
            arrow_y = y + box_height / 2
            parts.append(
                f'<path d="M {prev_x + 6} {arrow_y:.1f} L {x - 10} {arrow_y:.1f}" stroke="#58606b" stroke-width="2" marker-end="url(#arrow)"/>'
            )
        parts.append(
            f'<rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" rx="8" fill="#f8fafc" stroke="#243447" stroke-width="1.5"/>'
        )
        for line_idx, line in enumerate(_wrap_label(node, 20)):
            text_y = y + 34 + line_idx * 20
            parts.append(
                f'<text x="{x + box_width / 2:.1f}" y="{text_y}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="15" fill="#17202a">{html.escape(line)}</text>'
            )
    parts.insert(
        1,
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#58606b"/></marker></defs>',
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _wrap_label(label: str, max_chars: int) -> list[str]:
    words = label.replace("-", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word[:max_chars]
    if current:
        lines.append(current)
    return lines[:3] or [label[:max_chars]]


def _try_convert_svg(svg_path: Path, png_path: Path, pdf_path: Path) -> dict[str, str]:
    outputs: dict[str, str] = {}
    try:
        import cairosvg  # type: ignore
    except Exception:
        return outputs

    try:
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        outputs["png"] = str(png_path)
    except Exception:
        pass
    try:
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(pdf_path))
        outputs["pdf"] = str(pdf_path)
    except Exception:
        pass
    return outputs
