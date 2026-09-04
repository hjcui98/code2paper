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
import re
from dataclasses import dataclass, field, replace
import hashlib
from typing import Any, Callable, Iterable, Mapping, Protocol

from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.capabilities import StructuredResponseMode, load_capability_profile
from code2paper.llm.generation_trace import GenerationCallTrace, build_generation_call_trace
from code2paper.llm.role_config import (
    METHOD_WRITER,
    SEMANTIC_VERIFIER,
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
    PUBLICATION_PARAGRAPH_BINDING_SCHEMA,
    PUBLICATION_METHOD_SECTION_SCHEMA,
    PublicationMethodParagraphOutputV1,
    PublicationMethodSectionOutputV1,
    PublicationParagraphBindingResponseV1,
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
    "authoring_packets_v2",
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


def _is_implementation_trace_text(*values: Any) -> bool:
    """True for debug/logging/NER-skip/membership atoms that must not own Method prose."""

    blob = " ".join(
        " ".join(str(item) for item in value)
        if isinstance(value, (list, tuple, set))
        else str(value or "")
        for value in values
    )
    return bool(re.search(
        r"(?i)(?:\bcase_study\b|logger\.|"
        r"ent\.label_|label_\s*==|"
        r"['\"]ORDINAL['\"]|['\"]CARDINAL['\"]|"
        r"\([^)]{0,120}\)\s+in\s+[A-Za-z_][A-Za-z0-9_]*|"
        r"\b(?:debug|logging)\b)",
        blob,
    ))


def _strip_implementation_trace_values(value: Any) -> Any:
    """Drop audit/debug tokens from an otherwise scientific operation row."""

    if isinstance(value, (list, tuple, set)):
        cleaned = [
            item for item in value
            if str(item).strip() and not _is_implementation_trace_text(item)
        ]
        return type(value)(cleaned) if not isinstance(value, set) else cleaned
    if isinstance(value, str) and _is_implementation_trace_text(value):
        return ""
    return value


# These patterns intentionally describe *shapes* of implementation plumbing,
# rather than project names.  The Writer still receives scientific symbols
# (for example ``A``, ``B``, ``\u0394t``, attention masks, and sequence lengths),
# while qualified Python names, storage keys, and audit identifiers stay on the
# harness side of the publication boundary.
_READER_INTERNAL_IDENTIFIER_RE = re.compile(
    r"(?i)^(?:[a-z][a-z0-9]*:){1,}[a-z0-9_.:-]+$|"
    r"^(?:[a-z][a-z0-9]*[.:-]){1,}[a-z][a-z0-9_.:-]*$"
)
_READER_STORAGE_IDENTIFIER_RE = re.compile(
    r"(?i)(?:^|[_ .-])(?:cache|caches|memory|memories|buffer|buffers|"
    r"storage|stores|lookup|lookups|mapping|dict|dictionary|metadata|"
    r"artifact|artifacts|debug|logger|loggers)(?:$|[_ .-])"
)
_READER_ID_IDENTIFIER_RE = re.compile(
    r"(?i)(?:^|[_ .-])(?:id|ids|key|keys|index|indices|span|claim|facet|"
    r"paragraph|obligation|request)(?:$|[_ .-])"
)
_READER_PYTHON_SYNTAX_RE = re.compile(
    r"(?i)(?:\bself\s*\.|\b(?:torch|numpy|np|nn|tensorflow|tf|math)\s*\.\w*\s*\(|"
    r"\b(?:logsumexp|argsort|sort|stack|cat|concat|concatenate|reshape|view|"
    r"normalize|softmax|pad|split|topk|gather|scatter|einsum|matmul|mean|sum)\s*\([^)]{0,180}\)|"
    r"\b(?:dim|axis|dtype|device|keepdim|descending|largest|training)\s*=)"
)


def _project_reader_value(value: Any, *, limit: int = 360) -> Any:
    """Project an operation value into a bounded reader-facing representation.

    This is deliberately conservative for strings that have the shape of
    source plumbing.  It is not an allow-list of repository identifiers: a
    normal phrase or scientific symbol remains available, while internal IDs,
    tuple membership, qualified calls, and storage/index keys are omitted.
    Lists are projected element-wise so one implementation operand cannot
    poison an otherwise useful operation.
    """

    if isinstance(value, Mapping):
        projected = {
            str(key): _project_reader_value(item, limit=limit)
            for key, item in value.items()
        }
        return {
            key: item for key, item in projected.items()
            if item not in (None, "", [], (), {})
        }
    if isinstance(value, (list, tuple, set)):
        items = [
            _project_reader_value(item, limit=limit)
            for item in value
        ]
        items = [item for item in items if item not in (None, "", [], (), {})]
        return items
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    if _is_implementation_trace_text(text):
        return ""
    if _READER_PYTHON_SYNTAX_RE.search(text):
        return ""
    # A tuple/membership row is a lookup implementation detail unless an
    # upstream semantic statement already described the scientific operation.
    if re.search(r"\([^)]{0,180}\)\s+(?:in|not\s+in)\s+[A-Za-z_]\w*", text):
        return ""
    if re.search(r"\b[A-Za-z_]\w*\s+(?:not\s+)?in\s+[A-Za-z_]\w*", text) and (
        _READER_STORAGE_IDENTIFIER_RE.search(text)
        or _READER_ID_IDENTIFIER_RE.search(text)
    ):
        return ""
    if _READER_INTERNAL_IDENTIFIER_RE.fullmatch(text):
        return ""
    if _READER_STORAGE_IDENTIFIER_RE.search(text) and re.fullmatch(
        r"[A-Za-z0-9_.:-]+", text
    ):
        return ""
    if _READER_STORAGE_IDENTIFIER_RE.search(text) and re.search(
        r"(?i)\b(?:in|from|via|using|within|inside)\s+[A-Za-z0-9_.:-]+$",
        text,
    ):
        return ""
    if _READER_ID_IDENTIFIER_RE.search(text) and re.fullmatch(
        r"[A-Za-z0-9_.:-]+", text
    ):
        return ""
    # Internal snake-case names are retained only when they are clearly a
    # reader term (e.g. ``sequence_length``); identifier-bearing names are
    # not useful grammatical subjects in a paper Method.
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", text):
        lowered = text.casefold()
        if "_" in text and (
            lowered.endswith(("_id", "_ids", "_key", "_keys", "_index", "_indices"))
            or any(
                marker in lowered.split("_")
                for marker in ("cache", "memory", "buffer", "storage", "metadata", "debug")
            )
        ):
            return ""
    return text[:limit].rstrip() if len(text) > limit else text


def _is_raw_code_identifier(text: Any) -> bool:
    """Return True if text has the signature of a low-level implementation variable."""
    if not isinstance(text, str):
        return False
    val = text.strip()
    if not val:
        return False
    # Mathematical notation (LaTeX commands, sub/superscript brackets, operators) is scientific
    if "\\" in val or any(ch in val for ch in ("$", "{", "}", "^", "+", "-", "*", "/")):
        return False
    # Space-separated natural language phrases are reader concepts (e.g. "attention mask")
    if " " in val:
        return False
    # Snake_case implementation names: e.g. dst_router_logits, dst_routing_weights, conv_state
    # Subscripted math symbols (e.g. h_t, x_t, W_q) have a single-letter or uppercase base.
    if re.fullmatch(r"[a-z0-9_]+", val) and "_" in val:
        parts = val.split("_")
        if len(parts[0]) > 1 or any(len(p) > 2 for p in parts[1:]):
            return True
    return False


def _project_operation_to_reader_surface(value: Mapping[str, Any] | Any) -> dict[str, Any] | None:
    """Compile one raw operation row into the Writer's semantic surface.

    When semantic text exists (reader_facing_claim, semantic_atom, description,
    statement), use semantic-primary projection: keep the academic claim,
    predicate, material conditions, iteration context, and shape hints; do not
    expose raw implementation variables.  When no semantic text exists,
    fall back to structured projection so scientific symbols (such as h_t, W)
    remain visible.
    """

    row = dict(value) if isinstance(value, Mapping) else {}
    semantic = ""
    has_semantic_claim = False
    for key in (
        "reader_facing_claim", "semantic_atom", "description", "statement",
    ):
        projected = _project_reader_value(row.get(key))
        if isinstance(projected, str) and projected.strip():
            semantic = projected.strip()
            has_semantic_claim = True
            break
    if not semantic:
        projected = _project_reader_value(row.get("operation"))
        if isinstance(projected, str) and projected.strip():
            semantic = projected.strip()

    predicate = _project_reader_value(row.get("predicate"), limit=120)
    if not isinstance(predicate, str) or not predicate.strip():
        predicate = ""
    projected: dict[str, Any] = {}
    if semantic:
        projected["operation"] = semantic
    if predicate:
        projected["predicate"] = predicate

    if has_semantic_claim:
        # Semantic-primary mode: keep semantic operation, conditions, shape hints,
        # but filter out raw implementation code identifiers from operands/result/subject
        for source_key, output_key in (
            ("guard", "guard"),
            ("conditions", "conditions"),
            ("iteration_context", "iteration_context"),
            ("shape_or_type_hints", "shape_or_type_hints"),
        ):
            value = _project_reader_value(row.get(source_key))
            if value not in (None, "", [], (), {}):
                projected[output_key] = value

        for source_key, output_key in (
            ("subject", "subject"),
            ("operands", "operands"),
            ("result", "result"),
            ("output", "output"),
            ("return_value", "return_value"),
        ):
            raw_val = row.get(source_key)
            if raw_val is None:
                continue
            if isinstance(raw_val, (list, tuple)):
                filtered_items = [
                    item for item in raw_val
                    if not _is_raw_code_identifier(item)
                ]
                value = _project_reader_value(filtered_items)
            else:
                if _is_raw_code_identifier(raw_val):
                    continue
                value = _project_reader_value(raw_val)
            if value not in (None, "", [], (), {}):
                projected[output_key] = value
        return projected

    # Safe-structured fallback mode
    for source_key, output_key in (
        ("subject", "subject"),
        ("operands", "operands"),
        ("result", "result"),
        ("output", "output"),
        ("return_value", "return_value"),
        ("guard", "guard"),
        ("conditions", "conditions"),
        ("iteration_context", "iteration_context"),
        ("shape_or_type_hints", "shape_or_type_hints"),
    ):
        value = _project_reader_value(row.get(source_key))
        if value not in (None, "", [], (), {}):
            projected[output_key] = value
    # A predicate alone is not scientific content: retain it only when a
    # semantic statement or at least one reader-facing value accompanies it.
    content_keys = {
        "operation", "subject", "operands", "result", "output",
        "return_value", "conditions", "shape_or_type_hints",
    }
    if not any(projected.get(key) not in (None, "", [], (), {}) for key in content_keys):
        return None
    return projected


# Publicly named aliases make the projection contract reusable by diagnostics
# and focused tests without exposing the lower-level implementation regexes.
project_reader_value = _project_reader_value
project_operation_to_reader_surface = _project_operation_to_reader_surface


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


def _compact_formula_packages_for_llm(packages: Any) -> list[dict[str, Any]]:
    """Expose formula consumption tokens without exposing formula text."""

    compact_packages: list[dict[str, Any]] = []
    for item in packages or ():
        if not isinstance(item, Mapping):
            continue
        package_id = str(item.get("package_id") or "").strip()
        if not package_id:
            # Pre-package/legacy callers may provide a display-only formula
            # row without an internal package id.  Preserve that row as a
            # non-bindable context hint so the compatibility surface does not
            # silently erase the only formula input.  Current production
            # packages always carry an id and use the placeholder-only path
            # below; an id-less row can never be consumed by Binder.
            compact_packages.append({
                key: item[key]
                for key in (
                    "purpose", "latex", "prose_explanation",
                    "symbol_definitions", "symbol_table", "material_conditions",
                    "assumptions", "authority_status", "formula_lane",
                )
                if key in item
            })
            continue
        compact = {
            key: item[key]
            for key in (
                "package_id", "purpose", "prose_explanation",
                "symbol_definitions", "symbol_table", "material_conditions",
                "assumptions", "authority_status", "formula_lane",
                "satisfied_obligation_ids", "consumer_paragraph_id",
                "semantic_formula_digest",
            )
            if key in item
        }
        compact["placeholder"] = (
            str(item.get("placeholder") or "").strip()
            or f"[[FORMULA:{package_id}]]"
        )
        compact_packages.append(compact)
    return compact_packages


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
    field_candidates = [
        {
            "candidate_id": item.get("candidate_id"),
            "facet_id": item.get("facet_id"),
            "field_name": item.get("field_name"),
            "semantic_atom": item.get("semantic_atom"),
            "render_policy": item.get("render_policy"),
            "polarity": item.get("polarity", "unknown"),
            "conditions": list(item.get("conditions") or ()),
            "allowed_anchor_ids": list(item.get("bound_span_ids") or ()),
            "allowed_exact_excerpts": list(item.get("exact_excerpts") or ()),
            "derivation_record_ids": list(item.get("derivation_record_ids") or ()),
            "derivation_kind": item.get("derivation_kind", "direct"),
            "claim_strength": item.get("claim_strength", "descriptive"),
            "surface_mode": item.get("surface_mode", "omit_and_review"),
            "defer_reason": item.get("defer_reason", ""),
        }
        for item in (packet.get("publication_field_candidates") or ())
        if isinstance(item, Mapping)
        and not _is_implementation_trace_text(
            item.get("semantic_atom"),
            item.get("conditions"),
            item.get("exact_excerpts") or item.get("allowed_exact_excerpts"),
        )
    ]
    deferred_fields = [
        {
            "facet_id": item.get("facet_id"),
            "field_name": item.get("field_name"),
            "unsupported_atom": item.get("unsupported_atom"),
            "reason_code": item.get("reason_code"),
            "requested_search_terms": list(item.get("requested_search_terms") or ()),
        }
        for item in (packet.get("typed_field_deferred") or ())
        if isinstance(item, Mapping)
    ]
    formula_packages = _compact_formula_packages_for_llm(
        packet.get("formula_packages") or ()
    )
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
        "publication_field_candidates": field_candidates,
        "typed_field_deferred": deferred_fields,
        "formula_packages": formula_packages,
        "formula_generation_policy": packet.get(
            "formula_generation_policy",
            "consume_only" if formula_packages else "prose_only_or_request_formalizer",
        ),
        "canonical_formula_package_ids": list(
            packet.get("canonical_formula_package_ids") or ()
        ),
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


def _is_context_or_motivation_packet(packet: Mapping[str, Any]) -> bool:
    """Return True if this packet represents a motivation or context paragraph."""
    rhetorical_goal = str(packet.get("rhetorical_goal") or "").strip().casefold()
    if any(k in rhetorical_goal for k in ("motivation", "problem", "context", "background", "limitation")):
        return True
    section_id = str(packet.get("section_id") or "").strip().casefold()
    if any(k in section_id for k in ("motivation", "problem", "context", "background")):
        return True
    method_unit = packet.get("method_unit")
    if isinstance(method_unit, Mapping):
        heading = str(method_unit.get("section_heading") or method_unit.get("title") or "").strip().casefold()
        if any(k in heading for k in ("motivation", "context", "problem", "background")):
            return True
        role = str(method_unit.get("section_role") or "").strip().casefold()
        if any(k in role for k in ("motivation", "context", "problem", "background")):
            return True
    return False


def _compact_authoring_packets_v2_for_llm(
    packets: Any,
) -> list[dict[str, Any]]:
    """Expose only the ordered research-derived packet surface to the Writer.

    Dossier/source ids and audit dispositions stay in the harness-side packet
    and its persisted sidecars.  The prose Writer needs the operation shape,
    conditions, surface mode, and exact formula block, not a second unordered
    inventory of facts that could be paraphrased as prose.
    """

    if isinstance(packets, Mapping) or isinstance(packets, (str, bytes)):
        return []
    try:
        values = tuple(packets or ())
    except TypeError:
        return []

    def bounded_text(value: Any, limit: int = 360) -> str:
        """Keep organization hints bounded and clause-complete.

        Author specifications can contain an entire multi-stage design
        statement.  Passing that statement verbatim to a paragraph Writer
        makes it a tempting source of unsupported positive prose and also
        collapses otherwise separate operations.  The full statement remains
        in the harness-side facet/brief artifacts; the LLM receives only a
        short organization hint.
        """

        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        clauses = [
            item.strip()
            for item in re.split(r"(?<=[.!?;。；])\s+", text)
            if item.strip()
        ]
        if clauses and len(clauses[0]) <= limit:
            return clauses[0]
        clipped = text[:limit].rsplit(" ", 1)[0].rstrip(" ,:;-")
        return (clipped or text[:limit]).rstrip() + "…"

    def compact_target(value: Any) -> dict[str, Any]:
        row = dict(value) if isinstance(value, Mapping) else {}
        if _is_implementation_trace_text(
            row.get("semantic_atom"),
            row.get("conditions"),
            row.get("field_name"),
            row.get("paper_role"),
        ):
            return {}
        return {
            key: row[key]
            for key in (
                "target_kind", "field_name", "paper_role", "authority_lane",
                "semantic_atom", "polarity", "conditions", "surface_mode",
                "render_policy", "claim_strength",
            )
            if key in row
        }

    def compact_operation(value: Any, *, is_context: bool = False) -> dict[str, Any]:
        row = dict(value) if isinstance(value, Mapping) else {}
        predicate = str(row.get("predicate") or "").strip().casefold()
        if predicate == "author_specification":
            return {}
        if is_context:
            has_explicit_rationale = False
            for key in ("reader_facing_claim", "semantic_atom", "description", "statement"):
                text = str(row.get(key) or "").strip()
                if text:
                    has_explicit_rationale = True
                    break
            if not has_explicit_rationale:
                return {}
        compact = _project_operation_to_reader_surface(row)
        if not compact:
            return {}
        # Keep the operation surface deliberately small.  ``operation`` is a
        # semantic claim when available; the remaining fields are bounded
        # operands/conditions that let the Writer connect adjacent steps.
        if "operation" in compact:
            compact["operation"] = bounded_text(compact["operation"], 360)
        for key in ("subject", "result", "output", "return_value", "guard", "iteration_context"):
            if key in compact:
                compact[key] = bounded_text(compact[key], 240)
        for key in ("operands", "conditions", "shape_or_type_hints"):
            if key in compact:
                compact[key] = _strip_implementation_trace_values(compact[key])
                if compact[key] in ("", [], ()):
                    compact.pop(key, None)
        return compact

    def compact_config(value: Any) -> dict[str, Any]:
        row = dict(value) if isinstance(value, Mapping) else {}
        return {
            key: row[key]
            for key in (
                "configuration_id", "key", "value", "state", "conditions",
                "active", "unresolved_reason",
            )
            if key in row
        }

    def compact_formula(value: Any) -> dict[str, Any]:
        row = dict(value) if isinstance(value, Mapping) else {}
        compact = {
            key: row[key]
            for key in (
                "package_id", "purpose",
                "prose_explanation", "symbol_definitions", "symbol_table",
                "material_conditions", "assumptions", "authority_status",
                "formula_lane", "satisfied_obligation_ids",
                "consumer_paragraph_id", "semantic_formula_digest",
            )
            if key in row
        }
        package_id = str(row.get("package_id") or "").strip()
        if package_id:
            compact["placeholder"] = f"[[FORMULA:{package_id}]]"
        return compact

    def compact_method_unit(value: Any, *, is_context: bool = False) -> dict[str, Any]:
        row = dict(value) if isinstance(value, Mapping) else {}
        compact = {
            key: row[key]
            for key in (
                "reader_question", "purpose", "inputs",
                "outputs", "conditions", "shape_or_type_hints",
                "return_value_descriptors", "formula_roles", "authority",
                "intent_code_status",
            )
            if key in row
        }
        authority = str(row.get("authority") or "").strip().casefold()
        if authority == "code_equivalent":
            compact["surface_mode"] = "repository_statement"
            compact["render_policy"] = "required"
        elif authority == "mismatch_pending":
            compact["surface_mode"] = "mismatch_statement"
            compact["render_policy"] = "required"
        elif authority == "intent_specification":
            compact["surface_mode"] = "author_specification"
            compact["render_policy"] = "optional"
        if "purpose" in compact:
            compact["purpose"] = bounded_text(compact["purpose"], 320)

        def bounded_items(value: Any, limit: int = 240) -> list[str]:
            if isinstance(value, str):
                values = (value,)
            else:
                try:
                    values = tuple(value or ())
                except TypeError:
                    values = (value,)
            return [bounded_text(item, limit) for item in values if str(item or "").strip()]

        for key in ("inputs", "outputs", "conditions", "return_value_descriptors"):
            if key in compact:
                compact[key] = bounded_items(compact[key])
        if is_context:
            for key in ("inputs", "outputs", "return_value_descriptors"):
                if key in compact:
                    compact[key] = [
                        item for item in compact[key]
                        if not _is_implementation_trace_text(item)
                    ]
        intent_hints: list[str] = []
        operations: list[dict[str, Any]] = []
        operation_indexes_by_shape: dict[tuple[Any, ...], int] = {}

        def operation_display_shape(item: Mapping[str, Any]) -> tuple[Any, ...] | None:
            """Return the stable reader-operation identity for display merging.

            The private MethodUnit keeps one operation per obligation so the
            Binder can recover every target.  The Writer does not need those
            duplicate obligation rows: when the source span and operation
            shape are identical, emitting them separately encourages repeated
            sentences.  Guards/conditions are merged below rather than used
            as identity, so conditional variants remain visible to the model.
            """

            source_span = str(
                item.get("source_span_id")
                or item.get("span_id")
                or item.get("exact_span_id")
                or ""
            ).strip()
            predicate = str(item.get("predicate") or "").strip().casefold()
            if not source_span or not predicate or predicate == "author_specification":
                return None
            operands = item.get("operands") or ()
            if isinstance(operands, str):
                operands = (operands,)
            try:
                operand_shape = tuple(str(part).strip() for part in operands)
            except TypeError:
                operand_shape = (str(operands).strip(),)
            return (
                source_span,
                predicate,
                str(item.get("subject") or "").strip(),
                operand_shape,
                str(
                    item.get("result")
                    or item.get("output")
                    or item.get("return_value")
                    or ""
                ).strip(),
            )

        def merge_display_variants(
            existing: dict[str, Any],
            item: Mapping[str, Any],
        ) -> None:
            """Merge condition/shape metadata without merging semantics away."""

            def unique_texts(*values: Any) -> list[str]:
                result: list[str] = []
                for value in values:
                    if isinstance(value, str):
                        candidates = (value,)
                    else:
                        try:
                            candidates = tuple(value or ())
                        except TypeError:
                            candidates = (value,)
                    for candidate in candidates:
                        text = str(candidate or "").strip()
                        if text and text not in result:
                            result.append(text)
                return result

            merged_conditions = unique_texts(
                existing.get("conditions"),
                item.get("conditions"),
            )
            if merged_conditions:
                existing["conditions"] = merged_conditions
            merged_shapes = unique_texts(
                existing.get("shape_or_type_hints"),
                item.get("shape_or_type_hints"),
            )
            if merged_shapes:
                existing["shape_or_type_hints"] = merged_shapes
            raw_guards: list[str] = []
            if "guard" in existing:
                raw_guards.append(str(existing.get("guard") or "").strip())
            raw_guards.extend(unique_texts(existing.get("guard_variants")))
            if "guard" in item:
                raw_guards.append(str(item.get("guard") or "").strip())
            raw_guards.extend(unique_texts(item.get("guard_variants")))
            guards: list[str] = []
            for guard in raw_guards:
                normalized = "" if guard.casefold() == "unconditional" else guard
                if normalized not in guards:
                    guards.append(normalized)
            if len(guards) > 1:
                existing.pop("guard", None)
                existing["guard_variants"] = [
                    guard if guard else "unconditional"
                    for guard in guards
                ]
            elif guards:
                existing["guard"] = guards[0]

        for item in (row.get("ordered_operations") or ()):
            if not isinstance(item, Mapping):
                continue
            predicate = str(item.get("predicate") or "").strip().casefold()
            if predicate == "author_specification":
                hint = item.get("description") or item.get("statement")
                if str(hint or "").strip():
                    intent_hints.append(bounded_text(hint, 240))
                continue
            display = compact_operation(item, is_context=is_context)
            if not display:
                continue
            shape = operation_display_shape(item)
            if shape is None or shape not in operation_indexes_by_shape:
                if shape is not None:
                    operation_indexes_by_shape[shape] = len(operations)
                operations.append(display)
                continue
            merge_display_variants(operations[operation_indexes_by_shape[shape]], item)
        if intent_hints:
            compact["intent_hints"] = list(dict.fromkeys(intent_hints))
        sanitized_operations: list[dict[str, Any]] = []
        for item in operations:
            if not item:
                continue
            if "guard_variants" in item:
                variants = [
                    variant for variant in (item.get("guard_variants") or ())
                    if str(variant).strip()
                    and str(variant).casefold() != "unconditional"
                    and not _is_implementation_trace_text(variant)
                ]
                if variants:
                    item["guard_variants"] = variants
                else:
                    item.pop("guard_variants", None)
            if "guard" in item and _is_implementation_trace_text(item.get("guard")):
                item.pop("guard", None)
            if "conditions" in item:
                item["conditions"] = _strip_implementation_trace_values(item["conditions"])
                if item["conditions"] in ("", [], ()):
                    item.pop("conditions", None)
            sanitized_operations.append(item)
        compact["ordered_operations"] = sanitized_operations
        return compact

    compact_packets: list[dict[str, Any]] = []
    for packet in values:
        row = dict(packet) if isinstance(packet, Mapping) else {}
        is_context = _is_context_or_motivation_packet(row)
        dossier = row.get("dossier_summary")
        dossier_row = dict(dossier) if isinstance(dossier, Mapping) else {}
        raw_dossier_operations = [
            item for item in (dossier_row.get("operation_atoms") or ())
            if isinstance(item, Mapping)
        ]
        method_unit = row.get("method_unit")
        has_primary_operation_chain = bool(
            isinstance(method_unit, Mapping)
            and any(
                isinstance(item, Mapping)
                and str(item.get("predicate") or "").strip().casefold()
                != "author_specification"
                for item in (method_unit.get("ordered_operations") or ())
            )
        )
        compact_dossier = {
            # MethodUnit is the ordered paragraph source.  Repeating its
            # complete dossier chain created a second unordered inventory in
            # the model context and encouraged the Writer to blend spans from
            # neighboring components.  Keep the count for audit-free context
            # sizing, but expose the raw chain only when no MethodUnit chain
            # exists (legacy/intent-only packets).
            "operation_atoms": (
                [] if has_primary_operation_chain else [
                    op for item in raw_dossier_operations
                    if (op := compact_operation(item, is_context=is_context))
                ]
            ),
            "operation_atom_count": len(raw_dossier_operations),
            "default_activation": dossier_row.get("default_activation", "unknown"),
            "active_path_conditions": list(
                dossier_row.get("active_path_conditions") or ()
            ),
            "call_path_length": len(dossier_row.get("call_path_relation_ids") or ()),
            "data_flow_length": len(dossier_row.get("data_flow_relation_ids") or ()),
            "control_flow_length": len(dossier_row.get("control_flow_relation_ids") or ()),
            "unresolved_relation_count": len(dossier_row.get("unresolved_relations") or ()),
        }
        compact_packet = {
            "schema_version": row.get("schema_version", "2.0"),
            "section_id": row.get("section_id", ""),
            "paragraph_id": row.get("paragraph_id", ""),
            "rhetorical_goal": bounded_text(row.get("rhetorical_goal", ""), 240),
            "expected_sentence_range": list(
                row.get("expected_sentence_range") or (1, 4)
            ),
            "ordered_targets": [
                compact_target(item)
                for item in (row.get("ordered_targets") or ())
                if isinstance(item, Mapping) and compact_target(item)
            ],
            "dossier_summary": compact_dossier,
            "material_conditions": list(row.get("material_conditions") or ()),
            "configuration_state": [
                compact_config(item)
                for item in (row.get("configuration_state") or ())
                if isinstance(item, Mapping)
            ],
            "formula_packages": [
                compact_formula(item)
                for item in (row.get("formula_packages") or ())
                if isinstance(item, Mapping)
            ],
            "formula_generation_policy": row.get(
                "formula_generation_policy",
                "consume_only"
                if row.get("formula_packages")
                else "prose_only_or_request_formalizer",
            ),
            "canonical_formula_package_ids": list(
                row.get("canonical_formula_package_ids") or ()
            ),
            "preceding_paragraph_id": row.get("preceding_paragraph_id", ""),
            "following_paragraph_id": row.get("following_paragraph_id", ""),
        }
        if isinstance(method_unit, Mapping) and method_unit:
            compact_packet["method_unit"] = compact_method_unit(method_unit, is_context=is_context)
        compact_packets.append(compact_packet)
    return compact_packets


def _llm_visible_section_payload(section: WriterSectionInput) -> dict[str, Any]:
    """Keep low-level evidence machinery out of the Writer prose context.

    The omitted fields remain on ``WriterSectionInput.prompt_payload`` for
    deterministic validation and binding.  New proposition-backed calls
    receive only the compact four-layer ``writer_view``, their scoped callback
    state and bounded repair feedback.  Claim/fact/frame/equation/configuration
    IDs and move proofs are harness-private.
    """

    v2_packets = section.prompt_payload.get("authoring_packets_v2")
    if v2_packets:
        # Slice 3: the V2 packet is the single Writer organization surface.
        # Formula packages and target ids are closed response bindings; exact
        # witnesses are deliberately absent because the separate Binder adds
        # them only after prose has been frozen.  Keep callback/repair state
        # scoped to the same section without reintroducing the legacy fact
        # projections.
        result: dict[str, Any] = {
            "section_id": section.prompt_payload.get("section_id", section.section_id),
            "heading": section.prompt_payload.get("heading", section.heading),
            "authoring_packets_v2": _compact_authoring_packets_v2_for_llm(
                v2_packets
            ),
        }
        for key in (
            "required_qualifier_bindings",
            "writing_research_callback_artifacts",
            "writing_research_callback_resolution",
            "previous_attempt_error",
            "previous_attempt_section_markdown",
            "callback_owner_retry_instruction",
            "writer_section_repair",
            "writer_facet_coverage_repair",
        ):
            if key in section.prompt_payload:
                result[key] = section.prompt_payload[key]
        repair = result.get("writer_facet_coverage_repair")
        if isinstance(repair, Mapping):
            result["writer_facet_coverage_repair"] = _compact_writer_facet_coverage_repair_for_llm(
                repair
            )
        return result
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
    if "formula_packages" in result:
        result["formula_packages"] = _compact_formula_packages_for_llm(
            result["formula_packages"]
        )
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
    rendered_field_candidates: set[str] = set()
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
        rendered_field_candidates.update(str(v) for v in part.rendered_field_candidate_ids)
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
            "rendered_field_candidate_ids": tuple(sorted(rendered_field_candidates)),
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
    accepted_response_sink: Callable[[WriterSectionInput, LLMResponse], None] | None = None,
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
        if not isinstance(writer_view, dict):
            # V2 packets are the primary LLM organization surface and are
            # intentionally stripped of the full WriterView.  A transaction
            # failure still needs a Writer-owned content repair path, so
            # derive a compact repair-only view from the original private
            # input.  This view carries gists and closed facet ids, never
            # source spans or new authority.
            original_writer_view = section.prompt_payload.get("writer_view")
            if isinstance(original_writer_view, Mapping):
                writer_view = _compact_writer_view_for_llm(original_writer_view)
        if isinstance(writer_view, dict):
            visible_formula_obligations = (
                repair_input_payload.get("formula_obligations")
                or section.prompt_payload.get("formula_obligations")
                or writer_view.get("formula_obligations")
                or ()
            )
            visible_formula_packages = (
                writer_view.get("formula_packages")
                or section.prompt_payload.get("formula_packages")
                or (
                    (writer_view.get("mechanism_authoring_packet") or {}).get(
                        "formula_packages"
                    )
                    if isinstance(writer_view.get("mechanism_authoring_packet"), Mapping)
                    else ()
                )
                or ()
            )
            writer_view = {
                **writer_view,
                "formula_obligations": list(visible_formula_obligations),
                "formula_packages": _compact_formula_packages_for_llm(
                    visible_formula_packages
                ),
            }
        transaction_failure = _is_writer_content_repairable_failure(
            accepted_response.blocked_reason
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
                rendered_formula_package_ids=(
                    _response_rendered_formula_package_ids(accepted_response)
                    if visible_formula_packages else None
                ),
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
                    paragraph_transaction_repairs=(
                        _publication_paragraph_repair_contract(
                            section,
                            accepted_response,
                        )
                    ),
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
                # A paragraph-level repair is evaluated against the same
                # section transaction as its incumbent.  Preserve valid
                # siblings before scoring so a focused retry cannot appear to
                # regress merely because it omitted untouched paragraphs.
                repair_response = _merge_publication_repair_response(
                    section,
                    accepted_response,
                    repair_response,
                )
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
                repair_transaction_failure = _is_writer_content_repairable_failure(
                    repair_response.blocked_reason
                )
                if (
                    (repair_response.blocked_reason and not repair_transaction_failure)
                    or not (repair_response.text or "").strip()
                ):
                    break
                candidate_progress, candidate_failures = assess_writer_section_progress(
                    repair_response.text or "",
                    writer_view=writer_view,
                    rendered_proposition_ids=(),
                    rendered_formula_package_ids=(
                        _response_rendered_formula_package_ids(repair_response)
                        if visible_formula_packages else None
                    ),
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
                            "incumbent_metrics": dict(vars(incumbent_progress)),
                            "candidate_metrics": dict(vars(candidate_progress)),
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
                    # The typed failure that entered this bounded repair loop
                    # belongs to the rejected representation/content attempt,
                    # not to a candidate whose merged paragraph transaction
                    # has now been accepted.  Keep the response immutable
                    # while clearing only this repair-owned marker; unknown
                    # authority/research failures are stopped above and never
                    # reach this branch.
                    if repair_response.blocked_reason and repair_transaction_failure:
                        repair_response = replace(repair_response, blocked_reason=None)
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
        if accepted_response_sink is not None:
            accepted_response_sink(section, accepted_response)
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
                    ("rendered_field_candidate_ids", "required_field_candidate_ids"),
                    # ``ordered_semantic_slot_ids`` is Writer grounding and
                    # may contain support slots.  Only the explicit
                    # publication subset is a renderable paragraph target;
                    # otherwise native decoding exposes support ids and the
                    # model can declare a non-publication slot that the
                    # transaction contract must later reject.
                    ("rendered_slot_ids", "required_publication_slot_ids"),
                    ("rendered_edge_ids", "required_edge_ids"),
                    ("used_formula_package_ids", "formula_obligation_ids"),
                ):
                    field_schema = paragraph_properties.get(field_name)
                    if not isinstance(field_schema, dict):
                        continue
                    values = list(dict.fromkeys(
                        str(value)
                        for item in paragraph_plans
                        for value in (
                            item.get(plan_key)
                            or (item.get("ordered_semantic_slot_ids")
                                if plan_key == "required_publication_slot_ids"
                                and "required_publication_slot_ids" not in item
                                else ())
                            or ()
                        )
                        if str(value).strip()
                    ))
                    if field_name == "rendered_field_candidate_ids":
                        # Keep the enum paragraph-local.  The packet may
                        # contain candidates for several paragraphs, but a
                        # transaction must not bind a sibling field merely
                        # because its id is visible in the section packet.
                        if not any(
                            "required_field_candidate_ids" in item
                            for item in paragraph_plans
                            if isinstance(item, dict)
                        ):
                            values.extend(
                                str(item.get("candidate_id") or "")
                                for item in (
                                    ((mechanism_packet_early or {}).get("publication_field_candidates") or ())
                                    if isinstance(mechanism_packet_early, dict)
                                    else ()
                                )
                                if isinstance(item, dict) and str(item.get("candidate_id") or "").strip()
                            )
                            values = list(dict.fromkeys(values))
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
                if paragraph_transaction_required:
                    # Paragraph transactions are prose-first.  Internal
                    # facet/field/slot/edge/package ids belong to the
                    # MethodUnit sidecar and Binder, not to the Writer's
                    # response contract.  A package placeholder is still
                    # allowed in prose; the harness restores its package id
                    # after verbatim splicing.
                    for field_name in (
                        "rendered_from_facet_ids",
                        "rendered_field_candidate_ids",
                        "rendered_slot_ids",
                        "rendered_edge_ids",
                        "used_formula_package_ids",
                    ):
                        field_schema = paragraph_properties.get(field_name)
                        if not isinstance(field_schema, dict):
                            continue
                        field_schema.pop("minItems", None)
                        field_schema["maxItems"] = 0
                        field_schema["items"] = {"type": "string"}
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
        ("rendered_field_candidate_ids", "allowed_field_candidate_ids"),
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
    if paragraph_transaction_required:
        # Section-level aggregate ids are also reconstructed from the
        # paragraph transactions after Binder validation.  Keep only the
        # paragraph ids visible to the Writer; all other internal ids are
        # sidecar state.  This block follows the legacy facet/slot schema
        # loops so their enums cannot overwrite the prose-first contract.
        for field_name in (
            "rendered_from_facet_ids",
            "rendered_field_candidate_ids",
            "rendered_slot_ids",
            "rendered_edge_ids",
            "used_formula_package_ids",
        ):
            field_schema = properties.get(field_name)
            if not isinstance(field_schema, dict):
                continue
            field_schema.pop("minItems", None)
            field_schema["maxItems"] = 0
            field_schema["items"] = {"type": "string"}
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
        *(("rendered_from_facet_ids", "rendered_field_candidate_ids", "deferred_facet_ids") if facet_mode else ()),
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
            "rendered_field_candidate_ids",
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


_PUBLICATION_BINDER_PROMPT = """
You are the metadata-only Paragraph Evidence Binder.

The paragraph_markdown in the input is frozen Writer prose. Return only the
PublicationParagraphBindingResponseV1 object. For every supplied target,
either copy one exact unique substring that already occurs in that paragraph
or list the target as unbound. Do not rewrite, summarize, or add prose. Do not
bind a target when its semantic atom, required condition, polarity, or formula
block is absent. Formula witnesses must be copied exactly from the supplied
formula block as it appears in the paragraph. Use the supplied kind:target
format in unbound_target_ids. Rendered ids may already include their kind
prefix, so a target such as slot:fact-X may appear as slot:fact-X or
slot:slot:fact-X; only a form that resolves to a supplied target is valid.
Relation targets use witness_kind edge even when their target_id begins with
rel:, so report that supplied relation target exactly when it is unbound.
Never invent target ids or witness text.
""".strip()


def _merge_publication_binder_witnesses(
    transaction: PublicationMethodParagraphOutputV1,
    witnesses: Iterable[Mapping[str, str]],
    *,
    plan_row: Mapping[str, Any] | None = None,
    formula_packages: tuple[Mapping[str, Any], ...] = (),
) -> PublicationMethodParagraphOutputV1:
    """Add only already-validated Binder metadata to a frozen transaction.

    The plan/MethodUnit sidecar is the authority for ids.  Once the shared
    Binder contract has validated a witness against that sidecar, restoring
    its declaration in the transaction is a representation repair, not a
    model-authorized content binding.
    """

    source = transaction.model_dump(mode="json")
    validated = tuple(witnesses)
    existing = list(source.get("witnesses") or ())
    existing_keys = {
        (
            str(item.get("witness_kind") or ""),
            str(item.get("target_id") or ""),
        )
        for item in existing
        if isinstance(item, Mapping)
    }
    for witness in validated:
        key = (
            str(witness.get("witness_kind") or ""),
            str(witness.get("target_id") or ""),
        )
        if not all(key) or key in existing_keys:
            continue
        existing.append({
            "witness_kind": key[0],
            "target_id": key[1],
            "exact_text": str(witness.get("exact_text") or ""),
        })
        existing_keys.add(key)
    authorized_by_kind: dict[str, set[str]] = {}
    from code2paper.agentic.publication_transaction_contract import (
        paragraph_binding_targets,
    )
    for row in paragraph_binding_targets(
        transaction,
        plan_row=plan_row,
        formula_packages=formula_packages,
    ):
        authorized_by_kind.setdefault(str(row["witness_kind"]), set()).add(
            str(row["target_id"])
        )
    declaration_fields = {
        "facet": "rendered_from_facet_ids",
        "field": "rendered_field_candidate_ids",
        "slot": "rendered_slot_ids",
        "edge": "rendered_edge_ids",
        "formula": "used_formula_package_ids",
        "claim": "used_claim_ids",
        "equation": "used_equation_ids",
    }
    for raw in validated:
        kind = str(raw.get("witness_kind") or "").strip()
        target_id = str(raw.get("target_id") or "").strip()
        if target_id not in authorized_by_kind.get(kind, set()):
            continue
        field_name = declaration_fields.get(kind)
        if field_name:
            values = list(source.get(field_name) or ())
            if target_id not in values:
                values.append(target_id)
            source[field_name] = values
    source["witnesses"] = existing
    return transaction.__class__.model_validate(source)


def _invoke_publication_paragraph_binder(
    transaction: PublicationMethodParagraphOutputV1,
    *,
    plan_row: Mapping[str, Any],
    formula_packages: tuple[Mapping[str, Any], ...],
    binder_caller: _LLMCaller | None,
    binder_base_config: LLMConfig | None,
    call_id: str,
    trace_sink: list[GenerationCallTrace] | None = None,
    recovery_sink: list[dict[str, Any]] | None = None,
) -> PublicationMethodParagraphOutputV1:
    """Run at most one low-temperature Binder retry after deterministic match.

    This function is intentionally scoped to metadata. It never receives a
    prose-writing instruction and it only merges witnesses after the shared
    transaction contract validates every returned substring.
    """

    if binder_caller is None or binder_base_config is None:
        return transaction
    from code2paper.agentic.publication_transaction_contract import (
        paragraph_binding_targets,
        validate_paragraph_binding_response,
    )

    targets = paragraph_binding_targets(
        transaction,
        plan_row=plan_row,
        formula_packages=formula_packages,
    )
    if not targets:
        return transaction
    paragraph_id = str(transaction.paragraph_id or "").strip()
    body = str(transaction.paragraph_markdown or "")
    binder_config = apply_role_config(
        binder_base_config,
        SEMANTIC_VERIFIER,
    ).model_copy(update={
        "temperature": 0.0,
        "reasoning_effort": "none",
        "thinking_token_budget": None,
        "max_output_tokens": min(
            1536,
            apply_role_config(
                binder_base_config,
                SEMANTIC_VERIFIER,
            ).max_output_tokens,
        ),
    })
    base_payload: dict[str, Any] = {
        "paragraph_id": paragraph_id,
        "paragraph_markdown": body,
        "target_contracts": list(targets),
    }
    last_errors: tuple[str, ...] = ()
    for attempt in (1, 2):
        payload = dict(base_payload)
        if last_errors:
            payload["previous_attempt_error"] = list(last_errors)
        request = LLMRequest(
            prompt_template_id="phase5_publication_paragraph_binder_v1",
            prompt=_PUBLICATION_BINDER_PROMPT,
            input_payload=payload,
            schema_name=PUBLICATION_PARAGRAPH_BINDING_SCHEMA,
            response_json_schema=json_schema_for(
                PublicationParagraphBindingResponseV1
            ),
        )
        response = _safe_call(binder_caller, binder_config, request)
        if trace_sink is not None:
            trace_sink.append(build_generation_call_trace(
                call_id=f"{call_id}-binder-{attempt}",
                config=binder_config,
                request=request,
                response=response,
            ))
        parsed, recovery, parse_error = try_parse_structured_response_with_trace(
            response.text,
            PublicationParagraphBindingResponseV1,
        )
        record: dict[str, Any] = {
            "paragraph_id": paragraph_id,
            "attempt": attempt,
            "response_blocked_reason": str(response.blocked_reason or ""),
            "parsed": parsed is not None,
            "parse_error": str(parse_error or ""),
        }
        if parsed is None:
            record["validation_errors"] = ["binder_schema_failed"]
            if recovery_sink is not None:
                recovery_sink.append(record)
            last_errors = ("binder_schema_failed",)
            continue
        valid, errors, unbound = validate_paragraph_binding_response(
            parsed,
            transaction,
            plan_row=plan_row,
            formula_packages=formula_packages,
        )
        record.update({
            "bound_count": len(valid),
            "unbound_count": len(unbound),
            "validation_errors": list(errors),
        })
        if recovery_sink is not None:
            recovery_sink.append(record)
        if not errors:
            return _merge_publication_binder_witnesses(
                transaction,
                valid,
                plan_row=plan_row,
                formula_packages=formula_packages,
            )
        last_errors = errors
    return transaction


def _recover_exact_formula_block_representation(
    transaction: PublicationMethodParagraphOutputV1,
    *,
    missing_failures: Iterable[str],
    formula_packages: Iterable[Mapping[str, Any]],
) -> tuple[PublicationMethodParagraphOutputV1, tuple[str, ...]]:
    """Recover a lost placeholder when the exact canonical block is present.

    The Writer is allowed to lose the placeholder as a representation detail,
    but it is not allowed to change formula content.  Recovery therefore
    requires one owning accepted package and one byte-identical canonical
    block occurring exactly once in the paragraph.  The Harness restores the
    package witness from its private sidecar; no approximate or newly authored
    formula is accepted.
    """

    missing_ids = tuple(dict.fromkeys(
        str(value).split("formula_placeholder_missing:", 1)[1].strip()
        for value in (missing_failures or ())
        if str(value).startswith("formula_placeholder_missing:")
        and str(value).split("formula_placeholder_missing:", 1)[1].strip()
    ))
    if not missing_ids:
        return transaction, ()
    packages_by_id = {
        str(package.get("package_id") or "").strip(): package
        for package in formula_packages
        if isinstance(package, Mapping)
        and str(package.get("package_id") or "").strip()
    }
    body = str(transaction.paragraph_markdown or "")
    witnesses = [
        item.model_dump(mode="json")
        for item in (transaction.witnesses or ())
    ]
    used_formula_ids = [
        str(value).strip()
        for value in (transaction.used_formula_package_ids or ())
        if str(value).strip()
    ]
    recovered: list[str] = []
    for package_id in missing_ids:
        package = packages_by_id.get(package_id)
        if package is None:
            continue
        if str(package.get("authority_status") or "").strip() != "code_verified":
            continue
        if str(package.get("formula_lane") or "").strip() != "repository_derived":
            continue
        if str(package.get("review_status") or "").strip() != "accepted":
            continue
        if str(package.get("consumer_paragraph_id") or "").strip() != str(
            transaction.paragraph_id or ""
        ).strip():
            continue
        block = str(package.get("markdown_block") or "")
        latex = str(package.get("latex") or "").strip()
        # Keep this import local to avoid the section-writer/contract import
        # cycle at module load time.
        from code2paper.agentic.publication_transaction_contract import _DISPLAY_MATH_RE

        if block and body.count(block) == 1:
            pass
        elif latex and body.count(latex) == 1 and (not block or block not in body):
            canonical = block if _DISPLAY_MATH_RE.search(block or "") else f"$$\n{latex}\n$$"
            if not _DISPLAY_MATH_RE.search(canonical):
                continue
            body = body.replace(latex, canonical, 1)
            block = canonical
        else:
            continue
        if not _DISPLAY_MATH_RE.search(block):
            continue
        obligation_ids = {
            str(package.get("obligation_id") or "").strip(),
            *(
                str(value).strip()
                for value in (package.get("satisfied_obligation_ids") or ())
                if str(value).strip()
            ),
        }
        replaced = False
        normalized_witnesses: list[dict[str, str]] = []
        for witness in witnesses:
            kind = str(witness.get("witness_kind") or "").strip()
            target_id = str(witness.get("target_id") or "").strip()
            if kind == "formula" and target_id in {package_id, *obligation_ids}:
                if not replaced:
                    normalized_witnesses.append({
                        "witness_kind": "formula",
                        "target_id": package_id,
                        "exact_text": block,
                    })
                    replaced = True
                continue
            normalized_witnesses.append(witness)
        if not replaced:
            normalized_witnesses.append({
                "witness_kind": "formula",
                "target_id": package_id,
                "exact_text": block,
            })
        witnesses = normalized_witnesses
        if package_id not in used_formula_ids:
            used_formula_ids.append(package_id)
        recovered.append(package_id)

    if not recovered:
        return transaction, ()
    payload = transaction.model_dump(mode="json")
    payload.update({
        "paragraph_markdown": body,
        "used_formula_package_ids": list(dict.fromkeys(used_formula_ids)),
        "witnesses": witnesses,
    })
    return transaction.__class__.model_validate(payload), tuple(
        dict.fromkeys(recovered)
    )


def normalize_publication_heading(text: Any) -> str:
    """Normalize a structural publication heading without touching body text.

    A trailing colon is a common truncation artifact in generated H2/H3
    headings.  Strip only that structural suffix; colons in the paragraph body
    and in inline prose remain untouched.
    """

    value = " ".join(str(text or "").split()).strip()
    if value.startswith("#"):
        value = value.lstrip("#").strip()
    return value.rstrip(":").rstrip()


def _assembled_section_heading(
    section: WriterSectionInput,
    output: PublicationMethodSectionOutputV1,
) -> str:
    """Keep Architect headings except a validated repair of a truncated H2."""

    from code2paper.agentic.publication_quality import (
        heading_is_truncated,
        heading_replacement_is_coherent,
    )

    def _clean(value: Any) -> str:
        text = " ".join(str(value or "").split()).strip()
        if text.startswith("#"):
            text = text.lstrip("#").strip()
        return text

    planned = normalize_publication_heading(_clean(section.heading))
    written = normalize_publication_heading(_clean(getattr(output, "heading_text", "")))
    if not written:
        markdown = str(getattr(output, "section_markdown", "") or "")
        first = next((line.strip() for line in markdown.splitlines() if line.strip()), "")
        if first.startswith("#"):
            written = normalize_publication_heading(_clean(first))
    if (
        planned
        and written
        and heading_is_truncated(planned)
        and heading_replacement_is_coherent(written, planned_heading=planned)
    ):
        return normalize_publication_heading(written)
    return normalize_publication_heading(planned or written)


def _normalize_publication_paragraph_transaction(
    output: PublicationMethodSectionOutputV1,
    *,
    section: WriterSectionInput,
    require_transactions: bool = False,
    binder_caller: _LLMCaller | None = None,
    binder_base_config: LLMConfig | None = None,
    binder_trace_sink: list[GenerationCallTrace] | None = None,
    binder_recovery_sink: list[dict[str, Any]] | None = None,
    binder_call_id_prefix: str = "LLM-publication-paragraph-binder",
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
        "rendered_field_candidate_ids": set(),
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
        # Stage B Binder: select exact substrings from the frozen Writer body
        # before any transaction assessment.  The Binder is representation
        # metadata only; it cannot change the paragraph or introduce ids.
        from code2paper.agentic.publication_transaction_contract import (
            bind_paragraph_witnesses,
        )
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
        section_field_candidate_ids = {
            str(item.get("candidate_id") or "")
            for item in (packet.get("publication_field_candidates") or ())
            if isinstance(item, Mapping) and str(item.get("candidate_id") or "").strip()
        }
        section_formula_package_ids = {
            str(item.get("package_id") or "")
            for item in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(item, dict) and str(item.get("package_id") or "").strip()
        }
        formula_packages = tuple(
            item for item in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(item, Mapping)
        )
        transaction = bind_paragraph_witnesses(
            transaction,
            plan_row=plan_row,
            formula_packages=formula_packages,
        )
        transaction = _invoke_publication_paragraph_binder(
            transaction,
            plan_row=plan_row,
            formula_packages=formula_packages,
            binder_caller=binder_caller,
            binder_base_config=binder_base_config,
            call_id=(
                f"{binder_call_id_prefix}-{section.section_id}-{paragraph_id}"
            ),
            trace_sink=binder_trace_sink,
            recovery_sink=binder_recovery_sink,
        )
        # Keep the normalized transaction in the output even when a sibling
        # paragraph later fails.  Returning the original section object on a
        # partial failure would silently discard safe Binder witnesses from
        # the Candidate checkpoint.
        by_id[paragraph_id] = transaction
        body = transaction.paragraph_markdown.strip()
        plan_field_ids = set(str(value) for value in (plan_row.get("required_field_candidate_ids") or ()))
        plan_facet_ids = set(str(value) for value in (plan_row.get("required_facet_ids") or ()))
        plan_formula_ids = set(str(value) for value in (plan_row.get("formula_obligation_ids") or ()))
        if "required_field_candidate_ids" in plan_row:
            allowed_field_ids = plan_field_ids
        else:
            allowed_field_ids = plan_field_ids | section_field_candidate_ids
        if "required_facet_ids" in plan_row:
            allowed_facet_ids = plan_facet_ids
        else:
            allowed_facet_ids = plan_facet_ids | section_facet_ids
        route_packages = {
            str(package.get("package_id") or "")
            for package in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(package, Mapping)
            and str(package.get("package_id") or "").strip()
            and (
                not plan_formula_ids
                or (
                    bool(
                        plan_formula_ids.intersection(
                            {
                                str(item).strip()
                                for item in (package.get("satisfied_obligation_ids") or ())
                                if str(item).strip()
                            }
                            | (
                                {str(package.get("obligation_id") or "").strip()}
                                if str(package.get("obligation_id") or "").strip()
                                else set()
                            )
                        )
                    )
                    and str(package.get("consumer_paragraph_id") or "").strip()
                    == paragraph_id
                )
            )
        }
        allowed = {
            "facet": allowed_facet_ids,
            "field": allowed_field_ids,
            "slot": set(str(value) for value in (
                plan_row.get("required_publication_slot_ids")
                if "required_publication_slot_ids" in plan_row
                else plan_row.get("ordered_semantic_slot_ids")
                or ()
            )),
            "edge": set(str(value) for value in (plan_row.get("required_edge_ids") or ())),
            "formula": (
                plan_formula_ids
                | (route_packages if plan_formula_ids else section_formula_package_ids)
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
            ("rendered_field_candidate_ids", "field"),
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
            required_anchors_from_plan_row,
        )
        formula_packages = tuple(
            package for package in (section.prompt_payload.get("formula_packages") or ())
            if isinstance(package, Mapping)
        )
        has_explicit_package_routes = any(
            str(package.get("obligation_id") or "").strip()
            or bool(package.get("satisfied_obligation_ids"))
            for package in formula_packages
        )

        def _packages_for_obligation(obligation: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            exact = tuple(
                package for package in formula_packages
                if obligation_id in {
                    *(
                        str(item).strip()
                        for item in (package.get("satisfied_obligation_ids") or ())
                        if str(item).strip()
                    ),
                    *(
                        [str(package.get("obligation_id") or "").strip()]
                        if str(package.get("obligation_id") or "").strip()
                        else []
                    ),
                }
            )
            if exact or has_explicit_package_routes:
                return exact
            facet_ids = set(str(item) for item in (obligation.get("facet_ids") or ()))
            return tuple(
                package for package in formula_packages
                if not facet_ids
                or facet_ids.intersection(
                    set(str(item) for item in (package.get("bound_facet_ids") or ()))
                )
            )

        formula_routes = {}
        for obligation in (section.prompt_payload.get("formula_obligations") or ()):
            if not isinstance(obligation, Mapping):
                continue
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            if not obligation_id:
                continue
            matches = _packages_for_obligation(obligation)
            formula_routes[obligation_id] = {
                "package_ids": tuple(
                    str(package.get("package_id") or "")
                    for package in matches
                    if str(package.get("package_id") or "").strip()
                ),
                "latex": (
                    str(matches[0].get("latex") or matches[0].get("markdown_block") or "")
                    if matches else ""
                ),
            }
        # A Writer may not silently drop an accepted package.  A typed
        # disposition is allowed only for a package owned by this paragraph;
        # required obligations still need ``consumed`` and an exact formula
        # witness.  The singular field is a compact one-package compatibility
        # form; the plural form is authoritative when present.
        disposition_rows = [
            item.model_dump(mode="json")
            for item in (getattr(transaction, "formula_dispositions", ()) or ())
            if hasattr(item, "model_dump")
        ]
        singular_disposition = getattr(transaction, "formula_disposition", None)
        if singular_disposition:
            owned_package_ids = tuple(
                package_id for package_id in route_packages
                if package_id in section_formula_package_ids
            )
            if not owned_package_ids and not section_formula_package_ids:
                # A review-required or not-applicable Formalizer outcome is
                # intentionally absent from the Writer package set.  Ignore
                # a stale optional disposition field; no package id or
                # formula target can be granted by this branch.
                pass
            elif len(owned_package_ids) != 1:
                failures.append(
                    f"formula_disposition_package_ambiguous:{paragraph_id}"
                )
            else:
                disposition_rows.append({
                    "package_id": owned_package_ids[0],
                    "disposition": singular_disposition,
                    "reason": str(
                        getattr(transaction, "formula_disposition_reason", "") or ""
                    ),
                })
        disposition_by_package: dict[str, str] = {}
        for row in disposition_rows:
            package_id = str(row.get("package_id") or "").strip()
            disposition = str(row.get("disposition") or "").strip()
            if package_id not in allowed["formula"]:
                failures.append(
                    f"unknown_formula_disposition:{paragraph_id}:{package_id}"
                )
                continue
            if package_id in disposition_by_package:
                failures.append(
                    f"duplicate_formula_disposition:{paragraph_id}:{package_id}"
                )
                continue
            disposition_by_package[package_id] = disposition
            if disposition == "consumed" and package_id not in set(
                transaction.used_formula_package_ids
            ):
                failures.append(
                    f"consumed_formula_not_declared:{paragraph_id}:{package_id}"
                )
        required_package_ids: set[str] = set()
        for obligation in (section.prompt_payload.get("formula_obligations") or ()):
            if not isinstance(obligation, Mapping):
                continue
            if str(obligation.get("expectation") or "required") != "required":
                continue
            obligation_id = str(obligation.get("obligation_id") or "").strip()
            required_package_ids.update(
                str(package.get("package_id") or "").strip()
                for package in formula_packages
                if obligation_id in {
                    *(
                        str(item).strip()
                        for item in (package.get("satisfied_obligation_ids") or ())
                        if str(item).strip()
                    ),
                    *(
                        [str(package.get("obligation_id") or "").strip()]
                        if str(package.get("obligation_id") or "").strip()
                        else []
                    ),
                }
                and str(package.get("package_id") or "").strip()
            )
        for package_id, disposition in disposition_by_package.items():
            if package_id in required_package_ids and disposition != "consumed":
                failures.append(
                    f"required_formula_disposition_not_consumed:{paragraph_id}:{package_id}"
                )
        assessment = assess_paragraph_transaction(
            transaction,
            plan_row=plan_row,
            formula_routes=formula_routes,
            required_anchors=required_anchors_from_plan_row(plan_row),
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
        heading = _assembled_section_heading(section, output)
        section_markdown = "\n\n".join(assembled_parts)
        if heading and section_markdown:
            section_markdown = f"## {heading}\n\n{section_markdown}"
        preserved = output.model_copy(update={
            "section_markdown": section_markdown or output.section_markdown,
            "paragraphs": [
                by_id[item_id]
                for item_id in (expected_ids or tuple(by_id))
                if item_id in by_id
            ],
        })
        return preserved, list(dict.fromkeys(failures))
    # Section structure is owned by the Architect, not by whichever
    # paragraph happens to be emitted first.  Assemble exactly one H2 here
    # and keep each transaction's body substantive; this makes the reverse
    # validator see the same heading/paragraph boundary on every retry.
    heading = _assembled_section_heading(section, output)
    section_markdown = "\n\n".join(assembled_parts)
    if heading:
        section_markdown = f"## {heading}\n\n{section_markdown}"
    return output.model_copy(update={
        "section_markdown": section_markdown,
        "paragraphs": [
            by_id[item_id]
            for item_id in (expected_ids or tuple(by_id))
            if item_id in by_id
        ],
        "rendered_paragraph_ids": list(expected_ids or tuple(by_id)),
        "rendered_from_facet_ids": sorted(aggregate_fields["rendered_from_facet_ids"]),
        "rendered_field_candidate_ids": sorted(aggregate_fields["rendered_field_candidate_ids"]),
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
    accepted_outputs_by_section: dict[str, PublicationMethodSectionOutputV1] = {}
    recovery_traces: list[dict[str, Any]] = []
    binder_traces: list[GenerationCallTrace] = []

    def capture_accepted_response(
        section: WriterSectionInput,
        response: LLMResponse,
    ) -> None:
        metadata = response.metadata
        if isinstance(metadata, PublicationMethodSectionOutputV1):
            accepted_outputs_by_section[section.section_id] = metadata.model_copy(
                update={"section_id": section.section_id}
            )

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
        # A content repair is allowed to return only the failed paragraph(s).
        # The outer Writer loop merges that representation with the incumbent
        # section; the normal first-pass contract still requires every planned
        # paragraph.
        content_repair_request = isinstance(
            request.input_payload.get("writer_section_repair"), Mapping
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
        formula_placeholder_failures: list[str] = []
        if (
            isinstance(private_payload, dict)
            and private_payload.get("formula_placeholders_required")
        ):
            from code2paper.agentic.publication_transaction_contract import (
                splice_formula_placeholders,
            )

            formula_packages = tuple(
                item for item in (private_payload.get("formula_packages") or ())
                if isinstance(item, Mapping)
            )
            package_ids = {
                str(item.get("package_id") or "").strip()
                for item in formula_packages
                if str(item.get("package_id") or "").strip()
            }
            paragraph_owner_ids: dict[str, set[str]] = {}
            for package in formula_packages:
                package_id = str(package.get("package_id") or "").strip()
                consumer_id = str(package.get("consumer_paragraph_id") or "").strip()
                if not package_id:
                    formula_placeholder_failures.append("formula_package_id_missing")
                if not consumer_id:
                    formula_placeholder_failures.append(
                        f"formula_package_without_consumer:{package_id or 'unknown'}"
                    )
                paragraph_owner_ids.setdefault(consumer_id, set()).add(package_id)
            parsed_transactions = list(parsed.paragraphs or ())
            parsed_ids = {
                str(item.paragraph_id or "").strip() for item in parsed_transactions
            }
            for consumer_id in paragraph_owner_ids:
                if (
                    consumer_id
                    and consumer_id not in parsed_ids
                    and not content_repair_request
                ):
                    formula_placeholder_failures.append(
                        f"formula_package_consumer_missing:{consumer_id}"
                    )
            replaced_transactions: list[PublicationMethodParagraphOutputV1] = []
            for transaction in parsed_transactions:
                paragraph_id = str(transaction.paragraph_id or "").strip()
                replaced, failures = splice_formula_placeholders(
                    transaction.paragraph_markdown,
                    formula_packages,
                    required_package_ids=paragraph_owner_ids.get(paragraph_id, ()),
                    allowed_package_ids=paragraph_owner_ids.get(paragraph_id, ()),
                )
                if failures:
                    recovered_transaction, recovered_package_ids = (
                        _recover_exact_formula_block_representation(
                            transaction,
                            missing_failures=failures,
                            formula_packages=formula_packages,
                        )
                    )
                    if recovered_package_ids:
                        transaction = recovered_transaction
                        replaced = transaction.paragraph_markdown
                        failures = tuple(
                            failure for failure in failures
                            if not (
                                str(failure).startswith(
                                    "formula_placeholder_missing:"
                                )
                                and str(failure).split(
                                    "formula_placeholder_missing:", 1
                                )[1].strip() in set(recovered_package_ids)
                            )
                        )
                        recovery_traces.append({
                            "section_id": scoped_section_id,
                            "paragraph_id": paragraph_id,
                            "operation": "recover_existing_canonical_formula_block",
                            "package_ids": list(recovered_package_ids),
                        })
                formula_placeholder_failures.extend(
                    f"{paragraph_id}:{failure}" for failure in failures
                )
                transaction_updates: dict[str, Any] = {
                    "paragraph_markdown": replaced,
                }
                # The placeholder is the Writer-side consumption signal.
                # Restore the corresponding package declaration here after
                # successful verbatim insertion; the model is not required
                # to copy an internal package id into its response.  This is
                # representation repair only—the later Binder still needs
                # an exact formula witness in the resulting body.
                if not failures:
                    transaction_updates["used_formula_package_ids"] = list(
                        dict.fromkeys([
                            *(
                                str(value).strip()
                                for value in transaction.used_formula_package_ids
                                if str(value).strip()
                            ),
                            *sorted(paragraph_owner_ids.get(paragraph_id, ())),
                        ])
                    )
                replaced_transactions.append(transaction.model_copy(update=transaction_updates))
            section_markdown = parsed.section_markdown
            if not parsed_transactions:
                section_markdown, failures = splice_formula_placeholders(
                    section_markdown,
                    formula_packages,
                    required_package_ids=package_ids,
                    allowed_package_ids=package_ids,
                    require_all=True,
                )
                formula_placeholder_failures.extend(failures)
            if not formula_placeholder_failures:
                parsed = parsed.model_copy(update={
                    "paragraphs": replaced_transactions,
                    "section_markdown": section_markdown,
                })
        if formula_placeholder_failures:
            section_id = str(request.input_payload.get("section_id") or parsed.section_id or "")
            preserved_text = str(parsed.section_markdown or "").strip()
            if not preserved_text and parsed.paragraphs:
                preserved_text = "\n\n".join(
                    str(item.paragraph_markdown or "").strip()
                    for item in parsed.paragraphs
                    if str(item.paragraph_markdown or "").strip()
                )
            parsed_outputs_by_section[section_id] = [
                parsed.model_copy(update={"section_id": section_id})
            ]
            return LLMResponse(
                text=preserved_text,
                response_hash=response.response_hash,
                blocked_reason=(
                    "publication_section_binding_failed:formula_placeholder:"
                    + ";".join(dict.fromkeys(formula_placeholder_failures))
                ),
                cached=response.cached,
                response_mode=response.response_mode,
                finish_reason=response.finish_reason,
                token_usage=_failed_response_token_usage(response),
                metadata=parsed,
            )
        section_id = str(request.input_payload.get("section_id") or parsed.section_id or "")
        transaction_required = bool(
            isinstance(private_payload, dict)
            and private_payload.get("paragraph_transaction_required")
        )
        if private_section is not None:
            parsed, paragraph_failures = _normalize_publication_paragraph_transaction(
                parsed,
                section=private_section,
                require_transactions=transaction_required and not content_repair_request,
                binder_caller=caller,
                binder_base_config=base_config,
                binder_trace_sink=binder_traces,
                binder_recovery_sink=recovery_traces,
                binder_call_id_prefix=call_id_prefix,
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
        accepted_response_sink=capture_accepted_response,
    )
    parsed_outputs: list[PublicationMethodSectionOutputV1] = []
    for section_result in aggregate.sections:
        candidates = parsed_outputs_by_section.get(section_result.section_id, [])
        if not candidates:
            continue
        # ``write_method_by_sections`` is the state owner.  Its sink captures
        # the exact response that survived representation, paragraph, and
        # bounded Writer-repair decisions.  Never select a later rejected
        # parsed attempt merely because it contains more complete metadata.
        if (
            section_result.section_id not in aggregate.context_partitioned_section_ids
            and section_result.section_id in accepted_outputs_by_section
        ):
            selected = accepted_outputs_by_section[section_result.section_id]
            parsed_outputs.append(selected)
            aggregate.research_requests.extend(selected.new_research_requests)
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
                candidates[0] if section_result.incomplete else candidates[-1],
            )
        parsed_outputs.append(selected)
        aggregate.research_requests.extend(selected.new_research_requests)
    aggregate.response_recovery_traces.extend(recovery_traces)
    aggregate.traces.extend(binder_traces)
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


_WRITER_CONTENT_REPAIRABLE_FAILURE_PREFIXES = (
    "publication_paragraph_transaction_failed:",
    "publication_section_binding_failed:formula_placeholder:",
)


def _response_rendered_formula_package_ids(
    response: LLMResponse,
) -> tuple[str, ...] | None:
    """Read package consumption from the normalized section sidecar."""

    metadata = response.metadata
    if metadata is None:
        return None

    def value_from(item: Any, key: str) -> Any:
        if isinstance(item, Mapping):
            return item.get(key)
        return getattr(item, key, None)

    ids: list[str] = []
    ids.extend(
        str(value).strip()
        for value in (value_from(metadata, "used_formula_package_ids") or ())
        if str(value).strip()
    )
    for paragraph in value_from(metadata, "paragraphs") or ():
        ids.extend(
            str(value).strip()
            for value in (value_from(paragraph, "used_formula_package_ids") or ())
            if str(value).strip()
        )
    return tuple(dict.fromkeys(ids))


def _publication_paragraph_repair_contract(
    section: WriterSectionInput,
    response: LLMResponse,
) -> tuple[dict[str, Any], ...]:
    """Project the shared paragraph assessment into Writer repair hints.

    The paragraph transaction sidecar remains the only authority for target
    identity and acceptance.  This projection is deliberately reader-facing:
    it tells the Writer which semantic atoms are absent from which paragraph,
    while withholding source ids/spans and never asking the model to reproduce
    Harness metadata.  A content retry may return only the listed paragraphs;
    the caller merges those candidates with the incumbent valid siblings.
    """

    graph = section.argument_graph if isinstance(section.argument_graph, dict) else {}
    plans = tuple(
        item for item in (graph.get("paragraphs") or ()) if isinstance(item, Mapping)
    )
    if not plans:
        return ()
    metadata = response.metadata
    if isinstance(metadata, PublicationMethodSectionOutputV1):
        transactions = {
            str(item.paragraph_id or "").strip(): item
            for item in (metadata.paragraphs or ())
            if str(item.paragraph_id or "").strip()
        }
    else:
        transactions = {}

    formula_packages = tuple(
        item
        for item in (section.prompt_payload.get("formula_packages") or ())
        if isinstance(item, Mapping)
    )
    formula_obligations = tuple(
        item
        for item in (section.prompt_payload.get("formula_obligations") or ())
        if isinstance(item, Mapping)
    )
    has_explicit_routes = any(
        str(item.get("obligation_id") or "").strip()
        or bool(item.get("satisfied_obligation_ids"))
        for item in formula_packages
    )
    from code2paper.agentic.publication_transaction_contract import (
        _formula_package_terminal_disposition,
        _witness_constraints_from_plan_row,
        assess_paragraph_transaction,
        required_anchors_from_plan_row,
    )

    formula_routes: dict[str, dict[str, Any]] = {}
    for obligation in formula_obligations:
        obligation_id = str(obligation.get("obligation_id") or "").strip()
        if not obligation_id:
            continue
        matches = tuple(
            package for package in formula_packages
            if obligation_id in {
                *(
                    str(value).strip()
                    for value in (package.get("satisfied_obligation_ids") or ())
                    if str(value).strip()
                ),
                *(
                    [str(package.get("obligation_id") or "").strip()]
                    if str(package.get("obligation_id") or "").strip()
                    else []
                ),
            }
        )
        if not matches and not has_explicit_routes:
            facet_ids = {
                str(value).strip()
                for value in (obligation.get("facet_ids") or ())
                if str(value).strip()
            }
            matches = tuple(
                package for package in formula_packages
                if not facet_ids
                or facet_ids.intersection(
                    {
                        str(value).strip()
                        for value in (package.get("bound_facet_ids") or ())
                        if str(value).strip()
                    }
                )
            )
        formula_routes[obligation_id] = {
            "package_ids": tuple(
                str(package.get("package_id") or "").strip()
                for package in matches
                if str(package.get("package_id") or "").strip()
            ),
            "terminal_disposition": (
                _formula_package_terminal_disposition(matches[0])
                if len(matches) == 1 else "failed"
            ),
        }

    repairs: list[dict[str, Any]] = []
    for raw_plan in plans:
        paragraph_id = str(raw_plan.get("paragraph_id") or "").strip()
        if not paragraph_id:
            continue
        plan_row = {**raw_plan, "section_id": section.section_id}
        transaction = transactions.get(paragraph_id)
        if transaction is None:
            transaction = {
                "paragraph_id": paragraph_id,
                "paragraph_markdown": "",
            }
        assessment = assess_paragraph_transaction(
            transaction,
            plan_row=plan_row,
            formula_routes=formula_routes,
            required_anchors=required_anchors_from_plan_row(plan_row),
        )
        missing_by_kind = {
            str(kind): tuple(str(value) for value in values if str(value).strip())
            for kind, values in assessment.missing_by_kind.items()
            if values
        }
        if not missing_by_kind and not assessment.invalid_witnesses and not assessment.semantic_failures:
            continue
        constraints = _witness_constraints_from_plan_row(plan_row)
        semantic_targets: list[dict[str, Any]] = []
        for kind, target_ids in missing_by_kind.items():
            for target_id in target_ids:
                local = constraints.get((kind, target_id), {})
                target: dict[str, Any] = {
                    "target_kind": kind,
                    "paper_role": str(local.get("paper_role") or ""),
                    "semantic_atom": str(local.get("semantic_atom") or ""),
                    "conditions": list(local.get("conditions") or ()),
                    "polarity": str(local.get("polarity") or "unknown"),
                }
                if kind == "formula":
                    route = formula_routes.get(target_id, {})
                    package_ids = tuple(route.get("package_ids") or ())
                    package = next(
                        (
                            item for item in formula_packages
                            if str(item.get("package_id") or "").strip()
                            in package_ids
                        ),
                        None,
                    )
                    if package is not None:
                        target.update({
                            "placeholder": str(
                                package.get("placeholder")
                                or f"[[FORMULA:{package.get('package_id')}]]"
                            ),
                            "purpose": str(package.get("purpose") or ""),
                            "prose_explanation": str(
                                package.get("prose_explanation") or ""
                            ),
                            "material_conditions": list(
                                package.get("material_conditions") or ()
                            ),
                            "assumptions": list(package.get("assumptions") or ()),
                            "terminal_disposition": str(
                                route.get("terminal_disposition") or "failed"
                            ),
                        })
                semantic_targets.append(target)
        repairs.append({
            "paragraph_id": paragraph_id,
            "paragraph_role": str(raw_plan.get("paragraph_role") or ""),
            "repair_mode": "rewrite_only_missing_paragraph_content",
            "missing_targets_by_kind": missing_by_kind,
            "missing_targets": semantic_targets,
            "invalid_witnesses": list(assessment.invalid_witnesses),
            "semantic_failures": list(assessment.semantic_failures),
            "instruction": (
                "Repair only this paragraph. Preserve its correct existing content, "
                "add natural Method sentences for every missing semantic target, "
                "and emit the exact formula placeholder when one is listed. "
                "Do not mention ids, validators, or this repair packet."
            ),
        })
    return tuple(repairs)


def _merge_publication_repair_response(
    section: WriterSectionInput,
    incumbent: LLMResponse,
    candidate: LLMResponse,
) -> LLMResponse:
    """Merge a paragraph-scoped retry with the incumbent section.

    This is representation assembly only.  Every candidate paragraph has
    already crossed the same structured/Binder boundary; the shared assessor
    still decides whether the merged transaction is valid.  Missing candidate
    siblings retain their frozen incumbent transactions and therefore cannot
    be erased by a retry that addresses one paragraph.
    """

    old = incumbent.metadata
    new = candidate.metadata
    if not isinstance(old, PublicationMethodSectionOutputV1):
        return candidate
    if not isinstance(new, PublicationMethodSectionOutputV1):
        return candidate
    candidate_by_id: dict[str, PublicationMethodParagraphOutputV1] = {}
    for item in new.paragraphs or ():
        paragraph_id = str(item.paragraph_id or "").strip()
        if not paragraph_id:
            continue
        # Do not silently collapse duplicate or out-of-plan transactions.
        # The structured boundary must report those defects to the shared
        # assessor instead of allowing the merge to manufacture a valid view.
        if paragraph_id in candidate_by_id:
            return candidate
        candidate_by_id[paragraph_id] = item
    if not candidate_by_id:
        return candidate
    incumbent_by_id = {
        str(item.paragraph_id or "").strip(): item
        for item in (old.paragraphs or ())
        if str(item.paragraph_id or "").strip()
    }
    graph = section.argument_graph if isinstance(section.argument_graph, dict) else {}
    planned_ids = tuple(
        str(item.get("paragraph_id") or "").strip()
        for item in (graph.get("paragraphs") or ())
        if isinstance(item, Mapping) and str(item.get("paragraph_id") or "").strip()
    )
    ordered_ids = planned_ids or tuple(dict.fromkeys((*incumbent_by_id, *candidate_by_id)))
    if planned_ids and set(candidate_by_id) - set(planned_ids):
        return candidate
    merged_by_id = {
        paragraph_id: candidate_by_id.get(paragraph_id, incumbent_by_id.get(paragraph_id))
        for paragraph_id in ordered_ids
        if candidate_by_id.get(paragraph_id) is not None
        or incumbent_by_id.get(paragraph_id) is not None
    }
    if not merged_by_id:
        return candidate
    heading = str(old.heading_text or new.heading_text or section.heading or "").strip()
    heading = heading.lstrip("#").strip()
    body = "\n\n".join(
        str(merged_by_id[paragraph_id].paragraph_markdown or "").strip()
        for paragraph_id in ordered_ids
        if paragraph_id in merged_by_id
        and str(merged_by_id[paragraph_id].paragraph_markdown or "").strip()
    )
    section_markdown = f"## {heading}\n\n{body}" if heading and body else body

    def union(field_name: str) -> list[str]:
        return list(dict.fromkeys(
            str(value).strip()
            for paragraph in merged_by_id.values()
            for value in (getattr(paragraph, field_name) or ())
            if str(value).strip()
        ))

    def merge_items(field_name: str) -> list[Any]:
        """Preserve incumbent state, then retain new diagnostic items."""

        values: list[Any] = []
        seen: set[str] = set()
        for source in (getattr(old, field_name) or (), getattr(new, field_name) or ()):
            for value in source:
                try:
                    key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                except (TypeError, ValueError):
                    key = repr(value)
                if key in seen:
                    continue
                seen.add(key)
                values.append(value)
        return values

    rendered_facets = set(union("rendered_from_facet_ids"))
    rendered_briefs = {
        str(value).strip()
        for value in (old.rendered_brief_ids or ())
        if str(value).strip()
    }
    rendered_concepts = {
        str(value).strip()
        for value in (old.rendered_concept_keys or ())
        if str(value).strip()
    }
    merged = old.model_copy(update={
        # Aggregate authority fields that are not paragraph-derived remain
        # frozen at the incumbent.  A repair response may add prose and
        # paragraph witnesses, but it cannot replace the Architect's closed
        # concept/brief/unit/move contract with an incomplete self-report.
        "heading_text": old.heading_text or new.heading_text,
        "section_markdown": section_markdown,
        "paragraphs": [merged_by_id[item] for item in ordered_ids if item in merged_by_id],
        "rendered_paragraph_ids": union("paragraph_id"),
        "rendered_from_facet_ids": union("rendered_from_facet_ids"),
        "rendered_field_candidate_ids": union("rendered_field_candidate_ids"),
        "rendered_slot_ids": union("rendered_slot_ids"),
        "rendered_edge_ids": union("rendered_edge_ids"),
        "used_formula_package_ids": union("used_formula_package_ids"),
        "used_claim_ids": union("used_claim_ids"),
        "used_equation_ids": union("used_equation_ids"),
        "deferred_facet_ids": [
            value for value in (old.deferred_facet_ids or ())
            if str(value) not in rendered_facets
        ],
        "deferred_brief_ids": [
            value for value in (old.deferred_brief_ids or ())
            if str(value) not in rendered_briefs
        ],
        "deferred_concept_keys": [
            value for value in (old.deferred_concept_keys or ())
            if str(value) not in rendered_concepts
        ],
        "new_research_requests": merge_items("new_research_requests"),
        "unresolved_points": merge_items("unresolved_points"),
        "self_identified_risks": merge_items("self_identified_risks"),
    })
    return replace(
        candidate,
        text=section_markdown,
        metadata=merged,
    )


def _is_writer_content_repairable_failure(reason: str | None) -> bool:
    """Return whether a typed representation/content failure may be repaired.

    Formula placeholder failures are emitted after the structured response has
    already parsed successfully and therefore still carry usable prose.  They
    belong in the same bounded Writer repair loop as paragraph transaction
    failures.  Unknown-id, schema, transport, and authority failures remain
    terminal at this layer.
    """

    value = str(reason or "")
    return value.startswith(_WRITER_CONTENT_REPAIRABLE_FAILURE_PREFIXES)


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
    "project_reader_value",
    "project_operation_to_reader_surface",
    "normalize_publication_heading",
    "write_method_by_sections",
    "write_publication_method_by_sections",
]
