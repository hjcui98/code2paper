"""Formalization Agent contracts and deterministic validation helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
from code2paper.agentic.method_argument_models import ProofObligationV1


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


__all__ = [
    "FormalizationAgent",
    "FormalizationProposalItemV1",
    "FormalizationProposalV1",
    "FormalizationResultV1",
    "FormalizationRiskV1",
    "SymbolDefinitionV1",
    "formalize_code_facts",
    "validate_formalization_proposal",
]
