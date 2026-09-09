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
    # COMPILE_EVIDENCE was added so the Research Manager can submit the
    # deterministic evidence compiler once it judges the observations answer
    # the active issue (policy accepts it for any issue kind).
    assert "COMPILE_EVIDENCE" in RESEARCH_ACTIONS
    assert len(RESEARCH_ACTIONS) == 16


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


# ---------------------------------------------------------------------------
# P2: Scope fixtures (Domain-Pruning, FastGS, LearNAT)
# ---------------------------------------------------------------------------


def test_domain_pruning_vendor_exclusion() -> None:
    from code2paper.agentic.source_inventory import classify_source_kind
    from code2paper.agentic.implementation_scope import infer_implementation_scope

    assert classify_source_kind("sglang/srt/entrypoints/http_server.py") == "vendor"
    assert classify_source_kind("submodules/sglang/setup.py") == "vendor"
    assert classify_source_kind("sglang_pruned/models/llama.py") == "vendor"
    assert classify_source_kind("pruning/pruners/magnitude.py") == "first_party_executable"

    mock_symbols = [
        {"symbol_id": "sym:sglang:1", "name": "SGLangServer", "path": "sglang/srt/server.py", "kind": "class"},
        {"symbol_id": "sym:pruning:1", "name": "MagnitudePruner", "path": "pruning/magnitude.py", "kind": "class"},
    ]
    scope = infer_implementation_scope(mock_symbols, author_texts=["pruning", "magnitude"])
    assert "sym:sglang:1" not in scope.target_core_symbol_ids
    assert "sym:pruning:1" in scope.target_core_symbol_ids


def test_fastgs_densify_not_comparand() -> None:
    from code2paper.agentic.implementation_scope import infer_implementation_scope

    fastgs_symbols = [
        {
            "symbol_id": "sym:fastgs:1",
            "name": "densify_and_prune_fastgs",
            "path": "scene/gaussian_model.py",
            "qualified_name": "GaussianModel.densify_and_prune_fastgs",
            "docstring": "FastGS densification implementation without baseline comparison.",
            "kind": "method",
        },
        {
            "symbol_id": "sym:baseline:1",
            "name": "densify_and_prune_baseline",
            "path": "baseline/gaussian_model.py",
            "qualified_name": "BaselineGaussianModel.densify_and_prune",
            "docstring": "Baseline comparison model.",
            "kind": "method",
        },
    ]
    scope_fastgs = infer_implementation_scope(fastgs_symbols, author_texts=["FastGS", "densify", "prune"])
    assert "sym:fastgs:1" in scope_fastgs.target_core_symbol_ids
    assert "sym:fastgs:1" not in scope_fastgs.comparand_symbol_ids
    assert "sym:baseline:1" in scope_fastgs.comparand_symbol_ids


def test_learnat_mcts_target_core_ownership() -> None:
    from code2paper.agentic.implementation_scope import (
        infer_implementation_scope,
        scope_role_for_candidate,
    )

    learnat_symbols = [
        {
            "symbol_id": "sym:learnat:1",
            "name": "NL2SQLMCTS",
            "path": "src/search/mcts.py",
            "qualified_name": "NL2SQLMCTS",
            "docstring": "MCTS implementation for text-to-SQL search.",
            "kind": "class",
        }
    ]
    scope_learnat = infer_implementation_scope(learnat_symbols, author_texts=["LearNAT", "MCTS", "NL2SQLMCTS"])
    assert "sym:learnat:1" in scope_learnat.target_core_symbol_ids

    role = scope_role_for_candidate(
        scope_learnat,
        "symbol:src/search/mcts.py:NL2SQLMCTS:50",
        symbols=learnat_symbols,
    )
    assert role == "target_core"


def test_scope_entry_ranking_prefers_lifecycle_boundary_over_getter() -> None:
    from code2paper.agentic.implementation_scope import infer_implementation_scope

    symbols = [
        {
            "symbol_id": "sym:get-position",
            "path": "src/model.py",
            "qualified_name": "Reranker.get_passage_positional_encoding",
            "docstring": "Get sinusoidal passage position encoding for the model.",
            "kind": "method",
        },
        {
            "symbol_id": "sym:forward",
            "path": "src/model.py",
            "qualified_name": "Reranker.forward",
            "docstring": "Contextualize query and passage embeddings with document attention.",
            "kind": "method",
        },
        {
            "symbol_id": "sym:rerank",
            "path": "src/model.py",
            "qualified_name": "Reranker.rerank",
            "docstring": "Rerank passages from query and contextual passage embeddings.",
            "kind": "method",
        },
    ]

    scope = infer_implementation_scope(
        symbols,
        author_texts=(
            "Rerank passages by contextualizing query and passage embeddings "
            "with document attention and positional encoding.",
        ),
    )

    assert scope.target_entry_symbol_ids
    assert "sym:get-position" not in scope.target_entry_symbol_ids
    assert set(scope.target_entry_symbol_ids) <= {"sym:forward", "sym:rerank"}
    assert scope.entry_inference_status == "lifecycle"
    # Lexical overlap must not promote a helper into the target core either.
    assert "sym:get-position" not in scope.target_core_symbol_ids
    assert {"sym:forward", "sym:rerank"} & set(scope.target_core_symbol_ids)


def test_scope_entry_status_reports_explicit_and_ambiguous_lanes() -> None:
    from code2paper.agentic.implementation_scope import infer_implementation_scope

    explicit = infer_implementation_scope(
        [
            {"symbol_id": "sym:a", "path": "a.py", "qualified_name": "A.forward", "kind": "method"},
        ],
        entry_symbol_ids=("sym:a",),
    )
    assert explicit.entry_inference_status == "explicit"
    assert explicit.target_entry_symbol_ids == ("sym:a",)

    ambiguous_symbols = [
        {"symbol_id": f"sym:{index}", "path": f"m{index}.py",
         "qualified_name": f"Model{index}.forward", "kind": "method"}
        for index in range(3)
    ]
    ambiguous = infer_implementation_scope(ambiguous_symbols)
    assert ambiguous.target_entry_symbol_ids == ()
    assert ambiguous.entry_inference_status == "unresolved_ambiguous"


def test_scope_helper_is_dependency_only_when_the_entry_calls_it() -> None:
    from code2paper.agentic.implementation_scope import infer_implementation_scope

    symbols = [
        {
            "symbol_id": "sym:forward",
            "path": "src/model.py",
            "qualified_name": "Reranker.forward",
            "docstring": "Contextualize query and passage embeddings.",
            "kind": "method",
        },
        {
            "symbol_id": "sym:get-position",
            "path": "src/model.py",
            "qualified_name": "Reranker.get_passage_positional_encoding",
            "docstring": "Get sinusoidal passage position encoding for the model.",
            "kind": "method",
        },
    ]

    class _Graph:
        def __init__(self) -> None:
            self.nodes = [
                {"node_id": "n:forward", "symbol_id": "sym:forward"},
                {"node_id": "n:get", "symbol_id": "sym:get-position"},
            ]
            self.relations = [
                {
                    "relation_id": "rel:calls",
                    "kind": "CALLS",
                    "source_node_id": "n:forward",
                    "target_node_id": "n:get",
                },
            ]

    scope = infer_implementation_scope(
        symbols,
        author_texts=("Contextualize query and passage embeddings.",),
        entry_symbol_ids=("sym:forward",),
        behavior_graph=_Graph(),
    )

    assert scope.target_entry_symbol_ids == ("sym:forward",)
    assert "sym:forward" in scope.target_core_symbol_ids
    assert "sym:get-position" not in scope.target_core_symbol_ids
    assert "sym:get-position" in scope.target_dependency_symbol_ids


# ---------------------------------------------------------------------------
# P3: Observation promotion ledger
# ---------------------------------------------------------------------------


def test_observation_promotion_ledger_lifecycle() -> None:
    from code2paper.agentic.research_promotion import (
        build_observation_promotion_ledger,
    )

    observations = [
        {
            "observation_id": "obs:search:1",
            "obligation_id": "OBL-1",
            "tool_name": "search_symbols",
            "status": "success",
            "result_refs": ["sym:candidate:1"],
        },
        {
            "observation_id": "obs:failed:1",
            "obligation_id": "OBL-1",
            "tool_name": "read_symbol",
            "status": "error",
            "result_refs": ["sym:candidate:1"],
        },
        {
            "observation_id": "obs:read_no_span:1",
            "obligation_id": "OBL-1",
            "tool_name": "read_symbol",
            "status": "success",
            "result_refs": ["sym:candidate:1"],
        },
        {
            "observation_id": "obs:promoted:1",
            "obligation_id": "OBL-2",
            "tool_name": "read_code_span",
            "status": "success",
            "exact_span_ids": ["span:src/core.py:10:20"],
            "result_refs": ["node:1"],
        },
    ]

    class MockNode:
        node_id = "node:1"
        symbol_id = "sym:core:1"
        source_span_id = "span:src/core.py:10:20"

    class MockGraph:
        nodes = [MockNode()]

    compiled_by_obligation = {
        "OBL-2": {
            "packet_set": {"packets": [{"packet_id": "pkt:1"}]},
            "fact_set": {"facts": [{"fact_id": "f:1"}]},
            "claim_set": {"claims": [{"claim_id": "c:1"}]},
        }
    }

    ledger = build_observation_promotion_ledger(
        observations=observations,
        behavior_graph=MockGraph(),
        compiled_by_obligation=compiled_by_obligation,
        repo_snapshot_id="snap-1",
        project_tree_hash="hash-1",
    )

    assert len(ledger.records) == 4
    records_by_id = {r.observation_id: r for r in ledger.records}

    assert records_by_id["obs:search:1"].status == "discovered_only"
    assert records_by_id["obs:search:1"].rejection_code == "discovery_refs_are_not_evidence"

    assert records_by_id["obs:failed:1"].status == "rejected"
    assert records_by_id["obs:failed:1"].rejection_code == "observation_failed"

    assert records_by_id["obs:read_no_span:1"].status == "observed_unpromoted"
    assert records_by_id["obs:read_no_span:1"].rejection_code == "exact_source_span_missing"

    assert records_by_id["obs:promoted:1"].status == "claim_promoted"
    assert records_by_id["obs:promoted:1"].claim_ids == ("c:1",)
    assert records_by_id["obs:promoted:1"].rejection_code == ""
