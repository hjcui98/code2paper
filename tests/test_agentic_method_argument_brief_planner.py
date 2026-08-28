"""WP-C tests for the one-shot Mechanism Planner."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.method_argument_brief_compiler import (
    compile_method_argument_briefs,
    _stable_id,
)
from code2paper.agentic.method_argument_brief_models import ArgumentBriefGapV1, MechanismDraftV1
from code2paper.agentic.method_argument_brief_planner import (
    MechanismDraftProposalBatchV1,
    MechanismDraftProposalV1,
    StubMechanismDraftPlanner,
    _FragBinding,
    _validate_proposal,
    build_mechanism_draft_planner,
)
from code2paper.agentic.method_argument_models import MethodCompletenessItemV1, MethodCompletenessMatrixV1
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.llm.client import LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


def _minimal_claims(*, claim_id: str, text: str, obligation_id: str):
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
            )
        ],
        content_digest="sha256:claims",
    )


def _minimal_completeness(*, obligation_id: str, statement: str):
    return MethodCompletenessMatrixV1(
        items=(
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                role="implementation",
                statement=statement,
                status="supported_by_repository",
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


def _caveated_bundle():
    obligation_id = "O-PLAN-01"
    statement = (
        "Encode node interactions with DyGMamba routing and softmax gating. "
        "Motivated by Ebbinghaus forgetting curve theory."
    )
    claims = _minimal_claims(
        claim_id="C-ROUTE",
        text="DyGMamba.compute normalizes F.softmax routing logits.",
        obligation_id=obligation_id,
    )
    completeness = _minimal_completeness(obligation_id=obligation_id, statement=statement)
    intent = _minimal_intent(obligation_id=obligation_id, author_text=statement)
    spine = _minimal_spine(obligation_id=obligation_id, author_statement=statement)
    return claims, completeness, intent, spine


def test_build_frag_catalog_uses_equation_expression_field():
    from code2paper.agentic.equation_claims import EquationClaimV1
    from code2paper.agentic.method_argument_brief_models import MethodArgumentBriefV1
    from code2paper.agentic.method_argument_brief_planner import _build_frag_catalog

    brief = MethodArgumentBriefV1(
        brief_id="brief:eq",
        story_node_id="story:eq",
        obligation_ids=("O-EQ",),
        author_statement="Loss combines terms.",
        completeness_statuses=("supported_by_repository",),
        clauses=(),
        claim_ids=(),
        equation_ids=("EQ-1",),
        mechanism_draft={
            "draft_id": "draft-eq",
            "brief_id": "brief:eq",
            "status": "not_required",
        },
    )
    equation = EquationClaimV1(
        equation_id="EQ-1",
        expression=r"L = \alpha + \beta",
        fact_ids=["F1"],
        symbol_bindings=[],
        canonical_identity="sha256:eq",
        validation_status="supported",
    )
    lines, catalog, next_index = _build_frag_catalog(
        brief,
        claim_by_id={},
        equation_by_id={"EQ-1": equation},
    )
    assert lines == ["frag-1: equation EQ-1: L = \\alpha + \\beta"]
    assert catalog["frag-1"].equation_id == "EQ-1"
    assert next_index == 2


def test_validate_proposal_rejects_unknown_brief_and_frag():
    proposal = MechanismDraftProposalV1(
        brief_id="brief:missing",
        text="Draft text.",
        cited_frag_ids=("frag-99",),
    )
    draft, error = _validate_proposal(
        proposal,
        allowed_brief_ids={"brief:ok"},
        frag_catalog={},
    )
    assert draft is None
    assert "unknown brief_id" in error

    draft, error = _validate_proposal(
        MechanismDraftProposalV1(
            brief_id="brief:ok",
            text="Draft text.",
            cited_frag_ids=("frag-99",),
        ),
        allowed_brief_ids={"brief:ok"},
        frag_catalog={"frag-1": _FragBinding(frag_id="frag-1", claim_id="C1")},
    )
    assert draft is None
    assert "unknown frag id" in error


def test_stub_planner_writes_planner_filled_draft():
    claims, completeness, intent, spine = _caveated_bundle()
    base = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    target = next(brief for brief in base.briefs if brief.requires_caveat)
    draft = MechanismDraftV1(
        draft_id=_stable_id("draft", target.brief_id),
        brief_id=target.brief_id,
        text="Softmax routing combines neighbor embeddings before update.",
        cited_claim_ids=target.claim_ids[:1],
        status="planner_filled",
    )
    stub = StubMechanismDraftPlanner(drafts_by_brief_id={target.brief_id: draft})
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=stub,
    )
    assert filled.planner_used is True
    updated = next(brief for brief in filled.briefs if brief.brief_id == target.brief_id)
    assert updated.mechanism_draft.status == "planner_filled"
    assert updated.mechanism_draft.cited_claim_ids == target.claim_ids[:1]


def test_no_unlicensed_briefs_keep_planner_used_false():
    obligation_id = "O-ALL-01"
    statement = "DyGMamba routing uses softmax gating."
    claims = _minimal_claims(
        claim_id="C-ROUTE",
        text="DyGMamba.compute normalizes F.softmax routing logits.",
        obligation_id=obligation_id,
    )
    completeness = _minimal_completeness(obligation_id=obligation_id, statement=statement)
    intent = _minimal_intent(obligation_id=obligation_id, author_text=statement)
    spine = _minimal_spine(obligation_id=obligation_id, author_statement=statement)

    def _fail_if_called(_briefs):
        raise AssertionError("planner must not run when all clauses are licensed")

    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=_fail_if_called,
        require_planner_for_unlicensed=True,
    )
    assert briefs.planner_used is False
    assert not briefs.gaps


def test_planner_failure_records_gap_without_fabricated_draft():
    claims, completeness, intent, spine = _caveated_bundle()
    target_brief_id = "brief:story:O-PLAN-01"

    class _RecordingPlanner:
        def __init__(self):
            self.gaps: list[ArgumentBriefGapV1] = []

        def __call__(self, briefs):
            self.gaps.append(ArgumentBriefGapV1(
                gap_kind="planner_failed",
                brief_id=briefs[0].brief_id,
                message="unknown frag id:frag-99",
            ))
            return ()

    recorder = _RecordingPlanner()
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=recorder,
    )
    assert filled.gaps
    assert filled.gaps[0].gap_kind == "planner_failed"
    brief = next(b for b in filled.briefs if b.brief_id == target_brief_id)
    assert brief.mechanism_draft.status == "empty"


def test_live_planner_rejects_out_of_closure_frag_ids():
    claims, completeness, intent, spine = _caveated_bundle()
    target = next(
        brief
        for brief in compile_method_argument_briefs(
            claims=claims,
            completeness=completeness,
            coverage=None,
            intent_graph=intent,
            story_spine=spine,
        ).briefs
        if brief.requires_caveat
    )
    batch = MechanismDraftProposalBatchV1(
        drafts=(
            MechanismDraftProposalV1(
                brief_id=target.brief_id,
                text="Routing applies softmax over neighbor logits.",
                cited_frag_ids=("frag-999",),
            ),
        )
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps(batch.model_dump(mode="json")),
            response_hash="sha256:planner-test",
            finish_reason="stop",
        )

    planner = build_mechanism_draft_planner(
        LLMConfig(provider=LLMProvider.NONE, model="fixture", cache=False),
        claims=claims,
        llm_caller=caller,
    )
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=planner,
    )
    assert filled.gaps
    assert any(gap.gap_kind == "planner_failed" for gap in filled.gaps)
    updated = next(brief for brief in filled.briefs if brief.brief_id == target.brief_id)
    assert updated.mechanism_draft.status == "empty"


def test_live_planner_accepts_closed_set_response():
    claims, completeness, intent, spine = _caveated_bundle()
    target = next(
        brief
        for brief in compile_method_argument_briefs(
            claims=claims,
            completeness=completeness,
            coverage=None,
            intent_graph=intent,
            story_spine=spine,
        ).briefs
        if brief.requires_caveat
    )
    batch = MechanismDraftProposalBatchV1(
        drafts=(
            MechanismDraftProposalV1(
                brief_id=target.brief_id,
                text="Routing applies softmax over neighbor logits.",
                cited_frag_ids=("frag-1",),
                caveat="Author motivation remains unverified.",
            ),
        )
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps(batch.model_dump(mode="json")),
            response_hash="sha256:planner-ok",
            finish_reason="stop",
        )

    planner = build_mechanism_draft_planner(
        LLMConfig(provider=LLMProvider.NONE, model="fixture", cache=False),
        claims=claims,
        llm_caller=caller,
    )
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=planner,
    )
    assert not filled.gaps
    updated = next(brief for brief in filled.briefs if brief.brief_id == target.brief_id)
    assert updated.mechanism_draft.status == "planner_filled"
    assert updated.mechanism_draft.cited_claim_ids == ("C-ROUTE",)


def test_global_frag_catalog_does_not_collide_across_caveat_briefs():
    claims, completeness, intent, spine = _caveated_bundle()
    obligation_b = "O-PLAN-02"
    statement_b = (
        "Aggregate neighbor states with attention pooling. "
        "Motivated by Hebbian learning theory."
    )
    claims_b = _minimal_claims(
        claim_id="C-POOL",
        text="DyGMamba.pool aggregates neighbor embeddings with attention weights.",
        obligation_id=obligation_b,
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id=claims.repo_snapshot_id,
        project_tree_hash=claims.project_tree_hash,
        evidence_packet_digest=claims.evidence_packet_digest,
        code_fact_digest=claims.code_fact_digest,
        claims=[*claims.claims, *claims_b.claims],
        content_digest="sha256:claims-two",
    )
    completeness = MethodCompletenessMatrixV1(
        items=(
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id=obligation_b,
                role="implementation",
                statement=statement_b,
                status="supported_by_repository",
            ),
        ),
        content_digest="sha256:completeness-two",
    )
    intent = IntentObligationGraphV2(
        obligations=[
            *intent.obligations,
            {
                "obligation_id": obligation_b,
                "kind": "method_mainline",
                "priority": "must_cover",
                "source_field": "method_mainline",
                "author_text": statement_b,
                "typed_behavior_targets": [],
            },
        ],
    )
    spine = (
        *spine,
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_b}",
            title="Pooling",
            author_statement=statement_b,
            linked_obligation_ids=(obligation_b,),
            evidence_lane="repository_verified",
        ),
    )
    compiled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    caveat_briefs = tuple(
        brief for brief in compiled.briefs if brief.requires_caveat
    )
    assert len(caveat_briefs) >= 2

    from code2paper.agentic.method_argument_brief_planner import _brief_envelope

    claim_by_id = {item.claim_id: item for item in claims.claims}
    frag_catalog: dict[str, _FragBinding] = {}
    next_index = 1
    frag_ids_by_brief: dict[str, list[str]] = {}
    for brief in caveat_briefs:
        envelope, brief_catalog, next_index = _brief_envelope(
            brief,
            claim_by_id=claim_by_id,
            equation_by_id={},
            start_index=next_index,
        )
        frag_catalog.update(brief_catalog)
        frag_ids_by_brief[brief.brief_id] = [
            line.split(":", 1)[0]
            for line in envelope["fragments"]
        ]

    first_frag_ids = set(frag_ids_by_brief[caveat_briefs[0].brief_id])
    second_frag_ids = set(frag_ids_by_brief[caveat_briefs[1].brief_id])
    assert not first_frag_ids.intersection(second_frag_ids)
    assert frag_catalog["frag-1"].claim_id == "C-ROUTE"
    pool_frag = next(
        frag_id
        for frag_id in second_frag_ids
        if frag_catalog[frag_id].claim_id == "C-POOL"
    )
    assert pool_frag != "frag-1"


def test_two_caveat_brief_planner_accepts_distinct_frag_citations():
    claims, completeness, intent, spine = _caveated_bundle()
    obligation_b = "O-PLAN-02"
    statement_b = (
        "Aggregate neighbor states with attention pooling. "
        "Motivated by Hebbian learning theory."
    )
    claims_b = _minimal_claims(
        claim_id="C-POOL",
        text="DyGMamba.pool aggregates neighbor embeddings with attention weights.",
        obligation_id=obligation_b,
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id=claims.repo_snapshot_id,
        project_tree_hash=claims.project_tree_hash,
        evidence_packet_digest=claims.evidence_packet_digest,
        code_fact_digest=claims.code_fact_digest,
        claims=[*claims.claims, *claims_b.claims],
        content_digest="sha256:claims-two",
    )
    completeness = MethodCompletenessMatrixV1(
        items=(
            *completeness.items,
            MethodCompletenessItemV1(
                obligation_id=obligation_b,
                role="implementation",
                statement=statement_b,
                status="supported_by_repository",
            ),
        ),
        content_digest="sha256:completeness-two",
    )
    intent = IntentObligationGraphV2(
        obligations=[
            *intent.obligations,
            {
                "obligation_id": obligation_b,
                "kind": "method_mainline",
                "priority": "must_cover",
                "source_field": "method_mainline",
                "author_text": statement_b,
                "typed_behavior_targets": [],
            },
        ],
    )
    spine = (
        *spine,
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_b}",
            title="Pooling",
            author_statement=statement_b,
            linked_obligation_ids=(obligation_b,),
            evidence_lane="repository_verified",
        ),
    )
    compiled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    caveat_briefs = [brief for brief in compiled.briefs if brief.requires_caveat]
    assert len(caveat_briefs) >= 2
    from code2paper.agentic.method_argument_brief_planner import _brief_envelope

    claim_by_id = {item.claim_id: item for item in claims.claims}
    next_index = 1
    route_frag = ""
    pool_frag = ""
    for brief in caveat_briefs:
        _envelope, brief_catalog, next_index = _brief_envelope(
            brief,
            claim_by_id=claim_by_id,
            equation_by_id={},
            start_index=next_index,
        )
        for frag_id, binding in brief_catalog.items():
            if binding.claim_id == "C-ROUTE":
                route_frag = frag_id
            if binding.claim_id == "C-POOL":
                pool_frag = frag_id
    assert route_frag and pool_frag and route_frag != pool_frag
    batch = MechanismDraftProposalBatchV1(
        drafts=(
            MechanismDraftProposalV1(
                brief_id=caveat_briefs[0].brief_id,
                text="Routing applies softmax over neighbor logits.",
                cited_frag_ids=(route_frag,),
                caveat="Author motivation remains unverified.",
            ),
            MechanismDraftProposalV1(
                brief_id=caveat_briefs[1].brief_id,
                text="Pooling aggregates neighbor embeddings.",
                cited_frag_ids=(pool_frag,),
                caveat="Hebbian motivation remains unverified.",
            ),
        )
    )

    def caller(_config, _request):
        return LLMResponse(
            text=json.dumps(batch.model_dump(mode="json")),
            response_hash="sha256:planner-two-briefs",
            finish_reason="stop",
        )

    planner = build_mechanism_draft_planner(
        LLMConfig(provider=LLMProvider.NONE, model="fixture", cache=False),
        claims=claims,
        llm_caller=caller,
    )
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=planner,
    )
    assert not filled.gaps
    by_id = {brief.brief_id: brief for brief in filled.briefs}
    assert by_id[caveat_briefs[0].brief_id].mechanism_draft.cited_claim_ids == ("C-ROUTE",)
    assert by_id[caveat_briefs[1].brief_id].mechanism_draft.cited_claim_ids == ("C-POOL",)


def _many_caveat_briefs(count: int = 8):
    claims = []
    completeness_items = []
    intent_obligations = []
    spine = []
    for index in range(count):
        obligation_id = f"O-MANY-{index:02d}"
        statement = (
            f"Module{index} aggregates states with attention pooling. "
            f"Motivated by theory{index}."
        )
        claim_id = f"C-MANY-{index:02d}"
        claims.append(
            AtomicClaimV3(
                claim_id=claim_id,
                canonical_text=(
                    f"Module{index}.pool aggregates embeddings with attention weights."
                ),
                fact_ids=[f"F{index}"],
                covers_obligation_ids=[obligation_id],
                direct_evidence_ids=[f"S{index}"],
                relation_evidence_ids=[],
                allowed_wording_boundary="bounded",
                canonical_identity=f"sha256:{claim_id}",
            )
        )
        completeness_items.append(
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                role="implementation",
                statement=statement,
                status="supported_by_repository",
            )
        )
        intent_obligations.append({
            "obligation_id": obligation_id,
            "kind": "method_mainline",
            "priority": "must_cover",
            "source_field": "method_mainline",
            "author_text": statement,
            "typed_behavior_targets": [],
        })
        spine.append(
            AuthorStoryNodeV1(
                story_node_id=f"story:{obligation_id}",
                title=f"Module {index}",
                author_statement=statement,
                linked_obligation_ids=(obligation_id,),
                evidence_lane="repository_verified",
            )
        )
    claim_set = AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=claims,
        content_digest="sha256:claims-many",
    )
    completeness = MethodCompletenessMatrixV1(
        items=tuple(completeness_items),
        content_digest="sha256:completeness-many",
    )
    intent = IntentObligationGraphV2(obligations=intent_obligations)
    return claim_set, completeness, intent, tuple(spine)


def test_planner_parse_failure_records_trace_without_draft():
    claims, completeness, intent, spine = _many_caveat_briefs(count=8)
    compiled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    caveat_briefs = [brief for brief in compiled.briefs if brief.requires_caveat]
    assert len(caveat_briefs) >= 8

    def caller(_config, _request):
        return LLMResponse(
            text="not json at all " * 400,
            response_hash="sha256:planner-bad",
            finish_reason="stop",
        )

    planner = build_mechanism_draft_planner(
        LLMConfig(provider=LLMProvider.NONE, model="fixture", cache=False),
        claims=claims,
        llm_caller=caller,
    )
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=planner,
    )
    assert filled.planner_used is True
    assert filled.planner_call_traces
    assert any(trace.get("parse_error") for trace in filled.planner_call_traces)
    assert all(
        brief.mechanism_draft.status == "empty"
        for brief in filled.briefs
        if brief.requires_caveat
    )
    assert len(filled.gaps) >= len(caveat_briefs)


def test_planner_batch_accepts_many_caveat_briefs():
    claims, completeness, intent, spine = _many_caveat_briefs(count=8)
    compiled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    caveat_briefs = [brief for brief in compiled.briefs if brief.requires_caveat]
    from code2paper.agentic.method_argument_brief_planner import _brief_envelope

    claim_by_id = {item.claim_id: item for item in claims.claims}
    frag_by_brief: dict[str, str] = {}
    next_index = 1
    for brief in caveat_briefs:
        _envelope, catalog, next_index = _brief_envelope(
            brief,
            claim_by_id=claim_by_id,
            equation_by_id={},
            start_index=next_index,
        )
        for frag_id, binding in catalog.items():
            if binding.claim_id:
                frag_by_brief[brief.brief_id] = frag_id
                break
    drafts = tuple(
        MechanismDraftProposalV1(
            brief_id=brief.brief_id,
            text=f"Pooling aggregates embeddings for module {index}.",
            cited_frag_ids=(frag_by_brief[brief.brief_id],),
            caveat="Author motivation remains unverified.",
        )
        for index, brief in enumerate(caveat_briefs)
    )
    batch = MechanismDraftProposalBatchV1(drafts=drafts)
    call_count = {"value": 0}

    def caller(_config, _request):
        call_count["value"] += 1
        return LLMResponse(
            text=json.dumps(batch.model_dump(mode="json")),
            response_hash=f"sha256:planner-many-{call_count['value']}",
            finish_reason="stop",
        )

    planner = build_mechanism_draft_planner(
        LLMConfig(provider=LLMProvider.NONE, model="fixture", cache=False),
        claims=claims,
        llm_caller=caller,
    )
    filled = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
        planner=planner,
    )
    assert not filled.gaps
    for brief in caveat_briefs:
        updated = next(item for item in filled.briefs if item.brief_id == brief.brief_id)
        assert updated.mechanism_draft.status == "planner_filled"


def test_formula_like_draft_requires_caveat_for_delta_t_sentence():
    proposal = MechanismDraftProposalV1(
        brief_id="brief:delta",
        text="Delta_t = A * x with spectral normalization.",
        cited_frag_ids=("frag-1",),
        caveat="",
    )
    draft, error = _validate_proposal(
        proposal,
        allowed_brief_ids={"brief:delta"},
        frag_catalog={"frag-1": _FragBinding(frag_id="frag-1", claim_id="C-DELTA")},
    )
    assert draft is None
    assert "caveat" in error
