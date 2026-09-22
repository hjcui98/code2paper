"""PR B / F04：崩溃与恢复矩阵——每个场景只能有一个结论（审计 §B.3、§B.6）。

审计要求 CLI、doctor、resume、发送包装器消费**同一个**归约结果，因此这里的断言全部
打在 `reduce_invocation_recovery` 的状态上，并额外验证其它 reader 与它一致。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.writer_attempt_ledger import (
    RECOVERY_ACTIONS,
    build_resume_preflight,
    content_budget_exhausted,
    read_attempt_outcomes,
    read_invocation_ledger_state,
    reduce_invocation_recovery,
    unsettled_reservations,
)

INVOCATION = "inv:writer:MA-S1:page:deadbeef"
DIR_NAME = "inv-writer-MA-S1-page-deadbeef-abc123"


def _ledger(tmp_path: Path) -> Path:
    directory = tmp_path / "artifacts" / "06_authoring" / "invocations" / DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write(directory: Path, attempt: int, kind: str, payload: dict | None = None) -> Path:
    suffix = {
        "started": "started",
        "request": "provider-request",
        "response": "provider-response",
        "completed": "completed",
        "acceptance": "content-acceptance",
    }[kind]
    path = directory / f"attempt-{attempt:04d}.{suffix}.json"
    body = {"attempt": attempt, "invocation_id": INVOCATION, **(payload or {})}
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return path


def _completed_payload(*, sent: bool = True, repair: bool = False, code: str = "") -> dict:
    return {
        "sent_to_caller": sent,
        "delivery_status": "rejected" if code else "accepted",
        "delivery_rejection_code": code,
        "content_repair_attempt": repair,
        "provider_usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}
        if sent
        else None,
    }


def _reduce(tmp_path: Path, **kwargs):
    return reduce_invocation_recovery(tmp_path, INVOCATION, **kwargs)


# --------------------------------------------------------------------------- #
# §B.3 的八行状态表
# --------------------------------------------------------------------------- #


def test_only_started_is_reserved_not_sent(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    recovery = _reduce(tmp_path)

    assert recovery.state == "reserved_not_sent"
    assert recovery.counters.provider_send_count == 0
    assert recovery.counters.content_attempt_count == 0
    assert recovery.unknown_reservation_attempts == ()
    assert "count_it_as_a_content_failure" in recovery.forbidden_actions


def test_request_without_completed_is_send_outcome_unknown(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"request_digest": "sha256:req"})
    recovery = _reduce(tmp_path)

    assert recovery.state == "send_outcome_unknown"
    assert recovery.unknown_reservation_attempts == (1,)
    assert "assume_not_sent" in recovery.forbidden_actions
    assert "silently_retry" in recovery.forbidden_actions


def test_response_without_completed_is_response_received_unsettled(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {"response_digest": "sha256:resp"})
    recovery = _reduce(tmp_path)

    assert recovery.state == "response_received_unsettled"
    assert "request_the_same_content_again" in recovery.forbidden_actions


def test_completed_without_response_is_ledger_inconsistent(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "completed", _completed_payload())
    recovery = _reduce(tmp_path)

    assert recovery.state == "response_missing_or_ledger_inconsistent"
    assert "claim_offline_replay" in recovery.forbidden_actions


def test_response_without_acceptance_is_validation_pending(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {})
    _write(directory, 1, "completed", _completed_payload())
    recovery = _reduce(tmp_path)

    assert recovery.state == "validation_pending"
    assert recovery.accepted is False
    assert "treat_the_missing_acceptance_as_accepted" in recovery.forbidden_actions


def test_corrupt_acceptance_is_ledger_corrupt(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {})
    _write(directory, 1, "completed", _completed_payload())
    (directory / "attempt-0001.content-acceptance.json").write_text("{ not json", encoding="utf-8")

    recovery = _reduce(tmp_path)
    assert recovery.state == "ledger_corrupt"
    assert recovery.blocks and "content-acceptance" in recovery.blocks[0]
    assert "ignore_the_file_and_take_a_fresh_budget" in recovery.forbidden_actions


def test_accepted_matching_contract_is_reusable(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {})
    _write(directory, 1, "completed", _completed_payload())
    _write(directory, 1, "acceptance", {"accepted": True, "plan_digest": "sha256:plan"})

    recovery = _reduce(tmp_path, contract_digests={"plan_digest": "sha256:plan"})
    assert recovery.state == "accepted_reusable"
    assert recovery.accepted is True and recovery.primary_accepted is True
    assert recovery.contract_mismatch == ()

    mismatched = _reduce(tmp_path, contract_digests={"plan_digest": "sha256:other"})
    assert mismatched.contract_mismatch == ("1:plan_digest",)


def test_exhausted_content_budget_is_terminal(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    for attempt in (1, 2):
        _write(directory, attempt, "started")
        _write(directory, attempt, "request", {})
        _write(directory, attempt, "response", {})
        _write(
            directory,
            attempt,
            "completed",
            _completed_payload(repair=attempt == 2),
        )
        _write(
            directory,
            attempt,
            "acceptance",
            {"accepted": False, "failures": ["missing_paragraph:P2", "required_target_contract:x"]},
        )
    recovery = _reduce(tmp_path)

    assert recovery.state == "content_budget_exhausted"
    assert recovery.content_attempts_remaining == 0
    assert recovery.last_content_failure_codes == ("paragraph_missing", "detail_witness_missing")
    assert "continue_with_a_higher_attempt_number_on_the_same_root" in recovery.forbidden_actions


# --------------------------------------------------------------------------- #
# §B.6 的补充反例
# --------------------------------------------------------------------------- #


def test_two_real_failures_without_a_rejection_record_still_exhaust(tmp_path: Path) -> None:
    """审计点名：没有 attempt-0003 拒发记录时也必须报耗尽。"""

    directory = _ledger(tmp_path)
    for attempt in (1, 2):
        _write(directory, attempt, "started")
        _write(directory, attempt, "request", {})
        _write(directory, attempt, "response", {})
        _write(directory, attempt, "completed", _completed_payload())
        _write(directory, attempt, "acceptance", {"accepted": False, "failures": []})

    assert not (directory / "attempt-0003.completed.json").exists()
    recovery = _reduce(tmp_path)
    assert recovery.state == "content_budget_exhausted"
    assert recovery.counters.rejected_before_send_events == ()


def test_two_presend_refusals_without_sends_are_not_exhausted(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    for attempt in (1, 2):
        _write(
            directory,
            attempt,
            "completed",
            _completed_payload(sent=False, code=f"attempt_limit_exhausted:{INVOCATION}:{attempt}>2"),
        )
    recovery = _reduce(tmp_path)

    assert recovery.counters.provider_send_count == 0
    assert recovery.counters.content_attempt_count == 0
    assert recovery.state == "reserved_not_sent"
    assert recovery.counters.rejected_before_send_events == (1, 2)


def test_acceptance_survives_residual_rejection_records(tmp_path: Path) -> None:
    """历史拒发记录不得永久覆盖之后的合法接受。"""

    directory = _ledger(tmp_path)
    _write(
        directory,
        1,
        "completed",
        _completed_payload(sent=False, code=f"attempt_limit_exhausted:{INVOCATION}:1>2"),
    )
    _write(directory, 2, "started")
    _write(directory, 2, "request", {})
    _write(directory, 2, "response", {})
    _write(directory, 2, "completed", _completed_payload())
    _write(directory, 2, "acceptance", {"accepted": True})

    recovery = _reduce(tmp_path)
    assert recovery.state == "accepted_reusable"
    assert recovery.accepted is True
    assert recovery.exhausted is False


def test_same_page_with_a_different_validator_is_not_reusable(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {})
    _write(directory, 1, "completed", _completed_payload())
    _write(
        directory,
        1,
        "acceptance",
        {"accepted": True, "validator_bundle_digest": "sha256:old-validator"},
    )

    recovery = _reduce(
        tmp_path, contract_digests={"validator_bundle_digest": "sha256:new-validator"}
    )
    assert recovery.accepted is True
    assert recovery.contract_mismatch == ("1:validator_bundle_digest",)
    assert recovery.primary_cause == "accepted_but_contract_mismatch"


def test_every_state_declares_allowed_and_forbidden_actions() -> None:
    """状态表必须自带动作约束，避免每个 reader 各自解释。"""

    for state, (allowed, forbidden) in RECOVERY_ACTIONS.items():
        assert allowed, state
        assert forbidden, state


# --------------------------------------------------------------------------- #
# 一致性：所有 reader 消费同一个结论
# --------------------------------------------------------------------------- #


def test_all_readers_agree_on_the_same_conclusion(tmp_path: Path) -> None:
    directory = _ledger(tmp_path)
    for attempt in (1, 2):
        _write(directory, attempt, "started")
        _write(directory, attempt, "request", {})
        _write(directory, attempt, "response", {})
        _write(directory, attempt, "completed", _completed_payload())
        _write(directory, attempt, "acceptance", {"accepted": False, "failures": []})

    recovery = _reduce(tmp_path)
    state = read_invocation_ledger_state(tmp_path, INVOCATION)
    preflight = build_resume_preflight(tmp_path, [INVOCATION], execution_id="exec-x")
    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    unsettled = unsettled_reservations(tmp_path, INVOCATION)

    assert recovery.state == "content_budget_exhausted"
    assert content_budget_exhausted(state, 2) is True
    assert state.counters == recovery.counters
    assert preflight.allowed is False
    assert preflight.content_attempts_used == recovery.counters.content_attempt_count
    assert preflight.last_content_failure_codes == recovery.last_content_failure_codes
    # 已结算的两次真实尝试不再保留预留（结果已知）。
    assert unsettled == ()
    assert outcomes, "attempt 集合必须来自全部事件文件"
    assert {item.attempt for item in outcomes} == {1, 2}


# --------------------------------------------------------------------------- #
# §B.5：本地验证重放结算（只新增，不改写历史）
# --------------------------------------------------------------------------- #


def _pending_validation_ledger(tmp_path: Path) -> Path:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {})
    _write(directory, 1, "response", {"response_digest": "sha256:resp"})
    _write(directory, 1, "completed", _completed_payload())
    return directory


def test_local_replay_settles_a_pending_validation(tmp_path: Path) -> None:
    from code2paper.agentic.writer_attempt_ledger import (
        publish_validation_replay,
        read_validation_replays,
    )

    directory = _pending_validation_ledger(tmp_path)
    assert _reduce(tmp_path).state == "validation_pending"

    path = publish_validation_replay(
        tmp_path,
        INVOCATION,
        attempt=1,
        accepted=True,
        validator_bundle_digest="sha256:validator-current",
        source_response_digest="sha256:resp",
        contract_digest="sha256:plan",
    )
    assert path.is_file()
    assert not (directory / "attempt-0001.content-acceptance.json").exists(), (
        "本地重放不得改写/伪造历史 acceptance"
    )

    recovery = _reduce(
        tmp_path, contract_digests={"validator_bundle_digest": "sha256:validator-current"}
    )
    assert recovery.state == "accepted_reusable"
    assert recovery.accepted is True
    assert len(read_validation_replays(directory)) == 1


def test_replay_from_an_old_validator_is_not_reused(tmp_path: Path) -> None:
    """validator 身份变了 → 旧重放不得冒充当前契约的接受（§B.5）。"""

    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    _pending_validation_ledger(tmp_path)
    publish_validation_replay(
        tmp_path,
        INVOCATION,
        attempt=1,
        accepted=True,
        validator_bundle_digest="sha256:validator-old",
        source_response_digest="sha256:resp",
    )

    recovery = _reduce(
        tmp_path, contract_digests={"validator_bundle_digest": "sha256:validator-new"}
    )
    assert recovery.accepted is False
    assert recovery.state == "validation_pending"
    assert recovery.contract_mismatch == (
        "stale_validation_replay:1:sha256:validator-old",
    )


def test_rejected_replay_consumes_budget_like_a_real_rejection(tmp_path: Path) -> None:
    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    directory = _ledger(tmp_path)
    for attempt in (1, 2):
        _write(directory, attempt, "started")
        _write(directory, attempt, "request", {})
        _write(directory, attempt, "response", {})
        _write(directory, attempt, "completed", _completed_payload(repair=attempt == 2))
        publish_validation_replay(
            tmp_path,
            INVOCATION,
            attempt=attempt,
            accepted=False,
            validator_bundle_digest="sha256:validator-current",
            failure_codes=("detail_witness_missing",),
        )

    recovery = _reduce(
        tmp_path, contract_digests={"validator_bundle_digest": "sha256:validator-current"}
    )
    assert recovery.state == "content_budget_exhausted"
    assert recovery.last_content_failure_codes == ("detail_witness_missing",)


def test_replay_publication_is_idempotent_and_history_protected(tmp_path: Path) -> None:
    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    directory = _pending_validation_ledger(tmp_path)
    publish_validation_replay(
        tmp_path,
        INVOCATION,
        attempt=1,
        accepted=True,
        validator_bundle_digest="sha256:validator-current",
    )
    with pytest.raises(ValueError, match="already_published"):
        publish_validation_replay(
            tmp_path,
            INVOCATION,
            attempt=1,
            accepted=False,
            validator_bundle_digest="sha256:validator-current",
        )

    # 有历史 acceptance 的 attempt：本地重放必须拒绝，不能覆盖历史结论。
    _write(directory, 2, "started")
    _write(directory, 2, "completed", _completed_payload())
    _write(directory, 2, "acceptance", {"accepted": False, "failures": []})
    with pytest.raises(ValueError, match="shadow_historical_acceptance"):
        publish_validation_replay(
            tmp_path,
            INVOCATION,
            attempt=2,
            accepted=True,
            validator_bundle_digest="sha256:validator-current",
        )


# --------------------------------------------------------------------------- #
# §B.2：未知发送结果必须保留预留，且不得记成"真实 0 tokens"
# --------------------------------------------------------------------------- #


def test_unknown_send_outcome_keeps_its_reservation(tmp_path: Path) -> None:
    from code2paper.agentic.writer_attempt_ledger import (
        SEND_OUTCOME_UNKNOWN,
        read_attempt_outcomes,
        unsettled_reservations,
    )

    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"reserved_input_tokens": 7258})

    recovery = _reduce(tmp_path)
    assert recovery.state == "send_outcome_unknown"
    assert recovery.unknown_reservation_attempts == (1,)

    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    assert [item.state for item in outcomes] == [SEND_OUTCOME_UNKNOWN]
    assert outcomes[0].reservation_retained is True
    assert outcomes[0].acceptance_replayable is False
    assert unsettled_reservations(tmp_path, INVOCATION) == outcomes

    # 未知结果不得被当成"已结算的 0 调用"：预算视角仍需保留它。
    from code2paper.agentic.unified_invocation_ledger import (
        unsettled_started_attempt_records,
    )

    class _Plan:
        invocations = ()

    records = unsettled_started_attempt_records(directory.parent, _Plan())
    assert records, "started 但无 completed 的 attempt 必须保留在预算视角里"
    assert any(getattr(item, "attempt", 0) == 1 for item in records)
