"""Canonical formula identity bridge and publication worthiness."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from code2paper.agentic.intent_spine_models import CanonicalFormulaObligationV2


_PLUMBING_PREDICATES = frozenset({
    "LOAD", "WRITE", "RESHAPE", "READ", "RETURN", "CONSTRUCT", "CONCAT",
    "SORT", "STACK", "CALL", "FILTER", "SELECT",
})
_DISPLAY_PREDICATES = frozenset({
    "compute_loss", "infonce", "contrastive", "normalize", "softmax",
    "attention", "dot", "score", "update", "weighted_sum",
})
_DISPLAY_ROLES = frozenset({
    "training_objective", "inference", "formalization",
})
_AUTHOR_DISPLAY_HINTS = (
    "loss", "infonce", "dot-product", "dot product", "attention",
    "normalize", "softmax", "score",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (_text(value),) if _text(value) else ()
    return tuple(dict.fromkeys(_text(item) for item in value if _text(item)))


def _digest(*parts: str) -> str:
    encoded = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def classify_formula_worthiness(
    record: Any,
    *,
    author_expectation: str = "none",
) -> tuple[str, str]:
    """Separate evidence validity from publication worthiness."""

    predicate = _text(
        getattr(record, "predicate", "")
        or (record.get("predicate") if isinstance(record, Mapping) else "")
        or getattr(record, "mathematical_goal", "")
        or (record.get("mathematical_goal") if isinstance(record, Mapping) else "")
    )
    role = _text(
        getattr(record, "role", "")
        or (record.get("role") if isinstance(record, Mapping) else "")
        or getattr(record, "claim_kind", "")
        or ""
    )
    latex = _text(
        getattr(record, "latex", "")
        or (record.get("latex") if isinstance(record, Mapping) else "")
        or getattr(record, "source_equation_expression", "")
        or ""
    )
    upper_pred = predicate.upper()
    opcode = re.match(
        r"\b(LOAD|WRITE|RESHAPE|CALL|READ|RETURN|CONSTRUCT|CONCAT|SORT|STACK|FILTER|SELECT)\b",
        upper_pred,
    )
    if opcode or any(token in upper_pred.split() for token in _PLUMBING_PREDICATES):
        if author_expectation == "required" and any(
            hint in (predicate + " " + latex).casefold() for hint in _AUTHOR_DISPLAY_HINTS
        ):
            return "display", "author_plan_requires_academic_definition"
        return "prose_or_algorithm", "plumbing_or_container_operation"
    if re.search(r"\bNone\b|\[\s*\]", latex) or "default" in predicate.casefold():
        return "prose_or_algorithm", "default_or_list_initialization"
    if re.search(r"\b(?:shape|index|arange|unsqueeze|view)\b", (predicate + " " + latex).casefold()):
        return "prose_or_algorithm", "shape_or_index_arithmetic"
    lowered = (predicate + " " + role + " " + latex).casefold()
    if role in _DISPLAY_ROLES or any(token in lowered for token in _DISPLAY_PREDICATES):
        return "display", "academic_method_definition"
    if author_expectation == "required":
        return "display", "author_formula_expectation_required"
    if author_expectation == "preferred":
        return "inline", "author_formula_expectation_preferred"
    return "prose_or_algorithm", "no_academic_display_definition"


def _record_get(record: Any, *names: str) -> Any:
    for name in names:
        if isinstance(record, Mapping) and name in record:
            return record.get(name)
        if hasattr(record, name):
            return getattr(record, name)
    return None


def compile_canonical_formula_obligations(
    *,
    author_formula_ids: Sequence[str] = (),
    mechanism_obligations: Sequence[Any] = (),
    accepted_packages: Sequence[Any] = (),
    consumed_package_ids: Sequence[str] = (),
    author_formula_expectations: Mapping[str, str] | None = None,
    intent_atom_ids_by_author_formula: Mapping[str, Sequence[str]] | None = None,
    package_to_paragraph_ids: Mapping[str, Sequence[str]] | None = None,
) -> tuple[CanonicalFormulaObligationV2, dict[str, Any]]:
    """Bridge author formula IDs and mechanism obligations onto canonical identities.

    Source ID sets remain distinct.  A zero intersection between author IDs
    and mechanism obligation IDs is preserved in the trace rather than rewritten.
    """

    expectations = {
        str(key): str(value)
        for key, value in (author_formula_expectations or {}).items()
        if str(key).strip()
    }
    atom_map = {
        str(key): tuple(str(item) for item in values if str(item).strip())
        for key, values in (intent_atom_ids_by_author_formula or {}).items()
    }
    author_ids = tuple(dict.fromkeys(_text(item) for item in author_formula_ids if _text(item)))
    mech_rows = tuple(mechanism_obligations or ())
    packages = tuple(accepted_packages or ())
    consumed = set(_ids(consumed_package_ids))

    mech_by_id: dict[str, Any] = {}
    for item in mech_rows:
        obligation_id = _text(_record_get(item, "obligation_id"))
        if obligation_id:
            mech_by_id[obligation_id] = item
    package_by_obligation: dict[str, list[Any]] = {}
    for package in packages:
        for obligation_id in _ids(_record_get(package, "satisfied_obligation_ids", "obligation_ids")):
            package_by_obligation.setdefault(obligation_id, []).append(package)

    groups: dict[str, dict[str, Any]] = {}
    paragraph_map = {
        str(key): tuple(str(item) for item in values if str(item).strip())
        for key, values in (package_to_paragraph_ids or {}).items()
    }

    def empty_row() -> dict[str, Any]:
        return {
            "author_ids": [],
            "mechanism_ids": [],
            "atom_ids": [],
            "proof_ids": [],
            "expectation": "none",
            "records": [],
        }

    def add_to_group(key: str) -> dict[str, Any]:
        return groups.setdefault(key, empty_row())

    def author_bridge_keys(author_id: str) -> tuple[str, ...]:
        keys: list[str] = []
        if author_id.startswith("formula:facet:"):
            facet_id = author_id.split("formula:facet:", 1)[1]
            if facet_id:
                keys.append(f"facet:{facet_id}")
        proof_ids = tuple(
            item for item in atom_map.get(author_id, ()) if item.startswith("equation:")
        )
        if proof_ids:
            keys.append("eq:" + "|".join(proof_ids))
        return tuple(dict.fromkeys(keys)) or (f"src:{author_id}",)

    def mechanism_bridge_keys(item: Any, obligation_id: str) -> tuple[str, ...]:
        keys: list[str] = []
        for facet_id in _ids(_record_get(item, "source_facet_ids")):
            keys.append(f"facet:{facet_id}")
        proof_ids = _ids(_record_get(item, "source_equation_ids"))
        if proof_ids:
            keys.append("eq:" + "|".join(proof_ids))
        return tuple(dict.fromkeys(keys)) or (f"src:{obligation_id}",)

    for author_id in author_ids:
        keys = author_bridge_keys(author_id)
        row = add_to_group(keys[0])
        for extra in keys[1:]:
            other = groups.get(extra)
            if other is not None and other is not row:
                row["author_ids"].extend(other["author_ids"])
                row["mechanism_ids"].extend(other["mechanism_ids"])
                row["atom_ids"].extend(other["atom_ids"])
                row["proof_ids"].extend(other["proof_ids"])
                row["records"].extend(other["records"])
                groups[extra] = row
            else:
                groups[extra] = row
        row["author_ids"].append(author_id)
        row["atom_ids"].extend(atom_map.get(author_id, ()))
        row["proof_ids"].extend(item for item in atom_map.get(author_id, ()) if item.startswith("equation:"))
        author_expectation = expectations.get(
            author_id,
            "required" if author_id.startswith("formula:") else "none",
        )
        rank = {"none": 0, "preferred": 1, "required": 2}
        if rank.get(author_expectation, 0) > rank.get(row["expectation"], 0):
            row["expectation"] = author_expectation

    for obligation_id, item in mech_by_id.items():
        keys = mechanism_bridge_keys(item, obligation_id)
        row = add_to_group(keys[0])
        for extra in keys[1:]:
            other = groups.get(extra)
            if other is not None and other is not row:
                row["author_ids"].extend(other["author_ids"])
                row["mechanism_ids"].extend(other["mechanism_ids"])
                row["atom_ids"].extend(other["atom_ids"])
                row["proof_ids"].extend(other["proof_ids"])
                row["records"].extend(other["records"])
                groups[extra] = row
            else:
                groups[extra] = row
        row["mechanism_ids"].append(obligation_id)
        row["proof_ids"].extend(_ids(_record_get(item, "source_equation_ids")))
        row["records"].append(item)
        mech_expectation = _text(_record_get(item, "expectation")) or "preferred"
        rank = {"none": 0, "preferred": 1, "required": 2}
        if rank.get(mech_expectation, 0) > rank.get(row["expectation"], 0):
            row["expectation"] = mech_expectation

    unique_rows: list[dict[str, Any]] = []
    seen_row_ids: set[int] = set()
    for row in groups.values():
        marker = id(row)
        if marker in seen_row_ids:
            continue
        seen_row_ids.add(marker)
        unique_rows.append(row)

    canonical: list[CanonicalFormulaObligationV2] = []
    typed_diffs: list[dict[str, Any]] = []
    incidental = 0
    for row in unique_rows:
        sample = row["records"][0] if row["records"] else {
            "predicate": ",".join(row["author_ids"] or row["mechanism_ids"]),
            "mathematical_goal": ",".join(row["author_ids"] or row["mechanism_ids"]),
        }
        worthiness, reason = classify_formula_worthiness(
            sample, author_expectation=row["expectation"]
        )
        accepted_ids = []
        consumed_ids: list[str] = []
        committed_paragraphs: list[str] = []
        extra_packages = 0
        for obligation_id in dict.fromkeys(row["mechanism_ids"]):
            bound = package_by_obligation.get(obligation_id, [])
            if not bound:
                continue
            accepted_ids.append(_text(_record_get(bound[0], "package_id")))
            extra_packages += max(0, len(bound) - 1)
            for package in bound:
                package_id = _text(_record_get(package, "package_id"))
                if package_id in consumed:
                    consumed_ids.append(package_id)
                    committed_paragraphs.extend(paragraph_map.get(package_id, ()))
        if extra_packages:
            typed_diffs.append({
                "kind": "multiple_packages_for_one_obligation",
                "extra_packages": extra_packages,
                "source_mechanism_obligation_ids": list(dict.fromkeys(row["mechanism_ids"])),
            })
        if worthiness in {"prose_or_algorithm", "rejected"}:
            incidental += len(row["mechanism_ids"])
            typed_diffs.append({
                "kind": "non_display_disposition",
                "worthiness": worthiness,
                "reason": reason,
                "source_author_formula_ids": list(dict.fromkeys(row["author_ids"])),
                "source_mechanism_obligation_ids": list(dict.fromkeys(row["mechanism_ids"])),
            })
        if len(dict.fromkeys(row["author_ids"])) > 1:
            typed_diffs.append({
                "kind": "merged_author_formula_ids",
                "source_author_formula_ids": list(dict.fromkeys(row["author_ids"])),
            })
        if row["author_ids"] and row["mechanism_ids"]:
            typed_diffs.append({
                "kind": "bridged_author_and_mechanism_ids",
                "source_author_formula_ids": list(dict.fromkeys(row["author_ids"])),
                "source_mechanism_obligation_ids": list(dict.fromkeys(row["mechanism_ids"])),
            })
        elif row["author_ids"] and not row["mechanism_ids"]:
            typed_diffs.append({
                "kind": "unbridged_author_formula",
                "source_author_formula_ids": list(dict.fromkeys(row["author_ids"])),
            })
        canonical_id = f"canonical:formula:{_digest(*dict.fromkeys(row['author_ids']), *dict.fromkeys(row['mechanism_ids']))}"
        canonical.append(CanonicalFormulaObligationV2(
            canonical_formula_obligation_id=canonical_id,
            source_author_formula_ids=tuple(dict.fromkeys(row["author_ids"])),
            source_mechanism_obligation_ids=tuple(dict.fromkeys(row["mechanism_ids"])),
            source_intent_atom_ids=tuple(dict.fromkeys(row["atom_ids"])),
            expectation=row["expectation"] if row["expectation"] in {"required", "preferred", "none"} else "preferred",
            source_proof_ids=tuple(dict.fromkeys(row["proof_ids"])),
            formula_worthiness=worthiness,  # type: ignore[arg-type]
            disposition_reason=reason,
            accepted_package_id=accepted_ids[0] if accepted_ids else "",
            consumed_package_ids=tuple(dict.fromkeys(consumed_ids)),
            committed_paragraph_ids=tuple(dict.fromkeys(committed_paragraphs)),
            open=bool(
                row["expectation"] == "required"
                and (
                    worthiness in {"prose_or_algorithm", "rejected"}
                    or not accepted_ids
                    or not row["mechanism_ids"]
                )
            ),
        ))

    author_set = set(author_ids)
    mech_set = set(mech_by_id)
    covered_author = {
        item for row in canonical for item in row.source_author_formula_ids
    }
    covered_mech = {
        item for row in canonical for item in row.source_mechanism_obligation_ids
    }
    package_ids = [
        _text(_record_get(package, "package_id"))
        for package in packages
        if _text(_record_get(package, "package_id"))
    ]
    reverse_package = {}
    for row in canonical:
        if row.accepted_package_id:
            reverse_package[row.accepted_package_id] = row.canonical_formula_obligation_id
    unbridged_packages = [
        package_id for package_id in package_ids if package_id not in reverse_package
    ]
    trace = {
        "schema_version": "2.0",
        "author_formula_ids": list(author_ids),
        "mechanism_obligation_ids": list(mech_by_id),
        "raw_id_intersection": sorted(author_set & mech_set),
        "raw_id_intersection_size": len(author_set & mech_set),
        "author_ids_without_canonical": sorted(author_set - covered_author),
        "mechanism_ids_without_canonical": sorted(mech_set - covered_mech),
        "accepted_package_ids": package_ids,
        "consumed_package_ids": sorted(consumed),
        "packages_without_canonical": unbridged_packages,
        "incidental_or_code_trace_sources": incidental,
        "typed_diffs": typed_diffs,
        "canonical_count": len(canonical),
    }
    return tuple(canonical), trace


def formula_identity_conservation_table(
    canonical: Sequence[CanonicalFormulaObligationV2],
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "canonical_obligations": [
            item.model_dump(mode="json") for item in canonical
        ],
        "trace": dict(trace),
        "content_digest": "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "canonical": [item.content_digest for item in canonical],
                    "trace": dict(trace),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
