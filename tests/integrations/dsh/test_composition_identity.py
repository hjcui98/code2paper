"""I01: actual bytes, Loader position, links and validator source coverage."""
from pathlib import Path

import pytest

from code2paper.agentic.authoring_execution_identity import (
    CompositionSpecV1, _COMPOSITION_FILES, _COMPOSITION_TREES,
    capture_execution_composition, capture_validator_bundle_snapshot,
    runtime_inventory, validate_execution_composition,
)

ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def composition(tmp_path):
    files={}
    for name in _COMPOSITION_FILES:
        path=tmp_path/name; path.write_bytes(name.encode()); files[name]=path
    trees={}
    for name in _COMPOSITION_TREES:
        path=tmp_path/name; path.mkdir(); (path/"module.js").write_text("exports.x = 1"); trees[name]=path
    return CompositionSpecV1(files=files,trees=trees,effective_config=dict(model="test-only",options={},worker_version="1",renderer_version="1",tokenizer_version="1",meter_version="1"))


@pytest.mark.parametrize("source",["bundle_js","peer","renderer","node"])
def test_actual_file_drift_without_source_or_lock_change(composition,source):
    expected=capture_execution_composition(composition,engine_root=ROOT)
    composition.files[source].write_bytes(b"changed runtime only")
    with pytest.raises(ValueError,match="composition_drift"):
        validate_execution_composition(composition,expected,engine_root=ROOT)


def test_dependency_tree_bytes_and_symlink_target(composition):
    root=composition.trees["dependencies"]; (root/"linked.js").symlink_to("module.js")
    expected=capture_execution_composition(composition,engine_root=ROOT)
    (root/"module.js").write_text("changed")
    with pytest.raises(ValueError,match="composition_drift"):
        validate_execution_composition(composition,expected,engine_root=ROOT)


def test_loader_resolution_same_bytes_different_position(composition,tmp_path):
    original=composition.files["loader"]
    expected=capture_execution_composition(composition,engine_root=ROOT)
    other=tmp_path/"other-loader"; other.write_bytes(original.read_bytes())
    composition.files["loader"]=other
    with pytest.raises(ValueError,match="composition_drift"):
        validate_execution_composition(composition,expected,engine_root=ROOT)


def test_source_missing_and_external_link_fail_closed(composition,tmp_path):
    composition.files["renderer"].unlink()
    with pytest.raises(ValueError,match="composition_source_missing:renderer"):
        capture_execution_composition(composition,engine_root=ROOT)
    (composition.trees["runtime"]/"external").symlink_to(tmp_path/"loader")
    with pytest.raises(ValueError,match="external_or_absolute_symlink"):
        runtime_inventory(composition.trees["runtime"])


def test_validator_changes_when_new_decision_helper_changes(tmp_path):
    from code2paper.agentic.authoring_execution_identity import VALIDATOR_BUNDLE_SOURCES
    for name in VALIDATOR_BUNDLE_SOURCES:
        path=tmp_path/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes((ROOT/name).read_bytes())
    # resolve_engine_root requires these markers, without changing actual source coverage.
    (tmp_path/"pyproject.toml").write_text("[project]\nname='test'\n")
    first=capture_validator_bundle_snapshot(tmp_path)
    helper=tmp_path/"src/code2paper/integrations/dsh/protocol.py"
    assert helper.is_file()
    helper.write_text(helper.read_text()+"\n# changed decision source\n")
    assert capture_validator_bundle_snapshot(tmp_path).digest != first.digest
    helper.unlink()
    missing=capture_validator_bundle_snapshot(tmp_path)
    assert not missing.is_usable and str(helper.relative_to(tmp_path)) in missing.missing


def test_inventory_does_not_seal_mixed_engine_states(composition,monkeypatch):
    from dataclasses import replace
    from code2paper.agentic import authoring_execution_identity as identity
    original=identity.capture_engine_source_snapshot
    calls=[]
    def changed(root):
        value=original(root);calls.append(value)
        return value if len(calls)==1 else replace(value,source_digest='sha256:'+'0'*64)
    monkeypatch.setattr(identity,'capture_engine_source_snapshot',changed)
    with pytest.raises(ValueError,match='composition_source_unstable'):
        capture_execution_composition(composition,engine_root=ROOT)


def test_tree_root_resolution_relationship_is_identity(composition,tmp_path):
    original=composition.trees['dependencies'];first=tmp_path/'tree-link-a';second=tmp_path/'tree-link-b'
    first.symlink_to(original,target_is_directory=True);second.symlink_to(original,target_is_directory=True)
    composition.trees['dependencies']=first
    frozen=capture_execution_composition(composition,engine_root=ROOT)
    composition.trees['dependencies']=second
    with pytest.raises(ValueError,match='composition_drift'):
        validate_execution_composition(composition,frozen,engine_root=ROOT)
