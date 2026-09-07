from __future__ import annotations

import pytest

from code2paper.agentic.intent_ledger import (
    IntentCoverageScheduler,
    IntentImplementationLedgerItemV1,
    IntentImplementationLedgerV1,
    VALID_INTENT_IMPLEMENTATION_STATUSES,
    build_intent_implementation_ledger,
)


def test_intent_implementation_statuses() -> None:
    assert len(VALID_INTENT_IMPLEMENTATION_STATUSES) == 7
    expected = {
        "implemented_exact",
        "implemented_partial",
        "author_spec_only",
        "repo_mismatch",
        "inactive_alternative",
        "not_found_after_bounded_search",
        "out_of_scope",
    }
    assert set(VALID_INTENT_IMPLEMENTATION_STATUSES) == expected


def test_build_intent_implementation_ledger_metrics() -> None:
    clauses = [
        {"clause_id": "c1", "clause_text": "VCD densification", "is_core": True},
        {"clause_id": "c2", "clause_text": "VCP pruning", "is_core": True},
        {"clause_id": "c3", "clause_text": "SfM initialization", "is_core": False},
    ]

    queries = {
        "c1": ["densify_and_prune", "vcd_loss"],
        "c2": ["prune_gaussians"],
    }
    candidates = {
        "c1": ["scene/gaussian_model.py::densify_and_prune_fastgs"],
        "c2": ["scene/gaussian_model.py::prune"],
    }
    reads = {
        "c1": ["scene/gaussian_model.py::densify_and_prune_fastgs"],
    }
    facts = {
        "c1": ["fact:1"],
    }
    ops = {
        "c1": ["op:1"],
    }
    rejections = {
        "c2": "ownership_role_not_target_method",
    }

    compile_events = [
        {"new_spans_count": 1, "new_facts_count": 1, "new_operations_count": 1},
        {"new_spans_count": 0, "new_facts_count": 0, "new_operations_count": 0, "has_coverage_gain": False},
        {"new_spans_count": 0, "new_facts_count": 0, "new_operations_count": 0, "has_coverage_gain": False},
    ]

    ledger = build_intent_implementation_ledger(
        clauses=clauses,
        queries_by_clause=queries,
        candidates_by_clause=candidates,
        read_symbols_by_clause=reads,
        promoted_facts_by_clause=facts,
        promoted_operations_by_clause=ops,
        rejections_by_clause=rejections,
        repo_snapshot_id="snap_1",
        project_tree_hash="hash_1",
        total_budget_turns=10,
        novelty_budget_turns=8,
        compile_events=compile_events,
    )

    assert isinstance(ledger, IntentImplementationLedgerV1)
    assert len(ledger.items) == 3

    # Check clause dispositions
    item1 = ledger.items[0]
    assert item1.clause_id == "c1"
    assert item1.status == "implemented_exact"
    assert item1.evidence_authority == "repository_verified"

    item2 = ledger.items[1]
    assert item2.clause_id == "c2"
    assert item2.status == "not_found_after_bounded_search"
    assert item2.rejection_code == "ownership_role_not_target_method"

    item3 = ledger.items[2]
    assert item3.clause_id == "c3"
    assert item3.status == "author_spec_only"

    # Check 6 section 5.5 metrics:
    # 2 core clauses, both attempted (queries/candidates present)
    assert ledger.core_intent_attempt_coverage == 1.0
    # 2 total candidates, 1 read
    assert ledger.first_party_candidate_read_rate == 0.5
    # 1 observation read, 1 promoted
    assert ledger.observation_promotion_rate == 1.0
    # 1 unpromoted candidate (c2), with 1 typed rejection
    assert ledger.typed_rejection_coverage == 1.0
    # Novelty share: 8 / 10 = 0.8
    assert ledger.novelty_mechanism_budget_share == 0.8
    # 2 consecutive no-progress compiles
    assert ledger.no_progress_compile_count == 2


def test_intent_coverage_scheduler_prioritization() -> None:
    scheduler = IntentCoverageScheduler(min_novelty_budget_ratio=0.6, max_no_progress_compiles=2)

    clauses = [
        {"clause_id": "c1", "clause_text": "Core algorithm 1", "is_core": True},
        {"clause_id": "c2", "clause_text": "Core algorithm 2", "is_core": True},
    ]
    # c1 attempted, c2 unattempted
    queries = {"c1": ["search_algo1"]}
    ledger = build_intent_implementation_ledger(
        clauses=clauses,
        queries_by_clause=queries,
        compile_events=[{"new_spans_count": 0, "new_facts_count": 0, "new_operations_count": 0}],
    )

    schedule = scheduler.check_next_schedule(
        ledger,
        remaining_budget_turns=1,
        current_action_is_novelty=False,
    )
    assert schedule["must_prioritize_core"] is True
    assert schedule["unattempted_core_clause_ids"] == ("c2",)
    assert schedule["budget_constrained"] is True
    assert schedule["reserve_turns_needed"] == 1
