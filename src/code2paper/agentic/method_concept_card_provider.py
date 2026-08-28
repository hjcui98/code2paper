"""Stage 2 low-temperature LLM provider for Method Concept Cards.

The model receives only the bounded, closed cluster envelope
(``ConceptCardCandidateClusterV1``) and returns 1-3 phrase cards whose
fields are all bounded phrases.  The compiler owns every authority check
(fragment closure, authority lane, phrase budgets, digests); this provider
only builds the request and parses the structured response with bounded
representation repair.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from code2paper.agentic.method_concept_card_models import (
    ConceptCardCandidateClusterV1,
    MethodConceptCardProposalBatchV1,
    MethodConceptCardProposalV1,
)
from code2paper.llm.client import LLMClient, LLMRequest, LLMResponse
from code2paper.llm.response_schemas import (
    json_schema_for,
    try_parse_structured_response_with_trace,
)
from code2paper.llm.role_config import METHOD_PROPOSITION_ARCHITECT, apply_role_config
from code2paper.schemas import LLMConfig


class _ConceptCardResponseV1:
    """Semantic-only response surface; binding identity stays harness-side."""

    model_config = {"extra": "ignore", "frozen": True}

    def __init__(self, **kwargs: Any) -> None:
        proposals = kwargs.get("proposals") or []
        self.proposals = tuple(
            MethodConceptCardProposalV1.model_validate(item)
            if isinstance(item, dict)
            else item
            for item in proposals
        )


def _closed_fragment_terms(cluster: ConceptCardCandidateClusterV1) -> list[str]:
    """Expose bounded fragments and their closed ordinal ids to the model.

    The model may reference ``frag-1..frag-N``; the harness maps ordinals
    to exact spans/fragments and rejects any ref outside this set.
    """

    return [
        f"frag-{index}: {fragment}"
        for index, fragment in enumerate(cluster.source_fragments, start=1)
    ]


_IDENTIFIER_WORDS = {
    "avg": "average",
    "dists": "distances",
    "dist": "distance",
    "volumn": "volume",
    "rgb": "RGB color",
    "sh": "spherical-harmonic",
    "opacities": "opacity",
    "scales": "scale statistics",
    "prune_features": "pruning descriptor",
    "input_features": "feature descriptor",
    "local_z": "local z-score",
    "global_z": "global z-score",
    "sorted_scales": "sorted per-axis scales",
    "knn": "k-nearest-neighbour",
}
_IDENTIFIER_NOISE = frozenset({"f", "p", "self", "torch"})


def _humanize_code_identifier(value: str) -> str:
    """Return a reader-term hint derived only from an exact code token.

    Lexical projection only: the evidence judge still evaluates the card
    against the exact source fragments.
    """

    import re

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


def _code_term_hints(cluster: ConceptCardCandidateClusterV1) -> list[dict[str, str]]:
    """Expose exact identifiers as terminology aids, never as new evidence."""

    raw_terms: list[str] = []
    for fragment in cluster.source_fragments:
        for token in re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?",
            fragment,
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
    return hints


def build_concept_card_architect(
    llm_config: LLMConfig,
    *,
    llm_caller: Callable[[LLMConfig, LLMRequest], LLMResponse] | None = None,
):
    """Return a bounded concept-card proposer for Stage 2 clusters."""

    config = apply_role_config(llm_config, METHOD_PROPOSITION_ARCHITECT)
    if llm_caller is None:
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
        cluster: ConceptCardCandidateClusterV1,
        validation_error: str = "",
    ) -> MethodConceptCardProposalBatchV1:
        schema = json_schema_for(MethodConceptCardProposalBatchV1)
        if cluster.origin == "repository":
            # Repository cards MUST bind exact closed fragments.  The
            # proposal model defaults the field to an empty tuple, so the
            # vanilla schema would let the model omit it and only the
            # compiler would reject it after one repair round.  Force the
            # field in the guided-decoding schema itself: the model cannot
            # produce a repository card without frag refs.
            schema = _require_fragment_refs(schema)
        elif cluster.origin == "author_intent":
            # Author-intent cards must carry a visible caveat; the harness
            # refuses to fabricate paper language for them.  Force at least
            # one of candidate_caveat / missing_parts in the schema so the
            # model cannot omit the caveat obligation.
            schema = _require_caveat_fields(schema)
        prompt = _concept_architect_prompt(cluster, validation_error)
        request = LLMRequest(
            prompt_template_id="agentic_method_concept_card_architect_v1",
            prompt=prompt,
            input_payload={
                "origin": cluster.origin,
                "cluster_id": cluster.cluster_id,
                "research_question": cluster.research_question,
                "story_node": cluster.story_node,
                "fragments": _closed_fragment_terms(cluster),
            },
            schema_name="MethodConceptCardProposalBatchV1",
            response_json_schema=schema,
        )
        response = caller(config, request)
        if response.blocked_reason:
            raise ValueError(f"concept_architect_blocked:{response.blocked_reason}")
        parsed, recovery, parse_error = try_parse_structured_response_with_trace(
            response.text, MethodConceptCardProposalBatchV1
        )
        if parsed is None:
            raise ValueError(parse_error or "concept architect schema failed")
        proposal_traces.append({
            "cluster_id": cluster.cluster_id,
            "recovery_applied": recovery.applied,
            "recovery_operations": list(recovery.operations),
            "parsed_payload_digest": recovery.parsed_payload_digest,
        })
        return parsed

    propose.proposal_traces = proposal_traces  # type: ignore[attr-defined]
    return propose


def _require_fragment_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline the card $defs and require evidence_fragment_refs for repository cards.

    The provider keeps the schema closed (``additionalProperties: false``)
    and only strengthens the guided-decoding contract for the repository
    lane; the compiler still independently validates fragment closure.
    """

    import copy

    schema = copy.deepcopy(schema)
    defs = schema.get("$defs", {})
    card_def = defs.get("MethodConceptCardProposalV1")
    if card_def is None:
        return schema
    required = list(card_def.get("required", []))
    if "evidence_fragment_refs" not in required:
        required.append("evidence_fragment_refs")
    card_def["required"] = required
    # minItems=1 guarantees at least one closed fragment reference.
    refs_schema = card_def.get("properties", {}).get("evidence_fragment_refs", {})
    refs_schema["minItems"] = 1
    return schema


def _require_caveat_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Require candidate_caveat or missing_parts for author-intent cards.

    JSON Schema cannot express ``oneOf`` over array-length constraints, so
    the schema requires ``candidate_caveat`` to be present and non-empty;
    the compiler additionally accepts a card whose ``missing_parts`` is
    non-empty (caveat may be empty then).  The model cannot emit an
    author-intent card that silently claims nothing about its status.
    """

    import copy

    schema = copy.deepcopy(schema)
    defs = schema.get("$defs", {})
    card_def = defs.get("MethodConceptCardProposalV1")
    if card_def is None:
        return schema
    required = list(card_def.get("required", []))
    if "candidate_caveat" not in required:
        required.append("candidate_caveat")
    card_def["required"] = required
    caveat_schema = card_def.get("properties", {}).get("candidate_caveat", {})
    caveat_schema["minLength"] = 1
    return schema


def _concept_architect_prompt(
    cluster: ConceptCardCandidateClusterV1,
    validation_error: str,
) -> str:
    instructions = (
        "You are the Method Concept Architect. Convert one closed research cluster into "
        "1-3 atomic Method concept cards — NOT publication prose and NOT a code trace. "
        "Every field must be a short phrase; never write sentences or paragraphs.\n\n"
        "Rules:\n"
        "- method_subject: the reader-facing method concept (no raw function names, no "
        "dotted identifiers, no underscore tokens).\n"
        "- operation: the single mechanism in one short clause.\n"
        "- inputs/outputs/conditions: bounded reader-facing phrases; never raw code "
        "identifiers such as ``self.prune_features`` or ``input_features`` — use the "
        "reader_term_hint when supplied (e.g. ``normalized pruning descriptor``).\n"
        "- numeric_constraints/formula_constraints: only numbers/formulas actually present "
        "in the closed fragments (e.g. 15, 0.01, 0.99, log, z-score, min-max).\n"
        "- evidence_fragment_refs: for REPOSITORY cards this field is REQUIRED and must "
        "contain at least one id from the closed frag-N set. Choose the exact fragments "
        "that establish the card's operation/inputs/outputs. Never leave it empty and "
        "never invent ids.\n"
        "- known_parts: what the fragments establish; missing_parts: what they do not.\n"
        "- repository cards: never add author purpose, downstream pruning, benefits, or "
        "harness terminology; never add a caveat.\n"
        "- author_intent cards: describe the intended semantics, ALWAYS fill candidate_caveat "
        "(or missing_parts) with the author-attested status — a card with neither is rejected "
        "by the harness. Never claim repository implementation.\n"
        "- One card may cover several genuinely related low-level operations of the same "
        "method (e.g. descriptor composition and its normalization). Do NOT emit one card "
        "per low-level operation.\n"
        "- Do not copy fragment ids or span ids other than the closed frag-N refs.\n"
        "- story_node may be copied when supplied.\n"
        "- Return only JSON matching the schema."
    )
    envelope = {
        "origin": cluster.origin,
        "research_question": cluster.research_question,
        "story_node": cluster.story_node,
        "closed_fragments": _closed_fragment_terms(cluster),
        "author_term_hints": list(cluster.author_term_hints),
        "uncertainty_notes": list(cluster.uncertainty_notes),
        "low_level_predicates": list(cluster.low_level_predicates),
        "low_level_fact_count": cluster.low_level_fact_count,
    }
    if cluster.origin == "repository":
        # Reader terminology comes only from exact identifiers in this
        # repository evidence cluster; author prose is NOT repository
        # evidence and must not leak into repository cards.
        envelope["code_term_hints"] = _code_term_hints(cluster)
    if validation_error:
        envelope["validation_error"] = validation_error
    return instructions + "\n\nCluster envelope:\n" + json.dumps(
        envelope, ensure_ascii=False, indent=2
    )
