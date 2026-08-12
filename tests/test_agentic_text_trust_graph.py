from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.graph_text_trust_nodes import (
    _eligible_repair_claim_ids,
    _select_round_robin_claim,
    final_text_claim_extractor_node,
    local_text_repair_node,
    packet_binding_repair_node,
    text_evidence_validator_node,
    text_trace_builder_node,
)
from code2paper.agentic.graph_topology import CONDITIONAL_ROUTE_SPECS, DIRECT_EDGE_SPECS
from code2paper.agentic.rewrite_agent import LocalRewriteAgent
from code2paper.agentic.trust_contracts import (
    AuthoringInputProjection,
    FinalAtomicClaim,
    FinalTextClaims,
    FinalTextUnit,
    ProjectedClaim,
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType
from code2paper.llm.client import LLMResponse


def _rewrite_agent(patch_builder) -> LocalRewriteAgent:
    def caller(_config, request):
        patch = patch_builder(request.input_payload)
        return LLMResponse(
            text=json.dumps({"patches": [patch], "self_identified_risks": [], "incomplete": False}),
            response_hash="sha256:local-rewrite-response",
            finish_reason="stop",
            token_usage={"completion_tokens": 80},
        )

    return LocalRewriteAgent(caller=caller)


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


def test_text_trust_direct_edge_chain_preserves_upstream_blocked_reason(tmp_path: Path) -> None:
    state = AgenticRunState(
        project_root=tmp_path,
        out_root=tmp_path / "out",
        blocked_reason="authoring_projection_v3_required",
    )

    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = text_evidence_validator_node(extracted)
    traced = AgenticRunState.model_validate(text_trace_builder_node(validated))

    assert traced.next_node == "blocked"
    assert traced.blocked_reason == "authoring_projection_v3_required"
    assert not traced.artifacts


def test_text_trust_nodes_block_unrelated_direct_evidence_when_budget_is_zero(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="License and redistribution terms only.")
    result = _run_gate(state)

    assert result.next_node == "blocked"
    assert result.blocked_reason == "text_claim_packet_binding_repair_budget_exhausted"
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


def test_packet_failure_emits_typed_scoped_request_without_global_rerun(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="License and redistribution terms only.")
    state = state.model_copy(update={"max_authoring_revision_rounds": 1})
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = text_evidence_validator_node(extracted)
    traced = AgenticRunState.model_validate(text_trace_builder_node(validated))

    assert traced.next_node == "local_text_repair"
    repaired = AgenticRunState.model_validate(local_text_repair_node(traced.model_dump(mode="json")))
    assert repaired.next_node == "packet_binding_repair"
    payload = json.loads(Path(repaired.artifacts["packet_repair_requests_v1"]).read_text())
    assert payload["requests"] == [{
        "claim_id": "FAC1",
        "source_claim_ids": ["C1"],
        "packet_id": "",
        "failure_type": "wrong_span_role",
        "offending_span_ids": ["E1"],
        "missing_relation_type": "relation_evidence: none",
        "requested_scope": "packet_relation",
        "attempt": 1,
    }]
    blocked = AgenticRunState.model_validate(packet_binding_repair_node(repaired.model_dump(mode="json")))
    assert blocked.next_node == "blocked"
    assert (
        blocked.blocked_reason
        == "packet_scoped_repair_requires_research_owner"
    )


def test_text_failure_routes_cannot_reenter_global_pipeline_stages() -> None:
    routes = {
        route.source: {target for _decision, target in route.routes}
        for route in CONDITIONAL_ROUTE_SPECS
        if route.source in {"text_trace_builder", "local_text_repair"}
    }
    forbidden = {"input_resolution", "intake", "analysis", "evidence", "grounding", "authoring"}
    assert routes["text_trace_builder"].isdisjoint(forbidden)
    assert routes["local_text_repair"].isdisjoint(forbidden)


def test_missing_planned_claim_is_inserted_locally_without_full_authoring(tmp_path: Path) -> None:
    state = _write_inputs(
        tmp_path,
        evidence_summary="The encoder reads configured features and returns configured outputs.",
    )
    projection_path = Path(state.artifacts["authoring_projection"])
    projection = AuthoringInputProjection.model_validate_json(projection_path.read_text())
    projection = projection.model_copy(update={
        "projected_claims": [
            *projection.projected_claims,
            ProjectedClaim(
                claim_id="C2",
                claim_text="The encoder returns configured outputs.",
                support_status="supported",
                direct_evidence_ids=["E1"],
                supported_fragment="The encoder returns configured outputs.",
                allowed_wording_boundary="The encoder returns configured outputs.",
                input_digest="sha256:claim-2",
            ),
        ],
    })
    projection_path.write_text(projection.model_dump_json(indent=2), encoding="utf-8")
    plan_path = tmp_path / "authoring_plan_v3.json"
    plan_path.write_text(json.dumps({
        "sections": [{
            "heading": "Core stage",
            "claim_ids": ["C1", "C2"],
        }],
    }), encoding="utf-8")
    text_path = Path(state.artifacts["text_clean_md"])
    text_path.write_text(
        "# Method\n## Core stage\nThe encoder reads configured features.\n",
        encoding="utf-8",
    )
    state = state.model_copy(update={
        "artifacts": {**state.artifacts, "authoring_plan_v3": str(plan_path)},
        "max_authoring_revision_rounds": 1,
    })

    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = AgenticRunState.model_validate(text_evidence_validator_node(extracted))
    report = json.loads(Path(validated.artifacts["text_evidence_validation"]).read_text())
    assert report["status"] == "failed"
    assert report["recommended_actions"] == ["insert_planned_claim_locally:C2"]
    traced = AgenticRunState.model_validate(text_trace_builder_node(validated.model_dump(mode="json")))
    assert traced.next_node == "local_text_repair"
    def insertion_patch(payload):
        text = payload["incumbent_text"]
        return {
            "patch_id": "patch-insert-c2",
            "start": len(text),
            "end": len(text),
            "original_text": "",
            "replacement_text": "The encoder returns configured outputs.\n",
            "issue_ids": ["MISSING:C2"],
            "allowed_scope": "claim_decomposition",
        }

    repaired = AgenticRunState.model_validate(local_text_repair_node(
        traced.model_dump(mode="json"),
        rewrite_agent=_rewrite_agent(insertion_patch),
    ))
    assert repaired.next_node == "final_text_claim_extractor"
    repaired_text = text_path.read_text()
    assert "The encoder returns configured outputs." in repaired_text
    assert repaired_text.count("# Method") == 1


def test_wording_repair_deletes_redundant_failed_sibling_instead_of_duplicating_claim(
    tmp_path: Path,
) -> None:
    state = _write_inputs(
        tmp_path,
        evidence_summary="Only when seed_entities is empty, retrieval bypasses graph propagation.",
    )
    text = (
        "Only when seed_entities is empty, retrieval bypasses graph propagation and "
        "When NER is empty, retrieval bypasses graph propagation.\n"
    )
    text_path = Path(state.artifacts["text_clean_md"])
    text_path.write_text(text, encoding="utf-8")
    projection_path = Path(state.artifacts["authoring_projection"])
    projection = AuthoringInputProjection.model_validate_json(projection_path.read_text())
    projection = projection.model_copy(update={
        "projected_claims": [
            projection.projected_claims[0].model_copy(update={
                "supported_fragment": "Only when seed_entities is empty, retrieval bypasses graph propagation.",
                "required_qualifiers": ["only when seed_entities is empty"],
            })
        ],
    })
    projection_path.write_text(projection.model_dump_json(indent=2), encoding="utf-8")

    supported = "Only when seed_entities is empty, retrieval bypasses graph propagation"
    unsupported = "When NER is empty, retrieval bypasses graph propagation"
    unsupported_start = text.index(unsupported)
    final_claims = FinalTextClaims(
        input_text_digest="sha256:text",
        units=[FinalTextUnit(
            unit_id="FTU1", kind="sentence", text=text.strip(), line_start=1, line_end=1,
            char_start=0, char_end=len(text.strip()), factual=True, span_digest="sha256:unit",
        )],
        atomic_claims=[
            FinalAtomicClaim(
                atomic_claim_id="FAC1", unit_id="FTU1", text=supported,
                normalized_text=supported.lower(), line_start=1, line_end=1,
                char_start=0, char_end=len(supported), candidate_projection_claim_ids=["C1"],
                candidate_direct_evidence_ids=["E1"], claim_digest="sha256:fac1",
            ),
            FinalAtomicClaim(
                atomic_claim_id="FAC2", unit_id="FTU1", text=unsupported,
                normalized_text=unsupported.lower(), line_start=1, line_end=1,
                char_start=unsupported_start, char_end=unsupported_start + len(unsupported),
                candidate_projection_claim_ids=["C1"], candidate_direct_evidence_ids=["E1"],
                claim_digest="sha256:fac2",
            ),
        ],
    )
    validation = TextEvidenceValidationReport(
        status="failed", input_text_digest="sha256:text", projection_digest="sha256:projection",
        checked_factual_claims=2, supported_claims=1, unsupported_claims=1,
        verdicts=[
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC1", status="supported", matched_projection_claim_ids=["C1"],
                direct_evidence_ids=["E1"], supported_fragment=supported,
            ),
            TextClaimEvidenceVerdict(
                atomic_claim_id="FAC2", status="unsupported", matched_projection_claim_ids=["C1"],
                direct_evidence_ids=["E1"], unsupported_fragment=unsupported,
                required_qualifiers=["only when seed_entities is empty"],
                deterministic_failures=["required_qualifier_missing"],
                repair_action="revise_authoring_wording",
            ),
        ],
        recommended_actions=["revise_authoring_wording"],
    )
    claims_path = tmp_path / "final_claims.json"
    validation_path = tmp_path / "validation.json"
    claims_path.write_text(final_claims.model_dump_json(indent=2), encoding="utf-8")
    validation_path.write_text(validation.model_dump_json(indent=2), encoding="utf-8")
    state = state.model_copy(update={
        "artifacts": {
            **state.artifacts,
            "final_text_claims": str(claims_path),
            "text_evidence_validation": str(validation_path),
        },
        "max_authoring_revision_rounds": 1,
    })

    def wording_patch(payload):
        incumbent = payload["incumbent_text"]
        return {
            "patch_id": "patch-rewrite-compound",
            "start": 0,
            "end": len(incumbent),
            "original_text": incumbent,
            "replacement_text": supported + ".\n",
            "issue_ids": ["FAC2"],
            "allowed_scope": "wording_only",
        }

    repaired = AgenticRunState.model_validate(local_text_repair_node(
        state.model_dump(mode="json"),
        rewrite_agent=_rewrite_agent(wording_patch),
    ))
    repaired_text = text_path.read_text(encoding="utf-8")

    assert repaired.next_node == "final_text_claim_extractor"
    assert unsupported not in repaired_text
    assert repaired_text.count("Only when seed_entities is empty") == 1
    rewrite_result = json.loads(Path(repaired.artifacts["local_rewrite_result_v1"]).read_text())
    assert rewrite_result["status"] == "applied"
    assert rewrite_result["generation_trace"]["role"] == "local_rewrite"


def test_invalid_rewrite_patch_preserves_incumbent_and_records_transition(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="Only configured inputs are read.")
    text_path = Path(state.artifacts["text_clean_md"])
    incumbent = text_path.read_text(encoding="utf-8")
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = AgenticRunState.model_validate(text_evidence_validator_node(extracted))
    # Force a wording issue while keeping the fixture compact.
    report = TextEvidenceValidationReport.model_validate_json(
        Path(validated.artifacts["text_evidence_validation"]).read_text()
    ).model_copy(update={
        "status": "failed",
        "verdicts": [TextClaimEvidenceVerdict(
            atomic_claim_id="FAC1",
            status="unsupported",
            matched_projection_claim_ids=["C1"],
            direct_evidence_ids=["E1"],
            unsupported_fragment=incumbent.strip(),
            deterministic_failures=["required_qualifier_missing"],
            repair_action="revise_authoring_wording",
        )],
    })
    validation_path = Path(validated.artifacts["text_evidence_validation"])
    validation_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    validated = validated.model_copy(update={"max_authoring_revision_rounds": 1})

    def stale_patch(_payload):
        return {
            "patch_id": "patch-stale",
            "start": 0,
            "end": 4,
            "original_text": "WRONG",
            "replacement_text": "Safe",
            "issue_ids": ["FAC1"],
            "allowed_scope": "wording_only",
        }

    result = AgenticRunState.model_validate(local_text_repair_node(
        validated.model_dump(mode="json"),
        rewrite_agent=_rewrite_agent(stale_patch),
    ))

    assert result.next_node == "blocked"
    assert text_path.read_text(encoding="utf-8") == incumbent
    transition = json.loads(Path(result.artifacts["repair_transition_v1"]).read_text())
    assert transition["status"] == "rejected"


def test_repair_budget_is_per_claim_and_selection_rotates(tmp_path: Path) -> None:
    state = _write_inputs(tmp_path, evidence_summary="The encoder reads configured features.")
    state = state.model_copy(update={
        "max_authoring_revision_rounds": 2,
        "loop_counters": {
            "local_text_repair:FAC1": 2,
            "local_text_repair:FAC2": 0,
            "local_text_repair:FAC3": 0,
            "local_text_repair_cursor": 1,
        },
    })
    report = TextEvidenceValidationReport(
        status="failed",
        input_text_digest="sha256:text",
        projection_digest="sha256:projection",
        checked_factual_claims=3,
        unsupported_claims=3,
        verdicts=[
            TextClaimEvidenceVerdict(
                atomic_claim_id=claim_id,
                status="unsupported",
                deterministic_failures=["required_qualifier_missing"],
            )
            for claim_id in ("FAC1", "FAC2", "FAC3")
        ],
    )

    assert _eligible_repair_claim_ids(state, report) == ["FAC2", "FAC3"]
    selected, next_cursor = _select_round_robin_claim(state, report)
    assert selected == "FAC3"
    assert next_cursor == 2


def test_rewrite_candidate_that_adds_duplicate_claim_is_rejected_before_write(tmp_path: Path) -> None:
    state = _write_inputs(
        tmp_path,
        evidence_summary="The encoder reads configured features from configuration.",
    ).model_copy(update={"max_authoring_revision_rounds": 1})
    text_path = Path(state.artifacts["text_clean_md"])
    incumbent = text_path.read_text(encoding="utf-8")
    extracted = final_text_claim_extractor_node(state.model_dump(mode="json"))
    validated = AgenticRunState.model_validate(text_evidence_validator_node(extracted))
    report = TextEvidenceValidationReport.model_validate_json(
        Path(validated.artifacts["text_evidence_validation"]).read_text()
    ).model_copy(update={
        "status": "failed",
        "unsupported_claims": 1,
        "supported_claims": 0,
        "verdicts": [TextClaimEvidenceVerdict(
            atomic_claim_id="FAC1",
            status="unsupported",
            matched_projection_claim_ids=["C1"],
            direct_evidence_ids=["E1"],
            unsupported_fragment=incumbent.strip(),
            deterministic_failures=["required_qualifier_missing"],
        )],
    })
    validation_path = Path(validated.artifacts["text_evidence_validation"])
    validation_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    validated = validated.model_copy(update={"max_authoring_revision_rounds": 1})

    def duplicate_patch(payload):
        text = payload["incumbent_text"]
        return {
            "patch_id": "patch-duplicate",
            "start": 0,
            "end": len(text),
            "original_text": text,
            "replacement_text": text + text,
            "issue_ids": ["FAC1"],
            "allowed_scope": "wording_only",
        }

    result = AgenticRunState.model_validate(local_text_repair_node(
        validated.model_dump(mode="json"),
        rewrite_agent=_rewrite_agent(duplicate_patch),
    ))

    assert result.next_node == "blocked"
    assert result.blocked_reason == "rewrite_candidate_hard_gate_failed"
    assert text_path.read_text(encoding="utf-8") == incumbent
    rewrite_result = json.loads(Path(result.artifacts["local_rewrite_result_v1"]).read_text())
    assert "candidate_adds_duplicate_claim" in rewrite_result["patch_failures"]
