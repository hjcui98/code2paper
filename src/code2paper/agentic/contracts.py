from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidencePolicy(str, Enum):
    """Evidence contract attached to an agent tool or graph node."""

    NONE = "none"
    RETRIEVES_EVIDENCE = "retrieves_evidence"
    ANALYZES_EVIDENCE = "analyzes_evidence"
    FREEZES_EVIDENCE = "freezes_evidence"
    CONSUMES_FROZEN_EVIDENCE = "consumes_frozen_evidence"
    VALIDATES_EVIDENCE = "validates_evidence"


class StageStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


class AgentDecision(BaseModel):
    """Auditable model or router decision made during an agentic run."""

    model_config = ConfigDict(extra="forbid")

    node: str
    decision: str
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_keys: list[str] = Field(default_factory=list)
    # V3 research supervisor fields preserved for R8 gap_driven_tool_selection.
    goal: str = ""
    issue_id: str = ""
    expected_information_gain: str = ""


class StageToolSpec(BaseModel):
    """Static contract for a stage exposed as a LangChain-style tool."""

    model_config = ConfigDict(extra="forbid")

    name: str
    stage: str
    description: str
    input_artifacts: list[str] = Field(default_factory=list)
    output_artifacts: list[str] = Field(default_factory=list)
    required_output_artifacts: list[str] = Field(default_factory=list)
    evidence_policy: EvidencePolicy = EvidencePolicy.NONE
    allow_model_decision: bool = False
    hard_gate: bool = False

    @field_validator("name", "stage", "description")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class StageToolResult(BaseModel):
    """Normalized result returned by every agentic stage tool."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    status: StageStatus
    artifacts: dict[str, str] = Field(default_factory=dict)
    summary: str = ""
    blocked_reason: str = ""
    decisions: list[AgentDecision] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == StageStatus.SUCCESS


class AgenticRunState(BaseModel):
    """Shared state shape for LangGraph nodes and tool calls.

    Paths are stored as real Path objects inside Python, but serialize cleanly to
    strings for LangGraph checkpoints, manifests, and debugging.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    state_schema_version: str = "2.0"
    graph_contract_version: str = "agentic-graph-v3"
    run_id: str = ""
    project_root: Path
    out_root: Path
    project_id: str = ""
    author_markers_path: str = ""
    intent_path: str = ""
    intent_ref: str = ""
    repo_snapshot_ref: str = ""
    model_profile_ref: str = ""
    llm_provider: str | None = None
    llm_model: str | None = None
    # D6 rollout controls are execution configuration, not evidence.  They
    # are checkpoint-safe so an interrupted run resumes with the same route
    # decision instead of silently reading a different process environment.
    execution_opt_in: bool = False
    execution_rollback: bool = False
    execution_canary_key: str = ""
    core_top_k: int = 12
    skip_draft_bootstrap: bool = False
    max_retrieval_rounds: int = 0
    max_evidence_revision_rounds: int = 0
    max_authoring_revision_rounds: int = 0
    max_figure_revision_rounds: int = 0
    max_semantic_verifier_calls: int = 0
    loop_counters: dict[str, int] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    decisions: list[AgentDecision] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    phase_statuses: dict[str, str] = Field(default_factory=dict)
    pending_gaps: list[str] = Field(default_factory=list)
    checkpoint_metadata: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str = ""
    next_node: str = ""

    @field_validator(
        "max_retrieval_rounds",
        "max_evidence_revision_rounds",
        "max_authoring_revision_rounds",
        "max_figure_revision_rounds",
        "max_semantic_verifier_calls",
    )
    @classmethod
    def _nonnegative_budget(cls, value: int) -> int:
        if value < 0:
            raise ValueError("agentic budgets must be nonnegative")
        return value

    @property
    def budgets(self) -> dict[str, int]:
        return {
            "max_retrieval_rounds": self.max_retrieval_rounds,
            "max_evidence_revision_rounds": self.max_evidence_revision_rounds,
            "max_authoring_revision_rounds": self.max_authoring_revision_rounds,
            "max_figure_revision_rounds": self.max_figure_revision_rounds,
            "max_semantic_verifier_calls": self.max_semantic_verifier_calls,
        }

    @property
    def method_root(self) -> Path:
        return self.out_root / "artifacts"

    @property
    def effective_author_markers_path(self) -> str:
        return self.author_markers_path or self.artifacts.get("resolved_author_markers", "")

    def with_result(self, result: StageToolResult) -> "AgenticRunState":
        artifacts = dict(self.artifacts)
        artifacts.update(result.artifacts)
        phase_statuses = {**self.phase_statuses, result.stage: result.status.value}
        return self.model_copy(
            update={
                "artifacts": artifacts,
                "repo_snapshot_ref": artifacts.get("repo_snapshot", self.repo_snapshot_ref),
                "phase_statuses": phase_statuses,
                "decisions": [*self.decisions, *result.decisions],
                "blocked_reason": result.blocked_reason if result.status == StageStatus.BLOCKED else "",
            }
        )

    def increment_loop(self, name: str) -> "AgenticRunState":
        counters = dict(self.loop_counters)
        counters[name] = int(counters.get(name, 0)) + 1
        return self.model_copy(update={"loop_counters": counters})


StageHandler = Callable[[AgenticRunState], StageToolResult]
