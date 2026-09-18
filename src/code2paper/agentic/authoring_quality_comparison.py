"""§14.3：两份质量报告的对照比较（同冻结输入 + 同模型配置才可比）。

规则（全部 fail-closed，且**不产生任何综合评分**）：

* 冻结输入身份或模型身份缺失/不一致 → `comparable=False`，只报锚点差异，不给差值；
* 引擎指纹不同**不**阻断比较——代码修复正是要比较的对象，它被记录在锚点里；
* 只有极性明确的机械指标才给 `direction`；极性依赖判断的指标只给原始 delta 与
  `direction="unknown"`；
* 任一侧 `not_measured` 的维度不出差值，只列出"哪一侧没测、为什么"；
* 事故归档这类缺少完整 clean candidate 的输入，比较结果必须带范围声明
  （§14.3：可以比较已存的局部响应，但必须标明范围不同）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_quality_report import (
    AuthoringQualityReportV1,
    build_authoring_quality_report,
)
from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest

__all__ = [
    "QualityMetricDeltaV1",
    "AuthoringQualityComparisonV1",
    "METRIC_POLARITY",
    "compare_authoring_quality_reports",
]

#: 极性明确的机械指标：+1 = 越大越好，-1 = 越小越好。
#: 只收录方向无歧义的计数/比率；语义质量指标一律不在此表（direction=unknown）。
METRIC_POLARITY: Mapping[str, int] = {
    "efficiency.first_attempt_acceptance_rate": 1,
    "efficiency.repair_acceptance_rate": 1,
    "efficiency.invocations_accepted": 1,
    "efficiency.provider_sends": -1,
    "efficiency.content_attempts": -1,
    "efficiency.rejected_before_send_events": -1,
    "efficiency.input_tokens": -1,
    "efficiency.output_tokens": -1,
    "efficiency.total_tokens": -1,
    "efficiency.tokens_per_provider_send": -1,
    "efficiency.input_token_budget_utilization": -1,
    "recovery_robustness.pages_accepted": 1,
    "recovery_robustness.blocked_pages": -1,
    "recovery_robustness.exhausted_invocations": -1,
    "recovery_robustness.invocations_with_unsettled_reservation": -1,
    "intent_coverage.must_cover_obligations": 1,
    "intent_coverage.supported_must_cover": 1,
    "intent_coverage.terminal_must_cover": 1,
    "intent_coverage.supported_must_cover_ratio": 1,
    "intent_coverage.unresolved_must_cover": -1,
    "intent_coverage.explicit_gaps": -1,
    "intent_coverage.paragraphs_without_per_paragraph_material": -1,
    "intent_coverage.binder_owned_targets_shown_to_writer": -1,
    "information_utilization.formula.consumed": 1,
    "information_utilization.formula.required": -1,
    "information_utilization.consumer_invocation_acceptance_rate": 1,
    "narrative_quality.paragraphs_without_per_paragraph_material": -1,
    "narrative_quality.pages_blocked": -1,
}


class QualityMetricDeltaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str
    metric: str
    baseline: Any | None = None
    candidate: Any | None = None
    delta: float | None = None
    direction: str = "unknown"


class AuthoringQualityComparisonV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    comparable: bool = False
    blockers: tuple[str, ...] = ()
    baseline_root: str = ""
    candidate_root: str = ""
    anchors: dict[str, Any] = Field(default_factory=dict)
    metric_deltas: tuple[QualityMetricDeltaV1, ...] = ()
    dimensions_not_measured: dict[str, str] = Field(default_factory=dict)
    scope_notes: tuple[str, ...] = ()
    partial_evidence: bool = False
    content_digest: str = ""

    def render(self) -> str:
        lines = [
            f"QUALITY COMPARISON  {'COMPARABLE' if self.comparable else 'NOT COMPARABLE'}",
            f"BASELINE           {self.baseline_root}",
            f"CANDIDATE          {self.candidate_root}",
        ]
        for key, value in sorted(self.anchors.items()):
            lines.append(f"    anchor {key} = {value}")
        for blocker in self.blockers:
            lines.append(f"BLOCKER            {blocker}")
        if self.comparable:
            for item in self.metric_deltas:
                lines.append(
                    f"    {item.dimension}.{item.metric}: {item.baseline} -> "
                    f"{item.candidate} (delta={item.delta}, {item.direction})"
                )
        for dimension, reason in sorted(self.dimensions_not_measured.items()):
            lines.append(f"NOT MEASURED       {dimension}: {reason}")
        for note in self.scope_notes:
            lines.append(f"SCOPE              {note}")
        return "\n".join(lines)


def _as_report(source: AuthoringQualityReportV1 | str | Path | Mapping[str, Any]) -> AuthoringQualityReportV1:
    if isinstance(source, AuthoringQualityReportV1):
        return source
    if isinstance(source, Mapping):
        return AuthoringQualityReportV1.model_validate(dict(source))
    path = Path(source).expanduser()
    if path.is_dir():
        return build_authoring_quality_report(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return AuthoringQualityReportV1.model_validate(payload)


def _flatten(report: AuthoringQualityReportV1) -> dict[str, Any]:
    """把报告摊平成 ``dimension.metric`` → 值（只含数值与布尔，供客观比较）。"""

    flat: dict[str, Any] = {}
    for dimension in report.dimensions:
        for key, value in dimension.metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                flat[f"{dimension.dimension}.{key}"] = value
        for key, value in dimension.proxies.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                flat[f"{dimension.dimension}.{key}"] = value
    return flat


def _direction(metric: str, delta: float | None) -> str:
    if delta is None:
        return "unknown"
    polarity = METRIC_POLARITY.get(metric)
    if polarity is None or delta == 0:
        return "unknown" if polarity is None else "same"
    improved = delta > 0 if polarity > 0 else delta < 0
    return "better" if improved else "worse"


def compare_authoring_quality_reports(
    baseline: AuthoringQualityReportV1 | str | Path | Mapping[str, Any],
    candidate: AuthoringQualityReportV1 | str | Path | Mapping[str, Any],
) -> AuthoringQualityComparisonV1:
    """逐指标比较两份报告；不可比时只报锚点与原因，不给任何差值。"""

    left = _as_report(baseline)
    right = _as_report(candidate)
    comparable, blockers = left.comparability.is_comparable_with(right.comparability)

    anchors = {
        "baseline_frozen_input_digest": left.comparability.frozen_input_digest,
        "candidate_frozen_input_digest": right.comparability.frozen_input_digest,
        "baseline_model_identity_digest": left.comparability.model_identity_digest,
        "candidate_model_identity_digest": right.comparability.model_identity_digest,
        "baseline_engine_source_digest": left.comparability.engine_source_digest,
        "candidate_engine_source_digest": right.comparability.engine_source_digest,
        "baseline_execution_id": left.comparability.execution_id,
        "candidate_execution_id": right.comparability.execution_id,
    }

    not_measured: dict[str, str] = {}
    for report, label in ((left, "baseline"), (right, "candidate")):
        for dimension in report.dimensions:
            if dimension.status == "not_measured":
                not_measured[dimension.dimension] = (
                    f"{label}: {dimension.not_measured_reason or 'not measured'}"
                )

    scope_notes: list[str] = []
    partial_evidence = False
    for report, label in ((left, "baseline"), (right, "candidate")):
        if report.comparison_status != "candidates_present":
            partial_evidence = True
            scope_notes.append(
                f"{label} 缺少可比候选产物（candidates={len(report.candidate_artifacts)}）："
                "差异只代表已存证据，不代表完整正文质量。"
            )
    if left.comparability.engine_source_digest != right.comparability.engine_source_digest:
        scope_notes.append(
            "引擎指纹不同（这是修复的预期结果，不阻断比较）："
            f"{left.comparability.engine_source_digest[:19] or '(missing)'} -> "
            f"{right.comparability.engine_source_digest[:19] or '(missing)'}"
        )

    deltas: list[QualityMetricDeltaV1] = []
    if comparable:
        left_flat = _flatten(left)
        right_flat = _flatten(right)
        for metric in sorted(set(left_flat) | set(right_flat)):
            baseline_value = left_flat.get(metric)
            candidate_value = right_flat.get(metric)
            delta: float | None = None
            if isinstance(baseline_value, (int, float)) and isinstance(
                candidate_value, (int, float)
            ):
                delta = round(float(candidate_value) - float(baseline_value), 6)
            deltas.append(
                QualityMetricDeltaV1(
                    dimension=metric.split(".", 1)[0],
                    metric=metric.split(".", 1)[1],
                    baseline=baseline_value,
                    candidate=candidate_value,
                    delta=delta,
                    direction=_direction(metric, delta),
                )
            )

    payload = {
        "baseline_root": left.out_root,
        "candidate_root": right.out_root,
        "comparable": comparable,
        "blockers": list(blockers),
        "anchors": anchors,
        "deltas": [item.model_dump(mode="json") for item in deltas],
        "not_measured": not_measured,
        "scope_notes": scope_notes,
    }
    return AuthoringQualityComparisonV1(
        comparable=comparable,
        blockers=blockers,
        baseline_root=left.out_root,
        candidate_root=right.out_root,
        anchors=anchors,
        metric_deltas=tuple(deltas),
        dimensions_not_measured=not_measured,
        scope_notes=tuple(scope_notes),
        partial_evidence=partial_evidence,
        content_digest=sha256_digest(canonical_json_bytes(payload)),
    )
