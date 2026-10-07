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
    SEND_OUTCOME_UNKNOWN,
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
# --------------------------------------------------------------------------- #
# K04-GAP-1 / GAP-3：同一组**真实失败产物**经过账本计数、缓存选择与恢复入口
# --------------------------------------------------------------------------- #
#
# 本组不手写账本字段：四个 node 的持久字节全部由生产 owner 写出——
#   (a) rejected + 空实测摘要：真实 Writer caller 在 repair 上因材料不可重算被拒发
#       （started + completed(rejected, sent_to_caller=False, actual="")，**无 provider-request**）；
#   (b) 请求未构造/no-send 无回执：严格 unified 下缺 V2 页元数据，上游具名阻断，
#       writer invocation 连目录都没有（失败事实落在产品结果里，不在账本里）；
#   (c) 已发送但结果不确定：真实子进程在 provider 边界 os._exit(9)（child rc=9），
#       留下 started + provider-request 而没有 completed；
#   (d) 已接受且摘要匹配的合法缓存对照：真实合法运行的接受回执 + 验收。
#
# GAP-1 与 GAP-3 复用**同一组**产物、同一套消费者（第二次调用只复读报告，不重造账本）。


def _writer_invocation_and_dir(run_root: Path) -> tuple[str, Path | None]:
    """从真实 started 标记里发现 writer invocation 与它的账本目录。"""

    ledger = run_root / "artifacts" / "06_authoring" / "invocations"
    if not ledger.is_dir():
        return "", None
    for directory in sorted(path for path in ledger.iterdir() if path.is_dir()):
        if not directory.name.startswith("inv-writer-"):
            continue
        for path in sorted(directory.glob("attempt-*.started.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            invocation_id = str(payload.get("invocation_id") or "")
            if invocation_id:
                return invocation_id, directory
    return "", None


def _crash_run(root: Path) -> int:
    """真实崩溃：provider 边界处 os._exit(9)，留下 started + provider-request。"""

    import subprocess
    import sys
    import textwrap

    repo_root = Path(__file__).resolve().parents[2]
    child = textwrap.dedent(
        f"""
        import os, sys
        from pathlib import Path
        sys.path.insert(0, {str(repo_root / 'src')!r})
        sys.path.insert(0, {str(repo_root)!r})
        from tests.test_agentic_publication_method_writer_unified import (
            _unified_artifacts, _config, _mock_writer_caller,
        )
        from code2paper.agentic.publication_method_writer import run_publication_method_writer

        root = Path(sys.argv[1])
        paths = _unified_artifacts(root)

        def caller(config, request):
            if getattr(request, "prompt_template_id", "") == "unified_writer_page_v2":
                os._exit(9)
            return _mock_writer_caller(config, request)

        run_publication_method_writer(
            out_root=root, artifact_paths=paths, llm_config=_config(),
            llm_caller=caller, authoring_context_mode="unified",
        )
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", child, str(root)],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return int(completed.returncode)


def gap13_drop_material():
    """(a) 的实际侧单变量：材料不可重算（与 K04-G2-1 同一变异）。"""

    def _drop(payload, _boundary) -> None:
        payload["shared_contexts"] = []

    return _drop


def _gap13_generate(root: Path) -> dict[str, object]:
    import os  # noqa: F401  (保持与生产一致的环境清理路径)

    from code2paper.agentic import publication_method_writer as pmw
    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )
    from code2paper.llm import section_writer as sw
    from tests.regression_20260922 import test_authoring_contract_closure as closure
    from tests.test_agentic_publication_method_writer_unified import (
        _clear_unified_budget_env,
        _config,
        _mock_writer_caller,
        _unified_artifacts,
    )

    def _run(run_root: Path, caller):
        run_root.mkdir(parents=True, exist_ok=True)
        result, _outputs = run_publication_method_writer(
            out_root=run_root,
            artifact_paths=_unified_artifacts(run_root),
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
        return result

    # (a) rejected + 空实测摘要（只变异 repair 请求的材料可重算性）
    root_a = root / "a"
    with pytest.MonkeyPatch.context() as patch:
        closure._run_g2_case(root_a, patch, gap13_drop_material())
    _clear_unified_budget_env()

    # (b) 请求未构造：严格 unified 下缺 V2 页元数据 → 上游具名阻断、零回执
    root_b = root / "b"
    root_b.mkdir(parents=True, exist_ok=True)
    real_request = pmw.LLMRequest

    def _stripping_request(**kwargs):
        payload = kwargs.get("input_payload")
        if isinstance(payload, dict) and "shared_context_metadata" in payload:
            kwargs["input_payload"] = {
                key: value
                for key, value in payload.items()
                if key != "shared_context_metadata"
            }
        return real_request(**kwargs)

    caller_calls_b: list = []

    def caller_b(config, request):
        caller_calls_b.append(request)
        return _mock_writer_caller(config, request)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pmw, "LLMRequest", _stripping_request)
        patch.setattr(sw, "LLMRequest", _stripping_request)
        result_b = _run(
            root_b,
            caller_b,
        )
    _clear_unified_budget_env()

    # (c) 已发送但结果不确定：真实子进程崩溃
    root_c = root / "c"
    root_c.mkdir(parents=True, exist_ok=True)
    crash_returncode = _crash_run(root_c)
    _clear_unified_budget_env()

    # (d) 合法接受对照：无变异的一轮（primary 直接通过内容验收）
    root_d = root / "d"
    calls_d: list = []

    def caller_d(config, request):
        calls_d.append(request)
        return _mock_writer_caller(config, request)

    result_d = _run(root_d, caller_d)
    _clear_unified_budget_env()

    invocation, writer_dir_a = _writer_invocation_and_dir(root_a)
    invocation_b, writer_dir_b = _writer_invocation_and_dir(root_b)
    invocation_c, writer_dir_c = _writer_invocation_and_dir(root_c)
    invocation_d, writer_dir_d = _writer_invocation_and_dir(root_d)
    assert invocation, "node (a) 必须留下 writer 账本"
    assert invocation == invocation_d, "同一夹具的 writer invocation 必须一致"
    assert invocation_b == "", "node (b) 不得留下 writer 账本（无回执）"
    assert invocation_c == invocation, "node (c) 的崩溃发生在同一 writer invocation"
    return {
        "schema_version": "k04-gap13-artifacts/1",
        "root": str(root),
        "invocation": invocation,
        "a": {"run_root": str(root_a), "writer_dir": str(writer_dir_a)},
        "b": {
            "run_root": str(root_b),
            "writer_dir": "",
            "result_status": str(getattr(result_b, "status", "")),
            "result_reason": str(getattr(result_b, "blocked_reason", "")),
            "caller_call_count": len(caller_calls_b),
        },
        "c": {
            "run_root": str(root_c),
            "writer_dir": str(writer_dir_c),
            "crash_returncode": crash_returncode,
        },
        "d": {
            "run_root": str(root_d),
            "writer_dir": str(writer_dir_d),
            "result_status": str(getattr(result_d, "status", "")),
        },
    }


def _gap13_from_report(report: dict) -> dict[str, object]:
    result: dict[str, object] = {
        key: value for key, value in report.items() if key not in {"a", "b", "c", "d"}
    }
    result["root"] = Path(str(report["root"]))
    for node in ("a", "b", "c", "d"):
        row = dict(report[node])
        row["run_root"] = Path(str(row["run_root"]))
        row["writer_dir"] = Path(row["writer_dir"]) if row.get("writer_dir") else None
        result[node] = row
    return result


def build_gap13_artifact_runs(root: Path) -> dict[str, object]:
    """真实 owner 生成 GAP-1/3 的**同一组**持久产物（同一 root 只生成一次）。"""

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "gap13_artifacts.json"
    if marker.is_file():
        return _gap13_from_report(json.loads(marker.read_text(encoding="utf-8")))
    report = _gap13_generate(root)
    marker.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _gap13_from_report(report)


@pytest.fixture(scope="module")
def gap13(tmp_path_factory) -> dict[str, object]:
    """会话级共享：两份账本测试读同一组产物与同一份报告。"""

    return build_gap13_artifact_runs(tmp_path_factory.getbasetemp() / "k04-gap13")


def _receipt(writer_dir: Path, attempt: int) -> dict:
    return json.loads(
        (writer_dir / f"attempt-{attempt:04d}.completed.json").read_text(encoding="utf-8")
    )


def _acceptance(writer_dir: Path, attempt: int) -> dict:
    return json.loads(
        (writer_dir / f"attempt-{attempt:04d}.content-acceptance.json").read_text(
            encoding="utf-8"
        )
    )


def test_gap1_rejected_empty_measured_digest_is_not_accepted_or_reusable(gap13) -> None:
    """GAP-1：真实 rejected + 空实测摘要回执经计数/缓存/恢复，读出的结论都不是"接受"。

    attempt-0002 的 completed 由生产 owner 写出（rejected、sent_to_caller=False、
    actual_technical_bytes_digest 为空、provider_usage=None），且**没有 provider-request 文件**：
    拒绝发生在越过 caller 边界之前。
    """

    run_root = gap13["a"]["run_root"]
    writer_dir = gap13["a"]["writer_dir"]
    invocation = gap13["invocation"]
    assert writer_dir is not None

    rejected = _receipt(writer_dir, 2)
    assert rejected["delivery_status"] == "rejected"
    assert rejected["sent_to_caller"] is False
    assert rejected["actual_technical_bytes_digest"] == ""
    assert rejected["provider_usage"] is None
    assert not (writer_dir / "attempt-0002.provider-request.json").exists(), (
        "被拒发的 repair 不得留下 provider-request（零发送的持久证据）"
    )
    assert str(rejected["delivery_rejection_code"]).startswith(
        "unified_actual_page_bytes_mismatch:"
    )

    state = read_invocation_ledger_state(run_root, invocation, content_attempt_limit=2)
    # 只有 attempt-0001 是真的内容尝试；被拒 repair 不计发送、不计内容尝试。
    assert state.counters.provider_send_count == 1
    assert state.counters.content_attempt_count == 1
    assert state.content_attempts_remaining == 1
    assert state.accepted is False
    assert state.primary_accepted is False
    assert state.exhausted is False

    outcomes = {item.attempt: item for item in read_attempt_outcomes(run_root, invocation)}
    assert outcomes[2].reservation_retained is False
    assert outcomes[2].acceptance_replayable is False
    assert outcomes[1].reservation_retained is False

    recovery = reduce_invocation_recovery(run_root, invocation, content_attempt_limit=2)
    assert recovery.accepted is False
    assert recovery.primary_accepted is False
    assert recovery.unknown_reservation_attempts == ()
    assert recovery.blocks == ()
    assert "count_it_as_a_content_failure" in recovery.forbidden_actions
    assert unsettled_reservations(run_root, invocation) == ()

    # K04 收口后的分类与计数：真实合同拒发（不认前缀）必须被具名分类、计数并带出它的
    # rejection code，而不是记成 settled / 空计数器 / "no_events"。
    assert state.counters.rejected_before_send_events == (2,)
    assert outcomes[2].state == "rejected_before_send"
    assert "unified_actual_page_bytes_mismatch" in outcomes[2].detail
    assert recovery.last_rejection_code.startswith(
        "unified_actual_page_bytes_mismatch:"
    )
    # 状态仍是"可继续"（有剩余内容预算），但原因必须点名发送前拒绝。
    assert recovery.state == "reserved_not_sent"
    assert recovery.primary_cause == "presend_refusal_without_send"
    assert "release_the_reservation" in recovery.allowed_actions

    preflight = build_resume_preflight(run_root, [invocation], execution_id="gap1-a")
    assert preflight.allowed is True, "未耗尽 → 允许重新准入，且拒发不消耗内容尝试"


def test_gap3_no_receipt_attempt_is_not_a_completion_and_failure_stays_audited(
    gap13,
) -> None:
    """GAP-3：请求未构造/no-send 无回执时，账本无记录但失败事实不得消失成"成功"。"""

    run_root = gap13["b"]["run_root"]
    invocation = gap13["invocation"]
    assert gap13["b"]["writer_dir"] is None

    state = read_invocation_ledger_state(run_root, invocation, content_attempt_limit=2)
    assert state.counters.event_seq == 0
    assert state.counters.provider_send_count == 0
    assert state.counters.content_attempt_count == 0
    assert state.accepted is False
    assert state.exhausted is False
    assert read_attempt_outcomes(run_root, invocation) == ()
    assert unsettled_reservations(run_root, invocation) == ()

    recovery = reduce_invocation_recovery(run_root, invocation, content_attempt_limit=2)
    assert recovery.accepted is False
    assert recovery.unknown_reservation_attempts == ()
    assert recovery.blocks == ()

    # 缺回执 ≠ 成功：产品结果必须具名阻断，且这不是"预算耗尽"。
    assert gap13["b"]["result_status"] == "blocked"
    reason = str(gap13["b"]["result_reason"])
    assert "unified_unplanned_actual_request" in reason, reason
    preflight = build_resume_preflight(run_root, [invocation], execution_id="gap3-b")
    assert preflight.allowed is True


def test_gap3_unknown_send_keeps_reservation_and_blocks_a_blind_resend(gap13) -> None:
    """GAP-3：真实崩溃只留下 started+provider-request → 保留预留、禁止盲重发。"""

    from code2paper.agentic.unified_invocation_ledger import (
        unsettled_started_attempt_records,
    )

    run_root = gap13["c"]["run_root"]
    writer_dir = gap13["c"]["writer_dir"]
    invocation = gap13["invocation"]
    assert gap13["c"]["crash_returncode"] == 9, "必须是真实子进程崩溃（os._exit(9)）"
    assert writer_dir is not None
    files = sorted(path.name for path in writer_dir.iterdir())
    assert files == [
        "attempt-0001.provider-request.json",
        "attempt-0001.started.json",
    ], files

    outcomes = read_attempt_outcomes(run_root, invocation)
    assert [(item.attempt, item.state) for item in outcomes] == [
        (1, SEND_OUTCOME_UNKNOWN)
    ]
    assert outcomes[0].reservation_retained is True
    assert outcomes[0].acceptance_replayable is False
    assert [item.attempt for item in unsettled_reservations(run_root, invocation)] == [1]

    recovery = reduce_invocation_recovery(run_root, invocation, content_attempt_limit=2)
    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.unknown_reservation_attempts == (1,)
    assert recovery.accepted is False
    assert {"assume_not_sent", "silently_retry"} <= set(recovery.forbidden_actions)

    # 预算视角必须保留这次未知发送的真实预留，而不是"缺 usage 就记 0 成本"。
    class _Invocation:
        def __init__(self, invocation_id: str) -> None:
            self.invocation_id = invocation_id
            self.max_input_tokens = 0
            self.role = "writer"

    class _Plan:
        def __init__(self, invocation_id: str) -> None:
            self.invocations = (_Invocation(invocation_id),)

    records = unsettled_started_attempt_records(
        run_root / "artifacts" / "06_authoring" / "invocations", _Plan(invocation)
    )
    assert [item.attempt for item in records] == [1]
    assert records[0].planned_input_tokens > 0, records
    assert records[0].plan_source == "recorded_plan", records

    # 真实入口重跑同一 root：必须拒发（零新增 provider 到达），不得盲重发。
    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )
    from tests.test_agentic_publication_method_writer_unified import (
        _clear_unified_budget_env,
        _config,
        _mock_writer_caller,
        _unified_artifacts,
    )

    arrivals: list = []

    def caller(config, request):
        if getattr(request, "prompt_template_id", "") == "unified_writer_page_v2":
            arrivals.append(request)
        return _mock_writer_caller(config, request)

    raised = ""
    try:
        rerun, _outputs = run_publication_method_writer(
            out_root=run_root,
            artifact_paths=_unified_artifacts(run_root),
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
        rerun_status = str(getattr(rerun, "status", ""))
        rerun_reason = str(getattr(rerun, "blocked_reason", ""))
    except ValueError as exc:
        raised = str(exc)
        rerun_status, rerun_reason = "", ""
    finally:
        _clear_unified_budget_env()

    assert arrivals == [], "发送结果未知的 attempt 不得盲重发"
    # K04 收口后：整轮必须在相位边界报告**原始**阻断原因，而不是让 realizer 的预算错误
    # （"预算被保留的未知发送压成负数"）把 writer 根因掩盖掉。
    assert raised == "", f"未知发送必须在相位边界 blocked，而不是抛下游错误：{raised}"
    assert rerun_status == "blocked", (rerun_status, rerun_reason)
    assert rerun_reason.startswith("writer_phase_boundary_blocked:"), rerun_reason
    assert "primary_cause=send_outcome_unknown" in rerun_reason, rerun_reason
    assert f"invocation={invocation}" in rerun_reason, rerun_reason
    assert "unknown_reservations=[1]" in rerun_reason, rerun_reason
    assert "downstream_not_run=realizer" in rerun_reason, rerun_reason
    assert "unified_consumer_request_rejected:realizer" not in rerun_reason, rerun_reason


def test_gap1_accepted_receipt_is_reused_from_cache_without_resending(gap13) -> None:
    """GAP-1 合法对照：接受回执可重用；重跑零重发、不重封。"""

    run_root = gap13["d"]["run_root"]
    writer_dir = gap13["d"]["writer_dir"]
    invocation = gap13["invocation"]
    assert writer_dir is not None

    accepted = _receipt(writer_dir, 1)
    assert accepted["delivery_status"] == "accepted"
    assert accepted["sent_to_caller"] is True
    assert accepted["actual_technical_bytes_digest"] != ""
    assert accepted["content_repair_attempt"] is False
    sidecar = _acceptance(writer_dir, 1)
    assert sidecar["accepted"] is True

    state = read_invocation_ledger_state(run_root, invocation, content_attempt_limit=2)
    assert state.accepted is True and state.primary_accepted is True
    recovery = reduce_invocation_recovery(
        run_root,
        invocation,
        content_attempt_limit=2,
        contract_digests={"plan_digest": str(sidecar["plan_digest"])},
    )
    assert recovery.state == "accepted_reusable"
    assert recovery.accepted is True
    assert recovery.contract_mismatch == ()

    before_digest = accepted["content_digest"]
    before_files = sorted(path.name for path in writer_dir.iterdir())

    from code2paper.agentic.publication_method_writer import (
        run_publication_method_writer,
    )
    from tests.test_agentic_publication_method_writer_unified import (
        _clear_unified_budget_env,
        _config,
        _mock_writer_caller,
        _unified_artifacts,
    )

    arrivals: list = []

    def caller(config, request):
        if getattr(request, "prompt_template_id", "") == "unified_writer_page_v2":
            arrivals.append(request)
        return _mock_writer_caller(config, request)

    try:
        run_publication_method_writer(
            out_root=run_root,
            artifact_paths=_unified_artifacts(run_root),
            llm_config=_config(),
            llm_caller=caller,
            authoring_context_mode="unified",
        )
    finally:
        _clear_unified_budget_env()

    assert arrivals == [], "合法缓存复用不得重发 provider 请求"
    after = _receipt(writer_dir, 1)
    assert after["content_digest"] == before_digest, "接受回执不得被重新封印"
    assert _acceptance(writer_dir, 1)["accepted"] is True
    # 复用不得产生新的**接受**记录；新增文件只能是 pre-send 拒绝（无 provider-request）。
    new = sorted(set(path.name for path in writer_dir.iterdir()) - set(before_files))
    assert all("provider-request" not in name for name in new), new
    for name in new:
        if name.endswith(".completed.json"):
            row = json.loads((writer_dir / name).read_text(encoding="utf-8"))
            assert row["delivery_status"] == "rejected"
            assert row["sent_to_caller"] is False


def test_unsent_receipt_with_request_evidence_is_not_releasable(tmp_path: Path) -> None:
    """回执声称未发送，但 request 已落盘：不能变成 no_events 或可释放未发。"""

    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"wire": "present"})
    _write(
        directory,
        1,
        "completed",
        _completed_payload(sent=False, code="page_bytes_mismatch"),
    )
    recovery = _reduce(tmp_path)

    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.primary_cause == "send_claim_conflicts_with_persistent_evidence"
    assert recovery.primary_cause != "no_events"
    assert recovery.counters.provider_send_count == 0
    assert recovery.counters.content_attempt_count == 0
    assert recovery.counters.rejected_before_send_events == ()
    assert recovery.unknown_reservation_attempts == (1,)
    assert "release_the_reservation" not in recovery.allowed_actions
    assert {"assume_not_sent", "silently_retry"} <= set(recovery.forbidden_actions)
    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    assert outcomes[0].state == SEND_OUTCOME_UNKNOWN
    assert outcomes[0].reservation_retained is True


def test_unsent_receipt_with_response_evidence_is_not_accepted(tmp_path: Path) -> None:
    """response 与未发送回执冲突时，不得结算成可复用，也不得记成发送成功。"""

    directory = _ledger(tmp_path)
    _write(directory, 1, "request", {"wire": "present"})
    _write(directory, 1, "response", {"text": "model output"})
    _write(directory, 1, "completed", _completed_payload(sent=False, code="page_bytes_mismatch"))
    _write(directory, 1, "acceptance", {"accepted": True})
    recovery = _reduce(tmp_path)

    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.primary_cause == "send_claim_conflicts_with_persistent_evidence"
    assert recovery.accepted is False
    assert recovery.counters.provider_send_count == 0
    assert "release_the_reservation" not in recovery.allowed_actions
    assert "reuse_the_accepted_version" not in recovery.allowed_actions


def test_unsent_receipt_with_damaged_request_is_ledger_corrupt(tmp_path: Path) -> None:
    """相关证据损坏时不能当成明确未发，也不退款。"""

    directory = _ledger(tmp_path)
    request = _write(directory, 1, "request", {"wire": "present"})
    request.write_text("{broken", encoding="utf-8")
    _write(directory, 1, "completed", _completed_payload(sent=False, code="page_bytes_mismatch"))
    recovery = _reduce(tmp_path)

    assert recovery.state == "ledger_corrupt"
    assert recovery.primary_cause.startswith("ledger_corrupt:")
    assert recovery.primary_cause != "no_events"
    assert recovery.counters.provider_send_count == 0
    assert recovery.counters.rejected_before_send_events == ()
    assert "release_the_reservation" not in recovery.allowed_actions
    assert "ignore_the_file_and_take_a_fresh_budget" in recovery.forbidden_actions
    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    assert outcomes[0].reservation_retained is True
    assert outcomes[0].state != "rejected_before_send"


def test_named_no_send_unknown_and_budget_exhaustion_stay_distinct(tmp_path: Path) -> None:
    """合法未发、未知发送、预算耗尽不被冲突分类改名。"""

    no_send = tmp_path / "no-send"
    directory = _ledger(no_send)
    _write(directory, 1, "completed", _completed_payload(sent=False, code="page_bytes_mismatch"))
    recovery = _reduce(no_send)
    assert recovery.state == "reserved_not_sent"
    assert recovery.primary_cause == "presend_refusal_without_send"
    assert "release_the_reservation" in recovery.allowed_actions

    unknown = tmp_path / "unknown"
    directory = _ledger(unknown)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"wire": "present"})
    recovery = _reduce(unknown)
    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.primary_cause == "request_persisted_without_completed"
    assert "assume_not_sent" in recovery.forbidden_actions

    exhausted = tmp_path / "budget"
    directory = _ledger(exhausted)
    for attempt in (1, 2):
        _write(directory, attempt, "request", {"wire": "sent"})
        _write(directory, attempt, "response", {"text": "body"})
        _write(directory, attempt, "completed", _completed_payload())
        _write(
            directory,
            attempt,
            "acceptance",
            {"accepted": False, "failures": ["missing_paragraph:P2"]},
        )
    recovery = _reduce(exhausted, content_attempt_limit=2)
    assert recovery.state == "content_budget_exhausted"
    assert recovery.primary_cause.startswith("content_attempts_exhausted:")
    assert "send_claim_conflicts" not in recovery.primary_cause
    assert recovery.state != SEND_OUTCOME_UNKNOWN


def _conflict_ledger(tmp_path: Path) -> Path:
    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"wire": "present"})
    _write(directory, 1, "response", {"text": "model output"})
    _write(
        directory,
        1,
        "completed",
        _completed_payload(sent=False, code="page_bytes_mismatch"),
    )
    return directory


def test_matching_replay_cannot_cover_a_conflicting_send(tmp_path: Path) -> None:
    """冲突已经落盘后，同 validator 的接受重放不能把它变成可复用。"""

    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    directory = _conflict_ledger(tmp_path)
    before = _reduce(tmp_path)
    assert before.state == SEND_OUTCOME_UNKNOWN
    assert before.accepted is False
    with pytest.raises(ValueError, match="validation_replay_refuses_conflicting_send_evidence"):
        publish_validation_replay(
            tmp_path,
            INVOCATION,
            attempt=1,
            accepted=True,
            validator_bundle_digest="sha256:validator-current",
            source_response_digest="sha256:resp",
        )
    recovery = _reduce(tmp_path, contract_digests={
        "validator_bundle_digest": "sha256:validator-current",
    })
    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    ledger = read_invocation_ledger_state(tmp_path, INVOCATION)
    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.primary_cause == "send_claim_conflicts_with_persistent_evidence"
    assert recovery.accepted is False
    assert recovery.unknown_reservation_attempts == (1,)
    assert recovery.counters.provider_send_count == 0
    assert ledger.accepted is False
    assert outcomes[0].state == SEND_OUTCOME_UNKNOWN
    assert outcomes[0].reservation_retained is True
    assert not any(directory.glob("attempt-*.validation-replay.*.json"))


def test_replay_recorded_before_a_contradictory_receipt_stays_unknown(
    tmp_path: Path,
) -> None:
    """合法重放先落盘，之后 completed 变成矛盾未发送：重放不再覆盖冲突。"""

    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    _write(directory, 1, "request", {"wire": "present"})
    _write(directory, 1, "response", {"text": "model output"})
    completed = _write(directory, 1, "completed", _completed_payload())
    publish_validation_replay(
        tmp_path,
        INVOCATION,
        attempt=1,
        accepted=True,
        validator_bundle_digest="sha256:validator-current",
        source_response_digest="sha256:resp",
    )
    assert _reduce(tmp_path, contract_digests={
        "validator_bundle_digest": "sha256:validator-current",
    }).state == "accepted_reusable"
    completed.write_text(
        json.dumps({
            "attempt": 1,
            "invocation_id": INVOCATION,
            **_completed_payload(sent=False, code="page_bytes_mismatch"),
        }) + "\n",
        encoding="utf-8",
    )
    recovery = _reduce(tmp_path, contract_digests={
        "validator_bundle_digest": "sha256:validator-current",
    })
    outcomes = read_attempt_outcomes(tmp_path, INVOCATION)
    assert recovery.state == SEND_OUTCOME_UNKNOWN
    assert recovery.primary_cause == "send_claim_conflicts_with_persistent_evidence"
    assert recovery.accepted is False
    assert recovery.unknown_reservation_attempts == (1,)
    assert recovery.counters.provider_send_count == 0
    assert "reuse_the_accepted_version" not in recovery.allowed_actions
    assert outcomes[0].reservation_retained is True
    assert read_invocation_ledger_state(tmp_path, INVOCATION).accepted is False


def test_replay_cannot_mark_a_damaged_ledger_accepted(tmp_path: Path) -> None:
    """损坏 request 上的接受重放不能让 ledger_corrupt 带着 accepted=true。"""

    from code2paper.agentic.writer_attempt_ledger import publish_validation_replay

    directory = _ledger(tmp_path)
    _write(directory, 1, "started")
    request = _write(directory, 1, "request", {"wire": "present"})
    _write(directory, 1, "response", {"text": "model output"})
    _write(directory, 1, "completed", _completed_payload())
    publish_validation_replay(
        tmp_path,
        INVOCATION,
        attempt=1,
        accepted=True,
        validator_bundle_digest="sha256:validator-current",
    )
    request.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="validation_replay_refuses_damaged_ledger"):
        publish_validation_replay(
            tmp_path,
            INVOCATION,
            attempt=1,
            accepted=True,
            validator_bundle_digest="sha256:validator-other",
        )
    recovery = _reduce(tmp_path, contract_digests={
        "validator_bundle_digest": "sha256:validator-current",
    })
    assert recovery.state == "ledger_corrupt"
    assert recovery.accepted is False
    assert recovery.primary_accepted is False
    assert read_invocation_ledger_state(tmp_path, INVOCATION).accepted is False
    assert read_attempt_outcomes(tmp_path, INVOCATION)[0].reservation_retained is True
