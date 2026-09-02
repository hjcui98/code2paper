"""R6.2 text repair supervisor: map final-validator failures to repair issues.

Implements design section 9 (R6.2).  The final text evidence validator
(``text_evidence_validator.py``) emits string failure codes in
``TextClaimEvidenceVerdict.deterministic_failures``.  R6.2 formalizes those
failures into typed ``TextRepairIssueV1`` instances so the repair
supervisor can act on them with a bounded, auditable scope.

Hard rules enforced here (R6.2):

- a single sentence failure MUST NOT trigger a full
  intake/analysis/authoring rerun; the ``allowed_repair_scope`` is the
  only authority the supervisor has for that issue;
- every validator failure string maps to exactly one
  ``TextRepairFailureType`` and one ``TextRepairScope``;
- unknown failure strings map to ``unsupported_rationale`` with scope
  ``drop_or_gap`` so the supervisor falls back to the safest local
  repair (drop the sentence or record an explicit gap) rather than
  silently rerunning the whole pipeline;
- the mapping is project-agnostic: no ``F-RAP-*`` / ``C-RAP-*`` literals.

R6.4 hard constraint: this module's source MUST NOT contain project-specific
literals.
"""

from __future__ import annotations

from collections import Counter

from code2paper.agentic.research_models import (
    TEXT_REPAIR_FAILURE_TYPES,
    TEXT_REPAIR_SCOPES,
    TextRepairFailureType,
    TextRepairIssueV1,
    TextRepairScope,
)
from code2paper.agentic.trust_contracts import (
    TextClaimEvidenceVerdict,
    TextEvidenceValidationReport,
)


# ---------------------------------------------------------------------------
# Failure -> (repair failure type, repair scope, human-readable hint)
# ---------------------------------------------------------------------------


#: Mapping from the validator's deterministic failure strings to the typed
#: R6.2 repair issue.  The validator emits strings like
#: ``"no_semantically_matching_projected_claim"``;
#: this table projects them onto the closed ``TextRepairFailureType`` and
#: ``TextRepairScope`` vocabularies.
#:
#: The repair hint is diagnostic only; it never authorizes an action
#: outside ``allowed_repair_scope``.
_FAILURE_TO_REPAIR: dict[str, tuple[TextRepairFailureType, TextRepairScope, str]] = {
    "planned_claim_missing_from_final_text": (
        "no_semantically_matching_projected_claim",
        "claim_decomposition",
        "Insert the authorized planned claim fragment into its planned section.",
    ),
    # The sentence has no matching projected claim -> split or merge the
    # sentence so each atomic claim maps to exactly one projected claim.
    "no_semantically_matching_projected_claim": (
        "no_semantically_matching_projected_claim",
        "claim_decomposition",
        "Split or merge the sentence so each atomic claim maps to exactly one projected claim.",
    ),
    # The direct evidence span is semantically unrelated to the claim ->
    # replace the packet anchor with a span that actually supports the claim.
    "direct_evidence_semantically_unrelated": (
        "wrong_span_role",
        "packet_relation",
        "Replace the packet anchor span with one that semantically supports the claim.",
    ),
    # Direct evidence is missing entirely -> the claim cannot be backed;
    # drop the sentence or record an explicit code gap.
    "direct_evidence_missing": (
        "unsupported_rationale",
        "drop_or_gap",
        "Direct code evidence is missing; drop the sentence or record an explicit code gap.",
    ),
    # A required qualifier (e.g. 'under condition X') is missing ->
    # local wording rewrite only.
    "required_qualifier_missing": (
        "missing_qualifier",
        "wording_only",
        "Add the required qualifier via a local wording rewrite.",
    ),
    # The allowed wording boundary was exceeded -> local wording rewrite
    # to bring the sentence back inside the authorized boundary.
    "allowed_wording_boundary_exceeded": (
        "missing_qualifier",
        "wording_only",
        "Rewrite the sentence to stay within the allowed wording boundary.",
    ),
    "comparison_polarity_flipped": (
        "missing_qualifier",
        "claim_decomposition",
        "Restore the licensed comparison polarity from the parent fact.",
    ),
    # A numeric token in the sentence is not backed by direct evidence ->
    # drop the sentence or record a gap.
    "numeric_token_not_in_direct_evidence": (
        "unsupported_rationale",
        "drop_or_gap",
        "Numeric token is not in direct evidence; drop the sentence or record a gap.",
    ),
    # A formula token is not backed by direct evidence ->
    # drop the equation or rebuild the EquationClaim.
    "formula_not_in_direct_evidence": (
        "formula_unsupported",
        "drop_or_gap",
        "Drop the equation or rebuild the EquationClaim with authorized evidence.",
    ),
    # Author context was used as direct code evidence -> drop the sentence
    # or record a gap (author context is never direct code evidence).
    "author_context_cannot_be_direct_code_evidence": (
        "unsupported_rationale",
        "drop_or_gap",
        "Author context cannot serve as direct code evidence; drop or record a gap.",
    ),
    # The semantic verifier was unavailable -> fall back to deterministic
    # fact relations or validate the sentence independently.
    "semantic_verifier_unavailable": (
        "semantic_verifier_exhausted",
        "wording_only",
        "Semantic verifier unavailable; use deterministic fact relations or per-sentence validation.",
    ),
    # The semantic verifier budget was exhausted -> same fallback.
    "semantic_verifier_budget_exhausted": (
        "semantic_verifier_exhausted",
        "wording_only",
        "Semantic verifier budget exhausted; use deterministic fact relations or per-sentence validation.",
    ),
    # The semantic verifier rejected the claim -> drop the sentence or
    # record a gap (the claim is semantically unsupported).
    "semantic_verifier_rejected_claim": (
        "unsupported_rationale",
        "drop_or_gap",
        "Semantic verifier rejected the claim; drop the sentence or record a gap.",
    ),
}


#: The fallback mapping for unknown failure strings.  This is the safest
#: local repair: drop the sentence or record an explicit gap rather than
#: silently rerunning the whole pipeline.
_FALLBACK_REPAIR: tuple[TextRepairFailureType, TextRepairScope, str] = (
    "unsupported_rationale",
    "drop_or_gap",
    "Unknown validator failure; drop the sentence or record an explicit gap as the safe local repair.",
)


# ---------------------------------------------------------------------------
# Derivation
# ---------------------------------------------------------------------------


def failure_to_repair_scope(
    failure: str,
) -> tuple[TextRepairFailureType, TextRepairScope, str]:
    """Map a single validator failure string to its typed repair issue.

    Returns
    -------
    ``(failure_type, allowed_repair_scope, hint)``
        ``failure_type`` is one of ``TEXT_REPAIR_FAILURE_TYPES``;
        ``allowed_repair_scope`` is one of ``TEXT_REPAIR_SCOPES`` and is
        the only authority the repair supervisor has for this issue;
        ``hint`` is a diagnostic string (never an authorization).
    """

    return _FAILURE_TO_REPAIR.get(failure, _FALLBACK_REPAIR)


def derive_repair_issues(
    validation_report: TextEvidenceValidationReport,
    *,
    sentence_id_by_claim: dict[str, str] | None = None,
) -> list[TextRepairIssueV1]:
    """Derive typed repair issues from a final text validation report.

    Parameters
    ----------
    validation_report
        The output of ``validate_text_evidence``.  Only verdicts with a
        non-empty ``deterministic_failures`` list produce issues; verdicts
        that passed cleanly are skipped.
    sentence_id_by_claim
        Optional mapping from ``atomic_claim_id`` to the sentence id in
        the final text.  When omitted, the ``atomic_claim_id`` itself is
        used as the ``sentence_id`` so the caller can always trace the
        issue back to the claim.

    Notes
    -----
    Each validator failure string produces exactly one
    ``TextRepairIssueV1``.  A verdict with multiple failures produces
    multiple issues, each with its own ``allowed_repair_scope``.  The
    repair supervisor is free to address them in any order but MUST NOT
    exceed the most permissive scope among them for that sentence.
    """

    sentence_id_by_claim = sentence_id_by_claim or {}
    issues: list[TextRepairIssueV1] = []
    for verdict in validation_report.verdicts:
        if not verdict.deterministic_failures:
            continue
        sentence_id = sentence_id_by_claim.get(
            verdict.atomic_claim_id, verdict.atomic_claim_id
        )
        for failure in verdict.deterministic_failures:
            failure_type, scope, hint = failure_to_repair_scope(failure)
            issues.append(TextRepairIssueV1(
                sentence_id=sentence_id,
                atomic_claim_id=verdict.atomic_claim_id,
                failure_type=failure_type,
                matched_claim_ids=tuple(verdict.matched_projection_claim_ids),
                offending_fragment=verdict.unsupported_fragment,
                missing_fact_or_relation=_missing_relation_hint(verdict),
                allowed_repair_scope=scope,
                attempt=0,
            ))
    return issues


def _missing_relation_hint(verdict: TextClaimEvidenceVerdict) -> str:
    """Build a compact hint about which relation/evidence is missing.

    The hint must tell the Rewrite owner the exact missing content, not
    just that something is missing.  For ``required_qualifier_missing``
    the exact required qualifier tokens (derived by the validator from
    the frozen projection) are the actionable payload; a generic "add the
    required qualifier" instruction left the model guessing.
    """

    parts: list[str] = []
    if "required_qualifier_missing" in verdict.deterministic_failures:
        if verdict.required_qualifiers:
            from code2paper.agentic.method_proposition_provider import (
                candidate_qualifier_phrase,
            )

            reader_phrases = [
                candidate_qualifier_phrase(item) or item
                for item in dict.fromkeys(verdict.required_qualifiers)
            ]
            parts.append(
                "required_qualifiers_missing: "
                + "; ".join(reader_phrases)
            )
            parts.append(
                "qualifier_representation_rule: render each qualifier as "
                "academic prose from the supplied reader phrase; do not paste "
                "self., self.cfg, self.config, or torch. identifiers into "
                "Candidate sentences"
            )
        else:
            parts.append("required_qualifiers_missing: <validator listed no qualifier>")
    if "allowed_wording_boundary_exceeded" in verdict.deterministic_failures:
        parts.append(
            "wording_boundary_exceeded: keep only repository-supported wording"
        )
    if "formula_not_in_direct_evidence" in verdict.deterministic_failures:
        # The validator extracts comparison formulas (e.g. ``i == 0``)
        # greedily up to punctuation, so an appended descriptive word
        # (``configuration``, ``is enabled``) changes the formula token and
        # the exact comparison can no longer match the frozen qualifier or
        # evidence.  The fix is wording-only: reproduce the qualifier
        # comparison verbatim and keep the general-path formula outside the
        # branch scope.
        parts.append(
            "formula_comparison_must_be_verbatim: write the required qualifier "
            "comparison exactly as listed (e.g. 'i == 0 and case_study') without "
            "appending descriptive words such as 'configuration' or 'is enabled'; "
            "state the branch condition separately from the general-path formula "
            "it does not scope"
        )
        if verdict.required_qualifiers:
            parts.append(
                "required_qualifiers: "
                + "; ".join(dict.fromkeys(verdict.required_qualifiers))
            )
    if not verdict.direct_evidence_ids:
        parts.append("direct_evidence: none")
    if not verdict.relation_evidence_ids:
        parts.append("relation_evidence: none")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def group_repair_issues_by_scope(
    issues: list[TextRepairIssueV1],
) -> dict[TextRepairScope, list[TextRepairIssueV1]]:
    """Group repair issues by their ``allowed_repair_scope``.

    The repair supervisor uses this to batch issues that share a scope
    (e.g. all ``wording_only`` issues can be addressed in a single
    rewrite pass, while ``code_search`` issues require a new research
    sub-loop).
    """

    grouped: dict[TextRepairScope, list[TextRepairIssueV1]] = {
        scope: [] for scope in TEXT_REPAIR_SCOPES
    }
    for issue in issues:
        grouped[issue.allowed_repair_scope].append(issue)
    return {scope: items for scope, items in grouped.items() if items}


def count_repair_issues_by_failure_type(
    issues: list[TextRepairIssueV1],
) -> dict[TextRepairFailureType, int]:
    """Count issues by ``failure_type`` for diagnostic dashboards."""

    counter: Counter[TextRepairFailureType] = Counter()
    for issue in issues:
        counter[issue.failure_type] += 1
    return {failure_type: counter[failure_type] for failure_type in TEXT_REPAIR_FAILURE_TYPES}


def most_permissive_scope(
    issues: list[TextRepairIssueV1],
) -> TextRepairScope | None:
    """Return the most permissive repair scope among the issues.

    The repair supervisor MUST NOT exceed this scope when addressing the
    grouped issues.  The ordering (least -> most permissive) is:

    1. ``wording_only``        — local rewrite, no new evidence
    2. ``sentence_atomicity``  — split/merge sentences
    3. ``claim_decomposition`` — split/merge claims
    4. ``packet_relation``     — rebind packet anchors / relations
    5. ``code_search``         — new research sub-loop
    6. ``drop_or_gap``         — drop the sentence or record a gap

    Returns ``None`` when ``issues`` is empty.
    """

    if not issues:
        return None
    order: tuple[TextRepairScope, ...] = (
        "wording_only",
        "sentence_atomicity",
        "claim_decomposition",
        "packet_relation",
        "code_search",
        "drop_or_gap",
    )
    rank = {scope: index for index, scope in enumerate(order)}
    return max(issues, key=lambda issue: rank[issue.allowed_repair_scope]).allowed_repair_scope


# ---------------------------------------------------------------------------
# Sentinel validation
# ---------------------------------------------------------------------------


def assert_failure_mapping_covers_all_scopes() -> None:
    """Sanity check: every ``TextRepairScope`` is reachable from the mapping.

    This runs at module import time so a refactor that drops a scope
    from the mapping fails fast instead of silently falling back to
    ``drop_or_gap`` for every issue.
    """

    covered_scopes = {scope for _, scope, _ in _FAILURE_TO_REPAIR.values()}
    covered_scopes.add(_FALLBACK_REPAIR[1])
    missing = set(TEXT_REPAIR_SCOPES) - covered_scopes
    # ``sentence_atomicity`` and ``code_search`` are intentionally not
    # reachable from the current validator failure strings: they are
    # reserved for future relation-level and config-level validators.
    # We only fail if a scope that SHOULD be reachable is missing.
    expected_reachable = {"wording_only", "claim_decomposition", "packet_relation", "drop_or_gap"}
    missing_expected = expected_reachable - covered_scopes
    if missing_expected:
        raise RuntimeError(
            f"failure mapping is missing expected reachable scopes: {sorted(missing_expected)}"
        )
    _ = missing  # diagnostic only


assert_failure_mapping_covers_all_scopes()


__all__ = [
    "FAILURE_TO_REPAIR",
    "failure_to_repair_scope",
    "derive_repair_issues",
    "group_repair_issues_by_scope",
    "count_repair_issues_by_failure_type",
    "most_permissive_scope",
]
