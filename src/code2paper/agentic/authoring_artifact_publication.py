"""审计 §F.4：产物发布是一个**可中断、可诊断**的事务。

要求的事务顺序：

``写临时文件 → 严格验证 → 原子发布不可变产物 → 注册索引 revision → 原子更新 active``

某一步中断时只能留下 orphan/incomplete 状态，**不允许** active 指向半成品。本模块把
每一步都写进一个 append-only 的 journal（每条记录本身也是原子写入的不可变文件），
于是：

* 崩溃在"验证完成但尚未发布"→ journal 停在 ``validated``，目标文件不存在或仍是旧字节；
* 崩溃在"已发布但尚未注册"→ journal 停在 ``published``，索引不会把它当成 active；
* 崩溃在"已注册但指针未写"→ journal 停在 ``registered``（注册本身已是不可变记录）。

``scan_publication_transactions`` / ``incomplete_publications`` 让 doctor 与索引能一条命令
看到这些状态，而不是靠人猜"这个 JSON 为什么是半个"。
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.digest import digest_json
from code2paper.agentic.tool_runtime import atomic_write_bytes

PUBLICATION_SCHEMA_VERSION = "1.0"
JOURNAL_DIR_NAME = "publication_transactions"

PublicationStateV1 = Literal[
    "reserved",
    "validated",
    "published",
    "registered",
    # K02：一代产物的"已持久提交（成员+manifest 落盘）"与"active 已切换"两个状态。
    "committed",
    "switched",
    "complete",
    "incomplete",
]

#: 未走到 ``complete`` 的状态：都必须被当成"未完成的发布"。
UNFINISHED_STATES: frozenset[str] = frozenset(
    {"reserved", "validated", "published", "registered", "committed"}
)


class PublicationError(RuntimeError):
    """发布事务本身无法进行（路径越界、目标缺失等）。"""


def journal_dir(out_root: str | Path) -> Path:
    return Path(out_root).expanduser().resolve() / "artifacts" / JOURNAL_DIR_NAME


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class PublicationTransactionV1(BaseModel):
    """一次发布事务的 journal 记录（不可变，状态推进靠写新记录）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PUBLICATION_SCHEMA_VERSION
    transaction_id: str
    sequence: int = 1
    state: PublicationStateV1 = "reserved"
    logical_role: str
    phase: str
    generation: int = 1
    target_path: str
    file_bytes_digest: str = ""
    semantic_digest: str = ""
    producer: str = ""
    upstream_refs: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublicationTransactionV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", digest_json(payload))
        return self

    @property
    def unfinished(self) -> bool:
        return self.state in UNFINISHED_STATES

    def as_trace(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["unfinished"] = self.unfinished
        return payload


def _record_path(root: Path, record: PublicationTransactionV1) -> Path:
    token = record.content_digest.removeprefix("sha256:")[:16]
    return journal_dir(root) / (
        f"tx.{record.transaction_id.removeprefix('tx:')}."
        f"s{int(record.sequence)}.{record.state}.{token}.json"
    )


def _write_record(root: Path, record: PublicationTransactionV1) -> Path:
    path = _record_path(root, record)
    encoded = (record.model_dump_json(indent=2) + "\n").encode("utf-8")
    if path.is_file():
        if path.read_bytes() != encoded:  # pragma: no cover - 摘要冲突
            raise PublicationError(f"publication_record_conflict:{path.name}")
        return path
    atomic_write_bytes(path, encoded)
    return path


def scan_publication_transactions(
    out_root: str | Path,
) -> tuple[PublicationTransactionV1, ...]:
    """读取 journal；每个 transaction 只保留**最新序号**的记录。"""

    directory = journal_dir(out_root)
    if not directory.is_dir():
        return ()
    latest: dict[str, PublicationTransactionV1] = {}
    for path in sorted(directory.glob("tx.*.json")):
        try:
            record = PublicationTransactionV1.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue
        previous = latest.get(record.transaction_id)
        if previous is None or record.sequence >= previous.sequence:
            latest[record.transaction_id] = record
    return tuple(
        sorted(latest.values(), key=lambda item: (item.logical_role, item.phase, item.transaction_id))
    )


def incomplete_publications(
    out_root: str | Path,
) -> tuple[PublicationTransactionV1, ...]:
    """未走到 complete 的发布（含被验证拒绝的 incomplete）。"""

    return tuple(
        record
        for record in scan_publication_transactions(out_root)
        if record.state != "complete"
    )


def scan_orphan_temp_files(out_root: str | Path) -> tuple[str, ...]:
    """扫描原子写入留下的临时文件（进程中断的物理痕迹）。"""

    root = Path(out_root).expanduser().resolve()
    candidates = root / "artifacts"
    if not candidates.is_dir():
        return ()
    found: list[str] = []
    for path in candidates.rglob(".*.tmp"):
        if path.is_file():
            found.append(str(path.relative_to(root)))
    return tuple(sorted(found))


def _validate_payload(
    raw: bytes,
    *,
    validator: Callable[[Any], Sequence[str]] | None,
) -> tuple[Any, tuple[str, ...], str]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, ("publication_payload_unparsable",), ""
    failures: list[str] = []
    if validator is not None:
        failures.extend(str(item) for item in validator(payload) or ())
    semantic = ""
    if isinstance(payload, Mapping):
        for key in ("content_digest", "content_digest_sha256", "digest"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                semantic = value.strip()
                break
    return payload, tuple(failures), semantic


def publish_artifact_transaction(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
    target_path: str | Path,
    payload: bytes,
    generation: int = 1,
    producer: str = "",
    upstream_refs: Sequence[str] = (),
    validator: Callable[[Any], Sequence[str]] | None = None,
) -> PublicationTransactionV1:
    """按 §F.4 的顺序发布一个产物，并把每一步写进 journal。

    返回**最终状态**的记录（``complete`` / ``incomplete``）。验证失败时目标文件不会被
    创建或覆盖，索引也不会看到它。
    """

    root = Path(out_root).expanduser().resolve()
    target = Path(target_path)
    if not target.is_absolute():
        target = (root / target).resolve()
    else:
        target = target.resolve()
    if root != target and root not in target.parents:
        raise PublicationError(f"publication_path_escape:{target}")
    try:
        relative = str(target.relative_to(root))
    except ValueError as exc:  # pragma: no cover - 上面的检查已覆盖
        raise PublicationError(f"publication_path_escape:{target}") from exc

    raw = bytes(payload)
    file_digest = _sha256_bytes(raw)
    transaction_id = (
        "tx:"
        + digest_json(
            {
                "role": str(role),
                "phase": str(phase),
                "generation": int(generation),
                "path": relative,
                "bytes": file_digest,
            }
        ).removeprefix("sha256:")[:24]
    )

    def _record(
        sequence: int,
        state: PublicationStateV1,
        *,
        semantic_digest: str = "",
        failures: Sequence[str] = (),
    ) -> PublicationTransactionV1:
        record = PublicationTransactionV1(
            transaction_id=transaction_id,
            sequence=sequence,
            state=state,
            logical_role=str(role),
            phase=str(phase),
            generation=int(generation),
            target_path=relative,
            file_bytes_digest=file_digest,
            semantic_digest=semantic_digest,
            producer=str(producer),
            upstream_refs=tuple(
                dict.fromkeys(str(item) for item in upstream_refs if str(item).strip())
            ),
            failures=tuple(dict.fromkeys(str(item) for item in failures if str(item))),
        )
        _write_record(root, record)
        return record

    _record(1, "reserved")

    # 临时文件写在同一目录，保证 os.replace 是原子重命名。
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{os.getpid()}.publish.tmp"
    temporary.write_bytes(raw)
    try:
        _payload, failures, semantic_digest = _validate_payload(
            raw, validator=validator
        )
        if failures:
            temporary.unlink(missing_ok=True)
            return _record(2, "incomplete", failures=failures)
        _record(2, "validated", semantic_digest=semantic_digest)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    _record(3, "published", semantic_digest=semantic_digest)

    # 注册（审计 §F.1）本身就是不可变记录 + 原子指针；失败时保持 published 状态，
    # 索引不会把它当作 active。
    from code2paper.agentic.authoring_artifact_registry import (
        register_authoring_artifact,
    )

    register_authoring_artifact(
        root,
        role=role,
        phase=phase,
        path=target,
        generation=generation,
        payload=_payload,
        producer=producer,
        upstream_refs=upstream_refs,
    )
    _record(4, "registered", semantic_digest=semantic_digest)
    return _record(5, "complete", semantic_digest=semantic_digest)


def resolve_publication_authority_manifest(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
) -> tuple[Path, str] | None:
    """按持久发布 active 指针定位唯一 manifest。

    没有该 key 的指针时返回 ``None``（非一代产物继续走索引）。指针点名的摘要
    在磁盘上缺失、损坏或出现多份时失败，不回退到注册表 active 或派生索引。
    """

    root = Path(out_root).expanduser().resolve()
    pointer = load_active_publication_pointer(root)
    digest = str(pointer.active.get(f"{role}:{phase}") or "")
    if not digest:
        return None
    directory = publication_generation_dir(root)
    matches: list[Path] = []
    if directory.is_dir():
        for path in sorted(directory.glob("generation.*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise PublicationError(
                    f"publication_authority_unreadable:{path.name}"
                ) from exc
            if not isinstance(payload, Mapping):
                continue
            if str(payload.get("logical_role") or "") != str(role):
                continue
            if str(payload.get("phase") or "") != str(phase):
                continue
            if str(payload.get("content_digest") or "") == digest:
                matches.append(path)
    if len(matches) != 1:
        raise PublicationError(
            "publication_authority_unresolved:"
            f"{role}:{phase}:{digest}:matches={len(matches)}"
        )
    return matches[0], digest


__all__ = [
    "JOURNAL_DIR_NAME",
    "PUBLICATION_SCHEMA_VERSION",
    "PublicationError",
    "PublicationStateV1",
    "PublicationTransactionV1",
    "UNFINISHED_STATES",
    "incomplete_publications",
    "journal_dir",
    "publish_artifact_transaction",
    "scan_orphan_temp_files",
    "scan_publication_transactions",
]


# --------------------------------------------------------------------------- #
# K02：不可变成员 + manifest + CAS active（"先持久提交、后切换指针"）
# --------------------------------------------------------------------------- #
#
# 审计 §F.4/K02 要求一代产物的**成员集合**不可变：成员各自内容寻址落盘，manifest 绑定成员
# 字节/语义摘要与读集，状态先持久记录再切换 active。固定路径的单文件导出只是投影，
# **不得**再充当唯一成员存储。

PUBLICATION_MEMBER_DIR_NAME = "publication_members"
PUBLICATION_GENERATION_DIR_NAME = "publication_generations"
PUBLICATION_ACTIVE_NAME = "authoring_publication_active_v1.json"
GENERATION_SCHEMA_VERSION = "2.0"

#: 可注入的崩溃点（每个点表示"该写入已发生，进程随后死亡"）。生产路径不使用。
#: ``after_member_write`` 在 commit 里是成员校验之后，不是成员字节的持久写点；
#: 成员字节的持久点是 ``stage_publication_members`` 的 ``after_member_durable_write``。
CRASH_POINTS: tuple[str, ...] = (
    "after_reserved",
    "after_member_write",
    "after_validated",
    "after_manifest_write",
    "after_committed_record",
    "after_registered",
    "after_active_pointer_write",
    "after_active_switch",
)
STAGE_CRASH_POINTS: tuple[str, ...] = ("after_member_durable_write",)

#: 实际持久点。派生回执没有写点。导出投影由调用方写入，核验点在
#: ``verify_publication_generation``，不能把夹具写入算成 commit 的持久点。
PERSISTENCE_POINTS: tuple[dict[str, str], ...] = (
    {
        "id": "stage_member",
        "owner": "stage_publication_members",
        "crash": "after_member_durable_write",
        "kind": "durable_member_write",
    },
    {
        "id": "journal_reserved",
        "owner": "commit_publication_generation",
        "crash": "after_reserved",
        "kind": "journal_write",
    },
    {
        "id": "journal_validated",
        "owner": "commit_publication_generation",
        "crash": "after_validated",
        "kind": "journal_write",
    },
    {
        "id": "manifest",
        "owner": "commit_publication_generation",
        "crash": "after_manifest_write",
        "kind": "durable_manifest_write",
    },
    {
        "id": "journal_committed",
        "owner": "commit_publication_generation",
        "crash": "after_committed_record",
        "kind": "journal_write",
    },
    {
        "id": "registration_record",
        "owner": "prepare_artifact_registration",
        "crash": "after_registered",
        "kind": "immutable_record_then_journal",
    },
    {
        "id": "active_pointer",
        "owner": "switch_publication_active",
        "crash": "after_active_pointer_write",
        "kind": "durable_active_pointer",
    },
    {
        "id": "registry_activate",
        "owner": "activate_artifact_registration",
        "crash": "after_active_switch",
        "kind": "registry_pointer_after_publication_pointer",
    },
    {
        "id": "commit_receipt",
        "owner": "build_publication_receipt",
        "crash": "",
        "kind": "derived_no_write",
    },
    {
        "id": "export_projection",
        "owner": "generation_caller",
        "crash": "",
        "kind": "projection_verified_not_commit_write",
    },
)


class PublicationCasError(PublicationError):
    """CAS 失败：期望的 active 与磁盘上的当前 active 不一致（不覆盖新 active）。"""


class PublicationInterruptedError(PublicationError):
    """测试用崩溃注入：模拟"该写入点之后进程死亡"。"""

    def __init__(self, point: str) -> None:
        super().__init__(f"publication_interrupted:{point}")
        self.point = point


def publication_member_dir(out_root: str | Path, *, role: str, phase: str) -> Path:
    return (
        Path(out_root).expanduser().resolve()
        / "artifacts"
        / PUBLICATION_MEMBER_DIR_NAME
        / str(role)
        / str(phase)
    )


def publication_generation_dir(out_root: str | Path) -> Path:
    return (
        Path(out_root).expanduser().resolve()
        / "artifacts"
        / PUBLICATION_GENERATION_DIR_NAME
    )


def publication_active_pointer_path(out_root: str | Path) -> Path:
    return publication_generation_dir(out_root) / PUBLICATION_ACTIVE_NAME


def _member_token(payload: bytes) -> str:
    return _sha256_bytes(payload).removeprefix("sha256:")[:16]


def _member_content_digest(member: PublishedMemberV1) -> str:
    return digest_json(
        member.model_dump(mode="json", exclude={"content_digest"})
    )


class PublishedMemberV1(BaseModel):
    """一代产物里的一个**不可变成员**（内容寻址存储）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = GENERATION_SCHEMA_VERSION
    member_id: str
    logical_role: str
    phase: str
    path: str
    file_bytes_digest: str
    semantic_digest: str = ""
    artifact_schema_version: str = ""
    #: K02：成员媒体类型（json / markdown / bytes）；校验与读取都按它分支。
    media_type: str = "application/json"
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublishedMemberV1":
        object.__setattr__(self, "content_digest", _member_content_digest(self))
        return self


def _member_set_digest(members: Sequence[PublishedMemberV1]) -> str:
    return digest_json([
        {
            "member_id": item.member_id,
            "path": item.path,
            "file_bytes_digest": item.file_bytes_digest,
            "semantic_digest": item.semantic_digest,
            "artifact_schema_version": item.artifact_schema_version,
            "media_type": item.media_type,
        }
        for item in sorted(members, key=lambda row: row.member_id)
    ])


class PublicationManifestV1(BaseModel):
    """一代产物的冻结成员集合（manifest 本身也是不可变、封摘要的对象）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = GENERATION_SCHEMA_VERSION
    logical_role: str
    phase: str
    generation: int
    members: tuple[PublishedMemberV1, ...]
    member_set_digest: str = ""
    export_path: str = ""
    read_set: tuple[str, ...] = ()
    producer: str = ""
    upstream_refs: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublicationManifestV1":
        object.__setattr__(self, "members", tuple(sorted(self.members, key=lambda row: row.member_id)))
        object.__setattr__(self, "member_set_digest", _member_set_digest(self.members))
        object.__setattr__(
            self, "content_digest", _manifest_content_digest(self.model_dump(mode="json"))
        )
        return self

    def key(self) -> str:
        return f"{self.logical_role}:{self.phase}"

    def member_by_id(self) -> dict[str, PublishedMemberV1]:
        return {item.member_id: item for item in self.members}


def _manifest_content_digest(payload: Mapping[str, Any]) -> str:
    return digest_json(
        {key: value for key, value in payload.items() if key != "content_digest"}
    )


def bind_publication_manifest_bytes(
    raw: bytes,
    authority_digest: str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """读取期绑定 manifest：声明摘要、复算摘要和发布权威必须相同。

    创建期的模型 validator 会重算并写回摘要。这里只比较已经落盘的声明值，
    不把重封后的对象当作验证通过。
    """

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}, ("publication_manifest_half_written",)
    if not isinstance(payload, Mapping):
        return {}, ("publication_manifest_half_written",)
    declared = str(payload.get("content_digest") or "")
    recomputed = _manifest_content_digest(payload)
    if not declared or recomputed != declared or declared != str(authority_digest):
        return dict(payload), (
            "publication_manifest_digest_mismatch:"
            f"declared={declared}:recomputed={recomputed}:authority={authority_digest}",
        )
    return dict(payload), ()


def _manifest_path(root: Path, manifest: PublicationManifestV1) -> Path:
    token = manifest.content_digest.removeprefix("sha256:")[:16]
    return publication_generation_dir(root) / (
        f"generation.{manifest.logical_role}.{manifest.phase}."
        f"g{int(manifest.generation)}.{token}.json"
    )


class ActivePublicationPointerV1(BaseModel):
    """只增不改的 active 指针：每个 (role, phase) 一个 manifest 摘要 + fence 计数。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = GENERATION_SCHEMA_VERSION
    active: dict[str, str] = Field(default_factory=dict)
    fences: dict[str, int] = Field(default_factory=dict)
    history: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "ActivePublicationPointerV1":
        object.__setattr__(
            self,
            "content_digest",
            digest_json(self.model_dump(mode="json", exclude={"content_digest"})),
        )
        return self


def load_active_publication_pointer(
    out_root: str | Path,
) -> ActivePublicationPointerV1:
    """读取 active 指针；缺失 = 空指针，损坏/摘要不符 → fail-closed。"""

    path = publication_active_pointer_path(out_root)
    if not path.is_file():
        return ActivePublicationPointerV1()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationError(f"publication_active_unreadable:{path.name}") from exc
    if not isinstance(payload, Mapping):
        raise PublicationError(f"publication_active_unreadable:{path.name}")
    declared = str(payload.get("content_digest") or "")
    if not declared or _manifest_content_digest(payload) != declared:
        raise PublicationError("publication_active_digest_mismatch")
    try:
        pointer = ActivePublicationPointerV1.model_validate(dict(payload))
    except ValueError as exc:
        raise PublicationError("publication_active_invalid") from exc
    if pointer.content_digest != declared:
        raise PublicationError("publication_active_digest_mismatch")
    return pointer


def stage_publication_members(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
    members: Mapping[str, bytes] | Sequence[tuple[str, bytes]],
    semantic_digests: Mapping[str, str] | None = None,
    schema_versions: Mapping[str, str] | None = None,
    media_types: Mapping[str, str] | None = None,
    crash_at: str = "",
    crash_exit: bool = False,
) -> tuple[PublishedMemberV1, ...]:
    """把成员写入内容寻址的不可变存储；同内容幂等，同路径不同字节拒绝。

    K02：写入包含**文件与目录 fsync**，媒体类型随成员一起冻结。
    """

    if crash_at and crash_at not in STAGE_CRASH_POINTS:
        raise PublicationError(f"publication_unknown_crash_point:{crash_at}")
    root = Path(out_root).expanduser().resolve()
    directory = publication_member_dir(root, role=role, phase=phase)
    items = members.items() if isinstance(members, Mapping) else members
    staged: list[PublishedMemberV1] = []
    for member_id, payload in items:
        raw = bytes(payload)
        digest = _sha256_bytes(raw)
        token = _member_token(raw)
        path = directory / f"{member_id}.{token}.json"
        if path.is_file():
            if path.read_bytes() != raw:
                raise PublicationError(f"publication_member_conflict:{member_id}")
        else:
            _durable_write(path, raw)
            _maybe_crash(
                crash_at,
                "after_member_durable_write",
                crash_exit=crash_exit,
            )
        media_type = str(
            (media_types or {}).get(str(member_id), "application/json")
        )
        if media_type not in MEDIA_TYPES:
            raise PublicationError(f"publication_media_unsupported:{media_type}")
        staged.append(PublishedMemberV1(
            member_id=str(member_id),
            logical_role=str(role),
            phase=str(phase),
            path=str(path.relative_to(root)),
            file_bytes_digest=digest,
            semantic_digest=str((semantic_digests or {}).get(str(member_id), "")),
            artifact_schema_version=str((schema_versions or {}).get(str(member_id), "")),
            media_type=media_type,
        ))
    return tuple(sorted(staged, key=lambda row: row.member_id))


def build_publication_manifest(
    *,
    role: str,
    phase: str,
    generation: int,
    members: Sequence[PublishedMemberV1],
    export_path: str = "",
    read_set: Sequence[str] = (),
    producer: str = "",
    upstream_refs: Sequence[str] = (),
) -> PublicationManifestV1:
    return PublicationManifestV1(
        logical_role=str(role),
        phase=str(phase),
        generation=int(generation),
        members=tuple(members),
        export_path=str(export_path),
        read_set=tuple(dict.fromkeys(str(item) for item in read_set if str(item).strip())),
        producer=str(producer),
        upstream_refs=tuple(
            dict.fromkeys(str(item) for item in upstream_refs if str(item).strip())
        ),
    )


def _fsync_directory(path: Path) -> None:
    """把目录项本身刷盘（``atomic_write_bytes`` 只 fsync 文件内容）。"""

    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_write(path: Path, data: bytes) -> None:
    atomic_write_bytes(path, data)
    _fsync_directory(path.parent)


@contextmanager
def _active_switch_lock(root: Path):
    """active 切换的排他锁（持久 lock 文件 + flock）：比较与写入在同一临界区。"""

    lock_path = publication_generation_dir(root) / ".active.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


#: 成员媒体白名单。
MEDIA_TYPES: frozenset[str] = frozenset(
    {"application/json", "text/markdown", "application/octet-stream"}
)


def validate_member_media(
    raw: bytes, *, media_type: str, validator: Callable[[Any], Sequence[str]] | None
) -> tuple[Any, tuple[str, ...], str]:
    """按媒体类型校验成员字节：JSON / Markdown(UTF-8 文本) / bytes。

    返回 ``(payload, failures, declared_semantic_digest)``。Markdown 与 bytes 没有
    producer 模型可复算语义摘要时，只在**同一份字节**里读声明值。
    """

    normalized = str(media_type or "application/json")
    if normalized not in MEDIA_TYPES:
        return None, (f"publication_media_unsupported:{normalized}",), ""
    if normalized == "application/octet-stream":
        return None, (), ""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, (f"publication_media_not_utf8:{normalized}",), ""
    if normalized == "text/markdown":
        return text, (), ""
    try:
        payload = json.loads(text)
    except ValueError:
        return None, ("publication_payload_unparsable",), ""
    failures: list[str] = []
    if validator is not None:
        failures.extend(str(item) for item in validator(payload) or ())
    semantic = ""
    if isinstance(payload, Mapping):
        for key in ("content_digest", "content_digest_sha256", "digest"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                semantic = value.strip()
                break
    return payload, tuple(failures), semantic


def _maybe_crash(crash_at: str, point: str, *, crash_exit: bool = False) -> None:
    if crash_at != point:
        return
    if crash_exit:
        # 真实进程消失：不抛异常、不跑清理。调用方必须在子进程里使用。
        os._exit(86)
    raise PublicationInterruptedError(point)


def commit_publication_generation(
    out_root: str | Path,
    *,
    manifest: PublicationManifestV1,
    validator: Callable[[Any], Sequence[str]] | None = None,
    crash_at: str = "",
    crash_exit: bool = False,
) -> PublicationTransactionV1:
    """持久提交一代产物：成员 → 校验 → manifest → ``committed`` journal。

    **先持久记录、后切换指针**：本函数只做到 ``committed``（active 仍未变）；
    切换由 :func:`switch_publication_active` 单独做 CAS。崩溃点见 ``CRASH_POINTS``。
    """

    if crash_at and crash_at not in CRASH_POINTS:
        raise PublicationError(f"publication_unknown_crash_point:{crash_at}")
    root = Path(out_root).expanduser().resolve()
    transaction_id = (
        "tx:gen:"
        + digest_json({
            "role": manifest.logical_role,
            "phase": manifest.phase,
            "generation": int(manifest.generation),
            "manifest": manifest.content_digest,
        }).removeprefix("sha256:")[:24]
    )

    def _record(
        sequence: int,
        state: PublicationStateV1,
        *,
        failures: Sequence[str] = (),
    ) -> PublicationTransactionV1:
        record = PublicationTransactionV1(
            transaction_id=transaction_id,
            sequence=sequence,
            state=state,
            logical_role=manifest.logical_role,
            phase=manifest.phase,
            generation=int(manifest.generation),
            target_path=manifest.export_path or (
                f"artifacts/{PUBLICATION_GENERATION_DIR_NAME}/manifest.json"
            ),
            file_bytes_digest=manifest.content_digest,
            semantic_digest=manifest.member_set_digest,
            producer=manifest.producer,
            upstream_refs=manifest.upstream_refs,
            failures=tuple(dict.fromkeys(str(item) for item in failures if str(item))),
        )
        _write_record(root, record)
        return record

    _record(1, "reserved")
    _maybe_crash(crash_at, "after_reserved", crash_exit=crash_exit)

    failures: list[str] = []
    for member in manifest.members:
        member_path = root / member.path
        if member.logical_role != manifest.logical_role or member.phase != manifest.phase:
            failures.append(f"publication_member_role_mismatch:{member.member_id}")
            continue
        if not member_path.is_file():
            failures.append(f"publication_member_missing:{member.member_id}")
            continue
        raw = member_path.read_bytes()
        if _sha256_bytes(raw) != member.file_bytes_digest:
            failures.append(f"publication_member_bytes_mismatch:{member.member_id}")
            continue
        _payload, member_failures, semantic = validate_member_media(
            raw, media_type=member.media_type, validator=validator
        )
        failures.extend(f"{item}:{member.member_id}" for item in member_failures)
        if member.semantic_digest and semantic and member.semantic_digest != semantic:
            failures.append(f"publication_member_semantic_mismatch:{member.member_id}")
        if _member_content_digest(member) != member.content_digest:
            failures.append(f"publication_member_unsealed:{member.member_id}")
    _maybe_crash(crash_at, "after_member_write", crash_exit=crash_exit)
    if failures:
        return _record(2, "incomplete", failures=failures)
    _record(2, "validated")
    _maybe_crash(crash_at, "after_validated", crash_exit=crash_exit)

    manifest_path = _manifest_path(root, manifest)
    encoded = (manifest.model_dump_json(indent=2) + "\n").encode("utf-8")
    if manifest_path.is_file():
        if manifest_path.read_bytes() != encoded:
            raise PublicationError(f"publication_manifest_conflict:{manifest_path.name}")
    else:
        _durable_write(manifest_path, encoded)
    _maybe_crash(crash_at, "after_manifest_write", crash_exit=crash_exit)

    committed = _record(3, "committed")
    _maybe_crash(crash_at, "after_committed_record", crash_exit=crash_exit)

    # 登记（§F.1）：注册的**当前对象是这一代的 manifest**，成员由它绑定。登记失败时
    # journal 停在 committed —— 索引不会把这一代当作 active，恢复按"已提交未切换"处理。
    from code2paper.agentic.authoring_artifact_registry import (
        prepare_artifact_registration,
    )

    # 只**准备**不可变 registration record：注册表 active 的切换与权威 active 指针一起，
    # 在 CAS 成功之后进行（消除"manifest 一登记就抢先 active"的旁路）。
    prepare_artifact_registration(
        root,
        role=manifest.logical_role,
        phase=manifest.phase,
        path=manifest_path,
        generation=int(manifest.generation),
        payload=manifest.model_dump(mode="json"),
        producer=manifest.producer,
        upstream_refs=manifest.upstream_refs,
    )
    registered = _record(4, "registered")
    _maybe_crash(crash_at, "after_registered", crash_exit=crash_exit)
    return registered


def switch_publication_active(
    out_root: str | Path,
    *,
    manifest: PublicationManifestV1,
    expected_active_manifest_digest: str | None,
    expected_fence: int | None = None,
    crash_at: str = "",
    crash_exit: bool = False,
) -> ActivePublicationPointerV1:
    """在排他锁内比较 expected-active / fence，然后原子切换；不符即失败且不写。

    K02：``expected_fence`` 给出时必须等于当前 fence（旧 fence 的持有者不能覆盖新
    active）；比较与写入在同一临界区，两个并发的切换只有一个能成功。
    """

    root = Path(out_root).expanduser().resolve()
    with _active_switch_lock(root):
        return _switch_publication_active_locked(
            root,
            manifest=manifest,
            expected_active_manifest_digest=expected_active_manifest_digest,
            expected_fence=expected_fence,
            crash_at=crash_at,
            crash_exit=crash_exit,
        )


def _switch_publication_active_locked(
    root: Path,
    *,
    manifest: PublicationManifestV1,
    expected_active_manifest_digest: str | None,
    expected_fence: int | None,
    crash_at: str,
    crash_exit: bool = False,
) -> ActivePublicationPointerV1:
    pointer = load_active_publication_pointer(root)
    key = manifest.key()
    current = pointer.active.get(key)
    expected = expected_active_manifest_digest
    if (current or None) != (expected or None):
        raise PublicationCasError(
            "publication_active_cas_failed:"
            f"{key}:expected={expected or 'absent'}:current={current or 'absent'}"
        )
    current_fence = int(pointer.fences.get(key, 0))
    if expected_fence is not None and current_fence != int(expected_fence):
        raise PublicationCasError(
            "publication_active_fence_stale:"
            f"{key}:expected={int(expected_fence)}:current={current_fence}"
        )
    manifest_path = _manifest_path(root, manifest)
    if not manifest_path.is_file():
        raise PublicationError(
            f"publication_manifest_missing:{manifest_path.name}"
        )
    _maybe_crash(crash_at, "after_committed_record", crash_exit=crash_exit)
    from code2paper.agentic.authoring_artifact_registry import (
        activate_artifact_registration,
        prepare_artifact_registration,
    )

    # registration record 是**纯准备**（不改 active），放在权威指针之前；
    # 注册表 active 的切换在权威指针之后 —— 索引以权威指针为准。
    registration = prepare_artifact_registration(
        root,
        role=manifest.logical_role,
        phase=manifest.phase,
        path=manifest_path,
        generation=int(manifest.generation),
        payload=manifest.model_dump(mode="json"),
        producer=manifest.producer,
        upstream_refs=manifest.upstream_refs,
    )
    active = dict(pointer.active)
    fences = dict(pointer.fences)
    active[key] = manifest.content_digest
    fences[key] = int(fences.get(key, 0)) + 1
    history = tuple(dict.fromkeys((*pointer.history, manifest.content_digest)))
    updated = ActivePublicationPointerV1(
        active=active, fences=fences, history=history
    )
    pointer_path = publication_active_pointer_path(root)
    atomic_write_bytes(
        pointer_path, (updated.model_dump_json(indent=2) + "\n").encode("utf-8")
    )
    _fsync_directory(pointer_path.parent)
    _maybe_crash(crash_at, "after_active_pointer_write", crash_exit=crash_exit)
    activate_artifact_registration(root, registration)
    _maybe_crash(crash_at, "after_active_switch", crash_exit=crash_exit)
    return updated


def verify_publication_generation(
    out_root: str | Path,
    manifest_digest: str,
) -> tuple[str, ...]:
    """在同一次读取中重算 manifest 摘要与每个成员的字节摘要。

    返回具名失败（空 = 通过）：manifest 不可读/半写、摘要不符、成员缺失或字节漂移、
    成员集合摘要不符、导出路径漂移。
    """

    root = Path(out_root).expanduser().resolve()
    directory = publication_generation_dir(root)
    matches = sorted(directory.glob(
        f"generation.*.{manifest_digest.removeprefix('sha256:')[:16]}.json"
    ))
    if len(matches) != 1:
        # 文件名 token 不复用时（被改写后重新封摘要）按**重算摘要**定位，仍以内容为准；
        # 找不到才是真的缺失。
        matches = []
        for candidate in sorted(directory.glob("generation.*.json")):
            try:
                candidate_payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(candidate_payload, Mapping):
                continue
            if str(candidate_payload.get("content_digest") or "") == manifest_digest:
                matches.append(candidate)
    if len(matches) != 1:
        return (f"publication_manifest_missing:{manifest_digest}",)
    path = matches[0]
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return ("publication_manifest_half_written",)
    if not isinstance(payload, Mapping):
        return ("publication_manifest_half_written",)
    declared = str(payload.get("content_digest") or "")
    if not declared or _manifest_content_digest(payload) != declared:
        return ("publication_manifest_digest_mismatch",)
    if declared != manifest_digest:
        return ("publication_manifest_digest_mismatch",)
    try:
        manifest = PublicationManifestV1.model_validate(dict(payload))
    except ValueError:
        return ("publication_manifest_invalid",)
    failures: list[str] = []
    if manifest.content_digest != declared:
        failures.append("publication_manifest_digest_mismatch")
    recomputed: list[PublishedMemberV1] = []
    for member in manifest.members:
        if member.logical_role != manifest.logical_role or member.phase != manifest.phase:
            # 角色混代：成员自称的角色/阶段与 manifest 不一致 → 拒绝。
            failures.append(f"publication_member_role_mismatch:{member.member_id}")
            continue
        member_path = root / member.path
        if not member_path.is_file():
            failures.append(f"publication_member_missing:{member.member_id}")
            continue
        member_raw = member_path.read_bytes()
        member_payload: Any = None
        if str(member.media_type) == "application/json" and member_raw:
            try:
                member_payload = json.loads(member_raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                failures.append(f"publication_payload_unparsable:{member.member_id}")
                member_payload = None
        elif str(member.media_type) == "text/markdown":
            try:
                member_raw.decode("utf-8")
            except UnicodeDecodeError:
                failures.append(
                    f"publication_media_not_utf8:application/json:{member.member_id}"
                )
        digest = _sha256_bytes(member_raw)
        if digest != member.file_bytes_digest:
            failures.append(f"publication_member_bytes_mismatch:{member.member_id}")
        semantic = ""
        if isinstance(member_payload, Mapping):
            for key in ("content_digest", "content_digest_sha256", "digest"):
                value = member_payload.get(key)
                if isinstance(value, str) and value.strip():
                    semantic = value.strip()
                    break
        if member.semantic_digest and semantic and member.semantic_digest != semantic:
            failures.append(f"publication_member_semantic_mismatch:{member.member_id}")
        recomputed.append(member)
    if _member_set_digest(recomputed) != manifest.member_set_digest:
        failures.append("publication_member_set_mismatch")
    if manifest.export_path:
        export = root / manifest.export_path
        if not export.is_file():
            failures.append(f"publication_export_missing:{manifest.export_path}")
        else:
            export_digest = _sha256_bytes(export.read_bytes())
            if all(
                item.file_bytes_digest != export_digest for item in manifest.members
            ):
                failures.append(f"publication_export_drift:{manifest.export_path}")
    return tuple(dict.fromkeys(failures))


PublicationRecoveryStateV1 = Literal[
    "uncommitted",
    "committed_unswitched",
    "switched",
    "invalid",
]


def recover_publication_generation(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
    generation: int,
) -> tuple[PublicationRecoveryStateV1, tuple[str, ...], str]:
    """跨进程判定"未提交 / 已提交未切换 / 已切换"，并给出具名失败。

    返回 ``(state, failures, manifest_digest)``。判定只依据持久事实：generation 目录里的
    manifest、journal 的最新状态、active 指针；不依赖任何内存状态。
    """

    root = Path(out_root).expanduser().resolve()
    directory = publication_generation_dir(root)
    manifests = sorted(directory.glob(
        f"generation.{role}.{phase}.g{int(generation)}.*.json"
    ))
    journal = [
        record
        for record in scan_publication_transactions(root)
        if record.logical_role == str(role)
        and record.phase == str(phase)
        and int(record.generation) == int(generation)
    ]
    latest = max(journal, key=lambda item: item.sequence) if journal else None
    if not manifests:
        return ("uncommitted", (), "")
    if len(manifests) > 1:
        return ("invalid", ("publication_multiple_manifests",), "")
    try:
        payload = json.loads(manifests[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ("invalid", ("publication_manifest_half_written",), "")
    digest = str(payload.get("content_digest") or "")
    failures = verify_publication_generation(root, digest)
    if failures:
        return ("invalid", failures, digest)
    # 持久提交点是**manifest 及其成员可复核**，不是 journal 记录：崩溃可能正好落在
    # "manifest 已落盘、committed 记录未写"之间，那种情况仍是"已提交未切换"。
    try:
        pointer = load_active_publication_pointer(root)
    except PublicationError as exc:
        return ("invalid", (str(exc),), digest)
    active = pointer.active.get(f"{role}:{phase}")
    if active == digest:
        return ("switched", (), digest)
    return ("committed_unswitched", (), digest)


class PublicationReceiptV1(BaseModel):
    """**派生**提交回执：只从已持久事实重建，不需要"先有回执才能激活"。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = GENERATION_SCHEMA_VERSION
    logical_role: str
    phase: str
    generation: int = 0
    manifest_digest: str = ""
    member_set_digest: str = ""
    member_digests: dict[str, str] = Field(default_factory=dict)
    fence: int = 0
    state: PublicationRecoveryStateV1 = "invalid"
    active: bool = False
    registration_id: str = ""
    rebuilt_from: tuple[str, ...] = ()
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "PublicationReceiptV1":
        object.__setattr__(
            self,
            "content_digest",
            digest_json(self.model_dump(mode="json", exclude={"content_digest"})),
        )
        return self


def build_publication_receipt(
    out_root: str | Path,
    *,
    role: str,
    phase: str,
) -> PublicationReceiptV1:
    """从 manifest + 权威指针 + journal 重建提交回执（无写入、可反复重建）。"""

    root = Path(out_root).expanduser().resolve()
    pointer = load_active_publication_pointer(root)
    key = f"{role}:{phase}"
    active_digest = pointer.active.get(key, "")
    fence = int(pointer.fences.get(key, 0))
    rebuilt: list[str] = []
    generation = 0
    manifest_digest = ""
    member_set_digest = ""
    member_digests: dict[str, str] = {}
    state: PublicationRecoveryStateV1 = "invalid"
    if active_digest:
        manifest_digest = active_digest
        candidates = [
            path
            for path in sorted(publication_generation_dir(root).glob("generation.*.json"))
            if path.name != PUBLICATION_ACTIVE_NAME
        ]
        for candidate in candidates:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(payload, Mapping):
                continue
            if str(payload.get("content_digest") or "") != manifest_digest:
                continue
            generation = int(payload.get("generation") or 0)
            member_set_digest = str(payload.get("member_set_digest") or "")
            rebuilt.append(str(candidate.relative_to(root)))
            state, _failures, _digest = recover_publication_generation(
                root, role=role, phase=phase, generation=generation
            )
            for item in payload.get("members") or ():
                if isinstance(item, Mapping):
                    member_id = str(item.get("member_id") or "")
                    member_digests[member_id] = str(item.get("file_bytes_digest") or "")
                    rebuilt.append(str(item.get("path") or ""))
            break
    registration_id = ""
    from code2paper.agentic.authoring_artifact_registry import (
        load_artifact_registry,
    )

    try:
        registry = load_artifact_registry(root)
        registration_id = registry.active.get(key, "")
        rebuilt.append(f"artifacts/{PUBLICATION_GENERATION_DIR_NAME}/" + PUBLICATION_ACTIVE_NAME)
    except Exception:  # noqa: BLE001 - 回执重建失败不掩盖已有事实
        registration_id = ""
    return PublicationReceiptV1(
        logical_role=str(role),
        phase=str(phase),
        generation=generation,
        manifest_digest=manifest_digest,
        member_set_digest=member_set_digest,
        member_digests=member_digests,
        fence=fence,
        state=state,
        active=bool(active_digest) and state == "switched",
        registration_id=registration_id,
        rebuilt_from=tuple(item for item in rebuilt if item),
    )


__all__ += [
    "PublicationReceiptV1",
    "build_publication_receipt",
    "ActivePublicationPointerV1",
    "CRASH_POINTS",
    "PERSISTENCE_POINTS",
    "STAGE_CRASH_POINTS",
    "GENERATION_SCHEMA_VERSION",
    "PublicationCasError",
    "PublicationInterruptedError",
    "PublicationManifestV1",
    "PublicationRecoveryStateV1",
    "PublishedMemberV1",
    "PUBLICATION_ACTIVE_NAME",
    "PUBLICATION_GENERATION_DIR_NAME",
    "PUBLICATION_MEMBER_DIR_NAME",
    "bind_publication_manifest_bytes",
    "build_publication_manifest",
    "commit_publication_generation",
    "load_active_publication_pointer",
    "publication_active_pointer_path",
    "publication_generation_dir",
    "publication_member_dir",
    "recover_publication_generation",
    "resolve_publication_authority_manifest",
    "stage_publication_members",
    "switch_publication_active",
    "verify_publication_generation",
]
