from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.authoring_context import EvidenceBoundAuthoringClaim, EvidenceBoundAuthoringContext
from code2paper.agentic.authoring_plan import (
    authoring_plan_brief,
    build_authoring_plan,
    load_authoring_plan,
    write_authoring_plan,
)
from code2paper.agentic.authoring_plan_decisioning import authoring_plan_trace


class AgenticAuthoringPlanTests(unittest.TestCase):
    def test_plan_uses_only_allowed_and_caveated_claims(self) -> None:
        context = EvidenceBoundAuthoringContext(
            method_name="Demo",
            author_goal="Explain demo.",
            allowed_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C1",
                    claim_text="The encoder uses attention.",
                    support_status="supported",
                    evidence_ids=["E1"],
                    writing_boundary="safe_to_write",
                )
            ],
            caveated_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C2",
                    claim_text="The encoder partially exposes weighting.",
                    support_status="partial",
                    evidence_ids=["E2"],
                    caveats=["Only the weighting fragment is implemented."],
                    writing_boundary="write_only_with_caveats",
                )
            ],
            excluded_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C3",
                    claim_text="Unsupported behavior.",
                    support_status="unsupported",
                    writing_boundary="do_not_write_as_method_claim",
                )
            ],
        )

        plan = build_authoring_plan(context)
        brief = authoring_plan_brief(plan)

        self.assertTrue(plan.hard_gate_passed)
        self.assertEqual([section.claim_ids for section in plan.sections], [["C1"], ["C2"]])
        self.assertEqual(plan.excluded_claim_ids, ["C3"])
        self.assertTrue(plan.sections[1].caveat_required)
        self.assertIn("Evidence-bound Method writing plan", brief)
        self.assertIn("Excluded claim ids not allowed", brief)

    def test_plan_blocks_when_no_safe_sections_exist(self) -> None:
        plan = build_authoring_plan(EvidenceBoundAuthoringContext(method_name="Demo"))

        self.assertFalse(plan.hard_gate_passed)
        self.assertIn("return_to_analysis_for_evidence_backed_authoring_claims", plan.recommended_actions)

    def test_plan_round_trips_json(self) -> None:
        context = EvidenceBoundAuthoringContext(
            method_name="Demo",
            allowed_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C1",
                    claim_text="Supported.",
                    support_status="supported",
                    evidence_ids=["E1"],
                    writing_boundary="safe_to_write",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "agentic_authoring_plan.json"
            write_authoring_plan(path, build_authoring_plan(context))
            loaded = load_authoring_plan(path)

        self.assertEqual(loaded.mode, "evidence-bound-authoring-plan")
        self.assertEqual(loaded.sections[0].claim_ids, ["C1"])

    def test_model_plan_proposal_is_safety_merged_against_context(self) -> None:
        context = EvidenceBoundAuthoringContext(
            method_name="Demo",
            author_goal="Explain demo.",
            allowed_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C1",
                    claim_text="The encoder uses attention.",
                    support_status="supported",
                    evidence_ids=["E1"],
                    writing_boundary="safe_to_write",
                )
            ],
            caveated_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C2",
                    claim_text="The encoder partially exposes weighting.",
                    support_status="partial",
                    evidence_ids=["E2"],
                    caveats=["Only the weighting fragment is implemented."],
                    writing_boundary="write_only_with_caveats",
                )
            ],
            excluded_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C3",
                    claim_text="Unsupported behavior.",
                    support_status="unsupported",
                    evidence_ids=["E3"],
                    writing_boundary="do_not_write_as_method_claim",
                )
            ],
        )

        plan, trace = authoring_plan_trace(
            context,
            decision_provider=lambda _prompt: {
                "rationale": "Put the supported section first.",
                "sections": [
                    {
                        "heading": "Model heading",
                        "claim_ids": ["C1", "C3"],
                        "evidence_ids": ["E404"],
                        "writing_instructions": ["Use a compact implementation-first structure."],
                    }
                ],
            },
        )

        self.assertTrue(plan.hard_gate_passed)
        self.assertEqual(plan.sections[0].claim_ids, ["C1"])
        self.assertEqual(plan.sections[0].evidence_ids, ["E1"])
        self.assertEqual(plan.sections[1].claim_ids, ["C2"])
        self.assertTrue(plan.sections[1].caveat_required)
        self.assertEqual(trace.node, "authoring_planner")
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertIn("C3", trace.provider_payload["sections"][0]["claim_ids"])
        self.assertTrue(any("Appended fallback sections" in note for note in trace.safety_notes))

    def test_authoring_plan_prompt_exposes_evidence_attention(self) -> None:
        context = EvidenceBoundAuthoringContext(
            method_name="Demo",
            allowed_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C1",
                    claim_text="Supported.",
                    support_status="supported",
                    evidence_ids=["E1"],
                    writing_boundary="safe_to_write",
                )
            ],
            caveated_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C2",
                    claim_text="Partial.",
                    support_status="partial",
                    evidence_ids=["E2"],
                    caveats=["Only the parser branch is implemented."],
                    writing_boundary="write_only_with_caveats",
                )
            ],
            excluded_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C3",
                    claim_text="Unsupported.",
                    support_status="unsupported",
                    writing_boundary="do_not_write_as_method_claim",
                )
            ],
        )

        _plan, trace = authoring_plan_trace(context)

        attention = trace.prompt.inputs["authoring_evidence_attention"]
        tool_guidance = trace.prompt.inputs["stage_tool_guidance"]
        self.assertEqual(attention["allowed_claim_count"], 1)
        self.assertEqual(attention["caveated_claim_count"], 1)
        self.assertEqual(attention["excluded_claim_ids"], ["C3"])
        self.assertEqual(attention["claim_evidence"][0]["claim_id"], "C1")
        self.assertEqual(attention["claim_evidence"][0]["evidence_ids"], ["E1"])
        self.assertEqual(attention["claim_evidence"][1]["writing_boundary"], "write_only_with_caveats")
        self.assertIn("authoring", tool_guidance)
        self.assertIn("evidence_sufficiency_report", tool_guidance["authoring"]["required_inputs"])
        self.assertIn("hard evidence gate", tool_guidance["authoring"]["invocation_contract"])

    def test_invalid_model_plan_falls_back_to_deterministic_plan(self) -> None:
        context = EvidenceBoundAuthoringContext(
            method_name="Demo",
            allowed_claims=[
                EvidenceBoundAuthoringClaim(
                    claim_id="C1",
                    claim_text="Supported.",
                    support_status="supported",
                    evidence_ids=["E1"],
                    writing_boundary="safe_to_write",
                )
            ],
        )

        plan, trace = authoring_plan_trace(context, decision_provider=lambda _prompt: {"sections": []})

        self.assertEqual([section.claim_ids for section in plan.sections], [["C1"]])
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertEqual(trace.final_decision["sections"][0]["claim_ids"], ["C1"])


if __name__ == "__main__":
    unittest.main()
