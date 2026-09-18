"""§14.3：token 用量必须区分"本次发送"与"复用的冻结证据"。

实测缺陷：`--authoring-stage prepare` 会把冻结 Formalizer 阶段的 invocation 回执复制进
fresh 根，随后 token 汇总把这 45 次历史调用（1.16M input tokens）记成**本次 run 的**
用量——同一轮 `deterministic_preflight_v1.json` 却是 `model_calls: 0`。
这既是效率口径失真，也让"这次尝试有没有真的发过请求"这条判断（准备根续跑分支依赖
`calls == 0 and total_tokens == 0`）永远不成立。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_authoring_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("run_authoring_replay", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _call(role: str, usage: dict[str, int], *, reused: bool = False) -> dict[str, object]:
    return {
        "role": role,
        "token_usage": usage,
        "model": "sha256:model",
        "reused_evidence": reused,
        "blocked_reason": "",
    }


def test_summary_splits_sent_from_reused_evidence() -> None:
    module = _load_script()
    summary = module._summarize_token_usage(
        [
            _call("writer", {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}),
            _call("realizer", {"prompt_tokens": 900, "completion_tokens": 80, "total_tokens": 980}, reused=True),
            _call("realizer", {"prompt_tokens": 90, "completion_tokens": 8, "total_tokens": 98}, reused=True),
        ]
    )

    # 顶层 = 本次发送
    assert summary["calls"] == 1
    assert summary["total_tokens"] == 120
    assert summary["input_tokens"] == 100
    assert summary["status"] == "complete"
    # 复用证据单独记账，且不丢失
    assert summary["reused_evidence"]["calls"] == 2
    assert summary["reused_evidence"]["total_tokens"] == 1078
    assert summary["reused_evidence"]["input_tokens"] == 990
    assert summary["all_receipts"] == {
        "calls": 3,
        "calls_with_usage": 3,
        "input_tokens": 1090,
        "output_tokens": 108,
        "total_tokens": 1198,
        "reasoning_tokens": 0,
    }
    assert summary["provenance"] == {
        "sent": 1,
        "reused_evidence": 2,
        "unclassified": 0,
    }


def test_only_reused_receipts_report_zero_sent_calls() -> None:
    """prepared 根的真实状态：本轮一次都没发，就必须报 calls=0。"""

    module = _load_script()
    summary = module._summarize_token_usage(
        [_call("realizer", {"total_tokens": 850}, reused=True)]
    )
    assert summary["calls"] == 0
    assert summary["total_tokens"] == 0
    assert summary["status"] == "no_calls"
    assert summary["all_receipts"]["total_tokens"] == 850


def test_usage_accounting_contract_is_unchanged_without_provenance() -> None:
    """没有来源标记时（既有调用方/测试）行为必须与旧实现一致。"""

    module = _load_script()
    summary = module._summarize_token_usage(
        [
            _call("writer", {"total_tokens": 11, "prompt_tokens": 7, "completion_tokens": 4}),
            _call("editor", {"prompt_tokens": 6, "completion_tokens": 2}),
            _call("planner", {}),
        ]
    )
    assert (summary["calls"], summary["calls_with_usage"]) == (3, 2)
    assert (summary["explicit_total_token_calls"], summary["estimated_total_token_calls"]) == (1, 1)
    assert summary["total_tokens"] == 19
    assert summary["reused_evidence"]["calls"] == 0


def _write_receipt(root: Path, invocation: str, attempt: int, usage: dict[str, int]) -> Path:
    """写出真实通过校验的 receipt（用模型本身构造，避免手工字段漂移）。"""

    from code2paper.agentic.unified_context_models import ActualRequestReceiptV2

    directory = root / invocation
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"attempt-{attempt:04d}.completed.json"
    receipt = ActualRequestReceiptV2(
        invocation_id=invocation.replace("-", ":", 1),
        attempt=attempt,
        consumer_role="realizer",
        phase="realizer",
        workset_id="workset-1",
        task_ids=("task-1",),
        mechanism_id="mechanism-1",
        page_id="page-1",
        actual_technical_bytes_digest="sha256:" + "1" * 64,
        actual_request_envelope_digest="sha256:" + "2" * 64,
        response_digest="sha256:" + "6" * 64,
        model_identity_digest="sha256:model",
        started_at_unix=1.0,
        finished_at_unix=2.0,
        delivery_status="accepted",
        task_status="complete",
        succeeded_task_ids=("task-1",),
        sent_to_caller=True,
        provider_usage=dict(usage),
        upstream_archive_digest="sha256:" + "3" * 64,
        upstream_workset_manifest_digest="sha256:" + "4" * 64,
        upstream_plan_digest="sha256:" + "5" * 64,
    )
    path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def test_write_summary_classifies_copied_receipts_by_provenance_index(tmp_path: Path) -> None:
    module = _load_script()
    fresh = tmp_path / "fresh"
    ledger = fresh / "artifacts" / "06_authoring" / "invocations"
    copied = _write_receipt(
        ledger, "inv-copied", 1, {"prompt_tokens": 800, "completion_tokens": 50, "total_tokens": 850}
    )
    module._write_reused_evidence_receipts_index(
        authoring=fresh / "artifacts" / "06_authoring",
        frozen=tmp_path / "frozen",
        receipts=("inv-copied/attempt-0001.completed.json",),
    )
    _write_receipt(
        ledger, "inv-fresh", 1, {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
    )

    result = module._write_token_usage_summary(fresh)

    assert result["calls"] == 1, "只有本次发送的调用计入顶层"
    assert result["total_tokens"] == 150
    assert result["reused_evidence"]["calls"] == 1
    assert result["reused_evidence"]["total_tokens"] == 850
    assert result["provenance"]["sent"] == 1
    assert result["provenance"]["reused_evidence"] == 1
    assert copied.is_file(), "分类不修改证据文件本身"

    written = json.loads(
        (fresh / "artifacts" / "06_authoring" / "token_usage_summary_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["reused_evidence"]["total_tokens"] == 850


def test_receipt_changed_after_copy_counts_as_sent_and_is_recorded(tmp_path: Path) -> None:
    """复制后被改写的回执不得被当成"免费"的复用证据。"""

    module = _load_script()
    fresh = tmp_path / "fresh"
    ledger = fresh / "artifacts" / "06_authoring" / "invocations"
    receipt = _write_receipt(
        ledger, "inv-tampered", 1, {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}
    )
    module._write_reused_evidence_receipts_index(
        authoring=fresh / "artifacts" / "06_authoring",
        frozen=tmp_path / "frozen",
        receipts=("inv-tampered/attempt-0001.completed.json",),
    )
    # 复制后被合法改写（新内容仍通过校验，但摘要与索引记录不一致）。
    _write_receipt(
        ledger, "inv-tampered", 1, {"prompt_tokens": 999, "completion_tokens": 1, "total_tokens": 1000}
    )

    result = module._write_token_usage_summary(fresh)

    assert result["calls"] == 1
    assert result["total_tokens"] == 1000
    assert result["reused_evidence"]["calls"] == 0
    assert result["provenance"]["content_changed_after_copy"] == 1
