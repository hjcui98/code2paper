"""Formalization Agent guards: mutation rejection, bounded owner retry, upgrade denial."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

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


def _legacy_formalizer_context(*, operation_result: str = "y") -> SimpleNamespace:
    """Minimal mechanism context with one bound detail and operation.

    ``operation_result=""`` leaves the operation bound but not
    deterministically formalizable, so the legacy LLM lane is reached.
    """

    from code2paper.agentic.mechanism_context_models import (
        DetailWitnessAtomV1,
        EvidenceOperationV1,
        MechanismDetailV1,
        MechanismEvidenceClosureV1,
        SourceOperationDispositionV1,
    )

    operation = EvidenceOperationV1(
        operation_id="op:legacy",
        predicate="COMPUTE",
        operands=("x", "W"),
        result=operation_result,
        source_span_id="span:src/model.py:1:2",
        active_path_status="active_default",
    )
    detail = MechanismDetailV1(
        detail_id="detail:legacy",
        primary_mechanism_id="mech:legacy",
        order_index=0,
        role="transformation",
        importance="core",
        claim_kind="implementation",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="linear projection",
        predicate="COMPUTE",
        operands=("x", "W"),
        result=operation_result,
        active_path_status="active_default",
        source_operation_ids=("op:legacy",),
        source_span_ids=("span:src/model.py:1:2",),
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:legacy",
                atom_kind="operation",
                semantic_anchor="linear projection",
                source_operation_ids=("op:legacy",),
                exact_excerpts=("y = x @ W",),
            ),
        ),
        content_digest="",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:legacy",
        mechanism_id="mech:legacy",
        operation_nodes=(operation,),
        operation_dispositions=(SourceOperationDispositionV1(
            operation_id="op:legacy",
            disposition="absorbed_by_detail",
            detail_ids=("detail:legacy",),
        ),),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:src/model.py:1:2",),
        content_digest="",
    )
    return SimpleNamespace(
        mechanism_id="mech:legacy",
        content_digest="sha256:context",
        source_context_digest="sha256:context",
        details=(detail,),
        evidence_closure=closure,
    )

# ---------------------------------------------------------------------------
# R5: formula identity, authority and condition expression
# ---------------------------------------------------------------------------


def _mechanism_package(**overrides):
    from code2paper.agentic.formalization_agent import MechanismFormulaPackageV2

    payload = {
        "package_id": "pkg:r5",
        "mechanism_id": "mech:r5",
        "source_detail_ids": ("detail:r5",),
        "satisfied_obligation_ids": ("ob:r5",),
        "latex": "y = W x",
        "prose_explanation": "Linear projection.",
        "evidence_authority": "repository_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
        "bound_operation_ids": ("op:r5",),
    }
    payload.update(overrides)
    return MechanismFormulaPackageV2.model_validate(payload)


def test_compound_operator_chain_accepts_equivalent_latex_arrow() -> None:
    """Content validation accepts typeset arrows while retaining operator order."""

    from code2paper.agentic.formalization_agent import (
        MechanismFormulaObligationV1,
        MechanismFormulaPackageV2,
        validate_mechanism_formula_package,
    )

    context = _legacy_formalizer_context()
    obligation = MechanismFormulaObligationV1(
        obligation_id="ob:legacy",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:legacy",),
        mathematical_goal="Formalize the operation chain.",
        required_operator_signatures=({
            "predicate": "COMPUTE -> WRITE",
            "operands": ["x", "W", "y"],
            "result": "y",
        },),
        required_operand_sets=(("x", "W", "y"),),
        source_operation_ids=("op:legacy",),
    )
    package = MechanismFormulaPackageV2(
        package_id="pkg:compound",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:legacy",),
        satisfied_obligation_ids=("ob:legacy",),
        latex=r"\text{COMPUTE}(x, W) \xrightarrow{\text{WRITE}} y",
        prose_explanation="The computed value is written to y.",
        source_context_digest="sha256:context",
        bound_operation_ids=("op:legacy",),
    )

    failures = validate_mechanism_formula_package(
        package,
        context=context,
        obligation=obligation,
    )

    assert not any("missing_required_operator" in failure for failure in failures)
    assert not any("formula_operand_set_mismatch" in failure for failure in failures)


def test_author_intent_formula_with_fact_id_is_not_repository_authority() -> None:
    """R5: an author-intent package never becomes code_verified via a fact id."""

    from code2paper.agentic.formalization_agent import (
        adapt_mechanism_formula_package_to_legacy,
    )

    disguised = _mechanism_package(
        formula_lane="author_intent_academic",
        review_status="review_required",
        bound_operation_ids=(),
        bound_fact_ids=("fact:author",),
    )
    legacy = adapt_mechanism_formula_package_to_legacy(disguised, section_id="sec:1")

    assert legacy.authority_status == "author_intent"
    assert legacy.formula_lane == "author_intent_academic"
    assert legacy.review_status == "review_required"
    assert legacy.schema_version == "2.0"


def test_review_required_repository_formula_is_not_accepted() -> None:
    from code2paper.agentic.formalization_agent import (
        adapt_mechanism_formula_package_to_legacy,
    )

    pending = _mechanism_package(review_status="review_required")
    legacy = adapt_mechanism_formula_package_to_legacy(pending, section_id="sec:1")

    assert legacy.review_status == "review_required"
    assert legacy.authority_status == "partial"
    assert legacy.formula_lane == "hybrid_partial"


def test_repository_derived_formula_requires_exact_bindings() -> None:
    from code2paper.agentic.formalization_agent import (
        adapt_mechanism_formula_package_to_legacy,
    )

    unbound = _mechanism_package(
        bound_operation_ids=(),
        bound_fact_ids=(),
        bound_equation_ids=(),
    )
    legacy = adapt_mechanism_formula_package_to_legacy(unbound, section_id="sec:1")

    assert legacy.authority_status == "partial"
    assert legacy.review_status == "review_required"

    bound = adapt_mechanism_formula_package_to_legacy(
        _mechanism_package(), section_id="sec:1"
    )
    assert bound.authority_status == "code_verified"
    assert bound.formula_lane == "repository_derived"
    assert bound.review_status == "accepted"


def test_current_package_missing_disposition_is_not_historically_accepted() -> None:
    """R5: only a version-marked legacy package may use the compat branch."""

    from code2paper.agentic.publication_transaction_contract import (
        _formula_package_terminal_disposition,
    )

    current = {
        "package_id": "pkg:current",
        "schema_version": "2.0",
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
    }
    assert _formula_package_terminal_disposition(current) == "review_required"

    legacy = {
        "package_id": "pkg:legacy",
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
    }
    assert _formula_package_terminal_disposition(legacy) == "accepted"

    explicit = {
        "package_id": "pkg:current",
        "schema_version": "2.0",
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
    }
    assert _formula_package_terminal_disposition(explicit) == "accepted"

    rejected = {
        "package_id": "pkg:current",
        "schema_version": "2.0",
        "review_status": "rejected",
    }
    assert _formula_package_terminal_disposition(rejected) == "failed"


def test_condition_binding_is_structural_and_never_lexical() -> None:
    """R5 correction: only a provably identical condition may bind.

    Lexical helpers locate a candidate clause; authorization requires the same
    clause structure (order, AND/OR, negation parity, comparison operator and
    numeric literals).  A bare identifier is not a reader-facing conditional
    statement, so it never authorizes by itself.
    """

    from code2paper.agentic.publication_transaction_contract import (
        _condition_statement_matches,
        _witness_satisfies_constraints,
    )

    declared = "self.cfg.use_dedicated_attention"
    # Reader-facing phrasing of the same switch is located and binds.
    assert _condition_statement_matches(
        declared, "When dedicated attention is enabled, the model uses the mask."
    )
    # Hyphenated reader labels and the word ``flag`` are representation-only
    # variants of the same scoped switch.
    assert _condition_statement_matches(
        declared,
        "When the dedicated-attention flag is enabled, the model uses the mask.",
    )
    assert _condition_statement_matches(
        "self.cfg.add_positional_encoding",
        "When the positional-encoding flag is enabled, the model adds the embedding.",
    )
    # The raw identifier is not prose and must not authorize on identity.
    assert not _condition_statement_matches(declared, declared)
    # A dropped condition never matches.
    assert not _condition_statement_matches(
        declared, "The model always builds the dedicated attention mask."
    )
    # A reversed condition never matches.
    assert not _condition_statement_matches(
        declared, "When dedicated attention is disabled, the model uses the mask."
    )
    # An appended opposite condition never matches.
    assert not _condition_statement_matches(
        declared,
        "When dedicated attention is enabled or disabled, the mask is built.",
    )
    # A widened (unconditional) statement never matches.
    assert not _condition_statement_matches(
        declared, "Regardless of configuration the model uses the mask."
    )
    # Boolean structure is preserved: AND never authorizes OR and vice versa.
    assert _condition_statement_matches(
        "alpha and beta", "When alpha and beta hold, compute the output."
    )
    assert not _condition_statement_matches(
        "alpha and beta", "When alpha or beta holds, compute the output."
    )
    assert _condition_statement_matches(
        "alpha or beta", "When alpha or beta holds, compute the output."
    )
    assert not _condition_statement_matches(
        "alpha or beta", "When alpha and beta hold, compute the output."
    )
    # Nested negation keeps its parity.
    assert _condition_statement_matches(
        "not alpha", "When alpha does not hold, compute the output."
    )
    assert not _condition_statement_matches(
        "not alpha", "When alpha holds, compute the output."
    )
    # Comparison boundaries and scope are part of the condition.
    assert _condition_statement_matches("x >= 5", "When x >= 5, compute the output.")
    assert _condition_statement_matches(
        "x >= 5", "When x is at least 5, compute the output."
    )
    assert not _condition_statement_matches(
        "x >= 5", "When x >= 3, compute the output."
    )
    assert not _condition_statement_matches(
        "x > 5", "When x >= 5, compute the output."
    )
    assert not _condition_statement_matches(
        "x >= 5", "When x is at most 5, compute the output."
    )

    constraints = {
        "semantic_atom": "",
        "exact": (),
        "conditions": (declared,),
        "polarity": "conditional",
    }
    assert _witness_satisfies_constraints(
        "When dedicated attention is enabled, the mask is built.", constraints
    )
    assert not _witness_satisfies_constraints(
        "The mask is always built.", constraints
    )
    assert not _witness_satisfies_constraints(
        "When dedicated attention is disabled, the mask is built.", constraints
    )
    assert not _witness_satisfies_constraints(
        "When dedicated attention is enabled or disabled, the mask is built.",
        constraints,
    )


def test_condition_binding_rejects_regrouping_signs_negation_and_operand_order() -> None:
    """R5 correction: the second review's five structural counterexamples.

    Each pair keeps the same words on both sides; only the structure differs.
    Word-set matching accepted them, the structural grammar must not.
    """

    from code2paper.agentic.publication_transaction_contract import (
        _condition_statement_matches,
        _witness_condition_and_polarity_satisfied,
    )

    cases = (
        (
            "(alpha or beta) and gamma",
            "When alpha or (beta and gamma), output is computed.",
        ),
        ("value > -5", "When value > 5, output is computed."),
        ("not not alpha", "When not alpha, output is computed."),
        ("alpha < beta", "When beta < alpha, output is computed."),
        ("alpha", "When alpha or beta, output is computed."),
    )
    for declared, witness in cases:
        assert not _condition_statement_matches(declared, witness), (
            declared,
            witness,
        )
        assert not _witness_condition_and_polarity_satisfied(
            witness, {"conditions": (declared,)}
        ), (declared, witness)

    # The structurally identical forms still bind.
    assert _condition_statement_matches(
        "(alpha or beta) and gamma",
        "When (alpha or beta) and gamma, the output is computed.",
    )
    assert _condition_statement_matches(
        "value > -5", "When value > -5, the output is computed."
    )
    assert _condition_statement_matches(
        "not not alpha", "When not not alpha, the output is computed."
    )
    assert _condition_statement_matches(
        "alpha < beta", "When alpha < beta, the output is computed."
    )


def test_compact_formula_payload_keeps_machine_readable_metadata() -> None:
    from code2paper.llm.section_writer import _compact_formula_packages_for_llm

    package = {
        "schema_version": "2.0",
        "package_id": "pkg:meta",
        "purpose": "State the objective.",
        "prose_explanation": "Objective in paper notation.",
        "authority_status": "code_verified",
        "formula_lane": "repository_derived",
        "review_status": "accepted",
        "material_conditions": ["self.cfg.use_dedicated_attention"],
        "assumptions": ["training scope"],
        "consumer_paragraph_id": "sec:1:p2",
        "source_detail_ids": ["detail:r5"],
        "latex": "y = W x",
    }
    compact = _compact_formula_packages_for_llm([package])
    assert len(compact) == 1
    item = compact[0]
    for key in (
        "review_status",
        "schema_version",
        "source_detail_ids",
        "material_conditions",
        "assumptions",
        "consumer_paragraph_id",
        "formula_lane",
        "authority_status",
    ):
        assert key in item, key
    assert item["review_status"] == "accepted"
    assert item["consumer_paragraph_id"] == "sec:1:p2"


def test_legacy_formalizer_reads_real_llm_response_text() -> None:
    """R5: the legacy caller reads LLMResponse.text / blocked_reason."""

    import json as _json

    from code2paper.llm.client import LLMResponse
    from code2paper.agentic.formalization_agent import (
        _run_mechanism_formalizer_legacy,
    )

    calls: list[object] = []

    def caller(config, request):
        calls.append(request)
        return LLMResponse(
            text=_json.dumps({
                "latex": "y = W x",
                "prose_explanation": "Linear projection.",
                "symbol_definitions": [["W", "weight matrix"]],
                "material_conditions": [],
            }),
            response_hash="sha256:legacy",
            finish_reason="stop",
        )

    from code2paper.agentic.formalization_agent import (
        MechanismFormulaObligationV1,
    )

    context = _legacy_formalizer_context(operation_result="")
    obligation = MechanismFormulaObligationV1(
        obligation_id="ob:legacy",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:legacy",),
        source_operation_ids=("op:legacy",),
        mathematical_goal="Formalize the projection.",
    )
    packages, trace = _run_mechanism_formalizer_legacy(
        context=context,
        obligations=(obligation,),
        shared_payload_pages=("page-body",),
        shared_payload_digest="sha256:page",
        llm_config=SimpleNamespace(),
        caller=caller,
    )

    assert calls and trace["llm_call_made"] is True
    assert trace["llm_page_calls"] == 1
    # The real ``LLMResponse.text`` payload was parsed; a caller reading the
    # empty ``content`` field instead would record an empty-response failure.
    assert not [
        failure for failure in trace["failures"]
        if failure.startswith("llm_empty_response:")
    ]
    assert [package.latex for package in packages] == ["y = W x"]


def test_legacy_formalizer_records_blocked_response() -> None:
    from code2paper.llm.client import LLMResponse
    from code2paper.agentic.formalization_agent import (
        _run_mechanism_formalizer_legacy,
    )

    def caller(config, request):
        return LLMResponse(
            text="",
            response_hash="sha256:blocked",
            blocked_reason="provider_timeout",
            finish_reason="stop",
        )

    from code2paper.agentic.formalization_agent import (
        MechanismFormulaObligationV1,
    )

    context = _legacy_formalizer_context(operation_result="")
    obligation = MechanismFormulaObligationV1(
        obligation_id="ob:legacy",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:legacy",),
        source_operation_ids=("op:legacy",),
        mathematical_goal="Formalize the projection.",
    )
    packages, trace = _run_mechanism_formalizer_legacy(
        context=context,
        obligations=(obligation,),
        shared_payload_pages=("page-body",),
        shared_payload_digest="sha256:page",
        llm_config=SimpleNamespace(),
        caller=caller,
    )

    assert packages == ()
    assert any(
        failure.startswith("llm_blocked:") for failure in trace["failures"]
    )
    assert trace["llm_page_calls"] == 1
    # R5: an interface outcome is separated from a normal no-package result.
    assert trace["interface_failures"] == [{
        "kind": "llm_blocked",
        "obligation_id": "ob:legacy",
        "page_index": 0,
        "reason": "provider_timeout",
    }]
    assert trace["missing_binding_obligations"] == []
    assert trace["rejected_obligations"] == []
    assert trace["not_applicable_obligations"] == []
    assert trace["deterministic_obligation_ids"] == []

def test_legacy_formalizer_separates_missing_binding_and_not_applicable() -> None:
    """R5: no-package outcomes stay distinguishable in the legacy trace."""

    from code2paper.agentic.formalization_agent import (
        MechanismFormulaObligationV1,
        _run_mechanism_formalizer_legacy,
    )

    context = _legacy_formalizer_context(operation_result="")
    missing = MechanismFormulaObligationV1(
        obligation_id="ob:missing",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:absent",),
        mathematical_goal="Formalize the absent projection.",
    )
    optional = MechanismFormulaObligationV1(
        obligation_id="ob:optional",
        mechanism_id="mech:legacy",
        source_detail_ids=("detail:legacy",),
        source_operation_ids=("op:legacy",),
        mathematical_goal="Optionally describe the projection.",
        expectation="none",
    )
    calls: list[object] = []

    def caller(config, request):  # pragma: no cover - must not be reached
        calls.append(request)
        raise AssertionError("no model call may occur here")

    packages, trace = _run_mechanism_formalizer_legacy(
        context=context,
        obligations=(missing, optional),
        shared_payload_pages=("page-body",),
        shared_payload_digest="sha256:page",
        llm_config=SimpleNamespace(),
        caller=caller,
    )

    assert packages == ()
    assert calls == []
    assert trace["missing_binding_obligations"] == ["ob:missing"]
    assert trace["not_applicable_obligations"] == ["ob:optional"]
    assert trace["rejected_obligations"] == []
    assert trace["interface_failures"] == []
    assert trace["llm_page_calls"] == 0
    assert "formula_source_binding_missing:ob:missing" in trace["failures"]


def test_condition_binding_rejects_operator_and_scope_changes() -> None:
    """R5 correction (third review): the expression must be fully conserved.

    Arithmetic operators, attribute/index operands and boolean scope are part
    of the condition; a witness that swaps ``*`` for ``/``, drops a negation or
    adds an ``or`` branch around the matched phrase must not authorize it, while
    an identical indexed guard must still bind.
    """

    from code2paper.agentic.publication_transaction_contract import (
        _condition_statement_matches,
        _witness_condition_and_polarity_satisfied,
    )

    cases = (
        ("x * y > 5", "When x / y > 5, output is computed."),
        ("x + y > 5", "When x - y > 5, output is computed."),
        ("!alpha", "When alpha, output is computed."),
        ("alpha", "When beta or when alpha, output is computed."),
        ("x.shape[0] > 0", "When x.shape[1] > 0, the output is computed."),
    )
    for declared, witness in cases:
        assert not _condition_statement_matches(declared, witness), (
            declared,
            witness,
        )
        assert not _witness_condition_and_polarity_satisfied(
            witness, {"conditions": (declared,)}
        ), (declared, witness)

    # A legal indexed guard and the operator-preserving rewrites still bind.
    assert _condition_statement_matches(
        "x.shape[0] > 0", "When x.shape[0] > 0, the output is computed."
    )
    assert _condition_statement_matches(
        "x * y > 5", "When x * y > 5, the output is computed."
    )
    assert _condition_statement_matches(
        "x + y > 5", "When x + y > 5, the output is computed."
    )
    assert _condition_statement_matches(
        "!alpha", "When !alpha, the output is computed."
    )
# --------------------------------------------------------------------------- #
# K04-G7：Formalizer 发送前校验、no-send 回执来源与合法缓存复用
# --------------------------------------------------------------------------- #
#
# 窄范围复核（K04 授权）：原 Formalizer caller/receipt consumer。
#   * 发送前校验必须真的在 provider 之前（反例：改实际请求 → 零发送 + 具名拒绝）；
#   * no-send 尝试不得发行一条把**计划存储摘要**写成 actual 的回执；
#   * reader 不得因此把未实测材料当作已验证；
#   * 合法缓存复用不得被强制变成重发，也不得放松成"未验证也复用"。


def _g7_plan_and_material():
    """复用已完成 Formalizer 夹具的真实 material/manifest/plan（只替换 provider 输出）。"""

    from tests.integrations.dsh.fixtures import completed_formalizer_fixture as fixture
    from tests.integrations.dsh.fixtures import legacy_fixture_builder as builder

    archive, obligation, _source_digest, _source_manifest = fixture._material()
    envelope = builder._budget_envelope()
    manifest = builder.build_consumer_workset_manifest_v2(
        archive,
        {"mech_rescale": (obligation,)},
        max_page_input_tokens=envelope.max_page_input_tokens,
        max_obligations_per_page=envelope.max_obligations_per_page,
    )
    plan = builder.build_consumer_invocation_plan_v1(
        manifest,
        envelope,
        phase="formalizer",
        max_attempts=1,
        profile_digest=envelope.profile_digest,
        model_identity_digest=envelope.model_identity_digest,
        model_context_tokens=131072,
    )
    return archive, obligation, manifest, plan, envelope


def _g7_provider_row() -> str:
    return json.dumps({"results": [{
        "obligation_id": "ob:rescale",
        "latex": "y = a * x",
        "prose_explanation": "The output y is the scalar a times the input x.",
        "symbol_definitions": [["y", "rescaled output"], ["a", "scalar factor"], ["x", "input"]],
        "material_conditions": [],
        "assumptions": [],
    }]}, ensure_ascii=False)


def _g7_run(*, ledger_root=None, mutate=None, caller_available: bool = True, monkeypatch=None):
    from code2paper.agentic.formalization_agent import execute_formalizer_invocation_plan
    from code2paper.llm import client as llm_client
    from code2paper.llm.client import LLMConfig, LLMProvider

    archive, obligation, manifest, plan, envelope = _g7_plan_and_material()
    calls: list[Any] = []

    def provider(_config, request):
        calls.append(request)
        raw = _g7_provider_row()
        return LLMResponse(text=raw, response_hash="sha256:g7-formalizer", finish_reason="stop")

    if mutate is not None:
        # 真实构造点在 `_run_one` 内部执行 `from code2paper.llm.client import LLMRequest`，
        # 因此在 client 模块上替换同名构造器即可只改"caller 看到的可变请求对象"。
        real_request = llm_client.LLMRequest

        def request_factory(**kwargs):
            payload = kwargs.get("input_payload")
            if (
                isinstance(payload, dict)
                and kwargs.get("prompt_template_id") == "unified_formalizer_page_v2"
            ):
                mutated = json.loads(json.dumps(payload, ensure_ascii=False))
                mutate(mutated)
                kwargs = {**kwargs, "input_payload": mutated}
            return real_request(**kwargs)

        monkeypatch.setattr(llm_client, "LLMRequest", request_factory)

    execution = execute_formalizer_invocation_plan(
        plan=plan,
        workset_manifest=manifest,
        archive=archive,
        obligations_by_id={obligation.obligation_id: obligation},
        llm_config=LLMConfig(
            provider=LLMProvider.NONE, model="g7-offline", max_output_tokens=4096, cache=False
        ),
        caller=provider if caller_available else None,
        max_attempts=1,
        ledger_root=ledger_root,
        budget_envelope=envelope,
        model_identity_digest=envelope.model_identity_digest,
        run_digest=archive.content_digest,
    )
    return execution, calls, manifest, plan


def _g7_page_digest(manifest, row) -> str:
    page_id = str(row.get("page_id") or "")
    page = manifest.page_by_id(page_id) if page_id else None
    return str(getattr(page, "technical_bytes_digest", "") or "")


def test_g7_mutated_actual_request_is_refused_before_the_formalizer_provider(
    tmp_path: Path, monkeypatch
) -> None:
    """G7 反例/对照：改实际请求 → provider 零调用且具名拒绝；合法请求恰好一次并被接受。"""

    # 正对照：同一夹具、同一调用点，不改动时合法请求恰好发送一次并被接受。
    control, control_calls, control_manifest, _plan = _g7_run(
        ledger_root=tmp_path / "control"
    )
    assert len(control_calls) == 1, "合法 formalizer 请求必须恰好发送一次"
    assert control.accepted_packages, "合法请求必须产出被接受的公式包"
    assert control.assertion_failures == (), control.assertion_failures
    sent = [row for row in control.receipts if row.get("sent_to_caller") is True]
    assert sent, control.receipts
    for row in sent:
        measured = str(row.get("actual_technical_bytes_digest") or "")
        assert measured, row
        assert measured == _g7_page_digest(control_manifest, row), row

    # 反例：只改实际请求里的页技术材料（同一构造点、单变量）。
    def _change_page_material(payload: dict) -> None:
        page_payload = payload.get("technical_payload")
        assert isinstance(page_payload, dict)
        page_payload["mutated_by_adapter"] = True

    mutated, mutated_calls, mutated_manifest, _plan = _g7_run(
        ledger_root=tmp_path / "mutated",
        mutate=_change_page_material,
        monkeypatch=monkeypatch,
    )
    assert mutated_calls == [], "改材料的 formalizer 请求不得发给 provider"
    assert mutated.accepted_packages == ()
    failures = " ".join(
        [*mutated.task_failures]
        + [
            str(item)
            for row in mutated.receipts
            for item in (row.get("task_failures") or ())
        ]
    )
    assert "formalizer_pre_send_rejected" in failures, failures
    assert "unified_actual_page_bytes_mismatch" in failures, failures
    # no-send 回执必须自称未越过边界，actual 是**从请求重算**的值而不是计划存储值。
    no_send = [row for row in mutated.receipts if row.get("sent_to_caller") is False]
    assert no_send, mutated.receipts
    for row in no_send:
        assert row.get("delivery_status") == "rejected", row
        measured = str(row.get("actual_technical_bytes_digest") or "")
        assert measured, row
        assert measured != _g7_page_digest(mutated_manifest, row), (
            "no-send 回执不得把计划里的存储摘要写成本次实测"
        )


def test_g7_attempt_without_a_request_publishes_no_receipt_and_no_stored_digest(
    tmp_path: Path,
) -> None:
    """G7：请求根本没构造出来时不发行回执 —— 不得把计划存储摘要写成本次实测。"""

    execution, calls, _manifest, _plan = _g7_run(
        ledger_root=tmp_path / "no-caller", caller_available=False
    )
    assert calls == []
    assert execution.receipts == (), execution.receipts
    assert execution.actual_main_calls == 0
    assert execution.accepted_packages == ()
    assert any(
        "formalizer_request_error" in str(item) for item in execution.task_failures
    ), execution.task_failures
    # reader：没有任何回执可以冒充"页材料已验证"；唯一断言失败是诚实的"计划调用未发生"。
    assert not any(
        "actual_page_bytes" in str(item) for item in execution.assertion_failures
    ), execution.assertion_failures
    assert any(
        "actual_main_calls_mismatch" in str(item)
        for item in execution.assertion_failures
    ), execution.assertion_failures


def test_g7_verified_cache_reuse_does_not_resend_or_reseal(tmp_path: Path) -> None:
    """G7：已验证缓存复用不重发；复用沿用原回执，不新造一条实测记录。"""

    ledger_root = tmp_path / "ledger"
    first, first_calls, _manifest, _plan = _g7_run(ledger_root=ledger_root)
    assert len(first_calls) == 1
    assert first.accepted_packages
    first_receipts = list(first.receipts)
    assert first_receipts

    second, second_calls, _manifest2, _plan2 = _g7_run(ledger_root=ledger_root)
    assert second_calls == [], "已验证缓存复用不得重发 provider 请求"
    assert second.accepted_packages, "复用必须恢复已接受公式包"
    assert second.actual_main_calls == 0
    assert set(second.trace.get("reused_invocation_ids") or ()) == {
        row["invocation_id"] for row in first_receipts
    }, second.trace
    # 复用沿用原回执字节，不重新封印成一条新的"本次实测"。
    assert [row.get("content_digest") for row in second.receipts] == [
        row.get("content_digest") for row in first_receipts
    ]
    assert second.assertion_failures == (), second.assertion_failures


def test_g7_sent_but_unmeasured_receipt_is_not_read_as_verified(
    tmp_path: Path,
) -> None:
    """G7：已发送但**无法实测**页材料的回执必须具名"未实测"，不得读成已验证。

    provider 在返回前改动 caller 看到的请求对象（删掉页材料）—— 这正是
    ``_inspect_actual_request`` 存在的理由。发送已经发生，所以不能撤单；能做的是：
    回执 rejected、actual 记为空（未实测）、reader 具名指出未实测，并且不产生任何可接受包。
    """

    from code2paper.agentic.formalization_agent import execute_formalizer_invocation_plan
    from code2paper.llm.client import LLMConfig, LLMProvider

    archive, obligation, manifest, plan, envelope = _g7_plan_and_material()
    calls: list[Any] = []

    def provider(_config, request):
        calls.append(request)
        payload = getattr(request, "input_payload", None)
        assert isinstance(payload, dict)
        payload.pop("technical_payload", None)
        raw = _g7_provider_row()
        return LLMResponse(
            text=raw, response_hash="sha256:g7-formalizer", finish_reason="stop"
        )

    execution = execute_formalizer_invocation_plan(
        plan=plan,
        workset_manifest=manifest,
        archive=archive,
        obligations_by_id={obligation.obligation_id: obligation},
        llm_config=LLMConfig(
            provider=LLMProvider.NONE, model="g7-offline", max_output_tokens=4096, cache=False
        ),
        caller=provider,
        max_attempts=1,
        ledger_root=tmp_path / "sent-unmeasured",
        budget_envelope=envelope,
        model_identity_digest=envelope.model_identity_digest,
        run_digest=archive.content_digest,
    )
    assert len(calls) == 1, "本次尝试确实越过了 caller 边界"
    assert execution.accepted_packages == ()
    sent = [row for row in execution.receipts if row.get("sent_to_caller") is True]
    assert sent, execution.receipts
    for row in sent:
        assert row.get("delivery_status") == "rejected", row
        assert str(row.get("actual_technical_bytes_digest") or "") == "", row
    assert any(
        "actual_page_bytes_unmeasured" in str(item)
        for item in execution.assertion_failures
    ), execution.assertion_failures
