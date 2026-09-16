"""Compile a validation proposition set in parallel with argument briefs."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from code2paper.agentic.intent_spine_models import (
    MethodPropositionSetV2,
    MethodPropositionV2,
)
from code2paper.agentic.method_proposition_models import (
    MethodPropositionSetV1,
    MethodPropositionV1,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    return tuple(dict.fromkeys(_text(item) for item in value if _text(item)))


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _stable_id(*parts: str) -> str:
    return "MP2-" + hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def _surface_for_atom(atom: Any) -> str:
    authority = _text(_get(atom, "authority_expectation"))
    if authority == "author_rationale":
        return "author_specification"
    if authority == "author_specification":
        return "author_specification"
    return "repository"


def compile_method_propositions_v2(
    *,
    intent_atoms: Sequence[Any] = (),
    publication_field_candidates: Sequence[Any] = (),
    candidate_facet_policies: Sequence[Any] = (),
    mechanism_details: Sequence[Any] = (),
) -> MethodPropositionSetV2:
    """Deterministic validation set.  Does not write publication prose."""

    propositions: list[MethodPropositionV2] = []
    seen: set[str] = set()

    def add(item: MethodPropositionV2) -> None:
        if item.proposition_id in seen:
            return
        seen.add(item.proposition_id)
        propositions.append(item)

    policy_by_facet = {
        _text(_get(item, "facet_id")): item
        for item in candidate_facet_policies
        if _text(_get(item, "facet_id"))
    }
    for atom in intent_atoms:
        atom_id = _text(_get(atom, "atom_id"))
        if not atom_id:
            continue
        surface = _surface_for_atom(atom)
        add(MethodPropositionV2(
            proposition_id=_stable_id("atom", atom_id),
            surface=surface,  # type: ignore[arg-type]
            subject=_text(_get(atom, "subject")) or atom_id,
            predicate=_text(_get(atom, "predicate")) or "states",
            inputs=_ids(_get(atom, "object_or_operands")),
            polarity=_text(_get(atom, "polarity")) or "positive",  # type: ignore[arg-type]
            quantifier=_text(_get(atom, "quantifier")),
            condition=_text(_get(atom, "condition")),
            boundary=_text(_get(atom, "boundary")),
            source_atom_ids=(atom_id,),
            may_enter_verified=surface == "repository" and not _text(_get(atom, "unresolved_reason")),
            requires_caveat=surface != "repository",
        ))
    for candidate in publication_field_candidates:
        candidate_id = _text(_get(candidate, "candidate_id") or _get(candidate, "facet_id"))
        if not candidate_id:
            continue
        policy = policy_by_facet.get(_text(_get(candidate, "facet_id")))
        lane = _text(_get(policy, "prose_policy") or _get(candidate, "authority_lane"))
        surface = "author_specification" if "author" in lane else "repository"
        if "mismatch" in lane:
            surface = "mismatch"
        fields = _get(candidate, "semantic_fields") or {}
        if not isinstance(fields, Mapping):
            fields = {}
        add(MethodPropositionV2(
            proposition_id=_stable_id("field", candidate_id),
            surface=surface,  # type: ignore[arg-type]
            subject=_text(fields.get("subject") or candidate_id),
            predicate=_text(fields.get("operation") or fields.get("formula_goal") or "states"),
            inputs=_ids(fields.get("inputs")),
            outputs=_ids(fields.get("outputs")),
            condition=_text(fields.get("conditions")),
            source_field_candidate_ids=(candidate_id,),
            may_enter_verified=surface == "repository" and bool(_get(candidate, "is_consumable", False)),
            requires_caveat=surface != "repository",
        ))
    for detail in mechanism_details:
        detail_id = _text(_get(detail, "detail_id"))
        if not detail_id:
            continue
        authority = _text(_get(detail, "evidence_authority"))
        surface = "repository" if authority == "repository_verified" else "author_specification"
        add(MethodPropositionV2(
            proposition_id=_stable_id("detail", detail_id),
            surface=surface,  # type: ignore[arg-type]
            subject=_text(_get(detail, "subject") or _get(detail, "semantic_atom") or detail_id),
            predicate=_text(_get(detail, "predicate") or "states"),
            inputs=_ids(_get(detail, "operands")),
            outputs=(_text(_get(detail, "result")),) if _text(_get(detail, "result")) else (),
            condition="; ".join(_ids(_get(detail, "conditions"))),
            source_detail_ids=(detail_id,),
            may_enter_verified=surface == "repository",
            requires_caveat=surface != "repository",
        ))
    return MethodPropositionSetV2(propositions=tuple(propositions))


def propositions_v2_as_v1(propositions: MethodPropositionSetV2 | None) -> MethodPropositionSetV1 | None:
    """Project V2 validation cards onto the V1 aligner contract."""

    if propositions is None or not propositions.propositions:
        return None
    items: list[MethodPropositionV1] = []
    for item in propositions.propositions:
        origin = "repository_evidence" if item.surface == "repository" else "author_intent"
        lane = "repository_verified" if item.may_enter_verified else (
            "repository_mismatch" if item.surface == "mismatch" else "author_intent_unverified"
        )
        items.append(MethodPropositionV1(
            proposition_id=item.proposition_id,
            origin=origin,  # type: ignore[arg-type]
            evidence_lane=lane,  # type: ignore[arg-type]
            reader_subject=item.subject,
            transformation=item.predicate,
            inputs=item.inputs,
            outputs=item.outputs,
            conditions=(item.condition,) if item.condition else (),
            boundary=item.boundary,
            required_qualifiers=item.required_qualifiers,
            immutable_numeric_tokens=item.immutable_numeric_tokens,
            immutable_formula_tokens=item.immutable_formula_tokens,
            may_enter_verified=False,
            requires_caveat=item.requires_caveat or item.surface != "repository",
        ))
    digest = "sha256:" + hashlib.sha256(
        propositions.content_digest.encode("utf-8")
    ).hexdigest()
    return MethodPropositionSetV1(
        propositions=tuple(items),
        binding_sidecar_digest=digest,
    )
