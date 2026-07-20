"""R4.5 tests for the generic claim compiler (R4.3).

Verifies that ``authorize_claim`` and ``compile_atomic_claims``:

- reject claims that reference unknown or unsupported facts;
- reject quantifier words without a licensing fact predicate;
- reject direction words without a ``COMPUTE``/``COMPARE`` fact;
- reject claims that silently drop fact conditions;
- reject claims that merge contradictory conditions (``X`` vs ``not X``);
- reject duplicate canonical identities (same text + same fact ids);
- reject ``unsupported_author_fragments`` that contain implementation
  predicates;
- reject stage-introduction claims without any facts;
- reject claims with an empty ``allowed_wording_boundary``;
- accept a minimal well-formed claim and emit an ``AtomicClaimV3``.

R4.5 hard constraint: the claim compiler source MUST NOT contain
project-specific literals (``F-RAP-*``, ``C-RAP-*``, ``EBCAR``,
``DyG-Mamba``, ``LinearRAG``).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from code2paper.agentic.evidence_compiler_v3 import (
    CodeFactSetV1,
    CodeFactV1,
)
from code2paper.agentic.generic_claim_compiler import (
    ClaimAuthorizationReportV1,
    ClaimProposalV1,
    authorize_claim,
    compile_atomic_claims,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_REPO_SNAPSHOT_ID = "repo:test-snapshot"
_PROJECT_TREE_HASH = "sha256:tree"
_EVIDENCE_PACKET_DIGEST = "sha256:packets"


def _fact(
    *,
    fact_id: str,
    subject: str = "sym:module.func",
    predicate: str = "reads",
    object: str | list[str] = "x",
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
        scope=subject,
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
    import hashlib
    import json

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


def _proposal(
    *,
    claim_id: str = "claim-1",
    canonical_text: str = "The function reads x.",
    proposed_fact_ids: list[str] | None = None,
    required_qualifiers: list[str] | None = None,
    unsupported_author_fragments: list[str] | None = None,
    allowed_wording_boundary: str = "may describe reading x from the input",
    claim_kind: str = "implementation_behavior",
    covers_obligation_ids: list[str] | None = None,
) -> ClaimProposalV1:
    if proposed_fact_ids is None:
        proposed_fact_ids = ["fact-1"]
    return ClaimProposalV1(
        claim_id=claim_id,
        canonical_text=canonical_text,
        claim_kind=claim_kind,
        proposed_fact_ids=proposed_fact_ids,
        covers_obligation_ids=covers_obligation_ids or [],
        required_qualifiers=required_qualifiers or [],
        unsupported_author_fragments=unsupported_author_fragments or [],
        allowed_wording_boundary=allowed_wording_boundary,
    )


# ---------------------------------------------------------------------------
# fact_ids_subset
# ---------------------------------------------------------------------------


class TestFactIdsSubset:
    def test_unknown_fact_is_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(proposed_fact_ids=["fact-unknown"])
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("unknown_fact" in f for f in report.failures)

    def test_unsupported_fact_is_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", validation_status="rejected",
                  validation_failures=["weak_source_authority:..."])
        ])
        proposal = _proposal(proposed_fact_ids=["fact-1"])
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("unsupported_fact" in f for f in report.failures)

    def test_supported_fact_is_accepted(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(proposed_fact_ids=["fact-1"])
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None
        assert claim.fact_ids == ["fact-1"]


# ---------------------------------------------------------------------------
# no_quantifier_expansion
# ---------------------------------------------------------------------------


class TestQuantifierExpansion:
    def test_quantifier_word_without_licensing_predicate_rejected(self) -> None:
        # ``reads`` is not in ``_QUANTIFIER_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="reads")])
        proposal = _proposal(
            canonical_text="The function always reads x.",
            proposed_fact_ids=["fact-1"],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("quantifier_without_licensing_fact" in f for f in report.failures)

    def test_quantifier_word_with_licensing_predicate_accepted(self) -> None:
        # ``filters_by`` is in ``_QUANTIFIER_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="filters_by")])
        proposal = _proposal(
            canonical_text="The function always filters x by score.",
            proposed_fact_ids=["fact-1"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None

    def test_multiple_quantifier_words_compound_failure(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1", predicate="reads")])
        proposal = _proposal(
            canonical_text="The function always reads all values.",
            proposed_fact_ids=["fact-1"],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        # Only one failure code is emitted per claim, but it lists both words.
        assert any("quantifier_without_licensing_fact" in f for f in report.failures)


# ---------------------------------------------------------------------------
# no_direction_expansion
# ---------------------------------------------------------------------------


class TestDirectionExpansion:
    def test_direction_word_without_licensing_predicate_rejected(self) -> None:
        # ``reads`` is not in ``_DIRECTION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="reads")])
        proposal = _proposal(
            canonical_text="The function increases the value.",
            proposed_fact_ids=["fact-1"],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("direction_without_licensing_fact" in f for f in report.failures)

    def test_direction_word_with_compute_predicate_accepted(self) -> None:
        # ``computes_formula`` is in ``_DIRECTION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="computes_formula")])
        proposal = _proposal(
            canonical_text="The function increases the score.",
            proposed_fact_ids=["fact-1"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None

    def test_direction_word_with_compare_predicate_accepted(self) -> None:
        # ``compares`` is in ``_DIRECTION_PREDICATES``.
        facts = _fact_set([_fact(fact_id="fact-1", predicate="compares")])
        proposal = _proposal(
            canonical_text="The output improves after the call.",
            proposed_fact_ids=["fact-1"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None


# ---------------------------------------------------------------------------
# no_condition_expansion (dropped guard)
# ---------------------------------------------------------------------------


class TestConditionExpansion:
    def test_dropped_condition_is_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["training_mode"])
        ])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
            required_qualifiers=[],  # missing training_mode
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("dropped_condition" in f for f in report.failures)

    def test_declared_condition_is_accepted(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["training_mode"])
        ])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
            required_qualifiers=["training_mode"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None
        assert "training_mode" in claim.required_qualifiers


# ---------------------------------------------------------------------------
# no_contradictory_conditions
# ---------------------------------------------------------------------------


class TestContradictoryConditions:
    def test_contradictory_conditions_rejected(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["training_mode"]),
            _fact(fact_id="fact-2", conditions=["not training_mode"]),
        ])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1", "fact-2"],
            required_qualifiers=["training_mode", "not training_mode"],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("contradictory_conditions" in f for f in report.failures)

    def test_non_contradictory_conditions_accepted(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1", conditions=["mode_a"]),
            _fact(fact_id="fact-2", conditions=["mode_b"]),
        ])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1", "fact-2"],
            required_qualifiers=["mode_a", "mode_b"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None


# ---------------------------------------------------------------------------
# canonical_identity_dedup
# ---------------------------------------------------------------------------


class TestCanonicalIdentityDedup:
    def test_duplicate_claim_text_and_facts_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal_a = _proposal(
            claim_id="claim-a",
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
        )
        proposal_b = _proposal(
            claim_id="claim-b",
            canonical_text="The function reads x.",  # same normalized text
            proposed_fact_ids=["fact-1"],  # same fact ids
        )
        seen: set[str] = set()
        claim_a, report_a = authorize_claim(proposal_a, facts, seen_identities=seen)
        claim_b, report_b = authorize_claim(proposal_b, facts, seen_identities=seen)
        assert report_a.authorized
        assert claim_a is not None
        assert not report_b.authorized
        assert any("duplicate_canonical_identity" in f for f in report_b.failures)

    def test_same_text_different_facts_accepted(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1"),
            _fact(fact_id="fact-2"),
        ])
        proposal_a = _proposal(
            claim_id="claim-a",
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
        )
        proposal_b = _proposal(
            claim_id="claim-b",
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-2"],  # different fact ids
        )
        seen: set[str] = set()
        claim_a, report_a = authorize_claim(proposal_a, facts, seen_identities=seen)
        claim_b, report_b = authorize_claim(proposal_b, facts, seen_identities=seen)
        assert report_a.authorized
        assert report_b.authorized
        assert claim_a is not None
        assert claim_b is not None
        assert claim_a.canonical_identity != claim_b.canonical_identity


# ---------------------------------------------------------------------------
# rationale_separated
# ---------------------------------------------------------------------------


class TestRationaleSeparated:
    def test_implementation_predicate_in_fragment_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
            unsupported_author_fragments=["it also calls the helper"],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any(
            "rationale_contains_implementation_predicate" in f
            for f in report.failures
        )

    def test_rationale_only_fragment_accepted(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
            unsupported_author_fragments=["this enables faster convergence"],
        )
        claim, report = authorize_claim(proposal, facts)
        assert report.authorized
        assert claim is not None


# ---------------------------------------------------------------------------
# stage_introduction_has_facts + missing_wording_boundary
# ---------------------------------------------------------------------------


class TestStageIntroductionAndBoundary:
    def test_stage_introduction_without_facts_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(
            canonical_text="Stage one.",
            proposed_fact_ids=[],
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("stage_introduction_without_facts" in f for f in report.failures)

    def test_missing_wording_boundary_rejected(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposal = _proposal(
            canonical_text="The function reads x.",
            proposed_fact_ids=["fact-1"],
            allowed_wording_boundary="",  # missing
        )
        _, report = authorize_claim(proposal, facts)
        assert not report.authorized
        assert any("missing_wording_boundary" in f for f in report.failures)


# ---------------------------------------------------------------------------
# compile_atomic_claims (batch)
# ---------------------------------------------------------------------------


class TestCompileAtomicClaims:
    def test_batch_returns_one_report_per_proposal(self) -> None:
        facts = _fact_set([
            _fact(fact_id="fact-1"),
            _fact(fact_id="fact-2"),
        ])
        proposals = [
            _proposal(claim_id="claim-a", proposed_fact_ids=["fact-1"]),
            _proposal(claim_id="claim-b", proposed_fact_ids=["fact-unknown"]),
            _proposal(claim_id="claim-c", proposed_fact_ids=["fact-2"]),
        ]
        claim_set, reports = compile_atomic_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
            evidence_packet_digest=_EVIDENCE_PACKET_DIGEST,
        )
        assert len(reports) == 3
        # Only authorized claims appear in the set.
        authorized_ids = {c.claim_id for c in claim_set.claims}
        assert authorized_ids == {"claim-a", "claim-c"}
        # The unknown-fact proposal is rejected.
        assert any(not r.authorized for r in reports)

    def test_claim_set_provenance_fields(self) -> None:
        facts = _fact_set([_fact(fact_id="fact-1")])
        proposals = [_proposal(proposed_fact_ids=["fact-1"])]
        claim_set, _ = compile_atomic_claims(
            proposals,
            facts,
            repo_snapshot_id=_REPO_SNAPSHOT_ID,
            project_tree_hash=_PROJECT_TREE_HASH,
            evidence_packet_digest=_EVIDENCE_PACKET_DIGEST,
        )
        assert claim_set.repo_snapshot_id == _REPO_SNAPSHOT_ID
        assert claim_set.project_tree_hash == _PROJECT_TREE_HASH
        assert claim_set.evidence_packet_digest == _EVIDENCE_PACKET_DIGEST
        assert claim_set.code_fact_digest == facts.content_digest
        assert claim_set.content_digest.startswith("sha256:")


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
    # Strip inline comments.
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
            / "generic_claim_compiler.py"
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
