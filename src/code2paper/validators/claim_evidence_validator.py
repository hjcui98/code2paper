"""Claim-evidence consistency validator."""

from __future__ import annotations

from code2paper.schemas import DraftClaimMap, MethodEvidence


def validate_claim_evidence(
    *,
    method_evidence: MethodEvidence,
    draft_claim_map: DraftClaimMap,
) -> dict:
    known_claim_ids = {contract.claim_id for contract in method_evidence.claim_contracts}
    enforce_claim_binding = bool(known_claim_ids)
    known_mechanism_ids = {
        mechanism.mechanism_id
        for mechanism in method_evidence.frozen_mechanisms
        if mechanism.mechanism_id
    }
    known_mechanism_ids.update(
        {
            mechanism.mechanism_id
            for stage in method_evidence.stages
            for mechanism in stage.mechanisms
            if mechanism.mechanism_id
        }
    )
    known_evidence_ids = {
        evidence_id
        for mechanism in method_evidence.frozen_mechanisms
        for evidence_id in mechanism.evidence_span_ids
    }
    known_evidence_ids.update(
        {
            evidence_id
            for stage in method_evidence.stages
            for mechanism in stage.mechanisms
            for evidence_id in mechanism.evidence_ids
            if evidence_id
        }
    )
    known_evidence_ids.update(
        {
            evidence_id
            for contract in method_evidence.claim_contracts
            for evidence_id in contract.evidence_span_ids
            if evidence_id
        }
    )
    issues: list[dict] = []
    issue_counter = 1

    if not draft_claim_map.paragraphs:
        issues.append(
            {
                "issue_id": f"CE{issue_counter}",
                "category": "empty_draft_claim_map",
                "message": "Draft claim map has no paragraph mappings.",
                "paragraph_id": "",
            }
        )
        issue_counter += 1

    for paragraph in draft_claim_map.paragraphs:
        if enforce_claim_binding and not paragraph.claim_ids:
            issues.append(
                {
                    "issue_id": f"CE{issue_counter}",
                    "category": "missing_claim_binding",
                    "message": "Paragraph must bind at least one claim_id.",
                    "paragraph_id": paragraph.paragraph_id,
                }
            )
            issue_counter += 1
        if not paragraph.evidence_span_ids:
            issues.append(
                {
                    "issue_id": f"CE{issue_counter}",
                    "category": "missing_evidence_binding",
                    "message": "Paragraph must bind at least one evidence_span_id.",
                    "paragraph_id": paragraph.paragraph_id,
                }
            )
            issue_counter += 1
        for claim_id in paragraph.claim_ids:
            if enforce_claim_binding and claim_id not in known_claim_ids:
                issues.append(
                    {
                        "issue_id": f"CE{issue_counter}",
                        "category": "unknown_claim_id",
                        "message": f"Unknown claim id referenced in draft claim map: {claim_id}",
                        "paragraph_id": paragraph.paragraph_id,
                    }
                )
                issue_counter += 1
        for mechanism_id in paragraph.mechanism_ids:
            if mechanism_id not in known_mechanism_ids:
                issues.append(
                    {
                        "issue_id": f"CE{issue_counter}",
                        "category": "unknown_mechanism_id",
                        "message": f"Unknown mechanism id referenced in draft claim map: {mechanism_id}",
                        "paragraph_id": paragraph.paragraph_id,
                    }
                )
                issue_counter += 1
        for evidence_id in paragraph.evidence_span_ids:
            if evidence_id not in known_evidence_ids:
                issues.append(
                    {
                        "issue_id": f"CE{issue_counter}",
                        "category": "unknown_evidence_span_id",
                        "message": f"Unknown evidence span id referenced in draft claim map: {evidence_id}",
                        "paragraph_id": paragraph.paragraph_id,
                    }
                )
                issue_counter += 1

    mechanism_to_stage = {
        mechanism.mechanism_id: mechanism.parent_stage_id
        for mechanism in method_evidence.frozen_mechanisms
        if mechanism.parent_stage_id
    }
    for stage in method_evidence.stages:
        for mechanism in stage.mechanisms:
            if mechanism.mechanism_id and stage.stage_id:
                mechanism_to_stage.setdefault(mechanism.mechanism_id, stage.stage_id)
    stage_with_mechanism_paragraph: set[str] = set()
    for paragraph in draft_claim_map.paragraphs:
        for mechanism_id in paragraph.mechanism_ids:
            stage_id = mechanism_to_stage.get(mechanism_id)
            if stage_id:
                stage_with_mechanism_paragraph.add(stage_id)
    for stage in method_evidence.stages:
        if stage.stage_id not in stage_with_mechanism_paragraph:
            issues.append(
                {
                    "issue_id": f"CE{issue_counter}",
                    "category": "missing_stage_mechanism_paragraph",
                    "message": f"No paragraph provides mechanism mapping for stage {stage.stage_id}.",
                    "paragraph_id": "",
                }
            )
            issue_counter += 1
    return {
        "passed": not issues,
        "checked_paragraphs": len(draft_claim_map.paragraphs),
        "issues": issues,
    }
