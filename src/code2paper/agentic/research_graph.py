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
from typing import Any, Callable, Iterator, Mapping, Sequence

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1, SymbolIndexV2
from code2paper.agentic.research_models import (
    CandidateAcquisitionLedgerV1,
    CompileAttemptResultV1,
    GlobalSafetyBudgetV1,
    ImplementationScopeV1,
    PerObligationBudgetV1,
    ResearchAction,
    ResearchAgendaV1,
    ResearchAgendaItemV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    QualityContentDimensionsV1,
    QualityCostDimensionsV1,
    QualityMinimalityDimensionsV1,
    QualitySafetyDimensionsV1,
    QualityStateV2,
    empty_quality_state,
)
from code2paper.agentic.intent_ledger import (
    IntentCoverageScheduler,
    IntentImplementationLedgerV1,
    build_intent_implementation_ledger,
)
from code2paper.agentic.implementation_scope import (
    build_candidate_acquisition_ledger,
    infer_implementation_scope,
    seed_child_candidates_from_parents,
)
from code2paper.agentic.research_promotion import (
    build_observation_promotion_ledger,
    promotion_record_blocks_strict_research,
)
from code2paper.agentic.research_revision_contract import RevisionJournalV1
from code2paper.agentic.research_revision_ingest import (
    DEFAULT_REVISION_PROPOSAL_BUDGET,
    REVISION_PROPOSAL_TOOL_NAME,
)
from code2paper.agentic.research_terminal import (
    CandidateHandoffV1,
    ObligationTerminalProofV1,
    build_candidate_handoff,
    evaluate_obligation_terminal_proof,
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
from code2paper.agentic.source_inventory import (
    RepositorySourceManifestV1,
    build_repository_source_manifest,
)
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
    """Obligation-scoped analysis keys of content reads already executed.

    R4: the no-gain rule is per obligation.  The byte identity is still the
    cache key for reusing snapshot-identical source, but a different
    obligation may read the same span again for its own graph/claim
    compilation; only the same obligation re-reading the same span is a
    duplicate.  Building the set here (instead of in the supervisor node)
    keeps the decision context pure and lets unit tests construct the
    expected signatures directly.
    """

    from code2paper.agentic.research_policy import _obligation_read_signature

    signatures: list[str] = []
    seen: set[str] = set()
    for decision in loop.decision_trace:
        for call in decision.selected_tool_calls:
            if call.tool_call_id not in loop.recent_tool_call_ids:
                continue
            signature = _obligation_read_signature(call)
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


def _record_intent_compile_event(
    loop: "ResearchLoopState",
    payload: dict[str, Any] | None,
) -> None:
    """Record information gain at every compile boundary.

    The intent scheduler must be able to distinguish a real promotion from a
    repeated ``COMPILE_EVIDENCE`` route.  Counts are computed from the
    canonical packet/fact objects and never from a claimed status string.
    """

    if payload is None:
        loop.intent_compile_events.append({
            "new_spans_count": 0,
            "new_facts_count": 0,
            "new_claims_count": 0,
            "new_typed_slots_count": 0,
            "new_operations_count": 0,
            "has_coverage_gain": False,
        })
        return
    obligation_id = str(payload.get("obligation_id") or "")
    current = loop.compiled_evidence.get(obligation_id)
    old_fact_ids = {
        str(getattr(item, "fact_id", ""))
        for item in (getattr(getattr(current, "fact_set", None), "facts", ()) or ())
        if str(getattr(item, "fact_id", ""))
    }
    old_span_ids = {
        str(getattr(span, "span_id", ""))
        for packet in (getattr(getattr(current, "packet_set", None), "packets", ()) or ())
        for span in (getattr(packet, "spans", ()) or ())
        if str(getattr(span, "span_id", ""))
    }
    old_claim_ids = {
        str(getattr(claim, "claim_id", ""))
        for claim in (getattr(getattr(current, "claim_set", None), "claims", ()) or ())
        if str(getattr(claim, "claim_id", ""))
    }
    fact_ids = {
        str(getattr(item, "fact_id", ""))
        for item in (getattr(getattr(payload, "fact_set", None), "facts", ()) or ())
        if str(getattr(item, "fact_id", ""))
    }
    packet_spans = {
        str(getattr(span, "span_id", ""))
        for packet in (getattr(getattr(payload, "packet_set", None), "packets", ()) or ())
        for span in (getattr(packet, "spans", ()) or ())
        if str(getattr(span, "span_id", ""))
    }
    # ``payload`` is a dict but its evidence values are model objects.
    if not fact_ids:
        fact_set = payload.get("fact_set")
        fact_ids = {
            str(getattr(item, "fact_id", ""))
            for item in (getattr(fact_set, "facts", ()) or ())
            if str(getattr(item, "fact_id", ""))
        }
    if not packet_spans:
        packet_set = payload.get("packet_set")
        packet_spans = {
            str(getattr(span, "span_id", ""))
            for packet in (getattr(packet_set, "packets", ()) or ())
            for span in (getattr(packet, "spans", ()) or ())
            if str(getattr(span, "span_id", ""))
        }
    claim_set = payload.get("claim_set")
    claim_ids = {
        str(getattr(claim, "claim_id", ""))
        for claim in (getattr(claim_set, "claims", ()) or ())
        if str(getattr(claim, "claim_id", ""))
    }
    new_facts = fact_ids - old_fact_ids
    new_spans = packet_spans - old_span_ids
    new_claims = claim_ids - old_claim_ids
    loop.intent_compile_events.append({
        "obligation_id": obligation_id,
        "new_spans_count": len(new_spans),
        "new_facts_count": len(new_facts),
        "new_claims_count": len(new_claims),
        # Typed publication slots are represented by claims' obligation
        # bindings at this boundary.  Count newly bound claim/obligation pairs
        # so a retry can be classified by semantic rather than text gain.
        "new_typed_slots_count": len({
            (str(getattr(claim, "claim_id", "")), str(obligation_id))
            for claim in (getattr(claim_set, "claims", ()) or ())
            if str(getattr(claim, "claim_id", ""))
            and str(obligation_id)
        } - {
            (str(getattr(claim, "claim_id", "")), str(obligation_id))
            for claim in (getattr(getattr(current, "claim_set", None), "claims", ()) or ())
            if str(getattr(claim, "claim_id", ""))
            and str(obligation_id)
        }),
        "new_operations_count": 0,
        # Reading another span is acquisition progress, but it is not
        # terminal-proof progress.  Only promoted facts/claims/typed bindings
        # may reset the compile-stall counter used by the intent scheduler.
        "has_coverage_gain": bool(new_facts or new_claims),
    })


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
    observation_history: list[dict[str, Any]] = Field(default_factory=list)
    active_issue: dict[str, Any] | None = None
    current_quality_state: dict[str, Any] = Field(default_factory=dict)
    best_quality_state: dict[str, Any] = Field(default_factory=dict)
    decision_trace: list[dict[str, Any]] = Field(default_factory=list)
    policy_merge_trace: list[dict[str, Any]] = Field(default_factory=list)
    compiled_evidence: dict[str, dict[str, Any]] = Field(default_factory=dict)
    implementation_scope: dict[str, Any] = Field(default_factory=dict)
    implementation_scope_symbols: list[dict[str, Any]] = Field(default_factory=list)
    candidate_acquisition_ledger: dict[str, Any] = Field(default_factory=dict)
    intent_implementation_ledger: dict[str, Any] = Field(default_factory=dict)
    intent_schedule: dict[str, Any] = Field(default_factory=dict)
    intent_compile_events: list[dict[str, Any]] = Field(default_factory=list)
    compile_attempts: list[dict[str, Any]] = Field(default_factory=list)
    post_partial_retry_counts: dict[str, int] = Field(default_factory=dict)
    # Source identity sidecars are persisted in the immutable payload and
    # echoed here for quick resume validation.  They are checkpoint-safe
    # models, not LangGraph state channels.
    symbol_index: dict[str, Any] = Field(default_factory=dict)
    source_manifest: dict[str, Any] = Field(default_factory=dict)
    symbol_index_digest: str = ""
    source_manifest_digest: str = ""
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""

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
        "turn_index": loop.turn_index,
        "behavior_graph": loop.behavior_graph.model_dump(mode="json"),
        "agenda_items": [item.model_dump(mode="json") for item in loop.runtime.agenda.items],
        "gain_tracker": loop.gain_tracker.snapshot(),
        "recent_observations": [item.model_dump(mode="json") for item in loop.recent_observations],
        "observation_history": [item.model_dump(mode="json") for item in loop.observation_history],
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
        "implementation_scope": loop.implementation_scope.model_dump(mode="json"),
        "implementation_scope_symbols": list(loop.implementation_scope_symbols),
        "candidate_acquisition_ledger": loop.candidate_acquisition_ledger.model_dump(mode="json"),
        "intent_implementation_ledger": (
            loop.intent_implementation_ledger.model_dump(mode="json")
            if loop.intent_implementation_ledger is not None else {}
        ),
        "intent_schedule": dict(loop.intent_schedule or {}),
        "intent_compile_events": list(loop.intent_compile_events or ()),
        "compile_attempts": [
            item.model_dump(mode="json")
            for item in (loop.compile_attempts or ())
        ],
        "post_partial_retry_counts": dict(loop.post_partial_retry_counts or {}),
        "symbol_index": (
            loop.symbol_index.model_dump(mode="json")
            if loop.symbol_index is not None else {}
        ),
        "source_manifest": (
            loop.source_manifest.model_dump(mode="json")
            if loop.source_manifest is not None else {}
        ),
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
        symbol_index_digest=(
            str(getattr(loop.symbol_index, "content_digest", "") or "")
            if loop.symbol_index is not None else ""
        ),
        source_manifest_digest=(
            str(getattr(loop.source_manifest, "content_digest", "") or "")
            if loop.source_manifest is not None else ""
        ),
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
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
    snapshot_repo_id = str(
        snapshot.repo_snapshot_id
        or immutable.get("repo_snapshot_id", "")
        or ""
    )
    snapshot_tree_hash = str(
        snapshot.project_tree_hash
        or immutable.get("project_tree_hash", "")
        or ""
    )
    if snapshot_repo_id and snapshot_repo_id != runtime.repo_snapshot.snapshot_id:
        if strict:
            raise ValueError("invalid_loop_state_snapshot:repo_snapshot_mismatch")
        return None
    if snapshot_tree_hash and snapshot_tree_hash != runtime.repo_snapshot.project_tree_hash:
        if strict:
            raise ValueError("invalid_loop_state_snapshot:project_tree_mismatch")
        return None
    symbol_payload = immutable.get("symbol_index") or snapshot.symbol_index
    if symbol_payload:
        try:
            restored_index = SymbolIndexV2.model_validate(symbol_payload)
            if (
                restored_index.repo_snapshot_id != runtime.repo_snapshot.snapshot_id
                or restored_index.project_tree_hash != runtime.repo_snapshot.project_tree_hash
            ):
                raise ValueError("symbol index snapshot identity mismatch")
            expected_index_digest = str(snapshot.symbol_index_digest or "")
            if expected_index_digest and restored_index.content_digest != expected_index_digest:
                raise ValueError("symbol index digest mismatch")
            loop.symbol_index = restored_index
        except Exception as exc:
            if strict:
                raise ValueError("invalid_loop_state_snapshot:symbol_index") from exc
    elif snapshot.symbol_index_digest:
        # A digest without the authenticated payload is not an index.  Do
        # not resume with a fresh/empty identity and accidentally widen the
        # compile path on a checkpoint that only carried a sidecar hash.
        if strict:
            raise ValueError("invalid_loop_state_snapshot:symbol_index")
    manifest_payload = immutable.get("source_manifest") or snapshot.source_manifest
    if manifest_payload:
        try:
            restored_manifest = RepositorySourceManifestV1.model_validate(
                manifest_payload
            )
            if (
                restored_manifest.repo_snapshot_id != runtime.repo_snapshot.snapshot_id
                or restored_manifest.project_tree_hash != runtime.repo_snapshot.project_tree_hash
            ):
                raise ValueError("source manifest snapshot identity mismatch")
            expected_manifest_digest = str(snapshot.source_manifest_digest or "")
            if expected_manifest_digest and restored_manifest.content_digest != expected_manifest_digest:
                raise ValueError("source manifest digest mismatch")
            loop.source_manifest = restored_manifest
        except Exception as exc:
            if strict:
                raise ValueError("invalid_loop_state_snapshot:source_manifest") from exc
    elif snapshot.source_manifest_digest:
        if strict:
            raise ValueError("invalid_loop_state_snapshot:source_manifest")
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
    loop.observation_history = [
        ResearchObservationV1.model_validate(payload)
        for payload in (
            immutable.get("observation_history")
            or snapshot.observation_history
            or immutable.get("recent_observations")
            or snapshot.recent_observations
        )
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
    scope_payload = immutable.get("implementation_scope") or snapshot.implementation_scope
    if scope_payload:
        try:
            loop.implementation_scope = ImplementationScopeV1.model_validate(scope_payload)
        except Exception as exc:
            if strict:
                raise ValueError("invalid_loop_state_snapshot:implementation_scope") from exc
    scope_symbols = immutable.get("implementation_scope_symbols") or snapshot.implementation_scope_symbols
    if scope_symbols:
        loop.implementation_scope_symbols = tuple(
            dict(item) for item in scope_symbols if isinstance(item, dict)
        )
    ledger_payload = immutable.get("candidate_acquisition_ledger") or snapshot.candidate_acquisition_ledger
    if ledger_payload:
        try:
            loop.candidate_acquisition_ledger = CandidateAcquisitionLedgerV1.model_validate(ledger_payload)
        except Exception as exc:
            if strict:
                raise ValueError("invalid_loop_state_snapshot:candidate_acquisition_ledger") from exc
    intent_payload = immutable.get("intent_implementation_ledger") or snapshot.intent_implementation_ledger
    if intent_payload:
        try:
            loop.intent_implementation_ledger = IntentImplementationLedgerV1.model_validate(
                intent_payload
            )
        except Exception as exc:
            if strict:
                raise ValueError("invalid_loop_state_snapshot:intent_implementation_ledger") from exc
    loop.intent_schedule = dict(
        immutable.get("intent_schedule") or snapshot.intent_schedule or {}
    )
    loop.intent_compile_events = [
        dict(item)
        for item in (
            immutable.get("intent_compile_events")
            or getattr(snapshot, "intent_compile_events", ())
            or ()
        )
        if isinstance(item, dict)
    ]
    loop.compile_attempts = [
        CompileAttemptResultV1.model_validate(payload)
        for payload in (
            immutable.get("compile_attempts")
            or getattr(snapshot, "compile_attempts", ())
            or ()
        )
        if isinstance(payload, dict)
    ]
    loop.post_partial_retry_counts = {
        str(key): max(0, int(value or 0))
        for key, value in (
            immutable.get("post_partial_retry_counts")
            or getattr(snapshot, "post_partial_retry_counts", {})
            or {}
        ).items()
        if str(key).strip()
    }
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
    # Unlike ``recent_observations`` this list is never cleared when the
    # active obligation advances.  It is the provenance ledger input and is
    # therefore required for cumulative candidate closure and checkpoint
    # resume.
    observation_history: list[ResearchObservationV1] = field(default_factory=list)
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
    implementation_scope: ImplementationScopeV1 = field(default_factory=ImplementationScopeV1)
    implementation_scope_symbols: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    candidate_acquisition_ledger: CandidateAcquisitionLedgerV1 = field(default_factory=CandidateAcquisitionLedgerV1)
    intent_implementation_ledger: IntentImplementationLedgerV1 = field(
        default_factory=IntentImplementationLedgerV1
    )
    intent_schedule: dict[str, Any] = field(default_factory=dict)
    intent_compile_events: list[dict[str, Any]] = field(default_factory=list)
    compile_attempts: list[CompileAttemptResultV1] = field(default_factory=list)
    # A partial obligation gets one bounded post-partial compile transaction.
    # This counter is checkpointed so resume cannot buy another retry by
    # restarting the process.
    post_partial_retry_counts: dict[str, int] = field(default_factory=dict)
    intent_scheduler: IntentCoverageScheduler = field(
        default_factory=IntentCoverageScheduler
    )
    observation_promotion_ledger: Any = None
    # R10 revision binding.  The journal is the append-only record of the
    # revisions this run actually applied; the outcomes/notes/failures keep the
    # harness ingestion auditable without re-deriving it from disk.
    revision_journal: RevisionJournalV1 = field(default_factory=RevisionJournalV1)
    revision_ingest_outcomes: list[dict[str, Any]] = field(default_factory=list)
    revision_rebind_notes: list[dict[str, Any]] = field(default_factory=list)
    revision_ingest_failures: list[str] = field(default_factory=list)
    # Frozen input-boundary sidecars used by unified reconstruction.  They are
    # held outside LangGraph channels and re-emitted as ordinary artifacts.
    symbol_index: Any | None = None
    source_manifest: Any | None = None


def _compute_live_research_quality(loop: "ResearchLoopState") -> QualityStateV2:
    """Derive the current Research quality/cost state from live loop data.

    The previous loop carried the zero-valued seed forever.  This projection
    intentionally uses only already-authorized loop objects: agenda terminal
    states, compiled claims, executed decisions/calls, and typed missing
    relations.  It grants no new evidence authority.
    """

    must_cover = [
        item for item in loop.runtime.agenda.items
        if item.priority == "must_cover"
    ]
    terminal_statuses = {"supported", "partial", "explicit_gap"}
    terminal_must_cover = sum(
        item.status in terminal_statuses for item in must_cover
    )
    supported_must_cover = sum(
        item.status == "supported" for item in must_cover
    )
    supported_claim_identities = {
        str(getattr(claim, "canonical_identity", "") or getattr(claim, "claim_id", ""))
        for compiled in loop.compiled_evidence.values()
        for claim in (getattr(compiled.claim_set, "claims", ()) or ())
        if str(getattr(claim, "status", "supported") or "supported") == "supported"
        and str(
            getattr(claim, "canonical_identity", "")
            or getattr(claim, "claim_id", "")
        ).strip()
    }
    unresolved_relations = sum(
        str(value).startswith(("typed_relation:", "relation:"))
        for item in loop.runtime.agenda.items
        for value in (item.missing_information or ())
    )
    model_calls = sum(
        str(getattr(decision, "produced_by", "") or "") == "llm_proposal"
        for decision in loop.decision_trace
    )
    tool_calls = len(loop.recent_tool_call_ids)
    repeated_no_gain = int(
        getattr(loop.intent_implementation_ledger, "no_progress_compile_count", 0)
        or 0
    )
    content = QualityContentDimensionsV1(
        terminal_must_cover=terminal_must_cover,
        supported_must_cover=supported_must_cover,
        unique_supported_claims=len(supported_claim_identities),
        validated_final_sentences=0,
        unresolved_high_value_obligations=max(
            0, len(must_cover) - terminal_must_cover
        ),
    )
    cost = QualityCostDimensionsV1(
        model_calls=model_calls,
        tool_calls=tool_calls,
        repeated_no_gain_calls=repeated_no_gain,
    )
    state_payload = {
        "run_id": loop.runtime.run_id,
        "content": content.model_dump(mode="json"),
        "cost": cost.model_dump(mode="json"),
        "unresolved_relations": unresolved_relations,
    }
    state_id = "quality-state-" + hashlib.sha256(
        json.dumps(
            state_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    return QualityStateV2(
        state_id=state_id,
        run_id=loop.runtime.run_id,
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
        safety=QualitySafetyDimensionsV1(source_integrity=True),
        content=content,
        minimality=QualityMinimalityDimensionsV1(
            unresolved_relations=unresolved_relations,
        ),
        cost=cost,
    )


def _refresh_loop_quality(
    loop: "ResearchLoopState",
    state: AgentStateV3 | dict[str, Any],
) -> dict[str, Any]:
    """Recompute current quality and apply the conservative best selector."""

    loop.current_quality_state = _compute_live_research_quality(loop)
    update = quality_state_selector_node(
        state,
        runtime=loop.runtime,
        current_quality_state=loop.current_quality_state,
        best_quality_state=loop.best_quality_state,
    )
    if "best_quality_state_ref" in update:
        loop.best_quality_state = loop.current_quality_state
    return update


def _append_observation_history(
    loop: ResearchLoopState,
    observations: tuple[ResearchObservationV1, ...] | list[ResearchObservationV1],
) -> None:
    """Append observations once while keeping the supervisor window separate."""

    seen = {item.observation_id for item in loop.observation_history}
    for observation in observations:
        if observation.observation_id not in seen:
            loop.observation_history.append(observation)
            seen.add(observation.observation_id)


def _append_compile_attempt(
    loop: ResearchLoopState,
    attempt: CompileAttemptResultV1 | None,
) -> None:
    """Keep one immutable compile-attempt receipt per content digest."""

    if attempt is None:
        return
    if any(item.content_digest == attempt.content_digest for item in loop.compile_attempts):
        return
    loop.compile_attempts.append(attempt)


def _refresh_acquisition_ledger(
    loop: ResearchLoopState,
    state: dict[str, Any] | None = None,
) -> CandidateAcquisitionLedgerV1:
    """Rebuild and persist the candidate closure ledger at each boundary."""

    # Refine the scope at the behavior-graph boundary.  The initial indexer
    # has symbols and intent but no call graph; once behavior nodes/relations
    # exist, reachable symbols become dependencies and ambiguous siblings
    # remain unknown/audit-only.
    if loop.implementation_scope_symbols:
        entry_ids = loop.implementation_scope.target_entry_symbol_ids
        loop.implementation_scope = infer_implementation_scope(
            loop.implementation_scope_symbols,
            author_texts=tuple(
                str(getattr(item, "author_text", "") or "")
                for item in loop.runtime.agenda.items
            ),
            entry_symbol_ids=entry_ids,
            behavior_graph=loop.behavior_graph,
            evidence_refs=(
                loop.runtime.repo_snapshot.snapshot_id,
                loop.runtime.repo_snapshot.project_tree_hash,
                loop.behavior_graph.content_digest,
            ),
        )
        # Scope refinement changes path ownership.  Rebuild the manifest from
        # the same frozen snapshot/symbol index immediately so persistence
        # cannot combine a post-graph scope with the pre-graph source
        # partition under a false cross-artifact identity.
        if loop.symbol_index is not None:
            loop.source_manifest = build_repository_source_manifest(
                loop.runtime.repo_snapshot,
                symbols=getattr(loop.symbol_index, "symbols", ()) or (),
                implementation_scope=loop.implementation_scope,
            )

    # Parent-to-child propagation is repeated after behavior extraction so a
    # child can inherit a semantically related target symbol once the graph
    # exposes its operation context.  The helper never copies audit-only
    # candidates.
    seed_child_candidates_from_parents(
        loop.runtime.agenda.items,
        behavior_graph=loop.behavior_graph,
        scope=loop.implementation_scope,
        symbols=(
            getattr(loop.symbol_index, "symbols", ())
            if loop.symbol_index is not None
            else ()
        ),
    )
    loop.runtime.agenda.refresh_content_digest()
    ledger = build_candidate_acquisition_ledger(
        scope=loop.implementation_scope,
        agenda_items=loop.runtime.agenda.items,
        observations=tuple(loop.observation_history or loop.recent_observations),
        behavior_graph=loop.behavior_graph,
        compiled_by_obligation=loop.compiled_evidence,
        symbols=getattr(loop.symbol_index, "symbols", ()) if loop.symbol_index is not None else (),
        source_manifest=loop.source_manifest,
        repo_snapshot=loop.runtime.repo_snapshot,
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
    )
    loop.candidate_acquisition_ledger = ledger
    loop.observation_promotion_ledger = build_observation_promotion_ledger(
        observations=tuple(loop.observation_history or loop.recent_observations),
        behavior_graph=loop.behavior_graph,
        compiled_by_obligation=loop.compiled_evidence,
        symbols=(
            getattr(loop.symbol_index, "symbols", ())
            if loop.symbol_index is not None
            else ()
        ),
        agenda_items=tuple(loop.runtime.agenda.items),
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
    )
    path = loop.runtime.tool_context().write_artifact(
        "candidate_acquisition_ledgers", ledger.content_digest, ledger
    )
    if state is not None:
        state["candidate_acquisition_ledger_ref"] = ledger.content_digest
        state["observation_promotion_ledger_ref"] = (
            loop.observation_promotion_ledger.content_digest
        )
    return ledger


def _compiled_operation_ids_for_obligation(
    *,
    obligation_id: str,
    compiled: "CompiledEvidence",
    behavior_graph: CodeBehaviorGraphV1,
) -> tuple[str, ...]:
    """Return only graph nodes evidenced by one compiled obligation.

    ``ResearchLoopState.behavior_graph`` is a repository-wide accumulation.
    It is not an ownership proof for every obligation.  The compiler sidecar
    is the narrower authority: facts carry exact source spans and packets may
    carry resolved relation endpoint node ids.  A node is promoted only when
    one of those exact anchors points to it; an empty match stays empty rather
    than falling back to the complete behavior graph.
    """

    owned_span_ids: set[str] = set()
    for fact in (getattr(compiled.fact_set, "facts", ()) or ()):
        for field in ("direct_span_ids", "relation_span_ids"):
            owned_span_ids.update(
                str(value).strip()
                for value in (getattr(fact, field, ()) or ())
                if str(value).strip()
            )

    owned_node_ids: set[str] = set()
    for packet in (getattr(compiled.packet_set, "packets", ()) or ()):
        tags = {
            str(value).strip()
            for value in (getattr(packet, "obligation_tags", ()) or ())
            if str(value).strip()
        }
        if tags and str(obligation_id).strip() not in tags:
            continue
        owned_span_ids.update(
            str(getattr(span, "span_id", "")).strip()
            for span in (getattr(packet, "spans", ()) or ())
            if str(getattr(span, "span_id", "")).strip()
        )
        for relation in (getattr(packet, "relations", ()) or ()):
            for endpoint_name in ("source_endpoint", "target_endpoint"):
                endpoint = getattr(relation, endpoint_name, None)
                node_id = str(getattr(endpoint, "node_id", "")).strip()
                if node_id:
                    owned_node_ids.add(node_id)

    if not owned_span_ids and not owned_node_ids:
        return ()
    return tuple(
        str(node.node_id)
        for node in (getattr(behavior_graph, "nodes", ()) or ())
        if str(getattr(node, "node_id", "")).strip()
        and (
            str(node.node_id) in owned_node_ids
            or str(getattr(node, "source_span_id", "")).strip() in owned_span_ids
        )
    )


POST_PARTIAL_RETRY_LIMIT = 1


def _partial_retry_count(loop: "ResearchLoopState", obligation_id: str) -> int:
    return max(0, int(loop.post_partial_retry_counts.get(str(obligation_id), 0) or 0))


def _note_post_partial_retry(
    loop: "ResearchLoopState",
    obligation_id: str,
    *,
    was_partial: bool,
) -> None:
    """Consume the single retry slot after a partial compile.

    The compile node is the atomic boundary for this rule.  Counting here,
    immediately after it returns, makes the allowance durable even when the
    process is interrupted before the next supervisor decision.
    """

    if not was_partial:
        return
    key = str(obligation_id or "").strip()
    if not key:
        return
    current = _partial_retry_count(loop, key)
    if current < POST_PARTIAL_RETRY_LIMIT:
        loop.post_partial_retry_counts[key] = current + 1


def _is_partial_compile_retry(loop: "ResearchLoopState", obligation_id: str) -> bool:
    """Return whether the upcoming compile is the bounded partial retry."""

    item = next(
        (
            candidate for candidate in loop.runtime.agenda.items
            if str(candidate.obligation_id) == str(obligation_id)
        ),
        None,
    )
    if item is None or str(item.status) != "partial":
        return False
    compiled = loop.compiled_evidence.get(str(obligation_id))
    return bool(
        item.supported_claim_ids
        or tuple(
            getattr(getattr(compiled, "claim_set", None), "claims", ()) or ()
        )
    )


def _candidate_structural_failure_codes(loop: "ResearchLoopState") -> tuple[str, ...]:
    """Extract only structural failures that can contaminate Candidate."""

    values: list[str] = []
    structural_tokens = (
        "identity",
        "snapshot",
        "lineage",
        "ownership",
        "source_manifest",
        "symbol_index",
        "candidate_binding",
        "resume_",
        "invalid_loop_state",
    )
    core_ids = {
        str(item.obligation_id)
        for item in loop.runtime.agenda.items
        if item.priority == "must_cover"
    }

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and any(token in text.casefold() for token in structural_tokens):
            values.append(text)

    add(getattr(loop, "termination_reason", ""))
    for attempt in loop.compile_attempts or ():
        if str(getattr(attempt, "obligation_id", "") or "") not in core_ids:
            continue
        add(getattr(attempt, "rejection_code", ""))
    for item in loop.runtime.agenda.items:
        if item.priority != "must_cover":
            continue
        for value in item.missing_information or ():
            add(value)
    for record in getattr(loop.observation_promotion_ledger, "records", ()) or ():
        if str(getattr(record, "obligation_id", "") or "") not in core_ids:
            continue
        add(getattr(record, "rejection_code", ""))
    return tuple(dict.fromkeys(values))


def _compiled_claim_ids_by_obligation(
    loop: "ResearchLoopState",
) -> dict[str, tuple[str, ...]]:
    return {
        str(obligation_id): tuple(dict.fromkeys(
            str(getattr(claim, "claim_id", "") or "")
            for claim in (
                getattr(getattr(compiled, "claim_set", None), "claims", ()) or ()
            )
            if str(getattr(claim, "claim_id", "") or "")
        ))
        for obligation_id, compiled in (loop.compiled_evidence or {}).items()
    }


def _compiled_claims_by_obligation(
    loop: "ResearchLoopState",
) -> dict[str, tuple[Any, ...]]:
    return {
        str(obligation_id): tuple(
            getattr(getattr(compiled, "claim_set", None), "claims", ()) or ()
        )
        for obligation_id, compiled in (loop.compiled_evidence or {}).items()
    }


def _build_candidate_handoff(loop: "ResearchLoopState") -> CandidateHandoffV1:
    """Build the Candidate lane view from the live, frozen research state."""

    retry_gain_by_obligation: dict[str, bool | None] = {}
    for event in loop.intent_compile_events or ():
        obligation_id = str(event.get("obligation_id") or "").strip()
        if not obligation_id or _partial_retry_count(loop, obligation_id) < 1:
            continue
        retry_gain_by_obligation[obligation_id] = bool(
            event.get("has_coverage_gain", False)
        )
    agenda_digest = loop.runtime.agenda.refresh_content_digest()
    promotion_ledger = getattr(loop, "observation_promotion_ledger", None)
    revision_journal = getattr(loop, "revision_journal", None)
    return build_candidate_handoff(
        run_id=loop.runtime.run_id,
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
        agenda_items=tuple(loop.runtime.agenda.items),
        promotion_records=tuple(
            getattr(promotion_ledger, "records", ()) or ()
        ),
        compiled_claim_ids_by_obligation=_compiled_claim_ids_by_obligation(loop),
        compiled_claims_by_obligation=_compiled_claims_by_obligation(loop),
        post_partial_retry_counts=loop.post_partial_retry_counts,
        retry_gain_by_obligation=retry_gain_by_obligation,
        structural_failure_codes=_candidate_structural_failure_codes(loop),
        agenda_digest=agenda_digest,
        promotion_ledger_digest=str(
            getattr(promotion_ledger, "content_digest", "") or ""
        ),
        # R10 §15.6: the handoff names the revision its targets belong to, so a
        # handoff built before a later revision is detectable as stale.
        revision_id=(
            revision_journal.current_revision_id() if revision_journal else ""
        ),
    )


def _legal_action_available_for_core(
    loop: "ResearchLoopState",
    unresolved_core_ids: Sequence[str],
) -> bool:
    """Whether any unresolved core obligation still has a legal research move.

    Turn budget alone must not report ``can_continue`` when every remaining
    tool budget is zero and the only remaining move is the bounded-search
    proof.  This mirrors the policy merge's budget gate so the checkpoint
    and the final state describe the same constraint.
    """

    for obligation_id in unresolved_core_ids:
        budget = loop.per_obligation_budgets.get(str(obligation_id))
        if budget is not None:
            limits = dict(getattr(budget, "limits", {}) or {})
            if limits and not any(
                int(budget.remaining(kind)) > 0 for kind in limits
            ):
                continue
        if (
            loop.gain_tracker.targeted_search_exhausted(str(obligation_id))
            and loop.gain_tracker.may_record_gap(str(obligation_id))
        ):
            # The only remaining route is the bounded-search gap proof,
            # which is not a research action.
            continue
        return True
    return False


def _core_tool_budget_failure_code(loop: "ResearchLoopState") -> str:
    """Return a typed budget-exhaustion code for the blocked checkpoint."""

    for item in loop.runtime.agenda.items:
        if item.priority != "must_cover":
            continue
        if item.status in {"supported", "partial", "explicit_gap", "blocked"}:
            continue
        budget = loop.per_obligation_budgets.get(item.obligation_id)
        if budget is None:
            continue
        limits = dict(getattr(budget, "limits", {}) or {})
        if not limits:
            continue
        exhausted_kinds = sorted(
            kind for kind in limits if int(budget.remaining(kind)) <= 0
        )
        if len(exhausted_kinds) == len(limits):
            return (
                "core_tool_budget_exhausted:"
                f"{item.obligation_id}:{exhausted_kinds[0]}"
            )
    return "core_tool_budget_exhausted:unknown:unknown"


def _refresh_intent_coverage_scheduler(
    loop: "ResearchLoopState",
    state: dict[str, Any] | None = None,
    *,
    remaining_budget_turns: int = 0,
    current_action_is_novelty: bool = True,
) -> dict[str, Any]:
    """Build and execute the production core-intent scheduler.

    The old promotion ledger was an after-the-fact sidecar.  This boundary
    derives a closed intent ledger from the live agenda, observations, and
    compiled evidence, then invokes ``check_next_schedule`` before every
    scheduling/termination decision.  Discovery without a typed terminal
    disposition remains open.
    """

    agenda_items = tuple(loop.runtime.agenda.items)
    observations = tuple(loop.observation_history or loop.recent_observations)
    queries_by_clause: dict[str, list[str]] = {}
    reads_by_clause: dict[str, list[str]] = {}
    for item in agenda_items:
        cid = str(item.obligation_id)
        queries_by_clause[cid] = [
            str(action) for action in (item.attempted_actions or ()) if str(action)
        ]
    for observation in observations:
        cid = str(observation.obligation_id)
        queries_by_clause.setdefault(cid, []).append(str(observation.tool_name))
        reads_by_clause.setdefault(cid, []).extend(
            [
                *tuple(str(value) for value in observation.exact_span_ids),
                *tuple(str(value) for value in observation.notebook.discovered_symbols),
            ]
        )
    facts_by_clause: dict[str, list[str]] = {}
    operations_by_clause: dict[str, list[str]] = {}
    for obligation_id, compiled in loop.compiled_evidence.items():
        facts_by_clause[obligation_id] = [
            str(item.fact_id)
            for item in (getattr(compiled.fact_set, "facts", ()) or ())
            if str(getattr(item, "fact_id", ""))
        ]
        operations_by_clause[obligation_id] = list(
            _compiled_operation_ids_for_obligation(
                obligation_id=obligation_id,
                compiled=compiled,
                behavior_graph=loop.behavior_graph,
            )
        )
    statuses: dict[str, str] = {}
    rejections: dict[str, str] = {}
    for item in agenda_items:
        cid = str(item.obligation_id)
        if item.status == "supported":
            statuses[cid] = "implemented_exact"
        elif item.status == "partial":
            statuses[cid] = "implemented_partial"
        elif item.status == "explicit_gap":
            statuses[cid] = "not_found_after_bounded_search"
        elif item.status == "blocked":
            statuses[cid] = "repo_mismatch"
            rejections[cid] = ";".join(str(value) for value in item.missing_information) or "agenda_blocked"

    loop.intent_implementation_ledger = build_intent_implementation_ledger(
        clauses=[
            {
                "clause_id": str(item.obligation_id),
                "clause_text": str(item.author_text),
                "is_core": item.priority == "must_cover",
            }
            for item in agenda_items
        ],
        queries_by_clause=queries_by_clause,
        candidates_by_clause={
            str(item.obligation_id): tuple(item.candidate_symbol_ids or ())
            for item in agenda_items
        },
        read_symbols_by_clause=reads_by_clause,
        promoted_facts_by_clause=facts_by_clause,
        promoted_operations_by_clause=operations_by_clause,
        rejections_by_clause=rejections,
        statuses_by_clause=statuses,
        repo_snapshot_id=loop.runtime.repo_snapshot.snapshot_id,
        project_tree_hash=loop.runtime.repo_snapshot.project_tree_hash,
        total_budget_turns=max(1, int(remaining_budget_turns or 1)),
        novelty_budget_turns=max(0, int(remaining_budget_turns)),
        compile_events=tuple(loop.intent_compile_events),
    )
    schedule = loop.intent_scheduler.check_next_schedule(
        loop.intent_implementation_ledger,
        remaining_budget_turns=max(0, int(remaining_budget_turns)),
        current_action_is_novelty=current_action_is_novelty,
    )
    promotion_records = tuple(
        getattr(loop.observation_promotion_ledger, "records", ()) or ()
    )
    terminal_proofs: dict[str, ObligationTerminalProofV1] = {}
    for item in agenda_items:
        compiled = loop.compiled_evidence.get(str(item.obligation_id))
        compiled_claim_ids = tuple(
            str(getattr(claim, "claim_id", "") or "")
            for claim in (
                getattr(getattr(compiled, "claim_set", None), "claims", ()) or ()
            )
            if str(getattr(claim, "claim_id", "") or "")
        )
        terminal_proofs[str(item.obligation_id)] = evaluate_obligation_terminal_proof(
            item,
            promotion_records=tuple(
                record
                for record in promotion_records
                if str(getattr(record, "obligation_id", "") or "")
                == str(item.obligation_id)
            ),
            promoted_claim_ids=compiled_claim_ids,
        )
    unresolved_core_intents = tuple(
        str(value)
        for value in (
            *tuple(schedule.get("unattempted_core_clause_ids", ()) or ()),
            *tuple(schedule.get("unresolved_core_clause_ids", ()) or ()),
        )
        if str(value).strip()
    )
    unresolved_promotions = tuple(
        record.observation_id
        for record in (
            getattr(loop.observation_promotion_ledger, "records", ()) or ()
        )
        if promotion_record_blocks_strict_research(record)
    )
    unresolved_terminal_proof_ids = tuple(
        obligation_id
        for obligation_id, proof in terminal_proofs.items()
        if not proof.terminal
    )
    unresolved_terminal_proofs = tuple(
        obligation_id
        for obligation_id in unresolved_terminal_proof_ids
        if next(
            (
                item.priority == "must_cover"
                for item in agenda_items
                if str(item.obligation_id) == obligation_id
            ),
            False,
        )
    )
    schedule["obligation_terminal_proofs"] = {
        obligation_id: proof.model_dump(mode="json")
        for obligation_id, proof in terminal_proofs.items()
    }
    schedule["unresolved_terminal_proof_ids"] = unresolved_terminal_proof_ids
    schedule["unresolved_observation_promotion_ids"] = unresolved_promotions
    schedule["unresolved_core_intent_ids"] = tuple(
        dict.fromkeys((*unresolved_core_intents, *unresolved_terminal_proofs))
    )
    # The turn-budget scheduler can still answer ``can_continue`` while the
    # per-obligation tool budgets are already exhausted.  Recompute the
    # legal-action condition after the policy merge so the persisted
    # checkpoint and the terminal state agree.
    unresolved_core_ids = tuple(schedule["unresolved_core_intent_ids"])
    legal_action_available = _legal_action_available_for_core(
        loop, unresolved_core_ids
    )
    schedule["legal_action_available"] = legal_action_available
    schedule["budget_constrained"] = bool(
        unresolved_core_ids and not legal_action_available
    )
    schedule["can_continue"] = bool(
        schedule.get("can_continue", True)
    ) and legal_action_available
    # Keep the strict audit result separate from the bounded Candidate lane.
    # The former still includes every obligation and every promotion record;
    # the latter deliberately consumes only the must-cover spine after each
    # partial item has received one post-partial compile transaction.
    strict_research_complete = not bool(
        schedule.get("unresolved_core_intent_ids")
        or unresolved_promotions
        or unresolved_terminal_proof_ids
    )
    candidate_handoff = _build_candidate_handoff(loop)
    schedule["strict_research_complete"] = strict_research_complete
    schedule["candidate_handoff_ready"] = candidate_handoff.eligible
    schedule["candidate_handoff"] = candidate_handoff.model_dump(mode="json")
    schedule["deferred_obligation_ids"] = candidate_handoff.deferred_obligation_ids
    schedule["candidate_warning_codes"] = candidate_handoff.warning_codes
    # ``can_terminate`` is the scheduler's execution stop condition, not a
    # claim that the full research audit is complete.
    schedule["can_terminate"] = bool(
        strict_research_complete or candidate_handoff.eligible
    )
    loop.intent_schedule = schedule
    if state is not None:
        state["intent_implementation_ledger_ref"] = loop.intent_implementation_ledger.content_digest
        state["intent_schedule"] = dict(schedule)
    return schedule


def _intent_termination_blocked(loop: "ResearchLoopState", state: dict[str, Any]) -> bool:
    schedule = _refresh_intent_coverage_scheduler(
        loop,
        state,
        remaining_budget_turns=max(0, 0),
        current_action_is_novelty=False,
    )
    return not bool(schedule.get("can_terminate", False))


def _research_block_root_code(
    loop: "ResearchLoopState",
    *,
    active_obligation_id: str = "",
) -> str:
    """Return the concrete root code behind a supervisor stop.

    ``STOP_BLOCKED`` is a control action, not a diagnosis.  Prefer the last
    typed compile/data-plane rejection, then the active issue or missing-info
    code, so a terminal artifact remains actionable after the generic stop
    route has been taken.
    """

    if bool((loop.intent_schedule or {}).get("budget_constrained", False)):
        return _core_tool_budget_failure_code(loop)
    for attempt in reversed(loop.compile_attempts or ()):
        if active_obligation_id and attempt.obligation_id != active_obligation_id:
            continue
        if str(attempt.rejection_code or "").strip():
            return str(attempt.rejection_code).strip()
    if loop.active_issue is not None:
        issue_kind = str(getattr(loop.active_issue, "issue_kind", "") or "").strip()
        if issue_kind:
            return f"research_issue:{issue_kind}"
    for item in loop.runtime.agenda.items:
        if active_obligation_id and item.obligation_id != active_obligation_id:
            continue
        for value in item.missing_information or ():
            raw = str(value or "").strip()
            if raw.startswith("identity:"):
                return raw.removeprefix("identity:") or raw
            if raw:
                return raw
    return "supervisor_stop_blocked"


def _mark_trusted_terminal(
    loop: "ResearchLoopState",
    state: dict[str, Any],
    *,
    reason: str,
) -> str:
    """Apply strict or Candidate handoff gates before ending Research."""

    schedule = _refresh_intent_coverage_scheduler(
        loop,
        state,
        remaining_budget_turns=0,
        current_action_is_novelty=False,
    )
    if bool(schedule.get("strict_research_complete", False)):
        state["status"] = "trusted"
        return reason
    if bool(schedule.get("candidate_handoff_ready", False)):
        # Candidate is an intentionally non-trusted handoff.  The strict
        # proof remains open and Verified must continue to fail closed.
        state["status"] = "incomplete"
        state["blocked_reason"] = "candidate_handoff_partial"
        # Do not reuse all_obligations_terminal: the top-level terminal event
        # consumes this return value and must describe the actual lane.
        return "candidate_handoff_partial"
    if not bool(schedule.get("can_terminate", False)):
        state["status"] = "blocked"
        state["blocked_reason"] = "intent_coverage_or_promotion_incomplete"
        return "intent_coverage_blocked"
    state["status"] = "blocked"
    state["blocked_reason"] = "intent_coverage_or_promotion_incomplete"
    return "intent_coverage_blocked"


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
        implementation_scope=ImplementationScopeV1(),
        candidate_acquisition_ledger=CandidateAcquisitionLedgerV1(
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        ),
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
    # R10: the revision identity this run's evidence was produced under.  The
    # product path binds it into the research checkpoint, the journal artifact
    # and the Candidate handoff so no downstream consumer can reuse work that
    # the revised targets no longer justify.
    revision_journal: RevisionJournalV1 = field(default_factory=RevisionJournalV1)
    revision_ingest_outcomes: list[dict[str, Any]] = field(default_factory=list)
    revision_ingest_failures: list[str] = field(default_factory=list)


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
        max_wall_clock_seconds: float | None = None,
    ) -> None:
        self._runtime = runtime
        self._max_turns = max_turns
        self._max_wall_clock_seconds = max_wall_clock_seconds

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

        # Start the deadline before the linear prefix so the public wall-clock
        # budget covers the whole Research phase.  It is checked only at node
        # boundaries, after each atomic repository/model/tool transaction has
        # returned.
        deadline = (
            time.monotonic() + float(self._max_wall_clock_seconds)
            if self._max_wall_clock_seconds and self._max_wall_clock_seconds > 0
            else None
        )

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
                revision_journal=loop.revision_journal,
                revision_ingest_outcomes=list(loop.revision_ingest_outcomes),
                revision_ingest_failures=list(loop.revision_ingest_failures),
            )

        # --- linear prefix --------------------------------------------------
        state.update(input_resolution_node(state, runtime=runtime))
        state.update(intent_compiler_node(state, runtime=runtime))
        prior_symbol_index = loop.symbol_index
        prior_source_manifest = loop.source_manifest
        index_update = repository_indexer_node(state, runtime=runtime)
        inferred_scope = index_update.pop("_implementation_scope", None)
        index_update.pop("_implementation_scope_path", None)
        inferred_scope_symbols = index_update.pop("_implementation_scope_symbols", None)
        rebuilt_symbol_index = index_update.pop("_symbol_index", None)
        rebuilt_source_manifest = index_update.pop("_source_manifest", None)
        if prior_symbol_index is not None and rebuilt_symbol_index is not None:
            if str(getattr(prior_symbol_index, "content_digest", "") or "") != str(
                getattr(rebuilt_symbol_index, "content_digest", "") or ""
            ):
                raise ValueError("resume_symbol_index_digest_mismatch")
        loop.symbol_index = rebuilt_symbol_index or prior_symbol_index
        loop.source_manifest = rebuilt_source_manifest or prior_source_manifest
        index_update.pop("_source_manifest_path", None)
        state.update(index_update)
        if inferred_scope is not None:
            loop.implementation_scope = inferred_scope
        if inferred_scope_symbols:
            loop.implementation_scope_symbols = tuple(
                dict(item) for item in inferred_scope_symbols if isinstance(item, dict)
            )
        state.update(research_agenda_builder_node(
            state,
            runtime=runtime,
            implementation_scope=loop.implementation_scope,
            behavior_graph=loop.behavior_graph,
        ))
        _refresh_acquisition_ledger(loop, state)
        if prior_source_manifest is not None and loop.source_manifest is not None:
            if str(getattr(prior_source_manifest, "content_digest", "") or "") != str(
                getattr(loop.source_manifest, "content_digest", "") or ""
            ):
                raise ValueError("resume_source_manifest_digest_mismatch")
        _refresh_intent_coverage_scheduler(
            loop,
            state,
            remaining_budget_turns=max(0, self._max_turns),
        )

        # --- research loop --------------------------------------------------
        routes: list[str] = []
        turns_executed = 0
        terminated = False
        termination_reason = ""
        # R10: the harness owns the run's proposal budget and reviewer hook.
        revision_budget_remaining = DEFAULT_REVISION_PROPOSAL_BUDGET
        revision_semantic_verifier = getattr(
            runtime, "revision_semantic_verifier", None
        )

        while turns_executed < self._max_turns:
            # Recompute the intent ledger at the scheduling boundary.  This
            # makes the scheduler an input to the live loop rather than a
            # post-hoc report emitted only at termination.
            _refresh_intent_coverage_scheduler(
                loop,
                state,
                remaining_budget_turns=max(0, self._max_turns - turns_executed),
                current_action_is_novelty=True,
            )
            if deadline is not None and time.monotonic() >= deadline:
                terminated = True
                if bool(loop.intent_schedule.get("candidate_handoff_ready", False)):
                    termination_reason = _mark_trusted_terminal(
                        loop, state, reason="candidate_handoff_partial"
                    )
                else:
                    termination_reason = "wall_clock_deadline"
                    state["status"] = "incomplete"
                    state["blocked_reason"] = "wall_clock_deadline"
                break
            if bool(loop.intent_schedule.get("candidate_handoff_ready", False)):
                terminated = True
                termination_reason = _mark_trusted_terminal(
                    loop, state, reason="candidate_handoff_partial"
                )
                break
            active_obligation_id = state.get("active_obligation_id", "")
            if not active_obligation_id:
                terminated = True
                termination_reason = _mark_trusted_terminal(
                    loop, state, reason="no_active_obligation"
                )
                break

            # Supervisor + policy merge.
            supervisor_update = research_supervisor_node(
                state,
                runtime=runtime,
                per_obligation_budgets=loop.per_obligation_budgets,
                active_issue=loop.active_issue,
                recent_observations=tuple(loop.recent_observations[-5:]),
                observation_history=tuple(loop.observation_history),
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
                state["blocked_reason"] = _research_block_root_code(
                    loop,
                    active_obligation_id=active_obligation_id,
                )
                break
            if decision.action == "COMPILE_EVIDENCE":
                partial_retry = _is_partial_compile_retry(
                    loop, active_obligation_id
                )
                compile_update = compile_candidate_node(
                    state,
                    runtime=runtime,
                    behavior_graph=loop.behavior_graph,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                    implementation_scope=loop.implementation_scope,
                    symbol_index=loop.symbol_index,
                    source_manifest=loop.source_manifest,
                    prior_compiled_evidence=loop.compiled_evidence.get(
                        active_obligation_id
                    ),
                )
                compiled_evidence = compile_update.pop("_compiled_evidence", None)
                partial_evidence = compile_update.pop("_partial_evidence", None)
                gap_accepted = compile_update.pop("_gap_accepted", None)
                _append_compile_attempt(
                    loop,
                    compile_update.pop("_compile_attempt", None),
                )
                _note_post_partial_retry(
                    loop,
                    active_obligation_id,
                    was_partial=partial_retry,
                )
                state.update(compile_update)
                _record_intent_compile_event(
                    loop,
                    partial_evidence or compiled_evidence,
                )
                if partial_evidence is not None:
                    _store_evidence_sidecar(loop, partial_evidence)
                if compiled_evidence is not None:
                    _store_evidence_sidecar(loop, compiled_evidence)
                _refresh_acquisition_ledger(loop, state)
                state.update(_refresh_loop_quality(loop, state))
                if state.get("status") == "blocked":
                    terminated = True
                    termination_reason = "evidence_compile_blocked"
                    break
                if compiled_evidence is not None or gap_accepted is True:
                    next_obl = _next_loop_obligation(loop, active_obligation_id)
                    if next_obl is None:
                        terminated = True
                        termination_reason = _mark_trusted_terminal(
                            loop, state, reason="all_obligations_terminal"
                        )
                        break
                    state["active_obligation_id"] = next_obl
                    loop.active_issue = None
                    loop.recent_observations.clear()
                elif partial_evidence is not None:
                    next_obl = _next_loop_obligation(loop, active_obligation_id)
                    if next_obl is None:
                        # Every obligation is terminal (supported / partial
                        # with nothing left to research / gap / blocked):
                        # ``partial`` with no actionable missing information
                        # is a terminal status (design 8.4).  Re-entering the
                        # supervisor would only repeat exact calls until
                        # fallback exhaustion.
                        terminated = True
                        termination_reason = _mark_trusted_terminal(
                            loop, state, reason="all_obligations_terminal"
                        )
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
                if _active_obligation_partial(
                    runtime.agenda,
                    active_obligation_id,
                    promotion_records=tuple(
                        getattr(loop.observation_promotion_ledger, "records", ())
                        or ()
                    ),
                ):
                    next_obl = _next_loop_obligation(loop, active_obligation_id)
                    if next_obl is None or next_obl == active_obligation_id:
                        terminated = True
                        termination_reason = _mark_trusted_terminal(
                            loop, state, reason="all_obligations_terminal"
                        )
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
                next_obl = _next_loop_obligation(loop, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = _mark_trusted_terminal(
                        loop, state, reason="all_obligations_terminal"
                    )
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
            _append_observation_history(loop, observations)
            for observation in observations:
                record_executed_research_action(
                    loop.runtime.agenda,
                    obligation_id=observation.obligation_id,
                    action=_action_for_tool(observation.tool_name),
                    observations=[observation],
                )
            for call in pending:
                loop.recent_tool_call_ids.add(call.tool_call_id)
            state["pending_tool_calls"] = []
            state["tool_call_trace_refs"] = list(state.get("tool_call_trace_refs", [])) + trace_refs
            # R10: same harness ingestion boundary as the LangGraph subgraph.
            revision_budget_remaining = _ingest_target_revisions(
                loop,
                runtime,
                state,
                pending,
                budget_remaining=revision_budget_remaining,
                semantic_verifier=revision_semantic_verifier,
            )

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
                symbol_index=loop.symbol_index,
            )
            state.update(bg_update)
            _refresh_acquisition_ledger(loop, state)

            # Quality state selector.
            quality_update = _refresh_loop_quality(loop, state)
            state.update(quality_update)

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
                termination_reason = _mark_trusted_terminal(
                    loop, state, reason="all_obligations_terminal"
                )
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
                next_obl = _next_loop_obligation(loop, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = _mark_trusted_terminal(
                        loop, state, reason="all_obligations_terminal"
                    )
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
                partial_retry = _is_partial_compile_retry(
                    loop, active_obligation_id
                )
                compile_update = compile_candidate_node(
                    state,
                    runtime=runtime,
                    behavior_graph=loop.behavior_graph,
                    active_obligation_id=active_obligation_id,
                    gain_tracker=loop.gain_tracker,
                    implementation_scope=loop.implementation_scope,
                    symbol_index=loop.symbol_index,
                    source_manifest=loop.source_manifest,
                    prior_compiled_evidence=loop.compiled_evidence.get(
                        active_obligation_id
                    ),
                )
                compiled_evidence = compile_update.pop("_compiled_evidence", None)
                partial_evidence = compile_update.pop("_partial_evidence", None)
                gap_accepted = compile_update.pop("_gap_accepted", None)
                _append_compile_attempt(
                    loop,
                    compile_update.pop("_compile_attempt", None),
                )
                _note_post_partial_retry(
                    loop,
                    active_obligation_id,
                    was_partial=partial_retry,
                )
                state.update(compile_update)
                _record_intent_compile_event(
                    loop,
                    partial_evidence or compiled_evidence,
                )
                if partial_evidence is not None:
                    _store_evidence_sidecar(loop, partial_evidence)
                if compiled_evidence is not None:
                    _store_evidence_sidecar(loop, compiled_evidence)
                    # Move to the next unresolved obligation.
                    next_obl = _next_loop_obligation(loop, active_obligation_id)
                    if next_obl is None:
                        terminated = True
                        termination_reason = _mark_trusted_terminal(
                            loop, state, reason="all_obligations_terminal"
                        )
                        break
                    state["active_obligation_id"] = next_obl
                    loop.active_issue = None
                    loop.recent_observations.clear()
                    _refresh_acquisition_ledger(loop, state)
                    state.update(_refresh_loop_quality(loop, state))
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
                    next_obl = _next_loop_obligation(loop, active_obligation_id)
                    if next_obl is None:
                        terminated = True
                        termination_reason = _mark_trusted_terminal(
                            loop, state, reason="all_obligations_terminal"
                        )
                        break
                    if next_obl != active_obligation_id:
                        state["active_obligation_id"] = next_obl
                        loop.active_issue = None
                        loop.recent_observations.clear()
                    turns_executed += 1
                    loop.turn_index += 1
                    _refresh_acquisition_ledger(loop, state)
                    state.update(_refresh_loop_quality(loop, state))
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
                next_obl = _next_loop_obligation(loop, active_obligation_id)
                if next_obl is None:
                    terminated = True
                    termination_reason = _mark_trusted_terminal(
                        loop, state, reason="all_obligations_terminal"
                    )
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

        if loop.revision_ingest_failures and state.get("status") == "trusted":
            # Same rule as the subgraph terminator: a revision the live state
            # could not use is never a trusted terminal state.
            state["status"] = "incomplete"
            state["blocked_reason"] = "revision_ingest_failed"

        return ResearchLoopResult(
            loop_state=loop,
            final_state=state,
            turns_executed=turns_executed,
            terminated=terminated,
            termination_reason=termination_reason,
            decision_trace=loop.decision_trace,
            policy_merge_trace=loop.policy_merge_trace,
            evidence_critic_routes=routes,
            revision_journal=loop.revision_journal,
            revision_ingest_outcomes=list(loop.revision_ingest_outcomes),
            revision_ingest_failures=list(loop.revision_ingest_failures),
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

    def __init__(
        self,
        runtime: ResearchGraphRuntime,
        *,
        max_turns: int,
        max_wall_clock_seconds: float | None = None,
    ) -> None:
        self.runtime = runtime
        self.max_turns = max_turns
        self.max_wall_clock_seconds = max_wall_clock_seconds
        self.deadline = (
            time.monotonic() + float(max_wall_clock_seconds)
            if max_wall_clock_seconds and max_wall_clock_seconds > 0
            else None
        )
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
        # R10: the harness owns the proposal budget and the independent
        # semantic reviewer hook; the loop may only submit proposals.
        self.revision_budget_remaining: int = DEFAULT_REVISION_PROPOSAL_BUDGET
        self.revision_semantic_verifier: Callable[[Any, Any], bool] | None = (
            getattr(runtime, "revision_semantic_verifier", None)
        )


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
    prior_symbol_index = ctx.loop_state.symbol_index if ctx.loop_state is not None else None
    prior_source_manifest = ctx.loop_state.source_manifest if ctx.loop_state is not None else None
    index_update = repository_indexer_node(state, runtime=runtime)
    inferred_scope = index_update.pop("_implementation_scope", None)
    index_update.pop("_implementation_scope_path", None)
    inferred_scope_symbols = index_update.pop("_implementation_scope_symbols", None)
    rebuilt_symbol_index = index_update.pop("_symbol_index", None)
    rebuilt_source_manifest = index_update.pop("_source_manifest", None)
    if prior_symbol_index is not None and rebuilt_symbol_index is not None:
        if str(getattr(prior_symbol_index, "content_digest", "") or "") != str(
            getattr(rebuilt_symbol_index, "content_digest", "") or ""
        ):
            raise ValueError("resume_symbol_index_digest_mismatch")
    if ctx.loop_state is not None:
        ctx.loop_state.symbol_index = rebuilt_symbol_index or prior_symbol_index
        ctx.loop_state.source_manifest = rebuilt_source_manifest or prior_source_manifest
    index_update.pop("_source_manifest_path", None)
    update.update(index_update)
    if inferred_scope is not None and ctx.loop_state is not None:
        ctx.loop_state.implementation_scope = inferred_scope
    if inferred_scope_symbols and ctx.loop_state is not None:
        ctx.loop_state.implementation_scope_symbols = tuple(
            dict(item) for item in inferred_scope_symbols if isinstance(item, dict)
        )
    update.update(research_agenda_builder_node(
        state,
        runtime=runtime,
        implementation_scope=(ctx.loop_state.implementation_scope if ctx.loop_state else None),
        behavior_graph=(ctx.loop_state.behavior_graph if ctx.loop_state else None),
    ))
    if ctx.loop_state is not None:
        _refresh_acquisition_ledger(ctx.loop_state, update)
        if prior_source_manifest is not None and ctx.loop_state.source_manifest is not None:
            if str(getattr(prior_source_manifest, "content_digest", "") or "") != str(
                getattr(ctx.loop_state.source_manifest, "content_digest", "") or ""
            ):
                raise ValueError("resume_source_manifest_digest_mismatch")
        _refresh_intent_coverage_scheduler(
            ctx.loop_state,
            update,
            remaining_budget_turns=max(0, ctx.max_turns - ctx.turns_executed),
        )
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

    _refresh_intent_coverage_scheduler(
        loop,
        state,
        remaining_budget_turns=max(0, ctx.max_turns - ctx.turns_executed),
        current_action_is_novelty=True,
    )

    # Check the wall-clock deadline only at a supervisor boundary, after the
    # prior tool/observation/compile transaction has completed.
    if ctx.deadline is not None and time.monotonic() >= ctx.deadline:
        ctx.terminated = True
        if bool(loop.intent_schedule.get("candidate_handoff_ready", False)):
            ctx.termination_reason = _mark_trusted_terminal(
                loop, state, reason="candidate_handoff_partial"
            )
        else:
            ctx.termination_reason = "wall_clock_deadline"
            state["status"] = "incomplete"
            state["blocked_reason"] = "wall_clock_deadline"
        ctx.supervisor_route = "no_tool_calls"
        return {
            "status": state.get("status", "incomplete"),
            "blocked_reason": state.get("blocked_reason", ""),
        }

    if bool(loop.intent_schedule.get("candidate_handoff_ready", False)):
        ctx.terminated = True
        ctx.termination_reason = _mark_trusted_terminal(
            loop, state, reason="candidate_handoff_partial"
        )
        ctx.supervisor_route = "no_tool_calls"
        return {
            "status": state.get("status", "incomplete"),
            "blocked_reason": state.get("blocked_reason", ""),
        }

    active_obligation_id = state.get("active_obligation_id", "")
    if not active_obligation_id:
        ctx.terminated = True
        ctx.termination_reason = _mark_trusted_terminal(
            loop, state, reason="no_active_obligation"
        )
        ctx.supervisor_route = "no_tool_calls"
        return {"status": state.get("status", "blocked")}

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
        observation_history=tuple(loop.observation_history),
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
        return {
            "status": "blocked",
            "blocked_reason": _research_block_root_code(
                loop,
                active_obligation_id=active_obligation_id,
            ),
        }
    if decision.action == "RECORD_GAP":
        # A partial obligation (claims already authorized) must never be
        # routed to the gap finalizer: the record-gap tool rejects
        # ``gap_contradicts_authorized_positive_claim`` fail-closed and the
        # loop would churn RECORD_GAP until max_turns.  Route it to the
        # advancer, which terminates when every obligation is terminal
        # (``partial`` with no actionable missing info is terminal per
        # design 8.4).
        if _active_obligation_partial(
            runtime.agenda,
            active_obligation_id,
            promotion_records=tuple(
                getattr(loop.observation_promotion_ledger, "records", ()) or ()
            ),
        ):
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
    _append_observation_history(loop, observations)
    for observation in observations:
        record_executed_research_action(
            loop.runtime.agenda,
            obligation_id=observation.obligation_id,
            action=_action_for_tool(observation.tool_name),
            observations=[observation],
        )
    for call in pending:
        loop.recent_tool_call_ids.add(call.tool_call_id)
    ctx._observations = list(observations)
    # R10: a submitted revision proposal is ingested here, at the harness
    # boundary, not by the tool that wrote it.  Ingestion authenticates the
    # cited refs, spends the run's proposal budget and rebinds the loop state
    # to the revised targets before the next supervisor turn reads them.
    ctx.revision_budget_remaining = _ingest_target_revisions(
        loop,
        runtime,
        state,
        pending,
        budget_remaining=ctx.revision_budget_remaining,
        semantic_verifier=ctx.revision_semantic_verifier,
    )
    existing_refs = list(state.get("tool_call_trace_refs", []))
    return {
        "pending_tool_calls": [],
        "tool_call_trace_refs": existing_refs + trace_refs,
    }


def _ingest_target_revisions(
    loop: "ResearchLoopState",
    runtime: ResearchGraphRuntime,
    state: AgentStateV3,
    pending: Sequence[Any],
    *,
    budget_remaining: int = DEFAULT_REVISION_PROPOSAL_BUDGET,
    semantic_verifier: Callable[[Any, Any], bool] | None = None,
) -> int:
    """Harness-side ingestion of the revision proposals this turn submitted.

    Returns the run's remaining proposal budget.  Both loop implementations
    (the LangGraph subgraph and the direct driver) call this at their own tool
    boundary so a submitted proposal is applied exactly once, by the harness.
    """

    if not any(
        str(getattr(call, "tool_name", "") or "") == REVISION_PROPOSAL_TOOL_NAME
        for call in pending
    ):
        return budget_remaining
    from code2paper.agentic.research_revision_ingest import (
        ingest_revision_submissions,
        write_revision_ingest_result,
    )

    try:
        tool_ctx = runtime.tool_context(behavior_graph=loop.behavior_graph)
        artifact_root = getattr(tool_ctx, "artifact_root", None)
    except Exception:  # pragma: no cover - defensive: keep the loop alive
        artifact_root = getattr(runtime, "artifact_root", None)
    try:
        result = ingest_revision_submissions(
            runtime=runtime,
            artifact_root=artifact_root,
            journal=loop.revision_journal,
            remaining_budget=budget_remaining,
            semantic_verifier=semantic_verifier,
            compiled_by_obligation=loop.compiled_evidence,
            # The relevance check reads the behavior graph the run actually
            # built; a proposal may only add predicates the run has extracted.
            behavior_graph=loop.behavior_graph,
            symbol_index=loop.symbol_index,
        )
    except Exception as exc:  # noqa: BLE001 — ingestion failure must be visible
        loop.revision_ingest_failures.append(
            f"revision_ingest_failed:{type(exc).__name__}"
        )
        return budget_remaining
    loop.revision_journal = result.journal
    loop.revision_ingest_outcomes.extend(
        outcome.model_dump(mode="json") for outcome in result.outcomes
    )
    for failure in result.ledger_failures:
        if failure not in loop.revision_ingest_failures:
            loop.revision_ingest_failures.append(failure)
    for outcome in result.applied_outcomes():
        _rebind_loop_after_revision(loop, state, outcome)
    if result.outcomes:
        try:
            write_revision_ingest_result(
                artifact_root,
                result,
                ingestion_index=len(loop.revision_ingest_outcomes) - len(result.outcomes),
            )
        except Exception:  # pragma: no cover - defensive artifact write
            pass
    return result.budget_remaining


def _rebind_loop_after_revision(
    loop: "ResearchLoopState",
    state: AgentStateV3,
    outcome: Any,
) -> None:
    """Re-bind the loop state to the targets the revision actually left behind.

    §15.6: a revision changes the intent graph *and* everything derived from
    the old targets.  Two loop-local derivations are re-bound here:

    * the bounded post-partial retry counter was earned against targets that
      no longer exist, so the revised obligation starts its own retry (the old
      count stays recorded in the ingestion outcome);
    * compiled evidence whose targets no longer resolve is dropped, and the
      observation promotion ledger is re-derived from the revised agenda, so
      observations promoted under the old targets cannot keep supporting
      claims the revision removed.
    """

    obligation_id = str(getattr(outcome, "parent_obligation_id", "") or "")
    if not obligation_id:
        return
    loop.post_partial_retry_counts.pop(obligation_id, None)
    row = next(
        (
            item
            for item in (getattr(outcome, "revalidation_rows", ()) or ())
            if str(item.get("obligation_id") or "") == obligation_id
        ),
        {},
    )
    unresolved = tuple(
        str(value)
        for value in (row.get("unresolved_target_ids") or ())
        if str(value).strip()
    )
    must_revalidate = tuple(
        str(value)
        for value in (row.get("claim_ids_requiring_revalidation") or ())
        if str(value).strip()
    )
    if unresolved or must_revalidate:
        # The compilation was produced for the removed/changed targets.
        loop.compiled_evidence.pop(obligation_id, None)
    loop.revision_rebind_notes.append({
        "revision_id": str(getattr(outcome, "revision_id", "") or ""),
        "obligation_id": obligation_id,
        "unresolved_target_ids": list(unresolved),
        "claim_ids_requiring_revalidation": list(must_revalidate),
        "compiled_evidence_dropped": bool(unresolved or must_revalidate),
    })
    try:
        _refresh_acquisition_ledger(loop, state)
    except Exception as exc:  # noqa: BLE001 — a stale ledger must not be silent
        loop.revision_ingest_failures.append(
            f"revision_promotion_ledger_rebind_failed:{type(exc).__name__}"
        )
    agenda_refresh = getattr(loop.runtime.agenda, "refresh_content_digest", None)
    if callable(agenda_refresh):
        agenda_refresh()


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
        symbol_index=loop.symbol_index,
    )
    update.update(bg_update)

    _refresh_acquisition_ledger(loop, update)

    quality_update = _refresh_loop_quality(loop, state)
    update.update(quality_update)

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
        ctx.termination_reason = _mark_trusted_terminal(
            loop, state, reason="all_obligations_terminal"
        )
        ctx.critic_route = "ready_to_author"
        return {"status": state.get("status", "blocked")}

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

    partial_retry = _is_partial_compile_retry(loop, active_obligation_id)
    compile_update = compile_candidate_node(
        state,
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        active_obligation_id=active_obligation_id,
        gain_tracker=loop.gain_tracker,
        implementation_scope=loop.implementation_scope,
        symbol_index=loop.symbol_index,
        source_manifest=loop.source_manifest,
        prior_compiled_evidence=loop.compiled_evidence.get(active_obligation_id),
    )
    compiled_evidence = compile_update.pop("_compiled_evidence", None)
    partial_evidence = compile_update.pop("_partial_evidence", None)
    gap_accepted = compile_update.pop("_gap_accepted", None)
    _append_compile_attempt(
        loop,
        compile_update.pop("_compile_attempt", None),
    )
    _note_post_partial_retry(
        loop,
        active_obligation_id,
        was_partial=partial_retry,
    )

    _record_intent_compile_event(
        loop,
        partial_evidence or compiled_evidence,
    )

    if partial_evidence is not None:
        _store_evidence_sidecar(loop, partial_evidence)
    if compiled_evidence is not None:
        _store_evidence_sidecar(loop, compiled_evidence)
        # Success: route to advancer.  The advancer increments
        # turns_executed only when a next obligation exists.
        ctx.compile_route = "compiled"
        _refresh_acquisition_ledger(loop, compile_update)
        compile_update.update(_refresh_loop_quality(loop, compile_update))
        compile_update["loop_state_snapshot"] = snapshot_loop_state(loop)
        return compile_update
    if partial_evidence is not None:
        # The advancer performs the round-robin move and accounting.
        ctx.compile_route = "partial"
        _refresh_acquisition_ledger(loop, compile_update)
        compile_update.update(_refresh_loop_quality(loop, compile_update))
        compile_update["loop_state_snapshot"] = snapshot_loop_state(loop)
        return compile_update

    # No compiled evidence: compile_candidate_node already called
    # gap_finalizer_node internally.  Do NOT route to gap_finalizer.
    if gap_accepted is False:
        # Gap rejected: keep researching the current obligation.
        ctx.compile_route = "rejected"
        ctx.turns_executed += 1
        loop.turn_index += 1
        _refresh_acquisition_ledger(loop, compile_update)
        compile_update.update(_refresh_loop_quality(loop, compile_update))
        compile_update["loop_state_snapshot"] = snapshot_loop_state(loop)
        return compile_update

    if compile_update.get("status") == "blocked":
        ctx.terminated = True
        ctx.termination_reason = "gap_finalizer_blocked"
        ctx.compile_route = "blocked"
        compile_update["loop_state_snapshot"] = snapshot_loop_state(loop)
        return compile_update

    # Gap accepted: route to advancer (same as compiled-success).
    ctx.compile_route = "compiled"
    _refresh_acquisition_ledger(loop, compile_update)
    compile_update.update(_refresh_loop_quality(loop, compile_update))
    compile_update["loop_state_snapshot"] = snapshot_loop_state(loop)
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

    next_obl = _next_loop_obligation(loop, active_obligation_id)
    if next_obl is None or (
        # The supervisor exhausted every strategy for a partial obligation
        # (RECORD_GAP decision routed as ``partial_gap``): the round-robin
        # returning the same obligation is not a fresh depth pass, it is the
        # same dead end.  ``partial`` with claims is a terminal status
        # (design 8.4) once no further strategy exists.
        next_obl == active_obligation_id
        and _active_obligation_partial(
            runtime.agenda,
            active_obligation_id,
            promotion_records=tuple(
                getattr(loop.observation_promotion_ledger, "records", ()) or ()
            ),
        )
        and getattr(ctx, "supervisor_route", "") == "partial_gap"
    ):
        ctx.terminated = True
        ctx.termination_reason = _mark_trusted_terminal(
            loop, state, reason="all_obligations_terminal"
        )
        ctx.advancer_route = "no_next"
        return {"status": state.get("status", "blocked")}

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
    if ctx.termination_reason in (
        "max_turns_reached",
        "wall_clock_deadline",
        "candidate_handoff_partial",
    ):
        final_state["status"] = "incomplete"
        final_state["blocked_reason"] = ctx.termination_reason
    elif ctx.termination_reason in ("no_active_obligation", "all_obligations_terminal", "ready_to_author"):
        if state.get("status") == "incomplete" and state.get("blocked_reason") == "candidate_handoff_partial":
            final_state["status"] = "incomplete"
            final_state["blocked_reason"] = "candidate_handoff_partial"
        else:
            final_state["status"] = "trusted"
    elif ctx.termination_reason in ("stop_blocked", "gap_finalizer_blocked", "evidence_critic_blocked", "no_tool_calls_no_terminal", "intent_coverage_blocked"):
        final_state["status"] = "blocked"
    if loop.revision_ingest_failures and final_state.get("status") == "trusted":
        # A revision the journal holds but the live research state could not
        # use (or a ledger that could not be re-read) leaves the run describing
        # targets it did not actually research.  That is never a trusted
        # terminal state.
        final_state["status"] = "incomplete"
        final_state["blocked_reason"] = "revision_ingest_failed"
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
        revision_journal=loop.revision_journal,
        revision_ingest_outcomes=list(loop.revision_ingest_outcomes),
        revision_ingest_failures=list(loop.revision_ingest_failures),
    )


# ---------------------------------------------------------------------------
# LangGraph StateGraph wrapper
# ---------------------------------------------------------------------------


def build_research_subgraph(
    runtime: ResearchGraphRuntime,
    *,
    max_turns: int = 50,
    max_wall_clock_seconds: float | None = None,
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

    ctx = _ResearchGraphContext(
        runtime,
        max_turns=max_turns,
        max_wall_clock_seconds=max_wall_clock_seconds,
    )
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
    max_wall_clock_seconds: float | None = None,
    loop_state: "ResearchLoopState | None" = None,
) -> ResearchLoopResult:
    """Run the research loop without going through LangGraph.

    Convenience wrapper for tests.  Equivalent to::

        ResearchLoopDriver(runtime, max_turns=max_turns).run(
            initial_state, loop_state=loop_state,
        )
    """

    return ResearchLoopDriver(
        runtime,
        max_turns=max_turns,
        max_wall_clock_seconds=max_wall_clock_seconds,
    ).run(
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


def _obligation_is_terminal(
    item: Any,
    *,
    promotion_records: tuple[Any, ...] | None = None,
    receipt_verifier: Any | None = None,
) -> bool:
    """Whether an obligation needs no further research.

    ``supported`` / ``explicit_gap`` / ``blocked`` are terminal by design
    (8.4).  A ``partial`` obligation is terminal only when nothing remains
    to research (no missing information): claims are authorized and the
    writing boundary plus required qualifiers are clear.  A partial
    obligation that still lists missing information is revisitable -- the
    supervisor may still have a fresh strategy for it (e.g. a call trace
    for an unresolved ``call_relation``).
    """

    if _has_terminal_stop(item):
        # The bounded search stopped.  This is terminal for scheduling and
        # never authorizes a negative conclusion (that still requires the
        # receipt-backed proof below).
        return True
    # ``None`` means a legacy caller has no promotion ledger and may use the
    # agenda's compatibility claim ids.  An explicit empty tuple means the
    # production ledger was consulted and contains no promotion for this
    # obligation; it must not be treated as repository evidence.
    promoted_claim_ids = (
        tuple(item.supported_claim_ids or ())
        if promotion_records is None
        else ()
    )
    proof = evaluate_obligation_terminal_proof(
        item,
        promotion_records=promotion_records or (),
        promoted_claim_ids=promoted_claim_ids,
        receipt_verifier=receipt_verifier,
    )
    return proof.terminal


def _is_organization_preference(item: Any) -> bool:
    """Author story-order headings are not code-search obligations."""

    if str(getattr(item, "priority", "") or "") != "preference":
        return False
    return "ORGANIZATION" in str(getattr(item, "obligation_id", "") or "").upper()


def _records_for_obligation(
    promotion_records: tuple[Any, ...] | None,
    obligation_id: str,
) -> tuple[Any, ...] | None:
    """Return one obligation's promotion records without losing no-records."""

    if promotion_records is None:
        return None
    return tuple(
        record
        for record in promotion_records
        if str(
            (
                record.get("obligation_id", "")
                if isinstance(record, dict)
                else getattr(record, "obligation_id", "")
            )
            or ""
        )
        == str(obligation_id)
    )


def _has_unresolved_must_cover(
    agenda: ResearchAgendaV1,
    *,
    promotion_records: tuple[Any, ...] | None = None,
    receipt_verifier: Any | None = None,
) -> bool:
    return any(
        item.priority == "must_cover"
        and not _obligation_is_terminal(
            item,
            promotion_records=_records_for_obligation(
                promotion_records, item.obligation_id
            ),
            receipt_verifier=receipt_verifier,
        )
        for item in agenda.items
    )


def _obligation_is_researchable_now(
    item: Any,
    *,
    defer_organization_preference: bool,
    promotion_records: tuple[Any, ...] | None = None,
    receipt_verifier: Any | None = None,
) -> bool:
    if _obligation_is_terminal(
        item,
        promotion_records=_records_for_obligation(
            promotion_records, str(getattr(item, "obligation_id", "") or "")
        ),
        receipt_verifier=receipt_verifier,
    ):
        return False
    if defer_organization_preference and _is_organization_preference(item):
        return False
    return True


def _obligation_claim_ids(
    item: Any,
    *,
    promotion_records: tuple[Any, ...] | None,
) -> tuple[str, ...]:
    record_claims = ()
    if promotion_records is not None:
        record_claims = tuple(
            str(value).strip()
            for record in _records_for_obligation(
                promotion_records,
                str(getattr(item, "obligation_id", "") or ""),
            ) or ()
            for value in (
                record.get("claim_ids", ())
                if isinstance(record, dict)
                else (getattr(record, "claim_ids", ()) or ())
            )
            if str(value).strip()
        )
    agenda_claims = tuple(
        str(value).strip()
        for value in (getattr(item, "supported_claim_ids", ()) or ())
        if str(value).strip()
    )
    return tuple(dict.fromkeys((*record_claims, *agenda_claims)))


def _has_terminal_stop(item: Any) -> bool:
    """Whether the search for this obligation reached a typed bounded stop.

    R9: a stop record ends the *search* without proving absence.  Scheduling
    must honor it (no infinite churn), while the proof evaluator still refuses
    to treat it as negative evidence.
    """

    return any(
        str(value).startswith("terminal_stop:")
        for value in (getattr(item, "missing_information", ()) or ())
        if str(value).strip()
    )


def _obligation_needs_research(
    item: Any,
    *,
    promotion_records: tuple[Any, ...] | None,
    post_partial_retry_counts: Mapping[str, int] | None,
    receipt_verifier: Any | None = None,
) -> bool:
    """Whether an item still consumes a research scheduling slot."""

    status = str(getattr(item, "status", "") or "")
    if status == "explicit_gap":
        # R9: the status marker is not proof.  Only a receipt that still
        # re-authenticates against the current revision's ledger ends the
        # search for this obligation; a legacy or damaged gap keeps consuming
        # a scheduling slot instead of being treated as finished.
        return not evaluate_obligation_terminal_proof(
            item, receipt_verifier=receipt_verifier
        ).explicit_gap_bound
    if status == "blocked":
        return False
    if status in {"pending", "in_progress"}:
        # A typed stop record means the bounded search for this obligation is
        # finished; keep partial-retry semantics for ``partial`` items only.
        return not _has_terminal_stop(item)
    claim_ids = _obligation_claim_ids(item, promotion_records=promotion_records)
    if status == "supported":
        # A status without a promotion is not a safe supported handoff.
        return not bool(claim_ids)
    if status == "partial":
        if not claim_ids:
            return True
        count = max(
            0,
            int(
                (post_partial_retry_counts or {}).get(
                    str(getattr(item, "obligation_id", "") or ""),
                    0,
                )
                or 0
            ),
        )
        return count < POST_PARTIAL_RETRY_LIMIT
    return True


def _core_candidate_shape_ready(
    agenda: ResearchAgendaV1,
    *,
    promotion_records: tuple[Any, ...] | None,
    post_partial_retry_counts: Mapping[str, int] | None,
) -> bool:
    """Cheap scheduling predicate; the full handoff validator runs at refresh."""

    core_items = [item for item in agenda.items if item.priority == "must_cover"]
    if not core_items:
        return False
    for item in core_items:
        if _obligation_needs_research(
            item,
            promotion_records=promotion_records,
            post_partial_retry_counts=post_partial_retry_counts,
        ):
            return False
        if item.status not in {"supported", "partial"}:
            return False
        if not _obligation_claim_ids(item, promotion_records=promotion_records):
            return False
    return True


def _next_unresolved_obligation(
    agenda: ResearchAgendaV1,
    current_id: str,
    *,
    promotion_records: tuple[Any, ...] | None = None,
    post_partial_retry_counts: Mapping[str, int] | None = None,
    receipt_verifier: Any | None = None,
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
    core_needs = [
        item for item in items
        if item.priority == "must_cover"
        and _obligation_needs_research(
            item,
            promotion_records=promotion_records,
            post_partial_retry_counts=post_partial_retry_counts,
            receipt_verifier=receipt_verifier,
        )
    ]
    # Core breadth and the one partial retry always win over non-core story
    # work.  This is the key distinction from the old all-obligations loop.
    if core_needs:
        started = False
        for item in items:
            if not started:
                if item.obligation_id == current_id:
                    started = True
                continue
            if item in core_needs:
                return item.obligation_id
        return core_needs[0].obligation_id

    # Once the core shape is ready, the caller can hand off Candidate.  Do
    # not spend the remaining Research budget on should-cover/preference
    # items; those are persisted as deferred review work.
    if _core_candidate_shape_ready(
        agenda,
        promotion_records=promotion_records,
        post_partial_retry_counts=post_partial_retry_counts,
    ):
        return None

    # If a structural or qualifier blocker prevents Candidate, keep the old
    # fail-closed behavior and use remaining non-core items only as useful
    # work, while organization preferences remain last.
    defer_org = _has_unresolved_must_cover(
        agenda,
        promotion_records=promotion_records,
        receipt_verifier=receipt_verifier,
    )
    started = False
    for item in items:
        if not started:
            if item.obligation_id == current_id:
                started = True
            continue
        if _obligation_is_researchable_now(
            item,
            defer_organization_preference=defer_org,
            promotion_records=promotion_records,
            receipt_verifier=receipt_verifier,
        ):
            return item.obligation_id
    for item in items:
        if _obligation_is_researchable_now(
            item,
            defer_organization_preference=defer_org,
            promotion_records=promotion_records,
            receipt_verifier=receipt_verifier,
        ):
            return item.obligation_id
    for item in items:
        if not _obligation_is_terminal(
            item,
            promotion_records=_records_for_obligation(
                promotion_records, item.obligation_id
            ),
            receipt_verifier=receipt_verifier,
        ):
            return item.obligation_id
    return None


def _next_loop_obligation(
    loop: "ResearchLoopState",
    current_id: str,
) -> str | None:
    """Advance using the live promotion ledger as the terminal proof source."""

    return _next_unresolved_obligation(
        loop.runtime.agenda,
        current_id,
        promotion_records=tuple(
            getattr(loop.observation_promotion_ledger, "records", ()) or ()
        ),
        post_partial_retry_counts=loop.post_partial_retry_counts,
        receipt_verifier=_runtime_receipt_verifier(loop.runtime),
    )


def _runtime_receipt_verifier(runtime: Any) -> Any | None:
    """Build the ledger re-authentication adapter for one runtime."""

    tool_context = getattr(runtime, "tool_context", None)
    if not callable(tool_context):
        return None
    try:
        from code2paper.agentic.research_execution_ledger import (
            build_context_ledger_reader,
        )

        return build_context_ledger_reader(tool_context())
    except Exception:  # pragma: no cover - defensive: no reader, no proof
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
    "close_search_frontier": "RECORD_GAP",
    "record_explicit_code_gap": "RECORD_GAP",
    "check_obligation_coverage": "RECORD_GAP",
    "propose_target_revision": "PROPOSE_TARGET_REVISION",
}


def _action_for_tool(tool_name: str) -> str:
    return _TOOL_ACTION_MAP.get(tool_name, "SEARCH_SYMBOLS")


def record_executed_research_action(
    agenda: ResearchAgendaV1,
    *,
    obligation_id: str,
    action: ResearchAction | str,
    observations: Sequence[ResearchObservationV1],
) -> None:
    """Record a research action that actually executed.

    The agenda item's ``attempted_actions`` is the durable execution history
    consumed by gap reporting and Candidate eligibility.  It is updated only
    after tools ran: policy-rejected proposals never reach this helper, and
    a lone ``STOP_BLOCKED`` has no observation and therefore is not a
    research attempt.  ``success_empty`` and ``parse_failed`` observations
    still count as attempts because the tool did execute.

    Duplicate actions are collapsed while preserving execution order, a
    ``pending`` item advances to ``in_progress``, and ``no_progress_counter``
    / ``last_information_gain`` are kept in sync with the observation
    outcome.  Agenda items are persisted through the loop snapshot, so this
    ledger survives checkpoint/resume without being re-recorded.
    """

    if not obligation_id:
        return
    item = next(
        (
            candidate
            for candidate in agenda.items
            if candidate.obligation_id == obligation_id
        ),
        None,
    )
    if item is None:
        return
    relevant = tuple(
        observation
        for observation in observations
        if observation.obligation_id == obligation_id
    )
    if not relevant:
        return
    action_value = str(action or "").strip()
    if action_value and action_value not in item.attempted_actions:
        item.attempted_actions.append(action_value)  # type: ignore[arg-type]
    if item.status == "pending":
        item.status = "in_progress"
    gains = [
        observation
        for observation in relevant
        if observation.status == "success"
        and (
            observation.result_refs
            or observation.exact_span_ids
            or int(getattr(observation.diagnostics, "candidate_count", 0) or 0) > 0
        )
    ]
    if gains:
        item.no_progress_counter = 0
        item.last_information_gain = (
            f"{gains[-1].tool_name}:{gains[-1].observation_id}"
        )
    else:
        item.no_progress_counter = int(item.no_progress_counter or 0) + len(relevant)
        if not item.last_information_gain:
            item.last_information_gain = (
                f"no_gain:{relevant[-1].tool_name}:{relevant[-1].status}"
            )


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
    agenda: ResearchAgendaV1,
    active_obligation_id: str,
    *,
    promotion_records: tuple[Any, ...] | None = None,
) -> bool:
    """Whether the active obligation has promoted partial claims.

    This is intentionally weaker than ``evaluate_obligation_terminal_proof``:
    a partial with unresolved fields must not be sent through the explicit-gap
    finalizer, because that would contradict its already-authorized claims.
    """

    for item in agenda.items:
        if item.obligation_id == active_obligation_id:
            claims = _obligation_claim_ids(
                item,
                promotion_records=promotion_records,
            )
            return item.status == "partial" and bool(claims)
    return False
