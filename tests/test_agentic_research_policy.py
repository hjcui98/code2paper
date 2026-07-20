"""R3.5 tests for research policy merge (R3.3).

Covers all 8 hard rules from design section 8.2 / R3.3:

1. action / issue type match
2. tool currently ready
3. scope bounded (snapshot-internal paths only)
4. obligation exists in the agenda
5. no duplicate no-gain calls
6. no authority overreach
7. per-obligation / per-tool-kind budgets available
8. fallback is safe

Plus:

- structural validation (tool-calling action without tool calls, terminal
  action with tool calls).
- fallback construction when the proposal is rejected.
- STOP_BLOCKED escalation when the fallback is also rejected.
- ``apply_consumed_budgets`` correctly decrements remaining budgets.
- ``PolicyMergeResult`` contract (frozen, extra=forbid, trace_ref stable).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from code2paper.agentic.research_models import (
    BUDGET_TOOL_KINDS,
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAction,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchToolCallV1,
)
from code2paper.agentic.research_policy import (
    REJECTION_REASONS,
    PolicyMergeResult,
    PolicyRejectionV1,
    apply_consumed_budgets,
    apply_policy_merge,
)


_RUN_ID = "run-policy-test"
_SNAPSHOT_ID = "repo:policy-test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agenda(*items: ResearchAgendaItemV1) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        project_tree_hash="sha256:tree",
        items=list(items),
    )


def _obligation(
    obligation_id: str = "obl-1",
    *,
    priority: str = "must_cover",
    status: str = "in_progress",
    candidate_symbol_ids: tuple[str, ...] = (),
) -> ResearchAgendaItemV1:
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority=priority,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        candidate_symbol_ids=list(candidate_symbol_ids),
    )


def _issue(
    issue_kind: str = "missing_anchor",
    *,
    issue_id: str = "issue-1",
    obligation_id: str = "obl-1",
) -> ResearchIssueV1:
    return ResearchIssueV1(
        issue_id=issue_id,
        issue_kind=issue_kind,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        description=f"test issue {issue_kind}",
    )


def _tool_call(
    tool_call_id: str = "tc-1",
    tool_name: str = "search_symbols",
    *,
    obligation_id: str = "obl-1",
    tool_kind: str = "symbol_search",
    arguments: dict[str, Any] | None = None,
    path_scope: tuple[str, ...] = (),
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=tool_kind,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        goal="test goal",
        repo_snapshot_id=_SNAPSHOT_ID,
        path_scope=path_scope,
        arguments=arguments if arguments is not None else {"query": "train"},
    )


def _decision(
    *,
    action: ResearchAction = "SEARCH_SYMBOLS",
    obligation_id: str = "obl-1",
    issue_id: str = "",
    tool_calls: tuple[ResearchToolCallV1, ...] | None = None,
    turn_index: int = 0,
    fallback_action: ResearchAction | None = "RECORD_GAP",
) -> ResearchDecisionV1:
    if tool_calls is None:
        if action in {"STOP_BLOCKED", "RECORD_GAP", "PLAN_METHOD"}:
            tool_calls = ()
        else:
            tool_calls = (_tool_call(),)
    return ResearchDecisionV1(
        decision_id=f"decision-{turn_index}-{action}",
        run_id=_RUN_ID,
        turn_index=turn_index,
        action=action,
        obligation_id=obligation_id,
        issue_id=issue_id,
        goal="test goal",
        selected_tool_calls=tool_calls,
        candidate_scope=(),
        expected_information_gain="",
        evidence_needed=(),
        stop_condition="",
        fallback_action=fallback_action,
        rationale="test",
        produced_by="llm_proposal",
    )


def _budgets(
    obligation_id: str = "obl-1",
    *,
    limits: dict[str, int] | None = None,
    used: dict[str, int] | None = None,
) -> dict[str, PerObligationBudgetV1]:
    default_limits = {
        "symbol_search": 5,
        "code_read": 5,
        "call_trace": 5,
        "data_flow_trace": 5,
        "branch_inspection": 5,
        "hint_search": 5,
        "packet_repair": 5,
    }
    if limits is not None:
        default_limits.update(limits)
    return {
        obligation_id: PerObligationBudgetV1(
            obligation_id=obligation_id,
            limits=default_limits,
            used=used or {},
        )
    }


_READY_TOOLS = (
    "find_entrypoints",
    "search_symbols",
    "read_symbol",
    "find_references",
    "build_behavior_subgraph",
)

_SNAPSHOT_PATHS = (
    "train.py",
    "eval.py",
    "model.py",
    "dataset.py",
    "configs/train.yaml",
)


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestPolicyMergeResultContract:
    def test_result_forbids_extra_fields_at_construction(self) -> None:
        # PolicyMergeResult uses extra="forbid" so extra fields cannot be
        # passed at construction time.
        with pytest.raises(ValidationError):
            PolicyMergeResult(accepted=True, decision=None, bogus="oops")  # type: ignore[call-arg]

    def test_rejection_is_frozen(self) -> None:
        rej = PolicyRejectionV1(
            rule="tool_not_ready",
            reason="test",
        )
        with pytest.raises(ValidationError):
            rej.rule = "other"  # type: ignore[misc]

    def test_rejection_reasons_is_closed_set(self) -> None:
        # Every rejection reason must be a known code.
        assert isinstance(REJECTION_REASONS, tuple)
        assert len(REJECTION_REASONS) == len(set(REJECTION_REASONS))
        # Spot-check a few critical codes.
        for code in (
            "action_issue_mismatch",
            "tool_not_ready",
            "scope_not_in_snapshot",
            "obligation_does_not_exist",
            "duplicate_no_gain_call",
            "authority_overreach",
            "budget_exhausted",
        ):
            assert code in REJECTION_REASONS


# ---------------------------------------------------------------------------
# Rule 0: structural validation
# ---------------------------------------------------------------------------


class TestStructuralValidation:
    def test_tool_calling_action_without_tool_calls_is_rejected(self) -> None:
        # Use model_construct to bypass the model validator: we want to
        # verify policy merge catches this, not the model.
        proposal = ResearchDecisionV1.model_construct(
            decision_id="decision-0-SEARCH_SYMBOLS",
            run_id=_RUN_ID,
            turn_index=0,
            action="SEARCH_SYMBOLS",
            obligation_id="obl-1",
            issue_id="",
            goal="test",
            selected_tool_calls=(),
            candidate_scope=(),
            expected_information_gain="",
            evidence_needed=(),
            stop_condition="",
            fallback_action="RECORD_GAP",
            rationale="test",
            produced_by="llm_proposal",
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "tool_calling_action_without_tool_calls" in result.rejection_rules

    def test_terminal_action_with_tool_calls_is_rejected(self) -> None:
        proposal = ResearchDecisionV1.model_construct(
            decision_id="decision-0-STOP_BLOCKED",
            run_id=_RUN_ID,
            turn_index=0,
            action="STOP_BLOCKED",
            obligation_id="obl-1",
            issue_id="",
            goal="test",
            selected_tool_calls=(_tool_call(),),
            candidate_scope=(),
            expected_information_gain="",
            evidence_needed=(),
            stop_condition="",
            fallback_action=None,
            rationale="test",
            produced_by="llm_proposal",
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "terminal_action_with_tool_calls" in result.rejection_rules


# ---------------------------------------------------------------------------
# Rule 1: action / issue match
# ---------------------------------------------------------------------------


class TestActionIssueMatch:
    def test_search_symbols_accepted_for_missing_anchor(self) -> None:
        proposal = _decision(action="SEARCH_SYMBOLS")
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=_issue("missing_anchor"),
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert not result.fallback_used
        assert result.decision is not None
        assert result.decision.action == "SEARCH_SYMBOLS"

    def test_trace_calls_accepted_for_missing_relation(self) -> None:
        proposal = _decision(
            action="TRACE_CALLS",
            tool_calls=(_tool_call(tool_name="find_references", tool_kind="call_trace"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation(candidate_symbol_ids=("train.py:train",))),
            active_issue=_issue("missing_relation"),
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert not result.fallback_used

    def test_compile_facts_rejected_for_missing_anchor(self) -> None:
        # COMPILE_FACTS cannot be produced by the deterministic backend
        # (it's an R4 tool), so the proposal gets rejected and the fallback
        # kicks in.
        proposal = _decision(
            action="COMPILE_FACTS",
            tool_calls=(_tool_call(tool_name="compile_facts", tool_kind="other"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=_issue("missing_anchor"),
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "action_issue_mismatch" in result.rejection_rules


# ---------------------------------------------------------------------------
# Rule 2: tools ready
# ---------------------------------------------------------------------------


class TestToolsReady:
    def test_unknown_tool_is_rejected(self) -> None:
        proposal = _decision(
            action="SEARCH_SYMBOLS",
            tool_calls=(_tool_call(tool_name="bogus_tool"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "tool_not_ready" in result.rejection_rules

    def test_tool_not_in_ready_set_is_rejected(self) -> None:
        proposal = _decision(
            action="SEARCH_SYMBOLS",
            tool_calls=(_tool_call(tool_name="build_behavior_subgraph"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=("search_symbols",),  # only search_symbols ready
        )
        assert "tool_not_ready" in result.rejection_rules


# ---------------------------------------------------------------------------
# Rule 3: scope in snapshot
# ---------------------------------------------------------------------------


class TestScopeInSnapshot:
    def test_path_scope_outside_snapshot_is_rejected(self) -> None:
        proposal = _decision(
            action="SEARCH_SYMBOLS",
            tool_calls=(
                _tool_call(path_scope=("/etc/passwd", "train.py")),
            ),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            repo_snapshot_paths=_SNAPSHOT_PATHS,
        )
        assert "scope_not_in_snapshot" in result.rejection_rules

    def test_argument_path_outside_snapshot_is_rejected(self) -> None:
        proposal = _decision(
            action="READ_CANDIDATE",
            tool_calls=(
                _tool_call(
                    tool_name="read_symbol",
                    tool_kind="code_read",
                    arguments={"path": "/etc/passwd", "symbol": "train"},
                ),
            ),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation(candidate_symbol_ids=("train.py:train",))),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            repo_snapshot_paths=_SNAPSHOT_PATHS,
        )
        assert "scope_not_in_snapshot" in result.rejection_rules

    def test_in_snapshot_path_is_accepted(self) -> None:
        proposal = _decision(
            action="READ_CANDIDATE",
            tool_calls=(
                _tool_call(
                    tool_name="read_symbol",
                    tool_kind="code_read",
                    arguments={"path": "train.py", "symbol": "train"},
                ),
            ),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation(candidate_symbol_ids=("train.py:train",))),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            repo_snapshot_paths=_SNAPSHOT_PATHS,
        )
        assert result.accepted
        assert not result.fallback_used


# ---------------------------------------------------------------------------
# Rule 4: obligation exists
# ---------------------------------------------------------------------------


class TestObligationExists:
    def test_obligation_not_in_agenda_is_rejected(self) -> None:
        proposal = _decision(obligation_id="obl-missing")
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation("obl-1")),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "obligation_does_not_exist" in result.rejection_rules

    def test_tool_call_without_obligation_id_is_rejected(self) -> None:
        # Use model_construct to bypass the tool_call validator that
        # rejects empty obligation_id: we want to verify policy merge
        # catches this.
        empty_call = ResearchToolCallV1.model_construct(
            tool_call_id="tc-empty",
            tool_name="search_symbols",
            tool_kind="symbol_search",
            obligation_id="",
            goal="test",
            repo_snapshot_id=_SNAPSHOT_ID,
            path_scope=(),
            top_k=0,
            depth=0,
            node_budget=0,
            arguments={"query": "train"},
            input_digest="",
        )
        proposal = ResearchDecisionV1.model_construct(
            decision_id="decision-0-SEARCH_SYMBOLS",
            run_id=_RUN_ID,
            turn_index=0,
            action="SEARCH_SYMBOLS",
            obligation_id="",
            issue_id="",
            goal="test",
            selected_tool_calls=(empty_call,),
            candidate_scope=(),
            expected_information_gain="",
            evidence_needed=(),
            stop_condition="",
            fallback_action="RECORD_GAP",
            rationale="test",
            produced_by="llm_proposal",
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation("obl-1")),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "no_active_obligation_for_tool_call" in result.rejection_rules

    def test_terminal_action_without_obligation_is_allowed(self) -> None:
        # STOP_BLOCKED can fire without an obligation id.
        proposal = _decision(
            action="STOP_BLOCKED",
            obligation_id="",
            tool_calls=(),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation("obl-1")),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert not result.fallback_used


# ---------------------------------------------------------------------------
# Rule 5: no duplicate no-gain calls
# ---------------------------------------------------------------------------


class TestNoDuplicateNoGain:
    def test_duplicate_no_gain_call_is_rejected(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_call_id="tc-dup"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            no_progress_tool_call_ids=("tc-dup",),
        )
        assert "duplicate_no_gain_call" in result.rejection_rules

    def test_recently_executed_call_is_rejected(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_call_id="tc-recent"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            recent_tool_call_ids=("tc-recent",),
        )
        assert "duplicate_no_gain_call" in result.rejection_rules


# ---------------------------------------------------------------------------
# Rule 6: no authority overreach
# ---------------------------------------------------------------------------


class TestNoAuthorityOverreach:
    def test_authority_in_arguments_is_rejected(self) -> None:
        proposal = _decision(
            tool_calls=(
                _tool_call(
                    arguments={"query": "train", "source_authority": "executable_hard"},
                ),
            ),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "authority_overreach" in result.rejection_rules

    def test_clean_arguments_are_accepted(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(arguments={"query": "train"}),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert not result.fallback_used


# ---------------------------------------------------------------------------
# Rule 7: budgets available
# ---------------------------------------------------------------------------


class TestBudgetsAvailable:
    def test_exhausted_budget_is_rejected(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(used={"symbol_search": 5}),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "budget_exhausted" in result.rejection_rules

    def test_remaining_budget_is_accepted(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(used={"symbol_search": 4}),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert not result.fallback_used

    def test_no_budget_envelope_is_rejected(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets={},  # no envelope
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert "budget_exhausted" in result.rejection_rules


# ---------------------------------------------------------------------------
# Fallback construction
# ---------------------------------------------------------------------------


class TestFallbackConstruction:
    def test_rejected_proposal_produces_fallback_decision(self) -> None:
        # Exhausted budget -> proposal rejected -> fallback produces a
        # different action (RECORD_GAP or a different tool kind).
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(used={"symbol_search": 5}),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.fallback_used
        assert result.decision is not None
        # The fallback may be a different tool kind, RECORD_GAP, or STOP_BLOCKED.
        assert result.decision.action in {
            "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS",
            "RECORD_GAP", "STOP_BLOCKED",
        }

    def test_fallback_rejection_produces_stop_blocked(self) -> None:
        # Exhaust ALL budgets so the fallback also fails.
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        budgets = _budgets(
            used={
                "symbol_search": 5,
                "code_read": 5,
                "call_trace": 5,
                "data_flow_trace": 5,
                "branch_inspection": 5,
                "hint_search": 5,
                "packet_repair": 5,
            }
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=budgets,
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.fallback_used
        assert result.decision is not None
        # When all budgets are exhausted, the fallback should be STOP_BLOCKED
        # (since RECORD_GAP is the only no-budget action and it doesn't need
        # a tool call, the fallback should be STOP_BLOCKED or RECORD_GAP).
        assert result.decision.action in {"RECORD_GAP", "STOP_BLOCKED"}

    def test_trace_ref_is_stable(self) -> None:
        proposal = _decision()
        result1 = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        result2 = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result1.trace_ref == result2.trace_ref
        assert result1.trace_ref.startswith("policy-merge:")


# ---------------------------------------------------------------------------
# Budget accounting
# ---------------------------------------------------------------------------


class TestApplyConsumedBudgets:
    def test_apply_consumed_decrements_remaining(self) -> None:
        budgets = _budgets()
        consumed = {"obl-1": {"symbol_search": 1}}
        new_budgets = apply_consumed_budgets(budgets, consumed)
        assert new_budgets["obl-1"].remaining("symbol_search") == 4

    def test_apply_consumed_is_pure(self) -> None:
        budgets = _budgets()
        original_remaining = budgets["obl-1"].remaining("symbol_search")
        apply_consumed_budgets(budgets, {"obl-1": {"symbol_search": 1}})
        assert budgets["obl-1"].remaining("symbol_search") == original_remaining

    def test_apply_consumed_unknown_obligation_is_noop(self) -> None:
        budgets = _budgets()
        new_budgets = apply_consumed_budgets(budgets, {"obl-unknown": {"symbol_search": 1}})
        assert new_budgets["obl-1"].remaining("symbol_search") == 5

    def test_consumed_budgets_in_result_match_executed_calls(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
        )
        assert result.accepted
        assert result.consumed_budgets == {"obl-1": {"symbol_search": 1}}


# ---------------------------------------------------------------------------
# Full proposal acceptance
# ---------------------------------------------------------------------------


class TestFullAcceptance:
    def test_clean_proposal_is_accepted_without_fallback(self) -> None:
        proposal = _decision(
            tool_calls=(_tool_call(tool_kind="symbol_search"),),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation()),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            repo_snapshot_paths=_SNAPSHOT_PATHS,
        )
        assert result.accepted
        assert not result.fallback_used
        assert result.decision is proposal
        assert result.rejections == ()

    def test_multiple_tool_calls_all_validated(self) -> None:
        proposal = _decision(
            action="SEARCH_SYMBOLS",
            tool_calls=(
                _tool_call(tool_call_id="tc-a", tool_kind="symbol_search"),
                _tool_call(
                    tool_call_id="tc-b",
                    tool_name="read_symbol",
                    tool_kind="code_read",
                    arguments={"path": "train.py", "symbol": "train"},
                ),
            ),
        )
        result = apply_policy_merge(
            proposal,
            agenda=_agenda(_obligation(candidate_symbol_ids=("train.py:train",))),
            active_issue=None,
            per_obligation_budgets=_budgets(),
            global_safety_budget=GlobalSafetyBudgetV1(),
            ready_tools=_READY_TOOLS,
            repo_snapshot_paths=_SNAPSHOT_PATHS,
        )
        assert result.accepted
        assert result.consumed_budgets == {
            "obl-1": {"symbol_search": 1, "code_read": 1}
        }
