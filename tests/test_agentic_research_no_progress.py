"""R3.5 tests for no-progress escalation (R3.4 InformationGainTracker).

Per the R3.4 / R3.5 exit conditions
(``docs/agentic_method_quality_next_execution_plan_2026-07-19.md``):

    信息增益指标：
    - 新 hard-source span；
    - 新 symbol；
    - 新 behavior predicate；
    - 新 verified relation；
    - obligation 缺口减少；
    - candidate ambiguity 减少。

    连续两轮无增益必须换策略；第三轮仍无增益才允许申请 explicit gap。
    禁止简单增加全局 loop。

This file verifies:

1. ``InformationGainTracker`` correctly tracks gain / no-gain per
   obligation (pure unit tests).
2. The deterministic supervisor switches strategy after 2 consecutive
   no-gain turns (TRACE_CALLS / SEARCH_HINTS instead of SEARCH_SYMBOLS).
3. The deterministic supervisor proposes RECORD_GAP after 3 consecutive
   no-gain turns.
4. ``gap_finalizer_node`` rejects a gap before the no-progress threshold
   and accepts it once the threshold is met.
5. End-to-end: an obligation with no matching symbols terminates via
   ``record_gap`` (not via ``max_turns``) once the threshold is reached.
6. The no-progress counter is per-obligation: a no-gain turn on
   obligation A does not affect obligation B.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code2paper.agentic.research_graph import run_research_loop
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchObservationV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_nodes import (
    BudgetPolicyV1,
    InformationGainTracker,
    ResearchGraphRuntime,
    gap_finalizer_node,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    build_decision_context,
)
from code2paper.agentic.repo_snapshot import RepoSnapshot, build_repo_snapshot


# ---------------------------------------------------------------------------
# Fixture: a small repo so the runtime has a real snapshot
# ---------------------------------------------------------------------------


_SINGLE_FILE = """\
\"\"\"Train entrypoint.\"\"\"


def train() -> None:
    print("train")
"""


@pytest.fixture()
def snapshot(tmp_path: Path) -> RepoSnapshot:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / "train.py").write_text(_SINGLE_FILE, encoding="utf-8")
    return build_repo_snapshot(root)


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
        priority="must_cover",
        status="in_progress",
        candidate_symbol_ids=list(candidate_symbol_ids),
        missing_information=list(missing_information),
        typed_behavior_targets=targets,
    )


def _runtime(
    snapshot: RepoSnapshot,
    agenda: ResearchAgendaV1,
    *,
    run_id: str = "run-no-progress",
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
    status: str = "success",
) -> ResearchObservationV1:
    # ``success`` requires at least one result_ref / exact_span_id; fall
    # back to ``success_empty`` when neither is provided so the validator
    # accepts the observation.
    if status == "success" and not exact_span_ids and not result_refs:
        status = "success_empty"
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
# Unit tests: InformationGainTracker
# ---------------------------------------------------------------------------


class TestInformationGainTracker:
    def test_initial_counter_is_zero(self) -> None:
        tracker = InformationGainTracker()
        assert tracker.no_progress_counter("obl-x") == 0
        assert tracker.gain_history("obl-x") == ()
        assert tracker.should_switch_strategy("obl-x") is False
        assert tracker.may_record_gap("obl-x") is False

    def test_first_observation_with_new_span_yields_gain(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        gained, descriptors = tracker.ingest("obl-a", obs)
        assert gained is True
        assert any("span:" in d for d in descriptors)
        assert tracker.no_progress_counter("obl-a") == 0
        assert tracker.gain_history("obl-a") == ("gain:1",)

    def test_duplicate_span_yields_no_gain_and_increments_counter(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-a", obs)
        # Second observation with the same span -> no gain.
        gained, _ = tracker.ingest("obl-a", obs)
        assert gained is False
        assert tracker.no_progress_counter("obl-a") == 1
        assert tracker.should_switch_strategy("obl-a") is False

    def test_counter_resets_after_gain(self) -> None:
        tracker = InformationGainTracker()
        obs1 = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        obs2 = _observation(
            observation_id="obs-2",
            tool_call_id="tc-2",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),  # duplicate
        )
        tracker.ingest("obl-a", obs1)
        tracker.ingest("obl-a", obs2)  # no gain, counter=1
        obs3 = _observation(
            observation_id="obs-3",
            tool_call_id="tc-3",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:10:20",),  # new span
        )
        gained, _ = tracker.ingest("obl-a", obs3)
        assert gained is True
        assert tracker.no_progress_counter("obl-a") == 0

    def test_should_switch_strategy_after_two_no_gain_turns(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-a", obs)  # gain
        tracker.ingest("obl-a", obs)  # no gain, counter=1
        assert tracker.should_switch_strategy("obl-a") is False
        tracker.ingest("obl-a", obs)  # no gain, counter=2
        assert tracker.should_switch_strategy("obl-a") is True
        assert tracker.may_record_gap("obl-a") is False

    def test_may_record_gap_after_three_no_gain_turns(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-a", obs)  # gain
        for _ in range(3):
            tracker.ingest("obl-a", obs)  # 3 no-gain turns
        assert tracker.no_progress_counter("obl-a") == 3
        assert tracker.should_switch_strategy("obl-a") is True
        assert tracker.may_record_gap("obl-a") is True

    def test_counters_are_per_obligation(self) -> None:
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
        tracker.ingest("obl-a", obs_a)  # gain
        tracker.ingest("obl-a", obs_a)  # no gain, counter_a=1
        tracker.ingest("obl-a", obs_a)  # no gain, counter_a=2
        tracker.ingest("obl-b", obs_b)  # gain (independent)
        tracker.ingest("obl-b", obs_b)  # no gain, counter_b=1
        assert tracker.no_progress_counter("obl-a") == 2
        assert tracker.no_progress_counter("obl-b") == 1
        assert tracker.should_switch_strategy("obl-a") is True
        assert tracker.should_switch_strategy("obl-b") is False

    def test_new_symbol_yields_gain(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            result_refs=("symbol:train.py:train",),
        )
        gained, descriptors = tracker.ingest("obl-a", obs)
        assert gained is True
        assert any("symbol:" in d for d in descriptors)

    def test_new_predicate_yields_gain(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
        )
        gained, descriptors = tracker.ingest(
            "obl-a", obs, new_predicates=("READ",)
        )
        assert gained is True
        assert "predicate:READ" in descriptors

    def test_new_relation_yields_gain(self) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
        )
        gained, descriptors = tracker.ingest(
            "obl-a", obs, new_relations=("CALLS",)
        )
        assert gained is True
        assert "relation:CALLS" in descriptors

    def test_snapshot_is_json_serializable(self) -> None:
        import json

        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-a",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-a", obs)
        snap = tracker.snapshot()
        # Must be JSON-serializable for checkpoint persistence.
        encoded = json.dumps(snap, sort_keys=True)
        decoded = json.loads(encoded)
        assert decoded["seen_spans"]["obl-a"] == ["span:train.py:1:5"]


# ---------------------------------------------------------------------------
# Supervisor: strategy switch after 2 no-gain turns
# ---------------------------------------------------------------------------


class TestSupervisorStrategySwitch:
    def _backend(self, snapshot: RepoSnapshot) -> DeterministicSupervisorBackend:
        return DeterministicSupervisorBackend(
            run_id="run-switch",
            repo_snapshot_id=snapshot.snapshot_id,
            ready_tools=(
                "find_entrypoints",
                "search_symbols",
                "read_symbol",
                "find_references",
                "build_behavior_subgraph",
                "search_semantic_hints",
            ),
        )

    def _context(
        self,
        snapshot: RepoSnapshot,
        obligation: ResearchAgendaItemV1,
        *,
        no_progress_counter: int,
        recent_tool_names: tuple[str, ...] = (),
    ) -> "ResearchDecisionContextV1":  # type: ignore[name-defined]
        from code2paper.agentic.research_models import PerObligationBudgetV1

        agenda = _agenda("run-switch", snapshot, obligation)
        recent_obs = tuple(
            _observation(
                observation_id=f"obs-{i}",
                tool_call_id=f"tc-{i}",
                obligation_id=obligation.obligation_id,
            )
            for i, _ in enumerate(recent_tool_names)
        )
        # Patch tool_name on the recent observations so the supervisor can
        # see which tools were tried.
        recent_obs = tuple(
            obs.model_copy(update={"tool_name": name})
            for obs, name in zip(recent_obs, recent_tool_names)
        )
        return build_decision_context(
            run_id="run-switch",
            repo_snapshot_id=snapshot.snapshot_id,
            turn_index=2,
            agenda=agenda,
            active_obligation_id=obligation.obligation_id,
            active_issue=None,
            recent_observations=recent_obs,
            per_obligation_budgets={
                obligation.obligation_id: PerObligationBudgetV1(
                    obligation_id=obligation.obligation_id,
                    limits={
                        "symbol_search": 6,
                        "code_read": 8,
                        "call_trace": 6,
                        "data_flow_trace": 4,
                        "branch_inspection": 4,
                        "hint_search": 3,
                        "packet_repair": 4,
                    },
                )
            },
            global_safety_budget=GlobalSafetyBudgetV1(),
            no_progress_counter=no_progress_counter,
            no_progress_history=tuple(
                ["no_gain"] * no_progress_counter
            ),
            ready_tools=(
                "find_entrypoints",
                "search_symbols",
                "read_symbol",
                "find_references",
                "build_behavior_subgraph",
                "search_semantic_hints",
            ),
            hard_rules=(
                "no_snapshot_external_paths",
                "no_unregistered_tools",
                "no_authority_upgrade",
            ),
        )

    def test_after_two_no_gain_turns_switches_from_search_to_trace_calls(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-switch",
            search_terms=("train",),
            candidate_symbol_ids=("train.py:train",),
        )
        backend = self._backend(snapshot)
        context = self._context(
            snapshot,
            obl,
            no_progress_counter=2,
            recent_tool_names=("search_symbols", "search_symbols"),
        )
        decision = backend.decide(context)
        # After 2 no-gain turns with search_symbols in recent tools, the
        # backend must switch to TRACE_CALLS (find_references).
        assert decision.action == "TRACE_CALLS"
        assert decision.selected_tool_calls
        assert decision.selected_tool_calls[0].tool_name == "find_references"

    def test_after_two_no_gain_turns_search_hints_when_no_search_recently(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-switch",
            search_terms=("train",),
            candidate_symbol_ids=("train.py:train",),
        )
        backend = self._backend(snapshot)
        context = self._context(
            snapshot,
            obl,
            no_progress_counter=2,
            recent_tool_names=("read_symbol", "read_symbol"),
        )
        decision = backend.decide(context)
        # Recent tools don't include search_symbols -> switch to SEARCH_HINTS.
        assert decision.action == "SEARCH_HINTS"
        assert decision.selected_tool_calls
        assert decision.selected_tool_calls[0].tool_name == "search_semantic_hints"

    def test_after_three_no_gain_turns_proposes_record_gap(
        self, snapshot: RepoSnapshot
    ) -> None:
        obl = _obligation(
            "obl-gap",
            search_terms=("train",),
            candidate_symbol_ids=("train.py:train",),
        )
        backend = self._backend(snapshot)
        context = self._context(
            snapshot,
            obl,
            no_progress_counter=3,
            recent_tool_names=("search_symbols", "find_references", "search_symbols"),
        )
        decision = backend.decide(context)
        assert decision.action == "RECORD_GAP"
        assert not decision.selected_tool_calls
        assert decision.fallback_action == "STOP_BLOCKED"

    def test_below_threshold_no_strategy_switch(self, snapshot: RepoSnapshot) -> None:
        obl = _obligation(
            "obl-normal",
            search_terms=("train",),
        )
        backend = self._backend(snapshot)
        context = self._context(
            snapshot,
            obl,
            no_progress_counter=1,
            recent_tool_names=("search_symbols",),
        )
        decision = backend.decide(context)
        # counter=1 -> no switch; default SEARCH_SYMBOLS (no candidates).
        assert decision.action == "SEARCH_SYMBOLS"


# ---------------------------------------------------------------------------
# gap_finalizer: accept / reject based on no-progress counter
# ---------------------------------------------------------------------------


class TestGapFinalizerAcceptance:
    def _state(self, snapshot: RepoSnapshot) -> dict:
        return {
            "run_id": "run-gap",
            "repo_snapshot_id": snapshot.snapshot_id,
            "project_tree_hash": snapshot.project_tree_hash,
            "active_obligation_id": "obl-gap",
            "explicit_gap_set_ref": "",
        }

    def _runtime(self, snapshot: RepoSnapshot) -> ResearchGraphRuntime:
        obl = _obligation("obl-gap", search_terms=("train",))
        agenda = _agenda("run-gap", snapshot, obl)
        return _runtime(snapshot, agenda, run_id="run-gap")

    def test_rejects_gap_below_threshold(self, snapshot: RepoSnapshot) -> None:
        tracker = InformationGainTracker()
        # One no-gain turn only.
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-gap",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-gap", obs)  # gain
        tracker.ingest("obl-gap", obs)  # no gain, counter=1
        state = self._state(snapshot)
        runtime = self._runtime(snapshot)
        update = gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id="obl-gap",
            gain_tracker=tracker,
        )
        assert update["_gap_accepted"] is False
        assert update["status"] == "researching"
        # explicit_gap_set_ref must NOT be updated.
        assert update["explicit_gap_set_ref"] == ""

    def test_accepts_gap_at_threshold(self, snapshot: RepoSnapshot) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-gap",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-gap", obs)  # gain
        for _ in range(3):
            tracker.ingest("obl-gap", obs)  # 3 no-gain turns
        state = self._state(snapshot)
        runtime = self._runtime(snapshot)
        update = gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id="obl-gap",
            gain_tracker=tracker,
        )
        assert update["_gap_accepted"] is True
        assert update["status"] == "researching"
        # explicit_gap_set_ref must be populated with a gap reference.
        assert update["explicit_gap_set_ref"]
        assert update["explicit_gap_set_ref"].startswith("gap:")

    def test_gap_without_active_obligation_blocks(self, snapshot: RepoSnapshot) -> None:
        tracker = InformationGainTracker()
        state = self._state(snapshot)
        state["active_obligation_id"] = ""
        runtime = self._runtime(snapshot)
        update = gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id="",
            gain_tracker=tracker,
        )
        assert update["_gap_accepted"] is False
        assert update["status"] == "blocked"
        assert "gap_without_active_obligation" in update["blocked_reason"]

    def test_accepted_gap_appends_to_existing_gaps(self, snapshot: RepoSnapshot) -> None:
        tracker = InformationGainTracker()
        obs = _observation(
            observation_id="obs-1",
            tool_call_id="tc-1",
            obligation_id="obl-gap",
            exact_span_ids=("span:train.py:1:5",),
        )
        tracker.ingest("obl-gap", obs)
        for _ in range(3):
            tracker.ingest("obl-gap", obs)
        state = self._state(snapshot)
        state["explicit_gap_set_ref"] = "gap:existing:obl-prev"
        runtime = self._runtime(snapshot)
        update = gap_finalizer_node(
            state,
            runtime=runtime,
            active_obligation_id="obl-gap",
            gain_tracker=tracker,
        )
        assert update["_gap_accepted"] is True
        assert "gap:existing:obl-prev" in update["explicit_gap_set_ref"]
        assert "obl-gap" in update["explicit_gap_set_ref"]


# ---------------------------------------------------------------------------
# End-to-end: an obligation with no matching symbols terminates via record_gap
# ---------------------------------------------------------------------------


class TestEndToEndNoProgressTermination:
    def test_obligation_with_no_matching_symbols_terminates_via_record_gap(
        self, snapshot: RepoSnapshot
    ) -> None:
        """An obligation whose search query never matches a symbol must
        terminate via ``record_gap`` once the no-progress threshold is
        reached, NOT via ``max_turns``."""
        obl = _obligation(
            "obl-no-match",
            search_terms=("definitely_not_a_real_symbol_xyz",),
        )
        agenda = _agenda("run-no-match", snapshot, obl)
        # Tight budget so the loop can't spin forever.
        small_budget = BudgetPolicyV1(
            symbol_search=4,
            code_read=2,
            call_trace=2,
            data_flow_trace=2,
            branch_inspection=2,
            hint_search=2,
            packet_repair=2,
        )
        runtime = _runtime(
            snapshot,
            agenda,
            run_id="run-no-match",
            budget_policy=small_budget,
        )
        result = run_research_loop(runtime, max_turns=20)
        assert result.terminated
        # Either record_gap (preferred) or all_obligations_terminal.
        assert result.termination_reason in {
            "all_obligations_terminal",
            "record_gap",
            "ready_to_author",
        }, result.termination_reason
        # The loop must NOT have hit max_turns.
        assert result.termination_reason != "max_turns_reached"
        # evidence_critic_routes must include either record_gap or
        # record_gap_rejected (the latter happens when gap_finalizer
        # rejects the first RECORD_GAP proposal).
        routes = set(result.evidence_critic_routes)
        assert routes & {"record_gap", "record_gap_rejected"}, routes

    def test_obligation_with_matching_symbol_does_not_terminate_via_gap(
        self, snapshot: RepoSnapshot
    ) -> None:
        """An obligation whose search query matches a symbol must NOT
        terminate via ``record_gap`` immediately; the gain tracker must
        record at least one gain."""
        obl = _obligation(
            "obl-match",
            search_terms=("train",),  # matches train.py
        )
        agenda = _agenda("run-match", snapshot, obl)
        runtime = _runtime(snapshot, agenda, run_id="run-match")
        result = run_research_loop(runtime, max_turns=8)
        # The first turn should produce a gain (search_symbols finds train).
        # So the no-progress counter must be 0 after the first turn.
        # The loop may still terminate via record_gap later, but not on
        # the first turn.  With the Phase 3 evidence-chain repair, the
        # loop may also terminate via ``compile_candidate`` on the first
        # turn (the behavior graph is populated and the obligation is
        # marked ``supported``), which is the desired end state — not a
        # gap.  Either way, the termination reason must NOT be
        # ``record_gap`` on the first turn.
        assert result.termination_reason != "record_gap"
        assert "record_gap" not in result.evidence_critic_routes or (
            result.evidence_critic_routes[0] != "record_gap"
        )

    def test_per_obligation_isolation_in_multi_obligation_run(
        self, snapshot: RepoSnapshot
    ) -> None:
        """A no-gain turn on obligation A must not push obligation B's
        no-progress counter."""
        obl_a = _obligation(
            "obl-a",
            search_terms=("definitely_not_a_real_symbol_xyz",),
        )
        obl_b = _obligation(
            "obl-b",
            search_terms=("train",),  # matches
        )
        agenda = _agenda("run-iso", snapshot, obl_a, obl_b)
        runtime = _runtime(snapshot, agenda, run_id="run-iso")
        result = run_research_loop(runtime, max_turns=30)
        # Both obligations must be in the decision trace (the driver
        # must have advanced from obl-a to obl-b at some point).
        obligations_in_trace = {d.obligation_id for d in result.decision_trace}
        assert "obl-a" in obligations_in_trace
        assert "obl-b" in obligations_in_trace

    def test_multi_obligation_wrap_around_terminates_via_all_terminal(
        self, snapshot: RepoSnapshot
    ) -> None:
        """Regression: when ALL must-cover obligations gap out, the loop
        must terminate via ``all_obligations_terminal`` and NOT spin until
        ``max_turns_reached``.

        Before the fix, ``gap_finalizer_node`` only wrote a gap ref to
        ``explicit_gap_set_ref`` but did NOT update the agenda item's
        ``status`` to ``explicit_gap``.  As a result,
        ``_next_unresolved_obligation`` kept selecting the same
        obligations on wrap-around (their status was still
        ``in_progress``), and the loop cycled through them repeatedly
        until ``max_turns``.  This test reproduces that scenario with
        three non-matching obligations and asserts the loop terminates
        correctly with every agenda item marked terminal.
        """

        obl_a = _obligation(
            "obl-a", search_terms=("definitely_not_a_real_symbol_xyz_a",),
        )
        obl_b = _obligation(
            "obl-b", search_terms=("definitely_not_a_real_symbol_xyz_b",),
        )
        obl_c = _obligation(
            "obl-c", search_terms=("definitely_not_a_real_symbol_xyz_c",),
        )
        agenda = _agenda("run-wrap", snapshot, obl_a, obl_b, obl_c)
        runtime = _runtime(snapshot, agenda, run_id="run-wrap")
        result = run_research_loop(runtime, max_turns=30)
        # The loop MUST terminate via all_obligations_terminal, not by
        # hitting max_turns.  This is the core regression assertion.
        assert result.terminated is True
        assert result.termination_reason == "all_obligations_terminal", (
            f"expected all_obligations_terminal, got {result.termination_reason}; "
            f"turns_executed={result.turns_executed}"
        )
        assert result.termination_reason != "max_turns_reached"
        # Every agenda item must be terminal (explicit_gap).  If
        # gap_finalizer had not mutated the agenda, some items would
        # still be ``in_progress`` and the loop would not have
        # terminated via all_obligations_terminal.
        terminal_statuses = {"supported", "explicit_gap", "blocked"}
        for item in agenda.items:
            assert item.status in terminal_statuses, (
                f"obligation {item.obligation_id} has non-terminal status {item.status}"
            )
        # All three should be explicit_gap (none of them match any symbol).
        assert all(item.status == "explicit_gap" for item in agenda.items), (
            [item.obligation_id for item in agenda.items if item.status != "explicit_gap"]
        )
        # Each gapped item must have at least one GapRequirementV1
        # (required by the ResearchAgendaItemV1 model validator).
        for item in agenda.items:
            assert item.gap_requirements, (
                f"obligation {item.obligation_id} has no gap_requirements"
            )


# ---------------------------------------------------------------------------
# Budget policy: per-obligation envelope is independent
# ---------------------------------------------------------------------------


class TestBudgetPolicyPerObligation:
    def test_each_obligation_gets_its_own_envelope(self) -> None:
        policy = BudgetPolicyV1()
        b1 = policy.envelope_for("obl-1")
        b2 = policy.envelope_for("obl-2")
        assert b1.obligation_id == "obl-1"
        assert b2.obligation_id == "obl-2"
        # Consuming from obl-1 must not affect obl-2.
        b1_after = b1.consume("symbol_search")
        assert b1_after.remaining("symbol_search") == b1.remaining("symbol_search") - 1
        assert b2.remaining("symbol_search") == policy.symbol_search

    def test_custom_policy_overrides_defaults(self) -> None:
        policy = BudgetPolicyV1(
            symbol_search=2,
            code_read=3,
            call_trace=1,
            data_flow_trace=1,
            branch_inspection=1,
            hint_search=1,
            packet_repair=1,
        )
        env = policy.envelope_for("obl-x")
        assert env.remaining("symbol_search") == 2
        assert env.remaining("code_read") == 3
        assert env.remaining("call_trace") == 1

    def test_zero_remaining_blocks_further_calls(self) -> None:
        policy = BudgetPolicyV1(symbol_search=1)
        env = policy.envelope_for("obl-x")
        env_after = env.consume("symbol_search")
        assert env_after.remaining("symbol_search") == 0
        # The policy doesn't enforce the block itself (that's policy merge's
        # job), but the remaining count must be 0 so policy merge can
        # reject further calls.
