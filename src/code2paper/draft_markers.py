"""Compatibility wrapper around the shared draft_markers implementation."""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


@lru_cache(maxsize=1)
def _load_shared_module():
    here = Path(__file__).resolve()
    shared_candidates = [
        Path(os.environ["CODE2PAPER_SHARED_DRAFT_MARKERS"]).expanduser().resolve()
        if os.environ.get("CODE2PAPER_SHARED_DRAFT_MARKERS") else here.parent / "_missing_shared_draft_markers.py",
        here.parents[3] / "code2paper_agent" / "src" / "code2paper" / "draft_markers.py",
        here.parents[4] / "code2paper_agent" / "src" / "code2paper" / "draft_markers.py",
    ]
    shared_path = next((candidate for candidate in shared_candidates if candidate.exists()), shared_candidates[0])
    if not shared_path.exists():
        searched = ", ".join(str(candidate) for candidate in shared_candidates)
        raise FileNotFoundError(f"shared draft_markers not found. Searched: {searched}")
    spec = importlib.util.spec_from_file_location("code2paper_agent_shared_draft_markers", shared_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load shared draft_markers module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DEFAULT_IGNORE_FILES = ["README.md", "paper.pdf", "__pycache__/**", ".git/**"]


class DraftMarkersRefinementOutput(BaseModel):
    """Import-safe public response shape; the full bootstrap implementation is lazy."""

    model_config = ConfigDict(extra="allow")
    status: str = "ok"
    module_role_supports: list[dict] = Field(default_factory=list)
    pipeline_step_supports: list[dict] = Field(default_factory=list)
    priority_files: list[str] = Field(default_factory=list)
    design_intent_supports: list[dict] = Field(default_factory=list)
    innovation_claim_supports: list[dict] = Field(default_factory=list)
    ignore_file_reviews: list[dict] = Field(default_factory=list)
    potential_mismatches: list[dict] = Field(default_factory=list)
    rationale: str = ""


def _call(name: str, *args, **kwargs):
    return getattr(_load_shared_module(), name)(*args, **kwargs)


def dump_yaml(*args, **kwargs):
    return _call("dump_yaml", *args, **kwargs)


def load_stage_artifacts(*args, **kwargs):
    return _call("load_stage_artifacts", *args, **kwargs)


def load_stage_json(*args, **kwargs):
    return _call("load_stage_json", *args, **kwargs)


def load_yaml(*args, **kwargs):
    return _call("load_yaml", *args, **kwargs)


def refine_markers_from_stage12(*args, **kwargs):
    return _call("refine_markers_from_stage12", *args, **kwargs)


def refine_markers_with_llm(*args, **kwargs):
    return _call("refine_markers_with_llm", *args, **kwargs)


def run_code2flow_scan(*args, **kwargs):
    return _call("run_code2flow_scan", *args, **kwargs)


def suggest_mechanism_keywords(*args, **kwargs):
    return _call("suggest_mechanism_keywords", *args, **kwargs)


def validate_author_markers_payload(*args, **kwargs):
    return _call("validate_author_markers_payload", *args, **kwargs)


def build_coarse_markers_payload(*, draft_payload, scan_report, project_root):
    return _call(
        "build_coarse_markers_payload",
        draft_payload=draft_payload,
        scan_report=scan_report,
        project_root=project_root,
    )

__all__ = [
    "DEFAULT_IGNORE_FILES",
    "DraftMarkersRefinementOutput",
    "build_coarse_markers_payload",
    "dump_yaml",
    "load_stage_artifacts",
    "load_stage_json",
    "load_yaml",
    "refine_markers_from_stage12",
    "refine_markers_with_llm",
    "run_code2flow_scan",
    "suggest_mechanism_keywords",
    "validate_author_markers_payload",
]
