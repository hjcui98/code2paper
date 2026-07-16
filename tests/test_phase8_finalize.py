from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.core.output_names import method_output
from code2paper.pipeline.stages.finalize import write_phase8_artifacts
from tests.tempdir_support import workspace_tempdir


class Phase8FinalizeTests(unittest.TestCase):
    def test_phase6_writes_final_tex_and_report_without_compiler(self) -> None:
        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            method_root.mkdir(parents=True, exist_ok=True)
            text_tex = method_root / "text.tex"
            equations_tex = method_root / "equations.tex"
            symbols_tex = method_root / "symbols.tex"
            text_tex.write_text("\\subsection{Overview}\nThis is a grounded method section.\n", encoding="utf-8")
            equations_tex.write_text("\\begin{equation}\na=b\n\\end{equation}\n", encoding="utf-8")
            symbols_tex.write_text("\\paragraph{Tensor Roles}\ntext\n", encoding="utf-8")

            report = write_phase8_artifacts(
                method_root=method_root,
                method_tex_path=text_tex,
                figure_candidates=[],
                equations_tex_path=equations_tex,
                symbols_tex_path=symbols_tex,
                compiler=None,
                timeout_seconds=30,
            )

            final_tex = method_output(method_root, "final_tex")
            final_report = method_output(method_root, "final_pdf_report")
            manifest = method_output(method_root, "phase8_manifest")
            final_tex_exists = final_tex.exists()
            final_report_exists = final_report.exists()
            manifest_exists = manifest.exists()
            final_body = final_tex.read_text(encoding="utf-8")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertIn(report["status"], {"skipped", "degraded", "error", "success"})
        self.assertTrue(report["reason"] or report["status"] == "success")
        self.assertTrue(final_tex_exists)
        self.assertTrue(final_report_exists)
        self.assertTrue(manifest_exists)
        self.assertNotIn("\\subsection*{Code-Grounded Equations}", final_body)
        self.assertNotIn("\\subsection*{Code-Grounded Symbols}", final_body)
        self.assertEqual(manifest_payload["mode"], "final-method-package")

    def test_phase6_can_append_grounding_blocks_when_enabled(self) -> None:
        with workspace_tempdir() as tmpdir, patch.dict("os.environ", {"CODE2PAPER_PHASE6_APPEND_GROUNDING": "1"}):
            method_root = Path(tmpdir) / "paper" / "method"
            method_root.mkdir(parents=True, exist_ok=True)
            text_tex = method_root / "text.tex"
            equations_tex = method_root / "equations.tex"
            symbols_tex = method_root / "symbols.tex"
            text_tex.write_text("\\subsection{Overview}\nThis is a grounded method section.\n", encoding="utf-8")
            equations_tex.write_text("\\begin{equation}\na=b\n\\end{equation}\n", encoding="utf-8")
            symbols_tex.write_text("\\paragraph{Tensor Roles}\ntext\n", encoding="utf-8")

            write_phase8_artifacts(
                method_root=method_root,
                method_tex_path=text_tex,
                figure_candidates=[],
                equations_tex_path=equations_tex,
                symbols_tex_path=symbols_tex,
                compiler=None,
                timeout_seconds=30,
            )
            final_body = method_output(method_root, "final_tex").read_text(encoding="utf-8")

        self.assertIn("\\subsection*{Code-Grounded Equations}", final_body)
        self.assertIn("\\subsection*{Code-Grounded Symbols}", final_body)

    def test_phase8_writes_delivery_files_and_hash_bound_package_manifest(self) -> None:
        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            method_root.mkdir(parents=True, exist_ok=True)
            text_tex = method_root / "method_clean.tex"
            text_md = method_root / "method_clean.md"
            trace = method_root / "final_text_trace.json"
            text_tex.write_text("\\subsection{Overview}\nGrounded method.\n", encoding="utf-8")
            text_md.write_text("## Overview\n\nGrounded method.\n", encoding="utf-8")
            trace.write_text('{"hard_gate_passed": true}\n', encoding="utf-8")

            write_phase8_artifacts(
                method_root=method_root,
                method_tex_path=text_tex,
                figure_candidates=[],
                method_markdown_path=text_md,
                lineage_artifacts={"final_text_trace": trace},
                compiler=None,
                timeout_seconds=30,
            )

            finalize_manifest = json.loads(method_output(method_root, "finalize_manifest").read_text(encoding="utf-8"))
            package_manifest = json.loads(method_output(method_root, "package_manifest").read_text(encoding="utf-8"))

        self.assertEqual(package_manifest, finalize_manifest)
        self.assertEqual(package_manifest["schema_version"], "2.0")
        self.assertTrue(package_manifest["lineage_complete"])
        self.assertTrue(package_manifest["lineage"]["source_text_tex"]["hash"])
        self.assertTrue(package_manifest["lineage"]["final_text_trace"]["hash"])
        self.assertTrue(package_manifest["outputs"]["method_md"]["hash"])
        self.assertTrue(package_manifest["outputs"]["method_tex"]["hash"])


if __name__ == "__main__":
    unittest.main()
