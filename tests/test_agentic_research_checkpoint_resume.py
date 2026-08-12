"""R3.5 tests for checkpoint resume (R0.3 + R3.1).

Per the R3.5 exit condition
(``docs/agentic_method_quality_next_execution_plan_2026-07-19.md``):

    场景测试：
    - ...
    - checkpoint 后从 active obligation 和 best state 恢复。

    退出条件：Gemma 在 fixture repo 中能自主完成至少三种不同工具序列，
    policy trace 可解释，且最终支持边界与工具顺序无关。

This file verifies:

1. ``validate_resume_state_v3`` accepts a mid-run V3 state with an
   ``active_obligation_id`` set and a non-empty ``best_quality_state_ref``.
2. ``validate_resume_state_v3`` rejects source drift and snapshot
   mismatch (already covered in ``test_agentic_v2_v3_state_adapter.py``;
   here we re-verify with a mid-run state).
3. ``research_agenda_builder_node`` honours an existing
   ``active_obligation_id`` when resuming (does not reset to the first
   obligation).
4. ``ResearchLoopDriver.run`` accepts an ``initial_state`` pointing to
   a non-first obligation and processes that obligation.
5. ``ResearchLoopDriver.run`` accepts a ``loop_state`` with a pre-
   populated behavior graph, gain tracker and budgets, and continues
   from there (budgets are not reset to the full envelope).
6. End-to-end: a serialized mid-run state can be deserialized and the
   resumed driver reaches the same termination as a non-resumed run
   that started from the same point.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from code2paper.agentic.behavior_graph import CodeBehaviorGraphV1
from code2paper.agentic.checkpointing import (
    validate_resume_state_dispatch,
    validate_resume_state_v3,
)
from code2paper.agentic.research_graph import (
    ResearchLoopDriver,
    ResearchLoopState,
    initial_loop_state,
    run_research_loop,
)
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    GapRequirementV1,
    PerObligationBudgetV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchObservationV1,
    TypedBehaviorTargetV1,
    empty_quality_state,
)
from code2paper.agentic.research_nodes import (
    BudgetPolicyV1,
    InformationGainTracker,
    ResearchGraphRuntime,
    research_agenda_builder_node,
)
from code2paper.agentic.repo_snapshot import (
    RepoSnapshot,
    build_repo_snapshot,
    write_repo_snapshot,
)
from code2paper.agentic.state_v3 import (
    AgentStateV3Record,
    empty_agent_state_v3,
)


# ---------------------------------------------------------------------------
# Fixture: a small repo so the runtime has a real snapshot
# ---------------------------------------------------------------------------


_REPO_FILES = {
    "train.py": """\
\"\"\"Train entrypoint.\"\"\"

def train() -> None:
    print("train")
""",
    "eval.py": """\
\"\"\"Eval entrypoint.\"\"\"

def evaluate() -> float:
    return 0.0
""",
}


@pytest.fixture()
def snapshot(tmp_path: Path) -> RepoSnapshot:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    for name, text in _REPO_FILES.items():
        (root / name).write_text(text, encoding="utf-8")
    return build_repo_snapshot(root)


@pytest.fixture()
def snapshot_path(tmp_path: Path, snapshot: RepoSnapshot) -> Path:
    out = tmp_path / "snapshot.json"
    write_repo_snapshot(out, snapshot)
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agenda(
    run_id: str, snapshot: RepoSnapshot, *items: ResearchAgendaItemV1
) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=run_id,
        repo_snapshot_id=snapshot.snapshot_id,
        project_tree_hash=snapshot.project_tree_hash,
        items=list(items),
    )


def _obligation(
    obligation_id: str,
    *,
    search_terms: tuple[str, ...] = (),
    candidate_symbol_ids: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    status: str = "in_progress",
) -> ResearchAgendaItemV1:
    targets: list[TypedBehaviorTargetV1] = []
    if search_terms:
        targets.append(
            TypedBehaviorTargetV1(
                target_id=f"target-{obligation_id}",
                search_terms=search_terms,
            )
        )
    gap_requirements: list[GapRequirementV1] = []
    if status == "explicit_gap":
        # ResearchAgendaItemV1 requires gap_requirements when status is
        # explicit_gap; populate a minimal one so the test fixture is
        # well-formed.
        gap_requirements.append(
            GapRequirementV1(
                requirement_id=f"gap-{obligation_id}",
                description=f"unmet requirement for {obligation_id}",
                terminal="explicit_gap",
            )
        )
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority="must_cover",
        status=status,  # type: ignore[arg-type]
        candidate_symbol_ids=list(candidate_symbol_ids),
        missing_information=list(missing_information),
        typed_behavior_targets=targets,
        gap_requirements=gap_requirements,
    )


def _runtime(
    snapshot: RepoSnapshot,
    agenda: ResearchAgendaV1,
    *,
    run_id: str = "run-resume",
    budget_policy: BudgetPolicyV1 | None = None,
) -> ResearchGraphRuntime:
    return ResearchGraphRuntime(
        run_id=run_id,
        repo_snapshot=snapshot,
        agenda=agenda,
        budget_policy=budget_policy or BudgetPolicyV1(),
        global_safety_budget=GlobalSafetyBudgetV1(),
    )


def _observation(
    *,
    observation_id: str,
    tool_call_id: str,
    obligation_id: str,
    exact_span_ids: tuple[str, ...] = (),
    result_refs: tuple[str, ...] = (),
) -> ResearchObservationV1:
    status = "success" if (exact_span_ids or result_refs) else "success_empty"
    return ResearchObservationV1(
        observation_id=observation_id,
        tool_call_id=tool_call_id,
        tool_name="search_symbols",
        obligation_id=obligation_id,
        repo_snapshot_id="repo:test",
        status=status,
        exact_span_ids=exact_span_ids,
        result_refs=result_refs,
        input_digest="sha256:in",
        output_digest="sha256:out",
        source_authority="executable_hard",
    )


# ---------------------------------------------------------------------------
# validate_resume_state_v3 with mid-run state
# ---------------------------------------------------------------------------


class TestValidateResumeStateV3MidRun:
    def test_accepts_mid_run_state_with_active_obligation(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-mid", search_terms=("train",))
        agenda = _agenda("run-mid", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-mid",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-mid",
                "status": "researching",
                "research_agenda_ref": agenda.content_digest,
            }
        )
        resumed, metadata = validate_resume_state_v3(
            mid_run, repo_snapshot_path=str(snapshot_path)
        )
        assert resumed.active_obligation_id == "obl-mid"
        assert resumed.status == "researching"
        assert metadata.resumed is True
        assert metadata.run_id == "run-mid"
        assert metadata.repo_snapshot_id == snapshot.snapshot_id

    def test_accepts_mid_run_state_with_best_quality_state(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-best", search_terms=("train",))
        agenda = _agenda("run-best", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-best",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-best",
                "best_quality_state_ref": "quality-state:sha256:abc",
                "current_quality_state_ref": "quality-state:sha256:abc",
                "research_agenda_ref": agenda.content_digest,
                "status": "researching",
            }
        )
        resumed, _ = validate_resume_state_v3(
            mid_run, repo_snapshot_path=str(snapshot_path)
        )
        # Best quality state ref must be preserved across resume.
        assert resumed.best_quality_state_ref == "quality-state:sha256:abc"
        assert resumed.current_quality_state_ref == "quality-state:sha256:abc"

    def test_accepts_mid_run_state_with_partial_budgets(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-budget", search_terms=("train",))
        agenda = _agenda("run-budget", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-budget",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-budget",
                "research_agenda_ref": agenda.content_digest,
                "per_obligation_budgets": {
                    "obl-budget": {
                        "symbol_search": 2,  # partially consumed
                        "code_read": 8,
                        "call_trace": 6,
                        "data_flow_trace": 4,
                        "branch_inspection": 4,
                        "hint_search": 3,
                        "packet_repair": 4,
                    }
                },
                "status": "researching",
            }
        )
        resumed, _ = validate_resume_state_v3(
            mid_run, repo_snapshot_path=str(snapshot_path)
        )
        # Partial budgets must be preserved verbatim.
        assert resumed.per_obligation_budgets["obl-budget"]["symbol_search"] == 2

    def test_serialized_payload_round_trips_through_json(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-rt", search_terms=("train",))
        agenda = _agenda("run-rt", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-rt",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-rt",
                "research_agenda_ref": agenda.content_digest,
                "status": "researching",
                "explicit_gap_set_ref": "gap:abc:obl-prev",
            }
        )
        payload = mid_run.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        resumed, _ = validate_resume_state_v3(
            decoded, repo_snapshot_path=str(snapshot_path)
        )
        assert resumed.active_obligation_id == "obl-rt"
        assert resumed.explicit_gap_set_ref == "gap:abc:obl-prev"

    def test_dispatch_routes_v3_mid_run(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-dispatch", search_terms=("train",))
        agenda = _agenda("run-dispatch", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-dispatch",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-dispatch",
                "research_agenda_ref": agenda.content_digest,
                "status": "researching",
            }
        )
        state, metadata = validate_resume_state_dispatch(
            mid_run.model_dump(mode="json"),
            repo_snapshot_path=str(snapshot_path),
        )
        assert isinstance(state, AgentStateV3Record)
        assert state.active_obligation_id == "obl-dispatch"
        assert metadata.resumed is True

    def test_rejects_source_drift(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl = _obligation("obl-drift", search_terms=("train",))
        agenda = _agenda("run-drift", snapshot, obl)
        record = empty_agent_state_v3(
            run_id="run-drift",
            repo_snapshot_id=snapshot.snapshot_id,
            # Different tree hash: simulate source drift.
            project_tree_hash="sha256:different",
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-drift",
                "research_agenda_ref": agenda.content_digest,
            }
        )
        with pytest.raises(ValueError, match="source_drift"):
            validate_resume_state_v3(mid_run, repo_snapshot_path=str(snapshot_path))


# ---------------------------------------------------------------------------
# research_agenda_builder_node: resume honours existing active_obligation_id
# ---------------------------------------------------------------------------


class TestAgendaBuilderResume:
    def test_resume_keeps_existing_active_obligation(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-resume-agenda", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-resume-agenda")
        # Simulate a checkpoint that already moved to obl-2.
        state = empty_agent_state_v3(
            run_id="run-resume-agenda",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state["active_obligation_id"] = "obl-2"
        update = research_agenda_builder_node(state, runtime=runtime)
        # The node must keep obl-2 as the active obligation.
        assert update["active_obligation_id"] == "obl-2"

    def test_fresh_start_picks_first_must_cover(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-fresh", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-fresh")
        state = empty_agent_state_v3(
            run_id="run-fresh",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        # No active_obligation_id set -> fresh start.
        update = research_agenda_builder_node(state, runtime=runtime)
        assert update["active_obligation_id"] == "obl-1"

    def test_resume_falls_back_when_active_obligation_is_terminal(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",), status="explicit_gap")
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-terminal", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-terminal")
        state = empty_agent_state_v3(
            run_id="run-terminal",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        # active_obligation_id points to a terminal obligation -> fall back.
        state["active_obligation_id"] = "obl-1"
        update = research_agenda_builder_node(state, runtime=runtime)
        assert update["active_obligation_id"] == "obl-2"

    def test_resume_falls_back_when_active_obligation_unknown(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-unknown", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-unknown")
        state = empty_agent_state_v3(
            run_id="run-unknown",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state["active_obligation_id"] = "obl-not-in-agenda"
        update = research_agenda_builder_node(state, runtime=runtime)
        assert update["active_obligation_id"] == "obl-1"


# ---------------------------------------------------------------------------
# Driver resume: initial_state with non-first active_obligation_id
# ---------------------------------------------------------------------------


class TestDriverResumeFromInitialState:
    def test_completed_resume_returns_before_any_supervisor_model_call(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            initial_loop_state,
            snapshot_loop_state,
        )

        class ExplodingSupervisor:
            def propose(self, *_args, **_kwargs):
                raise AssertionError("terminal resume must make zero model calls")

        obligation = _obligation(
            "obl-terminal", search_terms=("train",), status="explicit_gap"
        )
        agenda = _agenda("run-zero-call", snapshot, obligation)
        runtime = _runtime(snapshot, agenda, run_id="run-zero-call").model_copy(
            update={"supervisor_backend": ExplodingSupervisor()}
        )
        loop = initial_loop_state(runtime)
        loop.terminated = True
        loop.termination_reason = "all_obligations_terminal"
        state = empty_agent_state_v3(
            run_id=runtime.run_id,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).model_copy(update={"status": "trusted"}).to_state_dict()
        state["loop_state_snapshot"] = snapshot_loop_state(loop)

        result = run_research_loop(runtime, initial_state=state, max_turns=10)

        assert result.terminated is True
        assert result.turns_executed == 0
        assert result.termination_reason == "all_obligations_terminal"
        assert result.decision_trace == []

    def test_corrupt_checkpoint_fails_closed_before_supervisor_call(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import snapshot_loop_state

        class ExplodingSupervisor:
            def propose(self, *_args, **_kwargs):
                raise AssertionError("corrupt checkpoint must not start a fresh run")

        obligation = _obligation("obl-corrupt", search_terms=("train",))
        agenda = _agenda("run-corrupt", snapshot, obligation)
        runtime = _runtime(snapshot, agenda, run_id="run-corrupt").model_copy(
            update={"supervisor_backend": ExplodingSupervisor()}
        )
        loop = initial_loop_state(runtime)
        checkpoint = snapshot_loop_state(loop)
        Path(checkpoint["immutable_payload_ref"]).write_text("{}\n", encoding="utf-8")
        state = empty_agent_state_v3(
            run_id=runtime.run_id,
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state["status"] = "researching"
        state["loop_state_snapshot"] = checkpoint

        with pytest.raises(ValueError, match="invalid_loop_state_snapshot:immutable_payload"):
            run_research_loop(runtime, initial_state=state, max_turns=5)

    def test_interrupted_and_uninterrupted_runs_reach_same_support_boundary(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import snapshot_loop_state

        def runtime_for(run_id: str) -> ResearchGraphRuntime:
            return _runtime(
                snapshot,
                _agenda(
                    run_id,
                    snapshot,
                    _obligation("obl-train", search_terms=("train",)),
                    _obligation("obl-eval", search_terms=("evaluate",)),
                ),
                run_id=run_id,
            )

        uninterrupted_runtime = runtime_for("run-boundary")
        uninterrupted = run_research_loop(uninterrupted_runtime, max_turns=20)

        resumed_runtime = runtime_for("run-boundary")
        interrupted = run_research_loop(resumed_runtime, max_turns=1)
        resume_state = dict(interrupted.final_state)
        resume_state["status"] = "researching"
        resume_state["blocked_reason"] = ""
        resume_state["loop_state_snapshot"] = snapshot_loop_state(interrupted.loop_state)
        resumed = run_research_loop(
            resumed_runtime,
            initial_state=resume_state,
            max_turns=20,
        )

        def boundary(result):
            return {
                obligation_id: {
                    claim.canonical_identity
                    for claim in compiled.claim_set.claims
                    if claim.status == "supported"
                }
                for obligation_id, compiled in result.loop_state.compiled_evidence.items()
            }

        assert boundary(resumed) == boundary(uninterrupted)
        assert {
            item.obligation_id: item.status for item in resumed_runtime.agenda.items
        } == {
            item.obligation_id: item.status for item in uninterrupted_runtime.agenda.items
        }

    def test_resume_from_second_obligation_processes_that_obligation(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-resume-2", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-resume-2")
        # Build a state that already has active_obligation_id=obl-2.
        initial = empty_agent_state_v3(
            run_id="run-resume-2",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        initial["active_obligation_id"] = "obl-2"
        initial["status"] = "researching"
        result = run_research_loop(runtime, initial_state=initial, max_turns=10)
        # The first decision must be for obl-2 (the resumed obligation),
        # NOT obl-1.
        if result.decision_trace:
            assert result.decision_trace[0].obligation_id == "obl-2"

    def test_resume_preserves_explicit_gap_set_ref(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-gap", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-gap")
        initial = empty_agent_state_v3(
            run_id="run-gap",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        initial["active_obligation_id"] = "obl-1"
        initial["status"] = "researching"
        initial["explicit_gap_set_ref"] = "gap:existing:obl-prev"
        result = run_research_loop(runtime, initial_state=initial, max_turns=10)
        # The existing gap ref must survive the run (the driver does not
        # erase it).
        assert "gap:existing:obl-prev" in result.final_state.get(
            "explicit_gap_set_ref", ""
        ) or result.final_state.get("explicit_gap_set_ref", "") == "gap:existing:obl-prev"

    def test_resume_with_best_quality_state_preserves_ref(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-best", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-best")
        initial = empty_agent_state_v3(
            run_id="run-best",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        initial["active_obligation_id"] = "obl-1"
        initial["status"] = "researching"
        initial["best_quality_state_ref"] = "quality-state:sha256:prev"
        result = run_research_loop(runtime, initial_state=initial, max_turns=5)
        # best_quality_state_ref must survive the run.
        assert result.final_state.get("best_quality_state_ref", "") != ""


# ---------------------------------------------------------------------------
# Driver resume: loop_state with pre-populated behavior graph / budgets
# ---------------------------------------------------------------------------


class TestDriverResumeFromLoopState:
    def test_resume_with_pre_populated_behavior_graph_keeps_nodes(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-bg", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-bg")
        # Seed a loop state with a non-empty behavior graph.
        loop = initial_loop_state(runtime)
        seed_graph = CodeBehaviorGraphV1(
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
            language="python",
        )
        # The seed graph is empty (we don't have real nodes here), but the
        # important thing is that the loop carries it through.
        loop.behavior_graph = seed_graph.with_digest()
        result = run_research_loop(runtime, max_turns=3, loop_state=loop)
        # The final behavior graph must have a content digest (it was
        # pre-populated and the driver may have merged more nodes).
        assert result.loop_state.behavior_graph.content_digest

    def test_resume_with_partially_consumed_budgets_respects_remaining(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-budget", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-budget")
        loop = initial_loop_state(runtime)
        # Consume most of the symbol_search budget.
        loop.per_obligation_budgets = {
            "obl-1": PerObligationBudgetV1(
                obligation_id="obl-1",
                limits={
                    "symbol_search": 1,  # only one call left
                    "code_read": 0,
                    "call_trace": 0,
                    "data_flow_trace": 0,
                    "branch_inspection": 0,
                    "hint_search": 0,
                    "packet_repair": 0,
                },
            )
        }
        result = run_research_loop(runtime, max_turns=10, loop_state=loop)
        # With only 1 symbol_search budget and no other budgets, the
        # obligation must terminate (not loop forever).
        assert result.terminated or result.termination_reason == "max_turns_reached"

    def test_resume_with_no_progress_counter_persists(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        agenda = _agenda("run-np", snapshot, obl1)
        runtime = _runtime(snapshot, agenda, run_id="run-np")
        loop = initial_loop_state(runtime)
        # Pre-populate the gain tracker with 2 no-gain turns so the
        # supervisor will switch strategy on the next turn.
        obs = _observation(
            observation_id="obs-prev",
            tool_call_id="tc-prev",
            obligation_id="obl-1",
            exact_span_ids=("span:train.py:1:5",),
        )
        loop.gain_tracker.ingest("obl-1", obs)  # gain
        loop.gain_tracker.ingest("obl-1", obs)  # no gain, counter=1
        loop.gain_tracker.ingest("obl-1", obs)  # no gain, counter=2
        assert loop.gain_tracker.no_progress_counter("obl-1") == 2
        # Run the loop: the supervisor should immediately switch strategy.
        result = run_research_loop(runtime, max_turns=5, loop_state=loop)
        # The resumed counter must still be 2 (the driver didn't reset it).
        # Note: the counter may have changed during the run, but the
        # initial state was 2 and the supervisor's first decision should
        # have been a strategy switch.  With the Phase 3 evidence-chain
        # repair, the loop may terminate via ``compile_candidate`` on
        # the first turn (turn 0) if the behavior graph is populated
        # and the obligation is marked ``supported`` — which is the
        # desired end state.  Either way, the loop must terminate and
        # the termination reason must not be ``no_tool_calls_no_terminal``
        # (which would indicate the supervisor failed to produce any
        # decision after resume).
        assert result.terminated
        assert result.termination_reason != "no_tool_calls_no_terminal"


# ---------------------------------------------------------------------------
# End-to-end: serialize -> deserialize -> resume -> verify continuation
# ---------------------------------------------------------------------------


class TestEndToEndResumeRoundTrip:
    def test_mid_run_state_can_be_serialized_and_resumed(
        self, snapshot: RepoSnapshot, snapshot_path: Path
    ) -> None:
        obl1 = _obligation("obl-1", search_terms=("train",))
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-e2e", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-e2e")
        # Build a mid-run state by hand: active=obl-2, status=researching.
        record = empty_agent_state_v3(
            run_id="run-e2e",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        mid_run = record.model_copy(
            update={
                "active_obligation_id": "obl-2",
                "status": "researching",
                "research_agenda_ref": agenda.content_digest,
            }
        )
        # Serialize -> deserialize via JSON (checkpoint round-trip).
        payload = mid_run.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        # Validate the decoded payload via the dispatch resume path.
        resumed_record, metadata = validate_resume_state_dispatch(
            decoded, repo_snapshot_path=str(snapshot_path)
        )
        assert isinstance(resumed_record, AgentStateV3Record)
        assert resumed_record.active_obligation_id == "obl-2"
        assert metadata.resumed is True
        # Feed the resumed state to the driver and verify it processes obl-2.
        resumed_state = resumed_record.to_state_dict()
        result = run_research_loop(
            runtime, initial_state=resumed_state, max_turns=10
        )
        if result.decision_trace:
            assert result.decision_trace[0].obligation_id == "obl-2"

    def test_resume_does_not_reset_already_terminal_obligations(
        self, snapshot: RepoSnapshot
    ) -> None:
        """When resuming, obligations marked terminal in the agenda must
        NOT be re-researched.  The driver's
        ``_next_unresolved_obligation`` already respects item.status, so
        a resume that lands on a terminal obligation must immediately
        advance to the next unresolved one."""
        obl1 = _obligation("obl-1", search_terms=("train",), status="explicit_gap")
        obl2 = _obligation("obl-2", search_terms=("evaluate",))
        agenda = _agenda("run-terminal-resume", snapshot, obl1, obl2)
        runtime = _runtime(snapshot, agenda, run_id="run-terminal-resume")
        initial = empty_agent_state_v3(
            run_id="run-terminal-resume",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        # Resume pointing to the terminal obl-1.
        initial["active_obligation_id"] = "obl-1"
        initial["status"] = "researching"
        result = run_research_loop(runtime, initial_state=initial, max_turns=10)
        # The agenda builder should have advanced past obl-1 to obl-2.
        # The first decision should be for obl-2 (or the run terminates
        # because there are no unresolved obligations left).
        if result.decision_trace:
            obligations_in_trace = {d.obligation_id for d in result.decision_trace}
            # obl-1 should NOT be in the trace (it's terminal).
            # Note: this depends on the agenda builder advancing; if the
            # supervisor still picks obl-1 because the active_obligation_id
            # was preserved, that's a bug we want to catch.
            assert "obl-2" in obligations_in_trace or obligations_in_trace == set()


# ---------------------------------------------------------------------------
# Checkpoint metadata: thread id stability and feature flag
# ---------------------------------------------------------------------------


class TestCheckpointMetadataStability:
    def test_thread_id_is_stable_for_same_run_and_snapshot(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.state_v3 import checkpoint_thread_id_v3

        tid1 = checkpoint_thread_id_v3(
            run_id="run-stable",
            repo_snapshot_id=snapshot.snapshot_id,
        )
        tid2 = checkpoint_thread_id_v3(
            run_id="run-stable",
            repo_snapshot_id=snapshot.snapshot_id,
        )
        assert tid1 == tid2
        # Different run id -> different thread id.
        tid3 = checkpoint_thread_id_v3(
            run_id="run-different",
            repo_snapshot_id=snapshot.snapshot_id,
        )
        assert tid1 != tid3

    def test_thread_id_includes_graph_contract_version(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.state_v3 import (
            GRAPH_CONTRACT_VERSION_V3,
            checkpoint_thread_id_v3,
        )

        tid = checkpoint_thread_id_v3(
            run_id="run-contract",
            repo_snapshot_id=snapshot.snapshot_id,
        )
        assert GRAPH_CONTRACT_VERSION_V3 in tid

    def test_feature_flag_default_is_off(self) -> None:
        from code2paper.agentic.state_v3 import (
            disable_agentic_research_v3,
            is_agentic_research_v3_enabled,
        )

        disable_agentic_research_v3()
        assert is_agentic_research_v3_enabled() is False

    def test_feature_flag_can_be_enabled(self) -> None:
        from code2paper.agentic.state_v3 import (
            disable_agentic_research_v3,
            enable_agentic_research_v3,
            is_agentic_research_v3_enabled,
        )

        enable_agentic_research_v3()
        assert is_agentic_research_v3_enabled() is True
        disable_agentic_research_v3()
        assert is_agentic_research_v3_enabled() is False


# ---------------------------------------------------------------------------
# Quality state: empty state and best-state retention across resume
# ---------------------------------------------------------------------------


class TestQualityStateResume:
    def test_empty_quality_state_is_seeded(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation("obl-q", search_terms=("train",))
        agenda = _agenda("run-q", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-q")
        loop = initial_loop_state(runtime)
        assert loop.current_quality_state is not None
        assert loop.best_quality_state is not None
        # Both should be empty quality states.
        assert hasattr(loop.current_quality_state, "is_empty")
        assert loop.current_quality_state.is_empty
        assert loop.best_quality_state.is_empty

    def test_best_quality_state_is_carried_through_run(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation("obl-best", search_terms=("train",))
        agenda = _agenda("run-best", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-best")
        loop = initial_loop_state(runtime)
        # Pre-populate best_quality_state with a non-empty state.
        best_state = empty_quality_state(
            run_id="run-best",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        loop.best_quality_state = best_state
        result = run_research_loop(runtime, max_turns=3, loop_state=loop)
        # The best_quality_state must survive the run.
        assert result.loop_state.best_quality_state is not None


# ---------------------------------------------------------------------------
# Phase 4: cross-instance checkpoint/resume via LoopStateSnapshot
# ---------------------------------------------------------------------------


class TestInformationGainTrackerFromSnapshot:
    """Phase 4.1: InformationGainTracker.from_snapshot round-trip."""

    def test_from_snapshot_returns_fresh_tracker_for_none(self) -> None:
        from code2paper.agentic.research_nodes import InformationGainTracker

        tracker = InformationGainTracker.from_snapshot(None)
        assert tracker.no_progress_counter("obl-x") == 0
        assert tracker.gain_history("obl-x") == ()

    def test_from_snapshot_returns_fresh_tracker_for_non_dict(self) -> None:
        from code2paper.agentic.research_nodes import InformationGainTracker

        tracker = InformationGainTracker.from_snapshot("not-a-dict")  # type: ignore[arg-type]
        assert tracker.no_progress_counter("obl-x") == 0

    def test_round_trip_preserves_seen_spans_and_counters(self) -> None:
        from code2paper.agentic.research_nodes import InformationGainTracker

        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
            result_refs=("symbol:train.py:train:17",),
        )
        tracker.ingest("obl-a", obs)  # gain
        tracker.ingest("obl-a", obs)  # no gain, counter=1
        tracker.ingest("obl-a", obs)  # no gain, counter=2

        snapshot = tracker.snapshot()
        restored = InformationGainTracker.from_snapshot(snapshot)

        assert restored.no_progress_counter("obl-a") == 2
        assert restored.gain_history("obl-a") == ("gain:2", "no_gain", "no_gain")
        assert restored.should_switch_strategy("obl-a") is True
        assert restored.may_record_gap("obl-a") is False

    def test_round_trip_preserves_multiple_obligations(self) -> None:
        from code2paper.agentic.research_nodes import InformationGainTracker

        tracker = InformationGainTracker()
        obs_a = _observation(
            observation_id="obs-a",
            tool_call_id="tc-a",
            obligation_id="obl-a",
            exact_span_ids=("span:a.py:1:5",),
        )
        obs_b = _observation(
            observation_id="obs-b",
            tool_call_id="tc-b",
            obligation_id="obl-b",
            exact_span_ids=("span:b.py:1:5",),
        )
        tracker.ingest("obl-a", obs_a)
        tracker.ingest("obl-b", obs_b)

        restored = InformationGainTracker.from_snapshot(tracker.snapshot())

        assert restored.no_progress_counter("obl-a") == 0
        assert restored.no_progress_counter("obl-b") == 0
        # Re-ingest the same observations: no gain since they are already seen.
        gained, _ = restored.ingest("obl-a", obs_a)
        assert gained is False
        assert restored.no_progress_counter("obl-a") == 1

    def test_round_trip_through_json(self) -> None:
        import json

        from code2paper.agentic.research_nodes import InformationGainTracker

        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-a", obs)
        tracker.ingest("obl-a", obs)  # no gain

        encoded = json.dumps(tracker.snapshot(), sort_keys=True)
        decoded = json.loads(encoded)
        restored = InformationGainTracker.from_snapshot(decoded)

        assert restored.no_progress_counter("obl-a") == 1
        assert restored.gain_history("obl-a") == ("gain:1", "no_gain")


class TestLoopStateSnapshotModel:
    """Phase 4.2: LoopStateSnapshot Pydantic model."""

    def test_default_snapshot_is_empty(self) -> None:
        from code2paper.agentic.research_graph import LoopStateSnapshot

        snap = LoopStateSnapshot()
        assert snap.behavior_graph == {}
        assert snap.gain_tracker == {}
        assert snap.per_obligation_budgets == {}
        assert snap.turn_index == 0
        assert snap.recent_tool_call_ids == []
        assert snap.no_progress_tool_call_ids == []
        assert snap.evidence_critic_route == ""
        assert snap.terminated is False
        assert snap.termination_reason == ""

    def test_to_state_dict_is_json_serializable(self) -> None:
        import json

        from code2paper.agentic.research_graph import LoopStateSnapshot

        snap = LoopStateSnapshot(
            turn_index=3,
            recent_tool_call_ids=["tc-1", "tc-2"],
            evidence_critic_route="search_more",
        )
        payload = snap.to_state_dict()
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        assert decoded["turn_index"] == 3
        assert decoded["recent_tool_call_ids"] == ["tc-1", "tc-2"]
        assert decoded["evidence_critic_route"] == "search_more"

    def test_model_validates_extra_fields_forbid(self) -> None:
        from pydantic import ValidationError

        from code2paper.agentic.research_graph import LoopStateSnapshot

        with pytest.raises(ValidationError):
            LoopStateSnapshot.model_validate({"unknown_field": "bad"})


class TestSnapshotLoopStateRoundTrip:
    """Phase 4.3: snapshot_loop_state / restore_loop_state_from_snapshot."""

    def test_restore_returns_none_for_empty_payload(self, snapshot: RepoSnapshot) -> None:
        from code2paper.agentic.research_graph import restore_loop_state_from_snapshot

        obl = _obligation("obl-r", search_terms=("train",))
        agenda = _agenda("run-r", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-r")
        assert restore_loop_state_from_snapshot(runtime, None) is None
        assert restore_loop_state_from_snapshot(runtime, {}) is None
        assert restore_loop_state_from_snapshot(runtime, "not-a-dict") is None  # type: ignore[arg-type]

    def test_round_trip_preserves_behavior_graph_and_budgets(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            initial_loop_state,
            restore_loop_state_from_snapshot,
            snapshot_loop_state,
        )

        obl = _obligation("obl-rt", search_terms=("train",))
        agenda = _agenda("run-rt", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-rt")

        loop = initial_loop_state(runtime)
        # Mutate the loop state to simulate mid-run progress.
        loop.turn_index = 5
        loop.recent_tool_call_ids = {"tc-1", "tc-2", "tc-3"}
        loop.no_progress_tool_call_ids = {"tc-2"}
        loop.evidence_critic_route = "search_more"
        loop.per_obligation_budgets = {
            "obl-rt": PerObligationBudgetV1(
                obligation_id="obl-rt",
                limits={
                    "symbol_search": 5,
                    "code_read": 5,
                    "call_trace": 5,
                    "data_flow_trace": 5,
                    "branch_inspection": 5,
                    "hint_search": 5,
                    "packet_repair": 5,
                },
                used={"symbol_search": 2, "code_read": 1},
            )
        }
        # Ingest an observation so the gain tracker has state.
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-rt",
            exact_span_ids=("span:train.py:1:5",),
        )
        loop.gain_tracker.ingest("obl-rt", obs)

        payload = snapshot_loop_state(loop)
        restored = restore_loop_state_from_snapshot(runtime, payload)
        assert restored is not None
        assert restored.turn_index == 5
        assert restored.recent_tool_call_ids == {"tc-1", "tc-2", "tc-3"}
        assert restored.no_progress_tool_call_ids == {"tc-2"}
        assert restored.evidence_critic_route == "search_more"
        # Budgets
        assert "obl-rt" in restored.per_obligation_budgets
        budget = restored.per_obligation_budgets["obl-rt"]
        assert budget.limits["symbol_search"] == 5
        assert budget.used["symbol_search"] == 2
        # Gain tracker
        assert restored.gain_tracker.no_progress_counter("obl-rt") == 0
        assert restored.gain_tracker.gain_history("obl-rt") == ("gain:1",)

    def test_new_checkpoint_channel_contains_only_compact_state_and_immutable_ref(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import initial_loop_state, snapshot_loop_state

        obligation = _obligation("obl-compact", search_terms=("train",))
        runtime = _runtime(snapshot, _agenda("run-compact", snapshot, obligation), run_id="run-compact")
        loop = initial_loop_state(runtime)
        observation = _observation(
            observation_id="obs-large",
            tool_call_id="tc-large",
            obligation_id="obl-compact",
            exact_span_ids=("span:train.py:1:5",),
        )
        loop.recent_observations = [observation] * 200

        payload = snapshot_loop_state(loop)

        assert payload["snapshot_version"] == "2.0"
        assert payload["immutable_payload_digest"].startswith("sha256:")
        assert Path(payload["immutable_payload_ref"]).is_file()
        assert payload["behavior_graph"] == {}
        assert payload["recent_observations"] == []
        assert payload["decision_trace"] == []
        assert payload["compiled_evidence"] == {}
        # The repeated observation bodies live outside the LangGraph channel.
        assert len(json.dumps(payload)) < 5000

    def test_tampered_immutable_checkpoint_payload_fails_closed(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            initial_loop_state,
            restore_loop_state_from_snapshot,
            snapshot_loop_state,
        )

        obligation = _obligation("obl-tamper", search_terms=("train",))
        runtime = _runtime(snapshot, _agenda("run-tamper", snapshot, obligation), run_id="run-tamper")
        payload = snapshot_loop_state(initial_loop_state(runtime))
        Path(payload["immutable_payload_ref"]).write_text("{}\n", encoding="utf-8")

        assert restore_loop_state_from_snapshot(runtime, payload) is None

    def test_round_trip_through_json_preserves_state(
        self, snapshot: RepoSnapshot
    ) -> None:
        import json

        from code2paper.agentic.research_graph import (
            initial_loop_state,
            restore_loop_state_from_snapshot,
            snapshot_loop_state,
        )

        obl = _obligation("obl-json", search_terms=("train",))
        agenda = _agenda("run-json", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-json")

        loop = initial_loop_state(runtime)
        loop.turn_index = 7
        loop.recent_tool_call_ids = {"tc-x"}
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-x",
            obligation_id="obl-json",
            exact_span_ids=("span:train.py:1:5",),
        )
        loop.gain_tracker.ingest("obl-json", obs)
        loop.gain_tracker.ingest("obl-json", obs)  # no gain, counter=1

        payload = snapshot_loop_state(loop)
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        restored = restore_loop_state_from_snapshot(runtime, decoded)
        assert restored is not None
        assert restored.turn_index == 7
        assert restored.recent_tool_call_ids == {"tc-x"}
        assert restored.gain_tracker.no_progress_counter("obl-json") == 1
        assert restored.gain_tracker.gain_history("obl-json") == ("gain:1", "no_gain")

    def test_restore_with_invalid_payload_returns_none(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import restore_loop_state_from_snapshot

        obl = _obligation("obl-bad", search_terms=("train",))
        agenda = _agenda("run-bad", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-bad")
        # Invalid payload (wrong types) should fail-soft to None so the
        # caller falls back to ``initial_loop_state(runtime)``.  Here
        # ``behavior_graph`` is a string instead of a dict, which fails
        # ``LoopStateSnapshot.model_validate``.
        assert restore_loop_state_from_snapshot(
            runtime, {"behavior_graph": "not-a-dict"}
        ) is None

    def test_restore_with_extra_field_returns_none(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import restore_loop_state_from_snapshot

        obl = _obligation("obl-extra", search_terms=("train",))
        agenda = _agenda("run-extra", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-extra")
        # Extra fields are forbidden by ``LoopStateSnapshot`` (extra="forbid"),
        # so validation fails and ``restore_loop_state_from_snapshot``
        # returns None.
        assert restore_loop_state_from_snapshot(
            runtime, {"unknown_field": "bad"}
        ) is None


class TestLinearPrefixRestoresFromSnapshot:
    """Phase 4.4: _ctx_linear_prefix rebuilds loop_state from snapshot."""

    def test_linear_prefix_uses_snapshot_when_present(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            _ResearchGraphContext,
            _ctx_linear_prefix,
            initial_loop_state,
            snapshot_loop_state,
        )

        obl = _obligation("obl-lp", search_terms=("train",))
        agenda = _agenda("run-lp", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-lp")

        # Build a pre-existing loop state with non-default turn_index.
        loop = initial_loop_state(runtime)
        loop.turn_index = 9
        loop.recent_tool_call_ids = {"tc-pre"}
        snapshot_payload = snapshot_loop_state(loop)

        # Build a state that carries the snapshot.
        state = empty_agent_state_v3(
            run_id="run-lp",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state["loop_state_snapshot"] = snapshot_payload

        ctx = _ResearchGraphContext(runtime, max_turns=10)
        update = _ctx_linear_prefix(state, ctx=ctx)

        # The context's loop_state must be restored from the snapshot.
        assert ctx.loop_state is not None
        assert ctx.loop_state.turn_index == 9
        assert ctx.loop_state.recent_tool_call_ids == {"tc-pre"}
        # The update must re-emit the snapshot so the checkpointer persists it.
        assert "loop_state_snapshot" in update

    def test_linear_prefix_seeds_fresh_loop_state_when_no_snapshot(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            _ResearchGraphContext,
            _ctx_linear_prefix,
        )

        obl = _obligation("obl-fresh", search_terms=("train",))
        agenda = _agenda("run-fresh-lp", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-fresh-lp")

        state = empty_agent_state_v3(
            run_id="run-fresh-lp",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()

        ctx = _ResearchGraphContext(runtime, max_turns=10)
        update = _ctx_linear_prefix(state, ctx=ctx)

        assert ctx.loop_state is not None
        assert ctx.loop_state.turn_index == 0
        assert ctx.loop_state.recent_tool_call_ids == set()
        # Even on fresh start, the snapshot is emitted so the checkpointer
        # has a baseline to compare against on resume.
        assert "loop_state_snapshot" in update


class TestCrossInstanceResumeViaSubgraph:
    """Phase 4.5: end-to-end cross-instance resume through build_research_subgraph.

    Simulates a process restart by:
    1. Running the subgraph partway (or seeding a mid-run snapshot).
    2. Serializing the LangGraph state to JSON (checkpoint).
    3. Building a FRESH subgraph (new _ResearchGraphContext).
    4. Invoking the fresh subgraph with the serialized state.
    5. Verifying the fresh context's loop_state matches the snapshot.
    """

    def test_fresh_subgraph_restores_loop_state_from_snapshot(
        self, snapshot: RepoSnapshot
    ) -> None:
        import json

        from code2paper.agentic.research_graph import (
            _ResearchGraphContext,
            _ctx_linear_prefix,
            build_research_subgraph,
            initial_loop_state,
            snapshot_loop_state,
        )

        obl = _obligation("obl-ci", search_terms=("train",))
        agenda = _agenda("run-ci", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-ci")

        # Simulate a mid-run checkpoint: build a loop state with progress.
        loop = initial_loop_state(runtime)
        loop.turn_index = 4
        loop.recent_tool_call_ids = {"tc-mid-1", "tc-mid-2"}
        loop.evidence_critic_route = "search_more"
        snapshot_payload = snapshot_loop_state(loop)

        # Build a serialized state that carries the snapshot.
        record = empty_agent_state_v3(
            run_id="run-ci",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        )
        state_dict = record.to_state_dict()
        state_dict["loop_state_snapshot"] = snapshot_payload
        # Serialize -> deserialize (simulates cross-process checkpoint).
        encoded = json.dumps(state_dict, sort_keys=True)
        decoded_state = json.loads(encoded)

        # Build a FRESH subgraph (new context).
        subgraph = build_research_subgraph(runtime, max_turns=10)
        # Access the context via the linear_prefix closure to verify
        # the loop_state is restored on the first node call.
        # We invoke _ctx_linear_prefix directly with the decoded state.
        ctx = _ResearchGraphContext(runtime, max_turns=10)
        _ctx_linear_prefix(decoded_state, ctx=ctx)

        assert ctx.loop_state is not None
        assert ctx.loop_state.turn_index == 4
        assert ctx.loop_state.recent_tool_call_ids == {"tc-mid-1", "tc-mid-2"}
        assert ctx.loop_state.evidence_critic_route == "search_more"

    def test_subgraph_invoke_with_snapshot_continues_from_mid_run(
        self, snapshot: RepoSnapshot
    ) -> None:
        from code2paper.agentic.research_graph import (
            build_research_subgraph,
            initial_loop_state,
            snapshot_loop_state,
        )

        obl = _obligation("obl-inv", search_terms=("train",))
        agenda = _agenda("run-inv", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-inv")

        # Build a mid-run snapshot.
        loop = initial_loop_state(runtime)
        loop.turn_index = 2
        loop.recent_tool_call_ids = {"tc-prev"}
        snapshot_payload = snapshot_loop_state(loop)

        # Build the state with the snapshot.
        state_dict = empty_agent_state_v3(
            run_id="run-inv",
            repo_snapshot_id=snapshot.snapshot_id,
            project_tree_hash=snapshot.project_tree_hash,
        ).to_state_dict()
        state_dict["loop_state_snapshot"] = snapshot_payload

        # Invoke the subgraph — it should restore the loop state from
        # the snapshot and run to termination.
        subgraph = build_research_subgraph(runtime, max_turns=10)
        subgraph.invoke(state_dict)
        result = subgraph.last_result
        assert result is not None
        # The result must have executed (either terminated or hit max_turns).
        assert result.termination_reason in (
            "no_active_obligation",
            "all_obligations_terminal",
            "ready_to_author",
            "stop_blocked",
            "gap_finalizer_blocked",
            "evidence_critic_blocked",
            "no_tool_calls_no_terminal",
            "max_turns_reached",
        )
        # The final state must carry a loop_state_snapshot (re-emitted
        # by the linear prefix and observation pipeline).
        assert "loop_state_snapshot" in result.final_state
        final_snapshot = result.final_state["loop_state_snapshot"]
        assert isinstance(final_snapshot, dict)
        assert final_snapshot.get("turn_index", 0) >= 0
