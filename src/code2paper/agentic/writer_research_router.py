"""Route writing-time information requests to their owning evidence lane."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_argument_models import WritingResearchRequestV1


RouteOwnerV1 = Literal[
    "repository_tools",
    "configuration_tools",
    "author_confirmation_queue",
    "empirical_artifact_tools",
    "external_literature_tools",
    "formalization_agent",
]


class WritingResearchRouteV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str
    request_id: str
    owner: RouteOwnerV1
    section_id: str
    argument_unit_id: str
    scope: tuple[str, ...] = Field(default_factory=tuple)
    required_authority_lane: str
    rationale: str
    resume_section_only: bool = True
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "WritingResearchRouteV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        object.__setattr__(self, "content_digest", "sha256:" + hashlib.sha256(encoded).hexdigest())
        return self


def route_writing_research_request(request: WritingResearchRequestV1) -> WritingResearchRouteV1:
    """Select an owner without broadening the requested scope."""

    owner_by_lane: dict[str, RouteOwnerV1] = {
        "executable_hard": "repository_tools",
        "configuration_resolved": "configuration_tools",
        "author_attested": "author_confirmation_queue",
        "formal_derivation": "formalization_agent",
        "empirical_artifact": "empirical_artifact_tools",
        "external_literature": "external_literature_tools",
        "expository_bridge": "repository_tools",
    }
    owner = owner_by_lane[request.required_authority_lane]
    return WritingResearchRouteV1(
        route_id="route:" + hashlib.sha256(request.request_id.encode("utf-8")).hexdigest()[:20],
        request_id=request.request_id,
        owner=owner,
        section_id=request.section_id,
        argument_unit_id=request.argument_unit_id,
        scope=request.candidate_symbols_or_terms,
        required_authority_lane=request.required_authority_lane,
        rationale=(
            f"The requested move requires the {request.required_authority_lane} lane; "
            f"resume section {request.section_id} after the owning artifact is validated."
        ),
    )


def route_writing_research_requests(
    requests: list[WritingResearchRequestV1] | tuple[WritingResearchRequestV1, ...],
) -> tuple[WritingResearchRouteV1, ...]:
    return tuple(route_writing_research_request(request) for request in requests)


__all__ = [
    "RouteOwnerV1",
    "WritingResearchRouteV1",
    "route_writing_research_request",
    "route_writing_research_requests",
]
