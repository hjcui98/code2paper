"""R10 §15.2/§15.6: the loop submits revision proposals; the harness applies them.

These tests cover the *reachable* submission path that the contract tests do
not: the ``propose_target_revision`` tool writes a content-addressed submission
envelope, the research loop ingests it at the tool/harness boundary, and the
applied revision re-binds the loop state (retry counter, compiled evidence,
promotion ledger) and the product-facing journal.

The model never decides acceptance: every test below asserts what the harness
did with a submission, including the submissions it refused.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from code2paper.agentic.research_models import (
    ResearchDecisionV1,
    ResearchToolCallV1,
)
from code2paper.agentic.research_revision_contract import (
    RevisionJournalV1,
    RevisionProposalV1,
    RevisionTargetV1,
    build_author_constraint_set,
    rebind_revision_in_place,
)
from code2paper.agentic.research_revision_ingest import (
    REVISION_PROPOSAL_TOOL_NAME,
    authenticated_observed_ref_ids,
    ingest_revision_submissions,
    iter_revision_submissions,
    persist_revision_proposal,
)
from code2paper.agentic.research_tools import (
    RESEARCH_TOOL_EXECUTORS,
    RESEARCH_TOOL_INPUT_SCHEMAS,
    RESEARCH_TOOL_KINDS,
    ResearchToolContext,
    execute_research_tool,
)
from code2paper.schemas import LLMConfig, LLMProvider


_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"
_INTENT_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures"
    / "research_loop_project_author_markers.yaml"
)


def _runtime(tmp_path: Path, *, run_id: str = "revision-loop"):
    from code2paper.agentic.autonomous_method_agent import (
        build_product_research_runtime,
    )

    return build_product_research_runtime(
        repo_path=_FIXTURE,
        author_intent_path=_INTENT_FIXTURE,
        claims=None,
        run_id=run_id,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        artifact_root=tmp_path / "artifacts" / "research_tool_data",
    )


def _tool_context(runtime: Any) -> ResearchToolContext:
    return runtime.tool_context()


def _proposal(
    runtime: Any,
    *,
    proposal_id: str = "proposal:loop-1",
    target_id: str = "target-inferred-subquestion",
    cited_refs: tuple[str, ...] = (),
    budget_requests: int = 0,
    source_type: str = "system_inferred",
) -> RevisionProposalV1:
    graph = runtime.intent_graph
    obligation_id = str(graph.obligations[0].obligation_id)
    constraints = build_author_constraint_set(graph)
    return RevisionProposalV1(
        proposal_id=proposal_id,
        parent_obligation_id=obligation_id,
        source_type=source_type,  # type: ignore[arg-type]
        subquestion_parent_id=(
            obligation_id if source_type == "research_subquestion" else ""
        ),
        after_targets=(
            RevisionTargetV1(
                target_id=target_id,
                role="subquestion",
                desired_predicates=("COMPUTE",),
                provenance="system_inferred",
            ),
        ),
        observation_refs=cited_refs,
        reason="the inspected span shows an addition worth a sub-question",
        budget_requests=budget_requests,
        author_constraint_digest=constraints.content_digest,
    )


def _read_span(
    runtime: Any,
    ctx: ResearchToolContext,
    tool_call_id: str,
    *,
    obligation_id: str = "",
) -> str:
    """Read one real span and return the ledger-authenticated ref it minted."""

    obligation = obligation_id or str(runtime.intent_graph.obligations[0].obligation_id)
    observation = execute_research_tool(
        ctx,
        ResearchToolCallV1(
            tool_call_id=tool_call_id,
            tool_name="read_code_span",
            tool_kind="code_read",
            obligation_id=obligation,
            goal="read the span a revision will cite",
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            arguments={"path": "compute.py", "start_line": 1, "end_line": 4},
        ),
    )
    assert observation.status == "success", observation.error_message
    assert observation.exact_span_ids
    return observation.exact_span_ids[0]


def _tool_call(
    runtime: Any,
    *,
    tool_call_id: str = "tc-proposal-1",
    obligation_id: str = "",
    arguments: dict[str, Any] | None = None,
) -> ResearchToolCallV1:
    graph = runtime.intent_graph
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=REVISION_PROPOSAL_TOOL_NAME,
        tool_kind="packet_repair",
        obligation_id=(
            obligation_id or str(graph.obligations[0].obligation_id)
        ),
        goal="revise the obligation's typed targets",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        path_scope=(),
        arguments=arguments
        if arguments is not None
        else {
            "parent_obligation_id": str(graph.obligations[0].obligation_id),
            "source_type": "system_inferred",
            "after_targets": [
                {
                    "target_id": "target-inferred-subquestion",
                    "role": "subquestion",
                    "desired_predicates": ["COMPUTE"],
                    "provenance": "system_inferred",
                }
            ],
            "observation_refs": [],
            "reason": "the inspected span shows an addition worth a sub-question",
            "budget_requests": 0,
        },
    )


# ---------------------------------------------------------------------------
# Submission surface
# ---------------------------------------------------------------------------


def test_tool_registries_expose_the_submission_surface() -> None:
    assert REVISION_PROPOSAL_TOOL_NAME in RESEARCH_TOOL_EXECUTORS
    assert REVISION_PROPOSAL_TOOL_NAME in RESEARCH_TOOL_INPUT_SCHEMAS
    # ``packet_repair`` is a budgeted kind: a proposal may not be submitted for
    # free on every turn.
    assert RESEARCH_TOOL_KINDS[REVISION_PROPOSAL_TOOL_NAME] == "packet_repair"


def test_tool_submits_but_never_applies(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    before_digest = runtime.intent_graph.content_digest
    before_agenda = runtime.agenda.content_digest
    ctx = _tool_context(runtime)

    observation = execute_research_tool(ctx, _tool_call(runtime))

    assert observation.status == "success"
    # A proposal is a hypothesis, never evidence.
    assert observation.source_authority == "semantic_hint"
    submissions = iter_revision_submissions(ctx.artifact_root)
    assert len(submissions) == 1
    assert observation.result_refs == (
        f"revision-proposal:{submissions[0].proposal.revision_id}",
    )
    assert submissions[0].proposal.proposal_id == "revision-proposal:tc-proposal-1"
    # Nothing was decided by submitting it.
    assert runtime.intent_graph.content_digest == before_digest
    assert runtime.agenda.content_digest == before_agenda


def test_tool_refuses_author_provenance_and_writes_nothing(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    call = _tool_call(
        runtime,
        arguments={
            "parent_obligation_id": str(runtime.intent_graph.obligations[0].obligation_id),
            "source_type": "author_explicit",
            "after_targets": [
                {"target_id": "target-forged", "provenance": "author_explicit"}
            ],
        },
    )

    observation = execute_research_tool(ctx, call)

    assert observation.status == "invalid_request"
    assert "author_explicit" in (observation.error_message or "")
    assert iter_revision_submissions(ctx.artifact_root) == ()


def test_tool_refuses_a_proposal_for_another_obligation(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    call = _tool_call(runtime, obligation_id="obligation-elsewhere")

    observation = execute_research_tool(_tool_context(runtime), call)

    assert observation.status == "invalid_request"
    assert "active obligation" in (observation.error_message or "")


def test_submission_replay_is_idempotent_and_tampering_is_refused(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    call = _tool_call(runtime)

    first = execute_research_tool(ctx, call)
    replay = execute_research_tool(ctx, call)
    assert first.status == "success" and replay.status == "success"
    assert first.result_refs == replay.result_refs

    path = next(
        (Path(ctx.artifact_root) / "research_tool_artifacts"
         / "target_revision_proposals").glob("*.json")
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["proposal"]["reason"] = "rewritten after the fact"
    path.write_text(json.dumps(payload), encoding="utf-8")

    # A store whose bytes no longer re-derive its own identity is not a
    # proposal: the harness refuses it instead of trusting the file name.
    with pytest.raises(ValueError, match="revision proposal revision_id mismatch"):
        iter_revision_submissions(ctx.artifact_root)


# ---------------------------------------------------------------------------
# Harness ingestion
# ---------------------------------------------------------------------------


def test_ingest_requires_ledger_authenticated_citations(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    proposal = _proposal(runtime, cited_refs=("span:model.py:1:2",))
    persist_revision_proposal(ctx.artifact_root, proposal, tool_call_id="tc-1")

    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
    )

    outcome = result.outcomes[0]
    assert outcome.status == "rejected"
    assert "revision_ref_unobserved:span:model.py:1:2" in outcome.failures
    assert result.applied_count == 0
    assert result.journal.entries == ()


def test_ingest_applies_a_ledger_authenticated_revision(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    before_digest = runtime.intent_graph.content_digest
    # Read a real span first: the execution ledger is what authenticates the
    # citation, not the proposal's own claim about it.
    read_call = ResearchToolCallV1(
        tool_call_id="tc-read-1",
        tool_name="read_code_span",
        tool_kind="code_read",
        obligation_id=str(runtime.intent_graph.obligations[0].obligation_id),
        goal="read the span the revision cites",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        arguments={"path": "compute.py", "start_line": 1, "end_line": 4},
    )
    observation = execute_research_tool(ctx, read_call)
    assert observation.status == "success", observation.error_message
    span_ref = observation.exact_span_ids[0]
    assert span_ref in authenticated_observed_ref_ids(
        ctx, (read_call.obligation_id,)
    )

    proposal = _proposal(runtime, cited_refs=(span_ref,))
    persist_revision_proposal(ctx.artifact_root, proposal, tool_call_id="tc-2")
    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
    )

    assert result.applied_count == 1, result.outcomes
    assert result.journal.has_applied(proposal.revision_id)
    assert runtime.intent_graph.content_digest != before_digest
    target_ids = {
        str(target.target_id)
        for target in runtime.intent_graph.obligations[0].typed_behavior_targets
    }
    assert "target-inferred-subquestion" in target_ids
    # The agenda -> graph link names the revised graph.
    assert runtime.agenda.intent_graph_digest == runtime.intent_graph.content_digest

    # Ingesting again is an explicit no-op, not a second application.
    replay = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        journal=result.journal,
    )
    assert replay.applied_count == 0
    assert replay.outcomes[0].status == "already_applied"
    assert replay.journal == result.journal
    assert runtime.intent_graph.content_digest != before_digest


def test_zero_zero_budget_proposals_cannot_bypass_the_application_limit(
    tmp_path: Path,
) -> None:
    """P2-A: the harness charge is one per application, not the proposal's ask."""

    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-budget-read")
    for index in range(4):
        persist_revision_proposal(
            ctx.artifact_root,
            _proposal(
                runtime,
                proposal_id=f"proposal:zero-{index}",
                target_id=f"target-zero-{index}",
                cited_refs=(span_ref,),
                budget_requests=0,
            ),
            tool_call_id=f"tc-zero-{index}",
        )

    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        remaining_budget=0,
    )

    assert result.applied_count == 0
    assert result.budget_remaining == 0
    assert {outcome.status for outcome in result.outcomes} == {"rejected"}
    assert all(
        outcome.failures and outcome.failures[0].startswith(
            "revision_application_budget_exhausted"
        )
        for outcome in result.outcomes
    )


def test_application_limit_and_research_allowance_are_separate(
    tmp_path: Path,
) -> None:
    """The revision count and the requested research budget are distinct."""

    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-limit-read")
    for index in range(4):
        persist_revision_proposal(
            ctx.artifact_root,
            _proposal(
                runtime,
                proposal_id=f"proposal:limit-{index}",
                target_id=f"target-limit-{index}",
                cited_refs=(span_ref,),
                budget_requests=1,
            ),
            tool_call_id=f"tc-limit-{index}",
        )

    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        behavior_graph=None,
        symbol_index=None,
    )

    statuses = [outcome.status for outcome in result.outcomes]
    assert statuses == ["applied", "applied", "applied", "rejected"]
    rejected = result.outcomes[-1]
    assert rejected.failures[0].startswith("revision_application_budget_exhausted")
    assert result.applied_count == 3
    assert result.budget_remaining == 0
    # Each application costs one charge whatever the proposal requested; the
    # research allowance is charged separately and stays reproducible.
    assert [outcome.application_charge for outcome in result.outcomes[:3]] == [1, 1, 1]
    assert [outcome.budget_spent for outcome in result.outcomes[:3]] == [1, 1, 1]
    assert result.research_allowance_remaining == 3
    assert all(
        entry.application_charge == 1 and entry.requested_budget == 1
        for entry in result.journal.entries
    )

    # A fresh ingest from the same journal cannot refill the count.
    replay = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        journal=result.journal,
    )
    assert replay.budget_remaining == 0
    assert replay.applied_count == 0
    replay_statuses = [outcome.status for outcome in replay.outcomes]
    assert replay_statuses == ["already_applied"] * 3 + ["rejected"]
    assert replay.journal == result.journal


def test_research_allowance_exhaustion_is_reported(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-allowance-read")
    persist_revision_proposal(
        ctx.artifact_root,
        _proposal(
            runtime,
            proposal_id="proposal:expensive",
            target_id="target-expensive",
            cited_refs=(span_ref,),
            budget_requests=5,
        ),
        tool_call_id="tc-expensive",
    )

    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        remaining_research_allowance=2,
    )

    assert result.applied_count == 0
    assert result.outcomes[0].status == "rejected"
    assert result.outcomes[0].failures[0].startswith(
        "revision_research_allowance_exhausted"
    )


def test_rebind_failure_is_typed_and_not_silent() -> None:
    class _FrozenGraph:
        model_config = {"frozen": True}

        def __init__(self) -> None:
            object.__setattr__(self, "content_digest", "before")

        def __setattr__(self, name: str, value: Any) -> None:  # pragma: no cover
            raise TypeError("frozen")

    failures = rebind_revision_in_place(
        runtime_intent_graph=_FrozenGraph(),
        runtime_agenda=None,
        revised_graph=type(
            "Revised", (), {"content_digest": "after", "obligations": []}
        )(),
        revised_agenda=None,
    )

    assert failures and "revision_rebind_failed:intent_graph" in failures[0]


# ---------------------------------------------------------------------------
# Loop integration
# ---------------------------------------------------------------------------


class _ScriptedSupervisor:
    """A supervisor backend that serves a scripted move list.

    Turn/run/obligation identity is taken from the decision context the loop
    passes in, so the script cannot smuggle a stale turn index.  Once the
    script is exhausted the backend proposes the deterministic evidence
    compiler, which keeps the loop terminating on its own rules.
    """

    def __init__(self, moves: list[tuple[str, tuple[ResearchToolCallV1, ...]]]) -> None:
        self._moves = list(moves)
        self.contexts: list[Any] = []

    def decide(self, context: Any) -> ResearchDecisionV1:
        self.contexts.append(context)
        action, tool_calls = (
            self._moves.pop(0) if self._moves else ("COMPILE_EVIDENCE", ())
        )
        return _decision(
            context,
            action=action,
            tool_calls=tool_calls,
        )


def _decision(
    context: Any,
    *,
    action: str,
    tool_calls: tuple[ResearchToolCallV1, ...],
) -> ResearchDecisionV1:
    obligation_id = (
        str(getattr(context.active_obligation, "obligation_id", "") or "")
        or str(getattr(context, "active_obligation_id", "") or "")
    )
    return ResearchDecisionV1(
        decision_id=f"decision-{context.turn_index}-{action}",
        run_id=context.run_id,
        turn_index=context.turn_index,
        action=action,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        goal="revise the obligation targets",
        selected_tool_calls=tool_calls,
        candidate_scope=(),
        expected_information_gain="",
        evidence_needed=(),
        stop_condition="",
        fallback_action="RECORD_GAP",
        rationale="scripted",
        produced_by="llm_proposal",
    )


def test_loop_ingests_a_submitted_proposal_at_the_harness_boundary(
    tmp_path: Path,
) -> None:
    """The loop can submit and the harness applies before the next turn."""

    from code2paper.agentic.research_graph import run_research_loop

    runtime = _runtime(tmp_path, run_id="revision-loop-e2e")
    before_digest = runtime.intent_graph.content_digest
    obligation_id = str(runtime.intent_graph.obligations[0].obligation_id)

    # A real read first: the execution ledger, not the proposal, is what
    # authenticates the citation the proposal makes.
    read_call = ResearchToolCallV1(
        tool_call_id="tc-read-e2e",
        tool_name="read_code_span",
        tool_kind="code_read",
        obligation_id=obligation_id,
        goal="read a span",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        arguments={"path": "compute.py", "start_line": 1, "end_line": 4},
    )
    ctx = _tool_context(runtime)
    read_observation = execute_research_tool(ctx, read_call)
    assert read_observation.status == "success", read_observation.error_message
    span_ref = read_observation.exact_span_ids[0]

    proposal_call = ResearchToolCallV1(
        tool_call_id="tc-proposal-e2e",
        tool_name=REVISION_PROPOSAL_TOOL_NAME,
        tool_kind="packet_repair",
        obligation_id=obligation_id,
        goal="submit a revision",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        arguments={
            "parent_obligation_id": obligation_id,
            "source_type": "research_subquestion",
            "subquestion_parent_id": obligation_id,
            "after_targets": [
                {
                    "target_id": "target-loop-subquestion",
                    "role": "subquestion",
                    "desired_predicates": ["COMPUTE"],
                    "provenance": "research_subquestion",
                }
            ],
            "observation_refs": [span_ref],
            "relation_refs": [],
            "reason": "the span shows an addition",
            "unresolved_impact": ["addition semantics"],
            "budget_requests": 0,
        },
    )
    backend = _ScriptedSupervisor([("PROPOSE_TARGET_REVISION", (proposal_call,))])
    runtime = runtime.model_copy(update={"supervisor_backend": backend})

    result = run_research_loop(runtime, max_turns=4)

    assert result.revision_ingest_failures == []
    assert len(result.revision_journal.entries) == 1
    applied = [
        outcome for outcome in result.revision_ingest_outcomes
        if outcome["status"] == "applied"
    ]
    assert len(applied) == 1, result.revision_ingest_outcomes
    assert applied[0]["applied_target_ids"]
    # The live graph every holder shares now carries the revised target.
    target_ids = {
        str(target.target_id)
        for target in runtime.intent_graph.obligations[0].typed_behavior_targets
    }
    assert "target-loop-subquestion" in target_ids
    assert runtime.intent_graph.content_digest != before_digest
    # The submission executed as a research move: it is in the decision trace
    # and its envelope is on disk.  It is deliberately *not* an evidence
    # execution, so it never widens the search frontier.
    assert any(
        decision.action == "PROPOSE_TARGET_REVISION"
        for decision in result.decision_trace
    )
    assert span_ref in authenticated_observed_ref_ids(ctx, (obligation_id,))
    assert backend.contexts


def test_loop_ingest_rebinds_retry_counter_and_promotion_state(
    tmp_path: Path,
) -> None:
    """§15.6: a revision re-binds what depended on the old targets."""

    from code2paper.agentic.research_graph import (
        _ingest_target_revisions,
        _ResearchGraphContext,
        initial_loop_state,
    )
    from code2paper.agentic.state_v3 import empty_agent_state_v3

    runtime = _runtime(tmp_path, run_id="revision-rebind")
    obligation_id = str(runtime.intent_graph.obligations[0].obligation_id)
    ctx = _tool_context(runtime)
    read_call = ResearchToolCallV1(
        tool_call_id="tc-read-rebind",
        tool_name="read_code_span",
        tool_kind="code_read",
        obligation_id=obligation_id,
        goal="read a span",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        arguments={"path": "compute.py", "start_line": 1, "end_line": 4},
    )
    read_observation = execute_research_tool(ctx, read_call)
    span_ref = read_observation.exact_span_ids[0]
    proposal = _proposal(
        runtime,
        proposal_id="proposal:rebind",
        cited_refs=(span_ref,),
    )
    persist_revision_proposal(ctx.artifact_root, proposal, tool_call_id="tc-rebind")

    loop = initial_loop_state(runtime)
    loop.post_partial_retry_counts[obligation_id] = 1
    loop.compiled_evidence[obligation_id] = type(  # type: ignore[assignment]
        "Compiled", (), {"obligation_id": obligation_id}
    )()
    state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    ).to_state_dict()
    graph_ctx = _ResearchGraphContext(runtime, max_turns=4)
    graph_ctx.loop_state = loop

    _ingest_target_revisions(
        loop,
        runtime,
        state,
        [type("Call", (), {"tool_name": REVISION_PROPOSAL_TOOL_NAME})()],
        budget_remaining=graph_ctx.revision_budget_remaining,
        semantic_verifier=graph_ctx.revision_semantic_verifier,
    )

    assert loop.revision_ingest_failures == []
    assert len(loop.revision_journal.entries) == 1
    # The retry counter was consumed against targets that no longer exist.
    assert obligation_id not in loop.post_partial_retry_counts
    notes = [note for note in loop.revision_rebind_notes]
    assert notes and notes[0]["obligation_id"] == obligation_id
    # The compiled evidence compiled against the removed targets is dropped and
    # the promotion ledger is re-derived from the revised agenda, so a
    # promotion earned under the old targets cannot outlive the revision.
    assert obligation_id not in loop.compiled_evidence
    assert notes[0]["compiled_evidence_dropped"] is True
    assert loop.observation_promotion_ledger is not None
    assert state.get("observation_promotion_ledger_ref") == str(
        getattr(loop.observation_promotion_ledger, "content_digest", "")
    )


def test_checkpoint_carries_the_loop_journal(tmp_path: Path) -> None:
    """The product checkpoint binds the revision the loop applied."""

    from code2paper.agentic.autonomous_method_agent import (
        UserClaimsInputV1,
        persist_research_stage_checkpoint,
    )
    from code2paper.agentic.research_graph import (
        ResearchLoopResult,
        initial_loop_state,
    )
    from code2paper.agentic.state_v3 import empty_agent_state_v3

    runtime = _runtime(tmp_path, run_id="revision-checkpoint")
    obligation_id = str(runtime.intent_graph.obligations[0].obligation_id)
    ctx = _tool_context(runtime)
    read_call = ResearchToolCallV1(
        tool_call_id="tc-read-checkpoint",
        tool_name="read_code_span",
        tool_kind="code_read",
        obligation_id=obligation_id,
        goal="read a span",
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        arguments={"path": "compute.py", "start_line": 1, "end_line": 4},
    )
    span_ref = execute_research_tool(ctx, read_call).exact_span_ids[0]
    proposal = _proposal(runtime, proposal_id="proposal:checkpoint-loop", cited_refs=(span_ref,))
    persist_revision_proposal(ctx.artifact_root, proposal, tool_call_id="tc-ckpt")

    ingest = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
    )
    assert ingest.applied_count == 1
    loop = initial_loop_state(runtime)
    loop.revision_journal = ingest.journal
    loop.revision_ingest_outcomes = [
        outcome.model_dump(mode="json") for outcome in ingest.outcomes
    ]
    result = ResearchLoopResult(
        loop_state=loop,
        final_state=empty_agent_state_v3(
            run_id=runtime.run_id,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        ).to_state_dict(),
        turns_executed=1,
        terminated=True,
        termination_reason="all_obligations_terminal",
        decision_trace=[],
        policy_merge_trace=[],
        evidence_critic_routes=[],
        revision_journal=ingest.journal,
        revision_ingest_outcomes=loop.revision_ingest_outcomes,
    )

    checkpoint = persist_research_stage_checkpoint(
        out_root=tmp_path,
        runtime=runtime,
        claims_input=UserClaimsInputV1(claims=[]),
        loop_result=result,
        packet_set=None,
        fact_set=None,
        claim_set=None,
        revision_journal=ingest.journal,
    )
    payload = json.loads(Path(checkpoint).read_text(encoding="utf-8"))

    assert payload["revision_journal"]["entries"][0]["revision_id"] == (
        proposal.revision_id
    )
    assert payload["revision_ingest_outcomes"][0]["status"] == "applied"
    assert payload["research_revision_binding_v1"] is None


def test_default_journal_stays_empty_without_submissions(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path, run_id="revision-none")
    result = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=_tool_context(runtime).artifact_root,
    )
    assert result.outcomes == ()
    assert result.journal == RevisionJournalV1()


def test_run_revision_state_binds_the_product_handoff(tmp_path: Path) -> None:
    """§15.6: the product handoff and checkpoint name the applied revision."""

    from code2paper.agentic.autonomous_method_agent import _run_revision_state
    from code2paper.agentic.research_graph import (
        _build_candidate_handoff,
        ResearchLoopResult,
        initial_loop_state,
    )
    from code2paper.agentic.state_v3 import empty_agent_state_v3

    runtime = _runtime(tmp_path, run_id="revision-product")
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-product-read")
    proposal = _proposal(
        runtime,
        proposal_id="proposal:product",
        cited_refs=(span_ref,),
    )
    persist_revision_proposal(ctx.artifact_root, proposal, tool_call_id="tc-product")

    ingest = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
    )
    assert ingest.applied_count == 1
    loop = initial_loop_state(runtime)
    loop.revision_journal = ingest.journal
    result = ResearchLoopResult(
        loop_state=loop,
        final_state=empty_agent_state_v3(
            run_id=runtime.run_id,
            repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            project_tree_hash=runtime.repo_snapshot.project_tree_hash,
        ).to_state_dict(),
        turns_executed=2,
        terminated=True,
        termination_reason="all_obligations_terminal",
        decision_trace=[],
        policy_merge_trace=[],
        evidence_critic_routes=[],
        revision_journal=ingest.journal,
    )

    journal, binding = _run_revision_state(result, runtime)

    assert binding is not None
    assert binding.revision_id == proposal.revision_id
    assert binding.intent_graph_digest == runtime.intent_graph.content_digest
    assert binding.target_identity_digest == runtime.intent_graph.target_identity_digest
    assert binding.agenda_digest == runtime.agenda.content_digest
    handoff = _build_candidate_handoff(loop)
    assert handoff.revision_id == journal.current_revision_id()


def test_product_run_without_revisions_writes_no_journal(tmp_path: Path) -> None:
    """A run that never revised keeps the pre-R10 artifact surface."""

    from code2paper.agentic.autonomous_method_agent import (
        run_autonomous_method_agent,
    )

    result = run_autonomous_method_agent(
        repo_path=_FIXTURE,
        author_intent_path=_INTENT_FIXTURE,
        out_root=tmp_path / "out",
        llm_config=LLMConfig(provider=LLMProvider.NONE, model=""),
        max_research_turns=4,
    )

    assert "research_revision_journal_v1" not in result.artifact_paths
    checkpoint = json.loads(
        Path(result.artifact_paths["research_stage_checkpoint_v1"]).read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["research_revision_binding_v1"] is None
    assert checkpoint["revision_journal"] is None
    assert checkpoint["revision_ingest_outcomes"] == []


def test_bound_checkpoint_without_a_journal_refuses_to_resume(
    tmp_path: Path,
) -> None:
    """§15.6: resuming a bound checkpoint without its journal would re-apply."""

    from code2paper.agentic.autonomous_method_agent import (
        run_autonomous_method_agent,
    )

    out_root = tmp_path / "out"
    result = run_autonomous_method_agent(
        repo_path=_FIXTURE,
        author_intent_path=_INTENT_FIXTURE,
        out_root=out_root,
        run_id="revision-bound-resume",
        llm_config=LLMConfig(provider=LLMProvider.NONE, model=""),
        max_research_turns=3,
    )
    payload = json.loads(
        Path(result.artifact_paths["research_stage_checkpoint_v1"]).read_text(
            encoding="utf-8"
        )
    )
    payload["research_revision_binding_v1"] = {
        "schema_version": "1.0",
        "revision_id": "sha256:bound-revision",
        "journal_digest": "",
        "intent_graph_digest": "",
        "target_identity_digest": "",
        "agenda_digest": "",
        "coverage_denominator_ids": [],
    }
    payload["revision_journal"] = None
    doctored = tmp_path / "doctored_checkpoint.json"
    doctored.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="revision_journal_missing"):
        run_autonomous_method_agent(
            repo_path=_FIXTURE,
            author_intent_path=_INTENT_FIXTURE,
            out_root=out_root,
            run_id="revision-bound-resume",
            llm_config=LLMConfig(provider=LLMProvider.NONE, model=""),
            max_research_turns=3,
            research_stage_checkpoint=doctored,
        )


# ---------------------------------------------------------------------------
# Cross-stage invariants (round-4 review)
# ---------------------------------------------------------------------------


def _enriched_author_fixture(tmp_path: Path):
    """Compile author targets, freeze the boundary, then legally enrich."""

    import runpy

    from code2paper.agentic.autonomous_method_agent import (
        build_product_research_runtime,
    )
    from code2paper.agentic.research_revision_contract import (
        build_author_constraint_set,
    )

    proposer = runpy.run_path(
        str(Path(__file__).resolve().parent
            / "test_agentic_intent_target_proposer.py")
    )
    compiled = proposer["_graph"]()
    frozen = build_author_constraint_set(compiled)
    eligible = [
        item for item in compiled.obligations
        if item.priority in {"must_cover", "should_cover"}
    ]
    enriched, report = proposer["_apply_proposal"](
        compiled, eligible, proposer["_proposal"](compiled)
    )
    assert report.accepted
    runtime = build_product_research_runtime(
        repo_path=_FIXTURE,
        author_intent_path=None,
        claims=None,
        run_id="revision-enriched",
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        artifact_root=tmp_path / "artifacts" / "research_tool_data",
        intent_graph_override=enriched,
        author_constraints_override=frozen,
    )
    return compiled, frozen, enriched, runtime


def test_author_boundary_survives_enrichment_and_protects_deletions(
    tmp_path: Path,
) -> None:
    """P1-A: enrichment must not erase the author's protection."""

    from code2paper.agentic.research_revision_contract import (
        build_author_constraint_set,
    )

    compiled, frozen, enriched, runtime = _enriched_author_fixture(tmp_path)

    # Every compiled author target is still protected after enrichment: the
    # enriched targets provably carry the author requirements.
    assert len(frozen.target_ids) == len(compiled.obligations[0].typed_behavior_targets) + len(
        [t for o in compiled.obligations[1:] for t in o.typed_behavior_targets]
    )
    enriched_ids = {
        str(target.target_id)
        for obligation in enriched.obligations
        for target in obligation.typed_behavior_targets
    }
    denied_ids = {
        str(target.target_id)
        for obligation in enriched.obligations
        for target in obligation.typed_behavior_targets
        if str(target.provenance) == "author_derived"
    }
    assert denied_ids, "enrichment must mark the targets that carry author requirements"
    assert denied_ids <= enriched_ids

    # A proposal that deletes the carrying target is refused: the author's
    # predicates/conditions would disappear from the resulting obligation.
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-boundary-read")
    victim = sorted(denied_ids)[0]
    deletion = RevisionProposalV1(
        proposal_id="proposal:delete-author-derived",
        parent_obligation_id=str(runtime.intent_graph.obligations[0].obligation_id),
        source_type="system_inferred",
        before_target_ids=(victim,),
        after_targets=(),
        observation_refs=(span_ref,),
        reason="delete the target that carries the author requirements",
    )
    persist_revision_proposal(
        ctx.artifact_root, deletion, tool_call_id="tc-delete"
    )
    ingest = ingest_revision_submissions(
        runtime=runtime, artifact_root=ctx.artifact_root
    )
    outcome = ingest.outcomes[0]
    assert outcome.status == "rejected"
    assert any(
        failure.startswith("revision_author_constraint_deleted:")
        or failure.startswith("revision_author_target_dropped:")
        or failure.startswith("revision_author_predicate_dropped:")
        for failure in outcome.failures
    ), outcome.failures
    assert ingest.journal.entries == ()
    assert ingest.applied_count == 0
    assert victim in {
        str(target.target_id)
        for target in runtime.intent_graph.obligations[0].typed_behavior_targets
    }

    # A legitimate inferred-layer revision still applies and keeps the author
    # coverage denominator.
    legit = RevisionProposalV1(
        proposal_id="proposal:add-supported",
        parent_obligation_id=str(runtime.intent_graph.obligations[0].obligation_id),
        source_type="system_inferred",
        after_targets=(RevisionTargetV1(
            target_id="target-supported-addition",
            role="subquestion",
            desired_predicates=("COMPUTE",),
        ),),
        observation_refs=(span_ref,),
        reason="the read span computes a scaled score",
    )
    persist_revision_proposal(ctx.artifact_root, legit, tool_call_id="tc-legit")
    second = ingest_revision_submissions(
        runtime=runtime, artifact_root=ctx.artifact_root
    )
    assert second.applied_count == 1, second.outcomes
    denominator = set(second.journal.entries[-1].coverage_denominator_ids)
    assert denied_ids & denominator, "the author denominator must stay conserved"


def test_revision_reaches_the_real_compiler(tmp_path: Path) -> None:
    """P1-B: the compiler must align the *revised* targets, not the old ones."""

    from unittest.mock import patch

    from code2paper.agentic import research_nodes
    from code2paper.agentic.research_graph import initial_loop_state
    from code2paper.agentic.state_v3 import empty_agent_state_v3

    runtime = _runtime(tmp_path, run_id="revision-compiler")
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-compiler-read")
    obligation_id = str(runtime.intent_graph.obligations[0].obligation_id)
    proposal = RevisionProposalV1(
        proposal_id="proposal:compiler",
        parent_obligation_id=obligation_id,
        source_type="system_inferred",
        after_targets=(RevisionTargetV1(
            target_id="target-compiler-addition",
            role="subquestion",
            desired_predicates=("COMPUTE",),
        ),),
        observation_refs=(span_ref,),
        reason="the read span computes a scaled score",
    )
    persist_revision_proposal(
        ctx.artifact_root, proposal, tool_call_id="tc-compiler"
    )
    ingest = ingest_revision_submissions(
        runtime=runtime, artifact_root=ctx.artifact_root
    )
    assert ingest.applied_count == 1, ingest.outcomes

    agenda_item = next(
        item for item in runtime.agenda.items
        if item.obligation_id == obligation_id
    )
    graph_targets = [
        target.model_dump(mode="json")
        for target in runtime.intent_graph.obligations[0].typed_behavior_targets
    ]
    assert [
        target.model_dump(mode="json")
        for target in agenda_item.typed_behavior_targets
    ] == graph_targets

    loop = initial_loop_state(runtime)
    state = empty_agent_state_v3(
        run_id=runtime.run_id,
        repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
        project_tree_hash=runtime.repo_snapshot.project_tree_hash,
    ).to_state_dict()
    state["active_obligation_id"] = obligation_id
    state["status"] = "researching"
    seen: list[str] = []
    real_align = research_nodes.align_target_to_facts

    def _spy(target, facts, **kwargs):
        seen.append(str(getattr(target, "target_id", "") or ""))
        return real_align(target, facts, **kwargs)

    # Drive the real loop so the compile boundary is reached the way the
    # product reaches it; the spy records every target the compiler aligned.
    with patch.object(research_nodes, "align_target_to_facts", _spy):
        from code2paper.agentic.research_graph import ResearchLoopDriver

        result = ResearchLoopDriver(runtime, max_turns=6).run(
            state, loop_state=loop
        )
    assert result.turns_executed >= 1
    assert "target-compiler-addition" in seen, seen


def test_vocabulary_and_relevance_gates_at_the_real_entry(tmp_path: Path) -> None:
    """P2-B: unknown vocabulary and irrelevant citations never apply."""

    runtime = _runtime(tmp_path, run_id="revision-gates")
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-gates-read")
    obligation_id = str(runtime.intent_graph.obligations[0].obligation_id)
    before_graph = runtime.intent_graph.content_digest

    cases = {
        "unknown": RevisionProposalV1(
            proposal_id="proposal:unknown-vocab",
            parent_obligation_id=obligation_id,
            source_type="research_subquestion",
            subquestion_parent_id=obligation_id,
            after_targets=(RevisionTargetV1(
                target_id="target-unknown-vocab",
                desired_predicates=("UNREGISTERED_REVIEW_PREDICATE",),
                provenance="research_subquestion",
            ),),
            observation_refs=(span_ref,),
            reason="invent a predicate",
        ),
        "unread": RevisionProposalV1(
            proposal_id="proposal:unread",
            parent_obligation_id=obligation_id,
            source_type="system_inferred",
            after_targets=(RevisionTargetV1(
                target_id="target-unread",
                desired_predicates=("COMPUTE",),
            ),),
            observation_refs=("span:compute.py:2:2",),
            reason="cite a span the run never read",
        ),
        "unrelated": RevisionProposalV1(
            proposal_id="proposal:unrelated",
            parent_obligation_id=obligation_id,
            source_type="research_subquestion",
            subquestion_parent_id=obligation_id,
            after_targets=(RevisionTargetV1(
                target_id="target-unrelated",
                desired_predicates=("SERIALIZE",),
                provenance="research_subquestion",
            ),),
            observation_refs=(span_ref,),
            reason="claim serialization on a compute span",
        ),
        "wrong_parent": RevisionProposalV1(
            proposal_id="proposal:wrong-parent",
            parent_obligation_id="obligation-does-not-exist",
            source_type="system_inferred",
            after_targets=(RevisionTargetV1(
                target_id="target-wrong-parent",
                desired_predicates=("COMPUTE",),
            ),),
            observation_refs=(span_ref,),
            reason="attach to an unknown parent",
        ),
    }
    for index, (label, proposal) in enumerate(cases.items()):
        persist_revision_proposal(
            ctx.artifact_root, proposal, tool_call_id=f"tc-gate-{index}"
        )

    ingest = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
    )
    by_id = {
        outcome.proposal_id: outcome for outcome in ingest.outcomes
    }
    assert by_id["proposal:unknown-vocab"].status == "rejected"
    assert any(
        failure.startswith("revision_predicate_unregistered:")
        for failure in by_id["proposal:unknown-vocab"].failures
    )
    assert by_id["proposal:unread"].status == "rejected"
    assert any(
        failure.startswith("revision_ref_unobserved:")
        for failure in by_id["proposal:unread"].failures
    )
    assert by_id["proposal:unrelated"].status == "pending_review"
    assert any(
        failure.startswith("revision_predicate_unsupported:")
        for failure in by_id["proposal:unrelated"].failures
    )
    assert by_id["proposal:wrong-parent"].status == "rejected"
    assert any(
        failure.startswith("revision_unknown_parent:")
        for failure in by_id["proposal:wrong-parent"].failures
    )
    # Nothing applied: the runtime, the journal and the author denominator are
    # unchanged.
    assert ingest.applied_count == 0
    assert ingest.journal.entries == ()
    assert runtime.intent_graph.content_digest == before_graph
    assert runtime.author_constraints is not None
    assert runtime.author_constraints.target_ids


def test_revision_count_survives_a_resume_from_the_journal(tmp_path: Path) -> None:
    """A fresh context must not refill the run's revision count."""

    runtime = _runtime(tmp_path, run_id="revision-resume-count")
    ctx = _tool_context(runtime)
    span_ref = _read_span(runtime, ctx, "tc-resume-count-read")
    for index in range(2):
        persist_revision_proposal(
            ctx.artifact_root,
            _proposal(
                runtime,
                proposal_id=f"proposal:resume-{index}",
                target_id=f"target-resume-{index}",
                cited_refs=(span_ref,),
                budget_requests=1,
            ),
            tool_call_id=f"tc-resume-{index}",
        )
    first = ingest_revision_submissions(
        runtime=runtime, artifact_root=ctx.artifact_root
    )
    assert first.applied_count == 2
    assert first.budget_remaining == 1

    # Resume: a brand-new ingest with only the restored journal must not see a
    # refilled count.
    resumed = ingest_revision_submissions(
        runtime=runtime,
        artifact_root=ctx.artifact_root,
        journal=first.journal,
    )
    assert resumed.budget_remaining == 1
    assert resumed.applied_count == 0
    assert resumed.research_allowance_remaining == 4


def test_product_run_applies_a_revision_and_carries_it_to_every_artifact(
    tmp_path: Path,
) -> None:
    """The whole chain: real read → supported proposal → artifacts/resume.

    A supervisor that behaves like a real manager (it cites a span the run
    actually observed, with a predicate the run's own extractor supports) runs
    through the product entry point.  The revision must reach the persisted
    graph, the journal, the checkpoint binding and the Candidate handoff.
    """

    from unittest.mock import patch

    from code2paper.agentic import autonomous_method_agent as agent
    from code2paper.agentic.research_revision_ingest import (
        cited_predicate_support,
    )
    from code2paper.agentic.research_supervisor import (
        DeterministicSupervisorBackend,
    )

    class _ProductChainSupervisor:
        """Reads a span and submits a supported revision in the same move.

        A real manager cites a span it has seen; the harness authenticates the
        citation against the execution ledger at the tool boundary.  The read
        and the proposal therefore travel in one decision, in that order, for
        the same obligation.
        """

        def __init__(self, runtime: Any) -> None:
            self._runtime = runtime
            self._delegate = DeterministicSupervisorBackend(
                run_id=runtime.run_id,
                repo_snapshot_id=runtime.repo_snapshot.snapshot_id,
            )
            self._submitted = False
            self.cited_refs: list[str] = []

        @property
        def deterministic_fallback(self) -> Any:
            return self._delegate

        def _fixture_span_and_predicate(self) -> tuple[str, str]:
            ctx = self._runtime.tool_context()
            adapter = ctx.language_adapter()
            text = (_FIXTURE / "compute.py").read_text(encoding="utf-8")
            index = adapter.index_symbols(
                repo_snapshot_id=self._runtime.repo_snapshot.snapshot_id,
                project_tree_hash=self._runtime.repo_snapshot.project_tree_hash,
                files={"compute.py": text},
            )
            span = ""
            for symbol in index.symbols:
                if str(getattr(symbol, "qualified_name", "")) == "run_training":
                    span = (
                        f"span:compute.py:{int(symbol.start_line)}:"
                        f"{int(symbol.end_line)}"
                    )
                    break
            assert span
            support = cited_predicate_support(ctx, [span]).get(span, ())
            assert support, "the extractor must support the fixture span"
            return span, support[0]

        def decide(self, context: Any) -> ResearchDecisionV1:
            if not self._submitted:
                obligation = context.active_obligation
                if obligation is not None:
                    span, predicate = self._fixture_span_and_predicate()
                    self._submitted = True
                    self.cited_refs.append(span)
                    obligation_id = str(obligation.obligation_id)
                    return _decision(
                        context,
                        action="PROPOSE_TARGET_REVISION",
                        tool_calls=(
                            ResearchToolCallV1(
                                tool_call_id=(
                                    f"tc-product-read-{context.turn_index}"
                                ),
                                tool_name="read_symbol",
                                tool_kind="code_read",
                                obligation_id=obligation_id,
                                goal="read the fixture symbol before revising",
                                repo_snapshot_id=(
                                    self._runtime.repo_snapshot.snapshot_id
                                ),
                                arguments={
                                    "path": "compute.py",
                                    "symbol": "run_training",
                                },
                            ),
                            ResearchToolCallV1(
                                tool_call_id=(
                                    f"tc-product-chain-{context.turn_index}"
                                ),
                                tool_name=REVISION_PROPOSAL_TOOL_NAME,
                                tool_kind="packet_repair",
                                obligation_id=obligation_id,
                                goal="submit a supported target revision",
                                repo_snapshot_id=(
                                    self._runtime.repo_snapshot.snapshot_id
                                ),
                                arguments={
                                    "parent_obligation_id": obligation_id,
                                    "source_type": "system_inferred",
                                    "after_targets": [{
                                        "target_id": "target-product-chain",
                                        "role": "subquestion",
                                        "desired_predicates": [predicate],
                                        "provenance": "system_inferred",
                                    }],
                                    "observation_refs": [span],
                                    "reason": (
                                        "the observed span shows this operation"
                                    ),
                                    "unresolved_impact": ["operation disposition"],
                                    "budget_requests": 0,
                                },
                            ),
                        ),
                    )
            return self._delegate.decide(context)

    out_root = tmp_path / "out"
    original = agent.build_product_research_runtime
    supervisors: list[_ProductChainSupervisor] = []

    def _builder(**kwargs: Any) -> Any:
        runtime = original(**kwargs)
        supervisor = _ProductChainSupervisor(runtime)
        supervisors.append(supervisor)
        return runtime.model_copy(update={"supervisor_backend": supervisor})

    with patch.object(agent, "build_product_research_runtime", _builder):
        result = agent.run_autonomous_method_agent(
            repo_path=_FIXTURE,
            author_intent_path=_INTENT_FIXTURE,
            out_root=out_root,
            run_id="revision-product-chain",
            llm_config=LLMConfig(provider=LLMProvider.NONE, model=""),
            max_research_turns=8,
        )

    assert supervisors and supervisors[0].cited_refs
    checkpoint_payload = json.loads(
        Path(result.artifact_paths["research_stage_checkpoint_v1"]).read_text(
            encoding="utf-8"
        )
    )
    trace_actions = [
        (item["action"], item["produced_by"], item["obligation_id"])
        for item in json.loads(
            Path(result.artifact_paths["research_trace"]).read_text(
                encoding="utf-8"
            )
        )["decision_trace"]
    ]
    assert checkpoint_payload["revision_ingest_outcomes"], (
        trace_actions,
        supervisors[0].cited_refs,
    )
    journal_path = result.artifact_paths.get("research_revision_journal_v1")
    assert journal_path, (
        trace_actions,
        [
            (outcome["status"], list(outcome["failures"])[:4])
            for outcome in checkpoint_payload["revision_ingest_outcomes"]
        ],
    )
    journal = RevisionJournalV1.model_validate_json(
        Path(journal_path).read_text(encoding="utf-8")
    )
    assert len(journal.entries) == 1
    entry = journal.entries[0]
    assert "target-product-chain" in entry.applied_target_ids
    assert entry.coverage_denominator_ids

    # The persisted graph is the revised one.
    graph = json.loads(
        Path(result.artifact_paths["intent_obligation_graph_v2"]).read_text(
            encoding="utf-8"
        )
    )
    target_ids = {
        str(target["target_id"])
        for obligation in graph["obligations"]
        for target in obligation["typed_behavior_targets"]
    }
    assert "target-product-chain" in target_ids

    # The checkpoint binds the same revision, and the handoff names it.
    payload = json.loads(
        Path(result.artifact_paths["research_stage_checkpoint_v1"]).read_text(
            encoding="utf-8"
        )
    )
    binding = payload["research_revision_binding_v1"]
    assert binding is not None
    assert binding["revision_id"] == journal.current_revision_id()
    assert payload["revision_ingest_outcomes"][0]["status"] == "applied"
    handoff = json.loads(
        Path(result.artifact_paths["candidate_handoff_v1"]).read_text(
            encoding="utf-8"
        )
    )
    assert handoff["revision_id"] == journal.current_revision_id()
