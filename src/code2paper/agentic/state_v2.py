from __future__ import annotations

from typing import Annotated, Any, TypedDict

from code2paper.agentic.contracts import AgentDecision, AgenticRunState


STATE_SCHEMA_VERSION = "2.0"
GRAPH_CONTRACT_VERSION = "agentic-graph-v3"


def merge_mapping(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Right-biased reducer for artifact and phase-status channels."""

    return {**(left or {}), **(right or {})}


def merge_counters(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    """Merge full-state counter updates without replaying increments on resume."""

    merged = dict(left or {})
    for key, value in (right or {}).items():
        merged[key] = max(int(merged.get(key, 0)), int(value))
    return merged


def append_unique(left: list[Any], right: list[Any]) -> list[Any]:
    """Stable de-duplicating reducer safe for nodes that return a full state."""

    result: list[Any] = []
    seen: set[str] = set()
    for item in [*(left or []), *(right or [])]:
        if hasattr(item, "model_dump_json"):
            key = item.model_dump_json()
        else:
            key = repr(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


class AgenticRunStateV2(TypedDict, total=False):
    """LangGraph channel schema; Pydantic ``AgenticRunState`` is the validator."""

    state_schema_version: str
    graph_contract_version: str
    run_id: str
    project_root: str
    out_root: str
    project_id: str
    author_markers_path: str
    intent_path: str
    intent_ref: str
    repo_snapshot_ref: str
    model_profile_ref: str
    llm_provider: str | None
    llm_model: str | None
    core_top_k: int
    skip_draft_bootstrap: bool
    max_retrieval_rounds: int
    max_evidence_revision_rounds: int
    max_authoring_revision_rounds: int
    max_figure_revision_rounds: int
    max_semantic_verifier_calls: int
    loop_counters: Annotated[dict[str, int], merge_counters]
    artifacts: Annotated[dict[str, str], merge_mapping]
    decisions: Annotated[list[dict[str, Any]], append_unique]
    phase_statuses: Annotated[dict[str, str], merge_mapping]
    pending_gaps: Annotated[list[str], append_unique]
    validation: Annotated[dict[str, Any], merge_mapping]
    checkpoint_metadata: Annotated[dict[str, Any], merge_mapping]
    blocked_reason: str
    next_node: str


def migrate_state_v1_to_v2(payload: AgenticRunState | dict[str, Any]) -> AgenticRunState:
    """Upgrade a pre-P3 state and reject unknown future checkpoint schemas."""

    raw = payload.model_dump(mode="json") if isinstance(payload, AgenticRunState) else dict(payload)
    version = str(raw.get("state_schema_version") or "1.0")
    if version not in {"1.0", STATE_SCHEMA_VERSION}:
        raise ValueError(f"unsupported agentic state schema: {version}")
    contract = str(raw.get("graph_contract_version") or GRAPH_CONTRACT_VERSION)
    if contract != GRAPH_CONTRACT_VERSION:
        raise ValueError(f"incompatible graph contract: {contract}")
    raw.update(
        state_schema_version=STATE_SCHEMA_VERSION,
        graph_contract_version=GRAPH_CONTRACT_VERSION,
        run_id=str(raw.get("run_id") or ""),
        repo_snapshot_ref=str(raw.get("repo_snapshot_ref") or raw.get("artifacts", {}).get("repo_snapshot", "")),
        intent_ref=str(raw.get("intent_ref") or raw.get("intent_path", "")),
        model_profile_ref=str(raw.get("model_profile_ref") or ""),
        phase_statuses=dict(raw.get("phase_statuses") or {}),
        pending_gaps=list(raw.get("pending_gaps") or []),
        checkpoint_metadata=dict(raw.get("checkpoint_metadata") or {}),
    )
    return AgenticRunState.model_validate(raw)
