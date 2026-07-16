"""Author marker loading helpers."""

from __future__ import annotations

from pathlib import Path

import yaml

from code2paper.core.schemas import AuthorMarkers


def load_author_markers(path: str | Path) -> AuthorMarkers:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return AuthorMarkers.model_validate(payload)

