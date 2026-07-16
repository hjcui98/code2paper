from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from code2paper.agentic.checkpointing import (
    build_memory_checkpointer,
    checkpoint_config,
    checkpoint_thread_id,
    open_sqlite_checkpointer,
    validate_resume_state,
)
from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.evidence_v2 import build_evidence_snapshot_v2, write_evidence_snapshot_v2
from code2paper.agentic.repo_snapshot import build_repo_snapshot, write_repo_snapshot
from code2paper.agentic.state_v2 import (
    AgenticRunStateV2,
    append_unique,
    merge_counters,
    merge_mapping,
    migrate_state_v1_to_v2,
)
from code2paper.agentic.tool_runtime import IdempotentToolCache, atomic_write_bytes, tool_cache_key
from code2paper.agentic.tool_selection import enforce_tool_proposal
from code2paper.agentic.trust_tools import build_trust_tool_contracts, build_trust_tools
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType


def _frozen_state(tmp_path: Path, *, run_id: str = "run-p3") -> AgenticRunState:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "model.py").write_text("def encode(x):\n    return x\n", encoding="utf-8")
    repo = build_repo_snapshot(repo_root)
    raw = RawEvidencePack(
        project_id="p3",
        project_root=str(repo_root),
        evidence_items=[EvidenceItem(
            evidence_id="E1", source_type=SourceType.SOURCE, path="model.py", symbol="encode",
            line_start=1, line_end=2, content_summary="encode returns its input", confidence=1.0,
        )],
    )
    evidence = build_evidence_snapshot_v2(raw, repo)
    out = tmp_path / "out"
    repo_path = out / "artifacts" / "01_input" / "repo_snapshot.json"
    evidence_path = out / "artifacts" / "04_evidence" / "evidence_snapshot_v2.json"
    write_repo_snapshot(repo_path, repo)
    write_evidence_snapshot_v2(evidence_path, evidence)
    return AgenticRunState(
        run_id=run_id,
        project_root=repo_root,
        out_root=out,
        repo_snapshot_ref=str(repo_path),
        max_authoring_revision_rounds=3,
        loop_counters={"authoring": 1},
        artifacts={"repo_snapshot": str(repo_path), "evidence_snapshot_v2": str(evidence_path)},
    )


def _checkpoint_graph(checkpointer, *, interrupt: bool):
    calls = {"evidence": 0, "authoring": 0}

    def evidence(state):
        calls["evidence"] += 1
        return {
            "phase_statuses": {"evidence": "success"},
            "decisions": [AgentDecision(node="evidence", decision="frozen").model_dump(mode="json")],
        }

    def authoring(state):
        calls["authoring"] += 1
        return {
            "phase_statuses": {"authoring": "success"},
            "loop_counters": {"authoring": 2},
            "decisions": [AgentDecision(node="authoring", decision="validated").model_dump(mode="json")],
        }

    builder = StateGraph(AgenticRunStateV2)
    builder.add_node("evidence", evidence)
    builder.add_node("authoring", authoring)
    builder.add_edge(START, "evidence")
    builder.add_edge("evidence", "authoring")
    builder.add_edge("authoring", END)
    return builder.compile(checkpointer=checkpointer, interrupt_after=["evidence"] if interrupt else None), calls


def test_state_v2_migration_reducers_and_extra_forbid(tmp_path: Path) -> None:
    state = _frozen_state(tmp_path)
    migrated = migrate_state_v1_to_v2(state.model_dump(exclude={"state_schema_version", "graph_contract_version"}))
    assert migrated.state_schema_version == "2.0"
    assert migrated.repo_snapshot_ref == state.artifacts["repo_snapshot"]
    assert merge_mapping({"a": "1"}, {"b": "2"}) == {"a": "1", "b": "2"}
    assert merge_counters({"x": 3}, {"x": 2, "y": 1}) == {"x": 3, "y": 1}
    decision = AgentDecision(node="x", decision="y")
    assert append_unique([decision], [decision]) == [decision]
    with pytest.raises(ValidationError):
        AgenticRunState.model_validate({**state.model_dump(), "model_injected": True})
    with pytest.raises(ValueError, match="unsupported agentic state schema"):
        migrate_state_v1_to_v2({**state.model_dump(), "state_schema_version": "99.0"})


def test_memory_checkpoint_resume_preserves_budget_and_skips_completed_node(tmp_path: Path) -> None:
    state = _frozen_state(tmp_path)
    saver = build_memory_checkpointer()
    app, calls = _checkpoint_graph(saver, interrupt=True)
    repo_id = build_repo_snapshot(state.project_root).snapshot_id
    config = checkpoint_config(checkpoint_thread_id(run_id=state.run_id, repo_snapshot_id=repo_id))
    first = app.invoke(state.model_dump(mode="json"), config=config)
    assert first["phase_statuses"] == {"evidence": "success"}
    assert calls == {"evidence": 1, "authoring": 0}

    resumed_state, metadata = validate_resume_state(app.get_state(config).values)
    assert resumed_state.max_authoring_revision_rounds == 3
    assert resumed_state.loop_counters["authoring"] == 1
    assert metadata.freshness_status == "passed"
    final = app.invoke(None, config=config)
    assert calls == {"evidence": 1, "authoring": 1}
    assert final["loop_counters"]["authoring"] == 2
    assert [item.decision if isinstance(item, AgentDecision) else item["decision"] for item in final["decisions"]] == ["frozen", "validated"]


def test_sqlite_checkpoint_survives_reopen_and_matches_control(tmp_path: Path) -> None:
    state = _frozen_state(tmp_path)
    repo_id = build_repo_snapshot(state.project_root).snapshot_id
    config = checkpoint_config(checkpoint_thread_id(run_id=state.run_id, repo_snapshot_id=repo_id))
    database = tmp_path / "checkpoints" / "run.sqlite"
    with open_sqlite_checkpointer(database) as saver:
        app, _calls = _checkpoint_graph(saver, interrupt=True)
        app.invoke(state.model_dump(mode="json"), config=config)
    with open_sqlite_checkpointer(database) as saver:
        app, calls = _checkpoint_graph(saver, interrupt=True)
        validate_resume_state(app.get_state(config).values)
        resumed = app.invoke(None, config=config)
    control_app, _ = _checkpoint_graph(build_memory_checkpointer(), interrupt=False)
    control_config = checkpoint_config(checkpoint_thread_id(run_id="control", repo_snapshot_id=repo_id))
    control = control_app.invoke(state.model_dump(mode="json"), config=control_config)
    assert calls == {"evidence": 0, "authoring": 1}
    assert resumed["phase_statuses"] == control["phase_statuses"]
    assert resumed["loop_counters"] == control["loop_counters"]


def test_resume_rejects_source_drift(tmp_path: Path) -> None:
    state = _frozen_state(tmp_path)
    (state.project_root / "model.py").write_text("def encode(x):\n    return x + 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source_drift"):
        validate_resume_state(state)


def test_fine_grained_tools_expose_complete_contracts() -> None:
    contracts = build_trust_tool_contracts()
    tools = build_trust_tools()
    assert len(contracts) == len(tools) == 9
    assert {item.name for item in contracts} == {item.name for item in tools}
    assert all(item.input_schema and item.output_schema and item.idempotency_fields for item in contracts)
    assert all(item.side_effects == ["atomic_artifact_write"] for item in contracts)


def test_restricted_selection_rejects_model_tool_escalation(tmp_path: Path) -> None:
    state = _frozen_state(tmp_path)
    with pytest.raises(PermissionError, match="tool_not_exposed"):
        enforce_tool_proposal(state, "finalize")
    with pytest.raises(PermissionError, match="preconditions_not_met"):
        enforce_tool_proposal(state, "render_structured_figure")
    assert enforce_tool_proposal(state, "check_artifact_freshness") == "check_artifact_freshness"


def test_atomic_cache_key_and_hit_do_not_repeat_operation(tmp_path: Path) -> None:
    key = tool_cache_key(
        tool_name="validate_claim", producer_version="p3", repo_snapshot_id="repo:1",
        input_digests={"claims": "sha256:a"}, model_profile={"model": "gemma4"},
        configuration={"strict": True},
    )
    cache = IdempotentToolCache(tmp_path / "cache")
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        return {"status": "passed", "digest": "sha256:stable"}

    first, first_hit = cache.invoke(key, operation)
    second, second_hit = cache.invoke(key, operation)
    assert first == second
    assert (first_hit, second_hit, calls) == (False, True, 1)
    target = tmp_path / "atomic.json"
    atomic_write_bytes(target, json.dumps(first).encode())
    assert json.loads(target.read_text()) == first
