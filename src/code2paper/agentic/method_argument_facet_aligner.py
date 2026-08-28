"""Candidate-side semantic facet alignment for Method argument briefs.

The deterministic argument-brief compiler remains the only source that can
license wording for the Verified lane.  This module adds a separate,
Candidate-facing path:

``author clause -> semantic facets -> closed evidence proposal -> policy``

LLM owners may decompose a compound author sentence and propose field-level
alignments, but the harness owns identity binding, exact excerpts, digest
checks, and the final prose policy.  In particular, a successful facet
alignment never mutates ``AuthorClauseLicenseV1`` or ``may_enter_verified``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
)
from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.method_argument_brief_models import (
    AuthorClauseLicenseV1,
    AuthorMechanismFacetV1,
    CandidateFacetPolicyV1,
    FacetAlignmentStatusV1,
    FacetEvidenceAlignmentV1,
    FacetEvidenceExcerptV1,
    FacetFieldBindingV1,
    FormulaExpectationV1,
    MechanismAuthoringPacketV1,
    MethodArgumentBriefSetV1,
    MethodArgumentBriefV1,
)
from code2paper.agentic.method_argument_brief_compiler import _stable_id
from code2paper.agentic.method_proposition_models import (
    MethodPropositionProposalBatchV1,
    MethodPropositionProposalV1,
    PropositionCandidateClusterV1,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.agentic.writer_research_router import directed_search_terms_from_texts
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    FacetFieldAlignmentProposalV1,
    FacetEvidenceAlignmentProposalBatchV1,
    FacetEvidenceAlignmentProposalV1,
    MethodMechanismFacetProposalBatchV1,
    MethodMechanismFacetProposalV1,
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import (
    METHOD_PROPOSITION_ARCHITECT,
    SEMANTIC_VERIFIER,
    apply_role_config,
)
from code2paper.schemas import LLMConfig


_FACET_KINDS = frozenset(
    {"mechanism", "motivation", "guarantee", "constraint", "interface", "formula"}
)
_FACET_KINDS_REQUIRED_BY_DEFAULT = frozenset(
    {"mechanism", "formula", "constraint", "interface", "algorithm", "procedure", "definition"}
)

_FACET_FIELD_ALIASES = {
    "reader_subject": "subject",
    "subject": "subject",
    "mechanism": "operation",
    "transformation": "operation",
    "operation": "operation",
    "inputs": "inputs",
    "input": "inputs",
    "outputs": "outputs",
    "output": "outputs",
    "conditions": "conditions",
    "condition": "conditions",
    "boundary": "conditions",
    "constraint": "conditions",
    "effects": "effects",
    "effect": "effects",
    "paper_terms": "effects",
    "interface": "interface",
    "formula": "formula_goal",
    "formula_goal": "formula_goal",
    "guarantee": "guarantee",
}


def _canonical_facet_field_name(value: Any) -> str:
    key = str(value or "").strip().casefold()
    return _FACET_FIELD_ALIASES.get(key, key)
_FORMULA_WORDS = frozenset(
    {
        "equation",
        "formula",
        "derivative",
        "gradient",
        "loss",
        "softplus",
        "sigmoid",
        "softmax",
        "normalization",
        "discretization",
        "discretize",
        "eigenvalue",
        "eigenvalues",
        "matrix",
        "matrices",
        "spectral",
        "update",
    }
)
_FORMULA_PHRASES = (
    "step size",
    "step-size",
    "delta t",
    "timespan-dependent",
    "time-gap",
)
_MOTIVATION_WORDS = frozenset(
    {
        "because",
        "benefit",
        "goal",
        "inspired",
        "motivat",
        "theory",
        "theoretical",
        "forgetting",
        "ebbinghaus",
        "novel",
        "novelty",
    }
)
_GUARANTEE_WORDS = frozenset(
    {
        "guarantee",
        "guarantees",
        "guaranteed",
        "stable",
        "stability",
        "monotonic",
        "monotonicity",
        "bounded",
        "constraint",
        "convergence",
        "spectral",
    }
)
_INTERFACE_WORDS = frozenset(
    {
        "input",
        "inputs",
        "output",
        "outputs",
        "passes",
        "receives",
        "returns",
        "feeds",
        "interface",
    }
)
_YAML_BOUND_SOURCE_FIELDS = frozenset({"pipeline_steps", "key_building_blocks"})
_ALIGNABLE_SOURCE_FIELDS = frozenset(
    {
        "design_intents",
        "innovation_claims",
        "story_order",
        "module_roles",
    }
)
_MAINLINE_SOURCE_FIELDS = frozenset({"method_mainline", "project_goal"})
_MECHANISM_OPERATION_WORDS = frozenset(
    {
        "transform",
        "compute",
        "initialize",
        "update",
        "encode",
        "decode",
        "select",
        "sort",
        "aggregate",
        "embed",
        "train",
        "learn",
        "apply",
        "scale",
        "normalize",
        "project",
        "concatenate",
        "multiply",
        "derive",
        "optimize",
        "minimize",
        "maximize",
        "sample",
        "retrieve",
        "search",
        "filter",
        "mask",
        "gate",
        "route",
        "forward",
        "backward",
        "replace",
        "insert",
        "remove",
        "extract",
        "build",
        "construct",
        "generate",
        "predict",
        "infer",
        "evaluate",
    }
)
_UNPROVEN_CONSTRAINT_WORDS = frozenset(
    {
        "ideally",
        "future",
        "unimplemented",
        "hopefully",
        "aspire",
        "wish",
    }
)


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _as_items(value: Any, attribute: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if hasattr(value, attribute):
        value = getattr(value, attribute)
    if isinstance(value, Mapping):
        return tuple(value.values())
    if isinstance(value, (str, bytes)):
        return (value,)
    try:
        return tuple(value)
    except TypeError:
        return (value,)


def _clean_strings(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value).strip()
        )
    )


def _tokens(value: Any) -> frozenset[str]:
    normalized = str(value or "").casefold()
    # Keep Greek delta as a semantic hint while also allowing ordinary code
    # identifiers and words.  This is recall metadata only; it never grants a
    # license.
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9δΔ]+", normalized)
        if token
    )


def _text_from_semantic_fields(fields: Mapping[str, Any]) -> str:
    values: list[str] = []
    for key, value in fields.items():
        values.append(str(key))
        if isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _default_facet_required(
    facet_kind: str,
    *,
    source_field: str = "",
) -> bool:
    """Required only for yaml stage/block mechanism kinds."""

    field = str(source_field or "").strip()
    if field not in _YAML_BOUND_SOURCE_FIELDS:
        return False
    kind = str(facet_kind or "").casefold().strip()
    if kind in {"motivation", "guarantee"}:
        return False
    if kind in {"algorithm", "procedure", "definition"}:
        return True
    return kind in _FACET_KINDS_REQUIRED_BY_DEFAULT


def _obligation_source_field_map(
    intent_graph: IntentObligationGraphV2 | None,
) -> dict[str, str]:
    if intent_graph is None:
        return {}
    return {
        str(item.obligation_id): str(item.source_field or "")
        for item in intent_graph.obligations
        if str(item.obligation_id or "").strip()
    }


def _brief_source_field(
    brief: MethodArgumentBriefV1,
    obligation_source_fields: Mapping[str, str],
) -> str:
    for obligation_id in brief.obligation_ids:
        field = str(obligation_source_fields.get(str(obligation_id), "") or "").strip()
        if field:
            return field
    return ""


def _normalize_facet_quote(quote: str) -> str:
    return " ".join(_tokens(str(quote or "")))


def _quote_covered_by_anchors(norm_quote: str, anchor_quotes: frozenset[str]) -> bool:
    if not norm_quote:
        return True
    for anchor in anchor_quotes:
        if not anchor:
            continue
        if norm_quote == anchor or norm_quote in anchor or anchor in norm_quote:
            return True
        anchor_tokens = set(anchor.split())
        quote_tokens = set(norm_quote.split())
        if quote_tokens and anchor_tokens:
            overlap = len(quote_tokens & anchor_tokens)
            if overlap / len(quote_tokens) >= 0.8:
                return True
    return False


def _has_author_formula_signal(text: str) -> bool:
    """Whether author wording names a mathematizable object (Δt, matrix, …)."""

    surface = str(text or "")
    folded = surface.casefold()
    if any(marker in surface for marker in ("=", "≤", "≥", "∥", "Δ", "δ")):
        return True
    if any(phrase in folded for phrase in _FORMULA_PHRASES):
        return True
    tokens = set(_tokens(surface))
    if tokens.intersection(_FORMULA_WORDS):
        return True
    return any(
        token.startswith("δ") or token.startswith("Δ") or token in {"δt", "deltat"}
        for token in tokens
    )


def _has_mechanism_signal(text: str) -> bool:
    words = set(_tokens(str(text or "").casefold()))
    if words.intersection(_MECHANISM_OPERATION_WORDS):
        return True
    if "=" in text:
        return True
    return _has_author_formula_signal(text)


def _has_non_mechanism_authority(text: str) -> bool:
    words = set(_tokens(str(text or "").casefold()))
    if words.intersection(_MOTIVATION_WORDS):
        return True
    if words.intersection(_GUARANTEE_WORDS):
        return True
    return bool(words.intersection(_UNPROVEN_CONSTRAINT_WORDS))


def _mixed_authority_segments(text: str) -> tuple[str, ...]:
    """Split only when one yaml item mixes mechanism with motivation/guarantee."""

    candidate = str(text or "").strip()
    if not candidate:
        return ()
    if not (_has_mechanism_signal(candidate) and _has_non_mechanism_authority(candidate)):
        return (candidate,)
    parts = _split_clause_fragments(candidate)
    if len(parts) <= 3:
        return parts
    return (parts[0], parts[1], " ".join(parts[2:]))


def _author_brief_text(brief: MethodArgumentBriefV1) -> str:
    text = str(brief.author_statement or "").strip()
    if text:
        return text
    if brief.clauses:
        return str(brief.clauses[0].text or "").strip()
    return ""


def _intent_grain_facet_rows(
    brief: MethodArgumentBriefV1,
    source_field: str,
) -> tuple[dict[str, Any], ...]:
    text = _author_brief_text(brief)
    if not text:
        return ()
    if source_field in _YAML_BOUND_SOURCE_FIELDS:
        segments = _mixed_authority_segments(text)
    else:
        segments = (text,)
    rows: list[dict[str, Any]] = []
    for fragment in segments:
        kind = _classify_facet_kind(fragment)
        rows.append(
            {
                "source_clause_index": 0,
                "exact_source_quote": fragment,
                "facet_kind": kind,
                "semantic_fields": _fallback_semantic_fields(fragment, kind),
                "formula_expectation": _formula_expectation(fragment, kind),
                "search_terms": list(directed_search_terms_from_texts(fragment)),
            }
        )
    return tuple(rows)


def _dedupe_intent_grain_facets(
    facets: list[AuthorMechanismFacetV1],
    *,
    brief_source_fields: Mapping[str, str],
) -> list[AuthorMechanismFacetV1]:
    anchor_quotes: set[str] = set()
    for facet in facets:
        source_field = str(brief_source_fields.get(facet.brief_id, "") or "")
        if source_field in _YAML_BOUND_SOURCE_FIELDS:
            anchor_quotes.add(_normalize_facet_quote(facet.exact_source_quote))
    anchor_frozen = frozenset(anchor_quotes)
    seen_quotes: set[str] = set()
    filtered: list[AuthorMechanismFacetV1] = []
    for facet in facets:
        source_field = str(brief_source_fields.get(facet.brief_id, "") or "")
        norm_quote = _normalize_facet_quote(facet.exact_source_quote)
        if source_field in _MAINLINE_SOURCE_FIELDS:
            if _quote_covered_by_anchors(norm_quote, anchor_frozen):
                continue
        if norm_quote in seen_quotes:
            continue
        seen_quotes.add(norm_quote)
        filtered.append(facet)
    return filtered


def _classify_facet_kind(text: str, fields: Mapping[str, Any] | None = None) -> str:
    surface = " ".join((text, _text_from_semantic_fields(fields or {}))).casefold()
    words = set(_tokens(surface))
    if _has_author_formula_signal(text) or _has_author_formula_signal(surface):
        return "formula"
    if words.intersection(_MOTIVATION_WORDS):
        return "motivation"
    if words.intersection(_GUARANTEE_WORDS):
        return "guarantee"
    if words.intersection(_INTERFACE_WORDS):
        return "interface"
    if "constraint" in words or "bound" in words:
        return "constraint"
    return "mechanism"


def _formula_expectation(text: str, facet_kind: str) -> FormulaExpectationV1:
    if facet_kind == "formula" or "=" in text or "≤" in text or "≥" in text:
        return "required"
    if _has_author_formula_signal(text):
        return "preferred"
    if facet_kind in {"mechanism", "constraint"} and (
        _tokens(text).intersection(_FORMULA_WORDS)
    ):
        return "preferred"
    return "none"


def _fallback_semantic_fields(text: str, facet_kind: str) -> dict[str, Any]:
    """Build conservative organization fields when an owner is unavailable."""

    if facet_kind == "motivation":
        return {"motivation": text}
    if facet_kind == "guarantee":
        return {"guarantee": text}
    if facet_kind == "constraint":
        return {"constraint": text}
    if facet_kind == "interface":
        return {"interface": text}
    if facet_kind == "formula":
        return {"formula": text}
    return {"mechanism": text}


def _split_clause_fragments(text: str) -> tuple[str, ...]:
    """Split only at clear author-level boundaries, preserving substrings."""

    candidate_parts = re.split(
        r";|,\s+(?=(?:and|while|where|with|then|but|which)\b)|"
        r"\s+\band\b(?=\s+(?:the|a|an|this|that|it|its|we|to|using|as)\b)",
        text,
        flags=re.IGNORECASE,
    )
    parts = tuple(
        part.strip(" \t\r\n,")
        for part in candidate_parts
        if part.strip(" \t\r\n,")
    )
    return parts or (text.strip(),)


def _brief_list(
    briefs: MethodArgumentBriefSetV1
    | Iterable[MethodArgumentBriefV1]
    | None,
) -> tuple[MethodArgumentBriefV1, ...]:
    if briefs is None:
        return ()
    return tuple(_as_items(briefs, "briefs"))


def _claim_list(claims: AtomicClaimSetV3 | Iterable[Any] | None) -> tuple[Any, ...]:
    return _as_items(claims, "claims")


def _fact_list(facts: CodeFactSetV1 | Iterable[Any] | None) -> tuple[Any, ...]:
    return _as_items(facts, "facts")


def _equation_list(equations: EquationClaimSetV1 | Iterable[Any] | None) -> tuple[Any, ...]:
    return _as_items(equations, "equations")


def _packet_list(
    packets: EvidencePacketSetV3 | Iterable[Any] | None,
) -> tuple[Any, ...]:
    return _as_items(packets, "packets")


def _span_list(packets: Iterable[Any]) -> tuple[Any, ...]:
    spans: list[Any] = []
    seen: set[str] = set()
    for packet in packets:
        for span in getattr(packet, "spans", ()) or ():
            span_id = str(getattr(span, "span_id", "") or "")
            if not span_id or span_id in seen:
                continue
            seen.add(span_id)
            spans.append(span)
    return tuple(spans)


def _claim_id(claim: Any) -> str:
    return str(getattr(claim, "claim_id", "") or "")


def _fact_id(fact: Any) -> str:
    return str(getattr(fact, "fact_id", "") or "")


def _equation_id(equation: Any) -> str:
    return str(getattr(equation, "equation_id", "") or "")


def _span_id(span: Any) -> str:
    return str(getattr(span, "span_id", "") or "")


def _span_excerpt(
    span: Any,
    *,
    facet_id: str = "",
    fact_ids: Iterable[str] = (),
    equation_ids: Iterable[str] = (),
) -> FacetEvidenceExcerptV1:
    return FacetEvidenceExcerptV1(
        facet_id=facet_id,
        span_id=_span_id(span),
        path=str(getattr(span, "path", "") or ""),
        symbol=str(getattr(span, "symbol", "") or ""),
        line_start=int(getattr(span, "line_start", 0) or 0),
        line_end=int(getattr(span, "line_end", 0) or 0),
        exact_excerpt=str(getattr(span, "exact_excerpt", "") or ""),
        excerpt_digest=str(getattr(span, "excerpt_digest", "") or ""),
        file_digest=str(getattr(span, "file_digest", "") or ""),
        fact_ids=_clean_strings(fact_ids),
        equation_ids=_clean_strings(equation_ids),
        operation_atoms=(),
    )


def _span_fact_ids(
    *,
    span_id: str,
    claims: Iterable[Any],
    facts: Iterable[Any],
    equations: Iterable[Any],
) -> tuple[str, ...]:
    fact_ids: list[str] = []
    for claim in claims:
        if span_id in set(getattr(claim, "direct_evidence_ids", ()) or ()):
            fact_ids.extend(str(item) for item in (getattr(claim, "fact_ids", ()) or ()))
    for equation in equations:
        if span_id in set(getattr(equation, "relation_evidence_ids", ()) or ()):
            fact_ids.extend(str(item) for item in (getattr(equation, "fact_ids", ()) or ()))
    for fact in facts:
        if span_id in set(getattr(fact, "direct_span_ids", ()) or ()):
            fact_ids.append(_fact_id(fact))
    return _clean_strings(fact_ids)


def _span_equation_ids(
    *,
    span_id: str,
    equations: Iterable[Any],
    facts: Iterable[Any],
) -> tuple[str, ...]:
    result: list[str] = []
    span_fact_ids = {
        _fact_id(fact)
        for fact in facts
        if span_id in set(getattr(fact, "direct_span_ids", ()) or ())
    }
    for equation in equations:
        equation_facts = set(getattr(equation, "fact_ids", ()) or ())
        if span_id in set(getattr(equation, "relation_evidence_ids", ()) or ()) or (
            span_fact_ids.intersection(equation_facts)
        ):
            result.append(_equation_id(equation))
    return _clean_strings(result)


def _candidate_evidence(
    brief: MethodArgumentBriefV1,
    *,
    claims: tuple[Any, ...],
    facts: tuple[Any, ...],
    equations: tuple[Any, ...],
    packets: tuple[Any, ...],
) -> tuple[dict[str, Any], ...]:
    """Return a closed, exact evidence envelope for one brief."""

    claim_by_id = {_claim_id(item): item for item in claims}
    fact_by_id = {_fact_id(item): item for item in facts}
    equation_by_id = {_equation_id(item): item for item in equations}
    span_by_id = {_span_id(item): item for item in _span_list(packets)}

    claim_ids = tuple(
        claim_id for claim_id in brief.claim_ids if claim_id in claim_by_id
    )
    equation_ids = tuple(
        equation_id for equation_id in brief.equation_ids if equation_id in equation_by_id
    )
    fact_ids = {
        fact_id
        for claim_id in claim_ids
        for fact_id in (getattr(claim_by_id[claim_id], "fact_ids", ()) or ())
        if fact_id in fact_by_id
    }
    fact_ids.update(
        fact_id
        for equation_id in equation_ids
        for fact_id in (getattr(equation_by_id[equation_id], "fact_ids", ()) or ())
        if fact_id in fact_by_id
    )
    span_ids: list[str] = [
        span_id for span_id in brief.span_ids if span_id in span_by_id
    ]
    for claim_id in claim_ids:
        for span_id in (getattr(claim_by_id[claim_id], "direct_evidence_ids", ()) or ()):
            if span_id in span_by_id:
                span_ids.append(span_id)
    for fact_id in fact_ids:
        for span_id in (getattr(fact_by_id[fact_id], "direct_span_ids", ()) or ()):
            if span_id in span_by_id:
                span_ids.append(span_id)
    for equation_id in equation_ids:
        for span_id in (
            getattr(equation_by_id[equation_id], "relation_evidence_ids", ()) or ()
        ):
            if span_id in span_by_id:
                span_ids.append(span_id)
    span_ids = list(dict.fromkeys(span_ids))

    rows: list[dict[str, Any]] = []
    for index, span_id in enumerate(span_ids):
        span = span_by_id[span_id]
        span_fact_ids = _span_fact_ids(
            span_id=span_id,
            claims=(claim_by_id[item] for item in claim_ids),
            facts=facts,
            equations=(equation_by_id[item] for item in equation_ids),
        )
        span_equation_ids = _span_equation_ids(
            span_id=span_id,
            equations=(equation_by_id[item] for item in equation_ids),
            facts=facts,
        )
        excerpt = _span_excerpt(
            span,
            fact_ids=span_fact_ids,
            equation_ids=span_equation_ids,
        )
        rows.append(
            {
                "evidence_index": index,
                "claim_ids": list(
                    claim_id
                    for claim_id in claim_ids
                    if span_id
                    in set(
                        getattr(claim_by_id[claim_id], "direct_evidence_ids", ())
                        or ()
                    )
                ),
                "claim_texts": [
                    str(getattr(claim_by_id[claim_id], "canonical_text", "") or "")
                    for claim_id in claim_ids
                    if span_id
                    in set(
                        getattr(claim_by_id[claim_id], "direct_evidence_ids", ())
                        or ()
                    )
                ],
                "fact_ids": list(span_fact_ids),
                "fact_atoms": [
                    {
                        "fact_id": fact_id,
                        "subject": str(getattr(fact_by_id[fact_id], "subject", "") or ""),
                        "predicate": str(
                            getattr(fact_by_id[fact_id], "predicate", "") or ""
                        ),
                        "object": getattr(fact_by_id[fact_id], "object", ""),
                        "conditions": list(
                            getattr(fact_by_id[fact_id], "conditions", ()) or ()
                        ),
                    }
                    for fact_id in span_fact_ids
                    if fact_id in fact_by_id
                ],
                "equation_ids": list(span_equation_ids),
                "equation_atoms": [
                    {
                        "equation_id": equation_id,
                        "expression": str(
                            getattr(equation_by_id[equation_id], "expression", "")
                            or ""
                        ),
                        "operation_descriptors": list(
                            getattr(
                                equation_by_id[equation_id],
                                "operation_descriptors",
                                (),
                            )
                            or ()
                        ),
                    }
                    for equation_id in span_equation_ids
                    if equation_id in equation_by_id
                ],
                "path": excerpt.path,
                "symbol": excerpt.symbol,
                "line_start": excerpt.line_start,
                "line_end": excerpt.line_end,
                "exact_excerpt": excerpt.exact_excerpt,
                "excerpt_digest": excerpt.excerpt_digest,
                "_excerpt": excerpt,
            }
        )
    return tuple(rows)


def _author_cluster(
    brief: MethodArgumentBriefV1,
    *,
    claims: tuple[Any, ...],
    facts: tuple[Any, ...],
) -> PropositionCandidateClusterV1:
    claim_ids = tuple(
        str(item) for item in brief.claim_ids if str(item).strip()
    )
    fact_ids = tuple(
        dict.fromkeys(
            str(fact_id)
            for claim in claims
            if _claim_id(claim) in set(claim_ids)
            for fact_id in (getattr(claim, "fact_ids", ()) or ())
            if str(fact_id).strip()
        )
    )
    subjects = tuple(
        dict.fromkeys(
            str(getattr(fact, "subject", "") or "")
            for fact in facts
            if _fact_id(fact) in set(fact_ids)
            and str(getattr(fact, "subject", "") or "").strip()
        )
    )
    predicates = tuple(
        dict.fromkeys(
            str(getattr(fact, "predicate", "") or "")
            for fact in facts
            if _fact_id(fact) in set(fact_ids)
            and str(getattr(fact, "predicate", "") or "").strip()
        )
    )
    conditions = tuple(
        dict.fromkeys(
            str(condition)
            for fact in facts
            if _fact_id(fact) in set(fact_ids)
            for condition in (getattr(fact, "conditions", ()) or ())
            if str(condition).strip()
        )
    )
    return PropositionCandidateClusterV1(
        cluster_id=f"facet-cluster:{brief.brief_id}",
        origin="author_intent",
        obligation_ids=brief.obligation_ids,
        claim_ids=claim_ids,
        fact_ids=fact_ids,
        span_ids=brief.span_ids,
        source_statements=tuple(
            clause.text for clause in brief.clauses if clause.text.strip()
        )
        or (brief.author_statement,),
        uncertainty_notes=tuple(
            dict.fromkeys(
                status
                for status in brief.completeness_statuses
                if status != "supported_by_repository"
            )
        ),
        subjects=subjects,
        predicates=predicates,
        conditions=conditions,
        section_hints=(brief.intended_role,),
        author_term_hints=tuple(
            token
            for clause in brief.clauses
            for token in re.findall(r"[A-Za-zΔδ][A-Za-z0-9_Δδ-]*", clause.text)
            if len(token) > 1
        )[:48],
        evidence_lane="author_intent_unverified",
    )


def _normalize_decomposition_output(
    value: Any,
) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if isinstance(value, MethodMechanismFacetProposalBatchV1):
        return tuple(item.model_dump(mode="python") for item in value.facets)
    if isinstance(value, Mapping):
        rows = value.get("facets", value.get("proposals", value.get("items", ())))
    elif hasattr(value, "facets"):
        rows = getattr(value, "facets")
    elif hasattr(value, "proposals"):
        rows = getattr(value, "proposals")
    else:
        rows = value
    if isinstance(rows, Mapping):
        rows = (rows,)
    result: list[dict[str, Any]] = []
    for item in rows or ():
        if isinstance(item, BaseModel):
            result.append(item.model_dump(mode="python"))
        elif isinstance(item, Mapping):
            result.append(dict(item))
    return tuple(result)


def _normalize_alignment_output(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, FacetEvidenceAlignmentProposalBatchV1):
        return (
            value.alignments[0].model_dump(mode="python")
            if value.alignments
            else {}
        )
    if isinstance(value, FacetEvidenceAlignmentProposalV1):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        if "alignments" in value:
            rows = value.get("alignments") or ()
            if rows:
                first = rows[0]
                return (
                    first.model_dump(mode="python")
                    if isinstance(first, BaseModel)
                    else dict(first)
                )
            return {}
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return {}


def _facet_from_row(
    row: Mapping[str, Any],
    *,
    brief: MethodArgumentBriefV1,
    fallback_index: int,
    source_field: str = "",
) -> tuple[AuthorMechanismFacetV1, tuple[str, ...]]:
    clauses = tuple(brief.clauses)
    raw_quote = str(
        row.get("exact_source_quote")
        or row.get("source_quote")
        or row.get("quote")
        or ""
    ).strip()
    raw_clause_index = row.get("source_clause_index", row.get("clause_index"))
    clause_index: int | None = None
    try:
        if raw_clause_index is not None:
            clause_index = int(raw_clause_index)
    except (TypeError, ValueError):
        clause_index = None

    selected_clause = None
    if raw_quote:
        selected_clause = next(
            (
                clause
                for clause in clauses
                if raw_quote in clause.text or clause.text in raw_quote
            ),
            None,
        )
    if selected_clause is None and clause_index is not None and clauses:
        candidates = [clause_index]
        if clause_index > 0:
            candidates.append(clause_index - 1)
        for candidate in candidates:
            if 0 <= candidate < len(clauses):
                selected_clause = clauses[candidate]
                break
    if selected_clause is None and clauses:
        selected_clause = clauses[min(fallback_index, len(clauses) - 1)]

    failures: list[str] = []
    if selected_clause is None:
        selected_clause_id = f"clause:{brief.brief_id}:{fallback_index}"
        quote = raw_quote or brief.author_statement
        failures.append("decomposer_clause_reference_unresolved")
    else:
        selected_clause_id = selected_clause.clause_id
        if raw_quote and raw_quote in selected_clause.text:
            quote = raw_quote
        elif raw_quote and selected_clause.text in raw_quote:
            quote = selected_clause.text
            failures.append("decomposer_quote_was_wider_than_clause")
        else:
            quote = selected_clause.text
            if raw_quote:
                failures.append("decomposer_quote_not_exact_substring")
    if not quote.strip():
        quote = brief.author_statement
        failures.append("empty_decomposer_quote")

    fields = row.get("semantic_fields")
    if not isinstance(fields, Mapping):
        fields = {}
    fields = dict(fields)
    # Accept the existing proposition-architect vocabulary as an adapter
    # without exposing proposition ids to the new packet.
    for source_key, target_key in (
        ("reader_subject", "subject"),
        ("transformation", "operation"),
        ("inputs", "inputs"),
        ("outputs", "outputs"),
        ("conditions", "conditions"),
        ("boundary", "conditions"),
        ("paper_terms", "effects"),
    ):
        if source_key in row and target_key not in fields:
            fields[target_key] = row[source_key]
    canonical_fields: dict[str, Any] = {}
    for raw_name, value in fields.items():
        field_name = _canonical_facet_field_name(raw_name)
        if field_name not in {
            "subject", "operation", "inputs", "outputs", "conditions",
            "effects", "interface", "formula_goal", "guarantee",
        }:
            failures.append(f"unknown_semantic_field:{raw_name}")
            continue
        if field_name not in canonical_fields:
            canonical_fields[field_name] = value
        elif canonical_fields[field_name] != value:
            existing = canonical_fields[field_name]
            existing_values = existing if isinstance(existing, list) else [existing]
            new_values = value if isinstance(value, list) else [value]
            canonical_fields[field_name] = [*existing_values, *new_values]
    fields = canonical_fields
    facet_kind = str(row.get("facet_kind") or "").strip().casefold()
    if facet_kind not in _FACET_KINDS:
        facet_kind = _classify_facet_kind(quote, fields)
    detected_expectation = _formula_expectation(quote, facet_kind)
    raw_expectation = str(row.get("formula_expectation") or "").strip().casefold()
    rank = {"none": 0, "preferred": 1, "required": 2}
    if raw_expectation not in rank:
        expectation = detected_expectation
        if raw_expectation:
            failures.append("invalid_formula_expectation")
    elif rank[detected_expectation] >= rank[raw_expectation]:
        # Model ``none`` must not hide a Δt / matrix quote from Formalizer.
        expectation = detected_expectation
    else:
        expectation = raw_expectation
    if not fields:
        fields = {
            _canonical_facet_field_name(key): value
            for key, value in _fallback_semantic_fields(quote, facet_kind).items()
        }
    search_terms = _clean_strings(
        row.get("search_terms")
        or row.get("candidate_symbols_or_terms")
        or ()
    )
    if not search_terms:
        field_texts: list[Any] = [quote]
        if isinstance(fields, Mapping):
            for value in fields.values():
                if isinstance(value, (list, tuple)):
                    field_texts.extend(value)
                else:
                    field_texts.append(value)
        search_terms = directed_search_terms_from_texts(*field_texts)
    facet_id = _stable_id(
        "facet",
        brief.brief_id,
        selected_clause_id,
        str(fallback_index),
        quote,
    )
    facet = AuthorMechanismFacetV1(
        facet_id=facet_id,
        clause_id=selected_clause_id,
        exact_source_quote=quote,
        facet_kind=facet_kind,  # type: ignore[arg-type]
        brief_id=brief.brief_id,
        semantic_fields=fields,
        formula_expectation=expectation,  # type: ignore[arg-type]
        search_terms=search_terms,
        required=_default_facet_required(facet_kind, source_field=source_field),
    )
    return facet, tuple(failures)


def _fallback_facet_rows(
    brief: MethodArgumentBriefV1,
    *,
    source_field: str = "",
) -> tuple[dict[str, Any], ...]:
    if source_field in (
        _YAML_BOUND_SOURCE_FIELDS
        | _ALIGNABLE_SOURCE_FIELDS
        | _MAINLINE_SOURCE_FIELDS
    ):
        rows = _intent_grain_facet_rows(brief, source_field)
        if rows:
            return rows
    rows: list[dict[str, Any]] = []
    for clause_index, clause in enumerate(brief.clauses):
        fragments = _split_clause_fragments(clause.text)
        for fragment in fragments:
            kind = _classify_facet_kind(fragment)
            rows.append(
                {
                    "source_clause_index": clause_index,
                    "exact_source_quote": fragment,
                    "facet_kind": kind,
                    "semantic_fields": _fallback_semantic_fields(fragment, kind),
                    "formula_expectation": _formula_expectation(fragment, kind),
                    "search_terms": list(
                        directed_search_terms_from_texts(fragment)
                    ),
                }
            )
    if rows:
        return tuple(rows)
    return (
        {
            "source_clause_index": 0,
            "exact_source_quote": brief.author_statement,
            "facet_kind": _classify_facet_kind(brief.author_statement),
            "semantic_fields": _fallback_semantic_fields(
                brief.author_statement,
                _classify_facet_kind(brief.author_statement),
            ),
        },
    )


def _decompose_brief(
    brief: MethodArgumentBriefV1,
    *,
    claims: tuple[Any, ...],
    facts: tuple[Any, ...],
    facet_decomposer: Callable[[dict[str, Any]], Any] | None,
    proposition_architect: Callable[..., Any] | None,
    schema_failures: list[str],
    source_field: str = "",
) -> tuple[AuthorMechanismFacetV1, ...]:
    rows: tuple[dict[str, Any], ...] = ()
    yaml_bound = source_field in _YAML_BOUND_SOURCE_FIELDS
    intent_grain = yaml_bound or source_field in (
        _ALIGNABLE_SOURCE_FIELDS | _MAINLINE_SOURCE_FIELDS
    )
    author_text = _author_brief_text(brief)
    mixed_authority = yaml_bound and len(_mixed_authority_segments(author_text)) > 1
    if facet_decomposer is not None and mixed_authority:
        payload = {
            "brief": {
                "intended_role": brief.intended_role,
                "author_statement": brief.author_statement,
                "clauses": [
                    {
                        "clause_index": index,
                        "text": clause.text,
                        "license": clause.license,
                    }
                    for index, clause in enumerate(brief.clauses)
                ],
            },
            "instruction": (
                "Preserve the supplied yaml step or building block as one facet "
                "unless it mixes implementable mechanism with motivation, external "
                "theory, or unproven constraints; in that mixed case split into at "
                "most three facets. Do not output facet_id. Use only the semantic "
                "field names subject, operation, inputs, outputs, conditions, "
                "effects, interface, formula_goal, and guarantee. Preserve exact "
                "source substrings; do not decide repository support or invent "
                "evidence ids."
            ),
        }
        try:
            rows = _normalize_decomposition_output(facet_decomposer(payload))
        except Exception as exc:  # noqa: BLE001 - owner failure is typed below
            schema_failures.append(
                f"{brief.brief_id}:facet_decomposer:{type(exc).__name__}"
            )
    elif intent_grain:
        rows = _intent_grain_facet_rows(brief, source_field)
    elif facet_decomposer is not None:
        payload = {
            "brief": {
                "intended_role": brief.intended_role,
                "author_statement": brief.author_statement,
                "clauses": [
                    {
                        "clause_index": index,
                        "text": clause.text,
                        "license": clause.license,
                    }
                    for index, clause in enumerate(brief.clauses)
                ],
            },
            "instruction": (
                "Split the supplied author clauses into independently judgeable "
                "mechanism, motivation, guarantee, constraint, interface, or "
                "formula facets. Each facet must be the smallest independent "
                "claim and its semantic_fields must use only subject, operation, "
                "inputs, outputs, conditions, effects, interface, formula_goal, "
                "or guarantee. Do not put text from a second sentence into a "
                "field when exact_source_quote covers only the first. Preserve "
                "exact source substrings; do not decide repository support or "
                "invent evidence ids."
            ),
        }
        try:
            rows = _normalize_decomposition_output(facet_decomposer(payload))
        except Exception as exc:  # noqa: BLE001 - owner failure is typed below
            schema_failures.append(
                f"{brief.brief_id}:facet_decomposer:{type(exc).__name__}"
            )
    elif proposition_architect is not None:
        cluster = _author_cluster(brief, claims=claims, facts=facts)
        try:
            proposed = proposition_architect(cluster)
            if isinstance(proposed, MethodPropositionProposalBatchV1):
                proposal_items = proposed.proposals
            elif hasattr(proposed, "proposals"):
                proposal_items = getattr(proposed, "proposals")
            elif isinstance(proposed, Mapping):
                proposal_items = proposed.get("proposals") or ()
            else:
                proposal_items = proposed or ()
            rows = tuple(
                item.model_dump(mode="python")
                if isinstance(item, BaseModel)
                else dict(item)
                for item in proposal_items
            )
        except Exception as exc:  # noqa: BLE001 - owner failure is typed below
            schema_failures.append(
                f"{brief.brief_id}:proposition_architect:{type(exc).__name__}"
            )
    if not rows:
        rows = _fallback_facet_rows(brief, source_field=source_field)
        if facet_decomposer is not None or proposition_architect is not None:
            if not intent_grain:
                schema_failures.append(f"{brief.brief_id}:facet_decomposer_empty")

    facets: list[AuthorMechanismFacetV1] = []
    for index, row in enumerate(rows):
        facet, failures = _facet_from_row(
            row,
            brief=brief,
            fallback_index=index,
            source_field=source_field,
        )
        facets.append(facet)
        schema_failures.extend(
            f"{facet.facet_id}:{failure}" for failure in failures
        )
    return tuple(facets)


def _score_evidence(
    facet: AuthorMechanismFacetV1,
    row: Mapping[str, Any],
) -> int:
    target = _tokens(
        " ".join(
            (
                facet.exact_source_quote,
                _text_from_semantic_fields(facet.semantic_fields),
                *facet.search_terms,
            )
        )
    )
    evidence = _tokens(
        " ".join(
            (
                str(row.get("exact_excerpt") or ""),
                " ".join(str(item) for item in (row.get("claim_texts") or ())),
                json.dumps(
                    row.get("fact_atoms") or (),
                    ensure_ascii=False,
                ),
                json.dumps(
                    row.get("equation_atoms") or (),
                    ensure_ascii=False,
                ),
            )
        )
    )
    return len(target.intersection(evidence))


def _select_evidence_rows(
    facet: AuthorMechanismFacetV1,
    rows: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    if not rows:
        return ()
    scored = [(max(0, _score_evidence(facet, row)), row) for row in rows]
    maximum = max(score for score, _ in scored)
    if maximum <= 0:
        return ()
    # Keep only the strongest tied rows.  This avoids turning a section-level
    # claim envelope into evidence for every facet.
    return tuple(row for score, row in scored if score == maximum)


def _row_text(row: Mapping[str, Any]) -> str:
    """Bounded textual view used only for polarity consistency checks."""

    return " ".join(
        (
            str(row.get("exact_excerpt") or ""),
            " ".join(str(item) for item in (row.get("claim_texts") or ())),
            json.dumps(row.get("fact_atoms") or (), ensure_ascii=False),
            json.dumps(row.get("equation_atoms") or (), ensure_ascii=False),
        )
    ).casefold()


def _polarity_conflict(polarity: str, rows: Iterable[Mapping[str, Any]]) -> str:
    """Return an explicit comparator conflict, if the source states one.

    Absence of a comparator is not treated as proof of polarity.  Conversely,
    an explicit opposite comparator is a hard mismatch and cannot be repaired
    by lexical overlap (e.g. ``<`` cannot satisfy ``threshold_gt_selects``).
    """

    value = str(polarity or "").strip().casefold()
    if value not in {
        "threshold_lt_excludes", "threshold_lte_excludes",
        "threshold_gt_selects", "threshold_gte_selects",
    }:
        return ""
    text = " ".join(_row_text(row) for row in rows)
    has_lt = bool(re.search(r"(?<![<])<(?![=])|\blt\b|less than|below", text))
    has_lte = bool(re.search(r"<=|\blte\b|less than or equal", text))
    has_gt = bool(re.search(r"(?<![>])>(?![=])|\bgt\b|greater than|above", text))
    has_gte = bool(re.search(r">=|\bgte\b|greater than or equal", text))
    if value == "threshold_gt_selects" and (has_lt or has_lte):
        return "polarity_conflict:expected_gt_selects_observed_lt"
    if value == "threshold_gte_selects" and (has_lt or has_lte):
        return "polarity_conflict:expected_gte_selects_observed_lt"
    if value == "threshold_lt_excludes" and (has_gt or has_gte):
        return "polarity_conflict:expected_lt_excludes_observed_gt"
    if value == "threshold_lte_excludes" and (has_gt or has_gte):
        return "polarity_conflict:expected_lte_excludes_observed_gt"
    return ""


def _proposition_judge_payload(
    facet: AuthorMechanismFacetV1,
    rows: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "proposition_id": facet.facet_id,
        "proposed_semantics": dict(facet.semantic_fields),
        "required_semantic_fields": list(facet.semantic_fields),
        "selected_atomic_claims": [
            {
                "claim_id": claim_id,
                "canonical_text": text,
            }
            for row in rows
            for claim_id, text in zip(
                row.get("claim_ids") or (),
                row.get("claim_texts") or (),
            )
        ],
        "selected_code_facts": [
            item for row in rows for item in (row.get("fact_atoms") or ())
        ],
        "selected_equations": [
            item for row in rows for item in (row.get("equation_atoms") or ())
        ],
        "exact_code_excerpts": [
            {
                key: row.get(key)
                for key in (
                    "path",
                    "symbol",
                    "line_start",
                    "line_end",
                    "exact_excerpt",
                )
            }
            for row in rows
        ],
    }


def _alignment_from_owner(
    value: Any,
    *,
    facet: AuthorMechanismFacetV1,
    rows: tuple[dict[str, Any], ...],
    owner_error: str = "",
) -> FacetEvidenceAlignmentV1:
    raw = _normalize_alignment_output(value)
    if not raw and rows:
        # External semantic judging is advisory.  When it is unavailable
        # (provider/schema/tool failure), continue through the local closed
        # evidence envelope rather than discarding every selected field.  The
        # fallback is deliberately ``partial`` and exact-id based, so it can
        # never grant Verified authorization by itself.
        selected = _select_evidence_rows(facet, rows)
        if selected:
            selected_indices = [int(row["evidence_index"]) for row in selected]
            field_rows = [
                {
                    "field_name": field_name,
                    "status": "partial",
                    "polarity": "unknown",
                    "bound_span_indices": selected_indices,
                }
                for field_name in facet.semantic_fields
            ]
            raw = {
                "status": "partial",
                "supported_fields": list(facet.semantic_fields),
                "field_bindings": field_rows,
                "bound_span_indices": selected_indices,
                "rationale": "Deterministic local evidence fallback after owner unavailability.",
            }
            owner_error = (owner_error + ";deterministic_local_evidence_fallback").strip(";")
    status = str(raw.get("status") or "unresolved").strip().casefold()
    if status not in {"entailed", "partial", "mismatch", "unresolved"}:
        status = "unresolved"
        owner_error = (owner_error + ";invalid_status").strip(";")
    by_index = {
        int(row.get("evidence_index")): row
        for row in rows
        if str(row.get("evidence_index", "")).isdigit()
    }
    bound_claim_ids = _clean_strings(raw.get("bound_claim_ids") or ())
    bound_span_ids = _clean_strings(raw.get("bound_span_ids") or ())
    bound_equation_ids = _clean_strings(raw.get("bound_equation_ids") or ())
    for index in raw.get("bound_claim_indices") or ():
        try:
            row = by_index[int(index)]
        except (KeyError, TypeError, ValueError):
            continue
        bound_claim_ids = _clean_strings(
            (*bound_claim_ids, *(row.get("claim_ids") or ()))
        )
    for index in raw.get("bound_span_indices") or raw.get("exact_excerpt_indices") or ():
        try:
            row = by_index[int(index)]
        except (KeyError, TypeError, ValueError):
            continue
        bound_span_ids = _clean_strings(
            (*bound_span_ids, str(row.get("_excerpt").span_id))
        )
    for index in raw.get("bound_equation_indices") or ():
        try:
            row = by_index[int(index)]
        except (KeyError, TypeError, ValueError):
            continue
        bound_equation_ids = _clean_strings(
            (*bound_equation_ids, *(row.get("equation_ids") or ()))
        )

    exact_excerpts: list[FacetEvidenceExcerptV1] = []
    raw_excerpts = raw.get("exact_excerpts") or raw.get("evidence_excerpts") or ()
    for item in raw_excerpts:
        try:
            excerpt = (
                item
                if isinstance(item, FacetEvidenceExcerptV1)
                else FacetEvidenceExcerptV1.model_validate(item)
            )
        except Exception:
            owner_error = (owner_error + ";invalid_exact_excerpt").strip(";")
            continue
        exact_excerpts.append(excerpt.model_copy(update={"facet_id": facet.facet_id}))
    if not exact_excerpts:
        exact_excerpts = [
            row["_excerpt"].model_copy(update={"facet_id": facet.facet_id})
            for row in rows
            if row["_excerpt"].span_id in set(bound_span_ids)
        ]
    if not bound_span_ids:
        bound_span_ids = _clean_strings(item.span_id for item in exact_excerpts)

    # Field bindings are optional for legacy callers, but the production
    # aligner returns ordinal field proposals.  Resolve each ordinal against
    # this facet's closed evidence rows before constructing the immutable
    # binding; no model-authored repository id is trusted.
    supported_fields = _clean_strings(
        _canonical_facet_field_name(value)
        for value in (raw.get("supported_fields") or ())
    )
    unsupported_fields = _clean_strings(
        _canonical_facet_field_name(value)
        for value in (raw.get("unsupported_fields") or ())
    )
    raw_field_bindings = raw.get("field_bindings") or ()
    field_bindings: list[FacetFieldBindingV1] = []

    def _rows_for_indices(indices: Any) -> tuple[dict[str, Any], ...]:
        selected: list[dict[str, Any]] = []
        for index in indices or ():
            try:
                selected.append(by_index[int(index)])
            except (KeyError, TypeError, ValueError):
                nonlocal owner_error
                owner_error = (owner_error + ";unknown_field_evidence_index").strip(";")
        unique: list[dict[str, Any]] = []
        seen: set[int] = set()
        for row in selected:
            marker = id(row)
            if marker not in seen:
                seen.add(marker)
                unique.append(row)
        return tuple(unique)

    for item in raw_field_bindings:
        raw_item = (
            item.model_dump(mode="python")
            if isinstance(item, BaseModel)
            else dict(item) if isinstance(item, Mapping) else {}
        )
        field_name = _canonical_facet_field_name(raw_item.get("field_name"))
        if field_name not in {
            _canonical_facet_field_name(key)
            for key in (facet.semantic_fields or {})
        }:
            owner_error = (owner_error + ";field_binding_overreach").strip(";")
            continue
        field_status = str(raw_item.get("status") or "unresolved").casefold()
        if field_status not in {"entailed", "partial", "mismatch", "unresolved"}:
            field_status = "unresolved"
            owner_error = (owner_error + ";invalid_field_status").strip(";")
        polarity = str(raw_item.get("polarity") or "unknown").casefold()
        if polarity not in {
            "positive", "negative", "threshold_lt_excludes",
            "threshold_lte_excludes", "threshold_gt_selects",
            "threshold_gte_selects", "conditional", "unknown",
        }:
            polarity = "unknown"
            owner_error = (owner_error + ";invalid_field_polarity").strip(";")
        claim_rows = _rows_for_indices(raw_item.get("bound_claim_indices"))
        fact_rows = _rows_for_indices(raw_item.get("bound_fact_indices"))
        span_rows = _rows_for_indices(
            raw_item.get("bound_span_indices")
            or raw_item.get("exact_excerpt_indices")
        )
        equation_rows = _rows_for_indices(raw_item.get("bound_equation_indices"))
        # A model often selects a fact/claim ordinal but omits the parallel
        # span ordinal.  Resolve the selected evidence rows deterministically
        # before judging the field so the exact source excerpt is retained;
        # this is a representation repair, not a new evidence decision.
        if not span_rows:
            selected_fact_ids = {
                str(fact_id)
                for row in fact_rows
                for fact_id in (row.get("fact_ids") or ())
            }
            selected_claim_ids = {
                str(claim_id)
                for row in claim_rows
                for claim_id in (row.get("claim_ids") or ())
            }
            selected_equation_ids = {
                str(equation_id)
                for row in equation_rows
                for equation_id in (row.get("equation_ids") or ())
            }
            inferred_span_rows = tuple(
                row for row in rows
                if (
                    selected_fact_ids.intersection(str(item) for item in (row.get("fact_ids") or ()))
                    or selected_claim_ids.intersection(str(item) for item in (row.get("claim_ids") or ()))
                    or selected_equation_ids.intersection(str(item) for item in (row.get("equation_ids") or ()))
                )
            )
            if inferred_span_rows:
                span_rows = inferred_span_rows
        field_claim_ids = _clean_strings(
            claim_id for row in claim_rows for claim_id in (row.get("claim_ids") or ())
        )
        field_fact_ids = _clean_strings(
            fact_id for row in fact_rows for fact_id in (row.get("fact_ids") or ())
        )
        # A span/equation row also carries the fact atoms that it exposes; it
        # is safe to include those exact ids when the owner selected the row.
        field_fact_ids = _clean_strings(
            (*field_fact_ids,
             *(fact_id for row in (*span_rows, *equation_rows)
               for fact_id in (row.get("fact_ids") or ())))
        )
        field_span_ids = _clean_strings(
            str(row.get("_excerpt").span_id)
            for row in span_rows
            if row.get("_excerpt") is not None
        )
        field_equation_ids = _clean_strings(
            equation_id
            for row in equation_rows
            for equation_id in (row.get("equation_ids") or ())
        )
        field_excerpts = tuple(
            row["_excerpt"].model_copy(update={"facet_id": facet.facet_id})
            for row in span_rows
            if row.get("_excerpt") is not None
        )
        if field_status in {"entailed", "partial"} and not (
            field_claim_ids or field_fact_ids or field_span_ids or field_equation_ids
        ):
            # Positive status without any concrete reference is not a partial
            # fact; retain the field row as unresolved for later local or
            # external repair.
            field_status = "unresolved"
            owner_error = (owner_error + f";field_positive_without_evidence:{field_name}").strip(";")
        if field_status in {"entailed", "partial"} and (
            field_span_ids or field_claim_ids or field_fact_ids or field_equation_ids
        ) and not field_excerpts:
            # Keep the selected ids, but make the representation gap visible
            # and non-entailed until an exact excerpt is available.
            if field_status == "entailed":
                field_status = "partial"
            owner_error = (owner_error + f";field_missing_exact_excerpt:{field_name}").strip(";")
        polarity_conflict = _polarity_conflict(polarity, (*claim_rows, *fact_rows, *span_rows, *equation_rows))
        if polarity_conflict:
            field_status = "mismatch"
            owner_error = (owner_error + ";" + polarity_conflict).strip(";")
        field_bindings.append(FacetFieldBindingV1(
            field_name=field_name,
            status=field_status,  # type: ignore[arg-type]
            polarity=polarity,  # type: ignore[arg-type]
            bound_claim_ids=field_claim_ids,
            bound_fact_ids=field_fact_ids,
            bound_span_ids=field_span_ids,
            bound_equation_ids=field_equation_ids,
            exact_excerpts=field_excerpts,
            active_path_conditions=_clean_strings(
                raw_item.get("active_path_conditions") or ()
            ),
            unsupported_reason=str(raw_item.get("unsupported_reason") or ""),
        ))
    if field_bindings:
        # Aggregate status is harness-derived.  The model's facet-level status
        # is ignored whenever a field ledger is available.
        field_names = {
            _canonical_facet_field_name(key)
            for key in (facet.semantic_fields or {})
        }
        by_field = {item.field_name: item for item in field_bindings}
        supported_fields = _clean_strings(
            field_name for field_name, binding in by_field.items()
            if binding.status in {"entailed", "partial"}
        )
        unsupported_fields = _clean_strings(
            field_name for field_name in field_names
            if field_name not in set(supported_fields)
        )
        states = [by_field.get(name, FacetFieldBindingV1(field_name=name)).status for name in field_names]
        if field_names and all(state == "entailed" for state in states):
            status = "entailed"
        elif any(state in {"entailed", "partial"} for state in states):
            status = "partial"
        elif any(state == "mismatch" for state in states):
            status = "mismatch"
        else:
            status = "unresolved"
        bound_claim_ids = _clean_strings(
            (*bound_claim_ids,
             *(value for binding in field_bindings for value in binding.bound_claim_ids))
        )
        bound_span_ids = _clean_strings(
            (*bound_span_ids,
             *(value for binding in field_bindings for value in binding.bound_span_ids))
        )
        bound_equation_ids = _clean_strings(
            (*bound_equation_ids,
             *(value for binding in field_bindings for value in binding.bound_equation_ids))
        )
        exact_excerpts = list(dict.fromkeys([
            *exact_excerpts,
            *(excerpt for binding in field_bindings for excerpt in binding.exact_excerpts),
        ]))
    else:
        for field_name in dict.fromkeys((*supported_fields, *unsupported_fields)):
            if field_name in supported_fields:
                field_status = "entailed" if status == "entailed" else "partial"
                field_ids = {
                    "bound_claim_ids": bound_claim_ids,
                    "bound_span_ids": bound_span_ids,
                    "bound_equation_ids": bound_equation_ids,
                }
                field_bindings.append(FacetFieldBindingV1(
                    field_name=field_name,
                    status=field_status,
                    polarity="unknown",
                    bound_claim_ids=tuple(sorted(field_ids["bound_claim_ids"])),
                    bound_span_ids=tuple(sorted(field_ids["bound_span_ids"])),
                    bound_equation_ids=tuple(sorted(field_ids["bound_equation_ids"])),
                    exact_excerpts=tuple(exact_excerpts),
                ))
            else:
                field_bindings.append(FacetFieldBindingV1(
                    field_name=field_name,
                    status="mismatch" if status == "mismatch" else "unresolved",
                    polarity="unknown",
                    unsupported_reason="owner marked this semantic field unsupported",
                ))

    return FacetEvidenceAlignmentV1(
        facet_id=facet.facet_id,
        alignment_id=str(raw.get("alignment_id") or f"alignment:{facet.facet_id}"),
        clause_id=facet.clause_id,
        status=status,  # type: ignore[arg-type]
        supported_fields=supported_fields,
        unsupported_fields=unsupported_fields,
        field_bindings=tuple(field_bindings),
        bound_claim_ids=bound_claim_ids,
        bound_span_ids=bound_span_ids,
        bound_equation_ids=bound_equation_ids,
        exact_excerpts=tuple(exact_excerpts),
        search_terms=_clean_strings(raw.get("search_terms") or facet.search_terms),
        rationale=str(raw.get("rationale") or ""),
        schema_failures=_clean_strings(
            (*((raw.get("schema_failures") or ())), *((
                owner_error,
            ) if owner_error else ()))
        ),
    )


def _alignment_from_proposition_judge(
    verdict: Any,
    *,
    facet: AuthorMechanismFacetV1,
    candidate_rows: tuple[dict[str, Any], ...],
) -> FacetEvidenceAlignmentV1:
    selected = _select_evidence_rows(facet, candidate_rows)
    raw_status = str(getattr(verdict, "status", "") or "unresolved")
    rationale = str(getattr(verdict, "rationale", "") or "").strip()
    supported_fields = list(getattr(verdict, "supported_fields", ()) or ())
    unsupported_fields = list(getattr(verdict, "unsupported_fields", ()) or ())
    if raw_status == "unsupported":
        has_fields = bool(supported_fields or unsupported_fields)
        if not rationale and not has_fields:
            status = "unresolved"
        elif unsupported_fields or (rationale and has_fields):
            status = "mismatch"
        elif rationale:
            status = "mismatch"
        else:
            status = "unresolved"
    else:
        status = {
            "ambiguous": "unresolved",
            "not_checked": "unresolved",
        }.get(raw_status, raw_status)
    if status not in {"entailed", "partial", "mismatch", "unresolved"}:
        status = "unresolved"
    return _alignment_from_owner(
        {
            "status": status,
            "supported_fields": supported_fields,
            "unsupported_fields": unsupported_fields,
            "bound_claim_ids": [
                claim_id
                for row in selected
                for claim_id in (row.get("claim_ids") or ())
            ],
            "bound_span_ids": [
                str(row["_excerpt"].span_id) for row in selected
            ],
            "bound_equation_ids": [
                equation_id
                for row in selected
                for equation_id in (row.get("equation_ids") or ())
            ],
            "rationale": str(getattr(verdict, "rationale", "") or ""),
        },
        facet=facet,
        rows=candidate_rows,
    )


def _default_proposition_architect(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
) -> Callable[..., Any]:
    from code2paper.agentic.method_proposition_provider import (
        build_method_proposition_architect,
    )

    return build_method_proposition_architect(
        llm_config,
        llm_caller=llm_caller,
    )


def _default_evidence_judge(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None,
) -> Callable[[dict[str, Any]], Any]:
    # Reuse the existing independent SEMANTIC_VERIFIER owner.  It sees exact
    # excerpts and evidence-side semantics, while this module owns the facet
    # identity and policy merge around its verdict.
    from code2paper.agentic.method_proposition_evidence_provider import (
        build_method_proposition_evidence_judge,
    )

    return build_method_proposition_evidence_judge(
        llm_config,
        llm_caller=llm_caller,
    )


def build_method_argument_facet_evidence_aligner(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
) -> Callable[[dict[str, Any]], Any]:
    """Build an ordinal closed-set alignment owner using SEMANTIC_VERIFIER.

    This narrow adapter is useful when a caller wants the new alignment
    response schema rather than the legacy proposition verdict schema.  The
    normal product path uses :func:`_default_evidence_judge` so existing
    evidence-provider safeguards remain shared.
    """

    config = apply_role_config(llm_config, SEMANTIC_VERIFIER).model_copy(
        update={
            "temperature": 0.0,
            "top_p": None,
            "top_k": None,
            "max_output_tokens": min(llm_config.max_output_tokens, 2048),
            "retry_max_attempts": 1,
            "cache": False,
        }
    )
    caller = llm_caller or (lambda cfg, request: LLMClient(cfg).complete(request))
    traces: list[dict[str, Any]] = []

    def align(payload: dict[str, Any]) -> Any:
        request = LLMRequest(
            prompt_template_id="method_argument_facet_alignment_v1",
            prompt=(
                "Return only JSON matching the facet alignment batch schema. "
                "Return one field_bindings item for every supplied semantic "
                "field using only subject, operation, inputs, outputs, "
                "conditions, effects, interface, formula_goal, and guarantee. "
                "Judge each field only against the supplied exact repository "
                "evidence. Use ordinal evidence indices; never invent ids. "
                "For each field return status, polarity, bound_claim_indices, "
                "bound_fact_indices, bound_span_indices, "
                "bound_equation_indices, exact_excerpt_indices, and active "
                "path conditions. The harness computes the aggregate facet "
                "status; do not upgrade a compound facet because one field is "
                "supported."
            ),
            input_payload=payload,
            schema_name="FacetEvidenceAlignmentProposalBatchV1",
            response_json_schema=json_schema_for(
                FacetEvidenceAlignmentProposalBatchV1
            ),
        )
        response = caller(config, request)
        trace: dict[str, Any] = {
            "role": SEMANTIC_VERIFIER,
            "prompt_template_id": request.prompt_template_id,
            "response_hash": response.response_hash,
            "finish_reason": response.finish_reason,
            "blocked_reason": response.blocked_reason,
        }
        traces.append(trace)
        if response.blocked_reason:
            trace["error"] = "blocked"
            return {}
        parsed, recovery, error = try_parse_structured_response_with_trace(
            response.text,
            FacetEvidenceAlignmentProposalBatchV1,
        )
        trace["representation_recovery"] = recovery.model_dump(mode="json")
        if parsed is None:
            trace["error"] = error or "schema_failed"
            return {}
        trace["result"] = parsed.model_dump(mode="json")
        return parsed

    align.traces = traces  # type: ignore[attr-defined]
    return align


class MethodArgumentFacetAlignmentResultV1(BaseModel):
    """Closed result of decomposition, alignment, and Candidate policy merge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facets: tuple[AuthorMechanismFacetV1, ...] = Field(default_factory=tuple)
    alignments: tuple[FacetEvidenceAlignmentV1, ...] = Field(default_factory=tuple)
    policies: tuple[CandidateFacetPolicyV1, ...] = Field(default_factory=tuple)
    schema_failures: tuple[str, ...] = Field(default_factory=tuple)
    traces: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed_and_digest(self) -> "MethodArgumentFacetAlignmentResultV1":
        facet_ids = [item.facet_id for item in self.facets]
        if len(facet_ids) != len(set(facet_ids)):
            raise ValueError("facet alignment result contains duplicate facet ids")
        if set(item.facet_id for item in self.alignments) - set(facet_ids):
            raise ValueError("facet alignment result contains an unknown facet")
        if set(item.facet_id for item in self.policies) - set(facet_ids):
            raise ValueError("facet policy result contains an unknown facet")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self

    def __iter__(self):
        """Allow the convenient ``facets, alignments, policies = result`` form."""

        return iter((self.facets, self.alignments, self.policies))

    @property
    def facet_by_id(self) -> dict[str, AuthorMechanismFacetV1]:
        return {item.facet_id: item for item in self.facets}

    @property
    def policy_by_facet_id(self) -> dict[str, CandidateFacetPolicyV1]:
        return {item.facet_id: item for item in self.policies}


def _known_ids(
    *,
    claims: AtomicClaimSetV3 | Iterable[Any] | None,
    facts: CodeFactSetV1 | Iterable[Any] | None,
    evidence_packets: EvidencePacketSetV3 | Iterable[Any] | None,
    equations: EquationClaimSetV1 | Iterable[Any] | None,
    known_claim_ids: Iterable[str],
    known_span_ids: Iterable[str],
    known_equation_ids: Iterable[str],
) -> tuple[set[str], set[str], set[str], set[str], dict[str, Any]]:
    claim_items = _claim_list(claims)
    fact_items = _fact_list(facts)
    packet_items = _packet_list(evidence_packets)
    equation_items = _equation_list(equations)
    claim_ids = set(known_claim_ids) | {
        _claim_id(item) for item in claim_items if _claim_id(item)
    }
    span_by_id = {
        _span_id(item): item for item in _span_list(packet_items) if _span_id(item)
    }
    span_ids = set(known_span_ids) | set(span_by_id)
    equation_ids = set(known_equation_ids) | {
        _equation_id(item) for item in equation_items if _equation_id(item)
    }
    fact_ids = {
        _fact_id(item) for item in fact_items if _fact_id(item)
    }
    return claim_ids, span_ids, equation_ids, fact_ids, span_by_id


def _license_by_clause(
    *,
    briefs: Iterable[MethodArgumentBriefV1],
    deterministic_licenses: Mapping[str, AuthorClauseLicenseV1]
    | Iterable[AuthorClauseLicenseV1]
    | None,
) -> dict[str, AuthorClauseLicenseV1]:
    result = {
        clause.clause_id: clause
        for brief in briefs
        for clause in brief.clauses
    }
    if deterministic_licenses is None:
        return result
    if isinstance(deterministic_licenses, Mapping):
        result.update(
            {
                str(key): value
                for key, value in deterministic_licenses.items()
                if isinstance(value, AuthorClauseLicenseV1)
            }
        )
    else:
        result.update(
            {
                item.clause_id: item
                for item in deterministic_licenses
                if isinstance(item, AuthorClauseLicenseV1)
            }
        )
    return result


def _merge_facet_alignment_policy(
    facets: tuple[AuthorMechanismFacetV1, ...],
    alignments: tuple[FacetEvidenceAlignmentV1, ...],
    *,
    briefs: tuple[MethodArgumentBriefV1, ...],
    claims: AtomicClaimSetV3 | Iterable[Any] | None,
    facts: CodeFactSetV1 | Iterable[Any] | None,
    evidence_packets: EvidencePacketSetV3 | Iterable[Any] | None,
    equations: EquationClaimSetV1 | Iterable[Any] | None,
    deterministic_licenses: Mapping[str, AuthorClauseLicenseV1]
    | Iterable[AuthorClauseLicenseV1]
    | None,
    known_claim_ids: Iterable[str],
    known_span_ids: Iterable[str],
    known_equation_ids: Iterable[str],
) -> tuple[
    tuple[FacetEvidenceAlignmentV1, ...],
    tuple[CandidateFacetPolicyV1, ...],
    tuple[str, ...],
]:
    known_claims, known_spans, known_equations, known_facts, span_by_id = _known_ids(
        claims=claims,
        facts=facts,
        evidence_packets=evidence_packets,
        equations=equations,
        known_claim_ids=known_claim_ids,
        known_span_ids=known_span_ids,
        known_equation_ids=known_equation_ids,
    )
    facet_by_id = {facet.facet_id: facet for facet in facets}
    alignment_by_facet: dict[str, FacetEvidenceAlignmentV1] = {}
    failures: list[str] = []
    for alignment in alignments:
        if alignment.facet_id not in facet_by_id:
            failures.append(f"{alignment.facet_id}:unknown_facet_id")
            continue
        if alignment.facet_id in alignment_by_facet:
            failures.append(f"{alignment.facet_id}:duplicate_alignment")
            continue
        alignment_by_facet[alignment.facet_id] = alignment

    license_by_clause = _license_by_clause(
        briefs=briefs,
        deterministic_licenses=deterministic_licenses,
    )
    normalized_alignments: list[FacetEvidenceAlignmentV1] = []
    policies: list[CandidateFacetPolicyV1] = []
    for facet in facets:
        original = alignment_by_facet.get(
            facet.facet_id,
            FacetEvidenceAlignmentV1(
                facet_id=facet.facet_id,
                alignment_id=f"alignment:{facet.facet_id}",
                clause_id=facet.clause_id,
                status="unresolved",
                rationale="No field-level alignment proposal was returned.",
                schema_failures=("alignment_missing",),
            ),
        )
        local_failures = list(original.schema_failures)
        if original.clause_id and original.clause_id != facet.clause_id:
            local_failures.append("clause_id_mismatch")

        facet_fields = {
            _canonical_facet_field_name(field_name)
            for field_name in facet.semantic_fields
        }
        supported = {
            _canonical_facet_field_name(field_name)
            for field_name in original.supported_fields
        }
        unsupported = {
            _canonical_facet_field_name(field_name)
            for field_name in original.unsupported_fields
        }
        overreach = (supported | unsupported) - facet_fields
        if overreach:
            local_failures.append(
                "field_overreach:" + ",".join(sorted(overreach))
            )
        if supported & unsupported:
            local_failures.append(
                "field_in_both_supported_and_unsupported:"
                + ",".join(sorted(supported & unsupported))
            )

        bound_claim_ids = set(original.bound_claim_ids)
        bound_span_ids = set(original.bound_span_ids)
        bound_equation_ids = set(original.bound_equation_ids)
        unknown_claims = bound_claim_ids - known_claims
        unknown_spans = bound_span_ids - known_spans
        unknown_equations = bound_equation_ids - known_equations
        if unknown_claims:
            local_failures.append(
                "unknown_claim_ids:" + ",".join(sorted(unknown_claims))
            )
        if unknown_spans:
            local_failures.append(
                "unknown_span_ids:" + ",".join(sorted(unknown_spans))
            )
        if unknown_equations:
            local_failures.append(
                "unknown_equation_ids:" + ",".join(sorted(unknown_equations))
            )
        field_bindings = tuple(getattr(original, "field_bindings", ()) or ())
        original_status = original.status
        if field_bindings:
            field_by_name = {
                _canonical_facet_field_name(binding.field_name): binding
                for binding in field_bindings
            }
            field_states = [
                field_by_name.get(field_name, FacetFieldBindingV1(field_name=field_name)).status
                for field_name in facet_fields
            ]
            if field_states and all(state == "entailed" for state in field_states):
                original_status = "entailed"
            elif any(state in {"entailed", "partial"} for state in field_states):
                original_status = "partial"
            elif any(state == "mismatch" for state in field_states):
                original_status = "mismatch"
            else:
                original_status = "unresolved"

        excerpt_by_span: dict[str, FacetEvidenceExcerptV1] = {}
        valid_excerpts: list[FacetEvidenceExcerptV1] = []
        for excerpt in original.exact_excerpts:
            if excerpt.span_id in excerpt_by_span:
                local_failures.append(f"duplicate_excerpt:{excerpt.span_id}")
                continue
            excerpt_by_span[excerpt.span_id] = excerpt
            if excerpt.facet_id and excerpt.facet_id != facet.facet_id:
                local_failures.append(f"excerpt_facet_id_mismatch:{excerpt.span_id}")
            excerpt_valid = True
            if excerpt.span_id not in known_spans or excerpt.span_id not in span_by_id:
                local_failures.append(f"unknown_excerpt_span_id:{excerpt.span_id}")
                continue
            source = span_by_id[excerpt.span_id]
            source_values = {
                "path": str(getattr(source, "path", "") or ""),
                "symbol": str(getattr(source, "symbol", "") or ""),
                "line_start": int(getattr(source, "line_start", 0) or 0),
                "line_end": int(getattr(source, "line_end", 0) or 0),
                "exact_excerpt": str(
                    getattr(source, "exact_excerpt", "") or ""
                ),
                "excerpt_digest": str(
                    getattr(source, "excerpt_digest", "") or ""
                ),
            }
            if not excerpt.exact_excerpt:
                local_failures.append(f"missing_exact_excerpt:{excerpt.span_id}")
                excerpt_valid = False
            for key, expected in source_values.items():
                actual = getattr(excerpt, key)
                if actual != expected:
                    local_failures.append(
                        f"excerpt_{key}_mismatch:{excerpt.span_id}"
                    )
                    excerpt_valid = False
            if excerpt_valid:
                valid_excerpts.append(excerpt)

        excerpt_span_ids = set(excerpt_by_span)
        if bound_span_ids != excerpt_span_ids:
            if bound_span_ids or excerpt_span_ids:
                local_failures.append("bound_span_excerpt_set_mismatch")
        if original_status in {"entailed", "partial"} and not (
            bound_claim_ids or bound_span_ids or bound_equation_ids
        ):
            local_failures.append("positive_alignment_has_no_evidence")
        if original_status in {"entailed", "partial"} and not original.exact_excerpts:
            local_failures.append("positive_alignment_missing_exact_excerpts")
        if original_status == "entailed":
            if not facet_fields:
                local_failures.append("entailed_alignment_has_no_semantic_fields")
            if supported != facet_fields or unsupported:
                local_failures.append("entailed_alignment_not_field_closed")
        if original_status == "partial" and not supported:
            local_failures.append("partial_alignment_has_no_supported_fields")

        # Code excerpts cannot entail author motivation, novelty, literature,
        # or a theory-level guarantee.  The owner must leave those facets
        # unresolved/author-scoped even if the same clause has code evidence.
        if facet.facet_kind in {"motivation", "guarantee"} and original_status == "entailed":
            local_failures.append(
                f"{facet.facet_kind}_cannot_be_code_entailed"
            )
        if facet.facet_kind == "formula" and original_status == "entailed" and not (
            bound_equation_ids
            or any(excerpt.equation_ids for excerpt in original.exact_excerpts)
        ):
            local_failures.append("formula_alignment_missing_equation_atom")

        # Remove only unknown ids.  A known claim/span/equation remains useful
        # Candidate evidence even when another field failed a closure check.
        bound_claim_ids -= unknown_claims
        bound_span_ids -= unknown_spans
        bound_equation_ids -= unknown_equations
        if field_bindings:
            # Aggregate status is derived from the normalized field ledger;
            # never trust a facet-level ``entailed`` token that hides an
            # unresolved guarantee/condition.
            field_by_name = {binding.field_name: binding for binding in field_bindings}
            field_states = [
                field_by_name.get(field_name, FacetFieldBindingV1(field_name=field_name)).status
                for field_name in facet_fields
            ]
            if field_states and all(state == "entailed" for state in field_states):
                original_status = "entailed"
            elif any(state in {"entailed", "partial"} for state in field_states):
                original_status = "partial"
            elif any(state == "mismatch" for state in field_states):
                original_status = "mismatch"
            else:
                original_status = "unresolved"
        else:
            original_status = original.status
        supported &= facet_fields
        unsupported &= facet_fields
        # A field not mentioned by the owner is unresolved, not a mismatch.
        # Preserve an explicit mismatch declaration so author/code conflicts
        # remain visible in Candidate review.
        unsupported.update(facet_fields - supported - unsupported)

        normalized_status: FacetAlignmentStatusV1 = original_status  # type: ignore[assignment]
        if local_failures:
            if original_status == "mismatch":
                normalized_status = "mismatch"
            elif supported:
                # Keep partial truth for Candidate, while any schema failure
                # still prevents deterministic Verified authorization below.
                normalized_status = "partial"
            else:
                normalized_status = "unresolved"

        normalized_field_bindings: list[FacetFieldBindingV1] = []
        for binding in (getattr(original, "field_bindings", ()) or ()):
            field_name = _canonical_facet_field_name(binding.field_name)
            if field_name not in facet_fields:
                local_failures.append(f"field_overreach:{field_name}")
                continue
            field_claim_ids = set(binding.bound_claim_ids)
            field_fact_ids = set(binding.bound_fact_ids)
            field_span_ids = set(binding.bound_span_ids)
            field_equation_ids = set(binding.bound_equation_ids)
            bad_claims = field_claim_ids - known_claims
            bad_facts = field_fact_ids - known_facts
            bad_spans = field_span_ids - known_spans
            bad_equations = field_equation_ids - known_equations
            if bad_claims:
                local_failures.append(
                    f"unknown_field_claim_ids:{field_name}:{','.join(sorted(bad_claims))}"
                )
                field_claim_ids -= bad_claims
            if bad_facts:
                local_failures.append(
                    f"unknown_field_fact_ids:{field_name}:{','.join(sorted(bad_facts))}"
                )
                field_fact_ids -= bad_facts
            if bad_spans:
                local_failures.append(
                    f"unknown_field_span_ids:{field_name}:{','.join(sorted(bad_spans))}"
                )
                field_span_ids -= bad_spans
            if bad_equations:
                local_failures.append(
                    f"unknown_field_equation_ids:{field_name}:{','.join(sorted(bad_equations))}"
                )
                field_equation_ids -= bad_equations
            valid_field_excerpts = tuple(
                excerpt for excerpt in binding.exact_excerpts
                if excerpt.span_id in known_spans and excerpt.span_id in span_by_id
            )
            normalized_field_bindings.append(binding.model_copy(update={
                "field_name": field_name,
                "bound_claim_ids": tuple(sorted(field_claim_ids)),
                "bound_fact_ids": tuple(sorted(field_fact_ids)),
                "bound_span_ids": tuple(sorted(field_span_ids)),
                "bound_equation_ids": tuple(sorted(field_equation_ids)),
                "exact_excerpts": valid_field_excerpts,
            }))
        field_bindings = tuple(normalized_field_bindings)
        if not field_bindings:
            field_bindings = tuple(
                FacetFieldBindingV1(
                    field_name=field_name,
                    status=(
                        "mismatch" if field_name in unsupported and original_status == "mismatch"
                        else "entailed" if field_name in supported and normalized_status == "entailed"
                        else "partial" if field_name in supported
                        else "unresolved"
                    ),
                    polarity="unknown",
                    bound_claim_ids=tuple(sorted(bound_claim_ids)) if field_name in supported else (),
                    bound_span_ids=tuple(sorted(bound_span_ids)) if field_name in supported else (),
                    bound_equation_ids=tuple(sorted(bound_equation_ids)) if field_name in supported else (),
                    exact_excerpts=tuple(valid_excerpts) if field_name in supported else (),
                    unsupported_reason=(
                        "owner marked this semantic field unsupported"
                        if field_name in unsupported else ""
                    ),
                )
                for field_name in sorted(facet_fields)
            )

        normalized = FacetEvidenceAlignmentV1(
            facet_id=facet.facet_id,
            alignment_id=original.alignment_id,
            clause_id=facet.clause_id,
            status=normalized_status,
            supported_fields=_clean_strings(supported),
            unsupported_fields=_clean_strings(unsupported),
            field_bindings=field_bindings,
            bound_claim_ids=_clean_strings(bound_claim_ids),
            bound_span_ids=_clean_strings(bound_span_ids),
            bound_equation_ids=_clean_strings(bound_equation_ids),
            exact_excerpts=tuple(valid_excerpts),
            search_terms=original.search_terms,
            rationale=original.rationale,
            schema_failures=_clean_strings(local_failures),
        )
        normalized_alignments.append(normalized)
        failures.extend(
            f"{facet.facet_id}:{failure}" for failure in local_failures
        )

        license_record = license_by_clause.get(facet.clause_id)
        deterministic_verified = bool(
            license_record is not None
            and license_record.license == "positively_licensed"
            and normalized_status == "entailed"
            and not local_failures
            and (
                set(license_record.bound_claim_ids).intersection(
                    normalized.bound_claim_ids
                )
                or set(license_record.bound_equation_ids).intersection(
                    normalized.bound_equation_ids
                )
                or set(license_record.bound_span_ids).intersection(
                    normalized.bound_span_ids
                )
            )
        )
        if normalized_status == "mismatch":
            prose_mode = "mismatch_statement"
            severity = "critical"
        elif normalized_status == "entailed":
            prose_mode = "repository_statement"
            severity = "none" if deterministic_verified else "minor"
        else:
            prose_mode = "author_specification"
            severity = "major" if normalized_status == "partial" else "major"
        rationale = normalized.rationale
        if local_failures:
            rationale = (
                (rationale + " " if rationale else "")
                + "Fail-closed alignment: "
                + "; ".join(_clean_strings(local_failures)[:8])
            )
        policies.append(
            CandidateFacetPolicyV1(
                facet_id=facet.facet_id,
                policy_id=f"policy:{facet.facet_id}",
                alignment_id=normalized.alignment_id,
                clause_id=facet.clause_id,
                alignment_status=normalized_status,
                prose_mode=prose_mode,  # type: ignore[arg-type]
                candidate_allowed=True,
                verified_directly_allowed=deterministic_verified,
                review_severity=severity,  # type: ignore[arg-type]
                supported_fields=normalized.supported_fields,
                unsupported_fields=normalized.unsupported_fields,
                field_bindings=normalized.field_bindings,
                bound_claim_ids=normalized.bound_claim_ids,
                bound_span_ids=normalized.bound_span_ids,
                bound_equation_ids=normalized.bound_equation_ids,
                evidence_digest=normalized.evidence_digest,
                rationale=rationale,
                schema_failures=normalized.schema_failures,
            )
        )
    return tuple(normalized_alignments), tuple(policies), tuple(
        dict.fromkeys(failures)
    )


def merge_facet_alignment_policy(
    facets: Iterable[AuthorMechanismFacetV1],
    alignments: Iterable[FacetEvidenceAlignmentV1],
    *,
    briefs: MethodArgumentBriefSetV1
    | Iterable[MethodArgumentBriefV1]
    | None = None,
    claims: AtomicClaimSetV3 | Iterable[Any] | None = None,
    facts: CodeFactSetV1 | Iterable[Any] | None = None,
    evidence_packets: EvidencePacketSetV3 | Iterable[Any] | None = None,
    equations: EquationClaimSetV1 | Iterable[Any] | None = None,
    deterministic_licenses: Mapping[str, AuthorClauseLicenseV1]
    | Iterable[AuthorClauseLicenseV1]
    | None = None,
    known_claim_ids: Iterable[str] = (),
    known_span_ids: Iterable[str] = (),
    known_equation_ids: Iterable[str] = (),
) -> tuple[CandidateFacetPolicyV1, ...]:
    """Validate a closed alignment proposal and return Candidate policies.

    Missing closure inputs are intentionally not inferred from the proposal.
    A caller that supplies bound ids must provide the corresponding repository
    set (directly or through claims/packets/equations), otherwise those ids
    are treated as unknown and the facet stays unresolved.
    """

    facet_items = tuple(facets)
    alignment_items = tuple(alignments)
    brief_items = _brief_list(briefs)
    _, policies, _ = _merge_facet_alignment_policy(
        facet_items,
        alignment_items,
        briefs=brief_items,
        claims=claims,
        facts=facts,
        evidence_packets=evidence_packets,
        equations=equations,
        deterministic_licenses=deterministic_licenses,
        known_claim_ids=known_claim_ids,
        known_span_ids=known_span_ids,
        known_equation_ids=known_equation_ids,
    )
    return policies


def bind_facets_to_argument_briefs(
    briefs: MethodArgumentBriefSetV1,
    *,
    facets: Iterable[AuthorMechanismFacetV1],
    alignments: Iterable[FacetEvidenceAlignmentV1] = (),
    policies: Iterable[CandidateFacetPolicyV1] = (),
) -> MethodArgumentBriefSetV1:
    """Add only closed facet references/digest to an immutable brief set."""

    facet_items = tuple(facets)
    alignment_items = tuple(alignments)
    policy_items = tuple(policies)
    facets_by_brief: dict[str, list[AuthorMechanismFacetV1]] = {}
    for facet in facet_items:
        if facet.brief_id:
            facets_by_brief.setdefault(facet.brief_id, []).append(facet)
    alignment_by_facet = {item.facet_id: item for item in alignment_items}
    policy_by_facet = {item.facet_id: item for item in policy_items}
    updated: list[MethodArgumentBriefV1] = []
    for brief in briefs.briefs:
        selected = tuple(facets_by_brief.get(brief.brief_id, ()))
        selected_ids = tuple(item.facet_id for item in selected)
        selected_alignment_ids = tuple(
            alignment_by_facet[item].alignment_id
            for item in selected_ids
            if item in alignment_by_facet
        )
        selected_policy_ids = tuple(
            policy_by_facet[item].policy_id
            for item in selected_ids
            if item in policy_by_facet
        )
        facet_digest = _digest(
            {
                "facet_ids": list(selected_ids),
                "facet_alignment_ids": list(selected_alignment_ids),
                "facet_policy_ids": list(selected_policy_ids),
            }
        ) if selected_ids else ""
        updated.append(
            brief.model_copy(
                update={
                    "facet_ids": selected_ids,
                    "facet_alignment_ids": selected_alignment_ids,
                    "facet_policy_ids": selected_policy_ids,
                    "facet_digest": facet_digest,
                }
            )
        )
    return briefs.model_copy(update={"briefs": tuple(updated)})


def build_mechanism_authoring_packet(
    *,
    briefs: Iterable[MethodArgumentBriefV1] = (),
    facets: Iterable[AuthorMechanismFacetV1] = (),
    policies: Iterable[CandidateFacetPolicyV1] = (),
    alignments: Iterable[FacetEvidenceAlignmentV1] = (),
    story_node_id: str = "",
    formula_packages: Iterable[Mapping[str, Any]] = (),
    required_facet_ids: Iterable[str] = (),
    organization_seed: str = "",
) -> MechanismAuthoringPacketV1:
    """Project facets/policies/evidence into the Writer's authoring packet."""

    brief_items = tuple(briefs)
    facet_items = tuple(facets)
    policy_items = tuple(policies)
    alignment_items = tuple(alignments)
    policy_by_facet = {item.facet_id: item for item in policy_items}
    excerpt_by_key: dict[tuple[str, str], FacetEvidenceExcerptV1] = {}
    for alignment in alignment_items:
        for excerpt in alignment.exact_excerpts:
            key = (alignment.facet_id, excerpt.span_id)
            excerpt_by_key[key] = excerpt.model_copy(
                update={"facet_id": alignment.facet_id}
            )
    conditions: list[str] = []
    interfaces: list[str] = []
    search_terms: dict[str, tuple[str, ...]] = {}
    for facet in facet_items:
        field_values = facet.semantic_fields
        for key in ("condition", "conditions", "assumption", "assumptions"):
            value = field_values.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                conditions.extend(str(item) for item in value)
            else:
                conditions.append(str(value))
        for key in ("interface", "inputs", "outputs"):
            value = field_values.get(key)
            if value is None:
                continue
            values = value if isinstance(value, (list, tuple, set)) else (value,)
            interfaces.extend(str(item) for item in values)
        search_terms[facet.facet_id] = facet.search_terms
    required = _clean_strings(required_facet_ids) or tuple(
        facet.facet_id for facet in facet_items if facet.required
    )
    brief_ids = _clean_strings(
        item.brief_id for item in brief_items if item.brief_id
    ) or _clean_strings(
        item.brief_id for item in facet_items if item.brief_id
    )
    return MechanismAuthoringPacketV1(
        story_node_id=story_node_id,
        brief_ids=brief_ids,
        facets=facet_items,
        facet_policies=tuple(
            policy_by_facet[facet.facet_id]
            for facet in facet_items
            if facet.facet_id in policy_by_facet
        ),
        exact_evidence_excerpts=tuple(excerpt_by_key.values()),
        formula_packages=tuple(dict(item) for item in formula_packages),
        applicable_conditions=_clean_strings(conditions),
        interfaces=_clean_strings(interfaces),
        required_facet_ids=required,
        search_terms_by_facet_id=search_terms,
        organization_seed=organization_seed.strip(),
    )


def decompose_and_align_argument_facets(
    *,
    briefs: MethodArgumentBriefSetV1
    | Iterable[MethodArgumentBriefV1]
    | None = None,
    argument_briefs: MethodArgumentBriefSetV1
    | Iterable[MethodArgumentBriefV1]
    | None = None,
    claims: AtomicClaimSetV3 | Iterable[Any] | None = None,
    facts: CodeFactSetV1 | Iterable[Any] | None = None,
    evidence_packets: EvidencePacketSetV3 | Iterable[Any] | None = None,
    packets: EvidencePacketSetV3 | Iterable[Any] | None = None,
    equations: EquationClaimSetV1 | Iterable[Any] | None = None,
    facet_decomposer: Callable[[dict[str, Any]], Any] | None = None,
    proposition_architect: Callable[..., Any] | None = None,
    evidence_aligner: Callable[[dict[str, Any]], Any] | None = None,
    semantic_verifier: Callable[[dict[str, Any]], Any] | None = None,
    evidence_judge: Callable[[dict[str, Any]], Any] | None = None,
    llm_config: LLMConfig | None = None,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    deterministic_licenses: Mapping[str, AuthorClauseLicenseV1]
    | Iterable[AuthorClauseLicenseV1]
    | None = None,
    intent_graph: IntentObligationGraphV2 | None = None,
) -> MethodArgumentFacetAlignmentResultV1:
    """Decompose briefs, align fields to exact evidence, and merge policy."""

    brief_items = _brief_list(briefs if briefs is not None else argument_briefs)
    claim_items = _claim_list(claims)
    fact_items = _fact_list(facts)
    equation_items = _equation_list(equations)
    packet_items = _packet_list(
        evidence_packets if evidence_packets is not None else packets
    )
    schema_failures: list[str] = []
    traces: list[dict[str, Any]] = []

    if facet_decomposer is None and proposition_architect is None and llm_config is not None:
        proposition_architect = _default_proposition_architect(
            llm_config,
            llm_caller=llm_caller,
        )
    if (
        evidence_aligner is None
        and semantic_verifier is None
        and evidence_judge is None
        and llm_config is not None
    ):
        # The field-level contract is the production default.  The legacy
        # proposition judge remains available only when explicitly injected
        # by a caller, so an aggregate LLM verdict cannot upgrade a compound
        # facet before the harness has checked each field.
        evidence_aligner = build_method_argument_facet_evidence_aligner(
            llm_config,
            llm_caller=llm_caller,
        )
    if evidence_aligner is None:
        evidence_aligner = semantic_verifier
    if evidence_aligner is None and evidence_judge is None and llm_config is not None:
        # Kept as an explicit opt-in path for callers that need ordinal
        # bindings.  The default above intentionally reuses the mature
        # proposition evidence provider.
        evidence_aligner = build_method_argument_facet_evidence_aligner(
            llm_config,
            llm_caller=llm_caller,
        )

    facets: list[AuthorMechanismFacetV1] = []
    candidate_rows_by_facet: dict[str, tuple[dict[str, Any], ...]] = {}
    obligation_source_fields = _obligation_source_field_map(intent_graph)
    brief_source_fields = {
        brief.brief_id: _brief_source_field(brief, obligation_source_fields)
        for brief in brief_items
    }
    for brief in brief_items:
        brief_facets = _decompose_brief(
            brief,
            claims=claim_items,
            facts=fact_items,
            facet_decomposer=facet_decomposer,
            proposition_architect=proposition_architect,
            schema_failures=schema_failures,
            source_field=brief_source_fields.get(brief.brief_id, ""),
        )
        facets.extend(brief_facets)
        candidate_rows = _candidate_evidence(
            brief,
            claims=claim_items,
            facts=fact_items,
            equations=equation_items,
            packets=packet_items,
        )
        for facet in brief_facets:
            candidate_rows_by_facet[facet.facet_id] = candidate_rows

    facets[:] = _dedupe_intent_grain_facets(
        facets,
        brief_source_fields=brief_source_fields,
    )

    alignments: list[FacetEvidenceAlignmentV1] = []
    for facet_index, facet in enumerate(facets):
        rows = candidate_rows_by_facet.get(facet.facet_id, ())
        if evidence_aligner is not None:
            payload = {
                "facet_index": facet_index,
                "facet": {
                    "facet_kind": facet.facet_kind,
                    "exact_source_quote": facet.exact_source_quote,
                    "semantic_fields": facet.semantic_fields,
                    "formula_expectation": facet.formula_expectation,
                },
                "evidence": [
                    {
                        key: value
                        for key, value in row.items()
                        if not key.startswith("_")
                    }
                    for row in rows
                ],
                "closed_sets": {
                    "evidence_indices": [
                        int(row["evidence_index"]) for row in rows
                    ],
                },
            }
            try:
                owner_value = evidence_aligner(payload)
                alignments.append(
                    _alignment_from_owner(
                        owner_value,
                        facet=facet,
                        rows=rows,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - typed unresolved result
                alignments.append(
                    _alignment_from_owner(
                        {},
                        facet=facet,
                        rows=rows,
                        owner_error=f"evidence_aligner:{type(exc).__name__}",
                    )
                )
                schema_failures.append(
                    f"{facet.facet_id}:evidence_aligner:{type(exc).__name__}"
                )
            owner_traces = getattr(evidence_aligner, "traces", ())
            if owner_traces:
                traces.extend(owner_traces[len(traces) :])
        elif evidence_judge is not None:
            selected_rows = _select_evidence_rows(facet, rows)
            judge_payload = _proposition_judge_payload(facet, selected_rows or rows)
            try:
                verdict = evidence_judge(judge_payload)
                if verdict is None:
                    alignments.append(
                        _alignment_from_owner(
                            {},
                            facet=facet,
                            rows=rows,
                            owner_error="evidence_judge_empty",
                        )
                    )
                else:
                    alignments.append(
                        _alignment_from_proposition_judge(
                            verdict,
                            facet=facet,
                            candidate_rows=rows,
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - typed unresolved result
                alignments.append(
                    _alignment_from_owner(
                        {},
                        facet=facet,
                        rows=rows,
                        owner_error=f"evidence_judge:{type(exc).__name__}",
                    )
                )
                schema_failures.append(
                    f"{facet.facet_id}:evidence_judge:{type(exc).__name__}"
                )
            owner_traces = getattr(evidence_judge, "evidence_judge_traces", ())
            if owner_traces:
                traces.extend(owner_traces[len(traces) :])
        else:
            alignments.append(
                _alignment_from_owner(
                    {},
                    facet=facet,
                    rows=rows,
                    owner_error="no_evidence_aligner",
                )
            )

    normalized_alignments, policies, merge_failures = _merge_facet_alignment_policy(
        tuple(facets),
        tuple(alignments),
        briefs=brief_items,
        claims=claims,
        facts=facts,
        evidence_packets=(
            evidence_packets if evidence_packets is not None else packets
        ),
        equations=equations,
        deterministic_licenses=deterministic_licenses,
        known_claim_ids=(),
        known_span_ids=(),
        known_equation_ids=(),
    )
    schema_failures.extend(merge_failures)
    return MethodArgumentFacetAlignmentResultV1(
        facets=tuple(facets),
        alignments=normalized_alignments,
        policies=policies,
        schema_failures=_clean_strings(schema_failures),
        traces=tuple(traces),
    )


__all__ = [
    "MethodArgumentFacetAlignmentResultV1",
    "bind_facets_to_argument_briefs",
    "build_mechanism_authoring_packet",
    "build_method_argument_facet_evidence_aligner",
    "decompose_and_align_argument_facets",
    "merge_facet_alignment_policy",
]
