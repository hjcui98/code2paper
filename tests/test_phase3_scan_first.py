from __future__ import annotations

import json
import unittest
from pathlib import Path

from code2paper.pipeline.stages.evidence import build_method_evidence, write_phase3_artifacts
from code2paper.core.schemas import CodeAlignmentIR, CodeMethodAnalysis, RawEvidencePack
from tests.tempdir_support import workspace_tempdir


class Phase3ScanFirstTests(unittest.TestCase):
    def _raw_pack(self) -> RawEvidencePack:
        return RawEvidencePack(
            project_id="toy_scan_first",
            project_root="/repo",
            author_mode="enhanced",
            author_confirmation_required=False,
            evidence_items=[],
        )

    def _alignment(self) -> CodeAlignmentIR:
        return CodeAlignmentIR(
            project_id="toy_scan_first",
            author_mode="enhanced",
            author_confirmation_required=False,
        )

    def _analysis(self) -> CodeMethodAnalysis:
        return CodeMethodAnalysis.model_validate(
            {
                "execution_flows": [
                    {
                        "flow_id": "FLOW-story-first-code-agents",
                        "purpose": "Recovered from scanned pipeline steps.",
                        "ordered_steps": [
                            "Experiment configuration assembly",
                            "Shared token generation and modality-specific projection",
                            "Dual-branch scoring and regularized optimization",
                            "Task-aware evaluation and report collection",
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
                        "path": "model.py",
                        "symbols": ["build_shared_tokens"],
                        "module_class": "method-core",
                        "paper_role": "shared representation builder",
                        "evidence_span_ids": ["E2"],
                        "llm_confidence": "high",
                    },
                    {
                        "path": "trainer.py",
                        "symbols": ["compute_loss"],
                        "module_class": "method-core",
                        "paper_role": "dual-branch objective",
                        "evidence_span_ids": ["E3"],
                        "llm_confidence": "high",
                    },
                    {
                        "path": "eval.py",
                        "symbols": ["evaluate"],
                        "module_class": "method-core",
                        "paper_role": "task-aware evaluator",
                        "evidence_span_ids": ["E4"],
                        "llm_confidence": "high",
                    },
                ],
                "candidate_mechanisms": [
                    {
                        "mechanism_id": "MECH1",
                        "name": "Experiment configuration assembly",
                        "description": "Resolve configs and launch settings from the scanned training entrypoint.",
                        "inputs": ["configs", "launcher overrides"],
                        "outputs": ["resolved experiment settings"],
                        "supporting_span_ids": ["E1"],
                    },
                    {
                        "mechanism_id": "MECH2",
                        "name": "Shared token generation and modality-specific projection",
                        "description": "Build shared representation tokens and project them into modality-specific spaces.",
                        "inputs": ["backbone features"],
                        "outputs": ["shared tokens"],
                        "supporting_span_ids": ["E2"],
                    },
                    {
                        "mechanism_id": "MECH3",
                        "name": "Dual-branch scoring and regularized optimization",
                        "description": "Fuse branch scores and optimize them with a regularized objective.",
                        "inputs": ["branch logits"],
                        "outputs": ["training objective"],
                        "supporting_span_ids": ["E3"],
                    },
                    {
                        "mechanism_id": "MECH4",
                        "name": "Task-aware evaluation and report collection",
                        "description": "Switch evaluation behavior by protocol and aggregate reports.",
                        "inputs": ["predictions", "task protocol"],
                        "outputs": ["evaluation report"],
                        "supporting_span_ids": ["E4"],
                    },
                ],
                "author_alignment": {
                    "author_proposed_flow": [
                        "Configuration and task setup",
                        "Shared representation learner",
                        "Dual-branch scoring and training objective",
                        "Task-specific inference protocol",
                    ],
                    "author_supported_flow": [
                        "Experiment configuration assembly",
                        "Shared token generation and modality-specific projection",
                        "Dual-branch scoring and regularized optimization",
                        "Task-aware evaluation and report collection",
                    ],
                },
            }
        )

    def test_build_method_evidence_recovers_supported_stages_from_scanned_analysis(self) -> None:
        evidence = build_method_evidence(
            self._raw_pack(),
            self._alignment(),
            self._analysis(),
        )

        stage_by_name = {stage.name: stage for stage in evidence.stages}
        self.assertEqual(
            stage_by_name["Configuration and task setup"].mechanisms[0].evidence_ids,
            ["E1"],
        )
        self.assertEqual(
            stage_by_name["Shared representation learner"].mechanisms[0].evidence_ids,
            ["E2"],
        )
        self.assertEqual(
            stage_by_name["Dual-branch scoring and training objective"].mechanisms[0].evidence_ids,
            ["E3"],
        )
        self.assertEqual(
            stage_by_name["Task-specific inference protocol"].mechanisms[0].evidence_ids,
            ["E4"],
        )
        self.assertEqual(stage_by_name["Configuration and task setup"].modules[0].path, "train.py")
        self.assertEqual(stage_by_name["Task-specific inference protocol"].outputs, ["evaluation report"])

    def test_write_phase3_artifacts_uses_scanned_pipeline_steps_for_stage_packets(self) -> None:
        code_facts = {
            "overview": {
                "implementation_summary": "Recovered from scanned code facts.",
            },
            "pipeline_steps": [
                {
                    "name": "Experiment configuration assembly",
                    "description": "Merge dataset config, trainer config, and command-line overrides.",
                    "input_data": ["config files", "launcher overrides"],
                    "output_data": ["resolved experiment settings"],
                    "involved_modules": ["configuration entrypoint"],
                    "confidence": 0.9,
                },
                {
                    "name": "Shared token generation and modality-specific projection",
                    "description": "Create shared tokens and project them into visual and textual spaces.",
                    "input_data": ["backbone features"],
                    "output_data": ["shared tokens"],
                    "involved_modules": ["shared representation builder"],
                    "confidence": 0.9,
                },
                {
                    "name": "Dual-branch scoring and regularized optimization",
                    "description": "Combine branch scores and build the regularized training objective.",
                    "input_data": ["branch logits"],
                    "output_data": ["training objective"],
                    "involved_modules": ["dual-branch objective"],
                    "confidence": 0.9,
                },
                {
                    "name": "Task-aware evaluation and report collection",
                    "description": "Run protocol-specific evaluation and collect reports.",
                    "input_data": ["predictions", "task protocol"],
                    "output_data": ["evaluation report"],
                    "involved_modules": ["task-aware evaluator"],
                    "confidence": 0.9,
                },
            ],
        }

        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            paper_root = Path(tmpdir) / "paper"
            evidence, _paths = write_phase3_artifacts(
                method_root=method_root,
                paper_root=paper_root,
                raw_pack=self._raw_pack(),
                alignment=self._alignment(),
                code_method_analysis=self._analysis(),
                code_facts=code_facts,
                llm_config=None,
            )
            from code2paper.core.output_names import method_output

            saved = json.loads(method_output(method_root, "evidence").read_text(encoding="utf-8"))

        packet_by_name = {packet["name"]: packet for packet in evidence.stage_packets}
        self.assertEqual(
            packet_by_name["Configuration and task setup"]["purpose"],
            "Merge dataset config, trainer config, and command-line overrides.",
        )
        self.assertEqual(
            packet_by_name["Task-specific inference protocol"]["outputs"],
            ["evaluation report"],
        )
        self.assertEqual(saved["stage_packets"][0]["name"], "Configuration and task setup")

    def test_phase3_promotes_paper_alias_only_with_code_evidence(self) -> None:
        raw_pack = RawEvidencePack(
            project_id="toy_alias",
            project_root="/repo",
            author_mode="enhanced",
            author_confirmation_required=False,
            evidence_items=[
                {
                    "evidence_id": "EAUTHOR1",
                    "source_type": "author",
                    "path": "author.md",
                    "confidence": 0.8,
                    "content_summary": (
                        "The paper calls this the Adaptive Routing Module (ARM). "
                        "It also mentions an Unsupported Display Block (UDB)."
                    ),
                }
            ],
        )
        code_facts = {
            "modules": [
                {
                    "name": "route_head",
                    "role": "adaptive routing head",
                    "key_logic": "Computes adaptive routing weights and applies them to encoded features.",
                    "evidence_refs": ["E7"],
                }
            ]
        }

        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            evidence, _paths = write_phase3_artifacts(
                method_root=method_root,
                paper_root=Path(tmpdir) / "paper",
                raw_pack=raw_pack,
                alignment=CodeAlignmentIR(project_id="toy_alias", author_mode="enhanced"),
                code_method_analysis=CodeMethodAnalysis(),
                code_facts=code_facts,
                llm_config=None,
            )

        aliases = {alias.alias: alias for alias in evidence.paper_module_aliases}
        self.assertIn("ARM", aliases)
        self.assertEqual(aliases["ARM"].expansion, "Adaptive Routing Module")
        self.assertEqual(aliases["ARM"].evidence_span_ids, ["E7"])
        self.assertNotIn("UDB", aliases)


if __name__ == "__main__":
    unittest.main()
