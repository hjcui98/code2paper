"""Canonical Unified Mechanism Context data models and digest contracts.

Implements the single canonical technical IR (MechanismContextV1) with:
- Lossless source-grounded EvidenceClosureV1
- Paper-facing annotation PaperDetails (MechanismDetailV1)
- Atomic witness obligations (DetailWitnessAtomV1)
- Explicit active-path precedence (ActivePathStatus)
- Three-dimensional authority: claim_kind x evidence_authority x publication_policy
- Paragraph-independent deterministic digests (source/view/slice/payload/request)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


ActivePathStatus = Literal[
    "active_default",
    "active_selected",
    "conditional",
    "inactive_default",
    "unreachable",
    "unknown",
]

DetailRole = Literal[
    "input",
    "representation",
    "transformation",
    "condition",
    "configuration",
    "branch",
    "output",
    "interface",
    "training_objective",
    "inference",
    "rationale",
    "limitation",
]

DetailImportance = Literal["core", "supporting", "side_branch"]

ClaimKind = Literal[
    "implementation",
    "rationale",
    "specification",
    "interface",
    "limitation",
    "formalization",
    "empirical",
]

EvidenceAuthority = Literal[
    "repository_verified",
    "repository_partial",
    "author_intent_only",
    "mismatch",
    "unresolved",
]

PublicationPolicy = Literal[
    "clean_candidate",
    "annotated_only",
    "review_only",
    "omit",
]

WitnessAtomKind = Literal[
    "operation",
    "operand",
    "output",
    "condition",
    "polarity",
    "interface",
    "formal_relation",
]

ContextReadiness = Literal[
    "repository_ready",
    "intent_ready",
    "partial",
    "blocked",
]

OperationDisposition = Literal[
    "absorbed_by_detail",
    "classified_supporting",
    "classified_side_branch",
    "explicitly_unresolved",
]


def canonical_json_bytes(data: Any, *, exclude_fields: set[str] | None = None) -> bytes:
    """Deterministic JSON serialization with sorted keys and no whitespace variation."""
    exclude = exclude_fields or set()

    def _clean(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            dumped = obj.model_dump(mode="json")
            return {k: _clean(v) for k, v in dumped.items() if k not in exclude}
        if isinstance(obj, Mapping):
            return {str(k): _clean(v) for k, v in obj.items() if str(k) not in exclude}
        if isinstance(obj, (list, tuple, set)):
            return [_clean(v) for v in obj]
        return obj

    cleaned = _clean(data)
    return json.dumps(
        cleaned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_digest(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


class MechanismSeedV1(BaseModel):
    """Narrow intent/alignment entry point for a mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seed_id: str
    story_node_ids: tuple[str, ...] = ()
    brief_ids: tuple[str, ...] = ()
    facet_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()

    author_statements: tuple[str, ...] = ()
    semantic_fields: tuple[dict[str, Any], ...] = ()

    bound_fact_ids: tuple[str, ...] = ()
    bound_claim_ids: tuple[str, ...] = ()
    bound_span_ids: tuple[str, ...] = ()
    bound_equation_ids: tuple[str, ...] = ()
    search_terms: tuple[str, ...] = ()

    formula_expectations: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MechanismSeedV1":
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class EvidenceOperationV1(BaseModel):
    """Source-grounded operation node in a mechanism evidence closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str
    symbol_id: str = ""
    predicate: str
    operands: tuple[str, ...] = ()
    result: str = ""
    guard: str = ""
    source_span_id: str
    relation_ids: tuple[str, ...] = ()
    active_path_status: ActivePathStatus = "unknown"
    activation_basis_ids: tuple[str, ...] = ()
    exact_excerpt: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "EvidenceOperationV1":
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class SourceOperationDispositionV1(BaseModel):
    """Terminal disposition of an operation node in an evidence closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str
    disposition: OperationDisposition
    detail_ids: tuple[str, ...] = ()
    reason_code: str = ""


class MechanismEvidenceClosureV1(BaseModel):
    """Lossless, source-grounded technical closure of a mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    closure_id: str
    mechanism_id: str

    entry_symbol_ids: tuple[str, ...] = ()
    operation_nodes: tuple[EvidenceOperationV1, ...] = ()
    call_relation_ids: tuple[str, ...] = ()
    data_flow_relation_ids: tuple[str, ...] = ()
    control_flow_relation_ids: tuple[str, ...] = ()

    configuration_bindings: tuple[dict[str, Any], ...] = ()
    active_path_conditions: tuple[str, ...] = ()
    default_activation: ActivePathStatus = "unknown"

    fact_ids: tuple[str, ...] = ()
    claim_ids: tuple[str, ...] = ()
    equation_ids: tuple[str, ...] = ()
    exact_span_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()
    source_digests: dict[str, str] = Field(default_factory=dict)

    shape_or_type_hints: tuple[str, ...] = ()
    return_value_descriptors: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    operation_dispositions: tuple[SourceOperationDispositionV1, ...] = ()
    source_operation_terminal_coverage: float = 0.0
    budget_exhausted: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_closure_invariants(self) -> "MechanismEvidenceClosureV1":
        if self.operation_dispositions:
            disp_op_ids = {d.operation_id for d in self.operation_dispositions}
            node_op_ids = {op.operation_id for op in self.operation_nodes}
            if disp_op_ids != node_op_ids:
                missing = node_op_ids - disp_op_ids
                extra = disp_op_ids - node_op_ids
                raise ValueError(
                    f"operation_dispositions set must match operation_nodes exactly. "
                    f"Missing: {missing}, Extra: {extra}"
                )
            if self.operation_nodes:
                expected_coverage = len(disp_op_ids) / len(node_op_ids)
                if abs(self.source_operation_terminal_coverage - expected_coverage) > 1e-6:
                    object.__setattr__(
                        self, "source_operation_terminal_coverage", expected_coverage
                    )
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class DetailWitnessAtomV1(BaseModel):
    """Deterministic atomic contract inside a mechanism detail."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    atom_id: str
    atom_kind: WitnessAtomKind
    semantic_anchor: str
    required: bool = True
    source_operation_ids: tuple[str, ...] = ()
    source_anchor_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()
    required_conditions: tuple[str, ...] = ()
    required_polarity: str = "unknown"
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "DetailWitnessAtomV1":
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class MechanismDetailV1(BaseModel):
    """Paper-facing annotation over an evidence closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detail_id: str
    primary_mechanism_id: str
    shared_with_mechanism_ids: tuple[str, ...] = ()
    order_index: int

    role: DetailRole
    importance: DetailImportance
    claim_kind: ClaimKind
    evidence_authority: EvidenceAuthority
    publication_policy: PublicationPolicy

    semantic_atom: str
    subject: str = ""
    predicate: str = ""
    operands: tuple[str, ...] = ()
    result: str = ""
    conditions: tuple[str, ...] = ()
    polarity: str = "unknown"
    shape_or_type_hints: tuple[str, ...] = ()

    active_path_status: ActivePathStatus = "unknown"
    activation_basis_ids: tuple[str, ...] = ()

    predecessor_detail_ids: tuple[str, ...] = ()
    successor_detail_ids: tuple[str, ...] = ()

    source_operation_ids: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = ()
    source_claim_ids: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    source_equation_ids: tuple[str, ...] = ()
    exact_excerpts: tuple[str, ...] = ()

    source_facet_ids: tuple[str, ...] = ()
    source_brief_ids: tuple[str, ...] = ()
    source_obligation_ids: tuple[str, ...] = ()
    author_statements: tuple[str, ...] = ()
    mismatch_reason: str = ""

    formalizable: bool = False
    formula_role: str = ""
    formalizable_signatures: tuple[dict[str, Any], ...] = ()

    witness_atoms: tuple[DetailWitnessAtomV1, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_detail_invariants(self) -> "MechanismDetailV1":
        if (
            self.evidence_authority in ("repository_verified", "repository_partial")
            and self.claim_kind in ("implementation", "interface", "formalization")
        ):
            has_source = bool(
                self.source_operation_ids
                or self.source_fact_ids
                or self.source_span_ids
                or self.source_equation_ids
            )
            if not has_source:
                raise ValueError(
                    f"Detail {self.detail_id} with authority {self.evidence_authority} "
                    f"and kind {self.claim_kind} must bind to source operations/facts/spans/equations."
                )
        if self.active_path_status in ("inactive_default", "unreachable"):
            if self.importance == "core" and self.publication_policy == "clean_candidate":
                raise ValueError(
                    f"Detail {self.detail_id} with inactive status {self.active_path_status} "
                    f"cannot have importance='core' and publication_policy='clean_candidate'."
                )
        if self.witness_atoms and self.source_operation_ids:
            detail_ops = set(self.source_operation_ids)
            for atom in self.witness_atoms:
                if atom.source_operation_ids:
                    invalid = set(atom.source_operation_ids) - detail_ops
                    if invalid:
                        raise ValueError(
                            f"Witness atom {atom.atom_id} references operation IDs {invalid} "
                            f"not in detail {self.detail_id} source operations {detail_ops}."
                        )
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class MechanismEdgeV1(BaseModel):
    """Semantic relation between mechanism details."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str
    mechanism_id: str
    source_detail_id: str
    target_detail_id: str
    relation: Literal[
        "feeds",
        "conditions",
        "branches_to",
        "produces",
        "consumes",
        "contrasts_with",
        "precedes",
    ]
    source_relation_ids: tuple[str, ...] = ()
    source_span_ids: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MechanismEdgeV1":
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class SharedDetailRefV1(BaseModel):
    """Secondary reference to a detail canonically owned by another mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detail_id: str
    primary_mechanism_id: str
    consumer_mechanism_id: str
    role: Literal["shared_interface", "shared_representation", "secondary_consumer"]

    @model_validator(mode="after")
    def _validate_shared_ref(self) -> "SharedDetailRefV1":
        if self.primary_mechanism_id == self.consumer_mechanism_id:
            raise ValueError(
                f"SharedDetailRef {self.detail_id} primary and consumer mechanisms must differ; "
                f"use canonical detail in primary mechanism instead."
            )
        return self


class MechanismContextV1(BaseModel):
    """Single canonical technical IR for a scientific mechanism."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    mechanism_id: str
    mechanism_name: str

    scientific_role: str
    reader_question: str
    purpose: str
    importance: Literal["core", "supporting", "side_branch"]

    story_node_ids: tuple[str, ...] = ()
    brief_ids: tuple[str, ...] = ()
    facet_ids: tuple[str, ...] = ()
    obligation_ids: tuple[str, ...] = ()
    author_statements: tuple[str, ...] = ()
    notation_hints: tuple[str, ...] = ()

    evidence_closure: MechanismEvidenceClosureV1

    input_detail_ids: tuple[str, ...] = ()
    ordered_detail_ids: tuple[str, ...] = ()
    output_detail_ids: tuple[str, ...] = ()
    details: tuple[MechanismDetailV1, ...] = ()
    edges: tuple[MechanismEdgeV1, ...] = ()
    shared_detail_refs: tuple[SharedDetailRefV1, ...] = ()

    formalizable_signatures: tuple[dict[str, Any], ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    context_readiness: ContextReadiness = "partial"
    readiness_failures: tuple[str, ...] = ()
    budget_exhausted: bool = False

    source_context_digest: str = ""

    @model_validator(mode="after")
    def _validate_context_invariants(self) -> "MechanismContextV1":
        for forbidden in ("section_", "paragraph_", "consumer_"):
            if forbidden in self.mechanism_id:
                raise ValueError(
                    f"mechanism_id '{self.mechanism_id}' cannot contain paragraph or section identifiers."
                )
        detail_ids = {d.detail_id for d in self.details}
        for did in self.ordered_detail_ids:
            if did not in detail_ids:
                raise ValueError(
                    f"ordered_detail_id '{did}' not found in mechanism details."
                )
        core_detail_ids = {d.detail_id for d in self.details if d.importance == "core"}
        ordered_set = set(self.ordered_detail_ids)
        missing_core = core_detail_ids - ordered_set
        if missing_core:
            raise ValueError(
                f"Core details {missing_core} must be included in ordered_detail_ids."
            )
        if not self.source_context_digest:
            payload = canonical_json_bytes(self, exclude_fields={"source_context_digest"})
            object.__setattr__(self, "source_context_digest", sha256_digest(payload))
        return self


class MechanismContextSetV1(BaseModel):
    """Container of all mechanism contexts compiled for a repository snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    repo_snapshot_id: str
    project_tree_hash: str
    intent_digest: str
    alignment_digest: str
    research_digest: str

    contexts: tuple[MechanismContextV1, ...]
    unresolved_seed_ids: tuple[str, ...] = ()
    compiler_diagnostics: tuple[dict[str, Any], ...] = ()

    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "MechanismContextSetV1":
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        return self


class MechanismContextViewV1(BaseModel):
    """Consumer-neutral reader/scientific projection of a MechanismContext."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str
    scientific_goal: dict[str, Any]
    author_intent: dict[str, Any]
    ordered_details: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    configurations: tuple[dict[str, Any], ...]
    exact_evidence: tuple[dict[str, Any], ...]
    unresolved_items: tuple[str, ...]

    source_context_digest: str
    view_digest: str = ""

    @model_validator(mode="after")
    def _compute_view_digest(self) -> "MechanismContextViewV1":
        if not self.view_digest:
            payload = canonical_json_bytes(self, exclude_fields={"view_digest"})
            object.__setattr__(self, "view_digest", sha256_digest(payload))
        return self


class MechanismContextSliceV1(BaseModel):
    """A bounded serialized slice of a MechanismContextView for LLM consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str
    slice_index: int
    detail_ids: tuple[str, ...]
    exact_evidence_ids: tuple[str, ...]
    view_digest: str
    slice_digest: str = ""

    @model_validator(mode="after")
    def _compute_slice_digest(self) -> "MechanismContextSliceV1":
        if not self.slice_digest:
            payload = canonical_json_bytes(self, exclude_fields={"slice_digest"})
            object.__setattr__(self, "slice_digest", sha256_digest(payload))
        return self


def compute_source_context_digest(context: MechanismContextV1) -> str:
    payload = canonical_json_bytes(context, exclude_fields={"source_context_digest"})
    return sha256_digest(payload)


def compute_view_digest(view: MechanismContextViewV1) -> str:
    payload = canonical_json_bytes(view, exclude_fields={"view_digest"})
    return sha256_digest(payload)


def compute_slice_digest(slice_obj: MechanismContextSliceV1) -> str:
    payload = canonical_json_bytes(slice_obj, exclude_fields={"slice_digest"})
    return sha256_digest(payload)


def compute_shared_payload_digest(slices: tuple[MechanismContextSliceV1, ...]) -> str:
    payload = canonical_json_bytes([s.slice_digest for s in slices])
    return sha256_digest(payload)


def compute_consumer_request_digest(
    shared_payload_digest: str,
    role_task: Mapping[str, Any],
) -> str:
    combined = {
        "shared_payload_digest": shared_payload_digest,
        "task": dict(role_task),
    }
    return sha256_digest(canonical_json_bytes(combined))


__all__ = [
    "ActivePathStatus",
    "DetailRole",
    "DetailImportance",
    "ClaimKind",
    "EvidenceAuthority",
    "PublicationPolicy",
    "WitnessAtomKind",
    "ContextReadiness",
    "OperationDisposition",
    "canonical_json_bytes",
    "sha256_digest",
    "MechanismSeedV1",
    "EvidenceOperationV1",
    "SourceOperationDispositionV1",
    "MechanismEvidenceClosureV1",
    "DetailWitnessAtomV1",
    "MechanismDetailV1",
    "MechanismEdgeV1",
    "SharedDetailRefV1",
    "MechanismContextV1",
    "MechanismContextSetV1",
    "MechanismContextViewV1",
    "MechanismContextSliceV1",
    "compute_source_context_digest",
    "compute_view_digest",
    "compute_slice_digest",
    "compute_shared_payload_digest",
    "compute_consumer_request_digest",
]
