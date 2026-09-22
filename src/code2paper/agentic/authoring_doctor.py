"""方案 §15：authoring doctor —— 只读诊断，替代"读几十个 JSON 猜状态"。

输入一个 out_root，输出：执行身份（引擎/目标/输入是否分离）、各阶段状态、逐页内容预算
余量、首个根因与下游阻断、空语义段落数、detail/atom 责任不一致数。全部只读，不改写
任何产物，也不发起模型调用。

设计目标是让 live 准入（§14.1 的"doctor 无 critical 阻断"）与事故复盘都能一条命令完成。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.authoring_artifact_index import (
    ArtifactIndexError,
    build_artifact_index,
    resolve_artifact,
)
from code2paper.agentic.writer_attempt_ledger import (
    read_invocation_ledger_state,
    reduce_invocation_recovery,
)

#: 阶段 → 判据产物（logical_role:phase）
_PHASE_ROLES: tuple[tuple[str, str], ...] = (
    ("formalizer", "formula_packages:formalizer"),
    ("writer", "writer_aggregate_receipt:writer"),
    ("realizer", "realizer_receipts:realizer"),
    ("binder", "binder_receipts:binder"),
)


class DoctorPageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invocation_id: str
    section_id: str = ""
    accepted: bool = False
    content_attempts_used: int = 0
    content_attempt_limit: int = 0
    exhausted: bool = False
    last_provider_attempt: int = 0
    rejected_before_send_events: tuple[int, ...] = ()
    failure_codes: tuple[str, ...] = ()
    #: 审计 §B.4：doctor 必须展示**同一个**归约结论，而不是各自解释字符串。
    recovery_state: str = ""
    primary_cause: str = ""
    unknown_reservation_attempts: tuple[int, ...] = ()


class AuthoringDoctorReportV1(BaseModel):
    """§15.1 的诊断样式（结构化版本，便于测试与消费）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    out_root: str
    execution_identity: str = "legacy identity; engine fingerprint unavailable"
    engine_fingerprint: str = ""
    target_identity: str = ""
    phases: dict[str, str] = Field(default_factory=dict)
    active_artifacts: dict[str, str] = Field(default_factory=dict)
    page_count: int = 0
    accepted_page_count: int = 0
    blocked_pages: tuple[DoctorPageV1, ...] = ()
    first_root_cause: str = ""
    downstream_not_run: tuple[str, ...] = ()
    empty_semantic_paragraph_count: int = 0
    binder_owned_writer_target_count: int = 0
    critical_blockers: tuple[str, ...] = ()
    next_action: str = ""

    def render(self) -> str:
        lines = [
            f"EXECUTION       {self.execution_identity}",
            f"TARGET          {self.target_identity or 'unknown'}",
        ]
        if self.engine_fingerprint:
            lines.append(f"ENGINE          {self.engine_fingerprint}")
        for phase, status in sorted(self.phases.items()):
            lines.append(f"{phase.upper():15s} {status}")
        lines.append(
            f"PAGES           {self.accepted_page_count}/{self.page_count} accepted"
        )
        for page in self.blocked_pages:
            lines.append(
                f"BLOCKED         {page.invocation_id} "
                f"({page.content_attempts_used}/{page.content_attempt_limit} content attempts)"
            )
        lines.append(
            f"INTENT SURFACE  {self.empty_semantic_paragraph_count} paragraph(s) lack per-paragraph material"
        )
        lines.append(
            f"WITNESS OWNER   {self.binder_owned_writer_target_count} Binder-owned target(s) still shown to Writer"
        )
        if self.first_root_cause:
            lines.append(f"FIRST CAUSE     {self.first_root_cause}")
        if self.downstream_not_run:
            lines.append(f"DOWNSTREAM      not run: {', '.join(self.downstream_not_run)}")
        lines.append(f"NEXT ACTION     {self.next_action or 'none'}")
        return "\n".join(lines)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _phase_status(index: Any, out_root: Path, role: str, phase: str) -> str:
    try:
        path = resolve_artifact(index, role, phase, out_root=out_root)
    except ArtifactIndexError:
        return "not produced"
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return "unreadable"
    if role == "writer_aggregate_receipt":
        sections = payload.get("completed_section_ids") or ()
        required = payload.get("required_section_ids") or ()
        complete = bool(payload.get("all_required_sections_complete"))
        return f"{len(sections)}/{len(required)} sections complete" + (
            "" if complete else "; incomplete"
        )
    receipts = payload.get("receipts") or ()
    failures = payload.get("failure_codes") or ()
    if failures:
        return f"{len(receipts)} receipt(s); failures={list(failures)[:2]}"
    return f"{len(receipts)} receipt(s)"


def run_authoring_doctor(out_root: str | Path) -> AuthoringDoctorReportV1:
    """只读诊断一个 run 目录；不写文件、不发请求。"""

    root = Path(out_root).expanduser().resolve()
    index = build_artifact_index(root)

    execution = index.entry_for("authoring_execution_identity", "research")
    legacy = index.entry_for("run_identity", "research")
    if execution is not None and execution.status not in {"missing"}:
        identity_text = f"AuthoringExecutionIdentityV2 (revision {index.index_revision})"
        engine = f"engine {execution.semantic_digest or execution.file_bytes_digest}"
    else:
        identity_text = "legacy identity; engine fingerprint unavailable"
        engine = ""

    target = ""
    snapshot_path = root / "artifacts" / "repo_snapshot_v2.json"
    snapshot = _read_json(snapshot_path)
    if isinstance(snapshot, dict):
        target = (
            f"{Path(str(snapshot.get('project_root') or '')).name} "
            f"@ {str(snapshot.get('git_commit') or '')[:12]}"
        )
    elif legacy is not None and legacy.semantic_digest:
        target = f"legacy run identity {legacy.semantic_digest[:19]}"

    phases = {name: _phase_status(index, root, role, phase) for name, role, phase in (
        (name, role.split(":")[0], role.split(":")[1]) for name, role in _PHASE_ROLES
    )}

    plan_path = root / "artifacts" / "06_authoring" / "consumer_invocation_plan_v1.2.json"
    plan = _read_json(plan_path)
    invocations = (plan or {}).get("invocations") or () if isinstance(plan, dict) else ()

    # resume 复用页不会产生新的内容验收记录，因此"已接受"还要看分节回执。
    receipt_completed: set[str] = set()
    receipts_payload = _read_json(
        root / "artifacts" / "06_authoring" / "writer_section_receipts_v2.json"
    )
    if isinstance(receipts_payload, dict):
        for receipt in receipts_payload.get("receipts") or ():
            for invocation_id in (receipt or {}).get("completed_invocation_ids") or ():
                receipt_completed.add(str(invocation_id))

    pages: list[DoctorPageV1] = []
    blocked: list[DoctorPageV1] = []
    for invocation in invocations:
        invocation_id = str((invocation or {}).get("invocation_id") or "")
        if not invocation_id:
            continue
        state = read_invocation_ledger_state(root, invocation_id)
        recovery = reduce_invocation_recovery(root, invocation_id)
        limit = state.content_attempt_limit
        record = DoctorPageV1(
            invocation_id=invocation_id,
            section_id=str((invocation or {}).get("section_id") or ""),
            accepted=bool(state.accepted or invocation_id in receipt_completed),
            content_attempts_used=state.counters.content_attempt_count,
            content_attempt_limit=limit,
            recovery_state=recovery.state,
            primary_cause=recovery.primary_cause,
            unknown_reservation_attempts=recovery.unknown_reservation_attempts,
            exhausted=recovery.state == "content_budget_exhausted",
            last_provider_attempt=state.last_provider_attempt,
            rejected_before_send_events=state.counters.rejected_before_send_events,
            failure_codes=state.last_content_failure_codes,
        )
        pages.append(record)
        if record.exhausted:
            blocked.append(record)

    paragraph_stats = _paragraph_surface_stats(root)
    first_cause = ""
    downstream: tuple[str, ...] = ()
    next_action = "run"
    writer_result = _read_json(
        root / "artifacts" / "06_authoring" / "publication_writer_result_v1.json"
    )
    if isinstance(writer_result, dict) and str(writer_result.get("status")) == "blocked":
        blocked_reason = str(writer_result.get("blocked_reason") or "")
        first_cause = blocked_reason
        if blocked_reason.startswith("writer_phase_boundary_blocked"):
            parts = dict(
                item.split("=", 1) for item in blocked_reason.split(":") if "=" in item
            )
            first_cause = str(parts.get("primary_cause") or blocked_reason)
            downstream = tuple(
                item
                for item in str(parts.get("downstream_not_run") or "").split(",")
                if item
            )
        next_action = "read-only diagnosis or explicit authoring fork"
    elif blocked:
        first_cause = "resume_exhausted_invocation"
        next_action = "fork_authoring_with_new_contract"

    critical: list[str] = []
    if blocked:
        critical.append("resume_exhausted_invocation")
    if paragraph_stats["empty"] > 0:
        critical.append("intent_surface_gaps")
    if paragraph_stats["binder_owned_targets"] > 0:
        critical.append("writer_binder_ownership_inconsistent")
    has_content = bool(pages or writer_result or any(
        status not in {"not produced", "unreadable"} for status in phases.values()
    ))
    if not engine and identity_text.startswith("legacy") and has_content:
        critical.append("engine_fingerprint_unavailable")

    return AuthoringDoctorReportV1(
        out_root=str(root),
        execution_identity=identity_text,
        engine_fingerprint=engine,
        target_identity=target,
        phases=phases,
        active_artifacts={key: value for key, value in index.active.items() if value},
        page_count=len(pages),
        accepted_page_count=sum(1 for page in pages if page.accepted),
        blocked_pages=tuple(blocked),
        first_root_cause=first_cause,
        downstream_not_run=downstream,
        empty_semantic_paragraph_count=paragraph_stats["empty"],
        binder_owned_writer_target_count=paragraph_stats["binder_owned_targets"],
        critical_blockers=tuple(critical),
        next_action=next_action,
    )


def _paragraph_surface_stats(root: Path) -> dict[str, int]:
    """空语义段落数与"Binder 责任仍暴露给 Writer"的目标数（§15.1 的两行）。"""

    candidates = (
        "narrative_plan_v3.revision.2.json",
        "narrative_plan_v3.json",
    )
    for name in candidates:
        payload = _read_json(root / "artifacts" / "06_authoring" / name)
        if not isinstance(payload, dict):
            continue
        empty = 0
        binder_owned = 0
        for section in payload.get("sections") or ():
            for paragraph in (section or {}).get("paragraphs") or ():
                kind = str((paragraph or {}).get("paragraph_kind") or "")
                targets = ((paragraph or {}).get("witness_contract") or {}).get(
                    "targets"
                ) or ()
                required_atoms = [
                    target
                    for target in targets
                    if str((target or {}).get("target_kind") or "") == "atom"
                    and bool((target or {}).get("required", True))
                ]
                binder_owned += len(required_atoms)
                has_material = bool(
                    (paragraph or {}).get("mechanism_id")
                    or (paragraph or {}).get("required_detail_ids")
                    or (paragraph or {}).get("optional_detail_ids")
                    or (paragraph or {}).get("formula_package_ids")
                    or required_atoms
                )
                if kind:
                    if kind not in {"grounded_content", "author_specification"}:
                        empty += 1
                elif not has_material:
                    empty += 1
        return {"empty": empty, "binder_owned_targets": binder_owned}
    return {"empty": 0, "binder_owned_targets": 0}


__all__ = [
    "AuthoringDoctorReportV1",
    "DoctorPageV1",
    "run_authoring_doctor",
]
