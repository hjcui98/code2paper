"""Utilities for building a standalone method-section PDF artifact.

The compiler step is best-effort by default:
- if no LaTeX compiler is available, the pipeline keeps running.
- if compilation fails, a structured report is still emitted.
"""

from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path
from typing import Any


def build_method_section_pdf(
    *,
    method_tex_path: Path,
    output_dir: Path,
    figure_candidates: list[Path] | None = None,
    compiler: str | None = None,
    timeout_seconds: int = 300,
    output_basename: str = "text",
    section_title: str = "Method",
    figure_caption: str = "",
    figure_asset_basename: str = "method_framework",
    extra_tex_blocks: list[str] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "status": "skipped",
        "reason": "",
        "compiler": "",
        "method_tex_path": str(method_tex_path),
        "standalone_tex_path": "",
        "pdf_path": "",
        "figure_path": "",
        "stdout": "",
        "stderr": "",
        "log_path": "",
        "attempt_count": 0,
        "attempts": [],
    }
    if not method_tex_path.exists():
        report["reason"] = "method_tex_missing"
        return report

    selected_figure = _pick_first_existing(figure_candidates or [])
    standalone_tex = output_dir / f"{output_basename}.standalone.tex"
    pdf_path = output_dir / f"{output_basename}.pdf"
    report["standalone_tex_path"] = str(standalone_tex)
    report["pdf_path"] = str(pdf_path)
    figure_ref = _materialize_figure_asset(output_dir, selected_figure, asset_basename=figure_asset_basename)
    report["figure_path"] = str(figure_ref) if figure_ref else ""

    body = method_tex_path.read_text(encoding="utf-8")
    standalone_tex.write_text(
        _wrap_method_tex(
            body,
            figure_ref,
            section_title=section_title,
            figure_caption=figure_caption,
            extra_tex_blocks=extra_tex_blocks or [],
        ),
        encoding="utf-8",
    )

    tool = _resolve_compiler(compiler)
    if not tool:
        fallback = _try_build_basic_pdf_fallback(
            method_tex_path=method_tex_path,
            pdf_path=pdf_path,
            figure_path=figure_ref,
            section_title=section_title,
            reason="latex_compiler_not_found",
        )
        if fallback:
            report.update(fallback)
            return report
        report["reason"] = "latex_compiler_not_found"
        return report
    report["compiler"] = tool

    cmd = _compiler_command(tool, standalone_tex)
    log_path = standalone_tex.with_suffix(".log")
    report["log_path"] = str(log_path)

    attempts = _run_compiler_with_retry(
        tool=tool,
        cmd=cmd,
        output_dir=output_dir,
        pdf_path=pdf_path,
        timeout_seconds=timeout_seconds,
    )
    report["attempt_count"] = len(attempts)
    report["attempts"] = attempts
    last_attempt = attempts[-1] if attempts else {}
    report["stdout"] = str(last_attempt.get("stdout", ""))[-4000:]
    report["stderr"] = str(last_attempt.get("stderr", ""))[-4000:]
    log_tail = _read_log_tail(log_path)
    if log_tail and not report["stderr"]:
        report["stderr"] = log_tail[-4000:]
    _materialize_compiled_pdf(standalone_tex=standalone_tex, requested_pdf=pdf_path)

    if last_attempt.get("status") == "invoke_error":
        report["status"] = "error"
        report["reason"] = f"compiler_invocation_failed:{last_attempt.get('error_type', 'unknown')}"
        return report
    if last_attempt.get("status") == "timeout":
        fallback = _try_build_basic_pdf_fallback(
            method_tex_path=method_tex_path,
            pdf_path=pdf_path,
            figure_path=figure_ref,
            section_title=section_title,
            reason=f"latex_compile_timeout:{last_attempt.get('timeout_seconds', max(30, int(timeout_seconds)))}",
        )
        if fallback:
            report.update(fallback)
            return report
        report["status"] = "error"
        report["reason"] = f"latex_compile_timeout:{last_attempt.get('timeout_seconds', max(30, int(timeout_seconds)))}"
        return report
    if int(last_attempt.get("returncode", 1)) != 0:
        fallback = _try_build_basic_pdf_fallback(
            method_tex_path=method_tex_path,
            pdf_path=pdf_path,
            figure_path=figure_ref,
            section_title=section_title,
            reason=f"latex_compile_failed:exit_{last_attempt.get('returncode', 'unknown')}",
        )
        if fallback:
            report.update(fallback)
            return report
        report["status"] = "error"
        report["reason"] = f"latex_compile_failed:exit_{last_attempt.get('returncode', 'unknown')}"
        return report
    if not pdf_path.exists():
        fallback = _try_build_basic_pdf_fallback(
            method_tex_path=method_tex_path,
            pdf_path=pdf_path,
            figure_path=figure_ref,
            section_title=section_title,
            reason="latex_compile_succeeded_but_pdf_missing",
        )
        if fallback:
            report.update(fallback)
            return report
        report["status"] = "error"
        report["reason"] = "latex_compile_succeeded_but_pdf_missing"
        return report
    report["status"] = "success"
    report["reason"] = ""
    return report


def _run_compiler_with_retry(
    *,
    tool: str,
    cmd: list[str],
    output_dir: Path,
    pdf_path: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    max_attempts = 2 if _supports_warmup_retry(tool) else 1
    base_timeout = max(60, int(timeout_seconds))
    for index in range(max_attempts):
        attempt_timeout = base_timeout if index == 0 else max(base_timeout, 300)
        attempt = _run_compiler_once(cmd=cmd, output_dir=output_dir, timeout_seconds=attempt_timeout)
        attempt["attempt_number"] = index + 1
        attempts.append(attempt)
        if attempt.get("status") == "ok" and int(attempt.get("returncode", 1)) == 0 and pdf_path.exists():
            break
        if not _should_retry_after_attempt(tool=tool, attempt=attempt, pdf_path=pdf_path, attempt_index=index):
            break
    return attempts


def _run_compiler_once(*, cmd: list[str], output_dir: Path, timeout_seconds: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(output_dir),
            check=False,
            capture_output=True,
            text=False,
            timeout=max(30, int(timeout_seconds)),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "returncode": None,
            "stdout": _decode_process_stream(exc.stdout),
            "stderr": _decode_process_stream(exc.stderr),
            "timeout_seconds": max(30, int(timeout_seconds)),
        }
    except Exception as exc:  # pragma: no cover - safety net
        return {
            "status": "invoke_error",
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error_type": exc.__class__.__name__,
            "timeout_seconds": max(30, int(timeout_seconds)),
        }
    return {
        "status": "ok",
        "returncode": proc.returncode,
        "stdout": _decode_process_stream(proc.stdout),
        "stderr": _decode_process_stream(proc.stderr),
        "timeout_seconds": max(30, int(timeout_seconds)),
    }


def _supports_warmup_retry(tool: str) -> bool:
    return Path(tool).name.lower() in {"xelatex", "pdflatex", "lualatex", "latex"}


def _should_retry_after_attempt(
    *,
    tool: str,
    attempt: dict[str, Any],
    pdf_path: Path,
    attempt_index: int,
) -> bool:
    if attempt_index > 0:
        return False
    if not _supports_warmup_retry(tool):
        return False
    if pdf_path.exists():
        return False
    status = str(attempt.get("status", ""))
    if status == "timeout":
        return True
    if status == "ok" and int(attempt.get("returncode", 1)) != 0:
        return True
    return False


def _pick_first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _materialize_figure_asset(output_dir: Path, figure_path: Path | None, *, asset_basename: str = "method_framework") -> Path | None:
    if figure_path is None or not figure_path.exists() or not figure_path.is_file():
        return None
    assets_dir = output_dir / "_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    clean_basename = _safe_asset_basename(asset_basename)
    target = assets_dir / f"{clean_basename}{figure_path.suffix.lower() or '.png'}"
    if figure_path.resolve() != target.resolve():
        shutil.copy2(figure_path, target)
    return target


def _resolve_compiler(preferred: str | None) -> str:
    preferred_normalized = str(preferred or "").strip()
    if preferred_normalized:
        resolved = shutil.which(preferred_normalized)
        return preferred_normalized if resolved else ""
    candidates: list[str] = []
    candidates.extend(["tectonic", "xelatex", "pdflatex"])
    for item in candidates:
        if item and shutil.which(item):
            return item
    return ""


def _compiler_command(compiler: str, tex_path: Path) -> list[str]:
    name = Path(compiler).name.lower()
    tex_name = tex_path.name
    if name == "tectonic":
        return [compiler, tex_name, "--keep-logs", "--keep-intermediates"]
    return [compiler, "-interaction=nonstopmode", "-halt-on-error", tex_name]


def _wrap_method_tex(
    method_body: str,
    figure_path: Path | None,
    *,
    section_title: str,
    figure_caption: str,
    extra_tex_blocks: list[str],
) -> str:
    figure_block = ""
    if figure_path is not None:
        fig = str(figure_path.relative_to(figure_path.parent.parent)).replace("\\", "/")
        caption = _escape_latex_text(figure_caption.strip() or "Overall framework of the proposed method.")
        figure_block = (
            "\n\\begin{figure}[!t]\n"
            "\\centering\n"
            f"\\includegraphics[width=0.96\\linewidth]{{{fig}}}\n"
            f"\\caption{{{caption}}}\n"
            "\\label{fig:method_framework}\n"
            "\\end{figure}\n"
        )
    extra_block = ""
    if extra_tex_blocks:
        extra_block = "\n" + "\n\n".join(block.strip() for block in extra_tex_blocks if str(block).strip()) + "\n"
    body = method_body.strip()
    has_explicit_heading = bool(re.search(r"\\(?:sub)*section\*?\{", body))
    section_block = "" if has_explicit_heading else f"\\section*{{{section_title}}}\n"
    return (
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{amsmath,amssymb}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{array}\n"
        "\\usepackage{hyperref}\n"
        "\\begin{document}\n"
        f"{figure_block}"
        f"{section_block}"
        f"{body}\n"
        f"{extra_block}"
        "\\end{document}\n"
    )


def _safe_asset_basename(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "method_framework"


def _escape_latex_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(ch, ch) for ch in value)


def _decode_process_stream(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_log_tail(log_path: Path, max_chars: int = 4000) -> str:
    if not log_path.exists():
        return ""
    try:
        return log_path.read_text(encoding="utf-8")[-max_chars:]
    except UnicodeDecodeError:
        try:
            return log_path.read_text(encoding="gbk")[-max_chars:]
        except UnicodeDecodeError:
            return log_path.read_text(encoding="utf-8", errors="replace")[-max_chars:]


def _materialize_compiled_pdf(*, standalone_tex: Path, requested_pdf: Path) -> None:
    produced_pdf = standalone_tex.with_suffix(".pdf")
    if not produced_pdf.exists():
        return
    shutil.copy2(produced_pdf, requested_pdf)


def _try_build_basic_pdf_fallback(
    *,
    method_tex_path: Path,
    pdf_path: Path,
    figure_path: Path | None,
    section_title: str,
    reason: str,
) -> dict[str, Any] | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None

    text = _plain_text_from_tex(method_tex_path.read_text(encoding="utf-8"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = ["Method content could not be rendered from LaTeX source."]

    page_width = 1654
    page_height = 2339
    margin = 110
    title_font = _load_pillow_font(ImageFont, 44)
    body_font = _load_pillow_font(ImageFont, 28)
    line_height = 42
    pages: list[Image.Image] = []

    current = Image.new("RGB", (page_width, page_height), "#ffffff")
    draw = ImageDraw.Draw(current)
    y = margin
    draw.text((margin, y), section_title, fill="#111111", font=title_font)
    y += 80

    figure_image = _load_figure_for_pdf(figure_path)
    if figure_image is not None:
        max_width = page_width - margin * 2
        scale = min(1.0, max_width / figure_image.width, 720 / max(1, figure_image.height))
        resized = figure_image.resize(
            (max(1, int(figure_image.width * scale)), max(1, int(figure_image.height * scale)))
        )
        x = (page_width - resized.width) // 2
        current.paste(resized, (x, y))
        y += resized.height + 56

    for source_line in lines:
        wrapped = _wrap_plain_text(source_line, max_chars=88)
        if not wrapped:
            wrapped = [""]
        for line in wrapped:
            if y + line_height > page_height - margin:
                pages.append(current)
                current = Image.new("RGB", (page_width, page_height), "#ffffff")
                draw = ImageDraw.Draw(current)
                y = margin
            draw.text((margin, y), line, fill="#111111", font=body_font)
            y += line_height
        y += 10

    pages.append(current)
    rgb_pages = [page.convert("RGB") for page in pages]
    try:
        rgb_pages[0].save(
            pdf_path,
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=rgb_pages[1:],
        )
    except Exception:
        return None
    return {
        "status": "degraded",
        "reason": f"pil_pdf_fallback:{reason}",
        "compiler": "pillow-fallback",
        "stdout": "",
        "stderr": "Pillow fallback is a readability preview, not a publication-quality LaTeX PDF.",
    }


def _plain_text_from_tex(text: str) -> str:
    plain = text
    plain = re.sub(r"%.*", "", plain)
    replacements = {
        r"\section{": "\n",
        r"\subsection{": "\n",
        r"\subsubsection{": "\n",
        r"\paragraph{": "\n",
        r"\item ": "- ",
        r"\\": "\n",
    }
    for source, target in replacements.items():
        plain = plain.replace(source, target)
    plain = re.sub(r"\\begin\{[^}]+\}", "\n", plain)
    plain = re.sub(r"\\end\{[^}]+\}", "\n", plain)
    plain = re.sub(r"\\[A-Za-z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", "", plain)
    plain = plain.replace("{", "").replace("}", "")
    plain = re.sub(r"\n{3,}", "\n\n", plain)
    return plain.strip()


def _load_pillow_font(image_font_module, size: int):
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return image_font_module.truetype(candidate, size)
        except Exception:
            continue
    return image_font_module.load_default()


def _wrap_plain_text(text: str, *, max_chars: int) -> list[str]:
    words = str(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _load_figure_for_pdf(figure_path: Path | None):
    if figure_path is None or not figure_path.exists():
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    if figure_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return None
    try:
        return Image.open(figure_path).convert("RGB")
    except Exception:
        return None
