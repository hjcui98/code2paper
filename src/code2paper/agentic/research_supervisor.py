"""Research supervisor node and decision context (R3.1 + R3.2).

Implements the LangGraph ``research_supervisor`` node from design section 8
and the compact ``ResearchDecisionContextV1`` from R3.2.

Hard rules (design 3.2, 8.2, 8.3):

- The supervisor never sees the full repository source, the full evidence
  JSON or the entire tool history.  It only receives a compact
  ``ResearchDecisionContextV1`` containing the active obligation, typed
  behavior targets, missing information, top candidate symbols, recent
  observations, no-progress history, remaining budgets and the allowed
  action set.
- The supervisor returns a ``ResearchDecisionV1`` proposal.  Every proposal
  is validated by ``research_policy.apply_policy_merge`` before any tool
  call is executed.  A rejected proposal is replaced by a deterministic
  fallback decision keyed on the active issue kind.
- The supervisor backend is pluggable: tests use
  ``DeterministicSupervisorBackend`` (scripted by issue kind), production
  uses a Gemma-backed implementation that lands in a later batch.  The
  protocol guarantees the graph topology and policy merge are independently
  testable without an LLM.

R3 scope: this module ships the context model, the backend protocol, the
deterministic fallback table, and the LangGraph node function.  The node
does not call any LLM directly; it delegates to the configured backend.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from code2paper.agentic.research_models import (
    BUDGET_TOOL_KINDS,
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAction,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    TypedBehaviorTargetV1,
    ToolKind,
)
from code2paper.agentic.state_v3 import AgentStateV3


# ---------------------------------------------------------------------------
# Decision context (R3.2)
# ---------------------------------------------------------------------------


class RecentObservationSummaryV1(BaseModel):
    """Compact summary of a recent observation fed to the supervisor.

    The supervisor never sees the full observation payload, only the
    fields below.  This keeps prompts small and prevents the model from
    inventing spans that did not appear in the actual observation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    tool_call_id: str
    tool_name: str
    status: str
    source_authority: str
    result_refs: tuple[str, ...] = Field(default_factory=tuple)
    exact_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    truncated: bool = False
    ambiguous: bool = False
    candidate_count: int = 0
    obligation_id: str = ""


class ResearchDecisionContextV1(BaseModel):
    """Compact context the supervisor sees each turn (R3.2).

    Hard rule (design 8.2): the supervisor prompt MUST be assembled from
    this model.  Injecting raw source code, full evidence JSON or the full
    tool history into the prompt is a contract violation.

    The context is built by ``build_decision_context`` from the LangGraph
    state plus the active obligation and recent observations.  It is
    deliberately small so a Gemma-class model can attend to every field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    repo_snapshot_id: str
    turn_index: int
    active_obligation: ResearchAgendaItemV1 | None = None
    active_issue: ResearchIssueV1 | None = None
    typed_behavior_targets: tuple[TypedBehaviorTargetV1, ...] = Field(default_factory=tuple)
    current_supported_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    missing_information: tuple[str, ...] = Field(default_factory=tuple)
    top_candidate_symbol_ids: tuple[str, ...] = Field(default_factory=tuple)
    top_candidate_behavior_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    recent_observations: tuple[RecentObservationSummaryV1, ...] = Field(default_factory=tuple)
    no_progress_counter: int = 0
    no_progress_history: tuple[str, ...] = Field(default_factory=tuple)
    remaining_budgets: dict[str, int] = Field(default_factory=dict)
    per_obligation_remaining: dict[str, int] = Field(default_factory=dict)
    allowed_actions: tuple[ResearchAction, ...] = Field(default_factory=tuple)
    ready_tools: tuple[str, ...] = Field(default_factory=tuple)
    hard_rules: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_must_cover_ids: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("run_id", "repo_snapshot_id")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("turn_index")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("turn_index must be nonnegative")
        return value


# ---------------------------------------------------------------------------
# Supervisor backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SupervisorBackend(Protocol):
    """Pluggable supervisor backend.

    Implementations:

    - ``DeterministicSupervisorBackend``: scripted by issue kind / obligation
      state, used by tests and as the parse-failure fallback.
    - (future) ``GemmaSupervisorBackend``: calls the local Gemma inference
      endpoint and parses the structured decision.

    The backend MUST be deterministic given its inputs and script.  Any
    randomness (e.g. sampling temperature) belongs inside the Gemma
    backend, not in the protocol.
    """

    def decide(self, context: ResearchDecisionContextV1) -> ResearchDecisionV1:
        """Return a structured decision proposal.

        The returned decision is a *proposal*: policy merge may still reject
        it and substitute a fallback.  The backend MUST NOT execute tools
        or mutate state directly.
        """
        ...


# ---------------------------------------------------------------------------
# Deterministic fallback table (R3.3 parse-failure / no-gain fallback)
# ---------------------------------------------------------------------------


# When the supervisor proposal is rejected (or the LLM failed to parse),
# policy merge picks a deterministic fallback action keyed on the active
# issue kind.  The table below is the single source of truth for these
# fallbacks so tests can enumerate every entry.
#
# Each entry maps an issue kind to (action, fallback_action).  The action
# is what the fallback decision proposes; the fallback_action is what
# policy merge will try next if this fallback is itself rejected (usually
# RECORD_GAP or STOP_BLOCKED).

_ISSUE_KIND_FALLBACKS: dict[str, tuple[ResearchAction, ResearchAction]] = {
    "missing_anchor": ("SEARCH_SYMBOLS", "RECORD_GAP"),
    "missing_relation": ("TRACE_CALLS", "RECORD_GAP"),
    "missing_condition": ("INSPECT_CONFIG", "RECORD_GAP"),
    "wrong_span_role": ("READ_CANDIDATE", "RECORD_GAP"),
    "direct_evidence_semantically_unrelated": ("READ_CANDIDATE", "RECORD_GAP"),
    "branch_ambiguity": ("INSPECT_BRANCH", "RECORD_GAP"),
    "config_ambiguity": ("INSPECT_CONFIG", "RECORD_GAP"),
    "no_semantically_matching_projected_claim": ("COMPILE_FACTS", "RECORD_GAP"),
    "sentence_claim_atomicity": ("DECOMPOSE_CLAIMS", "RECORD_GAP"),
    "formula_unsupported": ("COMPILE_FACTS", "RECORD_GAP"),
    "hint_code_conflict": ("SEARCH_HINTS", "RECORD_GAP"),
    "truncated_observation": ("SEARCH_SYMBOLS", "RECORD_GAP"),
    "ambiguous_observation": ("SEARCH_SYMBOLS", "RECORD_GAP"),
    "no_information_gain": ("SEARCH_SYMBOLS", "RECORD_GAP"),
    "budget_exhausted": ("RECORD_GAP", "STOP_BLOCKED"),
    "quality_regression": ("RECORD_GAP", "STOP_BLOCKED"),
}

# Fallback when there is no active issue but the obligation is unresolved.
# Picks the first action that matches the obligation's missing information
# shape; defaults to SEARCH_SYMBOLS.
_NO_ISSUE_FALLBACK: tuple[ResearchAction, ResearchAction] = (
    "SEARCH_SYMBOLS",
    "RECORD_GAP",
)


def fallback_action_for_issue(
    issue: ResearchIssueV1 | None,
) -> tuple[ResearchAction, ResearchAction]:
    """Return the deterministic fallback (action, next_fallback) for an issue."""

    if issue is None:
        return _NO_ISSUE_FALLBACK
    return _ISSUE_KIND_FALLBACKS.get(issue.issue_kind, _NO_ISSUE_FALLBACK)


def all_fallback_issue_kinds() -> tuple[str, ...]:
    """Return the issue kinds that have a deterministic fallback (for tests)."""

    return tuple(sorted(_ISSUE_KIND_FALLBACKS.keys()))


# ---------------------------------------------------------------------------
# Deterministic supervisor backend
# ---------------------------------------------------------------------------


class DeterministicSupervisorBackend:
    """Scripted supervisor backend used by tests and as fallback.

    The backend picks an action based on (1) the active issue kind, then
    (2) the active obligation's missing information shape, then (3) a
    default SEARCH_SYMBOLS.  It produces ``ResearchToolCallV1`` proposals
    for the chosen action with arguments derived from the context.

    The backend is intentionally simple: it exists so the graph topology,
    policy merge, no-progress escalation and checkpoint resume are fully
    testable without an LLM.  A real Gemma backend can be plugged in
    later without changing any graph wiring.
    """

    def __init__(
        self,
        *,
        run_id: str,
        repo_snapshot_id: str,
        ready_tools: tuple[str, ...] = (
            "find_entrypoints",
            "search_symbols",
            "read_symbol",
            "find_references",
            "build_behavior_subgraph",
        ),
        hard_rules: tuple[str, ...] = (
            "no_snapshot_external_paths",
            "no_unregistered_tools",
            "no_authority_upgrade",
            "no_skipped_validators",
            "no_duplicate_no_gain_calls",
            "obligation_must_exist",
            "budgets_must_be_available",
            "fallback_must_be_safe",
        ),
    ) -> None:
        self._run_id = run_id
        self._repo_snapshot_id = repo_snapshot_id
        self._ready_tools = tuple(ready_tools)
        self._hard_rules = tuple(hard_rules)

    @property
    def ready_tools(self) -> tuple[str, ...]:
        return self._ready_tools

    @property
    def hard_rules(self) -> tuple[str, ...]:
        return self._hard_rules

    def decide(self, context: ResearchDecisionContextV1) -> ResearchDecisionV1:
        """Return a deterministic decision proposal for the given context."""

        action, fallback = self._select_action(context)
        tool_calls = self._build_tool_calls(context, action)
        # If a tool-calling action cannot produce any tool call (e.g.
        # TRACE_CALLS with no candidate symbols), fall back to SEARCH_SYMBOLS
        # first (it always produces a tool call when there's an active
        # obligation with a search query). Only propose RECORD_GAP when the
        # no-progress threshold is met; otherwise STOP_BLOCKED.
        tool_calling_actions = {
            "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "TRACE_DATA_FLOW",
            "INSPECT_BRANCH", "INSPECT_CONFIG", "SEARCH_HINTS",
            "BUILD_BEHAVIOR_SUBGRAPH", "PROPOSE_PACKET", "COMPILE_FACTS",
            "DECOMPOSE_CLAIMS", "REWRITE_SENTENCES",
        }
        if action in tool_calling_actions and not tool_calls:
            if action != "SEARCH_SYMBOLS" and context.active_obligation is not None:
                alt_calls = self._build_tool_calls(context, "SEARCH_SYMBOLS")
                if alt_calls:
                    action = "SEARCH_SYMBOLS"
                    tool_calls = alt_calls
                    fallback = "RECORD_GAP"
            if not tool_calls:
                if context.no_progress_counter >= 3:
                    action = "RECORD_GAP"
                    fallback = "STOP_BLOCKED"
                else:
                    action = "STOP_BLOCKED"
                    fallback = "STOP_BLOCKED"
        obligation_id = context.active_obligation.obligation_id if context.active_obligation else ""
        issue_id = context.active_issue.issue_id if context.active_issue else ""
        goal = self._goal_for(action, context)

        return ResearchDecisionV1(
            decision_id=_decision_id(self._run_id, context.turn_index, action),
            run_id=self._run_id,
            turn_index=context.turn_index,
            action=action,
            obligation_id=obligation_id,
            issue_id=issue_id,
            goal=goal,
            selected_tool_calls=tool_calls,
            candidate_scope=tuple(context.top_candidate_symbol_ids),
            expected_information_gain=self._expected_gain(action, context),
            evidence_needed=tuple(context.missing_information),
            stop_condition=self._stop_condition(context),
            fallback_action=fallback,
            rationale=self._rationale(action, context),
            produced_by="deterministic_fallback",
        )

    # --- action selection ------------------------------------------------

    def _select_action(
        self, context: ResearchDecisionContextV1
    ) -> tuple[ResearchAction, ResearchAction]:
        # No-progress escalation: after two consecutive no-gain turns, switch
        # strategy; after three, propose RECORD_GAP (policy merge still has
        # to validate that the search was exhaustive).
        if context.no_progress_counter >= 3:
            return ("RECORD_GAP", "STOP_BLOCKED")
        if context.no_progress_counter >= 2:
            # Switch strategy: if we were doing symbol_search, try call_trace;
            # otherwise try SEARCH_HINTS as a last resort.
            recent_tools = {obs.tool_name for obs in context.recent_observations}
            if "search_symbols" in recent_tools or "find_entrypoints" in recent_tools:
                return ("TRACE_CALLS", "RECORD_GAP")
            return ("SEARCH_HINTS", "RECORD_GAP")

        if context.active_issue is not None:
            return fallback_action_for_issue(context.active_issue)

        # No active issue: pick based on what the obligation is missing.
        obl = context.active_obligation
        if obl is None:
            # Nothing to do; signal blocked so the graph can route to a stop.
            return ("STOP_BLOCKED", "STOP_BLOCKED")

        if not obl.candidate_symbol_ids:
            return ("SEARCH_SYMBOLS", "RECORD_GAP")
        if obl.missing_information and any(
            "relation" in m or "call" in m for m in obl.missing_information
        ):
            return ("TRACE_CALLS", "RECORD_GAP")
        if obl.missing_information and any(
            "branch" in m or "condition" in m or "config" in m
            for m in obl.missing_information
        ):
            return ("INSPECT_CONFIG", "RECORD_GAP")
        if obl.missing_information and any(
            "data" in m for m in obl.missing_information
        ):
            return ("TRACE_DATA_FLOW", "RECORD_GAP")
        # Candidates exist and no special missing-info shape: read the
        # candidate so the behavior graph can be populated.  This keeps
        # the supervisor from re-running SEARCH_SYMBOLS once it already
        # has a candidate, which would yield no new information gain.
        return ("READ_CANDIDATE", "RECORD_GAP")

    # --- tool call construction -----------------------------------------

    def _build_tool_calls(
        self, context: ResearchDecisionContextV1, action: ResearchAction
    ) -> tuple[ResearchToolCallV1, ...]:
        if action in {"STOP_BLOCKED", "RECORD_GAP", "PLAN_METHOD"}:
            return ()

        obligation_id = (
            context.active_obligation.obligation_id if context.active_obligation else ""
        )
        if not obligation_id:
            # Without an active obligation, no tool call can be policy-merged.
            return ()

        tool_name = _action_default_tool(action)
        if tool_name is None or tool_name not in self._ready_tools:
            return ()

        tool_kind = _tool_kind_for(tool_name)
        turn = context.turn_index
        # Stable id so the same (turn, tool, obligation) yields the same id
        # in tests.  No random component.
        tool_call_id = _stable_tool_call_id(
            self._run_id, turn, tool_name, obligation_id
        )

        arguments: dict[str, Any] = {}
        if tool_name == "search_symbols":
            query = self._search_query(context)
            arguments["query"] = query
            arguments["top_k"] = 10
        elif tool_name == "read_symbol":
            symbol = self._read_symbol_target(context)
            path = self._read_symbol_path(context)
            if symbol is None or path is None:
                return ()
            arguments["path"] = path
            arguments["symbol"] = symbol
            arguments["top_k"] = 1
        elif tool_name == "find_references":
            symbol = self._read_symbol_target(context)
            if symbol is None:
                return ()
            arguments["symbol"] = symbol
        elif tool_name == "find_entrypoints":
            arguments["top_k"] = 20
        elif tool_name == "build_behavior_subgraph":
            symbol = self._read_symbol_target(context)
            if symbol is None:
                return ()
            arguments["symbol"] = symbol
            arguments["depth"] = 1
            arguments["node_budget"] = 32
        elif tool_name == "trace_data_flow":
            symbol = self._read_symbol_target(context)
            if symbol is None:
                return ()
            arguments["symbol"] = symbol
            arguments["direction"] = "both"
        elif tool_name == "inspect_control_flow":
            path = self._read_symbol_path(context)
            symbol = self._read_symbol_target(context)
            if path is None:
                return ()
            arguments["path"] = path
            if symbol is not None:
                arguments["symbol"] = symbol
        elif tool_name == "inspect_configuration":
            arguments["config_key"] = ""
            arguments["top_k"] = 20
        elif tool_name == "search_semantic_hints":
            query = self._search_query(context)
            if not query:
                return ()
            arguments["query"] = query
            arguments["top_k"] = 10
        elif tool_name == "propose_evidence_packet":
            obl = context.active_obligation
            if obl is None:
                return ()
            arguments["obligation_tag"] = obl.obligation_id
            arguments["anchor_span_ids"] = list(obl.candidate_behavior_node_ids)
        elif tool_name == "compile_code_facts":
            obl = context.active_obligation
            if obl is None:
                return ()
            arguments["packet_id"] = f"proposed:{obl.obligation_id}"
        elif tool_name == "decompose_atomic_claims":
            obl = context.active_obligation
            if obl is None:
                return ()
            arguments["fact_ids"] = list(obl.candidate_behavior_node_ids)

        call = ResearchToolCallV1(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=tool_kind,
            obligation_id=obligation_id,
            goal=self._goal_for(action, context),
            repo_snapshot_id=self._repo_snapshot_id,
            path_scope=tuple(context.top_candidate_symbol_ids),
            top_k=int(arguments.get("top_k", 0)),
            depth=int(arguments.get("depth", 0)),
            node_budget=int(arguments.get("node_budget", 0)),
            arguments=arguments,
        )
        return (call,)

    # --- heuristics for argument construction ---------------------------

    def _search_query(self, context: ResearchDecisionContextV1) -> str:
        obl = context.active_obligation
        if obl is None:
            return ""
        # Prefer typed behavior target search terms, then fall back to the
        # obligation id's trailing slug.
        for target in obl.typed_behavior_targets:
            if target.search_terms:
                return target.search_terms[0]
        # Use the last token of the obligation id (typically a slug).
        return obl.obligation_id.rsplit("-", 1)[-1] or obl.obligation_id

    def _read_symbol_target(
        self, context: ResearchDecisionContextV1
    ) -> str | None:
        obl = context.active_obligation
        if obl is None:
            return None
        if obl.candidate_symbol_ids:
            # Use the last path segment of the first candidate (typically
            # ``module.py:Class.method`` -> ``Class.method``).
            first = obl.candidate_symbol_ids[0]
            if ":" in first:
                return first.rsplit(":", 1)[-1]
            return first
        return None

    def _read_symbol_path(self, context: ResearchDecisionContextV1) -> str | None:
        obl = context.active_obligation
        if obl is None:
            return None
        if obl.candidate_symbol_ids:
            first = obl.candidate_symbol_ids[0]
            if ":" in first:
                return first.split(":", 1)[0]
        return None

    # --- rationale / goal / stop condition ------------------------------

    def _goal_for(
        self, action: ResearchAction, context: ResearchDecisionContextV1
    ) -> str:
        obl_label = (
            context.active_obligation.obligation_id
            if context.active_obligation
            else "no-active-obligation"
        )
        if context.active_issue is not None:
            return f"{action} for obligation={obl_label} issue={context.active_issue.issue_kind}"
        return f"{action} for obligation={obl_label}"

    def _expected_gain(
        self, action: ResearchAction, context: ResearchDecisionContextV1
    ) -> str:
        if action == "SEARCH_SYMBOLS":
            return "new_candidate_symbol"
        if action == "READ_CANDIDATE":
            return "new_hard_source_span"
        if action == "TRACE_CALLS":
            return "new_verified_relation"
        if action == "TRACE_DATA_FLOW":
            return "new_data_dependency"
        if action == "INSPECT_BRANCH":
            return "branch_condition_resolved"
        if action == "INSPECT_CONFIG":
            return "config_condition_resolved"
        if action == "SEARCH_HINTS":
            return "search_query_refinement"
        if action == "BUILD_BEHAVIOR_SUBGRAPH":
            return "new_behavior_predicate"
        if action == "RECORD_GAP":
            return "terminal_explicit_gap"
        if action == "STOP_BLOCKED":
            return "terminal_blocked"
        return ""

    def _stop_condition(self, context: ResearchDecisionContextV1) -> str:
        obl = context.active_obligation
        if obl is None:
            return "no_active_obligation"
        if obl.status in {"supported", "explicit_gap", "blocked"}:
            return f"obligation_terminal:{obl.status}"
        if context.no_progress_counter >= 3:
            return "no_progress_three_turns"
        return "obligation_unresolved"

    def _rationale(
        self, action: ResearchAction, context: ResearchDecisionContextV1
    ) -> str:
        if context.no_progress_counter >= 3:
            return "no_progress_threshold_reached"
        if context.no_progress_counter >= 2:
            return "switching_search_strategy_after_two_no_gain_turns"
        if context.active_issue is not None:
            return f"issue_driven:{context.active_issue.issue_kind}"
        return "obligation_missing_information"


# ---------------------------------------------------------------------------
# Action -> default tool mapping
# ---------------------------------------------------------------------------


_ACTION_DEFAULT_TOOL: dict[ResearchAction, str | None] = {
    "SEARCH_SYMBOLS": "search_symbols",
    "READ_CANDIDATE": "read_symbol",
    "TRACE_CALLS": "find_references",
    "TRACE_DATA_FLOW": "trace_data_flow",
    "INSPECT_BRANCH": "inspect_control_flow",
    "INSPECT_CONFIG": "inspect_configuration",
    "SEARCH_HINTS": "search_semantic_hints",
    "BUILD_BEHAVIOR_SUBGRAPH": "build_behavior_subgraph",
    "PROPOSE_PACKET": "propose_evidence_packet",
    "COMPILE_FACTS": "compile_code_facts",
    "DECOMPOSE_CLAIMS": "decompose_atomic_claims",
    "REWRITE_SENTENCES": None,  # R6 tool
    "RECORD_GAP": None,
    "PLAN_METHOD": None,
    "STOP_BLOCKED": None,
}


def _action_default_tool(action: ResearchAction) -> str | None:
    return _ACTION_DEFAULT_TOOL.get(action)


_TOOL_KIND_MAP: dict[str, ToolKind] = {
    "find_entrypoints": "symbol_search",
    "search_symbols": "symbol_search",
    "read_symbol": "code_read",
    "find_references": "call_trace",
    "list_repository_tree": "symbol_search",
    "search_code": "symbol_search",
    "read_code_span": "code_read",
    "inspect_configuration": "configuration",
    "build_behavior_subgraph": "behavior_graph",
    "query_behavior_graph": "behavior_graph",
    "trace_call_path": "call_trace",
    "trace_data_flow": "data_flow_trace",
    "inspect_control_flow": "branch_inspection",
    "compare_implementation_branches": "branch_inspection",
    "find_output_side_effects": "call_trace",
    "search_semantic_hints": "hint_search",
    "derive_code_queries_from_hint": "hint_search",
    "compare_hint_to_code": "hint_search",
    "propose_evidence_packet": "packet_repair",
    "validate_evidence_packet": "packet_repair",
    "compile_code_facts": "packet_repair",
    "validate_code_facts": "packet_repair",
    "decompose_atomic_claims": "packet_repair",
    "authorize_atomic_claims": "packet_repair",
    "record_explicit_code_gap": "other",
    "check_obligation_coverage": "other",
}


def _tool_kind_for(tool_name: str) -> ToolKind:
    return _TOOL_KIND_MAP.get(tool_name, "other")


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------


def build_decision_context(
    *,
    run_id: str,
    repo_snapshot_id: str,
    turn_index: int,
    agenda: ResearchAgendaV1 | None,
    active_obligation_id: str,
    active_issue: ResearchIssueV1 | None,
    recent_observations: tuple[ResearchObservationV1, ...],
    per_obligation_budgets: dict[str, PerObligationBudgetV1],
    global_safety_budget: GlobalSafetyBudgetV1 | None,
    no_progress_counter: int = 0,
    no_progress_history: tuple[str, ...] = (),
    ready_tools: tuple[str, ...] = (),
    hard_rules: tuple[str, ...] = (),
    current_supported_claim_ids: tuple[str, ...] = (),
    unresolved_must_cover_ids: tuple[str, ...] | None = None,
) -> ResearchDecisionContextV1:
    """Assemble a ``ResearchDecisionContextV1`` from graph state.

    The builder is pure: it never reads files or calls the LLM.  It picks
    the active obligation from the agenda (if any), projects the recent
    observations into compact summaries, and computes the remaining
    per-obligation budget for the active obligation.
    """

    active_obligation: ResearchAgendaItemV1 | None = None
    typed_targets: tuple[TypedBehaviorTargetV1, ...] = ()
    missing_info: tuple[str, ...] = ()
    top_symbols: tuple[str, ...] = ()
    top_nodes: tuple[str, ...] = ()
    if agenda is not None and active_obligation_id:
        for item in agenda.items:
            if item.obligation_id == active_obligation_id:
                active_obligation = item
                typed_targets = tuple(item.typed_behavior_targets)
                missing_info = tuple(item.missing_information)
                top_symbols = tuple(item.candidate_symbol_ids)
                top_nodes = tuple(item.candidate_behavior_node_ids)
                break

    recent_summaries = tuple(
        RecentObservationSummaryV1(
            observation_id=obs.observation_id,
            tool_call_id=obs.tool_call_id,
            tool_name=obs.tool_name,
            status=obs.status,
            source_authority=obs.source_authority,
            result_refs=obs.result_refs,
            exact_span_ids=obs.exact_span_ids,
            truncated=obs.diagnostics.truncated,
            ambiguous=obs.diagnostics.ambiguous,
            candidate_count=obs.diagnostics.candidate_count,
            obligation_id=obs.obligation_id,
        )
        for obs in recent_observations
    )

    remaining_per_kind: dict[str, int] = {}
    if active_obligation_id and active_obligation_id in per_obligation_budgets:
        budget = per_obligation_budgets[active_obligation_id]
        for kind in BUDGET_TOOL_KINDS:
            remaining_per_kind[kind] = budget.remaining(kind)

    unresolved_ids = unresolved_must_cover_ids
    if unresolved_ids is None and agenda is not None:
        unresolved_ids = tuple(agenda.unresolved_must_cover_ids)

    # Always allow the terminal actions; tool-calling actions are allowed
    # only when there is an active obligation.
    allowed: list[ResearchAction] = ["STOP_BLOCKED"]
    if active_obligation is not None:
        allowed.extend(
            [
                "SEARCH_SYMBOLS",
                "READ_CANDIDATE",
                "TRACE_CALLS",
                "TRACE_DATA_FLOW",
                "INSPECT_BRANCH",
                "INSPECT_CONFIG",
                "SEARCH_HINTS",
                "BUILD_BEHAVIOR_SUBGRAPH",
                "RECORD_GAP",
            ]
        )

    return ResearchDecisionContextV1(
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        turn_index=turn_index,
        active_obligation=active_obligation,
        active_issue=active_issue,
        typed_behavior_targets=typed_targets,
        current_supported_claim_ids=tuple(current_supported_claim_ids),
        missing_information=missing_info,
        top_candidate_symbol_ids=top_symbols,
        top_candidate_behavior_node_ids=top_nodes,
        recent_observations=recent_summaries,
        no_progress_counter=no_progress_counter,
        no_progress_history=no_progress_history,
        remaining_budgets=remaining_per_kind,
        per_obligation_remaining=remaining_per_kind,
        allowed_actions=tuple(allowed),
        ready_tools=tuple(ready_tools),
        hard_rules=tuple(hard_rules),
        unresolved_must_cover_ids=tuple(unresolved_ids or ()),
    )


# ---------------------------------------------------------------------------
# LangGraph node function
# ---------------------------------------------------------------------------


def supervisor_node(
    state: AgentStateV3,
    *,
    backend: SupervisorBackend,
    agenda: ResearchAgendaV1 | None,
    active_issue: ResearchIssueV1 | None,
    recent_observations: tuple[ResearchObservationV1, ...] = (),
    per_obligation_budgets: dict[str, PerObligationBudgetV1] | None = None,
    global_safety_budget: GlobalSafetyBudgetV1 | None = None,
    no_progress_counter: int = 0,
    no_progress_history: tuple[str, ...] = (),
    turn_index: int = 0,
    ready_tools: tuple[str, ...] = (),
    hard_rules: tuple[str, ...] = (),
    current_supported_claim_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """LangGraph node: build context, ask backend, return decision + tool calls.

    The node returns a partial state update containing:

    - ``pending_tool_calls``: the proposed tool calls (policy merge runs in
      a separate node so its rejections are visible in the trace);
    - ``decision_trace_refs``: a compact decision summary reference;
    - ``active_obligation_id`` / ``active_issue_id``: echoed for traceability;
    - ``status``: ``researching`` (the policy node may downgrade to
      ``blocked`` if the fallback is also rejected).
    """

    context = build_decision_context(
        run_id=state.get("run_id", ""),
        repo_snapshot_id=state.get("repo_snapshot_id", ""),
        turn_index=turn_index,
        agenda=agenda,
        active_obligation_id=state.get("active_obligation_id", ""),
        active_issue=active_issue,
        recent_observations=recent_observations,
        per_obligation_budgets=per_obligation_budgets or {},
        global_safety_budget=global_safety_budget,
        no_progress_counter=no_progress_counter,
        no_progress_history=no_progress_history,
        ready_tools=ready_tools,
        hard_rules=hard_rules,
        current_supported_claim_ids=current_supported_claim_ids,
    )
    decision = backend.decide(context)
    decision_ref = _decision_ref(decision)
    return {
        "pending_tool_calls": list(decision.selected_tool_calls),
        "decision_trace_refs": [decision_ref],
        "active_obligation_id": decision.obligation_id or state.get("active_obligation_id", ""),
        "active_issue_id": decision.issue_id or state.get("active_issue_id", ""),
        "status": "blocked" if decision.action == "STOP_BLOCKED" else "researching",
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _decision_id(run_id: str, turn_index: int, action: ResearchAction) -> str:
    material = f"{run_id}|{turn_index}|{action}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"decision-{digest}"


def _decision_ref(decision: ResearchDecisionV1) -> str:
    """Compact reference string for the decision trace.

    The trace stores compact references, not full decisions, so the state
    channel stays small.  The full decision is reconstructed from the
    policy merge node's trace when needed for debugging.
    """

    payload = {
        "decision_id": decision.decision_id,
        "turn_index": decision.turn_index,
        "action": decision.action,
        "obligation_id": decision.obligation_id,
        "issue_id": decision.issue_id,
        "tool_calls": [tc.tool_call_id for tc in decision.selected_tool_calls],
        "produced_by": decision.produced_by,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    return f"decision-ref:{digest}:{decision.decision_id}"


def _stable_tool_call_id(
    run_id: str, turn_index: int, tool_name: str, obligation_id: str
) -> str:
    material = f"{run_id}|{turn_index}|{tool_name}|{obligation_id}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"tc-{digest}"


__all__ = [
    "DeterministicSupervisorBackend",
    "RecentObservationSummaryV1",
    "ResearchDecisionContextV1",
    "SupervisorBackend",
    "all_fallback_issue_kinds",
    "build_decision_context",
    "fallback_action_for_issue",
    "supervisor_node",
]
