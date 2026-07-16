from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path

import yaml

from code2paper.cli.prepare import run_prepare
from code2paper.core.output_names import method_output
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TOY_TRAIN_PROJECT = FIXTURES / "toy_train_project"


class PrepareCliTests(unittest.TestCase):
    def test_prepare_writes_seed_refined_and_bootstrap_outputs(self) -> None:
        with workspace_tempdir() as tmpdir:
            tmp = Path(tmpdir)
            draft_path = tmp / "draft.yaml"
            draft_path.write_text(
                textwrap.dedent(
                    """\
                    project_goal: "Train a toy model from config-driven inputs."
                    paper_method_goal: "Describe the toy training flow."
                    key_building_blocks:
                      - name: "trainer"
                        role: "training entrypoint"
                    pipeline_steps:
                      - name: "Resolve config"
                        purpose: "Read training settings and prepare execution."
                      - name: "Run training"
                        purpose: "Launch the toy training routine."
                    """
                ),
                encoding="utf-8",
            )

            result = run_prepare(
                project_root=TOY_TRAIN_PROJECT,
                draft_path=draft_path,
                out_root=tmp / "out",
                project_id="toy_train_project",
                core_top_k=12,
                llm_provider=None,
                llm_model=None,
            )

            self.assertEqual(result["exit_code"], 0)
            coarse = tmp / "out" / "paper" / "method" / "author_markers.coarse.yaml"
            refined = tmp / "out" / "paper" / "method" / "author_markers.story_first.generated.yaml"
            report = tmp / "out" / "paper" / "method" / "prepare_report.json"
            bootstrap_phase1 = method_output(tmp / "out" / "draft_markers_bootstrap" / "paper" / "method", "phase1_manifest")
            bootstrap_phase2 = method_output(tmp / "out" / "draft_markers_bootstrap" / "paper" / "method", "phase2_manifest")

            self.assertTrue(coarse.exists(), coarse)
            self.assertTrue(refined.exists(), refined)
            self.assertTrue(report.exists(), report)
            self.assertTrue(bootstrap_phase1.exists(), bootstrap_phase1)
            self.assertTrue(bootstrap_phase2.exists(), bootstrap_phase2)

            refined_payload = yaml.safe_load(refined.read_text(encoding="utf-8"))
            self.assertTrue(refined_payload["priority_files"])
            self.assertTrue(refined_payload["module_roles"])
            report_payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(report_payload["exit_code"], 0)
            self.assertTrue(report_payload["bootstrap"]["phase1_manifest"])
            self.assertTrue(report_payload["bootstrap"]["phase2_manifest"])

    def test_prepare_runs_without_code_marks(self) -> None:
        with workspace_tempdir() as tmpdir:
            tmp = Path(tmpdir)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "train.py").write_text(
                "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )
            draft_path = tmp / "draft.yaml"
            draft_path.write_text("project_goal: 'goal'\n", encoding="utf-8")

            result = run_prepare(
                project_root=repo,
                draft_path=draft_path,
                out_root=tmp / "out",
                project_id="repo",
                core_top_k=12,
                llm_provider=None,
                llm_model=None,
            )

            self.assertEqual(result["exit_code"], 0)
            self.assertTrue((tmp / "out" / "paper" / "method" / "author_markers.coarse.yaml").exists())
            self.assertTrue((tmp / "out" / "paper" / "method" / "author_markers.story_first.generated.yaml").exists())

    def test_prepare_continues_when_annotations_are_missing_by_default(self) -> None:
        with workspace_tempdir() as tmpdir:
            tmp = Path(tmpdir)
            repo = tmp / "repo"
            repo.mkdir()
            (repo / "train.py").write_text(
                "def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n",
                encoding="utf-8",
            )
            draft_path = tmp / "draft.yaml"
            draft_path.write_text("project_goal: 'goal'\n", encoding="utf-8")

            result = run_prepare(
                project_root=repo,
                draft_path=draft_path,
                out_root=tmp / "out",
                project_id="repo",
                core_top_k=12,
                llm_provider=None,
                llm_model=None,
            )

            self.assertEqual(result["exit_code"], 0)
            self.assertTrue((tmp / "out" / "paper" / "method" / "author_markers.story_first.generated.yaml").exists())


if __name__ == "__main__":
    unittest.main()
