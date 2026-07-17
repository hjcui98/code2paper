from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.atomic_claim_v2 import AtomicClaimSetV2
from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2
from code2paper.agentic.semantic_evidence import concepts_semantically_related
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ForbiddenClaim, ProjectedClaim
from code2paper.core.schemas import (
    AuthorLogicMapping,
    ClaimContract,
    ClaimEvidenceItem,
    ClaimEvidenceMap,
    ConflictStatus,
    MethodEvidence,
    RawEvidencePack,
    SupportStatus,
)


def build_authoring_projection(
    *,
    method_evidence: MethodEvidence,
    claim_map: ClaimEvidenceMap,
    verification: ClaimVerificationReport,
    raw_evidence: RawEvidencePack | None = None,
    evidence_snapshot_v2: EvidenceSnapshotV2 | None = None,
    atomic_claims_v2: AtomicClaimSetV2 | None = None,
) -> AuthoringInputProjection:
    claim_by_id = {claim.claim_id: claim for claim in claim_map.claims}
    contract_by_id = {contract.claim_id: contract for contract in method_evidence.claim_contracts}
    projected: list[ProjectedClaim] = []
    forbidden: list[ForbiddenClaim] = []
    structural_dropped: list[str] = []
    known_direct_evidence = _known_direct_evidence(method_evidence)
    v2_span_by_id = {
        span.evidence_id: span
        for span in (evidence_snapshot_v2.spans if evidence_snapshot_v2 else [])
        if span.status == "valid"
    }
    v2_claim_by_id = {claim.claim_id: claim for claim in (atomic_claims_v2.claims if atomic_claims_v2 else [])}
    for verified in verification.claims:
        if _is_stage_scaffold_claim(verified.claim_text, verified.source):
            structural_dropped.append(f"structural_claim:{verified.claim_id}")
            continue
        source_claim = claim_by_id.get(verified.claim_id)
        contract = contract_by_id.get(verified.claim_id)
        direct_ids = [item for item in _dedupe(verified.evidence_ids) if item in known_direct_evidence]
        if evidence_snapshot_v2 is not None:
            direct_ids = [item for item in direct_ids if item in v2_span_by_id]
        status = _enum_value(verified.support_status)
        v2_claim = v2_claim_by_id.get(verified.claim_id)
        if atomic_claims_v2 is not None and (v2_claim is None or v2_claim.verdict_status not in {"supported", "partial"}):
            status = SupportStatus.UNSUPPORTED.value
        evidence_semantically_related = _direct_evidence_semantically_related(
            verified.claim_text,
            direct_ids,
            raw_evidence,
            evidence_snapshot_v2=evidence_snapshot_v2,
        )
        if (
            status not in {SupportStatus.SUPPORTED.value, SupportStatus.PARTIAL.value}
            or not direct_ids
            or not evidence_semantically_related
        ):
            forbidden.append(
                ForbiddenClaim(
                    claim_id=verified.claim_id,
                    reason=(
                        "direct_evidence_semantically_unrelated"
                        if direct_ids and not evidence_semantically_related
                        else verified.rationale or "claim_not_authorized_for_prose"
                    ),
                    source=verified.source,
                    repair_metadata={
                        "recommended_action": verified.recommended_action,
                        "missing_evidence_ids": verified.missing_evidence_ids,
                    },
                )
            )
            continue
        qualifiers = _dedupe(
            [
                *verified.caveats,
                *list(getattr(source_claim, "caveats", []) or []),
                *list(getattr(contract, "required_qualifiers", []) or []),
            ]
        )
        if status == SupportStatus.PARTIAL.value and not qualifiers:
            forbidden.append(
                ForbiddenClaim(
                    claim_id=verified.claim_id,
                    reason="partial_claim_missing_explicit_qualifier",
                    source=verified.source,
                    repair_metadata={
                        "recommended_action": "supply_supported_fragment_or_explicit_qualifier"
                    },
                )
            )
            continue
        boundary = str(getattr(contract, "allowed_wording_boundary", "") or "").strip()
        fragment = _supported_fragment(
            claim_text=verified.claim_text,
            boundary=boundary,
            partial=status == SupportStatus.PARTIAL.value,
        )
        claim_payload = {
            "claim_id": verified.claim_id,
            "claim_text": fragment,
            "support_status": status,
            "direct_evidence_ids": direct_ids,
            "supported_fragment": fragment,
            "required_qualifiers": qualifiers,
            "allowed_wording_boundary": boundary or fragment,
            "source": verified.source,
        }
        projected.append(ProjectedClaim(**claim_payload, input_digest=_digest(claim_payload)))

    stage_packets, dropped = _project_stage_packets(method_evidence.stage_packets, projected)
    if stage_packets:
        author_scoped_ids = {
            str(claim_id)
            for packet in stage_packets
            for claim_id in packet.get("claim_ids", [])
            if str(claim_id)
        }
        out_of_scope = [claim for claim in projected if claim.claim_id not in author_scoped_ids]
        projected = [claim for claim in projected if claim.claim_id in author_scoped_ids]
        forbidden.extend(
            ForbiddenClaim(
                claim_id=claim.claim_id,
                reason="outside_author_scoped_method_stages",
                source=claim.source,
                repair_metadata={"recommended_action": "omit_from_current_author_intent"},
            )
            for claim in out_of_scope
        )
        stage_packets, stage_dropped = _project_stage_packets(method_evidence.stage_packets, projected)
        dropped.extend(stage_dropped)
    allowed_ids = {claim.claim_id for claim in projected}
    allowed_evidence = {item for claim in projected for item in claim.direct_evidence_ids}
    safe_equations = _filter_evidence_objects(method_evidence.equation_candidates, allowed_evidence)
    safe_numeric = _filter_evidence_objects(method_evidence.architecture_parameters, allowed_evidence)
    safe_aliases = _filter_evidence_objects(method_evidence.paper_module_aliases, allowed_evidence)
    source_digests = {
        "method_evidence": _digest(method_evidence.model_dump(mode="json")),
        "claim_map": _digest(claim_map.model_dump(mode="json")),
        "claim_verification": _digest(verification.model_dump(mode="json")),
    }
    if evidence_snapshot_v2 is not None:
        source_digests["evidence_snapshot_v2"] = evidence_snapshot_v2.content_digest
    if atomic_claims_v2 is not None:
        source_digests["atomic_claims_v2"] = atomic_claims_v2.content_digest
    payload = {
        "project_id": method_evidence.project_id,
        "method_name": method_evidence.method_name,
        "author_goal": "Organize the Method around the projected code-supported claims.",
        "implementation_scope": method_evidence.implementation_scope,
        "projected_claims": [item.model_dump(mode="json") for item in projected],
        "forbidden_claims": [item.model_dump(mode="json") for item in forbidden],
        "stage_packets": stage_packets,
        "safe_equations": safe_equations,
        "safe_numeric_facts": safe_numeric,
        "safe_aliases": safe_aliases,
        "safe_intent_spine": _safe_intent_spine(method_evidence, allowed_ids),
        "writing_rules": [
            "The projection is the writer's only positive method-fact input.",
            "Use only projected_claims and their direct_evidence_ids.",
            "When author-scoped stage packets exist, omit otherwise supported claims outside those stages.",
            "Partial claims must preserve every required qualifier.",
            "Forbidden claim records contain no reusable claim wording.",
        ],
        "dropped_positive_fields": _dedupe([*dropped, *structural_dropped]),
        "source_digests": source_digests,
        "repo_snapshot_id": evidence_snapshot_v2.repo_snapshot_id if evidence_snapshot_v2 else "",
        "project_tree_hash": evidence_snapshot_v2.project_tree_hash if evidence_snapshot_v2 else "",
        "evidence_snapshot_id": evidence_snapshot_v2.evidence_snapshot_id if evidence_snapshot_v2 else "",
        "evidence_snapshot_digest": evidence_snapshot_v2.content_digest if evidence_snapshot_v2 else "",
        "hard_gate_passed": bool(projected),
    }
    return AuthoringInputProjection(**payload, projection_digest=_digest(payload))


def projection_writer_payload(projection: AuthoringInputProjection) -> dict[str, Any]:
    """Return the only positive factual payload exposed to the writer."""

    return {
        "method_name": projection.method_name,
        "author_goal": projection.author_goal,
        "implementation_scope": projection.implementation_scope,
        "claims": [claim.model_dump(mode="json") for claim in projection.projected_claims],
        "stage_packets": projection.stage_packets,
        "equations": projection.safe_equations,
        "numeric_facts": projection.safe_numeric_facts,
        "aliases": projection.safe_aliases,
        "intent_spine": projection.safe_intent_spine,
        "writing_rules": projection.writing_rules,
        "projection_digest": projection.projection_digest,
    }


def projection_writer_brief(projection: AuthoringInputProjection) -> str:
    lines = [
        "Authoring input projection (the only positive method-fact source):",
        f"- projection_digest={projection.projection_digest}",
    ]
    for claim in projection.projected_claims:
        lines.append(
            f"- {claim.claim_id}: {claim.supported_fragment}; "
            f"direct_evidence={','.join(claim.direct_evidence_ids)}; boundary={claim.allowed_wording_boundary}"
        )
        if claim.required_qualifiers:
            lines.append("  qualifiers: " + "; ".join(claim.required_qualifiers))
    lines.extend(f"- rule: {rule}" for rule in projection.writing_rules)
    return "\n".join(lines)


def restrict_projection_for_authoring_revision(
    projection: AuthoringInputProjection,
    excluded_claim_ids: set[str],
) -> AuthoringInputProjection:
    """Create a writer-only subset after final-text validation rejects a claim."""

    if not excluded_claim_ids:
        return projection
    kept = [
        claim for claim in projection.projected_claims
        if claim.claim_id not in excluded_claim_ids
    ]
    # An empty writer view must not silently replace a safe block with an empty
    # Method. Keep the original view so the normal hard gate remains decisive.
    if not kept:
        return projection
    packets, _dropped = _project_stage_packets(projection.stage_packets, kept)
    allowed_evidence = {
        evidence_id for claim in kept for evidence_id in claim.direct_evidence_ids
    }
    update = {
        "projected_claims": kept,
        "stage_packets": packets,
        "safe_equations": _filter_projection_safe_objects(
            projection.safe_equations, allowed_evidence
        ),
        "safe_numeric_facts": _filter_projection_safe_objects(
            projection.safe_numeric_facts, allowed_evidence
        ),
        "safe_aliases": _filter_projection_safe_objects(
            projection.safe_aliases, allowed_evidence
        ),
    }
    payload = projection.model_dump(mode="json")
    payload.update(
        {
            **update,
            "projected_claims": [claim.model_dump(mode="json") for claim in kept],
        }
    )
    payload.pop("projection_digest", None)
    return projection.model_copy(
        update={**update, "projection_digest": _digest(payload)}
    )


def _filter_projection_safe_objects(
    values: list[dict[str, Any]], allowed_evidence: set[str]
) -> list[dict[str, Any]]:
    return [
        value for value in values
        if allowed_evidence
        & {
            str(item)
            for key in ("evidence_ids", "evidence_span_ids", "direct_evidence_ids")
            for item in value.get(key, [])
            if str(item)
        }
    ]


def projected_writer_inputs(
    projection: AuthoringInputProjection,
    *,
    template: MethodEvidence,
) -> tuple[MethodEvidence, ClaimEvidenceMap]:
    """Build compatibility inputs with every non-projected positive fact removed."""

    claims = [
        ClaimEvidenceItem(
            claim_id=claim.claim_id,
            claim_text=claim.supported_fragment,
            support_status=SupportStatus(claim.support_status),
            evidence_ids=claim.direct_evidence_ids,
            source="authoring_projection",
            caveats=claim.required_qualifiers,
        )
        for claim in projection.projected_claims
    ]
    contracts = [
        ClaimContract(
            claim_id=claim.claim_id,
            claim_intent=claim.supported_fragment,
            support_status=(
                ConflictStatus.SUPPORTED
                if claim.support_status == "supported"
                else ConflictStatus.PARTIALLY_SUPPORTED
            ),
            evidence_span_ids=claim.direct_evidence_ids,
            allowed_wording_boundary=claim.allowed_wording_boundary,
            required_qualifiers=claim.required_qualifiers,
        )
        for claim in projection.projected_claims
    ]
    evidence_payload = template.model_dump(mode="python")
    evidence_payload.update(
        {
            "method_goal": "Describe only the code-supported claims in the authoring projection.",
            "stages": [
                {
                    "stage_id": packet["stage_id"],
                    "name": packet["name"],
                    "purpose": packet["purpose"],
                    "inputs": [],
                    "outputs": [],
                    "modules": [],
                    "mechanisms": _projection_stage_mechanisms(
                        packet=packet,
                        template=template,
                        stage_index=index,
                    ),
                }
                for index, packet in enumerate(projection.stage_packets, start=1)
            ],
            "behavior_patterns": [],
            "equation_candidates": projection.safe_equations,
            "architecture_parameters": projection.safe_numeric_facts,
            "tensor_roles": [],
            "innovation_candidates": [],
            "paper_module_aliases": projection.safe_aliases,
            "method_overview": {},
            "stage_packets": projection.stage_packets,
            "writing_constraints": projection.writing_rules,
            "alignment_notes": [],
            "frozen_mechanisms": [],
            "distinguishing_mechanisms": [],
            "author_logic_mapping": AuthorLogicMapping(),
            "unsupported_author_parts": [],
            "claim_contracts": contracts,
            "negative_scope": [],
        }
    )
    evidence = MethodEvidence.model_validate(evidence_payload)
    return evidence, ClaimEvidenceMap(claims=claims)


def _projection_stage_mechanisms(
    *, packet: dict[str, Any], template: MethodEvidence, stage_index: int
) -> list[dict[str, Any]]:
    """Retain trace IDs without reopening legacy mechanism prose as writer input."""

    packet_evidence = {
        str(item) for item in packet.get("evidence_span_ids", []) if str(item)
    }
    matched = [
        mechanism
        for stage in template.stages
        for mechanism in stage.mechanisms
        if packet_evidence & set(mechanism.evidence_ids)
    ]
    if not matched:
        return [
            {
                "mechanism_id": f"MECH_PROJECTION_{stage_index}",
                "description": packet["purpose"],
                "support_status": packet.get("support_status", "supported"),
                "evidence_ids": sorted(packet_evidence),
            }
        ]
    return [
        {
            "mechanism_id": mechanism.mechanism_id,
            "description": packet["purpose"],
            "support_status": packet.get("support_status", "supported"),
            "evidence_ids": sorted(packet_evidence & set(mechanism.evidence_ids)),
        }
        for mechanism in matched
    ]


def write_authoring_projection(path: str | Path, projection: AuthoringInputProjection) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(projection.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_authoring_projection(path: str | Path) -> AuthoringInputProjection:
    return AuthoringInputProjection.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _project_stage_packets(
    packets: list[dict], projected_claims: list[ProjectedClaim]
) -> tuple[list[dict[str, Any]], list[str]]:
    result: list[dict[str, Any]] = []
    dropped: list[str] = []
    for index, packet in enumerate(packets):
        packet_text = _normalize_text(" ".join(
            str(packet.get(key) or "") for key in ("name", "purpose", "stage_claim")
        ))
        packet_evidence = {
            str(item)
            for key in ("evidence_ids", "evidence_span_ids", "primary_evidence_ids")
            for item in packet.get(key, [])
            if str(item)
        }
        explicit_ids = {str(item) for item in packet.get("claim_ids", [])}
        matches = [
            claim
            for claim in projected_claims
            if claim.claim_id in explicit_ids
            or _normalize_text(claim.supported_fragment) in packet_text
            or (
                _normalize_text(str(packet.get("name") or ""))
                and _normalize_text(str(packet.get("name") or "")) in _normalize_text(claim.supported_fragment)
            )
            or (
                packet_evidence.intersection(claim.direct_evidence_ids)
                and any(
                    concepts_semantically_related(fragment, claim.supported_fragment)
                    for fragment in _semantic_fragments(packet_text)
                )
            )
        ]
        if not matches:
            dropped.append(f"stage_packets[{index}]")
            continue
        claim_ids = [claim.claim_id for claim in matches]
        evidence_ids = _dedupe(
            evidence_id
            for claim in matches
            for evidence_id in claim.direct_evidence_ids
            if evidence_id in packet_evidence
        )
        if not evidence_ids:
            dropped.append(f"stage_packets[{index}]")
            continue
        supported_purpose = "; ".join(_dedupe(claim.supported_fragment for claim in matches))
        safe: dict[str, Any] = {
            "stage_id": str(packet.get("stage_id") or ""),
            "name": str(packet.get("name") or "Evidence-backed stage"),
            "purpose": supported_purpose,
            "stage_claim": supported_purpose,
            "claim_ids": claim_ids,
            "evidence_ids": evidence_ids,
            "primary_evidence_ids": evidence_ids,
            "evidence_span_ids": evidence_ids,
            "support_status": "supported" if all(claim.support_status == "supported" for claim in matches) else "partial",
        }
        result.append(safe)
    return result, dropped


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().strip().rstrip(".").split())


def _semantic_fragments(value: str) -> list[str]:
    text = str(value or "")
    return _dedupe(
        [
            text,
            *[
                part.strip()
                for part in re.split(r"[,.!?;:()]|\band\b", text, flags=re.IGNORECASE)
                if part.strip()
            ],
        ]
    )


def _direct_evidence_semantically_related(
    claim_text: str,
    direct_ids: list[str],
    raw_evidence: RawEvidencePack | None,
    evidence_snapshot_v2: EvidenceSnapshotV2 | None = None,
) -> bool:
    if evidence_snapshot_v2 is not None:
        span_by_id = {span.evidence_id: span for span in evidence_snapshot_v2.spans if span.status == "valid"}
        evidence_text = " ".join(span_by_id[item].exact_excerpt for item in direct_ids if item in span_by_id)
        claim_tokens = _semantic_tokens(claim_text)
        evidence_tokens = _semantic_tokens(evidence_text)
        overlap = claim_tokens & evidence_tokens
        lexical_match = bool(claim_tokens) and (
            len(overlap) / max(1, min(len(claim_tokens), len(evidence_tokens))) >= 0.45
            or len(overlap) >= 2
        )
        return lexical_match or concepts_semantically_related(claim_text, evidence_text)
    if raw_evidence is None:
        return True
    evidence_by_id = {item.evidence_id: item for item in raw_evidence.evidence_items}
    evidence_text = " ".join(
        " ".join((str(item.config_key or ""), str(item.content_summary or "")))
        for evidence_id in direct_ids
        if (item := evidence_by_id.get(evidence_id)) is not None
    )
    claim_tokens = _semantic_tokens(claim_text)
    evidence_tokens = _semantic_tokens(evidence_text)
    overlap = claim_tokens & evidence_tokens
    lexical_match = bool(claim_tokens) and (
        len(overlap) / max(1, min(len(claim_tokens), len(evidence_tokens))) >= 0.45
        or len(overlap) >= 2
    )
    return lexical_match or concepts_semantically_related(claim_text, evidence_text)


def _semantic_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our", "this", "that", "with", "for"}
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1 and token not in stop}


def _is_stage_scaffold_claim(claim_text: str, source: str) -> bool:
    return str(source or "").startswith("claim_contract:") and bool(
        re.search(r"\bpaper-facing\s+stage\s+named\b", str(claim_text or ""), flags=re.IGNORECASE)
    )


def _filter_evidence_objects(values: list[Any], allowed_evidence: set[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for value in values:
        payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)
        refs = _collect_ref_values(payload)
        if refs.intersection(allowed_evidence):
            result.append(payload)
    return result


def _collect_ref_values(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids"} and isinstance(item, list):
                found.update(str(element) for element in item)
            else:
                found.update(_collect_ref_values(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_collect_ref_values(item))
    return found


def _known_direct_evidence(method_evidence: MethodEvidence) -> set[str]:
    """Collect evidence only from frozen structural evidence, never claim/scaffold packets."""

    payload = method_evidence.model_dump(mode="json")
    authoritative_fields = (
        "stages",
        "behavior_patterns",
        "equation_candidates",
        "architecture_parameters",
        "tensor_roles",
        "frozen_mechanisms",
    )
    found: set[str] = set()
    for field in authoritative_fields:
        found.update(_collect_ref_values(payload.get(field, [])))
    return found


def _safe_intent_spine(method_evidence: MethodEvidence, allowed_ids: set[str]) -> list[str]:
    supported_contracts = [
        contract.claim_id
        for contract in method_evidence.claim_contracts
        if contract.claim_id in allowed_ids and contract.support_status == ConflictStatus.SUPPORTED
    ]
    return supported_contracts


def _supported_fragment(*, claim_text: str, boundary: str, partial: bool) -> str:
    if partial and boundary and len(boundary.split()) >= 3:
        return boundary.strip()
    return claim_text.strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def _digest(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
