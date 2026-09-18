"""WP0 事故回归的离线约束（方案 §4.3、§12.1）。

* 任何真实网络访问被硬拒绝——离线回归不得触碰 provider / endpoint；
* 归档目录在会话期间必须逐字节不变（只读证据，不是工作目录）。
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from . import incident_archive


class NetworkAccessForbidden(RuntimeError):
    """离线回归中出现了真实网络访问尝试。"""


def _blocked(*args: object, **kwargs: object) -> None:
    raise NetworkAccessForbidden(
        "tests/regression_20260917 为离线回归：禁止真实网络访问"
    )


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "gethostbyname", _blocked)


@pytest.fixture(scope="session", autouse=True)
def _archive_stays_frozen() -> None:
    """证明本次回归没有改写归档（S0 准出标准之一）。"""

    watched = {
        key: incident_archive.archive_path(key).stat()
        for key in incident_archive.PINNED
    }
    yield
    for key, before in watched.items():
        after = incident_archive.archive_path(key).stat()
        assert (after.st_size, after.st_mtime_ns) == (
            before.st_size,
            before.st_mtime_ns,
        ), f"归档文件在回归期间被修改: {incident_archive.PINNED[key].path}"


@pytest.fixture(scope="session")
def archive_root() -> Path:
    return incident_archive.archive_root()
