from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from code2paper.agentic.evidence_compiler_v3 import (
    compile_evidence_v3,
    write_compiler_v3_artifacts,
)
import code2paper.agentic.evidence_compiler_v3 as compiler_v3_module
from code2paper.agentic.evidence_profiles.rap_pruning import RapPruningProfile
from code2paper.agentic.evidence_profiles.registry import (
    EvidenceProfileRegistry,
    default_evidence_profile_registry,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from tests.test_agentic_evidence_compiler_v3 import _write_fixture


def test_registry_selects_profile_from_executable_structure(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is not None
    assert profile.profile_id == "feature_predict_score_rank_filter"
    assert matches[0].matched
    assert not matches[0].missing_required_fingerprints


def test_profile_does_not_activate_from_project_name_only(tmp_path: Path) -> None:
    (tmp_path / "RAP_feature_predict_score_rank_filter.txt").write_text(
        "RAP pruning predictor score rank mask", encoding="utf-8"
    )
    snapshot = build_repo_snapshot(tmp_path)
    profile, matches = default_evidence_profile_registry().select(snapshot)
    assert profile is None
    assert not matches[0].matched
    assert matches[0].missing_required_fingerprints


def test_required_symbol_mutation_prevents_profile_activation(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / "prune_percent.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "def prune_pure_feature", "def renamed_pruning_entrypoint"
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(tmp_path)
    assert compile_evidence_v3(snapshot) is None


def test_registry_rejects_duplicate_profile_ids() -> None:
    registry = EvidenceProfileRegistry()
    registry.register(RapPruningProfile())
    with pytest.raises(ValueError, match="duplicate evidence profile id"):
        registry.register(RapPruningProfile())


def test_selected_profile_and_match_are_persisted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    artifacts = tmp_path / "artifacts"
    _write_fixture(project)
    result = compile_evidence_v3(build_repo_snapshot(project))
    assert result is not None
    assert result.profile_id == "feature_predict_score_rank_filter"
    assert result.profile_match["matched"] is True

    paths = write_compiler_v3_artifacts(artifacts, result)
    payload = json.loads(Path(paths["evidence_profile_match"]).read_text(encoding="utf-8"))
    assert payload["profile_id"] == result.profile_id
    assert payload["profile_match"]["missing_required_fingerprints"] == []
    assert payload["repo_snapshot_id"] == result.packets.repo_snapshot_id


def test_common_compiler_contains_no_rap_project_literals() -> None:
    source = inspect.getsource(compiler_v3_module)
    for forbidden in (
        "F-RAP-",
        "C-RAP-",
        "EP-RAP-",
        "C-EBC-",
        "F-EBC-",
        "EBCAR",
        "C-DYG-",
        "F-DYG-",
        "DyG-Mamba",
        "C-LR-",
        "F-LR-",
        "LinearRAG",
        "prune_pure_feature",
        "get_prune_input_f15",
        "Softmax(dim=1)",
    ):
        assert forbidden not in source
