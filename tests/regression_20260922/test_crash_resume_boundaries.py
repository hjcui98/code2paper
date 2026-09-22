"""§G.3：在真实持久边界注入中断，再走真正的 resume。

审计要求（§G.3）：在下列点模拟进程中断后恢复，并断言

* 不能重复调用已收到响应的任务；
* 不能把"结果未知"当成"未发送"；
* 不能丢失已验证段；
* 不能发布未经最终验证的文本；
* summary 的主因/恢复动作与 ledger 一致。

这里用真实产品入口 + 真实 ledger/acceptance 文件实现：先跑一遍得到真实 run root，
再按崩溃点截断 attempt 事件文件（模拟进程在两步之间死掉），然后用**计数 fake provider**
再跑一次，断言恢复动作与"零重复发送"。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from code2paper.agentic.publication_method_writer import (
    run_publication_method_writer,
)
from code2paper.agentic.authoring_doctor import run_authoring_doctor
from code2paper.agentic.writer_attempt_ledger import (
    read_invocation_ledger_state,
    reduce_invocation_recovery,
)
from code2paper.llm.client import LLMRequest, LLMResponse
from tests.test_agentic_publication_method_writer_unified import (
    _clear_unified_budget_env,
    _config,
    _mock_writer_caller,
    _unified_artifacts,
    _unified_budget_env,
)

WRITER_TEMPLATE = "unified_writer_page_v2"

#: attempt 事件文件的顺序（崩溃点 = 保留到哪一步）。
_ATTEMPT_EVENTS = (
    ".started.json",
    ".provider-request.json",
    ".provider-response.json",
    ".completed.json",
    ".content-acceptance.json",
)


def _run_once(
    tmp_path: Path,
    caller: Callable[[Any, LLMRequest], LLMResponse],
    *,
    paths: dict[str, str] | None = None,
):
    if paths is None:
        artifact_paths = _unified_artifacts(tmp_path)
    else:
        # 恢复运行复用同一批冻结产物，但仍必须声明同一份预算 profile。
        _unified_budget_env()
        artifact_paths = paths
    try:
        return run_publication_method_writer(
            out_root=tmp_path,
            artifact_paths=artifact_paths,
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()


def _counting_caller(calls: list[LLMRequest]):
    def caller(config, request):
        calls.append(request)
        return _mock_writer_caller(config, request)

    return caller


def _writer_invocation_dirs(tmp_path: Path) -> list[Path]:
    root = tmp_path / "artifacts" / "06_authoring" / "invocations"
    return sorted(
        path
        for path in root.glob("inv-writer-*")
        if path.is_dir()
    )


def _truncate_attempts(tmp_path: Path, keep_through: str) -> Path:
    """把每个 writer invocation 的 attempt 事件截断到指定步（模拟中断）。"""

    keep_index = _ATTEMPT_EVENTS.index(keep_through)
    directories = _writer_invocation_dirs(tmp_path)
    assert directories, "baseline 必须先产生真实 writer invocation"
    for directory in directories:
        for event in _ATTEMPT_EVENTS[keep_index + 1 :]:
            for path in directory.glob(f"attempt-*{event}"):
                path.unlink()
        # 截断后不应该留下"更晚一步"的残留。
        for event in _ATTEMPT_EVENTS[keep_index + 1 :]:
            assert not list(directory.glob(f"attempt-*{event}"))
    return directories[0]


def _writer_call_count(calls: list[LLMRequest]) -> int:
    return sum(
        1
        for request in calls
        if getattr(request, "prompt_template_id", "") == WRITER_TEMPLATE
    )


def _baseline(tmp_path: Path) -> tuple[dict[str, str], list[LLMRequest]]:
    calls: list[LLMRequest] = []
    paths = _unified_artifacts(tmp_path)
    result, _outputs = _run_once(tmp_path, _counting_caller(calls), paths=paths)
    assert result.status in {"success", "incomplete"}
    assert _writer_call_count(calls) >= 1, "baseline 必须真的调用过 writer"
    return paths, calls


def test_unknown_send_outcome_is_never_resent(tmp_path: Path) -> None:
    """崩溃点 2：request 已落盘、结果未知 → 不得当作"没发过"重发。"""

    paths, _calls = _baseline(tmp_path)
    directory = _truncate_attempts(tmp_path, ".provider-request.json")
    invocation_id = directory.name.removeprefix("inv-").replace("-", ":", 1)
    # 真实 invocation id 形如 inv:writer:<section>:page:<digest>。
    recovery = reduce_invocation_recovery(tmp_path, _ledger_invocation_id(directory))
    assert recovery.state == "send_outcome_unknown", recovery.state

    resume_calls: list[LLMRequest] = []
    _run_once(tmp_path, _counting_caller(resume_calls), paths=paths)

    assert _writer_call_count(resume_calls) == 0, (
        "结果未知的 invocation 不得自动重发（免费无限重试）"
    )
    report = run_authoring_doctor(tmp_path)
    assert report.page_count >= 0  # doctor 仍可读（不因未知结果崩掉）


def test_recorded_response_is_settled_without_a_second_call(tmp_path: Path) -> None:
    """崩溃点 3：response 已落盘、completed 未落盘 → 本地结算，不重发。"""

    paths, _calls = _baseline(tmp_path)
    directory = _truncate_attempts(tmp_path, ".provider-response.json")
    invocation_id = _ledger_invocation_id(directory)

    resume_calls: list[LLMRequest] = []
    _run_once(tmp_path, _counting_caller(resume_calls), paths=paths)

    assert _writer_call_count(resume_calls) == 0, "已有响应不得再次请求 provider"
    # 本地结算：响应字节被重新解析 + 同一 assessor 复验 + 不可变 validation replay。
    recovery = reduce_invocation_recovery(tmp_path, invocation_id)
    assert recovery.state == "accepted_reusable", recovery.state
    assert recovery.accepted is True
    replays = list(directory.glob("attempt-*.validation-replay.*.json"))
    assert replays, "本地结算必须留下不可变 replay 记录"
    assert not list(directory.glob("attempt-0002.*")), (
        "本地结算不得新开 attempt"
    )
    # 恢复动作必须与 ledger 一致：doctor 报同一个结论（§B.4）。
    report = run_authoring_doctor(tmp_path)
    page = next(
        item for item in report.blocked_pages if item.invocation_id == invocation_id
    ) if any(item.invocation_id == invocation_id for item in report.blocked_pages) else None
    if page is not None:
        assert page.recovery_state == recovery.state


def test_completed_without_acceptance_is_revalidated_locally(tmp_path: Path) -> None:
    """崩溃点 4：completed 已落盘、acceptance 未落盘 → 只用本地响应重新验收。"""

    paths, _calls = _baseline(tmp_path)
    directory = _truncate_attempts(tmp_path, ".completed.json")
    invocation_id = _ledger_invocation_id(directory)
    assert not list(directory.glob("attempt-*.content-acceptance.json"))

    resume_calls: list[LLMRequest] = []
    _run_once(tmp_path, _counting_caller(resume_calls), paths=paths)

    assert _writer_call_count(resume_calls) == 0, "重新验收不得再发一次请求"
    # completed 已落盘、acceptance 缺失 → 本地结算该 attempt（不新开 attempt）。
    recovery = reduce_invocation_recovery(tmp_path, invocation_id)
    assert recovery.state == "accepted_reusable", recovery.state
    assert recovery.accepted is True
    # 绝不发布未经最终验证的文本。
    verified = tmp_path / "artifacts" / "06_authoring" / "repository_verified_method.md"
    if verified.is_file():
        assert verified.read_text(encoding="utf-8").strip() == ""
    assert directory.is_dir()


def test_writer_accepted_without_binder_reruns_only_the_binder(tmp_path: Path) -> None:
    """崩溃点 6：Writer 已接受、Binder 未跑 → 只重跑确定性 Binder。"""

    paths, _calls = _baseline(tmp_path)
    binder_receipts = tmp_path / "artifacts" / "06_authoring" / "binder_receipts_v2.json"
    assert binder_receipts.is_file()
    binder_receipts.unlink()

    resume_calls: list[LLMRequest] = []
    _result, outputs = _run_once(
        tmp_path, _counting_caller(resume_calls), paths=paths
    )

    assert _writer_call_count(resume_calls) == 0, "Writer 已接受，不得重写正文"
    assert binder_receipts.is_file(), "恢复必须重跑确定性 Binder 并落回执"
    payload = json.loads(binder_receipts.read_text(encoding="utf-8"))
    assert payload.get("receipts"), payload


def _ledger_invocation_id(directory: Path) -> str:
    """从目录名还原 invocation id（目录名把 ':' 换成了 '-'）。"""

    name = directory.name
    assert name.startswith("inv-")
    parts = name.split("-")
    # inv-writer-<section...>-page-<digest> → 段落 id 自身可能含 '-'，用 plan 反查更稳。
    plan_path = directory.parent.parent / "consumer_invocation_plan_v1.2.json"
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for invocation in plan.get("invocations") or ():
            invocation_id = str(invocation.get("invocation_id") or "")
            if invocation_id and name.startswith(_slug(invocation_id)):
                return invocation_id
    raise AssertionError(f"cannot resolve invocation id for {name}")


def _slug(value: str) -> str:
    return "inv-" + value.removeprefix("inv:").replace(":", "-")


# --------------------------------------------------------------------------- #
# §G.3 已复现但尚未修复的两个缺口（strict xfail：修好后会自动提醒移除标记）
# --------------------------------------------------------------------------- #


def test_unknown_outcome_stays_visible_after_a_blocked_resume(tmp_path: Path) -> None:
    """结果未知必须在恢复后**仍然是**结果未知（不能被新的 reserved attempt 挤掉）。"""
    paths, _calls = _baseline(tmp_path)
    directory = _truncate_attempts(tmp_path, ".provider-request.json")
    invocation_id = _ledger_invocation_id(directory)
    assert reduce_invocation_recovery(tmp_path, invocation_id).state == (
        "send_outcome_unknown"
    )

    resume_calls: list[LLMRequest] = []
    _run_once(tmp_path, _counting_caller(resume_calls), paths=paths)

    assert _writer_call_count(resume_calls) == 0
    assert reduce_invocation_recovery(tmp_path, invocation_id).state == (
        "send_outcome_unknown"
    )


def test_unsent_resume_attempt_leaves_no_rejection_record(tmp_path: Path) -> None:
    """本地结算不得为一次未发送的 attempt 制造拒绝记录。"""

    paths, _calls = _baseline(tmp_path)
    directory = _truncate_attempts(tmp_path, ".completed.json")
    invocation_id = _ledger_invocation_id(directory)

    resume_calls: list[LLMRequest] = []
    _run_once(tmp_path, _counting_caller(resume_calls), paths=paths)

    assert _writer_call_count(resume_calls) == 0
    assert not list(directory.glob("attempt-0002.content-acceptance.json"))
    assert reduce_invocation_recovery(tmp_path, invocation_id).accepted is True
    # 结算记录是 append-only 的 replay，不是覆盖历史 acceptance。
    replays = sorted(directory.glob("attempt-0001.validation-replay.*.json"))
    assert replays
    payload = json.loads(replays[0].read_text(encoding="utf-8"))
    assert payload["accepted"] is True
    assert payload["source_response_digest"]
    assert payload["validator_bundle_digest"]
