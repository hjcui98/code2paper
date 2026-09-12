from pathlib import Path
import json

import pytest

from code2paper.agentic.autonomous_method_agent import run_autonomous_method_agent
from code2paper.agentic.publication_method_writer import _load_repository_authoring_context
from code2paper.agentic.repo_snapshot import build_repo_snapshot, write_repo_snapshot
from code2paper.schemas import LLMConfig, LLMProvider


def test_product_writer_receives_current_research_manifest(tmp_path, monkeypatch):
    from code2paper.agentic import autonomous_method_agent as product

    fixture = Path(__file__).parent / "fixtures"
    captured = {}

    def writer(**kwargs):
        captured.update(kwargs["artifact_paths"])
        return {}, "blocked", "test_writer_boundary"

    monkeypatch.setattr(product, "_run_writer_surface", writer)
    out = tmp_path / "out"
    (out / "artifacts").mkdir(parents=True)
    # A leftover from an older output lane must not enter this run's manifest.
    (out / "artifacts" / "method_propositions_v1.json").write_text("{}")
    result = run_autonomous_method_agent(
        repo_path=fixture / "research_loop_project",
        author_intent_path=fixture / "research_loop_project_author_markers.yaml",
        out_root=out,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="", cache=False),
        max_research_turns=12,
        write_method_text=True,
    )
    for key in ("repo_snapshot_v2", "symbol_index_v2", "method_argument_briefs_v1"):
        assert key in captured
        assert captured[key] == result.artifact_paths[key]
    assert "method_propositions_v1" not in captured
    context = _load_repository_authoring_context(captured)
    assert context["argument_briefs"] is not None
    assert context["symbol_index"].symbols
    assert context["source_provider"]
    assert context["repo_snapshot"].snapshot_id == context["symbol_index"].repo_snapshot_id


@pytest.fixture
def snapshot_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "helper.py").write_text("def normalize(x):\n    return x / sum(x)\n", encoding="utf-8")
    (repo / "main.py").write_text("from helper import normalize\ndef run(x):\n    return normalize(x)\n", encoding="utf-8")
    snapshot = build_repo_snapshot(repo)
    path = write_repo_snapshot(tmp_path / "snapshot.json", snapshot)
    return repo, {"repo_snapshot_v2": str(path)}


def test_loaded_source_is_stable_after_worktree_changes(snapshot_paths):
    from code2paper.agentic.mechanism_context_compiler import DefinitionResolver

    repo, paths = snapshot_paths
    context = _load_repository_authoring_context(paths)
    resolver = DefinitionResolver(context["symbol_index"], context["source_provider"])
    helper = resolver.resolve_symbol("normalize", current_path="main.py")
    assert helper.path == "helper.py"
    assert "return x / sum(x)" in resolver.read_definition_body(helper)
    (repo / "helper.py").write_text("# replaced", encoding="utf-8")
    assert "return x / sum(x)" in context["source_provider"]["helper.py"]
    with pytest.raises(ValueError, match="repository_source_drift"):
        _load_repository_authoring_context(paths)


def test_mixed_snapshot_symbol_index_is_rejected(snapshot_paths, tmp_path):
    _, paths = snapshot_paths
    context = _load_repository_authoring_context(paths)
    index = context["symbol_index"].model_dump(mode="json")
    index["repo_snapshot_id"] = "repo:another-run"
    path = tmp_path / "index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="identity_mismatch"):
        _load_repository_authoring_context({**paths, "symbol_index_v2": str(path)})


@pytest.mark.parametrize("key", ["code_facts_v1", "atomic_claims_v3", "evidence_packets_v3"])
def test_mixed_research_evidence_identity_is_rejected(snapshot_paths, tmp_path, key):
    _, paths = snapshot_paths
    path = tmp_path / "other-run.json"
    path.write_text(json.dumps({"repo_snapshot_id": "repo:other", "project_tree_hash": "sha256:other"}))
    with pytest.raises(ValueError, match="identity_mismatch"):
        _load_repository_authoring_context({**paths, key: str(path)})


@pytest.mark.parametrize("key", ["repo_snapshot_v2", "symbol_index_v2", "method_argument_briefs_v1", "behavior_graph_v1"])
def test_explicit_invalid_artifact_is_not_silently_dropped(tmp_path, key):
    path = tmp_path / "invalid.json"
    path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact_invalid"):
        _load_repository_authoring_context({key: str(path)})
