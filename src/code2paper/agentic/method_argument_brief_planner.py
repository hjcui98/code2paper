"""WP-C: one-shot Mechanism Planner for argument brief drafts.

The model sees only a closed-set envelope (licensed/unlicensed clause text,
completeness statuses, and numbered ``frag-N`` evidence literals).  The harness
maps ``frag-N`` back to exact claim/equation ids and rejects any out-of-closure
reference.  Draft text is a mechanism constraint for the Writer, not final
publication prose.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.equation_claims import EquationClaimSetV1, EquationClaimV1
from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.method_argument_brief_compiler import _stable_id
from code2paper.agentic.method_argument_brief_models import (
    ArgumentBriefGapV1,
    MechanismDraftV1,
    MethodArgumentBriefV1,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import METHOD_MECHANISM_DRAFT_PLANNER, apply_role_config
from code2paper.schemas import LLMConfig


class MechanismDraftProposalV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    brief_id: str
    text: str = Field(min_length=1)
    cited_frag_ids: tuple[str, ...] = Field(min_length=1)
    caveat: str = ""


class MechanismDraftProposalBatchV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    drafts: tuple[MechanismDraftProposalV1, ...] = Field(min_length=1)


@dataclass(frozen=True)
class _FragBinding:
    frag_id: str
    claim_id: str = ""
    equation_id: str = ""
    span_id: str = ""


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _build_frag_catalog(
    brief: MethodArgumentBriefV1,
    *,
    claim_by_id: dict[str, AtomicClaimV3],
    equation_by_id: dict[str, EquationClaimV1],
    start_index: int = 1,
) -> tuple[list[str], dict[str, _FragBinding], int]:
    """Build numbered fragment literals and a closed frag-id map for one brief."""

    lines: list[str] = []
    catalog: dict[str, _FragBinding] = {}
    index = start_index
    for claim_id in brief.claim_ids:
        claim = claim_by_id.get(claim_id)
        if claim is None:
            continue
        frag_id = f"frag-{index}"
        index += 1
        lines.append(f"{frag_id}: claim {claim_id}: {claim.canonical_text.strip()}")
        catalog[frag_id] = _FragBinding(frag_id=frag_id, claim_id=claim_id)
    for equation_id in brief.equation_ids:
        equation = equation_by_id.get(equation_id)
        if equation is None:
            continue
        frag_id = f"frag-{index}"
        index += 1
        expression = str(getattr(equation, "expression", "") or "").strip()
        lines.append(f"{frag_id}: equation {equation_id}: {expression}")
        catalog[frag_id] = _FragBinding(frag_id=frag_id, equation_id=equation_id)
    for span_id in brief.span_ids:
        frag_id = f"frag-{index}"
        index += 1
        lines.append(f"{frag_id}: span {span_id}")
        catalog[frag_id] = _FragBinding(frag_id=frag_id, span_id=span_id)
    return lines, catalog, index


def _brief_envelope(
    brief: MethodArgumentBriefV1,
    *,
    claim_by_id: dict[str, AtomicClaimV3],
    equation_by_id: dict[str, EquationClaimV1],
    start_index: int = 1,
) -> tuple[dict[str, Any], dict[str, _FragBinding], int]:
    fragments, catalog, next_index = _build_frag_catalog(
        brief,
        claim_by_id=claim_by_id,
        equation_by_id=equation_by_id,
        start_index=start_index,
    )
    return {
        "brief_id": brief.brief_id,
        "intended_role": brief.intended_role,
        "completeness_statuses": list(brief.completeness_statuses),
        "licensed_clauses": [
            {"clause_id": clause.clause_id, "text": clause.text}
            for clause in brief.clauses
            if clause.license == "positively_licensed"
        ],
        "unlicensed_clauses": [
            {
                "clause_id": clause.clause_id,
                "text": clause.text,
                "license": clause.license,
            }
            for clause in brief.clauses
            if clause.license in {"unlicensed", "partially_licensed"}
        ],
        "fragments": fragments,
    }, catalog, next_index


def _closed_schema(
    *,
    brief_ids: tuple[str, ...],
    frag_ids: tuple[str, ...],
) -> dict[str, Any]:
    schema = json_schema_for(MechanismDraftProposalBatchV1)
    schema = copy.deepcopy(schema)
    draft_def = schema.get("$defs", {}).get("MechanismDraftProposalV1", {})
    properties = draft_def.get("properties", {})
    if brief_ids:
        properties["brief_id"] = {"type": "string", "enum": list(brief_ids)}
    cited = properties.get("cited_frag_ids", {})
    items = cited.get("items", {})
    if frag_ids:
        items["enum"] = list(frag_ids)
        cited["items"] = items
        properties["cited_frag_ids"] = cited
    draft_def["properties"] = properties
    schema["$defs"]["MechanismDraftProposalV1"] = draft_def
    return schema


def _looks_formula_like(text: str) -> bool:
    lowered = text.casefold()
    if any(token in text for token in ("=", "∑", "\\", "^", "_{", "^{")):
        return True
    return any(
        token in lowered
        for token in (" equation", " loss", " derivative", " softmax(", " norm(")
    )


def _validate_proposal(
    proposal: MechanismDraftProposalV1,
    *,
    allowed_brief_ids: set[str],
    frag_catalog: dict[str, _FragBinding],
) -> tuple[MechanismDraftV1 | None, str]:
    if proposal.brief_id not in allowed_brief_ids:
        return None, f"unknown brief_id:{proposal.brief_id}"
    if re.search(r"\bfrag-\d+\b", proposal.text, flags=re.IGNORECASE):
        return None, "planner draft text must not contain frag ids"
    cited_claims: list[str] = []
    cited_equations: list[str] = []
    for frag_id in proposal.cited_frag_ids:
        binding = frag_catalog.get(frag_id)
        if binding is None:
            return None, f"unknown frag id:{frag_id}"
        if binding.claim_id:
            cited_claims.append(binding.claim_id)
        if binding.equation_id:
            cited_equations.append(binding.equation_id)
    if not cited_claims and not cited_equations:
        return None, "draft must cite at least one claim or equation frag"
    authority_lane = "executable_hard"
    caveat = proposal.caveat.strip()
    if cited_equations:
        authority_lane = "executable_hard"
    elif cited_claims and not cited_equations and _looks_formula_like(proposal.text):
        authority_lane = "formal_derivation"
        if not caveat:
            return None, "formula-like draft without equation binding requires caveat"
    return MechanismDraftV1(
        draft_id=_stable_id("draft", proposal.brief_id),
        brief_id=proposal.brief_id,
        text=proposal.text.strip(),
        cited_claim_ids=tuple(dict.fromkeys(cited_claims)),
        cited_equation_ids=tuple(dict.fromkeys(cited_equations)),
        authority_lane=authority_lane,
        caveat=caveat,
        status="planner_filled",
    ), ""


def _estimate_token_count(text: str) -> int:
    """Rough token estimate for planner batching (chars / 4)."""

    return max(1, len(text) // 4)


def _split_planner_batches(
    briefs: tuple[MethodArgumentBriefV1, ...],
    *,
    max_briefs_per_batch: int = 8,
    estimated_tokens_per_brief: int = 400,
    max_input_tokens: int = 6000,
) -> list[tuple[MethodArgumentBriefV1, ...]]:
    """Split caveat briefs into ordered batches when the envelope is too large."""

    if not briefs:
        return []
    estimated = len(briefs) * estimated_tokens_per_brief
    if len(briefs) <= max_briefs_per_batch and estimated <= max_input_tokens:
        return [briefs]
    target_batches = min(4, max(2, (len(briefs) + max_briefs_per_batch - 1) // max_briefs_per_batch))
    batch_size = max(1, (len(briefs) + target_batches - 1) // target_batches)
    return [
        briefs[index:index + batch_size]
        for index in range(0, len(briefs), batch_size)
    ]


def _response_preview(text: str, *, limit: int = 2000) -> str:
    return str(text or "")[:limit]


def _planner_prompt(
    envelopes: list[dict[str, Any]],
    *,
    validation_error: str = "",
) -> str:
    lines = [
        "You are the Method Mechanism Planner.",
        "Produce one mechanism draft per brief that has unlicensed or partial author clauses.",
        "Use only the provided frag-N literals; do not invent evidence ids or claim repository facts "
        "for unlicensed author intent.",
        "Draft text is a mechanism/algorithm sketch for the Writer to rewrite; it is not final prose.",
        "Organize the full author mechanism story, including supported, partial, and "
        "unresolved facets. A planner_filled draft is an organization seed only: "
        "never paste frag-N, evidence ids, or a caveat token shell into draft text.",
        "If a formula-worthy point has no repository equation, describe the intended "
        "mathematical role for the author_intent_academic lane; do not force an "
        "incidental shape/configuration operation into an equation citation.",
        "",
        "Return JSON: {\"drafts\": [{\"brief_id\", \"text\", \"cited_frag_ids\", \"caveat\"}]}.",
        "",
        json.dumps({"briefs": envelopes}, ensure_ascii=False, indent=2),
    ]
    if validation_error.strip():
        lines.extend(["", "Previous response failed validation:", validation_error.strip()])
    return "\n".join(lines)


def _run_planner_batch(
    briefs: tuple[MethodArgumentBriefV1, ...],
    *,
    claim_by_id: dict[str, AtomicClaimV3],
    equation_by_id: dict[str, EquationClaimV1],
    config: LLMConfig,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse],
    call_traces: list[dict[str, Any]],
    gaps: list[ArgumentBriefGapV1],
    start_frag_index: int,
) -> tuple[dict[str, MechanismDraftV1], int]:
    """Execute one closed-set planner request for a brief subset."""

    if not briefs:
        return {}, start_frag_index
    envelopes: list[dict[str, Any]] = []
    frag_catalog: dict[str, _FragBinding] = {}
    next_frag_index = start_frag_index
    for brief in briefs:
        envelope, brief_catalog, next_frag_index = _brief_envelope(
            brief,
            claim_by_id=claim_by_id,
            equation_by_id=equation_by_id,
            start_index=next_frag_index,
        )
        frag_catalog.update(brief_catalog)
        envelopes.append(envelope)
    allowed_brief_ids = tuple(brief.brief_id for brief in briefs)
    allowed_frag_ids = tuple(sorted(frag_catalog))
    schema = _closed_schema(
        brief_ids=allowed_brief_ids,
        frag_ids=allowed_frag_ids,
    )
    validation_error = ""
    produced: dict[str, MechanismDraftV1] = {}
    for attempt in range(2):
        prompt = _planner_prompt(envelopes, validation_error=validation_error)
        request = LLMRequest(
            prompt_template_id="agentic_method_argument_brief_planner_v1",
            prompt=prompt,
            input_payload={
                "brief_ids": list(allowed_brief_ids),
                "frag_ids": list(allowed_frag_ids),
            },
            schema_name="MechanismDraftProposalBatchV1",
            response_json_schema=schema,
        )
        response = caller(config, request)
        trace_row: dict[str, Any] = {
            "brief_ids": list(allowed_brief_ids),
            "attempt": attempt + 1,
            "blocked_reason": str(response.blocked_reason or ""),
            "finish_reason": str(response.finish_reason or ""),
            "response_preview": _response_preview(response.text),
            "estimated_prompt_tokens": _estimate_token_count(prompt),
        }
        if response.blocked_reason:
            trace_row["parse_error"] = f"planner blocked:{response.blocked_reason}"
            call_traces.append(trace_row)
            for brief in briefs:
                gaps.append(ArgumentBriefGapV1(
                    gap_kind="planner_failed",
                    brief_id=brief.brief_id,
                    message=f"planner blocked:{response.blocked_reason}"[:240],
                ))
            return produced, next_frag_index
        parsed_obj, recovery, parse_error = try_parse_structured_response_with_trace(
            response.text,
            MechanismDraftProposalBatchV1,
        )
        if parsed_obj is None:
            validation_error = parse_error or "planner schema parse failed"
            trace_row["parse_error"] = validation_error
            trace_row["recovery_applied"] = recovery.applied
            trace_row["recovery_operations"] = list(recovery.operations)
            call_traces.append(trace_row)
            continue
        trace_row.update({
            "recovery_applied": recovery.applied,
            "recovery_operations": list(recovery.operations),
            "parsed_payload_digest": recovery.parsed_payload_digest,
            "response_digest": _digest(parsed_obj.model_dump(mode="json")),
        })
        produced = {}
        harness_error = ""
        seen_brief_ids: set[str] = set()
        for item in parsed_obj.drafts:
            if item.brief_id in seen_brief_ids:
                harness_error = f"duplicate draft for brief_id:{item.brief_id}"
                break
            seen_brief_ids.add(item.brief_id)
            draft, error = _validate_proposal(
                item,
                allowed_brief_ids=set(allowed_brief_ids),
                frag_catalog=frag_catalog,
            )
            if draft is None:
                harness_error = error
                break
            produced[item.brief_id] = draft
        if harness_error:
            validation_error = harness_error
            trace_row["parse_error"] = harness_error
            call_traces.append(trace_row)
            continue
        call_traces.append(trace_row)
        if set(produced.keys()) >= set(allowed_brief_ids):
            return produced, next_frag_index
        validation_error = "planner returned an incomplete brief draft set"
    for brief in briefs:
        if brief.brief_id not in produced:
            gaps.append(ArgumentBriefGapV1(
                gap_kind="planner_failed",
                brief_id=brief.brief_id,
                message=(validation_error or "planner validation failed")[:240],
            ))
    return produced, next_frag_index


def build_mechanism_draft_planner(
    llm_config: LLMConfig,
    *,
    claims: AtomicClaimSetV3,
    equations: EquationClaimSetV1 | None = None,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
):
    """Return a callable planner that performs one closed-set LLM request."""

    config = apply_role_config(llm_config, METHOD_MECHANISM_DRAFT_PLANNER)
    if llm_caller is None:
        from code2paper.llm.capabilities import (
            StructuredResponseMode,
            load_capability_profile,
        )

        profile = load_capability_profile(
            provider=getattr(config.provider, "value", str(config.provider)),
            model=config.model,
        ).model_copy(update={
            "response_mode": StructuredResponseMode.NATIVE_JSON_SCHEMA,
        })
        caller = lambda cfg, request: LLMClient(
            cfg, capability_profile=profile
        ).complete(request)
    else:
        caller = llm_caller

    claim_by_id = {item.claim_id: item for item in claims.claims}
    equation_by_id = {
        item.equation_id: item
        for item in (equations.equations if equations is not None else ())
    }
    gaps: list[ArgumentBriefGapV1] = []
    call_traces: list[dict[str, Any]] = []

    def planner(
        briefs: tuple[MethodArgumentBriefV1, ...],
    ) -> tuple[MechanismDraftV1, ...]:
        if not briefs:
            return ()
        produced_all: dict[str, MechanismDraftV1] = {}
        next_frag_index = 1
        for batch in _split_planner_batches(briefs):
            produced, next_frag_index = _run_planner_batch(
                batch,
                claim_by_id=claim_by_id,
                equation_by_id=equation_by_id,
                config=config,
                caller=caller,
                call_traces=call_traces,
                gaps=gaps,
                start_frag_index=next_frag_index,
            )
            produced_all.update(produced)
        return tuple(
            produced_all[brief_id]
            for brief_id in (brief.brief_id for brief in briefs)
            if brief_id in produced_all
        )

    planner.gaps = gaps  # type: ignore[attr-defined]
    planner.call_traces = call_traces  # type: ignore[attr-defined]
    return planner


class StubMechanismDraftPlanner:
    """Deterministic planner for tests; validates closed-set ids only."""

    def __init__(
        self,
        *,
        drafts_by_brief_id: dict[str, MechanismDraftV1] | None = None,
        reject_frag_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.drafts_by_brief_id = drafts_by_brief_id or {}
        self.reject_frag_ids = reject_frag_ids
        self.gaps: list[ArgumentBriefGapV1] = []
        self.call_traces: list[dict[str, Any]] = []

    def __call__(
        self,
        briefs: tuple[MethodArgumentBriefV1, ...],
    ) -> tuple[MechanismDraftV1, ...]:
        produced: list[MechanismDraftV1] = []
        for brief in briefs:
            draft = self.drafts_by_brief_id.get(brief.brief_id)
            if draft is None:
                continue
            for frag_id in self._frag_ids_from_draft(draft):
                if frag_id in self.reject_frag_ids or not frag_id.startswith("frag-"):
                    self.gaps.append(ArgumentBriefGapV1(
                        gap_kind="planner_failed",
                        brief_id=brief.brief_id,
                        message=f"closed-set violation:{frag_id}",
                    ))
                    draft = None
                    break
            if draft is not None:
                produced.append(draft)
        return tuple(produced)

    @staticmethod
    def _frag_ids_from_draft(draft: MechanismDraftV1) -> tuple[str, ...]:
        # Stub stores frag ids in caveat for negative tests.
        if draft.caveat.startswith("frags:"):
            return tuple(
                part.strip()
                for part in draft.caveat.split(":", 1)[1].split(",")
                if part.strip()
            )
        return ()


__all__ = [
    "MechanismDraftProposalBatchV1",
    "MechanismDraftProposalV1",
    "StubMechanismDraftPlanner",
    "build_mechanism_draft_planner",
]
