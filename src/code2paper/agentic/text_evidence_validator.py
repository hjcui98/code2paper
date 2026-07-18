from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from code2paper.agentic.trust_contracts import (
    AuthoringInputProjection,
    FinalTextClaims,
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)
from code2paper.agentic.evidence_v2 import EvidenceSnapshotV2, is_direct_code_path, is_direct_code_span
from code2paper.agentic.semantic_evidence import concepts_semantically_related
from code2paper.core.schemas import RawEvidencePack, SourceType


SemanticVerifier = Callable[[dict[str, Any]], Mapping[str, Any] | None]
_STRONG_WORDS = {"guarantee", "guarantees", "ensure", "ensures", "cause", "causes", "outperform", "outperforms"}


def validate_text_evidence(
    *,
    final_claims: FinalTextClaims,
    projection: AuthoringInputProjection,
    raw_evidence: RawEvidencePack,
    evidence_snapshot_v2: EvidenceSnapshotV2 | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    max_semantic_verifier_calls: int = 0,
    require_semantic_verifier: bool | None = None,
) -> TextEvidenceValidationReport:
    evidence_by_id = {item.evidence_id: item for item in raw_evidence.evidence_items}
    v2_by_id = {
        span.evidence_id: span
        for span in (evidence_snapshot_v2.spans if evidence_snapshot_v2 else [])
        if is_direct_code_span(span)
    }
    projection_by_id = {claim.claim_id: claim for claim in projection.projected_claims}
    verdicts: list[TextClaimEvidenceVerdict] = []
    verifier_calls = 0
    for claim in final_claims.atomic_claims:
        matches = [projection_by_id[item] for item in claim.candidate_projection_claim_ids if item in projection_by_id]
        failures: list[str] = []
        if not matches:
            failures.append("no_semantically_matching_projected_claim")
        direct_ids = _dedupe([evidence_id for item in matches for evidence_id in item.direct_evidence_ids])
        missing_ids = [
            item for item in direct_ids
            if item not in (v2_by_id if evidence_snapshot_v2 is not None else evidence_by_id)
        ]
        if missing_ids or not direct_ids:
            failures.append("direct_evidence_missing")
        if evidence_snapshot_v2 is not None:
            evidence_text = "\n".join(v2_by_id[item].exact_excerpt for item in direct_ids if item in v2_by_id)
        else:
            evidence_text = "\n".join(
                _evidence_text(evidence_by_id[item], project_root=raw_evidence.project_root)
                for item in direct_ids
                if item in evidence_by_id and is_direct_code_path(evidence_by_id[item].path)
            )
        if matches and not _relevant_to_evidence(claim.text, evidence_text, matches):
            failures.append("direct_evidence_semantically_unrelated")
        required_qualifiers = _dedupe([qualifier for item in matches for qualifier in item.required_qualifiers])
        if required_qualifiers and not _qualifier_preserved(claim.text, required_qualifiers):
            failures.append("required_qualifier_missing")
        if _wording_strength_exceeded(claim.text, matches):
            failures.append("allowed_wording_boundary_exceeded")
        if "number" in claim.high_risk_markers and not _numeric_tokens_supported(claim.text, evidence_text, projection):
            failures.append("numeric_token_not_in_direct_evidence")
        if "formula" in claim.high_risk_markers and not _formula_tokens_supported(claim.text, evidence_text, projection):
            failures.append("formula_not_in_direct_evidence")
        if evidence_snapshot_v2 is None and direct_ids and any(
            evidence_by_id[item].source_type == SourceType.AUTHOR for item in direct_ids if item in evidence_by_id
        ):
            failures.append("author_context_cannot_be_direct_code_evidence")

        model_verdict = ""
        model_rationale = ""
        model_supported_fragment = ""
        model_unsupported_fragment = ""
        verifier_required = (
            max_semantic_verifier_calls > 0
            if require_semantic_verifier is None
            else require_semantic_verifier
        )
        if not failures and semantic_verifier is not None and verifier_calls < max_semantic_verifier_calls:
            verifier_calls += 1
            proposal = semantic_verifier(
                {
                    "claim": claim.text,
                    "direct_evidence": evidence_text,
                    "allowed_boundaries": [item.allowed_wording_boundary for item in matches],
                    "required_qualifiers": required_qualifiers,
                }
            )
            if proposal is None:
                failures.append("semantic_verifier_unavailable")
            else:
                model_verdict = str(proposal.get("status") or "").lower()
                model_rationale = str(proposal.get("rationale") or "")
                model_supported_fragment = str(proposal.get("supported_fragment") or "")
                model_unsupported_fragment = str(proposal.get("unsupported_fragment") or "")
                if model_verdict not in {"supported", "caveated"}:
                    failures.append("semantic_verifier_rejected_claim")
        elif not failures and verifier_required:
            failures.append(
                "semantic_verifier_budget_exhausted"
                if semantic_verifier is not None
                else "semantic_verifier_unavailable"
            )

        partial = any(item.support_status == "partial" for item in matches)
        status = "unsupported" if failures else ("caveated" if partial else "supported")
        verdicts.append(
            TextClaimEvidenceVerdict(
                atomic_claim_id=claim.atomic_claim_id,
                status=status,
                matched_projection_claim_ids=[item.claim_id for item in matches],
                direct_evidence_ids=direct_ids,
                supported_fragment=(model_supported_fragment or claim.text) if not failures else model_supported_fragment,
                unsupported_fragment=(model_unsupported_fragment or claim.text) if failures else "",
                required_qualifiers=required_qualifiers,
                deterministic_failures=failures,
                model_verdict=model_verdict,
                rationale=model_rationale or ("; ".join(failures) if failures else "Direct evidence and projection constraints passed."),
                repair_action=_repair_action(failures),
            )
        )
    unsupported = sum(item.status == "unsupported" for item in verdicts)
    unverified = sum(item.status == "unverified" for item in verdicts)
    status = "passed" if final_claims.deterministic_completeness_passed and not unsupported and not unverified else "failed"
    actions = _dedupe(item.repair_action for item in verdicts if item.repair_action)
    if not final_claims.deterministic_completeness_passed:
        actions.append("repair_final_claim_extraction_completeness")
    return TextEvidenceValidationReport(
        status=status,
        input_text_digest=final_claims.input_text_digest,
        projection_digest=projection.projection_digest,
        repo_snapshot_id=projection.repo_snapshot_id,
        project_tree_hash=projection.project_tree_hash,
        evidence_snapshot_id=projection.evidence_snapshot_id,
        evidence_snapshot_digest=projection.evidence_snapshot_digest,
        checked_factual_claims=len(verdicts),
        supported_claims=sum(item.status == "supported" for item in verdicts),
        caveated_claims=sum(item.status == "caveated" for item in verdicts),
        unsupported_claims=unsupported,
        unverified_claims=unverified,
        semantic_verifier_calls=verifier_calls,
        verdicts=verdicts,
        recommended_actions=actions,
    )


def write_text_evidence_validation(path: str | Path, report: TextEvidenceValidationReport) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_text_evidence_validation(path: str | Path) -> TextEvidenceValidationReport:
    return TextEvidenceValidationReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def report_digest(report: TextEvidenceValidationReport) -> str:
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _evidence_text(item: Any, *, project_root: str = "") -> str:
    metadata = " ".join(str(value or "") for value in (item.config_key, item.content_summary))
    excerpt = _source_excerpt(
        project_root=project_root,
        relative_path=str(getattr(item, "path", "") or ""),
        line_start=int(getattr(item, "line_start", 0) or 0),
        line_end=int(getattr(item, "line_end", 0) or 0),
    )
    return "\n".join(value for value in (metadata, excerpt) if value)


def _source_excerpt(*, project_root: str, relative_path: str, line_start: int, line_end: int) -> str:
    if not project_root or not relative_path or line_start <= 0 or line_end < line_start:
        return ""
    try:
        root = Path(project_root).resolve()
        candidate = (root / relative_path).resolve()
        candidate.relative_to(root)
        lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return ""
    return "\n".join(lines[line_start - 1 : min(line_end, len(lines))])


def _relevant_to_evidence(text: str, evidence_text: str, matches: list[Any]) -> bool:
    claim_tokens = _tokens(text)
    evidence_tokens = _tokens(evidence_text)
    projection_tokens = set().union(*(_tokens(item.supported_fragment) for item in matches)) if matches else set()
    projection_overlap = len(claim_tokens & projection_tokens) / max(1, min(len(claim_tokens), len(projection_tokens)))
    evidence_overlap = len(claim_tokens & evidence_tokens) / max(1, min(len(claim_tokens), len(evidence_tokens)))
    evidence_related = (
        evidence_overlap >= 0.12
        or len(claim_tokens & evidence_tokens) >= 2
        or concepts_semantically_related(text, evidence_text)
    )
    return projection_overlap >= 0.45 and evidence_related


def _qualifier_preserved(text: str, qualifiers: list[str]) -> bool:
    text_tokens = _tokens(text)
    for qualifier in qualifiers:
        if "only" in qualifier.lower() and "only" not in text.lower():
            continue
        key_tokens = _tokens(qualifier) - {"describe", "only", "implemented", "fragment", "omit", "unsupported"}
        if key_tokens and len(text_tokens & key_tokens) / len(key_tokens) >= 0.5:
            return True
        if not key_tokens and "only" in qualifier.lower() and "only" in text.lower():
            return True
    return False


def _wording_strength_exceeded(text: str, matches: list[Any]) -> bool:
    text_words = _tokens(text) & _STRONG_WORDS
    allowed_words = set().union(*(_tokens(item.allowed_wording_boundary) for item in matches)) if matches else set()
    return bool(text_words - allowed_words)


def _numeric_tokens_supported(text: str, evidence_text: str, projection: AuthoringInputProjection) -> bool:
    tokens = set(re.findall(r"\d+(?:\.\d+)?%?", text))
    allowed = evidence_text + " " + json.dumps(projection.safe_numeric_facts, ensure_ascii=False)
    return all(token in allowed for token in tokens)


def _formula_tokens_supported(text: str, evidence_text: str, projection: AuthoringInputProjection) -> bool:
    formulas = re.findall(r"\$([^$]+)\$|([A-Za-z]\s*=\s*[^,.;]+)", text)
    needed = {"".join(item).replace(" ", "") for item in formulas}
    allowed = (evidence_text + json.dumps(projection.safe_equations, ensure_ascii=False)).replace(" ", "")
    return bool(needed) and all(item in allowed for item in needed)


def _repair_action(failures: list[str]) -> str:
    if "semantic_verifier_rejected_claim" in failures:
        return "revise_authoring_from_verifier_fragments"
    if any(
        item in {"semantic_verifier_unavailable", "semantic_verifier_budget_exhausted"}
        for item in failures
    ):
        return "block_for_semantic_verifier_review"
    if "no_semantically_matching_projected_claim" in failures:
        return "revise_authoring_wording"
    if any("evidence" in item for item in failures):
        return "return_to_analysis_for_direct_evidence"
    if failures:
        return "revise_authoring_wording"
    return ""


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our", "this", "that", "with", "for"}
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1 and token not in stop}


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
