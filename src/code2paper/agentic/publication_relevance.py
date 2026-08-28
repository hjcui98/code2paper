"""Publication-relevance writing roles (plan 19.5.4 / acceptance review B).

A small, closed three-way writing role for Method propositions:

- ``method_positive``: central input, representation, transformation,
  objective, output, active/default path, or a scientifically meaningful
  configuration or formula;
- ``method_conditional``: a paper-level proposition whose truth changes under
  a material condition (configuration, training/inference mode, algorithm
  branch);
- ``audit_only``: defensive empty/None/shape checks, loop/index mechanics,
  cache/memory existence, logging/progress, serialization, and incidental
  helpers.

Roles are derived deterministically from the exact fact/relation context plus
the proposition surface, and they are project-neutral (no EBCAR/DyG/LinearRAG
paths, symbols, sentences, or known answers).  ``audit_only`` is content
selection, never claim filtering: the facts stay in evidence, atomic claims,
traceability and audit artifacts; they simply leave Writer sentence plans,
supported-unit recall denominators, and qualifier Rewrite triggers unless the
author story or the Architect's mainline explicitly selects the mechanism.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Literal

WritingRole = Literal["method_positive", "method_conditional", "audit_only"]

#: Predicates that are audit-only bookkeeping by default.
_AUDIT_ONLY_PREDICATES = frozenset({
    "writes_artifact",  # serialization / artifact persistence
    "loops",            # loop/index mechanics
})

#: Branch predicates whose object/guard decides audit vs material.
_BRANCH_PREDICATES = frozenset({"branches_on", "compares"})

#: High-precision defensive/bookkeeping term patterns (project-neutral).
_AUDIT_TERM_PATTERNS = (
    re.compile(r"\bshape\b"),
    re.compile(r"\blen\s*\("),
    re.compile(r"\bis\s+not\s+none\b"),
    re.compile(r"\bempty\b"),
    re.compile(r"\bcache\b"),
    re.compile(r"\bmemo(?:ry|ization)?\b"),
    re.compile(r"\b(log|logger|logging|progress|debug)\b"),
    re.compile(r"\bassert\b"),
    re.compile(r"\bdtype\b"),
    re.compile(r"\bdevice\b"),
    re.compile(r"\bplaceholder\b"),
    # Concept-level defensive/bookkeeping mechanics (project-neutral).
    re.compile(r"\bpad(?:ding)?\b"),
    re.compile(r"\bchunk\b"),
    re.compile(r"\bingest(?:ion)?\b"),
    re.compile(r"\b(?:index|indices|indexing)\b"),
    re.compile(r"\bcounter\b"),
    re.compile(r"\boffset\b"),
    re.compile(r"\bcase\s*study\b"),
    re.compile(r"\balong\s+dimension\b"),
    re.compile(r"\bdim(?:ension)?s?\s*[=:]\s*\d"),
)

_INDEX_OBJECT_PATTERN = re.compile(
    r"^(i|j|k|idx|index|indices|count|counter|offset)$"
)


def has_audit_term(*values: str) -> bool:
    """Whether any value carries a defensive/bookkeeping term (case-folded)."""

    lowered = " ".join(str(value) for value in values if value).casefold()
    return any(pattern.search(lowered) for pattern in _AUDIT_TERM_PATTERNS)


def _object_texts(raw_object: Any) -> tuple[str, ...]:
    if isinstance(raw_object, (list, tuple)):
        return tuple(str(item) for item in raw_object if str(item).strip())
    return (str(raw_object),) if str(raw_object).strip() else ()


def classify_fact_writing_role(fact: Any) -> WritingRole:
    """Deterministic writing role for one code fact (exact fact context).

    A guarded fact is ``method_conditional`` only when its condition is
    material; defensive shape/empty/None guards on branch/loop mechanics are
    ``audit_only``.
    """

    predicate = str(getattr(fact, "predicate", "") or "")
    conditions = tuple(
        str(item) for item in (getattr(fact, "conditions", ()) or ()) if str(item).strip()
    )
    objects = _object_texts(getattr(fact, "object", ""))
    if predicate in _AUDIT_ONLY_PREDICATES:
        return "audit_only"
    if predicate in _BRANCH_PREDICATES and has_audit_term(*conditions, *objects):
        return "audit_only"
    if conditions:
        return "method_conditional"
    return "method_positive"


def classify_claim_writing_role(
    claim: Any,
    *,
    facts_by_id: dict[str, Any] | None = None,
) -> WritingRole:
    """Writing role for one atomic/projected claim on the live product path.

    Bound facts, when present, are classified with
    ``classify_fact_writing_role``.  A claim backed only by audit-only facts
    (or whose own surface is a defensive shape/index/empty/debug assertion)
    is ``audit_only``.  Mechanism claims with material conditions stay
    ``method_conditional``; otherwise ``method_positive``.
    """

    facts_by_id = facts_by_id or {}
    bound_facts = [
        facts_by_id[str(fact_id)]
        for fact_id in (getattr(claim, "fact_ids", ()) or ())
        if str(fact_id) in facts_by_id
    ]
    if bound_facts:
        roles = tuple(classify_fact_writing_role(fact) for fact in bound_facts)
        if roles and all(role == "audit_only" for role in roles):
            return "audit_only"
        if any(role == "method_conditional" for role in roles):
            return "method_conditional"
        return "method_positive"
    surface = " ".join(str(value) for value in (
        getattr(claim, "canonical_text", ""),
        getattr(claim, "claim_text", ""),
        getattr(claim, "supported_fragment", ""),
        " ".join(str(item) for item in (getattr(claim, "required_qualifiers", ()) or ())),
    ) if str(value).strip())
    if has_audit_term(surface):
        return "audit_only"
    if getattr(claim, "required_qualifiers", ()) or ():
        return "method_conditional"
    return "method_positive"


def classify_proposition_writing_role(
    *,
    origin: str,
    conditions: Iterable[str],
    bound_fact_roles: Iterable[WritingRole] = (),
) -> WritingRole:
    """Deterministic writing role for a Method proposition.

    Author-intent propositions are story content by definition.  A
    proposition backed only by audit-only facts stays in evidence unless its
    own reader surface carries a material condition; otherwise the role comes
    from the proposition's material conditions.
    """

    roles = tuple(bound_fact_roles)
    condition_values = tuple(
        str(item) for item in conditions if str(item).strip()
    )
    if origin == "author_intent":
        return "method_positive"
    if roles and all(role == "audit_only" for role in roles):
        if condition_values and not has_audit_term(*condition_values):
            return "method_conditional"
        return "audit_only"
    if condition_values:
        return "method_conditional"
    return "method_positive"


def _span_overlap(left: str, right: str) -> bool:
    """Exact span binding: equal ids, or numeric range overlap on one path.

    Concept-card bindings pin ``span:<path>:<start>:<end>`` fragment refs;
    facts pin exact operation ranges on the same form.  A fact is bound to a
    concept only when its span actually intersects the card's bound span on
    the same file — never by file, obligation, or token proximity (plan
    19.5.3 / review Q1: no obligation-wide expansion).
    """

    def parsed(value: str) -> tuple[str, int, int] | None:
        parts = str(value or "").split(":")
        if len(parts) != 4 or parts[0] != "span":
            return None
        try:
            return parts[1], int(parts[2]), int(parts[3])
        except ValueError:
            return None

    if left == right:
        return True
    a = parsed(left)
    b = parsed(right)
    if a is None or b is None:
        return False
    if a[0] != b[0]:
        return False
    return a[1] <= b[2] and b[1] <= a[2]


def _concept_span_ids_by_key(concept_cards: Any) -> dict[str, tuple[str, ...]]:
    """Exact bound fragment spans per concept key (never obligation ids)."""

    spans_by_key: dict[str, list[str]] = {}
    for binding in (getattr(concept_cards, "bindings", ()) or ()):
        key = str(getattr(binding, "concept_key", "") or "")
        if not key:
            continue
        spans = spans_by_key.setdefault(key, [])
        for span in (getattr(binding, "source_span_ids", ()) or ()):
            if str(span).strip():
                spans.append(str(span).strip())
    return {key: tuple(dict.fromkeys(spans)) for key, spans in spans_by_key.items()}


def concept_bound_fact_ids(
    concept_cards: Any,
    concept_keys: Iterable[str],
    facts: Any,
) -> set[str]:
    """Exact Concept -> fact binding through bound fragment spans.

    A fact belongs to a concept only when at least one of its own spans
    (direct or relation) overlaps a span the concept binding pins.  Source
    obligation ids play no role in this projection.
    """

    keys = {str(key) for key in concept_keys if str(key).strip()}
    if not keys or concept_cards is None or facts is None:
        return set()
    spans_by_key = _concept_span_ids_by_key(concept_cards)
    bound_spans = {
        span for key in keys for span in spans_by_key.get(key, ())
    }
    if not bound_spans:
        return set()
    bound: set[str] = set()
    for fact in (getattr(facts, "facts", ()) or ()):
        fact_spans = [
            str(item)
            for item in (
                *(getattr(fact, "direct_span_ids", ()) or ()),
                *(getattr(fact, "relation_span_ids", ()) or ()),
            )
            if str(item).strip()
        ]
        if any(
            _span_overlap(span, bound_span)
            for span in fact_spans
            for bound_span in bound_spans
        ):
            bound.add(str(getattr(fact, "fact_id", "") or ""))
    return bound


def concept_bound_claim_ids(
    concept_cards: Any,
    concept_keys: Iterable[str],
    claims: Any,
    facts: Any,
) -> set[str]:
    """Exact Concept -> claim binding through the Concept -> fact projection.

    A claim belongs to a concept only when at least one of its facts is
    bound to the concept's exact spans.  No obligation expansion.
    """

    bound_fact_ids = concept_bound_fact_ids(concept_cards, concept_keys, facts)
    if not bound_fact_ids or claims is None:
        return set()
    return {
        str(getattr(claim, "claim_id", "") or "")
        for claim in (getattr(claims, "claims", ()) or ())
        if set(str(item) for item in (getattr(claim, "fact_ids", ()) or ()))
        & bound_fact_ids
    }


def concept_audit_claim_ids_exact(
    *,
    concept_cards: Any,
    audit_concept_keys: Iterable[str],
    claims: Any,
    facts: Any,
) -> set[str]:
    """Exact audit Concept -> claim exclusion (review Q1, no obligation-wide).

    A claim is excluded from Writer obligations / qualifier triggers only
    when EVERY fact it carries is bound to the exact bound spans of at least
    one audit-only concept card.  A scientifically material claim that merely
    shares a source obligation with an audit card is never hidden.
    """

    keys = {str(key) for key in audit_concept_keys if str(key).strip()}
    if not keys or concept_cards is None or claims is None or facts is None:
        return set()
    spans_by_key = _concept_span_ids_by_key(concept_cards)
    audit_spans = {
        span for key in keys for span in spans_by_key.get(key, ())
    }
    if not audit_spans:
        return set()
    fact_by_id = {
        str(getattr(fact, "fact_id", "") or ""): fact
        for fact in (getattr(facts, "facts", ()) or ())
    }
    excluded: set[str] = set()
    for claim in (getattr(claims, "claims", ()) or ()):
        fact_ids = [
            str(item) for item in (getattr(claim, "fact_ids", ()) or ())
            if str(item).strip()
        ]
        if not fact_ids:
            continue
        if not all(
            any(
                _span_overlap(span, bound_span)
                for span in (
                    *(getattr(fact_by_id.get(fact_id), "direct_span_ids", ()) or ()),
                    *(getattr(fact_by_id.get(fact_id), "relation_span_ids", ()) or ()),
                )
                for bound_span in audit_spans
                if str(span).strip()
            )
            for fact_id in fact_ids
            if fact_id in fact_by_id
        ):
            continue
        excluded.add(str(getattr(claim, "claim_id", "") or ""))
    return excluded


def story_override_concept_keys(
    concept_cards: Any,
    story_spine_nodes: Iterable[Any],
) -> frozenset[str]:
    """Story-derived relevance override (review Q1): cards the frozen author
    story names are never filtered as audit_only.

    A concept card is story-selected when its ``story_node`` matches a story
    spine node's id or title.  The spine is the frozen author-intent
    organization authority; no project-specific symbols enter this rule.
    """

    spine_keys = {
        str(getattr(node, "story_node_id", "") or "").strip()
        for node in (story_spine_nodes or ())
    }
    spine_keys |= {
        str(getattr(node, "title", "") or "").strip()
        for node in (story_spine_nodes or ())
    }
    spine_keys.discard("")
    if not spine_keys or concept_cards is None:
        return frozenset()
    return frozenset(
        str(getattr(card, "concept_key", "") or "")
        for card in (getattr(concept_cards, "cards", ()) or ())
        if str(getattr(card, "story_node", "") or "").strip() in spine_keys
    )


def classify_concept_card_writing_role(
    card: Any,
    *,
    story_selected: bool = False,
) -> WritingRole:
    """Deterministic writing role for one Concept card (R1).

    The role is derived from the card's own reader surface
    (method_subject, operation, inputs/outputs, conditions, numeric and
    formula constraints).  Defensive/bookkeeping cards (padding, tensor
    shape checks, chunk/index/ingestion bookkeeping, case-study branches,
    cache/log/device mechanics) are ``audit_only``: they stay in evidence
    and validation sidecars but never enter sentence plans, coverage
    obligations, qualifier repair, or Formalizer inputs.  ``story_selected``
    is the explicit author-story override: when the author story names the
    card as scientifically material, the role is never audit_only.
    """

    if story_selected:
        return "method_positive"
    surface = " ".join(str(value) for value in (
        getattr(card, "method_subject", ""),
        getattr(card, "operation", ""),
        *(getattr(card, "inputs", ()) or ()),
        *(getattr(card, "outputs", ()) or ()),
        *(getattr(card, "conditions", ()) or ()),
        *(getattr(card, "numeric_constraints", ()) or ()),
        *(getattr(card, "formula_constraints", ()) or ()),
    ) if str(value).strip())
    if has_audit_term(surface):
        return "audit_only"
    if getattr(card, "conditions", ()) or ():
        return "method_conditional"
    return "method_positive"


__all__ = [
    "WritingRole",
    "classify_claim_writing_role",
    "classify_concept_card_writing_role",
    "classify_fact_writing_role",
    "classify_proposition_writing_role",
    "concept_audit_claim_ids_exact",
    "concept_bound_claim_ids",
    "concept_bound_fact_ids",
    "has_audit_term",
    "story_override_concept_keys",
]
