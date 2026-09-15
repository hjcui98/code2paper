"""Proposal-call accounting (planned / reserved / measured / spent / unsettled).

A proposal call is a model request whose *result is never authority*: an
organization or revision proposal may be consumed or rejected, but the request
itself still costs real tokens.  The round-4 review requires these calls to be
metered with the same discipline as the unified invocation plan:

* **planned** -- what the frozen plan reserved for this call;
* **reserved** -- what the run set aside before sending;
* **measured** -- the exact serialized request (prompt + structured payload +
  closed response schema) measured by the run's declared meter;
* **spent** -- measured tokens of an attempt that actually reached the caller;
* **unsettled** -- reserved tokens of an attempt with a start record and no
  finish record (interrupted, crashed, or awaiting resume).

This module deliberately does **not** reuse ``ActualRequestReceiptV2``: that
receipt binds ``consumer_role``/``phase``/``workset_id``/``page_id``/
``plan_digest``/envelope digests to a real unified-pipeline invocation, and
fabricating those identities for a proposal call would manufacture delivery
evidence.  A proposal call therefore gets its own tally whose
``invocation_plan_membership`` states exactly where it belongs.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.unified_context_compiler import measure_unified_tokens
from code2paper.agentic.unified_context_models import UnifiedTokenMeterV1


PROPOSAL_CALL_ACCOUNTING_VERSION = "1.0"

ProposalCallStatus = Literal["completed", "failed"]

#: Honest labels for how a proposal call's tokens relate to the unified
#: invocation plan.  ``recorded_not_in_invocation_plan`` is the historical
#: state; ``measured_with_proposal_accounting`` means the run measured the
#: complete serialized request and kept an auditable tally.
PROPOSAL_ACCOUNTING_IN_PLAN = "measured_with_proposal_accounting"
PROPOSAL_ACCOUNTING_RECORDED_ONLY = "recorded_not_in_invocation_plan"


def _digest(payload: Any) -> str:
    return hashlib_sha256(json.dumps(payload, sort_keys=True, default=str))


def hashlib_sha256(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ProposalCallPendingV1(BaseModel):
    """A call that started and has no finish record yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    proposal_kind: str = ""
    target_id: str = ""
    consumer_role: str = ""
    attempt: int = 1
    request_input_hash: str = ""
    planned_input_tokens: int = 0
    reserved_input_tokens: int = 0
    run_digest: str = ""
    revision_id: str = ""
    envelope_digest: str = ""
    profile_digest: str = ""
    model_identity_digest: str = ""
    started_at_unix: float = 0.0
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))


class ProposalCallTallyV1(BaseModel):
    """One finished proposal-call attempt as measured at the caller boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROPOSAL_CALL_ACCOUNTING_VERSION
    call_id: str
    proposal_kind: str = ""
    target_id: str = ""
    consumer_role: str = ""
    attempt: int = 1
    model_identity: str = ""
    request_input_hash: str = ""
    meter: UnifiedTokenMeterV1 | None = None
    planned_input_tokens: int = 0
    reserved_input_tokens: int = 0
    measured_input_tokens: int = 0
    # False means the request was rejected before the transport boundary.  It
    # remains visible for audit but must not be charged as provider spend.
    sent_to_caller: bool = True
    measurement_parts: dict[str, int] = Field(default_factory=dict)
    status: ProposalCallStatus = "completed"
    error: str = ""
    run_digest: str = ""
    revision_id: str = ""
    envelope_digest: str = ""
    profile_digest: str = ""
    model_identity_digest: str = ""
    started_at_unix: float = 0.0
    finished_at_unix: float = 0.0
    content_digest: str = ""

    def model_post_init(self, __context: Any) -> None:
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))

    @property
    def spent_input_tokens(self) -> int:
        """Tokens this attempt cost the run.

        A failed attempt still counts its measured input: the request was
        handed to the caller, so the conservative direction is to charge it.
        """

        if not self.sent_to_caller:
            return 0
        return max(0, int(self.measured_input_tokens))


class ProposalCallAccountingV1(BaseModel):
    """The run's append-only view of its proposal calls."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROPOSAL_CALL_ACCOUNTING_VERSION
    consumer_role: str = ""
    invocation_plan_membership: str = PROPOSAL_ACCOUNTING_RECORDED_ONLY
    # Bind this auxiliary tally to the same run contract as the page ledger.
    # Keeping the identity on the envelope as well as on each row lets a
    # resumed process reject a foreign/cross-revision file before appending.
    run_digest: str = ""
    revision_id: str = ""
    envelope_digest: str = ""
    profile_digest: str = ""
    model_identity_digest: str = ""
    rows: tuple[ProposalCallTallyV1, ...] = Field(default_factory=tuple)
    pending: tuple[ProposalCallPendingV1, ...] = Field(default_factory=tuple)
    content_digest: str = ""

    @model_validator(mode="after")
    def _compute_digest(self) -> "ProposalCallAccountingV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        expected = _digest(payload)
        if self.content_digest and self.content_digest != expected:
            raise ValueError("proposal call accounting content_digest mismatch")
        object.__setattr__(self, "content_digest", expected)
        return self

    # -- accounting views -------------------------------------------------

    def planned_input_tokens(self) -> int:
        return sum(
            max(0, int(row.planned_input_tokens)) for row in self.rows
        ) + sum(max(0, int(item.planned_input_tokens)) for item in self.pending)

    def reserved_input_tokens(self) -> int:
        return sum(
            max(0, int(row.reserved_input_tokens)) for row in self.rows
        ) + sum(max(0, int(item.reserved_input_tokens)) for item in self.pending)

    def measured_input_tokens(self) -> int:
        return sum(max(0, int(row.measured_input_tokens)) for row in self.rows)

    def spent_input_tokens(self) -> int:
        return sum(row.spent_input_tokens for row in self.rows)

    def unsettled_input_tokens(self) -> int:
        """Reserved tokens of attempts that never finished."""

        return sum(
            max(
                int(item.reserved_input_tokens) or int(item.planned_input_tokens),
                0,
            )
            for item in self.pending
        )

    def unsettled_call_ids(self) -> tuple[str, ...]:
        return tuple(item.call_id for item in self.pending)

    def failed_call_ids(self) -> tuple[str, ...]:
        return tuple(
            row.call_id for row in self.rows if row.status == "failed"
        )

    def totals(self) -> dict[str, Any]:
        return {
            "planned_input_tokens": self.planned_input_tokens(),
            "reserved_input_tokens": self.reserved_input_tokens(),
            "measured_input_tokens": self.measured_input_tokens(),
            "spent_input_tokens": self.spent_input_tokens(),
            "unsettled_input_tokens": self.unsettled_input_tokens(),
            "call_count": len(self.rows),
            "failed_call_count": len(self.failed_call_ids()),
            "unsettled_call_ids": list(self.unsettled_call_ids()),
            "invocation_plan_membership": self.invocation_plan_membership,
            "consumer_role": self.consumer_role,
            "run_digest": self.run_digest,
            "revision_id": self.revision_id,
            "envelope_digest": self.envelope_digest,
            "profile_digest": self.profile_digest,
            "model_identity_digest": self.model_identity_digest,
            "schema_version": self.schema_version,
        }

    # -- transitions ------------------------------------------------------

    def begin(
        self,
        *,
        call_id: str,
        proposal_kind: str = "",
        target_id: str = "",
        attempt: int = 1,
        request_input_hash: str = "",
        planned_input_tokens: int = 0,
        reserved_input_tokens: int = 0,
    ) -> tuple["ProposalCallAccountingV1", ProposalCallPendingV1]:
        if any(item.call_id == call_id and item.attempt == attempt for item in self.pending):
            raise ValueError(f"proposal call already pending: {call_id}#{attempt}")
        if any(
            row.call_id == call_id and row.attempt == attempt
            for row in self.rows
        ):
            raise ValueError(f"proposal call already finished: {call_id}#{attempt}")
        pending = ProposalCallPendingV1(
            call_id=str(call_id),
            proposal_kind=str(proposal_kind),
            target_id=str(target_id),
            consumer_role=self.consumer_role,
            attempt=max(1, int(attempt)),
            request_input_hash=str(request_input_hash),
            planned_input_tokens=max(0, int(planned_input_tokens)),
            reserved_input_tokens=max(0, int(reserved_input_tokens)),
            run_digest=self.run_digest,
            revision_id=self.revision_id,
            envelope_digest=self.envelope_digest,
            profile_digest=self.profile_digest,
            model_identity_digest=self.model_identity_digest,
            started_at_unix=time.time(),
        )
        # Rebuild through the constructor: ``model_copy`` skips the digest
        # validator and would leave a stale content digest on a changed tally.
        updated = ProposalCallAccountingV1(
            schema_version=self.schema_version,
            consumer_role=self.consumer_role,
            invocation_plan_membership=self.invocation_plan_membership,
            run_digest=self.run_digest,
            revision_id=self.revision_id,
            envelope_digest=self.envelope_digest,
            profile_digest=self.profile_digest,
            model_identity_digest=self.model_identity_digest,
            rows=self.rows,
            pending=(*self.pending, pending),
        )
        return updated, pending

    def finish(
        self,
        pending: ProposalCallPendingV1,
        *,
        status: ProposalCallStatus,
        measured_input_tokens: int = 0,
        measurement_parts: Mapping[str, int] | None = None,
        meter: UnifiedTokenMeterV1 | None = None,
        model_identity: str = "",
        error: str = "",
        sent_to_caller: bool = True,
    ) -> "ProposalCallAccountingV1":
        remaining = tuple(
            item
            for item in self.pending
            if not (
                item.call_id == pending.call_id
                and item.attempt == pending.attempt
            )
        )
        if len(remaining) == len(self.pending):
            raise ValueError(
                f"proposal call was not pending: {pending.call_id}"
            )
        row = ProposalCallTallyV1(
            call_id=pending.call_id,
            proposal_kind=pending.proposal_kind,
            target_id=pending.target_id,
            consumer_role=pending.consumer_role,
            attempt=pending.attempt,
            model_identity=str(model_identity),
            request_input_hash=pending.request_input_hash,
            meter=meter,
            planned_input_tokens=pending.planned_input_tokens,
            reserved_input_tokens=pending.reserved_input_tokens,
            measured_input_tokens=max(0, int(measured_input_tokens)),
            sent_to_caller=bool(sent_to_caller),
            measurement_parts={
                str(key): max(0, int(value))
                for key, value in (measurement_parts or {}).items()
            },
            status=status,
            error=str(error)[:400],
            run_digest=pending.run_digest,
            revision_id=pending.revision_id,
            envelope_digest=pending.envelope_digest,
            profile_digest=pending.profile_digest,
            model_identity_digest=pending.model_identity_digest,
            started_at_unix=pending.started_at_unix,
            finished_at_unix=time.time(),
        )
        return ProposalCallAccountingV1(
            schema_version=self.schema_version,
            consumer_role=self.consumer_role,
            invocation_plan_membership=self.invocation_plan_membership,
            run_digest=self.run_digest,
            revision_id=self.revision_id,
            envelope_digest=self.envelope_digest,
            profile_digest=self.profile_digest,
            model_identity_digest=self.model_identity_digest,
            rows=(*self.rows, row),
            pending=remaining,
        )


class ProposalCallMeterV1(BaseModel):
    """Everything needed to measure a proposal call without a pipeline identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    consumer_role: str
    meter: UnifiedTokenMeterV1
    model_identity: str = ""
    planned_input_tokens: int = 0
    reserved_input_tokens: int = 0
    # Optional whole-run limits.  Zero preserves the legacy, explicitly
    # recorded-only unit-test mode; meters derived from a unified envelope set
    # these fields and therefore enforce them before the transport call.
    max_calls: int = Field(default=0, ge=0)
    max_total_input_tokens: int = Field(default=0, ge=0)
    # The role-wide input ceiling from the envelope.  It is distinct from
    # ``max_input_tokens`` (the per-request cap).
    max_role_input_tokens: int = Field(default=0, ge=0)
    run_digest: str = ""
    revision_id: str = ""
    envelope_digest: str = ""
    profile_digest: str = ""
    model_identity_digest: str = ""
    budget_required: bool = False
    accounting_filename: str = "proposal_call_accounting_v1.json"
    #: Hard per-request input cap.  ``0`` means "no cap declared", in which
    #: case the call is measured but not refused on size.
    max_input_tokens: int = 0
    #: Directory that holds the durable started/completed tally.  When set,
    #: the tally is written *before* the call, so an interrupt between start
    #: and completion stays visible as ``unsettled`` on resume.
    accounting_root: Any | None = None
    #: A tokenizer object with ``encode`` when the meter is ``model_tokenizer``.
    tokenizer: Any | None = None

    @model_validator(mode="after")
    def _validate_meter(self) -> "ProposalCallMeterV1":
        if not self.consumer_role.strip():
            raise ValueError("proposal call meter requires a consumer role")
        if self.meter.method == "model_tokenizer" and self.tokenizer is None:
            raise ValueError(
                "a model_tokenizer proposal meter requires the tokenizer used "
                "for calibration"
            )
        return self


def measure_proposal_request(
    request: Any,
    *,
    call_meter: ProposalCallMeterV1,
) -> tuple[int, dict[str, int]]:
    """Measure the complete serialized request with the run's declared meter.

    The three parts mirror ``account_unified_request_tokens`` so a proposal
    plan and a proposal send can never be measured by two different rules.
    """

    parts = {
        "prompt": measure_unified_tokens(
            getattr(request, "prompt", "") or "",
            meter=call_meter.meter,
            tokenizer=call_meter.tokenizer,
        ),
        "input_payload": measure_unified_tokens(
            getattr(request, "input_payload", {}) or {},
            meter=call_meter.meter,
            tokenizer=call_meter.tokenizer,
        ),
        "response_schema": measure_unified_tokens(
            getattr(request, "response_json_schema", {}) or {},
            meter=call_meter.meter,
            tokenizer=call_meter.tokenizer,
        ),
    }
    return sum(parts.values()), parts


def proposal_call_id(
    *,
    prompt_template_id: str,
    proposal_kind: str,
    target_id: str,
    attempt: int,
) -> str:
    """Stable identity for one proposal call attempt."""

    return (
        f"proposal-call:{prompt_template_id}:{proposal_kind}:{target_id}:"
        f"{max(1, int(attempt))}"
    )


def proposal_call_meter_from_envelope(
    envelope: Any,
    *,
    consumer_role: str = "",
    model_identity: str = "",
    tokenizer: Any | None = None,
    accounting_root: Any | None = None,
    run_digest: str = "",
    revision_id: str = "",
    accounting_filename: str = "proposal_call_accounting_v1.json",
) -> ProposalCallMeterV1 | None:
    """Build a proposal-call meter from the run's frozen budget envelope.

    Returns ``None`` -- meaning "no measurement is available" -- instead of
    inventing one:

    * no envelope or no token meter: the run has no metering contract;
    * a ``model_tokenizer`` meter without the tokenizer: measuring with the
      conservative proxy while the envelope declares a tokenizer would report
      two different rules for the same run, so the call stays unmetered.
    """

    meter = getattr(envelope, "token_meter", None)
    if meter is None:
        return None
    if str(getattr(meter, "method", "")) == "model_tokenizer" and tokenizer is None:
        return None
    role = str(consumer_role or "").strip()
    # Lightweight envelope doubles used by legacy callers predate the
    # whole-run contract.  Preserve their explicitly recorded-only behavior;
    # a real ``RunInvocationBudgetEnvelopeV1`` always has these maps and takes
    # the strict branch below.
    if not hasattr(envelope, "max_calls_by_role"):
        role_budgets = (
            getattr(envelope, "max_request_input_tokens_by_role", None) or {}
        )
        planned = max(0, int(role_budgets.get(role, 0) or 0))
        return ProposalCallMeterV1(
            consumer_role=role,
            max_input_tokens=planned,
            meter=meter,
            model_identity=str(
                model_identity
                or getattr(envelope, "model_identity_digest", "")
                or ""
            ),
            planned_input_tokens=planned,
            reserved_input_tokens=planned,
            tokenizer=tokenizer,
            accounting_root=accounting_root,
            accounting_filename=str(accounting_filename),
        )
    max_calls_by_role = getattr(envelope, "max_calls_by_role", None) or {}
    request_budgets = getattr(envelope, "request_budget_by_role", None) or {}
    request_caps = getattr(envelope, "max_request_input_tokens_by_role", None) or {}
    # A four-role envelope cannot silently authorize an auxiliary role.  The
    # caller gets no meter and the owning path must take its explicit
    # deterministic fallback instead of sending an unbudgeted request.
    if (
        not role
        or role not in max_calls_by_role
        or role not in request_budgets
        or role not in request_caps
    ):
        return None
    planned = 0
    cap = 0
    if role in request_caps:
        planned = max(0, int(request_caps[role] or 0))
        cap = planned
    model_digest = str(
        model_identity
        or getattr(envelope, "model_identity_digest", "")
        or ""
    )
    return ProposalCallMeterV1(
        consumer_role=role,
        max_input_tokens=cap,
        meter=meter,
        model_identity=model_digest,
        planned_input_tokens=planned,
        reserved_input_tokens=planned,
        max_calls=max(0, int(max_calls_by_role.get(role, 0) or 0)),
        max_total_input_tokens=max(
            0, int(getattr(envelope, "max_total_input_tokens", 0) or 0)
        ),
        max_role_input_tokens=max(
            0,
            int(
                (getattr(envelope, "max_input_tokens_by_role", {}) or {}).get(
                    role, 0
                )
                or 0
            ),
        ),
        run_digest=str(run_digest or getattr(envelope, "run_digest", "") or ""),
        revision_id=str(revision_id or ""),
        envelope_digest=str(getattr(envelope, "content_digest", "") or ""),
        profile_digest=str(getattr(envelope, "profile_digest", "") or ""),
        model_identity_digest=str(
            getattr(envelope, "model_identity_digest", "") or model_digest
        ),
        budget_required=True,
        accounting_filename=str(accounting_filename),
        tokenizer=tokenizer,
        accounting_root=accounting_root,
    )


def build_budgeted_auxiliary_llm_caller(
    llm_config: Any,
    envelope: Any,
    *,
    accounting_root: Any,
    tokenizer: Any | None = None,
    base_caller: Any | None = None,
    revision_id: str = "",
) -> Any:
    """Wrap planner/verifier transport in the unified auxiliary budget.

    Auxiliary authoring requests do not have a truthful page/workset identity,
    so this adapter gives them a typed proposal-style tally while sharing the
    same run total and durable ledger root.  A missing/half-declared role,
    tokenizer, corrupt tally, or failed start write returns a blocked
    ``LLMResponse`` without entering the transport.
    """

    from types import SimpleNamespace

    from code2paper.export.run_manifest import hash_text
    from code2paper.llm.client import LLMClient, LLMResponse

    if base_caller is None:
        def _default_base_caller(config: Any, request: Any) -> Any:
            return LLMClient(config).complete(request)

        transport = _default_base_caller
    else:
        transport = base_caller

    states: dict[str, dict[str, Any]] = {}

    def _response_cache_path(role: str, target_id: str) -> Path:
        digest = hashlib.sha256(target_id.encode("utf-8")).hexdigest()
        safe_role = "".join(
            character if character.isalnum() or character in "-_" else "-"
            for character in role
        )
        return (
            Path(accounting_root)
            / "artifacts"
            / "06_authoring"
            / "auxiliary_responses"
            / safe_role
            / f"{digest}.json"
        )

    def _cached_response(
        *,
        role: str,
        target_id: str,
        kind: str,
        accounting: ProposalCallAccountingV1,
    ) -> LLMResponse | None:
        """Reuse a settled auxiliary response without creating a new row/send."""

        if not any(
            row.proposal_kind == kind
            and row.target_id == target_id
            and row.status in {"completed", "failed"}
            and bool(getattr(row, "sent_to_caller", True))
            for row in accounting.rows
        ):
            return None
        path = _response_cache_path(role, target_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None
        if str(payload.get("role") or "") != role:
            return None
        if str(payload.get("target_id") or "") != target_id:
            return None
        if str(payload.get("proposal_kind") or "") != kind:
            return None
        return LLMResponse(
            text=str(payload.get("text") or ""),
            response_hash=str(payload.get("response_hash") or ""),
            blocked_reason=str(payload.get("blocked_reason") or ""),
            cached=True,
            response_mode=str(payload.get("response_mode") or "auxiliary_cache"),
            finish_reason=str(payload.get("finish_reason") or ""),
            token_usage=(
                dict(payload.get("token_usage"))
                if isinstance(payload.get("token_usage"), Mapping)
                else None
            ),
            provider_finish_reason=str(payload.get("provider_finish_reason") or ""),
            thinking_chars=int(payload.get("thinking_chars", 0) or 0),
        )

    def _persist_response_cache(
        *,
        role: str,
        target_id: str,
        kind: str,
        response: Any,
    ) -> None:
        path = _response_cache_path(role, target_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "role": role,
            "proposal_kind": kind,
            "target_id": target_id,
            "text": str(getattr(response, "text", "") or ""),
            "response_hash": str(getattr(response, "response_hash", "") or ""),
            "blocked_reason": str(getattr(response, "blocked_reason", "") or ""),
            "response_mode": str(getattr(response, "response_mode", "") or ""),
            "finish_reason": str(getattr(response, "finish_reason", "") or ""),
            "token_usage": getattr(response, "token_usage", None),
            "provider_finish_reason": str(
                getattr(response, "provider_finish_reason", "") or ""
            ),
            "thinking_chars": int(getattr(response, "thinking_chars", 0) or 0),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _blocked(reason: str) -> LLMResponse:
        return LLMResponse(
            text="",
            response_hash=hash_text(""),
            blocked_reason=str(reason)[:400],
        )

    def _state_for(config: Any, request: Any) -> tuple[str, ProposalCallMeterV1 | None, str]:
        role = str(getattr(config, "role", "") or "").strip()
        if not role:
            return "", None, "unified_auxiliary_budget_missing:role"
        state = states.get(role)
        if state is not None:
            return role, state.get("meter"), str(state.get("failure") or "")
        filename = (
            "proposal_call_accounting_"
            + "".join(character if character.isalnum() or character in "-_" else "-" for character in role)
            + ".json"
        )
        meter = proposal_call_meter_from_envelope(
            envelope,
            consumer_role=role,
            model_identity=str(getattr(envelope, "model_identity_digest", "") or ""),
            tokenizer=tokenizer,
            accounting_root=accounting_root,
            run_digest=str(getattr(envelope, "run_digest", "") or ""),
            revision_id=revision_id,
            accounting_filename=filename,
        )
        if meter is None:
            failure = f"unified_auxiliary_budget_missing:{role}"
            states[role] = {"meter": None, "failure": failure, "accounting": None}
            return role, None, failure
        accounting, failure = load_durable_accounting_status(meter)
        if accounting is None:
            accounting = ProposalCallAccountingV1(
                consumer_role=role,
                invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
                run_digest=meter.run_digest,
                revision_id=meter.revision_id,
                envelope_digest=meter.envelope_digest,
                profile_digest=meter.profile_digest,
                model_identity_digest=meter.model_identity_digest,
            )
        states[role] = {"meter": meter, "failure": failure, "accounting": accounting}
        return role, meter, failure

    def _auxiliary_caller(config: Any, request: Any) -> LLMResponse:
        role, meter, state_failure = _state_for(config, request)
        if meter is None:
            return _blocked(state_failure or "unified_auxiliary_budget_missing")
        state = states[role]
        accounting = state.get("accounting")
        if state_failure:
            return _blocked(state_failure)
        if accounting is None:
            return _blocked("unified_auxiliary_accounting_missing")
        kind = "auxiliary:" + str(getattr(request, "prompt_template_id", "") or "request")
        target_id = str(getattr(request, "input_hash", "") or "")
        cached = _cached_response(
            role=role,
            target_id=target_id,
            kind=kind,
            accounting=accounting,
        )
        if cached is not None:
            return cached
        attempt = 1 + sum(
            1 for row in accounting.rows
            if row.proposal_kind == kind and row.target_id == target_id
        ) + sum(
            1 for item in accounting.pending
            if item.proposal_kind == kind and item.target_id == target_id
        )
        pending: ProposalCallPendingV1 | None = None
        measured = 0
        parts: dict[str, int] = {}
        error = ""
        sent = False
        try:
            accounting, pending = accounting.begin(
                call_id=proposal_call_id(
                    prompt_template_id=str(
                        getattr(request, "prompt_template_id", "auxiliary")
                    ),
                    proposal_kind=kind,
                    target_id=target_id,
                    attempt=attempt,
                ),
                proposal_kind=kind,
                target_id=target_id,
                attempt=attempt,
                request_input_hash=target_id,
                planned_input_tokens=meter.planned_input_tokens,
                reserved_input_tokens=(
                    meter.reserved_input_tokens or meter.planned_input_tokens
                ),
            )
            persist_proposal_call_state(meter, accounting, strict=True)
        except Exception as exc:  # noqa: BLE001 - no durable start, no send
            state["accounting"] = accounting
            return _blocked(
                "unified_auxiliary_start_persist_failed:" + type(exc).__name__
            )
        state["accounting"] = accounting
        try:
            measured, parts = measure_proposal_request(request, call_meter=meter)
        except Exception as exc:  # noqa: BLE001 - measurement is mandatory
            error = f"measurement_failed:{type(exc).__name__}:{exc}"
        if not error and meter.max_input_tokens > 0 and measured > meter.max_input_tokens:
            error = f"unified_auxiliary_request_cap_exceeded:{measured}>{meter.max_input_tokens}"
        if not error and meter.budget_required:
            from code2paper.agentic.unified_invocation_ledger import (
                check_run_budget_before_send,
            )

            budget_view = SimpleNamespace(
                max_calls_by_role={role: meter.max_calls},
                max_total_input_tokens=meter.max_total_input_tokens,
                max_input_tokens_by_role={
                    role: meter.max_role_input_tokens or meter.max_total_input_tokens
                },
            )
            failures = check_run_budget_before_send(
                unified_authoring_ledger_root(meter.accounting_root),
                budget_view,
                role=role,
                request_input_tokens=measured,
                current_reserved_input_tokens=(
                    meter.reserved_input_tokens or meter.planned_input_tokens
                ),
                current_attempt_recorded=True,
            )
            if failures:
                error = ";".join(failures)
        response: Any = None
        if not error:
            try:
                response = transport(config, request)
                sent = True
                if response is None:
                    response = _blocked("unified_auxiliary_call_returned_none")
            except Exception as exc:  # noqa: BLE001 - provider failure is spend
                sent = True
                error = f"{type(exc).__name__}:{str(exc)[:200]}"
                response = _blocked("unified_auxiliary_call_error:" + type(exc).__name__)
        if response is not None and getattr(response, "blocked_reason", ""):
            error = error or str(getattr(response, "blocked_reason", ""))
        try:
            accounting = accounting.finish(
                pending,
                status="failed" if error else "completed",
                measured_input_tokens=measured,
                measurement_parts=parts,
                meter=meter.meter,
                model_identity=meter.model_identity,
                error=error,
                sent_to_caller=sent,
            )
            state["accounting"] = accounting
            persist_proposal_call_state(meter, accounting, strict=True)
        except Exception:
            # If settlement cannot be published, the already durable pending
            # row remains the conservative recovery authority.
            state["accounting"] = accounting
            if response is None:
                return _blocked("unified_auxiliary_finish_persist_failed")
        if response is not None and sent:
            try:
                _persist_response_cache(
                    role=role,
                    target_id=target_id,
                    kind=kind,
                    response=response,
                )
            except Exception:
                # The settled accounting row remains the spend authority.  A
                # missing cache is not silently treated as a reusable result;
                # a later execution will report/attempt the bounded role again.
                pass
        if response is None:
            return _blocked(error or "unified_auxiliary_request_rejected")
        return response

    _auxiliary_caller.states = states  # type: ignore[attr-defined]
    return _auxiliary_caller


def accounting_from_plan_trace(trace: Mapping[str, Any]) -> ProposalCallAccountingV1 | None:
    """Rebuild the tally a narrative-plan trace recorded.

    The plan builder writes ``proposal_call_rows`` / ``proposal_call_totals``
    so a later stage can persist the run's proposal-call accounting without
    re-running the proposals.  A trace without measured rows returns ``None``:
    "recorded" is not "measured".
    """

    rows_payload = trace.get("proposal_call_rows")
    if not rows_payload:
        return None
    rows = tuple(
        ProposalCallTallyV1.model_validate(row) for row in rows_payload
    )
    totals = dict(trace.get("proposal_call_totals") or {})
    return ProposalCallAccountingV1(
        consumer_role=str(totals.get("consumer_role") or ""),
        invocation_plan_membership=str(
            totals.get("invocation_plan_membership")
            or PROPOSAL_ACCOUNTING_IN_PLAN
        ),
        run_digest=str(totals.get("run_digest") or ""),
        revision_id=str(totals.get("revision_id") or ""),
        envelope_digest=str(totals.get("envelope_digest") or ""),
        profile_digest=str(totals.get("profile_digest") or ""),
        model_identity_digest=str(totals.get("model_identity_digest") or ""),
        rows=rows,
    )


def persist_proposal_call_state(
    call_meter: ProposalCallMeterV1 | None,
    accounting: ProposalCallAccountingV1 | None,
    *,
    strict: bool = False,
) -> Path | None:
    """Write the current tally to the meter's durable root, if it has one.

    The caller persists *before* the model call and again after it settles, so
    a process that dies mid-call leaves a durable ``pending`` row: the next run
    reloads it and reports the reservation as unsettled instead of pretending
    the call never happened.
    """

    root = getattr(call_meter, "accounting_root", None)
    if root is None or accounting is None:
        return None
    try:
        return write_proposal_call_accounting(
            root,
            accounting,
            filename=str(
                getattr(call_meter, "accounting_filename", "")
                or "proposal_call_accounting_v1.json"
            ),
        )
    except Exception:
        if strict:
            raise
        return None


def _safe_accounting_filename(filename: Any) -> str:
    """Return one portable auxiliary-accounting filename.

    Auxiliary roles may use separate files, but every such file remains under
    the single ``06_authoring`` root and has a recognizable prefix for the
    run-ledger scanner.  A path supplied by a caller is never allowed to
    escape that root.
    """

    value = Path(str(filename or "proposal_call_accounting_v1.json")).name
    if not value.startswith("proposal_call_accounting"):
        raise ValueError("proposal accounting filename has an invalid prefix")
    if not value.endswith(".json"):
        value += ".json"
    return value


def write_proposal_call_accounting(
    out_root: Any,
    accounting: Any,
    *,
    filename: str = "proposal_call_accounting_v1.json",
) -> Path:
    """Persist the tally under the run's artifact root."""

    root = Path(out_root) / "artifacts" / "06_authoring"
    root.mkdir(parents=True, exist_ok=True)
    path = root / _safe_accounting_filename(filename)
    payload = (
        accounting.model_dump(mode="json")
        if isinstance(accounting, BaseModel)
        else dict(accounting)
    )
    temp_path = root / f".{path.name}.tmp-{os.getpid()}-{time.time_ns()}"
    try:
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return path


def durable_accounting_path(call_meter: ProposalCallMeterV1 | None) -> Path | None:
    """The run's durable tally path, or ``None`` when the meter has no root."""

    root = getattr(call_meter, "accounting_root", None)
    if root is None:
        return None
    return (
        Path(root)
        / "artifacts"
        / "06_authoring"
        / _safe_accounting_filename(
            getattr(call_meter, "accounting_filename", "")
            or "proposal_call_accounting_v1.json"
        )
    )


def unified_authoring_ledger_root(accounting_root: Any) -> Path:
    """Return the page-ledger root paired with an authoring output root.

    Proposal tallies live at ``<output>/artifacts/06_authoring`` while page
    receipts live one level below it in ``invocations``.  Keeping this mapping
    here prevents an auxiliary send check from accidentally scanning the output
    root (and therefore missing both page receipts and its sibling tally).
    """

    root = Path(accounting_root)
    if root.name == "invocations" and root.parent.name == "06_authoring":
        return root
    return root / "artifacts" / "06_authoring" / "invocations"


def _accounting_identity_failures(
    accounting: ProposalCallAccountingV1,
    call_meter: ProposalCallMeterV1,
) -> tuple[str, ...]:
    """Check every persisted identity against the current frozen meter."""

    failures: list[str] = []
    if accounting.consumer_role != str(call_meter.consumer_role):
        failures.append("consumer_role")
    if not call_meter.budget_required:
        return tuple(failures)
    if accounting.invocation_plan_membership != PROPOSAL_ACCOUNTING_IN_PLAN:
        failures.append("invocation_plan_membership")
    expected = {
        "run_digest": str(call_meter.run_digest or ""),
        "revision_id": str(call_meter.revision_id or ""),
        "envelope_digest": str(call_meter.envelope_digest or ""),
        "profile_digest": str(call_meter.profile_digest or ""),
        "model_identity_digest": str(call_meter.model_identity_digest or ""),
    }
    for field_name, expected_value in expected.items():
        if not expected_value:
            continue
        actual_value = str(getattr(accounting, field_name, "") or "")
        if actual_value != expected_value:
            failures.append(field_name)
    records = (*accounting.rows, *accounting.pending)
    for index, record in enumerate(records):
        for field_name, expected_value in expected.items():
            if not expected_value:
                continue
            actual_value = str(getattr(record, field_name, "") or "")
            if actual_value != expected_value:
                failures.append(f"{field_name}[{index}]")
    return tuple(dict.fromkeys(failures))


def load_durable_accounting_status(
    call_meter: ProposalCallMeterV1 | None,
) -> tuple[ProposalCallAccountingV1 | None, str]:
    """Load durable accounting with a typed, fail-closed status.

    Missing is the only non-error empty state.  Corruption, a foreign role,
    or a cross-run/revision identity mismatch is returned to the caller so it
    can refuse transport without overwriting the evidence that caused the
    refusal.
    """

    path = durable_accounting_path(call_meter)
    if path is None or not path.exists():
        return None, ""
    try:
        loaded = load_proposal_call_accounting(path)
    except Exception as exc:  # noqa: BLE001 - unknown spend must block
        return None, f"proposal_accounting_corrupt:{type(exc).__name__}"
    if call_meter is None:
        return loaded, ""
    failures = _accounting_identity_failures(loaded, call_meter)
    if failures:
        return None, "proposal_accounting_identity_mismatch:" + ",".join(failures)
    return loaded, ""


def load_durable_accounting(
    call_meter: ProposalCallMeterV1 | None,
) -> ProposalCallAccountingV1 | None:
    """Reload the tally a previous process left behind, if any.

    A resumed run must see the reservations of attempts that started and never
    settled; starting from an empty tally would erase exactly the evidence the
    durable ``started`` record exists to preserve.
    """

    loaded, _failure = load_durable_accounting_status(call_meter)
    return loaded


def carry_over_unsettled(
    accounting: ProposalCallAccountingV1,
    previous: ProposalCallAccountingV1 | None,
) -> ProposalCallAccountingV1:
    """Keep earlier unsettled attempts when a later tally replaces the file."""

    if previous is None or not previous.pending:
        return accounting
    known = {(row.call_id, row.attempt) for row in accounting.rows}
    carried = tuple(
        item
        for item in previous.pending
        if (item.call_id, item.attempt) not in known
    )
    if not carried:
        return accounting
    return ProposalCallAccountingV1(
        schema_version=accounting.schema_version,
        consumer_role=accounting.consumer_role,
        invocation_plan_membership=accounting.invocation_plan_membership,
        run_digest=accounting.run_digest,
        revision_id=accounting.revision_id,
        envelope_digest=accounting.envelope_digest,
        profile_digest=accounting.profile_digest,
        model_identity_digest=accounting.model_identity_digest,
        rows=accounting.rows,
        pending=(*carried, *accounting.pending),
    )


def load_proposal_call_accounting(path: Any) -> ProposalCallAccountingV1:
    return ProposalCallAccountingV1.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


__all__ = [
    "PROPOSAL_ACCOUNTING_IN_PLAN",
    "PROPOSAL_ACCOUNTING_RECORDED_ONLY",
    "PROPOSAL_CALL_ACCOUNTING_VERSION",
    "ProposalCallAccountingV1",
    "ProposalCallMeterV1",
    "ProposalCallPendingV1",
    "ProposalCallStatus",
    "ProposalCallTallyV1",
    "accounting_from_plan_trace",
    "build_budgeted_auxiliary_llm_caller",
    "load_proposal_call_accounting",
    "measure_proposal_request",
    "proposal_call_id",
    "carry_over_unsettled",
    "durable_accounting_path",
    "load_durable_accounting",
    "load_durable_accounting_status",
    "persist_proposal_call_state",
    "proposal_call_meter_from_envelope",
    "unified_authoring_ledger_root",
    "write_proposal_call_accounting",
]
