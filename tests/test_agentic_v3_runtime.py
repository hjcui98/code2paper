"""Tests for the V3 runtime wiring (R8.2/R8.3 code path).

Verifies that:

1. ``_is_v3_research_enabled()`` correctly parses the
   ``CODE2PAPER_AGENTIC_RESEARCH_V3`` environment variable.
2. ``build_research_agenda_from_intent_graph`` converts a V2 intent
   graph into a V1 research agenda (typed targets copied verbatim,
   missing information seeded from retrieval queries + candidate
   paths).
3. ``build_v3_research_runtime`` builds a ``ResearchGraphRuntime``
   configured with ``GemmaSupervisorBackend`` from a fixture project
   + author markers YAML.
4. ``convert_v3_decisions_to_agent_decisions`` maps V3 decisions to
   legacy ``AgentDecision`` records.
5. ``extract_v3_tool_call_trace_refs`` extracts tool-call IDs.
6. ``V3GraphWrapper.invoke`` runs V3 research + the legacy pipeline
   and merges V3 decisions and tool-call trace refs into the legacy
   payload.
7. ``V3GraphWrapper.invoke`` falls back gracefully when V3 research
   raises (the legacy pipeline still runs, no decisions are merged).
8. When ``CODE2PAPER_AGENTIC_RESEARCH_V3=1`` is set,
   ``run_agentic_code2paper`` builds a V3 graph wrapper (not the
   legacy ``build_code2paper_graph``).
9. When the flag is NOT set, ``run_agentic_code2paper`` still builds
   the legacy graph (no regression).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from code2paper.agentic.contracts import AgentDecision, AgenticRunState
from code2paper.agentic.runner import (
    _is_v3_research_enabled,
    run_agentic_code2paper,
)
from code2paper.agentic.research_models import (
    ResearchAction,
    ResearchDecisionV1,
    ResearchToolCallV1,
    TypedBehaviorTargetV1,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationV2,
)
from code2paper.agentic.intent_target_proposer import IntentTargetProposalReportV1
from code2paper.agentic.repo_snapshot import RepoSnapshot
from code2paper.agentic.v3_runtime import (
    V3GraphWrapper,
    build_code2paper_v3_graph,
    build_research_agenda_from_intent_graph,
    build_v3_research_runtime,
    convert_v3_decisions_to_agent_decisions,
    extract_v3_tool_call_trace_refs,
    run_v3_research_phase,
)
from code2paper.core.output_names import artifact_dir
from code2paper.schemas import LLMConfig, LLMProvider


ROOT = Path(__file__).resolve().parents[1]
TOY_MARKERS = ROOT / "tests" / "fixtures" / "toy_train_project_author_markers.yaml"
TOY_PROJECT = ROOT / "tests" / "fixtures" / "toy_train_project"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_v3_flag(value: str | None) -> None:
    """Set or clear the V3 feature flag in the environment."""

    if value is None:
        os.environ.pop("CODE2PAPER_AGENTIC_RESEARCH_V3", None)
    else:
        os.environ["CODE2PAPER_AGENTIC_RESEARCH_V3"] = value


def _intent_graph_with_one_obligation(
    *,
    obligation_id: str = "obl-1",
    author_text: str = "Find the training entrypoint.",
    retrieval_queries: tuple[str, ...] = ("train",),
    candidate_paths: tuple[str, ...] = ("train.py",),
    typed_targets: tuple[TypedBehaviorTargetV1, ...] = (),
) -> IntentObligationGraphV2:
    """Build a minimal V2 intent graph with one obligation."""

    obl = IntentObligationV2(
        obligation_id=obligation_id,
        kind="stage",
        priority="must_cover",
        source_field="pipeline_steps",
        source_index=0,
        author_text=author_text,
        typed_behavior_targets=typed_targets,
        retrieval_queries=retrieval_queries,
        candidate_paths=candidate_paths,
    )
    return IntentObligationGraphV2(
        schema_version="2.0",
        mode="intent-obligation-graph-v2",
        project_goal="goal",
        method_goal="method goal",
        implementation_scope="scope",
        obligations=[obl],
        relations=[],
        content_digest="sha256:fake",
    )


def _repo_snapshot() -> RepoSnapshot:
    """Build a real RepoSnapshot from the toy fixture project."""

    from code2paper.agentic.repo_snapshot import build_repo_snapshot

    return build_repo_snapshot(TOY_PROJECT)


_TOOL_CALLING_ACTIONS = frozenset({
    "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "TRACE_DATA_FLOW",
    "INSPECT_BRANCH", "INSPECT_CONFIG", "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH", "PROPOSE_PACKET", "COMPILE_FACTS",
    "DECOMPOSE_CLAIMS", "REWRITE_SENTENCES",
})


def _v3_decision(
    *,
    decision_id: str = "dec-1",
    action: ResearchAction = "SEARCH_SYMBOLS",
    obligation_id: str = "obl-1",
    tool_calls: tuple[ResearchToolCallV1, ...] | None = None,
    produced_by: str = "llm_proposal",
    rationale: str = "test rationale",
) -> ResearchDecisionV1:
    # ResearchDecisionV1 requires tool-calling actions to have at least
    # one tool call; terminal actions (RECORD_GAP, STOP_BLOCKED,
    # PLAN_METHOD) must have none.  When the caller does not pass
    # ``tool_calls`` explicitly we supply a default for tool-calling
    # actions so the helper is ergonomic.
    if tool_calls is None:
        if action in _TOOL_CALLING_ACTIONS:
            tool_calls = (_tool_call(),)
        else:
            tool_calls = ()
    return ResearchDecisionV1(
        decision_id=decision_id,
        run_id="run-v3-test",
        turn_index=0,
        action=action,
        obligation_id=obligation_id,
        issue_id="",
        goal="test goal",
        selected_tool_calls=tool_calls,
        candidate_scope=(),
        expected_information_gain="gain",
        evidence_needed=(),
        stop_condition="covered",
        fallback_action=None,
        rationale=rationale,
        produced_by=produced_by,
    )


def _tool_call(
    *,
    tool_call_id: str = "tc-1",
    tool_name: str = "search_symbols",
    obligation_id: str = "obl-1",
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind="symbol_search",
        obligation_id=obligation_id,
        goal="test goal",
        repo_snapshot_id="repo:abc",
        arguments={"query": "train"},
    )


def _llm_config() -> LLMConfig:
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gemma4-31b-nvfp4",
        temperature=0.0,
        max_output_tokens=512,
        request_timeout_seconds=10,
        retry_max_attempts=1,
        cache=False,
    )


# ---------------------------------------------------------------------------
# 1. _is_v3_research_enabled env-var parsing
# ---------------------------------------------------------------------------


class IsV3ResearchEnabledTests(unittest.TestCase):
    """Verify the feature flag parser accepts/rejects the right values."""

    def setUp(self) -> None:
        self._old = os.environ.get("CODE2PAPER_AGENTIC_RESEARCH_V3", "")

    def tearDown(self) -> None:
        if self._old:
            os.environ["CODE2PAPER_AGENTIC_RESEARCH_V3"] = self._old
        else:
            os.environ.pop("CODE2PAPER_AGENTIC_RESEARCH_V3", None)

    def test_unset_returns_false(self) -> None:
        os.environ.pop("CODE2PAPER_AGENTIC_RESEARCH_V3", None)
        self.assertFalse(_is_v3_research_enabled())

    def test_empty_string_returns_false(self) -> None:
        _set_v3_flag("")
        self.assertFalse(_is_v3_research_enabled())

    def test_one_returns_true(self) -> None:
        _set_v3_flag("1")
        self.assertTrue(_is_v3_research_enabled())

    def test_true_returns_true(self) -> None:
        _set_v3_flag("true")
        self.assertTrue(_is_v3_research_enabled())

    def test_yes_returns_true(self) -> None:
        _set_v3_flag("yes")
        self.assertTrue(_is_v3_research_enabled())

    def test_on_returns_true(self) -> None:
        _set_v3_flag("on")
        self.assertTrue(_is_v3_research_enabled())

    def test_case_insensitive(self) -> None:
        _set_v3_flag("TRUE")
        self.assertTrue(_is_v3_research_enabled())

    def test_whitespace_is_trimmed(self) -> None:
        _set_v3_flag("  1  ")
        self.assertTrue(_is_v3_research_enabled())

    def test_other_values_return_false(self) -> None:
        for value in ("0", "false", "no", "off", "maybe", "y"):
            with self.subTest(value=value):
                _set_v3_flag(value)
                self.assertFalse(_is_v3_research_enabled())


# ---------------------------------------------------------------------------
# 2. build_research_agenda_from_intent_graph
# ---------------------------------------------------------------------------


class BuildResearchAgendaFromIntentGraphTests(unittest.TestCase):
    """Verify the V2 -> V1 agenda converter."""

    def test_converts_obligation_to_agenda_item(self) -> None:
        graph = _intent_graph_with_one_obligation(
            obligation_id="obl-x",
            author_text="Locate the entrypoint.",
            retrieval_queries=("train", "main"),
            candidate_paths=("train.py",),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        self.assertEqual(agenda.run_id, "run-1")
        self.assertEqual(agenda.repo_snapshot_id, snapshot.snapshot_id)
        self.assertEqual(agenda.project_tree_hash, snapshot.project_tree_hash)
        self.assertEqual(agenda.intent_graph_digest, graph.content_digest)
        self.assertEqual(len(agenda.items), 1)
        item = agenda.items[0]
        self.assertEqual(item.obligation_id, "obl-x")
        self.assertEqual(item.priority, "must_cover")
        self.assertEqual(item.author_text, "Locate the entrypoint.")

    def test_missing_information_seeded_from_retrieval_queries_and_candidate_paths(
        self,
    ) -> None:
        graph = _intent_graph_with_one_obligation(
            retrieval_queries=("train", "main"),
            candidate_paths=("train.py", "model.py"),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        missing = agenda.items[0].missing_information
        self.assertIn("train", missing)
        self.assertIn("main", missing)
        self.assertIn("candidate_path:train.py", missing)
        self.assertIn("candidate_path:model.py", missing)

    def test_missing_information_deduplicated(self) -> None:
        graph = _intent_graph_with_one_obligation(
            retrieval_queries=("train", "train", "main"),
            candidate_paths=("train.py",),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        missing = agenda.items[0].missing_information
        self.assertEqual(missing.count("train"), 1)

    def test_missing_information_falls_back_to_author_text(self) -> None:
        graph = _intent_graph_with_one_obligation(
            author_text="A" * 200,
            retrieval_queries=(),
            candidate_paths=(),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        missing = agenda.items[0].missing_information
        self.assertEqual(len(missing), 1)
        # Truncated to 120 chars.
        self.assertEqual(len(missing[0]), 120)

    def test_typed_behavior_targets_copied_verbatim(self) -> None:
        target = TypedBehaviorTargetV1(
            target_id="tbt-1",
            role="predictor",
            desired_predicates=["COMPUTE"],
            required_relations=[],
            search_terms=["score"],
        )
        graph = _intent_graph_with_one_obligation(
            typed_targets=(target,),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        item = agenda.items[0]
        self.assertEqual(len(item.typed_behavior_targets), 1)
        copied = item.typed_behavior_targets[0]
        self.assertEqual(copied.target_id, "tbt-1")
        self.assertEqual(copied.role, "predictor")
        # Predicates and search_terms are stored as tuples.
        self.assertEqual(tuple(copied.desired_predicates), ("COMPUTE",))
        self.assertEqual(tuple(copied.search_terms), ("score",))

    def test_candidate_symbol_ids_seeded_from_candidate_paths(self) -> None:
        graph = _intent_graph_with_one_obligation(
            candidate_paths=("train.py", "model.py"),
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        item = agenda.items[0]
        self.assertEqual(item.candidate_symbol_ids, ["train.py", "model.py"])

    def test_multiple_obligations_preserved(self) -> None:
        obl1 = IntentObligationV2(
            obligation_id="obl-1",
            kind="stage",
            priority="must_cover",
            source_field="pipeline_steps",
            author_text="first",
        )
        obl2 = IntentObligationV2(
            obligation_id="obl-2",
            kind="stage",
            priority="should_cover",
            source_field="pipeline_steps",
            author_text="second",
        )
        graph = IntentObligationGraphV2(
            schema_version="2.0",
            mode="intent-obligation-graph-v2",
            obligations=[obl1, obl2],
            content_digest="sha256:fake",
        )
        snapshot = _repo_snapshot()
        agenda = build_research_agenda_from_intent_graph(
            graph, run_id="run-1", repo_snapshot=snapshot
        )
        self.assertEqual(len(agenda.items), 2)
        self.assertEqual(agenda.items[0].obligation_id, "obl-1")
        self.assertEqual(agenda.items[1].obligation_id, "obl-2")


# ---------------------------------------------------------------------------
# 3. build_v3_research_runtime
# ---------------------------------------------------------------------------


class BuildV3ResearchRuntimeTests(unittest.TestCase):
    """Verify the runtime builder assembles a GemmaSupervisorBackend."""

    def setUp(self) -> None:
        # The OPENAI provider with a loopback URL does not require an
        # API key (has_provider_api_key returns True for loopback).
        self._old_openai_url = os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "")
        self._old_openai_key = os.environ.get("OPENAI_API_KEY", "")
        os.environ["CODE2PAPER_OPENAI_BASE_URL"] = "http://127.0.0.1:8000/v1"
        os.environ["OPENAI_API_KEY"] = "dummy-local-vllm"

    def tearDown(self) -> None:
        for key, value in [
            ("CODE2PAPER_OPENAI_BASE_URL", self._old_openai_url),
            ("OPENAI_API_KEY", self._old_openai_key),
        ]:
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def test_builds_runtime_with_gemma_supervisor_backend(self) -> None:
        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-build",
            llm_config=_llm_config(),
        )
        from code2paper.agentic.gemma_supervisor_backend import (
            GemmaSupervisorBackend,
        )

        self.assertEqual(runtime.run_id, "run-v3-build")
        self.assertIsNotNone(runtime.repo_snapshot)
        self.assertIsNotNone(runtime.agenda)
        self.assertIsInstance(runtime.supervisor_backend, GemmaSupervisorBackend)

    def test_runtime_agenda_uses_toy_fixture_obligations(self) -> None:
        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-fixture",
            llm_config=_llm_config(),
        )
        # The toy markers have two pipeline steps; the V2 compiler
        # should produce at least one obligation.
        self.assertGreaterEqual(len(runtime.agenda.items), 1)

    def test_runtime_uses_accepted_typed_intent_proposal_before_agenda_build(self) -> None:
        """The live intent proposal is retained and drives the research agenda."""

        import code2paper.agentic.v3_runtime as v3_mod

        observed: list[LLMConfig] = []

        def _enrich(graph: IntentObligationGraphV2, config: LLMConfig):
            observed.append(config)
            replacement = TypedBehaviorTargetV1(
                target_id="target-intent-test",
                role="draft_generation",
                desired_predicates=("CALL",),
                inputs=("draft prefix",),
                outputs=("candidate draft",),
            )
            first = graph.obligations[0].model_copy(update={
                "typed_behavior_targets": (replacement,),
            })
            enriched = graph.model_copy(update={
                "obligations": [first, *graph.obligations[1:]],
            })
            return enriched, IntentTargetProposalReportV1(
                attempted=True,
                accepted=True,
                enriched_obligation_count=len(graph.obligations),
                original_graph_digest=graph.content_digest,
                enriched_graph_digest="sha256:typed-intent-test",
            )

        original = v3_mod.enrich_intent_graph_with_llm
        v3_mod.enrich_intent_graph_with_llm = _enrich
        try:
            runtime = build_v3_research_runtime(
                project_root=TOY_PROJECT,
                intent_path=TOY_MARKERS,
                run_id="run-v3-typed-intent",
                llm_config=_llm_config(),
            )
        finally:
            v3_mod.enrich_intent_graph_with_llm = original

        self.assertEqual(len(observed), 1)
        self.assertTrue(runtime.intent_target_proposal_report["accepted"])
        self.assertEqual(
            runtime.agenda.items[0].typed_behavior_targets[0].role,
            "draft_generation",
        )

    def test_runtime_propagates_ready_tools_and_hard_rules(self) -> None:
        ready = ("search_symbols", "read_symbol")
        rules = ("no_snapshot_external_paths",)
        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-tools",
            llm_config=_llm_config(),
            ready_tools=ready,
            hard_rules=rules,
        )
        self.assertEqual(runtime.ready_tools, ready)
        self.assertEqual(runtime.hard_rules, rules)

    def test_missing_project_root_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            build_v3_research_runtime(
                project_root=Path("/nonexistent/path/xyz"),
                intent_path=TOY_MARKERS,
                run_id="run-v3-missing",
                llm_config=_llm_config(),
            )

    def test_missing_intent_path_still_builds_runtime(self) -> None:
        # When intent_path is empty/missing, load_author_intent_summary
        # returns None and compile_intent_obligation_graph_v2 produces
        # an empty graph.  The runtime is still constructed.
        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path="",
            run_id="run-v3-no-intent",
            llm_config=_llm_config(),
        )
        self.assertEqual(runtime.run_id, "run-v3-no-intent")
        self.assertEqual(len(runtime.agenda.items), 0)


# ---------------------------------------------------------------------------
# 4. convert_v3_decisions_to_agent_decisions
# ---------------------------------------------------------------------------


class ConvertV3DecisionsToAgentDecisionsTests(unittest.TestCase):
    """Verify the V3 -> legacy decision converter."""

    def test_converts_single_decision_with_tool_calls(self) -> None:
        call = _tool_call(tool_call_id="tc-1")
        dec = _v3_decision(
            decision_id="dec-1",
            action="SEARCH_SYMBOLS",
            tool_calls=(call,),
            produced_by="llm_proposal",
            rationale="search for entrypoint",
        )
        converted = convert_v3_decisions_to_agent_decisions([dec])
        self.assertEqual(len(converted), 1)
        agent_dec = converted[0]
        self.assertIsInstance(agent_dec, AgentDecision)
        self.assertEqual(agent_dec.node, "research_supervisor")
        self.assertEqual(agent_dec.decision, "SEARCH_SYMBOLS")
        self.assertIn("llm_proposal:SEARCH_SYMBOLS", agent_dec.rationale)
        self.assertIn("search for entrypoint", agent_dec.rationale)
        self.assertEqual(agent_dec.evidence_ids, ["tc-1"])
        self.assertEqual(agent_dec.artifact_keys, ["obl-1"])

    def test_converts_terminal_action_without_tool_calls(self) -> None:
        dec = _v3_decision(
            decision_id="dec-2",
            action="RECORD_GAP",
            tool_calls=(),
            produced_by="deterministic_fallback",
            rationale="no progress",
        )
        converted = convert_v3_decisions_to_agent_decisions([dec])
        self.assertEqual(len(converted), 1)
        agent_dec = converted[0]
        self.assertEqual(agent_dec.decision, "RECORD_GAP")
        self.assertEqual(agent_dec.evidence_ids, [])
        self.assertIn("deterministic_fallback:RECORD_GAP", agent_dec.rationale)

    def test_preserves_decision_order(self) -> None:
        dec1 = _v3_decision(decision_id="dec-1", action="SEARCH_SYMBOLS")
        dec2 = _v3_decision(decision_id="dec-2", action="READ_CANDIDATE")
        dec3 = _v3_decision(decision_id="dec-3", action="RECORD_GAP")
        converted = convert_v3_decisions_to_agent_decisions([dec1, dec2, dec3])
        self.assertEqual([d.decision for d in converted], ["SEARCH_SYMBOLS", "READ_CANDIDATE", "RECORD_GAP"])

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(convert_v3_decisions_to_agent_decisions([]), [])

    def test_obligation_id_omitted_when_empty(self) -> None:
        dec = _v3_decision(
            decision_id="dec-1",
            action="STOP_BLOCKED",
            obligation_id="",
            tool_calls=(),
        )
        converted = convert_v3_decisions_to_agent_decisions([dec])
        self.assertEqual(converted[0].artifact_keys, [])

    def test_rationale_omits_separator_when_v3_rationale_empty(self) -> None:
        dec = _v3_decision(
            decision_id="dec-1",
            action="SEARCH_SYMBOLS",
            rationale="",
        )
        converted = convert_v3_decisions_to_agent_decisions([dec])
        # No trailing " | ".
        self.assertFalse(converted[0].rationale.endswith(" | "))


# ---------------------------------------------------------------------------
# 5. extract_v3_tool_call_trace_refs
# ---------------------------------------------------------------------------


class ExtractV3ToolCallTraceRefsTests(unittest.TestCase):
    """Verify tool-call trace ref extraction."""

    def test_extracts_refs_in_order(self) -> None:
        call1 = _tool_call(tool_call_id="tc-1")
        call2 = _tool_call(tool_call_id="tc-2")
        dec1 = _v3_decision(decision_id="dec-1", tool_calls=(call1,))
        dec2 = _v3_decision(decision_id="dec-2", tool_calls=(call2,))
        refs = extract_v3_tool_call_trace_refs([dec1, dec2])
        self.assertEqual(refs, ["tc-1", "tc-2"])

    def test_handles_decisions_without_tool_calls(self) -> None:
        # RECORD_GAP is a terminal action: it has no tool calls.
        dec1 = _v3_decision(decision_id="dec-1", action="RECORD_GAP")
        dec2 = _v3_decision(
            decision_id="dec-2",
            tool_calls=(_tool_call(tool_call_id="tc-1"),),
        )
        refs = extract_v3_tool_call_trace_refs([dec1, dec2])
        self.assertEqual(refs, ["tc-1"])

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(extract_v3_tool_call_trace_refs([]), [])

    def test_multiple_tool_calls_in_one_decision(self) -> None:
        call1 = _tool_call(tool_call_id="tc-1")
        call2 = _tool_call(tool_call_id="tc-2")
        call3 = _tool_call(tool_call_id="tc-3")
        dec = _v3_decision(decision_id="dec-1", tool_calls=(call1, call2, call3))
        refs = extract_v3_tool_call_trace_refs([dec])
        self.assertEqual(refs, ["tc-1", "tc-2", "tc-3"])


# ---------------------------------------------------------------------------
# 6. V3GraphWrapper.invoke merges decisions
# ---------------------------------------------------------------------------


class V3GraphWrapperInvokeTests(unittest.TestCase):
    """Verify the wrapper runs V3 + legacy and merges results."""

    def _fake_legacy_graph(
        self, *, return_payload: dict[str, Any] | None = None
    ) -> MagicMock:
        legacy = MagicMock()
        legacy.invoke.return_value = return_payload or {
            "decisions": [
                AgentDecision(
                    node="legacy_node",
                    decision="continue",
                    rationale="legacy ran",
                ).model_dump(mode="json")
            ],
            "tool_call_trace_refs": ["legacy-tc-1"],
        }
        return legacy

    def _fake_runtime_with_decisions(
        self, decisions: list[ResearchDecisionV1]
    ) -> MagicMock:
        runtime = MagicMock()
        # run_v3_research_phase returns a ResearchLoopResult-like object
        # with .decision_trace
        result = MagicMock()
        result.decision_trace = decisions
        runtime.run_id = "run-fake"
        runtime.repo_snapshot = MagicMock(snapshot_id="repo:fake")
        return runtime

    def test_invoke_runs_v3_then_legacy_and_merges_decisions(self) -> None:
        from code2paper.agentic.research_graph import ResearchLoopResult

        v3_decisions = [
            _v3_decision(
                decision_id="dec-v3-1",
                action="SEARCH_SYMBOLS",
                tool_calls=(_tool_call(tool_call_id="tc-v3-1"),),
            )
        ]
        legacy = self._fake_legacy_graph()
        runtime = self._fake_runtime_with_decisions(v3_decisions)

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        # Patch run_v3_research_phase to return our fake result.
        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: MagicMock(
            decision_trace=v3_decisions
        )
        try:
            payload = wrapper.invoke({"some": "state"})
        finally:
            v3_mod.run_v3_research_phase = original

        # Legacy was invoked.
        legacy.invoke.assert_called_once()
        # V3 decisions were merged in.
        decision_dicts = payload["decisions"]
        # Legacy contributed 1, V3 contributed 1.
        self.assertEqual(len(decision_dicts), 2)
        # Tool-call trace refs were merged (legacy + V3).
        self.assertIn("legacy-tc-1", payload["tool_call_trace_refs"])
        self.assertIn("tc-v3-1", payload["tool_call_trace_refs"])

    def test_completed_resume_restores_v3_decisions_from_checkpoint(self) -> None:
        """A no-task resume must reproduce the post-graph V3 merge."""

        v3_decision = _v3_decision(
            decision_id="dec-v3-resume",
            action="SEARCH_SYMBOLS",
            tool_calls=(_tool_call(tool_call_id="tc-v3-resume"),),
        )
        legacy = MagicMock()
        legacy.invoke.return_value = None
        legacy_snapshot = MagicMock()
        legacy_snapshot.values = {
            "decisions": [
                AgentDecision(
                    node="legacy_node",
                    decision="continue",
                    rationale="legacy checkpoint",
                ).model_dump(mode="json")
            ],
            "tool_call_trace_refs": ["legacy-tc-1"],
        }
        legacy.get_state.return_value = legacy_snapshot
        runtime = self._fake_runtime_with_decisions([])

        import code2paper.agentic.v3_runtime as v3_mod

        v3_subgraph = MagicMock()
        v3_snapshot = MagicMock()
        v3_snapshot.values = {
            "loop_state_snapshot": {
                "decision_trace": [v3_decision.model_dump(mode="json")]
            }
        }
        v3_subgraph.get_state.return_value = v3_snapshot
        original_build = v3_mod.build_research_subgraph
        v3_mod.build_research_subgraph = lambda *a, **kw: v3_subgraph
        try:
            wrapper = V3GraphWrapper(
                v3_runtime=runtime,
                legacy_graph=legacy,
                max_research_turns=5,
                v3_checkpointer=MagicMock(),
                v3_thread_id="v3-resume-thread",
            )
            payload = wrapper.invoke(
                None,
                config={"configurable": {"thread_id": "legacy"}},
            )
        finally:
            v3_mod.build_research_subgraph = original_build

        self.assertEqual(len(payload["decisions"]), 2)
        self.assertEqual(payload["decisions"][-1].node, "research_supervisor")
        self.assertEqual(
            payload["tool_call_trace_refs"],
            ["legacy-tc-1", "tc-v3-resume"],
        )
        v3_subgraph.get_state.assert_called_once_with(
            {"configurable": {"thread_id": "v3-resume-thread"}}
        )

    def test_invoke_falls_back_when_v3_research_raises(self) -> None:
        legacy = self._fake_legacy_graph()
        runtime = self._fake_runtime_with_decisions([])

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        # Patch run_v3_research_phase to raise.
        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase

        def _raise(*a: Any, **kw: Any) -> Any:
            raise RuntimeError("v3 blew up")

        v3_mod.run_v3_research_phase = _raise
        try:
            payload = wrapper.invoke({"some": "state"})
        finally:
            v3_mod.run_v3_research_phase = original

        # Legacy was still invoked.
        legacy.invoke.assert_called_once()
        # No V3 decisions were merged (legacy only).
        self.assertEqual(len(payload["decisions"]), 1)
        self.assertEqual(payload["decisions"][0]["node"], "legacy_node")
        # Legacy tool-call trace refs preserved.
        self.assertEqual(payload["tool_call_trace_refs"], ["legacy-tc-1"])
        # V3 error is surfaced in the payload so R8 acceptance can
        # fail the run instead of silently downgrading.
        self.assertIn("v3_error", payload)
        self.assertIn("v3 blew up", payload["v3_error"])
        # last_v3_error property exposes the same error for inspection.
        self.assertIsNotNone(wrapper.last_v3_error)
        self.assertIn("v3 blew up", wrapper.last_v3_error)
        # last_v3_result remains None because V3 never produced a result.
        self.assertIsNone(wrapper.last_v3_result)

    def test_invoke_does_not_merge_when_v3_produces_no_decisions(self) -> None:
        legacy = self._fake_legacy_graph()
        runtime = self._fake_runtime_with_decisions([])

        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: MagicMock(
            decision_trace=[]
        )
        try:
            payload = wrapper.invoke({"some": "state"})
        finally:
            v3_mod.run_v3_research_phase = original

        # Only legacy decisions.
        self.assertEqual(len(payload["decisions"]), 1)
        # Legacy tool-call trace refs preserved (no V3 refs added).
        self.assertEqual(payload["tool_call_trace_refs"], ["legacy-tc-1"])

    def test_get_state_delegates_to_legacy_without_v3_checkpointer(self) -> None:
        """Without V3 checkpointer, get_state returns the legacy snapshot directly."""

        legacy = MagicMock()
        legacy.get_state.return_value = "checkpoint-state"
        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        result = wrapper.get_state(config={"thread_id": "t"})
        legacy.get_state.assert_called_once_with({"thread_id": "t"})
        self.assertEqual(result, "checkpoint-state")

    def test_get_state_returns_v3_aware_snapshot_with_v3_checkpointer(self) -> None:
        """With V3 checkpointer, get_state returns a _V3AwareStateSnapshot."""

        from code2paper.agentic.v3_runtime import _V3AwareStateSnapshot

        legacy = MagicMock()
        legacy_snapshot = MagicMock()
        legacy_snapshot.values = {"run_id": "run-1", "status": "running"}
        legacy_snapshot.next = ("legacy_node",)
        legacy_snapshot.metadata = {"step": 5}
        legacy.get_state.return_value = legacy_snapshot

        runtime = self._fake_runtime_with_decisions([])

        # Patch build_research_subgraph so we don't need a real runtime.
        import code2paper.agentic.v3_runtime as v3_mod

        v3_subgraph = MagicMock()
        v3_snapshot = MagicMock()
        v3_snapshot.values = {"run_id": "run-1", "status": "researching"}
        v3_snapshot.next = ("research_supervisor",)
        v3_snapshot.metadata = {"step": 3}
        v3_subgraph.get_state.return_value = v3_snapshot

        original_build = v3_mod.build_research_subgraph
        v3_mod.build_research_subgraph = lambda *a, **kw: v3_subgraph
        try:
            wrapper = V3GraphWrapper(
                v3_runtime=runtime,
                legacy_graph=legacy,
                max_research_turns=5,
                v3_checkpointer=MagicMock(),
                v3_thread_id="v3-thread-1",
            )
            result = wrapper.get_state(config={"thread_id": "legacy-t"})
        finally:
            v3_mod.build_research_subgraph = original_build

        self.assertIsInstance(result, _V3AwareStateSnapshot)
        # Legacy state is accessible via .values
        self.assertEqual(result.values, {"run_id": "run-1", "status": "running"})
        self.assertEqual(result.next, ("legacy_node",))
        self.assertEqual(result.metadata, {"step": 5})
        # V3 state is accessible via .v3_values
        self.assertTrue(result.has_v3_state)
        self.assertEqual(result.v3_values, {"run_id": "run-1", "status": "researching"})
        self.assertEqual(result.v3_next, ("research_supervisor",))
        self.assertEqual(result.v3_metadata, {"step": 3})
        # Legacy graph's get_state was called with the legacy config.
        legacy.get_state.assert_called_once_with({"thread_id": "legacy-t"})
        # V3 subgraph's get_state was called with the V3 thread_id.
        v3_subgraph.get_state.assert_called_once_with(
            {"configurable": {"thread_id": "v3-thread-1"}}
        )

    def test_get_state_falls_back_to_legacy_when_v3_query_fails(self) -> None:
        """When V3 state query raises, get_state returns legacy snapshot only."""

        legacy = MagicMock()
        legacy_snapshot = MagicMock()
        legacy_snapshot.values = {"run_id": "run-1"}
        legacy.get_state.return_value = legacy_snapshot

        runtime = self._fake_runtime_with_decisions([])

        import code2paper.agentic.v3_runtime as v3_mod

        def _raise(*a, **kw):
            raise RuntimeError("v3 state query failed")

        original_build = v3_mod.build_research_subgraph
        v3_mod.build_research_subgraph = _raise
        try:
            wrapper = V3GraphWrapper(
                v3_runtime=runtime,
                legacy_graph=legacy,
                max_research_turns=5,
                v3_checkpointer=MagicMock(),
                v3_thread_id="v3-thread-1",
            )
            result = wrapper.get_state(config={"thread_id": "legacy-t"})
        finally:
            v3_mod.build_research_subgraph = original_build

        # Falls back to legacy snapshot (not a _V3AwareStateSnapshot).
        self.assertIs(result, legacy_snapshot)

    def test_get_state_returns_legacy_when_v3_checkpointer_none(self) -> None:
        """When v3_checkpointer is None, get_state returns legacy snapshot."""

        legacy = MagicMock()
        legacy_snapshot = MagicMock()
        legacy.get_state.return_value = legacy_snapshot

        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime,
            legacy_graph=legacy,
            max_research_turns=5,
            v3_checkpointer=None,
            v3_thread_id="v3-thread-1",  # thread_id set but no checkpointer
        )
        result = wrapper.get_state(config={"thread_id": "t"})
        self.assertIs(result, legacy_snapshot)

    def test_get_state_returns_legacy_when_v3_thread_id_none(self) -> None:
        """When v3_thread_id is None, get_state returns legacy snapshot."""

        legacy = MagicMock()
        legacy_snapshot = MagicMock()
        legacy.get_state.return_value = legacy_snapshot

        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime,
            legacy_graph=legacy,
            max_research_turns=5,
            v3_checkpointer=MagicMock(),  # checkpointer set but no thread_id
            v3_thread_id=None,
        )
        result = wrapper.get_state(config={"thread_id": "t"})
        self.assertIs(result, legacy_snapshot)

    def test_unknown_attribute_delegates_to_legacy(self) -> None:
        legacy = MagicMock()
        legacy.some_legacy_method.return_value = "legacy-result"
        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        self.assertEqual(wrapper.some_legacy_method(), "legacy-result")

    def test_last_v3_result_is_none_before_invoke(self) -> None:
        legacy = self._fake_legacy_graph()
        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        self.assertIsNone(wrapper.last_v3_result)

    def test_last_v3_result_set_after_successful_invoke(self) -> None:
        legacy = self._fake_legacy_graph()
        runtime = self._fake_runtime_with_decisions([])
        wrapper = V3GraphWrapper(
            v3_runtime=runtime, legacy_graph=legacy, max_research_turns=5
        )
        fake_result = MagicMock()
        import code2paper.agentic.v3_runtime as v3_mod

        original = v3_mod.run_v3_research_phase
        v3_mod.run_v3_research_phase = lambda *a, **kw: fake_result
        try:
            wrapper.invoke({"some": "state"})
        finally:
            v3_mod.run_v3_research_phase = original
        self.assertIs(wrapper.last_v3_result, fake_result)


# ---------------------------------------------------------------------------
# 7. build_code2paper_v3_graph
# ---------------------------------------------------------------------------


class BuildCode2PaperV3GraphTests(unittest.TestCase):
    """Verify the V3 graph builder wraps a legacy graph."""

    def test_builds_wrapper_around_legacy_graph(self) -> None:
        from code2paper.agentic.legacy_stage_tools import (
            build_legacy_stage_tool_registry,
        )

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-graph",
            llm_config=_llm_config(),
        )
        registry = build_legacy_stage_tool_registry()
        wrapper = build_code2paper_v3_graph(
            registry, v3_runtime=runtime, max_research_turns=3
        )
        self.assertIsInstance(wrapper, V3GraphWrapper)
        self.assertIs(wrapper.v3_runtime, runtime)
        # The legacy graph must be a compiled graph (has .invoke).
        self.assertTrue(hasattr(wrapper, "invoke"))
        self.assertTrue(callable(getattr(wrapper, "invoke", None)))


# ---------------------------------------------------------------------------
# 8. run_agentic_code2paper with V3 flag set
# ---------------------------------------------------------------------------


class RunAgenticCode2PaperV3FlagTests(unittest.TestCase):
    """Verify the runner respects the V3 feature flag."""

    def setUp(self) -> None:
        self._old_flag = os.environ.get("CODE2PAPER_AGENTIC_RESEARCH_V3", "")
        self._old_openai_url = os.environ.get("CODE2PAPER_OPENAI_BASE_URL", "")
        self._old_openai_key = os.environ.get("OPENAI_API_KEY", "")
        # Configure the LLM env so the V3 runtime can build an
        # LLMConfig pointing at the local loopback endpoint.
        os.environ["CODE2PAPER_OPENAI_BASE_URL"] = "http://127.0.0.1:8000/v1"
        os.environ["OPENAI_API_KEY"] = "dummy-local-vllm"

    def tearDown(self) -> None:
        for key, value in [
            ("CODE2PAPER_AGENTIC_RESEARCH_V3", self._old_flag),
            ("CODE2PAPER_OPENAI_BASE_URL", self._old_openai_url),
            ("OPENAI_API_KEY", self._old_openai_key),
        ]:
            if value:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def test_v3_flag_set_builds_v3_graph(self) -> None:
        """When CODE2PAPER_AGENTIC_RESEARCH_V3=1, the runner builds a V3 graph.

        We patch ``_build_v3_graph_for_state`` to capture the call and
        return a fake graph that produces a minimal valid payload, so
        we can verify the V3 path was taken without running the full
        pipeline.
        """

        _set_v3_flag("1")
        from code2paper.agentic import runner as runner_mod

        captured: dict[str, Any] = {}

        def _fake_v3_builder(state, registry, **kwargs):
            captured["called"] = True
            captured["state"] = state
            captured["registry"] = registry
            captured["kwargs"] = kwargs
            # Return a fake graph that produces a minimal valid payload.
            def _invoke(payload, *a, **kw):
                st = AgenticRunState.model_validate(payload)
                artifact_path = (
                    artifact_dir(st.method_root, "10_run") / "fake_v3.txt"
                )
                artifact_path.write_text("v3", encoding="utf-8")
                return st.model_copy(
                    update={
                        "artifacts": {"fake_v3": str(artifact_path)},
                        "decisions": [
                            AgentDecision(
                                node="research_supervisor",
                                decision="SEARCH_SYMBOLS",
                                rationale="v3_test",
                            )
                        ],
                        "next_node": "rendering",
                    }
                ).model_dump(mode="json") | {
                    "tool_call_trace_refs": ["v3-tc-1"]
                }

            fake = MagicMock()
            fake.invoke.side_effect = _invoke
            return fake

        original = runner_mod._build_v3_graph_for_state
        runner_mod._build_v3_graph_for_state = _fake_v3_builder
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(
                    project_root=TOY_PROJECT,
                    out_root=Path(tmpdir),
                    author_markers_path=str(TOY_MARKERS),
                )
                result = run_agentic_code2paper(initial)
            self.assertTrue(captured.get("called", False))
            # The V3 tool-call trace ref propagates to the summary.
            self.assertIn("v3-tc-1", result.summary.tool_call_trace_refs)
            # The V3 decision propagates to the summary decisions.
            self.assertTrue(
                any(d.decision == "SEARCH_SYMBOLS" for d in result.summary.decisions)
            )
        finally:
            runner_mod._build_v3_graph_for_state = original

    def test_v3_flag_unset_builds_legacy_graph(self) -> None:
        """When the flag is NOT set, the runner uses ``build_code2paper_graph``.

        We patch ``build_code2paper_graph`` to capture the call and
        return a fake graph, so we can verify the legacy path was
        taken (no V3 builder was called).
        """

        _set_v3_flag(None)
        from code2paper.agentic import runner as runner_mod

        legacy_captured: dict[str, Any] = {}
        v3_captured: dict[str, Any] = {}

        def _fake_legacy_graph(registry, **kwargs):
            legacy_captured["called"] = True
            legacy_captured["registry"] = registry
            legacy_captured["kwargs"] = kwargs

            def _invoke(payload, *a, **kw):
                st = AgenticRunState.model_validate(payload)
                artifact_path = (
                    artifact_dir(st.method_root, "10_run") / "fake_legacy.txt"
                )
                artifact_path.write_text("legacy", encoding="utf-8")
                return st.model_copy(
                    update={
                        "artifacts": {"fake_legacy": str(artifact_path)},
                        "decisions": [
                            AgentDecision(
                                node="legacy_node",
                                decision="continue",
                                rationale="legacy path",
                            )
                        ],
                        "next_node": "rendering",
                    }
                ).model_dump(mode="json")

            fake = MagicMock()
            fake.invoke.side_effect = _invoke
            return fake

        def _fake_v3_builder(state, registry, **kwargs):
            v3_captured["called"] = True
            raise AssertionError("V3 builder must not be called when flag is off")

        original_legacy = runner_mod.build_code2paper_graph
        original_v3 = runner_mod._build_v3_graph_for_state
        runner_mod.build_code2paper_graph = _fake_legacy_graph
        runner_mod._build_v3_graph_for_state = _fake_v3_builder
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(
                    project_root=TOY_PROJECT,
                    out_root=Path(tmpdir),
                    author_markers_path=str(TOY_MARKERS),
                )
                result = run_agentic_code2paper(initial)
            self.assertTrue(legacy_captured.get("called", False))
            self.assertFalse(v3_captured.get("called", False))
            # Legacy decision propagated.
            self.assertTrue(
                any(d.node == "legacy_node" for d in result.summary.decisions)
            )
        finally:
            runner_mod.build_code2paper_graph = original_legacy
            runner_mod._build_v3_graph_for_state = original_v3

    def test_v3_flag_false_does_not_build_v3_graph(self) -> None:
        """``0`` is not a truthy value: legacy path is used."""

        _set_v3_flag("0")
        from code2paper.agentic import runner as runner_mod

        legacy_captured: dict[str, Any] = {}

        def _fake_legacy_graph(registry, **kwargs):
            legacy_captured["called"] = True

            def _invoke(payload, *a, **kw):
                st = AgenticRunState.model_validate(payload)
                artifact_path = (
                    artifact_dir(st.method_root, "10_run") / "fake_legacy.txt"
                )
                artifact_path.write_text("legacy", encoding="utf-8")
                return st.model_copy(
                    update={
                        "artifacts": {"fake_legacy": str(artifact_path)},
                        "decisions": [],
                        "next_node": "rendering",
                    }
                ).model_dump(mode="json")

            fake = MagicMock()
            fake.invoke.side_effect = _invoke
            return fake

        original_legacy = runner_mod.build_code2paper_graph
        runner_mod.build_code2paper_graph = _fake_legacy_graph
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                initial = AgenticRunState(
                    project_root=TOY_PROJECT,
                    out_root=Path(tmpdir),
                )
                run_agentic_code2paper(initial)
            self.assertTrue(legacy_captured.get("called", False))
        finally:
            runner_mod.build_code2paper_graph = original_legacy


# ---------------------------------------------------------------------------
# 9. run_v3_research_phase
# ---------------------------------------------------------------------------


class RunV3ResearchPhaseTests(unittest.TestCase):
    """Verify the V3 research phase executor."""

    def test_runs_research_phase_on_toy_fixture(self) -> None:
        """The V3 research phase completes on the toy fixture.

        The GemmaSupervisorBackend falls back to the deterministic
        backend when the LLM endpoint is unreachable (which it is in
        the test environment), so this verifies the wiring works
        end-to-end with the deterministic fallback.
        """

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-phase",
            llm_config=_llm_config(),
        )
        result = run_v3_research_phase(runtime, max_turns=3)
        # The result must have a decision trace (possibly empty if the
        # agenda was empty, but never None).
        self.assertIsNotNone(result.decision_trace)
        # turns_executed must be a non-negative integer.
        self.assertGreaterEqual(result.turns_executed, 0)

    def test_production_path_uses_multi_node_langgraph_subgraph(self) -> None:
        """run_v3_research_phase must use build_research_subgraph (the
        9-node LangGraph topology), NOT the procedural run_research_loop
        helper.  This is the P0-1 fix: the multi-node graph must be in
        the production path so V3 checkpoints and node execution traces
        are available for R8 verification.
        """

        import code2paper.agentic.v3_runtime as v3_mod
        from code2paper.agentic.research_graph import CompiledResearchSubgraph

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-subgraph",
            llm_config=_llm_config(),
        )

        # Patch build_research_subgraph to track invocation.  We wrap
        # the real implementation so the subgraph still runs.
        original_build = v3_mod.build_research_subgraph
        build_calls: list[dict[str, Any]] = []

        def _tracking_build(runtime_arg: Any, **kwargs: Any) -> CompiledResearchSubgraph:
            build_calls.append({"runtime": runtime_arg, **kwargs})
            return original_build(runtime_arg, **kwargs)

        v3_mod.build_research_subgraph = _tracking_build
        try:
            result = run_v3_research_phase(runtime, max_turns=3)
        finally:
            v3_mod.build_research_subgraph = original_build

        # build_research_subgraph was called exactly once.
        self.assertEqual(len(build_calls), 1)
        # The checkpointer and thread_id were propagated.
        self.assertIn("checkpointer", build_calls[0])
        # The result is still a valid ResearchLoopResult.
        self.assertIsNotNone(result.decision_trace)
        self.assertGreaterEqual(result.turns_executed, 0)

    def test_production_path_passes_checkpointer_and_thread_id(self) -> None:
        """When checkpointer and thread_id are provided, they are
        propagated to build_research_subgraph so the V3 research phase
        is checkpointable."""

        from code2paper.agentic.checkpointing import build_memory_checkpointer

        import code2paper.agentic.v3_runtime as v3_mod
        from code2paper.agentic.research_graph import CompiledResearchSubgraph

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-ckpt",
            llm_config=_llm_config(),
        )

        original_build = v3_mod.build_research_subgraph
        captured: dict[str, Any] = {}

        def _capturing_build(runtime_arg: Any, **kwargs: Any) -> CompiledResearchSubgraph:
            captured.update(kwargs)
            return original_build(runtime_arg, **kwargs)

        v3_mod.build_research_subgraph = _capturing_build
        real_checkpointer = build_memory_checkpointer()
        try:
            run_v3_research_phase(
                runtime,
                max_turns=3,
                checkpointer=real_checkpointer,
                thread_id="test-v3-thread-id",
            )
        finally:
            v3_mod.build_research_subgraph = original_build

        self.assertIs(captured.get("checkpointer"), real_checkpointer)
        self.assertEqual(captured.get("max_turns"), 3)

    def test_production_path_raises_when_subgraph_produces_no_result(self) -> None:
        """When the subgraph's terminator node does not run (e.g.,
        max_turns=0), run_v3_research_phase raises RuntimeError instead
        of silently returning None."""

        import code2paper.agentic.v3_runtime as v3_mod
        from code2paper.agentic.research_graph import CompiledResearchSubgraph

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-no-result",
            llm_config=_llm_config(),
        )

        class _StubSubgraph(CompiledResearchSubgraph):
            def __init__(self) -> None:
                # Bypass the real __init__ — we only need invoke/last_result.
                pass

            def invoke(self, state: Any, *args: Any, **kwargs: Any) -> Any:
                return {}  # No result stashed in holder.

            @property
            def last_result(self) -> Any:
                return None

        original_build = v3_mod.build_research_subgraph
        v3_mod.build_research_subgraph = lambda *a, **kw: _StubSubgraph()
        try:
            with self.assertRaises(RuntimeError) as ctx:
                run_v3_research_phase(runtime, max_turns=3)
            self.assertIn("did not produce a ResearchLoopResult", str(ctx.exception))
        finally:
            v3_mod.build_research_subgraph = original_build

    def test_node_trace_is_populated_for_multi_node_graph(self) -> None:
        """Phase 2.5: run_v3_research_phase produces a non-empty
        node_trace when the multi-node LangGraph topology executes.

        Each trace entry must have the required keys: node, timestamp,
        duration_ms, turn_index, status, route, error.  The trace
        must include at least linear_prefix (the first node).
        """

        runtime = build_v3_research_runtime(
            project_root=TOY_PROJECT,
            intent_path=TOY_MARKERS,
            run_id="run-v3-trace",
            llm_config=_llm_config(),
        )
        result = run_v3_research_phase(runtime, max_turns=3)
        # node_trace must be a list (possibly empty if the graph didn't
        # execute, but never None).
        self.assertIsInstance(result.node_trace, list)
        # The trace must be non-empty (the graph executed at least
        # linear_prefix).
        self.assertGreater(len(result.node_trace), 0, "node_trace must not be empty")
        # The first entry must be linear_prefix.
        node_names = [entry.get("node", "") for entry in result.node_trace]
        self.assertEqual(node_names[0], "linear_prefix")
        # Every entry must have the required keys.
        required_keys = {"node", "timestamp", "duration_ms", "turn_index", "status", "route", "error"}
        for entry in result.node_trace:
            self.assertTrue(required_keys.issubset(entry.keys()), (
                f"trace entry missing keys: {entry}"
            ))
            self.assertIsInstance(entry["node"], str)
            self.assertIsInstance(entry["timestamp"], str)
            self.assertIsInstance(entry["duration_ms"], (int, float))
            self.assertIsInstance(entry["turn_index"], int)
            self.assertIn(entry["status"], ("ok", "error"))
            self.assertIsInstance(entry["route"], str)
            self.assertIsInstance(entry["error"], str)
        # All entries should have status="ok" (no errors in a normal run).
        error_entries = [e for e in result.node_trace if e["status"] == "error"]
        self.assertEqual(error_entries, [], (
            f"unexpected error trace entries: {error_entries}"
        ))


if __name__ == "__main__":
    unittest.main()
