"""Gemma-backed research supervisor backend (R8 wiring).

Implements ``GemmaSupervisorBackend`` — an LLM-backed supervisor that
calls a local Gemma inference endpoint (OpenAI-compatible) and parses
the structured decision proposal.

Design (from ``docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md``
section 8.2 / R3.2):

- The supervisor prompt is assembled **only** from
  ``ResearchDecisionContextV1``.  Injecting raw source code, full
  evidence JSON or the full tool history into the prompt is a contract
  violation.
- The LLM picks the **action** and provides a **rationale** and
  **goal**.  The backend **deterministically** builds the tool calls
  for the chosen action (reusing ``DeterministicSupervisorBackend``
  helpers).  This keeps tool-call construction safe and reproducible
  while letting the LLM control research strategy.
- On any failure (API error, parse error, validation error, blocked
  response), the backend falls back to ``DeterministicSupervisorBackend``
  so the graph never stalls.
- ``produced_by`` is ``"llm_proposal"`` when the LLM succeeds and
  ``"deterministic_fallback"`` when it falls back.
- Temperature is forced to 0 for R8 protocol compliance (section R8.1
  rule 2), regardless of the ``LLMConfig`` default.

The backend is selected by setting ``CODE2PAPER_AGENTIC_RESEARCH_V3=1``
and providing a valid ``LLMConfig`` (via the standard
``CODE2PAPER_LLM_PROVIDER`` / ``CODE2PAPER_OPENAI_BASE_URL`` /
``OPENAI_API_KEY`` environment variables).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from code2paper.agentic.research_models import (
    ResearchAction,
    ResearchDecisionV1,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    ResearchDecisionContextV1,
    SupervisorBackend,
    _action_default_tool,
    _decision_id,
    _stable_tool_call_id,
    _tool_kind_for,
)
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key

_logger = logging.getLogger(__name__)


# Actions the LLM is allowed to propose.  Terminal actions (RECORD_GAP,
# STOP_BLOCKED, PLAN_METHOD) do not issue tool calls.
_LLM_ALLOWED_ACTIONS: tuple[ResearchAction, ...] = (
    "SEARCH_SYMBOLS",
    "READ_CANDIDATE",
    "TRACE_CALLS",
    "TRACE_DATA_FLOW",
    "INSPECT_BRANCH",
    "INSPECT_CONFIG",
    "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH",
    "RECORD_GAP",
    "STOP_BLOCKED",
)

_LLM_ALLOWED_ACTIONS_SET = frozenset(_LLM_ALLOWED_ACTIONS)

# Actions that issue tool calls (must produce at least one tool call).
_TOOL_CALLING_ACTIONS = frozenset({
    "SEARCH_SYMBOLS", "READ_CANDIDATE", "TRACE_CALLS", "TRACE_DATA_FLOW",
    "INSPECT_BRANCH", "INSPECT_CONFIG", "SEARCH_HINTS",
    "BUILD_BEHAVIOR_SUBGRAPH",
})


class GemmaSupervisorBackend:
    """LLM-backed supervisor backend using a local Gemma endpoint.

    The backend implements the ``SupervisorBackend`` protocol.  It
    builds a compact prompt from ``ResearchDecisionContextV1``, calls
    the Gemma LLM, parses the JSON response into a
    ``ResearchDecisionV1``, and falls back to
    ``DeterministicSupervisorBackend`` on any failure.

    Parameters
    ----------
    llm_config
        The LLM configuration (provider, model, base URL, API key).
        Must point to the local Gemma vLLM endpoint for R8 runs.
    run_id
        Stable run identity (used for decision IDs and tool call IDs).
    repo_snapshot_id
        Repository snapshot ID (used for tool call construction).
    ready_tools
        Tuple of tool names available in the current runtime.
    hard_rules
        Tuple of hard rule names enforced by policy merge.
    fallback
        Optional pre-constructed ``DeterministicSupervisorBackend``
        used on LLM failure.  When omitted, a fresh one is created.
    temperature
        Override temperature for the LLM call.  Defaults to 0.0 for
        R8 protocol compliance.
    """

    def __init__(
        self,
        *,
        llm_config: LLMConfig,
        run_id: str,
        repo_snapshot_id: str,
        ready_tools: tuple[str, ...] = (
            "find_entrypoints",
            "search_symbols",
            "read_symbol",
            "find_references",
            "build_behavior_subgraph",
        ),
        hard_rules: tuple[str, ...] = (
            "no_snapshot_external_paths",
            "no_unregistered_tools",
            "no_authority_upgrade",
            "no_skipped_validators",
            "no_duplicate_no_gain_calls",
            "obligation_must_exist",
            "budgets_must_be_available",
            "fallback_must_be_safe",
        ),
        fallback: DeterministicSupervisorBackend | None = None,
        temperature: float = 0.0,
    ) -> None:
        self._llm_config = llm_config.model_copy(update={"temperature": temperature, "cache": False})
        self._run_id = run_id
        self._repo_snapshot_id = repo_snapshot_id
        self._ready_tools = tuple(ready_tools)
        self._hard_rules = tuple(hard_rules)
        self._fallback = fallback or DeterministicSupervisorBackend(
            run_id=run_id,
            repo_snapshot_id=repo_snapshot_id,
            ready_tools=self._ready_tools,
            hard_rules=self._hard_rules,
        )
        self._temperature = temperature

    # ------------------------------------------------------------------
    # SupervisorBackend protocol
    # ------------------------------------------------------------------

    def decide(self, context: ResearchDecisionContextV1) -> ResearchDecisionV1:
        """Return a structured decision proposal.

        Calls the Gemma LLM with a compact prompt built from the
        context.  On any failure (API error, parse error, validation
        error, blocked response, disallowed action), falls back to the
        deterministic backend.
        """

        if not self._llm_available():
            return self._fallback.decide(context)

        prompt = self._build_prompt(context)
        request = LLMRequest(
            prompt_template_id="agentic_research_supervisor_v1",
            prompt=_SYSTEM_PROMPT,
            input_payload=prompt,
            schema_name="ResearchSupervisorProposalV1",
            response_json_schema=_RESPONSE_SCHEMA,
        )

        try:
            response = LLMClient(self._llm_config).complete(request)
        except Exception as exc:  # noqa: BLE001 — LLM failures must not stall the graph
            _logger.warning("gemma_supervisor_llm_error: %s", exc)
            return self._fallback.decide(context)

        if response.blocked_reason:
            _logger.warning("gemma_supervisor_blocked: %s", response.blocked_reason)
            return self._fallback.decide(context)

        if not response.text.strip():
            _logger.warning("gemma_supervisor_empty_response")
            return self._fallback.decide(context)

        try:
            proposal = _parse_proposal(response.text)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            _logger.warning("gemma_supervisor_parse_error: %s", exc)
            return self._fallback.decide(context)

        action = proposal.get("action", "")
        if action not in _LLM_ALLOWED_ACTIONS_SET:
            _logger.warning("gemma_supervisor_disallowed_action: %r", action)
            return self._fallback.decide(context)

        return self._build_decision(context, proposal)

    # ------------------------------------------------------------------
    # LLM availability check
    # ------------------------------------------------------------------

    def _llm_available(self) -> bool:
        """Check whether the LLM config is usable."""

        if self._llm_config.provider == LLMProvider.NONE:
            return False
        if not has_provider_api_key(self._llm_config):
            return False
        return True

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, context: ResearchDecisionContextV1) -> dict[str, Any]:
        """Build the compact prompt payload from the decision context.

        The prompt contains only fields from ``ResearchDecisionContextV1``
        (design 8.2 hard rule).  No raw source code, full evidence JSON
        or full tool history is injected.
        """

        prompt: dict[str, Any] = {
            "run_id": context.run_id,
            "turn_index": context.turn_index,
            "allowed_actions": list(_LLM_ALLOWED_ACTIONS),
            "ready_tools": list(self._ready_tools),
            "hard_rules": list(self._hard_rules),
            "no_progress_counter": context.no_progress_counter,
            "unresolved_must_cover_ids": list(context.unresolved_must_cover_ids),
        }

        obl = context.active_obligation
        if obl is not None:
            prompt["active_obligation"] = {
                "obligation_id": obl.obligation_id,
                "priority": obl.priority,
                "status": obl.status,
                "missing_information": list(obl.missing_information),
                "candidate_symbol_ids": list(obl.candidate_symbol_ids),
                "typed_behavior_targets": [
                    {
                        "target_id": t.target_id,
                        "role": t.role,
                        "desired_predicates": list(t.desired_predicates),
                        "required_relations": list(t.required_relations),
                        "search_terms": list(t.search_terms),
                    }
                    for t in obl.typed_behavior_targets
                ],
            }
        else:
            prompt["active_obligation"] = None

        issue = context.active_issue
        if issue is not None:
            prompt["active_issue"] = {
                "issue_id": issue.issue_id,
                "issue_kind": issue.issue_kind,
                "obligation_id": issue.obligation_id,
                "description": issue.description,
            }
        else:
            prompt["active_issue"] = None

        prompt["recent_observations"] = [
            {
                "observation_id": obs.observation_id,
                "tool_name": obs.tool_name,
                "status": obs.status,
                "source_authority": obs.source_authority,
                "candidate_count": obs.candidate_count,
                "truncated": obs.truncated,
                "ambiguous": obs.ambiguous,
            }
            for obs in context.recent_observations
        ]

        prompt["missing_information"] = list(context.missing_information)
        prompt["top_candidate_symbol_ids"] = list(context.top_candidate_symbol_ids)
        prompt["remaining_budgets"] = dict(context.remaining_budgets)
        prompt["current_supported_claim_ids"] = list(context.current_supported_claim_ids)

        return prompt

    # ------------------------------------------------------------------
    # Decision construction from LLM proposal
    # ------------------------------------------------------------------

    def _build_decision(
        self,
        context: ResearchDecisionContextV1,
        proposal: dict[str, Any],
    ) -> ResearchDecisionV1:
        """Build a ``ResearchDecisionV1`` from the LLM proposal.

        The LLM provides ``action``, ``rationale``, ``goal``, and
        ``expected_information_gain``.  Tool calls are constructed
        deterministically based on the action (reusing the deterministic
        backend's logic) so tool-call construction stays safe and
        reproducible.
        """

        action: ResearchAction = proposal["action"]
        rationale = proposal.get("rationale", "").strip()
        goal = proposal.get("goal", "").strip()
        expected_gain = proposal.get("expected_information_gain", "").strip()

        obl = context.active_obligation
        obligation_id = obl.obligation_id if obl else ""
        issue = context.active_issue
        issue_id = issue.issue_id if issue else ""

        if not goal:
            goal = self._fallback._goal_for(action, context)
        if not rationale:
            rationale = f"llm_proposal:{action}"
        if not expected_gain:
            expected_gain = self._fallback._expected_gain(action, context)

        tool_calls = self._build_tool_calls(context, action)

        # If a tool-calling action cannot produce tool calls, fall back
        # to the deterministic backend (which handles the escalation
        # logic: try SEARCH_SYMBOLS, then RECORD_GAP / STOP_BLOCKED).
        if action in _TOOL_CALLING_ACTIONS and not tool_calls:
            return self._fallback.decide(context)

        stop_condition = self._fallback._stop_condition(context)
        fallback_action = self._fallback_fallback_action(context)

        return ResearchDecisionV1(
            decision_id=_decision_id(self._run_id, context.turn_index, action),
            run_id=self._run_id,
            turn_index=context.turn_index,
            action=action,
            obligation_id=obligation_id,
            issue_id=issue_id,
            goal=goal,
            selected_tool_calls=tool_calls,
            candidate_scope=tuple(context.top_candidate_symbol_ids),
            expected_information_gain=expected_gain,
            evidence_needed=tuple(context.missing_information),
            stop_condition=stop_condition,
            fallback_action=fallback_action,
            rationale=rationale,
            produced_by="llm_proposal",
        )

    def _build_tool_calls(
        self, context: ResearchDecisionContextV1, action: ResearchAction
    ) -> tuple[ResearchToolCallV1, ...]:
        """Construct tool calls for the given action.

        Reuses the deterministic backend's argument construction logic
        so tool calls are always well-formed and policy-mergeable.
        """

        if action in {"STOP_BLOCKED", "RECORD_GAP", "PLAN_METHOD"}:
            return ()

        obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation
            else ""
        )
        if not obligation_id:
            return ()

        tool_name = _action_default_tool(action)
        if tool_name is None or tool_name not in self._ready_tools:
            return ()

        tool_kind = _tool_kind_for(tool_name)
        turn = context.turn_index
        tool_call_id = _stable_tool_call_id(
            self._run_id, turn, tool_name, obligation_id
        )

        # Delegate argument construction to the fallback backend.
        det = self._fallback
        arguments: dict[str, Any] = {}
        if tool_name == "search_symbols":
            arguments["query"] = det._search_query(context)
            arguments["top_k"] = 10
        elif tool_name == "read_symbol":
            symbol = det._read_symbol_target(context)
            path = det._read_symbol_path(context)
            if symbol is None or path is None:
                return ()
            arguments["path"] = path
            arguments["symbol"] = symbol
            arguments["top_k"] = 1
        elif tool_name == "find_references":
            symbol = det._read_symbol_target(context)
            if symbol is None:
                return ()
            arguments["symbol"] = symbol
        elif tool_name == "find_entrypoints":
            arguments["top_k"] = 20
        elif tool_name == "build_behavior_subgraph":
            symbol = det._read_symbol_target(context)
            if symbol is None:
                return ()
            arguments["symbol"] = symbol
            arguments["depth"] = 1
            arguments["node_budget"] = 32

        call = ResearchToolCallV1(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_kind=tool_kind,
            obligation_id=obligation_id,
            goal=det._goal_for(action, context),
            repo_snapshot_id=self._repo_snapshot_id,
            path_scope=tuple(context.top_candidate_symbol_ids),
            top_k=int(arguments.get("top_k", 0)),
            depth=int(arguments.get("depth", 0)),
            node_budget=int(arguments.get("node_budget", 0)),
            arguments=arguments,
        )
        return (call,)

    def _fallback_fallback_action(
        self, context: ResearchDecisionContextV1
    ) -> ResearchAction | None:
        """Determine the fallback action for the decision.

        Uses the deterministic fallback table so policy merge knows
        what to try next if this decision is rejected.
        """

        from code2paper.agentic.research_supervisor import fallback_action_for_issue

        action, _ = fallback_action_for_issue(context.active_issue)
        return action


# ---------------------------------------------------------------------------
# System prompt and response schema
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are the research supervisor inside Code2Paper's robust LangGraph "
    "research agent.  You decide what research action to take next based on "
    "the compact decision context provided.\n\n"
    "Hard constraints:\n"
    "- You may ONLY propose one of the allowed_actions listed in the context.\n"
    "- Your decision is a PROPOSAL: policy merge may reject it and substitute "
    "a deterministic fallback.\n"
    "- You MUST NOT invent file paths, symbol names, span IDs or evidence IDs.\n"
    "- You MUST NOT propose actions that are not in allowed_actions.\n"
    "- Code evidence decides what may be claimed; you only decide what to "
    "search/trace/inspect next.\n"
    "- When no_progress_counter >= 3, prefer RECORD_GAP.\n"
    "- When the active issue indicates a specific gap, pick the action that "
    "addresses that gap.\n\n"
    "Return ONLY a JSON object with this schema:\n"
    '{\n'
    '  "action": "<one of allowed_actions>",\n'
    '  "rationale": "<brief reason for this action>",\n'
    '  "goal": "<what this action should achieve>",\n'
    '  "expected_information_gain": "<what new information this should produce>"\n'
    '}\n'
)


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "description": "One of the allowed_actions from the context.",
        },
        "rationale": {
            "type": "string",
            "description": "Brief reason for choosing this action.",
        },
        "goal": {
            "type": "string",
            "description": "What this action should achieve.",
        },
        "expected_information_gain": {
            "type": "string",
            "description": "What new information this action should produce.",
        },
    },
    "required": ["action", "rationale", "goal"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_proposal(text: str) -> dict[str, Any]:
    """Parse the LLM response text into a proposal dict.

    The LLM may wrap the JSON in markdown code fences or prepend
    commentary.  This function extracts the first JSON object from
    the response.
    """

    stripped = text.strip()

    # Strip markdown code fences if present.
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove first fence line.
        lines = lines[1:]
        # Remove trailing fence line if present.
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    # Find the first { and last } to extract the JSON object.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found in response")

    payload = stripped[start : end + 1]
    proposal = json.loads(payload)

    if not isinstance(proposal, dict):
        raise ValueError("response is not a JSON object")

    action = proposal.get("action", "")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("missing or empty 'action' field")

    return proposal
