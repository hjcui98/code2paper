from code2paper.core.schemas import (
    ClaimContract,
    ClaimEvidenceMap,
    ConflictStatus,
    DraftClaimMap,
    MethodEvidence,
    MethodOutline,
)
from code2paper.pipeline.stages.authoring import _normalize_draft_claim_map


def test_unbound_paragraph_does_not_receive_first_claim_or_evidence() -> None:
    evidence = MethodEvidence(
        project_id="demo",
        method_name="Demo",
        method_goal="Describe supported code.",
        implementation_scope="test",
        claim_contracts=[
            ClaimContract(
                claim_id="C1",
                claim_intent="The encoder reads features.",
                support_status=ConflictStatus.SUPPORTED,
                evidence_span_ids=["E1"],
                allowed_wording_boundary="The encoder reads features.",
            )
        ],
    )
    result = _normalize_draft_claim_map(
        draft_claim_map=DraftClaimMap(paragraphs=[{"paragraph_id": "UNBOUND"}]),
        outline=MethodOutline(),
        method_evidence=evidence,
        claim_map=ClaimEvidenceMap(),
    )

    paragraph = result.paragraphs[0]
    assert paragraph.claim_ids == []
    assert paragraph.evidence_span_ids == []
