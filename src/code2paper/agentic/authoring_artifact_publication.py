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

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
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
    "complete",
    "incomplete",
]

#: 未走到 ``complete`` 的状态：都必须被当成"未完成的发布"。
UNFINISHED_STATES: frozenset[str] = frozenset(
    {"reserved", "validated", "published", "registered"}
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
