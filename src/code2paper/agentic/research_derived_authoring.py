"""Research-derived Method authoring contracts and pure compilers.

This module is the narrow bridge between the research graph and the
publication surface.  It deliberately does not read a repository or invent
prose.  It only projects already frozen graph/evidence objects into
content-addressed dossier and derivation records; missing links remain typed
gaps.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code2paper.agentic.method_argument_brief_models import (
    ClaimStrengthV1,
    DerivationKindV1,
    PublicationFieldCandidateV1,
)


SurfaceModeV1 = Literal[
    "repository_statement",
    "author_specification",
    "mismatch_statement",
    "scoped_limitation",
    "omit_and_review",
]

_RELATION_ORDER = {
    "NEXT_CONTROL": 0,
    "CALLS": 1,
    "RETURNS_TO": 2,
    "DATA_DEPENDS_ON": 3,
    "READS_FROM": 4,
    "WRITES_TO": 5,
    "CONTROL_DEPENDS_ON": 6,
    "TRUE_BRANCH": 7,
    "FALSE_BRANCH": 8,
    "CONTAINS": 9,
    "CONFIGURED_BY": 10,
}
_CALL_RELATIONS = frozenset({"CALLS", "RETURNS_TO", "IMPLEMENTS", "OVERRIDES"})
_DATA_RELATIONS = frozenset({"DATA_DEPENDS_ON", "READS_FROM", "WRITES_TO", "ALIAS_OF"})
_CONTROL_RELATIONS = frozenset({"NEXT_CONTROL", "CONTROL_DEPENDS_ON", "TRUE_BRANCH", "FALSE_BRANCH"})
_INTERNAL_AUDIT_TERMS = re.compile(
    r"\b(?:audit|callback|sidecar|pending|unverified|validation\s+status|"
    r"repository\s+evidence|formalization\s+pending|typed\s+gap)\b",
    re.I,
)
_NON_TARGET_CONTEXT = re.compile(
    r"(?:^|[/_.:-])(?:baseline|comparand|competitor|evaluation|benchmark|"
    r"metrics?|ablation|tests?|test_suite|config(?:uration)?|settings?)"
    r"(?:$|[/_.:-])",
    re.I,
)


def _digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ids(values: Any) -> tuple[str, ...]:
    if values is None or isinstance(values, (str, bytes, Mapping)):
        return ()
    try:
        return tuple(dict.fromkeys(_text(item) for item in values if _text(item)))
    except TypeError:
        return ()


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _dump(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _source_digest(value: Any) -> str:
    """Return the frozen digest of an upstream research artifact.

    Upstream V1/V2/V3 models normally expose ``content_digest``.  Small
    adapter payloads used by tests or legacy integrations may not, so use a
    deterministic structural digest as a conservative fallback.  The digest
    is provenance metadata only; it never turns an unbound object into
    repository evidence.
    """

    if value is None:
        return ""
    existing = _text(_get(value, "content_digest"))
    if existing:
        return existing
    if isinstance(value, (list, tuple)):
        payload = [
            _dump(item) if not isinstance(item, (str, int, float, bool, type(None))) else item
            for item in value
        ]
    else:
        payload = _dump(value) or value
    try:
        return _digest(payload)
    except TypeError:
        return _digest(str(payload))


def _paragraphs(plan: Any) -> tuple[Any, ...]:
    sections = _get(plan, "sections", ()) or ()
    if isinstance(plan, Mapping) and "paragraphs" in plan:
        sections = (plan,)
    result: list[Any] = []
    for section in sections:
        result.extend(_get(section, "paragraphs", ()) or ())
    return tuple(result)


def _section_for_paragraph(plan: Any, paragraph_id: str) -> Any | None:
    for section in _get(plan, "sections", ()) or ():
        if any(_text(_get(row, "paragraph_id")) == paragraph_id for row in _get(section, "paragraphs", ()) or ()):
            return section
    if _text(_get(plan, "paragraph_id")) == paragraph_id:
        return plan
    return None


def _target_ids_for_paragraph(paragraph: Any) -> tuple[str, ...]:
    return _ids(
        (
            *(_get(paragraph, "required_facet_ids", ()) or ()),
            *(_get(paragraph, "required_field_candidate_ids", ()) or ()),
            *(_get(paragraph, "required_publication_slot_ids", ()) or ()),
            *(_get(paragraph, "ordered_semantic_slot_ids", ()) or ()),
            *(_get(paragraph, "required_edge_ids", ()) or ()),
            *(_get(paragraph, "formula_obligation_ids", ()) or ()),
        )
    )


def _facet_ids_for_paragraph(paragraph: Any, field_candidates: Iterable[Any]) -> tuple[str, ...]:
    facet_ids = list(_ids(_get(paragraph, "required_facet_ids", ())))
    candidate_ids = set(_ids(_get(paragraph, "required_field_candidate_ids", ())))
    for candidate in field_candidates:
        if _text(_get(candidate, "candidate_id")) in candidate_ids:
            facet_id = _text(_get(candidate, "facet_id"))
            if facet_id:
                facet_ids.append(facet_id)
    return tuple(dict.fromkeys(facet_ids))


def _field_candidates_by_id(candidates: Iterable[Any]) -> dict[str, Any]:
    return {
        _text(_get(item, "candidate_id")): item
        for item in candidates
        if _text(_get(item, "candidate_id"))
    }


def _facets_by_id(facets: Iterable[Any]) -> dict[str, Any]:
    return {
        _text(_get(item, "facet_id")): item
        for item in facets
        if _text(_get(item, "facet_id"))
    }


def _facts_by_id(facts: Any) -> dict[str, Any]:
    values = _get(facts, "facts", facts if isinstance(facts, (list, tuple)) else ()) or ()
    return {_text(_get(item, "fact_id")): item for item in values if _text(_get(item, "fact_id"))}


def _claims_by_id(claims: Any) -> dict[str, Any]:
    values = _get(claims, "claims", claims if isinstance(claims, (list, tuple)) else ()) or ()
    return {_text(_get(item, "claim_id")): item for item in values if _text(_get(item, "claim_id"))}


def _equations_by_id(equations: Any) -> dict[str, Any]:
    values = _get(equations, "equations", equations if isinstance(equations, (list, tuple)) else ()) or ()
    return {_text(_get(item, "equation_id")): item for item in values if _text(_get(item, "equation_id"))}


def _graph_parts(graph: Any) -> tuple[dict[str, Any], dict[str, Any], tuple[Any, ...]]:
    nodes = {
        _text(_get(item, "node_id")): item
        for item in (_get(graph, "nodes", ()) or ())
        if _text(_get(item, "node_id"))
    }
    relations = {
        _text(_get(item, "relation_id")): item
        for item in (_get(graph, "relations", ()) or ())
        if _text(_get(item, "relation_id"))
    }
    unresolved = tuple(_get(graph, "unresolved_relations", ()) or ())
    return nodes, relations, unresolved


def _relation_endpoint(relation: Any, side: str, nodes: Mapping[str, Any]) -> str:
    node_key = f"{side}_node_id"
    symbol_key = f"{side}_symbol_id"
    node_id = _text(_get(relation, node_key))
    if node_id in nodes:
        return node_id
    symbol_id = _text(_get(relation, symbol_key))
    if symbol_id:
        for node_id, node in nodes.items():
            if _text(_get(node, "symbol_id")) == symbol_id:
                return node_id
    return node_id or symbol_id


def _node_anchor_ids(
    *,
    node: Any,
    candidate_spans: set[str],
    candidate_symbols: set[str],
) -> bool:
    span = _text(_get(node, "source_span_id"))
    symbol = _text(_get(node, "symbol_id"))
    return bool(
        (span and span in candidate_spans)
        or (symbol and symbol in candidate_symbols)
    )


def _node_is_non_target(
    node: Any, *, scope_target: set[str] | None = None
) -> bool:
    """Recognize generic evaluation/comparand/config context, never by project name."""

    symbol_id = _text(_get(node, "symbol_id"))
    if symbol_id in (scope_target or set()):
        return False
    context = " ".join(
        _text(_get(node, name))
        for name in ("symbol_id", "operation_id", "predicate")
    )
    return bool(_NON_TARGET_CONTEXT.search(context))


def _shortest_connected_subgraph(
    nodes: Mapping[str, Any],
    relations: Mapping[str, Any],
    seed_ids: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Connect seed nodes using only typed graph relations.

    The graph is treated as undirected for finding a minimal evidence path;
    the original relation direction is retained in the dossier.  This avoids
    requiring every language adapter to expose the same edge orientation.
    """

    seeds = tuple(dict.fromkeys(item for item in seed_ids if item in nodes))
    if not seeds:
        return (), ()
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for relation_id, relation in relations.items():
        source = _relation_endpoint(relation, "source", nodes)
        target = _relation_endpoint(relation, "target", nodes)
        if source not in nodes or target not in nodes or source == target:
            continue
        adjacency[source].append((target, relation_id))
        adjacency[target].append((source, relation_id))
    selected_nodes: set[str] = {seeds[0]}
    selected_relations: set[str] = set()
    for target_seed in seeds[1:]:
        queue: deque[str] = deque([next(iter(selected_nodes))])
        predecessor: dict[str, tuple[str, str] | None] = {next(iter(selected_nodes)): None}
        # Multi-source search keeps the path to the already selected component.
        queue = deque(selected_nodes)
        predecessor = {item: None for item in selected_nodes}
        while queue and target_seed not in predecessor:
            current = queue.popleft()
            for neighbour, relation_id in sorted(
                adjacency.get(current, ()),
                key=lambda item: (_RELATION_ORDER.get(_text(_get(relations[item[1]], "kind")).upper(), 99), item[1]),
            ):
                if neighbour in predecessor:
                    continue
                predecessor[neighbour] = (current, relation_id)
                queue.append(neighbour)
        if target_seed not in predecessor:
            continue
        cursor = target_seed
        selected_nodes.add(cursor)
        while predecessor.get(cursor) is not None:
            previous, relation_id = predecessor[cursor]  # type: ignore[misc]
            selected_nodes.add(previous)
            selected_relations.add(relation_id)
            cursor = previous
    # Keep all typed edges entirely inside the selected node component.  This
    # retains control/data context needed for a multi-step operation without
    # turning the dossier into a section-wide fact union.
    for relation_id, relation in relations.items():
        source = _relation_endpoint(relation, "source", nodes)
        target = _relation_endpoint(relation, "target", nodes)
        if source in selected_nodes and target in selected_nodes:
            selected_relations.add(relation_id)
    return tuple(sorted(selected_nodes)), tuple(sorted(selected_relations))


class ResearchMechanismDossierV1(BaseModel):
    """A connected, frozen research view for one paragraph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    dossier_id: str
    section_id: str
    paragraph_id: str
    facet_ids: tuple[str, ...] = Field(default_factory=tuple)
    author_question: str = ""
    author_statements: tuple[str, ...] = Field(default_factory=tuple)
    entry_symbol_ids: tuple[str, ...] = Field(default_factory=tuple)
    ordered_operation_node_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    call_path_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    data_flow_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    control_flow_relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    operation_atoms: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    configuration_bindings: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    default_activation: Literal["active", "inactive", "conditional", "unknown"] = "unknown"
    active_path_conditions: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_relations: tuple[str, ...] = Field(default_factory=tuple)
    exact_span_ids: tuple[str, ...] = Field(default_factory=tuple)
    exact_excerpts: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    contradiction_ids: tuple[str, ...] = Field(default_factory=tuple)
    source_digests: dict[str, str] = Field(default_factory=dict)
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "ResearchMechanismDossierV1":
        for name in (
            "facet_ids", "entry_symbol_ids", "ordered_operation_node_ids",
            "relation_ids", "call_path_relation_ids", "data_flow_relation_ids",
            "control_flow_relation_ids", "active_path_conditions",
            "unresolved_relations", "exact_span_ids", "fact_ids",
            "equation_ids", "contradiction_ids",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"dossier contains duplicate {name}")
        if not self.dossier_id.strip() or not self.section_id.strip() or not self.paragraph_id.strip():
            raise ValueError("research dossier requires dossier, section, and paragraph ids")
        if set(self.call_path_relation_ids) - set(self.relation_ids):
            raise ValueError("call-path relations must be in relation_ids")
        if set(self.data_flow_relation_ids) - set(self.relation_ids):
            raise ValueError("data-flow relations must be in relation_ids")
        if set(self.control_flow_relation_ids) - set(self.relation_ids):
            raise ValueError("control-flow relations must be in relation_ids")
        if any(not str(key).strip() or not str(value).strip() for key, value in self.source_digests.items()):
            raise ValueError("dossier source digests require non-empty keys and values")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class DerivationRecordV1(BaseModel):
    """Provenance and authority ceiling for one atomic field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    derivation_id: str
    section_id: str
    paragraph_id: str
    facet_id: str
    field_name: str
    semantic_atom: str
    derivation_kind: DerivationKindV1
    claim_strength: ClaimStrengthV1
    authority_status: Literal[
        "repository_supported", "repository_partial", "author_intent",
        "intent_code_mismatch", "unresolved",
    ]
    dossier_ids: tuple[str, ...] = Field(default_factory=tuple)
    fact_ids: tuple[str, ...] = Field(default_factory=tuple)
    relation_ids: tuple[str, ...] = Field(default_factory=tuple)
    equation_ids: tuple[str, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    active_conditions: tuple[str, ...] = Field(default_factory=tuple)
    contradiction_ids: tuple[str, ...] = Field(default_factory=tuple)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_allowed: bool = False
    verified_eligible: bool = False
    content_digest: str = ""

    @model_validator(mode="after")
    def _authority_ceiling(self) -> "DerivationRecordV1":
        if not self.derivation_id.strip() or not self.section_id.strip() or not self.paragraph_id.strip():
            raise ValueError("derivation record requires stable location ids")
        if not self.facet_id.strip() or not self.field_name.strip() or not self.semantic_atom.strip():
            raise ValueError("derivation record requires an atomic field")
        if self.claim_strength == "conditional_analysis" and self.candidate_allowed and not self.assumptions:
            raise ValueError("conditional analysis requires explicit assumptions")
        if self.derivation_kind == "semantic_derived":
            if self.authority_status == "repository_supported":
                raise ValueError("semantic derivation cannot be repository_supported")
            if self.verified_eligible:
                raise ValueError("semantic derivation cannot be Verified eligible")
        if self.derivation_kind == "author_intent_only":
            if self.authority_status not in {"author_intent", "intent_code_mismatch", "unresolved"}:
                raise ValueError("author-intent derivation cannot be repository-supported")
            if self.verified_eligible:
                raise ValueError("author-intent derivation cannot be Verified eligible")
        if self.claim_strength in {"empirical", "guarantee"} and self.verified_eligible and not self.fact_ids:
            raise ValueError("empirical/guarantee Verified eligibility requires an evidence binding")
        if self.verified_eligible and (
            self.authority_status != "repository_supported"
            or self.derivation_kind not in {"direct", "static_derived", "formal_derived"}
        ):
            raise ValueError("Verified eligibility exceeds derivation authority")
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class PublicationAuthoringPacketV2(BaseModel):
    """Single ordered Writer-facing packet for one paragraph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "2.0"
    section_id: str
    paragraph_id: str
    rhetorical_goal: str = ""
    ordered_targets: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    dossier_summary: dict[str, Any] = Field(default_factory=dict)
    material_conditions: tuple[str, ...] = Field(default_factory=tuple)
    configuration_state: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    formula_packages: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    closed_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    preceding_paragraph_id: str = ""
    following_paragraph_id: str = ""
    content_digest: str = ""

    @model_validator(mode="after")
    def _closed(self) -> "PublicationAuthoringPacketV2":
        if not self.section_id.strip() or not self.paragraph_id.strip():
            raise ValueError("authoring packet requires section and paragraph ids")
        target_ids = tuple(_text(item.get("target_id")) for item in self.ordered_targets)
        target_ids = tuple(item for item in target_ids if item)
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("authoring packet contains duplicate target ids")
        if set(target_ids) - set(self.closed_target_ids):
            raise ValueError("authoring packet target is outside its closed id set")
        if len(self.closed_target_ids) != len(set(self.closed_target_ids)):
            raise ValueError("authoring packet contains duplicate closed ids")
        for package in self.formula_packages:
            consumer_id = _text(package.get("consumer_paragraph_id"))
            if consumer_id and consumer_id != self.paragraph_id:
                raise ValueError(
                    "authoring packet formula package escapes its consumer paragraph"
                )
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


class CandidateAuthorityValidationV1(BaseModel):
    """Candidate-only surface validation; it never authorizes Verified."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    status: Literal["passed", "warnings", "error"] = "error"
    violations: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    candidate_sentence_count: int = 0
    internal_audit_term_count: int = 0
    content_digest: str = ""

    @model_validator(mode="after")
    def _digest(self) -> "CandidateAuthorityValidationV1":
        payload = self.model_dump(mode="json", exclude={"content_digest"})
        object.__setattr__(self, "content_digest", _digest(payload))
        return self


def _candidate_surface_mode(record: DerivationRecordV1) -> SurfaceModeV1:
    if record.authority_status == "repository_supported":
        return "repository_statement"
    if record.authority_status == "intent_code_mismatch":
        return "mismatch_statement" if record.contradiction_ids else "omit_and_review"
    if record.authority_status == "author_intent":
        return "author_specification"
    if record.claim_strength == "conditional_analysis" and record.assumptions:
        return "scoped_limitation"
    return "omit_and_review"


def _claim_strength(field_name: str, atom: str) -> ClaimStrengthV1:
    text = f"{field_name} {atom}".casefold()
    if any(token in text for token in ("guarantee", "stable", "robust", "convergen", "lipschitz")):
        return "guarantee"
    if any(token in text for token in ("accuracy", "speed", "runtime", "performance", "improvement", "competitive")):
        return "empirical"
    if any(token in text for token in ("condition", "when ", "if ", "under ", "complexity")):
        return "conditional_analysis"
    if any(token in text for token in ("operation", "transform", "input", "output", "state", "data")):
        return "structural"
    return "descriptive"


def _relevant_field_binding(alignment: Any, field_name: str) -> Any | None:
    for binding in _get(alignment, "field_bindings", ()) or ():
        if _text(_get(binding, "field_name")).casefold() == field_name.casefold():
            return binding
    return None


def _dossier_for_field(
    dossiers: Iterable[ResearchMechanismDossierV1],
    *,
    facet_id: str,
    paragraph_id: str,
) -> ResearchMechanismDossierV1 | None:
    for dossier in dossiers:
        if dossier.paragraph_id == paragraph_id and facet_id in dossier.facet_ids:
            return dossier
    return next(
        (item for item in dossiers if item.paragraph_id == paragraph_id),
        None,
    )


def build_research_mechanism_dossiers(
    *,
    plan: Any,
    facets: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    behavior_graph: Any | None = None,
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    implementation_scope: Any | None = None,
) -> tuple[ResearchMechanismDossierV1, ...]:
    """Build one minimal connected dossier for each mechanism-heavy paragraph."""

    equation_by_id = _equations_by_id(equations)
    facet_by_id = _facets_by_id(facets)
    candidate_items = tuple(field_candidates)
    candidate_by_id = _field_candidates_by_id(candidate_items)
    fact_by_id = _facts_by_id(facts)
    claim_by_id = _claims_by_id(claims)
    graph_nodes, graph_relations, unresolved = _graph_parts(behavior_graph)
    config_values = tuple(_get(configurations, "claims", configurations if isinstance(configurations, (list, tuple)) else ()) or ())
    packet_values = tuple(_get(evidence_packets, "packets", evidence_packets if isinstance(evidence_packets, (list, tuple)) else ()) or ())
    scope_entries = set(_ids(_get(implementation_scope, "target_entry_symbol_ids", ())))
    scope_target = set(
        _ids(_get(implementation_scope, "target_core_symbol_ids", ()))
        + _ids(_get(implementation_scope, "target_dependency_symbol_ids", ()))
    )
    source_digests = {
        key: digest
        for key, value in (
            ("behavior_graph", behavior_graph),
            ("facts", facts),
            ("claims", claims),
            ("equations", equations),
            ("configurations", configurations),
            ("evidence_packets", evidence_packets),
            ("implementation_scope", implementation_scope),
        )
        if (digest := _source_digest(value))
    }
    dossiers: list[ResearchMechanismDossierV1] = []
    for paragraph in _paragraphs(plan):
        paragraph_id = _text(_get(paragraph, "paragraph_id"))
        if not paragraph_id:
            continue
        section = _section_for_paragraph(plan, paragraph_id)
        section_id = _text(_get(section, "section_id"))
        facet_ids = _facet_ids_for_paragraph(paragraph, candidate_items)
        formula_ids = set(_ids(_get(paragraph, "formula_obligation_ids", ())))
        relevant_candidates = [
            candidate_by_id[item]
            for item in _ids(_get(paragraph, "required_field_candidate_ids", ()))
            if item in candidate_by_id
        ]
        non_target_facet_ids = {
            _text(_get(candidate, "facet_id"))
            for candidate in relevant_candidates
            if set(_ids(_get(candidate, "ownership_roles", ())))
            and set(_ids(_get(candidate, "ownership_roles", ()))).issubset({
                "comparand", "evaluation", "configuration",
            })
        }
        facet_ids = tuple(
            facet_id for facet_id in facet_ids if facet_id not in non_target_facet_ids
        )
        if not facet_ids and not formula_ids and not _get(paragraph, "required_field_candidate_ids", ()):
            continue
        fact_ids: set[str] = set()
        claim_ids: set[str] = set()
        equation_ids: set[str] = set()
        span_ids: set[str] = set()
        exact_excerpts: list[str] = []
        candidate_symbols: set[str] = set()
        contradiction_ids: set[str] = set()
        for candidate in relevant_candidates:
            fact_ids.update(_ids(_get(candidate, "bound_fact_ids", ())))
            claim_ids.update(_ids(_get(candidate, "bound_claim_ids", ())))
            equation_ids.update(_ids(_get(candidate, "bound_equation_ids", ())))
            span_ids.update(_ids(_get(candidate, "bound_span_ids", ())))
            exact_excerpts.extend(_ids(_get(candidate, "exact_excerpts", ())))
            contradiction_ids.update(_ids(_get(candidate, "contradiction_ids", ())))
        for facet_id in facet_ids:
            facet = facet_by_id.get(facet_id)
            # Semantic fields and author statements describe intent; they are
            # not copied into the frozen source-excerpt channel.
            contradiction_ids.update(_ids(_get(facet, "contradiction_ids", ())))
        for fact_id in tuple(fact_ids):
            fact = fact_by_id.get(fact_id)
            span_ids.update(_ids(_get(fact, "direct_span_ids", ())) + _ids(_get(fact, "relation_span_ids", ())))
            claim_ids.update(_ids(_get(fact, "claim_ids", ())))
            fact_subject = _text(_get(fact, "subject"))
            if fact_subject:
                candidate_symbols.add(fact_subject)
            candidate_symbols.update(_ids(_get(fact, "scope_symbol_ids", ())))
        for claim_id in tuple(claim_ids):
            claim = claim_by_id.get(claim_id)
            fact_ids.update(_ids(_get(claim, "fact_ids", ())))
            span_ids.update(_ids(_get(claim, "span_ids", ())))
            contradiction_ids.update(_ids(_get(claim, "contradiction_ids", ())))
        for formula_id in formula_ids:
            formula_key = formula_id
            if formula_key.startswith("formula:"):
                formula_key = formula_key[len("formula:"):]
            if formula_key.startswith("equation:"):
                formula_key = formula_key[len("equation:"):]
            for equation_id in (formula_id, formula_key, f"equation:{formula_key}"):
                equation = equation_by_id.get(equation_id)
                if equation is not None:
                    equation_ids.add(_text(_get(equation, "equation_id")))
                    fact_ids.update(_ids(_get(equation, "fact_ids", ())))
                    span_ids.update(_ids(_get(equation, "span_ids", ())))
        for packet in packet_values:
            packet_spans = set(_ids(
                _get(packet, "anchor_span_ids", ())
            ) + _ids(_get(packet, "relation_span_ids", ())) + _ids(_get(packet, "semantic_span_ids", ())))
            if span_ids.intersection(packet_spans):
                for span in _get(packet, "spans", ()) or ():
                    excerpt = _text(_get(span, "exact_excerpt") or _get(span, "text"))
                    if excerpt:
                        exact_excerpts.append(excerpt)

        for candidate in relevant_candidates:
            for excerpt in _ids(_get(candidate, "exact_excerpts", ())):
                # A stable symbol is sometimes supplied as the excerpt by a
                # language adapter.  Accept only an exact span/symbol match;
                # prose excerpts remain frozen text and cannot seed arbitrary
                # graph nodes by fuzzy matching.
                for node in graph_nodes.values():
                    if excerpt in {
                        _text(_get(node, "source_span_id")),
                        _text(_get(node, "symbol_id")),
                    }:
                        symbol = _text(_get(node, "symbol_id"))
                        if symbol:
                            candidate_symbols.add(symbol)
        # Filter the graph before path search.  Removing an evaluation or
        # configuration node after BFS could leave a dossier with a relation
        # path that is no longer connected, or silently use that node as a
        # bridge between two implementation nodes.
        eligible_nodes = {
            node_id: node
            for node_id, node in graph_nodes.items()
            if not _node_is_non_target(node, scope_target=scope_target)
        }
        eligible_relations = {
            relation_id: relation
            for relation_id, relation in graph_relations.items()
            if (
                _relation_endpoint(relation, "source", eligible_nodes) in eligible_nodes
                and _relation_endpoint(relation, "target", eligible_nodes) in eligible_nodes
            )
        }
        seed_ids = [
            node_id for node_id, node in eligible_nodes.items()
            if (
                _node_anchor_ids(
                    node=node,
                    candidate_spans=span_ids,
                    candidate_symbols=candidate_symbols,
                )
                or (
                    _text(_get(node, "symbol_id")) in scope_target
                )
            )
        ]
        if not seed_ids and scope_entries:
            seed_ids = [
                node_id for node_id, node in eligible_nodes.items()
                if _text(_get(node, "symbol_id")) in scope_entries
            ]
        selected_node_ids, selected_relation_ids = _shortest_connected_subgraph(
            eligible_nodes, eligible_relations, seed_ids
        )
        selected_node_set = set(selected_node_ids)
        selected_relation_ids = tuple(
            relation_id
            for relation_id in selected_relation_ids
            if _relation_endpoint(eligible_relations[relation_id], "source", eligible_nodes)
            in selected_node_set
            and _relation_endpoint(eligible_relations[relation_id], "target", eligible_nodes)
            in selected_node_set
        )
        if (
            not selected_node_ids and (fact_ids or claim_ids or equation_ids)
        ) or set(seed_ids) - selected_node_set:
            unresolved_ids = ["missing_connected_behavior_subgraph"]
        else:
            unresolved_ids = []
        operation_nodes = [
            eligible_nodes[item] for item in selected_node_ids if item in eligible_nodes
        ]
        selected_relations = [
            eligible_relations[item]
            for item in selected_relation_ids
            if item in eligible_relations
        ]
        selected_relations.sort(key=lambda relation: (
            _RELATION_ORDER.get(_text(_get(relation, "kind")).upper(), 99),
            _text(_get(relation, "relation_id")),
        ))
        operation_nodes.sort(key=lambda node: (
            min(
                (
                    _RELATION_ORDER.get(_text(_get(relation, "kind")).upper(), 99)
                    for relation in selected_relations
                    if _relation_endpoint(relation, "source", eligible_nodes) == _text(_get(node, "node_id"))
                    or _relation_endpoint(relation, "target", eligible_nodes) == _text(_get(node, "node_id"))
                ),
                default=99,
            ),
            _text(_get(node, "source_span_id")),
            _text(_get(node, "node_id")),
        ))
        relation_ids = tuple(_text(_get(item, "relation_id")) for item in selected_relations if _text(_get(item, "relation_id")))
        relation_by_id = {
            _text(_get(item, "relation_id")): item
            for item in selected_relations
            if _text(_get(item, "relation_id"))
        }
        call_ids = tuple(item for item in relation_ids if _text(_get(relation_by_id[item], "kind")).upper() in _CALL_RELATIONS)
        data_ids = tuple(item for item in relation_ids if _text(_get(relation_by_id[item], "kind")).upper() in _DATA_RELATIONS)
        control_ids = tuple(item for item in relation_ids if _text(_get(relation_by_id[item], "kind")).upper() in _CONTROL_RELATIONS)
        unresolved_ids.extend(
            _text(_get(item, "relation_id"))
            for item in unresolved
            if _text(_get(item, "relation_id"))
            and (
                _text(_get(item, "source_node_id")) in selected_node_ids
                or _text(_get(item, "source_symbol_id")) in scope_target
            )
        )
        configuration_bindings: list[dict[str, Any]] = []
        active_conditions: list[str] = []
        for config in config_values:
            config_spans = set(_ids(_get(config, "definition_span_ids", ())) + _ids(_get(config, "entrypoint_span_ids", ())))
            config_facts = set(_ids(_get(config, "source_fact_ids", ())))
            config_id = _text(_get(config, "configuration_id"))
            paragraph_config_ids = set(_ids(_get(paragraph, "configuration_ids", ())))
            if (
                config_spans.intersection(span_ids)
                or config_facts.intersection(fact_ids)
                or config_id in paragraph_config_ids
            ):
                configuration_bindings.append(_dump(config))
                active_conditions.extend(_ids(_get(config, "conditions", ())))
        active_conditions.extend(
            _text(_get(node, "guard"))
            for node in operation_nodes
            if _text(_get(node, "guard"))
        )
        activation = "unknown"
        if configuration_bindings:
            active_values = [item.get("active") for item in configuration_bindings]
            if any(value is False for value in active_values):
                activation = "inactive"
            elif any(_text(item.get("state")) == "unresolved" for item in configuration_bindings):
                activation = "unknown"
            elif active_conditions:
                activation = "conditional"
            else:
                activation = "active"
        # Absence of a bound configuration is not evidence that defaults are
        # active.  Leave it unknown until the configuration research lane
        # contributes a frozen binding.
        entry_symbols = tuple(dict.fromkeys(
            _text(_get(node, "symbol_id"))
            for node in operation_nodes
            if _text(_get(node, "symbol_id")) in scope_entries
        )) or tuple(sorted(scope_entries.intersection(
            {_text(_get(node, "symbol_id")) for node in operation_nodes}
        )))
        author_statements = tuple(dict.fromkeys(
            _text(_get(facet_by_id.get(facet_id), "exact_source_quote"))
            for facet_id in facet_ids
            if _text(_get(facet_by_id.get(facet_id), "exact_source_quote"))
        ))
        dossier_identity = {
            "section_id": section_id,
            "paragraph_id": paragraph_id,
            "facet_ids": facet_ids,
            "nodes": selected_node_ids,
            "relations": relation_ids,
            "facts": tuple(sorted(fact_ids)),
        }
        dossiers.append(ResearchMechanismDossierV1(
            dossier_id="dossier:" + _digest(dossier_identity)[7:23],
            section_id=section_id,
            paragraph_id=paragraph_id,
            facet_ids=facet_ids,
            author_question=_text(_get(section, "reader_question")) or _text(_get(paragraph, "paragraph_role")),
            author_statements=author_statements,
            entry_symbol_ids=entry_symbols,
            ordered_operation_node_ids=tuple(_text(_get(node, "node_id")) for node in operation_nodes),
            relation_ids=relation_ids,
            call_path_relation_ids=call_ids,
            data_flow_relation_ids=data_ids,
            control_flow_relation_ids=control_ids,
            operation_atoms=tuple(_dump(node) for node in operation_nodes),
            configuration_bindings=tuple(configuration_bindings),
            default_activation=activation,
            active_path_conditions=tuple(dict.fromkeys(active_conditions)),
            unresolved_relations=tuple(dict.fromkeys(unresolved_ids)),
            exact_span_ids=tuple(dict.fromkeys(
                (*span_ids, *(_text(_get(node, "source_span_id")) for node in operation_nodes if _text(_get(node, "source_span_id"))))
            )),
            exact_excerpts=tuple(dict.fromkeys(exact_excerpts)),
            fact_ids=tuple(sorted(fact_ids)),
            equation_ids=tuple(sorted(equation_ids)),
            contradiction_ids=tuple(sorted(contradiction_ids)),
            source_digests=dict(source_digests),
        ))
    return tuple(dossiers)


def build_research_derived_callback_requests(
    *,
    plan: Any,
    dossiers: Iterable[ResearchMechanismDossierV1],
) -> tuple[dict[str, Any], ...]:
    """Create bounded research callbacks for dossier links that remain open.

    This is a routing projection, not a repair or prose generator.  It names
    the paragraph, argument unit, exact unresolved relation labels, and the
    already-frozen symbols/facts that define the next search.  Dynamic or
    missing graph links therefore remain open and cannot be silently treated
    as an implementation fact.
    """

    requests: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for dossier in dossiers:
        unresolved = tuple(
            item for item in (_text(value) for value in dossier.unresolved_relations)
            if item
        )
        if not unresolved:
            continue
        paragraph = next(
            (
                item for item in _paragraphs(plan)
                if _text(_get(item, "paragraph_id")) == dossier.paragraph_id
            ),
            None,
        )
        argument_unit_id = next(
            iter(_ids(_get(paragraph, "argument_unit_ids", ()))),
            dossier.paragraph_id,
        )
        lower_unresolved = " ".join(unresolved).casefold()
        if any(token in lower_unresolved for token in ("config", "activation", "default")):
            move = "configuration_and_branches"
            lane = "configuration_resolved"
        elif any(token in lower_unresolved for token in ("formula", "equation", "deriv")):
            move = "equation_or_derivation"
            lane = "formal_derivation"
        else:
            move = "algorithm_or_data_flow"
            lane = "executable_hard"
        key = (dossier.section_id, argument_unit_id, move)
        if key in seen:
            continue
        seen.add(key)

        terms: list[str] = list(dossier.entry_symbol_ids)
        for atom in dossier.operation_atoms:
            terms.extend(
                _text(atom.get(name))
                for name in ("symbol_id", "operation", "source_span_id")
                if _text(atom.get(name))
            )
        terms = list(dict.fromkeys(item for item in terms if item))[:16]
        unresolved_text = ", ".join(unresolved[:6])
        scope_text = ", ".join(terms[:8])
        question = (
            f"Which bounded repository trace resolves {unresolved_text} for "
            f"paragraph {dossier.paragraph_id}"
            + (f" near {scope_text}" if scope_text else "")
            + "?"
        )
        identity = {
            "section_id": dossier.section_id,
            "paragraph_id": dossier.paragraph_id,
            "argument_unit_id": argument_unit_id,
            "move": move,
            "unresolved": unresolved,
        }
        requests.append({
            "request_id": "research-derived:" + _digest(identity)[7:23],
            "section_id": dossier.section_id,
            "argument_unit_id": argument_unit_id,
            "missing_rhetorical_move": move,
            "exact_question": question,
            "required_authority_lane": lane,
            "candidate_symbols_or_terms": tuple(terms),
            "current_known_facts": tuple(dossier.fact_ids),
            "why_needed_for_reader": (
                "The paragraph's mechanism dossier has an unresolved connected "
                "repository relation; keep the Candidate scoped and leave "
                "Verified closed until the owning lane supplies a validated trace."
            ),
            "priority": "high",
            "status": "open",
            "missing_parts": unresolved,
            "baseline_span_ids": tuple(dossier.exact_span_ids),
            "target_story_node_ids": tuple(dossier.ordered_operation_node_ids),
            "target_formula_obligation_ids": _ids(
                _get(paragraph, "formula_obligation_ids", ())
            ),
        })
    return tuple(requests)


def compile_derivation_records(
    *,
    dossiers: Iterable[ResearchMechanismDossierV1],
    facets: Iterable[Any] = (),
    alignments: Iterable[Any] = (),
    formula_results: Iterable[Any] = (),
) -> tuple[DerivationRecordV1, ...]:
    """Compile field-level provenance without upgrading authority."""

    dossier_items = tuple(dossiers)
    facet_by_id = _facets_by_id(facets)
    alignment_by_id = {
        _text(_get(item, "facet_id")): item
        for item in alignments
        if _text(_get(item, "facet_id"))
    }
    formula_by_facet: dict[str, list[Any]] = defaultdict(list)
    for result in formula_results or ():
        packages = _get(result, "packages", ()) if not isinstance(result, Mapping) else result.get("packages", ())
        for package in packages or ():
            for facet_id in _ids(_get(package, "bound_facet_ids", ())):
                formula_by_facet[facet_id].append(package)
    records: list[DerivationRecordV1] = []
    for dossier in dossier_items:
        for facet_id in dossier.facet_ids:
            facet = facet_by_id.get(facet_id)
            alignment = alignment_by_id.get(facet_id)
            bindings = tuple(_get(alignment, "field_bindings", ()) or ())
            if not bindings:
                semantic_fields = _get(facet, "semantic_fields", {})
                bindings = tuple(
                    {"field_name": name, "status": "unresolved", "polarity": "unknown"}
                    for name in semantic_fields
                ) if isinstance(semantic_fields, Mapping) else ()
            for binding in bindings:
                field_name = _text(_get(binding, "field_name"))
                if not field_name:
                    continue
                semantic_fields = _get(facet, "semantic_fields", {})
                atom = _text(semantic_fields.get(field_name)) if isinstance(semantic_fields, Mapping) else ""
                atom = atom or field_name
                status = _text(_get(binding, "status")) or _text(_get(alignment, "status")) or "unresolved"
                has_evidence = bool(
                    dossier.fact_ids
                    or _ids(_get(binding, "bound_fact_ids", ()))
                    or _ids(_get(binding, "bound_claim_ids", ()))
                    or _ids(_get(binding, "bound_span_ids", ()))
                )
                if status == "entailed" and has_evidence and dossier.ordered_operation_node_ids:
                    kind: DerivationKindV1 = "static_derived" if dossier.relation_ids else "direct"
                    authority = "repository_supported"
                elif status == "partial" and has_evidence:
                    kind = "semantic_derived" if not dossier.relation_ids else "static_derived"
                    authority = "repository_partial"
                elif status == "mismatch":
                    kind = "author_intent_only"
                    authority = "intent_code_mismatch"
                elif _text(_get(facet, "exact_source_quote")):
                    kind = "author_intent_only"
                    authority = "author_intent"
                else:
                    kind = "semantic_derived"
                    authority = "unresolved"
                if formula_by_facet.get(facet_id) and kind in {"direct", "static_derived"}:
                    kind = "formal_derived"
                assumptions = tuple(dict.fromkeys((
                    *dossier.active_path_conditions,
                    *_ids(_get(binding, "active_path_conditions", ())),
                )))
                contradiction_ids = tuple(dict.fromkeys((
                    *dossier.contradiction_ids,
                    *_ids(_get(binding, "contradiction_ids", ())),
                )))
                strength = _claim_strength(field_name, atom)
                candidate_allowed = authority in {"repository_supported", "repository_partial", "author_intent", "intent_code_mismatch"}
                if strength in {"empirical", "guarantee"} and authority not in {"repository_supported", "repository_partial"}:
                    candidate_allowed = True  # Candidate may surface it only as a typed proposal.
                if strength == "conditional_analysis" and not assumptions:
                    candidate_allowed = False
                verified = authority == "repository_supported" and kind in {"direct", "static_derived", "formal_derived"} and strength in {"descriptive", "structural"}
                identity = {
                    "section_id": dossier.section_id,
                    "paragraph_id": dossier.paragraph_id,
                    "facet_id": facet_id,
                    "field_name": field_name,
                    "atom": atom,
                    "dossier": dossier.dossier_id,
                }
                records.append(DerivationRecordV1(
                    derivation_id="derivation:" + _digest(identity)[7:23],
                    section_id=dossier.section_id,
                    paragraph_id=dossier.paragraph_id,
                    facet_id=facet_id,
                    field_name=field_name,
                    semantic_atom=atom,
                    derivation_kind=kind,
                    claim_strength=strength,
                    authority_status=authority,
                    dossier_ids=(dossier.dossier_id,),
                    fact_ids=tuple(dict.fromkeys(
                        (*dossier.fact_ids, *_ids(_get(binding, "bound_fact_ids", ())))
                    )),
                    relation_ids=dossier.relation_ids,
                    equation_ids=tuple(dict.fromkeys(
                        (*dossier.equation_ids, *_ids(_get(binding, "bound_equation_ids", ())))
                    )),
                    assumptions=assumptions,
                    active_conditions=dossier.active_path_conditions,
                    contradiction_ids=contradiction_ids,
                    confidence=min(1.0, 0.55 + 0.08 * len(dossier.ordered_operation_node_ids) + 0.05 * len(dossier.relation_ids)) if has_evidence else 0.2,
                    candidate_allowed=candidate_allowed,
                    verified_eligible=verified,
                ))
    return tuple(records)


def merge_derivations_into_field_candidates(
    *,
    candidates: Iterable[PublicationFieldCandidateV1],
    derivations: Iterable[DerivationRecordV1],
) -> tuple[PublicationFieldCandidateV1, ...]:
    """Attach provenance and select a clean Candidate surface mode."""

    records_by_key: dict[tuple[str, str], list[DerivationRecordV1]] = defaultdict(list)
    for record in derivations:
        records_by_key[(record.facet_id, record.field_name.casefold())].append(record)
    merged: list[PublicationFieldCandidateV1] = []
    for candidate in candidates:
        records = records_by_key.get((candidate.facet_id, candidate.field_name.casefold()), [])
        if not records:
            merged.append(candidate)
            continue
        records = sorted(records, key=lambda item: (-item.confidence, item.derivation_id))
        primary = records[0]
        surface = _candidate_surface_mode(primary)
        bound_ids = bool(
            candidate.bound_claim_ids or candidate.bound_fact_ids
            or candidate.bound_span_ids or candidate.bound_equation_ids
        )
        render_policy = candidate.render_policy
        defer_reason = candidate.defer_reason
        if not primary.candidate_allowed or surface == "omit_and_review":
            render_policy = "deferred"
            defer_reason = defer_reason or "derivation_not_safe_for_clean_candidate_surface"
        elif surface in {"repository_statement", "scoped_limitation"} and not bound_ids:
            render_policy = "deferred"
            defer_reason = "repository_surface_missing_closed_evidence_binding"
            surface = "omit_and_review"
        elif surface == "mismatch_statement" and not primary.contradiction_ids:
            render_policy = "deferred"
            defer_reason = "mismatch_surface_missing_contradiction_binding"
            surface = "omit_and_review"
        merged.append(candidate.model_copy(update={
            "derivation_record_ids": tuple(item.derivation_id for item in records),
            "derivation_kind": primary.derivation_kind,
            "claim_strength": primary.claim_strength,
            "surface_mode": surface,
            "render_policy": render_policy,
            "defer_reason": defer_reason,
        }))
    return tuple(merged)


def validate_candidate_authority(
    *,
    candidate_text: str,
    candidates: Iterable[PublicationFieldCandidateV1] = (),
    derivations: Iterable[DerivationRecordV1] = (),
) -> CandidateAuthorityValidationV1:
    """Validate clean Candidate authority framing without touching Verified."""

    text = str(candidate_text or "")
    violations: list[str] = []
    warnings: list[str] = []
    internal_count = len(_INTERNAL_AUDIT_TERMS.findall(text))
    if internal_count:
        violations.append("candidate_contains_internal_audit_terms")
    derivation_by_id = {item.derivation_id: item for item in derivations}
    sentence_count = sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in re.split(r"(?<=[.!?])\s+|\n+", text)
    )
    for candidate in candidates:
        if candidate.surface_mode in {"repository_statement", "scoped_limitation"} and not (
            candidate.bound_claim_ids or candidate.bound_fact_ids or candidate.bound_span_ids or candidate.bound_equation_ids
        ):
            violations.append(f"{candidate.candidate_id}:repository_surface_without_evidence")
        if candidate.surface_mode == "mismatch_statement" and not any(
            _text(derivation_by_id.get(item, None) and derivation_by_id[item].authority_status) == "intent_code_mismatch"
            and derivation_by_id[item].contradiction_ids
            for item in candidate.derivation_record_ids
        ):
            violations.append(f"{candidate.candidate_id}:mismatch_without_contradiction")
        if candidate.surface_mode == "author_specification" and candidate.derivation_kind != "author_intent_only":
            warnings.append(f"{candidate.candidate_id}:author_surface_derivation_mismatch")
    status: Literal["passed", "warnings", "error"] = "error" if violations else "warnings" if warnings else "passed"
    return CandidateAuthorityValidationV1(
        status=status,
        violations=tuple(dict.fromkeys(violations)),
        warnings=tuple(dict.fromkeys(warnings)),
        candidate_sentence_count=sentence_count,
        internal_audit_term_count=internal_count,
    )


def build_publication_authoring_packets(
    *,
    plan: Any,
    dossiers: Iterable[ResearchMechanismDossierV1] = (),
    derivations: Iterable[DerivationRecordV1] = (),
    candidates: Iterable[PublicationFieldCandidateV1] = (),
    formula_packages_by_section: Mapping[str, Iterable[Any]] | None = None,
) -> dict[str, tuple[PublicationAuthoringPacketV2, ...]]:
    """Build ordered, paragraph-local packets for the prose Writer.

    The packet is an organization and surface-authority contract.  It carries
    no license to invent repository facts; exact evidence remains in the
    dossier and is consumed later by the Binder/transaction gate.
    """

    dossier_items = tuple(dossiers)
    derivation_items = tuple(derivations)
    candidate_by_id = _field_candidates_by_id(candidates)
    derivations_by_key: dict[tuple[str, str], list[DerivationRecordV1]] = defaultdict(list)
    for record in derivation_items:
        derivations_by_key[(record.facet_id, record.field_name.casefold())].append(record)
    packets_by_section: dict[str, tuple[PublicationAuthoringPacketV2, ...]] = {}
    for section in _get(plan, "sections", ()) or ():
        section_id = _text(_get(section, "section_id"))
        paragraphs = tuple(_get(section, "paragraphs", ()) or ())
        if not section_id or not paragraphs:
            continue
        paragraph_ids = tuple(_text(_get(row, "paragraph_id")) for row in paragraphs)
        section_packets: list[PublicationAuthoringPacketV2] = []
        for index, paragraph in enumerate(paragraphs):
            paragraph_id = paragraph_ids[index]
            if not paragraph_id:
                continue
            target_ids = _target_ids_for_paragraph(paragraph)
            required_candidate_ids = set(_ids(_get(paragraph, "required_field_candidate_ids", ())))
            facet_ids = set(_ids(_get(paragraph, "required_facet_ids", ())))
            slot_ids = set(_ids(
                (*(_get(paragraph, "required_publication_slot_ids", ()) or ()),
                 *(_get(paragraph, "ordered_semantic_slot_ids", ()) or ()))
            ))
            edge_ids = set(_ids(_get(paragraph, "required_edge_ids", ())))
            formula_ids = set(_ids(_get(paragraph, "formula_obligation_ids", ())))
            ordered_targets: list[dict[str, Any]] = []
            for target_id in target_ids:
                candidate = candidate_by_id.get(target_id)
                if candidate is not None:
                    records = derivations_by_key.get(
                        (_text(_get(candidate, "facet_id")), _text(_get(candidate, "field_name")).casefold()),
                        [],
                    )
                    ordered_targets.append({
                        "target_id": target_id,
                        "target_kind": "field_candidate",
                        "facet_id": _text(_get(candidate, "facet_id")),
                        "field_name": _text(_get(candidate, "field_name")),
                        "semantic_atom": _text(_get(candidate, "semantic_atom")),
                        "polarity": _text(_get(candidate, "polarity")) or "unknown",
                        "conditions": list(_ids(_get(candidate, "conditions", ()))),
                        "surface_mode": _text(_get(candidate, "surface_mode")) or "omit_and_review",
                        "render_policy": _text(_get(candidate, "render_policy")) or "deferred",
                        "derivation_record_ids": [item.derivation_id for item in records],
                        "claim_strength": (
                            records[0].claim_strength if records else _text(_get(candidate, "claim_strength"))
                        ),
                    })
                else:
                    target_kind = (
                        "facet" if target_id in facet_ids else
                        "slot" if target_id in slot_ids else
                        "edge" if target_id in edge_ids else
                        "formula" if target_id in formula_ids else
                        "target"
                    )
                    ordered_targets.append({
                        "target_id": target_id,
                        "target_kind": target_kind,
                    })
            dossier = next(
                (
                    item for item in dossier_items
                    if item.section_id == section_id and item.paragraph_id == paragraph_id
                ),
                None,
            )
            dossier_summary: dict[str, Any] = {}
            conditions: tuple[str, ...] = ()
            configuration_state: tuple[dict[str, Any], ...] = ()
            if dossier is not None:
                dossier_summary = {
                    "dossier_id": dossier.dossier_id,
                    "facet_ids": list(dossier.facet_ids),
                    "entry_symbol_ids": list(dossier.entry_symbol_ids),
                    "ordered_operation_node_ids": list(dossier.ordered_operation_node_ids),
                    "relation_ids": list(dossier.relation_ids),
                    "call_path_relation_ids": list(dossier.call_path_relation_ids),
                    "data_flow_relation_ids": list(dossier.data_flow_relation_ids),
                    "control_flow_relation_ids": list(dossier.control_flow_relation_ids),
                    "operation_atoms": [dict(item) for item in dossier.operation_atoms],
                    "default_activation": dossier.default_activation,
                    "exact_span_ids": list(dossier.exact_span_ids),
                    "fact_ids": list(dossier.fact_ids),
                    "equation_ids": list(dossier.equation_ids),
                    "contradiction_ids": list(dossier.contradiction_ids),
                    "source_digests": dict(dossier.source_digests),
                    "unresolved_relations": list(dossier.unresolved_relations),
                }
                conditions = dossier.active_path_conditions
                configuration_state = dossier.configuration_bindings
            formula_packages: list[dict[str, Any]] = []
            for package in (formula_packages_by_section or {}).get(section_id, ()):
                package_payload = _dump(package)
                consumer_id = _text(package_payload.get("consumer_paragraph_id"))
                package_obligation_ids = set(_ids(
                    (*(_get(package, "satisfied_obligation_ids", ()) or ()),
                     *((_get(package, "obligation_id"),) if _get(package, "obligation_id") else ()))
                ))
                if consumer_id and consumer_id != paragraph_id:
                    continue
                if not consumer_id and not package_obligation_ids.intersection(formula_ids):
                    continue
                formula_packages.append(package_payload)
            section_packets.append(PublicationAuthoringPacketV2(
                section_id=section_id,
                paragraph_id=paragraph_id,
                rhetorical_goal=_text(_get(paragraph, "paragraph_role")),
                ordered_targets=tuple(ordered_targets),
                dossier_summary=dossier_summary,
                material_conditions=conditions,
                configuration_state=configuration_state,
                formula_packages=tuple(formula_packages),
                closed_target_ids=target_ids,
                preceding_paragraph_id=paragraph_ids[index - 1] if index else "",
                following_paragraph_id=(
                    paragraph_ids[index + 1] if index + 1 < len(paragraph_ids) else ""
                ),
            ))
        packets_by_section[section_id] = tuple(section_packets)
    return packets_by_section


def write_research_derived_artifacts(
    root: str,
    *,
    dossiers: Iterable[ResearchMechanismDossierV1],
    derivations: Iterable[DerivationRecordV1],
) -> dict[str, str]:
    """Persist only the two new content-addressed research artifacts."""

    from pathlib import Path
    from code2paper.core.output_names import method_output

    base = Path(root).expanduser().resolve()
    outputs: dict[str, str] = {}
    dossier_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "items": [item.model_dump(mode="json") for item in tuple(dossiers)],
    }
    dossier_payload["content_digest"] = _digest(dossier_payload)
    derivation_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "items": [item.model_dump(mode="json") for item in tuple(derivations)],
        "source_dossier_digest": dossier_payload["content_digest"],
    }
    derivation_payload["content_digest"] = _digest(derivation_payload)
    for key, payload in (
        ("research_mechanism_dossiers_v1", dossier_payload),
        ("derivation_records_v1", derivation_payload),
    ):
        path = method_output(base, key)
        # Use the repository's atomic writer when available; no prose is
        # synthesized here and an existing artifact is never silently merged.
        from code2paper.agentic.tool_runtime import atomic_write_bytes
        atomic_write_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        outputs[key] = str(path)
    return outputs


__all__ = [
    "CandidateAuthorityValidationV1",
    "DerivationRecordV1",
    "PublicationAuthoringPacketV2",
    "ResearchMechanismDossierV1",
    "build_research_derived_callback_requests",
    "build_research_mechanism_dossiers",
    "build_publication_authoring_packets",
    "compile_derivation_records",
    "merge_derivations_into_field_candidates",
    "validate_candidate_authority",
    "write_research_derived_artifacts",
]
