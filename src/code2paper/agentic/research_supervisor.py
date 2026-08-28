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
import re
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
from code2paper.agentic.typed_refs import (
    is_symbol_ref,
    split_symbol_ref,
)
from code2paper.agentic.behavior_graph import make_symbol_id
from code2paper.agentic.research_read_identity import (
    content_read_covers_line,
    span_covers_line,
)


_PREDICATE_SEARCH_QUERIES: dict[str, str] = {
    "AGGREGATE": "aggregate pool combine",
    "ATTEND": "attention query key value",
    "BRANCH": "condition branch fallback",
    "CALL": "call invoke forward",
    "COMPUTE": "compute loss score formula",
    "CONCAT": "cat concat concatenate",
    "CONSTRUCT": "build construct initialize",
    "FILTER": "filter prune retain selective scan",
    "LOAD": "load checkpoint weights",
    "LOOP": "loop iterate epoch",
    "MASK": "mask threshold",
    "NORMALIZE": "normalize norm",
    "PROJECT": "project linear head",
    "PROPAGATE": "propagate message passing",
    "READ": "read input data",
    "REDUCE": "reduce mean sum loss",
    "RESHAPE": "reshape view flatten",
    "RETURN": "return forward output",
    "SAMPLE": "sample sampling",
    "SELECT": "select choose index",
    "SERIALIZE": "serialize save artifact",
    "SORT": "sort rank order",
    "STACK": "stack sequence",
    "TOPK": "topk top k",
    "TRANSFORM": "transform encode convert",
    "WRITE": "write save store",
}


_AUTHOR_SEARCH_STOP_WORDS = frozenset({
    "about", "after", "also", "and", "are", "before", "between", "each",
    "for", "from", "into", "method", "module", "other", "that", "the",
    "their", "then", "these", "this", "through", "using", "with",
})

_SEMANTIC_SEARCH_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "score": ("score", "predict", "prediction", "predictor"),
    "scores": ("scores", "score", "predict", "prediction", "predictor"),
    "dimension": ("dimension", "dim", "input_dim", "feature_size", "shape"),
    "infonce": ("infonce", "contrastive", "logsumexp"),
    "contrastive": ("contrastive", "infonce", "logsumexp"),
    # Public lifecycle endpoints are frequently named ``qa`` while the
    # executable invocation is ``infer`` and the author describes the stage
    # as generation.  These are retrieval aliases only; positive claims still
    # require exact source spans and typed semantic replay.
    "generation": ("generation", "generate", "infer", "answer", "qa"),
    "generate": ("generation", "generate", "infer", "answer", "qa"),
    "answer": ("answer", "infer", "qa"),
    "filtering": ("filter", "prune", "threshold", "selective", "scan"),
    "filter": ("filter", "prune", "threshold", "selective", "scan"),
}


def _expand_semantic_search_terms(values: tuple[str, ...]) -> tuple[str, ...]:
    expanded: list[str] = []
    for value in values:
        pieces = [value, *re.findall(r"[A-Za-z0-9_]+", value)]
        for piece in pieces:
            aliases = _SEMANTIC_SEARCH_EXPANSIONS.get(piece.casefold(), (piece,))
            if piece.isdigit():
                aliases = (*aliases, f"f{piece}")
            for alias in aliases:
                if alias and alias not in expanded:
                    expanded.append(alias)
    return tuple(expanded)


def _identifier_author_search_terms(text: str) -> tuple[str, ...]:
    """Return concrete identifier-shaped names supplied by the author."""

    terms: list[str] = []
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", text)
    code_like = [
        token
        for token in raw_tokens
        if (
            "_" in token
            # All-lowercase hyphenated phrases are ordinary prose
            # (``retrieval-augmented``, ``large-scale``), not implementation
            # identifiers.  Retain hyphenated names only when their casing
            # carries an identifier signal such as ``Acme-StateEncoder``.
            or ("-" in token and any(char.isupper() for char in token[1:]))
            or re.search(r"[a-z0-9][A-Z]", token)
            or (len(token) >= 3 and token.isupper())
        )
    ]
    for token in code_like:
        normalized = token.casefold().strip("-_")
        if len(normalized) < 3 or normalized in _AUTHOR_SEARCH_STOP_WORDS:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return tuple(terms)


def _explicit_author_symbol(text: str) -> str:
    """Return the symbol from an explicit ``path::Symbol`` marker."""

    match = re.search(
        r"(?:^|\s|:)(?:[^\s:]+\.(?:py|js|ts|java|go|rs))::([A-Za-z_][\w.]*)",
        text,
    )
    return match.group(1).rsplit(".", 1)[-1] if match else ""


def _salient_author_search_terms(text: str) -> tuple[str, ...]:
    """Keep implementation names before generic prose retrieval terms.

    Method descriptions often introduce the concrete implementation family
    after a sentence of domain prose (for example ``... pass it through
    FooEncoder ...``).  Taking only the first twelve ordinary words makes a
    multi-model repository rank a baseline with a generic method name ahead
    of the author-named implementation.  Identifier-shaped tokens are search
    hints, not factual authority, so prefer them without hard-coding any
    project vocabulary.
    """

    terms = list(_identifier_author_search_terms(text))

    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text.replace("_", " "))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9-]+", expanded):
        normalized = token.casefold().strip("-")
        if len(normalized) < 4 or normalized in _AUTHOR_SEARCH_STOP_WORDS:
            continue
        if normalized not in terms:
            terms.append(normalized)
        if len(terms) >= 12:
            break
    return tuple(terms)


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
    query: str = ""
    semantic_summary: str = ""
    code_excerpt: str = ""
    discovered_symbols: tuple[str, ...] = Field(default_factory=tuple)
    discovered_relations: tuple[str, ...] = Field(default_factory=tuple)
    enclosing_symbol_refs: tuple[str, ...] = Field(default_factory=tuple)


class BehaviorTemplateSearchHintV1(BaseModel):
    """Non-authorizing structural hint for supervisor tool selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    matched: bool = False
    match_score: float = 0.0
    missing_predicates: tuple[str, ...] = Field(default_factory=tuple)
    missing_relation_kinds: tuple[str, ...] = Field(default_factory=tuple)
    resolved_role_symbols: dict[str, str] = Field(default_factory=dict)
    predicate_order_hint: tuple[str, ...] = Field(default_factory=tuple)


class ExecutedToolCallSummaryV1(BaseModel):
    """A prior repository action shown back to the Research Manager.

    Tool-call IDs are deliberately omitted.  The model needs the semantic
    action and exact arguments in order to choose a different query or
    symbol; stable IDs remain harness-owned policy state.

    The summaries are assembled across obligations (``obligation_id`` is
    carried so the model can distinguish a fresh search for a new story
    question from an exact re-read of code it already inspected).  The
    policy layer additionally rejects exact re-runs of content-reading
    calls even when the obligation differs, because the source span
    returned by ``read_symbol`` / ``read_code_span`` is identical within
    one repo snapshot.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    path_scope: tuple[str, ...] = Field(default_factory=tuple)
    goal: str = ""
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
    current_supported_claim_statements: tuple[str, ...] = Field(default_factory=tuple)
    missing_information: tuple[str, ...] = Field(default_factory=tuple)
    top_candidate_symbol_ids: tuple[str, ...] = Field(default_factory=tuple)
    top_candidate_behavior_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    # Behavior nodes that bind to the exact candidate symbol/source span
    # (symbol_id match or covering source span).  A non-empty but unrelated
    # node list must not authorize COMPILE_EVIDENCE from a reused read.
    candidate_bound_behavior_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    recent_observations: tuple[RecentObservationSummaryV1, ...] = Field(default_factory=tuple)
    executed_tool_calls: tuple[ExecutedToolCallSummaryV1, ...] = Field(default_factory=tuple)
    policy_feedback: tuple[str, ...] = Field(default_factory=tuple)
    no_progress_tool_call_ids: tuple[str, ...] = Field(default_factory=tuple)
    no_progress_counter: int = 0
    no_progress_history: tuple[str, ...] = Field(default_factory=tuple)
    remaining_budgets: dict[str, int] = Field(default_factory=dict)
    per_obligation_remaining: dict[str, int] = Field(default_factory=dict)
    allowed_actions: tuple[ResearchAction, ...] = Field(default_factory=tuple)
    ready_tools: tuple[str, ...] = Field(default_factory=tuple)
    hard_rules: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_must_cover_ids: tuple[str, ...] = Field(default_factory=tuple)
    behavior_template_search_hints: tuple[BehaviorTemplateSearchHintV1, ...] = Field(default_factory=tuple)

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
        elif (
            action in tool_calling_actions
            and self._proposed_call_already_executed(context, action)
        ):
            # The exact deterministic call (same tool, obligation, arguments
            # and path scope) was already executed in this run; policy
            # rejects the repeat as a duplicate no-gain call and the
            # fallback repeats the same doomed call.  Switch strategy so the
            # loop can either find genuinely new evidence or escalate the
            # no-progress counter to a typed gap -- never burn turns into
            # fallback exhaustion.
            action, fallback = self._strategy_switch(context)
            tool_calls = self._build_tool_calls(context, action)
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

        if (
            context.active_issue is not None
            and context.active_issue.issue_kind == "truncated_observation"
            and context.recent_observations
            and context.recent_observations[-1].tool_name == "search_symbols"
            and any(
                is_symbol_ref(ref)
                for ref in context.recent_observations[-1].result_refs
            )
        ):
            # Truncation means there are more ranked candidates, not that the
            # top candidate is unusable.  Read it before broadening/repeating
            # the same search; the exact read remains the authority boundary.
            return ("READ_CANDIDATE", "RECORD_GAP")
        if context.active_issue is not None:
            return fallback_action_for_issue(context.active_issue)

        # No active issue: pick based on what the obligation is missing.
        obl = context.active_obligation
        if obl is None:
            # Nothing to do; signal blocked so the graph can route to a stop.
            return ("STOP_BLOCKED", "STOP_BLOCKED")

        if not obl.candidate_symbol_ids:
            return ("SEARCH_SYMBOLS", "RECORD_GAP")
        semantic_missing = [
            value.casefold()
            for value in obl.missing_information
            if not value.startswith("candidate_path:")
        ]
        searched_candidate_ready = self._latest_search_symbol_ref(context) is not None
        has_exact_source_span = (
            self._has_exact_source_span(context)
            # A pre-populated graph is sufficient for the legacy compile-node
            # unit path only when this obligation has no unresolved semantic
            # repair.  If semantic information is still missing, nodes from a
            # prior obligation on the same file must not suppress a fresh
            # search/read witness for that obligation.
            or (bool(context.top_candidate_behavior_node_ids) and not semantic_missing)
        )
        if semantic_missing and any(
            value.startswith("typed_predicate:") for value in semantic_missing
        ):
            # A failed compile adds the precise missing predicate.  Search
            # for that predicate, then read the top result on the next turn.
            # Previously the mere presence of an old candidate forced
            # READ_CANDIDATE forever, so the loop reread one symbol until it
            # recorded an explicit gap even when other symbols implemented
            # the missing operation.
            if searched_candidate_ready or self._predicate_candidate_ref(context) is not None:
                # The top result may already have been read for another
                # obligation in this snapshot (same exact identity rule as
                # the authority-boundary gate below).  Compile from the
                # existing candidate-bound graph nodes instead of proposing
                # a read that policy must reject as a duplicate.  The loop
                # treats ``partial`` as terminal when the round-robin
                # returns the same obligation, so recompiling cannot churn
                # past the run's terminal boundary.
                if self._candidate_read_already_executed(context):
                    if (
                        context.candidate_bound_behavior_node_ids
                        and not context.current_supported_claim_ids
                    ):
                        return ("COMPILE_EVIDENCE", "RECORD_GAP")
                    return self._strategy_switch(context)
                return ("READ_CANDIDATE", "RECORD_GAP")
            return ("SEARCH_SYMBOLS", "RECORD_GAP")
        if semantic_missing and any(
            value.startswith("typed_semantic:") for value in semantic_missing
        ):
            semantic_requirement = next(
                value.split(":", 2)[-1]
                for value in semantic_missing
                if value.startswith("typed_semantic:")
            )
            expected_query = " ".join(
                _expand_semantic_search_terms((semantic_requirement,))
            ).casefold()
            latest_query = self._latest_search_query(context).casefold()
            if searched_candidate_ready and (
                not latest_query or latest_query == expected_query
            ):
                if self._candidate_read_already_executed(context):
                    if (
                        context.candidate_bound_behavior_node_ids
                        and not context.current_supported_claim_ids
                    ):
                        return ("COMPILE_EVIDENCE", "RECORD_GAP")
                    return self._strategy_switch(context)
                return ("READ_CANDIDATE", "RECORD_GAP")
            return ("SEARCH_SYMBOLS", "RECORD_GAP")
        # Author text and candidate-path hints often contain words such as
        # ``config`` or ``training``.  They are discovery constraints, not a
        # reason to inspect configuration before the executable owner has
        # been found and read.  The old ordering sent path-seeded obligations
        # into repeated INSPECT_CONFIG/TRACE_CALLS turns and never populated a
        # behavior graph, so the critic could only synthesize a gap.  Force
        # the first two steps of the authority boundary here: search, then
        # read an exact symbol span; only after that may config/relation
        # diagnostics take priority.  Typed predicate/semantic repairs stay
        # above this gate because their search cursor and candidate selection
        # are intentionally more specific.
        if not has_exact_source_span:
            if searched_candidate_ready:
                # The exact read this obligation needs may already have been
                # executed for another obligation in the same snapshot.
                # Policy rejects a re-read of identical bytes, so proposing
                # READ_CANDIDATE here would be rejected and the loop would
                # burn turns until a fallback-exhaustion STOP_BLOCKED.  When
                # the behavior graph already carries nodes that bind to this
                # obligation's exact candidate symbol/span, the evidence is
                # already in the run: compile from the existing graph
                # instead of re-reading.  A non-empty but unrelated node
                # projection (same file, different symbol) must NOT authorize
                # compilation from a reused read.
                if self._candidate_read_already_executed(context):
                    if context.candidate_bound_behavior_node_ids:
                        return ("COMPILE_EVIDENCE", "RECORD_GAP")
                    # No candidate-bound graph nodes yet: switch strategy
                    # (same escalation as the no-progress rule) rather than
                    # repeat a doomed read; the next search may find
                    # cooperating code or a different span.
                    recent_tools = {
                        obs.tool_name for obs in context.recent_observations
                    }
                    if "search_symbols" in recent_tools or "find_entrypoints" in recent_tools:
                        return ("TRACE_CALLS", "RECORD_GAP")
                    return ("SEARCH_HINTS", "RECORD_GAP")
                return ("READ_CANDIDATE", "RECORD_GAP")
            return ("SEARCH_SYMBOLS", "RECORD_GAP")
        if semantic_missing and any(
            value.startswith("typed_relation:data_")
            or value.startswith("typed_relation:reads_")
            or value.startswith("typed_relation:writes_")
            for value in semantic_missing
        ):
            return ("TRACE_DATA_FLOW", "RECORD_GAP")
        if semantic_missing and any(
            value.startswith("typed_relation:configured_by")
            or value.startswith("typed_relation:control_")
            or value.startswith("typed_relation:true_branch")
            or value.startswith("typed_relation:false_branch")
            for value in semantic_missing
        ):
            return ("INSPECT_CONFIG", "RECORD_GAP")
        if semantic_missing and any(
            "relation" in value or "call" in value for value in semantic_missing
        ):
            return ("TRACE_CALLS", "RECORD_GAP")
        if semantic_missing and any(
            "branch" in value or "condition" in value or "config" in value
            for value in semantic_missing
        ):
            return ("INSPECT_CONFIG", "RECORD_GAP")
        if semantic_missing and any(
            "data" in value for value in semantic_missing
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
        if action in {"STOP_BLOCKED", "RECORD_GAP", "COMPILE_EVIDENCE", "PLAN_METHOD"}:
            return ()

        obligation_id = (
            context.active_obligation.obligation_id if context.active_obligation else ""
        )
        if not obligation_id:
            # Without an active obligation, no tool call can be policy-merged.
            return ()

        tool_name = _action_default_tool(action)
        if (
            action == "SEARCH_SYMBOLS"
            and context.no_progress_counter > 0
            and "search_code" in self._ready_tools
            and any(
                observation.tool_name == "search_symbols"
                and observation.status in {"success_empty", "scope_exhausted"}
                for observation in context.recent_observations
            )
        ):
            # Broaden an empty structural lookup to literal source search.
            # Repeating the same stable symbol-search call is neither useful
            # research nor a valid policy fallback.
            tool_name = "search_code"
        if tool_name is None or tool_name not in self._ready_tools:
            return ()

        tool_kind = _tool_kind_for(tool_name)
        turn = context.turn_index
        arguments: dict[str, Any] = {}
        if tool_name == "search_symbols":
            query = self._search_query(context)
            arguments["query"] = query
            arguments["top_k"] = 10
        elif tool_name == "search_code":
            query = self._search_query(context)
            if not query:
                return ()
            arguments["query"] = query
            arguments["top_k"] = 20
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

        path_scope = self._candidate_path_scope(context)
        if tool_name == "search_symbols" and any(
            value.startswith(("typed_predicate:", "typed_semantic:"))
            for value in context.missing_information
        ) and not any(
            value.startswith("candidate_path:")
            or (
                value in context.top_candidate_symbol_ids
                and not is_symbol_ref(value)
                and ":" not in value
            )
            for value in (*context.missing_information, *context.top_candidate_symbol_ids)
        ):
            # Candidate paths describe where the first retrieval landed, not
            # a repository boundary unless they were supplied by the author
            # intent as an explicit candidate-path allow-list.  A typed miss
            # may broaden beyond merely discovered paths to find a cooperating
            # module, but it must not escape an author-provided implementation
            # scope and silently select a sibling/baseline model.
            path_scope = ()
        tool_call_id = _stable_tool_call_id(
            self._run_id,
            tool_name,
            obligation_id,
            arguments=arguments,
            path_scope=path_scope,
        )
        call = ResearchToolCallV1(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=tool_kind,
            obligation_id=obligation_id,
            goal=self._goal_for(action, context),
            repo_snapshot_id=self._repo_snapshot_id,
            path_scope=path_scope,
            top_k=int(arguments.get("top_k", 0)),
            depth=int(arguments.get("depth", 0)),
            node_budget=int(arguments.get("node_budget", 0)),
            arguments=arguments,
        )
        return (call,)

    @staticmethod
    def _candidate_path_scope(context: ResearchDecisionContextV1) -> tuple[str, ...]:
        """Project mixed candidate references onto valid repository paths.

        ``candidate_symbol_ids`` contains both seed paths and typed symbol
        references.  Passing those values through verbatim makes tools reject
        ``symbol:<path>:<name>:<line>`` as a snapshot-external path.
        """

        paths: list[str] = []
        for candidate in context.top_candidate_symbol_ids:
            path = ""
            parsed = split_symbol_ref(candidate) if is_symbol_ref(candidate) else None
            if parsed is not None:
                path = parsed[0]
            elif candidate.startswith("candidate_path:"):
                path = candidate.split(":", 1)[1]
            elif ":" not in candidate:
                path = candidate
            if path and path not in paths:
                paths.append(path)
        return tuple(paths)

    # --- heuristics for argument construction ---------------------------

    def _search_query(self, context: ResearchDecisionContextV1) -> str:
        obl = context.active_obligation
        if obl is None:
            return ""
        # A failed typed alignment is a precise request for a missing
        # executable predicate.  It must override the original entrypoint
        # seed, otherwise the supervisor repeatedly rediscovers ``main``.
        for requirement in obl.missing_information:
            if not requirement.startswith("typed_predicate:"):
                continue
            predicate = requirement.split(":", 1)[1].upper()
            query = _PREDICATE_SEARCH_QUERIES.get(predicate)
            if query:
                return query
        for requirement in obl.missing_information:
            if requirement.startswith("typed_semantic:"):
                _prefix, _field, terms = requirement.split(":", 2)
                if terms.strip():
                    expanded = _expand_semantic_search_terms((terms.strip(),))
                    return " ".join(expanded)
        # Entry-point obligations need the executable symbol (normally
        # ``main``), not a broad domain term such as ``train`` that also
        # matches unrelated configuration keys like ``trainer``.
        entrypoint_text = " ".join(
            [obl.author_text, *(target.role for target in obl.typed_behavior_targets)]
        ).casefold()
        if "entrypoint" in entrypoint_text or "::main" in entrypoint_text:
            return "main"
        # Quantitative outputs and named equations are often the strongest
        # bridge from an author description to an implementation identifier
        # (for example ``15-dimensional`` -> ``input_f15``).  Preserve these
        # before generic role/search terms so the initial retrieval does not
        # collapse to broad words such as "feature" or "model".
        exact_output_terms: list[str] = []
        for target in obl.typed_behavior_targets:
            for output in target.outputs:
                exact_output_terms.extend(
                    _expand_semantic_search_terms((output,))
                )
        if exact_output_terms:
            implementation_terms = _identifier_author_search_terms(obl.author_text)
            retrieval_terms = [
                term
                for term in dict.fromkeys(
                    [*implementation_terms, *exact_output_terms]
                )
                if term
            ]
            if retrieval_terms:
                return " ".join(retrieval_terms[:12])
        # Prefer typed behavior target search terms, then fall back to the
        # obligation id's trailing slug.
        for target in obl.typed_behavior_targets:
            implementation_terms = _identifier_author_search_terms(obl.author_text)
            # A semantic anchor is deliberately strict: it is the compiler's
            # executable discriminator (for example ``indexing``, PageRank,
            # or a named state-space family).  Adding broad project prose or
            # a generic role such as ``graph_builder`` can rank a graph helper
            # ahead of the actual lifecycle endpoint and exhaust the read
            # budget.  Concrete author-supplied identifiers remain valid
            # prefixes because they are even more specific than the anchor.
            if target.transformations:
                retrieval_terms = [term for term in dict.fromkeys([
                    *implementation_terms,
                    *_expand_semantic_search_terms(target.transformations),
                ]) if term]
            else:
                retrieval_terms = [term for term in dict.fromkeys([
                    *implementation_terms,
                    *target.search_terms,
                    *target.aliases,
                    *target.role.split("+"),
                    *_salient_author_search_terms(obl.author_text),
                ]) if term]
            if retrieval_terms:
                # Combining a few intent-derived terms lets an author-facing
                # name such as "MLP" retrieve an implementation-facing class
                # named ``PrunePredictor`` without a project dictionary.
                return " ".join(retrieval_terms[:12])
        # Author markers commonly carry an explicit ``path::symbol`` binding
        # even when no typed behavior target was inferred.  It is strictly
        # better than an obligation id whose final component is a content
        # hash and can never match a repository symbol.
        explicit_symbol = re.search(
            r"(?:^|\s|:)(?:[^\s:]+\.(?:py|js|ts|java|go|rs))::([A-Za-z_][\w.]*)",
            obl.author_text,
        )
        if explicit_symbol:
            return explicit_symbol.group(1).rsplit(".", 1)[-1]
        # Preserve the semantic retrieval request for the deterministic
        # token-ranked symbol search. Candidate-path markers are scope hints,
        # not queries, so exclude them here.
        semantic_query = next(
            (
                value.strip()
                for value in obl.missing_information
                if value.strip() and not value.startswith("candidate_path:")
            ),
            "",
        )
        return semantic_query or obl.author_text.strip() or obl.obligation_id

    def _read_symbol_target(
        self, context: ResearchDecisionContextV1
    ) -> str | None:
        obl = context.active_obligation
        if obl is None:
            return None
        latest_search_ref = self._latest_search_symbol_ref(context)
        if latest_search_ref is not None:
            parsed = split_symbol_ref(latest_search_ref)
            if parsed is not None:
                return parsed[1]
        if _explicit_author_symbol(obl.author_text) and self._has_active_symbol_search(context):
            # The author named an implementation owner and the latest search
            # did not return that exact symbol. Do not substitute a fuzzy
            # neighbor (for example MemoryBank for missing MemoryModel).
            return None
        predicate_candidate = self._predicate_candidate_ref(context)
        if predicate_candidate is not None:
            parsed = split_symbol_ref(predicate_candidate)
            if parsed is not None:
                return parsed[1]
        if obl.candidate_symbol_ids:
            first = next(
                (value for value in reversed(obl.candidate_symbol_ids) if is_symbol_ref(value)),
                obl.candidate_symbol_ids[0],
            )
            # Phase 3: candidate_symbol_ids may carry typed refs of the
            # form ``symbol:<path>:<name>:<line>`` (produced by
            # observation_ingest_node).  Parse them via typed_refs so
            # the supervisor reads the *name*, not the line number.
            if is_symbol_ref(first):
                parsed = split_symbol_ref(first)
                if parsed is not None:
                    return parsed[1]
            # Legacy fallback: ``<path>:<symbol>`` or bare ``<symbol>``.
            if ":" in first:
                return first.rsplit(":", 1)[-1]
            return first
        return None

    def _read_symbol_path(self, context: ResearchDecisionContextV1) -> str | None:
        obl = context.active_obligation
        if obl is None:
            return None
        latest_search_ref = self._latest_search_symbol_ref(context)
        if latest_search_ref is not None:
            parsed = split_symbol_ref(latest_search_ref)
            if parsed is not None:
                return parsed[0]
        if _explicit_author_symbol(obl.author_text) and self._has_active_symbol_search(context):
            return None
        predicate_candidate = self._predicate_candidate_ref(context)
        if predicate_candidate is not None:
            parsed = split_symbol_ref(predicate_candidate)
            if parsed is not None:
                return parsed[0]
        if obl.candidate_symbol_ids:
            first = next(
                (value for value in reversed(obl.candidate_symbol_ids) if is_symbol_ref(value)),
                obl.candidate_symbol_ids[0],
            )
            # Phase 3: parse typed refs to extract the path component.
            if is_symbol_ref(first):
                parsed = split_symbol_ref(first)
                if parsed is not None:
                    return parsed[0]
            # Legacy fallback: ``<path>:<symbol>`` -> ``<path>``.
            if ":" in first:
                return first.split(":", 1)[0]
        return None

    def _candidate_symbol_line(
        self, context: ResearchDecisionContextV1
    ) -> int | None:
        """Return the candidate's source line, when recoverable.

        The line comes from the same typed symbol reference the read would
        target: the latest search result first, then the obligation's typed
        candidate refs.  A bare path or unparsable ref yields ``None``, in
        which case a prior ``read_code_span`` on the same file must NOT be
        treated as covering the candidate.
        """

        latest = self._latest_search_symbol_ref(context)
        ref: str | None = latest
        if ref is None:
            obl = context.active_obligation
            if obl is not None:
                ref = next(
                    (
                        value
                        for value in reversed(obl.candidate_symbol_ids)
                        if is_symbol_ref(value)
                    ),
                    None,
                )
        if ref is None:
            return None
        parsed = split_symbol_ref(ref)
        if parsed is None:
            return None
        return parsed[2]

    def _candidate_read_already_executed(
        self, context: ResearchDecisionContextV1
    ) -> bool:
        """Return whether the exact read for the top candidate already ran.

        The executed-call summaries are assembled across obligations: a
        ``read_symbol`` / ``read_code_span`` executed while answering another
        obligation returned the same snapshot-bound source bytes, so policy
        correctly rejects a re-read.  The deterministic supervisor must not
        keep proposing a doomed READ_CANDIDATE; callers switch to
        COMPILE_EVIDENCE (when the behavior graph carries the candidate) or
        to a different search strategy.

        Identity is exact and fail-closed:

        - ``read_symbol`` counts only for the same repository-relative path
          AND the same symbol name (a same-named symbol in another path or a
          different symbol in the same file is a different read);
        - ``read_code_span`` counts only for the same path AND an interval
          that covers the candidate's source line.  A different or merely
          adjacent interval in the same file does not count; without a
          recoverable candidate line, a span read never counts.
        """

        target = self._read_symbol_target(context)
        path = self._read_symbol_path(context)
        if target is None or path is None:
            return False
        candidate_line = self._candidate_symbol_line(context)
        for summary in context.executed_tool_calls:
            if summary.tool_name not in {"read_symbol", "read_code_span"}:
                continue
            arguments = summary.arguments or {}
            if content_read_covers_line(
                summary.tool_name,
                arguments,
                path=path,
                symbol=target,
                line=candidate_line,
            ):
                return True
        return False

    def _strategy_switch(
        self, context: ResearchDecisionContextV1
    ) -> tuple[ResearchAction, ResearchAction]:
        """Pick the alternative strategy after a doomed exact repeat.

        The chosen strategy must itself not repeat an already-executed
        exact call: policy would reject it the same way.  Try every
        deterministic tool-calling strategy in priority order (call trace,
        data flow, branch inspection, configuration, semantic hints,
        behavior subgraph) and pick the first whose exact call is fresh.
        Only when every strategy's exact call already ran (the obligation
        is genuinely exhausted on this runtime) propose a typed gap; the
        gap finalizer still validates exhaustiveness fail-closed.
        """

        candidates: tuple[ResearchAction, ...] = (
            "TRACE_CALLS",
            "TRACE_DATA_FLOW",
            "INSPECT_BRANCH",
            "INSPECT_CONFIG",
            "SEARCH_HINTS",
            "BUILD_BEHAVIOR_SUBGRAPH",
        )
        for candidate in candidates:
            if self._proposed_call_already_executed(context, candidate):
                continue
            if not self._build_tool_calls(context, candidate):
                # Tool not registered for this runtime (e.g. SEARCH_HINTS
                # without ``search_semantic_hints``): skip.
                continue
            return (candidate, "RECORD_GAP")
        # Every strategy is exhausted or unavailable: the obligation cannot
        # make further progress with this runtime; propose a typed gap (the
        # gap finalizer still validates exhaustiveness fail-closed).
        return ("RECORD_GAP", "STOP_BLOCKED")

    def _candidate_search_already_executed(
        self, context: ResearchDecisionContextV1
    ) -> bool:
        """Whether the exact search this obligation would propose already ran
        with no information gain.

        The deterministic search query is stable for a given obligation
        state, so re-proposing it produces the same stable tool-call id,
        which policy correctly rejects as a duplicate no-gain call.  The
        supervisor must switch strategy instead of burning turns until
        fallback-exhaustion STOP_BLOCKED.  The obligation id is part of the
        identity: the same query for another obligation is a fresh search.

        Only an executed search whose tool-call id sits in the no-progress
        window counts: a prior search that *gained* symbols was useful and
        must not be suppressed (the read of its top result may still be
        pending).
        """

        return self._proposed_call_already_executed(context, "SEARCH_SYMBOLS")

    def _proposed_call_already_executed(
        self, context: ResearchDecisionContextV1, action: ResearchAction
    ) -> bool:
        """Whether the exact call this action would build already ran.

        The deterministic tool arguments are stable for a given obligation
        state, so re-proposing an action produces the same stable tool-call
        id that policy rejects as a duplicate no-gain call (either because
        it is in the no-progress window or because it was just executed).
        The supervisor must switch strategy instead of burning turns until
        fallback-exhaustion STOP_BLOCKED.  The obligation id is part of the
        identity: the same tool for another obligation is a fresh call.

        The executed-call summaries are the recent executed window; a
        would-be call whose stable id matches one of them is a guaranteed
        policy rejection.
        """

        obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation is not None
            else ""
        )
        if not obligation_id:
            return False
        calls = self._build_tool_calls(context, action)
        if not calls:
            return False
        proposed = calls[0]
        proposed_id = _stable_tool_call_id(
            context.run_id,
            proposed.tool_name,
            obligation_id,
            arguments=dict(proposed.arguments or {}),
            path_scope=proposed.path_scope,
        )
        for summary in context.executed_tool_calls:
            if summary.tool_name != proposed.tool_name:
                continue
            if summary.obligation_id and summary.obligation_id != obligation_id:
                continue
            executed_id = _stable_tool_call_id(
                context.run_id,
                summary.tool_name,
                obligation_id,
                arguments=dict(summary.arguments or {}),
                path_scope=summary.path_scope,
            )
            if executed_id == proposed_id:
                return True
        return False

    @staticmethod
    def _latest_search_symbol_ref(
        context: ResearchDecisionContextV1,
    ) -> str | None:
        """Return the highest-ranked not-yet-read symbol from the latest search."""

        if not context.recent_observations:
            return None
        active_obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation is not None
            else ""
        )
        search_index = next(
            (
                index
                for index in range(len(context.recent_observations) - 1, -1, -1)
                if context.recent_observations[index].tool_name == "search_symbols"
                and context.recent_observations[index].status in {"success", "truncated"}
                and (
                    not active_obligation_id
                    or context.recent_observations[index].obligation_id
                    == active_obligation_id
                )
            ),
            None,
        )
        if search_index is None:
            return None
        observation = context.recent_observations[search_index]
        previously_read = {
            ref
            for prior in context.recent_observations
            if prior.tool_name == "read_symbol"
            and prior.status == "success"
            and (
                not active_obligation_id
                or prior.obligation_id == active_obligation_id
            )
            for ref in prior.result_refs
            if is_symbol_ref(ref)
        }
        ranked = [ref for ref in observation.result_refs if is_symbol_ref(ref)]
        explicit_symbol = _explicit_author_symbol(
            context.active_obligation.author_text
            if context.active_obligation is not None
            else ""
        )
        if explicit_symbol:
            ranked = [
                ref for ref in ranked
                if (
                    (parsed := split_symbol_ref(ref)) is not None
                    and (
                        parsed[1].casefold() == explicit_symbol.casefold()
                        or parsed[1].casefold().startswith(
                            explicit_symbol.casefold() + "."
                        )
                    )
                )
            ]
        return next(
            (ref for ref in ranked if ref not in previously_read),
            ranked[0] if ranked else None,
        )

    @staticmethod
    def _has_active_symbol_search(context: ResearchDecisionContextV1) -> bool:
        obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation is not None
            else ""
        )
        return any(
            observation.tool_name == "search_symbols"
            and observation.status in {"success", "truncated"}
            and (not obligation_id or observation.obligation_id == obligation_id)
            for observation in context.recent_observations
        )

    @staticmethod
    def _has_exact_source_span(context: ResearchDecisionContextV1) -> bool:
        """Return whether this obligation has a successful exact source read."""

        active_obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation is not None
            else ""
        )
        return any(
            observation.tool_name in {"read_symbol", "read_code_span"}
            and observation.status == "success"
            and bool(observation.exact_span_ids)
            and (
                not active_obligation_id
                or observation.obligation_id == active_obligation_id
            )
            for observation in context.recent_observations
        )

    @staticmethod
    def _latest_search_query(context: ResearchDecisionContextV1) -> str:
        active_obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation is not None
            else ""
        )
        return next(
            (
                observation.query
                for observation in reversed(context.recent_observations)
                if observation.tool_name == "search_symbols"
                and (
                    not active_obligation_id
                    or observation.obligation_id == active_obligation_id
                )
            ),
            "",
        )

    @staticmethod
    def _predicate_candidate_ref(
        context: ResearchDecisionContextV1,
    ) -> str | None:
        """Find a discovered symbol whose identifier matches a typed miss."""

        obligation = context.active_obligation
        if obligation is None:
            return None
        query_terms: set[str] = set()
        for requirement in obligation.missing_information:
            if not requirement.startswith("typed_predicate:"):
                continue
            predicate = requirement.split(":", 1)[1].upper()
            query = _PREDICATE_SEARCH_QUERIES.get(predicate, predicate.lower())
            query_terms.update(re.findall(r"[a-z0-9]+", query.casefold()))
            break
        if not query_terms:
            return None
        for candidate in reversed(obligation.candidate_symbol_ids):
            parsed = split_symbol_ref(candidate) if is_symbol_ref(candidate) else None
            if parsed is None:
                continue
            identifier_terms = set(
                re.findall(r"[a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", parsed[1]).replace("_", " ").casefold())
            )
            if any(
                query_term == identifier_term
                or query_term in identifier_term
                or identifier_term in query_term
                for query_term in query_terms
                for identifier_term in identifier_terms
                if len(query_term) >= 4 or len(identifier_term) >= 4
            ):
                return candidate
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
    "COMPILE_EVIDENCE": None,
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
    no_progress_tool_call_ids: tuple[str, ...] = (),
    ready_tools: tuple[str, ...] = (),
    hard_rules: tuple[str, ...] = (),
    current_supported_claim_ids: tuple[str, ...] = (),
    current_supported_claim_statements: tuple[str, ...] = (),
    executed_tool_calls: tuple[ExecutedToolCallSummaryV1, ...] = (),
    unresolved_must_cover_ids: tuple[str, ...] | None = None,
    behavior_template_search_hints: tuple[BehaviorTemplateSearchHintV1, ...] = (),
    behavior_graph: Any | None = None,
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
    candidate_bound_node_ids: tuple[str, ...] = ()
    if agenda is not None and active_obligation_id:
        for item in agenda.items:
            if item.obligation_id == active_obligation_id:
                active_obligation = item
                typed_targets = tuple(item.typed_behavior_targets)
                missing_info = tuple(item.missing_information)
                top_symbols = tuple(item.candidate_symbol_ids)
                top_nodes = tuple(item.candidate_behavior_node_ids)
                break

    # A candidate whose exact read already executed (for any obligation in
    # this snapshot) is not a fresh read: policy rejects it as a duplicate
    # no-gain call, so advertising it as a top candidate makes both the LLM
    # and the deterministic supervisor propose a doomed READ_CANDIDATE.
    # Filter it out here so both owners move to a trace/inspect/search
    # strategy or a different span instead of churning policy fallbacks.
    if active_obligation is not None and executed_tool_calls:
        kept_symbols: list[str] = []
        for candidate in top_symbols:
            parsed = (
                split_symbol_ref(candidate)
                if is_symbol_ref(candidate)
                else None
            )
            if parsed is None:
                # ``sym:<path>:<name>`` and legacy ``<path>:<name>`` refs
                # have no line; compare by path+symbol only, exactly as
                # ``_read_symbol_path``/``_read_symbol_target`` do.
                body = candidate
                if body.startswith("sym:") or body.startswith("symbol:"):
                    body = body.split(":", 1)[1]
                if ":" not in body:
                    kept_symbols.append(candidate)
                    continue
                cand_path, cand_symbol = body.rsplit(":", 1)
                read_already = any(
                    content_read_covers_line(
                        summary.tool_name,
                        summary.arguments or {},
                        path=cand_path,
                        symbol=cand_symbol,
                        line=None,
                    )
                    for summary in executed_tool_calls
                    if summary.tool_name in {"read_symbol", "read_code_span"}
                )
                if not read_already:
                    kept_symbols.append(candidate)
                continue
            cand_path, cand_symbol, cand_line = parsed
            read_already = any(
                content_read_covers_line(
                    summary.tool_name,
                    summary.arguments or {},
                    path=cand_path,
                    symbol=cand_symbol,
                    line=cand_line,
                )
                for summary in executed_tool_calls
                if summary.tool_name in {"read_symbol", "read_code_span"}
            )
            if not read_already:
                kept_symbols.append(candidate)
        if len(kept_symbols) != len(top_symbols):
            top_symbols = tuple(kept_symbols)

    # A resumed loop may already carry an exact behavior graph even though
    # the compact recent-observation window no longer contains the read that
    # produced it.  Project only nodes whose source span is inside the active
    # obligation's candidate paths; unrelated graph nodes must not discharge
    # the authority boundary for the current obligation.
    if active_obligation is not None and behavior_graph is not None:
        candidate_paths: set[str] = set()
        for candidate in active_obligation.candidate_symbol_ids:
            parsed = split_symbol_ref(candidate) if is_symbol_ref(candidate) else None
            if parsed is not None:
                candidate_paths.add(parsed[0])
            elif candidate.startswith("candidate_path:"):
                candidate_paths.add(candidate.split(":", 1)[1])
            elif ":" in candidate:
                candidate_paths.add(candidate.split(":", 1)[0])
            elif "/" in candidate or "." in candidate:
                candidate_paths.add(candidate)
        graph_node_ids = tuple(
            node.node_id
            for node in getattr(behavior_graph, "nodes", ())
            if any(
                (node.source_span_id or "").startswith(f"span:{path}:")
                for path in candidate_paths
            )
        )
        top_nodes = tuple(dict.fromkeys((*top_nodes, *graph_node_ids)))

        # Candidate-specific graph support: nodes whose symbol_id equals a
        # typed candidate symbol, or whose source span covers the candidate
        # line.  Path-prefix matches above are discovery projections; this
        # second pass is the fail-closed binding the supervisor requires
        # before compiling from a reused read.
        bound: list[str] = []
        bound_seen: set[str] = set()
        for candidate in active_obligation.candidate_symbol_ids:
            parsed = (
                split_symbol_ref(candidate)
                if is_symbol_ref(candidate)
                else None
            )
            if parsed is None:
                continue
            cand_path, cand_name, cand_line = parsed
            cand_symbol_id = make_symbol_id(cand_path, cand_name, cand_line)
            for node in getattr(behavior_graph, "nodes", ()):
                if node.node_id in bound_seen:
                    continue
                if node.symbol_id == cand_symbol_id or span_covers_line(
                    node.source_span_id or "", cand_line
                ):
                    bound_seen.add(node.node_id)
                    bound.append(node.node_id)
        candidate_bound_node_ids = tuple(bound)

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
            query=next(
                (
                    note.split("=", 1)[1]
                    for note in obs.diagnostics.notes
                    if note.startswith("query=")
                ),
                "",
            ),
            semantic_summary=obs.notebook.summary,
            code_excerpt=obs.notebook.code_excerpt,
            discovered_symbols=obs.notebook.discovered_symbols,
            discovered_relations=obs.notebook.discovered_relations,
            enclosing_symbol_refs=obs.notebook.enclosing_symbol_refs,
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
                "COMPILE_EVIDENCE",
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
        current_supported_claim_statements=tuple(
            current_supported_claim_statements
        ),
        missing_information=missing_info,
        top_candidate_symbol_ids=top_symbols,
        top_candidate_behavior_node_ids=top_nodes,
        candidate_bound_behavior_node_ids=candidate_bound_node_ids,
        recent_observations=recent_summaries,
        executed_tool_calls=tuple(executed_tool_calls),
        no_progress_counter=no_progress_counter,
        no_progress_history=no_progress_history,
        no_progress_tool_call_ids=tuple(no_progress_tool_call_ids),
        remaining_budgets=remaining_per_kind,
        per_obligation_remaining=remaining_per_kind,
        allowed_actions=tuple(allowed),
        ready_tools=tuple(ready_tools),
        hard_rules=tuple(hard_rules),
        unresolved_must_cover_ids=tuple(unresolved_ids or ()),
        behavior_template_search_hints=behavior_template_search_hints,
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
    no_progress_tool_call_ids: tuple[str, ...] = (),
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
        no_progress_tool_call_ids=no_progress_tool_call_ids,
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
    run_id: str,
    tool_name: str,
    obligation_id: str,
    *,
    arguments: dict[str, Any] | None = None,
    path_scope: tuple[str, ...] = (),
) -> str:
    material = json.dumps(
        {
            "run": run_id,
            "tool": tool_name,
            "obligation": obligation_id,
            "arguments": arguments or {},
            "path_scope": sorted(path_scope),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"tc-{digest}"


__all__ = [
    "BehaviorTemplateSearchHintV1",
    "DeterministicSupervisorBackend",
    "RecentObservationSummaryV1",
    "ResearchDecisionContextV1",
    "SupervisorBackend",
    "all_fallback_issue_kinds",
    "build_decision_context",
    "fallback_action_for_issue",
    "supervisor_node",
]
