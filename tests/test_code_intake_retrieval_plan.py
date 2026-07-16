from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.agents.code_intake import CodeIntakeAgent
from code2paper.agents.langgraph_utils import AgentResponse, LangGraphAgent, extract_json
from code2paper.agents.state.poster_state import create_state
from tests.tempdir_support import workspace_tempdir


class CodeIntakeRetrievalPlanTests(unittest.TestCase):
    def test_code_intake_keeps_orchestrator_imported_agent_class_snippets(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir) / "repo"
            agents_dir = root / "agents"
            agents_dir.mkdir(parents=True)
            (root / "main.py").write_text(
                "from agents.planner_agent import PlannerAgent\n\n"
                "def main():\n"
                "    agent = PlannerAgent()\n"
                "    return agent.process('paper text')\n",
                encoding="utf-8",
            )
            (agents_dir / "planner_agent.py").write_text(
                "class PlannerAgent:\n"
                "    def process(self, paper_text):\n"
                "        plan = {'task': 'diagram', 'source': paper_text}\n"
                "        return plan\n",
                encoding="utf-8",
            )
            out = Path(tmpdir) / "out"
            state = create_state(
                pdf_path=str(root / "author.yaml"),
                text_model="kimi-k2.5",
                vision_model="kimi-k2.5",
                output_dir=str(out),
                text_provider="openai",
                vision_provider="openai",
            )
            state["repo_path"] = str(root)
            state["method_experiment_structured_summary"] = {
                "method": {
                    "name": "Agent orchestration",
                    "pipeline_steps": [
                        {"name": "Planning", "purpose": "PlannerAgent builds a diagram plan."}
                    ],
                },
                "retrieval_hints": {
                    "priority_paths": ["main.py", "agents/planner_agent.py"],
                    "symbol_targets": [],
                },
            }
            state["structured_sections"] = {}
            state["paper_objects"] = {}
            state["enable_code_intake_llm_retrieval_planning"] = False
            state["enable_code_intake_llm_review"] = False
            state["config"] = {
                "code_intake": {
                    "snippet_budget": {
                        "max_total_snippet_lines": 80,
                        "max_single_snippet_lines": 40,
                        "top_k_per_role": 4,
                    },
                    "llm_review": {"max_iterations": 0},
                    "method_alignment": {"min_coverage_score": 0.0, "auto_rescan": False},
                }
            }

            state = CodeIntakeAgent()(state)

            self.assertFalse(state.get("errors"))
            snippets = state["core_snippets"]["snippets"]
            self.assertTrue(
                any(
                    sn.get("role") == "method_agent"
                    and sn.get("source", {}).get("path", "").endswith("agents/planner_agent.py")
                    and "class PlannerAgent" in sn.get("text", "")
                    for sn in snippets
                )
            )

    def test_code_intake_promotes_orchestrator_imports_to_symbol_targets_under_tight_budget(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir) / "repo"
            agents_dir = root / "agents"
            agents_dir.mkdir(parents=True)
            (root / "main.py").write_text(
                "from agents.planner_agent import PlannerAgent\n\n"
                "def main():\n"
                "    agent = PlannerAgent()\n"
                "    return agent.process('paper text')\n",
                encoding="utf-8",
            )
            (agents_dir / "planner_agent.py").write_text(
                "class PlannerAgent:\n"
                "    def process(self, paper_text):\n"
                "        plan = {'task': 'diagram', 'source': paper_text}\n"
                "        return plan\n",
                encoding="utf-8",
            )
            out = Path(tmpdir) / "out"
            state = create_state(
                pdf_path=str(root / "author.yaml"),
                text_model="kimi-k2.5",
                vision_model="kimi-k2.5",
                output_dir=str(out),
                text_provider="openai",
                vision_provider="openai",
            )
            state["repo_path"] = str(root)
            state["method_experiment_structured_summary"] = {
                "method": {
                    "name": "Agent orchestration",
                    "pipeline_steps": [
                        {"name": "Planning", "purpose": "PlannerAgent builds a diagram plan."}
                    ],
                },
                "retrieval_hints": {
                    "priority_paths": ["main.py"],
                    "symbol_targets": [],
                },
            }
            state["structured_sections"] = {}
            state["paper_objects"] = {}
            state["enable_code_intake_llm_retrieval_planning"] = False
            state["enable_code_intake_llm_review"] = False
            state["config"] = {
                "code_intake": {
                    "snippet_budget": {
                        "max_total_snippet_lines": 4,
                        "max_single_snippet_lines": 40,
                        "top_k_per_role": 4,
                    },
                    "llm_review": {"max_iterations": 0},
                    "method_alignment": {"min_coverage_score": 0.0, "auto_rescan": False},
                }
            }

            state = CodeIntakeAgent()(state)

            self.assertFalse(state.get("errors"))
            report = state["code_intake_report"]["author_guided_retrieval"]
            self.assertEqual(report["orchestrator_symbol_targets_added"], 1)
            snippets = state["core_snippets"]["snippets"]
            self.assertTrue(
                any(
                    sn.get("role") == "method_agent"
                    and sn.get("source", {}).get("symbol") == "PlannerAgent"
                    and "class PlannerAgent" in sn.get("text", "")
                    for sn in snippets
                )
            )

    def test_llm_retrieval_plan_drives_supplemental_symbol_extraction(self) -> None:
        with workspace_tempdir() as tmpdir:
            root = Path(tmpdir) / "repo"
            root.mkdir()
            (root / "main.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
            (root / "special_model.py").write_text(
                "class SpecialModel:\n"
                "    def forward(self, points):\n"
                "        projected = points\n"
                "        return projected\n",
                encoding="utf-8",
            )
            out = Path(tmpdir) / "out"
            state = create_state(
                pdf_path=str(root / "author.yaml"),
                text_model="kimi-k2.5",
                vision_model="kimi-k2.5",
                output_dir=str(out),
                text_provider="openai",
                vision_provider="openai",
            )
            state["repo_path"] = str(root)
            state["method_experiment_structured_summary"] = {
                "meta": {"version": "story-first-method-summary-v2"},
                "method": {
                    "name": "Special point projection",
                    "pipeline_steps": [
                        {"name": "Point projection", "purpose": "verify SpecialModel.forward"}
                    ],
                },
                "retrieval_hints": {
                    "priority_paths": [],
                    "claim_support_files": [],
                    "negative_globs": [],
                    "symbol_targets": [],
                },
            }
            state["structured_sections"] = {}
            state["paper_objects"] = {}
            state["enable_code_intake_llm_retrieval_planning"] = True
            state["enable_code_intake_llm_review"] = False
            state["config"] = {
                "code_intake": {
                    "snippet_budget": {
                        "max_total_snippet_lines": 200,
                        "max_single_snippet_lines": 80,
                        "top_k_per_role": 8,
                    },
                    "llm_retrieval_planning": {"enabled": True},
                    "llm_review": {"max_iterations": 0},
                    "method_alignment": {"min_coverage_score": 0.0, "auto_rescan": False},
                }
            }

            plan = {
                "status": "ok",
                "priority_files": ["special_model.py"],
                "claim_support_files": [],
                "ignore_files": [],
                "symbol_targets": [
                    {
                        "path": "special_model.py",
                        "symbol": "SpecialModel.forward",
                        "role": "model_arch",
                        "reason": "verifies point projection behavior",
                    }
                ],
                "search_keywords": ["SpecialModel", "projected"],
                "role_keywords": {"model_arch": ["SpecialModel", "projected"]},
                "rationale": "Use author purpose to retrieve the implementation symbol.",
            }

            with patch.object(
                LangGraphAgent,
                "step",
                return_value=AgentResponse(json.dumps(plan), input_tokens=10, output_tokens=12),
            ):
                state = CodeIntakeAgent()(state)

            self.assertFalse(state.get("errors"))
            report = state["code_intake_report"]
            self.assertTrue(report["llm_retrieval_planning"]["llm_used"])
            self.assertEqual(report["llm_retrieval_planning"]["symbol_targets_added"], 1)
            snippets = state["core_snippets"]["snippets"]
            self.assertTrue(
                any(
                    sn.get("source", {}).get("symbol") == "SpecialModel.forward"
                    and "projected = points" in sn.get("text", "")
                    for sn in snippets
                )
            )

    def test_extract_json_repairs_common_missing_comma_response(self) -> None:
        repaired = extract_json(
            """
            ```json
            {
              "status": "ok",
              "priority_files": ["special_model.py"]
              "symbol_targets": [
                {"path": "special_model.py", "symbol": "SpecialModel.forward"}
              ]
            }
            ```
            """
        )

        self.assertEqual(repaired["status"], "ok")
        self.assertEqual(repaired["priority_files"], ["special_model.py"])


if __name__ == "__main__":
    unittest.main()
