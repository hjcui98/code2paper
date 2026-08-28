"""R4.5 tests for the equation claim compiler (R4.4).

Verifies that ``authorize_equation`` and ``compile_equation_claims``:

- reject equations that reference unknown or unsupported facts;
- reject equations whose expression cannot be reconstructed from a
  licensing predicate in the fact set (``expression_from_operations``);
- reject equations with LaTeX symbols that have no fact-operand binding
  (``symbols_bound_to_fact_operands``);
- reject bindings that reference a fact operand value not present on any
  selected fact;
- reject equations that silently drop fact conditions
  (``relation_and_guard_complete``);
- reject equations with a ``prose_claim_id`` link but no fact ids;
- reject duplicate canonical identities (same expression + facts + bindings);
- accept a minimal well-formed equation and emit an ``EquationClaimV1``.

R4.5 hard constraint: the equation compiler source MUST NOT contain
project-specific literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``,
``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from code2paper.agentic.equation_claims import (
    EquationAuthorizationReportV1,
    EquationClaimSetV1,
    EquationClaimV1,
    EquationProposalV1,
    EquationSymbolBindingV1,
    authorize_equation,
    compile_equation_claims,
    derive_equation_proposals_from_facts,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    SemanticStageGroupV1,
)
from code2paper.agentic.authoring_projection import build_authoring_projection
from code2paper.agentic.claim_verifier import ClaimVerificationReport
from code2paper.core.schemas import ClaimEvidenceMap, MethodEvidence


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"
_EVIDENCE_PACKET_DIGEST = "sha256:packets"


def _fact(
    *,
    fact_id: str,
    subject: str = "x",
    predicate: str = "computes_formula",
    object: str | list[str] = "y",
    conditions: list[str] | None = None,
    validation_status: str = "supported",
    validation_failures: list[str] | None = None,
) -> CodeFactV1:
    return CodeFactV1(
        fact_id=fact_id,
        subject=subject,
        predicate=predicate,  # type: ignore[arg-type]
        object=object,
        conditions=conditions or [],
        scope=f"sym:module:{subject}",
        direct_span_ids=["span:module.py:1:10"],
        relation_span_ids=[],
        relation_evidence_ids=[],
        exact_source_digest="sha256:exact",
        canonical_identity=f"sha256:identity:{fact_id}",
        validation_status=validation_status,  # type: ignore[arg-type]
        validation_failures=validation_failures or [],
    )


def _fact_set(facts: list[CodeFactV1]) -> CodeFactSetV1:
    payload = [f.model_dump(mode="json") for f in facts]
    digest = "sha256:" + hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return CodeFactSetV1(
        repo_snapshot_id=_REPO_SNAPSHOT_ID,
        project_tree_hash=_PROJECT_TREE_HASH,
        evidence_packet_digest=_EVIDENCE_PACKET_DIGEST,
        facts=facts,
        content_digest=digest,
    )


def _binding(
    *,
    symbol: str,
    fact_id: str = "fact-1",
    operand_role: str = "subject",
    operand_value: str = "x",
) -> EquationSymbolBindingV1:
    return EquationSymbolBindingV1(
        symbol=symbol,
        fact_id=fact_id,
        operand_role=operand_role,
        operand_value=operand_value,
    )


def _proposal(
    *,
    equation_id: str = "eq-1",
    expression: str = r"y = \sigma(x)",
    fact_ids: list[str] | None = None,
    bindings: list[EquationSymbolBindingV1] | None = None,
    conditions: list[str] | None = None,
    prose_claim_id: str = "",
) -> EquationProposalV1:
    if fact_ids is None:
        fact_ids = ["fact-1"]
    if bindings is None:
        bindings = [
            _binding(symbol="y", operand_role="object", operand_value="y"),
            _binding(symbol="x", operand_role="subject", operand_value="x"),
            _binding(symbol="\\sigma", operand_role="subject", operand_value="x"),
        ]
    return EquationProposalV1(
        equation_id=equation_id,
        expression=expression,
        prose_claim_id=prose_claim_id,
        fact_ids=fact_ids,
        proposed_symbol_bindings=bindings,
        conditions=conditions or [],
    )


# ---------------------------------------------------------------------------
# fact_ids_subset
# ---------------------------------------------------------------------------


class TestFactIdsSubset:
    def test_unknown_fact_is_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(fact_ids=["fact-unknown"])
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any("unknown_fact" in f for f in report.failures)

    def test_unsupported_fact_is_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", validation_status="rejected",
                  validation_failures=["weak_source_authority:..."])
        ])
        proposal = _proposal(fact_ids=["fact-1"])
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any("unsupported_fact" in f for f in report.failures)


# ---------------------------------------------------------------------------
# expression_from_operations
# ---------------------------------------------------------------------------


class TestExpressionFromOperations:
    def test_source_operator_derives_authorizable_equation(self) -> None:
        fact = _fact(
            fact_id="fact-add",
            object=["left_operand", "right_operand"],
        ).model_copy(update={"semantic_context": ["COMPUTE", "add"]})
        facts = _fact_set([fact])

        proposals = derive_equation_proposals_from_facts(facts)
        equations, reports = compile_equation_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )

        assert len(proposals) == 1
        assert all(report.authorized for report in reports)
        assert len(equations.equations) == 1
        equation = equations.equations[0]
        assert equation.expression == "x + y"
        assert equation.operation_descriptors == ["add", "computes_formula"]
        assert equation.exact_source_digests == ["sha256:exact"]

    def test_no_equation_licensing_predicate_rejected(self) -> None:
        # ``reads`` is not in ``_EQUATION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="reads")])
        proposal = _proposal(fact_ids=["fact-1"])
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any(
            "expression_not_reconstructable_from_operations" in f
            for f in report.failures
        )

    def test_compute_predicate_licenses_expression(self) -> None:
        # ``computes_formula`` is in ``_EQUATION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposal = _proposal(fact_ids=["fact-1"])
        equation, report = authorize_equation(proposal, facts)
        assert report.authorized
        assert equation is not None

    def test_aggregates_predicate_licenses_expression(self) -> None:
        # ``aggregates`` is in ``_EQUATION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="aggregates")])
        proposal = _proposal(
            fact_ids=["fact-1"],
            expression=r"y = \sum_i x_i",
            bindings=[
                _binding(symbol="y", operand_value="y"),
                _binding(symbol="\\sum", operand_value="x"),
                _binding(symbol="i", operand_value="x"),
                _binding(symbol="x", operand_value="x"),
            ],
        )
        equation, report = authorize_equation(proposal, facts)
        assert report.authorized
        assert equation is not None


# ---------------------------------------------------------------------------
# symbols_bound_to_fact_operands
# ---------------------------------------------------------------------------


class TestSymbolBinding:
    def test_unbound_symbol_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        # Bind only ``y`` and ``x``, leaving ``W`` unbound.
        proposal = _proposal(
            expression=r"y = W x + b",
            fact_ids=["fact-1"],
            bindings=[
                _binding(symbol="y", operand_value="y"),
                _binding(symbol="x", operand_value="x"),
                # W and b are intentionally unbound
            ],
        )
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any("unbound_symbols" in f for f in report.failures)

    def test_binding_referencing_unknown_fact_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposal = _proposal(
            fact_ids=["fact-1"],
            bindings=[
                _binding(symbol="y", fact_id="fact-1", operand_value="y"),
                _binding(symbol="x", fact_id="fact-unknown", operand_value="x"),
                _binding(symbol="\\sigma", fact_id="fact-1", operand_value="x"),
            ],
        )
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any(
            "binding_references_unknown_fact" in f
            for f in report.failures
        )

    def test_binding_operand_not_in_fact_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", subject="x", object="y",
                  predicate="computes_formula")
        ])
        proposal = _proposal(
            fact_ids=["fact-1"],
            bindings=[
                _binding(symbol="y", fact_id="fact-1", operand_value="y"),
                _binding(symbol="x", fact_id="fact-1", operand_value="x"),
                _binding(symbol="\\sigma", fact_id="fact-1",
                         operand_value="not_a_real_operand"),
            ],
        )
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any(
            "binding_operand_not_in_fact" in f
            for f in report.failures
        )

    def test_full_binding_accepted(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", subject="x", object="y",
                  predicate="computes_formula")
        ])
        proposal = _proposal(fact_ids=["fact-1"])
        equation, report = authorize_equation(proposal, facts)
        assert report.authorized
        assert equation is not None
        assert {b.symbol for b in equation.symbol_bindings} == {"x", "y", "\\sigma"}


# ---------------------------------------------------------------------------
# relation_and_guard_complete
# ---------------------------------------------------------------------------


class TestRelationAndGuardComplete:
    def test_dropped_condition_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["training_mode"],
                  predicate="computes_formula")
        ])
        proposal = _proposal(
            fact_ids=["fact-1"],
            conditions=[],  # missing training_mode
        )
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any("dropped_condition" in f for f in report.failures)

    def test_declared_condition_accepted(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["training_mode"],
                  predicate="computes_formula")
        ])
        proposal = _proposal(
            fact_ids=["fact-1"],
            conditions=["training_mode"],
        )
        equation, report = authorize_equation(proposal, facts)
        assert report.authorized
        assert equation is not None
        assert "training_mode" in equation.conditions


# ---------------------------------------------------------------------------
# prose_uses_same_fact_ids
# ---------------------------------------------------------------------------


class TestProseLink:
    def test_prose_link_without_facts_rejected(self) -> None:
        # ``prose_claim_id`` is set but ``fact_ids`` is empty.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposal = _proposal(
            fact_ids=[],
            prose_claim_id="claim-1",
            bindings=[],  # no facts -> no bindings
            expression=r"y = 0",
        )
        _, report = authorize_equation(proposal, facts)
        assert not report.authorized
        assert any("prose_link_without_facts" in f for f in report.failures)

    def test_prose_link_with_facts_accepted(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposal = _proposal(
            fact_ids=["fact-1"],
            prose_claim_id="claim-1",
        )
        equation, report = authorize_equation(proposal, facts)
        assert report.authorized
        assert equation is not None
        assert equation.prose_claim_id == "claim-1"


class TestProductionProjection:
    def _projection(self, equation_fact_ids: list[str]):
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        equations, reports = compile_equation_claims(
            [_proposal(prose_claim_id="claim-1", fact_ids=equation_fact_ids)],
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert reports[0].authorized
        claims = AtomicClaimSetV3(
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
            evidence_packet_digest=_EVIDENCE_PACKET_DIGEST,
            code_fact_digest=facts.content_digest,
            claims=[AtomicClaimV3(
                claim_id="claim-1",
                canonical_text="The implementation computes y from x.",
                fact_ids=["fact-1"],
                direct_evidence_ids=["span:module.py:1:10"],
                allowed_wording_boundary="The implementation computes y from x.",
                canonical_identity="sha256:claim-1",
            )],
            semantic_stage_groups=[SemanticStageGroupV1(
                stage_id="stage-1",
                name="Computation",
                purpose="Describe the exact operation.",
                ordered_claim_ids=["claim-1"],
            )],
            content_digest="sha256:claims",
        )
        packets = EvidencePacketSetV3(
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
            packets=[],
            content_digest=_EVIDENCE_PACKET_DIGEST,
        )
        evidence = MethodEvidence(
            project_id="fixture",
            method_name="Fixture",
            method_goal="Describe the computation.",
            implementation_scope="fixture",
        )
        return build_authoring_projection(
            method_evidence=evidence,
            claim_map=ClaimEvidenceMap(),
            verification=ClaimVerificationReport(),
            atomic_claims_v3=claims,
            evidence_packets_v3=packets,
            equation_claims_v1=equations,
        )

    def test_authorized_equation_enters_writer_projection(self) -> None:
        projection = self._projection(["fact-1"])
        assert [item["equation_id"] for item in projection.safe_equations] == ["eq-1"]
        assert "equation_claims_v1" in projection.source_digests


# ---------------------------------------------------------------------------
# compile_equation_claims (batch)
# ---------------------------------------------------------------------------


class TestCompileEquationClaims:
    def test_batch_returns_one_report_per_proposal(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", predicate="computes_formula"),
            _fact(fact_id="fact-2", predicate="reads"),
        ])
        proposals = [
            _proposal(equation_id="eq-a", fact_ids=["fact-1"]),
            _proposal(equation_id="eq-b", fact_ids=["fact-2"]),  # reads → no license
            _proposal(equation_id="eq-c", fact_ids=["fact-1"],
                      expression=r"z = x + y",
                      bindings=[
                          _binding(symbol="z", operand_value="y"),
                          _binding(symbol="x", operand_value="x"),
                          _binding(symbol="y", operand_value="y"),
                      ]),
        ]
        equation_set, reports = compile_equation_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert len(reports) == 3
        authorized_ids = {e.equation_id for e in equation_set.equations}
        # eq-b is rejected (no equation-licensing predicate), eq-c is rejected
        # because the proposal references ``y`` as an operand value but
        # ``fact-1`` exposes ``x`` and ``y`` as operands (subject=x,
        # object=y).  So eq-c should actually be authorized.  Let me verify:
        # the binding for ``z`` uses operand_value="y" which IS in fact-1
        # (object=y).  Same for ``y``.  ``x`` maps to operand_value="x"
        # (subject=x).  So eq-c IS authorized.
        assert "eq-a" in authorized_ids
        assert "eq-b" not in authorized_ids
        assert "eq-c" in authorized_ids
        # Some proposal is rejected.
        assert any(not r.authorized for r in reports)

    def test_equation_set_provenance_fields(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposals = [_proposal(fact_ids=["fact-1"])]
        equation_set, _ = compile_equation_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        assert equation_set.repo_snapshot_id == _REPO_SNAPSHOT_ID
        assert equation_set.project_tree_hash == _PROJECT_TREE_HASH
        assert equation_set.code_fact_digest == facts.content_digest
        assert equation_set.content_digest.startswith("sha256:")
        assert equation_set.schema_version == "1.0"
        assert equation_set.producer_version == "code2paper-equation-compiler-v1"


# ---------------------------------------------------------------------------
# Duplicate canonical identity
# ---------------------------------------------------------------------------


class TestDuplicateIdentity:
    def test_duplicate_expression_and_facts_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposals = [
            _proposal(equation_id="eq-a", fact_ids=["fact-1"]),
            _proposal(equation_id="eq-b", fact_ids=["fact-1"]),  # same identity
        ]
        equation_set, reports = compile_equation_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
        )
        # Only one equation survives.
        assert len(equation_set.equations) == 1
        assert equation_set.equations[0].equation_id == "eq-a"
        # The second report is a duplicate-identity failure.
        assert reports[0].authorized
        assert not reports[1].authorized
        assert any("duplicate_canonical_identity" in f for f in reports[1].failures)


# ---------------------------------------------------------------------------
# R4.5 hard constraint: no project-specific literals in source
# ---------------------------------------------------------------------------


def _strip_docstrings_and_comments(source: str) -> str:
    """Strip docstrings and comments so they don't trip the literal scan."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body[0].value.value = ""  # type: ignore[misc]
    cleaned = ast.unparse(tree)
    cleaned = "\n".join(
        re.sub(r"#.*$", "", line) for line in cleaned.splitlines()
    )
    return cleaned


class TestNoProjectSpecificLiterals:
    @pytest.fixture
    def source_text(self) -> str:
        path = (
            Path(__file__).resolve().parent.parent
            / "src" / "code2paper" / "agentic"
            / "equation_claims.py"
        )
        return path.read_text(encoding="utf-8")

    def test_no_f_rap_literal(self, source_text: str) -> None:
        cleaned = _strip_docstrings_and_comments(source_text)
        assert "F-RAP-" not in cleaned

    def test_no_c_rap_literal(self, source_text: str) -> None:
        cleaned = _strip_docstrings_and_comments(source_text)
        assert "C-RAP-" not in cleaned

    def test_no_ebcar_literal(self, source_text: str) -> None:
        cleaned = _strip_docstrings_and_comments(source_text)
        assert "EBCAR" not in cleaned

    def test_no_dyg_mamba_literal(self, source_text: str) -> None:
        cleaned = _strip_docstrings_and_comments(source_text)
        assert "DyG-Mamba" not in cleaned

    def test_no_linearrag_literal(self, source_text: str) -> None:
        cleaned = _strip_docstrings_and_comments(source_text)
        assert "LinearRAG" not in cleaned
