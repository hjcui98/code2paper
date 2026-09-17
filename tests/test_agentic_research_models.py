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
    # R10: PROPOSE_TARGET_REVISION lets the manager submit a target revision
    # proposal.  It is a tool-calling action (the proposal is a tool call) and
    # the harness alone decides whether the proposal is applied.
    assert "PROPOSE_TARGET_REVISION" in RESEARCH_ACTIONS
    assert len(RESEARCH_ACTIONS) == 17


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


@pytest.mark.parametrize(
    ("initial_status", "updates", "expected_status"),
    [
        (
            "fact_promoted",
            {
                "status": "claim_promoted",
                "packet_ids": ("packet:terminal",),
                "claim_ids": ("claim:terminal",),
                "rejection_code": "",
            },
            "claim_promoted",
        ),
        (
            "behavior_built",
            {
                "status": "superseded",
                "disposition_reason": "replaced_by_compiled_evidence",
                "superseding_claim_ids": ("claim:terminal",),
                "superseding_compile_digest": "sha256:compile",
                "rejection_code": "",
            },
            "superseded",
        ),
        (
            "behavior_built",
            {
                "status": "not_selected",
                "disposition_reason": "observation_not_selected_for_compile",
                "rejection_code": "",
            },
            "not_selected",
        ),
        (
            "observed_unpromoted",
            {
                "status": "deferred",
                "disposition_reason": "non_core_observation_deferred_to_review",
                "rejection_code": "",
            },
            "deferred",
        ),
    ],
)
def test_terminal_disposition_recomputes_record_and_ledger_digest(
    initial_status: str,
    updates: dict,
    expected_status: str,
) -> None:
    from code2paper.agentic.digest import digest_json
    from code2paper.agentic.research_promotion import (
        ObservationPromotionLedgerV1,
        ObservationPromotionRecordV1,
        _replace_promotion_record,
    )

    original = ObservationPromotionRecordV1(
        observation_id=f"observation:{expected_status}",
        obligation_id="OBL-TERMINAL",
        tool_name="read_code_span",
        status=initial_status,
        behavior_node_ids=("node:terminal",),
        packet_ids=("packet:original",),
        fact_ids=("fact:terminal",),
        rejection_code="terminal_probe",
    )
    updated = _replace_promotion_record(original, updates)
    assert updated.status == expected_status
    assert updated.content_digest != original.content_digest
    assert updated.content_digest == digest_json(
        updated.model_dump(mode="json", exclude={"content_digest"})
    )

    ledger = ObservationPromotionLedgerV1(records=(updated,))
    reloaded = ObservationPromotionLedgerV1.model_validate_json(
        ledger.model_dump_json()
    )
    assert reloaded.content_digest == ledger.content_digest
    assert reloaded.records[0].content_digest == updated.content_digest


def test_promotion_record_rejects_model_copy_updates() -> None:
    from code2paper.agentic.research_promotion import ObservationPromotionRecordV1

    record = ObservationPromotionRecordV1(
        observation_id="observation:copy",
        obligation_id="OBL-COPY",
        tool_name="read_symbol",
        status="behavior_built",
        behavior_node_ids=("node:copy",),
        rejection_code="evidence_packet_not_emitted",
    )
    with pytest.raises(ValueError, match="model_copy"):
        record.model_copy(update={"status": "deferred"})


def test_observation_terminal_disposition_survives_ledger_persistence() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.digest import digest_json
    from code2paper.agentic.research_promotion import (
        INCOMPLETE_PROMOTION_STATUSES,
        ObservationPromotionLedgerV1,
        build_observation_promotion_ledger,
    )

    span_id = "span:train.py:3:3"
    observation = SimpleNamespace(
        observation_id="observation:config-later-compiled",
        obligation_id="OBL-LATER",
        tool_name="inspect_configuration",
        status="success",
        source_authority="executable_hard",
        result_refs=("config:train.py:3:lr",),
        exact_span_ids=(span_id,),
        notebook=SimpleNamespace(discovered_symbols=()),
    )
    graph = SimpleNamespace(nodes=(
        SimpleNamespace(
            node_id="node:parse_args",
            symbol_id="symbol:train.py:parse_args:1",
            source_span_id="span:train.py:1:5",
        ),
    ))

    before = build_observation_promotion_ledger(
        observations=(observation,),
        behavior_graph=graph,
        repo_snapshot_id="snap-before",
        project_tree_hash="tree-before",
    )
    record_before = next(
        record for record in before.records
        if record.observation_id == observation.observation_id
    )
    assert record_before.status in INCOMPLETE_PROMOTION_STATUSES

    compiled = SimpleNamespace(
        packet_set=SimpleNamespace(packets=(
            {
                "packet_id": "packet:later",
                "anchor_span_ids": [span_id],
                "spans": [{"span_id": span_id}],
            },
        )),
        fact_set=SimpleNamespace(facts=(
            {"fact_id": "fact:later", "direct_span_ids": [span_id]},
        )),
        claim_set=SimpleNamespace(
            claims=({"claim_id": "claim:later", "fact_ids": ["fact:later"]},),
            content_digest="sha256:later",
        ),
    )
    after = build_observation_promotion_ledger(
        observations=(observation,),
        behavior_graph=graph,
        compiled_by_obligation={"OBL-LATER": compiled},
        repo_snapshot_id="snap-after",
        project_tree_hash="tree-after",
    )
    record_after = next(
        record for record in after.records
        if record.observation_id == observation.observation_id
    )
    assert record_after.status == "claim_promoted"
    assert record_after.claim_ids == ("claim:later",)
    assert record_after.content_digest != record_before.content_digest
    assert record_after.content_digest == digest_json(
        record_after.model_dump(mode="json", exclude={"content_digest"})
    )

    reloaded = ObservationPromotionLedgerV1.model_validate_json(
        after.model_dump_json()
    )
    assert reloaded.content_digest == after.content_digest
    reloaded_record = next(
        record for record in reloaded.records
        if record.observation_id == observation.observation_id
    )
    assert reloaded_record.status == record_after.status
    assert reloaded_record.content_digest == record_after.content_digest


def test_unbound_must_cover_probe_is_not_selected_for_a_frozen_compile() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.research_promotion import (
        ObservationPromotionLedgerV1,
        build_observation_promotion_ledger,
        promotion_record_blocks_candidate,
        promotion_record_blocks_strict_research,
    )

    probe_span = "span:conf/model.yaml:1:4"
    source_span = "span:src/model.py:10:12"
    observation = SimpleNamespace(
        observation_id="observation:yaml-probe",
        obligation_id="OBL-CORE",
        tool_name="read_code_span",
        status="success",
        source_authority="executable_hard",
        result_refs=(),
        exact_span_ids=(probe_span,),
        notebook=SimpleNamespace(discovered_symbols=()),
    )
    graph = SimpleNamespace(nodes=(
        SimpleNamespace(
            node_id="node:core",
            symbol_id="sym:core",
            source_span_id=source_span,
        ),
    ))
    compiled = SimpleNamespace(
        packet_set=SimpleNamespace(packets=(
            SimpleNamespace(
                packet_id="packet:core",
                anchor_span_ids=(source_span,),
                spans=(SimpleNamespace(span_id=source_span),),
                relations=(),
            ),
        )),
        fact_set=SimpleNamespace(facts=(
            SimpleNamespace(
                fact_id="fact:core",
                direct_span_ids=(source_span,),
                relation_span_ids=(),
            ),
        )),
        claim_set=SimpleNamespace(
            claims=(SimpleNamespace(claim_id="claim:core", fact_ids=("fact:core",)),),
            content_digest="sha256:core",
        ),
    )
    item = ResearchAgendaItemV1(
        obligation_id="OBL-CORE",
        priority="must_cover",
        status="supported",
        supported_claim_ids=["claim:core"],
        attempted_actions=["READ_CANDIDATE"],
    )

    ledger = build_observation_promotion_ledger(
        observations=(observation,),
        behavior_graph=graph,
        compiled_by_obligation={"OBL-CORE": compiled},
        agenda_items=(item,),
        repo_snapshot_id="snap",
        project_tree_hash="tree",
    )
    record = next(
        record for record in ledger.records
        if record.observation_id == observation.observation_id
    )
    assert record.status == "not_selected"
    assert record.disposition_reason == "observation_not_selected_for_compile"
    assert promotion_record_blocks_candidate(record, None, item) is False
    assert promotion_record_blocks_strict_research(record) is False

    reloaded = ObservationPromotionLedgerV1.model_validate_json(
        ledger.model_dump_json()
    )
    assert reloaded.content_digest == ledger.content_digest


def test_configuration_observation_stays_in_separate_evidence_lane() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.research_promotion import (
        build_observation_promotion_ledger,
    )

    observation = SimpleNamespace(
        observation_id="obs:config:1",
        obligation_id="OBL-CONFIG",
        tool_name="inspect_configuration",
        status="success",
        source_authority="executable_hard",
        result_refs=("config:train.py:3:lr",),
        exact_span_ids=("span:train.py:3:3",),
    )
    graph = SimpleNamespace(nodes=(SimpleNamespace(
        node_id="node:parse_args",
        symbol_id="symbol:train.py:parse_args:1",
        source_span_id="span:train.py:1:5",
    ),))

    ledger = build_observation_promotion_ledger(
        observations=(observation,),
        behavior_graph=graph,
        repo_snapshot_id="snap-config",
        project_tree_hash="tree-config",
    )
    record = ledger.records[0]

    assert record.evidence_lane == "configuration"
    assert record.status == "observed_unpromoted"
    assert record.rejection_code.startswith("configuration_")
    assert record.rejection_code != "no_matching_behavior_node"


def test_observation_promotion_joins_only_its_own_lineage() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.research_promotion import (
        build_observation_promotion_ledger,
    )

    span_one = "span:src/model.py:10:10"
    span_two = "span:src/model.py:20:20"
    graph = SimpleNamespace(nodes=(
        SimpleNamespace(
            node_id="node:one",
            symbol_id="sym:one",
            source_span_id=span_one,
        ),
        SimpleNamespace(
            node_id="node:two",
            symbol_id="sym:two",
            source_span_id=span_two,
        ),
    ))
    symbols = (
        SimpleNamespace(
            symbol_id="sym:one",
            path="src/model.py",
            qualified_name="Model.one",
            start_line=10,
            end_line=12,
        ),
        SimpleNamespace(
            symbol_id="sym:two",
            path="src/model.py",
            qualified_name="Model.two",
            start_line=20,
            end_line=22,
        ),
    )
    compiled = SimpleNamespace(
        packet_set=SimpleNamespace(packets=(
            {
                "packet_id": "packet:one",
                "anchor_span_ids": [span_one],
                "spans": [{"span_id": span_one}],
            },
            {
                "packet_id": "packet:two",
                "anchor_span_ids": [span_two],
                "spans": [{"span_id": span_two}],
            },
        )),
        fact_set=SimpleNamespace(facts=(
            {"fact_id": "fact:one", "direct_span_ids": [span_one]},
            {"fact_id": "fact:two", "direct_span_ids": [span_two]},
        )),
        claim_set=SimpleNamespace(claims=(
            {"claim_id": "claim:one", "fact_ids": ["fact:one"]},
            {"claim_id": "claim:two", "fact_ids": ["fact:two"]},
        )),
    )
    observations = (
        SimpleNamespace(
            observation_id="observation:one",
            obligation_id="OBL-LINEAGE",
            tool_name="read_symbol",
            status="success",
            result_refs=("symbol:src/model.py:one:10",),
            # A legacy/wide read excerpt must not license the sibling symbol.
            exact_span_ids=("span:src/model.py:10:20",),
            notebook=SimpleNamespace(discovered_symbols=()),
        ),
        SimpleNamespace(
            observation_id="observation:two",
            obligation_id="OBL-LINEAGE",
            tool_name="read_code_span",
            status="success",
            result_refs=("node:two",),
            exact_span_ids=(span_two,),
            notebook=SimpleNamespace(discovered_symbols=()),
        ),
    )

    ledger = build_observation_promotion_ledger(
        observations=observations,
        behavior_graph=graph,
        compiled_by_obligation={"OBL-LINEAGE": compiled},
        symbols=symbols,
        repo_snapshot_id="snap-lineage",
        project_tree_hash="tree-lineage",
    )
    records = {record.observation_id: record for record in ledger.records}
    assert records["observation:one"].status == "claim_promoted"
    assert records["observation:one"].behavior_node_ids == ("node:one",)
    assert records["observation:one"].packet_ids == ("packet:one",)
    assert records["observation:one"].fact_ids == ("fact:one",)
    assert records["observation:one"].claim_ids == ("claim:one",)
    assert records["observation:two"].behavior_node_ids == ("node:two",)
    assert records["observation:two"].packet_ids == ("packet:two",)
    assert records["observation:two"].fact_ids == ("fact:two",)
    assert records["observation:two"].claim_ids == ("claim:two",)


def test_partial_obligation_requires_the_complete_terminal_proof() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.research_terminal import (
        evaluate_obligation_terminal_proof,
    )

    item = ResearchAgendaItemV1(
        **_agenda_item_kwargs(
            status="partial",
            missing_information=["typed_predicate:normalize"],
        )
    )
    promoted = SimpleNamespace(
        status="claim_promoted",
        claim_ids=("claim:partial",),
    )
    before_gap = evaluate_obligation_terminal_proof(
        item,
        promotion_records=(promoted,),
    )
    assert not before_gap.terminal
    assert "explicit_gap_not_bound_to_missing_field" in before_gap.reasons

    # R9: an ``explicit_gap`` marker alone is a claim, not evidence.  The
    # complete terminal proof now also requires a typed disposition whose
    # receipt carries the execution layer's authentication verdict.
    item.gap_requirements.append(GapRequirementV1(
        requirement_id="gap:partial",
        description="The normalization remainder was exhaustively searched.",
        required_predicate="normalize",
        terminal="explicit_gap",
        allowed_wording_boundary="Only the observed normalization branch may be stated.",
    ))
    without_receipt = evaluate_obligation_terminal_proof(
        item,
        promotion_records=(promoted,),
    )
    assert not without_receipt.terminal
    assert "explicit_gap_not_bound_to_missing_field" in without_receipt.reasons
    assert "bounded_search_not_exhausted" in without_receipt.reasons
    assert not without_receipt.bounded_search_exhausted

    from code2paper.agentic.research_models import SearchReceiptV1

    item.gap_requirements[-1] = item.gap_requirements[-1].model_copy(update={
        "terminal_outcome": "unsupported_with_scoped_evidence",
        "negative_evidence_authorized": True,
        "search_receipt": SearchReceiptV1(
            receipt_id="receipt:partial",
            obligation_id=item.obligation_id,
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:test-tree",
            queries=("normalize hidden state",),
            filter_scope=("model.py",),
            top_k=10,
            read_candidate_ids=("sym:normalize",),
            # R9: terminal consumers require the execution layer's verdict.
            ledger_digest="sha256:ledger",
            execution_record_ids=("exec:partial",),
            authentication="ledger_verified",
        ),
    })
    # R9 correction: the current-revision re-authentication adapter is what
    # turns a stored receipt into a proved negative conclusion.
    from code2paper.agentic.research_models import SearchReceiptV1 as _Receipt

    def _verifier(receipt_id: str) -> _Receipt:
        declared = item.gap_requirements[-1].search_receipt
        assert declared is not None
        return declared

    after_gap = evaluate_obligation_terminal_proof(
        item,
        promotion_records=(promoted,),
        receipt_verifier=_verifier,
    )
    assert after_gap.terminal
    assert after_gap.promoted_repository_evidence
    assert after_gap.bounded_search_exhausted
    assert after_gap.explicit_gap_bound


def test_compact_symbol_refs_resolve_only_when_unique() -> None:
    """R4: a compact path/name ref never binds an arbitrary first match."""

    from code2paper.agentic.implementation_scope import _canonical_symbol_id

    symbols = {
        "sym:a-forward": {
            "symbol_id": "sym:a-forward",
            "path": "src/model.py",
            "qualified_name": "ModelA.forward",
        },
        "sym:b-forward": {
            "symbol_id": "sym:b-forward",
            "path": "src/model.py",
            "qualified_name": "ModelB.forward",
        },
        "sym:solo": {
            "symbol_id": "sym:solo",
            "path": "src/utils.py",
            "qualified_name": "helper",
        },
    }

    # Exact id and unique compact forms resolve.
    assert _canonical_symbol_id("sym:a-forward", symbols) == "sym:a-forward"
    assert (
        _canonical_symbol_id("src/model.py:ModelA.forward", symbols)
        == "sym:a-forward"
    )
    assert _canonical_symbol_id("src/utils.py:helper", symbols) == "sym:solo"
    assert _canonical_symbol_id("src/utils.py", symbols) == "sym:solo"

    # A leaf-name collision in one file and a path hosting several symbols
    # stay ambiguous instead of picking the first match.
    assert _canonical_symbol_id("src/model.py:forward", symbols) == "src/model.py:forward"
    assert _canonical_symbol_id("src/model.py", symbols) == "src/model.py"
    assert _canonical_symbol_id("missing.py:forward", symbols) == "missing.py:forward"


def test_observation_without_behavior_nodes_superseded_not_promoted() -> None:
    """An observation without behavior nodes cannot be claim_promoted; it is superseded."""
    from types import SimpleNamespace
    from code2paper.agentic.research_promotion import build_observation_promotion_ledger

    span_id = "span:config.yaml:10:10"
    observation = SimpleNamespace(
        observation_id="observation:config-no-node",
        obligation_id="OBL-1",
        tool_name="inspect_configuration",
        status="success",
        source_authority="executable_hard",
        result_refs=("config:config.yaml:10",),
        exact_span_ids=(span_id,),
        notebook=SimpleNamespace(discovered_symbols=()),
    )
    # Graph has no behavior nodes matching this span
    graph = SimpleNamespace(nodes=())

    compiled = SimpleNamespace(
        packet_set=SimpleNamespace(packets=(
            {
                "packet_id": "packet:1",
                "anchor_span_ids": [span_id],
                "spans": [{"span_id": span_id}],
            },
        )),
        fact_set=SimpleNamespace(facts=(
            {"fact_id": "fact:1", "direct_span_ids": [span_id]},
        )),
        claim_set=SimpleNamespace(
            claims=({"claim_id": "claim:1", "fact_ids": ["fact:1"]},),
            content_digest="sha256:1",
        ),
    )
    ledger = build_observation_promotion_ledger(
        observations=(observation,),
        behavior_graph=graph,
        compiled_by_obligation={"OBL-1": compiled},
        repo_snapshot_id="snap-1",
        project_tree_hash="tree-1",
    )
    record = next(
        r for r in ledger.records if r.observation_id == observation.observation_id
    )
    assert record.status == "superseded"
    assert record.disposition_reason == "replaced_by_compiled_evidence"
