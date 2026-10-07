"""Kernel-issued immutable byte handles; paths never cross the RPC boundary."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code2paper.agentic.digest import canonical_json_bytes, digest_bytes, digest_json
from .protocol import ProtocolError, strict_json_loads
from .writer_contract import ArtifactRefV1

MAX_ARTIFACT_BYTES = 16 << 20


@dataclass(frozen=True)
class TaskScope:
    execution_id: str
    task_id: str
    task_epoch: int


class ArtifactStore:
    """Only trusted Host bootstrap chooses the root and scope.

    Exclusive creation and fsync preserve original bytes. A partial interrupted
    write is an explicit integrity failure, never silently resealed on retry.
    """
    def __init__(self, root: Path, scope: TaskScope):
        self.root = Path(root).resolve()
        self.scope = scope
        self.directory = self.root / "dsh-artifacts" / digest_json(scope.__dict__).split(":")[1]
        self.directory.mkdir(parents=True,exist_ok=True)

    @classmethod
    def open_readonly(cls, root: Path, scope: TaskScope):
        """Open existing immutable handles without creating an artifact root."""
        owner = object.__new__(cls)
        owner.root = Path(root).resolve(strict=True)
        owner.scope = scope
        owner.directory = owner.root / "dsh-artifacts" / digest_json(scope.__dict__).split(":")[1]
        if not owner.directory.is_dir() or owner.directory.is_symlink():
            raise ProtocolError("artifact_unavailable")
        owner._readonly = True
        return owner

    def _check_scope(self, ref: ArtifactRefV1):
        if (ref.execution_id,ref.task_id,ref.task_epoch) != (self.scope.execution_id,self.scope.task_id,self.scope.task_epoch):
            raise ProtocolError("artifact_scope_mismatch")
        if ref.byte_length > MAX_ARTIFACT_BYTES:
            raise ProtocolError("artifact_too_large")

    def put(self, raw: bytes, *, media_type: str = "application/octet-stream", semantic_digest: str | None = None) -> ArtifactRefV1:
        if getattr(self, "_readonly", False): raise ProtocolError("artifact_readonly")
        if len(raw) > MAX_ARTIFACT_BYTES: raise ProtocolError("artifact_too_large")
        digest=digest_bytes(raw)
        ref=ArtifactRefV1(schema_version="ArtifactRefV1", artifact_id=digest,
            execution_id=self.scope.execution_id,task_id=self.scope.task_id,task_epoch=self.scope.task_epoch,
            media_type=media_type,byte_length=len(raw),bytes_digest=digest,semantic_digest=semantic_digest)
        path=self.directory/digest.split(":")[1]
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        except FileExistsError:
            if self.read(ref) != raw: raise ProtocolError("artifact_collision")
            return ref
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        directory_fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(directory_fd)
        finally: os.close(directory_fd)
        return ref

    def put_json(self, value: Any) -> ArtifactRefV1:
        raw=canonical_json_bytes(value)
        strict_json_loads(raw,max_bytes=MAX_ARTIFACT_BYTES)
        return self.put(raw,media_type="application/json",semantic_digest=digest_bytes(raw))

    def read(self, ref: ArtifactRefV1) -> bytes:
        self._check_scope(ref)
        path=self.directory/ref.artifact_id.split(":")[1]
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,"rb") as stream:
                raw=stream.read(MAX_ARTIFACT_BYTES+1)
        except OSError as error:
            raise ProtocolError("artifact_unavailable") from error
        if len(raw) != ref.byte_length or digest_bytes(raw) != ref.bytes_digest:
            raise ProtocolError("artifact_bytes_mismatch")
        return raw

    def read_json(self, ref: ArtifactRefV1) -> Any:
        if ref.media_type != "application/json": raise ProtocolError("artifact_media_mismatch")
        value=strict_json_loads(self.read(ref),max_bytes=MAX_ARTIFACT_BYTES)
        if ref.semantic_digest != digest_json(value): raise ProtocolError("artifact_semantic_mismatch")
        return value
