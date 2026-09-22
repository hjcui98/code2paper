"""WP6：阶段化产物索引与解析（方案 §10.1/§10.2）。

事故里同一逻辑对象存在多代同名文件：`consumer_workset_manifest_v2.json`（Formalizer
阶段，**合法空产物**）与 `consumer_workset_manifest_v2.writer.2.json`（Writer 阶段真身）
并存；`narrative_plan_v3.json` 与 `.revision.2.json` 并存。任何"取无后缀文件"或"按
mtime/字典序猜当前对象"的读者都会拿到过期或空对象。

本模块只做**新增解析层**：为每个产物记录 `(logical_role, phase, generation)`、字节摘要与
语义摘要，并给出可分阶段解析的 active 指针；不重命名、不改写任何历史文件（I8）。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.digest import digest_json
from code2paper.agentic.tool_runtime import atomic_write_bytes

ArtifactStatusV1 = Literal[
    "missing",
    "valid_empty",
    "active",
    "superseded",
    "source_snapshot",
    "conflict",
    #: 审计 §F.2：非法 JSON / 不支持的 schema → invalid，**不得**进入 active。
    "invalid",
]

#: 已观测到的 schema 版本白名单（按 role+phase）。仅用于识别**声明了不受支持版本**的
#: 产物；未声明版本的 legacy 产物照旧可读。新版本必须先在此登记（或改成 producer 注册制）。
_KNOWN_SCHEMA_VERSIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("consumer_invocation_plan", "formalizer"): ("1.0",),
    ("consumer_invocation_plan", "realizer"): ("1.0",),
    ("consumer_invocation_plan", "writer"): ("1.0",),
    ("consumer_workset_manifest", "formalizer"): ("2.0",),
    ("consumer_workset_manifest", "writer"): ("2.0",),
    ("formula_packages", "formalizer"): ("1.0",),
    ("realizer_receipts", "realizer"): ("2.0",),
    ("run_identity", "research"): ("1.0",),
    ("run_summary", "terminal"): ("1.0",),
    ("writer_aggregate_receipt", "writer"): ("2.0",),
    ("writer_section_receipts", "writer"): ("2.0",),
}

#: (logical_role, phase, generation, relative path, 说明)
#: ``generation`` 只描述代际，不描述新旧；当前对象由同一 (role, phase) 的规则解析。
_KNOWN_ARTIFACTS: tuple[tuple[str, str, int, str, str], ...] = (
    (
        "consumer_workset_manifest",
        "formalizer",
        1,
        "artifacts/06_authoring/consumer_workset_manifest_v2.json",
        "Formalizer 阶段基础 manifest：无公式任务时合法为空",
    ),
    (
        "consumer_workset_manifest",
        "writer",
        2,
        "artifacts/06_authoring/consumer_workset_manifest_v2.writer.2.json",
        "Writer 阶段 phase-specific manifest",
    ),
    (
        "consumer_invocation_plan",
        "formalizer",
        1,
        "artifacts/06_authoring/consumer_invocation_plan_v1.1.json",
        "Formalizer 调用计划",
    ),
    (
        "consumer_invocation_plan",
        "writer",
        2,
        "artifacts/06_authoring/consumer_invocation_plan_v1.2.json",
        "Writer 调用计划",
    ),
    (
        "consumer_invocation_plan",
        "realizer",
        3,
        "artifacts/06_authoring/consumer_invocation_plan_v1.3.json",
        "Realizer 调用计划",
    ),
    (
        "narrative_plan",
        "authoring",
        1,
        "artifacts/06_authoring/narrative_plan_v3.json",
        "V4→V3 投影后的叙事计划",
    ),
    (
        "narrative_plan",
        "authoring",
        2,
        "artifacts/06_authoring/narrative_plan_v3.revision.2.json",
        "页预算修订后的叙事计划（当前）",
    ),
    (
        "method_section_plan",
        "compat",
        1,
        "artifacts/06_authoring/method_section_plan_v2.json",
        "兼容 MethodSectionPlanV2 适配产物",
    ),
    (
        "method_section_plan",
        "compat",
        0,
        "artifacts/06_authoring/method_section_plan_v2.legacy_source.json",
        "兼容源快照（不是独立语义对象）",
    ),
    (
        "formula_packages",
        "formalizer",
        1,
        "artifacts/06_authoring/mechanism_formula_packages_v2.json",
        "公式包与 Formalizer trace",
    ),
    (
        "realizer_receipts",
        "realizer",
        1,
        "artifacts/06_authoring/realizer_receipts_v2.json",
        "Realizer 回执",
    ),
    (
        "writer_section_receipts",
        "writer",
        1,
        "artifacts/06_authoring/writer_section_receipts_v2.json",
        "分节 Writer 回执",
    ),
    (
        "writer_aggregate_receipt",
        "writer",
        1,
        "artifacts/06_authoring/writer_aggregate_receipt_v2.json",
        "Writer 聚合回执",
    ),
    (
        "binder_receipts",
        "binder",
        1,
        "artifacts/06_authoring/binder_receipts_v2.json",
        "Binder 回执（失败即阻断发布）",
    ),
    (
        "run_identity",
        "research",
        1,
        "artifacts/research_product/run_identity_v1.json",
        "历史 RunIdentityV1（目标仓库身份）",
    ),
    (
        "authoring_execution_identity",
        "research",
        2,
        "artifacts/research_product/authoring_execution_identity_v2.json",
        "WP1 执行身份 V2（引擎/目标/输入分离）",
    ),
    (
        "run_summary",
        "terminal",
        1,
        "artifacts/research_product/run_summary.json",
        "运行终态摘要",
    ),
)

_ROLE_PHASE_KEYS = tuple(
    dict.fromkeys((role, phase) for role, phase, _g, _p, _d in _KNOWN_ARTIFACTS)
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


class ArtifactIndexError(RuntimeError):
    """解析失败：歧义、摘要不符、路径逃逸或缺失。"""


class ArtifactIndexEntryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_role: str
    phase: str
    schema_version: str = ""
    generation: int = 0
    path: str
    status: ArtifactStatusV1 = "missing"
    semantic_digest: str = ""
    file_bytes_digest: str = ""
    upstream_digests: dict[str, str] = Field(default_factory=dict)
    detail: str = ""
    #: 审计 §F.1：条目来自 producer 注册还是 legacy 扫描。
    discovery: Literal["legacy_scan", "producer_registration"] = "legacy_scan"
    #: producer 注册时声明的 upstream 引用（identity/digest 形式，原样保留）。
    upstream_refs: tuple[str, ...] = ()


class AuthoringArtifactIndexV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    execution_identity_digest: str = ""
    index_revision: int = 1
    entries: tuple[ArtifactIndexEntryV1, ...] = ()
    #: ``"role:phase" -> 该 (role, phase) 的当前条目 path``
    active: dict[str, str] = Field(default_factory=dict)
    content_digest: str = ""

    def entry_for(self, role: str, phase: str) -> ArtifactIndexEntryV1 | None:
        path = self.active.get(f"{role}:{phase}")
        if path is None:
            return None
        for entry in self.entries:
            if entry.path == path:
                return entry
        return None


def _semantic_digest(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("content_digest", "content_digest_sha256", "digest"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _empty_manifest(payload: Any) -> bool:
    """仅对**声明了 manifest 形状**的产物判空。

    身份、回执、计划等产物不含 ``worksets``/``pages`` 键，若把"键缺失"当作"空"，
    它们会被误标为 valid_empty，进而被 ``allow_empty=False`` 的读者错误拒绝。
    """

    if not isinstance(payload, dict):
        return False
    if "worksets" not in payload and "pages" not in payload:
        return False
    return not (payload.get("worksets") or ()) and not (payload.get("pages") or ())


#: 审计 §F.3：空产物是否合法取决于**该阶段冻结的 required units**，而不是所有 phase
#: 共用 ``allow_empty=True``。``requires_units`` 表示"有必需单元时不得为空"；
#: ``allowed_when_no_required_units`` 表示该阶段本来就可能没有任务（例如 Formalizer
#: 没有公式义务）。
PHASE_EMPTY_POLICY: Mapping[tuple[str, str], str] = MappingProxyType({
    ("consumer_workset_manifest", "formalizer"): "allowed_when_no_required_units",
    ("consumer_workset_manifest", "writer"): "requires_units",
    ("consumer_invocation_plan", "formalizer"): "allowed_when_no_required_units",
    ("consumer_invocation_plan", "writer"): "requires_units",
    ("consumer_invocation_plan", "realizer"): "allowed_when_no_required_units",
    ("formula_obligations", "formalizer"): "allowed_when_no_required_units",
    ("mechanism_formula_packages", "formalizer"): "allowed_when_no_required_units",
    ("binder_receipts", "binder"): "requires_units",
})

#: 未在表里登记的 (role, phase)：保守地按"允许为空但必须能说明原因"处理，
#: 由调用方按冻结 required units 收紧。
DEFAULT_PHASE_EMPTY_POLICY = "allowed_when_no_required_units"


def _not_applicable_task_ids(payload: Any) -> tuple[str, ...]:
    """空产物必须说明"为什么为空、哪些任务 not_applicable"（审计 §F.3）。"""

    if not isinstance(payload, Mapping):
        return ()
    found: list[str] = []
    for key in ("not_applicable_task_ids", "not_applicable_ids"):
        value = payload.get(key)
        if isinstance(value, str):
            value = [value]
        if isinstance(value, (list, tuple)):
            found.extend(str(item).strip() for item in value if str(item).strip())
    diagnostics = payload.get("projection_diagnostics") or ()
    if isinstance(diagnostics, (list, tuple)):
        for item in diagnostics:
            if not isinstance(item, Mapping):
                continue
            if str(item.get("kind") or "") not in {"not_applicable", "empty_manifest"}:
                continue
            for key in ("task_ids", "not_applicable_task_ids", "ids"):
                value = item.get(key) or ()
                if isinstance(value, str):
                    value = [value]
                found.extend(
                    str(entry).strip() for entry in value if str(entry).strip()
                )
    return tuple(dict.fromkeys(found))


class EmptyArtifactDispositionV1(BaseModel):
    """空产物的处置结论（审计 §F.3）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_role: str
    phase: str
    empty: bool = False
    policy: str = DEFAULT_PHASE_EMPTY_POLICY
    required_units: int = 0
    allowed: bool = True
    reason: str = ""
    declared_not_applicable_task_ids: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()

    def as_trace(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def assess_empty_artifact(
    role: str,
    phase: str,
    payload: Any,
    *,
    required_units: int = 0,
) -> EmptyArtifactDispositionV1:
    """判断某个阶段的空产物是否合法，并如实记录为空的原因。"""

    key = (str(role), str(phase))
    policy = PHASE_EMPTY_POLICY.get(key, DEFAULT_PHASE_EMPTY_POLICY)
    not_applicable = _not_applicable_task_ids(payload)
    if not _empty_manifest(payload):
        return EmptyArtifactDispositionV1(
            logical_role=key[0],
            phase=key[1],
            empty=False,
            policy=policy,
            required_units=int(required_units),
            reason="not_empty",
            declared_not_applicable_task_ids=not_applicable,
        )
    required = max(0, int(required_units))
    if required > 0 and policy == "requires_units":
        return EmptyArtifactDispositionV1(
            logical_role=key[0],
            phase=key[1],
            empty=True,
            policy=policy,
            required_units=required,
            allowed=False,
            reason="empty_with_required_units",
            declared_not_applicable_task_ids=not_applicable,
            failures=(
                f"artifact_empty_with_required_units:{key[0]}:{key[1]}:{required}",
            ),
        )
    return EmptyArtifactDispositionV1(
        logical_role=key[0],
        phase=key[1],
        empty=True,
        policy=policy,
        required_units=required,
        allowed=True,
        reason=(
            "no_required_units"
            if required == 0
            else "declared_not_applicable"
            if not_applicable
            else "empty_allowed_by_policy"
        ),
        declared_not_applicable_task_ids=not_applicable,
    )


def _classify_artifact_entry(
    root: Path,
    *,
    role: str,
    phase: str,
    generation: int,
    relative: str,
    detail: str,
    discovery: Literal["legacy_scan", "producer_registration"] = "legacy_scan",
    registered_bytes_digest: str = "",
    registered_semantic_digest: str = "",
    upstream_refs: Sequence[str] = (),
) -> ArtifactIndexEntryV1:
    """把一个产物文件分类为一条索引条目（legacy 扫描与 producer 注册共用）。

    ``registered_*`` 非空时按注册值核对：目标缺失或字节变化一律 invalid，不静默降级
    成"这次没产出"（审计 §F.1 的注册必须可验证）。
    """

    path = root / relative
    if not path.is_file():
        detail_text = (
            "registry target missing" if discovery == "producer_registration"
            else "not produced in this run"
        )
        return ArtifactIndexEntryV1(
            logical_role=role,
            phase=phase,
            generation=generation,
            path=relative,
            status="invalid" if discovery == "producer_registration" else "missing",
            detail=f"{detail} ({detail_text})" if detail else detail_text,
            discovery=discovery,
            upstream_refs=tuple(upstream_refs),
        )
    raw = path.read_bytes()
    actual_digest = _sha256_file(path)
    if registered_bytes_digest and actual_digest != registered_bytes_digest:
        return ArtifactIndexEntryV1(
            logical_role=role,
            phase=phase,
            generation=generation,
            path=relative,
            status="invalid",
            file_bytes_digest=actual_digest,
            detail=(
                f"{detail} (registry_bytes_changed:"
                f"{actual_digest}!={registered_bytes_digest})"
            ),
            discovery=discovery,
            upstream_refs=tuple(upstream_refs),
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        payload = None
    schema_version = ""
    if isinstance(payload, dict):
        schema_version = str(payload.get("schema_version") or "")
    status: ArtifactStatusV1 = "active"
    detail_text = detail
    if generation == 0:
        status = "source_snapshot"
    elif payload is None:
        # 解析失败：文件存在但内容不可用。旧实现仍把它记成 active
        # （审计 §F.2 的第一条反例）。
        status = "invalid"
        detail_text = f"{detail} (unparsable json)"
    elif (
        schema_version.strip()
        and (role, phase) in _KNOWN_SCHEMA_VERSIONS
        and schema_version.strip() not in _KNOWN_SCHEMA_VERSIONS[(role, phase)]
    ):
        # 声明了**不受支持**的 schema 版本 → invalid（未声明版本的 legacy 产物
        # 仍可读，但 schema_version 会被如实记录为空）。
        status = "invalid"
        detail_text = f"{detail} (unsupported schema_version:{schema_version})"
    elif _empty_manifest(payload):
        status = "valid_empty"
    semantic_digest = _semantic_digest(payload) or registered_semantic_digest
    return ArtifactIndexEntryV1(
        logical_role=role,
        phase=phase,
        schema_version=schema_version,
        generation=generation,
        path=relative,
        status=status,
        semantic_digest=semantic_digest,
        file_bytes_digest=actual_digest,
        upstream_digests={},
        detail=detail_text,
        discovery=discovery,
        upstream_refs=tuple(upstream_refs),
    )


def _registry_entries(
    root: Path,
    *,
    by_role_phase: dict[tuple[str, str], list[ArtifactIndexEntryV1]],
) -> tuple[list[ArtifactIndexEntryV1], dict[str, str]]:
    """把 producer 注册表投影成索引条目（审计 §F.1）。"""

    from code2paper.agentic.authoring_artifact_registry import (
        REGISTRY_DIR_NAME,
        REGISTRY_POINTER_NAME,
        ArtifactRegistryError,
        load_artifact_registry,
    )

    try:
        registry = load_artifact_registry(root)
    except ArtifactRegistryError as exc:
        entry = ArtifactIndexEntryV1(
            logical_role="authoring_artifact_registry",
            phase="research",
            path=f"artifacts/{REGISTRY_DIR_NAME}/{REGISTRY_POINTER_NAME}",
            status="invalid",
            detail=str(exc),
        )
        by_role_phase.setdefault(
            ("authoring_artifact_registry", "research"), []
        ).append(entry)
        return [entry], {}
    entries: list[ArtifactIndexEntryV1] = []
    active: dict[str, str] = {}
    for registration in registry.active_registrations():
        entry = _classify_artifact_entry(
            root,
            role=registration.logical_role,
            phase=registration.phase,
            generation=registration.generation,
            relative=registration.path,
            detail=f"registered by {registration.producer or 'producer'}",
            discovery="producer_registration",
            registered_bytes_digest=registration.file_bytes_digest,
            registered_semantic_digest=registration.semantic_digest,
            upstream_refs=registration.upstream_refs,
        )
        entries.append(entry)
        by_role_phase.setdefault(
            (registration.logical_role, registration.phase), []
        ).append(entry)
        if entry.status in {"missing", "invalid", "source_snapshot"}:
            # 注册指向的内容不可用：该 key 显式不可解析，而不是回退到别的候选。
            active[registration.key()] = ""
        else:
            active[registration.key()] = entry.path
    return entries, active


def build_artifact_index(
    out_root: str | Path,
    *,
    execution_identity_digest: str = "",
    reference_digests: dict[str, str] | None = None,
    index_revision: int = 1,
) -> AuthoringArtifactIndexV1:
    """扫描已知产物并给出分阶段 active 指针（只读）。

    条目来源有两种：producer 发布时的**注册**（审计 §F.1，权威）与 legacy 文件扫描
    （``_KNOWN_ARTIFACTS``，只读导入规则）。注册的 (role, phase) 直接决定当前对象，
    因此新增一代不需要再往 ``_KNOWN_ARTIFACTS`` 里加分支。
    """

    root = Path(out_root).expanduser().resolve()
    references = dict(reference_digests or {})
    entries: list[ArtifactIndexEntryV1] = []
    by_role_phase: dict[tuple[str, str], list[ArtifactIndexEntryV1]] = {}

    for role, phase, generation, relative, detail in _KNOWN_ARTIFACTS:
        entry = _classify_artifact_entry(
            root,
            role=role,
            phase=phase,
            generation=generation,
            relative=relative,
            detail=detail,
        )
        entries.append(entry)
        by_role_phase.setdefault((role, phase), []).append(entry)

    registry_entries, registry_active = _registry_entries(
        root, by_role_phase=by_role_phase
    )
    # 同一 (role, phase, path) 同时被扫描与注册命中时，保留注册条目（唯一权威），
    # 避免同一份内容在索引里出现两种 discovery 结论。
    registered_paths = {
        (item.logical_role, item.phase, item.path)
        for item in registry_entries
        if item.discovery == "producer_registration"
    }
    entries = [
        entry
        for entry in entries
        if (entry.logical_role, entry.phase, entry.path) not in registered_paths
    ]
    entries.extend(registry_entries)
    by_role_phase = {}
    for entry in entries:
        by_role_phase.setdefault((entry.logical_role, entry.phase), []).append(entry)

    active: dict[str, str] = {}
    for (role, phase), candidates in by_role_phase.items():
        usable = [
            item for item in candidates
            if item.status not in {"missing", "source_snapshot", "invalid"}
        ]
        if not usable:
            continue
        reference = references.get(f"{role}:{phase}") or references.get(role) or ""
        chosen: ArtifactIndexEntryV1 | None = None
        if reference:
            # 审计 §F.2：给了显式引用就必须**唯一命中**；零命中不得回退到最高代
            # （否则"指定了一个不存在的摘要"会静默变成"选了另一份内容"）。
            matching = [item for item in usable if item.semantic_digest == reference]
            if len(matching) != 1:
                active[f"{role}:{phase}"] = ""
                continue
            chosen = matching[0]
        if chosen is None:
            chosen = max(usable, key=lambda item: (item.generation, item.path))
        active[f"{role}:{phase}"] = chosen.path

    # 审计 §F.1：producer 注册是这个 (role, phase) 当前对象的权威结论；显式引用
    # （reference_digests）仍然优先，因为它是调用方对"要读哪一份内容"的断言。
    for key, registered_path in registry_active.items():
        if references.get(key) or references.get(key.split(":", 1)[0]):
            continue
        active[key] = registered_path

    final_entries: list[ArtifactIndexEntryV1] = []
    for entry in entries:
        key = f"{entry.logical_role}:{entry.phase}"
        if active.get(key) and entry.path != active[key]:
            if entry.status not in {"missing", "source_snapshot", "invalid"}:
                entry = entry.model_copy(update={"status": "superseded"})
        final_entries.append(entry)

    payload = {
        "schema_version": "1.0",
        "execution_identity_digest": str(execution_identity_digest or ""),
        "index_revision": int(index_revision),
        "entries": [item.model_dump(mode="json") for item in final_entries],
        "active": active,
    }
    return AuthoringArtifactIndexV1(
        execution_identity_digest=str(execution_identity_digest or ""),
        index_revision=int(index_revision),
        entries=tuple(final_entries),
        active=active,
        content_digest=digest_json(payload),
    )


def resolve_artifact(
    index: AuthoringArtifactIndexV1,
    role: str,
    phase: str,
    *,
    out_root: str | Path,
    expected_digest: str | None = None,
    allow_empty: bool = True,
    required_units: int | None = None,
) -> Path:
    """按 (role, phase) 解析当前产物；歧义/缺失/摘要不符/路径逃逸一律阻断。

    审计 §F.3：``required_units`` 给出该阶段**冻结的必需单元数**；>0 时该阶段的空产物
    不再是"合法空"，而是 typed block——空是否合法取决于阶段与冻结单元，不取决于
    所有 phase 共用的 ``allow_empty=True``。
    """

    key = f"{role}:{phase}"
    if key not in index.active:
        raise ArtifactIndexError(f"artifact_role_phase_unknown:{key}")
    path_value = index.active.get(key) or ""
    if not path_value:
        raise ArtifactIndexError(f"artifact_active_ambiguous:{key}")
    root = Path(out_root).expanduser().resolve()
    path = (root / path_value).resolve()
    if root != path and root not in path.parents:
        raise ArtifactIndexError(f"artifact_path_escape:{key}:{path_value}")
    if not path.is_file():
        raise ArtifactIndexError(f"artifact_missing:{key}:{path_value}")
    entry = index.entry_for(role, phase)
    if entry is not None:
        if entry.status == "valid_empty":
            if not allow_empty:
                raise ArtifactIndexError(f"artifact_empty_not_allowed:{key}")
            if required_units is not None and int(required_units) > 0:
                policy = PHASE_EMPTY_POLICY.get(
                    (str(role), str(phase)), DEFAULT_PHASE_EMPTY_POLICY
                )
                if policy == "requires_units":
                    raise ArtifactIndexError(
                        f"artifact_empty_with_required_units:{key}:"
                        f"{int(required_units)}"
                    )
        if expected_digest:
            if not entry.semantic_digest:
                raise ArtifactIndexError(f"artifact_semantic_digest_missing:{key}")
            if entry.semantic_digest != expected_digest:
                raise ArtifactIndexError(
                    f"artifact_digest_mismatch:{key}:"
                    f"{entry.semantic_digest}!={expected_digest}"
                )
    return path


class ValidatedArtifactReadV1(BaseModel):
    """一次**已验证字节**的读取结果（审计 §F.2）。

    返回字节而不是路径：调用方拿到的就是被验证过的那一份内容，避免"验证路径之后
    再重新打开另一份内容"的 TOCTOU 缺口。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_role: str
    phase: str
    path: str
    schema_version: str = ""
    status: str = "active"
    file_bytes_digest: str = ""
    semantic_digest: str = ""
    #: 语义摘要的验证级别：recomputed（用 producer 模型复算）/ declared_only（只在
    #: 同一份字节里读到声明值，未复算）/ bytes_only（该产物不带语义摘要）。
    semantic_digest_verification: str = "bytes_only"
    payload: Any = None
    #: 审计 §F.3：空产物是否合法、为什么为空、哪些任务 not_applicable。
    empty_disposition: EmptyArtifactDispositionV1 | None = None


#: 能用 producer 模型**复算**语义摘要的 role（审计 §F.2）。未注册的 role 会以
#: declared_only 如实标注，不假装已复算。
_SEMANTIC_RESEAL_MODELS: dict[tuple[str, str], tuple[str, str]] = {
    ("narrative_plan", "authoring"): (
        "code2paper.agentic.method_architect",
        "NarrativePlanV3",
    ),
    ("consumer_workset_manifest", "writer"): (
        "code2paper.agentic.unified_context_models",
        "ConsumerWorksetManifestV2",
    ),
    ("consumer_workset_manifest", "formalizer"): (
        "code2paper.agentic.unified_context_models",
        "ConsumerWorksetManifestV2",
    ),
}


def _reseal_semantic_digest(role: str, phase: str, payload: Any) -> str:
    """用 producer 模型重新封装语义摘要；未注册/不可用时返回空串。"""

    target = _SEMANTIC_RESEAL_MODELS.get((role, phase))
    if target is None or not isinstance(payload, dict):
        return ""
    import importlib

    module_name, class_name = target
    try:
        model = getattr(importlib.import_module(module_name), class_name)
        stripped = {key: value for key, value in payload.items() if key != "content_digest"}
        instance = model.model_validate(stripped)
    except Exception:  # noqa: BLE001 - 不可复算时退回 declared_only
        return ""
    return str(getattr(instance, "content_digest", "") or "")


def read_artifact_validated(
    index: AuthoringArtifactIndexV1,
    role: str,
    phase: str,
    *,
    out_root: str | Path,
    expected_digest: str | None = None,
    allow_empty: bool = True,
    required_units: int | None = None,
) -> ValidatedArtifactReadV1:
    """解析 + 读取 + **重算**字节与语义摘要，然后返回同一份已验证内容。

    审计 §F.2 的确定行为：``resolve_artifact`` 只比较索引缓存里的摘要，不重算当前
    字节，因此"建索引后改动 active 文件"不会被发觉。本函数在消费点重算：
    字节摘要必须等于索引记录值，语义摘要（若记录）也必须在同一份字节上复算一致。

    审计 §F.3：``required_units`` 给出该阶段冻结的必需单元数；空产物在该阶段需要
    单元时直接 typed block，并把"为什么为空 / 哪些任务 not_applicable"写进返回结果。
    """

    path = resolve_artifact(
        index,
        role,
        phase,
        out_root=out_root,
        expected_digest=expected_digest,
        allow_empty=allow_empty,
        required_units=required_units,
    )
    entry = index.entry_for(role, phase)
    if entry is None or entry.path != str(
        path.relative_to(Path(out_root).expanduser().resolve())
    ):
        raise ArtifactIndexError(f"artifact_active_entry_mismatch:{role}:{phase}")
    raw = path.read_bytes()
    actual_file_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if entry.file_bytes_digest and actual_file_digest != entry.file_bytes_digest:
        raise ArtifactIndexError(
            f"artifact_bytes_changed_since_index:{role}:{phase}:"
            f"{actual_file_digest}!={entry.file_bytes_digest}"
        )
    payload: Any = None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        if entry.status != "valid_empty":
            raise ArtifactIndexError(f"artifact_unparsable_at_read:{role}:{phase}")
    verification = "bytes_only"
    if entry.semantic_digest:
        resealed = _reseal_semantic_digest(role, phase, payload)
        if resealed:
            if resealed != entry.semantic_digest:
                raise ArtifactIndexError(
                    f"artifact_semantic_digest_changed:{role}:{phase}:"
                    f"{resealed}!={entry.semantic_digest}"
                )
            verification = "recomputed"
        else:
            # 该 role 还没有注册 producer 模型：只能确认"同一份字节里声明了同一个摘要"，
            # 如实标为 declared_only，而不是假装已经复算过。
            declared = _semantic_digest(payload)
            if declared != entry.semantic_digest:
                raise ArtifactIndexError(
                    f"artifact_semantic_digest_changed:{role}:{phase}:"
                    f"{declared}!={entry.semantic_digest}"
                )
            verification = "declared_only"
    return ValidatedArtifactReadV1(
        logical_role=role,
        phase=phase,
        path=str(path),
        schema_version=entry.schema_version,
        status=entry.status,
        file_bytes_digest=actual_file_digest,
        semantic_digest=entry.semantic_digest,
        semantic_digest_verification=verification,
        payload=payload,
        empty_disposition=assess_empty_artifact(
            role, phase, payload, required_units=int(required_units or 0)
        ),
    )


class ResolvedAuthoringSnapshotV1(BaseModel):
    """阶段开始前冻结的输入快照（方案 §10.3）。

    reader 不在执行过程中反复读取可变的 active 指针：本快照固定该阶段使用的
    产物路径与字节摘要，执行完成后另写完成状态，不修改已执行的输入快照。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    phase: str
    execution_identity_digest: str = ""
    index_revision: int = 1
    index_digest: str = ""
    resolved: dict[str, str] = Field(default_factory=dict)
    digests: dict[str, str] = Field(default_factory=dict)
    content_digest: str = ""

    def as_diagnostics(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def artifact_index_path(out_root: str | Path) -> Path:
    return (
        Path(out_root).expanduser().resolve()
        / "artifacts"
        / "06_authoring"
        / "authoring_artifact_index_v1.json"
    )


def publish_artifact_index(
    out_root: str | Path,
    *,
    execution_identity_digest: str = "",
    reference_digests: dict[str, str] | None = None,
) -> tuple[str, AuthoringArtifactIndexV1]:
    """原子发布一版索引；读回校验后才算发布成功（§10.2）。"""

    root = Path(out_root).expanduser().resolve()
    path = artifact_index_path(root)
    previous_revision = 0
    if path.is_file():
        try:
            previous_revision = int(
                json.loads(path.read_text(encoding="utf-8")).get("index_revision") or 0
            )
        except (OSError, ValueError):
            previous_revision = 0
    index = build_artifact_index(
        root,
        execution_identity_digest=execution_identity_digest,
        reference_digests=reference_digests,
        index_revision=previous_revision + 1,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(
        path, (index.model_dump_json(indent=2) + "\n").encode("utf-8")
    )
    try:
        reread = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # pragma: no cover - 磁盘异常
        raise ArtifactIndexError("artifact_index_publish_incomplete") from exc
    if str(reread.get("content_digest") or "") != index.content_digest:
        raise ArtifactIndexError("artifact_index_publish_incomplete")
    return str(path), index


_RESOLVED_SNAPSHOT_SCHEMA_VERSION = "1.0"

_SNAPSHOT_IDENTITY_FIELDS = (
    "schema_version",
    "phase",
    "execution_identity_digest",
    "index_revision",
    "index_digest",
    "resolved",
    "digests",
)


def _snapshot_digest_payload(
    *,
    phase: str,
    execution_identity_digest: str,
    index_revision: int,
    index_digest: str,
    resolved: dict[str, str],
    digests: dict[str, str],
) -> dict[str, Any]:
    """阶段快照被摘要的字段集：读写两端必须一致，否则验证会失真。"""

    return {
        "schema_version": _RESOLVED_SNAPSHOT_SCHEMA_VERSION,
        "phase": str(phase),
        "execution_identity_digest": str(execution_identity_digest or ""),
        "index_revision": int(index_revision),
        "index_digest": str(index_digest or ""),
        "resolved": dict(resolved or {}),
        "digests": dict(digests or {}),
    }


def _snapshot_identity(payload: dict[str, Any]) -> dict[str, Any]:
    return {field: payload.get(field) for field in _SNAPSHOT_IDENTITY_FIELDS}


def build_resolved_authoring_snapshot(
    index: AuthoringArtifactIndexV1,
    *,
    out_root: str | Path,
    phase: str,
    required_roles: list[str] | tuple[str, ...],
) -> ResolvedAuthoringSnapshotV1:
    """把某阶段需要的产物解析结果冻结成不可变快照。"""

    root = Path(out_root).expanduser().resolve()
    resolved: dict[str, str] = {}
    digests: dict[str, str] = {}
    for key in required_roles or ():
        role, _, phase_name = str(key).partition(":")
        if not role or not phase_name:
            raise ArtifactIndexError(f"artifact_role_phase_malformed:{key}")
        path = resolve_artifact(index, role, phase_name, out_root=root)
        entry = index.entry_for(role, phase_name)
        resolved[key] = str(path.relative_to(root))
        digests[key] = entry.file_bytes_digest if entry is not None else ""
    payload = _snapshot_digest_payload(
        phase=phase,
        execution_identity_digest=index.execution_identity_digest,
        index_revision=index.index_revision,
        index_digest=index.content_digest,
        resolved=resolved,
        digests=digests,
    )
    return ResolvedAuthoringSnapshotV1(
        phase=str(phase),
        execution_identity_digest=index.execution_identity_digest,
        index_revision=index.index_revision,
        index_digest=index.content_digest,
        resolved=resolved,
        digests=digests,
        content_digest=digest_json(payload),
    )


def resolved_snapshot_evidence_path(
    out_root: str | Path, snapshot: ResolvedAuthoringSnapshotV1
) -> Path:
    """不可变证据路径：文件名带 snapshot 摘要（审计 §F.4）。"""

    token = str(snapshot.content_digest or "undigested").removeprefix("sha256:")[:16]
    return (
        Path(out_root).expanduser().resolve()
        / "artifacts"
        / "06_authoring"
        / f"resolved_authoring_snapshot_v1.{snapshot.phase}.{token}.json"
    )


def write_resolved_authoring_snapshot(
    out_root: str | Path, snapshot: ResolvedAuthoringSnapshotV1
) -> str:
    """冻结阶段输入快照：**不可变证据 + 原子指针**（审计 §F.4）。

    旧实现往固定文件名无条件覆盖写，于是同一 phase 的第二次运行会抹掉第一次的输入
    证据。现在：

    * 证据写进带 snapshot 摘要的文件名，**同内容重复写入幂等**，同名不同内容拒绝；
    * 固定文件名（``...{phase}.json``）作为当前指针，内容仍是完整快照（兼容既有
      reader），并额外带 ``evidence_path`` 指向不可变副本。

    某一步中断只会留下 orphan 证据或旧指针，不会让指针指向半成品。
    """

    root = Path(out_root).expanduser().resolve()
    authoring = root / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True, exist_ok=True)
    payload = (snapshot.model_dump_json(indent=2) + "\n").encode("utf-8")

    evidence_path = resolved_snapshot_evidence_path(root, snapshot)
    if evidence_path.is_file():
        if evidence_path.read_bytes() != payload:
            # 同摘要不同内容意味着摘要被伪造或写入被截断：拒绝，不覆盖历史证据。
            raise ArtifactIndexError(
                f"stage_snapshot_content_conflict:{snapshot.phase}:{evidence_path.name}"
            )
    else:
        atomic_write_bytes(evidence_path, payload)

    pointer = authoring / f"resolved_authoring_snapshot_v1.{snapshot.phase}.json"
    pointer_payload = {
        **snapshot.model_dump(mode="json"),
        "evidence_path": str(evidence_path),
    }
    atomic_write_bytes(
        pointer,
        (json.dumps(pointer_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )
    return str(pointer)


def frozen_snapshot_evidence(
    out_root: str | Path, phase: str
) -> ValidatedArtifactReadV1:
    """读取某 phase 的**不可变**输入快照证据（不经过可变的固定名指针）。"""

    root = Path(out_root).expanduser().resolve()
    pointer = (
        root
        / "artifacts"
        / "06_authoring"
        / f"resolved_authoring_snapshot_v1.{phase}.json"
    )
    if not pointer.is_file():
        raise ArtifactIndexError(f"stage_snapshot_missing:{phase}")
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactIndexError(f"stage_snapshot_pointer_unreadable:{phase}") from exc
    evidence_value = str(payload.get("evidence_path") or "")
    if not evidence_value:
        # 旧格式（无证据副本）：只能如实报告"没有不可变证据"。
        raise ArtifactIndexError(f"stage_snapshot_evidence_missing:{phase}")
    evidence = Path(evidence_value)
    if not evidence.is_file():
        raise ArtifactIndexError(f"stage_snapshot_evidence_missing:{phase}")
    raw = evidence.read_bytes()
    try:
        evidence_payload = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:  # pragma: no cover - 磁盘异常
        raise ArtifactIndexError(f"stage_snapshot_evidence_unreadable:{phase}") from exc
    if not isinstance(evidence_payload, dict):
        raise ArtifactIndexError(f"stage_snapshot_evidence_unreadable:{phase}")

    # 指针与证据必须描述同一份快照（否则指针可以被悄悄指向别的快照）。
    if _snapshot_identity(payload) != _snapshot_identity(evidence_payload):
        raise ArtifactIndexError(f"stage_snapshot_pointer_evidence_mismatch:{phase}")

    # 证据内容必须自洽地重算出它声明的语义摘要：只比较声明值等于文件字节摘要会
    # 把"文件字节 sha256"和"规范化 JSON 摘要"混为一谈，从而永真或永假。
    declared = str(payload.get("content_digest") or "")
    evidence_declared = str(evidence_payload.get("content_digest") or "")
    recomputed = digest_json(
        _snapshot_digest_payload(
            phase=str(evidence_payload.get("phase") or phase),
            execution_identity_digest=str(
                evidence_payload.get("execution_identity_digest") or ""
            ),
            index_revision=int(evidence_payload.get("index_revision") or 0),
            index_digest=str(evidence_payload.get("index_digest") or ""),
            resolved=evidence_payload.get("resolved") or {},
            digests=evidence_payload.get("digests") or {},
        )
    )
    if not declared or recomputed != declared or evidence_declared != declared:
        raise ArtifactIndexError(
            f"stage_snapshot_evidence_changed:{phase}:{recomputed}!={declared or evidence_declared}"
        )
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    return ValidatedArtifactReadV1(
        logical_role="resolved_authoring_snapshot",
        phase=phase,
        path=str(evidence),
        schema_version=str(payload.get("schema_version") or ""),
        status="frozen",
        file_bytes_digest=digest,
        semantic_digest=declared,
        semantic_digest_verification="pointer_declared_sha256",
        payload=json.loads(raw.decode("utf-8")),
    )



def resolve_role_phase_keys() -> tuple[str, ...]:
    return tuple(f"{role}:{phase}" for role, phase in _ROLE_PHASE_KEYS)


__all__ = [
    "ArtifactIndexEntryV1",
    "ArtifactIndexError",
    "ArtifactStatusV1",
    "AuthoringArtifactIndexV1",
    "ResolvedAuthoringSnapshotV1",
    "artifact_index_path",
    "build_artifact_index",
    "build_resolved_authoring_snapshot",
    "publish_artifact_index",
    "write_resolved_authoring_snapshot",
    "resolved_snapshot_evidence_path",
    "frozen_snapshot_evidence",
    "resolve_artifact",
    "read_artifact_validated",
    "ValidatedArtifactReadV1",
    "resolve_role_phase_keys",
]
