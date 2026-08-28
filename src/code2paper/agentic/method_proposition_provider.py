"""Low-temperature LLM provider for conceptual Method propositions."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from code2paper.agentic.method_proposition_models import (
    MethodPropositionProposalBatchV1,
    MethodPropositionProposalV1,
    PropositionCandidateClusterV1,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import METHOD_PROPOSITION_ARCHITECT, apply_role_config
from code2paper.schemas import LLMConfig


_BINDING_STOP_WORDS = frozenset({
    "a", "an", "and", "as", "by", "for", "from", "in", "into", "is",
    "method", "of", "on", "or", "per", "the", "to", "using", "with",
})

_IDENTIFIER_WORDS = {
    "avg": "average",
    "dists": "distances",
    "dist": "distance",
    "volumn": "volume",
    "rgb": "RGB",
    "sh": "spherical-harmonic",
}
_IDENTIFIER_NOISE = frozenset({"f", "p", "self", "torch"})


class _ArchitectSemanticCardV1(BaseModel):
    """LLM-owned concept fields; all binding identity stays private."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    reader_subject: str = Field(max_length=160)
    transformation: str = Field(max_length=360)
    inputs: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    outputs: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    conditions: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    boundary: str = Field(default="", max_length=360)
    paper_terms: tuple[str, ...] = Field(default_factory=tuple, max_length=24)
    implementation_binding_terms: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    source_statement_fragments: tuple[str, ...] = Field(default_factory=tuple, max_length=12)


class _ArchitectSemanticBatchV1(BaseModel):
    """Compact guided-decoding response surface."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    proposals: tuple[_ArchitectSemanticCardV1, ...] = Field(
        min_length=1,
        max_length=12,
    )


def _binding_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", value.casefold().replace("_", " ")):
        if len(token) <= 1 or token in _BINDING_STOP_WORDS:
            continue
        if token in {"cat", "concat", "concatenate", "concatenates", "concatenation"}:
            tokens.add("concat")
        elif token in {"normalize", "normalizes", "normalized", "normalization"}:
            tokens.add("normalize")
        elif token in {"sort", "sorts", "sorted", "sorting"}:
            tokens.add("sort")
        elif token in {"reduce", "reduces", "reduced", "reduction"}:
            tokens.add("reduce")
        elif token in {"compute", "computes", "computed", "computation"}:
            tokens.add("compute")
        elif token in {"return", "returns", "returned"}:
            tokens.add("return")
        else:
            tokens.add(token)
    return tokens


_MECHANISM_BINDING_TOKENS = frozenset({
    "call", "compute", "concat", "construct", "filter", "mask",
    "normalize", "project", "propagate", "reduce", "return", "sample",
    "select", "sort", "stack", "transform",
})


def _mechanism_binding_tokens(value: str) -> set[str]:
    tokens = _binding_tokens(value)
    return {
        token for token in tokens
        if token in _MECHANISM_BINDING_TOKENS or token.isdigit()
    }


def _humanize_code_identifier(value: str) -> str:
    """Return a reader-term hint derived only from an exact code token.

    This is deliberately a lexical projection, not a factual proposition.
    It lets the Architect call ``f_p_avg_dists_z_score_local`` an average-
    distance local z-score component without giving author prose authority
    over repository behavior.  The evidence judge still evaluates the
    resulting conceptual card against the exact source excerpts.
    """

    surface = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    words = [
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9]*", surface.replace(".", "_"))
        if word.casefold() not in _IDENTIFIER_NOISE
    ]
    rendered: list[str] = []
    index = 0
    while index < len(words):
        if index + 1 < len(words) and words[index:index + 2] == ["z", "score"]:
            rendered.append("z-score")
            index += 2
            continue
        feature_width = re.fullmatch(r"f(\d+)", words[index])
        if feature_width:
            rendered.append(f"{feature_width.group(1)}-dimensional feature")
            index += 1
            continue
        rendered.append(_IDENTIFIER_WORDS.get(words[index], words[index]))
        index += 1
    return " ".join(rendered)


def _code_term_hints(cluster: PropositionCandidateClusterV1) -> tuple[dict[str, str], ...]:
    """Expose exact identifiers as terminology aids, never as new evidence."""

    raw_terms: list[str] = []
    for value in (*cluster.subjects, *cluster.operands):
        for token in re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?",
            str(value),
        ):
            if "_" not in token and "." not in token:
                continue
            if token not in raw_terms:
                raw_terms.append(token)
    hints: list[dict[str, str]] = []
    for binding in raw_terms[:48]:
        paper_term = _humanize_code_identifier(binding)
        if not paper_term or paper_term.casefold() == binding.casefold():
            continue
        hints.append({"binding": binding, "reader_term_hint": paper_term})
    return tuple(hints)


def _bind_source_fragments(cluster, proposal):
    """Retrieve exact witnesses inside one already-closed cluster.

    This chooses binding metadata, not evidence authority. Repository cards
    with no semantic overlap remain unbound and fail the compiler; the
    independent judge still decides whether a bound card is entailed.
    """

    exact = tuple(dict.fromkeys(
        statement
        for statement in cluster.source_statements
        if any(
            fragment and fragment in statement
            for fragment in proposal.source_statement_fragments
        )
    ))
    surface = " ".join((
        proposal.reader_subject,
        proposal.transformation,
        *proposal.inputs,
        *proposal.outputs,
        *proposal.conditions,
        proposal.boundary,
        *proposal.paper_terms,
        *proposal.implementation_binding_terms,
    ))
    tokens = _binding_tokens(surface)
    mechanism_tokens = _mechanism_binding_tokens(" ".join((
        proposal.transformation,
        *proposal.inputs,
        *proposal.outputs,
        *proposal.conditions,
        proposal.boundary,
        *proposal.paper_terms,
    )))
    candidates = list(exact or cluster.source_statements)
    selected: list[str] = []
    if cluster.origin == "author_intent" and not tokens:
        selected = candidates
    elif candidates:
        # Normalize even model-supplied fragment arrays to a minimal semantic
        # cover. Models commonly copied every statement in a cluster into a
        # generic card, causing unrelated numbers and operations to leak into
        # its immutable constraints. Exact identity still comes from the
        # selected statements; this step only removes irrelevant overbinding.
        scored = [
            (len(tokens & _binding_tokens(statement)), -index, statement)
            for index, statement in enumerate(candidates)
        ]
        best, _neg_index, statement = max(scored, default=(0, 0, ""))
        if best > 0 and statement:
            selected.append(statement)
        elif cluster.origin == "author_intent":
            selected = candidates

    # One conceptual card can require several exact statements from the same
    # connected evidence component.  A descriptor card that says it is both
    # assembled and percentile-normalized, for example, needs CONCAT and the
    # normalization call.  Greedily add only statements that cover a concept
    # token not covered by the model-selected fragment. This stays inside the
    # already closed cluster; the independent judge still decides entailment.
    covered = {
        token
        for statement in selected
        for token in _mechanism_binding_tokens(statement)
    }
    # Reader-subject vocabulary (for example ``descriptor``) identifies the
    # card but must not pull in another operation merely because that sibling
    # statement also mentions the descriptor. Additional witnesses are needed
    # only for uncovered transformation/input/output/condition semantics.
    uncovered = mechanism_tokens - covered
    remaining = [
        statement for statement in cluster.source_statements
        if statement not in selected
    ]
    while uncovered and remaining:
        scored = [
            (len(uncovered & _mechanism_binding_tokens(statement)), statement)
            for statement in remaining
        ]
        best = max((score for score, _statement in scored), default=0)
        if best <= 0:
            break
        statement = next(
            statement for score, statement in scored if score == best
        )
        selected.append(statement)
        statement_tokens = _mechanism_binding_tokens(statement)
        uncovered -= statement_tokens
        remaining.remove(statement)
    return proposal.model_copy(update={
        "source_statement_fragments": tuple(selected)
    })


def _dedupe_proposals(cluster, proposals):
    """Remove duplicate cards without merging distinct method concepts."""

    if cluster.origin != "repository_evidence":
        unique: dict[tuple[Any, ...], Any] = {}
        for proposal in proposals:
            key = (
                proposal.reader_subject.casefold(),
                proposal.transformation.casefold(),
                tuple(item.casefold() for item in proposal.inputs),
                tuple(item.casefold() for item in proposal.outputs),
                tuple(item.casefold() for item in proposal.conditions),
                proposal.boundary.casefold(),
                tuple(item.casefold() for item in proposal.paper_terms),
                tuple(proposal.source_statement_fragments),
            )
            unique.setdefault(key, proposal)
        return tuple(unique.values())
    selected: dict[tuple[str, ...], tuple[int, int, Any]] = {}
    for index, proposal in enumerate(proposals):
        key = tuple(proposal.source_statement_fragments)
        surface = " ".join((
            proposal.reader_subject,
            proposal.transformation,
            *proposal.inputs,
            *proposal.outputs,
            *proposal.conditions,
            *proposal.paper_terms,
        ))
        source = " ".join(key)
        score = len(_binding_tokens(surface) & _binding_tokens(source))
        current = selected.get(key)
        candidate = (score, -index, proposal)
        if current is None or candidate[:2] > current[:2]:
            selected[key] = candidate
    return tuple(
        value[2]
        for value in sorted(selected.values(), key=lambda item: -item[1])
    )


def _repair_payload(validation_error: str) -> dict[str, Any]:
    """Decode compiler feedback while preserving schema/transport errors."""

    if not validation_error:
        return {}
    try:
        value = json.loads(validation_error)
    except (TypeError, ValueError):
        return {"owner_error": validation_error}
    return value if isinstance(value, dict) else {"owner_error": validation_error}


def build_method_proposition_architect(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
):
    """Return a bounded conceptual-card proposer.

    The model may reorganize the supplied semantic material but cannot cite
    IDs outside the cluster.  The deterministic compiler performs that
    authority check after this call.
    """

    config = apply_role_config(llm_config, METHOD_PROPOSITION_ARCHITECT)
    if llm_caller is None:
        # Proposition cards are compact structured semantics. Use the
        # runtime's guided JSON schema mode explicitly; the generic client
        # otherwise defaulted to json_object for this role on the live
        # profile, which allowed multi-thousand-token repetition inside one
        # string field before the JSON object closed.
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
    proposal_traces: list[dict[str, Any]] = []

    def propose(
        cluster: PropositionCandidateClusterV1,
        validation_error: str = "",
    ) -> MethodPropositionProposalBatchV1:
        base_prompt = (
                "You are the Method Proposition Architect. Convert one closed research cluster "
                "into one or more atomic conceptual Method cards, not publication prose. Return "
                "only JSON matching "
                "the schema. Preserve every condition, qualifier, number, formula, input and output. "
                "Split a source statement whenever it contains distinct representation, "
                "normalization, model architecture, training objective, inference, deployment, "
                "or limitation concepts; each proposal must express exactly one concept that a "
                "Writer can cover in one coherent sentence group. Return at most six non-overlapping "
                "cards for this cluster; combine source operations only when they form one coherent "
                "mechanism, and never emit alternative paraphrases of the same source operation. "
                "Keep transformation to one short scientific clause. Put meaningful operands in "
                "inputs and the produced quantity in outputs; do not hide them in transformation. "
                "Never add purpose, rationale, downstream use, author intention, benefits, pruning "
                "motivation, implementation narration, or binding-harness commentary to a repository "
                "card. Put raw code identifiers only in implementation_binding_terms. "
                "Do not collapse a multi-part "
                "author story into a generic overview card. When convenient, copy the exact source "
                "statement(s) used by each card into source_statement_fragments. If one card combines "
                "composition, normalization, a dimension, or another distinct semantic field, include "
                "every source statement needed to establish those fields; otherwise leave the array "
                "empty and the binding harness will choose the closest statement inside this closed "
                "cluster. These bindings determine which numbers and formulas belong to that card. "
                "Do not copy uncertainty "
                "notes as method content. "
                "Use reader-facing scientific concepts for reader_subject, transformation, inputs, "
                "outputs and paper_terms. Put raw source symbols only in implementation_binding_terms. "
                "author_term_hints may guide paper terminology and story organization only; they do "
                "not authorize implementation behavior, support status, conditions, numbers, formulas, "
                "benefits, novelty, or performance. Every repository transformation still comes only "
                "from the supplied evidence claims/facts/relations. "
                "code_term_hints are lexical renderings of exact source identifiers. Use them to "
                "recover reader-facing component names, but do not treat them as extra facts; every "
                "resulting component and operation must still be supported by source_statements. "
                "For a concatenation or stacking concept, populate inputs with the distinct "
                "reader-facing components established by the selected source statement; do not "
                "return an empty inputs array. For normalization, prefer the normalized scientific "
                "quantity and meaningful percentile or formula terms over a raw function name. "
                "Do not select or copy cluster, claim, fact, relation, span, or digest IDs. Those "
                "fields do not exist in your response schema. The binding harness derives every "
                "sidecar identity from your exact source_statement_fragments. For author_intent, "
                "describe the intended contribution without claiming it is implemented. Preserve "
                "every explicit dimension, named component list, condition, formula, input, and "
                "output from the author statement in the appropriate semantic fields. A dimension "
                "describes a representation (for example, a dimensional descriptor); it is never "
                "a count of stages, targets, operations, or transformations. Do not reduce a "
                "multi-part author statement to a generic label such as feature extraction or "
                "method operation. Do not invent rationale, benefit, performance, novelty or mathematics."
        )
        # Give the model a compact conceptual envelope, not the compiler
        # object. Opaque obligation/claim/fact/span IDs, graph edges, section
        # IDs, digests, and repeated raw operand arrays remain in the binding
        # sidecar. Keeping them in this prompt made the local model spend its
        # output budget explaining or copying harness state instead of
        # producing concise method concepts.
        architect_payload: dict[str, Any] = {
            "origin": cluster.origin,
            "evidence_lane": cluster.evidence_lane,
            "source_statements": list(cluster.source_statements),
            "source_semantics": {
                "subjects": list(cluster.subjects),
                "predicates": list(cluster.predicates),
                "conditions": list(cluster.conditions),
                "required_qualifiers": list(cluster.required_qualifiers),
            },
        }
        if cluster.origin == "repository_evidence":
            # Full author prose is organization context, not repository
            # evidence. Reader terminology comes only from exact identifiers
            # in this repository evidence cluster.
            architect_payload["code_term_hints"] = _code_term_hints(cluster)
        else:
            architect_payload["author_term_hints"] = list(
                cluster.author_term_hints
            )
            architect_payload["uncertainty_notes"] = list(
                cluster.uncertainty_notes
            )
        request = LLMRequest(
            prompt_template_id="method_proposition_architect_v1",
            prompt=base_prompt,
            input_payload={
                **architect_payload,
                **({
                    "repair": {
                        "previous_error": _repair_payload(validation_error),
                        "instruction": (
                            "Return a complete schema-valid batch. Preserve every card in "
                            "valid_cards_to_preserve without semantic changes. Correct each "
                            "failed_cards item using its previous_card and reason. For "
                            "concept_fields_missing on a concatenation/stacking card, fill inputs "
                            "with the distinct reader-facing components in its selected source and "
                            "put the produced quantity in outputs. For concept_not_atomic, replace "
                            "the long or purposive transformation with one evidence-only scientific "
                            "clause; remove author intent, downstream use, motivation, implementation "
                            "narration, and raw identifiers. "
                            "Add concise cards for every missing_source_statements item, unless a "
                            "corrected card explicitly covers it. When a missing statement is the "
                            "formula, return, or typed operation for a mechanism already represented "
                            "by a valid card, extend that one card's source fragments and semantic "
                            "fields instead of adding a paraphrase card. Use only this cluster's source "
                            "statements, conditions, numbers, formulas, and authority surface. "
                            "Do not emit any ID fields; the harness owns binding identities. "
                            "For author_semantics_missing, preserve every explicit dimension and "
                            "named parenthetical component in reader_subject, transformation, "
                            "inputs, outputs, or paper_terms; do not hide them in a generic label. "
                            + (
                                "The previous response hit its output limit. Return no more than "
                                "six non-overlapping cards; use short scientific phrases in each "
                                "field and emit no explanations outside the JSON object."
                                if "finish_reason=length" in validation_error
                                else ""
                            )
                        ),
                    }
                } if validation_error else {}),
            },
            schema_name=MethodPropositionProposalBatchV1.__name__,
            response_json_schema=json_schema_for(_ArchitectSemanticBatchV1),
        )
        response = caller(config, request)
        trace = {
            "role": METHOD_PROPOSITION_ARCHITECT,
            "cluster_id": cluster.cluster_id,
            "repair_error": validation_error,
            "effective_config": {
                "provider": getattr(config.provider, "value", str(config.provider)),
                "model": config.model,
                "temperature": config.temperature,
                "top_p": config.top_p,
                "top_k": config.top_k,
                "seed": config.seed,
                "max_output_tokens": config.max_output_tokens,
            },
            "response_hash": response.response_hash,
            "finish_reason": response.finish_reason,
            "blocked_reason": response.blocked_reason,
        }
        proposal_traces.append(trace)
        if response.blocked_reason:
            raise ValueError(f"proposition_architect_blocked:{response.blocked_reason}")
        semantic_batch, recovery, error = try_parse_structured_response_with_trace(
            response.text, _ArchitectSemanticBatchV1
        )
        trace["representation_recovery"] = recovery.model_dump(mode="json")
        if semantic_batch is None:
            trace["response_preview"] = response.text[:4000]
            raise ValueError(
                "proposition_architect_schema_failed:"
                f"finish_reason={response.finish_reason or 'unknown'}:"
                f"{error or 'unknown'}"
            )
        # Convert the semantic response to the internal binding contract.
        # IDs are born empty here and are bound from source fragments later;
        # the model never sees or transcribes opaque identities.
        parsed = MethodPropositionProposalBatchV1(
            cluster_id=cluster.cluster_id,
            proposals=tuple(
                MethodPropositionProposalV1(
                    cluster_id=cluster.cluster_id,
                    **proposal.model_dump(mode="python"),
                )
                for proposal in semantic_batch.proposals
            ),
        )
        parsed = parsed.model_copy(update={
            "proposals": _dedupe_proposals(cluster, tuple(
                _bind_source_fragments(cluster, proposal)
                for proposal in parsed.proposals
            ))
        })
        trace["proposal_count"] = len(parsed.proposals)
        trace["proposals"] = [
            proposal.model_dump(mode="json") for proposal in parsed.proposals
        ]
        return parsed

    propose.proposal_traces = proposal_traces  # type: ignore[attr-defined]
    return propose
