from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from pydantic import BaseModel

from code2paper.agentic.decision_core import AgenticDecisionPrompt, DecisionProvider, DecisionProviderResult
from code2paper.agentic.decision_models import (
    AnalysisRepairRouterProposal,
    AuthoringPlanProposal,
    CoverageCriticProposal,
    EvidenceSufficiencyProposal,
    RevisionRouterProposal,
)
from code2paper.agentic.figure_planner import FigurePlanProposal
from code2paper.core.schemas import LLMConfig, LLMProvider
from code2paper.llm.client import LLMClient, LLMRequest
from code2paper.llm.providers import has_provider_api_key
from code2paper.llm.response_schemas import json_schema_for, try_parse_structured_response

ProposalSchema = (
    type[CoverageCriticProposal]
    | type[RevisionRouterProposal]
    | type[AuthoringPlanProposal]
    | type[EvidenceSufficiencyProposal]
    | type[AnalysisRepairRouterProposal]
    | type[FigurePlanProposal]
)

_PROPOSAL_SCHEMAS: Final[Mapping[str, ProposalSchema]] = {
    "coverage_critic": CoverageCriticProposal,
    "analysis_repair_router": AnalysisRepairRouterProposal,
    "evidence_sufficiency": EvidenceSufficiencyProposal,
    "revision_router": RevisionRouterProposal,
    "authoring_planner": AuthoringPlanProposal,
    "figure_planner": FigurePlanProposal,
}

_NODE_MAX_OUTPUT_TOKENS: Final[Mapping[str, int]] = {
    "coverage_critic": 512,
    "analysis_repair_router": 512,
    "evidence_sufficiency": 512,
    "revision_router": 512,
    "authoring_planner": 1024,
    "figure_planner": 1024,
}


def build_llm_decision_provider(llm_config: LLMConfig | None) -> DecisionProvider | None:
    """Build an LLM-backed decision provider for agentic graph routing.

    The provider returns only a proposal. Graph safety rules still merge or
    reject that proposal before it can affect routing.
    """

    if llm_config is None or llm_config.provider == LLMProvider.NONE:
        return None
    if not has_provider_api_key(llm_config):
        return None

    def _provider(prompt: AgenticDecisionPrompt) -> Mapping[str, Any] | BaseModel | None:
        schema = _proposal_schema(prompt.node)
        if schema is None:
            return None
        request = LLMRequest(
            prompt_template_id=f"agentic_{prompt.node}_decision_v1",
            prompt=_decision_system_prompt(prompt.node),
            input_payload=prompt.model_dump(mode="json"),
            schema_name=schema.__name__,
            response_json_schema=json_schema_for(schema),
        )
        node_config = llm_config.model_copy(
            update={"max_output_tokens": min(llm_config.max_output_tokens, _NODE_MAX_OUTPUT_TOKENS[prompt.node])}
        )
        response = LLMClient(node_config).complete(request)
        response_metadata = {
            "response_mode": response.response_mode,
            "finish_reason": response.finish_reason,
            "token_usage": response.token_usage or {},
            "blocked_reason": response.blocked_reason,
            "schema_name": request.schema_name,
            "max_output_tokens": node_config.max_output_tokens,
        }
        if response.blocked_reason:
            return DecisionProviderResult(proposal=None, response_metadata=response_metadata)
        parsed, error = try_parse_structured_response(response.text, schema)
        response_metadata["parse_error"] = error or ""
        response_metadata["schema_validation_passed"] = parsed is not None
        return DecisionProviderResult(proposal=parsed, response_metadata=response_metadata)

    return _provider


def supported_llm_decision_nodes() -> tuple[str, ...]:
    return tuple(_PROPOSAL_SCHEMAS)


def _proposal_schema(node: str) -> ProposalSchema | None:
    return _PROPOSAL_SCHEMAS.get(node)


def _decision_system_prompt(node: str) -> str:
    return (
        "You are a routing decision assistant inside Code2Paper's agentic graph.\n"
        "Return only JSON matching the requested schema.\n"
        "You may propose a route, rationale, and targeted hints, but the system will reject unsafe routes.\n"
        "Hard constraints:\n"
        "- Author intent guides retrieval priorities; code evidence decides what may be claimed.\n"
        "- Do not bypass frozen MethodEvidence, claim verification, validation, or invariant audit.\n"
        "- Unsupported claims must be downgraded, caveated, excluded, or sent back for evidence.\n"
        f"Current decision node: {node}."
    )
