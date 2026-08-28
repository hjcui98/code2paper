"""Policy merge for research supervisor decisions (R3.3).

Implements the deterministic policy layer that validates every supervisor
proposal before any tool call is executed.  Design section 8.2 + R3.3 hard
rules:

1. ``action`` matches the active issue type (or no-issue fallback).
2. every selected tool is currently ``ready`` (registered and not blocked).
3. every ``path_scope`` / argument path resolves inside the repo snapshot.
4. ``obligation_id`` refers to an existing agenda item.
5. no duplicate no-gain calls (same tool+args within the no-progress window).
6. no authority overreach (hint-only observations cannot anchor positive
   claims; tool kind cannot upgrade authority).
7. per-obligation/per-tool-kind budgets are still available.
8. fallback action is safe (terminal or matches the issue kind fallback
   table).

If any rule fails, policy merge rejects the proposal and substitutes a
deterministic fallback decision built from the issue kind.  The fallback
is itself validated; if it also fails, the run routes to ``STOP_BLOCKED``.

The merge is pure: it never executes tools, never calls the LLM, and never
mutates the agenda.  It returns a ``PolicyMergeResult`` describing the
accepted decision, the consumed budget and the trace of rejection reasons
so tests can assert on every rule.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    SupervisorBackend,
    fallback_action_for_issue,
)


# ---------------------------------------------------------------------------
# Rejection reasons
# ---------------------------------------------------------------------------


PolicyRejectionReason = str  # closed below

# Closed set of rejection reason codes so tests can enumerate every entry.
REJECTION_REASONS: tuple[str, ...] = (
    "action_issue_mismatch",
    "tool_not_ready",
    "scope_not_in_snapshot",
    "obligation_does_not_exist",
    "duplicate_no_gain_call",
    "authority_overreach",
    "budget_exhausted",
    "fallback_not_safe",
    "terminal_action_with_tool_calls",
    "tool_calling_action_without_tool_calls",
    "no_active_obligation_for_tool_call",
    "unknown_tool_name",
    "unknown_tool_kind",
)


# ---------------------------------------------------------------------------
# Policy merge result
# ---------------------------------------------------------------------------


class PolicyRejectionV1(BaseModel):
    """A single rejection produced by a policy rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str
    reason: str
    detail: str = ""
    tool_call_id: str = ""


class PolicyMergeResult(BaseModel):
    """Outcome of validating a supervisor proposal.

    ``accepted`` is True iff the proposal (or its fallback) passed all
    rules.  ``decision`` is the decision the graph should execute (either
    the original proposal or the fallback).  ``rejections`` records every
    rule that failed on the original proposal so the trace is explainable.
    ``consumed_budgets`` is the per-obligation/per-tool-kind budget delta
    the graph should apply if it executes the accepted decision.
    """

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    decision: ResearchDecisionV1 | None = None
    rejections: tuple[PolicyRejectionV1, ...] = Field(default_factory=tuple)
    fallback_used: bool = False
    fallback_rejection: PolicyRejectionV1 | None = None
    consumed_budgets: dict[str, dict[str, int]] = Field(default_factory=dict)
    trace_ref: str = ""

    @property
    def rejection_rules(self) -> tuple[str, ...]:
        return tuple(r.rule for r in self.rejections)


# ---------------------------------------------------------------------------
# Policy merge
# ---------------------------------------------------------------------------


def apply_policy_merge(
    proposal: ResearchDecisionV1,
    *,
    agenda: ResearchAgendaV1 | None,
    active_issue: ResearchIssueV1 | None,
    per_obligation_budgets: dict[str, PerObligationBudgetV1],
    global_safety_budget: GlobalSafetyBudgetV1 | None,
    ready_tools: tuple[str, ...],
    recent_tool_call_ids: tuple[str, ...] = (),
    no_progress_tool_call_ids: tuple[str, ...] = (),
    executed_read_signatures: tuple[str, ...] = (),
    executed_tool_calls: tuple[Any, ...] = (),
    repo_snapshot_paths: tuple[str, ...] | None = None,
    fallback_backend: SupervisorBackend | None = None,
    context_run_id: str = "",
    context_repo_snapshot_id: str = "",
    context_turn_index: int = 0,
    gap_justified: bool = False,
) -> PolicyMergeResult:
    """Validate a supervisor proposal against the R3.3 hard rules.

    The function is pure: it returns a ``PolicyMergeResult`` but does not
    mutate any input.  The graph layer is responsible for applying
    ``consumed_budgets`` to the state after executing the accepted
    decision.

    ``executed_read_signatures`` carries the normalized content-read keys
    already executed anywhere in this run (across obligations), so policy
    can reject a proposal that re-reads an exact source span whose bytes
    are already known.  The graph layer builds it from the executed tool
    calls; callers without access to that history (unit tests) simply
    omit it.

    ``executed_tool_calls`` carries the compact executed-call summaries so
    the deterministic fallback context can avoid proposing a doomed exact
    repeat: without them the fallback re-reads the same symbol, policy
    rejects the fallback too, and the run dies in STOP_BLOCKED from
    fallback exhaustion instead of switching strategy.

    ``repo_snapshot_paths`` is optional: when provided, every path scope
    and ``read_symbol`` / ``build_behavior_subgraph`` argument path is
    checked against it.  When omitted, the scope check is skipped (used
    by unit tests that only exercise the budget / obligation rules).

    ``gap_justified`` reports whether the graph's gain tracker considers
    the active obligation exhausted enough for an explicit gap (three
    consecutive no-gain turns or targeted search exhaustion).  It gates
    the second-level RECORD_GAP fallback so a rejected fallback cannot
    manufacture an unjustified gap (the gap finalizer validates the same
    condition fail-closed).
    """

    rejections: list[PolicyRejectionV1] = []

    # Rule 0: structural validation (action vs tool calls).
    _structural_rejections(proposal, rejections)

    # Rule 1: action / issue type match.
    _action_issue_match(proposal, active_issue, rejections)

    # Rule 4: obligation exists.
    obligation_exists = _obligation_exists(
        proposal, agenda, rejections
    )

    # Rule 2: tools ready.
    _tools_ready(proposal, ready_tools, rejections)

    # Rule 3: scope in snapshot.
    if repo_snapshot_paths is not None:
        _scope_in_snapshot(proposal, repo_snapshot_paths, rejections)

    # Rule 5: no duplicate no-gain calls.
    _no_duplicate_no_gain(
        proposal,
        no_progress_tool_call_ids,
        recent_tool_call_ids,
        rejections,
        executed_read_signatures=executed_read_signatures,
    )

    # Rule 6: no authority overreach.
    _no_authority_overreach(proposal, rejections)

    # Rule 7: budgets available.
    budgets_available = _budgets_available(
        proposal, per_obligation_budgets, rejections
    )

    if not rejections:
        # Proposal accepted: compute consumed budgets and return.
        consumed = _compute_consumed_budgets(proposal)
        return PolicyMergeResult(
            accepted=True,
            decision=proposal,
            rejections=(),
            fallback_used=False,
            consumed_budgets=consumed,
            trace_ref=_trace_ref(proposal, fallback_used=False, rejections=()),
            )

    # Proposal rejected: build a deterministic fallback decision.
    fallback_decision, fallback_rejection = _build_fallback_decision(
        proposal=proposal,
        active_issue=active_issue,
        agenda=agenda,
        per_obligation_budgets=per_obligation_budgets,
        global_safety_budget=global_safety_budget,
        ready_tools=ready_tools,
        recent_tool_call_ids=recent_tool_call_ids,
        no_progress_tool_call_ids=no_progress_tool_call_ids,
        executed_tool_calls=executed_tool_calls,
        repo_snapshot_paths=repo_snapshot_paths,
        fallback_backend=fallback_backend,
        context_run_id=context_run_id or proposal.run_id,
        context_repo_snapshot_id=context_repo_snapshot_id,
        context_turn_index=context_turn_index or proposal.turn_index,
    )

    if fallback_decision is None:
        # Fallback also rejected.  Per the R3.3 fallback table the
        # decision's ``fallback_action`` is the documented next move when
        # the fallback is itself rejected (usually RECORD_GAP or
        # STOP_BLOCKED).  Try RECORD_GAP before dying in STOP_BLOCKED from
        # fallback exhaustion -- but only when the graph reports the gap is
        # justified (no-progress threshold met or targeted search
        # exhausted); the gap finalizer still validates exhaustiveness
        # fail-closed.  Without the gate, a rejected RECORD_GAP would
        # route straight back to the same supervisor proposal and churn.
        if (
            proposal.fallback_action == "RECORD_GAP"
            and gap_justified
        ):
            gap_decision = _record_gap_decision(
                run_id=context_run_id or proposal.run_id,
                turn_index=proposal.turn_index,
                obligation_id=proposal.obligation_id,
                issue_id=proposal.issue_id,
                rationale="policy_merge_fallback_exhausted",
            )
            gap_rejections: list[PolicyRejectionV1] = []
            _structural_rejections(gap_decision, gap_rejections)
            _action_issue_match(gap_decision, active_issue, gap_rejections)
            _obligation_exists(gap_decision, agenda, gap_rejections)
            _tools_ready(gap_decision, ready_tools, gap_rejections)
            if repo_snapshot_paths is not None:
                _scope_in_snapshot(gap_decision, repo_snapshot_paths, gap_rejections)
            _no_duplicate_no_gain(
                gap_decision,
                no_progress_tool_call_ids,
                recent_tool_call_ids,
                gap_rejections,
                executed_read_signatures=executed_read_signatures,
            )
            _no_authority_overreach(gap_decision, gap_rejections)
            _budgets_available(
                gap_decision, per_obligation_budgets, gap_rejections
            )
            if not gap_rejections:
                return PolicyMergeResult(
                    accepted=True,
                    decision=gap_decision,
                    rejections=tuple(rejections),
                    fallback_used=True,
                    fallback_rejection=fallback_rejection,
                    consumed_budgets={},
                    trace_ref=_trace_ref(
                        gap_decision, fallback_used=True, rejections=rejections
                    ),
                )
        # Fallback also rejected: route to STOP_BLOCKED.
        stop_decision = _stop_blocked_decision(
            run_id=context_run_id or proposal.run_id,
            turn_index=proposal.turn_index,
            obligation_id=proposal.obligation_id,
            issue_id=proposal.issue_id,
            rationale="policy_merge_fallback_exhausted",
        )
        return PolicyMergeResult(
            accepted=True,
            decision=stop_decision,
            rejections=tuple(rejections),
            fallback_used=True,
            fallback_rejection=fallback_rejection,
            consumed_budgets={},
            trace_ref=_trace_ref(stop_decision, fallback_used=True, rejections=rejections),
        )

    consumed = _compute_consumed_budgets(fallback_decision)
    return PolicyMergeResult(
        accepted=True,
        decision=fallback_decision,
        rejections=tuple(rejections),
        fallback_used=True,
        fallback_rejection=fallback_rejection,
        consumed_budgets=consumed,
        trace_ref=_trace_ref(fallback_decision, fallback_used=True, rejections=rejections),
    )


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _structural_rejections(
    decision: ResearchDecisionV1,
    rejections: list[PolicyRejectionV1],
) -> None:
    """Rule 0: action / tool-call structural alignment.

    Mirrors the ``ResearchDecisionV1`` model validator but produces typed
    rejections instead of raising.  The model validator is the last line
    of defense; policy merge is the first.
    """

    tool_calling_actions = {
        "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "TRACE_DATA_FLOW",
        "INSPECT_BRANCH", "INSPECT_CONFIG", "SEARCH_HINTS",
        "BUILD_BEHAVIOR_SUBGRAPH", "PROPOSE_PACKET", "COMPILE_FACTS",
        "DECOMPOSE_CLAIMS", "REWRITE_SENTENCES",
    }
    terminal_actions = {
        "STOP_BLOCKED", "RECORD_GAP", "COMPILE_EVIDENCE", "PLAN_METHOD"
    }

    if decision.action in tool_calling_actions and not decision.selected_tool_calls:
        rejections.append(
            PolicyRejectionV1(
                rule="tool_calling_action_without_tool_calls",
                reason=f"action {decision.action} requires at least one selected_tool_call",
                detail=f"decision_id={decision.decision_id}",
            )
        )
    if decision.action in terminal_actions and decision.selected_tool_calls:
        rejections.append(
            PolicyRejectionV1(
                rule="terminal_action_with_tool_calls",
                reason=f"action {decision.action} must not select tool calls",
                detail=f"decision_id={decision.decision_id}",
            )
        )


def _action_issue_match(
    decision: ResearchDecisionV1,
    active_issue: ResearchIssueV1 | None,
    rejections: list[PolicyRejectionV1],
) -> None:
    """Rule 1: action must match the active issue kind.

    The fallback table in ``research_supervisor`` is the single source of
    truth for issue-kind -> action.  If the proposal's action is not in
    the allowed set for the active issue (or no-issue), policy rejects.
    """

    if active_issue is None:
        # No-issue proposals accept any tool-calling or terminal action.
        return
    expected_action, _ = fallback_action_for_issue(active_issue)
    # Compilation is always a valid next move once the manager judges that
    # the observations answer the active issue.  The deterministic compiler
    # will still return a typed partial result when evidence is insufficient;
    # forbidding this action here forced the manager to keep searching (or
    # claim STOP_BLOCKED) after it had already found the needed code.
    allowed = {expected_action, "COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"}
    # For trace_data_flow / inspect_branch / inspect_config we also accept the
    # closely related actions (the fallback table is intentionally coarse).
    if expected_action == "TRACE_CALLS":
        allowed |= {"TRACE_DATA_FLOW"}
    if expected_action == "INSPECT_CONFIG":
        allowed |= {"INSPECT_BRANCH", "READ_CANDIDATE"}
    if expected_action == "INSPECT_BRANCH":
        allowed |= {"INSPECT_CONFIG", "READ_CANDIDATE"}
    if expected_action == "READ_CANDIDATE":
        allowed |= {"INSPECT_BRANCH"}
    if expected_action == "SEARCH_SYMBOLS":
        allowed |= {"READ_CANDIDATE", "BUILD_BEHAVIOR_SUBGRAPH"}
    if decision.action not in allowed:
        rejections.append(
            PolicyRejectionV1(
                rule="action_issue_mismatch",
                reason=f"action {decision.action} not allowed for issue {active_issue.issue_kind}",
                detail=f"expected_one_of={sorted(allowed)}",
            )
        )


def _obligation_exists(
    decision: ResearchDecisionV1,
    agenda: ResearchAgendaV1 | None,
    rejections: list[PolicyRejectionV1],
) -> bool:
    """Rule 4: obligation_id must refer to an existing agenda item."""

    if not decision.selected_tool_calls:
        # Terminal action: obligation existence is not required (e.g.
        # STOP_BLOCKED can fire with an empty obligation_id).
        return True
    obligation_id = decision.obligation_id
    if not obligation_id:
        rejections.append(
            PolicyRejectionV1(
                rule="no_active_obligation_for_tool_call",
                reason="tool-calling decision without obligation_id",
                detail=f"decision_id={decision.decision_id}",
            )
        )
        return False
    if agenda is None:
        # No agenda at all: any non-empty obligation is rejected.
        rejections.append(
            PolicyRejectionV1(
                rule="obligation_does_not_exist",
                reason="no agenda loaded but decision carries obligation_id",
                detail=f"obligation_id={obligation_id}",
            )
        )
        return False
    for item in agenda.items:
        if item.obligation_id == obligation_id:
            return True
    rejections.append(
        PolicyRejectionV1(
            rule="obligation_does_not_exist",
            reason="obligation_id not found in agenda",
            detail=f"obligation_id={obligation_id}",
        )
    )
    return False


def _tools_ready(
    decision: ResearchDecisionV1,
    ready_tools: tuple[str, ...],
    rejections: list[PolicyRejectionV1],
) -> None:
    """Rule 2: every selected tool must be registered and ready."""

    ready_set = set(ready_tools)
    for call in decision.selected_tool_calls:
        if call.tool_name not in ready_set:
            rejections.append(
                PolicyRejectionV1(
                    rule="tool_not_ready",
                    reason=f"tool {call.tool_name} is not in ready_tools",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )
        if call.tool_kind not in BUDGET_TOOL_KINDS and call.tool_kind not in {
            "behavior_graph", "configuration", "other",
        }:
            rejections.append(
                PolicyRejectionV1(
                    rule="unknown_tool_kind",
                    reason=f"tool_kind {call.tool_kind} not recognized",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )


def _scope_in_snapshot(
    decision: ResearchDecisionV1,
    snapshot_paths: tuple[str, ...],
    rejections: list[PolicyRejectionV1],
) -> None:
    """Rule 3: every path scope / argument path must resolve inside the snapshot."""

    snapshot_set = set(snapshot_paths)
    for call in decision.selected_tool_calls:
        for path in call.path_scope:
            if path not in snapshot_set and not _path_in_snapshot(path, snapshot_set):
                rejections.append(
                    PolicyRejectionV1(
                        rule="scope_not_in_snapshot",
                        reason=f"path_scope entry {path!r} not in snapshot",
                        detail=f"tool_call_id={call.tool_call_id}",
                        tool_call_id=call.tool_call_id,
                    )
                )
        # read_symbol / build_behavior_subgraph carry an explicit ``path``.
        arg_path = call.arguments.get("path")
        if isinstance(arg_path, str) and arg_path:
            if arg_path not in snapshot_set and not _path_in_snapshot(arg_path, snapshot_set):
                rejections.append(
                    PolicyRejectionV1(
                        rule="scope_not_in_snapshot",
                        reason=f"argument path {arg_path!r} not in snapshot",
                        detail=f"tool_call_id={call.tool_call_id}",
                        tool_call_id=call.tool_call_id,
                    )
                )


def _path_in_snapshot(path: str, snapshot_set: set[str]) -> bool:
    """A path is in-scope if it exactly matches or is a prefix-relative entry."""

    if path in snapshot_set:
        return True
    # Allow directory-style scope prefixes (e.g. "src/" matches "src/foo.py").
    if path.endswith("/"):
        return any(s.startswith(path) for s in snapshot_set)
    return False


def _no_duplicate_no_gain(
    decision: ResearchDecisionV1,
    no_progress_tool_call_ids: tuple[str, ...],
    recent_tool_call_ids: tuple[str, ...],
    rejections: list[PolicyRejectionV1],
    *,
    executed_read_signatures: tuple[str, ...] = (),
) -> None:
    """Rule 5: no duplicate no-gain calls.

    Tool-call ids are stable execution signatures generated from tool name,
    obligation, canonical typed arguments, scope and local limits. They do
    not contain the turn index, so an exact rerun remains visible across
    turns and can be rejected after no gain.

    ``executed_read_signatures`` additionally carries the normalized
    content-read keys (``read_symbol`` path+symbol, ``read_code_span``
    path+span) already executed in this run, across obligations.  Reading
    the same exact source span returns the same bytes inside one repo
    snapshot, so a cross-obligation re-read produces no new information;
    the Manager must instead trace a caller/data/control/config relation
    or read a different span.
    """

    no_progress_set = set(no_progress_tool_call_ids)
    recent_set = set(recent_tool_call_ids)
    executed_read_set = set(executed_read_signatures)
    for call in decision.selected_tool_calls:
        if call.tool_call_id in no_progress_set:
            rejections.append(
                PolicyRejectionV1(
                    rule="duplicate_no_gain_call",
                    reason="tool_call_id already in no-progress window",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )
        # Also reject exact re-runs of the *same* call within a single run
        # (different turn, same id).  The supervisor should always advance
        # the turn_index, producing a different id.
        if call.tool_call_id in recent_set:
            rejections.append(
                PolicyRejectionV1(
                    rule="duplicate_no_gain_call",
                    reason="tool_call_id already executed in this run",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )
        read_signature = _content_read_signature(call)
        if read_signature and read_signature in executed_read_set:
            rejections.append(
                PolicyRejectionV1(
                    rule="duplicate_no_gain_call",
                    reason=(
                        "content read already executed for another "
                        "obligation in this snapshot"
                    ),
                    detail=f"read_signature={read_signature}",
                    tool_call_id=call.tool_call_id,
                )
            )


def _content_read_signature(call: ResearchToolCallV1) -> str:
    """Normalized identity of a content read within one repo snapshot.

    Delegates to the shared canonical identity so policy merge and the
    deterministic supervisor cannot drift apart.  The signature
    deliberately omits obligation id and turn index: the returned source
    bytes are identical whenever the same span is read again in the same
    snapshot, regardless of which obligation prompted the read.
    """

    from code2paper.agentic.research_read_identity import content_read_signature

    return content_read_signature(call.tool_name, call.arguments)


def _no_authority_overreach(
    decision: ResearchDecisionV1,
    rejections: list[PolicyRejectionV1],
) -> None:
    """Rule 6: no authority overreach.

    The supervisor cannot *upgrade* a tool's source authority.  Tools
    declare their authority in ``ResearchObservationV1.source_authority``;
    the supervisor has no field that overrides it.  This rule is therefore
    structural: it rejects any tool call whose ``arguments`` contain an
    explicit ``source_authority`` key (which would be a contract violation
    if the supervisor tried to set one).
    """

    for call in decision.selected_tool_calls:
        if "source_authority" in call.arguments:
            rejections.append(
                PolicyRejectionV1(
                    rule="authority_overreach",
                    reason="tool call arguments must not set source_authority",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )


def _budgets_available(
    decision: ResearchDecisionV1,
    per_obligation_budgets: dict[str, PerObligationBudgetV1],
    rejections: list[PolicyRejectionV1],
) -> bool:
    """Rule 7: per-obligation/per-tool-kind budgets must be available."""

    if not decision.selected_tool_calls:
        return True
    obligation_id = decision.obligation_id
    if not obligation_id:
        # Already reported by rule 4; nothing more to do here.
        return False
    budget = per_obligation_budgets.get(obligation_id)
    if budget is None:
        # No budget envelope registered: this is allowed only for terminal
        # actions, which we already handled.  Treat as exhausted.
        for call in decision.selected_tool_calls:
            rejections.append(
                PolicyRejectionV1(
                    rule="budget_exhausted",
                    reason=f"no budget envelope for obligation {obligation_id}",
                    detail=f"tool_call_id={call.tool_call_id}",
                    tool_call_id=call.tool_call_id,
                )
            )
        return False
    ok = True
    required_by_kind = Counter(call.tool_kind for call in decision.selected_tool_calls)
    for tool_kind, required in required_by_kind.items():
        remaining = budget.remaining(tool_kind)
        if remaining < required:
            affected = next(
                call for call in decision.selected_tool_calls
                if call.tool_kind == tool_kind
            )
            rejections.append(
                PolicyRejectionV1(
                    rule="budget_exhausted",
                    reason=(
                        f"budget for {tool_kind} cannot cover {required} calls "
                        f"on obligation {obligation_id}"
                    ),
                    detail=(
                        f"tool_call_id={affected.tool_call_id} "
                        f"remaining={remaining} required={required}"
                    ),
                    tool_call_id=affected.tool_call_id,
                )
            )
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Fallback construction
# ---------------------------------------------------------------------------


def _build_fallback_decision(
    *,
    proposal: ResearchDecisionV1,
    active_issue: ResearchIssueV1 | None,
    agenda: ResearchAgendaV1 | None,
    per_obligation_budgets: dict[str, PerObligationBudgetV1],
    global_safety_budget: GlobalSafetyBudgetV1 | None,
    ready_tools: tuple[str, ...],
    recent_tool_call_ids: tuple[str, ...],
    no_progress_tool_call_ids: tuple[str, ...],
    executed_tool_calls: tuple[Any, ...] = (),
    repo_snapshot_paths: tuple[str, ...] | None,
    fallback_backend: SupervisorBackend | None,
    context_run_id: str,
    context_repo_snapshot_id: str,
    context_turn_index: int,
) -> tuple[ResearchDecisionV1 | None, PolicyRejectionV1 | None]:
    """Build and validate a deterministic fallback decision.

    Returns ``(fallback_decision, None)`` on success, ``(None, rejection)``
    if the fallback is itself rejected.  When the fallback is rejected, the
    caller routes to ``STOP_BLOCKED``.
    """

    # Extract repo_snapshot_id from the proposal's tool calls when the
    # caller didn't provide one.  This is needed because policy merge is
    # often called with only the proposal, not the full graph state.
    snapshot_id = context_repo_snapshot_id
    if not snapshot_id:
        for call in proposal.selected_tool_calls:
            if call.repo_snapshot_id:
                snapshot_id = call.repo_snapshot_id
                break
    if not snapshot_id:
        # No snapshot id available anywhere: cannot build a fallback
        # context.  Return None so the caller routes to STOP_BLOCKED.
        return None, PolicyRejectionV1(
            rule="fallback_not_safe",
            reason="cannot build fallback context without repo_snapshot_id",
            detail="no_snapshot_id_in_proposal_or_context",
        )

    run_id = context_run_id or proposal.run_id

    backend = fallback_backend or DeterministicSupervisorBackend(
        run_id=run_id,
        repo_snapshot_id=snapshot_id,
        ready_tools=ready_tools,
    )
    # Build a minimal context for the fallback backend.  The fallback only
    # uses the active issue and the (synthetic) turn index, so we don't
    # need the full state.
    from code2paper.agentic.research_supervisor import ResearchDecisionContextV1

    obligation_id = proposal.obligation_id
    active_obligation: ResearchAgendaItemV1 | None = None
    if agenda is not None and obligation_id:
        for item in agenda.items:
            if item.obligation_id == obligation_id:
                active_obligation = item
                break

    fallback_context = ResearchDecisionContextV1(
        run_id=run_id,
        repo_snapshot_id=snapshot_id,
        turn_index=context_turn_index + 1,  # advance turn to avoid id collision
        active_obligation=active_obligation,
        active_issue=active_issue,
        ready_tools=tuple(ready_tools),
        allowed_actions=("SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS",
                          "RECORD_GAP", "STOP_BLOCKED"),
        # The deterministic supervisor must see what already ran, exactly as
        # the LLM supervisor does, or it re-proposes the same doomed exact
        # read/search that policy rejected for the original proposal; policy
        # then rejects the fallback too and the run dies in STOP_BLOCKED
        # from fallback exhaustion.  With the summaries it can switch to a
        # fresh strategy (trace/data flow/branch/config) or record a gap.
        executed_tool_calls=tuple(executed_tool_calls),
        no_progress_tool_call_ids=tuple(no_progress_tool_call_ids),
    )
    fallback_decision = backend.decide(fallback_context)

    # Validate the fallback against the same rules.
    fallback_rejections: list[PolicyRejectionV1] = []
    _structural_rejections(fallback_decision, fallback_rejections)
    _action_issue_match(fallback_decision, active_issue, fallback_rejections)
    _obligation_exists(fallback_decision, agenda, fallback_rejections)
    _tools_ready(fallback_decision, ready_tools, fallback_rejections)
    if repo_snapshot_paths is not None:
        _scope_in_snapshot(fallback_decision, repo_snapshot_paths, fallback_rejections)
    _no_duplicate_no_gain(
        fallback_decision, no_progress_tool_call_ids, recent_tool_call_ids,
        fallback_rejections,
    )
    _no_authority_overreach(fallback_decision, fallback_rejections)
    _budgets_available(fallback_decision, per_obligation_budgets, fallback_rejections)

    if fallback_rejections:
        # Return the first rejection as the fallback rejection reason.
        first = fallback_rejections[0]
        return None, first
    return fallback_decision, None


def _stop_blocked_decision(
    *,
    run_id: str,
    turn_index: int,
    obligation_id: str,
    issue_id: str,
    rationale: str,
) -> ResearchDecisionV1:
    """Build a terminal STOP_BLOCKED decision."""

    return ResearchDecisionV1(
        decision_id=_fallback_decision_id(run_id, turn_index, "STOP_BLOCKED"),
        run_id=run_id,
        turn_index=turn_index,
        action="STOP_BLOCKED",
        obligation_id=obligation_id,
        issue_id=issue_id,
        goal="policy_merge_fallback_exhausted",
        selected_tool_calls=(),
        candidate_scope=(),
        expected_information_gain="terminal_blocked",
        evidence_needed=(),
        stop_condition="policy_merge_fallback_exhausted",
        fallback_action=None,
        rationale=rationale,
        produced_by="policy_override",
    )


def _record_gap_decision(
    *,
    run_id: str,
    turn_index: int,
    obligation_id: str,
    issue_id: str,
    rationale: str,
) -> ResearchDecisionV1:
    """Build a RECORD_GAP decision as the second-level fallback.

    When the deterministic fallback is itself rejected (for example a
    duplicate no-gain call), the run must not die in STOP_BLOCKED from
    fallback exhaustion: per the R3.3 fallback table the decision's
    ``fallback_action`` (usually RECORD_GAP) is the documented next move.
    The graph's gap finalizer still validates exhaustiveness fail-closed
    before the obligation is marked ``explicit_gap``.
    """

    return ResearchDecisionV1(
        decision_id=_fallback_decision_id(run_id, turn_index, "RECORD_GAP"),
        run_id=run_id,
        turn_index=turn_index,
        action="RECORD_GAP",
        obligation_id=obligation_id,
        issue_id=issue_id,
        goal="policy_merge_fallback_exhausted",
        selected_tool_calls=(),
        candidate_scope=(),
        expected_information_gain="typed_gap",
        evidence_needed=(),
        stop_condition="policy_merge_fallback_exhausted",
        fallback_action=None,
        rationale=rationale,
        produced_by="policy_override",
    )


# ---------------------------------------------------------------------------
# Budget accounting
# ---------------------------------------------------------------------------


def _compute_consumed_budgets(
    decision: ResearchDecisionV1,
) -> dict[str, dict[str, int]]:
    """Compute the per-obligation/per-tool-kind budget delta to apply."""

    if not decision.selected_tool_calls:
        return {}
    obligation_id = decision.obligation_id
    if not obligation_id:
        return {}
    delta: dict[str, int] = {}
    for call in decision.selected_tool_calls:
        delta[call.tool_kind] = delta.get(call.tool_kind, 0) + 1
    return {obligation_id: delta}


def apply_consumed_budgets(
    budgets: dict[str, PerObligationBudgetV1],
    consumed: dict[str, dict[str, int]],
) -> dict[str, PerObligationBudgetV1]:
    """Return a new budgets dict with ``consumed`` applied.

    Pure: never mutates the input dict.  Used by the graph layer after a
    policy-merged decision is executed.
    """

    new_budgets = dict(budgets)
    for obligation_id, kind_delta in consumed.items():
        current = new_budgets.get(obligation_id)
        if current is None:
            continue
        updated = current
        for tool_kind, amount in kind_delta.items():
            updated = updated.consume(tool_kind, amount)
        new_budgets[obligation_id] = updated
    return new_budgets


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fallback_decision_id(
    run_id: str, turn_index: int, action: ResearchAction
) -> str:
    material = f"{run_id}|{turn_index}|{action}|fallback".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"decision-{digest}"


def _trace_ref(
    decision: ResearchDecisionV1,
    *,
    fallback_used: bool,
    rejections: tuple[PolicyRejectionV1, ...] | list[PolicyRejectionV1],
) -> str:
    payload = {
        "decision_id": decision.decision_id,
        "action": decision.action,
        "obligation_id": decision.obligation_id,
        "fallback_used": fallback_used,
        "rejection_rules": [r.rule for r in rejections],
        "produced_by": decision.produced_by,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()[:12]
    return f"policy-merge:{digest}:{decision.decision_id}"


__all__ = [
    "PolicyMergeResult",
    "PolicyRejectionV1",
    "REJECTION_REASONS",
    "PolicyRejectionReason",
    "apply_consumed_budgets",
    "apply_policy_merge",
]
