from __future__ import annotations

import unittest
from types import SimpleNamespace

from code2paper.pipeline.stages.analysis import _build_analysis_repair_tasks, _merge_alignment_with_scan_outputs
from code2paper.core.schemas import CodeAlignmentIR, CodeMethodAnalysis, RawEvidencePack


class Phase2ScanFirstAlignmentTests(unittest.TestCase):
    def test_analysis_repair_tasks_bind_claim_candidates_to_existing_evidence(self) -> None:
        focus = {
            "mode": "evidence-repair-focus",
            "focus_claim_ids": ["C2"],
            "missing_evidence_claim_ids": ["C2"],
            "priority_paths": ["src/encoder.py"],
            "symbol_targets": [{"claim_id": "C2", "path": "src/encoder.py", "symbol": "Encoder.forward"}],
            "claim_targets": [
                {
                    "claim_id": "C2",
                    "claim_query": "C2: encoder forward behavior",
                    "candidates": [
                        {
                            "path": "src/encoder.py",
                            "symbol": "Encoder.forward",
                            "kind": "function",
                            "start_line": 10,
                            "end_line": 20,
                            "score": 2.5,
                            "reasons": ["claim_token:encoder"],
                        }
                    ],
                }
            ],
            "recommended_actions": ["retrieve_missing_evidence_ids_for_focus_claims"],
        }
        core_snippets = {
            "snippets": [
                {
                    "snippet_id": "S1",
                    "source": {
                        "path": "src/encoder.py",
                        "symbol": "Encoder.forward",
                        "start_line": 12,
                        "end_line": 18,
                    },
                    "text": "def forward(self, x): return x",
                }
            ]
        }

        tasks = _build_analysis_repair_tasks(
            focus=focus,
            core_snippets=core_snippets,
            snippet_to_evidence={"S1": "E1"},
        )

        self.assertEqual(tasks["mode"], "agentic-analysis-repair-tasks")
        self.assertEqual(tasks["task_count"], 1)
        self.assertEqual(tasks["candidate_count"], 1)
        task = tasks["tasks"][0]
        self.assertEqual(task["issue_types"], ["missing_evidence"])
        self.assertEqual(task["recommended_next"], "reassess_existing_evidence")
        self.assertEqual(task["candidates"][0]["matched_snippet_ids"], ["S1"])
        self.assertEqual(task["candidates"][0]["evidence_ids"], ["E1"])
        self.assertEqual(task["candidates"][0]["coverage_status"], "existing_evidence")

    def test_scan_outputs_fill_empty_alignment_ir(self) -> None:
        base_alignment = CodeAlignmentIR(
            project_id="toy_scan_first",
            author_mode="enhanced",
            author_confirmation_required=False,
        )
        raw_pack = RawEvidencePack(
            project_id="toy_scan_first",
            project_root="/repo",
            author_mode="enhanced",
            author_confirmation_required=False,
            evidence_items=[],
        )
        analysis = CodeMethodAnalysis.model_validate(
            {
                "execution_flows": [
                    {
                        "flow_id": "FLOW-story-first-code-agents",
                        "purpose": "Recovered from scanned pipeline steps.",
                        "ordered_steps": [
                            "Experiment configuration assembly",
                            "Dual-branch scoring and regularized optimization",
                        ],
                    }
                ],
                "method_modules": [
                    {
                        "path": "train.py",
                        "symbols": ["main"],
                        "module_class": "method-core",
                        "paper_role": "configuration entrypoint",
                        "evidence_span_ids": ["E1"],
                        "llm_confidence": "high",
                    },
                    {
                        "path": "trainer.py",
                        "symbols": ["compute_loss"],
                        "module_class": "method-core",
                        "paper_role": "dual-branch objective",
                        "evidence_span_ids": ["E2"],
                        "llm_confidence": "medium",
                    },
                ],
                "candidate_mechanisms": [
                    {
                        "mechanism_id": "MECH1",
                        "name": "Experiment configuration assembly",
                        "description": "Resolve configs and launch settings.",
                        "inputs": ["configs"],
                        "outputs": ["resolved settings"],
                        "supporting_span_ids": ["E1"],
                    },
                    {
                        "mechanism_id": "MECH2",
                        "name": "Dual-branch scoring and regularized optimization",
                        "description": "Fuse branch scores and optimize them jointly.",
                        "inputs": ["branch logits"],
                        "outputs": ["training objective"],
                        "supporting_span_ids": ["E2"],
                    },
                ],
                "author_alignment": {
                    "author_proposed_flow": [
                        "Configuration and task setup",
                        "Dual-branch scoring and training objective",
                    ],
                    "author_supported_flow": [
                        "Experiment configuration assembly",
                        "Dual-branch scoring and regularized optimization",
                    ],
                },
            }
        )
        code_facts = {
            "pipeline_steps": [
                {
                    "name": "Experiment configuration assembly",
                    "description": "Resolve configs and launch settings.",
                },
                {
                    "name": "Dual-branch scoring and regularized optimization",
                    "description": "Fuse branch scores and optimize them jointly.",
                },
            ]
        }
        author_markers = SimpleNamespace(
            paper_story_order=[
                "Configuration and task setup",
                "Dual-branch scoring and training objective",
            ],
            module_roles=[],
        )

        alignment = _merge_alignment_with_scan_outputs(
            base_alignment=base_alignment,
            raw_pack=raw_pack,
            code_method_analysis=analysis,
            code_facts=code_facts,
            author_markers=author_markers,
        )

        self.assertEqual(len(alignment.method_stages), 2)
        self.assertEqual(len(alignment.execution_stages), 2)
        self.assertEqual(len(alignment.stage_mappings), 2)
        self.assertEqual(len(alignment.module_roles), 2)
        self.assertEqual(
            [stage.name for stage in alignment.method_stages],
            [
                "Experiment configuration assembly",
                "Dual-branch scoring and regularized optimization",
            ],
        )
        self.assertEqual(
            alignment.author_alignment.preferred_method_stage_ids,
            ["M1", "M2"],
        )
        self.assertEqual(
            alignment.author_alignment.matched_steps,
            [
                "Configuration and task setup",
                "Dual-branch scoring and training objective",
            ],
        )


if __name__ == "__main__":
    unittest.main()
