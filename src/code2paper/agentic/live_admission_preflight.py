"""方案 §14.1：live 准入预检（离线可跑，不发起任何模型调用）。

live 之前必须逐条确认：执行身份可冻结、输入一致、模型/预算/停止条件显式声明、
out 目录身份合法、doctor 无 critical 阻断。本模块把这些条件变成一次可复算的检查，
输出 `ready` 与**具体阻断项**——授权到达后即可直接进入 L1，而不是临场逐项手查。

它完全只读：不写 run 目录、不创建身份、不发请求。身份由产品入口创建。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_doctor import run_authoring_doctor
from code2paper.agentic.authoring_execution_identity import (
    RESEARCH_IMPORT_UNVERIFIABLE,
    EngineSourceSnapshot,
    RunOpenDecision,
    ValidatorBundleSnapshot,
    build_run_open_identity,
    capture_engine_source_snapshot,
    capture_target_identity,
    capture_validator_bundle_snapshot,
    validate_run_open,
    verify_research_import,
)
from code2paper.agentic.transport_retry_policy import (
    TransportRetryPolicyV1,
    load_transport_retry_policy,
)

__all__ = [
    "LiveAdmissionGateV1",
    "LiveAdmissionReportV1",
    "OfflineSuiteReceiptV1",
    "RuntimeProbeSummaryV1",
    "build_offline_suite_receipt",
    "parse_runtime_probe",
    "preflight_live_admission",
    "read_offline_suite_receipt",
    "write_offline_suite_receipt",
]

_SUMMARY_PATTERN = re.compile(r"(\d+)\s+(passed|failed|error|errors|deselected)")


#: §14.4：live 准入要求的**必测集合**。回执必须证明这些集合真的跑过，
#: 而不是"某条命令有 1 passed"。
REQUIRED_OFFLINE_TEST_PLAN: tuple[str, ...] = (
    "tests/regression_20260917",
    "tests/regression_20260922",
    "tests/test_agentic_publication_method_writer_unified.py",
    "tests/test_llm_section_writer.py",
)


class OfflineSuiteReceiptV1(BaseModel):
    """§14.1/§14.4 "offline 全链通过" 的可复算证据。

    必须绑定：引擎内容指纹、验收规则身份、有效配置身份、**必测集合**身份与原始输出摘要。
    引擎/validator/config/测试集合任一变化，旧回执即失效。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    passed: bool = False
    exit_code: int = -1
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    deselected_count: int = 0
    command: str = ""
    engine_commit_sha: str = ""
    engine_source_digest: str = ""
    worktree_dirty_entry_count: int = 0
    #: §14.4：回执必须绑定验收规则、有效配置与必测集合身份。
    validator_bundle_digest: str = ""
    effective_config_digest: str = ""
    test_plan_ids: tuple[str, ...] = ()
    test_plan_digest: str = ""
    output_digest: str = ""

    def matches(
        self,
        snapshot: EngineSourceSnapshot,
        *,
        validator_bundle_digest: str = "",
        effective_config_digest: str = "",
        required_test_plan: tuple[str, ...] = (),
    ) -> bool:
        """回执必须绑定同一引擎/规则/配置/测试集合身份；否则"之前跑过"不能当作现状。"""

        if (
            self.engine_source_digest != snapshot.source_digest
            or self.engine_commit_sha != snapshot.commit_sha
        ):
            return False
        if (
            validator_bundle_digest
            and self.validator_bundle_digest
            and self.validator_bundle_digest != validator_bundle_digest
        ):
            return False
        if (
            effective_config_digest
            and self.effective_config_digest != effective_config_digest
        ):
            return False
        if required_test_plan and self.test_plan_ids:
            # 声明了测试集合就必须覆盖必测集合；旧格式回执（完全没有该字段）由准入
            # 侧单独记为"身份未绑定"，而不是伪装成"集合不完整"。
            covered = set(self.test_plan_ids)
            if not set(required_test_plan).issubset(covered):
                return False
        return True

    def missing_test_plan_ids(
        self, required_test_plan: tuple[str, ...] = REQUIRED_OFFLINE_TEST_PLAN
    ) -> tuple[str, ...]:
        covered = set(self.test_plan_ids)
        return tuple(item for item in required_test_plan if item not in covered)


def _parse_pytest_summary(output: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "error": 0, "deselected": 0}
    for line in reversed(str(output or "").splitlines()):
        if not _SUMMARY_PATTERN.search(line):
            continue
        for value, label in _SUMMARY_PATTERN.findall(line):
            key = {"errors": "error", "error": "error"}.get(label, label)
            counts[key] = max(counts[key], int(value))
        break
    return counts


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def build_offline_suite_receipt(
    *,
    command: str,
    exit_code: int,
    output: str = "",
    engine_snapshot: EngineSourceSnapshot | None = None,
    validator_bundle_digest: str | None = None,
    effective_config_digest: str = "",
    test_plan_ids: Sequence[str] = REQUIRED_OFFLINE_TEST_PLAN,
) -> OfflineSuiteReceiptV1:
    """从一次离线全链运行的实际结果构造回执（结果来自真实输出，不接受声明值）。"""

    snapshot = engine_snapshot or capture_engine_source_snapshot()
    if validator_bundle_digest is None:
        # §14.4：回执默认绑定**当前**验收规则身份（而不是留空）。
        validator_bundle_digest = capture_validator_bundle_snapshot().digest
    counts = _parse_pytest_summary(output)
    plan_ids = tuple(
        dict.fromkeys(str(item).strip() for item in test_plan_ids if str(item).strip())
    )
    return OfflineSuiteReceiptV1(
        passed=bool(
            int(exit_code) == 0
            and counts["failed"] == 0
            and counts["error"] == 0
            and counts["passed"] > 0
        ),
        exit_code=int(exit_code),
        passed_count=counts["passed"],
        failed_count=counts["failed"],
        error_count=counts["error"],
        deselected_count=counts["deselected"],
        command=str(command),
        engine_commit_sha=snapshot.commit_sha,
        engine_source_digest=snapshot.source_digest,
        worktree_dirty_entry_count=len(snapshot.entries),
        validator_bundle_digest=str(validator_bundle_digest or ""),
        effective_config_digest=str(effective_config_digest or ""),
        test_plan_ids=plan_ids,
        test_plan_digest=_digest_text("\n".join(sorted(plan_ids))),
        output_digest=_digest_text(output),
    )


def write_offline_suite_receipt(
    path: str | Path, receipt: OfflineSuiteReceiptV1
) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    temp.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(temp, target)
    return target


def read_offline_suite_receipt(path: str | Path) -> OfflineSuiteReceiptV1:
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    return OfflineSuiteReceiptV1.model_validate(payload)


class LiveAdmissionGateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    passed: bool
    detail: str = ""
    #: 审计 §G.5：offline-ready 与 live-ready 的门是**两组**，不能混为一谈。
    scope: str = "offline"


class RuntimeProbeSummaryV1(BaseModel):
    """§14.1 要求的部署侧探测结果摘要（由调用方抓取后传入，本模块不联网）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    health_ok: bool = False
    served_models: tuple[str, ...] = ()
    runtime_note: str = ""

    def serves(self, model: str) -> bool:
        wanted = str(model or "").strip()
        if not wanted:
            return False
        if wanted in self.served_models:
            return True
        # 部署端常带版本后缀；只接受"服务名以配置名开头"这一种放宽。
        return any(name.startswith(wanted + ":") for name in self.served_models)


def parse_runtime_probe(
    *,
    models_payload: Mapping[str, Any] | None = None,
    health_payload: Mapping[str, Any] | None = None,
) -> RuntimeProbeSummaryV1:
    """把 ``/v1/models`` 与 ``/health`` 的响应体解析成可比较的模型身份摘要。"""

    served: list[str] = []
    if isinstance(models_payload, Mapping):
        for entry in models_payload.get("data") or ():
            if isinstance(entry, Mapping):
                name = str(entry.get("id") or "").strip()
                if name:
                    served.append(name)
        if not served:
            single = str(models_payload.get("model") or "").strip()
            if single:
                served.append(single)
    health_ok = False
    note = ""
    if isinstance(health_payload, Mapping):
        status = str(health_payload.get("status") or "").strip().casefold()
        health_ok = status in {"ok", "healthy", "ready", "up"} or bool(
            health_payload.get("healthy")
        )
        note = status
    return RuntimeProbeSummaryV1(
        health_ok=health_ok,
        served_models=tuple(sorted(dict.fromkeys(served))),
        runtime_note=note,
    )


class LiveAdmissionReportV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    #: ``ready`` 保留原义：**offline-ready**（不证明当前服务可用）。
    ready: bool = False
    #: 审计 §G.5：live-ready 额外要求部署探测、角色预算、输出上限与停止条件。
    live_ready: bool = False
    readiness_scope: str = "not_ready"
    scope_note: str = (
        "offline-ready 只证明离线全链与身份/账本/页面检查通过，"
        "不证明当前服务可用；live-ready 需要本轮部署探测与预算声明。"
    )
    live_blockers: tuple[str, ...] = ()
    out_root: str
    run_open_mode: str = "auto"
    execution_id: str = ""
    execution_identity_digest: str = ""
    effective_config_digest: str = ""
    engine: dict[str, Any] = Field(default_factory=dict)
    run_open_decision: dict[str, Any] = Field(default_factory=dict)
    gates: tuple[LiveAdmissionGateV1, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    policy: dict[str, Any] = Field(default_factory=dict)

    def render(self) -> str:
        lines = [
            f"LIVE ADMISSION  {'READY' if self.ready else 'NOT READY'}",
            f"READINESS SCOPE {self.readiness_scope}"
            + ("  (live-ready)" if self.live_ready else ""),
            f"OUT ROOT        {self.out_root}",
            f"RUN OPEN MODE   {self.run_open_mode}",
            f"EXECUTION ID    {self.execution_id or '(unresolved)'}",
            f"IDENTITY DIGEST {self.execution_identity_digest or '(unresolved)'}",
            f"EFFECTIVE CONFIG {self.effective_config_digest or '(unresolved)'}",
        ]
        for gate in self.gates:
            lines.append(
                f"{'PASS' if gate.passed else 'FAIL':4s}  {gate.name:26s} {gate.detail}"
            )
        for blocker in self.blockers:
            lines.append(f"BLOCKER         {blocker}")
        for blocker in self.live_blockers:
            lines.append(f"LIVE BLOCKER    {blocker}")
        if self.scope_note:
            lines.append(f"SCOPE           {self.scope_note}")
        for warning in self.warnings:
            lines.append(f"WARNING         {warning}")
        return "\n".join(lines)


def _material_state(path: str | Path | None) -> tuple[bool, str]:
    if path is None:
        return False, "missing"
    candidate = Path(path).expanduser()
    try:
        if not candidate.is_file():
            return False, "missing"
        size = candidate.stat().st_size
    except OSError as exc:  # noqa: BLE001 - 预检报告失败而不是抛穿
        return False, f"unreadable:{type(exc).__name__}"
    return (size > 0), ("ok" if size > 0 else "empty")


def preflight_live_admission(
    out_root: str | Path,
    *,
    repo_path: str | Path,
    author_intent_path: str | Path | None = None,
    claims_path: str | Path | None = None,
    llm_config: Any | None = None,
    run_open_mode: str = "auto",
    model_context_tokens: int = 0,
    max_writer_calls: int = 0,
    max_total_input_tokens: int = 0,
    transport_policy: TransportRetryPolicyV1 | None = None,
    engine_snapshot: EngineSourceSnapshot | None = None,
    validator_bundle: ValidatorBundleSnapshot | None = None,
    narrative_plan_mode: Any | None = None,
    authoring_context_mode: Any | None = None,
    runtime_probe: RuntimeProbeSummaryV1 | Mapping[str, Any] | None = None,
    offline_suite_receipt: OfflineSuiteReceiptV1 | Mapping[str, Any] | str | Path | None = None,
    research_import_path: str | Path | None = None,
    # 审计 §G.5：live-ready 需要的部署侧声明（offline-ready 不要求）。
    role_call_budgets: Mapping[str, int] | None = None,
    role_output_limits: Mapping[str, int] | None = None,
    stop_conditions: Sequence[str] = (),
) -> LiveAdmissionReportV1:
    """逐条检查 §14.1 的 live 准入条件（只读、零模型调用）。"""

    root = Path(out_root).expanduser().resolve()
    mode = str(run_open_mode or "auto").strip().casefold() or "auto"
    policy = transport_policy or load_transport_retry_policy()
    probe = (
        runtime_probe
        if isinstance(runtime_probe, RuntimeProbeSummaryV1)
        else (parse_runtime_probe(**dict(runtime_probe)) if runtime_probe else None)
    )
    receipt: OfflineSuiteReceiptV1 | None
    if isinstance(offline_suite_receipt, OfflineSuiteReceiptV1):
        receipt = offline_suite_receipt
    elif isinstance(offline_suite_receipt, (str, Path)):
        receipt = (
            read_offline_suite_receipt(offline_suite_receipt)
            if Path(offline_suite_receipt).expanduser().is_file()
            else None
        )
    elif isinstance(offline_suite_receipt, Mapping):
        receipt = OfflineSuiteReceiptV1.model_validate(dict(offline_suite_receipt))
    else:
        receipt = None
    gates: list[LiveAdmissionGateV1] = []
    blockers: list[str] = []
    live_blockers: list[str] = []
    warnings: list[str] = []

    snapshot = engine_snapshot or capture_engine_source_snapshot()
    engine_ok = snapshot.is_usable
    gates.append(
        LiveAdmissionGateV1(
            name="engine_identity",
            passed=engine_ok,
            detail=(
                f"commit={snapshot.commit_sha[:12]} source={snapshot.source_digest[:19]} "
                f"dirty={len(snapshot.entries)}"
                if engine_ok
                else f"unusable:{snapshot.failure_code or 'engine_commit_unknown'}"
            ),
        )
    )
    if not engine_ok:
        blockers.append("engine_identity_unavailable")
    elif snapshot.entries:
        warnings.append(
            f"engine worktree dirty: {len(snapshot.entries)} file(s) folded into source digest"
        )
    if snapshot.unstable:
        warnings.append("engine source snapshot marked unstable (concurrent writes observed)")

    # 目标身份必须是**内容**身份（审计 F02）：commit/porcelain 只作诊断。
    try:
        target = capture_target_identity(repo_path)
        target_ok = target.is_usable
        target_detail = (
            f"commit={target.commit_sha[:12]} snapshot={target.source_snapshot_digest[:19]} "
            f"files={target.file_count}"
            if target_ok
            else f"unusable:{target.failure_code}"
        )
    except Exception as exc:  # noqa: BLE001 - 预检报告失败而不是抛穿
        target_ok = False
        target_detail = f"{type(exc).__name__}: {exc}"
    gates.append(LiveAdmissionGateV1(name="target_identity", passed=target_ok, detail=target_detail))
    if not target_ok:
        blockers.append("target_identity_unresolved")

    # 验收规则来源不可用 → 非空 digest 也不等于可用 bundle（审计 §A.1.5）。
    bundle = validator_bundle or capture_validator_bundle_snapshot()
    gates.append(
        LiveAdmissionGateV1(
            name="validator_bundle_identity",
            passed=bundle.is_usable,
            detail=(
                f"{len(bundle.entries)} source(s) {bundle.digest[:19]}"
                if bundle.is_usable
                else f"unusable:{bundle.failure_code} missing={list(bundle.missing)}"
            ),
        )
    )
    if not bundle.is_usable:
        blockers.append("validator_bundle_unavailable")

    # §14.1 "目标仓库和作者材料身份一致"：作者意图是必需输入；claims 在产品入口
    # 是可选的，未声明只告警，**声明了却缺失/为空**才阻断（不静默降级身份）。
    intent_ok, intent_state = _material_state(author_intent_path)
    claims_specified = claims_path is not None and str(claims_path).strip() != ""
    if claims_specified:
        claims_ok, claims_state = _material_state(claims_path)
    else:
        claims_ok, claims_state = True, "not supplied"
    materials_ok = intent_ok and claims_ok
    gates.append(
        LiveAdmissionGateV1(
            name="author_materials",
            passed=materials_ok,
            detail=f"author_intent={intent_state} claims={claims_state}",
        )
    )
    if not materials_ok:
        blockers.append("author_material_missing")
    if not claims_specified:
        warnings.append("claims not supplied: identity records an absent claims input")

    provider = str(getattr(llm_config, "provider", "") or "").strip()
    model = str(getattr(llm_config, "model", "") or "").strip()
    model_ok = bool(provider and model)
    gates.append(
        LiveAdmissionGateV1(
            name="model_profile_identity",
            passed=model_ok,
            detail=f"provider={provider or '(unset)'} model={model or '(unset)'}",
        )
    )
    if not model_ok:
        blockers.append("model_identity_unresolved")

    budget_ok = (
        int(model_context_tokens) > 0
        and int(max_writer_calls) > 0
        and int(max_total_input_tokens) > 0
    )
    gates.append(
        LiveAdmissionGateV1(
            name="declared_budget",
            passed=budget_ok,
            detail=(
                f"context={int(model_context_tokens)} writer_calls={int(max_writer_calls)} "
                f"input_tokens={int(max_total_input_tokens)}"
            ),
        )
    )
    if not budget_ok:
        blockers.append("run_budget_not_declared")

    transport_ok = (
        int(policy.max_transport_retries) >= 0
        and int(policy.unknown_outcome_retries) <= 0
        and bool(policy.counts_against_call_budget)
    )
    gates.append(
        LiveAdmissionGateV1(
            name="transport_policy",
            passed=transport_ok,
            detail=(
                f"max_retries={int(policy.max_transport_retries)} "
                f"unknown_retries={int(policy.unknown_outcome_retries)} "
                f"counts_against_budget={bool(policy.counts_against_call_budget)}"
            ),
        )
    )
    if not transport_ok:
        blockers.append("transport_policy_unbounded")

    # §C.2：段数上限是辅助安全限。0=关闭只能是**显式实验配置**；环境变量不能悄悄改契约，
    # 因此关闭上限而未显式声明实验时，live 准入直接阻断。
    from code2paper.agentic.unified_context_compiler import (
        semantic_paragraph_limit_policy,
    )

    paragraph_policy = semantic_paragraph_limit_policy()
    paragraph_ok = not (
        paragraph_policy["disabled"] and not paragraph_policy["experiment_acknowledged"]
    ) and bool(paragraph_policy["valid"])
    gates.append(
        LiveAdmissionGateV1(
            name="semantic_paragraph_limit_policy",
            passed=paragraph_ok,
            detail=(
                f"value={paragraph_policy['value']} source={paragraph_policy['source']} "
                f"experiment={paragraph_policy['experiment_acknowledged']}"
            ),
        )
    )
    if not paragraph_ok:
        blockers.append("semantic_paragraph_limit_policy_unacknowledged")

    if receipt is None:
        gates.append(
            LiveAdmissionGateV1(
                name="offline_suite_receipt",
                passed=False,
                detail="no receipt supplied",
            )
        )
        blockers.append("offline_suite_receipt_missing")
    else:
        receipt_fresh = receipt.matches(
            snapshot,
            validator_bundle_digest=bundle.digest if bundle.is_usable else "",
            effective_config_digest="",
            required_test_plan=REQUIRED_OFFLINE_TEST_PLAN,
        )
        missing_plan = (
            receipt.missing_test_plan_ids() if receipt.test_plan_ids else ()
        )
        receipt_ok = bool(receipt.passed and receipt_fresh and not missing_plan)
        gates.append(
            LiveAdmissionGateV1(
                name="offline_suite_receipt",
                passed=receipt_ok,
                detail=(
                    f"passed={receipt.passed_count} failed={receipt.failed_count} "
                    f"exit={receipt.exit_code} identities_bound={receipt_fresh} "
                    f"test_plan={len(receipt.test_plan_ids)}/{len(REQUIRED_OFFLINE_TEST_PLAN)}"
                ),
            )
        )
        if not receipt.passed:
            blockers.append("offline_suite_not_passed")
        elif missing_plan:
            # §14.4：某条命令有 passed 不代表必测集合跑完。
            blockers.append(
                "offline_suite_test_plan_incomplete:"
                + ",".join(missing_plan[:4])
            )
        elif not receipt_fresh:
            blockers.append("offline_suite_receipt_stale")
        if not receipt.validator_bundle_digest or not receipt.test_plan_ids:
            # 旧格式回执没有绑定规则/测试集合身份：offline 只警告，live 直接阻断。
            warnings.append(
                "offline suite receipt does not bind validator/test-plan identity"
            )
            live_blockers.append("offline_suite_receipt_identities_unbound")

    if probe is None:
        # §G.5：offline-ready 允许没有部署探测，但 live-ready 不行——两者必须分开报。
        warnings.append(
            "runtime probe not supplied: offline-ready only; live-ready requires "
            "/health and /v1/models from this round"
        )
        live_blockers.append("runtime_probe_missing")
    else:
        serves_ok = bool(probe.health_ok and probe.serves(model))
        gates.append(
            LiveAdmissionGateV1(
                name="runtime_model_identity",
                passed=serves_ok,
                detail=(
                    f"health={'ok' if probe.health_ok else 'not-ok'} "
                    f"served={','.join(probe.served_models) or '(none)'}"
                ),
            )
        )
        if not serves_ok:
            blockers.append("runtime_model_identity_mismatch")
            live_blockers.append("runtime_model_identity_mismatch")

    # L2（fork_authoring）必须导入"已校验研究证据"：预检与启动器使用同一
    # verify_research_import，因此预检给出的 execution_id 与随后真实 run 一致。
    import_verifiable, import_digest, import_detail = (True, "", "not applicable")
    if mode == "fork_authoring":
        import_verifiable, import_digest, import_detail = verify_research_import(
            research_import_path
        )
        gates.append(
            LiveAdmissionGateV1(
                name="research_import",
                passed=bool(import_verifiable),
                detail=str(import_detail),
            )
        )
        if not import_verifiable:
            blockers.append(RESEARCH_IMPORT_UNVERIFIABLE)

    try:
        identity = build_run_open_identity(
            repo_path=repo_path,
            author_intent_path=author_intent_path,
            claims_path=claims_path,
            llm_config=llm_config,
            run_open_mode=mode,
            engine_snapshot=snapshot,
            validator_bundle=bundle,
            research_import_digest=import_digest,
            narrative_plan_mode=narrative_plan_mode,
            authoring_context_mode=authoring_context_mode,
            require_usable_inputs=False,
        )
    except ValueError as exc:
        # 有效配置非法（例如未知 narrative mode）→ 预检直接判不可进入。
        identity = None
        gates.append(
            LiveAdmissionGateV1(
                name="effective_config_identity",
                passed=False,
                detail=str(exc)[:160],
            )
        )
        blockers.append(str(exc).split(":", 1)[0] or "effective_config_invalid")
    decision = (
        validate_run_open(
            root,
            mode,
            identity,
            research_import_verifiable=import_verifiable,
        )
        if identity is not None
        else RunOpenDecision(
            allowed=False,
            code="effective_config_invalid",
            requested_mode=mode,
            effective_mode=mode,
            allowed_next_action="fix_the_requested_effective_configuration",
            detail="有效配置身份无法构造（见 effective_config_identity）",
        )
    )
    gates.append(
        LiveAdmissionGateV1(
            name="run_open_decision",
            passed=bool(decision.allowed),
            detail=f"{decision.code} -> {decision.effective_mode} ({decision.detail})",
        )
    )
    if not decision.allowed:
        blockers.append(f"run_open_rejected:{decision.code}")
    if decision.exhausted_invocations:
        warnings.append(
            "exhausted invocation(s) present: " + ", ".join(decision.exhausted_invocations)
        )

    # 审计 §G.5：live-ready 必须显式声明各角色调用预算、输出上限与停止条件；
    # 这些门属于 live scope，不阻断 offline-ready。
    required_roles = ("formalizer", "writer", "realizer", "binder")
    budgets = {
        str(role): int((role_call_budgets or {}).get(role, 0) or 0)
        for role in required_roles
    }
    budgets_ok = all(value > 0 for value in budgets.values())
    gates.append(
        LiveAdmissionGateV1(
            name="role_call_budgets",
            passed=budgets_ok,
            scope="live",
            detail=", ".join(f"{role}={value}" for role, value in budgets.items()),
        )
    )
    if not budgets_ok:
        live_blockers.append("role_call_budgets_not_declared")

    output_limits = {
        str(role): int((role_output_limits or {}).get(role, 0) or 0)
        for role in required_roles
    }
    limits_ok = all(value > 0 for value in output_limits.values())
    gates.append(
        LiveAdmissionGateV1(
            name="output_limits",
            passed=limits_ok,
            scope="live",
            detail=", ".join(
                f"{role}={value}" for role, value in output_limits.items()
            ),
        )
    )
    if not limits_ok:
        live_blockers.append("output_limits_not_declared")

    stops = tuple(
        dict.fromkeys(str(item).strip() for item in stop_conditions if str(item).strip())
    )
    gates.append(
        LiveAdmissionGateV1(
            name="stop_conditions",
            passed=bool(stops),
            scope="live",
            detail="; ".join(stops) or "none declared",
        )
    )
    if not stops:
        live_blockers.append("stop_conditions_not_declared")

    if (root / "artifacts").is_dir():
        report = run_authoring_doctor(root)
        doctor_ok = not report.critical_blockers
        gates.append(
            LiveAdmissionGateV1(
                name="doctor_critical_clear",
                passed=doctor_ok,
                detail=", ".join(report.critical_blockers) or "clear",
            )
        )
        if not doctor_ok:
            blockers.append("doctor_critical_blocker")
        if report.blocked_pages:
            warnings.append(f"{len(report.blocked_pages)} blocked page(s) reported by doctor")
    elif decision.allowed and mode in {"new", "fork_authoring"}:
        warnings.append("doctor skipped: fresh run directory")

    offline_ready = not blockers
    live_ready = offline_ready and not live_blockers
    scope = "live_ready" if live_ready else "offline_ready" if offline_ready else "not_ready"
    return LiveAdmissionReportV1(
        ready=offline_ready,
        live_ready=live_ready,
        readiness_scope=scope,
        live_blockers=tuple(dict.fromkeys(live_blockers)),
        out_root=str(root),
        run_open_mode=mode,
        execution_id=(identity.execution_id if identity is not None else ""),
        execution_identity_digest=(identity.content_digest if identity is not None else ""),
        engine=snapshot.as_diagnostics(),
        run_open_decision=decision.as_diagnostics(),
        gates=tuple(gates),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(warnings),
        policy={
            "model_context_tokens": int(model_context_tokens),
            "max_writer_calls": int(max_writer_calls),
            "max_total_input_tokens": int(max_total_input_tokens),
            "transport": policy.as_diagnostics(),
            "semantic_paragraph_limit": paragraph_policy,
            "readiness_scope": scope,
            "role_call_budgets": budgets,
            "role_output_limits": output_limits,
            "stop_conditions": list(stops),
            "offline_suite_receipt": (
                receipt.model_dump(mode="json") if receipt is not None else None
            ),
        },
    )
