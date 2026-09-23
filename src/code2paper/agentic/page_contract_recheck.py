"""PR C.6：发送前用**最终实际请求**复核冻结 page contract（审计 §C.6）。

分页/适配器可以把段落集合改掉；primaries 有 envelope digest 兜底，但 content repair
请求按设计不走同一个 envelope，于是"adapter 后来又追加段落"这类漏项会直接发出去。
本模块把准入时冻结的契约（该 invocation 最早一次持久化的 provider-request）提取成
可比较快照，并在发送前对**实际** payload 做确定性复核——只负责拒绝，不改页、不重排。

这是对 compiler/adapter 漏项的保护，不是第三套规划器。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "PageContractSnapshotV1",
    "capture_page_contract_snapshot",
    "page_contract_snapshot_from_payload",
    "compare_actual_request_to_page_contract",
    "page_output_cap_failures",
    "resolve_frozen_page_output_cap",
    "ACTUAL_PAGE_CONTRACT_MISMATCH",
]

ACTUAL_PAGE_CONTRACT_MISMATCH = "actual_page_contract_mismatch"

_CONTRACT_SCOPE_KEYS: tuple[str, ...] = (
    "allowed_detail_ids",
    "required_detail_ids",
    "allowed_formula_obligation_ids",
    "allowed_formula_package_ids",
    "required_rhetorical_moves",
)


class PageContractSnapshotV1(BaseModel):
    """准入时冻结的 page contract（来自最早一次持久化请求）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    page_id: str = ""
    section_id: str = ""
    attempt: int = 0
    paragraph_ids: tuple[str, ...] = ()
    scope: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    max_output_tokens: int = 0
    request_digest: str = ""
    source_path: str = ""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sorted_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, set)):
        return tuple(sorted(str(item) for item in value if str(item).strip()))
    return ()


def capture_page_contract_snapshot(
    out_root: str | Path,
    invocation_id: str,
) -> PageContractSnapshotV1 | None:
    """从最早一次持久化请求提取冻结契约；没有持久化请求时返回 ``None``。"""

    ledger = Path(out_root) / "artifacts" / "06_authoring" / "invocations"
    if not ledger.is_dir():
        return None
    candidates: list[tuple[int, Path, dict[str, Any]]] = []
    for directory in sorted(path for path in ledger.iterdir() if path.is_dir()):
        for path in sorted(directory.glob("attempt-*.provider-request.json")):
            payload = _read_object(path)
            if str(payload.get("invocation_id") or "") != str(invocation_id):
                continue
            try:
                attempt = int(payload.get("attempt") or 0)
            except (TypeError, ValueError):
                attempt = 0
            candidates.append((attempt, path, payload))
    if not candidates:
        return None
    attempt, path, payload = sorted(candidates, key=lambda item: (item[0], str(item[1])))[0]
    input_payload = payload.get("input_payload")
    plan = (input_payload or {}).get("narrative_plan") if isinstance(input_payload, Mapping) else None
    plan = plan if isinstance(plan, Mapping) else {}
    binding = (input_payload or {}).get("binding_contract") if isinstance(input_payload, Mapping) else None
    binding = binding if isinstance(binding, Mapping) else {}
    config = payload.get("config") if isinstance(payload.get("config"), Mapping) else {}
    return PageContractSnapshotV1(
        invocation_id=str(invocation_id),
        page_id=str(plan.get("page_id") or ""),
        section_id=str(plan.get("section_id") or ""),
        attempt=attempt,
        paragraph_ids=tuple(str(item) for item in (plan.get("page_paragraph_ids") or ())),
        scope={key: _sorted_strings(binding.get(key)) for key in _CONTRACT_SCOPE_KEYS},
        max_output_tokens=int(config.get("max_output_tokens") or 0),
        request_digest=str(payload.get("request_digest") or ""),
        source_path=str(path),
    )


def page_contract_snapshot_from_payload(
    *,
    invocation_id: str,
    payload: Mapping[str, Any] | None,
    attempt: int = 0,
    request_digest: str = "",
    source_path: str = "",
) -> PageContractSnapshotV1:
    """从**内存中的实际请求**构造契约快照。

    同一次运行里，content repair 可能在上一次请求落盘之前就被构造出来（primary 的
    provider-request 在响应处理之后才发布），因此 repair 不能只依赖磁盘上的历史请求。
    """

    plan = (payload or {}).get("narrative_plan") if isinstance(payload, Mapping) else None
    plan = plan if isinstance(plan, Mapping) else {}
    binding = (payload or {}).get("binding_contract") if isinstance(payload, Mapping) else None
    binding = binding if isinstance(binding, Mapping) else {}
    config = (payload or {}).get("config") if isinstance(payload, Mapping) else None
    config = config if isinstance(config, Mapping) else {}
    return PageContractSnapshotV1(
        invocation_id=str(invocation_id),
        page_id=str(plan.get("page_id") or ""),
        section_id=str(plan.get("section_id") or ""),
        attempt=int(attempt or 0),
        paragraph_ids=tuple(str(item) for item in (plan.get("page_paragraph_ids") or ())),
        scope={key: _sorted_strings(binding.get(key)) for key in _CONTRACT_SCOPE_KEYS},
        max_output_tokens=int(config.get("max_output_tokens") or 0),
        request_digest=str(request_digest or ""),
        source_path=str(source_path or ""),
    )


def resolve_frozen_page_output_cap(
    snapshot: PageContractSnapshotV1 | None,
    invocation: Any | None = None,
) -> int:
    """该页**冻结**的输出上限（审计 §C.6）。

    请求 payload 里显式声明的 ``config.max_output_tokens`` 优先；真实 unified 页请求
    不携带 ``config``，此时以调用计划冻结的每页预算为准。两者都没有时返回 0，表示
    "没有冻结值"（调用方不得据此放行一个未知的实际上限）。
    """

    declared = int(getattr(snapshot, "max_output_tokens", 0) or 0)
    if declared > 0:
        return declared
    return int(getattr(invocation, "max_output_tokens", 0) or 0)


def page_output_cap_failures(
    snapshot: PageContractSnapshotV1 | None,
    invocation: Any | None = None,
    *,
    actual_max_output_tokens: int,
) -> tuple[str, ...]:
    """比较冻结与**实际**输出上限（审计 §C.6/§C.7）。

    * 冻结值未知（0）→ 没有可比对象，不产出失败（envelope digest 仍覆盖 primary）；
    * 实际值未知（0）而冻结值 >0 → fail-closed：无法证明没超限，不得静默放行；
    * 实际值 > 冻结值 → 契约不匹配（发送前拒绝）。
    """

    frozen = resolve_frozen_page_output_cap(snapshot, invocation)
    if frozen <= 0:
        return ()
    actual = int(actual_max_output_tokens or 0)
    if actual <= 0:
        return ("unified_actual_output_cap_unknown",)
    if actual > frozen:
        return (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:output_cap:{actual}>{frozen}",)
    return ()


def compare_actual_request_to_page_contract(
    snapshot: PageContractSnapshotV1 | None,
    *,
    invocation_id: str,
    payload: Mapping[str, Any] | None,
    page_id: str = "",
    section_id: str = "",
    max_output_tokens: int = 0,
    is_repair: bool = False,
) -> tuple[str, ...]:
    """比较**实际**请求与冻结契约；返回失败码（空元组 = 一致）。

    * 没有冻结契约时：primary 放行（envelope digest 已覆盖），repair **拒绝**——
      repair 按设计不比对 envelope，失去契约就没有任何东西能证明它没被改页。
    * 段落集合与顺序必须逐一相等：追加/删除/重排都拒绝。
    * 明细/公式/修辞 scope 必须相等（repair 允许附带 repair packet，但不允许改 scope）。
    * 输出上限不得超过冻结值。
    """

    if snapshot is None:
        if is_repair:
            return (f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:frozen_page_contract_missing",)
        return ()

    failures: list[str] = []
    plan = (payload or {}).get("narrative_plan") if isinstance(payload, Mapping) else None
    plan = plan if isinstance(plan, Mapping) else {}
    binding = (payload or {}).get("binding_contract") if isinstance(payload, Mapping) else None
    binding = binding if isinstance(binding, Mapping) else {}

    actual_paragraphs = tuple(str(item) for item in (plan.get("page_paragraph_ids") or ()))
    if actual_paragraphs != snapshot.paragraph_ids:
        failures.append(
            f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:paragraph_ids:"
            f"expected={len(snapshot.paragraph_ids)}:actual={len(actual_paragraphs)}"
        )
    actual_page = str(plan.get("page_id") or page_id or "")
    if snapshot.page_id and actual_page != snapshot.page_id:
        failures.append(f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:page_id")
    actual_section = str(plan.get("section_id") or section_id or "")
    if snapshot.section_id and actual_section != snapshot.section_id:
        failures.append(f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:section_id")
    for key, expected in snapshot.scope.items():
        if not expected:
            continue
        actual = _sorted_strings(binding.get(key))
        if actual != expected:
            failures.append(f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:scope:{key}")
    if snapshot.max_output_tokens and int(max_output_tokens) > int(snapshot.max_output_tokens):
        failures.append(
            f"{ACTUAL_PAGE_CONTRACT_MISMATCH}:output_cap:"
            f"{int(max_output_tokens)}>{int(snapshot.max_output_tokens)}"
        )
    return tuple(failures)
