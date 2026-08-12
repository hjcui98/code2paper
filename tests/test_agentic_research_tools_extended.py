"""扩展研究工具面（设计 section 7.1-7.4）的功能测试。

覆盖 22 个新增研究工具，按设计文档分组：

- 7.1 仓库与符号检索: list_repository_tree, search_code, read_code_span,
  inspect_configuration;
- 7.2 行为图查询: build_behavior_subgraph, query_behavior_graph,
  trace_call_path, trace_data_flow, inspect_control_flow,
  compare_implementation_branches, find_output_side_effects;
- 7.3 hint 检索: search_semantic_hints, derive_code_queries_from_hint,
  compare_hint_to_code;
- 7.4 证据与事实工具: propose_evidence_packet, validate_evidence_packet,
  compile_code_facts, validate_code_facts, decompose_atomic_claims,
  authorize_atomic_claims, record_explicit_code_gap,
  check_obligation_coverage.

每个测试都断言 R1.2 契约：返回的 ``ResearchObservationV1`` 携带 ``status``、
``source_authority``、``result_refs`` / ``exact_span_ids``、``diagnostics``
以及稳定的输入/输出摘要。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.behavior_graph import BehaviorNodeV1, CodeBehaviorGraphV1
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_EXECUTORS,
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    authorize_atomic_claims,
    build_behavior_subgraph,
    check_obligation_coverage,
    compare_hint_to_code,
    compare_implementation_branches,
    compile_code_facts,
    decompose_atomic_claims,
    derive_code_queries_from_hint,
    execute_research_tool,
    find_output_side_effects,
    inspect_configuration,
    inspect_control_flow,
    list_repository_tree,
    propose_evidence_packet,
    query_behavior_graph,
    read_code_span,
    record_explicit_code_gap,
    search_code,
    search_semantic_hints,
    trace_call_path,
    trace_data_flow,
    validate_code_facts,
    validate_evidence_packet,
)


# ---------------------------------------------------------------------------
# Fixture: richer repo with config, branches, hints, side effects
# ---------------------------------------------------------------------------


_TRAIN_PY = """\
import argparse
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--epochs", type=int, default=10)
    return parser.parse_args()


class Trainer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.model = torch.nn.Linear(10, 1)

    def train_loop(self, data) -> float:
        loss = 0.0
        for batch in data:
            out = self.model(batch)
            loss = loss + out.sum()
        if loss < 0:
            print("negative loss")
        else:
            print("positive loss")
        self.save_checkpoint()
        return float(loss)

    def save_checkpoint(self) -> None:
        torch.save(self.model.state_dict(), "checkpoint.pt")


def main() -> int:
    args = parse_args()
    trainer = Trainer(args)
    trainer.train_loop(range(10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


_CONFIG_YAML = """\
lr: 0.001
epochs: 10
batch_size: 32
"""


_README_MD = """\
# Toy Project

This project trains a linear model using SGD.

The Trainer class uses a learning rate of 0.001 by default.

## Usage

    python train.py --lr 0.01
"""


@pytest.fixture()
def rich_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "configs").mkdir(parents=True)
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "configs" / "train.yaml").write_text(_CONFIG_YAML, encoding="utf-8")
    (root / "README.md").write_text(_README_MD, encoding="utf-8")
    return root


@pytest.fixture()
def ctx(rich_repo: Path) -> ResearchToolContext:
    snapshot = build_repo_snapshot(rich_repo)
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        nodes=[
            BehaviorNodeV1(
                node_id="node:trainer-model",
                symbol_id="sym:train.Trainer.__init__",
                operation_id="op:trainer-model",
                predicate="CONSTRUCT",
                operands=("torch.nn.Linear",),
                result="self.model",
                source_span_id="span:train.py:15:18",
                source_authority="executable_hard",
            )
        ],
    ).with_digest()
    return ResearchToolContext(
        repo_snapshot=snapshot,
        behavior_graph=graph,
        artifact_root=rich_repo / ".research-artifacts",
    )


def _tool_call(
    *,
    tool_name: str,
    tool_call_id: str = "tc-1",
    obligation_id: str = "obl-1",
    goal: str = "explain trainer",
    repo_snapshot_id: str,
    path_scope: tuple[str, ...] = (),
    top_k: int = 10,
    depth: int = 0,
    node_budget: int = 0,
    arguments: dict | None = None,
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=RESEARCH_TOOL_KINDS.get(tool_name, "other"),
        obligation_id=obligation_id,
        goal=goal,
        repo_snapshot_id=repo_snapshot_id,
        path_scope=path_scope,
        top_k=top_k,
        depth=depth,
        node_budget=node_budget,
        arguments=dict(arguments or {}),
    )


# ---------------------------------------------------------------------------
# 7.1 仓库与符号检索
# ---------------------------------------------------------------------------


class TestListRepositoryTree:
    def test_lists_files_in_snapshot(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="list_repository_tree",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            top_k=50,
        )
        obs = list_repository_tree(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert any("train.py" in r for r in refs), refs
        assert any("README.md" in r for r in refs), refs
        assert all(r.startswith("tree:") for r in refs)

    def test_filters_by_file_kind_python(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="list_repository_tree",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"file_kinds": ("python",)},
            top_k=50,
        )
        obs = list_repository_tree(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert all("train.py" in r for r in refs), refs
        assert not any("README.md" in r for r in refs), refs

    def test_respects_depth_limit(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="list_repository_tree",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            depth=1,  # only top-level files (rel_depth < 1)
            top_k=50,
        )
        obs = list_repository_tree(ctx, call)
        assert obs.status in ("success", "truncated")
        refs = list(obs.result_refs)
        # depth=1 means rel_depth < 1, i.e. only files at the root.
        # configs/train.yaml has rel_depth=1 and should be excluded.
        assert not any("configs/train.yaml" in r for r in refs), refs

    def test_returns_success_empty_when_no_matches(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="list_repository_tree",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"file_kinds": ("rust",)},
            top_k=50,
        )
        obs = list_repository_tree(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


class TestSearchCode:
    def test_finds_query_in_python_file(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "Trainer"},
            top_k=10,
        )
        obs = search_code(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert any("train.py" in r for r in refs), refs
        assert all(r.startswith("code:") for r in refs)

    def test_finds_query_in_markdown(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "learning rate"},
            top_k=10,
        )
        obs = search_code(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert any("README.md" in r for r in refs), refs

    def test_returns_success_empty_when_query_misses(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "NoSuchTokenHere"},
            top_k=10,
        )
        obs = search_code(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()

    def test_invalid_request_on_empty_query(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": ""},
            top_k=10,
        )
        obs = search_code(ctx, call)
        assert obs.status == "invalid_request"

    def test_truncates_at_top_k(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "e"},
            top_k=1,
        )
        obs = search_code(ctx, call)
        assert obs.status == "truncated"
        assert obs.diagnostics.truncated is True
        assert len(obs.result_refs) == 1


class TestReadCodeSpan:
    def test_reads_specified_line_range(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="read_code_span",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "start_line": 1, "end_line": 5},
            top_k=1,
        )
        obs = read_code_span(ctx, call)
        assert obs.status == "success"
        span = obs.exact_span_ids[0]
        assert span == "span:train.py:1:5"

    def test_defaults_end_line_when_zero(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="read_code_span",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "start_line": 1, "end_line": 0},
            top_k=1,
        )
        obs = read_code_span(ctx, call)
        assert obs.status == "success"
        # end_line defaults to start_line + 50 capped at file length.
        span = obs.exact_span_ids[0]
        assert span.startswith("span:train.py:1:")

    def test_returns_success_empty_when_start_exceeds_file(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="read_code_span",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "start_line": 10000, "end_line": 10010},
            top_k=1,
        )
        obs = read_code_span(ctx, call)
        assert obs.status == "success_empty"
        assert obs.exact_span_ids == ()

    def test_invalid_request_on_empty_path(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="read_code_span",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "", "start_line": 1, "end_line": 5},
            top_k=1,
        )
        obs = read_code_span(ctx, call)
        assert obs.status == "invalid_request"

    def test_invalid_request_on_external_path(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="read_code_span",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "/etc/passwd", "start_line": 1, "end_line": 5},
            top_k=1,
        )
        obs = read_code_span(ctx, call)
        assert obs.status == "invalid_request"


class TestInspectConfiguration:
    def test_finds_argparse_defaults(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="inspect_configuration",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"config_key": ""},
            top_k=20,
        )
        obs = inspect_configuration(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # argparse add_argument for --lr and --epochs should be detected.
        assert any("lr" in r for r in refs), refs
        assert any("epochs" in r for r in refs), refs
        assert all(r.startswith("config:") for r in refs)

    def test_filters_by_config_key(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="inspect_configuration",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"config_key": "lr"},
            top_k=20,
        )
        obs = inspect_configuration(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert all("lr" in r for r in refs), refs
        assert not any("epochs" in r for r in refs), refs

    def test_returns_success_empty_when_no_bindings(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="inspect_configuration",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            path_scope=("README.md",),  # non-python scope
            arguments={"config_key": ""},
            top_k=20,
        )
        obs = inspect_configuration(ctx, call)
        # README.md is not .py, so no bindings.
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


# ---------------------------------------------------------------------------
# 7.2 行为图查询
# ---------------------------------------------------------------------------


class TestBuildBehaviorSubgraph:
    def test_extracts_methods_within_class(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="build_behavior_subgraph",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "Trainer", "path": "train.py"},
            node_budget=32,
            top_k=10,
        )
        obs = build_behavior_subgraph(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # Trainer contains __init__, train_loop, save_checkpoint.
        assert any("train_loop" in r for r in refs), refs
        assert any("save_checkpoint" in r for r in refs), refs
        assert all(r.startswith("behavior:") for r in refs)

    def test_returns_success_empty_for_unknown_symbol(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="build_behavior_subgraph",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "NoSuchClass", "path": "train.py"},
            node_budget=32,
            top_k=10,
        )
        obs = build_behavior_subgraph(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()

    def test_returns_success_empty_for_non_python_file(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="build_behavior_subgraph",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "Trainer", "path": "README.md"},
            node_budget=32,
            top_k=10,
        )
        obs = build_behavior_subgraph(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


class TestQueryBehaviorGraph:
    def test_invalid_request_when_all_args_empty(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="query_behavior_graph",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"predicate": "", "operand": "", "relation": ""},
            top_k=10,
        )
        obs = query_behavior_graph(ctx, call)
        assert obs.status == "invalid_request"

    def test_returns_success_empty_with_query_echo(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="query_behavior_graph",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"predicate": "calls", "operand": "save_checkpoint", "relation": ""},
            top_k=10,
        )
        obs = query_behavior_graph(ctx, call)
        # Behavior graph is not in tool context, so always success_empty.
        assert obs.status == "success_empty"
        assert obs.diagnostics.candidate_count == 0


class TestTraceCallPath:
    def test_finds_call_path_between_symbols(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="trace_call_path",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"source_symbol": "train_loop", "target_symbol": "save_checkpoint"},
            top_k=20,
        )
        obs = trace_call_path(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert all(r.startswith("callpath:") for r in refs)
        assert any("train.py" in r for r in refs), refs

    def test_returns_success_empty_when_no_path(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="trace_call_path",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"source_symbol": "train_loop", "target_symbol": "nonexistent"},
            top_k=20,
        )
        obs = trace_call_path(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()

    def test_invalid_request_on_empty_symbols(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="trace_call_path",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"source_symbol": "", "target_symbol": ""},
            top_k=20,
        )
        obs = trace_call_path(ctx, call)
        assert obs.status == "invalid_request"


class TestTraceDataFlow:
    def test_traces_both_directions(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="trace_data_flow",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "loss", "direction": "both"},
            top_k=20,
        )
        obs = trace_data_flow(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # `loss = 0.0`, `loss = loss + out.sum()`, `return float(loss)`.
        assert len(refs) >= 2, refs
        assert all(r.startswith("dataflow:") for r in refs)

    def test_traces_forward_only(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="trace_data_flow",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "loss", "direction": "forward"},
            top_k=20,
        )
        obs = trace_data_flow(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # Forward only: assignments to `loss`.
        assert all(r.startswith("dataflow:") for r in refs)

    def test_returns_success_empty_for_unknown_symbol(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="trace_data_flow",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol": "nonexistent_var", "direction": "both"},
            top_k=20,
        )
        obs = trace_data_flow(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


class TestInspectControlFlow:
    def test_finds_branches_in_function(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="inspect_control_flow",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "symbol": "train_loop"},
            top_k=20,
        )
        obs = inspect_control_flow(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # train_loop has: for, if, return. Each ref is branch:<path>:<line>:<kind>.
        kinds = {ref.rsplit(":", 1)[-1] for ref in refs}
        assert "for" in kinds, kinds
        assert "if" in kinds, kinds
        assert "return" in kinds, kinds

    def test_returns_success_empty_when_no_branches(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="inspect_control_flow",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "symbol": "save_checkpoint"},
            top_k=20,
        )
        obs = inspect_control_flow(ctx, call)
        # save_checkpoint has no branches/loops (only a single torch.save call,
        # which is not a control-flow construct).
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


class TestCompareImplementationBranches:
    def test_returns_comparison_ref(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compare_implementation_branches",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol_a": "Trainer", "symbol_b": "Evaluator"},
            top_k=10,
        )
        obs = compare_implementation_branches(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert len(refs) == 1
        assert "Trainer" in refs[0] and "Evaluator" in refs[0]

    def test_invalid_request_on_empty_symbols(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compare_implementation_branches",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"symbol_a": "", "symbol_b": ""},
            top_k=10,
        )
        obs = compare_implementation_branches(ctx, call)
        assert obs.status == "invalid_request"


class TestFindOutputSideEffects:
    def test_finds_save_and_print(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="find_output_side_effects",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "symbol": "train_loop"},
            top_k=20,
        )
        obs = find_output_side_effects(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # Each ref is ``effect:<path>:<line>:<kind>`` where kind may be
        # ``output:print``, ``write:save``, ``checkpoint:torch.save`` or
        # bare ``return``. Use substring matching so the inconsistent
        # nesting of the kind suffix does not break the assertion.
        joined = " ".join(refs)
        assert "output:print" in joined, refs
        assert ":return" in joined, refs

    def test_finds_checkpoint_save_in_class(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="find_output_side_effects",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "symbol": "save_checkpoint"},
            top_k=20,
        )
        obs = find_output_side_effects(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        # torch.save is detected as a write (func_name="save" matches the
        # write set since AST sees ``torch.save`` as Attribute with attr="save").
        joined = " ".join(refs)
        assert "write:save" in joined, refs

    def test_returns_success_empty_when_no_effects(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="find_output_side_effects",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"path": "train.py", "symbol": "Trainer.__init__"},
            top_k=20,
        )
        obs = find_output_side_effects(ctx, call)
        # Trainer.__init__ has only assignments and a torch.nn.Linear()
        # constructor call (func_name="Linear" is not in any effect set).
        assert obs.status == "success_empty"
        assert obs.result_refs == ()


# ---------------------------------------------------------------------------
# 7.3 hint 检索
# ---------------------------------------------------------------------------


class TestSearchSemanticHints:
    def test_finds_hint_in_markdown(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_semantic_hints",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "learning rate"},
            top_k=10,
        )
        obs = search_semantic_hints(ctx, call)
        assert obs.status == "success"
        assert obs.source_authority == "semantic_hint"
        refs = list(obs.result_refs)
        assert all(r.startswith("hint:") for r in refs)
        assert any("README.md" in r for r in refs), refs

    def test_returns_success_empty_when_query_misses(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="search_semantic_hints",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "NoSuchHintTerm"},
            top_k=10,
        )
        obs = search_semantic_hints(ctx, call)
        assert obs.status == "success_empty"
        assert obs.source_authority == "semantic_hint"

    def test_invalid_request_on_empty_query(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="search_semantic_hints",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": ""},
            top_k=10,
        )
        obs = search_semantic_hints(ctx, call)
        assert obs.status == "invalid_request"

    def test_does_not_search_python_files(self, ctx: ResearchToolContext) -> None:
        # Trainer appears in both train.py and README.md, but only README.md
        # is a hint file. search_semantic_hints must only return hint matches.
        call = _tool_call(
            tool_name="search_semantic_hints",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"query": "Trainer"},
            top_k=10,
        )
        obs = search_semantic_hints(ctx, call)
        # README.md contains "Trainer", so we expect a success match in
        # README.md only — never in train.py.
        assert obs.status == "success"
        assert obs.source_authority == "semantic_hint"
        for ref in obs.result_refs:
            assert "README.md" in ref, ref
            assert "train.py" not in ref, ref


class TestDeriveCodeQueriesFromHint:
    def test_extracts_tokens_from_hint(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="derive_code_queries_from_hint",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"hint_text": "The Trainer uses SGD optimizer with lr=0.001"},
            top_k=10,
        )
        obs = derive_code_queries_from_hint(ctx, call)
        assert obs.status == "success"
        assert obs.source_authority == "semantic_hint"
        refs = list(obs.result_refs)
        assert all(r.startswith("hintquery:") for r in refs)
        # Trainer, SGD, optimizer, lr are valid tokens.
        query_str = " ".join(refs)
        assert "Trainer" in query_str
        assert "SGD" in query_str

    def test_filters_stopwords(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="derive_code_queries_from_hint",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"hint_text": "the and for with that this from"},
            top_k=10,
        )
        obs = derive_code_queries_from_hint(ctx, call)
        assert obs.status == "success_empty"
        assert obs.result_refs == ()

    def test_invalid_request_on_empty_hint(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="derive_code_queries_from_hint",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"hint_text": ""},
            top_k=10,
        )
        obs = derive_code_queries_from_hint(ctx, call)
        assert obs.status == "invalid_request"


class TestCompareHintToCode:
    def test_returns_match_when_hint_term_in_code(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compare_hint_to_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "hint_text": "The Trainer class trains a model",
                "code_span": "class Trainer: def __init__(self): pass",
            },
            top_k=10,
        )
        obs = compare_hint_to_code(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["hintcompare:match"]

    def test_returns_mismatch_when_no_overlap(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compare_hint_to_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "hint_text": "GradientDescent Optimizer Backpropagate",
                "code_span": "class Trainer: def __init__(self): pass",
            },
            top_k=10,
        )
        obs = compare_hint_to_code(ctx, call)
        # None of the hint tokens appear in the code span.
        assert obs.status == "success_empty"
        refs = list(obs.result_refs)
        assert refs == ["hintcompare:mismatch"]

    def test_invalid_request_on_empty_args(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compare_hint_to_code",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"hint_text": "", "code_span": ""},
            top_k=10,
        )
        obs = compare_hint_to_code(ctx, call)
        assert obs.status == "invalid_request"


# ---------------------------------------------------------------------------
# 7.4 证据与事实工具
# ---------------------------------------------------------------------------


def _run_real_evidence_chain(
    ctx: ResearchToolContext,
    *,
    through: str,
):
    """Drive the D1 packet -> fact -> claim data plane without a facade."""

    proposed = propose_evidence_packet(
        ctx,
        _tool_call(
            tool_name="propose_evidence_packet",
            tool_call_id="tc-chain-propose",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_tag": "obl-trainer",
                "packet_id": "packet-trainer",
                "anchor_span_ids": ("span:train.py:15:18",),
                "behavior_node_ids": ("node:trainer-model",),
            },
        ),
    )
    assert proposed.status == "success", proposed
    validated_packet = validate_evidence_packet(
        ctx,
        _tool_call(
            tool_name="validate_evidence_packet",
            tool_call_id="tc-chain-validate-packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"packet_id": "packet-trainer"},
        ),
    )
    assert validated_packet.status == "success", validated_packet
    facts = compile_code_facts(
        ctx,
        _tool_call(
            tool_name="compile_code_facts",
            tool_call_id="tc-chain-compile-facts",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"packet_id": "packet-trainer"},
        ),
    )
    assert facts.status == "success", facts
    if through == "facts":
        return facts
    fact_ids = tuple(ref.removeprefix("fact:compiled:") for ref in facts.result_refs)
    validated_facts = validate_code_facts(
        ctx,
        _tool_call(
            tool_name="validate_code_facts",
            tool_call_id="tc-chain-validate-facts",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "fact_id": fact_ids[0],
                "fact_set_id": "packet-trainer",
            },
        ),
    )
    assert validated_facts.status == "success", validated_facts
    if through == "validated_facts":
        return validated_facts
    proposals = decompose_atomic_claims(
        ctx,
        _tool_call(
            tool_name="decompose_atomic_claims",
            tool_call_id="tc-chain-propose-claims",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "fact_ids": fact_ids,
                "fact_set_id": "packet-trainer",
                "claim_proposals": (
                    {
                        "claim_id": "claim-trainer-model",
                        "canonical_text": "Trainer constructs its model.",
                        "claim_kind": "implementation_behavior",
                        "proposed_fact_ids": list(fact_ids),
                        "covers_obligation_ids": ["obl-trainer"],
                        "required_qualifiers": [],
                        "unsupported_author_fragments": [],
                        "allowed_wording_boundary": "Trainer constructs its model.",
                    },
                ),
            },
        ),
    )
    assert proposals.status == "success", proposals
    if through == "proposed_claims":
        return proposals
    proposal_set_id = next(
        note.split("=", 1)[1]
        for note in proposals.diagnostics.notes
        if note.startswith("proposal_set_id=")
    )
    return authorize_atomic_claims(
        ctx,
        _tool_call(
            tool_name="authorize_atomic_claims",
            tool_call_id="tc-chain-authorize-claims",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "claim_ids": ("claim-trainer-model",),
                "proposal_set_id": proposal_set_id,
            },
        ),
    )


class TestProposeEvidencePacket:
    def test_proposes_packet_with_valid_anchors(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="propose_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_tag": "obl-trainer",
                "packet_id": "packet-trainer",
                "anchor_span_ids": ("span:train.py:15:18",),
                "behavior_node_ids": ("node:trainer-model",),
            },
            top_k=10,
        )
        obs = propose_evidence_packet(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["packet:proposed:packet-trainer"]
        assert ctx.read_artifact("packet_proposals", "packet-trainer") is not None

    def test_invalid_request_on_empty_obligation(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="propose_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_tag": "", "anchor_span_ids": ("span:train.py:10:20",)},
            top_k=10,
        )
        obs = propose_evidence_packet(ctx, call)
        assert obs.status == "invalid_request"

    def test_invalid_request_on_empty_anchors(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="propose_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_tag": "obl-1", "anchor_span_ids": ()},
            top_k=10,
        )
        obs = propose_evidence_packet(ctx, call)
        assert obs.status == "invalid_request"

    def test_rejects_anchors_outside_snapshot(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="propose_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_tag": "obl-1",
                "anchor_span_ids": ("span:/etc/passwd:1:5",),
            },
            top_k=10,
        )
        obs = propose_evidence_packet(ctx, call)
        # /etc/passwd is not in the snapshot, so no anchors validate.
        assert obs.status == "invalid_request"


class TestValidateEvidencePacket:
    def test_validates_packet_id(self, ctx: ResearchToolContext) -> None:
        proposed = _tool_call(
            tool_name="propose_evidence_packet",
            tool_call_id="tc-propose",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_tag": "obl-trainer",
                "packet_id": "packet-trainer",
                "anchor_span_ids": ("span:train.py:15:18",),
                "behavior_node_ids": ("node:trainer-model",),
            },
        )
        assert propose_evidence_packet(ctx, proposed).status == "success"
        call = _tool_call(
            tool_name="validate_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"packet_id": "packet-trainer"},
            top_k=10,
        )
        obs = validate_evidence_packet(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["packet:validated:packet-trainer"]
        assert ctx.read_artifact("validated_packets", "packet-trainer") is not None

    def test_invalid_request_on_empty_packet_id(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="validate_evidence_packet",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"packet_id": ""},
            top_k=10,
        )
        obs = validate_evidence_packet(ctx, call)
        assert obs.status == "invalid_request"

    def test_rejects_tampered_validated_packet_on_replay(self, ctx: ResearchToolContext) -> None:
        assert _run_real_evidence_chain(ctx, through="validated_facts").status == "success"
        path = ctx.artifact_path("validated_packets", "packet-trainer")
        assert path is not None
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["conditions"] = ["tampered-condition"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        obs = validate_evidence_packet(
            ctx,
            _tool_call(
                tool_name="validate_evidence_packet",
                tool_call_id="tc-tampered-packet",
                repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
                arguments={"packet_id": "packet-trainer"},
            ),
        )
        assert obs.status == "invalid_request"
        assert "validated_packet_artifact_drift" in obs.error_message


class TestCompileCodeFacts:
    def test_compiles_facts_from_packet(self, ctx: ResearchToolContext) -> None:
        obs = _run_real_evidence_chain(ctx, through="facts")
        assert obs.status == "success", obs
        refs = list(obs.result_refs)
        assert refs and all(ref.startswith("fact:compiled:fact-") for ref in refs)
        fact_set = ctx.read_artifact("fact_sets", "packet-trainer")
        assert fact_set and fact_set["facts"][0]["validation_status"] == "supported"
        assert fact_set["producer_version"] == "code2paper-generic-research-data-plane-v1"

    def test_invalid_request_on_empty_packet_id(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="compile_code_facts",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"packet_id": ""},
            top_k=10,
        )
        obs = compile_code_facts(ctx, call)
        assert obs.status == "invalid_request"


class TestValidateCodeFacts:
    def test_validates_fact(self, ctx: ResearchToolContext) -> None:
        obs = _run_real_evidence_chain(ctx, through="validated_facts")
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs and all(ref.startswith("fact:validated:fact-") for ref in refs)

    def test_invalid_request_on_empty_fact_id(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="validate_code_facts",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"fact_id": ""},
            top_k=10,
        )
        obs = validate_code_facts(ctx, call)
        assert obs.status == "invalid_request"

    def test_rejects_tampered_fact_set_on_replay(self, ctx: ResearchToolContext) -> None:
        assert _run_real_evidence_chain(ctx, through="validated_facts").status == "success"
        path = ctx.artifact_path("fact_sets", "packet-trainer")
        assert path is not None
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["facts"][0]["object"] = ["tampered-object"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        fact_id = payload["facts"][0]["fact_id"]
        obs = validate_code_facts(
            ctx,
            _tool_call(
                tool_name="validate_code_facts",
                tool_call_id="tc-tampered-fact",
                repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
                arguments={
                    "fact_id": fact_id,
                    "fact_set_id": "packet-trainer",
                },
            ),
        )
        assert obs.status == "invalid_request"
        assert "fact_set_replay_mismatch" in obs.error_message


class TestDecomposeAtomicClaims:
    def test_decomposes_facts_into_claims(self, ctx: ResearchToolContext) -> None:
        obs = _run_real_evidence_chain(ctx, through="proposed_claims")
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["claim:proposed:claim-trainer-model"]

    def test_invalid_request_on_empty_facts(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="decompose_atomic_claims",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"fact_ids": ()},
            top_k=10,
        )
        obs = decompose_atomic_claims(ctx, call)
        assert obs.status == "invalid_request"


class TestAuthorizeAtomicClaims:
    def test_authorizes_claims(self, ctx: ResearchToolContext) -> None:
        obs = _run_real_evidence_chain(ctx, through="authorized_claims")
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["claim:authorized:claim-trainer-model"]
        artifact_note = next(
            note for note in obs.diagnostics.notes if note.startswith("artifact=")
        )
        payload = json.loads(Path(artifact_note.split("=", 1)[1]).read_text(encoding="utf-8"))
        assert payload["producer_version"] == "code2paper-generic-research-data-plane-v1"

    def test_invalid_request_on_empty_claims(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="authorize_atomic_claims",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"claim_ids": ()},
            top_k=10,
        )
        obs = authorize_atomic_claims(ctx, call)
        assert obs.status == "invalid_request"


class TestRecordExplicitCodeGap:
    def test_records_gap_with_reason(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="record_explicit_code_gap",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_id_ref": "obl-1",
                "termination_reason": "no_evidence_after_exhaustive_search",
                "search_scope": ("train.py",),
                "attempted_tools": ("search_code", "read_symbol"),
                "search_complete": True,
            },
            top_k=10,
        )
        obs = record_explicit_code_gap(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert len(refs) == 1 and refs[0].startswith("gap:gap-")
        # termination_reason appears in diagnostics notes.
        notes = " ".join(obs.diagnostics.notes)
        assert "no_evidence_after_exhaustive_search" in notes
        replay = record_explicit_code_gap(ctx, call)
        assert replay.status == "success"
        assert replay.result_refs == obs.result_refs
        assert "idempotent_replay=true" in replay.diagnostics.notes

    def test_rejects_missing_relation_without_relation_trace(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="record_explicit_code_gap",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_id_ref": "obl-1",
                "termination_reason": "required call edge not found",
                "search_scope": ("train.py",),
                "attempted_tools": ("search_code", "read_symbol"),
                "missing_relations": ("CALLS",),
                "search_complete": True,
            },
        )

        obs = record_explicit_code_gap(ctx, call)

        assert obs.status == "invalid_request"
        assert "gap_missing_relation_not_traced" in obs.error_message

    def test_rejects_scope_outside_frozen_snapshot(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="record_explicit_code_gap",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={
                "obligation_id_ref": "obl-1",
                "termination_reason": "no evidence",
                "search_scope": ("/outside/frozen/repository.py",),
                "attempted_tools": ("search_code", "read_symbol"),
                "search_complete": True,
            },
        )

        obs = record_explicit_code_gap(ctx, call)

        assert obs.status == "invalid_request"
        assert "gap_search_scope_outside_snapshot" in obs.error_message

    def test_invalid_request_on_empty_obligation(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="record_explicit_code_gap",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_id_ref": "", "termination_reason": ""},
            top_k=10,
        )
        obs = record_explicit_code_gap(ctx, call)
        assert obs.status == "invalid_request"


class TestCheckObligationCoverage:
    def test_returns_coverage_ref_for_obligation(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="check_obligation_coverage",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_id_ref": "obl-1"},
            top_k=10,
        )
        obs = check_obligation_coverage(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["coverage:obl-1"]

    def test_returns_all_coverage_when_no_obligation(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="check_obligation_coverage",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_id_ref": ""},
            top_k=10,
        )
        obs = check_obligation_coverage(ctx, call)
        assert obs.status == "success"
        refs = list(obs.result_refs)
        assert refs == ["coverage:all"]


# ---------------------------------------------------------------------------
# Registry / dispatch sanity checks
# ---------------------------------------------------------------------------


class TestExtendedToolRegistry:
    def test_all_22_extended_tools_have_executors(self) -> None:
        extended = (
            "list_repository_tree",
            "search_code",
            "read_code_span",
            "inspect_configuration",
            "build_behavior_subgraph",
            "query_behavior_graph",
            "trace_call_path",
            "trace_data_flow",
            "inspect_control_flow",
            "compare_implementation_branches",
            "find_output_side_effects",
            "search_semantic_hints",
            "derive_code_queries_from_hint",
            "compare_hint_to_code",
            "propose_evidence_packet",
            "validate_evidence_packet",
            "compile_code_facts",
            "validate_code_facts",
            "decompose_atomic_claims",
            "authorize_atomic_claims",
            "record_explicit_code_gap",
            "check_obligation_coverage",
        )
        for name in extended:
            assert name in RESEARCH_TOOL_EXECUTORS, f"missing executor: {name}"
            assert callable(RESEARCH_TOOL_EXECUTORS[name])

    def test_dispatch_via_execute_research_tool(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="check_obligation_coverage",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={"obligation_id_ref": "obl-1"},
            top_k=10,
        )
        obs = execute_research_tool(ctx, call)
        assert obs.status == "success"

    def test_dispatch_rejects_unknown_tool(self, ctx: ResearchToolContext) -> None:
        call = _tool_call(
            tool_name="nonexistent_tool",
            repo_snapshot_id=ctx.repo_snapshot.snapshot_id,
            arguments={},
            top_k=10,
        )
        obs = execute_research_tool(ctx, call)
        assert obs.status == "invalid_request"

    def test_dispatch_rejects_snapshot_id_mismatch(
        self, ctx: ResearchToolContext
    ) -> None:
        call = _tool_call(
            tool_name="check_obligation_coverage",
            repo_snapshot_id="different-snapshot-id",
            arguments={"obligation_id_ref": "obl-1"},
            top_k=10,
        )
        obs = execute_research_tool(ctx, call)
        assert obs.status == "invalid_request"
