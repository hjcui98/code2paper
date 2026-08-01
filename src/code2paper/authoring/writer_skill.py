"""Versioned, repository-local publication Method writer skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicationMethodWriterSkillV1(BaseModel):
    """Prompt-level writing contract kept separate from evidence schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: str = "publication-method-writer"
    version: str = "1.0"
    audience: str = "technical paper readers"
    venue: str = ""
    rhetorical_moves: tuple[str, ...] = (
        "problem_or_local_context",
        "design_objective",
        "mechanism_overview",
        "intuition_or_rationale",
        "formal_objects_and_notation",
        "equation_or_derivation",
        "algorithm_or_data_flow",
        "implementation_realization",
        "configuration_and_branches",
        "training_objective",
        "inference_and_output",
        "complexity_or_boundary_conditions",
        "limitations_or_mismatch",
        "transition_to_next_section",
    )
    authority_rules: tuple[str, ...] = (
        "Treat executable_hard as implementation evidence only.",
        "Use configuration_resolved for actual/default/conditional branch statements.",
        "Use formal_derivation only with explicit assumptions and source operations.",
        "Do not turn author intent, hints, or paper drafts into repository facts.",
        "Keep empirical, literature, and author-attested statements in their own lanes.",
    )
    style_rules: tuple[str, ...] = (
        "Explain input -> transformation -> condition -> output when the graph supports it.",
        "Define symbols before using an equation and state branch conditions.",
        "Use transitions and intuition only when they add no new factual claim.",
        "Do not expose evidence ids, validator messages, or bookkeeping language.",
        "Write content first, then bind used argument and claim ids in the response object.",
    )
    callback_protocol: tuple[str, ...] = (
        "Return a scoped WritingResearchRequestV1 when a required move lacks evidence.",
        "Resume only the affected section after a callback artifact is validated.",
        "Mark the section incomplete when a critical move remains unresolved.",
    )
    prohibited_shortcuts: tuple[str, ...] = (
        "deterministic prose placeholders",
        "unsupported performance or novelty claims",
        "conditional behavior written as default behavior",
        "mechanical synonym expansion",
    )
    examples: tuple[dict[str, str], ...] = Field(default_factory=lambda: (
        {
            "good": "The encoder first forms the input representation, then applies the guarded transformation before emitting the score.",
            "bad": "The encoder is powerful and improves the result.",
        },
        {
            "good": "Under the evaluation branch, the normalized value is passed to the selector; the training branch is described separately.",
            "bad": "The same path is always used.",
        },
    ))

    @model_validator(mode="after")
    def _versioned(self) -> "PublicationMethodWriterSkillV1":
        if not self.skill_id or not self.version:
            raise ValueError("writer skill must be versioned")
        return self

    def system_prompt(self) -> str:
        lines = [
            f"You are a publication Method writer, skill {self.skill_id}/{self.version}.",
            f"Audience: {self.audience}. Venue: {self.venue or 'unspecified'}.",
            "Generate one focused section from the supplied argument graph and authorized inputs.",
            "Hard constraints and authority rules:",
            *[f"- {rule}" for rule in self.authority_rules],
            "Writing rules:",
            *[f"- {rule}" for rule in self.style_rules],
            "Callback rules:",
            *[f"- {rule}" for rule in self.callback_protocol],
            "Never use:",
            *[f"- {rule}" for rule in self.prohibited_shortcuts],
            "Return structured content-first output with section_markdown, used_argument_unit_ids, used_claim_ids, used_equation_ids, new_research_requests, and self_identified_risks.",
        ]
        return "\n".join(lines)


def load_publication_method_writer_skill(path: str | Path | None = None) -> PublicationMethodWriterSkillV1:
    """Load the versioned skill; a missing optional file uses the contract above."""

    if path is None:
        return PublicationMethodWriterSkillV1()
    candidate = Path(path)
    if not candidate.exists():
        return PublicationMethodWriterSkillV1()
    # The checked-in prompt is prose, not a second source of truth.  Loading
    # it is useful to callers that want a local override while model fields
    # remain the auditable contract.
    text = candidate.read_text(encoding="utf-8").strip()
    return PublicationMethodWriterSkillV1(style_rules=(
        *PublicationMethodWriterSkillV1().style_rules,
        f"Local prompt extension: {text[:400]}",
    ))


__all__ = ["PublicationMethodWriterSkillV1", "load_publication_method_writer_skill"]
