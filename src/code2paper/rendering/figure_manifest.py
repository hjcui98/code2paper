from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from code2paper.rendering.scene_svg import file_sha256


class StructuredFigureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2.0"
    producer_version: str = "code2paper-agentic-p2"
    renderer: str = "deterministic-svg-v1"
    scene_digest: str
    asset_path: str
    asset_digest: str
    status: str = "rendered"


def build_figure_manifest(*, scene_digest: str, asset_path: str | Path) -> StructuredFigureManifest:
    return StructuredFigureManifest(scene_digest=scene_digest, asset_path=str(asset_path), asset_digest=file_sha256(asset_path))


def write_figure_manifest(path: str | Path, manifest: StructuredFigureManifest) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(manifest.model_dump_json(indent=2), encoding="utf-8"); return output
