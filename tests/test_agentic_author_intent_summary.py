from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.author_intent_summary import AuthorIntentSummary, build_author_intent_summary
from code2paper.agentic.authoring_context import EvidenceBoundAuthoringClaim, EvidenceBoundAuthoringContext
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.coverage_decisioning import coverage_decision_trace
from code2paper.agentic.decisioning import AgenticDecisionPrompt
from code2paper.agentic.evidence_sufficiency import EvidenceSufficiencyReport, evidence_sufficiency_trace
from code2paper.agentic.figure_planner import figure_plan_trace
from code2paper.agentic.graph import _coverage_critic_node
from code2paper.agentic.invariant_audit import build_invariant_audit
from code2paper.agentic.legacy_pre_evidence_stage_tools import run_input_resolution_stage
from code2paper.agentic.retrieval import CoverageItem, RetrievalCoverageReport
from code2paper.core.author_questionnaire import load_author_markers
from code2paper.core.schemas import (
    AuthorDesignIntent,
    AuthorInnovationClaim,
    AuthorMarkers,
    AuthorPipelineStep,
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


ROOT = Path(__file__).resolve().parents[1]
TOY_MARKERS = ROOT / "tests" / "fixtures" / "toy_train_project_author_markers.yaml"
TOY_PROJECT = ROOT / "tests" / "fixtures" / "toy_train_project"


class AgenticAuthorIntentSummaryTests(unittest.TestCase):
    def test_input_resolution_freezes_digest_bound_intent_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            markers = root / "author.yaml"
            markers.write_text(TOY_MARKERS.read_text(encoding="utf-8"), encoding="utf-8")
            state = AgenticRunState(
                project_root=TOY_PROJECT,
                out_root=root / "out",
                author_markers_path=str(markers),
            )

            result = run_input_resolution_stage(state)
            payload = json.loads(Path(result.artifacts["intent_spec"]).read_text(encoding="utf-8"))
            repo_snapshot = root / "repo_snapshot.json"
            repo_snapshot.write_text("{}\n", encoding="utf-8")
            formal_state = state.model_copy(update={
                "artifacts": {
                    **result.artifacts,
                    "repo_snapshot": str(repo_snapshot),
                }
            })
            initial = next(
                item for item in build_invariant_audit(formal_state).checks
                if item.name == "author_intent_spec_gate"
            )
            resolved_markers = Path(result.artifacts["resolved_author_markers"])
            resolved_markers.write_text(
                resolved_markers.read_text(encoding="utf-8") + "\n# changed\n",
                encoding="utf-8",
            )
            stale = next(
                item for item in build_invariant_audit(formal_state).checks
                if item.name == "author_intent_spec_gate"
            )

        self.assertEqual(result.status.value, "success")
        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(
            payload["source_author_markers"]["hash"],
            payload["input_artifact_digests"]["resolved_author_markers"],
        )
        self.assertEqual(
            payload["intent"]["method_goal"],
            build_author_intent_summary(load_author_markers(TOY_MARKERS)).method_goal,
        )
        self.assertTrue(initial.passed)
        self.assertFalse(stale.passed)

    def test_summary_keeps_story_relevant_author_intent(self) -> None:
        markers = AuthorMarkers(
            project_goal="Train a configurable model.",
            paper_method_goal="Describe the config-driven training method.",
            implementation_scope="Current repository only.",
            method_mainline="Configuration -> training",
            paper_story_order=["Configuration loading", "Training execution"],
            deemphasize_details=["shell launcher plumbing"],
            priority_files=["train.py", "configs/base.yaml"],
            pipeline_steps=[
                AuthorPipelineStep(name="Configuration loading", purpose="Resolve settings."),
                AuthorPipelineStep(name="Training execution", purpose="Run the trainer."),
            ],
            design_intents=[AuthorDesignIntent(intent="Keep the paper centered on implementation behavior.")],
            innovation_claims=[AuthorInnovationClaim(claim="Config-driven training is the central method claim.")],
        )

        summary = build_author_intent_summary(markers)

        self.assertEqual(summary.project_goal, "Train a configurable model.")
        self.assertEqual(summary.method_goal, "Describe the config-driven training method.")
        self.assertEqual(summary.story_order, ["Configuration loading", "Training execution"])
        self.assertEqual(summary.deemphasize_details, ["shell launcher plumbing"])
        self.assertEqual(summary.priority_files, ["train.py", "configs/base.yaml"])
        self.assertEqual(summary.pipeline_steps[0], "Configuration loading: Resolve settings.")
        self.assertEqual(summary.design_intents[0], "Keep the paper centered on implementation behavior.")
        self.assertEqual(summary.innovation_claims[0], "Config-driven training is the central method claim.")

    def test_coverage_trace_exposes_author_intent_summary(self) -> None:
        summary = AuthorIntentSummary(method_goal="Explain config-driven training.", priority_files=["train.py"])
        coverage = RetrievalCoverageReport(
            overall_score=1.0,
            covered_targets=1,
            items=[
                CoverageItem(
                    target_id="RT1",
                    query="Training execution",
                    support_status="covered",
                    matched_paths=["train.py"],
                )
            ],
        )

        _decision, trace = coverage_decision_trace(coverage, author_intent_summary=summary)

        self.assertEqual(trace.prompt.inputs["author_intent_summary"]["method_goal"], "Explain config-driven training.")
        self.assertEqual(trace.prompt.inputs["author_intent_summary"]["priority_files"], ["train.py"])

    def test_graph_coverage_node_loads_author_intent_summary_from_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            coverage_path = root / "coverage.json"
            coverage_path.write_text(RetrievalCoverageReport(overall_score=1.0).model_dump_json(), encoding="utf-8")
            prompts: list[AgenticDecisionPrompt] = []
            state = AgenticRunState(
                project_root=Path("."),
                out_root=root,
                author_markers_path=str(TOY_MARKERS),
                artifacts={"retrieval_coverage": str(coverage_path)},
            )

            _coverage_critic_node(decision_provider=lambda prompt: prompts.append(prompt) or {})(state.model_dump(mode="json"))

        summary = prompts[0].inputs["author_intent_summary"]
        self.assertEqual(summary["method_goal"], "Describe the code-backed configuration fields and training entrypoint in this fixture project.")
        self.assertEqual(summary["priority_files"][:2], ["train.py", "configs/base.yaml"])
        self.assertEqual(summary["pipeline_steps"][0], "Configuration loading: The base configuration specifies dataset and trainer settings.")

    def test_late_decision_prompts_expose_author_intent_summary(self) -> None:
        summary = AuthorIntentSummary(
            method_goal="Write implementation-first method prose.",
            story_order=["Feature Encoding", "Prediction Head"],
            deemphasize_details=["unsupported add-ons"],
        )

        _authoring_plan, authoring_trace = authoring_plan_trace(_authoring_context(), author_intent_summary=summary)
        _evidence_decision, evidence_trace = evidence_sufficiency_trace(_sufficiency_report(), author_intent_summary=summary)
        _figure_plan, figure_trace = figure_plan_trace(
            method_evidence=_method_evidence(),
            claim_map=_claim_map(),
            author_intent_summary=summary,
        )

        self.assertEqual(authoring_trace.prompt.inputs["author_intent_summary"]["story_order"], ["Feature Encoding", "Prediction Head"])
        self.assertEqual(evidence_trace.prompt.inputs["author_intent_summary"]["method_goal"], "Write implementation-first method prose.")
        self.assertEqual(figure_trace.prompt.inputs["author_intent_summary"]["deemphasize_details"], ["unsupported add-ons"])


def _authoring_context() -> EvidenceBoundAuthoringContext:
    return EvidenceBoundAuthoringContext(
        method_name="Demo",
        allowed_claims=[
            EvidenceBoundAuthoringClaim(
                claim_id="C1",
                claim_text="The encoder uses attention.",
                support_status="supported",
                evidence_ids=["E1"],
                writing_boundary="safe_to_write",
            )
        ],
    )


def _sufficiency_report() -> EvidenceSufficiencyReport:
    return EvidenceSufficiencyReport(
        checked_claims=1,
        supported_claims=1,
        support_rate=1.0,
        safe_claim_ids=["C1"],
        frozen_evidence_ids=["E1"],
        evidence_backed_mechanisms=1,
        hard_gate_passed=True,
    )


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo Method",
        method_goal="Explain the demo method.",
        implementation_scope="core implementation",
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Feature Encoding",
                purpose="Encode inputs.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="Feature encoder uses attention.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                    )
                ],
            )
        ],
    )


def _claim_map() -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder uses attention.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                mechanism_ids=["MECH1"],
            )
        ]
    )


if __name__ == "__main__":
    unittest.main()
