from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code2paper.agentic.authoring_constraints import (
    apply_authoring_constraints,
    build_authoring_constraints,
    load_authoring_constraints,
    write_authoring_constraints,
)
from code2paper.agentic.authoring_context import (
    authoring_context_brief,
    build_authoring_context,
    load_authoring_context,
)
from code2paper.agentic.authoring_plan import build_authoring_plan, load_authoring_plan
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.contracts import AgenticRunState, StageStatus
from code2paper.agentic.legacy_stage_tools import _run_authoring
from code2paper.agentic.legacy_authoring_stage_tool import _text_revision_brief
from code2paper.agentic.tools import canonical_stage_tool_specs
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo Method",
        method_goal="Explain the implementation.",
        implementation_scope="core implementation",
        writing_constraints=["Use code evidence as the truth boundary."],
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Encode",
                purpose="Extract features.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="Feature encoder uses the configured attention block.",
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
                source="author_claim:mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The encoder has an unsupported extra behavior.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E404"],
                source="author_claim:mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The encoder exposes a partial weighting behavior.",
                support_status=SupportStatus.PARTIAL,
                evidence_ids=["E1"],
                source="method_mechanism",
                caveats=["Only the observed weighting path is supported."],
            ),
        ]
    )


def _authorize_authoring(state: AgenticRunState) -> AgenticRunState:
    report_path = method_output(state.method_root, "grounding_context").parent / "agentic_evidence_sufficiency_report.json"
    trace_path = state.method_root / "10_run" / "evidence_sufficiency_decision_trace.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"hard_gate_passed": True, "safe_claim_ids": ["C1"], "frozen_evidence_ids": ["E1"]}),
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps(
            {
                "node": "evidence_sufficiency",
                "prompt": {"node": "evidence_sufficiency", "objective": "test"},
                "final_decision": {"recommended_next": "grounding"},
            }
        ),
        encoding="utf-8",
    )
    return state.model_copy(
        update={
            "artifacts": {
                "evidence_sufficiency_report": str(report_path),
                "evidence_sufficiency_decision_trace": str(trace_path),
            }
        }
    )


class AgenticAuthoringConstraintsTests(unittest.TestCase):
    def test_text_revision_brief_preserves_verifier_keep_and_remove_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "text_validation.json"
            report_path.write_text(
                json.dumps(
                    {
                        "verdicts": [
                            {
                                "atomic_claim_id": "T1",
                                "status": "unsupported",
                                "supported_fragment": "Load the base configuration.",
                                "unsupported_fragment": "to resolve all settings",
                                "matched_projection_claim_ids": ["C1", "C5"],
                                "deterministic_failures": ["semantic_verifier_rejected_claim"],
                                "repair_action": "revise_authoring_from_verifier_fragments",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            state.artifacts["text_evidence_validation"] = str(report_path)

            brief = _text_revision_brief(state)

        self.assertIn('"keep_supported_fragment": "Load the base configuration."', brief)
        self.assertIn('"remove_or_rewrite_text": "to resolve all settings"', brief)
        self.assertIn('"matched_projection_claim_ids": [', brief)
        self.assertIn("Never reintroduce", brief)

    def test_constraints_split_allowed_caveated_and_excluded_claims(self) -> None:
        report = build_claim_verification_report(_method_evidence(), _claim_map())
        constraints = build_authoring_constraints(report)

        self.assertEqual(constraints.allowed_claim_ids, ["C1"])
        self.assertEqual(constraints.caveated_claim_ids, ["C3"])
        self.assertEqual(constraints.excluded_claim_ids, ["C2"])
        self.assertEqual(constraints.missing_evidence_claim_ids, ["C2"])

    def test_apply_constraints_filters_authoring_claim_map_without_mutating_frozen_inputs(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        report = build_claim_verification_report(method_evidence, claim_map)

        constrained_evidence, constrained_claim_map, constraints = apply_authoring_constraints(
            method_evidence=method_evidence,
            claim_map=claim_map,
            report=report,
        )

        self.assertEqual([claim.claim_id for claim in claim_map.claims], ["C1", "C2", "C3"])
        self.assertEqual([claim.claim_id for claim in constrained_claim_map.claims], ["C1", "C3"])
        self.assertIn("C2", constraints.excluded_claim_ids)
        self.assertTrue(any("Agentic excluded claim ids: C2" in rule for rule in constrained_evidence.writing_constraints))

    def test_constraints_round_trip_to_json(self) -> None:
        report = build_claim_verification_report(_method_evidence(), _claim_map())
        constraints = build_authoring_constraints(report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "authoring_constraints.json"
            write_authoring_constraints(output, constraints)
            loaded = load_authoring_constraints(output)

        self.assertEqual(loaded.excluded_claim_ids, ["C2"])

    def test_authoring_context_summarizes_author_goal_and_claim_boundaries(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        report = build_claim_verification_report(method_evidence, claim_map)
        constraints = build_authoring_constraints(report)

        context = build_authoring_context(
            method_evidence=method_evidence,
            claim_map=claim_map,
            verification=report,
            constraints=constraints,
        )
        brief = authoring_context_brief(context)

        self.assertTrue(context.hard_gate_passed)
        self.assertEqual([claim.claim_id for claim in context.allowed_claims], ["C1"])
        self.assertEqual([claim.claim_id for claim in context.caveated_claims], ["C3"])
        self.assertEqual([claim.claim_id for claim in context.excluded_claims], ["C2"])
        self.assertIn("Explain the implementation", brief)
        self.assertIn("Allowed claims", brief)
        self.assertIn("Excluded claim ids", brief)
        self.assertNotIn("unsupported extra behavior", brief)
        plan = build_authoring_plan(context)
        self.assertTrue(plan.hard_gate_passed)
        self.assertEqual([section.claim_ids for section in plan.sections], [["C1"], ["C3"]])

    def test_authoring_stage_blocks_without_evidence_sufficiency_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            method_output(state.method_root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(state.method_root, "evidence").write_text(
                _method_evidence().model_dump_json(indent=2),
                encoding="utf-8",
            )
            method_output(state.method_root, "claims").write_text(
                _claim_map().model_dump_json(indent=2),
                encoding="utf-8",
            )

            result = _run_authoring(state)

        self.assertEqual(result.status, StageStatus.BLOCKED)
        self.assertEqual(result.blocked_reason, "pre_authoring_authorization_missing")
        self.assertIn("evidence_sufficiency_report", result.summary)
        self.assertIn("evidence_sufficiency_decision_trace", result.summary)

    def test_authoring_spec_requires_evidence_sufficiency_authorization(self) -> None:
        specs = {spec.stage: spec for spec in canonical_stage_tool_specs()}

        self.assertIn("evidence_sufficiency_report", specs["authoring"].input_artifacts)
        self.assertIn("evidence_sufficiency_decision_trace", specs["authoring"].input_artifacts)
        self.assertTrue(specs["authoring"].hard_gate)

    def test_legacy_authoring_bridge_passes_constrained_claim_map_to_writer(self) -> None:
        captured_claim_ids: list[str] = []
        captured_grounding_context: list[str] = []

        def fake_write_phase5_artifacts(**kwargs):
            claim_map = kwargs["claim_map"]
            captured_claim_ids.extend(claim.claim_id for claim in claim_map.claims)
            captured_grounding_context.append(kwargs["grounding_context_markdown"])
            output = method_output(kwargs["method_root"], "text_md")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("# Method\n\nEvidence-backed draft.\n", encoding="utf-8")
            manifest = method_output(kwargs["method_root"], "phase5_manifest")
            manifest.write_text(json.dumps({"mode": "fake"}), encoding="utf-8")
            return "# Method\n", "\\section{Method}", {"text_md": output, "phase5_manifest": manifest}

        with tempfile.TemporaryDirectory() as tmpdir, patch(
            "code2paper.agentic.legacy_authoring_stage_tool.write_phase5_artifacts",
            side_effect=fake_write_phase5_artifacts,
        ):
            state = AgenticRunState(project_root=Path("."), out_root=Path(tmpdir))
            method_output(state.method_root, "evidence").parent.mkdir(parents=True, exist_ok=True)
            method_output(state.method_root, "evidence").write_text(
                _method_evidence().model_dump_json(indent=2),
                encoding="utf-8",
            )
            method_output(state.method_root, "claims").write_text(
                _claim_map().model_dump_json(indent=2),
                encoding="utf-8",
            )
            state = _authorize_authoring(state)

            result = _run_authoring(state)
            constraints_path = Path(result.artifacts["authoring_constraints"])
            constraints = json.loads(constraints_path.read_text(encoding="utf-8"))
            context = load_authoring_context(result.artifacts["authoring_context"])
            plan = load_authoring_plan(result.artifacts["authoring_plan"])

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(captured_claim_ids, ["C1", "C3"])
        self.assertIn("Authoring input projection", captured_grounding_context[0])
        self.assertIn("Evidence-bound Method writing plan", captured_grounding_context[0])
        self.assertNotIn("C2", captured_grounding_context[0])
        self.assertNotIn("unsupported extra behavior", captured_grounding_context[0])
        self.assertEqual(constraints["excluded_claim_ids"], ["C2"])
        self.assertEqual([claim.claim_id for claim in context.allowed_claims], ["C1"])
        self.assertEqual([section.claim_ids for section in plan.sections], [["C1"], ["C3"]])
        self.assertIn("authoring_context", result.artifacts)
        self.assertIn("authoring_plan", result.artifacts)
        self.assertIn("authoring_plan_decision_trace", result.artifacts)
        self.assertIn("authoring_projection", result.artifacts)


if __name__ == "__main__":
    unittest.main()
