"""Formalization Agent guards: mutation rejection, bounded owner retry, upgrade denial."""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.equation_claims import EquationClaimSetV1, EquationClaimV1, EquationSymbolBindingV1
from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
from code2paper.agentic.formalization_agent import (
    FormalizationProposalItemV1,
    FormalizationProposalV1,
    formalize_code_facts,
    validate_formalization_proposal,
)
from code2paper.llm.client import LLMResponse


def _facts() -> CodeFactSetV1:
    return CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:score",
            subject="compute_knn_score",
            predicate="computes_formula",
            object="feature_scores",
            scope="sym:compute_knn_score",
            direct_span_ids=["span:model.py:1:2"],
            semantic_context=["SCORE"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:score",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )


def _equations() -> EquationClaimSetV1:
    equation = EquationClaimV1(
        equation_id="equation:score",
        expression="s = w @ x + b",
        fact_ids=["fact:score"],
        symbol_bindings=[
            EquationSymbolBindingV1(symbol="s", operand_role="result", operand_value="score", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="w", operand_role="object", operand_value="weights", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="x", operand_role="object", operand_value="features", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="b", operand_role="object", operand_value="bias", fact_id="fact:score"),
        ],
        canonical_identity="sha256:equation:score",
        validation_status="supported",
    )
    return EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[equation],
        content_digest="sha256:equations",
    )


def _proposal(*items) -> FormalizationProposalV1:
    return FormalizationProposalV1(
        proposal_id="proposal:test",
        items=tuple(items),
    )


def _item(kind: str, statement: str, equation_ids=("equation:score",), fact_ids=("fact:score",)):
    return FormalizationProposalItemV1(
        kind=kind,
        statement=statement,
        fact_ids=tuple(fact_ids),
        equation_ids=tuple(equation_ids),
    )


def test_formalization_proposal_preserving_operands_and_operators_passes() -> None:
    proposal = _proposal(_item(
        "derivation_step",
        "The score is computed as the sum of the product of weights and features plus bias.",
    ))

    failures = validate_formalization_proposal(proposal, facts=_facts(), equations=_equations())

    assert failures == []


def test_formalization_proposal_mutating_operator_is_rejected() -> None:
    proposal = _proposal(_item(
        "derivation_step",
        "The score is computed as the product of weights, features, and bias.",
    ))

    failures = validate_formalization_proposal(proposal, facts=_facts(), equations=_equations())

    assert any("operator_mutation" in failure for failure in failures)


def test_formalization_proposal_mutating_value_constant_is_rejected() -> None:
    proposal = _proposal(_item(
        "validation_conclusion",
        "The score uses exactly 32 features and adds a bias of 0.5.",
    ))

    failures = validate_formalization_proposal(proposal, facts=_facts(), equations=_equations())

    assert any("operand_or_value_mutation" in failure for failure in failures)


def test_formalization_proposal_theoretical_upgrade_is_rejected_with_and_without_assumptions() -> None:
    proposal = _proposal(_item(
        "validation_conclusion",
        "The score converges to the true nearest-neighbor ranking.",
    ))

    failures = validate_formalization_proposal(proposal, facts=_facts(), equations=_equations())
    assert any("unsupported_theoretical_upgrade" in failure for failure in failures)

    with_assumptions = validate_formalization_proposal(
        proposal,
        facts=_facts(),
        equations=_equations(),
        assumptions=("explicit convergence assumption",),
    )
    assert any("unsupported_theoretical_upgrade" in failure for failure in with_assumptions)


def test_formalization_proposal_unknown_ids_are_rejected() -> None:
    proposal = _proposal(FormalizationProposalItemV1(
        kind="pseudocode",
        statement="A loop reads each feature row.",
        fact_ids=("fact:invented",),
        equation_ids=("equation:invented",),
    ))

    failures = validate_formalization_proposal(proposal, facts=_facts(), equations=_equations())

    assert any("unknown_fact_ids" in failure for failure in failures)
    assert any("unknown_equation_ids" in failure for failure in failures)


def test_formalization_base_is_stable_with_proposal_items() -> None:
    base = formalize_code_facts(facts=_facts(), equations=_equations())
    assert base.symbols
    assert base.proof_obligations
    assert base.proposal_items == ()
    assert base.content_digest.startswith("sha256:")
