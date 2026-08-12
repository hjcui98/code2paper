"""Phase 6: non-mock end-to-end V3 research architecture tests.

Drives the full V3 multi-node LangGraph topology (9 checkpointable
nodes: linear_prefix -> research_supervisor -> research_tool ->
observation_pipeline -> evidence_critic -> compile_candidate /
gap_finalizer -> obligation_advancer -> terminator) against a real
ML-style fixture project.

These tests do NOT mock the V3 nodes, the V3 runtime builder, or the
V3 subgraph compiler.  The supervisor backend falls back to the
``DeterministicSupervisorBackend`` because the LLM config is set to
``LLMProvider.NONE`` (Phase 6 validates the V3 *plumbing*; Phase 7
validates the real Gemma-backed R8 acceptance on six real projects).

Coverage:

1. ``run_v3_research_phase`` returns a non-None ``ResearchLoopResult``
   with a populated ``node_trace`` that records every multi-node
   LangGraph node execution.
2. The 9 checkpointable nodes all appear in ``node_trace`` (linear_prefix,
   research_supervisor, research_tool, observation_pipeline,
   evidence_critic, compile_candidate, gap_finalizer,
   obligation_advancer, terminator).
3. The research loop terminates cleanly (``loop_state.terminated`` is
   True, ``termination_reason`` is non-empty).
4. ``V3GraphWrapper.invoke`` runs V3 research then the legacy pipeline
   and merges V3 decisions / tool-call trace refs / node trace into
   the legacy payload WITHOUT surfacing a ``v3_error``.
5. ``v3_node_trace`` is non-empty after ``V3GraphWrapper.invoke`` so
   the R8 acceptance checker can verify the multi-node topology
   actually executed.
6. When V3 research produces compiled evidence, the artifacts are
   serialized to ``out_root/artifacts/`` under the standard keys
   (``evidence_packets_v3`` / ``code_facts_v1`` / ``atomic_claims_v3``).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.legacy_stage_tools import build_legacy_stage_tool_registry
from code2paper.agentic.research_graph import (
    CompiledEvidence,
    ResearchLoopResult,
    build_research_subgraph,
)
from code2paper.agentic.repo_snapshot import build_repo_snapshot
from code2paper.agentic.v3_runtime import (
    V3GraphWrapper,
    build_code2paper_v3_graph,
    build_v3_research_runtime,
    merge_compiled_evidence,
    run_v3_research_phase,
    write_v3_evidence_artifacts,
)
from code2paper.schemas import LLMConfig, LLMProvider


# ---------------------------------------------------------------------------
# Fixture: a small ML-research-style project
# ---------------------------------------------------------------------------


_TRAIN_PY = """\
\"\"\"Training entrypoint.\"\"\"

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
    def __init__(self) -> None:
        super().__init__()
        self.gaussians = nn.Parameter(torch.zeros(64, 3))

    def forward(self, batch: Any = None) -> torch.Tensor:
        return self.gaussians.sum()
"""


_DATASET_PY = """\
\"\"\"Dataset definition.\"\"\"

import torch


class SceneDataset:
    def __iter__(self):
        return iter([torch.zeros(8)])
"""


_AUTHOR_MARKERS_YAML = """\
project_goal: "Execute a small Gaussian pipeline."
paper_method_goal: "Describe the executable entrypoint and model forward path."
implementation_scope: "ml_repo current codebase only."
priority_files:
  - "train.py"
  - "model.py"
module_roles:
  - path: "train.py"
    symbol: "main"
    role: "executable entrypoint"
    importance: "core"
    is_novel: false
    notes: "Builds the model and dataset, then invokes the forward path."
pipeline_steps:
  - name: "Model execution"
    purpose: "The executable entrypoint invokes the Gaussian model forward path."
    input:
      - "CLI arguments"
    output:
      - "model output"
    related_files:
      - "train.py"
      - "model.py"
      - "dataset.py"
    highlight_level: "main"
    omit_from_main_figure: false
innovation_claims: []
potential_mismatches: []
"""


@pytest.fixture()
def ml_repo(tmp_path: Path) -> Path:
    """Build a small ML fixture repo with train/eval/model/dataset modules."""

    root = tmp_path / "ml_repo"
    root.mkdir(parents=True)
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "eval.py").write_text(_EVAL_PY, encoding="utf-8")
    (root / "model.py").write_text(_MODEL_PY, encoding="utf-8")
    (root / "dataset.py").write_text(_DATASET_PY, encoding="utf-8")
    return root


@pytest.fixture()
def author_markers_path(tmp_path: Path) -> Path:
    """Write the author markers YAML to a temp file."""

    path = tmp_path / "author_markers.yaml"
    path.write_text(_AUTHOR_MARKERS_YAML, encoding="utf-8")
    return path


@pytest.fixture()
def llm_config_none() -> LLMConfig:
    """An LLM config that forces the supervisor to use deterministic fallback.

    ``LLMProvider.NONE`` makes ``GemmaSupervisorBackend._llm_available``
    return False, so the supervisor delegates to
    ``DeterministicSupervisorBackend`` without attempting any network
    call.  This lets the E2E test exercise the full V3 multi-node
    topology without a running vLLM endpoint.
    """

    return LLMConfig(
        provider=LLMProvider.NONE,
        model="",
        temperature=0.0,
        max_output_tokens=512,
        request_timeout_seconds=5,
        retry_max_attempts=1,
        cache=False,
    )


@pytest.fixture(autouse=True)
def _isolate_v3_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Islate environment variables that affect V3 runtime construction.

    Ensures ``CODE2PAPER_OPENAI_BASE_URL`` and ``OPENAI_API_KEY`` do
    not leak from the host environment (which could trick the
    supervisor into thinking a real vLLM endpoint is available).
    """

    monkeypatch.delenv("CODE2PAPER_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# 1. run_v3_research_phase — full V3 subgraph execution
# ---------------------------------------------------------------------------


class TestRunV3ResearchPhaseFullSubgraph:
    """Verify ``run_v3_research_phase`` drives the 9-node LangGraph to completion."""

    def test_returns_non_none_research_loop_result(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-1",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert isinstance(result, ResearchLoopResult)
        assert result.loop_state is not None

    def test_node_trace_records_required_nodes(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        """Verify the required V3 nodes appear in the execution trace.

        The V3 multi-node topology has 9 nodes, but not all of them
        are executed on every run:

        - **Required nodes** (must appear on every clean run):
          ``linear_prefix``, ``research_supervisor``, ``research_tool``,
          ``observation_pipeline``, ``evidence_critic``, ``terminator``.
        - **Conditional nodes** (appear only when the corresponding
          route is taken):
          ``compile_candidate`` (only when an obligation has candidate
          symbols and no missing information),
          ``gap_finalizer`` (only when the critic routes to
          ``record_gap``),
          ``obligation_advancer`` (only when an obligation reaches a
          terminal state and the loop advances to the next one).
        """

        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-nodes",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        node_names = {entry["node"] for entry in result.node_trace}
        required = {
            "linear_prefix",
            "research_supervisor",
            "research_tool",
            "observation_pipeline",
            "evidence_critic",
            "terminator",
        }
        missing = required - node_names
        assert not missing, f"missing required nodes in node_trace: {missing}"

    def test_node_trace_entries_have_required_fields(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-trace-fields",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert result.node_trace, "node_trace must not be empty"
        required = {"node", "timestamp", "duration_ms", "turn_index", "status", "route", "error"}
        for entry in result.node_trace:
            missing = required - set(entry.keys())
            assert not missing, f"trace entry missing fields: {missing}"

    def test_node_trace_all_entries_status_ok(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-ok",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        bad = [e for e in result.node_trace if e["status"] != "ok"]
        assert not bad, f"nodes with non-ok status: {bad}"

    def test_loop_state_terminated_cleanly(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-term",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert result.loop_state.terminated is True
        assert result.terminated is True
        assert result.termination_reason, "termination_reason must be non-empty"

    def test_decision_trace_non_empty(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-decisions",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert result.decision_trace, "decision_trace must not be empty"
        # Every decision has a produced_by label (deterministic_fallback
        # because the LLM config is NONE).
        for dec in result.decision_trace:
            assert dec.produced_by, "produced_by must be non-empty"

    def test_terminator_is_last_node(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-last",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert result.node_trace, "node_trace must not be empty"
        assert result.node_trace[-1]["node"] == "terminator"

    def test_linear_prefix_is_first_node(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-first",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        assert result.node_trace, "node_trace must not be empty"
        assert result.node_trace[0]["node"] == "linear_prefix"


# ---------------------------------------------------------------------------
# 2. V3GraphWrapper.invoke — V3 + legacy merge
# ---------------------------------------------------------------------------


class TestV3GraphWrapperInvokeE2E:
    """Verify ``V3GraphWrapper.invoke`` runs V3 then legacy and merges results."""

    def _build_wrapper(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        *,
        out_root: Path,
    ) -> V3GraphWrapper:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-wrapper-e2e",
            llm_config=llm_config_none,
        )
        registry = build_legacy_stage_tool_registry()
        wrapper = build_code2paper_v3_graph(
            registry,
            v3_runtime=runtime,
            max_research_turns=15,
        )
        return wrapper

    def _initial_state(self, ml_repo: Path, out_root: Path, author_markers_path: Path) -> AgenticRunState:
        return AgenticRunState(
            project_root=ml_repo,
            out_root=out_root,
            author_markers_path=str(author_markers_path),
        )

    def test_invoke_returns_legacy_payload_without_v3_error(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        payload = wrapper.invoke(initial.model_dump(mode="json"))
        assert isinstance(payload, dict)
        # V3 research must NOT have surfaced an error.
        assert not payload.get("v3_error"), f"v3_error leaked: {payload.get('v3_error')}"

    def test_invoke_populates_v3_node_trace(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        payload = wrapper.invoke(initial.model_dump(mode="json"))
        node_trace = payload.get("v3_node_trace") or []
        assert node_trace, "v3_node_trace must be populated after invoke"
        node_names = {entry["node"] for entry in node_trace}
        assert "terminator" in node_names, "terminator must appear in v3_node_trace"
        assert "linear_prefix" in node_names, "linear_prefix must appear in v3_node_trace"

    def test_invoke_merges_v3_decisions_into_payload(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        payload = wrapper.invoke(initial.model_dump(mode="json"))
        decisions = payload.get("decisions") or []
        # Decisions may be AgentDecision objects (Pydantic models) or
        # dicts depending on the legacy pipeline path.  Normalize to
        # node names for the assertion.
        def _node(d: Any) -> str:
            if hasattr(d, "node"):
                return d.node
            if isinstance(d, dict):
                return d.get("node", "")
            return ""

        v3_decisions = [d for d in decisions if _node(d) == "research_supervisor"]
        assert v3_decisions, "V3 research_supervisor decisions must be merged"

    def test_invoke_merges_v3_tool_call_trace_refs(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        payload = wrapper.invoke(initial.model_dump(mode="json"))
        refs = payload.get("tool_call_trace_refs") or []
        # V3 tool call refs are non-empty when the supervisor issued tool calls.
        assert isinstance(refs, list)

    def test_invoke_sets_last_v3_result(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        wrapper.invoke(initial.model_dump(mode="json"))
        assert wrapper.last_v3_result is not None
        assert isinstance(wrapper.last_v3_result, ResearchLoopResult)
        assert wrapper.last_v3_error is None

    def test_invoke_does_not_raise_on_minimal_state(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        # Even with a minimal state (no pre-resolved artifacts), the
        # wrapper must complete without raising.
        wrapper = self._build_wrapper(
            ml_repo, author_markers_path, llm_config_none, out_root=tmp_path
        )
        initial = self._initial_state(ml_repo, tmp_path, author_markers_path)
        # Should not raise.
        payload = wrapper.invoke(initial.model_dump(mode="json"))
        assert isinstance(payload, dict)


# ---------------------------------------------------------------------------
# 3. V3 compiled evidence serialization (when produced)
# ---------------------------------------------------------------------------


class TestV3CompiledEvidenceSerialization:
    """Verify compiled evidence (when produced) serializes to artifacts/."""

    def test_config_words_do_not_bypass_generic_compile_route(
        self,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        """A config-heavy obligation must still search/read before compiling."""

        fixture_root = Path(__file__).parent / "fixtures" / "research_loop_project"
        intent_path = Path(__file__).parent / "fixtures" / (
            "research_loop_project_author_markers.yaml"
        )
        runtime = build_v3_research_runtime(
            project_root=fixture_root,
            intent_path=intent_path,
            run_id="run-e2e-config-generic-chain",
            llm_config=llm_config_none,
        ).model_copy(update={"artifact_root": tmp_path / "research-tools"})
        result = run_v3_research_phase(runtime, max_turns=30)

        selected_tools = [
            call.tool_name
            for decision in result.decision_trace
            for call in decision.selected_tool_calls
        ]
        assert "search_symbols" in selected_tools
        assert "read_symbol" in selected_tools
        assert "compile_candidate" in result.evidence_critic_routes
        assert result.loop_state.compiled_evidence
        assert result.loop_state.behavior_graph.nodes
        assert (tmp_path / "research-tools" / "research_tool_artifacts" / "validated_packets").is_dir()
        assert (tmp_path / "research-tools" / "research_tool_artifacts" / "authorized_claim_sets").is_dir()

    def test_compiled_evidence_can_be_merged_and_serialized(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
        tmp_path: Path,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-evidence",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        compiled = result.loop_state.compiled_evidence
        assert compiled, "ML fixture must exercise the real behavior-to-evidence chain"
        # When compiled evidence exists, the merge + serialization
        # pipeline must succeed without raising.
        packet_set, fact_set, claim_set = merge_compiled_evidence(
            compiled,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        )
        assert packet_set is not None
        assert fact_set is not None
        assert claim_set is not None
        out_root = tmp_path / "out"
        out_root.mkdir(parents=True)
        paths = write_v3_evidence_artifacts(
            out_root,
            packet_set=packet_set,
            fact_set=fact_set,
            claim_set=claim_set,
        )
        assert "evidence_packets_v3" in paths
        assert "code_facts_v1" in paths
        assert "atomic_claims_v3" in paths
        for key, path_str in paths.items():
            path = Path(path_str)
            assert path.exists(), f"{key} artifact not written: {path}"
            # Must be valid JSON.
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            assert "content_digest" in data

    def test_compiled_evidence_obligation_ids_match_agenda(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-obl-ids",
            llm_config=llm_config_none,
        )
        result = run_v3_research_phase(runtime, max_turns=15)
        compiled = result.loop_state.compiled_evidence
        assert compiled, "ML fixture must exercise the real behavior-to-evidence chain"
        agenda_ids = {item.obligation_id for item in runtime.agenda.items}
        compiled_ids = set(compiled.keys())
        # Compiled evidence obligation IDs must be a subset of agenda IDs.
        unknown = compiled_ids - agenda_ids
        assert not unknown, f"compiled evidence has unknown obligation IDs: {unknown}"


# ---------------------------------------------------------------------------
# 4. Cross-instance resume via snapshot (Phase 4 + Phase 6 integration)
# ---------------------------------------------------------------------------


class TestV3SubgraphCrossInstanceResume:
    """Verify the V3 subgraph state can round-trip through a JSON snapshot.

    Phase 4 introduced ``LoopStateSnapshot`` + ``loop_state_snapshot``
    channel so cross-instance checkpoint/resume can rebuild the
    non-serializable loop state.  Phase 6 verifies the integration
    end-to-end: a fresh subgraph can be built, invoked with a snapshot
    payload from a previous run, and still reach the terminator.
    """

    def test_subgraph_invoke_with_snapshot_restores_loop_state(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        from code2paper.agentic.research_graph import (
            initial_loop_state,
            restore_loop_state_from_snapshot,
            snapshot_loop_state,
        )
        from code2paper.agentic.state_v3 import empty_agent_state_v3

        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-resume",
            llm_config=llm_config_none,
        )
        # Run the subgraph once to produce a snapshot.
        first_result = run_v3_research_phase(runtime, max_turns=15)
        assert first_result.loop_state.terminated is True
        # Build a snapshot from the terminated loop state.
        snapshot = snapshot_loop_state(first_result.loop_state)
        assert isinstance(snapshot, dict)
        assert snapshot["terminated"] is True
        # Restore into a fresh loop state.
        restored = restore_loop_state_from_snapshot(runtime, snapshot)
        assert restored is not None
        assert restored.terminated is True
        assert restored.turn_index == first_result.loop_state.turn_index

    def test_subgraph_invoke_with_empty_snapshot_creates_fresh_loop_state(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        from code2paper.agentic.research_graph import (
            restore_loop_state_from_snapshot,
        )

        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-fresh",
            llm_config=llm_config_none,
        )
        # Empty / None snapshot must yield None (caller falls back to
        # initial_loop_state).
        assert restore_loop_state_from_snapshot(runtime, None) is None
        assert restore_loop_state_from_snapshot(runtime, {}) is None

    def test_memory_saver_resumes_from_next_node_with_fresh_runtime(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        """A process-style restart must resume past the linear prefix."""

        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.errors import GraphRecursionError

        from code2paper.agentic.state_v3 import empty_agent_state_v3

        def make_runtime():
            return build_v3_research_runtime(
                project_root=ml_repo,
                intent_path=author_markers_path,
                run_id="run-e2e-real-resume",
                llm_config=llm_config_none,
            )

        saver = MemorySaver()
        thread = {"configurable": {"thread_id": "v3-real-resume"}}
        first_runtime = make_runtime()
        first = build_research_subgraph(first_runtime, max_turns=30, checkpointer=saver)
        initial = empty_agent_state_v3(
            run_id=first_runtime.run_id,
            repo_snapshot_id=first_runtime.repo_snapshot.snapshot_id,
            project_tree_hash=first_runtime.repo_snapshot.project_tree_hash,
        ).to_state_dict()
        with pytest.raises(GraphRecursionError):
            first.invoke(initial, config={**thread, "recursion_limit": 4})
        interrupted = first.get_state(thread)
        assert interrupted.next
        assert interrupted.next != ("linear_prefix",)

        resumed = build_research_subgraph(make_runtime(), max_turns=30, checkpointer=saver)
        resumed.invoke(None, config={**thread, "recursion_limit": 100})
        result = resumed.last_result
        assert result is not None
        assert result.termination_reason == "all_obligations_terminal"
        assert result.loop_state.compiled_evidence
        assert all(
            item.status in {"supported", "explicit_gap", "blocked"}
            for item in result.loop_state.runtime.agenda.items
        )


# ---------------------------------------------------------------------------
# 5. V3 subgraph topology integrity
# ---------------------------------------------------------------------------


class TestV3SubgraphTopologyIntegrity:
    """Verify the compiled V3 subgraph has the 9-node topology."""

    def test_subgraph_has_nine_named_nodes(
        self,
        ml_repo: Path,
        author_markers_path: Path,
        llm_config_none: LLMConfig,
    ) -> None:
        runtime = build_v3_research_runtime(
            project_root=ml_repo,
            intent_path=author_markers_path,
            run_id="run-e2e-topology",
            llm_config=llm_config_none,
        )
        subgraph = build_research_subgraph(runtime, max_turns=5)
        # ``nodes`` is exposed on the compiled LangGraph.
        compiled = subgraph.compiled
        node_names = set(compiled.nodes.keys())
        expected = {
            "linear_prefix",
            "research_supervisor",
            "research_tool",
            "observation_pipeline",
            "evidence_critic",
            "compile_candidate",
            "gap_finalizer",
            "obligation_advancer",
            "terminator",
        }
        # LangGraph may inject ``__start__`` / ``__end__`` pseudo-nodes;
        # only verify the 9 real nodes are present.
        missing = expected - node_names
        assert not missing, f"missing topology nodes: {missing}"


def test_v3_authoring_fails_closed_without_compiled_v3_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from code2paper.agentic import legacy_authoring_stage_tool

    monkeypatch.setenv("CODE2PAPER_AGENTIC_RESEARCH_V3", "1")
    monkeypatch.setattr(
        legacy_authoring_stage_tool,
        "_has_frozen_evidence",
        lambda state: True,
    )
    state = AgenticRunState(project_root=tmp_path, out_root=tmp_path / "out")
    result = legacy_authoring_stage_tool.run_authoring(state)
    assert result.status.value == "blocked"
    assert result.blocked_reason == "generic_path_compilation_required"
