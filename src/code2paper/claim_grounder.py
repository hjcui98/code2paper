"""Claim grounding for method evidence and author claims."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import (
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    CodeAlignmentIR,
    MethodEvidence,
    SupportStatus,
)


def build_claim_evidence_map(
    method_evidence: MethodEvidence,
    alignment: CodeAlignmentIR | None = None,
) -> ClaimEvidenceMap:
    claims: list[ClaimEvidenceItem] = []
    claim_index = 1
    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            claims.append(
                ClaimEvidenceItem(
                    claim_id=f"C{claim_index}",
                    claim_text=mechanism.description,
                    support_status=mechanism.support_status,
                    evidence_ids=mechanism.evidence_ids,
                    mechanism_ids=[mechanism.mechanism_id],
                    source="method_mechanism",
                    caveats=[],
                )
            )
            claim_index += 1
            for submechanism in mechanism.submechanisms:
                claims.append(
                    ClaimEvidenceItem(
                        claim_id=f"C{claim_index}",
                        claim_text=submechanism.description,
                        support_status=mechanism.support_status,
                        evidence_ids=submechanism.evidence_ids,
                        mechanism_ids=[mechanism.mechanism_id],
                        source=f"submechanism:{submechanism.submechanism_id}",
                        caveats=[],
                    )
                )
                claim_index += 1

    for equation in method_evidence.equation_candidates:
        claims.append(
            ClaimEvidenceItem(
                claim_id=f"C{claim_index}",
                claim_text=f"Equation candidate {equation.name}: {equation.latex}",
                support_status=SupportStatus.SUPPORTED if equation.evidence_ids else SupportStatus.PARTIAL,
                evidence_ids=equation.evidence_ids,
                mechanism_ids=[],
                source=f"equation_candidate:{equation.equation_id}",
                caveats=equation.caveats,
            )
        )
        claim_index += 1

    for contract in method_evidence.claim_contracts:
        if contract.support_status.value == "unsupported":
            continue
        if contract.support_status.value == "supported" and not contract.evidence_span_ids:
            continue
        claims.append(
            ClaimEvidenceItem(
                claim_id=f"C{claim_index}",
                claim_text=contract.claim_intent,
                support_status=_contract_support_status(contract.support_status.value),
                evidence_ids=contract.evidence_span_ids,
                mechanism_ids=[],
                source=f"claim_contract:{contract.claim_id}",
                caveats=contract.required_qualifiers,
            )
        )
        claim_index += 1

    if alignment is not None:
        for assessment in alignment.author_alignment.claim_assessments:
            claims.append(
                ClaimEvidenceItem(
                    claim_id=f"C{claim_index}",
                    claim_text=assessment.claim_text,
                    support_status=assessment.support_status,
                    evidence_ids=assessment.evidence_ids,
                    mechanism_ids=[],
                    source=f"author_claim:{assessment.support_level.value}",
                    caveats=assessment.caveats
                    + (
                        ["Author claim is not supported by discovered files or symbols."]
                        if assessment.support_status == SupportStatus.UNSUPPORTED
                        else []
                    ),
                )
            )
            claim_index += 1
    return ClaimEvidenceMap(claims=claims)


def _contract_support_status(status: str) -> SupportStatus:
    if status == "supported":
        return SupportStatus.SUPPORTED
    if status == "unsupported":
        return SupportStatus.UNSUPPORTED
    return SupportStatus.PARTIAL


def build_claim_evidence_map_from_files(
    method_evidence_path: str | Path,
    alignment_path: str | Path | None = None,
) -> ClaimEvidenceMap:
    method_evidence = MethodEvidence.model_validate(json.loads(Path(method_evidence_path).read_text(encoding="utf-8")))
    alignment = None
    if alignment_path is not None:
        alignment = CodeAlignmentIR.model_validate(json.loads(Path(alignment_path).read_text(encoding="utf-8")))
    return build_claim_evidence_map(method_evidence, alignment)
