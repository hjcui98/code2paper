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
import math
import re
import time
import json
import os
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
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
from code2paper.agentic.writer_output_workload import (
    DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE as _DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE,
)
from code2paper.agentic.unified_context_models import (
    UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE,
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
    RoleRequestBudgetV1,
    RunInvocationBudgetEnvelopeV1,
    TASK_KIND,
    UNIFIED_ATOMIC_PAGE_OVER_BUDGET,
    UnifiedAdmissionGateV1,
    UnifiedContextArchiveV2,
    UnifiedLiveAdmissionV1,
    UnifiedRequestTokenAccountingV1,
    UnifiedTokenMeterV1,
    compute_request_envelope_digest,
    compute_technical_page_id,
    conservative_token_meter,
)

COMPILER_VERSION = "unified_context_compiler_v2"

#: Consumer roles that may appear in an invocation plan.  Each one must have a
#: declared request budget; there is no implicit role default.
UNIFIED_BUDGET_ROLES: tuple[str, ...] = ("formalizer", "writer", "realizer", "binder")

#: Env key listing additional consumer roles that opt into the run budget.
#: The four-role contract above stays the *required* contract: a profile only
#: widens it by naming the role here **and** declaring its four budget fields,
#: so every existing profile keeps a byte-identical envelope while a run that
#: wants to meter, for example, its organization-proposal calls can budget
#: them explicitly.  Declaring a role without its fields fails closed.
UNIFIED_EXTRA_ROLES_ENV: str = "CODE2PAPER_UNIFIED_EXTRA_ROLES"

#: Per-role budget fields beyond the call count, in the env suffix convention
#: ``CODE2PAPER_UNIFIED_<FIELD>_<ROLE>``.
UNIFIED_EXTRA_ROLE_FIELDS: tuple[str, ...] = (
    "output_token_reserve",
    "max_request_input_tokens",
    "scaffolding_token_reserve",
)


def read_unified_extra_roles(env: Mapping[str, str]) -> dict[str, Any]:
    """Read the *optional* extra-role budget declarations from the environment.

    Kept out of ``BUDGET_FIELD_BY_ENV`` on purpose: that mapping is the
    required-field contract, and registering optional roles there makes every
    existing profile fail.  Incomplete declarations raise here, so a profile
    can never half-declare a role budget.
    """

    raw = str(env.get(UNIFIED_EXTRA_ROLES_ENV, "") or "")
    extra: dict[str, Any] = {}
    declared: list[str] = []
    for value in raw.replace(";", ",").split(","):
        role = value.strip().lower()
        if not role or role in UNIFIED_BUDGET_ROLES or role in declared:
            continue
        declared.append(role)
    if not declared:
        return extra
    extra["extra_roles"] = ",".join(declared)
    missing: list[str] = []
    for role in declared:
        calls_key = f"CODE2PAPER_UNIFIED_MAX_{role.upper()}_CALLS"
        calls_raw = str(env.get(calls_key, "") or "").strip()
        if not calls_raw:
            missing.append(calls_key)
        else:
            extra[f"max_{role}_calls"] = int(calls_raw)
        for field in UNIFIED_EXTRA_ROLE_FIELDS:
            env_key = f"CODE2PAPER_UNIFIED_{field.upper()}_{role.upper()}"
            raw_value = str(env.get(env_key, "") or "").strip()
            if not raw_value:
                missing.append(env_key)
                continue
            extra[f"{field}_{role}"] = int(raw_value)
    if missing:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            f"extra roles {declared} are declared in {UNIFIED_EXTRA_ROLES_ENV} "
            f"but missing budget fields: {sorted(missing)}",
        )
    return extra


def declared_extra_roles(profile_budget: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the roles an already-merged profile opted in."""

    raw = str(profile_budget.get("extra_roles", "") or "")
    return tuple(
        dict.fromkeys(
            role.strip().lower()
            for role in raw.replace(";", ",").split(",")
            if role.strip() and role.strip().lower() not in UNIFIED_BUDGET_ROLES
        )
    )

BUDGET_FIELD_BY_ENV = {
    "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "max_page_input_tokens",
    "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "max_total_input_tokens",
    "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "max_formalizer_calls",
    "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "max_writer_calls",
    "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "max_realizer_calls",
    "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS": "max_binder_calls",
    "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "max_obligations_per_page",
    "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "max_formula_repair_calls",
    # R6: one declared per-request contract.  These values feed the plan, the
    # admission gate, and the send-time accounting; none of them has a code
    # default.
    "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS": "safety_margin_tokens",
    "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE": "prompt_token_reserve",
    "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE": "thinking_token_reserve",
    **{
        f"CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_{role.upper()}": (
            f"output_token_reserve_{role}"
        )
        for role in UNIFIED_BUDGET_ROLES
    },
    **{
        f"CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_{role.upper()}": (
            f"max_request_input_tokens_{role}"
        )
        for role in UNIFIED_BUDGET_ROLES
    },
    **{
        f"CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_{role.upper()}": (
            f"scaffolding_token_reserve_{role}"
        )
        for role in UNIFIED_BUDGET_ROLES
    },
}

# Retry headroom is an optional extension of the required four-role contract.
# A profile that does not declare it remains valid but has no retry headroom;
# production profiles that permit bounded content retries must declare the
# amount explicitly.
OPTIONAL_BUDGET_FIELD_BY_ENV = {
    f"CODE2PAPER_UNIFIED_RETRY_RESERVE_INPUT_TOKENS_{role.upper()}": (
        f"retry_reserve_input_tokens_{role}"
    )
    for role in UNIFIED_BUDGET_ROLES
}


def read_unified_budget_profile(env: Mapping[str, str]) -> dict[str, int]:
    """Read the declared profile budget contract from the environment.

    Only declared values are returned.  A missing key stays missing so the
    envelope builder fails closed instead of inventing a global default.
    """

    profile: dict[str, int] = {}
    for env_name, field_name in BUDGET_FIELD_BY_ENV.items():
        raw = env.get(env_name)
        if raw is None or not str(raw).strip():
            continue
        profile[field_name] = int(str(raw).strip())
    for env_name, field_name in OPTIONAL_BUDGET_FIELD_BY_ENV.items():
        raw = env.get(env_name)
        if raw is None or not str(raw).strip():
            continue
        profile[field_name] = int(str(raw).strip())
    return profile


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


def _budget_contribution_codes(
    *,
    subject: str,
    token_estimate: int,
    page_budget: int,
    atom_tokens: Mapping[str, int],
    top_atoms: int = 3,
) -> tuple[str, ...]:
    """Report an over-budget atomic unit and what consumed the budget.

    A page that cannot be made legal by regrouping is a hard failure, not a
    reason to truncate evidence.  The codes therefore name the offending
    subject and the largest contributing atoms so the over-budget atom can be
    identified without re-running the compiler.
    """

    codes = [
        f"{UNIFIED_ATOMIC_PAGE_OVER_BUDGET}:{subject}:{int(token_estimate)}>"
        f"{int(page_budget)}"
    ]
    ranked = sorted(
        ((int(tokens), str(atom_id)) for atom_id, tokens in atom_tokens.items()),
        key=lambda item: (-item[0], item[1]),
    )
    for tokens, atom_id in ranked[: max(0, int(top_atoms))]:
        codes.append(
            f"{UNIFIED_ATOMIC_PAGE_OVER_BUDGET}:contribution:{atom_id}:{tokens}"
        )
    return tuple(codes)


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

    header = _minimal_mechanism_header(mechanism_context)

    def _page_payload_for(obligations: Iterable[str]) -> dict[str, Any]:
        """Return the exact technical payload the packed page would carry.

        The grouping budget must meter the page that will actually be sent.
        Summing per-atom estimates ignored the header, obligation list,
        projection proof, and JSON framing, so a group the packer accepted
        could still exceed the profile page cap at manifest construction.
        """

        atom_ids = _atoms_for_group(obligations)
        return {
            "archive_digest": archive.content_digest,
            "mechanism_header": header,
            "obligation_ids": list(sorted(set(str(item) for item in obligations))),
            "atoms": [
                dict(atom_index[atom_id].payload)
                | {"_atom_id": atom_id, "_atom_kind": atom_index[atom_id].atom_kind}
                for atom_id in atom_ids
            ],
            "projection_proof": {atom_id: atom_id for atom_id in atom_ids},
        }

    def _tokens_for(group: Iterable[str]) -> int:
        return conservative_token_estimate(_page_payload_for(group))

    def _atom_contribution_for(group: Iterable[str]) -> dict[str, int]:
        return {
            atom_id: conservative_token_estimate(atom_index[atom_id].payload)
            for atom_id in _atoms_for_group(group)
        }

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
    for group, _group_detail_ids in zip(groups, group_details):
        obligation_group = sorted(_group_obligations(group))
        if not obligation_group:
            continue
        if _group_tokens(group) > token_budget:
            # A group that cannot be split further is an over-budget atomic
            # page failure; the report names the obligation and the atoms that
            # consumed the budget.  Evidence is never truncated to fit.
            if len(obligation_group) == 1:
                blocking.extend(_budget_contribution_codes(
                    subject=f"obligation:{obligation_group[0]}",
                    token_estimate=_tokens_for(obligation_group),
                    page_budget=token_budget,
                    atom_tokens=_atom_contribution_for(obligation_group),
                ))
                continue
            # Split by obligations deterministically, metering the merged page
            # rather than the sum of separately-headed pages.
            current: list[str] = []
            for obligation_id in obligation_group:
                candidate = [*current, obligation_id]
                candidate_tokens = _tokens_for(candidate)
                if candidate_tokens > token_budget and current:
                    pages.append(_make_page_group(current))
                    current = [obligation_id]
                    candidate_tokens = _tokens_for(current)
                if candidate_tokens > token_budget:
                    blocking.extend(_budget_contribution_codes(
                        subject=f"obligation:{obligation_id}",
                        token_estimate=candidate_tokens,
                        page_budget=token_budget,
                        atom_tokens=_atom_contribution_for([obligation_id]),
                    ))
                    continue
                current = candidate
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
                blocking.extend(_budget_contribution_codes(
                    subject=f"page:{page.page_id}",
                    token_estimate=page.token_estimate,
                    page_budget=max_page_input_tokens,
                    atom_tokens={
                        atom_id: conservative_token_estimate(
                            atom_index[atom_id].payload
                        )
                        for atom_id in group["atom_ids"]
                    },
                ))
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
                blocking.extend(_budget_contribution_codes(
                    subject=f"join:{obligation_id}",
                    token_estimate=join_page.token_estimate,
                    page_budget=max_page_input_tokens,
                    atom_tokens={
                        atom_id: conservative_token_estimate(
                            atom_index[atom_id].payload
                        )
                        for atom_id in join_page.atom_ids
                    },
                ))
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


def _resolve_candidate_atom_ids(
    raw_id: Any,
    atom_payloads: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Resolve one narrative handle to an archive atom id, if unambiguous."""

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


def _expand_archive_atom_closure(
    atom_id: str,
    atom_payloads: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    """Expand one archive atom to the source records it explicitly owns.

    A narrative detail is not consumable by itself: its source operations and
    source evidence are part of the same frozen closure.  The formula page
    packer already applies this rule for an obligation, but the Writer page
    compiler also needs it when it assigns detail handles to paragraph pages.
    Keeping the expansion here makes the budget pass and the actual page
    builder use the same closure rather than leaving operations in a residual
    page.
    """

    root = str(atom_id or "").strip()
    if not root:
        return set()
    expanded: set[str] = {root}
    pending = [root]
    while pending:
        current = pending.pop()
        payload = atom_payloads.get(current, {})
        atom_kind = str(payload.get("_atom_kind") or "").strip()
        if not atom_kind:
            atom_kind = current.split(":", 1)[0]
        reference_fields: tuple[tuple[str, str], ...]
        if atom_kind == "detail":
            reference_fields = (
                ("source_operation_ids", "operation"),
                ("source_fact_ids", "evidence:fact"),
                ("source_claim_ids", "evidence:claim"),
                ("source_equation_ids", "equation"),
            )
        elif atom_kind == "operation":
            reference_fields = (
                ("source_fact_ids", "evidence:fact"),
                ("source_claim_ids", "evidence:claim"),
                ("source_equation_ids", "equation"),
            )
        else:
            reference_fields = ()
        for field_name, _kind in reference_fields:
            values = payload.get(field_name, ()) or ()
            if isinstance(values, str):
                values = (values,)
            for value in values:
                matches = _resolve_candidate_atom_ids(value, atom_payloads)
                if not matches:
                    continue
                resolved = matches[0]
                if resolved not in expanded:
                    expanded.add(resolved)
                    pending.append(resolved)
    return expanded


def _formula_obligation_atom_closures(
    formula_obligations: Sequence[Any],
    *,
    archive: UnifiedContextArchiveV2,
    atom_payloads: Mapping[str, Mapping[str, Any]],
) -> dict[str, set[str]]:
    """Map each formula obligation to its own exact archive closure.

    A primary formula page may contain several adjacent obligations.  Its atom
    union is therefore not a valid closure for every individual obligation.
    This mapping is the authoritative per-obligation alternative used by the
    section Writer compiler; it prevents a merged Formalizer page from
    inflating unrelated paragraph pages.
    """

    result: dict[str, set[str]] = {}
    for obligation in formula_obligations or ():
        obligation_id = str(
            obligation.get("obligation_id", "")
            if isinstance(obligation, Mapping)
            else getattr(obligation, "obligation_id", "")
        ).strip()
        if not obligation_id:
            continue
        required = _obligation_required_atom_ids(obligation, archive)
        closure: set[str] = set()
        for atom_id in required:
            closure.update(_expand_archive_atom_closure(atom_id, atom_payloads))
        result[obligation_id] = closure
    return result


def _paragraph_closure_group(
    row: Mapping[str, Any],
    *,
    atom_payloads: Mapping[str, Mapping[str, Any]],
    obligation_to_atoms: Mapping[str, Sequence[str]],
) -> tuple[set[str], set[str], set[str]]:
    """Return the archive closure a narrative paragraph owns.

    Shared by the writer workset builder and the page-budget revision pass so
    a paragraph cannot be measured by one rule and packed by another.
    """

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
            matches = _resolve_candidate_atom_ids(value, atom_payloads)
            if matches:
                # A detail handle owns the detail atom itself.  Operation and
                # evidence atoms are added when an obligation explicitly
                # closes over them; attaching every source operation to every
                # narrative detail would turn a legal paragraph split into an
                # artificial over-budget atomic unit.
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
            paragraph_atoms.update(str(atom_id) for atom_id in mapped)
        else:
            matches = _resolve_candidate_atom_ids(obligation_id, atom_payloads)
            if matches:
                paragraph_atoms.add(matches[0])
    return paragraph_atoms, detail_ids, obligation_ids


def _section_mechanism_header(
    archive: UnifiedContextArchiveV2 | None,
    mechanism_ids: set[str],
    section_id: str,
) -> dict[str, Any]:
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
        "mechanism_id": (
            sorted(mechanism_ids)[0]
            if len(mechanism_ids) == 1
            else f"join:{section_id}"
        ),
        "mechanism_ids": sorted(mechanism_ids),
    }


def _section_page_payload(
    *,
    archive_digest: str,
    header: Mapping[str, Any],
    section_id: str,
    task_ids: Sequence[str],
    paragraph_ids: Sequence[str],
    detail_ids: Sequence[str],
    obligation_ids: Sequence[str],
    formula_package_ids: Sequence[str] = (),
    formula_package_source_detail_ids: Mapping[str, Sequence[str]] | None = None,
    atom_ids: Sequence[str],
    atom_payloads: Mapping[str, Mapping[str, Any]],
    page_kind: str,
    mechanism_ids: set[str],
) -> dict[str, Any]:
    """One section page payload, byte-shaped exactly like the real page."""

    payload: dict[str, Any] = {
        "archive_digest": archive_digest,
        "mechanism_header": dict(header),
        "section_id": section_id,
        "obligation_ids": list(sorted(set(str(item) for item in task_ids))),
        # 审计 §C.1 / 不变量 I5：段落顺序是**叙述顺序**，必须保序去重。
        # 旧实现 sorted(...) 把计划顺序换成字典序（实测事故请求先给 P10..P17 再给
        # P1__f1, P3..P9），于是"实际请求的顺序"与冻结 page contract 表达的不是同一件事。
        "paragraph_ids": list(dict.fromkeys(
            str(item) for item in paragraph_ids if str(item).strip()
        )),
        "detail_ids": list(sorted(set(str(item) for item in detail_ids if str(item).strip()))),
        "formula_obligation_ids": list(sorted(set(str(item) for item in obligation_ids if str(item).strip()))),
        "formula_package_ids": list(sorted(set(
            str(item) for item in formula_package_ids if str(item).strip()
        ))),
        "formula_package_source_detail_ids": {
            str(package_id): list(dict.fromkeys(
                str(detail_id).strip()
                for detail_id in detail_ids
                if str(detail_id).strip()
            ))
            for package_id, detail_ids in sorted(
                (formula_package_source_detail_ids or {}).items()
            )
            if str(package_id).strip()
        },
        "atoms": [dict(atom_payloads[atom_id]) for atom_id in atom_ids],
        "projection_proof": {atom_id: atom_id for atom_id in atom_ids},
    }
    if page_kind == "join":
        payload["join_dependency_proof"] = {
            "mechanism_ids": sorted(mechanism_ids),
            "atom_ids": list(atom_ids),
        }
    return payload


def fit_narrative_plan_to_page_budget(
    narrative_plan: Any,
    *,
    archive: UnifiedContextArchiveV2,
    max_page_input_tokens: int,
    formula_packages: Sequence[Any] = (),
    formula_obligations: Sequence[Any] = (),
    request_token_estimator: Callable[
        [ConsumerTechnicalPageV2, str, Sequence[Mapping[str, Any]]], int
    ] | None = None,
    max_request_input_tokens: int | None = None,
) -> tuple[Any, tuple[str, ...], dict[str, Any]]:
    """Return a plan-revision copy whose paragraphs each fit one legal page.

    The Writer transaction binds one paragraph to exactly one page, so an
    over-budget paragraph cannot be spread over pages without breaking its
    identity.  This pass therefore revises the narrative plan: a paragraph
    whose archive closure exceeds the profile page budget is split into
    consecutive paragraph fragments, each owning a disjoint detail subset,
    and each fragment is measured with the same payload rule the workset
    builder uses.  A single detail whose own closure cannot fit is reported
    with its token contribution and left untouched, so the workset builder
    still fails closed on the exact over-budget atom.
    """

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativeSectionPlanV3,
    )

    if int(max_page_input_tokens) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "paragraph page-budget revision requires a positive cap",
        )
    if request_token_estimator is not None and int(max_request_input_tokens or 0) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "request-aware paragraph revision requires a positive request cap",
        )
    atom_payloads: dict[str, dict[str, Any]] = {
        atom.atom_id: dict(atom.payload) | {
            "_atom_id": atom.atom_id,
            "_atom_kind": atom.atom_kind,
        }
        for atom in archive.all_atoms()
    }
    obligation_to_atoms: dict[str, set[str]] = {}
    for atom in archive.all_atoms():
        for obligation_id in (atom.payload.get("satisfied_obligation_ids", ()) or ()):
            key = str(obligation_id).strip()
            if key:
                obligation_to_atoms.setdefault(key, set()).add(atom.atom_id)
    # Do not use a merged Formalizer page as the closure for every obligation
    # it carries.  The actual formula objects retain the source-level binding
    # needed to rebuild an exact per-obligation closure.
    obligation_to_atoms.update(
        _formula_obligation_atom_closures(
            formula_obligations,
            archive=archive,
            atom_payloads=atom_payloads,
        )
    )
    # Compiled formula packages bind a package id to the obligations it
    # satisfies; without that binding a split cannot prove which fragment owns
    # the package's formula.
    obligation_to_packages: dict[str, tuple[str, ...]] = {}
    package_to_obligations: dict[str, tuple[str, ...]] = {}
    package_to_source_detail_ids: dict[str, tuple[str, ...]] = {}
    for package in (formula_packages or ()):
        package_id = str(
            package.get("package_id") if isinstance(package, Mapping)
            else getattr(package, "package_id", "")
        ).strip()
        satisfied = (
            package.get("satisfied_obligation_ids")
            if isinstance(package, Mapping)
            else getattr(package, "satisfied_obligation_ids", ())
        ) or ()
        if not package_id:
            continue
        source_detail_ids = (
            package.get("source_detail_ids")
            if isinstance(package, Mapping)
            else getattr(package, "source_detail_ids", ())
        ) or ()
        package_to_source_detail_ids[package_id] = tuple(dict.fromkeys(
            str(detail_id).strip()
            for detail_id in source_detail_ids
            if str(detail_id).strip()
        ))
        for obligation_id in satisfied:
            key = str(obligation_id).strip()
            if key:
                obligation_to_packages[key] = (
                    *obligation_to_packages.get(key, ()),
                    package_id,
                )
                package_to_obligations[package_id] = (
                    *package_to_obligations.get(package_id, ()),
                    key,
                )

    diagnostics: dict[str, Any] = {"split_paragraphs": [], "over_budget": []}
    failures: list[str] = []

    def _detail_atom_ids(detail_id: str) -> set[str]:
        matches = _resolve_candidate_atom_ids(detail_id, atom_payloads)
        if not matches:
            return set()
        atom_id = matches[0]
        atoms = {atom_id}
        payload = atom_payloads.get(atom_id, {})
        for operation_id in (payload.get("source_operation_ids", ()) or ()):
            operation_atom = _resolve_candidate_atom_ids(
                f"operation:{operation_id}", atom_payloads
            )
            if operation_atom:
                atoms.add(operation_atom[0])
        return atoms

    def _paragraph_payload_tokens(
        *,
        section_id: str,
        mechanism_ids: set[str],
        paragraph_ids: Sequence[str],
        detail_ids: Sequence[str],
        obligation_ids: Sequence[str],
        row: Mapping[str, Any],
    ) -> tuple[int, int | None, tuple[str, ...], dict[str, int]]:
        group_atoms, _row_details, row_obligations = _paragraph_closure_group(
            row,
            atom_payloads=atom_payloads,
            obligation_to_atoms=obligation_to_atoms,
        )
        obligation_ids = tuple(dict.fromkeys((*obligation_ids, *sorted(row_obligations))))
        atoms = tuple(sorted(group_atoms))
        header = _section_mechanism_header(archive, mechanism_ids, section_id)
        payload = _section_page_payload(
            archive_digest=archive.content_digest,
            header=header,
            section_id=section_id,
            task_ids=(section_id,),
            paragraph_ids=paragraph_ids,
            detail_ids=detail_ids,
            obligation_ids=obligation_ids,
            formula_package_ids=tuple(row.get("formula_package_ids", ()) or ()),
            formula_package_source_detail_ids={
                package_id: package_to_source_detail_ids.get(package_id, ())
                for package_id in (row.get("formula_package_ids", ()) or ())
                if str(package_id).strip()
            },
            atom_ids=atoms,
            atom_payloads=atom_payloads,
            page_kind=(
                "header"
                if not atoms
                else "technical"
                if len(mechanism_ids) <= 1
                else "join"
            ),
            mechanism_ids=mechanism_ids,
        )
        contributions = {
            atom_id: conservative_token_estimate(atom_payloads[atom_id])
            for atom_id in atoms
        }
        conservative_tokens = conservative_token_estimate(payload)
        request_tokens: int | None = None
        if request_token_estimator is not None:
            page_id, _page_bytes, bytes_digest = compute_technical_page_id(
                archive_digest=archive.content_digest,
                technical_payload=payload,
            )
            page_kind = (
                "header"
                if not atoms
                else "technical"
                if len(mechanism_ids) <= 1
                else "join"
            )
            page_mechanism_id = (
                sorted(mechanism_ids)[0]
                if len(mechanism_ids) == 1
                else f"join:{section_id}"
                if mechanism_ids
                else f"header:{section_id}"
            )
            page = ConsumerTechnicalPageV2(
                page_id=page_id,
                page_kind=page_kind,
                archive_digest=archive.content_digest,
                mechanism_id=page_mechanism_id,
                atom_ids=atoms,
                technical_payload=payload,
                technical_bytes_digest=bytes_digest,
                token_estimate=conservative_tokens,
            )
            request_tokens = int(
                request_token_estimator(page, section_id, (row,))
            )
        return conservative_tokens, request_tokens, atoms, contributions

    def _over_budget(conservative_tokens: int, request_tokens: int | None) -> bool:
        return (
            conservative_tokens > int(max_page_input_tokens)
            or (
                request_tokens is not None
                and request_tokens > int(max_request_input_tokens or 0)
            )
        )

    revised_sections: list[Any] = []
    for section in (getattr(narrative_plan, "sections", ()) or ()):
        section_id = str(getattr(section, "section_id", ""))
        mechanism_ids = {
            str(value)
            for value in (getattr(section, "mechanism_ids", ()) or ())
            if str(value).strip()
        }
        revised_paragraphs: list[Any] = []
        for paragraph in (getattr(section, "paragraphs", ()) or ()):
            row = (
                paragraph.model_dump(mode="json")
                if hasattr(paragraph, "model_dump")
                else dict(vars(paragraph))
                if hasattr(paragraph, "__dict__")
                else dict(paragraph)
                if isinstance(paragraph, Mapping)
                else {}
            )
            paragraph_id = str(row.get("paragraph_id", ""))
            tokens, request_tokens, atoms, contributions = _paragraph_payload_tokens(
                section_id=section_id,
                mechanism_ids=mechanism_ids,
                paragraph_ids=(paragraph_id,) if paragraph_id else (),
                detail_ids=tuple(row.get("required_detail_ids", ()) or ())
                + tuple(row.get("optional_detail_ids", ()) or ()),
                obligation_ids=tuple(row.get("formula_obligation_ids", ()) or ()),
                row=row,
            )
            if not _over_budget(tokens, request_tokens):
                revised_paragraphs.append(paragraph)
                continue

            detail_order = tuple(dict.fromkeys(
                str(value)
                for value in (
                    list(row.get("required_detail_ids", ()) or ())
                    + list(row.get("optional_detail_ids", ()) or ())
                )
                if str(value).strip()
            ))
            if len(detail_order) < 2:
                failures.extend(_budget_contribution_codes(
                    subject=f"paragraph:{section_id}:{paragraph_id}",
                    token_estimate=(
                        request_tokens
                        if request_tokens is not None
                        and request_tokens > int(max_request_input_tokens or 0)
                        else tokens
                    ),
                    page_budget=(
                        int(max_request_input_tokens)
                        if request_tokens is not None
                        and request_tokens > int(max_request_input_tokens or 0)
                        else max_page_input_tokens
                    ),
                    atom_tokens=contributions,
                ))
                diagnostics["over_budget"].append({
                    "section_id": section_id,
                    "paragraph_id": paragraph_id,
                    "token_estimate": tokens,
                    "request_token_estimate": request_tokens,
                    "page_budget": max_page_input_tokens,
                    "request_budget": max_request_input_tokens,
                })
                revised_paragraphs.append(paragraph)
                continue

            fragments: list[list[str]] = []
            current: list[str] = []
            for detail_id in detail_order:
                candidate = [*current, detail_id]
                candidate_row = dict(row)
                candidate_row["required_detail_ids"] = tuple(
                    value for value in candidate
                    if value in set(row.get("required_detail_ids", ()) or ())
                )
                candidate_row["optional_detail_ids"] = tuple(
                    value for value in candidate
                    if value not in set(candidate_row["required_detail_ids"])
                )
                candidate_formula_ids = tuple(
                    obligation_id
                    for obligation_id in (row.get("formula_obligation_ids", ()) or ())
                    if not formula_obligations
                    or any(
                        str(getattr(obligation, "obligation_id", "") or (
                            obligation.get("obligation_id", "")
                            if isinstance(obligation, Mapping) else ""
                        )).strip() == str(obligation_id).strip()
                        and (
                            str(getattr(obligation, "primary_detail_id", "") or (
                                obligation.get("primary_detail_id", "")
                                if isinstance(obligation, Mapping) else ""
                            )).removeprefix("detail:")
                            in {
                                str(value).removeprefix("detail:")
                                for value in candidate
                            }
                            or not str(getattr(obligation, "primary_detail_id", "") or (
                                obligation.get("primary_detail_id", "")
                                if isinstance(obligation, Mapping) else ""
                            )).strip()
                        )
                        for obligation in formula_obligations
                    )
                )
                candidate_row["formula_package_ids"] = tuple(
                    package_id
                    for package_id in (row.get("formula_package_ids", ()) or ())
                    if any(
                        package_id in obligation_to_packages.get(
                            str(obligation_id).strip(), ()
                        )
                        for obligation_id in candidate_formula_ids
                    )
                )
                candidate_tokens, candidate_request_tokens, _atoms, _contributions = _paragraph_payload_tokens(
                    section_id=section_id,
                    mechanism_ids=mechanism_ids,
                    paragraph_ids=(paragraph_id,) if paragraph_id else (),
                    detail_ids=tuple(candidate),
                    obligation_ids=candidate_formula_ids,
                    row=candidate_row,
                )
                if _over_budget(candidate_tokens, candidate_request_tokens) and current:
                    fragments.append(current)
                    current = [detail_id]
                    continue
                if _over_budget(candidate_tokens, candidate_request_tokens):
                    request_over = (
                        candidate_request_tokens is not None
                        and candidate_request_tokens > int(max_request_input_tokens or 0)
                    )
                    failures.extend(_budget_contribution_codes(
                        subject=f"detail:{detail_id}",
                        token_estimate=(
                            candidate_request_tokens if request_over else candidate_tokens
                        ),
                        page_budget=(
                            int(max_request_input_tokens)
                            if request_over else max_page_input_tokens
                        ),
                        atom_tokens={
                            atom_id: contributions.get(atom_id, 0)
                            for atom_id in _detail_atom_ids(detail_id)
                        },
                    ))
                    diagnostics["over_budget"].append({
                        "section_id": section_id,
                        "paragraph_id": paragraph_id,
                        "detail_id": detail_id,
                        "token_estimate": candidate_tokens,
                        "request_token_estimate": candidate_request_tokens,
                        "page_budget": max_page_input_tokens,
                        "request_budget": max_request_input_tokens,
                    })
                    current = []
                    fragments = []
                    break
                current = candidate
            if current:
                fragments = [*fragments, current]
            fragments = [fragment for fragment in fragments if fragment]
            if len(fragments) < 2:
                revised_paragraphs.append(paragraph)
                continue

            required_ids = set(row.get("required_detail_ids", ()) or ())
            raw_targets = list(
                (row.get("witness_contract", {}) or {}).get("targets", ()) or ()
            )

            # R7 correction: resolve a target's owning detail by
            # ``target_kind`` and compare canonical ids on both sides.  A
            # ``detail`` target carries its id in ``target_id`` while an
            # ``atom`` target carries it in ``detail_id``; the previous
            # one-field lookup plus one-sided ``detail:`` strip silently dropped
            # every witness, condition and authority obligation of the
            # paragraph while the page budget and the schema validator still
            # passed.
            def _target_field(target: Any, name: str) -> str:
                if isinstance(target, Mapping):
                    return str(target.get(name) or "")
                return str(getattr(target, name, "") or "")

            def _canonical_detail(value: Any) -> str:
                return str(value or "").strip().removeprefix("detail:")

            def _target_detail_key(target: Any) -> str:
                kind = _target_field(target, "target_kind").strip()
                if kind == "atom":
                    return _canonical_detail(_target_field(target, "detail_id"))
                if kind in {"", "detail"}:
                    return _canonical_detail(_target_field(target, "target_id"))
                # field/slot/edge/formula targets are paragraph-scoped.
                return ""

            def _target_identity(target: Any) -> str:
                payload = (
                    target.model_dump(mode="json")
                    if hasattr(target, "model_dump")
                    else dict(target)
                )
                return json.dumps(payload, sort_keys=True, default=str)

            def _fragment_row(candidate: Sequence[str]) -> dict[str, Any]:
                fragment_row = dict(row)
                fragment_row["required_detail_ids"] = tuple(
                    value for value in candidate if value in required_ids
                )
                fragment_row["optional_detail_ids"] = tuple(
                    value for value in candidate if value not in required_ids
                )
                return fragment_row

            fragment_detail_keys = [
                {_canonical_detail(value) for value in candidate}
                for candidate in fragments
            ]
            fragment_rows = [_fragment_row(candidate) for candidate in fragments]
            assigned_targets: list[list[Any]] = [
                [] for _index in range(len(fragments))
            ]
            deferred_targets: list[Any] = []
            for target in raw_targets:
                key = _target_detail_key(target)
                if not key:
                    deferred_targets.append(target)
                    continue
                owners = [
                    index
                    for index, keys in enumerate(fragment_detail_keys)
                    if key in keys
                ]
                if not owners:
                    failures.append(
                        "paragraph_split_target_unassigned:"
                        f"{paragraph_id}:"
                        f"{_target_field(target, 'target_id').strip()}"
                    )
                    continue
                assigned_targets[owners[0]].append(target)
            # Paragraph-scoped targets (field/slot/edge) keep the paragraph's
            # contract on its first fragment: the split is driven by detail
            # closure, and duplicating a paragraph-level obligation on every
            # fragment would double-count it.
            for target in deferred_targets:
                if _target_field(target, "target_kind").strip() != "formula":
                    assigned_targets[0].append(target)
            # A formula obligation may not simply move to the first fragment:
            # the fragment that carries it must own the obligation's whole
            # atom/detail dependency closure, or the split fails closed.
            formula_owner_by_obligation: dict[str, int] = {}
            for target in deferred_targets:
                if _target_field(target, "target_kind").strip() != "formula":
                    continue
                obligation_id = _target_field(target, "target_id").strip()
                required_atoms = set(obligation_to_atoms.get(obligation_id, set()))
                if not required_atoms:
                    assigned_targets[0].append(target)
                    formula_owner_by_obligation[obligation_id] = 0
                    diagnostics.setdefault("formula_owner_unproven", []).append({
                        "section_id": section_id,
                        "paragraph_id": paragraph_id,
                        "formula_obligation_id": obligation_id,
                    })
                    continue
                owner_index: int | None = None
                for index, fragment_row in enumerate(fragment_rows):
                    group_atoms, _row_details, _row_obligations = (
                        _paragraph_closure_group(
                            fragment_row,
                            atom_payloads=atom_payloads,
                            obligation_to_atoms=obligation_to_atoms,
                        )
                    )
                    if required_atoms.issubset(group_atoms):
                        owner_index = index
                        break
                if owner_index is None:
                    failures.append(
                        "paragraph_split_formula_consumer_incomplete:"
                        f"{paragraph_id}:{obligation_id}"
                    )
                    continue
                assigned_targets[owner_index].append(target)
                formula_owner_by_obligation[obligation_id] = owner_index
            # The fragment contract multiset must equal the paragraph contract:
            # no target may be dropped, duplicated or edited by the split.
            before_targets = Counter(_target_identity(target) for target in raw_targets)
            after_targets = Counter(
                _target_identity(target)
                for targets in assigned_targets
                for target in targets
            )
            if before_targets != after_targets:
                missing = sum((before_targets - after_targets).values())
                duplicated = sum((after_targets - before_targets).values())
                failures.append(
                    "paragraph_split_target_contract_not_conserved:"
                    f"{paragraph_id}:missing={missing}:duplicated={duplicated}"
                )

            row_obligations = tuple(row.get("formula_obligation_ids", ()) or ())
            row_packages = tuple(row.get("formula_package_ids", ()) or ())
            package_owner: dict[str, int] = {}
            for package_id in row_packages:
                owners = [
                    index
                    for obligation_id in (
                        package_to_obligations.get(str(package_id), ())
                    )
                    if (index := formula_owner_by_obligation.get(obligation_id))
                    is not None
                ]
                package_owner[str(package_id)] = min(owners) if owners else 0
            package_fragment_by_id: dict[str, str] = {
                str(package_id): f"{paragraph_id}__f"
                f"{package_owner.get(str(package_id), 0) + 1}"
                for package_id in row_packages
            }

            for fragment_index, fragment in enumerate(fragments, start=1):
                fragment_required = tuple(
                    value for value in fragment if value in required_ids
                )
                fragment_optional = tuple(
                    value for value in fragment if value not in required_ids
                )
                fragment_targets = assigned_targets[fragment_index - 1]
                fragment_id = f"{paragraph_id}__f{fragment_index}"
                index = fragment_index - 1
                if formula_owner_by_obligation:
                    fragment_obligations = tuple(
                        obligation_id
                        for obligation_id in row_obligations
                        if formula_owner_by_obligation.get(
                            str(obligation_id)
                        ) == index
                    )
                    fragment_packages = tuple(
                        package_id
                        for package_id in row_packages
                        if package_owner.get(str(package_id)) == index
                    )
                else:
                    # No formula target was declared for this paragraph; the
                    # row-level placement keeps its original first-fragment
                    # behaviour and is reported for audit.
                    fragment_obligations = row_obligations if index == 0 else ()
                    fragment_packages = row_packages if index == 0 else ()
                last_fragment = fragment_index == len(fragments)
                fragment_mid = str(row.get("mechanism_id", ""))
                if fragment:
                    for did in fragment:
                        matches = _resolve_candidate_atom_ids(did, atom_payloads)
                        if matches:
                            payload = atom_payloads.get(matches[0], {})
                            mid = str(payload.get("primary_mechanism_id") or payload.get("mechanism_id") or "").strip()
                            if mid:
                                fragment_mid = mid
                                break
                        if did.startswith("detail:"):
                            parts = did.split(":")
                            if len(parts) >= 3 and parts[1].startswith("mech_"):
                                fragment_mid = f"{parts[1]}:{parts[2]}"
                                break
                revised_paragraphs.append(NarrativeParagraphPlanV3(
                    paragraph_id=fragment_id,
                    section_id=section_id,
                    role=str(row.get("role", "")),
                    mechanism_id=fragment_mid,
                    required_detail_ids=fragment_required,
                    optional_detail_ids=fragment_optional,
                    formula_obligation_ids=fragment_obligations,
                    formula_package_ids=fragment_packages,
                    shared_detail_refs=tuple(row.get("shared_detail_refs", ()) or ()),
                    witness_contract={
                        "schema_version": "1.0",
                        "paragraph_id": fragment_id,
                        "parent_paragraph_id": paragraph_id,
                        "fragment_index": fragment_index,
                        "fragment_count": len(fragments),
                        "rhetorical_goal": str(
                            row.get("rhetorical_goal", "") or row.get("role", "")
                        ),
                        "targets": fragment_targets,
                    },
                    suggested_depth=str(
                        row.get("suggested_depth", "") or "standard"
                    ),
                    reader_goal=str(row.get("reader_goal", "")),
                    transition_from=(
                        str(row.get("transition_from", "") or "")
                        if fragment_index == 1 else ""
                    ),
                    transition_to=(
                        str(row.get("transition_to", "") or "")
                        if last_fragment else ""
                    ),
                    mechanism_ids=(fragment_mid,) if fragment_mid else tuple(row.get("mechanism_ids", ()) or ()),
                ))
                diagnostics["split_paragraphs"].append({
                    "section_id": section_id,
                    "paragraph_id": paragraph_id,
                    "fragment_id": fragment_id,
                    "detail_ids": list(fragment),
                    "package_fragments": dict(package_fragment_by_id),
                    "target_ids": [
                        _target_field(target, "target_id").strip()
                        for target in fragment_targets
                    ],
                    "formula_obligation_ids": list(fragment_obligations),
                    "formula_package_ids": list(fragment_packages),
                })

        revised_sections.append(NarrativeSectionPlanV3(
            section_id=section_id,
            heading=str(getattr(section, "heading", "")),
            mechanism_ids=tuple(getattr(section, "mechanism_ids", ()) or ()),
            paragraphs=tuple(revised_paragraphs),
        ))

    # Units keep their identity and must name the revised paragraph ids.
    # R7 correction: a unit keeps only the paragraphs it owned, with each split
    # paragraph replaced by its own fragments.  Re-deriving the unit's paragraph
    # list from the whole section attached every new fragment to every unit of a
    # multi-unit section.
    split_fragments: dict[tuple[str, str], tuple[str, ...]] = {}
    for entry in diagnostics["split_paragraphs"]:
        key = (entry["section_id"], entry["paragraph_id"])
        split_fragments[key] = (*split_fragments.get(key, ()), entry["fragment_id"])
    revised_units: list[Any] = []
    for unit in (getattr(narrative_plan, "narrative_units", ()) or ()):
        unit_dict = (
            unit.model_dump(mode="json")
            if hasattr(unit, "model_dump")
            else dict(vars(unit))
            if hasattr(unit, "__dict__")
            else dict(unit)
            if isinstance(unit, Mapping)
            else {}
        )
        section_id = str(unit_dict.get("section_id", ""))
        section = next(
            (item for item in revised_sections if item.section_id == section_id),
            None,
        )
        original_ids = tuple(
            str(value) for value in (unit_dict.get("paragraph_ids", ()) or ())
        )
        if section is None or not original_ids:
            revised_units.append(unit)
            continue
        available = {paragraph.paragraph_id for paragraph in section.paragraphs}
        mapped: list[str] = []
        for paragraph_id in original_ids:
            replacements = split_fragments.get(
                (section_id, paragraph_id), (paragraph_id,)
            )
            for replacement in replacements:
                if replacement in available and replacement not in mapped:
                    mapped.append(replacement)
        revised_units.append(unit.model_copy(update={
            "paragraph_ids": tuple(mapped),
            # model_copy intentionally skips validators; clear the old digest
            # so the complete plan is revalidated below after paragraph IDs
            # have changed.
            "content_digest": "",
        }))

    # Formula placements follow the fragment that owns the package's
    # obligation; a split no longer moves every formula to the first fragment.
    split_fragment_owner: dict[tuple[str, str], str] = {}
    for entry in diagnostics["split_paragraphs"]:
        split_fragment_owner.setdefault(
            (entry["section_id"], entry["paragraph_id"]),
            entry.get("owner_obligation_fragment", entry["fragment_id"]),
        )
    placement_owner: dict[str, str] = {}
    for entry in diagnostics["split_paragraphs"]:
        for package_id, fragment_id in (
            entry.get("package_fragments", {}) or {}
        ).items():
            placement_owner[f"{entry['section_id']}|{package_id}"] = fragment_id
    revised_placements: list[Any] = []
    for placement in (getattr(narrative_plan, "formula_placements", ()) or ()):
        section_id = str(
            placement.get("section_id") if isinstance(placement, Mapping)
            else getattr(placement, "section_id", "")
        )
        paragraph_id = str(
            placement.get("paragraph_id") if isinstance(placement, Mapping)
            else getattr(placement, "paragraph_id", "")
        )
        package_id = str(
            placement.get("package_id") if isinstance(placement, Mapping)
            else getattr(placement, "package_id", "")
        )
        replacement = placement_owner.get(f"{section_id}|{package_id}")
        if replacement is None:
            replacement = split_fragment_owner.get((section_id, paragraph_id))
        if replacement and hasattr(placement, "model_copy"):
            revised_placements.append(
                placement.model_copy(update={"paragraph_id": replacement})
            )
        else:
            revised_placements.append(placement)

    revised_plan = narrative_plan.model_copy(update={
        "sections": tuple(revised_sections),
        "narrative_units": tuple(revised_units),
        "formula_placements": tuple(revised_placements),
        "content_digest": "",
    })
    # Re-run the nested Pydantic validators.  The earlier implementation used
    # model_copy for the unit/plan rewrites, leaving stale content digests in
    # the persisted revision and making a resume reject an otherwise legal
    # split plan.
    if hasattr(revised_plan, "model_dump"):
        plan_payload = revised_plan.model_dump(mode="json")
        plan_payload["content_digest"] = ""
        for unit_payload in plan_payload.get("narrative_units", ()) or ():
            if isinstance(unit_payload, Mapping):
                unit_payload["content_digest"] = ""
        revised_plan = type(revised_plan).model_validate(plan_payload)
    return revised_plan, tuple(dict.fromkeys(failures)), diagnostics


#: §C.2：段数上限是**辅助安全限**，它的取值与来源必须显式进入运行契约——
#: 0（关闭）只允许作为显式实验配置，不能靠环境变量悄悄改契约。
SEMANTIC_PARAGRAPH_LIMIT_ENV = "CODE2PAPER_UNIFIED_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE"
SEMANTIC_PARAGRAPH_LIMIT_EXPERIMENT_ENV = (
    "CODE2PAPER_UNIFIED_PARAGRAPH_LIMIT_EXPERIMENT"
)


def semantic_paragraph_limit_policy(
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """返回段数上限的**策略标注**：值、来源、是否显式实验配置。"""

    env = environment if environment is not None else os.environ
    raw = str(env.get(SEMANTIC_PARAGRAPH_LIMIT_ENV, "") or "").strip()
    experiment_flag = str(
        env.get(SEMANTIC_PARAGRAPH_LIMIT_EXPERIMENT_ENV, "") or ""
    ).strip().casefold() in {"1", "true", "yes", "on"}
    if not raw:
        value = int(_DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE)
        source = "default"
        valid = True
    else:
        try:
            value = max(0, int(raw))
            source = "environment"
            valid = True
        except ValueError:
            value = int(_DEFAULT_MAX_SEMANTIC_PARAGRAPHS_PER_PAGE)
            source = "environment_invalid_fallback_default"
            valid = False
    return {
        "value": value,
        "source": source,
        "valid": valid,
        # 0 = 关闭上限：只允许显式实验配置；生产准入据此拒绝。
        "disabled": value == 0,
        "experiment_acknowledged": bool(experiment_flag),
        "env_key": SEMANTIC_PARAGRAPH_LIMIT_ENV,
        "experiment_env_key": SEMANTIC_PARAGRAPH_LIMIT_EXPERIMENT_ENV,
    }


def _max_semantic_paragraphs_per_page() -> int:
    """WP4 §8.2/§8.3：单页语义段落上限（待标定候选，可用环境变量覆盖）。

    这不是"页大小=常量"的正确性标准，而是把"一页必须一次写完多少段"纳入候选页
    联合预算；超出时先拆页（flush 当前页），而不是先拆段落 fragment。
    取值与来源见 :func:`semantic_paragraph_limit_policy`（§C.2 的策略标注）。
    """

    return int(semantic_paragraph_limit_policy()["value"])


def extend_writer_worksets_from_narrative_plan(
    manifest: ConsumerWorksetManifestV2,
    narrative_plan: Any,
    *,
    max_page_input_tokens: int,
    archive: UnifiedContextArchiveV2 | None = None,
    formula_packages: Sequence[Any] = (),
    formula_obligations: Sequence[Any] = (),
    request_token_estimator: Callable[
        [ConsumerTechnicalPageV2, str, Sequence[Mapping[str, Any]]], int
    ] | None = None,
    max_request_input_tokens: int | None = None,
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
    if request_token_estimator is not None and int(max_request_input_tokens or 0) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "request-aware writer workset compilation requires a positive request cap",
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

    formula_package_source_detail_ids: dict[str, tuple[str, ...]] = {}
    for package in formula_packages or ():
        package_id = str(
            package.get("package_id") if isinstance(package, Mapping)
            else getattr(package, "package_id", "")
        ).strip()
        if not package_id:
            continue
        source_detail_ids = (
            package.get("source_detail_ids")
            if isinstance(package, Mapping)
            else getattr(package, "source_detail_ids", ())
        ) or ()
        formula_package_source_detail_ids[package_id] = tuple(dict.fromkeys(
            str(detail_id).strip()
            for detail_id in source_detail_ids
            if str(detail_id).strip()
        ))

    def _candidate_atom_ids(raw_id: Any) -> tuple[str, ...]:
        return _resolve_candidate_atom_ids(raw_id, atom_payloads)

    obligation_to_atoms: dict[str, set[str]] = {}
    if formula_obligations and archive is not None:
        obligation_to_atoms.update(
            _formula_obligation_atom_closures(
                formula_obligations,
                archive=archive,
                atom_payloads=atom_payloads,
            )
        )
    # Legacy callers may not have the typed obligation objects.  Retain the
    # page-derived fallback for those callers, but never let it overwrite the
    # exact source closure supplied by the production path.
    for page in manifest.pages:
        page_obligation_ids = page.technical_payload.get("obligation_ids", ()) or ()
        for obligation_id in page_obligation_ids:
            obligation_key = str(obligation_id)
            if obligation_key not in obligation_to_atoms:
                obligation_to_atoms[obligation_key] = set(page.atom_ids)

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
        return _section_mechanism_header(archive, mechanism_ids, section_id)

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
            # 审计 §C.1/§C.2：无 atom 不等于没有叙事任务或输出成本。旧实现在这里直接
            # 返回**一张** header 页，把全部段落塞进去，候选页段数上限完全没被使用
            # （审计最小反例 A：7 个无 atom 作者段落 + 上限 6 仍是一页）。
            # 现在按同一套候选页判据分页：段数上限（辅助安全限）+ 输入 token 预算；
            # 单个段落自身就超限时给出说明真实限制维度的 typed failure（§C.4）。
            page_kind = "header"
            page_mechanism_id = (
                sorted(mechanism_ids)[0]
                if len(mechanism_ids) == 1
                else f"join:{section_id}" if mechanism_ids
                else f"header:{section_id}"
            )
            header = _mechanism_header(mechanism_ids, section_id)
            archive_digest_value = (
                archive.content_digest if archive is not None else manifest.archive_digest
            )
            ordered_paragraph_ids = list(dict.fromkeys(
                str(row.get("paragraph_id") or "")
                for row in paragraph_rows
                if isinstance(row, Mapping) and str(row.get("paragraph_id") or "").strip()
            ))
            paragraph_limit = _max_semantic_paragraphs_per_page()
            header_pages: list[ConsumerTechnicalPageV2] = []
            current_ids: list[str] = []

            def _header_page(ids: Sequence[str]) -> ConsumerTechnicalPageV2:
                payload = _section_page_payload(
                    archive_digest=archive_digest_value,
                    header=header,
                    section_id=section_id,
                    task_ids=task_ids,
                    paragraph_ids=tuple(ids),
                    detail_ids=(),
                    obligation_ids=(),
                    atom_ids=(),
                    atom_payloads=atom_payloads,
                    page_kind=page_kind,
                    mechanism_ids=mechanism_ids,
                )
                page_id, _page_bytes, bytes_digest = compute_technical_page_id(
                    archive_digest=archive_digest_value,
                    technical_payload=payload,
                )
                return ConsumerTechnicalPageV2(
                    page_id=page_id,
                    page_kind=page_kind,
                    archive_digest=archive_digest_value,
                    mechanism_id=page_mechanism_id,
                    atom_ids=(),
                    technical_payload=payload,
                    technical_bytes_digest=bytes_digest,
                    token_estimate=conservative_token_estimate(payload),
                )

            def _header_over_budget(ids: Sequence[str]) -> str:
                """返回超限维度（"" = 未超限）。段数是辅助限，token 是主限。"""

                payload_tokens = conservative_token_estimate(
                    _section_page_payload(
                        archive_digest=archive_digest_value,
                        header=header,
                        section_id=section_id,
                        task_ids=task_ids,
                        paragraph_ids=tuple(ids),
                        detail_ids=(),
                        obligation_ids=(),
                        atom_ids=(),
                        atom_payloads=atom_payloads,
                        page_kind=page_kind,
                        mechanism_ids=mechanism_ids,
                    )
                )
                if payload_tokens > max_page_input_tokens:
                    return f"input_tokens:{payload_tokens}>{max_page_input_tokens}"
                if paragraph_limit > 0 and len(set(ids)) > paragraph_limit:
                    return (
                        f"paragraph_count:{len(set(ids))}>{paragraph_limit}"
                    )
                return ""

            for paragraph_id in ordered_paragraph_ids:
                candidate_ids = [*current_ids, paragraph_id]
                dimension = _header_over_budget(candidate_ids)
                if dimension and current_ids:
                    header_pages.append(_header_page(current_ids))
                    current_ids = []
                    candidate_ids = [paragraph_id]
                    dimension = _header_over_budget(candidate_ids)
                if dimension:
                    # 单段自身超限：如实报出限制维度，不再只打印一个其实未超的不等式。
                    raise UnifiedCompilerError(
                        UNIFIED_ATOMIC_PAGE_OVER_BUDGET,
                        f"section {section_id} paragraph {paragraph_id} alone exceeds "
                        f"the header page contract ({dimension})",
                    )
                current_ids = candidate_ids
            if current_ids or not header_pages:
                header_pages.append(_header_page(current_ids))
            return header_pages
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
        ) -> tuple[set[str], set[str], set[str], set[str]]:
            paragraph_atoms, detail_ids, obligation_ids = _paragraph_closure_group(
                row,
                atom_payloads=atom_payloads,
                obligation_to_atoms=obligation_to_atoms,
            )
            package_ids = {
                str(value).strip()
                for value in (row.get("formula_package_ids", ()) or ())
                if str(value).strip()
            }
            return paragraph_atoms, detail_ids, obligation_ids, package_ids

        groups: list[
            tuple[tuple[str, ...], set[str], set[str], set[str], set[str]]
        ] = []
        paragraph_rows_by_id = {
            str(row.get("paragraph_id") or ""): row
            for row in paragraph_rows
            if isinstance(row, Mapping) and str(row.get("paragraph_id") or "").strip()
        }
        assigned_atoms: set[str] = set()
        for row in paragraph_rows:
            if not isinstance(row, Mapping):
                continue
            paragraph_id = str(row.get("paragraph_id") or "").strip()
            (
                group_atoms,
                detail_ids,
                obligation_ids,
                package_ids,
            ) = _paragraph_atom_group(row)
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
                    package_ids,
                )
            )
            assigned_atoms.update(group_atoms)
        residual_atoms = required_atoms - assigned_atoms
        if residual_atoms or not groups:
            groups.append(
                ((), residual_atoms or set(required_atoms), set(), set(), set())
            )

        chunks: list[
            tuple[list[str], set[str], set[str], set[str], set[str]]
        ] = []
        current_atoms: list[str] = []
        current_paragraph_ids: set[str] = set()
        current_detail_ids: set[str] = set()
        current_obligation_ids: set[str] = set()
        current_package_ids: set[str] = set()

        def _payload(
            chunk: Sequence[str],
            paragraph_ids: Sequence[str],
            detail_ids: Sequence[str],
            obligation_ids: Sequence[str],
            package_ids: Sequence[str],
        ) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "archive_digest": manifest.archive_digest,
                "mechanism_header": header,
                "section_id": section_id,
                "obligation_ids": list(sorted(set(str(item) for item in task_ids))),
                # 审计 §C.1 / 不变量 I5：段落顺序是**叙述顺序**，必须保序去重。
        # 旧实现 sorted(...) 把计划顺序换成字典序（实测事故请求先给 P10..P17 再给
        # P1__f1, P3..P9），于是"实际请求的顺序"与冻结 page contract 表达的不是同一件事。
        "paragraph_ids": list(dict.fromkeys(
            str(item) for item in paragraph_ids if str(item).strip()
        )),
                "detail_ids": list(sorted(set(str(item) for item in detail_ids if str(item).strip()))),
                "formula_obligation_ids": list(sorted(set(str(item) for item in obligation_ids if str(item).strip()))),
                # Formula packages are response-binding metadata for the
                # Realizer.  They are page-local and are carried alongside,
                # but not substituted for, the immutable technical atoms.
                "formula_package_ids": list(sorted(set(
                    str(item) for item in package_ids if str(item).strip()
                ))),
                "formula_package_source_detail_ids": {
                    str(package_id): list(
                        formula_package_source_detail_ids.get(
                            str(package_id), ()
                        )
                    )
                    for package_id in sorted(set(
                        str(item) for item in package_ids if str(item).strip()
                    ))
                },
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
                        set(current_package_ids),
                    )
                )

        def _candidate_page(
            payload: Mapping[str, Any],
            chunk: Sequence[str],
        ) -> ConsumerTechnicalPageV2:
            page_id, _bytes, bytes_digest = compute_technical_page_id(
                archive_digest=manifest.archive_digest,
                technical_payload=payload,
            )
            return ConsumerTechnicalPageV2(
                page_id=page_id,
                page_kind=page_kind,  # type: ignore[arg-type]
                archive_digest=manifest.archive_digest,
                mechanism_id=page_mechanism_id,
                atom_ids=tuple(chunk),
                technical_payload=dict(payload),
                technical_bytes_digest=bytes_digest,
                token_estimate=conservative_token_estimate(payload),
            )

        def _candidate_request_tokens(
            page: ConsumerTechnicalPageV2,
            paragraph_ids: Sequence[str],
        ) -> int | None:
            if request_token_estimator is None:
                return None
            rows = tuple(
                paragraph_rows_by_id[paragraph_id]
                for paragraph_id in paragraph_ids
                if paragraph_id in paragraph_rows_by_id
            )
            return int(request_token_estimator(page, section_id, rows))

        for (
            paragraph_ids,
            group_atoms,
            detail_ids,
            obligation_ids,
            package_ids,
        ) in groups:
            group_atom_ids = sorted(group_atoms)
            candidate_atoms = list(dict.fromkeys([*current_atoms, *group_atom_ids]))
            candidate_tokens = conservative_token_estimate(
                _payload(
                    candidate_atoms,
                    [*current_paragraph_ids, *paragraph_ids],
                    [*current_detail_ids, *detail_ids],
                    [*current_obligation_ids, *obligation_ids],
                    [*current_package_ids, *package_ids],
                )
            )
            candidate_paragraph_ids = [*current_paragraph_ids, *paragraph_ids]
            candidate_payload = _payload(
                candidate_atoms,
                candidate_paragraph_ids,
                [*current_detail_ids, *detail_ids],
                [*current_obligation_ids, *obligation_ids],
                [*current_package_ids, *package_ids],
            )
            candidate_page = _candidate_page(candidate_payload, candidate_atoms)
            candidate_request_tokens = _candidate_request_tokens(
                candidate_page, candidate_paragraph_ids
            )
            paragraph_limit = _max_semantic_paragraphs_per_page()
            candidate_over_budget = (
                candidate_tokens > max_page_input_tokens
                or (
                    candidate_request_tokens is not None
                    and candidate_request_tokens > int(max_request_input_tokens or 0)
                )
                # WP4 §8.3：输出工作量维度——一页要一次写出的语义段落数超限时
                # 先拆页；输入看起来装得下不代表一次事务写得完（事故页 16 段）。
                or (
                    paragraph_limit > 0
                    and len(set(candidate_paragraph_ids)) > paragraph_limit
                )
            )
            if candidate_over_budget and current_atoms:
                _flush_current()
                current_atoms = []
                current_paragraph_ids = set()
                current_detail_ids = set()
                current_obligation_ids = set()
                current_package_ids = set()
                candidate_atoms = group_atom_ids
                candidate_paragraph_ids = list(paragraph_ids)
                candidate_payload = _payload(
                    candidate_atoms,
                    paragraph_ids,
                    detail_ids,
                    obligation_ids,
                    package_ids,
                )
                candidate_tokens = conservative_token_estimate(candidate_payload)
                candidate_page = _candidate_page(candidate_payload, candidate_atoms)
                candidate_request_tokens = _candidate_request_tokens(
                    candidate_page, candidate_paragraph_ids
                )
                candidate_over_budget = (
                    candidate_tokens > max_page_input_tokens
                    or (
                        candidate_request_tokens is not None
                        and candidate_request_tokens > int(max_request_input_tokens or 0)
                    )
                    or (
                        paragraph_limit > 0
                        and len(set(candidate_paragraph_ids)) > paragraph_limit
                    )
                )
            if candidate_over_budget:
                contributions = ", ".join(
                    f"{atom_id}:{conservative_token_estimate(atom_payloads[atom_id])}"
                    for atom_id in sorted(
                        candidate_atoms,
                        key=lambda item: (
                            -conservative_token_estimate(atom_payloads[item]),
                            item,
                        ),
                    )[:3]
                )
                raise UnifiedCompilerError(
                    UNIFIED_ATOMIC_PAGE_OVER_BUDGET,
                    f"section {section_id} paragraph closure exceeds page budget "
                    f"{candidate_request_tokens if candidate_request_tokens is not None and candidate_request_tokens > int(max_request_input_tokens or 0) else candidate_tokens}>"
                    f"{int(max_request_input_tokens) if candidate_request_tokens is not None and candidate_request_tokens > int(max_request_input_tokens or 0) else max_page_input_tokens}; "
                    f"largest atoms {contributions}",
                )
            current_atoms = candidate_atoms
            current_paragraph_ids.update(paragraph_ids)
            current_detail_ids.update(detail_ids)
            current_obligation_ids.update(obligation_ids)
            current_package_ids.update(package_ids)
        _flush_current()
        result: list[ConsumerTechnicalPageV2] = []
        for (
            chunk,
            paragraph_ids,
            detail_ids,
            obligation_ids,
            package_ids,
        ) in chunks:
            payload = _payload(
                chunk,
                paragraph_ids,
                detail_ids,
                obligation_ids,
                package_ids,
            )
            result.append(_candidate_page(payload, chunk))
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
            mechanism_id=(
                sorted(mechanism_ids)[0]
                if len(mechanism_ids) == 1
                else f"join:{section_id}"
                if mechanism_ids
                else f"header:{section_id}"
            ),
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
        elif hasattr(section, "__dict__"):
            section = dict(vars(section))
        if isinstance(section, Mapping):
            paragraphs = section.get("paragraphs", ()) or ()
            paragraph_rows = [
                item.model_dump(mode="json") if isinstance(item, BaseModel)
                else dict(vars(item)) if hasattr(item, "__dict__")
                else item
                for item in paragraphs
                if isinstance(item, (BaseModel, Mapping)) or hasattr(item, "__dict__")
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
# Versioned token metering (R6)
# ---------------------------------------------------------------------------


def measure_unified_tokens(
    value: Any,
    *,
    meter: UnifiedTokenMeterV1,
    tokenizer: Any | None = None,
) -> int:
    """Measure one request part with the envelope's declared meter.

    A conservative meter is the only measurement available without a real
    tokenizer; it is a declared upper-bound proxy over canonical JSON bytes.
    When the caller supplies a tokenizer, its identity must match the meter so
    a plan and an actual send can never be measured by two different rules.
    """

    if meter.method == "model_tokenizer":
        if tokenizer is None:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                "the envelope declares a model tokenizer meter but no tokenizer "
                "was provided for measurement",
            )
        declared_identity = str(getattr(tokenizer, "identity", "") or "").strip()
        if not declared_identity or declared_identity != meter.tokenizer_identity:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                "supplied tokenizer identity is missing or disagrees with the frozen meter",
            )
        # The OpenAI-compatible client serializes non-string request parts
        # with this exact JSON shape before transport.  Measuring
        # ``str(dict)`` would count a Python representation that is never put
        # on the wire and could silently under/over-count the real request.
        text = (
            value
            if isinstance(value, str)
            else json.dumps(value, ensure_ascii=False, sort_keys=True)
        )
        encoded = tokenizer.encode(text)
        return len(encoded)
    text = (
        value if isinstance(value, str) else canonical_json_bytes(value).decode("utf-8")
    )
    size = len(text.encode("utf-8"))
    return max(1, math.ceil(size / meter.bytes_per_token)) if size else 0


def account_unified_request_tokens(
    *,
    consumer_role: str,
    request_budget: RoleRequestBudgetV1,
    max_input_tokens: int,
    model_context_tokens: int,
    safety_margin_tokens: int,
    meter: UnifiedTokenMeterV1,
    rendered_prompt: Any = "",
    input_payload: Any = None,
    response_schema: Any = None,
    system_prompt: str = "",
    tokenizer: Any | None = None,
    invocation_id: str = "",
    page_id: str = "",
    scaffolding_reserve_tokens: int | None = None,
) -> UnifiedRequestTokenAccountingV1:
    """Measure one request and decide whether it fits its frozen budget.

    The same function measures the frozen plan and the actual request, so a
    mutation that inflates any part is visible as an overflow instead of a
    second, independently drifting threshold.
    """

    if int(max_input_tokens) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "per-request max_input_tokens must be positive",
        )
    if int(model_context_tokens) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "model context tokens must be positive",
        )
    system_tokens = (
        measure_unified_tokens(system_prompt, meter=meter, tokenizer=tokenizer)
        if str(system_prompt)
        else 0
    )
    prompt_tokens = measure_unified_tokens(
        rendered_prompt if rendered_prompt is not None else "",
        meter=meter,
        tokenizer=tokenizer,
    )
    payload_tokens = measure_unified_tokens(
        input_payload if input_payload is not None else {},
        meter=meter,
        tokenizer=tokenizer,
    )
    if (
        meter.method == "model_tokenizer"
        and tokenizer is not None
        and hasattr(tokenizer, "encode_response_schema")
    ):
        schema_tokens = len(
            tokenizer.encode_response_schema(
                response_schema if response_schema is not None else {}
            )
        )
    else:
        schema_tokens = measure_unified_tokens(
            response_schema if response_schema is not None else {},
            meter=meter,
            tokenizer=tokenizer,
        )
    wrapper_reserve = int(request_budget.prompt_token_reserve)
    # The scaffolding allowance belongs to the planned upper bound.  A send
    # boundary measures the real parts and passes 0 so the allowance is not
    # counted twice.
    scaffolding_reserve = (
        int(request_budget.scaffolding_token_reserve)
        if scaffolding_reserve_tokens is None
        else max(0, int(scaffolding_reserve_tokens))
    )
    if (
        meter.method == "model_tokenizer"
        and meter.measurement_basis == "openai_chat_template_v1"
    ):
        if tokenizer is None or not hasattr(tokenizer, "encode_wire_request"):
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                "the frozen chat-template meter requires a wire tokenizer",
            )
        wire_prompt_tokens = len(tokenizer.encode_wire_request(
            prompt=str(rendered_prompt if rendered_prompt is not None else system_prompt),
            input_payload=input_payload if input_payload is not None else {},
            response_schema=response_schema if response_schema is not None else {},
            response_mode="native_json_schema",
            # Keep the tokenizer request identical to the current client
            # request.  The client omits chat_template_kwargs for the
            # qwen38 ``reasoning_effort=low`` profile; callers using an
            # explicit ``reasoning_effort=none`` profile must pass a tokenizer
            # configured for that wire variant instead of silently measuring a
            # different sequence.
            enable_thinking=None,
        ))
        # rendered_prompt_tokens stores the exact chat-template count in this
        # mode. The component fields remain diagnostics; adding them to
        # input_tokens would double-count the user message already tokenized by
        # the wire endpoint.
        prompt_tokens = wire_prompt_tokens
        input_tokens = (
            wire_prompt_tokens
            + schema_tokens
            + wrapper_reserve
            + scaffolding_reserve
        )
    else:
        input_tokens = (
            system_tokens
            + prompt_tokens
            + payload_tokens
            + schema_tokens
            + wrapper_reserve
            + scaffolding_reserve
        )
    required_context = (
        input_tokens
        + int(request_budget.output_token_reserve)
        + int(request_budget.thinking_token_reserve)
        + int(safety_margin_tokens)
    )
    overflow = max(
        0,
        input_tokens - int(max_input_tokens),
        required_context - int(model_context_tokens),
    )
    return UnifiedRequestTokenAccountingV1(
        consumer_role=str(consumer_role),
        invocation_id=str(invocation_id),
        page_id=str(page_id),
        meter=meter,
        system_prompt_tokens=system_tokens,
        rendered_prompt_tokens=prompt_tokens,
        input_payload_tokens=payload_tokens,
        response_schema_tokens=schema_tokens,
        wrapper_reserve_tokens=wrapper_reserve,
        scaffolding_reserve_tokens=scaffolding_reserve,
        input_tokens=input_tokens,
        output_reserve_tokens=int(request_budget.output_token_reserve),
        thinking_reserve_tokens=int(request_budget.thinking_token_reserve),
        safety_margin_tokens=int(safety_margin_tokens),
        model_context_tokens=int(model_context_tokens),
        max_input_tokens=int(max_input_tokens),
        fits=overflow == 0,
        overflow_tokens=overflow,
    )


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
    token_meter: UnifiedTokenMeterV1 | None = None,
) -> RunInvocationBudgetEnvelopeV1:
    """Build the frozen run envelope from explicit profile values.

    Missing configuration is a hard failure: production code never supplies
    an unbounded default.  When no real tokenizer is available the envelope
    carries the declared conservative meter rather than claiming that UTF-8
    bytes are tokenizer tokens.
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
        "binder": int(profile_budget["max_binder_calls"]),
    }
    # Optional, explicitly budgeted roles (see ``UNIFIED_EXTRA_ROLES_ENV``).
    # Nothing is added when the profile declares none, so the four-role
    # envelope stays byte-identical.
    for extra_role in declared_extra_roles(profile_budget):
        calls_key = f"max_{extra_role}_calls"
        if calls_key not in profile_budget:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"extra role {extra_role} is declared without {calls_key}",
            )
        missing = [
            f"{field}_{extra_role}"
            for field in UNIFIED_EXTRA_ROLE_FIELDS
            if f"{field}_{extra_role}" not in profile_budget
        ]
        if missing:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"extra role {extra_role} is missing budget fields: {sorted(missing)}",
            )
        role_calls[extra_role] = int(profile_budget[calls_key])
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
    # R6: the per-request contract is part of the envelope, not a planning
    # default.  Every role reserves prompt/output/thinking tokens explicitly.
    safety_margin_tokens = int(profile_budget["safety_margin_tokens"])
    if safety_margin_tokens < 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "safety_margin_tokens must be >= 0",
        )
    prompt_token_reserve = int(profile_budget["prompt_token_reserve"])
    thinking_token_reserve = int(profile_budget["thinking_token_reserve"])
    for label, value in (
        ("prompt_token_reserve", prompt_token_reserve),
        ("thinking_token_reserve", thinking_token_reserve),
    ):
        if value < 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING, f"{label} must be >= 0"
            )
    request_budget_by_role: dict[str, RoleRequestBudgetV1] = {}
    max_request_input_tokens_by_role: dict[str, int] = {}
    retry_reserve_input_tokens_by_role = {
        role: int(profile_budget.get(f"retry_reserve_input_tokens_{role}", 0) or 0)
        for role in role_calls
    }
    if any(value < 0 for value in retry_reserve_input_tokens_by_role.values()):
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "retry reserve input tokens must be >= 0",
        )
    for role in role_calls:
        output_reserve = int(profile_budget[f"output_token_reserve_{role}"])
        if output_reserve <= 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"output token reserve for role {role} must be positive",
            )
        request_cap = int(profile_budget[f"max_request_input_tokens_{role}"])
        if request_cap <= 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"per-request input cap for role {role} must be positive",
            )
        if request_cap > max_total_input_tokens:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_EXCEEDED,
                f"per-request input cap for role {role} exceeds the run reservation",
            )
        if prompt_token_reserve + output_reserve + thinking_token_reserve + safety_margin_tokens >= context_tokens:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_EXCEEDED,
                f"role {role} reserves leave no model context for a request",
            )
        scaffolding_reserve = int(profile_budget[f"scaffolding_token_reserve_{role}"])
        if scaffolding_reserve < 0:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"scaffolding reserve for role {role} must be >= 0",
            )
        request_budget_by_role[role] = RoleRequestBudgetV1(
            role=role,
            prompt_token_reserve=prompt_token_reserve,
            output_token_reserve=output_reserve,
            thinking_token_reserve=thinking_token_reserve,
            scaffolding_token_reserve=scaffolding_reserve,
        )
        max_request_input_tokens_by_role[role] = request_cap
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
        token_meter=token_meter or conservative_token_meter(),
        request_budget_by_role=request_budget_by_role,
        max_request_input_tokens_by_role=max_request_input_tokens_by_role,
        safety_margin_tokens=safety_margin_tokens,
        model_context_tokens=context_tokens,
        max_calls_by_role=role_calls,
        max_input_tokens_by_role=max_input_tokens_by_role,
        retry_reserve_input_tokens_by_role=retry_reserve_input_tokens_by_role,
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


def _request_schema_digest(role: str, *, section_id: str = "") -> str:
    return sha256_digest(
        canonical_json_bytes({
            "role": str(role),
            "schema_version": "unified-consumer-response-v2",
            "shape": consumer_response_json_schema(role, section_id=section_id),
        })
    )


def consumer_response_json_schema(
    role: str,
    *,
    section_id: str = "",
) -> dict[str, Any]:
    """Return the closed V2 response schema for a non-legacy consumer.

    The schema is kept beside the request-envelope compiler so a consumer
    request cannot silently drift from the schema digest frozen in its plan.
    Writer V2 uses the same stable publication response shape as its
    structured decoder, with the page's exact section id bound when one is
    supplied.  Other section-local restrictions remain a compatibility
    detail of the legacy path.
    """

    if str(role) == "realizer":
        # Keep the nested witness contract closed as well as the outer response
        # shape.  A permissive ``items: {type: object}`` lets a native-schema
        # provider emit legacy evidence records (or large source metadata
        # blobs) that the Realizer's PublicationContentWitnessV1 validator
        # must reject after transport.  The exact witness model is the
        # consumer contract at this boundary, so freeze it into the provider
        # schema rather than relying on post-send validation alone.
        from code2paper.llm.response_schemas import (
            PublicationContentWitnessV1,
            json_schema_for,
        )

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
                    "type": "array",
                    "items": json_schema_for(PublicationContentWitnessV1),
                },
            },
        }
    if str(role) == "formalizer":
        from code2paper.llm.response_schemas import (
            UnifiedFormalizerResponseV2, json_schema_for,
        )

        return json_schema_for(UnifiedFormalizerResponseV2)
    if str(role) == "writer":
        # Import lazily to keep the pure compiler independent of the LLM
        # module at import time (the LLM module imports shared models too).
        from code2paper.llm.response_schemas import (
            PublicationMethodSectionOutputV1,
            json_schema_for,
        )

        schema = json_schema_for(PublicationMethodSectionOutputV1)
        # Unified V2 Writer pages are paragraph transactions, not legacy
        # section-markdown fragments.  Keep this requirement in the frozen
        # provider schema so a page-level response cannot pass transport and
        # fail only after the request has been charged and persisted.  The
        # page-local closed sets and exact witness checks remain in the
        # orchestration/transaction gates.
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "section_id",
            "paragraphs",
        ]))
        paragraphs = schema.get("properties", {}).get("paragraphs")
        if isinstance(paragraphs, dict):
            paragraphs["minItems"] = 1
        normalized_section_id = str(section_id or "").strip()
        if normalized_section_id:
            section_property = schema.get("properties", {}).get("section_id")
            if isinstance(section_property, dict):
                # The V2 request is one immutable page for one section.  Bind
                # that identity in the provider schema as well as in the
                # caller/transaction gates so a representation typo cannot
                # consume a repair attempt before it is rejected.
                section_property["const"] = normalized_section_id
        return schema
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
    repair_feedback: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the canonical payload handed to a consumer caller.

    This payload is shared by plan compilation and execution.  Keeping the
    exact technical payload nested here prevents a caller from rebuilding a
    subtly different page while still allowing role-specific metadata.
    """

    payload: dict[str, Any] = {
        "consumer_role": str(role),
        "mechanism_id": str(page.mechanism_id),
        "page_id": str(page.page_id),
        "task_ids": tuple(sorted({str(item) for item in task_ids if str(item).strip()})),
        "section_id": str(section_id),
        "is_repair": bool(is_repair),
        "technical_payload": dict(page.technical_payload),
        "technical_bytes_digest": str(page.technical_bytes_digest),
    }
    if str(role) == "realizer":
        # The technical page intentionally exposes source atoms and detail
        # projections, but it does not itself prescribe the response binding
        # spelling.  Make that response-local contract explicit at the actual
        # caller boundary.  In particular, do not let a model mistake source
        # span/operation IDs for the closed publication witness IDs.
        technical_payload = getattr(page, "technical_payload", {})
        if not isinstance(technical_payload, Mapping):
            technical_payload = {}
        detail_ids = tuple(dict.fromkeys(
            "detail:" + str(value).strip().removeprefix("detail:")
            for value in (technical_payload.get("detail_ids", ()) or ())
            if str(value).strip()
        ))
        unresolved_detail_ids: list[str] = []
        atom_ids: list[str] = []
        for raw_detail in (technical_payload.get("atoms", ()) or ()):
            if not isinstance(raw_detail, Mapping):
                continue
            raw_detail_id = str(
                raw_detail.get("detail_id") or raw_detail.get("_atom_id") or ""
            ).strip()
            if str(raw_detail.get("evidence_authority", "")) == "unresolved":
                canonical_detail_id = (
                    "detail:" + raw_detail_id.removeprefix("detail:")
                    if raw_detail_id else ""
                )
                if canonical_detail_id:
                    unresolved_detail_ids.append(canonical_detail_id)
            for raw_atom in (raw_detail.get("witness_atoms", ()) or ()):
                if not isinstance(raw_atom, Mapping):
                    continue
                atom_id = str(raw_atom.get("atom_id", "")).strip()
                if atom_id and atom_id not in atom_ids:
                    atom_ids.append(atom_id)
        formula_package_ids = tuple(sorted({
            str(value).strip()
            for value in (technical_payload.get("formula_package_ids", ()) or ())
            if str(value).strip()
        }))
        package_source_detail_ids = (
            technical_payload.get("formula_package_source_detail_ids", {})
            or {}
        )
        if not isinstance(package_source_detail_ids, Mapping):
            package_source_detail_ids = {}
        formula_witness_bindings: list[dict[str, Any]] = []
        for package_id in formula_package_ids:
            source_detail_ids = tuple(dict.fromkeys(
                "detail:" + str(value).strip().removeprefix("detail:")
                for value in (
                    package_source_detail_ids.get(package_id, ())
                    if isinstance(package_source_detail_ids, Mapping)
                    else ()
                )
                if str(value).strip()
            ))
            source_excerpts: list[str] = []
            for raw_detail in (technical_payload.get("atoms", ()) or ()):
                if not isinstance(raw_detail, Mapping):
                    continue
                raw_detail_id = str(
                    raw_detail.get("detail_id")
                    or raw_detail.get("_atom_id")
                    or ""
                ).strip()
                canonical_detail_id = (
                    "detail:" + raw_detail_id.removeprefix("detail:")
                    if raw_detail_id else ""
                )
                if canonical_detail_id not in source_detail_ids:
                    continue
                for raw_atom in (raw_detail.get("witness_atoms", ()) or ()):
                    if not isinstance(raw_atom, Mapping):
                        continue
                    for raw_excerpt in (raw_atom.get("exact_excerpts", ()) or ()):
                        excerpt = str(raw_excerpt)
                        if excerpt and excerpt not in source_excerpts:
                            source_excerpts.append(excerpt)
            formula_witness_bindings.append({
                "package_id": package_id,
                "source_detail_ids": list(source_detail_ids),
                "literal_source_excerpts": source_excerpts,
            })
        payload["response_contract"] = {
            "format": "json",
            "required_top_level_fields": [
                "draft_markdown",
                "rendered_detail_ids",
                "used_formula_package_ids",
                "witnesses",
            ],
            "required_detail_ids": list(detail_ids),
            "required_formula_package_ids": list(formula_package_ids),
            "required_formula_witness_bindings": formula_witness_bindings,
            "required_formula_witness_rule": (
                "Emit exactly one witness with witness_kind=formula for every "
                "required_formula_package_id; target_id must be that exact package "
                "ID. exact_text must be one of the package's listed frozen "
                "literal_source_excerpts, copied verbatim into draft_markdown and "
                "used as a substring of draft_markdown. Never use the package ID "
                "itself as a formula witness or invent a formula excerpt."
            ),
            "unresolved_detail_ids": list(dict.fromkeys(unresolved_detail_ids)),
            "required_detail_witness_rule": (
                "Emit exactly one witness with witness_kind=detail for every "
                "required_detail_id; its target_id must be that exact ID."
            ),
            "unresolved_detail_rule": (
                "For every unresolved_detail_id, describe only the conditional "
                "branch and preserve its unresolved/qualified-partial status; "
                "do not assert an active/default configuration value."
            ),
            "allowed_atom_target_ids": sorted(atom_ids),
            "atom_witness_rule": (
                "Atom witnesses are optional; if emitted, witness_kind=atom and "
                "target_id must be one of allowed_atom_target_ids. Never use a "
                "source span ID or graph-operation ID as target_id."
            ),
            "exact_text_rule": (
                "Every witness exact_text must be copied verbatim from, and be a "
                "substring of, draft_markdown."
            ),
        }
        if repair_feedback:
            repair_items: list[dict[str, Any]] = []
            incumbent_draft_markdown = ""
            for raw_item in repair_feedback:
                if not isinstance(raw_item, Mapping):
                    continue
                if not incumbent_draft_markdown:
                    incumbent_draft_markdown = str(
                        raw_item.get("previous_draft_markdown") or ""
                    )
                excerpts = [
                    str(value)
                    for value in (raw_item.get("source_exact_excerpts") or ())
                    if str(value)
                ]
                incumbent_witnesses = [
                    {
                        "witness_kind": str(value.get("witness_kind") or ""),
                        "target_id": str(value.get("target_id") or ""),
                        "exact_text": str(value.get("exact_text") or ""),
                    }
                    for value in (
                        raw_item.get("validated_incumbent_witnesses") or ()
                    )
                    if isinstance(value, Mapping)
                    and str(value.get("witness_kind") or "")
                    and str(value.get("target_id") or "")
                    and str(value.get("exact_text") or "")
                ]
                repair_item = {
                    "failure_code": str(raw_item.get("failure_code") or ""),
                    "witness_kind": str(raw_item.get("witness_kind") or ""),
                    "target_id": str(raw_item.get("target_id") or ""),
                    "source_exact_excerpts": list(dict.fromkeys(excerpts)),
                    # A repair must make the frozen source bytes visibly
                    # present in the new draft before it can bind metadata to
                    # them.  Keeping this as a separate field makes the
                    # literal-insertion obligation unambiguous to structured
                    # providers that otherwise normalize punctuation.
                    "required_literal_insertions": [
                        {"target_id": str(raw_item.get("target_id") or ""),
                         "exact_text": excerpt}
                        for excerpt in dict.fromkeys(excerpts)
                    ],
                }
                if incumbent_witnesses:
                    repair_item["validated_incumbent_witnesses"] = incumbent_witnesses
                repair_items.append(repair_item)
            if repair_items:
                repair_kind = (
                    "response_format"
                    if any(
                        str(item.get("failure_code") or "")
                        in {"realizer_response_not_json", "realizer_response_not_object"}
                        for item in repair_items
                    )
                    else "realizer_witness_binding"
                )
                payload["response_contract"]["bounded_content_repair"] = {
                    "repair_kind": repair_kind,
                    "incumbent_draft_markdown": incumbent_draft_markdown,
                    "incumbent_rule": (
                        "The incumbent_draft_markdown is prior model output, not "
                        "technical authority. Preserve its valid witness-bearing "
                        "prose verbatim when possible; do not treat it as evidence "
                        "and do not add facts from it. An item may carry "
                        "validated_incumbent_witnesses from the previous attempt. "
                        "Such a witness remains satisfied only while its exact_text "
                        "is preserved verbatim in the repaired draft; the validator "
                        "will recheck and carry that metadata when the response omits "
                        "it. Re-emit a replacement witness whenever those bytes are "
                        "rewritten or removed."
                    ),
                    "instructions": (
                        "The previous provider response was not a complete valid "
                        "JSON object. Return one complete response object matching "
                        "the supplied schema and response_contract. Keep the same "
                        "closed detail/package sets and use only the immutable "
                        "technical_payload. Do not emit Markdown fences, prose "
                        "outside JSON, or truncated strings."
                        if repair_kind == "response_format"
                        else (
                            "The previous response failed witness validation. Keep "
                            "the same closed detail/package sets, rewrite only as "
                            "needed, and include each listed frozen source excerpt "
                            "verbatim in draft_markdown before using it as exact_text. "
                            "For every required_literal_insertion, paste the exact_text "
                            "as a literal code line or code block, preserving every "
                            "comma, quote, bracket, and line break; do not use a "
                            "punctuation variant or merely describe the excerpt. "
                            "Set witness exact_text to the exact substring you pasted. "
                            "Return a complete response object."
                        )
                    ),
                    "items": repair_items,
                }
    return payload


def render_consumer_page_prompt(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
    repair_feedback: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Render the deterministic prompt whose digest is frozen in the plan.

    The structured page is sent separately as ``LLMRequest.input_payload``.
    The V2 Realizer system prompt therefore carries only the role contract;
    repeating the full technical page here would double-count every page byte
    in the run-wide input budget without adding authority.
    """

    if str(role) == "formalizer":
        return (
            "You are the unified V2 Formalizer. Use only the user JSON technical_payload "
            "as evidence. Return one JSON object matching the supplied response schema. "
            "For every task_id, return exactly one results entry with obligation_id equal "
            "to that exact task_id; never omit, duplicate or invent an ID. Derive latex "
            "from the supplied operations and explain it in prose_explanation. The latex "
            "field must preserve every source-derived predicate exactly as written in the "
            "technical_payload, including compound predicates such as 'RESHAPE -> WRITE', "
            "and must contain every listed operand token (including dotted or underscored "
            "identifiers and the result variable); do not replace those tokens with a "
            "natural-language paraphrase. Define symbol_definitions as pairs [symbol, "
            "meaning]; material_conditions and assumptions are arrays of strings. Preserve "
            "branch conditions, operands, normalization and reductions. Do not assert "
            "unresolved configuration values or invent implementation facts. Return no "
            "source-status or authority fields. "
            + ("This is a bounded repair of the specified obligation. " if is_repair else "")
        )

    if str(role) == "realizer":
        prompt = (
            "You are the unified V2 Mechanism Realizer. Read the user JSON "
            "payload as the sole technical authority. Return exactly one JSON "
            "object matching the supplied response schema and response_contract. "
            "Write only evidence-bound draft_markdown; render every required "
            "detail ID exactly once and emit every required formula package ID "
            "exactly once in used_formula_package_ids; emit exactly one formula "
            "witness for each required package, using its exact package ID as "
            "target_id and the package's bound frozen literal_source_excerpt from "
            "response_contract as exact_text; never use the package ID itself as "
            "formula exact_text; "
            "use only allowed atom target IDs; every "
            "exact_text must be a verbatim substring of draft_markdown. Preserve "
            "unresolved conditional branches and never assert an unresolved "
            "configuration value."
        )
        if repair_feedback:
            repair_contract = build_consumer_request_payload(
                page=page,
                role=role,
                task_ids=task_ids,
                section_id=section_id,
                is_repair=is_repair,
                repair_feedback=repair_feedback,
            ).get("response_contract", {}).get("bounded_content_repair")
            if repair_contract:
                if repair_contract.get("repair_kind") == "response_format":
                    prompt += (
                        " This is one bounded response-format repair attempt. "
                        "Return one complete JSON object only; preserve the same "
                        "closed detail/package sets and use only the immutable "
                        "technical_payload. Do not emit Markdown fences, prose "
                        "outside JSON, or a truncated object. Repair contract: "
                        + canonical_json_bytes(repair_contract).decode("utf-8")
                    )
                else:
                    prompt += (
                        " This is one bounded content-repair attempt. Correct the "
                        "listed witness failures, copy the listed frozen excerpts "
                        "verbatim into draft_markdown. For each required literal "
                        "insertion, paste the exact excerpt as a code line/block, "
                        "including trailing punctuation, then set exact_text to that "
                        "literal substring. Self-check every exact_text substring "
                        "before returning. Repair contract: "
                        + canonical_json_bytes(repair_contract).decode("utf-8")
                    )
        return prompt

    if str(role) == "writer":
        # The immutable page is the user payload, not part of the system
        # prompt.  The production Writer uses this same default contract
        # through ``build_publication_writer_request``; serializing the page
        # here as well made plan-time accounting measure it twice and made
        # the frozen prompt digest disagree with the actual request.
        from code2paper.llm.section_writer import default_section_system_prompt

        prompt = default_section_system_prompt()
        if is_repair:
            prompt += (
                " This is a bounded repair attempt for the same immutable page. "
                "Preserve accepted paragraph prose and repair only the listed "
                "content or binding defects."
            )
        return prompt

    # Unknown roles remain fail-closed and deterministic, but do not silently
    # reintroduce the full technical page into a role's prompt.  The payload
    # is always carried once through ``LLMRequest.input_payload``.
    return (
        f"You are the unified V2 {str(role).strip() or 'consumer'}. "
        "Read the user JSON technical_payload as the sole technical authority "
        "and return exactly one object matching the supplied response schema."
    )


def consumer_request_envelope_digest(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
    repair_feedback: Sequence[Mapping[str, Any]] | None = None,
    request_payload: Mapping[str, Any] | None = None,
    rendered_prompt: str | None = None,
    response_schema: Mapping[str, Any] | None = None,
) -> str:
    """Compute the exact role-specific envelope digest used by execution."""

    payload = (
        dict(request_payload)
        if request_payload is not None
        else build_consumer_request_payload(
            page=page,
            role=role,
            task_ids=task_ids,
            section_id=section_id,
            is_repair=is_repair,
            repair_feedback=repair_feedback,
        )
    )
    prompt = (
        str(rendered_prompt)
        if rendered_prompt is not None
        else render_consumer_page_prompt(
            page=page,
            role=role,
            task_ids=task_ids,
            section_id=section_id,
            is_repair=is_repair,
            repair_feedback=repair_feedback,
        )
    )
    schema = (
        dict(response_schema)
        if response_schema is not None
        else consumer_response_json_schema(role, section_id=section_id)
    )
    schema_digest = (
        sha256_digest(canonical_json_bytes(schema))
        if response_schema is not None
        else _request_schema_digest(role, section_id=section_id)
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
        response_schema_digest=schema_digest,
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
        updates: dict[str, Any] = {"max_output_tokens": ceiling}
        # The V2 Realizer is a bounded structured-output serializer.  Its
        # technical reasoning must come from the immutable page payload, and
        # allowing an unbounded provider-side thinking lane can consume the
        # frozen output ceiling before the JSON object is closed.  Keep the
        # Formalizer's configured reasoning policy unchanged; only the
        # Realizer is forced into the already-supported no-thinking mode.
        if str(getattr(invocation, "role", "")) == "realizer":
            updates.update({
                "reasoning_effort": "none",
                "thinking_token_budget": None,
            })
        return base_config.model_copy(update=updates)
    raise UnifiedCompilerError(
        UNIFIED_INVOCATION_BUDGET_MISSING,
        "consumer LLM config must support immutable model_copy",
    )


def _repage_budget_failure_code(plan_revision: int, *, exceeded: bool) -> str | None:
    """拆页后预算不足时给出可解释的失败码（方案 §8.5）。

    ``plan_revision > 1`` 表示这次 plan 是分页/修订后的版本；此时越过 whole-run
    预算必须报 ``run_budget_insufficient_after_repage``，而不是让调用方以为只是
    普通超预算、更不能以"只是拆页"为由截掉剩余页。
    """

    if not exceeded:
        return None
    try:
        revision = int(plan_revision)
    except (TypeError, ValueError):
        revision = 1
    return (
        UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE
        if revision > 1
        else UNIFIED_INVOCATION_BUDGET_EXCEEDED
    )


def build_consumer_invocation_plan_v1(
    manifest: ConsumerWorksetManifestV2,
    envelope: RunInvocationBudgetEnvelopeV1,
    *,
    phase: INVOCATION_PHASE = "formalizer",
    parent_plan: ConsumerInvocationPlanV1 | None = None,
    parent_active_invocation_ids: Sequence[str] | None = None,
    plan_revision: int = 1,
    profile_digest: str,
    model_identity_digest: str,
    model_context_tokens: int,
    max_attempts: int = 2,
    tokenizer: Any | None = None,
    request_material_by_invocation: Mapping[str, Mapping[str, Any]] | None = None,
) -> ConsumerInvocationPlanV1:
    """Freeze the actual per-phase call plan; one invocation consumes one page.

    Formalizer repair invocations are pre-declared as conditional slots (one
    per obligation) with dependencies on the owning main invocation; runtime
    activates at most ``formalizer_repair_call_limit`` of them.  When a child
    phase supplies ``parent_active_invocation_ids``, only those parent slots
    (plus explicit non-invocation retry headroom) are inherited into the
    child reservation.  The parent plan itself is never rewritten.

    R6: every reserve the plan uses comes from the frozen envelope.  This
    function no longer accepts independent reserve maps, so admission and the
    actual send cannot drift onto two unaware thresholds.
    """

    if int(model_context_tokens) <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            "model_context_tokens must be positive",
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
    safety_margin_tokens = int(envelope.safety_margin_tokens)

    def _request_material(invocation_id: str) -> Mapping[str, Any] | None:
        if request_material_by_invocation is None:
            return None
        material = request_material_by_invocation.get(str(invocation_id))
        if material is None:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                f"request material missing for planned invocation {invocation_id}",
            )
        return material

    def _material_digest_kwargs(
        material: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if material is None:
            return {}
        return {
            "request_payload": material.get("input_payload"),
            "rendered_prompt": material.get("rendered_prompt"),
            "response_schema": material.get("response_schema"),
        }

    invocations: list[ConsumerInvocationV1] = []
    workset_index = {workset.workset_id: workset for workset in manifest.worksets}
    page_index = manifest._page_index()  # noqa: SLF001 - same-package compiler
    worksets_by_page: dict[str, list[Any]] = {}
    for workset in manifest.worksets:
        for page_id in workset.required_page_ids:
            worksets_by_page.setdefault(str(page_id), []).append(workset)

    join_page_by_obligation: dict[str, str] = {}
    for page in manifest.pages:
        if page.page_kind != "join":
            continue
        payload = page.technical_payload
        obligation_id = str(payload.get("repair_obligation_id", "")).strip()
        page_worksets = worksets_by_page.get(str(page.page_id), [])
        task_kinds = {
            str(getattr(workset, "task_kind", "")) for workset in page_worksets
        }
        dependency_proof = payload.get("join_dependency_proof")
        if not obligation_id:
            # R7/F3: a section join page is a legal multi-mechanism
            # Writer/Realizer page.  It proves section/paragraph dependency,
            # not a formula repair, so it must not be forced to carry a
            # repair obligation ID.  Anything that is neither a repair page
            # nor a proven section join page fails closed.
            section_join = (
                "section" in task_kinds
                and isinstance(dependency_proof, Mapping)
                and bool(str(payload.get("section_id", "")).strip())
            )
            if not section_join:
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"join page {page.page_id} has neither a repair obligation "
                    "ID nor a section dependency proof",
                )
            declared_mechanisms = tuple(
                sorted(
                    str(value)
                    for value in (dependency_proof.get("mechanism_ids", ()) or ())
                    if str(value).strip()
                )
            )
            proof_atoms = tuple(
                str(value)
                for value in (dependency_proof.get("atom_ids", ()) or ())
            )
            if (
                not declared_mechanisms
                or proof_atoms != tuple(page.atom_ids)
                or sorted(declared_mechanisms)
                != sorted(
                    str(value)
                    for value in (
                        payload.get("mechanism_header", {}).get("mechanism_ids", ())
                        or ()
                    )
                    if str(value).strip()
                )
            ):
                raise UnifiedCompilerError(
                    UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                    f"section join page {page.page_id} has an inconsistent "
                    "dependency proof",
                )
            continue
        if "section" in task_kinds:
            raise UnifiedCompilerError(
                UNIFIED_PAGE_PROJECTION_INCOMPLETE,
                f"section join page {page.page_id} must not claim a formula "
                "repair obligation",
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
                material = _request_material(invocation_id)
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
                        **_material_digest_kwargs(material),
                    ),
                    max_input_tokens=_plan_invocation_token_accounting(
                        page=page,
                        role="formalizer",
                        task_ids=obligation_ids,
                        envelope=envelope,
                        tokenizer=tokenizer,
                        request_material=material,
                    ).input_tokens,
                    max_output_tokens=_role_output_reserve(envelope, "formalizer"),
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
                material = _request_material(repair_invocation_id)
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
                        **_material_digest_kwargs(material),
                    ),
                    max_input_tokens=_plan_invocation_token_accounting(
                        page=page,
                        role="formalizer",
                        task_ids=(str(obligation_id),),
                        is_repair=True,
                        envelope=envelope,
                        tokenizer=tokenizer,
                        request_material=material,
                    ).input_tokens,
                    max_output_tokens=_role_output_reserve(envelope, "formalizer"),
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
                material = _request_material(invocation_id)
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
                        **_material_digest_kwargs(material),
                    ),
                    max_input_tokens=_plan_invocation_token_accounting(
                        page=page,
                        role=phase,
                        task_ids=workset.task_ids,
                        section_id=workset.section_id,
                        envelope=envelope,
                        tokenizer=tokenizer,
                        request_material=material,
                    ).input_tokens,
                    max_output_tokens=_role_output_reserve(envelope, phase),
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
    if parent_plan is not None and parent_active_invocation_ids is not None:
        # Conditional parent slots are declarations, not spend.  A repair
        # slot only becomes part of the downstream run reservation after the
        # Formalizer actually starts it (or leaves it unsettled).  Preserve
        # the immutable parent plan/digest, but project its active invocation
        # reservation into this child plan so a preferred, never-triggered
        # repair cannot starve Writer/Realizer admission.
        active_parent_ids = {
            str(invocation_id).strip()
            for invocation_id in parent_active_invocation_ids
            if str(invocation_id).strip()
        }
        parent_invocations = tuple(
            getattr(parent_plan, "invocations", ()) or ()
        )
        parent_invocation_ids = {
            str(invocation.invocation_id) for invocation in parent_invocations
        }
        unknown_parent_ids = active_parent_ids - parent_invocation_ids
        if unknown_parent_ids:
            raise UnifiedCompilerError(
                UNIFIED_INVOCATION_BUDGET_MISSING,
                "active parent invocation IDs are not in the parent plan: "
                + ",".join(sorted(unknown_parent_ids)[:8]),
            )
        parent_all_tokens: dict[str, int] = {}
        parent_extra_tokens: dict[str, int] = {}
        for invocation in parent_invocations:
            role = str(invocation.role)
            parent_all_tokens[role] = (
                parent_all_tokens.get(role, 0)
                + int(invocation.max_input_tokens)
            )
        for role, reserved in (
            getattr(parent_plan, "reserved_input_tokens_by_role", {}) or {}
        ).items():
            # Retry headroom is not attached to an invocation.  Keep that
            # explicit reserve while replacing only the parent invocation
            # portion with the active subset.
            parent_extra_tokens[str(role)] = max(
                0,
                int(reserved)
                - int(parent_all_tokens.get(str(role), 0) or 0),
            )
        reserved_calls = {}
        reserved_tokens = dict(parent_extra_tokens)
        for invocation in parent_invocations:
            if str(invocation.invocation_id) not in active_parent_ids:
                continue
            role = str(invocation.role)
            reserved_calls[role] = reserved_calls.get(role, 0) + 1
            reserved_tokens[role] = (
                reserved_tokens.get(role, 0)
                + int(invocation.max_input_tokens)
            )
    else:
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
        # A retry reserve is explicit profile budget, not an implicit second
        # copy of every invocation.  It is added once when that role's phase
        # first enters the run lineage; every attempt still spends measured
        # input from this same durable reservation.
        retry_reserve = int(
            getattr(envelope, "retry_reserve_input_tokens_by_role", {})
            .get(role, 0)
            or 0
        )
        reserved_tokens[role] += retry_reserve

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
        reservation_contract="atomic_debit_v1",
    )


def _role_request_budget(
    envelope: RunInvocationBudgetEnvelopeV1,
    role: str,
) -> RoleRequestBudgetV1:
    budget = envelope.request_budget_by_role.get(str(role))
    if budget is None:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            f"role {role} has no declared request budget in the run envelope",
        )
    return budget


def _role_output_reserve(
    envelope: RunInvocationBudgetEnvelopeV1,
    role: str,
) -> int:
    return int(_role_request_budget(envelope, role).output_token_reserve)


def _plan_invocation_token_accounting(
    *,
    page: ConsumerTechnicalPageV2,
    role: str,
    task_ids: Sequence[str],
    section_id: str = "",
    is_repair: bool = False,
    envelope: RunInvocationBudgetEnvelopeV1,
    tokenizer: Any | None = None,
    request_material: Mapping[str, Any] | None = None,
) -> UnifiedRequestTokenAccountingV1:
    """Measure one planned request exactly as the actual send will be measured.

    The plan no longer estimates a request from the page's atom-sum proxy.  It
    measures the rendered prompt, the canonical payload, the closed response
    schema and the declared wrapper reserve with the envelope's own meter, so
    plan admission and the caller boundary cannot disagree about what fits.
    """

    budget = _role_request_budget(envelope, role)
    request_cap = int(envelope.max_request_input_tokens_by_role.get(str(role), -1))
    if request_cap <= 0:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_MISSING,
            f"role {role} has no declared per-request input cap",
        )
    payload = (
        dict(request_material.get("input_payload") or {})
        if request_material is not None
        else build_consumer_request_payload(
            page=page,
            role=role,
            task_ids=task_ids,
            section_id=section_id,
            is_repair=is_repair,
        )
    )
    prompt = (
        str(request_material.get("rendered_prompt") or "")
        if request_material is not None
        else render_consumer_page_prompt(
            page=page,
            role=role,
            task_ids=task_ids,
            section_id=section_id,
            is_repair=is_repair,
        )
    )
    response_schema = (
        dict(request_material.get("response_schema") or {})
        if request_material is not None
        else consumer_response_json_schema(role, section_id=section_id)
    )
    accounting = account_unified_request_tokens(
        consumer_role=role,
        request_budget=budget,
        max_input_tokens=request_cap,
        model_context_tokens=int(envelope.model_context_tokens),
        safety_margin_tokens=int(envelope.safety_margin_tokens),
        meter=envelope.token_meter,
        rendered_prompt=prompt,
        input_payload=payload,
        response_schema=response_schema,
        tokenizer=tokenizer,
        page_id=str(page.page_id),
    )
    if not accounting.fits:
        raise UnifiedCompilerError(
            UNIFIED_INVOCATION_BUDGET_EXCEEDED,
            f"planned {role} request needs {accounting.input_tokens} input tokens "
            f"with output {accounting.output_reserve_tokens} and thinking "
            f"{accounting.thinking_reserve_tokens} against a declared per-request "
            f"cap of {request_cap} and a {accounting.model_context_tokens}-token "
            f"context window",
        )
    return accounting


def remaining_run_input_tokens(
    *,
    reserved_input_tokens_by_role: Mapping[str, int],
    spent_input_tokens_by_role: Mapping[str, int],
    role: str,
) -> int:
    """Return the input budget left for one more request of ``role``.

    The plan's reservation is a run-level token budget.  Retries and resumed
    attempts debit the same reservation, so the bound is enforced from the
    durable receipts rather than from a post-hoc calibration.
    """

    reserved = int(reserved_input_tokens_by_role.get(str(role), 0) or 0)
    spent = int(spent_input_tokens_by_role.get(str(role), 0) or 0)
    return reserved - spent


def spend_input_tokens_by_role(
    receipts: Iterable[Any],
    *,
    plan_digests: Iterable[str] = (),
) -> dict[str, int]:
    """Sum measured input tokens that actually crossed the caller boundary.

    Only receipts belonging to the given plans (or, when none are supplied,
    every receipt) are counted, so a phase revision starts from its own
    reservation instead of inheriting an unrelated plan's spend.  A measured
    pre-send rejection remains in its receipt for auditability but contributes
    no provider spend.
    """

    allowed = {str(value) for value in plan_digests if str(value)}
    spent: dict[str, int] = {}
    for receipt in receipts or ():
        if allowed:
            receipt_plan = str(
                getattr(receipt, "upstream_plan_digest", "")
                or (
                    receipt.get("upstream_plan_digest", "")
                    if isinstance(receipt, Mapping) else ""
                )
            )
            if receipt_plan not in allowed:
                continue
        role = str(
            getattr(receipt, "consumer_role", "")
            or (
                receipt.get("consumer_role", "")
                if isinstance(receipt, Mapping) else ""
            )
        )
        accounting = getattr(receipt, "token_accounting", None)
        if accounting is None and isinstance(receipt, Mapping):
            accounting = receipt.get("token_accounting")
        if not role or accounting is None:
            continue
        sent_to_caller = getattr(receipt, "sent_to_caller", True)
        if isinstance(receipt, Mapping):
            sent_to_caller = receipt.get("sent_to_caller", True)
        if not bool(sent_to_caller):
            continue
        tokens = int(
            getattr(accounting, "input_tokens", 0)
            or (
                accounting.get("input_tokens", 0)
                if isinstance(accounting, Mapping) else 0
            )
            or 0
        )
        def field(name: str, default: Any = None) -> Any:
            return receipt.get(name, default) if isinstance(receipt, Mapping) else getattr(receipt, name, default)
        usage = field("provider_usage")
        provider_input = (usage or {}).get("prompt_tokens", (usage or {}).get("input_tokens"))
        if provider_input is not None:
            # Retain the estimate as a floor when it is more conservative.
            tokens = max(tokens, int(provider_input))
        spent[role] = spent.get(role, 0) + tokens
    return spent


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
                if str(seed_id).strip() and not str(seed_id).startswith("story:")
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
    request_material_by_invocation: Mapping[str, Mapping[str, Any]] | None = None,
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

    def _admission_material(invocation_id: str) -> Mapping[str, Any] | None:
        if request_material_by_invocation is None:
            return None
        material = request_material_by_invocation.get(str(invocation_id))
        if material is None:
            formula_gate_failures.append(
                f"unified_request_material_missing:{invocation_id}"
            )
        return material

    def _material_digest_kwargs(
        material: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if material is None:
            return {}
        return {
            "request_payload": material.get("input_payload"),
            "rendered_prompt": material.get("rendered_prompt"),
            "response_schema": material.get("response_schema"),
        }

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
                **_material_digest_kwargs(_admission_material(invocation.invocation_id)),
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
                **_material_digest_kwargs(_admission_material(invocation.invocation_id)),
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
            invocation_gate_failures.append(f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:calls:{role}:{calls}>{limit}")
            repage_code = _repage_budget_failure_code(
                plan.plan_revision, exceeded=limit >= 0
            )
            if repage_code == UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE:
                invocation_gate_failures.append(
                    f"{repage_code}:calls:{role}:{calls}>{limit}"
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
        repage_code = _repage_budget_failure_code(plan.plan_revision, exceeded=True)
        if repage_code == UNIFIED_RUN_BUDGET_INSUFFICIENT_AFTER_REPAGE:
            invocation_gate_failures.append(
                f"{repage_code}:total_input_tokens:"
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
        # R6: the per-request cap and the role output budget are part of the
        # admitted contract, so a plan cannot promise more than the envelope.
        request_cap = int(
            envelope.max_request_input_tokens_by_role.get(invocation.role, -1)
        )
        if request_cap <= 0:
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_MISSING}:request_cap:{invocation.invocation_id}"
            )
        elif invocation.max_input_tokens > request_cap:
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:request_input_tokens:"
                f"{invocation.invocation_id}:{invocation.max_input_tokens}>{request_cap}"
            )
        role_budget = envelope.request_budget_by_role.get(invocation.role)
        if role_budget is None:
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_MISSING}:role_budget:{invocation.invocation_id}"
            )
        elif int(invocation.max_output_tokens) != int(role_budget.output_token_reserve):
            invocation_gate_failures.append(
                f"{UNIFIED_INVOCATION_BUDGET_EXCEEDED}:output_tokens:"
                f"{invocation.invocation_id}:{invocation.max_output_tokens}"
                f"!={role_budget.output_token_reserve}"
            )
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
    "fit_narrative_plan_to_page_budget",
    "remaining_run_input_tokens",
    "spend_input_tokens_by_role",
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
