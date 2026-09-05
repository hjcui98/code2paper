from __future__ import annotations

import pytest
from code2paper.agentic.formalization_agent import (
    MechanismFormulaObligationV1,
    MechanismFormulaPackageV2,
    adapt_mechanism_formula_package_to_legacy,
    build_deterministic_mechanism_formula_packages,
    compile_mechanism_formula_obligations,
    run_mechanism_formalizer,
    validate_mechanism_formula_package,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)


def _make_context(active_path: str = "active_default") -> MechanismContextV1:
    op1 = EvidenceOperationV1(
        operation_id="op:loss",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        source_span_id="span:loss:1",
        active_path_status=active_path,
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:loss",
        mechanism_id="mech_infonce",
        operation_nodes=(op1,),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:loss",
                disposition="absorbed_by_detail",
                detail_ids=("d:loss",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:loss:1",),
    )
    is_inactive = active_path in ("inactive_default", "unreachable")
    d1 = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_infonce",
        order_index=0,
        role="training_objective",
        importance="side_branch" if is_inactive else "core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="review_only" if is_inactive else "clean_candidate",
        semantic_atom="compute InfoNCE contrastive loss",
        predicate="compute_loss",
        operands=("logits", "labels"),
        result="loss",
        formalizable=True,
        source_operation_ids=("op:loss",),
        active_path_status=active_path,
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:loss",
                atom_kind="formal_relation",
                semantic_anchor="loss formula",
                source_operation_ids=("op:loss",),
            ),
        ),
    )
    return MechanismContextV1(
        mechanism_id="mech_infonce",
        mechanism_name="InfoNCE Loss",
        scientific_role="training_objective",
        reader_question="What is the optimization objective?",
        purpose="Contrastive learning objective",
        importance="side_branch" if is_inactive else "core",
        evidence_closure=closure,
        ordered_detail_ids=("d:loss",),
        details=(d1,),
    )


def test_validate_mechanism_formula_package_guards() -> None:
    ctx = _make_context()
    obs = compile_mechanism_formula_obligations(ctx, author_formula_expectations=("loss",))
    assert len(obs) == 1
    ob = obs[0]

    pkgs = build_deterministic_mechanism_formula_packages(
        context=ctx,
        obligations=obs,
        shared_payload_digest="sha256:shared_payload",
    )
    assert len(pkgs) == 1
    pkg = pkgs[0]
    assert pkg.latex == r"loss = \operatorname{compute_loss}(logits, labels)"
    assert pkg.evidence_authority == "repository_verified"

    # 1. Digest mismatch guard
    bad_digest_pkg = pkg.model_copy(update={"source_context_digest": "sha256:corrupted"})
    failures = validate_mechanism_formula_package(bad_digest_pkg, context=ctx)
    assert any("source_context_digest_mismatch" in f for f in failures)

    # 2. Shared payload digest mismatch guard
    bad_shared_pkg = pkg.model_copy(update={"shared_payload_digest": "sha256:wrong_payload"})
    failures = validate_mechanism_formula_package(bad_shared_pkg, context=ctx, shared_payload_digest="sha256:shared_payload")
    assert any("shared_payload_digest_mismatch" in f for f in failures)

    # 3. Mechanism ID mismatch guard
    bad_mech_pkg = pkg.model_copy(update={"mechanism_id": "other_mech"})
    failures = validate_mechanism_formula_package(bad_mech_pkg, context=ctx)
    assert any("mechanism_id_mismatch" in f for f in failures)

    # 4. Code plumbing guard (reject python / torch code)
    bad_code_pkg = pkg.model_copy(update={"latex": r"torch.matmul(logits, labels)"})
    failures = validate_mechanism_formula_package(bad_code_pkg, context=ctx)
    assert "formula_contains_unrendered_code" in failures

    # 5. Inactive path promotion guard
    inactive_ctx = _make_context(active_path="inactive_default")
    failures = validate_mechanism_formula_package(pkg, context=inactive_ctx)
    assert any("inactive_path_detail_promoted" in f for f in failures)
    assert any("inactive_path_operation_promoted" in f for f in failures)


def test_deterministic_generation_and_legacy_adaptation() -> None:
    ctx = _make_context()
    obs = compile_mechanism_formula_obligations(ctx, author_formula_expectations=("loss",))
    pkgs = build_deterministic_mechanism_formula_packages(context=ctx, obligations=obs)
    assert len(pkgs) == 1

    # Adapt to legacy SectionFormulaPackageV1
    legacy_pkg = adapt_mechanism_formula_package_to_legacy(
        pkgs[0],
        section_id="MA-S1",
        consumer_paragraph_id="MA-S1-P2",
    )
    assert legacy_pkg.package_id == pkgs[0].package_id
    assert legacy_pkg.section_id == "MA-S1"
    assert legacy_pkg.consumer_paragraph_id == "MA-S1-P2"
    assert legacy_pkg.authority_status == "code_verified"
    assert legacy_pkg.formula_lane == "repository_derived"
    assert legacy_pkg.review_status == "accepted"
    assert legacy_pkg.latex == pkgs[0].latex


def test_run_mechanism_formalizer_no_cross_mechanism_fallback() -> None:
    ctx = _make_context()
    obs = compile_mechanism_formula_obligations(ctx, author_formula_expectations=("loss",))
    
    pkgs, trace = run_mechanism_formalizer(
        context=ctx,
        obligations=obs,
        shared_payload="mock slice payload",
        shared_payload_digest="sha256:slice",
    )
    assert len(pkgs) == 1
    assert trace["deterministic_packages"] == 1
    assert trace["mechanism_id"] == "mech_infonce"
