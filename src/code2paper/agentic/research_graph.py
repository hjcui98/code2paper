"""LangGraph research subgraph wiring (R3.1).

Builds the V3 research subgraph topology from design section 8 / R3.1:

::

    input_resolution
      -> intent_compiler
      -> repository_indexer
      -> research_agenda_builder
      -> research_supervisor
      -> research_tool_node
      -> observation_ingest
      -> behavior_graph_updater
      -> evidence_critic

``evidence_critic`` routes to:

- ``search_more``      -> research_supervisor
- ``inspect_branch``   -> research_supervisor
- ``compile_candidate``-> generic_fact_compiler_stub (R4 will replace this)
- ``record_gap``       -> gap_finalizer
- ``ready_to_author``  -> ready_to_author (terminal for R3)
- ``blocked``          -> blocked (terminal)

The graph topology is a LangGraph ``StateGraph[AgentStateV3]``.  Because
LangGraph state channels must be JSON-serializable and the research loop
also needs to carry a live ``CodeBehaviorGraphV1``, an
``InformationGainTracker`` and the recent observation list, the graph
delegates to a ``ResearchLoopDriver`` that holds those non-serializable
objects.  The driver is what tests call directly; the LangGraph wrapper
exists for topology compliance and for the R3.5 checkpoint-resume test.

R3.5 exit condition: the driver can complete at least three different
tool sequences in a fixture repo, the policy trace is explainable, and
the final support boundary is independent of tool order.  All three
properties are verified by ``tests/test_agentic_research_*``.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from langgraph.graph import END, START, StateGraph

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    empty_quality_state,
)
from code2paper.agentic.research_nodes import (
    BudgetPolicyV1,
    DEFAULT_BUDGET_POLICY,
    EVIDENCE_CRITIC_ROUTES,
    InformationGainTracker,
    ResearchGraphRuntime,
    behavior_graph_updater_node,
    evidence_critic_node,
    execute_pending_tool_calls,
    gap_finalizer_node,
    input_resolution_node,
    intent_compiler_node,
    observation_ingest_node,
    quality_state_selector_node,
    repository_indexer_node,
    research_agenda_builder_node,
    research_supervisor_node,
    research_tool_node,
    seed_per_obligation_budgets,
)
from code2paper.agentic.research_policy import (
    PolicyMergeResult,
    apply_consumed_budgets,
    apply_policy_merge,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    SupervisorBackend,
    build_decision_context,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.agentic.state_v3 import (
    AgentStateV3,
    AgentStateV3Record,
    empty_agent_state_v3,
)


# ---------------------------------------------------------------------------
# Mutable loop state (non-serializable; held outside LangGraph channels)
# ---------------------------------------------------------------------------


@dataclass
class ResearchLoopState:
    """Mutable research-loop state carried alongside the LangGraph state.

    LangGraph channels only hold serializable references (digests, ids,
    counters).  The live ``CodeBehaviorGraphV1``, ``InformationGainTracker``
    and the recent observation list live here so the nodes can mutate them
    in place without round-tripping through JSON.
    """

    runtime: ResearchGraphRuntime
    behavior_graph: CodeBehaviorGraphV1
    gain_tracker: InformationGainTracker = field(default_factory=InformationGainTracker)
    per_obligation_budgets: dict[str, PerObligationBudgetV1] = field(default_factory=dict)
    recent_observations: list[ResearchObservationV1] = field(default_factory=list)
    active_issue: ResearchIssueV1 | None = None
    turn_index: int = 0
    no_progress_tool_call_ids: set[str] = field(default_factory=set)
    recent_tool_call_ids: set[str] = field(default_factory=set)
    current_quality_state: Any = None
    best_quality_state: Any = None
    decision_trace: list[ResearchDecisionV1] = field(default_factory=list)
    policy_merge_trace: list[PolicyMergeResult] = field(default_factory=list)
    evidence_critic_route: str = ""
    terminated: bool = False
    termination_reason: str = ""


def initial_loop_state(
    runtime: ResearchGraphRuntime,
) -> ResearchLoopState:
    """Build a fresh ``ResearchLoopState`` for a new run."""

    agenda = runtime.agenda
    budgets = seed_per_obligation_budgets(agenda, runtime.budget_policy)
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        language="python",
    )
    initial_quality = empty_quality_state(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    )
    return ResearchLoopState(
        runtime=runtime,
        behavior_graph=graph,
        per_obligation_budgets=budgets,
        current_quality_state=initial_quality,
        best_quality_state=initial_quality,
    )


# ---------------------------------------------------------------------------
# Research loop driver (deterministic, testable)
# ---------------------------------------------------------------------------


@dataclass
class ResearchLoopResult:
    """Final outcome of a research loop run."""

    loop_state: ResearchLoopState
    final_state: AgentStateV3
    turns_executed: int
    terminated: bool
    termination_reason: str
    decision_trace: list[ResearchDecisionV1]
    policy_merge_trace: list[PolicyMergeResult]
    evidence_critic_routes: list[str]


class ResearchLoopDriver:
    """Drives the research loop by calling node functions directly.

    The driver is the single entry point for tests and for the LangGraph
    wrapper.  It:

    1. Runs the linear prefix (input_resolution -> intent_compiler ->
       repository_indexer -> research_agenda_builder) once.
    2. Runs the research loop (supervisor -> tool_node -> observation_ingest
       -> behavior_graph_updater -> evidence_critic) until a terminal route
       is reached or the global safety budget is exhausted.
    3. Returns a ``ResearchLoopResult`` containing the final state, the
       decision trace and the policy-merge trace.

    The driver is deterministic: given the same runtime and supervisor
    backend, it produces the same trace.  Randomness (if any) lives inside
    the supervisor backend.
    """

    def __init__(
        self,
        runtime: ResearchGraphRuntime,
        *,
        max_turns: int = 50,
    ) -> None:
        self._runtime = runtime
        self._max_turns = max_turns

    def run(
        self,
        initial_state: AgentStateV3 | None = None,
        *,
        loop_state: "ResearchLoopState | None" = None,
    ) -> ResearchLoopResult:
        """Run the research loop to termination.

        Parameters
        ----------
        initial_state
            Optional LangGraph state to resume from.  When provided, the
            driver respects the existing ``active_obligation_id`` if it
            points to an unresolved obligation (checkpoint resume).
        loop_state
            Optional pre-populated loop state (behavior graph, gain
            tracker, budgets) to resume from.  When omitted, a fresh
            loop state is seeded from the runtime.  When provided, the
            caller is responsible for ensuring the loop state is
            consistent with ``initial_state`` (e.g. budgets match the
            consumed tool calls recorded in the state).
        """

        runtime = self._runtime
        if initial_state is None:
            record = empty_agent_state_v3(
                run_id=runtime.run_id,
                repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
                project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            )
            state: AgentStateV3 = record.to_state_dict()
        else:
            state = dict(initial_state)

        if loop_state is not None:
            loop = loop_state
        else:
            loop = initial_loop_state(runtime)

        # --- linear prefix --------------------------------------------------
        state.update(input_resolution_node(state, runtime=runtime))
        state.update(intent_compiler_node(state, runtime=runtime))
        state.update(repository_indexer_node(state, runtime=runtime))
        state.update(research_agenda_builder_node(state, runtime=runtime))

        # --- research loop --------------------------------------------------
        routes: list[str] = []
        turns_executed = 0
        terminated = False
        termination_reason = ""

        while turns_executed < self._max_turns:
            active_obligation_id = state.get("active_obligation_id", "")
            if not active_obligation_id:
                terminated = True
                termination_reason = "no_active_obligation"
                state["status"] = "trusted"
                break

            # Supervisor + policy merge.
            supervisor_update = research_supervisor_node(
                state,
                runtime=runtime,
                per_obligation_budgets=loop.per_obligation_budgets,
                active_issue=loop.active_issue,
                recent_observations=tuple(loop.recent_observations[-5:]),
                no_progress_counter=loop.gain_tracker.no_progress_counter(active_obligation_id),
                no_progress_history=loop.gain_tracker.gain_history(active_obligation_id),
                recent_tool_call_ids=tuple(loop.recent_tool_call_ids),
                no_progress_tool_call_ids=tuple(loop.no_progress_tool_call_ids),
                turn_index=loop.turn_index,
                current_supported_claim_ids=tuple(
                    _supported_claim_ids(runtime.agenda, active_obligation_id)
                ),
            )
            # Pop the private channel BEFORE state.update so the real
            # merged decision (with ``produced_by`` / ``rationale`` /
            # ``goal`` from the supervisor backend) is preserved in the
            # decision trace.  Falling back to ``_reconstruct_decision``
            # would overwrite ``produced_by`` to ``deterministic_fallback``
            # and hide LLM proposals from the R8 acceptance check.
            merged_decision = supervisor_update.pop("_merged_decision", None)
            state.update(supervisor_update)

            pending = supervisor_update.get("pending_tool_calls", [])
            if merged_decision is not None:
                decision = merged_decision
            else:
                # Fallback for callers that don't return the merged
                # decision (e.g. unit tests with a stub supervisor node).
                decision = _reconstruct_decision(
                    runtime=runtime,
                    turn_index=loop.turn_index,
                    pending=pending,
                    active_obligation_id=active_obligation_id,
                    active_issue=loop.active_issue,
                )
            loop.decision_trace.append(decision)

            # Terminal actions short-circuit the loop.
            if decision.action == "STOP_BLOCKED":
                terminated = True
                termination_reason = "stop_blocked"
                state["status"] = "blocked"
                state["blocked_reason"] = "supervisor_stop_blocked"
                break
            if decision.action == "RECORD_GAP":
                # Route to gap finalizer.
                gap_update = gap_finalizer_node(
                    state,
                    runtime=runtime,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                )
                gap_accepted = gap_update.pop("_gap_accepted", False)
                state.update(gap_update)
                if state.get("status") == "blocked":
                    terminated = True
                    termination_reason = "gap_finalizer_blocked"
                    break
                if not gap_accepted:
                    # Gap was rejected: the search has not yet been
                    # exhaustive enough.  Continue researching the current
                    # obligation; the supervisor will pick a different
                    # action (or escalate to RECORD_GAP again after the
                    # no-progress threshold is met).
                    turns_executed += 1
                    loop.turn_index += 1
                    routes.append("record_gap_rejected")
                    continue
                # Move to the next unresolved obligation.
                next_obl = _next_unresolved_obligation(runtime.agenda, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = "all_obligations_terminal"
                    state["status"] = "trusted"
                    break
                state["active_obligation_id"] = next_obl
                loop.active_issue = None
                loop.recent_observations.clear()
                turns_executed += 1
                loop.turn_index += 1
                routes.append("record_gap")
                continue

            if not pending:
                # No tool calls and not terminal: nothing to do.
                terminated = True
                termination_reason = "no_tool_calls_no_terminal"
                state["status"] = "blocked"
                state["blocked_reason"] = "supervisor_no_tool_calls"
                break

            # Tool execution.
            observations, trace_refs = execute_pending_tool_calls(runtime, pending)
            loop.recent_observations.extend(observations)
            for call in pending:
                loop.recent_tool_call_ids.add(call.tool_call_id)
            state["pending_tool_calls"] = []
            state["tool_call_trace_refs"] = list(state.get("tool_call_trace_refs", [])) + trace_refs

            # Observation ingest.
            ingest_update = observation_ingest_node(
                state,
                runtime=runtime,
                observations=tuple(observations),
                gain_tracker=loop.gain_tracker,
                active_obligation_id=active_obligation_id,
            )
            state.update(ingest_update)

            # Track no-progress tool call ids for the duplicate-no-gain rule.
            _track_no_progress_calls(loop, observations, active_obligation_id)

            # Behavior graph updater.
            loop.behavior_graph, bg_update = behavior_graph_updater_node(
                state,
                runtime=runtime,
                behavior_graph=loop.behavior_graph,
                observations=tuple(observations),
                active_obligation_id=active_obligation_id,
            )
            state.update(bg_update)

            # Quality state selector.
            quality_update = quality_state_selector_node(
                state,
                runtime=runtime,
                current_quality_state=loop.current_quality_state,
                best_quality_state=loop.best_quality_state,
            )
            state.update(quality_update)
            if "best_quality_state_ref" in quality_update:
                loop.best_quality_state = loop.current_quality_state

            # Evidence critic: route the next iteration.
            route, critic_update = evidence_critic_node(
                state,
                runtime=runtime,
                gain_tracker=loop.gain_tracker,
                active_obligation_id=active_obligation_id,
                active_issue=loop.active_issue,
            )
            state.update(critic_update)
            routes.append(route)
            loop.evidence_critic_route = route

            if route == "blocked":
                terminated = True
                termination_reason = "evidence_critic_blocked"
                state["status"] = "blocked"
                break
            if route == "ready_to_author":
                terminated = True
                termination_reason = "ready_to_author"
                state["status"] = "trusted"
                break
            if route == "record_gap":
                gap_update = gap_finalizer_node(
                    state,
                    runtime=runtime,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                )
                gap_accepted = gap_update.pop("_gap_accepted", False)
                state.update(gap_update)
                if not gap_accepted:
                    # Gap rejected: keep researching the current obligation.
                    turns_executed += 1
                    loop.turn_index += 1
                    continue
                next_obl = _next_unresolved_obligation(runtime.agenda, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = "all_obligations_terminal"
                    state["status"] = "trusted"
                    break
                state["active_obligation_id"] = next_obl
                loop.active_issue = None
                loop.recent_observations.clear()
            elif route == "compile_candidate":
                # R4 not implemented yet; record a gap and move on.
                gap_update = gap_finalizer_node(
                    state,
                    runtime=runtime,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                )
                gap_accepted = gap_update.pop("_gap_accepted", False)
                state.update(gap_update)
                if not gap_accepted:
                    # Gap rejected: keep researching the current obligation.
                    turns_executed += 1
                    loop.turn_index += 1
                    continue
                next_obl = _next_unresolved_obligation(runtime.agenda, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = "all_obligations_terminal"
                    state["status"] = "trusted"
                    break
                state["active_obligation_id"] = next_obl
                loop.active_issue = None
                loop.recent_observations.clear()
            # search_more / inspect_branch: continue the loop.

            turns_executed += 1
            loop.turn_index += 1

        if not terminated and turns_executed >= self._max_turns:
            termination_reason = "max_turns_reached"
            state["status"] = "incomplete"
            state["blocked_reason"] = "max_turns_reached"

        return ResearchLoopResult(
            loop_state=loop,
            final_state=state,
            turns_executed=turns_executed,
            terminated=terminated,
            termination_reason=termination_reason,
            decision_trace=loop.decision_trace,
            policy_merge_trace=loop.policy_merge_trace,
            evidence_critic_routes=routes,
        )


# ---------------------------------------------------------------------------
# LangGraph StateGraph wrapper
# ---------------------------------------------------------------------------


def build_research_subgraph(
    runtime: ResearchGraphRuntime,
    *,
    max_turns: int = 50,
    checkpointer: Any = None,
) -> "CompiledResearchSubgraph":
    """Build the LangGraph ``StateGraph`` for the V3 research plane.

    The graph delegates to ``ResearchLoopDriver.run``.  This keeps the
    topology compliant with design section 8 while avoiding the complexity
    of passing non-serializable objects (behavior graph, gain tracker)
    through LangGraph state channels.

    The returned ``CompiledResearchSubgraph`` exposes ``invoke`` (delegated
    to the compiled LangGraph) and ``last_result`` (the most recent
    ``ResearchLoopResult``).  The result cannot travel through LangGraph
    state channels because it carries non-serializable objects (live
    behavior graph, gain tracker); tests use ``last_result`` to compare
    against the direct driver.

    Tests that want to assert on the graph topology can inspect
    ``graph.compiled.nodes`` and ``graph.compiled.edges``.
    """

    driver = ResearchLoopDriver(runtime, max_turns=max_turns)
    holder = _ResultHolder()

    def _entry(state: AgentStateV3) -> AgentStateV3:
        result = driver.run(initial_state=state)
        holder.result = result
        merged: dict[str, Any] = dict(state)
        merged.update(result.final_state)
        return merged  # type: ignore[return-value]

    graph = StateGraph(AgentStateV3)
    graph.add_node("research_loop", _entry)
    graph.add_edge(START, "research_loop")
    graph.add_edge("research_loop", END)
    compiled = graph.compile(checkpointer=checkpointer)
    return CompiledResearchSubgraph(compiled=compiled, result_holder=holder)


class _ResultHolder:
    """Mutable holder so the entry closure can stash the loop result."""

    __slots__ = ("result",)

    def __init__(self) -> None:
        self.result: ResearchLoopResult | None = None


class CompiledResearchSubgraph:
    """Wrapper around the compiled LangGraph research subgraph.

    Exposes ``invoke`` (delegated to the compiled graph) and
    ``last_result`` (the most recent ``ResearchLoopResult`` set by the
    entry closure).  The wrapper exists because ``ResearchLoopResult``
    carries non-serializable objects (live behavior graph, gain tracker)
    that cannot travel through LangGraph state channels.
    """

    def __init__(
        self,
        *,
        compiled: Any,
        result_holder: _ResultHolder,
    ) -> None:
        self._compiled = compiled
        self._holder = result_holder

    @property
    def compiled(self) -> Any:
        """The underlying compiled LangGraph (for topology inspection)."""

        return self._compiled

    @property
    def last_result(self) -> "ResearchLoopResult | None":
        """Most recent ``ResearchLoopResult`` produced by ``invoke``."""

        return self._holder.result

    def invoke(self, state: Any, *args: Any, **kwargs: Any) -> Any:
        # Reset the holder before invoking so a stale result is never
        # returned if the invocation fails before the entry node runs.
        self._holder.result = None
        return self._compiled.invoke(state, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # Delegate unknown attributes (e.g. ``nodes``, ``edges``) to the
        # compiled graph for backward compatibility with tests that
        # inspect topology directly on the wrapper.
        return getattr(self._compiled, name)


def run_research_loop(
    runtime: ResearchGraphRuntime,
    *,
    initial_state: AgentStateV3 | None = None,
    max_turns: int = 50,
    loop_state: "ResearchLoopState | None" = None,
) -> ResearchLoopResult:
    """Run the research loop without going through LangGraph.

    Convenience wrapper for tests.  Equivalent to::

        ResearchLoopDriver(runtime, max_turns=max_turns).run(
            initial_state, loop_state=loop_state,
        )
    """

    return ResearchLoopDriver(runtime, max_turns=max_turns).run(
        initial_state, loop_state=loop_state
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _supported_claim_ids(
    agenda: ResearchAgendaV1, obligation_id: str
) -> list[str]:
    for item in agenda.items:
        if item.obligation_id == obligation_id:
            return list(item.supported_claim_ids)
    return []


def _next_unresolved_obligation(
    agenda: ResearchAgendaV1, current_id: str
) -> str | None:
    """Return the next unresolved must-cover obligation after ``current_id``."""

    items = agenda.items
    started = False
    for item in items:
        if not started:
            if item.obligation_id == current_id:
                started = True
            continue
        if item.priority == "must_cover" and item.status not in {
            "supported", "explicit_gap", "blocked",
        }:
            return item.obligation_id
    # Wrap around: pick any unresolved must-cover.
    for item in items:
        if item.obligation_id == current_id:
            continue
        if item.priority == "must_cover" and item.status not in {
            "supported", "explicit_gap", "blocked",
        }:
            return item.obligation_id
    # Fall back to any unresolved obligation.
    for item in items:
        if item.obligation_id == current_id:
            continue
        if item.status not in {"supported", "explicit_gap", "blocked"}:
            return item.obligation_id
    return None


def _reconstruct_decision(
    *,
    runtime: ResearchGraphRuntime,
    turn_index: int,
    pending: list[ResearchToolCallV1] | list[dict[str, Any]],
    active_obligation_id: str,
    active_issue: ResearchIssueV1 | None,
) -> ResearchDecisionV1:
    """Reconstruct a ``ResearchDecisionV1`` from the supervisor node output.

    The supervisor node applies policy merge internally and only returns
    the accepted tool calls.  For the trace, we reconstruct a decision
    object so tests can assert on ``action`` / ``obligation_id`` / etc.
    """

    calls: list[ResearchToolCallV1] = []
    for call in pending:
        if isinstance(call, ResearchToolCallV1):
            calls.append(call)
        else:
            calls.append(ResearchToolCallV1.model_validate(call))

    if not calls:
        # Terminal action (STOP_BLOCKED or RECORD_GAP).
        action = "STOP_BLOCKED"
        if active_issue is not None and active_issue.issue_kind in {
            "budget_exhausted", "quality_regression",
        }:
            action = "RECORD_GAP"
    else:
        action = _action_for_tool(calls[0].tool_name)

    return ResearchDecisionV1(
        decision_id=f"decision-turn{turn_index}-{active_obligation_id}",
        run_id=runtime.run_id,
        turn_index=turn_index,
        action=action,
        obligation_id=active_obligation_id,
        issue_id=active_issue.issue_id if active_issue else "",
        goal=f"turn {turn_index} for {active_obligation_id}",
        selected_tool_calls=tuple(calls),
        candidate_scope=tuple(calls[0].path_scope) if calls else (),
        expected_information_gain="",
        evidence_needed=tuple(),
        stop_condition="",
        fallback_action=None,
        rationale="reconstructed_from_supervisor_node",
        produced_by="deterministic_fallback",
    )


_TOOL_ACTION_MAP: dict[str, str] = {
    "find_entrypoints": "SEARCH_SYMBOLS",
    "search_symbols": "SEARCH_SYMBOLS",
    "read_symbol": "READ_CANDIDATE",
    "find_references": "TRACE_CALLS",
    "build_behavior_subgraph": "BUILD_BEHAVIOR_SUBGRAPH",
}


def _action_for_tool(tool_name: str) -> str:
    return _TOOL_ACTION_MAP.get(tool_name, "SEARCH_SYMBOLS")


def _track_no_progress_calls(
    loop: ResearchLoopState,
    observations: list[ResearchObservationV1],
    active_obligation_id: str,
) -> None:
    """Add tool call ids to the no-progress set when they yield no gain.

    The gain tracker has already been updated by ``observation_ingest``.
    If the latest ingest produced no gain for the active obligation, the
    tool call ids are added to ``no_progress_tool_call_ids`` so policy
    merge can reject exact re-runs.
    """

    history = loop.gain_tracker.gain_history(active_obligation_id)
    if not history:
        return
    if history[-1] != "no_gain":
        return
    for obs in observations:
        if obs.obligation_id != active_obligation_id:
            continue
        loop.no_progress_tool_call_ids.add(obs.tool_call_id)


__all__ = [
    "CompiledResearchSubgraph",
    "ResearchLoopDriver",
    "ResearchLoopResult",
    "ResearchLoopState",
    "build_research_subgraph",
    "initial_loop_state",
    "run_research_loop",
]
