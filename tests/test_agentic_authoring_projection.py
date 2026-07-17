from __future__ import annotations

import json

from code2paper.agentic.authoring_projection import (
    build_authoring_projection,
    projected_writer_inputs,
    projection_writer_payload,
)
from code2paper.agentic.claim_verifier import build_claim_verification_report
from code2paper.authoring.writing.method_writer import build_method_draft_markdown
from code2paper.core.schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    Mechanism,
    MethodEvidence,
    MethodStageEvidence,
    SupportStatus,
)


def _evidence() -> MethodEvidence:
    return MethodEvidence(
        project_id="projection-test",
        method_name="Projection Method",
        method_goal="Claim unsupported 99% acceleration while describing the encoder.",
        implementation_scope="test",
        stages=[
            MethodStageEvidence(
                stage_id="S1",
                name="Encode",
                purpose="Unsupported 99% acceleration.",
                mechanisms=[
                    Mechanism(
                        mechanism_id="MECH1",
                        description="The encoder reads configured features.",
                        support_status=SupportStatus.SUPPORTED,
                        evidence_ids=["E1"],
                    )
                ],
            )
        ],
        stage_packets=[
            {
                "stage_id": "S1",
                "name": "Encode",
                "purpose": "Unsupported 99% acceleration.",
                "claim_ids": ["C1", "C2"],
                "evidence_span_ids": ["E1", "E404"],
                "stage_claim": "Unsupported 99% acceleration.",
            }
        ],
        innovation_candidates=[{"claim": "Unsupported 99% acceleration."}],
    )


def _claims() -> ClaimEvidenceMap:
    return ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The method provides unsupported 99% acceleration.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E404"],
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The encoder exposes only the configured feature path.",
                support_status=SupportStatus.PARTIAL,
                evidence_ids=["E1"],
                caveats=["Only the configured path is implemented."],
            ),
        ]
    )


def test_projection_recursively_removes_forbidden_positive_wording() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )

    positive_payload = json.dumps(projection_writer_payload(projection), ensure_ascii=False)
    assert "unsupported 99% acceleration" not in positive_payload.lower()
    assert [claim.claim_id for claim in projection.projected_claims] == ["C1", "C3"]
    assert [claim.claim_id for claim in projection.forbidden_claims] == ["C2"]
    assert projection.forbidden_claims[0].model_dump().get("claim_text") is None
    assert len(projection.stage_packets) == 1
    assert projection.stage_packets[0]["stage_id"] == "S1"
    assert set(projection.stage_packets[0]["claim_ids"]) == {"C1", "C3"}
    assert projection.stage_packets[0]["evidence_span_ids"] == ["E1"]
    assert "guarantees impossible speedups" not in str(projection.stage_packets[0]).lower()


def test_partial_projection_keeps_supported_fragment_and_qualifier() -> None:
    evidence = _evidence()
    claims = _claims()
    projection = build_authoring_projection(
        method_evidence=evidence,
        claim_map=claims,
        verification=build_claim_verification_report(evidence, claims),
    )
    partial = next(claim for claim in projection.projected_claims if claim.claim_id == "C3")

    assert partial.support_status == "partial"
    assert partial.required_qualifiers == ["Only the configured path is implemented."]
    writer_evidence, writer_claims = projected_writer_inputs(projection, template=evidence)
    assert [stage.stage_id for stage in writer_evidence.stages] == ["S1"]
    assert writer_evidence.stages[0].purpose == projection.stage_packets[0]["purpose"]
    assert writer_evidence.innovation_candidates == []
    assert [claim.claim_id for claim in writer_claims.claims] == ["C1", "C3"]


def test_projection_writer_deduplicates_claims_and_omits_stage_contract_metadata() -> None:
    evidence = _evidence()
    evidence.writing_constraints.append(
        "The projection is the writer's only positive method-fact input."
    )
    evidence.stage_packets[0]["claim_ids"] = ["C1", "C2", "C3", "C4"]
    claims = ClaimEvidenceMap(
        claims=[
            ClaimEvidenceItem(
                claim_id="C1",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="method_mechanism",
            ),
            ClaimEvidenceItem(
                claim_id="C2",
                claim_text="The method contains a paper-facing stage named Encode.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="claim_contract:C1",
            ),
            ClaimEvidenceItem(
                claim_id="C3",
                claim_text="The encoder reads configured features.",
                support_status=SupportStatus.SUPPORTED,
                evidence_ids=["E1"],
                source="claim_contract:C2",
                caveats=["Only the configured path is implemented."],
            ),
            ClaimEvidenceItem(
                claim_id="C4",
                claim_text="Unsupported duplicate.",
                support_status=SupportStatus.UNSUPPORTED,
                evidence_ids=[],
                source="author_claim:none",
            ),
        ]
    )

    draft = build_method_draft_markdown(evidence, claims)

    assert draft.count("The encoder reads configured features") == 1
    assert "Only the configured path is implemented." in draft
    assert "paper-facing stage named" not in draft
    assert "Unsupported duplicate" not in draft
