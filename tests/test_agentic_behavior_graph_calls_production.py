"""Production behavior-graph builder must persist directed CALLS relations.

``build_behavior_subgraph`` already resolved interprocedural calls, but the
frozen graph written by the production research path was assembled from
``adapter.extract_operations``/``extract_relations`` only.  A persisted graph
therefore had zero typed call edges and no downstream owner/path closure could
ever prove a call chain such as ``rerank -> forward``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from code2paper.agentic.repository_authoring_artifacts import read_snapshot_files
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_graph import initial_loop_state
from code2paper.agentic.research_models import (
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchToolCallV1,
)
from code2paper.agentic.research_nodes import (
    ResearchGraphRuntime,
    behavior_graph_updater_node,
    repository_indexer_node,
)
from code2paper.agentic.research_tools import (
    build_behavior_subgraph as build_behavior_tool,
)


def _call(snapshot_id: str, name: str, **arguments) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=f"call:{name}",
        tool_name=name,
        tool_kind="behavior_graph",
        obligation_id="obl-main",
        goal="Recover the executable transformation and output path.",
        repo_snapshot_id=snapshot_id,
        path_scope=("src/model.py",),
        top_k=10,
        node_budget=64,
        arguments=arguments,
    )


def test_behavior_graph_updater_persists_directed_calls(tmp_path: Path) -> None:
    source_root = tmp_path / "py-project"
    source = source_root / "src" / "model.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        textwrap.dedent(
            """\
            class Reranker:
                def forward(self, x):
                    return x + 1

                def rerank(self, x):
                    return self.forward(x)
            """
        ),
        encoding="utf-8",
    )
    snapshot = build_repo_snapshot(source_root)
    agenda = ResearchAgendaV1(
        run_id="run-calls",
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=[ResearchAgendaItemV1(obligation_id="obl-main", priority="must_cover")],
    )
    runtime = ResearchGraphRuntime(
        run_id="run-calls",
        repo_snapshot=snapshot,
        agenda=agenda,
        artifact_root=tmp_path / "artifacts",
    )
    indexed = repository_indexer_node({}, runtime=runtime)
    assert indexed["status"] == "repository_indexed"
    loop = initial_loop_state(runtime)

    built = build_behavior_tool(
        runtime.tool_context(behavior_graph=loop.behavior_graph),
        _call(
            snapshot.snapshot_id,
            "build_behavior_subgraph",
            path="src/model.py",
            symbol="Reranker.rerank",
        ),
    )
    assert built.status == "success"
    built_callee = build_behavior_tool(
        runtime.tool_context(behavior_graph=loop.behavior_graph),
        _call(
            snapshot.snapshot_id,
            "build_behavior_subgraph",
            path="src/model.py",
            symbol="Reranker.forward",
        ),
    )
    assert built_callee.status == "success"

    graph, update = behavior_graph_updater_node(
        {},
        runtime=runtime,
        behavior_graph=loop.behavior_graph,
        observations=(built, built_callee),
        active_obligation_id="obl-main",
    )
    assert update["behavior_graph_ref"] == graph.content_digest

    symbols = {
        symbol.qualified_name: symbol.symbol_id
        for symbol in runtime.language_adapter(
            read_snapshot_files(snapshot)
        ).index_symbols(
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            files=read_snapshot_files(snapshot),
        ).symbols
    }
    rerank_id = symbols["Reranker.rerank"]
    forward_id = symbols["Reranker.forward"]

    calls = [
        relation
        for relation in graph.relations
        if relation.kind == "CALLS"
        and relation.source_symbol_id == rerank_id
        and relation.target_symbol_id == forward_id
    ]
    assert calls, "the persisted production graph must contain rerank -> forward"
    assert calls[0].target_node_id, "resolved CALLS must bind the callee's first node"
