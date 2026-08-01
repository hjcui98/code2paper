"""Formalization Agent contracts and deterministic validation helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

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
    "FormalizationResultV1",
    "FormalizationRiskV1",
    "SymbolDefinitionV1",
    "formalize_code_facts",
]
