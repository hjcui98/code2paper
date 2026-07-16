"""LaTeX smoke validator."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path


def validate_latex_smoke(latex: str) -> dict:
    engine = shutil.which("pdflatex")
    if not engine:
        return {
            "passed": False,
            "status": "unavailable",
            "engine": "pdflatex",
            "issues": [
                {
                    "issue_id": "LATEX1",
                    "category": "engine_unavailable",
                    "message": "pdflatex was not found on PATH; compile smoke was not run.",
                }
            ],
        }

    document = "\n".join(
        [
            r"\documentclass{article}",
            r"\usepackage{amsmath}",
            r"\begin{document}",
            latex,
            r"\end{document}",
            "",
        ]
    )
    with _temporary_directory() as tmpdir:
        tex_path = Path(tmpdir) / "method_smoke.tex"
        tex_path.write_text(document, encoding="utf-8")
        try:
            result = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=tmpdir,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "status": "failed",
                "engine": "pdflatex",
                "issues": [
                    {
                        "issue_id": "LATEX1",
                        "category": "compile_timeout",
                        "message": "pdflatex did not finish within 20 seconds.",
                    }
                ],
            }

    if result.returncode == 0:
        return {"passed": True, "status": "compiled", "engine": "pdflatex", "issues": []}
    return {
        "passed": False,
        "status": "failed",
        "engine": "pdflatex",
        "issues": [
            {
                "issue_id": "LATEX1",
                "category": "compile_failed",
                "message": _tail(result.stdout, 4000),
            }
        ],
    }


def _tail(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[-limit:]


@contextmanager
def _temporary_directory():
    root = _resolve_temp_root()
    if root is not None:
        path = root / f"latex-smoke-{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=False)
        try:
            yield str(path)
        finally:
            shutil.rmtree(path, ignore_errors=True)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _resolve_temp_root() -> Path | None:
    configured_root = os.environ.get("CODE2PAPER_TMPDIR", "").strip()
    candidates = [Path(configured_root)] if configured_root else []
    candidates.extend(
        [
            Path.cwd() / ".tmp" / "latex_smoke",
            Path(tempfile.gettempdir()) / "code2paper_latex_smoke",
        ]
    )
    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
            probe_dir = root / f".probe-{uuid.uuid4().hex}"
            probe_dir.mkdir()
            probe_file = probe_dir / "write_test.txt"
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink()
            probe_dir.rmdir()
            return root
        except OSError:
            continue
    return None
