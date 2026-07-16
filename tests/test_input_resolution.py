from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from code2paper.core.input_resolution import resolve_author_input
from code2paper.core.schemas import LLMConfig
from code2paper.llm.client import LLMResponse
from tests.tempdir_support import workspace_tempdir


def _write_repo(repo: Path) -> None:
    (repo / "models").mkdir(parents=True, exist_ok=True)
    (repo / "models" / "network.py").write_text(
        textwrap.dedent(
            """\
            # Core implementation anchor for the pruning method.
            # Select local and global token anchors before aggregation.
            # Keep semantically stable anchors before pruning transient tokens.
            class Network:
                def forward(self, x):
                    return x
            """
        ),
        encoding="utf-8",
    )


def _write_author_yaml(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            project_goal: "Reduce token cost for video-language modeling."
            paper_method_goal: "Explain the anchor-based pruning pipeline."
            implementation_scope: "Method-relevant files only."
            method_mainline: "Original story placeholder."
            paper_story_order:
              - "Original story placeholder"
            deemphasize_details:
              - "Legacy benchmark notes"
            latex_expression_preference: balanced
            priority_files:
              - "legacy.py"
            ignore_files: []
            module_roles: []
            pipeline_steps: []
            design_intents: []
            innovation_claims: []
            potential_mismatches: []
            """
        ),
        encoding="utf-8",
    )


class InputResolutionTests(unittest.TestCase):
    def test_input_resolution_uses_llm_to_revise_author_markers_from_yaml_and_annotations(self) -> None:
        with workspace_tempdir() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            tmp = Path(tmpdir)
            repo = tmp / "repo"
            method_root = tmp / "artifacts"
            author_yaml = tmp / "author.yaml"
            _write_repo(repo)
            _write_author_yaml(author_yaml)
            complete.return_value = LLMResponse(
                text=json.dumps(
                    {
                        "project_goal": "Reduce token cost for video-language modeling.",
                        "paper_method_goal": "Explain the anchor-based pruning pipeline.",
                        "implementation_scope": "Method-relevant files only.",
                        "method_mainline": "Anchor selection followed by token aggregation.",
                        "paper_story_order": ["Anchor selection", "Token aggregation"],
                        "deemphasize_details": ["Legacy benchmark notes"],
                        "latex_expression_preference": "balanced",
                        "priority_files": ["models/network.py"],
                        "ignore_files": [],
                        "module_roles": [
                            {
                                "path": "models/network.py",
                                "symbol": "",
                                "role": "token anchor construction",
                                "importance": "core",
                                "is_novel": True,
                                "notes": "Refined from annotations.",
                            }
                        ],
                        "pipeline_steps": [
                            {
                                "name": "anchor selection",
                                "purpose": "Select local and global token anchors before aggregation.",
                                "input": ["video tokens"],
                                "output": ["anchor tokens"],
                                "related_files": ["models/network.py"],
                                "highlight_level": "main",
                                "omit_from_main_figure": False,
                            }
                        ],
                        "design_intents": [
                            {
                                "intent": "Keep semantically stable anchors before pruning transient tokens.",
                                "rationale": "stabilize video context under token reduction",
                                "supporting_files": ["models/network.py"],
                                "supporting_functions": [],
                                "confidence": "medium",
                                "caveats": [],
                            }
                        ],
                        "innovation_claims": [],
                        "potential_mismatches": [],
                    }
                ),
                response_hash="sha256:stage1-llm",
            )

            resolved = resolve_author_input(
                intent_path=author_yaml,
                project_root=repo,
                method_root=method_root,
                core_top_k=8,
                annotation_required=False,
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
            )
            request = complete.call_args.args[1]
            payload = yaml.safe_load(resolved.effective_author_markers_path.read_text(encoding="utf-8"))

        complete.assert_called_once()
        self.assertEqual(request.prompt_template_id, "input_resolution_author_markers_v1")
        self.assertEqual(
            request.input_payload["original_author_yaml"]["paper_method_goal"],
            "Explain the anchor-based pruning pipeline.",
        )
        self.assertEqual(request.input_payload["annotation_summary"]["annotated_file_count"], 0)
        self.assertEqual(payload["method_mainline"], "Anchor selection followed by token aggregation.")
        self.assertEqual(payload["priority_files"][0], "models/network.py")
        self.assertEqual(payload["module_roles"][0]["path"], "models/network.py")
        self.assertEqual(payload["pipeline_steps"][0]["related_files"], ["models/network.py"])
        self.assertEqual(
            payload["design_intents"][0]["intent"],
            "Keep semantically stable anchors before pruning transient tokens.",
        )

    def test_input_resolution_falls_back_to_deterministic_markers_when_llm_response_is_invalid(self) -> None:
        with workspace_tempdir() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            tmp = Path(tmpdir)
            repo = tmp / "repo"
            method_root = tmp / "artifacts"
            author_yaml = tmp / "author.yaml"
            _write_repo(repo)
            _write_author_yaml(author_yaml)
            complete.return_value = LLMResponse(text='{"wrong":"shape"}', response_hash="sha256:bad-stage1")

            resolved = resolve_author_input(
                intent_path=author_yaml,
                project_root=repo,
                method_root=method_root,
                core_top_k=8,
                annotation_required=False,
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
            )
            payload = yaml.safe_load(resolved.effective_author_markers_path.read_text(encoding="utf-8"))

        complete.assert_called_once()
        self.assertEqual(payload["project_goal"], "Reduce token cost for video-language modeling.")
        self.assertEqual(payload["priority_files"][0], "models/network.py")
        self.assertEqual(payload["pipeline_steps"][0]["related_files"], ["models/network.py"])
        self.assertEqual(payload["design_intents"], [])

    def test_input_resolution_skips_llm_when_no_original_yaml_is_provided(self) -> None:
        with workspace_tempdir() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            tmp = Path(tmpdir)
            repo = tmp / "repo"
            method_root = tmp / "artifacts"
            _write_repo(repo)

            resolved = resolve_author_input(
                intent_path=None,
                project_root=repo,
                method_root=method_root,
                core_top_k=8,
                annotation_required=False,
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
            )
            payload = yaml.safe_load(resolved.effective_author_markers_path.read_text(encoding="utf-8"))

        complete.assert_not_called()
        self.assertEqual(resolved.source, "generated")
        self.assertEqual(payload["priority_files"][0], "models/network.py")
        self.assertEqual(payload["pipeline_steps"][0]["name"], "Core Step 1: Network")


if __name__ == "__main__":
    unittest.main()
