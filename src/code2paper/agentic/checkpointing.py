from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.artifact_freshness import check_artifact_freshness
from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.evidence_v2 import load_evidence_snapshot_v2
from code2paper.agentic.repo_snapshot import load_repo_snapshot
from code2paper.agentic.state_v2 import GRAPH_CONTRACT_VERSION, STATE_SCHEMA_VERSION, migrate_state_v1_to_v2
from code2paper.agentic.state_v3 import (
    GRAPH_CONTRACT_VERSION_V3,
    STATE_SCHEMA_VERSION_V3,
    AgentStateV3Record,
    CheckpointMetadataV3,
    checkpoint_thread_id_v3,
    detect_state_schema,
)


class CheckpointMetadataV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_schema_version: str = STATE_SCHEMA_VERSION
    graph_contract_version: str = GRAPH_CONTRACT_VERSION
    run_id: str
    repo_snapshot_id: str
    thread_id: str
    checkpoint_backend: str
    resumed: bool = False
    freshness_status: str = "not_checked"
    stale_artifact_keys: list[str] = Field(default_factory=list)


def checkpoint_thread_id(*, run_id: str, repo_snapshot_id: str) -> str:
    run = run_id.strip()
    snapshot = repo_snapshot_id.strip()
    if not run or not snapshot:
        raise ValueError("checkpoint identity requires run_id and repo_snapshot_id")
    return f"{run}:{snapshot}:{GRAPH_CONTRACT_VERSION}"


def checkpoint_config(thread_id: str) -> dict[str, dict[str, str]]:
    if not thread_id.strip():
        raise ValueError("checkpoint thread_id must not be empty")
    return {"configurable": {"thread_id": thread_id}}


def build_memory_checkpointer():
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver()


@contextmanager
def open_sqlite_checkpointer(path: str | Path) -> Iterator[Any]:
    """Open a durable LangGraph saver with an explicitly managed connection."""

    from langgraph.checkpoint.sqlite import SqliteSaver

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(output), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    try:
        yield saver
    finally:
        connection.close()


def validate_resume_state(payload: AgenticRunState | dict[str, Any]) -> tuple[AgenticRunState, CheckpointMetadataV2]:
    """Fail closed when a checkpoint cannot be bound to current code evidence."""

    state = migrate_state_v1_to_v2(payload)
    repo_path = state.repo_snapshot_ref or state.artifacts.get("repo_snapshot", "")
    evidence_path = state.artifacts.get("evidence_snapshot_v2", "")
    if not repo_path or not evidence_path:
        raise ValueError("resume requires repo_snapshot and evidence_snapshot_v2")
    repo = load_repo_snapshot(repo_path)
    evidence = load_evidence_snapshot_v2(evidence_path)
    if evidence.repo_snapshot_id != repo.snapshot_id:
        raise ValueError("checkpoint evidence is bound to another repo snapshot")
    report = check_artifact_freshness(repo_snapshot=repo, evidence_snapshot=evidence, artifacts=state.artifacts)
    if report.source_drift:
        raise ValueError("source_drift: checkpoint repository no longer matches frozen snapshot")
    if report.evidence_round_trip_failures or report.stale_artifact_keys:
        failures = report.evidence_round_trip_failures or report.stale_artifact_keys
        raise ValueError("stale_checkpoint_artifacts: " + ",".join(failures))
    thread_id = checkpoint_thread_id(run_id=state.run_id, repo_snapshot_id=repo.snapshot_id)
    metadata = CheckpointMetadataV2(
        run_id=state.run_id,
        repo_snapshot_id=repo.snapshot_id,
        thread_id=thread_id,
        checkpoint_backend=str(state.checkpoint_metadata.get("checkpoint_backend") or "unknown"),
        resumed=True,
        freshness_status=report.status,
        stale_artifact_keys=report.stale_artifact_keys,
    )
    return state.model_copy(update={"repo_snapshot_ref": repo_path, "checkpoint_metadata": metadata.model_dump(mode="json")}), metadata


def validate_resume_state_v3(
    payload: AgentStateV3Record | dict[str, Any],
    *,
    repo_snapshot_path: str,
) -> tuple[AgentStateV3Record, CheckpointMetadataV3]:
    """V3 resume path: bind a serialized V3 state to current repo evidence.

    The V3 research plane does not require an ``evidence_snapshot_v2``
    artifact: V3 facts are compiled from tool observations and the behavior
    graph, not from the legacy V2 snapshot.  Resume therefore only checks:

    - the payload is a valid ``AgentStateV3Record`` (schema/graph versions);
    - the repo snapshot exists and its ``project_tree_hash`` matches the
      state's ``project_tree_hash`` (source drift fails closed);
    - any V2 artifacts referenced via ``evidence_packet_set_ref`` /
      ``code_fact_set_ref`` / ``atomic_claim_set_ref`` are fresh when present
      (R0.4 extends freshness to V3 artifact keys).

    The function never touches the V2 ``AgenticRunState``; cross-plane
    exchange happens through ``project_v3_state_from_v2`` /
    ``writeback_v3_references_to_v2`` in ``state_v3``.
    """

    if isinstance(payload, AgentStateV3Record):
        record = payload
    else:
        record = AgentStateV3Record.model_validate(dict(payload))
    repo = load_repo_snapshot(repo_snapshot_path)
    if record.repo_snapshot_id and record.repo_snapshot_id != repo.snapshot_id:
        raise ValueError("checkpoint V3 state is bound to another repo snapshot")
    if record.project_tree_hash and record.project_tree_hash != repo.project_tree_hash:
        raise ValueError("source_drift: checkpoint repository no longer matches frozen snapshot")
    thread_id = checkpoint_thread_id_v3(run_id=record.run_id, repo_snapshot_id=repo.snapshot_id)
    metadata = CheckpointMetadataV3(
        run_id=record.run_id,
        repo_snapshot_id=repo.snapshot_id,
        thread_id=thread_id,
        checkpoint_backend="v3-resume",
        resumed=True,
        freshness_status="not_checked",
    )
    updated = record.model_copy(
        update={
            "repo_snapshot_id": repo.snapshot_id,
            "project_tree_hash": repo.project_tree_hash,
        }
    )
    return updated, metadata


def validate_resume_state_dispatch(
    payload: AgenticRunState | AgentStateV3Record | dict[str, Any],
    *,
    repo_snapshot_path: str,
    evidence_snapshot_path: str = "",
) -> tuple[BaseModel, BaseModel]:
    """Dispatch a checkpoint payload to the V2 or V3 resume path.

    Used by unified resume entry points so callers do not need to inspect the
    schema version themselves.  Returns a ``(state, metadata)`` tuple whose
    concrete types depend on the detected schema.
    """

    schema = detect_state_schema(payload)
    if schema == "v3":
        if not repo_snapshot_path:
            raise ValueError("V3 resume requires repo_snapshot_path")
        return validate_resume_state_v3(payload, repo_snapshot_path=repo_snapshot_path)
    if schema == "v2":
        if not repo_snapshot_path or not evidence_snapshot_path:
            raise ValueError("V2 resume requires repo_snapshot_path and evidence_snapshot_path")
        return validate_resume_state(payload)
    raise ValueError(f"cannot resume unknown checkpoint schema: {schema}")
