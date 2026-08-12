"""Section-based Method writer (Phase 1 R8 writer protocol).

Implements the writer role's per-section generation protocol:

- Each Method section is a separate LLM call tagged
  ``role="method_writer"``.
- Per-call default budget is 8192 tokens
  (:func:`role_config.writer_default_budget`).
- When a section call returns ``finish_reason == "length"``, the call
  is retried once with the extended budget (12288 tokens).
- When a publication section response fails schema validation or
  closed-set binding (``publication_section_schema_failed:*`` /
  ``publication_section_binding_failed:*``) and the cumulative budget
  allows it, the same Method Writer owner receives exactly one bounded
  retry carrying the parse error and the original closed
  binding/grounding contract.  The rule layer never synthesizes
  replacement prose; a second failure keeps the section a credible
  incomplete.  This owner repair is part of the D4/D5 structured-output
  recovery contract.
- The cumulative output token budget across all section calls is
  capped (``writer_cumulative_budget`` for legacy inputs, or a dynamic
  Architect-derived budget for publication inputs).  Once the cap is
  reached, no further section calls are made.  Legacy (non-publication)
  sections are then filled with a deterministic scaffold placeholder so
  the writer produces a contiguous Method draft; publication sections
  are left incomplete without placeholder prose.
- Each call emits a :class:`GenerationCallTrace` for R8 acceptance
  evidence (role, effective config, finish reason, token usage,
  cumulative budget consumed).

This module is the authoritative writer protocol implementation.  The
legacy phase5 authoring path can opt into section-based generation by
calling :func:`write_method_by_sections` instead of issuing a single
``METHOD_DRAFT_SCHEMA`` call.

Hard rules:

- ``finish_reason == "length"`` triggers the one extended-budget
  escalation.  Typed publication schema/binding failures trigger the
  one bounded owner repair described above; other blocked reasons
  (e.g. ``"content_filter"``, transport errors) never escalate here.
- The cumulative budget is measured in *output* tokens (sum of
  ``completion_tokens`` reported by the provider).  When the provider
  does not report token usage, we fall back to the deterministic
  raw-text estimate (:func:`_estimated_output_tokens`): zero only for
  empty text, otherwise at least one token (``max(1, len(text) // 4)``),
  so every non-empty model call — including a schema/binding-failed
  response whose invalid text is cleared — is charged against the cap.
- A section whose LLM call is blocked (``blocked_reason`` non-empty)
  is not retried by this module unless it is a typed publication
  schema/binding failure (one owner retry); transport-level retry is
  the LLM client's job.  In publication mode the blocked section stays
  incomplete with its failure visible; in legacy mode it receives the
  deterministic placeholder.
"""

from __future__ import annotations

import logging
import copy
import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
from code2paper.llm.generation_trace import GenerationCallTrace, build_generation_call_trace
from code2paper.llm.role_config import (
    METHOD_WRITER,
    apply_role_config,
    writer_cumulative_budget,
)
from code2paper.authoring.writer_skill import PublicationMethodWriterSkillV1
from code2paper.llm.response_schemas import (
    PUBLICATION_METHOD_SECTION_SCHEMA,
    PublicationMethodSectionOutputV1,
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.schemas import LLMConfig

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WriterSectionInput:
    """A single section to be rendered by the writer.

    ``section_id`` is a stable identifier (used in the trace ``call_id``).
    ``heading`` is the section heading (e.g., ``"Overview"``).
    ``prompt_payload`` is the per-section input payload (already
    projected from the authoring plan / evidence / claim map).
    ``system_prompt`` is the per-section system prompt; when empty,
    :func:`write_method_by_sections` uses :func:`default_section_system_prompt`.
    """

    section_id: str
    heading: str
    prompt_payload: dict[str, Any]
    system_prompt: str = ""
    publication_mode: bool = False
    argument_graph: dict[str, Any] = field(default_factory=dict)


@dataclass
class WriterSectionResult:
    """Result of generating a single section."""

    section_id: str
    heading: str
    text: str
    finish_reason: str
    extended_budget_used: bool
    blocked_reason: str = ""
    trace: GenerationCallTrace | None = None
    incomplete: bool = False
    new_research_requests: list[dict[str, Any]] = field(default_factory=list)
    self_identified_risks: list[str] = field(default_factory=list)


@dataclass
class WriterAggregateResult:
    """Aggregate result of a section-based writer run."""

    sections: list[WriterSectionResult] = field(default_factory=list)
    traces: list[GenerationCallTrace] = field(default_factory=list)
    cumulative_budget_consumed: int = 0
    cumulative_budget_cap: int = 0
    cumulative_budget_exhausted: bool = False
    concatenated_markdown: str = ""
    incomplete_sections: list[str] = field(default_factory=list)
    research_requests: list[dict[str, Any]] = field(default_factory=list)
    response_recovery_traces: list[dict[str, Any]] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "sections": [
                {
                    "section_id": s.section_id,
                    "heading": s.heading,
                    "text_length": len(s.text),
                    "finish_reason": s.finish_reason,
                    "extended_budget_used": s.extended_budget_used,
                    "blocked_reason": s.blocked_reason,
                }
                for s in self.sections
            ],
            "traces": [t.to_json_dict() for t in self.traces],
            "cumulative_budget_consumed": self.cumulative_budget_consumed,
            "cumulative_budget_cap": self.cumulative_budget_cap,
            "cumulative_budget_exhausted": self.cumulative_budget_exhausted,
            "concatenated_markdown_length": len(self.concatenated_markdown),
            "incomplete_sections": list(self.incomplete_sections),
            "research_request_count": len(self.research_requests),
            "response_recovery_traces": list(self.response_recovery_traces),
        }


# ---------------------------------------------------------------------------
# LLM client protocol (for testability)
# ---------------------------------------------------------------------------


class _LLMCaller(Protocol):
    """Callable signature for the LLM complete function."""

    def __call__(self, config: LLMConfig, request: LLMRequest) -> LLMResponse: ...


def _default_llm_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
    mode = os.environ.get("CODE2PAPER_LLM_PUBLICATION_WRITER_RESPONSE_MODE", "").strip()
    if request.schema_name == PUBLICATION_METHOD_SECTION_SCHEMA and mode:
        try:
            response_mode = StructuredResponseMode(mode)
        except ValueError:
            response_mode = StructuredResponseMode.NATIVE_JSON_SCHEMA
        profile = load_capability_profile(
            provider=getattr(config.provider, "value", str(config.provider)),
            model=config.model,
        ).model_copy(update={"response_mode": response_mode})
        return LLMClient(config, capability_profile=profile).complete(request)
    return LLMClient(config).complete(request)


# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------


def default_section_system_prompt() -> str:
    """Return the default per-section system prompt for the method writer.

    The prompt instructs the model to render a single Method section
    from the provided projection payload, without inventing evidence
    or reintroducing unsupported claims.
    """

    return PublicationMethodWriterSkillV1().system_prompt()


# ---------------------------------------------------------------------------
# Budget tracking
# ---------------------------------------------------------------------------


def _estimated_output_tokens(text: str | None) -> int:
    """Deterministic raw-text output-token estimate.

    Returns ``0`` only for empty text and at least ``1`` for every non-empty
    response so that any model call that produced bytes is charged against
    the cumulative budget (plan §3.2.4: every generated token is counted).
    A one-to-three character response (for example the schema-failed body
    ``{}``) must never consume zero budget, otherwise an owner retry could be
    authorized after the real budget is exhausted.
    """

    text = text or ""
    return 0 if not text else max(1, len(text) // 4)


def _output_tokens_used(response: LLMResponse) -> int:
    """Return the number of output tokens consumed by a call.

    Falls back to the deterministic raw-text estimate
    (:func:`_estimated_output_tokens`) when the provider did not report
    token usage, so the cumulative cap is still enforced and every
    non-empty response is charged at least one token.
    """

    usage = response.token_usage or {}
    for key in ("completion_tokens", "output_tokens", "generated_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return _estimated_output_tokens(response.text)


def _failed_response_token_usage(response: LLMResponse) -> dict[str, int]:
    """Carry budget accounting from a raw response whose invalid
    schema/binding text is about to be cleared.

    A publication call may generate non-empty output that fails schema or
    binding validation.  The harness clears that text (it must never be
    exposed as prose) but must still count the generated tokens toward the
    cumulative budget (plan §3.2.4: both calls are traced and every
    generated token is counted).  When the provider reported usage, it is
    preserved verbatim; otherwise the same deterministic raw-text estimate
    used by ordinary output accounting (:func:`_estimated_output_tokens`)
    is synthesized so the failed call contributes a nonzero, monotonic
    budget delta instead of silently consuming zero.
    """

    usage = response.token_usage or {}
    for key in ("completion_tokens", "output_tokens", "generated_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value > 0:
            return usage
    return {"completion_tokens": _estimated_output_tokens(response.text)}


def dynamic_writer_cumulative_budget(
    sections: Iterable[WriterSectionInput],
    *,
    global_cap: int | None = None,
) -> int:
    """Derive a run budget from the Architect's information plan.

    Legacy section inputs do not carry an argument graph, so they retain the
    historical global cap.  Publication inputs with a graph are budgeted from
    supported units, formalization/configuration load, and planned paragraphs;
    the result can never exceed the audited role cap.
    """

    normalized = list(sections)
    cap = global_cap or writer_cumulative_budget()
    if not normalized or not any(section.argument_graph for section in normalized):
        return cap
    total = 0
    for section in normalized:
        graph = section.argument_graph or {}
        payload = section.prompt_payload or {}
        unit_count = len(graph.get("argument_unit_ids") or payload.get("argument_units") or ())
        equation_count = len(payload.get("equations") or payload.get("equation_ids") or ())
        configuration_count = len(
            payload.get("configurations") or payload.get("configuration_ids") or ()
        )
        paragraph_count = sum(
            max(0, int(move.get("paragraph_budget") or 0))
            for move in (graph.get("moves") or ())
            if isinstance(move, dict)
        )
        section_budget = (
            1024
            + 768 * max(1, unit_count)
            + 512 * equation_count
            + 384 * configuration_count
            + 512 * max(1, paragraph_count)
        )
        total += max(2048, section_budget)
    retry_floor = 8192 * len(normalized) + 4096
    return min(cap, max(2048, total, retry_floor))


# ---------------------------------------------------------------------------
# Section-based writer
# ---------------------------------------------------------------------------


def write_method_by_sections(
    base_config: LLMConfig,
    sections: Iterable[WriterSectionInput],
    *,
    llm_caller: _LLMCaller | None = None,
    call_id_prefix: str = "LLM-writer-section",
    schema_name: str = "DraftMarkdownOutput",
    response_json_schema: dict[str, Any] | None = None,
    publication_mode: bool = False,
) -> WriterAggregateResult:
    """Render a Method document by calling the writer once per section.

    See module docstring for the writer protocol (default 8192 budget,
    extended 12288 on ``finish_reason="length"``, cumulative 24576 cap).

    ``base_config`` is the base LLM config; per-call configs are
    derived by :func:`apply_role_config` with ``role="method_writer"``.
    The base config's ``role`` field is overwritten to
    ``"method_writer"`` on every call.

    ``llm_caller`` is injectable for testing; the default constructs a
    fresh :class:`LLMClient` per call.

    Returns a :class:`WriterAggregateResult` with the concatenated
    Markdown, per-section traces, and cumulative budget accounting.
    """

    caller = llm_caller or _default_llm_caller
    normalized_sections = list(sections)
    cap = dynamic_writer_cumulative_budget(normalized_sections)

    result = WriterAggregateResult(cumulative_budget_cap=cap)
    rendered_sections: list[str] = []

    for index, section in enumerate(normalized_sections):
        # Stop issuing LLM calls once the cumulative budget is exhausted.
        if result.cumulative_budget_consumed >= cap:
            result.cumulative_budget_exhausted = True
            publication_section = publication_mode or section.publication_mode
            placeholder = "" if publication_section else _placeholder_section(section, reason="cumulative_budget_exhausted")
            if placeholder:
                rendered_sections.append(placeholder)
            result.sections.append(
                WriterSectionResult(
                    section_id=section.section_id,
                    heading=section.heading,
                    text=placeholder,
                    finish_reason="skipped_cumulative_budget_exhausted",
                    extended_budget_used=False,
                    incomplete=True,
                )
            )
            result.incomplete_sections.append(section.section_id)
            continue

        system_prompt = section.system_prompt or default_section_system_prompt()
        section_schema = _closed_set_publication_schema(
            response_json_schema,
            section=section,
        )
        request = LLMRequest(
            prompt_template_id=f"phase5_method_writer_section_v1",
            prompt=system_prompt,
            input_payload={
                **section.prompt_payload,
                "argument_graph": section.argument_graph,
            },
            schema_name=schema_name,
            response_json_schema=section_schema,
        )

        # First attempt: default budget.
        call_config = apply_role_config(
            base_config, METHOD_WRITER, extended_writer_budget=False
        )
        call_config = call_config.model_copy(
            update={
                "max_output_tokens": min(
                    call_config.max_output_tokens,
                    cap - result.cumulative_budget_consumed,
                )
            }
        )
        call_id = f"{call_id_prefix}-{index}-{section.section_id}"
        response = _safe_call(caller, call_config, request)
        extended_used = False

        # Emit a trace for the default-budget call.  R8 protocol
        # requires "each call records effective sampling config"; even
        # when the call is later superseded by an extended-budget
        # retry, the default-budget call still happened and must be
        # evidenced in the trace list.
        default_used = _output_tokens_used(response)
        default_cumulative = min(cap, result.cumulative_budget_consumed + default_used)
        default_trace = build_generation_call_trace(
            call_id=call_id,
            config=call_config,
            request=request,
            response=response,
            extended_budget_used=False,
            cumulative_budget_consumed=default_cumulative,
        )
        result.traces.append(default_trace)
        accepted_trace: GenerationCallTrace = default_trace
        accepted_response = response
        # Cumulative budget always counts every token the LLM
        # generated, regardless of whether the response was accepted
        # -- the GPU spent those tokens either way.
        result.cumulative_budget_consumed = default_cumulative

        # Escalate only on finish_reason == "length".
        if (
            response.finish_reason == "length"
            and (
                not response.blocked_reason
                or response.blocked_reason.startswith("publication_section_schema_failed:")
                or response.blocked_reason.startswith("publication_section_binding_failed:")
            )
            and result.cumulative_budget_consumed < cap
        ):
            extended_config = apply_role_config(
                base_config, METHOD_WRITER, extended_writer_budget=True
            )
            extended_config = extended_config.model_copy(
                update={
                    "max_output_tokens": min(
                        extended_config.max_output_tokens,
                        cap - result.cumulative_budget_consumed,
                    )
                }
            )
            extended_call_id = f"{call_id_prefix}-{index}-{section.section_id}-ext"
            extended_response = _safe_call(caller, extended_config, request)
            extended_token_used = _output_tokens_used(extended_response)
            extended_cumulative = min(
                cap, result.cumulative_budget_consumed + extended_token_used
            )
            extended_trace = build_generation_call_trace(
                call_id=extended_call_id,
                config=extended_config,
                request=request,
                response=extended_response,
                extended_budget_used=True,
                cumulative_budget_consumed=extended_cumulative,
            )
            result.traces.append(extended_trace)
            # The extended call's tokens always count toward the
            # cumulative budget (the GPU spent them).
            result.cumulative_budget_consumed = extended_cumulative
            # Only accept the extended response if it actually produced
            # more content than the truncated default response.
            if len(extended_response.text or "") > len(response.text or ""):
                accepted_response = extended_response
                accepted_trace = extended_trace
                extended_used = True

        # Owner retry on schema/binding failure.  The LLM returned content
        # but it failed schema validation or binding (e.g. an empty JSON
        # object ``{}`` or missing required fields).  Give the owning Agent
        # one bounded retry carrying the parse error and the original
        # contract, so it can regenerate a compliant response.  The rule
        # layer never synthesizes replacement prose — only the owning Agent
        # may produce text.  A second failure keeps the section a credible
        # incomplete.
        # Any non-``length`` finish reason (``stop``, ``structured_complete``,
        # or an empty reason from a blocked transport) may carry a typed
        # schema/binding failure.  Requiring ``== "stop"`` excluded the
        # streaming client's ``structured_complete`` responses, so a live
        # schema failure never reached the owning Agent.  ``length`` is
        # excluded: it already consumed the extended-budget repair path
        # above, and the plan keeps a single bounded repair allowance per
        # section.
        elif (
            accepted_response.finish_reason != "length"
            and accepted_response.blocked_reason
            and (
                accepted_response.blocked_reason.startswith("publication_section_schema_failed:")
                or accepted_response.blocked_reason.startswith("publication_section_binding_failed:")
            )
            and result.cumulative_budget_consumed < cap
        ):
            retry_config = apply_role_config(
                base_config, METHOD_WRITER, extended_writer_budget=False
            )
            retry_config = retry_config.model_copy(
                update={
                    "max_output_tokens": min(
                        retry_config.max_output_tokens,
                        cap - result.cumulative_budget_consumed,
                    )
                }
            )
            # Carry the parse error in the retry payload alongside the
            # original contract so the owning Agent sees which constraint
            # it violated on the first attempt.
            retry_input_payload = dict(request.input_payload or {})
            retry_input_payload["previous_attempt_error"] = accepted_response.blocked_reason
            retry_request = LLMRequest(
                prompt_template_id=request.prompt_template_id,
                prompt=request.prompt,
                input_payload=retry_input_payload,
                schema_name=request.schema_name,
                response_json_schema=request.response_json_schema,
            )
            retry_call_id = f"{call_id_prefix}-{index}-{section.section_id}-retry"
            retry_response = _safe_call(caller, retry_config, retry_request)
            retry_token_used = _output_tokens_used(retry_response)
            retry_cumulative = min(
                cap, result.cumulative_budget_consumed + retry_token_used
            )
            retry_trace = build_generation_call_trace(
                call_id=retry_call_id,
                config=retry_config,
                request=retry_request,
                response=retry_response,
                extended_budget_used=False,
                cumulative_budget_consumed=retry_cumulative,
            )
            result.traces.append(retry_trace)
            result.cumulative_budget_consumed = retry_cumulative
            # Accept the retry only if it resolved the schema/binding
            # failure.  Otherwise keep the original incomplete response
            # (fail-closed; the rule layer does not patch prose).
            if not retry_response.blocked_reason and (retry_response.text or "").strip():
                accepted_response = retry_response
                accepted_trace = retry_trace

        publication_section = publication_mode or section.publication_mode
        section_text = accepted_response.text or (
            "" if publication_section else _placeholder_section(section, reason="empty_response")
        )
        if section_text:
            rendered_sections.append(section_text)
        incomplete = not bool(section_text.strip()) or bool(accepted_response.blocked_reason)
        result.sections.append(
            WriterSectionResult(
                section_id=section.section_id,
                heading=section.heading,
                text=section_text,
                finish_reason=accepted_response.finish_reason,
                extended_budget_used=extended_used,
                blocked_reason=accepted_response.blocked_reason,
                trace=accepted_trace,
                incomplete=incomplete,
            )
        )
        if incomplete:
            result.incomplete_sections.append(section.section_id)

        if result.cumulative_budget_consumed >= cap:
            result.cumulative_budget_exhausted = True

    result.concatenated_markdown = "\n\n".join(rendered_sections)
    return result


def _closed_set_publication_schema(
    base_schema: dict[str, Any] | None,
    *,
    section: WriterSectionInput,
) -> dict[str, Any] | None:
    """Bind publication response identifiers to the section's exact sets.

    Prompt prose is not a closed-set contract: a model can copy a claim id
    into an equation-looking id or invent a local equation label.  Native
    structured decoding should prevent that representation error before the
    response reaches the authorship gate.  Non-publication/legacy schemas are
    left unchanged.
    """

    if not base_schema or not section.publication_mode:
        return base_schema
    contract = section.prompt_payload.get("binding_contract")
    if not isinstance(contract, dict):
        return base_schema
    grounding = section.prompt_payload.get("grounding_contract")
    callback_required = bool(
        isinstance(grounding, dict) and grounding.get("callback_required")
    )
    schema = copy.deepcopy(base_schema)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return base_schema
    section_property = properties.get("section_id")
    if isinstance(section_property, dict):
        section_property["const"] = section.section_id
    paragraph_budget = sum(
        max(0, int(move.get("paragraph_budget") or 0))
        for move in (section.argument_graph.get("moves") or ())
        if isinstance(move, dict)
    )
    unit_count = len(section.argument_graph.get("argument_unit_ids") or ())
    markdown_property = properties.get("section_markdown")
    if isinstance(markdown_property, dict):
        max_length = min(
            16000,
            max(2400, 1200 * max(1, paragraph_budget) + 400 * max(1, unit_count)),
        )
        markdown_property["minLength"] = min(
            max_length,
            max(800, 300 * max(1, paragraph_budget) + 200 * max(1, unit_count)),
        )
        markdown_property["maxLength"] = max_length
    # Content-first binding contract: the Writer is never forced to complete
    # every id/move.  Each closed set is an ``enum`` array (bounded by the
    # set size) so unknown ids are rejected by structured decoding while
    # subsets are always legal; post-processing binds prose to facts.
    binding_fields = (
        "used_argument_unit_ids",
        "used_claim_ids",
        "used_equation_ids",
        "used_configuration_ids",
    )
    for field in binding_fields:
        values = list(dict.fromkeys(str(value) for value in contract.get(field, ())))
        # An empty ``enum`` array is fatal to xgrammar guided decoding
        # (json_schema_converter.cc rejects it and the engine dies).
        # When the closed set is empty the item type alone is the
        # contract; the harness binding gate still enforces exactness.
        properties[field] = {
            "type": "array",
            "items": (
                {"type": "string"}
                if not values
                else {"type": "string", "enum": values}
            ),
            "maxItems": len(values) if values else 16,
            "uniqueItems": True,
        }
    required_moves = list(dict.fromkeys(
        str(value) for value in contract.get("completed_rhetorical_moves", ())
    ))
    anchored_moves = list(dict.fromkeys(
        str(value)
        for value in contract.get("anchored_required_rhetorical_moves", required_moves)
    ))
    move_schema = properties.get("completed_rhetorical_moves")
    if isinstance(move_schema, dict):
        properties["completed_rhetorical_moves"] = {
            "type": "array",
            "items": (
                {"type": "string"}
                if not anchored_moves
                else {"type": "string", "enum": anchored_moves}
            ),
            "maxItems": len(anchored_moves) if anchored_moves else 16,
            "uniqueItems": True,
        }
    ordered_names = (
        "section_id",
        "used_argument_unit_ids",
        "used_claim_ids",
        "used_equation_ids",
        "used_configuration_ids",
        "completed_rhetorical_moves",
        "new_research_requests",
        "self_identified_risks",
        "unresolved_points",
        "section_markdown",
    )
    schema["properties"] = {
        name: properties[name]
        for name in ordered_names
        if name in properties
    }
    return schema


@dataclass
class PublicationWriterResult:
    """Publication-mode writer result with structured callback requests."""

    aggregate: WriterAggregateResult
    outputs: list[PublicationMethodSectionOutputV1] = field(default_factory=list)

    @property
    def incomplete_sections(self) -> list[str]:
        return list(self.aggregate.incomplete_sections)


def write_publication_method_by_sections(
    base_config: LLMConfig,
    sections: Iterable[WriterSectionInput],
    *,
    llm_caller: _LLMCaller | None = None,
    call_id_prefix: str = "LLM-publication-method-section",
) -> PublicationWriterResult:
    """Run the content-first publication Writer contract.

    A malformed structured response becomes an incomplete section.  The
    harness never fills it with deterministic prose and never converts the
    model's ids into substitute text.
    """

    caller = llm_caller or _default_llm_caller
    # A ``finish_reason=length`` call may be followed by an extended retry.
    # Keep every parsed attempt long enough to match it to the response that
    # the section protocol ultimately accepts; exposing both attempts would
    # duplicate callback metadata and let a discarded short response affect
    # the aggregate.
    parsed_outputs_by_section: dict[str, list[PublicationMethodSectionOutputV1]] = {}
    recovery_traces: list[dict[str, Any]] = []

    def structured_caller(config: LLMConfig, request: LLMRequest) -> LLMResponse:
        response = caller(config, request)
        if response.blocked_reason or not (response.text or "").strip():
            # Preserve the owning client/provider failure. Attempting JSON
            # recovery on an empty blocked response hides the actionable
            # cause behind a secondary schema-parse error.
            return response
        normalized_text, bridged_fields = _decode_publication_binding_tokens(
            response.text,
            request.input_payload.get("binding_contract") or {},
        )
        normalized_text, research_bridge_fields = _decode_publication_research_requests(
            normalized_text,
            section_id=str(request.input_payload.get("section_id") or ""),
            argument_graph=request.input_payload.get("argument_graph") or {},
        )
        normalized_text, callback_bridge_fields = _decode_publication_callback_moves(
            normalized_text,
            resolution=request.input_payload.get(
                "writing_research_callback_resolution"
            ) or {},
        )
        parsed, recovery, error = try_parse_structured_response_with_trace(
            normalized_text,
            PublicationMethodSectionOutputV1,
        )
        recovery_traces.append({
            "section_id": str(request.input_payload.get("section_id") or ""),
            "binding_bridge_fields": bridged_fields,
            "research_request_bridge_fields": research_bridge_fields,
            "callback_move_bridge_fields": callback_bridge_fields,
            **recovery.model_dump(mode="json"),
        })
        if parsed is None:
            return LLMResponse(
                text="",
                response_hash=response.response_hash,
                blocked_reason=f"publication_section_schema_failed:{error}",
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
            )
        section_id = str(request.input_payload.get("section_id") or parsed.section_id or "")
        grounding_contract = request.input_payload.get("grounding_contract") or {}
        contract_failures = _publication_contract_failures(
            parsed,
            expected_section_id=section_id,
            contract=request.input_payload.get("binding_contract") or {},
            allow_subset=bool(
                isinstance(grounding_contract, dict)
                and grounding_contract.get("callback_required")
            ),
        )
        if contract_failures:
            return LLMResponse(
                text="",
                response_hash=response.response_hash,
                blocked_reason=(
                    "publication_section_binding_failed:"
                    + ";".join(contract_failures)
                ),
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
            )
        # The section call itself is an unambiguous binding authority.  Some
        # JSON-object capable providers omit the optional metadata field even
        # when the schema/prompt contains it (especially after content-first
        # generation).  Recover only that empty field from the current call;
        # a non-empty value naming another section remains a hard failure in
        # ``_publication_contract_failures`` below.
        parsed_outputs_by_section.setdefault(section_id, []).append(
            parsed.model_copy(update={"section_id": section_id})
        )
        return LLMResponse(
            text=parsed.section_markdown,
            response_hash=response.response_hash,
            blocked_reason=response.blocked_reason,
            cached=response.cached,
            response_mode=response.response_mode,
            finish_reason=response.finish_reason,
            token_usage=response.token_usage,
        )

    normalized_sections = [
        WriterSectionInput(
            section_id=section.section_id,
            heading=section.heading,
            prompt_payload={
                "section_id": section.section_id,
                "heading": section.heading,
                **section.prompt_payload,
                "argument_graph": section.argument_graph,
                "output_contract": "PublicationMethodSectionOutputV1",
            },
            system_prompt=section.system_prompt or PublicationMethodWriterSkillV1().system_prompt(),
            publication_mode=True,
            argument_graph=section.argument_graph,
        )
        for section in sections
    ]
    aggregate = write_method_by_sections(
        base_config,
        normalized_sections,
        llm_caller=structured_caller,
        call_id_prefix=call_id_prefix,
        schema_name=PUBLICATION_METHOD_SECTION_SCHEMA,
        response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
        publication_mode=True,
    )
    parsed_outputs: list[PublicationMethodSectionOutputV1] = []
    for section_result in aggregate.sections:
        candidates = parsed_outputs_by_section.get(section_result.section_id, [])
        if not candidates:
            continue
        # The accepted text is the exact structured section_markdown returned
        # through ``write_method_by_sections``.  Prefer that match so a
        # shorter first response is not selected when the extended response
        # was accepted; fall back to the latest parsed attempt for providers
        # that normalize the text before returning it.
        selected = next(
            (
                candidate
                for candidate in reversed(candidates)
                if candidate.section_markdown == section_result.text
            ),
            candidates[-1],
        )
        parsed_outputs.append(selected)
        aggregate.research_requests.extend(selected.new_research_requests)
    aggregate.response_recovery_traces.extend(recovery_traces)
    return PublicationWriterResult(aggregate=aggregate, outputs=parsed_outputs)


def _decode_publication_binding_tokens(
    text: str,
    contract: dict[str, Any],
) -> tuple[str, list[str]]:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, []
    if not isinstance(payload, dict):
        return text, []
    bridged: list[str] = []
    for field in (
        "used_argument_unit_ids",
        "used_claim_ids",
        "used_equation_ids",
        "used_configuration_ids",
        "completed_rhetorical_moves",
    ):
        values = list(dict.fromkeys(str(value) for value in contract.get(field, ())))
        token = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
        if payload.get(field) == token:
            payload[field] = values
            bridged.append(field)
    if not bridged:
        return text, []
    return json.dumps(payload, ensure_ascii=False), bridged


def _decode_publication_research_requests(
    text: str,
    *,
    section_id: str,
    argument_graph: dict[str, Any],
) -> tuple[str, list[str]]:
    """Normalize a model's compact callback shorthand into the typed contract.

    Qwen-class providers occasionally emit ``{"move": ..., "reason": ...,
    "status": "unresolved"}`` when the prompt asks for a research callback.
    The shorthand carries no prose authority, but it is still useful metadata.
    We deterministically bind it to the current section/unit and preserve the
    model's reason as the exact question; no factual content is synthesized.
    Full :class:`WritingResearchRequestV1` objects pass through unchanged.
    """

    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, []
    if not isinstance(payload, dict):
        return text, []
    raw_requests = payload.get("new_research_requests")
    if not isinstance(raw_requests, list):
        return text, []
    graph = argument_graph if isinstance(argument_graph, dict) else {}
    unit_ids = [
        str(value) for value in (graph.get("argument_unit_ids") or ()) if str(value)
    ]
    if not unit_ids:
        unit_ids = [
            str(item.get("argument_unit_id") or "")
            for item in (graph.get("argument_units") or ())
            if isinstance(item, dict) and str(item.get("argument_unit_id") or "")
        ]
    move_lanes: dict[str, str] = {}
    for move in graph.get("moves") or ():
        if not isinstance(move, dict):
            continue
        name = str(move.get("move") or "").strip()
        lanes = move.get("allowed_authority_lanes") or ()
        if name and lanes:
            move_lanes[name] = str(lanes[0])
    bridge_fields: list[str] = []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_requests):
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        if {"request_id", "section_id", "argument_unit_id", "missing_rhetorical_move"} <= set(item):
            normalized.append(item)
            continue
        move = str(item.get("move") or item.get("missing_move") or "").strip()
        reason = str(item.get("reason") or item.get("exact_question") or "").strip()
        if not move or not reason or not section_id or not unit_ids:
            normalized.append(item)
            continue
        request_id = str(item.get("request_id") or f"request:{section_id}:{move}:{index + 1}")
        normalized.append({
            "request_id": request_id,
            "section_id": section_id,
            "argument_unit_id": unit_ids[0],
            "missing_rhetorical_move": move,
            "exact_question": reason,
            "required_authority_lane": move_lanes.get(move, "executable_hard"),
            "candidate_symbols_or_terms": tuple(str(value) for value in (item.get("candidate_symbols_or_terms") or ()) if str(value)),
            "current_known_facts": tuple(str(value) for value in (item.get("current_known_facts") or ()) if str(value)),
            "why_needed_for_reader": str(item.get("why_needed_for_reader") or reason),
            "priority": str(item.get("priority") or "high"),
            "status": "open",
        })
        bridge_fields.append(f"new_research_requests[{index}]")
    if not bridge_fields:
        return text, []
    payload["new_research_requests"] = normalized
    return json.dumps(payload, ensure_ascii=False), bridge_fields


def _decode_publication_callback_moves(
    text: str,
    *,
    resolution: dict[str, Any],
) -> tuple[str, list[str]]:
    """Recover move metadata for already fulfilled callback artifacts.

    Callback artifacts authorize only the exact organization move they bind.
    They do not authorize executable claims or arbitrary rhetorical moves.  A
    content-first provider may consume the artifact in ``section_markdown``
    while omitting the corresponding bookkeeping entry, so bridge that one
    structural field before validation.  Reopened requests are deliberately
    excluded; the contract checker must report them instead of hiding a
    failed callback loop.
    """

    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, []
    if not isinstance(payload, dict) or not isinstance(resolution, dict):
        return text, []
    raw_moves = resolution.get("fulfilled_moves")
    if not isinstance(raw_moves, list):
        return text, []
    completed = payload.get("completed_rhetorical_moves")
    if not isinstance(completed, list):
        completed = []
    completed_values = [str(value) for value in completed if str(value)]
    requested_moves = {
        str(item.get("missing_rhetorical_move") or item.get("move") or "").strip()
        for item in (payload.get("new_research_requests") or ())
        if isinstance(item, dict)
    }
    bridge_fields: list[str] = []
    for item in raw_moves:
        if not isinstance(item, dict):
            continue
        move = str(item.get("move") or "").strip()
        if move and move not in completed_values and move not in requested_moves:
            completed_values.append(move)
            bridge_fields.append(f"completed_rhetorical_moves:{move}")
    if not bridge_fields:
        return text, []
    payload["completed_rhetorical_moves"] = completed_values
    return json.dumps(payload, ensure_ascii=False), bridge_fields


def _publication_contract_failures(
    output: PublicationMethodSectionOutputV1,
    *,
    expected_section_id: str,
    contract: dict[str, Any],
    allow_subset: bool = False,
) -> list[str]:
    failures: list[str] = []
    # An omitted/empty section id is a representation defect that can be
    # safely recovered from the scoped call.  A non-empty id is model-authored
    # binding metadata and must match exactly; accepting a cross-section id
    # would let a response satisfy the wrong argument graph.
    if output.section_id and output.section_id != expected_section_id:
        failures.append(f"section_id:{output.section_id!r}!={expected_section_id!r}")
    # Closed-set ID binding happens here, at the writer boundary, so a
    # violation is a typed ``publication_section_binding_failed:*`` response
    # that the owning Agent can repair.  Content-first writer semantics
    # deliberately relax the *missing* side: the Writer is not required to
    # complete every full id/config/equation/move binding in the prose call;
    # post-processing extracts claims from prose and binds them against
    # facts.  A missing id therefore becomes a validator/post-processing
    # concern, never a hard writer failure.  Unknown ids always fail: the
    # harness must never accept an invented id, and the owning Agent may
    # repair a near-miss representation.
    for label, contract_key, used_values in (
        ("argument_units", "used_argument_unit_ids", output.used_argument_unit_ids),
        ("claims", "used_claim_ids", output.used_claim_ids),
        ("equations", "used_equation_ids", output.used_equation_ids),
        ("configurations", "used_configuration_ids", output.used_configuration_ids),
    ):
        allowed = {str(value) for value in contract.get(contract_key, ())}
        used = {str(value) for value in used_values}
        if used - allowed:
            failures.append(f"unknown_{label}:{','.join(sorted(used - allowed))}")
    return failures


def _safe_call(
    caller: _LLMCaller, config: LLMConfig, request: LLMRequest
) -> LLMResponse:
    """Call ``caller`` and convert exceptions into a blocked response.

    The writer never raises from a single-section LLM failure; the
    section is filled with a placeholder and the run continues so the
    final Method is always contiguous.
    """

    try:
        return caller(config, request)
    except Exception as exc:  # noqa: BLE001 — writer must not crash on LLM errors
        _logger.warning("section_writer_llm_error: %s", exc)
        from code2paper.export.run_manifest import hash_text

        return LLMResponse(
            text="",
            response_hash=hash_text(""),
            blocked_reason=f"section_writer_llm_error:{exc.__class__.__name__}",
        )


def _placeholder_section(section: WriterSectionInput, *, reason: str) -> str:
    """Return a deterministic placeholder for a skipped section."""

    return (
        f"## {section.heading}\n\n"
        f"<!-- writer_placeholder: section_id={section.section_id} reason={reason} -->\n"
    )


__all__ = [
    "PublicationWriterResult",
    "WriterAggregateResult",
    "WriterSectionInput",
    "WriterSectionResult",
    "default_section_system_prompt",
    "dynamic_writer_cumulative_budget",
    "write_method_by_sections",
    "write_publication_method_by_sections",
]
