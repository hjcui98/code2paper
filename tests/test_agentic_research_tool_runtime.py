"""R1.4 runtime closure test: ``find_entrypoints -> search_symbols ->
read_symbol -> find_references``.

Per the R1.4 exit condition (``docs/agentic_method_quality_next_execution_plan_2026-07-19.md``):

    退出条件：用工具 API 能在 RAP、EBCAR、DyG、LinearRAG 中完成
    "找 entrypoint -> 找核心 symbol -> 读定义 -> 找引用"，
    且无需调用 legacy intake stage。

This test builds a small fixture that mimics the structure of the four
representative real-world projects (RAP / EBCAR / DyG / LinearRAG: a
``train.py`` entrypoint that imports a model class, a ``model.py`` defining
that class with a forward/encode method, an ``eval.py`` entrypoint, and a
config file).  It then drives the four-tool closure end-to-end through the
LangChain ``StructuredTool`` API produced by ``build_research_structured_tools``.

The closure must succeed without ever invoking the legacy
``legacy_intake_stage_tool.run_intake`` path: the V3 research plane is the
new source of truth for repository exploration, and the intake stage is
only consulted by the legacy P3 graph.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.research_tool_manifest import (
    RESEARCH_TOOL_RETURN_FIELDS,
    build_research_structured_tools,
    build_research_tool_manifest,
)
from code2paper.agentic.research_tools import RESEARCH_TOOL_NAMES, ResearchToolContext


# ---------------------------------------------------------------------------
# Fixture: a small ML-research-style project (RAP/EBCAR/DyG/LinearRAG shape)
# ---------------------------------------------------------------------------


_TRAIN_PY = """\
\"\"\"Training entrypoint for the toy project.\"\"\"

import argparse
import torch

from model import GaussianModel
from dataset import SceneDataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lr", type=float, default=1.0e-4)
    parser.add_argument("--epochs", type=int, default=100)
    return parser.parse_args()


def train(model: GaussianModel, dataset: SceneDataset, args: argparse.Namespace) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    for epoch in range(args.epochs):
        for batch in dataset:
            loss = model.forward(batch)
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()


def main() -> None:
    args = parse_args()
    model = GaussianModel()
    dataset = SceneDataset()
    train(model, dataset, args)


if __name__ == "__main__":
    main()
"""


_EVAL_PY = """\
\"\"\"Evaluation entrypoint.\"\"\"

import torch

from model import GaussianModel


def evaluate(model: GaussianModel, checkpoint_path: str) -> float:
    state = torch.load(checkpoint_path)
    model.load_state_dict(state)
    return model.forward()


def main() -> None:
    model = GaussianModel()
    print(evaluate(model, "ckpt.pt"))


if __name__ == "__main__":
    main()
"""


_MODEL_PY = """\
\"\"\"Model definition.\"\"\"

import torch
import torch.nn as nn


class GaussianModel(nn.Module):
    \"\"\"A toy 3D Gaussian Splatting model.\"\"\"

    def __init__(self) -> None:
        super().__init__()
        self.gaussians = nn.Parameter(torch.zeros(64, 3))

    def forward(self, batch: Any = None) -> torch.Tensor:
        return self.gaussians.sum()

    def load_state_dict(self, state: dict, strict: bool = True) -> Any:
        return super().load_state_dict(state, strict=strict)
"""


_DATASET_PY = """\
\"\"\"Dataset definition.\"\"\"

import torch


class SceneDataset:
    def __iter__(self):
        return iter([torch.zeros(8)])
"""


CONFIG_YAML = """\
lr: 1.0e-4
epochs: 100
batch_size: 16
"""


@pytest.fixture()
def ml_repo(tmp_path: Path) -> Path:
    root = tmp_path / "rap_toy"
    (root / "configs").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "eval.py").write_text(_EVAL_PY, encoding="utf-8")
    (root / "model.py").write_text(_MODEL_PY, encoding="utf-8")
    (root / "dataset.py").write_text(_DATASET_PY, encoding="utf-8")
    (root / "configs" / "train.yaml").write_text(CONFIG_YAML, encoding="utf-8")
    (root / "scripts" / "run_train.sh").write_text(
        "#!/usr/bin/env bash\npython -m train\n", encoding="utf-8"
    )
    return root


@pytest.fixture()
def tools(ml_repo: Path):
    snapshot = build_repo_snapshot(ml_repo)
    ctx = ResearchToolContext(repo_snapshot=snapshot)
    return build_research_structured_tools(ctx), ctx


def _find_tool(tools, name: str):
    for tool in tools:
        if tool.name == name:
            return tool
    raise AssertionError(f"tool {name} not registered")


def _base_kwargs(ctx: ResearchToolContext, **overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "tool_call_id": "tc-runtime",
        "obligation_id": "obl-train-loop",
        "goal": "Explain the training loop in train.py",
        "repo_snapshot_id": ctx.repo_snapshot.snapshot_id,
        "path_scope": (),
        "top_k": 20,
        "depth": 0,
        "node_budget": 0,
    }
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# Closure: find_entrypoints -> search_symbols -> read_symbol -> find_references
# ---------------------------------------------------------------------------


def test_research_tool_closure_finds_entrypoint_then_symbol_then_span_then_refs(
    tools,
) -> None:
    """End-to-end closure of the four minimal research tools.

    The test proves a supervisor can drive the full exploration loop using
    only the V3 research tool API: it locates the training entrypoint, finds
    the ``train`` function, reads its source span, and finds every place
    ``GaussianModel`` is referenced.  No legacy intake stage call is needed.
    """

    tool_list, ctx = tools

    # ------------------------------------------------------------------
    # Step 1: find_entrypoints -> locate train.py
    # ------------------------------------------------------------------
    find_entrypoints = _find_tool(tool_list, "find_entrypoints")
    step1 = find_entrypoints.invoke(_base_kwargs(ctx, tool_call_id="tc-step1"))
    assert step1["status"] == "success", step1
    entrypoint_refs = list(step1["result_refs"])
    assert "entrypoint:train.py" in entrypoint_refs, entrypoint_refs
    assert "entrypoint:eval.py" in entrypoint_refs, entrypoint_refs
    assert "entrypoint:scripts/run_train.sh" in entrypoint_refs, entrypoint_refs

    # ------------------------------------------------------------------
    # Step 2: search_symbols -> locate the ``train`` function in train.py
    # ------------------------------------------------------------------
    search_symbols = _find_tool(tool_list, "search_symbols")
    step2 = search_symbols.invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-step2",
            goal="Locate the train function",
            query="train",
        )
    )
    assert step2["status"] == "success", step2
    symbol_refs = list(step2["result_refs"])
    # The symbol index should surface the toplevel ``train`` function (and
    # possibly ``GaussianModel.forward`` from model.py, but ``train`` must
    # be there).
    train_symbol_refs = [ref for ref in symbol_refs if "train.py:train" in ref]
    assert train_symbol_refs, symbol_refs

    # ------------------------------------------------------------------
    # Step 3: read_symbol -> read the source span of ``train``
    # ------------------------------------------------------------------
    read_symbol = _find_tool(tool_list, "read_symbol")
    step3 = read_symbol.invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-step3",
            goal="Read the train function body",
            path="train.py",
            symbol="train",
            top_k=1,
        )
    )
    assert step3["status"] == "success", step3
    span_ids = list(step3["exact_span_ids"])
    assert len(span_ids) == 1, span_ids
    span = span_ids[0]
    assert span.startswith("span:train.py:"), span
    # The span must cover at least 5 lines (the train() body is multi-line).
    _, start_str, end_str = span.rsplit(":", 2)
    start, end = int(start_str), int(end_str)
    assert end - start >= 4, f"train() span too short: {start}-{end}"

    # ------------------------------------------------------------------
    # Step 4: find_references -> every place GaussianModel is used
    # ------------------------------------------------------------------
    find_references = _find_tool(tool_list, "find_references")
    step4 = find_references.invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-step4",
            goal="Find every usage of GaussianModel",
            symbol="GaussianModel",
        )
    )
    assert step4["status"] == "success", step4
    ref_paths = {
        ref.rsplit(":", 1)[0].removeprefix("ref:") for ref in step4["result_refs"]
    }
    # GaussianModel is imported and instantiated in both train.py and eval.py.
    # The class definition site in model.py is NOT a "reference" - only
    # imports and usages count, so model.py must NOT appear here.
    assert "train.py" in ref_paths, ref_paths
    assert "eval.py" in ref_paths, ref_paths
    assert "model.py" not in ref_paths, ref_paths


def test_every_step_of_closure_carries_full_return_contract(tools) -> None:
    """Every observation in the closure must carry the R1.2 return contract.

    This guards against a future refactor that drops a field from
    ResearchObservationV1: the manifest return_fields list is the
    public contract, and every step must honor it.
    """

    tool_list, ctx = tools
    manifest = build_research_tool_manifest()
    return_fields = manifest.tools[0].return_fields
    assert return_fields == RESEARCH_TOOL_RETURN_FIELDS

    # Step 1: find_entrypoints
    step1 = _find_tool(tool_list, "find_entrypoints").invoke(
        _base_kwargs(ctx, tool_call_id="tc-contract-1")
    )
    for field in return_fields:
        assert field in step1, f"find_entrypoints missing return field {field}"
    assert step1["input_digest"].startswith("sha256:")
    assert step1["output_digest"].startswith("sha256:")

    # Step 2: search_symbols
    step2 = _find_tool(tool_list, "search_symbols").invoke(
        _base_kwargs(ctx, tool_call_id="tc-contract-2", query="GaussianModel")
    )
    for field in return_fields:
        assert field in step2, f"search_symbols missing return field {field}"

    # Step 3: read_symbol
    step3 = _find_tool(tool_list, "read_symbol").invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-contract-3",
            path="model.py",
            symbol="GaussianModel",
            top_k=1,
        )
    )
    for field in return_fields:
        assert field in step3, f"read_symbol missing return field {field}"

    # Step 4: find_references
    step4 = _find_tool(tool_list, "find_references").invoke(
        _base_kwargs(ctx, tool_call_id="tc-contract-4", symbol="GaussianModel")
    )
    for field in return_fields:
        assert field in step4, f"find_references missing return field {field}"


def test_closure_does_not_invoke_legacy_intake_stage(tools) -> None:
    """The V3 closure must NOT depend on ``legacy_intake_stage_tool.run_intake``.

    We assert the negative: the legacy intake stage tool is not imported by
    the V3 research tool runtime, and the closure above does not call it.
    This is the R1.4 "no legacy intake stage" exit condition.
    """

    # The research tool runtime modules must not transitively import the
    # legacy intake stage tool.
    import code2paper.agentic.research_tools as research_tools_mod
    import code2paper.agentic.research_tool_manifest as manifest_mod

    research_tools_source = Path(research_tools_mod.__file__).read_text(encoding="utf-8")
    manifest_source = Path(manifest_mod.__file__).read_text(encoding="utf-8")
    assert "legacy_intake_stage_tool" not in research_tools_source
    assert "legacy_intake_stage_tool" not in manifest_source
    assert "run_intake" not in research_tools_source
    assert "run_intake" not in manifest_source

    # And the manifest must only register the four V3 tool names.
    manifest = build_research_tool_manifest()
    assert {tool.name for tool in manifest.tools} == set(RESEARCH_TOOL_NAMES)


# ---------------------------------------------------------------------------
# Closure variants: the same loop works for eval.py / model.py
# ---------------------------------------------------------------------------


def test_closure_can_target_eval_entrypoint_and_model_class(tools) -> None:
    """The closure is parametric: a supervisor can re-target it at eval.py."""

    tool_list, ctx = tools

    # Step 1: find_entrypoints restricted to eval.py
    step1 = _find_tool(tool_list, "find_entrypoints").invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-eval-1",
            path_scope=("eval.py",),
        )
    )
    assert step1["status"] == "success"
    # StructuredTool.invoke returns the observation as a JSON-serialized dict,
    # so result_refs is a list (not a tuple).
    assert list(step1["result_refs"]) == ["entrypoint:eval.py"]

    # Step 2: search_symbols for the ``evaluate`` function
    step2 = _find_tool(tool_list, "search_symbols").invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-eval-2",
            query="evaluate",
        )
    )
    assert step2["status"] == "success"
    assert any("eval.py:evaluate" in ref for ref in step2["result_refs"])

    # Step 3: read_symbol of GaussianModel.forward in model.py
    step3 = _find_tool(tool_list, "read_symbol").invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-eval-3",
            path="model.py",
            symbol="GaussianModel.forward",
            top_k=1,
        )
    )
    assert step3["status"] == "success"
    assert step3["exact_span_ids"][0].startswith("span:model.py:")


def test_closure_reports_success_empty_for_unknown_target(tools) -> None:
    """The closure gracefully reports ``success_empty`` for missing targets.

    A supervisor that asks for a non-existent symbol must get a
    ``success_empty`` observation, not a crash.  This is the
    anti-hallucination floor for the runtime path.
    """

    tool_list, ctx = tools
    step = _find_tool(tool_list, "read_symbol").invoke(
        _base_kwargs(
            ctx,
            tool_call_id="tc-empty",
            path="train.py",
            symbol="NoSuchFunctionExists",
            top_k=1,
        )
    )
    assert step["status"] == "success_empty"
    assert step["exact_span_ids"] == []
    assert step["result_refs"] == []
