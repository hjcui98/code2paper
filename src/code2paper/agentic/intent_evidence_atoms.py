"""Split narrative units into independently judgeable intent evidence atoms."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from code2paper.agentic.intent_spine_models import (
    FieldEvidenceProofV2,
    IntentAtomClosureStatusV1,
    IntentEvidenceAtomV1,
)


_RATIONALE_MARKERS = re.compile(
    r"\b(?:to (?:consolidate|support|enable|improve|inject|reduce)|"
    r"for (?:global|intra[- ]document|cross[- ]passage)|"
    r"in order to|so that|because)\b",
    re.IGNORECASE,
)
_QUANTIFIER_MARKERS = re.compile(
    r"\b(?:every|each|all|any|always|never|some|at least|exactly)\b",
    re.IGNORECASE,
)
_NEGATION_MARKERS = re.compile(
    r"\b(?:not|never|without|cannot|no longer)\b",
    re.IGNORECASE,
)
_CONDITION_MARKERS = re.compile(
    r"\b(?:when|if|unless|where|while|given that)\b",
    re.IGNORECASE,
)
_SCOPE_MARKERS = re.compile(
    r"\b(?:every layer|each layer|in every|in each|all layers)\b",
    re.IGNORECASE,
)


def _stable_id(*parts: str) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return "atom:" + hashlib.sha256(encoded).hexdigest()[:16]


def _text(value: Any) -> str:
    return str(value or "").strip()


def semantic_fields_exceed_quote(
    fields: Mapping[str, Any],
    quote: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Reject semantic fields wider than the exact source quote."""

    quote_text = _text(quote)
    clipped: dict[str, Any] = {}
    violations: list[str] = []
    for key, value in fields.items():
        if isinstance(value, (list, tuple)):
            kept: list[str] = []
            for item in value:
                text = _text(item)
                if text and text in quote_text:
                    kept.append(text)
                elif text:
                    violations.append(f"{key}:exceeds_quote")
            if kept:
                clipped[str(key)] = kept
        else:
            text = _text(value)
            if not text:
                continue
            if text in quote_text:
                clipped[str(key)] = text
            else:
                violations.append(f"{key}:exceeds_quote")
    return clipped, tuple(dict.fromkeys(violations))


def _polarity(text: str) -> str:
    return "negative" if _NEGATION_MARKERS.search(text) else "positive"


def _quantifier(text: str) -> str:
    match = _QUANTIFIER_MARKERS.search(text)
    return match.group(0).casefold() if match else ""


def _condition(text: str) -> str:
    match = _CONDITION_MARKERS.search(text)
    if not match:
        return ""
    return text[match.start():].strip()


def _authority(text: str) -> str:
    if _RATIONALE_MARKERS.search(text) and not _SCOPE_MARKERS.search(text):
        return "author_rationale"
    if _SCOPE_MARKERS.search(text):
        return "repository_compositional"
    return "repository_implementation"


def _candidate_spans(text: str) -> tuple[str, ...]:
    parts = re.split(r"(?<=[.!;])\s+|(?=\b(?:and|while|then)\b\s)", text)
    spans = tuple(part.strip(" \t\r\n,;") for part in parts if part.strip(" \t\r\n,;"))
    return spans or (text.strip(),)


def _preserves_scope(original: str, fragment: str) -> bool:
    for pattern in (_QUANTIFIER_MARKERS, _NEGATION_MARKERS, _CONDITION_MARKERS):
        original_hits = {item.group(0).casefold() for item in pattern.finditer(original)}
        fragment_hits = {item.group(0).casefold() for item in pattern.finditer(fragment)}
        if original_hits and not original_hits.issubset(fragment_hits | {fragment.casefold()}):
            if any(token in fragment.casefold() for token in original_hits):
                continue
            # A fragment that dropped a marker still covers the original if
            # the marker's clause is wholly outside this fragment.  Only fail
            # when the fragment overlaps the marked span and omitted it.
            for match in pattern.finditer(original):
                window = original[max(0, match.start() - 24): match.end() + 24]
                if fragment in window or window in fragment:
                    if match.group(0).casefold() not in fragment.casefold():
                        return False
    return True


def decompose_intent_evidence_atoms(
    *,
    narrative_unit_id: str,
    story_node_id: str = "",
    source_quote: str,
    owner_fields: Mapping[str, Any] | None = None,
    owner_confirmed: bool = False,
) -> tuple[tuple[IntentEvidenceAtomV1, ...], tuple[str, ...]]:
    """Propose independently judgeable atoms without claiming harness repair.

    YAML/narrative units stay intact as ``narrative_unit_id``.  Deterministic
    spans are candidates only; missing quantifier/negation/condition coverage
    keeps the original statement as ``unresolved``.
    """

    quote = _text(source_quote)
    if not quote:
        return (), ("empty_source_quote",)
    fields, field_violations = semantic_fields_exceed_quote(owner_fields or {}, quote)
    diagnostics = list(field_violations)
    fragments = _candidate_spans(quote)
    atoms: list[IntentEvidenceAtomV1] = []
    if field_violations and not owner_confirmed:
        diagnostics.append("semantic_fields_require_bounded_owner_repair")
    for fragment in fragments:
        if not _preserves_scope(quote, fragment) and fragment != quote:
            diagnostics.append("splitter_dropped_quantifier_or_condition")
            continue
        start = quote.find(fragment)
        end = start + len(fragment) if start >= 0 else len(quote)
        authority = _authority(fragment)
        predicate = "states"
        lowered = fragment.casefold()
        if "attention" in lowered:
            predicate = "uses_attention"
        elif "loss" in lowered or "infonce" in lowered:
            predicate = "optimizes"
        elif "rank" in lowered or "dot-product" in lowered or "dot product" in lowered:
            predicate = "scores"
        elif "embedding" in lowered:
            predicate = "encodes"
        atom = IntentEvidenceAtomV1(
            atom_id=_stable_id(narrative_unit_id, story_node_id, fragment),
            narrative_unit_id=narrative_unit_id,
            story_node_id=story_node_id,
            source_quote=fragment,
            source_quote_range=(max(0, start), end),
            subject=fragment.split()[0] if fragment.split() else narrative_unit_id,
            predicate=predicate,
            object_or_operands=(),
            polarity=_polarity(fragment),  # type: ignore[arg-type]
            quantifier=_quantifier(fragment),
            condition=_condition(fragment),
            boundary="",
            authority_expectation=authority,  # type: ignore[arg-type]
            semantic_fields=fields if fragment == quote else {"operation": fragment},
            splitter_candidate=fragment != quote,
            unresolved_reason=(
                "owner_confirmation_required"
                if fragment != quote and not owner_confirmed
                else ("semantic_field_exceeds_quote" if field_violations and fragment == quote else "")
            ),
        )
        atoms.append(atom)
    if not atoms:
        atoms.append(IntentEvidenceAtomV1(
            atom_id=_stable_id(narrative_unit_id, story_node_id, quote, "unresolved"),
            narrative_unit_id=narrative_unit_id,
            story_node_id=story_node_id,
            source_quote=quote,
            source_quote_range=(0, len(quote)),
            subject=quote.split()[0] if quote.split() else narrative_unit_id,
            predicate="states",
            polarity=_polarity(quote),  # type: ignore[arg-type]
            quantifier=_quantifier(quote),
            condition=_condition(quote),
            authority_expectation="repository_implementation",
            semantic_fields=fields,
            unresolved_reason="splitter_did_not_preserve_scope",
        ))
        diagnostics.append("original_statement_retained_unresolved")
    return tuple(atoms), tuple(dict.fromkeys(diagnostics))


def compose_field_evidence_proof(
    *,
    proof_id: str,
    conclusion_atom_id: str,
    span_ids: Sequence[str],
    relation_path_ids: Sequence[str] = (),
    snapshot_ids: Sequence[str] = (),
    call_path_ids: Sequence[str] = (),
    branch_conditions: Sequence[str] = (),
    layer_coverage: str = "unknown",
    construction_executed: bool = True,
) -> FieldEvidenceProofV2:
    """Combine exact spans only when snapshot, reachability, and branches agree."""

    unique_snapshots = tuple(dict.fromkeys(_text(item) for item in snapshot_ids if _text(item)))
    unique_branches = tuple(dict.fromkeys(_text(item) for item in branch_conditions if _text(item)))
    spans = tuple(dict.fromkeys(_text(item) for item in span_ids if _text(item)))
    reason = ""
    compatible = True
    if len(unique_snapshots) > 1:
        compatible = False
        reason = "incompatible_source_snapshots"
    elif any("exclusive:" in item or item.startswith("else:") or "mutex:" in item for item in unique_branches):
        polarities = {item.split(":", 1)[0] for item in unique_branches}
        if {"if", "else"} <= polarities or {"then", "else"} <= polarities:
            compatible = False
            reason = "mutually_exclusive_branches"
    elif not construction_executed:
        compatible = False
        reason = "construction_not_executed"
    elif layer_coverage == "partial":
        compatible = False
        reason = "partial_layer_coverage"
    elif len(spans) < 2 and layer_coverage == "all":
        compatible = False
        reason = "universal_claim_requires_construction_and_forward"
    return FieldEvidenceProofV2(
        proof_id=proof_id,
        conclusion_atom_id=conclusion_atom_id,
        span_ids=spans,
        relation_path_ids=tuple(dict.fromkeys(_text(item) for item in relation_path_ids if _text(item))),
        snapshot_ids=unique_snapshots,
        call_path_ids=tuple(dict.fromkeys(_text(item) for item in call_path_ids if _text(item))),
        branch_conditions=unique_branches,
        layer_coverage=layer_coverage if layer_coverage in {"all", "partial", "unknown"} else "unknown",  # type: ignore[arg-type]
        compatible=compatible,
        rejection_reason=reason,
    )


def terminal_atom_closure(
    atom: IntentEvidenceAtomV1,
    *,
    evidence_disposition: str,
    search_terminal: bool,
    author_surface_receipt_id: str = "",
    stop_reason: str = "",
    review_binding_id: str = "",
    repository_proof_status: str = "unavailable",
) -> IntentAtomClosureStatusV1:
    surface = "incomplete"
    if evidence_disposition in {"author_spec_only", "out_of_scope"}:
        if stop_reason and author_surface_receipt_id and review_binding_id:
            surface = "complete"
        else:
            surface = "incomplete"
    elif evidence_disposition == "repository_exact" and repository_proof_status == "exact":
        surface = "complete"
    elif evidence_disposition == "mismatch" and author_surface_receipt_id:
        surface = "complete"
    return IntentAtomClosureStatusV1(
        atom_id=atom.atom_id,
        search_status="terminal" if search_terminal else "searching",
        evidence_disposition=evidence_disposition,  # type: ignore[arg-type]
        candidate_surface_status=surface,  # type: ignore[arg-type]
        repository_proof_status=repository_proof_status,  # type: ignore[arg-type]
        author_surface_receipt_id=author_surface_receipt_id,
        stop_reason=stop_reason,
        review_binding_id=review_binding_id,
    )


def compile_intent_evidence_from_facets(
    *,
    facets: Sequence[Any] = (),
    alignments: Sequence[Any] = (),
    story_spine: Sequence[Any] = (),
) -> dict[str, Any]:
    """Produce atoms, closures, and legacy-field traces from Candidate facets."""

    alignment_by_facet = {
        _text(_get(item, "facet_id")): item
        for item in alignments
        if _text(_get(item, "facet_id"))
    }
    story_by_obligation: dict[str, str] = {}
    for node in story_spine:
        story_id = _text(_get(node, "story_node_id"))
        for obligation_id in _ids(_get(node, "linked_obligation_ids")):
            story_by_obligation.setdefault(obligation_id, story_id)
    atoms: list[IntentEvidenceAtomV1] = []
    closures: list[IntentAtomClosureStatusV1] = []
    field_trace: dict[str, list[str]] = {}
    diagnostics: list[str] = []
    for facet in facets:
        facet_id = _text(_get(facet, "facet_id"))
        if not facet_id:
            continue
        quote = _text(_get(facet, "exact_source_quote"))
        brief_id = _text(_get(facet, "brief_id"))
        story_id = story_by_obligation.get(brief_id, "")
        fields = _get(facet, "semantic_fields") or {}
        if not isinstance(fields, Mapping):
            fields = {}
        produced, diag = decompose_intent_evidence_atoms(
            narrative_unit_id=facet_id,
            story_node_id=story_id,
            source_quote=quote or facet_id,
            owner_fields=fields,
            owner_confirmed=False,
        )
        diagnostics.extend(f"{facet_id}:{item}" for item in diag)
        field_trace[facet_id] = [item.atom_id for item in produced]
        alignment = alignment_by_facet.get(facet_id)
        excerpts = _ids(_get(alignment, "excerpts") or _get(alignment, "exact_excerpts"))
        status = _text(_get(alignment, "status") or _get(alignment, "alignment_status"))
        authority = _text(_get(facet, "facet_kind"))
        for atom in produced:
            if atom.authority_expectation in {"author_rationale", "author_specification"}:
                disposition = "author_spec_only"
                proof = "not_applicable"
            elif status in {"aligned", "supported", "exact"} and excerpts:
                disposition = "repository_exact"
                proof = "exact"
            elif excerpts or status in {"partial", "mismatch"}:
                disposition = "repository_partial" if status != "mismatch" else "mismatch"
                proof = "partial" if status != "mismatch" else "mismatch"
            else:
                disposition = "bounded_not_found"
                proof = "unavailable"
            closures.append(terminal_atom_closure(
                atom,
                evidence_disposition=disposition,
                search_terminal=True,
                stop_reason="bounded_research_complete",
                repository_proof_status=proof,
            ))
            atoms.append(atom)
    return {
        "atoms": tuple(atoms),
        "closures": tuple(closures),
        "legacy_field_to_atom_trace": {
            key: tuple(values) for key, values in field_trace.items()
        },
        "diagnostics": tuple(dict.fromkeys(diagnostics)),
    }


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    return tuple(dict.fromkeys(_text(item) for item in value if _text(item)))
