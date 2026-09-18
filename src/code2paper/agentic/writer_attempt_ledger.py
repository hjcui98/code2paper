"""WP5：Writer 调用的重试/拒发/恢复账本（方案 §9.2、§9.3）。

事故里 `attempt` 同时充当"事件序号"和"真实内容试验次数"：两次真正的 provider
调用（1 = primary，2 = 一次 content repair）之后，第 3、4 次记录都是**预发送拒绝**，
却仍然推进了 attempt 计数并形成新记录，于是"重启后必死"且失败原因只能靠
`acceptance_count:0` 事后推断。

本模块只做只读派生，不新增写入、不改写历史记录（不变量 I8）：

* ``event_seq``（历史 ``attempt``）：不可变事件序号；
* ``provider_send_count``：真正到达 provider 的次数；
* ``content_attempt_count``：真实内容试验次数；
* ``content_repair_count``：其中的 content repair 次数；
* ``rejected_before_send_events``：拒发事件序号（诊断用，不计入发送/内容次数）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

RESUME_EXHAUSTED_INVOCATION = "resume_exhausted_invocation"
DEFAULT_CONTENT_ATTEMPT_LIMIT = 2

FailureCodeV1 = Literal[
    "paragraph_missing",
    "detail_witness_missing",
    "atom_witness_missing",
    "exact_span_not_in_body",
    "detail_semantic_mismatch",
    "target_out_of_scope",
    "authority_surface_violation",
    "formula_consumer_mismatch",
    "input_material_missing",
]


class WriterAttemptCountersV1(BaseModel):
    """一次 invocation 的只读计数器（§9.2）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_seq: int = 0
    provider_send_count: int = 0
    content_attempt_count: int = 0
    content_repair_count: int = 0
    rejected_before_send_events: tuple[int, ...] = ()

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class WriterInvocationLedgerStateV1(BaseModel):
    """一个 invocation 的恢复状态；``exhausted`` 只描述**当前身份**的剩余预算。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    counters: WriterAttemptCountersV1
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT
    #: 任一（含 repair）内容验收通过 = 该页内容已完成，不再需要发送。
    accepted: bool = False
    #: 仅"非 repair 的首次交付"被接受 = 页交付门语义（与上者不同，不可混用）。
    primary_accepted: bool = False
    last_provider_attempt: int = 0
    last_content_failure_codes: tuple[str, ...] = ()
    last_rejection_code: str = ""

    @property
    def content_attempts_remaining(self) -> int:
        return max(0, int(self.content_attempt_limit) - self.counters.content_attempt_count)

    @property
    def exhausted(self) -> bool:
        return (not self.accepted) and self.content_attempts_remaining == 0

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _attempt_records(invocation_dir: Path) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    for path in sorted(invocation_dir.glob("attempt-*.completed.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        try:
            attempt = int(payload.get("attempt") or 0)
        except (TypeError, ValueError):
            attempt = 0
        records.append((attempt, payload))
    records.sort(key=lambda item: item[0])
    return records


def _acceptance_failure_codes(path: Path) -> tuple[str, ...]:
    """把历史 acceptance 失败项映射为结构化码（§7.5 的只读派生）。"""

    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    codes: list[str] = []
    for failure in payload.get("failures") or ():
        text = str(failure)
        if text.startswith("missing_paragraph:"):
            code = "paragraph_missing"
        elif ":detail:" in text or text.startswith("required_target_contract:"):
            code = "detail_witness_missing"
        elif "invalid_witness" in text:
            code = "detail_semantic_mismatch"
        elif text.startswith("transaction_metadata_missing") or text.startswith(
            "paragraph_metadata_missing"
        ):
            code = "input_material_missing"
        elif "authority_violation" in text:
            code = "authority_surface_violation"
        else:
            continue
        if code not in codes:
            codes.append(code)
    return tuple(codes)


def _invocation_directory(out_root: Path, invocation_id: str) -> Path:
    root = Path(out_root) / "artifacts" / "06_authoring" / "invocations"
    directory = root / invocation_id.replace(":", "-")
    if directory.is_dir():
        return directory
    # 目录命名不总是可逆（含额外后缀摘要）：按转换后的 invocation_id 子串回退查找。
    matches = [
        item
        for item in root.glob("*")
        if item.is_dir() and invocation_id.replace(":", "-") in item.name
    ]
    return matches[0] if matches else directory


def read_invocation_ledger_state(
    out_root: str | Path,
    invocation_id: str,
    *,
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT,
) -> WriterInvocationLedgerStateV1:
    """从持久回执派生一个 invocation 的计数器与恢复状态（只读）。"""

    directory = _invocation_directory(Path(out_root), str(invocation_id))

    sends = 0
    content_attempts = 0
    repairs = 0
    rejected: list[int] = []
    event_seq = 0
    accepted = False
    primary_accepted = False
    last_provider_attempt = 0
    last_rejection = ""
    failure_codes: tuple[str, ...] = ()
    limit = int(content_attempt_limit)

    for attempt, payload in _attempt_records(directory):
        event_seq = max(event_seq, attempt)
        code = str(payload.get("delivery_rejection_code") or "")
        if code.startswith("attempt_limit_exhausted:"):
            rejected.append(attempt)
            last_rejection = code
            if ">" in code.rsplit(":", 1)[-1]:
                try:
                    limit = int(code.rsplit(">", 1)[1])
                except ValueError:
                    pass
            continue
        if bool(payload.get("sent_to_caller", True)):
            sends += 1
            content_attempts += 1
            last_provider_attempt = attempt
            if bool(payload.get("content_repair_attempt")):
                repairs += 1
        # 传输层的 delivery_status=accepted 不等于内容 accepted（事故里两次
        # provider 调用的 delivery_status 都是 accepted，而内容验收都是 rejected），
        # 因此 accepted 只取内容验收记录。
        acceptance = directory / f"attempt-{attempt:04d}.content-acceptance.json"
        if acceptance.is_file():
            try:
                acceptance_payload = json.loads(acceptance.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                acceptance_payload = {}
            if bool(acceptance_payload.get("accepted")):
                # 页内容已完成（repair 后接受也算完成）。
                accepted = True
                if not bool(payload.get("content_repair_attempt")):
                    primary_accepted = True
        codes = _acceptance_failure_codes(acceptance)
        if codes:
            failure_codes = codes

    return WriterInvocationLedgerStateV1(
        invocation_id=str(invocation_id),
        counters=WriterAttemptCountersV1(
            event_seq=event_seq,
            provider_send_count=sends,
            content_attempt_count=content_attempts,
            content_repair_count=repairs,
            rejected_before_send_events=tuple(rejected),
        ),
        content_attempt_limit=limit,
        accepted=accepted,
        primary_accepted=primary_accepted,
        last_provider_attempt=last_provider_attempt,
        last_content_failure_codes=failure_codes,
        last_rejection_code=last_rejection,
    )


class ResumePreflightV1(BaseModel):
    """恢复前置检查结果（§9.3）：进入 Writer 主循环之前给出根因链。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool = True
    code: str = ""
    execution_id: str = ""
    invocation_id: str = ""
    content_attempts_used: int = 0
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT
    last_provider_attempt: int = 0
    last_content_failure_codes: tuple[str, ...] = ()
    rejected_before_send_events: tuple[int, ...] = ()
    allowed_next_action: str = ""
    detail: str = ""

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


SEND_OUTCOME_UNKNOWN = "send_outcome_unknown"

AttemptOutcomeStateV1 = Literal[
    "not_started",
    "reservation_without_send",
    "rejected_before_send",
    "send_outcome_unknown",
    "response_without_completion",
    "completed_without_acceptance",
    "settled",
]


class AttemptOutcomeV1(BaseModel):
    """一次 attempt 的崩溃点分类（方案 §9.5）。

    恢复时不得重复计费、不得静默丢弃 reservation，也不得把"发送结果未知"当成
    "未发送"自动退款或重发。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt: int
    state: AttemptOutcomeStateV1
    #: True = 该 attempt 的预留必须保留（可能已经产生真实开销或结果未知）。
    reservation_retained: bool = False
    #: True = 可以由确定性 validator 重放重建验收，无需再次调用模型。
    acceptance_replayable: bool = False
    detail: str = ""

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def read_attempt_outcomes(
    out_root: str | Path, invocation_id: str
) -> tuple[AttemptOutcomeV1, ...]:
    """按 attempt 汇总崩溃点状态；缺文件即事实，不按空集合处理。"""

    directory = _invocation_directory(Path(out_root), str(invocation_id))
    numbers: set[int] = set()
    for pattern in ("attempt-*.started.json", "attempt-*.completed.json"):
        for path in directory.glob(pattern):
            try:
                numbers.add(int(path.name.split("-")[1].split(".")[0]))
            except (IndexError, ValueError):
                continue

    outcomes: list[AttemptOutcomeV1] = []
    for attempt in sorted(numbers):
        started = directory / f"attempt-{attempt:04d}.started.json"
        request = directory / f"attempt-{attempt:04d}.provider-request.json"
        response = directory / f"attempt-{attempt:04d}.provider-response.json"
        completed = directory / f"attempt-{attempt:04d}.completed.json"
        acceptance = directory / f"attempt-{attempt:04d}.content-acceptance.json"

        payload: dict[str, Any] = {}
        if completed.is_file():
            try:
                payload = json.loads(completed.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = {}
        rejected_before_send = (
            bool(payload)
            and payload.get("sent_to_caller") is False
            and str(payload.get("delivery_rejection_code") or "").startswith(
                "attempt_limit_exhausted:"
            )
        )

        if rejected_before_send:
            state: AttemptOutcomeStateV1 = "rejected_before_send"
            retained, replayable = False, False
            detail = "预算/合同拒绝，未发送；不消耗内容预算"
        elif request.is_file() and not response.is_file():
            state = "send_outcome_unknown"
            retained, replayable = True, False
            detail = "已发出请求但无响应记录：结果未知，保留 reservation，不自动重发"
        elif response.is_file() and not completed.is_file():
            state = "response_without_completion"
            retained, replayable = True, True
            detail = "有响应但缺 completed 收据：保留 reservation，可由 validator 重建"
        elif completed.is_file() and not acceptance.is_file():
            state = "completed_without_acceptance"
            retained, replayable = False, True
            detail = "已完成但缺内容验收：可由确定性 validator 重放，无需再次调用模型"
        elif completed.is_file():
            state = "settled"
            retained, replayable = False, False
            detail = ""
        elif started.is_file() and not request.is_file():
            state = "reservation_without_send"
            retained, replayable = False, False
            detail = "已预留但未发送：可释放预留，不得计费"
        else:
            state = "not_started"
            retained, replayable = False, False
            detail = ""

        outcomes.append(
            AttemptOutcomeV1(
                attempt=attempt,
                state=state,
                reservation_retained=retained,
                acceptance_replayable=replayable,
                detail=detail,
            )
        )
    return tuple(outcomes)


def unsettled_reservations(
    out_root: str | Path, invocation_id: str
) -> tuple[AttemptOutcomeV1, ...]:
    """需要保留预留的 attempt（结果未知 / 有响应未完成）。

    视角说明（防止与账本预算视角重复扣费）：
    * 本函数是**崩溃点视角**：只保留"可能已产生真实开销且结果未知"的 attempt，
      "已预留未发送"可安全释放。
    * `unified_invocation_ledger.unsettled_started_attempt_records` 是**预算视角**：
      保守地把"started 且无 completed"都算作未结算。
    两者语义不同，**不得相加**；写侧预算核算继续只使用后者，本函数用于诊断与
    结果未知处理。
    """

    return tuple(
        outcome
        for outcome in read_attempt_outcomes(out_root, invocation_id)
        if outcome.reservation_retained
    )


def content_budget_exhausted(
    state: WriterInvocationLedgerStateV1, max_attempts: int
) -> bool:
    """内容预算是否真的耗尽（§9.2）。

    只有**真实内容尝试**（provider send）用满上限才算耗尽；仅有预发送拒绝事件不算——
    否则一个从未发送过请求的 invocation 会被拒发事件永久锁死。
    """

    if state.accepted:
        return False
    limit = int(max_attempts) if int(max_attempts) > 0 else state.content_attempt_limit
    return state.counters.content_attempt_count >= limit


def build_resume_preflight(
    out_root: str | Path,
    required_invocation_ids: list[str] | tuple[str, ...],
    *,
    execution_id: str = "",
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT,
) -> ResumePreflightV1:
    """在进入 Writer 主循环前检查是否已有必需页耗尽内容预算（零新增调用）。"""

    for invocation_id in required_invocation_ids or ():
        state = read_invocation_ledger_state(
            out_root, invocation_id, content_attempt_limit=content_attempt_limit
        )
        if not state.exhausted:
            continue
        return ResumePreflightV1(
            allowed=False,
            code=RESUME_EXHAUSTED_INVOCATION,
            execution_id=str(execution_id),
            invocation_id=state.invocation_id,
            content_attempts_used=state.counters.content_attempt_count,
            content_attempt_limit=state.content_attempt_limit,
            last_provider_attempt=state.last_provider_attempt,
            last_content_failure_codes=state.last_content_failure_codes,
            rejected_before_send_events=state.counters.rejected_before_send_events,
            allowed_next_action="fork_authoring_with_new_contract",
            detail=(
                f"{state.counters.content_attempt_count}/"
                f"{state.content_attempt_limit} content attempts used; "
                f"rejected_before_send={list(state.counters.rejected_before_send_events)}"
            ),
        )
    return ResumePreflightV1(allowed=True, execution_id=str(execution_id))


__all__ = [
    "DEFAULT_CONTENT_ATTEMPT_LIMIT",
    "FailureCodeV1",
    "RESUME_EXHAUSTED_INVOCATION",
    "ResumePreflightV1",
    "WriterAttemptCountersV1",
    "WriterInvocationLedgerStateV1",
    "AttemptOutcomeV1",
    "SEND_OUTCOME_UNKNOWN",
    "build_resume_preflight",
    "content_budget_exhausted",
    "read_attempt_outcomes",
    "read_invocation_ledger_state",
    "unsettled_reservations",
]
