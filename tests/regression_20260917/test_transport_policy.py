"""WP5 传输策略：限流/网络重试不是免费无限重试（方案 §9.2）。"""

from __future__ import annotations

from code2paper.agentic.transport_retry_policy import (
    DEFAULT_MAX_TRANSPORT_RETRIES,
    TransportRetryPolicyV1,
    classify_transport_failure,
    load_transport_retry_policy,
    next_transport_action,
)


def test_rate_limit_is_retryable_but_bounded() -> None:
    policy = TransportRetryPolicyV1(max_transport_retries=2)
    kind = classify_transport_failure(status_code=429, policy=policy)
    assert kind == "retryable_status"

    first = next_transport_action(failure_kind=kind, policy=policy)
    assert first.action == "retry" and first.retry_index == 1
    assert first.counts_against_call_budget is True
    assert first.delay_seconds > 0

    second = next_transport_action(failure_kind=kind, retry_index=1, policy=policy)
    assert second.action == "retry" and second.retry_index == 2

    # 第三次到达上限：必须失败，不能无限重试。
    third = next_transport_action(failure_kind=kind, retry_index=2, policy=policy)
    assert third.action == "fail"
    assert "transport_retries_exhausted" in third.reason


def test_retry_respects_run_call_budget() -> None:
    policy = TransportRetryPolicyV1(max_transport_retries=5)
    blocked = next_transport_action(
        failure_kind="retryable_status",
        calls_used=20,
        call_limit=20,
        policy=policy,
    )
    assert blocked.action == "fail"
    assert "transport_retry_exceeds_call_budget" in blocked.reason

    allowed = next_transport_action(
        failure_kind="retryable_status",
        calls_used=19,
        call_limit=20,
        policy=policy,
    )
    assert allowed.action == "retry"


def test_send_outcome_unknown_preserves_reservation_and_never_retries() -> None:
    """已发送但无确认：不得当成未发送自动退款或重发（§9.2）。"""

    policy = TransportRetryPolicyV1()
    kind = classify_transport_failure(exception=TimeoutError("read timeout"), sent=True)
    assert kind == "transport_timeout"

    decision = next_transport_action(
        failure_kind=kind, calls_used=0, call_limit=10, policy=policy
    )
    assert decision.action == "preserve_reservation"
    assert decision.reservation_retained is True
    assert decision.retry_index == 0
    assert policy.unknown_outcome_retries == 0

    # 无法判定同样按结果未知处理。
    unknown = next_transport_action(failure_kind="unknown", policy=policy)
    assert unknown.action == "preserve_reservation"


def test_connection_error_is_retryable_terminal_status_is_not() -> None:
    policy = TransportRetryPolicyV1()
    assert (
        classify_transport_failure(exception=ConnectionResetError("reset"), sent=False)
        == "connection_error"
    )
    connection = next_transport_action(failure_kind="connection_error", policy=policy)
    assert connection.action == "retry"

    assert classify_transport_failure(status_code=400, policy=policy) == "terminal_status"
    terminal = next_transport_action(failure_kind="terminal_status", policy=policy)
    assert terminal.action == "fail"
    assert "terminal_status" in terminal.reason


def test_policy_loading_falls_back_safely(monkeypatch) -> None:
    monkeypatch.delenv("CODE2PAPER_TRANSPORT_MAX_RETRIES", raising=False)
    assert (
        load_transport_retry_policy().max_transport_retries
        == DEFAULT_MAX_TRANSPORT_RETRIES
    )

    monkeypatch.setenv("CODE2PAPER_TRANSPORT_MAX_RETRIES", "3")
    assert load_transport_retry_policy().max_transport_retries == 3

    # 坏配置回落默认，而不是变成"无限重试"或负数。
    monkeypatch.setenv("CODE2PAPER_TRANSPORT_MAX_RETRIES", "abc")
    assert (
        load_transport_retry_policy().max_transport_retries
        == DEFAULT_MAX_TRANSPORT_RETRIES
    )
    monkeypatch.setenv("CODE2PAPER_TRANSPORT_MAX_RETRIES", "-5")
    assert load_transport_retry_policy().max_transport_retries == 0


def test_backoff_is_deterministic_and_capped() -> None:
    policy = TransportRetryPolicyV1(
        max_transport_retries=5, base_delay_seconds=2.0, max_delay_seconds=5.0
    )
    delays = [
        next_transport_action(
            failure_kind="retryable_status", retry_index=index, policy=policy
        ).delay_seconds
        for index in range(5)
    ]
    assert delays == [2.0, 4.0, 5.0, 5.0, 5.0]


def test_failure_codes_are_recorded_for_durable_receipts() -> None:
    """§9.2：持久记录必须能区分"结果未知 / 终态 / 可重试"。"""

    from code2paper.agentic.transport_retry_policy import (
        transport_failure_failure_code as code_for,
    )

    unknown = code_for(TimeoutError("read timeout"), sent=True)
    assert unknown.startswith("send_outcome_unknown:")
    assert "TimeoutError" in unknown

    assert code_for(status_code=400).startswith("transport_terminal_failure:")
    assert code_for(status_code=429).startswith("transport_retryable_failure:")
    assert code_for(ConnectionResetError("reset"), sent=False).startswith(
        "transport_retryable_failure:"
    )


def test_writer_call_branch_uses_the_transport_classifier() -> None:
    """结构性守卫：provider 调用异常分支必须调用分类器（否则策略层形同虚设）。"""

    import inspect

    from code2paper.agentic import publication_method_writer

    source = inspect.getsource(publication_method_writer)
    assert "transport_failure_failure_code(" in source
    assert "send_outcome_unknown" in source or "transport_failure_code" in source
