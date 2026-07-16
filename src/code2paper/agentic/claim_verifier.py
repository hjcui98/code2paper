from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence, SupportStatus


class VerifiedClaim(BaseModel):
    """Claim-level audit result used by agentic routers before authoring."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_text: str
    source: str
    support_status: SupportStatus
    evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    recommended_action: str
    rationale: str


class ClaimVerificationReport(BaseModel):
    """Auditable summary of whether frozen claims are safe to write."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "claim-verification"
    checked_claims: int = 0
    supported_claims: int = 0
    partial_claims: int = 0
    unsupported_claims: int = 0
    claims_with_missing_evidence: int = 0
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)
    claims: list[VerifiedClaim] = Field(default_factory=list)


def build_claim_verification_report(
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
) -> ClaimVerificationReport:
    """Verify each claim against the frozen MethodEvidence evidence ids."""

    known_evidence_ids = _known_evidence_ids(method_evidence)
    verified: list[VerifiedClaim] = []

    for claim in claim_map.claims:
        evidence_ids = _unique(claim.evidence_ids)
        missing_ids = [evidence_id for evidence_id in evidence_ids if evidence_id not in known_evidence_ids]
        effective_status = claim.support_status
        if not evidence_ids or missing_ids:
            effective_status = SupportStatus.UNSUPPORTED
        elif claim.support_status == SupportStatus.PARTIAL:
            effective_status = SupportStatus.PARTIAL

        action, rationale = _claim_action(
            declared_status=claim.support_status,
            effective_status=effective_status,
            evidence_ids=evidence_ids,
            missing_ids=missing_ids,
        )
        verified.append(
            VerifiedClaim(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                source=claim.source,
                support_status=effective_status,
                evidence_ids=evidence_ids,
                missing_evidence_ids=missing_ids,
                caveats=claim.caveats,
                recommended_action=action,
                rationale=rationale,
            )
        )

    supported = sum(1 for claim in verified if claim.support_status == SupportStatus.SUPPORTED)
    partial = sum(1 for claim in verified if claim.support_status == SupportStatus.PARTIAL)
    unsupported = sum(1 for claim in verified if claim.support_status == SupportStatus.UNSUPPORTED)
    missing = sum(1 for claim in verified if claim.missing_evidence_ids)
    actions = _recommended_actions(unsupported=unsupported, partial=partial, missing=missing)
    return ClaimVerificationReport(
        checked_claims=len(verified),
        supported_claims=supported,
        partial_claims=partial,
        unsupported_claims=unsupported,
        claims_with_missing_evidence=missing,
        hard_gate_passed=unsupported == 0 and missing == 0,
        recommended_actions=actions,
        claims=verified,
    )


def write_claim_verification_report(path: str | Path, report: ClaimVerificationReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return output


def _claim_action(
    *,
    declared_status: SupportStatus,
    effective_status: SupportStatus,
    evidence_ids: list[str],
    missing_ids: list[str],
) -> tuple[str, str]:
    if missing_ids:
        return (
            "drop_or_retrieve_more_evidence",
            "Claim references evidence ids that are not present in MethodEvidence.",
        )
    if not evidence_ids:
        return "drop_or_retrieve_more_evidence", "Claim has no frozen code evidence binding."
    if effective_status == SupportStatus.UNSUPPORTED:
        return "drop_or_retrieve_more_evidence", "Claim is marked unsupported by the evidence builder."
    if effective_status == SupportStatus.PARTIAL:
        return "caveat_only", "Claim is only partially supported and must be written with qualifiers."
    if declared_status != effective_status:
        return "caveat_only", "Claim support was downgraded during verification."
    return "allow_in_prose", "Claim is supported by frozen code evidence."


def _recommended_actions(*, unsupported: int, partial: int, missing: int) -> list[str]:
    actions: list[str] = []
    if missing:
        actions.append("return_to_analysis_for_missing_evidence_ids")
    if unsupported:
        actions.append("exclude_unsupported_claims_from_authoring")
    if partial:
        actions.append("write_partial_claims_with_required_caveats")
    if not actions:
        actions.append("all_claims_safe_for_evidence_constrained_authoring")
    return actions


def _known_evidence_ids(method_evidence: MethodEvidence) -> set[str]:
    payload = method_evidence.model_dump(mode="json")
    found: set[str] = set()
    _collect_evidence_ids(payload, found)
    return found


def _collect_evidence_ids(value: object, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "span_id"} and isinstance(item, str):
                found.add(item)
            elif key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids"} and isinstance(item, list):
                found.update(str(element) for element in item if str(element).strip())
            else:
                _collect_evidence_ids(item, found)
        return
    if isinstance(value, list):
        for item in value:
            _collect_evidence_ids(item, found)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def load_claim_verification_report(path: str | Path) -> ClaimVerificationReport:
    return ClaimVerificationReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
