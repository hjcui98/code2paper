from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.core.schemas import ClaimEvidenceItem, ClaimEvidenceMap, MethodEvidence, SupportStatus


class AuthoringConstraintSet(BaseModel):
    """Claim-level constraints passed from evidence verification into writing."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "agentic-authoring-constraints"
    allowed_claim_ids: list[str] = Field(default_factory=list)
    caveated_claim_ids: list[str] = Field(default_factory=list)
    excluded_claim_ids: list[str] = Field(default_factory=list)
    missing_evidence_claim_ids: list[str] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)


def build_authoring_constraints(report: ClaimVerificationReport) -> AuthoringConstraintSet:
    """Turn claim verification into explicit writing-time constraints."""

    allowed: list[str] = []
    caveated: list[str] = []
    excluded: list[str] = []
    missing: list[str] = []
    rules: list[str] = [
        "Only write claims that appear in allowed_claim_ids or caveated_claim_ids.",
        "Write caveated_claim_ids with qualifiers from their caveats/rationale.",
        "Do not mention excluded_claim_ids as method claims.",
    ]

    for claim in report.claims:
        if claim.missing_evidence_ids:
            missing.append(claim.claim_id)
        if claim.support_status == SupportStatus.SUPPORTED and claim.recommended_action == "allow_in_prose":
            allowed.append(claim.claim_id)
        elif claim.support_status == SupportStatus.PARTIAL:
            caveated.append(claim.claim_id)
        else:
            excluded.append(claim.claim_id)

    if missing:
        rules.append("Return to analysis/retrieval before authoring if excluded claims are essential to the author story.")
    if caveated:
        rules.append("Partial claims may describe only the implemented fragment; do not complete missing mechanisms from domain knowledge.")
    return AuthoringConstraintSet(
        allowed_claim_ids=_unique(allowed),
        caveated_claim_ids=_unique(caveated),
        excluded_claim_ids=_unique(excluded),
        missing_evidence_claim_ids=_unique(missing),
        writing_rules=rules,
    )


def apply_authoring_constraints(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    report: ClaimVerificationReport,
) -> tuple[MethodEvidence, ClaimEvidenceMap, AuthoringConstraintSet]:
    """Create constrained authoring inputs without mutating frozen evidence."""

    constraints = build_authoring_constraints(report)
    verified_by_id = {claim.claim_id: claim for claim in report.claims}
    kept_claims: list[ClaimEvidenceItem] = []
    for claim in claim_map.claims:
        verified = verified_by_id.get(claim.claim_id)
        if verified is None:
            continue
        if claim.claim_id in constraints.excluded_claim_ids:
            continue
        kept_claims.append(
            claim.model_copy(
                update={
                    "support_status": verified.support_status,
                    "evidence_ids": verified.evidence_ids,
                    "caveats": _unique([*claim.caveats, *verified.caveats, verified.rationale]),
                }
            )
        )

    constrained_evidence = method_evidence.model_copy(
        update={
            "writing_constraints": _unique(
                [
                    *method_evidence.writing_constraints,
                    *constraints.writing_rules,
                    f"Agentic allowed claim ids: {', '.join(constraints.allowed_claim_ids) or 'none'}.",
                    f"Agentic caveated claim ids: {', '.join(constraints.caveated_claim_ids) or 'none'}.",
                    f"Agentic excluded claim ids: {', '.join(constraints.excluded_claim_ids) or 'none'}.",
                ]
            )
        }
    )
    return constrained_evidence, ClaimEvidenceMap(claims=kept_claims), constraints


def write_authoring_constraints(path: str | Path, constraints: AuthoringConstraintSet) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(constraints.model_dump_json(indent=2), encoding="utf-8")
    return output


def load_authoring_constraints(path: str | Path) -> AuthoringConstraintSet:
    return AuthoringConstraintSet.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result
