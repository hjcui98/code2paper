"""Produce a deterministic D6 JavaScript/TypeScript adapter acceptance artifact.

The fixture exercises the second-language path without a provider call:
symbol/index and behavior-graph construction, resolved and dynamic calls,
cross-file references, and runtime/build configuration discovery.  It is a
static adapter proof, not a claim that arbitrary JavaScript semantics are
resolved or that a provider rollout is authorized.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from code2paper.agentic.behavior_graph_tools import build_behavior_subgraph
from code2paper.agentic.javascript_behavior_adapter import JavaScriptBehaviorAdapter
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import ResearchToolContext, inspect_configuration
from code2paper.agentic.tool_runtime import atomic_write_json


def _tool_call(snapshot_id: str) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id="d6:inspect-configuration",
        tool_name="inspect_configuration",
        tool_kind="configuration",
        obligation_id="d6:configuration",
        goal="Trace runtime configuration and build entrypoints.",
        repo_snapshot_id=snapshot_id,
        top_k=32,
    )


def evaluate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="code2paper-d6-js-") as temporary:
        root = Path(temporary)
        files = {
            "package.json": (
                '{\n'
                '  "scripts": {"build": "vite build"},\n'
                '  "dependencies": {"vite": "latest"}\n'
                '}\n'
            ),
            "vite.config.ts": (
                'import { defineConfig } from "vite";\n'
                'export default defineConfig({\n'
                '  base: process.env.PUBLIC_BASE || "/",\n'
                '});\n'
            ),
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
                'export const consume = (value) => helper(value);\n'
                'export const endpoint = import.meta.env.API_URL;\n'
            ),
        }
        for relative_path, source in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")

        snapshot = build_repo_snapshot(root)
        adapter = JavaScriptBehaviorAdapter()
        index = adapter.index_symbols(
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            files=files,
        )
        pipeline = next(item for item in index.symbols if item.qualified_name == "pipeline")
        helper = next(item for item in index.symbols if item.qualified_name == "helper")
        graph_result = build_behavior_subgraph(
            adapter=adapter,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            files=files,
            symbol_index=index,
            symbol_ids=[pipeline.symbol_id],
            depth=1,
            node_budget=64,
        )
        references = adapter.resolve_references(helper, index, files)
        configuration = inspect_configuration(
            ResearchToolContext(
                repo_snapshot=snapshot,
                artifact_root=root / "artifacts",
                adapter_language="javascript",
            ),
            _tool_call(snapshot.snapshot_id),
        )
        resolved_calls = any(
            relation.target_symbol_id == helper.symbol_id
            for relation in graph_result.graph.relations
            if relation.kind == "CALLS"
        )
        dynamic_gap = any(
            unresolved.reason == "dynamic_call"
            and "getFactory" in unresolved.target_hint
            for unresolved in graph_result.graph.unresolved_relations
        )
        cross_file_reference = any(
            site.kind == "import" and site.path == "src/consumer.ts"
            for site in references.sites
        )
        build_config = any("manifest:scripts" in ref for ref in configuration.result_refs) and any(
            "define_config" in ref for ref in configuration.result_refs
        )
        runtime_config = any("env:PUBLIC_BASE" in ref for ref in configuration.result_refs) and any(
            "env:API_URL" in ref for ref in configuration.result_refs
        )
        invariants = {
            "resolved_helper_call": resolved_calls,
            "dynamic_callable_is_gap": dynamic_gap,
            "cross_js_ts_reference": cross_file_reference,
            "build_configuration_discovered": build_config,
            "runtime_configuration_discovered": runtime_config,
            "configuration_observation_has_digests": (
                configuration.input_digest.startswith("sha256:")
                and configuration.output_digest.startswith("sha256:")
            ),
        }
        return {
            "schema_version": "d6_js_adapter_acceptance_v2",
            "status": "passed" if all(invariants.values()) else "failed",
            "snapshot_id": snapshot.snapshot_id,
            "language": adapter.language,
            "indexed_symbols": index.indexed_symbols,
            "graph": {
                "nodes": graph_result.node_count,
                "relations": graph_result.relation_count,
                "unresolved_relations": graph_result.unresolved_count,
                "content_digest": graph_result.graph.content_digest,
            },
            "configuration_observation": {
                "status": configuration.status,
                "result_refs": list(configuration.result_refs),
                "input_digest": configuration.input_digest,
                "output_digest": configuration.output_digest,
                "notes": list(configuration.diagnostics.notes),
            },
            "invariants": invariants,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    atomic_write_json(args.output, report)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
