"""Fail-closed terminal proof for Research obligations.

Status strings are mutable scheduling state.  This module is the single
deterministic proof boundary used when a caller needs to decide whether an
obligation may leave the research queue.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json


class ResearchClosureAdmissionV1(BaseModel):
    """Research-to-authoring pre-admission, persisted before model calls.

    This is deliberately smaller than a Formalizer/Writer admission: those
    phases may not have been planned when Research is blocked, so their phase
    artifacts are not fabricated as placeholders.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    admission_id: str
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    research_status: str
    model_calls_allowed: bool = False
    # Candidate is a deliberately separate, weaker downstream lane.  It may
    # consume a bounded partial handoff, while the same admission continues
    # to report the strict failures that keep Verified closed.
    candidate_handoff_allowed: bool = False
    candidate_handoff_id: str = ""
    candidate_warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    downstream_phases_planned: tuple[str, ...] = Field(default_factory=tuple)
    failure_codes: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ResearchClosureAdmissionV1":
        if not self.admission_id.strip() or not self.run_id.strip():
            raise ValueError("research closure admission requires admission and run ids")
        if not self.repo_snapshot_id.strip() or not self.project_tree_hash.strip():
            raise ValueError("research closure admission requires snapshot identity")
        if self.failure_codes and self.model_calls_allowed and not self.candidate_handoff_allowed:
            raise ValueError("failed research closure cannot allow model calls")
        if self.candidate_handoff_allowed and not self.candidate_handoff_id.strip():
            raise ValueError("candidate handoff requires a handoff id")
        if self.candidate_handoff_allowed and not self.model_calls_allowed:
            raise ValueError("candidate handoff must allow its downstream model lane")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("research closure admission content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def build_research_closure_admission(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    research_status: str,
    failure_codes: Iterable[str] = (),
    downstream_phases_planned: Iterable[str] = (),
    candidate_handoff_allowed: bool = False,
    candidate_handoff_id: str = "",
    candidate_warning_codes: Iterable[str] = (),
) -> ResearchClosureAdmissionV1:
    """Create the single gate between Research and model-backed authoring."""

    failures = tuple(dict.fromkeys(
        str(value).strip() for value in failure_codes if str(value).strip()
    ))
    candidate_allowed = bool(candidate_handoff_allowed)
    handoff_id = str(candidate_handoff_id or "").strip()
    warnings = tuple(dict.fromkeys(
        str(value).strip()
        for value in candidate_warning_codes
        if str(value).strip()
    ))
    status = str(research_status or "incomplete").strip() or "incomplete"
    return ResearchClosureAdmissionV1(
        admission_id=digest_json({
            "run_id": run_id,
            "repo_snapshot_id": repo_snapshot_id,
            "project_tree_hash": project_tree_hash,
            "research_status": status,
            "failure_codes": failures,
            "candidate_handoff_allowed": candidate_allowed,
            "candidate_handoff_id": handoff_id,
            "candidate_warning_codes": warnings,
        }),
        run_id=str(run_id or "").strip(),
        repo_snapshot_id=str(repo_snapshot_id or "").strip(),
        project_tree_hash=str(project_tree_hash or "").strip(),
        research_status=status,
        model_calls_allowed=not failures or candidate_allowed,
        candidate_handoff_allowed=candidate_allowed,
        candidate_handoff_id=handoff_id,
        candidate_warning_codes=warnings,
        downstream_phases_planned=tuple(dict.fromkeys(
            str(value).strip()
            for value in downstream_phases_planned
            if str(value).strip()
        )),
        failure_codes=failures,
    )


CandidateUnresolvedFieldType = Literal[
    "call_relation",
    "source_span",
    "parameter",
    "numeric",
    "formula",
    "control_flow",
    "configuration",
    "lineage",
    "ownership",
    "qualifier",
    "other",
]


class CandidateUnresolvedFieldV1(BaseModel):
    """Typed unresolved information carried by a partial Candidate item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    field_type: CandidateUnresolvedFieldType = "other"
    description: str

    @model_validator(mode="after")
    def _valid(self) -> "CandidateUnresolvedFieldV1":
        if not self.field_id.strip() or not self.description.strip():
            raise ValueError("candidate unresolved field requires id and description")
        return self


class CandidateClaimBindingV1(BaseModel):
    """Exact frozen claim surface consumed by the Candidate lane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    obligation_id: str
    canonical_identity: str
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    direct_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    required_qualifiers: tuple[str, ...] = Field(default_factory=tuple)
    allowed_wording_boundary: str = ""
    claim_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "CandidateClaimBindingV1":
        if not self.claim_id.strip() or not self.obligation_id.strip():
            raise ValueError("candidate claim binding requires ids")
        if not self.canonical_identity.strip():
            raise ValueError("candidate claim binding requires canonical identity")
        if not self.fact_ids:
            raise ValueError("candidate claim binding requires fact lineage")
        if not (self.direct_evidence_ids or self.relation_evidence_ids):
            raise ValueError("candidate claim binding requires evidence lineage")
        if not self.allowed_wording_boundary.strip():
            raise ValueError("candidate claim binding requires wording boundary")
        expected = digest_json(self.model_dump(mode="json", exclude={"claim_digest"}))
        if self.claim_digest and self.claim_digest != expected:
            raise ValueError("candidate claim binding digest mismatch")
        object.__setattr__(self, "claim_digest", expected)
        return self


class CandidateRetryLedgerV1(BaseModel):
    """Frozen retry ledger used to re-evaluate a Candidate handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    post_partial_retry_counts: dict[str, int] = Field(default_factory=dict)
    semantic_gain_by_obligation: dict[str, bool | None] = Field(default_factory=dict)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "CandidateRetryLedgerV1":
        if not self.run_id.strip() or not self.repo_snapshot_id.strip():
            raise ValueError("candidate retry ledger requires run identity")
        if not self.project_tree_hash.strip():
            raise ValueError("candidate retry ledger requires project tree hash")
        if any(int(value) < 0 for value in self.post_partial_retry_counts.values()):
            raise ValueError("candidate retry count cannot be negative")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            raise ValueError("candidate retry ledger content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self


def build_candidate_retry_ledger(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    post_partial_retry_counts: Mapping[str, int] | None = None,
    semantic_gain_by_obligation: Mapping[str, bool | None] | None = None,
) -> CandidateRetryLedgerV1:
    """Build the immutable retry surface shared by Research and Writer."""

    return CandidateRetryLedgerV1(
        run_id=str(run_id or "").strip(),
        repo_snapshot_id=str(repo_snapshot_id or "").strip(),
        project_tree_hash=str(project_tree_hash or "").strip(),
        post_partial_retry_counts={
            str(key): max(0, int(value or 0))
            for key, value in (post_partial_retry_counts or {}).items()
            if str(key).strip()
        },
        semantic_gain_by_obligation={
            str(key): value
            for key, value in (semantic_gain_by_obligation or {}).items()
            if str(key).strip()
        },
    )


class CandidatePartialHandoffV1(BaseModel):
    """One partial obligation carried into the Candidate/review lane.

    This is not a terminal proof.  In particular, an unresolved field is
    retained instead of being rewritten as an explicit repository gap.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    promoted_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    missing_fields: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_fields: tuple[CandidateUnresolvedFieldV1, ...] = Field(default_factory=tuple)
    qualifier: str = ""
    allowed_wording_boundary: str = ""
    qualifier_clear: bool = False
    post_partial_retry_count: int = 0
    semantic_gain_on_retry: bool | None = None
    review_warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    promoted_claim_bindings: tuple[CandidateClaimBindingV1, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _valid(self) -> "CandidatePartialHandoffV1":
        if not self.obligation_id.strip():
            raise ValueError("candidate partial handoff requires an obligation id")
        if self.post_partial_retry_count < 0:
            raise ValueError("candidate partial retry count cannot be negative")
        if not self.missing_fields or not self.unresolved_fields:
            raise ValueError(
                "candidate partial handoff requires typed unresolved fields"
            )
        if tuple(field.description for field in self.unresolved_fields) != self.missing_fields:
            raise ValueError("candidate unresolved fields do not match missing_fields")
        if not self.qualifier.strip():
            raise ValueError(
                "candidate partial handoff requires an explicit qualifier"
            )
        if not self.allowed_wording_boundary.strip():
            raise ValueError(
                "candidate partial handoff requires an allowed wording boundary"
            )
        if not self.qualifier_clear:
            raise ValueError(
                "candidate partial handoff requires a closed qualifier contract"
            )
        if self.promoted_claim_bindings:
            binding_ids = tuple(binding.claim_id for binding in self.promoted_claim_bindings)
            if binding_ids != self.promoted_claim_ids:
                raise ValueError("candidate claim bindings do not match promoted claim ids")
            if any(
                binding.obligation_id != self.obligation_id
                for binding in self.promoted_claim_bindings
            ):
                raise ValueError("candidate claim binding obligation mismatch")
        return self


class CandidateHandoffV1(BaseModel):
    """Independent Research -> Candidate handoff contract.

    ``eligible`` only means that the minimum Candidate lane is safe to
    consume.  It never changes ``ObligationTerminalProofV1`` and therefore
    cannot authorize a repository-verified result.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    handoff_id: str
    run_id: str
    repo_snapshot_id: str
    project_tree_hash: str
    eligible: bool = False
    eligibility_reasons: tuple[str, ...] = Field(default_factory=tuple)
    must_cover_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    supported_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    partial_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    partial_obligations: tuple[CandidatePartialHandoffV1, ...] = Field(default_factory=tuple)
    deferred_obligation_ids: tuple[str, ...] = Field(default_factory=tuple)
    structural_failure_codes: tuple[str, ...] = Field(default_factory=tuple)
    warning_codes: tuple[str, ...] = Field(default_factory=tuple)
    agenda_digest: str = ""
    promotion_ledger_digest: str = ""
    retry_ledger_digest: str = ""
    # R10 (§15.6): the research revision this handoff was built under.  A
    # handoff may not stay usable once a newer revision changed the targets.
    revision_id: str = ""
    claim_bindings: tuple[CandidateClaimBindingV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "CandidateHandoffV1":
        if not self.handoff_id.strip() or not self.run_id.strip():
            raise ValueError("candidate handoff requires identity")
        if not self.repo_snapshot_id.strip() or not self.project_tree_hash.strip():
            raise ValueError("candidate handoff requires snapshot identity")
        if self.eligible and self.eligibility_reasons:
            # Warnings are allowed, but an eligibility reason is a blocker.
            raise ValueError("eligible candidate handoff cannot contain eligibility reasons")
        if self.eligible and self.structural_failure_codes:
            raise ValueError("eligible candidate handoff cannot contain structural failures")
        if self.eligible and not (
            self.agenda_digest.strip()
            and self.promotion_ledger_digest.strip()
            and self.retry_ledger_digest.strip()
        ):
            raise ValueError("eligible candidate handoff requires frozen source digests")
        partial_ids = tuple(item.obligation_id for item in self.partial_obligations)
        if partial_ids != self.partial_obligation_ids:
            raise ValueError("candidate partial obligation ids do not match payload")
        binding_keys = tuple(
            (binding.obligation_id, binding.claim_id)
            for binding in self.claim_bindings
        )
        if len(binding_keys) != len(set(binding_keys)):
            raise ValueError("candidate handoff contains duplicate claim bindings")
        expected_handoff_id = digest_json(
            self.model_dump(mode="json", exclude={"handoff_id", "content_digest"})
        )
        # R10 added ``revision_id`` to the handoff identity.  A pre-R10 handoff
        # (no revision id) keeps its original content address so frozen
        # artifacts stay readable; once a revision id is present it must bind.
        legacy_handoff_id = ""
        legacy_content_digest = ""
        if not self.revision_id:
            legacy_handoff_id = digest_json(self.model_dump(
                mode="json",
                exclude={"handoff_id", "content_digest", "revision_id"},
            ))
            legacy_content_digest = digest_json(self.model_dump(
                mode="json", exclude={"content_digest", "revision_id"}
            ))
        if self.handoff_id != expected_handoff_id and (
            not legacy_handoff_id or self.handoff_id != legacy_handoff_id
        ):
            raise ValueError("candidate handoff handoff_id mismatch")
        expected = digest_json(self.model_dump(mode="json", exclude={"content_digest"}))
        if self.content_digest and self.content_digest != expected:
            if not legacy_content_digest or (
                self.content_digest != legacy_content_digest
            ):
                raise ValueError("candidate handoff content_digest mismatch")
            # Legacy payload: keep its original digest instead of rewriting it.
            return self
        object.__setattr__(self, "content_digest", expected)
        return self


def handoff_payload_identity(handoff: CandidateHandoffV1) -> str:
    """Digest a handoff's *content*, independent of the digest scheme.

    R10 added ``revision_id`` to the handoff identity, which shifts both the
    id and the content digest of an otherwise unchanged handoff.  A consumer
    that recomputes a handoff from frozen inputs compares this normalized
    identity instead, so a pre-R10 artifact (empty revision id) stays
    verifiable while a real revision id remains bound.
    """

    payload = handoff.model_dump(
        mode="json", exclude={"handoff_id", "content_digest"}
    )
    if not str(payload.get("revision_id") or ""):
        payload.pop("revision_id", None)
    return digest_json(payload)


def handoff_address_variants(
    handoff: CandidateHandoffV1,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the accepted ``(handoff_id, content_digest)`` spellings.

    R10 added ``revision_id`` to the handoff identity; a handoff without one
    keeps its pre-R10 content address so a frozen artifact stays verifiable.
    Consumers compare against both spellings instead of re-implementing the
    legacy rule.
    """

    ids = [digest_json(
        handoff.model_dump(mode="json", exclude={"handoff_id", "content_digest"})
    )]
    digests = [digest_json(
        handoff.model_dump(mode="json", exclude={"content_digest"})
    )]
    if not handoff.revision_id:
        ids.append(digest_json(handoff.model_dump(
            mode="json", exclude={"handoff_id", "content_digest", "revision_id"}
        )))
        digests.append(digest_json(handoff.model_dump(
            mode="json", exclude={"content_digest", "revision_id"}
        )))
    return tuple(dict.fromkeys(ids)), tuple(dict.fromkeys(digests))


def build_candidate_handoff(
    *,
    run_id: str,
    repo_snapshot_id: str,
    project_tree_hash: str,
    agenda_items: Iterable[Any],
    promotion_records: Iterable[Any] = (),
    compiled_claim_ids_by_obligation: Mapping[str, Iterable[str]] | None = None,
    compiled_claims_by_obligation: Mapping[str, Iterable[Any]] | None = None,
    post_partial_retry_counts: Mapping[str, int] | None = None,
    retry_gain_by_obligation: Mapping[str, bool | None] | None = None,
    structural_failure_codes: Iterable[str] = (),
    agenda_digest: str = "",
    promotion_ledger_digest: str = "",
    retry_ledger_digest: str = "",
    revision_id: str = "",
) -> CandidateHandoffV1:
    """Evaluate the bounded Candidate lane without weakening strict proofs.

    Every must-cover item must have been attempted.  It then needs either
    promoted supported evidence or promoted partial evidence plus typed
    unresolved fields, an explicit qualifier/wording boundary, and exactly
    the bounded post-partial retry represented by the supplied count.  The
    promoted claim ids must be present in both the promotion ledger and the
    frozen claim objects.  Non-core items are recorded as deferred review
    work.
    """

    items = tuple(agenda_items)
    records = tuple(promotion_records or ())
    compiled_map = compiled_claim_ids_by_obligation or {}
    compiled_claim_map = compiled_claims_by_obligation or {}
    retry_counts = post_partial_retry_counts or {}
    retry_gains = retry_gain_by_obligation or {}
    structural = tuple(dict.fromkeys(
        str(value).strip() for value in structural_failure_codes if str(value).strip()
    ))
    must_cover_ids: list[str] = []
    supported_ids: list[str] = []
    partial_ids: list[str] = []
    partials: list[CandidatePartialHandoffV1] = []
    claim_bindings: list[CandidateClaimBindingV1] = []
    deferred_ids: list[str] = []
    reasons: list[str] = []
    legacy_gap_warnings: list[str] = []

    for item in items:
        obligation_id = str(_value(item, "obligation_id", "") or "").strip()
        if not obligation_id:
            continue
        item_records = tuple(
            record for record in records
            if str(_value(record, "obligation_id", "") or "").strip() == obligation_id
        )
        promoted_claim_ids = tuple(dict.fromkeys(_record_claim_ids(item_records)))
        compiled_claims = tuple(compiled_claim_map.get(obligation_id, ()) or ())
        compiled_claim_ids = tuple(dict.fromkeys(
            str(_value(claim, "claim_id", "") or "").strip()
            for claim in compiled_claims
            if str(_value(claim, "claim_id", "") or "").strip()
        ))
        if not records:
            reasons.append(f"candidate_promotion_ledger_missing:{obligation_id}")
        if promoted_claim_ids and not set(promoted_claim_ids).issubset(
            set(compiled_claim_ids)
        ):
            reasons.append(f"candidate_claim_set_binding_mismatch:{obligation_id}")
        if not promoted_claim_ids:
            promoted_claim_ids = ()
        bindings: list[CandidateClaimBindingV1] = []
        for claim_id in promoted_claim_ids:
            claim = next(
                (
                    value for value in compiled_claims
                    if str(_value(value, "claim_id", "") or "").strip() == claim_id
                ),
                None,
            )
            if claim is None:
                reasons.append(f"candidate_claim_set_missing:{obligation_id}:{claim_id}")
                continue
            covers = {
                str(value).strip()
                for value in (_value(claim, "covers_obligation_ids", ()) or ())
                if str(value).strip()
            }
            if obligation_id not in covers:
                reasons.append(
                    f"candidate_claim_obligation_binding_mismatch:{obligation_id}:{claim_id}"
                )
                continue
            try:
                bindings.append(_candidate_claim_binding(claim, obligation_id))
            except (TypeError, ValueError):
                reasons.append(f"candidate_claim_binding_invalid:{obligation_id}:{claim_id}")
        if len(bindings) != len(promoted_claim_ids):
            reasons.append(f"candidate_claim_binding_incomplete:{obligation_id}")
        claim_bindings.extend(bindings)
        attempted = bool(
            tuple(_value(item, "attempted_actions", ()) or ())
            or item_records
            or str(_value(item, "status", "") or "")
            in {"supported", "partial", "explicit_gap", "blocked"}
        )
        status = str(_value(item, "status", "") or "")
        priority = str(_value(item, "priority", "") or "")
        if priority == "must_cover":
            must_cover_ids.append(obligation_id)
            if not attempted:
                reasons.append(f"candidate_core_unresearched:{obligation_id}")
            retry_count = max(0, int(retry_counts.get(obligation_id, 0) or 0))
            if status == "partial":
                # Keep the bounded-retry diagnosis even when the promotion
                # ledger is incomplete.  Otherwise a missing promotion would
                # hide the fact that the partial lane has not yet consumed
                # its one permitted follow-up transaction.
                if retry_count < 1:
                    reasons.append(f"candidate_partial_retry_missing:{obligation_id}")
                elif retry_count > 1:
                    reasons.append(f"candidate_partial_retry_overrun:{obligation_id}")
            if status == "supported" and promoted_claim_ids:
                if len(bindings) == len(promoted_claim_ids):
                    supported_ids.append(obligation_id)
                else:
                    reasons.append(f"candidate_supported_binding_ineligible:{obligation_id}")
                continue
            if status == "partial" and promoted_claim_ids:
                missing_fields = tuple(dict.fromkeys(
                    str(value).strip()
                    for value in (_value(item, "missing_information", ()) or ())
                    if str(value).strip()
                ))
                unresolved_fields = _typed_unresolved_fields(
                    obligation_id,
                    missing_fields,
                )
                qualifier, wording_boundary = _candidate_qualifier_contract(
                    item,
                    compiled_claims,
                    promoted_claim_ids,
                )
                qualifier_present = bool(qualifier.strip())
                wording_boundary_present = bool(wording_boundary.strip())
                qualifier_clear = qualifier_present and wording_boundary_present
                warnings = [f"candidate_partial_unresolved:{obligation_id}"] if missing_fields else []
                if not missing_fields:
                    reasons.append(f"candidate_partial_missing_fields:{obligation_id}")
                if not qualifier_present:
                    reasons.append(f"candidate_partial_qualifier_missing:{obligation_id}")
                    warnings.append(f"candidate_partial_qualifier_missing:{obligation_id}")
                if not wording_boundary_present:
                    reasons.append(
                        f"candidate_partial_wording_boundary_missing:{obligation_id}"
                    )
                    warnings.append(
                        f"candidate_partial_wording_boundary_missing:{obligation_id}"
                    )
                if not qualifier_clear:
                    reasons.append(f"candidate_partial_qualifier_unresolved:{obligation_id}")
                if (
                    missing_fields
                    and unresolved_fields
                    and qualifier_clear
                    and retry_count == 1
                    and len(bindings) == len(promoted_claim_ids)
                ):
                    partial_ids.append(obligation_id)
                    partials.append(CandidatePartialHandoffV1(
                        obligation_id=obligation_id,
                        promoted_claim_ids=promoted_claim_ids,
                        missing_fields=missing_fields,
                        unresolved_fields=unresolved_fields,
                        qualifier=qualifier,
                        allowed_wording_boundary=wording_boundary,
                        qualifier_clear=qualifier_clear,
                        post_partial_retry_count=retry_count,
                        semantic_gain_on_retry=retry_gains.get(obligation_id),
                        review_warning_codes=tuple(warnings),
                        promoted_claim_bindings=tuple(bindings),
                    ))
                continue
            if status == "explicit_gap" and not _terminal_gap_bound(item):
                # R9 migration: a checkpoint written before the typed terminal
                # contract records ``explicit_gap`` without a ledger-verified
                # receipt.  It is not negative evidence; report the legacy
                # record explicitly so the obligation returns to research
                # instead of entering the Writer as an exhausted gap.
                reasons.append(
                    f"candidate_legacy_explicit_gap_unverified:{obligation_id}"
                )
                legacy_gap_warnings.append(
                    f"candidate_legacy_explicit_gap_unverified:{obligation_id}"
                )
                continue
            reasons.append(f"candidate_core_evidence_ineligible:{obligation_id}")
            continue
        # Candidate does not wait for should-cover/preference/verify-only
        # work.  Preserve it as review/deferred metadata instead.
        if status not in {"supported", "explicit_gap", "blocked"}:
            deferred_ids.append(obligation_id)

    warning_codes = list(structural)
    warning_codes.extend(legacy_gap_warnings)
    warning_codes.extend(
        f"candidate_deferred:{obligation_id}" for obligation_id in deferred_ids
    )
    warning_codes.extend(
        warning for partial in partials for warning in partial.review_warning_codes
    )
    eligibility_reasons = tuple(dict.fromkeys(
        [*reasons, *(
            f"candidate_structural_failure:{value}" for value in structural
        )]
    ))
    source_agenda_digest = str(agenda_digest or "").strip() or digest_json([
        _model_json(item) for item in items
    ])
    source_promotion_digest = str(promotion_ledger_digest or "").strip()
    if not source_promotion_digest and records:
        source_promotion_digest = digest_json([_model_json(record) for record in records])
    retry_ledger = build_candidate_retry_ledger(
        run_id=str(run_id or "").strip(),
        repo_snapshot_id=str(repo_snapshot_id or "").strip(),
        project_tree_hash=str(project_tree_hash or "").strip(),
        post_partial_retry_counts=retry_counts,
        semantic_gain_by_obligation=retry_gains,
    )
    source_retry_digest = str(retry_ledger_digest or "").strip() or retry_ledger.content_digest
    if not source_agenda_digest:
        reasons.append("candidate_agenda_digest_missing")
    if not source_promotion_digest:
        reasons.append("candidate_promotion_ledger_digest_missing")
    if not source_retry_digest:
        reasons.append("candidate_retry_ledger_digest_missing")
    eligibility_reasons = tuple(dict.fromkeys(
        [*reasons, *(
            f"candidate_structural_failure:{value}" for value in structural
        )]
    ))
    eligible = bool(must_cover_ids) and not eligibility_reasons
    base = {
        "schema_version": "1.0",
        "run_id": str(run_id or "").strip(),
        "repo_snapshot_id": str(repo_snapshot_id or "").strip(),
        "project_tree_hash": str(project_tree_hash or "").strip(),
        "eligible": eligible,
        "eligibility_reasons": eligibility_reasons,
        "must_cover_obligation_ids": tuple(dict.fromkeys(must_cover_ids)),
        "supported_obligation_ids": tuple(dict.fromkeys(supported_ids)),
        "partial_obligation_ids": tuple(dict.fromkeys(partial_ids)),
        "partial_obligations": tuple(partials),
        "deferred_obligation_ids": tuple(dict.fromkeys(deferred_ids)),
        "structural_failure_codes": structural,
        "warning_codes": tuple(dict.fromkeys(warning_codes)),
        "agenda_digest": source_agenda_digest,
        "promotion_ledger_digest": source_promotion_digest,
        "retry_ledger_digest": source_retry_digest,
        "revision_id": str(revision_id or "").strip(),
        "claim_bindings": tuple(claim_bindings),
    }
    return CandidateHandoffV1(
        handoff_id=digest_json(base),
        **base,
    )


class ObligationTerminalProofV1(BaseModel):
    """Evidence-backed terminal decision for one agenda obligation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    obligation_id: str
    agenda_status: str
    terminal: bool = False
    promoted_repository_evidence: bool = False
    bounded_search_exhausted: bool = False
    explicit_gap_bound: bool = False
    qualifier_clear: bool = False
    promoted_claim_ids: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ObligationTerminalProofV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", digest_json(payload))
        return self


def _value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _model_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    return str(value)


def _candidate_claim_binding(
    claim: Any,
    obligation_id: str,
) -> CandidateClaimBindingV1:
    payload = {
        "claim_id": str(_value(claim, "claim_id", "") or "").strip(),
        "obligation_id": str(obligation_id or "").strip(),
        "canonical_identity": str(
            _value(claim, "canonical_identity", "") or ""
        ).strip(),
        "fact_ids": tuple(
            str(value).strip()
            for value in (_value(claim, "fact_ids", ()) or ())
            if str(value).strip()
        ),
        "direct_evidence_ids": tuple(
            str(value).strip()
            for value in (_value(claim, "direct_evidence_ids", ()) or ())
            if str(value).strip()
        ),
        "relation_evidence_ids": tuple(
            str(value).strip()
            for value in (_value(claim, "relation_evidence_ids", ()) or ())
            if str(value).strip()
        ),
        "required_qualifiers": tuple(
            str(value).strip()
            for value in (_value(claim, "required_qualifiers", ()) or ())
            if str(value).strip()
        ),
        "allowed_wording_boundary": str(
            _value(claim, "allowed_wording_boundary", "") or ""
        ).strip(),
    }
    return CandidateClaimBindingV1(**payload)


def _missing_field_type(value: str) -> CandidateUnresolvedFieldType:
    prefix = str(value or "").strip().split(":", 1)[0].casefold()
    mapping: dict[str, CandidateUnresolvedFieldType] = {
        "call_relation": "call_relation",
        "source_span": "source_span",
        "parameter": "parameter",
        "numeric": "numeric",
        "formula": "formula",
        "control_flow": "control_flow",
        "configuration": "configuration",
        "lineage": "lineage",
        "ownership": "ownership",
        "qualifier": "qualifier",
        "required_qualifier": "qualifier",
    }
    return mapping.get(prefix, "other")


def _typed_unresolved_fields(
    obligation_id: str,
    missing_fields: tuple[str, ...],
) -> tuple[CandidateUnresolvedFieldV1, ...]:
    return tuple(
        CandidateUnresolvedFieldV1(
            field_id=digest_json({
                "obligation_id": obligation_id,
                "ordinal": index,
                "description": description,
            })[:24],
            field_type=_missing_field_type(description),
            description=description,
        )
        for index, description in enumerate(missing_fields)
    )


def _candidate_qualifier_contract(
    item: Any,
    compiled_claims: Iterable[Any],
    claim_ids: Iterable[str],
) -> tuple[str, str]:
    selected = {
        str(value).strip() for value in claim_ids if str(value).strip()
    }
    qualifiers: list[str] = []
    boundaries: list[str] = []
    for claim in compiled_claims:
        if str(_value(claim, "claim_id", "") or "").strip() not in selected:
            continue
        qualifiers.extend(
            str(value).strip()
            for value in (_value(claim, "required_qualifiers", ()) or ())
            if str(value).strip()
        )
        boundary = str(
            _value(claim, "allowed_wording_boundary", "") or ""
        ).strip()
        if boundary:
            boundaries.append(boundary)
    # Explicit agenda fields are accepted as a frozen contract when a caller
    # has already materialized them. Missing-information prose alone is never
    # treated as a closed qualifier.
    qualifiers.extend(
        str(value).strip()
        for value in (_value(item, "required_qualifiers", ()) or ())
        if str(value).strip()
    )
    item_boundary = str(
        _value(item, "allowed_wording_boundary", "") or ""
    ).strip()
    if item_boundary:
        boundaries.append(item_boundary)
    return (
        "; ".join(dict.fromkeys(qualifiers)),
        " OR ".join(dict.fromkeys(boundaries)),
    )


def _requirement_terminal_outcome(requirement: Any) -> str:
    """Return the typed terminal outcome recorded for one gap requirement.

    R9: the outcome comes from the typed disposition (or, for a legacy record,
    from nothing at all).  Notes that merely claim the frontier closed are not
    a state and must not be read as one.
    """

    declared = str(_value(requirement, "terminal_outcome", "") or "").strip()
    if declared:
        return declared
    disposition = _value(requirement, "terminal_disposition", None)
    if isinstance(disposition, Mapping):
        outcome = str(disposition.get("outcome") or "").strip()
        if outcome:
            return outcome
    payload = _value(requirement, "gap_payload", None)
    if isinstance(payload, Mapping):
        outcome = str(payload.get("terminal_outcome") or "").strip()
        if outcome:
            return outcome
        disposition = payload.get("terminal_disposition")
        if isinstance(disposition, Mapping):
            return str(disposition.get("outcome") or "").strip()
    return ""


def _negative_evidence_authorized(
    requirement: Any, *, receipt_verifier: Any | None = None
) -> bool:
    """Return whether one requirement carries ledger-authenticated negative proof.

    R9: the verdict is produced once by the execution ledger and reused here
    through ``verify_receipt_authentication``.  A receipt-shaped payload whose
    derivation was never authenticated by the execution layer is not evidence,
    so terminal consumers no longer repeat an ad-hoc boolean list check.

    ``receipt_verifier`` is the caller-supplied adapter that re-derives the
    receipt from the *current* revision's ledger.  Consumers that can reach the
    ledger must pass it: a stored ``ledger_verified`` marker alone cannot prove
    that the records behind it are still present and intact.  Without a
    verifier the requirement is treated as unproven.
    """

    if receipt_verifier is None:
        return False

    if _requirement_terminal_outcome(requirement) != (
        "unsupported_with_scoped_evidence"
    ):
        return False
    if _value(requirement, "negative_evidence_authorized", False) is not True:
        return False
    from code2paper.agentic.research_execution_ledger import (
        verify_receipt_authentication,
    )

    obligation_id = str(_value(requirement, "obligation_id", "") or "").strip()
    candidates: list[Any] = []
    declared_receipt = _value(requirement, "search_receipt", None)
    if declared_receipt is not None:
        candidates.append(declared_receipt)
    disposition = _value(requirement, "terminal_disposition", None)
    if isinstance(disposition, Mapping):
        candidates.extend(tuple(disposition.get("receipts") or ()))
    payload = _value(requirement, "gap_payload", None)
    if isinstance(payload, Mapping):
        if payload.get("search_receipt"):
            candidates.append(payload["search_receipt"])
        payload_disposition = payload.get("terminal_disposition")
        if isinstance(payload_disposition, Mapping):
            candidates.extend(
                tuple(payload_disposition.get("receipts") or ())
            )
    for candidate in candidates:
        authorized, _failures = verify_receipt_authentication(
            candidate,
            obligation_id=obligation_id,
            ledger_reader=receipt_verifier,
        )
        if authorized:
            return True
    return False


def _terminal_gap_bound(
    item: Any, *, receipt_verifier: Any | None = None
) -> bool:
    """Return whether every requirement is a *proved* negative conclusion.

    R9: a requirement marked ``explicit_gap`` without a typed, receipt-backed
    disposition is a legacy claim, not evidence.  It reads as unresolved and
    keeps its raw data.  The proof must be re-authenticated against the current
    revision's ledger through ``receipt_verifier``.
    """

    requirements = tuple(_value(item, "gap_requirements", ()) or ())
    if not requirements:
        return False
    return all(
        str(_value(req, "terminal", "open") or "open") == "explicit_gap"
        and _negative_evidence_authorized(
            req, receipt_verifier=receipt_verifier
        )
        for req in requirements
    )


def _typed_terminal_outcomes(item: Any) -> tuple[str, ...]:
    outcomes: list[str] = []
    payload = _value(item, "gap_payload", None)
    if isinstance(payload, Mapping):
        outcome = str(payload.get("terminal_outcome") or "").strip()
        if outcome:
            outcomes.append(outcome)
    for requirement in (_value(item, "gap_requirements", ()) or ()):
        outcome = _requirement_terminal_outcome(requirement)
        if outcome:
            outcomes.append(outcome)
    return tuple(dict.fromkeys(outcomes))


def _search_exhausted(
    item: Any,
    *,
    explicit_gap_bound: bool,
    receipt_verifier: Any | None = None,
) -> bool:
    """Return whether the search reached a proved, scoped closure.

    A bounded stop (``budget_exhausted``) or an inconclusive search is a real
    terminal *record* but never proves absence, so neither counts as an
    exhausted search for a ``partial`` claim.  Only an execution-ledger
    authenticated ``unsupported_with_scoped_evidence`` disposition does; a
    declared outcome string without that receipt is not proof.
    """

    if explicit_gap_bound:
        return True
    if any(
        _negative_evidence_authorized(
            requirement, receipt_verifier=receipt_verifier
        )
        for requirement in (_value(item, "gap_requirements", ()) or ())
    ):
        return True
    payload = _value(item, "gap_payload", None)
    if isinstance(payload, Mapping):
        return _negative_evidence_authorized(
            {
                "terminal_outcome": payload.get("terminal_outcome", ""),
                "negative_evidence_authorized": payload.get(
                    "negative_evidence_authorized", False
                ),
                "search_receipt": payload.get("search_receipt"),
                "terminal_disposition": payload.get("terminal_disposition"),
            },
            receipt_verifier=receipt_verifier,
        )
    return False


def _qualifier_clear(item: Any) -> bool:
    # A missing qualifier is not closed merely because no error marker appears
    # in missing_information. Only typed agenda/gap fields may close it.
    qualifiers = tuple(
        str(value).strip()
        for value in (_value(item, "required_qualifiers", ()) or ())
        if str(value).strip()
    )
    boundary = str(_value(item, "allowed_wording_boundary", "") or "").strip()
    if qualifiers or boundary:
        return True
    for requirement in (_value(item, "gap_requirements", ()) or ()):
        if str(_value(requirement, "qualifier", "") or "").strip():
            return True
        if str(_value(requirement, "allowed_wording_boundary", "") or "").strip():
            return True
    return False


def _record_claim_ids(records: Iterable[Any]) -> tuple[str, ...]:
    values: list[str] = []
    for record in records:
        status = str(_value(record, "status", "") or "")
        if status != "claim_promoted":
            continue
        values.extend(
            str(value).strip()
            for value in (_value(record, "claim_ids", ()) or ())
            if str(value).strip()
        )
    return tuple(dict.fromkeys(values))


def evaluate_obligation_terminal_proof(
    item: Any,
    *,
    promotion_records: Iterable[Any] = (),
    promoted_claim_ids: Iterable[str] = (),
    search_exhausted: bool | None = None,
    receipt_verifier: Any | None = None,
) -> ObligationTerminalProofV1:
    """Evaluate whether an agenda item has a complete terminal proof.

    ``supported`` requires repository-promoted claims.  ``partial`` requires
    the same promotion plus a bounded, explicit gap and a clear qualifier
    boundary.  A status string or a discovery hit alone is never sufficient.
    """

    obligation_id = str(_value(item, "obligation_id", "") or "").strip()
    agenda_status = str(_value(item, "status", "") or "")
    record_claims = _record_claim_ids(promotion_records)
    claims = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in (*record_claims, *tuple(promoted_claim_ids))
            if str(value).strip()
        )
    )
    promoted = bool(claims)
    explicit_gap_bound = _terminal_gap_bound(
        item, receipt_verifier=receipt_verifier
    )
    exhausted = (
        _search_exhausted(
            item,
            explicit_gap_bound=explicit_gap_bound,
            receipt_verifier=receipt_verifier,
        )
        if search_exhausted is None
        else bool(search_exhausted)
    )
    qualifier_clear = _qualifier_clear(item)
    reasons: list[str] = []
    terminal = False
    if agenda_status == "supported":
        if promoted:
            terminal = True
        else:
            reasons.append("promoted_repository_evidence_missing")
    elif agenda_status == "partial":
        if not promoted:
            reasons.append("promoted_repository_evidence_missing")
        if not exhausted:
            reasons.append("bounded_search_not_exhausted")
        if not explicit_gap_bound:
            reasons.append("explicit_gap_not_bound_to_missing_field")
        if not qualifier_clear:
            reasons.append("required_qualifier_not_closed")
        terminal = promoted and exhausted and explicit_gap_bound and qualifier_clear
    elif agenda_status == "explicit_gap":
        terminal = explicit_gap_bound
        if not terminal:
            reasons.append("explicit_gap_requirements_not_terminal")
    elif agenda_status == "blocked":
        terminal = True
    else:
        reasons.append("agenda_status_not_terminal")

    return ObligationTerminalProofV1(
        obligation_id=obligation_id,
        agenda_status=agenda_status,
        terminal=terminal,
        promoted_repository_evidence=promoted,
        bounded_search_exhausted=exhausted,
        explicit_gap_bound=explicit_gap_bound,
        qualifier_clear=qualifier_clear,
        promoted_claim_ids=claims,
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "ResearchClosureAdmissionV1",
    "build_research_closure_admission",
    "ObligationTerminalProofV1",
    "evaluate_obligation_terminal_proof",
    "CandidateUnresolvedFieldV1",
    "CandidateClaimBindingV1",
    "CandidateRetryLedgerV1",
    "build_candidate_retry_ledger",
    "CandidatePartialHandoffV1",
    "CandidateHandoffV1",
    "build_candidate_handoff",
    "handoff_address_variants",
    "handoff_payload_identity",
]
