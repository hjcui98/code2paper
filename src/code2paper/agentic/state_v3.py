"""LangGraph state schema and adapters for the V3 research plane.

Implements ``AgentStateV3`` from design section 5 and the R0.3 migration
boundary:

- new path gated by feature flag ``agentic_research_v3`` (env var
  ``CODE2PAPER_AGENTIC_RESEARCH_V3``);
- legacy P3 graph and V2 state remain the default route;
- V3 state and V2 artifacts exchange only through explicit adapters;
- checkpoint metadata records both schema and graph contract versions.

R0 ships the state schema, reducers, feature flag, V2->V3 projection and
V3->V2 writeback adapter.  No node consumes the V3 state yet; that wiring
lands in R3 when the research supervisor subgraph is added.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.research_models import (
    CandidateAcquisitionLedgerV1,
    GlobalSafetyBudgetV1,
    ImplementationScopeV1,
    PerObligationBudgetV1,
    QualityStateV2,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
)
from code2paper.agentic.source_authority import SourceAuthorityPolicy


STATE_SCHEMA_VERSION_V3 = "3.0"
GRAPH_CONTRACT_VERSION_V3 = "agentic-research-v3"
RESEARCH_FEATURE_FLAG = "agentic_research_v3"


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def is_agentic_research_v3_enabled() -> bool:
    """Return True when the V3 research plane is opted in for the current run.

    The flag is read from the ``CODE2PAPER_AGENTIC_RESEARCH_V3`` environment
    variable.  Accepted truthy values: ``1``, ``true``, ``yes``, ``on``
    (case-insensitive).  Everything else (including unset) is False so the
    default route stays on the existing P3 graph.
    """

    raw = os.environ.get(f"CODE2PAPER_{RESEARCH_FEATURE_FLAG}".upper(), "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def enable_agentic_research_v3() -> None:
    """Programmatically opt in (used by tests and explicit run configs)."""

    os.environ[f"CODE2PAPER_{RESEARCH_FEATURE_FLAG}".upper()] = "1"


def disable_agentic_research_v3() -> None:
    """Programmatically opt out (used by tests)."""

    os.environ.pop(f"CODE2PAPER_{RESEARCH_FEATURE_FLAG}".upper(), None)


# ---------------------------------------------------------------------------
# Reducers (mirror state_v2 semantics, but V3 owns its own channels)
# ---------------------------------------------------------------------------


def merge_mapping(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Right-biased reducer for reference/diagnostic channels."""

    return {**(left or {}), **(right or {})}


def merge_counters(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    """Merge full-state counters without replaying increments on resume."""

    merged = dict(left or {})
    for key, value in (right or {}).items():
        merged[key] = max(int(merged.get(key, 0)), int(value))
    return merged


def append_unique(left: list[Any], right: list[Any]) -> list[Any]:
    """Stable de-duplicating reducer for trace references."""

    result: list[Any] = []
    seen: set[str] = set()
    for item in [*(left or []), *(right or [])]:
        if hasattr(item, "model_dump_json"):
            key = item.model_dump_json()
        elif isinstance(item, BaseModel):
            key = item.model_dump_json()
        else:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# AgentStateV3 (LangGraph TypedDict)
# ---------------------------------------------------------------------------


ResearchRunStatus = Literal[
    "initialized",
    "intent_compiled",
    "repository_indexed",
    "agenda_built",
    "researching",
    "authoring_planned",
    "drafting",
    "validating",
    "trusted",
    "incomplete",
    "blocked",
]


class AgentStateV3(TypedDict, total=False):
    """LangGraph channel schema for the V3 research plane.

    The state only stores artifact *references*, digests and compact decision
    context.  Source snippets, behavior graph payloads and evidence packets
    are read on demand by tools so prompts stay small and deterministic.

    Channels with ``Annotated[..., reducer]`` use custom reducers so partial
    node updates merge correctly across checkpoint resume.
    """

    # --- identity / contracts -------------------------------------------------
    state_schema_version: str
    graph_contract_version: str
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    source_authority_policy: Annotated[dict[str, Any], merge_mapping]

    # --- artifact references (paths or content digests, never inline bodies) --
    intent_graph_ref: str
    behavior_graph_ref: str
    symbol_index_ref: str
    research_agenda_ref: str
    implementation_scope_ref: str
    candidate_acquisition_ledger_ref: str

    evidence_packet_set_ref: str
    code_fact_set_ref: str
    atomic_claim_set_ref: str
    explicit_gap_set_ref: str
    obligation_coverage_ref: str

    current_quality_state_ref: str
    best_quality_state_ref: str

    # --- active research focus -----------------------------------------------
    active_obligation_id: str
    active_issue_id: str
    pending_tool_calls: Annotated[list[ResearchToolCallV1], append_unique]
    recent_observation_refs: Annotated[list[str], append_unique]
    decision_trace_refs: Annotated[list[str], append_unique]
    tool_call_trace_refs: Annotated[list[str], append_unique]

    # --- budgets / safety ----------------------------------------------------
    per_obligation_budgets: Annotated[dict[str, dict[str, int]], merge_mapping]
    global_safety_budget: Annotated[dict[str, int], merge_mapping]
    no_progress_counters: Annotated[dict[str, int], merge_counters]

    # Phase 4: serializable snapshot of the research loop state
    # (behavior graph, gain tracker, budgets, turn index, tool call ids).
    # Populated by the multi-node LangGraph topology so cross-instance
    # checkpoint/resume can rebuild the non-serializable loop state.
    loop_state_snapshot: Annotated[dict[str, Any], merge_mapping]

    # --- authoring -----------------------------------------------------------
    authoring_plan_ref: str
    method_draft_ref: str
    final_validation_ref: str

    # --- status --------------------------------------------------------------
    status: ResearchRunStatus
    blocked_reason: str


# ---------------------------------------------------------------------------
# Pydantic validator (used by checkpoints and adapters)
# ---------------------------------------------------------------------------


class AgentStateV3Record(BaseModel):
    """Pydantic validator for a serialized ``AgentStateV3`` payload.

    LangGraph TypedDicts do not validate by default.  Checkpoint write/read
    and the V2/V3 adapter go through this model so a malformed channel value
    fails closed instead of corrupting downstream nodes.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    state_schema_version: str = STATE_SCHEMA_VERSION_V3
    graph_contract_version: str = GRAPH_CONTRACT_VERSION_V3
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    source_authority_policy: dict[str, Any] = Field(default_factory=dict)

    intent_graph_ref: str = ""
    behavior_graph_ref: str = ""
    symbol_index_ref: str = ""
    research_agenda_ref: str = ""
    implementation_scope_ref: str = ""
    candidate_acquisition_ledger_ref: str = ""

    evidence_packet_set_ref: str = ""
    code_fact_set_ref: str = ""
    atomic_claim_set_ref: str = ""
    explicit_gap_set_ref: str = ""
    obligation_coverage_ref: str = ""

    current_quality_state_ref: str = ""
    best_quality_state_ref: str = ""

    active_obligation_id: str = ""
    active_issue_id: str = ""
    pending_tool_calls: list[ResearchToolCallV1] = Field(default_factory=list)
    recent_observation_refs: list[str] = Field(default_factory=list)
    decision_trace_refs: list[str] = Field(default_factory=list)
    tool_call_trace_refs: list[str] = Field(default_factory=list)

    per_obligation_budgets: dict[str, dict[str, int]] = Field(default_factory=dict)
    global_safety_budget: dict[str, int] = Field(default_factory=dict)
    no_progress_counters: dict[str, int] = Field(default_factory=dict)

    # Phase 4: serializable snapshot of the research loop state.
    # Empty by default; populated by the multi-node LangGraph topology.
    loop_state_snapshot: dict[str, Any] = Field(default_factory=dict)

    authoring_plan_ref: str = ""
    method_draft_ref: str = ""
    final_validation_ref: str = ""

    status: ResearchRunStatus = "initialized"
    blocked_reason: str = ""

    @field_validator("run_id", "repo_snapshot_id", "project_tree_hash")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("state_schema_version")
    @classmethod
    def _schema_version(cls, value: str) -> str:
        if value != STATE_SCHEMA_VERSION_V3:
            raise ValueError(
                f"unsupported V3 state schema version: {value}; expected {STATE_SCHEMA_VERSION_V3}"
            )
        return value

    @field_validator("graph_contract_version")
    @classmethod
    def _graph_contract(cls, value: str) -> str:
        if value != GRAPH_CONTRACT_VERSION_V3:
            raise ValueError(
                f"unsupported V3 graph contract: {value}; expected {GRAPH_CONTRACT_VERSION_V3}"
            )
        return value

    def to_state_dict(self) -> AgentStateV3:
        """Convert to a LangGraph-consumable TypedDict payload."""

        payload = self.model_dump(mode="json")
        # LangGraph expects lists/tuples for the annotated channels.
        for key in (
            "pending_tool_calls",
            "recent_observation_refs",
            "decision_trace_refs",
            "tool_call_trace_refs",
        ):
            payload[key] = list(payload.get(key) or [])
        return payload  # type: ignore[return-value]


def empty_agent_state_v3(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    source_authority_policy: SourceAuthorityPolicy | dict[str, Any] | None = None,
) -> AgentStateV3Record:
    """Return a blank V3 state record for a new run."""

    if source_authority_policy is None:
        from code2paper.agentic.source_authority import default_source_authority_policy

        policy = default_source_authority_policy()
        policy_payload = policy.model_dump(mode="json")
    elif isinstance(source_authority_policy, SourceAuthorityPolicy):
        policy_payload = source_authority_policy.model_dump(mode="json")
    else:
        policy_payload = dict(source_authority_policy)
    return AgentStateV3Record(
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        source_authority_policy=policy_payload,
        status="initialized",
    )


# ---------------------------------------------------------------------------
# Checkpoint metadata for V3
# ---------------------------------------------------------------------------


class CheckpointMetadataV3(BaseModel):
    """V3 checkpoint metadata (mirrors V2 with V3 versions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_schema_version: str = STATE_SCHEMA_VERSION_V3
    graph_contract_version: str = GRAPH_CONTRACT_VERSION_V3
    run_id: str
    repo_snapshot_id: str
    thread_id: str
    checkpoint_backend: str
    resumed: bool = False
    freshness_status: str = "not_checked"
    stale_artifact_keys: list[str] = Field(default_factory=list)
    feature_flag: str = RESEARCH_FEATURE_FLAG


def checkpoint_thread_id_v3(*, run_id: str, repo_snapshot_id: str) -> str:
    """Stable thread id for V3 checkpoints (distinct from V2 thread ids)."""

    run = run_id.strip()
    snapshot = repo_snapshot_id.strip()
    if not run or not snapshot:
        raise ValueError("checkpoint identity requires run_id and repo_snapshot_id")
    return f"{run}:{snapshot}:{GRAPH_CONTRACT_VERSION_V3}"


# ---------------------------------------------------------------------------
# V2 <-> V3 adapters
# ---------------------------------------------------------------------------


def project_v3_state_from_v2(
    v2_state: AgenticRunState,
    *,
    project_tree_hash: str,
    source_authority_policy: SourceAuthorityPolicy | dict[str, Any] | None = None,
) -> AgentStateV3Record:
    """Project a V2 ``AgenticRunState`` into a V3 ``AgentStateV3Record``.

    R0.3 hard rule: V3 and V2 exchange only through explicit adapters.  This
    function never mutates ``v2_state`` and only copies fields that have a
    well-defined V3 home:

    - run_id, repo_snapshot_id (via repo_snapshot_ref), project_tree_hash
      (passed explicitly by the caller, who already loaded the snapshot for
      the V2 freshness gate);
    - artifact references are populated from ``v2_state.artifacts`` using the
      V2 artifact key registry;
    - status is mapped from V2 phase_statuses (best-effort);
    - blocked_reason is copied verbatim.

    Fields without a V2 source (e.g. ``research_agenda_ref``,
    ``per_obligation_budgets``) stay empty and are filled by V3 nodes in R3+.

    ``project_tree_hash`` is required because every V3 research artifact is
    bound to a frozen repository identity (design 3.1, 5).  Callers that only
    have a snapshot file path should call ``load_repo_snapshot`` first; the
    adapter deliberately does not perform file IO so the boundary stays
    explicit and testable.
    """

    artifacts = dict(v2_state.artifacts or {})
    repo_snapshot_ref = v2_state.repo_snapshot_ref or artifacts.get("repo_snapshot", "")
    normalized_tree_hash = (project_tree_hash or "").strip()
    if not normalized_tree_hash:
        raise ValueError(
            "project_v3_state_from_v2 requires project_tree_hash; "
            "load the repo snapshot before projecting V2 -> V3"
        )

    if source_authority_policy is None:
        from code2paper.agentic.source_authority import default_source_authority_policy

        policy = default_source_authority_policy()
        policy_payload = policy.model_dump(mode="json")
    elif isinstance(source_authority_policy, SourceAuthorityPolicy):
        policy_payload = source_authority_policy.model_dump(mode="json")
    else:
        policy_payload = dict(source_authority_policy)

    status = _map_v2_phase_to_v3_status(v2_state)
    return AgentStateV3Record(
        run_id=v2_state.run_id,
        repo_snapshot_id=repo_snapshot_ref,
        project_tree_hash=normalized_tree_hash,
        source_authority_policy=policy_payload,
        intent_graph_ref=artifacts.get("intent_obligation_graph", ""),
        behavior_graph_ref="",
        symbol_index_ref=artifacts.get("symbol_index", ""),
        research_agenda_ref="",
        evidence_packet_set_ref=artifacts.get("evidence_packets_v3", ""),
        code_fact_set_ref=artifacts.get("code_facts_v1", ""),
        atomic_claim_set_ref=artifacts.get("atomic_claims_v3", artifacts.get("atomic_claims_v2", "")),
        explicit_gap_set_ref="",
        obligation_coverage_ref=artifacts.get("authoring_obligation_coverage", ""),
        current_quality_state_ref="",
        best_quality_state_ref="",
        authoring_plan_ref=artifacts.get("authoring_plan", ""),
        method_draft_ref=artifacts.get("method_text", artifacts.get("method_draft", "")),
        final_validation_ref=artifacts.get("text_evidence_validation", ""),
        status=status,
        blocked_reason=v2_state.blocked_reason,
    )


def writeback_v3_references_to_v2(
    v2_state: AgenticRunState,
    v3_record: AgentStateV3Record,
) -> AgenticRunState:
    """Write V3 artifact references back into a V2 ``AgenticRunState``.

    Used when a run starts on the V2 default route but opts in to V3 research
    artifacts (e.g. evidence packets compiled by the generic compiler).  The
    adapter only writes fields that have an explicit V2 artifact key; it never
    overwrites V2-only channels like ``loop_counters`` or ``phase_statuses``.
    """

    artifacts = dict(v2_state.artifacts or {})
    if v3_record.evidence_packet_set_ref:
        artifacts["evidence_packets_v3"] = v3_record.evidence_packet_set_ref
    if v3_record.code_fact_set_ref:
        artifacts["code_facts_v1"] = v3_record.code_fact_set_ref
    if v3_record.atomic_claim_set_ref:
        artifacts["atomic_claims_v3"] = v3_record.atomic_claim_set_ref
    if v3_record.symbol_index_ref:
        artifacts["symbol_index"] = v3_record.symbol_index_ref
    if v3_record.authoring_plan_ref:
        artifacts["authoring_plan"] = v3_record.authoring_plan_ref
    if v3_record.final_validation_ref:
        artifacts["text_evidence_validation"] = v3_record.final_validation_ref
    checkpoint_metadata = dict(v2_state.checkpoint_metadata or {})
    checkpoint_metadata.update(
        {
            "state_schema_version_seen": v3_record.state_schema_version,
            "graph_contract_version_seen": v3_record.graph_contract_version,
            "research_feature_flag": RESEARCH_FEATURE_FLAG,
        }
    )
    return v2_state.model_copy(
        update={
            "artifacts": artifacts,
            "repo_snapshot_ref": v3_record.repo_snapshot_id or v2_state.repo_snapshot_ref,
            "checkpoint_metadata": checkpoint_metadata,
        }
    )


def detect_state_schema(payload: dict[str, Any] | BaseModel) -> Literal["v2", "v3", "unknown"]:
    """Inspect a checkpoint payload and report which schema it carries.

    Used by the unified resume path (R0.3 + R3.5) so a single entry point can
    dispatch to V2 or V3 resume without trial-and-error validation.
    """

    if isinstance(payload, BaseModel):
        raw = payload.model_dump(mode="json")
    else:
        raw = dict(payload or {})
    schema = str(raw.get("state_schema_version") or "")
    contract = str(raw.get("graph_contract_version") or "")
    if schema == STATE_SCHEMA_VERSION_V3 or contract == GRAPH_CONTRACT_VERSION_V3:
        return "v3"
    if schema in {"2.0", "1.0"} or contract == "agentic-graph-v3":
        return "v2"
    return "unknown"


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


_V2_TO_V3_STATUS_MAP: dict[str, ResearchRunStatus] = {
    "intake": "repository_indexed",
    "analysis": "repository_indexed",
    "retrieval": "repository_indexed",
    "evidence": "researching",
    "grounding": "researching",
    "authoring": "drafting",
    "validation": "validating",
    "finalize": "trusted",
}


def _map_v2_phase_to_v3_status(v2_state: AgenticRunState) -> ResearchRunStatus:
    if v2_state.blocked_reason:
        return "blocked"
    phases = v2_state.phase_statuses or {}
    if not phases:
        return "initialized"
    # Pick the latest non-skipped phase in a fixed order.
    for phase in ("finalize", "validation", "authoring", "grounding", "evidence", "retrieval", "analysis", "intake"):
        status = phases.get(phase)
        if status and status != "skipped":
            return _V2_TO_V3_STATUS_MAP.get(phase, "researching")
    return "initialized"


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


__all__ = [
    "GRAPH_CONTRACT_VERSION_V3",
    "RESEARCH_FEATURE_FLAG",
    "STATE_SCHEMA_VERSION_V3",
    "AgentStateV3",
    "AgentStateV3Record",
    "CheckpointMetadataV3",
    "ResearchRunStatus",
    "append_unique",
    "checkpoint_thread_id_v3",
    "detect_state_schema",
    "disable_agentic_research_v3",
    "empty_agent_state_v3",
    "enable_agentic_research_v3",
    "is_agentic_research_v3_enabled",
    "merge_counters",
    "merge_mapping",
    "project_v3_state_from_v2",
    "writeback_v3_references_to_v2",
]
