from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from code2paper.core.output_paths import default_out_root, intent_output_name, repo_output_name, resolve_project_id


class OutputPathsTests(unittest.TestCase):
    def test_repo_output_name_normalizes_non_ascii_and_spaces(self) -> None:
        name = repo_output_name(Path("D:/tmp/My Repo 测试"))
        self.assertEqual(name, "My_Repo")

    def test_default_out_root_uses_outputs_repo_name_and_timestamp(self) -> None:
        out_root = default_out_root(
            Path("D:/tmp/toy_train_project"),
            base_dir=Path("D:/workspace"),
            now=datetime(2026, 4, 25, 9, 30, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(out_root, Path("D:/workspace/outputs/toy_train_project_20260425_093045"))

    def test_intent_output_name_uses_yaml_filename_slug(self) -> None:
        slug = intent_output_name("3DGen-R1 - Are We Ready for RL in Text-to-3D Generation - .yaml")
        self.assertEqual(slug, "3DGen-R1_Are_We_Ready_for_RL_in_Text-to-3D_Generation")

    def test_default_out_root_prefers_intent_yaml_slug_when_present(self) -> None:
        out_root = default_out_root(
            Path("D:/tmp/toy_train_project"),
            intent_path="3DGen-R1 - Are We Ready for RL in Text-to-3D Generation - .yaml",
            base_dir=Path("D:/workspace"),
            now=datetime(2026, 4, 25, 9, 30, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(
            out_root,
            Path("D:/workspace/outputs/3DGen-R1_Are_We_Ready_for_RL_in_Text-to-3D_Generation_20260425_093045"),
        )

    def test_resolve_project_id_prefers_intent_yaml_slug_when_project_id_missing(self) -> None:
        project_id = resolve_project_id(
            "",
            project_root=Path("D:/tmp/toy_train_project"),
            intent_path="3DGen-R1 - Are We Ready for RL in Text-to-3D Generation - .yaml",
        )
        self.assertEqual(project_id, "3DGen-R1_Are_We_Ready_for_RL_in_Text-to-3D_Generation")


if __name__ == "__main__":
    unittest.main()
