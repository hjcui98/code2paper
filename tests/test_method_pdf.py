from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.rendering.method_pdf import build_method_section_pdf
from tests.tempdir_support import workspace_tempdir


class MethodPdfTests(unittest.TestCase):
    def test_build_method_section_pdf_falls_back_without_latex_compiler(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            method_tex = root / "text.tex"
            method_tex.write_text(
                "\\subsection{Overview}\nThis method has two stages.\n\\begin{itemize}\n\\item Stage A\n\\item Stage B\n\\end{itemize}\n",
                encoding="utf-8",
            )
            report = build_method_section_pdf(
                method_tex_path=method_tex,
                output_dir=root,
                figure_candidates=[],
                compiler="definitely_missing_compiler",
                timeout_seconds=30,
            )

            pdf_path = root / "text.pdf"
            standalone_path = root / "text.standalone.tex"
            pdf_exists = pdf_path.exists()
            standalone_exists = standalone_path.exists()

        self.assertTrue(pdf_exists)
        self.assertTrue(standalone_exists)
        self.assertEqual(report["status"], "degraded")
        self.assertIn("pil_pdf_fallback", report["reason"])

    def test_build_method_section_pdf_retries_after_first_timeout(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            method_tex = root / "text.tex"
            method_tex.write_text("\\subsection{Overview}\nRetry should succeed.\n", encoding="utf-8")

            calls: list[int] = []

            def fake_run(cmd, cwd, check, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                calls.append(int(timeout))
                if len(calls) == 1:
                    raise TimeoutErrorLike(timeout=timeout)
                pdf_path = Path(cwd) / "text.pdf"
                pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")
                return FakeCompletedProcess(returncode=0, stdout=b"ok", stderr=b"")

            with (
                patch("code2paper.rendering.method_pdf.shutil.which", return_value="xelatex"),
                patch("code2paper.rendering.method_pdf.subprocess.run", side_effect=fake_run),
            ):
                report = build_method_section_pdf(
                    method_tex_path=method_tex,
                    output_dir=root,
                    figure_candidates=[],
                    compiler="xelatex",
                    timeout_seconds=30,
                )

            self.assertEqual(report["status"], "success")
            self.assertEqual(report["reason"], "")
            self.assertEqual(report["attempt_count"], 2)
            self.assertEqual(len(report["attempts"]), 2)
            self.assertEqual(report["attempts"][0]["status"], "timeout")
            self.assertEqual(report["attempts"][1]["status"], "ok")
            self.assertTrue((root / "text.pdf").exists())

    def test_build_method_section_pdf_copies_standalone_pdf_to_requested_path(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir)
            method_tex = root / "text.tex"
            method_tex.write_text("\\subsection{Overview}\nCompiled PDF should be materialized.\n", encoding="utf-8")

            def fake_run(cmd, cwd, check, capture_output, text, timeout):  # type: ignore[no-untyped-def]
                standalone_pdf = Path(cwd) / "text.standalone.pdf"
                standalone_pdf.write_bytes(b"%PDF-1.4\n%mock-standalone\n")
                return FakeCompletedProcess(returncode=0, stdout=b"ok", stderr=b"")

            with (
                patch("code2paper.rendering.method_pdf.shutil.which", return_value="xelatex"),
                patch("code2paper.rendering.method_pdf.subprocess.run", side_effect=fake_run),
            ):
                report = build_method_section_pdf(
                    method_tex_path=method_tex,
                    output_dir=root,
                    figure_candidates=[],
                    compiler="xelatex",
                    timeout_seconds=30,
                )

            self.assertEqual(report["status"], "success")
            self.assertEqual(report["reason"], "")
            self.assertTrue((root / "text.pdf").exists())


class FakeCompletedProcess:
    def __init__(self, *, returncode: int, stdout: bytes, stderr: bytes) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TimeoutErrorLike(subprocess.TimeoutExpired):
    def __init__(self, *, timeout: int) -> None:
        super().__init__(cmd=["xelatex"], timeout=timeout, output=b"", stderr=b"")


if __name__ == "__main__":
    unittest.main()
