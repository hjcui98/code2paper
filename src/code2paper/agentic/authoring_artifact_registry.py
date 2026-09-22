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

REGISTRY_SCHEMA_VERSION = "1.0"
REGISTRY_DIR_NAME = "artifact_registrations"
REGISTRY_POINTER_NAME = "authoring_artifact_registry_v1.json"


class ArtifactRegistryError(RuntimeError):
    """注册/读取失败：路径越界、目标缺失、同名不同内容或指针不可读。"""


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


def load_artifact_registry(out_root: str | Path) -> ArtifactRegistryV1:
    """读取注册表；指针或某条记录不可读时 fail-closed（不静默忽略）。"""

    pointer = registry_pointer_path(out_root)
    if not pointer.is_file():
        return ArtifactRegistryV1()
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}") from exc
    if not isinstance(payload, Mapping):
        raise ArtifactRegistryError(f"artifact_registry_unreadable:{pointer}")
    try:
        return ArtifactRegistryV1.model_validate(payload)
    except ValueError as exc:
        raise ArtifactRegistryError(f"artifact_registry_invalid:{pointer}") from exc


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
) -> ArtifactRegistrationV1:
    """注册一个已发布的产物；返回不可变注册记录。

    ``payload`` 给出时用于读取产物的 schema 版本与声明的语义摘要；未给出时按字节读取
    并尝试解析 JSON（解析失败不阻断注册，只是没有语义摘要）。
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
    if resolved_generation <= 0:
        resolved_generation = 1 + max(
            (
                item.generation
                for item in registry.registrations
                if item.key() == f"{role}:{phase}"
            ),
            default=0,
        )
    try:
        relative = str(target.relative_to(root))
    except ValueError as exc:  # pragma: no cover - 上面的越界检查已覆盖
        raise ArtifactRegistryError(
            f"artifact_registration_path_escape:{target}"
        ) from exc

    identity = {
        "logical_role": str(role),
        "phase": str(phase),
        "generation": resolved_generation,
        "path": relative,
        "file_bytes_digest": file_bytes_digest,
        "semantic_digest": semantic_digest,
    }
    registration = ArtifactRegistrationV1(
        registration_id="reg:" + digest_json(identity).removeprefix("sha256:")[:24],
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

    record_path = _registration_file(root, registration)
    encoded = (registration.model_dump_json(indent=2) + "\n").encode("utf-8")
    if record_path.is_file():
        if record_path.read_bytes() != encoded:
            raise ArtifactRegistryError(
                f"artifact_registration_conflict:{record_path.name}"
            )
    else:
        atomic_write_bytes(record_path, encoded)

    known = {item.registration_id: item for item in registry.registrations}
    known[registration.registration_id] = registration
    active = dict(registry.active)
    previous_id = active.get(registration.key())
    previous = known.get(previous_id) if previous_id else None
    if previous is None or registration.generation >= previous.generation:
        active[registration.key()] = registration.registration_id
    pointer = ArtifactRegistryV1(
        active=active,
        registrations=tuple(
            sorted(known.values(), key=lambda item: (item.key(), item.generation, item.registration_id))
        ),
    )
    atomic_write_bytes(
        registry_pointer_path(root),
        (pointer.model_dump_json(indent=2) + "\n").encode("utf-8"),
    )
    return registration


__all__ = [
    "ArtifactRegistrationV1",
    "ArtifactRegistryError",
    "ArtifactRegistryV1",
    "REGISTRY_DIR_NAME",
    "REGISTRY_POINTER_NAME",
    "REGISTRY_SCHEMA_VERSION",
    "load_artifact_registry",
    "register_authoring_artifact",
    "registry_dir",
    "registry_pointer_path",
]
