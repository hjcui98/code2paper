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
    compile_candidate_node,
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
# Compiled evidence sidecar (R4)
# ---------------------------------------------------------------------------


@dataclass
class CompiledEvidence:
    """Sidecar holding the V3 evidence packets/facts/claims for one obligation.

    Produced by ``compile_candidate_node`` and stored in
    ``ResearchLoopState.compiled_evidence`` so the writer (V3GraphWrapper)
    can read the full objects after the loop terminates.  These objects
    are non-serializable and must not travel through LangGraph channels.
    """

    obligation_id: str
    packet_set: Any  # EvidencePacketSetV3
    fact_set: Any  # CodeFactSetV1
    claim_set: Any  # AtomicClaimSetV3


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
    # R4 sidecar: compiled evidence packets / facts / claims keyed by
    # obligation_id.  These objects are non-serializable (they carry live
    # span/relation payloads) so they cannot travel through LangGraph
    # channels; the writer (V3GraphWrapper) reads them from here after the
    # loop terminates.
    compiled_evidence: dict[str, "CompiledEvidence"] = field(default_factory=dict)


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
                # R4 wiring: compile the active obligation's candidate
                # behavior nodes into authorized claims via the generic
                # evidence/fact/claim compilers.  On success the obligation
                # is marked ``supported`` and the compiled packets/facts/
                # claims are stashed in the loop state sidecar.  On failure
                # the node delegates to ``gap_finalizer_node``.
                compile_update = compile_candidate_node(
                    state,
                    runtime=runtime,
                    behavior_graph=loop.behavior_graph,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                )
                compiled_evidence = compile_update.pop("_compiled_evidence", None)
                gap_accepted = compile_update.pop("_gap_accepted", None)
                state.update(compile_update)
                if compiled_evidence is not None:
                    loop.compiled_evidence[compiled_evidence["obligation_id"]] = CompiledEvidence(
                        obligation_id=compiled_evidence["obligation_id"],
                        packet_set=compiled_evidence["packet_set"],
                        fact_set=compiled_evidence["fact_set"],
                        claim_set=compiled_evidence["claim_set"],
                    )
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
                    continue
                # No compiled evidence: the node already routed to gap
                # finalizer.  ``gap_accepted`` is True when the gap was
                # accepted (obligation marked ``explicit_gap``) and False
                # when the gap was rejected (search not yet exhaustive).
                if gap_accepted is False:
                    # Gap rejected: keep researching the current obligation.
                    turns_executed += 1
                    loop.turn_index += 1
                    continue
                if state.get("status") == "blocked":
                    terminated = True
                    termination_reason = "gap_finalizer_blocked"
                    break
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
# Multi-node LangGraph context (non-serializable sidecar)
# ---------------------------------------------------------------------------


class _ResearchGraphContext:
    """Mutable context for the multi-node research graph.

    Holds non-serializable objects (live ``CodeBehaviorGraphV1``,
    ``InformationGainTracker``, compiled evidence) and the current
    routing decisions.  Node functions and routing functions read from
    this context via closure capture; the LangGraph state channels only
    carry serializable references (digests, ids, counters).

    The context is NOT checkpointed.  On checkpoint resume, a fresh
    context is created and the linear_prefix node re-initializes the
    loop state from the runtime.  This matches the behavior of the
    direct ``ResearchLoopDriver`` which also does not persist the live
    behavior graph.
    """

    def __init__(self, runtime: ResearchGraphRuntime, *, max_turns: int) -> None:
        self.runtime = runtime
        self.max_turns = max_turns
        self.loop_state: ResearchLoopState | None = None
        # Routing decisions read by the conditional edge functions.
        self.supervisor_route: str = "tool_exec"
        self.critic_route: str = "search_more"
        self.compile_route: str = "compiled"
        self.gap_route: str = "accepted"
        self.advancer_route: str = "has_next"
        # Loop accounting.
        self.turns_executed: int = 0
        self.routes: list[str] = []
        self.terminated: bool = False
        self.termination_reason: str = ""
        self._observations: list[ResearchObservationV1] = []
        self._pending: list[ResearchToolCallV1] = []
        self._merged_decision: ResearchDecisionV1 | None = None


def _ctx_linear_prefix(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run the 4 linear prefix nodes and initialize the loop state."""

    runtime = ctx.runtime
    if ctx.loop_state is None:
        ctx.loop_state = initial_loop_state(runtime)
    update: dict[str, Any] = {}
    update.update(input_resolution_node(state, runtime=runtime))
    update.update(intent_compiler_node(state, runtime=runtime))
    update.update(repository_indexer_node(state, runtime=runtime))
    update.update(research_agenda_builder_node(state, runtime=runtime))
    return update


def _ctx_supervisor(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run the supervisor and set the routing decision."""

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None, "linear_prefix must run before supervisor"

    active_obligation_id = state.get("active_obligation_id", "")
    if not active_obligation_id:
        ctx.terminated = True
        ctx.termination_reason = "no_active_obligation"
        ctx.supervisor_route = "no_tool_calls"
        return {"status": "trusted"}

    # Max-turns check: if we've exceeded the budget, terminate.
    if ctx.turns_executed >= ctx.max_turns:
        ctx.terminated = True
        ctx.termination_reason = "max_turns_reached"
        ctx.supervisor_route = "no_tool_calls"
        return {"status": "incomplete", "blocked_reason": "max_turns_reached"}

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
    merged_decision = supervisor_update.pop("_merged_decision", None)
    pending = supervisor_update.get("pending_tool_calls", [])

    if merged_decision is not None:
        decision = merged_decision
    else:
        decision = _reconstruct_decision(
            runtime=runtime,
            turn_index=loop.turn_index,
            pending=pending,
            active_obligation_id=active_obligation_id,
            active_issue=loop.active_issue,
        )
    loop.decision_trace.append(decision)
    loop.policy_merge_trace.extend(supervisor_update.get("_policy_merge_results", []))

    # Stash pending and merged decision for the tool node.
    ctx._pending = list(pending)
    ctx._merged_decision = decision

    # Route based on the action.
    if decision.action == "STOP_BLOCKED":
        ctx.terminated = True
        ctx.termination_reason = "stop_blocked"
        ctx.supervisor_route = "stop_blocked"
        return {"status": "blocked", "blocked_reason": "supervisor_stop_blocked"}
    if decision.action == "RECORD_GAP":
        ctx.supervisor_route = "record_gap"
        return supervisor_update

    if not pending:
        ctx.terminated = True
        ctx.termination_reason = "no_tool_calls_no_terminal"
        ctx.supervisor_route = "no_tool_calls"
        return {
            "status": "blocked",
            "blocked_reason": "supervisor_no_tool_calls",
        }

    ctx.supervisor_route = "tool_exec"
    return supervisor_update


def _ctx_tool(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Execute the pending tool calls."""

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    pending = ctx._pending
    observations, trace_refs = execute_pending_tool_calls(runtime, pending)
    loop.recent_observations.extend(observations)
    for call in pending:
        loop.recent_tool_call_ids.add(call.tool_call_id)
    ctx._observations = list(observations)
    existing_refs = list(state.get("tool_call_trace_refs", []))
    return {
        "pending_tool_calls": [],
        "tool_call_trace_refs": existing_refs + trace_refs,
    }


def _ctx_observation(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run observation_ingest + behavior_graph_updater + quality_state_selector."""

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    active_obligation_id = state.get("active_obligation_id", "")
    observations = tuple(ctx._observations)

    update: dict[str, Any] = {}
    ingest_update = observation_ingest_node(
        state,
        runtime=runtime,
        observations=observations,
        gain_tracker=loop.gain_tracker,
        active_obligation_id=active_obligation_id,
    )
    update.update(ingest_update)

    _track_no_progress_calls(loop, observations, active_obligation_id)

    loop.behavior_graph, bg_update = behavior_graph_updater_node(
        state,
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        observations=observations,
        active_obligation_id=active_obligation_id,
    )
    update.update(bg_update)

    quality_update = quality_state_selector_node(
        state,
        runtime=runtime,
        current_quality_state=loop.current_quality_state,
        best_quality_state=loop.best_quality_state,
    )
    update.update(quality_update)
    if "best_quality_state_ref" in quality_update:
        loop.best_quality_state = loop.current_quality_state

    return update


def _ctx_critic(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run evidence_critic and set the routing decision."""

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    active_obligation_id = state.get("active_obligation_id", "")

    route, critic_update = evidence_critic_node(
        state,
        runtime=runtime,
        gain_tracker=loop.gain_tracker,
        active_obligation_id=active_obligation_id,
        active_issue=loop.active_issue,
    )
    ctx.routes.append(route)
    loop.evidence_critic_route = route

    if route == "blocked":
        ctx.terminated = True
        ctx.termination_reason = "evidence_critic_blocked"
        ctx.critic_route = "blocked"
        return {"status": "blocked"}
    if route == "ready_to_author":
        ctx.terminated = True
        ctx.termination_reason = "ready_to_author"
        ctx.critic_route = "ready_to_author"
        return {"status": "trusted"}

    # Non-terminal routes: record_gap, compile_candidate, search_more, inspect_branch.
    ctx.critic_route = route

    # search_more / inspect_branch: increment turn counter (the loop
    # continues to the supervisor via the conditional edge).
    if route in ("search_more", "inspect_branch"):
        ctx.turns_executed += 1
        loop.turn_index += 1

    return critic_update


def _ctx_compile(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run compile_candidate and set the routing decision.

    ``compile_candidate_node`` internally delegates to
    ``gap_finalizer_node`` when it cannot compile.  The gap result is
    returned via the private ``_gap_accepted`` key, so this node must
    NOT route to ``gap_finalizer`` again — that would double-call the
    finalizer.  Instead, accepted gaps route to ``obligation_advancer``
    (same as the compiled-success path) and rejected gaps route back to
    ``research_supervisor``.
    """

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    active_obligation_id = state.get("active_obligation_id", "")

    compile_update = compile_candidate_node(
        state,
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        active_obligation_id=active_obligation_id,
        gain_tracker=loop.gain_tracker,
    )
    compiled_evidence = compile_update.pop("_compiled_evidence", None)
    gap_accepted = compile_update.pop("_gap_accepted", None)

    if compiled_evidence is not None:
        loop.compiled_evidence[compiled_evidence["obligation_id"]] = CompiledEvidence(
            obligation_id=compiled_evidence["obligation_id"],
            packet_set=compiled_evidence["packet_set"],
            fact_set=compiled_evidence["fact_set"],
            claim_set=compiled_evidence["claim_set"],
        )
        # Success: route to advancer.  The advancer increments
        # turns_executed only when a next obligation exists.
        ctx.compile_route = "compiled"
        return compile_update

    # No compiled evidence: compile_candidate_node already called
    # gap_finalizer_node internally.  Do NOT route to gap_finalizer.
    if gap_accepted is False:
        # Gap rejected: keep researching the current obligation.
        ctx.compile_route = "rejected"
        ctx.turns_executed += 1
        loop.turn_index += 1
        return compile_update

    if compile_update.get("status") == "blocked":
        ctx.terminated = True
        ctx.termination_reason = "gap_finalizer_blocked"
        ctx.compile_route = "blocked"
        return compile_update

    # Gap accepted: route to advancer (same as compiled-success).
    ctx.compile_route = "compiled"
    return compile_update


def _ctx_gap(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run gap_finalizer and set the routing decision.

    Reached only from the critic's ``record_gap`` route.  The route
    itself is already appended to ``ctx.routes`` by ``_ctx_critic``,
    so this node must NOT append it again.
    """

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    active_obligation_id = state.get("active_obligation_id", "")

    gap_update = gap_finalizer_node(
        state,
        runtime=runtime,
        active_obligation_id=active_obligation_id,
        gain_tracker=loop.gain_tracker,
    )
    gap_accepted = gap_update.pop("_gap_accepted", False)

    if gap_update.get("status") == "blocked":
        ctx.terminated = True
        ctx.termination_reason = "gap_finalizer_blocked"
        ctx.gap_route = "blocked"
        return gap_update

    if not gap_accepted:
        # Gap rejected: keep researching the current obligation.
        ctx.gap_route = "rejected"
        ctx.turns_executed += 1
        loop.turn_index += 1
        return gap_update

    # Gap accepted: route to advancer.  The advancer increments
    # turns_executed only when a next obligation exists.
    ctx.gap_route = "accepted"
    return gap_update


def _ctx_advancer(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Advance to the next unresolved obligation.

    Increments ``turns_executed`` only when a next obligation exists
    (i.e. the loop will continue).  When no next obligation is found,
    the loop terminates and ``turns_executed`` is not incremented,
    matching the direct driver's behavior.
    """

    runtime = ctx.runtime
    loop = ctx.loop_state
    assert loop is not None
    active_obligation_id = state.get("active_obligation_id", "")

    next_obl = _next_unresolved_obligation(runtime.agenda, active_obligation_id)
    if next_obl is None:
        ctx.terminated = True
        ctx.termination_reason = "all_obligations_terminal"
        ctx.advancer_route = "no_next"
        return {"status": "trusted"}

    ctx.advancer_route = "has_next"
    ctx.turns_executed += 1
    loop.turn_index += 1
    loop.active_issue = None
    loop.recent_observations.clear()
    return {"active_obligation_id": next_obl}


def _ctx_terminate(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> "ResearchLoopResult":
    """Build the final ``ResearchLoopResult``."""

    loop = ctx.loop_state
    assert loop is not None
    if not ctx.terminated:
        ctx.termination_reason = ctx.termination_reason or "max_turns_reached"
    final_state = dict(state)
    if ctx.termination_reason == "max_turns_reached":
        final_state["status"] = "incomplete"
        final_state["blocked_reason"] = "max_turns_reached"
    elif ctx.termination_reason in ("no_active_obligation", "all_obligations_terminal", "ready_to_author"):
        final_state["status"] = "trusted"
    elif ctx.termination_reason in ("stop_blocked", "gap_finalizer_blocked", "evidence_critic_blocked", "no_tool_calls_no_terminal"):
        final_state["status"] = "blocked"
    return ResearchLoopResult(
        loop_state=loop,
        final_state=final_state,
        turns_executed=ctx.turns_executed,
        terminated=ctx.terminated,
        termination_reason=ctx.termination_reason,
        decision_trace=loop.decision_trace,
        policy_merge_trace=loop.policy_merge_trace,
        evidence_critic_routes=ctx.routes,
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

    The graph implements the multi-node topology from design section 8.
    Each node corresponds to one step of the research loop so individual
    steps can be inspected and checkpointed.  Non-serializable objects
    (live ``CodeBehaviorGraphV1``, ``InformationGainTracker``, compiled
    evidence) are held in a ``_ResearchGraphContext`` sidecar that is
    closure-captured by the node and routing functions; the LangGraph
    state channels only carry serializable references (digests, ids,
    counters).

    Topology::

        START
          -> linear_prefix
          -> research_supervisor
          -> supervisor_router
               (stop_blocked)   -> END
               (record_gap)     -> gap_finalizer
               (tool_exec)      -> research_tool
          -> observation_pipeline
          -> evidence_critic
          -> critic_router
               (blocked)        -> END
               (ready_to_author)-> END
               (record_gap)     -> gap_finalizer
               (compile_candidate) -> compile_candidate
               (search_more)    -> research_supervisor
               (inspect_branch) -> research_supervisor
          -> compile_candidate
          -> compile_router
               (compiled)       -> obligation_advancer
               (gap)            -> gap_finalizer
          -> gap_finalizer
          -> gap_router
               (accepted)       -> obligation_advancer
               (rejected)       -> research_supervisor
               (blocked)        -> END
          -> obligation_advancer
          -> advancer_router
               (has_next)       -> research_supervisor
               (no_next)        -> END

    The returned ``CompiledResearchSubgraph`` exposes ``invoke`` (delegated
    to the compiled LangGraph) and ``last_result`` (the most recent
    ``ResearchLoopResult``).
    """

    ctx = _ResearchGraphContext(runtime, max_turns=max_turns)
    holder = _ResultHolder()

    # --- node wrappers --------------------------------------------------

    def _linear_prefix_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_linear_prefix(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _supervisor_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_supervisor(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _tool_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_tool(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _observation_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_observation(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _critic_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_critic(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _compile_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_compile(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _gap_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_gap(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _advancer_node(state: AgentStateV3) -> AgentStateV3:
        update = _ctx_advancer(state, ctx=ctx)
        merged: dict[str, Any] = dict(state)
        merged.update(update)
        return merged  # type: ignore[return-value]

    def _terminator_node(state: AgentStateV3) -> AgentStateV3:
        """Final node: builds and stashes the ``ResearchLoopResult``."""
        result = _ctx_terminate(state, ctx=ctx)
        holder.result = result
        merged: dict[str, Any] = dict(state)
        merged.update(result.final_state)
        return merged  # type: ignore[return-value]

    # --- routing functions ----------------------------------------------

    def _supervisor_router(state: AgentStateV3) -> str:
        return ctx.supervisor_route

    def _critic_router(state: AgentStateV3) -> str:
        return ctx.critic_route

    def _compile_router(state: AgentStateV3) -> str:
        return ctx.compile_route

    def _gap_router(state: AgentStateV3) -> str:
        return ctx.gap_route

    def _advancer_router(state: AgentStateV3) -> str:
        return ctx.advancer_route

    # --- graph topology -------------------------------------------------

    graph = StateGraph(AgentStateV3)
    graph.add_node("linear_prefix", _linear_prefix_node)
    graph.add_node("research_supervisor", _supervisor_node)
    graph.add_node("research_tool", _tool_node)
    graph.add_node("observation_pipeline", _observation_node)
    graph.add_node("evidence_critic", _critic_node)
    graph.add_node("compile_candidate", _compile_node)
    graph.add_node("gap_finalizer", _gap_node)
    graph.add_node("obligation_advancer", _advancer_node)
    graph.add_node("terminator", _terminator_node)

    graph.add_edge(START, "linear_prefix")
    graph.add_edge("linear_prefix", "research_supervisor")

    graph.add_conditional_edges(
        "research_supervisor",
        _supervisor_router,
        {
            "stop_blocked": "terminator",
            "record_gap": "gap_finalizer",
            "tool_exec": "research_tool",
            "no_tool_calls": "terminator",
        },
    )

    graph.add_edge("research_tool", "observation_pipeline")
    graph.add_edge("observation_pipeline", "evidence_critic")

    graph.add_conditional_edges(
        "evidence_critic",
        _critic_router,
        {
            "blocked": "terminator",
            "ready_to_author": "terminator",
            "record_gap": "gap_finalizer",
            "compile_candidate": "compile_candidate",
            "search_more": "research_supervisor",
            "inspect_branch": "research_supervisor",
        },
    )

    graph.add_conditional_edges(
        "compile_candidate",
        _compile_router,
        {
            "compiled": "obligation_advancer",
            "rejected": "research_supervisor",
            "blocked": "terminator",
        },
    )

    graph.add_conditional_edges(
        "gap_finalizer",
        _gap_router,
        {
            "accepted": "obligation_advancer",
            "rejected": "research_supervisor",
            "blocked": "terminator",
        },
    )

    graph.add_conditional_edges(
        "obligation_advancer",
        _advancer_router,
        {
            "has_next": "research_supervisor",
            "no_next": "terminator",
        },
    )

    graph.add_edge("terminator", END)

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
    "list_repository_tree": "SEARCH_SYMBOLS",
    "search_code": "SEARCH_SYMBOLS",
    "read_code_span": "READ_CANDIDATE",
    "inspect_configuration": "INSPECT_CONFIG",
    "build_behavior_subgraph": "BUILD_BEHAVIOR_SUBGRAPH",
    "query_behavior_graph": "BUILD_BEHAVIOR_SUBGRAPH",
    "trace_call_path": "TRACE_CALLS",
    "trace_data_flow": "TRACE_DATA_FLOW",
    "inspect_control_flow": "INSPECT_BRANCH",
    "compare_implementation_branches": "INSPECT_BRANCH",
    "find_output_side_effects": "TRACE_CALLS",
    "search_semantic_hints": "SEARCH_HINTS",
    "derive_code_queries_from_hint": "SEARCH_HINTS",
    "compare_hint_to_code": "SEARCH_HINTS",
    "propose_evidence_packet": "PROPOSE_PACKET",
    "validate_evidence_packet": "PROPOSE_PACKET",
    "compile_code_facts": "COMPILE_FACTS",
    "validate_code_facts": "COMPILE_FACTS",
    "decompose_atomic_claims": "DECOMPOSE_CLAIMS",
    "authorize_atomic_claims": "DECOMPOSE_CLAIMS",
    "record_explicit_code_gap": "RECORD_GAP",
    "check_obligation_coverage": "RECORD_GAP",
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
    "CompiledEvidence",
    "CompiledResearchSubgraph",
    "ResearchLoopDriver",
    "ResearchLoopResult",
    "ResearchLoopState",
    "build_research_subgraph",
    "initial_loop_state",
    "run_research_loop",
]
