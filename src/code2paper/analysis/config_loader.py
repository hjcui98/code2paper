"""Config ingestion facade."""

from __future__ import annotations

from pathlib import Path

from code2paper.analysis.ingestion import _EvidenceCounter, _ingest_config
from code2paper.core.schemas import EvidenceItem


def load_config_evidence(path: str | Path, *, rel_path: str | None = None) -> EvidenceItem:
    path = Path(path)
    return _ingest_config(path, rel_path or path.as_posix(), _EvidenceCounter())

