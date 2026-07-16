from __future__ import annotations

import unittest

from code2paper.agents.utils.code_ir_builder import build_code_facts


class CodeIrBuilderScanFirstTests(unittest.TestCase):
    def test_build_code_facts_recovers_agent_modules_when_author_alignment_is_empty(self) -> None:
        # Given: an orchestration snippet with explicit agent imports and constructor injection.
        core_snippets = {
            "snippets": [
                {
                    "snippet_id": "sn-main",
                    "role": "training_loop",
                    "source": {"path": "main.py", "symbol": "main"},
                    "text": """
from agents.planner_agent import PlannerAgent
from agents.visualizer_agent import VisualizerAgent
from agents.critic_agent import CriticAgent
from utils.paperviz_processor import PaperVizProcessor

async def main():
    processor = PaperVizProcessor(
        planner_agent=PlannerAgent(exp_config=exp_config),
        visualizer_agent=VisualizerAgent(exp_config=exp_config),
        critic_agent=CriticAgent(exp_config=exp_config),
    )
    async for result in processor.process_queries_batch(data_list, max_concurrent=10):
        yield result
""",
                }
            ]
        }

        # When: the project has no author-supplied module or pipeline alignment.
        facts = build_code_facts(
            core_snippets,
            {"modules": [], "pipeline_steps": [], "losses": [], "coverage_report": {"overall_score": 0}},
            {},
            {"method": {}},
            [],
        )

        # Then: scan-first analysis still promotes code-backed agent modules and flow.
        module_names = {module["name"] for module in facts["modules"]}
        self.assertIn("PlannerAgent", module_names)
        self.assertIn("VisualizerAgent", module_names)
        self.assertIn("CriticAgent", module_names)
        self.assertIn("PaperVizProcessor", module_names)
        planner_module = next(module for module in facts["modules"] if module["name"] == "PlannerAgent")
        self.assertNotIn("implementation evidence", planner_module["key_logic"])
        self.assertNotIn("main.py", planner_module["key_logic"])
        self.assertGreaterEqual(len(facts["pipeline_steps"]), 1)
        self.assertIn("PlannerAgent", facts["pipeline_steps"][0]["involved_modules"])

    def test_build_code_facts_prefers_agent_class_evidence_over_import_mention(self) -> None:
        core_snippets = {
            "snippets": [
                {
                    "snippet_id": "sn-main",
                    "role": "training_loop",
                    "source": {"path": "main.py", "symbol": "main"},
                    "text": "from agents.planner_agent import PlannerAgent\n\nagent = PlannerAgent()\n",
                },
                {
                    "snippet_id": "sn-class",
                    "role": "method_agent",
                    "source": {"path": "agents/planner_agent.py", "symbol": "PlannerAgent"},
                    "text": (
                        "class PlannerAgent:\n"
                        "    def process(self, paper_text):\n"
                        "        return {'plan': paper_text}\n"
                    ),
                },
            ]
        }

        facts = build_code_facts(
            core_snippets,
            {"modules": [], "pipeline_steps": [], "losses": [], "coverage_report": {"overall_score": 0}},
            {},
            {"method": {}},
            [],
        )

        planner_module = next(module for module in facts["modules"] if module["name"] == "PlannerAgent")
        self.assertEqual(planner_module["evidence_refs"], ["sn-class"])

    def test_build_code_facts_orders_agents_by_orchestrator_mentions(self) -> None:
        core_snippets = {
            "snippets": [
                {
                    "snippet_id": "sn-critic-class",
                    "role": "method_agent",
                    "source": {"path": "agents/critic_agent.py", "symbol": "CriticAgent"},
                    "text": "class CriticAgent:\n    def process(self, plan):\n        return plan\n",
                },
                {
                    "snippet_id": "sn-main",
                    "role": "training_loop",
                    "source": {"path": "main.py", "symbol": "main"},
                    "text": (
                        "from agents.planner_agent import PlannerAgent\n"
                        "from agents.visualizer_agent import VisualizerAgent\n"
                        "from agents.critic_agent import CriticAgent\n\n"
                        "processor = PaperVizProcessor(\n"
                        "    planner_agent=PlannerAgent(),\n"
                        "    visualizer_agent=VisualizerAgent(),\n"
                        "    critic_agent=CriticAgent(),\n"
                        ")\n"
                    ),
                },
                {
                    "snippet_id": "sn-planner-class",
                    "role": "method_agent",
                    "source": {"path": "agents/planner_agent.py", "symbol": "PlannerAgent"},
                    "text": "class PlannerAgent:\n    def process(self, paper):\n        return {'plan': paper}\n",
                },
                {
                    "snippet_id": "sn-visualizer-class",
                    "role": "method_agent",
                    "source": {"path": "agents/visualizer_agent.py", "symbol": "VisualizerAgent"},
                    "text": "class VisualizerAgent:\n    def process(self, plan):\n        return {'image': plan}\n",
                },
            ]
        }

        facts = build_code_facts(
            core_snippets,
            {"modules": [], "pipeline_steps": [], "losses": [], "coverage_report": {"overall_score": 0}},
            {},
            {"method": {}},
            [],
        )

        self.assertEqual(
            [step["involved_modules"][0] for step in facts["pipeline_steps"][:3]],
            ["PlannerAgent", "VisualizerAgent", "CriticAgent"],
        )


if __name__ == "__main__":
    unittest.main()
