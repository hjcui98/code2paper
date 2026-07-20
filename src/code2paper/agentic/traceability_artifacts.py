from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code2paper.agentic.contracts import AgenticRunState


def artifact_json(state: AgenticRunState, key: str) -> dict[str, Any]:
    path = state.artifacts.get(key, "")
    if not path:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def known_claim_ids(state: AgenticRunState) -> set[str]:
    ids = {
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "claims").get("claims"))
        if isinstance(claim, dict)
    }
    ids.update(
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "claim_verification").get("claims"))
        if isinstance(claim, dict)
    )
    ids.update(
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "atomic_claims_v3").get("claims"))
        if isinstance(claim, dict)
    )
    ids.update(
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "atomic_claims_v2").get("claims"))
        if isinstance(claim, dict)
    )
    return {claim_id for claim_id in ids if claim_id}


def unsupported_claim_ids(state: AgenticRunState) -> set[str]:
    unsupported = {
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "claims").get("claims"))
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    }
    unsupported.update(
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "claim_verification").get("claims"))
        if isinstance(claim, dict) and str(claim.get("support_status") or "") == "unsupported"
    )
    unsupported.update(
        str(claim.get("claim_id") or "")
        for claim in as_list(artifact_json(state, "atomic_claims_v2").get("claims"))
        if isinstance(claim, dict) and str(claim.get("verdict_status") or "") in {"unsupported", "unverified"}
    )
    return {claim_id for claim_id in unsupported if claim_id}


def known_evidence_ids(state: AgenticRunState) -> set[str]:
    ids: set[str] = set()
    evidence_v2 = artifact_json(state, "evidence_snapshot_v2")
    if evidence_v2:
        ids.update({
            str(span.get("evidence_id") or "")
            for span in as_list(evidence_v2.get("spans"))
            if isinstance(span, dict) and span.get("status") == "valid" and str(span.get("evidence_id") or "")
        })
    ids.update(collect_evidence_ids(artifact_json(state, "evidence_packets_v3")))
    ids.update(collect_evidence_ids(artifact_json(state, "code_facts_v1")))
    ids.update(collect_evidence_ids(artifact_json(state, "atomic_claims_v3")))
    ids.update(collect_evidence_ids(artifact_json(state, "evidence")))
    ids.update(collect_evidence_ids(artifact_json(state, "claims")))
    return ids


def collect_evidence_ids(value: object) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence_id", "span_id", "relation_id"} and isinstance(item, str):
                ids.add(item)
            elif key in {"evidence_ids", "evidence_span_ids", "related_evidence_ids", "primary_evidence_ids", "direct_span_ids", "relation_span_ids", "direct_evidence_ids", "relation_evidence_ids"}:
                ids.update(as_string_list(item))
            else:
                ids.update(collect_evidence_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(collect_evidence_ids(item))
    return ids


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
