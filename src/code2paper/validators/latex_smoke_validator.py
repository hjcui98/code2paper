"""LaTeX smoke validator."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
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
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "method_smoke.tex"
        tex_path.write_text(document, encoding="utf-8")
        try:
            result = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=tmpdir,
                text=True,
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


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]
