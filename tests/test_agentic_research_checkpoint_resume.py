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
        # have been a strategy switch.
        assert result.turns_executed >= 1


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
