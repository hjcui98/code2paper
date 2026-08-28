"""Stage 3 low-temperature per-field Evidence Judge for Method Concept Cards.

The Judge evaluates every positive semantic field of a card against the
exact closed fragments of its cluster and returns, per field:

``ConceptCardFieldJudgmentV1``
    field_name
    proposed_value
    verdict: entailed | partial | contradicted | not_found
    evidence_fragment_refs[]
    rationale

plus an ``overall_verdict``.  Hard rules enforced by the harness (this
module's response model and the compiler):

- rationale is mandatory for any verdict other than ``not_found`` with no
  refs — the judge must say *which* fragment supports the field;
- ``entailed``/``partial`` field verdicts REQUIRE at least one fragment ref;
- a card enters the verified lane only when every positive semantic field
  is individually entailed — one card cannot pass on the mere presence of
  unrelated facts;
- purpose/downstream claims (e.g. "for pruning") without caller/dataflow
  evidence must be ``partial`` or ``not_found``;
- numbers such as ``15`` must be marked as coming from code, from the
  author, or both (the verdict alone is not enough; the rationale states
  the provenance).

The judge only ever sees the bounded card fields and the closed ``frag-N``
fragments of the cluster; internal IDs are harness-owned.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from code2paper.agentic.method_concept_card_models import (
    ConceptCardCandidateClusterV1,
    ConceptCardEvidenceVerdictV1,
    ConceptCardFieldJudgmentV1,
    MethodConceptCardV1,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import METHOD_PROPOSITION_ARCHITECT, apply_role_config
from code2paper.schemas import LLMConfig


class _FieldJudgmentResponseV1:
    """Semantic-only response surface for one field judgment."""

    model_config = {"extra": "ignore", "frozen": True}

    def __init__(self, **kwargs: Any) -> None:
        self.field_name = str(kwargs.get("field_name", "") or "")
        self.proposed_value = str(kwargs.get("proposed_value", "") or "")
        self.verdict = str(kwargs.get("verdict", "not_found") or "not_found")
        self.evidence_fragment_refs = tuple(
            str(item) for item in (kwargs.get("evidence_fragment_refs") or ())
        )
        self.rationale = str(kwargs.get("rationale", "") or "")


class _FieldJudgmentsResponseV1:
    """Semantic-only response surface for one card's field judgments."""

    model_config = {"extra": "ignore", "frozen": True}

    def __init__(self, **kwargs: Any) -> None:
        self.field_judgments = tuple(
            _FieldJudgmentResponseV1(**item)
            if isinstance(item, dict)
            else item
            for item in (kwargs.get("field_judgments") or ())
        )
        self.overall_verdict = str(kwargs.get("overall_verdict", "not_found") or "not_found")
        self.rationale = str(kwargs.get("rationale", "") or "")


def _card_fields(card: MethodConceptCardV1) -> list[dict[str, str]]:
    """Positive semantic fields of a card, for per-field judgment."""

    fields: list[dict[str, str]] = [
        {"field_name": "method_subject", "value": card.method_subject},
        {"field_name": "operation", "value": card.operation},
    ]
    for field_name, values in (
        ("inputs", card.inputs),
        ("outputs", card.outputs),
        ("conditions", card.conditions),
        ("numeric_constraints", card.numeric_constraints),
        ("formula_constraints", card.formula_constraints),
    ):
        for value in values:
            fields.append({"field_name": field_name, "value": value})
    return fields


def _closed_fragment_terms(cluster: ConceptCardCandidateClusterV1) -> list[str]:
    return [
        f"frag-{index}: {fragment}"
        for index, fragment in enumerate(cluster.source_fragments, start=1)
    ]


def build_concept_card_evidence_judge(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
    timeout_seconds: float | None = None,
):
    """Return a per-field Evidence Judge for one cluster's concept cards."""

    config = apply_role_config(llm_config, METHOD_PROPOSITION_ARCHITECT)
    if timeout_seconds is not None:
        config = config.model_copy(update={"request_timeout_seconds": timeout_seconds})
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

    judge_traces: list[dict[str, Any]] = []

    def judge(
        cards: tuple[MethodConceptCardV1, ...],
        cluster: ConceptCardCandidateClusterV1,
    ) -> tuple[ConceptCardEvidenceVerdictV1, ...]:
        verdicts: list[ConceptCardEvidenceVerdictV1] = []
        for card in cards:
            verdict = _judge_one(card, cluster, caller, config, judge_traces)
            verdicts.append(verdict)
        return tuple(verdicts)

    judge.judge_traces = judge_traces  # type: ignore[attr-defined]
    return judge


def _judge_one(
    card: MethodConceptCardV1,
    cluster: ConceptCardCandidateClusterV1,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse],
    config: LLMConfig,
    traces: list[dict[str, Any]],
) -> ConceptCardEvidenceVerdictV1:
    """Judge one card's positive fields against the closed fragments."""

    fields = _card_fields(card)
    schema = _require_judge_fields(json_schema_for(_judge_schema_model()))
    prompt = _judge_prompt(card, cluster, fields)
    request = LLMRequest(
        prompt_template_id="agentic_method_concept_card_evidence_judge_v1",
        prompt=prompt,
        input_payload={
            "concept_key": card.concept_key,
            "authority_lane": card.authority_lane,
            "closed_fragments": _closed_fragment_terms(cluster),
            "fields": fields,
        },
        schema_name="ConceptCardEvidenceJudgeV1",
        response_json_schema=schema,
    )
    response = caller(config, request)
    if response.blocked_reason:
        raise ValueError(f"evidence_judge_blocked:{response.blocked_reason}")
    parsed, recovery, parse_error = try_parse_structured_response_with_trace(
        response.text, _judge_schema_model()
    )
    if parsed is None:
        raise ValueError(parse_error or "evidence judge schema failed")
    traces.append({
        "concept_key": card.concept_key,
        "recovery_applied": recovery.applied,
        "recovery_operations": list(recovery.operations),
        "parsed_payload_digest": recovery.parsed_payload_digest,
    })
    return _verdict_from_response(card.concept_key, parsed)


def _require_judge_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Force per-field required columns and a non-empty judgments array.

    Without this the guided decoder happily omits proposed_value,
    evidence_fragment_refs and rationale, producing verdicts that pass the
    schema but fail the harness validator after one repair round.  The
    schema itself must require them so the model cannot emit a judgment
    that says nothing about which fragment supports a field.
    """

    import copy

    schema = copy.deepcopy(schema)
    defs = schema.get("$defs", {})
    row_def = defs.get("_FieldRow")
    if row_def is not None:
        row_def["required"] = [
            "field_name", "proposed_value", "verdict",
            "evidence_fragment_refs", "rationale",
        ]
        refs_schema = row_def.get("properties", {}).get("evidence_fragment_refs", {})
        refs_schema["minItems"] = 0  # not_found may legitimately have no refs
    judgments_schema = schema.get("properties", {}).get("field_judgments", {})
    judgments_schema["minItems"] = 1
    schema["properties"]["field_judgments"]["items"] = {
        **schema["properties"]["field_judgments"].get("items", {}),
    }
    return schema


def _judge_schema_model():
    """Pydantic model matching the semantic-only judge response."""

    from pydantic import BaseModel, ConfigDict, Field, field_validator

    class _FieldRow(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        field_name: str
        proposed_value: str = ""
        verdict: str = "not_found"
        evidence_fragment_refs: tuple[str, ...] = Field(default_factory=tuple)
        rationale: str = ""

    class _JudgeResponse(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        field_judgments: tuple[_FieldRow, ...] = Field(default_factory=tuple)
        overall_verdict: str = "not_found"
        rationale: str = ""

    return _JudgeResponse


def _verdict_from_response(concept_key: str, parsed: Any) -> ConceptCardEvidenceVerdictV1:
    judgments = tuple(
        ConceptCardFieldJudgmentV1(
            field_name=item.field_name,
            proposed_value=item.proposed_value,
            verdict=item.verdict,
            evidence_fragment_refs=item.evidence_fragment_refs,
            rationale=item.rationale,
        )
        for item in parsed.field_judgments
    )
    return ConceptCardEvidenceVerdictV1(
        concept_key=concept_key,
        field_judgments=judgments,
        overall_verdict=parsed.overall_verdict,
        rationale=parsed.rationale,
    )


def _judge_prompt(
    card: MethodConceptCardV1,
    cluster: ConceptCardCandidateClusterV1,
    fields: list[dict[str, str]],
) -> str:
    instructions = (
        "You are the Method Concept Evidence Judge. For ONE concept card, judge every "
        "positive semantic field (method_subject, operation, inputs, outputs, conditions, "
        "numeric_constraints, formula_constraints) against the closed fragments of its "
        "cluster. Return only JSON matching the schema.\n\n"
        "Verdicts:\n"
        "- entailed: the fragment(s) directly establish this exact field value.\n"
        "- partial: fragments establish part of it, but a material piece is missing.\n"
        "- contradicted: a fragment contradicts the proposed value.\n"
        "- not_found: no fragment supports it.\n\n"
        "Rules:\n"
        "- Judge EVERY field listed in fields_to_judge; never skip or merge fields.\n"
        "- For every field judgment fill ALL five columns: field_name, proposed_value "
        "(copy the card's value for that field), verdict, evidence_fragment_refs, rationale.\n"
        "- For entailed/partial, list the exact frag-N ids that support the field.\n"
        "- rationale is mandatory and must name the supporting/contradicting fragment "
        "content; never leave it empty.\n"
        "- Purpose/downstream claims (e.g. 'for pruning', 'to enable pruning', 'as a "
        "predictor input') without a caller/data-flow fragment must be partial or "
        "not_found.\n"
        "- Numbers/formulas: state in the rationale whether each number (e.g. 15, "
        "0.01, 0.99) comes from the code fragments, from the author statement, or both.\n"
        "- A card cannot pass on the mere presence of unrelated facts: each field needs "
        "its own supporting fragments.\n"
        "- overall_verdict: entailed only when EVERY field judgment is entailed; "
        "otherwise partial/contradicted/not_found, and the overall rationale must "
        "summarize which fields failed.\n"
        "- Never invent frag ids; use only the closed set below."
    )
    payload = {
        "authority_lane": card.authority_lane,
        "card": {
            "method_subject": card.method_subject,
            "operation": card.operation,
            "inputs": list(card.inputs),
            "outputs": list(card.outputs),
            "conditions": list(card.conditions),
            "numeric_constraints": list(card.numeric_constraints),
            "formula_constraints": list(card.formula_constraints),
            "evidence_fragment_refs": list(card.evidence_fragment_refs),
        },
        "closed_fragments": _closed_fragment_terms(cluster),
        "fields_to_judge": fields,
    }
    return instructions + "\n\nPayload:\n" + json.dumps(
        payload, ensure_ascii=False, indent=2
    )
