"""§14.3：对照比较必须 fail-closed——冻结输入或模型身份不同就不给差值。

比较器**不产生综合评分**：只有极性明确的机械指标才给方向，其余只给原始 delta。
"""

from __future__ import annotations

import json
from pathlib import Path

from code2paper.agentic.authoring_quality_comparison import (
    METRIC_POLARITY,
    compare_authoring_quality_reports,
)
from code2paper.agentic.authoring_quality_report import build_authoring_quality_report

from . import incident_archive


def _report():
    return build_authoring_quality_report(incident_archive.archive_root())


def _with_anchors(report, **overrides):
    comparability = report.comparability.model_copy(update=overrides)
    return report.model_copy(update={"comparability": comparability})


def test_identical_runs_are_comparable_with_zero_deltas_and_no_score() -> None:
    report = _report()
    comparison = compare_authoring_quality_reports(report, report)

    assert comparison.comparable is True
    assert comparison.blockers == ()
    assert comparison.metric_deltas, "应当逐指标给出原始值"
    assert all(item.delta == 0.0 for item in comparison.metric_deltas)
    keys = {f"{item.dimension}.{item.metric}" for item in comparison.metric_deltas}
    assert "efficiency.provider_sends" in keys
    # 方向只对极性明确的指标给出；比较器不输出任何综合分数字段。
    unknown = {
        f"{item.dimension}.{item.metric}"
        for item in comparison.metric_deltas
        if item.direction == "unknown"
    }
    assert "efficiency.declared_max_total_input_tokens" in unknown
    payload = comparison.model_dump(mode="json")
    assert not any("score" in key for key in payload), "比较结果不得包含评分字段"


def test_engine_fingerprint_difference_does_not_block_comparison() -> None:
    """修复改变引擎指纹是预期结果，必须仍然可比，并在 scope 里说明。"""

    report = _report()
    candidate = _with_anchors(report, engine_source_digest="sha256:" + "b" * 64)
    baseline = _with_anchors(report, engine_source_digest="sha256:" + "a" * 64)

    comparison = compare_authoring_quality_reports(baseline, candidate)
    assert comparison.comparable is True
    assert any("引擎指纹不同" in note for note in comparison.scope_notes)


def test_different_frozen_input_refuses_comparison() -> None:
    report = _report()
    other = _with_anchors(
        report,
        frozen_input_digest="sha256:" + "c" * 64,
        repo_snapshot_id="repo:other",
    )
    comparison = compare_authoring_quality_reports(report, other)

    assert comparison.comparable is False
    assert "frozen_input_identity_mismatch" in comparison.blockers
    assert comparison.metric_deltas == (), "不可比时不得给出任何差值"


def test_different_model_identity_refuses_comparison() -> None:
    report = _report()
    other = _with_anchors(report, model_identity_digest="sha256:" + "d" * 64)
    comparison = compare_authoring_quality_reports(report, other)

    assert comparison.comparable is False
    assert "model_identity_mismatch" in comparison.blockers
    assert comparison.metric_deltas == ()


def test_missing_anchor_refuses_comparison(tmp_path: Path) -> None:
    """没有冻结输入身份的根（例如裸目录）不得被当成"同输入"比较。"""

    bare = tmp_path / "bare-run"
    (bare / "artifacts").mkdir(parents=True)
    report = build_authoring_quality_report(bare)
    assert report.comparability.frozen_input_digest == ""

    comparison = compare_authoring_quality_reports(_report(), report)
    assert comparison.comparable is False
    assert "frozen_input_identity_missing" in comparison.blockers
    assert comparison.metric_deltas == ()
    assert comparison.render().startswith("QUALITY COMPARISON  NOT COMPARABLE")


def test_partial_evidence_and_unmeasured_dimensions_are_declared() -> None:
    report = _report()
    comparison = compare_authoring_quality_reports(report, report)

    # 事故归档没有候选产物：必须声明范围不同，而不是假装是完整正文比较。
    assert comparison.partial_evidence is True
    assert any("缺少可比候选产物" in note for note in comparison.scope_notes)
    # 忠实性两侧都未测量 → 只声明原因，不出差值。
    assert "faithfulness" in comparison.dimensions_not_measured
    assert all(item.dimension != "faithfulness" for item in comparison.metric_deltas)


def test_comparison_accepts_report_json_and_is_deterministic(tmp_path: Path) -> None:
    report = _report()
    path = tmp_path / "quality-report.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    directory_input = compare_authoring_quality_reports(
        incident_archive.archive_root(), report
    )
    file_input = compare_authoring_quality_reports(path, report)
    assert directory_input.content_digest == file_input.content_digest
    assert directory_input.comparable == file_input.comparable is True


def test_polarity_table_directions_are_consistent() -> None:
    """方向由显式极性表决定：越大越好的指标上升 → better，反之更差。"""

    report = _report()
    efficiency = report.dimension("efficiency")
    assert efficiency is not None
    worse = report.model_copy(
        update={
            "dimensions": tuple(
                item.model_copy(
                    update={"metrics": {**item.metrics, "provider_sends": 90}}
                )
                if item.dimension == "efficiency"
                else item
                for item in report.dimensions
            )
        }
    )
    comparison = compare_authoring_quality_reports(report, worse)
    sends = next(
        item for item in comparison.metric_deltas if item.metric == "provider_sends"
    )
    assert sends.baseline == 45 and sends.candidate == 90
    assert sends.delta == 45.0
    assert sends.direction == "worse", "发送数上升是变差"
    # 审计 §G.6：provider_sends 属于**条件**效率指标（同 scope + 有效交付 + 覆盖不退化），
    # 不再放在无条件极性表里。
    assert "efficiency.provider_sends" not in METRIC_POLARITY
    from code2paper.agentic.authoring_quality_comparison import (
        CONDITIONAL_EFFICIENCY_POLARITY,
    )

    assert CONDITIONAL_EFFICIENCY_POLARITY["efficiency.provider_sends"] == -1


def test_compare_quality_cli_exit_codes(tmp_path: Path, capsys) -> None:
    from code2paper.cli.agentic_run import method_agent_main, supervised_method_agent_main

    root = str(incident_archive.archive_root())
    assert method_agent_main(["compare-quality", "--baseline", root, "--candidate", root]) == 0
    assert "COMPARABLE" in capsys.readouterr().out

    assert (
        method_agent_main(
            ["compare-quality", "--baseline", root, "--candidate", root, "--json"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["comparable"] is True
    assert payload["metric_deltas"] and payload["metric_deltas"][0]["delta"] == 0.0

    # 不可比 → exit 3（原因已打印）；只读命令不得被包进 worker 监督进程。
    assert method_agent_main(["compare-quality", "--baseline", root, "--candidate", str(tmp_path)]) == 3
    assert "NOT COMPARABLE" in capsys.readouterr().out
    assert supervised_method_agent_main(["compare-quality", "--baseline", root, "--candidate", root]) == 0
    capsys.readouterr()

    assert method_agent_main(["compare-quality", "--baseline", root, "--candidate", str(tmp_path / "absent")]) == 2
    capsys.readouterr()


# --------------------------------------------------------------------------- #
# §G.6：负数不能被读成质量改善
# --------------------------------------------------------------------------- #


def _dimension_update(report, dimension: str, **metrics):
    """替换某个维度的 metrics（保留 proxy 与状态）。"""

    return report.model_copy(
        update={
            "dimensions": tuple(
                item.model_copy(update={"metrics": {**item.metrics, **metrics}})
                if item.dimension == dimension
                else item
                for item in report.dimensions
            )
        }
    )


def _metric(comparison, metric: str):
    return next(
        item for item in comparison.metric_deltas if item.metric == metric
    )


def test_fewer_required_formulas_is_not_an_improvement() -> None:
    report = _report()
    candidate = _dimension_update(
        report, "information_utilization", **{"formula.required": 0}
    )

    comparison = compare_authoring_quality_reports(report, candidate)
    required = _metric(comparison, "formula.required")
    assert required.direction == "unknown", required
    assert any("分母不同" in note for note in comparison.scope_notes)


def test_empty_candidate_tokens_are_not_an_efficiency_gain() -> None:
    """空候选/提前失败的零 token、少调用不得标成改善。"""

    report = _report()
    candidate = _dimension_update(
        report,
        "efficiency",
        **{
            "provider_sends": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        },
    )
    candidate = _dimension_update(
        candidate, "recovery_robustness", **{"pages_accepted": 0}
    )

    comparison = compare_authoring_quality_reports(report, candidate)
    assert _metric(comparison, "provider_sends").direction == "unknown"
    assert _metric(comparison, "total_tokens").direction == "unknown"
    assert any("效率差异不解释" in note for note in comparison.scope_notes)
    assert not any(
        item.direction == "better" and item.metric in {"provider_sends", "total_tokens"}
        for item in comparison.metric_deltas
    )


def test_hiding_gaps_while_coverage_regresses_is_not_an_improvement() -> None:
    report = _report()
    baseline = _dimension_update(
        report,
        "intent_coverage",
        **{"explicit_gaps": 5, "supported_must_cover_ratio": 0.9},
    )
    candidate = _dimension_update(
        report,
        "intent_coverage",
        **{
            "explicit_gaps": 0,
            "supported_must_cover_ratio": 0.25,
            "provider_sends": 1,  # 提前失败带来的少调用
        },
    )

    comparison = compare_authoring_quality_reports(baseline, candidate)
    gaps = _metric(comparison, "explicit_gaps")
    # 同一分母下 gap 归零但覆盖率退化：少报 gap 仍不得读成改善。
    assert gaps.delta == -5.0
    assert gaps.direction == "unknown", gaps
    assert any("覆盖退化" in note for note in comparison.scope_notes)

    # 正例：覆盖不退化时，gap 减少才是改善。
    better = _dimension_update(
        baseline,
        "intent_coverage",
        **{"explicit_gaps": 0, "supported_must_cover_ratio": 0.95},
    )
    improved = compare_authoring_quality_reports(baseline, better)
    assert _metric(improved, "explicit_gaps").direction == "better"


def test_same_scope_efficiency_direction_still_applies() -> None:
    """同 scope + 交付不退化时，效率指标仍必须给出方向（否则规则形同废纸）。"""

    report = _report()
    candidate = _dimension_update(report, "efficiency", **{"provider_sends": 20})

    comparison = compare_authoring_quality_reports(report, candidate)
    assert _metric(comparison, "provider_sends").direction == "better"
    assert not any("效率差异不解释" in note for note in comparison.scope_notes)


def test_not_measured_reasons_from_both_sides_are_preserved() -> None:
    report = _report()
    edited = report.model_copy(
        update={
            "dimensions": tuple(
                item.model_copy(
                    update={
                        "status": "not_measured",
                        "not_measured_reason": "candidate-side reason"
                        if item.dimension == "faithfulness"
                        else item.not_measured_reason,
                    }
                )
                if item.dimension == "faithfulness"
                else item
                for item in report.dimensions
            )
        }
    )

    comparison = compare_authoring_quality_reports(report, edited)
    reason = comparison.dimensions_not_measured["faithfulness"]
    assert "baseline:" in reason and "candidate:" in reason
    assert "candidate-side reason" in reason
