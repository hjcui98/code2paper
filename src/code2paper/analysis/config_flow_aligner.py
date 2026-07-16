"""Config resolution helpers for Phase 2 alignment."""

from __future__ import annotations

from code2paper.analysis.alignment import _extract_config_resolutions
from code2paper.core.schemas import ConfigResolution, RawEvidencePack


def extract_config_resolutions(raw_pack: RawEvidencePack) -> list[ConfigResolution]:
    return _extract_config_resolutions(raw_pack)

