"""Deterministic L1 Math IR and L2 technical claims.

L0 executable facts stay fail-closed (exact predicate, no effect expansion).
This module compiles:

- L1 execution ops from fact predicates (threshold, product, sparse matvec, …)
- L1 chains sharing result→input
- L2 technical-semantic claims with licensed effect text and polarity

No free LLM summary.  No project-specific literals.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
)
from code2paper.agentic.tool_runtime import atomic_write_json
from code2paper.agentic.text_evidence_validator import _comparison_units

InferenceLevel = Literal["E0", "E1", "E2", "E3"]
MathOpKind = Literal[
    "threshold_mask",
    "elementwise_product",
    "sparse_matvec",
    "log1p",
    "weighted_sum",
    "topk",
    "iterate_until",
    "normalize",
]
InferenceType = Literal["algorithmic_interpretation"]

_SPARSE_MM_RE = re.compile(
    r"\b(?:sparse(?:[._]mm)?|spmm|matmul|mm\b|coalesce)\b",
    re.I,
)
_LOG1P_RE = re.compile(r"\blog(?:1p)?\b", re.I)
_CONTINUE_RE = re.compile(
    r"(?:guarded_continue|(?:^|[^A-Za-z])(?:continue|skip|break)(?:[^A-Za-z]|$))",
    re.I,
)
_INCIDENCE_RE = re.compile(
    r"\b(?:incidence|adjacency|co[- ]?occurrence|mention|contain)\b",
    re.I,
)
_PRODUCT_TOKEN_RE = re.compile(
    r"(?:\*|\b(?:product|times|multiply|multiplies|mul)\b)",
    re.I,
)
_SUM_TOKEN_RE = re.compile(
    r"(?:\+|\b(?:add|sum|plus)\b)",
    re.I,
)
_NUMERIC_THRESHOLD_OPS = frozenset({"<", "<=", ">", ">="})
_NARRATIVE_L2_KINDS = frozenset({
    "threshold_mask",
    "sparse_matvec",
    "log1p",
    "topk",
    "iterate_until",
    "normalize",
})


def _context_has_product(joined: str) -> bool:
    return bool(_PRODUCT_TOKEN_RE.search(str(joined or "")))


def _context_has_sum(joined: str) -> bool:
    return bool(_SUM_TOKEN_RE.search(str(joined or "")))


def _quoted_operand(value: object) -> bool:
    text = str(value or "").strip()
    return len(text) >= 2 and text[0] in {"'", '"'} and text[-1] == text[0]


class MathOpIRV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    op_id: str
    kind: MathOpKind
    parent_fact_ids: tuple[str, ...]
    polarity: str = ""
    comparison: tuple[str, str, str] | None = None
    result_role: str = ""


class MathOpGraphV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str
    obligation_id: str = ""
    ops: tuple[MathOpIRV1, ...]
    chain_length: int = 0


class TechnicalClaimV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    canonical_text: str
    inference_level: Literal["E2"] = "E2"
    inference_type: InferenceType = "algorithmic_interpretation"
    parent_fact_ids: tuple[str, ...]
    parent_claim_ids: tuple[str, ...]
    parent_math_ids: tuple[str, ...]
    intent_obligation_ids: tuple[str, ...] = ()
    math_op_kind: str = ""
    forbidden_flips: tuple[str, ...] = ()
    allowed_wording_boundary: str = (
        "effect interpretation licensed; polarity must match parent comparison units"
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _fact_text(fact: CodeFactV1) -> str:
    obj = fact.object
    if isinstance(obj, list):
        obj_text = " ".join(str(item) for item in obj)
    else:
        obj_text = str(obj or "")
    context = " ".join(str(item) for item in fact.semantic_context)
    conditions = " ".join(str(item) for item in fact.conditions)
    return " ".join((fact.subject, fact.predicate, obj_text, context, conditions))


def _parse_comparison(fact: CodeFactV1) -> tuple[str, str, str] | None:
    units = _comparison_units(_fact_text(fact))
    if not units:
        return None
    return next(iter(units))


def _comparison_operator(fact: CodeFactV1) -> str | None:
    parsed = _parse_comparison(fact)
    if parsed:
        return parsed[1]
    match = re.search(r"(>=|<=|!=|==|>|<)", _fact_text(fact))
    return match.group(1) if match else None


def _neighborhood_has_continue(fact: CodeFactV1, facts: list[CodeFactV1]) -> bool:
    if _CONTINUE_RE.search(_fact_text(fact)):
        return True
    spans = {str(item) for item in fact.direct_span_ids if str(item)}
    if not spans:
        return False
    for other in facts:
        if other.fact_id == fact.fact_id:
            continue
        if spans & {str(item) for item in other.direct_span_ids if str(item)}:
            if _CONTINUE_RE.search(_fact_text(other)):
                return True
    return False


def _preferred_covers(
    *,
    obligation_id: str,
    parents: list[AtomicClaimV3],
) -> list[str]:
    if obligation_id:
        return [obligation_id]
    parent_covers = [
        str(item)
        for claim in parents
        for item in claim.covers_obligation_ids
        if str(item)
    ]
    stage_covers = [
        item for item in parent_covers
        if re.search(r"(STAGE|PIPELINE)", item, re.I)
    ]
    return list(dict.fromkeys(stage_covers or parent_covers))


def compile_math_ops(facts: CodeFactSetV1 | list[CodeFactV1]) -> list[MathOpIRV1]:
    items = list(getattr(facts, "facts", facts) or [])
    ops: list[MathOpIRV1] = []
    for fact in items:
        if getattr(fact, "validation_status", "supported") not in {"supported", ""}:
            continue
        text = _fact_text(fact)
        kind: MathOpKind | None = None
        polarity = ""
        comparison = None
        operator = _comparison_operator(fact)
        mask_predicate = fact.predicate in {
            "filters_by", "compares", "constructs_mask",
        } or (
            fact.predicate == "branches_on"
            and operator in _NUMERIC_THRESHOLD_OPS
        )
        if operator and mask_predicate:
            comparison = _parse_comparison(fact)
            kind = "threshold_mask"
            if _neighborhood_has_continue(fact, items) or operator in {"<", "<="}:
                polarity = "exclude_below" if operator in {"<", "<="} else "exclude_on_compare"
            elif operator in {">", ">="}:
                polarity = "retain_above"
            else:
                polarity = "mask"
        elif fact.predicate == "computes_formula" and isinstance(fact.object, list) and len(fact.object) >= 2:
            joined = " ".join(str(item) for item in fact.semantic_context).lower()
            quoted = any(_quoted_operand(item) for item in fact.object[:2])
            if quoted:
                kind = None
            elif _context_has_product(joined):
                kind = "elementwise_product"
            elif _context_has_sum(joined):
                kind = "weighted_sum"
        elif fact.predicate in {"computes", "computes_formula", "propagates", "transforms"} and _SPARSE_MM_RE.search(text):
            kind = "sparse_matvec"
        elif fact.predicate == "selects_top_k":
            kind = "topk"
        elif fact.predicate in {"computes", "computes_formula", "transforms"} and _LOG1P_RE.search(text):
            kind = "log1p"
        elif fact.predicate == "normalizes":
            kind = "normalize"
        elif fact.predicate == "loops":
            kind = "iterate_until"
        if kind is None:
            continue
        ops.append(MathOpIRV1(
            op_id=f"math:{fact.fact_id}:{kind}",
            kind=kind,
            parent_fact_ids=(fact.fact_id,),
            polarity=polarity,
            comparison=comparison,
            result_role=str(getattr(fact, "subject", "") or ""),
        ))
    return ops


def compile_math_graphs(
    facts: CodeFactSetV1 | list[CodeFactV1],
    *,
    obligation_id: str = "",
) -> list[MathOpGraphV1]:
    ops = compile_math_ops(facts)
    if not ops:
        return []
    kinds = {op.kind for op in ops}
    chain = len(kinds)
    return [MathOpGraphV1(
        graph_id=f"math-graph:{obligation_id or 'default'}",
        obligation_id=obligation_id,
        ops=tuple(ops),
        chain_length=chain,
    )]


def _l0_for_facts(
    l0_claims: list[AtomicClaimV3],
    fact_ids: tuple[str, ...],
) -> list[AtomicClaimV3]:
    wanted = set(fact_ids)
    return [
        claim for claim in l0_claims
        if wanted & set(claim.fact_ids)
        and getattr(claim, "inference_level", "E0") in {"E0", "", None}
        and claim.claim_kind == "implementation_behavior"
    ]


def compile_technical_claims(
    facts: CodeFactSetV1 | list[CodeFactV1],
    l0_claims: list[AtomicClaimV3] | AtomicClaimSetV3,
    *,
    obligation_id: str = "",
    intent_obligation_ids: tuple[str, ...] | list[str] = (),
) -> tuple[list[TechnicalClaimV1], list[AtomicClaimV3]]:
    """Emit L2 technical claims and matching AtomicClaimV3 rows."""

    claims = list(getattr(l0_claims, "claims", l0_claims) or [])
    ops = compile_math_ops(facts)
    kinds = {op.kind for op in ops}
    lone_arithmetic = not (kinds & _NARRATIVE_L2_KINDS) and len(kinds) < 2
    technical: list[TechnicalClaimV1] = []
    atomic: list[AtomicClaimV3] = []
    intent_ids = tuple(str(item) for item in intent_obligation_ids if str(item).strip())
    for op in ops:
        if op.kind in {"elementwise_product", "weighted_sum"} and lone_arithmetic:
            continue
        parents = _l0_for_facts(claims, op.parent_fact_ids)
        parent_ids = tuple(claim.claim_id for claim in parents)
        covers = _preferred_covers(obligation_id=obligation_id, parents=parents)
        evidence_ids = list(dict.fromkeys(
            span_id
            for claim in parents
            for span_id in claim.direct_evidence_ids
        ))
        fact_ids = list(op.parent_fact_ids)
        text = ""
        forbidden: tuple[str, ...] = ()
        if op.kind == "threshold_mask":
            text = "Values that fail the comparison are excluded."
            forbidden = ("comparison polarity",)
        elif op.kind == "elementwise_product":
            text = "Operands are multiplied."
        elif op.kind == "sparse_matvec":
            if _INCIDENCE_RE.search(" ".join(_fact_text(fact) for fact in getattr(facts, "facts", facts) or [])):
                text = "A sparse co-occurrence product distributes the signal."
            else:
                text = "A sparse matrix–vector product distributes the signal."
        elif op.kind == "iterate_until":
            text = "Iteration continues until the working set is empty or a bound is reached."
        elif op.kind == "topk":
            text = "A top-k selection keeps the highest scoring items."
        elif op.kind == "log1p":
            text = "A compressed occurrence signal is combined with the base score."
        elif op.kind == "normalize":
            text = "Scores are normalized before they are compared or aggregated."
        elif op.kind == "weighted_sum":
            text = "Contributing terms are aggregated by a sum."
        if not text:
            continue
        claim_id = f"l2:{op.op_id}"
        technical.append(TechnicalClaimV1(
            claim_id=claim_id,
            canonical_text=text,
            parent_fact_ids=tuple(fact_ids),
            parent_claim_ids=parent_ids,
            parent_math_ids=(op.op_id,),
            intent_obligation_ids=intent_ids,
            math_op_kind=op.kind,
            forbidden_flips=forbidden,
        ))
        if not evidence_ids and parents:
            continue
        if not evidence_ids:
            continue
        payload = {
            "claim_id": claim_id,
            "canonical_text": text,
            "parent_claim_ids": list(parent_ids),
            "math_op_kind": op.kind,
        }
        atomic.append(AtomicClaimV3(
            claim_id=claim_id,
            canonical_text=text,
            claim_kind="technical_semantic",
            fact_ids=fact_ids,
            covers_obligation_ids=list(covers or [
                obligation
                for claim in parents
                for obligation in claim.covers_obligation_ids
            ]),
            direct_evidence_ids=evidence_ids,
            relation_evidence_ids=list(dict.fromkeys(
                relation_id
                for claim in parents
                for relation_id in claim.relation_evidence_ids
            )),
            required_qualifiers=[],
            unsupported_author_fragments=[],
            allowed_wording_boundary=(
                "effect interpretation licensed; polarity must match parent comparison units"
            ),
            canonical_identity=_digest(payload),
            status="supported",
            inference_level="E2",
            parent_claim_ids=list(parent_ids),
            math_op_kind=op.kind,
        ))
    return technical, atomic


def append_technical_claims(
    claim_set: AtomicClaimSetV3,
    facts: CodeFactSetV1,
    *,
    obligation_id: str = "",
) -> AtomicClaimSetV3:
    """Append L2 rows into an existing V3 set without changing L0 identity."""

    _technical, extra = compile_technical_claims(
        facts,
        claim_set.claims,
        obligation_id=obligation_id,
    )
    if not extra:
        return claim_set
    existing = {claim.claim_id for claim in claim_set.claims}
    merged = [*claim_set.claims, *[item for item in extra if item.claim_id not in existing]]
    payload = [claim.model_dump(mode="json") for claim in merged]
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return claim_set.model_copy(update={"claims": merged, "content_digest": digest})


def l1_chain_length(facts: CodeFactSetV1 | list[CodeFactV1]) -> int:
    graphs = compile_math_graphs(facts)
    if not graphs:
        return 0
    return max(graph.chain_length for graph in graphs)


def technical_claims_sidecar_payload(claim_set: AtomicClaimSetV3) -> dict[str, Any]:
    """Serialize L2 rows that already live on the V3 claim set."""

    rows = []
    for claim in claim_set.claims:
        kind = str(getattr(claim, "claim_kind", "") or "")
        level = str(getattr(claim, "inference_level", "E0") or "E0")
        if kind != "technical_semantic" and level != "E2":
            continue
        rows.append({
            "claim_id": claim.claim_id,
            "canonical_text": claim.canonical_text,
            "inference_level": level if level in {"E2", "E3"} else "E2",
            "parent_claim_ids": list(getattr(claim, "parent_claim_ids", ()) or ()),
            "parent_fact_ids": list(claim.fact_ids),
            "math_op_kind": str(getattr(claim, "math_op_kind", "") or ""),
            "covers_obligation_ids": list(claim.covers_obligation_ids),
            "allowed_wording_boundary": claim.allowed_wording_boundary,
        })
    payload = {"schema_version": "1.0", "claims": rows}
    payload["content_digest"] = _digest(payload)
    return payload


def write_technical_claims_sidecar(
    atomic_claims_path: str | Path,
    claim_set: AtomicClaimSetV3,
) -> str:
    """Persist ``technical_claims_v1.json`` beside ``atomic_claims_v3``."""

    path = Path(atomic_claims_path)
    name = path.name.replace("atomic_claims_v3", "technical_claims_v1")
    if name == path.name:
        name = "technical_claims_v1.json"
    dest = path.with_name(name)
    atomic_write_json(dest, technical_claims_sidecar_payload(claim_set))
    return str(dest)
