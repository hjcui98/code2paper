from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.graph_text_trust_nodes import (
    final_text_claim_extractor_node,
    text_evidence_validator_node,
    text_trace_builder_node,
)
from code2paper.agentic.graph_topology import DIRECT_EDGE_SPECS
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ProjectedClaim
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType


def _write_inputs(root: Path, *, evidence_summary: str) -> AgenticRunState:
    text = root / "method_clean.md"
    projection_path = root / "projection.json"
    evidence_path = root / "evidence_raw.json"
    text.write_text("The encoder reads configured features.\n", encoding="utf-8")
    projection = AuthoringInputProjection(
        project_id="demo",
        method_name="Demo",
        author_goal="Use projected claims.",
        implementation_scope="test",
        projected_claims=[
            ProjectedClaim(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status="supported",
                direct_evidence_ids=["E1"],
                supported_fragment="The encoder reads configured features.",
                allowed_wording_boundary="The encoder reads configured features.",
                input_digest="sha256:claim",
            )
        ],
        projection_digest="sha256:projection",
    )
    projection_path.write_text(projection.model_dump_json(indent=2), encoding="utf-8")
    raw = RawEvidencePack(
        project_id="demo",
        project_root="/repo",
        evidence_items=[
            EvidenceItem(
                evidence_id="E1",
                source_type=SourceType.SOURCE,
                path="encoder.py",
                symbol="read_features",
                line_start=1,
                line_end=4,
                content_summary=evidence_summary,
                confidence=0.9,
            )
        ],
    )
    evidence_path.write_text(raw.model_dump_json(indent=2), encoding="utf-8")
    return AgenticRunState(
        project_root=root,
        out_root=root / "out",
        artifacts={
            "text_clean_md": str(text),
            "authoring_projection": str(projection_path),
            "evidence_raw": str(evidence_path),
        },
    )


def _run_gate(state: AgenticRunState) -> AgenticRunState:
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = text_evidence_validator_node(extracted)
    return AgenticRunState.model_validate(text_trace_builder_node(validated))


def test_text_trust_nodes_route_valid_final_text_to_quality_validation(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="The encoder reads configured features from configuration.")
    result = _run_gate(state)

    assert result.next_node == "validation"
    assert not result.blocked_reason
    assert set(("final_text_claims", "text_evidence_validation", "final_text_trace")).issubset(result.artifacts)
    report = json.loads(Path(result.artifacts["text_evidence_validation"]).read_text(encoding="utf-8"))
    assert report["status"] == "passed"


def test_text_trust_nodes_block_unrelated_direct_evidence_when_budget_is_zero(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="License and redistribution terms only.")
    result = _run_gate(state)

    assert result.next_node == "blocked"
    assert result.blocked_reason == "text_claim_direct_evidence_missing_budget_exhausted"
    assert "final_text_trace" in result.artifacts


def test_runtime_topology_places_text_gate_between_authoring_and_validation() -> None:
    edges = {(edge.source, edge.target) for edge in DIRECT_EDGE_SPECS}
    assert ("authoring", "validation") not in edges
    assert ("authoring", "final_text_claim_extractor") in edges
    assert ("final_text_claim_extractor", "text_evidence_validator") in edges
    assert ("text_evidence_validator", "text_trace_builder") in edges


def test_semantic_verifier_budget_is_global_and_exhaustion_blocks(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="The encoder reads configured features from configuration.")
    text_path = Path(state.artifacts["text_clean_md"])
    text_path.write_text(
        "The encoder reads configured features.\nThe encoder reads configured features.\n",
        encoding="utf-8",
    )
    state = state.model_copy(update={"max_semantic_verifier_calls": 1})
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = text_evidence_validator_node(
        extracted,
        semantic_verifier=lambda _payload: {"status": "supported", "rationale": "direct match"},
    )
    result = AgenticRunState.model_validate(validated)
    report = json.loads(Path(result.artifacts["text_evidence_validation"]).read_text(encoding="utf-8"))

    assert result.loop_counters["semantic_verifier"] == 1
    assert report["status"] == "failed"
    assert "semantic_verifier_budget_exhausted" in report["verdicts"][1]["deterministic_failures"]


def test_deterministic_provider_does_not_require_unavailable_model_verifier(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="The encoder reads configured features from configuration.")
    state = state.model_copy(update={"llm_provider": "none", "max_semantic_verifier_calls": 3})
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = text_evidence_validator_node(extracted, semantic_verifier=None)
    report = json.loads(Path(AgenticRunState.model_validate(validated).artifacts["text_evidence_validation"]).read_text())

    assert report["status"] == "passed"
    assert report["semantic_verifier_calls"] == 0
