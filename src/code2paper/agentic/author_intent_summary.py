from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from code2paper.agentic.contracts import AgenticRunState
from code2paper.core.author_questionnaire import load_author_markers
from code2paper.core.schemas import (
    AuthorDesignIntent,
    AuthorInnovationClaim,
    AuthorKeyBuildingBlock,
    AuthorMarkers,
    AuthorModuleRole,
    AuthorPipelineStep,
    AuthorPotentialMismatch,
)


MAX_ITEMS: Final = 12
# Structured author fields are already bounded by MAX_ITEMS.  The previous
# 240-character cap silently removed later pipeline mechanisms from real
# mainlines/stages, changing the obligation graph rather than merely compacting
# it.  Keep a defensive per-field bound while preserving normal questionnaire
# entries in full.
MAX_TEXT: Final = 2048


class AuthorIntentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: str = "agentic-author-intent-summary"
    project_goal: str = ""
    method_goal: str = ""
    implementation_scope: str = ""
    method_mainline: str = ""
    story_order: list[str] = Field(default_factory=list)
    deemphasize_details: list[str] = Field(default_factory=list)
    priority_files: list[str] = Field(default_factory=list)
    ignore_files: list[str] = Field(default_factory=list)
    module_roles: list[str] = Field(default_factory=list)
    key_building_blocks: list[str] = Field(default_factory=list)
    pipeline_steps: list[str] = Field(default_factory=list)
    design_intents: list[str] = Field(default_factory=list)
    innovation_claims: list[str] = Field(default_factory=list)
    potential_mismatches: list[str] = Field(default_factory=list)


def build_author_intent_summary(markers: AuthorMarkers) -> AuthorIntentSummary:
    return AuthorIntentSummary(
        project_goal=_trim(markers.project_goal),
        method_goal=_trim(markers.paper_method_goal or markers.project_goal),
        implementation_scope=_trim(markers.implementation_scope),
        method_mainline=_trim(markers.method_mainline),
        story_order=_limited_texts(markers.paper_story_order),
        deemphasize_details=_limited_texts(markers.deemphasize_details),
        priority_files=_limited_texts(markers.priority_files),
        ignore_files=_limited_texts(markers.ignore_files),
        module_roles=[_module_role_summary(role) for role in markers.module_roles[:MAX_ITEMS]],
        key_building_blocks=[
            _key_building_block_summary(block)
            for block in markers.key_building_blocks[:MAX_ITEMS]
        ],
        pipeline_steps=[_pipeline_step_summary(step) for step in markers.pipeline_steps[:MAX_ITEMS]],
        design_intents=[_design_intent_summary(intent) for intent in markers.design_intents[:MAX_ITEMS]],
        innovation_claims=[_innovation_claim_summary(claim) for claim in markers.innovation_claims[:MAX_ITEMS]],
        potential_mismatches=[_potential_mismatch_summary(mismatch) for mismatch in markers.potential_mismatches[:MAX_ITEMS]],
    )


def load_author_intent_summary(path: str | Path) -> AuthorIntentSummary | None:
    candidate = Path(path)
    if not str(path).strip() or not candidate.exists():
        return None
    try:
        return build_author_intent_summary(load_author_markers(candidate))
    except (OSError, ValidationError, yaml.YAMLError):
        return None


def author_intent_summary_from_state(state: AgenticRunState) -> AuthorIntentSummary | None:
    author_path = state.effective_author_markers_path
    if not author_path:
        return None
    return load_author_intent_summary(author_path)


def _module_role_summary(role: AuthorModuleRole) -> str:
    symbol = f"::{role.symbol}" if role.symbol else ""
    return _trim(f"{role.path}{symbol}: {role.role}")


def _key_building_block_summary(block: AuthorKeyBuildingBlock) -> str:
    return _trim(f"{block.name}: {block.role}")


def _pipeline_step_summary(step: AuthorPipelineStep) -> str:
    return _trim(f"{step.name}: {step.purpose}")


def _design_intent_summary(intent: AuthorDesignIntent) -> str:
    return _trim(intent.intent)


def _innovation_claim_summary(claim: AuthorInnovationClaim) -> str:
    return _trim(claim.claim)


def _potential_mismatch_summary(mismatch: AuthorPotentialMismatch) -> str:
    return _trim(mismatch.description)


def _limited_texts(values: list[str]) -> list[str]:
    return [_trim(value) for value in values[:MAX_ITEMS] if _trim(value)]


def _trim(value: str) -> str:
    text = str(value or "").strip()
    if len(text) <= MAX_TEXT:
        return text
    return text[:MAX_TEXT].rstrip()
