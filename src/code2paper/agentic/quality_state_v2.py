"""R6.3 quality state computation: derive QualityStateV2 from run artifacts.

Implements design section 9 (R6.3).  The ``QualityStateV2`` contract and
the ``quality_state_dominates`` Pareto selector were defined in R0
(``research_models.py``).  This module provides the *computation* layer:
given a run's obligation coverage report, claim set, final text
validation report, and invariant audit, derive the safety / content /
minimality / cost dimensions that feed ``QualityStateV2``.

Hard rules enforced here (R6.3):

- ``unsupported_positive_claims`` is the count of final-text atomic
  claims whose verdict status is ``unsupported``; the state is untrusted
  when this is nonzero;
- ``supported_must_cover`` counts only ``must_cover`` obligations whose
  coverage status is ``supported`` (NOT ``partial`` and NOT
  ``explicit_gap``);
- ``terminal_must_cover`` counts ``must_cover`` obligations whose
  coverage status is terminal (``supported``, ``partial``,
  ``explicit_gap`` or ``blocked``);
- ``explicit_gap`` obligations reduce ``unresolved_high_value_obligations``
  but never count as ``supported``;
- ``duplicate_claims`` counts atomic claims that share the same
  ``canonical_identity`` with another claim in the same set;
- ``unjustified_fan_in`` counts claims whose ``direct_evidence_ids``
  list has more than three entries (a heuristic for over-supported
  claims that bloat the Method section);
- cost dimensions are populated from the run's tool/model call counters
  when available, defaulting to zero.

R6.4 hard constraint: this module's source MUST NOT contain project-specific
literals.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2
from code2paper.agentic.research_models import (
    QualityContentDimensionsV1,
    QualityCostDimensionsV1,
    QualityMinimalityDimensionsV1,
    QualitySafetyDimensionsV1,
    QualityStateV2,
)
from code2paper.agentic.trust_contracts import TextEvidenceValidationReport


# ---------------------------------------------------------------------------
# Heuristic thresholds
# ---------------------------------------------------------------------------


#: A claim with more than this many direct evidence spans is considered
#: over-supported and contributes to ``unjustified_fan_in``.  Three is
#: the design default: one anchor span + at most two relation spans.
_MAX_DIRECT_EVIDENCE_FOR_FAN_IN: int = 3


# ---------------------------------------------------------------------------
# Safety dimensions
# ---------------------------------------------------------------------------


def compute_safety_dimensions(
    *,
    validation_report: TextEvidenceValidationReport | None = None,
    invariant_failures: int = 0,
    stale_artifacts: int = 0,
    source_integrity: bool = True,
) -> QualitySafetyDimensionsV1:
    """Compute the safety dimensions of a quality state.

    Parameters
    ----------
    validation_report
        The final text evidence validation report.  When provided,
        ``unsupported_positive_claims`` is the count of unsupported
        atomic claims in the report.  When ``None``, defaults to zero.
    invariant_failures
        The number of invariant audit failures recorded for the run.
    stale_artifacts
        The number of stale artifacts detected by ``artifact_freshness``.
    source_integrity
        ``False`` when any source-integrity violation was detected
        (e.g. a hint was promoted to a positive claim).  Defaults to
        ``True``.
    """

    unsupported = (
        validation_report.unsupported_claims
        if validation_report is not None
        else 0
    )
    return QualitySafetyDimensionsV1(
        source_integrity=source_integrity,
        unsupported_positive_claims=unsupported,
        stale_artifacts=stale_artifacts,
        invariant_failures=invariant_failures,
    )


# ---------------------------------------------------------------------------
# Content dimensions
# ---------------------------------------------------------------------------


def compute_content_dimensions(
    *,
    coverage_report: ObligationCoverageReportV2 | None = None,
    claim_set: AtomicClaimSetV3 | None = None,
    validation_report: TextEvidenceValidationReport | None = None,
) -> QualityContentDimensionsV1:
    """Compute the content dimensions of a quality state.

    - ``terminal_must_cover``: ``must_cover`` obligations with a terminal
      coverage status (``supported``, ``partial``, ``explicit_gap``,
      ``blocked``).
    - ``supported_must_cover``: ``must_cover`` obligations with status
      ``supported`` ONLY (explicit gaps never count as supported).
    - ``unique_supported_claims``: distinct ``AtomicClaimV3`` instances
      with status ``supported`` (counted by ``canonical_identity`` so
      duplicate claim texts only count once).
    - ``validated_final_sentences``: ``supported`` + ``caveated`` claims
      in the final text validation report.
    - ``unresolved_high_value_obligations``: ``must_cover`` obligations
      that are NOT terminal (i.e. still ``unresolved``).
    """

    terminal_must_cover = 0
    supported_must_cover = 0
    unresolved_high_value = 0
    if coverage_report is not None:
        for item in coverage_report.items:
            if item.obligation_priority != "must_cover":
                continue
            if item.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}:
                terminal_must_cover += 1
            if item.coverage_status == "supported":
                supported_must_cover += 1
            if item.coverage_status == "unresolved":
                unresolved_high_value += 1

    unique_supported_claims = 0
    if claim_set is not None:
        unique_identities = {
            claim.canonical_identity
            for claim in claim_set.claims
            if claim.status == "supported"
        }
        unique_supported_claims = len(unique_identities)

    validated_final_sentences = 0
    if validation_report is not None:
        validated_final_sentences = (
            validation_report.supported_claims
            + validation_report.caveated_claims
        )

    return QualityContentDimensionsV1(
        terminal_must_cover=terminal_must_cover,
        supported_must_cover=supported_must_cover,
        unique_supported_claims=unique_supported_claims,
        validated_final_sentences=validated_final_sentences,
        unresolved_high_value_obligations=unresolved_high_value,
    )


# ---------------------------------------------------------------------------
# Minimality dimensions
# ---------------------------------------------------------------------------


def compute_minimality_dimensions(
    *,
    claim_set: AtomicClaimSetV3 | None = None,
    validation_report: TextEvidenceValidationReport | None = None,
    unresolved_relations: int = 0,
    max_direct_evidence_for_fan_in: int = _MAX_DIRECT_EVIDENCE_FOR_FAN_IN,
) -> QualityMinimalityDimensionsV1:
    """Compute the minimality dimensions of a quality state.

    - ``duplicate_claims``: atomic claims that share the same
      ``canonical_identity`` with at least one other claim in the same
      set.  Each duplicate occurrence beyond the first is counted.
    - ``unjustified_fan_in``: claims whose ``direct_evidence_ids`` list
      has more than ``max_direct_evidence_for_fan_in`` entries.
    - ``unresolved_relations``: relation evidence that was requested but
      not resolved (passed through from the caller).
    """

    duplicate_claims = 0
    unjustified_fan_in = 0
    if claim_set is not None:
        identity_counts: Counter[str] = Counter(
            claim.canonical_identity for claim in claim_set.claims
        )
        # Each identity that appears N times contributes (N - 1) duplicates.
        duplicate_claims = sum(count - 1 for count in identity_counts.values() if count > 1)
        for claim in claim_set.claims:
            if len(claim.direct_evidence_ids) > max_direct_evidence_for_fan_in:
                unjustified_fan_in += 1

    # Also count fan-in from the final text verdicts when available, so a
    # claim that gained extra spans during authoring is still flagged.
    if validation_report is not None:
        seen_claim_ids: set[str] = set()
        for verdict in validation_report.verdicts:
            if verdict.atomic_claim_id in seen_claim_ids:
                continue
            seen_claim_ids.add(verdict.atomic_claim_id)
            if len(verdict.direct_evidence_ids) > max_direct_evidence_for_fan_in:
                # Only count if not already counted from the claim set.
                if claim_set is None or not any(
                    claim.claim_id == verdict.atomic_claim_id
                    and len(claim.direct_evidence_ids) > max_direct_evidence_for_fan_in
                    for claim in claim_set.claims
                ):
                    unjustified_fan_in += 1

    return QualityMinimalityDimensionsV1(
        duplicate_claims=duplicate_claims,
        unjustified_fan_in=unjustified_fan_in,
        unresolved_relations=unresolved_relations,
    )


# ---------------------------------------------------------------------------
# Cost dimensions
# ---------------------------------------------------------------------------


def compute_cost_dimensions(
    *,
    model_calls: int = 0,
    tool_calls: int = 0,
    repeated_no_gain_calls: int = 0,
) -> QualityCostDimensionsV1:
    """Compute the cost dimensions of a quality state.

    Cost dimensions are tracked but never override safety/content.  The
    caller is responsible for incrementing these counters from the run's
    tool/model call ledger.
    """

    return QualityCostDimensionsV1(
        model_calls=model_calls,
        tool_calls=tool_calls,
        repeated_no_gain_calls=repeated_no_gain_calls,
    )


# ---------------------------------------------------------------------------
# Top-level compute_quality_state
# ---------------------------------------------------------------------------


def compute_quality_state(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    coverage_report: ObligationCoverageReportV2 | None = None,
    claim_set: AtomicClaimSetV3 | None = None,
    validation_report: TextEvidenceValidationReport | None = None,
    invariant_failures: int = 0,
    stale_artifacts: int = 0,
    source_integrity: bool = True,
    unresolved_relations: int = 0,
    model_calls: int = 0,
    tool_calls: int = 0,
    repeated_no_gain_calls: int = 0,
) -> QualityStateV2:
    """Compute a ``QualityStateV2`` from a run's artifacts.

    This is the main entry point for the R6.3 quality state computation.
    The supervisor calls this after each repair turn to decide whether
    the new state dominates the incumbent best state via
    ``quality_state_dominates``.
    """

    safety = compute_safety_dimensions(
        validation_report=validation_report,
        invariant_failures=invariant_failures,
        stale_artifacts=stale_artifacts,
        source_integrity=source_integrity,
    )
    content = compute_content_dimensions(
        coverage_report=coverage_report,
        claim_set=claim_set,
        validation_report=validation_report,
    )
    minimality = compute_minimality_dimensions(
        claim_set=claim_set,
        validation_report=validation_report,
        unresolved_relations=unresolved_relations,
    )
    cost = compute_cost_dimensions(
        model_calls=model_calls,
        tool_calls=tool_calls,
        repeated_no_gain_calls=repeated_no_gain_calls,
    )
    state_id = _stable_state_id(run_id, repo_snapshot_id, project_tree_hash, safety, content)
    return QualityStateV2(
        state_id=state_id,
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        safety=safety,
        content=content,
        minimality=minimality,
        cost=cost,
    )


# ---------------------------------------------------------------------------
# Best-state retention
# ---------------------------------------------------------------------------


def select_best_state(
    candidate: QualityStateV2,
    incumbent: QualityStateV2,
) -> tuple[QualityStateV2, bool]:
    """Return ``(best_state, replaced)`` after applying the Pareto rule.

    When ``candidate`` dominates ``incumbent`` (via
    ``quality_state_dominates``), the candidate becomes the new best
    state and ``replaced`` is ``True``.  Otherwise the incumbent is
    retained and ``replaced`` is ``False``.

    The supervisor uses this to implement best-state retention: a repair
    turn that regresses quality never overwrites the best artifacts.
    """

    from code2paper.agentic.research_models import quality_state_dominates

    if quality_state_dominates(candidate, incumbent):
        return candidate, True
    return incumbent, False


def is_trusted_success(state: QualityStateV2) -> bool:
    """A state is a trusted success when it is trusted AND has no unresolved must-cover.

    This is the R6.3 ``final unsupported rate must be 0`` exit condition:
    a run may terminate as ``trusted_success`` only when:

    - ``state.is_trusted`` (no unsupported positive claims, source
      integrity intact, no invariant failures), AND
    - ``state.content.unresolved_high_value_obligations == 0`` (every
      must_cover obligation is terminal).
    """

    return state.is_trusted and state.content.unresolved_high_value_obligations == 0


def is_incomplete(state: QualityStateV2) -> bool:
    """A state is incomplete when it is trusted but has unresolved must-cover.

    This is the R6.3 ``incomplete Method 可以安全输出为 incomplete`` exit
    condition: a run that cannot reach ``is_trusted_success`` but can
    reach a trusted state with some unresolved must-cover may terminate
    as ``incomplete``, emitting the unresolved obligations as explicit
    gaps rather than fabricating evidence.
    """

    return state.is_trusted and state.content.unresolved_high_value_obligations > 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_state_id(
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    safety: QualitySafetyDimensionsV1,
    content: QualityContentDimensionsV1,
) -> str:
    """Build a stable state id from run identity + content footprint.

    Two states from the same run with the same content footprint share
    an id so the supervisor can detect no-op repair turns.
    """

    import hashlib
    payload = "|".join([
        run_id,
        repo_snapshot_id,
        project_tree_hash,
        f"s={safety.source_integrity},{safety.unsupported_positive_claims},{safety.stale_artifacts},{safety.invariant_failures}",
        f"c={content.terminal_must_cover},{content.supported_must_cover},{content.unique_supported_claims},{content.validated_final_sentences},{content.unresolved_high_value_obligations}",
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"qs-{digest}"


__all__ = [
    "compute_safety_dimensions",
    "compute_content_dimensions",
    "compute_minimality_dimensions",
    "compute_cost_dimensions",
    "compute_quality_state",
    "select_best_state",
    "is_trusted_success",
    "is_incomplete",
]
