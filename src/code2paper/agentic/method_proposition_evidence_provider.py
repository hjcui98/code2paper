"""Independent low-temperature evidence judge for Method propositions."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from code2paper.agentic.method_proposition_models import (
    PropositionEvidenceJudgmentBatchV1,
    PropositionEvidenceVerdictV1,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import SEMANTIC_VERIFIER, apply_role_config
from code2paper.schemas import LLMConfig


def build_method_proposition_evidence_judge(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
):
    """Return a judge that compares one conceptual card to exact code evidence.

    This owner is deliberately separate from the Proposition Architect. It
    receives no author story or paper terminology hints, so author intent
    cannot be used to fill a semantic field that the selected source does not
    establish.
    """

    # A proposition judgment is a local, fail-closed enhancement: when the
    # provider is unavailable the proposition remains useful as visibly
    # caveated candidate material but cannot enter repository-verified prose.
    # It must therefore never inherit a 15--30 minute Writer transport window
    # or provider-level automatic retries that stall the whole product after
    # research has already completed.
    try:
        configured_timeout = int(
            os.environ.get("CODE2PAPER_METHOD_PROPOSITION_JUDGE_TIMEOUT_SECONDS", "90")
        )
    except ValueError:
        configured_timeout = 90
    judge_timeout = max(
        15,
        min(llm_config.request_timeout_seconds, configured_timeout, 180),
    )
    config = apply_role_config(llm_config, SEMANTIC_VERIFIER).model_copy(
        update={
            "temperature": 0.0,
            "top_p": None,
            "top_k": None,
            "max_output_tokens": 1536,
            "request_timeout_seconds": judge_timeout,
            "retry_max_attempts": 1,
            "cache": False,
        }
    )
    caller = llm_caller or (lambda cfg, request: LLMClient(cfg).complete(request))
    evidence_judge_traces: list[dict[str, Any]] = []

    def judge(payload: dict[str, Any]) -> PropositionEvidenceVerdictV1 | None:
        base_prompt = (
                "You are the independent repository Evidence Judge for a Method proposition. "
                "Return only JSON matching the schema. Compare every proposed semantic field "
                "against the exact selected code excerpts, atomic claims, code facts, and "
                "relations. Author intent and paper terminology are not evidence. Use status "
                "entailed only when reader_subject, transformation, and every supplied input, "
                "output, condition, and boundary are directly established by the selected "
                "evidence. Use partial when a strict subset is established, unsupported when "
                "the proposition adds or conflicts with behavior, and ambiguous when the source "
                "cannot disambiguate roles. Leave claim_ids, fact_ids, relation_ids and span_ids "
                "empty; the binding harness owns evidence identities. A field cannot appear in both "
                "supported_fields and unsupported_fields. An entailed verdict has no unsupported "
                "fields. "
                "Do not reward fluent wording or infer benefits, rationale, performance, loss "
                "terms, dimensions, formulas, or conditions absent from the source."
        )
        repair_error = ""
        for attempt in range(1, 3):
            request = LLMRequest(
                prompt_template_id="method_proposition_evidence_judge_v1",
                prompt=(
                    base_prompt
                    + (
                        " Your previous verdict failed schema or semantic consistency: "
                        + repair_error
                        + ". Return a corrected complete verdict."
                        if repair_error else ""
                    )
                ),
                input_payload=payload,
                schema_name=PropositionEvidenceVerdictV1.__name__,
                response_json_schema=json_schema_for(PropositionEvidenceVerdictV1),
            )
            response = caller(config, request)
            trace: dict[str, Any] = {
                "role": SEMANTIC_VERIFIER,
                "prompt_template_id": request.prompt_template_id,
                "proposition_id": str(payload.get("proposition_id") or ""),
                "attempt": attempt,
                "repair_error": repair_error,
                "effective_config": {
                    "provider": getattr(config.provider, "value", str(config.provider)),
                    "model": config.model,
                    "temperature": config.temperature,
                    "seed": config.seed,
                    "max_output_tokens": config.max_output_tokens,
                    "request_timeout_seconds": config.request_timeout_seconds,
                    "retry_max_attempts": config.retry_max_attempts,
                },
                "response_hash": response.response_hash,
                "finish_reason": response.finish_reason,
                "blocked_reason": response.blocked_reason,
            }
            evidence_judge_traces.append(trace)
            if response.blocked_reason:
                trace["error"] = "blocked"
                return None
            parsed, recovery, error = try_parse_structured_response_with_trace(
                response.text, PropositionEvidenceVerdictV1
            )
            trace["representation_recovery"] = recovery.model_dump(mode="json")
            if parsed is None:
                repair_error = error or "schema_failed"
                trace["error"] = repair_error
                continue
            overlap = set(parsed.supported_fields) & set(parsed.unsupported_fields)
            if overlap:
                repair_error = "fields appear in both supported and unsupported: " + ",".join(sorted(overlap))
                trace["error"] = repair_error
                continue
            trace["result"] = parsed.model_dump(mode="json")
            return parsed
        return None

    def judge_batch(
        payloads: list[dict[str, Any]],
    ) -> list[PropositionEvidenceVerdictV1 | None]:
        """Judge one closed concept cluster in a single model request."""

        if not payloads:
            return []
        if len(payloads) == 1:
            return [judge(payloads[0])]

        compact_rows: list[dict[str, Any]] = []
        proposition_ids: list[str] = []
        for index, payload in enumerate(payloads, start=1):
            proposition_ids.append(str(payload.get("proposition_id") or ""))
            compact_rows.append({
                "judgment_index": index,
                "proposed_semantics": dict(payload.get("proposed_semantics") or {}),
                "required_semantic_fields": list(
                    payload.get("required_semantic_fields") or ()
                ),
                "atomic_claim_statements": [
                    {
                        "statement": str(item.get("canonical_text") or ""),
                        "required_qualifiers": list(
                            item.get("required_qualifiers") or ()
                        ),
                    }
                    for item in payload.get("selected_atomic_claims") or ()
                ],
                "code_facts": [
                    {
                        "subject": str(item.get("subject") or ""),
                        "predicate": str(item.get("predicate") or ""),
                        "object": item.get("object"),
                        "conditions": list(item.get("conditions") or ()),
                    }
                    for item in payload.get("selected_code_facts") or ()
                ],
                "relations": [
                    {
                        "kind": str(item.get("kind") or ""),
                        "source_symbol": str(item.get("source_symbol") or ""),
                        "target_symbol": str(item.get("target_symbol") or ""),
                    }
                    for item in payload.get("selected_relations") or ()
                ],
                "exact_code_excerpts": [
                    {
                        "path": str(item.get("path") or ""),
                        "symbol": str(item.get("symbol") or ""),
                        "line_start": item.get("line_start"),
                        "line_end": item.get("line_end"),
                        "exact_excerpt": str(item.get("exact_excerpt") or ""),
                    }
                    for item in payload.get("exact_code_excerpts") or ()
                ],
            })
        base_prompt = (
            "You are the independent repository Evidence Judge. Return only JSON "
            "matching the batch schema. For each judgment_index, compare every "
            "proposed semantic field only with that row's claims, code facts, "
            "relations, and exact excerpts. Use entailed only when all required "
            "fields and every supplied input, output, condition, and boundary are "
            "directly established. Use partial for a strict supported subset, "
            "unsupported for additions or conflicts, and ambiguous when roles "
            "cannot be resolved. Do not infer benefits, rationale, performance, "
            "dimensions, formulas, or conditions. Return exactly one unique row "
            "for every supplied judgment_index."
        )
        repair_error = ""
        for attempt in range(1, 3):
            request = LLMRequest(
                prompt_template_id="method_proposition_evidence_judge_batch_v1",
                prompt=(
                    base_prompt
                    + (
                        " The previous batch failed closure: "
                        + repair_error
                        + ". Return the complete corrected batch."
                        if repair_error else ""
                    )
                ),
                input_payload={"propositions": compact_rows},
                schema_name=PropositionEvidenceJudgmentBatchV1.__name__,
                response_json_schema=json_schema_for(
                    PropositionEvidenceJudgmentBatchV1
                ),
            )
            response = caller(config, request)
            trace: dict[str, Any] = {
                "role": SEMANTIC_VERIFIER,
                "prompt_template_id": request.prompt_template_id,
                "proposition_count": len(payloads),
                "attempt": attempt,
                "repair_error": repair_error,
                "effective_config": {
                    "provider": getattr(
                        config.provider, "value", str(config.provider)
                    ),
                    "model": config.model,
                    "temperature": config.temperature,
                    "seed": config.seed,
                    "max_output_tokens": config.max_output_tokens,
                    "request_timeout_seconds": config.request_timeout_seconds,
                    "retry_max_attempts": config.retry_max_attempts,
                },
                "response_hash": response.response_hash,
                "finish_reason": response.finish_reason,
                "blocked_reason": response.blocked_reason,
            }
            evidence_judge_traces.append(trace)
            if response.blocked_reason:
                trace["error"] = "blocked"
                return [None] * len(payloads)
            parsed, recovery, error = try_parse_structured_response_with_trace(
                response.text, PropositionEvidenceJudgmentBatchV1
            )
            trace["representation_recovery"] = recovery.model_dump(mode="json")
            if parsed is None:
                repair_error = error or "schema_failed"
                trace["error"] = repair_error
                continue
            by_index = {item.judgment_index: item for item in parsed.judgments}
            expected = set(range(1, len(payloads) + 1))
            if set(by_index) != expected:
                repair_error = "judgment_index set is not closed"
                trace["error"] = repair_error
                continue
            verdicts = [
                PropositionEvidenceVerdictV1(
                    proposition_id=proposition_ids[index - 1],
                    status=by_index[index].status,
                    supported_fields=by_index[index].supported_fields,
                    unsupported_fields=by_index[index].unsupported_fields,
                    rationale=by_index[index].rationale,
                )
                for index in range(1, len(payloads) + 1)
            ]
            trace["result"] = [item.model_dump(mode="json") for item in verdicts]
            return verdicts
        return [None] * len(payloads)

    judge.evidence_judge_traces = evidence_judge_traces  # type: ignore[attr-defined]
    judge.judge_batch = judge_batch  # type: ignore[attr-defined]
    return judge


__all__ = ["build_method_proposition_evidence_judge"]
