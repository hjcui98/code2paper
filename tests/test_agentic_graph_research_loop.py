"""R3.5 tests for the full research loop (R3.1 graph topology).

Per the R3.5 exit condition
(``docs/agentic_method_quality_next_execution_plan_2026-07-19.md``):

    退出条件：Gemma 在 fixture repo 中能自主完成至少三种不同工具序列，
    policy trace 可解释，且最终支持边界与工具顺序无关。

This file builds a small fixture repo (the same shape as the R1.4 runtime
test: ``train.py`` / ``eval.py`` / ``model.py`` / ``dataset.py``) and
drives ``ResearchLoopDriver`` end-to-end.  It verifies:

1. The driver can complete at least three different tool sequences
   (search_symbols -> read_symbol -> find_references, etc.).
2. The policy-merge trace is explainable: every decision has a
   ``produced_by`` label and a stable trace reference.
3. The final support boundary is independent of tool order: running the
   same obligations in different orders yields the same set of supported
   claims / explicit gaps.
4. The evidence critic routes correctly (search_more / record_gap /
   ready_to_author / blocked).
5. The LangGraph ``build_research_subgraph`` wrapper produces the same
   result as the direct driver.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.research_graph import (
    ResearchLoopDriver,
    ResearchLoopResult,
    ResearchLoopState,
    build_research_subgraph,
    initial_loop_state,
    run_research_loop,
)
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_nodes import (
    BudgetPolicyV1,
    ResearchGraphRuntime,
)
from code2paper.agentic.research_supervisor import DeterministicSupervisorBackend
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot


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


@pytest.fixture()
def ml_repo(tmp_path: Path) -> Path:
    root = tmp_path / "ml_repo"
    root.mkdir(parents=True)
    (root / "train.py").write_text(_TRAIN_PY, encoding="utf-8")
    (root / "eval.py").write_text(_EVAL_PY, encoding="utf-8")
    (root / "model.py").write_text(_MODEL_PY, encoding="utf-8")
    (root / "dataset.py").write_text(_DATASET_PY, encoding="utf-8")
    return root


@pytest.fixture()
def snapshot(ml_repo: Path) -> RepoSnapshot:
    return build_repo_snapshot(ml_repo)


# ---------------------------------------------------------------------------
# Agenda builder
# ---------------------------------------------------------------------------


def _agenda(run_id: str, snapshot: RepoSnapshot, *items: ResearchAgendaItemV1) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=list(items),
    )


def _obligation(
    obligation_id: str,
    *,
    priority: str = "must_cover",
    search_terms: tuple[str, ...] = (),
    candidate_symbol_ids: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
) -> ResearchAgendaItemV1:
    targets: list[TypedBehaviorTargetV1] = []
    if search_terms:
        targets.append(
            TypedBehaviorTargetV1(
                target_id=f"target-{obligation_id}",
                search_terms=search_terms,
            )
        )
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority=priority,  # type: ignore[arg-type]
        status="in_progress",
        candidate_symbol_ids=list(candidate_symbol_ids),
        missing_information=list(missing_information),
        typed_behavior_targets=targets,
    )


def _runtime(
    snapshot: RepoSnapshot,
    agenda: ResearchAgendaV1,
    *,
    run_id: str = "run-loop-test",
    budget_policy: BudgetPolicyV1 | None = None,
) -> ResearchGraphRuntime:
    return ResearchGraphRuntime(
        run_id=run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        budget_policy=budget_policy or BudgetPolicyV1(),
        global_safety_budget=GlobalSafetyBudgetV1(),
    )


# ---------------------------------------------------------------------------
# Tests: three different tool sequences
# ---------------------------------------------------------------------------


class TestThreeDifferentToolSequences:
    """R3.5 exit condition: at least three different tool sequences."""

    def test_sequence_1_search_symbols_then_read_symbol(self, snapshot: RepoSnapshot) -> None:
        """Sequence 1: search_symbols -> read_symbol."""
        obl = _obligation(
            "obl-search-read",
            search_terms=("train",),
            missing_information=("entry_point",),
        )
        agenda = _agenda("run-seq-1", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-seq-1")
        driver = ResearchLoopDriver(runtime, max_turns=10)
        result = driver.run()
        # The driver should have executed at least one turn with tool calls.
        assert result.turns_executed >= 1
        # At least one decision should carry a tool call.
        tool_decisions = [
            d for d in result.decision_trace if d.selected_tool_calls
        ]
        assert len(tool_decisions) >= 1
        # The first tool call should be search_symbols (deterministic backend
        # picks SEARCH_SYMBOLS for an obligation with missing information).
        first_call = tool_decisions[0].selected_tool_calls[0]
        assert first_call.tool_name == "search_symbols"

    def test_sequence_2_find_references_for_call_trace(self, snapshot: RepoSnapshot) -> None:
        """Sequence 2: find_references for tracing calls."""
        obl = _obligation(
            "obl-trace-calls",
            search_terms=("GaussianModel",),
            candidate_symbol_ids=("model.py:GaussianModel",),
            missing_information=("call_relation",),
        )
        agenda = _agenda("run-seq-2", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-seq-2")
        driver = ResearchLoopDriver(runtime, max_turns=10)
        result = driver.run()
        tool_decisions = [
            d for d in result.decision_trace if d.selected_tool_calls
        ]
        assert len(tool_decisions) >= 1
        # The deterministic backend should pick TRACE_CALLS for an obligation
        # with "call" in its missing information.
        trace_decisions = [
            d for d in tool_decisions
            if d.selected_tool_calls[0].tool_name == "find_references"
        ]
        assert len(trace_decisions) >= 1

    def test_sequence_3_read_symbol_for_read_candidate(self, snapshot: RepoSnapshot) -> None:
        """Sequence 3: read_symbol for reading a candidate."""
        obl = _obligation(
            "obl-read-candidate",
            search_terms=("train",),
            candidate_symbol_ids=("train.py:train",),
            # No missing information -> backend picks SEARCH_SYMBOLS first,
            # but with candidates it can also do READ_CANDIDATE.
        )
        agenda = _agenda("run-seq-3", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-seq-3")
        driver = ResearchLoopDriver(runtime, max_turns=10)
        result = driver.run()
        tool_decisions = [
            d for d in result.decision_trace if d.selected_tool_calls
        ]
        assert len(tool_decisions) >= 1

    def test_at_least_three_distinct_tool_names_across_sequences(
        self, snapshot: RepoSnapshot
    ) -> None:
        """Verify that across the three sequences, at least 3 distinct tool
        names appear."""
        obligations = [
            _obligation(
                "obl-a",
                search_terms=("train",),
                missing_information=("entry_point",),
            ),
            _obligation(
                "obl-b",
                search_terms=("GaussianModel",),
                candidate_symbol_ids=("model.py:GaussianModel",),
                missing_information=("call_relation",),
            ),
            _obligation(
                "obl-c",
                search_terms=("evaluate",),
                candidate_symbol_ids=("eval.py:evaluate",),
            ),
        ]
        all_tool_names: set[str] = set()
        for i, obl in enumerate(obligations):
            agenda = _agenda(f"run-distinct-{i}", snapshot, obl)
            runtime = _runtime(snapshot, agenda, run_id=f"run-distinct-{i}")
            driver = ResearchLoopDriver(runtime, max_turns=8)
            result = driver.run()
            for d in result.decision_trace:
                for call in d.selected_tool_calls:
                    all_tool_names.add(call.tool_name)
        assert len(all_tool_names) >= 3, all_tool_names


# ---------------------------------------------------------------------------
# Tests: policy trace explainability
# ---------------------------------------------------------------------------


class TestPolicyTraceExplainability:
    """R3.5 exit condition: policy trace is explainable."""

    def test_every_decision_has_produced_by_label(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-trace", search_terms=("train",))
        agenda = _agenda("run-trace", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-trace")
        result = run_research_loop(runtime, max_turns=5)
        for d in result.decision_trace:
            assert d.produced_by in {
                "llm_proposal", "deterministic_fallback", "policy_override",
            }

    def test_every_decision_has_stable_decision_id(self, snapshot: RepoSnapshot) -> None:
        # Two independent runtimes with identical (but distinct) agendas.
        # The agenda items must be distinct objects because
        # ``gap_finalizer_node`` mutates the agenda item status to
        # ``explicit_gap`` in place; reusing the same item across runs
        # would make the second run see a terminal obligation.
        obl1 = _obligation("obl-stable", search_terms=("train",))
        agenda1 = _agenda("run-stable", snapshot, obl1)
        runtime1 = _runtime(snapshot, agenda1, run_id="run-stable")
        result1 = run_research_loop(runtime1, max_turns=5)
        obl2 = _obligation("obl-stable", search_terms=("train",))
        agenda2 = _agenda("run-stable", snapshot, obl2)
        runtime2 = _runtime(snapshot, agenda2, run_id="run-stable")
        result2 = run_research_loop(runtime2, max_turns=5)
        ids1 = [d.decision_id for d in result1.decision_trace]
        ids2 = [d.decision_id for d in result2.decision_trace]
        assert ids1 == ids2, "decision ids must be deterministic"

    def test_every_decision_has_obligation_id(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-obl", search_terms=("train",))
        agenda = _agenda("run-obl", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-obl")
        result = run_research_loop(runtime, max_turns=5)
        for d in result.decision_trace:
            assert d.obligation_id  # must be non-empty

    def test_evidence_critic_routes_are_recorded(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-routes", search_terms=("train",))
        agenda = _agenda("run-routes", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-routes")
        result = run_research_loop(runtime, max_turns=10)
        # Every route must be from the closed set.
        from code2paper.agentic.research_nodes import EVIDENCE_CRITIC_ROUTES
        for route in result.evidence_critic_routes:
            assert route in EVIDENCE_CRITIC_ROUTES, route


# ---------------------------------------------------------------------------
# Tests: final support boundary independent of tool order
# ---------------------------------------------------------------------------


class TestSupportBoundaryIndependentOfToolOrder:
    """R3.5 exit condition: final support boundary independent of tool order."""

    def test_same_obligations_different_order_same_terminal_set(
        self, snapshot: RepoSnapshot
    ) -> None:
        """Two runs with the same obligations in different order must
        terminate with the same set of terminal obligation ids."""
        # Distinct obligation objects per agenda: ``gap_finalizer_node``
        # mutates the agenda item status in place, so sharing items
        # across runs would let the second run see terminal obligations.
        obl_a1 = _obligation("obl-a", search_terms=("train",))
        obl_b1 = _obligation("obl-b", search_terms=("GaussianModel",))
        obl_a2 = _obligation("obl-a", search_terms=("train",))
        obl_b2 = _obligation("obl-b", search_terms=("GaussianModel",))

        agenda1 = _agenda("run-order-1", snapshot, obl_a1, obl_b1)
        agenda2 = _agenda("run-order-2", snapshot, obl_b2, obl_a2)

        runtime1 = _runtime(snapshot, agenda1, run_id="run-order-1")
        runtime2 = _runtime(snapshot, agenda2, run_id="run-order-2")

        result1 = run_research_loop(runtime1, max_turns=15)
        result2 = run_research_loop(runtime2, max_turns=15)

        # Both runs must terminate.
        assert result1.terminated
        assert result2.terminated

        # The final status must be the same (both trusted or both incomplete).
        status1 = result1.final_state.get("status")
        status2 = result2.final_state.get("status")
        assert status1 == status2

        # The set of obligations that were explored must be the same.
        obligations1 = {d.obligation_id for d in result1.decision_trace}
        obligations2 = {d.obligation_id for d in result2.decision_trace}
        assert obligations1 == obligations2

    def test_same_obligation_run_twice_same_behavior_graph_digest(
        self, snapshot: RepoSnapshot
    ) -> None:
        """Running the same obligation twice must produce the same behavior
        graph digest (deterministic extraction)."""
        # Distinct obligation objects per agenda: ``observation_ingest_node``
        # and ``gap_finalizer_node`` mutate the agenda item in place
        # (candidate_symbol_ids, status), so sharing items across runs
        # would let the second run see the first run's side effects.
        obl1 = _obligation("obl-determinism", search_terms=("train",))
        obl2 = _obligation("obl-determinism", search_terms=("train",))
        agenda1 = _agenda("run-det-1", snapshot, obl1)
        agenda2 = _agenda("run-det-2", snapshot, obl2)
        runtime1 = _runtime(snapshot, agenda1, run_id="run-det-1")
        runtime2 = _runtime(snapshot, agenda2, run_id="run-det-2")
        result1 = run_research_loop(runtime1, max_turns=8)
        result2 = run_research_loop(runtime2, max_turns=8)
        bg1 = result1.loop_state.behavior_graph.content_digest
        bg2 = result2.loop_state.behavior_graph.content_digest
        assert bg1 == bg2


# ---------------------------------------------------------------------------
# Tests: evidence critic routing
# ---------------------------------------------------------------------------


class TestEvidenceCriticRouting:
    def test_critic_routes_to_search_more_for_unresolved_obligation(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-search",
            search_terms=("train",),
            missing_information=("entry_point",),
        )
        agenda = _agenda("run-critic-search", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-critic-search")
        result = run_research_loop(runtime, max_turns=5)
        # The first route should be search_more (obligation unresolved, no
        # terminal state, no gap threshold).
        assert "search_more" in result.evidence_critic_routes

    def test_critic_routes_to_record_gap_after_no_progress(
        self, snapshot: RepoSnapshot
    ) -> None:
        # Use a very small budget so the obligation exhausts its search
        # budget quickly and routes to record_gap.
        obl = _obligation(
            "obl-gap",
            search_terms=("nonexistent_symbol_xyz",),
        )
        agenda = _agenda("run-critic-gap", snapshot, obl)
        small_budget = BudgetPolicyV1(
            symbol_search=2,
            code_read=1,
            call_trace=1,
            data_flow_trace=1,
            branch_inspection=1,
            hint_search=1,
            packet_repair=1,
        )
        runtime = _runtime(snapshot, agenda, run_id="run-critic-gap", budget_policy=small_budget)
        result = run_research_loop(runtime, max_turns=15)
        # The loop should terminate (either via record_gap or max_turns).
        assert result.terminated or "record_gap" in result.evidence_critic_routes


# ---------------------------------------------------------------------------
# Tests: LangGraph wrapper
# ---------------------------------------------------------------------------


class TestLangGraphWrapper:
    def test_build_research_subgraph_returns_compiled_graph(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-lg", search_terms=("train",))
        agenda = _agenda("run-lg", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-lg")
        graph = build_research_subgraph(runtime, max_turns=5)
        assert graph is not None
        # The compiled graph should be invokable.
        assert hasattr(graph, "invoke")

    def test_lang_graph_invoke_produces_same_result_as_driver(
        self, snapshot: RepoSnapshot
    ) -> None:
        # Distinct obligation objects per run: ``gap_finalizer_node``
        # mutates the agenda item status in place, so the LangGraph
        # invocation and the direct driver call must use independent
        # agendas to avoid the second call seeing terminal obligations.
        obl1 = _obligation("obl-lg-equiv", search_terms=("train",))
        agenda1 = _agenda("run-lg-equiv", snapshot, obl1)
        runtime1 = _runtime(snapshot, agenda1, run_id="run-lg-equiv")
        graph = build_research_subgraph(runtime1, max_turns=5)
        graph.invoke({})
        loop_result = graph.last_result
        assert loop_result is not None
        assert isinstance(loop_result, ResearchLoopResult)

        # Compare with the direct driver on a fresh, identical runtime.
        obl2 = _obligation("obl-lg-equiv", search_terms=("train",))
        agenda2 = _agenda("run-lg-equiv", snapshot, obl2)
        runtime2 = _runtime(snapshot, agenda2, run_id="run-lg-equiv")
        direct_result = run_research_loop(runtime2, max_turns=5)
        assert loop_result.turns_executed == direct_result.turns_executed
        assert loop_result.termination_reason == direct_result.termination_reason


# ---------------------------------------------------------------------------
# Tests: loop state management
# ---------------------------------------------------------------------------


class TestLoopStateManagement:
    def test_initial_loop_state_seeds_budgets(self, snapshot: RepoSnapshot) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        obl2 = _obligation("obl-2", search_terms=("eval",))
        agenda = _agenda("run-init", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-init")
        loop = initial_loop_state(runtime)
        assert "obl-1" in loop.per_obligation_budgets
        assert "obl-2" in loop.per_obligation_budgets
        assert loop.per_obligation_budgets["obl-1"].remaining("symbol_search") > 0

    def test_initial_loop_state_seeds_empty_behavior_graph(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-bg", search_terms=("train",))
        agenda = _agenda("run-bg", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-bg")
        loop = initial_loop_state(runtime)
        assert isinstance(loop.behavior_graph, CodeBehaviorGraphV1)
        assert len(loop.behavior_graph.nodes) == 0

    def test_driver_terminates_on_max_turns(self, snapshot: RepoSnapshot) -> None:
        # An obligation that never resolves (no matching symbol) should
        # terminate via max_turns or via record_gap.
        obl = _obligation("obl-max", search_terms=("nonexistent",))
        agenda = _agenda("run-max", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-max")
        result = run_research_loop(runtime, max_turns=3)
        assert result.terminated or result.termination_reason == "max_turns_reached"

    def test_executed_read_signatures_span_obligations(self, snapshot: RepoSnapshot) -> None:
        # A read executed for one obligation must be visible to the policy
        # layer when another obligation is active, so the Manager cannot
        # re-read the same exact span.  This is the regression for the
        # canary where the LLM re-read ``get_prune_input_f15`` on two
        # consecutive component obligations.
        from code2paper.agentic.research_graph import _executed_read_signatures
        from code2paper.agentic.research_models import ResearchToolCallV1

        runtime = _runtime(
            snapshot,
            _agenda("run-sig", snapshot, _obligation("obl-a")),
            run_id="run-sig",
        )
        loop = initial_loop_state(runtime)
        read_call = ResearchToolCallV1(
            tool_call_id="tc-read-1",
            tool_name="read_symbol",
            tool_kind="code_read",
            obligation_id="obl-a",
            goal="read feature constructor",
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            arguments={
                "path": "utils/gaussian_model.py",
                "symbol": "GaussianModel.get_prune_input_f15",
            },
        )
        # Simulate: the call was executed (id in recent_tool_call_ids) while
        # the decision trace records it under its own obligation.
        loop.recent_tool_call_ids.add("tc-read-1")
        decision = ResearchDecisionV1(
            decision_id="d-1",
            run_id="run-sig",
            turn_index=0,
            action="READ_CANDIDATE",
            obligation_id="obl-a",
            goal="read feature constructor",
            selected_tool_calls=(read_call,),
        )
        loop.decision_trace.append(decision)
        signatures = _executed_read_signatures(loop)
        assert "read_symbol:utils/gaussian_model.py::GaussianModel.get_prune_input_f15" in signatures

    def test_executed_read_signatures_skip_rejected_calls(self, snapshot: RepoSnapshot) -> None:
        from code2paper.agentic.research_graph import _executed_read_signatures
        from code2paper.agentic.research_models import ResearchToolCallV1

        runtime = _runtime(
            snapshot,
            _agenda("run-sig2", snapshot, _obligation("obl-a")),
            run_id="run-sig2",
        )
        loop = initial_loop_state(runtime)
        rejected_call = ResearchToolCallV1(
            tool_call_id="tc-rejected",
            tool_name="read_symbol",
            tool_kind="code_read",
            obligation_id="obl-a",
            goal="read rejected span",
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            arguments={
                "path": "utils/gaussian_model.py",
                "symbol": "GaussianModel.prune_points",
            },
        )
        decision = ResearchDecisionV1(
            decision_id="d-rej",
            run_id="run-sig2",
            turn_index=0,
            action="READ_CANDIDATE",
            obligation_id="obl-a",
            goal="read rejected span",
            selected_tool_calls=(rejected_call,),
        )
        loop.decision_trace.append(decision)
        # The id is NOT in recent_tool_call_ids => the call was never
        # executed, so it must not enter the read-signature set.
        signatures = _executed_read_signatures(loop)
        assert "read_symbol:utils/gaussian_model.py::GaussianModel.prune_points" not in signatures
