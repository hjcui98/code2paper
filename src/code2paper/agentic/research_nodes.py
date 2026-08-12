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
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1, make_symbol_id
from code2paper.agentic.generic_claim_compiler import (
    ClaimProposalV1,
)
from code2paper.agentic.generic_evidence_compiler import (
    EvidencePacketProposalV1,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
    GENERIC_RESEARCH_PRODUCER_VERSION,
)
from code2paper.agentic.obligation_fact_alignment import (
    BEHAVIOR_PREDICATE_ALIASES,
    align_target_to_facts,
)
from code2paper.agentic.language_adapter_registry import (
    LanguageAdapterRegistry,
    default_language_adapter_registry,
)
from code2paper.agentic.execution_profile import (
    ExecutionProfileV1,
    ExecutionRouteV1,
    assert_evidence_policy_unchanged,
    route_execution_profile,
)
from code2paper.agentic.research_models import (
    BUDGET_TOOL_KINDS,
    GapRequirementV1,
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
from code2paper.agentic.typed_refs import (
    behavior_refs,
    is_behavior_ref,
    is_entrypoint_ref,
    is_symbol_ref,
    split_symbol_ref,
    split_span_ref,
    symbol_refs,
)


_SPECIALIZED_MISSING_TERMS: dict[str, tuple[str, ...]] = {
    "call": ("call", "relation", "invoke", "dispatch"),
    "data": ("data", "flow", "input", "output"),
    "branch": ("branch", "condition", "control"),
    "config": ("config", "parameter", "setting", "option"),
}


def _resolved_missing_information(
    missing: list[str], observation: ResearchObservationV1
) -> list[str]:
    """Remove only research requirements satisfied by a strong observation."""

    if observation.status != "success" or observation.source_authority == "hint_only":
        return missing
    tool_categories = {
        "find_references": {"call"},
        "trace_call_path": {"call"},
        "trace_data_flow": {"data"},
        "inspect_control_flow": {"branch"},
        "inspect_configuration": {"config"},
        "build_behavior_subgraph": {"call", "data", "branch"},
    }.get(observation.tool_name, set())
    concrete_read = observation.tool_name in {"read_symbol", "build_behavior_subgraph"}
    observed_paths = {
        parsed[0]
        for ref in observation.exact_span_ids
        if (parsed := split_span_ref(ref)) is not None
    }
    for ref in observation.result_refs:
        parsed = split_symbol_ref(ref)
        if parsed is not None:
            observed_paths.add(parsed[0])

    unresolved: list[str] = []
    for requirement in missing:
        if requirement.startswith("typed_semantic:"):
            # Only target-to-fact alignment can discharge a semantic
            # requirement.  A successful read may still contain unrelated
            # code, so keep the requirement available for relevance ranking.
            unresolved.append(requirement)
            continue
        normalized = requirement.casefold()
        categories = {
            category
            for category, terms in _SPECIALIZED_MISSING_TERMS.items()
            if any(term in normalized for term in terms)
        }
        if requirement.startswith("candidate_path:"):
            # Candidate paths are alternatives, not an all-paths obligation.
            if concrete_read and observed_paths:
                continue
        elif categories:
            if categories & tool_categories:
                continue
        elif concrete_read and observed_paths:
            # A successful exact code read satisfies the agenda's generic
            # retrieval query; specialized relation/config questions remain.
            continue
        unresolved.append(requirement)
    return unresolved


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
    behavior_graph: int = 4
    configuration: int = 4

    def envelope_for(self, obligation_id: str) -> PerObligationBudgetV1:
        limits: dict[str, int] = {
            "symbol_search": self.symbol_search,
            "code_read": self.code_read,
            "call_trace": self.call_trace,
            "data_flow_trace": self.data_flow_trace,
            "branch_inspection": self.branch_inspection,
            "hint_search": self.hint_search,
            "packet_repair": self.packet_repair,
            "behavior_graph": self.behavior_graph,
            "configuration": self.configuration,
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
        self._attempted_tools: dict[str, set[str]] = {}
        self._exhausted_tools: dict[str, set[str]] = {}
        self._no_progress: dict[str, int] = {}
        self._gain_history: dict[str, list[str]] = {}
        self._last_gain_items: dict[str, tuple[str, ...]] = {}

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
        self._attempted_tools.setdefault(obligation_id, set()).add(
            observation.tool_name
        )
        if observation.status in {"success_empty", "scope_exhausted"}:
            self._exhausted_tools.setdefault(obligation_id, set()).add(
                observation.tool_name
            )

        gained_items: list[str] = []
        for span in observation.exact_span_ids:
            if span not in spans:
                spans.add(span)
                gained_items.append(f"span:{span}")
        for ref in observation.result_refs:
            # Phase 3: use typed_refs for uniform symbol/entrypoint
            # detection instead of hard-coded ``startswith`` checks.
            # This lets the gain tracker recognize every symbol or
            # entrypoint reference produced by the research tools.
            if is_symbol_ref(ref) or is_entrypoint_ref(ref):
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
        self._last_gain_items[obligation_id] = tuple(gained_items)
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

    def attempted_tools(self, obligation_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._attempted_tools.get(obligation_id, set())))

    def has_exact_span(self, obligation_id: str) -> bool:
        """Return whether code was actually read for this obligation.

        Symbol-search hits are discovery hints.  They may seed behavior
        parsing, but they cannot authorize compilation until a read tool has
        returned an exact, snapshot-bound source span.
        """

        return bool(self._seen_spans.get(obligation_id))

    def latest_gain_includes_exact_span(self, obligation_id: str) -> bool:
        return any(
            item.startswith("span:")
            for item in self._last_gain_items.get(obligation_id, ())
        )

    def exhausted_tools(self, obligation_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._exhausted_tools.get(obligation_id, set())))

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot (for checkpoint persistence)."""

        return {
            "seen_spans": {k: sorted(v) for k, v in self._seen_spans.items()},
            "seen_symbols": {k: sorted(v) for k, v in self._seen_symbols.items()},
            "seen_predicates": {k: sorted(v) for k, v in self._seen_predicates.items()},
            "seen_relations": {k: sorted(v) for k, v in self._seen_relations.items()},
            "attempted_tools": {k: sorted(v) for k, v in self._attempted_tools.items()},
            "exhausted_tools": {k: sorted(v) for k, v in self._exhausted_tools.items()},
            "no_progress": dict(self._no_progress),
            "gain_history": {k: list(v) for k, v in self._gain_history.items()},
            "last_gain_items": {k: list(v) for k, v in self._last_gain_items.items()},
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any] | None) -> "InformationGainTracker":
        """Reconstruct a tracker from a ``snapshot()`` payload.

        Phase 4: enables cross-instance checkpoint/resume for the
        multi-node LangGraph topology.  When ``snapshot`` is ``None`` or
        not a mapping, a fresh tracker is returned so callers can use
        this method unconditionally on the resume path.
        """

        tracker = cls()
        if not isinstance(snapshot, dict):
            return tracker
        for key, field in (
            ("seen_spans", "_seen_spans"),
            ("seen_symbols", "_seen_symbols"),
            ("seen_predicates", "_seen_predicates"),
            ("seen_relations", "_seen_relations"),
            ("attempted_tools", "_attempted_tools"),
            ("exhausted_tools", "_exhausted_tools"),
            ("no_progress", "_no_progress"),
            ("gain_history", "_gain_history"),
            ("last_gain_items", "_last_gain_items"),
        ):
            value = snapshot.get(key)
            if not isinstance(value, dict):
                continue
            if key == "gain_history":
                setattr(
                    tracker,
                    field,
                    {k: list(v) for k, v in value.items() if isinstance(v, list)},
                )
            elif key == "last_gain_items":
                setattr(
                    tracker,
                    field,
                    {k: tuple(v) for k, v in value.items() if isinstance(v, list)},
                )
            elif key == "no_progress":
                setattr(
                    tracker,
                    field,
                    {k: int(v) for k, v in value.items() if isinstance(v, (int, float))},
                )
            else:
                setattr(
                    tracker,
                    field,
                    {k: set(v) for k, v in value.items() if isinstance(v, (list, tuple, set))},
                )
        return tracker


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
    intent_graph: Any | None = None
    intent_target_proposal_report: dict[str, Any] = Field(default_factory=dict)
    budget_policy: BudgetPolicyV1 = Field(default_factory=BudgetPolicyV1)
    global_safety_budget: GlobalSafetyBudgetV1 = Field(default_factory=GlobalSafetyBudgetV1)
    supervisor_backend: SupervisorBackend | None = None
    artifact_root: Path | None = None
    adapter_registry: LanguageAdapterRegistry = Field(default_factory=default_language_adapter_registry)
    adapter_language: str = ""
    # D6 execution routing is explicit runtime configuration.  It is kept
    # separate from evidence artifacts and never changes their validators or
    # authorization decisions.  With no profile the historical route remains
    # the default, preserving backwards compatibility.
    execution_profile: ExecutionProfileV1 | None = None
    execution_route: ExecutionRouteV1 | None = None
    execution_opt_in: bool = False
    execution_canary_key: str = ""
    execution_rollback: bool = False
    execution_default_authorized: bool = False
    evidence_policy_digest: str = ""
    ready_tools: tuple[str, ...] = (
        "find_entrypoints",
        "search_symbols",
        "read_symbol",
        "find_references",
        "build_behavior_subgraph",
        "trace_call_path",
        "trace_data_flow",
        "inspect_control_flow",
        "inspect_configuration",
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

    @model_validator(mode="after")
    def _bind_execution_route(self) -> "ResearchGraphRuntime":
        profile = self.execution_profile
        if profile is None:
            if self.execution_route is not None:
                raise ValueError("execution_route requires execution_profile")
            return self
        expected_digest = self.evidence_policy_digest.strip() or profile.evidence_policy_digest
        if profile.evidence_policy_digest != expected_digest:
            raise ValueError("execution profile evidence policy digest mismatch")
        expected_route = route_execution_profile(
            profile,
            opt_in=self.execution_opt_in,
            canary_key=self.execution_canary_key or self.run_id,
            rollback=self.execution_rollback,
            default_authorized=self.execution_default_authorized,
        )
        if (
            self.execution_route is not None
            and self.execution_route.model_dump(mode="json")
            != expected_route.model_dump(mode="json")
        ):
            raise ValueError("execution route does not match the selected profile and rollout inputs")
        route = expected_route
        assert_evidence_policy_unchanged(route, expected_digest)
        # The model is frozen, so bind derived values through pydantic's
        # documented post-validation escape hatch.  The route is now part of
        # the runtime identity and can be serialized for rollout evidence.
        object.__setattr__(self, "execution_route", route)
        object.__setattr__(self, "evidence_policy_digest", expected_digest)
        if not self.adapter_language.strip() and profile.language.strip():
            object.__setattr__(self, "adapter_language", profile.language.strip().lower())
        return self

    def supervisor(self) -> SupervisorBackend:
        return self.supervisor_backend or DeterministicSupervisorBackend(
            run_id=self.run_id,
            repo_snapshot_id=self.repo_snapshot.snapshot_id,
            ready_tools=self.ready_tools,
            hard_rules=self.hard_rules,
        )

    @property
    def execution_enabled(self) -> bool:
        """Whether this configured route is allowed to execute agentic work."""

        return self.execution_route.execute if self.execution_route is not None else True

    @property
    def execution_shadow(self) -> bool:
        """Whether this run is a shadow observation rather than an opt-in run."""

        return bool(self.execution_route and self.execution_route.shadow)

    def execution_manifest(self) -> dict[str, Any]:
        """Return route metadata without exposing a policy override surface."""

        return {
            "profile": self.execution_profile.model_dump(mode="json")
            if self.execution_profile is not None
            else {},
            "route": self.execution_route.model_dump(mode="json")
            if self.execution_route is not None
            else {},
            "evidence_policy_digest": self.evidence_policy_digest,
        }

    def tool_context(
        self,
        *,
        behavior_graph: CodeBehaviorGraphV1 | None = None,
    ) -> ResearchToolContext:
        artifact_root = self.artifact_root
        if artifact_root is None:
            # The immutable checkpoint store must survive a process/runtime
            # object restart.  PID/object identity made a fresh runtime point
            # at a different directory, so a valid cross-instance snapshot
            # looked missing and could not be resumed.  Run id + frozen
            # snapshot identity are the stable namespace; callers that need
            # isolation across repeated runs should provide artifact_root.
            runtime_identity = hashlib.sha256(
                (
                    f"v3:{self.run_id}:{self.repo_snapshot.snapshot_id}:"
                    f"{self.repo_snapshot.project_tree_hash}"
                ).encode("utf-8")
            ).hexdigest()[:20]
            artifact_root = (
                Path(tempfile.gettempdir())
                / "code2paper-research-tool-runtime"
                / runtime_identity
            )
        return ResearchToolContext(
            repo_snapshot=self.repo_snapshot,
            behavior_graph=behavior_graph,
            artifact_root=artifact_root,
            adapter_registry=self.adapter_registry,
            adapter_language=self.adapter_language,
        )

    def snapshot_paths(self) -> tuple[str, ...]:
        return tuple(f.path for f in self.repo_snapshot.included_files)

    def language_adapter(self, files: dict[str, str] | None = None) -> Any:
        if self.adapter_language.strip():
            return self.adapter_registry.get(self.adapter_language)
        candidates = files or {path: "" for path in self.snapshot_paths()}
        return self.adapter_registry.for_files(candidates)


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

    files = _read_snapshot_files(runtime.repo_snapshot)
    adapter = runtime.language_adapter(files)
    symbol_index = adapter.index_symbols(
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        files=files,
    )
    symbol_index_digest = symbol_index.content_digest
    return {
        "symbol_index_ref": symbol_index_digest,
        "behavior_graph_ref": _empty_behavior_graph_digest(
            runtime.repo_snapshot, language=adapter.language
        ),
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
    behavior_graph: CodeBehaviorGraphV1 | None = None,
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
        behavior_template_search_hints=_behavior_template_search_hints(behavior_graph),
        behavior_graph=behavior_graph,
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
        "_policy_merge_results": [merge_result],
    }


def _behavior_template_search_hints(graph: CodeBehaviorGraphV1 | None):
    """Return compact structural hints; never facts or claim authorization."""

    if graph is None or os.environ.get(
        "CODE2PAPER_AGENTIC_BEHAVIOR_TEMPLATES", "1"
    ).strip().lower() in {"0", "false", "no", "off"}:
        return ()
    from code2paper.agentic.behavior_templates import (
        DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES,
        match_all_templates,
    )
    from code2paper.agentic.research_supervisor import BehaviorTemplateSearchHintV1

    templates = {
        item.template_id: item
        for item in DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES
    }
    matches = sorted(
        match_all_templates(DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES, graph),
        key=lambda item: (not item.matched, -item.match_score, item.template_id),
    )
    hints = []
    for match in matches:
        if not match.matched and match.match_score <= 0:
            continue
        template = templates[match.template_id]
        hints.append(BehaviorTemplateSearchHintV1(
            template_id=match.template_id,
            matched=match.matched,
            match_score=match.match_score,
            missing_predicates=match.missing_predicates,
            missing_relation_kinds=match.missing_relation_kinds,
            resolved_role_symbols=match.resolved_role_symbols,
            predicate_order_hint=template.query.predicate_order_hint,
        ))
        if len(hints) >= 3:
            break
    return tuple(hints)


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
    *,
    behavior_graph: CodeBehaviorGraphV1 | None = None,
) -> tuple[list[ResearchObservationV1], list[str]]:
    """Execute a batch of tool calls and return (observations, trace_refs).

    Factored out of ``research_tool_node`` so tests can drive tool execution
    without going through the LangGraph state.
    """

    ctx = runtime.tool_context(behavior_graph=behavior_graph)
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

    Phase 3: the node now also extracts ``symbol:`` and ``behavior:``
    refs from each admissible observation and merges them into the
    active obligation's ``candidate_symbol_ids`` /
    ``candidate_behavior_node_ids``.  This repairs the evidence chain:
    the ``evidence_critic_node`` routes to ``compile_candidate`` only
    when ``candidate_symbol_ids`` is non-empty, so without this update
    the loop never produces compiled evidence.
    """

    active_obligation_id = active_obligation_id or state.get("active_obligation_id", "")
    if not active_obligation_id:
        return {"recent_observation_refs": []}

    no_progress_counter = gain_tracker.no_progress_counter(active_obligation_id)
    no_progress_history = gain_tracker.gain_history(active_obligation_id)

    # Locate the active obligation so we can update its candidate lists.
    active_obligation: ResearchAgendaItemV1 | None = None
    for item in runtime.agenda.items:
        if item.obligation_id == active_obligation_id:
            active_obligation = item
            break

    # Track which observations are admissible for positive claims.
    admissible_refs: list[str] = []
    # Preserve tool ranking.  Turning result refs into sets made the next
    # READ_CANDIDATE target depend on hash iteration order rather than the
    # deterministic search rank.  Candidate batches are merged in reverse
    # because the compact supervisor intentionally reads the newest entry
    # from the tail; therefore the tool's rank-1 result becomes that tail.
    new_symbol_refs: list[str] = []
    new_behavior_refs: list[str] = []
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
        # Phase 3: extract typed refs so the obligation's candidate
        # lists stay in sync with what the tools actually observed.
        # The evidence_critic_node reads candidate_symbol_ids to decide
        # whether to route to compile_candidate; without this update
        # the loop never compiles evidence.
        for ref in symbol_refs(list(obs.result_refs)):
            if ref not in new_symbol_refs:
                new_symbol_refs.append(ref)
        for ref in behavior_refs(list(obs.result_refs)):
            if ref not in new_behavior_refs:
                new_behavior_refs.append(ref)
        if active_obligation is not None:
            active_obligation.missing_information = _resolved_missing_information(
                active_obligation.missing_information,
                obs,
            )

    # Merge new refs into the active obligation's candidate lists
    # (deduplicated).  The agenda item is mutable (not frozen) so
    # in-place extension is safe and consistent with how
    # gap_finalizer_node / compile_candidate_node mutate status.
    candidate_symbol_ids: list[str] = []
    candidate_behavior_node_ids: list[str] = []
    if active_obligation is not None:
        existing_symbols = set(active_obligation.candidate_symbol_ids)
        existing_behaviors = set(active_obligation.candidate_behavior_node_ids)
        for ref in reversed(new_symbol_refs):
            if ref not in existing_symbols:
                active_obligation.candidate_symbol_ids.append(ref)
                existing_symbols.add(ref)
        for ref in new_behavior_refs:
            if ref not in existing_behaviors:
                active_obligation.candidate_behavior_node_ids.append(ref)
                existing_behaviors.add(ref)
        candidate_symbol_ids = list(active_obligation.candidate_symbol_ids)
        candidate_behavior_node_ids = list(
            active_obligation.candidate_behavior_node_ids
        )

    state_update: dict[str, Any] = {
        "recent_observation_refs": admissible_refs,
        "no_progress_counters": {
            active_obligation_id: gain_tracker.no_progress_counter(active_obligation_id)
        },
    }
    # Include the candidate lists in the state update so downstream
    # nodes (and checkpoint consumers) can see the current candidates
    # without re-reading the agenda.  These channels are read by the
    # evidence_critic_node and compile_candidate_node.
    if active_obligation is not None:
        state_update["candidate_symbol_ids"] = candidate_symbol_ids
        state_update["candidate_behavior_node_ids"] = candidate_behavior_node_ids
    return state_update


# ---------------------------------------------------------------------------
# Node: behavior_graph_updater
# ---------------------------------------------------------------------------


def _find_symbol_by_location(
    symbol_index: Any,
    path: str,
    qualified_name: str,
    start_line: int,
) -> Any | None:
    """Find a ``SymbolRefV1`` by (path, qualified_name, start_line).

    The research tools emit ``symbol:<path>:<name>:<line>`` refs whose
    body is the *location* of the symbol, not its ``symbol_id`` (which
    is ``sym:<hash>``).  This helper bridges the two representations so
    the behavior graph updater can re-parse the cited symbol and merge
    its operations into the running graph.
    """

    for sym in symbol_index.symbols:
        if (
            sym.path == path
            and sym.qualified_name == qualified_name
            and sym.start_line == start_line
        ):
            return sym
    # Fallback: match on (path, start_line) only — the qualified_name
    # in the ref may differ from the index's qualified_name when the
    # tool emits a short name (e.g. ``Bar`` vs ``module.Bar``).
    for sym in symbol_index.symbols:
        if sym.path == path and sym.start_line == start_line:
            return sym
    return None


def _parse_behavior_ref_body(body: str) -> tuple[str, str, int] | None:
    """Parse a ``behavior:<path>:<symbol>:<line>`` ref body.

    Returns ``(path, symbol, line)`` or ``None`` when the body is not
    a valid ``<path>:<symbol>:<line>`` triple.  The path may contain
    colons, so the split is anchored from the right.
    """

    if not body:
        return None
    parts = body.rsplit(":", 2)
    if len(parts) < 3:
        return None
    path, name, line_str = parts
    try:
        line = int(line_str)
    except ValueError:
        return None
    if not path or not name or line < 1:
        return None
    return path, name, line


def behavior_graph_updater_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    behavior_graph: CodeBehaviorGraphV1,
    observations: tuple[ResearchObservationV1, ...],
    active_obligation_id: str,
) -> tuple[CodeBehaviorGraphV1, dict[str, Any]]:
    """Merge new behavior subgraphs extracted from observations.

    For every exact ``read_symbol`` / ``build_behavior_subgraph``
    observation, the node re-parses the cited symbol and merges the resulting
    nodes into the running ``CodeBehaviorGraphV1``.  ``search_symbols`` refs
    remain discovery-only and never enter the executable evidence graph.

    Phase 3: ref filtering now uses ``typed_refs`` so both
    ``symbol:<path>:<name>:<line>`` refs (from ``search_symbols``) and
    ``behavior:<path>:<name>:<line>`` refs (from
    ``build_behavior_subgraph``) are handled uniformly.  The previous
    implementation looked up the ref body as a ``symbol_id`` (which is
    ``sym:<hash>``) and never matched — this is the root cause of the
    broken evidence chain.

    Returns the updated behavior graph (carried in the runtime, not the
    state) and a state update containing the new digest.
    """

    files = _read_snapshot_files(runtime.repo_snapshot)
    adapter = runtime.language_adapter(files)
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
        if not obs.exact_span_ids and obs.tool_name == "read_symbol":
            continue
        # Phase 3: handle both ``symbol:`` and ``behavior:`` refs via
        # typed_refs.  Each ref carries a (path, name, line) location
        # that we resolve to a SymbolRefV1 in the V2 index, then
        # re-parse and merge the resulting subgraph.
        for ref in obs.result_refs:
            sym = None
            if is_symbol_ref(ref):
                parsed = split_symbol_ref(ref)
                if parsed is not None:
                    path, name, line = parsed
                    sym = _find_symbol_by_location(
                        symbol_index, path, name, line
                    )
            elif is_behavior_ref(ref):
                # ``behavior:<path>:<symbol>:<line>`` — parse the body
                # and resolve to a SymbolRefV1 by location.
                body = ref.split(":", 1)[1] if ":" in ref else ""
                parsed = _parse_behavior_ref_body(body)
                if parsed is not None:
                    path, name, line = parsed
                    sym = _find_symbol_by_location(
                        symbol_index, path, name, line
                    )
            else:
                continue
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
    if new_predicates:
        available_relation_kinds = {
            relation.kind for relation in updated_graph.relations
        }
        for item in runtime.agenda.items:
            if item.obligation_id != active_obligation_id:
                continue
            retained: list[str] = []
            for value in item.missing_information:
                if value.startswith("typed_semantic:"):
                    # Preserve the exact semantic miss so packet ranking can
                    # prioritize the newly read node that satisfies it.  The
                    # compile alignment, not the read itself, discharges it.
                    retained.append(value)
                    continue
                if value.startswith("typed_predicate:"):
                    desired = value.split(":", 1)[1].upper()
                    if (
                        desired in new_predicates
                        or BEHAVIOR_PREDICATE_ALIASES.get(desired, frozenset())
                        & new_predicates
                    ):
                        continue
                if value.startswith("typed_relation:"):
                    if value.split(":", 1)[1].upper() in available_relation_kinds:
                        continue
                retained.append(value)
            item.missing_information = retained
            break
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

    # Recompile whenever exact evidence exists, even when an earlier compile
    # recorded typed missing information. Search turns may add candidate
    # symbols and read turns may add graph nodes; both need to replay typed
    # alignment instead of searching until a false gap is emitted.
    if (
        active_obligation.candidate_symbol_ids
        and gain_tracker.has_exact_span(active_obligation_id)
    ):
        return "compile_candidate", {"status": "researching"}

    return "search_more", {"status": "researching"}


# ---------------------------------------------------------------------------
# Node: compile_candidate (R4 wiring)
# ---------------------------------------------------------------------------


def _select_behavior_nodes_for_obligation(
    behavior_graph: CodeBehaviorGraphV1,
    *,
    candidate_symbol_ids: list[str],
    candidate_behavior_node_ids: list[str],
) -> list[Any]:
    """Select behavior nodes relevant to an obligation.

    Prefers explicit ``candidate_behavior_node_ids``; falls back to
    matching ``candidate_symbol_ids`` against behavior nodes.  The fallback
    handles multiple candidate formats because callers use different
    conventions:

    - exact ``symbol_id`` (``sym:<digest>``) — direct match;
    - exact ``node_id`` (``node:<digest>``) — direct match;
    - ``path:name`` (e.g. ``train.py:train``) — match by extracting the
      path prefix and checking the node's ``source_span_id``;
    - bare path (e.g. ``train.py`` or ``src/``) — match by path prefix
      in ``source_span_id``.

    Returns nodes in deterministic order (by node_id).
    """

    nodes_by_id = {n.node_id: n for n in behavior_graph.nodes}
    if candidate_behavior_node_ids:
        normalized_node_ids = {
            value.removeprefix("behavior:")
            for value in candidate_behavior_node_ids
            if value
        }
        selected = [
            nodes_by_id[nid]
            for nid in normalized_node_ids
            if nid in nodes_by_id
        ]
    else:
        selected = _match_nodes_by_candidate(behavior_graph.nodes, candidate_symbol_ids)
    # De-duplicate by node_id while preserving sorted order for determinism.
    seen: set[str] = set()
    unique: list[Any] = []
    for node in sorted(selected, key=lambda n: n.node_id):
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        unique.append(node)
    return unique


def _match_nodes_by_candidate(
    nodes: list[Any],
    candidate_symbol_ids: list[str],
) -> list[Any]:
    """Match behavior nodes against heterogeneous candidate identifiers.

    Each candidate is matched against the node's ``symbol_id``,
    ``node_id`` and ``source_span_id``.  Path-like candidates
    (e.g. ``train.py:train`` or ``src/model.py``) are matched by checking
    whether the node's ``source_span_id`` starts with
    ``span:<path>:`` (directory candidates are prefix-matched).
    """

    if not candidate_symbol_ids:
        return []
    # Typed symbol refs carry the exact indexed symbol location.  Prefer
    # those over seed paths, otherwise a successful lookup of one function
    # can accidentally compile every operation in the same file.
    typed_symbol_ids = {
        make_symbol_id(path, name, line)
        for candidate in candidate_symbol_ids
        if (parsed := split_symbol_ref(candidate)) is not None
        for path, name, line in (parsed,)
    }
    if typed_symbol_ids:
        return [n for n in nodes if n.symbol_id in typed_symbol_ids]

    selected: list[Any] = []
    for candidate in candidate_symbol_ids:
        if not candidate:
            continue
        # Direct symbol_id / node_id match.
        direct = [
            n for n in nodes
            if n.symbol_id == candidate or n.node_id == candidate
        ]
        if direct:
            selected.extend(direct)
            continue
        # Path-based match: extract the path component and match
        # source_span_id (format ``span:<path>:<start>:<end>``).
        path_component = _extract_path_component(candidate)
        if path_component:
            prefix = f"span:{path_component}:"
            prefix_dir = path_component.rstrip("/") + "/"
            for node in nodes:
                span_id = node.source_span_id or ""
                if span_id.startswith(prefix):
                    selected.append(node)
                elif _span_path_matches_prefix(span_id, prefix_dir):
                    selected.append(node)
    return selected


_COMPILE_NODE_LIMIT = 3
_COMPILE_FACT_LIMIT = 8
_SEMANTIC_STOP_WORDS = frozenset({
    "about", "after", "also", "author", "before", "behavior", "candidate",
    "code", "describe", "from", "implementation", "information", "method",
    "missing", "module", "paper", "path", "project", "related", "should",
    "stage", "system", "that", "their", "this", "through", "using", "with",
})


def _semantic_tokens(value: Any) -> set[str]:
    """Return conservative identifier-like terms for relevance matching."""

    original = str(value)
    compact_identifiers = {
        token.lower()
        for token in re.findall(
            r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+\b", original
        )
        if len(token) >= 3
    }
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", original)
    tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]+|\d+", text.replace("_", " "))
    }
    normalized: set[str] = set(compact_identifiers)
    for token in tokens:
        if not (len(token) >= 3 or token.isdigit()):
            continue
        if token.lower() in _SEMANTIC_STOP_WORDS:
            continue
        if token in {"dim", "dims", "dimensional"}:
            normalized.add("dimension")
        elif token in {"mamba", "ssm"}:
            normalized.add("state_space")
        elif token in {"ppr", "pagerank"}:
            normalized.add("pagerank")
        elif token in {"generation", "generated", "generates", "infer", "inference"}:
            normalized.add("generate")
        elif token in {"propagate", "propagates", "propagating", "propagation"}:
            normalized.add("propagate")
        elif token in {"filter", "filtering", "prune", "pruned", "prunes", "pruning", "threshold"}:
            normalized.add("filter")
        elif token in {
            "score", "scores", "scoring", "predict", "predicts",
            "prediction", "predictor",
        }:
            normalized.add("predict")
        elif token in {"infonce", "contrastive", "logsumexp"}:
            normalized.add("contrastive_objective")
        elif token.endswith("ing") and len(token) > 6:
            normalized.add(token[:-3])
        elif token.endswith("ed") and len(token) > 5:
            normalized.add(token[:-2])
        elif len(token) > 4 and token.endswith("s"):
            normalized.add(token[:-1])
        else:
            normalized.add(token)
    if {"state", "space"} <= normalized:
        normalized.add("state_space")
    return normalized


def _obligation_retrieval_terms(
    obligation: ResearchAgendaItemV1,
) -> tuple[set[str], set[str]]:
    """Collect semantic terms and requested predicates from typed intent."""

    terms = _semantic_tokens(obligation.author_text)
    predicates: set[str] = set()
    for missing in obligation.missing_information:
        # Candidate-path bookkeeping is a search control, not a semantic
        # requirement, and must not make an arbitrary node look relevant.
        if "candidate_path" not in missing.lower():
            terms.update(_semantic_tokens(missing))
    for target in obligation.typed_behavior_targets:
        raw_predicates = {value.upper() for value in target.desired_predicates}
        predicates.update(raw_predicates)
        # Expand with aliases so AGGREGATE also matches CONCAT/STACK/REDUCE
        # nodes, and CONSTRUCT also matches CALL/LOAD nodes.  Without this,
        # _rank_relevant_behavior_nodes would filter out all nodes when the
        # adapter never emits the abstract predicate directly.
        for pred in raw_predicates:
            predicates.update(BEHAVIOR_PREDICATE_ALIASES.get(pred, frozenset()))
        for values in (
            target.search_terms,
            target.aliases,
            target.inputs,
            target.transformations,
            target.decisions,
            target.outputs,
            target.conditions,
        ):
            for value in values:
                terms.update(_semantic_tokens(value))
        terms.update(_semantic_tokens(target.role))
    return terms, predicates


def _rank_relevant_behavior_nodes(
    nodes: list[Any],
    obligation: ResearchAgendaItemV1,
    *,
    limit: int | None = None,
) -> list[Any]:
    """Select a small, obligation-relevant behavior slice.

    When legacy/test obligations contain no semantic intent at all, retain a
    deterministic bounded fallback.  Once intent supplies retrieval terms or
    desired predicates, at least one term/predicate must match; otherwise the
    compiler fails closed and the caller records a typed gap.
    """

    terms, desired_predicates = _obligation_retrieval_terms(obligation)
    missing_semantic_terms = {
        term
        for requirement in obligation.missing_information
        if requirement.startswith("typed_semantic:")
        for term in _semantic_tokens(requirement.split(":", 2)[-1])
    }
    if limit is None:
        # Three is the normal minimality target.  A typed obligation may
        # require a few distinct predicates; allow a bounded larger slice
        # rather than mechanically deleting evidence needed to resolve it.
        required_group_count = sum(
            len(target.predicate_groups) if target.predicate_groups else len(target.desired_predicates)
            for target in obligation.typed_behavior_targets
        )
        base_limit = max(_COMPILE_NODE_LIMIT, required_group_count)
        if obligation.priority in {"must_cover", "should_cover"}:
            base_limit += 5
        limit = min(_COMPILE_FACT_LIMIT, base_limit)
    if not terms and not desired_predicates:
        return sorted(nodes, key=lambda node: node.node_id)[:limit]

    symbol_terms: dict[str, set[str]] = {}
    for candidate in obligation.candidate_symbol_ids:
        parsed = split_symbol_ref(candidate)
        if parsed is None:
            continue
        path, name, line = parsed
        symbol_terms.setdefault(make_symbol_id(path, name, line), set()).update(
            _semantic_tokens(name)
        )

    ranked: list[tuple[int, str, Any]] = []
    node_terms_by_id: dict[str, set[str]] = {}
    local_node_terms_by_id: dict[str, set[str]] = {}
    for node in nodes:
        node_terms: set[str] = set()
        for value in (
            node.predicate,
            node.operands,
            node.result,
            node.guard,
            node.iteration_context,
            node.shape_or_type_hints,
        ):
            node_terms.update(_semantic_tokens(value))
        local_node_terms_by_id[node.node_id] = set(node_terms)
        node_terms.update(symbol_terms.get(node.symbol_id, set()))
        node_terms_by_id[node.node_id] = node_terms
        overlap = terms & node_terms
        predicate_match = node.predicate.upper() in desired_predicates
        # A single shared word (for example ``model`` or ``step``) is too
        # weak to authorize a Method claim.  Typed predicate intent can
        # disambiguate one semantic term; untyped prose needs two distinct
        # overlaps.  This deliberately prefers an explicit gap over a
        # plausible but unrelated operation from the right file.
        if predicate_match:
            # Typed predicates are the deterministic authorization key;
            # lexical terms are only needed to align untyped search prose.
            relevant = True
        else:
            relevant = len(overlap) >= 2
        if not relevant:
            continue
        score = (
            len(overlap) * 4
            + len(missing_semantic_terms & node_terms) * 12
            + (8 if predicate_match else 0)
        )
        ranked.append((score, node.node_id, node))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    ranked_nodes = [item[2] for item in ranked]

    # A strong semantic anchor (PageRank, state-space/Mamba, attention,
    # adjacency construction, ...) defines a coherent symbol family.  Once a
    # witness exists, do not mix earlier same-predicate candidates from an
    # unrelated implementation into the same evidence packet.
    anchor_requirements = [
        _semantic_tokens(value)
        for target in obligation.typed_behavior_targets
        for value in target.transformations
        if _semantic_tokens(value)
    ]
    anchor_symbols: set[str] = set()
    for requirement in anchor_requirements:
        anchor_symbols.update(
            node.symbol_id
            for node in ranked_nodes
            if requirement <= node_terms_by_id.get(node.node_id, set())
        )
    if anchor_symbols:
        requested_family_terms = terms & {
            "attention", "pagerank", "state_space",
        }
        anchor_family_terms = {
            term
            for node in ranked_nodes
            if node.symbol_id in anchor_symbols
            for term in symbol_terms.get(node.symbol_id, set())
            if term in requested_family_terms
        }
        if anchor_family_terms:
            anchor_symbols.update(
                node.symbol_id
                for node in ranked_nodes
                if anchor_family_terms
                & symbol_terms.get(node.symbol_id, set())
            )
        ranked_nodes = [
            node for node in ranked_nodes if node.symbol_id in anchor_symbols
        ]

    # Preserve typed predicate coverage under the bounded packet limit.  A
    # plain top-N cut can spend all eight slots on repeated LOAD/CALL nodes
    # from a long orchestration function and omit the one CONCAT or NORMALIZE
    # node that the obligation explicitly requires.
    desired_groups: list[tuple[tuple[str, ...], frozenset[str]]] = []
    for target in obligation.typed_behavior_targets:
        groups = target.predicate_groups or tuple(
            (predicate,) for predicate in target.desired_predicates
        )
        target_semantic_terms = frozenset(
            term
            for values in (
                target.inputs,
                target.transformations,
                target.decisions,
                target.outputs,
                tuple(
                    value for value in target.conditions
                    if value not in {"any", "training", "inference"}
                ),
            )
            for value in values
            for term in _semantic_tokens(value)
        )
        for group in groups:
            normalized_group = tuple(
                dict.fromkeys(predicate.upper() for predicate in group)
            )
            group_key = (normalized_group, target_semantic_terms)
            if normalized_group and group_key not in desired_groups:
                desired_groups.append(group_key)
    selected: list[Any] = []
    selected_ids: set[str] = set()
    for group, target_semantic_terms in desired_groups:
        equivalents: set[str] = set(group)
        for desired in group:
            equivalents.update(
                BEHAVIOR_PREDICATE_ALIASES.get(desired, frozenset())
            )
        candidate = next(
            (
                node
                for node in ranked_nodes
                if node.node_id not in selected_ids
                and node.predicate.upper() in equivalents
                and (
                    not target_semantic_terms
                    or target_semantic_terms
                    <= node_terms_by_id.get(node.node_id, set())
                )
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            selected_ids.add(candidate.node_id)
        if len(selected) >= limit:
            return selected

    # Once an author-relevant symbol has been identified, retain a bounded
    # method-completeness closure of high-information operations from that
    # same executable symbol.  These operations are not authorized by a
    # regression fixture or profile: they come from the exact source span
    # already selected for the obligation.  This prevents minimal predicate
    # coverage from dropping configuration branches, routing/top-k readouts,
    # normalization, propagation, or the returned output that a Method
    # section needs to form a closed mechanism description.
    if obligation.priority in {"must_cover", "should_cover"} and selected:
        selected_symbols = {node.symbol_id for node in selected}
        completeness_predicates = (
            "BRANCH",
            "NORMALIZE",
            "TOPK",
            "SORT",
            "PROPAGATE",
            "ATTEND",
            "REDUCE",
            "RETURN",
        )
        same_symbol_nodes = sorted(
            (
                node
                for node in nodes
                if node.symbol_id in selected_symbols
                and node.node_id not in selected_ids
            ),
            key=lambda node: node.node_id,
        )
        completeness_terms = {
            term
            for target in obligation.typed_behavior_targets
            for value in (
                *target.search_terms,
                *target.transformations,
                *target.conditions,
                *target.decisions,
            )
            for term in _semantic_tokens(value)
        }
        for predicate in completeness_predicates:
            predicate_candidates = [
                node
                for node in same_symbol_nodes
                if node.node_id not in selected_ids
                and node.predicate.upper() == predicate
            ]
            predicate_candidates.sort(key=lambda node: (
                -len(completeness_terms & local_node_terms_by_id.get(node.node_id, set())),
                -len(terms & local_node_terms_by_id.get(node.node_id, set())),
                node.node_id,
            ))
            candidate = predicate_candidates[0] if predicate_candidates else None
            if candidate is None:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.node_id)
            if len(selected) >= limit:
                return selected
    for node in ranked_nodes:
        if node.node_id in selected_ids:
            continue
        selected.append(node)
        selected_ids.add(node.node_id)
        if len(selected) >= limit:
            break
    return selected


def _extract_path_component(candidate: str) -> str:
    """Extract a file path from a candidate identifier.

    Handles ``path:name`` and bare ``path`` forms.  Returns an empty
    string when the candidate does not look like a path (e.g. it is a
    ``sym:`` / ``node:`` id without a slash or dot).

    Phase 3: also handles typed ``symbol:<path>:<name>:<line>`` refs
    via ``split_symbol_ref`` so the behavior graph updater and the
    compile candidate node can match candidates produced by
    ``observation_ingest_node`` against ``span:<path>:...`` ids.
    """

    raw = candidate.strip()
    if not raw:
        return ""
    # Phase 3: typed ``symbol:<path>:<name>:<line>`` ref — extract the
    # path component directly from the parsed fields.
    if is_symbol_ref(raw):
        parsed = split_symbol_ref(raw)
        if parsed is not None:
            return parsed[0]
        return ""
    # ``sym:`` / ``node:`` ids without a path separator are not paths.
    if raw.startswith(("sym:", "node:")) and "/" not in raw and "." not in raw:
        return ""
    # ``path:name`` — take everything before the last colon that follows
    # a dot or slash.  This is a heuristic; the path component itself
    # may contain dots (e.g. ``src/pkg.mod.py:func``).
    if ":" in raw:
        head, _, _tail = raw.rpartition(":")
        if head and ("." in head or "/" in head):
            return head
    # Bare path (no colon) — return as-is if it looks like a path.
    if "." in raw or "/" in raw:
        return raw
    return ""


def _span_path_matches_prefix(span_id: str, path_prefix_dir: str) -> bool:
    """Check whether ``span:<path>:...`` has a path under ``path_prefix_dir``."""

    if not span_id.startswith("span:") or not path_prefix_dir:
        return False
    body = span_id[len("span:"):]
    parts = body.split(":", 2)
    if len(parts) < 3:
        return False
    path = parts[0]
    return path == path_prefix_dir.rstrip("/") or path.startswith(path_prefix_dir)


def _select_relations_among_nodes(
    behavior_graph: CodeBehaviorGraphV1,
    selected_node_ids: set[str],
) -> list[Any]:
    """Return internal relations plus exact config dependencies of nodes."""

    out: list[Any] = []
    for rel in behavior_graph.relations:
        if not rel.source_node_id or not rel.target_node_id:
            continue
        if rel.source_node_id in selected_node_ids and (
            rel.target_node_id in selected_node_ids or rel.kind == "CONFIGURED_BY"
        ):
            out.append(rel)
    return out


def _build_evidence_packet_proposal(
    *,
    obligation_id: str,
    selected_nodes: list[Any],
    selected_relations: list[Any],
) -> EvidencePacketProposalV1 | None:
    """Build a deterministic ``EvidencePacketProposalV1`` from selected nodes.

    Returns ``None`` when the selection has no anchor spans (no source_span_id
    on any node), which means the proposal cannot anchor a packet.
    """

    anchor_span_ids: list[str] = []
    relation_span_ids: list[str] = []
    behavior_node_ids = [n.node_id for n in selected_nodes]
    # CONFIGURED_BY deliberately permits a selected operation to point at an
    # unselected configuration/default node.  Its target span is a relation
    # span, so the packet must also carry that endpoint node; otherwise the
    # compiler receives ``relation_span_ids`` that cannot be materialized and
    # the EvidencePacket model rejects an otherwise exact proposal.
    for relation in selected_relations:
        for node_id in (relation.source_node_id, relation.target_node_id):
            if node_id and node_id not in behavior_node_ids:
                behavior_node_ids.append(node_id)
    behavior_relation_ids = [r.relation_id for r in selected_relations]
    conditions: list[str] = []
    for node in selected_nodes:
        if not node.source_span_id:
            continue
        if node.source_span_id not in anchor_span_ids:
            anchor_span_ids.append(node.source_span_id)
        if node.guard and node.guard not in conditions:
            conditions.append(node.guard)
    for rel in selected_relations:
        for span_id in (rel.source_span_id, rel.target_span_id):
            if span_id and span_id not in anchor_span_ids and span_id not in relation_span_ids:
                relation_span_ids.append(span_id)
    if not anchor_span_ids:
        return None
    # Compose a deterministic packet id from obligation + span digest so
    # repeated compiles of the same selection produce the same id.
    import hashlib as _hashlib

    digest_input = "|".join(sorted(anchor_span_ids + relation_span_ids))
    digest = _hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12]
    packet_id = f"pkt-{obligation_id}-{digest}"
    scope = selected_nodes[0].symbol_id if selected_nodes else obligation_id
    # Packets with more than three spans require a composition rationale.
    total_spans = len(anchor_span_ids) + len(relation_span_ids)
    rationale = ""
    if total_spans > 3:
        rationale = (
            f"Deterministic selection covers {len(anchor_span_ids)} anchor "
            f"spans and {len(relation_span_ids)} relation spans across "
            f"{len(selected_nodes)} behavior nodes."
        )
    return EvidencePacketProposalV1(
        packet_id=packet_id,
        obligation_id=obligation_id,
        scope=scope,
        anchor_span_ids=anchor_span_ids,
        relation_span_ids=relation_span_ids,
        semantic_span_ids=[],
        behavior_node_ids=behavior_node_ids,
        behavior_relation_ids=behavior_relation_ids,
        conditions=conditions,
        composition_rationale=rationale,
        rejected_candidates=[],
    )


def _build_claim_proposals_for_facts(
    *,
    obligation_id: str,
    facts: Any,
) -> list[ClaimProposalV1]:
    """Build conservative ``ClaimProposalV1`` per supported fact.

    One claim per supported fact avoids merging contradictory conditions.
    Wording is a simple declarative sentence (``{subject} {predicate} {object}``)
    so no quantifier / direction expansion can occur.  ``required_qualifiers``
    mirrors the fact's conditions so no guard is silently dropped.
    """

    proposals: list[ClaimProposalV1] = []
    supported_facts = [
        fact for fact in facts.facts if fact.validation_status == "supported"
    ]
    # Preserve at least one claim for each method-significant operation
    # before filling the remaining bounded slots in source/compiler order.
    # Relation closure can add LOAD/WRITE facts ahead of a later branch or
    # top-k operation; a plain ``facts[:N]`` then makes executable content
    # visible to coverage but unavailable to the Writer.
    significant_predicates = (
        "branches_on",
        "normalizes",
        "selects_top_k",
        "sorts_by",
        "propagates",
        "attends",
        "reduces",
        "returns",
        "computes_formula",
    )
    selected_facts: list[Any] = []
    selected_fact_ids: set[str] = set()
    for predicate in significant_predicates:
        fact = next(
            (item for item in supported_facts if item.predicate == predicate),
            None,
        )
        if fact is None:
            continue
        selected_facts.append(fact)
        selected_fact_ids.add(fact.fact_id)
        if len(selected_facts) >= _COMPILE_FACT_LIMIT:
            break
    # Preserve a second executable implementation for predicates where
    # method diversity changes the mechanism (most importantly propagation
    # modes and configuration branches).  This second pass occurs only after
    # every significant predicate had a chance to reserve one slot.
    diversity_predicates = (
        "propagates",
        "branches_on",
        "normalizes",
        "selects_top_k",
        "sorts_by",
        "returns",
        "computes_formula",
    )
    for predicate in diversity_predicates:
        selected_subjects = {
            item.subject for item in selected_facts if item.predicate == predicate
        }
        fact = next(
            (
                item for item in supported_facts
                if item.predicate == predicate
                and item.fact_id not in selected_fact_ids
                and item.subject not in selected_subjects
            ),
            None,
        )
        if fact is None:
            continue
        selected_facts.append(fact)
        selected_fact_ids.add(fact.fact_id)
        if len(selected_facts) >= _COMPILE_FACT_LIMIT:
            break
    for fact in supported_facts:
        if len(selected_facts) >= _COMPILE_FACT_LIMIT:
            break
        if fact.fact_id in selected_fact_ids:
            continue
        selected_facts.append(fact)
        selected_fact_ids.add(fact.fact_id)

    for fact in selected_facts:
        if fact.validation_status != "supported":
            continue
        obj = fact.object
        if isinstance(obj, list):
            obj_text = ", ".join(obj)
        else:
            obj_text = str(obj)
        # Replace underscores in predicate for readable text; the
        # canonical identity is computed from the normalized text + fact ids,
        # so this wording does not affect dedup.
        predicate_text = fact.predicate.replace("_", " ")
        canonical_text = f"{fact.subject} {predicate_text} {obj_text}".strip()
        proposal = ClaimProposalV1(
            claim_id=f"claim-{obligation_id}-{fact.fact_id}",
            canonical_text=canonical_text,
            claim_kind="implementation_behavior",
            proposed_fact_ids=[fact.fact_id],
            covers_obligation_ids=[obligation_id],
            required_qualifiers=list(fact.conditions),
            unsupported_author_fragments=[],
            allowed_wording_boundary=(
                "exact behavior predicate and operands from source span; "
                "no quantifier, direction, or effect expansion"
            ),
        )
        proposals.append(proposal)
    return proposals


def _alignment_semantic_context(
    obligation: ResearchAgendaItemV1,
    selected_nodes: list[Any],
) -> tuple[str, ...]:
    """Expose only descriptors from exact behavior nodes in the packet.

    ``candidate_symbol_ids`` also contains un-read symbol-search hints.  A
    hint such as ``LLM.infer`` may route the next tool call, but it is not an
    evidence span and must never lend its name to an unrelated fact (for
    example making an indexing CALL satisfy a generation target).
    """

    values: list[str] = []
    for node in selected_nodes:
        values.extend((node.predicate, node.result, node.guard, node.iteration_context))
        values.extend(node.operands)
    return tuple(value for value in values if value)


def _execute_compile_data_plane_tool(
    *,
    ctx: ResearchToolContext,
    obligation_id: str,
    packet_id: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> ResearchObservationV1:
    """Execute one deterministic D1 tool call with a replay-stable identity."""

    call = ResearchToolCallV1(
        tool_call_id=f"compile:{obligation_id}:{packet_id}:{tool_name}",
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS[tool_name],
        obligation_id=obligation_id,
        goal=f"compile validated evidence for {obligation_id}",
        repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
        arguments=arguments,
    )
    return execute_research_tool(ctx, call)


def _compile_data_plane_failure(
    *,
    state: AgentStateV3,
    obligation: ResearchAgendaItemV1,
    observation: ResearchObservationV1,
) -> dict[str, Any]:
    """Return a typed, retryable issue instead of converting tool failure to gap."""

    issue_token = hashlib.sha256(
        f"{observation.tool_name}:{observation.output_digest}".encode("utf-8")
    ).hexdigest()[:16]
    requirement = (
        f"tool_data_plane:{observation.tool_name}:"
        f"{observation.error_message or observation.status}"
    )
    if requirement not in obligation.missing_information:
        obligation.missing_information.append(requirement)
    return {
        "status": "researching",
        "active_issue_id": f"issue:data-plane:{issue_token}",
        "tool_call_trace_refs": [
            *list(state.get("tool_call_trace_refs", []) or []),
            _observation_ref(observation),
        ],
        "candidate_symbol_ids": list(obligation.candidate_symbol_ids),
        "candidate_behavior_node_ids": list(
            obligation.candidate_behavior_node_ids
        ),
    }


def compile_candidate_node(
    state: AgentStateV3,
    *,
    runtime: ResearchGraphRuntime,
    behavior_graph: CodeBehaviorGraphV1,
    active_obligation_id: str,
    gain_tracker: InformationGainTracker,
) -> dict[str, Any]:
    """Compile the active obligation's candidate into authorized claims (R4).

    Replaces the R3 stub that recorded a gap and moved on.  This node:

    1. Selects behavior nodes/relations for the active obligation from the
       live ``CodeBehaviorGraphV1``.
    2. Submits the packet through ``propose_evidence_packet`` and
       ``validate_evidence_packet``.
    3. Runs ``compile_code_facts`` and ``validate_code_facts`` against the
       persisted validated packet.
    4. Submits Agent-scoped claim groupings through
       ``decompose_atomic_claims`` and ``authorize_atomic_claims``.
    5. On success: marks the obligation ``supported`` with
       ``supported_claim_ids`` and returns the packet/fact/claim refs.
    6. On failure (no packet, no supported facts, or no authorized claims):
       delegates to ``gap_finalizer_node`` so the obligation gets a typed
       gap rather than silently looping.

    The compiled ``EvidencePacketSetV3`` / ``CodeFactSetV1`` /
    ``AtomicClaimSetV3`` are returned via a private ``_compiled_evidence``
    channel so the driver can stash them in the loop state sidecar for the
    writer to consume.  The state only stores content digests (refs).
    """

    active_obligation_id = active_obligation_id or state.get("active_obligation_id", "")
    if not active_obligation_id:
        return {
            "status": "blocked",
            "blocked_reason": "compile_candidate_without_active_obligation",
        }

    # Look up the active obligation.
    active_obligation: ResearchAgendaItemV1 | None = None
    for item in runtime.agenda.items:
        if item.obligation_id == active_obligation_id:
            active_obligation = item
            break
    if active_obligation is None:
        return {
            "status": "blocked",
            "blocked_reason": "compile_candidate_obligation_not_in_agenda",
        }

    # If already terminal, do nothing.
    if active_obligation.status in {"supported", "explicit_gap", "blocked"}:
        return {"status": "researching"}

    selected_nodes = _select_behavior_nodes_for_obligation(
        behavior_graph,
        candidate_symbol_ids=active_obligation.candidate_symbol_ids,
        candidate_behavior_node_ids=active_obligation.candidate_behavior_node_ids,
    )
    selected_nodes = _rank_relevant_behavior_nodes(
        selected_nodes,
        active_obligation,
    )
    if not selected_nodes:
        # Nothing to compile: route to gap finalizer.
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )

    selected_node_ids = {n.node_id for n in selected_nodes}
    selected_relations = _select_relations_among_nodes(
        behavior_graph, selected_node_ids
    )

    proposal = _build_evidence_packet_proposal(
        obligation_id=active_obligation_id,
        selected_nodes=selected_nodes,
        selected_relations=selected_relations,
    )
    if proposal is None:
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )

    tool_ctx = runtime.tool_context(behavior_graph=behavior_graph)
    compile_observations: list[ResearchObservationV1] = []

    propose_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="propose_evidence_packet",
        arguments={
            "obligation_tag": proposal.obligation_id,
            "packet_id": proposal.packet_id,
            "scope": proposal.scope,
            "anchor_span_ids": tuple(proposal.anchor_span_ids),
            "relation_span_ids": tuple(proposal.relation_span_ids),
            "semantic_span_ids": tuple(proposal.semantic_span_ids),
            "behavior_node_ids": tuple(proposal.behavior_node_ids),
            "behavior_relation_ids": tuple(proposal.behavior_relation_ids),
            "conditions": tuple(proposal.conditions),
            "composition_rationale": proposal.composition_rationale,
        },
    )
    compile_observations.append(propose_observation)
    if propose_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=propose_observation,
        )

    packet_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="validate_evidence_packet",
        arguments={"packet_id": proposal.packet_id},
    )
    compile_observations.append(packet_observation)
    if packet_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=packet_observation,
        )
    packet_payload = tool_ctx.read_artifact("validated_packets", proposal.packet_id)
    if packet_payload is None:
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=packet_observation.model_copy(
                update={
                    "status": "invalid_request",
                    "error_message": "validated packet artifact missing",
                }
            ),
        )
    packet = EvidencePacketV3.model_validate(packet_payload)

    fact_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="compile_code_facts",
        arguments={"packet_id": proposal.packet_id},
    )
    compile_observations.append(fact_observation)
    if fact_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=fact_observation,
        )
    fact_payload = tool_ctx.read_artifact("fact_sets", proposal.packet_id)
    if fact_payload is None:
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=fact_observation.model_copy(
                update={
                    "status": "invalid_request",
                    "error_message": "compiled fact artifact missing",
                }
            ),
        )
    fact_set = CodeFactSetV1.model_validate(fact_payload)
    validate_fact_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="validate_code_facts",
        arguments={
            "fact_id": proposal.packet_id,
            "fact_set_id": proposal.packet_id,
        },
    )
    compile_observations.append(validate_fact_observation)
    if validate_fact_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=validate_fact_observation,
        )
    target_alignments = [
        align_target_to_facts(
            target,
            fact_set.facts,
            behavior_relations=selected_relations,
            semantic_context=_alignment_semantic_context(
                active_obligation,
                selected_nodes,
            ),
        )
        for target in active_obligation.typed_behavior_targets
    ]
    if not target_alignments:
        # Lexical/semantic similarity may select a candidate, but only typed
        # target-to-fact alignment can authorize obligation coverage (R5.2).
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )
    if not all(alignment.status == "resolved" for alignment in target_alignments):
        unresolved_predicates = sorted({
            predicate
            for alignment in target_alignments
            for predicate in alignment.unmatched_predicates
        })
        for predicate in unresolved_predicates:
            requirement = f"typed_predicate:{predicate}"
            if requirement not in active_obligation.missing_information:
                active_obligation.missing_information.append(requirement)
        unresolved_relations = sorted({
            relation
            for alignment in target_alignments
            for relation in alignment.unmatched_relations
        })
        for relation in unresolved_relations:
            requirement = f"typed_relation:{relation}"
            if requirement not in active_obligation.missing_information:
                active_obligation.missing_information.append(requirement)
        for target, alignment in zip(
            active_obligation.typed_behavior_targets,
            target_alignments,
        ):
            requirements = _target_semantic_requirements_for_search(target)
            for field in alignment.unmatched_semantic_fields:
                terms = requirements.get(field, "")
                requirement = f"typed_semantic:{field}:{terms}"
                if requirement not in active_obligation.missing_information:
                    active_obligation.missing_information.append(requirement)
        # Persist validated packets/facts even while the obligation remains
        # unresolved.  Fact authority is independent from claim coverage:
        # dropping an exact, validated fact here makes configuration and
        # completeness artifacts depend on whether an unrelated predicate
        # happened to resolve in the same turn.
        partial_packet_set = EvidencePacketSetV3(
            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            packets=[packet],
            content_digest=packet.source_digest,
        )
        empty_claim_payload = {
            "claims": [],
            "explicit_code_gaps": [],
            "semantic_stage_groups": [],
        }
        partial_claim_set = AtomicClaimSetV3(
            producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
            evidence_packet_digest=partial_packet_set.content_digest,
            code_fact_digest=fact_set.content_digest,
            claims=[],
            content_digest=_digest_payload(empty_claim_payload),
        )
        return {
            "status": "researching",
            "candidate_symbol_ids": list(active_obligation.candidate_symbol_ids),
            "candidate_behavior_node_ids": list(
                active_obligation.candidate_behavior_node_ids
            ),
            "evidence_packet_set_ref": partial_packet_set.content_digest,
            "code_fact_set_ref": fact_set.content_digest,
            "tool_call_trace_refs": [
                *list(state.get("tool_call_trace_refs", []) or []),
                *[_observation_ref(item) for item in compile_observations],
            ],
            "_partial_evidence": {
                "obligation_id": active_obligation_id,
                "packet_set": partial_packet_set,
                "fact_set": fact_set,
                "claim_set": partial_claim_set,
            },
        }
    aligned_fact_ids = {
        fact_id
        for alignment in target_alignments
        for fact_id in alignment.matched_fact_ids
    }
    required_group_count = sum(
        len(target.predicate_groups) if target.predicate_groups else len(target.desired_predicates)
        for target in active_obligation.typed_behavior_targets
    )
    if required_group_count > _COMPILE_FACT_LIMIT:
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )
    # Preserve every bounded fact that participated in target alignment.
    # Collapsing to one fact per predicate can discard the semantic witness
    # (for example ``input_dim=15``) and retain an unrelated READ fact with
    # the same predicate, leaving the final claim artifact unable to replay
    # the semantic authorization that succeeded above.
    aligned_facts = [
        fact
        for fact in sorted(fact_set.facts, key=lambda item: item.fact_id)
        if fact.fact_id in aligned_fact_ids
    ][:_COMPILE_FACT_LIMIT]
    supported_facts = [
        f for f in aligned_facts if f.validation_status == "supported"
    ]
    if not supported_facts:
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )

    # Build a single packet set carrying this packet so downstream writers
    # can consume the standard ``EvidencePacketSetV3`` shape.
    packet_set = EvidencePacketSetV3(
        producer_version=GENERIC_RESEARCH_PRODUCER_VERSION,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        packets=[packet],
        content_digest=packet.source_digest,
    )

    claim_proposals = _build_claim_proposals_for_facts(
        obligation_id=active_obligation_id,
        facts=fact_set.model_copy(update={"facts": aligned_facts}),
    )
    if not claim_proposals:
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )
    claim_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="decompose_atomic_claims",
        arguments={
            "fact_ids": tuple(
                fact_id
                for claim_proposal in claim_proposals
                for fact_id in claim_proposal.proposed_fact_ids
            ),
            "fact_set_id": proposal.packet_id,
            "claim_proposals": tuple(
                item.model_dump(mode="json") for item in claim_proposals
            ),
        },
    )
    compile_observations.append(claim_observation)
    if claim_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=claim_observation,
        )
    proposal_set_id = next(
        (
            note.split("=", 1)[1]
            for note in claim_observation.diagnostics.notes
            if note.startswith("proposal_set_id=")
        ),
        "",
    )
    if not proposal_set_id:
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=claim_observation.model_copy(
                update={
                    "status": "invalid_request",
                    "error_message": "claim proposal set id missing",
                }
            ),
        )
    authorize_observation = _execute_compile_data_plane_tool(
        ctx=tool_ctx,
        obligation_id=active_obligation_id,
        packet_id=proposal.packet_id,
        tool_name="authorize_atomic_claims",
        arguments={
            "claim_ids": tuple(item.claim_id for item in claim_proposals),
            "proposal_set_id": proposal_set_id,
        },
    )
    compile_observations.append(authorize_observation)
    if authorize_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=authorize_observation,
        )
    claim_payload = tool_ctx.read_artifact(
        "authorized_claim_sets", proposal_set_id
    )
    if claim_payload is None:
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=authorize_observation.model_copy(
                update={
                    "status": "invalid_request",
                    "error_message": "authorized claim artifact missing",
                }
            ),
        )
    claim_set = AtomicClaimSetV3.model_validate(claim_payload)
    if not claim_set.claims:
        # No claim was authorized: route to gap finalizer.
        return gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id=active_obligation_id,
            gain_tracker=gain_tracker,
        )

    # Authorization succeeded: mark the obligation as supported.
    authorized_claim_ids = [c.claim_id for c in claim_set.claims]
    active_obligation.supported_claim_ids = list(authorized_claim_ids)
    active_obligation.status = "supported"

    return {
        "evidence_packet_set_ref": packet_set.content_digest,
        "code_fact_set_ref": fact_set.content_digest,
        "atomic_claim_set_ref": claim_set.content_digest,
        "status": "researching",  # the obligation is terminal but the run continues
        "tool_call_trace_refs": [
            *list(state.get("tool_call_trace_refs", []) or []),
            *[_observation_ref(item) for item in compile_observations],
        ],
        # Private channel: the driver pops this and stashes the objects in
        # the loop state sidecar so the writer can consume them.
        "_compiled_evidence": {
            "obligation_id": active_obligation_id,
            "packet_set": packet_set,
            "fact_set": fact_set,
            "claim_set": claim_set,
        },
    }


def _target_semantic_requirements_for_search(
    target: TypedBehaviorTargetV1,
) -> dict[str, str]:
    values: dict[str, str] = {}
    role = target.role.strip()
    if role:
        values["role"] = role
    for field in ("inputs", "transformations", "decisions", "outputs"):
        items = getattr(target, field)
        if items:
            values[field] = " ".join(items)
    conditions = [
        value for value in target.conditions
        if value not in {"training", "inference", "any"}
    ]
    if conditions:
        values["conditions"] = " ".join(conditions)
    return values


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

    active_obligation = next(
        (
            item
            for item in runtime.agenda.items
            if item.obligation_id == active_obligation_id
        ),
        None,
    )
    if active_obligation is None:
        return {
            "status": "blocked",
            "blocked_reason": "gap_obligation_not_in_agenda",
            "_gap_accepted": False,
        }
    attempted_tools = tuple(
        sorted(
            {
                *gain_tracker.attempted_tools(active_obligation_id),
                *gap_search_attempts,
            }
        )
    )
    search_scope = tuple(
        dict.fromkeys(
            path
            for candidate in active_obligation.candidate_symbol_ids
            if (path := _extract_path_component(candidate))
        )
    )
    if not search_scope:
        search_scope = tuple(
            entry.path
            for entry in runtime.repo_snapshot.included_files
            if entry.kind == "file"
        )
    missing_relations = tuple(
        item.split(":", 1)[1]
        for item in active_obligation.missing_information
        if item.startswith("typed_relation:")
    )
    gap_observation = _execute_compile_data_plane_tool(
        ctx=runtime.tool_context(),
        obligation_id=active_obligation_id,
        packet_id="terminal-gap",
        tool_name="record_explicit_code_gap",
        arguments={
            "obligation_id_ref": active_obligation_id,
            "termination_reason": (
                f"No executable evidence satisfied the obligation after "
                f"{gain_tracker.no_progress_counter(active_obligation_id)} "
                "consecutive no-gain turns."
            ),
            "search_scope": search_scope,
            "attempted_tools": attempted_tools,
            "missing_relations": missing_relations,
            "search_complete": True,
            "scope_exhausted": bool(
                gain_tracker.exhausted_tools(active_obligation_id)
            ),
        },
    )
    if gap_observation.status != "success":
        return _compile_data_plane_failure(
            state=state,
            obligation=active_obligation,
            observation=gap_observation,
        ) | {"_gap_accepted": False}

    gap_ref = gap_observation.result_refs[0]
    existing_gaps = state.get("explicit_gap_set_ref", "")
    existing_gap_refs = tuple(
        ref for ref in str(existing_gaps).split(";") if ref
    )
    # The tool artifact is idempotent; keep the state sidecar idempotent too
    # when a resumed/replayed node receives the same terminal observation.
    new_gaps = (
        str(existing_gaps)
        if gap_ref in existing_gap_refs
        else f"{existing_gaps};{gap_ref}" if existing_gaps else gap_ref
    )

    # Mark the agenda item as terminal (explicit_gap).  Without this
    # mutation, ``_next_unresolved_obligation`` would keep selecting the
    # same obligation on wrap-around, causing the loop to spin until
    # ``max_turns`` even though the gap was accepted.  The model
    # validator on ``ResearchAgendaItemV1`` requires a non-empty
    # ``gap_requirements`` entry for ``explicit_gap`` status, so we
    # append a typed ``GapRequirementV1`` recording the exhaustive
    # search evidence.
    gap_requirement = GapRequirementV1(
        requirement_id=f"gap-req:{active_obligation_id}:{gap_ref}",
        description=(
            f"Exhaustive search for obligation {active_obligation_id} did not "
            f"yield sufficient executable evidence to compile a supported claim."
        ),
        # Preserve the actual frozen-source scope.  Recording the obligation
        # id here loses the provenance needed to audit an explicit gap.
        search_scope=",".join(search_scope) if search_scope else active_obligation_id,
        attempted_tools=attempted_tools,
        terminal="explicit_gap",
        rationale=(
            f"Accepted after {gain_tracker.no_progress_counter(active_obligation_id)} "
            f"consecutive no-gain turns."
        ),
    )
    if not any(
        requirement.requirement_id == gap_requirement.requirement_id
        for requirement in active_obligation.gap_requirements
    ):
        active_obligation.gap_requirements.append(gap_requirement)
    active_obligation.status = "explicit_gap"

    return {
        "explicit_gap_set_ref": new_gaps,
        "status": "researching",  # the obligation is terminal but the run continues
        "active_issue_id": "",
        "tool_call_trace_refs": [
            *list(state.get("tool_call_trace_refs", []) or []),
            _observation_ref(gap_observation),
        ],
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


def _empty_behavior_graph_digest(snapshot: RepoSnapshot, *, language: str = "python") -> str:
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        language=language,
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
    "compile_candidate_node",
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
