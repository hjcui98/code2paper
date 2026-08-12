"""Versioned, repository-local publication Method writer skill."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicationMethodWriterSkillV1(BaseModel):
    """Prompt-level writing contract kept separate from evidence schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: str = "publication-method-writer"
    version: str = "1.8"
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
        "Every positive factual sentence must be supported by one or more supplied semantic-frame slots (subject, predicate, operands, conditions, produced entities) or a fulfilled callback artifact; a sentence that states content no supplied slot authorizes is a new unsupported claim.",
        "Render each argument_flow slot's operation as a normal Method sentence in your own words, from the reader's perspective: write what the operation does with its operands, not the record itself.  Do not copy any example sentence from this skill or from the prompt into the section; every sentence must describe the section's own authorized slots.",
        "Use reader_facing_claims as the sentence plan: express each paper_statement in your own Method language.  code_binding_terms exist only to preserve factual binding; prefer paper terms over raw identifiers, and when a raw identifier must be mentioned put it in a short implementation clause, not as the grammatical center of the sentence.",
        "The validation_constraints channel lists the exact canonical wording, qualifiers, equations, and configuration values that the reverse validator enforces.  It is a meaning-checking channel, not a wording template: preserve required qualifiers, equations, numeric values, and semantic roles; do not preserve raw code token spelling unless it is the paper-level term or an implementation-realization detail.  Never emit a constraint record itself as a sentence.",
        "The reverse validator requires your factual sentence to express the slot's semantic content, so keep the operation's meaningful operands, predicate meaning, and conditions — but write a readable sentence, not a record serialization.  A section that reads like a source-code execution log (repeated raw identifiers as sentence subjects) fails the publication-quality style guard even when every sentence validates.",
        "You may combine several slots into one factual sentence when they describe one connected operation flow (for example a load-then-compute-then-return chain), joined by sequence connectives such as then, after, first, before, or once.  Every operand and predicate meaning in the combined sentence must remain attributable to one of the slots.",
        "Never write a sentence that names rhetorical moves or recaps the section organization (for example 'The implementation stage 1 begins with the mechanism overview and implementation realization'): move names, reader questions, headings, and objectives are organization context, not factual anchors.",
        "An equation constraint is covered by its prose claim sentence (prose_claim_id): write that claim sentence and bind both ids; never emit a separate equation sentence and never write 'The expression ...', 'The equation ... is computed', or '... corresponds to the selected code operations'.",
        "Write the equation's own code expression with bound operand values substituted (for example 'positions * div_term' for x * y with bindings x -> positions, y -> div_term) rather than a prose gloss or a bare expression standing alone.",
        "Do not add explanations such as aligns, establishes, enables, defines, handles, ensures, or subsequent stages, and do not add purpose, benefit, robustness, consistency, determinism, causality, or performance language unless the supplied authority explicitly states it.",
        "Claim-free organization, transition, and definition scaffolding is allowed only as an expository bridge: start the sentence with a bridge marker (for example 'In this section', 'Next', 'We now describe', 'For clarity') and include no claim/equation/configuration operand, behavior predicate, number, or formula in it.  A bridge sentence that carries factual content will be reverse-validated as a factual claim.",
        "Write only required moves that have anchors. Do not fill an optional or unanchored move with a template sentence, and do not use labels such as 'The mechanism overview', 'The equation', 'The formal objects', or 'The method' as factual subjects.",
        "Start section_markdown with exactly one Markdown H2 heading copied from the supplied heading field (format: '## <heading>'), then write the first anchored Method sentence.  The heading is section structure, not factual evidence; never invent, rename, or expand it.",
        "If several slots share the same operation, write that sentence once and bind all of their IDs; do not repeat identical information merely because the IDs differ.",
        "One sentence or paragraph may complete several rhetorical moves. Never restate the same operation separately for mechanism overview, algorithm/data flow, and implementation realization; describe it once in the most natural Method paragraph and list every move that paragraph genuinely completes only in completed_rhetorical_moves.",
        "Treat section_candidate_points as an explicit candidate-narrative paragraph plan. Group related points into coherent paragraphs in argument-unit order, state each point once, and visibly preserve its caveat (for example intended, partially supported, mismatched, or pending confirmation). Candidate narrative is allowed in the editable candidate even when it cannot enter the repository-verified output.",
        "For a section with multiple argument units, use paragraph breaks to separate conceptual subtopics. Do not create one paragraph per bookkeeping record and do not collapse all candidate points into a generic overview sentence.",
        "Treat reader questions, design objectives, headings, method names, and rhetorical moves as organization context, never as repository evidence or implementation facts.",
        "If a required move has no authorized factual anchor and is not expository-bridge completable, emit one scoped WritingResearchRequestV1 and leave that move unresolved instead of filling it with generic prose.",
        "When grounding_contract.callback_required is true, do not claim that the section is complete: return one compact unresolved callback for an unanchored required move and keep completed_rhetorical_moves limited to anchored moves.",
        "When writing_research_callback_resolution lists a fulfilled move, use only its digest-bound artifact preview/ref for that move, add one sentence grounded in that artifact, mark the move complete, and never reopen or replace the fulfilled request.",
        "A fulfilled callback does not authorize any neighboring move, claim, equation, configuration, purpose, benefit, or rationale; keep every other sentence within its own authorized anchor.",
        "Use code identifiers, dimensions, constants, formulas, and branch conditions only when they occur in the supplied authorized records.",
        "Do not mention source line numbers, file locations, evidence ids, frame slot ids, or validator bookkeeping unless the exact supplied authorized record contains that item as part of its wording.",
        "Never write a meta-description sentence about an equation, claim, slot, or anchor (for example 'The displayed expression is equivalent to the selected code operations for equation:...' or 'This formula corresponds to claim:...').  Write the authorized expression or claim itself as the factual sentence; do not frame or describe an anchor by its id.",
        "Repeat a required qualifier in every factual sentence that uses its claim; a qualifier in a preceding sentence does not scope a later sentence.",
        "Do not expose evidence ids, validator messages, or bookkeeping language.",
        "Write content first, then bind used argument and claim ids in the response object.",
        "Copy every binding id exactly from binding_contract; never derive, rename, or invent an id.",
        "List every required rhetorical move actually completed in completed_rhetorical_moves.",
        "Emit each paragraph once; never repeat a completed section or restart the same heading.",
        "Keep section_markdown to paper prose only; never serialize output field names or binding metadata inside it.",
    )
    callback_protocol: tuple[str, ...] = (
        "Return a scoped WritingResearchRequestV1 when a required move lacks evidence.",
        "If callback_required is true, emit one request for every move in unanchored_required_moves with the exact section_id, an allowed argument_unit_id, an allowed required_authority_lane, status='open', and a precise exact_question; do not mark those moves complete.",
        "On resume, consume each fulfilled callback artifact exactly once: complete only its bound move, do not reopen it, and do not infer authority for other moves.",
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
        {
            "good": "The feature representation is assembled by iterating over the available feature channels and then applying the recorded normalization step before downstream scoring.",
            "bad": "The module calls range with operand x.shape[1] and then passes normalized to normalize.",
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
            "Return structured content-first output with section_id copied exactly from the supplied section_id (do not omit it), section_markdown, used_argument_unit_ids, used_claim_ids, used_equation_ids, used_configuration_ids, completed_rhetorical_moves, new_research_requests, and self_identified_risks.",
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
