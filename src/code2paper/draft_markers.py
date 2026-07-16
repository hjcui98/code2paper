"""Compatibility wrapper around the shared draft_markers implementation."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_shared_module():
    here = Path(__file__).resolve()
    shared_candidates = [
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


_shared = _load_shared_module()
if hasattr(_shared, "DraftMarkersRefinementOutput"):
    _shared.DraftMarkersRefinementOutput.model_rebuild(_types_namespace=vars(_shared))

DEFAULT_IGNORE_FILES = _shared.DEFAULT_IGNORE_FILES
DraftMarkersRefinementOutput = _shared.DraftMarkersRefinementOutput
dump_yaml = _shared.dump_yaml
load_stage_artifacts = _shared.load_stage_artifacts
load_stage_json = _shared.load_stage_json
load_yaml = _shared.load_yaml
refine_markers_from_stage12 = _shared.refine_markers_from_stage12
refine_markers_with_llm = _shared.refine_markers_with_llm
run_code2flow_scan = _shared.run_code2flow_scan
suggest_mechanism_keywords = _shared.suggest_mechanism_keywords
validate_author_markers_payload = _shared.validate_author_markers_payload


def build_coarse_markers_payload(*, draft_payload, scan_report, project_root):
    return _shared.build_coarse_markers_payload(
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
