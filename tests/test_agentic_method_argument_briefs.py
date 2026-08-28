"""WP-A tests for deterministic Method argument brief compilation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code2paper.agentic.equation_claims import EquationClaimSetV1, EquationClaimV1
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.method_argument_brief_compiler import (
    compile_method_argument_briefs,
    extract_license_keys,
    split_author_clauses,
)
from code2paper.agentic.method_argument_brief_models import MethodArgumentBriefV1
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
)
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.agentic.obligation_fact_alignment import ObligationCoverageReportV2


_DYG_ROOT = Path(__file__).resolve().parents[1] / ".tmp/c2p-stage1-canary/run-dyg/artifacts"


def _minimal_claims(*, claim_id: str, text: str, obligation_id: str, status: str = "supported"):
    return AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=text,
                fact_ids=["F1"],
                covers_obligation_ids=[obligation_id],
                direct_evidence_ids=["S1"],
                relation_evidence_ids=[],
                allowed_wording_boundary="bounded",
                canonical_identity=f"sha256:{claim_id}",
                status=status,
            )
        ],
        content_digest="sha256:claims",
    )


def _minimal_completeness(*, obligation_id: str, statement: str, status: str = "supported_by_repository"):
    return MethodCompletenessMatrixV1(
        items=(
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                role="implementation",
                statement=statement,
                status=status,
            ),
        ),
        content_digest="sha256:completeness",
    )


def _minimal_intent(*, obligation_id: str, author_text: str):
    return IntentObligationGraphV2(
        obligations=[
            {
                "obligation_id": obligation_id,
                "kind": "method_mainline",
                "priority": "must_cover",
                "source_field": "method_mainline",
                "author_text": author_text,
                "typed_behavior_targets": [],
            }
        ],
    )


def _minimal_spine(*, obligation_id: str, author_statement: str):
    return (
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title="Main mechanism",
            author_statement=author_statement,
            linked_obligation_ids=(obligation_id,),
            evidence_lane="repository_verified",
        ),
    )


def test_split_author_clauses_preserves_order_and_ids():
    obligation_id = "O-TEST-01"
    text = (
        "Encode node interactions with DyGMamba routing. "
        "Motivated by Ebbinghaus forgetting curve theory."
    )
    clauses = split_author_clauses(text, obligation_id)
    assert len(clauses) == 2
    assert clauses[0].clause_id == f"clause:{obligation_id}:0"
    assert clauses[1].clause_id == f"clause:{obligation_id}:1"
    assert all(clause.license == "unlicensed" for clause in clauses)


def test_supported_implementation_clause_licensed_motivation_unlicensed():
    obligation_id = "O-MECH-01"
    statement = (
        "Encode node interactions with DyGMamba routing and softmax gating. "
        "Motivated by Ebbinghaus forgetting curve theory."
    )
    claims = _minimal_claims(
        claim_id="C-ROUTE",
        text="DyGMamba.compute_src_dst_node_temporal_embeddings normalizes F.softmax routing logits.",
        obligation_id=obligation_id,
    )
    completeness = _minimal_completeness(obligation_id=obligation_id, statement=statement)
    intent = _minimal_intent(obligation_id=obligation_id, author_text=statement)
    spine = _minimal_spine(obligation_id=obligation_id, author_statement=statement)

    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )

    assert len(briefs.briefs) == 1
    brief = briefs.briefs[0]
    assert brief.licensed_wording != brief.author_statement
    assert "DyGMamba" in brief.licensed_wording or "softmax" in brief.licensed_wording.lower()
    motivation = next(
        clause for clause in brief.clauses if "Ebbinghaus" in clause.text
    )
    assert motivation.license == "unlicensed"
    implementation = next(
        clause for clause in brief.clauses if "DyGMamba" in clause.text
    )
    assert implementation.license == "positively_licensed"
    assert brief.may_enter_verified is False
    assert brief.requires_caveat is True
    assert brief.mechanism_draft.status == "empty"


def test_obligation_supported_does_not_license_every_clause():
    obligation_id = "O-MAIN-01"
    statement = (
        "Implement DyGMamba softmax routing for temporal embeddings. "
        "Inspired by Ebbinghaus forgetting dynamics."
    )
    claims = _minimal_claims(
        claim_id="C-MAIN",
        text="DyGMamba.compute softmax routing.",
        obligation_id=obligation_id,
    )
    completeness = _minimal_completeness(
        obligation_id=obligation_id,
        statement=statement,
        status="supported_by_repository",
    )
    intent = _minimal_intent(obligation_id=obligation_id, author_text=statement)
    spine = _minimal_spine(obligation_id=obligation_id, author_statement=statement)

    brief = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    ).briefs[0]

    assert completeness.items[0].status == "supported_by_repository"
    assert any(clause.license == "unlicensed" for clause in brief.clauses)
    assert brief.licensed_wording != brief.author_statement


def test_author_statement_not_truncated_to_160_chars():
    long_statement = "Alpha " * 40 + "DyGMamba routing."
    obligation_id = "O-LONG-01"
    brief = MethodArgumentBriefV1(
        brief_id="brief:story:O-LONG-01",
        story_node_id="story:O-LONG-01",
        obligation_ids=(obligation_id,),
        author_statement=long_statement.strip(),
        completeness_statuses=("supported_by_repository",),
        clauses=(),
        mechanism_draft={
            "draft_id": "draft-1",
            "brief_id": "brief:story:O-LONG-01",
            "status": "empty",
        },
    )
    assert len(brief.author_statement) > 160


def test_require_planner_for_unlicensed_records_gap_without_planner():
    obligation_id = "O-GAP-01"
    statement = "Only author intent without repository keys."
    briefs = compile_method_argument_briefs(
        claims=_minimal_claims(
            claim_id="C1",
            text="unrelated.identifier_value",
            obligation_id=obligation_id,
        ),
        completeness=_minimal_completeness(obligation_id=obligation_id, statement=statement),
        coverage=None,
        intent_graph=_minimal_intent(obligation_id=obligation_id, author_text=statement),
        story_spine=_minimal_spine(obligation_id=obligation_id, author_statement=statement),
        require_planner_for_unlicensed=True,
        planner=None,
    )
    assert briefs.gaps
    assert briefs.gaps[0].gap_kind == "planner_required"


def test_extract_license_keys_filters_short_search_terms():
    keys = extract_license_keys(
        "module.process_input uses softmax routing",
        extra_stop_words=frozenset({"input"}),
    )
    assert "input" not in keys
    assert "softmax" in keys
    assert "routing" in keys


@pytest.mark.skipif(not _DYG_ROOT.is_dir(), reason="frozen DyG artifacts unavailable")
def test_frozen_dyg_mainline_brief_shape():
    claims = AtomicClaimSetV3.model_validate_json(
        (_DYG_ROOT / "atomic_claims_v3.json").read_text(encoding="utf-8")
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        (_DYG_ROOT / "method_completeness_matrix_v1.json").read_text(encoding="utf-8")
    )
    coverage = ObligationCoverageReportV2.model_validate_json(
        (_DYG_ROOT / "obligation_coverage_v2.json").read_text(encoding="utf-8")
    )
    intent = IntentObligationGraphV2.model_validate_json(
        (_DYG_ROOT / "intent_obligation_graph_v2.json").read_text(encoding="utf-8")
    )
    from code2paper.agentic.intent_compiler_v2 import build_story_spine_from_intent_graph

    spine = build_story_spine_from_intent_graph(intent, claim_set=claims)
    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=coverage,
        intent_graph=intent,
        story_spine=spine,
    )
    mainline_id = next(
        item.obligation_id
        for item in completeness.items
        if item.obligation_id.startswith("O-METHOD-MAINLINE")
    )
    mainline_brief = next(
        brief for brief in briefs.briefs if mainline_id in brief.obligation_ids
    )
    mainline_statement = next(
        item.statement
        for item in completeness.items
        if item.obligation_id == mainline_id
    )
    assert mainline_brief.licensed_wording != mainline_statement
    ebbinghaus = [
        clause for clause in mainline_brief.clauses if "Ebbinghaus" in clause.text
    ]
    assert ebbinghaus
    assert all(clause.license == "unlicensed" for clause in ebbinghaus)
    assert mainline_brief.may_enter_verified is False
    assert mainline_brief.claim_ids
    assert mainline_brief.span_ids
    assert len(mainline_brief.author_statement) > 160
    licensed_clauses = [
        clause for clause in mainline_brief.clauses
        if clause.license == "positively_licensed"
    ]
    for clause in licensed_clauses:
        bound_text = " ".join(
            claim.canonical_text
            for claim in claims.claims
            if claim.claim_id in clause.bound_claim_ids
        ).casefold()
        assert "softmax" not in bound_text or "softmax" in clause.text.casefold()
        assert "pad_sequences" not in bound_text or "pad" in clause.text.casefold()


@pytest.mark.skipif(not _DYG_ROOT.is_dir(), reason="frozen DyG artifacts unavailable")
def test_frozen_dyg_writer_view_includes_evidence_claim_texts():
    from code2paper.agentic.intent_compiler_v2 import build_story_spine_from_intent_graph
    from code2paper.agentic.writer_view_projection import build_writer_view_from_argument_briefs

    claims = AtomicClaimSetV3.model_validate_json(
        (_DYG_ROOT / "atomic_claims_v3.json").read_text(encoding="utf-8")
    )
    completeness = MethodCompletenessMatrixV1.model_validate_json(
        (_DYG_ROOT / "method_completeness_matrix_v1.json").read_text(encoding="utf-8")
    )
    coverage = ObligationCoverageReportV2.model_validate_json(
        (_DYG_ROOT / "obligation_coverage_v2.json").read_text(encoding="utf-8")
    )
    intent = IntentObligationGraphV2.model_validate_json(
        (_DYG_ROOT / "intent_obligation_graph_v2.json").read_text(encoding="utf-8")
    )
    spine = build_story_spine_from_intent_graph(intent, claim_set=claims)
    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=coverage,
        intent_graph=intent,
        story_spine=spine,
    )
    mainline_brief = next(
        brief for brief in briefs.briefs
        if brief.claim_ids and brief.span_ids
    )
    claim_by_id = {claim.claim_id: claim for claim in claims.claims}
    view = build_writer_view_from_argument_briefs(
        heading="Method",
        reader_question="How does it work?",
        section_goal="Explain the mechanism.",
        briefs=[mainline_brief],
        callback_opportunities=[],
        claims_by_id=claim_by_id,
    )
    assert view.evidence_claim_texts
    assert {
        item.claim_id for item in view.evidence_claim_texts
    }.issubset(set(mainline_brief.claim_ids))
    assert mainline_brief.licensed_wording != mainline_brief.author_statement


def test_licensed_wording_cannot_smuggle_unlicensed_clause():
    with pytest.raises(ValidationError):
        MethodArgumentBriefV1(
            brief_id="brief:bad",
            story_node_id="story:bad",
            obligation_ids=("O-BAD",),
            author_statement="Licensed part. Unlicensed part.",
            completeness_statuses=("supported_by_repository",),
            clauses=(
                {
                    "clause_id": "clause:O-BAD:0",
                    "text": "Licensed part.",
                    "license": "positively_licensed",
                    "bound_claim_ids": ("C1",),
                },
                {
                    "clause_id": "clause:O-BAD:1",
                    "text": "Unlicensed part.",
                    "license": "unlicensed",
                },
            ),
            licensed_wording="Licensed part. Unlicensed part.",
            claim_ids=("C1",),
            mechanism_draft={
                "draft_id": "draft-bad",
                "brief_id": "brief:bad",
                "status": "empty",
            },
            requires_caveat=True,
        )


def test_partial_completeness_forces_caveat_even_when_clauses_licensed():
    """Nine-state completeness must block verified even if clause license passes."""

    obligation_id = "O-PARTIAL-LICENSED"
    statement = "DyGMamba.compute applies softmax routing to temporal embeddings."
    claims = _minimal_claims(
        claim_id="C-ROUTE",
        text="DyGMamba.compute normalizes F.softmax routing logits.",
        obligation_id=obligation_id,
    )
    completeness = MethodCompletenessMatrixV1(
        items=(
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                role="implementation",
                statement=statement,
                status="partially_supported_by_repository",
                matched_fact_ids=("F1",),
                matched_span_ids=("S1",),
            ),
        ),
        content_digest="sha256:completeness",
    )
    intent = IntentObligationGraphV2(
        obligations=[
            {
                "obligation_id": obligation_id,
                "kind": "method_mainline",
                "priority": "must_cover",
                "source_field": "method_mainline",
                "author_text": statement,
                "typed_behavior_targets": [],
            }
        ],
    )
    spine = (
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title="Routing",
            author_statement=statement,
            linked_obligation_ids=(obligation_id,),
            evidence_lane="repository_partial",
        ),
    )
    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    brief = briefs.briefs[0]
    assert all(clause.license == "positively_licensed" for clause in brief.clauses)
    assert brief.requires_caveat is True
    assert brief.may_enter_verified is False


def test_equation_only_hit_yields_bound_equation_ids_without_claim_ids():
    """Equation symbol keys can positively license a clause without bound claims."""

    obligation_id = "O-EQ-ONLY"
    statement = (
        "DyGMambaRecurrence applies spectral_norm to the hidden state update. "
        "Motivated by cognitive forgetting theory."
    )
    claims = _minimal_claims(
        claim_id="C-CONFIG",
        text="Loads yaml configuration at startup.",
        obligation_id=obligation_id,
    )
    equations = EquationClaimSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        code_fact_digest="sha256:facts",
        equations=[
            EquationClaimV1(
                equation_id="equation:recurrence",
                expression="h_next = DyGMambaRecurrence(h, spectral_norm(W))",
                fact_ids=["F1"],
                symbol_bindings=[],
                canonical_identity="sha256:equation:recurrence",
                validation_status="supported",
            )
        ],
        content_digest="sha256:equations",
    )
    completeness = _minimal_completeness(obligation_id=obligation_id, statement=statement)
    intent = _minimal_intent(obligation_id=obligation_id, author_text=statement)
    spine = _minimal_spine(obligation_id=obligation_id, author_statement=statement)

    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        equations=equations,
    )
    brief = briefs.briefs[0]
    licensed = [
        clause for clause in brief.clauses if clause.license == "positively_licensed"
    ]
    assert licensed
    equation_clause = next(
        clause for clause in licensed if "DyGMambaRecurrence" in clause.text
    )
    assert equation_clause.bound_equation_ids == ("equation:recurrence",)
    assert not equation_clause.bound_claim_ids
    assert brief.licensed_wording != brief.author_statement
