"""R0.3 V2/V3 state adapter tests.

Exit conditions covered:
- V2 -> V3 projection copies only fields with a well-defined V3 home;
- V3 -> V2 writeback records schema/graph versions in checkpoint metadata;
- ``validate_resume_state_dispatch`` routes V2 and V3 payloads correctly;
- V2 state is never mutated by the adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code2paper.agentic.contracts import AgenticRunState
from code2paper.agentic.repo_snapshot import build_repo_snapshot, write_repo_snapshot
from code2paper.agentic.state_v3 import (
    GRAPH_CONTRACT_VERSION_V3,
    STATE_SCHEMA_VERSION_V3,
    AgentStateV3Record,
    detect_state_schema,
    project_v3_state_from_v2,
    writeback_v3_references_to_v2,
)
from code2paper.agentic.checkpointing import (
    validate_resume_state_dispatch,
    validate_resume_state_v3,
)


def _v2_state(**overrides) -> AgenticRunState:
    base = {
        "project_root": Path("."),
        "out_root": Path("/tmp/code2paper-v3-adapter-test"),
        "run_id": "run-1",
        "artifacts": {
            "repo_snapshot": "/tmp/repo_snapshot.json",
            "symbol_index": "/tmp/symbol_index.json",
            "evidence_packets_v3": "/tmp/packets.json",
            "code_facts_v1": "/tmp/facts.json",
            "atomic_claims_v3": "/tmp/claims.json",
            "authoring_plan": "/tmp/authoring_plan.json",
            "text_evidence_validation": "/tmp/validation.json",
            "intent_obligation_graph": "/tmp/intent_graph.json",
            "authoring_obligation_coverage": "/tmp/coverage.json",
        },
        "phase_statuses": {"intake": "success", "evidence": "success"},
        "blocked_reason": "",
    }
    base.update(overrides)
    return AgenticRunState.model_validate(base)


# ---------------------------------------------------------------------------
# project_v3_state_from_v2
# ---------------------------------------------------------------------------


def test_project_v3_state_from_v2_copies_artifact_refs() -> None:
    v2 = _v2_state()
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.run_id == "run-1"
    assert v3.repo_snapshot_id == "/tmp/repo_snapshot.json"
    assert v3.project_tree_hash == "sha256:tree"
    assert v3.symbol_index_ref == "/tmp/symbol_index.json"
    assert v3.evidence_packet_set_ref == "/tmp/packets.json"
    assert v3.code_fact_set_ref == "/tmp/facts.json"
    assert v3.atomic_claim_set_ref == "/tmp/claims.json"
    assert v3.authoring_plan_ref == "/tmp/authoring_plan.json"
    assert v3.final_validation_ref == "/tmp/validation.json"
    assert v3.intent_graph_ref == "/tmp/intent_graph.json"
    assert v3.obligation_coverage_ref == "/tmp/coverage.json"


def test_project_v3_state_from_v2_requires_project_tree_hash() -> None:
    v2 = _v2_state()
    with pytest.raises(ValueError, match="requires project_tree_hash"):
        project_v3_state_from_v2(v2, project_tree_hash="")


def test_project_v3_state_from_v2_does_not_mutate_v2() -> None:
    v2 = _v2_state()
    original_artifacts = dict(v2.artifacts)
    original_repo_ref = v2.repo_snapshot_ref
    project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v2.artifacts == original_artifacts
    assert v2.repo_snapshot_ref == original_repo_ref


def test_project_v3_state_from_v2_seeds_default_policy() -> None:
    v2 = _v2_state()
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.source_authority_policy["policy_id"] == "source-authority-v1"
    assert v3.source_authority_policy["schema_version"] == "1.0"


def test_project_v3_state_from_v2_marks_blocked_state() -> None:
    v2 = _v2_state(blocked_reason="fidelity_validation_failed")
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.status == "blocked"
    assert v3.blocked_reason == "fidelity_validation_failed"


def test_project_v3_state_from_v2_maps_phase_status_to_researching() -> None:
    v2 = _v2_state(phase_statuses={"evidence": "success"})
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.status == "researching"


def test_project_v3_state_from_v2_initial_status_when_no_phases() -> None:
    v2 = _v2_state(phase_statuses={})
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.status == "initialized"


def test_project_v3_state_from_v2_leaves_v3_only_channels_empty() -> None:
    v2 = _v2_state()
    v3 = project_v3_state_from_v2(v2, project_tree_hash="sha256:tree")
    assert v3.research_agenda_ref == ""
    assert v3.behavior_graph_ref == ""
    assert v3.explicit_gap_set_ref == ""
    assert v3.current_quality_state_ref == ""
    assert v3.best_quality_state_ref == ""
    assert v3.active_obligation_id == ""
    assert v3.per_obligation_budgets == {}


# ---------------------------------------------------------------------------
# writeback_v3_references_to_v2
# ---------------------------------------------------------------------------


def test_writeback_v3_references_to_v2_writes_artifact_refs() -> None:
    v2 = _v2_state()
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
        evidence_packet_set_ref="/new/packets.json",
        code_fact_set_ref="/new/facts.json",
        atomic_claim_set_ref="/new/claims.json",
        symbol_index_ref="/new/symbol_index.json",
        authoring_plan_ref="/new/authoring_plan.json",
        final_validation_ref="/new/validation.json",
    )
    updated = writeback_v3_references_to_v2(v2, v3)
    assert updated.artifacts["evidence_packets_v3"] == "/new/packets.json"
    assert updated.artifacts["code_facts_v1"] == "/new/facts.json"
    assert updated.artifacts["atomic_claims_v3"] == "/new/claims.json"
    assert updated.artifacts["symbol_index"] == "/new/symbol_index.json"
    assert updated.artifacts["authoring_plan"] == "/new/authoring_plan.json"
    assert updated.artifacts["text_evidence_validation"] == "/new/validation.json"


def test_writeback_v3_references_to_v2_records_schema_versions() -> None:
    v2 = _v2_state()
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
    )
    updated = writeback_v3_references_to_v2(v2, v3)
    metadata = updated.checkpoint_metadata
    assert metadata["state_schema_version_seen"] == STATE_SCHEMA_VERSION_V3
    assert metadata["graph_contract_version_seen"] == GRAPH_CONTRACT_VERSION_V3
    assert metadata["research_feature_flag"] == "agentic_research_v3"


def test_writeback_v3_references_to_v2_does_not_mutate_v2() -> None:
    v2 = _v2_state()
    original_artifacts = dict(v2.artifacts)
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
        atomic_claim_set_ref="/new/claims.json",
    )
    writeback_v3_references_to_v2(v2, v3)
    assert v2.artifacts == original_artifacts


def test_writeback_v3_references_to_v2_preserves_v2_only_channels() -> None:
    v2 = _v2_state()
    v2 = v2.model_copy(update={"loop_counters": {"retrieval": 3}})
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
        atomic_claim_set_ref="/new/claims.json",
    )
    updated = writeback_v3_references_to_v2(v2, v3)
    # loop_counters and phase_statuses are V2-only channels; the adapter must
    # never touch them.
    assert updated.loop_counters == {"retrieval": 3}
    assert updated.phase_statuses == v2.phase_statuses


# ---------------------------------------------------------------------------
# detect_state_schema + dispatch
# ---------------------------------------------------------------------------


def test_detect_state_schema_v2_from_pydantic_state() -> None:
    v2 = _v2_state()
    assert detect_state_schema(v2) == "v2"


def test_validate_resume_state_dispatch_routes_v3(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    snapshot = build_repo_snapshot(repo_root)
    snapshot_path = tmp_path / "snapshot.json"
    write_repo_snapshot(snapshot_path, snapshot)
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
    )
    state, metadata = validate_resume_state_dispatch(
        v3.model_dump(mode="json"),
        repo_snapshot_path=str(snapshot_path),
    )
    assert isinstance(state, AgentStateV3Record)
    assert state.repo_snapshot_id == snapshot.snapshot_id
    assert state.project_tree_hash == snapshot.project_tree_hash
    assert metadata.state_schema_version == STATE_SCHEMA_VERSION_V3
    assert metadata.graph_contract_version == GRAPH_CONTRACT_VERSION_V3
    assert metadata.resumed is True


def test_validate_resume_state_v3_rejects_repo_drift(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    snapshot = build_repo_snapshot(repo_root)
    snapshot_path = tmp_path / "snapshot.json"
    write_repo_snapshot(snapshot_path, snapshot)
    # Build a V3 record bound to a *different* tree hash.
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash="sha256:different",
    )
    with pytest.raises(ValueError, match="source_drift"):
        validate_resume_state_v3(v3, repo_snapshot_path=str(snapshot_path))


def test_validate_resume_state_v3_rejects_snapshot_mismatch(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    snapshot = build_repo_snapshot(repo_root)
    snapshot_path = tmp_path / "snapshot.json"
    write_repo_snapshot(snapshot_path, snapshot)
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:different",
        project_tree_hash=snapshot.project_tree_hash,
    )
    with pytest.raises(ValueError, match="another repo snapshot"):
        validate_resume_state_v3(v3, repo_snapshot_path=str(snapshot_path))


def test_validate_resume_state_dispatch_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError, match="unknown checkpoint schema"):
        validate_resume_state_dispatch(
            {"hello": "world"},
            repo_snapshot_path="/tmp/none.json",
        )


def test_validate_resume_state_dispatch_v3_requires_repo_path() -> None:
    v3 = AgentStateV3Record(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
    )
    with pytest.raises(ValueError, match="V3 resume requires repo_snapshot_path"):
        validate_resume_state_dispatch(
            v3.model_dump(mode="json"),
            repo_snapshot_path="",
        )
