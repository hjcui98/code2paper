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
from typing import Any, Literal

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
_FORMULA_PLACEHOLDER_RE = re.compile(r"\[\[FORMULA:([A-Za-z0-9_.:-]+)\]\]")


def splice_formula_placeholders(
    markdown: str,
    packages: Any,
    *,
    required_package_ids: Any = (),
    allowed_package_ids: Any = None,
    require_all: bool = False,
) -> tuple[str, tuple[str, ...]]:
    """Replace formula placeholders with the stored display block verbatim.

    Formula text crosses the Writer boundary as a package-owned artifact, not
    as model-authored prose.  Unknown, duplicate, missing, or malformed
    package routes fail closed before Binder/transaction validation.  The
    replacement deliberately does not strip or normalize the package block.
    """

    rows = tuple(packages or ()) if not isinstance(packages, (str, bytes, Mapping)) else ()
    package_by_id: dict[str, Any] = {}
    failures: list[str] = []
    for package in rows:
        raw_package_id = (
            package.get("package_id", "") if isinstance(package, Mapping)
            else getattr(package, "package_id", "")
        )
        package_id = str(raw_package_id or "").strip()
        if not package_id:
            failures.append("formula_package_id_missing")
            continue
        if package_id in package_by_id:
            failures.append(f"formula_package_id_duplicate:{package_id}")
            continue
        package_by_id[package_id] = package

    required = {
        str(item).strip() for item in (required_package_ids or ())
        if str(item).strip()
    }
    allowed = None if allowed_package_ids is None else {
        str(item).strip() for item in (allowed_package_ids or ())
        if str(item).strip()
    }
    used: list[str] = []
    spans: list[tuple[int, int, str]] = []
    for match in _FORMULA_PLACEHOLDER_RE.finditer(str(markdown or "")):
        package_id = match.group(1).strip()
        if package_id not in package_by_id:
            failures.append(f"formula_placeholder_unknown_package:{package_id}")
            continue
        if allowed is not None and package_id not in allowed:
            failures.append(f"formula_placeholder_wrong_consumer:{package_id}")
            continue
        if package_id in used:
            failures.append(f"formula_placeholder_duplicate:{package_id}")
            continue
        used.append(package_id)
        spans.append((match.start(), match.end(), package_id))

    expected = required or (set(package_by_id) if require_all else set())
    missing = sorted(expected - set(used))
    failures.extend(f"formula_placeholder_missing:{package_id}" for package_id in missing)
    if failures:
        return str(markdown or ""), tuple(dict.fromkeys(failures))

    replacements: list[tuple[int, int, str]] = []
    for start, end, package_id in spans:
        package = package_by_id[package_id]
        block = (
            package.get("markdown_block") if isinstance(package, Mapping)
            else getattr(package, "markdown_block", "")
        )
        latex = (
            package.get("latex") if isinstance(package, Mapping)
            else getattr(package, "latex", "")
        )
        latex = str(latex or "").strip()
        from code2paper.agentic.formalization_agent import canonical_formula_markdown_block
        if latex:
            block = canonical_formula_markdown_block(latex)
        else:
            raw = str(block or "")
            match = _DISPLAY_MATH_RE.search(raw)
            if match:
                inner = match.group(0).strip()
                if inner.startswith("$$") and inner.endswith("$$"):
                    inner = inner[2:-2].strip()
                block = canonical_formula_markdown_block(inner) if inner else match.group(0)
            elif raw.strip():
                block = canonical_formula_markdown_block(raw)
            else:
                block = ""
        if not block.strip():
            failures.append(f"formula_package_block_empty:{package_id}")
            continue
        if not _DISPLAY_MATH_RE.search(block):
            failures.append(f"formula_package_block_not_display_math:{package_id}")
            continue
        replacements.append((start, end, block))
    if failures:
        return str(markdown or ""), tuple(dict.fromkeys(failures))
    result = str(markdown or "")
    for start, end, block in reversed(replacements):
        result = result[:start] + block + result[end:]
    return result, ()


insert_formula_blocks_verbatim = splice_formula_placeholders


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
    """Return conservative lexical forms for paragraph-local matching.

    Writer prose is allowed to paraphrase a MethodUnit, so ``embedding`` and
    ``embeddings`` (or ``formulate`` and ``formulation``) must be comparable.
    The matcher still keeps the raw token's identity and only removes a small
    set of productive English suffixes; it is not a general-purpose semantic
    similarity function and cannot authorize an unanchored target.
    """

    def forms(token: str) -> tuple[str, ...]:
        value = token.casefold()
        if value in _ANCHOR_STOPWORDS or (
            len(value) < 3 and not value.isdigit() and not value.startswith(("δ", "Δ"))
        ):
            return ()
        values = [value]
        # Split identifiers into stable lexical pieces as well as retaining
        # the identifier itself.  This lets a natural-language witness refer
        # to ``passage_id_embeddings`` without making the whole identifier a
        # required verbatim substring.
        for part in re.split(r"[_\-]+|(?<=[a-z])(?=[A-Z])", token):
            part = part.casefold()
            if part and part not in _ANCHOR_STOPWORDS and (
                len(part) >= 3 or part.isdigit() or part.startswith(("δ", "Δ"))
            ):
                values.append(part)

        # Keep stems deliberately shallow.  The raw form remains above, so a
        # short stem can only help when the surrounding target has enough
        # independent overlap to pass _anchor_compatible's ratio gate.
        for suffix in ("ization", "isation", "ation", "tion", "ment", "ing", "ers", "er", "ed", "es", "s"):
            if value.endswith(suffix) and len(value) - len(suffix) >= 4:
                values.append(value[:-len(suffix)])
                break
        aliases = {
            "compute": "compute",
            "computes": "compute",
            "computed": "compute",
            "computing": "compute",
            "computation": "compute",
            "calculate": "calculate",
            "calculates": "calculate",
            "calculated": "calculate",
            "calculating": "calculate",
            "normalize": "normalize",
            "normalizes": "normalize",
            "normalized": "normalize",
            "normalizing": "normalize",
            "normalization": "normalize",
            "concatenate": "concatenate",
            "concatenates": "concatenate",
            "concatenated": "concatenate",
            "concatenating": "concatenate",
            "concatenation": "concatenate",
            "reduce": "reduce",
            "reduces": "reduce",
            "reduced": "reduce",
            "reducing": "reduce",
            "reduction": "reduce",
            "average": "average",
            "averages": "average",
            "averaged": "average",
            "averaging": "average",
            "sort": "sort",
            "sorts": "sort",
            "sorted": "sort",
            "sorting": "sort",
            "branch": "branch",
            "branches": "branch",
            "branched": "branch",
            "branching": "branch",
            "return": "return",
            "returns": "return",
            "returned": "return",
            "returning": "return",
            "output": "output",
            "outputs": "output",
            "embedding": "embed",
            "embeddings": "embed",
            "embedded": "embed",
            "encodes": "encode",
            "encoded": "encode",
            "encoding": "encode",
            "encoders": "encode",
            "similarities": "similarity",
            "scores": "score",
            "weights": "weight",
            "passages": "passage",
            "documents": "document",
            "positions": "position",
            "enabled": "enable",
            "enables": "enable",
            "active": "enable",
            "activates": "enable",
            "yielding": "yield",
            "yields": "yield",
            "yielded": "yield",
            "additive": "add",
            "additively": "add",
            "add": "add",
            "adds": "add",
            "added": "add",
            "adding": "add",
            "addition": "add",
            "augment": "add",
            "augments": "add",
            "augmented": "add",
            "augmenting": "add",
            "combine": "combine",
            "combines": "combine",
            "combined": "combine",
            "combining": "combine",
            "control": "control",
            "controls": "control",
            "controlled": "control",
            "controlling": "control",
            "dimension": "dim",
            "dimensions": "dim",
            "yield": "return",
            "rerank": "rank",
            "reranking": "rank",
            "reranked": "rank",
            "reranker": "rank",
            "rerankers": "rank",
        }
        alias = aliases.get(value)
        if alias:
            values.append(alias)
        return tuple(dict.fromkeys(values))

    result: set[str] = set()
    for token in _SEMANTIC_TOKEN_RE.findall(str(value or "")):
        result.update(forms(token))
    return result


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


def _semantic_anchor_variants(semantic_atom: Any) -> tuple[str, ...]:
    """Return bounded reader-language projections for legacy semantic atoms.

    Older frozen MethodUnit plans serialized implementation operands directly
    into ``semantic_atom`` (for example ``src``, ``shared_out`` and
    ``dropout1``).  Those strings are closed sidecar metadata, but they are
    not words a Writer is expected to reproduce.  The projections below are
    deliberately pattern-gated and generic: they normalize only a known
    representation mismatch, while the original atom and all source-backed
    target ids remain part of the contract.
    """

    atom = str(semantic_atom or "").strip()
    if not atom or atom.casefold() in {"formal expression", "formula"}:
        return ()
    lowered = atom.casefold()
    tokens = _semantic_tokens(atom)
    variants: list[str] = []

    def add(value: str) -> None:
        value = " ".join(str(value or "").split()).strip()
        if value and value.casefold() != atom.casefold() and value not in variants:
            variants.append(value)

    # Legacy operation slots that exposed local variable names.
    if (
        "src" in tokens
        and {"shared", "dedicated", "dropout"}.issubset(tokens)
        and ("+" in lowered or "combine" in tokens or "combines" in tokens)
    ):
        add("attention dropout residual")
    if (
        "return" in tokens
        and ("attn" in tokens or "attention" in tokens)
        and "weight" in tokens
    ):
        add("return attention weights")

    # Facet atoms can also be longer than one prose sentence.  These compact
    # forms are activated only when several independent operation terms are
    # present, so a generic document-id sentence cannot satisfy them.
    if (
        "contrastive" in tokens
        and ("infonce" in tokens or {"info", "nce"}.issubset(tokens))
        and ("loss" in tokens or "objective" in tokens)
    ):
        add("contrastive InfoNCE loss")
    if (
        ("retriever" in tokens or "retrieve" in tokens or "retrieval" in tokens)
        and ("passage" in tokens or "embedding" in tokens or "embed" in tokens)
    ):
        # Keep the retriever marker itself in the compact form.  Adding
        # ``passage`` and ``embedding`` here lets an unrelated sentence about
        # passage embeddings satisfy a retriever facet because the tokenizer
        # intentionally emits both noun and stem aliases.
        add("dense retriever")
    if (
        "sinusoidal" in tokens
        and ("position" in tokens or "positional" in tokens)
        and ("encode" in tokens or "encoding" in tokens)
    ):
        if "structural" in tokens and ("augment" in tokens or "augmentation" in tokens):
            add("structural augmentation sinusoidal positional encoding")
        else:
            add("sinusoidal positional encoding")
    if "hybrid" in tokens and "attention" in tokens:
        add("hybrid attention")
        if {"transformer", "shared", "dedicated"}.issubset(tokens):
            add("transformer shared dedicated attention")
    if (
        "dedicated" in tokens
        and "attention" in tokens
        and "hybrid" not in tokens
        and ("masked" in tokens or "use" in tokens or "enable" in tokens)
    ):
        add("dedicated masked attention" if "masked" in tokens else "dedicated attention")
    if (
        "sinusoidal" not in tokens
        and
        ("position" in tokens or "positional" in tokens)
        and ("add" in tokens or "enable" in tokens)
        and ("encode" in tokens or "encoding" in tokens)
    ):
        add("position encoding")

    return tuple(variants)


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
            exact = _text_values(
                item.get("allowed_exact_excerpts")
                or item.get("exact_excerpts")
            )
            semantic_atom = str(item.get("semantic_atom") or "").strip()
            conditions = _text_values(
                item.get("required_conditions") or item.get("conditions")
            )
            polarity = str(
                item.get("required_polarity") or item.get("polarity") or "unknown"
            ).strip()
            paper_role = str(item.get("paper_role") or "").strip()
        else:
            kind = str(getattr(item, "target_kind", "") or "").strip()
            target_id = str(getattr(item, "target_id", "") or "").strip()
            exact = _text_values(
                getattr(item, "allowed_exact_excerpts", ())
                or getattr(item, "exact_excerpts", ())
            )
            semantic_atom = str(getattr(item, "semantic_atom", "") or "").strip()
            conditions = _text_values(
                getattr(item, "required_conditions", ())
                or getattr(item, "conditions", ())
            )
            polarity = str(
                getattr(item, "required_polarity", "")
                or getattr(item, "polarity", "")
                or "unknown"
            ).strip()
            paper_role = str(getattr(item, "paper_role", "") or "").strip()
        if not kind or not target_id:
            continue
        if isinstance(item, Mapping):
            required = bool(
                item.get(
                    "required",
                    True if "render_policy" not in item else item.get("render_policy") == "required",
                )
            )
        else:
            render_policy = getattr(item, "render_policy", "required")
            required = bool(getattr(item, "required", render_policy == "required"))
        result[(kind, target_id)] = {
            "exact": exact,
            "semantic_atom": semantic_atom,
            "conditions": conditions,
            "polarity": polarity,
            "paper_role": paper_role,
            "required": required,
            "source_anchor_ids": _text_values(
                (
                    item.get("source_anchor_ids")
                    or item.get("source_operation_ids")
                    or item.get("allowed_anchor_ids")
                )
                if isinstance(item, Mapping)
                else (
                    getattr(item, "source_anchor_ids", ())
                    or getattr(item, "source_operation_ids", ())
                    or getattr(item, "allowed_anchor_ids", ())
                )
            ),
        }
    raw_atoms = row.get("witness_atoms") or row.get("detail_witness_atoms") or ()
    for atom in raw_atoms:
        atom_id = str(atom.get("atom_id") if isinstance(atom, Mapping) else getattr(atom, "atom_id", "")).strip()
        detail_id = str(atom.get("detail_id") if isinstance(atom, Mapping) else getattr(atom, "detail_id", "")).strip()
        exact = _text_values(
            (
                atom.get("exact_excerpts")
                or atom.get("allowed_exact_excerpts")
            ) if isinstance(atom, Mapping) else (
                getattr(atom, "exact_excerpts", ())
                or getattr(atom, "allowed_exact_excerpts", ())
            )
        )
        semantic_atom = str(
            atom.get("semantic_anchor") if isinstance(atom, Mapping)
            else getattr(atom, "semantic_anchor", "")
        ).strip()
        conditions = _text_values(
            (
                atom.get("required_conditions")
                or atom.get("conditions")
            ) if isinstance(atom, Mapping) else (
                getattr(atom, "required_conditions", ())
                or getattr(atom, "conditions", ())
            )
        )
        polarity = str(
            (
                atom.get("required_polarity")
                or atom.get("polarity")
                or "unknown"
            ) if isinstance(atom, Mapping) else (
                getattr(atom, "required_polarity", "")
                or getattr(atom, "polarity", "")
                or "unknown"
            )
        ).strip()
        paper_role = str(atom.get("atom_kind") if isinstance(atom, Mapping) else getattr(atom, "atom_kind", "")).strip()
        if isinstance(atom, Mapping):
            required = bool(
                atom.get(
                    "required",
                    True if "render_policy" not in atom else atom.get("render_policy") == "required",
                )
            )
        else:
            render_policy = getattr(atom, "render_policy", "required")
            required = bool(getattr(atom, "required", render_policy == "required"))
        if atom_id:
            result[("atom", atom_id)] = {
                "exact": exact,
                "semantic_atom": semantic_atom,
                "conditions": conditions,
                "polarity": polarity,
                "paper_role": paper_role,
                "detail_id": detail_id,
                "required": required,
                "source_anchor_ids": _text_values(
                    (
                        atom.get("source_anchor_ids")
                        or atom.get("source_operation_ids")
                    ) if isinstance(atom, Mapping) else (
                        getattr(atom, "source_anchor_ids", ())
                        or getattr(atom, "source_operation_ids", ())
                    )
                ),
            }
    for did in _ids(row.get("required_detail_ids")):
        result.setdefault(("detail", did), {
            "exact": (),
            "semantic_atom": "",
            "conditions": (),
            "polarity": "unknown",
            "paper_role": "detail",
            "source_anchor_ids": (),
        })
    return result


def _witness_satisfies_constraints(
    witness: str,
    constraints: Mapping[str, Any],
) -> bool:
    semantic_atom = str(constraints.get("semantic_atom") or "").strip()
    semantic_anchors = tuple(dict.fromkeys(
        (semantic_atom, *_semantic_anchor_variants(semantic_atom))
    ))
    if (
        semantic_atom
        and semantic_atom.casefold() not in {"formal expression", "formula"}
        and not _anchor_compatible(witness, "", semantic_anchors)
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
    ("detail", "rendered_detail_ids"),
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


def _formula_package_terminal_disposition(package: Mapping[str, Any]) -> str:
    """Return the one terminal formula state visible to downstream stages.

    A package with an author-intent or review-required lane remains a review
    item, not a Writer obligation.  Keeping this projection here prevents the
    assessment, trace, and replay diagnostics from independently deciding
    whether the same package is code-accepted.
    """

    review_status = str(package.get("review_status") or "").strip()
    authority_status = str(package.get("authority_status") or "").strip()
    formula_lane = str(package.get("formula_lane") or "").strip()
    if review_status == "rejected":
        return "failed"
    if review_status == "accepted" and (
        authority_status == "code_verified"
        and formula_lane == "repository_derived"
    ):
        return "accepted"
    if not review_status and authority_status in {"", "code_verified"} and formula_lane in {
        "", "repository_derived"
    }:
        # Pre-V2 frozen artifacts did not persist all three disposition
        # fields.  Preserve their accepted-package compatibility without
        # weakening the explicit current-state rules above.
        return "accepted"
    if review_status == "not_applicable":
        return "not_applicable"
    return "review_required"


def _formula_package_for_target(
    target_id: str,
    *,
    package_by_id: Mapping[str, Mapping[str, Any]],
    package_by_obligation: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    return package_by_id.get(target_id) or package_by_obligation.get(target_id)


def _formula_package_for_source_fact_target(
    target_id: str,
    *,
    local: Mapping[str, Any],
    paragraph_id: str,
    packages: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any] | None:
    """Return one accepted formula package that also proves a slot/edge.

    A formula block may be the only exact rendered representation of an
    operation slot.  Recovering that representation is safe only when the
    target names the exact source fact bound by one accepted repository
    package, that package has one owner paragraph, and the local semantic atom
    overlaps the package symbols.  This is deliberately narrower than normal
    semantic matching: a formula is never allowed to satisfy an unrelated
    slot merely because both occur in the same paragraph.
    """

    value = str(target_id or "").strip()
    if not value or not value.startswith(("slot:", "edge:")):
        return None
    source_fact_id = value.split(":", 1)[1].strip()
    if not source_fact_id.startswith("fact-"):
        return None
    semantic_atom = str(local.get("semantic_atom") or "").strip()
    semantic_tokens = _semantic_tokens(semantic_atom)
    if not semantic_tokens or not semantic_tokens.intersection({
        "compute", "calculation", "formula", "equation", "loss", "log",
        "sum", "exp", "similarity", "sim", "score", "rank",
    }):
        return None

    matches: list[Mapping[str, Any]] = []
    for package in packages:
        if str(package.get("authority_status") or "").strip() != "code_verified":
            continue
        if str(package.get("formula_lane") or "").strip() != "repository_derived":
            continue
        if str(package.get("review_status") or "").strip() != "accepted":
            continue
        consumer = str(package.get("consumer_paragraph_id") or "").strip()
        if not consumer or consumer != paragraph_id:
            continue
        if source_fact_id not in _ids(package.get("bound_fact_ids")):
            continue
        block = str(package.get("markdown_block") or "").strip()
        latex = str(package.get("latex") or "").strip()
        if not block or not _DISPLAY_MATH_RE.search(block):
            continue
        formula_tokens = _semantic_tokens(f"{block} {latex}")
        if len(semantic_tokens.intersection(formula_tokens)) < 2:
            continue
        matches.append(package)
    return matches[0] if len(matches) == 1 else None


def _binding_anchors(constraints: Mapping[str, Any]) -> tuple[str, ...]:
    """Project exact, semantic, and condition anchors for both Binder stages."""

    values = list(_text_values(constraints.get("exact")))
    semantic_atom = str(constraints.get("semantic_atom") or "").strip()
    if semantic_atom and semantic_atom.casefold() not in {"formal expression", "formula"}:
        values.append(semantic_atom)
        values.extend(_semantic_anchor_variants(semantic_atom))
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
    """Resolve an unbound id in the closed target set.

    Models sometimes omit the kind prefix even though the same target was
    supplied in a typed contract.  Recover that representation only when the
    bare id maps to exactly one closed target; a bare id shared by two kinds
    remains invalid rather than being guessed.
    """

    raw_value = str(value or "").strip()
    kind, separator, target_id = raw_value.partition(":")
    if not separator:
        bare_matches = tuple(
            key for key in target_keys
            if key[1] == raw_value
        )
        return bare_matches[0] if len(bare_matches) == 1 else None
    direct = _resolve_binding_target_key(kind, target_id, target_keys)
    if direct is not None:
        return direct

    # Edge declarations use witness kind ``edge`` but their stable ids use
    # the repository relation prefix ``rel:``.  The Binder commonly reports
    # that id directly (``rel:...``).  Accept it only when the complete value
    # is already the target id of exactly one declared target.
    matches = tuple(dict.fromkeys(
        key for key in target_keys if key[1] == raw_value
    ))
    return matches[0] if len(matches) == 1 else None


def paragraph_binding_targets(
    transaction: Mapping[str, Any] | Any,
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_packages: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    """Return local contracts still eligible for a metadata-only Binder.

    The Writer is not the authority for the paragraph's internal ids.  The
    paragraph plan/MethodUnit sidecar supplies the closed required-target set;
    Writer declarations are only additional representation proposals.  A
    Binder can attach a witness to a supplied target, but it cannot invent a
    target or turn an unanchored id into evidence. Targets without a local
    semantic contract (and without an exact formula package) are deliberately
    omitted so a malformed sidecar remains fail-closed.
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
    packages = tuple(item for item in formula_packages if isinstance(item, Mapping))
    package_by_id, package_by_obligation = _formula_package_indexes(packages)
    rows: list[dict[str, Any]] = []
    candidate_targets: list[tuple[str, str]] = []

    # Required non-formula targets are restored from the paragraph sidecar,
    # even when the Writer omitted their private ids.  The slot projection is
    # intentionally the publication set; support slots remain in
    # ordered_semantic_slot_ids for the Writer but are not hard prose targets.
    required = required_targets_from_plan_row(plan_row)
    for kind, target_ids in required.items():
        for target_id in target_ids:
            if kind == "formula":
                package = package_by_obligation.get(target_id)
                package_id = str(package.get("package_id") or "").strip() if package else ""
                if package_id:
                    candidate_targets.append((kind, package_id))
                continue
            candidate_targets.append((kind, target_id))
    # V3 detail contracts carry deterministic atom obligations separately from
    # the externally declared detail id.  Expose those atoms to the Binder so
    # omitted Writer metadata cannot make a detail appear complete by id alone.
    candidate_targets.extend(
        key for key in constraints
        if key[0] == "atom" and constraints[key].get("required", True)
    )

    # A Writer declaration is only a proposal.  Keep it in the Binder's
    # closed input when it names a sidecar-required target (or an already
    # witnessed target for a legacy transaction); never let a sibling or
    # invented id expand the paragraph contract.  In particular, a section
    # response can contain ids from another paragraph because its structured
    # schema is shared by all paragraph items.
    required_keys: set[tuple[str, str]] = set()
    for kind, target_ids in required.items():
        for target_id in target_ids:
            required_keys.add((kind, target_id))
            if kind == "formula":
                package = package_by_obligation.get(target_id)
                package_id = str(package.get("package_id") or "").strip() if package else ""
                if package_id:
                    required_keys.add((kind, package_id))
    # Small legacy/unit-test plan rows may carry the complete sidecar only as
    # ``witness_contract.targets`` and omit the denormalized required_* lists.
    # Those typed contract entries are still closed authority; they are not a
    # license to accept arbitrary Writer declarations.
    required_keys.update(
        key for key, local in constraints.items()
        if key[0] != "atom" or local.get("required", True)
    )
    for kind, target_ids in declarations.items():
        for target_id in target_ids:
            key = (kind, target_id)
            if key in required_keys or key in existing:
                candidate_targets.append((kind, target_id))

    seen_candidates: set[tuple[str, str]] = set()
    paragraph_id = str(get("paragraph_id", "") or "").strip()
    for kind, target_id in candidate_targets:
        key = (kind, target_id)
        if key in seen_candidates or key in existing:
            continue
        seen_candidates.add(key)
        local = constraints.get(key, {})
        package = (
            _formula_package_for_target(
                target_id,
                package_by_id=package_by_id,
                package_by_obligation=package_by_obligation,
            )
            if kind == "formula"
            else _formula_package_for_source_fact_target(
                target_id,
                local=local,
                paragraph_id=paragraph_id,
                packages=packages,
            )
        )
        if package is not None:
            consumer = str(package.get("consumer_paragraph_id") or "").strip()
            if consumer and paragraph_id and consumer != paragraph_id:
                package = None
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
            "paper_role": str(local.get("paper_role") or ""),
            "required_conditions": list(local.get("conditions") or ()),
            "required_polarity": str(local.get("polarity") or "unknown"),
            "required": bool(local.get("required", True)),
            "detail_id": str(local.get("detail_id") or ""),
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

    def _detail_atom_complete(detail_id: str) -> bool:
        atom_keys = {
            (
                str(row.get("witness_kind") or ""),
                str(row.get("target_id") or ""),
            )
            for row in target_rows
            if (
                row.get("witness_kind") == "atom"
                and str(row.get("detail_id") or "") == detail_id
                and row.get("required", True)
            )
        }
        return bool(atom_keys) and atom_keys.issubset(seen)

    for kind, target_id in sorted(target_keys - reported):
        if kind == "detail" and _detail_atom_complete(target_id):
            # Detail/Atom mode uses the atom witnesses as the lossless
            # semantic proof.  Requiring a second aggregate sentence would
            # make the contract impossible for a one-sentence detail.
            continue
        errors.append(f"binder_target_unreported:{kind}:{target_id}")
    return tuple(valid), tuple(dict.fromkeys(errors)), tuple(unbound_values)


class ParagraphTransactionAssessmentV1(BaseModel):
    """Deterministic result for one planned paragraph transaction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    paragraph_id: str
    section_id: str = ""
    status: Literal["not_run", "blocked", "invalid", "valid"] = "not_run"
    valid: bool = False
    required_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    declared_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    witnessed_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    missing_by_kind: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    invalid_witnesses: tuple[str, ...] = ()
    semantic_failures: tuple[str, ...] = ()
    ordered_semantic_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    target_source_fact_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    target_source_span_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    formula_package_ids_by_obligation: dict[str, tuple[str, ...]] = Field(
        default_factory=dict
    )
    formula_terminal_dispositions_by_obligation: dict[str, str] = Field(
        default_factory=dict
    )
    required_conditions_by_target: dict[str, tuple[str, ...]] = Field(
        default_factory=dict
    )
    required_polarity_by_target: dict[str, str] = Field(default_factory=dict)
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
    detail_ids = _ids(row.get("required_detail_ids"))
    if detail_ids:
        return {
            "detail": detail_ids,
            "formula": _ids(row.get("formula_obligation_ids") or row.get("formula_package_ids")),
        }
    return {
        "facet": _ids(row.get("required_facet_ids")),
        "field": _ids(row.get("required_field_candidate_ids")),
        # ``support_slot_ids`` must remain in the ordered MethodUnit closure,
        # but only ``required_publication_slot_ids`` are hard prose
        # obligations.  A frozen pre-split row has no publication field and
        # therefore falls back to its ordered slots for compatibility; an
        # explicit empty publication list is meaningful and must not promote
        # support-only atoms into required prose targets.  MethodUnit-era
        # dumps may omit that empty list; presence of support/field keys
        # still means publication slots were split and must stay empty.
        "slot": _publication_slot_ids(row),
        "edge": _ids(row.get("required_edge_ids")),
        "formula": _ids(row.get("formula_obligation_ids")),
    }


def _publication_slot_ids(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Hard Candidate slots: never promote ordered support slots past an empty pub list."""

    if "required_publication_slot_ids" in row:
        return _ids(row.get("required_publication_slot_ids"))
    if "support_slot_ids" in row or "required_field_candidate_ids" in row:
        return _ids(row.get("required_publication_slot_ids"))
    return _ids(row.get("ordered_semantic_slot_ids"))


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
            values.extend(_semantic_anchor_variants(semantic_atom))
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
    existing_witness_texts = {
        str(raw.get("exact_text") or "").strip()
        for raw in (get("witnesses", ()) or ())
        if isinstance(raw, Mapping) and str(raw.get("exact_text") or "").strip()
    }

    constraints = _witness_constraints_from_plan_row(plan_row)
    packages = tuple(item for item in formula_packages if isinstance(item, Mapping))
    package_by_id, package_by_obligation = _formula_package_indexes(packages)
    paragraph_id = str(get("paragraph_id", "") or "").strip()

    def _select_unique_witness(
        *,
        target_kind: str,
        local: Mapping[str, Any],
        package: Mapping[str, Any] | None,
        allow_semantic_fallback: bool,
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
        semantic_atom = str(local.get("semantic_atom") or "").strip()
        semantic_fallback_anchors = tuple(dict.fromkeys(
            (
                semantic_atom,
                *_semantic_anchor_variants(semantic_atom),
            )
            if semantic_atom
            and semantic_atom.casefold() not in {"formal expression", "formula"}
            else anchors
        ))
        for raw in candidates:
            candidate = str(raw or "").strip()
            if not candidate or body.count(candidate) != 1:
                continue
            # The canonical package block may prove both the owning formula
            # and its source-fact slot.  Reuse the exact same substring only
            # for the strict package-backed slot/edge path; ordinary prose
            # witnesses remain unique across targets.
            if candidate in existing_witness_texts and not (
                package is not None and target_kind in {"slot", "edge"}
            ):
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
        # When the Writer omits internal ids, the harness may recover one
        # target from an existing semantic anchor.  Select only a unique
        # sentence-level match; never bind an entire paragraph or choose
        # among several plausible sentences.
        if (
            package is None
            and target_kind in {"facet", "field", "slot", "edge"}
            and semantic_fallback_anchors
            and allow_semantic_fallback
        ):
            # One reader sentence may legitimately satisfy two closed
            # contracts (for example a pipeline sentence can state both the
            # high-level formula context and retrieval).  Existing witness
            # text is therefore not a uniqueness constraint across target
            # ids; uniqueness is enforced per sentence and per target below.
            # Formula blocks are package-owned text and must not compete with
            # prose anchors.  Remove complete blocks before sentence
            # splitting, retaining a newline boundary so prose immediately
            # before and after a display equation remains independently
            # recoverable as an exact substring of the original body.
            prose_body = _DISPLAY_MATH_RE.sub("\n", body)
            sentences = tuple(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+|\n+", prose_body)
                if sentence.strip()
            )
            semantic_matches: list[tuple[float, int, str, str]] = []
            for sentence in sentences:
                if (
                    body.count(sentence) != 1
                    or not _witness_satisfies_constraints(sentence, local)
                ):
                    continue
                sentence_tokens = _semantic_tokens(sentence)
                if not sentence_tokens:
                    continue
                best_score = 0.0
                best_overlap = 0
                best_anchor = ""
                for raw_anchor in semantic_fallback_anchors:
                    anchor_tokens = _semantic_tokens(raw_anchor)
                    if not anchor_tokens:
                        continue
                    overlap = len(sentence_tokens.intersection(anchor_tokens))
                    if overlap < 2:
                        continue
                    # Prefer coverage of the authorized semantic atom while
                    # retaining a precision term so a generic long sentence
                    # cannot win merely by containing two common words.
                    score = (
                        0.75 * overlap / max(1, len(anchor_tokens))
                        + 0.25 * overlap / max(1, len(sentence_tokens))
                    )
                    if score > best_score:
                        best_score = score
                        best_overlap = overlap
                        best_anchor = raw_anchor
                # Slots and edges are also recoverable from the paragraph's
                # closed semantic contract, but require three overlapping
                # lexical forms.  This keeps a short generic sentence from
                # binding an implementation target while allowing ordinary
                # prose to witness a paraphrased operation.
                minimum_score = 0.34 if target_kind in {"slot", "edge"} else 0.38
                minimum_overlap = 3 if target_kind in {"slot", "edge"} else 2
                if (
                    best_overlap >= minimum_overlap
                    and best_score >= minimum_score
                    and _anchor_compatible(sentence, body, semantic_fallback_anchors)
                ):
                    semantic_matches.append((best_score, best_overlap, sentence, best_anchor))
            semantic_matches.sort(key=lambda item: (-item[0], -item[1], item[2]))
            if semantic_matches:
                top = semantic_matches[0]
                second_score = semantic_matches[1][0] if len(semantic_matches) > 1 else 0.0
                second_overlap = semantic_matches[1][1] if len(semantic_matches) > 1 else 0
                # A uniquely strongest sentence is a representation recovery;
                # a near tie remains unbound for the dedicated Binder instead
                # of guessing which sentence carries the target.
                raw_semantic_atom = str(local.get("semantic_atom") or "").strip()
                derived_anchors = set(_semantic_anchor_variants(raw_semantic_atom))
                # A legacy frozen slot can have a specific raw atom such as
                # ``enable use dedicated attention attend``.  Its reader
                # sentence may lose one implementation word and therefore
                # score only slightly above a sibling sentence that happens
                # to contain the compact derived anchor.  Prefer the raw
                # atom only when it is itself specific and has at least two
                # more authorized terms; this closes that representation
                # mismatch without turning generic overlap into a guess.
                raw_specificity_recovery = (
                    len(_semantic_tokens(raw_semantic_atom)) >= 5
                    and top[3].casefold() == raw_semantic_atom.casefold()
                    and top[1] >= second_overlap + 2
                    and top[0] > second_score
                )
                if (
                    top[0] - second_score >= 0.05
                    or raw_specificity_recovery
                    or (
                        len(semantic_matches) > 1
                        and top[3] in derived_anchors
                        and top[3] == semantic_matches[1][3]
                    )
                    or (
                        len(semantic_matches) > 1
                        and top[3] not in derived_anchors
                        and top[1] >= 3 * max(1, semantic_matches[1][1])
                    )
                ):
                    return top[2]
        return ""

    additions: list[dict[str, str]] = []
    required = required_targets_from_plan_row(plan_row)
    required_keys: set[tuple[str, str]] = set()
    for kind, target_ids in required.items():
        for target_id in target_ids:
            required_keys.add((kind, target_id))
            if kind == "formula":
                package = package_by_obligation.get(target_id)
                package_id = str(package.get("package_id") or "").strip() if package else ""
                if package_id:
                    required_keys.add((kind, package_id))
    required_keys.update(constraints)
    # A formula package is a closed section-sidecar contract even in a
    # legacy frozen row that omitted formula_obligation_ids. Preserve a
    # Writer declaration only for the package's owning paragraph; the exact
    # package block is still required before a witness can be added.
    for package in packages:
        package_id = str(package.get("package_id") or "").strip()
        consumer_id = str(package.get("consumer_paragraph_id") or "").strip()
        if package_id and (not consumer_id or consumer_id == paragraph_id):
            required_keys.add(("formula", package_id))
    # Preserve a required self-report until assessment so it remains a
    # visible ``missing_exact_witness`` failure; discard only declarations
    # outside the sidecar contract.  This is the representation-only repair
    # that prevents a model from selecting a sibling paragraph's slot.
    candidate_declarations = {
        kind: [
            target_id for target_id in target_ids
            if (kind, target_id) in required_keys or (kind, target_id) in existing
        ]
        for kind, target_ids in declarations.items()
    }
    candidate_targets: list[tuple[str, str, str]] = []
    for kind, target_ids in required.items():
        for required_id in target_ids:
            if kind == "detail" and any(
                atom_kind == "atom"
                and local.get("detail_id") == required_id
                and local.get("required", True)
                for (atom_kind, _atom_id), local in constraints.items()
            ):
                # A Detail with a required atom contract is witnessed by its
                # complete atom set.  Do not select one generic aggregate
                # sentence first and thereby prevent the atoms from getting
                # their own exact witnesses.
                continue
            target_id = required_id
            if kind == "formula":
                package = package_by_obligation.get(required_id)
                target_id = str(package.get("package_id") or "").strip() if package else ""
                if not target_id:
                    # An unresolved formula obligation remains unresolved; it
                    # must not be converted into a declaration by the Writer.
                    continue
            if target_id:
                candidate_targets.append((kind, target_id, required_id))
    candidate_targets.extend(
        (kind, target_id, target_id)
        for kind, target_id in constraints
        if kind == "atom" and constraints[(kind, target_id)].get("required", True)
    )
    for kind, target_ids in declarations.items():
        candidate_targets.extend(
            (kind, target_id, target_id)
            for target_id in target_ids
            if (kind, target_id) in required_keys or (kind, target_id) in existing
        )
    seen_candidates: set[tuple[str, str]] = set()
    for kind, target_id, _required_id in candidate_targets:
        if (kind, target_id) in seen_candidates:
            continue
        seen_candidates.add((kind, target_id))
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
            else _formula_package_for_source_fact_target(
                target_id,
                local=local,
                paragraph_id=paragraph_id,
                packages=packages,
            )
        )
        exact = _select_unique_witness(
            target_kind=kind,
            local=local,
            package=package,
            # An omitted id is the normal sidecar-recovery case.  When the
            # Writer explicitly proposes a required target, leave a
            # paraphrase for the dedicated Binder (the existing exact-witness
            # test and its bounded retry depend on that distinction).  A
            # declaration-only extra never reaches this loop.
            allow_semantic_fallback=(
                (kind, target_id) in required_keys
                and target_id not in declarations.get(kind, ())
            ),
        )
        if exact:
            if target_id not in candidate_declarations.setdefault(kind, []):
                candidate_declarations[kind].append(target_id)
            additions.append({
                "witness_kind": kind,
                "target_id": target_id,
                "exact_text": exact,
            })
            existing.add((kind, target_id))
            existing_witness_texts.add(exact)
    if additions:
        source["witnesses"] = [*(source.get("witnesses") or ()), *additions]
    declaration_fields = dict(_TRANSACTION_DECLARATION_FIELDS)
    for kind, values in candidate_declarations.items():
        field_name = declaration_fields.get(kind)
        if field_name:
            if not isinstance(transaction, Mapping) and field_name not in getattr(transaction.__class__, "model_fields", {}):
                continue
            source[field_name] = list(dict.fromkeys(values))
    if "unbound_target_ids" in source:
        witness_keys = {
            (
                str(item.get("witness_kind") or "").strip(),
                str(item.get("target_id") or "").strip(),
            )
            for item in source.get("witnesses") or ()
            if isinstance(item, Mapping)
            and str(item.get("witness_kind") or "").strip()
            and str(item.get("target_id") or "").strip()
        }

        def _detail_atom_complete(detail_id: str) -> bool:
            atom_keys = {
                (atom_kind, atom_id)
                for (atom_kind, atom_id), local in constraints.items()
                if (
                    atom_kind == "atom"
                    and local.get("detail_id") == detail_id
                    and local.get("required", True)
                )
            }
            return bool(atom_keys) and atom_keys.issubset(witness_keys)

        source["unbound_target_ids"] = [
            f"{kind}:{target}"
            for kind, target_ids in declarations.items()
            for target in target_ids
            if not (kind == "detail" and _detail_atom_complete(target))
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
    declared = _transaction_declarations(get)
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
                # Detail/Atom contracts permit the Binder to witness a Detail
                # through the complete set of owned atom witnesses.  The
                # aggregate detail id remains useful for routing and is not a
                # second prose substring requirement.
                if kind == "detail":
                    detail_atoms = [
                        (atom_kind, atom_target)
                        for (atom_kind, atom_target), constraint in _witness_constraints_from_plan_row(plan_row).items()
                        if (
                            atom_kind == "atom"
                            and constraint.get("detail_id") == target
                            and constraint.get("required", True)
                        )
                    ]
                    if detail_atoms and all(atom_key in witness_keys for atom_key in detail_atoms):
                        continue
                invalid.append(f"missing_exact_witness:{kind}:{target}")

    missing: dict[str, tuple[str, ...]] = {}
    witnessed: dict[str, tuple[str, ...]] = {}
    routes = formula_routes or {}
    routes_are_authoritative = formula_routes is not None
    if routes_are_authoritative:
        # A review-required/not-applicable Formalizer result is a terminal
        # state for the formula lane, but it is not a required accepted-code
        # target for this paragraph transaction.  Keep the obligation and its
        # route in the sidecar below; remove only the downstream hard target
        # so Binder/Writer cannot be asked to consume a non-accepted package.
        required["formula"] = tuple(
            obligation_id
            for obligation_id in required["formula"]
            if str(
                routes.get(obligation_id, {}).get("terminal_disposition", "")
                if isinstance(routes.get(obligation_id), Mapping) else ""
            ).strip()
            not in {"review_required", "not_applicable"}
        )
    constraints_by_key = _witness_constraints_from_plan_row(plan_row)
    for kind, values in required.items():
        if kind == "detail":
            missing_details: list[str] = []
            witnessed_details: list[str] = []
            for did in values:
                detail_atoms = [
                    (k, t) for (k, t), c in constraints_by_key.items()
                    if (
                        k == "atom"
                        and c.get("detail_id") == did
                        and c.get("required", True)
                    )
                ]
                if ("detail", did) in witness_keys and (
                    not detail_atoms
                    or all((k, t) in witness_keys for (k, t) in detail_atoms)
                ):
                    witnessed_details.append(did)
                elif detail_atoms and all((k, t) in witness_keys for (k, t) in detail_atoms):
                    witnessed_details.append(did)
                else:
                    missing_details.append(did)
            witnessed[kind] = tuple(witnessed_details)
            if missing_details:
                missing[kind] = tuple(missing_details)
            continue
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
    row = plan_row if isinstance(plan_row, Mapping) else {}
    source_fact_ids: dict[str, tuple[str, ...]] = {}
    source_span_ids: dict[str, tuple[str, ...]] = {}
    conditions_by_target: dict[str, tuple[str, ...]] = {}
    polarity_by_target: dict[str, str] = {}
    for (kind, target), local in _witness_constraints_from_plan_row(plan_row).items():
        target_key = f"{kind}:{target}"
        anchors = tuple(local.get("source_anchor_ids") or ())
        facts = tuple(dict.fromkeys(
            anchor for anchor in anchors
            if str(anchor).startswith("fact-")
        ))
        if kind in {"slot", "edge"} and target.startswith(f"{kind}:fact-"):
            facts = tuple(dict.fromkeys((*facts, target.split(":", 1)[1])))
        spans = tuple(dict.fromkeys(
            anchor for anchor in anchors
            if str(anchor).startswith(("span:", "span-", "direct:", "l2:"))
        ))
        if facts:
            source_fact_ids[target_key] = facts
        if spans:
            source_span_ids[target_key] = spans
        if local.get("conditions"):
            conditions_by_target[target_key] = tuple(local["conditions"])
        polarity = str(local.get("polarity") or "unknown").strip()
        if polarity and polarity.casefold() != "unknown":
            polarity_by_target[target_key] = polarity
    formula_package_ids_by_obligation = {
        str(obligation_id): _ids(
            route.get("package_ids") if isinstance(route, Mapping) else route
        )
        for obligation_id, route in routes.items()
        if str(obligation_id).strip()
    }
    formula_terminal_dispositions = {
        str(obligation_id): str(
            route.get("terminal_disposition") or "accepted"
            if isinstance(route, Mapping) else "accepted"
        ).strip()
        for obligation_id, route in routes.items()
        if str(obligation_id).strip()
    }
    body_digest = _digest(body)
    return ParagraphTransactionAssessmentV1(
        paragraph_id=paragraph_id,
        section_id=str(row.get("section_id") or "").strip(),
        status="valid" if valid else "invalid" if body else "not_run",
        valid=valid,
        required_by_kind=required,
        declared_by_kind=declared,
        witnessed_by_kind=witnessed,
        missing_by_kind=missing,
        invalid_witnesses=tuple(dict.fromkeys(invalid)),
        semantic_failures=tuple(dict.fromkeys(semantic_failures)),
        ordered_semantic_slot_ids=_ids(row.get("ordered_semantic_slot_ids")),
        target_source_fact_ids=source_fact_ids,
        target_source_span_ids=source_span_ids,
        formula_package_ids_by_obligation=formula_package_ids_by_obligation,
        formula_terminal_dispositions_by_obligation=formula_terminal_dispositions,
        required_conditions_by_target=conditions_by_target,
        required_polarity_by_target=polarity_by_target,
        body_digest=body_digest,
    )


__all__ = [
    "ParagraphTransactionAssessmentV1",
    "assess_paragraph_transaction",
    "insert_formula_blocks_verbatim",
    "paragraph_binding_targets",
    "required_anchors_from_plan_row",
    "required_targets_from_plan_row",
    "splice_formula_placeholders",
    "validate_paragraph_binding_response",
]
