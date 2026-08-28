from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.method_proposition_funnel import (
    evaluate_method_proposition_funnel,
    load_method_proposition_baselines,
    load_method_proposition_funnel_fixture,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "method_synthesis_funnel"
GOLD = FIXTURE_DIR / "linearrag_method_propositions_v1.json"
BASELINES = FIXTURE_DIR / "baselines_v1.json"


def test_gold_fixture_is_diagnostic_and_has_forty_three_propositions() -> None:
    raw = json.loads(GOLD.read_text(encoding="utf-8"))
    fixture = load_method_proposition_funnel_fixture(GOLD)
    assert fixture.authority == "diagnostic_non_authorizing"
    assert fixture.prose_copied_from_paper is False
    assert len(fixture.propositions) == 43
    assert sum(item.stage1 for item in fixture.propositions) == 14
    serialized = json.dumps(raw, ensure_ascii=False).lower()
    assert "we propose" not in serialized
    assert "\\delta" not in serialized


def test_baselines_record_empty_binding_oracle_stage1_gap() -> None:
    baselines = {item.condition: item for item in load_method_proposition_baselines(BASELINES)}
    assert baselines["product_empty_mas4"].stage1_used == 0
    assert baselines["binding_only"].stage1_used == 4
    assert baselines["oracle_writer"].stage1_used == 11
    assert baselines["product_empty_mas4"].funnel_counts["compiled"] == 35
    assert baselines["product_empty_mas4"].funnel_counts["bound_correct_h2"] == 18
    assert baselines["product_empty_mas4"].funnel_counts["used"] == 8


def test_funnel_scores_correct_h2_use_not_sibling_dump() -> None:
    fixture = load_method_proposition_funnel_fixture(GOLD)
    report = evaluate_method_proposition_funnel(
        fixture=fixture,
        yaml_or_code_text=(
            "avoid relation extraction entities as anchors tri-graph passage "
            "sentence entity contain mention sparse adjacency ner seed query "
            "sentence similarity iterative frontier prune threshold exclude "
            "below bridging intermediate hybrid pagerank damping top-k passages"
        ),
        claims=[
            {
                "claim_id": "c-activate",
                "canonical_text": (
                    "frontier expansion multiplies parent score by sentence "
                    "similarity then continue when score is below threshold"
                ),
            }
        ],
        plan_sections=[
            {"heading": "Motivation: revisit shortcomings", "claim_ids": ["c-activate"]},
            {
                "heading": "First retrieval: local activation via semantic bridging",
                "claim_ids": [],
            },
        ],
        writer_sections=[
            {
                "heading": "Motivation: revisit shortcomings",
                "markdown": (
                    "Frontier expansion multiplies parent score by sentence "
                    "similarity then prunes scores below a threshold."
                ),
            },
            {
                "heading": "First retrieval: local activation via semantic bridging",
                "markdown": "The operational specification is not provided in the repository.",
            },
        ],
    )
    prune = next(row for row in report.rows if row.proposition_id == "dynamic_threshold_pruning")
    assert prune.compiled is True
    assert prune.bound_correct_h2 is False
    assert prune.used is False


def test_weighted_coverage_rewards_used_critical_items() -> None:
    fixture = load_method_proposition_funnel_fixture(GOLD)
    stage1 = [item.proposition_id for item in fixture.propositions if item.stage1]
    report = evaluate_method_proposition_funnel(
        fixture=fixture,
        claims=[{
            "claim_id": "c1",
            "canonical_text": (
                "seed query entities sentence similarity iterative frontier "
                "subgraph product prune threshold exclude below bridging "
                "intermediate multi-hop without relation vectorized top sentence score"
            ),
        }],
        plan_sections=[{
            "heading": "First retrieval: entity activation via local semantic bridging",
            "claim_ids": ["c1"],
        }],
        writer_sections=[{
            "heading": "First retrieval: entity activation via local semantic bridging",
            "markdown": (
                "Seed query entities initialize activation. Query-sentence "
                "similarity modulates child scores. Iterative frontier expansion "
                "on the sentence-entity subgraph prunes scores below a threshold "
                "and discovers intermediate bridging entities without explicit "
                "relation triples. Vectorized and sequential modes share the same "
                "top sentence score selection."
            ),
        }],
        realization_by_id={item: 3 for item in stage1},
    )
    used_stage1 = [row for row in report.rows if row.stage1 and row.used]
    assert len(used_stage1) >= 8
    assert report.weighted_coverage > 0
    assert report.mean_realization_used == 3.0


def test_dyg_and_ebcar_diagnostic_fixtures_are_non_authorizing() -> None:
    for name, expected_n in (
        ("dyg_method_propositions_v1.json", 17),
        ("ebcar_method_propositions_v1.json", 16),
    ):
        path = FIXTURE_DIR / name
        fixture = load_method_proposition_funnel_fixture(path)
        assert fixture.authority == "diagnostic_non_authorizing"
        assert fixture.prose_copied_from_paper is False
        assert len(fixture.propositions) == expected_n
        raw = path.read_text(encoding="utf-8").lower()
        assert "we propose" not in raw
        assert "exp(" not in raw
