"""Config resolution helpers for Phase 2 alignment."""

from __future__ import annotations

from .alignment import _extract_config_resolutions
from .schemas import ConfigResolution, RawEvidencePack


def extract_config_resolutions(raw_pack: RawEvidencePack) -> list[ConfigResolution]:
    return _extract_config_resolutions(raw_pack)

