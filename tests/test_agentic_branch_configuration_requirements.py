"""A branch that reads an unresolved configuration key must not close.

Regression for the first real node-C blocker: `if self.cfg.use_dedicated_attention:`
gates the ablation branch, but the frozen research input never acquired the key's
definition (`conf/config.yaml` defines it).  Operations on the unresolved branch
keep `active_path_status=unknown`, and the frozen completeness gate then reports
`operation_disposition_unresolved`.  Research therefore has to *acquire* the
definition before the obligation can be terminal.
"""

from __future__ import annotations

from types import SimpleNamespace

from code2paper.agentic.research_models import ResearchAgendaItemV1
from code2paper.agentic.research_nodes import (
    branch_configuration_evidence_requirements,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    RecentObservationSummaryV1,
    ResearchDecisionContextV1,
)


def _branches_on(object_value: object) -> SimpleNamespace:
    return SimpleNamespace(predicate="branches_on", object=object_value)


def test_branch_gating_configuration_key_requires_definition_evidence() -> None:
    facts = (
        _branches_on(["self.cfg.use_dedicated_attention"]),
        _branches_on(["self.cfg.add_positional_encoding"]),
        # Not a branch: a plain access must not demand a definition here.
        SimpleNamespace(predicate="loads_weights", object=["self.cfg.other_flag"]),
    )
    unresolved = (
        SimpleNamespace(key="self.cfg.use_dedicated_attention", state="unresolved"),
        SimpleNamespace(key="self.cfg.add_positional_encoding", state="unresolved"),
    )
    assert branch_configuration_evidence_requirements(facts, unresolved) == (
        "configuration:branch_key:add_positional_encoding",
        "configuration:branch_key:use_dedicated_attention",
    )

    # A key with a resolved value is already answered and is not requested.
    resolved = (
        SimpleNamespace(key="self.cfg.use_dedicated_attention", state="default"),
        SimpleNamespace(key="self.cfg.add_positional_encoding", state="unresolved"),
    )
    assert branch_configuration_evidence_requirements(facts, resolved) == (
        "configuration:branch_key:add_positional_encoding",
    )
    # No facts and no claims is an empty requirement set, never a crash.
    assert branch_configuration_evidence_requirements((), ()) == ()


def test_same_leaf_on_another_configuration_object_does_not_close_branch() -> None:
    facts = (_branches_on(["self.cfg.mode"]),)
    unrelated = (
        SimpleNamespace(key="other.cfg.mode", state="default"),
    )
    assert branch_configuration_evidence_requirements(facts, unrelated) == (
        "configuration:branch_key:mode",
    )


OBLIGATION_ID = "O-METHOD-MAINLINE-01"


def _exact_read_observation() -> RecentObservationSummaryV1:
    """The authority boundary requires search -> exact read before config."""

    return RecentObservationSummaryV1(
        observation_id="observation:read",
        tool_call_id="tool-call:read",
        tool_name="read_symbol",
        status="success",
        source_authority="repository_verified",
        exact_span_ids=("span:src/model/ebcar_dedicated_attention_model.py:145:145",),
        obligation_id=OBLIGATION_ID,
    )


def test_pending_requirement_routes_the_supervisor_to_the_exact_key() -> None:
    supervisor = DeterministicSupervisorBackend(
        run_id="run",
        repo_snapshot_id="repo:snapshot",
        ready_tools=("inspect_configuration", "search_symbols", "read_symbol"),
    )
    # The requirement lives on the obligation: that is the list the action
    # selection reads, and where the research node appends it.
    obligation = ResearchAgendaItemV1(
        obligation_id=OBLIGATION_ID,
        candidate_symbol_ids=["sym:model"],
        missing_information=["configuration:branch_key:use_dedicated_attention"],
    )
    context = ResearchDecisionContextV1(
        run_id="run",
        repo_snapshot_id="repo:snapshot",
        turn_index=3,
        active_obligation=obligation,
        missing_information=("configuration:branch_key:use_dedicated_attention",),
        recent_observations=(_exact_read_observation(),),
        ready_tools=supervisor.ready_tools,
    )
    decision = supervisor.decide(context)
    assert decision.action == "INSPECT_CONFIG"
    assert len(decision.selected_tool_calls) == 1
    call = decision.selected_tool_calls[0]
    assert call.tool_name == "inspect_configuration"
    assert call.arguments["config_key"] == "use_dedicated_attention"


def test_without_a_configuration_requirement_the_scan_stays_generic() -> None:
    supervisor = DeterministicSupervisorBackend(
        run_id="run",
        repo_snapshot_id="repo:snapshot",
        ready_tools=("inspect_configuration", "search_symbols", "read_symbol"),
    )
    obligation = ResearchAgendaItemV1(
        obligation_id=OBLIGATION_ID,
        candidate_symbol_ids=["sym:model"],
        missing_information=["typed_relation:configured_by"],
    )
    context = ResearchDecisionContextV1(
        run_id="run",
        repo_snapshot_id="repo:snapshot",
        turn_index=3,
        active_obligation=obligation,
        missing_information=("typed_relation:configured_by",),
        recent_observations=(_exact_read_observation(),),
        ready_tools=supervisor.ready_tools,
    )
    decision = supervisor.decide(context)
    assert decision.action == "INSPECT_CONFIG"
    assert decision.selected_tool_calls[0].arguments["config_key"] == ""


def test_llm_proposal_is_bound_to_the_required_configuration_key() -> None:
    """The required key wins over the model's own choice of key or step."""

    from code2paper.agentic.research_models import (
        ResearchDecisionV1,
        ResearchToolCallV1,
    )
    from code2paper.agentic.research_nodes import (
        bind_pending_configuration_requirement,
    )

    obligation = ResearchAgendaItemV1(
        obligation_id=OBLIGATION_ID,
        missing_information=["configuration:branch_key:use_dedicated_attention"],
    )

    def _proposal(action, tool_name, arguments):
        calls = ()
        if tool_name:
            calls = (
                ResearchToolCallV1(
                    tool_call_id="tool-call:proposed",
                    tool_name=tool_name,
                    tool_kind="configuration" if tool_name == "inspect_configuration" else "code_read",
                    obligation_id=OBLIGATION_ID,
                    goal="goal",
                    repo_snapshot_id="repo:snapshot",
                    arguments=arguments,
                ),
            )
        return ResearchDecisionV1(
            decision_id="decision:1",
            run_id="run",
            turn_index=1,
            action=action,
            obligation_id=OBLIGATION_ID,
            goal="goal",
            selected_tool_calls=calls,
            produced_by="llm_proposal",
        )

    def _bind(proposal):
        return bind_pending_configuration_requirement(
            proposal,
            obligation=obligation,
            ready_tools=("inspect_configuration", "read_symbol"),
            repo_snapshot_id="repo:snapshot",
            run_id="run",
        )

    # 1) The model inspected configuration but guessed the wrong key.
    repaired = _bind(_proposal(
        "INSPECT_CONFIG", "inspect_configuration", {"config_key": "retrieval_model"}
    ))
    assert repaired.selected_tool_calls[0].arguments["config_key"] == (
        "use_dedicated_attention"
    )
    assert "configuration_requirement:use_dedicated_attention" in repaired.rationale
    # The repaired call gets a stable identity, not the rejected one.
    assert repaired.selected_tool_calls[0].tool_call_id != "tool-call:proposed"

    # 2) The model proposed an unrelated step: the requirement still forces the
    # exact configuration read instead of being silently skipped.
    forced = _bind(_proposal("READ_CANDIDATE", "read_symbol", {"path": "src/model.py"}))
    assert forced.action == "INSPECT_CONFIG"
    assert forced.selected_tool_calls[0].tool_name == "inspect_configuration"
    assert forced.selected_tool_calls[0].arguments["config_key"] == (
        "use_dedicated_attention"
    )

    # 3) Already-correct proposal and no-requirement case stay untouched.
    correct = _proposal(
        "INSPECT_CONFIG",
        "inspect_configuration",
        {"config_key": "use_dedicated_attention"},
    )
    assert _bind(correct) is correct
    without = ResearchAgendaItemV1(obligation_id=OBLIGATION_ID)
    unrelated = _proposal("READ_CANDIDATE", "read_symbol", {"path": "src/model.py"})
    assert bind_pending_configuration_requirement(
        unrelated,
        obligation=without,
        ready_tools=("inspect_configuration", "read_symbol"),
        repo_snapshot_id="repo:snapshot",
        run_id="run",
    ) is unrelated
    # A run without the tool ready keeps its original proposal too.
    assert bind_pending_configuration_requirement(
        unrelated,
        obligation=obligation,
        ready_tools=("read_symbol",),
        repo_snapshot_id="repo:snapshot",
        run_id="run",
    ) is unrelated


def test_requirement_is_discharged_only_by_evidence_naming_the_key() -> None:
    """A successful scan for other keys must not discharge the requirement."""

    from code2paper.agentic.research_nodes import _resolved_missing_information
    from code2paper.agentic.research_models import ResearchObservationV1

    requirement = "configuration:branch_key:use_dedicated_attention"

    def _observation(result_refs, status="success"):
        return ResearchObservationV1(
            observation_id="observation:config",
            tool_call_id="tool-call:config",
            tool_name="inspect_configuration",
            status=status,
            source_authority="executable_hard",
            obligation_id=OBLIGATION_ID,
            repo_snapshot_id="repo:snapshot",
            result_refs=result_refs,
        )

    unrelated = _observation(("config:conf/retrieval_model/e5.yaml:12:retrieval_model",))
    assert _resolved_missing_information([requirement], unrelated) == [requirement]

    matching = _observation((
        "config:conf/config.yaml:19:use_dedicated_attention",
    ))
    assert _resolved_missing_information([requirement], matching) == []

    # An empty scan is not evidence either.
    empty = _observation((), status="success_empty")
    assert _resolved_missing_information([requirement], empty) == [requirement]
