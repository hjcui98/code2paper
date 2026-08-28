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
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAgendaV1,
    ResearchAgendaItemV1,
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
    ExecutedToolCallSummaryV1,
    SupervisorBackend,
    build_decision_context,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.agentic.tool_runtime import atomic_write_bytes
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


def _supported_claim_statements(
    loop: "ResearchLoopState",
    obligation_id: str,
) -> tuple[str, ...]:
    """Project compiled evidence back into the Manager's semantic workspace."""

    compiled = loop.compiled_evidence.get(obligation_id)
    if compiled is None:
        return ()
    return tuple(
        dict.fromkeys(
            str(getattr(claim, "canonical_text", "") or "").strip()
            for claim in getattr(compiled.claim_set, "claims", ())
            if str(getattr(claim, "canonical_text", "") or "").strip()
        )
    )


def _executed_tool_call_summaries(
    loop: "ResearchLoopState",
    obligation_id: str,
) -> tuple[ExecutedToolCallSummaryV1, ...]:
    """Return exact prior calls, newest useful window.

    The window is assembled across obligations: a ``read_symbol`` /
    ``read_code_span`` / ``search`` executed while answering another
    obligation still tells the Manager that this code has already been
    inspected, so it must not re-read the same span.  The obligation id
    is carried so the model can distinguish a fresh search for a new
    story question from an exact re-read of code it already saw.

    Only executed calls (present in ``recent_tool_call_ids``) are shown;
    rejected proposals never appear.
    """

    summaries = [
        ExecutedToolCallSummaryV1(
            tool_name=call.tool_name,
            arguments=dict(call.arguments),
            path_scope=tuple(call.path_scope),
            goal=call.goal,
            obligation_id=decision.obligation_id,
        )
        for decision in loop.decision_trace
        for call in decision.selected_tool_calls
        if call.tool_call_id in loop.recent_tool_call_ids
    ]
    return tuple(summaries[-16:])


def _executed_read_signatures(loop: "ResearchLoopState") -> tuple[str, ...]:
    """Normalized keys of content reads already executed, across obligations.

    The policy layer rejects an exact re-read of a source span whose bytes
    were already returned in this snapshot, even when a different
    obligation is now active.  Building the set here (instead of in the
    supervisor node) keeps the decision context pure and lets unit tests
    construct the expected signatures directly.
    """

    from code2paper.agentic.research_policy import _content_read_signature

    signatures: list[str] = []
    seen: set[str] = set()
    for decision in loop.decision_trace:
        for call in decision.selected_tool_calls:
            if call.tool_call_id not in loop.recent_tool_call_ids:
                continue
            signature = _content_read_signature(call)
            if signature and signature not in seen:
                seen.add(signature)
                signatures.append(signature)
    return tuple(signatures)


def _store_evidence_sidecar(
    loop: "ResearchLoopState",
    payload: dict[str, Any],
) -> None:
    """Accumulate validated evidence without promoting partial facts to claims."""

    obligation_id = payload["obligation_id"]
    incoming = CompiledEvidence(
        obligation_id=obligation_id,
        packet_set=payload["packet_set"],
        fact_set=payload["fact_set"],
        claim_set=payload["claim_set"],
    )
    current = loop.compiled_evidence.get(obligation_id)
    if current is None:
        loop.compiled_evidence[obligation_id] = incoming
        return

    def unique(items: list[Any], identity: str) -> list[Any]:
        result: dict[str, Any] = {}
        for item in items:
            result.setdefault(str(getattr(item, identity)), item)
        return list(result.values())

    packets = unique(
        [*current.packet_set.packets, *incoming.packet_set.packets],
        "packet_id",
    )
    packet_digest = _sidecar_digest(
        [item.model_dump(mode="json") for item in packets]
    )
    packet_set = incoming.packet_set.model_copy(update={
        "packets": packets,
        "content_digest": packet_digest,
    })
    facts = unique(
        [*current.fact_set.facts, *incoming.fact_set.facts],
        "canonical_identity",
    )
    fact_digest = _sidecar_digest(
        [item.model_dump(mode="json") for item in facts]
    )
    fact_set = incoming.fact_set.model_copy(update={
        "facts": facts,
        "evidence_packet_digest": packet_digest,
        "content_digest": fact_digest,
    })
    claims = unique(
        [*current.claim_set.claims, *incoming.claim_set.claims],
        "canonical_identity",
    )
    gaps = unique(
        [
            *current.claim_set.explicit_code_gaps,
            *incoming.claim_set.explicit_code_gaps,
        ],
        "gap_id",
    )
    stage_groups = unique(
        [
            *current.claim_set.semantic_stage_groups,
            *incoming.claim_set.semantic_stage_groups,
        ],
        "stage_id",
    )
    claim_payload = {
        "claims": [item.model_dump(mode="json") for item in claims],
        "explicit_code_gaps": [item.model_dump(mode="json") for item in gaps],
        "semantic_stage_groups": [
            item.model_dump(mode="json") for item in stage_groups
        ],
    }
    claim_set = incoming.claim_set.model_copy(update={
        "claims": claims,
        "explicit_code_gaps": gaps,
        "semantic_stage_groups": stage_groups,
        "evidence_packet_digest": packet_digest,
        "code_fact_digest": fact_digest,
        "content_digest": _sidecar_digest(claim_payload),
    })
    loop.compiled_evidence[obligation_id] = CompiledEvidence(
        obligation_id=obligation_id,
        packet_set=packet_set,
        fact_set=fact_set,
        claim_set=claim_set,
    )


def _sidecar_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Phase 4: LoopStateSnapshot for cross-instance checkpoint/resume
# ---------------------------------------------------------------------------


class LoopStateSnapshot(BaseModel):
    """Serializable snapshot of ``ResearchLoopState`` for checkpoint/resume.

    The multi-node LangGraph topology holds the live
    ``CodeBehaviorGraphV1`` / ``InformationGainTracker`` /
    ``PerObligationBudgetV1`` in a non-serializable
    ``_ResearchGraphContext``.  Without an explicit snapshot channel,
    LangGraph's checkpointer would lose this state on cross-instance
    resume (e.g. process restart), forcing the loop to start over from
    the linear prefix.

    This model captures the checkpointable fields so a fresh context can
    rebuild the loop state via ``restore_loop_state_from_snapshot``.

    Non-checkpointable fields (``runtime``, ``recent_observations``,
    ``active_issue``, ``current_quality_state``, ``best_quality_state``,
    ``decision_trace``, ``policy_merge_trace``, ``compiled_evidence``)
    are intentionally omitted: they are either re-derived from the
    runtime, re-accumulated during the loop, or only consumed after the
    loop terminates (``compiled_evidence``).
    """

    model_config = ConfigDict(extra="forbid")

    snapshot_version: str = "2.0"
    immutable_payload_ref: str = ""
    immutable_payload_digest: str = ""
    # The fields below are retained only to read pre-D4 checkpoints.  New
    # snapshots leave every large inline field empty and persist the payload
    # in the immutable content-addressed store above.
    behavior_graph: dict[str, Any] = Field(default_factory=dict)
    agenda_items: list[dict[str, Any]] = Field(default_factory=list)
    gain_tracker: dict[str, Any] = Field(default_factory=dict)
    per_obligation_budgets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    turn_index: int = 0
    recent_tool_call_ids: list[str] = Field(default_factory=list)
    no_progress_tool_call_ids: list[str] = Field(default_factory=list)
    evidence_critic_route: str = ""
    terminated: bool = False
    termination_reason: str = ""
    recent_observations: list[dict[str, Any]] = Field(default_factory=list)
    active_issue: dict[str, Any] | None = None
    current_quality_state: dict[str, Any] = Field(default_factory=dict)
    best_quality_state: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)
    policy_merge_trace: list[dict[str, Any]] = Field(default_factory=list)
    compiled_evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def to_state_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for LangGraph state channels."""

        return self.model_dump(mode="json")


def snapshot_loop_state(loop: "ResearchLoopState") -> dict[str, Any]:
    """Serialize a ``ResearchLoopState`` into a ``loop_state_snapshot`` dict.

    Phase 4: called by the multi-node LangGraph topology after each turn
    so the checkpointer persists the loop state.  The snapshot is
    rebuilt into a live ``ResearchLoopState`` on resume via
    ``restore_loop_state_from_snapshot``.
    """

    immutable_payload = {
        "behavior_graph": loop.behavior_graph.model_dump(mode="json"),
        "agenda_items": [item.model_dump(mode="json") for item in loop.runtime.agenda.items],
        "gain_tracker": loop.gain_tracker.snapshot(),
        "recent_observations": [item.model_dump(mode="json") for item in loop.recent_observations],
        "active_issue": (loop.active_issue.model_dump(mode="json") if loop.active_issue else None),
        "current_quality_state": loop.current_quality_state.model_dump(mode="json"),
        "best_quality_state": loop.best_quality_state.model_dump(mode="json"),
        "decision_trace": [item.model_dump(mode="json") for item in loop.decision_trace],
        "policy_merge_trace": [item.model_dump(mode="json") for item in loop.policy_merge_trace],
        "compiled_evidence": {
            key: {
                "obligation_id": value.obligation_id,
                "packet_set": value.packet_set.model_dump(mode="json"),
                "fact_set": value.fact_set.model_dump(mode="json"),
                "claim_set": value.claim_set.model_dump(mode="json"),
            }
            for key, value in loop.compiled_evidence.items()
        },
    }
    payload_ref, payload_digest = _write_immutable_loop_payload(
        loop.runtime,
        immutable_payload,
    )
    snapshot = LoopStateSnapshot(
        immutable_payload_ref=payload_ref,
        immutable_payload_digest=payload_digest,
        per_obligation_budgets={
            obl_id: budget.model_dump(mode="json")
            for obl_id, budget in loop.per_obligation_budgets.items()
        },
        turn_index=loop.turn_index,
        recent_tool_call_ids=sorted(loop.recent_tool_call_ids),
        no_progress_tool_call_ids=sorted(loop.no_progress_tool_call_ids),
        evidence_critic_route=loop.evidence_critic_route,
        terminated=loop.terminated,
        termination_reason=loop.termination_reason,
    )
    return snapshot.to_state_dict()


def _checkpoint_store_root(runtime: "ResearchGraphRuntime") -> Path:
    artifact_root = runtime.artifact_root or runtime.tool_context().artifact_root
    return Path(artifact_root).resolve() / "immutable_checkpoints"


def _write_immutable_loop_payload(
    runtime: "ResearchGraphRuntime",
    payload: dict[str, Any],
) -> tuple[str, str]:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = "sha256:" + hashlib.sha256(encoded).hexdigest()
    root = _checkpoint_store_root(runtime)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{digest.removeprefix('sha256:')}.json"
    if not path.exists():
        # Content-addressed checkpoint payloads are immutable.  Use the same
        # fsync + replace boundary as every other research artifact so a
        # process crash cannot leave a partially-written JSON body at the
        # digest path.
        atomic_write_bytes(path, encoded + b"\n")
    return str(path), digest


def load_immutable_loop_payload(
    runtime: "ResearchGraphRuntime",
    snapshot_payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Load and authenticate a D4 snapshot payload without widening scope."""

    try:
        snapshot = LoopStateSnapshot.model_validate(snapshot_payload)
    except Exception:
        return None
    if not snapshot.immutable_payload_ref:
        # Backward-compatible read path for pre-D4 checkpoints only.
        return snapshot.model_dump(mode="json")
    root = _checkpoint_store_root(runtime)
    path = Path(snapshot.immutable_payload_ref).resolve()
    if path.parent != root or not path.is_file():
        return None
    encoded = path.read_bytes().rstrip(b"\n")
    actual = "sha256:" + hashlib.sha256(encoded).hexdigest()
    if actual != snapshot.immutable_payload_digest:
        return None
    try:
        payload = json.loads(encoded)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def restore_loop_state_from_snapshot(
    runtime: "ResearchGraphRuntime",
    snapshot_payload: dict[str, Any] | None,
    *,
    strict: bool = False,
) -> "ResearchLoopState | None":
    """Rebuild a ``ResearchLoopState`` from a ``loop_state_snapshot`` dict.

    Returns ``None`` when ``snapshot_payload`` is empty/invalid for the
    backwards-compatible inspection API.  Production resume callers pass
    ``strict=True``: a non-empty but invalid/tampered snapshot then raises
    instead of silently falling back to a fresh loop, which would erase the
    checkpoint's progress and violate fail-closed recovery.

    The rebuilt state carries the persisted behavior graph, gain tracker,
    budgets and tool-call id sets so the resumed loop continues from where it
    left off instead of restarting from the linear prefix.
    """

    if not isinstance(snapshot_payload, dict) or not snapshot_payload:
        if strict and snapshot_payload:
            raise ValueError("invalid_loop_state_snapshot:payload_not_mapping")
        return None
    try:
        snapshot = LoopStateSnapshot.model_validate(snapshot_payload)
    except Exception as exc:  # noqa: BLE001 — compatibility API remains fail-soft
        if strict:
            raise ValueError("invalid_loop_state_snapshot:schema") from exc
        return None
    immutable = load_immutable_loop_payload(runtime, snapshot_payload)
    if immutable is None:
        if strict:
            raise ValueError("invalid_loop_state_snapshot:immutable_payload")
        return None
    loop = initial_loop_state(runtime)
    agenda_items = immutable.get("agenda_items") or snapshot.agenda_items
    if agenda_items:
        restored_items: list[ResearchAgendaItemV1] = []
        for payload in agenda_items:
            try:
                restored_items.append(ResearchAgendaItemV1.model_validate(payload))
            except Exception as exc:
                if strict:
                    raise ValueError("invalid_loop_state_snapshot:agenda_items") from exc
                pass
        if restored_items:
            runtime.agenda.items[:] = restored_items
    behavior_graph = immutable.get("behavior_graph") or snapshot.behavior_graph
    if behavior_graph:
        try:
            loop.behavior_graph = CodeBehaviorGraphV1.model_validate(
                behavior_graph
            )
        except Exception as exc:  # noqa: BLE001 — compatibility API keeps fresh graph
            if strict:
                raise ValueError("invalid_loop_state_snapshot:behavior_graph") from exc
            pass
    from code2paper.agentic.research_nodes import InformationGainTracker

    loop.gain_tracker = InformationGainTracker.from_snapshot(
        immutable.get("gain_tracker") or snapshot.gain_tracker
    )
    if snapshot.per_obligation_budgets:
        restored_budgets: dict[str, PerObligationBudgetV1] = {}
        for obl_id, payload in snapshot.per_obligation_budgets.items():
            try:
                restored_budgets[obl_id] = PerObligationBudgetV1.model_validate(payload)
            except Exception as exc:  # noqa: BLE001 — compatibility API keeps seeded budget
                if strict:
                    raise ValueError(f"invalid_loop_state_snapshot:budget:{obl_id}") from exc
                pass
        if restored_budgets:
            loop.per_obligation_budgets = restored_budgets
    loop.turn_index = int(snapshot.turn_index)
    loop.recent_tool_call_ids = set(snapshot.recent_tool_call_ids)
    loop.no_progress_tool_call_ids = set(snapshot.no_progress_tool_call_ids)
    loop.evidence_critic_route = snapshot.evidence_critic_route
    loop.terminated = bool(snapshot.terminated)
    loop.termination_reason = snapshot.termination_reason
    loop.recent_observations = [
        ResearchObservationV1.model_validate(payload)
        for payload in (immutable.get("recent_observations") or snapshot.recent_observations)
    ]
    active_issue = immutable.get("active_issue") or snapshot.active_issue
    if active_issue:
        loop.active_issue = ResearchIssueV1.model_validate(active_issue)
    quality_type = type(loop.current_quality_state)
    current_quality = immutable.get("current_quality_state") or snapshot.current_quality_state
    best_quality = immutable.get("best_quality_state") or snapshot.best_quality_state
    if current_quality:
        loop.current_quality_state = quality_type.model_validate(current_quality)
    if best_quality:
        loop.best_quality_state = quality_type.model_validate(best_quality)
    loop.decision_trace = [
        ResearchDecisionV1.model_validate(payload)
        for payload in (immutable.get("decision_trace") or snapshot.decision_trace)
    ]
    loop.policy_merge_trace = [
        PolicyMergeResult.model_validate(payload)
        for payload in (immutable.get("policy_merge_trace") or snapshot.policy_merge_trace)
    ]
    compiled_evidence = immutable.get("compiled_evidence") or snapshot.compiled_evidence
    if compiled_evidence:
        from code2paper.agentic.evidence_compiler_v3 import (
            AtomicClaimSetV3,
            CodeFactSetV1,
            EvidencePacketSetV3,
        )
        for key, payload in compiled_evidence.items():
            try:
                loop.compiled_evidence[key] = CompiledEvidence(
                    obligation_id=str(payload["obligation_id"]),
                    packet_set=EvidencePacketSetV3.model_validate(payload["packet_set"]),
                    fact_set=CodeFactSetV1.model_validate(payload["fact_set"]),
                    claim_set=AtomicClaimSetV3.model_validate(payload["claim_set"]),
                )
            except Exception as exc:
                if strict:
                    raise ValueError(f"invalid_loop_state_snapshot:compiled_evidence:{key}") from exc
                pass
    return loop


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
        language=runtime.language_adapter().language,
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
    # Phase 2.5: formal node execution trace.  Each entry is a dict
    # with keys: node, timestamp, duration_ms, turn_index, status,
    # route, error.  Populated by the _wrap_with_trace helper in
    # build_research_subgraph; empty for runs that bypass LangGraph
    # (e.g. direct ResearchLoopDriver calls in unit tests).
    node_trace: list[dict[str, Any]] = field(default_factory=list)


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
            restored = restore_loop_state_from_snapshot(
                runtime,
                state.get("loop_state_snapshot") if isinstance(state, dict) else None,
                strict=True,
            )
            loop = restored or initial_loop_state(runtime)

        # A content-authenticated terminal snapshot is a completed execution,
        # not a hint to rerun the prefix.  Validate identity and return before
        # the Intent/Supervisor backends (and therefore before any model call).
        if loop.terminated:
            _validate_terminal_resume(runtime=runtime, state=state, loop=loop)
            return ResearchLoopResult(
                loop_state=loop,
                final_state=state,
                turns_executed=0,
                terminated=True,
                termination_reason=loop.termination_reason,
                decision_trace=loop.decision_trace,
                policy_merge_trace=loop.policy_merge_trace,
                evidence_critic_routes=[],
            )

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
                executed_read_signatures=_executed_read_signatures(loop),
                turn_index=loop.turn_index,
                current_supported_claim_ids=tuple(
                    _supported_claim_ids(runtime.agenda, active_obligation_id)
                ),
                current_supported_claim_statements=_supported_claim_statements(
                    loop, active_obligation_id
                ),
                executed_tool_calls=_executed_tool_call_summaries(
                    loop, active_obligation_id
                ),
                behavior_graph=loop.behavior_graph,
            )
            # Pop the private channel BEFORE state.update so the real
            # merged decision (with ``produced_by`` / ``rationale`` /
            # ``goal`` from the supervisor backend) is preserved in the
            # decision trace.  Falling back to ``_reconstruct_decision``
            # would overwrite ``produced_by`` to ``deterministic_fallback``
            # and hide LLM proposals from the R8 acceptance check.
            merged_decision = supervisor_update.pop("_merged_decision", None)
            merge_results = supervisor_update.pop("_policy_merge_results", [])
            state.update(supervisor_update)

            # Policy merge is pure.  Apply the accepted calls to the live
            # per-obligation budget before the next model turn; previously
            # the deltas were only traced, so an Agent could call the same
            # tool kind indefinitely until the unrelated global turn cap.
            for merge_result in merge_results:
                loop.per_obligation_budgets = apply_consumed_budgets(
                    loop.per_obligation_budgets,
                    merge_result.consumed_budgets,
                )
            loop.policy_merge_trace.extend(merge_results)

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
            if decision.action == "COMPILE_EVIDENCE":
                compile_update = compile_candidate_node(
                    state,
                    runtime=runtime,
                    behavior_graph=loop.behavior_graph,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                )
                compiled_evidence = compile_update.pop("_compiled_evidence", None)
                partial_evidence = compile_update.pop("_partial_evidence", None)
                gap_accepted = compile_update.pop("_gap_accepted", None)
                state.update(compile_update)
                if partial_evidence is not None:
                    _store_evidence_sidecar(loop, partial_evidence)
                if compiled_evidence is not None:
                    _store_evidence_sidecar(loop, compiled_evidence)
                if state.get("status") == "blocked":
                    terminated = True
                    termination_reason = "evidence_compile_blocked"
                    break
                if compiled_evidence is not None or gap_accepted is True:
                    next_obl = _next_unresolved_obligation(
                        runtime.agenda, active_obligation_id
                    )
                    if next_obl is None:
                        terminated = True
                        termination_reason = "all_obligations_terminal"
                        state["status"] = "trusted"
                        break
                    state["active_obligation_id"] = next_obl
                    loop.active_issue = None
                    loop.recent_observations.clear()
                elif partial_evidence is not None:
                    next_obl = _next_unresolved_obligation(
                        runtime.agenda, active_obligation_id
                    )
                    if next_obl is None:
                        # Every obligation is terminal (supported / partial
                        # with nothing left to research / gap / blocked):
                        # ``partial`` with no actionable missing information
                        # is a terminal status (design 8.4).  Re-entering the
                        # supervisor would only repeat exact calls until
                        # fallback exhaustion.
                        terminated = True
                        termination_reason = "all_obligations_terminal"
                        state["status"] = "trusted"
                        break
                    if next_obl != active_obligation_id:
                        state["active_obligation_id"] = next_obl
                        loop.active_issue = None
                        loop.recent_observations.clear()
                turns_executed += 1
                loop.turn_index += 1
                routes.append("manager_compile")
                continue
            if decision.action == "RECORD_GAP":
                # ``partial`` is a terminal per-obligation status (design
                # 8.4: "可写边界与 required qualifier 明确").  An obligation
                # whose claims were already authorized must never be routed
                # to the gap finalizer: the record-gap tool rejects
                # ``gap_contradicts_authorized_positive_claim`` fail-closed,
                # and re-entering the supervisor would only repeat exact
                # calls until fallback exhaustion.  Advance (or terminate)
                # the partial obligation directly.
                if _active_obligation_partial(runtime.agenda, active_obligation_id):
                    next_obl = _next_unresolved_obligation(
                        runtime.agenda, active_obligation_id
                    )
                    if next_obl is None or next_obl == active_obligation_id:
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
            observations, trace_refs = execute_pending_tool_calls(
                runtime,
                pending,
                behavior_graph=loop.behavior_graph,
            )
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
                partial_evidence = compile_update.pop("_partial_evidence", None)
                gap_accepted = compile_update.pop("_gap_accepted", None)
                state.update(compile_update)
                if partial_evidence is not None:
                    _store_evidence_sidecar(loop, partial_evidence)
                if compiled_evidence is not None:
                    _store_evidence_sidecar(loop, compiled_evidence)
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
                if partial_evidence is not None:
                    # Validated facts were retained. Give the next open
                    # story question a breadth pass before revisiting this
                    # partially answered obligation.  When nothing non-terminal
                    # remains, ``partial`` with no actionable missing info is a
                    # terminal status (design 8.4): terminate instead of
                    # re-entering the supervisor with only exact repeats.
                    next_obl = _next_unresolved_obligation(
                        runtime.agenda,
                        active_obligation_id,
                    )
                    if next_obl is None:
                        terminated = True
                        termination_reason = "all_obligations_terminal"
                        state["status"] = "trusted"
                        break
                    if next_obl != active_obligation_id:
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

        loop.terminated = terminated
        loop.termination_reason = termination_reason

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


def _validate_terminal_resume(
    *,
    runtime: ResearchGraphRuntime,
    state: AgentStateV3,
    loop: "ResearchLoopState",
) -> None:
    if state.get("run_id") != runtime.run_id:
        raise ValueError("terminal_resume_run_id_mismatch")
    if state.get("repo_snapshot_id") != runtime.repo_snapshot.snapshot_id:
        raise ValueError("terminal_resume_snapshot_id_mismatch")
    if state.get("project_tree_hash") != runtime.repo_snapshot.project_tree_hash:
        raise ValueError("terminal_resume_project_tree_hash_mismatch")
    if not loop.termination_reason:
        raise ValueError("terminal_resume_reason_missing")
    if state.get("status") not in {"trusted", "incomplete", "blocked"}:
        raise ValueError("terminal_resume_status_not_terminal")


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
        # Phase 2.5: formal node execution trace.  Each entry is a
        # dict with keys: node, timestamp, duration_ms, turn_index,
        # status, route, error.  Populated by _wrap_with_trace.
        self.node_trace: list[dict[str, Any]] = []


def _ensure_ctx_loop(
    state: AgentStateV3,
    ctx: _ResearchGraphContext,
) -> ResearchLoopState:
    """Lazily restore closure state when LangGraph resumes past the prefix."""

    if ctx.loop_state is None:
        payload = state.get("loop_state_snapshot") if isinstance(state, dict) else None
        restored = restore_loop_state_from_snapshot(ctx.runtime, payload, strict=True)
        ctx.loop_state = restored or initial_loop_state(ctx.runtime)
        if restored is not None:
            ctx.turns_executed = restored.turn_index
    return ctx.loop_state


def _ctx_linear_prefix(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run the 4 linear prefix nodes and initialize the loop state.

    Phase 4: when ``state`` carries a ``loop_state_snapshot`` (from a
    prior checkpoint), the loop state is rebuilt from the snapshot so
    cross-instance resume preserves the accumulated behavior graph,
    gain tracker, per-obligation budgets and tool-call id sets.  When
    no snapshot is present, a fresh loop state is seeded from the
    runtime (existing behavior).
    """

    runtime = ctx.runtime
    if ctx.loop_state is None:
        snapshot_payload = state.get("loop_state_snapshot") if isinstance(state, dict) else None
        restored = restore_loop_state_from_snapshot(runtime, snapshot_payload, strict=True)
        ctx.loop_state = restored or initial_loop_state(runtime)
        if restored is not None:
            ctx.turns_executed = restored.turn_index
    update: dict[str, Any] = {}
    update.update(input_resolution_node(state, runtime=runtime))
    update.update(intent_compiler_node(state, runtime=runtime))
    update.update(repository_indexer_node(state, runtime=runtime))
    update.update(research_agenda_builder_node(state, runtime=runtime))
    # Re-emit the snapshot so the checkpointer persists the restored
    # state even when the linear prefix did not mutate it this turn.
    if ctx.loop_state is not None:
        update["loop_state_snapshot"] = snapshot_loop_state(ctx.loop_state)
    return update


def _ctx_supervisor(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run the supervisor and set the routing decision."""

    runtime = ctx.runtime
    loop = _ensure_ctx_loop(state, ctx)

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
        executed_read_signatures=_executed_read_signatures(loop),
        turn_index=loop.turn_index,
        current_supported_claim_ids=tuple(
            _supported_claim_ids(runtime.agenda, active_obligation_id)
        ),
        current_supported_claim_statements=_supported_claim_statements(
            loop, active_obligation_id
        ),
        executed_tool_calls=_executed_tool_call_summaries(
            loop, active_obligation_id
        ),
        behavior_graph=loop.behavior_graph,
        # Same fail-closed exhaustiveness condition the gap finalizer uses:
        # a second-level RECORD_GAP fallback is only proposed when the
        # obligation may record a gap (no-progress threshold met or targeted
        # search exhausted).  Without the gate, a rejected fallback would
        # emit RECORD_GAP the finalizer rejects, routing straight back to the
        # same doomed proposal (churn loop).
        gap_justified=(
            loop.gain_tracker.may_record_gap(active_obligation_id)
            or loop.gain_tracker.targeted_search_exhausted(active_obligation_id)
        ),
    )
    merged_decision = supervisor_update.pop("_merged_decision", None)
    merge_results = supervisor_update.pop("_policy_merge_results", [])
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
    loop.policy_merge_trace.extend(merge_results)
    for merge_result in merge_results:
        loop.per_obligation_budgets = apply_consumed_budgets(
            loop.per_obligation_budgets,
            merge_result.consumed_budgets,
        )

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
        # A partial obligation (claims already authorized) must never be
        # routed to the gap finalizer: the record-gap tool rejects
        # ``gap_contradicts_authorized_positive_claim`` fail-closed and the
        # loop would churn RECORD_GAP until max_turns.  Route it to the
        # advancer, which terminates when every obligation is terminal
        # (``partial`` with no actionable missing info is terminal per
        # design 8.4).
        if _active_obligation_partial(runtime.agenda, active_obligation_id):
            ctx.supervisor_route = "partial_gap"
            return supervisor_update
        ctx.supervisor_route = "record_gap"
        return supervisor_update
    if decision.action == "COMPILE_EVIDENCE":
        ctx.supervisor_route = "compile_evidence"
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
    loop = _ensure_ctx_loop(state, ctx)
    pending = ctx._pending or list(state.get("pending_tool_calls", []) or [])
    observations, trace_refs = execute_pending_tool_calls(
        runtime,
        pending,
        behavior_graph=loop.behavior_graph,
    )
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
    loop = _ensure_ctx_loop(state, ctx)
    active_obligation_id = state.get("active_obligation_id", "")
    observations = tuple(ctx._observations)
    if not observations:
        # On cross-instance resume at observation_pipeline, the tool node's
        # closure-local buffer is gone but its observations are in snapshot.
        observations = tuple(
            item
            for item in loop.recent_observations
            if item.obligation_id == active_obligation_id
        )

    update: dict[str, Any] = {}
    ingest_update = observation_ingest_node(
        state,
        runtime=runtime,
        observations=observations,
        gain_tracker=loop.gain_tracker,
        active_obligation_id=active_obligation_id,
    )
    update.update(ingest_update)

    # Nodes in this composite pipeline share one logical turn.  Feed the
    # freshly ingested candidate lists to the behavior-graph updater instead
    # of the pre-turn state; otherwise a model-selected read may not become
    # compilable until an unrelated later call.
    observation_state = dict(state)
    observation_state.update(ingest_update)

    _track_no_progress_calls(loop, observations, active_obligation_id)

    loop.behavior_graph, bg_update = behavior_graph_updater_node(
        observation_state,
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

    # Phase 4: persist the loop state snapshot so cross-instance
    # checkpoint/resume can rebuild the behavior graph, gain tracker
    # and per-obligation budgets.  Emitting the snapshot on every
    # observation pipeline turn keeps the checkpointer in sync with
    # the non-serializable loop state held in the context closure.
    update["loop_state_snapshot"] = snapshot_loop_state(loop)
    return update


def _ctx_critic(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> dict[str, Any]:
    """Run evidence_critic and set the routing decision."""

    runtime = ctx.runtime
    loop = _ensure_ctx_loop(state, ctx)
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
    loop = _ensure_ctx_loop(state, ctx)
    active_obligation_id = state.get("active_obligation_id", "")

    compile_update = compile_candidate_node(
        state,
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        active_obligation_id=active_obligation_id,
        gain_tracker=loop.gain_tracker,
    )
    compiled_evidence = compile_update.pop("_compiled_evidence", None)
    partial_evidence = compile_update.pop("_partial_evidence", None)
    gap_accepted = compile_update.pop("_gap_accepted", None)

    if partial_evidence is not None:
        _store_evidence_sidecar(loop, partial_evidence)
    if compiled_evidence is not None:
        _store_evidence_sidecar(loop, compiled_evidence)
        # Success: route to advancer.  The advancer increments
        # turns_executed only when a next obligation exists.
        ctx.compile_route = "compiled"
        return compile_update
    if partial_evidence is not None:
        # The advancer performs the round-robin move and accounting.
        ctx.compile_route = "partial"
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
    loop = _ensure_ctx_loop(state, ctx)
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
    loop = _ensure_ctx_loop(state, ctx)
    active_obligation_id = state.get("active_obligation_id", "")

    next_obl = _next_unresolved_obligation(runtime.agenda, active_obligation_id)
    if next_obl is None or (
        # The supervisor exhausted every strategy for a partial obligation
        # (RECORD_GAP decision routed as ``partial_gap``): the round-robin
        # returning the same obligation is not a fresh depth pass, it is the
        # same dead end.  ``partial`` with claims is a terminal status
        # (design 8.4) once no further strategy exists.
        next_obl == active_obligation_id
        and _active_obligation_partial(runtime.agenda, active_obligation_id)
        and getattr(ctx, "supervisor_route", "") == "partial_gap"
    ):
        ctx.terminated = True
        ctx.termination_reason = "all_obligations_terminal"
        ctx.advancer_route = "no_next"
        return {"status": "trusted"}

    ctx.advancer_route = "has_next"
    ctx.turns_executed += 1
    loop.turn_index += 1
    loop.active_issue = None
    # A partial compile of the only/current obligation is not a context
    # switch.  Preserve the exact source observation so the next Manager turn
    # can reason about it.  Clear only when advancing to another question.
    if next_obl != active_obligation_id:
        loop.recent_observations.clear()
    return {"active_obligation_id": next_obl}


def _ctx_terminate(
    state: AgentStateV3,
    *,
    ctx: _ResearchGraphContext,
) -> "ResearchLoopResult":
    """Build the final ``ResearchLoopResult``."""

    loop = _ensure_ctx_loop(state, ctx)
    if not ctx.terminated:
        ctx.termination_reason = ctx.termination_reason or "max_turns_reached"
    # Phase 6 fix: propagate ``ctx.terminated`` / ``ctx.termination_reason``
    # to ``loop_state`` so consumers reading ``result.loop_state.terminated``
    # see the correct value (previously only ``ctx.terminated`` was set,
    # leaving ``loop_state.terminated`` stuck at False).
    loop.terminated = ctx.terminated
    loop.termination_reason = ctx.termination_reason
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
        node_trace=list(ctx.node_trace),
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
        """Final node: builds and stashes the ``ResearchLoopResult``.

        Phase 6 fix: the terminator node records its own trace entry
        BEFORE calling ``_ctx_terminate`` so the entry appears in
        ``result.node_trace``.  The generic ``_wrap_with_trace`` wrapper
        would record the trace only AFTER ``_ctx_terminate`` returns,
        which is too late — ``_ctx_terminate`` copies
        ``ctx.node_trace`` into the ``ResearchLoopResult`` before the
        wrapper has a chance to append the terminator entry.  By
        recording the entry here (with ``duration_ms=0``) we ensure
        the terminator node appears in the formal node execution trace
        that the R8 acceptance checker verifies.
        """

        from datetime import datetime, timezone

        ctx.node_trace.append({
            "node": "terminator",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0.0,
            "turn_index": ctx.turns_executed,
            "status": "ok",
            "route": "",
            "error": "",
        })
        result = _ctx_terminate(state, ctx=ctx)
        holder.result = result
        merged: dict[str, Any] = dict(state)
        merged.update(result.final_state)
        return merged  # type: ignore[return-value]

    # --- trace wrapper (Phase 2.5) --------------------------------------
    def _wrap_with_trace(
        node_name: str,
        fn: Callable[[AgentStateV3], AgentStateV3],
    ) -> Callable[[AgentStateV3], AgentStateV3]:
        """Wrap a node function to record a formal execution trace entry.

        Each trace entry is a dict with keys:
        - ``node``: the node name
        - ``timestamp``: ISO 8601 UTC timestamp
        - ``duration_ms``: wall-clock duration in milliseconds
        - ``turn_index``: the current turn index from ``ctx.turns_executed``
        - ``status``: ``"ok"`` on success, ``"error"`` on exception
        - ``route``: the routing decision after this node (empty for
          non-routing nodes; populated by the next router call)
        - ``error``: empty on success, ``"Type: message"`` on exception

        The trace is stored in ``ctx.node_trace`` and copied into the
        ``ResearchLoopResult`` by ``_ctx_terminate``.
        """

        def wrapper(state: AgentStateV3) -> AgentStateV3:
            start = time.monotonic()
            ts = datetime.now(timezone.utc).isoformat()
            turn = ctx.turns_executed
            try:
                result = fn(state)
                if ctx.loop_state is not None and isinstance(result, dict):
                    # Persist after every node, including compile/gap/advance;
                    # observation-only snapshots lose terminal agenda state
                    # and compiled evidence when interruption happens later.
                    result["loop_state_snapshot"] = snapshot_loop_state(ctx.loop_state)
                duration_ms = (time.monotonic() - start) * 1000.0
                ctx.node_trace.append({
                    "node": node_name,
                    "timestamp": ts,
                    "duration_ms": round(duration_ms, 3),
                    "turn_index": turn,
                    "status": "ok",
                    "route": "",
                    "error": "",
                })
                return result
            except Exception as exc:
                duration_ms = (time.monotonic() - start) * 1000.0
                ctx.node_trace.append({
                    "node": node_name,
                    "timestamp": ts,
                    "duration_ms": round(duration_ms, 3),
                    "turn_index": turn,
                    "status": "error",
                    "route": "",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                raise

        return wrapper

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
    # Phase 2.5: wrap every node with _wrap_with_trace so each
    # execution is recorded in ctx.node_trace and surfaced in the
    # ResearchLoopResult for R8 verification.
    graph.add_node("linear_prefix", _wrap_with_trace("linear_prefix", _linear_prefix_node))
    graph.add_node("research_supervisor", _wrap_with_trace("research_supervisor", _supervisor_node))
    graph.add_node("research_tool", _wrap_with_trace("research_tool", _tool_node))
    graph.add_node("observation_pipeline", _wrap_with_trace("observation_pipeline", _observation_node))
    graph.add_node("evidence_critic", _wrap_with_trace("evidence_critic", _critic_node))
    graph.add_node("compile_candidate", _wrap_with_trace("compile_candidate", _compile_node))
    graph.add_node("gap_finalizer", _wrap_with_trace("gap_finalizer", _gap_node))
    graph.add_node("obligation_advancer", _wrap_with_trace("obligation_advancer", _advancer_node))
    graph.add_node("terminator", _wrap_with_trace("terminator", _terminator_node))

    graph.add_edge(START, "linear_prefix")
    graph.add_edge("linear_prefix", "research_supervisor")

    graph.add_conditional_edges(
        "research_supervisor",
        _supervisor_router,
        {
            "stop_blocked": "terminator",
            "record_gap": "gap_finalizer",
            "partial_gap": "obligation_advancer",
            "compile_evidence": "compile_candidate",
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
            "partial": "obligation_advancer",
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


def _obligation_is_terminal(item: Any) -> bool:
    """Whether an obligation needs no further research.

    ``supported`` / ``explicit_gap`` / ``blocked`` are terminal by design
    (8.4).  A ``partial`` obligation is terminal only when nothing remains
    to research (no missing information): claims are authorized and the
    writing boundary plus required qualifiers are clear.  A partial
    obligation that still lists missing information is revisitable -- the
    supervisor may still have a fresh strategy for it (e.g. a call trace
    for an unresolved ``call_relation``).
    """

    if item.status in {"supported", "explicit_gap", "blocked"}:
        return True
    if item.status == "partial":
        actionable = [
            value
            for value in (item.missing_information or ())
            if not value.startswith("candidate_path:")
            and not value.startswith("tool_data_plane:")
        ]
        return not actionable
    return False


def _is_organization_preference(item: Any) -> bool:
    """Author story-order headings are not code-search obligations."""

    if str(getattr(item, "priority", "") or "") != "preference":
        return False
    return "ORGANIZATION" in str(getattr(item, "obligation_id", "") or "").upper()


def _has_unresolved_must_cover(agenda: ResearchAgendaV1) -> bool:
    return any(
        item.priority == "must_cover" and not _obligation_is_terminal(item)
        for item in agenda.items
    )


def _obligation_is_researchable_now(
    item: Any,
    *,
    defer_organization_preference: bool,
) -> bool:
    if _obligation_is_terminal(item):
        return False
    if defer_organization_preference and _is_organization_preference(item):
        return False
    return True


def _next_unresolved_obligation(
    agenda: ResearchAgendaV1, current_id: str
) -> str | None:
    """Round-robin unresolved obligations instead of starving later sections.

    Author method stories commonly start with a broad overview obligation.
    Requiring that one item to close before touching feature extraction,
    training, or inference let it consume the whole global turn budget.  A
    partial item with unresolved missing information is therefore
    revisitable, not terminal: breadth across the story spine happens
    before another depth pass over the same question.  A partial item with
    nothing left to research is terminal (design 8.4).

    Organization ``preference`` nodes (paper story order) stay off the
    must-cover search rotation until every unresolved must-cover item has
    had a research turn.  They remain visible as review/candidate spine
    items; they do not consume the code-search budget.
    """

    items = agenda.items
    defer_org = _has_unresolved_must_cover(agenda)
    started = False
    # First move forward in story/agenda order regardless of priority.  The
    # old must-cover-first second pass let a broad overview starve every
    # should-cover stage that actually contained the method mechanics.
    for item in items:
        if not started:
            if item.obligation_id == current_id:
                started = True
            continue
        if _obligation_is_researchable_now(
            item, defer_organization_preference=defer_org
        ):
            return item.obligation_id
    # Wrap around after every later question has had a breadth pass, with
    # must-cover items taking precedence on the next cycle.
    for item in items:
        if item.priority == "must_cover" and not _obligation_is_terminal(item):
            return item.obligation_id
    # Fall back to any unresolved obligation, still skipping organization
    # preference while must-cover search remains open.
    for item in items:
        if _obligation_is_researchable_now(
            item, defer_organization_preference=defer_org
        ):
            return item.obligation_id
    for item in items:
        if not _obligation_is_terminal(item):
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

    for obs in observations:
        if obs.obligation_id != active_obligation_id:
            continue
        if loop.gain_tracker.last_call_gained(obs.tool_call_id) is False:
            loop.no_progress_tool_call_ids.add(obs.tool_call_id)


__all__ = [
    "CompiledEvidence",
    "CompiledResearchSubgraph",
    "LoopStateSnapshot",
    "ResearchLoopDriver",
    "ResearchLoopResult",
    "ResearchLoopState",
    "build_research_subgraph",
    "initial_loop_state",
    "restore_loop_state_from_snapshot",
    "run_research_loop",
    "snapshot_loop_state",
]


def _active_obligation_partial(
    agenda: ResearchAgendaV1, active_obligation_id: str
) -> bool:
    """Whether the active obligation is terminal-``partial`` (claims owned)."""

    for item in agenda.items:
        if item.obligation_id == active_obligation_id:
            return bool(item.status == "partial" and item.supported_claim_ids)
    return False
