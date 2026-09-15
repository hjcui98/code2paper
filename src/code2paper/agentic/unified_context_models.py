"""Three-layer Unified Context contracts (V2): archive, workset, invocation plan.

Implements the second-phase data contracts from
``docs/dyg_mamba_unified_live_run_failure_diagnosis_and_remediation_2026-09-08.md``:

- ``UnifiedContextArchiveV2``: lossless full-evidence archive for audit and
  reconstruction; never sent to a model as-is.
- ``ConsumerWorksetManifestV2``: deterministic minimal-closure projection for
  one consumer task; self-contained technical pages plus join pages.
- ``ConsumerInvocationPlanV1`` / ``RunInvocationBudgetEnvelopeV1``: frozen,
  bounded actual call plans and per-run budget envelopes admitted before the
  first model request.

Every model is ``extra="forbid", frozen=True``.  ID tuples that represent sets
are sorted and de-duplicated on construction; tuples that represent technical
or narrative order are preserved verbatim and validated for uniqueness.  All
``content_digest`` values are computed with
``canonical_json_bytes(..., exclude_fields={"content_digest"})`` and
``sha256_digest`` so a caller can never submit a digest that disagrees with
its content.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.mechanism_context_models import (
    EvidenceOperationV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEdgeV1,
    canonical_json_bytes,
    conservative_token_estimate,
    sha256_digest,
)


# ---------------------------------------------------------------------------
# Typed failure codes (remediation plan section 9.10).
# ---------------------------------------------------------------------------

UNIFIED_SOURCE_MANIFEST_MISSING = "unified_source_manifest_missing"
UNIFIED_SOURCE_MANIFEST_INVALID = "unified_source_manifest_invalid"
UNIFIED_PROJECT_TREE_HASH_MISMATCH = "unified_project_tree_hash_mismatch"
UNIFIED_SOURCE_SPAN_UNMAPPED = "unified_source_span_unmapped"
UNIFIED_AUTHORING_CLOSED_SET_MISMATCH = "unified_authoring_closed_set_mismatch"
UNIFIED_CORE_INTENT_UNSEARCHED = "unified_core_intent_unsearched"
UNIFIED_CORE_INTENT_PARTIAL_WITHOUT_TERMINAL_GAP = (
    "unified_core_intent_partial_without_terminal_gap"
)
UNIFIED_MECHANISM_OWNER_MISSING = "unified_mechanism_owner_missing"
UNIFIED_MECHANISM_OWNER_CONFLICT = "unified_mechanism_owner_conflict"
UNIFIED_MECHANISM_PATH_DISCONNECTED = "unified_mechanism_path_disconnected"
UNIFIED_PAGE_PROJECTION_INCOMPLETE = "unified_page_projection_incomplete"
UNIFIED_PAGE_PROJECTION_OVERREACH = "unified_page_projection_overreach"
UNIFIED_ATOMIC_PAGE_OVER_BUDGET = "unified_atomic_page_over_budget"
UNIFIED_INVOCATION_BUDGET_MISSING = "unified_invocation_budget_missing"
UNIFIED_INVOCATION_BUDGET_EXCEEDED = "unified_invocation_budget_exceeded"
UNIFIED_UNPLANNED_ACTUAL_REQUEST = "unified_unplanned_actual_request"
UNIFIED_ACTUAL_PAGE_BYTES_MISMATCH = "unified_actual_page_bytes_mismatch"
UNIFIED_CONSUMER_RECEIPT_MISSING = "unified_consumer_receipt_missing"
UNIFIED_CONSUMER_TASK_INCOMPLETE = "unified_consumer_task_incomplete"
UNIFIED_RESUME_DIGEST_MISMATCH = "unified_resume_digest_mismatch"

ARCHIVE_SCHEMA_VERSION = "2.0"
WORKSET_SCHEMA_VERSION = "2.0"
PLAN_SCHEMA_VERSION = "1.0"
ENVELOPE_SCHEMA_VERSION = "1.0"
ADMISSION_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_VERSION = "2.0"

INVOCATION_ROLE = Literal["formalizer", "writer", "realizer", "binder"]
INVOCATION_PHASE = Literal["formalizer", "writer", "realizer", "binder"]
PAGE_KIND = Literal["technical", "join", "header"]
TASK_KIND = Literal["formula", "section", "draft_realization", "binding"]
ADMISSION_STATUS = Literal["pass", "fail"]
GATE_STATUS = Literal["pass", "fail"]
DELIVERY_STATUS = Literal["accepted", "rejected"]
TASK_STATUS = Literal["complete", "partial", "failed"]


def _sorted_unique(values: Any) -> tuple[str, ...]:
    """Canonicalize a set-like ID tuple: sorted, de-duplicated, strings."""

    if values is None:
        return ()
    return tuple(sorted({str(value) for value in values if str(value).strip()}))


def _ordered_unique(values: Any) -> tuple[str, ...]:
    """Preserve compiler-proven order; require uniqueness."""

    if values is None:
        return ()
    items = tuple(str(value) for value in values)
    if len(items) != len(set(items)):
        raise ValueError("ordered ID tuple must not contain duplicates")
    return items


def compute_technical_page_id(
    *,
    archive_digest: str,
    technical_payload: Mapping[str, Any],
) -> tuple[str, bytes, str]:
    """Return ``(page_id, technical_bytes, technical_bytes_digest)``.

    The canonical page identity binds the page to its archive so identical
    text from two different archives can never reuse a page ID.
    """

    technical_bytes = canonical_json_bytes(dict(technical_payload))
    technical_bytes_digest = sha256_digest(technical_bytes)
    page_digest = hashlib.sha256(
        b"code2paper-consumer-page-v2\0"
        + str(archive_digest).encode("utf-8")
        + b"\0"
        + technical_bytes
    ).hexdigest()
    return f"page:{page_digest}", technical_bytes, technical_bytes_digest


def compute_request_envelope_digest(
    *,
    prompt_template_id: str,
    consumer_role: str,
    task_ids: Any,
    page_id: str,
    technical_bytes_digest: str,
    system_prompt_digest: str,
    rendered_prompt_digest: str,
    canonical_input_payload_digest: str,
    response_schema_digest: str,
) -> str:
    """Role-specific request envelope digest.

    This digest is per consumer role: Formalizer and Writer keep different
    envelope digests for the same shared technical page.  Cross-role identity
    is established only through ``page_id + technical_bytes_digest``.
    """

    payload = {
        "prompt_template_id": str(prompt_template_id),
        "consumer_role": str(consumer_role),
        "task_ids": _sorted_unique(task_ids),
        "page_id": str(page_id),
        "technical_bytes_digest": str(technical_bytes_digest),
        "system_prompt_digest": str(system_prompt_digest),
        "rendered_prompt_digest": str(rendered_prompt_digest),
        "canonical_input_payload_digest": str(canonical_input_payload_digest),
        "response_schema_digest": str(response_schema_digest),
    }
    return sha256_digest(canonical_json_bytes(payload))


# ---------------------------------------------------------------------------
# Archive atoms
# ---------------------------------------------------------------------------

ArchiveAtomKind = Literal[
    "mechanism",
    "detail",
    "operation",
    "edge",
    "equation",
    "evidence",
    "intent",
]

PayloadModelByAtomKind: dict[str, tuple[str, ...]] = {
    "mechanism": ("mechanism_id", "mechanism_name", "scientific_role"),
    "detail": ("detail_id", "primary_mechanism_id", "order_index"),
    "operation": ("operation_id", "predicate", "source_span_id"),
    "edge": ("edge_id", "mechanism_id", "source_detail_id", "target_detail_id"),
    "equation": ("equation_id",),
    # Evidence is a typed union in the existing research plane: facts and
    # claims have different primary IDs.  The old implementation required an
    # ``evidence_id`` key and consequently rejected every real CodeFact and
    # AtomicClaim payload.  Validation below accepts only the known frozen
    # models, never an arbitrary dict.
    "evidence": (),
    "intent": ("obligation_id",),
}

_EAGER_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "mechanism": MechanismContextV1,
    "detail": MechanismDetailV1,
    "operation": EvidenceOperationV1,
    "edge": MechanismEdgeV1,
}


def _payload_model_for(atom_kind: str) -> type[BaseModel] | None:
    if atom_kind in _EAGER_PAYLOAD_MODELS:
        return _EAGER_PAYLOAD_MODELS[atom_kind]
    if atom_kind == "equation":
        from code2paper.agentic.equation_claims import EquationClaimV1

        return EquationClaimV1
    if atom_kind == "evidence":
        # There is no single V2 evidence payload shape.  Callers use the
        # union helper below so this branch is kept only for introspection.
        return None
    if atom_kind == "intent":
        from code2paper.agentic.intent_compiler_v2 import IntentObligationV2

        return IntentObligationV2
    return None


def _payload_models_for(atom_kind: str) -> tuple[type[BaseModel], ...]:
    """Return the closed set of frozen payload models for one atom kind."""

    model = _payload_model_for(atom_kind)
    if model is not None:
        return (model,)
    if atom_kind == "evidence":
        from code2paper.agentic.evidence_compiler_v3 import (
            AtomicClaimV3,
            CodeFactV1,
            EvidencePacketV3,
            EvidenceSpanV3,
        )

        return (CodeFactV1, AtomicClaimV3, EvidencePacketV3, EvidenceSpanV3)
    return ()


def _evidence_authority_of(atom_kind: str, payload: Mapping[str, Any]) -> str:
    if atom_kind == "detail":
        return str(payload.get("evidence_authority") or "unresolved")
    if atom_kind == "operation":
        # Only executable first-party source is an implementation authority.
        # Configuration, documentation and test records remain useful
        # evidence but cannot silently become repository-verified operations.
        return (
            "repository_verified"
            if str(payload.get("source_kind", "")) == "first_party_executable"
            else "unresolved"
        )
    return "unresolved"


class ArchiveAtomV2(BaseModel):
    """One de-duplicated archive entity; stored once, referenced everywhere."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    atom_id: str
    atom_kind: ArchiveAtomKind
    primary_mechanism_id: str = ""
    source_span_ids: tuple[str, ...] = ()
    source_entry_paths: tuple[str, ...] = ()
    evidence_authority: Literal[
        "repository_verified",
        "repository_partial",
        "author_intent_only",
        "mismatch",
        "unresolved",
    ] = "unresolved"
    payload: Mapping[str, Any]
    content_digest: str = ""

    @property
    def is_core(self) -> bool:
        payload = self.payload
        importance = str(payload.get("importance", ""))
        return importance == "core"

    @model_validator(mode="after")
    def _validate_atom(self) -> "ArchiveAtomV2":
        if not self.atom_id.strip():
            raise ValueError("archive atom_id must be non-empty")
        if not isinstance(self.payload, Mapping):
            raise ValueError("archive atom payload must be a mapping")
        models = _payload_models_for(self.atom_kind)
        if not models:
            raise ValueError(f"unknown archive atom_kind: {self.atom_kind}")
        required_keys = PayloadModelByAtomKind[self.atom_kind]
        missing_keys = [key for key in required_keys if key not in self.payload]
        if missing_keys:
            raise ValueError(
                f"archive atom {self.atom_id} payload missing keys for kind "
                f"{self.atom_kind}: {missing_keys}"
            )
        payload_model_errors: list[str] = []
        for model in models:
            try:
                model.model_validate(dict(self.payload))
                break
            except Exception as exc:
                payload_model_errors.append(f"{model.__name__}: {exc}")
        else:
            raise ValueError(
                f"archive atom {self.atom_id} payload does not satisfy the "
                f"{self.atom_kind} contract: {'; '.join(payload_model_errors)}"
            )
        if self.atom_kind == "detail":
            declared = str(self.payload.get("evidence_authority") or "")
            if declared and declared != self.evidence_authority:
                raise ValueError(
                    f"archive atom {self.atom_id} evidence_authority disagrees with payload"
                )
            owner = str(self.payload.get("primary_mechanism_id") or "")
            if owner and owner != self.primary_mechanism_id:
                raise ValueError(
                    f"archive atom {self.atom_id} primary_mechanism_id disagrees with payload"
                )
        if self.atom_kind == "operation":
            expected_authority = _evidence_authority_of("operation", self.payload)
            if self.evidence_authority != expected_authority:
                raise ValueError(
                    f"archive operation atom {self.atom_id} evidence_authority "
                    "must be derived from its source_kind, not asserted"
                )
        object.__setattr__(
            self,
            "source_span_ids",
            _sorted_unique(self.source_span_ids),
        )
        object.__setattr__(
            self,
            "source_entry_paths",
            _sorted_unique(self.source_entry_paths),
        )
        payload = dict(self.model_dump(mode="json", exclude={"content_digest"}))
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"archive atom {self.atom_id} content_digest mismatch"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class SourceAuthorityPartitionProofV1(BaseModel):
    """Proof that one semantic detail was split by source authority atoms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    parent_detail_id: str
    partition_key: str
    child_atom_ids: tuple[str, ...] = ()
    included_span_ids: tuple[str, ...] = ()
    excluded_span_ids: tuple[str, ...] = ()
    decision: Literal["partitioned", "mixed_unresolved", "single_owner"]
    reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_proof(self) -> "SourceAuthorityPartitionProofV1":
        if not self.parent_detail_id.strip():
            raise ValueError("partition proof requires a parent detail ID")
        included = set(self.included_span_ids)
        excluded = set(self.excluded_span_ids)
        if included & excluded:
            raise ValueError(
                f"partition proof {self.parent_detail_id} includes and excludes "
                f"the same spans: {sorted(included & excluded)}"
            )
        object.__setattr__(self, "child_atom_ids", _sorted_unique(self.child_atom_ids))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("partition proof content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class MechanismMergeProofV1(BaseModel):
    """Machine-verifiable proof for one owner-scoped mechanism merge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    left_seed_id: str
    right_seed_id: str
    owner_anchor_id: str
    input_node_ids: tuple[str, ...] = ()
    output_node_ids: tuple[str, ...] = ()
    directed_path_relation_ids: tuple[str, ...] = ()
    decision: Literal["merged", "shared", "conflict"]
    reason: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_proof(self) -> "MechanismMergeProofV1":
        if self.decision == "merged":
            if not self.owner_anchor_id.strip():
                raise ValueError(
                    f"merge proof {self.left_seed_id}+{self.right_seed_id} "
                    "decision=merged requires an owner anchor"
                )
        object.__setattr__(
            self, "input_node_ids", _sorted_unique(self.input_node_ids)
        )
        object.__setattr__(
            self, "output_node_ids", _sorted_unique(self.output_node_ids)
        )
        object.__setattr__(
            self,
            "directed_path_relation_ids",
            _ordered_unique(self.directed_path_relation_ids),
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("mechanism merge proof content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class UnifiedContextArchiveV2(BaseModel):
    """Lossless, de-duplicated full-evidence archive (layer A)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ARCHIVE_SCHEMA_VERSION
    archive_id: str
    repo_snapshot_digest: str
    project_tree_hash: str
    source_manifest_digest: str
    authoring_digest: str
    research_digest: str
    context_set_digest: str

    mechanism_atoms: tuple[ArchiveAtomV2, ...] = ()
    detail_atoms: tuple[ArchiveAtomV2, ...] = ()
    operation_atoms: tuple[ArchiveAtomV2, ...] = ()
    edge_atoms: tuple[ArchiveAtomV2, ...] = ()
    equation_atoms: tuple[ArchiveAtomV2, ...] = ()
    evidence_atoms: tuple[ArchiveAtomV2, ...] = ()
    intent_atoms: tuple[ArchiveAtomV2, ...] = ()

    partition_proofs: tuple[SourceAuthorityPartitionProofV1, ...] = ()
    merge_proofs: tuple[MechanismMergeProofV1, ...] = ()

    # Reverse lookup is part of the archive contract rather than an
    # incidental compiler cache.  Keys are archive atom IDs and values retain
    # the source spans, manifest paths, and indexed symbols that explain the
    # atom.  All values are normalized as set-like tuples below.
    source_reverse_index: Mapping[str, Mapping[str, tuple[str, ...]]] = Field(
        default_factory=dict
    )

    compiler_version: str = "unified_context_compiler_v2"
    content_digest: str = ""

    def all_atoms(self) -> tuple[ArchiveAtomV2, ...]:
        return (
            self.mechanism_atoms + self.detail_atoms + self.operation_atoms
            + self.edge_atoms + self.equation_atoms + self.evidence_atoms
            + self.intent_atoms
        )

    def atom_by_id(self, atom_id: str) -> ArchiveAtomV2 | None:
        return self._atom_index().get(atom_id)

    def _atom_index(self) -> dict[str, ArchiveAtomV2]:
        cached = getattr(self, "_atom_index_cache", None)
        if cached is None:
            cached = {atom.atom_id: atom for atom in self.all_atoms()}
            object.__setattr__(self, "_atom_index_cache", cached)
        return cached

    @property
    def archive_digest(self) -> str:
        return self.content_digest

    @model_validator(mode="after")
    def _validate_archive(self) -> "UnifiedContextArchiveV2":
        for field_name in (
            "archive_id", "repo_snapshot_digest", "project_tree_hash",
            "source_manifest_digest", "authoring_digest", "research_digest",
            "context_set_digest",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"unified context archive requires {field_name}")
        all_atoms = self.all_atoms()
        atom_ids = [atom.atom_id for atom in all_atoms]
        if len(atom_ids) != len(set(atom_ids)):
            duplicates = sorted(
                {atom_id for atom_id in atom_ids if atom_ids.count(atom_id) > 1}
            )
            raise ValueError(f"archive atom IDs must be globally unique: {duplicates}")
        atom_index = {atom.atom_id: atom for atom in all_atoms}
        mechanism_ids = {
            str(atom.payload.get("mechanism_id") or atom.atom_id.removeprefix("mechanism:"))
            for atom in self.mechanism_atoms
        }
        for atom in self.mechanism_atoms:
            declared = str(atom.payload.get("mechanism_id") or "")
            if not declared or declared != atom.primary_mechanism_id:
                raise ValueError(
                    f"mechanism atom {atom.atom_id} must carry its canonical mechanism owner"
                )
        for atom in self.detail_atoms:
            owner = atom.primary_mechanism_id
            if owner and owner not in mechanism_ids:
                raise ValueError(
                    f"detail atom {atom.atom_id} names unknown primary mechanism {owner}"
                )
            if atom.is_core and not owner:
                raise ValueError(
                    f"core detail atom {atom.atom_id} must carry a primary owner"
                )
        for atom in self.operation_atoms + self.edge_atoms:
            owner = str(
                atom.primary_mechanism_id
                or atom.payload.get("mechanism_id")
                or ""
            )
            if owner and owner not in mechanism_ids:
                raise ValueError(
                    f"archive atom {atom.atom_id} names unknown mechanism owner {owner}"
                )
        # Shared secondary references may only point at a uniquely owned detail.
        for atom in self.detail_atoms:
            shared_with = _sorted_unique(
                atom.payload.get("shared_with_mechanism_ids", ())
            )
            if shared_with and not atom.primary_mechanism_id:
                raise ValueError(
                    f"detail atom {atom.atom_id} cannot be shared without a primary owner"
                )
        for atom in self.edge_atoms:
            mechanism_id = str(atom.payload.get("mechanism_id") or "")
            if mechanism_id and mechanism_id not in mechanism_ids:
                raise ValueError(
                    f"edge atom {atom.atom_id} names unknown mechanism {mechanism_id}"
                )
            for field_name in ("source_detail_id", "target_detail_id"):
                detail_id = str(atom.payload.get(field_name) or "")
                if detail_id:
                    detail_atom_id = (
                        detail_id if detail_id.startswith("detail:")
                        else f"detail:{detail_id}"
                    )
                    if detail_atom_id not in atom_index:
                        raise ValueError(
                            f"edge atom {atom.atom_id} references unknown detail {detail_id}"
                        )
        for proof in self.partition_proofs:
            parent_atom_id = (
                proof.parent_detail_id
                if proof.parent_detail_id.startswith("detail:")
                else f"detail:{proof.parent_detail_id}"
            )
            if parent_atom_id not in atom_index:
                raise ValueError(
                    f"partition proof references unknown parent detail {proof.parent_detail_id}"
                )
            unknown_children = set(proof.child_atom_ids) - set(atom_index)
            if unknown_children:
                raise ValueError(
                    f"partition proof references unknown child atoms {sorted(unknown_children)}"
                )
            parent_spans = set(atom_index[parent_atom_id].source_span_ids)
            included_spans = set(proof.included_span_ids)
            excluded_spans = set(proof.excluded_span_ids)
            if included_spans | excluded_spans != parent_spans:
                raise ValueError(
                    f"partition proof {proof.parent_detail_id} does not exactly cover "
                    "the parent source spans"
                )
            if proof.decision == "partitioned" and len(proof.child_atom_ids) < 2:
                raise ValueError(
                    f"partition proof {proof.parent_detail_id} marked partitioned "
                    "without at least two child atoms"
                )
        for proof in self.merge_proofs:
            if not proof.left_seed_id.strip() or not proof.right_seed_id.strip():
                raise ValueError("merge proofs require both seed IDs")
        reverse_index: dict[str, dict[str, tuple[str, ...]]] = {}
        for atom in all_atoms:
            payload = atom.payload
            symbol_ids = tuple(
                str(value)
                for value in (
                    payload.get("symbol_ids", ())
                    or payload.get("source_symbol_ids", ())
                    or ((payload.get("symbol_id"),) if payload.get("symbol_id") else ())
                )
                if str(value).strip()
            )
            reverse_index[atom.atom_id] = {
                "source_span_ids": _sorted_unique(atom.source_span_ids),
                "source_entry_paths": _sorted_unique(atom.source_entry_paths),
                "symbol_ids": _sorted_unique(symbol_ids),
            }
        supplied_reverse: dict[str, dict[str, tuple[str, ...]]] = {}
        for atom_id, value in self.source_reverse_index.items():
            if not isinstance(value, Mapping):
                raise ValueError(
                    f"archive source_reverse_index[{atom_id}] must be a mapping"
                )
            if set(value) != {"source_span_ids", "source_entry_paths", "symbol_ids"}:
                raise ValueError(
                    f"archive source_reverse_index[{atom_id}] has an invalid field set"
                )
            normalized_value: dict[str, tuple[str, ...]] = {}
            for field in ("source_span_ids", "source_entry_paths", "symbol_ids"):
                values = value[field]
                if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple, set)):
                    raise ValueError(
                        f"archive source_reverse_index[{atom_id}][{field}] must be a sequence"
                    )
                normalized_value[field] = _sorted_unique(values)
            supplied_reverse[str(atom_id)] = normalized_value
        if supplied_reverse and supplied_reverse != reverse_index:
            raise ValueError("unified context archive source_reverse_index mismatch")
        object.__setattr__(self, "source_reverse_index", reverse_index)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("unified context archive content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


# ---------------------------------------------------------------------------
# Consumer worksets and technical pages (layer B)
# ---------------------------------------------------------------------------


class ConsumerTechnicalPageV2(BaseModel):
    """One self-contained technical page; exactly one invocation consumes it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_id: str
    page_kind: PAGE_KIND
    archive_digest: str
    mechanism_id: str
    atom_ids: tuple[str, ...] = ()
    technical_payload: Mapping[str, Any]
    technical_bytes_digest: str
    token_estimate: int = Field(ge=0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_page(self) -> "ConsumerTechnicalPageV2":
        if not self.archive_digest.strip() or not self.mechanism_id.strip():
            raise ValueError(
                f"consumer page {self.page_id} requires archive and mechanism identities"
            )
        expected_page_id, _technical_bytes, expected_bytes_digest = (
            compute_technical_page_id(
                archive_digest=self.archive_digest,
                technical_payload=dict(self.technical_payload),
            )
        )
        if self.page_id != expected_page_id:
            raise ValueError(
                f"consumer page page_id mismatch: got {self.page_id}, expected {expected_page_id}"
            )
        if self.technical_bytes_digest != expected_bytes_digest:
            raise ValueError(
                f"consumer page {self.page_id} technical_bytes_digest mismatch"
            )
        expected_tokens = conservative_token_estimate(dict(self.technical_payload))
        if self.token_estimate != expected_tokens:
            raise ValueError(
                f"consumer page {self.page_id} token_estimate mismatch"
            )
        if str(self.technical_payload.get("archive_digest", "")) != self.archive_digest:
            raise ValueError(
                f"consumer page {self.page_id} technical_payload must embed archive_digest"
            )
        raw_atoms = self.technical_payload.get("atoms", ())
        if not isinstance(raw_atoms, (list, tuple)):
            raise ValueError(f"consumer page {self.page_id} atoms must be a sequence")
        if self.page_kind in {"technical", "join"} and not self.atom_ids:
            raise ValueError(f"consumer page {self.page_id} must carry atom IDs")
        if any(not isinstance(item, Mapping) for item in raw_atoms):
            raise ValueError(
                f"consumer page {self.page_id} atoms must contain mappings only"
            )
        payload_atom_ids = tuple(str(item.get("_atom_id", "")) for item in raw_atoms)
        if any(not atom_id.strip() for atom_id in payload_atom_ids):
            raise ValueError(
                f"consumer page {self.page_id} contains an atom without _atom_id"
            )
        if len(payload_atom_ids) != len(set(payload_atom_ids)):
            raise ValueError(f"consumer page {self.page_id} contains duplicate atoms")
        if set(payload_atom_ids) != set(self.atom_ids):
            raise ValueError(
                f"consumer page {self.page_id} atom_ids disagree with technical payload"
            )
        projection_proof = self.technical_payload.get("projection_proof", {})
        if self.page_kind in {"technical", "join"}:
            if not isinstance(projection_proof, Mapping):
                raise ValueError(
                    f"consumer page {self.page_id} projection_proof must be a mapping"
                )
            normalized_proof = {
                str(key): str(value) for key, value in projection_proof.items()
            }
            if normalized_proof != {
                atom_id: atom_id for atom_id in self.atom_ids
            }:
                raise ValueError(
                    f"consumer page {self.page_id} projection proof is not exact"
                )
        object.__setattr__(self, "atom_ids", _sorted_unique(self.atom_ids))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(f"consumer page {self.page_id} content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class ConsumerWorksetV2(BaseModel):
    """Minimal closure of pages/atoms one consumer task requires."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workset_id: str
    task_kind: TASK_KIND
    task_ids: tuple[str, ...] = ()
    mechanism_id: str = ""
    section_id: str = ""
    required_atom_ids: tuple[str, ...] = ()
    required_page_ids: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_workset(self) -> "ConsumerWorksetV2":
        if not self.workset_id.strip():
            raise ValueError("workset_id must be non-empty")
        if self.task_kind in {"formula", "section", "draft_realization", "binding"} and not self.task_ids:
            raise ValueError(f"workset {self.workset_id} must declare task IDs")
        object.__setattr__(self, "task_ids", _sorted_unique(self.task_ids))
        object.__setattr__(
            self, "required_atom_ids", _sorted_unique(self.required_atom_ids)
        )
        object.__setattr__(
            self, "required_page_ids", _ordered_unique(self.required_page_ids)
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(f"workset {self.workset_id} content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class ConsumerWorksetManifestV2(BaseModel):
    """Deterministic projection of the archive into consumer worksets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = WORKSET_SCHEMA_VERSION
    archive_digest: str
    source_manifest_digest: str
    pages: tuple[ConsumerTechnicalPageV2, ...] = ()
    worksets: tuple[ConsumerWorksetV2, ...] = ()
    projection_diagnostics: tuple[Mapping[str, Any], ...] = ()
    content_digest: str = ""

    def page_by_id(self, page_id: str) -> ConsumerTechnicalPageV2 | None:
        return self._page_index().get(page_id)

    def _page_index(self) -> dict[str, ConsumerTechnicalPageV2]:
        cached = getattr(self, "_page_index_cache", None)
        if cached is None:
            cached = {page.page_id: page for page in self.pages}
            object.__setattr__(self, "_page_index_cache", cached)
        return cached

    @property
    def total_token_estimate(self) -> int:
        return sum(page.token_estimate for page in self.pages)

    @property
    def unique_page_ids(self) -> tuple[str, ...]:
        return tuple(sorted({page.page_id for page in self.pages}))

    @model_validator(mode="after")
    def _validate_manifest(self) -> "ConsumerWorksetManifestV2":
        if not self.archive_digest.strip() or not self.source_manifest_digest.strip():
            raise ValueError(
                "consumer workset manifest requires archive and source manifest digests"
            )
        page_ids = [page.page_id for page in self.pages]
        if len(page_ids) != len(set(page_ids)):
            duplicates = sorted({p for p in page_ids if page_ids.count(p) > 1})
            raise ValueError(f"workset manifest page IDs must be unique: {duplicates}")
        page_index = {page.page_id: page for page in self.pages}
        workset_ids = [workset.workset_id for workset in self.worksets]
        if len(workset_ids) != len(set(workset_ids)):
            raise ValueError(
                f"workset manifest workset IDs must be unique: {sorted({item for item in workset_ids if workset_ids.count(item) > 1})}"
            )
        for page in self.pages:
            if page.archive_digest != self.archive_digest:
                raise ValueError(
                    f"page {page.page_id} archive_digest disagrees with manifest"
                )
            if any(not atom_id.strip() for atom_id in page.atom_ids):
                raise ValueError(f"page {page.page_id} contains an empty atom ID")
        for workset in self.worksets:
            required_atoms = set(workset.required_atom_ids)
            if not required_atoms and workset.task_ids:
                raise ValueError(
                    f"workset {workset.workset_id} has tasks but no required atoms"
                )
            covered: set[str] = set()
            for page_id in workset.required_page_ids:
                page = page_index.get(page_id)
                if page is None:
                    raise ValueError(
                        f"workset {workset.workset_id} references unknown page {page_id}"
                    )
                covered.update(page.atom_ids)
            missing = required_atoms - covered
            extra = covered - required_atoms
            if missing or extra:
                raise ValueError(
                    f"workset {workset.workset_id} page union is not exact: "
                    f"missing={sorted(missing)} extra={sorted(extra)}"
                )
            extra_atoms_by_page: dict[str, set[str]] = {}
            # Overreach: atoms covered but not required are allowed only when
            # the pages are shared with other tasks; a workset must never
            # reference a page purely to read unrelated atoms.  We therefore
            # require every referenced page to contribute at least one
            # required atom or be an explicit join page.
            for page_id in workset.required_page_ids:
                page = page_index[page_id]
                contribution = set(page.atom_ids) & required_atoms
                if (
                    not contribution
                    and page.page_kind != "join"
                ):
                    extra_atoms_by_page[page_id] = set(page.atom_ids) - required_atoms
            if extra_atoms_by_page:
                raise ValueError(
                    f"workset {workset.workset_id} references pages with no required "
                    f"atom contribution: {sorted(extra_atoms_by_page)}"
                )
            if set(workset.required_page_ids) - set(page_index):
                raise ValueError(
                    f"workset {workset.workset_id} references pages outside the manifest"
                )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("consumer workset manifest content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


# ---------------------------------------------------------------------------
# Invocation envelope and plan (layer C)
# ---------------------------------------------------------------------------


UNIFIED_TOKEN_METER_VERSION = "unified-token-meter-v1"
UNIFIED_REQUEST_ACCOUNTING_VERSION = "unified-request-token-accounting-v1"


class UnifiedTokenMeterV1(BaseModel):
    """Versioned token measurement contract shared by plan and send time.

    ``conservative_utf8_bytes_div_4`` is an explicit, declared estimate: its
    unit is tokens only as a conservative upper-bound proxy for canonical JSON
    bytes, and it never claims that a byte count *is* a tokenizer count.  A
    real tokenizer is usable only when its identity is recorded.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    meter_version: str = UNIFIED_TOKEN_METER_VERSION
    method: Literal["model_tokenizer", "conservative_utf8_bytes_div_4"]
    tokenizer_identity: str = ""
    unit: Literal["tokens"] = "tokens"
    measurement_basis: str = ""
    bytes_per_token: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_meter(self) -> "UnifiedTokenMeterV1":
        if self.method == "model_tokenizer":
            if not self.tokenizer_identity.strip():
                raise ValueError(
                    "a model_tokenizer meter must record the tokenizer identity"
                )
            if self.bytes_per_token:
                raise ValueError(
                    "a model_tokenizer meter must not declare bytes_per_token"
                )
        else:
            if self.bytes_per_token <= 0:
                raise ValueError(
                    "a conservative meter must declare a positive bytes_per_token"
                )
            if not self.measurement_basis.strip():
                raise ValueError(
                    "a conservative meter must declare its measurement basis"
                )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("token meter content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def conservative_token_meter() -> UnifiedTokenMeterV1:
    """Return the only meter production may use without a real tokenizer."""

    return UnifiedTokenMeterV1(
        method="conservative_utf8_bytes_div_4",
        measurement_basis="canonical_json_utf8_bytes_ceil_div_4",
        bytes_per_token=4,
    )


def model_tokenizer_meter(tokenizer_identity: str) -> UnifiedTokenMeterV1:
    return UnifiedTokenMeterV1(
        method="model_tokenizer",
        tokenizer_identity=str(tokenizer_identity),
        measurement_basis="tokenizer_encode",
    )


def model_chat_template_tokenizer_meter(tokenizer_identity: str) -> UnifiedTokenMeterV1:
    """Declare a model tokenizer that counts the actual OpenAI chat sequence."""

    return UnifiedTokenMeterV1(
        method="model_tokenizer",
        tokenizer_identity=str(tokenizer_identity),
        measurement_basis="openai_chat_template_v1",
    )


class RoleRequestBudgetV1(BaseModel):
    """Declared per-request budget for one consumer role.

    Every field comes from the frozen profile contract.  There is no global
    code default: an undeclared role budget is a hard planning failure.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    prompt_token_reserve: int = Field(ge=0)
    output_token_reserve: int = Field(gt=0)
    thinking_token_reserve: int = Field(ge=0)
    # R6/F4: a declared allowance for the role's own request scaffolding
    # (prompt envelope, metadata and payload wrappers the consumer adds around
    # the admitted page).  It makes the planned per-invocation input an upper
    # bound for the actual request instead of a different measurement.
    scaffolding_token_reserve: int = Field(ge=0, default=0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_role_budget(self) -> "RoleRequestBudgetV1":
        if not self.role.strip():
            raise ValueError("role request budget requires a role")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(f"role budget {self.role} content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class UnifiedRequestTokenAccountingV1(BaseModel):
    """One measurement of a planned or actually-built consumer request.

    Plan time and send time measure the same parts with the same meter:
    the rendered prompt, the structured payload, the closed response schema,
    and optionally the literal system prompt.  ``wrapper_reserve_tokens`` is
    the declared role reserve that covers the provider-side chat wrapper; it
    is a declared allowance, never a measured value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    accounting_version: str = UNIFIED_REQUEST_ACCOUNTING_VERSION
    consumer_role: str
    invocation_id: str = ""
    page_id: str = ""
    meter: UnifiedTokenMeterV1
    system_prompt_tokens: int = Field(ge=0)
    rendered_prompt_tokens: int = Field(ge=0)
    input_payload_tokens: int = Field(ge=0)
    response_schema_tokens: int = Field(ge=0)
    wrapper_reserve_tokens: int = Field(ge=0)
    scaffolding_reserve_tokens: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_reserve_tokens: int = Field(ge=0)
    thinking_reserve_tokens: int = Field(ge=0)
    safety_margin_tokens: int = Field(ge=0)
    model_context_tokens: int = Field(gt=0)
    max_input_tokens: int = Field(gt=0)
    fits: bool
    overflow_tokens: int = Field(ge=0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_accounting(self) -> "UnifiedRequestTokenAccountingV1":
        if not self.consumer_role.strip():
            raise ValueError("token accounting requires a consumer role")
        if (
            self.meter.method == "model_tokenizer"
            and self.meter.measurement_basis == "openai_chat_template_v1"
        ):
            expected_input = (
                self.rendered_prompt_tokens
                + self.response_schema_tokens
                + self.wrapper_reserve_tokens
                + self.scaffolding_reserve_tokens
            )
        else:
            expected_input = (
                self.system_prompt_tokens
                + self.rendered_prompt_tokens
                + self.input_payload_tokens
                + self.response_schema_tokens
                + self.wrapper_reserve_tokens
                + self.scaffolding_reserve_tokens
            )
        if self.input_tokens != expected_input:
            raise ValueError(
                f"token accounting input_tokens {self.input_tokens} does not match "
                f"the measured parts {expected_input}"
            )
        required_context = (
            self.input_tokens
            + self.output_reserve_tokens
            + self.thinking_reserve_tokens
            + self.safety_margin_tokens
        )
        expected_overflow = max(
            0,
            self.input_tokens - self.max_input_tokens,
            required_context - self.model_context_tokens,
        )
        if self.overflow_tokens != expected_overflow:
            raise ValueError(
                f"token accounting overflow_tokens {self.overflow_tokens} does not "
                f"match the measured overflow {expected_overflow}"
            )
        if self.fits != (expected_overflow == 0):
            raise ValueError("token accounting fits disagrees with its measurement")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("token accounting content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class RunInvocationBudgetEnvelopeV1(BaseModel):
    """Frozen whole-run budget envelope admitted before any model request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ENVELOPE_SCHEMA_VERSION
    envelope_id: str
    run_digest: str
    profile_digest: str
    model_identity_digest: str
    token_meter: UnifiedTokenMeterV1
    request_budget_by_role: Mapping[str, RoleRequestBudgetV1]
    max_request_input_tokens_by_role: Mapping[str, int]
    safety_margin_tokens: int = Field(ge=0)
    # The advertised context window the per-request contract was checked
    # against; recorded so send-time accounting cannot use a second window.
    model_context_tokens: int = Field(gt=0)
    max_calls_by_role: Mapping[str, int]
    max_input_tokens_by_role: Mapping[str, int]
    # Explicit headroom for bounded consumer retries.  This is part of the
    # frozen run contract: retry attempts debit the same role reservation as
    # primary attempts, but must not consume the reservation needed by later
    # primary invocations merely because they happen to run first.
    retry_reserve_input_tokens_by_role: Mapping[str, int] = Field(
        default_factory=dict
    )
    max_total_input_tokens: int = Field(gt=0)
    max_formula_repair_calls: int = Field(ge=0)
    max_page_input_tokens: int = Field(gt=0)
    max_obligations_per_page: int = Field(gt=0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_envelope(self) -> "RunInvocationBudgetEnvelopeV1":
        for role, value in self.max_calls_by_role.items():
            if int(value) < 0:
                raise ValueError(f"envelope max_calls_by_role[{role}] must be >= 0")
        for role, value in self.max_input_tokens_by_role.items():
            if int(value) < 0:
                raise ValueError(
                    f"envelope max_input_tokens_by_role[{role}] must be >= 0"
                )
        for role, value in self.retry_reserve_input_tokens_by_role.items():
            if int(value) < 0:
                raise ValueError(
                    f"envelope retry_reserve_input_tokens_by_role[{role}] "
                    "must be >= 0"
                )
        # R6: every planned role must declare a request budget and a per-request
        # input cap.  An undeclared role is unplannable, not unlimited.
        for role in self.max_calls_by_role:
            if role not in self.request_budget_by_role:
                raise ValueError(
                    f"envelope role {role} has no declared request budget"
                )
            if role not in self.max_request_input_tokens_by_role:
                raise ValueError(
                    f"envelope role {role} has no declared per-request input cap"
                )
        for role, budget in self.request_budget_by_role.items():
            if str(budget.role) != str(role):
                raise ValueError(
                    f"envelope request budget role mismatch: {budget.role} != {role}"
                )
        unknown_retry_roles = set(self.retry_reserve_input_tokens_by_role) - set(
            self.max_calls_by_role
        )
        if unknown_retry_roles:
            raise ValueError(
                "envelope retry reserve has undeclared roles: "
                + ",".join(sorted(str(role) for role in unknown_retry_roles))
            )
        for role, value in self.max_request_input_tokens_by_role.items():
            if int(value) <= 0:
                raise ValueError(
                    f"envelope max_request_input_tokens_by_role[{role}] must be positive"
                )
            if int(value) > self.max_total_input_tokens:
                raise ValueError(
                    f"envelope max_request_input_tokens_by_role[{role}] exceeds the "
                    "run-wide input reservation"
                )
            per_role_total = int(self.max_input_tokens_by_role.get(role, -1))
            if per_role_total >= 0 and int(value) > per_role_total:
                raise ValueError(
                    f"envelope max_request_input_tokens_by_role[{role}] exceeds the "
                    "role input reservation"
                )
        if self.max_formula_repair_calls < 0:
            raise ValueError("envelope max_formula_repair_calls must be >= 0")
        if self.max_obligations_per_page <= 0:
            raise ValueError("envelope max_obligations_per_page must be positive")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("run invocation budget envelope content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class ConsumerInvocationV1(BaseModel):
    """One planned actual model call: exactly one page, one consumer role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    role: INVOCATION_ROLE
    phase: INVOCATION_PHASE
    workset_id: str
    task_ids: tuple[str, ...] = ()
    mechanism_id: str
    section_id: str = ""
    page_id: str
    expected_technical_bytes_digest: str
    expected_request_envelope_digest: str
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    max_attempts: int = Field(gt=0)
    dependency_invocation_ids: tuple[str, ...] = ()
    is_repair: bool = False
    repair_obligation_id: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_invocation(self) -> "ConsumerInvocationV1":
        for field_name in (
            "invocation_id",
            "workset_id",
            "mechanism_id",
            "page_id",
            "expected_technical_bytes_digest",
            "expected_request_envelope_digest",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(
                    f"invocation {self.invocation_id or '<unknown>'} requires "
                    f"{field_name}"
                )
        if self.role != self.phase:
            raise ValueError(
                f"invocation {self.invocation_id} role and phase must match"
            )
        if not self.task_ids:
            raise ValueError(
                f"invocation {self.invocation_id} must carry a non-empty task closed set"
            )
        if self.is_repair and not self.repair_obligation_id.strip():
            raise ValueError(
                f"repair invocation {self.invocation_id} must name its repair obligation"
            )
        if not self.is_repair and self.repair_obligation_id:
            raise ValueError(
                f"non-repair invocation {self.invocation_id} cannot name a repair obligation"
            )
        if self.is_repair and tuple(self.task_ids) != (self.repair_obligation_id,):
            raise ValueError(
                f"repair invocation {self.invocation_id} must carry exactly its repair obligation"
            )
        object.__setattr__(self, "task_ids", _sorted_unique(self.task_ids))
        object.__setattr__(
            self,
            "dependency_invocation_ids",
            _sorted_unique(self.dependency_invocation_ids),
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(f"invocation {self.invocation_id} content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class ConsumerInvocationPlanV1(BaseModel):
    """Frozen, per-phase call plan; total calls counted from invocations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PLAN_SCHEMA_VERSION
    plan_revision: int = Field(ge=1)
    parent_plan_digest: str = ""
    phase: INVOCATION_PHASE
    archive_digest: str
    workset_manifest_digest: str
    envelope_digest: str
    profile_digest: str
    model_identity_digest: str
    invocations: tuple[ConsumerInvocationV1, ...] = ()
    formalizer_repair_call_limit: int = Field(ge=0)
    planned_calls_by_role: Mapping[str, int] = Field(default_factory=dict)
    planned_input_tokens_by_role: Mapping[str, int] = Field(default_factory=dict)
    reserved_calls_by_role: Mapping[str, int] = Field(default_factory=dict)
    reserved_input_tokens_by_role: Mapping[str, int] = Field(default_factory=dict)
    # R6/F4: how the run-level reservation is enforced.  ``atomic_debit_v1``
    # means every attempt (retries and resumed attempts included) is measured
    # before it is sent and debited from the same reservation.
    reservation_contract: str = "atomic_debit_v1"
    content_digest: str = ""

    def invocations_for_role(self, role: str) -> tuple[ConsumerInvocationV1, ...]:
        return tuple(item for item in self.invocations if item.role == role)

    @model_validator(mode="after")
    def _validate_plan(self) -> "ConsumerInvocationPlanV1":
        if self.plan_revision > 1 and not self.parent_plan_digest:
            raise ValueError(
                "plan revision > 1 must reference its parent plan digest"
            )
        invocation_ids = [item.invocation_id for item in self.invocations]
        if len(invocation_ids) != len(set(invocation_ids)):
            raise ValueError("plan invocation IDs must be unique")
        invocation_index = {item.invocation_id: item for item in self.invocations}
        for invocation in self.invocations:
            if invocation.phase != self.phase:
                raise ValueError(
                    f"invocation {invocation.invocation_id} phase disagrees with plan phase"
                )
            for dependency in invocation.dependency_invocation_ids:
                if dependency not in invocation_index:
                    raise ValueError(
                        f"invocation {invocation.invocation_id} depends on unknown "
                        f"invocation {dependency}"
                    )
        # DAG check.
        visiting: set[str] = set()
        visited: set[str] = set()

        def _visit(invocation_id: str) -> None:
            if invocation_id in visited:
                return
            if invocation_id in visiting:
                raise ValueError("plan invocations must form a DAG, not a cycle")
            visiting.add(invocation_id)
            for dependency in invocation_index[invocation_id].dependency_invocation_ids:
                _visit(dependency)
            visiting.discard(invocation_id)
            visited.add(invocation_id)

        for invocation_id in invocation_ids:
            _visit(invocation_id)
        planned_calls: dict[str, int] = {}
        planned_tokens: dict[str, int] = {}
        for invocation in self.invocations:
            planned_calls[invocation.role] = planned_calls.get(invocation.role, 0) + 1
            planned_tokens[invocation.role] = (
                planned_tokens.get(invocation.role, 0) + invocation.max_input_tokens
            )
        for role, count in self.planned_calls_by_role.items():
            if planned_calls.get(role, 0) != int(count):
                raise ValueError(
                    f"plan planned_calls_by_role[{role}]={count} disagrees with "
                    f"invocation count {planned_calls.get(role, 0)}"
                )
        for role, tokens in self.planned_input_tokens_by_role.items():
            if planned_tokens.get(role, 0) != int(tokens):
                raise ValueError(
                    f"plan planned_input_tokens_by_role[{role}] disagrees with invocations"
                )
        for name, values in (
            ("reserved_calls_by_role", self.reserved_calls_by_role),
            ("reserved_input_tokens_by_role", self.reserved_input_tokens_by_role),
        ):
            if any(int(value) < 0 for value in values.values()):
                raise ValueError(f"plan {name} values must be non-negative")
        for role, count in self.planned_calls_by_role.items():
            if int(self.reserved_calls_by_role.get(role, count)) < int(count):
                raise ValueError(
                    f"plan reserved calls for {role} cannot be below current allocation"
                )
        for role, tokens in self.planned_input_tokens_by_role.items():
            if int(self.reserved_input_tokens_by_role.get(role, tokens)) < int(tokens):
                raise ValueError(
                    f"plan reserved input tokens for {role} cannot be below current allocation"
                )
        object.__setattr__(self, "planned_calls_by_role", planned_calls)
        object.__setattr__(self, "planned_input_tokens_by_role", planned_tokens)
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("consumer invocation plan content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------


class UnifiedAdmissionGateV1(BaseModel):
    """One structural admission gate outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: str
    status: GATE_STATUS
    failure_codes: tuple[str, ...] = ()
    evidence_artifact: str = ""
    evidence_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_gate(self) -> "UnifiedAdmissionGateV1":
        if self.status == "pass" and self.failure_codes:
            raise ValueError(
                f"admission gate {self.gate_id} passed but carries failure codes"
            )
        if self.status == "fail" and not self.failure_codes:
            raise ValueError(
                f"admission gate {self.gate_id} failed without failure codes"
            )
        object.__setattr__(self, "failure_codes", _sorted_unique(self.failure_codes))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(f"admission gate {self.gate_id} content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class UnifiedLiveAdmissionV1(BaseModel):
    """Persisted admission decision made before the first model request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = ADMISSION_SCHEMA_VERSION
    admission_id: str
    phase: INVOCATION_PHASE
    plan_revision: int = Field(ge=1)
    run_digest: str
    archive_digest: str
    workset_manifest_digest: str
    envelope_digest: str
    plan_digest: str
    gates: tuple[UnifiedAdmissionGateV1, ...] = ()
    phase_planned_calls_by_role: Mapping[str, int] = Field(default_factory=dict)
    phase_planned_input_tokens_by_role: Mapping[str, int] = Field(default_factory=dict)
    run_reserved_calls_by_role: Mapping[str, int] = Field(default_factory=dict)
    run_reserved_input_tokens_by_role: Mapping[str, int] = Field(default_factory=dict)
    status: ADMISSION_STATUS = "fail"
    failure_codes: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_admission(self) -> "UnifiedLiveAdmissionV1":
        derived_failures: list[str] = []
        for gate in self.gates:
            if gate.status == "fail":
                derived_failures.extend(gate.failure_codes)
        if derived_failures:
            if self.status != "fail":
                raise ValueError(
                    "unified live admission with failing gates cannot report pass"
                )
        else:
            if self.failure_codes:
                raise ValueError(
                    "unified live admission reports failure codes without failing gates"
                )
        if self.status == "fail" and not (derived_failures or self.failure_codes):
            raise ValueError("failed unified live admission must carry failure codes")
        if self.status == "pass" and (derived_failures or self.failure_codes):
            raise ValueError("passed unified live admission cannot carry failure codes")
        object.__setattr__(
            self, "failure_codes", _sorted_unique(list(self.failure_codes) + derived_failures)
        )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("unified live admission content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


# ---------------------------------------------------------------------------
# Invocation ledger events
# ---------------------------------------------------------------------------


class InvocationAttemptStartedV1(BaseModel):
    """Durable start marker for one attempt of one invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    invocation_id: str
    attempt: int = Field(ge=1)
    plan_digest: str
    page_id: str
    expected_technical_bytes_digest: str
    expected_request_envelope_digest: str
    model_identity_digest: str
    started_at_unix: float = Field(ge=0)
    # A Writer/Realizer content retry reuses the primary invocation id but is
    # a separate provider debit.  Persist the classification in the start
    # marker as well as the completed receipt so a crash between the provider
    # call and receipt publication cannot turn a retry into primary capacity.
    content_repair_attempt: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_started(self) -> "InvocationAttemptStartedV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            # Markers written before this field existed remain valid only in
            # the non-repair case.  Accept their exact legacy digest shape;
            # every new marker is normalized to the current digest schema.
            legacy_payload = dict(payload)
            if not self.content_repair_attempt:
                legacy_payload.pop("content_repair_attempt", None)
            legacy_expected = sha256_digest(canonical_json_bytes(legacy_payload))
            if self.content_digest != legacy_expected:
                raise ValueError(
                    f"invocation attempt started {self.invocation_id} content_digest mismatch"
                )
            expected = self.content_digest
        object.__setattr__(self, "content_digest", expected)
        return self


class ActualRequestReceiptV2(BaseModel):
    """Receipt for one real request/response crossing the caller boundary.

    There is no self-reportable ``accepted`` flag: ``delivery_accepted`` is
    derived by the ledger from the actual digests, and ``task_complete`` is
    derived from the closed task set.  A delivery may succeed while its tasks
    stay partial or failed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    invocation_id: str
    attempt: int = Field(ge=1)
    consumer_role: INVOCATION_ROLE
    phase: INVOCATION_PHASE
    workset_id: str
    task_ids: tuple[str, ...] = ()
    mechanism_id: str
    section_id: str = ""
    page_id: str
    actual_technical_bytes_digest: str
    actual_request_envelope_digest: str
    response_digest: str = ""
    fragment_digests: tuple[str, ...] = ()
    model_identity_digest: str
    started_at_unix: float = Field(ge=0)
    finished_at_unix: float = Field(ge=0)
    delivery_status: DELIVERY_STATUS
    delivery_rejection_code: str = ""
    task_status: TASK_STATUS
    succeeded_task_ids: tuple[str, ...] = ()
    failed_task_ids: tuple[str, ...] = ()
    task_failures: tuple[Mapping[str, Any], ...] = ()
    is_repair: bool = False
    # A bounded consumer content retry belongs to the same planned immutable
    # page invocation.  It is still a real request and must be metered and
    # persisted, but it must not be mistaken for a second page delivery when
    # resume or page-integrity gates count accepted deliveries.
    content_repair_attempt: bool = False
    upstream_archive_digest: str = ""
    upstream_workset_manifest_digest: str = ""
    upstream_plan_digest: str = ""
    # R6: the actual request measurement is recorded beside the digests; a
    # rejected request keeps its measurement so the rejection is auditable.
    token_accounting: UnifiedRequestTokenAccountingV1 | None = None
    # A request can be rejected after measurement but before transport.  Keep
    # that distinction explicit so its auditable measurement is not charged as
    # provider spend when the whole-run ledger is recomputed.
    sent_to_caller: bool = True
    # Provider settlement is independent from the pre-send estimate. Unknown
    # usage retains the original reservation; it is never treated as free.
    provider_usage: dict[str, int] | None = None
    provider_diagnostics_digest: str = ""
    reserved_input_tokens: int = Field(default=0, ge=0)
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_receipt(self) -> "ActualRequestReceiptV2":
        for field_name in (
            "invocation_id",
            "workset_id",
            "mechanism_id",
            "page_id",
            "actual_technical_bytes_digest",
            "actual_request_envelope_digest",
            "model_identity_digest",
            "upstream_archive_digest",
            "upstream_workset_manifest_digest",
            "upstream_plan_digest",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(
                    f"receipt {self.invocation_id or '<unknown>'} requires {field_name}"
                )
        if self.consumer_role != self.phase:
            raise ValueError(
                f"receipt {self.invocation_id} consumer_role and phase must match"
            )
        if self.finished_at_unix < self.started_at_unix:
            raise ValueError(
                f"receipt {self.invocation_id} finished before it started"
            )
        if self.delivery_status == "rejected" and not self.delivery_rejection_code:
            raise ValueError(
                f"receipt {self.invocation_id} rejected without a rejection code"
            )
        if not self.sent_to_caller and self.delivery_status == "accepted":
            raise ValueError(
                f"receipt {self.invocation_id} accepted without crossing the caller boundary"
            )
        if self.delivery_status == "accepted":
            if not self.actual_technical_bytes_digest:
                raise ValueError(
                    f"receipt {self.invocation_id} accepted without page bytes digest"
                )
            if not self.actual_request_envelope_digest:
                raise ValueError(
                    f"receipt {self.invocation_id} accepted without request envelope digest"
                )
            if not self.response_digest:
                raise ValueError(
                    f"receipt {self.invocation_id} accepted without response digest"
                )
        if self.task_status == "failed" and not self.failed_task_ids:
            raise ValueError(
                f"receipt {self.invocation_id} task_status=failed without failed tasks"
            )
        if self.task_status == "complete" and self.failed_task_ids:
            raise ValueError(
                f"receipt {self.invocation_id} task_status=complete with failed tasks"
            )
        if self.task_status == "complete" and set(self.succeeded_task_ids) != set(
            self.task_ids
        ):
            raise ValueError(
                f"receipt {self.invocation_id} task_status=complete must cover the "
                "declared task closed set"
            )
        if set(self.succeeded_task_ids) & set(self.failed_task_ids):
            raise ValueError(
                f"receipt {self.invocation_id} succeeded and failed task IDs overlap"
            )
        unknown_succeeded = set(self.succeeded_task_ids) - set(self.task_ids)
        unknown_failed = set(self.failed_task_ids) - set(self.task_ids)
        if unknown_succeeded or unknown_failed:
            raise ValueError(
                f"receipt {self.invocation_id} reports tasks outside its closed set: "
                f"succeeded={sorted(unknown_succeeded)} failed={sorted(unknown_failed)}"
            )
        if self.task_status == "complete" and not self.task_ids:
            raise ValueError(
                f"receipt {self.invocation_id} task_status=complete without tasks"
            )
        object.__setattr__(self, "task_ids", _sorted_unique(self.task_ids))
        object.__setattr__(
            self, "succeeded_task_ids", _sorted_unique(self.succeeded_task_ids)
        )
        object.__setattr__(
            self, "failed_task_ids", _sorted_unique(self.failed_task_ids)
        )
        object.__setattr__(self, "fragment_digests", _ordered_unique(self.fragment_digests))
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            # ``content_repair_attempt`` was added after the first durable
            # Writer receipts were emitted.  Accept exactly the old digest
            # shape for a non-repair receipt, then normalize the in-memory
            # digest to the current schema before any new write.  All other
            # digest mismatches remain fail-closed.
            legacy_payload = dict(payload)
            optional_fields = ("provider_usage", "provider_diagnostics_digest", "reserved_input_tokens")
            defaults = self.provider_usage is None and not self.provider_diagnostics_digest and not self.reserved_input_tokens
            candidates = []
            if defaults:
                for key in optional_fields:
                    legacy_payload.pop(key, None)
                candidates.append(sha256_digest(canonical_json_bytes(legacy_payload)))
            if not self.content_repair_attempt:
                legacy_payload.pop("content_repair_attempt", None)
                candidates.append(sha256_digest(canonical_json_bytes(legacy_payload)))
            if self.content_digest not in candidates:
                raise ValueError(f"actual request receipt {self.invocation_id} content_digest mismatch")
            expected = self.content_digest
        if self.provider_usage is not None and any(value < 0 for value in self.provider_usage.values()):
            raise ValueError("provider usage must be nonnegative")
        object.__setattr__(self, "content_digest", expected)
        return self


class SectionWriterReceiptV2(BaseModel):
    """Section-level writer receipt: every required page really consumed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    section_id: str
    workset_id: str
    plan_digest: str
    required_invocation_ids: tuple[str, ...] = ()
    completed_invocation_ids: tuple[str, ...] = ()
    completed_receipt_digests: tuple[str, ...] = ()
    output_digest: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_section_receipt(self) -> "SectionWriterReceiptV2":
        object.__setattr__(
            self, "required_invocation_ids", _sorted_unique(self.required_invocation_ids)
        )
        object.__setattr__(
            self, "completed_invocation_ids", _sorted_unique(self.completed_invocation_ids)
        )
        if self.output_digest and set(self.completed_invocation_ids) != set(
            self.required_invocation_ids
        ):
            raise ValueError(
                f"section writer receipt {self.section_id} completed invocations do "
                "not exactly cover the required set"
            )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"section writer receipt {self.section_id} content_digest mismatch"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


class WriterAggregateReceiptV2(BaseModel):
    """Aggregate writer receipt over all planned sections."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    plan_digest: str
    required_section_ids: tuple[str, ...] = ()
    completed_section_ids: tuple[str, ...] = ()
    section_receipt_digests: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_aggregate(self) -> "WriterAggregateReceiptV2":
        object.__setattr__(
            self, "required_section_ids", _sorted_unique(self.required_section_ids)
        )
        object.__setattr__(
            self, "completed_section_ids", _sorted_unique(self.completed_section_ids)
        )
        if self.completed_section_ids and self.completed_section_ids != self.required_section_ids:
            raise ValueError(
                "writer aggregate receipt completed sections must exactly cover the "
                "required sections"
            )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("writer aggregate receipt content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


class BinderReceiptV2(BaseModel):
    """Receipt for the deterministic Binder pass over one Writer paragraph.

    Binder is a separate consumer role even though the current implementation
    performs the binding deterministically.  The receipt therefore records the
    Writer output it consumed, the closed target universe, and the exact
    witness keys it accepted.  It cannot be substituted by a Writer, Realizer,
    or Formalizer receipt.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECEIPT_SCHEMA_VERSION
    consumer_role: Literal["binder"] = "binder"
    phase: Literal["binder"] = "binder"
    section_id: str
    paragraph_id: str
    plan_digest: str
    archive_digest: str
    workset_manifest_digest: str
    writer_output_digest: str = ""
    allowed_target_keys: tuple[str, ...] = ()
    required_target_keys: tuple[str, ...] = ()
    witnessed_target_keys: tuple[str, ...] = ()
    missing_target_keys: tuple[str, ...] = ()
    witness_digest: str = ""
    lexical_producer: Literal["writer"] = "writer"
    status: Literal["complete", "partial", "failed"]
    failure_codes: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _validate_binder_receipt(self) -> "BinderReceiptV2":
        for field_name in (
            "section_id",
            "paragraph_id",
            "plan_digest",
            "archive_digest",
            "workset_manifest_digest",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise ValueError(f"binder receipt requires {field_name}")
        for field_name in (
            "allowed_target_keys",
            "required_target_keys",
            "witnessed_target_keys",
            "missing_target_keys",
        ):
            object.__setattr__(self, field_name, _sorted_unique(getattr(self, field_name)))
        allowed = set(self.allowed_target_keys)
        required = set(self.required_target_keys)
        witnessed = set(self.witnessed_target_keys)
        if not required.issubset(allowed):
            raise ValueError("binder required targets must be in the allowed target set")
        if not witnessed.issubset(allowed):
            raise ValueError("binder witnessed targets must be in the allowed target set")
        derived_missing = tuple(sorted(required - witnessed))
        if self.missing_target_keys and tuple(self.missing_target_keys) != derived_missing:
            raise ValueError("binder missing target keys disagree with required/witnessed sets")
        object.__setattr__(self, "missing_target_keys", derived_missing)
        object.__setattr__(self, "failure_codes", _sorted_unique(self.failure_codes))
        if self.status in {"complete", "partial"} and not self.writer_output_digest:
            raise ValueError(f"binder receipt {self.paragraph_id} lacks Writer output digest")
        if self.status in {"complete", "partial"} and not self.witness_digest:
            raise ValueError(f"binder receipt {self.paragraph_id} lacks witness digest")
        if self.status == "complete" and (self.missing_target_keys or self.failure_codes):
            raise ValueError("complete binder receipt cannot have missing targets or failures")
        if self.status == "failed" and not self.failure_codes and not self.missing_target_keys:
            raise ValueError("failed binder receipt must carry a failure or missing target")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = sha256_digest(canonical_json_bytes(payload))
        if self.content_digest and self.content_digest != expected:
            raise ValueError(
                f"binder receipt {self.paragraph_id} content_digest mismatch"
            )
        object.__setattr__(self, "content_digest", expected)
        return self


__all__ = [
    "UNIFIED_SOURCE_MANIFEST_MISSING",
    "UNIFIED_SOURCE_MANIFEST_INVALID",
    "UNIFIED_PROJECT_TREE_HASH_MISMATCH",
    "UNIFIED_SOURCE_SPAN_UNMAPPED",
    "UNIFIED_AUTHORING_CLOSED_SET_MISMATCH",
    "UNIFIED_CORE_INTENT_UNSEARCHED",
    "UNIFIED_CORE_INTENT_PARTIAL_WITHOUT_TERMINAL_GAP",
    "UNIFIED_MECHANISM_OWNER_MISSING",
    "UNIFIED_MECHANISM_OWNER_CONFLICT",
    "UNIFIED_MECHANISM_PATH_DISCONNECTED",
    "UNIFIED_PAGE_PROJECTION_INCOMPLETE",
    "UNIFIED_PAGE_PROJECTION_OVERREACH",
    "UNIFIED_ATOMIC_PAGE_OVER_BUDGET",
    "UNIFIED_INVOCATION_BUDGET_MISSING",
    "UNIFIED_INVOCATION_BUDGET_EXCEEDED",
    "UNIFIED_UNPLANNED_ACTUAL_REQUEST",
    "UNIFIED_ACTUAL_PAGE_BYTES_MISMATCH",
    "UNIFIED_CONSUMER_RECEIPT_MISSING",
    "UNIFIED_CONSUMER_TASK_INCOMPLETE",
    "UNIFIED_REQUEST_ACCOUNTING_VERSION",
    "UNIFIED_RESUME_DIGEST_MISMATCH",
    "UNIFIED_TOKEN_METER_VERSION",
    "RoleRequestBudgetV1",
    "UnifiedRequestTokenAccountingV1",
    "UnifiedTokenMeterV1",
    "conservative_token_meter",
    "model_tokenizer_meter",
    "model_chat_template_tokenizer_meter",
    "compute_technical_page_id",
    "compute_request_envelope_digest",
    "ArchiveAtomV2",
    "SourceAuthorityPartitionProofV1",
    "MechanismMergeProofV1",
    "UnifiedContextArchiveV2",
    "ConsumerTechnicalPageV2",
    "ConsumerWorksetV2",
    "ConsumerWorksetManifestV2",
    "RunInvocationBudgetEnvelopeV1",
    "ConsumerInvocationV1",
    "ConsumerInvocationPlanV1",
    "UnifiedAdmissionGateV1",
    "UnifiedLiveAdmissionV1",
    "InvocationAttemptStartedV1",
    "ActualRequestReceiptV2",
    "SectionWriterReceiptV2",
    "WriterAggregateReceiptV2",
    "BinderReceiptV2",
]
