from __future__ import annotations

from pathlib import Path

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.intent_obligations import (
    build_authoring_obligation_coverage,
    compile_intent_obligation_graph,
)
from code2paper.agentic.graph_evidence_nodes import _obligation_repair_focus
from code2paper.agentic.graph_routes import route_after_authoring_planner
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.retrieval import SymbolIndexEntry, SymbolIndexReport
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ProjectedClaim


def _summary() -> AuthorIntentSummary:
    return AuthorIntentSummary(
        project_goal="Predict primitive importance without using paper text as evidence.",
        method_goal="Score and prune low-importance primitives.",
        implementation_scope="Provided inference entrypoint.",
        method_mainline="Load a predictor, compute per-primitive scores, and prune low-ranked primitives.",
        story_order=["Feature construction", "Score prediction", "Pruning"],
        priority_files=["prune_percent.py"],
        module_roles=[
            "utils/net_utils.py::PrunePredictor: predict one importance score per primitive",
        ],
        pipeline_steps=[
            "Feature construction: build per-primitive descriptors",
            "Pruning: sort scores, construct a mask, and remove low-ranked primitives",
        ],
        design_intents=["Avoid rendering in the scoped inference function."],
        innovation_claims=["Three training losses learn the importance predictor."],
    )


def _projection(*, include_pruning: bool = False) -> AuthoringInputProjection:
    claims = [
        ProjectedClaim(
            claim_id="C-FEATURE",
            claim_text="The inference entrypoint builds a per-primitive descriptor.",
            support_status="supported",
            direct_evidence_ids=["E1"],
            supported_fragment="The inference entrypoint builds a per-primitive descriptor.",
            allowed_wording_boundary="The inference entrypoint builds a per-primitive descriptor.",
            input_digest="sha256:feature",
        ),
        ProjectedClaim(
            claim_id="C-SCORE",
            claim_text="The loaded predictor computes one importance score for each primitive.",
            support_status="supported",
            direct_evidence_ids=["E2"],
            supported_fragment="The loaded predictor computes one importance score for each primitive.",
            allowed_wording_boundary="The loaded predictor computes one importance score for each primitive.",
            input_digest="sha256:score",
        ),
    ]
    if include_pruning:
        claims.append(
            ProjectedClaim(
                claim_id="C-PRUNE",
                claim_text="The inference path sorts scores, constructs a boolean mask, and removes the selected primitives.",
                support_status="supported",
                direct_evidence_ids=["E3"],
                supported_fragment="The inference path sorts scores, constructs a boolean mask, and removes the selected primitives.",
                allowed_wording_boundary="The inference path sorts scores, constructs a boolean mask, and removes the selected primitives.",
                input_digest="sha256:prune",
            )
        )
    return AuthoringInputProjection(
        project_id="rap",
        method_name="RAP",
        author_goal="Organize supported claims.",
        implementation_scope="Provided inference entrypoint.",
        projected_claims=claims,
        stage_packets=[{
            "stage_id": "S1",
            "name": "Feature construction and score prediction",
            "purpose": "; ".join(claim.supported_fragment for claim in claims),
            "stage_claim": "; ".join(claim.supported_fragment for claim in claims),
            "claim_ids": [claim.claim_id for claim in claims],
            "evidence_span_ids": [item for claim in claims for item in claim.direct_evidence_ids],
        }],
        projection_digest="sha256:projection",
    )


def test_intent_compiler_separates_method_obligations_from_organization_and_rationale() -> None:
    graph = compile_intent_obligation_graph(_summary())

    assert graph.content_digest.startswith("sha256:")
    assert any(item.kind == "method_mainline" and item.priority == "must_cover" for item in graph.obligations)
    assert len([item for item in graph.obligations if item.kind == "stage" and item.priority == "must_cover"]) == 2
    assert all(item.priority == "preference" for item in graph.obligations if item.kind == "organization")
    assert all(item.priority == "verify_only" for item in graph.obligations if item.kind in {"rationale_check", "high_risk_claim"})
    predictor = next(item for item in graph.obligations if item.kind == "component")
    assert "utils/net_utils.py" in predictor.candidate_paths
    assert all(item.status == "unresolved" for item in graph.obligations)


def test_authoring_coverage_requests_targeted_repair_for_missing_must_cover_pruning() -> None:
    graph = compile_intent_obligation_graph(_summary())
    report = build_authoring_obligation_coverage(graph, _projection(include_pruning=False))

    pruning = next(
        item
        for item in report.items
        if item.kind == "stage" and "Pruning" in next(
            obligation.author_text for obligation in graph.obligations if obligation.obligation_id == item.obligation_id
        )
    )
    assert pruning.status in {"unresolved", "partially_covered"}
    assert pruning.obligation_id in report.unresolved_must_cover_ids
    assert report.recommended_next == "targeted_evidence_repair"
    assert report.projected_claim_count == 2
    assert report.unique_projected_claim_count == 2


def test_authoring_coverage_never_treats_author_training_loss_text_as_a_writable_claim() -> None:
    graph = compile_intent_obligation_graph(_summary())
    report = build_authoring_obligation_coverage(graph, _projection(include_pruning=True))

    loss_obligation = next(item for item in graph.obligations if item.kind == "high_risk_claim")
    loss_coverage = next(item for item in report.items if item.obligation_id == loss_obligation.obligation_id)
    assert loss_coverage.status == "unresolved"
    assert loss_coverage.projected_claim_ids == []


def test_unresolved_obligations_become_targeted_analysis_focus_and_graph_route() -> None:
    graph = compile_intent_obligation_graph(_summary())
    report = build_authoring_obligation_coverage(graph, _projection(include_pruning=False))
    symbol_index = SymbolIndexReport(
        project_root="/repo",
        indexed_files=1,
        indexed_symbols=1,
        candidates=[SymbolIndexEntry(
            path="prune_percent.py",
            symbol="prune_pure_feature",
            kind="function",
            start_line=1,
            end_line=40,
            docstring="Compute predictor scores, sort them, build a mask, and prune primitives.",
            score=4.0,
        )],
    )

    focus = _obligation_repair_focus(
        graph=graph,
        report=report,
        source_decision="coverage.json",
        symbol_index=symbol_index,
    )
    state = AgenticRunState(
        project_root=Path("."),
        out_root=Path("/tmp/code2paper-obligation-route-test"),
        next_node="analysis",
    )

    assert focus.mode == "obligation-evidence-repair-focus-v1"
    assert set(focus.focus_claim_ids) == set(report.unresolved_must_cover_ids)
    assert "prune_percent.py" in focus.priority_paths
    assert any("Pruning" in query for query in focus.claim_queries)
    assert any(
        candidate.symbol == "prune_pure_feature"
        for target in focus.claim_targets
        for candidate in target.candidates
    )
    assert route_after_authoring_planner(state.model_dump(mode="json")) == "analysis"
