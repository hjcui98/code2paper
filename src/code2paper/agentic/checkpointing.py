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
