"""WP5：拒发/重试/恢复账本（方案 §9.2、§9.3）。

用事故归档的真实回执冻结"事件序号 ≠ 真实发送次数"，并验证恢复前置检查能给出
根因链而不是等到末尾报 acceptance_count:0。
"""

from __future__ import annotations

import json

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
