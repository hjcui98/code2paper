"""Python source ingestion facade."""

from __future__ import annotations

from pathlib import Path

from .ingestion import _EvidenceCounter, _ingest_python_source
from .schemas import EvidenceItem


def load_python_source_evidence(path: str | Path, *, rel_path: str | None = None) -> list[EvidenceItem]:
    path = Path(path)
    return _ingest_python_source(path, rel_path or path.as_posix(), _EvidenceCounter())

