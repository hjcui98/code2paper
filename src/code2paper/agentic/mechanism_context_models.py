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
        payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
        expected = sha256_digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"mechanism seed content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
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
    shape_or_type_hints: tuple[str, ...] = ()
    source_fact_ids: tuple[str, ...] = ()
    exact_excerpt: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "EvidenceOperationV1":
        payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
        expected = sha256_digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"evidence operation content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
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
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""

    # Seed provenance is retained alongside the technical closure so a
    # deterministic identity merge can preserve the authoring links that
    # selected the closure.  These are provenance handles, not technical
    # evidence and never grant repository authority.
    seed_story_node_ids: tuple[str, ...] = ()
    seed_brief_ids: tuple[str, ...] = ()
    seed_facet_ids: tuple[str, ...] = ()
    seed_obligation_ids: tuple[str, ...] = ()
    seed_author_statements: tuple[str, ...] = ()

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
        node_operation_ids = tuple(op.operation_id for op in self.operation_nodes)
        if len(node_operation_ids) != len(set(node_operation_ids)):
            raise ValueError("operation_nodes must contain unique operation IDs")
        if len(self.exact_span_ids) != len(set(self.exact_span_ids)):
            raise ValueError("exact_span_ids must contain unique source span IDs")
        if self.exact_excerpts and len(self.exact_excerpts) != len(self.exact_span_ids):
            raise ValueError(
                "exact_excerpts must align one-to-one with exact_span_ids when supplied"
            )
        if self.operation_nodes and not self.operation_dispositions:
            raise ValueError(
                "operation_nodes require one terminal operation_disposition per operation"
            )
        if self.operation_dispositions:
            disposition_ids = tuple(d.operation_id for d in self.operation_dispositions)
            if len(disposition_ids) != len(set(disposition_ids)):
                raise ValueError(
                    "operation_dispositions must contain exactly one disposition per operation"
                )
            disp_op_ids = set(disposition_ids)
            node_op_ids = set(node_operation_ids)
            if disp_op_ids != node_op_ids:
                missing = node_op_ids - disp_op_ids
                extra = disp_op_ids - node_op_ids
                raise ValueError(
                    f"operation_dispositions set must match operation_nodes exactly. "
                    f"Missing: {missing}, Extra: {extra}"
                )
            expected_coverage = len(disp_op_ids) / len(node_op_ids) if node_op_ids else 0.0
            if abs(self.source_operation_terminal_coverage - expected_coverage) > 1e-6:
                raise ValueError(
                    "source_operation_terminal_coverage must equal the closed operation coverage"
                )
            for disposition in self.operation_dispositions:
                if disposition.disposition == "absorbed_by_detail" and not disposition.detail_ids:
                    raise ValueError(
                        f"absorbed operation {disposition.operation_id} must name an owning detail"
                    )
                if disposition.disposition == "explicitly_unresolved" and disposition.detail_ids:
                    raise ValueError(
                        f"unresolved operation {disposition.operation_id} cannot name detail owners"
                    )
                if disposition.disposition == "classified_side_branch" and len(
                    disposition.detail_ids
                ) > 1:
                    raise ValueError(
                        f"side-branch operation {disposition.operation_id} may have at most one detail owner"
                    )
        elif self.source_operation_terminal_coverage != 0.0:
            raise ValueError(
                "empty operation closure must have zero terminal operation coverage"
            )
        closure_fact_ids = set(self.fact_ids)
        closure_span_ids = set(self.exact_span_ids)
        for operation in self.operation_nodes:
            missing_fact_ids = set(operation.source_fact_ids) - closure_fact_ids
            if missing_fact_ids:
                raise ValueError(
                    f"operation {operation.operation_id} references unknown closure fact IDs: "
                    f"{sorted(missing_fact_ids)}"
                )
            if operation.source_span_id and operation.source_span_id not in closure_span_ids:
                raise ValueError(
                    f"operation {operation.operation_id} references unknown closure span ID: "
                    f"{operation.source_span_id}"
                )
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        else:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            expected = sha256_digest(payload)
            if self.content_digest != expected:
                raise ValueError(
                    f"evidence closure content_digest mismatch: got {self.content_digest}, expected {expected}"
                )
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
        payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
        expected = sha256_digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"detail witness atom content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
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
        if self.evidence_authority == "author_intent_only" and self.claim_kind in {
            "rationale", "specification",
        } and not (
            self.source_facet_ids or self.source_brief_ids or self.source_obligation_ids
        ):
            raise ValueError(
                f"Author-intent Detail {self.detail_id} must bind a facet, brief, or obligation"
            )
        if self.active_path_status in ("inactive_default", "unreachable") and (
            self.importance == "core" and self.publication_policy == "clean_candidate"
        ):
            raise ValueError(
                f"Detail {self.detail_id} with inactive status {self.active_path_status} "
                "cannot have importance='core' and publication_policy='clean_candidate'."
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
        atom_ids = tuple(atom.atom_id for atom in self.witness_atoms)
        if len(atom_ids) != len(set(atom_ids)):
            raise ValueError(f"Detail {self.detail_id} witness_atoms must have unique atom IDs")
        if (
            self.evidence_authority in ("repository_verified", "repository_partial")
            and self.claim_kind in ("implementation", "interface", "formalization")
            and not self.witness_atoms
        ):
            raise ValueError(
                f"Repository Detail {self.detail_id} must expose deterministic witness_atoms"
            )
        if not self.content_digest:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            object.__setattr__(self, "content_digest", sha256_digest(payload))
        else:
            payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
            expected = sha256_digest(payload)
            if self.content_digest != expected:
                raise ValueError(
                    f"mechanism detail content_digest mismatch: got {self.content_digest}, expected {expected}"
                )
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
        payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
        expected = sha256_digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"mechanism edge content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
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
        if self.evidence_closure.mechanism_id != self.mechanism_id:
            raise ValueError(
                "MechanismContext evidence_closure mechanism_id must match context mechanism_id"
            )
        detail_id_values = tuple(d.detail_id for d in self.details)
        if len(detail_id_values) != len(set(detail_id_values)):
            raise ValueError("MechanismContext details must have unique detail IDs")
        detail_ids = set(detail_id_values)
        for detail in self.details:
            if detail.primary_mechanism_id != self.mechanism_id:
                raise ValueError(
                    f"Detail {detail.detail_id} is owned by {detail.primary_mechanism_id}, "
                    f"not context mechanism {self.mechanism_id}"
                )
        closure = self.evidence_closure
        closure_operation_ids = {op.operation_id for op in closure.operation_nodes}
        closure_fact_ids = set(closure.fact_ids)
        closure_claim_ids = set(closure.claim_ids)
        closure_span_ids = set(closure.exact_span_ids)
        closure_equation_ids = set(closure.equation_ids)
        for detail in self.details:
            memberships = (
                ("operation", set(detail.source_operation_ids), closure_operation_ids),
                ("fact", set(detail.source_fact_ids), closure_fact_ids),
                ("claim", set(detail.source_claim_ids), closure_claim_ids),
                ("span", set(detail.source_span_ids), closure_span_ids),
                ("equation", set(detail.source_equation_ids), closure_equation_ids),
            )
            for label, values, allowed in memberships:
                unknown = values - allowed
                if unknown:
                    raise ValueError(
                        f"Detail {detail.detail_id} references unknown closure {label} IDs: {sorted(unknown)}"
                    )
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
        if len(self.ordered_detail_ids) != len(set(self.ordered_detail_ids)):
            raise ValueError("ordered_detail_ids must be unique")
        for field_name, values in (
            ("input_detail_ids", self.input_detail_ids),
            ("output_detail_ids", self.output_detail_ids),
        ):
            unknown = set(values) - detail_ids
            if unknown:
                raise ValueError(f"{field_name} reference unknown detail IDs: {sorted(unknown)}")
        for edge in self.edges:
            if edge.mechanism_id != self.mechanism_id:
                raise ValueError(
                    f"Edge {edge.edge_id} belongs to {edge.mechanism_id}, not {self.mechanism_id}"
                )
            if edge.source_detail_id not in detail_ids or edge.target_detail_id not in detail_ids:
                raise ValueError(f"Edge {edge.edge_id} references unknown context detail IDs")
        for disposition in closure.operation_dispositions:
            if disposition.operation_id not in closure_operation_ids:
                raise ValueError(
                    f"Operation disposition {disposition.operation_id} is not present in closure"
                )
            unknown_details = set(disposition.detail_ids) - detail_ids
            if unknown_details:
                raise ValueError(
                    f"Operation disposition {disposition.operation_id} references unknown details: "
                    f"{sorted(unknown_details)}"
                )
            # A disposition may omit detail_ids for a shared secondary
            # consumer or an explicitly unresolved operation.  If it names a
            # detail, however, the source operation must really belong to
            # that detail; otherwise the terminal ledger and paper annotation
            # describe different technical worlds.
            for detail_id in disposition.detail_ids:
                detail = next(item for item in self.details if item.detail_id == detail_id)
                if disposition.operation_id not in set(detail.source_operation_ids):
                    raise ValueError(
                        f"Operation disposition {disposition.operation_id} is not owned by "
                        f"detail {detail_id}"
                    )
        for ref in self.shared_detail_refs:
            if ref.consumer_mechanism_id != self.mechanism_id:
                raise ValueError(
                    f"Shared detail ref {ref.detail_id} has consumer {ref.consumer_mechanism_id}, "
                    f"not {self.mechanism_id}"
                )
        if not self.source_context_digest:
            payload = canonical_json_bytes(self, exclude_fields={"source_context_digest"})
            object.__setattr__(self, "source_context_digest", sha256_digest(payload))
        else:
            payload = canonical_json_bytes(self, exclude_fields={"source_context_digest"})
            expected = sha256_digest(payload)
            if self.source_context_digest != expected:
                raise ValueError(
                    "MechanismContext source_context_digest mismatch"
                )
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
        payload = canonical_json_bytes(self, exclude_fields={"content_digest"})
        expected = sha256_digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"mechanism context set content_digest mismatch: got {self.content_digest}, expected {expected}"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class MechanismContextViewV1(BaseModel):
    """Consumer-neutral reader/scientific projection of a MechanismContext."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str
    scientific_goal: dict[str, Any]
    author_intent: dict[str, Any]
    ordered_details: tuple[dict[str, Any], ...]
    operations: tuple[dict[str, Any], ...] = ()
    operation_dispositions: tuple[dict[str, Any], ...] = ()
    edges: tuple[dict[str, Any], ...]
    configurations: tuple[dict[str, Any], ...]
    exact_evidence: tuple[dict[str, Any], ...]
    unresolved_items: tuple[str, ...]

    source_context_digest: str
    view_digest: str = ""

    @model_validator(mode="after")
    def _compute_view_digest(self) -> "MechanismContextViewV1":
        payload = canonical_json_bytes(self, exclude_fields={"view_digest"})
        expected = sha256_digest(payload)
        if self.view_digest and self.view_digest != expected:
            raise ValueError(
                f"mechanism context view_digest mismatch: got {self.view_digest}, expected {expected}"
            )
        object.__setattr__(self, "view_digest", expected)
        return self


class MechanismContextSliceV1(BaseModel):
    """A bounded serialized slice of a MechanismContextView for LLM consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism_id: str
    slice_index: int
    detail_ids: tuple[str, ...]
    exact_evidence_ids: tuple[str, ...]
    view_digest: str
    # The IDs above are useful indexes, but are not the shared technical
    # payload.  ``technical_payload`` is the materialized, deterministic
    # slice that both consumers receive byte-for-byte.  Keeping it on the
    # slice prevents Formalizer and Writer from independently compacting the
    # canonical context into two subtly different technical worlds.
    technical_payload: dict[str, Any] = Field(default_factory=dict)
    core_detail_ids: tuple[str, ...] = ()
    shared_payload_digest: str = ""
    slice_digest: str = ""

    @model_validator(mode="after")
    def _compute_slice_digest(self) -> "MechanismContextSliceV1":
        payload = canonical_json_bytes(shared_slice_payload_record(self))
        expected = sha256_digest(payload)
        if self.slice_digest and self.slice_digest != expected:
            raise ValueError(
                f"mechanism context slice_digest mismatch: got {self.slice_digest}, expected {expected}"
            )
        object.__setattr__(self, "slice_digest", expected)
        detail_ids = tuple(str(value) for value in self.detail_ids)
        payload_detail_ids = tuple(
            str(item.get("detail_id"))
            for item in (self.technical_payload.get("details") or ())
            if isinstance(item, Mapping) and str(item.get("detail_id") or "").strip()
        )
        if "details" in self.technical_payload and payload_detail_ids != detail_ids:
            raise ValueError(
                "materialized slice detail_ids must match technical_payload details in order"
            )
        payload_core_ids = tuple(
            str(value) for value in (self.technical_payload.get("core_detail_ids") or ())
        )
        if (
            "core_detail_ids" in self.technical_payload
            and payload_core_ids != tuple(self.core_detail_ids)
        ):
            raise ValueError(
                "materialized slice core_detail_ids must match technical_payload"
            )
        return self

    @property
    def payload(self) -> dict[str, Any]:
        """Compatibility/readability alias for the materialized payload."""

        return self.technical_payload

    @property
    def serialized_payload(self) -> bytes:
        """Canonical bytes for this exact slice, excluding digest metadata."""

        return canonical_json_bytes(shared_slice_payload_record(self))


def shared_slice_payload_record(slice_obj: MechanismContextSliceV1 | Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical materialized record used by both consumers.

    Digest fields are metadata about the record and are intentionally excluded
    from the record being hashed.  This avoids a circular digest while still
    making the actual details, evidence, edges, configuration and unresolved
    state part of the shared bytes.
    """

    if isinstance(slice_obj, BaseModel):
        raw = slice_obj.model_dump(mode="json")
    elif isinstance(slice_obj, Mapping):
        raw = dict(slice_obj)
    else:
        raw = {}
    return {
        str(key): value
        for key, value in raw.items()
        if str(key) not in {"slice_digest", "shared_payload_digest"}
    }


def compute_source_context_digest(context: MechanismContextV1) -> str:
    payload = canonical_json_bytes(context, exclude_fields={"source_context_digest"})
    return sha256_digest(payload)


def compute_view_digest(view: MechanismContextViewV1) -> str:
    payload = canonical_json_bytes(view, exclude_fields={"view_digest"})
    return sha256_digest(payload)


def compute_slice_digest(slice_obj: MechanismContextSliceV1) -> str:
    payload = canonical_json_bytes(shared_slice_payload_record(slice_obj))
    return sha256_digest(payload)


def compute_shared_payload_digest(slices: tuple[MechanismContextSliceV1, ...]) -> str:
    # Hash the ordered materialized payload, not a list of self-reported
    # digest strings.  The latter allowed an ID-only slice to claim identity
    # while its actual technical contents were absent or diverged.
    payload = canonical_json_bytes([
        shared_slice_payload_record(slice_obj) for slice_obj in slices
    ])
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
    "shared_slice_payload_record",
    "compute_source_context_digest",
    "compute_view_digest",
    "compute_slice_digest",
    "compute_shared_payload_digest",
    "compute_consumer_request_digest",
]
