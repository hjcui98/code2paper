"""R0.1 research contract tests.

Exit conditions covered:
- all schemas use ``extra="forbid"``;
- terminal status consistency for agenda items and observations;
- unknown actions / tool kinds / failure types are rejected;
- action <-> tool call alignment enforced;
- Pareto-style ``quality_state_dominates`` rule;
- per-obligation budget tracking.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.research_models import (
    BUDGET_TOOL_KINDS,
    RESEARCH_ACTIONS,
    GlobalSafetyBudgetV1,
    GapRequirementV1,
    PerObligationBudgetV1,
    QualityContentDimensionsV1,
    QualityCostDimensionsV1,
    QualityMinimalityDimensionsV1,
    QualitySafetyDimensionsV1,
    QualityStateV2,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationDiagnosticsV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    TEXT_REPAIR_FAILURE_TYPES,
    TEXT_REPAIR_SCOPES,
    TOOL_KINDS,
    TextRepairIssueV1,
    TypedBehaviorTargetV1,
    assert_observation_can_anchor_positive_claim,
    can_observe_authority_for_positive_claim,
    empty_quality_state,
    make_observation,
    quality_state_dominates,
)


# ---------------------------------------------------------------------------
# ResearchAgendaItemV1
# ---------------------------------------------------------------------------


def _agenda_item_kwargs(**overrides):
    base = {
        "obligation_id": "OBL-1",
        "priority": "must_cover",
        "author_text": "explain pruning",
    }
    base.update(overrides)
    return base


def test_agenda_item_requires_obligation_id() -> None:
    with pytest.raises(ValidationError):
        ResearchAgendaItemV1(obligation_id="")  # type: ignore[call-arg]


def test_agenda_item_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchAgendaItemV1(obligation_id="OBL-1", surprise=True)  # type: ignore[call-arg]


def test_agenda_item_supported_requires_claim_ids() -> None:
    with pytest.raises(ValidationError, match="supported without supported_claim_ids"):
        ResearchAgendaItemV1(**_agenda_item_kwargs(status="supported"))


def test_agenda_item_explicit_gap_requires_gap_requirements() -> None:
    with pytest.raises(ValidationError, match="explicit_gap without gap_requirements"):
        ResearchAgendaItemV1(**_agenda_item_kwargs(status="explicit_gap"))


def test_agenda_item_supported_with_claim_ids_succeeds() -> None:
    item = ResearchAgendaItemV1(
        **_agenda_item_kwargs(
            status="supported",
            supported_claim_ids=["C-1"],
        )
    )
    assert item.status == "supported"
    assert item.supported_claim_ids == ["C-1"]


# ---------------------------------------------------------------------------
# ResearchAgendaV1
# ---------------------------------------------------------------------------


def _agenda_kwargs(**overrides):
    base = {
        "run_id": "run-1",
        "repo_snapshot_id": "repo:abc",
        "project_tree_hash": "sha256:tree",
    }
    base.update(overrides)
    return base


def test_agenda_computes_content_digest() -> None:
    agenda = ResearchAgendaV1(**_agenda_kwargs())
    assert agenda.content_digest.startswith("sha256:")


def test_agenda_digest_is_deterministic() -> None:
    first = ResearchAgendaV1(**_agenda_kwargs())
    second = ResearchAgendaV1(**_agenda_kwargs())
    assert first.content_digest == second.content_digest


def test_agenda_digest_changes_when_items_change() -> None:
    empty = ResearchAgendaV1(**_agenda_kwargs())
    with_item = ResearchAgendaV1(
        **_agenda_kwargs(items=[ResearchAgendaItemV1(obligation_id="OBL-1")])
    )
    assert empty.content_digest != with_item.content_digest


def test_agenda_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchAgendaV1(**_agenda_kwargs(surprise=True))  # type: ignore[call-arg]


def test_agenda_requires_run_id_and_snapshot_id() -> None:
    with pytest.raises(ValidationError):
        ResearchAgendaV1(run_id="", repo_snapshot_id="r", project_tree_hash="h")  # type: ignore[call-arg]


def test_agenda_must_cover_filters() -> None:
    agenda = ResearchAgendaV1(
        **_agenda_kwargs(
            items=[
                ResearchAgendaItemV1(obligation_id="OBL-1", priority="must_cover"),
                ResearchAgendaItemV1(obligation_id="OBL-2", priority="preference"),
            ]
        )
    )
    assert len(agenda.must_cover_items) == 1
    assert agenda.must_cover_items[0].obligation_id == "OBL-1"


# ---------------------------------------------------------------------------
# ResearchToolCallV1
# ---------------------------------------------------------------------------


def _tool_call_kwargs(**overrides):
    base = {
        "tool_call_id": "TC-1",
        "tool_name": "search_symbols",
        "tool_kind": "symbol_search",
        "obligation_id": "OBL-1",
        "goal": "find encoder entrypoint",
        "repo_snapshot_id": "repo:abc",
    }
    base.update(overrides)
    return base


def test_tool_call_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchToolCallV1(**_tool_call_kwargs(extra=True))  # type: ignore[call-arg]


def test_tool_call_requires_nonempty_fields() -> None:
    for field in ("tool_call_id", "tool_name", "obligation_id", "repo_snapshot_id"):
        with pytest.raises(ValidationError):
            ResearchToolCallV1(**_tool_call_kwargs(**{field: ""}))


def test_tool_call_rejects_negative_budgets() -> None:
    with pytest.raises(ValidationError):
        ResearchToolCallV1(**_tool_call_kwargs(top_k=-1))


# ---------------------------------------------------------------------------
# ResearchObservationV1
# ---------------------------------------------------------------------------


def test_observation_success_requires_result_refs_or_spans() -> None:
    with pytest.raises(ValidationError, match="success observations must return"):
        ResearchObservationV1(
            observation_id="OBS-1",
            tool_call_id="TC-1",
            tool_name="search_symbols",
            obligation_id="OBL-1",
            repo_snapshot_id="repo:abc",
            status="success",
        )


def test_observation_invalid_request_requires_error_message() -> None:
    with pytest.raises(ValidationError, match="invalid_request observations must carry"):
        ResearchObservationV1(
            observation_id="OBS-1",
            tool_call_id="TC-1",
            tool_name="search_symbols",
            obligation_id="OBL-1",
            repo_snapshot_id="repo:abc",
            status="invalid_request",
        )


def test_observation_success_empty_does_not_require_refs() -> None:
    obs = ResearchObservationV1(
        observation_id="OBS-1",
        tool_call_id="TC-1",
        tool_name="search_symbols",
        obligation_id="OBL-1",
        repo_snapshot_id="repo:abc",
        status="success_empty",
    )
    assert obs.is_empty is True


def test_observation_rejects_unknown_authority() -> None:
    with pytest.raises(ValidationError):
        ResearchObservationV1(
            observation_id="OBS-1",
            tool_call_id="TC-1",
            tool_name="search_symbols",
            obligation_id="OBL-1",
            repo_snapshot_id="repo:abc",
            status="success_empty",
            source_authority="rumor",  # type: ignore[arg-type]
        )


def test_observation_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchObservationV1(
            observation_id="OBS-1",
            tool_call_id="TC-1",
            tool_name="search_symbols",
            obligation_id="OBL-1",
            repo_snapshot_id="repo:abc",
            status="success_empty",
            surprise=True,  # type: ignore[call-arg]
        )


def test_make_observation_produces_stable_digests() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    first = make_observation(
        tool_call=tool_call,
        status="success",
        result_refs=("symbol:src/main.py:L1",),
    )
    second = make_observation(
        tool_call=tool_call,
        status="success",
        result_refs=("symbol:src/main.py:L1",),
    )
    assert first.input_digest == second.input_digest
    assert first.output_digest == second.output_digest
    assert first.observation_id == second.observation_id


def test_make_observation_digests_change_with_payload() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    a = make_observation(tool_call=tool_call, status="success", result_refs=("a",))
    b = make_observation(tool_call=tool_call, status="success", result_refs=("b",))
    assert a.output_digest != b.output_digest


def test_assert_observation_can_anchor_positive_claim_rejects_hints() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    hint_obs = make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="semantic_hint",
        result_refs=("hint:readme:line1",),
    )
    with pytest.raises(ValueError, match="executable_hard"):
        assert_observation_can_anchor_positive_claim(hint_obs)


def test_can_observe_authority_for_positive_claim() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    hard_obs = make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="executable_hard",
        result_refs=("sym:src/main.py:L1",),
    )
    hint_obs = make_observation(
        tool_call=tool_call,
        status="success",
        source_authority="semantic_hint",
        result_refs=("hint:readme:line1",),
    )
    assert can_observe_authority_for_positive_claim(hard_obs) is True
    assert can_observe_authority_for_positive_claim(hint_obs) is False


# ---------------------------------------------------------------------------
# ResearchIssueV1
# ---------------------------------------------------------------------------


def test_issue_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchIssueV1(issue_id="ISS-1", issue_kind="missing_anchor", description="x", surprise=True)  # type: ignore[call-arg]


def test_issue_requires_nonempty_id_and_description() -> None:
    with pytest.raises(ValidationError):
        ResearchIssueV1(issue_id="", issue_kind="missing_anchor", description="x")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ResearchIssueV1(issue_id="ISS-1", issue_kind="missing_anchor", description="")


# ---------------------------------------------------------------------------
# ResearchDecisionV1
# ---------------------------------------------------------------------------


def test_decision_action_requiring_tool_calls_must_select_one() -> None:
    with pytest.raises(ValidationError, match="requires at least one selected_tool_call"):
        ResearchDecisionV1(
            decision_id="DEC-1",
            run_id="run-1",
            turn_index=0,
            action="SEARCH_SYMBOLS",
            goal="find encoder",
        )


def test_decision_terminal_action_must_not_select_tool_calls() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    with pytest.raises(ValidationError, match="must not select tool calls"):
        ResearchDecisionV1(
            decision_id="DEC-1",
            run_id="run-1",
            turn_index=0,
            action="STOP_BLOCKED",
            goal="stop run",
            selected_tool_calls=(tool_call,),
        )


def test_decision_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        ResearchDecisionV1(  # type: ignore[arg-type]
            decision_id="DEC-1",
            run_id="run-1",
            turn_index=0,
            action="INVENT_HYPOTHESIS",
            goal="x",
        )


def test_decision_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchDecisionV1(
            decision_id="DEC-1",
            run_id="run-1",
            turn_index=0,
            action="STOP_BLOCKED",
            goal="x",
            surprise=True,  # type: ignore[call-arg]
        )


def test_decision_negative_turn_index_rejected() -> None:
    with pytest.raises(ValidationError):
        ResearchDecisionV1(
            decision_id="DEC-1",
            run_id="run-1",
            turn_index=-1,
            action="STOP_BLOCKED",
            goal="x",
        )


def test_decision_with_tool_calls_succeeds() -> None:
    tool_call = ResearchToolCallV1(**_tool_call_kwargs())
    decision = ResearchDecisionV1(
        decision_id="DEC-1",
        run_id="run-1",
        turn_index=0,
        action="SEARCH_SYMBOLS",
        goal="find encoder",
        selected_tool_calls=(tool_call,),
    )
    assert decision.action == "SEARCH_SYMBOLS"
    assert len(decision.selected_tool_calls) == 1


# ---------------------------------------------------------------------------
# TextRepairIssueV1
# ---------------------------------------------------------------------------


def test_text_repair_issue_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TextRepairIssueV1(  # type: ignore[call-arg]
            sentence_id="S1",
            failure_type="wrong_span_role",
            allowed_repair_scope="wording_only",
            surprise=True,
        )


def test_text_repair_issue_rejects_unknown_failure_type() -> None:
    with pytest.raises(ValidationError):
        TextRepairIssueV1(  # type: ignore[arg-type]
            sentence_id="S1",
            failure_type="invented_failure",
            allowed_repair_scope="wording_only",
        )


def test_text_repair_issue_rejects_unknown_scope() -> None:
    with pytest.raises(ValidationError):
        TextRepairIssueV1(  # type: ignore[arg-type]
            sentence_id="S1",
            failure_type="wrong_span_role",
            allowed_repair_scope="full_rewrite",
        )


def test_text_repair_issue_negative_attempt_rejected() -> None:
    with pytest.raises(ValidationError):
        TextRepairIssueV1(
            sentence_id="S1",
            failure_type="wrong_span_role",
            allowed_repair_scope="wording_only",
            attempt=-1,
        )


# ---------------------------------------------------------------------------
# QualityStateV2
# ---------------------------------------------------------------------------


def _quality_state_kwargs(state_id: str = "QS-1", **overrides):
    base = {
        "state_id": state_id,
        "run_id": "run-1",
        "repo_snapshot_id": "repo:abc",
        "project_tree_hash": "sha256:tree",
    }
    base.update(overrides)
    return base


def test_quality_state_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        QualityStateV2(**_quality_state_kwargs(surprise=True))  # type: ignore[call-arg]


def test_quality_state_computes_digest() -> None:
    state = QualityStateV2(**_quality_state_kwargs())
    assert state.content_digest.startswith("sha256:")


def test_quality_state_is_trusted_default() -> None:
    state = QualityStateV2(**_quality_state_kwargs())
    assert state.is_trusted is True
    assert state.is_empty is True


def test_quality_state_untrusted_when_unsupported_positive_claims_exist() -> None:
    state = QualityStateV2(
        **_quality_state_kwargs(
            safety=QualitySafetyDimensionsV1(unsupported_positive_claims=1)
        )
    )
    assert state.is_trusted is False


def test_quality_state_untrusted_when_source_integrity_lost() -> None:
    state = QualityStateV2(
        **_quality_state_kwargs(
            safety=QualitySafetyDimensionsV1(source_integrity=False)
        )
    )
    assert state.is_trusted is False


def test_quality_state_dominates_empty_incumbent() -> None:
    incumbent = empty_quality_state(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
    )
    candidate = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(
                terminal_must_cover=4,
                supported_must_cover=1,
                unique_supported_claims=2,
            )
        )
    )
    assert quality_state_dominates(candidate, incumbent) is True


def test_quality_state_dominates_rejects_safety_regression() -> None:
    incumbent = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(supported_must_cover=2)
        )
    )
    candidate = QualityStateV2(
        **_quality_state_kwargs(
            safety=QualitySafetyDimensionsV1(unsupported_positive_claims=1),
            content=QualityContentDimensionsV1(supported_must_cover=3),
        )
    )
    assert quality_state_dominates(candidate, incumbent) is False


def test_quality_state_dominates_rejects_supported_must_cover_loss() -> None:
    incumbent = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(supported_must_cover=3)
        )
    )
    candidate = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(supported_must_cover=2)
        )
    )
    assert quality_state_dominates(candidate, incumbent) is False


def test_quality_state_dominates_rejects_no_improvement() -> None:
    # Same dimensions -> not dominated (Pareto rule requires improvement).
    incumbent = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(supported_must_cover=2)
        )
    )
    candidate = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(supported_must_cover=2)
        )
    )
    assert quality_state_dominates(candidate, incumbent) is False


def test_quality_state_dominates_accepts_minimality_improvement() -> None:
    incumbent = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(
                terminal_must_cover=3,
                supported_must_cover=2,
                unique_supported_claims=2,
                validated_final_sentences=2,
            ),
            minimality=QualityMinimalityDimensionsV1(duplicate_claims=3),
        )
    )
    candidate = QualityStateV2(
        **_quality_state_kwargs(
            content=QualityContentDimensionsV1(
                terminal_must_cover=3,
                supported_must_cover=2,
                unique_supported_claims=2,
                validated_final_sentences=2,
            ),
            minimality=QualityMinimalityDimensionsV1(duplicate_claims=1),
        )
    )
    assert quality_state_dominates(candidate, incumbent) is True


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


def test_per_obligation_budget_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PerObligationBudgetV1(obligation_id="OBL-1", surprise=True)  # type: ignore[call-arg]


def test_per_obligation_budget_rejects_unknown_tool_kind() -> None:
    with pytest.raises(ValidationError):
        PerObligationBudgetV1(obligation_id="OBL-1", limits={"invented_kind": 5})  # type: ignore[dict-item]


def test_per_obligation_budget_consume_and_remaining() -> None:
    budget = PerObligationBudgetV1(
        obligation_id="OBL-1",
        limits={"symbol_search": 5, "code_read": 3},
    )
    assert budget.remaining("symbol_search") == 5
    consumed = budget.consume("symbol_search", 2)
    assert consumed.remaining("symbol_search") == 3
    assert consumed.remaining("code_read") == 3
    # Consume past the limit just clamps at zero.
    over = consumed.consume("symbol_search", 100)
    assert over.remaining("symbol_search") == 0


def test_global_safety_budget_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GlobalSafetyBudgetV1(surprise=True)  # type: ignore[call-arg]


def test_global_safety_budget_rejects_negative() -> None:
    with pytest.raises(ValidationError):
        GlobalSafetyBudgetV1(max_total_tool_calls=-1)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


def test_research_actions_canonical() -> None:
    assert "STOP_BLOCKED" in RESEARCH_ACTIONS
    assert "SEARCH_SYMBOLS" in RESEARCH_ACTIONS
    assert len(RESEARCH_ACTIONS) == 15


def test_tool_kinds_canonical() -> None:
    assert "symbol_search" in TOOL_KINDS
    assert "other" in TOOL_KINDS
    assert len(TOOL_KINDS) == 10


def test_budget_tool_kinds_subset_of_tool_kinds() -> None:
    assert set(BUDGET_TOOL_KINDS).issubset(set(TOOL_KINDS))
    assert "other" not in BUDGET_TOOL_KINDS


def test_text_repair_failure_types_canonical() -> None:
    assert "wrong_span_role" in TEXT_REPAIR_FAILURE_TYPES
    assert "semantic_verifier_exhausted" in TEXT_REPAIR_FAILURE_TYPES


def test_text_repair_scopes_canonical() -> None:
    assert "wording_only" in TEXT_REPAIR_SCOPES
    assert "drop_or_gap" in TEXT_REPAIR_SCOPES


# ---------------------------------------------------------------------------
# TypedBehaviorTargetV1 / GapRequirementV1
# ---------------------------------------------------------------------------


def test_typed_behavior_target_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TypedBehaviorTargetV1(target_id="T-1", surprise=True)  # type: ignore[call-arg]


def test_gap_requirement_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        GapRequirementV1(requirement_id="G-1", description="x", surprise=True)  # type: ignore[call-arg]
