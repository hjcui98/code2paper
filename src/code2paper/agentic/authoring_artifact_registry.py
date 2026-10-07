"""审计 §F.1：producer 发布产物时向索引**注册**真实身份。

旧实现只能靠扫描器 + ``_KNOWN_ARTIFACTS`` 猜测"当前生产对象"：谁写了什么角色、
什么 phase、哪一代、字节与语义摘要是什么，全靠文件名后缀穷举；新增一代就要再写一个
``.writer.3`` 分支。本模块把"发布"和"注册"合并成一个动作：

* producer 写完成产物后调用 :func:`register_authoring_artifact`，注册记录里带
  role / phase / generation / 相对路径 / 产物 schema / 字节摘要 / 语义摘要 /
  upstream refs / producer 标识；
* 注册记录本身是**不可变**的（文件名带内容摘要，同内容重复写入幂等，同名不同内容拒绝），
  固定名指针 ``authoring_artifact_registry_v1.json`` 只指向每个 (role, phase) 的当前一代；
* ``_KNOWN_ARTIFACTS`` 因此退回为 legacy 只读导入规则，不再是"所有可能当前对象"的
  穷举表；新的 generation 只要被注册就能被识别。

只做纯文件 I/O 与摘要计算，不发请求、不改写历史产物。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.agentic.tool_runtime import atomic_write_bytes

REGISTRY_SCHEMA_VERSION = "2.0"
#: 旧格式（只有 role/phase/generation/path/摘要，registration_id 不绑定 producer/upstream）：
#: 只能由**具名只读 reader** 读取，严格 reader 明确拒绝，不做原地迁移。
LEGACY_REGISTRY_SCHEMA_VERSION = "1.0"
REGISTRY_DIR_NAME = "artifact_registrations"
REGISTRY_POINTER_NAME = "authoring_artifact_registry_v1.json"


class ArtifactRegistryError(RuntimeError):
    """注册/读取失败：路径越界、目标缺失、同名不同内容、摘要不符或指针不可读。"""


def registry_dir(out_root: str | Path) -> Path:
    return Path(out_root).expanduser().resolve() / "artifacts" / REGISTRY_DIR_NAME


def registry_pointer_path(out_root: str | Path) -> Path:
    return registry_dir(out_root) / REGISTRY_POINTER_NAME


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _declared_semantic_digest(payload: Any) -> str:
    if isinstance(payload, Mapping):
        for key in ("content_digest", "content_digest_sha256", "digest"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


class ArtifactRegistrationV1(BaseModel):
    """一次产物的**不可变**注册记录（审计 §F.1）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = REGISTRY_SCHEMA_VERSION
    registration_id: str
    logical_role: str
    phase: str
    generation: int = 1
    path: str
    artifact_schema_version: str = ""
    file_bytes_digest: str = ""
    semantic_digest: str = ""
    upstream_refs: tuple[str, ...] = ()
    producer: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ArtifactRegistrationV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", digest_json(payload))
        return self

    def key(self) -> str:
        return f"{self.logical_role}:{self.phase}"

    def as_trace(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ArtifactRegistryV1(BaseModel):
    """固定名指针：每个 (role, phase) 指向当前一代注册记录。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = REGISTRY_SCHEMA_VERSION
    active: dict[str, str] = Field(default_factory=dict)
    registrations: tuple[ArtifactRegistrationV1, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ArtifactRegistryV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", digest_json(payload))
        return self

    def by_id(self) -> dict[str, ArtifactRegistrationV1]:
        return {item.registration_id: item for item in self.registrations}

    def active_registrations(self) -> tuple[ArtifactRegistrationV1, ...]:
        index = self.by_id()
        return tuple(
            index[registration_id]
            for _key, registration_id in sorted(self.active.items())
            if registration_id in index
        )


def _registration_file(root: Path, registration: ArtifactRegistrationV1) -> Path:
    token = registration.content_digest.removeprefix("sha256:")[:16]
    return registry_dir(root) / (
        f"registration.{registration.logical_role}.{registration.phase}."
        f"g{int(registration.generation)}.{token}.json"
    )


def _sealed_payload_digest(payload: Mapping[str, Any]) -> str:
    """从**声明字段**重算封存摘要（创建时封、加载时验都用这一个函数）。"""

    return digest_json(
        {key: value for key, value in payload.items() if key != "content_digest"}
    )


def registration_logical_digest(registration: ArtifactRegistrationV1) -> str:
    """注册记录的**完整逻辑内容**摘要（不含 generation/registration_id/内容摘要）。

    幂等判定与"同 ID 不同来源"都打在这上面：producer、upstream、schema、路径、
    字节与语义摘要全部进入，观察时间与 generation 不进入。
    """

    return digest_json({
        "logical_role": registration.logical_role,
        "phase": registration.phase,
        "path": registration.path,
        "artifact_schema_version": registration.artifact_schema_version,
        "file_bytes_digest": registration.file_bytes_digest,
        "semantic_digest": registration.semantic_digest,
        "upstream_refs": list(registration.upstream_refs),
        "producer": registration.producer,
    })


def _verified_registration(
    row: Mapping[str, Any],
    *,
    root: Path,
    verify_records: bool,
) -> ArtifactRegistrationV1:
    """校验一条注册记录的封存摘要，并与磁盘不可变 record 交叉核对。

    * 声明摘要缺失或与从声明字段重算的值不符 → 拒绝（**不重新封印**损坏值）；
    * 磁盘上按声明摘要命名的 record 缺失或逻辑内容与指针行不一致 → 拒绝。
    """

    declared = str(row.get("content_digest") or "")
    if not declared:
        raise ArtifactRegistryError("artifact_registry_unsealed:registration")
    if _sealed_payload_digest(row) != declared:
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:registration")
    try:
        registration = ArtifactRegistrationV1.model_validate(dict(row))
    except ValueError as exc:
        raise ArtifactRegistryError("artifact_registry_invalid:registration") from exc
    if registration.content_digest != declared:
        # 模型 validator 会重算；两者不等说明声明值本身与字段不自洽。
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:registration")
    if not verify_records:
        return registration
    record_path = _registration_file(root, registration)
    if not record_path.is_file():
        raise ArtifactRegistryError(
            f"artifact_registry_record_missing:{record_path.name}"
        )
    try:
        record_payload = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactRegistryError(
            f"artifact_registry_record_unreadable:{record_path.name}"
        ) from exc
    if not isinstance(record_payload, Mapping):
        raise ArtifactRegistryError(
            f"artifact_registry_record_unreadable:{record_path.name}"
        )
    if _sealed_payload_digest(record_payload) != str(
        record_payload.get("content_digest") or ""
    ):
        raise ArtifactRegistryError(
            f"artifact_registry_record_digest_mismatch:{record_path.name}"
        )
    try:
        record = ArtifactRegistrationV1.model_validate(dict(record_payload))
    except ValueError as exc:
        raise ArtifactRegistryError(
            f"artifact_registry_record_invalid:{record_path.name}"
        ) from exc
    if record.model_dump(mode="json") != registration.model_dump(mode="json"):
        raise ArtifactRegistryError(
            f"artifact_registry_record_mismatch:{record_path.name}"
        )
    return registration


def _verify_registry_payload(
    payload: Mapping[str, Any],
    *,
    root: Path,
    verify_records: bool,
) -> ArtifactRegistryV1:
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != REGISTRY_SCHEMA_VERSION:
        raise ArtifactRegistryError(
            f"artifact_registry_schema_version:{schema_version or 'missing'}"
        )
    declared = str(payload.get("content_digest") or "")
    if not declared:
        raise ArtifactRegistryError("artifact_registry_unsealed:pointer")
    if _sealed_payload_digest(payload) != declared:
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:pointer")
    rows = payload.get("registrations") or ()
    if not isinstance(rows, (list, tuple)):
        raise ArtifactRegistryError("artifact_registry_invalid:pointer")
    verified: list[ArtifactRegistrationV1] = []
    by_id: dict[str, ArtifactRegistrationV1] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ArtifactRegistryError("artifact_registry_invalid:registration")
        registration = _verified_registration(
            row, root=root, verify_records=verify_records
        )
        previous = by_id.get(registration.registration_id)
        if previous is not None and previous.model_dump(mode="json") != (
            registration.model_dump(mode="json")
        ):
            # 同 ID 不同来源/内容：即使摘要各自自洽也必须拒绝。
            raise ArtifactRegistryError(
                f"artifact_registry_id_conflict:{registration.registration_id}"
            )
        by_id[registration.registration_id] = registration
        verified.append(registration)
    active = payload.get("active") or {}
    if not isinstance(active, Mapping):
        raise ArtifactRegistryError("artifact_registry_invalid:pointer")
    for key, registration_id in active.items():
        if str(registration_id) and str(registration_id) not in by_id:
            raise ArtifactRegistryError(
                f"artifact_registry_active_dangling:{key}:{registration_id}"
            )
    try:
        registry = ArtifactRegistryV1.model_validate(dict(payload))
    except ValueError as exc:
        raise ArtifactRegistryError("artifact_registry_invalid:pointer") from exc
    if registry.content_digest != declared:
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:pointer")
    if tuple(registry.registrations) != tuple(verified):
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:pointer")
    return registry


def load_artifact_registry(
    out_root: str | Path,
    *,
    allow_legacy: bool = False,
) -> ArtifactRegistryV1:
    """严格读取注册表：校验封存摘要并与磁盘不可变 record 交叉核对。

    缺失指针 = 空注册表（legacy 扫描路径仍可用）。指针或任一记录不可读、摘要不符、
    record 缺失/漂移、active 悬空、同 ID 不同内容 → fail-closed，不静默忽略、
    **不重新封印**损坏值。

    旧 ``1.0`` 记录只能由 :func:`load_legacy_artifact_registry` 具名只读打开；
    本函数默认拒绝（``allow_legacy=True`` 时也只做只读校验，不做迁移）。
    """

    root = Path(out_root).expanduser().resolve()
    pointer = registry_pointer_path(root)
    if not pointer.is_file():
        return ArtifactRegistryV1()
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}") from exc
    if not isinstance(payload, Mapping):
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}")
    schema_version = str(payload.get("schema_version") or "")
    if schema_version == LEGACY_REGISTRY_SCHEMA_VERSION and not allow_legacy:
        raise ArtifactRegistryError(
            "artifact_registry_legacy_requires_named_reader:"
            f"{LEGACY_REGISTRY_SCHEMA_VERSION}"
        )
    return _verify_registry_payload(payload, root=root, verify_records=True)


def load_legacy_artifact_registry(out_root: str | Path) -> ArtifactRegistryV1:
    """具名只读 reader：读取旧 ``1.0`` 注册表，**不迁移、不重写、不重封**。

    只验证"声明摘要 = 从声明字段重算值"和磁盘 record 一致；schema 版本必须是 ``1.0``，
    新格式交给 :func:`load_artifact_registry`。
    """

    root = Path(out_root).expanduser().resolve()
    pointer = registry_pointer_path(root)
    if not pointer.is_file():
        return ArtifactRegistryV1()
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}") from exc
    if not isinstance(payload, Mapping):
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}")
    if str(payload.get("schema_version") or "") != LEGACY_REGISTRY_SCHEMA_VERSION:
        raise ArtifactRegistryError(
            "artifact_registry_not_legacy:"
            f"{str(payload.get('schema_version') or 'missing')}"
        )
    # 旧格式的注册行字段集与新格式相同（本任务未加字段），因此同一套封存校验可用；
    # 这里只做只读核对，不写回任何字节。
    declared = str(payload.get("content_digest") or "")
    if not declared:
        raise ArtifactRegistryError("artifact_registry_unsealed:pointer")
    if _sealed_payload_digest(payload) != declared:
        raise ArtifactRegistryError("artifact_registry_digest_mismatch:pointer")
    for row in payload.get("registrations") or ():
        if isinstance(row, Mapping):
            _verified_registration(row, root=root, verify_records=True)
    try:
        registry = ArtifactRegistryV1.model_validate(dict(payload))
    except ValueError as exc:
        raise ArtifactRegistryError("artifact_registry_invalid:pointer") from exc
    return registry


def register_authoring_artifact(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
    path: str | Path,
    generation: int | None = None,
    payload: Any = None,
    producer: str = "",
    upstream_refs: Sequence[str] = (),
    _activate: bool = True,
) -> ArtifactRegistrationV1:
    """注册一个已发布的产物：准备不可变 record **并**切换 active（向后兼容入口）。

    ``payload`` 给出时用于读取产物的 schema 版本与声明的语义摘要；未给出时按字节读取
    并尝试解析 JSON（解析失败不阻断注册，只是没有语义摘要）。

    需要"先持久、后切换"的发布事务请直接用
    :func:`prepare_artifact_registration` + :func:`activate_artifact_registration`。
    """

    root = Path(out_root).expanduser().resolve()
    target = Path(path)
    if not target.is_absolute():
        target = (root / target).resolve()
    else:
        target = target.resolve()
    if root != target and root not in target.parents:
        raise ArtifactRegistryError(f"artifact_registration_path_escape:{target}")
    if not target.is_file():
        raise ArtifactRegistryError(f"artifact_registration_target_missing:{target}")

    raw = target.read_bytes()
    file_bytes_digest = _sha256_bytes(raw)
    if payload is None:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = None
    artifact_schema_version = ""
    if isinstance(payload, Mapping):
        artifact_schema_version = str(payload.get("schema_version") or "")
    semantic_digest = _declared_semantic_digest(payload)

    registry = load_artifact_registry(root)
    resolved_generation = int(generation or 0)
    try:
        relative = str(target.relative_to(root))
    except ValueError as exc:  # pragma: no cover - 上面的越界检查已覆盖
        raise ArtifactRegistryError(
            f"artifact_registration_path_escape:{target}"
        ) from exc

    # registration_id 绑定**完整来源身份**：producer / upstream / schema / 字节与语义
    # 摘要。旧实现漏掉 producer/upstream，于是同一 ID 可以携带不同来源元数据。
    identity = {
        "logical_role": str(role),
        "phase": str(phase),
        "path": relative,
        "artifact_schema_version": artifact_schema_version,
        "file_bytes_digest": file_bytes_digest,
        "semantic_digest": semantic_digest,
        "upstream_refs": [
            str(item)
            for item in dict.fromkeys(
                str(item) for item in upstream_refs if str(item).strip()
            )
        ],
        "producer": str(producer),
    }
    registration_id = "reg:" + digest_json(identity).removeprefix("sha256:")[:24]

    # 幂等按**完整逻辑内容**判定：同一次提交重复注册必须保持原 record，观察时间与
    # 自动 generation 不得把它变成新产物，也不能靠丢 provenance 换取同 ID。
    existing = next(
        (
            item
            for item in registry.registrations
            if item.registration_id == registration_id
        ),
        None,
    )
    if existing is not None and int(generation or 0) <= 0:
        # 合法重复：原样返回既有不可变记录（不新增 record、不改写指针内容）。
        return existing

    if resolved_generation <= 0:
        resolved_generation = 1 + max(
            (
                item.generation
                for item in registry.registrations
                if item.key() == f"{role}:{phase}"
            ),
            default=0,
        )
    registration = ArtifactRegistrationV1(
        registration_id=registration_id,
        logical_role=str(role),
        phase=str(phase),
        generation=resolved_generation,
        path=relative,
        artifact_schema_version=artifact_schema_version,
        file_bytes_digest=file_bytes_digest,
        semantic_digest=semantic_digest,
        upstream_refs=tuple(
            dict.fromkeys(str(item) for item in upstream_refs if str(item).strip())
        ),
        producer=str(producer),
    )

    # 同 ID 不同来源/内容：显式拒绝，不让后来的记录替换既有身份。
    for item in registry.registrations:
        if item.registration_id != registration.registration_id:
            continue
        if registration_logical_digest(item) != registration_logical_digest(
            registration
        ):
            raise ArtifactRegistryError(
                f"artifact_registry_id_conflict:{registration.registration_id}"
            )

    record_path = _registration_file(root, registration)
    encoded = (registration.model_dump_json(indent=2) + "\n").encode("utf-8")
    if record_path.is_file():
        if record_path.read_bytes() != encoded:
            raise ArtifactRegistryError(
                f"artifact_registration_conflict:{record_path.name}"
            )
    else:
        atomic_write_bytes(record_path, encoded)

    # K02：不可变 record 的**准备**与 active **切换**分开，消除内部抢先激活的旁路。
    if _activate:
        activate_artifact_registration(root, registration)
    return registration


def prepare_artifact_registration(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
    path: str | Path,
    generation: int | None = None,
    payload: Any = None,
    producer: str = "",
    upstream_refs: Sequence[str] = (),
) -> ArtifactRegistrationV1:
    """只准备不可变 registration record（含幂等/冲突检查），**不**动 active 指针。"""

    return register_authoring_artifact(
        out_root,
        role=role,
        phase=phase,
        path=path,
        generation=generation,
        payload=payload,
        producer=producer,
        upstream_refs=upstream_refs,
        _activate=False,
    )


def activate_artifact_registration(
    out_root: str | Path,
    registration: ArtifactRegistrationV1,
    *,
    expected_active_registration_id: str | None = None,
) -> ArtifactRegistryV1:
    """只切换注册表 active 指针；不可变 record 必须已经准备好。

    ``expected_active_registration_id`` 给出时做 CAS（不符即拒绝且不写）。发布 owner 负责
    顺序：先持久 record，再切换权威指针。
    """

    root = Path(out_root).expanduser().resolve()
    registry = load_artifact_registry(root)
    known = {item.registration_id: item for item in registry.registrations}
    if registration.registration_id not in known:
        record_path = _registration_file(root, registration)
        if not record_path.is_file():
            raise ArtifactRegistryError(
                f"artifact_registration_record_missing:{record_path.name}"
            )
        known[registration.registration_id] = registration
    active = dict(registry.active)
    key = registration.key()
    current = active.get(key)
    if expected_active_registration_id is not None and (current or None) != (
        expected_active_registration_id or None
    ):
        raise ArtifactRegistryError(
            "artifact_registry_active_cas_failed:"
            f"{key}:expected={expected_active_registration_id or 'absent'}:"
            f"current={current or 'absent'}"
        )
    previous = known.get(current) if current else None
    if previous is None or registration.generation >= previous.generation:
        active[key] = registration.registration_id
    pointer = ArtifactRegistryV1(
        active=active,
        registrations=tuple(
            sorted(
                known.values(),
                key=lambda item: (item.key(), item.generation, item.registration_id),
            )
        ),
    )
    atomic_write_bytes(
        registry_pointer_path(root),
        (pointer.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return pointer


__all__ = [
    "ArtifactRegistrationV1",
    "activate_artifact_registration",
    "prepare_artifact_registration",
    "ArtifactRegistryError",
    "ArtifactRegistryV1",
    "LEGACY_REGISTRY_SCHEMA_VERSION",
    "REGISTRY_DIR_NAME",
    "REGISTRY_POINTER_NAME",
    "REGISTRY_SCHEMA_VERSION",
    "load_artifact_registry",
    "load_legacy_artifact_registry",
    "register_authoring_artifact",
    "registration_logical_digest",
    "registry_dir",
    "registry_pointer_path",
]
