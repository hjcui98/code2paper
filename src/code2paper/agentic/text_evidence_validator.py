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
from code2paper.agentic.evidence_compiler_v3 import EvidencePacketSetV3
from code2paper.agentic.tool_runtime import atomic_write_bytes
from code2paper.agentic.semantic_evidence import concepts_semantically_related
from code2paper.core.schemas import RawEvidencePack, SourceType


SemanticVerifier = Callable[[dict[str, Any]], Mapping[str, Any] | None]
_STRONG_WORDS = {
    "not", "never", "without", "always",
    "guarantee", "guarantees", "ensure", "ensures", "cause", "causes",
    "enable", "enables", "outperform", "outperforms", "improve", "improves",
    "faster", "better", "robust", "novel",
}

# A comparison is an exact ``identifier operator value`` unit.  The
# identifier and the value carry word boundaries so an authorized
# ``discount > 0`` can never authorize ``count > 0`` (variable-suffix
# collision) and an authorized ``count > 10`` can never authorize
# ``count > 1`` (value-prefix collision).  The identifier grammar accepts
# dotted attributes, bracket-indexed operands (``tensor.shape[0]``,
# ``counts[i]``), and call suffixes so an authorized indexed threshold such
# as ``tensor.shape[0] > 1`` is verified as a complete unit instead of
# degrading to loose numeric membership.  Operators are the closed
# comparison set; signed and scientific thresholds are parsed as part of
# the value so ``count > -1``, ``count > 1``, and ``count > 1e5`` are
# distinct units and an operator-only mutation cannot ride on a substring.
_COMPARISON_UNIT = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\[\]]*\]|\([^)]*\))*)"
    r"\s*((?:>=|<=|!=|==|>|<))\s*"
    r"([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?%?)"
    r"(?![A-Za-z0-9_])"
)
# A loose comparison-shaped ``operator value`` scanner used only to prove
# coverage: every operator+value occurrence in the claim must be covered by
# an exact parsed unit, otherwise the expression has a comparison shape the
# parser cannot represent and the gate must fail closed instead of
# downgrading to standalone numeric membership.
_COMPARISON_SHAPE = re.compile(
    r"((?:>=|<=|!=|==|>|<))\s*"
    r"([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?%?)"
    r"(?![A-Za-z0-9_])"
)

_FORMULA_IDENTIFIER = (
    r"[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[^\[\]]*\]|\([^)]*\))*"
)
_FORMULA_EXPRESSION = re.compile(
    r"\$(?P<math>[^$]+)\$|"
    r"(?<![A-Za-z0-9_])(?P<comparison>"
    + _FORMULA_IDENTIFIER
    + r"\s*==\s*[^,.;]+)|"
    r"(?<![A-Za-z0-9_])(?P<assignment>"
    + _FORMULA_IDENTIFIER
    + r"\s+=\s+(?![\[\"'])[^,.;]+)"
)


def _comparison_units(text: str) -> set[tuple[str, str, str]]:
    """Parse every comparison expression in ``text`` into exact normalized
    ``(identifier, operator, value)`` units.

    The identifier is whitespace-normalized so ``len (x) > 0`` and
    ``len(x) > 0`` are the same unit; the operator and value are kept
    verbatim (``>=`` differs from ``>``, ``-1`` differs from ``1``, and
    ``1e5`` differs from ``1``).
    """

    units: set[tuple[str, str, str]] = set()
    for identifier, operator, value in _COMPARISON_UNIT.findall(text):
        units.add((re.sub(r"\s+", "", identifier), operator, value))
    return units


def validate_text_evidence(
    *,
    final_claims: FinalTextClaims,
    projection: AuthoringInputProjection,
    raw_evidence: RawEvidencePack,
    evidence_snapshot_v2: EvidenceSnapshotV2 | None = None,
    evidence_packets_v3: EvidencePacketSetV3 | None = None,
    semantic_verifier: SemanticVerifier | None = None,
    max_semantic_verifier_calls: int = 0,
    require_semantic_verifier: bool | None = None,
    proposition_claim_ids: Mapping[str, list[str] | tuple[str, ...]] | None = None,
    candidate_only_proposition_ids: set[str] | None = None,
    evidence_entailed_proposition_ids: set[str] | None = None,
) -> TextEvidenceValidationReport:
    evidence_by_id = {item.evidence_id: item for item in raw_evidence.evidence_items}
    v2_by_id = {
        span.evidence_id: span
        for span in (evidence_snapshot_v2.spans if evidence_snapshot_v2 else [])
        if is_direct_code_span(span)
    }
    v3_by_id = {
        span.span_id: span
        for packet in (evidence_packets_v3.packets if evidence_packets_v3 else [])
        for span in packet.spans
    }
    v3_relation_by_id = {
        relation.relation_id: relation
        for packet in (evidence_packets_v3.packets if evidence_packets_v3 else [])
        for relation in packet.relations
    }
    projection_by_id = {claim.claim_id: claim for claim in projection.projected_claims}
    author_attested_by_id = {
        fragment.fragment_id: fragment
        for fragment in projection.author_attested_fragments
    }
    candidate_narrative_by_id = {
        str(item.get("point_id") or ""): item
        for values in (
            projection.author_intent_unverified_points,
            projection.repository_mismatches,
            projection.external_pending_points,
            projection.formalization_needed_points,
        )
        for item in values
        if isinstance(item, dict) and str(item.get("point_id") or "")
    }
    # Qualifier preservation is a sentence-level property: a conditional prefix
    # such as "When self.time_mamba is active and dts is not None, ... computes
    # rearrange(...)" scopes the whole sentence.  The atomic-fragment splitter
    # breaks that sentence on the comma, detaching the qualifier from the
    # formula fragment.  The qualifier check therefore consults the full unit
    # (sentence) text; the fragment-level text remains authoritative for
    # projection matching, wording strength, and numeric/formula token checks.
    unit_text_by_id = {unit.unit_id: unit.text for unit in final_claims.units}
    verdicts: list[TextClaimEvidenceVerdict] = []
    verifier_calls = 0
    proposition_claim_ids = proposition_claim_ids or {}
    candidate_only_proposition_ids = candidate_only_proposition_ids or set()
    for claim in final_claims.atomic_claims:
        proposition_backed = bool(
            claim.candidate_method_proposition_ids
            if evidence_entailed_proposition_ids is None
            else set(claim.candidate_method_proposition_ids)
            & evidence_entailed_proposition_ids
        )
        projection_ids = _dedupe([
            *claim.candidate_projection_claim_ids,
            *(
                claim_id
                for proposition_id in claim.candidate_method_proposition_ids
                for claim_id in proposition_claim_ids.get(proposition_id, ())
            ),
        ])
        matches = [projection_by_id[item] for item in projection_ids if item in projection_by_id]
        author_matches = [
            author_attested_by_id[item]
            for item in claim.candidate_author_attested_ids
            if item in author_attested_by_id
        ]
        candidate_narrative_matches = [
            candidate_narrative_by_id[item]
            for item in claim.candidate_narrative_ids
            if item in candidate_narrative_by_id
        ]
        matched_candidate_propositions = sorted(
            set(claim.candidate_method_proposition_ids)
            & candidate_only_proposition_ids
        )
        # Author-owned statements are a separate lane.  They may be emitted
        # as caveated prose only when the final fragment is a close match to
        # the validated callback/MethodEvidence wording; they never receive
        # repository evidence ids or satisfy a repository claim by accident.
        if not matches and author_matches:
            verdicts.append(TextClaimEvidenceVerdict(
                atomic_claim_id=claim.atomic_claim_id,
                status="caveated",
                matched_projection_claim_ids=[item.fragment_id for item in author_matches],
                matched_method_proposition_ids=claim.candidate_method_proposition_ids,
                supported_fragment=claim.text,
                rationale="Author-attested fragment matched; not repository evidence.",
                repair_action="",
            ))
            continue
        if not matches and candidate_narrative_matches:
            point_ids = [
                str(item.get("point_id") or "")
                for item in candidate_narrative_matches
            ]
            verdicts.append(TextClaimEvidenceVerdict(
                atomic_claim_id=claim.atomic_claim_id,
                status="caveated",
                matched_projection_claim_ids=point_ids,
                matched_method_proposition_ids=claim.candidate_method_proposition_ids,
                supported_fragment=claim.text,
                rationale=(
                    "Typed candidate narrative matched with explicit author/"
                    "partial/pending framing; not repository evidence."
                ),
                repair_action="",
            ))
            continue
        if not matches and matched_candidate_propositions:
            # The closed-set aligner has already checked semantic roles,
            # immutable constraints, authority expansion and the visible
            # epistemic caveat.  This author/partial proposition therefore
            # authorizes candidate prose only; it supplies no repository IDs
            # and can never enter the verified document.
            verdicts.append(TextClaimEvidenceVerdict(
                atomic_claim_id=claim.atomic_claim_id,
                status="caveated",
                matched_projection_claim_ids=[],
                matched_method_proposition_ids=matched_candidate_propositions,
                supported_fragment=claim.text,
                rationale=(
                    "Closed candidate-only Method proposition matched with "
                    "its required caveat; not repository evidence."
                ),
                repair_action="",
            ))
            continue
        licensed_matches = [
            item for item in projection.projected_claims
            if str(getattr(item, "inference_level", "E0") or "E0") in {"E2", "E3"}
            and list(getattr(item, "parent_claim_ids", ()) or ())
            and _projection_overlap_sufficient(claim.text, [item])
        ]
        failures: list[str] = []
        candidate_licensed = False
        if licensed_matches and (
            not matches or not _projection_overlap_sufficient(claim.text, matches)
        ):
            matches = licensed_matches
            candidate_licensed = True
        elif not matches:
            failures.append("no_semantically_matching_projected_claim")
        direct_ids = _dedupe([evidence_id for item in matches for evidence_id in item.direct_evidence_ids])
        relation_ids = _dedupe([evidence_id for item in matches for evidence_id in item.relation_evidence_ids])
        relation_span_ids = _dedupe([
            span_id
            for relation_id in relation_ids
            for span_id in (v3_relation_by_id[relation_id].direct_span_ids if relation_id in v3_relation_by_id else [])
        ])
        known_exact = {**v2_by_id, **v3_by_id}
        missing_ids = [
            item for item in direct_ids
            if item not in (known_exact if (evidence_snapshot_v2 is not None or evidence_packets_v3 is not None) else evidence_by_id)
        ]
        if missing_ids or (not direct_ids and not candidate_licensed):
            failures.append("direct_evidence_missing")
        if evidence_snapshot_v2 is not None or evidence_packets_v3 is not None:
            evidence_text = "\n".join(
                known_exact[item].exact_excerpt
                for item in _dedupe([*direct_ids, *relation_span_ids])
                if item in known_exact
            )
        else:
            evidence_text = "\n".join(
                _evidence_text(evidence_by_id[item], project_root=raw_evidence.project_root)
                for item in direct_ids
                if item in evidence_by_id and is_direct_code_path(evidence_by_id[item].path)
            )
        if matches:
            # Separate the two failure classes that the combined relevance
            # check collapsed: a fragment whose wording drifted below the
            # projection overlap is a Writer-wording failure (route to
            # ``revise_authoring_wording``); only a fragment whose matched
            # evidence genuinely cannot support it routes to the packet
            # binding owner.
            if (
                not candidate_licensed
                and not proposition_backed
                and not _projection_overlap_sufficient(claim.text, matches)
            ):
                failures.append("no_semantically_matching_projected_claim")
            if (
                not candidate_licensed
                and not proposition_backed
                and evidence_text
                and not _evidence_related(claim.text, evidence_text)
            ):
                failures.append("direct_evidence_semantically_unrelated")
        required_qualifiers = _dedupe([qualifier for item in matches for qualifier in item.required_qualifiers])
        if _comparison_polarity_flipped(claim.text, matches):
            failures.append("comparison_polarity_flipped")
        if required_qualifiers and not _qualifier_preserved(
            unit_text_by_id.get(claim.unit_id, claim.text), required_qualifiers
        ):
            failures.append("required_qualifier_missing")
        if (
            _wording_strength_exceeded(claim.text, matches)
            and not _licensed_effect_match(claim.text, matches)
        ):
            failures.append("allowed_wording_boundary_exceeded")
        # Authorized projection fragments and wording boundaries carry the
        # exact code expressions (e.g. ``dim=1``, ``node_memories[torch...]``)
        # that the Writer was told to copy.  These are not free-form numeric
        # or formula claims — they are pre-authorized wording, so they should
        # be treated as an allowed source alongside direct evidence.
        authorized_wording = " ".join(
            str(item.supported_fragment) for item in matches
        ) + " " + " ".join(str(item.allowed_wording_boundary) for item in matches)
        # When direct evidence ids exist but the excerpt is empty (a D1
        # evidence extraction gap), the claim cannot be verified against
        # repository code.  This is an explicit failure: relying on other
        # gates to indirectly block it lets a claim with an empty evidence
        # excerpt slip through when no other failure fires.  Fail closed
        # here so the gap is visible and must be repaired at the evidence
        # layer.
        _evidence_excerpt_empty = (
            bool(direct_ids) and not evidence_text.strip() and not candidate_licensed
        )
        if _evidence_excerpt_empty:
            failures.append("direct_evidence_excerpt_empty")
        if (
            "number" in claim.high_risk_markers
            and not _evidence_excerpt_empty
            and not _numeric_tokens_supported(claim.text, evidence_text, projection, required_qualifiers, authorized_wording)
        ):
            failures.append("numeric_token_not_in_direct_evidence")
        if (
            "formula" in claim.high_risk_markers
            and not _evidence_excerpt_empty
            and not _formula_tokens_supported(claim.text, evidence_text, projection, required_qualifiers, authorized_wording)
        ):
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
        if candidate_licensed and not failures:
            status = "caveated"
        else:
            status = "unsupported" if failures else ("caveated" if partial else "supported")
        verdicts.append(
            TextClaimEvidenceVerdict(
                atomic_claim_id=claim.atomic_claim_id,
                status=status,
                matched_projection_claim_ids=[item.claim_id for item in matches],
                matched_method_proposition_ids=claim.candidate_method_proposition_ids,
                direct_evidence_ids=direct_ids,
                relation_evidence_ids=relation_ids,
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
        verification_mode="semantic" if verifier_calls > 0 else "lexical_only",
        verdicts=verdicts,
        recommended_actions=actions,
    )


def _drop_heading_only_verified_sections(text: str) -> str:
    """Omit sections that contain only a heading after sentence filtering."""

    blocks = re.split(r"(?m)(?=^#{1,6}\s+)", text)
    kept: list[str] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        lines = [line for line in stripped.splitlines() if line.strip()]
        if lines and lines[0].lstrip().startswith("#") and len(lines) == 1:
            continue
        kept.append(stripped)
    return "\n\n".join(kept)


def _normalize_scaffolding_heading(text: str) -> str:
    """Normalize a heading for exact comparison with the Architect's plan.

    Strips markdown ``#`` markers and collapses inner whitespace so a
    writer-copied heading matches its plan heading regardless of leading
    hash count or spacing.
    """

    value = str(text or "").strip().lstrip("#").strip()
    return " ".join(value.split()).casefold()


def _unit_has_factual_payload(unit: Any) -> bool:
    """Fail-closed scaffolding guard: does a non-factual unit carry facts?

    A heading/discourse unit is claim-free scaffolding only when it is
    structurally minimal.  Any of these makes it factual payload that must
    be reverse-validated (and excluded from verified until supported):

    - the extractor flagged high-risk markers (numbers, formulas,
      causal/performance/complexity vocabulary) on the unit;
    - the text carries epistemic markers (author-intent / unverified /
      pending / review language) — such prose is caveated material at best;
    - the text contains two or more sentence-final periods, i.e. the unit
      is really a fused paragraph, not a heading;
    - the unit is implausibly long for a heading (beyond a short label).
    """

    text = str(getattr(unit, "text", "") or "").strip()
    if not text:
        return False
    if getattr(unit, "high_risk_markers", ()) or ():
        return True
    lowered = text.casefold()
    if any(marker in lowered for marker in _EPISTEMIC_MARKERS):
        return True
    # Two or more terminal periods means the unit holds multiple sentences.
    if len(re.findall(r"[.!?](?:\s|$)", text)) >= 2:
        return True
    return len(text.split()) > 14


_EPISTEMIC_MARKERS = (
    "author-intended", "author intended", "author-attested", "author attested",
    "unverified", "not verified", "pending confirmation", "pending",
    "our intended", "we aim", "remains intended", "intended design",
    "requires confirmation", "not yet implemented", "to be confirmed",
    "await", "awaiting",
)


def _verdict_is_repository_supported(
    verdict: TextClaimEvidenceVerdict,
    *,
    projection_claim_ids: set[str],
    include_partial: bool,
) -> bool:
    """Whether one claim verdict may enter the repository-verified document.

    ``supported`` verdicts always qualify.  ``caveated`` verdicts qualify
    only when the caveat is a *partial repository support* (the matched ids
    are projection claim ids) AND the caller permits partial lanes; a
    caveat whose matched ids are author-attested fragment ids is
    author-intent material and never enters verified.
    """

    if verdict.status == "supported":
        if not verdict.matched_projection_claim_ids:
            return True
        return any(str(item) in projection_claim_ids for item in verdict.matched_projection_claim_ids)
    if verdict.status != "caveated" or not include_partial:
        return False
    return any(
        str(item) in projection_claim_ids
        for item in verdict.matched_projection_claim_ids
    )


def build_repository_verified_text(
    *,
    final_text: str,
    final_claims: FinalTextClaims,
    validation_report: TextEvidenceValidationReport,
    projection: AuthoringInputProjection,
    include_partial: bool = True,
    expected_headings: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build the repository-verified document from a candidate text (G2).

    Sentence-level, fail-closed filtering:

    - non-factual units (headings, discourse, expository bridges) are kept as
      structural scaffolding — they carry no implementation facts;
    - factual units are kept only when *every* atomic claim in the unit
      qualifies for verified inclusion (``supported``, or qualifier-guarded
      partial when ``include_partial``);
    - author-attested caveats, mismatches, review questions, literature/
      formalization pending content, and unsupported positives are excluded
      from verified and reported for review linking.

    The text is reconstructed from the original source offsets so headings,
    blank lines and markdown layout survive.  ``unsupported_positive`` spans
    are never rewritten or invented.
    """

    projection_claim_ids = {
        claim.claim_id
        for claim in projection.projected_claims
        if str(getattr(claim, "inference_level", "E0") or "E0") in {"E0", "E1", ""}
    }
    verdict_by_id = {item.atomic_claim_id: item for item in validation_report.verdicts}
    claim_ids_by_unit: dict[str, list[str]] = {}
    for claim in final_claims.atomic_claims:
        claim_ids_by_unit.setdefault(claim.unit_id, []).append(claim.atomic_claim_id)

    keep_unit: dict[str, bool] = {}
    excluded_reasons: list[dict[str, Any]] = []
    normalized_expected = {
        _normalize_scaffolding_heading(str(heading))
        for heading in (expected_headings or ())
    }
    for unit in final_claims.units:
        if not unit.factual or unit.kind in {
            "heading", "discourse", "expository_bridge", "caption",
        }:
            # Scaffolding exemption is fail-closed: a heading/discourse unit
            # is kept only when it is the Architect's own heading or carries
            # no factual payload.  A fused ``## HeadingBody...`` paragraph
            # that escaped heading normalization must not ride into verified
            # as "structure" — its sentences are factual content and need
            # verdicts.
            if _unit_has_factual_payload(unit) and not (
                unit.kind == "heading"
                and _normalize_scaffolding_heading(unit.text) in normalized_expected
            ):
                keep_unit[unit.unit_id] = False
                excluded_reasons.append({
                    "unit_id": unit.unit_id,
                    "text": unit.text,
                    "char_start": unit.char_start,
                    "char_end": unit.char_end,
                    "reason": "scaffolding_unit_with_factual_payload",
                })
                continue
            keep_unit[unit.unit_id] = True
            continue
        claim_ids = claim_ids_by_unit.get(unit.unit_id, [])
        if not claim_ids:
            keep_unit[unit.unit_id] = False
            excluded_reasons.append({
                "unit_id": unit.unit_id,
                "text": unit.text,
                "char_start": unit.char_start,
                "char_end": unit.char_end,
                "reason": "factual_unit_without_extracted_claim",
            })
            continue
        verdicts = [verdict_by_id[claim_id] for claim_id in claim_ids if claim_id in verdict_by_id]
        missing_verdicts = [claim_id for claim_id in claim_ids if claim_id not in verdict_by_id]
        if missing_verdicts:
            keep_unit[unit.unit_id] = False
            excluded_reasons.append({
                "unit_id": unit.unit_id,
                "text": unit.text,
                "char_start": unit.char_start,
                "char_end": unit.char_end,
                "reason": "missing_claim_verdict:" + ",".join(sorted(missing_verdicts)),
            })
            continue
        if all(
            _verdict_is_repository_supported(
                verdict,
                projection_claim_ids=projection_claim_ids,
                include_partial=include_partial,
            )
            for verdict in verdicts
        ):
            keep_unit[unit.unit_id] = True
            continue
        excluded_reasons.append({
            "unit_id": unit.unit_id,
            "text": unit.text,
            "char_start": unit.char_start,
            "char_end": unit.char_end,
            "reason": ";".join(sorted({
                verdict.status
                for verdict in verdicts
                if not _verdict_is_repository_supported(
                    verdict,
                    projection_claim_ids=projection_claim_ids,
                    include_partial=include_partial,
                )
            })),
        })
        keep_unit[unit.unit_id] = False

    ordered = sorted(final_claims.units, key=lambda item: item.char_start)
    parts: list[str] = []
    cursor = 0
    for unit in ordered:
        start = max(cursor, unit.char_start)
        end = min(len(final_text), unit.char_end)
        if end <= start:
            continue
        if keep_unit.get(unit.unit_id, False):
            parts.append(final_text[cursor:end])
        else:
            # Keep the interstitial whitespace only (no replaced content).
            parts.append(final_text[cursor:start])
        cursor = end
    parts.append(final_text[cursor:])
    verified_text = "".join(parts)
    # Rejoining on blank lines keeps markdown layout canonical.
    verified_text = re.sub(r"\n{3,}", "\n\n", verified_text)
    verified_text = re.sub(r"[ \t]{2,}", " ", verified_text)
    verified_text = _drop_heading_only_verified_sections(verified_text).strip()
    excluded_unsupported = [
        item for item in excluded_reasons
        if not keep_unit.get(item["unit_id"], False)
    ]
    report = {
        "split_mode": "sentence_reverse_validation",
        "verified_unit_ids": [item.unit_id for item in ordered if keep_unit.get(item.unit_id, False)],
        "excluded_units": excluded_unsupported,
        "verified_positive_unit_count": sum(
            keep_unit.get(item.unit_id, False)
            and item.kind not in {"heading", "discourse", "expository_bridge", "caption"}
            for item in ordered
        ),
        "unsupported_positive_units": len(excluded_unsupported),
    }
    return verified_text, report


def write_text_evidence_validation(path: str | Path, report: TextEvidenceValidationReport) -> Path:
    output = Path(path)
    payload = (
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    return atomic_write_bytes(output, payload)


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


def _projection_overlap_sufficient(text: str, matches: list[Any]) -> bool:
    """Whether the final fragment still overlaps its matched projections.

    A fragment whose wording drifted too far from the projection is a
    Writer-wording failure, NOT an evidence-binding defect.  Separating the
    two lets ``direct_evidence_semantically_unrelated`` route to the packet
    owner only when the evidence itself genuinely cannot support the
    fragment.
    """

    claim_tokens = _tokens(text)
    projection_tokens = (
        set().union(*(_tokens(item.supported_fragment) for item in matches))
        if matches
        else set()
    )
    if not projection_tokens:
        return False
    overlap = len(claim_tokens & projection_tokens)
    threshold = 0.20 if any(
        str(getattr(item, "inference_level", "E0") or "E0") in {"E2", "E3"}
        for item in matches
    ) else 0.45
    return overlap / max(1, min(len(claim_tokens), len(projection_tokens))) >= threshold


def _licensed_effect_match(text: str, matches: list[Any]) -> bool:
    return any(
        str(getattr(item, "inference_level", "E0") or "E0") in {"E2", "E3"}
        for item in matches
    ) and _projection_overlap_sufficient(text, matches)


def _comparison_polarity_flipped(text: str, matches: list[Any]) -> bool:
    licensed = " ".join(str(item.supported_fragment) for item in matches).casefold()
    if "exclud" not in licensed and "fails the threshold" not in licensed:
        return False
    folded = str(text or "").casefold()
    return bool(re.search(r"(eligib|retain|keep|only if).{0,48}<\s", folded))


def _evidence_related(text: str, evidence_text: str) -> bool:
    claim_tokens = _tokens(text)
    evidence_tokens = _tokens(evidence_text)
    overlap = len(claim_tokens & evidence_tokens)
    return (
        overlap / max(1, min(len(claim_tokens), len(evidence_tokens))) >= 0.12
        or overlap >= 2
        or concepts_semantically_related(text, evidence_text)
    )


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
    allowed_words = set().union(*(
        _tokens(
            str(item.supported_fragment)
            + " "
            + str(item.allowed_wording_boundary)
        )
        for item in matches
    )) if matches else set()
    return bool(text_words - allowed_words)


def _numeric_tokens_supported(
    text: str,
    evidence_text: str,
    projection: AuthoringInputProjection,
    required_qualifiers: list[str] | None = None,
    authorized_wording: str = "",
) -> bool:
    # Remove symbol references (e.g. sym:75d56395dcbb01a3) so hash digits
    # inside symbol identifiers are not mistaken for numeric claims that
    # require evidence support.
    cleaned = re.sub(r"sym:[0-9a-fA-F]+", "", text)
    # Remove mathematical interval notation like (0,1) or [0,1] which
    # describe output ranges implied by activation functions (e.g. Sigmoid
    # → (0,1), Tanh → (-1,1)).  These are mathematical properties of the
    # function, not standalone numeric claims that require literal code
    # evidence.
    cleaned = re.sub(r"[\[\(]\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*[\]\)]", "", cleaned)
    # Remove numbers that are part of sequential labels (e.g. ``stage 1``,
    # ``step 2``, ``phase 3``, ``layer 1``).  These are ordinal labels, not
    # standalone numeric claims that require evidence support.
    cleaned = re.sub(r"\b(?:stage|step|phase|layer|level|part|chapter|section)\s+\d+\b", "", cleaned, flags=re.I)

    qualifier_text = " ".join(required_qualifiers or [])
    allowed = (
        evidence_text
        + " "
        + json.dumps(projection.safe_numeric_facts, ensure_ascii=False)
        + " "
        + qualifier_text
        + " "
        + authorized_wording
    )

    # Comparison expressions (``count > 0``, ``len(x) != 0``,
    # ``entity_occurrences >= 1``, ``tensor.shape[0] > 1``) are conditional
    # thresholds.  They must be verified as an exact
    # ``identifier + operator + threshold`` unit against the authorized
    # sources.  A threshold digit can never be dropped or matched as a
    # substring: an authorized ``count > 0`` must not authorize
    # ``count > 999``, ``discount > 0`` must not authorize ``count > 0``,
    # and ``count > 10`` must not authorize ``count > 1``.
    claim_units = _comparison_units(cleaned)
    allowed_units = _comparison_units(allowed)
    if not claim_units.issubset(allowed_units):
        return False
    # Fail closed for any comparison-shaped ``operator value`` that the exact
    # parser could not represent as an identifier unit.  An authorized
    # ``tensor.shape[0] > 1`` must not let a mutated ``tensor.shape[0] >= 1``
    # fall through to loose standalone numeric membership: an unparseable
    # comparison shape is an unsupported predicate, not a harmless number.
    covered_operator_positions = {
        match.start(2) for match in _COMPARISON_UNIT.finditer(cleaned)
    }
    for shape_match in _COMPARISON_SHAPE.finditer(cleaned):
        operator_position = shape_match.start(1)
        if operator_position not in covered_operator_positions:
            return False
    # All comparisons authorized: remove them so their threshold digits
    # are not re-checked as standalone numeric tokens.
    cleaned = _COMPARISON_UNIT.sub(" ", cleaned)

    # Digits embedded in code identifiers (``get_prune_input_f15``) are not
    # numeric claims.  Require numeric tokens to be delimited from letters
    # and underscores while preserving standalone values such as
    # ``input_dim=15`` and ``dim=1``.
    tokens = set(re.findall(
        r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?%?(?![A-Za-z0-9_])",
        cleaned,
    ))
    return all(token in allowed for token in tokens)


def _formula_tokens_supported(
    text: str,
    evidence_text: str,
    projection: AuthoringInputProjection,
    required_qualifiers: list[str] | None = None,
    authorized_wording: str = "",
) -> bool:
    # Use the same pattern as the risk marker: match ``==`` comparisons and
    # spaced ``=`` formulas, but NOT keyword arguments (``dim=1``) or code
    # patterns (``x = ["..."]``, ``x = "..."``).
    # Markdown code delimiters are presentation, not part of an authorized
    # comparison/formula.  Remove them before exact expression extraction so
    # a backticked qualifier does not become ``current_layer_num==0```.
    formula_text = text.replace("`", "")
    needed = set()
    for match in _FORMULA_EXPRESSION.finditer(formula_text):
        value = next(
            value for value in match.groupdict().values() if value is not None
        )
        normalized = value.replace(" ", "")
        # The value part of a comparison is greedy up to punctuation, so a
        # compact parenthetical binding such as
        # ``(`doc['chunk_id'] == query['chunk_id']`)`` leaves one trailing
        # unbalanced closing paren in the extracted formula.  The required
        # qualifier (the authority) never contains that paren; strip only
        # trailing closers when they are unbalanced, so the parenthetical
        # backtick form of a required qualifier still matches its frozen
        # predicate instead of failing as ``formula_not_in_direct_evidence``.
        if normalized.count(")") > normalized.count("("):
            normalized = normalized.rstrip(")]}")
        needed.add(normalized)
    # Formulas that appear inside authorized qualifiers or authorized
    # projection fragments are already validated by ``_qualifier_preserved``
    # or the projection itself; add them to the allowed source.
    qualifier_text = " ".join(required_qualifiers or [])
    allowed = (evidence_text + json.dumps(projection.safe_equations, ensure_ascii=False) + " " + qualifier_text + " " + authorized_wording).replace(" ", "")
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
    if "direct_evidence_semantically_unrelated" in failures:
        return "return_to_packet_binding_repair"
    if "direct_evidence_missing" in failures:
        return "return_to_analysis_for_direct_evidence"
    if failures:
        return "revise_authoring_wording"
    return ""


def _tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "we", "our", "this", "that", "with", "for"}
    # Split snake_case identifiers into their semantic components.  Treating
    # ``percentile_cutoff_normalize`` as one opaque token caused prose such as
    # “percentile clipping” to be declared unrelated even when the exact
    # relation span contained that function and its clipping implementation.
    # Identifier decomposition remains deterministic and project-agnostic.
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in stop
    }


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))
