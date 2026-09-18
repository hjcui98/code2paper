"""WP5：传输层重试策略（方案 §9.2）。

方案明确：限流/网络重试**不是免费无限重试**——它必须受单独的策略与 run 费用/调用上限
约束；而"已发送但超时且无确认"属于 ``send_outcome_unknown``：保留 reservation，
**不得**当成未发送去自动退款或重发。

本模块是纯决策函数：给定失败类别、已用调用数与策略，输出下一步动作。它不做 I/O、
不发请求、不改账本，便于离线枚举所有分支。
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

#: 失败类别
TransportFailureKindV1 = Literal[
    "retryable_status",       # 429/5xx：服务端明确未接受或明确拒绝，可安全重试
    "terminal_status",        # 4xx（非 429）：请求本身有问题，重试无意义
    "transport_timeout",      # 已发送、超时、无确认 → 结果未知
    "connection_error",       # 连接未建立 → 确定未发送
    "unknown",                # 无法判定 → 按结果未知处理（fail-closed）
]

TransportActionV1 = Literal["retry", "fail", "preserve_reservation"]

DEFAULT_MAX_TRANSPORT_RETRIES = 2
DEFAULT_BASE_DELAY_SECONDS = 1.0
DEFAULT_MAX_DELAY_SECONDS = 30.0
DEFAULT_RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)

#: 结果未知的失败绝不自动重试（不得把未知当作未发送）。
UNKNOWN_OUTCOME_RETRIES = 0


class TransportRetryPolicyV1(BaseModel):
    """一次运行使用的传输策略（可经环境变量覆盖）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    max_transport_retries: int = DEFAULT_MAX_TRANSPORT_RETRIES
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS
    retryable_status_codes: tuple[int, ...] = DEFAULT_RETRYABLE_STATUS_CODES
    #: 限流/网络重试同样消耗 run 的调用与费用预算（§9.2）。
    counts_against_call_budget: bool = True
    unknown_outcome_retries: int = UNKNOWN_OUTCOME_RETRIES

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class TransportActionDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: TransportActionV1
    reason: str
    failure_kind: str
    retry_index: int = 0
    delay_seconds: float = 0.0
    counts_against_call_budget: bool = True
    #: True = 该次失败必须保留 reservation（结果未知）。
    reservation_retained: bool = False

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def load_transport_retry_policy(
    environment: dict[str, str] | None = None,
) -> TransportRetryPolicyV1:
    """从环境读取策略；非法值回落默认（不因坏配置变成无限重试）。"""

    env = environment if environment is not None else dict(os.environ)

    def _int(name: str, default: int) -> int:
        try:
            value = int(str(env.get(name, "") or "").strip())
        except (TypeError, ValueError):
            return default
        return max(0, value)

    def _float(name: str, default: float) -> float:
        try:
            value = float(str(env.get(name, "") or "").strip())
        except (TypeError, ValueError):
            return default
        return max(0.0, value)

    return TransportRetryPolicyV1(
        max_transport_retries=_int(
            "CODE2PAPER_TRANSPORT_MAX_RETRIES", DEFAULT_MAX_TRANSPORT_RETRIES
        ),
        base_delay_seconds=_float(
            "CODE2PAPER_TRANSPORT_BASE_DELAY_SECONDS", DEFAULT_BASE_DELAY_SECONDS
        ),
        max_delay_seconds=_float(
            "CODE2PAPER_TRANSPORT_MAX_DELAY_SECONDS", DEFAULT_MAX_DELAY_SECONDS
        ),
        retryable_status_codes=DEFAULT_RETRYABLE_STATUS_CODES,
        counts_against_call_budget=True,
        unknown_outcome_retries=UNKNOWN_OUTCOME_RETRIES,
    )


def classify_transport_failure(
    *,
    status_code: int | None = None,
    exception: BaseException | None = None,
    sent: bool = True,
    policy: TransportRetryPolicyV1 | None = None,
) -> TransportFailureKindV1:
    """把一次失败归类；无法判定时按"结果未知"处理（fail-closed）。"""

    active = policy or TransportRetryPolicyV1()
    if status_code is not None:
        if int(status_code) in active.retryable_status_codes:
            return "retryable_status"
        if 400 <= int(status_code) < 500:
            return "terminal_status"
        return "retryable_status" if int(status_code) >= 500 else "unknown"
    if exception is not None:
        name = type(exception).__name__.casefold()
        if isinstance(exception, TimeoutError) or "timeout" in name:
            # 已发送却无确认：结果未知，不是"未发送"。
            return "transport_timeout" if sent else "connection_error"
        if "connection" in name or "connect" in name:
            return "connection_error"
    return "unknown"


def next_transport_action(
    *,
    failure_kind: TransportFailureKindV1,
    retry_index: int = 0,
    calls_used: int = 0,
    call_limit: int | None = None,
    policy: TransportRetryPolicyV1 | None = None,
) -> TransportActionDecisionV1:
    """决定下一步：retry / fail / preserve_reservation。

    * 结果未知（timeout / unknown）→ ``preserve_reservation``，**不重试、不退款**。
    * 可重试失败 → 受 ``max_transport_retries`` 与 run 调用上限双重约束。
    * 终态失败 → ``fail``。
    """

    active = policy or TransportRetryPolicyV1()
    kind = str(failure_kind)

    if kind in {"transport_timeout", "unknown"}:
        return TransportActionDecisionV1(
            action="preserve_reservation",
            reason="send_outcome_unknown:保留 reservation，不自动重发/退款",
            failure_kind=kind,
            retry_index=int(retry_index),
            counts_against_call_budget=active.counts_against_call_budget,
            reservation_retained=True,
        )

    if kind == "terminal_status":
        return TransportActionDecisionV1(
            action="fail",
            reason="terminal_status:重试无意义",
            failure_kind=kind,
            retry_index=int(retry_index),
        )

    if kind == "connection_error":
        # 确定未发送：可以安全重试（仍受策略与预算约束）。
        pass

    if int(retry_index) >= int(active.max_transport_retries):
        return TransportActionDecisionV1(
            action="fail",
            reason=(
                f"transport_retries_exhausted:{retry_index}>="
                f"{active.max_transport_retries}"
            ),
            failure_kind=kind,
            retry_index=int(retry_index),
        )

    if call_limit is not None and int(call_limit) >= 0:
        if int(calls_used) >= int(call_limit):
            return TransportActionDecisionV1(
                action="fail",
                reason=(
                    "transport_retry_exceeds_call_budget:"
                    f"{calls_used}>={call_limit}"
                ),
                failure_kind=kind,
                retry_index=int(retry_index),
            )

    delay = min(
        float(active.max_delay_seconds),
        float(active.base_delay_seconds) * (2 ** int(retry_index)),
    )
    return TransportActionDecisionV1(
        action="retry",
        reason=f"retryable:{kind}",
        failure_kind=kind,
        retry_index=int(retry_index) + 1,
        delay_seconds=delay,
        counts_against_call_budget=active.counts_against_call_budget,
    )


__all__ = [
    "DEFAULT_BASE_DELAY_SECONDS",
    "DEFAULT_MAX_DELAY_SECONDS",
    "DEFAULT_MAX_TRANSPORT_RETRIES",
    "DEFAULT_RETRYABLE_STATUS_CODES",
    "TransportActionDecisionV1",
    "TransportActionV1",
    "TransportFailureKindV1",
    "TransportRetryPolicyV1",
    "UNKNOWN_OUTCOME_RETRIES",
    "classify_transport_failure",
    "load_transport_retry_policy",
    "next_transport_action",
]
