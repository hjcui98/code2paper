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


def _fact_values(value: Any) -> tuple[str, ...]:
    """Read ordered scalar values from a CodeFact object field."""

    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if value is None or isinstance(value, Mapping):
        return ()
    try:
        return tuple(
            _text(item) for item in value if _text(item)
        )
    except TypeError:
        text = _text(value)
        return (text,) if text else ()


def _fact_source_order(fact: Any) -> tuple[str, int, int, str]:
    """Return a stable source order without treating a span as prose."""

    spans = _ids(
        (*(_get(fact, "direct_span_ids", ()) or ()),
         *(_get(fact, "relation_span_ids", ()) or ()))
    )
    for span in spans:
        match = re.search(r":(\d+):(\d+)$", span)
        if match:
            return (
                _text(_get(fact, "scope")),
                int(match.group(1)),
                int(match.group(2)),
                _text(_get(fact, "fact_id")),
            )
    return (_text(_get(fact, "scope")), 10**9, 10**9, _text(_get(fact, "fact_id")))


def _fact_shape_hints(fact: Any) -> tuple[str, ...]:
    """Keep only explicit shape/type descriptors supplied by the fact."""

    values: list[str] = []
    for name in ("shape_or_type_hints", "shape_hints", "types", "type_hints"):
        values.extend(_fact_values(_get(fact, name, ())))
    # Older CodeFactV1 instances have no dedicated shape field.  Its semantic
    # context is still authoritative, but only entries that explicitly carry
    # a shape/type signal belong in the shape channel.
    for value in _fact_values(_get(fact, "semantic_context", ())):
        lower = value.casefold()
        if (
            "shape" in lower or "dtype" in lower or "dim" in lower
            or re.search(r"\[[^\]]+\]", value)
        ):
            values.append(value)
    return tuple(dict.fromkeys(value for value in values if value))


def _fact_operation_parts(fact: Any) -> tuple[tuple[str, ...], str]:
    """Split CodeFact object values while preserving ``result=`` exactly."""

    values = _fact_values(_get(fact, "object", ()))
    operands: list[str] = []
    result = ""
    for value in values:
        if value.casefold().startswith("result=") and not result:
            result = value.split("=", 1)[1].strip()
            continue
        operands.append(value)
    predicate = _text(_get(fact, "predicate")).casefold()
    if not result and predicate in {"return", "returns", "emits", "outputs", "writes_back"} and operands:
        result = operands.pop()
    return tuple(dict.fromkeys(operands)), result


def compile_code_fact_operation_chain(
    *,
    facts: Any,
    fact_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Compile validated CodeFacts into bounded, source-ordered operations.

    This is intentionally a representation compiler, not a semantic guesser:
    rejected facts and facts without an exact direct/relation span are not
    promoted.  Operations are ordered inside each source ``scope``; separate
    scopes remain separate chains unless a later graph/relation stage supplies
    an explicit connection.
    """

    fact_by_id = _facts_by_id(facts)
    requested = set(_ids(fact_ids))
    selected = [
        fact for fact_id, fact in fact_by_id.items()
        if not requested or fact_id in requested
    ]
    selected.sort(key=_fact_source_order)
    atoms: list[dict[str, Any]] = []
    signatures: list[dict[str, Any]] = []
    span_ids: list[str] = []
    relation_evidence_ids: list[str] = []
    shape_or_type_hints: list[str] = []
    return_value_descriptors: list[str] = []
    diagnostics: list[str] = []
    scopes: list[str] = []
    accepted_fact_ids: list[str] = []
    for fact in selected:
        fact_id = _text(_get(fact, "fact_id"))
        status = _text(_get(fact, "validation_status")) or "supported"
        spans = _ids(
            (*(_get(fact, "direct_span_ids", ()) or ()),
             *(_get(fact, "relation_span_ids", ()) or ()))
        )
        if status != "supported":
            diagnostics.append(f"fact_not_supported:{fact_id}")
            continue
        if not spans:
            diagnostics.append(f"fact_exact_span_missing:{fact_id}")
            continue
        predicate = _text(_get(fact, "predicate"))
        operands, result = _fact_operation_parts(fact)
        conditions = _ids(_get(fact, "conditions", ()))
        scope = _text(_get(fact, "scope"))
        shape_hints = _fact_shape_hints(fact)
        relation_ids = _ids(_get(fact, "relation_evidence_ids", ()))
        if not predicate and not operands and not result:
            diagnostics.append(f"fact_operation_fields_missing:{fact_id}")
            continue
        atom = {
            "atom_id": f"fact-operation:{fact_id}",
            "operation_id": f"fact-operation:{fact_id}",
            "fact_id": fact_id,
            "subject": _text(_get(fact, "subject")),
            "scope": scope,
            "predicate": predicate,
            "operands": list(operands),
            "result": result,
            "guard": conditions[0] if conditions else "",
            "conditions": list(conditions),
            "shape_or_type_hints": list(shape_hints),
            "operation_descriptors": list(_fact_values(
                _get(fact, "semantic_context", ())
            )),
            "relation_evidence_ids": list(relation_ids),
            "span_ids": list(spans),
            "source_span_id": spans[0],
            "chain_scope": scope,
        }
        atoms.append(atom)
        signatures.append({
            "operation_id": atom["operation_id"],
            "fact_id": fact_id,
            "predicate": predicate,
            "operands": list(operands),
            "result": result,
            "conditions": list(conditions),
            "guard": atom["guard"],
            "shape_or_type_hints": list(shape_hints),
            "scope": scope,
            "source_span_id": spans[0],
        })
        shape_or_type_hints.extend(
            value for value in shape_hints if value not in shape_or_type_hints
        )
        if predicate.casefold() in {"return", "returns", "emits", "outputs", "writes_back"}:
            if result and result not in return_value_descriptors:
                return_value_descriptors.append(result)
        accepted_fact_ids.append(fact_id)
        if scope and scope not in scopes:
            scopes.append(scope)
        span_ids.extend(spans)
        relation_evidence_ids.extend(relation_ids)
    if requested:
        for fact_id in sorted(requested - set(fact_by_id)):
            diagnostics.append(f"fact_missing:{fact_id}")
    return {
        "operation_atoms": tuple(atoms),
        "formalizable_signatures": tuple(signatures),
        "fact_ids": tuple(accepted_fact_ids),
        "exact_span_ids": tuple(dict.fromkeys(span_ids)),
        "relation_evidence_ids": tuple(dict.fromkeys(relation_evidence_ids)),
        "shape_or_type_hints": tuple(dict.fromkeys(shape_or_type_hints)),
        "return_value_descriptors": tuple(dict.fromkeys(return_value_descriptors)),
        "scopes": tuple(scopes),
        "diagnostics": tuple(dict.fromkeys(diagnostics)),
    }


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


def _is_logging_or_filtering_excerpt(text: str) -> bool:
    """Identify generic helper, logging, or NER filtering excerpts to deprioritize."""

    lowered = text.casefold()
    if any(marker in lowered for marker in ("logger.", "logging.", "log.info", "log.debug", "log.warning")):
        return True
    if any(marker in text for marker in ("ORDINAL", "CARDINAL", "DATE", "TIME", "MONEY")):
        return True
    return False


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
    formalizable_signatures: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    configuration_bindings: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    default_activation: Literal["active", "inactive", "conditional", "unknown"] = "unknown"
    active_path_conditions: tuple[str, ...] = Field(default_factory=tuple)
    shape_or_type_hints: tuple[str, ...] = Field(default_factory=tuple)
    return_value_descriptors: tuple[str, ...] = Field(default_factory=tuple)
    evidence_readiness: Literal["code_ready", "intent_ready", "blocked"] = "blocked"
    readiness_failures: tuple[str, ...] = Field(default_factory=tuple)
    code_required: bool = False
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
            "readiness_failures", "unresolved_relations", "exact_span_ids", "fact_ids",
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
        if self.evidence_readiness == "code_ready" and self.readiness_failures:
            raise ValueError("code-ready dossier cannot carry readiness failures")
        if self.evidence_readiness == "code_ready" and not self.code_required:
            raise ValueError("code-ready dossier must require code evidence")
        if self.code_required and self.evidence_readiness == "intent_ready" and not self.author_statements:
            raise ValueError("code-required intent-ready dossier needs an author statement")
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
    # This is a Writer-facing organization bound.  It is deliberately kept
    # separate from the closed target/evidence ids so a model can control
    # paragraph density without being asked to reconstruct the transaction.
    expected_sentence_range: tuple[int, int] = (1, 4)
    ordered_targets: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    dossier_summary: dict[str, Any] = Field(default_factory=dict)
    material_conditions: tuple[str, ...] = Field(default_factory=tuple)
    configuration_state: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    formula_packages: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    # Formula text is a closed transaction input.  When a package is present
    # the Writer may consume its placeholder, but it may not author a second
    # equation for the same mechanism.  Empty packets explicitly stay prose
    # only (or return to the Formalizer owner for a typed gap).
    formula_generation_policy: Literal[
        "consume_only", "prose_only_or_request_formalizer"
    ] = "prose_only_or_request_formalizer"
    canonical_formula_package_ids: tuple[str, ...] = Field(default_factory=tuple)
    method_unit: dict[str, Any] = Field(default_factory=dict)
    closed_target_ids: tuple[str, ...] = Field(default_factory=tuple)
    preceding_paragraph_id: str = ""
    following_paragraph_id: str = ""
    content_digest: str = ""

    @model_validator(mode="before")
    @classmethod
    def _infer_formula_policy_for_legacy_packets(cls, value: Any) -> Any:
        """Backfill the policy fields when loading pre-policy artifacts.

        Frozen replay artifacts predating the consume-only contract do not
        carry either field.  Infer the safe value from their already-closed
        package list so loading those packets remains compatible without
        weakening the post-validation contradiction checks below.
        """

        if not isinstance(value, Mapping):
            return value
        row = dict(value)
        packages = tuple(
            item for item in (row.get("formula_packages") or ())
            if isinstance(item, Mapping)
        )
        if "formula_generation_policy" not in row:
            row["formula_generation_policy"] = (
                "consume_only" if packages else "prose_only_or_request_formalizer"
            )
        if "canonical_formula_package_ids" not in row:
            row["canonical_formula_package_ids"] = tuple(
                _text(item.get("package_id"))
                for item in packages
                if _text(item.get("package_id"))
            )
        return row

    @model_validator(mode="after")
    def _closed(self) -> "PublicationAuthoringPacketV2":
        if not self.section_id.strip() or not self.paragraph_id.strip():
            raise ValueError("authoring packet requires section and paragraph ids")
        if (
            len(self.expected_sentence_range) != 2
            or self.expected_sentence_range[0] < 1
            or self.expected_sentence_range[1] < self.expected_sentence_range[0]
        ):
            raise ValueError("authoring packet sentence range must be increasing")
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
        package_ids = tuple(
            _text(package.get("package_id"))
            for package in self.formula_packages
            if _text(package.get("package_id"))
        )
        if len(package_ids) != len(set(package_ids)):
            raise ValueError("authoring packet contains duplicate formula packages")
        if set(self.canonical_formula_package_ids) - set(package_ids):
            raise ValueError(
                "authoring packet canonical formula id is outside its package set"
            )
        if self.formula_packages and self.formula_generation_policy != "consume_only":
            raise ValueError(
                "authoring packet with formula packages must use consume_only policy"
            )
        if not self.formula_packages and self.formula_generation_policy == "consume_only":
            raise ValueError(
                "consume_only formula policy requires a formula package"
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
        return "mismatch_statement" if record.contradiction_ids else "author_specification"
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
    facet_alignments: Iterable[Any] = (),
    field_candidates: Iterable[Any] = (),
    argument_briefs: Any | None = None,
    behavior_graph: Any | None = None,
    facts: Any | None = None,
    claims: Any | None = None,
    equations: Any | None = None,
    configurations: Any | None = None,
    evidence_packets: Any | None = None,
    implementation_scope: Any | None = None,
    require_nonempty: bool = False,
) -> tuple[ResearchMechanismDossierV1, ...]:
    """Build one minimal connected dossier for each mechanism-heavy paragraph.

    Facet alignments are the only bridge from the intent-first authoring lane
    into this compiler.  Their exact spans, field bindings, and operation
    atoms seed the same graph walk as ordinary field candidates.  In the
    production path ``require_nonempty`` makes an empty mechanism dossier a
    hard error; legacy callers keep the historical permissive behavior.
    """

    equation_by_id = _equations_by_id(equations)
    facet_by_id = _facets_by_id(facets)
    candidate_items = tuple(field_candidates)
    candidate_by_id = _field_candidates_by_id(candidate_items)
    brief_values = tuple(
        _get(argument_briefs, "briefs", argument_briefs)
        if argument_briefs is not None else ()
    )
    brief_by_id = {
        _text(_get(item, "brief_id")): item
        for item in brief_values
        if _text(_get(item, "brief_id"))
    }
    alignment_items = tuple(facet_alignments)
    alignment_by_facet_id = {
        _text(_get(item, "facet_id")): item
        for item in alignment_items
        if _text(_get(item, "facet_id"))
    }
    fact_by_id = _facts_by_id(facts)
    fact_ids_by_span: dict[str, set[str]] = defaultdict(set)
    for fact_id, fact in fact_by_id.items():
        for span_id in _ids(
            (*(_get(fact, "direct_span_ids", ()) or ()),
             *(_get(fact, "relation_span_ids", ()) or ()))
        ):
            fact_ids_by_span[span_id].add(fact_id)
    claim_by_id = _claims_by_id(claims)
    graph_nodes, graph_relations, unresolved = _graph_parts(behavior_graph)
    config_values = tuple(_get(configurations, "claims", configurations if isinstance(configurations, (list, tuple)) else ()) or ())
    packet_values = tuple(_get(evidence_packets, "packets", evidence_packets if isinstance(evidence_packets, (list, tuple)) else ()) or ())
    spans_by_id: dict[str, Any] = {}
    spans_by_symbol: dict[str, list[Any]] = defaultdict(list)
    for packet in packet_values:
        for span in _get(packet, "spans", ()) or ():
            span_id = _text(_get(span, "span_id") or _get(span, "evidence_id"))
            if span_id:
                spans_by_id.setdefault(span_id, span)
            sym = _text(_get(span, "symbol") or _get(span, "symbol_id"))
            if sym:
                spans_by_symbol[sym].append(span)
    for alignment in alignment_items:
        for excerpt in _get(alignment, "exact_excerpts", ()) or ():
            span_id = _text(_get(excerpt, "span_id") or _get(excerpt, "source_span_id"))
            if span_id:
                spans_by_id.setdefault(span_id, excerpt)
            sym = _text(_get(excerpt, "symbol") or _get(excerpt, "symbol_id"))
            if sym:
                spans_by_symbol[sym].append(excerpt)
        for binding in _get(alignment, "field_bindings", ()) or ():
            for excerpt in _get(binding, "exact_excerpts", ()) or ():
                span_id = _text(_get(excerpt, "span_id") or _get(excerpt, "source_span_id"))
                if span_id:
                    spans_by_id.setdefault(span_id, excerpt)
                sym = _text(_get(excerpt, "symbol") or _get(excerpt, "symbol_id"))
                if sym:
                    spans_by_symbol[sym].append(excerpt)
    for node in graph_nodes.values():
        span_id = _text(_get(node, "source_span_id"))
        if span_id:
            spans_by_id.setdefault(span_id, node)
        sym = _text(_get(node, "symbol_id"))
        if sym:
            spans_by_symbol[sym].append(node)
    for fact in fact_by_id.values():
        for span_id in _ids((*(_get(fact, "direct_span_ids", ()) or ()), *(_get(fact, "relation_span_ids", ()) or ()))):
            spans_by_id.setdefault(span_id, fact)
        sym = _text(_get(fact, "subject"))
        if sym:
            spans_by_symbol[sym].append(fact)
    scope_entries = set(_ids(_get(implementation_scope, "target_entry_symbol_ids", ())))
    scope_target = set(
        _ids(_get(implementation_scope, "target_core_symbol_ids", ()))
        + _ids(_get(implementation_scope, "target_dependency_symbol_ids", ()))
    )
    # A paragraph is not always represented by a facet.  In particular, the
    # Architect can split a method unit into a formula/output paragraph while
    # retaining the authoritative claim/equation bindings only on the
    # argument unit.  Build this index before compiling paragraphs so that the
    # Research dossier has one deterministic evidence entry point for both
    # facet-led and unit-led plans.  These are identity bindings only; no
    # operation is inferred from the unit's prose fields.
    argument_unit_by_id = {
        _text(_get(unit, "argument_unit_id")): unit
        for unit in (_get(plan, "argument_units", ()) or ())
        if _text(_get(unit, "argument_unit_id"))
    }
    method_unit_by_paragraph: dict[str, list[Any]] = defaultdict(list)
    for method_unit in (_get(plan, "method_units", ()) or ()):
        for paragraph_id in _ids(_get(method_unit, "paragraph_ids", ())):
            method_unit_by_paragraph[paragraph_id].append(method_unit)
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
            ("facet_alignments", alignment_items),
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
        fact_ids: set[str] = set()
        claim_ids: set[str] = set()
        equation_ids: set[str] = set()
        span_ids: set[str] = set()
        paragraph_argument_units = [
            argument_unit_by_id[unit_id]
            for unit_id in _ids(_get(paragraph, "argument_unit_ids", ()))
            if unit_id in argument_unit_by_id
        ]
        paragraph_method_units = method_unit_by_paragraph.get(paragraph_id, ())
        # A MethodUnit is the closed paragraph-sidecar authority.  When one
        # exists, consuming the coarse argument-unit rows as well duplicates
        # every fact in the unit across every split paragraph and lets a
        # facet inherit evidence for unrelated operations.  Use the exact
        # MethodUnit only.  The argument-unit fallback is intentionally
        # limited to a formula-only paragraph whose equation binding selects
        # one unambiguous unit; ordinary facet paragraphs must remain
        # evidence-local.
        if paragraph_method_units:
            paragraph_unit_records = list(paragraph_method_units)
        else:
            formula_only = bool(formula_ids) and not facet_ids and not _get(
                paragraph, "required_field_candidate_ids", ()
            )
            formula_tokens = {
                value.removeprefix("formula:").removeprefix("equation:")
                for value in formula_ids
                if value.strip()
            }
            equation_matched_units = [
                unit for unit in paragraph_argument_units
                if formula_tokens.intersection({
                    value.removeprefix("equation:")
                    for value in _ids(_get(unit, "equation_ids", ()))
                })
            ]
            if formula_only and len(equation_matched_units) == 1:
                paragraph_unit_records = equation_matched_units
            elif formula_only and len(paragraph_argument_units) == 1:
                paragraph_unit_records = paragraph_argument_units
            else:
                paragraph_unit_records = []
        unit_binding_present = False
        unit_fact_ids: set[str] = set()
        unit_claim_ids: set[str] = set()
        unit_equation_ids: set[str] = set()
        unit_span_ids: set[str] = set()
        for unit in paragraph_unit_records:
            bound_fact_ids = set(_ids(_get(unit, "fact_ids", ())))
            bound_claim_ids = set(_ids(_get(unit, "claim_ids", ())))
            bound_equation_ids = set(_ids(_get(unit, "equation_ids", ())))
            bound_span_ids = {
                value for value in _ids(
                    (*(_get(unit, "evidence_spans", ()) or ()),
                     *(_get(unit, "source_artifact_ids", ()) or ()))
                )
                if value.startswith("span:")
            }
            if bound_fact_ids or bound_claim_ids or bound_equation_ids or bound_span_ids:
                unit_binding_present = True
            unit_fact_ids.update(bound_fact_ids)
            unit_claim_ids.update(bound_claim_ids)
            unit_equation_ids.update(bound_equation_ids)
            unit_span_ids.update(bound_span_ids)
        # Argument-unit bindings are closed identifiers, not a semantic
        # shortcut.  The normal fact/claim/equation expansion below still
        # requires the referenced objects to exist and to pass the same
        # operation-chain checks as facet evidence.
        if unit_binding_present:
            fact_ids.update(unit_fact_ids)
            claim_ids.update(unit_claim_ids)
            equation_ids.update(unit_equation_ids)
            span_ids.update(unit_span_ids)
        if (
            not facet_ids
            and not formula_ids
            and not _get(paragraph, "required_field_candidate_ids", ())
            and not unit_binding_present
        ):
            continue
        exact_excerpts: list[str] = []
        direct_excerpts: list[str] = []
        fallback_excerpts: list[str] = []
        candidate_symbols: set[str] = set()
        alignment_operation_atoms: list[dict[str, Any]] = []
        alignment_conditions: list[str] = []
        alignment_statuses: list[str] = []
        alignment_unresolved = False
        contradiction_ids: set[str] = set()

        def collect_alignment_excerpt(excerpt: Any) -> None:
            excerpt_text = _text(_get(excerpt, "exact_excerpt") or _get(excerpt, "text"))
            if excerpt_text:
                direct_excerpts.append(excerpt_text)
            span_id = _text(_get(excerpt, "span_id") or _get(excerpt, "source_span_id"))
            if span_id:
                span_ids.add(span_id)
            candidate_symbols.update(_ids(
                (_get(excerpt, "symbol_id"), _get(excerpt, "symbol"))
            ))
            excerpt_fact_ids = _ids(_get(excerpt, "fact_ids", ()))
            excerpt_claim_ids = _ids(_get(excerpt, "claim_ids", ()))
            excerpt_equation_ids = _ids(_get(excerpt, "equation_ids", ()))
            fact_ids.update(excerpt_fact_ids)
            claim_ids.update(excerpt_claim_ids)
            equation_ids.update(excerpt_equation_ids)
            for atom in _get(excerpt, "operation_atoms", ()) or ():
                atom_row = (
                    {"operation": _text(atom), "predicate": "aligned_operation"}
                    if isinstance(atom, str)
                    else _dump(atom)
                )
                if atom_row and span_id:
                    atom_row.setdefault("source_span_id", span_id)
                if atom_row and excerpt_text:
                    atom_row.setdefault("exact_excerpt", excerpt_text)
                if atom_row:
                    alignment_operation_atoms.append(atom_row)
                    candidate_symbols.update(_ids(
                        (_get(atom, "symbol_id"), _get(atom, "symbol"))
                    ))

        for candidate in relevant_candidates:
            fact_ids.update(_ids(_get(candidate, "bound_fact_ids", ())))
            claim_ids.update(_ids(_get(candidate, "bound_claim_ids", ())))
            equation_ids.update(_ids(_get(candidate, "bound_equation_ids", ())))
            span_ids.update(_ids(_get(candidate, "bound_span_ids", ())))
            direct_excerpts.extend(_ids(_get(candidate, "exact_excerpts", ())))
            contradiction_ids.update(_ids(_get(candidate, "contradiction_ids", ())))
        for facet_id in facet_ids:
            facet = facet_by_id.get(facet_id)
            # Semantic fields and author statements describe intent; they are
            # not copied into the frozen source-excerpt channel.
            contradiction_ids.update(_ids(_get(facet, "contradiction_ids", ())))
            # A frozen brief clause is an upstream deterministic binding.  It
            # is narrower than the brief-level union: use only the clause
            # whose id is carried by this facet, and only its closed evidence
            # handles.  Unlicensed clauses deliberately contribute nothing.
            brief = brief_by_id.get(_text(_get(facet, "brief_id")))
            facet_clause_id = _text(_get(facet, "clause_id"))
            if brief is not None and facet_clause_id:
                for clause in _get(brief, "clauses", ()) or ():
                    if _text(_get(clause, "clause_id")) != facet_clause_id:
                        continue
                    clause_license = _text(_get(clause, "license"))
                    if clause_license in {"positively_licensed", "partially_licensed"}:
                        claim_ids.update(_ids(_get(clause, "bound_claim_ids", ())))
                        span_ids.update(_ids(_get(clause, "bound_span_ids", ())))
                        equation_ids.update(_ids(_get(clause, "bound_equation_ids", ())))
                    break
            alignment = alignment_by_facet_id.get(facet_id)
            if alignment is None:
                continue
            alignment_status = _text(_get(alignment, "status"))
            if alignment_status:
                alignment_statuses.append(alignment_status)
            alignment_unresolved = alignment_unresolved or alignment_status in {
                "mismatch", "unresolved"
            }
            alignment_span_ids = set(_ids(_get(alignment, "bound_span_ids", ())))
            alignment_fact_ids = set(_ids(_get(alignment, "bound_fact_ids", ())))
            alignment_claim_ids = set(_ids(_get(alignment, "bound_claim_ids", ())))
            alignment_equation_ids = set(_ids(_get(alignment, "bound_equation_ids", ())))
            for binding in _get(alignment, "field_bindings", ()) or ():
                binding_status = _text(_get(binding, "status"))
                if binding_status:
                    alignment_statuses.append(binding_status)
                alignment_unresolved = alignment_unresolved or binding_status in {
                    "mismatch", "unresolved"
                }
                alignment_fact_ids.update(_ids(_get(binding, "bound_fact_ids", ())))
                alignment_claim_ids.update(_ids(_get(binding, "bound_claim_ids", ())))
                alignment_span_ids.update(_ids(_get(binding, "bound_span_ids", ())))
                alignment_equation_ids.update(_ids(_get(binding, "bound_equation_ids", ())))
                alignment_conditions.extend(_ids(_get(binding, "active_path_conditions", ())))
                for excerpt in _get(binding, "exact_excerpts", ()) or ():
                    collect_alignment_excerpt(excerpt)
            fact_ids.update(alignment_fact_ids)
            claim_ids.update(alignment_claim_ids)
            equation_ids.update(alignment_equation_ids)
            span_ids.update(alignment_span_ids)
            alignment_unresolved = alignment_unresolved or (
                _text(_get(alignment, "status")) in {"mismatch", "unresolved"}
            )
            for excerpt in _get(alignment, "exact_excerpts", ()) or ():
                collect_alignment_excerpt(excerpt)
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
        # The live aligner may return a validated exact source span while
        # omitting internal CodeFact ids.  Recover the binding by exact span
        # identity only; this is a representation repair, not semantic
        # matching.  A span shared by several facts keeps all of them and the
        # normal CodeFact compiler still applies validation/status gates.
        for span_id in tuple(span_ids):
            fact_ids.update(fact_ids_by_span.get(span_id, ()))
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
                        fallback_excerpts.append(excerpt)

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
        # An empty requested set means "compile all facts" for the standalone
        # compiler API.  A paragraph dossier must never use that default:
        # without an exact facet/claim/span binding it has no code evidence.
        fact_chain = (
            compile_code_fact_operation_chain(
                facts=facts,
                fact_ids=fact_ids,
            )
            if fact_ids else {
                "operation_atoms": (),
                "formalizable_signatures": (),
                "fact_ids": (),
                "exact_span_ids": (),
                "relation_evidence_ids": (),
                "shape_or_type_hints": (),
                "return_value_descriptors": (),
                "scopes": (),
                "diagnostics": (),
            }
        )
        span_ids.update(fact_chain["exact_span_ids"])
        relation_ids_from_facts = tuple(fact_chain["relation_evidence_ids"])
        for fact_id in fact_chain["fact_ids"]:
            fact = fact_by_id.get(fact_id)
            fact_subject = _text(_get(fact, "subject"))
            if fact_subject:
                candidate_symbols.add(fact_subject)
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
        fact_chain_diagnostics = list(fact_chain["diagnostics"])
        fact_chain_ready = bool(
            fact_chain["fact_ids"]
            and fact_chain["operation_atoms"]
            and fact_chain["formalizable_signatures"]
            and not fact_chain_diagnostics
        )
        if not selected_node_ids and (fact_ids or claim_ids or equation_ids):
            # A behavior graph is optional at this boundary.  A complete
            # CodeFact operation chain is an equivalent deterministic source;
            # do not report a missing graph when it already closes the facts.
            if fact_chain_ready:
                unresolved_ids = []
            elif fact_ids and graph_nodes:
                unresolved_ids = [
                    "missing_connected_behavior_subgraph",
                    "missing_fact_operation_chain",
                ]
            else:
                unresolved_ids = [
                    "missing_fact_operation_chain"
                    if fact_ids else "missing_connected_behavior_subgraph"
                ]
        elif set(seed_ids) - selected_node_set:
            unresolved_ids = ["missing_connected_behavior_subgraph"]
        else:
            unresolved_ids = []
        if fact_chain_ready:
            # A complete source-ordered CodeFact chain is an equivalent
            # deterministic research source.  The optional behavior graph
            # may expose only a partial symbol neighbourhood (or none at
            # all), which must not demote an otherwise closed fact dossier.
            # Preserve genuine unresolved relation rows, but remove only the
            # synthetic graph-connectivity diagnostics emitted by this
            # paragraph's seed search.
            unresolved_ids = [
                item for item in unresolved_ids
                if item not in {
                    "missing_connected_behavior_subgraph",
                    "missing_fact_operation_chain",
                }
            ]
        if alignment_unresolved and not fact_chain_ready:
            unresolved_ids.append("facet_alignment:" + ",".join(
                facet_ids[:1]
            ))
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
        relation_ids = tuple(dict.fromkeys((
            *(
                _text(_get(item, "relation_id"))
                for item in selected_relations
                if _text(_get(item, "relation_id"))
            ),
            *relation_ids_from_facts,
        )))
        relation_by_id = {
            _text(_get(item, "relation_id")): item
            for item in selected_relations
            if _text(_get(item, "relation_id"))
        }
        # Fact-level relation evidence may be represented only by its stable
        # id in the CodeFact artifact.  It is still retained in the dossier,
        # but it cannot be classified as a call/data/control edge without the
        # relation row itself.  Never turn that representation gap into a
        # compiler KeyError.
        call_ids = tuple(
            item for item in relation_ids
            if item in relation_by_id
            and _text(_get(relation_by_id[item], "kind")).upper() in _CALL_RELATIONS
        )
        data_ids = tuple(
            item for item in relation_ids
            if item in relation_by_id
            and _text(_get(relation_by_id[item], "kind")).upper() in _DATA_RELATIONS
        )
        control_ids = tuple(
            item for item in relation_ids
            if item in relation_by_id
            and _text(_get(relation_by_id[item], "kind")).upper() in _CONTROL_RELATIONS
        )
        # Bounded callee-body expansion for direct call edges (depth=1, max 3 callees, max 75 lines)
        callee_body_excerpts: list[str] = []
        call_path_excerpts: list[str] = []
        data_flow_excerpts: list[str] = []

        caller_symbols = {
            _text(_get(node, "symbol_id"))
            for node in operation_nodes
            if _text(_get(node, "symbol_id"))
        }
        visited_callees: set[str] = set()

        candidate_call_relations: list[Any] = [
            relation_by_id[cid] for cid in call_ids if cid in relation_by_id
        ]
        for rel in eligible_relations.values():
            if _text(_get(rel, "kind")).upper() in _CALL_RELATIONS:
                src_node = _relation_endpoint(rel, "source", eligible_nodes)
                if src_node in selected_node_ids and rel not in candidate_call_relations:
                    candidate_call_relations.append(rel)

        for rel in candidate_call_relations:
            if len(visited_callees) >= 3:
                break
            callee_node_id = _relation_endpoint(rel, "target", eligible_nodes)
            callee_symbol = _text(_get(rel, "target_symbol_id"))
            if not callee_symbol and callee_node_id in graph_nodes:
                callee_symbol = _text(_get(graph_nodes[callee_node_id], "symbol_id"))
            if not callee_symbol:
                callee_symbol = callee_node_id
            if not callee_symbol or callee_symbol in caller_symbols or callee_symbol in visited_callees:
                continue

            callee_span_id = _text(_get(rel, "target_span_id"))
            if not callee_span_id and callee_node_id in graph_nodes:
                callee_span_id = _text(_get(graph_nodes[callee_node_id], "source_span_id"))

            callee_spans = []
            if callee_span_id and callee_span_id in spans_by_id:
                callee_spans.append(spans_by_id[callee_span_id])
            if callee_symbol in spans_by_symbol:
                callee_spans.extend(spans_by_symbol[callee_symbol])
            if callee_node_id in graph_nodes:
                node_span_id = _text(_get(graph_nodes[callee_node_id], "source_span_id"))
                if node_span_id and node_span_id in spans_by_id:
                    callee_spans.append(spans_by_id[node_span_id])

            callee_found_excerpt = ""
            for sp in callee_spans:
                txt = _text(_get(sp, "exact_excerpt") or _get(sp, "text"))
                if txt and not _is_logging_or_filtering_excerpt(txt):
                    callee_found_excerpt = txt
                    sid = _text(_get(sp, "span_id") or _get(sp, "evidence_id"))
                    if sid:
                        span_ids.add(sid)
                    dig = _text(_get(sp, "file_digest") or _get(sp, "source_digest") or _get(sp, "excerpt_digest"))
                    pth = _text(_get(sp, "path") or sid)
                    if pth and dig:
                        source_digests[pth] = dig
                    break

            if not callee_found_excerpt and callee_node_id in graph_nodes:
                txt = _text(_get(graph_nodes[callee_node_id], "code_snippet") or _get(graph_nodes[callee_node_id], "exact_excerpt"))
                if txt and not _is_logging_or_filtering_excerpt(txt):
                    callee_found_excerpt = txt

            if callee_found_excerpt:
                visited_callees.add(callee_symbol)
                lines = callee_found_excerpt.splitlines()
                if len(lines) > 75:
                    callee_found_excerpt = "\n".join(lines[:75])
                callee_body_excerpts.append(callee_found_excerpt)

        for cid in call_ids:
            rel = relation_by_id.get(cid)
            if not rel:
                continue
            txt = _text(_get(rel, "exact_excerpt") or _get(rel, "text"))
            if txt:
                call_path_excerpts.append(txt)

        for did in data_ids:
            rel = relation_by_id.get(did)
            if not rel:
                continue
            txt = _text(_get(rel, "exact_excerpt") or _get(rel, "text"))
            if txt:
                data_flow_excerpts.append(txt)

        direct_primary = [x for x in direct_excerpts if not _is_logging_or_filtering_excerpt(x)]
        direct_demoted = [x for x in direct_excerpts if _is_logging_or_filtering_excerpt(x)]
        regular_fallbacks = [x for x in fallback_excerpts if not _is_logging_or_filtering_excerpt(x)]
        demoted_fallbacks = [x for x in fallback_excerpts if _is_logging_or_filtering_excerpt(x)]

        ordered_excerpts = [
            *direct_primary,
            *callee_body_excerpts,
            *call_path_excerpts,
            *data_flow_excerpts,
            *regular_fallbacks,
            *direct_demoted,
            *demoted_fallbacks,
        ]
        exact_excerpts = tuple(dict.fromkeys(item for item in ordered_excerpts if str(item).strip()))
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
        active_conditions.extend(alignment_conditions)
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
        operation_atoms = [
            _dump(node) for node in operation_nodes
        ]
        operation_atoms.extend(fact_chain["operation_atoms"])
        operation_atoms.extend(alignment_operation_atoms)
        # Do not let duplicate alignment excerpts inflate the operation
        # contract.  The first exact atom wins, preserving source order.
        unique_operation_atoms: list[dict[str, Any]] = []
        seen_operation_atoms: set[str] = set()
        for atom in operation_atoms:
            atom_key = _text(
                atom.get("operation_id")
                or atom.get("source_span_id")
                or atom.get("node_id")
                or atom.get("predicate")
            )
            atom_key = atom_key or _digest(atom)
            if atom_key in seen_operation_atoms:
                continue
            seen_operation_atoms.add(atom_key)
            unique_operation_atoms.append(atom)
        shape_or_type_hints: list[str] = list(fact_chain.get("shape_or_type_hints", ()))
        return_value_descriptors: list[str] = list(fact_chain.get("return_value_descriptors", ()))
        formalizable_signatures: list[dict[str, Any]] = [
            dict(item) for item in fact_chain["formalizable_signatures"]
        ]
        for atom in unique_operation_atoms:
            predicate = _text(
                atom.get("predicate") or atom.get("operation")
                or atom.get("operation_id")
            )
            operands = _ids(atom.get("operands", ()))
            result = _text(
                atom.get("result") or atom.get("output")
                or atom.get("return_value")
            )
            atom_conditions = tuple(dict.fromkeys(
                _ids(atom.get("conditions", ()))
                + _ids((atom.get("guard"),))
            ))
            atom_shapes = _ids(
                atom.get("shape_or_type_hints")
                or atom.get("shape_hints")
                or atom.get("types")
                or ()
            )
            shape_or_type_hints.extend(
                item for item in atom_shapes if item not in shape_or_type_hints
            )
            if predicate.casefold() in {
                "return", "returns", "emits", "outputs", "writes_back"
            } or any(
                key in atom for key in ("return_value", "returns", "output")
            ):
                return_descriptor = result or _text(
                    atom.get("returns") or atom.get("output")
                )
                if return_descriptor and return_descriptor not in return_value_descriptors:
                    return_value_descriptors.append(return_descriptor)
            if predicate or operands or result:
                formalizable_signatures.append({
                    "predicate": predicate,
                    "operands": list(operands),
                    "result": result,
                    "conditions": list(atom_conditions),
                    "shape_or_type_hints": list(atom_shapes),
                    "source_span_id": _text(
                        atom.get("source_span_id") or atom.get("span_id")
                    ),
                })
        mechanism_bound = bool(
            selected_node_ids
            or unique_operation_atoms
            or span_ids
            or author_statements
            or unit_binding_present
        )
        code_required = bool(
            fact_chain["fact_ids"]
            or equation_ids
            or (span_ids and not author_statements)
            or selected_node_ids
        )
        readiness_failures: list[str] = []
        readiness_failures.extend(fact_chain_diagnostics)
        if not fact_chain_ready:
            readiness_failures.extend(
                item for item in unresolved_ids
                if item not in readiness_failures
            )
        # A complete source-ordered CodeFact chain is sufficient for the
        # operation/signature contract.  Keep unresolved graph relations on
        # the dossier for audit and callback routing, but do not make an
        # optional graph edge a prerequisite for a closed fact chain.
        if alignment_unresolved and not fact_chain_ready:
            readiness_failures.append(
                "facet_alignment_unresolved:" + ",".join(
                    dict.fromkeys(facet_ids)
                )
            )
        if code_required and not fact_chain["fact_ids"]:
            readiness_failures.append("supported_code_fact_missing")
        if code_required and not span_ids:
            readiness_failures.append("exact_source_span_missing")
        if code_required and not unique_operation_atoms:
            readiness_failures.append("operation_chain_missing")
        if code_required and not formalizable_signatures:
            readiness_failures.append("formalizable_signature_missing")
        readiness_failures = list(dict.fromkeys(
            value for value in readiness_failures if _text(value)
        ))
        if (
            code_required
            and fact_chain["fact_ids"]
            and span_ids
            and unique_operation_atoms
            and formalizable_signatures
            and not readiness_failures
        ):
            evidence_readiness: Literal["code_ready", "intent_ready", "blocked"] = "code_ready"
            readiness_failures = []
        elif author_statements:
            evidence_readiness = "intent_ready"
        else:
            evidence_readiness = "blocked"
        if require_nonempty and (facet_ids or formula_ids or relevant_candidates) and not mechanism_bound:
            raise ValueError(
                "research_dossier_empty_mechanism_unit:"
                f"{section_id}:{paragraph_id}"
            )
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
            operation_atoms=tuple(unique_operation_atoms),
            formalizable_signatures=tuple(formalizable_signatures),
            configuration_bindings=tuple(configuration_bindings),
            default_activation=activation,
            active_path_conditions=tuple(dict.fromkeys(active_conditions)),
            shape_or_type_hints=tuple(dict.fromkeys(shape_or_type_hints)),
            return_value_descriptors=tuple(dict.fromkeys(return_value_descriptors)),
            evidence_readiness=evidence_readiness,
            readiness_failures=tuple(readiness_failures),
            code_required=code_required,
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
    facets: Iterable[Any] = (),
) -> tuple[dict[str, Any], ...]:
    """Create bounded research callbacks for dossier links that remain open.

    This is a routing projection, not a repair or prose generator.  It names
    the paragraph, argument unit, exact unresolved relation labels, and the
    already-frozen symbols/facts that define the next search.  Dynamic or
    missing graph links therefore remain open and cannot be silently treated
    as an implementation fact.
    """

    requests: list[dict[str, Any]] = []
    facet_by_id = {
        _text(_get(facet, "facet_id")): facet
        for facet in facets
        if _text(_get(facet, "facet_id"))
    }

    def _semantic_query_texts(
        dossier: ResearchMechanismDossierV1,
    ) -> tuple[str, ...]:
        """Collect reader/scientific vocabulary, never binding ids.

        Unresolved relation labels identify the gap for the ledger, but they
        are not useful repository queries.  Search terms instead come from the
        paragraph goal, author statements, facet semantic fields, and the
        source operation's scientific operands/results.
        """

        values: list[str] = [
            _text(dossier.author_question),
            *(_text(item) for item in dossier.author_statements),
        ]
        for facet_id in dossier.facet_ids:
            facet = facet_by_id.get(_text(facet_id))
            if facet is None:
                continue
            quote = _text(_get(facet, "exact_source_quote"))
            if quote:
                values.append(quote)
            fields = _get(facet, "semantic_fields", {}) or {}
            if isinstance(fields, Mapping):
                values.extend(
                    _text(value)
                    for value in fields.values()
                    if _text(value)
                )
        for atom in dossier.operation_atoms:
            if not isinstance(atom, Mapping):
                continue
            # ``source_span_id``, operation ids, relation ids, and node ids are
            # binding metadata.  Subject/operands/result and descriptors are
            # the bounded scientific/data-flow vocabulary we want to search.
            for name in (
                "subject", "predicate", "operands", "result", "output",
                "return_value", "operation_descriptors", "shape_or_type_hints",
            ):
                value = atom.get(name)
                if isinstance(value, (list, tuple, set)):
                    values.extend(_text(item) for item in value if _text(item))
                elif _text(value):
                    values.append(_text(value))
        values.extend(_text(item) for item in dossier.shape_or_type_hints)
        values.extend(_text(item) for item in dossier.return_value_descriptors)
        # Entry symbols are allowed only when they are actual symbols, not
        # source-span/node/relation handles.
        values.extend(
            _text(item)
            for item in dossier.entry_symbol_ids
            if not re.match(r"^(?:span|node|relation|dossier|paragraph|facet|brief|claim|formula|obligation)[:_-]", _text(item), re.I)
        )
        return tuple(dict.fromkeys(value for value in values if value))

    def _reader_missing_parts(
        dossier: ResearchMechanismDossierV1,
        unresolved: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Describe the open gap in reader language while keeping ids typed.

        ``missing_parts`` is consumed by the callback supervisor as search
        context.  Binding handles such as ``facet_alignment:<id>`` belong in
        the request's target/ledger fields, not in that reader-facing text.
        Generic diagnostic labels (for example
        ``missing_connected_behavior_subgraph``) remain because they describe
        the kind of gap without naming a project object.
        """

        values: list[str] = []
        if dossier.author_question:
            values.append(_text(dossier.author_question))
        values.extend(
            _text(item) for item in dossier.author_statements if _text(item)
        )
        for facet_id in dossier.facet_ids:
            facet = facet_by_id.get(_text(facet_id))
            if facet is None:
                continue
            fields = _get(facet, "semantic_fields", {}) or {}
            if isinstance(fields, Mapping):
                for key in (
                    "rationale", "design_objective", "motivation", "operation",
                    "mechanism", "formula_goal", "mathematical_goal", "purpose",
                ):
                    value = fields.get(key)
                    if isinstance(value, (list, tuple, set)):
                        values.extend(_text(item) for item in value if _text(item))
                    elif _text(value):
                        values.append(_text(value))
            quote = _text(_get(facet, "exact_source_quote"))
            if quote:
                values.append(quote)
        for atom in dossier.operation_atoms:
            if not isinstance(atom, Mapping):
                continue
            descriptors = atom.get("operation_descriptors") or ()
            if isinstance(descriptors, (list, tuple, set)):
                values.extend(_text(item) for item in descriptors if _text(item))
            elif _text(descriptors):
                values.append(_text(descriptors))
        for item in unresolved:
            label = _text(item)
            if not label:
                continue
            if re.match(
                r"^(?:span|node|relation|rel|dossier|request|target|facet|brief|"
                r"paragraph|claim|formula|obligation|method[-_]?unit)"
                r"[-_:][A-Za-z0-9:_-]+$",
                label,
                re.I,
            ) or label.casefold().startswith("facet_alignment:"):
                continue
            values.append(label)
        return tuple(dict.fromkeys(value for value in values if value))[:12]

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

        semantic_texts = _semantic_query_texts(dossier)
        from code2paper.agentic.writer_research_router import (
            directed_search_terms_from_texts,
        )

        terms = list(directed_search_terms_from_texts(*semantic_texts, limit=16))
        scope_text = ", ".join(terms[:8])
        question = (
            f"Which bounded repository trace resolves the missing implementation "
            f"for the reader goal {dossier.author_question or 'this mechanism'}"
            + (f" using {scope_text}" if scope_text else "")
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
            "missing_parts": _reader_missing_parts(dossier, unresolved),
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
                fact_chain_ready = (
                    dossier.evidence_readiness == "code_ready"
                    and bool(dossier.fact_ids)
                    and bool(dossier.formalizable_signatures)
                )
                if status == "entailed" and has_evidence and (
                    dossier.ordered_operation_node_ids or fact_chain_ready
                ):
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
    method_unit_by_paragraph: dict[str, dict[str, Any]] = {}
    for method_unit in (_get(plan, "method_units", ()) or ()):
        method_unit_payload = _dump(method_unit)
        for paragraph_id in _ids(method_unit_payload.get("paragraph_ids", ())):
            method_unit_by_paragraph.setdefault(paragraph_id, method_unit_payload)

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
            witness_contract = _get(paragraph, "witness_contract", {}) or {}
            contract_by_target_id = {
                _text(_get(item, "target_id")): dict(_dump(item))
                for item in (_get(witness_contract, "targets", ()) or ())
                if _text(_get(item, "target_id"))
            }
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
                    target_contract = contract_by_target_id.get(target_id, {})
                    target_row: dict[str, Any] = {
                        "target_id": target_id,
                        "target_kind": target_kind,
                    }
                    # Keep the Writer's organization surface useful when a
                    # target is not a publication field candidate.  The
                    # private id remains in ``closed_target_ids`` and is
                    # removed by the LLM projection; only the Architect's
                    # semantic/authority contract crosses the prose boundary.
                    for source_key, output_key in (
                        ("semantic_atom", "semantic_atom"),
                        ("paper_role", "paper_role"),
                        ("authority_lane", "authority_lane"),
                        ("surface_mode", "surface_mode"),
                        ("render_policy", "render_policy"),
                        ("claim_strength", "claim_strength"),
                    ):
                        value = target_contract.get(source_key)
                        if isinstance(value, str):
                            value = value.strip()
                        if value not in (None, "", (), []):
                            target_row[output_key] = value
                    required_conditions = target_contract.get("required_conditions")
                    if required_conditions:
                        target_row["conditions"] = list(
                            _ids(required_conditions)
                        )
                    required_polarity = _text(
                        target_contract.get("required_polarity")
                    )
                    if required_polarity and required_polarity != "unknown":
                        target_row["polarity"] = required_polarity
                    ordered_targets.append(target_row)
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
                    "evidence_readiness": dossier.evidence_readiness,
                    "readiness_failures": list(dossier.readiness_failures),
                    "code_required": dossier.code_required,
                    "formalizable_signatures": [
                        dict(item) for item in dossier.formalizable_signatures
                    ],
                    "shape_or_type_hints": list(dossier.shape_or_type_hints),
                    "return_value_descriptors": list(dossier.return_value_descriptors),
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
            # A paragraph owns one canonical package per package id.  Preserve
            # source order for distinct obligations, but never hand duplicate
            # representations of the same package to the Writer.
            canonical_formula_packages: list[dict[str, Any]] = []
            seen_formula_package_ids: set[str] = set()
            for package in formula_packages:
                package_id = _text(package.get("package_id"))
                if package_id and package_id in seen_formula_package_ids:
                    continue
                if package_id:
                    seen_formula_package_ids.add(package_id)
                canonical_formula_packages.append(package)
            formula_packages = canonical_formula_packages
            formula_policy = (
                "consume_only" if formula_packages
                else "prose_only_or_request_formalizer"
            )
            section_packets.append(PublicationAuthoringPacketV2(
                section_id=section_id,
                paragraph_id=paragraph_id,
                rhetorical_goal=_text(_get(paragraph, "paragraph_role")),
                expected_sentence_range=tuple(
                    int(value)
                    for value in (
                        _get(paragraph, "expected_sentence_range", (1, 4))
                        or (1, 4)
                    )
                ),
                ordered_targets=tuple(ordered_targets),
                dossier_summary=dossier_summary,
                material_conditions=conditions,
                configuration_state=configuration_state,
                formula_packages=tuple(formula_packages),
                formula_generation_policy=formula_policy,
                canonical_formula_package_ids=tuple(
                    _text(item.get("package_id"))
                    for item in formula_packages
                    if _text(item.get("package_id"))
                ),
                method_unit={
                    **dict(method_unit_by_paragraph.get(paragraph_id, {})),
                    **({"section_heading": _text(_get(section, "heading") or _get(section, "title"))}
                       if _text(_get(section, "heading") or _get(section, "title")) else {}),
                },
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
    "compile_code_fact_operation_chain",
    "compile_derivation_records",
    "merge_derivations_into_field_candidates",
    "validate_candidate_authority",
    "write_research_derived_artifacts",
]
