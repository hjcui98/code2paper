"""Tests for proposal-call accounting (round-4 review §7.5).

A proposal call is not authority, but it is a real request: the run must be
able to say what it planned, reserved, measured, spent and left unsettled,
including failed attempts and resumed runs.  These tests also pin the honest
boundary: without a meter (or without the tokenizer a ``model_tokenizer`` meter
requires) the calls stay *recorded only* rather than measured by another rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from code2paper.agentic.narrative_organization_proposal import (
    build_narrative_organization_proposal_caller,
)
from code2paper.agentic.proposal_call_accounting import (
    PROPOSAL_ACCOUNTING_IN_PLAN,
    PROPOSAL_ACCOUNTING_RECORDED_ONLY,
    ProposalCallAccountingV1,
    ProposalCallMeterV1,
    build_budgeted_auxiliary_llm_caller,
    carry_over_unsettled,
    durable_accounting_path,
    load_durable_accounting,
    load_durable_accounting_status,
    load_proposal_call_accounting,
    measure_proposal_request,
    proposal_call_meter_from_envelope,
    write_proposal_call_accounting,
)
from code2paper.agentic.unified_context_models import UnifiedTokenMeterV1
from code2paper.schemas import LLMConfig, LLMProvider


CONSERVATIVE_METER = UnifiedTokenMeterV1(
    method="conservative_utf8_bytes_div_4",
    measurement_basis="canonical json bytes / 4",
    bytes_per_token=4,
)


def _config() -> LLMConfig:
    return LLMConfig(provider=LLMProvider.NONE, model="none")


def stated_tokens(tokenizer: _Tokenizer, request: Any) -> int:
    """The same rule the production meter applies to a tokenizer."""

    return sum(
        len(tokenizer.encode(str(value)))
        for value in (
            request.prompt,
            request.input_payload,
            request.response_json_schema,
        )
    )


def _meter(**overrides) -> ProposalCallMeterV1:
    payload = {
        "consumer_role": "method_proposition_architect",
        "meter": CONSERVATIVE_METER,
        "model_identity": "qwen36-27b-nvfp4",
        "planned_input_tokens": 1000,
        "reserved_input_tokens": 1200,
    }
    payload.update(overrides)
    return ProposalCallMeterV1(**payload)


class _Tokenizer:
    identity = "qwen36-27b-nvfp4"

    def encode(self, text: str) -> list[int]:
        return list(range(len(str(text).split())))


def _strict_envelope(
    *,
    max_calls: int = 4,
    max_total: int = 2000,
    run_digest: str = "sha256:strict-run",
    token_meter: UnifiedTokenMeterV1 | None = None,
):
    """Build the smallest explicit extra-role contract used by S2 tests."""

    from code2paper.agentic.unified_context_compiler import (
        build_run_invocation_budget_envelope_v1,
        read_unified_budget_profile,
        read_unified_extra_roles,
    )

    env = {
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": str(max_total),
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "500",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "3",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "0",
        "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS": "10",
        "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE": "20",
        "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE": "0",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS": "0",
        "CODE2PAPER_UNIFIED_EXTRA_ROLES": "method_proposition_architect",
        "CODE2PAPER_UNIFIED_MAX_METHOD_PROPOSITION_ARCHITECT_CALLS": str(max_calls),
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "64",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_METHOD_PROPOSITION_ARCHITECT": "400",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "0",
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        env[f"CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_{role.upper()}"] = "100"
        env[f"CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_{role.upper()}"] = "400"
        env[f"CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_{role.upper()}"] = "0"
    profile = read_unified_budget_profile(env)
    profile.update(read_unified_extra_roles(env))
    return build_run_invocation_budget_envelope_v1(
        profile_budget=profile,
        model_capabilities={"context_tokens": 4096},
        run_digest=run_digest,
        profile_digest="sha256:strict-profile",
        model_identity_digest="sha256:strict-model",
        token_meter=token_meter,
    )


# ---------------------------------------------------------------------------
# Tally arithmetic
# ---------------------------------------------------------------------------


def test_accounting_distinguishes_planned_reserved_measured_spent_unsettled() -> None:
    accounting = ProposalCallAccountingV1(
        consumer_role="method_proposition_architect",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    accounting, pending = accounting.begin(
        call_id="proposal-call:a:1",
        proposal_kind="narrative_organization",
        target_id="mech-1",
        planned_input_tokens=1000,
        reserved_input_tokens=1200,
    )
    # Started and not finished: the reservation is unsettled, nothing is spent.
    assert accounting.unsettled_input_tokens() == 1200
    assert accounting.unsettled_call_ids() == ("proposal-call:a:1",)
    assert accounting.spent_input_tokens() == 0

    accounting = accounting.finish(
        pending,
        status="completed",
        measured_input_tokens=900,
        meter=CONSERVATIVE_METER,
        model_identity="qwen36-27b-nvfp4",
    )
    totals = accounting.totals()
    assert totals["planned_input_tokens"] == 1000
    assert totals["reserved_input_tokens"] == 1200
    assert totals["measured_input_tokens"] == 900
    assert totals["spent_input_tokens"] == 900
    assert totals["unsettled_input_tokens"] == 0
    assert totals["call_count"] == 1
    assert totals["failed_call_count"] == 0
    assert totals["invocation_plan_membership"] == PROPOSAL_ACCOUNTING_IN_PLAN


def test_failed_attempt_is_charged_conservatively_and_never_unsettled() -> None:
    accounting = ProposalCallAccountingV1(consumer_role="role")
    accounting, pending = accounting.begin(
        call_id="proposal-call:b:1", planned_input_tokens=500
    )
    accounting = accounting.finish(
        pending, status="failed", measured_input_tokens=450, error="provider_down"
    )

    row = accounting.rows[0]
    assert row.status == "failed"
    assert row.error == "provider_down"
    # The request was handed to the caller, so its measured input is charged.
    assert row.spent_input_tokens == 450
    assert accounting.unsettled_input_tokens() == 0
    assert accounting.failed_call_ids() == ("proposal-call:b:1",)


def test_duplicate_call_identity_is_refused() -> None:
    accounting = ProposalCallAccountingV1(consumer_role="role")
    accounting, pending = accounting.begin(call_id="proposal-call:c:1")
    with pytest.raises(ValueError, match="already pending"):
        accounting.begin(call_id="proposal-call:c:1")
    accounting = accounting.finish(pending, status="completed")
    with pytest.raises(ValueError, match="already finished"):
        accounting.begin(call_id="proposal-call:c:1")
    with pytest.raises(ValueError, match="not pending"):
        accounting.finish(pending, status="completed")


def test_accounting_survives_a_resume_with_unsettled_tokens(tmp_path: Path) -> None:
    """A resumed run recomputes what the previous context left unsettled."""

    accounting = ProposalCallAccountingV1(
        consumer_role="role",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    accounting, finished_pending = accounting.begin(
        call_id="proposal-call:done:1", planned_input_tokens=300
    )
    accounting = accounting.finish(
        finished_pending, status="completed", measured_input_tokens=280
    )
    accounting, interrupted = accounting.begin(
        call_id="proposal-call:interrupted:1",
        planned_input_tokens=700,
        reserved_input_tokens=800,
    )
    path = write_proposal_call_accounting(tmp_path, accounting)

    restored = load_proposal_call_accounting(path)
    assert restored.content_digest == accounting.content_digest
    assert restored.unsettled_input_tokens() == 800
    assert restored.unsettled_call_ids() == ("proposal-call:interrupted:1",)
    assert restored.spent_input_tokens() == 280
    # The interrupted attempt can only be *finished*; it cannot be restarted
    # under the same identity without a new attempt number.
    restored = restored.finish(
        restored.pending[0], status="failed", measured_input_tokens=800
    )
    assert restored.unsettled_input_tokens() == 0
    assert restored.spent_input_tokens() == 1080


def test_measurement_uses_the_declared_meter_and_requires_its_tokenizer() -> None:
    request = SimpleNamespace(
        prompt="score the candidates",
        input_payload={"mechanism_id": "mech-1"},
        response_json_schema={"type": "object"},
    )
    measured, parts = measure_proposal_request(
        request, call_meter=_meter()
    )
    assert measured == sum(parts.values()) > 0
    assert set(parts) == {"prompt", "input_payload", "response_schema"}

    tokenizer_meter = UnifiedTokenMeterV1(
        method="model_tokenizer", tokenizer_identity="qwen36-27b-nvfp4"
    )
    with pytest.raises(ValueError, match="requires the tokenizer"):
        _meter(meter=tokenizer_meter)
    tokenizer = _Tokenizer()
    measured_tokens, tokenizer_parts = measure_proposal_request(
        request,
        call_meter=_meter(meter=tokenizer_meter, tokenizer=tokenizer),
    )
    assert stated_tokens(tokenizer, request) == measured_tokens == sum(
        tokenizer_parts.values()
    )


def test_envelope_meter_refuses_to_fake_a_tokenizer_measurement() -> None:
    envelope = SimpleNamespace(
        token_meter=CONSERVATIVE_METER,
        model_identity_digest="sha256:model",
        max_request_input_tokens_by_role={"method_proposition_architect": 1500},
    )
    meter = proposal_call_meter_from_envelope(
        envelope, consumer_role="method_proposition_architect"
    )
    assert meter is not None
    assert meter.planned_input_tokens == 1500
    assert meter.reserved_input_tokens == 1500

    tokenizer_envelope = SimpleNamespace(
        token_meter=UnifiedTokenMeterV1(
            method="model_tokenizer", tokenizer_identity="qwen36-27b-nvfp4"
        ),
        model_identity_digest="sha256:model",
        max_request_input_tokens_by_role={},
    )
    assert (
        proposal_call_meter_from_envelope(
            tokenizer_envelope, consumer_role="method_proposition_architect"
        )
        is None
    )
    assert proposal_call_meter_from_envelope(None, consumer_role="r") is None


# ---------------------------------------------------------------------------
# Caller integration
# ---------------------------------------------------------------------------


def test_caller_measures_every_attempt_and_records_failures() -> None:
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(
            text='{"mechanism_id": "mech-1"}'
        ),
        call_meter=_meter(),
    )
    assert caller is not None
    payload = caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    assert payload == {"mechanism_id": "mech-1"}
    accounting = caller.accounting
    assert accounting is not None
    assert accounting.invocation_plan_membership == PROPOSAL_ACCOUNTING_IN_PLAN
    assert len(accounting.rows) == 1
    row = accounting.rows[0]
    assert row.status == "completed"
    assert row.measured_input_tokens > 0
    assert row.planned_input_tokens == 1000
    assert row.reserved_input_tokens == 1200
    assert row.request_input_hash
    assert row.meter is not None

    # A second attempt for the same target gets its own attempt number instead
    # of overwriting the first tally.
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    assert [item.attempt for item in caller.accounting.rows] == [1, 2]
    assert caller.accounting.totals()["call_count"] == 2

    def _boom(cfg, request):
        raise RuntimeError("provider_down")

    failing = build_narrative_organization_proposal_caller(
        _config(), llm_caller=_boom, call_meter=_meter()
    )
    assert failing is not None
    failing("mech-2", ["detail-2"], ["sec-2"], ["writer"])
    failed_row = failing.accounting.rows[0]
    assert failed_row.status == "failed"
    assert "provider_down" in failed_row.error
    assert failed_row.spent_input_tokens == failed_row.measured_input_tokens


def test_caller_without_a_meter_stays_recorded_only() -> None:
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(text="{}"),
    )
    assert caller is not None
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    assert caller.accounting is None
    row = caller.traces[0]
    assert row["measured_input_tokens"] == 0
    assert row["request_input_hash"]
    assert PROPOSAL_ACCOUNTING_RECORDED_ONLY == (
        "recorded_not_in_invocation_plan"
    )


def test_measurement_failure_is_recorded_and_does_not_reach_the_model() -> None:
    calls: list[Any] = []
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: calls.append(request),
        call_meter=_meter(
            meter=UnifiedTokenMeterV1(
                method="model_tokenizer", tokenizer_identity="qwen36-27b-nvfp4"
            ),
            tokenizer=object(),
        ),
    )
    assert caller is not None
    payload = caller("mech-3", ["detail-3"], ["sec-3"], ["writer"])

    assert payload == {}
    assert calls == []
    row = caller.accounting.rows[0]
    assert row.status == "failed"
    assert row.error.startswith("measurement_failed:")
    assert row.measured_input_tokens == 0


def test_narrative_plan_trace_reports_measured_totals(tmp_path: Path) -> None:
    """The plan trace carries the measured tally, not a bare marker."""

    from code2paper.agentic.method_architect import build_narrative_plan_v3

    contexts = SimpleNamespace(contexts=[])
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(text="{}"),
        call_meter=_meter(),
    )
    plan, trace = build_narrative_plan_v3(
        contexts=contexts,
        proposal_caller=caller,
    )
    assert plan is not None
    assert trace["proposal_call_accounting"] == PROPOSAL_ACCOUNTING_IN_PLAN
    totals = trace["proposal_call_totals"]
    assert set(totals) >= {
        "planned_input_tokens",
        "reserved_input_tokens",
        "measured_input_tokens",
        "spent_input_tokens",
        "unsettled_input_tokens",
    }
    assert trace["proposal_call_accounting_digest"]
    assert isinstance(trace.get("proposal_call_rows", []), list)
    assert json.dumps(totals, sort_keys=True)


def test_plan_trace_rebuilds_the_durable_accounting_artifact(tmp_path: Path) -> None:
    """The writer-side persistence path rebuilds the tally from the trace."""

    from code2paper.agentic.proposal_call_accounting import (
        accounting_from_plan_trace,
        load_proposal_call_accounting,
        write_proposal_call_accounting,
    )

    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(text="{}"),
        call_meter=_meter(),
    )
    assert caller is not None
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    measured = caller.accounting
    assert measured is not None and measured.rows
    # This is the shape ``build_narrative_plan_v3`` records on its trace.
    trace = {
        "proposal_call_accounting": PROPOSAL_ACCOUNTING_IN_PLAN,
        "proposal_call_rows": [row.model_dump(mode="json") for row in measured.rows],
        "proposal_call_totals": measured.totals(),
    }

    accounting = accounting_from_plan_trace(trace)
    assert accounting is not None
    assert accounting.rows
    assert accounting.totals()["measured_input_tokens"] > 0
    assert accounting.invocation_plan_membership == PROPOSAL_ACCOUNTING_IN_PLAN
    path = write_proposal_call_accounting(tmp_path, accounting)
    restored = load_proposal_call_accounting(path)
    assert restored.content_digest == accounting.content_digest
    assert restored.totals() == accounting.totals()

    # A trace without measured rows must not fabricate a tally.
    assert accounting_from_plan_trace({"proposal_call_accounting": "recorded"}) is None
    assert accounting_from_plan_trace({}) is None


def test_writer_artifact_path_matches_the_registered_output_name(tmp_path: Path) -> None:
    """The persistence helper and the registered output name must agree."""

    from code2paper.agentic.proposal_call_accounting import (
        ProposalCallAccountingV1,
        write_proposal_call_accounting,
    )
    from code2paper.core.output_names import method_output

    path = write_proposal_call_accounting(
        tmp_path, ProposalCallAccountingV1(consumer_role="role")
    )
    assert path == method_output(tmp_path, "proposal_call_accounting_v1")


def test_run_summary_reports_only_measured_proposal_accounting(tmp_path: Path) -> None:
    """The run summary claims metering only when a measured tally exists."""

    from code2paper.agentic.autonomous_method_agent import (
        _proposal_accounting_summary,
    )
    from code2paper.agentic.proposal_call_accounting import (
        ProposalCallAccountingV1,
        write_proposal_call_accounting,
    )

    # No artifact -> no keys at all.
    assert _proposal_accounting_summary({}) == {}
    # A dangling path is not a reason to invent or fail anything.
    assert _proposal_accounting_summary(
        {"proposal_call_accounting_v1": str(tmp_path / "missing.json")}
    ) == {}

    accounting = ProposalCallAccountingV1(consumer_role="role")
    accounting, pending = accounting.begin(
        call_id="proposal-call:summary:1", planned_input_tokens=100
    )
    accounting = accounting.finish(
        pending, status="completed", measured_input_tokens=90
    )
    path = write_proposal_call_accounting(tmp_path, accounting)
    keys = _proposal_accounting_summary(
        {"proposal_call_accounting_v1": str(path)}
    )
    assert keys["proposal_call_accounting"]["measured_input_tokens"] == 90
    assert keys["proposal_call_accounting"]["spent_input_tokens"] == 90
    assert keys["proposal_call_accounting"]["unsettled_input_tokens"] == 0
    assert keys["proposal_call_accounting_digest"] == accounting.content_digest


def test_proposal_role_can_opt_into_the_run_budget_without_widening_defaults() -> None:
    """`CODE2PAPER_UNIFIED_EXTRA_ROLES` widens the contract explicitly only."""

    from code2paper.agentic.unified_context_compiler import (
        build_run_invocation_budget_envelope_v1,
        read_unified_budget_profile,
        read_unified_extra_roles,
    )

    base = {
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "2000000",
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "500",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "3",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "0",
        "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS": "10",
        "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE": "20",
        "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE": "0",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS": "0",
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        base[f"CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_{role.upper()}"] = "100"
        base[f"CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_{role.upper()}"] = "400"
        base[f"CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_{role.upper()}"] = "0"

    def envelope(env: dict[str, str]):
        profile = read_unified_budget_profile(env)
        profile.update(read_unified_extra_roles(env))
        return build_run_invocation_budget_envelope_v1(
            profile_budget=profile,
            model_capabilities={"context_tokens": 4096},
            run_digest="sha256:run",
            profile_digest="sha256:profile",
            model_identity_digest="sha256:model",
        )

    default = envelope(base)
    assert sorted(default.max_calls_by_role) == [
        "binder", "formalizer", "realizer", "writer",
    ]

    opted_in = envelope(base | {
        "CODE2PAPER_UNIFIED_EXTRA_ROLES": "method_proposition_architect",
        "CODE2PAPER_UNIFIED_MAX_METHOD_PROPOSITION_ARCHITECT_CALLS": "6",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "64",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_METHOD_PROPOSITION_ARCHITECT": "1024",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "0",
    })
    assert "method_proposition_architect" in opted_in.max_calls_by_role
    budget = opted_in.request_budget_by_role["method_proposition_architect"]
    assert budget.output_token_reserve == 64
    # The cap must fit a real serialized proposal request (prompt + payload
    # + closed schema); the illustrative declaration is deliberately roomy.
    assert opted_in.max_request_input_tokens_by_role[
        "method_proposition_architect"
    ] == 1024
    # Opting in is a real contract change; the default envelope stays as is.
    assert opted_in.content_digest != default.content_digest

    # A half-declared role fails closed instead of silently defaulting.
    incomplete = dict(base)
    incomplete["CODE2PAPER_UNIFIED_EXTRA_ROLES"] = "method_proposition_architect"
    incomplete["CODE2PAPER_UNIFIED_MAX_METHOD_PROPOSITION_ARCHITECT_CALLS"] = "6"
    with pytest.raises(Exception, match="missing budget fields"):
        envelope(incomplete)


# ---------------------------------------------------------------------------
# Durable started / pre-send rejection (node B metering closure)
# ---------------------------------------------------------------------------


def test_started_attempt_is_durable_before_the_request_is_sent(
    tmp_path: Path,
) -> None:
    """The tally on disk has the pending row while the model call is running."""

    observed: list[ProposalCallAccountingV1 | None] = []

    def _slow(cfg, request):
        observed.append(load_proposal_call_accounting(_path))
        return SimpleNamespace(text='{"mechanism_id": "mech-1"}')

    meter = _meter(accounting_root=tmp_path)
    _path = durable_accounting_path(meter)
    assert _path is not None
    caller = build_narrative_organization_proposal_caller(
        _config(), llm_caller=_slow, call_meter=meter
    )
    assert caller is not None
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])

    # Inside the call the durable tally already carried the reservation.
    assert observed and observed[0] is not None
    assert observed[0].unsettled_call_ids() == (
        "proposal-call:agentic_method_narrative_organization_v1:"
        "narrative_organization:mech-1:1",
    )
    assert observed[0].spent_input_tokens() == 0

    # After the call the same file holds the settled row and nothing pending.
    settled = load_proposal_call_accounting(_path)
    assert settled.pending == ()
    assert [row.status for row in settled.rows] == ["completed"]


def test_resume_sees_unsettled_attempt_and_continues_attempt_numbering(
    tmp_path: Path,
) -> None:
    """An interrupted process leaves evidence; the resumed run keeps it."""

    meter = _meter(accounting_root=tmp_path)
    interrupted = ProposalCallAccountingV1(
        consumer_role="method_proposition_architect",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    interrupted, _pending = interrupted.begin(
        call_id="proposal-call:agentic_method_narrative_organization_v1:"
        "narrative_organization:mech-1:1",
        proposal_kind="narrative_organization",
        target_id="mech-1",
        planned_input_tokens=1000,
        reserved_input_tokens=1200,
    )
    write_proposal_call_accounting(tmp_path, interrupted)

    reloaded = load_durable_accounting(meter)
    assert reloaded is not None
    assert reloaded.unsettled_input_tokens() == 1200

    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(
            text='{"mechanism_id": "mech-1"}'
        ),
        call_meter=meter,
    )
    assert caller is not None
    assert caller.accounting.unsettled_call_ids() == (
        "proposal-call:agentic_method_narrative_organization_v1:"
        "narrative_organization:mech-1:1",
    )
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    # The resumed attempt does not reuse the interrupted identity.
    assert [row.attempt for row in caller.accounting.rows] == [2]
    assert caller.accounting.totals()["unsettled_call_ids"] == [
        "proposal-call:agentic_method_narrative_organization_v1:"
        "narrative_organization:mech-1:1"
    ]


def test_durable_accounting_is_scoped_to_the_declared_role(tmp_path: Path) -> None:
    meter = _meter(accounting_root=tmp_path)
    other = ProposalCallAccountingV1(
        consumer_role="someone_else",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    write_proposal_call_accounting(tmp_path, other)
    # A foreign tally is not adopted: "someone else's tokens" is not this run.
    assert load_durable_accounting(meter) is None


def test_carry_over_unsettled_keeps_rows_a_later_tally_would_drop() -> None:
    previous = ProposalCallAccountingV1(
        consumer_role="method_proposition_architect",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    previous, _pending = previous.begin(
        call_id="proposal-call:a:1",
        proposal_kind="narrative_organization",
        target_id="mech-1",
        reserved_input_tokens=700,
    )
    current = ProposalCallAccountingV1(
        consumer_role="method_proposition_architect",
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
    )
    merged = carry_over_unsettled(current, previous)
    assert merged.unsettled_call_ids() == ("proposal-call:a:1",)
    # Without a previous tally nothing changes.
    assert carry_over_unsettled(current, None).pending == ()


def test_over_cap_request_is_refused_before_it_reaches_the_model() -> None:
    calls: list[Any] = []
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: calls.append(request),
        call_meter=_meter(max_input_tokens=8),
    )
    assert caller is not None
    payload = caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    assert payload == {}
    # The model was never called, and the refusal is recorded without being
    # misreported as provider spend.
    assert calls == []
    row = caller.accounting.rows[0]
    assert row.status == "failed"
    assert row.error.startswith("proposal_call_budget_exceeded:")
    assert row.measured_input_tokens > 8
    assert row.spent_input_tokens == 0
    assert caller.traces[0]["error"].startswith("proposal_call_budget_exceeded:")

    # A declared cap that the request fits leaves the normal path untouched.
    ok = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: SimpleNamespace(
            text='{"mechanism_id": "mech-1"}'
        ),
        call_meter=_meter(max_input_tokens=10**6),
    )
    assert ok is not None
    assert ok("mech-1", ["detail-1"], ["sec-1"], ["writer"]) == {
        "mechanism_id": "mech-1"
    }
    assert ok.accounting.rows[0].status == "completed"


def test_envelope_meter_carries_the_declared_cap_and_durable_root(
    tmp_path: Path,
) -> None:
    """The run's per-request cap is the meter's pre-send bound."""

    from code2paper.agentic.unified_context_compiler import (
        build_run_invocation_budget_envelope_v1,
        read_unified_budget_profile,
        read_unified_extra_roles,
    )

    env = {
        "CODE2PAPER_UNIFIED_MAX_TOTAL_INPUT_TOKENS": "2000000",
        "CODE2PAPER_UNIFIED_MAX_PAGE_INPUT_TOKENS": "500",
        "CODE2PAPER_UNIFIED_MAX_OBLIGATIONS_PER_PAGE": "3",
        "CODE2PAPER_UNIFIED_MAX_FORMULA_REPAIR_CALLS": "0",
        "CODE2PAPER_UNIFIED_MODEL_CONTEXT_TOKENS": "4096",
        "CODE2PAPER_UNIFIED_SAFETY_MARGIN_TOKENS": "10",
        "CODE2PAPER_UNIFIED_PROMPT_TOKEN_RESERVE": "20",
        "CODE2PAPER_UNIFIED_THINKING_TOKEN_RESERVE": "0",
        "CODE2PAPER_UNIFIED_MAX_FORMALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_WRITER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_REALIZER_CALLS": "5",
        "CODE2PAPER_UNIFIED_MAX_BINDER_CALLS": "0",
        "CODE2PAPER_UNIFIED_EXTRA_ROLES": "method_proposition_architect",
        "CODE2PAPER_UNIFIED_MAX_METHOD_PROPOSITION_ARCHITECT_CALLS": "6",
        "CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "64",
        "CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_METHOD_PROPOSITION_ARCHITECT": "1024",
        "CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_METHOD_PROPOSITION_ARCHITECT": "0",
    }
    for role in ("formalizer", "writer", "realizer", "binder"):
        env[f"CODE2PAPER_UNIFIED_OUTPUT_TOKEN_RESERVE_{role.upper()}"] = "100"
        env[f"CODE2PAPER_UNIFIED_MAX_REQUEST_INPUT_TOKENS_{role.upper()}"] = "400"
        env[f"CODE2PAPER_UNIFIED_SCAFFOLDING_TOKEN_RESERVE_{role.upper()}"] = "0"
    profile = read_unified_budget_profile(env)
    profile.update(read_unified_extra_roles(env))
    envelope = build_run_invocation_budget_envelope_v1(
        profile_budget=profile,
        model_capabilities={"context_tokens": 4096},
        run_digest="sha256:run",
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
    )

    meter = proposal_call_meter_from_envelope(
        envelope,
        consumer_role="method_proposition_architect",
        accounting_root=tmp_path,
    )
    assert meter is not None
    assert meter.max_input_tokens == 1024
    assert meter.planned_input_tokens == 1024
    # Without a root there is no durable path; with one it is the registered
    # authoring artifact.
    assert durable_accounting_path(meter) == (
        tmp_path / "artifacts" / "06_authoring" / "proposal_call_accounting_v1.json"
    )
    assert durable_accounting_path(_meter()) is None


def test_supplied_tokenizer_meters_a_model_tokenizer_envelope(
    tmp_path: Path,
) -> None:
    """The calibration path: the run's own tokenizer, or no measurement."""

    from code2paper.agentic.unified_context_models import model_tokenizer_meter

    envelope = SimpleNamespace(
        token_meter=model_tokenizer_meter("qwen36-27b-nvfp4"),
        max_request_input_tokens_by_role={"method_proposition_architect": 4096},
        model_identity_digest="sha256:model",
    )
    tokenizer = _Tokenizer()
    # Without the tokenizer the meter refuses to invent a measurement.
    assert (
        proposal_call_meter_from_envelope(
            envelope, consumer_role="method_proposition_architect"
        )
        is None
    )

    meter = proposal_call_meter_from_envelope(
        envelope,
        consumer_role="method_proposition_architect",
        tokenizer=tokenizer,
        accounting_root=tmp_path,
    )
    assert meter is not None
    traced: list[Any] = []

    def _caller(cfg, request):
        traced.append(request)
        return SimpleNamespace(text='{"mechanism_id": "mech-1"}')

    caller = build_narrative_organization_proposal_caller(
        _config(), llm_caller=_caller, call_meter=meter
    )
    assert caller is not None
    caller("mech-1", ["detail-1"], ["sec-1"], ["writer"])
    row = caller.accounting.rows[0]
    assert row.status == "completed"
    assert row.meter is not None and row.meter.method == "model_tokenizer"
    # The measurement is the tokenizer's own count over the same three parts
    # the unified pipeline measures, not a byte proxy.
    assert row.measured_input_tokens == stated_tokens(tokenizer, traced[0])


# ---------------------------------------------------------------------------
# S2 strict run-budget and recovery boundaries
# ---------------------------------------------------------------------------


def _auxiliary_request(*, prompt: str = "x", identity: str = "request-1"):
    return SimpleNamespace(
        prompt_template_id="auxiliary_test_v1",
        input_hash=identity,
        prompt=prompt,
        input_payload={"mechanism_id": "mech-1"},
        response_json_schema={"type": "object", "additionalProperties": False},
    )


def test_strict_auxiliary_caller_enforces_cumulative_call_count_and_spend(
    tmp_path: Path,
) -> None:
    calls: list[Any] = []
    envelope = _strict_envelope(max_calls=1, max_total=2000)
    config = LLMConfig(
        provider=LLMProvider.NONE,
        model="none",
        role="method_proposition_architect",
    )
    caller = build_budgeted_auxiliary_llm_caller(
        config,
        envelope,
        accounting_root=tmp_path,
        base_caller=lambda cfg, request: calls.append(request) or SimpleNamespace(text="{}"),
    )
    request = _auxiliary_request()

    first = caller(config, request)
    second = caller(config, _auxiliary_request(identity="request-2"))

    assert getattr(first, "text", "") == "{}"
    assert getattr(second, "blocked_reason", "").startswith(
        "unified_invocation_budget_exceeded:calls:"
    )
    assert len(calls) == 1
    accounting_path = tmp_path / "artifacts" / "06_authoring" / (
        "proposal_call_accounting_method_proposition_architect.json"
    )
    restored = load_proposal_call_accounting(accounting_path)
    assert len(restored.rows) == 2
    assert restored.rows[1].sent_to_caller is False
    assert restored.rows[1].spent_input_tokens == 0


def test_strict_auxiliary_caller_enforces_cumulative_run_input_budget(
    tmp_path: Path,
) -> None:
    calls: list[Any] = []
    envelope = _strict_envelope(max_calls=4, max_total=500)
    config = LLMConfig(
        provider=LLMProvider.NONE,
        model="none",
        role="method_proposition_architect",
    )
    caller = build_budgeted_auxiliary_llm_caller(
        config,
        envelope,
        accounting_root=tmp_path,
        base_caller=lambda cfg, request: calls.append(request) or SimpleNamespace(text="{}"),
    )
    # Each request is below the 400-token request cap, while two requests
    # exceed the 500-token run reservation.
    request = _auxiliary_request(prompt="x" * 1400)
    first = caller(config, request)
    second = caller(config, _auxiliary_request(prompt="x" * 1400, identity="request-2"))

    assert getattr(first, "text", "") == "{}"
    assert getattr(second, "blocked_reason", "").startswith(
        "unified_invocation_budget_exceeded:total_input_tokens:"
    )
    assert len(calls) == 1


def test_strict_auxiliary_caller_blocks_missing_role_and_missing_tokenizer(
    tmp_path: Path,
) -> None:
    calls: list[Any] = []
    envelope = _strict_envelope()
    request = _auxiliary_request()
    missing_role = build_budgeted_auxiliary_llm_caller(
        LLMConfig(provider=LLMProvider.NONE, model="none", role="semantic_verifier"),
        envelope,
        accounting_root=tmp_path / "missing-role",
        base_caller=lambda cfg, req: calls.append(req) or SimpleNamespace(text="{}"),
    )
    response = missing_role(
        LLMConfig(provider=LLMProvider.NONE, model="none", role="semantic_verifier"),
        request,
    )
    assert getattr(response, "blocked_reason", "") == (
        "unified_auxiliary_budget_missing:semantic_verifier"
    )
    assert calls == []

    tokenizer_envelope = _strict_envelope(
        token_meter=UnifiedTokenMeterV1(
            method="model_tokenizer", tokenizer_identity="strict-tokenizer"
        )
    )
    missing_tokenizer = build_budgeted_auxiliary_llm_caller(
        LLMConfig(
            provider=LLMProvider.NONE,
            model="none",
            role="method_proposition_architect",
        ),
        tokenizer_envelope,
        accounting_root=tmp_path / "missing-tokenizer",
        base_caller=lambda cfg, req: calls.append(req) or SimpleNamespace(text="{}"),
    )
    response = missing_tokenizer(
        LLMConfig(
            provider=LLMProvider.NONE,
            model="none",
            role="method_proposition_architect",
        ),
        request,
    )
    assert getattr(response, "blocked_reason", "") == (
        "unified_auxiliary_budget_missing:method_proposition_architect"
    )
    assert calls == []


def test_strict_auxiliary_caller_refuses_corrupt_or_foreign_tally(
    tmp_path: Path,
) -> None:
    config = LLMConfig(
        provider=LLMProvider.NONE,
        model="none",
        role="method_proposition_architect",
    )
    envelope = _strict_envelope()
    meter = proposal_call_meter_from_envelope(
        envelope,
        consumer_role=config.role,
        accounting_root=tmp_path,
        accounting_filename=(
            "proposal_call_accounting_method_proposition_architect.json"
        ),
    )
    assert meter is not None
    path = durable_accounting_path(meter)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    loaded, failure = load_durable_accounting_status(meter)
    assert loaded is None
    assert failure.startswith("proposal_accounting_corrupt:")

    calls: list[Any] = []
    caller = build_budgeted_auxiliary_llm_caller(
        config,
        envelope,
        accounting_root=tmp_path,
        base_caller=lambda cfg, req: calls.append(req) or SimpleNamespace(text="{}"),
    )
    response = caller(config, _auxiliary_request())
    assert getattr(response, "blocked_reason", "").startswith(
        "proposal_accounting_corrupt:"
    )
    assert calls == []

    # A different run/revision must not adopt a previous tally as current
    # spend, even when the file is syntactically valid.
    path.unlink()
    foreign = ProposalCallAccountingV1(
        consumer_role=config.role,
        invocation_plan_membership=PROPOSAL_ACCOUNTING_IN_PLAN,
        run_digest="sha256:foreign-run",
        revision_id="foreign-revision",
        envelope_digest="sha256:foreign-envelope",
        profile_digest="sha256:foreign-profile",
        model_identity_digest="sha256:foreign-model",
    )
    write_proposal_call_accounting(
        tmp_path,
        foreign,
        filename="proposal_call_accounting_method_proposition_architect.json",
    )
    loaded, failure = load_durable_accounting_status(meter)
    assert loaded is None
    assert failure.startswith("proposal_accounting_identity_mismatch:")


def test_strict_narrative_start_write_failure_blocks_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []
    meter = _meter(accounting_root=tmp_path)

    def _fail_start(*args: Any, **kwargs: Any) -> None:
        raise OSError("read-only")

    monkeypatch.setattr(
        "code2paper.agentic.narrative_organization_proposal.persist_proposal_call_state",
        _fail_start,
    )
    caller = build_narrative_organization_proposal_caller(
        _config(),
        llm_caller=lambda cfg, request: calls.append(request),
        call_meter=meter,
    )
    assert caller is not None
    assert caller("mech-1", ["detail-1"], ["sec-1"], ["writer"]) == {}
    assert calls == []
    assert caller.accounting is not None
    assert caller.accounting.rows[-1].sent_to_caller is False
    assert caller.accounting.rows[-1].spent_input_tokens == 0
