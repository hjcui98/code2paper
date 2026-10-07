"""WP5：拒发/重试/恢复账本（方案 §9.2、§9.3）。

用事故归档的真实回执冻结"事件序号 ≠ 真实发送次数"，并验证恢复前置检查能给出
根因链而不是等到末尾报 acceptance_count:0。
"""

from __future__ import annotations

import json

import pytest

from code2paper.agentic.writer_attempt_ledger import (
    RESUME_EXHAUSTED_INVOCATION,
    build_resume_preflight,
    read_invocation_ledger_state,
)

from . import incident_archive

INCIDENT_DIR_NAME = (
    "inv-writer-MA-S3-page-"
    "751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815-"
    "f463066ebdc243a6"
)


def test_incident_counters_separate_events_from_sends() -> None:
    """4 条事件记录里只有 2 次真正的 provider 发送、1 次 content repair。"""

    state = read_invocation_ledger_state(
        _run_root(), INCIDENT_DIR_NAME
    )
    assert state.counters.event_seq == 4
    assert state.counters.provider_send_count == 2
    assert state.counters.content_attempt_count == 2
    assert state.counters.content_repair_count == 1
    assert state.counters.rejected_before_send_events == (3, 4)
    assert state.accepted is False
    assert state.last_provider_attempt == 2
    assert state.content_attempt_limit == 2
    assert state.exhausted is True
    assert state.content_attempts_remaining == 0


def test_incident_failure_codes_are_derived_not_parsed_by_callers() -> None:
    state = read_invocation_ledger_state(_run_root(), INCIDENT_DIR_NAME)
    assert "detail_witness_missing" in state.last_content_failure_codes


def test_resume_preflight_reports_root_cause_chain() -> None:
    """恢复前置检查在进入主循环前就给出结构化阻断（零新增调用）。"""

    preflight = build_resume_preflight(
        _run_root(),
        [INCIDENT_DIR_NAME],
        execution_id="exec-incident",
    )
    assert preflight.allowed is False
    assert preflight.code == RESUME_EXHAUSTED_INVOCATION
    assert preflight.execution_id == "exec-incident"
    assert preflight.content_attempts_used == 2
    assert preflight.content_attempt_limit == 2
    assert preflight.last_provider_attempt == 2
    assert preflight.rejected_before_send_events == (3, 4)
    assert preflight.allowed_next_action == "fork_authoring_with_new_contract"
    assert preflight.last_content_failure_codes


def test_resume_preflight_allows_unexhausted_invocations() -> None:
    accepted_dir = (
        "inv-writer-MA-S1-page-"
        "281af1e758001328894fc2f8200e5e244a060ff3eafae98e6dcfb3a428ed052a-"
        "68f416529f3b1c40"
    )
    preflight = build_resume_preflight(_run_root(), [accepted_dir])
    assert preflight.allowed is True
    assert preflight.code == ""

    state = read_invocation_ledger_state(_run_root(), accepted_dir)
    assert state.accepted is True
    assert state.exhausted is False
    assert state.counters.provider_send_count >= 1
    assert state.counters.rejected_before_send_events == ()


def test_missing_invocation_is_not_treated_as_exhausted(tmp_path) -> None:
    """缺目录/缺回执不得被当成"已耗尽"（不变量：不把缺失当结论）。"""

    state = read_invocation_ledger_state(tmp_path, "inv:writer:MA-S9:page:missing")
    assert state.counters.event_seq == 0
    assert state.counters.provider_send_count == 0
    assert state.exhausted is False

    preflight = build_resume_preflight(tmp_path, ["inv:writer:MA-S9:page:missing"])
    assert preflight.allowed is True


def _run_root():
    return incident_archive.archive_root()


def test_presend_refusals_do_not_consume_content_budget(tmp_path) -> None:
    """§9.2：只有真实内容尝试用满才算耗尽；两次拒发不能锁死从未发送的页。"""

    from code2paper.agentic.writer_attempt_ledger import content_budget_exhausted

    invocation = "inv:writer:MA-S3:page:demo"
    directory = tmp_path / "artifacts" / "06_authoring" / "invocations" / (
        "inv-writer-MA-S3-page-demo-0000"
    )
    directory.mkdir(parents=True)
    for index in (1, 2):
        (directory / f"attempt-{index:04d}.completed.json").write_text(
            json.dumps(
                {
                    "attempt": index,
                    "sent_to_caller": False,
                    "delivery_status": "rejected",
                    "delivery_rejection_code": (
                        "attempt_limit_exhausted:inv:writer:MA-S3:page:demo:"
                        f"{index}>2"
                    ),
                    "content_repair_attempt": False,
                    "provider_usage": None,
                }
            ),
            encoding="utf-8",
        )

    state = read_invocation_ledger_state(tmp_path, invocation)
    assert state.counters.provider_send_count == 0
    assert state.counters.content_attempt_count == 0
    assert state.counters.rejected_before_send_events == (1, 2)
    # 事件序号已到 2，但内容预算一次都没用过 → 不算耗尽。
    assert content_budget_exhausted(state, 2) is False

    incident = read_invocation_ledger_state(_run_root(), INCIDENT_DIR_NAME)
    assert content_budget_exhausted(incident, 2) is True


def test_accepted_invocation_is_never_exhausted() -> None:
    from code2paper.agentic.writer_attempt_ledger import content_budget_exhausted

    accepted_dir = (
        "inv-writer-MA-S1-page-"
        "281af1e758001328894fc2f8200e5e244a060ff3eafae98e6dcfb3a428ed052a-"
        "68f416529f3b1c40"
    )
    state = read_invocation_ledger_state(_run_root(), accepted_dir)
    assert state.accepted is True
    assert content_budget_exhausted(state, 0) is False


def _write_attempt(directory, attempt: int, files: dict[str, dict | None]) -> None:
    for suffix, payload in files.items():
        path = directory / f"attempt-{attempt:04d}.{suffix}.json"
        path.write_text(json.dumps(payload if payload is not None else {}), encoding="utf-8")


def test_crash_points_are_classified_without_losing_reservations(tmp_path) -> None:
    """§9.5：reservation 后未 send / send 后无 response / response 后未 completed /
    completed 后未 acceptance 必须各自可解释，且不得重复计费或丢预留。"""

    from code2paper.agentic.writer_attempt_ledger import (
        read_attempt_outcomes,
        unsettled_reservations,
    )

    invocation = "inv:writer:MA-S3:page:crash"
    directory = tmp_path / "artifacts" / "06_authoring" / "invocations" / (
        "inv-writer-MA-S3-page-crash-0001"
    )
    directory.mkdir(parents=True)
    _write_attempt(directory, 1, {"started": {}})
    _write_attempt(directory, 2, {"started": {}, "provider-request": {}})
    _write_attempt(directory, 3, {"started": {}, "provider-request": {}, "provider-response": {}})
    _write_attempt(
        directory,
        4,
        {
            "started": {},
            "provider-request": {},
            "provider-response": {},
            "completed": {"attempt": 4, "sent_to_caller": True, "delivery_status": "accepted"},
        },
    )
    _write_attempt(
        directory,
        5,
        {
            "started": {},
            "provider-request": {},
            "provider-response": {},
            "completed": {"attempt": 5, "sent_to_caller": True, "delivery_status": "accepted"},
            "content-acceptance": {"accepted": True},
        },
    )

    states = {item.attempt: item for item in read_attempt_outcomes(tmp_path, invocation)}
    assert states[1].state == "reservation_without_send"
    assert states[1].reservation_retained is False
    assert states[2].state == "send_outcome_unknown"
    assert states[2].reservation_retained is True
    assert states[3].state == "response_without_completion"
    assert states[3].reservation_retained is True
    assert states[4].state == "completed_without_acceptance"
    assert states[4].acceptance_replayable is True
    assert states[4].reservation_retained is False
    assert states[5].state == "settled"

    retained = unsettled_reservations(tmp_path, invocation)
    assert [item.attempt for item in retained] == [2, 3]


def test_incident_archive_attempts_are_settled_or_presend_rejections() -> None:
    from code2paper.agentic.writer_attempt_ledger import read_attempt_outcomes

    states = {
        item.attempt: item.state
        for item in read_attempt_outcomes(_run_root(), INCIDENT_DIR_NAME)
    }
    assert states == {
        1: "settled",
        2: "settled",
        3: "rejected_before_send",
        4: "rejected_before_send",
    }


def test_incident_refusals_are_not_billed_as_unsettled(tmp_path) -> None:
    """预算视角与崩溃点视角不得把"拒发事件"当成未结算开销（防双重扣费）。

    两者语义不同但**必须一致地对已完成的拒发事件不计费**：
    * `unsettled_started_attempt_records`（账本预算视角）= started 且无 completed；
    * `unsettled_reservations`（崩溃点视角）= 结果未知 / 有响应未完成。
    事故里 4 个 attempt 都有 completed 回执 → 两者都必须为空。
    """

    from code2paper.agentic.unified_invocation_ledger import (
        unsettled_started_attempt_records,
    )
    from code2paper.agentic.writer_attempt_ledger import unsettled_reservations

    root = _run_root()
    ledger_root = root / "artifacts" / "06_authoring" / "invocations"

    class _Plan:
        invocations: tuple = ()

    assert unsettled_started_attempt_records(ledger_root, _Plan()) == ()
    assert unsettled_reservations(root, INCIDENT_DIR_NAME) == ()


def test_presend_only_and_started_only_attempts_are_distinguished(tmp_path) -> None:
    """两种视角的差异被显式钉住：只在"已预留未发送"上不同，且都不产生未知开销。"""

    from code2paper.agentic.writer_attempt_ledger import read_attempt_outcomes

    invocation = "inv:writer:MA-S3:page:started-only"
    directory = tmp_path / "artifacts" / "06_authoring" / "invocations" / (
        "inv-writer-MA-S3-page-started-only-0001"
    )
    directory.mkdir(parents=True)
    (directory / "attempt-0001.started.json").write_text("{}", encoding="utf-8")
    (directory / "attempt-0002.started.json").write_text("{}", encoding="utf-8")
    (directory / "attempt-0002.provider-request.json").write_text("{}", encoding="utf-8")

    outcomes = {item.attempt: item for item in read_attempt_outcomes(tmp_path, invocation)}
    # 已预留未发送：不得计费（可释放）。
    assert outcomes[1].state == "reservation_without_send"
    assert outcomes[1].reservation_retained is False
    # 已发送无响应：结果未知，必须保留预留。
    assert outcomes[2].state == "send_outcome_unknown"
    assert outcomes[2].reservation_retained is True


def test_repair_accepted_page_is_complete_but_not_primary_accepted() -> None:
    """两种"接受"语义必须分开：页内容完成 vs 首次交付被接受。"""

    accepted_dir = (
        "inv-writer-MA-S1-page-"
        "281af1e758001328894fc2f8200e5e244a060ff3eafae98e6dcfb3a428ed052a-"
        "68f416529f3b1c40"
    )
    primary = read_invocation_ledger_state(_run_root(), accepted_dir)
    assert primary.accepted is True and primary.primary_accepted is True

    # MA-S5 页：首次被拒、repair 后接受 → 内容完成，但不是首次交付接受。
    repaired_dir = (
        "inv-writer-MA-S5-page-"
        "5c2d0db68504d5ae006260b0181541d6dd1d98eb6ec8423956efe075ad43d515-"
        "e6acde3701dd59d1"
    )
    repaired = read_invocation_ledger_state(_run_root(), repaired_dir)
    assert repaired.accepted is True
    assert repaired.primary_accepted is False
    assert repaired.exhausted is False


# --------------------------------------------------------------------------- #
# K04-GAP-1 / GAP-3：同一组真实产物的**恢复策略**（预留与前置检查）
# --------------------------------------------------------------------------- #
#
# 产物与消费者与 `test_ledger_recovery_matrix.py` 的 GAP 组**同一组**：
# `build_gap13_artifact_runs` 把报告写在会话级基目录，第二次调用只复读，不重造账本。


from .test_ledger_recovery_matrix import (  # noqa: E402  (复用同一组真实产物)
    build_gap13_artifact_runs,
)


@pytest.fixture(scope="module")
def gap13(tmp_path_factory) -> dict:
    return build_gap13_artifact_runs(tmp_path_factory.getbasetemp() / "k04-gap13")


def test_gap13_presend_refusal_and_unknown_send_keep_opposite_reservation_policy(
    gap13,
) -> None:
    """GAP-3：明确未发送不保留预留；结果未知必须保留。两种形态不得互相折抵。"""

    from code2paper.agentic.unified_invocation_ledger import (
        unsettled_started_attempt_records,
    )
    from code2paper.agentic.writer_attempt_ledger import (
        read_attempt_outcomes,
        reduce_invocation_recovery,
        unsettled_reservations,
    )

    invocation = gap13["invocation"]

    class _Invocation:
        def __init__(self, invocation_id: str) -> None:
            self.invocation_id = invocation_id
            self.max_input_tokens = 0
            self.role = "writer"

    class _Plan:
        def __init__(self, invocation_id: str) -> None:
            self.invocations = (_Invocation(invocation_id),)

    def _budget_view(run_root) -> list:
        return list(
            unsettled_started_attempt_records(
                run_root / "artifacts" / "06_authoring" / "invocations",
                _Plan(invocation),
            )
        )

    # (a) 明确未发送的合同拒发：不保留预留、不进预算视角、可重新准入。
    run_root_a = gap13["a"]["run_root"]
    assert unsettled_reservations(run_root_a, invocation) == ()
    assert _budget_view(run_root_a) == []
    refused_outcomes = {
        item.attempt: item for item in read_attempt_outcomes(run_root_a, invocation)
    }
    assert refused_outcomes[2].reservation_retained is False
    refused_state = read_invocation_ledger_state(run_root_a, invocation)
    assert refused_state.counters.content_attempt_count == 1
    assert refused_state.content_attempts_remaining == 1
    refused_recovery = reduce_invocation_recovery(
        run_root_a, invocation, content_attempt_limit=2
    )
    # 明确未发送：允许释放预留，且不得把拒发记成内容失败。
    assert "release_the_reservation" in refused_recovery.allowed_actions
    assert "count_it_as_a_content_failure" in refused_recovery.forbidden_actions
    assert build_resume_preflight(
        run_root_a, [invocation], execution_id="gap13-a"
    ).allowed is True

    # (c) 结果未知的真实崩溃：保留预留、进预算视角、禁止"当成未发送/静默重试"。
    run_root_c = gap13["c"]["run_root"]
    assert [item.attempt for item in unsettled_reservations(run_root_c, invocation)] == [1]
    records = _budget_view(run_root_c)
    assert [item.attempt for item in records] == [1]
    assert records[0].planned_input_tokens > 0
    unknown_outcomes = read_attempt_outcomes(run_root_c, invocation)
    assert unknown_outcomes[0].reservation_retained is True
    unknown_recovery = reduce_invocation_recovery(
        run_root_c, invocation, content_attempt_limit=2
    )
    assert unknown_recovery.unknown_reservation_attempts == (1,)
    assert {"assume_not_sent", "silently_retry"} <= set(
        unknown_recovery.forbidden_actions
    )
    # 结果未知：只允许对账，**不允许**把预留当未发送释放掉。
    assert "reconcile_if_the_provider_supports_it" in unknown_recovery.allowed_actions
    assert "release_the_reservation" not in unknown_recovery.allowed_actions

    # 两种形态在同一组消费者上给出相反结论（不是因为"都不许重发"）。
    assert refused_outcomes[2].reservation_retained is not unknown_outcomes[0].reservation_retained
    assert refused_state.accepted is False and unknown_recovery.accepted is False
    assert refused_state.counters.provider_send_count == 1  # 只有真正的首次发送
    assert unknown_recovery.counters.provider_send_count == 0  # 崩溃没有回执可计


def test_gap13_preflight_alone_does_not_clear_an_unknown_send(gap13) -> None:
    """GAP-3：前置检查只回答"是否耗尽"；未知发送必须由归约结论阻断，不能被它放行。"""

    from code2paper.agentic.writer_attempt_ledger import (
        build_resume_preflight,
        reduce_invocation_recovery,
    )

    invocation = gap13["invocation"]
    run_root_c = gap13["c"]["run_root"]

    preflight = build_resume_preflight(run_root_c, [invocation], execution_id="gap13-c")
    assert preflight.allowed is True, "未耗尽：前置检查按设计放行相位"

    recovery = reduce_invocation_recovery(
        run_root_c, invocation, content_attempt_limit=2
    )
    assert recovery.state == "send_outcome_unknown"
    assert recovery.accepted is False
    assert recovery.unknown_reservation_attempts == (1,)
    assert "reconcile_if_the_provider_supports_it" in recovery.allowed_actions
    assert "release_the_reservation" not in recovery.allowed_actions
    assert {"assume_not_sent", "silently_retry"} <= set(recovery.forbidden_actions)
    # 结论：恢复入口必须同时消费归约结论；只凭前置检查放行会变成"缺回执=未调用=可重发"。
