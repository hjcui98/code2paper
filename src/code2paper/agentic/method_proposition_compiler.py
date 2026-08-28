"""Compile evidence and author intent into validated method propositions."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    CodeFactSetV1,
    EvidencePacketSetV3,
)
from code2paper.agentic.method_argument_models import MethodCompletenessMatrixV1
from code2paper.agentic.method_argument_models import ConfigurationClaimSetV1
from code2paper.agentic.equation_claims import EquationClaimSetV1
from code2paper.agentic.method_product_models import AuthorStoryNodeV1, method_lane_from_reference_status
from code2paper.agentic.publication_relevance import (
    classify_fact_writing_role,
    classify_proposition_writing_role,
)
from code2paper.agentic.method_proposition_models import (
    MethodPropositionProposalBatchV1,
    MethodPropositionProposalV1,
    MethodPropositionSetV1,
    MethodPropositionV1,
    PropositionEvidenceVerdictV1,
    PropositionBindingSidecarV1,
    PropositionBindingV1,
    PropositionCandidateClusterV1,
    TypedPropositionGapV1,
)


ProposalArchitect = Callable[
    ...,
    MethodPropositionProposalV1 | MethodPropositionProposalBatchV1,
]
EvidenceJudge = Callable[[dict[str, Any]], PropositionEvidenceVerdictV1 | dict[str, Any] | None]
_NUMBER = re.compile(r"(?<![A-Za-z_])(?:\d+(?:\.\d+)?(?:e[+-]?\d+)?%?)(?![A-Za-z_])", re.I)
_FORMULA = re.compile(r"(?:[$][^$\n]+[$]|\\(?:frac|sum|prod|mathbb|mathbf|mathcal)\b[^\n,.;]*)")
_HIGH_RISK_CONCEPT = re.compile(
    r"\b(?:outperform(?:s|ed|ing)?|state[- ]of[- ]the[- ]art|novel|"
    r"improv(?:e|es|ed|ing|ement)|enhanc(?:e|es|ed|ing)|"
    r"guarantee(?:s|d)?|ensure(?:s|d)?|more accurate|faster|"
    r"robust(?:ness)?|efficient(?:ly|cy)?|speedup)\b",
    re.I,
)
_PROPOSITION_COVERAGE_PREDICATES = frozenset({
    "constructs", "returns", "transforms", "concatenates", "stacks",
    "normalizes", "aggregates", "computes_formula", "branches_on",
    "selects", "selects_top_k", "sorts_by", "constructs_mask", "filters_by",
    "reshapes", "projects", "attends", "samples", "propagates",
})
_NONCONCEPTUAL_PROPOSITION_LANGUAGE = re.compile(
    r"\b(?:author intends?|binding harness|implementation (?:relies|binds|maps)|"
    r"downstream|for pruning decisions?|serves as|is designed to|ready for|"
    r"ensures?|enables?|robust(?:ness)?|benefits?|captures? .*? for)\b",
    re.IGNORECASE,
)
_RAW_IMPLEMENTATION_TERM = re.compile(
    r"\b(?:torch\.|self\.|GaussianModel\.|f_p_|input_features|prune_features|"
    r"cut_off_(?:idx|features?))",
    re.IGNORECASE,
)


def _stable_id(prefix: str, *parts: str) -> str:
    value = "\x1f".join(parts).encode()
    return f"{prefix}-{hashlib.sha256(value).hexdigest()[:16]}"


def _flatten(value: str | list[str]) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item).strip())
    return (value,) if value.strip() else ()


def build_proposition_candidate_clusters(
    *,
    claims: AtomicClaimSetV3,
    facts: CodeFactSetV1,
    packets: EvidencePacketSetV3,
    completeness: MethodCompletenessMatrixV1 | None = None,
    story_spine: Iterable[AuthorStoryNodeV1] = (),
) -> tuple[PropositionCandidateClusterV1, ...]:
    """Build project-agnostic closed clusters without generating prose.

    Supported claims are grouped by obligation and evidence connectivity.
    Candidate-only rows preserve author-owned statements verbatim as an input
    envelope; they never inherit repository authority from nearby claims.
    """

    facts_by_id = {item.fact_id: item for item in facts.facts}
    relations = {item.relation_id: item for packet in packets.packets for item in packet.relations}
    story_by_obligation: dict[str, list[AuthorStoryNodeV1]] = defaultdict(list)
    for node in story_spine:
        for obligation_id in node.linked_obligation_ids:
            story_by_obligation[obligation_id].append(node)

    grouped: dict[str, list] = defaultdict(list)
    for claim in claims.claims:
        if claim.status not in {"supported", "partial"}:
            continue
        keys = claim.covers_obligation_ids or [f"claim:{claim.claim_id}"]
        for key in keys:
            grouped[key].append(claim)

    clusters: list[PropositionCandidateClusterV1] = []
    for obligation_id, obligation_group in sorted(grouped.items()):
        for group in _connected_claim_components(obligation_group, facts_by_id, relations):
            claim_ids = tuple(claim.claim_id for claim in group)
            fact_ids = tuple(dict.fromkeys(fid for claim in group for fid in claim.fact_ids if fid in facts_by_id))
            bound_facts = [facts_by_id[fid] for fid in fact_ids]
            relation_ids = tuple(dict.fromkeys(
                rid for claim in group for rid in claim.relation_evidence_ids if rid in relations
            ))
            connectivity_edges: list[tuple[str, str]] = []
            for fact_index, left_fact in enumerate(bound_facts):
                for right_fact in bound_facts[fact_index + 1:]:
                    shared_subject = left_fact.subject == right_fact.subject
                    shared_claim = any(
                        left_fact.fact_id in claim.fact_ids
                        and right_fact.fact_id in claim.fact_ids
                        for claim in group
                    )
                    relation_connected = any(
                        {
                            str(relations[relation_id].source_symbol),
                            str(relations[relation_id].target_symbol),
                        } == {str(left_fact.subject), str(right_fact.subject)}
                        for relation_id in relation_ids
                    )
                    if shared_subject or shared_claim or relation_connected:
                        connectivity_edges.append((left_fact.fact_id, right_fact.fact_id))
            span_ids = tuple(dict.fromkeys(
                span for claim in group for span in claim.direct_evidence_ids
            ))
            if not span_ids:
                span_ids = tuple(dict.fromkeys(span for fact in bound_facts for span in fact.direct_span_ids))
            qualifiers = tuple(dict.fromkeys(q for claim in group for q in claim.required_qualifiers))
            lane = "repository_partial" if any(claim.status == "partial" for claim in group) else "repository_verified"
            story_nodes = story_by_obligation.get(obligation_id, ())
            hints = tuple(dict.fromkeys(node.story_node_id for node in story_nodes))
            author_term_hints = tuple(dict.fromkeys(
                value
                for node in story_nodes
                for value in (node.title, node.author_statement)
                if value.strip()
            ))
            clusters.append(PropositionCandidateClusterV1(
                cluster_id=_stable_id("PC", obligation_id, *claim_ids),
                origin="repository_evidence",
                obligation_ids=() if obligation_id.startswith("claim:") else (obligation_id,),
                claim_ids=claim_ids,
                fact_ids=fact_ids,
                fact_connectivity_edges=tuple(connectivity_edges),
                relation_ids=relation_ids,
                span_ids=span_ids,
                source_statements=tuple(claim.canonical_text for claim in group),
                subjects=tuple(fact.subject for fact in bound_facts),
                predicates=tuple(fact.predicate for fact in bound_facts),
                operands=tuple(value for fact in bound_facts for value in _flatten(fact.object)),
                conditions=tuple(condition for fact in bound_facts for condition in fact.conditions),
                required_qualifiers=qualifiers,
                claim_required_qualifiers=tuple(
                    (claim.claim_id, tuple(claim.required_qualifiers))
                    for claim in group
                ),
                section_hints=hints,
                author_term_hints=author_term_hints,
                evidence_lane=lane,
            ))

    covered = {oid for cluster in clusters for oid in cluster.obligation_ids}
    if completeness is not None:
        for row in completeness.items:
            if row.status == "out_of_scope":
                continue
            # A few repository facts may bind the same broad obligation while
            # the completeness row still says partial/gap/confirmation. Keep
            # both surfaces: the repository proposition describes only the
            # known implementation fragment and this author-intent proposition
            # carries the unresolved intended semantics into candidate prose.
            # Skip only obligations whose completeness state itself is fully
            # repository-supported.
            if (
                row.obligation_id in covered
                and row.status == "supported_by_repository"
            ):
                continue
            nodes = story_by_obligation.get(row.obligation_id, ())
            statement = row.statement.strip()
            if not statement:
                continue
            clusters.append(PropositionCandidateClusterV1(
                cluster_id=_stable_id("PC", row.obligation_id, statement),
                origin="author_intent",
                obligation_ids=(row.obligation_id,),
                source_statements=(statement,),
                uncertainty_notes=((row.reason.strip(),) if row.reason.strip() else ()),
                section_hints=tuple(node.story_node_id for node in nodes),
                author_term_hints=tuple(dict.fromkeys(
                    value
                    for node in nodes
                    for value in (node.title, node.author_statement)
                    if value.strip()
                )),
                evidence_lane=method_lane_from_reference_status(row.status),
                required_qualifiers=(),
            ))
    return tuple(clusters)


def _connected_claim_components(group, facts_by_id, relations) -> list[list]:
    """Split one broad obligation into exact evidence-graph components."""

    if len(group) < 2:
        return [list(group)]
    adjacency: dict[str, set[str]] = {claim.claim_id: set() for claim in group}

    def subjects(claim) -> set[str]:
        return {
            str(facts_by_id[fact_id].subject)
            for fact_id in claim.fact_ids if fact_id in facts_by_id
        }

    for index, left in enumerate(group):
        left_facts = set(left.fact_ids)
        left_relations = set(left.relation_evidence_ids)
        left_subjects = subjects(left)
        for right in group[index + 1:]:
            right_facts = set(right.fact_ids)
            right_relations = set(right.relation_evidence_ids)
            right_subjects = subjects(right)
            relation_ids = left_relations | right_relations
            relation_connects = any(
                relation_id in relations
                and {
                    str(relations[relation_id].source_symbol),
                    str(relations[relation_id].target_symbol),
                }.intersection(left_subjects)
                and {
                    str(relations[relation_id].source_symbol),
                    str(relations[relation_id].target_symbol),
                }.intersection(right_subjects)
                for relation_id in relation_ids
            )
            if (
                left_facts.intersection(right_facts)
                or left_relations.intersection(right_relations)
                or left_subjects.intersection(right_subjects)
                or relation_connects
            ):
                adjacency[left.claim_id].add(right.claim_id)
                adjacency[right.claim_id].add(left.claim_id)
    by_id = {claim.claim_id: claim for claim in group}
    unseen = set(by_id)
    components: list[list] = []
    while unseen:
        root = min(unseen)
        pending = [root]
        component: list = []
        unseen.remove(root)
        while pending:
            claim_id = pending.pop()
            component.append(by_id[claim_id])
            for neighbor in sorted(adjacency[claim_id]):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    pending.append(neighbor)
        components.append(sorted(component, key=lambda item: item.claim_id))
    return components


def _validate_proposal(
    cluster: PropositionCandidateClusterV1,
    proposal: MethodPropositionProposalV1,
) -> str:
    if proposal.cluster_id != cluster.cluster_id:
        return "unknown_binding_id"
    for used, allowed in (
        (proposal.used_claim_ids, cluster.claim_ids),
        (proposal.used_fact_ids, cluster.fact_ids),
        (proposal.used_relation_ids, cluster.relation_ids),
    ):
        if not set(used).issubset(set(allowed)):
            return "unknown_binding_id"
    if cluster.origin == "repository_evidence" and (not proposal.used_claim_ids or not proposal.used_fact_ids):
        return "evidence_not_connected"
    selected_fact_ids = set(proposal.used_fact_ids)
    if len(selected_fact_ids) > 1:
        adjacency = {fact_id: set() for fact_id in selected_fact_ids}
        for left, right in cluster.fact_connectivity_edges:
            if left in selected_fact_ids and right in selected_fact_ids:
                adjacency[left].add(right)
                adjacency[right].add(left)
        root = next(iter(selected_fact_ids))
        visited = {root}
        pending = [root]
        while pending:
            current = pending.pop()
            for neighbor in adjacency[current] - visited:
                visited.add(neighbor)
                pending.append(neighbor)
        if visited != selected_fact_ids:
            return "evidence_not_connected"
    if not proposal.reader_subject.strip() or not proposal.transformation.strip():
        return "empty_concept"
    # Every decomposition must identify the exact source text it preserves.
    # Otherwise a batch containing several numbers, formulae, or qualifiers can
    # silently copy every cluster-level constraint onto every proposition.
    if not proposal.source_statement_fragments:
        return "source_fragment_not_closed"
    if proposal.source_statement_fragments:
        source_surface = "\n".join(cluster.source_statements)
        if any(fragment not in source_surface for fragment in proposal.source_statement_fragments):
            return "source_fragment_not_closed"
    proposal_surface = " ".join((
        proposal.reader_subject,
        proposal.transformation,
        *proposal.inputs,
        *proposal.outputs,
        *proposal.conditions,
        proposal.boundary,
        *proposal.paper_terms,
    ))
    source_surface = " ".join((
        *cluster.source_statements,
        *cluster.subjects,
        *cluster.predicates,
        *cluster.operands,
        *cluster.conditions,
        *cluster.required_qualifiers,
    ))
    proposed_risks = {item.casefold() for item in _HIGH_RISK_CONCEPT.findall(proposal_surface)}
    source_risks = {item.casefold() for item in _HIGH_RISK_CONCEPT.findall(source_surface)}
    if proposed_risks - source_risks:
        return "authority_expansion"
    transformation = proposal.transformation.strip()
    if (
        len(transformation) > 360
        or len(re.findall(r"[.!?](?:\s|$)", transformation)) > 1
        or _NONCONCEPTUAL_PROPOSITION_LANGUAGE.search(transformation)
    ):
        return "concept_not_atomic"
    if cluster.origin == "repository_evidence" and _RAW_IMPLEMENTATION_TERM.search(
        transformation
    ):
        return "concept_not_atomic"
    selected_source = " ".join(
        proposal.source_statement_fragments or cluster.source_statements
    )
    if cluster.origin == "repository_evidence" and re.search(
        r"\b(?:calls|computes|concatenates|stacks|normalizes|reduces|sorts by|"
        r"returns|constructs|projects|samples|propagates)\b",
        selected_source,
        re.IGNORECASE,
    ):
        if re.search(r"\bresult\s*=", selected_source, re.IGNORECASE) and not proposal.outputs:
            return "concept_fields_missing"
        if re.search(
            r"\b(?:calls|concatenates|stacks|reduces|sorts by|projects|samples)\b",
            selected_source,
            re.IGNORECASE,
        ) and not proposal.inputs:
            return "concept_fields_missing"
    if cluster.origin == "author_intent":
        # Candidate authority still needs semantic fidelity to the author's
        # supplied statement.  Keeping numbers only in a hidden immutable
        # sidecar allowed a broad 15-dimensional descriptor claim to collapse
        # into the empty label "Feature extraction and normalization", which
        # the Writer then misread as 15 operations/targets.  Require explicit
        # numeric and parenthetical component content to survive in the
        # conceptual card that the Writer actually sees.
        selected_author_surface = " ".join(
            proposal.source_statement_fragments or cluster.source_statements
        )
        dimension_numbers = {
            match.group(1)
            for match in re.finditer(
                r"\b(\d+(?:\.\d+)?)\s*(?:-|\s)?(?:dimensional|dimension|layer)\b",
                selected_author_surface,
                re.IGNORECASE,
            )
        }
        proposed_numbers = set(_NUMBER.findall(proposal_surface))
        if dimension_numbers - proposed_numbers:
            return "author_semantics_missing"
        parenthetical_groups = re.findall(
            r"\(([^()]*,[^()]*)\)", selected_author_surface
        )
        proposed_tokens = _semantic_tokens(proposal_surface)
        for group in parenthetical_groups:
            component_tokens = {
                token
                for component in group.split(",")
                for token in _semantic_tokens(component)
            }
            if component_tokens and len(component_tokens & proposed_tokens) < min(
                2, len(component_tokens)
            ):
                return "author_semantics_missing"
    authorized_conditions = tuple(dict.fromkeys((
        *cluster.conditions,
        *cluster.required_qualifiers,
        *cluster.source_statements,
    )))
    if any(
        not any(condition.casefold() in allowed.casefold() for allowed in authorized_conditions)
        for condition in proposal.conditions
    ):
        return "condition_not_closed"
    combined_conditions = " ".join(proposal.conditions).casefold()
    qualifiers_by_claim = dict(cluster.claim_required_qualifiers)
    selected_qualifiers = tuple(dict.fromkeys(
        qualifier
        for claim_id in proposal.used_claim_ids
        for qualifier in qualifiers_by_claim.get(claim_id, ())
    ))
    for qualifier in selected_qualifiers:
        if qualifier.casefold() not in combined_conditions and qualifier.casefold() not in proposal.boundary.casefold():
            return "qualifier_weakened"
    return ""


def _semantic_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9-]+", value.casefold())
        if len(token) > 2 and token not in {
            "and", "for", "from", "into", "the", "this", "using", "with",
        }
    }


def _bind_proposal_from_source_fragments(
    *,
    cluster: PropositionCandidateClusterV1,
    proposal: MethodPropositionProposalV1,
    claims: AtomicClaimSetV3,
) -> MethodPropositionProposalV1:
    """Project model semantics onto exact evidence without model-owned IDs.

    The Proposition Architect owns the conceptual decomposition and selects
    exact ``source_statement_fragments``. Claim/fact/relation identities are
    binding metadata owned by the harness: asking a language model to copy
    long opaque IDs makes a semantically useful card fail for an irrelevant
    transcription error. Foreign IDs supplied by a model are therefore never
    trusted or preserved. They are replaced by the claims whose canonical
    source statements contain the selected fragments, then projected through
    those claims to their exact facts and relations.
    """

    if cluster.origin == "author_intent":
        return proposal.model_copy(update={
            "cluster_id": cluster.cluster_id,
            "used_claim_ids": (),
            "used_fact_ids": (),
            "used_relation_ids": (),
        })

    selected_statements = {
        statement
        for statement in cluster.source_statements
        if any(
            fragment and fragment in statement
            for fragment in proposal.source_statement_fragments
        )
    }
    selected_claims = [
        claim
        for claim in claims.claims
        if claim.claim_id in cluster.claim_ids
        and claim.canonical_text in selected_statements
    ]
    claim_ids = tuple(claim.claim_id for claim in selected_claims)
    fact_ids = tuple(dict.fromkeys(
        fact_id
        for claim in selected_claims
        for fact_id in claim.fact_ids
        if fact_id in cluster.fact_ids
    ))
    relation_ids = tuple(dict.fromkeys(
        relation_id
        for claim in selected_claims
        for relation_id in claim.relation_evidence_ids
        if relation_id in cluster.relation_ids
    ))
    return proposal.model_copy(update={
        "cluster_id": cluster.cluster_id,
        "used_claim_ids": claim_ids,
        "used_fact_ids": fact_ids,
        "used_relation_ids": relation_ids,
    })


def _invoke_proposal_architect(
    proposal_architect: ProposalArchitect,
    cluster: PropositionCandidateClusterV1,
    validation_error: str,
) -> MethodPropositionProposalV1 | MethodPropositionProposalBatchV1:
    """Call new repair-aware owners while preserving one-argument fixtures."""

    try:
        parameters = inspect.signature(proposal_architect).parameters.values()
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
        return proposal_architect(cluster, validation_error)
    return proposal_architect(cluster)


def _proposal_repair_feedback(
    *,
    proposals: tuple[MethodPropositionProposalV1, ...],
    failures: tuple[str, ...],
    missing_source_statements: tuple[str, ...],
) -> str:
    """Serialize semantic repair context without exposing sidecar IDs."""

    return json.dumps({
        "failed_cards": [
            {
                "proposal_index": index,
                "reason": failure,
                "previous_card": {
                    "reader_subject": proposal.reader_subject,
                    "transformation": proposal.transformation,
                    "inputs": list(proposal.inputs),
                    "outputs": list(proposal.outputs),
                    "conditions": list(proposal.conditions),
                    "boundary": proposal.boundary,
                    "paper_terms": list(proposal.paper_terms),
                    "implementation_binding_terms": list(
                        proposal.implementation_binding_terms
                    ),
                    "source_statement_fragments": list(
                        proposal.source_statement_fragments
                    ),
                },
            }
            for index, (proposal, failure) in enumerate(
                zip(proposals, failures, strict=True), start=1
            )
            if failure
        ],
        "valid_cards_to_preserve": [
            {
                "reader_subject": proposal.reader_subject,
                "transformation": proposal.transformation,
                "inputs": list(proposal.inputs),
                "outputs": list(proposal.outputs),
                "conditions": list(proposal.conditions),
                "boundary": proposal.boundary,
                "paper_terms": list(proposal.paper_terms),
                "implementation_binding_terms": list(
                    proposal.implementation_binding_terms
                ),
                "source_statement_fragments": list(
                    proposal.source_statement_fragments
                ),
            }
            for proposal, failure in zip(proposals, failures, strict=True)
            if not failure
        ],
        "missing_source_statements": list(missing_source_statements),
    }, ensure_ascii=False)


def _build_evidence_judge_payload(
    *,
    proposition_id: str,
    proposal: MethodPropositionProposalV1,
    claims: AtomicClaimSetV3,
    facts: CodeFactSetV1,
    packets: EvidencePacketSetV3,
) -> tuple[dict[str, Any], tuple[str, ...], set[str]]:
    """Project one proposed concept onto its exact repository evidence."""

    spans_by_id = {
        span.span_id: span
        for packet in packets.packets
        for span in packet.spans
    }
    facts_by_id = {fact.fact_id: fact for fact in facts.facts}
    claims_by_id = {claim.claim_id: claim for claim in claims.claims}
    relations_by_id = {
        relation.relation_id: relation
        for packet in packets.packets
        for relation in packet.relations
    }
    selected_claims = [
        claims_by_id[item]
        for item in proposal.used_claim_ids
        if item in claims_by_id
    ]
    selected_fact_ids = set(proposal.used_fact_ids)
    selected_span_ids = tuple(dict.fromkeys(
        span_id
        for claim in selected_claims
        for span_id in claim.direct_evidence_ids
    )) or tuple(dict.fromkeys(
        span_id
        for fact in facts.facts if fact.fact_id in selected_fact_ids
        for span_id in fact.direct_span_ids
    ))
    required_fields = {"reader_subject", "transformation"}
    if proposal.inputs:
        required_fields.add("inputs")
    if proposal.outputs:
        required_fields.add("outputs")
    if proposal.conditions:
        required_fields.add("conditions")
    if proposal.boundary.strip():
        required_fields.add("boundary")
    return ({
        "proposition_id": proposition_id,
        "proposed_semantics": {
            "reader_subject": proposal.reader_subject,
            "transformation": proposal.transformation,
            "inputs": list(proposal.inputs),
            "outputs": list(proposal.outputs),
            "conditions": list(proposal.conditions),
            "boundary": proposal.boundary,
        },
        "required_semantic_fields": sorted(required_fields),
        "selected_atomic_claims": [
            claims_by_id[item].model_dump(mode="json")
            for item in proposal.used_claim_ids if item in claims_by_id
        ],
        "selected_code_facts": [
            facts_by_id[item].model_dump(mode="json")
            for item in proposal.used_fact_ids if item in facts_by_id
        ],
        "selected_relations": [
            relations_by_id[item].model_dump(mode="json")
            for item in proposal.used_relation_ids if item in relations_by_id
        ],
        "exact_code_excerpts": [
            spans_by_id[item].model_dump(mode="json")
            for item in selected_span_ids if item in spans_by_id
        ],
    }, selected_span_ids, required_fields)


def compile_method_propositions(
    *,
    claims: AtomicClaimSetV3,
    facts: CodeFactSetV1,
    packets: EvidencePacketSetV3,
    completeness: MethodCompletenessMatrixV1 | None,
    story_spine: Iterable[AuthorStoryNodeV1],
    proposal_architect: ProposalArchitect | None,
    evidence_judge: EvidenceJudge | None = None,
    require_evidence_judge: bool = False,
    configurations: ConfigurationClaimSetV1 | None = None,
    equations: EquationClaimSetV1 | None = None,
) -> tuple[MethodPropositionSetV1, PropositionBindingSidecarV1, tuple[PropositionCandidateClusterV1, ...]]:
    """Run the bounded proposal step and fail typed when it cannot be trusted."""

    clusters = build_proposition_candidate_clusters(
        claims=claims, facts=facts, packets=packets, completeness=completeness, story_spine=story_spine,
    )
    propositions: list[MethodPropositionV1] = []
    evidence_verdicts: list[PropositionEvidenceVerdictV1] = []
    bindings: list[PropositionBindingV1] = []
    gaps: list[TypedPropositionGapV1] = []
    for cluster in clusters:
        if proposal_architect is None:
            gaps.append(TypedPropositionGapV1(
                gap_id=_stable_id("PG", cluster.cluster_id, "missing"), cluster_id=cluster.cluster_id,
                reason="proposal_missing", detail="Proposition Architect was not configured.",
                source_obligation_ids=cluster.obligation_ids,
            ))
            continue
        proposals: tuple[MethodPropositionProposalV1, ...] = ()
        proposal_failures: tuple[str, ...] = ()
        missing_source_statements: tuple[str, ...] = ()
        validation_error = ""
        preserved_valid_proposals: tuple[MethodPropositionProposalV1, ...] = ()
        for owner_attempt in range(1, 3):
            try:
                proposed = _invoke_proposal_architect(
                    proposal_architect, cluster, validation_error
                )
            except Exception as exc:  # owner failure is typed; no harness prose fallback
                validation_error = f"proposal_schema_failed:{type(exc).__name__}:{exc}"
                if owner_attempt < 2:
                    continue
                gaps.append(TypedPropositionGapV1(
                    gap_id=_stable_id("PG", cluster.cluster_id, "schema"),
                    cluster_id=cluster.cluster_id,
                    reason="proposal_schema_failed",
                    detail=validation_error,
                    source_obligation_ids=cluster.obligation_ids,
                ))
                proposals = ()
                break
            proposals = (
                proposed.proposals
                if isinstance(proposed, MethodPropositionProposalBatchV1)
                else (proposed,)
            )
            proposals = tuple(
                _bind_proposal_from_source_fragments(
                    cluster=cluster,
                    proposal=proposal,
                    claims=claims,
                )
                for proposal in proposals
            )
            if preserved_valid_proposals:
                # A repair turn owns only failed/missing concepts. Preserve
                # the already-valid cards from the first response in the
                # harness instead of trusting the second response to copy
                # them all back verbatim. Previously a repair for one missing
                # normalization statement replaced five good descriptor cards
                # with one oversized card, losing the usable research result.
                proposals = _merge_proposition_repair(
                    preserved=preserved_valid_proposals,
                    repaired=proposals,
                )
            proposal_failures = tuple(
                _validate_proposal(cluster, proposal) for proposal in proposals
            )
            claims_by_id = {claim.claim_id: claim for claim in claims.claims}
            facts_by_id = {fact.fact_id: fact for fact in facts.facts}
            required_claim_ids = {
                claim_id
                for claim_id in cluster.claim_ids
                if claim_id in claims_by_id
                and any(
                    fact_id in facts_by_id
                    and facts_by_id[fact_id].predicate in _PROPOSITION_COVERAGE_PREDICATES
                    for fact_id in claims_by_id[claim_id].fact_ids
                )
            }
            covered_claim_ids = {
                claim_id
                for proposal, failure in zip(
                    proposals, proposal_failures, strict=True
                )
                if not failure
                for claim_id in proposal.used_claim_ids
            }
            missing_source_statements = tuple(
                claims_by_id[claim_id].canonical_text
                for claim_id in cluster.claim_ids
                if claim_id in required_claim_ids
                and claim_id not in covered_claim_ids
            )
            if not any(proposal_failures) and not missing_source_statements:
                break
            if owner_attempt == 1:
                preserved_valid_proposals = tuple(
                    proposal
                    for proposal, failure in zip(
                        proposals, proposal_failures, strict=True
                    )
                    if not failure
                )
            validation_error = _proposal_repair_feedback(
                proposals=proposals,
                failures=proposal_failures,
                missing_source_statements=missing_source_statements,
            )
            if owner_attempt == 2:
                break
        if missing_source_statements:
            gaps.append(TypedPropositionGapV1(
                gap_id=_stable_id(
                    "PG", cluster.cluster_id, "concept_coverage_missing",
                    *missing_source_statements,
                ),
                cluster_id=cluster.cluster_id,
                reason="concept_coverage_missing",
                detail=(
                    "No valid proposition covers these method-significant source statements: "
                    + " | ".join(missing_source_statements)
                ),
                source_obligation_ids=cluster.obligation_ids,
            ))
        cluster_judgments: dict[str, PropositionEvidenceVerdictV1] = {}
        cluster_judge_failure = ""
        valid_repository_proposals: list[tuple[str, MethodPropositionProposalV1]] = []
        if cluster.origin == "repository_evidence" and evidence_judge is not None:
            for proposal_index, proposal in enumerate(proposals, start=1):
                if proposal_failures[proposal_index - 1]:
                    continue
                proposition_id = _stable_id(
                    "MP",
                    cluster.cluster_id,
                    str(proposal_index),
                    proposal.reader_subject,
                    proposal.transformation,
                )
                valid_repository_proposals.append((proposition_id, proposal))
            if valid_repository_proposals:
                prepared = [
                    _build_evidence_judge_payload(
                        proposition_id=proposition_id,
                        proposal=proposal,
                        claims=claims,
                        facts=facts,
                        packets=packets,
                    )[0]
                    for proposition_id, proposal in valid_repository_proposals
                ]
                try:
                    if len(prepared) > 1 and hasattr(evidence_judge, "judge_batch"):
                        raw_cluster_judgments = evidence_judge.judge_batch(prepared)  # type: ignore[attr-defined]
                    else:
                        raw_cluster_judgments = [
                            evidence_judge(payload) for payload in prepared
                        ]
                except Exception as exc:
                    raw_cluster_judgments = []
                    cluster_judge_failure = (
                        f"{type(exc).__name__}:{str(exc) or 'judge call failed'}"
                    )
                if not cluster_judge_failure:
                    for (proposition_id, _proposal), raw_verdict in zip(
                        valid_repository_proposals,
                        raw_cluster_judgments,
                        strict=False,
                    ):
                        if raw_verdict is None:
                            continue
                        try:
                            candidate_verdict = (
                                raw_verdict
                                if isinstance(raw_verdict, PropositionEvidenceVerdictV1)
                                else PropositionEvidenceVerdictV1.model_validate(raw_verdict)
                            )
                        except ValueError:
                            continue
                        cluster_judgments[proposition_id] = candidate_verdict
                    if len(cluster_judgments) != len(valid_repository_proposals):
                        cluster_judgments.clear()
                        cluster_judge_failure = (
                            "judge returned an incomplete or invalid cluster verdict"
                        )
        for proposal_index, proposal in enumerate(proposals, start=1):
            failure = proposal_failures[proposal_index - 1]
            if failure:
                gaps.append(TypedPropositionGapV1(
                    gap_id=_stable_id(
                        "PG", cluster.cluster_id, str(proposal_index), failure
                    ),
                    cluster_id=cluster.cluster_id,
                    reason=failure,
                    detail="Proposition proposal violated the closed cluster contract.",
                    source_obligation_ids=cluster.obligation_ids,
                ))
                continue
            proposition_id = _stable_id(
                "MP",
                cluster.cluster_id,
                str(proposal_index),
                proposal.reader_subject,
                proposal.transformation,
            )
            source_text = " ".join(
                proposal.source_statement_fragments or cluster.source_statements
            )
            selected_claims = [
                claim for claim in claims.claims
                if claim.claim_id in proposal.used_claim_ids
            ]
            selected_fact_ids = set(proposal.used_fact_ids)
            selected_span_ids = tuple(dict.fromkeys(
                span_id
                for claim in selected_claims
                for span_id in claim.direct_evidence_ids
            )) or tuple(dict.fromkeys(
                span_id
                for fact in facts.facts if fact.fact_id in selected_fact_ids
                for span_id in fact.direct_span_ids
            ))
            selected_qualifiers = tuple(dict.fromkeys(
                qualifier for claim in selected_claims
                for qualifier in claim.required_qualifiers
            ))
            selected_equation_ids = tuple(
                equation.equation_id
                for equation in (equations.equations if equations is not None else ())
                if set(equation.fact_ids).intersection(selected_fact_ids)
                or equation.prose_claim_id in proposal.used_claim_ids
            )
            selected_configuration_ids = tuple(
                configuration.configuration_id
                for configuration in (configurations.claims if configurations is not None else ())
                if set(configuration.source_fact_ids).intersection(selected_fact_ids)
                or set(configuration.override_chain).intersection(proposal.used_relation_ids)
            )
            partial = cluster.evidence_lane == "repository_partial"
            candidate_only = cluster.origin == "author_intent" or cluster.evidence_lane not in {
                "repository_verified", "repository_partial",
            }
            evidence_status = "not_checked"
            evidence_verdict: PropositionEvidenceVerdictV1 | None = None
            evidence_judge_failure = ""
            if cluster.origin == "repository_evidence" and evidence_judge is not None:
                _judge_payload, _judge_spans, required_fields = (
                    _build_evidence_judge_payload(
                        proposition_id=proposition_id,
                        proposal=proposal,
                        claims=claims,
                        facts=facts,
                        packets=packets,
                    )
                )
                raw_verdict = cluster_judgments.get(proposition_id)
                evidence_judge_failure = cluster_judge_failure
                if raw_verdict is None and not evidence_judge_failure:
                    evidence_judge_failure = "judge returned no valid verdict"
                if raw_verdict is not None:
                    try:
                        candidate_verdict = (
                            raw_verdict if isinstance(raw_verdict, PropositionEvidenceVerdictV1)
                            else PropositionEvidenceVerdictV1.model_validate(raw_verdict)
                        )
                    except ValueError:
                        candidate_verdict = None
                        evidence_judge_failure = "judge verdict failed model validation"
                    if candidate_verdict is not None:
                        # The judge owns only semantic support. Opaque evidence
                        # identities are already closed by the proposition
                        # sidecar and must not depend on model transcription.
                        candidate_verdict = candidate_verdict.model_copy(update={
                            "claim_ids": proposal.used_claim_ids,
                            "fact_ids": proposal.used_fact_ids,
                            "relation_ids": proposal.used_relation_ids,
                            "span_ids": selected_span_ids,
                        })
                        ids_closed = (
                            candidate_verdict.proposition_id == proposition_id
                            and set(candidate_verdict.claim_ids).issubset(set(proposal.used_claim_ids))
                            and set(candidate_verdict.fact_ids).issubset(set(proposal.used_fact_ids))
                            and set(candidate_verdict.relation_ids).issubset(set(proposal.used_relation_ids))
                            and set(candidate_verdict.span_ids).issubset(set(selected_span_ids))
                        )
                        allowed_fields = {
                            "reader_subject", "transformation", "inputs",
                            "outputs", "conditions", "boundary",
                        }
                        reported_fields = set(candidate_verdict.supported_fields) | set(
                            candidate_verdict.unsupported_fields
                        )
                        fields_closed = (
                            reported_fields.issubset(allowed_fields)
                            and required_fields.issubset(
                                set(candidate_verdict.supported_fields)
                            )
                        )
                        direct_support_bound = bool(
                            candidate_verdict.claim_ids
                            and candidate_verdict.fact_ids
                            and candidate_verdict.span_ids
                        )
                        if ids_closed and reported_fields.issubset(allowed_fields):
                            if candidate_verdict.status == "entailed" and (
                                not fields_closed or not direct_support_bound
                            ):
                                candidate_verdict = candidate_verdict.model_copy(update={
                                    "status": "partial",
                                    "unsupported_fields": tuple(sorted(
                                        required_fields - set(candidate_verdict.supported_fields)
                                    )),
                                    "rationale": (
                                        candidate_verdict.rationale
                                        + " Entailment lacked complete semantic-field or direct evidence bindings."
                                    ).strip(),
                                })
                            evidence_verdict = candidate_verdict
                            evidence_status = candidate_verdict.status
                            evidence_verdicts.append(candidate_verdict)
                if evidence_judge_failure:
                    gaps.append(TypedPropositionGapV1(
                        gap_id=_stable_id(
                            "PG", cluster.cluster_id, proposition_id, "evidence_judge_failed"
                        ),
                        cluster_id=cluster.cluster_id,
                        reason="evidence_judge_failed",
                        detail=evidence_judge_failure,
                        source_obligation_ids=cluster.obligation_ids,
                    ))
            may_enter_verified = (
                cluster.origin == "repository_evidence"
                and cluster.evidence_lane == "repository_verified"
                and (
                    evidence_status == "entailed"
                    or (evidence_judge is None and not require_evidence_judge)
                )
            )
            needs_caveat = partial or candidate_only or (
                cluster.origin == "repository_evidence" and not may_enter_verified
            )
            propositions.append(MethodPropositionV1(
            proposition_id=proposition_id,
            writing_role=classify_proposition_writing_role(
                origin=cluster.origin,
                conditions=proposal.conditions,
                bound_fact_roles=tuple(
                    classify_fact_writing_role(fact)
                    for fact in facts.facts
                    if fact.fact_id in proposal.used_fact_ids
                ),
            ),
            origin=cluster.origin,
            evidence_lane=cluster.evidence_lane,
            status="partial" if (partial or candidate_only) else "ready",
            source_obligation_ids=cluster.obligation_ids,
            may_enter_verified=may_enter_verified,
            evidence_verdict=evidence_status,
            requires_caveat=needs_caveat,
            reader_subject=proposal.reader_subject,
            transformation=proposal.transformation,
            inputs=proposal.inputs,
            outputs=proposal.outputs,
            conditions=proposal.conditions,
            boundary=proposal.boundary,
            paper_terms=proposal.paper_terms,
            implementation_binding_terms=proposal.implementation_binding_terms,
            required_qualifiers=selected_qualifiers,
            immutable_numeric_tokens=tuple(_NUMBER.findall(
                source_text
                if cluster.origin == "author_intent"
                else " ".join((
                    proposal.reader_subject,
                    proposal.transformation,
                    *proposal.inputs,
                    *proposal.outputs,
                    *proposal.conditions,
                    proposal.boundary,
                    *proposal.paper_terms,
                ))
            )),
            immutable_formula_tokens=tuple(match.group(0) for match in _FORMULA.finditer(source_text)),
            required_configuration_ids=selected_configuration_ids,
            section_hints=cluster.section_hints,
            missing_or_uncertain_parts=(
                tuple(dict.fromkeys((
                    *cluster.uncertainty_notes,
                    *([proposal.boundary] if proposal.boundary.strip() else []),
                )))
                if candidate_only else ()
            ),
            ))
            bindings.append(PropositionBindingV1(
                proposition_id=proposition_id,
                claim_ids=proposal.used_claim_ids,
                fact_ids=proposal.used_fact_ids,
                relation_ids=proposal.used_relation_ids,
                span_ids=selected_span_ids,
                equation_ids=selected_equation_ids,
                configuration_ids=selected_configuration_ids,
                source_obligation_ids=cluster.obligation_ids,
                source_digests=tuple(dict.fromkeys((
                    cluster.content_digest,
                    *(claim.canonical_identity for claim in selected_claims),
                    *(
                        fact.exact_source_digest for fact in facts.facts
                        if fact.fact_id in selected_fact_ids
                    ),
                ))),
            ))
    sidecar = PropositionBindingSidecarV1(
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
        bindings=tuple(bindings),
    )
    proposition_set = MethodPropositionSetV1(
        repo_snapshot_id=facts.repo_snapshot_id,
        project_tree_hash=facts.project_tree_hash,
        propositions=tuple(propositions),
        evidence_verdicts=tuple(evidence_verdicts),
        gaps=tuple(gaps),
        binding_sidecar_digest=sidecar.content_digest if propositions else "",
    )
    return proposition_set, sidecar, clusters


def _merge_proposition_repair(
    *,
    preserved: tuple[MethodPropositionProposalV1, ...],
    repaired: tuple[MethodPropositionProposalV1, ...],
) -> tuple[MethodPropositionProposalV1, ...]:
    """Merge a bounded owner repair without dropping prior valid concepts."""

    merged: list[MethodPropositionProposalV1] = []
    seen: set[tuple[Any, ...]] = set()
    seen_source_surfaces: set[tuple[str, ...]] = set()
    for proposal in (*preserved, *repaired):
        source_surface = tuple(proposal.source_statement_fragments)
        if source_surface and source_surface in seen_source_surfaces:
            continue
        key = (
            proposal.reader_subject.casefold(),
            proposal.transformation.casefold(),
            tuple(item.casefold() for item in proposal.inputs),
            tuple(item.casefold() for item in proposal.outputs),
            tuple(item.casefold() for item in proposal.conditions),
            proposal.boundary.casefold(),
            tuple(proposal.source_statement_fragments),
        )
        if key in seen:
            continue
        seen.add(key)
        if source_surface:
            seen_source_surfaces.add(source_surface)
        merged.append(proposal)
    return tuple(merged)
