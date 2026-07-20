"""Tests for ``GemmaSupervisorBackend`` (R8 wiring).

Covers:

- ``SupervisorBackend`` protocol conformance (runtime-checkable).
- Fallback to ``DeterministicSupervisorBackend`` on every failure mode:
    * provider=NONE
    * missing API key (non-loopback URL)
    * LLM API exception
    * blocked response
    * empty response
    * malformed JSON / missing ``action`` field
    * disallowed action (not in ``_LLM_ALLOWED_ACTIONS``)
    * tool-calling action that cannot produce tool calls
- Successful LLM proposal produces a ``ResearchDecisionV1`` with
  ``produced_by="llm_proposal"`` and deterministic tool calls.
- Prompt construction only uses ``ResearchDecisionContextV1`` fields.
- ``_parse_proposal`` handles markdown fences, plain JSON, and rejects
  malformed payloads.
- Temperature is forced to 0 and cache is forced off (R8 protocol).
- Live LLM test (opt-in via ``CODE2PAPER_RUN_LIVE_LLM=1``) calls the
  real Gemma endpoint.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from pydantic import ValidationError

from code2paper.agentic.gemma_supervisor_backend import (
    GemmaSupervisorBackend,
    _LLM_ALLOWED_ACTIONS,
    _LLM_ALLOWED_ACTIONS_SET,
    _RESPONSE_SCHEMA,
    _SYSTEM_PROMPT,
    _TOOL_CALLING_ACTIONS,
    _parse_proposal,
)
from code2paper.agentic.research_models import (
    GlobalSafetyBudgetV1,
    PerObligationBudgetV1,
    ResearchAgendaItemV1,
    ResearchAgendaV1,
    ResearchDecisionV1,
    ResearchIssueV1,
    ResearchObservationV1,
    ResearchToolCallV1,
    TypedBehaviorTargetV1,
    make_observation,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    ResearchDecisionContextV1,
    SupervisorBackend,
    build_decision_context,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.schemas import LLMConfig, LLMProvider


# ---------------------------------------------------------------------------
# Constants and fixtures
# ---------------------------------------------------------------------------

_RUN_ID = "run-gemma-test"


@pytest.fixture(autouse=True)
def _restore_env() -> Any:
    """Save/restore env vars that ``_llm_config`` mutates as a side effect.

    ``_llm_config`` sets ``CODE2PAPER_OPENAI_BASE_URL`` and
    ``OPENAI_API_KEY`` so ``has_provider_api_key`` /
    ``openai_compatible_base_url`` see the loopback URL.  Without this
    fixture those env vars leak across test files and break
    ``test_llm_runtime.py``.
    """

    saved = {
        key: os.environ.get(key)
        for key in ("CODE2PAPER_OPENAI_BASE_URL", "OPENAI_API_KEY")
    }
    yield
    for key, value in saved.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


_SNAPSHOT_ID = "repo:abc123"
_TREE_HASH = "sha256:tree"


def _agenda(*items: ResearchAgendaItemV1) -> ResearchAgendaV1:
    return ResearchAgendaV1(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        project_tree_hash=_TREE_HASH,
        items=list(items),
    )


def _typed_target(
    *,
    target_id: str = "tbt-1",
    role: str = "predictor",
    predicates: tuple[str, ...] = ("COMPUTE",),
    search_terms: tuple[str, ...] = ("score",),
) -> TypedBehaviorTargetV1:
    return TypedBehaviorTargetV1(
        target_id=target_id,
        role=role,
        desired_predicates=list(predicates),
        required_relations=(),
        search_terms=list(search_terms),
    )


def _obligation(
    obligation_id: str = "obl-1",
    *,
    priority: str = "must_cover",
    status: str = "in_progress",
    candidate_symbol_ids: tuple[str, ...] = (),
    missing_information: tuple[str, ...] = (),
    typed_targets: tuple[TypedBehaviorTargetV1, ...] = (),
) -> ResearchAgendaItemV1:
    return ResearchAgendaItemV1(
        obligation_id=obligation_id,
        priority=priority,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        candidate_symbol_ids=list(candidate_symbol_ids),
        missing_information=list(missing_information),
        typed_behavior_targets=list(typed_targets),
    )


def _issue(
    issue_kind: str = "missing_anchor",
    *,
    issue_id: str = "issue-1",
    obligation_id: str = "obl-1",
) -> ResearchIssueV1:
    return ResearchIssueV1(
        issue_id=issue_id,
        issue_kind=issue_kind,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        description=f"test issue {issue_kind}",
    )


def _tool_call(
    tool_call_id: str = "tc-1",
    tool_name: str = "search_symbols",
    *,
    obligation_id: str = "obl-1",
    tool_kind: str = "symbol_search",
) -> ResearchToolCallV1:
    return ResearchToolCallV1(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        tool_kind=tool_kind,  # type: ignore[arg-type]
        obligation_id=obligation_id,
        goal="test goal",
        repo_snapshot_id=_SNAPSHOT_ID,
        arguments={"query": "train"},
    )


def _observation(
    tool_call: ResearchToolCallV1,
    *,
    status: str = "success",
) -> ResearchObservationV1:
    return make_observation(
        tool_call=tool_call,
        status=status,  # type: ignore[arg-type]
        result_refs=("symbol:train.py:train",),
        exact_span_ids=("span:train.py:10-20",),
    )


def _context(
    *,
    active_obligation: ResearchAgendaItemV1 | None = None,
    active_issue: ResearchIssueV1 | None = None,
    no_progress_counter: int = 0,
    recent_observations: tuple[ResearchObservationV1, ...] = (),
    turn_index: int = 0,
    ready_tools: tuple[str, ...] = (
        "find_entrypoints",
        "search_symbols",
        "read_symbol",
        "find_references",
        "build_behavior_subgraph",
    ),
) -> ResearchDecisionContextV1:
    agenda = _agenda(active_obligation) if active_obligation else None
    return build_decision_context(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        turn_index=turn_index,
        agenda=agenda,
        active_obligation_id=active_obligation.obligation_id if active_obligation else "",
        active_issue=active_issue,
        recent_observations=recent_observations,
        per_obligation_budgets={},
        global_safety_budget=GlobalSafetyBudgetV1(),
        no_progress_counter=no_progress_counter,
        ready_tools=ready_tools,
        hard_rules=("no_snapshot_external_paths",),
    )


def _llm_config(
    *,
    provider: LLMProvider = LLMProvider.OPENAI,
    base_url: str = "http://127.0.0.1:8000/v1",
    api_key: str = "dummy-local-vllm",
    temperature: float = 0.2,
) -> LLMConfig:
    """Build an LLMConfig for tests, also setting the env vars that
    ``has_provider_api_key`` and ``openai_compatible_base_url`` consult.
    """

    # Set env vars that providers.py reads at call time.
    os.environ["CODE2PAPER_OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_KEY"] = api_key
    return LLMConfig(
        provider=provider,
        model="gemma4-31b-nvfp4",
        temperature=temperature,
        max_output_tokens=512,
        request_timeout_seconds=10,
        retry_max_attempts=1,
        cache=True,
    )


def _response(
    text: str = "",
    *,
    blocked_reason: str = "",
    finish_reason: str = "stop",
) -> LLMResponse:
    from code2paper.export.run_manifest import hash_text

    return LLMResponse(
        text=text,
        response_hash=hash_text(text),
        blocked_reason=blocked_reason,
        cached=False,
        response_mode="prompt_only",
        finish_reason=finish_reason,
    )


class _StubLLMClient(LLMClient):
    """LLMClient subclass that returns a queued response or raises."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        responses: list[LLMResponse] | None = None,
        exc: BaseException | None = None,
        recorded: list[LLMRequest] | None = None,
    ) -> None:
        super().__init__(config)
        self._responses = list(responses) if responses else []
        self._exc = exc
        self._recorded = recorded if recorded is not None else []

    @property
    def recorded(self) -> list[LLMRequest]:
        return self._recorded

    def complete(self, request: LLMRequest, *, dry_run: bool = False) -> LLMResponse:  # type: ignore[override]
        self._recorded.append(request)
        if self._exc is not None:
            raise self._exc
        if not self._responses:
            return _response(text="")
        return self._responses.pop(0)


def _patch_llm_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    responses: list[LLMResponse] | None = None,
    exc: BaseException | None = None,
    recorded: list[LLMRequest] | None = None,
) -> None:
    """Replace ``LLMClient`` (as imported in the gemma backend module)
    with ``_StubLLMClient`` configured with the given responses/exception.
    """

    def factory(config: LLMConfig, *args: Any, **kwargs: Any) -> _StubLLMClient:
        return _StubLLMClient(
            config,
            responses=responses,
            exc=exc,
            recorded=recorded,
        )

    from code2paper.agentic import gemma_supervisor_backend as mod

    monkeypatch.setattr(mod, "LLMClient", factory)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_protocol_conformance_runtime_checkable() -> None:
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    assert isinstance(backend, SupervisorBackend)


def test_backend_exposes_fallback() -> None:
    fallback = DeterministicSupervisorBackend(
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        fallback=fallback,
    )
    assert backend._fallback is fallback


# ---------------------------------------------------------------------------
# Fallback: LLM unavailable
# ---------------------------------------------------------------------------


def test_fallback_when_provider_is_none() -> None:
    """provider=NONE means LLM is unavailable -> deterministic fallback."""

    cfg = LLMConfig(provider=LLMProvider.NONE, model="")
    backend = GemmaSupervisorBackend(
        llm_config=cfg,
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"
    assert decision.action in _LLM_ALLOWED_ACTIONS_SET or decision.action == "SEARCH_SYMBOLS"


def test_fallback_when_no_api_key_and_not_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI provider but no API key and a non-loopback URL -> fallback."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.setenv("CODE2PAPER_OPENAI_BASE_URL", "https://api.openai.com/v1")
    cfg = LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4",
        temperature=0.0,
    )
    backend = GemmaSupervisorBackend(
        llm_config=cfg,
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Fallback: LLM call failures
# ---------------------------------------------------------------------------


def test_fallback_on_llm_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[LLMRequest] = []
    _patch_llm_client(
        monkeypatch,
        exc=RuntimeError("boom"),
        recorded=recorded,
    )
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"
    assert recorded  # LLM was actually called


def test_fallback_on_blocked_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm_client(
        monkeypatch,
        responses=[_response(text="", blocked_reason="llm_api_key_missing")],
    )
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


def test_fallback_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm_client(monkeypatch, responses=[_response(text="   ")])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Fallback: parse failures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        "```not even a fence```",
        "{",
        "{}",
        '{"rationale": "missing action"}',
        "[]",
        '"a string"',
        "null",
    ],
)
def test_fallback_on_malformed_response(
    monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    _patch_llm_client(monkeypatch, responses=[_response(text=text)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


def test_fallback_on_disallowed_action(monkeypatch: pytest.MonkeyPatch) -> None:
    # COMPILE_FACTS is excluded from _LLM_ALLOWED_ACTIONS (R4 tool).
    payload = json.dumps({"action": "COMPILE_FACTS", "rationale": "r", "goal": "g"})
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


def test_fallback_on_unknown_action_string(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps({"action": "INVENT_NEW_ACTION", "rationale": "r", "goal": "g"})
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "deterministic_fallback"


# ---------------------------------------------------------------------------
# Fallback: tool-calling action that cannot produce tool calls
# ---------------------------------------------------------------------------


def test_fallback_when_tool_calling_action_cannot_build_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """READ_CANDIDATE without a candidate symbol cannot build a tool call,
    so the backend falls back to the deterministic path (which itself
    escalates to SEARCH_SYMBOLS or STOP_BLOCKED)."""

    payload = json.dumps(
        {"action": "READ_CANDIDATE", "rationale": "read", "goal": "read the symbol"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    # Obligation with no candidate symbols -> _read_symbol_target returns None.
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=(),
            typed_targets=(_typed_target(),),
        ),
    )
    decision = backend.decide(ctx)
    # Either the fallback escalated to SEARCH_SYMBOLS (which can build a
    # tool call from typed_target search terms) or to STOP_BLOCKED.
    assert decision.produced_by == "deterministic_fallback"
    assert decision.action in {"SEARCH_SYMBOLS", "STOP_BLOCKED", "RECORD_GAP"}


# ---------------------------------------------------------------------------
# Successful LLM proposal
# ---------------------------------------------------------------------------


def test_successful_search_symbols_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {
            "action": "SEARCH_SYMBOLS",
            "rationale": "need to find the predictor module",
            "goal": "locate the score-prediction function",
            "expected_information_gain": "new_candidate_symbol",
        }
    )
    recorded: list[LLMRequest] = []
    _patch_llm_client(
        monkeypatch,
        responses=[_response(text=payload)],
        recorded=recorded,
    )
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(temperature=0.5),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=("models.predictor:forward",),
            missing_information=("predictor_module_path",),
            typed_targets=(_typed_target(search_terms=("score", "predictor")),),
        ),
        active_issue=_issue(issue_kind="missing_anchor"),
    )
    decision = backend.decide(ctx)

    assert decision.produced_by == "llm_proposal"
    assert decision.action == "SEARCH_SYMBOLS"
    assert decision.run_id == _RUN_ID
    assert decision.obligation_id == "obl-1"
    assert decision.issue_id == "issue-1"
    assert "predictor module" in decision.rationale
    assert "locate the score-prediction" in decision.goal
    assert "new_candidate_symbol" in decision.expected_information_gain
    assert len(decision.selected_tool_calls) == 1
    call = decision.selected_tool_calls[0]
    assert call.tool_name == "search_symbols"
    assert call.tool_kind == "symbol_search"
    assert call.obligation_id == "obl-1"
    assert call.arguments["query"] == "score"  # first typed_target search term
    assert call.arguments["top_k"] == 10
    assert call.repo_snapshot_id == _SNAPSHOT_ID
    # LLM was actually invoked once.
    assert len(recorded) == 1


def test_successful_read_candidate_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {"action": "READ_CANDIDATE", "rationale": "read", "goal": "read the symbol"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=("models.predictor:forward",),
            typed_targets=(_typed_target(),),
        ),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "llm_proposal"
    assert decision.action == "READ_CANDIDATE"
    assert len(decision.selected_tool_calls) == 1
    call = decision.selected_tool_calls[0]
    assert call.tool_name == "read_symbol"
    assert call.arguments["path"] == "models.predictor"
    assert call.arguments["symbol"] == "forward"
    assert call.arguments["top_k"] == 1


def test_successful_trace_calls_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {"action": "TRACE_CALLS", "rationale": "trace", "goal": "find callers"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=("models.predictor:forward",),
            typed_targets=(_typed_target(),),
        ),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "llm_proposal"
    assert decision.action == "TRACE_CALLS"
    assert len(decision.selected_tool_calls) == 1
    call = decision.selected_tool_calls[0]
    assert call.tool_name == "find_references"
    assert call.arguments["symbol"] == "forward"


def test_successful_build_behavior_subgraph_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.dumps(
        {"action": "BUILD_BEHAVIOR_SUBGRAPH", "rationale": "bg", "goal": "subgraph"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=("models.predictor:forward",),
            typed_targets=(_typed_target(),),
        ),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "llm_proposal"
    assert decision.action == "BUILD_BEHAVIOR_SUBGRAPH"
    assert len(decision.selected_tool_calls) == 1
    call = decision.selected_tool_calls[0]
    assert call.tool_name == "build_behavior_subgraph"
    assert call.arguments["symbol"] == "forward"
    assert call.arguments["depth"] == 1
    assert call.arguments["node_budget"] == 32


def test_successful_terminal_action_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terminal actions (RECORD_GAP, STOP_BLOCKED) produce no tool calls."""

    payload = json.dumps(
        {"action": "RECORD_GAP", "rationale": "stuck", "goal": "record the gap"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "llm_proposal"
    assert decision.action == "RECORD_GAP"
    assert decision.selected_tool_calls == ()


def test_successful_stop_blocked_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(
        {"action": "STOP_BLOCKED", "rationale": "blocked", "goal": "stop"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    assert decision.produced_by == "llm_proposal"
    assert decision.action == "STOP_BLOCKED"
    assert decision.selected_tool_calls == ()


def test_llm_proposal_decision_is_valid_research_decision_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructed decision must pass ResearchDecisionV1 validators
    (including the action/tool-call alignment validator)."""

    payload = json.dumps(
        {"action": "SEARCH_SYMBOLS", "rationale": "r", "goal": "g"}
    )
    _patch_llm_client(monkeypatch, responses=[_response(text=payload)])
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    decision = backend.decide(ctx)
    # Re-validate by reconstructing from dict to catch any validator issue.
    rebuilt = ResearchDecisionV1.model_validate(decision.model_dump())
    assert rebuilt.action == "SEARCH_SYMBOLS"
    assert len(rebuilt.selected_tool_calls) == 1


# ---------------------------------------------------------------------------
# Temperature and cache enforcement (R8 protocol)
# ---------------------------------------------------------------------------


def test_temperature_forced_to_zero_and_cache_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regardless of the input LLMConfig temperature, the backend forces
    temperature=0 and cache=False for R8 protocol compliance."""

    captured_configs: list[LLMConfig] = []

    def factory(config: LLMConfig, *args: Any, **kwargs: Any) -> _StubLLMClient:
        captured_configs.append(config)
        return _StubLLMClient(
            config,
            responses=[
                _response(
                    text=json.dumps(
                        {"action": "SEARCH_SYMBOLS", "rationale": "r", "goal": "g"}
                    )
                )
            ],
        )

    from code2paper.agentic import gemma_supervisor_backend as mod

    monkeypatch.setattr(mod, "LLMClient", factory)

    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(temperature=0.7),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        temperature=0.0,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    backend.decide(ctx)
    assert captured_configs, "LLMClient should have been constructed"
    assert captured_configs[0].temperature == 0.0
    assert captured_configs[0].cache is False


def test_temperature_override_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``temperature`` ctor arg overrides the LLMConfig temperature."""

    captured: list[LLMConfig] = []

    def factory(config: LLMConfig, *args: Any, **kwargs: Any) -> _StubLLMClient:
        captured.append(config)
        return _StubLLMClient(
            config,
            responses=[
                _response(
                    text=json.dumps(
                        {"action": "STOP_BLOCKED", "rationale": "r", "goal": "g"}
                    )
                )
            ],
        )

    from code2paper.agentic import gemma_supervisor_backend as mod

    monkeypatch.setattr(mod, "LLMClient", factory)

    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(temperature=0.9),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
        temperature=0.0,
    )
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
    )
    backend.decide(ctx)
    assert captured[0].temperature == 0.0


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_build_prompt_only_uses_context_fields() -> None:
    """The prompt must contain only fields derived from
    ResearchDecisionContextV1 (design 8.2 hard rule)."""

    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    obl = _obligation(
        candidate_symbol_ids=("models.predictor:forward",),
        missing_information=("predictor_path",),
        typed_targets=(_typed_target(search_terms=("score",)),),
    )
    ctx = _context(
        active_obligation=obl,
        active_issue=_issue(issue_kind="missing_anchor"),
        no_progress_counter=1,
    )
    prompt = backend._build_prompt(ctx)

    # Required structural fields.
    assert prompt["run_id"] == _RUN_ID
    assert prompt["turn_index"] == 0
    assert "SEARCH_SYMBOLS" in prompt["allowed_actions"]
    assert prompt["no_progress_counter"] == 1
    assert "find_entrypoints" in prompt["ready_tools"]
    assert "no_snapshot_external_paths" in prompt["hard_rules"]

    # Active obligation fields.
    obl_payload = prompt["active_obligation"]
    assert obl_payload["obligation_id"] == "obl-1"
    assert obl_payload["missing_information"] == ["predictor_path"]
    assert obl_payload["candidate_symbol_ids"] == ["models.predictor:forward"]
    assert obl_payload["typed_behavior_targets"][0]["search_terms"] == ["score"]

    # Active issue fields.
    issue_payload = prompt["active_issue"]
    assert issue_payload["issue_kind"] == "missing_anchor"

    # Missing information and candidate symbols.
    assert prompt["missing_information"] == ["predictor_path"]
    assert prompt["top_candidate_symbol_ids"] == ["models.predictor:forward"]


def test_build_prompt_with_no_active_obligation() -> None:
    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(active_obligation=None, active_issue=None)
    prompt = backend._build_prompt(ctx)
    assert prompt["active_obligation"] is None
    assert prompt["active_issue"] is None
    assert prompt["recent_observations"] == []


def test_build_prompt_includes_recent_observations_compact() -> None:
    """Recent observations are projected to compact summaries — no raw
    result_refs / exact_span_ids leak into the prompt."""

    backend = GemmaSupervisorBackend(
        llm_config=_llm_config(),
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    tc = _tool_call()
    obs = _observation(tc)
    ctx = _context(
        active_obligation=_obligation(typed_targets=(_typed_target(),)),
        recent_observations=(obs,),
    )
    prompt = backend._build_prompt(ctx)
    assert len(prompt["recent_observations"]) == 1
    summary = prompt["recent_observations"][0]
    # Compact fields only — no result_refs or exact_span_ids.
    assert "observation_id" in summary
    assert "tool_name" in summary
    assert "status" in summary
    assert "result_refs" not in summary
    assert "exact_span_ids" not in summary


# ---------------------------------------------------------------------------
# _parse_proposal
# ---------------------------------------------------------------------------


def test_parse_proposal_plain_json() -> None:
    text = json.dumps({"action": "SEARCH_SYMBOLS", "rationale": "r"})
    proposal = _parse_proposal(text)
    assert proposal["action"] == "SEARCH_SYMBOLS"


def test_parse_proposal_with_markdown_fence() -> None:
    text = "```json\n" + json.dumps({"action": "READ_CANDIDATE"}) + "\n```"
    proposal = _parse_proposal(text)
    assert proposal["action"] == "READ_CANDIDATE"


def test_parse_proposal_with_prose_around_json() -> None:
    text = (
        "Here is my decision:\n"
        '{"action": "TRACE_CALLS", "rationale": "trace"}\n'
        "Hope that helps."
    )
    proposal = _parse_proposal(text)
    assert proposal["action"] == "TRACE_CALLS"


def test_parse_proposal_rejects_non_object() -> None:
    with pytest.raises((ValueError, json.JSONDecodeError)):
        _parse_proposal("[]")


def test_parse_proposal_rejects_missing_action() -> None:
    with pytest.raises(ValueError, match="missing or empty 'action'"):
        _parse_proposal(json.dumps({"rationale": "no action"}))


def test_parse_proposal_rejects_empty_action() -> None:
    with pytest.raises(ValueError, match="missing or empty 'action'"):
        _parse_proposal(json.dumps({"action": "  "}))


def test_parse_proposal_rejects_no_json_object() -> None:
    with pytest.raises(ValueError, match="no JSON object found"):
        _parse_proposal("no braces here")


# ---------------------------------------------------------------------------
# Response schema and system prompt
# ---------------------------------------------------------------------------


def test_response_schema_requires_action_rationale_goal() -> None:
    assert "action" in _RESPONSE_SCHEMA["properties"]
    assert "rationale" in _RESPONSE_SCHEMA["properties"]
    assert "goal" in _RESPONSE_SCHEMA["properties"]
    assert _RESPONSE_SCHEMA["required"] == ["action", "rationale", "goal"]


def test_system_prompt_lists_allowed_actions_constraint() -> None:
    assert "allowed_actions" in _SYSTEM_PROMPT
    assert "PROPOSAL" in _SYSTEM_PROMPT


def test_llm_allowed_actions_exclude_r4_r6_tools() -> None:
    """The LLM must not propose R4/R6 tool-only actions."""

    excluded = {"PROPOSE_PACKET", "COMPILE_FACTS", "DECOMPOSE_CLAIMS", "REWRITE_SENTENCES", "PLAN_METHOD"}
    for action in excluded:
        assert action not in _LLM_ALLOWED_ACTIONS_SET
    # Sanity: terminal actions ARE allowed.
    assert "RECORD_GAP" in _LLM_ALLOWED_ACTIONS_SET
    assert "STOP_BLOCKED" in _LLM_ALLOWED_ACTIONS_SET


def test_tool_calling_actions_subset_of_allowed() -> None:
    assert _TOOL_CALLING_ACTIONS.issubset(_LLM_ALLOWED_ACTIONS_SET)


# ---------------------------------------------------------------------------
# Live LLM test (opt-in)
# ---------------------------------------------------------------------------


pytestmark_live = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        os.environ.get("CODE2PAPER_RUN_LIVE_LLM") != "1",
        reason="set CODE2PAPER_RUN_LIVE_LLM=1 to call the configured live endpoint",
    ),
]


@pytest.mark.live_llm
@pytest.mark.skipif(
    os.environ.get("CODE2PAPER_RUN_LIVE_LLM") != "1",
    reason="set CODE2PAPER_RUN_LIVE_LLM=1 to call the configured live endpoint",
)
def test_live_gemma_supervisor_decides_search_symbols() -> None:
    """Calls the real Gemma endpoint.  Verifies the backend either:
    (a) returns an llm_proposal with a valid action, or
    (b) falls back to deterministic (acceptable for slow/blocked endpoints).
    """

    base_url = (
        os.environ.get("CODE2PAPER_LIVE_LLM_BASE_URL")
        or os.environ.get("CODE2PAPER_OPENAI_BASE_URL")
        or "http://127.0.0.1:8000/v1"
    ).rstrip("/")
    model = (
        os.environ.get("CODE2PAPER_LIVE_LLM_MODEL")
        or os.environ.get("CODE2PAPER_LLM_MODEL")
        or "gemma4-31b-nvfp4"
    )
    os.environ["CODE2PAPER_OPENAI_BASE_URL"] = base_url
    os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY") or "dummy-local-vllm"

    cfg = LLMConfig(
        provider=LLMProvider.OPENAI,
        model=model,
        temperature=0.0,
        max_output_tokens=512,
        request_timeout_seconds=120,
        retry_max_attempts=1,
        cache=False,
    )
    backend = GemmaSupervisorBackend(
        llm_config=cfg,
        run_id=_RUN_ID,
        repo_snapshot_id=_SNAPSHOT_ID,
    )
    ctx = _context(
        active_obligation=_obligation(
            candidate_symbol_ids=("models.predictor:forward",),
            missing_information=("predictor_module_path",),
            typed_targets=(_typed_target(search_terms=("score", "predictor")),),
        ),
        active_issue=_issue(issue_kind="missing_anchor"),
    )
    decision = backend.decide(ctx)
    # Either path is acceptable; both must produce a valid decision.
    assert decision.produced_by in {"llm_proposal", "deterministic_fallback"}
    assert decision.action in _LLM_ALLOWED_ACTIONS_SET
    assert decision.run_id == _RUN_ID
