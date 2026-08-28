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
import hashlib
from typing import Any, Callable, Iterable, Mapping, Protocol

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
from code2paper.llm.generation_trace import GenerationCallTrace, build_generation_call_trace
from code2paper.llm.role_config import (
    METHOD_WRITER,
    apply_role_config,
    writer_cumulative_budget,
)
from code2paper.authoring.writer_skill import PublicationMethodWriterSkillV1
from code2paper.llm.writer_section_repair import (
    assess_writer_section_progress,
    build_writer_section_repair_packet,
    repair_is_monotonic,
)
from code2paper.llm.response_schemas import (
    PUBLICATION_METHOD_SECTION_SCHEMA,
    PublicationMethodParagraphOutputV1,
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
    writer_repair_rounds: int = 0
    writer_repair_commits: int = 0
    writer_repair_no_progress_stops: int = 0
    writer_repair_transaction_rejections: list[dict[str, Any]] = field(default_factory=list)
    context_partitioned_section_ids: list[str] = field(default_factory=list)

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
            "writer_repair_rounds": self.writer_repair_rounds,
            "writer_repair_commits": self.writer_repair_commits,
            "writer_repair_no_progress_stops": self.writer_repair_no_progress_stops,
            "writer_repair_transaction_rejections": list(
                self.writer_repair_transaction_rejections
            ),
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


_HARNESS_ONLY_PROMPT_FIELDS = frozenset({
    "argument_units", "argument_flow", "validation_constraints",
    "reader_facing_claims", "section_candidate_points", "paper_term_hints",
    "content_first_instruction", "grounding_contract", "binding_contract",
    "argument_graph", "formalization", "required_rhetorical_moves",
    "anchored_required_moves", "unanchored_required_moves",
    "expository_bridge_required_moves", "callback_required",
    "response_protocol", "audience", "output_contract",
})

_WRITER_VIEW_VISIBLE_FIELDS = frozenset({
    "section_id", "heading", "writer_view",
    "paragraph_plan",
    "formula_packages",
    "formula_obligations",
    "mechanism_section",
    "required_qualifier_bindings",
    "writing_research_callback_artifacts",
    "writing_research_callback_resolution",
    "previous_attempt_error", "previous_attempt_section_markdown",
    "callback_owner_retry_instruction", "writer_section_repair",
    "writer_facet_coverage_repair",
})


_COMPACT_SEMANTIC_FIELD_KEYS = (
    "operation",
    "subject",
    "transformation",
    "inputs",
    "outputs",
    "paper_terms",
    "conditions",
    "interface",
    "interfaces",
    "boundary",
)


def _compact_semantic_gist(fields: Mapping[str, Any] | None) -> str:
    """One-line facet gist from semantic fields (no author quote)."""

    parts: list[str] = []
    if isinstance(fields, Mapping):
        for key in _COMPACT_SEMANTIC_FIELD_KEYS:
            value = fields.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                parts.extend(str(item) for item in value if str(item).strip())
            elif str(value).strip():
                parts.append(str(value))
    return "; ".join(parts[:8])[:800] if parts else ""


def _compact_authoring_packet_for_llm(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Shrink mechanism packet for LLM-visible Writer calls."""

    policies_by_facet: dict[str, str] = {}
    for policy in packet.get("facet_policies") or ():
        if isinstance(policy, Mapping):
            facet_id = str(policy.get("facet_id") or "")
            prose_mode = str(policy.get("prose_mode") or "")
            if facet_id:
                policies_by_facet[facet_id] = prose_mode
    compact_facets: list[dict[str, Any]] = []
    for facet in packet.get("facets") or ():
        if not isinstance(facet, Mapping):
            continue
        facet_id = str(facet.get("facet_id") or "")
        compact_facets.append({
            "facet_id": facet_id,
            "facet_kind": facet.get("facet_kind"),
            "gist": _compact_semantic_gist(facet.get("semantic_fields")),
            "prose_mode": policies_by_facet.get(facet_id, ""),
            "required": bool(facet.get("required", False)),
        })
    seed = str(packet.get("organization_seed") or "")
    return {
        "organization_seed": seed[:4000],
        "required_facet_ids": list(packet.get("required_facet_ids") or ()),
        "facets": compact_facets,
        "facet_policies": [
            {
                "facet_id": item.get("facet_id"),
                "prose_mode": item.get("prose_mode"),
            }
            for item in (packet.get("facet_policies") or ())
            if isinstance(item, Mapping)
        ],
        "brief_ids": list(packet.get("brief_ids") or ()),
    }


def _compact_writer_view_for_llm(writer_view: Mapping[str, Any]) -> dict[str, Any]:
    """Compact four-layer writer_view for LLM calls; validation keeps full packet."""

    purpose = writer_view.get("purpose")
    packet = writer_view.get("mechanism_authoring_packet")
    compact_packet: dict[str, Any] = {}
    if isinstance(packet, Mapping):
        compact_packet = _compact_authoring_packet_for_llm(packet)
    brief_one_liners: list[dict[str, Any]] = []
    for brief in writer_view.get("positive_briefs") or ():
        if isinstance(brief, Mapping):
            brief_one_liners.append({
                "brief_id": brief.get("brief_id"),
                "lane": "licensed",
                "line": str(brief.get("licensed_wording") or "")[:800],
            })
    for brief in writer_view.get("caveated_briefs") or ():
        if isinstance(brief, Mapping):
            brief_one_liners.append({
                "brief_id": brief.get("brief_id"),
                "lane": str(brief.get("required_caveat_kind") or "unlicensed"),
                "line": str(brief.get("text") or "")[:800],
            })
    technical_rows: list[dict[str, Any]] = []
    for item in writer_view.get("technical_propositions") or ():
        if not isinstance(item, Mapping):
            continue
        transformation = str(item.get("transformation") or "").strip()
        if not transformation:
            continue
        technical_rows.append({
            "license": "E2",
            "reader_subject": str(item.get("reader_subject") or "")[:200],
            "transformation": transformation[:500],
        })
    compact: dict[str, Any] = {
        "purpose": purpose,
        "brief_one_liners": brief_one_liners,
        "technical_propositions": technical_rows,
        "claim_free_expository_bridge_allowed": not bool(technical_rows),
        "allowed_brief_ids": list(writer_view.get("allowed_brief_ids") or ()),
        "required_brief_ids": list(writer_view.get("required_brief_ids") or ()),
        "mechanism_authoring_packet": compact_packet,
    }
    if writer_view.get("view_digest"):
        compact["view_digest"] = writer_view.get("view_digest")
    return compact


def _compact_writer_facet_coverage_repair_for_llm(
    repair: Mapping[str, Any],
) -> dict[str, Any]:
    """Compact facet-coverage repair payload for LLM-visible calls."""

    compact = dict(repair)
    packet = compact.get("mechanism_authoring_packet")
    if isinstance(packet, Mapping):
        compact["mechanism_authoring_packet"] = _compact_authoring_packet_for_llm(packet)
    compact.pop("mechanism_drafts", None)
    return compact


def _llm_visible_section_payload(section: WriterSectionInput) -> dict[str, Any]:
    """Keep low-level evidence machinery out of the Writer prose context.

    The omitted fields remain on ``WriterSectionInput.prompt_payload`` for
    deterministic validation and binding.  New proposition-backed calls
    receive only the compact four-layer ``writer_view``, their scoped callback
    state and bounded repair feedback.  Claim/fact/frame/equation/configuration
    IDs and move proofs are harness-private.
    """

    if not section.prompt_payload.get("writer_view"):
        # Frozen pre-proposition artifacts retain the historical surface for
        # backward-compatible replay. New product runs always persist and
        # supply writer_view.
        return {
            **section.prompt_payload,
            "argument_graph": section.argument_graph,
        }
    result = {
        key: value for key, value in section.prompt_payload.items()
        if key in _WRITER_VIEW_VISIBLE_FIELDS
        and key not in _HARNESS_ONLY_PROMPT_FIELDS
    }
    writer_view = result.get("writer_view")
    if isinstance(writer_view, Mapping):
        result["writer_view"] = _compact_writer_view_for_llm(writer_view)
    repair = result.get("writer_facet_coverage_repair")
    if isinstance(repair, Mapping):
        result["writer_facet_coverage_repair"] = _compact_writer_facet_coverage_repair_for_llm(
            repair
        )
    return result


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


def _estimate_input_tokens(text: str | None) -> int:
    """Rough input-token estimate (chars / 4), zero for empty."""

    text = text or ""
    return 0 if not text else max(1, len(text) // 4)


_WRITER_CONTEXT_WINDOW = 131072
_WRITER_INPUT_CHARS_PER_TOKEN = 3
_MIN_WRITER_OUTPUT_TOKENS = 2048


def _writer_context_window(config: LLMConfig) -> int:
    if config.max_input_tokens is not None and config.max_input_tokens > 0:
        return config.max_input_tokens
    return _WRITER_CONTEXT_WINDOW


def _writer_thinking_token_budget(config: LLMConfig) -> int:
    return max(0, int(config.thinking_token_budget or 0))


def _estimate_writer_input_tokens(text: str | None) -> int:
    """Conservative Writer input estimate (chars / 3)."""

    text = text or ""
    return 0 if not text else max(1, len(text) // _WRITER_INPUT_CHARS_PER_TOKEN)


def _estimate_llm_request_tokens(
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
) -> int:
    parts = [system_prompt, json.dumps(input_payload, ensure_ascii=False, default=str)]
    if response_json_schema is not None:
        parts.append(json.dumps(response_json_schema, ensure_ascii=False, default=str))
    return _estimate_writer_input_tokens("\n".join(parts))


def _writer_request_exceeds_context_window(
    *,
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
    max_output_tokens: int | None = None,
) -> bool:
    estimated = _estimate_llm_request_tokens(
        system_prompt,
        input_payload,
        response_json_schema,
    )
    max_output = (
        max_output_tokens
        if max_output_tokens is not None
        else int(config.max_output_tokens or 8192)
    )
    thinking = _writer_thinking_token_budget(config)
    return estimated + max_output + thinking >= _writer_context_window(config)


def _writer_compact_input_exceeds_window_minus_min_output(
    *,
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
) -> bool:
    """True when compact input alone cannot leave room for minimum output."""

    estimated = _estimate_llm_request_tokens(
        system_prompt,
        input_payload,
        response_json_schema,
    )
    thinking = _writer_thinking_token_budget(config)
    return (
        estimated + thinking + _MIN_WRITER_OUTPUT_TOKENS
        >= _writer_context_window(config)
    )


def _writer_call_max_output_tokens(
    *,
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
) -> int:
    """Clamp max_output so input + output + thinking stays below the window."""

    window = _writer_context_window(config)
    thinking = _writer_thinking_token_budget(config)
    estimated = _estimate_llm_request_tokens(
        system_prompt,
        input_payload,
        response_json_schema,
    )
    available = window - estimated - thinking - 1
    requested = int(config.max_output_tokens or 8192)
    if available <= 0:
        return 0
    return max(1, min(requested, available))


def _writer_partition_request_fits(
    *,
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
) -> bool:
    """Whether a compact partition request can be sent after output clamp."""

    max_output = _writer_call_max_output_tokens(
        system_prompt=system_prompt,
        input_payload=input_payload,
        response_json_schema=response_json_schema,
        config=config,
    )
    return max_output >= _MIN_WRITER_OUTPUT_TOKENS


def _sanitize_publication_output_overlap(
    output: PublicationMethodSectionOutputV1,
) -> PublicationMethodSectionOutputV1:
    """Drop ids listed in both rendered and deferred witness lists (rendered wins)."""

    rendered_facets = {str(value) for value in output.rendered_from_facet_ids}
    deferred_facets = [
        str(value)
        for value in output.deferred_facet_ids
        if str(value) not in rendered_facets
    ]
    if rendered_facets == set(output.rendered_from_facet_ids) and deferred_facets == list(
        output.deferred_facet_ids
    ):
        return output
    return output.model_copy(
        update={"deferred_facet_ids": deferred_facets},
    )


def _merge_publication_partition_outputs(
    outputs: list[PublicationMethodSectionOutputV1],
) -> PublicationMethodSectionOutputV1:
    """Merge partitioned Writer structured outputs for one section."""

    if not outputs:
        raise ValueError("partition merge requires at least one output")
    if len(outputs) == 1:
        return outputs[0]
    base = outputs[0]
    markdown_parts = [
        part.section_markdown.strip()
        for part in outputs
        if str(part.section_markdown or "").strip()
    ]
    rendered_facets: set[str] = set()
    deferred_facets: set[str] = set()
    rendered_briefs: set[str] = set()
    deferred_briefs: set[str] = set()
    rendered_concepts: set[str] = set()
    deferred_concepts: set[str] = set()
    rendered_paragraphs: set[str] = set()
    rendered_slots: set[str] = set()
    rendered_edges: set[str] = set()
    used_formula_packages: list[str] = []
    used_units: list[str] = []
    used_claims: list[str] = []
    used_equations: list[str] = []
    used_configs: list[str] = []
    paragraph_transactions: dict[str, PublicationMethodParagraphOutputV1] = {}
    callbacks: list[Any] = []
    for part in outputs:
        rendered_facets.update(str(v) for v in part.rendered_from_facet_ids)
        deferred_facets.update(str(v) for v in part.deferred_facet_ids)
        rendered_briefs.update(str(v) for v in part.rendered_brief_ids)
        deferred_briefs.update(str(v) for v in part.deferred_brief_ids)
        rendered_concepts.update(str(v) for v in part.rendered_concept_keys)
        deferred_concepts.update(str(v) for v in part.deferred_concept_keys)
        rendered_paragraphs.update(str(v) for v in part.rendered_paragraph_ids)
        rendered_slots.update(str(v) for v in part.rendered_slot_ids)
        rendered_edges.update(str(v) for v in part.rendered_edge_ids)
        used_formula_packages.extend(part.used_formula_package_ids)
        used_units.extend(part.used_argument_unit_ids)
        used_claims.extend(part.used_claim_ids)
        used_equations.extend(part.used_equation_ids)
        used_configs.extend(part.used_configuration_ids)
        for paragraph in part.paragraphs:
            paragraph_transactions.setdefault(paragraph.paragraph_id, paragraph)
        callbacks.extend(part.new_research_requests)
    deferred_facets -= rendered_facets
    deferred_briefs -= rendered_briefs
    deferred_concepts -= rendered_concepts
    return base.model_copy(
        update={
            "section_markdown": "\n\n".join(markdown_parts),
            "rendered_from_facet_ids": tuple(sorted(rendered_facets)),
            "deferred_facet_ids": tuple(sorted(deferred_facets)),
            "rendered_brief_ids": tuple(dict.fromkeys(rendered_briefs)),
            "deferred_brief_ids": tuple(sorted(deferred_briefs)),
            "rendered_concept_keys": tuple(sorted(rendered_concepts)),
            "deferred_concept_keys": tuple(sorted(deferred_concepts)),
            "rendered_paragraph_ids": tuple(sorted(rendered_paragraphs)),
            "rendered_slot_ids": tuple(sorted(rendered_slots)),
            "rendered_edge_ids": tuple(sorted(rendered_edges)),
            "used_formula_package_ids": tuple(dict.fromkeys(used_formula_packages)),
            "used_argument_unit_ids": tuple(dict.fromkeys(used_units)),
            "used_claim_ids": tuple(dict.fromkeys(used_claims)),
            "used_equation_ids": tuple(dict.fromkeys(used_equations)),
            "used_configuration_ids": tuple(dict.fromkeys(used_configs)),
            "paragraphs": tuple(paragraph_transactions.values()),
            "new_research_requests": tuple(callbacks),
        },
    )


def _filter_writer_payload_facet_ids(
    payload: dict[str, Any],
    facet_ids: frozenset[str],
) -> dict[str, Any]:
    """Return a deep copy of ``payload`` scoped to ``facet_ids``."""

    if not facet_ids:
        return payload
    filtered = copy.deepcopy(payload)
    writer_view = filtered.get("writer_view")
    if isinstance(writer_view, dict):
        packet = writer_view.get("mechanism_authoring_packet")
        if isinstance(packet, dict):
            facets = [
                item for item in (packet.get("facets") or ())
                if isinstance(item, dict)
                and str(item.get("facet_id") or "") in facet_ids
            ]
            packet = {
                **packet,
                "facets": facets,
                "required_facet_ids": [
                    fid for fid in (packet.get("required_facet_ids") or ())
                    if str(fid) in facet_ids
                ],
                "facet_policies": [
                    item for item in (packet.get("facet_policies") or ())
                    if isinstance(item, dict)
                    and str(item.get("facet_id") or "") in facet_ids
                ],
            }
            writer_view["mechanism_authoring_packet"] = packet
        drafts = writer_view.get("mechanism_drafts")
        if isinstance(drafts, list):
            writer_view["mechanism_drafts"] = [
                item for item in drafts
                if isinstance(item, dict)
                and any(
                    str(fid) in facet_ids
                    for fid in (item.get("facet_ids") or item.get("required_facet_ids") or ())
                )
            ]
        filtered["writer_view"] = writer_view
    contract = filtered.get("binding_contract")
    if isinstance(contract, dict):
        filtered["binding_contract"] = {
            **contract,
            "allowed_facet_ids": [
                fid for fid in (contract.get("allowed_facet_ids") or ())
                if str(fid) in facet_ids
            ],
            "required_facet_ids": [
                fid for fid in (contract.get("required_facet_ids") or ())
                if str(fid) in facet_ids
            ],
        }
    return filtered


def _publication_section_partitions(
    section: WriterSectionInput,
    *,
    system_prompt: str,
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
) -> list[WriterSectionInput]:
    """Split one section only when compact input still exceeds the context window."""

    base_payload = {
        "section_id": section.section_id,
        "heading": section.heading,
        **_llm_visible_section_payload(section),
    }
    if not _writer_request_exceeds_context_window(
        system_prompt=system_prompt,
        input_payload=base_payload,
        response_json_schema=response_json_schema,
        config=config,
    ):
        return [section]
    clamped_max_output = _writer_call_max_output_tokens(
        system_prompt=system_prompt,
        input_payload=base_payload,
        response_json_schema=response_json_schema,
        config=config,
    )
    if (
        clamped_max_output >= _MIN_WRITER_OUTPUT_TOKENS
        and not _writer_compact_input_exceeds_window_minus_min_output(
            system_prompt=system_prompt,
            input_payload=base_payload,
            response_json_schema=response_json_schema,
            config=config,
        )
    ):
        return [section]
    payload = section.prompt_payload or {}
    writer_view = payload.get("writer_view") if isinstance(payload.get("writer_view"), dict) else {}
    packet = writer_view.get("mechanism_authoring_packet")
    if not isinstance(packet, dict):
        packet = payload.get("mechanism_authoring_packet")
    facet_items = [
        item for item in ((packet or {}).get("facets") or ())
        if isinstance(item, dict) and str(item.get("facet_id") or "").strip()
    ]
    facet_ids = [str(item.get("facet_id") or "") for item in facet_items]
    if len(facet_ids) < 2:
        graph = section.argument_graph or {}
        moves = [move for move in (graph.get("moves") or ()) if isinstance(move, dict)]
        if len(moves) < 2:
            return [section]
        partitions: list[WriterSectionInput] = []
        for move_index, move in enumerate(moves):
            move_graph = {
                **graph,
                "moves": [move],
            }
            partition_payload = copy.deepcopy(payload)
            partition_payload["writer_context_partition"] = {
                "partition_index": move_index,
                "partition_count": len(moves),
                "partition_move": str(move.get("move") or ""),
            }
            partitions.append(WriterSectionInput(
                section_id=section.section_id,
                heading=section.heading,
                prompt_payload=partition_payload,
                system_prompt=section.system_prompt,
                publication_mode=section.publication_mode,
                argument_graph=move_graph,
            ))
        return _writer_partitions_that_fit(
            partitions,
            system_prompt=system_prompt,
            response_json_schema=response_json_schema,
            config=config,
            fallback=section,
        )
    groups: list[list[str]] = []
    current: list[str] = []
    for facet_id in facet_ids:
        trial_ids = frozenset((*current, facet_id))
        trial_payload = _filter_writer_payload_facet_ids(payload, trial_ids)
        trial_input = {
            "section_id": section.section_id,
            "heading": section.heading,
            **_llm_visible_section_payload(WriterSectionInput(
                section_id=section.section_id,
                heading=section.heading,
                prompt_payload=trial_payload,
                system_prompt=section.system_prompt,
                publication_mode=section.publication_mode,
                argument_graph=section.argument_graph,
            )),
        }
        if current and _writer_compact_input_exceeds_window_minus_min_output(
            system_prompt=system_prompt,
            input_payload=trial_input,
            response_json_schema=response_json_schema,
            config=config,
        ):
            groups.append(current)
            current = [facet_id]
        else:
            current.append(facet_id)
    if current:
        groups.append(current)
    if len(groups) < 2:
        return [section]
    partitions: list[WriterSectionInput] = []
    for partition_index, group in enumerate(groups):
        facet_group = frozenset(group)
        partition_payload = _filter_writer_payload_facet_ids(payload, facet_group)
        partition_payload["writer_context_partition"] = {
            "partition_index": partition_index,
            "partition_count": len(groups),
            "partition_facet_ids": list(group),
        }
        if partition_index > 0:
            partition_payload["previous_partition_tail_instruction"] = (
                "Continue the same section from the prior partition without "
                "repeating its heading or already-covered facets."
            )
        partitions.append(WriterSectionInput(
            section_id=section.section_id,
            heading=section.heading,
            prompt_payload=partition_payload,
            system_prompt=section.system_prompt,
            publication_mode=section.publication_mode,
            argument_graph=section.argument_graph,
        ))
    return _writer_partitions_that_fit(
        partitions,
        system_prompt=system_prompt,
        response_json_schema=response_json_schema,
        config=config,
        fallback=section,
    )


def _writer_partitions_that_fit(
    partitions: list[WriterSectionInput],
    *,
    system_prompt: str,
    response_json_schema: dict[str, Any] | None,
    config: LLMConfig,
    fallback: WriterSectionInput,
) -> list[WriterSectionInput]:
    """Drop partitions whose compact input still cannot fit after output clamp."""

    fitting: list[WriterSectionInput] = []
    for work_section in partitions:
        trial_input = {
            "section_id": work_section.section_id,
            "heading": work_section.heading,
            **_llm_visible_section_payload(work_section),
        }
        if _writer_partition_request_fits(
            system_prompt=system_prompt,
            input_payload=trial_input,
            response_json_schema=response_json_schema,
            config=config,
        ):
            fitting.append(work_section)
    if fitting:
        return fitting
    return [fallback]


def _apply_writer_context_clamp(
    config: LLMConfig,
    *,
    system_prompt: str,
    input_payload: Mapping[str, Any],
    response_json_schema: dict[str, Any] | None,
) -> tuple[LLMConfig, LLMResponse | None]:
    """Clamp max_output to fit the context window; block when input alone overflows."""

    clamped_max = _writer_call_max_output_tokens(
        system_prompt=system_prompt,
        input_payload=input_payload,
        response_json_schema=response_json_schema,
        config=config,
    )
    if clamped_max <= 0:
        from code2paper.export.run_manifest import hash_text

        return config, LLMResponse(
            text="",
            response_hash=hash_text(""),
            blocked_reason="writer_context_window_exceeded:compact_input_overflow",
        )
    if clamped_max < _MIN_WRITER_OUTPUT_TOKENS:
        if _writer_compact_input_exceeds_window_minus_min_output(
            system_prompt=system_prompt,
            input_payload=input_payload,
            response_json_schema=response_json_schema,
            config=config,
        ):
            from code2paper.export.run_manifest import hash_text

            return config, LLMResponse(
                text="",
                response_hash=hash_text(""),
                blocked_reason="writer_context_window_exceeded:compact_input_overflow",
            )
    requested = int(config.max_output_tokens or 8192)
    if clamped_max >= requested:
        return config, None
    return config.model_copy(update={"max_output_tokens": clamped_max}), None


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
    content_transaction_validator: Callable[
        [WriterSectionInput, str, str], tuple[bool, str]
    ] | None = None,
    content_transaction_assessor: Callable[
        [WriterSectionInput, LLMResponse, LLMResponse], tuple[bool, str]
    ] | None = None,
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
        publication_section = publication_mode or section.publication_mode
        call_config_for_partition = apply_role_config(
            base_config, METHOD_WRITER, extended_writer_budget=False
        )
        call_config_for_partition = call_config_for_partition.model_copy(
            update={
                "max_output_tokens": min(
                    call_config_for_partition.max_output_tokens,
                    cap - result.cumulative_budget_consumed,
                )
            }
        )
        partition_targets = (
            _publication_section_partitions(
                section,
                system_prompt=system_prompt,
                response_json_schema=section_schema,
                config=call_config_for_partition,
            )
            if publication_section
            else [section]
        )
        partition_markdown_parts: list[str] = []
        accepted_response: LLMResponse | None = None
        accepted_trace: GenerationCallTrace | None = None
        extended_used = False
        repair_input_payload: dict[str, Any] = {}

        for part_index, work_section in enumerate(partition_targets):
            if part_index > 0 and partition_markdown_parts:
                work_section = WriterSectionInput(
                    section_id=work_section.section_id,
                    heading=work_section.heading,
                    prompt_payload={
                        **work_section.prompt_payload,
                        "previous_attempt_section_markdown": (
                            partition_markdown_parts[-1][-2000:]
                        ),
                    },
                    system_prompt=work_section.system_prompt,
                    publication_mode=work_section.publication_mode,
                    argument_graph=work_section.argument_graph,
                )
            part_schema = _closed_set_publication_schema(
                response_json_schema,
                section=work_section,
            )
            request = LLMRequest(
                prompt_template_id=f"phase5_method_writer_section_v1",
                prompt=system_prompt,
                input_payload={
                    "section_id": work_section.section_id,
                    "heading": work_section.heading,
                    **_llm_visible_section_payload(work_section),
                },
                schema_name=schema_name,
                response_json_schema=part_schema,
            )
            repair_input_payload = dict(request.input_payload or {})

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
            part_suffix = (
                f"-part{part_index}" if len(partition_targets) > 1 else ""
            )
            call_id = f"{call_id_prefix}-{index}-{section.section_id}{part_suffix}"
            call_config, blocked_response = _apply_writer_context_clamp(
                call_config,
                system_prompt=system_prompt,
                input_payload=request.input_payload,
                response_json_schema=part_schema,
            )
            if blocked_response is not None:
                response = blocked_response
            else:
                response = _safe_call(caller, call_config, request)
            part_extended_used = False

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
            accepted_trace = default_trace
            accepted_response = response
            result.cumulative_budget_consumed = default_cumulative

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
                extended_call_id = (
                    f"{call_id_prefix}-{index}-{section.section_id}{part_suffix}-ext"
                )
                extended_config, blocked_response = _apply_writer_context_clamp(
                    extended_config,
                    system_prompt=system_prompt,
                    input_payload=request.input_payload,
                    response_json_schema=part_schema,
                )
                if blocked_response is not None:
                    extended_response = blocked_response
                else:
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
                result.cumulative_budget_consumed = extended_cumulative
                if len(extended_response.text or "") > len(response.text or ""):
                    accepted_response = extended_response
                    accepted_trace = extended_trace
                    part_extended_used = True
                    extended_used = True
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
                retry_input_payload = dict(request.input_payload or {})
                retry_input_payload["previous_attempt_error"] = accepted_response.blocked_reason
                retry_request = LLMRequest(
                    prompt_template_id=request.prompt_template_id + "_representation_repair_v1",
                    prompt=request.prompt,
                    input_payload=retry_input_payload,
                    schema_name=request.schema_name,
                    response_json_schema=request.response_json_schema,
                )
                retry_call_id = (
                    f"{call_id_prefix}-{index}-{section.section_id}{part_suffix}-representation-retry"
                )
                retry_config, blocked_response = _apply_writer_context_clamp(
                    retry_config,
                    system_prompt=system_prompt,
                    input_payload=retry_input_payload,
                    response_json_schema=part_schema,
                )
                if blocked_response is not None:
                    retry_response = blocked_response
                else:
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
                if not retry_response.blocked_reason and (retry_response.text or "").strip():
                    accepted_response = retry_response
                    accepted_trace = retry_trace

            partition_markdown_parts.append(accepted_response.text or "")
            if result.cumulative_budget_consumed >= cap:
                break

        if len(partition_targets) > 1 and partition_markdown_parts:
            merged_text = "\n\n".join(
                part for part in partition_markdown_parts if part.strip()
            )
            result.context_partitioned_section_ids.append(section.section_id)
            last_response = accepted_response
            accepted_response = LLMResponse(
                text=merged_text,
                response_hash=(
                    last_response.response_hash if last_response is not None else ""
                ),
                blocked_reason=(
                    last_response.blocked_reason if last_response is not None else None
                ),
                cached=last_response.cached if last_response is not None else False,
                response_mode=(
                    last_response.response_mode if last_response is not None else None
                ),
                finish_reason=(
                    last_response.finish_reason if last_response is not None else "stop"
                ),
                token_usage=(
                    last_response.token_usage if last_response is not None else None
                ),
                metadata=last_response.metadata if last_response is not None else None,
            )
            repair_input_payload = {
                "section_id": section.section_id,
                "heading": section.heading,
                **_llm_visible_section_payload(section),
            }

        if accepted_response is None:
            accepted_response = LLMResponse(text="", blocked_reason="section_writer_no_response")

        # Content-level repair belongs to the Writer owner.
        writer_view = repair_input_payload.get("writer_view")
        if isinstance(writer_view, dict):
            writer_view = {
                **writer_view,
                "formula_obligations": list(
                    repair_input_payload.get("formula_obligations") or ()
                ),
            }
        transaction_failure = str(accepted_response.blocked_reason or "").startswith(
            "publication_paragraph_transaction_failed:"
        )
        if (
            isinstance(writer_view, dict)
            and (accepted_response.text or "").strip()
            and (not accepted_response.blocked_reason or transaction_failure)
            and result.cumulative_budget_consumed < cap
        ):
            # The structured wrapper cannot expose its metadata here, so use
            # the model's required set as the conservative initial rendered
            # set only when the prose contains no typed failure. The repair
            # request asks the Writer to return explicit proposition IDs.
            incumbent_progress, content_failures = assess_writer_section_progress(
                accepted_response.text or "",
                writer_view=writer_view,
                rendered_proposition_ids=(),
            )
            try:
                configured_rounds = int(os.environ.get("CODE2PAPER_MAX_WRITER_REPAIR_ROUNDS", "3"))
            except ValueError:
                configured_rounds = 3
            max_rounds = max(0, min(configured_rounds, 4))
            transaction_repair_used = False
            for repair_round in range(1, max_rounds + 1):
                if not content_failures or result.cumulative_budget_consumed >= cap:
                    break
                repair_payload = dict(request.input_payload)
                repair_packet = build_writer_section_repair_packet(
                    section_id=section.section_id,
                    attempt=repair_round,
                    incumbent_text=accepted_response.text or "",
                    writer_view=writer_view,
                    progress=incumbent_progress,
                    failures=content_failures,
                )
                repair_payload["writer_section_repair"] = repair_packet.model_dump(
                    mode="json"
                )
                repair_request = LLMRequest(
                    prompt_template_id=request.prompt_template_id + "_content_repair_v1",
                    prompt=request.prompt,
                    input_payload=repair_payload,
                    schema_name=request.schema_name,
                    response_json_schema=request.response_json_schema,
                )
                repair_config = apply_role_config(base_config, METHOD_WRITER).model_copy(update={
                    "max_output_tokens": min(
                        apply_role_config(base_config, METHOD_WRITER).max_output_tokens,
                        cap - result.cumulative_budget_consumed,
                    )
                })
                repair_config, blocked_response = _apply_writer_context_clamp(
                    repair_config,
                    system_prompt=system_prompt,
                    input_payload=repair_payload,
                    response_json_schema=request.response_json_schema,
                )
                if blocked_response is not None:
                    repair_response = blocked_response
                else:
                    repair_response = _safe_call(caller, repair_config, repair_request)
                result.writer_repair_rounds += 1
                used = _output_tokens_used(repair_response)
                cumulative = min(cap, result.cumulative_budget_consumed + used)
                repair_trace = build_generation_call_trace(
                    call_id=f"{call_id_prefix}-{index}-{section.section_id}-content-{repair_round}",
                    config=repair_config,
                    request=repair_request,
                    response=repair_response,
                    extended_budget_used=False,
                    cumulative_budget_consumed=cumulative,
                )
                result.traces.append(repair_trace)
                result.cumulative_budget_consumed = cumulative
                repair_transaction_failure = str(
                    repair_response.blocked_reason or ""
                ).startswith("publication_paragraph_transaction_failed:")
                if (
                    (repair_response.blocked_reason and not repair_transaction_failure)
                    or not (repair_response.text or "").strip()
                ):
                    break
                candidate_progress, candidate_failures = assess_writer_section_progress(
                    repair_response.text or "",
                    writer_view=writer_view,
                    rendered_proposition_ids=(),
                )
                if content_transaction_assessor is not None:
                    transaction_ok, transaction_reason = content_transaction_assessor(
                        section, accepted_response, repair_response
                    )
                elif content_transaction_validator is not None:
                    transaction_ok, transaction_reason = content_transaction_validator(
                        section, accepted_response.text or "", repair_response.text or ""
                    )
                if content_transaction_assessor is not None or content_transaction_validator is not None:
                    if not transaction_ok:
                        result.writer_repair_transaction_rejections.append({
                            "section_id": section.section_id,
                            "repair_round": repair_round,
                            "reason": transaction_reason,
                            "incumbent_digest": hashlib.sha256(
                                (accepted_response.text or "").encode("utf-8")
                            ).hexdigest(),
                            "candidate_digest": hashlib.sha256(
                                (repair_response.text or "").encode("utf-8")
                            ).hexdigest(),
                        })
                        if transaction_repair_used or repair_round == max_rounds:
                            result.writer_repair_no_progress_stops += 1
                            break
                        transaction_repair_used = True
                        content_failures = list(dict.fromkeys([
                            f"transaction:{transaction_reason}",
                            *candidate_failures,
                        ]))
                        continue
                # Run the semantic/evidence transaction before the local
                # progress comparison.  This preserves an actionable owner
                # failure (and permits its single correction turn) when a
                # stylistic improvement introduces an unsupported positive.
                if not repair_is_monotonic(incumbent_progress, candidate_progress):
                    result.writer_repair_no_progress_stops += 1
                    break
                accepted_response = repair_response
                accepted_trace = repair_trace
                incumbent_progress = candidate_progress
                content_failures = candidate_failures
                transaction_repair_used = False
                result.writer_repair_commits += 1

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


_MECHANISM_MOVE_NAMES = frozenset({
    "mechanism_overview",
    "equation_or_derivation",
    "algorithm_or_data_flow",
    "implementation_realization",
    "inference_and_output",
    "formal_objects_and_notation",
    "configuration_and_branches",
    "training_objective",
})


def _publication_section_markdown_max_length(
    *,
    unit_count: int,
    moves: Any,
    facet_count: int = 0,
) -> int:
    """JSON-schema cap for one Method section.

    Rhetorical-only sections stay bounded so they cannot absorb thousands of
    characters of unsupported background.  Mechanism sections need enough
    room for a multi-step procedure (input, transformation steps, conditions,
    output) rather than a single cramped paragraph.
    """

    move_list = [move for move in (moves or ()) if isinstance(move, dict)]
    budgets = [
        max(0, int(move.get("paragraph_budget") or 0))
        for move in move_list
    ]
    has_mechanism = any(
        str(move.get("move") or "") in _MECHANISM_MOVE_NAMES
        or int(move.get("paragraph_budget") or 0) >= 2
        for move in move_list
    )
    conceptual_paragraphs = max(
        1,
        min(
            6,
            max(budgets or [1])
            + (1 if unit_count > 3 else 0)
            + (1 if facet_count > 2 else 0),
        ),
    )
    floor = 4800 if has_mechanism else 2800
    return min(
        10000,
        max(
            floor,
            1600 + 900 * conceptual_paragraphs + 180 * max(1, unit_count),
        ),
    )


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
    unit_count = len(section.argument_graph.get("argument_unit_ids") or ())
    writer_view_early = section.prompt_payload.get("writer_view")
    mechanism_packet_early = (
        writer_view_early.get("mechanism_authoring_packet")
        if isinstance(writer_view_early, dict)
        else None
    )
    facet_count = 0
    if isinstance(mechanism_packet_early, dict):
        facets_early = mechanism_packet_early.get("facets") or ()
        if isinstance(facets_early, (list, tuple)):
            facet_count = len(facets_early)
    paragraph_transaction_required = bool(
        section.prompt_payload.get("paragraph_transaction_required")
    )
    if not paragraph_transaction_required:
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "section_markdown",
        ]))
    markdown_property = properties.get("section_markdown")
    if isinstance(markdown_property, dict):
        max_length = _publication_section_markdown_max_length(
            unit_count=unit_count,
            moves=section.argument_graph.get("moves") or (),
            facet_count=facet_count,
        )
        # A Method section may be concise.  Headings-only and fragment
        # output are still rejected by structural/editability checks.
        markdown_property["minLength"] = (
            0 if paragraph_transaction_required else min(max_length, 180)
        )
        markdown_property["maxLength"] = max_length
    paragraph_property = properties.get("paragraphs")
    if isinstance(paragraph_property, dict):
        paragraph_plans = [
            item for item in (section.argument_graph.get("paragraphs") or ())
            if isinstance(item, dict)
        ]
        paragraph_property["maxItems"] = len(paragraph_plans) if paragraph_plans else 64
        if paragraph_transaction_required and paragraph_plans:
            schema["required"] = list(dict.fromkeys([
                *(schema.get("required") or ()),
                "paragraphs",
            ]))
        paragraph_def = (
            schema.get("$defs", {}).get("PublicationMethodParagraphOutputV1")
            if isinstance(schema.get("$defs"), dict)
            else None
        )
        if isinstance(paragraph_def, dict):
            paragraph_properties = paragraph_def.get("properties")
            if isinstance(paragraph_properties, dict):
                for field_name, plan_key in (
                    ("rendered_from_facet_ids", "required_facet_ids"),
                    ("rendered_slot_ids", "ordered_semantic_slot_ids"),
                    ("rendered_edge_ids", "required_edge_ids"),
                    ("used_formula_package_ids", "formula_obligation_ids"),
                ):
                    field_schema = paragraph_properties.get(field_name)
                    if not isinstance(field_schema, dict):
                        continue
                    values = list(dict.fromkeys(
                        str(value)
                        for item in paragraph_plans
                        for value in (item.get(plan_key) or ())
                        if str(value).strip()
                    ))
                    # A paragraph may bind either the Architect's obligation
                    # id or the Formalizer's package id.  Keep both in the
                    # native closed set; otherwise a valid package consumer
                    # is rejected before the transaction validator can check
                    # its exact formula witness.
                    if field_name == "used_formula_package_ids":
                        values.extend(
                            str(item.get("package_id") or "")
                            for item in (section.prompt_payload.get("formula_packages") or ())
                            if isinstance(item, dict)
                            and str(item.get("package_id") or "").strip()
                        )
                        values = list(dict.fromkeys(values))
                    item_schema = field_schema.get("items")
                    if isinstance(item_schema, dict) and values:
                        item_schema["enum"] = values
                id_schema = paragraph_properties.get("paragraph_id")
                if isinstance(id_schema, dict):
                    paragraph_ids = [
                        str(item.get("paragraph_id") or "")
                        for item in paragraph_plans
                        if str(item.get("paragraph_id") or "").strip()
                    ]
                    if paragraph_ids:
                        id_schema["enum"] = paragraph_ids
    writer_view = section.prompt_payload.get("writer_view")
    concept_mode = bool(
        isinstance(writer_view, dict)
        and (writer_view.get("positive_concepts") or writer_view.get("caveated_concepts"))
    )
    brief_mode = bool(
        isinstance(writer_view, dict)
        and (writer_view.get("positive_briefs") or writer_view.get("caveated_briefs"))
    )
    mechanism_packet = (
        writer_view.get("mechanism_authoring_packet")
        if isinstance(writer_view, dict)
        else None
    )
    facet_mode = bool(
        isinstance(mechanism_packet, dict)
        and mechanism_packet.get("facets")
    )
    proposition_mode = bool(
        isinstance(writer_view, dict)
        and (writer_view.get("positive_propositions") or writer_view.get("caveated_propositions"))
    )
    content_first_mode = concept_mode or proposition_mode or brief_mode or facet_mode
    heading_property = properties.get("heading_text")
    if isinstance(heading_property, dict):
        heading_property["maxLength"] = 220
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
    for field in (() if content_first_mode else binding_fields):
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
    for field, contract_key in (
        ("rendered_proposition_ids", "allowed_proposition_ids"),
        ("deferred_proposition_ids", "allowed_proposition_ids"),
    ):
        if not proposition_mode:
            continue
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
        properties[field] = {
            "type": "array",
            "items": {"type": "string"} if not values else {"type": "string", "enum": values},
            "maxItems": len(values) if values else 16,
            "uniqueItems": True,
        }
    for field, contract_key in (
        ("rendered_concept_keys", "allowed_concept_keys"),
        ("deferred_concept_keys", "allowed_concept_keys"),
    ):
        if not concept_mode:
            continue
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
        properties[field] = {
            "type": "array",
            "items": {"type": "string"} if not values else {"type": "string", "enum": values},
            "maxItems": len(values) if values else 16,
            "uniqueItems": True,
        }
    for field, contract_key in (
        ("rendered_brief_ids", "allowed_brief_ids"),
        ("deferred_brief_ids", "allowed_brief_ids"),
    ):
        if not brief_mode:
            continue
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
        properties[field] = {
            "type": "array",
            "items": {"type": "string"} if not values else {"type": "string", "enum": values},
            "maxItems": len(values) if values else 16,
            "uniqueItems": True,
        }
        if field == "rendered_brief_ids":
            primary_brief_ids = [
                str(value).strip()
                for value in (contract.get("primary_brief_ids") or ())
                if str(value).strip()
            ]
            if primary_brief_ids:
                properties[field]["minItems"] = 1
    for field, contract_key in (
        ("rendered_from_facet_ids", "allowed_facet_ids"),
        ("deferred_facet_ids", "allowed_facet_ids"),
        ("rendered_paragraph_ids", "allowed_paragraph_ids"),
        ("rendered_slot_ids", "allowed_slot_ids"),
        ("rendered_edge_ids", "allowed_edge_ids"),
        ("used_formula_package_ids", "allowed_formula_package_ids"),
    ):
        if not facet_mode:
            continue
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
        properties[field] = {
            "type": "array",
            "items": {"type": "string"} if not values else {"type": "string", "enum": values},
            "maxItems": len(values) if values else 16,
            "uniqueItems": True,
        }
        if field == "rendered_from_facet_ids":
            required_facet_ids = [
                str(value).strip()
                for value in (contract.get("required_facet_ids") or ())
                if str(value).strip()
            ]
            if required_facet_ids:
                properties[field]["minItems"] = len(required_facet_ids)
    for field, contract_key in (
        ("rendered_paragraph_ids", "allowed_paragraph_ids"),
        ("rendered_slot_ids", "allowed_slot_ids"),
        ("rendered_edge_ids", "allowed_edge_ids"),
        ("used_formula_package_ids", "allowed_formula_package_ids"),
    ):
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
        properties[field] = {
            "type": "array",
            "items": {"type": "string"} if not values else {"type": "string", "enum": values},
            "maxItems": len(values) if values else 64,
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
    if isinstance(move_schema, dict) and not content_first_mode:
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
    # Stage 5 callback enforcement: when the section has unanchored required
    # moves, ``new_research_requests`` must be present and non-empty with
    # closed-set bindings.  Guided decoding then physically prevents the
    # Writer from returning ``[]`` and silently leaving the move unresolved.
    # The harness contract validator still rejects fabricated requests
    # (unknown move/unit/lane, missing candidates, invented concept keys),
    # so schema enforcement never weakens the callback gate.
    unanchored_moves = list(dict.fromkeys(
        str(value) for value in (
            grounding.get("unanchored_required_moves") or ()
            if isinstance(grounding, dict) else ()
        )
    ))
    callback_prototypes = (
        grounding.get("callback_request_prototypes") or ()
        if isinstance(grounding, dict) else ()
    )
    concept_binding_present = any(
        isinstance(proto, dict) and proto.get("concept_binding")
        for proto in callback_prototypes
    )
    brief_binding_present = any(
        isinstance(proto, dict) and proto.get("brief_binding")
        for proto in callback_prototypes
    )
    # Brief callbacks are an independent callback obligation.  A section can
    # have all repository moves anchored while still carrying an unverified
    # author clause or an empty mechanism draft; that state must reach the
    # forced callback schema instead of being treated as complete.
    if brief_binding_present:
        callback_required = True
    graph_moves = section.argument_graph.get("moves") or ()
    real_move_names = {
        str(move.get("move") or "").strip()
        for move in graph_moves
        if isinstance(move, dict) and str(move.get("move") or "").strip()
    }
    if callback_required and (unanchored_moves or brief_binding_present):
        move_authority = grounding.get("move_authority") or {}
        callback_moves = list(dict.fromkeys(
            unanchored_moves
            + [
                str(proto.get("missing_rhetorical_move") or "").strip()
                for proto in callback_prototypes
                if isinstance(proto, dict)
                and str(proto.get("missing_rhetorical_move") or "").strip()
            ]
            + [
                str(value).strip()
                for value in (contract.get("required_rhetorical_moves") or ())
                if str(value).strip()
            ]
        ))
        callback_moves = [
            move_name for move_name in callback_moves
            if move_name in real_move_names
        ]
        move_unit_ids = {
            str(move.get("move") or ""): tuple(
                str(unit_id) for unit_id in (move.get("argument_unit_ids") or ())
            )
            for move in graph_moves
            if isinstance(move, dict)
        }
        allowed_units = list(dict.fromkeys(
            str(unit_id)
            for move_name in callback_moves
            for unit_id in (
                move_unit_ids.get(move_name)
                or section.argument_graph.get("argument_unit_ids")
                or ()
            )
        ))
        allowed_lanes = list(dict.fromkeys(
            str((move_authority.get(move_name) or {}).get("required_authority_lane") or "")
            for move_name in callback_moves
            if str((move_authority.get(move_name) or {}).get("required_authority_lane") or "")
        ))
        if not allowed_lanes:
            allowed_lanes = list(dict.fromkeys(
                str(proto.get("required_authority_lane") or "").strip()
                for proto in callback_prototypes
                if isinstance(proto, dict)
                and str(proto.get("required_authority_lane") or "").strip()
            ))
        require_candidate_symbols = bool(
            allowed_lanes
            and set(allowed_lanes) <= {
                "executable_hard", "configuration_resolved", "formal_derivation",
            }
        )
        properties["new_research_requests"] = {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                # Strict structured outputs (OpenAI ``strict: true``, used for
                # loopback xgrammar guided decoding) require every nested
                # object to forbid additional properties; all callback fields
                # are declared below.
                "additionalProperties": False,
                "required": [
                    "request_id", "section_id", "argument_unit_id",
                    "missing_rhetorical_move", "exact_question",
                    "required_authority_lane", "status",
                    *(
                        ["candidate_symbols_or_terms"]
                        if require_candidate_symbols
                        else []
                    ),
                    *(
                        ["concept_key", "missing_parts", "evidence_refs_used"]
                        if concept_binding_present else []
                    ),
                    *(
                        ["target_brief_ids", "target_clause_ids", "missing_parts", "evidence_refs_used"]
                        if brief_binding_present else []
                    ),
                ],
                "properties": {
                    "request_id": {"type": "string", "minLength": 8},
                    "section_id": {"const": section.section_id},
                    "argument_unit_id": {
                        "type": "string",
                        "enum": allowed_units,
                    },
                    "missing_rhetorical_move": {
                        "type": "string",
                        "enum": callback_moves,
                    },
                    "exact_question": {"type": "string", "minLength": 5},
                    "required_authority_lane": {
                        "type": "string",
                        "enum": allowed_lanes,
                    },
                    "candidate_symbols_or_terms": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                    "current_known_facts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "why_needed_for_reader": {"type": "string"},
                    "priority": {"type": "string"},
                    "status": {"const": "open"},
                    "concept_key": {"type": "string"},
                    "missing_parts": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence_refs_used": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "target_brief_ids": {
                        "type": "array",
                        "minItems": 1 if brief_binding_present else 0,
                        "items": {"type": "string"},
                    },
                    "target_clause_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        }
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "new_research_requests",
        ]))
    elif not callback_required:
        # Without an unanchored required move the Writer must not invent
        # extra callbacks.  Guided decoding physically forbids a non-empty
        # list so anchored sections cannot fail as invalid extras.
        properties["new_research_requests"] = {
            "type": "array",
            "maxItems": 0,
            "items": {"type": "object"},
        }
    # Concept-mode guided decoding must expose the WP2 witness fields.
    # Dropping them here made native JSON schema physically unable to emit
    # rendered/deferred concept keys, so every required primary failed as
    # ``missing_required_concepts`` after a structurally valid response.
    # Proposition id fields belong only in proposition mode; leaving them
    # unconstrained in concept-only sections lets formula obligation ids
    # leak into ``deferred_proposition_ids``.
    ordered_names = (
        "section_id",
        "heading_text",
        "paragraphs",
        "rendered_paragraph_ids",
        "rendered_slot_ids",
        "rendered_edge_ids",
        "used_formula_package_ids",
        *(("used_argument_unit_ids", "used_claim_ids", "used_equation_ids", "used_configuration_ids") if not proposition_mode else ()),
        *(("rendered_proposition_ids", "deferred_proposition_ids") if proposition_mode else ()),
        *(("rendered_concept_keys", "deferred_concept_keys") if concept_mode else ()),
        *(("rendered_brief_ids", "deferred_brief_ids") if brief_mode else ()),
        *(("rendered_from_facet_ids", "deferred_facet_ids") if facet_mode else ()),
        *(("completed_rhetorical_moves",) if not proposition_mode else ()),
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
    if concept_mode:
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "rendered_concept_keys",
            "deferred_concept_keys",
        ]))
    if brief_mode:
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "rendered_brief_ids",
            "deferred_brief_ids",
        ]))
    if proposition_mode:
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "rendered_proposition_ids",
            "deferred_proposition_ids",
        ]))
    if facet_mode:
        schema["required"] = list(dict.fromkeys([
            *(schema.get("required") or ()),
            "rendered_from_facet_ids",
            "deferred_facet_ids",
        ]))
    return schema


@dataclass
class PublicationWriterResult:
    """Publication-mode writer result with structured callback requests."""

    aggregate: WriterAggregateResult
    outputs: list[PublicationMethodSectionOutputV1] = field(default_factory=list)

    @property
    def incomplete_sections(self) -> list[str]:
        return list(self.aggregate.incomplete_sections)


def _normalize_publication_paragraph_transaction(
    output: PublicationMethodSectionOutputV1,
    *,
    section: WriterSectionInput,
    require_transactions: bool = False,
) -> tuple[PublicationMethodSectionOutputV1, list[str]]:
    """Validate and assemble paragraph-scoped Writer transactions.

    Self-reported aggregate ids are insufficient evidence of rendered content.
    When the production contract is enabled, every planned paragraph must
    arrive once, each witness must be an exact unique substring of that
    paragraph, and the section Markdown is assembled in plan order.  Frozen
    replay callers may omit ``paragraphs`` and retain the legacy section field.
    """

    transactions = tuple(output.paragraphs or ())
    if not transactions:
        return output, ["paragraph_transaction_missing"] if require_transactions else []
    graph = section.argument_graph if isinstance(section.argument_graph, dict) else {}
    planned = tuple(
        item for item in (graph.get("paragraphs") or ()) if isinstance(item, dict)
    )
    expected_ids = tuple(
        str(item.get("paragraph_id") or "") for item in planned
        if str(item.get("paragraph_id") or "").strip()
    )
    failures: list[str] = []
    if not expected_ids:
        failures.append("paragraph_transactions_without_plan")
    by_id: dict[str, PublicationMethodParagraphOutputV1] = {}
    for transaction in transactions:
        paragraph_id = str(transaction.paragraph_id)
        if paragraph_id in by_id:
            failures.append(f"duplicate_paragraph_transaction:{paragraph_id}")
        elif expected_ids and paragraph_id not in set(expected_ids):
            failures.append(f"unknown_paragraph_transaction:{paragraph_id}")
        else:
            by_id[paragraph_id] = transaction
    if require_transactions:
        missing = [paragraph_id for paragraph_id in expected_ids if paragraph_id not in by_id]
        failures.extend(f"missing_paragraph_transaction:{paragraph_id}" for paragraph_id in missing)

    plan_by_id = {
        str(item.get("paragraph_id") or ""): item for item in planned
    }
    aggregate_fields = {
        "rendered_from_facet_ids": set(),
        "rendered_slot_ids": set(),
        "rendered_edge_ids": set(),
        "used_formula_package_ids": set(),
        "used_claim_ids": set(),
        "used_equation_ids": set(),
    }
    assembled_parts: list[str] = []
    for paragraph_id in expected_ids or tuple(by_id):
        transaction = by_id.get(paragraph_id)
        if transaction is None:
            continue
        body = transaction.paragraph_markdown.strip()
        plan_row = plan_by_id.get(paragraph_id, {})
        section_claim_ids = {
            str(value)
            for unit in (section.prompt_payload.get("argument_units") or ())
            if isinstance(unit, dict)
            for value in (unit.get("claim_ids") or ())
        }
        section_equation_ids = {
            str(value)
            for unit in (section.prompt_payload.get("argument_units") or ())
            if isinstance(unit, dict)
            for value in (unit.get("equation_ids") or ())
        }
        packet = section.prompt_payload.get("writer_view") or {}
        packet = (
            packet.get("mechanism_authoring_packet")
            if isinstance(packet, dict)
            else {}
        ) or {}
        section_facet_ids = {
            str(item.get("facet_id") or "")
            for item in (packet.get("facets") or ())
            if isinstance(item, dict) and str(item.get("facet_id") or "").strip()
        }
        section_formula_package_ids = {
            str(item.get("package_id") or "")
            for item in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(item, dict) and str(item.get("package_id") or "").strip()
        }
        allowed = {
            "facet": (
                set(str(value) for value in (plan_row.get("required_facet_ids") or ()))
                | section_facet_ids
            ),
            "slot": set(str(value) for value in (plan_row.get("ordered_semantic_slot_ids") or ())),
            "edge": set(str(value) for value in (plan_row.get("required_edge_ids") or ())),
            "formula": (
                set(str(value) for value in (plan_row.get("formula_obligation_ids") or ()))
                | section_formula_package_ids
            ),
            "claim": section_claim_ids,
            "equation": section_equation_ids,
        }
        witnessed: set[tuple[str, str]] = set()
        for witness in transaction.witnesses:
            kind = str(witness.witness_kind)
            target_id = str(witness.target_id)
            exact_text = str(witness.exact_text)
            if target_id not in allowed.get(kind, set()):
                failures.append(f"unknown_{kind}_witness:{paragraph_id}:{target_id}")
            if body.count(exact_text) != 1:
                failures.append(f"witness_not_unique_substring:{paragraph_id}:{target_id}")
            key = (kind, target_id)
            if key in witnessed:
                failures.append(f"duplicate_witness:{paragraph_id}:{kind}:{target_id}")
            witnessed.add(key)
        for field_name, kind in (
            ("rendered_from_facet_ids", "facet"),
            ("rendered_slot_ids", "slot"),
            ("rendered_edge_ids", "edge"),
            ("used_formula_package_ids", "formula"),
            ("used_claim_ids", "claim"),
            ("used_equation_ids", "equation"),
        ):
            values = tuple(str(value) for value in getattr(transaction, field_name))
            for value in values:
                if (kind, value) not in witnessed:
                    failures.append(f"missing_exact_witness:{paragraph_id}:{kind}:{value}")
                aggregate_fields[field_name].add(value)
        # The local checks above reject unknown/de-duplicated declarations and
        # malformed exact witnesses.  The shared assessor additionally closes
        # the other side of the contract: every target required by this plan
        # row must be declared and witnessed.  Keeping this in one pure
        # helper lets the persisted content trace apply precisely the same
        # rule after the response has crossed the Writer boundary.
        # Import lazily: ``code2paper.agentic`` exports the publication
        # writer, which itself imports this module.  Keeping the shared
        # contract out of module import time avoids that package cycle while
        # preserving one implementation for runtime/trace validation.
        from code2paper.agentic.publication_transaction_contract import (
            assess_paragraph_transaction,
        )
        assessment = assess_paragraph_transaction(
            transaction,
            plan_row=plan_row,
            formula_routes={
                str(obligation.get("obligation_id") or ""): {
                    "package_ids": tuple(
                        str(package.get("package_id") or "")
                        for package in (section.prompt_payload.get("formula_packages") or ())
                        if isinstance(package, Mapping)
                        and str(package.get("package_id") or "").strip()
                        and (
                            not obligation.get("facet_ids")
                            or set(str(item) for item in (obligation.get("facet_ids") or ()))
                            & set(str(item) for item in (package.get("bound_facet_ids") or ()))
                        )
                    ),
                    "latex": next(
                        (
                            str(package.get("latex") or package.get("markdown_block") or "")
                            for package in (section.prompt_payload.get("formula_packages") or ())
                            if isinstance(package, Mapping)
                            and str(package.get("package_id") or "").strip()
                            and (
                                not obligation.get("facet_ids")
                                or set(str(item) for item in (obligation.get("facet_ids") or ()))
                                & set(str(item) for item in (package.get("bound_facet_ids") or ()))
                            )
                        ),
                        "",
                    ),
                }
                for obligation in (section.prompt_payload.get("formula_obligations") or ())
                if isinstance(obligation, Mapping)
                and str(obligation.get("obligation_id") or "").strip()
            },
        )
        if not assessment.valid:
            failures.extend(
                f"required_target_contract:{paragraph_id}:{kind}:{target}"
                for kind, targets in assessment.missing_by_kind.items()
                for target in targets
            )
            failures.extend(
                f"semantic_target_contract:{paragraph_id}:{failure}"
                for failure in assessment.semantic_failures
            )
        if body:
            assembled_parts.append(body)

    if failures:
        # Keep the authored bytes available for the Candidate checkpoint even
        # when the transaction is invalid.  The failure state is carried
        # separately and the caller/trace must not count these rows as
        # rendered, but dropping the body here would make a quality defect
        # indistinguishable from a transport failure.
        heading = " ".join(str(section.heading or output.heading_text or "").split()).strip()
        if heading.startswith("#"):
            heading = heading.lstrip("#").strip()
        section_markdown = "\n\n".join(assembled_parts)
        if heading and section_markdown:
            section_markdown = f"## {heading}\n\n{section_markdown}"
        preserved = output.model_copy(update={
            "section_markdown": section_markdown or output.section_markdown,
        })
        return preserved, list(dict.fromkeys(failures))
    # Section structure is owned by the Architect, not by whichever
    # paragraph happens to be emitted first.  Assemble exactly one H2 here
    # and keep each transaction's body substantive; this makes the reverse
    # validator see the same heading/paragraph boundary on every retry.
    heading = " ".join(str(section.heading or output.heading_text or "").split()).strip()
    if heading.startswith("#"):
        heading = heading.lstrip("#").strip()
    section_markdown = "\n\n".join(assembled_parts)
    if heading:
        section_markdown = f"## {heading}\n\n{section_markdown}"
    return output.model_copy(update={
        "section_markdown": section_markdown,
        "rendered_paragraph_ids": list(expected_ids or tuple(by_id)),
        "rendered_from_facet_ids": sorted(aggregate_fields["rendered_from_facet_ids"]),
        "rendered_slot_ids": sorted(aggregate_fields["rendered_slot_ids"]),
        "rendered_edge_ids": sorted(aggregate_fields["rendered_edge_ids"]),
        "used_formula_package_ids": sorted(aggregate_fields["used_formula_package_ids"]),
        "used_claim_ids": sorted(aggregate_fields["used_claim_ids"]),
        "used_equation_ids": sorted(aggregate_fields["used_equation_ids"]),
    }), []


def write_publication_method_by_sections(
    base_config: LLMConfig,
    sections: Iterable[WriterSectionInput],
    *,
    llm_caller: _LLMCaller | None = None,
    call_id_prefix: str = "LLM-publication-method-section",
    content_transaction_validator: Callable[
        [WriterSectionInput, str, str], tuple[bool, str]
    ] | None = None,
    content_transaction_assessor: Callable[
        [WriterSectionInput, LLMResponse, LLMResponse], tuple[bool, str]
    ] | None = None,
) -> PublicationWriterResult:
    """Run the content-first publication Writer contract.

    A malformed structured response becomes an incomplete section.  The
    harness never fills it with deterministic prose and never converts the
    model's ids into substitute text.
    """

    caller = llm_caller or _default_llm_caller
    source_sections = list(sections)
    private_sections_by_id = {item.section_id: item for item in source_sections}
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
        scoped_section_id = str(request.input_payload.get("section_id") or "")
        private_section = private_sections_by_id.get(scoped_section_id)
        private_payload = (
            private_section.prompt_payload if private_section is not None else {}
        )
        private_graph = (
            private_section.argument_graph if private_section is not None else {}
        )
        normalized_text, bridged_fields = _decode_publication_binding_tokens(
            response.text,
            private_payload.get("binding_contract") or {},
        )
        normalized_text, research_bridge_fields = _decode_publication_research_requests(
            normalized_text,
            section_id=scoped_section_id,
            argument_graph=private_graph or {},
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
        parsed = _sanitize_publication_output_overlap(parsed)
        section_id = str(request.input_payload.get("section_id") or parsed.section_id or "")
        transaction_required = bool(
            isinstance(private_payload, dict)
            and private_payload.get("paragraph_transaction_required")
        )
        if private_section is not None:
            parsed, paragraph_failures = _normalize_publication_paragraph_transaction(
                parsed,
                section=private_section,
                require_transactions=transaction_required,
            )
        else:
            paragraph_failures = []
        if paragraph_failures:
            # Preserve the model-authored Candidate body while marking the
            # transaction incomplete.  The owner repair path can now see the
            # actual incumbent text and attempt a scoped semantic correction;
            # no invalid paragraph is ever counted as rendered.
            parsed_outputs_by_section[section_id] = [
                parsed.model_copy(update={"section_id": section_id})
            ]
            return LLMResponse(
                text=parsed.section_markdown,
                response_hash=response.response_hash,
                blocked_reason=(
                    "publication_paragraph_transaction_failed:"
                    + ";".join(paragraph_failures)
                ),
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
                metadata=parsed,
            )
        if not transaction_required and not str(parsed.section_markdown or "").strip():
            return LLMResponse(
                text="",
                response_hash=response.response_hash,
                blocked_reason="publication_section_schema_failed:section_markdown_empty",
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
            )
        grounding_contract = private_payload.get("grounding_contract") or {}
        contract_failures = _publication_contract_failures(
            parsed,
            expected_section_id=section_id,
            contract=private_payload.get("binding_contract") or {},
            allow_subset=bool(
                isinstance(grounding_contract, dict)
                and grounding_contract.get("callback_required")
            ),
        )
        hard_failures = _hard_publication_binding_failures(contract_failures)
        if hard_failures:
            return LLMResponse(
                text="",
                response_hash=response.response_hash,
                blocked_reason=(
                    "publication_section_binding_failed:"
                    + ";".join(hard_failures)
                ),
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
            )
        partition_meta = request.input_payload.get("writer_context_partition")
        if partition_meta:
            parsed_outputs_by_section.setdefault(section_id, []).append(
                parsed.model_copy(update={"section_id": section_id})
            )
        else:
            parsed_outputs_by_section[section_id] = [
                parsed.model_copy(update={"section_id": section_id})
            ]
        return LLMResponse(
            text=parsed.section_markdown,
            response_hash=response.response_hash,
            blocked_reason=response.blocked_reason,
            cached=response.cached,
            response_mode=response.response_mode,
            finish_reason=response.finish_reason,
            token_usage=response.token_usage,
            metadata=parsed,
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
        for section in source_sections
    ]
    aggregate = write_method_by_sections(
        base_config,
        normalized_sections,
        llm_caller=structured_caller,
        call_id_prefix=call_id_prefix,
        schema_name=PUBLICATION_METHOD_SECTION_SCHEMA,
        response_json_schema=json_schema_for(PublicationMethodSectionOutputV1),
        publication_mode=True,
        content_transaction_validator=content_transaction_validator,
        content_transaction_assessor=content_transaction_assessor,
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
        if len(candidates) > 1 and section_result.section_id in aggregate.context_partitioned_section_ids:
            selected = _merge_publication_partition_outputs(candidates)
        else:
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
    for field, contract_key in (
        ("used_argument_unit_ids", "used_argument_unit_ids"),
        ("used_claim_ids", "used_claim_ids"),
        ("used_equation_ids", "used_equation_ids"),
        ("used_configuration_ids", "used_configuration_ids"),
        ("completed_rhetorical_moves", "completed_rhetorical_moves"),
        ("rendered_from_facet_ids", "allowed_facet_ids"),
        ("deferred_facet_ids", "allowed_facet_ids"),
        ("rendered_paragraph_ids", "allowed_paragraph_ids"),
        ("rendered_slot_ids", "allowed_slot_ids"),
        ("rendered_edge_ids", "allowed_edge_ids"),
        ("used_formula_package_ids", "allowed_formula_package_ids"),
    ):
        values = list(dict.fromkeys(str(value) for value in contract.get(contract_key, ())))
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
        ("rendered_propositions", "allowed_proposition_ids", output.rendered_proposition_ids),
        ("deferred_propositions", "allowed_proposition_ids", output.deferred_proposition_ids),
        ("rendered_concepts", "allowed_concept_keys", output.rendered_concept_keys),
        ("deferred_concepts", "allowed_concept_keys", output.deferred_concept_keys),
        ("rendered_briefs", "allowed_brief_ids", output.rendered_brief_ids),
        ("deferred_briefs", "allowed_brief_ids", output.deferred_brief_ids),
        ("rendered_paragraphs", "allowed_paragraph_ids", output.rendered_paragraph_ids),
        ("rendered_slots", "allowed_slot_ids", output.rendered_slot_ids),
        ("rendered_edges", "allowed_edge_ids", output.rendered_edge_ids),
        ("formula_packages", "allowed_formula_package_ids", output.used_formula_package_ids),
    ):
        allowed = {str(value) for value in contract.get(contract_key, ())}
        used = {str(value) for value in used_values}
        if used - allowed:
            failures.append(f"unknown_{label}:{','.join(sorted(used - allowed))}")
    rendered_concepts = {str(value) for value in output.rendered_concept_keys}
    deferred_concepts = {str(value) for value in output.deferred_concept_keys}
    overlap = rendered_concepts & deferred_concepts
    if overlap:
        failures.append(
            f"concept_rendered_deferred_overlap:{','.join(sorted(overlap))}"
        )
    required_primary = {
        str(value)
        for value in (
            contract.get("primary_concept_keys")
            or contract.get("required_concept_keys")
            or ()
        )
        if str(value).strip()
    }
    if required_primary:
        missing_primary = required_primary - rendered_concepts - deferred_concepts
        if missing_primary:
            failures.append(
                f"missing_required_concepts:{','.join(sorted(missing_primary))}"
            )
    rendered_briefs = {str(value) for value in output.rendered_brief_ids}
    deferred_briefs = {str(value) for value in output.deferred_brief_ids}
    overlap_briefs = rendered_briefs & deferred_briefs
    if overlap_briefs:
        failures.append(
            f"brief_rendered_deferred_overlap:{','.join(sorted(overlap_briefs))}"
        )
    required_briefs = {
        str(value)
        for value in (
            contract.get("primary_brief_ids")
            or contract.get("required_brief_ids")
            or ()
        )
        if str(value).strip()
    }
    if required_briefs:
        missing_briefs = required_briefs - rendered_briefs
        if missing_briefs:
            failures.append(
                f"missing_required_briefs:{','.join(sorted(missing_briefs))}"
            )
    rendered_facets = {str(value) for value in output.rendered_from_facet_ids}
    deferred_facets = {str(value) for value in output.deferred_facet_ids}
    overlap_facets = rendered_facets & deferred_facets
    if overlap_facets:
        failures.append(
            f"facet_rendered_deferred_overlap:{','.join(sorted(overlap_facets))}"
        )
    allowed_facets = {
        str(value) for value in contract.get("allowed_facet_ids", ())
    }
    if rendered_facets - allowed_facets:
        failures.append(
            f"unknown_rendered_facets:{','.join(sorted(rendered_facets - allowed_facets))}"
        )
    if deferred_facets - allowed_facets:
        failures.append(
            f"unknown_deferred_facets:{','.join(sorted(deferred_facets - allowed_facets))}"
        )
    required_facets = {
        str(value)
        for value in contract.get("required_facet_ids", ())
        if str(value).strip()
    }
    missing_facets = required_facets - rendered_facets
    if missing_facets:
        # Required facet coverage is a content-completeness warning.  Keep
        # the authored body for the Writer owner retry and Candidate
        # diagnostics; only unknown/overlapping ids are hard binding errors.
        failures.append(
            f"missing_required_facets:{','.join(sorted(missing_facets))}"
        )
    return failures


_CONTENT_COMPLETENESS_FAILURE_PREFIXES = (
    "missing_required_briefs:",
    "missing_required_facets:",
)


def _hard_publication_binding_failures(failures: Iterable[str]) -> list[str]:
    """Unknown-id / overlap failures that discard a Writer response.

    ``missing_required_briefs`` is a Candidate completeness warning.  DyG
    111122 and LinearRAG 100052 showed the live defect: the Writer returned
    structured JSON with thousands of markdown tokens, then this gate
    cleared ``text=""`` and the Candidate path never saw the body.
    Invented ids still discard.
    """

    return [
        failure
        for failure in failures
        if not str(failure).startswith(_CONTENT_COMPLETENESS_FAILURE_PREFIXES)
    ]


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
