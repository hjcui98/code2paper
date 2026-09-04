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
    # Canonical mechanism identity used by the Architect to de-duplicate
    # alias obligations that formalize the same transformation in one
    # paragraph.  Distinct facet ids may share one mechanism_key; only the
    # canonical obligation is then emitted to the Formalizer.
    mechanism_key: str = ""
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


def facet_mechanism_key(facet: Any) -> str:
    """Canonical, paragraph-independent mechanism identity for one facet.

    Two facets that formalize the same transformation share this key.  The
    Architect and the obligation builder use it to de-duplicate alias
    obligations instead of emitting one paper formula per facet.  The key is
    derived from the facet's reader-facing operation/subject, never from
    project paths, symbols, or known answers; an empty key means "no shared
    mechanism identity" and disables de-duplication for that facet.
    """

    fields = dict(getattr(facet, "semantic_fields", {}) or {})
    explicit = str(fields.get("mechanism_key") or "").strip()
    operation = str(
        fields.get("operation")
        or fields.get("mechanism")
        or fields.get("transformation")
        or fields.get("subject")
        or ""
    ).strip()
    if explicit:
        operation = explicit
    if operation:
        return "mechanism:" + re.sub(r"\s+", " ", operation.casefold())
    # Formula facets often carry only a long mathematical goal.  Use a
    # canonical role only when the goal has one unambiguous role signal;
    # umbrella goals that mention several stages deliberately stay
    # uncollapsed so a positional/attention/loss distinction is not erased.
    goal = str(
        fields.get("formula_goal")
        or fields.get("mathematical_goal")
        or getattr(facet, "exact_source_quote", "")
        or ""
    ).casefold()
    role_signals = (
        ("contrastive_loss", ("infonce", "contrastive loss", "contrastive")),
        ("attention_mask", ("masked attention", "attention mask", "attention")),
        ("positional_encoding", ("positional encoding", "position encoding", "sinusoidal")),
        ("embedding_augmentation", ("augment", "additive embedding", "embedding augmentation")),
        ("inference_ranking", ("dot-product", "dot product", "ranking", "rank passages")),
        ("normalization", ("normaliz", "softmax")),
        ("state_update", ("state update", "selective scan")),
        ("propagation", ("pagerank", "page rank", "propagat")),
    )
    matches = [
        role for role, signals in role_signals
        if any(signal in goal for signal in signals)
    ]
    if len(matches) == 1:
        return "mechanism:" + matches[0]
    return ""


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
    dossier_ids: tuple[str, ...] = Field(default_factory=tuple)
    ordered_operation_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    call_path_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    data_flow_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    configuration_bindings: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    default_activation: Literal["active", "inactive", "conditional", "unknown"] = "unknown"
    unresolved_relations: tuple[str, ...] = Field(default_factory=tuple)
    operation_atoms: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    formalizable_signatures: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
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
            "dossier_ids",
            "ordered_operation_node_ids",
            "call_path_relation_ids",
            "data_flow_relation_ids",
            "unresolved_relations",
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


def normalize_formula_latex_body(latex: str) -> str:
    """Representation-only normalization stripping outer display math delimiters.

    Strips outer display wrappers such as $$...$$, \\[...\\],
    \\begin{equation}...\\end{equation} while leaving mathematical
    identifiers, operators, aligned/array environments, conditions, and numbers
    unchanged.
    """

    body = str(latex or "").strip()
    if not body:
        return ""
    changed = True
    while changed:
        changed = False
        if body.startswith("$$") and body.endswith("$$") and len(body) >= 4:
            inner = body[2:-2].strip()
            if "$$" not in inner:
                body = inner
                changed = True
                continue
        if body.startswith(r"\[") and body.endswith(r"\]") and len(body) >= 4:
            inner = body[2:-2].strip()
            if r"\]" not in inner and r"\[" not in inner:
                body = inner
                changed = True
                continue
        for eq_env in ("equation", "equation*", "displaymath"):
            begin_tag = rf"\begin{{{eq_env}}}"
            end_tag = rf"\end{{{eq_env}}}"
            if (
                body.startswith(begin_tag)
                and body.endswith(end_tag)
                and len(body) >= len(begin_tag) + len(end_tag)
            ):
                inner = body[len(begin_tag):-len(end_tag)].strip()
                if begin_tag not in inner and end_tag not in inner:
                    body = inner
                    changed = True
                    break
    return body


def canonical_formula_markdown_block(latex: str) -> str:
    """Exactly one display-math block; Writer inputs stay off this surface."""

    body = normalize_formula_latex_body(str(latex or "")).strip()
    if not body:
        return ""
    return "$$\n" + body + "\n$$"


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
    # One accepted package may formalize several section obligations when they
    # share a single consumer paragraph (Section 6.4).  ``obligation_id`` is
    # retained only as a compatibility alias for single-obligation artifacts.
    satisfied_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    # Stable digest over the reader-facing math content (latex, symbol table,
    # conditions, assumptions) used for recovery and reference; not a quality
    # score.
    semantic_formula_digest: str = ""
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
        normalized_latex = normalize_formula_latex_body(self.latex)
        if normalized_latex != self.latex:
            object.__setattr__(self, "latex", normalized_latex)
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
        object.__setattr__(
            self,
            "markdown_block",
            canonical_formula_markdown_block(self.latex),
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
        if self.review_status == "accepted" and not (
            lane == "repository_derived" and self.authority_status == "code_verified"
        ):
            raise ValueError(
                "only code-verified repository-derived formula packages may be accepted"
            )
        if self.authority_status == "code_verified" and not (
            self.bound_fact_ids or self.bound_equation_ids
        ):
            raise ValueError("code_verified formula packages must bind exact ids")
        # Compatibility normalization (Section 6.4): a historical package that
        # carries only ``obligation_id`` is normalized to a single-element
        # ``satisfied_obligation_ids``.  New packages return the closed-set ids
        # explicitly; ``obligation_id`` remains a single-element alias only.
        if not self.satisfied_obligation_ids and self.obligation_id.strip():
            object.__setattr__(
                self,
                "satisfied_obligation_ids",
                (self.obligation_id.strip(),),
            )
        object.__setattr__(
            self,
            "satisfied_obligation_ids",
            tuple(dict.fromkeys(
                str(item).strip()
                for item in self.satisfied_obligation_ids
                if str(item).strip()
            )),
        )
        if self.obligation_id.strip() and self.satisfied_obligation_ids and (
            self.obligation_id.strip() not in self.satisfied_obligation_ids
        ):
            raise ValueError(
                "formula package obligation_id is not in satisfied_obligation_ids"
            )
        if len(self.satisfied_obligation_ids) != 1 and self.obligation_id.strip():
            # The old alias is intentionally not carried on a multi-obligation
            # package.  Keeping it would make legacy consumers route only the
            # first obligation and silently lose the remaining closed ids.
            object.__setattr__(self, "obligation_id", "")
        elif len(self.satisfied_obligation_ids) == 1 and not self.obligation_id.strip():
            object.__setattr__(
                self, "obligation_id", self.satisfied_obligation_ids[0]
            )
        if self.semantic_formula_digest and self.semantic_formula_digest != _digest_json({
            "latex": self.latex.strip(),
            "symbol_definitions": self.symbol_definitions,
            "material_conditions": self.material_conditions,
            "assumptions": self.assumptions,
        }):
            raise ValueError("formula package semantic_formula_digest mismatch")
        object.__setattr__(
            self,
            "semantic_formula_digest",
            _digest_json({
                "latex": self.latex.strip(),
                "symbol_definitions": self.symbol_definitions,
                "material_conditions": self.material_conditions,
                "assumptions": self.assumptions,
            }),
        )
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
    disposition: Literal[
        "not_applicable",
        "insufficient_binding",
        "paper_code_mismatch",
        "formalizer_empty",
        "formalizer_not_invoked",
        "declined_empty",
    ]
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
    # ``outcome`` describes representation (a package was rendered or not),
    # while this field is the closed lifecycle state used by Binder and
    # acceptance.  In particular, an author-intent or partial package may be
    # rendered for review but can never be counted as an accepted code
    # formula.
    terminal_disposition: Literal[
        "accepted", "review_required", "not_applicable", "failed"
    ] = "failed"
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


_OPERATION_SIGNATURE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("attention", r"attention|attn"),
    ("mask", r"mask|masked|same[_ -]?document|\-infinity|\-inf|indicator"),
    ("position", r"position|sin(?:usoidal)?|cos(?:ine)?|positional"),
    ("normalize", r"normaliz|l2|functional\.normalize|norm"),
    ("concat", r"concat|concatenate|torch\.cat|\bcat\b|stack"),
    ("logsumexp", r"logsumexp|log\s*sum"),
    ("exp", r"\\exp\b|\bexp(?:onential)?\b"),
    ("reduce", r"\\sum\b|\bsum\b|reduce|mean|average"),
    ("rank", r"argsort|sort|ranking|rank|descending|top[_ -]?k"),
    ("threshold", r"threshold|compare|greater|less|select(?:s|ed)?|indicator"),
    ("ppr", r"pagerank|page[_ -]?rank|personalized[_ -]?pagerank|ppr"),
    ("multiply", r"\\cdot|\\times|\bmatmul\b|\bmm\b|\bdot\b|multiply|product|\*|@"),
    ("divide", r"\\frac|\bdivide\b|\bratio\b|\bquotient\b|/"),
    ("subtract", r"subtract|minus|negative|\-"),
    ("add", r"\badd(?:ed|ition)?\b|accumulat|residual|\+"),
)


def _operation_signature_families(value: Any) -> set[str]:
    """Extract conservative operation families from frozen source evidence."""

    if isinstance(value, Mapping):
        raw_payload = dict(value)
    elif hasattr(value, "model_dump"):
        raw_payload = value.model_dump(mode="json")
    else:
        raw_payload = {"value": str(value or "")}
    # Paths, span ids, and exact excerpts contain punctuation that is not an
    # operation signature (for example the slashes in ``src/model.py``).
    # Only retain the source operation vocabulary and execution conditions;
    # author statements are intentionally excluded from this authority check.
    atom_fields = (
        "predicate", "operands", "result", "operation_descriptors", "diagnostics",
        "guard", "iteration_context", "shape_or_type_hints", "description",
    )
    atoms = []
    for raw_atom in (
        *(raw_payload.get("operation_atoms") or ()),
        *(raw_payload.get("formalizable_signatures") or ()),
    ):
        if not isinstance(raw_atom, Mapping):
            continue
        atoms.append({key: raw_atom.get(key) for key in atom_fields if key in raw_atom})
    payload = {
        "operation_atoms": atoms,
        "preconditions": raw_payload.get("preconditions") or (),
        "shape_or_type_hints": raw_payload.get("shape_or_type_hints") or (),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    families = {
        family for family, pattern in _OPERATION_SIGNATURE_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    }
    # ``logsumexp`` is a fused source operation.  A paper expression that
    # expands the same implementation into exp/sum notation is still
    # operation-equivalent; requiring the source fact to contain the literal
    # expanded primitives would reject a faithful formalization.  The
    # implication is one-way and deliberately narrow: seeing exp or reduce
    # in source evidence does not authorize a fused logsumexp formula.
    if "logsumexp" in families:
        families.update({"exp", "reduce"})
    return families


def _formula_signature_families(package: SectionFormulaPackageV1) -> set[str]:
    """Extract operation families asserted by a paper formula package."""

    # The prose explanation may legitimately mention neighbouring operations
    # in the mechanism (for example position encoding while the displayed
    # expression is augmentation).  Signature authority belongs to the
    # displayed expression itself; otherwise explanatory context creates a
    # false operation-signature mismatch.
    text = package.latex
    return {
        family for family, pattern in _OPERATION_SIGNATURE_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    }


_OPERATION_BINDING_STOPWORDS = frozenset({
    "self", "the", "a", "an", "and", "or", "to", "of", "in", "on", "for",
    "with", "from", "this", "that", "is", "are", "be", "as", "by", "via",
    "input", "output", "value", "values", "data", "tensor", "item", "items",
    "element", "elements", "result", "operation",
})


def _operation_rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    """Return typed source operation rows from an evidence pack-like value."""

    if isinstance(value, Mapping):
        payload = value
    elif hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        payload = dumped if isinstance(dumped, Mapping) else {}
    else:
        payload = {}
    rows: list[Mapping[str, Any]] = []
    for raw in (
        *(payload.get("operation_atoms") or ()),
        *(payload.get("formalizable_signatures") or ()),
    ):
        if isinstance(raw, Mapping):
            rows.append(raw)
    return tuple(rows)


def _operation_binding_tokens(value: Any) -> set[str]:
    """Extract conservative semantic tokens for an operand/condition binding."""

    raw_tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?",
        str(value or ""),
    )
    tokens: set[str] = set()
    for token in raw_tokens:
        token = token.casefold()
        tokens.add(token)
        # Source operands are commonly snake_case implementation names while
        # paper symbols/meanings use ordinary words (for example
        # ``document_id_embeddings`` -> ``document``/``embeddings``).  Keep
        # the raw identifier for exact binding, and add only its lexical
        # components so a declared paper meaning can prove the mapping.
        for part in re.split(r"[_\-]+|(?<=[a-z])(?=[A-Z])", token):
            if part:
                tokens.add(part)
        for suffix in (
            "ization", "isation", "ation", "tion", "ment", "ing",
            "ers", "er", "ed", "es", "s",
        ):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                tokens.add(token[:-len(suffix)])
                break
    return {
        token for token in tokens
        if token not in _OPERATION_BINDING_STOPWORDS
    }


def _operation_binding_values(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if value is None or isinstance(value, Mapping):
        return ()
    try:
        return tuple(
            str(item).strip()
            for item in value
            if str(item).strip()
        )
    except TypeError:
        text = str(value).strip()
        return (text,) if text else ()


def _operation_binding_surface(package: SectionFormulaPackageV1) -> tuple[str, set[str], tuple[tuple[str, set[str]], ...]]:
    """Build the package surface used for source operand/guard matching.

    Academic symbols may differ from implementation names, so a source term
    can bind through a declared symbol meaning (for example ``q`` meaning
    ``query embedding``).  One-letter implementation operands still require
    an exact symbol/token match; this keeps the check conservative without
    forcing code identifiers into publication prose.
    """

    meanings: list[tuple[str, set[str]]] = []
    for symbol, meaning in package.symbol_definitions:
        meanings.append((str(symbol).strip().casefold(), _operation_binding_tokens(meaning)))
    for symbol in (package.symbol_table or ()):
        meanings.append((str(symbol.symbol).strip().casefold(), _operation_binding_tokens(symbol.meaning)))
    text = " ".join((
        package.latex,
        package.prose_explanation,
        *(str(symbol) for symbol, _meaning in package.symbol_definitions),
        *(str(meaning) for _symbol, meaning in package.symbol_definitions),
        *(str(item) for item in package.material_conditions),
        *(str(item) for item in package.assumptions),
    ))
    return text, _operation_binding_tokens(text), tuple(meanings)


def _operation_value_is_bound(
    value: str,
    *,
    surface_tokens: set[str],
    declared_meanings: tuple[tuple[str, set[str]], ...],
) -> bool:
    source_tokens = _operation_binding_tokens(value)
    if not source_tokens:
        return True
    # A one-character variable has no reliable semantic overlap signal; it
    # must be present as a declared/visible mathematical symbol.
    if len(source_tokens) == 1 and len(next(iter(source_tokens))) <= 2:
        return next(iter(source_tokens)) in surface_tokens or any(
            symbol == next(iter(source_tokens)) for symbol, _meaning in declared_meanings
        )
    if source_tokens.issubset(surface_tokens):
        return True
    # Qualified code names often become a compact academic symbol whose
    # meaning retains one or more substantive tokens (``query_embedding`` ->
    # ``q`` / ``query embedding``).  Require overlap with a declared meaning,
    # never with the symbol name alone.
    for _symbol, meaning_tokens in declared_meanings:
        if meaning_tokens and len(source_tokens.intersection(meaning_tokens)) >= 1:
            return True
    return False


def _operation_callable_is_rendered(value: str, latex: str) -> bool:
    """Accept a known source callable when its math operator is displayed.

    Operation-formula packages use reader-facing operators (for example
    ``\\operatorname{sort}``) instead of leaking ``torch.sort`` into the
    paper.  The callable itself is still part of the closed source atom; it
    is considered bound only through this exact terminal-name/operator alias
    mapping, never through a generic lexical overlap.
    """

    terminal = str(value or "").strip().rsplit(".", 1)[-1].casefold()
    if not terminal:
        return False
    aliases = {
        "cat": "concat",
        "concatenate": "concat",
        "argsort": "sort",
        "logsumexp": "logsumexp",
    }
    operator = aliases.get(terminal, terminal)
    return bool(re.search(
        r"\\operatorname\{" + re.escape(operator) + r"\}",
        str(latex or ""),
        flags=re.IGNORECASE,
    ))


def _operation_source_conditions(packs: tuple[Any, ...]) -> tuple[str, ...]:
    conditions: list[str] = []
    for pack in packs:
        conditions.extend(
            str(item).strip()
            for item in ((pack.get("preconditions", ()) if isinstance(pack, Mapping)
                          else getattr(pack, "preconditions", ())) or ())
            if str(item).strip()
        )
        for atom in _operation_rows(pack):
            conditions.extend(
                str(item).strip()
                for item in (
                    *_operation_binding_values(atom.get("conditions")),
                    *_operation_binding_values(atom.get("guard")),
                )
                if str(item).strip()
            )
    return tuple(dict.fromkeys(conditions))


def _operation_source_shapes(packs: tuple[Any, ...]) -> tuple[str, ...]:
    shapes: list[str] = []
    for pack in packs:
        shapes.extend(
            str(item).strip()
            for item in ((pack.get("shape_or_type_hints", ())
                          if isinstance(pack, Mapping)
                          else getattr(pack, "shape_or_type_hints", ())) or ())
            if str(item).strip()
        )
        for atom in _operation_rows(pack):
            shapes.extend(
                str(item).strip()
                for item in _operation_binding_values(
                    atom.get("shape_or_type_hints")
                    or atom.get("shape_hints")
                    or atom.get("types")
                )
                if str(item).strip()
            )
    return tuple(dict.fromkeys(shapes))


def _operation_explicit_families(atom: Mapping[str, Any]) -> set[str]:
    """Return arithmetic families explicitly recorded by one source atom.

    ``_operation_signature_families`` is intentionally broader because it is
    also used to validate a rendered formula.  Candidate construction needs a
    narrower signal: an implementation operand such as ``x + y`` may contain
    the operator, but a source descriptor (or an explicit diagnostic) is what
    gives the deterministic compiler permission to select the operation.
    """

    values = (
        *(atom.get("operation_descriptors") or ()),
        *(atom.get("diagnostics") or ()),
        atom.get("operation"),
        atom.get("operator"),
        atom.get("predicate"),
    )
    text = " ".join(str(value).strip().casefold() for value in values if str(value).strip())
    families: set[str] = set()
    if re.search(r"(?<![a-z0-9_])(?:add|added|addition|plus|accumulat)(?![a-z0-9_])", text):
        families.add("add")
    if re.search(r"(?<![a-z0-9_])(?:sub|subtract|subtraction|minus|negative)(?![a-z0-9_])", text):
        families.add("subtract")
    if re.search(r"(?<![a-z0-9_])(?:mult|multiply|multiplication|product)(?![a-z0-9_])", text):
        families.add("multiply")
    if re.search(r"(?<![a-z0-9_])(?:div|divide|division|quotient|ratio)(?![a-z0-9_])", text):
        families.add("divide")
    return families


def _operation_topic_groups(goal: str) -> tuple[frozenset[str], ...]:
    """Extract narrow mechanism signals used to avoid cross-stage binding."""

    text = str(goal or "").casefold()
    groups: list[frozenset[str]] = []
    if any(term in text for term in ("infonce", "contrastive", "contrastive loss", "loss")):
        groups.append(frozenset({
            "infonce", "contrastive", "loss", "loss_i", "pos_sim", "logsumexp",
            "negative", "positive", "similarity",
        }))
    if any(term in text for term in (
        "dot-product", "dot product", "rank", "ranking", "sort", "descending",
        "similarity", "relevance score",
    )):
        groups.append(frozenset({
            "dot", "similarity", "similarities", "rank", "ranking", "sort",
            "sorting", "descending", "score", "scores", "relevance",
        }))
    if any(term in text for term in (
        "augment", "document id embedding", "passage-position", "passage position",
    )):
        groups.append(frozenset({
            "augment", "document", "document_id", "passage", "passage_id",
            "embedding", "embeddings", "position", "positional",
        }))
    if any(term in text for term in ("positional encoding", "position encoding", "sinusoidal")):
        groups.append(frozenset({
            "position", "positions", "positional", "sinusoidal", "arange",
            "div_term", "sin", "cos",
        }))
    if any(term in text for term in ("attention", "masked attention", "attention mask")):
        groups.append(frozenset({"attention", "attn", "mask", "masked", "same_document"}))
    if any(term in text for term in ("pagerank", "page rank", "ppr", "propagation")):
        groups.append(frozenset({"pagerank", "page_rank", "ppr", "propagat"}))
    return tuple(groups)


def _render_operation_term(value: str) -> str:
    """Translate only known math calls; leave unknown implementation syntax out."""

    rendered = str(value or "").strip()
    replacements = (
        (r"\btorch\.logsumexp\s*\(", r"\\operatorname{logsumexp}("),
        (r"\btorch\.exp\s*\(", r"\\exp("),
        (r"\bmath\.log\s*\(", r"\\log("),
        (r"\btorch\.sum\s*\(", r"\\sum("),
        (r"\btorch\.mean\s*\(", r"\\operatorname{mean}("),
        (r"\btorch\.cat\s*\(", r"\\operatorname{concat}("),
    )
    for pattern, replacement in replacements:
        rendered = re.sub(pattern, replacement, rendered, flags=re.IGNORECASE)
    return rendered


def build_deterministic_operation_formula_packages(
    *,
    section_id: str,
    formula_obligations: tuple[MethodFormulaObligationV2, ...]
    | list[MethodFormulaObligationV2] = (),
    operation_evidence_packs: tuple[Any, ...] | list[Any] = (),
    package_namespace: str = "",
) -> tuple[SectionFormulaPackageV1, ...]:
    """Compile one conservative formula per closed operation obligation.

    This is a representation-only fallback for a ``code_ready`` Research
    dossier.  It admits only fact-backed ``computes_formula`` atoms with an
    exact span, an explicit arithmetic descriptor, operands, and a result.
    The obligation's mechanism words select the atom; no cross-scope call or
    semantic relation is inferred here.  A missing or ambiguous match returns
    no package so the normal typed failure path remains fail-closed.
    """

    obligations = tuple(formula_obligations or ())
    if not obligations:
        return ()

    def pack_value(pack: Any, name: str, default: Any = None) -> Any:
        if isinstance(pack, Mapping):
            return pack.get(name, default)
        return getattr(pack, name, default)

    candidates: dict[str, dict[str, Any]] = {}
    for pack in tuple(operation_evidence_packs or ()):
        if not bool(pack_value(pack, "connected", False)):
            continue
        readiness = str(pack_value(pack, "evidence_readiness", "code_ready") or "").strip()
        if readiness and readiness != "code_ready":
            continue
        if pack_value(pack, "unresolved_relations", ()):
            continue
        bound_fact_ids = {
            str(value).strip()
            for value in (pack_value(pack, "bound_fact_ids", ()) or ())
            if str(value).strip()
        }
        exact_span_ids = {
            str(value).strip()
            for value in (pack_value(pack, "exact_span_ids", ()) or ())
            if str(value).strip()
        }
        for raw_atom in _operation_rows(pack):
            atom = dict(raw_atom)
            predicate = str(
                atom.get("predicate") or atom.get("operation") or ""
            ).strip().casefold()
            operation_kind = ""
            if predicate in {"computes_formula", "computes", "compute", "formula"}:
                operation_kind = "arithmetic"
            elif predicate in {"sorts_by", "sort", "argsort"}:
                # A source-backed ranking signature is a valid formal
                # object even though it is not arithmetic.  Keep the
                # operation conservative: the displayed formula will retain
                # the exact result, score input, dimension, and direction.
                operation_kind = "sort"
            elif predicate in {"normalizes", "normalize"}:
                operation_kind = "normalize"
            elif predicate in {"reshapes", "reshape"}:
                operation_kind = "reshape"
            elif predicate in {"concatenates", "concatenate", "concat"}:
                operation_kind = "concat"
            if not operation_kind:
                continue
            fact_id = str(atom.get("fact_id") or "").strip()
            source_span_id = str(
                atom.get("source_span_id") or atom.get("span_id") or ""
            ).strip()
            operands = tuple(
                str(value).strip()
                for value in _operation_binding_values(atom.get("operands"))
                if str(value).strip()
            )
            result = str(
                atom.get("result") or atom.get("output") or atom.get("return_value") or ""
            ).strip()
            if not fact_id or fact_id not in bound_fact_ids:
                continue
            if not source_span_id or (exact_span_ids and source_span_id not in exact_span_ids):
                continue
            if not operands or not result:
                continue
            families = _operation_explicit_families(atom)
            if operation_kind != "arithmetic":
                families = {operation_kind}
            elif not families:
                source_families = _operation_signature_families({"operation_atoms": [atom]})
                families = source_families & {"add", "subtract", "multiply", "divide"}
            if len(families) != 1:
                continue
            atom_key = fact_id
            score_key = (
                len(atom.get("operation_descriptors") or ())
                + len(atom.get("conditions") or ())
                + len(atom.get("span_ids") or ())
            )
            previous = candidates.get(atom_key)
            if previous is None or score_key > int(previous.get("score_key", -1)):
                candidates[atom_key] = {
                    "atom": atom,
                    "pack": pack,
                    "family": next(iter(families)),
                    "operation_kind": operation_kind,
                    "score_key": score_key,
                }

    if not candidates:
        return ()

    packages: list[SectionFormulaPackageV1] = []
    used_fact_ids: set[str] = set()
    for obligation_index, obligation in enumerate(obligations, start=1):
        if obligation.expectation == "none":
            continue
        goal = " ".join(
            str(value).strip()
            for value in (
                getattr(obligation, "mathematical_goal", ""),
                getattr(obligation, "mechanism_key", ""),
            )
            if str(value).strip()
        )
        goal_tokens = _operation_binding_tokens(goal)
        topic_groups = _operation_topic_groups(goal)
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for fact_id, candidate in candidates.items():
            if fact_id in used_fact_ids:
                continue
            atom = candidate["atom"]
            atom_text = " ".join(
                str(atom.get(name) or "")
                for name in (
                    "predicate", "operands", "result", "operation_descriptors",
                    "diagnostics", "guard", "conditions",
                )
            )
            atom_tokens = _operation_binding_tokens(atom_text)
            if topic_groups and not any(group.intersection(atom_tokens) for group in topic_groups):
                continue
            overlap = len(goal_tokens.intersection(atom_tokens))
            if goal_tokens and overlap == 0:
                continue
            topic_bonus = sum(
                3 for group in topic_groups if group.intersection(atom_tokens)
            )
            scored.append((overlap + topic_bonus, fact_id, candidate))
        if not scored and not topic_groups:
            remaining = [
                (fact_id, candidate)
                for fact_id, candidate in candidates.items()
                if fact_id not in used_fact_ids
            ]
            if len(remaining) == 1:
                # A generic section obligation may carry no operation words.
                # A single code-ready atom in the already scoped consumer
                # dossier is still an unambiguous representation target;
                # multiple atoms remain unresolved rather than guessed.
                fact_id, candidate = remaining[0]
                scored.append((0, fact_id, candidate))
        if not scored:
            continue
        scored.sort(key=lambda item: (-item[0], item[1]))
        best_score = scored[0][0]
        best = [item for item in scored if item[0] == best_score]
        if len(best) > 1:
            # Different facts with the same score are not interchangeable
            # source authority.  Keep the obligation unresolved instead of
            # guessing which operation the author meant.
            continue
        _score, fact_id, candidate = best[0]
        atom = candidate["atom"]
        family = str(candidate["family"])
        rendered_operands = tuple(_render_operation_term(value) for value in (
            str(value).strip() for value in _operation_binding_values(atom.get("operands"))
        ))
        operation_kind = str(candidate.get("operation_kind") or "arithmetic")
        if operation_kind == "arithmetic" and any(
            re.search(r"\b(?:self|torch|numpy|np|tensorflow|tf|nn|math)\s*\.", value)
            for value in rendered_operands
        ):
            continue
        rendered_result = _render_operation_term(str(
            atom.get("result") or atom.get("output") or atom.get("return_value") or ""
        ).strip())
        if not rendered_result or not all(rendered_operands):
            continue
        if operation_kind == "arithmetic":
            operator = {
                "add": " + ",
                "subtract": " - ",
                "multiply": r" \cdot ",
                "divide": " / ",
            }[family]
            latex = rendered_result + " = " + operator.join(rendered_operands)
        else:
            function_names = {
                "sort": {"sort", "torch.sort", "argsort", "torch.argsort"},
                "normalize": {"normalize", "torch.nn.functional.normalize"},
                "reshape": {"reshape", "torch.reshape", "view"},
                "concat": {"concat", "concatenate", "torch.cat", "cat"},
            }
            args = tuple(
                value for value in rendered_operands
                if value.casefold() not in function_names.get(operation_kind, set())
            )
            if not args:
                continue
            operator_name = {
                "sort": "sort",
                "normalize": "normalize",
                "reshape": "reshape",
                "concat": "concat",
            }[operation_kind]
            latex = (
                rendered_result
                + r" = \operatorname{" + operator_name + "}("
                + ", ".join(args)
                + ")"
            )
        pack = candidate["pack"]
        conditions = tuple(dict.fromkeys(
            str(value).strip()
            for value in (
                *(pack_value(pack, "preconditions", ()) or ()),
                *(atom.get("conditions") or ()),
                atom.get("guard") or "",
            )
            if str(value).strip()
        ))
        consumer = str(
            getattr(obligation, "consumer_paragraph_id", "")
            or (
                obligation.paragraph_ids[0]
                if len(tuple(getattr(obligation, "paragraph_ids", ()) or ())) == 1
                else ""
            )
        ).strip()
        obligation_id = str(obligation.obligation_id).strip()
        package = SectionFormulaPackageV1(
            package_id=f"opfp:{section_id}:{package_namespace}{obligation_index}",
            section_id=section_id,
            obligation_id=obligation_id,
            consumer_paragraph_id=consumer,
            satisfied_obligation_ids=(obligation_id,),
            purpose=goal or "Formalize the authorized source operation.",
            latex=latex,
            prose_explanation=(
                "The repository operation computes the recorded result from the "
                "recorded operands using the authorized source operation."
            ),
            material_conditions=conditions,
            assumptions=(),
            authority_status="code_verified",
            formula_lane="repository_derived",
            bound_facet_ids=tuple(
                dict.fromkeys(
                    str(value).strip()
                    for value in (getattr(obligation, "facet_ids", ()) or ())
                    if str(value).strip()
                )
            ),
            bound_fact_ids=(fact_id,),
            bound_equation_ids=(),
        )
        packages.append(package)
        used_fact_ids.add(fact_id)
    return tuple(packages)


def _operation_condition_is_bound(
    condition: str,
    *,
    surface_text: str,
    surface_tokens: set[str],
) -> bool:
    normalized_surface = " ".join(surface_text.casefold().split())
    normalized_condition = " ".join(str(condition).casefold().split())
    if normalized_condition and normalized_condition in normalized_surface:
        return True
    condition_tokens = _operation_binding_tokens(condition)
    if not condition_tokens:
        return True
    numeric_tokens = {
        token for token in condition_tokens if token[0].isdigit()
    }
    if not numeric_tokens.issubset(surface_tokens):
        return False
    overlap = condition_tokens.intersection(surface_tokens)
    # Paraphrasing a condition is allowed, but not replacing it with a generic
    # sentence.  A third of the substantive predicate tokens is a deliberately
    # conservative floor; exact numeric thresholds remain mandatory.
    return len(overlap) >= max(1, (len(condition_tokens) + 2) // 3)


def _operation_evidence_failures(
    package: SectionFormulaPackageV1,
    *,
    operation_evidence_packs: tuple[Any, ...] | list[Any],
) -> list[str]:
    """Check a code-equivalent package against operation-level evidence.

    Equation ids are sufficient for the historical equation compiler.  When
    the compiler has only source operation chains, however, a package must be
    linked to a matching fact-backed pack and its claimed operator families
    must be present in that pack.  This keeps conventional notation separate
    from a code-equivalent authority upgrade.
    """

    if package.authority_status != "code_verified":
        return []
    if package.bound_equation_ids:
        # Equation-bound packages already pass the exact expression,
        # operand, operator, and condition checks below.  Operation-level
        # signature matching is the additional authority check only for the
        # equation-less path produced from a Research operation chain.
        return []
    packs = tuple(operation_evidence_packs or ())
    if not packs:
        # Preserve the pre-operation-pack contract for isolated callers that
        # validate a package directly against the frozen equation set.
        return []

    package_facts = set(str(item).strip() for item in package.bound_fact_ids if str(item).strip())
    package_equations = set(str(item).strip() for item in package.bound_equation_ids if str(item).strip())
    matching: list[Any] = []
    for pack in packs:
        pack_section = str(getattr(pack, "section_id", "") or "").strip()
        if pack_section and package.section_id != pack_section:
            continue
        pack_facts = set(str(item).strip() for item in (getattr(pack, "bound_fact_ids", ()) or ()) if str(item).strip())
        pack_equations = set(str(item).strip() for item in (getattr(pack, "bound_equation_ids", ()) or ()) if str(item).strip())
        if package_facts.intersection(pack_facts) or package_equations.intersection(pack_equations):
            matching.append(pack)
    if not matching:
        return ["operation_evidence_unbound"]
    scoped_matching: list[dict[str, Any]] = []
    for pack in matching:
        payload = (
            pack.model_dump(mode="json")
            if hasattr(pack, "model_dump")
            else dict(pack)
            if isinstance(pack, Mapping)
            else {}
        )
        if package_facts:
            # A dossier pack can carry the whole paragraph chain.  A formula
            # package is allowed to bind only the fact atoms it names; using
            # every neighbouring atom here made unrelated reshape/call
            # operands look like missing formula operands.
            rows = [
                row for row in _operation_rows(payload)
                if str(row.get("fact_id") or "").strip() in package_facts
            ]
            if rows:
                payload["operation_atoms"] = rows
                payload["formalizable_signatures"] = rows
        scoped_matching.append(payload)
    failures: list[str] = []
    if any(getattr(pack, "unresolved_relations", ()) for pack in matching):
        failures.append("operation_evidence_unresolved")
    if any(
        str(getattr(pack, "default_activation", "unknown") or "unknown") == "inactive"
        for pack in matching
    ):
        failures.append("operation_evidence_inactive")
    source_families = set().union(*(
        _operation_signature_families(pack) for pack in scoped_matching
    ))
    formula_families = _formula_signature_families(package)
    if not formula_families and not source_families:
        failures.append("operation_signature_not_detected")
    unsupported = sorted(formula_families - source_families)
    if unsupported:
        failures.append("operation_signature_mismatch:" + ",".join(unsupported))
    surface_text, surface_tokens, declared_meanings = _operation_binding_surface(package)
    relevant_packs: list[dict[str, Any]] = []
    for pack in scoped_matching:
        rows = list(_operation_rows(pack))
        if formula_families and rows:
            scored = [
                (
                    len(
                        formula_families.intersection(
                            _operation_signature_families({"operation_atoms": [row]})
                        )
                    ),
                    row,
                )
                for row in rows
            ]
            best_score = max((score for score, _row in scored), default=0)
            if best_score:
                rows = [row for score, row in scored if score == best_score]
        # A package with no recognizable displayed operator still has to bind
        # the sole source atom (the guarded-normalization case); with several
        # atoms the operand/result checks remain conservative and use all
        # rows because no deterministic family can select a subset.
        selected = dict(pack)
        selected["operation_atoms"] = rows
        selected["formalizable_signatures"] = rows
        if rows:
            selected["shape_or_type_hints"] = tuple(dict.fromkeys(
                str(item).strip()
                for row in rows
                for item in _operation_binding_values(
                    row.get("shape_or_type_hints")
                    or row.get("shape_hints")
                    or row.get("types")
                )
                if str(item).strip()
            ))
        relevant_packs.append(selected)
    missing_values: list[str] = []
    for pack in relevant_packs:
        for atom in _operation_rows(pack):
            for field in ("operands", "result", "output", "return_value"):
                values = _operation_binding_values(atom.get(field))
                for value in values:
                    # Free-form fact descriptions are already checked by the
                    # operation-family guard; identifier-shaped values are
                    # where an operation-equivalent formula can silently swap
                    # an input or output.
                    if (
                        re.fullmatch(
                            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
                            value,
                        )
                        and not _operation_value_is_bound(
                            value,
                            surface_tokens=surface_tokens,
                            declared_meanings=declared_meanings,
                        )
                        and not _operation_callable_is_rendered(
                            value,
                            package.latex,
                        )
                    ):
                        missing_values.append(value)
    if missing_values:
        failures.append(
            "operation_operand_binding_missing:"
            + ",".join(list(dict.fromkeys(missing_values))[:8])
        )
    missing_conditions = [
        condition for condition in _operation_source_conditions(tuple(relevant_packs))
        if not _operation_condition_is_bound(
            condition,
            surface_text=surface_text,
            surface_tokens=surface_tokens,
        )
    ]
    if missing_conditions:
        failures.append(
            "operation_condition_missing:"
            + ",".join(list(dict.fromkeys(missing_conditions))[:4])
        )
    missing_shapes = [
        shape for shape in _operation_source_shapes(tuple(relevant_packs))
        if not _operation_condition_is_bound(
            shape,
            surface_text=surface_text,
            surface_tokens=surface_tokens,
        )
    ]
    if missing_shapes:
        failures.append(
            "operation_shape_or_type_missing:"
            + ",".join(list(dict.fromkeys(missing_shapes))[:4])
        )
    return failures


def build_mechanism_equation_evidence_packs(
    *,
    section_id: str,
    equations: Any,
    facts: Any,
    allowed_equation_ids: set[str] | None = None,
    author_statements: tuple[str, ...] = (),
    dossiers: tuple[Any, ...] | list[Any] = (),
) -> tuple[MechanismEquationEvidencePackV1, ...]:
    """Build bounded evidence packs for mechanism-level equations.

    The pack keeps source operation atoms separate from publication formulas.
    A lone generic binary operation is deliberately omitted; a connected
    multi-operation chain or a relation-backed mechanism is eligible for
    Formalizer review.
    """

    from code2paper.agentic.research_derived_authoring import (
        compile_code_fact_operation_chain,
    )

    facts_by_id = {
        str(item.fact_id): item
        for item in (facts.facts if facts is not None else ())
    }
    dossier_values = tuple(dossiers or ())

    def dossier_value(item: Any, name: str, default: Any = None) -> Any:
        if isinstance(item, Mapping):
            return item.get(name, default)
        return getattr(item, name, default)

    def unique_dicts(values: Any) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values or ():
            if isinstance(value, Mapping):
                row = dict(value)
            elif hasattr(value, "model_dump"):
                dumped = value.model_dump(mode="json")
                row = dumped if isinstance(dumped, dict) else {}
            else:
                continue
            key = _digest_json(row)
            if key not in seen:
                seen.add(key)
                result.append(row)
        return tuple(result)

    packs: list[MechanismEquationEvidencePackV1] = []
    covered_dossier_ids: set[str] = set()
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
        compiled_facts = compile_code_fact_operation_chain(
            facts=selected_facts,
        )
        compiled_by_fact_id = {
            str(atom.get("fact_id")): dict(atom)
            for atom in compiled_facts["operation_atoms"]
            if str(atom.get("fact_id") or "").strip()
        }
        span_ids: list[str] = []
        conditions: list[str] = []
        shape_hints: list[str] = []
        relation_ids = set(getattr(equation, "relation_evidence_ids", ()) or ())
        for fact in selected_facts:
            compiled_atom = compiled_by_fact_id.get(str(fact.fact_id))
            if compiled_atom is not None:
                atoms.append(compiled_atom)
                relation_ids.update(compiled_atom.get("relation_evidence_ids") or ())
                conditions.extend(compiled_atom.get("conditions") or ())
                span_ids.extend(compiled_atom.get("span_ids") or ())
                shape_hints.extend(compiled_atom.get("shape_or_type_hints") or ())
                continue
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
        equation_id = str(getattr(equation, "equation_id", ""))
        equation_fact_ids = set(
            str(item) for item in (getattr(equation, "fact_ids", ()) or ())
        )
        matching_dossiers = tuple(
            dossier
            for dossier in dossier_values
            if str(dossier_value(dossier, "section_id", "")) == section_id
            and (
                equation_id in set(
                    str(item)
                    for item in (dossier_value(dossier, "equation_ids", ()) or ())
                )
                or equation_fact_ids.intersection(set(
                    str(item)
                    for item in (dossier_value(dossier, "fact_ids", ()) or ())
                ))
            )
        )
        dossier_ids = tuple(dict.fromkeys(
            str(dossier_value(item, "dossier_id", ""))
            for item in matching_dossiers
            if str(dossier_value(item, "dossier_id", "")).strip()
        ))
        dossier_atoms = [
            atom
            for dossier in matching_dossiers
            for atom in (dossier_value(dossier, "operation_atoms", ()) or ())
        ]
        dossier_signatures = [
            signature
            for dossier in matching_dossiers
            for signature in (
                dossier_value(dossier, "formalizable_signatures", ()) or ()
            )
            if isinstance(signature, Mapping)
        ]
        all_atoms: list[dict[str, Any]] = []
        atom_keys: set[str] = set()
        for atom in (*atoms, *dossier_atoms):
            if not isinstance(atom, Mapping):
                continue
            row = dict(atom)
            key = str(row.get("atom_id") or row.get("node_id") or _digest_json(row))
            if key in atom_keys:
                continue
            atom_keys.add(key)
            all_atoms.append(row)
        dossier_span_ids = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "exact_span_ids", ()) or ())
            if str(item).strip()
        ]
        dossier_conditions = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "active_path_conditions", ()) or ())
            if str(item).strip()
        ]
        dossier_shape_hints = [
            str(item).strip()
            for dossier in matching_dossiers
            for item in (
                dossier_value(dossier, "shape_or_type_hints", ()) or ()
            )
            if str(item).strip()
        ]
        dossier_author_statements = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "author_statements", ()) or ())
            if str(item).strip()
        ]
        dossier_unresolved = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "unresolved_relations", ()) or ())
            if str(item).strip()
        ]
        dossier_node_ids = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "ordered_operation_node_ids", ()) or ())
            if str(item).strip()
        ]
        dossier_call_ids = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "call_path_relation_ids", ()) or ())
            if str(item).strip()
        ]
        dossier_data_ids = [
            str(item)
            for dossier in matching_dossiers
            for item in (dossier_value(dossier, "data_flow_relation_ids", ()) or ())
            if str(item).strip()
        ]
        dossier_configs = unique_dicts(
            config
            for dossier in matching_dossiers
            for config in (dossier_value(dossier, "configuration_bindings", ()) or ())
        )
        signature_rows: list[dict[str, Any]] = []
        signature_keys: set[str] = set()
        for signature in dossier_signatures:
            key = _digest_json(signature)
            if key not in signature_keys:
                signature_keys.add(key)
                signature_rows.append(dict(signature))
        if not signature_rows:
            for atom in all_atoms:
                if not isinstance(atom, Mapping):
                    continue
                predicate = str(
                    atom.get("predicate") or atom.get("operation")
                    or atom.get("operation_id") or ""
                ).strip()
                operands = tuple(
                    str(item).strip()
                    for item in (atom.get("operands") or ())
                    if str(item).strip()
                )
                result = str(
                    atom.get("result") or atom.get("output")
                    or atom.get("return_value") or ""
                ).strip()
                if not (predicate or operands or result):
                    continue
                row = {
                    "predicate": predicate,
                    "operands": list(dict.fromkeys(operands)),
                    "result": result,
                    "guard": str(atom.get("guard") or "").strip(),
                    "shape_or_type_hints": list(dict.fromkeys(
                        str(item).strip()
                        for item in (atom.get("shape_or_type_hints") or ())
                        if str(item).strip()
                    )),
                    "source_span_id": str(
                        atom.get("source_span_id") or atom.get("span_id") or ""
                    ).strip(),
                }
                key = _digest_json(row)
                if key not in signature_keys:
                    signature_keys.add(key)
                    signature_rows.append(row)
        activation_values = tuple(dict.fromkeys(
            str(dossier_value(dossier, "default_activation", "unknown"))
            for dossier in matching_dossiers
            if str(dossier_value(dossier, "default_activation", "unknown")).strip()
        ))
        default_activation = (
            activation_values[0]
            if len(activation_values) == 1
            and activation_values[0] in {"active", "inactive", "conditional", "unknown"}
            else "conditional"
            if dossier_conditions
            else "unknown"
        )
        pack_identity = {
            "section_id": section_id,
            "equation_id": equation_id,
            "fact_ids": list(getattr(equation, "fact_ids", ()) or ()),
            "span_ids": list(dict.fromkeys((*span_ids, *dossier_span_ids))),
            "dossier_ids": dossier_ids,
        }
        packs.append(MechanismEquationEvidencePackV1(
            pack_id="eqpack:" + _digest_json(pack_identity)[7:23],
            section_id=section_id,
            dossier_ids=dossier_ids,
            ordered_operation_node_ids=tuple(dict.fromkeys(dossier_node_ids)),
            call_path_relation_ids=tuple(dict.fromkeys(dossier_call_ids)),
            data_flow_relation_ids=tuple(dict.fromkeys(dossier_data_ids)),
            configuration_bindings=dossier_configs,
            default_activation=default_activation,
            unresolved_relations=tuple(dict.fromkeys(dossier_unresolved)),
            operation_atoms=tuple(all_atoms),
            formalizable_signatures=tuple(signature_rows),
            exact_span_ids=tuple(dict.fromkeys((*span_ids, *dossier_span_ids))),
            exact_excerpts=tuple(dict.fromkeys(
                str(item).strip()
                for dossier in matching_dossiers
                for item in (dossier_value(dossier, "exact_excerpts", ()) or ())
                if str(item).strip()
            )),
            preconditions=tuple(dict.fromkeys((*conditions, *dossier_conditions))),
            shape_or_type_hints=tuple(dict.fromkeys((*shape_hints, *dossier_shape_hints))),
            author_statements=tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in (*author_statements, *dossier_author_statements)
                    if str(item).strip()
                )
            ),
            bound_fact_ids=tuple(
                str(item) for item in (getattr(equation, "fact_ids", ()) or ())
                if str(item) in facts_by_id
            ),
            bound_equation_ids=(equation_id,),
            connected=True,
        ))
        covered_dossier_ids.update(dossier_ids)

    # The equation compiler can legitimately reject incidental ``x + y`` /
    # ``x * y`` wrappers even when the Research dossier contains a connected,
    # fact-backed operation chain.  Preserve that chain as a separate
    # operation evidence pack so the Formalizer can derive an equivalent
    # paper expression without promoting the incidental equation itself.
    for dossier in dossier_values:
        dossier_section = str(dossier_value(dossier, "section_id", "") or "").strip()
        dossier_id = str(dossier_value(dossier, "dossier_id", "") or "").strip()
        if dossier_section != section_id or not dossier_id or dossier_id in covered_dossier_ids:
            continue
        # Author-intent and blocked dossiers may carry operation-looking
        # descriptions, but they are not repository authority.  Only an
        # explicitly code-ready dossier can enter the operation formula lane;
        # legacy callers without a readiness field retain the structural
        # checks below for compatibility.
        dossier_readiness = str(
            dossier_value(dossier, "evidence_readiness", "") or ""
        ).strip()
        if dossier_readiness and dossier_readiness != "code_ready":
            continue
        raw_atoms = [
            dict(atom)
            for atom in (dossier_value(dossier, "operation_atoms", ()) or ())
            if isinstance(atom, Mapping)
        ]
        if not raw_atoms:
            continue
        # A dossier may reference helper functions in several scopes.  Keep
        # those as independent packs unless a relation-backed pack was
        # already produced; never turn a shared symbol name into an invented
        # call/data-flow edge.
        chain_groups: dict[str, list[dict[str, Any]]] = {}
        for atom in raw_atoms:
            chain_scope = str(
                atom.get("chain_scope") or atom.get("scope")
                or atom.get("symbol_id") or "scope:unknown"
            ).strip()
            chain_groups.setdefault(chain_scope, []).append(atom)
        raw_dossier_fact_ids = tuple(dict.fromkeys(
            str(item).strip()
            for item in (dossier_value(dossier, "fact_ids", ()) or ())
            if str(item).strip() and str(item).strip() in facts_by_id
        ))
        dossier_spans = tuple(dict.fromkeys(
            str(item).strip()
            for item in (dossier_value(dossier, "exact_span_ids", ()) or ())
            if str(item).strip()
        ))
        dossier_signatures = tuple(
            dict(signature)
            for signature in (dossier_value(dossier, "formalizable_signatures", ()) or ())
            if isinstance(signature, Mapping)
        )
        activation = str(
            dossier_value(dossier, "default_activation", "unknown") or "unknown"
        ).strip()
        if activation not in {"active", "inactive", "conditional", "unknown"}:
            activation = "unknown"
        for chain_index, (chain_scope, chain_atoms) in enumerate(
            sorted(chain_groups.items()), start=1
        ):
            atom_rows: list[dict[str, Any]] = []
            seen_atoms: set[str] = set()
            chain_fact_ids: list[str] = []
            span_ids: list[str] = []
            relation_ids: list[str] = []
            for atom in chain_atoms:
                atom_spans = atom.get("span_ids") or ()
                if isinstance(atom_spans, str):
                    atom_spans = (atom_spans,)
                span_ids.extend(
                    str(item).strip() for item in atom_spans if str(item).strip()
                )
                source_span = str(
                    atom.get("source_span_id") or atom.get("span_id") or ""
                ).strip()
                if source_span:
                    span_ids.append(source_span)
                atom_fact_id = str(atom.get("fact_id") or "").strip()
                if atom_fact_id and atom_fact_id in facts_by_id:
                    chain_fact_ids.append(atom_fact_id)
                relation_ids.extend(
                    str(item).strip()
                    for item in (atom.get("relation_evidence_ids") or ())
                    if str(item).strip()
                )
                atom_key = str(
                    atom.get("atom_id") or atom.get("node_id")
                    or atom.get("operation_id") or _digest_json(atom)
                ).strip()
                if atom_key in seen_atoms:
                    continue
                seen_atoms.add(atom_key)
                atom_rows.append(atom)
            chain_fact_ids = list(dict.fromkeys(chain_fact_ids))
            if not chain_fact_ids and len(chain_groups) == 1:
                chain_fact_ids = list(raw_dossier_fact_ids)
            if not span_ids:
                span_ids.extend(dossier_spans)
            span_ids = list(dict.fromkeys(item for item in span_ids if item))
            if not chain_fact_ids or not span_ids or not atom_rows:
                continue
            chain_fact_set = set(chain_fact_ids)
            chain_span_set = set(span_ids)
            signature_rows = [
                dict(signature) for signature in dossier_signatures
                if (
                    not signature.get("fact_id")
                    or str(signature.get("fact_id")) in chain_fact_set
                    or str(signature.get("source_span_id") or "") in chain_span_set
                    or str(signature.get("scope") or "") == chain_scope
                )
            ]
            if not signature_rows:
                for atom in atom_rows:
                    predicate = str(
                        atom.get("predicate") or atom.get("operation")
                        or atom.get("operation_id") or ""
                    ).strip()
                    operands = tuple(
                        str(item).strip()
                        for item in (atom.get("operands") or ())
                        if str(item).strip()
                    )
                    result = str(
                        atom.get("result") or atom.get("output")
                        or atom.get("return_value") or ""
                    ).strip()
                    if predicate or operands or result:
                        signature_rows.append({
                            "predicate": predicate,
                            "operands": list(dict.fromkeys(operands)),
                            "result": result,
                            "guard": str(atom.get("guard") or "").strip(),
                            "shape_or_type_hints": list(dict.fromkeys(
                                str(item).strip()
                                for item in (atom.get("shape_or_type_hints") or ())
                                if str(item).strip()
                            )),
                            "source_span_id": str(
                                atom.get("source_span_id") or atom.get("span_id") or ""
                            ).strip(),
                        })
            pack_identity = {
                "section_id": section_id,
                "dossier_id": dossier_id,
                "chain_scope": chain_scope,
                "chain_index": chain_index,
                "fact_ids": chain_fact_ids,
                "span_ids": span_ids,
                "atoms": atom_rows,
            }
            packs.append(MechanismEquationEvidencePackV1(
                pack_id="opack:" + _digest_json(pack_identity)[7:23],
                section_id=section_id,
                dossier_ids=(dossier_id,),
                ordered_operation_node_ids=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "ordered_operation_node_ids", ()) or ())
                    if str(item).strip()
                )),
                call_path_relation_ids=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "call_path_relation_ids", ()) or ())
                    if str(item).strip()
                )),
                data_flow_relation_ids=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "data_flow_relation_ids", ()) or ())
                    if str(item).strip()
                )),
                configuration_bindings=unique_dicts(
                    dossier_value(dossier, "configuration_bindings", ()) or ()
                ),
                default_activation=activation,
                unresolved_relations=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "unresolved_relations", ()) or ())
                    if str(item).strip()
                )),
                operation_atoms=tuple(atom_rows),
                formalizable_signatures=tuple(signature_rows),
                exact_span_ids=tuple(span_ids),
                shape_or_type_hints=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "shape_or_type_hints", ()) or ())
                    if str(item).strip()
                )),
                exact_excerpts=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "exact_excerpts", ()) or ())
                    if str(item).strip()
                )),
                preconditions=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "active_path_conditions", ()) or ())
                    if str(item).strip()
                )),
                author_statements=tuple(dict.fromkeys(
                    str(item).strip()
                    for item in (dossier_value(dossier, "author_statements", ()) or ())
                    if str(item).strip()
                )),
                bound_fact_ids=tuple(chain_fact_ids),
                connected=bool(
                    len(atom_rows) > 1
                    or relation_ids
                    or any(
                        str(atom.get("predicate") or "").casefold()
                        not in {"add", "sub", "mult", "div", "computes_formula"}
                        for atom in atom_rows
                    )
                    or any(
                        atom.get("result")
                        or atom.get("operation_descriptors")
                        for atom in atom_rows
                    )
                ),
            ))
    return tuple(packs)


def validate_section_formula_package(
    package: SectionFormulaPackageV1,
    *,
    equations: Any,
    facts: Any,
    allowed_facet_ids: set[str] | None = None,
    allowed_equation_ids: set[str] | None = None,
    formula_obligations: tuple[Any, ...] | list[Any] = (),
    require_consumer: bool = False,
    operation_evidence_packs: tuple[Any, ...] | list[Any] = (),
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
    canonical_block = canonical_formula_markdown_block(package.latex)
    if package.markdown_block.strip() != canonical_block.strip():
        failures.append("markdown_block_not_canonical_display")
    if package.markdown_block.strip() and package.latex.strip() not in package.markdown_block:
        failures.append("markdown_block_missing_exact_latex")
    failures.extend(_formula_code_trace_failures(package))
    failures.extend(_operation_evidence_failures(
        package,
        operation_evidence_packs=operation_evidence_packs,
    ))
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
    if allowed_equation_ids is not None:
        failures.extend(
            f"equation_not_in_current_core:{equation_id}"
            for equation_id in sorted(
                set(package.bound_equation_ids) - set(allowed_equation_ids)
            )
        )
    if require_consumer:
        obligations = tuple(formula_obligations or ())
        obligation_by_id = {
            str(getattr(item, "obligation_id", "") or "").strip(): item
            for item in obligations
            if str(getattr(item, "obligation_id", "") or "").strip()
        }
        package_consumer_id = str(package.consumer_paragraph_id or "").strip()
        satisfied_ids = tuple(
            str(item).strip() for item in package.satisfied_obligation_ids
            if str(item).strip()
        )
        if not satisfied_ids:
            failures.append("formula_package_obligation_id_missing")
        # Every satisfied obligation must be in the section's closed set and
        # resolve to the same single consumer paragraph (Section 6.4).  A
        # package that names obligations spanning several paragraphs is
        # rejected as a whole; it can never close a paragraph transaction.
        resolved_consumers: set[str] = set()
        for obligation_id in satisfied_ids:
            obligation = obligation_by_id.get(obligation_id)
            if obligation is None:
                failures.append(f"formula_package_obligation_route_mismatch:{obligation_id}")
                continue
            obligation_section = str(
                getattr(obligation, "section_id", "") or ""
            ).strip()
            if obligation_section and package.section_id != obligation_section:
                failures.append(f"formula_package_section_mismatch:{obligation_id}")
            expected_consumer = str(
                getattr(obligation, "consumer_paragraph_id", "")
                or (
                    obligation.paragraph_ids[0]
                    if len(tuple(getattr(obligation, "paragraph_ids", ()) or ())) == 1
                    else ""
                )
            ).strip()
            if not expected_consumer:
                failures.append(f"formula_package_without_paragraph_consumer:{obligation_id}")
            else:
                resolved_consumers.add(expected_consumer)
            package_facets = set(package.bound_facet_ids)
            obligation_facets = set(getattr(obligation, "facet_ids", ()) or ())
            if obligation_facets and package_facets and not obligation_facets.intersection(package_facets):
                failures.append(f"formula_package_facet_binding_mismatch:{obligation_id}")
        if len(resolved_consumers) > 1:
            failures.append("formula_package_consumer_paragraph_mismatch")
        elif not package_consumer_id and resolved_consumers:
            failures.append("formula_package_consumer_id_missing")
        elif (
            package_consumer_id
            and resolved_consumers
            and package_consumer_id not in resolved_consumers
        ):
            failures.append("formula_package_consumer_paragraph_mismatch")
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
    r"\uparrow", r"\downarrow", r"\Uparrow", r"\Downarrow", r"\updownarrow",
    r"\xrightarrow", r"\xleftarrow", r"\longrightarrow", r"\longleftarrow",
    r"\nearrow", r"\searrow", r"\swarrow", r"\nwarrow",
    r"\Longrightarrow", r"\Longleftarrow", r"\longleftrightarrow", r"\Longleftrightarrow",
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
    ("python_keyword_arg", re.compile(
        r"\b(?:dim|descending|keepdim|axis|dtype|device)\s*=",
        flags=re.IGNORECASE,
    )),
    ("python_tuple_assignment", re.compile(
        r"\([^()\n]{1,80}\)\s*=",
    )),
    ("raw_snake_case_identifier", re.compile(
        r"\b[a-z]+(?:_[a-z0-9]+){2,}\b",
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
            # Guided decoding occasionally emits the requested repository
            # lane together with an explicit author-intent (or partial)
            # authority.  That is a representation conflict, not evidence
            # that the package is code licensed.  Normalize the lane toward
            # the less-authoritative declaration so the package can enter
            # the typed review_required terminal state instead of being
            # discarded by Pydantic before the Formalizer guard sees it.
            # Never perform the inverse upgrade: intent/partial content must
            # not become repository-derived merely because the model copied
            # the prompt's lane label.
            authority_status = str(row.get("authority_status") or "").strip()
            formula_lane = str(row.get("formula_lane") or "").strip()
            if (
                authority_status == "author_intent"
                and formula_lane == "repository_derived"
            ):
                row["formula_lane"] = "author_intent_academic"
            elif (
                authority_status in {"partial", "paper_code_mismatch"}
                and formula_lane == "repository_derived"
            ):
                row["formula_lane"] = "hybrid_partial"
            elif (
                authority_status == "code_verified"
                and formula_lane in {"author_intent_academic", "hybrid_partial"}
            ):
                row["authority_status"] = (
                    "author_intent"
                    if formula_lane == "author_intent_academic"
                    else "partial"
                )
            # For every package lane, markdown_block is representation-only
            # display math.  Extra headings, Symbol Definitions, and prose
            # memos stay in Writer-facing sidecar fields.
            if str(row.get("latex") or "").strip():
                latex = normalize_formula_latex_body(str(row["latex"]))
                row["latex"] = latex
                row["markdown_block"] = canonical_formula_markdown_block(latex)
            normalized.append(row)
        data["packages"] = normalized
    elif str(data.get("outcome") or "") == "unresolved" and not str(
        data.get("review_question") or ""
    ).strip():
        data["review_question"] = (
            "Which repository evidence would upgrade this formula?"
        )
    return data


def _normalize_non_code_formula_package(
    package: SectionFormulaPackageV1,
) -> SectionFormulaPackageV1:
    """Canonicalize representation-only residue on review-lane packages."""

    normalized_latex = normalize_formula_latex_body(package.latex)
    if (
        str(package.authority_status or "") == "code_verified"
        or not package.latex.strip()
        or (
            package.markdown_block.strip()
            and package.latex.strip() in package.markdown_block
            and normalized_latex == package.latex
        )
    ):
        return package
    payload = package.model_dump(mode="json", exclude={"content_digest"})
    payload["latex"] = normalized_latex
    payload["markdown_block"] = canonical_formula_markdown_block(normalized_latex)
    try:
        return SectionFormulaPackageV1.model_validate(payload)
    except (TypeError, ValueError):
        # The normal validator remains authoritative if the package contains
        # a deeper content/schema error; do not manufacture a fallback object.
        return package


def coerce_section_formalizer_response(
    payload: Any,
    *,
    section_id: str,
) -> SectionFormalizerResponseV1 | None:
    """Parse guided-decoding payloads, including legacy package batches."""

    if isinstance(payload, SectionFormalizerResponseV1):
        packages = tuple(
            _normalize_non_code_formula_package(item)
            for item in payload.packages
        )
        if packages != payload.packages:
            try:
                payload = payload.model_copy(update={"packages": packages})
            except (TypeError, ValueError):
                pass
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
            packages=tuple(
                _normalize_non_code_formula_package(item)
                for item in payload.packages
            ),
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
                package_satisfied = set(
                    str(item).strip()
                    for item in (
                        package.satisfied_obligation_ids
                        or ((package.obligation_id,) if package.obligation_id else ())
                    )
                    if str(item).strip()
                )
                if not package_satisfied.intersection(target_obligations):
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
                formula_obligations=tuple(section_result.formula_obligations),
                require_consumer=bool(section_result.formula_obligations),
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
    package_namespace: str = "",
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

    def _package_obligations(group: list[Any]) -> tuple[MethodFormulaObligationV2, ...]:
        if not obligations:
            return ()
        equation_ids = {
            str(getattr(item, "equation_id", "") or "").strip()
            for item in group
            if str(getattr(item, "equation_id", "") or "").strip()
        }
        equation_keys = set().union(*(_formula_identity(item) for item in equation_ids)) if equation_ids else set()
        matches: list[MethodFormulaObligationV2] = []
        for obligation in obligations:
            obligation_keys = _formula_identity(obligation.obligation_id)
            if equation_keys.intersection(obligation_keys):
                matches.append(obligation)
        if not matches:
            group_key = str(mechanism_for_group := next(
                (
                    str(item).strip().casefold()
                    for item in (
                        getattr(group[0], "operation_descriptors", ()) or ()
                    )
                    if str(item).strip().casefold() in _CORE_EQUATION_DESCRIPTORS
                ),
                "",
            ))
            def _norm(value: Any) -> str:
                return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
            keyed = [
                obligation for obligation in obligations
                if str(getattr(obligation, "mechanism_key", "") or "").strip()
                and _norm(getattr(obligation, "mechanism_key", ""))
                in {_norm(group_key), _norm(mechanism)}
            ]
            if keyed:
                matches = keyed
        # A single mechanism group can safely satisfy every obligation that
        # explicitly names the same mechanism and consumer.  Different
        # consumers must remain separate and are never guessed together.
        if matches:
            consumers = {
                str(
                    getattr(item, "consumer_paragraph_id", "")
                    or (
                        item.paragraph_ids[0]
                        if len(tuple(getattr(item, "paragraph_ids", ()) or ())) == 1
                        else ""
                    )
                ).strip()
                for item in matches
            }
            keys = {
                str(getattr(item, "mechanism_key", "") or "").strip()
                for item in matches
                if str(getattr(item, "mechanism_key", "") or "").strip()
            }
            if len(consumers) <= 1 and (len(matches) == 1 or len(keys) == 1):
                return tuple(matches)
        if len(obligations) == 1 and len(groups) == 1:
            return (obligations[0],)
        return ()

    packages: list[SectionFormulaPackageV1] = []
    for index, (mechanism, group) in enumerate(
        sorted(groups.items(), key=lambda item: item[0]), start=1
    ):
        primary = group[0]
        package_obligations = _package_obligations(group)
        consumer = ""
        obligation_id = ""
        satisfied_obligation_ids: tuple[str, ...] = ()
        bound_facets: tuple[str, ...] = ()
        if package_obligations:
            satisfied_obligation_ids = tuple(
                str(item.obligation_id) for item in package_obligations
            )
            if len(satisfied_obligation_ids) == 1:
                obligation_id = satisfied_obligation_ids[0]
            obligation = package_obligations[0]
            consumer = str(
                obligation.consumer_paragraph_id
                or (obligation.paragraph_ids[0] if len(obligation.paragraph_ids) == 1 else "")
            ).strip()
            bound_facets = tuple(dict.fromkeys(
                facet_id
                for item in package_obligations
                for facet_id in item.facet_ids
            ))
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
            package_id=f"fp:{section_id}:{package_namespace}{index}",
            section_id=section_id,
            obligation_id=obligation_id,
            consumer_paragraph_id=consumer,
            satisfied_obligation_ids=satisfied_obligation_ids,
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
        for obligation_id in (
            package.satisfied_obligation_ids
            or ((package.obligation_id,) if str(package.obligation_id or "").strip() else ())
        ):
            if str(obligation_id or "").strip():
                package_by_obligation[str(obligation_id)] = package
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
            if not expected_consumer:
                package = None
            elif package_consumer != expected_consumer:
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
        synthetic_not_applicable = str(obligation_id).strip() == (
            f"formula:section:{section_id}:none"
        )
        expectation = (
            "none"
            if synthetic_not_applicable
            else obligation.expectation
            if obligation is not None
            else "required"
        )
        if package is not None and package in packages:
            terminal_disposition = (
                "accepted"
                if (
                    str(package.review_status or "") == "accepted"
                    and package.formula_lane == "repository_derived"
                    and package.authority_status == "code_verified"
                )
                else "review_required"
            )
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="rendered",
                terminal_disposition=terminal_disposition,
                package_id=package.package_id,
                review_question=(
                    package.review_question
                    if terminal_disposition == "review_required"
                    else ""
                ),
                reason=(
                    "formula package is not code-accepted"
                    if terminal_disposition == "review_required"
                    else ""
                ),
                expectation=expectation,
                blocking=(
                    expectation == "required"
                    and terminal_disposition != "accepted"
                ),
            ))
            continue
        if expectation == "none":
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="not_applicable",
                terminal_disposition="not_applicable",
                reason="formula expectation is none",
                expectation=expectation,
            ))
            continue
        if disposition is not None:
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="unresolved",
                terminal_disposition="failed",
                review_question=disposition.review_question,
                reason=disposition.review_note,
                expectation=expectation,
                blocking=expectation == "required",
            ))
        else:
            truths.append(SectionFormulaObligationTruthV1(
                obligation_id=obligation_id,
                outcome="unresolved",
                terminal_disposition="failed",
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
    empty_disposition: str = "formalizer_empty",
) -> FormalizationSectionResultV1:
    """Wrap accepted packages into a section result (empty packages never
    silently count as completion).

    Section 6.4 route isolation: a package that fails its obligation/consumer
    route is rejected on its own; the other packages in the same section are
    kept.  New packages carry explicit ``satisfied_obligation_ids`` (one
    canonical consumer paragraph, possibly several obligations); historical
    packages are bound only when their route is uniquely resolvable.
    """

    obligation_by_id = {
        str(item.obligation_id): item
        for item in formula_obligations
        if str(item.obligation_id).strip()
    }
    normalized_packages: list[SectionFormulaPackageV1] = []
    route_failures: list[str] = []
    claimed_obligations: set[str] = set()
    claimed_consumers: dict[str, str] = {}

    def _expected_consumer(obligation: Any) -> str:
        return str(
            getattr(obligation, "consumer_paragraph_id", "")
            or (
                obligation.paragraph_ids[0]
                if len(tuple(getattr(obligation, "paragraph_ids", ()) or ())) == 1
                else ""
            )
        ).strip()

    for package in packages:
        package_consumer_id = str(package.consumer_paragraph_id or "").strip()
        satisfied_ids = tuple(
            str(item).strip() for item in package.satisfied_obligation_ids
            if str(item).strip()
        )
        if satisfied_ids:
            # Explicit closed-set route (new responses).  Every satisfied id
            # must be a planned obligation in this section and must resolve to
            # one consumer paragraph.
            resolved_consumers: set[str] = set()
            package_ok = True
            for obligation_id in satisfied_ids:
                obligation = obligation_by_id.get(obligation_id)
                if obligation is None:
                    route_failures.append(
                        f"unknown_obligation:{package.package_id}:{obligation_id}"
                    )
                    package_ok = False
                    continue
                expected_consumer = _expected_consumer(obligation)
                if expected_consumer:
                    resolved_consumers.add(expected_consumer)
                elif getattr(obligation, "paragraph_ids", ()):
                    route_failures.append(f"consumer_not_unique:{obligation_id}")
                    package_ok = False
                elif package_consumer_id:
                    route_failures.append(f"consumer_not_planned:{obligation_id}")
                    package_ok = False
                else:
                    route_failures.append(f"consumer_not_planned:{obligation_id}")
                    package_ok = False
            if len(resolved_consumers) > 1:
                route_failures.append(f"consumer_mismatch:{package.package_id}")
                package_ok = False
            elif resolved_consumers and package_consumer_id and package_consumer_id not in resolved_consumers:
                route_failures.append(f"consumer_mismatch:{package.package_id}")
                package_ok = False
            duplicate = [oid for oid in satisfied_ids if oid in claimed_obligations]
            if duplicate:
                route_failures.append(f"duplicate_obligation_consumers:{package.package_id}")
                package_ok = False
            if not package_ok:
                continue
            for obligation_id in satisfied_ids:
                claimed_obligations.add(obligation_id)
            if resolved_consumers and not package_consumer_id:
                package = package.model_copy(update={
                    "consumer_paragraph_id": next(iter(resolved_consumers)),
                    "obligation_id": satisfied_ids[0],
                })
            for obligation_id in satisfied_ids:
                claimed_consumers[obligation_id] = package.package_id
            normalized_packages.append(package)
            continue

        # Legacy single-obligation route: only ``obligation_id`` is present.
        package_obligation_id = str(package.obligation_id or "").strip()
        if package_obligation_id:
            obligation = obligation_by_id.get(package_obligation_id)
            if obligation is None:
                route_failures.append(
                    f"unknown_obligation:{package.package_id}:{package_obligation_id}"
                )
                continue
            expected_consumer = _expected_consumer(obligation)
            if expected_consumer and package_consumer_id and package_consumer_id != expected_consumer:
                route_failures.append(f"consumer_mismatch:{package_obligation_id}")
                continue
            if not expected_consumer:
                if getattr(obligation, "paragraph_ids", ()):
                    route_failures.append(f"consumer_not_unique:{package_obligation_id}")
                else:
                    route_failures.append(f"consumer_not_planned:{package_obligation_id}")
                continue
            if package_obligation_id in claimed_obligations:
                route_failures.append(f"duplicate_obligation_consumers:{package.package_id}")
                continue
            claimed_obligations.add(package_obligation_id)
            claimed_consumers[package_obligation_id] = package.package_id
            package = package.model_copy(update={
                "satisfied_obligation_ids": (package_obligation_id,),
                "consumer_paragraph_id": expected_consumer,
            })
            normalized_packages.append(package)
            continue

        # No explicit ids: bind only when the facet/equation overlap is
        # unique; otherwise reject this package alone (never a whole-section
        # flush).
        # Historical callers may provide only ``obligation_ids`` and an
        # equation-bound package, without materialized obligation objects.
        # Preserve that representation-only compatibility path; once the
        # closed obligation objects exist, the strict branch above owns route
        # resolution and ambiguity remains fail-closed.
        if not formula_obligations:
            normalized_packages.append(package)
            continue
        matches = [
            obligation
            for obligation in formula_obligations
            if (
                (set(package.bound_facet_ids) & set(getattr(obligation, "facet_ids", ()) or ()))
                or str(obligation.obligation_id) in set(package.bound_equation_ids)
            )
        ]
        if len(matches) == 1:
            obligation = matches[0]
            consumer = _expected_consumer(obligation)
            if not consumer:
                if getattr(obligation, "paragraph_ids", ()):
                    route_failures.append(f"consumer_not_unique:{obligation.obligation_id}")
                else:
                    route_failures.append(f"consumer_not_planned:{obligation.obligation_id}")
                continue
            if str(obligation.obligation_id) in claimed_obligations:
                route_failures.append(f"duplicate_obligation_consumers:{package.package_id}")
                continue
            claimed_obligations.add(str(obligation.obligation_id))
            claimed_consumers[str(obligation.obligation_id)] = package.package_id
            package = package.model_copy(update={
                "obligation_id": str(obligation.obligation_id),
                "satisfied_obligation_ids": (str(obligation.obligation_id),),
                "consumer_paragraph_id": consumer,
            })
            normalized_packages.append(package)
        elif formula_obligations:
            route_failures.append(f"ambiguous_obligation:{package.package_id}")
    packages = tuple(normalized_packages)

    # Once the current typed obligation set exists, the graph-level ids are
    # aliases from the pre-consumer plan.  Keeping those aliases here creates
    # a second unresolved target after an alias was already merged into its
    # canonical consumer obligation.  Legacy plans without typed obligations
    # still retain their original ids below.
    effective_obligation_ids = tuple(dict.fromkeys(
        [
            *(
                item.obligation_id
                for item in formula_obligations
                if str(getattr(item, "obligation_id", "") or "").strip()
            ),
        ]
        if formula_obligations
        else [*obligation_ids]
    ))
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
            disposition=empty_disposition,
            review_question=(
                "The section has a required formula consumer but the Formalizer "
                "was never invoked; route it through a real consumer before it can complete."
                if empty_disposition == "formalizer_not_invoked"
                else "Which core mechanism formula should this section present, and which repository evidence binds it?"
            ),
            review_note=(
                "Formula package route failed: " + "; ".join(dict.fromkeys(route_failures))
                if route_failures
                else (
                    "The section has a required formula obligation and consumer, but no "
                    "Formalizer call or deterministic package was produced."
                    if empty_disposition == "formalizer_not_invoked"
                    else "Core equation evidence exists but the Formalizer produced no accepted package."
                )
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
            blocking_for_candidate=empty_disposition == "formalizer_not_invoked",
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
        and truth.terminal_disposition != "accepted"
    )
    preferred_formula_review_ids = tuple(
        truth.obligation_id
        for truth in obligation_truths
        if truth.expectation == "preferred"
        and truth.terminal_disposition != "accepted"
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
    "build_deterministic_operation_formula_packages",
    "canonical_formula_markdown_block",
    "normalize_formula_latex_body",
    "build_mechanism_equation_evidence_packs",
    "build_formula_obligation_truths",
    "coerce_section_formalizer_response",
    "facet_mechanism_key",
    "formalize_code_facts",
    "load_formalization_section_results",
    "resolve_formalization_route_artifact",
    "section_result_from_packages",
    "select_core_equations",
    "validate_formalization_proposal",
    "validate_section_formalizer_response",
    "validate_section_formula_package",
]
