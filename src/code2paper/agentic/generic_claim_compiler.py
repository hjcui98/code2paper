"""R4.3 generic claim compiler: ``CodeFactV1`` -> ``AtomicClaimV3``.

This module implements design section 9.3 (claim decomposition).  The LLM
proposes natural-language claims and fact groupings; the deterministic
authorizer verifies that every factual component of the claim is backed by
a supported fact and that the claim does not expand quantifiers, direction,
conditions or effects beyond what the facts authorize.

Authorization checks (R4.3):

- ``fact_ids_subset``: every proposed fact id exists and is
  ``validation_status="supported"``;
- ``no_quantifier_expansion``: quantifier words (``always``, ``never``,
  ``all``, ``none``, ``every``, ``only``) in the claim text must be backed
  by the facts' conditions;
- ``no_direction_expansion``: direction words (``increases``, ``decreases``,
  ``faster``, ``slower``, ``before``, ``after``) must be backed by a
  ``COMPUTE`` / ``COMPARE`` fact;
- ``no_condition_expansion``: the claim's ``required_qualifiers`` must be a
  superset of the union of facts' conditions (a guard cannot be silently
  dropped);
- ``no_contradictory_conditions``: two facts with contradictory conditions
  (``X`` and ``not X``) cannot be merged into one claim;
- ``canonical_identity_dedup``: same (normalized text, fact ids) yields the
  same identity; duplicates are rejected;
- ``rationale_separated``: ``unsupported_author_fragments`` must not
  contain implementation predicates;
- ``stage_introduction_has_facts``: a claim that reads like a stage
  introduction (short declarative sentence) must still have its own facts.

R4.5 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    ExplicitCodeGapV1,
    GENERIC_RESEARCH_PRODUCER_VERSION,
    SemanticStageGroupV1,
)


# ---------------------------------------------------------------------------
# Proposal input (R4.3)
# ---------------------------------------------------------------------------


class ClaimProposalV1(BaseModel):
    """LLM-proposed atomic claim with fact grouping (R4.3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    canonical_text: str
    claim_kind: str = "implementation_behavior"
    proposed_fact_ids: list[str]
    covers_obligation_ids: list[str] = Field(default_factory=list)
    required_qualifiers: list[str] = Field(default_factory=list)
    unsupported_author_fragments: list[str] = Field(default_factory=list)
    allowed_wording_boundary: str = ""


class ClaimAuthorizationReportV1(BaseModel):
    """Deterministic authorization report for a proposed claim.

    ``failures`` is a list of stable, machine-parseable failure codes.  An
    empty list means the claim is authorized.  The semantic verifier (LLM)
    may *append* observations to ``semantic_notes`` but MUST NOT remove
    items from ``failures``: a deterministic failure cannot be overridden
    by a semantic pass (R4.5 hard constraint).
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    failures: list[str] = Field(default_factory=list)
    semantic_notes: list[str] = Field(default_factory=list)

    @property
    def authorized(self) -> bool:
        return not self.failures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", value.lower()))


_QUANTIFIER_WORDS: tuple[str, ...] = (
    "always", "never", "all", "none", "every", "only", "exclusively",
    "invariably", "uniformly",
)
_DIRECTION_WORDS: tuple[str, ...] = (
    "increases", "decreases", "faster", "slower", "before", "after",
    "improves", "degrades", "ascending", "descending",
)
# Predicates that license a direction claim (must be present in the facts
# for a direction word to be authorized).
_DIRECTION_PREDICATES: frozenset[str] = frozenset({
    "computes_formula", "compares", "sorts_by", "selects_top_k", "aggregates",
    "reduces",
})
# Predicates that license a quantifier claim (universal / existential).
_QUANTIFIER_PREDICATES: frozenset[str] = frozenset({
    "filters_by", "selects", "selects_column", "selects_top_k", "loops",
    "aggregates", "reduces", "branches_on",
})


def _words_in(text: str, words: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            found.append(word)
    return found


def _contradictory(condition_a: str, condition_b: str) -> bool:
    """Heuristic: two conditions are contradictory if one is ``X`` and the
    other is ``not X`` / ``X is False`` / etc."""

    a = condition_a.strip().lower()
    b = condition_b.strip().lower()
    if a == b:
        return False
    # Strip a leading negation and compare.
    negations = ("not ", "!", "no ")
    a_neg = any(a.startswith(n) for n in negations) and a.split(" ", 1)[-1].strip()
    b_neg = any(b.startswith(n) for n in negations) and b.split(" ", 1)[-1].strip()
    if a_neg and a_neg == b:
        return True
    if b_neg and b_neg == a:
        return True
    return False


# ---------------------------------------------------------------------------
# Core: authorize a single claim proposal
# ---------------------------------------------------------------------------


def authorize_claim(
    proposal: ClaimProposalV1,
    facts: CodeFactSetV1,
    *,
    seen_identities: set[str] | None = None,
) -> tuple[AtomicClaimV3 | None, ClaimAuthorizationReportV1]:
    """Authorize a single claim proposal against a fact set.

    Returns ``(claim, report)``.  When ``report.failures`` is non-empty the
    claim is ``None`` (not authorized).  The report's failures explain why.
    """

    failures: list[str] = []
    fact_by_id = {f.fact_id: f for f in facts.facts}

    # 1) fact_ids_subset: every proposed fact must exist and be supported.
    selected_facts: list[CodeFactV1] = []
    for fid in proposal.proposed_fact_ids:
        fact = fact_by_id.get(fid)
        if fact is None:
            failures.append(f"unknown_fact:{fid}")
            continue
        if fact.validation_status != "supported":
            failures.append(f"unsupported_fact:{fid}:{fact.validation_status}")
            continue
        selected_facts.append(fact)

    # 2) no_quantifier_expansion
    quantifiers_found = _words_in(proposal.canonical_text, _QUANTIFIER_WORDS)
    if quantifiers_found:
        has_quantifier_fact = any(
            f.predicate in _QUANTIFIER_PREDICATES for f in selected_facts
        )
        if not has_quantifier_fact:
            failures.append(
                f"quantifier_without_licensing_fact:{','.join(quantifiers_found)}"
            )

    # 3) no_direction_expansion
    directions_found = _words_in(proposal.canonical_text, _DIRECTION_WORDS)
    if directions_found:
        has_direction_fact = any(
            f.predicate in _DIRECTION_PREDICATES for f in selected_facts
        )
        if not has_direction_fact:
            failures.append(
                f"direction_without_licensing_fact:{','.join(directions_found)}"
            )

    # 4) no_condition_expansion: required_qualifiers must cover fact conditions
    declared_qualifiers = set(proposal.required_qualifiers)
    all_conditions: list[str] = []
    for fact in selected_facts:
        for cond in fact.conditions:
            all_conditions.append(cond)
            if cond not in declared_qualifiers:
                failures.append(f"dropped_condition:{fact.fact_id}:{cond}")

    # 5) no_contradictory_conditions: two facts with contradictory guards
    #    cannot be merged.
    for i, cond_a in enumerate(all_conditions):
        for cond_b in all_conditions[i + 1:]:
            if _contradictory(cond_a, cond_b):
                failures.append(
                    f"contradictory_conditions:{cond_a}::{cond_b}"
                )

    # 6) canonical_identity_dedup
    identity = _digest({
        "behavior": _normalize_text(proposal.canonical_text),
        "fact_ids": sorted(proposal.proposed_fact_ids),
    })
    if seen_identities is not None and identity in seen_identities:
        failures.append(f"duplicate_canonical_identity:{identity}")
    if seen_identities is not None:
        seen_identities.add(identity)

    # 7) rationale_separated: unsupported_author_fragments must not contain
    #    implementation predicates (they're for rationale/effect/performance
    #    prose only).
    for fragment in proposal.unsupported_author_fragments:
        fragment_lower = fragment.lower()
        for pred in ("reads", "writes", "calls", "constructs", "returns", "transforms"):
            if pred in fragment_lower:
                failures.append(
                    f"rationale_contains_implementation_predicate:{pred}"
                )
                break

    # 8) stage_introduction_has_facts: a short declarative sentence
    #    (stage introduction) must still have at least one fact.
    if not proposal.proposed_fact_ids:
        failures.append("stage_introduction_without_facts")

    # 9) allowed_wording_boundary must be non-empty (the claim must declare
    #    its wording boundary so a downstream writer cannot paraphrase past
    #    it).
    if not proposal.allowed_wording_boundary.strip():
        failures.append("missing_wording_boundary")

    report = ClaimAuthorizationReportV1(
        claim_id=proposal.claim_id,
        failures=failures,
    )
    if failures:
        return None, report

    # Build the authorized AtomicClaimV3.
    direct_evidence_ids: list[str] = []
    relation_evidence_ids: list[str] = []
    for fact in selected_facts:
        for span in fact.direct_span_ids:
            if span not in direct_evidence_ids:
                direct_evidence_ids.append(span)
        for rel in fact.relation_evidence_ids:
            if rel not in relation_evidence_ids:
                relation_evidence_ids.append(rel)

    claim = AtomicClaimV3(
        claim_id=proposal.claim_id,
        canonical_text=proposal.canonical_text,
        claim_kind=proposal.claim_kind,  # type: ignore[arg-type]
        fact_ids=list(proposal.proposed_fact_ids),
        covers_obligation_ids=list(proposal.covers_obligation_ids),
        direct_evidence_ids=direct_evidence_ids,
        relation_evidence_ids=relation_evidence_ids,
        required_qualifiers=list(proposal.required_qualifiers),
        unsupported_author_fragments=list(proposal.unsupported_author_fragments),
        allowed_wording_boundary=proposal.allowed_wording_boundary,
        canonical_identity=identity,
        status="supported",
    )
    return claim, report


# ---------------------------------------------------------------------------
# Core: compile a batch of claim proposals into an AtomicClaimSetV3
# ---------------------------------------------------------------------------


def compile_atomic_claims(
    proposals: list[ClaimProposalV1],
    facts: CodeFactSetV1,
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
    evidence_packet_digest: str,
    explicit_code_gaps: list[ExplicitCodeGapV1] | None = None,
    include_technical_claims: bool = True,
) -> tuple[AtomicClaimSetV3, list[ClaimAuthorizationReportV1]]:
    """Authorize a batch of claim proposals.

    Returns ``(claim_set, reports)``.  ``claim_set`` contains only the
    authorized claims; ``reports`` contains one report per proposal (so the
    caller can explain why a proposal was rejected).
    """

    seen_identities: set[str] = set()
    authorized_claims: list[AtomicClaimV3] = []
    reports: list[ClaimAuthorizationReportV1] = []
    for proposal in proposals:
        claim, report = authorize_claim(
            proposal, facts, seen_identities=seen_identities
        )
        reports.append(report)
        if claim is not None:
            authorized_claims.append(claim)

    claims_by_obligation: dict[str, list[AtomicClaimV3]] = {}
    unscoped: list[AtomicClaimV3] = []
    for claim in authorized_claims:
        if claim.covers_obligation_ids:
            for obligation_id in claim.covers_obligation_ids:
                claims_by_obligation.setdefault(obligation_id, []).append(claim)
        else:
            unscoped.append(claim)
    if unscoped:
        claims_by_obligation["implementation"] = unscoped
    stage_groups: list[SemanticStageGroupV1] = []
    for index, (obligation_id, grouped_claims) in enumerate(
        claims_by_obligation.items(), start=1
    ):
        ordered_ids = list(dict.fromkeys(claim.claim_id for claim in grouped_claims))
        stage_groups.append(
            SemanticStageGroupV1(
                stage_id=(
                    f"SG-{index:02d}-"
                    + hashlib.sha256(obligation_id.encode("utf-8")).hexdigest()[:8]
                ),
                name=f"Implementation stage {index}",
                purpose=" ".join(claim.canonical_text for claim in grouped_claims),
                ordered_claim_ids=ordered_ids,
                covers_obligation_ids=(
                    [] if obligation_id == "implementation" else [obligation_id]
                ),
                relation_evidence_ids=list(dict.fromkeys(
                    relation
                    for claim in grouped_claims
                    for relation in claim.relation_evidence_ids
                )),
                organization_priority=index,
            )
        )

    payload = {
        "claims": [c.model_dump(mode="json") for c in authorized_claims],
        "explicit_code_gaps": [
            g.model_dump(mode="json")
            for g in (explicit_code_gaps or [])
        ],
        "semantic_stage_groups": [
            group.model_dump(mode="json") for group in stage_groups
        ],
    }
    claim_set = AtomicClaimSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        evidence_packet_digest=evidence_packet_digest,
        code_fact_digest=facts.content_digest,
        claims=authorized_claims,
        explicit_code_gaps=explicit_code_gaps or [],
        semantic_stage_groups=stage_groups,
        content_digest=_digest(payload),
    )
    if include_technical_claims:
        from code2paper.agentic.scientific_claim_ir import append_technical_claims

        claim_set = append_technical_claims(claim_set, facts)
    return claim_set, reports


__all__ = [
    "ClaimAuthorizationReportV1",
    "ClaimProposalV1",
    "authorize_claim",
    "compile_atomic_claims",
]
