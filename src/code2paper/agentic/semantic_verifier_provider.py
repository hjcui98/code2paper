from __future__ import annotations

from typing import Any

from code2paper.agentic.decision_models import SemanticEvidenceProposal
from code2paper.core.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key, with_node_output_budget
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response


class LLMSemanticEvidenceVerifier:
    """Isolated claim/evidence verifier with auditable, bounded calls."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = with_node_output_budget(config, "text_evidence_validator", 512)
        self.traces: list[dict[str, Any]] = []

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        request = LLMRequest(
            prompt_template_id="agentic_text_evidence_semantic_verifier_v1",
            prompt=(
                "You are an evidence entailment verifier, isolated from the Method writer. "
                "Use only the supplied direct code evidence; never use outside knowledge. "
                "Decide whether the atomic claim stays within the allowed wording boundary and qualifiers. "
                "Return strict JSON. When any part is unsupported, identify supported and unsupported fragments."
            ),
            input_payload=payload,
            schema_name=SemanticEvidenceProposal.__name__,
            response_json_schema=json_schema_for(SemanticEvidenceProposal),
        )
        response = LLMClient(self.config).complete(request)
        parsed, error = (None, response.blocked_reason)
        if not response.blocked_reason:
            parsed, error = try_parse_structured_response(response.text, SemanticEvidenceProposal)
        trace = {
            "prompt_template_id": request.prompt_template_id,
            "input_hash": request.input_hash,
            "response_hash": response.response_hash,
            "response_mode": response.response_mode,
            "finish_reason": response.finish_reason,
            "token_usage": response.token_usage or {},
            "cached": response.cached,
            "blocked_reason": response.blocked_reason,
            "parse_error": error or "",
            "schema_validation_passed": parsed is not None,
        }
        self.traces.append(trace)
        if parsed is None:
            return None
        result = parsed.model_dump(mode="json")
        result["_response_metadata"] = trace
        return result


def build_llm_semantic_verifier(config: LLMConfig | None) -> LLMSemanticEvidenceVerifier | None:
    if config is None or config.provider == LLMProvider.NONE or not has_provider_api_key(config):
        return None
    return LLMSemanticEvidenceVerifier(config)
