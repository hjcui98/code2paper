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
import re
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

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


#: 统一恢复状态（审计 §B.3 的八种结论）。每个 invocation 在任一时刻只能落在其中之一，
#: CLI / doctor / resume preflight / 发送包装器必须消费同一个值。
AttemptRecoveryStateV1 = Literal[
    "reserved_not_sent",
    "send_outcome_unknown",
    "response_received_unsettled",
    "response_missing_or_ledger_inconsistent",
    "validation_pending",
    "ledger_corrupt",
    "accepted_reusable",
    "content_budget_exhausted",
]

#: 每种状态的允许/禁止动作（供 CLI/doctor 直接展示，避免各处再解释）。
RECOVERY_ACTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "reserved_not_sent": (
        ("release_the_reservation", "record_an_audit_event"),
        ("count_it_as_a_content_failure",),
    ),
    "send_outcome_unknown": (
        ("reconcile_if_the_provider_supports_it",),
        ("assume_not_sent", "silently_retry"),
    ),
    "response_received_unsettled": (
        ("verify_request_and_response_digests_then_settle_locally",),
        ("request_the_same_content_again",),
    ),
    "response_missing_or_ledger_inconsistent": (
        ("block_with_a_recovery_reason",),
        ("claim_offline_replay",),
    ),
    "validation_pending": (
        ("validate_the_same_contract_locally_and_persist_the_result",),
        ("treat_the_missing_acceptance_as_accepted",),
    ),
    "ledger_corrupt": (
        ("block_with_a_typed_reason",),
        ("ignore_the_file_and_take_a_fresh_budget",),
    ),
    "accepted_reusable": (
        ("reuse_the_accepted_version",),
        ("let_historical_refusals_override_it",),
    ),
    "content_budget_exhausted": (
        ("summarize_the_primary_failures_and_stop",),
        ("continue_with_a_higher_attempt_number_on_the_same_root",),
    ),
}

#: 参与 attempt 集合构造的事件文件（审计 §B.4：所有已定义事件的并集，而不是只看 completed）。
_ATTEMPT_EVENT_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("started", ".started.json"),
    ("request", ".provider-request.json"),
    ("response", ".provider-response.json"),
    ("completed", ".completed.json"),
    ("acceptance", ".content-acceptance.json"),
    ("output_fragment", ".output-fragment-"),
)


class InvocationRecoveryV1(BaseModel):
    """统一归约结论：状态 + 主要成因 + 计数器 + 允许/禁止动作（审计 §B.3/§B.4）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    state: AttemptRecoveryStateV1
    primary_cause: str = ""
    counters: WriterAttemptCountersV1 = WriterAttemptCountersV1()
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT
    accepted: bool = False
    primary_accepted: bool = False
    #: 已可能发送但结果未确定的 attempt（不得免费重发）。
    unknown_reservation_attempts: tuple[int, ...] = ()
    #: 已落盘但无法结算/损坏的证据文件（相对 dir 的路径）。
    blocks: tuple[str, ...] = ()
    evidence: dict[str, str] = Field(default_factory=dict)
    last_content_failure_codes: tuple[str, ...] = ()
    last_rejection_code: str = ""
    #: 最近一次**真实 provider 调用**的事件序号（与事件序号上限不同）。
    last_provider_attempt: int = 0
    allowed_actions: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    #: 契约绑定：验收只有在 execution/plan/request/response/validator 一致时才可复用。
    contract_digest: str = ""
    contract_mismatch: tuple[str, ...] = ()

    @property
    def content_attempts_remaining(self) -> int:
        return max(0, int(self.content_attempt_limit) - int(self.counters.content_attempt_count))

    @property
    def exhausted(self) -> bool:
        return self.state == "content_budget_exhausted"

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _attempt_event_files(invocation_dir: Path) -> tuple[dict[int, dict[str, Path]], tuple[str, ...]]:
    """按 attempt 归集**所有**已定义事件文件（审计 §B.4 的并集，而不是只看 completed）。

    文件名形态是 ``attempt-0001.<kind>.json``（点分隔，不是连字符）。
    """

    events: dict[int, dict[str, Path]] = {}
    if not invocation_dir.is_dir():
        return events, ()
    pattern = re.compile(r"^attempt-(\d+)\.(.+)\.json$")
    for path in sorted(invocation_dir.glob("attempt-*.json")):
        match = pattern.match(path.name)
        if not match:
            continue
        attempt = int(match.group(1))
        remainder = match.group(2)
        kind = ""
        if remainder == "started":
            kind = "started"
        elif remainder == "provider-request":
            kind = "request"
        elif remainder == "provider-response":
            kind = "response"
        elif remainder == "completed":
            kind = "completed"
        elif remainder == "content-acceptance":
            kind = "acceptance"
        elif remainder.startswith("output-fragment-"):
            kind = "output_fragment"
        if not kind:
            continue
        events.setdefault(attempt, {})[kind] = path
    return events, ()


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    """严格读取：返回 (payload, error)。损坏必须作为事实报出，不能当成"没有这个文件"。"""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{path.name}:{type(exc).__name__}"
    if not isinstance(payload, dict):
        return None, f"{path.name}:not_an_object"
    return payload, ""


def _resolve_invocation_directory(out_root: Path, invocation_id: str) -> tuple[Path, str]:
    """精确解析 invocation 目录。

    审计 §B.4：禁止 substring 选第一个目录。允许两种精确形态：目录名等于
    ``invocation_id.replace(':', '-')``，或该名加一个 ``-<digest>`` 后缀；后者必须由
    回执内的 ``invocation_id`` 字段确认。
    """

    ledger = Path(out_root) / "artifacts" / "06_authoring" / "invocations"
    expected = invocation_id.replace(":", "-")
    exact = ledger / expected
    if exact.is_dir():
        return exact, ""
    candidates = sorted(
        item
        for item in ledger.glob(f"{expected}-*")
        if item.is_dir() and item.name.startswith(expected + "-")
    )
    for candidate in candidates:
        suffix = candidate.name[len(expected) + 1 :]
        # 后缀必须是单段摘要式标识（无路径分隔、无额外 '-' 结构歧义）。
        if not suffix or "/" in suffix:
            continue
        declared: set[str] = set()
        for receipt in sorted(candidate.glob("attempt-*.json")):
            payload, _error = _read_json_object(receipt)
            if payload:
                value = str(payload.get("invocation_id") or "").strip()
                if value:
                    declared.add(value)
        if declared and declared != {invocation_id}:
            # 回执自称是别的 invocation：绝不按目录名硬认。
            return exact, f"invocation_directory_identity_conflict:{invocation_id}"
        return candidate, ""
    return exact, ("" if not candidates else f"invocation_directory_ambiguous:{invocation_id}")


def reduce_invocation_recovery(
    out_root: str | Path,
    invocation_id: str,
    *,
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT,
    contract_digests: Mapping[str, str] | None = None,
) -> InvocationRecoveryV1:
    """把一个 invocation 的所有已落盘事件归约成**唯一**恢复结论（审计 §B.3）。"""

    directory, resolve_error = _resolve_invocation_directory(Path(out_root), invocation_id)
    limit = int(content_attempt_limit) if int(content_attempt_limit) > 0 else DEFAULT_CONTENT_ATTEMPT_LIMIT
    if resolve_error:
        return _recovery(
            invocation_id,
            state="ledger_corrupt",
            primary_cause=resolve_error,
            limit=limit,
            blocks=(resolve_error,),
        )
    if not directory.is_dir():
        # 缺失目录是事实：没有事件、没有已用预算（由调用方决定是否必需）。
        return _recovery(
            invocation_id,
            state="reserved_not_sent",
            primary_cause="invocation_directory_missing",
            limit=limit,
        )

    events, unparsable = _attempt_event_files(directory)
    corrupt: list[str] = list(unparsable)
    sends = 0
    content_attempts = 0
    repairs = 0
    rejected_before_send: list[int] = []
    last_provider_attempt = 0
    last_rejection = ""
    failure_codes: tuple[str, ...] = ()
    accepted = False
    primary_accepted = False
    unknown_reservations: list[int] = []
    #: 有响应/交付但**没有**验收记录 → 本地可结算。
    unvalidated_attempts: list[int] = []
    #: 有验收记录但未通过 → 已经评价过，不能靠本地重验"变绿"。
    rejected_attempts: list[int] = []
    response_unsettled: list[int] = []
    response_missing: list[int] = []
    reserved_not_sent: list[int] = []
    contract_mismatch: list[str] = []

    for attempt in sorted(events):
        files = events[attempt]
        completed_payload: dict[str, Any] = {}
        if "completed" in files:
            payload, error = _read_json_object(files["completed"])
            if error:
                corrupt.append(error)
            else:
                completed_payload = payload or {}

        code = str(completed_payload.get("delivery_rejection_code") or "")
        sent_flag = bool(completed_payload.get("sent_to_caller", True)) if completed_payload else None
        if code.startswith("attempt_limit_exhausted:"):
            rejected_before_send.append(attempt)
            last_rejection = code
            if ">" in code.rsplit(":", 1)[-1]:
                try:
                    limit = max(limit, int(code.rsplit(">", 1)[1]))
                except ValueError:
                    pass
        elif sent_flag:
            sends += 1
            content_attempts += 1
            last_provider_attempt = attempt
            if bool(completed_payload.get("content_repair_attempt")):
                repairs += 1

        # 崩溃点：只有 request 没有 completed → 是否发送不可确定。
        if "request" in files and not completed_payload:
            unknown_reservations.append(attempt)
        elif "started" in files and "request" not in files and not completed_payload:
            reserved_not_sent.append(attempt)
        if "response" in files and not completed_payload:
            response_unsettled.append(attempt)
        pre_send_refusal = bool(code.startswith("attempt_limit_exhausted:")) or (
            completed_payload and sent_flag is False
        )
        if completed_payload and "response" not in files and not pre_send_refusal:
            response_missing.append(attempt)

        if "acceptance" in files:
            acceptance_path = files["acceptance"]
            payload, error = _read_json_object(acceptance_path)
            if error:
                corrupt.append(error)
            else:
                accepted_payload = payload or {}
                if contract_digests:
                    for key, expected in contract_digests.items():
                        declared = str(accepted_payload.get(key) or "")
                        if declared and expected and declared != expected:
                            contract_mismatch.append(f"{attempt}:{key}")
                if bool(accepted_payload.get("accepted")):
                    accepted = True
                    if not bool(completed_payload.get("content_repair_attempt")):
                        primary_accepted = True
                else:
                    rejected_attempts.append(attempt)
                # 只有**真实内容尝试**的验收失败才算"主要失败"：纯拒发事件的
                # acceptance 文件（若存在）不得覆盖最近一次真实失败的原因。
                if sent_flag or "response" in files:
                    codes = _acceptance_failure_codes(acceptance_path)
                    if codes:
                        failure_codes = codes
        elif completed_payload and not code.startswith("attempt_limit_exhausted:"):
            # 有可评价响应但缺少验收记录 → 待本地验收，不得当成接受。
            unvalidated_attempts.append(attempt)

    # 本地验证重放（§B.5）：只认**当前 validator 身份**的重放；旧身份的重放不得复用。
    replays = read_validation_replays(directory)
    stale_replays: list[str] = []
    for record, _path in replays:
        expected_validator = str((contract_digests or {}).get("validator_bundle_digest") or "")
        if expected_validator and record.validator_bundle_digest != expected_validator:
            stale_replays.append(
                f"stale_validation_replay:{record.attempt}:{record.validator_bundle_digest}"
            )
            continue
        # 无论接受与否，该 attempt 都已经结算过 → 不再是"待本地验收"。
        unvalidated_attempts = [a for a in unvalidated_attempts if a != record.attempt]
        completed_payload = {}
        if "completed" in events.get(record.attempt, {}):
            completed_payload = (
                _read_json_object(events[record.attempt]["completed"])[0] or {}
            )
        if record.accepted:
            accepted = True
            if not bool(completed_payload.get("content_repair_attempt")):
                primary_accepted = True
        else:
            rejected_attempts.append(record.attempt)
            if record.failure_codes:
                failure_codes = tuple(record.failure_codes)

    if corrupt:
        state: AttemptRecoveryStateV1 = "ledger_corrupt"
        cause = "ledger_corrupt:" + ",".join(sorted(dict.fromkeys(corrupt))[:3])
    elif accepted:
        state = "accepted_reusable"
        cause = "accepted_response_matches_contract" if not contract_mismatch else "accepted_but_contract_mismatch"
    elif response_missing:
        state = "response_missing_or_ledger_inconsistent"
        cause = "completed_without_response_reference"
    elif unvalidated_attempts:
        # 有可评价响应但**从未验收**：先用本地验收把它结算掉（不产生新发送），而不是
        # 直接判"预算耗尽"。若本地验收拒绝，下一次归约才会落到 exhausted。
        state = "validation_pending"
        cause = "response_present_without_acceptance"
    elif content_attempts >= limit:
        state = "content_budget_exhausted"
        cause = "content_attempts_exhausted:" + (",".join(failure_codes) or "unknown")
    elif response_unsettled:
        # response 已落盘是信息最多的崩溃点：先按"待本地结算"处理，而不是
        # 因为同一 attempt 也有 request 就退化成"发送结果未知"。
        state = "response_received_unsettled"
        cause = "response_persisted_without_completed"
    elif unknown_reservations:
        state = "send_outcome_unknown"
        cause = "request_persisted_without_completed"
    else:
        state = "reserved_not_sent"
        cause = "reserved_without_send_boundary" if reserved_not_sent else "no_events"

    return _recovery(
        invocation_id,
        state=state,
        primary_cause=cause,
        limit=limit,
        counters=WriterAttemptCountersV1(
            event_seq=max(events) if events else 0,
            provider_send_count=sends,
            content_attempt_count=content_attempts,
            content_repair_count=repairs,
            rejected_before_send_events=tuple(rejected_before_send),
        ),
        accepted=accepted,
        primary_accepted=primary_accepted,
        unknown_reservation_attempts=tuple(unknown_reservations),
        blocks=tuple(dict.fromkeys(corrupt)),
        last_content_failure_codes=failure_codes,
        last_rejection_code=last_rejection,
        last_provider_attempt=last_provider_attempt,
        contract_mismatch=tuple(dict.fromkeys(contract_mismatch + stale_replays)),
        evidence={
            f"attempt-{attempt:04d}": ",".join(sorted(events[attempt]))
            for attempt in sorted(events)
        },
    )


def _recovery(
    invocation_id: str,
    *,
    state: AttemptRecoveryStateV1,
    primary_cause: str,
    limit: int,
    counters: WriterAttemptCountersV1 | None = None,
    accepted: bool = False,
    primary_accepted: bool = False,
    unknown_reservation_attempts: tuple[int, ...] = (),
    blocks: tuple[str, ...] = (),
    last_content_failure_codes: tuple[str, ...] = (),
    last_rejection_code: str = "",
    last_provider_attempt: int = 0,
    contract_mismatch: tuple[str, ...] = (),
    evidence: dict[str, str] | None = None,
) -> InvocationRecoveryV1:
    allowed, forbidden = RECOVERY_ACTIONS.get(state, ((), ()))
    return InvocationRecoveryV1(
        invocation_id=str(invocation_id),
        state=state,
        primary_cause=primary_cause,
        counters=counters or WriterAttemptCountersV1(),
        content_attempt_limit=int(limit),
        accepted=bool(accepted),
        primary_accepted=bool(primary_accepted),
        unknown_reservation_attempts=unknown_reservation_attempts,
        blocks=blocks,
        evidence=dict(evidence or {}),
        last_content_failure_codes=last_content_failure_codes,
        allowed_actions=allowed,
        forbidden_actions=forbidden,
        last_rejection_code=last_rejection_code,
        last_provider_attempt=int(last_provider_attempt),
        contract_mismatch=contract_mismatch,
    )


#: 本地验证重放记录的文件名模式（审计 §B.5）：**新增**证据，绝不改写历史 acceptance。
VALIDATION_REPLAY_SUFFIX = ".validation-replay."


class ValidationReplayV1(BaseModel):
    """一次本地结算的只读记录（审计 §B.5）。

    "缺失结算"与"validator/代码身份变化后的重验"必须能被区分：因此重放记录显式携带
    ``source_response_digest`` 与 ``validator_bundle_digest``，并且**只新增、不覆盖**。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    invocation_id: str
    attempt: int
    accepted: bool
    failure_codes: tuple[str, ...] = ()
    source_response_digest: str = ""
    validator_bundle_digest: str = ""
    contract_digest: str = ""
    detail: str = ""


def validation_replay_path(
    invocation_dir: Path, attempt: int, validator_bundle_digest: str
) -> Path:
    token = str(validator_bundle_digest or "unspecified").removeprefix("sha256:")[:16]
    return invocation_dir / f"attempt-{attempt:04d}{VALIDATION_REPLAY_SUFFIX}{token}.json"


def read_validation_replays(
    invocation_dir: Path,
) -> tuple[tuple[ValidationReplayV1, Path], ...]:
    """读取全部本地验证重放记录（不解析/不删除，损坏的跳过并留给 reducer 报块）。"""

    if not invocation_dir.is_dir():
        return ()
    found: list[tuple[ValidationReplayV1, Path]] = []
    for path in sorted(invocation_dir.glob(f"attempt-*{VALIDATION_REPLAY_SUFFIX}*.json")):
        payload, error = _read_json_object(path)
        if error or payload is None:
            continue
        try:
            found.append((ValidationReplayV1.model_validate(payload), path))
        except Exception:  # noqa: BLE001 - 损坏记录由调用方按块报告
            continue
    return tuple(found)


def publish_validation_replay(
    out_root: str | Path,
    invocation_id: str,
    *,
    attempt: int,
    accepted: bool,
    validator_bundle_digest: str,
    source_response_digest: str = "",
    contract_digest: str = "",
    failure_codes: tuple[str, ...] = (),
    detail: str = "",
) -> Path:
    """原子地追加一条本地结算记录（审计 §B.5）。

    拒绝的两种情况：
    * 该 attempt 已有**历史** ``content-acceptance.json`` —— 历史结论不可被本地重放冒充；
    * 同一 validator 身份的重放已存在 —— 重放本身也必须幂等。
    """

    directory, resolve_error = _resolve_invocation_directory(Path(out_root), str(invocation_id))
    if resolve_error or not directory.is_dir():
        raise FileNotFoundError(f"invocation_directory_unresolved:{invocation_id}")
    if (directory / f"attempt-{attempt:04d}.content-acceptance.json").is_file():
        raise ValueError("validation_replay_refuses_to_shadow_historical_acceptance")
    path = validation_replay_path(directory, int(attempt), validator_bundle_digest)
    if path.is_file():
        raise ValueError("validation_replay_already_published")
    record = ValidationReplayV1(
        invocation_id=str(invocation_id),
        attempt=int(attempt),
        accepted=bool(accepted),
        failure_codes=tuple(failure_codes),
        source_response_digest=str(source_response_digest or ""),
        validator_bundle_digest=str(validator_bundle_digest or ""),
        contract_digest=str(contract_digest or ""),
        detail=str(detail or "")[:320],
    )
    path.write_text(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return path


def read_invocation_ledger_state(
    out_root: str | Path,
    invocation_id: str,
    *,
    content_attempt_limit: int = DEFAULT_CONTENT_ATTEMPT_LIMIT,
) -> WriterInvocationLedgerStateV1:
    """一个 invocation 的只读状态视图（审计 §B.1：统一由 reducer 派生）。

    保留既有字段供调用方渐进迁移；新增的权威结论在
    :func:`reduce_invocation_recovery`（``state`` / ``unknown_reservation_attempts`` /
    ``blocks``）。这里不再自己 glob 事件、也不再用事件序号判断预算。
    """

    recovery = reduce_invocation_recovery(
        out_root,
        invocation_id,
        content_attempt_limit=content_attempt_limit,
    )
    return WriterInvocationLedgerStateV1(
        invocation_id=recovery.invocation_id,
        counters=recovery.counters,
        content_attempt_limit=recovery.content_attempt_limit,
        accepted=recovery.accepted,
        primary_accepted=recovery.primary_accepted,
        last_provider_attempt=recovery.last_provider_attempt,
        last_content_failure_codes=recovery.last_content_failure_codes,
        last_rejection_code=recovery.last_rejection_code,
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

    # 审计 §B.4：attempt 集合必须来自**所有**已定义事件的并集（started/request/
    # response/completed/acceptance/fragment），否则孤立 request/response 会漏掉。
    directory, _resolve_error = _resolve_invocation_directory(Path(out_root), str(invocation_id))
    events, _unparsable = _attempt_event_files(directory)
    numbers: set[int] = set(events)

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
    "AttemptRecoveryStateV1",
    "InvocationRecoveryV1",
    "RECOVERY_ACTIONS",
    "reduce_invocation_recovery",
    "ValidationReplayV1",
    "publish_validation_replay",
    "read_validation_replays",
    "validation_replay_path",
    "VALIDATION_REPLAY_SUFFIX",
]
