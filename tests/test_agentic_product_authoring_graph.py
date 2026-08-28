from __future__ import annotations

import json

import pytest

from code2paper.agentic.graph_topology import CONDITIONAL_ROUTE_SPECS
from code2paper.agentic.product_authoring_graph import (
    PRODUCT_AUTHORING_CONDITIONAL_ROUTES,
    PRODUCT_AUTHORING_DIRECT_EDGES,
    PRODUCT_AUTHORING_NODE_NAMES,
    ProductAuthoringIssueV1,
    apply_dependency_invalidation,
    build_product_authoring_graph,
    build_product_authoring_state,
    load_product_authoring_state,
    invalidated_surfaces_for_changes,
    persist_product_authoring_state_from_writer,
    record_product_authoring_attempt,
    route_product_authoring_issues,
    run_product_authoring_graph,
)


def test_evidence_invalidation_reaches_section_and_reverse_surface() -> None:
    assert invalidated_surfaces_for_changes("evidence") == (
        "binding",
        "coverage",
        "equations",
        "completeness",
        "brief",
        "facet_policy",
        "formula",
        "placement",
        "section",
        "surface",
        "reverse_validation",
    )
    assert invalidated_surfaces_for_changes("style") == (
        "surface",
        "reverse_validation",
    )


def test_dependency_change_preserves_incumbent_and_marks_affected_sections() -> None:
    state = build_product_authoring_state(
        run_id="run-1",
        frozen_digests={"evidence": "sha256:frozen"},
        brief_ids=("B1",),
        facet_ids=("F1",),
        policy_ids=("P1",),
        formula_obligation_ids=("FO1",),
        section_ids=("S1", "S2"),
    )

    updated = apply_dependency_invalidation(
        state,
        changed_surfaces="evidence",
        affected_section_ids=("S2",),
        revision_digests={"evidence": "sha256:revision"},
    )

    assert updated.frozen_revision_digest == state.frozen_revision_digest
    assert updated.revision_digests["evidence"] == "sha256:revision"
    assert updated.affected_section_ids == ("S2",)
    assert updated.invalidated_surfaces[-1] == "reverse_validation"
    assert updated.formula_obligation_ids == ()
    assert updated.section_ids == ()
    assert updated.brief_ids == ()
    assert updated.facet_ids == ()
    assert updated.policy_ids == ()
    repeated = apply_dependency_invalidation(
        updated,
        changed_surfaces="evidence",
        affected_section_ids=("S2",),
        revision_digests={"evidence": "sha256:revision"},
    )
    assert repeated.content_digest == updated.content_digest
    assert repeated.revision_id == updated.revision_id


def test_style_invalidation_keeps_formula_and_section_authority() -> None:
    state = build_product_authoring_state(
        formula_obligation_ids=("FO1",),
        section_ids=("S1",),
        brief_ids=("B1",),
    )

    updated = apply_dependency_invalidation(
        state,
        changed_surfaces="style",
        affected_section_ids=("S1",),
    )

    assert updated.formula_obligation_ids == ("FO1",)
    assert updated.section_ids == ("S1",)
    assert updated.brief_ids == ("B1",)
    assert "formula" not in updated.invalidated_surfaces
    assert updated.invalidated_surfaces == ("surface", "reverse_validation")


def test_attempt_information_gain_requires_semantic_delta() -> None:
    state = build_product_authoring_state(run_id="semantic-delta")
    unchanged = record_product_authoring_attempt(
        state,
        node="section_writer",
        owner="writer",
        attempt=1,
        input_digest="sha256:input",
        output_digest="sha256:changed-bytes-only",
        semantic_delta={},
        information_gain=True,
        stop_reason="no_semantic_delta",
    )
    assert unchanged.attempt_receipts[-1].information_gain is False
    assert unchanged.attempt_receipts[-1].semantic_delta == {}
    improved = record_product_authoring_attempt(
        unchanged,
        node="section_writer",
        owner="writer",
        attempt=2,
        input_digest="sha256:input",
        output_digest="sha256:semantic-change",
        semantic_delta={"validated_witnesses_added": 1},
        information_gain=False,
    )
    assert improved.attempt_receipts[-1].information_gain is True
    assert improved.attempt_receipts[-1].semantic_delta["validated_witnesses_added"] == 1


def test_direct_formula_recompile_keeps_new_formula_ids() -> None:
    state = build_product_authoring_state(
        formula_obligation_ids=("FO2",),
        section_ids=("S1",),
    )

    updated = apply_dependency_invalidation(
        state,
        changed_surfaces="formula",
        revision_digests={"formalization_section_results_v1": "sha256:new"},
    )

    assert updated.formula_obligation_ids == ("FO2",)
    assert updated.section_ids == ()


def test_issue_owner_route_has_no_rewrite_to_research_edge() -> None:
    assert ("rewrite_method_language", "writing_research_continue") not in (
        PRODUCT_AUTHORING_DIRECT_EDGES
    )
    assert "writing_research_continue" not in PRODUCT_AUTHORING_CONDITIONAL_ROUTES[
        "rewrite_method_language"
    ]
    assert "research_frozen" not in PRODUCT_AUTHORING_CONDITIONAL_ROUTES[
        "rewrite_method_language"
    ]
    state = build_product_authoring_state(
        open_issues=(
            ProductAuthoringIssueV1(
                issue_id="e1",
                issue_type="evidence_gap",
                owner="research_continuation",
                section_id="S1",
            ),
        ),
        next_node="issue_owner_router",
    )

    routed = route_product_authoring_issues(state)

    assert routed.next_node == "writing_research_continue"
    assert routed.owner_routes[0].owner == "research_continuation"


def test_evidence_formula_content_style_issues_return_to_owning_nodes() -> None:
    cases = (
        ("evidence_gap", "research_continuation", "writing_research_continue"),
        ("formula_unsupported", "formalizer", "section_formalizer"),
        ("missing_core_facet", "writer", "section_writer"),
        ("method_language_style", "rewrite", "rewrite_method_language"),
    )
    for issue_type, owner, expected_node in cases:
        state = build_product_authoring_state(
            open_issues=(
                ProductAuthoringIssueV1(
                    issue_id=issue_type,
                    issue_type=issue_type,
                    owner=owner,
                    section_id="S1",
                ),
            ),
            next_node="issue_owner_router",
        )
        routed = route_product_authoring_issues(state)
        assert routed.next_node == expected_node, issue_type
        assert routed.owner_routes[0].owner == owner


def test_product_graph_cannot_route_local_repair_to_intake() -> None:
    assert "local_text_repair" not in PRODUCT_AUTHORING_NODE_NAMES
    assert "intake" not in PRODUCT_AUTHORING_NODE_NAMES
    rewrite_targets = PRODUCT_AUTHORING_CONDITIONAL_ROUTES["rewrite_method_language"]
    assert "writing_research_continue" not in rewrite_targets
    r8_repair_targets = {
        target
        for route in CONDITIONAL_ROUTE_SPECS
        if route.source == "local_text_repair"
        for _decision, target in route.routes
    }
    assert "intake" not in r8_repair_targets
    assert r8_repair_targets.isdisjoint(
        {"input_resolution", "intake", "analysis", "evidence", "grounding", "authoring"}
    )


def test_style_issue_reaches_review_without_global_research_restart() -> None:
    state = build_product_authoring_state(
        open_issues=(
            ProductAuthoringIssueV1(
                issue_id="s1",
                issue_type="method_language_style",
                owner="rewrite",
                section_id="S1",
            ),
        ),
        next_node="issue_owner_router",
    )

    routed = run_product_authoring_graph(state, max_steps=5)

    assert any(
        receipt.node == "rewrite_method_language"
        for receipt in routed.attempt_receipts
    )
    assert all(
        not (
            receipt.node == "rewrite_method_language"
            and receipt.status == "blocked"
        )
        for receipt in routed.attempt_receipts
    )


def test_langgraph_overlay_exposes_invoke_boundary() -> None:
    state = build_product_authoring_state(next_node="author_review_items")
    graph = build_product_authoring_graph(max_steps=1)

    result = graph.invoke({"authoring_state": state.model_dump(mode="json")})

    assert "authoring_state" in result
    assert result["authoring_state"]["terminal_status"] == "completed"


def test_default_overlay_walks_explicit_product_nodes() -> None:
    state = build_product_authoring_state(next_node="research_frozen")

    result = run_product_authoring_graph(state, max_steps=32)

    assert result.terminal_status == "completed"
    assert [receipt.node for receipt in result.attempt_receipts] == [
        "research_frozen",
        "brief_compile",
        "facet_decompose",
        "facet_evidence_align",
        "writing_gap_router",
        "mechanism_planner",
        "architect",
        "section_formalizer",
        "section_writer",
        "reverse_validate",
        "issue_owner_router",
        "editor",
        "rewrite_method_language",
        "split_candidate_verified",
        "author_review_items",
    ]


def test_product_state_rejects_duplicate_open_issue_ids() -> None:
    with pytest.raises(ValueError, match="open issue ids must be unique"):
        build_product_authoring_state(
            open_issues=(
                ProductAuthoringIssueV1(
                    issue_id="duplicate",
                    issue_type="method_language_style",
                    owner="rewrite",
                ),
                ProductAuthoringIssueV1(
                    issue_id="duplicate",
                    issue_type="method_language_style",
                    owner="rewrite",
                ),
            )
        )


def test_writer_adapter_persists_receipts_and_recompiles_changed_evidence(
    tmp_path,
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    def write(name: str, payload) -> str:
        path = artifacts / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    paths = {
        "method_section_plan_v2": write(
            "method_section_plan_v2.json",
            {"sections": [{"section_id": "S1"}]},
        ),
        "method_argument_facets_v1": write(
            "method_argument_facets_v1.json",
            {"facets": [{"facet_id": "F1"}]},
        ),
        "candidate_facet_policies_v1": write(
            "candidate_facet_policies_v1.json",
            {"policies": [{"policy_id": "P1", "facet_id": "F1"}]},
        ),
        "formalization_section_results_v1": write(
            "formalization_section_results_v1.json",
            {"obligations": [{"obligation_id": "FO1"}]},
        ),
        "publication_candidate_method": write(
            "publication_candidate_method.md",
            "## S1\n\nThe mechanism transforms the input.",
        ),
        "repository_verified_method": write(
            "repository_verified_method.md",
            "The mechanism transforms the input.",
        ),
        "publication_rewrite_results_v1": write(
            "publication_rewrite_results_v1.json",
            {"rewrites": [{"rewrite_id": "R1"}]},
        ),
        "author_review_candidates": write(
            "author_review_candidates.json",
            {"items": []},
        ),
        "text_evidence_validation": write(
            "text_evidence_validation.json",
            {"status": "passed"},
        ),
        "evidence_packets_v3": write(
            "evidence_packets_v3.json",
            {"packets": []},
        ),
    }
    issue = ProductAuthoringIssueV1(
        issue_id="style-1",
        issue_type="method_language_style",
        owner="rewrite",
        section_id="S1",
    )

    first, state_path = persist_product_authoring_state_from_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        run_id="run-1",
        open_issues=(issue,),
        affected_section_ids=("S1",),
        terminal_status="review_ready_with_warnings",
        stop_reason="open_issues_remain",
    )

    assert state_path.endswith(
        "artifacts/06_authoring/product_authoring_state_v1.json"
    )
    assert first.revision_id == "revision:0"
    assert first.owner_routes[0].owner == "rewrite"
    assert first.formula_obligation_ids == ("FO1",)
    assert first.section_ids == ("S1",)
    assert "rewrite_method_language" in {
        receipt.node for receipt in first.attempt_receipts
    } or "issue_owner_router" in {
        receipt.node for receipt in first.attempt_receipts
    }
    assert load_product_authoring_state(state_path).content_digest == first.content_digest

    paths["evidence_packets_v3"] = write(
        "evidence_packets_v3.json",
        {"packets": [{"packet_id": "new-evidence"}]},
    )
    second, _ = persist_product_authoring_state_from_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        run_id="run-1",
        open_issues=(issue,),
        affected_section_ids=("S1",),
        terminal_status="review_ready_with_warnings",
        stop_reason="open_issues_remain",
    )

    assert second.revision_id == "revision:1"
    assert "binding" in second.invalidated_surfaces
    assert "reverse_validation" in second.invalidated_surfaces
    assert second.frozen_revision_digest == first.frozen_revision_digest
    assert second.formula_obligation_ids == ()
    assert second.section_ids == ()
    assert second.facet_ids == ()
    assert second.policy_ids == ()


def test_writer_adapter_style_only_persist_keeps_formula_and_section_ids(
    tmp_path,
) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()

    def write(name: str, payload) -> str:
        path = artifacts / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    paths = {
        "method_section_plan_v2": write(
            "method_section_plan_v2.json",
            {"sections": [{"section_id": "S1"}]},
        ),
        "formalization_section_results_v1": write(
            "formalization_section_results_v1.json",
            {"obligations": [{"obligation_id": "FO1"}]},
        ),
        "publication_candidate_method": write(
            "publication_candidate_method.md",
            "## S1\n\nThe mechanism transforms the input.",
        ),
        "publication_rewrite_results_v1": write(
            "publication_rewrite_results_v1.json",
            {"rewrites": [{"rewrite_id": "R1"}]},
        ),
        "text_evidence_validation": write(
            "text_evidence_validation.json",
            {"status": "passed"},
        ),
        "evidence_packets_v3": write(
            "evidence_packets_v3.json",
            {"packets": []},
        ),
    }
    first, _ = persist_product_authoring_state_from_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        run_id="run-style",
        terminal_status="completed",
    )
    paths["publication_rewrite_results_v1"] = write(
        "publication_rewrite_results_v1.json",
        {"rewrites": [{"rewrite_id": "R2"}]},
    )
    second, _ = persist_product_authoring_state_from_writer(
        out_root=tmp_path,
        artifact_paths=paths,
        run_id="run-style",
        terminal_status="completed",
    )

    assert second.formula_obligation_ids == ("FO1",)
    assert second.section_ids == ("S1",)
    assert "formula" not in second.invalidated_surfaces
    assert "binding" not in second.invalidated_surfaces
    assert second.frozen_revision_digest == first.frozen_revision_digest
