"""Closed-set proposition retrieval and bounded semantic alignment."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_proposition_models import MethodPropositionV1


class PropositionSemanticAlignmentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["matched", "no_match", "ambiguous"]
    matched_proposition_ids: tuple[str, ...] = Field(default_factory=tuple)
    preserved_roles: tuple[str, ...] = Field(default_factory=tuple)
    missing_roles: tuple[str, ...] = Field(default_factory=tuple)
    rationale: str = ""

    @model_validator(mode="after")
    def _status_consistent(self) -> "PropositionSemanticAlignmentV1":
        if self.status == "matched" and not self.matched_proposition_ids:
            raise ValueError("matched proposition alignment requires IDs")
        if self.status != "matched" and self.matched_proposition_ids:
            raise ValueError("non-matched alignment cannot carry matched IDs")
        return self


SemanticAligner = Callable[[dict[str, Any]], PropositionSemanticAlignmentV1 | dict[str, Any] | None]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_-]+", text.casefold()))


_AUTHORITY_MARKERS = {
    "negation": re.compile(r"\b(?:not|never|without|cannot|doesn't|isn't)\b", re.I),
    "absolute": re.compile(r"\b(?:always|guarantee(?:s|d)?|ensure(?:s|d)?)\b", re.I),
    "causal": re.compile(r"\b(?:cause(?:s|d)?|enable(?:s|d)?|lead(?:s)? to)\b", re.I),
    "performance": re.compile(
        r"\b(?:improv(?:e|es|ed|ing)|outperform(?:s|ed)?|faster|"
        r"more accurate|state[- ]of[- ]the[- ]art|speedup)\b",
        re.I,
    ),
}


def _authority_marker_set(text: str) -> set[str]:
    return {
        name for name, pattern in _AUTHORITY_MARKERS.items() if pattern.search(text)
    }


def _authority_expands(sentence: str, proposition: MethodPropositionV1) -> bool:
    proposition_surface = " ".join((
        proposition.reader_subject,
        proposition.transformation,
        *proposition.inputs,
        *proposition.outputs,
        *proposition.conditions,
        proposition.boundary,
        *proposition.paper_terms,
    ))
    return bool(
        _authority_marker_set(sentence) - _authority_marker_set(proposition_surface)
    )


def _expected_semantic_roles(proposition: MethodPropositionV1) -> set[str]:
    roles = {"subject", "transformation"}
    if proposition.inputs:
        roles.add("inputs")
    if proposition.outputs:
        roles.add("outputs")
    if proposition.conditions:
        roles.add("conditions")
    return roles


def _exact_role_surface_preserved(
    sentence: str, proposition: MethodPropositionV1
) -> bool:
    lowered = sentence.casefold()
    for values in (proposition.inputs, proposition.outputs, proposition.conditions):
        for value in values:
            if str(value).casefold() not in lowered:
                return False
    return True


def retrieve_section_propositions(
    sentence: str,
    propositions: Iterable[MethodPropositionV1],
    *,
    max_candidates: int = 6,
) -> tuple[tuple[MethodPropositionV1, ...], bool]:
    sentence_tokens = _tokens(sentence)
    ranked: list[tuple[float, MethodPropositionV1]] = []
    for proposition in propositions:
        semantic_text = " ".join((
            proposition.reader_subject, proposition.transformation,
            *proposition.inputs, *proposition.outputs, *proposition.conditions,
            *proposition.paper_terms, *proposition.implementation_binding_terms,
        ))
        semantic_tokens = _tokens(semantic_text)
        if not semantic_tokens:
            continue
        overlap = len(sentence_tokens & semantic_tokens) / max(
            1, min(len(sentence_tokens), len(semantic_tokens))
        )
        # Keep the closed section set available to the bounded semantic owner
        # even when a genuine academic paraphrase shares no surface token
        # (e.g. ``uses`` versus ``is consumed by``). Lexical score still ranks
        # candidates and exact overlap still bypasses the model; zero-overlap
        # rows cannot pass without an explicit closed-set semantic decision.
        ranked.append((overlap, proposition))
    ranked.sort(key=lambda item: (-item[0], item[1].proposition_id))
    candidates = tuple(item for _score, item in ranked[:max_candidates])
    exact = bool(ranked and ranked[0][0] >= 0.72)
    return candidates, exact


def align_sentence_to_section_propositions(
    sentence: str,
    propositions: Iterable[MethodPropositionV1],
    *,
    semantic_aligner: SemanticAligner | None = None,
    max_candidates: int = 6,
) -> PropositionSemanticAlignmentV1:
    candidates, exact = retrieve_section_propositions(
        sentence, propositions, max_candidates=max_candidates,
    )
    if not candidates:
        return PropositionSemanticAlignmentV1(
            status="no_match", rationale="No closed section proposition was retrieved.",
        )
    if exact:
        lowered = sentence.casefold()
        if _authority_expands(sentence, candidates[0]):
            return PropositionSemanticAlignmentV1(
                status="no_match",
                rationale="Sentence changes proposition polarity or authority strength.",
            )
        if not _exact_role_surface_preserved(sentence, candidates[0]):
            return PropositionSemanticAlignmentV1(
                status="no_match",
                rationale="A proposition input, output, or condition was not preserved.",
            )
        if candidates[0].requires_caveat and not any(marker in lowered for marker in (
            "intend", "aim", "partial", "pending", "unverified", "mismatch", "confirmation",
        )):
            return PropositionSemanticAlignmentV1(
                status="no_match", rationale="Candidate-only proposition lacks a visible caveat.",
            )
        required = (
            *candidates[0].required_qualifiers,
            *candidates[0].immutable_numeric_tokens,
            *candidates[0].immutable_formula_tokens,
        )
        if any(str(token).casefold() not in lowered for token in required):
            return PropositionSemanticAlignmentV1(
                status="no_match", rationale="Immutable proposition constraints were not preserved.",
            )
        return PropositionSemanticAlignmentV1(
            status="matched", matched_proposition_ids=(candidates[0].proposition_id,),
            preserved_roles=("subject", "transformation"),
            rationale="Deterministic exact semantic-field overlap.",
        )
    if semantic_aligner is None:
        return PropositionSemanticAlignmentV1(
            status="ambiguous", rationale="Candidates retrieved but semantic aligner unavailable.",
        )
    raw = semantic_aligner({
        "sentence": sentence,
        "candidate_propositions": [
            {
                "proposition_id": item.proposition_id,
                "semantic_fields": {
                    "subject": item.reader_subject,
                    "transformation": item.transformation,
                    "inputs": list(item.inputs),
                    "outputs": list(item.outputs),
                    "conditions": list(item.conditions),
                },
                "constraints": {
                    "qualifiers": list(item.required_qualifiers),
                    "numbers": list(item.immutable_numeric_tokens),
                    "formulas": list(item.immutable_formula_tokens),
                },
            }
            for item in candidates
        ],
    })
    if raw is None:
        return PropositionSemanticAlignmentV1(status="ambiguous", rationale="Semantic aligner unavailable.")
    result = raw if isinstance(raw, PropositionSemanticAlignmentV1) else PropositionSemanticAlignmentV1.model_validate(raw)
    allowed = {item.proposition_id for item in candidates}
    if set(result.matched_proposition_ids) - allowed:
        return PropositionSemanticAlignmentV1(status="no_match", rationale="Aligner returned an ID outside the closed set.")
    if result.status == "matched" and result.missing_roles:
        return PropositionSemanticAlignmentV1(status="ambiguous", rationale="Semantic roles are missing.")
    if result.status == "matched":
        lowered = sentence.casefold()
        for item in candidates:
            if item.proposition_id not in result.matched_proposition_ids:
                continue
            if not _expected_semantic_roles(item).issubset(
                set(result.preserved_roles)
            ):
                return PropositionSemanticAlignmentV1(
                    status="ambiguous",
                    rationale="The aligner did not affirm every required semantic role.",
                )
            if _authority_expands(sentence, item):
                return PropositionSemanticAlignmentV1(
                    status="no_match",
                    rationale="Sentence changes proposition polarity or authority strength.",
                )
            required = (*item.required_qualifiers, *item.immutable_numeric_tokens, *item.immutable_formula_tokens)
            if any(str(token).casefold() not in lowered for token in required):
                return PropositionSemanticAlignmentV1(status="no_match", rationale="Immutable proposition constraints were not preserved.")
            if item.requires_caveat and not any(marker in lowered for marker in (
                "intend", "aim", "partial", "pending", "unverified", "mismatch", "confirmation",
            )):
                return PropositionSemanticAlignmentV1(status="no_match", rationale="Candidate-only proposition lacks a visible caveat.")
    return result
