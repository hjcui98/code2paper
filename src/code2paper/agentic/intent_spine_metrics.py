"""Dashboard metrics that keep record, symbol, obligation, and atom keys distinct."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from code2paper.agentic.formula_identity import (
    compile_canonical_formula_obligations,
    formula_identity_conservation_table,
)


_TARGET_ROLES = frozenset({"target_core", "target_dependency"})
_FULL_CHAIN_STATUS = "acquired_and_compiled"
_SEARCH_TERMINAL_RESOLUTIONS = frozenset({
    "implemented_exact",
    "implemented_partial",
    "author_spec_only",
    "repo_mismatch",
    "inactive_alternative",
    "not_found_after_bounded_search",
    "out_of_scope",
})
_SEARCH_TERMINAL_STATUSES = frozenset({
    "acquired_and_compiled",
    "explicitly_rejected",
    "superseded",
    "not_selected",
})


def _get(record: Any, name: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_research_closure_dashboard(
    *,
    records: Sequence[Any] = (),
    publication_field_candidates: Sequence[Any] = (),
    typed_field_deferred: Sequence[Any] = (),
    intent_atoms: Sequence[Any] = (),
    atom_closures: Sequence[Any] = (),
    legacy_field_ids: Sequence[str] = (),
    atom_ids_by_legacy_field: Mapping[str, Sequence[str]] | None = None,
    must_cover_obligation_ids: Sequence[str] = (),
    author_formula_ids: Sequence[str] = (),
    mechanism_obligations: Sequence[Any] = (),
    accepted_packages: Sequence[Any] = (),
    consumed_package_ids: Sequence[str] = (),
    planning_targets: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Report independent denominators for acquisition, atoms, and formulas."""

    target_records = tuple(
        item for item in records
        if _text(_get(item, "ownership_role")) in _TARGET_ROLES
    )
    symbols = {
        _text(_get(item, "candidate_symbol_id"))
        for item in target_records
        if _text(_get(item, "candidate_symbol_id"))
    }
    obligations = {
        _text(_get(item, "obligation_id"))
        for item in target_records
        if _text(_get(item, "obligation_id"))
    }
    stage_counts = {
        "discovered": 0,
        "read": 0,
        "behavior": 0,
        "packet": 0,
        "fact": 0,
        "claim": 0,
        "full_chain": 0,
    }
    for item in target_records:
        if _get(item, "search_observation_refs") or _text(_get(item, "terminal_status")):
            stage_counts["discovered"] += 1
        if _get(item, "read_observation_refs") or _text(_get(item, "read_status")) not in {"", "not_attempted"}:
            stage_counts["read"] += 1
        if _get(item, "behavior_node_ids"):
            stage_counts["behavior"] += 1
        if _get(item, "packet_ids"):
            stage_counts["packet"] += 1
        if _get(item, "fact_ids"):
            stage_counts["fact"] += 1
        if _get(item, "claim_ids"):
            stage_counts["claim"] += 1
        if _text(_get(item, "terminal_status")) == _FULL_CHAIN_STATUS:
            stage_counts["full_chain"] += 1

    by_obligation: dict[str, list[Any]] = defaultdict(list)
    for item in target_records:
        by_obligation[_text(_get(item, "obligation_id")) or "unknown"].append(item)
    obligation_rollup = {
        "at_least_one_exact_full_chain": 0,
        "only_partial": 0,
        "mismatch": 0,
        "bounded_not_found": 0,
    }
    for obligation_id, rows in by_obligation.items():
        _ = obligation_id
        statuses = {_text(_get(item, "resolution_status")) for item in rows}
        terminals = {_text(_get(item, "terminal_status")) for item in rows}
        if _FULL_CHAIN_STATUS in terminals:
            obligation_rollup["at_least_one_exact_full_chain"] += 1
        elif "repo_mismatch" in statuses:
            obligation_rollup["mismatch"] += 1
        elif "not_found_after_bounded_search" in statuses:
            obligation_rollup["bounded_not_found"] += 1
        elif "implemented_partial" in statuses:
            obligation_rollup["only_partial"] += 1

    search_terminal = 0
    repository_proof_complete = 0
    for item in target_records:
        terminal_status = _text(_get(item, "terminal_status"))
        resolution = _text(_get(item, "resolution_status"))
        if terminal_status in _SEARCH_TERMINAL_STATUSES or resolution in _SEARCH_TERMINAL_RESOLUTIONS:
            search_terminal += 1
        if terminal_status == _FULL_CHAIN_STATUS and resolution in {"implemented_exact", ""}:
            repository_proof_complete += 1

    atom_rows = tuple(intent_atoms or ())
    closure_by_atom = {
        _text(_get(item, "atom_id")): item
        for item in (atom_closures or ())
        if _text(_get(item, "atom_id"))
    }
    candidate_surface_complete = 0
    repository_atom_complete = 0
    for atom in atom_rows:
        closure = closure_by_atom.get(_text(_get(atom, "atom_id")))
        if closure is None:
            continue
        if _text(_get(closure, "candidate_surface_status")) == "complete":
            candidate_surface_complete += 1
        if _text(_get(closure, "repository_proof_status")) == "exact":
            repository_atom_complete += 1

    deferred_rows = tuple(typed_field_deferred or ())
    deferred_by_reason: Counter[str] = Counter()
    deferred_by_lane: Counter[str] = Counter()
    for item in deferred_rows:
        reason = _text(_get(item, "reason") or _get(item, "failure_reason") or "unspecified")
        lane = _text(_get(item, "authority_lane") or _get(item, "lane") or "unspecified")
        deferred_by_reason[reason] += 1
        deferred_by_lane[lane] += 1

    field_ids = tuple(dict.fromkeys(
        _text(item) for item in (legacy_field_ids or ()) if _text(item)
    ))
    if not field_ids:
        field_ids = tuple(dict.fromkeys(
            _text(_get(item, "candidate_id") or _get(item, "field_id") or _get(item, "facet_id"))
            for item in (*publication_field_candidates, *deferred_rows)
            if _text(_get(item, "candidate_id") or _get(item, "field_id") or _get(item, "facet_id"))
        ))
    mapping = {
        str(key): tuple(str(value) for value in values if str(value).strip())
        for key, values in (atom_ids_by_legacy_field or {}).items()
    }
    traced_fields = sum(1 for field_id in field_ids if mapping.get(field_id))
    required_field_disposition = 0
    for field_id in field_ids:
        atom_ids = mapping.get(field_id) or ()
        if not atom_ids:
            continue
        if all(
            _text(_get(closure_by_atom.get(atom_id), "evidence_disposition"))
            for atom_id in atom_ids
        ):
            required_field_disposition += 1
    if not mapping and field_ids:
        # Until atoms exist, a deferred/candidate row still counts as a typed
        # disposition so the dashboard cannot hide the 30-field remainder.
        required_field_disposition = len(deferred_rows) + sum(
            1 for item in publication_field_candidates if _get(item, "is_consumable", True)
        )

    must_cover = tuple(dict.fromkeys(
        _text(item) for item in (must_cover_obligation_ids or obligations) if _text(item)
    ))
    atom_ids_by_author_formula: dict[str, tuple[str, ...]] = {}
    for author_id in author_formula_ids:
        if str(author_id).startswith("formula:facet:"):
            facet_id = str(author_id).split("formula:facet:", 1)[1]
            atom_ids_by_author_formula[str(author_id)] = tuple(mapping.get(facet_id, ()))
        elif mapping.get(str(author_id)):
            atom_ids_by_author_formula[str(author_id)] = tuple(mapping[str(author_id)])
    canonical, formula_trace = compile_canonical_formula_obligations(
        author_formula_ids=author_formula_ids,
        mechanism_obligations=mechanism_obligations,
        accepted_packages=accepted_packages,
        consumed_package_ids=consumed_package_ids,
        intent_atom_ids_by_author_formula=atom_ids_by_author_formula,
        author_formula_expectations={
            str(item): "required"
            for item in author_formula_ids
            if str(item).startswith("formula:")
        },
    )
    identity_table = formula_identity_conservation_table(canonical, formula_trace)
    planning = dict(planning_targets or {})
    return {
        "schema_version": "2.0",
        "research": {
            "obligation_candidate_records": len(target_records),
            "unique_candidate_symbols": len(symbols),
            "unique_obligations": len(obligations),
            "must_cover_obligations": len(must_cover),
            "must_cover_intent_atoms": len(atom_rows),
            "stage_counts": stage_counts,
            "search_terminal_records": search_terminal,
            "candidate_surface_complete_atoms": candidate_surface_complete,
            "repository_proof_complete_records": repository_proof_complete,
            "repository_proof_complete_atoms": repository_atom_complete,
            "unresolved_acquisition": sum(
                1 for item in target_records
                if not (
                    _text(_get(item, "terminal_status")) in _SEARCH_TERMINAL_STATUSES
                    or _text(_get(item, "resolution_status")) in _SEARCH_TERMINAL_RESOLUTIONS
                )
            ),
            "acquired_and_compiled": stage_counts["full_chain"],
            "obligation_rollup": obligation_rollup,
            "full_chain_record_ratio": (
                stage_counts["full_chain"] / len(target_records) if target_records else 0.0
            ),
        },
        "alignment": {
            "atomic_fields": len(publication_field_candidates),
            "renderable_fields": sum(
                1 for item in publication_field_candidates if _get(item, "is_consumable", False)
            ),
            "deferred_fields": len(deferred_rows),
            "deferred_by_failure_reason": dict(deferred_by_reason),
            "deferred_by_authority_lane": dict(deferred_by_lane),
            "legacy_field_count": len(field_ids),
            "legacy_field_to_atom_trace_coverage": (
                traced_fields / len(field_ids) if field_ids else 0.0
            ),
            "required_field_disposition_coverage": (
                required_field_disposition / len(field_ids) if field_ids else 0.0
            ),
        },
        "planning": {
            "hard_targets": int(planning.get("hard_targets") or 0),
            "support_slots": int(planning.get("support_slots") or 0),
            "publication_slots": int(planning.get("publication_slots") or 0),
        },
        "formula_identity": identity_table,
    }
