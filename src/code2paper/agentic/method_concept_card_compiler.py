"""Stage 2 compiler: bounded source fragments -> Method Concept Cards.

Implements the pause-diagnosis Stage 2 plan
(``autonomous_method_agent_pause_diagnosis_and_handoff_20260813.md``):

1. Build *closed* candidate clusters whose only model-visible content is
   bounded source fragments (exact claim/statement text and span ids), plus
   obligation/story hints.  No raw fact/claim JSON and no internal IDs are
   exposed to the model.
2. Invoke the (optional, low-temperature) Concept Architect to propose
   1-3 phrase cards per cluster.  Every field is a bounded phrase; there is
   no free-form ``transformation`` paragraph field.
3. Validate proposals against the closed cluster: fragment refs must come
   from the supplied fragment set, phrases must be bounded, repository
   cards must never carry author purpose, author-intent cards can never
   enter verified output.
4. Bind each semantic field to the exact fragments that support it
   (field -> refs), never to the whole cluster.
5. Emit a digest-covered ``MethodConceptCardSetV1``.

The compiler is deterministic except for the optional Architect/Judge LLM
calls; all authority checks, phrase budgets, closed-set rules and digests
run in harness code.

Coverage rule: a card may cover several genuinely related low-level facts,
but there is no quota requiring every ``calls/reduces/sorts`` predicate to
become a card.  Unused low-level facts stay in the evidence ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Callable, Iterable, Protocol

from code2paper.agentic.method_concept_card_models import (
    ConceptCardBindingV1,
    ConceptCardCandidateClusterV1,
    ConceptCardEvidenceVerdictV1,
    ConceptCardFieldJudgmentV1,
    ConceptCardGapV1,
    MethodConceptCardProposalBatchV1,
    MethodConceptCardProposalV1,
    MethodConceptCardSetV1,
    MethodConceptCardV1,
)


def _stable_id(prefix: str, *parts: str) -> str:
    material = "|".join(str(part) for part in parts if str(part))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


class ConceptCardArchitect(Protocol):
    """Low-temperature LLM (or deterministic stub) proposing concept cards."""

    def __call__(
        self,
        cluster: ConceptCardCandidateClusterV1,
        validation_error: str = "",
    ) -> MethodConceptCardProposalBatchV1 | MethodConceptCardProposalV1:
        ...


class ConceptCardEvidenceJudge(Protocol):
    """Per-field evidence judge for concept cards (Stage 3 interface)."""

    def __call__(
        self,
        cards: tuple[MethodConceptCardV1, ...],
        cluster: ConceptCardCandidateClusterV1,
    ) -> tuple[ConceptCardEvidenceVerdictV1, ...]:
        ...


# ---------------------------------------------------------------------------
# Cluster construction
# ---------------------------------------------------------------------------


def _claim_statement(claim: Any) -> str:
    return str(getattr(claim, "canonical_text", "") or "").strip()


def _claim_method_scope(claim: Any) -> str:
    """Extract the executable method scope from a claim's canonical text.

    Claims compiled from repository behavior read like
    ``GaussianModel.get_prune_input_f15 concatenates ...``; the leading
    dotted identifier is the method whose operations belong to one concept.
    Reader-language claims without a dotted identifier return an empty
    scope, which keeps all claims of one obligation in the same cluster.
    """

    statement = _claim_statement(claim)
    match = re.match(
        r"\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)",
        statement,
    )
    if match is None:
        return ""
    return match.group(1)


def _connected_claim_components(group: list[Any]) -> list[list[Any]]:
    """Split claims into components connected by span/fact/relation identity.

    Used only for claims without a method scope, where forcing every claim
    of an obligation into one cluster could merge genuinely unrelated
    statements.
    """

    components: list[list[Any]] = []
    for claim in group:
        claim_spans = set(_claim_span_ids(claim))
        claim_facts = set(str(item) for item in getattr(claim, "fact_ids", ()) or ())
        claim_relations = set(
            str(item) for item in getattr(claim, "relation_evidence_ids", ()) or ()
        )
        placed = False
        for component in components:
            component_spans: set[str] = set()
            component_facts: set[str] = set()
            component_relations: set[str] = set()
            for item in component:
                component_spans.update(_claim_span_ids(item))
                component_facts.update(
                    str(x) for x in getattr(item, "fact_ids", ()) or ()
                )
                component_relations.update(
                    str(x) for x in getattr(item, "relation_evidence_ids", ()) or ()
                )
            if (
                claim_spans & component_spans
                or claim_facts & component_facts
                or claim_relations & component_relations
            ):
                component.append(claim)
                placed = True
                break
        if not placed:
            components.append([claim])
    return components


def _claim_span_ids(claim: Any) -> tuple[str, ...]:
    ids = tuple(getattr(claim, "direct_evidence_ids", ()) or ())
    return tuple(str(item) for item in ids if str(item).strip())


def build_concept_candidate_clusters(
    *,
    claims: Any,
    story_spine: Iterable[Any] = (),
    completeness: Any | None = None,
) -> tuple[ConceptCardCandidateClusterV1, ...]:
    """Build closed concept clusters from atomic claims.

    ``claims`` is the V3 ``AtomicClaimSetV3``.  Only ``supported`` and
    ``partial`` claims enter clusters.  Author-intent rows from the
    completeness matrix (rows that are not fully repository-supported) are
    kept as separate ``author_intent`` clusters so the two authorities are
    never mixed in one generation response.
    """

    story_by_obligation: dict[str, list[Any]] = defaultdict(list)
    for node in story_spine:
        for obligation_id in getattr(node, "linked_obligation_ids", ()) or ():
            story_by_obligation[str(obligation_id)].append(node)

    # Group by (obligation, method scope) so the low-level operations of one
    # executable method (concat, sort, prod, normalize) form ONE concept
    # cluster instead of one cluster per predicate.  The Stage 2 plan
    # explicitly forbids a per-predicate card quota (root cause G): a
    # feature-descriptor card covers every genuinely related operation of
    # its method; unused low-level facts stay in the evidence ledger.
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for claim in getattr(claims, "claims", ()) or ():
        if getattr(claim, "status", "") not in {"supported", "partial"}:
            continue
        keys = getattr(claim, "covers_obligation_ids", None) or [
            f"claim:{getattr(claim, 'claim_id', '')}"
        ]
        scope = _claim_method_scope(claim)
        for key in keys:
            grouped[(str(key), scope)].append(claim)

    clusters: list[ConceptCardCandidateClusterV1] = []
    for (obligation_id, scope), obligation_group in sorted(grouped.items()):
        # One (obligation, method scope) is ONE concept cluster: the
        # low-level operations of the same executable method (concat, sort,
        # prod, normalize, z-score) describe one mechanism and must not be
        # split into one cluster per predicate (root cause G).  Claims with
        # an empty scope (reader-language claims without a dotted method
        # identifier) fall back to connectivity-based splitting so unrelated
        # statements of one obligation are not force-merged.
        if scope:
            components = [obligation_group]
        else:
            components = _connected_claim_components(obligation_group)

        for component in components:
            span_ids = tuple(dict.fromkeys(
                span
                for claim in component
                for span in _claim_span_ids(claim)
            ))
            source_fragments = tuple(dict.fromkeys(
                statement
                for claim in component
                if (statement := _claim_statement(claim))
            ))
            predicates: list[str] = []
            for claim in component:
                for target in getattr(claim, "typed_behavior_targets", ()) or ():
                    for predicate in getattr(target, "desired_predicates", ()) or ():
                        if str(predicate).strip() and str(predicate) not in predicates:
                            predicates.append(str(predicate))
            is_partial = any(
                getattr(claim, "status", "") == "partial" for claim in component
            )
            nodes = story_by_obligation.get(obligation_id, ())
            story_node = (
                str(getattr(nodes[0], "title", "") or "").strip()
                if nodes else ""
            )
            author_hints = tuple(dict.fromkeys(
                value
                for node in nodes
                for value in (getattr(node, "title", ""), getattr(node, "author_statement", ""))
                if str(value).strip()
            ))
            clusters.append(ConceptCardCandidateClusterV1(
                cluster_id=_stable_id(
                    "CC",
                    obligation_id,
                    *[getattr(claim, "claim_id", "") for claim in component],
                ),
                origin="repository",
                obligation_ids=(
                    () if obligation_id.startswith("claim:")
                    else (obligation_id,)
                ),
                research_question=str(
                    getattr(claims, "research_question", "") or ""
                ),
                source_fragments=source_fragments,
                source_span_ids=span_ids,
                low_level_fact_count=len(component),
                low_level_predicates=tuple(predicates),
                story_node=story_node,
                author_term_hints=author_hints,
                required_qualifiers=tuple(dict.fromkeys(
                    qualifier
                    for claim in component
                    for qualifier in getattr(claim, "required_qualifiers", ()) or ()
                )),
                uncertainty_notes=(
                    ("partially supported by repository",)
                    if is_partial else ()
                ),
            ))

    if completeness is not None:
        covered = {oid for cluster in clusters for oid in cluster.obligation_ids}
        for row in getattr(completeness, "items", ()) or ():
            if getattr(row, "status", "") == "out_of_scope":
                continue
            obligation_id = str(getattr(row, "obligation_id", "") or "")
            if (
                obligation_id in covered
                and getattr(row, "status", "") == "supported_by_repository"
            ):
                continue
            statement = str(getattr(row, "statement", "") or "").strip()
            if not statement:
                continue
            nodes = story_by_obligation.get(obligation_id, ())
            clusters.append(ConceptCardCandidateClusterV1(
                cluster_id=_stable_id("CC", obligation_id, statement),
                origin="author_intent",
                obligation_ids=(obligation_id,),
                research_question=str(
                    getattr(claims, "research_question", "") or ""
                ),
                source_fragments=(statement,),
                story_node=(
                    str(getattr(nodes[0], "title", "") or "").strip()
                    if nodes else ""
                ),
                author_term_hints=tuple(dict.fromkeys(
                    value
                    for node in nodes
                    for value in (getattr(node, "title", ""), getattr(node, "author_statement", ""))
                    if str(value).strip()
                )),
                uncertainty_notes=(
                    (str(getattr(row, "reason", "") or "").strip(),)
                    if str(getattr(row, "reason", "") or "").strip() else ()
                ),
            ))
    return tuple(clusters)


# ---------------------------------------------------------------------------
# Proposal validation and binding
# ---------------------------------------------------------------------------


def _validate_proposal(
    cluster: ConceptCardCandidateClusterV1,
    proposal: MethodConceptCardProposalV1,
) -> tuple[list[str], list[str]]:
    """Validate one card against its closed cluster.

    Returns ``(failures, missing_source_statements)``.  Failures are
    semantic/authority violations that must be repaired by the owner;
    missing statements are only diagnostics.
    """

    failures: list[str] = []
    if proposal.cluster_id != cluster.cluster_id:
        failures.append("cluster_id_mismatch")
    if cluster.origin == "repository" and not proposal.evidence_fragment_refs:
        failures.append("repository_card_without_fragments")
    if cluster.origin == "repository" and proposal.candidate_caveat.strip():
        failures.append("repository_card_with_caveat")
    unknown_refs = [
        ref for ref in proposal.evidence_fragment_refs
        if ref not in cluster.source_span_ids
        and ref not in {
            f"frag-{index}"
            for index in range(1, len(cluster.source_fragments) + 1)
        }
    ]
    if unknown_refs:
        failures.append(f"fragment_not_closed:{','.join(unknown_refs[:3])}")
    # Author purpose must never enter a repository card's operation/inputs.
    if cluster.origin == "repository":
        surface = " ".join((
            proposal.method_subject,
            proposal.operation,
            *proposal.inputs,
            *proposal.outputs,
            *proposal.conditions,
            *proposal.numeric_constraints,
            *proposal.formula_constraints,
        )).casefold()
        for marker in ("author intends", "author wants", "we aim", "our goal",
                       "for pruning", "to enable pruning", "binding harness",
                       "downstream pruning", "paper contribution"):
            if marker in surface:
                failures.append(f"authority_expansion:{marker}")
                break
    return failures, []


_BINDING_STOP_WORDS = frozenset({
    "a", "an", "and", "as", "by", "for", "from", "in", "into", "is",
    "of", "on", "or", "per", "the", "to", "using", "with", "its", "their",
})

# Lexical normalization for binding overlap: map code tokens and inflected
# forms to a small reader vocabulary.  This is binding-precision ONLY —
# the independent judge still decides per-field entailment.
_BINDING_TOKEN_ALIASES = {
    "prod": "product", "produces": "product", "product": "product",
    "scales": "scale", "scaling": "scale", "scale": "scale",
    "sorted": "sort", "sorts": "sort", "sort": "sort",
    "normalizes": "normalize", "normalized": "normalize",
    "concatenates": "concat", "concatenation": "concat", "cat": "concat",
    "computes": "compute", "computed": "compute",
    "returns": "return", "returned": "return",
    "standardizes": "standardize", "standardized": "standardize",
    "opacities": "opacity", "opacity": "opacity",
    "volumes": "volume", "volume": "volume",
    "anisotropy": "anisotropy",
    "percentile": "percentile",
    "zscore": "z-score", "z_score": "z-score", "zscore_tensor": "z-score",
    "rescales": "normalize", "rescale": "normalize",
    "bounds": "percentile", "bound": "percentile",
    "clipped": "clip", "clip": "clip",
    "lower": "bound", "upper": "bound",
}


def _binding_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", value.casefold().replace("_", " ")):
        if len(token) <= 1 or token in _BINDING_STOP_WORDS:
            continue
        tokens.add(_BINDING_TOKEN_ALIASES.get(token, token))
    return tokens


def _field_fragment_overlap(field_text: str, fragment: str) -> int:
    """Number of content tokens a field shares with a fragment.

    Pure lexical overlap used ONLY to pick exact binding refs inside the
    already closed cluster.  It never authorizes evidence: the independent
    judge decides entailment per field.
    """

    field_tokens = _binding_tokens(field_text)
    fragment_tokens = _binding_tokens(fragment)
    return len(field_tokens & fragment_tokens)


def _bind_concept_card(
    cluster: ConceptCardCandidateClusterV1,
    proposal: MethodConceptCardProposalV1,
    *,
    concept_key: str = "",
) -> ConceptCardBindingV1:
    """Bind each semantic field to its exact source fragments (Stage 3 rule 5).

    - Default binding is model-selected precision: only fragments the model
      referenced (or, for author-intent clusters, the author statement
      itself) are candidates.
    - Within that closed candidate set, each field binds only the fragments
      whose content lexically overlaps the field's text (field -> exact
      refs), never the whole cluster.
    - Sibling evidence is NEVER auto-expanded merely because it shares a
      mechanism label or a common token with another field.
    """

    if cluster.origin == "author_intent":
        field_bindings = (
            ("method_subject", cluster.source_fragments),
            ("operation", cluster.source_fragments),
        )
    else:
        candidate_refs = tuple(
            ref for ref in proposal.evidence_fragment_refs
            if ref in cluster.source_span_ids or ref.startswith("frag-")
        )
        if not candidate_refs:
            candidate_refs = tuple(
                f"frag-{index}"
                for index in range(1, len(cluster.source_fragments) + 1)
            )
        fragments_by_ref = {
            f"frag-{index}": fragment
            for index, fragment in enumerate(cluster.source_fragments, start=1)
        }
        fragments_by_ref.update(
            {span_id: fragment for span_id, fragment in zip(
                cluster.source_span_ids,
                cluster.source_fragments,
                strict=False,
            )}
        )
        field_bindings: list[tuple[str, tuple[str, ...]]] = []
        for field_name, field_text in (
            ("method_subject", proposal.method_subject),
            ("operation", proposal.operation),
        ):
            refs = tuple(
                ref for ref in candidate_refs
                if _field_fragment_overlap(
                    field_text, fragments_by_ref.get(ref, "")
                ) > 0
            )
            if refs:
                field_bindings.append((field_name, refs))
        for field_name, values in (
            ("inputs", proposal.inputs),
            ("outputs", proposal.outputs),
            ("conditions", proposal.conditions),
            ("numeric_constraints", proposal.numeric_constraints),
            ("formula_constraints", proposal.formula_constraints),
        ):
            refs = tuple(dict.fromkeys(
                ref
                for value in values
                for ref in candidate_refs
                if _field_fragment_overlap(
                    value, fragments_by_ref.get(ref, "")
                ) > 0
            ))
            if refs:
                field_bindings.append((field_name, refs))
        if not field_bindings:
            field_bindings.append(("operation", candidate_refs))
    return ConceptCardBindingV1(
        concept_key=concept_key,
        field_bindings=tuple(field_bindings),
        source_obligation_ids=cluster.obligation_ids,
        source_span_ids=cluster.source_span_ids,
    )


_PURPOSE_MARKERS = (
    "for pruning", "to enable pruning", "as a predictor input",
    "for scoring", "to score", "downstream", "to predict",
    "prior to prediction", "for the predictor",
)
_CALLER_EVIDENCE_MARKERS = (
    "calls", "caller", "invokes", "invoked by", "data flow",
    "data_flow", "feeds", "is consumed by", "passed to",
    "predictor", "consumes", "scored by", "score path",
)


def _enforce_purpose_evidence_rule(
    verdict: ConceptCardEvidenceVerdictV1,
    cluster: ConceptCardCandidateClusterV1,
) -> ConceptCardEvidenceVerdictV1:
    """Stage 3 rule: purpose/downstream fields need caller/data-flow evidence.

    A field judged ``entailed`` whose value carries purpose language
    (``for pruning``, ``to enable``, ``as a predictor input``) is only
    acceptable when at least one supporting fragment contains a
    caller/data-flow witness.  Without one, the judgment is downgraded to
    ``partial`` (and the overall verdict recomputed), so author motivation
    can never be silently upgraded to repository fact.
    """

    fragments_by_ref = {
        f"frag-{index}": fragment
        for index, fragment in enumerate(cluster.source_fragments, start=1)
    }
    fragments_by_ref.update(dict(zip(
        cluster.source_span_ids,
        cluster.source_fragments,
        strict=False,
    )))

    changed = False
    normalized_judgments = list(verdict.field_judgments)
    for index, item in enumerate(normalized_judgments):
        if item.verdict != "entailed":
            continue
        value = item.proposed_value.casefold()
        if not any(marker in value for marker in _PURPOSE_MARKERS):
            continue
        fragment_surface = " ".join(
            fragments_by_ref.get(ref, "") for ref in item.evidence_fragment_refs
        ).casefold()
        if any(marker in fragment_surface for marker in _CALLER_EVIDENCE_MARKERS):
            continue
        normalized_judgments[index] = ConceptCardFieldJudgmentV1(
            field_name=item.field_name,
            proposed_value=item.proposed_value,
            verdict="partial",
            evidence_fragment_refs=item.evidence_fragment_refs,
            rationale=(
                item.rationale
                + " [purpose downgraded: no caller/data-flow evidence]"
            ).strip(),
        )
        changed = True

    if not changed:
        return verdict

    overall = "entailed"
    for item in normalized_judgments:
        if item.verdict != "entailed":
            overall = item.verdict if overall == "entailed" else (
                "partial" if overall == "entailed" or overall == "partial"
                else overall
            )
    return ConceptCardEvidenceVerdictV1(
        concept_key=verdict.concept_key,
        field_judgments=tuple(normalized_judgments),
        overall_verdict=(
            "partial" if overall == "entailed" else overall
        ),
        rationale=(
            verdict.rationale
            + " [purpose fields downgraded without caller/data-flow evidence]"
        ).strip(),
    )


def _card_identity_key(proposal: MethodConceptCardProposalV1) -> tuple[str, ...]:
    return (
        proposal.method_subject.casefold(),
        proposal.operation.casefold(),
        tuple(item.casefold() for item in proposal.inputs),
        tuple(item.casefold() for item in proposal.outputs),
    )


def _dedupe_cards(
    cluster: ConceptCardCandidateClusterV1,
    proposals: tuple[MethodConceptCardProposalV1, ...],
) -> tuple[MethodConceptCardProposalV1, ...]:
    unique: list[MethodConceptCardProposalV1] = []
    seen: set[tuple[str, ...]] = set()
    for proposal in proposals:
        key = _card_identity_key(proposal)
        if key in seen:
            continue
        seen.add(key)
        unique.append(proposal)
    return tuple(unique)


def _invoke_concept_architect(
    architect: ConceptCardArchitect,
    cluster: ConceptCardCandidateClusterV1,
    validation_error: str,
) -> MethodConceptCardProposalBatchV1 | MethodConceptCardProposalV1:
    """Call repair-aware owners while preserving one-argument fixtures."""

    import inspect

    try:
        parameters = inspect.signature(architect).parameters.values()
        accepts_feedback = any(
            parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
            for parameter in parameters
        ) or len(tuple(parameters)) >= 2
    except (TypeError, ValueError):
        accepts_feedback = False
    if accepts_feedback:
        return architect(cluster, validation_error)
    return architect(cluster)


# ---------------------------------------------------------------------------
# Compiler entry
# ---------------------------------------------------------------------------


def _card_realized_story_node_ids(
    *,
    cluster: ConceptCardCandidateClusterV1,
    binding: ConceptCardBindingV1,
    story_spine: Iterable[Any],
    claims: Any,
) -> tuple[str, ...]:
    """Exact claim/span overlap with bound story nodes; never obligation inference."""

    title = str(getattr(cluster, "story_node", "") or "").strip()
    if not title:
        return ()
    nodes = [
        node for node in story_spine
        if str(getattr(node, "story_node_id", "") or "").strip() == title
        or str(getattr(node, "title", "") or "").strip() == title
    ]
    if not nodes:
        return ()
    linked_claim_ids = {
        str(claim_id)
        for node in nodes
        for claim_id in (getattr(node, "linked_claim_ids", ()) or ())
        if str(claim_id).strip()
    }
    if not linked_claim_ids:
        return ()
    bound_spans = {
        str(span) for span in (getattr(binding, "source_span_ids", ()) or ())
        if str(span).strip()
    }
    cluster_spans = {
        str(span) for span in (getattr(cluster, "source_span_ids", ()) or ())
        if str(span).strip()
    }
    from code2paper.agentic.publication_relevance import _span_overlap

    realized: list[str] = []
    for node in nodes:
        node_claim_ids = {
            str(claim_id)
            for claim_id in (getattr(node, "linked_claim_ids", ()) or ())
            if str(claim_id).strip()
        }
        if not node_claim_ids:
            continue
        for claim in (getattr(claims, "claims", ()) or ()):
            claim_id = str(getattr(claim, "claim_id", "") or "")
            if claim_id not in node_claim_ids:
                continue
            claim_spans = set(_claim_span_ids(claim))
            if bound_spans and any(
                _span_overlap(left, right)
                for left in bound_spans
                for right in claim_spans
            ):
                realized.append(str(getattr(node, "story_node_id", "") or ""))
                break
            if cluster_spans and any(
                _span_overlap(left, right)
                for left in cluster_spans
                for right in claim_spans
            ):
                realized.append(str(getattr(node, "story_node_id", "") or ""))
                break
            if claim_id in bound_spans or claim_id in cluster_spans:
                realized.append(str(getattr(node, "story_node_id", "") or ""))
                break
    return tuple(dict.fromkeys(item for item in realized if item.strip()))


def _card_realizes_story_node(
    *,
    cluster: ConceptCardCandidateClusterV1,
    binding: ConceptCardBindingV1,
    story_spine: Iterable[Any],
    claims: Any,
) -> bool:
    return bool(_card_realized_story_node_ids(
        cluster=cluster,
        binding=binding,
        story_spine=story_spine,
        claims=claims,
    ))


def compile_method_concept_cards(
    *,
    claims: Any,
    completeness: Any | None = None,
    story_spine: Iterable[Any] = (),
    architect: ConceptCardArchitect | None = None,
    evidence_judge: ConceptCardEvidenceJudge | None = None,
    require_evidence_judge: bool = False,
    repo_snapshot_id: str = "",
    project_tree_hash: str = "",
) -> tuple[
    MethodConceptCardSetV1,
    tuple[ConceptCardCandidateClusterV1, ...],
]:
    """Compile bounded clusters into digest-covered concept cards.

    Returns ``(card_set, clusters)``.  When ``architect`` is ``None`` the
    compiler emits a typed gap per cluster (no deterministic prose
    fallback); the owner (Architect LLM) must produce the cards.
    """

    clusters = build_concept_candidate_clusters(
        claims=claims,
        story_spine=story_spine,
        completeness=completeness,
    )
    cards: list[MethodConceptCardV1] = []
    verdicts: list[ConceptCardEvidenceVerdictV1] = []
    bindings: list[ConceptCardBindingV1] = []
    gaps: list[ConceptCardGapV1] = []

    for cluster in clusters:
        if architect is None:
            gaps.append(ConceptCardGapV1(
                gap_id=_stable_id("CG", cluster.cluster_id, "missing"),
                cluster_id=cluster.cluster_id,
                reason="proposal_missing",
                detail="Concept Architect was not configured.",
                source_obligation_ids=cluster.obligation_ids,
            ))
            continue

        proposals: tuple[MethodConceptCardProposalV1, ...] = ()
        validation_error = ""
        for attempt in range(1, 3):
            try:
                proposed = _invoke_concept_architect(
                    architect, cluster, validation_error
                )
            except Exception as exc:  # owner failure is typed
                validation_error = (
                    f"proposal_schema_failed:{type(exc).__name__}:{exc}"
                )
                if attempt < 2:
                    continue
                gaps.append(ConceptCardGapV1(
                    gap_id=_stable_id("CG", cluster.cluster_id, "schema"),
                    cluster_id=cluster.cluster_id,
                    reason="proposal_schema_failed",
                    detail=validation_error,
                    source_obligation_ids=cluster.obligation_ids,
                ))
                proposals = ()
                break
            proposals = (
                proposed.proposals
                if isinstance(proposed, MethodConceptCardProposalBatchV1)
                else (proposed,)
            )
            proposals = _dedupe_cards(cluster, proposals)
            failures_by_index: list[list[str]] = []
            for proposal in proposals:
                failures, _missing = _validate_proposal(cluster, proposal)
                failures_by_index.append(failures)
            if any(failures_by_index):
                failed_indexes = [
                    index for index, failures in enumerate(failures_by_index)
                    if failures
                ]
                if attempt < 2:
                    validation_error = json.dumps({
                        "failed_cards": [
                            {
                                "proposal_index": index + 1,
                                "reasons": failures_by_index[index],
                                "previous_card": proposals[index].model_dump(mode="json"),
                            }
                            for index in failed_indexes
                        ],
                        "closed_fragment_ids": [
                            f"frag-{index}"
                            for index in range(1, len(cluster.source_fragments) + 1)
                        ],
                    }, ensure_ascii=False)
                    continue
                for index in failed_indexes:
                    gaps.append(ConceptCardGapV1(
                        gap_id=_stable_id(
                            "CG", cluster.cluster_id, f"card-{index + 1}"
                        ),
                        cluster_id=cluster.cluster_id,
                        reason="proposal_schema_failed",
                        detail=";".join(failures_by_index[index]),
                        source_obligation_ids=cluster.obligation_ids,
                    ))
                proposals = tuple(
                    proposal
                    for index, proposal in enumerate(proposals)
                    if not failures_by_index[index]
                )
            break

        for index, proposal in enumerate(proposals):
            concept_key = _stable_id(
                "CK", cluster.cluster_id, f"card-{index + 1}",
                proposal.method_subject, proposal.operation,
            )
            # Author-intent cards must carry a visible caveat: the author's
            # intended semantics are candidate-only.  The harness never
            # fabricates paper language for them — a card without a model
            # caveat or missing parts is a typed gap, not a silent promotion.
            if (
                cluster.origin == "author_intent"
                and not proposal.candidate_caveat.strip()
                and not proposal.missing_parts
            ):
                gaps.append(ConceptCardGapV1(
                    gap_id=_stable_id("CG", concept_key, "caveat"),
                    cluster_id=cluster.cluster_id,
                    reason="proposal_schema_failed",
                    detail="author_intent_card_without_caveat",
                    source_obligation_ids=cluster.obligation_ids,
                ))
                continue
            binding = _bind_concept_card(
                cluster, proposal, concept_key=concept_key
            )
            may_enter_verified = (
                cluster.origin == "repository"
                and not cluster.uncertainty_notes
            )
            # A partial repository cluster or any author-intent cluster must
            # be visibly caveated downstream; the harness never silently
            # promotes it.  ``missing_parts`` comes from the model only —
            # uncertainty_notes are harness diagnostics and must not leak
            # into reader-facing cards as method content.
            requires_caveat = (
                cluster.origin != "repository"
                or bool(cluster.uncertainty_notes)
                or not may_enter_verified
            )
            card = MethodConceptCardV1(
                concept_key=concept_key,
                cluster_id=cluster.cluster_id,
                authority_lane=cluster.origin,
                research_question=cluster.research_question,
                method_subject=proposal.method_subject,
                operation=proposal.operation,
                inputs=proposal.inputs,
                outputs=proposal.outputs,
                conditions=proposal.conditions,
                numeric_constraints=proposal.numeric_constraints,
                formula_constraints=proposal.formula_constraints,
                evidence_fragment_refs=proposal.evidence_fragment_refs,
                story_node=proposal.story_node or cluster.story_node,
                known_parts=proposal.known_parts,
                missing_parts=proposal.missing_parts,
                candidate_caveat=proposal.candidate_caveat,
                requires_caveat=requires_caveat,
                may_enter_verified=may_enter_verified,
                evidence_verdict="not_checked",
                realized_story_node_ids=_card_realized_story_node_ids(
                    cluster=cluster,
                    binding=binding,
                    story_spine=story_spine,
                    claims=claims,
                ),
            )
            cards.append(card)
            bindings.append(binding)

    # Per-card evidence judgment (Stage 3 wiring; optional in Stage 2).
    if evidence_judge is not None and cards:
        for cluster in clusters:
            cluster_cards = tuple(
                card for card in cards
                if card.cluster_id == cluster.cluster_id
            )
            if not cluster_cards:
                continue
            try:
                judged = evidence_judge(cluster_cards, cluster)
            except Exception as exc:  # owner failure is typed
                for card in cluster_cards:
                    gaps.append(ConceptCardGapV1(
                        gap_id=_stable_id("CG", card.concept_key, "judge"),
                        cluster_id=cluster.cluster_id,
                        reason="evidence_judge_failed",
                        detail=f"{type(exc).__name__}:{exc}",
                        source_obligation_ids=cluster.obligation_ids,
                    ))
                    # A card whose judge call failed must NOT keep the
                    # initial verified eligibility: the per-field verdict is
                    # missing, so verified entry is not proven.  Downgrade
                    # fail-closed.
                    cards[cards.index(card)] = MethodConceptCardV1(
                        concept_key=card.concept_key,
                        cluster_id=card.cluster_id,
                        authority_lane=card.authority_lane,
                        research_question=card.research_question,
                        method_subject=card.method_subject,
                        operation=card.operation,
                        inputs=card.inputs,
                        outputs=card.outputs,
                        conditions=card.conditions,
                        numeric_constraints=card.numeric_constraints,
                        formula_constraints=card.formula_constraints,
                        evidence_fragment_refs=card.evidence_fragment_refs,
                        story_node=card.story_node,
                        known_parts=card.known_parts,
                        missing_parts=card.missing_parts,
                        candidate_caveat=card.candidate_caveat,
                        requires_caveat=True,
                        may_enter_verified=False,
                        evidence_verdict="not_found",
                        realized_story_node_ids=tuple(card.realized_story_node_ids),
                        writing_role=getattr(card, "writing_role", None),
                    )
                continue
            for verdict in judged:
                verdict = _enforce_purpose_evidence_rule(
                    verdict, cluster
                )
                verdicts.append(verdict)
                for index, card in enumerate(cluster_cards):
                    if card.concept_key != verdict.concept_key:
                        continue
                    # model_copy does not re-run validators on frozen models,
                    # so the digest would stay stale; rebuild the card so the
                    # content digest covers the judged verdict.
                    rebuilt = MethodConceptCardV1(
                        concept_key=card.concept_key,
                        cluster_id=card.cluster_id,
                        authority_lane=card.authority_lane,
                        research_question=card.research_question,
                        method_subject=card.method_subject,
                        operation=card.operation,
                        inputs=card.inputs,
                        outputs=card.outputs,
                        conditions=card.conditions,
                        numeric_constraints=card.numeric_constraints,
                        formula_constraints=card.formula_constraints,
                        evidence_fragment_refs=card.evidence_fragment_refs,
                        story_node=card.story_node,
                        known_parts=card.known_parts,
                        missing_parts=card.missing_parts,
                        candidate_caveat=card.candidate_caveat,
                        requires_caveat=card.requires_caveat,
                        may_enter_verified=(
                            card.may_enter_verified
                            and verdict.overall_verdict == "entailed"
                        ),
                        evidence_verdict=verdict.overall_verdict,
                        realized_story_node_ids=tuple(card.realized_story_node_ids),
                        writing_role=getattr(card, "writing_role", None),
                    )
                    cards[cards.index(card)] = rebuilt

    card_set = MethodConceptCardSetV1(
        repo_snapshot_id=repo_snapshot_id,
        project_tree_hash=project_tree_hash,
        cards=tuple(cards),
        evidence_verdicts=tuple(verdicts),
        bindings=tuple(bindings),
        gaps=tuple(gaps),
    )
    return card_set, clusters
