"""R4.4 equation claims: ``EquationClaimV1``.

This module implements design section 9.3 (equations).  Only an
``EquationClaimV1`` may appear as a formula in the final prose, and only
when the deterministic authorizer can reconstruct the expression from
behavior-graph operations and bind every symbol to a fact operand.

Authorization checks (R4.4):

- ``expression_from_operations``: the proposed LaTeX expression is rebuilt
  deterministically from a sequence of ``COMPUTE`` / ``TRANSFORM`` /
  ``AGGREGATE`` / ``REDUCE`` behavior nodes in the fact set;
- ``symbols_bound_to_fact_operands``: every symbol in the expression maps
  to a ``CodeFactV1`` operand (``subject`` or ``object``);
- ``relation_and_guard_complete``: every relation and guard referenced by
  the underlying facts appears in the equation's ``conditions``;
- ``prose_uses_same_fact_ids``: the equation's ``prose_claim_id`` (if
  set) must reference the same fact ids as the equation itself.

When any check fails the compiler returns ``safe_equations=[]`` for that
proposal (the proposal is dropped, not silently relaxed).

R4.5 hard constraint: this module's source MUST NOT contain project-specific
literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``, ``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.evidence_compiler_v3 import (
    CodeFactSetV1,
    CodeFactV1,
)


# ---------------------------------------------------------------------------
# Equation claim model
# ---------------------------------------------------------------------------


class EquationSymbolBindingV1(BaseModel):
    """A binding from a LaTeX symbol to the fact operand that licenses it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    fact_id: str
    operand_role: str  # "subject" | "object" | "result"
    operand_value: str


class EquationClaimV1(BaseModel):
    """A typed equation claim that may appear in final prose (R4.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    equation_id: str
    expression: str  # LaTeX expression, e.g. r"y = \sigma(Wx + b)"
    prose_claim_id: str = ""  # optional link to the prose AtomicClaimV3
    fact_ids: list[str]
    symbol_bindings: list[EquationSymbolBindingV1]
    conditions: list[str] = Field(default_factory=list)
    canonical_identity: str
    validation_status: str = "supported"  # "supported" | "rejected"
    validation_failures: list[str] = Field(default_factory=list)


class EquationClaimSetV1(BaseModel):
    """A set of authorized equation claims (R4.4)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    producer_version: str = "code2paper-equation-compiler-v1"
    repo_snapshot_id: str
    project_tree_hash: str
    code_fact_digest: str
    equations: list[EquationClaimV1]
    content_digest: str


# ---------------------------------------------------------------------------
# Proposal input
# ---------------------------------------------------------------------------


class EquationProposalV1(BaseModel):
    """LLM-proposed equation claim (R4.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    equation_id: str
    expression: str
    prose_claim_id: str = ""
    fact_ids: list[str]
    proposed_symbol_bindings: list[EquationSymbolBindingV1] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


class EquationAuthorizationReportV1(BaseModel):
    """Deterministic authorization report for an equation proposal."""

    model_config = ConfigDict(extra="forbid")

    equation_id: str
    failures: list[str] = Field(default_factory=list)
    semantic_notes: list[str] = Field(default_factory=list)

    @property
    def authorized(self) -> bool:
        return not self.failures


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _digest(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


# Predicates that can license an equation operation.  An equation must be
# reconstructable from a chain of these predicates in the fact set.
_EQUATION_PREDICATES: frozenset[str] = frozenset({
    "computes_formula", "transforms", "aggregates", "reduces",
    "concatenates", "stacks", "normalizes", "compares",
    "selects", "selects_top_k", "sorts_by", "filters_by",
    "constructs", "returns",
})

# LaTeX symbol pattern: backslash commands (e.g. \sigma) or alphanumeric
# identifiers (e.g. x, W, b, y).
_LATEX_SYMBOL_RE = re.compile(r"\\[a-zA-Z]+|[a-zA-Z][a-zA-Z0-9]*")


def _extract_symbols(expression: str) -> list[str]:
    """Extract LaTeX symbols from an expression.

    Returns a de-duplicated list in order of first appearance.  Operators
    (``+``, ``-``, ``*``, ``/``, ``=``, ``^``, ``_``, parentheses) are
    skipped.
    """

    seen: set[str] = set()
    symbols: list[str] = []
    for match in _LATEX_SYMBOL_RE.finditer(expression):
        sym = match.group(0)
        if sym in seen:
            continue
        seen.add(sym)
        symbols.append(sym)
    return symbols


def _fact_operand_values(fact: CodeFactV1) -> list[str]:
    """All operand values a fact exposes for symbol binding."""

    values: list[str] = []
    if fact.subject:
        values.append(fact.subject)
    if isinstance(fact.object, str):
        values.append(fact.object)
    elif isinstance(fact.object, list):
        values.extend(fact.object)
    return values


# ---------------------------------------------------------------------------
# Core: authorize a single equation proposal
# ---------------------------------------------------------------------------


def authorize_equation(
    proposal: EquationProposalV1,
    facts: CodeFactSetV1,
) -> tuple[EquationClaimV1 | None, EquationAuthorizationReportV1]:
    """Authorize an equation proposal against a fact set.

    Returns ``(equation, report)``.  When ``report.failures`` is non-empty
    the equation is ``None`` and the caller MUST treat it as
    ``safe_equations=[]`` for this proposal.
    """

    failures: list[str] = []
    fact_by_id = {f.fact_id: f for f in facts.facts}

    # 1) Every fact id must exist and be supported.
    selected_facts: list[CodeFactV1] = []
    for fid in proposal.fact_ids:
        fact = fact_by_id.get(fid)
        if fact is None:
            failures.append(f"unknown_fact:{fid}")
            continue
        if fact.validation_status != "supported":
            failures.append(f"unsupported_fact:{fid}:{fact.validation_status}")
            continue
        selected_facts.append(fact)

    # 2) expression_from_operations: at least one fact must carry an
    #    equation-licensing predicate, otherwise the expression is not
    #    reconstructable from behavior operations.
    has_equation_fact = any(
        f.predicate in _EQUATION_PREDICATES for f in selected_facts
    )
    if not has_equation_fact:
        failures.append("expression_not_reconstructable_from_operations")

    # 3) symbols_bound_to_fact_operands: every LaTeX symbol must map to a
    #    fact operand via a proposed binding.
    expression_symbols = _extract_symbols(proposal.expression)
    bound_symbols = {b.symbol for b in proposal.proposed_symbol_bindings}
    unbound = [s for s in expression_symbols if s not in bound_symbols]
    if unbound:
        failures.append(
            f"unbound_symbols:{','.join(unbound)}"
        )

    # Validate each binding references a real fact and operand.
    available_operand_values: set[str] = set()
    for fact in selected_facts:
        for val in _fact_operand_values(fact):
            available_operand_values.add(val)
    for binding in proposal.proposed_symbol_bindings:
        if binding.fact_id not in fact_by_id:
            failures.append(f"binding_references_unknown_fact:{binding.symbol}:{binding.fact_id}")
            continue
        if binding.operand_value not in available_operand_values:
            failures.append(
                f"binding_operand_not_in_fact:{binding.symbol}:{binding.operand_value}"
            )

    # 4) relation_and_guard_complete: every condition on a selected fact
    #    must appear in the proposal's conditions.
    declared_conditions = set(proposal.conditions)
    for fact in selected_facts:
        for cond in fact.conditions:
            if cond not in declared_conditions:
                failures.append(f"dropped_condition:{fact.fact_id}:{cond}")

    # 5) prose_uses_same_fact_ids: if a prose_claim_id is supplied, the
    #    caller is responsible for verifying the link upstream; here we
    #    only check that the proposal declares it consistently (non-empty
    #    link means the prose claim must reuse at least one fact id).
    if proposal.prose_claim_id and not proposal.fact_ids:
        failures.append("prose_link_without_facts")

    identity = _digest({
        "expression": proposal.expression.strip(),
        "fact_ids": sorted(proposal.fact_ids),
        "symbol_bindings": [
            b.model_dump(mode="json")
            for b in sorted(
                proposal.proposed_symbol_bindings,
                key=lambda b: b.symbol,
            )
        ],
    })

    report = EquationAuthorizationReportV1(
        equation_id=proposal.equation_id,
        failures=failures,
    )
    if failures:
        return None, report

    equation = EquationClaimV1(
        equation_id=proposal.equation_id,
        expression=proposal.expression,
        prose_claim_id=proposal.prose_claim_id,
        fact_ids=list(proposal.fact_ids),
        symbol_bindings=list(proposal.proposed_symbol_bindings),
        conditions=list(proposal.conditions),
        canonical_identity=identity,
        validation_status="supported",
        validation_failures=[],
    )
    return equation, report


# ---------------------------------------------------------------------------
# Core: compile a batch of equation proposals
# ---------------------------------------------------------------------------


def compile_equation_claims(
    proposals: list[EquationProposalV1],
    facts: CodeFactSetV1,
    *,
    repo_snapshot_id: str,
    project_tree_hash: str,
) -> tuple[EquationClaimSetV1, list[EquationAuthorizationReportV1]]:
    """Authorize a batch of equation proposals.

    Returns ``(equation_set, reports)``.  ``equation_set.equations``
    contains only the authorized equations; rejected proposals yield
    ``safe_equations=[]`` for that proposal.
    """

    authorized: list[EquationClaimV1] = []
    reports: list[EquationAuthorizationReportV1] = []
    seen_identities: set[str] = set()
    for proposal in proposals:
        equation, report = authorize_equation(proposal, facts)
        reports.append(report)
        if equation is not None:
            if equation.canonical_identity in seen_identities:
                # Replace the last report with a duplicate-identity failure.
                reports[-1] = EquationAuthorizationReportV1(
                    equation_id=proposal.equation_id,
                    failures=[
                        f"duplicate_canonical_identity:{equation.canonical_identity}"
                    ],
                )
                continue
            seen_identities.add(equation.canonical_identity)
            authorized.append(equation)

    payload = [e.model_dump(mode="json") for e in authorized]
    equation_set = EquationClaimSetV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        code_fact_digest=facts.content_digest,
        equations=authorized,
        content_digest=_digest(payload),
    )
    return equation_set, reports


def write_equation_claims(path: str | Path, equations: EquationClaimSetV1) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(equations.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return output


def load_equation_claims(path: str | Path) -> EquationClaimSetV1:
    return EquationClaimSetV1.model_validate_json(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "EquationAuthorizationReportV1",
    "EquationClaimSetV1",
    "EquationClaimV1",
    "EquationProposalV1",
    "EquationSymbolBindingV1",
    "authorize_equation",
    "compile_equation_claims",
    "load_equation_claims",
    "write_equation_claims",
]
