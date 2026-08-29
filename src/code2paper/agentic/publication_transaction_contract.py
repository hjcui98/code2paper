"""Shared, fail-closed validation for paragraph-scoped Method transactions.

The Writer response is model-authored metadata, not evidence by itself.  This
module keeps the small deterministic contract in one place so the Writer
boundary, repair scoring, and the persisted source-to-render trace cannot
disagree about whether a planned paragraph was actually rendered.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


_DISPLAY_MATH_RE = re.compile(r"(?s)(?:\\\[.*?\\\]|\\begin\{(?:equation|aligned|gather|split|cases)\}.*?\\end\{(?:equation|aligned|gather|split|cases)\}|\$\$.*?\$\$)")
_SEMANTIC_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+|[Δδ][A-Za-z0-9_]*")
_ANCHOR_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "from", "this", "that", "is", "are", "be", "as", "by", "via", "we",
})
_POLARITY_RE = re.compile(
    r"\b(?:threshold|comparison)_(gt|gte|lt|lte)_(selects|excludes)\b",
    re.I,
)


def _ids(values: Any) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, Mapping)) or values is None:
        return ()
    try:
        iterator = iter(values)
    except TypeError:
        return ()
    return tuple(dict.fromkeys(
        str(value).strip() for value in iterator if str(value).strip()
    ))


def _digest(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _semantic_tokens(value: Any) -> set[str]:
    return {
        token.casefold()
        for token in _SEMANTIC_TOKEN_RE.findall(str(value or ""))
        if token.casefold() not in _ANCHOR_STOPWORDS and (
            len(token) >= 3 or token.isdigit() or token.startswith(("Δ", "δ"))
        )
    }


def _anchor_compatible(witness: str, body: str, anchors: tuple[str, ...]) -> bool:
    """Check a witness against an authorized excerpt without requiring a
    verbatim source-code paste.

    Exact excerpts are preferred.  When the Writer paraphrases an operation,
    a bounded token-overlap check keeps the witness tied to the same source
    symbols/operation while rejecting an arbitrary self-reported sentence.
    """

    witness = str(witness or "").strip()
    body = str(body or "")
    witness_tokens = _semantic_tokens(witness)
    for raw_anchor in anchors:
        anchor = str(raw_anchor or "").strip()
        if not anchor:
            continue
        if witness == anchor:
            return True
        anchor_tokens = _semantic_tokens(anchor)
        overlap = witness_tokens.intersection(anchor_tokens)
        if len(overlap) < 2:
            continue
        denominator = max(1, min(len(witness_tokens), len(anchor_tokens)))
        if len(overlap) / denominator >= 0.35:
            return True
    return not anchors


def _polarity_signature(value: Any) -> tuple[str, str]:
    """Extract a conservative comparison direction and action from text."""

    text = str(value or "").strip().casefold()
    named = _POLARITY_RE.search(text)
    if named:
        return named.group(1).casefold(), named.group(2).casefold()
    if any(token in text for token in (">=", "≥", "at least", "no less", "not less")):
        operator = "gte"
    elif any(token in text for token in ("<=", "≤", "at most", "no more", "not greater")):
        operator = "lte"
    elif ">" in text or any(token in text for token in (
        "above", "exceeds", "exceeding", "greater than", "more than", "higher than",
    )):
        operator = "gt"
    elif "<" in text or any(token in text for token in (
        "below", "less than", "fewer than", "lower than",
    )):
        operator = "lt"
    else:
        operator = ""
    if any(token in text for token in (
        "select", "choose", "keep", "include", "retain", "accept", "activate",
    )):
        action = "selects"
    elif any(token in text for token in (
        "exclude", "drop", "remove", "reject", "discard", "prune", "filter out",
    )):
        action = "excludes"
    else:
        action = ""
    return operator, action


def _text_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if value is None:
        return ()
    try:
        return tuple(
            str(item).strip() for item in value if str(item).strip()
        )
    except TypeError:
        text = str(value).strip()
        return (text,) if text else ()


def _witness_constraints_from_plan_row(
    plan_row: Mapping[str, Any] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    row = plan_row or {}
    contract = row.get("witness_contract")
    if isinstance(contract, Mapping):
        raw_targets = contract.get("targets") or ()
    else:
        raw_targets = getattr(contract, "targets", ()) or ()
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for item in raw_targets:
        if isinstance(item, Mapping):
            kind = str(item.get("target_kind") or "").strip()
            target_id = str(item.get("target_id") or "").strip()
            exact = _text_values(item.get("allowed_exact_excerpts"))
            semantic_atom = str(item.get("semantic_atom") or "").strip()
            conditions = _text_values(item.get("required_conditions"))
            polarity = str(item.get("required_polarity") or "unknown").strip()
        else:
            kind = str(getattr(item, "target_kind", "") or "").strip()
            target_id = str(getattr(item, "target_id", "") or "").strip()
            exact = _text_values(getattr(item, "allowed_exact_excerpts", ()))
            semantic_atom = str(getattr(item, "semantic_atom", "") or "").strip()
            conditions = _text_values(getattr(item, "required_conditions", ()))
            polarity = str(getattr(item, "required_polarity", "unknown") or "unknown").strip()
        if not kind or not target_id:
            continue
        result[(kind, target_id)] = {
            "exact": exact,
            "semantic_atom": semantic_atom,
            "conditions": conditions,
            "polarity": polarity,
        }
    return result


def _witness_satisfies_constraints(
    witness: str,
    constraints: Mapping[str, Any],
) -> bool:
    semantic_atom = str(constraints.get("semantic_atom") or "").strip()
    if (
        semantic_atom
        and semantic_atom.casefold() not in {"formal expression", "formula"}
        and not _anchor_compatible(witness, "", (semantic_atom,))
    ):
        return False
    conditions = _text_values(constraints.get("conditions"))
    exact = _text_values(constraints.get("exact"))
    polarity = str(constraints.get("polarity") or "").strip()
    # Conditions are independent obligations.  A witness that only repeats
    # the operation but drops its guard must not pass through the operation's
    # semantic anchor by accident.
    if conditions and not all(
        _anchor_compatible(witness, "", (condition,))
        for condition in conditions
    ):
        return False
    expected_operators: set[str] = set()
    expected_actions: set[str] = set()
    for value in (*conditions, *exact, polarity):
        operator, action = _polarity_signature(value)
        if operator:
            expected_operators.add(operator)
        if action and "_" in value:
            expected_actions.add(action)
    observed_operator, observed_action = _polarity_signature(witness)
    if expected_operators and observed_operator not in expected_operators:
        return False
    if expected_actions and observed_action and observed_action not in expected_actions:
        return False
    return True


_TRANSACTION_DECLARATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("facet", "rendered_from_facet_ids"),
    ("field", "rendered_field_candidate_ids"),
    ("slot", "rendered_slot_ids"),
    ("edge", "rendered_edge_ids"),
    ("formula", "used_formula_package_ids"),
    ("claim", "used_claim_ids"),
    ("equation", "used_equation_ids"),
)


def _transaction_declarations(get: Any) -> dict[str, tuple[str, ...]]:
    """Read the closed declaration sets from a transaction-like object."""

    return {
        kind: _ids(get(field, ()))
        for kind, field in _TRANSACTION_DECLARATION_FIELDS
    }


def _transaction_witness_keys(get: Any) -> set[tuple[str, str]]:
    """Return existing witness keys without trusting their textual values."""

    existing: set[tuple[str, str]] = set()
    for raw in get("witnesses", ()) or ():
        if isinstance(raw, Mapping):
            key = (
                str(raw.get("witness_kind") or raw.get("kind") or "").strip(),
                str(raw.get("target_id") or "").strip(),
            )
        else:
            key = (
                str(getattr(raw, "witness_kind", "") or "").strip(),
                str(getattr(raw, "target_id", "") or "").strip(),
            )
        if all(key):
            existing.add(key)
    return existing


def _formula_package_indexes(
    formula_packages: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    """Index formula packages by package id and routed obligation id."""

    packages = tuple(item for item in formula_packages if isinstance(item, Mapping))
    package_by_id = {
        str(item.get("package_id") or "").strip(): item
        for item in packages
        if str(item.get("package_id") or "").strip()
    }
    package_by_obligation: dict[str, Mapping[str, Any]] = {}
    for package in packages:
        ids = _ids(
            package.get("satisfied_obligation_ids")
            or ((package.get("obligation_id"),) if package.get("obligation_id") else ())
        )
        for obligation_id in ids:
            package_by_obligation[obligation_id] = package
    return package_by_id, package_by_obligation


def _formula_package_for_target(
    target_id: str,
    *,
    package_by_id: Mapping[str, Mapping[str, Any]],
    package_by_obligation: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    return package_by_id.get(target_id) or package_by_obligation.get(target_id)


def _binding_anchors(constraints: Mapping[str, Any]) -> tuple[str, ...]:
    """Project exact, semantic, and condition anchors for both Binder stages."""

    values = list(_text_values(constraints.get("exact")))
    semantic_atom = str(constraints.get("semantic_atom") or "").strip()
    if semantic_atom and semantic_atom.casefold() not in {"formal expression", "formula"}:
        values.append(semantic_atom)
    values.extend(_text_values(constraints.get("conditions")))
    return tuple(dict.fromkeys(value for value in values if value))


def _resolve_binding_target_key(
    witness_kind: str,
    target_id: str,
    target_keys: set[tuple[str, str]],
) -> tuple[str, str] | None:
    """Resolve compatible target-id wire forms against closed declarations.

    Rendered transaction declarations conventionally store ids with their
    kind prefix (for example ``slot:fact-...``), while some Binder responses
    encode the same target as ``slot:fact-...`` after already using ``slot``
    as the kind.  A plan may also use an unprefixed id.  Accept only an exact
    target or its one-step kind-prefix alias, and only when that alias is
    present in the closed declaration set.  This is a representation-only
    compatibility repair; it cannot authorize a new target.
    """

    kind = str(witness_kind or "").strip()
    value = str(target_id or "").strip()
    if not kind or not value:
        return None
    candidate_ids = [value]
    prefix = f"{kind}:"
    if value.startswith(prefix):
        candidate_ids.append(value[len(prefix):])
    else:
        candidate_ids.append(prefix + value)
    matches = tuple(dict.fromkeys(
        (kind, candidate)
        for candidate in candidate_ids
        if (kind, candidate) in target_keys
    ))
    return matches[0] if len(matches) == 1 else None


def _resolve_unbound_target_key(
    value: str,
    target_keys: set[tuple[str, str]],
) -> tuple[str, str] | None:
    """Resolve an unbound id in either kind-prefixed wire representation."""

    kind, separator, target_id = str(value or "").partition(":")
    if not separator:
        return None
    direct = _resolve_binding_target_key(kind, target_id, target_keys)
    if direct is not None:
        return direct

    # Edge declarations use witness kind ``edge`` but their stable ids use
    # the repository relation prefix ``rel:``.  The Binder commonly reports
    # that id directly (``rel:...``).  Accept it only when the complete value
    # is already the target id of exactly one declared target.
    matches = tuple(dict.fromkeys(
        key for key in target_keys if key[1] == str(value or "").strip()
    ))
    return matches[0] if len(matches) == 1 else None


def paragraph_binding_targets(
    transaction: Mapping[str, Any] | Any,
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_packages: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    """Return local contracts still eligible for a metadata-only Binder.

    Only targets already declared by the Writer are returned. A Binder can
    attach a witness to such a closed target, but it cannot invent a target or
    turn an unanchored id into evidence. Targets without a local semantic
    contract (and without an exact formula package) are deliberately omitted.
    """

    if isinstance(transaction, Mapping):
        get = transaction.get
    else:
        get = lambda name, default=None: getattr(transaction, name, default)
    body = str(get("paragraph_markdown", "") or "")
    if not body:
        return ()
    declarations = _transaction_declarations(get)
    existing = _transaction_witness_keys(get)
    constraints = _witness_constraints_from_plan_row(plan_row)
    package_by_id, package_by_obligation = _formula_package_indexes(formula_packages)
    rows: list[dict[str, Any]] = []
    for kind, target_ids in declarations.items():
        for target_id in target_ids:
            if (kind, target_id) in existing:
                continue
            local = constraints.get((kind, target_id), {})
            package = (
                _formula_package_for_target(
                    target_id,
                    package_by_id=package_by_id,
                    package_by_obligation=package_by_obligation,
                )
                if kind == "formula"
                else None
            )
            has_local_contract = bool(
                local.get("exact")
                or str(local.get("semantic_atom") or "").strip()
                and str(local.get("semantic_atom") or "").strip().casefold()
                not in {"formal expression", "formula"}
                or local.get("conditions")
                or str(local.get("polarity") or "unknown").strip().casefold()
                not in {"", "unknown"}
            )
            if not has_local_contract and package is None:
                continue
            rows.append({
                "witness_kind": kind,
                "target_id": target_id,
                "semantic_atom": str(local.get("semantic_atom") or ""),
                "required_conditions": list(local.get("conditions") or ()),
                "required_polarity": str(local.get("polarity") or "unknown"),
                "allowed_exact_excerpts": list(local.get("exact") or ()),
                "formula_exact_texts": list(dict.fromkeys(
                    str(value).strip()
                    for value in (
                        package.get("markdown_block") if package is not None else "",
                        package.get("latex") if package is not None else "",
                    )
                    if str(value or "").strip()
                )),
            })
    return tuple(rows)


def validate_paragraph_binding_response(
    response: Mapping[str, Any] | Any,
    transaction: Mapping[str, Any] | Any,
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_packages: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
) -> tuple[tuple[dict[str, str], ...], tuple[str, ...], tuple[str, ...]]:
    """Validate a Binder response without granting it prose authority.

    The first return value contains only witnesses whose exact text is a
    unique substring of the frozen body and whose local semantic, polarity,
    and condition contract passes. The second contains representation
    failures; the third contains explicitly reported unbound kind:target keys.
    """

    if isinstance(transaction, Mapping):
        transaction_get = transaction.get
    else:
        transaction_get = lambda name, default=None: getattr(transaction, name, default)
    if isinstance(response, Mapping):
        response_get = response.get
    else:
        response_get = lambda name, default=None: getattr(response, name, default)
    body = str(transaction_get("paragraph_markdown", "") or "")
    paragraph_id = str(transaction_get("paragraph_id", "") or "").strip()
    response_paragraph_id = str(response_get("paragraph_id", "") or "").strip()
    errors: list[str] = []
    if response_paragraph_id != paragraph_id:
        errors.append(
            f"binder_paragraph_id:{response_paragraph_id!r}!={paragraph_id!r}"
        )

    target_rows = paragraph_binding_targets(
        transaction,
        plan_row=plan_row,
        formula_packages=formula_packages,
    )
    by_key = {
        (str(row["witness_kind"]), str(row["target_id"])): row
        for row in target_rows
    }
    target_keys = set(by_key)
    raw_witnesses = response_get("witnesses", ()) or ()
    valid: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_witnesses):
        if isinstance(raw, Mapping):
            kind = str(raw.get("witness_kind") or raw.get("kind") or "").strip()
            target_id = str(raw.get("target_id") or "").strip()
            exact_text = str(raw.get("exact_text") or "").strip()
        else:
            kind = str(getattr(raw, "witness_kind", "") or "").strip()
            target_id = str(getattr(raw, "target_id", "") or "").strip()
            exact_text = str(getattr(raw, "exact_text", "") or "").strip()
        key = _resolve_binding_target_key(kind, target_id, target_keys)
        if key is None:
            errors.append(f"binder_unknown_target:{index}:{kind}:{target_id}")
            continue
        if key in seen:
            errors.append(f"binder_duplicate_target:{kind}:{target_id}")
            continue
        seen.add(key)
        if not exact_text:
            errors.append(f"binder_empty_exact_text:{kind}:{target_id}")
            continue
        if not body or body.count(exact_text) != 1:
            errors.append(f"binder_nonunique_substring:{kind}:{target_id}")
            continue
        row = by_key[key]
        constraints = {
            "exact": tuple(row.get("allowed_exact_excerpts") or ()),
            "semantic_atom": str(row.get("semantic_atom") or ""),
            "conditions": tuple(row.get("required_conditions") or ()),
            "polarity": str(row.get("required_polarity") or "unknown"),
        }
        anchors = _binding_anchors(constraints)
        if anchors and not _anchor_compatible(exact_text, body, anchors):
            errors.append(f"binder_anchor_mismatch:{kind}:{target_id}")
            continue
        if not _witness_satisfies_constraints(exact_text, constraints):
            errors.append(
                f"binder_condition_or_polarity_mismatch:{kind}:{target_id}"
            )
            continue
        formula_exact_texts = tuple(row.get("formula_exact_texts") or ())
        if formula_exact_texts:
            if exact_text not in formula_exact_texts:
                errors.append(f"binder_formula_not_exact_package_block:{target_id}")
                continue
            if not _DISPLAY_MATH_RE.search(body):
                errors.append(f"binder_formula_without_display_math:{target_id}")
                continue
        valid.append({
            "witness_kind": kind,
            "target_id": target_id,
            "exact_text": exact_text,
        })

    unbound_keys: list[tuple[str, str]] = []
    unbound_values: list[str] = []
    for raw in response_get("unbound_target_ids", ()) or ():
        value = str(raw or "").strip()
        if not value:
            errors.append("binder_empty_unbound_target")
            continue
        key = _resolve_unbound_target_key(value, target_keys)
        if key is None:
            errors.append(f"binder_unknown_unbound_target:{value}")
            continue
        if key in seen:
            errors.append(f"binder_target_both_bound_and_unbound:{value}")
            continue
        if key not in unbound_keys:
            unbound_keys.append(key)
            unbound_values.append(value)

    reported = set(seen) | set(unbound_keys)
    for kind, target_id in sorted(target_keys - reported):
        errors.append(f"binder_target_unreported:{kind}:{target_id}")
    return tuple(valid), tuple(dict.fromkeys(errors)), tuple(unbound_values)


class ParagraphTransactionAssessmentV1(BaseModel):
    """Deterministic result for one planned paragraph transaction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph_id: str
    valid: bool = False
    required_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    declared_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    witnessed_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    missing_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    invalid_witnesses: tuple[str, ...] = ()
    semantic_failures: tuple[str, ...] = ()
    body_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ParagraphTransactionAssessmentV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


def required_targets_from_plan_row(plan_row: Mapping[str, Any] | None) -> dict[str, tuple[str, ...]]:
    """Return the exact target sets owned by a paragraph plan row."""

    row = plan_row or {}
    return {
        "facet": _ids(row.get("required_facet_ids")),
        "field": _ids(row.get("required_field_candidate_ids")),
        # Frozen plans predate the support/publication split.  Preserve their
        # exact behavior; new plans explicitly list only reader-facing slots.
        "slot": _ids(
            row.get("required_publication_slot_ids")
            or row.get("ordered_semantic_slot_ids")
        ),
        "edge": _ids(row.get("required_edge_ids")),
        "formula": _ids(row.get("formula_obligation_ids")),
    }


def required_anchors_from_plan_row(
    plan_row: Mapping[str, Any] | None,
) -> dict[tuple[str, str], tuple[str, ...]]:
    """Project paragraph-local semantic atoms and exact excerpts as anchors."""

    result: dict[tuple[str, str], tuple[str, ...]] = {}
    for key, constraints in _witness_constraints_from_plan_row(plan_row).items():
        exact = constraints["exact"]
        semantic_atom = constraints["semantic_atom"]
        conditions = constraints["conditions"]
        values = list(exact)
        if semantic_atom and semantic_atom.casefold() not in {"formal expression", "formula"}:
            values.append(semantic_atom)
        values.extend(conditions)
        values = list(dict.fromkeys(values))
        if values:
            result[key] = tuple(values)
    return result


def _route_package_ids(
    obligation_id: str,
    formula_routes: Mapping[str, Any],
) -> tuple[str, ...]:
    route = formula_routes.get(obligation_id)
    if route is None:
        return ()
    if isinstance(route, Mapping):
        values = route.get("package_ids") or route.get("package_id") or ()
        return _ids(values if not isinstance(values, str) else (values,))
    return _ids(route if not isinstance(route, str) else (route,))


def bind_paragraph_witnesses(
    transaction: Mapping[str, Any] | Any,
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_packages: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
) -> Any:
    """Bind exact metadata to a frozen paragraph without changing its prose.

    This is the deterministic first Binder stage.  It only selects substrings
    already present in ``paragraph_markdown`` and authorized by the local
    contract or an exact formula package.  It never adds declarations, edits
    text, or treats an internal identifier as a textual witness.  The returned
    object is the same transaction type when a Pydantic response model was
    supplied; mappings receive a plain mapping copy.
    """

    if isinstance(transaction, Mapping):
        source = dict(transaction)
        get = source.get
    else:
        source = transaction.model_dump(mode="json") if hasattr(transaction, "model_dump") else {}
        get = lambda name, default=None: getattr(transaction, name, default)
    body = str(get("paragraph_markdown", "") or "")
    if not body:
        return transaction

    declarations = _transaction_declarations(get)
    existing = _transaction_witness_keys(get)

    constraints = _witness_constraints_from_plan_row(plan_row)
    packages = tuple(item for item in formula_packages if isinstance(item, Mapping))
    package_by_id, package_by_obligation = _formula_package_indexes(packages)

    def _select_unique_witness(
        *,
        local: Mapping[str, Any],
        package: Mapping[str, Any] | None,
    ) -> str:
        has_local_contract = bool(
            local.get("exact")
            or (
                str(local.get("semantic_atom") or "").strip()
                and str(local.get("semantic_atom") or "").strip().casefold()
                not in {"formal expression", "formula"}
            )
            or local.get("conditions")
            or str(local.get("polarity") or "unknown").strip().casefold()
            not in {"", "unknown"}
        )
        if package is None and not has_local_contract:
            return ""
        values: list[str] = []
        if package is not None:
            values.extend((
                str(package.get("markdown_block") or ""),
                str(package.get("latex") or ""),
            ))
        values.extend(local.get("exact", ()))
        values.append(str(local.get("semantic_atom", "") or ""))
        values.extend(local.get("conditions", ()))
        exact_values = tuple(
            dict.fromkeys(value for value in (
                str(item or "").strip() for item in values
            ) if value)
        )
        # Stage B starts with exact contract/package anchors only.  A
        # paraphrased sentence is intentionally left for the low-temperature
        # metadata Binder; broad sentence selection here would make the
        # deterministic path bind the same generic paragraph to unrelated
        # targets.
        candidates = exact_values
        anchors = _binding_anchors(local)
        for raw in candidates:
            candidate = str(raw or "").strip()
            if not candidate or body.count(candidate) != 1:
                continue
            if package is not None and candidate not in {
                str(package.get("markdown_block") or "").strip(),
                str(package.get("latex") or "").strip(),
            }:
                continue
            if anchors and not _anchor_compatible(candidate, body, anchors):
                continue
            if not _witness_satisfies_constraints(candidate, local):
                continue
            if package is not None and not _DISPLAY_MATH_RE.search(body):
                continue
            return candidate
        return ""

    additions: list[dict[str, str]] = []
    for kind, target_ids in declarations.items():
        for target_id in target_ids:
            if (kind, target_id) in existing:
                continue
            values: list[str] = []
            if kind == "formula":
                package = package_by_id.get(target_id) or package_by_obligation.get(target_id)
                if package is not None:
                    values.extend((
                        str(package.get("markdown_block") or ""),
                        str(package.get("latex") or ""),
                    ))
            local = constraints.get((kind, target_id), {})
            package = (
                _formula_package_for_target(
                    target_id,
                    package_by_id=package_by_id,
                    package_by_obligation=package_by_obligation,
                )
                if kind == "formula"
                else None
            )
            exact = _select_unique_witness(
                local=local,
                package=package,
            )
            if exact:
                additions.append({
                    "witness_kind": kind,
                    "target_id": target_id,
                    "exact_text": exact,
                })
    if additions:
        source["witnesses"] = [*(source.get("witnesses") or ()), *additions]
    if "unbound_target_ids" in source:
        source["unbound_target_ids"] = [
            f"{kind}:{target}"
            for kind, target_ids in declarations.items()
            for target in target_ids
            if not any(
                str(item.get("witness_kind") or "") == kind
                and str(item.get("target_id") or "") == target
                for item in source.get("witnesses") or ()
                if isinstance(item, Mapping)
            )
        ]
    if isinstance(transaction, Mapping):
        return source
    return transaction.__class__.model_validate(source)


def assess_paragraph_transaction(
    transaction: Mapping[str, Any] | Any,
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_routes: Mapping[str, Any] | None = None,
    required_anchors: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
) -> ParagraphTransactionAssessmentV1:
    """Assess exact declaration, witness, route, and optional semantic anchors.

    ``required_anchors`` is deliberately supplied by the authority projection;
    this function never searches the repository or invents source terms.  An
    empty anchor list means that exact target/witness closure is the available
    check for that target, except that a declared target must still have a
    non-empty local contract anchor when one was supplied.
    """

    if isinstance(transaction, Mapping):
        get = transaction.get
    else:
        get = lambda name, default=None: getattr(transaction, name, default)
    paragraph_id = str(get("paragraph_id", "") or "").strip()
    body = str(get("paragraph_markdown", "") or "").strip()
    required = required_targets_from_plan_row(plan_row)
    declared = {
        kind: _ids(get(field, ()))
        for kind, field in (
            ("facet", "rendered_from_facet_ids"),
            ("field", "rendered_field_candidate_ids"),
            ("slot", "rendered_slot_ids"),
            ("edge", "rendered_edge_ids"),
            ("formula", "used_formula_package_ids"),
            ("claim", "used_claim_ids"),
            ("equation", "used_equation_ids"),
        )
    }
    invalid: list[str] = []
    witness_keys: set[tuple[str, str]] = set()
    witness_by_key: dict[tuple[str, str], str] = {}
    raw_witnesses = get("witnesses", ()) or ()
    for index, raw in enumerate(raw_witnesses):
        if isinstance(raw, Mapping):
            kind = str(raw.get("witness_kind") or raw.get("kind") or "").strip()
            target = str(raw.get("target_id") or "").strip()
            exact = str(raw.get("exact_text") or "")
        else:
            kind = str(getattr(raw, "witness_kind", "") or "").strip()
            target = str(getattr(raw, "target_id", "") or "").strip()
            exact = str(getattr(raw, "exact_text", "") or "")
        if not kind or not target or not exact:
            invalid.append(f"witness_missing_fields:{index}")
            continue
        key = (kind, target)
        if key in witness_keys:
            invalid.append(f"duplicate_witness:{kind}:{target}")
            continue
        if not body or body.count(exact) != 1:
            invalid.append(f"witness_not_unique_substring:{kind}:{target}")
        witness_keys.add(key)
        witness_by_key[key] = exact

    # A declared target is never evidence without an exact witness.
    for kind, values in declared.items():
        for target in values:
            if (kind, target) not in witness_keys:
                invalid.append(f"missing_exact_witness:{kind}:{target}")

    missing: dict[str, tuple[str, ...]] = {}
    witnessed: dict[str, tuple[str, ...]] = {}
    routes = formula_routes or {}
    routes_are_authoritative = formula_routes is not None
    for kind, values in required.items():
        if kind != "formula":
            seen = tuple(target for target in values if (kind, target) in witness_keys)
            witnessed[kind] = seen
            missing_values = tuple(target for target in values if target not in seen)
            if missing_values:
                missing[kind] = missing_values
            continue
        formula_witnessed: list[str] = []
        formula_missing: list[str] = []
        used_packages = set(declared.get("formula", ()))
        for obligation_id in values:
            package_ids = _route_package_ids(obligation_id, routes)
            # In the current transaction protocol a formula obligation is
            # satisfiable only through its explicit package route.  A model
            # cannot manufacture a formula witness by declaring the
            # obligation id when formalization produced no safe package.
            if routes_are_authoritative and not package_ids:
                formula_missing.append(obligation_id)
                continue
            valid_packages = used_packages.intersection(package_ids)
            if not valid_packages and ("formula", obligation_id) not in witness_keys:
                formula_missing.append(obligation_id)
                continue
            # Coverage is keyed by the plan's obligation id, while package
            # consumption remains observable through ``declared_by_kind``.
            # Keeping the two identifiers separate prevents a valid
            # package (``package:*``) from being mistaken for the required
            # obligation (``formula:*``) by the structural-exit gate.
            formula_witnessed.append(obligation_id)
            route = routes.get(obligation_id)
            route_map = route if isinstance(route, Mapping) else {}
            exact_latex = str(
                route_map.get("latex") or route_map.get("markdown_block") or ""
            ).strip()
            if exact_latex and exact_latex not in body:
                invalid.append(f"formula_body_missing_exact_latex:{obligation_id}")
            if not _DISPLAY_MATH_RE.search(body):
                invalid.append(f"formula_body_missing_display_math:{obligation_id}")
        witnessed[kind] = tuple(dict.fromkeys(formula_witnessed))
        if formula_missing:
            missing[kind] = tuple(formula_missing)

    semantic_failures: list[str] = []
    for (kind, target), anchors in (required_anchors or {}).items():
        if (kind, target) not in witness_keys:
            continue
        anchors = tuple(str(anchor).strip() for anchor in anchors if str(anchor).strip())
        witness = witness_by_key.get((kind, target), "")
        if anchors and not _anchor_compatible(witness, body, anchors):
            semantic_failures.append(f"semantic_anchor_missing:{kind}:{target}")
    for key, constraints in _witness_constraints_from_plan_row(plan_row).items():
        witness = witness_by_key.get(key)
        if witness is not None and not _witness_satisfies_constraints(witness, constraints):
            semantic_failures.append(
                f"condition_or_polarity_mismatch:{key[0]}:{key[1]}"
            )

    valid = bool(paragraph_id and body) and not invalid and not missing and not semantic_failures
    body_digest = _digest(body)
    return ParagraphTransactionAssessmentV1(
        paragraph_id=paragraph_id,
        valid=valid,
        required_by_kind=required,
        declared_by_kind=declared,
        witnessed_by_kind=witnessed,
        missing_by_kind=missing,
        invalid_witnesses=tuple(dict.fromkeys(invalid)),
        semantic_failures=tuple(dict.fromkeys(semantic_failures)),
        body_digest=body_digest,
    )


__all__ = [
    "ParagraphTransactionAssessmentV1",
    "assess_paragraph_transaction",
    "paragraph_binding_targets",
    "required_anchors_from_plan_row",
    "required_targets_from_plan_row",
    "validate_paragraph_binding_response",
]
