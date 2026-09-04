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


# ---------------------------------------------------------------------------
# Q2 — section-scoped formula packages (plan 19.6)
# ---------------------------------------------------------------------------


def _guarded_facts() -> CodeFactSetV1:
    return CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:score",
                subject="compute_knn_score",
                predicate="computes_formula",
                object="feature_scores",
                scope="sym:compute_knn_score",
                direct_span_ids=["span:model.py:1:2"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:score",
                validation_status="supported",
            ),
            CodeFactV1(
                fact_id="fact:guard",
                subject="reduce_loss",
                predicate="branches_on",
                object=["loss_i.shape[0]", "==", "0"],
                scope="sym:reduce_loss",
                direct_span_ids=["span:model.py:3:4"],
                conditions=("loss_i.shape[0] == 0",),
                exact_source_digest="sha256:src2",
                canonical_identity="sha256:fact:guard",
                validation_status="supported",
            ),
        ],
        content_digest="sha256:facts2",
    )


def _guarded_equations() -> EquationClaimSetV1:
    core = EquationClaimV1(
        equation_id="equation:score",
        expression="s = w @ x + b",
        fact_ids=["fact:score"],
        operation_descriptors=["inference score"],
        symbol_bindings=[
            EquationSymbolBindingV1(symbol="s", operand_role="result", operand_value="score", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="w", operand_role="object", operand_value="weights", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="x", operand_role="object", operand_value="features", fact_id="fact:score"),
            EquationSymbolBindingV1(symbol="b", operand_role="object", operand_value="bias", fact_id="fact:score"),
        ],
        canonical_identity="sha256:equation:score",
        validation_status="supported",
    )
    defensive = EquationClaimV1(
        equation_id="equation:defensive",
        expression="r = \\begin{cases} 0 & \\text{if } \\text{len}(l)=0 \\end{cases}",
        fact_ids=["fact:guard"],
        operation_descriptors=["empty check"],
        symbol_bindings=[
            EquationSymbolBindingV1(symbol="r", operand_role="result", operand_value="reduction", fact_id="fact:guard"),
        ],
        canonical_identity="sha256:equation:defensive",
        validation_status="supported",
    )
    return EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts2",
        equations=[core, defensive],
        content_digest="sha256:equations2",
    )


def test_core_equation_selection_is_section_scoped_and_audit_filtered() -> None:
    from code2paper.agentic.formalization_agent import select_core_equations

    equations = _guarded_equations()
    facts = _guarded_facts()
    core = select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:score", "equation:defensive"},
    )
    assert [item.equation_id for item in core] == ["equation:score"]
    # A foreign section equation is never selected.
    foreign = select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:elsewhere"},
    )
    assert foreign == []


def test_deterministic_packages_carry_latex_symbols_and_explanation() -> None:
    from code2paper.agentic.formalization_agent import (
        build_deterministic_formula_packages,
        validate_section_formula_package,
    )

    packages = build_deterministic_formula_packages(
        section_id="MA-S1",
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        allowed_equation_ids={"equation:score"},
    )
    assert len(packages) == 1
    pkg = packages[0]
    assert pkg.latex == "s = w @ x + b"
    assert pkg.symbol_definitions
    assert pkg.prose_explanation.strip()
    assert pkg.authority_status == "code_verified"
    assert pkg.bound_equation_ids == ("equation:score",)
    assert validate_section_formula_package(
        pkg, equations=_guarded_equations(), facts=_guarded_facts()
    ) == []


def test_operation_evidence_pack_can_authorize_only_matching_signature() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        build_mechanism_equation_evidence_packs,
        validate_section_formula_package,
    )

    packs = build_mechanism_equation_evidence_packs(
        section_id="MA-S1",
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        allowed_equation_ids=set(),
        dossiers=[{
            "dossier_id": "dossier:operation",
            "section_id": "MA-S1",
            "fact_ids": ["fact:score"],
            "exact_span_ids": ["span:model.py:1:2"],
            "operation_atoms": [{
                "node_id": "node:add",
                "predicate": "COMPUTE",
                "operands": ["w", "x"],
                "result": "s",
                "diagnostics": ["add"],
                "source_span_id": "span:model.py:1:2",
            }],
            "unresolved_relations": [],
        }],
    )
    assert len(packs) == 1
    assert packs[0].pack_id.startswith("opack:")
    assert packs[0].bound_equation_ids == ()
    assert packs[0].operation_atoms[0]["operands"] == ["w", "x"]

    package = SectionFormulaPackageV1(
        package_id="package:operation",
        section_id="MA-S1",
        purpose="State the source addition.",
        latex="s = w + x",
        prose_explanation="The operation adds the two inputs.",
        authority_status="code_verified",
        bound_fact_ids=("fact:score",),
    )
    assert validate_section_formula_package(
        package,
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        operation_evidence_packs=packs,
    ) == []

    unsupported = package.model_copy(update={"latex": "s = w / x"})
    failures = validate_section_formula_package(
        unsupported,
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        operation_evidence_packs=packs,
    )
    assert any("operation_signature_mismatch" in failure for failure in failures)

    swapped_operands = package.model_copy(update={"latex": "s = u + v"})
    failures = validate_section_formula_package(
        swapped_operands,
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        operation_evidence_packs=packs,
    )
    assert any("operation_operand_binding_missing" in failure for failure in failures)


def test_operation_evidence_requires_bound_conditions_and_shapes() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        build_mechanism_equation_evidence_packs,
        validate_section_formula_package,
    )

    packs = build_mechanism_equation_evidence_packs(
        section_id="MA-S1",
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        allowed_equation_ids=set(),
        dossiers=[{
            "dossier_id": "dossier:guarded-operation",
            "section_id": "MA-S1",
            "fact_ids": ["fact:score"],
            "exact_span_ids": ["span:model.py:1:2"],
            "operation_atoms": [{
                "operation_id": "normalize",
                "predicate": "NORMALIZE",
                "operands": ["x"],
                "result": "z",
                "guard": "x.shape[0] > 0",
                "shape_or_type_hints": ["x: [N, d]"],
                "source_span_id": "span:model.py:1:2",
            }],
            "unresolved_relations": [],
            "default_activation": "active",
        }],
    )
    package = SectionFormulaPackageV1(
        package_id="package:guarded-operation",
        section_id="MA-S1",
        purpose="State the guarded normalization.",
        latex="z = x",
        prose_explanation="The operation normalizes x when the leading dimension is nonempty.",
        material_conditions=("x.shape[0] > 0", "x: [N, d]"),
        authority_status="code_verified",
        bound_fact_ids=("fact:score",),
    )
    assert validate_section_formula_package(
        package,
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        operation_evidence_packs=packs,
    ) == []

    missing_guard = package.model_copy(update={
        "prose_explanation": "The operation normalizes x.",
        "material_conditions": (),
    })
    failures = validate_section_formula_package(
        missing_guard,
        equations=_guarded_equations(),
        facts=_guarded_facts(),
        operation_evidence_packs=packs,
    )
    assert any("operation_condition_missing" in failure for failure in failures)


def test_formula_package_rejects_added_dimensions_and_undefined_symbols() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Score.",
        latex="s = w @ x + b + 42 \\unknownmacro",
        prose_explanation="The score adds the constant forty-two.",
        symbol_definitions=(
            ("s", "score"), ("w", "weights"), ("x", "features"), ("b", "bias"),
        ),
        authority_status="code_verified",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
    )
    failures = validate_section_formula_package(
        pkg, equations=_guarded_equations(), facts=_guarded_facts()
    )
    assert any("added_numbers" in failure for failure in failures)
    assert any("undefined_symbols" in failure for failure in failures)


def test_section_result_without_packages_gets_typed_disposition_not_silent_success() -> None:
    from code2paper.agentic.formalization_agent import section_result_from_packages

    result = section_result_from_packages(section_id="MA-S1", packages=())
    assert result.packages == ()
    assert result.disposition is not None
    assert result.disposition.disposition == "formalizer_empty"
    assert result.disposition.review_question
    assert result.disposition.blocking_for_candidate is False


def test_generic_arithmetic_operators_are_not_core_formulas() -> None:
    """Review P0-Q2 negative test: an equation whose only descriptors are raw
    source arithmetic (add/sub/mult/matmul) is NOT a core Method formula.
    The section receives no package from it; the deterministic fallback never
    wraps ``x + y`` / ``x * y`` bookkeeping as paper math."""

    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.formalization_agent import (
        build_deterministic_formula_packages,
        select_core_equations,
    )

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:add",
                subject="channel_weights",
                predicate="computes",
                object="weighted_channels",
                scope="sym:weight",
                direct_span_ids=["span:model.py:10:11"],
                semantic_context=["MULT", "ADD"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:add",
                validation_status="supported",
            ),
            CodeFactV1(
                fact_id="fact:shape",
                subject="residual",
                predicate="branches_on",
                object=["x.shape", "==", "y.shape"],
                scope="sym:residual",
                direct_span_ids=["span:model.py:12:12"],
                conditions=("x.shape == y.shape",),
                exact_source_digest="sha256:src2",
                canonical_identity="sha256:fact:shape",
                validation_status="supported",
            ),
        ],
        content_digest="sha256:facts-arith",
    )
    arithmetic = EquationClaimV1(
        equation_id="equation:weight",
        expression="out = w * x + b",
        fact_ids=["fact:add"],
        operation_descriptors=["add", "mult", "matmul"],
        symbol_bindings=[
            EquationSymbolBindingV1(symbol="w", operand_role="object", operand_value="weights", fact_id="fact:add"),
            EquationSymbolBindingV1(symbol="x", operand_role="object", operand_value="channels", fact_id="fact:add"),
            EquationSymbolBindingV1(symbol="b", operand_role="object", operand_value="bias", fact_id="fact:add"),
            EquationSymbolBindingV1(symbol="out", operand_role="result", operand_value="output", fact_id="fact:add"),
        ],
        canonical_identity="sha256:equation:weight",
        validation_status="supported",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts-arith",
        equations=[arithmetic],
        content_digest="sha256:equations-arith",
    )
    core = select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:weight"},
    )
    assert core == [], "raw add/mult arithmetic must not be selected as core"
    packages = build_deterministic_formula_packages(
        section_id="MA-S1",
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:weight"},
    )
    assert packages == (), "the deterministic fallback must not wrap raw arithmetic"


def test_formalizer_schema_status_distinguishes_truncation() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.publication_method_writer import (
        _formalizer_observability,
        _formalizer_schema_status,
    )

    truncated = SimpleNamespace(
        finish_reason="length",
        text='{"items": [{"latex": "$x',
        token_usage={"completion_tokens": 2048},
    )
    malformed = SimpleNamespace(
        finish_reason="stop",
        text="not-json",
        token_usage={"completion_tokens": 12},
    )
    config = SimpleNamespace(max_output_tokens=6144)
    assert _formalizer_schema_status(truncated) == "schema_failed_truncated"
    assert _formalizer_schema_status(malformed) == "schema_failed_malformed"
    obs = _formalizer_observability(truncated, config=config)
    assert obs["finish_reason"] == "length"
    assert obs["max_output_tokens"] == 6144
    assert obs["raw_preview"].startswith("{")


def test_declined_empty_is_a_typed_author_intent_disposition() -> None:
    from code2paper.agentic.formalization_agent import SectionFormulaDispositionV1

    item = SectionFormulaDispositionV1(
        section_id="MA-S1",
        disposition="declined_empty",
        review_note="author-intent Formalizer returned no package",
        review_question="Which formula should this section state?",
    )
    assert item.disposition == "declined_empty"
    assert item.disposition != "accepted"


def test_loss_relation_with_generic_add_descriptor_is_core_formula() -> None:
    """EBCAR-style contrastive loss: generic add descriptor + computes_formula."""

    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.formalization_agent import select_core_equations

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:infonce",
                subject="forward",
                predicate="computes_formula",
                object="negative positive similarity plus logsumexp over positive and negative similarities",
                scope="sym:forward",
                direct_span_ids=["span:model.py:70:71"],
                relation_evidence_ids=["rel:loss"],
                semantic_context=["ADD", "LOGSUMEXP"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:infonce",
                validation_status="supported",
            ),
        ],
        content_digest="sha256:facts-infonce",
    )
    equation = EquationClaimV1(
        equation_id="equation:infonce",
        expression="loss = -pos_sim + logsumexp(all_sims)",
        fact_ids=["fact:infonce"],
        operation_descriptors=["add"],
        relation_evidence_ids=["rel:loss"],
        symbol_bindings=[
            EquationSymbolBindingV1(
                symbol="loss", operand_role="result", operand_value="loss", fact_id="fact:infonce",
            ),
            EquationSymbolBindingV1(
                symbol="pos_sim", operand_role="object", operand_value="pos_sim", fact_id="fact:infonce",
            ),
            EquationSymbolBindingV1(
                symbol="all_sims", operand_role="object", operand_value="all_sims", fact_id="fact:infonce",
            ),
        ],
        canonical_identity="sha256:equation:infonce",
        validation_status="supported",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:formalizer",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts-infonce",
        equations=[equation],
        content_digest="sha256:equations-infonce",
    )
    core = select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:infonce"},
    )
    assert [item.equation_id for item in core] == ["equation:infonce"]


def test_placeholder_section_id_rejected_by_formalizer_schema() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        SectionFormalizerResponseV1,
        validate_section_formalizer_response,
    )
    import pytest

    with pytest.raises(ValueError, match="placeholder"):
        SectionFormalizerResponseV1(
            outcome="rendered",
            section_id="{section_id}",
            packages=(
                SectionFormulaPackageV1(
                    package_id="fp:bad:1",
                    section_id="{section_id}",
                    purpose="Loss.",
                    latex="loss = -pos_sim + logsumexp(all_sims)",
                    prose_explanation="Contrastive loss.",
                    symbol_definitions=(("loss", "loss"),),
                    authority_status="author_intent",
                    review_question="Which evidence binds the loss?",
                ),
            ),
        )

    response = SectionFormalizerResponseV1(
        outcome="unresolved",
        section_id="MA-S1",
        review_question="Which repository evidence binds the contrastive loss?",
    )
    failures = validate_section_formalizer_response(
        response,
        section_id="MA-S1",
        formula_obligation_required=True,
        formula_not_applicable=False,
    )
    assert failures == []

    with pytest.raises(ValueError, match="requires at least one package"):
        SectionFormalizerResponseV1(
            outcome="rendered",
            section_id="MA-S1",
            packages=(),
        )


def test_global_formalization_digest_does_not_fulfill_callback() -> None:
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1
    from code2paper.agentic.formalization_agent import (
        FormalizationSectionResultV1,
        SectionFormulaPackageV1,
        formalize_code_facts,
        section_result_from_packages,
    )
    from code2paper.agentic.method_argument_models import WritingResearchRequestV1
    from code2paper.agentic.writer_research_router import (
        execute_writing_research_route,
        route_writing_research_request,
    )

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:router",
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
    formalization = formalize_code_facts(facts=facts)
    request = WritingResearchRequestV1(
        request_id="request:formal_derivation",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="equation_or_derivation",
        exact_question="Which formula governs the score?",
        required_authority_lane="formal_derivation",
        candidate_symbols_or_terms=("equation:score",),
        why_needed_for_reader="The reader needs the score formula.",
        priority="high",
    )
    route = route_writing_research_request(request)

    # Global digest alone must not fulfill.
    assert execute_writing_research_route(
        route,
        request,
        formalization=formalization,
    ) is None

    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Score.",
        latex="s = w @ x + b",
        prose_explanation="The score combines weights and features.",
        symbol_definitions=(("s", "score"), ("w", "weights"), ("x", "features")),
        authority_status="author_intent",
        review_question="Which equation licenses the score?",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
    )
    foreign = section_result_from_packages(
        section_id="MA-S2",
        packages=(package.model_copy(update={"section_id": "MA-S2", "package_id": "fp:MA-S2:1"}),),
    )
    local = FormalizationSectionResultV1(
        section_id="MA-S1",
        packages=(package,),
    )

    assert execute_writing_research_route(
        route,
        request,
        formalization_sections=(foreign,),
    ) is None

    artifact = execute_writing_research_route(
        route,
        request,
        formalization_sections=(local,),
    )
    assert artifact is not None
    assert artifact.artifact_ref == "fp:MA-S1:1"
    assert artifact.artifact_digest == package.content_digest
    assert artifact.artifact_digest != formalization.content_digest


def test_computes_formula_shape_arithmetic_is_incidental_not_core() -> None:
    from code2paper.agentic.equation_claims import (
        compile_equation_claims,
        derive_equation_proposals_from_facts,
    )
    from code2paper.agentic.formalization_agent import (
        build_deterministic_formula_packages,
        select_core_equations,
    )

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:incidental",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:shape-product",
            subject="encoder",
            predicate="computes_formula",
            object=["num_channels", "channel_embedding_dim"],
            scope="sym:encoder",
            direct_span_ids=["span:model.py:20:20"],
            semantic_context=["MULT", "shape"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:shape-product",
        )],
        content_digest="sha256:incidental-facts",
    )
    proposals = derive_equation_proposals_from_facts(facts)
    assert proposals[0].formula_role == "incidental"
    equations, _reports = compile_equation_claims(
        proposals,
        facts,
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
    )
    assert equations.equations[0].formula_role == "incidental"
    assert select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:fact:shape-product"},
    ) == []
    assert build_deterministic_formula_packages(
        section_id="MA-S1",
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:fact:shape-product"},
    ) == ()


def test_generic_entity_weight_addition_without_mechanism_is_not_core() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.formalization_agent import select_core_equations

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:entity-weights",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:weights",
            subject="score",
            predicate="computes_formula",
            object=["entity_weights", "passage_weights"],
            scope="sym:score",
            direct_span_ids=["span:score.py:4:4"],
            semantic_context=["ADD"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:weights",
        )],
        content_digest="sha256:weights-facts",
    )
    equation = EquationClaimV1(
        equation_id="equation:weights",
        expression="s = x + y",
        fact_ids=["fact:weights"],
        operation_descriptors=["add"],
        symbol_bindings=[
            EquationSymbolBindingV1(
                symbol="s", operand_role="result", operand_value="score", fact_id="fact:weights",
            ),
            EquationSymbolBindingV1(
                symbol="x", operand_role="object", operand_value="entity_weights", fact_id="fact:weights",
            ),
            EquationSymbolBindingV1(
                symbol="y", operand_role="object", operand_value="passage_weights", fact_id="fact:weights",
            ),
        ],
        canonical_identity="sha256:equation:weights",
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
        code_fact_digest=facts.content_digest,
        equations=[equation],
        content_digest="sha256:weights-equations",
    )
    assert select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:weights"},
    ) == []


def test_bare_xy_with_attention_substring_operand_is_not_core() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
        effective_formula_role,
    )
    from code2paper.agentic.formalization_agent import (
        build_deterministic_formula_packages,
        select_core_equations,
    )

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:name-add",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:name-add",
            subject="train",
            predicate="computes_formula",
            object=["'hybrid_attention_'", "run_name"],
            scope="sym:train",
            direct_span_ids=["span:train.py:1:1"],
            semantic_context=["add", "'hybrid_attention_'", "run_name"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:name-add",
        )],
        content_digest="sha256:name-add-facts",
    )
    equation = EquationClaimV1(
        equation_id="equation:name-add",
        expression="x + y",
        fact_ids=["fact:name-add"],
        operation_descriptors=["add"],
        symbol_bindings=[
            EquationSymbolBindingV1(
                symbol="x", operand_role="object", operand_value="'hybrid_attention_'",
                fact_id="fact:name-add",
            ),
            EquationSymbolBindingV1(
                symbol="y", operand_role="object", operand_value="run_name",
                fact_id="fact:name-add",
            ),
        ],
        canonical_identity="sha256:equation:name-add",
    )
    assert effective_formula_role(equation) == "incidental"
    equations = EquationClaimSetV1(
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
        code_fact_digest=facts.content_digest,
        equations=[equation],
        content_digest="sha256:name-add-equations",
    )
    assert select_core_equations(
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:name-add"},
    ) == []
    assert build_deterministic_formula_packages(
        section_id="MA-S3",
        equations=equations,
        facts=facts,
        allowed_equation_ids={"equation:name-add"},
    ) == ()


def test_author_intent_formula_lane_requires_academic_display_math() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    package = SectionFormulaPackageV1(
        package_id="fp:author:delta",
        section_id="MA-S3",
        purpose="Define the time-aware step size.",
        latex=r"\Delta t = f(\Delta T)",
        markdown_block=r"$$\Delta t = f(\Delta T)$$",
        prose_explanation="The step size is defined as a function of the observed time gap.",
        symbol_definitions=(
            (r"\Delta t", "time-aware step size"),
            (r"\Delta T", "observed time gap"),
            ("f", "author-specified mapping"),
        ),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
        bound_facet_ids=("facet:delta",),
    )
    assert package.review_status == "review_required"
    assert validate_section_formula_package(
        package,
        equations=_equations(),
        facts=_facts(),
        allowed_facet_ids={"facet:delta"},
    ) == []


def test_author_intent_formula_rejects_code_shaped_expression() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    package = SectionFormulaPackageV1(
        package_id="fp:author:code-shaped",
        section_id="MA-S3",
        purpose="Define the mechanism.",
        latex="self.time_mamba.compute_step(x)",
        markdown_block="$$self.time_mamba.compute_step(x)$$",
        prose_explanation="A paper formula.",
        symbol_definitions=(("x", "input"),),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(
        package,
        equations=_equations(),
        facts=_facts(),
    )
    assert any("code_shaped_formula" in failure for failure in failures)


def test_formula_markdown_block_rejects_memo_wrapper() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        canonical_formula_markdown_block,
        validate_section_formula_package,
    )

    latex = r"\Delta t = f(\tau)"
    package = SectionFormulaPackageV1(
        package_id="fp:memo",
        section_id="MA-S3",
        purpose="Define the timespan step.",
        latex=latex,
        markdown_block=f"### Notes\n$$\n{latex}\n$$\n- assumption list",
        prose_explanation="The step depends on elapsed time.",
        symbol_definitions=((r"\Delta t", "step"),),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    assert package.markdown_block == canonical_formula_markdown_block(latex)
    assert validate_section_formula_package(
        package,
        equations=_equations(),
        facts=_facts(),
    ) == []


def test_hybrid_formula_lane_requires_explicit_assumptions() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    package = SectionFormulaPackageV1(
        package_id="fp:hybrid:delta",
        section_id="MA-S3",
        purpose="Formalize the partially supported time step.",
        latex=r"\Delta t = \operatorname{softplus}(g(\Delta T))",
        markdown_block=r"$$\Delta t = \operatorname{softplus}(g(\Delta T))$$",
        prose_explanation="The repository supports the projection and positive transform under the stated assumption.",
        symbol_definitions=(
            (r"\Delta t", "time step"),
            (r"\Delta T", "time gap"),
            ("g", "projection"),
        ),
        assumptions=("Monotonicity is an author assumption, not a repository fact.",),
        authority_status="partial",
        formula_lane="hybrid_partial",
    )
    assert validate_section_formula_package(
        package,
        equations=_equations(),
        facts=_facts(),
    ) == []


def test_formula_obligation_expectations_distinguish_required_and_preferred() -> None:
    from code2paper.agentic.formalization_agent import (
        MethodFormulaObligationV2,
        section_result_from_packages,
    )

    required = MethodFormulaObligationV2(
        obligation_id="formula:facet:required",
        facet_ids=("facet:required",),
        expectation="required",
        mathematical_goal="Define the method state transition.",
    )
    preferred = MethodFormulaObligationV2(
        obligation_id="formula:facet:preferred",
        facet_ids=("facet:preferred",),
        expectation="preferred",
        mathematical_goal="Give an optional intuition formula.",
    )
    result = section_result_from_packages(
        section_id="MA-S3",
        packages=(),
        formula_obligations=(required, preferred),
    )
    assert result.required_formula_failures == ("formula:facet:required",)
    assert result.preferred_formula_review_ids == ("formula:facet:preferred",)
    assert result.disposition is not None
    assert result.disposition.blocking_for_candidate is False
    truths = {item.obligation_id: item for item in result.obligation_truths}
    assert truths["formula:facet:required"].blocking is True
    assert truths["formula:facet:preferred"].blocking is False


def test_formalizer_receives_connected_exact_code_excerpts() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
    )

    pack = MechanismEquationEvidencePackV1(
        pack_id="pack:MA-S1",
        section_id="MA-S1",
        exact_excerpts=("def compute_score(x, w, b):\n    return x @ w + b",),
        bound_fact_ids=("fact:1",),
    )
    assert pack.exact_excerpts == ("def compute_score(x, w, b):\n    return x @ w + b",)
    assert pack.pack_id == "pack:MA-S1"


def test_candidate_formula_may_be_review_required_without_entering_verified() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    academic = SectionFormulaPackageV1(
        package_id="pkg-candidate-only",
        section_id="MA-S2",
        purpose="Define contrastive InfoNCE objective.",
        latex=r"\mathcal{L}_i = -\log \frac{\exp(s_i^+ / \tau)}{\sum_j \exp(s_{ij} / \tau)}",
        prose_explanation="The contrastive loss maximizes positive alignment relative to sampled negatives.",
        symbol_definitions=(
            (r"\mathcal{L}_i", "sample loss"),
            (r"s_i^+", "positive score"),
            (r"s_{ij}", "similarity score"),
            (r"\tau", "temperature parameter"),
        ),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
        review_status="review_required",
        review_question="Verify whether negative sampling temperature tau is dynamically scheduled.",
        bound_fact_ids=(),
        bound_equation_ids=(),
    )
    failures = validate_section_formula_package(
        academic,
        equations=_equations(),
        facts=_facts(),
    )
    assert failures == []
    assert academic.authority_status != "code_verified"


def test_formalizer_payload_strips_outer_dollar_display_wrapper() -> None:
    from code2paper.agentic.formalization_agent import (
        _normalize_formalizer_payload,
        canonical_formula_markdown_block,
        normalize_formula_latex_body,
    )

    payload = {
        "section_id": "MA-S1",
        "packages": [{
            "package_id": "fp:MA-S1:1",
            "section_id": "MA-S1",
            "purpose": "State diagonal matrix representation.",
            "latex": "$$ A = \\operatorname{diag}(\\lambda_1,\\dots,\\lambda_d) $$",
            "authority_status": "author_intent",
            "formula_lane": "author_intent_academic",
        }],
    }
    normalized = _normalize_formalizer_payload(payload, section_id="MA-S1")
    pkg = normalized["packages"][0]
    assert pkg["latex"] == "A = \\operatorname{diag}(\\lambda_1,\\dots,\\lambda_d)"
    assert "$$" not in pkg["latex"]
    assert pkg["markdown_block"] == canonical_formula_markdown_block(pkg["latex"])


def test_formalizer_payload_strips_bracket_display_wrapper() -> None:
    from code2paper.agentic.formalization_agent import normalize_formula_latex_body

    body = normalize_formula_latex_body(r"\[ x = y + z \]")
    assert body == "x = y + z"


def test_formalizer_payload_keeps_aligned_environment_inside_body() -> None:
    from code2paper.agentic.formalization_agent import normalize_formula_latex_body

    latex = "$$\n\\begin{aligned}\nx &= 1 \\\\\ny &= 2\n\\end{aligned}\n$$"
    normalized = normalize_formula_latex_body(latex)
    assert normalized == "\\begin{aligned}\nx &= 1 \\\\\ny &= 2\n\\end{aligned}"
    assert "$$" not in normalized


def test_formula_normalization_does_not_change_math_body() -> None:
    from code2paper.agentic.formalization_agent import normalize_formula_latex_body

    raw = "$$ A_t = \\exp(-\\Delta t \\cdot B) + C $$"
    normalized = normalize_formula_latex_body(raw)
    assert normalized == "A_t = \\exp(-\\Delta t \\cdot B) + C"


def test_normalized_formula_still_runs_all_semantic_guards() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pkg = SectionFormulaPackageV1(
        package_id="pkg:test",
        section_id="MA-S1",
        purpose="Compute score with guaranteed optimality.",
        latex="$$ s = w @ x + b $$",
        prose_explanation="This proves guaranteed optimality under all distributions.",
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(
        pkg,
        equations=_equations(),
        facts=_facts(),
    )
    assert "$$" not in pkg.latex
    assert "latex_contains_display_wrapper" not in failures
    assert "unsupported_theoretical_upgrade" in failures


def test_standard_arrow_commands_are_not_symbols() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pkg = SectionFormulaPackageV1(
        package_id="pkg:arrow",
        section_id="MA-S1",
        purpose="Illustrate transition with standard arrow commands.",
        latex=r"x \xrightarrow{f} y \downarrow z",
        prose_explanation="Transition maps x to y with downward projection to z.",
        symbol_definitions=(
            ("x", "input"),
            ("y", "output"),
            ("z", "projection"),
            ("f", "mapping"),
        ),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(
        pkg,
        equations=_equations(),
        facts=_facts(),
    )
    assert not any("undefined_symbols" in f for f in failures)


def test_unknown_custom_command_still_fails_symbol_closure() -> None:
    from code2paper.agentic.formalization_agent import (
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pkg = SectionFormulaPackageV1(
        package_id="pkg:custom",
        section_id="MA-S1",
        purpose="Formula with unknown macro.",
        latex=r"x = \myCustomUnknownMacro(y)",
        prose_explanation="Applies unknown custom macro to y.",
        symbol_definitions=(("x", "output"), ("y", "input")),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(
        pkg,
        equations=_equations(),
        facts=_facts(),
    )
    assert any("undefined_symbols:\\myCustomUnknownMacro" in f for f in failures)


def test_code_verified_paper_operator_can_bind_generic_run_callable() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pack = MechanismEquationEvidencePackV1(
        pack_id="pack:MA-S4",
        section_id="MA-S4",
        bound_fact_ids=("fact:ppr",),
        operation_atoms=(
            {
                "fact_id": "fact:ppr",
                "predicate": "computes_formula",
                "operation": "self.run_ppr(adj, restart_prob)",
                "operands": ["self.run_ppr", "adj", "restart_prob"],
                "result": "ppr_scores",
            },
        ),
        formalizable_signatures=(
            {
                "fact_id": "fact:ppr",
                "predicate": "computes_formula",
                "operands": ["self.run_ppr", "adj", "restart_prob"],
                "result": "ppr_scores",
            },
        ),
    )
    pkg = SectionFormulaPackageV1(
        package_id="pkg:ppr",
        section_id="MA-S4",
        purpose="Compute Personalized PageRank scores.",
        latex=r"\pi = \operatorname{PPR}(A, \alpha)",
        prose_explanation="Computes personalized PageRank scores from adjacency matrix and restart probability.",
        symbol_definitions=(
            (r"\pi", "personalized PageRank score"),
            (r"A", "adjacency matrix"),
            (r"\alpha", "restart probability"),
        ),
        authority_status="code_verified",
        formula_lane="repository_derived",
        bound_fact_ids=("fact:ppr",),
    )
    fact_set = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:ppr",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[CodeFactV1(
            fact_id="fact:ppr",
            subject="run_ppr",
            predicate="computes_formula",
            object="ppr_scores",
            scope="sym:run_ppr",
            direct_span_ids=["span:ppr.py:1:10"],
            semantic_context=["PPR"],
            exact_source_digest="sha256:src",
            canonical_identity="sha256:fact:ppr",
            validation_status="supported",
        )],
        content_digest="sha256:facts",
    )
    failures = validate_section_formula_package(
        pkg,
        equations=None,
        facts=fact_set,
        operation_evidence_packs=(pack,),
    )
    assert "operation_operand_binding_missing:self.run_ppr" not in failures
    assert failures == []


def test_raw_callable_name_need_not_appear_in_paper_formula() -> None:
    from code2paper.agentic.formalization_agent import _operation_callable_is_rendered

    assert _operation_callable_is_rendered("self.run_ppr", r"\pi = \operatorname{PPR}(A, \alpha)") is True
    assert _operation_callable_is_rendered("compute_score", r"s = \operatorname{score}(x)") is True
    assert _operation_callable_is_rendered("torch.cat", r"z = \operatorname{concat}(a, b)") is True


def test_symbol_meaning_can_bind_source_result_semantically() -> None:
    from code2paper.agentic.formalization_agent import (
        _operation_binding_tokens,
        _operation_value_is_bound,
    )

    meaning_tokens = _operation_binding_tokens("personalized PageRank score")
    declared_meanings = ((r"\pi", meaning_tokens),)
    bound = _operation_value_is_bound(
        "self.run_ppr",
        surface_tokens={"pi", "a", "alpha"},
        declared_meanings=declared_meanings,
    )
    assert bound is True


def test_dtype_rearrange_plumbing_does_not_block_formula() -> None:
    from code2paper.agentic.formalization_agent import (
        _is_operation_implementation_plumbing,
        _operation_source_shapes,
    )

    plumbing = "rearrange(self.in_proj.bias.to(dtype=xz.dtype), 'd -> d 1')"
    assert _is_operation_implementation_plumbing(plumbing) is True

    shapes = _operation_source_shapes(({
        "operation_atoms": [{
            "shape_or_type_hints": [plumbing, "B x L x d"],
        }],
    },))
    assert plumbing not in shapes
    assert "B x L x d" in shapes


def test_material_branch_condition_still_must_be_preserved() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pack = MechanismEquationEvidencePackV1(
        pack_id="pack:cond",
        section_id="MA-S1",
        bound_fact_ids=("fact:cond",),
        operation_atoms=({
            "fact_id": "fact:cond",
            "predicate": "computes_formula",
            "operands": ["x", "w"],
            "result": "y",
            "conditions": ["threshold > 0.5"],
        },),
    )
    pkg = SectionFormulaPackageV1(
        package_id="pkg:cond",
        section_id="MA-S1",
        purpose="Compute output y = w * x without condition.",
        latex=r"y = w \cdot x",
        prose_explanation="Computes y as product of w and x.",
        symbol_definitions=((r"y", "output"), (r"w", "weights"), (r"x", "input")),
        authority_status="code_verified",
        formula_lane="repository_derived",
        bound_fact_ids=("fact:cond",),
    )
    failures = validate_section_formula_package(
        pkg,
        equations=None,
        facts=None,
        operation_evidence_packs=(pack,),
    )
    assert any("operation_condition_missing" in f for f in failures)


def test_operator_family_mismatch_still_fails() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pack = MechanismEquationEvidencePackV1(
        pack_id="pack:mismatch",
        section_id="MA-S1",
        bound_fact_ids=("fact:add",),
        operation_atoms=({
            "fact_id": "fact:add",
            "predicate": "computes_formula",
            "operation": "add",
            "operands": ["a", "b"],
            "result": "c",
        },),
    )
    pkg = SectionFormulaPackageV1(
        package_id="pkg:mismatch",
        section_id="MA-S1",
        purpose="Sort a and b.",
        latex=r"c = \operatorname{sort}(a, b)",
        prose_explanation="Sorts operands a and b.",
        symbol_definitions=((r"c", "result"), (r"a", "first"), (r"b", "second")),
        authority_status="code_verified",
        formula_lane="repository_derived",
        bound_fact_ids=("fact:add",),
    )
    failures = validate_section_formula_package(
        pkg,
        equations=None,
        facts=None,
        operation_evidence_packs=(pack,),
    )
    assert any("operation_signature_mismatch" in f for f in failures)


def test_unbound_fact_still_fails() -> None:
    from code2paper.agentic.formalization_agent import (
        MechanismEquationEvidencePackV1,
        SectionFormulaPackageV1,
        validate_section_formula_package,
    )

    pack = MechanismEquationEvidencePackV1(
        pack_id="pack:known",
        section_id="MA-S1",
        bound_fact_ids=("fact:known",),
        operation_atoms=({
            "fact_id": "fact:known",
            "predicate": "computes_formula",
            "operands": ["a", "b"],
            "result": "c",
        },),
    )
    pkg = SectionFormulaPackageV1(
        package_id="pkg:unbound",
        section_id="MA-S1",
        purpose="Unbound fact formula.",
        latex=r"c = a + b",
        prose_explanation="Adds a and b.",
        symbol_definitions=((r"c", "result"), (r"a", "first"), (r"b", "second")),
        authority_status="code_verified",
        formula_lane="repository_derived",
        bound_fact_ids=("fact:unbound_other",),
    )
    failures = validate_section_formula_package(
        pkg,
        equations=None,
        facts=None,
        operation_evidence_packs=(pack,),
    )
    assert "operation_evidence_unbound" in failures
