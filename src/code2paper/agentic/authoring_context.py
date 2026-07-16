from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_constraints import AuthoringConstraintSet
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


class EvidenceBoundAuthoringClaim(BaseModel):
    """One claim contract available to the Method writer."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_text: str
    support_status: str
    evidence_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    source: str = ""
    writing_boundary: str = ""


class EvidenceBoundAuthoringContext(BaseModel):
    """Auditable author-intent and evidence context for Method writing."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "evidence-bound-authoring-context"
    method_name: str = ""
    author_goal: str = ""
    implementation_scope: str = ""
    writing_rules: list[str] = Field(default_factory=list)
    allowed_claims: list[EvidenceBoundAuthoringClaim] = Field(default_factory=list)
    caveated_claims: list[EvidenceBoundAuthoringClaim] = Field(default_factory=list)
    excluded_claims: list[EvidenceBoundAuthoringClaim] = Field(default_factory=list)
    negative_scope: list[str] = Field(default_factory=list)
    unsupported_author_parts: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    hard_gate_passed: bool = True
    recommended_actions: list[str] = Field(default_factory=list)


def build_authoring_context(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    verification: ClaimVerificationReport,
    constraints: AuthoringConstraintSet,
) -> EvidenceBoundAuthoringContext:
    """Build the compact authoring contract from author intent and verified evidence."""

    claim_source = {claim.claim_id: claim for claim in claim_map.claims}
    allowed = [
        _context_claim(claim_id, claim_source=claim_source, verification=verification, writing_boundary="safe_to_write")
        for claim_id in constraints.allowed_claim_ids
    ]
    caveated = [
        _context_claim(claim_id, claim_source=claim_source, verification=verification, writing_boundary="write_only_with_caveats")
        for claim_id in constraints.caveated_claim_ids
    ]
    excluded = [
        _context_claim(claim_id, claim_source=claim_source, verification=verification, writing_boundary="do_not_write_as_method_claim")
        for claim_id in constraints.excluded_claim_ids
    ]
    evidence_ids = _dedupe([evidence_id for claim in [*allowed, *caveated] for evidence_id in claim.evidence_ids])
    missing_safe_evidence = [
        claim.claim_id
        for claim in [*allowed, *caveated]
        if not claim.evidence_ids
    ]
    actions: list[str] = []
    if missing_safe_evidence:
        actions.append("return_to_analysis_for_safe_claims_without_evidence")
    if excluded:
        actions.append("exclude_unverified_author_claims_from_method_text")
    if caveated:
        actions.append("write_partial_claims_with_explicit_caveats")
    if not actions:
        actions.append("authoring_context_ready_for_evidence_constrained_writing")
    return EvidenceBoundAuthoringContext(
        method_name=method_evidence.method_name,
        author_goal=method_evidence.method_goal,
        implementation_scope=method_evidence.implementation_scope,
        writing_rules=constraints.writing_rules,
        allowed_claims=allowed,
        caveated_claims=caveated,
        excluded_claims=excluded,
        negative_scope=method_evidence.negative_scope,
        unsupported_author_parts=method_evidence.unsupported_author_parts,
        evidence_ids=evidence_ids,
        hard_gate_passed=not missing_safe_evidence,
        recommended_actions=actions,
    )


def authoring_context_brief(context: EvidenceBoundAuthoringContext) -> str:
    """Render a compact writing contract suitable for Phase 5 LLM payloads."""

    lines = [
        "Evidence-bound authoring contract:",
        f"- Author goal: {context.author_goal or 'unspecified'}.",
        f"- Implementation scope: {context.implementation_scope or 'unspecified'}.",
        "- Write only allowed claims and caveated claims listed below; do not write excluded claims.",
    ]
    if context.allowed_claims:
        lines.append("- Allowed claims:")
        for claim in context.allowed_claims[:20]:
            lines.append(f"  - {claim.claim_id}: {claim.claim_text}; evidence={', '.join(claim.evidence_ids) or 'none'}.")
    if context.caveated_claims:
        lines.append("- Caveated claims:")
        for claim in context.caveated_claims[:20]:
            caveat = "; ".join(claim.caveats[:3]) or "must be qualified"
            lines.append(f"  - {claim.claim_id}: {claim.claim_text}; evidence={', '.join(claim.evidence_ids) or 'none'}; caveat={caveat}.")
    if context.excluded_claims:
        lines.append("- Excluded claims:")
        for claim in context.excluded_claims[:20]:
            lines.append(f"  - {claim.claim_id}: {claim.claim_text}.")
    if context.negative_scope:
        lines.append("- Negative scope: " + "; ".join(context.negative_scope[:12]) + ".")
    if context.unsupported_author_parts:
        lines.append("- Unsupported author parts to omit: " + "; ".join(context.unsupported_author_parts[:12]) + ".")
    return "\n".join(lines)


def write_authoring_context(path: str | Path, context: EvidenceBoundAuthoringContext) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_authoring_context(path: str | Path) -> EvidenceBoundAuthoringContext:
    return EvidenceBoundAuthoringContext.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _context_claim(
    claim_id: str,
    *,
    claim_source: dict[str, object],
    verification: ClaimVerificationReport,
    writing_boundary: str,
) -> EvidenceBoundAuthoringClaim:
    source_claim = claim_source.get(claim_id)
    verified = {claim.claim_id: claim for claim in verification.claims}.get(claim_id)
    claim_text = getattr(verified, "claim_text", "") or getattr(source_claim, "claim_text", "")
    support_status = _enum_text(getattr(verified, "support_status", getattr(source_claim, "support_status", "")))
    evidence_ids = list(getattr(verified, "evidence_ids", getattr(source_claim, "evidence_ids", [])) or [])
    caveats = _dedupe(
        [
            *list(getattr(source_claim, "caveats", []) or []),
            *list(getattr(verified, "caveats", []) or []),
            str(getattr(verified, "rationale", "") or ""),
        ]
    )
    return EvidenceBoundAuthoringClaim(
        claim_id=claim_id,
        claim_text=claim_text,
        support_status=support_status,
        evidence_ids=_dedupe(evidence_ids),
        caveats=caveats,
        source=str(getattr(source_claim, "source", getattr(verified, "source", "")) or ""),
        writing_boundary=writing_boundary,
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value) or "").strip()
