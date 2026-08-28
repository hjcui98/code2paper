"""R3.5 tests for the research supervisor (R3.1 + R3.2).

Covers:

- ``ResearchDecisionContextV1`` contract (frozen, extra=forbid, validators).
- ``RecentObservationSummaryV1`` contract.
- ``SupervisorBackend`` protocol is runtime-checkable.
- ``DeterministicSupervisorBackend`` produces valid ``ResearchDecisionV1``
  proposals for every issue kind in the fallback table.
- ``build_decision_context`` assembles a compact context from graph state
  without leaking full observations or source code.
- ``fallback_action_for_issue`` covers every issue kind.
- ``supervisor_node`` returns the right state update shape.

Exit condition (R3.5): the deterministic backend can drive the supervisor
node for every issue kind, and the context it builds is small enough that
no raw source / full observation payload leaks through.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from code2paper.agentic.research_models import (
    RESEARCH_ACTIONS,
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAction,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationDiagnosticsV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    TypedBehaviorTargetV1,
    make_observation,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    ExecutedToolCallSummaryV1,
    RecentObservationSummaryV1,
    ResearchDecisionContextV1,
    SupervisorBackend,
    all_fallback_issue_kinds,
    build_decision_context,
    fallback_action_for_issue,
    supervisor_node,
    _salient_author_search_terms,
)
from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.repo_snapshot import build_repo_snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_RUN_ID = "run-supervisor-test"
_SNAPSHOT_ID = "repo:abc123"
_TREE_HASH = "sha256:tree"


def test_salient_author_search_terms_prioritize_named_implementation_family() -> None:
    terms = _salient_author_search_terms(
        "Extract a long interaction sequence with temporal context and then "
        "pass it through Acme-StateEncoder before an MLP head."
    )

    assert terms[:2] == ("acme-stateencoder", "mlp")
    assert "extract" in terms


def test_search_query_prefers_active_typed_target_before_project_goal_prose() -> None:
    obligation = ResearchAgendaItemV1(
        obligation_id="obl-lifecycle",
        priority="should_cover",
        author_text=(
            "Develop a retrieval augmented generation system that handles "
            "large corpora using entity graph indexing."
        ),
        typed_behavior_targets=[
            TypedBehaviorTargetV1(
                target_id="target-index",
                role="graph_builder",
                desired_predicates=("CALL", "WRITE"),
                predicate_groups=(("CALL", "WRITE"),),
                search_terms=("graph index", "indexing"),
                aliases=("graph_builder",),
                transformations=("indexing",),
            )
        ],
    )
    context = ResearchDecisionContextV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=0,
        active_obligation=obligation,
        allowed_actions=("SEARCH_SYMBOLS",),
    )

    query = DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )._search_query(context)

    assert query == "indexing"


def test_search_query_expands_generation_semantic_repair_aliases() -> None:
    obligation = _obligation(
        missing_information=("typed_semantic:transformations:generation",),
    )
    context = ResearchDecisionContextV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=0,
        active_obligation=obligation,
        allowed_actions=("SEARCH_SYMBOLS",),
    )

    query = DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )._search_query(context)

    assert query == "generation generate infer answer qa"


def test_search_query_expands_numeric_dimension_semantics_to_code_identifiers() -> None:
    obligation = _obligation(
        missing_information=("typed_semantic:outputs:dimension 15",),
    )
    context = ResearchDecisionContextV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=0,
        active_obligation=obligation,
        allowed_actions=("SEARCH_SYMBOLS",),
    )

    query = DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )._search_query(context)

    assert "input_dim" in query
    assert "f15" in query


def test_search_query_routes_answer_output_repair_to_qa_endpoint() -> None:
    obligation = _obligation(
        missing_information=("typed_semantic:outputs:answer",),
    )
    context = ResearchDecisionContextV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=0,
        active_obligation=obligation,
        allowed_actions=("SEARCH_SYMBOLS",),
    )

    query = DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )._search_query(context)

    assert query == "answer infer qa"


def _agenda(*items: ResearchAgendaItemV1) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        project_tree_hash=_TREE_HASH,
        items=list(items),
    )


def _obligation(
    obligation_id: str = "obl-1",
    *,
    priority: str = "must_cover",
    status: str = "in_progress",
    candidate_symbol_ids: tuple[str, ...] = (),
    candidate_behavior_node_ids: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    typed_targets: tuple[TypedBehaviorTargetV1, ...] = (),
) -> ResearchAgendaItemV1:
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority=priority,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        candidate_symbol_ids=list(candidate_symbol_ids),
        candidate_behavior_node_ids=list(candidate_behavior_node_ids),
        missing_information=list(missing_information),
        typed_behavior_targets=list(typed_targets),
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
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=tool_kind,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        goal="test goal",
        repo_snapshot_id=_SNAPSHOT_ID,
        arguments={"query": "train"},
    )


def _observation(
    tool_call: ResearchToolCallV1,
    *,
    status: str = "success",
    result_refs: tuple[str, ...] = ("symbol:train.py:train",),
    exact_span_ids: tuple[str, ...] = ("span:train.py:10-20",),
) -> ResearchObservationV1:
    return make_observation(
        tool_call=tool_call,
        status=status,  # type: ignore[arg-type]
        result_refs=result_refs,
        exact_span_ids=exact_span_ids,
    )


def _context(
    *,
    active_obligation: ResearchAgendaItemV1 | None = None,
    active_issue: ResearchIssueV1 | None = None,
    no_progress_counter: int = 0,
    recent_observations: tuple[ResearchObservationV1, ...] = (),
    executed_tool_calls: tuple[ExecutedToolCallSummaryV1, ...] = (),
    behavior_graph: Any | None = None,
    per_obligation_budgets: dict[str, PerObligationBudgetV1] | None = None,
    turn_index: int = 0,
) -> ResearchDecisionContextV1:
    agenda = _agenda(active_obligation) if active_obligation else None
    return build_decision_context(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=turn_index,
        agenda=agenda,
        active_obligation_id=active_obligation.obligation_id if active_obligation else "",
        active_issue=active_issue,
        recent_observations=recent_observations,
        executed_tool_calls=executed_tool_calls,
        behavior_graph=behavior_graph,
        per_obligation_budgets=per_obligation_budgets or {},
        global_safety_budget=GlobalSafetyBudgetV1(),
        no_progress_counter=no_progress_counter,
        ready_tools=("find_entrypoints", "search_symbols", "read_symbol", "find_references"),
        hard_rules=("no_snapshot_external_paths",),
    )


def _backend() -> DeterministicSupervisorBackend:
    return DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        ready_tools=("find_entrypoints", "search_symbols", "read_symbol", "find_references"),
    )


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestResearchDecisionContextContract:
    def test_context_is_frozen(self) -> None:
        ctx = _context()
        with pytest.raises(ValidationError):
            ctx.run_id = "other"  # type: ignore[misc]

    def test_context_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ResearchDecisionContextV1(
                run_id=_RUN_ID,
                repo_snapshot_id=_SNAPSHOT_ID,
                turn_index=0,
                bogus_field="oops",  # type: ignore[call-arg]
            )

    def test_context_requires_run_id_and_snapshot_id(self) -> None:
        with pytest.raises(ValidationError):
            ResearchDecisionContextV1(
                run_id="",
                repo_snapshot_id=_SNAPSHOT_ID,
                turn_index=0,
            )
        with pytest.raises(ValidationError):
            ResearchDecisionContextV1(
                run_id=_RUN_ID,
                repo_snapshot_id="",
                turn_index=0,
            )

    def test_context_rejects_negative_turn_index(self) -> None:
        with pytest.raises(ValidationError):
            ResearchDecisionContextV1(
                run_id=_RUN_ID,
                repo_snapshot_id=_SNAPSHOT_ID,
                turn_index=-1,
            )


class TestRecentObservationSummaryContract:
    def test_summary_is_frozen(self) -> None:
        summary = RecentObservationSummaryV1(
            observation_id="obs-1",
            tool_call_id="tc-1",
            tool_name="search_symbols",
            status="success",
            source_authority="executable_hard",
        )
        with pytest.raises(ValidationError):
            summary.status = "truncated"  # type: ignore[misc]

    def test_summary_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            RecentObservationSummaryV1(
                observation_id="obs-1",
                tool_call_id="tc-1",
                tool_name="search_symbols",
                status="success",
                source_authority="executable_hard",
                full_payload="leak",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


class TestSupervisorBackendProtocol:
    def test_deterministic_backend_satisfies_protocol(self) -> None:
        backend = _backend()
        assert isinstance(backend, SupervisorBackend)

    def test_protocol_is_runtime_checkable(self) -> None:
        # A class that doesn't implement `decide` should not satisfy.
        class NotABackend:
            pass

        assert not isinstance(NotABackend(), SupervisorBackend)


# ---------------------------------------------------------------------------
# Fallback table
# ---------------------------------------------------------------------------


class TestFallbackTable:
    def test_every_issue_kind_has_a_fallback(self) -> None:
        kinds = all_fallback_issue_kinds()
        # Every kind in the closed ResearchIssueV1.issue_kind set must be
        # covered, except the ones that are inherently terminal.
        expected = {
            "missing_anchor", "missing_relation", "missing_condition",
            "wrong_span_role", "direct_evidence_semantically_unrelated",
            "branch_ambiguity", "config_ambiguity",
            "no_semantically_matching_projected_claim",
            "sentence_claim_atomicity", "formula_unsupported",
            "hint_code_conflict", "truncated_observation",
            "ambiguous_observation", "no_information_gain",
            "budget_exhausted", "quality_regression",
        }
        assert set(kinds) == expected

    def test_fallback_returns_action_and_next_fallback(self) -> None:
        issue = _issue("missing_relation")
        action, next_fallback = fallback_action_for_issue(issue)
        assert action == "TRACE_CALLS"
        assert next_fallback == "RECORD_GAP"

    def test_fallback_for_none_issue_returns_default(self) -> None:
        action, next_fallback = fallback_action_for_issue(None)
        assert action == "SEARCH_SYMBOLS"
        assert next_fallback == "RECORD_GAP"

    def test_budget_exhausted_fallback_is_record_gap(self) -> None:
        issue = _issue("budget_exhausted")
        action, next_fallback = fallback_action_for_issue(issue)
        assert action == "RECORD_GAP"
        assert next_fallback == "STOP_BLOCKED"

    def test_quality_regression_fallback_is_record_gap(self) -> None:
        issue = _issue("quality_regression")
        action, _ = fallback_action_for_issue(issue)
        assert action == "RECORD_GAP"


# ---------------------------------------------------------------------------
# DeterministicSupervisorBackend
# ---------------------------------------------------------------------------


class TestDeterministicSupervisorBackend:
    def test_backend_produces_valid_decision_for_every_issue_kind(self) -> None:
        backend = _backend()
        for kind in all_fallback_issue_kinds():
            issue = _issue(kind)
            obl = _obligation()
            ctx = _context(active_obligation=obl, active_issue=issue)
            decision = backend.decide(ctx)
            assert isinstance(decision, ResearchDecisionV1)
            assert decision.run_id == _RUN_ID
            assert decision.turn_index == 0
            assert decision.produced_by == "deterministic_fallback"

    def test_backend_returns_search_symbols_for_missing_anchor(self) -> None:
        backend = _backend()
        obl = _obligation()
        ctx = _context(active_obligation=obl, active_issue=_issue("missing_anchor"))
        decision = backend.decide(ctx)
        assert decision.action == "SEARCH_SYMBOLS"
        assert len(decision.selected_tool_calls) == 1
        call = decision.selected_tool_calls[0]
        assert call.tool_name == "search_symbols"
        assert call.obligation_id == "obl-1"
        assert call.repo_snapshot_id == _SNAPSHOT_ID

    def test_backend_returns_trace_calls_for_missing_relation(self) -> None:
        backend = _backend()
        obl = _obligation(candidate_symbol_ids=("train.py:train",))
        ctx = _context(active_obligation=obl, active_issue=_issue("missing_relation"))
        decision = backend.decide(ctx)
        assert decision.action == "TRACE_CALLS"
        call = decision.selected_tool_calls[0]
        assert call.tool_name == "find_references"

    def test_backend_returns_read_candidate_for_wrong_span_role(self) -> None:
        backend = _backend()
        obl = _obligation(candidate_symbol_ids=("train.py:train",))
        ctx = _context(active_obligation=obl, active_issue=_issue("wrong_span_role"))
        decision = backend.decide(ctx)
        assert decision.action == "READ_CANDIDATE"
        call = decision.selected_tool_calls[0]
        assert call.tool_name == "read_symbol"
        assert call.arguments.get("path") == "train.py"
        assert call.arguments.get("symbol") == "train"

    def test_truncated_ranked_search_reads_top_candidate(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:features.py:normalize_features:21",),
            missing_information=("typed_predicate:NORMALIZE",),
        )
        search_call = _tool_call(tool_call_id="tc-truncated", tool_name="search_symbols")
        observation = _observation(
            search_call,
            status="truncated",
            result_refs=("symbol:features.py:normalize_features:21",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            active_issue=_issue("truncated_observation"),
            recent_observations=(observation,),
        )

        decision = backend.decide(ctx)

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "normalize_features"

    def test_backend_returns_record_gap_after_three_no_progress_turns(self) -> None:
        backend = _backend()
        obl = _obligation()
        ctx = _context(active_obligation=obl, no_progress_counter=3)
        decision = backend.decide(ctx)
        assert decision.action == "RECORD_GAP"
        assert decision.selected_tool_calls == ()
        assert decision.fallback_action == "STOP_BLOCKED"

    def test_backend_switches_strategy_after_two_no_progress_turns(self) -> None:
        backend = _backend()
        # Give the obligation a candidate symbol so TRACE_CALLS can produce
        # a find_references call (otherwise the action downgrades to RECORD_GAP).
        obl = _obligation(candidate_symbol_ids=("train.py:train",))
        # Recent observation was a search_symbols call -> switch to TRACE_CALLS.
        tc = _tool_call(tool_name="search_symbols")
        obs = _observation(tc)
        ctx = _context(
            active_obligation=obl,
            no_progress_counter=2,
            recent_observations=(obs,),
        )
        decision = backend.decide(ctx)
        assert decision.action == "TRACE_CALLS"

    @staticmethod
    def _bound_graph(
        *,
        path: str = "train.py",
        name: str = "train",
        line: int = 10,
        node_id: str = "node:bound1",
        span_start: int = 1,
        span_end: int = 30,
    ) -> CodeBehaviorGraphV1:
        """A behavior graph whose node binds to the exact candidate symbol."""
        from code2paper.agentic.behavior_graph import BehaviorNodeV1, make_symbol_id

        return CodeBehaviorGraphV1(
            repo_snapshot_id=_SNAPSHOT_ID,
            project_tree_hash=_TREE_HASH,
            nodes=[
                BehaviorNodeV1(
                    node_id=node_id,
                    symbol_id=make_symbol_id(path, name, line),
                    operation_id="op-1",
                    predicate="WRITE",
                    operands=("x",),
                    result="x",
                    source_span_id=f"span:{path}:{span_start}:{span_end}",
                )
            ],
        )

    def test_backend_compiles_when_candidate_read_already_executed(self) -> None:
        """A read already executed for another obligation must not be re-proposed.

        Policy rejects the exact re-read (identical snapshot bytes), so the
        deterministic supervisor must switch to COMPILE_EVIDENCE when the
        behavior graph already carries nodes that bind to the exact
        candidate; otherwise the loop burns turns until fallback-exhaustion
        STOP_BLOCKED.
        """
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
            # Semantic information is still outstanding (as in the live
            # fixture); only the exact read bytes are already in the run.
            missing_information=("describe the code-backed aggregation output",),
        )
        # The read was executed while answering another obligation.
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_symbol",
            arguments={"path": "train.py", "symbol": "train", "top_k": 1},
            path_scope=("train.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        # Recent search found the same symbol (so READ_CANDIDATE would be the
        # naive next step).
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=self._bound_graph(),
        )
        decision = backend.decide(ctx)
        assert decision.action == "COMPILE_EVIDENCE"
        assert decision.selected_tool_calls == ()

    def test_same_symbol_name_in_other_path_does_not_suppress_read(self) -> None:
        """A prior read_symbol of ``other.py:train`` must not suppress
        reading ``train.py:train``: the identity is (path, symbol)."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
        )
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_symbol",
            arguments={"path": "other.py", "symbol": "train", "top_k": 1},
            path_scope=("other.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=self._bound_graph(),
        )
        decision = backend.decide(ctx)
        assert decision.action == "READ_CANDIDATE"

    def test_same_file_different_span_does_not_suppress_read(self) -> None:
        """A prior read_code_span of a different interval in the same file
        must not suppress reading the candidate symbol."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
        )
        # Prior span read covers lines 40-60; the candidate is at line 10.
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_code_span",
            arguments={"path": "train.py", "start_line": 40, "end_line": 60},
            path_scope=("train.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=self._bound_graph(),
        )
        decision = backend.decide(ctx)
        assert decision.action == "READ_CANDIDATE"

    def test_adjacent_non_covering_span_does_not_suppress_read(self) -> None:
        """An adjacent (non-covering) interval must not suppress the read."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
        )
        # Span ends at line 9, candidate starts at line 10: adjacent, not
        # covering.
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_code_span",
            arguments={"path": "train.py", "start_line": 1, "end_line": 9},
            path_scope=("train.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=self._bound_graph(),
        )
        decision = backend.decide(ctx)
        assert decision.action == "READ_CANDIDATE"

    def test_covering_span_suppresses_read_when_graph_binds_candidate(self) -> None:
        """A prior read_code_span whose interval covers the candidate line
        may suppress the read when graph support binds to that candidate."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
            missing_information=("describe the code-backed aggregation output",),
        )
        # Prior span covers lines 1-30, candidate at line 10.
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_code_span",
            arguments={"path": "train.py", "start_line": 1, "end_line": 30},
            path_scope=("train.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=self._bound_graph(),
        )
        decision = backend.decide(ctx)
        assert decision.action == "COMPILE_EVIDENCE"
        assert decision.selected_tool_calls == ()

    def test_exact_read_with_unrelated_nodes_switches_strategy(self) -> None:
        """An exact prior read with behavior nodes that do NOT bind to the
        candidate must switch strategy, not compile from unrelated bytes."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
            missing_information=("describe the code-backed aggregation output",),
        )
        executed = ExecutedToolCallSummaryV1(
            tool_name="read_symbol",
            arguments={"path": "train.py", "symbol": "train", "top_k": 1},
            path_scope=("train.py",),
            goal="READ_CANDIDATE for obl-0",
            obligation_id="obl-0",
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        # Graph node binds to a DIFFERENT symbol in the same file, in a
        # region that does NOT cover the candidate line: the path projection
        # is non-empty but the candidate binding is not.
        unrelated = self._bound_graph(
            path="train.py", name="other", line=50, node_id="node:unrelated",
            span_start=40, span_end=60,
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
            executed_tool_calls=(executed,),
            behavior_graph=unrelated,
        )
        decision = backend.decide(ctx)
        assert decision.action in {"TRACE_CALLS", "SEARCH_HINTS"}

    def test_backend_still_reads_candidate_when_read_not_executed(self) -> None:
        """The guard must not suppress legitimate first reads."""
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:train.py:train:10",),
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:train:10",),
            exact_span_ids=(),
        )
        ctx = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
        )
        decision = backend.decide(ctx)
        assert decision.action == "READ_CANDIDATE"

    def test_backend_returns_stop_blocked_when_no_active_obligation(self) -> None:
        backend = _backend()
        ctx = _context(active_obligation=None)
        decision = backend.decide(ctx)
        assert decision.action == "STOP_BLOCKED"
        assert decision.selected_tool_calls == ()

    def test_backend_returns_search_symbols_when_obligation_has_no_candidates(self) -> None:
        backend = _backend()
        obl = _obligation()
        ctx = _context(active_obligation=obl)
        decision = backend.decide(ctx)
        assert decision.action == "SEARCH_SYMBOLS"

    def test_config_words_do_not_skip_search_and_exact_read(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("train.py", "configs/base.yaml"),
            missing_information=(
                "Describe the code-backed configuration fields and training entrypoint.",
                "candidate_path:train.py",
                "candidate_path:configs/base.yaml",
            ),
        )

        first = backend.decide(_context(active_obligation=obl))
        assert first.action == "SEARCH_SYMBOLS"
        assert first.selected_tool_calls[0].tool_name == "search_symbols"

        search_call = first.selected_tool_calls[0]
        search_observation = _observation(
            search_call,
            status="success",
            result_refs=("symbol:train.py:main:1",),
        )
        second = backend.decide(
            _context(active_obligation=obl, recent_observations=(search_observation,))
        )
        assert second.action == "READ_CANDIDATE"
        assert second.selected_tool_calls[0].tool_name == "read_symbol"

    def test_missing_typed_predicate_searches_beyond_old_candidate(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:old.py:unrelated:3",),
            missing_information=("typed_predicate:NORMALIZE",),
        )

        decision = backend.decide(_context(active_obligation=obl))

        assert decision.action == "SEARCH_SYMBOLS"
        assert decision.selected_tool_calls[0].arguments["query"] == "normalize norm"
        assert decision.selected_tool_calls[0].path_scope == ()

    def test_missing_typed_predicate_stays_inside_author_candidate_paths(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("models/NamedEncoder.py", "utils/ops.py"),
            missing_information=(
                "typed_predicate:ATTEND",
                "candidate_path:models/NamedEncoder.py",
                "candidate_path:utils/ops.py",
            ),
        )

        decision = backend.decide(_context(active_obligation=obl))

        assert decision.action == "SEARCH_SYMBOLS"
        assert decision.selected_tool_calls[0].path_scope == (
            "models/NamedEncoder.py",
            "utils/ops.py",
        )

    def test_missing_typed_predicate_reads_top_result_after_search(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:old.py:unrelated:3",),
            missing_information=("typed_predicate:NORMALIZE",),
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="truncated",
            result_refs=(
                "symbol:features.py:normalize_features:21",
                "symbol:old.py:unrelated:3",
            ),
            exact_span_ids=(),
        )

        decision = backend.decide(
            _context(active_obligation=obl, recent_observations=(search_observation,))
        )

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["path"] == "features.py"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "normalize_features"

    def test_read_candidate_advances_to_next_result_from_latest_search(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:old.py:unrelated:3",),
            missing_information=("typed_predicate:NORMALIZE",),
        )
        search_call = _tool_call(tool_call_id="tc-search", tool_name="search_symbols")
        search_observation = _observation(
            search_call,
            status="truncated",
            result_refs=(
                "symbol:features.py:normalize_features:21",
                "symbol:ops.py:stable_norm:8",
            ),
            exact_span_ids=(),
        )
        first_read_call = _tool_call(
            tool_call_id="tc-read-first",
            tool_name="read_symbol",
            tool_kind="code_read",
        )
        first_read_observation = _observation(
            first_read_call,
            result_refs=("symbol:features.py:normalize_features:21",),
        )

        decision = backend.decide(_context(
            active_obligation=obl,
            recent_observations=(search_observation, first_read_observation),
        ))

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["path"] == "ops.py"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "stable_norm"

    def test_explicit_author_symbol_rejects_fuzzy_search_neighbor(self) -> None:
        backend = _backend()
        obl = ResearchAgendaItemV1(
            obligation_id="obl-1",
            priority="should_cover",
            status="in_progress",
            author_text=(
                "evaluate_models_utils.py::MemoryModel: Encode shared-neighbor frequency."
            ),
            missing_information=["typed_semantic:transformations:memorymodel"],
        )
        search_observation = _observation(
            _tool_call(tool_call_id="tc-search", tool_name="search_symbols"),
            status="truncated",
            result_refs=(
                "symbol:models/DyGMamba.py:MemoryBank:925",
                "symbol:evaluate_models_utils.py:evaluate_model:19",
            ),
            exact_span_ids=(),
        )
        context = _context(
            active_obligation=obl,
            recent_observations=(search_observation,),
        )

        assert backend._latest_search_symbol_ref(context) is None
        assert backend._read_symbol_target(context) is None
        assert backend._read_symbol_path(context) is None

    def test_candidate_read_in_other_obligation_does_not_skip_current_result(self) -> None:
        backend = _backend()
        target_ref = "symbol:graph.py:build_index:21"
        obl = _obligation(
            candidate_symbol_ids=(target_ref,),
            missing_information=("typed_semantic:transformations:adjacency",),
        )
        other_read = _observation(
            _tool_call(
                tool_call_id="tc-other-read",
                tool_name="read_symbol",
                tool_kind="code_read",
                obligation_id="obl-other",
            ),
            result_refs=(target_ref,),
        )
        current_search = _observation(
            _tool_call(tool_call_id="tc-current-search", tool_name="search_symbols"),
            result_refs=(target_ref,),
            exact_span_ids=(),
        )

        decision = backend.decide(_context(
            active_obligation=obl,
            recent_observations=(other_read, current_search),
        ))

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "build_index"

    def test_new_semantic_target_replaces_stale_ranked_search_cursor(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=("symbol:graph.py:build_index:21",),
            missing_information=("typed_semantic:transformations:generation",),
        )
        search_call = _tool_call(
            tool_call_id="tc-index-search",
            tool_name="search_symbols",
        )
        stale_search = make_observation(
            tool_call=search_call,
            status="success",
            source_authority="executable_hard",
            result_refs=(
                "symbol:graph.py:build_index:21",
                "symbol:graph.py:add_nodes:40",
            ),
            diagnostics=ResearchObservationDiagnosticsV1(
                candidate_count=2,
                notes=("query=indexing",),
            ),
        )

        decision = backend.decide(_context(
            active_obligation=obl,
            recent_observations=(stale_search,),
        ))

        assert decision.action == "SEARCH_SYMBOLS"
        assert decision.selected_tool_calls[0].arguments["query"] == (
            "generation generate infer answer qa"
        )

    def test_repeated_ranked_search_reads_next_unseen_candidate(self) -> None:
        backend = _backend()
        first_ref = "symbol:features.py:get_feature_vector:21"
        second_ref = "symbol:model.py:Predictor.__init__:6"
        obl = _obligation(
            candidate_symbol_ids=(first_ref, second_ref),
            missing_information=("typed_semantic:outputs:dimension 15",),
        )
        read_observation = _observation(
            _tool_call(tool_call_id="tc-read", tool_name="read_symbol"),
            status="success",
            result_refs=(first_ref,),
        )
        search_observation = _observation(
            _tool_call(tool_call_id="tc-search-next", tool_name="search_symbols"),
            status="truncated",
            result_refs=(first_ref, second_ref),
            exact_span_ids=(),
        )

        decision = backend.decide(_context(
            active_obligation=obl,
            recent_observations=(read_observation, search_observation),
        ))

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["path"] == "model.py"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "Predictor.__init__"

    def test_interleaved_loop_reads_discovered_predicate_candidate(self) -> None:
        backend = _backend()
        obl = _obligation(
            candidate_symbol_ids=(
                "symbol:model.py:forward:3",
                "symbol:features.py:percentile_cutoff_normalize:21",
            ),
            missing_information=("typed_predicate:NORMALIZE",),
        )

        decision = backend.decide(_context(active_obligation=obl))

        assert decision.action == "READ_CANDIDATE"
        assert decision.selected_tool_calls[0].arguments["path"] == "features.py"
        assert decision.selected_tool_calls[0].arguments["symbol"] == "percentile_cutoff_normalize"

    def test_backend_uses_typed_target_search_terms(self) -> None:
        backend = _backend()
        target = TypedBehaviorTargetV1(
            target_id="t1",
            search_terms=("prune_pure_feature",),
        )
        obl = _obligation(typed_targets=(target,))
        ctx = _context(active_obligation=obl)
        decision = backend.decide(ctx)
        call = decision.selected_tool_calls[0]
        assert call.arguments.get("query") == "prune_pure_feature"

    def test_backend_uses_explicit_author_symbol_instead_of_obligation_hash(self) -> None:
        backend = _backend()
        obl = ResearchAgendaItemV1(
            obligation_id="O-COMPONENT-01-deadbeef",
            author_text="src/runtime.py::generate_candidates: execute the core path",
            priority="must_cover",
            status="in_progress",
        )
        decision = backend.decide(_context(active_obligation=obl))

        assert decision.selected_tool_calls[0].arguments["query"] == "generate_candidates"

    def test_backend_uses_semantic_missing_information_not_obligation_hash(self) -> None:
        backend = _backend()
        obl = ResearchAgendaItemV1(
            obligation_id="O-STAGE-01-deadbeef",
            author_text="Generate candidate sequences from the current prefix.",
            priority="must_cover",
            status="in_progress",
            missing_information=[
                "Generate candidate sequences from the current prefix.",
                "candidate_path:src/runtime.py",
            ],
        )
        decision = backend.decide(_context(active_obligation=obl))

        assert decision.selected_tool_calls[0].arguments["query"].startswith("Generate candidate")

    def test_backend_decision_id_is_stable(self) -> None:
        backend = _backend()
        obl = _obligation()
        ctx = _context(active_obligation=obl)
        d1 = backend.decide(ctx)
        d2 = backend.decide(ctx)
        assert d1.decision_id == d2.decision_id

    def test_backend_does_not_produce_authority_overreach(self) -> None:
        backend = _backend()
        obl = _obligation()
        ctx = _context(active_obligation=obl, active_issue=_issue("missing_anchor"))
        decision = backend.decide(ctx)
        for call in decision.selected_tool_calls:
            assert "source_authority" not in call.arguments


# ---------------------------------------------------------------------------
# build_decision_context
# ---------------------------------------------------------------------------


class TestBuildDecisionContext:
    def test_context_picks_active_obligation_from_agenda(self) -> None:
        obl1 = _obligation("obl-1")
        obl2 = _obligation("obl-2")
        agenda = _agenda(obl1, obl2)
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-2",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert ctx.active_obligation is not None
        assert ctx.active_obligation.obligation_id == "obl-2"

    def test_context_returns_none_obligation_when_id_not_in_agenda(self) -> None:
        obl1 = _obligation("obl-1")
        agenda = _agenda(obl1)
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-missing",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert ctx.active_obligation is None

    def test_context_projects_recent_observations_into_summaries(self) -> None:
        obl = _obligation()
        agenda = _agenda(obl)
        tc = _tool_call()
        obs = _observation(tc)
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-1",
            active_issue=None,
            recent_observations=(obs,),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert len(ctx.recent_observations) == 1
        summary = ctx.recent_observations[0]
        assert summary.observation_id == obs.observation_id
        assert summary.tool_name == "search_symbols"
        assert summary.status == "success"
        # The summary must NOT carry the full observation payload.
        assert not hasattr(summary, "diagnostics")
        assert not hasattr(summary, "error_message")

    def test_context_computes_remaining_budgets_for_active_obligation(self) -> None:
        obl = _obligation()
        agenda = _agenda(obl)
        budget = PerObligationBudgetV1(
            obligation_id="obl-1",
            limits={"symbol_search": 5, "code_read": 3},
            used={"symbol_search": 2, "code_read": 0},
        )
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-1",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={"obl-1": budget},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert ctx.remaining_budgets["symbol_search"] == 3
        assert ctx.remaining_budgets["code_read"] == 3

    def test_context_allowed_actions_include_terminal_when_no_obligation(self) -> None:
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=None,
            active_obligation_id="",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert "STOP_BLOCKED" in ctx.allowed_actions
        assert "SEARCH_SYMBOLS" not in ctx.allowed_actions

    def test_context_filters_already_read_candidates(self) -> None:
        """A candidate whose exact read already executed must not be shown as
        a top candidate: policy would reject a re-read as a duplicate no-gain
        call, so advertising it makes both the LLM and the deterministic
        supervisor propose a doomed READ_CANDIDATE (EBCAR churn)."""
        obl = _obligation(
            candidate_symbol_ids=(
                "sym:src/model/ebcar_dedicated_attention_model.py:EBCarRerankerHybridAttention.forward",
                "sym:src/model/ebcar_dedicated_attention_model.py:EBCarRerankerHybridAttention.rerank",
            )
        )
        agenda = _agenda(obl)
        executed = (
            ExecutedToolCallSummaryV1(
                tool_name="read_symbol",
                arguments={
                    "path": "src/model/ebcar_dedicated_attention_model.py",
                    "symbol": "EBCarRerankerHybridAttention.forward",
                },
                path_scope=("src/model/ebcar_dedicated_attention_model.py",),
                goal="read",
                obligation_id="obl-0",
            ),
        )
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-1",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
            executed_tool_calls=executed,
        )
        assert ctx.top_candidate_symbol_ids == (
            "sym:src/model/ebcar_dedicated_attention_model.py:EBCarRerankerHybridAttention.rerank",
        )

    def test_context_allowed_actions_include_tool_calling_when_obligation_active(self) -> None:
        obl = _obligation()
        agenda = _agenda(obl)
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-1",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        for action in ("SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "RECORD_GAP"):
            assert action in ctx.allowed_actions

    def test_context_carries_unresolved_must_cover_ids(self) -> None:
        obl1 = _obligation("obl-1")
        obl2 = ResearchAgendaItemV1(
            obligation_id="obl-2",
            priority="must_cover",
            status="supported",
            supported_claim_ids=["c1"],
        )
        agenda = _agenda(obl1, obl2)
        ctx = build_decision_context(
            run_id=_RUN_ID,
            repo_snapshot_id=_SNAPSHOT_ID,
            turn_index=0,
            agenda=agenda,
            active_obligation_id="obl-1",
            active_issue=None,
            recent_observations=(),
            per_obligation_budgets={},
            global_safety_budget=GlobalSafetyBudgetV1(),
        )
        assert "obl-1" in ctx.unresolved_must_cover_ids
        assert "obl-2" not in ctx.unresolved_must_cover_ids


# ---------------------------------------------------------------------------
# supervisor_node
# ---------------------------------------------------------------------------


class TestSupervisorNode:
    def test_node_returns_state_update_shape(self) -> None:
        backend = _backend()
        obl = _obligation()
        agenda = _agenda(obl)
        state = {
            "run_id": _RUN_ID,
            "repo_snapshot_id": _SNAPSHOT_ID,
            "active_obligation_id": "obl-1",
        }
        update = supervisor_node(
            state,  # type: ignore[arg-type]
            backend=backend,
            agenda=agenda,
            active_issue=None,
            turn_index=0,
            ready_tools=("search_symbols",),
            hard_rules=("no_snapshot_external_paths",),
        )
        assert "pending_tool_calls" in update
        assert "decision_trace_refs" in update
        assert "status" in update
        assert update["status"] == "researching"
        assert len(update["decision_trace_refs"]) == 1

    def test_node_sets_blocked_status_for_stop_blocked(self) -> None:
        backend = _backend()
        # No active obligation -> backend returns STOP_BLOCKED.
        state = {
            "run_id": _RUN_ID,
            "repo_snapshot_id": _SNAPSHOT_ID,
            "active_obligation_id": "",
        }
        update = supervisor_node(
            state,  # type: ignore[arg-type]
            backend=backend,
            agenda=None,
            active_issue=None,
            turn_index=0,
        )
        assert update["status"] == "blocked"
        assert update["pending_tool_calls"] == []
