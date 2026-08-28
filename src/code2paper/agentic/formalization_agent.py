"""Formalization Agent contracts and deterministic validation helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.equation_claims import (
    EquationClaimSetV1,
    effective_formula_role,
    is_bare_binary_expression,
)
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
from code2paper.agentic.method_argument_models import ProofObligationV1


def _digest_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class SymbolDefinitionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    meaning: str
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_artifact_ids: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)


class FormalizationRiskV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_id: str
    kind: str
    message: str
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    blocking: bool = True


class FormalizationProposalItemV1(BaseModel):
    """One bounded Formalization-Agent proposal bound to closed IDs.

    ``kind`` is one of ``pseudocode``, ``derivation_step``, ``notation_note``,
    or ``validation_conclusion``.  Every item must bind exact fact/equation
    ids; the deterministic guards reject operand/value/operator mutations and
    theoretical upgrades the code cannot license.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["pseudocode", "derivation_step", "notation_note", "validation_conclusion"]
    statement: str
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    symbols: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _valid(self) -> "FormalizationProposalItemV1":
        if not self.statement.strip():
            raise ValueError("formalization proposal statements must not be empty")
        if not self.fact_ids and not self.equation_ids:
            raise ValueError("formalization proposals must bind fact or equation ids")
        return self


class FormalizationProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    proposal_id: str
    items: tuple[FormalizationProposalItemV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "FormalizationProposalV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


class FormalizationResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repo_snapshot_id: str
    project_tree_hash: str
    fact_digest: str
    equation_digest: str = ""
    symbols: tuple[SymbolDefinitionV1, ...] = Field(default_factory=tuple)
    equations: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    proof_obligations: tuple[ProofObligationV1, ...] = Field(default_factory=tuple)
    risks: tuple[FormalizationRiskV1, ...] = Field(default_factory=tuple)
    proposal_items: tuple[FormalizationProposalItemV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "FormalizationResultV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


FormulaLaneV1 = Literal[
    "repository_derived",
    "hybrid_partial",
    "author_intent_academic",
]

FormulaReviewStatusV1 = Literal[
    "accepted",
    "review_required",
    "rejected",
]


class MethodFormulaObligationV2(BaseModel):
    """A formula-worthy author facet and its bounded expectation.

    Formula obligations are not inferred from every AST ``+``/``*``.  They
    are created from a mechanism facet (or an explicit section obligation)
    and tell the Formalizer whether a package is required, preferred, or not
    applicable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    expectation: Literal["required", "preferred", "none"] = "required"
    mathematical_goal: str = ""
    authority_requirements: tuple[str, ...] = Field(default_factory=tuple)
    section_id: str = ""
    # Canonical placement for the current plan.  ``paragraph_ids`` remains
    # readable for frozen pre-consumer artifacts, but new obligations must
    # identify exactly one paragraph that will consume the package.
    consumer_paragraph_id: str = ""
    paragraph_ids: tuple[str, ...] = Field(default_factory=tuple)
    ordered_semantic_slot_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_edge_ids: tuple[str, ...] = Field(default_factory=tuple)
    preconditions: tuple[str, ...] = Field(default_factory=tuple)
    formula_lane: FormulaLaneV1 | None = None
    exact_source_quotes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "MethodFormulaObligationV2":
        if not self.obligation_id.strip():
            raise ValueError("formula obligation requires an id")
        if self.expectation != "none" and not (
            self.mathematical_goal.strip()
            or self.facet_ids
            or self.authority_requirements
        ):
            raise ValueError(
                "non-empty formula obligations require a mathematical goal, facet, "
                "or authority requirement"
            )
        if self.consumer_paragraph_id and self.paragraph_ids and tuple(
            dict.fromkeys(self.paragraph_ids)
        ) != (self.consumer_paragraph_id,):
            raise ValueError(
                "formula obligation consumer_paragraph_id must be the sole paragraph_ids entry"
            )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest_json(payload))
        return self


class MechanismEquationEvidencePackV1(BaseModel):
    """Connected source operations supplied to a section Formalizer.

    A pack may describe several connected operation atoms, exact source
    spans, conditions, and author statements.  One isolated binary
    operation is intentionally not enough to establish a publication
    equation; it remains an operation atom or an incidental bookkeeping fact.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: str
    section_id: str = ""
    operation_atoms: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    exact_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    preconditions: tuple[str, ...] = Field(default_factory=tuple)
    shape_or_type_hints: tuple[str, ...] = Field(default_factory=tuple)
    author_statements: tuple[str, ...] = Field(default_factory=tuple)
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
    bound_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    connected: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "MechanismEquationEvidencePackV1":
        if not self.pack_id.strip():
            raise ValueError("equation evidence pack requires an id")
        for name in (
            "exact_span_ids",
            "bound_fact_ids",
            "bound_equation_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"equation evidence pack contains duplicate {name}")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest_json(payload))
        return self


# ---------------------------------------------------------------------------
# Q2 - section-scoped paper-formula packages (plan 19.6)
# ---------------------------------------------------------------------------


class SectionFormulaPackageV1(BaseModel):
    """One section-scoped, evidence-bound paper formula package (Q2).

    The Writer sees only reader-facing fields (purpose, latex,
    prose_explanation, symbol_definitions, material_conditions,
    assumptions, authority_status, risks, review_question).
    Internal ids (bound_fact_ids / bound_equation_ids) live in the
    package for binding/sidecar use only and are never rendered into prose.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str
    section_id: str
    # New consumer-first route.  Historical packages may omit these fields;
    # current authoring plans must bind each package to one obligation and its
    # single paragraph consumer before the Writer can count it as consumed.
    obligation_id: str = ""
    consumer_paragraph_id: str = ""
    purpose: str  # the Method question this formula answers
    latex: str  # formula body that can be placed in Markdown/LaTeX
    prose_explanation: str
    markdown_block: str = ""
    symbol_definitions: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    symbol_table: tuple[SymbolDefinitionV1, ...] = Field(default_factory=tuple)
    material_conditions: tuple[str, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    authority_status: Literal["code_verified", "author_intent", "partial", "paper_code_mismatch"]
    formula_lane: FormulaLaneV1 | None = None
    bound_facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    review_status: FormulaReviewStatusV1 | None = None
    risks: tuple[str, ...] = Field(default_factory=tuple)
    review_question: str = ""
    bound_fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    bound_equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "SectionFormulaPackageV1":
        if not self.package_id.strip() or not self.section_id.strip():
            raise ValueError("formula package requires package and section ids")
        if not self.latex.strip():
            raise ValueError("formula package latex must not be empty")
        lane = self.formula_lane
        if lane is None:
            lane = {
                "code_verified": "repository_derived",
                "partial": "hybrid_partial",
                "author_intent": "author_intent_academic",
                "paper_code_mismatch": "hybrid_partial",
            }[self.authority_status]
            object.__setattr__(self, "formula_lane", lane)
        if lane == "repository_derived" and self.authority_status != "code_verified":
            raise ValueError(
                "repository-derived formula packages must be code_verified"
            )
        if lane != "repository_derived" and self.authority_status == "code_verified":
            raise ValueError(
                "semantic or partial formula lanes cannot be code_verified"
            )
        if not self.markdown_block.strip() or not _FORMULA_DISPLAY_MATH_RE.search(
            self.markdown_block
        ):
            object.__setattr__(
                self,
                "markdown_block",
                "$$\n" + self.latex.strip() + "\n$$",
            )
        if not self.symbol_table:
            object.__setattr__(
                self,
                "symbol_table",
                tuple(
                    SymbolDefinitionV1(symbol=symbol, meaning=meaning)
                    for symbol, meaning in self.symbol_definitions
                ),
            )
        if self.review_status is None:
            object.__setattr__(
                self,
                "review_status",
                "accepted" if lane == "repository_derived" else "review_required",
            )
        if self.authority_status == "code_verified" and not (
            self.bound_fact_ids or self.bound_equation_ids
        ):
            raise ValueError("code_verified formula packages must bind exact ids")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = "sha256:" + hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        object.__setattr__(self, "content_digest", computed)
        return self


class SectionFormulaDispositionV1(BaseModel):
    """Typed disposition when a section receives no accepted formula package.

    Q2 rule: a section with core equation evidence must end with an accepted
    package OR a typed disposition plus review item; an empty proposal list
    is never silently treated as completion.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    disposition: Literal["not_applicable", "insufficient_binding", "paper_code_mismatch", "formalizer_empty", "declined_empty"]
    review_question: str = ""
    review_note: str = ""
    required_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    preferred_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    blocking_for_candidate: bool = False
    blocking_for_verified: bool = True


class SectionFormulaObligationTruthV1(BaseModel):
    """Per-obligation formula truth for one section (WP3 Slice 3B)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    outcome: Literal["rendered", "unresolved", "not_applicable"]
    package_id: str = ""
    review_question: str = ""
    reason: str = ""
    expectation: Literal["required", "preferred", "none"] = "required"
    blocking: bool = False


class FormalizationSectionResultV1(BaseModel):
    """Section-scoped formalization outcome: packages or a typed disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    section_id: str
    packages: tuple[SectionFormulaPackageV1, ...] = Field(default_factory=tuple)
    disposition: SectionFormulaDispositionV1 | None = None
    obligation_truths: tuple[SectionFormulaObligationTruthV1, ...] = Field(default_factory=tuple)
    formula_obligations: tuple[MethodFormulaObligationV2, ...] = Field(default_factory=tuple)
    evidence_packs: tuple[MechanismEquationEvidencePackV1, ...] = Field(default_factory=tuple)
    required_formula_failures: tuple[str, ...] = Field(default_factory=tuple)
    preferred_formula_review_ids: tuple[str, ...] = Field(default_factory=tuple)
    formula_route_failures: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "FormalizationSectionResultV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        computed = "sha256:" + hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        object.__setattr__(self, "content_digest", computed)
        return self

#: Equation operation descriptors that denote a core Method mechanism
#: (representation, transformation, normalization, aggregation, objective,
#: state update, inference score, attention, propagation).  A bare source
#: arithmetic operator (add/sub/mult/div/mod/pow/matmul) is NOT a paper
#: formula by itself (review P0-Q2): the descriptor vocabulary must denote
#: a scientifically material mechanism, not incidental bookkeeping.
_CORE_EQUATION_DESCRIPTORS = frozenset({
    "representation", "transform", "transformation", "normalize", "normalization",
    "aggregate", "aggregation", "reduce", "reduction", "objective", "loss",
    "state update", "state_update", "inference score", "score", "propagate",
    "propagation", "attention", "attend", "concatenate", "stack", "project",
    "sample", "embedding", "dot product", "inner product", "outer product",
    "similarity", "mask", "threshold", "cross_entropy", "contrastive",
})

#: Fact predicates that license a mechanism-level formula even when the
#: equation carries no mechanism descriptor (review P0-Q2: an authorized
#: expression is core only when its source fact states a scientific
#: mechanism, not merely a source-level arithmetic operation).
_MECHANISM_PREDICATE_TERMS = (
    "computes", "update", "attend", "propagat", "aggregat", "normaliz",
    "embed", "score", "transform", "represent", "mask", "threshold",
    "project", "sample", "stack", "concatenat", "pool", "loss", "objective",
    "state", "infer", "similarity", "contrastive", "cross_entropy", "formula",
)

_AUDIT_DESCRIPTOR_TERMS = (
    "shape", "len(", "empty", "cache", "index", "log", "progress", "assert",
    "dtype", "device", "placeholder",
)

#: Source-level arithmetic descriptors that never license a paper formula alone.
_GENERIC_ARITHMETIC_DESCRIPTORS = frozenset({
    "add", "sub", "mult", "div", "mod", "pow", "matmul",
})

# Values that describe tensor/configuration bookkeeping rather than a
# scientific transformation.  They remain supported CodeFacts, but their
# binary operations are not paper equations.
_BOOKKEEPING_FORMULA_TERMS = frozenset({
    "shape", "shapes", "dim", "dims", "dimension", "dimensions",
    "channel", "channels", "embedding_dim", "hidden_dim", "feature_dim",
    "batch", "batch_size", "length", "len", "size", "width", "height",
    "capacity", "index", "indices", "offset", "stride", "config",
    "configuration",
})

#: Fact predicates that can license a mechanism-level formula when generic
#: arithmetic descriptors are present but no core mechanism descriptor matches.
_EQUATION_LICENSING_PREDICATES = frozenset({
    "computes_formula", "transforms", "aggregates", "reduces",
    "concatenates", "stacks", "normalizes", "compares",
    "selects", "selects_top_k", "sorts_by", "filters_by",
    "constructs", "returns",
})

_PLACEHOLDER_SECTION_ID_RE = re.compile(r"^\{[^}]+\}$")


def _predicate_is_mechanism(predicate: str) -> bool:
    lowered = str(predicate or "").casefold()
    # ``computes_formula`` is an authorization predicate for source
    # operations, not proof that an expression is publication-worthy.  The
    # selector must see a real mechanism predicate/descriptor or connected
    # relation evidence before choosing a generic arithmetic expression.
    if lowered in {"computes_formula", "computes", "formula"}:
        return False
    return any(term in lowered for term in _MECHANISM_PREDICATE_TERMS)


def _formula_value_tokens(value: Any) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9_]*", str(value or "").casefold()))


def _is_bookkeeping_formula_value(value: Any) -> bool:
    tokens = _formula_value_tokens(value)
    return bool(tokens & _BOOKKEEPING_FORMULA_TERMS) or any(
        token.startswith(("num_", "n_", "shape_", "dim_"))
        or token.endswith(("_dim", "_size", "_length", "_shape"))
        for token in tokens
    )


def _equation_uses_bookkeeping_values(
    equation: Any,
    facts_by_id: dict[str, Any],
) -> bool:
    for fact_id in (getattr(equation, "fact_ids", ()) or ()):
        fact = facts_by_id.get(fact_id)
        if fact is None:
            continue
        values = (
            getattr(fact, "subject", ""),
            getattr(fact, "object", ""),
            *(getattr(fact, "semantic_context", ()) or ()),
        )
        if any(_is_bookkeeping_formula_value(value) for value in values):
            return True
    return False


def _descriptor_term_in_value(term: str, value: str) -> bool:
    """Whole-token mechanism match; never ``attention`` inside ``hybrid_attention_``."""

    text = str(value or "").strip().casefold()
    token = str(term or "").strip().casefold()
    if not text or not token:
        return False
    if text == token:
        return True
    if " " in token:
        return token in text
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", text) is not None


def _equation_has_mechanism_descriptor(
    equation: Any,
    facts_by_id: dict[str, Any],
) -> bool:
    values = [
        *(getattr(equation, "operation_descriptors", ()) or ()),
        *(
            value
            for fact_id in (getattr(equation, "fact_ids", ()) or ())
            for value in (getattr(facts_by_id.get(fact_id), "semantic_context", ()) or ())
        ),
    ]
    return any(
        _descriptor_term_in_value(term, str(value))
        for value in values
        if str(value).strip()
        for term in _CORE_EQUATION_DESCRIPTORS
    )


def _equation_relation_evidence_ids(
    equation: Any,
    facts_by_id: dict[str, Any],
) -> set[str]:
    relation_ids: set[str] = set()
    for relation_id in (getattr(equation, "relation_evidence_ids", ()) or ()):
        cleaned = str(relation_id).strip()
        if cleaned:
            relation_ids.add(cleaned)
    for fact_id in (getattr(equation, "fact_ids", ()) or ()):
        fact = facts_by_id.get(fact_id)
        if fact is None:
            continue
        for relation_id in (getattr(fact, "relation_evidence_ids", ()) or ()):
            cleaned = str(relation_id).strip()
            if cleaned:
                relation_ids.add(cleaned)
    return relation_ids


def _equation_has_licensing_predicate(
    equation: Any,
    facts_by_id: dict[str, Any],
) -> bool:
    for fact_id in (getattr(equation, "fact_ids", ()) or ()):
        fact = facts_by_id.get(fact_id)
        if fact is None:
            continue
        predicate = str(getattr(fact, "predicate", "") or "").strip()
        if predicate in _EQUATION_LICENSING_PREDICATES:
            return True
    return False


def _equation_is_core(
    equation: Any,
    facts_by_id: dict[str, Any],
) -> bool:
    """Whether an equation expresses a core Method mechanism (Q2).

    An equation is core when its operation descriptors denote a paper-level
    mechanism (state update, propagation, attention, normalization, score,
    aggregation, ...) — or, for descriptor-less expressions, when its bound
    fact predicates state a scientific mechanism — and none of its bound
    facts are audit-only bookkeeping (defensive shape/empty checks, loops,
    serialization).  Generic add/sub/mult/div/mod/matmul descriptors never
    make an expression a paper formula by themselves; when only generic
    arithmetic descriptors are present, selection falls back to equation-
    licensing predicates and exact relation evidence.
    """

    descriptors = [
        str(item).strip().casefold()
        for item in (getattr(equation, "operation_descriptors", ()) or ())
    ]
    if effective_formula_role(equation) == "incidental":
        return False
    if is_bare_binary_expression(str(getattr(equation, "expression", "") or "")):
        return False
    predicates = {
        str(getattr(facts_by_id.get(fact_id), "predicate", "") or "")
        for fact_id in (getattr(equation, "fact_ids", ()) or ())
        if fact_id in facts_by_id
    }
    if predicates & {"branches_on", "loops", "writes_artifact"}:
        return False
    joined = " ".join(descriptors)
    if any(term in joined for term in _AUDIT_DESCRIPTOR_TERMS):
        return False
    if descriptors:
        if any(descriptor in _CORE_EQUATION_DESCRIPTORS for descriptor in descriptors):
            return True
        only_generic = all(
            descriptor in _GENERIC_ARITHMETIC_DESCRIPTORS for descriptor in descriptors
        )
        if only_generic:
            if _equation_uses_bookkeeping_values(equation, facts_by_id):
                return False
            return (
                _equation_has_mechanism_descriptor(equation, facts_by_id)
                or bool(_equation_relation_evidence_ids(equation, facts_by_id))
            )
        return False
    # Descriptor-less authorized expression: core only when its facts state
    # a scientific mechanism predicate.
    return any(_predicate_is_mechanism(predicate) for predicate in predicates)


def select_core_equations(
    *,
    equations: Any,
    facts: Any,
    allowed_equation_ids: set[str] | None = None,
) -> list[Any]:
    """Select the section-scoped core equations (plan 19.6.4.1/19.6.4.2)."""

    facts_by_id = {fact.fact_id: fact for fact in (facts.facts if facts is not None else ())}
    selected: list[Any] = []
    for equation in (equations.equations if equations is not None else ()):
        if allowed_equation_ids is not None and equation.equation_id not in allowed_equation_ids:
            continue
        if not _equation_is_core(equation, facts_by_id):
            continue
        selected.append(equation)
    return selected


def build_mechanism_equation_evidence_packs(
    *,
    section_id: str,
    equations: Any,
    facts: Any,
    allowed_equation_ids: set[str] | None = None,
    author_statements: tuple[str, ...] = (),
) -> tuple[MechanismEquationEvidencePackV1, ...]:
    """Build bounded evidence packs for mechanism-level equations.

    The pack keeps source operation atoms separate from publication formulas.
    A lone generic binary operation is deliberately omitted; a connected
    multi-operation chain or a relation-backed mechanism is eligible for
    Formalizer review.
    """

    facts_by_id = {
        str(item.fact_id): item
        for item in (facts.facts if facts is not None else ())
    }
    packs: list[MechanismEquationEvidencePackV1] = []
    for equation in select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids=allowed_equation_ids,
    ):
        selected_facts = [
            facts_by_id[fact_id]
            for fact_id in (getattr(equation, "fact_ids", ()) or ())
            if str(fact_id) in facts_by_id
        ]
        atoms: list[dict[str, Any]] = []
        span_ids: list[str] = []
        conditions: list[str] = []
        shape_hints: list[str] = []
        relation_ids = set(getattr(equation, "relation_evidence_ids", ()) or ())
        for fact in selected_facts:
            values = (
                list(fact.object)
                if isinstance(fact.object, list)
                else [str(fact.object)]
            )
            atoms.append({
                "atom_id": f"atom:{fact.fact_id}",
                "fact_id": fact.fact_id,
                "predicate": fact.predicate,
                "operands": values,
                "result": fact.subject,
                "operation_descriptors": list(fact.semantic_context or ()),
                "span_ids": list(dict.fromkeys([
                    *fact.direct_span_ids,
                    *fact.relation_span_ids,
                ])),
            })
            relation_ids.update(fact.relation_evidence_ids or ())
            conditions.extend(fact.conditions or ())
            span_ids.extend(fact.direct_span_ids or ())
            span_ids.extend(fact.relation_span_ids or ())
            shape_hints.extend(
                value for value in (fact.semantic_context or ())
                if _is_bookkeeping_formula_value(value)
            )
        span_ids = list(dict.fromkeys(str(item) for item in span_ids if str(item).strip()))
        conditions = list(dict.fromkeys(str(item) for item in conditions if str(item).strip()))
        shape_hints = list(dict.fromkeys(str(item) for item in shape_hints if str(item).strip()))
        descriptors = {
            str(item).strip().casefold()
            for item in (getattr(equation, "operation_descriptors", ()) or ())
            if str(item).strip()
        }
        connected = bool(
            len(atoms) > 1
            or relation_ids
            or descriptors - _GENERIC_ARITHMETIC_DESCRIPTORS
        )
        if not connected:
            continue
        pack_identity = {
            "section_id": section_id,
            "equation_id": str(getattr(equation, "equation_id", "")),
            "fact_ids": list(getattr(equation, "fact_ids", ()) or ()),
            "span_ids": span_ids,
        }
        packs.append(MechanismEquationEvidencePackV1(
            pack_id="eqpack:" + _digest_json(pack_identity)[7:23],
            section_id=section_id,
            operation_atoms=tuple(atoms),
            exact_span_ids=tuple(span_ids),
            preconditions=tuple(conditions),
            shape_or_type_hints=tuple(shape_hints),
            author_statements=tuple(
                str(item).strip() for item in author_statements if str(item).strip()
            ),
            bound_fact_ids=tuple(
                str(item) for item in (getattr(equation, "fact_ids", ()) or ())
                if str(item) in facts_by_id
            ),
            bound_equation_ids=(str(getattr(equation, "equation_id", "")),),
            connected=True,
        ))
    return tuple(packs)


def validate_section_formula_package(
    package: SectionFormulaPackageV1,
    *,
    equations: Any,
    facts: Any,
    allowed_facet_ids: set[str] | None = None,
    formula_obligations: tuple[Any, ...] | list[Any] = (),
    require_consumer: bool = False,
) -> list[str]:
    """Deterministic authority guards over one section formula package.

    Checks LaTeX well-formedness (balanced braces, non-empty body), closed
    symbol definitions, preservation of the source equation's operands,
    values, operators and dimensions (no new numbers), and absence of
    theoretical upgrades the code cannot license.  The harness never invents
    math to fix a formula.
    """

    failures: list[str] = []
    if package.latex.count("{") != package.latex.count("}"):
        failures.append("latex_unbalanced_braces")
    if not package.latex.strip():
        failures.append("latex_empty")
    # ``latex`` is a math-only field.  A previous Formalizer response put a
    # complete Markdown section (heading, prose, and a display wrapper) in
    # this field; accepting it made the insertion path duplicate sections and
    # corrupted the Candidate.  Keep aligned/array environments valid but
    # reject document/Markdown residue and display delimiters.
    if re.search(r"```|(^|\n)\s*#{1,6}\s|(^|\n)\s*[-*]\s", package.latex):
        failures.append("latex_contains_markdown")
    if "$$" in package.latex or "\\[" in package.latex or "\\]" in package.latex:
        failures.append("latex_contains_display_wrapper")
    if re.search(r"\\(?:section|subsection|paragraph|textbf|emph)\b", package.latex):
        failures.append("latex_contains_document_command")
    if not _FORMULA_DISPLAY_MATH_RE.search(package.markdown_block):
        failures.append("markdown_block_not_display_math")
    if package.markdown_block.strip() and package.latex.strip() not in package.markdown_block:
        failures.append("markdown_block_missing_exact_latex")
    failures.extend(_formula_code_trace_failures(package))
    if package.formula_lane == "repository_derived":
        if package.authority_status != "code_verified":
            failures.append("repository_lane_requires_code_verified")
    elif package.formula_lane == "hybrid_partial":
        if package.authority_status == "code_verified":
            failures.append("hybrid_lane_cannot_be_code_verified")
        if not package.assumptions:
            failures.append("hybrid_lane_requires_explicit_assumptions")
    elif package.formula_lane == "author_intent_academic":
        if package.authority_status == "code_verified":
            failures.append("author_intent_lane_cannot_be_code_verified")
    if package.review_status == "rejected":
        failures.append("formula_package_marked_rejected")
    if allowed_facet_ids is not None:
        failures.extend(
            f"unknown_facet:{facet_id}"
            for facet_id in sorted(set(package.bound_facet_ids) - set(allowed_facet_ids))
        )
    if require_consumer:
        obligations = tuple(formula_obligations or ())
        package_obligation_id = str(package.obligation_id or "").strip()
        package_consumer_id = str(package.consumer_paragraph_id or "").strip()
        # Current plans use a canonical obligation id and a single explicit
        # consumer.  Facet overlap is intentionally not an alternative route:
        # it was the source of formula:facet/formula:equation aliasing and
        # allowed an unrelated package to appear consumed.
        if not package_obligation_id:
            failures.append("formula_package_obligation_id_missing")
        obligation_by_id = {
            str(getattr(item, "obligation_id", "") or "").strip(): item
            for item in obligations
            if str(getattr(item, "obligation_id", "") or "").strip()
        }
        obligation = obligation_by_id.get(package_obligation_id)
        if obligation is None:
            failures.append("formula_package_obligation_route_mismatch")
        else:
            expected_consumer = str(
                getattr(obligation, "consumer_paragraph_id", "")
                or (
                    obligation.paragraph_ids[0]
                    if len(tuple(getattr(obligation, "paragraph_ids", ()) or ())) == 1
                    else ""
                )
            ).strip()
            if not expected_consumer:
                failures.append("formula_package_without_paragraph_consumer")
            if not package_consumer_id:
                failures.append("formula_package_consumer_id_missing")
            elif expected_consumer and package_consumer_id != expected_consumer:
                failures.append("formula_package_consumer_paragraph_mismatch")
            package_facets = set(package.bound_facet_ids)
            obligation_facets = set(getattr(obligation, "facet_ids", ()) or ())
            if obligation_facets and package_facets and not obligation_facets.intersection(package_facets):
                failures.append("formula_package_facet_binding_mismatch")
    equation_by_id = {
        item.equation_id: item
        for item in (equations.equations if equations is not None else ())
    }
    fact_by_id = {
        item.fact_id: item
        for item in (facts.facts if facts is not None else ())
    }
    for fact_id in package.bound_fact_ids:
        if fact_id not in fact_by_id:
            failures.append(f"unknown_fact:{fact_id}")
    known_tokens: set[str] = set()
    for equation_id in package.bound_equation_ids:
        equation = equation_by_id.get(equation_id)
        if equation is None:
            failures.append(f"unknown_equation:{equation_id}")
            continue
        known_tokens.update(_equation_content_tokens(equation))
        concrete = _binding_concrete_expression(equation)
        source_numbers = set(re.findall(r"\d+(?:\.\d+)?", concrete))
        package_numbers = set(re.findall(r"\d+(?:\.\d+)?", package.latex))
        added = package_numbers - source_numbers
        if added:
            failures.append("added_numbers:" + ",".join(sorted(added)[:6]))
        present_operators = set(concrete) & set("+-*/^")
        if present_operators:
            statement = package.latex + " " + package.prose_explanation
            missing: list[str] = []
            for operator in sorted(present_operators):
                family = _OPERATOR_WORD_FAMILIES.get(operator, frozenset())
                covered = operator in statement or any(
                    word in statement.casefold() for word in family
                )
                if not covered:
                    missing.append(operator)
            if missing:
                failures.append("missing_operators:" + ",".join(missing))
    declared_symbols = {symbol for symbol, _meaning in package.symbol_definitions}
    for symbol, _meaning in package.symbol_definitions:
        if not symbol.strip() or not str(_meaning).strip():
            failures.append("empty_symbol_definition")
    used_symbols = _latex_command_tokens(package.latex)
    unknown_symbols = (
        used_symbols
        - declared_symbols
        - known_tokens
        - _STANDARD_LATEX_COMMANDS
        - _LATEX_GREEK_COMMANDS
        - _LATEX_TYPESETTING_COMMANDS
    )
    if unknown_symbols:
        failures.append("undefined_symbols:" + ",".join(sorted(unknown_symbols)[:6]))
    if _THEORETICAL_UPGRADE_PATTERN.search(package.prose_explanation):
        failures.append("unsupported_theoretical_upgrade")
    return failures

class FormalizationAgent:
    """Validate and expose formal objects; it never upgrades authority."""

    def run(
        self,
        *,
        facts: CodeFactSetV1,
        equations: EquationClaimSetV1 | None = None,
        assumptions: tuple[str, ...] = (),
    ) -> FormalizationResultV1:
        return formalize_code_facts(facts=facts, equations=equations, assumptions=assumptions)


_FORMULA_TOKEN_STOP = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "is", "are", "be",
    "for", "with", "as", "by", "at", "from", "into", "that", "this", "each",
    "then", "when", "where", "which", "uses", "using", "use", "over", "between",
})
_OPERATOR_WORD_FAMILIES: dict[str, frozenset[str]] = {
    "+": frozenset({"plus", "sum", "add", "added", "addition", "total", "accumulate", "accumulated"}),
    "-": frozenset({"minus", "subtract", "subtracted", "difference", "remove", "removed", "decrement"}),
    "*": frozenset({"multiply", "multiplied", "product", "times", "scale", "scaled", "dot", "outer"}),
    "/": frozenset({"divide", "divided", "division", "ratio", "quotient", "normalize", "normalized", "scaling"}),
    "^": frozenset({"power", "squared", "cubed", "exponent", "exponential", "raised"}),
}
def _latex_command_tokens(latex: str) -> set[str]:
    """Extract LaTeX command tokens, ignoring environment wrappers.

    Whitespace escapes such as ``\\n`` in a serialized latex field are not
    math identifiers.  Typesetting and Greek commands are classified by the
    allowlists in ``validate_section_formula_package``, not here.
    """

    stripped = re.sub(r"\\begin\{[A-Za-z*]+\}", "", latex)
    stripped = re.sub(r"\\end\{[A-Za-z*]+\}", "", stripped)
    tokens = set(re.findall(r"\\[A-Za-z]+|\\[A-Za-z]+_[A-Za-z0-9]+", stripped))
    return tokens - _LATEX_WHITESPACE_ESCAPES


_FORMULA_DISPLAY_MATH_RE = re.compile(
    r"\$\$|\\\[|\\begin\{(?:equation|equation\*|align|align\*)\}"
)
_LATEX_WHITESPACE_ESCAPES = frozenset({r"\n", r"\t", r"\r"})
_LATEX_GREEK_COMMANDS = frozenset({
    r"\alpha", r"\beta", r"\gamma", r"\delta", r"\epsilon", r"\varepsilon",
    r"\zeta", r"\eta", r"\theta", r"\vartheta", r"\iota", r"\kappa",
    r"\lambda", r"\mu", r"\nu", r"\xi", r"\pi", r"\varpi", r"\rho",
    r"\varrho", r"\sigma", r"\varsigma", r"\tau", r"\upsilon", r"\phi",
    r"\varphi", r"\chi", r"\psi", r"\omega",
    r"\Gamma", r"\Delta", r"\Theta", r"\Lambda", r"\Xi", r"\Pi",
    r"\Sigma", r"\Upsilon", r"\Phi", r"\Psi", r"\Omega",
})
_LATEX_TYPESETTING_COMMANDS = frozenset({
    r"\int", r"\oint", r"\iint", r"\iiint",
    r"\mid", r"\vert", r"\Vert",
    r"\underbrace", r"\overbrace",
    r"\textbf", r"\textit", r"\textrm", r"\emph",
    r"\to", r"\mapsto", r"\ell", r"\sim", r"\simeq", r"\cong",
    r"\otimes", r"\oplus", r"\ominus", r"\odot",
    r"\langle", r"\rangle",
    r"\sin", r"\cos", r"\tan", r"\tanh", r"\sinh", r"\cosh",
    r"\lim", r"\ln", r"\arg", r"\det", r"\dim", r"\ker", r"\sup", r"\inf",
    r"\binom", r"\pmod", r"\bmod",
    r"\rightarrow", r"\leftarrow", r"\Rightarrow", r"\Leftarrow",
    r"\leftrightarrow", r"\Leftrightarrow", r"\iff", r"\implies",
    r"\wedge", r"\vee", r"\neg", r"\land", r"\lor",
    r"\emptyset", r"\varnothing", r"\colon", r"\prime",
    r"\nonumber", r"\not", r"\ast", r"\star",
})
_STANDARD_LATEX_COMMANDS = frozenset({
    r"\Delta", r"\delta", r"\Sigma", r"\sigma", r"\Theta", r"\theta",
    r"\Lambda", r"\lambda", r"\Phi", r"\phi", r"\Psi", r"\psi",
    r"\tau",
    r"\Omega", r"\omega", r"\Gamma", r"\gamma", r"\in", r"\le", r"\leq",
    r"\ge", r"\geq", r"\neq", r"\cdot", r"\times", r"\left", r"\right",
    r"\big", r"\Big", r"\bigg", r"\Bigg",
    r"\bigl", r"\bigr", r"\Bigl", r"\Bigr", r"\biggl", r"\biggr",
    r"\dot", r"\mathrm", r"\mathbf", r"\mathbb", r"\mathcal", r"\text",
    r"\operatorname", r"\frac", r"\exp", r"\log", r"\min", r"\max",
    r"\sum", r"\prod", r"\sqrt", r"\quad", r"\qquad", r"\ldots",
    r"\cdots", r"\pm", r"\mp", r"\infty", r"\partial", r"\nabla",
    r"\bigcup", r"\bigcap", r"\cup", r"\cap", r"\subset", r"\supset",
    r"\subseteq", r"\supseteq", r"\forall", r"\exists", r"\approx",
    r"\equiv", r"\propto", r"\ldots", r"\dots", r"\cdots",
    r"\aligned", r"\align", r"\equation", r"\gather", r"\matrix",
    r"\cases", r"\displaystyle", r"\limits", r"\over", r"\under",
    r"\hat", r"\bar", r"\tilde", r"\vec", r"\overline", r"\underline",
    r"\top", r"\bot", r"\perp", r"\angle", r"\circ",
}) | _LATEX_GREEK_COMMANDS | _LATEX_TYPESETTING_COMMANDS
_THEORETICAL_UPGRADE_PATTERN = re.compile(
    r"(?:converg|statistically significan|asymptotic|guarantees? (?:accuracy|performance)|"
    r"optimal|outperform|generaliz|sample complexity|lower bound on (?:loss|error)|"
    r"is (?:provably|theoretically) |proof of (?:convergence|optimality)|unbiased estimate)",
    flags=re.IGNORECASE,
)


def validate_formalization_proposal(
    proposal: FormalizationProposalV1,
    *,
    facts: CodeFactSetV1,
    equations: EquationClaimSetV1 | None = None,
    assumptions: tuple[str, ...] = (),
) -> list[str]:
    """Deterministic authority guards over a Formalization-Agent proposal.

    Rejects: unknown fact/equation ids; operand/value mutations; operator
    mutations; theoretical upgrades that code equivalence cannot license; and
    statements that do not bind the closed IDs they describe.
    """

    known_fact_ids = {item.fact_id for item in facts.facts}
    equation_by_id = {
        item.equation_id: item for item in (equations.equations if equations else ())
    }
    failures: list[str] = []
    for index, item in enumerate(proposal.items):
        label = f"item:{index}"
        unknown_facts = [fact_id for fact_id in item.fact_ids if fact_id not in known_fact_ids]
        if unknown_facts:
            failures.append(f"{label}:unknown_fact_ids:{','.join(sorted(unknown_facts))}")
        unknown_equations = [
            equation_id for equation_id in item.equation_ids
            if equation_id not in equation_by_id
        ]
        if unknown_equations:
            failures.append(f"{label}:unknown_equation_ids:{','.join(sorted(unknown_equations))}")
        for equation_id in item.equation_ids:
            if equation_id not in equation_by_id:
                continue
            equation = equation_by_id[equation_id]
            operand_failure = _operand_value_mutation(statement=item.statement, equation=equation)
            if operand_failure:
                failures.append(f"{label}:operand_or_value_mutation:{equation_id}:{operand_failure}")
            operator_failure = _operator_mutation(statement=item.statement, equation=equation)
            if operator_failure:
                failures.append(f"{label}:operator_mutation:{equation_id}:{operator_failure}")
        if _THEORETICAL_UPGRADE_PATTERN.search(item.statement):
            if assumptions:
                failures.append(
                    f"{label}:unsupported_theoretical_upgrade:assumptions_do_not_license_theory"
                )
            else:
                failures.append(f"{label}:unsupported_theoretical_upgrade:missing_assumptions")
        if not item.fact_ids and not item.equation_ids:
            failures.append(f"{label}:unbound_statement")
    return failures


def _binding_concrete_expression(equation: Any) -> str:
    """Substitute symbol bindings so the concrete operands are checked."""
    expression = str(getattr(equation, "expression", "") or "")
    for binding in getattr(equation, "symbol_bindings", ()) or ():
        expression = re.sub(
            r"(?<![A-Za-z0-9_])" + re.escape(str(binding.symbol)) + r"(?![A-Za-z0-9_])",
            str(binding.operand_value),
            expression,
        )
    return expression


def _equation_content_tokens(equation: Any) -> set[str]:
    concrete = _binding_concrete_expression(equation)
    tokens = re.findall(r"[a-z][a-z0-9_]*", concrete.lower())
    numbers = set(re.findall(r"\d+(?:\.\d+)?", concrete))
    return (set(tokens) - _FORMULA_TOKEN_STOP) | numbers


_FORMULA_CODE_TRACE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python_qualified_name", re.compile(
        r"\b(?:self|torch|numpy|np|tensorflow|tf|nn)\s*\.",
        flags=re.IGNORECASE,
    )),
    ("python_shape_index", re.compile(
        r"\b(?:shape|size|len)\s*\[",
        flags=re.IGNORECASE,
    )),
    ("python_function_name", re.compile(
        r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]*\s*\(",
    )),
)


def _formula_code_trace_failures(package: SectionFormulaPackageV1) -> list[str]:
    """Detect implementation syntax that should not be a paper formula."""

    surface = " ".join((
        package.latex,
        package.markdown_block,
        package.prose_explanation,
    ))
    return [
        f"code_shaped_formula:{name}"
        for name, pattern in _FORMULA_CODE_TRACE_PATTERNS
        if pattern.search(surface)
    ]


def _operand_value_mutation(*, statement: str, equation: Any) -> str:
    statement_tokens = set(re.findall(r"[a-z][a-z0-9_]*", statement.lower()))
    statement_tokens |= set(re.findall(r"\d+(?:\.\d+)?", statement))
    required = _equation_content_tokens(equation)
    if not required:
        return ""
    missing = required - statement_tokens
    if missing:
        return "missing_operands_or_values:" + ",".join(sorted(missing)[:6])
    return ""


def _operator_mutation(*, statement: str, equation: Any) -> str:
    concrete = _binding_concrete_expression(equation)
    present_operators = set(concrete) & set("+-*/^")
    if not present_operators:
        return ""
    statement_lower = statement.lower()
    covered: list[str] = []
    for operator in sorted(present_operators):
        family = _OPERATOR_WORD_FAMILIES.get(operator, frozenset())
        if operator in statement_lower or any(word in statement_lower for word in family):
            covered.append(operator)
    if set(covered) != present_operators:
        return "missing_operators:" + ",".join(sorted(present_operators - set(covered)))
    return ""


def formalize_code_facts(
    *,
    facts: CodeFactSetV1,
    equations: EquationClaimSetV1 | None = None,
    assumptions: tuple[str, ...] = (),
) -> FormalizationResultV1:
    """Build a symbol table and proof-obligation ledger from exact artifacts."""

    fact_by_id = {fact.fact_id: fact for fact in facts.facts}
    symbols: dict[str, SymbolDefinitionV1] = {}
    for fact in facts.facts:
        values = [fact.subject]
        values.extend(fact.object if isinstance(fact.object, list) else [fact.object])
        for value in values:
            if not value:
                continue
            symbols.setdefault(
                value,
                SymbolDefinitionV1(
                    symbol=value,
                    meaning=f"operand of {fact.predicate}",
                    fact_ids=(fact.fact_id,),
                    source_artifact_ids=tuple(fact.direct_span_ids + fact.relation_span_ids),
                    conditions=tuple(fact.conditions),
                ),
            )
    equation_rows: list[dict[str, Any]] = []
    obligations: list[ProofObligationV1] = []
    risks: list[FormalizationRiskV1] = []
    if equations is not None:
        for equation in equations.equations:
            selected = [fact_by_id[fact_id] for fact_id in equation.fact_ids if fact_id in fact_by_id]
            missing = [fact_id for fact_id in equation.fact_ids if fact_id not in fact_by_id]
            if missing:
                risks.append(FormalizationRiskV1(
                    risk_id=f"risk:{equation.equation_id}:missing_fact",
                    kind="missing_fact",
                    message="Equation references a fact absent from the supplied fact set.",
                    fact_ids=tuple(missing),
                ))
                continue
            equation_rows.append(equation.model_dump(mode="json"))
            obligations.append(ProofObligationV1(
                proof_obligation_id=f"proof:{equation.equation_id}",
                statement=f"The displayed expression is equivalent to the selected code operations for {equation.equation_id}.",
                assumptions=tuple(dict.fromkeys([*assumptions, *equation.conditions])),
                conclusion=equation.expression,
                supporting_fact_ids=tuple(equation.fact_ids),
                derivation_steps=tuple(
                    f"Bind {binding.symbol} to {binding.operand_value} from {binding.fact_id}."
                    for binding in equation.symbol_bindings
                ),
                status="supported" if selected else "unproved",
            ))
    # Code facts can support an algorithmic identity, but not a statistical or
    # convergence theorem.  Keep this distinction explicit for downstream
    # writer and editor gates.
    if not assumptions and equation_rows:
        risks.append(FormalizationRiskV1(
            risk_id="risk:missing_assumptions",
            kind="missing_assumptions",
            message="A formal expression is available, but no independent assumptions were supplied.",
            blocking=False,
        ))
    return FormalizationResultV1(
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
        fact_digest=facts.content_digest,
        equation_digest=equations.content_digest if equations is not None else "",
        symbols=tuple(symbols.values()),
        equations=tuple(equation_rows),
        proof_obligations=tuple(obligations),
        risks=tuple(risks),
    )


class SectionFormulaPackageBatchV1(BaseModel):
    """Legacy LLM response schema for one section formula packages (Q2).

    Prefer ``SectionFormalizerResponseV1`` for guided decoding; this batch
    wrapper remains for representation-only recovery of historical payloads.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    section_id: str
    packages: tuple[SectionFormulaPackageV1, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _valid(self) -> "SectionFormulaPackageBatchV1":
        if not self.section_id.strip():
            raise ValueError("formula package batch requires section id")
        if _PLACEHOLDER_SECTION_ID_RE.fullmatch(self.section_id.strip()):
            raise ValueError("formula package batch rejects placeholder section id")
        if any(item.section_id != self.section_id for item in self.packages):
            raise ValueError("formula package batch contains a foreign section id")
        return self


class SectionFormalizerResponseV1(BaseModel):
    """Discriminated Formalizer outcome for one section (WP3 Slice 3A).

    ``rendered`` carries accepted packages; ``unresolved`` records missing
    operands/relations; ``not_applicable`` is allowed only when WP1 already
    marked the section formula-not-applicable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal["rendered", "unresolved", "not_applicable"]
    section_id: str
    packages: tuple[SectionFormulaPackageV1, ...] = Field(default_factory=tuple)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    missing_operand_roles: tuple[str, ...] = Field(default_factory=tuple)
    missing_relation_roles: tuple[str, ...] = Field(default_factory=tuple)
    review_question: str = ""
    reason: str = ""

    @model_validator(mode="after")
    def _outcome_consistency(self) -> "SectionFormalizerResponseV1":
        section_id = self.section_id.strip()
        if not section_id:
            raise ValueError("section formalizer response requires section id")
        if _PLACEHOLDER_SECTION_ID_RE.fullmatch(section_id):
            raise ValueError("section formalizer response rejects placeholder section id")
        if self.outcome == "rendered" and not self.packages:
            raise ValueError("rendered outcome requires at least one package")
        if self.outcome == "unresolved" and not self.review_question.strip():
            raise ValueError("unresolved outcome requires review_question")
        if self.outcome == "not_applicable" and not self.reason.strip():
            raise ValueError("not_applicable outcome requires reason")
        if any(item.section_id != section_id for item in self.packages):
            raise ValueError("section formalizer response contains a foreign section id")
        for package in self.packages:
            latex = package.latex.strip()
            if _PLACEHOLDER_SECTION_ID_RE.fullmatch(latex) or latex in {section_id, f"{{{section_id}}}"}:
                raise ValueError("formula package latex must not be a section placeholder")
        return self


def validate_section_formalizer_response(
    response: SectionFormalizerResponseV1,
    *,
    section_id: str,
    formula_obligation_required: bool,
    formula_not_applicable: bool,
    formula_obligations: tuple[MethodFormulaObligationV2, ...] = (),
) -> list[str]:
    """Fail-closed checks for obligation-aware Formalizer outcomes."""

    failures: list[str] = []
    if response.section_id != section_id:
        failures.append("foreign_section_id")
    if formula_obligation_required:
        if response.outcome == "not_applicable" and not formula_not_applicable:
            failures.append("not_applicable_without_wp1_authority")
        if response.outcome == "rendered" and not response.packages:
            failures.append("empty_packages_with_obligation")
    if formula_obligations and not any(
        item.expectation in {"required", "preferred"}
        for item in formula_obligations
    ) and response.outcome == "rendered":
        failures.append("formula_rendered_for_none_expectation")
    return failures


class AuthorIntentSectionFormalizerResponseV1(BaseModel):
    """Guided-decoding schema for the author-intent Formalizer lane.

    ``unresolved`` with an empty package list is not a legal success on this
    lane, so native JSON schema must not offer that outcome.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    outcome: Literal["rendered"] = "rendered"
    section_id: str
    packages: tuple[SectionFormulaPackageV1, ...] = Field(min_length=1, max_length=3)
    formula_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    review_question: str = ""
    reason: str = ""


def _normalize_formalizer_payload(
    payload: Mapping[str, Any],
    *,
    section_id: str,
) -> dict[str, Any]:
    """Representation-only salvage of Formalizer JSON.

    Live qwen36 labeled a complete ``packages`` list ``outcome=unresolved``
    without ``review_question``, which discarded already-written latex.
    Non-empty packages are a rendered outcome.  Missing identity/purpose
    labels are filled; latex is never invented.
    """

    data = dict(payload)
    if not str(data.get("section_id") or "").strip():
        data["section_id"] = section_id
    packages = data.get("packages")
    if isinstance(packages, list) and packages:
        data["outcome"] = "rendered"
        allowed = set(SectionFormulaPackageV1.model_fields)
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(packages):
            if not isinstance(item, Mapping):
                continue
            row = {key: value for key, value in dict(item).items() if key in allowed}
            if not str(row.get("section_id") or "").strip():
                row["section_id"] = str(data["section_id"])
            if not str(row.get("package_id") or "").strip():
                row["package_id"] = f"fp:{data['section_id']}:author-intent:{index + 1}"
            if not str(row.get("purpose") or "").strip():
                row["purpose"] = "Formalize the section's author-intent mechanism."
            if not str(row.get("prose_explanation") or "").strip():
                row["prose_explanation"] = row["purpose"]
            if not str(row.get("latex") or "").strip():
                continue
            normalized.append(row)
        data["packages"] = normalized
    elif str(data.get("outcome") or "") == "unresolved" and not str(
        data.get("review_question") or ""
    ).strip():
        data["review_question"] = (
            "Which repository evidence would upgrade this formula?"
        )
    return data


def coerce_section_formalizer_response(
    payload: Any,
    *,
    section_id: str,
) -> SectionFormalizerResponseV1 | None:
    """Parse guided-decoding payloads, including legacy package batches."""

    if isinstance(payload, SectionFormalizerResponseV1):
        if payload.packages and payload.outcome != "rendered":
            try:
                return payload.model_copy(update={"outcome": "rendered"})
            except (TypeError, ValueError):
                return payload
        return payload
    if isinstance(payload, AuthorIntentSectionFormalizerResponseV1):
        return SectionFormalizerResponseV1(
            outcome="rendered",
            section_id=payload.section_id,
            packages=payload.packages,
            formula_obligation_ids=payload.formula_obligation_ids,
            review_question=payload.review_question,
            reason=payload.reason,
        )
    if isinstance(payload, SectionFormulaPackageBatchV1):
        if not payload.packages:
            return None
        return SectionFormalizerResponseV1(
            outcome="rendered",
            section_id=payload.section_id,
            packages=payload.packages,
        )
    if isinstance(payload, dict):
        data = _normalize_formalizer_payload(payload, section_id=section_id)
        if data.get("packages"):
            try:
                return SectionFormalizerResponseV1.model_validate(data)
            except (TypeError, ValueError):
                pass
        if "outcome" in data:
            try:
                return SectionFormalizerResponseV1.model_validate(data)
            except (TypeError, ValueError):
                return None
        if "packages" in data:
            try:
                batch = SectionFormulaPackageBatchV1.model_validate(data)
            except (TypeError, ValueError):
                return None
            if batch.section_id != section_id or not batch.packages:
                return None
            return SectionFormalizerResponseV1(
                outcome="rendered",
                section_id=batch.section_id,
                packages=batch.packages,
            )
    return None


def load_formalization_section_results(
    path: str | Path,
) -> tuple[FormalizationSectionResultV1, ...]:
    """Load persisted section-scoped formalization outcomes."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sections = payload.get("sections") if isinstance(payload, dict) else ()
    results: list[FormalizationSectionResultV1] = []
    for item in sections or ():
        try:
            results.append(FormalizationSectionResultV1.model_validate(item))
        except (TypeError, ValueError):
            continue
    return tuple(results)


def _package_covers_formula_obligation(package: SectionFormulaPackageV1, obligation_id: str) -> bool:
    """Exact package-to-obligation binding; unmatched obligations stay unresolved."""

    target = str(obligation_id or "").strip()
    if not target:
        return False
    keys = {target, target.casefold()}
    if target.startswith("formula:"):
        tail = target[len("formula:"):]
        keys.update({tail, tail.casefold(), f"equation:{tail}", f"formula:{tail}"})
    elif target.startswith("equation:"):
        tail = target[len("equation:"):]
        keys.update({tail, tail.casefold(), f"formula:{target}", f"formula:equation:{tail}"})
    bound = {
        str(item).strip()
        for item in (package.bound_equation_ids or ())
        if str(item).strip()
    }
    bound_folded = {item.casefold() for item in bound}
    return bool(keys & bound) or bool({item.casefold() for item in keys} & bound_folded)


def resolve_formalization_route_artifact(
    request: Any,
    *,
    section_results: tuple[FormalizationSectionResultV1, ...] | list[FormalizationSectionResultV1],
    equations: Any | None = None,
    facts: Any | None = None,
) -> WritingResearchCallbackArtifactV1 | None:
    """Bind one formal_derivation request to a section-scoped accepted package.

    Global ``FormalizationResultV1`` digests never fulfill callbacks.  A
    package must match the request section, overlap candidate equation/fact
    ids when supplied, and pass deterministic package guards when equations
    and facts are available.
    """

    from code2paper.agentic.method_argument_models import WritingResearchCallbackArtifactV1

    section_id = str(getattr(request, "section_id", "") or "").strip()
    if not section_id:
        return None
    candidates = {
        str(term).strip().casefold()
        for term in (getattr(request, "candidate_symbols_or_terms", ()) or ())
        if str(term).strip()
    }
    section_result = next(
        (
            item for item in section_results
            if str(item.section_id) == section_id
        ),
        None,
    )
    if section_result is None or not section_result.packages:
        return None
    target_obligations = {
        str(item).strip()
        for item in (getattr(request, "target_formula_obligation_ids", ()) or ())
        if str(item).strip()
    }
    rendered_package_ids = {
        str(truth.package_id)
        for truth in (getattr(section_result, "obligation_truths", ()) or ())
        if str(getattr(truth, "outcome", "") or "") == "rendered"
        and str(getattr(truth, "obligation_id", "") or "") in target_obligations
        and str(getattr(truth, "package_id", "") or "").strip()
    }
    for package in section_result.packages:
        if str(package.section_id) != section_id:
            continue
        if target_obligations:
            if rendered_package_ids:
                if str(package.package_id) not in rendered_package_ids:
                    continue
            elif getattr(section_result, "formula_obligations", ()):
                # Current sections expose the canonical route explicitly;
                # do not fall back to equation/facet aliases when a package
                # lacks the requested obligation id.
                if str(package.obligation_id or "").strip() not in target_obligations:
                    continue
            elif not any(
                    _package_covers_formula_obligation(package, obligation_id)
                    for obligation_id in target_obligations
                ):
                    continue
        package_equations = {
            str(item).strip().casefold()
            for item in (package.bound_equation_ids or ())
            if str(item).strip()
        }
        package_facts = {
            str(item).strip().casefold()
            for item in (package.bound_fact_ids or ())
            if str(item).strip()
        }
        if candidates and not (
            candidates & package_equations
            or candidates & package_facts
        ):
            continue
        if equations is not None and facts is not None:
            guard_failures = validate_section_formula_package(
                package,
                equations=equations,
                facts=facts,
            )
            if guard_failures:
                continue
        return WritingResearchCallbackArtifactV1(
            artifact_id=f"formula:{package.package_id}",
            request_id=str(request.request_id),
            section_id=section_id,
            argument_unit_id=str(request.argument_unit_id),
            authority_lane="formal_derivation",
            artifact_ref=str(package.package_id),
            artifact_digest=str(package.content_digest),
            validated=True,
        )
    return None


def build_deterministic_formula_packages(
    *,
    section_id: str,
    equations: Any,
    facts: Any,
    allowed_equation_ids: set[str] | None = None,
    formula_obligations: tuple[MethodFormulaObligationV2, ...] | list[MethodFormulaObligationV2] = (),
) -> tuple[SectionFormulaPackageV1, ...]:
    """Representation-only formula packages from authorized core equations.

    Used when no LLM Formalizer is configured (isolated static milestone):
    the authorized LaTeX expression and its symbol bindings are carried
    verbatim with a deterministic reader explanation built from the
    operation descriptors.  This is representation, never invented math.

    Review P0-Q2: only mechanism-level core equations (``select_core_equations``)
    are admitted; equations are deduplicated by canonical identity and grouped
    by mechanism so a section receives ONE meaningful package per mechanism
    instead of a raw x+y wrapper per source operation.  Symbol meanings are
    reader-facing; internal ids never enter them.
    """

    selected = select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids=allowed_equation_ids,
    )
    facts_by_id = {fact.fact_id: fact for fact in (facts.facts if facts is not None else ())}
    # Deduplicate by canonical identity (same expression + same facts),
    # then group by the mechanism descriptor the equation formalizes.
    seen_identities: set[str] = set()
    groups: dict[str, list[Any]] = {}
    for equation in selected:
        identity = (
            str(getattr(equation, "canonical_identity", "") or "")
            or str(getattr(equation, "equation_id", "") or "")
        )
        if not identity or identity in seen_identities:
            continue
        if is_bare_binary_expression(str(getattr(equation, "expression", "") or "")):
            continue
        if effective_formula_role(equation) == "incidental":
            continue
        seen_identities.add(identity)
        descriptors = [
            str(item).strip().casefold()
            for item in (getattr(equation, "operation_descriptors", ()) or ())
        ]
        mechanism = next(
            (descriptor for descriptor in descriptors
             if descriptor in _CORE_EQUATION_DESCRIPTORS),
            "",
        )
        if not mechanism:
            mechanism = next(
                (
                    str(getattr(facts_by_id.get(fact_id), "predicate", "") or "")
                    for fact_id in (getattr(equation, "fact_ids", ()) or ())
                    if fact_id in facts_by_id
                    and _predicate_is_mechanism(
                        str(getattr(facts_by_id.get(fact_id), "predicate", "") or "")
                    )
                ),
                "core mechanism",
            )
        groups.setdefault(mechanism, []).append(equation)

    obligations = tuple(formula_obligations or ())

    def _formula_identity(value: Any) -> set[str]:
        raw = str(value or "").strip()
        if not raw:
            return set()
        values = {raw}
        if raw.startswith("formula:"):
            values.add(raw[len("formula:"):])
        if raw.startswith("equation:"):
            values.add(raw[len("equation:"):])
        return values

    def _package_obligation(group: list[Any]) -> MethodFormulaObligationV2 | None:
        if not obligations:
            return None
        equation_ids = {
            str(getattr(item, "equation_id", "") or "").strip()
            for item in group
            if str(getattr(item, "equation_id", "") or "").strip()
        }
        equation_keys = set().union(*(_formula_identity(item) for item in equation_ids)) if equation_ids else set()
        matches = []
        for obligation in obligations:
            obligation_keys = _formula_identity(obligation.obligation_id)
            if equation_keys.intersection(obligation_keys):
                matches.append(obligation)
        # A single mechanism group can be safely bound to the sole current
        # obligation even when the id is facet-scoped rather than equation-
        # scoped.  Multiple obligations remain unbound and are rejected by
        # the strict route validator instead of being guessed.
        if len(matches) == 1:
            return matches[0]
        if len(obligations) == 1 and len(groups) == 1:
            return obligations[0]
        return None

    packages: list[SectionFormulaPackageV1] = []
    for index, (mechanism, group) in enumerate(
        sorted(groups.items(), key=lambda item: item[0]), start=1
    ):
        primary = group[0]
        obligation = _package_obligation(group)
        consumer = ""
        obligation_id = ""
        bound_facets: tuple[str, ...] = ()
        if obligation is not None:
            obligation_id = str(obligation.obligation_id)
            consumer = str(
                obligation.consumer_paragraph_id
                or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
            ).strip()
            bound_facets = tuple(obligation.facet_ids)
        bound_facts = tuple(
            fact_id for fact_id in (getattr(primary, "fact_ids", ()) or ())
            if fact_id in facts_by_id
        )
        symbol_definitions = tuple(
            (
                str(binding.symbol),
                f"repository operand {binding.operand_value!r} ({binding.operand_role})",
            )
            for binding in (getattr(primary, "symbol_bindings", ()) or ())
            if str(getattr(binding, "symbol", "") or "").strip()
        )
        packages.append(SectionFormulaPackageV1(
            package_id=f"fp:{section_id}:{index}",
            section_id=section_id,
            obligation_id=obligation_id,
            consumer_paragraph_id=consumer,
            purpose=f"Formalize the {mechanism} that this section explains.",
            latex=str(getattr(primary, "expression", "") or ""),
            prose_explanation=(
                "This expression states the " + mechanism
                + " in paper notation; every symbol is bound to an exact repository operand "
                + "and the formula preserves the authorized code expression."
            ),
            symbol_definitions=symbol_definitions,
            material_conditions=tuple(
                str(item) for item in (getattr(primary, "conditions", ()) or ()) if str(item).strip()
            ),
            assumptions=tuple(dict.fromkeys(
                str(item) for item in (getattr(primary, "conditions", ()) or ()) if str(item).strip()
            )),
            authority_status="code_verified",
            bound_facet_ids=bound_facets,
            bound_fact_ids=bound_facts,
            bound_equation_ids=(str(primary.equation_id),),
        ))
    return tuple(packages)


def build_formula_obligation_truths(
    *,
    section_id: str,
    obligation_ids: tuple[str, ...],
    packages: tuple[SectionFormulaPackageV1, ...],
    disposition: SectionFormulaDispositionV1 | None,
    formula_not_applicable: bool,
    obligations: tuple[MethodFormulaObligationV2, ...] = (),
) -> tuple[SectionFormulaObligationTruthV1, ...]:
    """Map each section formula obligation to rendered or unresolved truth."""

    obligation_by_id = {
        str(item.obligation_id): item for item in obligations
    }
    if obligations:
        obligation_ids = tuple(
            dict.fromkeys(
                [
                    *obligation_ids,
                    *(str(item.obligation_id) for item in obligations),
                ]
            )
        )
    if not obligation_ids and formula_not_applicable:
        return (
            SectionFormulaObligationTruthV1(
                obligation_id=f"formula:section:{section_id}:none",
                outcome="not_applicable",
                reason="section marked formula_not_applicable",
                expectation="none",
            ),
        )
    package_by_equation: dict[str, SectionFormulaPackageV1] = {}
    package_by_obligation: dict[str, SectionFormulaPackageV1] = {}
    for package in packages:
        if str(package.obligation_id or "").strip():
            package_by_obligation[str(package.obligation_id)] = package
        for equation_id in (package.bound_equation_ids or ()):
            package_by_equation[str(equation_id)] = package
            tail = str(equation_id).split(":", 1)[-1]
            package_by_equation[tail] = package
            package_by_equation[f"formula:{equation_id}"] = package
            package_by_equation[f"formula:equation:{tail}"] = package
    truths: list[SectionFormulaObligationTruthV1] = []
    strict_identity = bool(obligations)
    for obligation_id in obligation_ids:
        obligation = obligation_by_id.get(str(obligation_id))
        eq_key = str(obligation_id)
        if eq_key.startswith("formula:"):
            eq_key = eq_key[len("formula:"):]
        package = package_by_obligation.get(str(obligation_id))
        if not strict_identity:
            package = (
                package
                or package_by_equation.get(str(obligation_id))
                or package_by_equation.get(eq_key)
                or package_by_equation.get(f"equation:{eq_key}")
                or package_by_equation.get(f"formula:{eq_key}")
            )
        if package is not None and obligation is not None:
            expected_consumer = str(
                getattr(obligation, "consumer_paragraph_id", "")
                or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
            ).strip()
            package_consumer = str(package.consumer_paragraph_id or "").strip()
            if expected_consumer and package_consumer != expected_consumer:
                package = None
        if package is None and obligation is not None and obligation.facet_ids and not strict_identity:
            package = next(
                (
                    candidate
                    for candidate in packages
                    if set(obligation.facet_ids)
                    & set(candidate.bound_facet_ids)
                    and (
                        not str(
                            getattr(obligation, "consumer_paragraph_id", "")
                            or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
                        ).strip()
                        or str(candidate.consumer_paragraph_id or "").strip()
                        == str(
                            getattr(obligation, "consumer_paragraph_id", "")
                            or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
                        ).strip()
                    )
                ),
                None,
            )
        expectation = (
            obligation.expectation
            if obligation is not None
            else "required"
        )
        if package is not None and package in packages:
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="rendered",
                package_id=package.package_id,
                expectation=expectation,
            ))
            continue
        if expectation == "none":
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="not_applicable",
                reason="formula expectation is none",
                expectation=expectation,
            ))
            continue
        if disposition is not None:
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="unresolved",
                review_question=disposition.review_question,
                reason=disposition.review_note,
                expectation=expectation,
                blocking=expectation == "required",
            ))
        else:
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="unresolved",
                review_question=(
                    "Which repository evidence binds this section formula obligation?"
                ),
                expectation=expectation,
                blocking=expectation == "required",
            ))
    return tuple(truths)


def section_result_from_packages(
    *,
    section_id: str,
    packages: tuple[SectionFormulaPackageV1, ...],
    obligation_ids: tuple[str, ...] = (),
    formula_not_applicable: bool = False,
    formula_obligations: tuple[MethodFormulaObligationV2, ...] = (),
    evidence_packs: tuple[MechanismEquationEvidencePackV1, ...] = (),
) -> FormalizationSectionResultV1:
    """Wrap accepted packages into a section result (empty packages never
    silently count as completion).
    """

    # Bind each accepted package to one planned obligation/consumer before it
    # reaches the Writer.  Facet/equation overlap is only a compatibility
    # resolver for historical packages; current packages should already carry
    # the explicit ids.  Ambiguous packages remain unbound and therefore
    # cannot satisfy a required paragraph transaction.
    normalized_packages: list[SectionFormulaPackageV1] = []
    route_failures: list[str] = []
    obligation_by_id = {
        str(item.obligation_id): item
        for item in formula_obligations
        if str(item.obligation_id).strip()
    }
    for package in packages:
        package_obligation_id = str(package.obligation_id or "").strip()
        package_consumer_id = str(package.consumer_paragraph_id or "").strip()
        if package_obligation_id:
            obligation = obligation_by_id.get(package_obligation_id)
            if obligation is None:
                route_failures.append(
                    f"unknown_obligation:{package.package_id}:{package_obligation_id}"
                )
            else:
                expected_consumer = str(
                    obligation.consumer_paragraph_id
                    or (
                        obligation.paragraph_ids[0]
                        if len(obligation.paragraph_ids) == 1 else ""
                    )
                ).strip()
                if expected_consumer and package_consumer_id != expected_consumer:
                    route_failures.append(
                        f"consumer_mismatch:{package_obligation_id}"
                    )
                elif obligation.paragraph_ids and not expected_consumer:
                    route_failures.append(
                        f"consumer_not_unique:{package_obligation_id}"
                    )
                elif not expected_consumer and package_consumer_id:
                    route_failures.append(
                        f"consumer_not_planned:{package_obligation_id}"
                    )
            normalized_packages.append(package)
            continue
        matches = [
            obligation
            for obligation in formula_obligations
            if (
                (set(package.bound_facet_ids) & set(obligation.facet_ids))
                or str(obligation.obligation_id) in set(package.bound_equation_ids)
            )
        ]
        if len(matches) == 1:
            obligation = matches[0]
            consumer = str(
                getattr(obligation, "consumer_paragraph_id", "")
                or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
            ).strip()
            package = package.model_copy(update={
                "obligation_id": str(obligation.obligation_id),
                "consumer_paragraph_id": consumer,
            })
        elif formula_obligations:
            route_failures.append(
                f"ambiguous_obligation:{package.package_id}"
            )
        normalized_packages.append(package)
    packages = tuple(normalized_packages)
    # An obligation and a consumer are one-to-one.  If a Formalizer returns
    # duplicate routes, retain the typed failure and expose no accepted
    # packages to downstream Writer/trace code.
    explicit_obligation_ids = [
        str(package.obligation_id).strip()
        for package in packages
        if str(package.obligation_id or "").strip()
    ]
    explicit_consumers = [
        str(package.consumer_paragraph_id).strip()
        for package in packages
        if str(package.consumer_paragraph_id or "").strip()
    ]
    if len(explicit_obligation_ids) != len(set(explicit_obligation_ids)):
        route_failures.append("duplicate_obligation_consumers")
    if len(explicit_consumers) != len(set(explicit_consumers)):
        route_failures.append("duplicate_consumer_paragraphs")
    if route_failures:
        packages = ()

    effective_obligation_ids = tuple(dict.fromkeys([
        *obligation_ids,
        *(item.obligation_id for item in formula_obligations),
    ]))
    if packages:
        disposition = None
    elif not effective_obligation_ids and formula_not_applicable:
        disposition = SectionFormulaDispositionV1(
            section_id=section_id,
            disposition="not_applicable",
            review_question="Does this section need a core mechanism formula, and which repository evidence would bind it?",
            review_note="No formula-worthy mechanism facet or equation is bound to this section.",
            blocking_for_candidate=False,
        )
    else:
        disposition = SectionFormulaDispositionV1(
            section_id=section_id,
            disposition="formalizer_empty",
            review_question="Which core mechanism formula should this section present, and which repository evidence binds it?",
            review_note=(
                "Formula package route failed: " + "; ".join(dict.fromkeys(route_failures))
                if route_failures
                else "Core equation evidence exists but the Formalizer produced no accepted package."
            ),
            required_obligation_ids=tuple(
                item.obligation_id
                for item in formula_obligations
                if item.expectation == "required"
            ),
            preferred_obligation_ids=tuple(
                item.obligation_id
                for item in formula_obligations
                if item.expectation == "preferred"
            ),
            blocking_for_candidate=False,
        )
    obligation_truths = build_formula_obligation_truths(
        section_id=section_id,
        obligation_ids=effective_obligation_ids,
        packages=packages,
        disposition=disposition,
        formula_not_applicable=formula_not_applicable,
        obligations=formula_obligations,
    )
    required_formula_failures = tuple(
        truth.obligation_id
        for truth in obligation_truths
        if truth.expectation == "required"
        and truth.outcome != "rendered"
    )
    preferred_formula_review_ids = tuple(
        truth.obligation_id
        for truth in obligation_truths
        if truth.expectation == "preferred"
        and truth.outcome != "rendered"
    )
    return FormalizationSectionResultV1(
        section_id=section_id,
        packages=packages,
        disposition=disposition,
        obligation_truths=obligation_truths,
        formula_obligations=formula_obligations,
        evidence_packs=evidence_packs,
        required_formula_failures=required_formula_failures,
        preferred_formula_review_ids=preferred_formula_review_ids,
        formula_route_failures=tuple(dict.fromkeys(route_failures)),
    )


__all__ = [
    "FormalizationAgent",
    "FormalizationProposalItemV1",
    "FormalizationProposalV1",
    "FormalizationResultV1",
    "FormalizationRiskV1",
    "FormulaLaneV1",
    "FormulaReviewStatusV1",
    "MethodFormulaObligationV2",
    "MechanismEquationEvidencePackV1",
    "FormalizationSectionResultV1",
    "SectionFormulaDispositionV1",
    "SectionFormulaObligationTruthV1",
    "SectionFormulaPackageBatchV1",
    "SectionFormalizerResponseV1",
    "AuthorIntentSectionFormalizerResponseV1",
    "SectionFormulaPackageV1",
    "SymbolDefinitionV1",
    "build_deterministic_formula_packages",
    "build_mechanism_equation_evidence_packs",
    "build_formula_obligation_truths",
    "coerce_section_formalizer_response",
    "formalize_code_facts",
    "load_formalization_section_results",
    "resolve_formalization_route_artifact",
    "section_result_from_packages",
    "select_core_equations",
    "validate_formalization_proposal",
    "validate_section_formalizer_response",
    "validate_section_formula_package",
]
