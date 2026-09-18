"""§14.3：authoring 质量报告（只报可机械复算的维度，其余显式标"未测量"）。

方案 §14.3 要求"同时报告运行正确性和学术质量，不能只报 accepted_pages / pages"，
并列出六个维度。本模块把它们拆成两类：

* **可机械复算**：效率（发送调用数、真实 tokens、无效调用量、首次接受率、repair 收益、
  预算占用）、恢复健壮性（耗尽 invocation、阻塞页、未结算预留、拒发是否真的没发送）、
  意图覆盖中由 `obligation_coverage_v2` 直接给出的有依据/未解决计数、
  信息利用中由 `method_authoring_closure_metrics_v1` / realizer 回执给出的消费计数；
* **需要语义判断**：忠实性（无依据新增陈述、authority 误升级、公式/方向错误）、
  叙事质量的文体部分。离线没有判断者，因此**如实标 `not_measured` 并写明缺什么**，
  而不是编一个分数。

所有数值都来自产物本身；除汇总与比率外不做任何再解释。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_doctor import run_authoring_doctor
from code2paper.agentic.authoring_execution_identity import (
    load_execution_identity,
    scan_exhausted_invocations,
)
from code2paper.agentic.mechanism_context_models import canonical_json_bytes, sha256_digest
from code2paper.agentic.reused_evidence_index import (
    classify_receipt,
    load_reused_evidence_index,
    normalize_relative,
)
from code2paper.agentic.writer_attempt_ledger import (
    read_invocation_ledger_state,
    unsettled_reservations,
)

__all__ = [
    "QualityDimensionV1",
    "QualityComparabilityV1",
    "AuthoringQualityReportV1",
    "build_authoring_quality_report",
]

#: 六个维度及其在离线下的可测性（方案 §14.3 表格顺序）。
_DIMENSIONS = (
    "intent_coverage",
    "information_utilization",
    "faithfulness",
    "narrative_quality",
    "recovery_robustness",
    "efficiency",
)

_REQUIRES_SEMANTIC_JUDGEMENT = {
    "faithfulness": (
        "无依据新增陈述、authority 误升级、训练/推理混淆、公式/方向错误都需要把正文与"
        "冻结证据逐句比对；离线没有语义判断者，本报告不给出分数。"
    ),
}


class QualityDimensionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dimension: str
    #: measured = 全部指标来自产物；partial = 只有代理/部分指标；not_measured = 未测量。
    status: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    proxies: dict[str, Any] = Field(default_factory=dict)
    not_measured_reason: str = ""
    evidence_paths: dict[str, str] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()


class QualityComparabilityV1(BaseModel):
    """§14.3 对照比较的锚点：只有冻结输入与模型配置相同，比较才有意义。

    引擎指纹**故意**不参与可比性判定——修复本身就会改变引擎指纹，那正是要比较的对象。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    frozen_input_digest: str = ""
    repo_snapshot_id: str = ""
    project_tree_hash: str = ""
    run_identity_digest: str = ""
    model_identity_digest: str = ""
    profile_digest: str = ""
    engine_source_digest: str = ""
    execution_id: str = ""
    sources: dict[str, str] = Field(default_factory=dict)

    def is_comparable_with(self, other: "QualityComparabilityV1") -> tuple[bool, tuple[str, ...]]:
        """返回 (是否可比, 阻断原因元组)。缺锚点即不可比（fail-closed）。"""

        reasons: list[str] = []
        if not self.frozen_input_digest or not other.frozen_input_digest:
            reasons.append("frozen_input_identity_missing")
        elif self.frozen_input_digest != other.frozen_input_digest:
            reasons.append("frozen_input_identity_mismatch")
        if not self.model_identity_digest or not other.model_identity_digest:
            reasons.append("model_identity_missing")
        elif self.model_identity_digest != other.model_identity_digest:
            reasons.append("model_identity_mismatch")
        return (not reasons), tuple(reasons)


class AuthoringQualityReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    out_root: str
    execution_identity: str = ""
    dimensions: tuple[QualityDimensionV1, ...] = ()
    unmeasured_dimensions: tuple[str, ...] = ()
    candidate_artifacts: tuple[str, ...] = ()
    comparability: QualityComparabilityV1 = Field(default_factory=QualityComparabilityV1)
    comparison_status: str = "not_available"
    comparison_note: str = ""
    content_digest: str = ""

    def dimension(self, name: str) -> QualityDimensionV1 | None:
        for item in self.dimensions:
            if item.dimension == name:
                return item
        return None

    def render(self) -> str:
        lines = [
            f"AUTHORING QUALITY  {self.out_root}",
            f"EXECUTION          {self.execution_identity or '(unknown)'}",
        ]
        for item in self.dimensions:
            lines.append(f"[{item.status.upper()}] {item.dimension}")
            for key, value in sorted(item.metrics.items()):
                lines.append(f"    {key} = {value}")
            for key, value in sorted(item.proxies.items()):
                lines.append(f"    (proxy) {key} = {value}")
            if item.not_measured_reason:
                lines.append(f"    not measured: {item.not_measured_reason}")
            for note in item.notes:
                lines.append(f"    note: {note}")
        lines.append(f"COMPARISON         {self.comparison_status} {self.comparison_note}".rstrip())
        anchor = self.comparability
        lines.append(
            "ANCHORS            "
            f"frozen_input={anchor.frozen_input_digest[:19] or '(missing)'} "
            f"model={anchor.model_identity_digest[:19] or '(missing)'} "
            f"engine={anchor.engine_source_digest[:19] or '(missing)'}"
        )
        if self.unmeasured_dimensions:
            lines.append("UNMEASURED         " + ", ".join(self.unmeasured_dimensions))
        return "\n".join(lines)


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _receipts(out_root: Path) -> list[Mapping[str, Any]]:
    """读取回执，并按复用证据索引标注来源（复制自冻结根的回执不算本次产生）。"""

    ledger = out_root / "artifacts" / "06_authoring" / "invocations"
    index = load_reused_evidence_index(out_root)
    receipts: list[Mapping[str, Any]] = []
    for path in sorted(ledger.glob("*/attempt-*.completed.json")):
        payload = _read_json(path)
        if not payload:
            continue
        relative = normalize_relative(path, ledger)
        receipts.append({
            **payload,
            "_path": str(path),
            "_relative": relative,
            "_reused": classify_receipt(
                index=index, relative_path=relative, receipt_path=path
            ),
        })
    return receipts


def _invocation_states(
    out_root: Path, receipts: Iterable[Mapping[str, Any]] | None = None
) -> tuple[Any, ...]:
    """按 invocation 读取账本状态（接受语义以账本为准，不看回执的 delivery_status）。

    复用证据索引里声明的 invocation（其回执全部复制自冻结根）不参与本次 run 的
    效率统计——它们的用量与接受情况属于历史。
    """

    ledger = out_root / "artifacts" / "06_authoring" / "invocations"
    if not ledger.is_dir():
        return ()
    rows = list(receipts) if receipts is not None else _receipts(out_root)
    fresh_invocations: set[str] = set()
    reused_invocations: set[str] = set()
    for row in rows:
        invocation_id = str(row.get("invocation_id") or "")
        if not invocation_id:
            continue
        if row.get("_reused"):
            reused_invocations.add(invocation_id)
        else:
            fresh_invocations.add(invocation_id)
    reused_invocations -= fresh_invocations
    states = []
    for invocation_id in sorted(fresh_invocations):
        states.append(read_invocation_ledger_state(out_root, invocation_id))
    return tuple(states)


def _reused_invocation_ids(
    out_root: Path, receipts: Iterable[Mapping[str, Any]]
) -> tuple[str, ...]:
    rows = list(receipts)
    fresh = {
        str(row.get("invocation_id") or "")
        for row in rows
        if not row.get("_reused")
    }
    reused = {
        str(row.get("invocation_id") or "")
        for row in rows
        if row.get("_reused")
    }
    return tuple(sorted(name for name in (reused - fresh) if name))


def _efficiency(out_root: Path, receipts: Iterable[Mapping[str, Any]]) -> QualityDimensionV1:
    rows = list(receipts)
    sent = [row for row in rows if bool(row.get("sent_to_caller", True))]
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for row in sent:
        provider_usage = row.get("provider_usage") or {}
        if not isinstance(provider_usage, Mapping):
            continue
        usage["input_tokens"] += int(provider_usage.get("prompt_tokens") or 0)
        usage["output_tokens"] += int(provider_usage.get("completion_tokens") or 0)
        usage["total_tokens"] += int(provider_usage.get("total_tokens") or 0)

    # 发送与接受一律以持久账本为准：回执 delivery_status=accepted 只表示"响应已交付"，
    # 页是否被接受由任务完成度与账本 accepted/primary_accepted 决定（事故中两者不等）。
    states = _invocation_states(out_root, rows)
    reused_invocations = _reused_invocation_ids(out_root, rows)
    provider_sends = sum(int(state.counters.provider_send_count) for state in states)
    content_attempts = sum(int(state.counters.content_attempt_count) for state in states)
    rejected_before_send = sum(
        len(tuple(state.counters.rejected_before_send_events)) for state in states
    )
    with_send = [state for state in states if int(state.counters.provider_send_count) > 0]
    primary_accepted = [state for state in with_send if state.primary_accepted]
    repaired = [state for state in states if int(state.counters.content_repair_count) > 0]
    repair_accepted = [state for state in repaired if state.accepted]

    roles: dict[str, int] = {}
    for row in sent:
        role = str(row.get("consumer_role") or "unknown")
        roles[role] = roles.get(role, 0) + 1

    envelope = _read_json(
        out_root / "artifacts" / "06_authoring" / "run_invocation_budget_envelope_v1.json"
    )
    budget_total = int(envelope.get("max_total_input_tokens") or 0)
    ledger = out_root / "artifacts" / "06_authoring" / "invocations"
    directories = (
        [path for path in ledger.iterdir() if path.is_dir()] if ledger.is_dir() else []
    )
    metrics: dict[str, Any] = {
        "invocations": len(states),
        "invocation_directories": len(directories),
        "invocation_directories_without_receipts": max(
            0, len(directories) - len({str(row.get("invocation_id") or "") for row in rows})
        ),
        "reused_evidence_invocations": len(reused_invocations),
        "reused_evidence_receipts": sum(1 for row in rows if row.get("_reused")),
        "provider_sends": provider_sends,
        "provider_sends_by_role_from_receipts": dict(sorted(roles.items())),
        "content_attempts": content_attempts,
        "rejected_before_send_events": rejected_before_send,
        "invocations_with_a_send": len(with_send),
        **usage,
        "first_attempt_acceptance_rate": _ratio(len(primary_accepted), len(with_send)),
        "invocations_accepted_without_repair": len(primary_accepted),
        "invocations_needing_repair": len(repaired),
        "repair_acceptance_rate": _ratio(len(repair_accepted), len(repaired)),
        "invocations_accepted": sum(1 for state in states if state.accepted),
        "tokens_per_provider_send": (
            _ratio(usage["total_tokens"], provider_sends) if provider_sends else None
        ),
        "declared_max_total_input_tokens": budget_total or None,
        "input_token_budget_utilization": (
            _ratio(usage["input_tokens"], budget_total) if budget_total else None
        ),
    }
    notes = []
    if rejected_before_send:
        notes.append("拒发事件未产生 provider-request，因此不计入真实开销与发送数。")
    return QualityDimensionV1(
        dimension="efficiency",
        status="measured" if states else "not_measured",
        metrics=metrics,
        not_measured_reason="" if states else "没有 invocation 账本目录：无法给出效率指标",
        notes=tuple(notes),
        evidence_paths={
            "invocation_receipts": str(
                out_root / "artifacts" / "06_authoring" / "invocations"
            ),
            "budget_envelope": str(
                out_root / "artifacts" / "06_authoring" / "run_invocation_budget_envelope_v1.json"
            ),
        },
    )


def _recovery_robustness(out_root: Path, doctor: Any) -> QualityDimensionV1:
    exhausted = scan_exhausted_invocations(out_root)
    unsettled: dict[str, int] = {}
    last_failure_codes: dict[str, list[str]] = {}
    for invocation_id in exhausted:
        state = read_invocation_ledger_state(out_root, invocation_id)
        last_failure_codes[invocation_id] = list(state.last_content_failure_codes)
        retained = unsettled_reservations(out_root, invocation_id)
        if retained:
            unsettled[invocation_id] = len(retained)
        elif not state.accepted:
            unsettled.setdefault(invocation_id, 0)
    return QualityDimensionV1(
        dimension="recovery_robustness",
        status="measured",
        metrics={
            "pages_total": doctor.page_count,
            "pages_accepted": doctor.accepted_page_count,
            "blocked_pages": len(doctor.blocked_pages),
            "exhausted_invocations": len(exhausted),
            "exhausted_invocation_ids": list(exhausted),
            "invocations_with_unsettled_reservation": sum(
                1 for count in unsettled.values() if count
            ),
            "terminal_reason": doctor.first_root_cause,
            "downstream_not_run": list(doctor.downstream_not_run),
            "exhausted_invocation_failure_codes": last_failure_codes,
        },
        notes=(
            "耗尽/阻塞必须保持可解释：报告只汇总持久回执里的既有结论，不重算预算。",
        )
        + tuple(
            f"{page.invocation_id}: {page.content_attempts_used}/"
            f"{page.content_attempt_limit} content attempts, rejected_before_send="
            f"{list(page.rejected_before_send_events)}"
            for page in doctor.blocked_pages
        ),
        evidence_paths={"doctor": str(out_root / "artifacts" / "06_authoring")},
    )


def _intent_coverage(out_root: Path, doctor: Any) -> QualityDimensionV1:
    artifacts = out_root / "artifacts"
    coverage = _read_json(artifacts / "obligation_coverage_v2.json")
    metrics: dict[str, Any] = {
        "must_cover_obligations": int(coverage.get("must_cover_count") or 0),
        "supported_must_cover": int(coverage.get("supported_must_cover_count") or 0),
        "terminal_must_cover": int(coverage.get("terminal_must_cover_count") or 0),
        "unresolved_must_cover": len(coverage.get("unresolved_must_cover_ids") or ()),
        "explicit_gaps": int(coverage.get("explicit_gap_count") or 0),
        "supported_must_cover_ratio": _ratio(
            int(coverage.get("supported_must_cover_count") or 0),
            int(coverage.get("must_cover_count") or 0),
        ),
    }
    proxies = {
        "paragraphs_without_per_paragraph_material": doctor.empty_semantic_paragraph_count,
        "binder_owned_targets_shown_to_writer": doctor.binder_owned_writer_target_count,
    }
    status = "measured" if coverage else "partial"
    reason = (
        ""
        if coverage
        else "缺少 obligation_coverage_v2：只能给出意图表面代理指标"
    )
    return QualityDimensionV1(
        dimension="intent_coverage",
        status=status,
        metrics=metrics if coverage else {},
        proxies=proxies,
        not_measured_reason=reason,
        notes=(
            "作者限定描述的落地位置是否正确需要语义判断，本报告未测量。",
        ),
        evidence_paths={
            "obligation_coverage_v2": str(artifacts / "obligation_coverage_v2.json"),
            "intent_narrative_plan_v4": str(
                artifacts / "06_authoring" / "intent_narrative_plan_v4.json"
            ),
        },
    )


def _information_utilization(out_root: Path, receipts: Iterable[Mapping[str, Any]]) -> QualityDimensionV1:
    artifacts = out_root / "artifacts"
    closure = _read_json(artifacts / "method_authoring_closure_metrics_v1.json")
    metrics: dict[str, Any] = {}
    for block in ("research", "alignment", "planning", "formula", "verification", "writer"):
        payload = closure.get(block)
        if isinstance(payload, Mapping):
            for key, value in payload.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    metrics[f"{block}.{key}"] = value
    all_rows = list(receipts)
    rows = [
        row
        for row in all_rows
        if bool(row.get("sent_to_caller", True)) and not row.get("_reused")
    ]
    delivered = [row for row in rows if str(row.get("delivery_status")) == "accepted"]
    states = _invocation_states(out_root, all_rows)
    metrics["consumer_receipts"] = len(rows)
    metrics["consumer_receipts_delivered"] = len(delivered)
    metrics["consumer_invocation_acceptance_rate"] = _ratio(
        sum(1 for state in states if state.accepted), len(states)
    )
    status = "partial" if metrics else "not_measured"
    return QualityDimensionV1(
        dimension="information_utilization",
        status=status,
        metrics=metrics,
        not_measured_reason=(
            ""
            if metrics
            else "缺少 closure metrics 与消费回执：无法给出 detail/公式消费计数"
        ),
        notes=(
            "这里只报「冻结的 detail/条件/公式是否被计数消费」；"
            "是否消费得**正确**属于忠实性，未测量。",
        ),
        evidence_paths={
            "closure_metrics": str(artifacts / "method_authoring_closure_metrics_v1.json"),
            "formula_identity_conservation": str(
                artifacts / "06_authoring" / "formula_identity_conservation_v1.json"
            ),
        },
    )


def _narrative_quality(doctor: Any) -> QualityDimensionV1:
    return QualityDimensionV1(
        dimension="narrative_quality",
        status="partial",
        proxies={
            "paragraphs_without_per_paragraph_material": (
                doctor.empty_semantic_paragraph_count
            ),
            "pages_blocked": len(doctor.blocked_pages),
        },
        not_measured_reason=(
            "段落局部问题是否讲清、角色位置是否正确、模板填充段与重复率，"
            "都需要读正文；离线只给出「无段落材料」这一可机械计数的代理指标。"
        ),
        notes=(
            "代理指标的用途是定位，不是评分：为 0 也不等于叙事质量合格。",
        ),
    )


def _candidate_artifacts(out_root: Path) -> tuple[str, ...]:
    candidates: list[str] = []
    for relative in (
        "artifacts/06_authoring/publication_candidate_method.md",
        "artifacts/06_authoring/method_content_trace_v2.json",
        "artifacts/06_authoring/publication_writer_result_v1.json",
        "artifacts/06_authoring/repository_verified_method.md",
    ):
        path = out_root / relative
        if path.is_file() and path.stat().st_size > 0:
            candidates.append(relative)
    return tuple(candidates)


def _comparability(out_root: Path, identity: Any) -> QualityComparabilityV1:
    """从产物里提取冻结输入/模型/引擎锚点（缺失即留空——比较方据此 fail-closed）。"""

    artifacts = out_root / "artifacts"
    authoring = artifacts / "06_authoring"
    contract = _read_json(authoring / "authoring_run_contract_v1.json")
    checkpoint = _read_json(artifacts / "research_product" / "research_stage_checkpoint_v1.json")
    envelope = _read_json(authoring / "run_invocation_budget_envelope_v1.json")

    repo_snapshot_id = str(
        contract.get("repo_snapshot_id") or checkpoint.get("repo_snapshot_id") or ""
    )
    project_tree_hash = str(
        contract.get("project_tree_hash") or checkpoint.get("project_tree_hash") or ""
    )
    run_identity_digest = str(contract.get("run_identity_digest") or "")
    code_commit_sha = str(contract.get("code_commit_sha") or "")
    frozen_input_digest = (
        sha256_digest(
            canonical_json_bytes(
                {
                    "repo_snapshot_id": repo_snapshot_id,
                    "project_tree_hash": project_tree_hash,
                    "run_identity_digest": run_identity_digest,
                    "code_commit_sha": code_commit_sha,
                }
            )
        )
        if (repo_snapshot_id or project_tree_hash or run_identity_digest or code_commit_sha)
        else ""
    )
    sources = {}
    if contract:
        sources["authoring_run_contract_v1"] = str(
            authoring / "authoring_run_contract_v1.json"
        )
    if checkpoint:
        sources["research_stage_checkpoint_v1"] = str(
            artifacts / "research_product" / "research_stage_checkpoint_v1.json"
        )
    if envelope:
        sources["run_invocation_budget_envelope_v1"] = str(
            authoring / "run_invocation_budget_envelope_v1.json"
        )
    if identity is not None:
        sources["authoring_execution_identity_v2"] = str(
            artifacts / "research_product" / "authoring_execution_identity_v2.json"
        )
    return QualityComparabilityV1(
        frozen_input_digest=frozen_input_digest,
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        run_identity_digest=run_identity_digest,
        model_identity_digest=str(envelope.get("model_identity_digest") or ""),
        profile_digest=str(envelope.get("profile_digest") or ""),
        engine_source_digest=str(getattr(identity, "engine_source_digest", "") or ""),
        execution_id=str(getattr(identity, "execution_id", "") or ""),
        sources=sources,
    )


def build_authoring_quality_report(out_root: str | Path) -> AuthoringQualityReportV1:
    """只读装配 §14.3 报告（不写任何文件、不调用模型）。"""

    root = Path(out_root).expanduser().resolve()
    doctor = run_authoring_doctor(root)
    identity = load_execution_identity(root)
    receipts = _receipts(root)

    dimensions = [
        _intent_coverage(root, doctor),
        _information_utilization(root, receipts),
        QualityDimensionV1(
            dimension="faithfulness",
            status="not_measured",
            not_measured_reason=_REQUIRES_SEMANTIC_JUDGEMENT["faithfulness"],
            notes=(
                "需要：冻结证据集合 + 最终正文 + 逐句/逐公式比对；三者齐备前不报分。",
            ),
        ),
        _narrative_quality(doctor),
        _recovery_robustness(root, doctor),
        _efficiency(root, receipts),
    ]
    unmeasured = tuple(
        item.dimension for item in dimensions if item.status == "not_measured"
    )
    candidates = _candidate_artifacts(root)
    if len(candidates) >= 2:
        comparison_status = "candidates_present"
        comparison_note = "存在候选产物；与旧候选/独立 baseline 的差异比较仍需同一冻结输入下的对照运行。"
    else:
        comparison_status = "not_available"
        comparison_note = (
            "没有可比的候选产物：§14.3 要求同一冻结输入、同一模型配置的旧候选与独立 "
            "baseline；缺失时不伪造旧完整输出。"
        )
    comparability = _comparability(root, identity)
    payload = {
        "out_root": str(root),
        "execution_identity": doctor.execution_identity,
        "identity_digest": (identity.content_digest if identity else ""),
        "dimensions": [item.model_dump(mode="json") for item in dimensions],
        "candidates": list(candidates),
        "comparison_status": comparison_status,
        "comparability": comparability.model_dump(mode="json"),
    }
    return AuthoringQualityReportV1(
        out_root=str(root),
        execution_identity=doctor.execution_identity,
        dimensions=tuple(dimensions),
        unmeasured_dimensions=unmeasured,
        candidate_artifacts=candidates,
        comparability=comparability,
        comparison_status=comparison_status,
        comparison_note=comparison_note,
        content_digest=sha256_digest(canonical_json_bytes(payload)),
    )
