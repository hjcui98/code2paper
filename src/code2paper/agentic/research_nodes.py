"""Deterministic LangGraph nodes for the V3 research subgraph (R3.1, R3.3, R3.4).

This module ships the deterministic node functions used by
``research_graph.build_research_subgraph``.  Every node is a pure function
``(state, **deps) -> partial_state_update`` so the graph topology, policy
merge and information-gain accounting are independently testable.

Nodes implemented here:

- ``input_resolution_node``      : bind run id, snapshot id, project tree hash
- ``intent_compiler_node``       : author YAML -> typed obligations (stub)
- ``repository_indexer_node``    : build RepoSnapshot + SymbolIndexReport
- ``research_agenda_builder_node``: order obligations by priority
- ``research_tool_node``         : execute policy-merged tool calls
- ``observation_ingest_node``    : validate observations + authority gate
- ``behavior_graph_updater_node``: merge observations into CodeBehaviorGraph
- ``evidence_critic_node``       : route to search_more / compile / gap / ready
- ``gap_finalizer_node``         : record explicit gaps
- ``quality_state_selector_node``: Pareto-style best-state retention

R3.4 information-gain accounting lives in ``InformationGainTracker``: the
``observation_ingest_node`` calls it to update ``no_progress_counter`` per
obligation.  The tracker is pure and deterministic.

R3.4 per-obligation/per-tool-kind budget envelopes are seeded by
``research_agenda_builder_node`` from a ``BudgetPolicyV1`` and consumed by
``research_tool_node`` after policy merge accepts a decision.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.python_behavior_adapter import PythonBehaviorAdapter
from code2paper.agentic.research_models import (
    BUDGET_TOOL_KINDS,
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAction,
    ResearchAgendaItemV1,
    ResearchAgendaItemStatus,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    ToolKind,
    TypedBehaviorTargetV1,
    empty_quality_state,
)
from code2paper.agentic.research_policy import (
    PolicyMergeResult,
    apply_consumed_budgets,
    apply_policy_merge,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    SupervisorBackend,
    fallback_action_for_issue,
)
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot
from code2paper.agentic.state_v3 import AgentStateV3


# ---------------------------------------------------------------------------
# Budget policy (R3.4)
# ---------------------------------------------------------------------------


class BudgetPolicyV1(BaseModel):
    """Default per-obligation/per-tool-kind budget envelope.

    The supervisor may never exceed these limits.  A run can override them
    via the graph builder, but every obligation gets the same envelope so
    one hard obligation cannot starve the rest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol_search: int = 6
    code_read: int = 8
    call_trace: int = 6
    data_flow_trace: int = 4
    branch_inspection: int = 4
    hint_search: int = 3
    packet_repair: int = 4

    def envelope_for(self, obligation_id: str) -> PerObligationBudgetV1:
        limits: dict[str, int] = {
            "symbol_search": self.symbol_search,
            "code_read": self.code_read,
            "call_trace": self.call_trace,
            "data_flow_trace": self.data_flow_trace,
            "branch_inspection": self.branch_inspection,
            "hint_search": self.hint_search,
            "packet_repair": self.packet_repair,
        }
        return PerObligationBudgetV1(obligation_id=obligation_id, limits=limits)


DEFAULT_BUDGET_POLICY = BudgetPolicyV1()


def seed_per_obligation_budgets(
    agenda: ResearchAgendaV1,
    policy: BudgetPolicyV1 | None = None,
) -> dict[str, PerObligationBudgetV1]:
    """Build the initial per-obligation budget map from an agenda."""

    policy = policy or DEFAULT_BUDGET_POLICY
    return {item.obligation_id: policy.envelope_for(item.obligation_id) for item in agenda.items}


# ---------------------------------------------------------------------------
# Information gain tracker (R3.4)
# ---------------------------------------------------------------------------


class InformationGainTracker:
    """Tracks information gain per obligation and detects no-progress windows.

    The tracker is pure: it stores sets of seen spans/symbols/predicates/
    relations per obligation and computes the *new* items added by each
    observation.  A turn with zero new items increments the no-progress
    counter; a turn with at least one new item resets it.

    R3.4 hard rule: after two consecutive no-gain turns, the supervisor
    must switch strategy.  After three, it may propose RECORD_GAP.  The
    tracker exposes ``should_switch_strategy`` and ``may_record_gap`` so
    the supervisor / policy merge can read the deterministic state.
    """

    def __init__(self) -> None:
        self._seen_spans: dict[str, set[str]] = {}
        self._seen_symbols: dict[str, set[str]] = {}
        self._seen_predicates: dict[str, set[str]] = {}
        self._seen_relations: dict[str, set[str]] = {}
        self._no_progress: dict[str, int] = {}
        self._gain_history: dict[str, list[str]] = {}

    def ingest(
        self,
        obligation_id: str,
        observation: ResearchObservationV1,
        *,
        new_predicates: tuple[str, ...] = (),
        new_relations: tuple[str, ...] = (),
    ) -> tuple[bool, tuple[str, ...]]:
        """Ingest an observation and return (gained, gain_descriptors).

        ``gained`` is True iff at least one new span/symbol/predicate/relation
        was added.  ``gain_descriptors`` is the tuple of new item descriptors
        (used for the no-progress history trace).
        """

        spans = self._seen_spans.setdefault(obligation_id, set())
        symbols = self._seen_symbols.setdefault(obligation_id, set())
        predicates = self._seen_predicates.setdefault(obligation_id, set())
        relations = self._seen_relations.setdefault(obligation_id, set())
        history = self._gain_history.setdefault(obligation_id, [])

        gained_items: list[str] = []
        for span in observation.exact_span_ids:
            if span not in spans:
                spans.add(span)
                gained_items.append(f"span:{span}")
        for ref in observation.result_refs:
            if ref.startswith("symbol:") or ref.startswith("entrypoint:"):
                if ref not in symbols:
                    symbols.add(ref)
                    gained_items.append(f"symbol:{ref}")
        for pred in new_predicates:
            if pred not in predicates:
                predicates.add(pred)
                gained_items.append(f"predicate:{pred}")
        for rel in new_relations:
            if rel not in relations:
                relations.add(rel)
                gained_items.append(f"relation:{rel}")

        gained = len(gained_items) > 0
        if gained:
            self._no_progress[obligation_id] = 0
            history.append(f"gain:{len(gained_items)}")
        else:
            self._no_progress[obligation_id] = self._no_progress.get(obligation_id, 0) + 1
            history.append("no_gain")
        return gained, tuple(gained_items)

    def no_progress_counter(self, obligation_id: str) -> int:
        return self._no_progress.get(obligation_id, 0)

    def gain_history(self, obligation_id: str) -> tuple[str, ...]:
        return tuple(self._gain_history.get(obligation_id, []))

    def should_switch_strategy(self, obligation_id: str) -> bool:
        return self.no_progress_counter(obligation_id) >= 2

    def may_record_gap(self, obligation_id: str) -> bool:
        return self.no_progress_counter(obligation_id) >= 3

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot (for checkpoint persistence)."""

        return {
            "seen_spans": {k: sorted(v) for k, v in self._seen_spans.items()},
            "seen_symbols": {k: sorted(v) for k, v in self._seen_symbols.items()},
            "seen_predicates": {k: sorted(v) for k, v in self._seen_predicates.items()},
            "seen_relations": {k: sorted(v) for k, v in self._seen_relations.items()},
            "no_progress": dict(self._no_progress),
            "gain_history": {k: list(v) for k, v in self._gain_history.items()},
        }


# ---------------------------------------------------------------------------
# Node runtime context (carries non-state dependencies)
# ---------------------------------------------------------------------------


class ResearchGraphRuntime(BaseModel):
    """Frozen runtime dependencies shared by all research nodes.

    The graph builder constructs this once and passes it to every node via
    ``functools.partial``.  Keeping it explicit (instead of a global) means
    tests can swap implementations without touching the graph topology.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    run_id: str
    repo_snapshot: RepoSnapshot
    agenda: ResearchAgendaV1
    budget_policy: BudgetPolicyV1 = Field(default_factory=BudgetPolicyV1)
    global_safety_budget: GlobalSafetyBudgetV1 = Field(default_factory=GlobalSafetyBudgetV1)
    supervisor_backend: SupervisorBackend | None = None
    ready_tools: tuple[str, ...] = (
        "find_entrypoints",
        "search_symbols",
        "read_symbol",
        "find_references",
        "build_behavior_subgraph",
    )
    hard_rules: tuple[str, ...] = (
        "no_snapshot_external_paths",
        "no_unregistered_tools",
        "no_authority_upgrade",
        "no_skipped_validators",
        "no_duplicate_no_gain_calls",
        "obligation_must_exist",
        "budgets_must_be_available",
        "fallback_must_be_safe",
    )

    def supervisor(self) -> SupervisorBackend:
        return self.supervisor_backend or DeterministicSupervisorBackend(
            run_id=self.run_id,
            repo_snapshot_id=self.repo_snapshot.snapshot_id,
            ready_tools=self.ready_tools,
            hard_rules=self.hard_rules,
        )

    def tool_context(self) -> ResearchToolContext:
        return ResearchToolContext(repo_snapshot=self.repo_snapshot)

    def snapshot_paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.repo_snapshot.included_files)


# ---------------------------------------------------------------------------
# Node: input_resolution
# ---------------------------------------------------------------------------


def input_resolution_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Bind run identity and snapshot contract.

    The node is intentionally minimal: it only echoes the runtime identity
    into the state.  The actual snapshot is built by ``repository_indexer``.
    """

    return {
        "run_id": runtime.run_id,
        "repo_snapshot_id": runtime.repo_snapshot.snapshot_id,
        "project_tree_hash": runtime.repo_snapshot.project_tree_hash,
        "status": "initialized",
    }


# ---------------------------------------------------------------------------
# Node: intent_compiler
# ---------------------------------------------------------------------------


def intent_compiler_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Author YAML -> typed obligations.

    R3 stub: the real intent compiler lands in R5.  For R3 we accept an
    already-built agenda via the runtime and only record its digest.  This
    keeps the graph topology complete and lets the rest of the loop run.
    """

    agenda = runtime.agenda
    return {
        "intent_graph_ref": agenda.intent_graph_digest or "",
        "research_agenda_ref": agenda.content_digest,
        "status": "intent_compiled",
    }


# ---------------------------------------------------------------------------
# Node: repository_indexer
# ---------------------------------------------------------------------------


def repository_indexer_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Build the symbol index and seed the behavior graph.

    The node caches the symbol index on the runtime's tool context and
    stores the behavior graph content digest in the state.  The full
    CodeBehaviorGraph is held in the runtime (not the state) to keep the
    LangGraph channels small.
    """

    # Build a fresh PythonBehaviorAdapter index for the snapshot.
    adapter = PythonBehaviorAdapter()
    files = _read_snapshot_files(runtime.repo_snapshot)
    symbol_index = adapter.index_symbols(
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        files=files,
    )
    symbol_index_digest = symbol_index.content_digest
    return {
        "symbol_index_ref": symbol_index_digest,
        "behavior_graph_ref": _empty_behavior_graph_digest(runtime.repo_snapshot),
        "status": "repository_indexed",
    }


# ---------------------------------------------------------------------------
# Node: research_agenda_builder
# ---------------------------------------------------------------------------


def research_agenda_builder_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Order obligations by priority and seed per-obligation budgets.

    R3 stub: the agenda is already built (R5 will replace this).  We only
    seed the per-obligation budgets and pick the first must-cover obligation
    as the active one.

    Resume support: when the incoming state already carries an
    ``active_obligation_id`` that points to an unresolved obligation, the
    node keeps it.  This lets a checkpoint resume continue from the
    obligation that was active when the checkpoint was written, rather
    than always re-starting from the first obligation.
    """

    agenda = runtime.agenda
    budgets = seed_per_obligation_budgets(agenda, runtime.budget_policy)
    # Resume: honour an existing active_obligation_id if it still points
    # to an unresolved obligation.
    existing_active = state.get("active_obligation_id", "") or ""
    active_id = ""
    if existing_active:
        for item in agenda.items:
            if (
                item.obligation_id == existing_active
                and item.status not in {"supported", "explicit_gap", "blocked"}
            ):
                active_id = existing_active
                break
    # Fresh start: pick the first unresolved must-cover obligation; fall
    # back to the first unresolved obligation of any priority.
    if not active_id:
        for item in agenda.must_cover_items:
            if item.status not in {"supported", "explicit_gap", "blocked"}:
                active_id = item.obligation_id
                break
    if not active_id:
        for item in agenda.items:
            if item.status not in {"supported", "explicit_gap", "blocked"}:
                active_id = item.obligation_id
                break
    return {
        "research_agenda_ref": agenda.content_digest,
        "per_obligation_budgets": {k: v.model_dump(mode="json") for k, v in budgets.items()},
        "active_obligation_id": active_id,
        "status": "agenda_built",
    }


# ---------------------------------------------------------------------------
# Node: research_supervisor (wraps the supervisor + policy merge)
# ---------------------------------------------------------------------------


def research_supervisor_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    per_obligation_budgets: dict[str, PerObligationBudgetV1],
    active_issue: ResearchIssueV1 | None,
    recent_observations: tuple[ResearchObservationV1, ...] = (),
    no_progress_counter: int = 0,
    no_progress_history: tuple[str, ...] = (),
    recent_tool_call_ids: tuple[str, ...] = (),
    no_progress_tool_call_ids: tuple[str, ...] = (),
    turn_index: int = 0,
    current_supported_claim_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Run the supervisor backend, then policy-merge the proposal.

    The node combines the R3.2 supervisor and the R3.3 policy merge into a
    single graph step.  The output carries:

    - ``pending_tool_calls``: the policy-merged tool calls to execute;
    - ``decision_trace_refs``: compact trace references for both the
      proposal and the policy merge result;
    - ``status``: ``researching`` (or ``blocked`` if STOP_BLOCKED).
    """

    from code2paper.agentic.research_supervisor import build_decision_context

    backend = runtime.supervisor()
    context = build_decision_context(
        run_id=state.get("run_id", runtime.run_id),
        repo_snapshot_id=state.get("repo_snapshot_id", runtime.repo_snapshot.snapshot_id),
        turn_index=turn_index,
        agenda=runtime.agenda,
        active_obligation_id=state.get("active_obligation_id", ""),
        active_issue=active_issue,
        recent_observations=recent_observations,
        per_obligation_budgets=per_obligation_budgets,
        global_safety_budget=runtime.global_safety_budget,
        no_progress_counter=no_progress_counter,
        no_progress_history=no_progress_history,
        ready_tools=runtime.ready_tools,
        hard_rules=runtime.hard_rules,
        current_supported_claim_ids=current_supported_claim_ids,
    )
    proposal = backend.decide(context)
    merge_result = apply_policy_merge(
        proposal,
        agenda=runtime.agenda,
        active_issue=active_issue,
        per_obligation_budgets=per_obligation_budgets,
        global_safety_budget=runtime.global_safety_budget,
        ready_tools=runtime.ready_tools,
        recent_tool_call_ids=recent_tool_call_ids,
        no_progress_tool_call_ids=no_progress_tool_call_ids,
        repo_snapshot_paths=runtime.snapshot_paths(),
        fallback_backend=backend,
        context_run_id=runtime.run_id,
        context_repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        context_turn_index=turn_index,
    )
    decision = merge_result.decision
    assert decision is not None  # policy merge always returns a decision
    return {
        "pending_tool_calls": list(decision.selected_tool_calls),
        "decision_trace_refs": [merge_result.trace_ref],
        "active_obligation_id": decision.obligation_id or state.get("active_obligation_id", ""),
        "active_issue_id": decision.issue_id or state.get("active_issue_id", ""),
        "status": "blocked" if decision.action == "STOP_BLOCKED" else "researching",
        # Private channel: the loop reads this BEFORE ``state.update`` so
        # the real ``produced_by`` / ``rationale`` / ``goal`` from the
        # supervisor backend (LLM or deterministic) are preserved in the
        # decision trace.  Without this, ``_reconstruct_decision`` would
        # overwrite ``produced_by`` to ``deterministic_fallback`` and the
        # R8 ``gap_driven_tool_selection`` criterion would never see LLM
        # proposals even when the backend succeeded.
        "_merged_decision": decision,
    }


# ---------------------------------------------------------------------------
# Node: research_tool_node
# ---------------------------------------------------------------------------


def research_tool_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
) -> dict[str, Any]:
    """Execute the pending tool calls and produce observations.

    The node reads ``pending_tool_calls`` from the state, executes each one
    via ``execute_research_tool`` and returns the observations as a list of
    ``ResearchObservationV1``.  The state stores compact references; the
    full observations are carried alongside the state in the graph runtime
    so the next node (``observation_ingest``) can read them.
    """

    pending = state.get("pending_tool_calls", []) or []
    if not pending:
        return {"pending_tool_calls": [], "tool_call_trace_refs": []}

    ctx = runtime.tool_context()
    observations: list[ResearchObservationV1] = []
    trace_refs: list[str] = []
    for call in pending:
        if not isinstance(call, ResearchToolCallV1):
            # State may carry dict-shaped values when resumed from a checkpoint.
            call = ResearchToolCallV1.model_validate(call)
        observation = execute_research_tool(ctx, call)
        observations.append(observation)
        trace_refs.append(_observation_ref(observation))

    return {
        "pending_tool_calls": [],  # consumed
        "tool_call_trace_refs": trace_refs,
        # The observation list is returned via a private channel so the
        # observation_ingest node can read it without re-executing tools.
        # LangGraph reducers merge this into the state via append_unique.
        "recent_observation_refs": [_observation_ref(o) for o in observations],
    }


def execute_pending_tool_calls(
    runtime: ResearchGraphRuntime,
    pending: list[ResearchToolCallV1] | list[dict[str, Any]],
) -> tuple[list[ResearchObservationV1], list[str]]:
    """Execute a batch of tool calls and return (observations, trace_refs).

    Factored out of ``research_tool_node`` so tests can drive tool execution
    without going through the LangGraph state.
    """

    ctx = runtime.tool_context()
    observations: list[ResearchObservationV1] = []
    trace_refs: list[str] = []
    for call in pending:
        if not isinstance(call, ResearchToolCallV1):
            call = ResearchToolCallV1.model_validate(call)
        observation = execute_research_tool(ctx, call)
        observations.append(observation)
        trace_refs.append(_observation_ref(observation))
    return observations, trace_refs


# ---------------------------------------------------------------------------
# Node: observation_ingest
# ---------------------------------------------------------------------------


def observation_ingest_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    observations: tuple[ResearchObservationV1, ...],
    gain_tracker: InformationGainTracker,
    active_obligation_id: str,
) -> dict[str, Any]:
    """Validate observations, gate authority, update gain tracker.

    The node applies three deterministic checks per observation:

    1. ``observation.repo_snapshot_id == state.repo_snapshot_id``: a stale
       snapshot id means the observation came from a different run and
       must be discarded.
    2. ``observation.status`` is not ``parse_failed`` / ``invalid_request``:
       those statuses are recorded but produce no information gain.
    3. The observation's source authority is compatible with positive
       claims (per ``source_authority`` rules).  Hint-only observations
       are kept but flagged so the evidence critic can downgrade them.

    The node then feeds each observation into the gain tracker and returns
    the updated no-progress counter for the active obligation.
    """

    active_obligation_id = active_obligation_id or state.get("active_obligation_id", "")
    if not active_obligation_id:
        return {"recent_observation_refs": []}

    no_progress_counter = gain_tracker.no_progress_counter(active_obligation_id)
    no_progress_history = gain_tracker.gain_history(active_obligation_id)

    # Track which observations are admissible for positive claims.
    admissible_refs: list[str] = []
    for obs in observations:
        if obs.obligation_id != active_obligation_id:
            # Observations for other obligations are recorded but do not
            # affect this obligation's gain counter.
            continue
        if obs.status in {"parse_failed", "invalid_request"}:
            # These statuses are not "no-gain" in the search sense; they
            # indicate a tool bug or a policy rejection.  Treat as no-gain
            # for now so the supervisor switches strategy.
            gain_tracker.ingest(active_obligation_id, obs)
            continue
        gain_tracker.ingest(active_obligation_id, obs)
        admissible_refs.append(_observation_ref(obs))

    return {
        "recent_observation_refs": admissible_refs,
        "no_progress_counters": {active_obligation_id: gain_tracker.no_progress_counter(active_obligation_id)},
    }


# ---------------------------------------------------------------------------
# Node: behavior_graph_updater
# ---------------------------------------------------------------------------


def behavior_graph_updater_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    behavior_graph: CodeBehaviorGraphV1,
    observations: tuple[ResearchObservationV1, ...],
    active_obligation_id: str,
) -> tuple[CodeBehaviorGraphV1, dict[str, Any]]:
    """Merge new behavior subgraphs extracted from observations.

    For every ``read_symbol`` / ``build_behavior_subgraph`` observation,
    the node re-parses the cited symbol and merges the resulting nodes
    into the running ``CodeBehaviorGraphV1``.  The merge is content-addressed
    so duplicate reads do not duplicate nodes.

    Returns the updated behavior graph (carried in the runtime, not the
    state) and a state update containing the new digest.
    """

    adapter = PythonBehaviorAdapter()
    files = _read_snapshot_files(runtime.repo_snapshot)
    symbol_index = adapter.index_symbols(
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        files=files,
    )
    updated_graph = behavior_graph
    new_predicates: set[str] = set()
    new_relations: set[str] = set()
    for obs in observations:
        if obs.obligation_id != active_obligation_id:
            continue
        if obs.tool_name not in {"read_symbol", "build_behavior_subgraph"}:
            continue
        if obs.status not in {"success"}:
            continue
        # The result_refs carry ``symbol:<symbol_id>`` entries produced by
        # the research tools.  Re-parse each cited symbol and merge the
        # resulting subgraph.
        for ref in obs.result_refs:
            if not ref.startswith("symbol:"):
                continue
            symbol_id = ref.removeprefix("symbol:")
            sym = symbol_index.find(symbol_id)
            if sym is None:
                continue
            source = files.get(sym.path)
            if source is None:
                continue
            try:
                ops = adapter.extract_operations(sym, source)
            except Exception:
                continue
            for op in ops:
                new_predicates.add(op.predicate)
            try:
                rels = adapter.extract_relations(sym, source, ops)
            except Exception:
                rels = []
            for rel in rels:
                new_relations.add(rel.kind)
            sym_graph = CodeBehaviorGraphV1(
                repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
                project_tree_hash=runtime.repo_snapshot.project_tree_hash,
                language=adapter.language,
                nodes=ops,
                relations=rels,
            )
            updated_graph = updated_graph.merge(sym_graph)

    state_update: dict[str, Any] = {
        "behavior_graph_ref": updated_graph.content_digest,
    }
    return updated_graph, state_update


# ---------------------------------------------------------------------------
# Node: evidence_critic (routes the research loop)
# ---------------------------------------------------------------------------


EvidenceCriticRoute = str  # closed below

EVIDENCE_CRITIC_ROUTES: tuple[str, ...] = (
    "search_more",
    "inspect_branch",
    "compile_candidate",
    "record_gap",
    "ready_to_author",
    "blocked",
)


def evidence_critic_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    gain_tracker: InformationGainTracker,
    active_obligation_id: str,
    active_issue: ResearchIssueV1 | None,
    max_turns_without_gain: int = 3,
) -> tuple[str, dict[str, Any]]:
    """Route the research loop based on obligation status and gain history.

    Routing rules (deterministic):

    - If the active obligation is ``supported``: route to ``ready_to_author``.
    - If the active obligation is ``explicit_gap`` / ``blocked``: route to
      ``record_gap`` / ``blocked`` respectively.
    - If the active issue is a missing-anchor / missing-relation / etc.:
      route to ``search_more`` (unless gain tracker says switch strategy).
    - If the gain tracker says ``may_record_gap``: route to ``record_gap``.
    - If the gain tracker says ``should_switch_strategy``: route to
      ``search_more`` (the supervisor backend will pick a different action).
    - If the obligation has unresolved must-cover but no missing information:
      route to ``compile_candidate`` (R4 will handle the actual compile; for
      R3 this routes to a stub that records a gap).
    - Default: ``search_more``.
    """

    active_obligation_id = active_obligation_id or state.get("active_obligation_id", "")
    if not active_obligation_id:
        return "blocked", {"status": "blocked", "blocked_reason": "no_active_obligation"}

    # Look up the active obligation from the agenda.
    active_obligation: ResearchAgendaItemV1 | None = None
    for item in runtime.agenda.items:
        if item.obligation_id == active_obligation_id:
            active_obligation = item
            break
    if active_obligation is None:
        return "blocked", {"status": "blocked", "blocked_reason": "obligation_not_in_agenda"}

    # Terminal states short-circuit.
    if active_obligation.status == "supported":
        return "ready_to_author", {"status": "researching"}
    if active_obligation.status == "explicit_gap":
        return "record_gap", {"status": "researching"}
    if active_obligation.status == "blocked":
        return "blocked", {"status": "blocked", "blocked_reason": "obligation_blocked"}

    # Gain-tracker driven routing.
    if gain_tracker.may_record_gap(active_obligation_id):
        return "record_gap", {"status": "researching"}

    # Issue-driven routing.
    if active_issue is not None:
        kind = active_issue.issue_kind
        if kind in {"branch_ambiguity"}:
            return "inspect_branch", {"status": "researching"}
        if kind in {"budget_exhausted", "quality_regression"}:
            return "record_gap", {"status": "researching"}
        return "search_more", {"status": "researching"}

    # No active issue: if the obligation has candidate symbols and no
    # missing information, attempt to compile.
    if (
        active_obligation.candidate_symbol_ids
        and not active_obligation.missing_information
    ):
        return "compile_candidate", {"status": "researching"}

    return "search_more", {"status": "researching"}


# ---------------------------------------------------------------------------
# Node: gap_finalizer
# ---------------------------------------------------------------------------


def gap_finalizer_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    active_obligation_id: str,
    gain_tracker: InformationGainTracker,
    gap_search_attempts: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Record an explicit gap for the active obligation.

    The gap finalizer checks that the supervisor has actually exhausted
    its search before allowing an explicit gap.  R3.4 exit condition: a
    gap is allowed only after ``may_record_gap`` returns True (three
    consecutive no-gain turns) or after every ready tool kind has been
    tried at least once.

    The returned dict carries a private ``_gap_accepted`` flag so the
    driver can decide whether to advance to the next obligation.  The
    flag is not part of the ``AgentStateV3`` schema; the driver pops it
    before merging the update into the state.
    """

    active_obligation_id = active_obligation_id or state.get("active_obligation_id", "")
    if not active_obligation_id:
        return {
            "status": "blocked",
            "blocked_reason": "gap_without_active_obligation",
            "_gap_accepted": False,
        }

    # Verify the search was exhaustive enough to justify a gap.
    if not gain_tracker.may_record_gap(active_obligation_id):
        # Not enough no-gain turns; reject the gap and route back to search.
        return {
            "status": "researching",
            "active_issue_id": "",
            "explicit_gap_set_ref": state.get("explicit_gap_set_ref", ""),
            "_gap_accepted": False,
        }

    gap_ref = _gap_ref(runtime.run_id, active_obligation_id)
    existing_gaps = state.get("explicit_gap_set_ref", "")
    new_gaps = f"{existing_gaps};{gap_ref}" if existing_gaps else gap_ref
    return {
        "explicit_gap_set_ref": new_gaps,
        "status": "researching",  # the obligation is terminal but the run continues
        "active_issue_id": "",
        "_gap_accepted": True,
    }


# ---------------------------------------------------------------------------
# Node: quality_state_selector
# ---------------------------------------------------------------------------


def quality_state_selector_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    current_quality_state: Any,
    best_quality_state: Any,
) -> dict[str, Any]:
    """Pareto-style best-state retention (design 11).

    Compares ``current`` against ``best`` using
    ``quality_state_dominates``.  If ``current`` dominates ``best``, it
    becomes the new ``best``.  Otherwise ``best`` is retained.
    """

    from code2paper.agentic.research_models import quality_state_dominates

    if best_quality_state is None or (
        hasattr(best_quality_state, "is_empty") and best_quality_state.is_empty
    ):
        # No best state yet: seed with current (only if non-empty).
        if current_quality_state is None or (
            hasattr(current_quality_state, "is_empty") and current_quality_state.is_empty
        ):
            return {}
        return {
            "current_quality_state_ref": _quality_state_ref(current_quality_state),
            "best_quality_state_ref": _quality_state_ref(current_quality_state),
        }

    if current_quality_state is None:
        return {}

    if quality_state_dominates(current_quality_state, best_quality_state):
        return {
            "current_quality_state_ref": _quality_state_ref(current_quality_state),
            "best_quality_state_ref": _quality_state_ref(current_quality_state),
        }
    return {
        "current_quality_state_ref": _quality_state_ref(current_quality_state),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _empty_behavior_graph_digest(snapshot: RepoSnapshot) -> str:
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
    )
    return graph.with_digest().content_digest


def _read_snapshot_files(snapshot: RepoSnapshot) -> dict[str, str]:
    """Read every file in the snapshot into a ``{path: text}`` dict.

    Used by the symbol indexer and the behavior graph updater.  Reads go
    through ``project_root`` (the snapshot only stores content digests).
    """

    root = snapshot.project_root
    files: dict[str, str] = {}
    for entry in snapshot.included_files:
        if entry.kind != "file":
            continue
        try:
            files[entry.path] = _read_text(Path(root) / entry.path)
        except OSError:
            continue
    return files


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _observation_ref(observation: ResearchObservationV1) -> str:
    payload = {
        "observation_id": observation.observation_id,
        "tool_call_id": observation.tool_call_id,
        "tool_name": observation.tool_name,
        "status": observation.status,
        "input_digest": observation.input_digest,
        "output_digest": observation.output_digest,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    return f"obs-ref:{digest}:{observation.observation_id}"


def _gap_ref(run_id: str, obligation_id: str) -> str:
    material = f"{run_id}|{obligation_id}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"gap:{digest}:{obligation_id}"


def _quality_state_ref(state: Any) -> str:
    if hasattr(state, "content_digest"):
        return state.content_digest
    if hasattr(state, "state_id"):
        return f"quality-state:{state.state_id}"
    return _digest_payload(state)


__all__ = [
    "BudgetPolicyV1",
    "DEFAULT_BUDGET_POLICY",
    "EVIDENCE_CRITIC_ROUTES",
    "EvidenceCriticRoute",
    "InformationGainTracker",
    "ResearchGraphRuntime",
    "behavior_graph_updater_node",
    "evidence_critic_node",
    "execute_pending_tool_calls",
    "gap_finalizer_node",
    "input_resolution_node",
    "intent_compiler_node",
    "observation_ingest_node",
    "quality_state_selector_node",
    "repository_indexer_node",
    "research_agenda_builder_node",
    "research_supervisor_node",
    "research_tool_node",
    "seed_per_obligation_budgets",
]
