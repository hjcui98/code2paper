"""Phase 0 schemas for the code-to-paper method evidence pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields so schema drift is caught early."""

    model_config = ConfigDict(extra="forbid")


class SourceType(str, Enum):
    CONFIG = "config"
    BASH = "bash"
    SOURCE = "source"
    COMMENT = "comment"
    AUTHOR = "author"


class ReadmePolicy(str, Enum):
    EXCLUDE = "exclude"
    CONFLICT_CHECK_ONLY = "conflict_check_only"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Importance(str, Enum):
    CORE = "core"
    SUPPORTING = "supporting"
    UTILITY = "utility"


class HighlightLevel(str, Enum):
    MAIN = "main"
    SECONDARY = "secondary"
    OMIT = "omit"


class AuthorLatexStyle(str, Enum):
    IMPLEMENTATION_FAITHFUL = "implementation-faithful"
    BALANCED = "balanced"
    PAPER_ABSTRACT = "paper-abstract"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ModuleCategory(str, Enum):
    METHOD_CORE = "method-core"
    EXPERIMENT_SUPPORT = "experiment-support"
    INFRA_UTILITY = "infra-utility"


class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class ConflictStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS_DUE_TO_MISSING_CONTEXT = "ambiguous_due_to_missing_context"


class EvidenceStrength(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    SEMANTIC_HINT = "semantic_hint"


class AuthorMode(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    ENHANCED = "enhanced"


class ClaimSupportLevel(str, Enum):
    NONE = "none"
    FILE = "file"
    SYMBOL = "symbol"
    MECHANISM = "mechanism"


class FormulaSource(str, Enum):
    CODE_PATTERN = "code_pattern"
    AUTHOR = "author"
    REFERENCE = "reference"
    HYBRID = "hybrid"


class CommentType(str, Enum):
    METHOD_EXPLANATION = "method_explanation"
    FLOW_HINT = "flow_hint"
    IMPLEMENTATION_NOTE = "implementation_note"
    EXPERIMENT_ENGINEERING = "experiment_engineering"
    STALE_OR_UNTRUSTED = "stale_or_untrusted"


class NavigationWeight(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    UNKNOWN = "unknown"
    POSSIBLY_STALE = "possibly_stale"
    STALE = "stale"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OPENROUTER = "openrouter"
    NONE = "none"


class EvidenceRefMixin(BaseModel):
    @field_validator("evidence_ids", "related_evidence_ids", mode="after", check_fields=False)
    @classmethod
    def _validate_evidence_ids(cls, value: list[str]) -> list[str]:
        for evidence_id in value:
            if not evidence_id.startswith("E") or len(evidence_id) == 1:
                raise ValueError("evidence IDs must start with 'E' and include an identifier")
        return value


class AuthorModuleRole(StrictModel):
    path: str
    symbol: str = ""
    role: str
    importance: Importance = Importance.CORE
    is_novel: bool = False
    notes: str = ""

    @field_validator("path", "role")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class AuthorPipelineStep(StrictModel):
    name: str
    purpose: str
    input: list[str] = Field(default_factory=list)
    output: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    highlight_level: HighlightLevel = HighlightLevel.MAIN
    omit_from_main_figure: bool = False

    @field_validator("name", "purpose")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class AuthorInnovationClaim(StrictModel):
    claim: str
    supporting_files: list[str] = Field(default_factory=list)
    supporting_functions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    caveats: list[str] = Field(default_factory=list)

    @field_validator("claim")
    @classmethod
    def _required_claim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim must not be empty")
        return value


class AuthorDesignIntent(StrictModel):
    intent: str
    rationale: str = ""
    supporting_files: list[str] = Field(default_factory=list)
    supporting_functions: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    caveats: list[str] = Field(default_factory=list)

    @field_validator("intent")
    @classmethod
    def _required_intent(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("intent must not be empty")
        return value


class AuthorPotentialMismatch(StrictModel):
    description: str
    files: list[str] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM

    @field_validator("description")
    @classmethod
    def _required_description(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be empty")
        return value


class AuthorMarkers(StrictModel):
    project_goal: str
    paper_method_goal: str = ""
    implementation_scope: str = ""
    method_mainline: str = ""
    paper_story_order: list[str] = Field(default_factory=list)
    deemphasize_details: list[str] = Field(default_factory=list)
    latex_expression_preference: AuthorLatexStyle = AuthorLatexStyle.BALANCED
    priority_files: list[str] = Field(default_factory=list)
    ignore_files: list[str] = Field(default_factory=list)
    module_roles: list[AuthorModuleRole] = Field(default_factory=list)
    pipeline_steps: list[AuthorPipelineStep] = Field(default_factory=list)
    design_intents: list[AuthorDesignIntent] = Field(default_factory=list)
    innovation_claims: list[AuthorInnovationClaim] = Field(default_factory=list)
    potential_mismatches: list[AuthorPotentialMismatch] = Field(default_factory=list)

    @field_validator("project_goal")
    @classmethod
    def _project_goal_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project_goal must not be empty")
        return value


class ExcludedSource(StrictModel):
    path: str
    reason: str

    @field_validator("path", "reason")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class EvidenceSpan(StrictModel):
    evidence_id: str
    source_type: SourceType
    path: str
    symbol: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    config_key: str | None = None
    shell_command_segment: str | None = None
    excerpt_hash: str = ""
    evidence_strength: EvidenceStrength | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, value: str) -> str:
        if not value.startswith("E") or len(value) == 1:
            raise ValueError("evidence_id must start with 'E' and include an identifier")
        return value

    @field_validator("path")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_line_span_and_strength(self) -> "EvidenceSpan":
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("line_start and line_end must be provided together")
        if self.line_start is not None:
            if self.line_start < 1 or self.line_end < 1:
                raise ValueError("line spans must be positive")
            if self.line_end < self.line_start:
                raise ValueError("line_end must be >= line_start")
        if self.evidence_strength is None:
            if self.source_type == SourceType.COMMENT:
                self.evidence_strength = EvidenceStrength.SOFT
            elif self.source_type == SourceType.AUTHOR:
                self.evidence_strength = EvidenceStrength.SEMANTIC_HINT
            else:
                self.evidence_strength = EvidenceStrength.HARD
        return self


class EvidenceItem(EvidenceSpan):
    content_summary: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("content_summary")
    @classmethod
    def _summary_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content_summary must not be empty")
        return value


class RawEvidencePack(StrictModel):
    project_id: str
    project_root: str
    author_mode: AuthorMode = AuthorMode.NONE
    author_confirmation_required: bool = True
    readme_policy: ReadmePolicy = ReadmePolicy.EXCLUDE
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    excluded_sources: list[ExcludedSource] = Field(default_factory=list)

    @field_validator("project_id", "project_root")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _unique_evidence_ids(self) -> "RawEvidencePack":
        ids = [item.evidence_id for item in self.evidence_items]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence_id values must be unique")
        return self


class FreshnessSignal(StrictModel):
    status: FreshnessStatus = FreshnessStatus.UNKNOWN
    reasons: list[str] = Field(default_factory=list)


class CommentIndexItem(StrictModel):
    comment_id: str
    evidence_id: str
    path: str
    symbol: str = ""
    line_start: int | None = None
    line_end: int | None = None
    comment_type: CommentType
    tags: list[str] = Field(default_factory=list)
    summary: str
    navigation_weight: NavigationWeight = NavigationWeight.LOW
    trust_score: float = Field(ge=0.0, le=1.0)
    freshness_or_staleness_signal: FreshnessSignal = Field(default_factory=FreshnessSignal)
    allowed_as_fact_evidence: bool = False

    @field_validator("comment_id")
    @classmethod
    def _comment_id_format(cls, value: str) -> str:
        if not value.startswith("CMT") or len(value) <= 3:
            raise ValueError("comment_id must start with 'CMT' and include an identifier")
        return value

    @field_validator("evidence_id")
    @classmethod
    def _evidence_id_format(cls, value: str) -> str:
        if not value.startswith("E") or len(value) == 1:
            raise ValueError("evidence_id must start with 'E' and include an identifier")
        return value

    @field_validator("path", "summary")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_line_span(self) -> "CommentIndexItem":
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("line_start and line_end must be provided together")
        if self.line_start is not None:
            if self.line_start < 1 or self.line_end < self.line_start:
                raise ValueError("comment line span must be positive and ordered")
        if self.allowed_as_fact_evidence:
            raise ValueError("comments cannot be allowed as fact evidence in Phase 1")
        return self


class CommentIndex(StrictModel):
    comments: list[CommentIndexItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_comment_ids(self) -> "CommentIndex":
        ids = [comment.comment_id for comment in self.comments]
        if len(ids) != len(set(ids)):
            raise ValueError("comment_id values must be unique")
        return self


class RawContextIndex(StrictModel):
    project_id: str
    entrypoint_candidates: list[str] = Field(default_factory=list)
    config_candidates: list[str] = Field(default_factory=list)
    source_span_index: list[str] = Field(default_factory=list)
    author_hint_spans: list[str] = Field(default_factory=list)
    excluded_sources: list[ExcludedSource] = Field(default_factory=list)
    token_budget: dict[str, int] = Field(default_factory=dict)

    @field_validator("project_id")
    @classmethod
    def _project_id_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project_id must not be empty")
        return value


class ContextMap(StrictModel):
    likely_entrypoints: list[str] = Field(default_factory=list)
    likely_config_candidates: list[str] = Field(default_factory=list)
    method_relevant_comments: list[str] = Field(default_factory=list)
    author_related_symbols: list[str] = Field(default_factory=list)
    method_affecting_config_keys: list[str] = Field(default_factory=list)
    source_trace_seeds: list[str] = Field(default_factory=list)
    ignore_or_low_priority: list[str] = Field(default_factory=list)


class Entrypoint(StrictModel, EvidenceRefMixin):
    path: str
    symbol: str
    called_by: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class ExecutionStage(StrictModel, EvidenceRefMixin):
    stage_id: str
    name: str
    description: str
    related_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("stage_id")
    @classmethod
    def _stage_id_format(cls, value: str) -> str:
        if not value.startswith("X"):
            raise ValueError("execution stage_id must start with 'X'")
        return value


class MethodStageAlignment(StrictModel, EvidenceRefMixin):
    stage_id: str
    name: str
    purpose: str
    related_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("stage_id")
    @classmethod
    def _stage_id_format(cls, value: str) -> str:
        if not value.startswith("M"):
            raise ValueError("method stage_id must start with 'M'")
        return value


class StageMapping(StrictModel):
    execution_stage_id: str
    method_stage_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class ConfigResolutionStep(StrictModel):
    source: str
    value: Any = None
    evidence_id: str | None = None
    kind: str = "source"


class ConfigResolution(StrictModel):
    resolved_key: str
    final_value: Any = None
    resolution_chain: list[ConfigResolutionStep] = Field(default_factory=list)

    @field_validator("resolved_key")
    @classmethod
    def _required_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("resolved_key must not be empty")
        return value


class AlignedModuleRole(StrictModel, EvidenceRefMixin):
    path: str
    symbol: str = ""
    role: str
    category: ModuleCategory
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class RoleConflict(StrictModel, EvidenceRefMixin):
    description: str
    severity: Severity = Severity.MEDIUM
    evidence_ids: list[str] = Field(default_factory=list)


class AuthorAlignment(StrictModel):
    matched_steps: list[str] = Field(default_factory=list)
    mismatched_steps: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    author_story_order: list[str] = Field(default_factory=list)
    preferred_method_stage_ids: list[str] = Field(default_factory=list)
    latex_expression_preference: AuthorLatexStyle = AuthorLatexStyle.BALANCED
    claim_assessments: list["AuthorClaimAssessment"] = Field(default_factory=list)


class AuthorClaimAssessment(StrictModel, EvidenceRefMixin):
    claim_text: str
    support_status: SupportStatus
    support_level: ClaimSupportLevel = ClaimSupportLevel.NONE
    supporting_files: list[str] = Field(default_factory=list)
    supporting_functions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)

    @field_validator("claim_text")
    @classmethod
    def _claim_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim_text must not be empty")
        return value


class CodeAlignmentIR(StrictModel):
    project_id: str
    author_mode: AuthorMode = AuthorMode.NONE
    author_confirmation_required: bool = True
    entrypoints: list[Entrypoint] = Field(default_factory=list)
    execution_stages: list[ExecutionStage] = Field(default_factory=list)
    method_stages: list[MethodStageAlignment] = Field(default_factory=list)
    stage_mappings: list[StageMapping] = Field(default_factory=list)
    config_resolutions: list[ConfigResolution] = Field(default_factory=list)
    module_roles: list[AlignedModuleRole] = Field(default_factory=list)
    role_conflicts: list[RoleConflict] = Field(default_factory=list)
    author_alignment: AuthorAlignment = Field(default_factory=AuthorAlignment)

    @model_validator(mode="after")
    def _validate_stage_mapping_refs(self) -> "CodeAlignmentIR":
        execution_ids = {stage.stage_id for stage in self.execution_stages}
        method_ids = {stage.stage_id for stage in self.method_stages}
        for mapping in self.stage_mappings:
            if mapping.execution_stage_id not in execution_ids:
                raise ValueError(f"unknown execution_stage_id: {mapping.execution_stage_id}")
            if mapping.method_stage_id not in method_ids:
                raise ValueError(f"unknown method_stage_id: {mapping.method_stage_id}")
        return self


class Phase2BlockedReport(StrictModel):
    project_id: str
    blocked_reason: str
    mode: str = "inspect-only"
    required_provider: LLMProvider = LLMProvider.NONE
    required_model: str = ""
    generated_prompt_artifacts: list[str] = Field(default_factory=list)
    author_review_questions: list[str] = Field(default_factory=list)


class NavigationQuestion(StrictModel):
    question_id: str
    question: str
    driven_by: list[str] = Field(default_factory=list)
    seed_span_ids: list[str] = Field(default_factory=list)
    target_paths_or_symbols: list[str] = Field(default_factory=list)
    priority: NavigationWeight = NavigationWeight.MEDIUM

    @field_validator("question_id")
    @classmethod
    def _question_id_format(cls, value: str) -> str:
        if not value.startswith("Q"):
            raise ValueError("question_id must start with Q")
        return value


class CommentTriage(StrictModel):
    high_priority_comment_ids: list[str] = Field(default_factory=list)
    medium_priority_comment_ids: list[str] = Field(default_factory=list)
    low_priority_comment_ids: list[str] = Field(default_factory=list)
    excluded_comment_ids: list[str] = Field(default_factory=list)


class AnalysisNavigationPlan(StrictModel):
    author_logic_summary: str = ""
    navigation_questions: list[NavigationQuestion] = Field(default_factory=list)
    suspected_core_symbols: list[str] = Field(default_factory=list)
    suspected_config_behavior_links: list[str] = Field(default_factory=list)
    claims_to_verify: list[str] = Field(default_factory=list)
    comment_triage: CommentTriage = Field(default_factory=CommentTriage)


class TraceFinding(StrictModel):
    finding_id: str
    question_id: str = ""
    trace_type: str
    summary: str
    hard_span_ids: list[str] = Field(default_factory=list)
    soft_span_ids: list[str] = Field(default_factory=list)
    status: ConflictStatus = ConflictStatus.AMBIGUOUS_DUE_TO_MISSING_CONTEXT


class TargetedCodeTracing(StrictModel):
    entrypoint_pipeline_tracing: list[TraceFinding] = Field(default_factory=list)
    core_mechanism_tracing: list[TraceFinding] = Field(default_factory=list)
    config_to_behavior_tracing: list[TraceFinding] = Field(default_factory=list)
    author_claim_verification: list[TraceFinding] = Field(default_factory=list)


class CodeMethodExecutionFlow(StrictModel):
    flow_id: str
    purpose: str
    ordered_steps: list[str] = Field(default_factory=list)
    entrypoint_span_ids: list[str] = Field(default_factory=list)
    config_resolution_span_ids: list[str] = Field(default_factory=list)


class CodeMethodModule(StrictModel):
    path: str
    symbols: list[str] = Field(default_factory=list)
    module_class: ModuleCategory
    paper_role: str
    evidence_span_ids: list[str] = Field(default_factory=list)
    llm_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class CandidateMechanism(StrictModel):
    mechanism_id: str
    name: str
    description: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    supporting_span_ids: list[str] = Field(default_factory=list)
    unsupported_parts: list[str] = Field(default_factory=list)

    @field_validator("mechanism_id")
    @classmethod
    def _mechanism_id_format(cls, value: str) -> str:
        if not value.startswith("MECH"):
            raise ValueError("mechanism_id must start with MECH")
        return value

    @model_validator(mode="after")
    def _require_hard_support(self) -> "CandidateMechanism":
        if not self.supporting_span_ids:
            raise ValueError("candidate mechanisms require at least one supporting evidence span")
        return self


class CommentDrivenInsight(StrictModel):
    insight: str
    comment_span_ids: list[str] = Field(default_factory=list)
    verified_by_hard_span_ids: list[str] = Field(default_factory=list)
    verification_status: ConflictStatus


class Phase2AuthorAlignment(StrictModel):
    author_proposed_flow: list[str] = Field(default_factory=list)
    author_supported_flow: list[str] = Field(default_factory=list)
    author_unsupported_parts: list[str] = Field(default_factory=list)


class CodeMethodAnalysis(StrictModel):
    navigation_questions: list[NavigationQuestion] = Field(default_factory=list)
    execution_flows: list[CodeMethodExecutionFlow] = Field(default_factory=list)
    method_modules: list[CodeMethodModule] = Field(default_factory=list)
    candidate_mechanisms: list[CandidateMechanism] = Field(default_factory=list)
    comment_driven_insights: list[CommentDrivenInsight] = Field(default_factory=list)
    author_alignment: Phase2AuthorAlignment = Field(default_factory=Phase2AuthorAlignment)
    candidate_distinguishing_mechanisms: list[str] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Phase1Manifest(StrictModel):
    project_id: str
    mode: str = "intake"
    readme_policy: ReadmePolicy = ReadmePolicy.EXCLUDE
    author_input_provided: bool = False
    outputs: dict[str, ArtifactHash] = Field(default_factory=dict)


class Phase2Manifest(StrictModel):
    project_id: str
    llm_required: bool = True
    llm_available: bool = False
    mode: str = "inspect-only"
    prompt_template_version: str = ""
    outputs: dict[str, ArtifactHash] = Field(default_factory=dict)
    llm_call_logs: list[str] = Field(default_factory=list)
    blocked_report: str = ""


class MethodModule(StrictModel):
    path: str
    symbols: list[str] = Field(default_factory=list)
    role: str
    category: ModuleCategory
    is_novel: bool = False


class MethodBehaviorPattern(StrictModel, EvidenceRefMixin):
    behavior_id: str
    behavior_type: str
    detected_pattern: str = ""
    description: str
    operations: list[str] = Field(default_factory=list)
    path: str
    symbol: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    @field_validator("behavior_id")
    @classmethod
    def _behavior_id_format(cls, value: str) -> str:
        if not value.startswith("BEH"):
            raise ValueError("behavior_id must start with 'BEH'")
        return value


class EquationCandidate(StrictModel, EvidenceRefMixin):
    equation_id: str
    name: str
    latex: str
    source: FormulaSource = FormulaSource.CODE_PATTERN
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    caveats: list[str] = Field(default_factory=list)

    @field_validator("equation_id")
    @classmethod
    def _equation_id_format(cls, value: str) -> str:
        if not value.startswith("EQ"):
            raise ValueError("equation_id must start with 'EQ'")
        return value


class ArchitectureParameter(StrictModel, EvidenceRefMixin):
    parameter_id: str
    name: str
    value: Any = None
    source: str
    path: str
    symbol: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    @field_validator("parameter_id")
    @classmethod
    def _parameter_id_format(cls, value: str) -> str:
        if not value.startswith("PARAM"):
            raise ValueError("parameter_id must start with 'PARAM'")
        return value


class TensorRole(StrictModel, EvidenceRefMixin):
    tensor_id: str
    name: str
    role: str
    path: str
    symbol: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    @field_validator("tensor_id")
    @classmethod
    def _tensor_id_format(cls, value: str) -> str:
        if not value.startswith("TENSOR"):
            raise ValueError("tensor_id must start with 'TENSOR'")
        return value


class SubMechanism(StrictModel, EvidenceRefMixin):
    submechanism_id: str
    description: str
    behavior_ids: list[str] = Field(default_factory=list)
    equation_ids: list[str] = Field(default_factory=list)
    parameter_ids: list[str] = Field(default_factory=list)
    tensor_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    @field_validator("submechanism_id")
    @classmethod
    def _submechanism_id_format(cls, value: str) -> str:
        if not value.startswith("SUBMECH"):
            raise ValueError("submechanism_id must start with 'SUBMECH'")
        return value


class Mechanism(StrictModel, EvidenceRefMixin):
    mechanism_id: str
    description: str
    support_status: SupportStatus
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    submechanisms: list[SubMechanism] = Field(default_factory=list)

    @field_validator("mechanism_id")
    @classmethod
    def _mechanism_id_format(cls, value: str) -> str:
        if not value.startswith("MECH"):
            raise ValueError("mechanism_id must start with 'MECH'")
        return value


class MethodStageEvidence(StrictModel):
    stage_id: str
    name: str
    purpose: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    modules: list[MethodModule] = Field(default_factory=list)
    mechanisms: list[Mechanism] = Field(default_factory=list)

    @field_validator("stage_id")
    @classmethod
    def _stage_id_format(cls, value: str) -> str:
        if not value.startswith("S"):
            raise ValueError("method evidence stage_id must start with 'S'")
        return value


class MethodImplementationAnchor(StrictModel):
    path: str
    symbols: list[str] = Field(default_factory=list)


class FrozenMechanism(StrictModel):
    mechanism_id: str
    mechanism_name: str
    mechanism_description: str
    parent_stage_id: str = ""
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    implementation_anchor: MethodImplementationAnchor = Field(default_factory=lambda: MethodImplementationAnchor(path=""))
    distinguishing_level: str = "none"
    author_claim_relation: ConflictStatus = ConflictStatus.SUPPORTED
    evidence_span_ids: list[str] = Field(default_factory=list)

    @field_validator("mechanism_id")
    @classmethod
    def _mechanism_id_format(cls, value: str) -> str:
        if not value.startswith("MECH"):
            raise ValueError("mechanism_id must start with MECH")
        return value

    @field_validator("distinguishing_level")
    @classmethod
    def _distinguishing_level(cls, value: str) -> str:
        if value not in {"none", "secondary", "main"}:
            raise ValueError("distinguishing_level must be none, secondary, or main")
        return value


class AuthorLogicMapping(StrictModel):
    author_proposed_flow: list[str] = Field(default_factory=list)
    author_supported_flow: list[str] = Field(default_factory=list)
    author_unsupported_parts: list[str] = Field(default_factory=list)


class ClaimContract(StrictModel):
    claim_id: str
    claim_intent: str
    support_status: ConflictStatus
    evidence_span_ids: list[str] = Field(default_factory=list)
    allowed_wording_boundary: str
    required_qualifiers: list[str] = Field(default_factory=list)
    review_question_id: str = ""

    @field_validator("claim_id")
    @classmethod
    def _claim_id_format(cls, value: str) -> str:
        if not value.startswith("C"):
            raise ValueError("claim_id must start with C")
        return value

    @model_validator(mode="after")
    def _supported_claims_need_evidence(self) -> "ClaimContract":
        if self.support_status == ConflictStatus.SUPPORTED and not self.evidence_span_ids:
            raise ValueError("supported claim contracts require evidence_span_ids")
        return self


class MethodEvidence(StrictModel):
    project_id: str
    author_mode: AuthorMode = AuthorMode.NONE
    author_confirmation_required: bool = True
    method_name: str
    method_goal: str
    implementation_scope: str
    latex_expression_preference: AuthorLatexStyle = AuthorLatexStyle.BALANCED
    entrypoints: list[str] = Field(default_factory=list)
    stages: list[MethodStageEvidence] = Field(default_factory=list)
    behavior_patterns: list[MethodBehaviorPattern] = Field(default_factory=list)
    equation_candidates: list[EquationCandidate] = Field(default_factory=list)
    architecture_parameters: list[ArchitectureParameter] = Field(default_factory=list)
    tensor_roles: list[TensorRole] = Field(default_factory=list)
    innovation_candidates: list[dict] = Field(default_factory=list)
    method_overview: dict = Field(default_factory=dict)
    stage_packets: list[dict] = Field(default_factory=list)
    writing_constraints: list[str] = Field(default_factory=list)
    alignment_notes: list[str] = Field(default_factory=list)
    excluded_sources: list[ExcludedSource] = Field(default_factory=list)
    author_logic_priority: bool = False
    frozen_mechanisms: list[FrozenMechanism] = Field(default_factory=list)
    distinguishing_mechanisms: list[str] = Field(default_factory=list)
    author_logic_mapping: AuthorLogicMapping = Field(default_factory=AuthorLogicMapping)
    unsupported_author_parts: list[str] = Field(default_factory=list)
    claim_contracts: list[ClaimContract] = Field(default_factory=list)
    negative_scope: list[str] = Field(default_factory=list)

    @field_validator("project_id", "method_name", "method_goal", "implementation_scope")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class Phase3StageBuilderOutput(StrictModel):
    stages: list[MethodStageEvidence] = Field(default_factory=list)


class Phase3MechanismBuilderOutput(StrictModel):
    frozen_mechanisms: list[FrozenMechanism] = Field(default_factory=list)


class Phase3DistinguishingMechanismOutput(StrictModel):
    distinguishing_mechanisms: list[str] = Field(default_factory=list)
    frozen_mechanisms: list[FrozenMechanism] = Field(default_factory=list)


class Phase3AuthorLogicOutput(StrictModel):
    author_logic_mapping: AuthorLogicMapping = Field(default_factory=AuthorLogicMapping)
    unsupported_author_parts: list[str] = Field(default_factory=list)


class Phase3ClaimContractOutput(StrictModel):
    claim_contracts: list[ClaimContract] = Field(default_factory=list)


class Phase3NegativeScopeOutput(StrictModel):
    negative_scope: list[str] = Field(default_factory=list)


class ClaimEvidenceItem(StrictModel, EvidenceRefMixin):
    claim_id: str
    claim_text: str
    support_status: SupportStatus
    evidence_ids: list[str] = Field(default_factory=list)
    mechanism_ids: list[str] = Field(default_factory=list)
    source: str = "method"
    caveats: list[str] = Field(default_factory=list)


class ClaimEvidenceMap(StrictModel):
    claims: list[ClaimEvidenceItem] = Field(default_factory=list)


class FidelityIssue(StrictModel):
    issue_id: str
    severity: Severity = Severity.MEDIUM
    category: str
    message: str
    evidence_ids: list[str] = Field(default_factory=list)
    paragraph: str = ""


class MethodFidelityReport(StrictModel):
    project_id: str
    passed: bool
    grounded_paragraphs: int = 0
    issues: list[FidelityIssue] = Field(default_factory=list)
    checked_claims: int = 0
    checked_evidence_items: int = 0


class ConfigValueIssue(StrictModel):
    issue_id: str
    severity: Severity = Severity.MEDIUM
    category: str
    message: str
    key: str
    written_value: Any = None
    expected_values: list[Any] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ConfigValueReport(StrictModel):
    project_id: str
    passed: bool
    checked_values: int = 0
    issues: list[ConfigValueIssue] = Field(default_factory=list)


class LLMConfig(StrictModel):
    provider: LLMProvider = LLMProvider.NONE
    model: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=12000, ge=1)
    request_timeout_seconds: int = Field(default=300, ge=1)
    retry_max_attempts: int = Field(default=5, ge=1)
    retry_initial_delay_seconds: float = Field(default=2.0, ge=0.0)
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0)
    fail_on_timeout: bool = True
    prompt_template_version: str = ""
    require_api_for_writing: bool = True
    cache: bool = True


class LLMCallLog(StrictModel):
    call_id: str
    provider: LLMProvider
    model: str
    prompt_template_id: str
    prompt_template_version: str = ""
    input_hash: str
    response_hash: str = ""
    temperature: float = Field(ge=0.0, le=2.0)
    max_output_tokens: int = Field(ge=1)
    schema_name: str = ""
    schema_validation_passed: bool = False
    blocked_reason: str = ""
    cached: bool = False
    created_at: str = ""

    @field_validator("call_id")
    @classmethod
    def _call_id_format(cls, value: str) -> str:
        if not value.startswith("LLM") or len(value) <= 3:
            raise ValueError("call_id must start with 'LLM' and include an identifier")
        return value

    @field_validator("prompt_template_id", "input_hash")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class ArtifactHash(StrictModel):
    path: str
    hash: str


class Phase3Manifest(StrictModel):
    project_id: str
    mode: str = "deterministic-freeze"
    llm_available: bool = False
    blocked_reason: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, ArtifactHash] = Field(default_factory=dict)
    llm_call_logs: list[str] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)


class MethodOutlineParagraph(StrictModel):
    paragraph_id: str
    purpose: str
    stage_ids: list[str] = Field(default_factory=list)
    mechanism_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)


class MethodOutline(StrictModel):
    sections: list[MethodOutlineParagraph] = Field(default_factory=list)
    author_logic_order: list[str] = Field(default_factory=list)


class TerminologyTerm(StrictModel):
    term_id: str
    canonical: str
    term_type: str
    allowed_synonyms: list[str] = Field(default_factory=list)
    forbidden_replacements: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)


class TerminologyTable(StrictModel):
    terms: list[TerminologyTerm] = Field(default_factory=list)


class DraftMarkdownOutput(StrictModel):
    markdown: str


class DraftLatexOutput(StrictModel):
    latex: str


class TargetedRevisionOutput(StrictModel):
    markdown: str
    latex: str
    revision_notes: list[str] = Field(default_factory=list)
    resolved_issue_ids: list[str] = Field(default_factory=list)


class DraftClaimMapParagraph(StrictModel):
    paragraph_id: str
    claim_ids: list[str] = Field(default_factory=list)
    mechanism_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)


class DraftClaimMap(StrictModel):
    paragraphs: list[DraftClaimMapParagraph] = Field(default_factory=list)


class MethodAuthoringSidecarParagraph(StrictModel):
    paragraph_id: str
    markdown_range: str = ""
    latex_range: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    evidence_span_ids: list[str] = Field(default_factory=list)
    llm_call_id: str = ""
    validator_status: str = "pending"


class MethodAuthoringSidecar(StrictModel):
    draft_version: int = 1
    method_outline_path: str
    terminology_table_path: str
    draft_claim_map_path: str
    paragraphs: list[MethodAuthoringSidecarParagraph] = Field(default_factory=list)
    revision_history: list[dict] = Field(default_factory=list)


class Phase4CriticIssue(StrictModel):
    issue_id: str
    severity: Severity = Severity.MEDIUM
    category: str
    message: str
    paragraph_id: str = ""


class SelfCriticReport(StrictModel):
    issues: list[Phase4CriticIssue] = Field(default_factory=list)


class Phase4BlockedReport(StrictModel):
    project_id: str
    blocked_reason: str
    generated_prompt_artifacts: list[str] = Field(default_factory=list)


class Phase4Manifest(StrictModel):
    project_id: str
    mode: str = "blocked"
    llm_available: bool = False
    blocked_reason: str = ""
    outputs: dict[str, ArtifactHash] = Field(default_factory=dict)
    llm_call_logs: list[str] = Field(default_factory=list)
    validator_reports: list[str] = Field(default_factory=list)


class Code2PaperRunManifest(StrictModel):
    run_id: str
    created_at: str
    project_root: str
    project_hash: str
    readme_policy: ReadmePolicy = ReadmePolicy.EXCLUDE
    author_input_hash: str = ""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    phase_inputs: dict[str, list[str]] = Field(default_factory=dict)
    phase_outputs: dict[str, ArtifactHash] = Field(default_factory=dict)
    final_draft_hash: str = ""
    validator_reports: list[str] = Field(default_factory=list)

    @field_validator("run_id", "created_at", "project_root", "project_hash")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value
