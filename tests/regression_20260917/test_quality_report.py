"""§14.3：质量报告只报可机械复算的维度，其余显式标"未测量"。

冻结 oracle = 事故归档（`artifacts/runs/2026-09-17-ebcar-intent-v4-p7-j9L1bn`）。
报告不得写入归档、不得调用模型、不得为不可测维度编造分数。
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.authoring_quality_report import build_authoring_quality_report

from . import incident_archive


def _report():
    return build_authoring_quality_report(incident_archive.archive_root())


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def test_efficiency_uses_ledger_acceptance_not_response_delivery() -> None:
    """回执 delivery_status=accepted 只表示"响应交付"；接受必须看账本。"""

    dimension = _report().dimension("efficiency")
    assert dimension is not None and dimension.status == "measured"
    metrics = dimension.metrics

    assert metrics["invocations"] == 40
    assert metrics["provider_sends"] == 45
    assert metrics["rejected_before_send_events"] == 2
    assert metrics["invocations_accepted"] == 19, "19/20 页被接受（事故事实）"
    assert metrics["invocations_accepted_without_repair"] == 16
    assert metrics["invocations_needing_repair"] == 5
    assert metrics["repair_acceptance_rate"] == 0.6
    assert metrics["first_attempt_acceptance_rate"] == 0.4
    # 真实 tokens（冻结 oracle，与归档回执求和一致）
    assert metrics["input_tokens"] == 1164056
    assert metrics["output_tokens"] == 57144
    assert metrics["total_tokens"] == 1221200
    assert metrics["input_token_budget_utilization"] == 0.4393


def test_recovery_robustness_explains_the_blocked_page() -> None:
    dimension = _report().dimension("recovery_robustness")
    assert dimension is not None and dimension.status == "measured"
    metrics = dimension.metrics
    assert metrics["pages_total"] == 20
    assert metrics["pages_accepted"] == 19
    assert metrics["blocked_pages"] == 1
    assert metrics["exhausted_invocations"] == 1
    exhausted = metrics["exhausted_invocation_ids"][0]
    assert exhausted.endswith("751aa8b5352377a0766e7f7416c05553647380df74d5295f04d695646a47b815")
    assert metrics["exhausted_invocation_failure_codes"][exhausted] == [
        "detail_witness_missing",
        "detail_semantic_mismatch",
    ]


def test_intent_coverage_matches_the_frozen_artifact() -> None:
    root = incident_archive.archive_root()
    coverage = json.loads(
        (root / "artifacts" / "obligation_coverage_v2.json").read_text(encoding="utf-8")
    )
    dimension = _report().dimension("intent_coverage")
    assert dimension is not None and dimension.status == "measured"
    metrics = dimension.metrics
    assert metrics["must_cover_obligations"] == coverage["must_cover_count"] == 6
    assert metrics["supported_must_cover"] == coverage["supported_must_cover_count"] == 4
    assert metrics["unresolved_must_cover"] == len(coverage["unresolved_must_cover_ids"])
    assert metrics["supported_must_cover_ratio"] == 0.6667
    assert dimension.proxies["paragraphs_without_per_paragraph_material"] == 27


def test_information_utilization_reports_unconsumed_formulas() -> None:
    dimension = _report().dimension("information_utilization")
    assert dimension is not None and dimension.status == "partial"
    metrics = dimension.metrics
    assert metrics["formula.required"] == 7, "该页 7 个 allowed detail"
    assert metrics["formula.consumed"] == 0, "0 detail witness 被消费"
    assert metrics["consumer_receipts"] == 45
    assert metrics["consumer_invocation_acceptance_rate"] == 0.475


def test_unmeasurable_dimensions_are_not_scored() -> None:
    report = _report()
    faithfulness = report.dimension("faithfulness")
    assert faithfulness is not None
    assert faithfulness.status == "not_measured"
    assert faithfulness.metrics == {}
    assert "语义判断者" in faithfulness.not_measured_reason
    assert "faithfulness" in report.unmeasured_dimensions

    narrative = report.dimension("narrative_quality")
    assert narrative is not None and narrative.status == "partial"
    assert narrative.metrics == {}, "叙事质量不得给出分数"
    assert narrative.proxies["paragraphs_without_per_paragraph_material"] == 27

    assert report.comparison_status == "not_available"
    assert "不伪造旧完整输出" in report.comparison_note


def test_report_is_read_only_and_deterministic() -> None:
    root = incident_archive.archive_root()
    before = _snapshot(root)
    first = _report()
    second = _report()
    after = _snapshot(root)

    assert before == after, "质量报告不得改写冻结归档"
    assert first.content_digest == second.content_digest
    assert first.content_digest.startswith("sha256:")


def test_quality_report_cli_renders_and_emits_json(capsys) -> None:
    from code2paper.cli.agentic_run import method_agent_main, supervised_method_agent_main

    root = str(incident_archive.archive_root())
    assert method_agent_main(["quality-report", "--out", root]) == 0
    rendered = capsys.readouterr().out
    assert "UNMEASURED" in rendered and "faithfulness" in rendered
    assert "provider_sends = 45" in rendered

    assert method_agent_main(["quality-report", "--out", root, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    efficiency = next(item for item in payload["dimensions"] if item["dimension"] == "efficiency")
    assert efficiency["metrics"]["provider_sends"] == 45

    # 只读命令不得被包进 worker 监督进程。
    assert supervised_method_agent_main(["quality-report", "--out", root]) == 0
    assert "AUTHORING QUALITY" in capsys.readouterr().out


def _write_receipt(
    ledger: Path,
    invocation: str,
    attempt: int,
    *,
    task_status: str = "complete",
    usage: dict[str, int] | None = None,
    content_accepted: bool | None = None,
) -> Path:
    """写一份通过校验的 invocation 回执（用模型构造，避免手工字段漂移）。

    ``content_accepted`` 会额外写内容验收记录：账本的 accepted 只认这份记录
    （传输层 delivery_status=accepted 表示"响应已交付"，不等于内容被接受）。
    """

    from code2paper.agentic.unified_context_models import ActualRequestReceiptV2

    directory = ledger / invocation
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
        task_status=task_status,
        succeeded_task_ids=("task-1",) if task_status == "complete" else (),
        sent_to_caller=True,
        provider_usage=dict(usage or {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}),
        upstream_archive_digest="sha256:" + "3" * 64,
        upstream_workset_manifest_digest="sha256:" + "4" * 64,
        upstream_plan_digest="sha256:" + "5" * 64,
    )
    path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if content_accepted is not None:
        (directory / f"attempt-{attempt:04d}.content-acceptance.json").write_text(
            json.dumps({"accepted": bool(content_accepted)}) + "\n", encoding="utf-8"
        )
    return path


def test_prepared_root_copied_receipts_are_not_reported_as_this_runs_efficiency(
    tmp_path: Path,
) -> None:
    """复制自冻结根的回执不得计入本次 run 的发送数/接受率（§14.3 效率口径）。"""

    from code2paper.agentic.reused_evidence_index import write_reused_evidence_index

    root = tmp_path / "prepare-root"
    ledger = root / "artifacts" / "06_authoring" / "invocations"
    _write_receipt(ledger, "inv-copied", 1, task_status="partial")
    _write_receipt(ledger, "inv-copied", 2, task_status="partial")
    _write_receipt(ledger, "inv-fresh", 1, task_status="complete", content_accepted=True)
    write_reused_evidence_index(
        root=root,
        frozen_root=tmp_path / "frozen",
        ledger_dir=ledger,
        relative_paths=(
            "inv-copied/attempt-0001.completed.json",
            "inv-copied/attempt-0002.completed.json",
        ),
    )

    report = build_authoring_quality_report(root)
    efficiency = report.dimension("efficiency")
    assert efficiency is not None
    assert efficiency.metrics["invocations"] == 1, "复用 invocation 不计入本次 run"
    assert efficiency.metrics["provider_sends"] == 1
    assert efficiency.metrics["invocations_accepted"] == 1
    assert efficiency.metrics["first_attempt_acceptance_rate"] == 1.0
    assert efficiency.metrics["reused_evidence_invocations"] == 1
    assert efficiency.metrics["reused_evidence_receipts"] == 2
    # 复用部分不得被静默丢掉
    assert efficiency.metrics["invocations"] + efficiency.metrics["reused_evidence_invocations"] == 2
