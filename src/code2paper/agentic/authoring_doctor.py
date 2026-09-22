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
    EmptyArtifactDispositionV1,
    assess_empty_artifact,
    build_artifact_index,
    load_published_artifact_index,
    resolve_artifact,
)
from code2paper.agentic.authoring_artifact_publication import (
    PublicationTransactionV1,
    incomplete_publications,
    scan_orphan_temp_files,
    scan_publication_transactions,
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
    #: 审计 §F.3：空产物是否合法、为什么为空、哪些任务 not_applicable。
    empty_artifacts: tuple[EmptyArtifactDispositionV1, ...] = ()
    #: 审计 §F.5：本次诊断消费的是已发布 revision 还是临时扫描。
    artifact_index_source: str = ""
    #: 审计 §F.4：发布事务 journal（未完成的发布必须可见）。
    publications: tuple[PublicationTransactionV1, ...] = ()
    orphan_publication_files: tuple[str, ...] = ()
    critical_blockers: tuple[str, ...] = ()
    next_action: str = ""

    def render(self) -> str:
        lines = [
            f"EXECUTION       {self.execution_identity}",
            f"TARGET          {self.target_identity or 'unknown'}",
        ]
        if self.engine_fingerprint:
            lines.append(f"ENGINE          {self.engine_fingerprint}")
        if self.artifact_index_source:
            lines.append(f"INDEX SOURCE    {self.artifact_index_source}")
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
        # 审计 §F.3：空产物（尤其"该阶段需要单元却为空"）必须一条命令就能看见。
        for disposition in self.empty_artifacts:
            state = "allowed" if disposition.allowed else "BLOCKED"
            not_applicable = (
                f"; not_applicable={','.join(disposition.declared_not_applicable_task_ids)}"
                if disposition.declared_not_applicable_task_ids
                else ""
            )
            lines.append(
                f"EMPTY ARTIFACT  {disposition.logical_role}:{disposition.phase} "
                f"{state} ({disposition.reason}; required_units="
                f"{disposition.required_units}){not_applicable}"
            )
        for publication in self.publications:
            if publication.state == "complete":
                continue
            lines.append(
                f"PUBLICATION     {publication.logical_role}:{publication.phase} "
                f"{publication.state}"
                + (
                    f" ({','.join(publication.failures)})"
                    if publication.failures
                    else ""
                )
            )
        for orphan in self.orphan_publication_files:
            lines.append(f"ORPHAN TEMP     {orphan}")
        for blocker in self.critical_blockers:
            lines.append(f"CRITICAL        {blocker}")
        if self.first_root_cause:
            lines.append(f"FIRST CAUSE     {self.first_root_cause}")
        if self.downstream_not_run:
            lines.append(f"DOWNSTREAM      not run: {', '.join(self.downstream_not_run)}")
        lines.append(f"NEXT ACTION     {self.next_action or 'none'}")
        return "\n".join(lines)


def load_run_summary_validated(out_root: str | Path) -> tuple[Any, str]:
    """按 §F.5 读取 run summary：先解析索引（优先已发布 revision），再验证字节。

    返回 ``(payload, blocker)``；验证失败时 payload 为 None 并给出 typed blocker，
    **不退回**按固定文件名再读一份未验证内容。
    """

    from code2paper.agentic.authoring_artifact_index import (
        ArtifactIndexError,
        build_artifact_index,
        load_published_artifact_index,
        read_artifact_validated,
    )

    root = Path(out_root).expanduser().resolve()
    try:
        index = load_published_artifact_index(root)
    except ArtifactIndexError:
        index = build_artifact_index(root)
    try:
        read = read_artifact_validated(
            index, "run_summary", "terminal", out_root=root
        )
    except ArtifactIndexError as exc:
        return None, f"artifact_read_blocked:run_summary:terminal:{exc}"
    return read.payload, ""


def _read_json(path: Path) -> Any:
    """legacy 归档读取（未经索引验证）；受索引管理的产物走 _validated_payload。"""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _validated_payload(
    index: Any,
    out_root: Path,
    role: str,
    phase: str,
    *,
    required_units: int | None = None,
) -> tuple[Any, str]:
    """按 §F.5 读取受索引管理的产物：**使用前**验证字节与摘要。

    返回 ``(payload, blocker)``：读不到或验证失败时 payload 为 ``None`` 并把 typed
    blocker 交给调用方——绝不退回到"按无后缀文件名再读一份"的隐式 fallback。
    """

    from code2paper.agentic.authoring_artifact_index import read_artifact_validated

    entry = index.entry_for(role, phase)
    if entry is None or entry.status == "missing":
        # 该阶段本来就没有产物：不算"读被阻断"。
        return None, ""
    try:
        read = read_artifact_validated(
            index,
            role,
            phase,
            out_root=out_root,
            required_units=required_units,
        )
    except ArtifactIndexError as exc:
        return None, f"artifact_read_blocked:{role}:{phase}:{exc}"
    return read.payload, ""


def _phase_status(index: Any, out_root: Path, role: str, phase: str) -> str:
    payload, blocker = _validated_payload(index, out_root, role, phase)
    if blocker:
        return f"blocked ({blocker})"
    if payload is None:
        return "not produced"
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
    # 审计 §F.5：优先消费**已发布**的索引 revision；没有发布过才退回临时扫描，
    # 并如实标注来源（否则"发布后改动文件"会被重新扫描重新认证）。
    index_source = "fresh scan (no published revision)"
    try:
        index = load_published_artifact_index(root)
        index_source = f"published revision {index.index_revision}"
    except ArtifactIndexError:
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

    plan, plan_blocker = _validated_payload(
        index, root, "consumer_invocation_plan", "writer"
    )
    invocations = (plan or {}).get("invocations") or () if isinstance(plan, dict) else ()

    # resume 复用页不会产生新的内容验收记录，因此"已接受"还要看分节回执。
    receipt_completed: set[str] = set()
    receipts_payload, receipts_blocker = _validated_payload(
        index, root, "writer_section_receipts", "writer"
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

    empty_artifacts, empty_blockers = _empty_artifact_dispositions(index, root)
    publications = scan_publication_transactions(root)
    unfinished = tuple(item for item in publications if item.state != "complete")
    orphan_files = scan_orphan_temp_files(root)
    critical: list[str] = []
    if blocked:
        critical.append("resume_exhausted_invocation")
    critical.extend(empty_blockers)
    critical.extend(
        f"publication_incomplete:{item.logical_role}:{item.phase}:{item.state}"
        for item in unfinished
    )
    critical.extend(f"publication_orphan_temp:{path}" for path in orphan_files)
    # 审计 §F.5：受索引管理的产物验证失败时，doctor 必须报告"读被阻断"，
    # 而不是继续用未验证内容拼结论。
    critical.extend(
        blocker for blocker in (plan_blocker, receipts_blocker) if blocker
    )
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
        artifact_index_source=index_source,
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
        empty_artifacts=empty_artifacts,
        publications=publications,
        orphan_publication_files=orphan_files,
        critical_blockers=tuple(critical),
        next_action=next_action,
    )



#: 空产物需要冻结单元数的阶段：Writer 需要实现正文，Formalizer 本来就可能没有公式任务。
_EMPTY_POLICY_KEYS: tuple[tuple[str, str], ...] = (
    ("consumer_workset_manifest", "formalizer"),
    ("consumer_workset_manifest", "writer"),
    ("consumer_invocation_plan", "writer"),
)


def _planned_unit_count(root: Path) -> int:
    """Writer 阶段的冻结必需单元数 = 计划里的段落数（审计 §F.3）。"""

    candidates = (
        "narrative_plan_v3.revision.2.json",
        "narrative_plan_v3.json",
    )
    for name in candidates:
        payload = _read_json(root / "artifacts" / "06_authoring" / name)
        if not isinstance(payload, dict):
            continue
        count = sum(
            len((section or {}).get("paragraphs") or ())
            for section in (payload.get("sections") or ())
        )
        if count:
            return count
    return 0


def _empty_artifact_dispositions(
    index: Any, root: Path
) -> tuple[tuple[EmptyArtifactDispositionV1, ...], list[str]]:
    """列出空产物的处置，并把"该阶段需要单元却为空"升级为 critical blocker。"""

    planned_units = _planned_unit_count(root)
    dispositions: list[EmptyArtifactDispositionV1] = []
    blockers: list[str] = []
    for role, phase in _EMPTY_POLICY_KEYS:
        entry = index.entry_for(role, phase)
        if entry is None or entry.status != "valid_empty":
            continue
        payload = _read_json(root / entry.path)
        required_units = planned_units if phase == "writer" else 0
        disposition = assess_empty_artifact(
            role, phase, payload, required_units=required_units
        )
        dispositions.append(disposition)
        blockers.extend(disposition.failures)
    return tuple(dispositions), blockers


def _paragraph_surface_stats(
    root: Path) -> dict[str, int]:
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
