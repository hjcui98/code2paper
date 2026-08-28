"""Low-temperature semantic aligner for closed Method propositions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from code2paper.agentic.proposition_semantic_aligner import PropositionSemanticAlignmentV1
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response
from code2paper.llm.role_config import SEMANTIC_VERIFIER, apply_role_config
from code2paper.llm.providers import has_provider_api_key
from code2paper.schemas import LLMConfig, LLMProvider


def build_proposition_semantic_aligner(
    config: LLMConfig,
    *,
    caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
):
    if config.provider == LLMProvider.NONE or not has_provider_api_key(config):
        return None
    role_config = apply_role_config(config, SEMANTIC_VERIFIER).model_copy(
        update={"max_output_tokens": 768}
    )
    invoke = caller or (lambda cfg, request: LLMClient(cfg).complete(request))
    alignment_traces: list[dict[str, Any]] = []

    def align(payload):
        request = LLMRequest(
            prompt_template_id="method_proposition_semantic_alignment_v1",
            prompt=(
                "You are a closed-set semantic aligner, not an evidence judge. Return only JSON. "
                "Decide whether the sentence expresses one or more supplied propositions with the "
                "same subject, transformation, inputs, outputs and conditions. Use only supplied "
                "proposition IDs. Return ambiguous when roles are missing or several readings remain. "
                "Never waive a qualifier, number, formula, branch condition or epistemic caveat."
            ),
            input_payload=payload,
            schema_name=PropositionSemanticAlignmentV1.__name__,
            response_json_schema=json_schema_for(PropositionSemanticAlignmentV1),
        )
        response = invoke(role_config, request)
        trace = {
            "role": SEMANTIC_VERIFIER,
            "prompt_template_id": request.prompt_template_id,
            "effective_config": {
                "provider": getattr(role_config.provider, "value", str(role_config.provider)),
                "model": role_config.model,
                "temperature": role_config.temperature,
                "top_p": role_config.top_p,
                "top_k": role_config.top_k,
                "seed": role_config.seed,
                "max_output_tokens": role_config.max_output_tokens,
            },
            "response_hash": response.response_hash,
            "finish_reason": response.finish_reason,
            "blocked_reason": response.blocked_reason,
            "candidate_proposition_ids": [
                str(item.get("proposition_id") or "")
                for item in payload.get("candidate_propositions", ())
                if isinstance(item, dict)
            ],
        }
        alignment_traces.append(trace)
        if response.blocked_reason:
            return None
        parsed, _error = try_parse_structured_response(
            response.text, PropositionSemanticAlignmentV1
        )
        trace["result"] = (
            parsed.model_dump(mode="json") if parsed is not None else None
        )
        return parsed

    align.alignment_traces = alignment_traces  # type: ignore[attr-defined]
    return align
