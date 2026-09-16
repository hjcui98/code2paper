"""R7: the default, budgeted narrative/section organization proposal caller.

The deterministic narrative builder always produces a validated plan.  This
module lets the owning Agent influence *organization* inside a closed-choice
contract: it receives the mechanism's intent, reader question, section roles
and the semantic projection of its own detail ids, and may return a grouping
(narrative) or an assignment of details to proven sections (multi-section).

The caller never decides evidence: the builder re-validates every returned id
against the closed sets, refuses unknown/duplicated/dropped ids, and falls back
to the deterministic organization.  Each attempt records the request, the
response and the consumption result so a rejection can be fed back to the owner
as repair input instead of being silently ignored.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

from code2paper.agentic.proposal_call_accounting import (
    PROPOSAL_ACCOUNTING_IN_PLAN,
    ProposalCallAccountingV1,
    ProposalCallMeterV1,
    ProposalCallPendingV1,
    load_durable_accounting,
    load_durable_accounting_status,
    measure_proposal_request,
    persist_proposal_call_state,
    proposal_call_id,
    unified_authoring_ledger_root,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.role_config import (
    METHOD_PROPOSITION_ARCHITECT,
    apply_role_config,
)
from code2paper.schemas import LLMConfig


PROPOSAL_PROMPT_TEMPLATE_ID = "agentic_method_narrative_organization_v1"


def _closed_proposal_schema(kind: str) -> dict[str, Any]:
    if kind == "section_organization":
        entries = {
            "type": "object",
            "properties": {
                "section_id": {"type": "string"},
                "detail_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["section_id", "detail_ids"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "section_id": {"type": "string"},
                "mechanism_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "mechanism_id": {"type": "string"},
                "sections": {"type": "array", "items": entries},
            },
            "required": ["sections"],
            "additionalProperties": False,
        }
    entries = {
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "detail_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["role", "detail_ids"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "mechanism_id": {"type": "string"},
            "paragraphs": {"type": "array", "items": entries},
        },
        "required": ["mechanism_id", "paragraphs"],
        "additionalProperties": False,
    }


def _render_prompt(
    *,
    kind: str,
    mechanism_id: str,
    detail_ids: Sequence[str],
    section_ids: Sequence[str],
    role_names: Sequence[str],
    context: Mapping[str, Any] | None,
    repair_failures: Sequence[str],
) -> str:
    context = context or {}
    lines = [
        "You organize one mechanism's Method section. Decide only how the",
        "existing detail ids are grouped; never invent, drop or rename an id.",
        "",
        f"kind: {kind}",
        f"mechanism_id: {mechanism_id}",
        f"mechanism_name: {context.get('mechanism_name', '')}",
        f"scientific_role: {context.get('scientific_role', '')}",
        f"reader_question: {context.get('reader_question', '')}",
        f"purpose: {context.get('purpose', '')}",
        "",
        "closed detail ids (each must appear exactly once):",
    ]
    for detail in context.get("details") or ():
        lines.append(
            "  - {detail_id} | role={role} | importance={importance} | "
            "atom={semantic_atom}".format(
                detail_id=detail.get("detail_id", ""),
                role=detail.get("role", ""),
                importance=detail.get("importance", ""),
                semantic_atom=str(detail.get("semantic_atom", ""))[:160],
            )
        )
    if not context.get("details"):
        lines.extend(f"  - {detail_id}" for detail_id in detail_ids)
    if kind == "section_organization":
        lines.extend([
            "",
            "proven section ids (each must argue at least one detail):",
        ])
        for section in context.get("sections") or ():
            lines.append(
                "  - {section_id} | heading={heading}".format(
                    section_id=section.get("section_id", ""),
                    heading=section.get("heading", ""),
                )
            )
        if not context.get("sections"):
            lines.extend(f"  - {section_id}" for section_id in section_ids)
        lines.extend([
            "",
            'Return JSON: {"mechanism_id": "...", "sections": '
            '[{"section_id": "...", "detail_ids": ["..."]}]}',
        ])
    else:
        lines.extend([
            "",
            "allowed paragraph roles (choose from this closed set):",
            *(f"  - {role}" for role in role_names),
            "",
            'Return JSON: {"mechanism_id": "...", "paragraphs": '
            '[{"role": "...", "detail_ids": ["..."]}]}',
        ])
    if repair_failures:
        lines.extend([
            "",
            "Your previous answer was rejected for these reasons; correct them:",
            *(f"  - {failure}" for failure in repair_failures),
        ])
    return "\n".join(lines)


def _parse_response(response: Any) -> dict[str, Any]:
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _request_identity(request: Any) -> str:
    """Return the real request identity (``LLMRequest.input_hash``)."""

    return str(
        getattr(request, "input_hash", "")
        or getattr(request, "prompt_digest", "")
        or getattr(request, "input_digest", "")
        or ""
    )


def build_narrative_organization_proposal_caller(
    llm_config: LLMConfig | None,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    call_meter: ProposalCallMeterV1 | None = None,
) -> Callable[..., dict[str, Any]] | None:
    """Return the default proposal caller, or ``None`` when no model is usable.

    The caller is bounded: one request per attempt, a closed-id schema, and a
    recorded trace of the request, the response and whether the builder could
    consume it.  A configuration without a provider key yields ``None`` so the
    deterministic product path keeps ``proposal_status="not_requested"``.

    With ``call_meter`` the caller also *measures* every attempt: the complete
    serialized request (prompt + payload + closed schema) is measured with the
    run's declared meter before the call, and the attempt is tallied as
    planned/reserved/measured/spent/unsettled.  Without it the historical
    "recorded but not measured" state is preserved rather than faked.
    """

    if llm_config is None:
        return None
    if llm_caller is None and not has_provider_api_key(llm_config):
        return None
    config = apply_role_config(llm_config, METHOD_PROPOSITION_ARCHITECT)
    if llm_caller is None:
        from code2paper.llm.capabilities import (
            StructuredResponseMode,
            load_capability_profile,
        )
        from code2paper.llm.client import LLMClient

        profile = load_capability_profile(
            provider=getattr(config.provider, "value", str(config.provider)),
            model=config.model,
        ).model_copy(update={
            "response_mode": StructuredResponseMode.NATIVE_JSON_SCHEMA,
        })
        caller: Callable[[LLMConfig, LLMRequest], LLMResponse] = (
            lambda cfg, request: LLMClient(
                cfg, capability_profile=profile
            ).complete(request)
        )
    else:
        caller = llm_caller

    traces: list[dict[str, Any]] = []
    accounting_load_failure = ""
    # A resumed run inherits the tally the previous process left on disk: the
    # reservations of attempts that started and never settled stay visible,
    # and attempt numbering continues instead of restarting at 1.  A corrupt
    # or foreign file is *not* replaced by an empty tally; the caller blocks.
    if call_meter is not None:
        accounting, accounting_load_failure = load_durable_accounting_status(
            call_meter
        )
        if accounting is None:
            accounting = ProposalCallAccountingV1(
                consumer_role=call_meter.consumer_role,
                invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
                run_digest=call_meter.run_digest,
                revision_id=call_meter.revision_id,
                envelope_digest=call_meter.envelope_digest,
                profile_digest=call_meter.profile_digest,
                model_identity_digest=call_meter.model_identity_digest,
            )
        if call_meter.budget_required and call_meter.accounting_root is None:
            accounting_load_failure = accounting_load_failure or (
                "proposal_accounting_root_missing"
            )
    else:
        accounting = None

    def proposal_caller(
        mechanism_id: str,
        detail_ids: Sequence[str],
        section_ids: Sequence[str],
        role_names: Sequence[str],
        *,
        kind: str = "narrative_organization",
        context: Mapping[str, Any] | None = None,
        repair_failures: Sequence[str] = (),
        **_kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal accounting
        prompt = _render_prompt(
            kind=kind,
            mechanism_id=str(mechanism_id),
            detail_ids=detail_ids,
            section_ids=section_ids,
            role_names=role_names,
            context=context,
            repair_failures=repair_failures,
        )
        request = LLMRequest(
            prompt_template_id=PROPOSAL_PROMPT_TEMPLATE_ID,
            prompt=prompt,
            input_payload={
                "kind": kind,
                "mechanism_id": str(mechanism_id),
                "detail_ids": list(detail_ids),
                "section_ids": list(section_ids),
                "role_names": list(role_names),
                "repair_failures": list(repair_failures),
            },
            schema_name=(
                "NarrativeSectionOrganizationProposalV1"
                if kind == "section_organization"
                else "NarrativeOrganizationProposalV1"
            ),
            response_json_schema=_closed_proposal_schema(kind),
        )
        response: Any = None
        error = accounting_load_failure
        measured_tokens = 0
        measurement_parts: dict[str, int] = {}
        pending: ProposalCallPendingV1 | None = None
        attempt_number = 0
        sent_to_caller = False
        start_persisted = False

        def _finish_accounting(*, sent: bool, finish_error: str) -> None:
            """Settle the pending row while retaining durable uncertainty."""

            nonlocal accounting, pending, error
            if accounting is None or pending is None or call_meter is None:
                return
            try:
                accounting = accounting.finish(
                    pending,
                    status="failed" if finish_error else "completed",
                    measured_input_tokens=measured_tokens,
                    measurement_parts=measurement_parts,
                    meter=call_meter.meter,
                    model_identity=call_meter.model_identity,
                    error=finish_error,
                    sent_to_caller=sent,
                )
            except Exception as exc:  # noqa: BLE001 - preserve the pending row
                error = error or f"proposal_accounting_finish_failed:{type(exc).__name__}"
                return
            pending = None
            try:
                persist_proposal_call_state(call_meter, accounting, strict=True)
            except Exception as exc:  # noqa: BLE001 - disk state is the authority
                error = error or (
                    "proposal_accounting_finish_persist_failed:"
                    f"{type(exc).__name__}"
                )

        if accounting is not None and call_meter is not None and not error:
            attempt = 1 + sum(
                1
                for row in accounting.rows
                if row.proposal_kind == str(kind)
                and row.target_id == str(mechanism_id)
            ) + sum(
                1
                for item in accounting.pending
                if item.proposal_kind == str(kind)
                and item.target_id == str(mechanism_id)
            )
            attempt_number = attempt
            try:
                accounting, pending = accounting.begin(
                    call_id=proposal_call_id(
                        prompt_template_id=PROPOSAL_PROMPT_TEMPLATE_ID,
                        proposal_kind=str(kind),
                        target_id=str(mechanism_id),
                        attempt=attempt,
                    ),
                    proposal_kind=str(kind),
                    target_id=str(mechanism_id),
                    attempt=attempt,
                    request_input_hash=_request_identity(request),
                    planned_input_tokens=call_meter.planned_input_tokens,
                    reserved_input_tokens=(
                        call_meter.reserved_input_tokens
                        or call_meter.planned_input_tokens
                    ),
                )
                # Durable ``started``: the reservation is on disk *before* the
                # request leaves this process, so an interrupt between start
                # and settlement is visible on resume.
                persist_proposal_call_state(call_meter, accounting, strict=True)
                start_persisted = True
            except Exception as exc:  # noqa: BLE001 - never send without a start
                error = (
                    "proposal_accounting_start_persist_failed:"
                    f"{type(exc).__name__}"
                )

            if start_persisted and pending is not None:
                try:
                    measured_tokens, measurement_parts = measure_proposal_request(
                        request, call_meter=call_meter
                    )
                except Exception as exc:  # noqa: BLE001 — measurement is mandatory
                    error = f"measurement_failed:{type(exc).__name__}:{exc}"
                if not error and (
                    call_meter.max_input_tokens > 0
                    and measured_tokens > call_meter.max_input_tokens
                ):
                    error = (
                        "proposal_call_budget_exceeded:"
                        f"{measured_tokens}>{call_meter.max_input_tokens}"
                    )
                if not error and call_meter.budget_required:
                    from code2paper.agentic.unified_invocation_ledger import (
                        check_run_budget_before_send,
                    )

                    budget_view = SimpleNamespace(
                        max_calls_by_role={
                            call_meter.consumer_role: call_meter.max_calls
                        },
                        max_total_input_tokens=call_meter.max_total_input_tokens,
                        max_input_tokens_by_role={
                            call_meter.consumer_role: (
                                call_meter.max_role_input_tokens
                                or call_meter.max_total_input_tokens
                            )
                        },
                    )
                    budget_failures = check_run_budget_before_send(
                        unified_authoring_ledger_root(call_meter.accounting_root),
                        budget_view,
                        role=call_meter.consumer_role,
                        request_input_tokens=measured_tokens,
                        current_reserved_input_tokens=(
                            call_meter.reserved_input_tokens
                            or call_meter.planned_input_tokens
                        ),
                        current_attempt_recorded=True,
                    )
                    if budget_failures:
                        error = ";".join(budget_failures)

                if error:
                    _finish_accounting(sent=False, finish_error=error)

        if not error and (accounting is None or call_meter is None):
            # This is the historical explicitly recorded-only lane.  Product
            # wiring supplies a strict meter; direct compatibility callers may
            # still use this branch, but it never claims measured spend.
            try:
                response = caller(config, request)
                sent_to_caller = True
            except Exception as exc:  # noqa: BLE001 — a failed proposal is not authority
                error = f"{type(exc).__name__}:{str(exc)[:200]}"
                sent_to_caller = True
        elif not error and pending is not None and start_persisted:
            try:
                response = caller(config, request)
                sent_to_caller = True
            except Exception as exc:  # noqa: BLE001 — a failed proposal is not authority
                error = f"{type(exc).__name__}:{str(exc)[:200]}"
                sent_to_caller = True

        if response is not None and getattr(response, "blocked_reason", ""):
            error = error or str(getattr(response, "blocked_reason", ""))
        payload = _parse_response(response) if response is not None else {}
        if pending is not None and accounting is not None and call_meter is not None:
            _finish_accounting(sent=sent_to_caller, finish_error=error)
        traces.append({
            "kind": kind,
            "mechanism_id": str(mechanism_id),
            # ``LLMRequest`` exposes the request identity as ``input_hash``;
            # the earlier attribute names never existed, so the trace recorded
            # an empty digest for every attempt.  ``request_prompt_digest`` is
            # kept as the same value for older readers.
            "request_input_hash": _request_identity(request),
            "request_prompt_digest": _request_identity(request),
            "planned_input_tokens": int(
                getattr(request, "estimated_input_tokens", 0) or 0
            ),
            "accounted_planned_input_tokens": int(
                call_meter.planned_input_tokens if call_meter is not None else 0
            ),
            "reserved_input_tokens": int(
                (
                    call_meter.reserved_input_tokens
                    or call_meter.planned_input_tokens
                )
                if call_meter is not None
                else 0
            ),
            "measured_input_tokens": int(measured_tokens),
            "measurement_parts": dict(measurement_parts),
            "sent_to_caller": bool(sent_to_caller),
            "attempt": int(attempt_number),
            "model_identity": (
                call_meter.model_identity if call_meter is not None else ""
            ),
            "input_payload": dict(request.input_payload),
            "response_text_excerpt": str(
                getattr(response, "text", "") or ""
            )[:400],
            "parsed_mechanism_id": str(payload.get("mechanism_id") or ""),
            "repair_failures": list(repair_failures),
            "error": error,
        })
        proposal_caller.accounting = accounting  # type: ignore[attr-defined]
        return payload

    proposal_caller.traces = traces  # type: ignore[attr-defined]
    #: The running tally; a caller without a meter keeps ``None`` so no consumer
    #: can mistake "recorded" for "measured".
    proposal_caller.accounting = accounting  # type: ignore[attr-defined]
    return proposal_caller


__all__ = [
    "PROPOSAL_PROMPT_TEMPLATE_ID",
    "build_narrative_organization_proposal_caller",
]
