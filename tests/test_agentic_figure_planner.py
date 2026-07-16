from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.figure_planner import (
    build_evidence_backed_figure_plan,
    figure_plan_brief,
    figure_plan_trace,
    load_figure_plan,
    write_figure_plan,
)
from code2paper.core.output_names import method_output
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)
from code2paper.rendering.figures.backend_paperbanana import _prepare_content_file


def _method_evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="demo",
        method_name="Demo Method",
        method_goal="Explain the implementation.",
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
            ),
            MethodStageEvidence(
                stage_id="S2",
                name="Prediction Head",
                purpose="Predict outputs.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH2",
                        description="Prediction head maps representations to outputs.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E2"],
                    )
                ],
            ),
            MethodStageEvidence(
                stage_id="S3",
                name="Unsupported Add-on",
                purpose="Unverified behavior.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH3",
                        description="Unsupported extra behavior.",
                        support_status=SupportStatus.UNSUPPORTED,
                        evidence_ids=[],
                    )
                ],
            ),
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
                source="method_mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The prediction head maps representations.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E2"],
                mechanism_ids=["MECH2"],
                source="method_mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The method has an unsupported add-on.",
                support_status=SupportStatus.UNSUPPORTED,
                evidence_ids=[],
                mechanism_ids=["MECH3"],
                source="method_mechanism",
            ),
        ]
    )


class AgenticFigurePlannerTests(unittest.TestCase):
    def test_figure_plan_keeps_only_evidence_backed_nodes_and_edges(self) -> None:
        method_evidence = _method_evidence()
        claim_map = _claim_map()
        verification = build_claim_verification_report(method_evidence, claim_map)

        plan = build_evidence_backed_figure_plan(
            method_evidence=method_evidence,
            claim_map=claim_map,
            claim_verification=verification,
        )

        self.assertTrue(plan.hard_gate_passed)
        self.assertEqual([node.stage_id for node in plan.nodes], ["S1", "S2"])
        self.assertEqual(plan.edges[0].source_node_id, "N1")
        self.assertEqual(plan.edges[0].target_node_id, "N2")
        self.assertEqual(plan.omitted_mechanism_ids, ["MECH3"])
        self.assertIn("C3", plan.omitted_claim_ids)
        self.assertTrue(all(node.evidence_ids for node in plan.nodes))
        self.assertTrue(all(edge.evidence_ids for edge in plan.edges))

    def test_figure_plan_brief_is_natural_language_contract(self) -> None:
        plan = build_evidence_backed_figure_plan(
            method_evidence=_method_evidence(),
            claim_map=_claim_map(),
        )
        brief = figure_plan_brief(plan)

        self.assertIn("Evidence-backed visual contract", brief)
        self.assertIn("Node N1", brief)
        self.assertIn("evidence=E1", brief)
        self.assertIn("Omit unverified claim ids", brief)

    def test_figure_plan_round_trips_to_json(self) -> None:
        plan = build_evidence_backed_figure_plan(method_evidence=_method_evidence(), claim_map=_claim_map())

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "method_overview.intent.json"
            write_figure_plan(output, plan)
            loaded = load_figure_plan(output)

        self.assertEqual(loaded.nodes[0].node_id, "N1")
        self.assertEqual(loaded.edges[0].edge_id, "FE1")

    def test_figure_plan_trace_safety_merges_model_proposal(self) -> None:
        prompts = []

        def provider(prompt):
            prompts.append(prompt)
            return {
                "rationale": "Put prediction first and add an unsupported visual.",
                "nodes": [
                    {
                        "node_id": "N2",
                        "stage_id": "S2",
                        "label": "Model proposed prediction",
                        "claim_ids": ["C2", "C404"],
                        "evidence_ids": ["E2", "E404"],
                    },
                    {
                        "node_id": "N404",
                        "stage_id": "S404",
                        "label": "Unsupported model addition",
                        "claim_ids": ["C404"],
                        "evidence_ids": ["E404"],
                    },
                ],
                "edges": [
                    {
                        "source_node_id": "N2",
                        "target_node_id": "N404",
                        "evidence_ids": ["E404"],
                    }
                ],
            }

        plan, trace = figure_plan_trace(
            method_evidence=_method_evidence(),
            claim_map=_claim_map(),
            decision_provider=provider,
        )

        self.assertEqual(prompts[0].node, "figure_planner")
        self.assertTrue(plan.hard_gate_passed)
        self.assertEqual([node.stage_id for node in plan.nodes], ["S2", "S1"])
        self.assertEqual(plan.nodes[0].claim_ids, ["C2"])
        self.assertEqual(plan.nodes[0].evidence_ids, ["E2"])
        self.assertNotIn("N404", [node.node_id for node in plan.nodes])
        self.assertTrue(any(edge.source_node_id == "N1" and edge.target_node_id == "N2" for edge in plan.edges))
        self.assertEqual(trace.node, "figure_planner")
        self.assertEqual(trace.provider_status, "model_proposal_merged")
        self.assertTrue(any("Dropped" in note for note in trace.safety_notes))
        self.assertTrue(any("Appended fallback figure nodes" in note for note in trace.safety_notes))

    def test_figure_plan_prompt_exposes_evidence_attention(self) -> None:
        _plan, trace = figure_plan_trace(
            method_evidence=_method_evidence(),
            claim_map=_claim_map(),
        )

        attention = trace.prompt.inputs["figure_evidence_attention"]
        self.assertEqual(attention["allowed_node_count"], 2)
        self.assertEqual(attention["allowed_edge_count"], 1)
        self.assertEqual(attention["omitted_claim_ids"], ["C3"])
        self.assertEqual(attention["nodes"][0]["node_id"], "N1")
        self.assertEqual(attention["nodes"][0]["stage_id"], "S1")
        self.assertEqual(attention["nodes"][0]["evidence_ids"], ["E1"])
        self.assertEqual(attention["edges"][0]["source_node_id"], "N1")
        self.assertEqual(attention["edges"][0]["target_node_id"], "N2")

    def test_paperbanana_content_file_includes_evidence_backed_visual_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            draft_path = tmp / "method.md"
            draft_path.write_text("# Method\n\n## Feature Encoding\nThe encoder uses attention.\n", encoding="utf-8")
            evidence_path = tmp / "method_evidence.json"
            claim_path = tmp / "claim_map.json"
            evidence_path.write_text(_method_evidence().model_dump_json(indent=2), encoding="utf-8")
            claim_path.write_text(_claim_map().model_dump_json(indent=2), encoding="utf-8")
            out_dir = tmp / "figures"
            out_dir.mkdir()

            content_path = _prepare_content_file(
                draft_path,
                out_dir,
                method_evidence_path=evidence_path,
                claim_map_path=claim_path,
                clean_tex_to_txt=True,
                semantic_anchor="",
                revision_note="",
            )
            content = content_path.read_text(encoding="utf-8")
            intent = json.loads((out_dir / "method_overview.intent.json").read_text(encoding="utf-8"))

        self.assertIn("Evidence-backed visual contract", content)
        self.assertEqual(intent["nodes"][0]["evidence_ids"], ["E1"])


if __name__ == "__main__":
    unittest.main()
