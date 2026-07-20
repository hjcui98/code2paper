"""R0.3 V3 state schema tests.

Exit conditions covered:
- all schemas use ``extra="forbid"``;
- checkpoint distinguishes V2/V3 (detect_state_schema + thread ids);
- feature flag defaults to off and can be toggled programmatically;
- reducers merge correctly across checkpoint resume.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.state_v3 import (
    GRAPH_CONTRACT_VERSION_V3,
    RESEARCH_FEATURE_FLAG,
    STATE_SCHEMA_VERSION_V3,
    AgentStateV3,
    AgentStateV3Record,
    CheckpointMetadataV3,
    checkpoint_thread_id_v3,
    detect_state_schema,
    disable_agentic_research_v3,
    empty_agent_state_v3,
    enable_agentic_research_v3,
    is_agentic_research_v3_enabled,
    append_unique,
    merge_counters,
    merge_mapping,
)


@pytest.fixture(autouse=True)
def _reset_feature_flag():
    """Ensure each test starts and ends with the V3 flag unset."""

    disable_agentic_research_v3()
    yield
    disable_agentic_research_v3()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_state_schema_version_is_3() -> None:
    assert STATE_SCHEMA_VERSION_V3 == "3.0"


def test_graph_contract_version_is_research_v3() -> None:
    assert GRAPH_CONTRACT_VERSION_V3 == "agentic-research-v3"


def test_feature_flag_name_matches_design() -> None:
    assert RESEARCH_FEATURE_FLAG == "agentic_research_v3"


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def test_feature_flag_defaults_off() -> None:
    assert is_agentic_research_v3_enabled() is False


def test_feature_flag_can_be_enabled() -> None:
    enable_agentic_research_v3()
    assert is_agentic_research_v3_enabled() is True


def test_feature_flag_can_be_disabled_after_enable() -> None:
    enable_agentic_research_v3()
    disable_agentic_research_v3()
    assert is_agentic_research_v3_enabled() is False


def test_feature_flag_truthy_values(monkeypatch) -> None:
    for raw in ("1", "true", "TRUE", "Yes", "on"):
        monkeypatch.setenv("CODE2PAPER_AGENTIC_RESEARCH_V3", raw)
        assert is_agentic_research_v3_enabled() is True, raw


def test_feature_flag_falsy_values(monkeypatch) -> None:
    for raw in ("", "0", "false", "off", "maybe"):
        monkeypatch.setenv("CODE2PAPER_AGENTIC_RESEARCH_V3", raw)
        assert is_agentic_research_v3_enabled() is False, raw


# ---------------------------------------------------------------------------
# AgentStateV3Record
# ---------------------------------------------------------------------------


def _v3_kwargs(**overrides):
    base = {
        "run_id": "run-1",
        "repo_snapshot_id": "repo:abc",
        "project_tree_hash": "sha256:tree",
    }
    base.update(overrides)
    return base


def test_record_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AgentStateV3Record(**_v3_kwargs(surprise=True))  # type: ignore[call-arg]


def test_record_requires_run_id_snapshot_and_hash() -> None:
    for field in ("run_id", "repo_snapshot_id", "project_tree_hash"):
        with pytest.raises(ValidationError):
            AgentStateV3Record(**_v3_kwargs(**{field: ""}))


def test_record_rejects_wrong_schema_version() -> None:
    with pytest.raises(ValidationError, match="unsupported V3 state schema version"):
        AgentStateV3Record(**_v3_kwargs(state_schema_version="2.0"))


def test_record_rejects_wrong_graph_contract() -> None:
    with pytest.raises(ValidationError, match="unsupported V3 graph contract"):
        AgentStateV3Record(**_v3_kwargs(graph_contract_version="agentic-graph-v3"))


def test_record_defaults_to_v3_versions() -> None:
    record = AgentStateV3Record(**_v3_kwargs())
    assert record.state_schema_version == STATE_SCHEMA_VERSION_V3
    assert record.graph_contract_version == GRAPH_CONTRACT_VERSION_V3
    assert record.status == "initialized"
    assert record.blocked_reason == ""


def test_record_to_state_dict_returns_typed_dict() -> None:
    record = AgentStateV3Record(**_v3_kwargs())
    state = record.to_state_dict()
    assert isinstance(state, dict)
    assert state["state_schema_version"] == STATE_SCHEMA_VERSION_V3
    assert state["graph_contract_version"] == GRAPH_CONTRACT_VERSION_V3
    assert state["run_id"] == "run-1"


def test_empty_agent_state_v3_seeds_default_policy() -> None:
    record = empty_agent_state_v3(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        project_tree_hash="sha256:tree",
    )
    assert record.status == "initialized"
    assert record.source_authority_policy["policy_id"] == "source-authority-v1"
    assert record.source_authority_policy["schema_version"] == "1.0"


# ---------------------------------------------------------------------------
# CheckpointMetadataV3
# ---------------------------------------------------------------------------


def test_checkpoint_metadata_v3_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CheckpointMetadataV3(  # type: ignore[call-arg]
            run_id="run-1",
            repo_snapshot_id="repo:abc",
            thread_id="t",
            checkpoint_backend="memory",
            surprise=True,
        )


def test_checkpoint_metadata_v3_defaults_to_v3_versions() -> None:
    metadata = CheckpointMetadataV3(
        run_id="run-1",
        repo_snapshot_id="repo:abc",
        thread_id="t",
        checkpoint_backend="memory",
    )
    assert metadata.state_schema_version == STATE_SCHEMA_VERSION_V3
    assert metadata.graph_contract_version == GRAPH_CONTRACT_VERSION_V3
    assert metadata.feature_flag == RESEARCH_FEATURE_FLAG
    assert metadata.resumed is False
    assert metadata.freshness_status == "not_checked"


def test_checkpoint_thread_id_v3_is_distinct_from_v2() -> None:
    thread = checkpoint_thread_id_v3(run_id="run-1", repo_snapshot_id="repo:abc")
    assert thread == f"run-1:repo:abc:{GRAPH_CONTRACT_VERSION_V3}"
    # V2 uses the older graph contract version; V3 must not collide.
    from code2paper.agentic.checkpointing import checkpoint_thread_id

    v2_thread = checkpoint_thread_id(run_id="run-1", repo_snapshot_id="repo:abc")
    assert thread != v2_thread


def test_checkpoint_thread_id_v3_requires_inputs() -> None:
    with pytest.raises(ValueError):
        checkpoint_thread_id_v3(run_id="", repo_snapshot_id="repo:abc")
    with pytest.raises(ValueError):
        checkpoint_thread_id_v3(run_id="run-1", repo_snapshot_id="")


# ---------------------------------------------------------------------------
# detect_state_schema
# ---------------------------------------------------------------------------


def test_detect_state_schema_v3_payload() -> None:
    record = AgentStateV3Record(**_v3_kwargs())
    assert detect_state_schema(record) == "v3"
    assert detect_state_schema(record.model_dump(mode="json")) == "v3"


def test_detect_state_schema_v3_by_graph_contract_only() -> None:
    payload = {"graph_contract_version": GRAPH_CONTRACT_VERSION_V3}
    assert detect_state_schema(payload) == "v3"


def test_detect_state_schema_v2_payload() -> None:
    payload = {
        "state_schema_version": "2.0",
        "graph_contract_version": "agentic-graph-v3",
    }
    assert detect_state_schema(payload) == "v2"


def test_detect_state_schema_unknown_payload() -> None:
    assert detect_state_schema({"hello": "world"}) == "unknown"
    assert detect_state_schema({}) == "unknown"


# ---------------------------------------------------------------------------
# Reducers
# ---------------------------------------------------------------------------


def test_merge_mapping_right_biased() -> None:
    left = {"a": 1, "b": 2}
    right = {"b": 20, "c": 3}
    assert merge_mapping(left, right) == {"a": 1, "b": 20, "c": 3}


def test_merge_mapping_handles_none_inputs() -> None:
    assert merge_mapping(None, {"a": 1}) == {"a": 1}  # type: ignore[arg-type]
    assert merge_mapping({"a": 1}, None) == {"a": 1}  # type: ignore[arg-type]


def test_merge_counters_takes_max() -> None:
    left = {"a": 3, "b": 1}
    right = {"a": 5, "c": 2}
    assert merge_counters(left, right) == {"a": 5, "b": 1, "c": 2}


def test_append_unique_deduplicates() -> None:
    left = [1, 2, 3]
    right = [3, 4, 5]
    assert append_unique(left, right) == [1, 2, 3, 4, 5]


def test_append_unique_deduplicates_pydantic_models() -> None:
    from code2paper.agentic.research_models import ResearchToolCallV1

    tc = ResearchToolCallV1(
        tool_call_id="TC-1",
        tool_name="search_symbols",
        tool_kind="symbol_search",
        obligation_id="OBL-1",
        goal="find encoder",
        repo_snapshot_id="repo:abc",
    )
    left = [tc]
    right = [tc.model_copy()]
    merged = append_unique(left, right)
    assert len(merged) == 1


# ---------------------------------------------------------------------------
# TypedDict shape sanity
# ---------------------------------------------------------------------------


def test_agent_state_v3_typed_dict_allows_partial_construction() -> None:
    # TypedDict with total=False should accept any subset of fields.
    state: AgentStateV3 = {"run_id": "run-1"}
    assert state["run_id"] == "run-1"
