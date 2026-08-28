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
        "slot": _ids(row.get("ordered_semantic_slot_ids")),
        "edge": _ids(row.get("required_edge_ids")),
        "formula": _ids(row.get("formula_obligation_ids")),
    }


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
    check for that target.
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
        if anchors and not any(anchor in body for anchor in anchors):
            semantic_failures.append(f"semantic_anchor_missing:{kind}:{target}")

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
    "required_targets_from_plan_row",
]
