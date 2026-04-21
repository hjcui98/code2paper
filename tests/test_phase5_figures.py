from __future__ import annotations

import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from code2paper.figures.backend_fallback import generate_fallback_figure
from code2paper.figures.backend_paperbanana import PaperBananaBackendError, generate_paperbanana_figure, _parse_generated_paths
from code2paper.figures.method_draft_adapter import build_paperbanana_figure_brief, clean_method_draft, clean_tex_to_plain_text


class Phase5FigureTests(unittest.TestCase):
    def test_method_draft_adapter_strips_audit_comments(self) -> None:
        draft = textwrap.dedent(
            """\
            # Method

            <!-- c2p: stage=S1; mechanisms=MECH1; evidence=E1; confidence=high -->
            ## Evidence-Grounded Pipeline
            The method aligns code evidence with method stages.
            """
        )

        clean = clean_method_draft(draft)
        brief = build_paperbanana_figure_brief(draft)

        self.assertNotIn("<!-- c2p:", clean)
        self.assertIn("Evidence-Grounded Pipeline", brief)
        self.assertIn("Create a paper-ready method overview figure", brief)
        self.assertIn("Do not add claims", brief)

    def test_tex_to_plain_text_removes_latex_noise(self) -> None:
        draft = textwrap.dedent(
            r"""\
            \section{Method}\label{sec:method}
            The \textbf{projector} maps \texttt{point\_tokens} into $h_{LLM}$.
            % c2p: hidden audit marker
            """
        )

        clean = clean_tex_to_plain_text(draft)

        self.assertIn("Method", clean)
        self.assertIn("projector", clean)
        self.assertIn("point_tokens", clean)
        self.assertNotIn("\\section", clean)
        self.assertNotIn("\\label", clean)
        self.assertNotIn("c2p:", clean)

    def test_fallback_backend_generates_svg_and_meta(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            draft_path = tmp / "method_draft.md"
            draft_path.write_text(
                "# Method\n\n## Ingestion\nText.\n\n## Alignment\nText.\n\n## Writing\nText.\n",
                encoding="utf-8",
            )

            meta = generate_fallback_figure(draft_path, out_dir=tmp / "figures")

            self.assertEqual(meta["backend"], "fallback")
            self.assertEqual(meta["outputs"]["svg"], str(tmp / "figures" / "method_overview.svg"))
            self.assertTrue((tmp / "figures" / "method_overview.svg").exists())
            self.assertTrue((tmp / "figures" / "method_overview.meta.json").exists())
            self.assertEqual(meta["nodes"][:3], ["Ingestion", "Alignment", "Writing"])

    def test_paperbanana_backend_accepts_method_draft_with_fake_local_backend(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paperbanana_root = tmp / "PaperBanana"
            _write_fake_paperbanana(paperbanana_root)

            draft_path = tmp / "method_draft.md"
            draft_path.write_text("# Method\n\n## Stage A\nText.\n", encoding="utf-8")

            meta = generate_paperbanana_figure(
                draft_path=draft_path,
                out_dir=tmp / "figures",
                paperbanana_root=paperbanana_root,
                chat_api_url="http://example.invalid/v1",
                api_key="test-key",
                model="test-model",
                image_model="test-image-model",
                clean_tex_to_txt=True,
            )

            self.assertEqual(meta["backend"], "paperbanana")
            self.assertTrue((tmp / "figures" / "method_overview.png").exists())
            self.assertEqual(
                meta["input"]["content_file"],
                str(tmp / "figures" / "method_overview.paperbanana_input.txt"),
            )
            self.assertTrue((tmp / "figures" / "method_overview.paperbanana_input.txt").exists())
            self.assertTrue((tmp / "figures" / "method_overview.meta.json").exists())
            self.assertIn("fake paperbanana", meta["paperbanana"]["stdout"])

    def test_parse_generated_paths_ignores_long_non_path_logs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            expected = tmp / "method_overview.png"
            expected.write_bytes(b"png")
            long_log_line = "AIHubMix retry: " + ("x" * 5000)

            paths = _parse_generated_paths(long_log_line, expected)

            self.assertEqual(paths, [expected.resolve()])

    def test_paperbanana_backend_fails_when_no_output_is_created(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paperbanana_root = tmp / "PaperBanana"
            _write_fake_paperbanana_without_output(paperbanana_root)
            draft_path = tmp / "method_draft.md"
            draft_path.write_text("# Method\n\nText.\n", encoding="utf-8")
            figures_dir = tmp / "figures"
            figures_dir.mkdir()
            stale_output = figures_dir / "method_overview.png"
            stale_output.write_bytes(b"stale")

            with self.assertRaises(PaperBananaBackendError) as ctx:
                generate_paperbanana_figure(
                    draft_path=draft_path,
                    out_dir=figures_dir,
                    paperbanana_root=paperbanana_root,
                )

            self.assertIn("without producing", str(ctx.exception))
            self.assertFalse(stale_output.exists())

    def test_api_key_uses_paperbanana_config_model_provider(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paperbanana_root = tmp / "PaperBanana"
            _write_fake_paperbanana(paperbanana_root, print_env_key="AIHUBMIX_API_KEY")
            (paperbanana_root / "configs").mkdir()
            (paperbanana_root / "configs" / "model_config.yaml").write_text(
                'defaults:\n  main_model_name: "aihubmix/kimi-k2.5"\n',
                encoding="utf-8",
            )
            draft_path = tmp / "method_draft.md"
            draft_path.write_text("# Method\n\nText.\n", encoding="utf-8")

            meta = generate_paperbanana_figure(
                draft_path=draft_path,
                out_dir=tmp / "figures",
                paperbanana_root=paperbanana_root,
                api_key="test-key",
            )

            self.assertIn("AIHUBMIX_API_KEY=set", meta["paperbanana"]["stdout"])

    def test_paperbanana_success_with_retrieval_failures_is_warned(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paperbanana_root = tmp / "PaperBanana"
            _write_fake_paperbanana_with_retrieval_failure_logs(paperbanana_root)
            draft_path = tmp / "method_draft.md"
            draft_path.write_text("# Method\n\nText.\n", encoding="utf-8")

            meta = generate_paperbanana_figure(
                draft_path=draft_path,
                out_dir=tmp / "figures",
                paperbanana_root=paperbanana_root,
                retrieval_setting="auto",
            )

            self.assertEqual(meta["status"], "success_with_warnings")
            self.assertTrue(meta["warnings"])
            self.assertTrue(any("0 references" in warning for warning in meta["warnings"]))


def _write_fake_paperbanana(root: Path, *, print_env_key: str = "") -> None:
    (root / "skill").mkdir(parents=True)
    (root / "requirements.txt").write_text("pillow\n", encoding="utf-8")
    (root / "skill" / "run.py").write_text(
        textwrap.dedent(
            f"""\
            import os
            from pathlib import Path

            async def run(args):
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"fakepng")
                print("fake paperbanana")
                if {print_env_key!r}:
                    print(f"{print_env_key}=set" if os.environ.get({print_env_key!r}) else f"{print_env_key}=missing")
                print(output)
            """
        ),
        encoding="utf-8",
    )


def _write_fake_paperbanana_without_output(root: Path) -> None:
    (root / "skill").mkdir(parents=True)
    (root / "requirements.txt").write_text("pillow\n", encoding="utf-8")
    (root / "skill" / "run.py").write_text(
        textwrap.dedent(
            """\
            async def run(args):
                print("fake paperbanana without output")
            """
        ),
        encoding="utf-8",
    )


def _write_fake_paperbanana_with_retrieval_failure_logs(root: Path) -> None:
    (root / "skill").mkdir(parents=True)
    (root / "requirements.txt").write_text("pillow\n", encoding="utf-8")
    (root / "skill" / "run.py").write_text(
        textwrap.dedent(
            """\
            from pathlib import Path

            async def run(args):
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"fakepng")
                print("AIHubMix attempt 1 failed: error code: 400")
                print("Error: All 5 AIHubMix attempts failed.")
                print("Warning: Failed to parse retrieval result: 'str' object has no attribute 'get'")
                print("[Retriever] Done. Retrieved 0 references.")
                print(output)
            """
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
