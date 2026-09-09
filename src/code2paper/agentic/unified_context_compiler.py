"""Pure V2 compilers: archive, consumer worksets, invocation plans, admission.

Implements section 9.5 of
``docs/dyg_mamba_unified_live_run_failure_diagnosis_and_remediation_2026-09-08.md``.
Every function is deterministic and side-effect free; persistence belongs to
the run orchestration layer.

Key invariants enforced here:

- the archive stores every entity exactly once; pages only carry the minimal
  header and local atoms each invocation needs (no global author intent,
  unresolved lists, or core-ID lists copied page by page);
- a workset's required atom IDs must equal the union of its required pages'
  atom IDs exactly;
- planned calls are counted from the frozen invocation list, never from an
  obligation x page product;
- any allocation beyond the run budget envelope fails admission before the
  first model request.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel

from code2paper.agentic.mechanism_context_models import (
    MechanismContextSetV1,
    canonical_json_bytes,
    conservative_token_estimate,
    sha256_digest,
)
from code2paper.agentic.source_inventory import normalize_source_path
from code2paper.agentic.unified_context_models import (
    UNIFIED_INVOCATION_BUDGET_EXCEEDED,
    UNIFIED_INVOCATION_BUDGET_MISSING,
    UNIFIED_MECHANISM_OWNER_CONFLICT,
    UNIFIED_MECHANISM_OWNER_MISSING,
    UNIFIED_MECHANISM_PATH_DISCONNECTED,
    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
    UNIFIED_PAGE_PROJECTION_OVERREACH,
    UNIFIED_SOURCE_MANIFEST_MISSING,
    UNIFIED_SOURCE_MANIFEST_INVALID,
    UNIFIED_PROJECT_TREE_HASH_MISMATCH,
    UNIFIED_SOURCE_SPAN_UNMAPPED,
    UNIFIED_RESUME_DIGEST_MISMATCH,
    UNIFIED_UNPLANNED_ACTUAL_REQUEST,
    ADMISSION_STATUS,
    ArchiveAtomV2,
    ConsumerInvocationPlanV1,
    ConsumerInvocationV1,
    ConsumerTechnicalPageV2,
    ConsumerWorksetManifestV2,
    ConsumerWorksetV2,
    INVOCATION_PHASE,
    PAGE_KIND,
    RunInvocationBudgetEnvelopeV1,
    TASK_KIND,
    UnifiedAdmissionGateV1,
    UnifiedContextArchiveV2,
    UnifiedLiveAdmissionV1,
    compute_request_envelope_digest,
    compute_technical_page_id,
)

COMPILER_VERSION = "unified_context_compiler_v2"

BUDGET_FIELD_BY_ENV = {
    "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "max_page_input_tokens",
    "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "max_total_input_tokens",
    "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "max_formalizer_calls",
    "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "max_writer_calls",
    "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "max_realizer_calls",
    "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "max_obligations_per_page",
    "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "max_formula_repair_calls",
}


class UnifiedCompilerError(ValueError):
    """Typed compiler failure carrying a machine-readable failure code."""

    def __init__(self, failure_code: str, message: str) -> None:
        super().__init__(f"{failure_code}: {message}")
        self.failure_code = failure_code
        self.message = message


# ---------------------------------------------------------------------------
# Archive construction (layer A)
# ---------------------------------------------------------------------------


def _qualified_atom_id(kind: str, raw_id: Any) -> str:
    """Return one canonical namespace prefix for an archive entity ID.

    Frozen research artifacts already qualify some identifiers (most notably
    ``equation:*``), while mechanism-context identifiers such as ``d:*`` and
    ``op:*`` still need their archive namespace.  Applying ``f"{kind}:..."``
    unconditionally produced archive IDs such as
    ``equation:equation:fact-*`` that no formula obligation could reference.
    """

    value = str(raw_id or "").strip()
    if not value:
        return ""
    return value if value.startswith(f"{kind}:") else f"{kind}:{value}"


def _detail_atom_id(detail_id: str) -> str:
    return _qualified_atom_id("detail", detail_id)


#: Fields that identify one source operation.  Context-scoped evidence links
#: (``relation_ids``) and the payload digest legitimately differ between two
#: mechanisms that traverse the same operation, so they are excluded from the
#: archive's duplicate check; the mechanism atom keeps each closure's own list.
_OPERATION_IDENTITY_FIELDS: tuple[str, ...] = (
    "symbol_id",
    "predicate",
    "operands",
    "result",
    "guard",
    "source_span_id",
    "source_kind",
    "exact_excerpt",
    "shape_or_type_hints",
)


def _operation_identity(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: payload.get(field) for field in _OPERATION_IDENTITY_FIELDS
    }


def build_unified_context_archive_v2(
    context_set: MechanismContextSetV1,
    *,
    source_manifest_digest: str,
    source_manifest: Any | None = None,
    repo_snapshot_digest: str = "",
    equations: Any | None = None,
    claims: Any | None = None,
    facts: Any | None = None,
    intent_graph: Any | None = None,
    merge_proofs: Iterable[Any] = (),
    partition_proofs: Iterable[Any] = (),
) -> UnifiedContextArchiveV2:
    """Normalize a frozen V1 context set into the lossless V2 archive.

    Mechanism, detail, operation and typed-edge entities always come from the
    context set.  Equation, claim/evidence and intent atoms are materialized
    only when their concrete research artifacts are supplied; references kept
    by ID alone never fabricate archive authority.
    """

    if not source_manifest_digest:
        raise UnifiedCompilerError(
            UNIFIED_SOURCE_MANIFEST_MISSING,
            "archive compilation requires a non-empty source manifest digest",
        )
    if source_manifest is not None:
        manifest_digest = str(getattr(source_manifest, "content_digest", ""))
        if not manifest_digest:
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_MANIFEST_INVALID,
                "source manifest object has no content digest",
            )
        if manifest_digest != str(source_manifest_digest):
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_MANIFEST_INVALID,
                "source manifest object and declared digest disagree",
            )
        manifest_tree = str(getattr(source_manifest, "project_tree_hash", ""))
        if manifest_tree and manifest_tree != str(context_set.project_tree_hash):
            raise UnifiedCompilerError(
                UNIFIED_PROJECT_TREE_HASH_MISMATCH,
                "source manifest tree hash disagrees with the context set",
            )
    elif any(
        str(span_id).strip()
        for context in context_set.contexts
        for span_id in (
            tuple(getattr(context.evidence_closure, "exact_span_ids", ()) or ())
            + tuple(
                span_id
                for detail in (getattr(context, "details", ()) or ())
                for span_id in (getattr(detail, "source_span_ids", ()) or ())
            )
        )
    ):
        raise UnifiedCompilerError(
            UNIFIED_SOURCE_MANIFEST_MISSING,
            "source spans cannot enter the archive without the parsed source manifest",
        )

    def _source_entry_map() -> dict[str, Any]:
        return {
            normalize_source_path(str(getattr(entry, "path", ""))): entry
            for entry in (getattr(source_manifest, "entries", ()) or ())
        }

    source_entries = _source_entry_map()

    def _assert_source_authority(
        *,
        atom_label: str,
        payload: Mapping[str, Any],
        source_entry_paths: Sequence[str],
        claimed_authority: str,
    ) -> None:
        """Prevent source metadata from promoting a non-executable atom."""

        if claimed_authority not in {"repository_verified", "repository_partial"}:
            return
        source_kind = str(payload.get("source_kind", "") or "")
        if source_kind and source_kind != "first_party_executable":
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_MANIFEST_INVALID,
                f"{atom_label} claims repository authority for source kind {source_kind}",
            )
        if not source_entry_paths:
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_SPAN_UNMAPPED,
                f"{atom_label} claims repository authority without source entry paths",
            )
        entries = [source_entries.get(path) for path in source_entry_paths]
        if any(entry is None for entry in entries):
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_SPAN_UNMAPPED,
                f"{atom_label} references an unknown source entry",
            )
        if not all(
            str(getattr(entry, "source_kind", "")) == "first_party_executable"
            and bool(getattr(entry, "executable_authority", False))
            for entry in entries
        ):
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_MANIFEST_INVALID,
                f"{atom_label} source entries are not allowed executable authority",
            )

    def _authority_from_source_paths(source_entry_paths: Sequence[str]) -> str:
        """Derive authority from manifest entries, never from stale V1 labels."""

        if not source_entry_paths:
            return "unresolved"
        entries = [
            source_entries.get(normalize_source_path(path))
            for path in source_entry_paths
        ]
        if not entries or any(entry is None for entry in entries):
            return "unresolved"
        if all(
            str(getattr(entry, "source_kind", "")) == "first_party_executable"
            and bool(getattr(entry, "executable_authority", False))
            for entry in entries
        ):
            return "repository_verified"
        return "unresolved"

    mechanism_atoms_by_id: dict[str, ArchiveAtomV2] = {}
    detail_atoms_by_id: dict[str, ArchiveAtomV2] = {}
    operation_atoms_by_id: dict[str, ArchiveAtomV2] = {}
    edge_atoms_by_id: dict[str, ArchiveAtomV2] = {}
    equation_atoms: list[ArchiveAtomV2] = []
    evidence_atoms: list[ArchiveAtomV2] = []
    intent_atoms: list[ArchiveAtomV2] = []

    seen_detail_ids: set[str] = set()
    seen_operation_ids: set[str] = set()
    seen_edge_ids: set[str] = set()
    # Two mechanisms may legitimately traverse the same dependency operation
    # (for example two public entries that both call one submodule).  The
    # archive stores that operation once, under one canonical primary owner,
    # exactly like ``annotate_mechanism_paper_details`` does; the second
    # mechanism references the atom through its shared detail refs.  Picking
    # the canonical owner deterministically keeps the archive reproducible.
    canonical_owner_by_operation: dict[str, str] = {}
    for context in context_set.contexts:
        mechanism_id = str(context.mechanism_id)
        for operation in context.evidence_closure.operation_nodes:
            prior_owner = canonical_owner_by_operation.get(operation.operation_id)
            if prior_owner is None or mechanism_id < prior_owner:
                canonical_owner_by_operation[operation.operation_id] = mechanism_id

    for context in context_set.contexts:
        mechanism_atom = ArchiveAtomV2(
            atom_id=f"mechanism:{context.mechanism_id}",
            atom_kind="mechanism",
            primary_mechanism_id=str(context.mechanism_id),
            payload=dict(context.model_dump(mode="json")),
        )
        prior_mechanism = mechanism_atoms_by_id.get(mechanism_atom.atom_id)
        if prior_mechanism is not None and prior_mechanism.content_digest != mechanism_atom.content_digest:
            raise UnifiedCompilerError(
                UNIFIED_MECHANISM_OWNER_CONFLICT,
                f"duplicate mechanism atom has different payload: {mechanism_atom.atom_id}",
        )
        mechanism_atoms_by_id[mechanism_atom.atom_id] = mechanism_atom
        closure = context.evidence_closure
        operation_entry_paths_by_id = {
            str(operation.operation_id): _source_entry_paths_for_spans(
                (operation.source_span_id,) if operation.source_span_id else (),
                source_manifest,
            )
            for operation in closure.operation_nodes
        }
        for operation in closure.operation_nodes:
            atom_id = f"operation:{operation.operation_id}"
            operation_payload = dict(operation.model_dump(mode="json"))
            operation_entry_paths = operation_entry_paths_by_id.get(
                str(operation.operation_id), ()
            )
            if (
                str(operation_payload.get("source_kind", "")) == "unknown"
                and _authority_from_source_paths(operation_entry_paths)
                == "repository_verified"
            ):
                # Historical V1 operations did not carry source-kind labels.
                # Reclassify them from the authenticated manifest before the
                # operation authority is derived; no semantic text is added.
                operation_payload["source_kind"] = "first_party_executable"
                operation_payload.pop("content_digest", None)
            operation_authority = (
                "repository_verified"
                if str(operation_payload.get("source_kind", ""))
                == "first_party_executable"
                and _authority_from_source_paths(operation_entry_paths)
                == "repository_verified"
                else "unresolved"
            )
            _assert_source_authority(
                atom_label=atom_id,
                payload=operation_payload,
                source_entry_paths=operation_entry_paths,
                claimed_authority=operation_authority,
            )
            if operation.operation_id in seen_operation_ids:
                prior = operation_atoms_by_id.get(atom_id)
                if prior is not None and (
                    _operation_identity(dict(prior.payload))
                    != _operation_identity(operation_payload)
                    or prior.source_span_ids != (
                        (operation.source_span_id,) if operation.source_span_id else ()
                    )
                ):
                    raise UnifiedCompilerError(
                        UNIFIED_MECHANISM_OWNER_CONFLICT,
                        f"operation {operation.operation_id} has conflicting payloads",
                    )
                continue
            seen_operation_ids.add(operation.operation_id)
            operation_atoms_by_id[atom_id] = ArchiveAtomV2(
                atom_id=atom_id,
                atom_kind="operation",
                primary_mechanism_id=canonical_owner_by_operation.get(
                    operation.operation_id, str(context.mechanism_id)
                ),
                source_span_ids=(operation.source_span_id,) if operation.source_span_id else (),
                source_entry_paths=operation_entry_paths,
                evidence_authority=operation_authority,  # type: ignore[arg-type]
                payload=operation_payload,
            )
        for detail in context.details:
            atom_id = _detail_atom_id(detail.detail_id)
            if detail.detail_id in seen_detail_ids:
                # A detail shared across mechanism projections is stored once;
                # ownership conflicts are an owner-compiler failure, not an
                # archive duplication problem.
                prior = detail_atoms_by_id.get(atom_id)
                if prior is not None and (
                    prior.primary_mechanism_id != str(detail.primary_mechanism_id)
                    or dict(prior.payload) != dict(detail.model_dump(mode="json"))
                    or prior.source_span_ids != tuple(dict.fromkeys(detail.source_span_ids))
                ):
                    raise UnifiedCompilerError(
                        UNIFIED_MECHANISM_OWNER_CONFLICT,
                        f"detail {detail.detail_id} has conflicting owners",
                    )
                continue
            seen_detail_ids.add(detail.detail_id)
            span_ids = tuple(dict.fromkeys(detail.source_span_ids))
            detail_payload = dict(detail.model_dump(mode="json"))
            detail_entry_paths_set = set(
                _source_entry_paths_for_spans(span_ids, source_manifest)
            )
            for operation_id in detail.source_operation_ids:
                detail_entry_paths_set.update(
                    operation_entry_paths_by_id.get(str(operation_id), ())
                )
            detail_entry_paths = tuple(sorted(detail_entry_paths_set))
            claimed_detail_authority = str(
                detail_payload.get("evidence_authority") or "unresolved"
            )
            if (
                claimed_detail_authority in {"repository_verified", "repository_partial"}
                and str(detail_payload.get("source_kind", "")) == "unknown"
            ):
                manifest_authority = _authority_from_source_paths(detail_entry_paths)
                detail_payload.pop("content_digest", None)
                if manifest_authority == "repository_verified":
                    detail_payload["source_kind"] = "first_party_executable"
                else:
                    # A historical verified label without a manifest-proven
                    # source partition is retained for diagnostics only.
                    detail_payload["evidence_authority"] = "unresolved"
                    claimed_detail_authority = "unresolved"
            _assert_source_authority(
                atom_label=atom_id,
                payload=detail_payload,
                source_entry_paths=detail_entry_paths,
                claimed_authority=claimed_detail_authority,
            )
            detail_atoms_by_id[atom_id] = ArchiveAtomV2(
                atom_id=atom_id,
                atom_kind="detail",
                primary_mechanism_id=str(detail.primary_mechanism_id),
                source_span_ids=span_ids,
                source_entry_paths=detail_entry_paths,
                evidence_authority=claimed_detail_authority,  # type: ignore[arg-type]
                payload=detail_payload,
            )
        for edge in context.edges:
            if edge.edge_id in seen_edge_ids:
                prior = edge_atoms_by_id.get(f"edge:{edge.edge_id}")
                if prior is not None and prior.primary_mechanism_id != str(edge.mechanism_id):
                    raise UnifiedCompilerError(
                        UNIFIED_MECHANISM_OWNER_CONFLICT,
                        f"edge {edge.edge_id} has conflicting owners",
                    )
                continue
            seen_edge_ids.add(edge.edge_id)
            edge_atom_id = f"edge:{edge.edge_id}"
            edge_atoms_by_id[edge_atom_id] = ArchiveAtomV2(
                atom_id=edge_atom_id,
                atom_kind="edge",
                primary_mechanism_id=str(edge.mechanism_id),
                source_span_ids=tuple(dict.fromkeys(edge.source_span_ids)),
                source_entry_paths=_source_entry_paths_for_spans(
                    tuple(dict.fromkeys(edge.source_span_ids)), source_manifest
                ),
                payload=dict(edge.model_dump(mode="json")),
            )

    def _rows(collection: Any, id_field: str) -> list[tuple[str, dict[str, Any]]]:
        if collection is None:
            return []
        rows: list[tuple[str, dict[str, Any]]] = []
        items = collection
        if isinstance(items, BaseModel):
            dumped = items.model_dump(mode="json")
            for key in ("equations", "claims", "facts", "items", "obligations"):
                value = dumped.get(key)
                if isinstance(value, list):
                    items = value
                    break
        if isinstance(items, Mapping):
            if id_field in items:
                items = (items,)
            else:
                nested = items.get("items")
                if nested is None:
                    for key in ("equations", "claims", "facts", "obligations"):
                        value = items.get(key)
                        if isinstance(value, (list, tuple)):
                            nested = value
                            break
                items = nested or ()
        for row in items:
            if isinstance(row, BaseModel):
                payload = row.model_dump(mode="json")
            elif isinstance(row, Mapping):
                payload = dict(row)
            else:
                continue
            row_id = str(payload.get(id_field, ""))
            if row_id:
                rows.append((row_id, payload))
        return rows

    # Intent is an authoring authority, not repository evidence.  It is kept
    # in the archive exactly once so reverse validation can distinguish an
    # author request from an implementation fact.  The graph is optional for
    # legacy diagnostics, but when supplied every row must satisfy the frozen
    # IntentObligationV2 contract through ArchiveAtomV2 validation below.
    seen_intent_ids: set[str] = set()
    for obligation_id, payload in _rows(intent_graph, "obligation_id"):
        atom_id = f"intent:{obligation_id}"
        intent_atom = ArchiveAtomV2(
            atom_id=atom_id,
            atom_kind="intent",
            evidence_authority="author_intent_only",
            payload=payload,
        )
        prior = next(
            (item for item in intent_atoms if item.atom_id == atom_id),
            None,
        )
        if prior is not None and prior.content_digest != intent_atom.content_digest:
            raise UnifiedCompilerError(
                UNIFIED_MECHANISM_OWNER_CONFLICT,
                f"intent obligation has conflicting duplicate payloads: {obligation_id}",
            )
        if obligation_id in seen_intent_ids:
            continue
        seen_intent_ids.add(obligation_id)
        intent_atoms.append(intent_atom)

    seen_equation_ids: set[str] = set()
    for equation_id, payload in _rows(equations, "equation_id"):
        if equation_id in seen_equation_ids:
            continue
        seen_equation_ids.add(equation_id)
        equation_atoms.append(ArchiveAtomV2(
            atom_id=_qualified_atom_id("equation", equation_id),
            atom_kind="equation",
            payload=payload,
        ))

    seen_claim_ids: set[str] = set()
    for claim_id, payload in _rows(claims, "claim_id"):
        if claim_id in seen_claim_ids:
            continue
        seen_claim_ids.add(claim_id)
        evidence_atoms.append(ArchiveAtomV2(
            atom_id=f"evidence:claim:{claim_id}",
            atom_kind="evidence",
            source_span_ids=tuple(
                str(value) for value in (
                    payload.get("direct_evidence_ids", ())
                    or payload.get("span_ids", ())
                ) if str(value).strip()
            ),
            source_entry_paths=_source_entry_paths_for_spans(
                tuple(
                    str(value) for value in (
                        payload.get("direct_evidence_ids", ())
                        or payload.get("span_ids", ())
                    ) if str(value).strip()
                ),
                source_manifest,
            ),
            payload=payload,
        ))
    seen_fact_ids: set[str] = set()
    for fact_id, payload in _rows(facts, "fact_id"):
        if fact_id in seen_fact_ids:
            continue
        seen_fact_ids.add(fact_id)
        evidence_atoms.append(ArchiveAtomV2(
            atom_id=f"evidence:fact:{fact_id}",
            atom_kind="evidence",
            source_span_ids=tuple(
                str(value) for value in (
                    payload.get("direct_span_ids", ())
                    or payload.get("relation_span_ids", ())
                ) if str(value).strip()
            ),
            source_entry_paths=_source_entry_paths_for_spans(
                tuple(
                    str(value) for value in (
                        payload.get("direct_span_ids", ())
                        or payload.get("relation_span_ids", ())
                    ) if str(value).strip()
                ),
                source_manifest,
            ),
            payload=payload,
        ))

    resolved_merge_proofs = tuple(merge_proofs) or tuple(
        getattr(context_set, "merge_proofs", ()) or ()
    )
    return UnifiedContextArchiveV2(
        archive_id=_archive_id(context_set),
        repo_snapshot_digest=repo_snapshot_digest
        or sha256_digest(str(context_set.repo_snapshot_id).encode("utf-8")),
        project_tree_hash=str(context_set.project_tree_hash),
        source_manifest_digest=str(source_manifest_digest),
        authoring_digest=str(context_set.intent_digest),
        research_digest=str(context_set.research_digest),
        context_set_digest=str(context_set.content_digest),
        mechanism_atoms=tuple(mechanism_atoms_by_id[key] for key in sorted(mechanism_atoms_by_id)),
        detail_atoms=tuple(detail_atoms_by_id[key] for key in sorted(detail_atoms_by_id)),
        operation_atoms=tuple(operation_atoms_by_id[key] for key in sorted(operation_atoms_by_id)),
        edge_atoms=tuple(edge_atoms_by_id[key] for key in sorted(edge_atoms_by_id)),
        equation_atoms=tuple(equation_atoms),
        evidence_atoms=tuple(evidence_atoms),
        intent_atoms=tuple(intent_atoms),
        partition_proofs=tuple(partition_proofs),
        merge_proofs=resolved_merge_proofs,
        compiler_version=COMPILER_VERSION,
    )


def _archive_id(context_set: MechanismContextSetV1) -> str:
    digest = hashlib.sha256(
        b"code2paper-unified-context-archive-v2\0"
        + str(context_set.content_digest).encode("utf-8")
    ).hexdigest()
    return f"archive:{digest}"


def _source_entry_paths_for_spans(
    span_ids: Sequence[str],
    source_manifest: Any | None,
) -> tuple[str, ...]:
    """Resolve source span handles to manifest paths when a manifest is available.

    The archive compiler accepts a digest-only input for offline compatibility,
    but the production caller passes the parsed manifest.  In that case an
    unmapped span is a typed source failure instead of silently becoming an
    ``unknown`` authority atom.
    """

    if source_manifest is None:
        return ()
    paths: list[str] = []
    for span_id in span_ids:
        match = re.match(r"^span:(.*):(\d+):(\d+)$", str(span_id))
        if match is None:
            raise UnifiedCompilerError(
                UNIFIED_SOURCE_MANIFEST_MISSING,
                f"source span is not a resolvable span handle: {span_id}",
            )
        path = normalize_source_path(match.group(1))
        entry_for = getattr(source_manifest, "entry_for", None)
        entry = entry_for(path) if callable(entry_for) else None
        if entry is None:
            for candidate in getattr(source_manifest, "entries", ()) or ():
                candidate_path = normalize_source_path(str(getattr(candidate, "path", "")))
                if candidate_path == path:
                    entry = candidate
                    break
        if entry is None:
            raise UnifiedCompilerError(
                "unified_source_span_unmapped",
                f"source span {span_id} is absent from the repository source manifest",
            )
        paths.append(path)
    return tuple(sorted(set(paths)))


# ---------------------------------------------------------------------------
# Consumer workset manifest (layer B)
# ---------------------------------------------------------------------------


def _minimal_mechanism_header(context: Mapping[str, Any]) -> dict[str, Any]:
    """The only global header a technical page materializes.

    Everything else (full author intent, global unresolved lists, core-ID
    lists) stays in the archive and is never copied per page.
    """

    return {
        "mechanism_id": str(context.get("mechanism_id", "")),
        "mechanism_name": str(context.get("mechanism_name", "")),
        "scientific_role": str(context.get("scientific_role", "")),
        "purpose": str(context.get("purpose", "")),
        "importance": str(context.get("importance", "")),
    }


def _obligation_required_atom_ids(
    obligation: Any,
    archive: UnifiedContextArchiveV2,
) -> tuple[str, ...]:
    atom_index = archive._atom_index()  # noqa: SLF001 - same-package compiler
    required: list[str] = []

    def _atom_id(kind: str, raw_id: Any) -> str:
        value = str(raw_id or "").strip()
        if not value:
            return ""
        # Research artifacts use several already-qualified forms (for
        # example ``fact:1`` and ``evidence:fact:1``), while the archive uses
        # the canonical atom namespace.  Prefixing blindly would turn the
        # former into ``evidence:fact:fact:1`` and silently lose a formula
        # dependency.  Resolve exact IDs first, then only the closed aliases
        # for the declared reference kind.
        candidates: list[str] = [value]
        if kind == "evidence:fact":
            fact_id = value
            if fact_id.startswith("evidence:fact:"):
                fact_id = fact_id.removeprefix("evidence:fact:")
            elif fact_id.startswith("fact:"):
                fact_id = fact_id.removeprefix("fact:")
            candidates.extend((f"evidence:fact:{fact_id}", f"fact:{fact_id}"))
        elif kind == "evidence:claim":
            claim_id = value
            if claim_id.startswith("evidence:claim:"):
                claim_id = claim_id.removeprefix("evidence:claim:")
            elif claim_id.startswith("claim:"):
                claim_id = claim_id.removeprefix("claim:")
            candidates.extend((f"evidence:claim:{claim_id}", f"claim:{claim_id}"))
        else:
            candidates.append(_qualified_atom_id(kind, value))
        for candidate in dict.fromkeys(candidates):
            if candidate in atom_index:
                return candidate
        # Return the canonical spelling so the error names the namespace the
        # compiler expected, rather than exposing an implementation-specific
        # duplicate prefix.
        return next(
            candidate for candidate in dict.fromkeys(candidates)
            if candidate.startswith(kind + ":")
        )

    references = (
        ("source_detail_ids", "detail"),
        ("source_operation_ids", "operation"),
        ("source_equation_ids", "equation"),
        ("source_fact_ids", "evidence:fact"),
        ("source_claim_ids", "evidence:claim"),
    )
    for field_name, kind in references:
        for raw_id in getattr(obligation, field_name, ()) or ():
            value = str(raw_id or "").strip()
            if not value:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {getattr(obligation, 'obligation_id', '')} "
                    f"contains an empty {field_name} reference",
                )
            atom_id = _atom_id(kind, value)
            if atom_id not in atom_index:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {getattr(obligation, 'obligation_id', '')} "
                    f"references unknown archive atom {atom_id}",
                )
            required.append(atom_id)
    return tuple(dict.fromkeys(required))


def _pack_pages_by_detail_graph(
    *,
    archive: UnifiedContextArchiveV2,
    mechanism_context: Mapping[str, Any],
    obligation_atoms: Mapping[str, tuple[str, ...]],
    token_budget: int,
    max_obligations_per_page: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Deterministically group obligations into bounded technical pages.

    Grouping follows owner detail adjacency (typed mechanism edges), then
    splits by token budget and the profile's per-page obligation cap.  It
    never splits a single obligation's atoms across pages.
    """

    atom_index = archive._atom_index()  # noqa: SLF001 - same-package compiler
    detail_neighbors: dict[str, set[str]] = {}
    for edge in archive.edge_atoms:
        payload = edge.payload
        if str(payload.get("relation", "")).casefold() == "precedes":
            # Narrative ordering is not a technical adjacency proof and must
            # not influence the workset closure or page grouping.
            continue
        source = _detail_atom_id(str(payload.get("source_detail_id", "")))
        target = _detail_atom_id(str(payload.get("target_detail_id", "")))
        if source in atom_index and target in atom_index:
            detail_neighbors.setdefault(source, set()).add(target)
            detail_neighbors.setdefault(target, set()).add(source)

    obligation_ids = sorted(obligation_atoms)
    obligation_details: dict[str, set[str]] = {
        obligation_id: {
            atom_id
            for atom_id in obligation_atoms[obligation_id]
            if atom_id.startswith("detail:")
        }
        for obligation_id in obligation_ids
    }

    def _atoms_for_group(group: Iterable[str]) -> tuple[str, ...]:
        merged: set[str] = set()
        for obligation_id in group:
            merged.update(obligation_atoms[obligation_id])
        for obligation_id in group:
            for atom_id in obligation_atoms[obligation_id]:
                if atom_id.startswith("detail:"):
                    detail_payload = atom_index[atom_id].payload
                    for operation_id in detail_payload.get("source_operation_ids", ()):
                        operation_atom_id = f"operation:{operation_id}"
                        if operation_atom_id in atom_index:
                            merged.add(operation_atom_id)
        return tuple(sorted(merged))

    def _make_page_group(page_obligations: Iterable[str]) -> dict[str, Any]:
        obligations = tuple(sorted(set(page_obligations)))
        atom_ids = _atoms_for_group(obligations)
        return {
            "obligation_ids": obligations,
            "atom_ids": atom_ids,
        }

    def _tokens_for(group: Iterable[str]) -> int:
        return sum(
            conservative_token_estimate(atom_index[atom_id].payload)
            for atom_id in _atoms_for_group(group)
        )

    # Seed groups one-per-obligation.  The earlier detail-seeded implementation
    # could place an obligation that referenced two details in two pages, which
    # silently duplicated a planned task.  Detail IDs are retained separately
    # as adjacency metadata; the obligation itself is always atomic and appears
    # in exactly one group.
    groups: list[set[str]] = [{obligation_id} for obligation_id in obligation_ids]
    group_details: list[set[str]] = [
        set(obligation_details.get(obligation_id, ()))
        for obligation_id in obligation_ids
    ]

    def _group_tokens(group: set[str]) -> int:
        return _tokens_for(sorted(group))

    def _group_obligations(group: set[str]) -> set[str]:
        return set(group)

    merged = True
    while merged:
        merged = False
        for index, left in enumerate(groups):
            for right_index, right in enumerate(groups):
                if index == right_index:
                    continue
                adjacent = any(
                    neighbor in group_details[right_index]
                    for detail in group_details[index]
                    for neighbor in detail_neighbors.get(detail, ())
                ) or bool(group_details[index] & group_details[right_index])
                if not adjacent:
                    continue
                candidate = left | right
                if (
                    _group_tokens(candidate) <= token_budget
                    and len(_group_obligations(candidate)) <= max_obligations_per_page
                ):
                    groups[index] = candidate
                    group_details[index].update(group_details[right_index])
                    groups.pop(right_index)
                    group_details.pop(right_index)
                    merged = True
                    break
            if merged:
                break

    pages: list[dict[str, Any]] = []
    blocking: list[str] = []
    header = _minimal_mechanism_header(mechanism_context)
    for group, _group_detail_ids in zip(groups, group_details):
        obligation_group = sorted(_group_obligations(group))
        if not obligation_group:
            continue
        if _group_tokens(group) > token_budget:
            # Single obligations must always fit; a group that cannot be
            # split further is an over-budget atomic page failure.
            if len(obligation_group) == 1:
                blocking.append(
                    f"unified_atomic_page_over_budget:obligation:{obligation_group[0]}"
                )
                continue
            # Split by obligations deterministically.
            current: list[str] = []
            current_tokens = 0
            for obligation_id in obligation_group:
                single = _tokens_for([obligation_id])
                if single > token_budget:
                    blocking.append(
                        f"unified_atomic_page_over_budget:obligation:{obligation_id}"
                    )
                    continue
                if current and current_tokens + single > token_budget:
                    pages.append(_make_page_group(current))
                    current = []
                    current_tokens = 0
                current.append(obligation_id)
                current_tokens += single
            if current:
                pages.append(_make_page_group(current))
            continue
        pages.append(_make_page_group(obligation_group))

    return pages, blocking


def build_consumer_workset_manifest_v2(
    archive: UnifiedContextArchiveV2,
    formula_obligations_by_mechanism: Mapping[str, Sequence[Any]],
    *,
    max_page_input_tokens: int,
    max_obligations_per_page: int,
) -> ConsumerWorksetManifestV2:
    """Project the archive into formula-task worksets and technical pages."""

    if max_page_input_tokens <= 0 or max_obligations_per_page <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "workset compilation requires positive page token and obligation caps",
        )

    context_index = {
        str(getattr(context, "mechanism_id", "")): context.model_dump(mode="json")
        for context in ()
    }
    atom_index = archive._atom_index()  # noqa: SLF001 - same-package compiler
    # The archive mechanism payload is the context dump itself.
    for atom in archive.mechanism_atoms:
        context_index[str(atom.payload.get("mechanism_id", ""))] = dict(atom.payload)

    pages: list[ConsumerTechnicalPageV2] = []
    worksets: list[ConsumerWorksetV2] = []
    diagnostics: list[dict[str, Any]] = []
    blocking: list[str] = []

    for mechanism_id in sorted(formula_obligations_by_mechanism):
        obligations = tuple(formula_obligations_by_mechanism[mechanism_id])
        if not obligations:
            continue
        mechanism_context = context_index.get(str(mechanism_id), {})
        obligation_atoms: dict[str, tuple[str, ...]] = {}
        seen_obligation_ids: set[str] = set()
        for obligation in obligations:
            obligation_id = str(getattr(obligation, "obligation_id", "")).strip()
            if not obligation_id:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation in {mechanism_id} has no obligation_id",
                )
            if obligation_id in seen_obligation_ids:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} is duplicated in {mechanism_id}",
                )
            seen_obligation_ids.add(obligation_id)
            declared_mechanism_id = str(
                getattr(obligation, "mechanism_id", "") or ""
            ).strip()
            if declared_mechanism_id and declared_mechanism_id != str(mechanism_id):
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} mechanism owner disagrees: "
                    f"{declared_mechanism_id} != {mechanism_id}",
                )
            required = _obligation_required_atom_ids(obligation, archive)
            if not required:
                blocking.append(
                    f"obligation_without_archive_atoms:{mechanism_id}:{obligation_id}"
                )
                diagnostics.append({
                    "kind": "obligation_without_archive_atoms",
                    "mechanism_id": str(mechanism_id),
                    "obligation_id": obligation_id,
                })
                continue
            obligation_atoms[obligation_id] = required

        page_groups, group_blocking = _pack_pages_by_detail_graph(
            archive=archive,
            mechanism_context=mechanism_context,
            obligation_atoms=obligation_atoms,
            token_budget=max_page_input_tokens,
            max_obligations_per_page=max_obligations_per_page,
        )
        blocking.extend(group_blocking)

        workset_page_ids: list[str] = []
        workset_required_atoms: set[str] = set()
        page_index_base = len(pages)
        for group_index, group in enumerate(page_groups):
            header = _minimal_mechanism_header(mechanism_context)
            payload: dict[str, Any] = {
                "archive_digest": archive.content_digest,
                "mechanism_header": header,
                "obligation_ids": list(group["obligation_ids"]),
                "atoms": [
                    dict(atom_index[atom_id].payload) | {"_atom_id": atom_id, "_atom_kind": atom_index[atom_id].atom_kind}
                    for atom_id in group["atom_ids"]
                ],
                # Projection proof is intentionally redundant with the atom
                # markers: it makes an omitted or overreaching atom visible
                # without trusting the serialized payload itself.
                "projection_proof": {
                    atom_id: atom_id for atom_id in group["atom_ids"]
                },
            }
            page_id, _bytes, bytes_digest = compute_technical_page_id(
                archive_digest=archive.content_digest,
                technical_payload=payload,
            )
            page = ConsumerTechnicalPageV2(
                page_id=page_id,
                page_kind="technical",
                archive_digest=archive.content_digest,
                mechanism_id=str(mechanism_id),
                atom_ids=group["atom_ids"],
                technical_payload=payload,
                technical_bytes_digest=bytes_digest,
                token_estimate=conservative_token_estimate(payload),
            )
            if page.token_estimate > max_page_input_tokens:
                blocking.append(
                    f"unified_atomic_page_over_budget:{page.page_id}:{page.token_estimate}"
                )
            else:
                pages.append(page)
                workset_page_ids.append(page_id)
                workset_required_atoms.update(group["atom_ids"])

        # Every formula obligation also gets one deterministic, repair-only
        # join page.  It is not a main invocation page: its payload has no
        # ``obligation_ids`` and is addressed only by ``repair_obligation_id``.
        # Keeping it in the workset makes the repair closure explicit while
        # avoiding a runtime scan of unrelated technical pages.
        for obligation_id in sorted(obligation_atoms):
            join_atom_ids = set(obligation_atoms[obligation_id])
            detail_atom_ids = {
                atom_id for atom_id in join_atom_ids if atom_id.startswith("detail:")
            }
            join_edge_ids: set[str] = set()
            for edge in archive.edge_atoms:
                payload = edge.payload
                source_detail = _detail_atom_id(
                    str(payload.get("source_detail_id", ""))
                )
                target_detail = _detail_atom_id(
                    str(payload.get("target_detail_id", ""))
                )
                if source_detail in detail_atom_ids or target_detail in detail_atom_ids:
                    join_edge_ids.add(edge.atom_id)
            join_atom_ids.update(join_edge_ids)
            join_payload: dict[str, Any] = {
                "archive_digest": archive.content_digest,
                "mechanism_header": _minimal_mechanism_header(mechanism_context),
                "obligation_ids": [],
                "repair_obligation_id": obligation_id,
                "atoms": [
                    dict(atom_index[atom_id].payload)
                    | {"_atom_id": atom_id, "_atom_kind": atom_index[atom_id].atom_kind}
                    for atom_id in sorted(join_atom_ids)
                ],
                "projection_proof": {
                    atom_id: atom_id for atom_id in sorted(join_atom_ids)
                },
                "join_dependency_proof": {
                    "obligation_id": obligation_id,
                    "source_atom_ids": sorted(obligation_atoms[obligation_id]),
                    "edge_atom_ids": sorted(join_edge_ids),
                },
            }
            join_page_id, _join_bytes, join_bytes_digest = compute_technical_page_id(
                archive_digest=archive.content_digest,
                technical_payload=join_payload,
            )
            join_page = ConsumerTechnicalPageV2(
                page_id=join_page_id,
                page_kind="join",
                archive_digest=archive.content_digest,
                mechanism_id=str(mechanism_id),
                atom_ids=tuple(sorted(join_atom_ids)),
                technical_payload=join_payload,
                technical_bytes_digest=join_bytes_digest,
                token_estimate=conservative_token_estimate(join_payload),
            )
            if join_page.token_estimate > max_page_input_tokens:
                blocking.append(
                    f"unified_atomic_page_over_budget:join:{obligation_id}:{join_page.token_estimate}"
                )
                continue
            pages.append(join_page)
            workset_page_ids.append(join_page.page_id)
            workset_required_atoms.update(join_page.atom_ids)

        task_ids = tuple(sorted(
            str(getattr(obligation, "obligation_id", ""))
            for obligation in obligations
            if str(getattr(obligation, "obligation_id", ""))
        ))
        direct_required: set[str] = set()
        for required in obligation_atoms.values():
            direct_required.update(required)
        # Pages carry the deterministic detail -> operation closure required
        # by a consumer.  The workset must therefore record the exact union
        # of page atoms, while still rejecting a projection that dropped a
        # directly required atom.
        all_required: set[str] = set(workset_required_atoms)
        # Do not construct a malformed workset while a page projection is
        # already known to be incomplete (for example an atomic page that is
        # over budget).  The typed compiler error below must win over a
        # secondary Pydantic invariant error with less diagnostic value.
        if (
            not task_ids
            or set(task_ids) != set(obligation_atoms)
            or not direct_required.issubset(all_required)
        ):
            continue
        worksets.append(ConsumerWorksetV2(
            workset_id=f"workset:formula:{mechanism_id}",
            task_kind="formula",
            task_ids=task_ids,
            mechanism_id=str(mechanism_id),
            required_atom_ids=tuple(sorted(all_required)),
            required_page_ids=tuple(workset_page_ids),
        ))
        del page_index_base

    if blocking:
        raise UnifiedCompilerError(
            UNIFIED_PAGE_PROJECTION_INCOMPLETE,
            ";".join(sorted(set(blocking))),
        )

    return ConsumerWorksetManifestV2(
        archive_digest=archive.content_digest,
        source_manifest_digest=archive.source_manifest_digest,
        pages=tuple(pages),
        worksets=tuple(worksets),
        projection_diagnostics=tuple(diagnostics),
    )


def bind_formula_obligation_page_owners(
    formula_obligations_by_mechanism: Mapping[str, Sequence[Any]],
    manifest: ConsumerWorksetManifestV2,
) -> dict[str, tuple[Any, ...]]:
    """Bind every formula obligation to exactly one compiled technical page.

    The formula compiler can determine a primary detail before pagination, but
    only the workset compiler can determine the page owner.  Keeping this
    binding as a separate deterministic step prevents a caller from treating
    page membership as an incidental overlap.  A duplicated or missing page
    owner is a structural failure; it is never repaired by scanning other
    pages at runtime.
    """

    page_owners: dict[str, list[str]] = {}
    join_page_owners: dict[str, list[str]] = {}
    page_index = manifest._page_index()  # noqa: SLF001 - same-package compiler
    for page in manifest.pages:
        for obligation_id in page.technical_payload.get("obligation_ids", ()) or ():
            key = str(obligation_id).strip()
            if key:
                page_owners.setdefault(key, []).append(page.page_id)
        if page.page_kind == "join":
            key = str(
                page.technical_payload.get("repair_obligation_id", "")
            ).strip()
            if key:
                join_page_owners.setdefault(key, []).append(page.page_id)

    bound: dict[str, tuple[Any, ...]] = {}
    for mechanism_id, obligations in formula_obligations_by_mechanism.items():
        rows: list[Any] = []
        for obligation in obligations or ():
            obligation_id = str(getattr(obligation, "obligation_id", "")).strip()
            if not obligation_id:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation in {mechanism_id} has no obligation_id",
                )
            primary_detail_id = str(
                getattr(obligation, "primary_detail_id", "") or ""
            ).strip()
            source_detail_ids = {
                str(value).strip()
                for value in (getattr(obligation, "source_detail_ids", ()) or ())
                if str(value).strip()
            }
            if not primary_detail_id or primary_detail_id not in source_detail_ids:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} has no primary detail owner",
                )
            owners = tuple(dict.fromkeys(page_owners.get(obligation_id, ())))
            if len(owners) != 1:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} has {len(owners)} primary pages",
                )
            join_owners = tuple(dict.fromkeys(join_page_owners.get(obligation_id, ())))
            if len(join_owners) != 1:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} has {len(join_owners)} repair join pages",
                )
            page = page_index.get(owners[0])
            detail_atom_id = _detail_atom_id(primary_detail_id)
            if page is None or detail_atom_id not in set(page.atom_ids):
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} primary detail is absent from page {owners[0]}",
                )
            payload = obligation.model_dump(mode="python") if hasattr(
                obligation, "model_dump"
            ) else dict(obligation)
            payload["primary_page_id"] = owners[0]
            payload["join_page_id"] = join_owners[0]
            # Page ownership is part of the obligation identity.  The source
            # obligation's digest was computed before pagination, so retaining
            # it after adding ``primary_page_id`` would make the strict model
            # validator reject an otherwise valid rebind.
            payload.pop("content_digest", None)
            model_type = obligation.__class__
            try:
                rows.append(model_type.model_validate(payload))
            except AttributeError as exc:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"formula obligation {obligation_id} cannot be rebound",
                ) from exc
        bound[str(mechanism_id)] = tuple(rows)
    return bound


def extend_writer_worksets_from_narrative_plan(
    manifest: ConsumerWorksetManifestV2,
    narrative_plan: Any,
    *,
    max_page_input_tokens: int,
    archive: UnifiedContextArchiveV2 | None = None,
) -> ConsumerWorksetManifestV2:
    """Extend a formula workset manifest with section-scoped writer worksets.

    ``narrative_plan`` supplies, per section, the mechanism and the detail /
    formula / claim IDs the section must cover.  Writer pages are rebuilt from
    the archive atom index (or, for legacy callers, from the existing formula
    pages) so a section never receives a formula page merely because it shares
    one detail with that page.  The resulting section pages are self-contained
    and their atom union is exactly the section closure.
    """

    if max_page_input_tokens <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "writer workset compilation requires a positive page token cap",
        )
    sections = _narrative_plan_sections(narrative_plan)
    pages = list(manifest.pages)
    worksets = list(manifest.worksets)
    diagnostics: list[dict[str, Any]] = []
    existing_workset_ids = {workset.workset_id for workset in worksets}

    atom_payloads: dict[str, dict[str, Any]] = {}
    atom_mechanisms: dict[str, str] = {}
    if archive is not None:
        if archive.content_digest != manifest.archive_digest:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                "writer archive and workset manifest digests disagree",
            )
        for atom in archive.all_atoms():
            atom_payloads[atom.atom_id] = dict(atom.payload) | {
                "_atom_id": atom.atom_id,
                "_atom_kind": atom.atom_kind,
            }
            atom_mechanisms[atom.atom_id] = atom.primary_mechanism_id
    for page in manifest.pages:
        for raw_atom in page.technical_payload.get("atoms", ()) or ():
            if not isinstance(raw_atom, Mapping):
                continue
            atom_id = str(raw_atom.get("_atom_id", ""))
            if not atom_id:
                continue
            atom_payloads.setdefault(atom_id, dict(raw_atom))
            atom_mechanisms.setdefault(atom_id, str(page.mechanism_id))

    def _candidate_atom_ids(raw_id: Any) -> tuple[str, ...]:
        value = str(raw_id or "").strip()
        if not value:
            return ()
        if value in atom_payloads:
            return (value,)
        candidates = (
            value,
            f"detail:{value}",
            f"operation:{value}",
            f"equation:{value}",
            f"evidence:claim:{value}",
            f"evidence:fact:{value}",
            f"evidence:{value}",
            f"intent:{value}",
        )
        return tuple(candidate for candidate in candidates if candidate in atom_payloads)

    obligation_to_atoms: dict[str, set[str]] = {}
    for page in manifest.pages:
        page_obligation_ids = page.technical_payload.get("obligation_ids", ()) or ()
        for obligation_id in page_obligation_ids:
            obligation_to_atoms.setdefault(str(obligation_id), set()).update(page.atom_ids)

    def _section_required_atoms(section: Mapping[str, Any]) -> tuple[set[str], list[str]]:
        required: set[str] = set()
        unresolved: list[str] = []
        direct_fields = (
            "required_atom_ids", "atom_ids", "detail_ids", "ordered_detail_ids",
            "operation_ids", "equation_ids", "fact_ids", "claim_ids", "evidence_ids",
            "source_detail_ids", "source_operation_ids", "source_equation_ids",
            "source_fact_ids", "source_claim_ids",
        )
        for field_name in direct_fields:
            values = section.get(field_name, ()) or ()
            if isinstance(values, str):
                values = (values,)
            for value in values:
                matches = _candidate_atom_ids(value)
                if matches:
                    required.add(matches[0])
                else:
                    unresolved.append(f"{field_name}:{value}")

        obligation_values = list(section.get("formula_obligation_ids", ()) or ())
        obligation_values.extend(section.get("obligation_ids", ()) or ())
        if section.get("obligation_id"):
            obligation_values.append(section["obligation_id"])
        for obligation_id in obligation_values:
            obligation_key = str(obligation_id)
            mapped = obligation_to_atoms.get(obligation_key)
            if mapped:
                required.update(mapped)
                continue
            matches = _candidate_atom_ids(obligation_key)
            if matches:
                required.add(matches[0])
            else:
                unresolved.append(f"obligation:{obligation_key}")

        # A section with only a canonical mechanism owner still needs the
        # complete owner closure.  This is an explicit owner projection, not
        # a project-wide fallback: only atoms whose archive owner matches are
        # eligible.
        mechanism_ids = set(
            str(value) for value in (
                section.get("mechanism_ids", ()) or ()
            ) if str(value).strip()
        )
        if section.get("mechanism_id"):
            mechanism_ids.add(str(section["mechanism_id"]))
        if not required and mechanism_ids:
            required.update(
                atom_id for atom_id, mechanism_id in atom_mechanisms.items()
                if mechanism_id in mechanism_ids
            )
        return required, unresolved

    def _mechanism_header(mechanism_ids: set[str], section_id: str) -> dict[str, Any]:
        if archive is not None:
            headers = [
                _minimal_mechanism_header(dict(atom.payload))
                for atom in archive.mechanism_atoms
                if str(atom.payload.get("mechanism_id", "")) in mechanism_ids
            ]
            if len(headers) == 1:
                return headers[0]
            if headers:
                return {
                    "mechanism_id": f"join:{section_id}",
                    "mechanism_ids": sorted(mechanism_ids),
                    "mechanism_headers": headers,
                }
        return {
            "mechanism_id": sorted(mechanism_ids)[0] if len(mechanism_ids) == 1 else f"join:{section_id}",
            "mechanism_ids": sorted(mechanism_ids),
        }

    def _build_section_pages(
        *,
        section_id: str,
        required_atoms: set[str],
        mechanism_ids: set[str],
        task_ids: Sequence[str],
        paragraph_rows: Sequence[Mapping[str, Any]] = (),
    ) -> list[ConsumerTechnicalPageV2]:
        atom_ids = sorted(required_atoms)
        if not atom_ids:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                f"section {section_id} has no archive atoms",
            )
        for atom_id in atom_ids:
            if atom_id not in atom_payloads:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"section {section_id} references unknown archive atom {atom_id}",
                )
        page_mechanism_id = (
            sorted(mechanism_ids)[0]
            if len(mechanism_ids) == 1
            else f"join:{section_id}"
        )
        page_kind = "technical" if len(mechanism_ids) <= 1 else "join"
        header = _mechanism_header(mechanism_ids, section_id)
        # Pack paragraph closures rather than cutting a sorted section atom
        # list at an arbitrary byte boundary.  A shared atom may occur in two
        # paragraph closures; repeating it is deliberate and keeps each page
        # independently consumable while the workset's set-union stays exact.
        def _paragraph_atom_group(
            row: Mapping[str, Any],
        ) -> tuple[set[str], set[str], set[str]]:
            paragraph_atoms: set[str] = set()
            detail_ids: set[str] = set()
            obligation_ids: set[str] = set()
            for field_name in (
                "required_detail_ids", "optional_detail_ids", "detail_ids",
                "ordered_detail_ids", "required_atom_ids", "atom_ids",
                "operation_ids", "equation_ids", "fact_ids", "claim_ids",
                "evidence_ids", "source_detail_ids", "source_operation_ids",
                "source_equation_ids", "source_fact_ids", "source_claim_ids",
            ):
                values = row.get(field_name, ()) or ()
                if isinstance(values, str):
                    values = (values,)
                for value in values:
                    matches = _candidate_atom_ids(value)
                    if matches:
                        paragraph_atoms.add(matches[0])
                    value_text = str(value).strip()
                    if field_name in {
                        "required_detail_ids", "optional_detail_ids", "detail_ids",
                        "ordered_detail_ids", "source_detail_ids",
                    } and value_text:
                        detail_ids.add(value_text.removeprefix("detail:"))
            raw_obligations = list(row.get("formula_obligation_ids", ()) or ())
            raw_obligations.extend(row.get("obligation_ids", ()) or ())
            if row.get("obligation_id"):
                raw_obligations.append(row["obligation_id"])
            for value in raw_obligations:
                obligation_id = str(value).strip()
                if not obligation_id:
                    continue
                obligation_ids.add(obligation_id)
                mapped = obligation_to_atoms.get(obligation_id)
                if mapped:
                    paragraph_atoms.update(mapped)
                else:
                    matches = _candidate_atom_ids(obligation_id)
                    if matches:
                        paragraph_atoms.add(matches[0])
            return paragraph_atoms, detail_ids, obligation_ids

        groups: list[tuple[tuple[str, ...], set[str], set[str], set[str]]] = []
        assigned_atoms: set[str] = set()
        for row in paragraph_rows:
            if not isinstance(row, Mapping):
                continue
            paragraph_id = str(row.get("paragraph_id") or "").strip()
            group_atoms, detail_ids, obligation_ids = _paragraph_atom_group(row)
            group_atoms &= required_atoms
            if not group_atoms:
                # Rhetorical-only paragraphs are assigned by the Writer
                # adapter to the residual page and do not grant themselves
                # technical atoms.
                continue
            groups.append(
                (
                    (paragraph_id,) if paragraph_id else (),
                    group_atoms,
                    detail_ids,
                    obligation_ids,
                )
            )
            assigned_atoms.update(group_atoms)
        residual_atoms = required_atoms - assigned_atoms
        if residual_atoms or not groups:
            groups.append(((), residual_atoms or set(required_atoms), set(), set()))

        chunks: list[tuple[list[str], set[str], set[str], set[str]]] = []
        current_atoms: list[str] = []
        current_paragraph_ids: set[str] = set()
        current_detail_ids: set[str] = set()
        current_obligation_ids: set[str] = set()

        def _payload(
            chunk: Sequence[str],
            paragraph_ids: Sequence[str],
            detail_ids: Sequence[str],
            obligation_ids: Sequence[str],
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "archive_digest": manifest.archive_digest,
                "mechanism_header": header,
                "section_id": section_id,
                "obligation_ids": list(sorted(set(str(item) for item in task_ids))),
                "paragraph_ids": list(sorted(set(str(item) for item in paragraph_ids if str(item).strip()))),
                "detail_ids": list(sorted(set(str(item) for item in detail_ids if str(item).strip()))),
                "formula_obligation_ids": list(sorted(set(str(item) for item in obligation_ids if str(item).strip()))),
                "atoms": [atom_payloads[atom_id] for atom_id in chunk],
                "projection_proof": {atom_id: atom_id for atom_id in chunk},
            }
            if page_kind == "join":
                payload["join_dependency_proof"] = {
                    "mechanism_ids": sorted(mechanism_ids),
                    "atom_ids": list(chunk),
                }
            return payload

        def _flush_current() -> None:
            if current_atoms:
                chunks.append(
                    (
                        list(current_atoms),
                        set(current_paragraph_ids),
                        set(current_detail_ids),
                        set(current_obligation_ids),
                    )
                )

        for paragraph_ids, group_atoms, detail_ids, obligation_ids in groups:
            group_atom_ids = sorted(group_atoms)
            candidate_atoms = list(dict.fromkeys([*current_atoms, *group_atom_ids]))
            candidate_tokens = conservative_token_estimate(
                _payload(
                    candidate_atoms,
                    [*current_paragraph_ids, *paragraph_ids],
                    [*current_detail_ids, *detail_ids],
                    [*current_obligation_ids, *obligation_ids],
                )
            )
            if candidate_tokens > max_page_input_tokens and current_atoms:
                _flush_current()
                current_atoms = []
                current_paragraph_ids = set()
                current_detail_ids = set()
                current_obligation_ids = set()
                candidate_atoms = group_atom_ids
                candidate_tokens = conservative_token_estimate(
                    _payload(candidate_atoms, paragraph_ids, detail_ids, obligation_ids)
                )
            if candidate_tokens > max_page_input_tokens:
                raise UnifiedCompilerError(
                    UNIFIED_ATOMIC_PAGE_OVER_BUDGET,
                    f"section {section_id} paragraph closure exceeds page budget",
                )
            current_atoms = candidate_atoms
            current_paragraph_ids.update(paragraph_ids)
            current_detail_ids.update(detail_ids)
            current_obligation_ids.update(obligation_ids)
        _flush_current()
        result: list[ConsumerTechnicalPageV2] = []
        for chunk, paragraph_ids, detail_ids, obligation_ids in chunks:
            payload = _payload(chunk, paragraph_ids, detail_ids, obligation_ids)
            page_id, _bytes, bytes_digest = compute_technical_page_id(
                archive_digest=manifest.archive_digest,
                technical_payload=payload,
            )
            result.append(ConsumerTechnicalPageV2(
                page_id=page_id,
                page_kind=page_kind,  # type: ignore[arg-type]
                archive_digest=manifest.archive_digest,
                mechanism_id=page_mechanism_id,
                atom_ids=tuple(chunk),
                technical_payload=payload,
                technical_bytes_digest=bytes_digest,
                token_estimate=conservative_token_estimate(payload),
            ))
        return result

    for section in sections:
        section_id = str(section.get("section_id", ""))
        if not section_id:
            continue
        workset_id = f"workset:section:{section_id}"
        if workset_id in existing_workset_ids:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_OVERREACH,
                f"duplicate section workset {workset_id}",
            )
        required_atoms, unresolved = _section_required_atoms(section)
        if unresolved:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                f"section {section_id} has unresolved ownership handles: {sorted(set(unresolved))}",
            )
        mechanism_ids = set(
            str(value) for value in (
                section.get("mechanism_ids", ()) or ()
            ) if str(value).strip()
        )
        if section.get("mechanism_id"):
            mechanism_ids.add(str(section["mechanism_id"]))
        if not mechanism_ids:
            mechanism_ids.update(
                atom_mechanisms.get(atom_id, "")
                for atom_id in required_atoms
                if atom_mechanisms.get(atom_id, "")
            )
        task_ids = tuple(sorted({section_id}))
        section_pages = _build_section_pages(
            section_id=section_id,
            required_atoms=required_atoms,
            mechanism_ids=mechanism_ids,
            task_ids=task_ids,
            paragraph_rows=tuple(
                item for item in (section.get("paragraphs") or ())
                if isinstance(item, Mapping)
            ),
        )
        pages.extend(section_pages)
        worksets.append(ConsumerWorksetV2(
            workset_id=workset_id,
            task_kind="section",
            task_ids=task_ids,
            mechanism_id=(sorted(mechanism_ids)[0] if len(mechanism_ids) == 1 else f"join:{section_id}"),
            section_id=section_id,
            required_atom_ids=tuple(sorted(required_atoms)),
            required_page_ids=tuple(page.page_id for page in section_pages),
        ))
        existing_workset_ids.add(workset_id)
        diagnostics.append({
            "kind": "section_projection_compiled",
            "section_id": section_id,
            "required_atom_count": len(required_atoms),
            "page_count": len(section_pages),
        })

    return ConsumerWorksetManifestV2(
        archive_digest=manifest.archive_digest,
        source_manifest_digest=manifest.source_manifest_digest,
        pages=tuple(pages),
        worksets=tuple(worksets),
        projection_diagnostics=tuple(list(manifest.projection_diagnostics) + diagnostics),
    )


def _minimal_page_cover(
    candidate_pages: set[str],
    page_atom_map: Mapping[str, set[str]],
    required_atoms: set[str],
) -> set[str]:
    """Greedy minimal cover: drop candidate pages whose atoms are redundant."""

    cover: set[str] = set(candidate_pages)
    for page_id in sorted(candidate_pages, key=lambda item: (-len(page_atom_map[item]), item)):
        reduced = cover - {page_id}
        covered = set().union(*(page_atom_map[p] for p in reduced)) if reduced else set()
        if required_atoms <= covered:
            cover = reduced
    return cover


def _narrative_plan_sections(narrative_plan: Any) -> list[dict[str, Any]]:
    if narrative_plan is None:
        return []
    if isinstance(narrative_plan, BaseModel):
        narrative_plan = narrative_plan.model_dump(mode="json")
    if isinstance(narrative_plan, Mapping):
        sections = narrative_plan.get("sections", ())
    else:
        sections = getattr(narrative_plan, "sections", ())
    result: list[dict[str, Any]] = []
    for section in sections or ():
        if isinstance(section, BaseModel):
            section = section.model_dump(mode="json")
        if isinstance(section, Mapping):
            paragraphs = section.get("paragraphs", ()) or ()
            paragraph_rows = [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in paragraphs
                if isinstance(item, (BaseModel, Mapping))
            ]
            def _values(name: str) -> tuple[str, ...]:
                values: list[str] = []
                for row in [section, *paragraph_rows]:
                    raw = row.get(name, ()) if isinstance(row, Mapping) else ()
                    if isinstance(raw, str):
                        raw = (raw,)
                    values.extend(str(value) for value in (raw or ()) if str(value).strip())
                return tuple(dict.fromkeys(values))
            result.append({
                "section_id": str(section.get("section_id", "")),
                "mechanism_id": str(
                    section.get("mechanism_id", "") or section.get("primary_mechanism_id", "")
                ),
                # Preserve paragraph rows for page-closure compilation.  The
                # Writer must not reconstruct paragraph ownership after page
                # digests have been frozen from an aggregate id set.
                "paragraphs": tuple(paragraph_rows),
                "detail_ids": tuple(dict.fromkeys(
                    [
                        *_values("detail_ids"),
                        *_values("ordered_detail_ids"),
                        *_values("required_detail_ids"),
                        *_values("optional_detail_ids"),
                    ]
                )),
                "mechanism_ids": _values("mechanism_ids"),
                "required_atom_ids": _values("required_atom_ids"),
                "atom_ids": _values("atom_ids"),
                "operation_ids": _values("operation_ids"),
                "equation_ids": _values("equation_ids"),
                "fact_ids": _values("fact_ids"),
                "claim_ids": _values("claim_ids"),
                "evidence_ids": _values("evidence_ids"),
                "source_detail_ids": _values("source_detail_ids"),
                "source_operation_ids": _values("source_operation_ids"),
                "source_equation_ids": _values("source_equation_ids"),
                "source_fact_ids": _values("source_fact_ids"),
                "source_claim_ids": _values("source_claim_ids"),
                "paragraph_ids": _values("paragraph_ids"),
                "formula_obligation_ids": _values("formula_obligation_ids"),
                "obligation_ids": _values("obligation_ids"),
                "obligation_id": str(section.get("obligation_id", "")),
            })
    return result


# ---------------------------------------------------------------------------
# Budget envelope (layer C support)
# ---------------------------------------------------------------------------


def build_run_invocation_budget_envelope_v1(
    *,
    profile_budget: Mapping[str, int],
    model_capabilities: Mapping[str, Any],
    run_digest: str,
    profile_digest: str,
    model_identity_digest: str,
) -> RunInvocationBudgetEnvelopeV1:
    """Build the frozen run envelope from explicit profile values.

    Missing configuration is a hard failure: production code never supplies
    an unbounded default.
    """

    missing = [
        field for field in BUDGET_FIELD_BY_ENV.values()
        if field not in profile_budget
    ]
    if missing:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            f"profile budget is missing required fields: {sorted(missing)}",
        )
    max_total_input_tokens = int(profile_budget["max_total_input_tokens"])
    if max_total_input_tokens <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "max_total_input_tokens must be positive",
        )
    role_calls = {
        "formalizer": int(profile_budget["max_formalizer_calls"]),
        "writer": int(profile_budget["max_writer_calls"]),
        "realizer": int(profile_budget["max_realizer_calls"]),
        "binder": int(profile_budget.get("max_binder_calls", 0)),
    }
    max_page_input_tokens = int(profile_budget["max_page_input_tokens"])
    if max_page_input_tokens <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "max_page_input_tokens must be positive",
        )
    max_obligations_per_page = int(profile_budget["max_obligations_per_page"])
    if max_obligations_per_page <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "max_obligations_per_page must be positive",
        )
    max_formula_repair_calls = int(profile_budget["max_formula_repair_calls"])
    if max_formula_repair_calls < 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "max_formula_repair_calls must be >= 0",
        )
    context_tokens = int(model_capabilities.get("context_tokens", 0))
    if context_tokens <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "model context token count must be provided and positive",
        )
    for role, calls in role_calls.items():
        if calls < 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"max calls for role {role} must be >= 0",
            )
        role_tokens = int(
            model_capabilities.get(f"max_input_tokens_{role}", max_total_input_tokens)
        )
        if role_tokens < 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"max input tokens for role {role} must be >= 0",
            )
    max_input_tokens_by_role = {
        role: int(model_capabilities.get(f"max_input_tokens_{role}", max_total_input_tokens))
        for role in role_calls
    }
    digest = hashlib.sha256(
        b"code2paper-run-invocation-budget-envelope-v1\0"
        + str(run_digest).encode("utf-8")
        + b"\0"
        + str(profile_digest).encode("utf-8")
    ).hexdigest()
    return RunInvocationBudgetEnvelopeV1(
        envelope_id=f"envelope:{digest}",
        run_digest=str(run_digest),
        profile_digest=str(profile_digest),
        model_identity_digest=str(model_identity_digest),
        max_calls_by_role=role_calls,
        max_input_tokens_by_role=max_input_tokens_by_role,
        max_total_input_tokens=max_total_input_tokens,
        max_formula_repair_calls=max_formula_repair_calls,
        max_page_input_tokens=max_page_input_tokens,
        max_obligations_per_page=max_obligations_per_page,
    )


# ---------------------------------------------------------------------------
# Invocation plan (layer C)
# ---------------------------------------------------------------------------


def _safe_invocation_component(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_." else "-"
        for character in value
    )[:120]


def _request_schema_digest(role: str) -> str:
    return sha256_digest(
        canonical_json_bytes({
            "role": str(role),
            "schema_version": "unified-consumer-response-v2",
            "shape": consumer_response_json_schema(role),
        })
    )


def consumer_response_json_schema(role: str) -> dict[str, Any]:
    """Return the closed V2 response schema for a non-legacy consumer.

    The schema is kept beside the request-envelope compiler so a consumer
    request cannot silently drift from the schema digest frozen in its plan.
    Writer V2 uses the same stable publication response shape as its
    structured decoder; section-local enum/const restrictions remain a
    compatibility detail of the legacy path.
    """

    if str(role) == "realizer":
        return {
            "type": "object",
            "required": [
                "draft_markdown",
                "rendered_detail_ids",
                "used_formula_package_ids",
                "witnesses",
            ],
            "properties": {
                "draft_markdown": {"type": "string"},
                "rendered_detail_ids": {
                    "type": "array", "items": {"type": "string"}
                },
                "used_formula_package_ids": {
                    "type": "array", "items": {"type": "string"}
                },
                "witnesses": {
                    "type": "array", "items": {"type": "object"}
                },
            },
        }
    if str(role) == "formalizer":
        return {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "obligation_id", "latex", "prose_explanation",
                            "symbol_definitions", "material_conditions", "assumptions",
                        ],
                    },
                },
            },
        }
    if str(role) == "writer":
        # Import lazily to keep the pure compiler independent of the LLM
        # module at import time (the LLM module imports shared models too).
        from code2paper.llm.response_schemas import (
            PublicationMethodSectionOutputV1,
            json_schema_for,
        )

        return json_schema_for(PublicationMethodSectionOutputV1)
    return {
        "type": "object",
        "required": ["output"],
        "properties": {"output": {"type": "string"}},
    }


def build_consumer_request_payload(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
) -> dict[str, Any]:
    """Build the canonical payload handed to a consumer caller.

    This payload is shared by plan compilation and execution.  Keeping the
    exact technical payload nested here prevents a caller from rebuilding a
    subtly different page while still allowing role-specific metadata.
    """

    return {
        "consumer_role": str(role),
        "mechanism_id": str(page.mechanism_id),
        "page_id": str(page.page_id),
        "task_ids": tuple(sorted({str(item) for item in task_ids if str(item).strip()})),
        "section_id": str(section_id),
        "is_repair": bool(is_repair),
        "technical_payload": dict(page.technical_payload),
        "technical_bytes_digest": str(page.technical_bytes_digest),
    }


def render_consumer_page_prompt(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
) -> str:
    """Render the deterministic prompt whose digest is frozen in the plan."""

    return canonical_json_bytes(build_consumer_request_payload(
        page=page,
        role=role,
        task_ids=task_ids,
        section_id=section_id,
        is_repair=is_repair,
    )).decode("utf-8")


def consumer_request_envelope_digest(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
) -> str:
    """Compute the exact role-specific envelope digest used by execution."""

    payload = build_consumer_request_payload(
        page=page,
        role=role,
        task_ids=task_ids,
        section_id=section_id,
        is_repair=is_repair,
    )
    prompt = render_consumer_page_prompt(
        page=page,
        role=role,
        task_ids=task_ids,
        section_id=section_id,
        is_repair=is_repair,
    )
    return compute_request_envelope_digest(
        prompt_template_id=f"unified_{role}_page_v2",
        consumer_role=role,
        task_ids=task_ids,
        page_id=page.page_id,
        technical_bytes_digest=page.technical_bytes_digest,
        system_prompt_digest=sha256_digest(
            f"unified:{role}:system:v2".encode("utf-8")
        ),
        rendered_prompt_digest=sha256_digest(prompt.encode("utf-8")),
        canonical_input_payload_digest=sha256_digest(canonical_json_bytes(payload)),
        response_schema_digest=_request_schema_digest(role),
    )


def bound_consumer_llm_config(
    base_config: Any,
    invocation: Any,
) -> Any:
    """Cap an actual consumer config at the frozen invocation budget.

    A deployment-wide ``LLMConfig`` can be larger than one planned page
    request.  Passing it through unchanged would let the provider allocate
    more output than the invocation plan admitted, so the immutable plan is
    applied as the final output ceiling while all other config fields remain
    unchanged.
    """

    planned_max = int(getattr(invocation, "max_output_tokens", 0) or 0)
    if planned_max <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "consumer invocation max_output_tokens must be positive",
        )
    configured_max = int(
        getattr(base_config, "max_output_tokens", planned_max) or 0
    )
    if configured_max <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "consumer LLM config max_output_tokens must be positive",
        )
    ceiling = min(configured_max, planned_max)
    if hasattr(base_config, "model_copy"):
        return base_config.model_copy(update={"max_output_tokens": ceiling})
    raise UnifiedCompilerError(
        UNIFIED_INVOCATION_BUDGET_MISSING,
        "consumer LLM config must support immutable model_copy",
    )


def build_consumer_invocation_plan_v1(
    manifest: ConsumerWorksetManifestV2,
    envelope: RunInvocationBudgetEnvelopeV1,
    *,
    phase: INVOCATION_PHASE = "formalizer",
    parent_plan: ConsumerInvocationPlanV1 | None = None,
    plan_revision: int = 1,
    profile_digest: str,
    model_identity_digest: str,
    model_context_tokens: int,
    role_prompt_token_reserve: Mapping[str, int] | None = None,
    output_token_reserve_by_role: Mapping[str, int] | None = None,
    thinking_token_budget_by_role: Mapping[str, int] | None = None,
    safety_margin_tokens: int = 1024,
    max_attempts: int = 2,
) -> ConsumerInvocationPlanV1:
    """Freeze the actual per-phase call plan; one invocation consumes one page.

    Formalizer repair invocations are pre-declared as conditional slots (one
    per obligation) with dependencies on the owning main invocation; runtime
    activates at most ``formalizer_repair_call_limit`` of them.
    """

    role_reserves = dict(role_prompt_token_reserve or {})
    output_reserves = dict(output_token_reserve_by_role or {})
    thinking_budgets = dict(thinking_token_budget_by_role or {})
    if int(model_context_tokens) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "model_context_tokens must be positive",
        )
    if int(safety_margin_tokens) < 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "safety_margin_tokens must be >= 0",
        )
    if int(max_attempts) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "max_attempts must be positive",
        )
    if str(profile_digest) != str(envelope.profile_digest):
        raise UnifiedCompilerError(
            UNIFIED_RESUME_DIGEST_MISMATCH,
            "plan profile digest disagrees with the run envelope",
        )
    if str(model_identity_digest) != str(envelope.model_identity_digest):
        raise UnifiedCompilerError(
            UNIFIED_RESUME_DIGEST_MISMATCH,
            "plan model identity digest disagrees with the run envelope",
        )
    for reserve_name, values in (
        ("role_prompt_token_reserve", role_reserves),
        ("output_token_reserve_by_role", output_reserves),
        ("thinking_token_budget_by_role", thinking_budgets),
    ):
        if any(int(value) < 0 for value in values.values()):
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"{reserve_name} values must be >= 0",
            )

    invocations: list[ConsumerInvocationV1] = []
    workset_index = {workset.workset_id: workset for workset in manifest.worksets}
    page_index = manifest._page_index()  # noqa: SLF001 - same-package compiler
    join_page_by_obligation: dict[str, str] = {}
    for page in manifest.pages:
        if page.page_kind != "join":
            continue
        obligation_id = str(
            page.technical_payload.get("repair_obligation_id", "")
        ).strip()
        if not obligation_id:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                f"join page {page.page_id} has no repair obligation ID",
            )
        prior = join_page_by_obligation.get(obligation_id)
        if prior is not None and prior != page.page_id:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                f"formula obligation {obligation_id} has duplicate repair join pages",
            )
        join_page_by_obligation[obligation_id] = page.page_id

    if phase == "formalizer":
        repair_limit = envelope.max_formula_repair_calls
        declared_repairs = 0
        for workset in manifest.worksets:
            if workset.task_kind != "formula":
                continue
            page_ids_by_obligation: dict[str, list[str]] = {}
            for page_id in workset.required_page_ids:
                page = page_index[page_id]
                for obligation_id in page.technical_payload.get("obligation_ids", ()):
                    page_ids_by_obligation.setdefault(str(obligation_id), []).append(page_id)
            for page_id in workset.required_page_ids:
                page = page_index[page_id]
                obligation_ids = tuple(
                    str(item) for item in page.technical_payload.get("obligation_ids", ())
                )
                if not obligation_ids:
                    continue
                invocation_id = (
                    f"inv:formalizer:main:{_safe_invocation_component(workset.mechanism_id)}"
                    f":{page_id}"
                )
                invocations.append(ConsumerInvocationV1(
                    invocation_id=invocation_id,
                    role="formalizer",
                    phase="formalizer",
                    workset_id=workset.workset_id,
                    task_ids=obligation_ids,
                    mechanism_id=workset.mechanism_id,
                    page_id=page_id,
                    expected_technical_bytes_digest=page.technical_bytes_digest,
                    expected_request_envelope_digest=consumer_request_envelope_digest(
                        page=page,
                        role="formalizer",
                        task_ids=obligation_ids,
                        is_repair=False,
                    ),
                    max_input_tokens=_per_invocation_input_budget(
                        page_token_estimate=page.token_estimate,
                        role="formalizer",
                        model_context_tokens=model_context_tokens,
                        role_reserves=role_reserves,
                        output_reserves=output_reserves,
                        thinking_budgets=thinking_budgets,
                        safety_margin_tokens=safety_margin_tokens,
                    ),
                    max_output_tokens=int(output_reserves.get("formalizer", 4096)),
                    max_attempts=max_attempts,
                ))
            # Conditional repair slots: bounded by the envelope repair limit
            # across the whole phase, not reset for each mechanism/workset.
            for obligation_id in sorted(workset.task_ids):
                if declared_repairs >= repair_limit:
                    break
                primary_page_ids = tuple(
                    dict.fromkeys(page_ids_by_obligation.get(str(obligation_id), ()))
                )
                if len(primary_page_ids) != 1:
                    raise UnifiedCompilerError(
                        UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                        f"formula obligation {obligation_id} has {len(primary_page_ids)} primary pages",
                    )
                page_id = primary_page_ids[0]
                join_page_id = join_page_by_obligation.get(str(obligation_id), "")
                if not join_page_id:
                    raise UnifiedCompilerError(
                        UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                        f"formula obligation {obligation_id} has no repair join page",
                    )
                page = page_index[join_page_id]
                main_invocation_id = (
                    f"inv:formalizer:main:{_safe_invocation_component(workset.mechanism_id)}"
                    f":{page_id}"
                )
                repair_invocation_id = (
                    f"inv:formalizer:repair:{_safe_invocation_component(workset.mechanism_id)}"
                    f":{_safe_invocation_component(str(obligation_id))}"
                )
                invocations.append(ConsumerInvocationV1(
                    invocation_id=repair_invocation_id,
                    role="formalizer",
                    phase="formalizer",
                    workset_id=workset.workset_id,
                    task_ids=(str(obligation_id),),
                    mechanism_id=workset.mechanism_id,
                    page_id=join_page_id,
                    expected_technical_bytes_digest=page.technical_bytes_digest,
                    expected_request_envelope_digest=consumer_request_envelope_digest(
                        page=page,
                        role="formalizer",
                        task_ids=(str(obligation_id),),
                        is_repair=True,
                    ),
                    max_input_tokens=_per_invocation_input_budget(
                        page_token_estimate=page.token_estimate,
                        role="formalizer",
                        model_context_tokens=model_context_tokens,
                        role_reserves=role_reserves,
                        output_reserves=output_reserves,
                        thinking_budgets=thinking_budgets,
                        safety_margin_tokens=safety_margin_tokens,
                    ),
                    max_output_tokens=int(output_reserves.get("formalizer", 4096)),
                    max_attempts=max_attempts,
                    is_repair=True,
                    repair_obligation_id=str(obligation_id),
                    dependency_invocation_ids=(main_invocation_id,),
                ))
                declared_repairs += 1
    elif phase in ("writer", "realizer"):
        for workset in manifest.worksets:
            if workset.task_kind != "section":
                continue
            for page_id in workset.required_page_ids:
                page = page_index[page_id]
                invocation_id = (
                    f"inv:{phase}:{_safe_invocation_component(workset.section_id)}:{page_id}"
                )
                invocations.append(ConsumerInvocationV1(
                    invocation_id=invocation_id,
                    role=phase,  # type: ignore[arg-type]
                    phase=phase,
                    workset_id=workset.workset_id,
                    task_ids=workset.task_ids,
                    mechanism_id=workset.mechanism_id,
                    section_id=workset.section_id,
                    page_id=page_id,
                    expected_technical_bytes_digest=page.technical_bytes_digest,
                    expected_request_envelope_digest=consumer_request_envelope_digest(
                        page=page,
                        role=phase,
                        task_ids=workset.task_ids,
                        section_id=workset.section_id,
                    ),
                    max_input_tokens=_per_invocation_input_budget(
                        page_token_estimate=page.token_estimate,
                        role=phase,
                        model_context_tokens=model_context_tokens,
                        role_reserves=role_reserves,
                        output_reserves=output_reserves,
                        thinking_budgets=thinking_budgets,
                        safety_margin_tokens=safety_margin_tokens,
                    ),
                    max_output_tokens=int(output_reserves.get(phase, 8192)),
                    max_attempts=max_attempts,
                ))
    else:
        raise UnifiedCompilerError(
            UNIFIED_UNPLANNED_ACTUAL_REQUEST,
            f"invocation plan phase {phase} is not a plannable consumer phase",
        )

    del workset_index
    planned_calls: dict[str, int] = {}
    planned_tokens: dict[str, int] = {}
    for invocation in invocations:
        planned_calls[invocation.role] = planned_calls.get(invocation.role, 0) + 1
        planned_tokens[invocation.role] = (
            planned_tokens.get(invocation.role, 0) + invocation.max_input_tokens
        )
    reserved_calls = dict(
        getattr(parent_plan, "reserved_calls_by_role", {}) or {}
        if parent_plan is not None else {}
    )
    reserved_tokens = dict(
        getattr(parent_plan, "reserved_input_tokens_by_role", {}) or {}
        if parent_plan is not None else {}
    )
    for role, count in planned_calls.items():
        reserved_calls[role] = int(reserved_calls.get(role, 0)) + int(count)
    for role, tokens in planned_tokens.items():
        reserved_tokens[role] = int(reserved_tokens.get(role, 0)) + int(tokens)

    return ConsumerInvocationPlanV1(
        plan_revision=plan_revision,
        parent_plan_digest=(
            parent_plan.content_digest
            if parent_plan is not None and plan_revision > 1
            else ""
        ),
        phase=phase,
        archive_digest=manifest.archive_digest,
        workset_manifest_digest=manifest.content_digest,
        envelope_digest=envelope.content_digest,
        profile_digest=str(profile_digest),
        model_identity_digest=str(model_identity_digest),
        invocations=tuple(invocations),
        formalizer_repair_call_limit=(
            envelope.max_formula_repair_calls if phase == "formalizer" else 0
        ),
        planned_calls_by_role=planned_calls,
        planned_input_tokens_by_role=planned_tokens,
        reserved_calls_by_role=reserved_calls,
        reserved_input_tokens_by_role=reserved_tokens,
    )


def _per_invocation_input_budget(
    *,
    page_token_estimate: int,
    role: str,
    model_context_tokens: int,
    role_reserves: Mapping[str, int],
    output_reserves: Mapping[str, int],
    thinking_budgets: Mapping[str, int],
    safety_margin_tokens: int,
) -> int:
    """page + prompt + thinking + output + margin must fit model context."""

    prompt_reserve = int(role_reserves.get(role, 2048))
    reserved = (
        prompt_reserve
        + int(output_reserves.get(role, 4096))
        + int(thinking_budgets.get(role, 0))
        + int(safety_margin_tokens)
    )
    available_for_page = model_context_tokens - reserved
    if available_for_page <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_EXCEEDED,
            f"role {role} reserves exceed the advertised model context",
        )
    if int(page_token_estimate) > available_for_page:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_EXCEEDED,
            f"page for role {role} does not fit context after declared reserves",
        )
    return int(page_token_estimate) + prompt_reserve


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------

REQUIRED_ADMISSION_GATES: tuple[str, ...] = (
    "run_identity",
    "source",
    "authoring_closed_set",
    "research",
    "mechanism_owner",
    "mechanism_path",
    "formula",
    "workset",
    "invocation",
    "resume",
)


def collect_archive_structural_diagnostics(
    archive: UnifiedContextArchiveV2,
) -> dict[str, Any]:
    """Owner/path structural diagnostics derived from archive atoms alone."""

    core_ownerless: list[str] = []
    ownerless_seed_ids: set[str] = set()
    owner_counts: dict[str, dict[str, int]] = {}
    for atom in archive.detail_atoms:
        payload_owner = str(atom.payload.get("primary_mechanism_id", ""))
        owner = atom.primary_mechanism_id or payload_owner
        if atom.is_core and not owner:
            core_ownerless.append(atom.atom_id)
        if owner:
            owner_counts.setdefault(atom.atom_id, {})
            owner_counts[atom.atom_id][owner] = (
                owner_counts[atom.atom_id].get(owner, 0) + 1
            )
    for atom in archive.mechanism_atoms:
        closure = atom.payload.get("evidence_closure", {})
        if isinstance(closure, Mapping):
            ownerless_seed_ids.update(
                str(seed_id)
                for seed_id in (closure.get("unresolved_seed_ids", ()) or ())
                if str(seed_id).strip()
            )
    conflicts = sorted(
        atom_id for atom_id, counts in owner_counts.items() if len(counts) > 1
    )
    return {
        "core_ownerless_atom_ids": sorted(core_ownerless),
        "core_ownerless_count": len(core_ownerless) + len(ownerless_seed_ids),
        "core_ownerless_seed_ids": sorted(ownerless_seed_ids),
        "owner_conflict_atom_ids": conflicts,
        "core_owner_conflict_count": len(conflicts),
        "merge_proofs": len(archive.merge_proofs),
        "partition_proofs": len(archive.partition_proofs),
    }


def evaluate_unified_live_admission_v1(
    *,
    phase: INVOCATION_PHASE,
    plan: ConsumerInvocationPlanV1,
    envelope: RunInvocationBudgetEnvelopeV1,
    archive: UnifiedContextArchiveV2,
    manifest: ConsumerWorksetManifestV2,
    run_digest: str,
    model_context_tokens: int,
    closed_set_failures: Sequence[str] = (),
    research_failures: Sequence[str] = (),
    mechanism_diagnostics: Mapping[str, Any] | None = None,
    resume_failures: Sequence[str] = (),
    run_identity_failures: Sequence[str] = (),
    source_failures: Sequence[str] = (),
    admission_id: str = "",
) -> UnifiedLiveAdmissionV1:
    """Evaluate and return the persisted pre-request admission decision.

    This is intentionally a redundant verifier.  The Pydantic contracts catch
    malformed individual objects; this boundary checks relationships across
    archive, pages, worksets, plans, and the run envelope before a caller can
    reach an LLM adapter.
    """

    gates: list[UnifiedAdmissionGateV1] = []
    diagnostics = dict(mechanism_diagnostics or {})
    page_index = manifest._page_index()  # noqa: SLF001 - same-package compiler
    atom_index = archive._atom_index()  # noqa: SLF001 - same-package compiler
    workset_index = {workset.workset_id: workset for workset in manifest.worksets}

    def _gate(gate_id: str, failures: Sequence[str]) -> UnifiedAdmissionGateV1:
        normalized = tuple(dict.fromkeys(str(item) for item in failures if str(item)))
        return UnifiedAdmissionGateV1(
            gate_id=gate_id,
            status="pass" if not normalized else "fail",
            failure_codes=normalized,
        )

    identity_failures = list(run_identity_failures)
    if not str(run_digest).strip():
        identity_failures.append("unified_run_digest_missing")
    if plan.phase != phase:
        identity_failures.append("unified_plan_phase_mismatch")
    if envelope.run_digest != str(run_digest):
        identity_failures.append("unified_run_digest_mismatch")
    if plan.archive_digest != archive.content_digest:
        identity_failures.append("unified_plan_archive_digest_mismatch")
    if plan.workset_manifest_digest != manifest.content_digest:
        identity_failures.append("unified_plan_workset_digest_mismatch")
    if plan.envelope_digest != envelope.content_digest:
        identity_failures.append("unified_plan_envelope_digest_mismatch")
    if plan.model_identity_digest != envelope.model_identity_digest:
        identity_failures.append("unified_model_identity_digest_mismatch")
    if plan.profile_digest != envelope.profile_digest:
        identity_failures.append("unified_profile_digest_mismatch")
    gates.append(_gate("run_identity", identity_failures))

    source_gate_failures: list[str] = list(source_failures)
    if not archive.repo_snapshot_digest or not archive.project_tree_hash:
        source_gate_failures.append(UNIFIED_SOURCE_MANIFEST_INVALID)
    if not archive.source_manifest_digest:
        source_gate_failures.append(UNIFIED_SOURCE_MANIFEST_MISSING)
    if manifest.source_manifest_digest != archive.source_manifest_digest:
        source_gate_failures.append(UNIFIED_SOURCE_MANIFEST_INVALID)
    for atom in archive.all_atoms():
        reverse = archive.source_reverse_index.get(atom.atom_id, {})
        spans = set(atom.source_span_ids)
        paths = set(reverse.get("source_entry_paths", ()))
        for path in atom.source_entry_paths:
            normalized_path = str(path).replace("\\", "/")
            if (
                not normalized_path
                or normalized_path.startswith("/")
                or normalized_path != str(path)
                or ".." in PurePosixPath(normalized_path).parts
            ):
                source_gate_failures.append(
                    f"{UNIFIED_SOURCE_MANIFEST_INVALID}:{atom.atom_id}"
                )
        if spans and (not paths or not set(atom.source_entry_paths) == paths):
            source_gate_failures.append(f"{UNIFIED_SOURCE_SPAN_UNMAPPED}:{atom.atom_id}")
        if spans and not atom.source_entry_paths:
            source_gate_failures.append(f"{UNIFIED_SOURCE_SPAN_UNMAPPED}:{atom.atom_id}")
        if atom.evidence_authority in {"repository_verified", "repository_partial"}:
            if not atom.source_entry_paths:
                source_gate_failures.append(f"{UNIFIED_SOURCE_SPAN_UNMAPPED}:{atom.atom_id}")
            if atom.atom_kind == "operation" and str(
                atom.payload.get("source_kind", "")
            ) != "first_party_executable":
                source_gate_failures.append(f"{UNIFIED_SOURCE_MANIFEST_INVALID}:{atom.atom_id}")
            if atom.atom_kind == "detail" and str(
                atom.payload.get("evidence_authority", "")
            ) not in {"repository_verified", "repository_partial"}:
                source_gate_failures.append(f"{UNIFIED_SOURCE_MANIFEST_INVALID}:{atom.atom_id}")
    gates.append(_gate("source", source_gate_failures))

    gates.append(_gate("authoring_closed_set", closed_set_failures))
    gates.append(_gate("research", research_failures))

    archive_diagnostics = collect_archive_structural_diagnostics(archive)
    owner_gate_failures: list[str] = []
    if int(diagnostics.get(
        "core_ownerless_count", archive_diagnostics["core_ownerless_count"]
    )) > 0:
        owner_gate_failures.append(UNIFIED_MECHANISM_OWNER_MISSING)
    if int(diagnostics.get(
        "core_owner_conflict_count", archive_diagnostics["core_owner_conflict_count"]
    )) > 0:
        owner_gate_failures.append(UNIFIED_MECHANISM_OWNER_CONFLICT)
    proof_digests: set[str] = set()
    for proof in archive.merge_proofs:
        if proof.content_digest in proof_digests:
            owner_gate_failures.append("unified_mechanism_merge_proof_duplicate")
        proof_digests.add(proof.content_digest)
        if proof.decision == "merged" and not (
            proof.owner_anchor_id.strip()
            and (proof.directed_path_relation_ids or proof.reason == "same_explicit_owner")
        ):
            owner_gate_failures.append("unified_mechanism_merge_proof_invalid")
    known_proof_digests = {proof.content_digest for proof in archive.merge_proofs}
    for atom in archive.mechanism_atoms:
        closure = atom.payload.get("evidence_closure", {})
        for proof_id in closure.get("merge_proof_ids", ()) if isinstance(closure, Mapping) else ():
            if str(proof_id) not in known_proof_digests:
                owner_gate_failures.append("unified_mechanism_merge_proof_invalid")
    if diagnostics.get("invalid_merge_proofs") or diagnostics.get("merge_proofs_valid") is False:
        owner_gate_failures.append("unified_mechanism_merge_proof_invalid")
    gates.append(_gate("mechanism_owner", owner_gate_failures))

    path_gate_failures: list[str] = []
    if diagnostics.get("disconnected_core_detail_count", 0) or diagnostics.get(
        "mechanism_path_disconnected"
    ):
        path_gate_failures.append(UNIFIED_MECHANISM_PATH_DISCONNECTED)
    if diagnostics.get("unknown_core_active_path_count", 0):
        path_gate_failures.append("unified_core_active_path_unknown")
    for atom in archive.detail_atoms:
        if atom.is_core and not atom.primary_mechanism_id:
            path_gate_failures.append(UNIFIED_MECHANISM_OWNER_MISSING)
    gates.append(_gate("mechanism_path", path_gate_failures))

    workset_gate_failures: list[str] = []
    if manifest.archive_digest != archive.content_digest:
        workset_gate_failures.append(UNIFIED_PAGE_PROJECTION_INCOMPLETE)
    for page in manifest.pages:
        if page.token_estimate > envelope.max_page_input_tokens:
            workset_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:page:{page.page_id}"
            )
        raw_atoms = page.technical_payload.get("atoms", ()) or ()
        for raw_atom in raw_atoms:
            if not isinstance(raw_atom, Mapping):
                workset_gate_failures.append(f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{page.page_id}")
                continue
            atom_id = str(raw_atom.get("_atom_id", ""))
            archive_atom = atom_index.get(atom_id)
            if archive_atom is None:
                workset_gate_failures.append(
                    f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{page.page_id}:{atom_id}"
                )
                continue
            projected = dict(raw_atom)
            projected.pop("_atom_id", None)
            projected.pop("_atom_kind", None)
            if canonical_json_bytes(projected) != canonical_json_bytes(dict(archive_atom.payload)):
                workset_gate_failures.append(
                    f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{page.page_id}:{atom_id}"
                )
    for workset in manifest.worksets:
        unknown_atoms = set(workset.required_atom_ids) - set(atom_index)
        if unknown_atoms:
            workset_gate_failures.append(
                f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{workset.workset_id}"
            )
        covered: set[str] = set()
        for page_id in workset.required_page_ids:
            page = page_index.get(page_id)
            if page is None:
                workset_gate_failures.append(
                    f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{workset.workset_id}:{page_id}"
                )
                continue
            covered.update(page.atom_ids)
            if workset.task_kind == "formula" and page.mechanism_id != workset.mechanism_id:
                workset_gate_failures.append(
                    f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{workset.workset_id}:{page_id}"
                )
        if covered != set(workset.required_atom_ids):
            workset_gate_failures.append(
                f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{workset.workset_id}"
            )
    gates.append(_gate("workset", workset_gate_failures))

    formula_gate_failures: list[str] = []
    formalizer_main_page_ids: list[str] = []
    formula_repair_count = 0
    phase_workset_kinds = {
        "formalizer": {"formula"},
        "writer": {"section"},
        "realizer": {"section"},
        "binder": {"binding"},
    }
    expected_worksets = [
        workset for workset in manifest.worksets
        if workset.task_kind in phase_workset_kinds.get(phase, set())
    ]
    invocations_by_workset: dict[str, list[ConsumerInvocationV1]] = {}
    for invocation in plan.invocations:
        page = page_index.get(invocation.page_id)
        workset = workset_index.get(invocation.workset_id)
        if page is None or workset is None:
            formula_gate_failures.append(
                f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}"
            )
            continue
        invocations_by_workset.setdefault(invocation.workset_id, []).append(invocation)
        if invocation.role != phase or invocation.phase != phase:
            formula_gate_failures.append(f"unified_invocation_phase_mismatch:{invocation.invocation_id}")
        expected_task_kind = phase_workset_kinds.get(phase, set())
        if workset.task_kind not in expected_task_kind:
            formula_gate_failures.append(
                f"unified_invocation_task_kind_mismatch:{invocation.invocation_id}"
            )
        if invocation.expected_technical_bytes_digest != page.technical_bytes_digest:
            formula_gate_failures.append(f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}")
        if invocation.mechanism_id != page.mechanism_id:
            formula_gate_failures.append(
                f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{invocation.invocation_id}:mechanism"
            )
        if not set(invocation.task_ids).issubset(set(workset.task_ids)):
            formula_gate_failures.append(f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{invocation.invocation_id}")
        if invocation.page_id not in workset.required_page_ids:
            formula_gate_failures.append(f"{UNIFIED_PAGE_PROJECTION_OVERREACH}:{invocation.invocation_id}")
        if phase != "formalizer" and invocation.is_repair:
            formula_gate_failures.append(
                f"{UNIFIED_UNPLANNED_ACTUAL_REQUEST}:{invocation.invocation_id}:repair"
            )
        if phase == "formalizer":
            page_obligations = set(str(item) for item in (
                page.technical_payload.get("obligation_ids", ()) or ()
            ))
            if invocation.is_repair:
                repair_obligation_id = str(
                    page.technical_payload.get("repair_obligation_id", "")
                )
                if page.page_kind != "join" or repair_obligation_id != str(
                    invocation.repair_obligation_id
                ):
                    formula_gate_failures.append(
                        f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}:join"
                    )
                if invocation.page_id not in workset.required_page_ids:
                    formula_gate_failures.append(
                        f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}:join_unlisted"
                    )
                if invocation.task_ids != (invocation.repair_obligation_id,):
                    formula_gate_failures.append(
                        f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}"
                    )
            elif set(invocation.task_ids) != page_obligations:
                formula_gate_failures.append(f"{UNIFIED_PAGE_PROJECTION_INCOMPLETE}:{invocation.invocation_id}")
            expected_envelope = consumer_request_envelope_digest(
                page=page,
                role="formalizer",
                task_ids=invocation.task_ids,
                is_repair=invocation.is_repair,
            )
            if expected_envelope != invocation.expected_request_envelope_digest:
                formula_gate_failures.append(f"unified_request_envelope_digest_mismatch:{invocation.invocation_id}")
            if invocation.is_repair:
                formula_repair_count += 1
                if invocation.task_ids != (invocation.repair_obligation_id,):
                    formula_gate_failures.append(f"unified_repair_closed_set_mismatch:{invocation.invocation_id}")
            else:
                formalizer_main_page_ids.append(invocation.page_id)
        else:
            if workset.task_kind == "section":
                if invocation.section_id != workset.section_id:
                    formula_gate_failures.append(
                        f"unified_invocation_section_mismatch:{invocation.invocation_id}"
                    )
                if str(page.technical_payload.get("section_id", "")) != str(
                    workset.section_id
                ):
                    formula_gate_failures.append(
                        f"unified_page_section_mismatch:{invocation.invocation_id}"
                    )
                if set(invocation.task_ids) != set(workset.task_ids):
                    formula_gate_failures.append(
                        f"unified_invocation_task_closed_set_mismatch:{invocation.invocation_id}"
                    )
            expected_envelope = consumer_request_envelope_digest(
                page=page,
                role=phase,
                task_ids=invocation.task_ids,
                section_id=invocation.section_id,
            )
            if expected_envelope != invocation.expected_request_envelope_digest:
                formula_gate_failures.append(f"unified_request_envelope_digest_mismatch:{invocation.invocation_id}")
    for workset in expected_worksets:
        planned = invocations_by_workset.get(workset.workset_id, ())
        main = tuple(item for item in planned if not item.is_repair)
        expected_pages = {
            page_id for page_id in workset.required_page_ids
            if page_index[page_id].technical_payload.get("obligation_ids", ())
            or phase != "formalizer"
        }
        actual_pages = {item.page_id for item in main}
        if actual_pages != expected_pages:
            formula_gate_failures.append(
                f"unified_invocation_workset_coverage_mismatch:{workset.workset_id}"
            )
        if not planned and workset.task_ids:
            formula_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_MISSING}:{workset.workset_id}"
            )
    if len(formalizer_main_page_ids) != len(set(formalizer_main_page_ids)):
        formula_gate_failures.append(UNIFIED_UNPLANNED_ACTUAL_REQUEST)
    gates.append(_gate("formula", formula_gate_failures))

    invocation_gate_failures: list[str] = []
    planned_calls = dict(plan.planned_calls_by_role)
    planned_tokens = dict(plan.planned_input_tokens_by_role)
    reserved_calls = dict(plan.reserved_calls_by_role or planned_calls)
    reserved_tokens = dict(plan.reserved_input_tokens_by_role or planned_tokens)
    for role, calls in reserved_calls.items():
        limit = int(envelope.max_calls_by_role.get(role, -1))
        if limit < 0 or int(calls) > limit:
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:calls:{role}:{calls}>{limit}"
            )
    for role, tokens in reserved_tokens.items():
        limit = int(envelope.max_input_tokens_by_role.get(role, -1))
        if limit < 0 or int(tokens) > limit:
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:input_tokens:{role}:{tokens}>{limit}"
            )
    total_reserved_tokens = sum(int(value) for value in reserved_tokens.values())
    if total_reserved_tokens > envelope.max_total_input_tokens:
        invocation_gate_failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:total_input_tokens:"
            f"{total_reserved_tokens}>{envelope.max_total_input_tokens}"
        )
    if phase == "formalizer" and formula_repair_count > envelope.max_formula_repair_calls:
        invocation_gate_failures.append(
            f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:formula_repairs"
        )
    if int(model_context_tokens) <= 0:
        invocation_gate_failures.append(UNIFIED_INVOCATION_BUDGET_MISSING + ":model_context_tokens")
    for invocation in plan.invocations:
        page = page_index.get(invocation.page_id)
        if page is None:
            continue
        if not invocation.task_ids:
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:{invocation.invocation_id}")
        if len(invocation.task_ids) > envelope.max_obligations_per_page:
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:obligations:{invocation.invocation_id}")
        if page.token_estimate > envelope.max_page_input_tokens:
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:page_tokens:{invocation.invocation_id}")
        if invocation.max_input_tokens > model_context_tokens:
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:model_context:{invocation.invocation_id}")
        if invocation.max_attempts <= 0:
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:max_attempts:{invocation.invocation_id}")
    if not planned_calls and expected_worksets:
        invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_MISSING}:no_invocations_planned:{phase}")
    gates.append(_gate("invocation", invocation_gate_failures))

    resume_gate_failures = list(resume_failures)
    if plan.parent_plan_digest and plan.plan_revision <= 1:
        resume_gate_failures.append(UNIFIED_RESUME_DIGEST_MISMATCH)
    gates.append(_gate("resume", resume_gate_failures))

    failure_codes: list[str] = []
    for gate in gates:
        failure_codes.extend(gate.failure_codes)
    status: ADMISSION_STATUS = "pass" if not failure_codes else "fail"
    digest = hashlib.sha256(
        b"code2paper-unified-live-admission-v1\0"
        + str(plan.content_digest).encode("utf-8")
        + b"\0"
        + str(envelope.content_digest).encode("utf-8")
        + b"\0"
        + str(phase).encode("utf-8")
    ).hexdigest()

    return UnifiedLiveAdmissionV1(
        admission_id=admission_id or f"admission:{digest}",
        phase=phase,
        plan_revision=plan.plan_revision,
        run_digest=str(run_digest),
        archive_digest=archive.content_digest,
        workset_manifest_digest=manifest.content_digest,
        envelope_digest=envelope.content_digest,
        plan_digest=plan.content_digest,
        gates=tuple(gates),
        phase_planned_calls_by_role=planned_calls,
        phase_planned_input_tokens_by_role=planned_tokens,
        run_reserved_calls_by_role=reserved_calls,
        run_reserved_input_tokens_by_role=reserved_tokens,
        status=status,
        failure_codes=tuple(dict.fromkeys(failure_codes)),
    )


__all__ = [
    "COMPILER_VERSION",
    "BUDGET_FIELD_BY_ENV",
    "UnifiedCompilerError",
    "build_unified_context_archive_v2",
    "build_consumer_workset_manifest_v2",
    "bind_formula_obligation_page_owners",
    "extend_writer_worksets_from_narrative_plan",
    "build_run_invocation_budget_envelope_v1",
    "build_consumer_request_payload",
    "render_consumer_page_prompt",
    "consumer_request_envelope_digest",
    "bound_consumer_llm_config",
    "consumer_response_json_schema",
    "build_consumer_invocation_plan_v1",
    "collect_archive_structural_diagnostics",
    "evaluate_unified_live_admission_v1",
]
