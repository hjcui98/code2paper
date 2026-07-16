from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.llm.client import LLMResponse
from code2paper.evidence.claim_grounder import build_claim_evidence_map
from code2paper.pipeline.stages import authoring as phase5_authoring
from code2paper.pipeline.stages.evidence import build_method_evidence
from code2paper.pipeline.stages.authoring import write_phase5_artifacts
from code2paper.core.schemas import (
    ClaimEvidenceMap,
    CodeAlignmentIR,
    CodeMethodAnalysis,
    EvidenceItem,
    EvidenceStrength,
    LLMConfig,
    MethodEvidence,
    RawEvidencePack,
    SourceType,
)
from code2paper.validation.fidelity_validator import validate_method_fidelity
from tests.tempdir_support import workspace_tempdir


ROOT = Path(__file__).resolve().parents[1]
ATTENTION_FIXTURES = ROOT / "tests" / "fixtures" / "attention_story_first"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def paper_ready_markdown() -> str:
    overview = " ".join(
        [
            "The method is organized as an implementation-grounded pipeline that converts raw inputs into a shared representation before applying task-specific scoring.",
            "The overview stage defines the data flow, keeps the notation stable across modules, and separates reusable computation from evaluation logic.",
            "Rather than describing scripts or runtime commands, this section focuses on the algorithmic transformations that are supported by the extracted evidence.",
        ]
        * 7
    )
    encoding = " ".join(
        [
            "The encoder first maps each input unit into a latent vector and then refines the representation through repeated contextual mixing.",
            "This stage preserves the input identity while allowing neighboring evidence to influence the hidden state, which is the central mechanism used by later predictions.",
            "The output of the encoder is therefore a compact representation that can be reused by the downstream objective without restating implementation details.",
        ]
        * 7
    )
    scoring = " ".join(
        [
            "The prediction head receives the contextual representation and produces scores in the target space required by the method.",
            "Its role is deliberately narrow: it transforms the learned feature into the supervised or self-supervised signal while leaving feature extraction to the encoder.",
            "This separation makes the method description faithful to the code because the reusable backbone and the lightweight head are discussed as different components.",
        ]
        * 7
    )
    objective = " ".join(
        [
            "Training optimizes the prediction objective over the evidence-supported outputs and combines the terms that are explicitly present in the method analysis.",
            "The objective subsection gives only the core mathematical relations needed to understand the method, avoiding an appendix-like dump of every intermediate symbol.",
            "At inference time, the reusable representation is kept while auxiliary training-only components can be omitted when they are not required by the task.",
        ]
        * 7
    )
    return "\n\n".join(
        [
            "# Method",
            "## Overview",
            overview,
            "## Representation Learning",
            encoding,
            "$$\nh = f_\\theta(x)\n$$",
            "## Prediction Mechanism",
            scoring,
            "$$\ny = g_\\phi(h)\n$$",
            "## Training Objective",
            objective,
            "$$\n\\mathcal{L}=\\ell(y, y^*)\n$$",
        ]
    )


class Phase5AuthoringTests(unittest.TestCase):
    def _method_evidence(self) -> MethodEvidence:
        return MethodEvidence.model_validate(load_json(ATTENTION_FIXTURES / "attention_method_evidence.generated.json"))

    def _claim_map(self) -> ClaimEvidenceMap:
        return ClaimEvidenceMap.model_validate(load_json(ATTENTION_FIXTURES / "attention_claim_evidence_map.generated.json"))

    def _alignment(self) -> CodeAlignmentIR:
        return CodeAlignmentIR.model_validate(load_json(ATTENTION_FIXTURES / "attention_code_alignment_ir.generated.json"))

    def _raw_fallback_pack(self) -> RawEvidencePack:
        return RawEvidencePack(
            project_id="demo",
            project_root="/repo",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E1",
                    source_type=SourceType.SOURCE,
                    path="train.py",
                    line_start=1,
                    line_end=4,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="training_loop",
                ),
                EvidenceItem(
                    evidence_id="E2",
                    source_type=SourceType.BASH,
                    path="scripts/train.sh",
                    line_start=1,
                    line_end=3,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="config",
                ),
            ],
        )

    def _raw_fallback_pack_with_loss_summary(self) -> RawEvidencePack:
        return RawEvidencePack(
            project_id="demo",
            project_root="/repo",
            evidence_items=[
                EvidenceItem(
                    evidence_id="E1",
                    source_type=SourceType.SOURCE,
                    path="agents/visualizer_agent.py",
                    line_start=1,
                    line_end=20,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="inference",
                ),
                EvidenceItem(
                    evidence_id="E2",
                    source_type=SourceType.SOURCE,
                    path="utils/eval_toolkits.py",
                    line_start=1,
                    line_end=30,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="loss",
                ),
                EvidenceItem(
                    evidence_id="E3",
                    source_type=SourceType.CONFIG,
                    path="configs/model_config.yaml",
                    line_start=1,
                    line_end=8,
                    evidence_strength=EvidenceStrength.HARD,
                    confidence=0.85,
                    content_summary="config",
                ),
            ],
        )

    def test_phase5_uses_deterministic_authoring_fallback_without_llm(self) -> None:
        with workspace_tempdir() as tmpdir:
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase5_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="none"),
            )
            manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
            prompt_exists = paths["write_prompt"].exists()
            blocked_exists = paths["phase5_blocked"].exists()
            draft_exists = paths["text_md"].exists()

        self.assertIsNotNone(markdown)
        self.assertIsNotNone(tex)
        self.assertTrue(prompt_exists)
        self.assertFalse(blocked_exists)
        self.assertTrue(draft_exists)
        self.assertEqual(manifest["mode"], "deterministic-authoring-fallback")
        self.assertFalse(manifest["llm_available"])
        self.assertEqual(len(manifest["llm_call_logs"]), 0)

    def test_phase5_raw_evidence_fallback_remains_fidelity_valid_without_leaking_paths(self) -> None:
        raw_pack = self._raw_fallback_pack()
        method_evidence = build_method_evidence(
            raw_pack,
            CodeAlignmentIR(project_id="demo"),
            CodeMethodAnalysis(evidence_spans=raw_pack.evidence_items),
        )
        claim_map = build_claim_evidence_map(method_evidence, CodeAlignmentIR(project_id="demo"))

        with workspace_tempdir() as tmpdir:
            markdown, _tex, _paths = write_phase5_artifacts(
                method_root=Path(tmpdir) / "paper" / "method",
                method_evidence=method_evidence,
                claim_map=claim_map,
                llm_config=LLMConfig(provider="none"),
            )

        self.assertIsNotNone(markdown)
        assert markdown is not None
        self.assertIn("mechanisms=MECH1", markdown)
        self.assertNotIn("train.py", markdown)
        self.assertNotIn("scripts/train.sh", markdown)
        report = validate_method_fidelity(
            raw_pack=raw_pack,
            method_evidence=method_evidence,
            draft_markdown=markdown,
            claim_map=claim_map,
        )
        self.assertTrue(report.passed, report.model_dump())

    def test_phase5_raw_evidence_fallback_with_loss_summary_does_not_invent_objective_modules(self) -> None:
        raw_pack = self._raw_fallback_pack_with_loss_summary()
        method_evidence = build_method_evidence(
            raw_pack,
            CodeAlignmentIR(project_id="demo"),
            CodeMethodAnalysis(evidence_spans=raw_pack.evidence_items),
        )
        claim_map = build_claim_evidence_map(method_evidence, CodeAlignmentIR(project_id="demo"))

        with workspace_tempdir() as tmpdir:
            markdown, _tex, _paths = write_phase5_artifacts(
                method_root=Path(tmpdir) / "paper" / "method",
                method_evidence=method_evidence,
                claim_map=claim_map,
                llm_config=LLMConfig(provider="none"),
            )

        self.assertIsNotNone(markdown)
        assert markdown is not None
        lowered = markdown.lower()
        self.assertNotIn("## objective", lowered)
        self.assertNotIn("decoder", lowered)
        self.assertNotIn("prediction", lowered)
        self.assertNotIn("reconstruction", lowered)

    def test_phase5_uses_llm_authoring_outputs(self) -> None:
        with workspace_tempdir() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            complete.return_value = LLMResponse(
                text=json.dumps({"markdown": paper_ready_markdown()}),
                response_hash="sha256:test-llm",
            )
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase5_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
            sidecar = json.loads(paths["text_sidecar"].read_text(encoding="utf-8"))
            numeric_report = json.loads(paths["qa_numbers"].read_text(encoding="utf-8"))
            equation_report = json.loads(paths["qa_equations"].read_text(encoding="utf-8"))
            outline_exists = paths["outline"].exists()
            terminology_exists = paths["terms"].exists()
            draft_claim_map_exists = paths["text_claims"].exists()

        complete.assert_called_once()
        self.assertIn("# Method", markdown or "")
        self.assertIn("Representation Learning", markdown or "")
        self.assertIn("\\section{Method}", tex or "")
        self.assertTrue(outline_exists)
        self.assertTrue(terminology_exists)
        self.assertTrue(draft_claim_map_exists)
        self.assertEqual(manifest["mode"], "llm-authoring")
        self.assertEqual(manifest["llm_call_logs"], ["sha256:test-llm"])
        self.assertEqual(sidecar["paragraphs"][0]["llm_call_id"], "sha256:test-llm")
        self.assertTrue(numeric_report["passed"])
        self.assertIn("passed", equation_report)

    def test_phase5_reports_quality_without_blocking_invalid_llm_response(self) -> None:
        with workspace_tempdir() as tmpdir, patch.dict(
            "os.environ",
            {
                "CODE2PAPER_PHASE5_ENABLE_REVISION_CYCLE": "1",
                "CODE2PAPER_PHASE5_REQUIRE_PAPER_READY": "0",
            },
        ), patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            complete.return_value = LLMResponse(text='{"wrong": ""}', response_hash="sha256:bad")
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase5_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
            blocked_exists = paths["phase5_blocked"].exists()
            self_check_exists = paths["self_check"].exists()

        complete.assert_called_once()
        self.assertIsNotNone(markdown)
        self.assertIsNotNone(tex)
        self.assertFalse(blocked_exists)
        self.assertTrue(self_check_exists)
        self.assertEqual(manifest["mode"], "deterministic-authoring-fallback")
        self.assertEqual(manifest["llm_call_logs"], ["sha256:bad"])

    def test_phase5_falls_back_to_deterministic_writer_on_provider_missing_content(self) -> None:
        with workspace_tempdir() as tmpdir, patch.dict(
            "os.environ", {"CODE2PAPER_PHASE5_REQUIRE_PAPER_READY": "1"}
        ), patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            complete.return_value = LLMResponse(
                text="",
                response_hash="sha256:missing-content",
                blocked_reason="provider_response_missing_content:message_keys=role",
            )
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase5_artifacts(
                method_root=method_root,
                method_evidence=self._method_evidence(),
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
            text_md_exists = paths["text_md"].exists()
            text_tex_exists = paths["text_tex"].exists()
            blocked_exists = paths["phase5_blocked"].exists()

        self.assertIsNone(markdown)
        self.assertIsNone(tex)
        self.assertFalse(text_md_exists)
        self.assertFalse(text_tex_exists)
        self.assertTrue(blocked_exists)
        self.assertEqual(manifest["mode"], "blocked_paper_readiness_fallback")
        self.assertEqual(manifest["llm_call_logs"], ["sha256:missing-content"])

    def test_phase5_claim_mapping_uses_stage_mechanism_evidence_when_frozen_sparse(self) -> None:
        method_evidence = self._method_evidence()
        for mechanism in method_evidence.frozen_mechanisms:
            mechanism.evidence_span_ids = []
            mechanism.parent_stage_id = ""

        with workspace_tempdir() as tmpdir, patch("code2paper.llm.client.LLMClient.complete", autospec=True) as complete:
            complete.return_value = LLMResponse(
                text=json.dumps({"markdown": paper_ready_markdown()}),
                response_hash="sha256:test-llm",
            )
            method_root = Path(tmpdir) / "paper" / "method"
            markdown, tex, paths = write_phase5_artifacts(
                method_root=method_root,
                method_evidence=method_evidence,
                claim_map=self._claim_map(),
                llm_config=LLMConfig(provider="openai", model="gpt-test"),
                alignment=self._alignment(),
            )
            manifest = json.loads(paths["phase5_manifest"].read_text(encoding="utf-8"))
            claim_report = json.loads(paths["qa_claims"].read_text(encoding="utf-8"))
            draft_claim_map = json.loads(paths["text_claims"].read_text(encoding="utf-8"))

        self.assertIsNotNone(markdown)
        self.assertIsNotNone(tex)
        self.assertEqual(manifest["mode"], "llm-authoring")
        self.assertTrue(claim_report["passed"])
        self.assertTrue(draft_claim_map["paragraphs"])
        self.assertTrue(all(paragraph["evidence_span_ids"] for paragraph in draft_claim_map["paragraphs"]))

    def test_phase5_postprocess_marks_implementation_leakage_before_revision(self) -> None:
        markdown = "\n\n".join(
            [
                "# Method",
                "## Overview",
                "<!-- c2p: stage=ALL; evidence=E1; confidence=high -->\n"
                "The method is implemented in `models.PCP_MAE.Group` and launched from train.py with --config. "
                "The method groups inputs and preserves patch normalization as an algorithmic transformation.",
                "## Objective",
                "<!-- c2p: stage=S1; evidence=E2; confidence=high -->\n"
                "The objective combines prediction and reconstruction terms.",
                "$$\n\\mathcal{L}=\\mathcal{L}_{p}+\\mathcal{L}_{r}\n$$",
            ]
        )

        cleaned = phase5_authoring._paper_prose_postprocess(
            markdown,
            self._method_evidence(),
            equations_tex="",
        )
        issues = phase5_authoring._semantic_method_issues(
            cleaned,
            phase5_authoring._method_plan_scaffold(self._method_evidence(), equations_tex=""),
        )

        self.assertIn("train.py", cleaned)
        self.assertIn("--config", cleaned)
        self.assertIn("implementation_leakage", {issue["issue"] for issue in issues["issues"]})
        self.assertNotIn("`", cleaned)
        self.assertIn("patch normalization", cleaned)

    def test_phase5_authoring_prompt_exposes_author_intent_spine(self) -> None:
        prompt = phase5_authoring._authoring_prompt(self._method_evidence(), self._claim_map())

        self.assertIn("author_intent_spine", prompt)
        self.assertIn("preferred_section_flow", prompt)
        self.assertIn("preferred module naming plan", prompt)

    def test_method_plan_scaffold_has_io_roles_and_report_only_quality(self) -> None:
        plan = phase5_authoring._method_plan_scaffold(self._method_evidence(), equations_tex="")
        report = phase5_authoring._method_plan_quality_report(plan)

        self.assertTrue(plan.sections)
        self.assertEqual(plan.sections[0].role, "overview")
        self.assertTrue(any(section.role in {"core", "objective"} for section in plan.sections))
        self.assertTrue(all(section.input_representation for section in plan.sections if section.role in {"core", "objective"}))
        self.assertTrue(all(section.operation for section in plan.sections if section.role in {"core", "objective"}))
        self.assertTrue(all(section.output_representation for section in plan.sections if section.role in {"core", "objective"}))
        self.assertIn("report_only", report)
        self.assertTrue(report["report_only"])

    def test_deterministic_authoring_keeps_config_only_pipeline_paper_facing(self) -> None:
        method_evidence = MethodEvidence.model_validate(
            {
                "project_id": "toy",
                "method_name": "Toy Train Method Pipeline",
                "method_goal": "Describe the config-driven toy training pipeline implemented in this fixture project.",
                "implementation_scope": "current codebase only",
                "stages": [
                    {
                        "stage_id": "S1",
                        "name": "Configuration loading",
                        "purpose": "Resolve training settings from the base config and launcher overrides.",
                        "inputs": ["raw_point_cloud"],
                        "outputs": ["output_0"],
                        "mechanisms": [
                            {
                                "mechanism_id": "MECH1",
                                "description": "Resolve training settings from the base config and launcher overrides.",
                                "support_status": "supported",
                                "evidence_ids": ["E1"],
                                "confidence": "high",
                            }
                        ],
                    },
                    {
                        "stage_id": "S2",
                        "name": "Training execution",
                        "purpose": "Launch the toy training entrypoint with the resolved configuration.",
                        "inputs": ["input_1"],
                        "outputs": ["output_1"],
                        "mechanisms": [
                            {
                                "mechanism_id": "MECH2",
                                "description": "Launch the toy training entrypoint with the resolved configuration.",
                                "support_status": "supported",
                                "evidence_ids": ["E2"],
                                "confidence": "high",
                            }
                        ],
                    },
                ],
                "stage_packets": [
                    {
                        "stage_id": "S1",
                        "name": "Configuration loading",
                        "purpose": "Resolve training settings from the base config and launcher overrides.",
                        "inputs": ["raw_point_cloud"],
                        "outputs": ["output_0"],
                        "primary_evidence_ids": ["E1"],
                        "primary_mechanism_ids": ["MECH1"],
                    },
                    {
                        "stage_id": "S2",
                        "name": "Training execution",
                        "purpose": "Launch the toy training entrypoint with the resolved configuration.",
                        "inputs": ["input_1"],
                        "outputs": ["output_1"],
                        "primary_evidence_ids": ["E2"],
                        "primary_mechanism_ids": ["MECH2"],
                    },
                ],
            }
        )

        plan = phase5_authoring._method_plan_scaffold(method_evidence, equations_tex="")
        quality = phase5_authoring._method_plan_quality_report(plan)
        markdown = phase5_authoring._force_structural_method_shape(
            markdown="# Method\n\nShort draft.",
            method_evidence=method_evidence,
            equations_tex="",
        )
        semantic = phase5_authoring._semantic_method_issues(markdown, plan)

        self.assertTrue(any(section.role in {"core", "objective"} for section in plan.sections))
        self.assertFalse(any("objective" in section.heading.lower() and section.role != "objective" for section in plan.sections))
        self.assertFalse(any(section.role == "objective" for section in plan.sections))
        self.assertTrue(quality["passed"])
        self.assertTrue(semantic["passed"])
        self.assertNotIn("stage performs this transformation", markdown)

    def test_method_plan_quality_flags_protocol_promoted_to_main_figure(self) -> None:
        plan = phase5_authoring.MethodPlanOutput(
            overview_focus="test",
            sections=[
                phase5_authoring.MethodPlanSection(
                    section_id="S1",
                    heading="Downstream Voting Evaluation",
                    purpose="Describe testing metrics.",
                    role="core",
                    input_representation="features",
                    operation="run voting evaluation",
                    output_representation="metrics",
                    figure_role="include",
                )
            ],
        )

        report = phase5_authoring._method_plan_quality_report(plan)

        self.assertFalse(report["passed"])
        self.assertIn("protocol_section_promoted_to_core_or_figure", {issue["issue"] for issue in report["issues"]})

    def test_phase5_structural_readiness_repair_expands_short_draft(self) -> None:
        short = "\n\n".join(
            [
                "# Method",
                "The method encodes inputs and optimizes a compact objective.",
                "$$\nh=f_\\theta(x)\n$$",
                "$$\ny=g_\\phi(h)\n$$",
                "$$\n\\mathcal{L}=\\ell(y,y^*)\n$$",
            ]
        )

        repaired = phase5_authoring._repair_structural_readiness_if_needed(
            markdown=short,
            method_evidence=self._method_evidence(),
            equations_tex="",
        )
        report = phase5_authoring.validate_paper_readiness(repaired)

        self.assertIn("## Overview", repaired)
        self.assertRegex(repaired, r"## .*Objective")
        self.assertGreaterEqual(report["metrics"]["heading_count"], 4)
        self.assertNotIn("PR1", {issue["issue_id"] for issue in report["issues"] if issue["severity"] == "high"})
        self.assertNotIn("PR3", {issue["issue_id"] for issue in report["issues"] if issue["severity"] == "high"})
        self.assertNotIn("PR5", {issue["issue_id"] for issue in report["issues"] if issue["severity"] == "high"})

    def test_latex_smoke_report_uses_real_compile_command(self) -> None:
        with patch.dict(os.environ, {"CODE2PAPER_TMPDIR": str(ROOT / ".tmp")}, clear=False), patch(
            "code2paper.validation.latex_smoke_validator.shutil.which", return_value="/usr/bin/pdflatex"
        ), patch(
            "code2paper.validation.latex_smoke_validator.subprocess.run",
            return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="ok"),
        ) as run:
            report = phase5_authoring.validate_latex_smoke("\\section{Method}\nText.")

        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "compiled")
        self.assertIn("-halt-on-error", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
