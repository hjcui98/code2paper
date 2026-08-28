from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.method_content_regression import (
    build_python_behavior_inventory,
    evaluate_method_authoring_oracle,
    evaluate_method_content_artifacts,
    load_method_authoring_oracle,
    load_method_content_fixture,
    load_method_synthesis_baselines,
)


FIXTURE = Path(__file__).parent / "fixtures" / "post_r8_method_content_regression_v1.json"
SYNTHESIS_BASELINES = (
    Path(__file__).parent / "fixtures" / "method_synthesis_funnel" / "baselines_v1.json"
)
AUTHORING_ORACLE = (
    Path(__file__).parent / "fixtures" / "method_synthesis_funnel" / "original_oracle_v1.json"
)


def test_six_round_source_to_render_baseline_is_typed_and_diagnostic() -> None:
    baseline = load_method_synthesis_baselines(SYNTHESIS_BASELINES)
    replay = baseline.source_to_render_baseline

    assert replay.run_id == "c2p-synth-20260826-225116"
    assert replay.protocol == {
        "callback_rounds": 0,
        "revision_budget": 0,
        "authority": "frozen_research_artifacts",
    }
    assert set(replay.projects) == {"linearrag", "dyg", "ebcar"}
    for project in replay.projects.values():
        assert project.draft_nonempty
        assert project.writer_call_count > 0
        assert project.formalizer_call_count >= project.formula_package_count
        assert project.rendered_paragraph_count <= project.planned_paragraph_count
        assert project.content_states["not_discovered"] >= 0


def test_four_project_fixture_is_diagnostic_and_contains_no_copied_prose_fields() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture = load_method_content_fixture(FIXTURE)

    assert fixture.authority == "diagnostic_non_authorizing"
    assert fixture.prose_copied_from_paper is False
    assert set(fixture.projects) == {"rap", "ebcar", "dyg", "linearrag"}
    serialized = json.dumps(raw, ensure_ascii=False).lower()
    for forbidden_field in ('"paper_text"', '"claim_text"', '"fact_text"', '"source_path"', '"symbol"'):
        assert forbidden_field not in serialized


def test_fixture_evaluator_reports_every_required_unit_from_authorized_artifacts() -> None:
    fixture = load_method_content_fixture(FIXTURE)
    for project_id, project in fixture.projects.items():
        tokens = " ".join(group[0] for unit in project.units for group in unit.required_alias_groups)
        report = evaluate_method_content_artifacts(
            fixture=fixture,
            project_id=project_id,
            artifacts={
                "claims": {
                    "claims": [{"canonical_text": tokens}],
                }
            },
        )
        assert report.complete, (project_id, report.model_dump(mode="json"))
        assert report.covered_units == report.total_units == len(project.units)


def test_fixture_evaluator_does_not_treat_unrelated_text_as_coverage() -> None:
    fixture = load_method_content_fixture(FIXTURE)
    report = evaluate_method_content_artifacts(
        fixture=fixture,
        project_id="ebcar",
        artifacts={"claims": {"claims": [{"canonical_text": "An encoder returns a result."}]}},
    )

    assert not report.complete
    assert report.covered_units == 0


def test_diagnostic_inventory_cannot_satisfy_authoring_content_coverage() -> None:
    fixture = load_method_content_fixture(FIXTURE)
    report = evaluate_method_content_artifacts(
        fixture=fixture,
        project_id="dyg",
        artifacts={
            "inventory": {
                "authority": "executable_hard_diagnostic_inventory",
                "operation_descriptors": [{
                    "symbol": "route_time_mamba",
                    "predicate": "BRANCH",
                    "operands": ["topk", "softmax", "routing_weights.sum"],
                }],
            }
        },
    )

    assert not report.complete
    assert report.covered_units == 0


def test_fixture_evaluator_ignores_provenance_ids_and_line_numbers() -> None:
    fixture = load_method_content_fixture(FIXTURE)
    report = evaluate_method_content_artifacts(
        fixture=fixture,
        project_id="rap",
        artifacts={
            "facts": {
                "facts": [{
                    "canonical_identity": "span:model.py:15:15",
                    "direct_span_ids": ["span:model.py:15:15"],
                    "subject": "compute_knn_score",
                    "predicate": "computes_formula",
                    "object": "feature",
                }]
            }
        },
    )

    dimension = next(unit for unit in report.units if unit.unit_id == "rap_feature_dimension")
    assert not dimension.covered
    assert ("15", "fifteen") in dimension.missing_alias_groups


def test_python_inventory_is_source_derived_and_does_not_promote_comments() -> None:
    inventory = build_python_behavior_inventory(
        files={
            "model.py": (
                "def route(x, time_mamba=False):\n"
                "    # forbidden_paper_only_phrase\n"
                "    if time_mamba:\n"
                "        return x.softmax(dim=-1)\n"
                "    return x\n"
            )
        },
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
    )
    serialized = json.dumps(inventory).lower()

    assert inventory["authority"] == "executable_hard_diagnostic_inventory"
    assert "time_mamba" in serialized
    assert "softmax" in serialized
    assert "forbidden_paper_only_phrase" not in serialized


def test_original_paper_oracle_is_offline_and_captures_cross_project_units() -> None:
    oracle = load_method_authoring_oracle(AUTHORING_ORACLE)
    assert oracle.authority == "diagnostic_non_authorizing"
    assert oracle.prose_copied_from_paper is False
    assert set(oracle.projects) == {"linearrag", "dyg", "ebcar"}
    assert any(
        unit.polarity == "exclude_below_threshold"
        for unit in oracle.projects["linearrag"].units
    )
    assert any(
        unit.unit_id == "dyg_timespan_step_and_bc_path"
        for unit in oracle.projects["dyg"].units
    )
    assert any(
        unit.unit_id == "ebcar_dedicated_masked_attention"
        for unit in oracle.projects["ebcar"].units
    )


def test_original_paper_oracle_reports_candidate_gap_without_authorizing_it() -> None:
    oracle = load_method_authoring_oracle(AUTHORING_ORACLE)
    original = (
        "## First Retrieval: Entity Activation\n"
        "Seed entities propagate through co-occurring sentences. Scores below "
        "the threshold are discarded.\n"
            "## Second Retrieval: Passage Ranking\n"
            "A hybrid passage score uses log occurrence and damping in personalized "
            "PageRank, then ranks passages in descending order. $$r(v)=w(v)$$\n"
    )
    candidate = (
        "## First Retrieval: Entity Activation\n"
        "Seed entities propagate through sentences and prune low scores.\n"
    )
    report = evaluate_method_authoring_oracle(
        oracle=oracle,
        project_id="linearrag",
        candidate_text=candidate,
        original_text=original,
    )
    stage2 = next(item for item in report.units if item.unit_id == "linearrag_stage2_hybrid_ppr")
    assert stage2.original_covered
    assert not stage2.candidate_covered
    assert report.candidate_covered_units < report.original_covered_units
