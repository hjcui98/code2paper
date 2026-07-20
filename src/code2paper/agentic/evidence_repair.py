from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.agentic.evidence_sufficiency import EvidenceSufficiencyDecision, EvidenceSufficiencyReport
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport
from code2paper.core.schemas import ClaimEvidenceMap


class EvidenceRepairCandidate(BaseModel):
    """Candidate code location for repairing one weak claim."""

    model_config = ConfigDict(extra="forbid")

    path: str
    symbol: str = ""
    kind: str = ""
    start_line: int = 1
    end_line: int = 1
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class EvidenceRepairClaimTarget(BaseModel):
    """One weak claim and the ranked code candidates to inspect next."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_query: str = ""
    candidates: list[EvidenceRepairCandidate] = Field(default_factory=list)


class EvidenceRepairFocus(BaseModel):
    """Actionable focus passed from evidence sufficiency back to analysis/intake."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "evidence-repair-focus"
    source_decision: str = ""
    focus_claim_ids: list[str] = Field(default_factory=list)
    missing_evidence_claim_ids: list[str] = Field(default_factory=list)
    unsupported_claim_ids: list[str] = Field(default_factory=list)
    caveated_claim_ids: list[str] = Field(default_factory=list)
    claim_queries: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    priority_paths: list[str] = Field(default_factory=list)
    claim_support_files: list[str] = Field(default_factory=list)
    symbol_targets: list[dict[str, str]] = Field(default_factory=list)
    claim_targets: list[EvidenceRepairClaimTarget] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


def build_evidence_repair_focus(
    *,
    decision: EvidenceSufficiencyDecision,
    report: EvidenceSufficiencyReport,
    claim_verification: ClaimVerificationReport,
    claim_map: ClaimEvidenceMap,
    symbol_index: SymbolIndexReport | None = None,
    source_decision: str = "",
    max_candidates_per_claim: int = 8,
) -> EvidenceRepairFocus:
    """Turn a sufficiency decision into concrete repair hints for the next pass."""

    focus_ids = _dedupe(
        [
            *decision.focus_claim_ids,
            *report.missing_evidence_claim_ids,
            *report.unsupported_claim_ids,
        ]
    )
    claim_text_by_id = {claim.claim_id: claim.claim_text for claim in claim_map.claims}
    verified_by_id = {claim.claim_id: claim for claim in claim_verification.claims}
    claim_queries_by_id = {
        claim_id: _claim_query(claim_id, claim_text_by_id.get(claim_id, ""))
        for claim_id in focus_ids
    }
    claim_queries = [claim_queries_by_id[claim_id] for claim_id in focus_ids]
    claim_targets = _claim_targets(
        focus_ids=focus_ids,
        claim_queries_by_id=claim_queries_by_id,
        symbol_index=symbol_index,
        max_candidates_per_claim=max_candidates_per_claim,
    )
    priority_paths = _candidate_paths(claim_targets)
    symbol_targets = _symbol_targets(claim_targets)
    missing_ids = [claim_id for claim_id in focus_ids if verified_by_id.get(claim_id) and verified_by_id[claim_id].missing_evidence_ids]
    unsupported_ids = [claim_id for claim_id in focus_ids if claim_id in report.unsupported_claim_ids]
    caveated_ids = [claim_id for claim_id in focus_ids if claim_id in report.caveated_claim_ids]
    actions: list[str] = []
    if missing_ids:
        actions.append("retrieve_missing_evidence_ids_for_focus_claims")
    if unsupported_ids:
        actions.append("reassess_or_exclude_unsupported_focus_claims")
    if caveated_ids:
        actions.append("strengthen_or_keep_caveats_for_partial_focus_claims")
    if not actions:
        actions.append("review_focus_claims_before_next_evidence_freeze")
    return EvidenceRepairFocus(
        source_decision=source_decision,
        focus_claim_ids=focus_ids,
        missing_evidence_claim_ids=_dedupe(missing_ids),
        unsupported_claim_ids=_dedupe(unsupported_ids),
        caveated_claim_ids=_dedupe(caveated_ids),
        claim_queries=claim_queries,
        search_keywords=_dedupe([*_tokens_from_queries(claim_queries), *focus_ids])[:80],
        priority_paths=priority_paths,
        claim_support_files=priority_paths,
        symbol_targets=symbol_targets,
        claim_targets=claim_targets,
        recommended_actions=actions,
    )


def focus_to_retrieval_overlay(focus: EvidenceRepairFocus) -> dict[str, object]:
    """Expose repair focus in the same shape accepted by intake retrieval hints."""

    return {
        key: value
        for key, value in {
            "priority_paths": focus.priority_paths,
            "claim_support_files": focus.claim_support_files or focus.priority_paths,
            "symbol_targets": focus.symbol_targets,
            "claim_targets": [target.model_dump(mode="json") for target in focus.claim_targets],
            "search_keywords": _dedupe([*focus.claim_queries, *focus.search_keywords]),
            "source_decision": focus.source_decision,
            "focus_claim_ids": focus.focus_claim_ids,
        }.items()
        if value
    }


def rank_evidence_repair_candidates(
    *,
    query: str,
    symbol_index: SymbolIndexReport | None,
    limit: int = 16,
) -> list[EvidenceRepairCandidate]:
    """Rank existing symbol-index entries for an obligation repair query."""

    candidates = list((symbol_index.candidates if symbol_index else []) or [])
    ranked = _rank_candidates_for_claim(query=query, candidates=candidates)
    query_tokens = _tokens(query)
    # The generic symbol index score contains accumulated legacy retrieval-target
    # matches and can dominate the active obligation. Re-rank primarily by tokens
    # from the current question so RAP's prune_pure_feature is not hidden below a
    # broad GaussianModel class merely because the latter matched many old targets.
    ranked.sort(
        key=lambda candidate: (
            -sum(token in " ".join([candidate.path, candidate.symbol, " ".join(candidate.reasons)]).lower() for token in query_tokens),
            -candidate.score,
            candidate.path,
            candidate.start_line,
        )
    )
    return ranked[: max(0, limit)]


def write_evidence_repair_focus(path: str | Path, focus: EvidenceRepairFocus) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(focus.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def load_evidence_repair_focus(path: str | Path) -> EvidenceRepairFocus | None:
    candidate = Path(path)
    if not candidate.exists():
        return None
    try:
        return EvidenceRepairFocus.model_validate(json.loads(candidate.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _claim_query(claim_id: str, claim_text: str) -> str:
    text = " ".join(str(claim_text or "").strip().split())
    if not text:
        return claim_id
    return f"{claim_id}: {text}"[:220]


def _tokens_from_queries(queries: list[str]) -> list[str]:
    tokens: list[str] = []
    for query in queries:
        tokens.extend(_tokens(query))
    return _dedupe(tokens)


def _claim_targets(
    *,
    focus_ids: list[str],
    claim_queries_by_id: dict[str, str],
    symbol_index: SymbolIndexReport | None,
    max_candidates_per_claim: int,
) -> list[EvidenceRepairClaimTarget]:
    candidates = list((symbol_index.candidates if symbol_index else []) or [])
    targets: list[EvidenceRepairClaimTarget] = []
    for claim_id in focus_ids:
        query = claim_queries_by_id.get(claim_id, claim_id)
        scored = _rank_candidates_for_claim(query=query, candidates=candidates)
        targets.append(
            EvidenceRepairClaimTarget(
                claim_id=claim_id,
                claim_query=query,
                candidates=scored[:max_candidates_per_claim],
            )
        )
    return targets


def _rank_candidates_for_claim(
    *,
    query: str,
    candidates: list[SymbolIndexEntry],
) -> list[EvidenceRepairCandidate]:
    query_tokens = _tokens(query)
    ranked: list[EvidenceRepairCandidate] = []
    for candidate in candidates:
        haystack = _candidate_haystack(candidate)
        matched_tokens = [token for token in query_tokens if token.lower() in haystack]
        if not matched_tokens:
            continue
        token_score = len(matched_tokens) * 0.25
        ranked.append(
            EvidenceRepairCandidate(
                path=candidate.path,
                symbol=candidate.symbol,
                kind=candidate.kind,
                start_line=candidate.start_line,
                end_line=candidate.end_line,
                score=round(float(candidate.score or 0.0) + token_score, 4),
                reasons=_dedupe(
                    [
                        *candidate.reasons,
                        *[f"claim_token:{token}" for token in matched_tokens[:8]],
                    ]
                )[:12],
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.path, item.start_line, item.symbol))
    return ranked


def _candidate_haystack(candidate: SymbolIndexEntry) -> str:
    return " ".join(
        [
            candidate.path,
            candidate.symbol,
            candidate.kind,
            candidate.parent,
            candidate.docstring,
            " ".join(candidate.reasons),
            " ".join(candidate.matched_target_ids),
        ]
    ).lower()


def _candidate_paths(claim_targets: list[EvidenceRepairClaimTarget]) -> list[str]:
    paths: list[str] = []
    for target in claim_targets:
        paths.extend(candidate.path for candidate in target.candidates)
    return _dedupe(paths)[:40]


def _symbol_targets(claim_targets: list[EvidenceRepairClaimTarget]) -> list[dict[str, str]]:
    targets: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for claim_target in claim_targets:
        for candidate in claim_target.candidates:
            if not candidate.path or not candidate.symbol:
                continue
            key = (claim_target.claim_id, candidate.path, candidate.symbol)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                {
                    "claim_id": claim_target.claim_id,
                    "path": candidate.path,
                    "symbol": candidate.symbol,
                    "kind": candidate.kind,
                    "source": "evidence_repair_focus",
                }
            )
    return targets[:80]


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in text.replace("_", " ").replace("-", " ").split():
        clean = "".join(ch for ch in token if ch.isalnum()).lower()
        if len(clean) >= 4:
            tokens.append(clean)
    return _dedupe(tokens)


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
