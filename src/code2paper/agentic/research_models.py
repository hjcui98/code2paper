"""Research-plane contracts for the robust LangGraph research agent.

These Pydantic models implement the V3 research contracts defined in
``docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md`` and
``docs/agentic_method_quality_next_execution_plan_2026-07-19.md`` R0.1:

- ``ResearchAgendaV1`` / ``ResearchAgendaItemV1``
- ``ResearchToolCallV1``
- ``ResearchObservationV1``
- ``ResearchIssueV1``
- ``ResearchDecisionV1``
- ``TextRepairIssueV1``
- ``QualityStateV2``

The models are contracts-only in R0.  No node, tool runtime or policy merge
imports them yet; that integration happens in R1+ batches.  All models use
``extra="forbid"`` so a malformed LLM proposal or tool result cannot silently
inject unknown fields into research state.

Every research artifact carries a ``repo_snapshot_id`` and, where relevant, a
``source_authority`` tag.  ``SourceAuthorityV1`` is re-exported here so callers
can import the full V3 contract surface from a single module.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from code2paper.agentic.source_authority import (
    SOURCE_AUTHORITY_LEVELS,
    SourceAuthorityV1,
    assert_authority_allows_positive_claim,
    can_support_positive_claim,
)


# ---------------------------------------------------------------------------
# Common enums / literals
# ---------------------------------------------------------------------------


ResearchAction = Literal[
    "SEARCH_SYMBOLS",
    "READ_CANDIDATE",
    "TRACE_CALLS",
    "TRACE_DATA_FLOW",
    "INSPECT_BRANCH",
    "INSPECT_CONFIG",
    "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH",
    "PROPOSE_PACKET",
    "COMPILE_FACTS",
    "DECOMPOSE_CLAIMS",
    "REWRITE_SENTENCES",
    "RECORD_GAP",
    "PLAN_METHOD",
    "STOP_BLOCKED",
]


RESEARCH_ACTIONS: tuple[ResearchAction, ...] = (
    "SEARCH_SYMBOLS",
    "READ_CANDIDATE",
    "TRACE_CALLS",
    "TRACE_DATA_FLOW",
    "INSPECT_BRANCH",
    "INSPECT_CONFIG",
    "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH",
    "PROPOSE_PACKET",
    "COMPILE_FACTS",
    "DECOMPOSE_CLAIMS",
    "REWRITE_SENTENCES",
    "RECORD_GAP",
    "PLAN_METHOD",
    "STOP_BLOCKED",
)


ResearchAgendaItemStatus = Literal[
    "pending",
    "in_progress",
    "supported",
    "partial",
    "explicit_gap",
    "blocked",
]


ResearchObservationStatus = Literal[
    "success",
    "success_empty",
    "scope_exhausted",
    "truncated",
    "parse_failed",
    "invalid_request",
]


ObligationPriority = Literal["must_cover", "should_cover", "preference", "verify_only"]


ToolKind = Literal[
    "symbol_search",
    "code_read",
    "call_trace",
    "data_flow_trace",
    "branch_inspection",
    "hint_search",
    "packet_repair",
    "behavior_graph",
    "configuration",
    "other",
]


TOOL_KINDS: tuple[ToolKind, ...] = (
    "symbol_search",
    "code_read",
    "call_trace",
    "data_flow_trace",
    "branch_inspection",
    "hint_search",
    "packet_repair",
    "behavior_graph",
    "configuration",
    "other",
)


# R3.4 per-obligation/per-tool-kind budget categories
BUDGET_TOOL_KINDS: tuple[ToolKind, ...] = (
    "symbol_search",
    "code_read",
    "call_trace",
    "data_flow_trace",
    "branch_inspection",
    "hint_search",
    "packet_repair",
)


TextRepairFailureType = Literal[
    "no_semantically_matching_projected_claim",
    "wrong_span_role",
    "direct_evidence_semantically_unrelated",
    "missing_relation",
    "missing_qualifier",
    "unsupported_rationale",
    "formula_unsupported",
    "branch_ambiguity",
    "semantic_verifier_exhausted",
    "method_language_style",
    "supported_claim_not_rendered",
]


TextRepairScope = Literal[
    "wording_only",
    "sentence_atomicity",
    "claim_decomposition",
    "packet_relation",
    "code_search",
    "drop_or_gap",
]


TEXT_REPAIR_FAILURE_TYPES: tuple[TextRepairFailureType, ...] = (
    "no_semantically_matching_projected_claim",
    "wrong_span_role",
    "direct_evidence_semantically_unrelated",
    "missing_relation",
    "missing_qualifier",
    "unsupported_rationale",
    "formula_unsupported",
    "branch_ambiguity",
    "semantic_verifier_exhausted",
    "method_language_style",
    "supported_claim_not_rendered",
)


TEXT_REPAIR_SCOPES: tuple[TextRepairScope, ...] = (
    "wording_only",
    "sentence_atomicity",
    "claim_decomposition",
    "packet_relation",
    "code_search",
    "drop_or_gap",
)


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class _ResearchModel(BaseModel):
    """Common config: forbid extra fields, freeze where useful."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Research agenda
# ---------------------------------------------------------------------------


class TypedBehaviorTargetV1(_ResearchModel):
    """A typed behavior target derived from author intent.

    The intent compiler (R5) produces these from author YAML.  Each target
    describes the *kind* of executable behavior the obligation wants to
    explain, without dictating the exact symbol path or claim wording.

    ``desired_predicates`` and ``required_relations`` use the generic
    predicate/relation vocabularies defined in
    ``code_behavior_graph`` (R2).  R0 only stores them as opaque tokens so the
    contract is stable even before the behavior graph ships.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    role: str = ""
    desired_predicates: tuple[str, ...] = Field(default_factory=tuple)
    # Concept-level alternatives. Every group must be satisfied, while any
    # predicate (or registered concrete alias) inside one group is enough.
    # Empty keeps the legacy meaning: every ``desired_predicates`` item is
    # independently required.
    predicate_groups: tuple[tuple[str, ...], ...] = Field(default_factory=tuple)
    required_relations: tuple[str, ...] = Field(default_factory=tuple)
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    transformations: tuple[str, ...] = Field(default_factory=tuple)
    decisions: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    conditions: tuple[str, ...] = Field(default_factory=tuple)
    search_terms: tuple[str, ...] = Field(default_factory=tuple)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    organization_preference: str = ""
    risk_level: Literal["low", "medium", "high"] = "medium"


class GapRequirementV1(_ResearchModel):
    """A typed requirement that, if unmet after exhaustive search, yields a gap."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str
    description: str
    required_predicate: str = ""
    required_relation: str = ""
    search_scope: str = ""
    attempted_tools: tuple[str, ...] = Field(default_factory=tuple)
    terminal: Literal["open", "explicit_gap", "blocked"] = "open"
    rationale: str = ""


class ResearchAgendaItemV1(_ResearchModel):
    """One research obligation the supervisor must drive to a terminal state.

    R0.1 contract: at minimum the fields below.  ``status`` is the only field
    the supervisor may advance without deterministic validator sign-off for
    ``supported``/``explicit_gap``/``blocked`` transitions (those are set by
    the fact/claim compiler and gap finalizer in R4).
    """

    model_config = ConfigDict(extra="forbid")

    obligation_id: str
    priority: ObligationPriority = "should_cover"
    author_text: str = ""
    typed_behavior_targets: list[TypedBehaviorTargetV1] = Field(default_factory=list)
    status: ResearchAgendaItemStatus = "pending"
    supported_claim_ids: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    attempted_actions: list[ResearchAction] = Field(default_factory=list)
    candidate_symbol_ids: list[str] = Field(default_factory=list)
    candidate_behavior_node_ids: list[str] = Field(default_factory=list)
    gap_requirements: list[GapRequirementV1] = Field(default_factory=list)
    no_progress_counter: int = 0
    last_information_gain: str = ""

    @field_validator("obligation_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("obligation_id must not be empty")
        return value

    @model_validator(mode="after")
    def _terminal_status_consistency(self) -> "ResearchAgendaItemV1":
        if self.status == "supported" and not self.supported_claim_ids:
            raise ValueError(
                f"obligation {self.obligation_id} marked supported without supported_claim_ids"
            )
        if self.status == "explicit_gap" and not self.gap_requirements:
            raise ValueError(
                f"obligation {self.obligation_id} marked explicit_gap without gap_requirements"
            )
        return self


class ResearchAgendaV1(_ResearchModel):
    """Ordered research agenda for a single run.

    The agenda is content-addressed so checkpoint resume can detect drift
    between the persisted agenda and the re-compiled intent graph.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    intent_graph_digest: str = ""
    items: list[ResearchAgendaItemV1] = Field(default_factory=list)
    content_digest: str = ""

    @field_validator("run_id", "repo_snapshot_id", "project_tree_hash")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _compute_digest(self) -> "ResearchAgendaV1":
        payload = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "repo_snapshot_id": self.repo_snapshot_id,
            "project_tree_hash": self.project_tree_hash,
            "intent_graph_digest": self.intent_graph_digest,
            "items": [item.model_dump(mode="json") for item in self.items],
        }
        digest = _digest_payload(payload)
        object.__setattr__(self, "content_digest", digest)
        return self

    @property
    def must_cover_items(self) -> list[ResearchAgendaItemV1]:
        return [item for item in self.items if item.priority == "must_cover"]

    @property
    def unresolved_must_cover_ids(self) -> list[str]:
        return [
            item.obligation_id
            for item in self.must_cover_items
            if item.status not in {"supported", "partial", "explicit_gap", "blocked"}
        ]


# ---------------------------------------------------------------------------
# Tool calls and observations
# ---------------------------------------------------------------------------


class ResearchToolCallV1(_ResearchModel):
    """A single tool call proposed by the supervisor and validated by policy.

    Every tool call MUST bind to an obligation and a snapshot scope.  Policy
    merge (R3) rejects calls with snapshot-external paths, missing obligation
    id, unknown tool name, or no remaining budget.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str
    tool_name: str
    tool_kind: ToolKind = "other"
    obligation_id: str
    goal: str
    repo_snapshot_id: str
    path_scope: tuple[str, ...] = Field(default_factory=tuple)
    top_k: int = 0
    depth: int = 0
    node_budget: int = 0
    arguments: dict[str, Any] = Field(default_factory=dict)
    input_digest: str = ""

    @field_validator("tool_call_id", "tool_name", "obligation_id", "repo_snapshot_id")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("top_k", "depth", "node_budget")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("budget fields must be nonnegative")
        return value


class ResearchObservationDiagnosticsV1(_ResearchModel):
    """Compact diagnostics returned alongside an observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_count: int = 0
    truncated: bool = False
    ambiguous: bool = False
    notes: tuple[str, ...] = Field(default_factory=tuple)


class ResearchObservationV1(_ResearchModel):
    """Deterministic result of executing a ``ResearchToolCallV1``.

    Empty results and tool errors MUST be distinguishable:

    - ``success``          : the tool executed and returned candidates
    - ``success_empty``    : the tool executed but nothing matched
    - ``scope_exhausted``  : the given scope has been fully searched
    - ``truncated``        : more candidates may exist beyond top_k/depth
    - ``parse_failed``     : the tool could not parse the requested source
    - ``invalid_request``  : policy rejected the call before execution

    ``source_authority`` records the *weakest* authority level among the
    returned spans so packet validators can refuse hint-only anchors without
    re-classifying every span.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    tool_call_id: str
    tool_name: str
    obligation_id: str
    repo_snapshot_id: str
    status: ResearchObservationStatus
    source_authority: SourceAuthorityV1 = "executable_hard"
    result_refs: tuple[str, ...] = Field(default_factory=tuple)
    exact_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    diagnostics: ResearchObservationDiagnosticsV1 = Field(
        default_factory=ResearchObservationDiagnosticsV1
    )
    input_digest: str = ""
    output_digest: str = ""
    error_message: str = ""

    @field_validator("source_authority")
    @classmethod
    def _known_authority(cls, value: SourceAuthorityV1) -> SourceAuthorityV1:
        if value not in SOURCE_AUTHORITY_LEVELS:
            raise ValueError(f"unknown source authority: {value}")
        return value

    @model_validator(mode="after")
    def _status_consistency(self) -> "ResearchObservationV1":
        if self.status == "invalid_request" and not self.error_message.strip():
            raise ValueError("invalid_request observations must carry an error_message")
        if self.status == "success" and not self.result_refs and not self.exact_span_ids:
            raise ValueError(
                "success observations must return at least one result_ref or exact_span_id; "
                "use success_empty for genuine zero-hit results"
            )
        return self

    @property
    def is_empty(self) -> bool:
        return self.status in {"success_empty", "scope_exhausted"}


# ---------------------------------------------------------------------------
# Research issues and decisions
# ---------------------------------------------------------------------------


class ResearchIssueV1(_ResearchModel):
    """Typed issue raised by the evidence critic, fact validator or final validator.

    The issue id is the join key between the supervisor decision and the
    issue-scoped repair surface (R6).  ``issue_kind`` is closed so policy
    merge can route each issue to a deterministic fallback action.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    issue_id: str
    issue_kind: Literal[
        "missing_anchor",
        "missing_relation",
        "missing_condition",
        "wrong_span_role",
        "direct_evidence_semantically_unrelated",
        "branch_ambiguity",
        "config_ambiguity",
        "no_semantically_matching_projected_claim",
        "sentence_claim_atomicity",
        "formula_unsupported",
        "hint_code_conflict",
        "truncated_observation",
        "ambiguous_observation",
        "no_information_gain",
        "budget_exhausted",
        "quality_regression",
    ]
    obligation_id: str = ""
    claim_id: str = ""
    packet_id: str = ""
    description: str
    missing_fact_or_relation: str = ""
    suggested_actions: tuple[ResearchAction, ...] = Field(default_factory=tuple)
    severity: Literal["info", "warning", "error"] = "warning"

    @field_validator("issue_id", "description")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class ResearchDecisionV1(_ResearchModel):
    """Structured decision returned by the research supervisor each turn.

    The supervisor may propose one or more independent tool calls per turn;
    CPU-only read tools can run in parallel, but Gemma inference stays serial
    (design 7.6).  Policy merge (R3.3) MUST reject decisions that violate any
    hard rule: snapshot-external paths, unregistered tools, authority
    upgrades, skipped validators, etc.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str
    run_id: str
    turn_index: int
    action: ResearchAction
    obligation_id: str = ""
    issue_id: str = ""
    goal: str
    selected_tool_calls: tuple[ResearchToolCallV1, ...] = Field(default_factory=tuple)
    candidate_scope: tuple[str, ...] = Field(default_factory=tuple)
    expected_information_gain: str = ""
    evidence_needed: tuple[str, ...] = Field(default_factory=tuple)
    stop_condition: str = ""
    fallback_action: ResearchAction | None = None
    rationale: str = ""
    produced_by: Literal["llm_proposal", "deterministic_fallback", "policy_override"] = "llm_proposal"

    @field_validator("decision_id", "run_id", "goal")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @field_validator("turn_index")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("turn_index must be nonnegative")
        return value

    @model_validator(mode="after")
    def _action_tool_alignment(self) -> "ResearchDecisionV1":
        # Actions that issue tool calls must select at least one.
        tool_calling_actions = {
            "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "TRACE_DATA_FLOW",
            "INSPECT_BRANCH", "INSPECT_CONFIG", "SEARCH_HINTS",
            "BUILD_BEHAVIOR_SUBGRAPH", "PROPOSE_PACKET", "COMPILE_FACTS",
            "DECOMPOSE_CLAIMS", "REWRITE_SENTENCES",
        }
        if self.action in tool_calling_actions and not self.selected_tool_calls:
            raise ValueError(
                f"action {self.action} requires at least one selected_tool_call"
            )
        # STOP_BLOCKED and RECORD_GAP must not issue tool calls.
        terminal_actions = {"STOP_BLOCKED", "RECORD_GAP", "PLAN_METHOD"}
        if self.action in terminal_actions and self.selected_tool_calls:
            raise ValueError(
                f"action {self.action} must not select tool calls"
            )
        return self


# ---------------------------------------------------------------------------
# Text repair issues (R6)
# ---------------------------------------------------------------------------


class TextRepairIssueV1(_ResearchModel):
    """A single sentence-level failure produced by the final validator.

    The repair supervisor (R6) is only allowed to act inside
    ``allowed_repair_scope``.  This contract forbids a single sentence failure
    from triggering a full intake/analysis/authoring rerun.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sentence_id: str
    atomic_claim_id: str = ""
    failure_type: TextRepairFailureType
    matched_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    offending_fragment: str = ""
    missing_fact_or_relation: str = ""
    allowed_repair_scope: TextRepairScope
    attempt: int = 0

    @field_validator("sentence_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sentence_id must not be empty")
        return value

    @field_validator("failure_type")
    @classmethod
    def _known_failure(cls, value: TextRepairFailureType) -> TextRepairFailureType:
        if value not in TEXT_REPAIR_FAILURE_TYPES:
            raise ValueError(f"unknown failure_type: {value}")
        return value

    @field_validator("allowed_repair_scope")
    @classmethod
    def _known_scope(cls, value: TextRepairScope) -> TextRepairScope:
        if value not in TEXT_REPAIR_SCOPES:
            raise ValueError(f"unknown allowed_repair_scope: {value}")
        return value

    @field_validator("attempt")
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("attempt must be nonnegative")
        return value


class PacketRepairRequestV1(_ResearchModel):
    """Fail-closed request for a packet-scoped evidence repair.

    This is deliberately narrower than a research or authoring rerun: it
    identifies one final claim, one packet (when known), and the exact spans
    or relation role that failed validation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    source_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    packet_id: str = ""
    failure_type: TextRepairFailureType
    offending_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    missing_relation_type: str = ""
    requested_scope: TextRepairScope
    attempt: int = 0

    @field_validator("claim_id")
    @classmethod
    def _claim_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim_id must not be empty")
        return value

    @field_validator("failure_type")
    @classmethod
    def _valid_failure(cls, value: TextRepairFailureType) -> TextRepairFailureType:
        if value not in TEXT_REPAIR_FAILURE_TYPES:
            raise ValueError(f"unknown failure_type: {value}")
        return value

    @field_validator("requested_scope")
    @classmethod
    def _valid_scope(cls, value: TextRepairScope) -> TextRepairScope:
        if value not in {"packet_relation", "code_search"}:
            raise ValueError("packet repair scope must be packet_relation or code_search")
        return value

    @field_validator("attempt")
    @classmethod
    def _attempt_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("attempt must be nonnegative")
        return value


# ---------------------------------------------------------------------------
# Quality state (R6.3, design 11)
# ---------------------------------------------------------------------------


class QualitySafetyDimensionsV1(_ResearchModel):
    """Safety dimensions: regression here always rejects the new state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_integrity: bool = True
    unsupported_positive_claims: int = 0
    stale_artifacts: int = 0
    invariant_failures: int = 0


class QualityContentDimensionsV1(_ResearchModel):
    """Content dimensions: must-cover and validated sentence counts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    terminal_must_cover: int = 0
    supported_must_cover: int = 0
    unique_supported_claims: int = 0
    validated_final_sentences: int = 0
    unresolved_high_value_obligations: int = 0


class QualityMinimalityDimensionsV1(_ResearchModel):
    """Minimality dimensions: duplicates and unjustified fan-in."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    duplicate_claims: int = 0
    unjustified_fan_in: int = 0
    unresolved_relations: int = 0


class QualityCostDimensionsV1(_ResearchModel):
    """Cost dimensions: tracked but never override safety/content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_calls: int = 0
    tool_calls: int = 0
    repeated_no_gain_calls: int = 0


class QualityStateV2(_ResearchModel):
    """Pareto-style quality state used for best-state retention.

    A new state replaces ``best`` only when:

    1. safety does not regress (``source_integrity`` stays True and the other
       safety counters do not increase), AND
    2. ``supported_must_cover`` does not decrease, AND
    3. ``unique_supported_claims`` does not decrease, AND
    4. ``validated_final_sentences`` does not decrease, AND
    5. ``duplicate_claims`` and ``unjustified_fan_in`` do not increase.

    ``explicit_gap`` may reduce ``unresolved_high_value_obligations`` but never
    counts as ``supported``.  ``unsupported_positive_claims`` MUST be zero for
    a state to be considered trusted.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_id: str
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    safety: QualitySafetyDimensionsV1 = Field(default_factory=QualitySafetyDimensionsV1)
    content: QualityContentDimensionsV1 = Field(default_factory=QualityContentDimensionsV1)
    minimality: QualityMinimalityDimensionsV1 = Field(default_factory=QualityMinimalityDimensionsV1)
    cost: QualityCostDimensionsV1 = Field(default_factory=QualityCostDimensionsV1)
    content_digest: str = ""

    @field_validator("state_id", "run_id", "repo_snapshot_id", "project_tree_hash")
    @classmethod
    def _required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _compute_digest(self) -> "QualityStateV2":
        payload = {
            "state_id": self.state_id,
            "run_id": self.run_id,
            "repo_snapshot_id": self.repo_snapshot_id,
            "project_tree_hash": self.project_tree_hash,
            "safety": self.safety.model_dump(mode="json"),
            "content": self.content.model_dump(mode="json"),
            "minimality": self.minimality.model_dump(mode="json"),
            "cost": self.cost.model_dump(mode="json"),
        }
        digest = _digest_payload(payload)
        object.__setattr__(self, "content_digest", digest)
        return self

    @property
    def is_trusted(self) -> bool:
        """A state is trusted only when no unsupported positive claims remain."""

        return (
            self.safety.source_integrity
            and self.safety.unsupported_positive_claims == 0
            and self.safety.invariant_failures == 0
        )

    @property
    def is_empty(self) -> bool:
        return (
            self.content.terminal_must_cover == 0
            and self.content.unique_supported_claims == 0
            and self.content.validated_final_sentences == 0
        )


def quality_state_dominates(
    candidate: QualityStateV2,
    incumbent: QualityStateV2,
) -> bool:
    """Return True when ``candidate`` may replace ``incumbent`` as best state.

    Implements the Pareto selection rule from design 11.  The rule is
    intentionally conservative: any safety regression, any loss of supported
    must-cover, any loss of unique supported claims, any loss of validated
    sentences, or any increase in duplicates/unjustified fan-in rejects the
    candidate.  Cost dimensions are tracked but never override safety/content.
    """

    # 1. safety must not regress
    if not candidate.safety.source_integrity:
        return False
    if candidate.safety.unsupported_positive_claims > incumbent.safety.unsupported_positive_claims:
        return False
    if candidate.safety.stale_artifacts > incumbent.safety.stale_artifacts:
        return False
    if candidate.safety.invariant_failures > incumbent.safety.invariant_failures:
        return False
    # 2. supported must-cover must not decrease
    if candidate.content.supported_must_cover < incumbent.content.supported_must_cover:
        return False
    # 3. unique supported claims must not decrease
    if candidate.content.unique_supported_claims < incumbent.content.unique_supported_claims:
        return False
    # 4. validated sentences must not decrease
    if candidate.content.validated_final_sentences < incumbent.content.validated_final_sentences:
        return False
    # 5. duplicates / unjustified fan-in must not increase
    if candidate.minimality.duplicate_claims > incumbent.minimality.duplicate_claims:
        return False
    if candidate.minimality.unjustified_fan_in > incumbent.minimality.unjustified_fan_in:
        return False
    # 6. unresolved high-value obligations must not increase
    if candidate.content.unresolved_high_value_obligations > incumbent.content.unresolved_high_value_obligations:
        return False
    # 7. at least one dimension must actually improve (or incumbent is empty)
    if incumbent.is_empty:
        return not candidate.is_empty
    improved = (
        candidate.content.supported_must_cover > incumbent.content.supported_must_cover
        or candidate.content.unique_supported_claims > incumbent.content.unique_supported_claims
        or candidate.content.validated_final_sentences > incumbent.content.validated_final_sentences
        or candidate.minimality.duplicate_claims < incumbent.minimality.duplicate_claims
        or candidate.minimality.unjustified_fan_in < incumbent.minimality.unjustified_fan_in
        or candidate.content.unresolved_high_value_obligations < incumbent.content.unresolved_high_value_obligations
        or candidate.safety.unsupported_positive_claims < incumbent.safety.unsupported_positive_claims
    )
    return improved


# ---------------------------------------------------------------------------
# Per-obligation budgets (R3.4)
# ---------------------------------------------------------------------------


class PerObligationBudgetV1(_ResearchModel):
    """Per-obligation, per-tool-kind budget envelope.

    R3.4 replaces the global ``max_*_rounds`` counters with per-obligation
    budgets so one hard obligation cannot exhaust the run's search capacity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    limits: dict[str, int] = Field(default_factory=dict)
    used: dict[str, int] = Field(default_factory=dict)

    @field_validator("obligation_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("obligation_id must not be empty")
        return value

    @model_validator(mode="after")
    def _budgets_nonnegative(self) -> "PerObligationBudgetV1":
        for kind, value in self.limits.items():
            if kind not in TOOL_KINDS:
                raise ValueError(f"unknown tool kind in limits: {kind}")
            if value < 0:
                raise ValueError(f"budget limit for {kind} must be nonnegative")
        for kind, value in self.used.items():
            if kind not in TOOL_KINDS:
                raise ValueError(f"unknown tool kind in used: {kind}")
            if value < 0:
                raise ValueError(f"used budget for {kind} must be nonnegative")
        return self

    def remaining(self, tool_kind: ToolKind) -> int:
        limit = self.limits.get(tool_kind, 0)
        used = self.used.get(tool_kind, 0)
        return max(0, limit - used)

    def consume(self, tool_kind: ToolKind, amount: int = 1) -> "PerObligationBudgetV1":
        if amount < 0:
            raise ValueError("amount must be nonnegative")
        used = dict(self.used)
        used[tool_kind] = used.get(tool_kind, 0) + amount
        return self.model_copy(update={"used": used})


class GlobalSafetyBudgetV1(_ResearchModel):
    """Hard global caps the supervisor may never exceed.

    These are fail-closed limits: a run that hits any of them MUST route to
    ``STOP_BLOCKED`` and emit a typed issue, never silently continue.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_total_tool_calls: int = 200
    max_total_model_calls: int = 60
    max_consecutive_no_gain_turns: int = 3
    max_explicit_gaps_per_run: int = 12

    @field_validator(
        "max_total_tool_calls",
        "max_total_model_calls",
        "max_consecutive_no_gain_turns",
        "max_explicit_gaps_per_run",
    )
    @classmethod
    def _nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("global safety budgets must be nonnegative")
        return value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def empty_quality_state(
    *, run_id: str, repo_snapshot_id: str, project_tree_hash: str
) -> QualityStateV2:
    """Return a zero-value quality state used to seed best-state retention."""

    return QualityStateV2(
        state_id=_stable_id("quality-state", run_id, repo_snapshot_id),
        run_id=run_id,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
    )


def make_observation(
    *,
    tool_call: ResearchToolCallV1,
    status: ResearchObservationStatus,
    source_authority: SourceAuthorityV1 = "executable_hard",
    result_refs: tuple[str, ...] = (),
    exact_span_ids: tuple[str, ...] = (),
    diagnostics: ResearchObservationDiagnosticsV1 | None = None,
    error_message: str = "",
    output_payload: Any = None,
) -> ResearchObservationV1:
    """Build a ``ResearchObservationV1`` with stable digests.

    R1 tool runtime calls this helper so every observation carries a stable
    input/output digest.  Keeping the helper here means the digest scheme is
    defined once, in the contract module.
    """

    input_digest = tool_call.input_digest or _digest_payload(
        {
            "tool_call_id": tool_call.tool_call_id,
            "tool_name": tool_call.tool_name,
            "obligation_id": tool_call.obligation_id,
            "repo_snapshot_id": tool_call.repo_snapshot_id,
            "arguments": tool_call.arguments,
        }
    )
    output_digest = _digest_payload(
        {
            "status": status,
            "source_authority": source_authority,
            "result_refs": list(result_refs),
            "exact_span_ids": list(exact_span_ids),
            "diagnostics": (diagnostics or ResearchObservationDiagnosticsV1()).model_dump(mode="json"),
            "error_message": error_message,
            "output_payload": output_payload,
        }
    )
    return ResearchObservationV1(
        observation_id=_stable_id(
            "obs", tool_call.tool_call_id, input_digest, output_digest
        ),
        tool_call_id=tool_call.tool_call_id,
        tool_name=tool_call.tool_name,
        obligation_id=tool_call.obligation_id,
        repo_snapshot_id=tool_call.repo_snapshot_id,
        status=status,
        source_authority=source_authority,
        result_refs=result_refs,
        exact_span_ids=exact_span_ids,
        diagnostics=diagnostics or ResearchObservationDiagnosticsV1(),
        input_digest=input_digest,
        output_digest=output_digest,
        error_message=error_message,
    )


def assert_observation_can_anchor_positive_claim(
    observation: ResearchObservationV1,
    *,
    context: str = "",
) -> None:
    """Hard gate used by R4 ``validate_evidence_packet``.

    A packet anchor sourced from a hint-only observation can never support a
    positive implementation claim.  The helper raises so the validator returns
    a typed ``wrong_span_role`` / ``direct_evidence_semantically_unrelated``
    issue instead of silently accepting the anchor.
    """

    assert_authority_allows_positive_claim(
        observation.source_authority,
        context=context or f"observation {observation.observation_id}",
    )


def can_observe_authority_for_positive_claim(
    observation: ResearchObservationV1,
) -> bool:
    """Non-raising variant for policy merge."""

    return can_support_positive_claim(observation.source_authority)


# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _stable_id(prefix: str, *parts: str) -> str:
    material = "\u241F".join(str(part) for part in parts if part)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


__all__ = [
    "BUDGET_TOOL_KINDS",
    "GlobalSafetyBudgetV1",
    "GapRequirementV1",
    "PerObligationBudgetV1",
    "PacketRepairRequestV1",
    "QualityContentDimensionsV1",
    "QualityCostDimensionsV1",
    "QualityMinimalityDimensionsV1",
    "QualitySafetyDimensionsV1",
    "QualityStateV2",
    "RESEARCH_ACTIONS",
    "ResearchAction",
    "ResearchAgendaItemStatus",
    "ResearchAgendaItemV1",
    "ResearchAgendaV1",
    "ResearchDecisionV1",
    "ResearchIssueV1",
    "ResearchObservationDiagnosticsV1",
    "ResearchObservationStatus",
    "ResearchObservationV1",
    "ResearchToolCallV1",
    "TEXT_REPAIR_FAILURE_TYPES",
    "TEXT_REPAIR_SCOPES",
    "TOOL_KINDS",
    "TextRepairFailureType",
    "TextRepairIssueV1",
    "TextRepairScope",
    "TypedBehaviorTargetV1",
    "ToolKind",
    "assert_observation_can_anchor_positive_claim",
    "can_observe_authority_for_positive_claim",
    "empty_quality_state",
    "make_observation",
    "quality_state_dominates",
]
