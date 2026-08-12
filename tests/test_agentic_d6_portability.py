"""D6 vertical proof: registry language path and provider-neutral trust gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph as build_behavior_graph
from code2paper.agentic.execution_profile import (
    ExecutionProfileV1,
    ExecutionRouteV1,
    route_execution_profile,
)
from code2paper.agentic.generic_claim_compiler import ClaimProposalV1, compile_atomic_claims
from code2paper.agentic.generic_fact_compiler import FactCompilerInputV1, compile_facts_from_behavior_graph
from code2paper.agentic.language_adapter_registry import default_language_adapter_registry
from code2paper.agentic.javascript_behavior_adapter import JavaScriptBehaviorAdapter
from code2paper.agentic.research_graph import initial_loop_state
from code2paper.agentic.research_models import ResearchAgendaItemV1, ResearchAgendaV1, ResearchToolCallV1
from code2paper.agentic.research_nodes import (
    ResearchGraphRuntime,
    behavior_graph_updater_node,
    repository_indexer_node,
)
from code2paper.agentic.v3_runtime import V3GraphWrapper
from code2paper.agentic.v3_runtime import build_v3_research_runtime
from code2paper.schemas import LLMConfig
from code2paper.agentic.research_tools import (
    ResearchToolContext,
    build_behavior_subgraph as build_behavior_tool,
    inspect_configuration,
    read_symbol,
    search_symbols,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.llm.capabilities import StructuredResponseMode, builtin_capability_profile


def _call(snapshot_id: str, name: str, **arguments) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=f"call:{name}",
        tool_name=name,
        tool_kind="behavior_graph" if name == "build_behavior_subgraph" else "symbol_search",
        obligation_id="obl-main",
        goal="Recover the executable transformation and output path.",
        repo_snapshot_id=snapshot_id,
        path_scope=("src/pipeline.js",),
        top_k=10,
        node_budget=32,
        arguments=arguments,
    )


def test_javascript_registry_runs_production_index_tool_graph_fact_claim_path(tmp_path: Path) -> None:
    source_root = tmp_path / "js-project"
    source = source_root / "src" / "pipeline.js"
    source.parent.mkdir(parents=True)
    source.write_text(
        "export function selectValues(values) {\n"
        "  const normalized = values.map(value => value / 2);\n"
        "  return normalized.filter(value => value > 0);\n"
        "}\n",
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-js",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[ResearchAgendaItemV1(obligation_id="obl-main", priority="must_cover")],
    )
    runtime = ResearchGraphRuntime(
        run_id="run-js",
        repo_snapshot=snapshot,
        agenda=agenda,
        artifact_root=tmp_path / "artifacts",
    )
    assert runtime.language_adapter().language == "javascript"
    indexed = repository_indexer_node({}, runtime=runtime)
    assert indexed["status"] == "repository_indexed"
    loop = initial_loop_state(runtime)
    assert loop.behavior_graph.language == "javascript"

    context = runtime.tool_context(behavior_graph=loop.behavior_graph)
    searched = search_symbols(context, _call(snapshot.snapshot_id, "search_symbols", query="selectValues"))
    assert searched.status == "success"
    assert searched.result_refs == ("symbol:src/pipeline.js:selectValues:1",)
    read = read_symbol(
        context,
        _call(snapshot.snapshot_id, "read_symbol", path="src/pipeline.js", symbol="selectValues"),
    )
    assert read.status == "success"
    assert read.exact_span_ids == ("span:src/pipeline.js:1:4",)
    built = build_behavior_tool(
        context,
        _call(snapshot.snapshot_id, "build_behavior_subgraph", path="src/pipeline.js", symbol="selectValues"),
    )
    assert built.status == "success"
    graph, update = behavior_graph_updater_node(
        {},
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        observations=(built,),
        active_obligation_id="obl-main",
    )
    assert update["behavior_graph_ref"] == graph.content_digest
    assert {"TRANSFORM", "FILTER", "RETURN"} <= graph.predicates()

    facts = compile_facts_from_behavior_graph(
        graph,
        FactCompilerInputV1(
            obligation_id="obl-main",
            behavior_node_ids=[item.node_id for item in graph.nodes],
            behavior_relation_ids=[item.relation_id for item in graph.relations],
            evidence_span_ids=[item.source_span_id for item in graph.nodes],
        ),
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        evidence_packet_digest=graph.content_digest,
    )
    transform_fact = next(item for item in facts.facts if item.predicate == "transforms")
    filter_fact = next(item for item in facts.facts if item.predicate == "filters_by")
    proposal = ClaimProposalV1(
        claim_id="claim-js-transform",
        canonical_text="The executable stage maps and filters the input values.",
        proposed_fact_ids=[transform_fact.fact_id, filter_fact.fact_id],
        covers_obligation_ids=["obl-main"],
        allowed_wording_boundary="maps and filters input values",
    )
    claims, reports = compile_atomic_claims(
        [proposal],
        facts,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        evidence_packet_digest=graph.content_digest,
    )
    assert reports[0].authorized
    assert [item.claim_id for item in claims.claims] == [proposal.claim_id]


def test_javascript_calls_and_dynamic_behavior_are_auditable(tmp_path: Path) -> None:
    source_root = tmp_path / "js-call-project"
    source_root.mkdir()
    files = {
        "src/pipeline.js": (
            "export function helper(value) {\n"
            "  return value * 2;\n"
            "}\n"
            "export function pipeline(value) {\n"
            "  const resolved = helper(value);\n"
            "  return getFactory()(resolved);\n"
            "}\n"
        ),
        "src/consumer.ts": (
            'import { helper } from "./pipeline";\n'
            "export const consume = (value) => helper(value);\n"
        ),
    }
    for relative_path, text in files.items():
        path = source_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    adapter = JavaScriptBehaviorAdapter()
    index = adapter.index_symbols(
        repo_snapshot_id="snapshot-js-calls",
        project_tree_hash="tree-js-calls",
        files=files,
    )
    helper = next(item for item in index.symbols if item.qualified_name == "helper")
    pipeline = next(item for item in index.symbols if item.qualified_name == "pipeline")
    result = build_behavior_graph(
        adapter=adapter,
        repo_snapshot_id="snapshot-js-calls",
        project_tree_hash="tree-js-calls",
        files=files,
        symbol_index=index,
        symbol_ids=[pipeline.symbol_id],
        depth=1,
        node_budget=64,
    )

    calls = [relation for relation in result.graph.relations if relation.kind == "CALLS"]
    assert any(relation.target_symbol_id == helper.symbol_id for relation in calls)
    assert any(item.reason == "dynamic_call" for item in result.graph.unresolved_relations)
    assert any("getFactory" in item.target_hint for item in result.graph.unresolved_relations)

    references = adapter.resolve_references(helper, index, files)
    assert any(site.kind == "import" and site.path == "src/consumer.ts" for site in references.sites)
    assert any(site.kind == "usage" and site.path == "src/pipeline.js" for site in references.sites)


def test_javascript_configuration_and_build_graph_are_auditable(tmp_path: Path) -> None:
    source_root = tmp_path / "js-config-project"
    (source_root / "src").mkdir(parents=True)
    (source_root / "package.json").write_text(
        '{\n'
        '  "scripts": {"build": "vite build"},\n'
        '  "dependencies": {"vite": "latest"}\n'
        '}\n',
        encoding="utf-8",
    )
    (source_root / "vite.config.ts").write_text(
        'import { defineConfig } from "vite";\n'
        'export default defineConfig({\n'
        '  base: process.env.PUBLIC_BASE || "/",\n'
        '});\n',
        encoding="utf-8",
    )
    (source_root / "src" / "main.ts").write_text(
        'export const endpoint = import.meta.env.API_URL;\n',
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(source_root)
    context = ResearchToolContext(
        repo_snapshot=snapshot,
        artifact_root=tmp_path / "artifacts",
        adapter_language="javascript",
    )
    call = ResearchToolCallV1(
        tool_call_id="call:js-config",
        tool_name="inspect_configuration",
        tool_kind="configuration",
        obligation_id="obl-config",
        goal="Trace runtime configuration and the build entrypoint.",
        repo_snapshot_id=snapshot.snapshot_id,
        top_k=20,
    )
    observation = inspect_configuration(context, call)
    assert observation.status == "success"
    refs = set(observation.result_refs)
    assert any("manifest:scripts" in ref for ref in refs)
    assert any("build:vite.config.ts:define_config" in ref for ref in refs)
    assert any("env:PUBLIC_BASE" in ref for ref in refs)
    assert any("env:API_URL" in ref for ref in refs)
    assert any(
        note.startswith("build_bindings=") and int(note.split("=", 1)[1]) > 0
        for note in observation.diagnostics.notes
    )
    assert any(note == "runtime_bindings=2" for note in observation.diagnostics.notes)


def test_provider_capability_profiles_change_transport_not_authorization() -> None:
    native = builtin_capability_profile(provider="openai", model="model-a")
    second = builtin_capability_profile(provider="anthropic", model="model-b")
    assert native.response_mode == StructuredResponseMode.NATIVE_JSON_SCHEMA
    assert second.response_mode == StructuredResponseMode.JSON_OBJECT
    assert not hasattr(native, "source_authority")
    assert not hasattr(second, "source_authority")
    assert not hasattr(native, "authorization_policy")
    assert not hasattr(second, "authorization_policy")


def test_registry_is_explicit_and_mixed_repositories_fail_to_python_default() -> None:
    registry = default_language_adapter_registry()
    assert registry.supported_languages() == ("javascript", "python")
    assert registry.for_files({"index.ts": ""}).language == "javascript"
    assert registry.for_files({"main.py": "", "ui.ts": ""}).language == "python"


def test_execution_profile_is_bound_to_runtime_without_changing_policy(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-profile",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="js-anthropic-shadow",
        mode="shadow",
        language="javascript",
        provider="anthropic",
        model="second-model",
        evidence_policy_digest="sha256:fixed-policy",
    )
    runtime = ResearchGraphRuntime(
        run_id="run-profile",
        repo_snapshot=snapshot,
        agenda=agenda,
        execution_profile=profile,
    )
    assert runtime.execution_route is not None
    assert runtime.execution_route.shadow
    assert not runtime.execution_enabled
    assert runtime.language_adapter().language == "javascript"
    assert runtime.execution_route.evidence_policy_digest == "sha256:fixed-policy"
    assert runtime.execution_manifest()["evidence_policy_digest"] == "sha256:fixed-policy"


def test_execution_profile_rejects_policy_digest_override(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-profile-mismatch",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="profile",
        evidence_policy_digest="sha256:profile-policy",
    )
    with pytest.raises(ValueError, match="digest mismatch"):
        ResearchGraphRuntime(
            run_id="run-profile-mismatch",
            repo_snapshot=snapshot,
            agenda=agenda,
            execution_profile=profile,
            evidence_policy_digest="sha256:other-policy",
        )


def test_default_ready_profile_cannot_self_activate_implicit_default(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-default",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="unauthorized-default",
        mode="default_ready",
        evidence_policy_digest="sha256:fixed-policy",
    )
    runtime = ResearchGraphRuntime(
        run_id="run-default",
        repo_snapshot=snapshot,
        agenda=agenda,
        execution_profile=profile,
    )
    assert not runtime.execution_enabled


def test_default_ready_profile_executes_only_with_explicit_runtime_authorization(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project-authorized"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-default-authorized",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="authorized-default",
        mode="default_ready",
        evidence_policy_digest="sha256:fixed-policy",
    )
    runtime = ResearchGraphRuntime(
        run_id="run-default-authorized",
        repo_snapshot=snapshot,
        agenda=agenda,
        execution_profile=profile,
        execution_default_authorized=True,
    )
    assert runtime.execution_enabled


def test_execution_route_cannot_override_profile_mode(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-route-mismatch",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="shadow-profile",
        mode="shadow",
        evidence_policy_digest="sha256:fixed-policy",
    )
    with pytest.raises(ValueError, match="does not match"):
        ResearchGraphRuntime(
            run_id="run-route-mismatch",
            repo_snapshot=snapshot,
            agenda=agenda,
            execution_profile=profile,
            execution_route=ExecutionRouteV1(
                profile_id="shadow-profile",
                mode="default_ready",
                execute=True,
                evidence_policy_digest="sha256:fixed-policy",
            ),
        )


def test_opt_in_route_keeps_legacy_default_until_explicit_opt_in(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-opt-in",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[],
    )
    profile = ExecutionProfileV1(
        profile_id="opt-in-profile",
        mode="opt_in",
        evidence_policy_digest="sha256:fixed-policy",
    )
    runtime = ResearchGraphRuntime(
        run_id="run-opt-in",
        repo_snapshot=snapshot,
        agenda=agenda,
        execution_profile=profile,
    )

    class LegacyGraph:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, state, *args, **kwargs):
            self.calls += 1
            return {"artifacts": {}}

    legacy = LegacyGraph()
    result = V3GraphWrapper(v3_runtime=runtime, legacy_graph=legacy).invoke(
        {"out_root": str(tmp_path / "out"), "artifacts": {}}
    )
    assert legacy.calls == 1
    assert result["artifacts"]["execution_profile"]
    assert Path(result["artifacts"]["execution_profile"]).is_file()
    assert Path(result["artifacts"]["execution_route"]).is_file()


def test_runtime_builder_applies_profile_provider_and_model_to_supervisor(tmp_path: Path) -> None:
    source_root = tmp_path / "profile-project"
    source_root.mkdir()
    (source_root / "main.py").write_text("return_value = 1\n", encoding="utf-8")
    profile = ExecutionProfileV1(
        profile_id="second-provider",
        mode="shadow",
        provider="anthropic",
        model="second-model",
        evidence_policy_digest="sha256:fixed-policy",
    )
    runtime = build_v3_research_runtime(
        project_root=source_root,
        intent_path="",
        run_id="run-second-provider",
        llm_config=LLMConfig(provider="none"),
        execution_profile=profile,
    )
    backend_config = runtime.supervisor_backend._llm_config  # type: ignore[attr-defined]
    assert getattr(backend_config.provider, "value", backend_config.provider) == "anthropic"
    assert backend_config.model == "second-model"


def test_canary_is_deterministic_and_rollback_never_executes() -> None:
    canary = ExecutionProfileV1(
        profile_id="canary",
        mode="canary",
        canary_fraction=0.5,
        evidence_policy_digest="sha256:fixed-policy",
    )
    first = route_execution_profile(canary, canary_key="case-1")
    second = route_execution_profile(canary, canary_key="case-1")
    assert first == second
    assert first.shadow == (not first.execute)

    rollback = ExecutionProfileV1(
        profile_id="rollback",
        mode="rollback",
        fallback_profile_id="legacy",
        evidence_policy_digest="sha256:fixed-policy",
    )
    rollback_route = route_execution_profile(rollback)
    assert not rollback_route.execute
    assert rollback_route.rollback_to == "legacy"


def test_execution_profile_rejects_tampered_content_digest() -> None:
    with pytest.raises(ValueError, match="content digest mismatch"):
        ExecutionProfileV1(
            profile_id="tampered",
            mode="shadow",
            evidence_policy_digest="sha256:fixed-policy",
            content_digest="sha256:tampered",
        )


def test_forced_rollback_requires_an_explicit_fallback_profile() -> None:
    profile = ExecutionProfileV1(
        profile_id="shadow",
        mode="shadow",
        evidence_policy_digest="sha256:fixed-policy",
    )
    with pytest.raises(ValueError, match="fallback profile"):
        route_execution_profile(profile, rollback=True)
