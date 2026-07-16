from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2
from code2paper.core.schemas import ClaimEvidenceMap


class AtomicClaimV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_text: str
    subject: str = ""
    predicate: str = ""
    object: str = ""
    conditions: list[str] = Field(default_factory=list)
    qualifiers: list[str] = Field(default_factory=list)
    claim_type: Literal["structural", "numeric", "formula", "causal", "performance", "runtime", "unknown"] = "unknown"
    risk_markers: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    context_evidence_ids: list[str] = Field(default_factory=list)
    supported_fragment: str = ""
    unsupported_fragment: str = ""
    allowed_wording_boundary: str = ""
    verifier_input_digest: str
    verdict_status: Literal["unverified", "supported", "partial", "unsupported"] = "unverified"
    verdict_rationale: str = "V1 compatibility conversion requires V2 re-verification."


class AtomicClaimSetV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p1"
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    claims: list[AtomicClaimV2] = Field(default_factory=list)
    content_digest: str


def convert_claims_to_v2(
    claim_map: ClaimEvidenceMap,
    verification: ClaimVerificationReport,
    evidence_snapshot: EvidenceSnapshotV2,
) -> AtomicClaimSetV2:
    verified_by_id = {item.claim_id: item for item in verification.claims}
    valid_ids = {span.evidence_id for span in evidence_snapshot.spans if span.status == "valid"}
    claims: list[AtomicClaimV2] = []
    for item in claim_map.claims:
        verified = verified_by_id.get(item.claim_id)
        direct = [evidence_id for evidence_id in item.evidence_ids if evidence_id in valid_ids]
        claim_type, risks = _claim_risk(item.claim_text)
        subject, predicate, object_ = _simple_spo(item.claim_text)
        payload = {
            "claim_id": item.claim_id,
            "claim_text": item.claim_text,
            "subject": subject,
            "predicate": predicate,
            "object": object_,
            "conditions": [],
            "qualifiers": list(item.caveats),
            "claim_type": claim_type,
            "risk_markers": risks,
            "direct_evidence_ids": direct,
            "context_evidence_ids": [],
            "supported_fragment": "",
            "unsupported_fragment": item.claim_text,
            "allowed_wording_boundary": "",
            "verdict_status": "unverified",
            "verdict_rationale": (
                "Converted from V1 status " + str(getattr(getattr(verified, "support_status", ""), "value", getattr(verified, "support_status", "")))
                + "; V2 semantic verification required."
            ),
        }
        claims.append(AtomicClaimV2(**payload, verifier_input_digest=_digest_json(payload)))
    content = [claim.model_dump(mode="json") for claim in claims]
    return AtomicClaimSetV2(
        evidence_snapshot_id=evidence_snapshot.evidence_snapshot_id,
        evidence_snapshot_digest=evidence_snapshot.content_digest,
        claims=claims,
        content_digest=_digest_json(content),
    )


def verify_atomic_claims_v2(
    claims: AtomicClaimSetV2,
    evidence_snapshot: EvidenceSnapshotV2,
) -> AtomicClaimSetV2:
    """Explicit V2 verification step; conversion alone never grants support."""

    spans = {span.evidence_id: span for span in evidence_snapshot.spans if span.status == "valid"}
    verified: list[AtomicClaimV2] = []
    for claim in claims.claims:
        evidence_text = "\n".join(spans[item].exact_excerpt for item in claim.direct_evidence_ids if item in spans)
        related = _semantically_related(claim.claim_text, evidence_text)
        status = "supported" if related and claim.direct_evidence_ids else "unsupported"
        verified.append(
            claim.model_copy(
                update={
                    "verdict_status": status,
                    "supported_fragment": claim.claim_text if status == "supported" else "",
                    "unsupported_fragment": "" if status == "supported" else claim.claim_text,
                    "allowed_wording_boundary": claim.claim_text if status == "supported" else "",
                    "verdict_rationale": (
                        "Exact EvidenceSpanV2 excerpt has direct lexical-semantic overlap."
                        if status == "supported"
                        else "Exact EvidenceSpanV2 excerpt does not directly support the claim wording."
                    ),
                }
            )
        )
    content = [claim.model_dump(mode="json") for claim in verified]
    return claims.model_copy(update={"claims": verified, "content_digest": _digest_json(content)})


def write_atomic_claims_v2(path: str | Path, claims: AtomicClaimSetV2) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(claims.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_atomic_claims_v2(path: str | Path) -> AtomicClaimSetV2:
    return AtomicClaimSetV2.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _simple_spo(text: str) -> tuple[str, str, str]:
    tokens = text.strip().rstrip(".").split()
    if len(tokens) < 3:
        return (tokens[0] if tokens else "", "", " ".join(tokens[1:]))
    return tokens[0], tokens[1], " ".join(tokens[2:])


def _claim_risk(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    risks: list[str] = []
    claim_type = "structural"
    if re.search(r"\d", text): risks.append("numeric"); claim_type = "numeric"
    if any(word in lowered for word in ("cause", "ensure", "guarantee")): risks.append("causal"); claim_type = "causal"
    if any(word in lowered for word in ("outperform", "faster", "improve")): risks.append("performance"); claim_type = "performance"
    if "$" in text or "=" in text: risks.append("formula"); claim_type = "formula"
    return claim_type, risks


def _semantically_related(claim_text: str, evidence_text: str) -> bool:
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our", "this", "that", "with", "for"}
    def tokens(value: str) -> set[str]:
        raw = [part for item in re.findall(r"[a-z0-9_]+", value.lower()) for part in item.split("_")]
        return {_stem(item) for item in raw if len(item) > 1 and item not in stop}
    claim_tokens, evidence_tokens = tokens(claim_text), tokens(evidence_text)
    overlap = claim_tokens & evidence_tokens
    return bool(overlap) and (
        len(overlap) / max(1, min(len(claim_tokens), len(evidence_tokens))) >= 0.45 or len(overlap) >= 2
    )


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 3:
            token = token[: -len(suffix)]
            break
    if token.endswith("er") and len(token) > 5:
        token = token[:-1]
    return token


def _digest_json(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
