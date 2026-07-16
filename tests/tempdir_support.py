from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / ".tmp" / "test_workspaces"


@contextmanager
def workspace_tempdir():
    base_root = _resolve_temp_root()
    path = base_root / f"tmp-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _resolve_temp_root() -> Path:
    for candidate in (
        TEMP_ROOT,
        Path(tempfile.gettempdir()) / "code2paper_test_workspaces",
    ):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / f".probe-{uuid.uuid4().hex}"
            probe.mkdir()
            probe.rmdir()
            return candidate
        except OSError:
            continue
    raise PermissionError("Could not create a writable temporary workspace for tests.")
