"""LLM-backed repository research manager.

Implements ``GemmaSupervisorBackend`` — an LLM-backed supervisor that
calls a local Gemma inference endpoint (OpenAI-compatible) and parses
the structured decision proposal.

Design (from ``docs/agentic_robust_langgraph_research_writing_design_2026-07-19.md``
section 8.2 / R3.2):

- The prompt is assembled **only** from ``ResearchDecisionContextV1``.
  That context now includes bounded source excerpts and exact candidates
  returned by the repository tools, so the model can actually reason about
  what it has just read.
- The LLM selects concrete repository tools and their typed arguments.  The
  harness infers the legacy graph action, validates every argument and path,
  and enforces budgets; it does not choose the query, path or symbol on the
  model's behalf.
- On an infrastructure or representation failure the backend can use the
  deterministic compatibility backend, but records the degraded event so a
  product run cannot present a scripted fallback as autonomous research.
- ``produced_by`` is ``"llm_proposal"`` when the LLM succeeds and
  ``"deterministic_fallback"`` when it falls back.
- The supervisor's LLM config is built via
  :func:`code2paper.llm.role_config.apply_role_config` with
  ``role="research_supervisor"``.  This applies the R8 per-role
  sampling protocol (temperature=0.20, max_output_tokens=1536) while
  respecting per-role env overrides
  (``CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR`` etc.).  ``cache``
  is forced to ``False`` for R8 protocol compliance.

The backend is selected by setting ``CODE2PAPER_AGENTIC_RESEARCH_V3=1``
and providing a valid ``LLMConfig`` (via the standard
``CODE2PAPER_LLM_PROVIDER`` / ``CODE2PAPER_OPENAI_BASE_URL`` /
``OPENAI_API_KEY`` environment variables).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from code2paper.agentic.research_models import (
    ResearchAction,
    ResearchDecisionV1,
)
from code2paper.agentic.research_supervisor import (
    DeterministicSupervisorBackend,
    ResearchDecisionContextV1,
    SupervisorBackend,
    _decision_id,
    _tool_kind_for,
)
from code2paper.agentic.research_models import ResearchToolCallV1
from code2paper.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.role_config import RESEARCH_SUPERVISOR, apply_role_config
from code2paper.llm.response_schemas import try_parse_structured_response_with_trace

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
    "COMPILE_EVIDENCE",
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


# The model sees repository operations, not the packet/fact/claim compiler
# internals.  The latter remain deterministic services behind the evidence
# boundary.  Multiple calls in one proposal are allowed when they represent
# the same research move (for example two independent reads).
_MODEL_TOOL_TO_ACTION: dict[str, ResearchAction] = {
    "list_repository_tree": "SEARCH_SYMBOLS",
    "find_entrypoints": "SEARCH_SYMBOLS",
    "search_symbols": "SEARCH_SYMBOLS",
    "search_code": "SEARCH_SYMBOLS",
    "read_symbol": "READ_CANDIDATE",
    "read_code_span": "READ_CANDIDATE",
    "find_references": "TRACE_CALLS",
    "trace_call_path": "TRACE_CALLS",
    "trace_data_flow": "TRACE_DATA_FLOW",
    "inspect_control_flow": "INSPECT_BRANCH",
    "inspect_configuration": "INSPECT_CONFIG",
    "build_behavior_subgraph": "BUILD_BEHAVIOR_SUBGRAPH",
}

_MODEL_TOOL_GUIDANCE: dict[str, dict[str, Any]] = {
    "list_repository_tree": {"arguments": {"file_kinds": "optional array such as ['python']"}, "use_when": "orienting in an unfamiliar repository; use path_scope and depth to bound the listing"},
    "find_entrypoints": {"arguments": {}, "use_when": "locating the executable lifecycle"},
    "search_symbols": {"arguments": {"query": "string"}, "use_when": "finding classes or functions by method concept"},
    "search_code": {"arguments": {"query": "string"}, "use_when": "finding an operation, literal, loss, config key, or API use"},
    "read_symbol": {"arguments": {"path": "exact path", "symbol": "exact symbol"}, "use_when": "reading a discovered function or class"},
    "read_code_span": {"arguments": {"path": "exact path", "start_line": "int", "end_line": "int"}, "use_when": "reading a concrete search or trace hit"},
    "find_references": {"arguments": {"symbol": "exact symbol"}, "use_when": "finding callers and usages"},
    "trace_call_path": {"arguments": {"source_symbol": "exact symbol", "target_symbol": "exact symbol"}, "use_when": "checking whether two known symbols are connected"},
    "trace_data_flow": {"arguments": {"symbol": "exact symbol", "direction": "both|upstream|downstream"}, "use_when": "following inputs, outputs, assignments, or returns"},
    "inspect_control_flow": {"arguments": {"path": "exact path", "symbol": "optional exact symbol"}, "use_when": "checking branches, loops, and conditions"},
    "inspect_configuration": {"arguments": {"config_key": "key or empty", "path": "optional exact path"}, "use_when": "checking defaults and runtime configuration"},
    "build_behavior_subgraph": {"arguments": {"path": "exact path", "symbol": "exact symbol"}, "use_when": "extracting operations from code already read"},
}

_COMMON_TOOL_INPUT_FIELDS = {
    "tool_call_id",
    "obligation_id",
    "goal",
    "repo_snapshot_id",
    "path_scope",
    "top_k",
    "depth",
    "node_budget",
}


def infer_research_tool_name_from_arguments(arguments: dict[str, Any]) -> str:
    """Return a ready tool name when argument keys uniquely identify it."""

    args = arguments if isinstance(arguments, dict) else {}
    path = args.get("path")
    if isinstance(path, list):
        path = next((str(item).strip() for item in path if str(item).strip()), "")
    path_text = str(path or "").strip()
    symbol = str(args.get("symbol") or "").strip()
    query = str(args.get("query") or "").strip()
    source_symbol = str(args.get("source_symbol") or "").strip()
    target_symbol = str(args.get("target_symbol") or "").strip()
    direction = str(args.get("direction") or "").strip()
    has_span_keys = any(key in args for key in ("start_line", "end_line", "context_lines"))
    matches: list[str] = []
    if source_symbol and target_symbol:
        matches.append("trace_call_path")
    if symbol and direction and not path_text and not query:
        matches.append("trace_data_flow")
    if path_text and symbol and "start_line" not in args and "end_line" not in args:
        matches.append("read_symbol")
    if path_text and not symbol and has_span_keys:
        matches.append("read_code_span")
    if query and not path_text and not symbol and str(args.get("kind") or "").strip() in {"", "text"}:
        matches.append("search_symbols")
    if query and str(args.get("kind") or "").strip() not in {"", "text"}:
        matches.append("search_code")
    if symbol and not path_text and not query and not direction:
        matches.append("find_references")
    if len(matches) == 1:
        return matches[0]
    return ""


def _alias_model_tool_name(data: dict[str, Any]) -> str:
    """Copy a model-owned ``tool`` alias onto ``tool_name`` when unique."""

    named = str(data.get("tool_name") or "").strip()
    if named:
        return named
    alias = str(data.get("tool") or "").strip()
    if alias in _MODEL_TOOL_TO_ACTION:
        return alias
    return ""


def _flatten_model_tool_call_items(value: Any) -> list[Any]:
    """Drop empty list items and unwrap a nested list-of-dicts."""

    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list):
        return []
    flattened: list[Any] = []
    for item in value:
        if item in (None, {}, []):
            continue
        if isinstance(item, list):
            flattened.extend(_flatten_model_tool_call_items(item))
            continue
        flattened.append(item)
    return flattened


def lift_harness_fields_from_tool_arguments(
    raw_call: dict[str, Any],
) -> dict[str, Any]:
    """Move harness-owned keys off ``arguments`` onto the call item.

    Representation-only: the model already supplied ``top_k`` / ``depth`` /
    ``node_budget`` / ``path_scope`` / ``goal``, but nested them under
    ``arguments`` where the schema forbids them.  Values are lifted, never
    invented.
    """

    repaired = dict(raw_call)
    arguments = repaired.get("arguments")
    if not isinstance(arguments, dict):
        return repaired
    cleaned = dict(arguments)
    for field in ("top_k", "depth", "node_budget"):
        if field not in cleaned:
            continue
        nested = cleaned.pop(field)
        current = repaired.get(field)
        if current in (None, "", 0, "0"):
            repaired[field] = nested
    if "path_scope" in cleaned and not repaired.get("path_scope"):
        repaired["path_scope"] = cleaned.pop("path_scope")
    elif "path_scope" in cleaned:
        cleaned.pop("path_scope")
    if "goal" in cleaned and not str(repaired.get("goal") or "").strip():
        repaired["goal"] = cleaned.pop("goal")
    elif "goal" in cleaned:
        cleaned.pop("goal")
    for field in ("tool_call_id", "obligation_id", "repo_snapshot_id"):
        cleaned.pop(field, None)
    repaired["arguments"] = cleaned
    return repaired


def sanitize_model_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Keep schema fields only; coerce a list ``path`` to one string."""

    from code2paper.agentic.research_tools import RESEARCH_TOOL_INPUT_SCHEMAS

    schema = RESEARCH_TOOL_INPUT_SCHEMAS.get(tool_name)
    if schema is None or not isinstance(arguments, dict):
        return arguments if isinstance(arguments, dict) else {}
    allowed = set(schema.model_fields) - _COMMON_TOOL_INPUT_FIELDS - {"source_authority"}
    cleaned: dict[str, Any] = {}
    for key, value in arguments.items():
        if key not in allowed:
            continue
        if key == "path" and isinstance(value, list):
            value = next((str(item).strip() for item in value if str(item).strip()), "")
        cleaned[key] = value
    return cleaned


class _ResearchManagerToolCallV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    path_scope: list[str] = Field(default_factory=list)
    goal: str = ""
    top_k: int = 0
    depth: int = 0
    node_budget: int = 0

    @model_validator(mode="before")
    @classmethod
    def _infer_missing_tool_name(cls, data: Any) -> Any:
        """Fill tool_name from a ``tool`` alias or uniquely identifying arguments.

        Representation-only: the model already named a path, query, or ready
        tool, but omitted the schema field or nested harness-owned keys.
        """

        if not isinstance(data, dict):
            return data
        repaired = lift_harness_fields_from_tool_arguments(data)
        named = _alias_model_tool_name(repaired)
        if named:
            repaired["tool_name"] = named
        repaired.pop("tool", None)
        if str(repaired.get("tool_name") or "").strip():
            return repaired
        arguments = (
            repaired.get("arguments")
            if isinstance(repaired.get("arguments"), dict)
            else {}
        )
        inferred = infer_research_tool_name_from_arguments(arguments)
        if not inferred:
            return repaired
        repaired["tool_name"] = inferred
        return repaired


class _ResearchManagerProposalV1(BaseModel):
    """Representation model; semantic/tool validation remains in the backend."""

    model_config = ConfigDict(extra="allow")

    goal: str = ""
    rationale: str = ""
    expected_information_gain: str = ""
    terminal_action: str = ""
    tool_calls: list[_ResearchManagerToolCallV1] = Field(default_factory=list)
    action: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_tool_call_items(cls, data: Any) -> Any:
        """Drop empty list items and unwrap a nested list-of-dicts."""

        if not isinstance(data, dict):
            return data
        if "tool_calls" not in data:
            return data
        repaired = dict(data)
        repaired["tool_calls"] = _flatten_model_tool_call_items(data.get("tool_calls"))
        return repaired


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
        Optional override temperature for the LLM call.  When ``None``
        (the default), the supervisor uses the per-role R8 protocol
        temperature (0.20 for ``research_supervisor``) applied via
        :func:`apply_role_config`.  When set, the override wins over
        the role default — this is intended for testing or protocol
        experiments and is not used in production R8 runs.
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
        temperature: float | None = None,
    ) -> None:
        # Apply the per-role R8 sampling protocol (temperature=0.20,
        # max_output_tokens=1536 for research_supervisor) via
        # ``apply_role_config``.  Per-role env overrides
        # (``CODE2PAPER_LLM_TEMPERATURE_RESEARCH_SUPERVISOR`` etc.) are
        # respected.  When the caller passes an explicit ``temperature``
        # (non-None), it overrides the role default — this is intended
        # for testing or protocol experiments and is not used in
        # production R8 runs.
        role_config = apply_role_config(llm_config, RESEARCH_SUPERVISOR)
        if temperature is not None:
            role_config = role_config.model_copy(update={"temperature": temperature})
        # Always force cache=False for R8 protocol compliance.
        self._llm_config = role_config.model_copy(update={"cache": False})
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
        self._temperature = self._llm_config.temperature
        self._degraded_events: list[str] = []
        self._representation_repairs: list[dict[str, Any]] = []
        self._llm_decision_count = 0

    @property
    def degraded_events(self) -> tuple[str, ...]:
        """Compatibility-fallback events observed during this run."""

        return tuple(self._degraded_events)

    @property
    def llm_decision_count(self) -> int:
        return self._llm_decision_count

    @property
    def representation_repairs(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._representation_repairs)

    @property
    def deterministic_fallback(self) -> DeterministicSupervisorBackend:
        """Expose the non-LLM safety fallback to the policy layer.

        Policy merge must never ask this backend to generate a second model
        proposal after rejecting the first one.  Doing so both spends another
        model call and makes the resulting trace look autonomous even though
        the policy had already rejected the manager's decision.
        """

        return self._fallback

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
            return self._fallback_decision(context, "llm_unavailable")

        prompt = self._build_prompt(context)
        ready_model_tools = [
            name for name in self._ready_tools if name in _MODEL_TOOL_TO_ACTION
        ]
        request = LLMRequest(
            prompt_template_id="agentic_repository_research_manager_v2",
            prompt=_SYSTEM_PROMPT,
            input_payload=prompt,
            schema_name="ResearchSupervisorProposalV1",
            response_json_schema=_response_schema_for_tools(ready_model_tools),
        )

        try:
            response = LLMClient(self._llm_config).complete(request)
        except Exception as exc:  # noqa: BLE001 — LLM failures must not stall the graph
            _logger.warning("gemma_supervisor_llm_error: %s", exc)
            return self._fallback_decision(context, "llm_api_error")

        if response.blocked_reason:
            _logger.warning("gemma_supervisor_blocked: %s", response.blocked_reason)
            return self._fallback_decision(context, "llm_blocked")

        if not response.text.strip():
            _logger.warning("gemma_supervisor_empty_response")
            return self._fallback_decision(context, "llm_empty_response")

        try:
            parsed, recovery, parse_error = try_parse_structured_response_with_trace(
                response.text, _ResearchManagerProposalV1
            )
            if parsed is None:
                raise ValueError(parse_error or "research manager schema failed")
            if recovery.applied:
                self._representation_repairs.append({
                    "turn_index": context.turn_index,
                    "operations": list(recovery.operations),
                    "original_text_digest": recovery.original_text_digest,
                    "parsed_payload_digest": recovery.parsed_payload_digest,
                })
            proposal = parsed.model_dump(mode="json")
            _validate_proposal_shape(proposal)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            # Phase 7 diagnostic: record the raw response text so we can
            # see what Gemma actually returned when the parser fails.
            # Truncate to 500 chars to avoid flooding logs.
            raw_preview = response.text[:500].replace("\n", "\\n")
            _logger.warning(
                "gemma_supervisor_parse_error: %s | response_mode=%s | finish_reason=%s | raw_preview=%r",
                exc,
                getattr(response, "response_mode", ""),
                getattr(response, "finish_reason", ""),
                raw_preview,
            )
            return self._fallback_decision(context, "llm_parse_error")

        try:
            decision = self._build_decision(context, proposal)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            _logger.warning("research_manager_invalid_tool_proposal: %s", exc)
            return self._fallback_decision(context, "invalid_tool_proposal")
        self._llm_decision_count += 1
        return decision

    def repair_after_policy_rejection(
        self,
        context: ResearchDecisionContextV1,
        *,
        rejected_decision: ResearchDecisionV1,
        rejection_messages: tuple[str, ...],
    ) -> ResearchDecisionV1:
        """Give one rejected tool choice back to its owning Manager.

        The policy layer still has final authority and validates the repaired
        decision independently.  This is a content repair, not harness JSON
        recovery: the LLM sees why its prior action was unsafe or redundant
        and must choose a materially different next step.
        """

        rejected_calls = tuple(
            f"{call.tool_name}({json.dumps(call.arguments, ensure_ascii=False, sort_keys=True)})"
            for call in rejected_decision.selected_tool_calls
        )
        feedback = tuple(
            dict.fromkeys(
                (
                    "The previous proposal was not executed.",
                    *(f"rejected_call={item}" for item in rejected_calls),
                    *rejection_messages,
                    "Choose a policy-compliant action that is not the rejected call.",
                )
            )
        )
        repaired = self.decide(
            context.model_copy(update={"policy_feedback": feedback})
        )
        rejected_sig = tuple(
            (
                call.tool_name,
                json.dumps(call.arguments, ensure_ascii=False, sort_keys=True),
            )
            for call in rejected_decision.selected_tool_calls
        )
        repaired_sig = tuple(
            (
                call.tool_name,
                json.dumps(call.arguments, ensure_ascii=False, sort_keys=True),
            )
            for call in repaired.selected_tool_calls
        )
        if repaired.action == rejected_decision.action and repaired_sig == rejected_sig:
            return self._fallback_decision(context, "unchanged_retry_rejected")
        return repaired.model_copy(update={
            "rationale": (
                "policy_repair: " + repaired.rationale
            ).strip(),
        })

    def _fallback_decision(
        self,
        context: ResearchDecisionContextV1,
        reason: str,
    ) -> ResearchDecisionV1:
        self._degraded_events.append(reason)
        return self._fallback.decide(context)

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
        """Build the manager workspace from the bounded decision context."""

        ready_model_tools = [
            name for name in self._ready_tools if name in _MODEL_TOOL_TO_ACTION
        ]

        prompt: dict[str, Any] = {
            "run_id": context.run_id,
            "turn_index": context.turn_index,
            "allowed_actions": list(context.allowed_actions or _LLM_ALLOWED_ACTIONS),
            "ready_tools": ready_model_tools,
            "tool_guidance": {
                name: _MODEL_TOOL_GUIDANCE[name] for name in ready_model_tools
            },
            "hard_rules": list(self._hard_rules),
            "no_progress_counter": context.no_progress_counter,
            "unresolved_must_cover_ids": list(context.unresolved_must_cover_ids),
            "behavior_template_search_hints": [
                item.model_dump(mode="json")
                for item in context.behavior_template_search_hints
            ],
        }

        obl = context.active_obligation
        if obl is not None:
            prompt["active_obligation"] = {
                "obligation_id": obl.obligation_id,
                "priority": obl.priority,
                "status": obl.status,
                # The author's question is the research goal.  Omitting it
                # reduced the manager to generic target labels such as
                # "feature" and hid decisive details (dimensions, formulas,
                # named stages) that should drive repository queries.
                "author_question": obl.author_text,
                "missing_information": list(obl.missing_information),
                "candidate_symbol_ids": list(obl.candidate_symbol_ids),
                "typed_behavior_targets": [
                    {
                        "target_id": t.target_id,
                        "role": t.role,
                        "desired_predicates": list(t.desired_predicates),
                        "predicate_groups": [list(group) for group in t.predicate_groups],
                        "required_relations": list(t.required_relations),
                        "inputs": list(t.inputs),
                        "transformations": list(t.transformations),
                        "decisions": list(t.decisions),
                        "outputs": list(t.outputs),
                        "conditions": list(t.conditions),
                        "search_terms": list(t.search_terms),
                        "aliases": list(t.aliases),
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
                "query": obs.query,
                "candidate_count": obs.candidate_count,
                "truncated": obs.truncated,
                "ambiguous": obs.ambiguous,
                "semantic_summary": obs.semantic_summary,
                "code_excerpt": obs.code_excerpt,
                "discovered_symbols": list(obs.discovered_symbols[:12]),
                "discovered_relations": list(obs.discovered_relations[:12]),
                "enclosing_symbol_refs": list(obs.enclosing_symbol_refs[:8]),
            }
            for obs in context.recent_observations
        ]

        prompt["missing_information"] = list(context.missing_information)
        prompt["top_candidate_symbol_ids"] = list(context.top_candidate_symbol_ids)
        prompt["remaining_budgets"] = dict(context.remaining_budgets)
        # Opaque claim IDs are useful to the harness, not to the Manager.  The
        # semantic statements let the LLM compare what is already established
        # with the author's still-open question before selecting another tool.
        prompt["current_compiled_evidence"] = {
            "supported_method_statements": list(
                context.current_supported_claim_statements
            ),
            "remaining_information": list(context.missing_information),
        }
        prompt["executed_tool_calls"] = [
            item.model_dump(mode="json") for item in context.executed_tool_calls
        ]
        # Exact-repeat guard, mirror of the policy rule: re-reading the same
        # path+symbol (or a code span that covers the same line) inside this
        # snapshot returns identical bytes and is rejected by policy as a
        # duplicate no-gain call, even when a different obligation prompted
        # the original read.  The model must not propose these again; it must
        # trace a caller/data/control/config relation or read another span.
        prompt["forbidden_exact_reads"] = [
            item.model_dump(mode="json") for item in context.executed_tool_calls
            if item.tool_name in {"read_symbol", "read_code_span"}
        ]
        if context.policy_feedback:
            prompt["policy_feedback"] = list(context.policy_feedback)

        return prompt

    # ------------------------------------------------------------------
    # Decision construction from LLM proposal
    # ------------------------------------------------------------------

    def _build_decision(
        self,
        context: ResearchDecisionContextV1,
        proposal: dict[str, Any],
    ) -> ResearchDecisionV1:
        """Validate model-owned tool calls and adapt them to graph state."""

        rationale = proposal.get("rationale", "").strip()
        goal = proposal.get("goal", "").strip()
        expected_gain = proposal.get("expected_information_gain", "").strip()

        obl = context.active_obligation
        obligation_id = obl.obligation_id if obl else ""
        issue = context.active_issue
        issue_id = issue.issue_id if issue else ""

        terminal_action = str(proposal.get("terminal_action") or "").strip()
        raw_tool_calls = proposal.get("tool_calls") or []
        if not isinstance(raw_tool_calls, list):
            raise ValueError("tool_calls must be an array")
        raw_tool_calls = _flatten_model_tool_call_items(raw_tool_calls)
        # Representation-only normalization: schema-guided models sometimes
        # echo harness-owned identity fields (obligation_id,
        # repo_snapshot_id, tool_call_id) as siblings of ``arguments`` in a
        # tool-call item.  Those fields are always re-derived from context
        # here, so echoing them is noise, not content.  Drop any key outside
        # the model-owned item schema before strict validation; unknown
        # fields are never honored, so the harness contract is unchanged.
        _MODEL_TOOL_CALL_ITEM_FIELDS = {
            "tool_name",
            "tool",
            "arguments",
            "path_scope",
            "goal",
            "top_k",
            "depth",
            "node_budget",
        }
        raw_tool_calls = [
            lift_harness_fields_from_tool_arguments(
                {
                    key: value
                    for key, value in item.items()
                    if key in _MODEL_TOOL_CALL_ITEM_FIELDS
                }
            )
            if isinstance(item, dict)
            else item
            for item in raw_tool_calls
        ]
        normalized_calls: list[dict[str, Any]] = []
        for item in raw_tool_calls:
            if not isinstance(item, dict):
                continue
            named = _alias_model_tool_name(item)
            if named:
                item = {**item, "tool_name": named}
            item.pop("tool", None)
            if not str(item.get("tool_name") or "").strip():
                arguments = (
                    item.get("arguments")
                    if isinstance(item.get("arguments"), dict)
                    else {}
                )
                inferred = infer_research_tool_name_from_arguments(arguments)
                if inferred:
                    item = {**item, "tool_name": inferred}
            normalized_calls.append(item)
        raw_tool_calls = normalized_calls

        # Compatibility for old recorded responses and API clients.  New live
        # requests are schema-guided to provide model-owned tool arguments;
        # an old action-only response remains visibly compatible during the
        # migration instead of making every historical replay unreadable.
        legacy_action = str(proposal.get("action") or "").strip()
        if not terminal_action and legacy_action in {
            "COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"
        }:
            terminal_action = legacy_action
        if not terminal_action and not raw_tool_calls and legacy_action in _TOOL_CALLING_ACTIONS:
            legacy_calls = self._fallback._build_tool_calls(
                context,
                legacy_action,  # type: ignore[arg-type]
            )
            if not legacy_calls:
                raise ValueError("legacy tool action could not produce a compatible call")
            if not goal:
                goal = legacy_calls[0].goal
            if not rationale:
                rationale = f"legacy_llm_action_compat:{legacy_action}"
            if not expected_gain:
                expected_gain = self._fallback._expected_gain(
                    legacy_action,  # type: ignore[arg-type]
                    context,
                )
            return ResearchDecisionV1(
                decision_id=_decision_id(
                    self._run_id,
                    context.turn_index,
                    legacy_action,  # type: ignore[arg-type]
                ),
                run_id=self._run_id,
                turn_index=context.turn_index,
                action=legacy_action,  # type: ignore[arg-type]
                obligation_id=obligation_id,
                issue_id=issue_id,
                goal=goal,
                selected_tool_calls=legacy_calls,
                candidate_scope=tuple(context.top_candidate_symbol_ids),
                expected_information_gain=expected_gain,
                evidence_needed=tuple(context.missing_information),
                stop_condition=self._fallback._stop_condition(context),
                fallback_action=self._fallback_fallback_action(context),
                rationale=rationale,
                produced_by="llm_proposal",
            )

        if terminal_action:
            if terminal_action not in {
                "COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"
            }:
                raise ValueError(f"invalid terminal_action: {terminal_action}")
            if raw_tool_calls:
                if terminal_action == "COMPILE_EVIDENCE":
                    # Compiling is a checkpoint, not an irreversible stop.  Some
                    # otherwise useful manager responses ask to compile the
                    # current notebook and also sketch the searches they would run
                    # if the result remains partial.  Execute the checkpoint first;
                    # the graph will return the partial result to the manager and
                    # it can then decide whether those searches are still useful.
                    # Rejecting the whole response here used to replace a sound
                    # model decision with the deterministic fallback and could
                    # send research toward an unrelated symbol.
                    raw_tool_calls = []
                    rationale = (
                        rationale
                        + " Follow-up tool proposals were deferred until the "
                        "evidence compiler reports any remaining gap."
                    ).strip()
                else:
                    executable = [
                        item
                        for item in raw_tool_calls
                        if isinstance(item, dict)
                        and str(item.get("tool_name") or "").strip() in self._ready_tools
                        and str(item.get("tool_name") or "").strip() in _MODEL_TOOL_TO_ACTION
                    ]
                    if not executable:
                        raise ValueError("terminal proposal cannot include tool calls")
                    # RECORD_GAP / STOP_BLOCKED plus already-named repository
                    # tools is a representation collision, not a content gap.
                    # Keep the tools the model actually named; drop the stop.
                    terminal_action = ""
                    rationale = (
                        rationale
                        + " Terminal stop was dropped because the proposal "
                        "already named executable repository tools."
                    ).strip()
        if terminal_action:
            action: ResearchAction = terminal_action  # type: ignore[assignment]
            tool_calls: tuple[ResearchToolCallV1, ...] = ()
        else:
            if not raw_tool_calls:
                raise ValueError("research proposal must include at least one tool call")
            if len(raw_tool_calls) > 3:
                raise ValueError("at most three independent tool calls are allowed per turn")
            actions: list[ResearchAction] = []
            calls: list[ResearchToolCallV1] = []
            deferred_moves: list[str] = []
            chosen_action: ResearchAction | None = None
            for index, raw_call in enumerate(raw_tool_calls):
                if not isinstance(raw_call, dict):
                    raise ValueError("each tool call must be an object")
                tool_name = str(raw_call.get("tool_name") or "").strip()
                if not tool_name:
                    arguments = raw_call.get("arguments") if isinstance(raw_call.get("arguments"), dict) else {}
                    tool_name = infer_research_tool_name_from_arguments(arguments)
                    if tool_name:
                        raw_call = {**raw_call, "tool_name": tool_name}
                if tool_name not in self._ready_tools or tool_name not in _MODEL_TOOL_TO_ACTION:
                    raise ValueError(f"tool is not model-visible and ready: {tool_name}")
                call_action = _MODEL_TOOL_TO_ACTION[tool_name]
                if call_action not in context.allowed_actions:
                    raise ValueError(f"action {call_action} is not currently allowed")
                if chosen_action is None:
                    chosen_action = call_action
                if call_action != chosen_action:
                    deferred_moves.append(tool_name)
                    continue
                actions.append(call_action)
                calls.append(
                    self._build_model_tool_call(
                        context=context,
                        raw_call=raw_call,
                        index=index,
                        goal=goal,
                    )
                )
            if not calls:
                raise ValueError("research proposal must include at least one tool call")
            if len({call.tool_call_id for call in calls}) != len(calls):
                raise ValueError("parallel tool calls must have distinct tool+arguments signatures")
            if deferred_moves:
                rationale = (
                    rationale
                    + " Deferred later research moves until a later turn: "
                    + ", ".join(deferred_moves)
                    + "."
                ).strip()
            action = actions[0]
            tool_calls = tuple(calls)

        if not goal:
            goal = tool_calls[0].goal if tool_calls else self._fallback._goal_for(action, context)
        if not rationale:
            rationale = f"llm_repository_research:{action}"
        if not expected_gain:
            expected_gain = self._fallback._expected_gain(action, context)
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

    def _build_model_tool_call(
        self,
        *,
        context: ResearchDecisionContextV1,
        raw_call: dict[str, Any],
        index: int,
        goal: str,
    ) -> ResearchToolCallV1:
        """Validate one LLM-selected tool call against its Pydantic schema."""

        from code2paper.agentic.research_tools import RESEARCH_TOOL_INPUT_SCHEMAS

        tool_name = str(raw_call.get("tool_name") or "").strip()
        obligation_id = (
            context.active_obligation.obligation_id
            if context.active_obligation
            else ""
        )
        if not obligation_id:
            raise ValueError("tool proposal has no active obligation")
        arguments = raw_call.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        lifted = lift_harness_fields_from_tool_arguments(
            {**raw_call, "arguments": dict(arguments)}
        )
        arguments = lifted.get("arguments") if isinstance(lifted.get("arguments"), dict) else {}
        forbidden_common = set(arguments).intersection(_COMMON_TOOL_INPUT_FIELDS)
        if forbidden_common:
            raise ValueError(
                "tool arguments cannot override harness-owned fields: "
                + ",".join(sorted(forbidden_common))
            )
        if "source_authority" in arguments:
            raise ValueError("tool arguments cannot set source authority")
        path_scope = lifted.get("path_scope") or raw_call.get("path_scope") or []
        if not isinstance(path_scope, list) or not all(
            isinstance(item, str) for item in path_scope
        ):
            raise ValueError("path_scope must be an array of paths")

        call_goal = str(lifted.get("goal") or raw_call.get("goal") or goal or "").strip()
        if not call_goal:
            call_goal = f"answer {obligation_id} with {tool_name}"
        top_k = max(0, min(int(lifted.get("top_k") or raw_call.get("top_k") or 0), 50))
        depth = max(0, min(int(lifted.get("depth") or raw_call.get("depth") or 0), 4))
        node_budget = max(0, min(int(lifted.get("node_budget") or raw_call.get("node_budget") or 0), 96))
        # Stable execution signature: the same concrete call in a later turn
        # must remain visible to the no-repeat policy instead of receiving a
        # fresh id merely because its turn or batch position changed.
        material = json.dumps(
            {
                "run": self._run_id,
                "tool": tool_name,
                "obligation": obligation_id,
                "arguments": arguments,
                "path_scope": sorted(path_scope),
                "top_k": top_k,
                "depth": depth,
                "node_budget": node_budget,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        tool_call_id = "tc-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]

        schema = RESEARCH_TOOL_INPUT_SCHEMAS[tool_name]
        arguments = sanitize_model_tool_arguments(tool_name, arguments)
        validated = schema.model_validate(
            {
                **arguments,
                "tool_call_id": tool_call_id,
                "obligation_id": obligation_id,
                "goal": call_goal,
                "repo_snapshot_id": self._repo_snapshot_id,
                "path_scope": path_scope,
                "top_k": top_k,
                "depth": depth,
                "node_budget": node_budget,
            }
        ).model_dump(mode="json")
        tool_arguments = {
            key: value
            for key, value in validated.items()
            if key not in _COMMON_TOOL_INPUT_FIELDS
        }
        return ResearchToolCallV1(
            tool_call_id=validated["tool_call_id"],
            tool_name=tool_name,
            tool_kind=_tool_kind_for(tool_name),
            obligation_id=obligation_id,
            goal=validated["goal"],
            repo_snapshot_id=self._repo_snapshot_id,
            path_scope=tuple(validated["path_scope"]),
            top_k=int(validated["top_k"]),
            depth=int(validated["depth"]),
            node_budget=int(validated["node_budget"]),
            arguments=tool_arguments,
        )

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
    "You are the repository Research Manager for Code2Paper. Your job is to "
    "study the implementation until you can answer the active author-facing "
    "method question with concrete code evidence. You receive a bounded "
    "workspace containing the question, prior search results, exact candidates, "
    "and source excerpts.\n\n"
    "Working method:\n"
    "- Select the concrete repository tool and its arguments yourself.\n"
    "- Treat active_obligation.author_question as the research goal. Preserve "
    "its named components, dimensions, numeric constraints, formulas, and "
    "stage semantics when constructing queries. Generic role labels are only "
    "fallbacks.\n"
    "- After search, read the most relevant exact candidate. After reading, "
    "trace callers/data/control/config only when needed to explain the method.\n"
    "- Change query, symbol, path, or trace direction when a call makes no progress.\n"
    "- Inspect executed_tool_calls before acting. Never repeat the same tool "
    "with the same arguments. Use current_compiled_evidence to distinguish "
    "what the repository has already established from the exact remaining "
    "question.\n"
    "- forbidden_exact_reads lists every read_symbol/read_code_span already "
    "executed anywhere in this snapshot, including reads done for another "
    "obligation. Those exact reads return the same bytes and are rejected by "
    "policy as duplicate no-gain calls. Never propose them again: trace a "
    "caller/data/control/config relation, inspect a branch or configuration, "
    "or read a different span instead. The same applies after a rejection: "
    "policy_feedback explains why, and a repair must pick a materially "
    "different action, never STOP_BLOCKED for a merely rejected proposal.\n"
    "- Prefer one call. You may request 2-3 independent calls of the same move "
    "when comparing candidates is genuinely useful. All tool_calls in one "
    "response MUST belong to the same research move (all reads, or all "
    "searches, or all traces). Never mix read_symbol with search_symbols or "
    "different tool kinds in one response; a mixed-move response is rejected "
    "and replaced by a deterministic fallback.\n"
    "- When the excerpts and traces contain evidence for one or more material "
    "parts of the active question, return COMPILE_EVIDENCE. The compiler can "
    "retain a typed partial result and expose the exact remainder for another "
    "search round; do not wait for every broad author detail to be proven in one "
    "symbol. This hands the current "
    "notebook to the deterministic evidence compiler; do not keep reading and "
    "do not use STOP_BLOCKED for a successfully researched question.\n"
    "- Use RECORD_GAP only after bounded searches really found no owner. Use "
    "STOP_BLOCKED only for an unrecoverable infrastructure or protocol failure.\n"
    "- terminal_action and tool_calls are mutually exclusive: when "
    "terminal_action is COMPILE_EVIDENCE, RECORD_GAP, or STOP_BLOCKED, "
    "tool_calls MUST be an empty array. When you choose tool calls, "
    "terminal_action MUST be empty. A response that combines both is "
    "rejected and replaced by a deterministic fallback.\n\n"
    "Hard constraints:\n"
    "- Use only ready_tools and each tool's documented arguments.\n"
    "- For read/trace calls, copy exact paths and symbols from candidates or "
    "observations. Search queries may be newly derived from the author question.\n"
    "- Never invent span IDs or evidence IDs. Never set source authority.\n"
    "- Code evidence decides what may be claimed; you only decide what to "
    "search/trace/inspect next.\n"
    "- A max-turn or budget boundary is incomplete, never successful.\n\n"
    "Keep rationale, goal, and expected_information_gain short.\n\n"
    "Return ONLY a JSON object with this schema:\n"
    '{\n'
    '  "tool_calls": [{"tool_name": "<ready tool>", "arguments": {}, '
    '"path_scope": [], "top_k": 0, "depth": 0, "node_budget": 0, '
    '"goal": "<specific question>"}],\n'
    '  "terminal_action": "<empty, COMPILE_EVIDENCE, RECORD_GAP, or STOP_BLOCKED>",\n'
    '  "rationale": "<brief reason for this action>",\n'
    '  "goal": "<what this action should achieve>",\n'
    '  "expected_information_gain": "<what new information this should produce>"\n'
    '}\n'
)


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tool_calls": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "enum": list(_MODEL_TOOL_TO_ACTION),
                    },
                    "arguments": {"type": "object", "additionalProperties": True},
                    "path_scope": {"type": "array", "items": {"type": "string"}},
                    "top_k": {"type": "integer", "minimum": 0, "maximum": 50},
                    "depth": {"type": "integer", "minimum": 0, "maximum": 4},
                    "node_budget": {"type": "integer", "minimum": 0, "maximum": 96},
                    "goal": {"type": "string", "maxLength": 240},
                },
                "required": ["tool_name", "arguments"],
                "additionalProperties": False,
            },
        },
        "terminal_action": {
            "type": "string",
            "enum": ["", "COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"],
        },
        "rationale": {
            "type": "string",
            "maxLength": 240,
            "description": "Brief reason for choosing this action.",
        },
        "goal": {
            "type": "string",
            "maxLength": 240,
            "description": "What this action should achieve.",
        },
        "expected_information_gain": {
            "type": "string",
            "maxLength": 180,
            "description": "What new information this action should produce.",
        },
    },
    "required": ["tool_calls", "terminal_action", "rationale", "goal"],
    "additionalProperties": False,
}


def _response_schema_for_tools(ready_tools: list[str]) -> dict[str, Any]:
    """Bind guided decoding to tools the current runtime can execute.

    ``arguments`` is constrained per tool to the exact Pydantic input
    schema (minus harness-owned fields).  Without the constraint the model
    invents fields such as ``regex`` on ``search_code``, which the strict
    tool validator rejects and turns an otherwise sound LLM decision into a
    deterministic fallback.
    """

    from code2paper.agentic.research_tools import RESEARCH_TOOL_INPUT_SCHEMAS

    schema = json.loads(json.dumps(_RESPONSE_SCHEMA))
    visible = [name for name in ready_tools if name in _MODEL_TOOL_TO_ACTION]
    if visible:
        schema["properties"]["tool_calls"]["items"]["properties"][
            "tool_name"
        ]["enum"] = visible
    # One ``if/then`` branch per visible tool: when tool_name is X, the
    # arguments object must match X's input schema.  Unknown/extra fields
    # are rejected by guided decoding before the harness validator runs.
    branches = []
    for tool_name in visible:
        tool_schema = RESEARCH_TOOL_INPUT_SCHEMAS.get(tool_name)
        if tool_schema is None:
            continue
        args_schema = json.loads(json.dumps(tool_schema.model_json_schema()))
        properties = {
            key: value
            for key, value in (args_schema.get("properties") or {}).items()
            if key not in _COMMON_TOOL_INPUT_FIELDS
            and key != "source_authority"
        }
        required = [
            key
            for key in (args_schema.get("required") or [])
            if key not in _COMMON_TOOL_INPUT_FIELDS
            and key != "source_authority"
        ]
        branches.append({
            "if": {
                "properties": {
                    "tool_name": {"const": tool_name},
                },
            },
            "then": {
                "properties": {
                    "arguments": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            },
        })
    items_schema = schema["properties"]["tool_calls"]["items"]
    if branches:
        items_schema["allOf"] = branches
    return schema


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

    has_new_contract = isinstance(proposal.get("tool_calls"), list) and isinstance(
        proposal.get("terminal_action"), str
    )
    action = proposal.get("action", "")
    has_legacy_terminal = isinstance(action, str) and action in {
        "RECORD_GAP",
        "STOP_BLOCKED",
    }
    has_legacy_tool_action = isinstance(action, str) and action in _TOOL_CALLING_ACTIONS
    if not (has_new_contract or has_legacy_terminal or has_legacy_tool_action):
        if not isinstance(action, str) or not action.strip():
            raise ValueError("missing or empty 'action'")
        raise ValueError("response has neither tool_calls nor a terminal action")

    return proposal


def _validate_proposal_shape(proposal: dict[str, Any]) -> None:
    """Require either concrete tool calls or one explicit terminal move."""

    has_new_contract = isinstance(proposal.get("tool_calls"), list) and (
        bool(proposal.get("tool_calls"))
        or str(proposal.get("terminal_action") or "") in {
            "COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"
        }
    )
    action = str(proposal.get("action") or "")
    if not (
        has_new_contract
        or action in {"COMPILE_EVIDENCE", "RECORD_GAP", "STOP_BLOCKED"}
        or action in _TOOL_CALLING_ACTIONS
    ):
        raise ValueError("response has neither tool_calls nor a terminal action")
