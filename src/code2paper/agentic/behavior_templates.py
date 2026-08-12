"""R7 composable behavior templates.

Implements design section 10 (R7): composable behavior templates that
improve path discovery and Method organization quality without
affecting fact authorization.

A behavior template is a **structural pattern matcher** against the
``CodeBehaviorGraphV1`` produced by the research loop.  Each template
identifies a common implementation pattern (e.g.,
``feature_predict_score_rank_filter``) and provides:

- a **graph query** (the structural fingerprint: required predicates,
  required relation kinds, optional ordering hint);
- **role aliases** (mapping generic role names like "predictor" /
  "ranker" to behavior-graph predicate sets, so the supervisor can
  resolve which symbols play each role without hardcoding symbol ids);
- **stage hints** (organization preferences the writer may use to order
  claims within a Method section);
- a **match score** (how well the template matches the actual code,
  computed deterministically from predicate / relation coverage).

R7 hard constraints (design section 10):

- templates MUST NOT contain project names as required conditions;
- templates MUST NOT contain absolute file paths;
- templates MUST NOT contain project claim text;
- templates MUST NOT contain fixed evidence ids or fact ids;
- templates MUST NOT directly authorize claims (that is the generic
  compiler's job -- ``generic_fact_compiler.py``).

Exit condition (design section 10): with all templates disabled, the
generic compiler MUST still produce some supported claims; enabling
templates only improves path discovery and organization quality, never
the fact authorization result.

The four templates required by R7 are registered in
``DEFAULT_BEHAVIOR_TEMPLATES``:

- ``feature_predict_score_rank_filter``
- ``embedding_augment_dual_attention_rerank``
- ``temporal_multichannel_sequence_readout``
- ``sparse_bipartite_propagation_ppr``
"""

from __future__ import annotations

import re
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BEHAVIOR_RELATION_KINDS,
    CodeBehaviorGraphV1,
    assert_valid_predicate,
    assert_valid_relation_kind,
)


# ---------------------------------------------------------------------------
# Template data models
# ---------------------------------------------------------------------------


class BehaviorTemplateQueryV1(BaseModel):
    """A structural query against the behavior graph.

    A query is a paraphrase-invariant fingerprint: it matches any
    behavior graph whose nodes contain the required predicates and whose
    relations contain the required relation kinds.  Queries NEVER
    reference symbol ids, file paths, or project names -- only generic
    behavior predicates and relation kinds from the V1 vocabulary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_predicates: frozenset[str] = Field(default_factory=frozenset)
    required_relation_kinds: frozenset[str] = Field(default_factory=frozenset)
    optional_predicates: frozenset[str] = Field(default_factory=frozenset)
    forbidden_predicates: frozenset[str] = Field(default_factory=frozenset)
    #: Optional data-flow order hint: the expected sequence of
    #: predicates along the data path.  Used only for organization, not
    #: for matching.
    predicate_order_hint: tuple[str, ...] = Field(default_factory=tuple)
    #: Minimum number of distinct predicates that must appear (default
    #: 0 means "all required_predicates must appear").
    min_distinct_predicates: int = 0

    @field_validator("required_predicates", "optional_predicates", "forbidden_predicates")
    @classmethod
    def _validate_predicates(cls, value: frozenset[str]) -> frozenset[str]:
        for predicate in value:
            assert_valid_predicate(predicate)
        return value

    @field_validator("required_relation_kinds")
    @classmethod
    def _validate_relation_kinds(cls, value: frozenset[str]) -> frozenset[str]:
        for kind in value:
            assert_valid_relation_kind(kind)
        return value


class RoleAliasV1(BaseModel):
    """A mapping from a generic role name to a predicate set.

    The alias is resolved at match time: the supervisor looks for a
    symbol whose behavior nodes contain the alias's required predicates.
    A role alias never references a specific symbol id, file path, or
    project name -- only generic behavior predicates.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    required_predicates: frozenset[str] = Field(default_factory=frozenset)
    optional_predicates: frozenset[str] = Field(default_factory=frozenset)
    description: str = ""

    @field_validator("required_predicates", "optional_predicates")
    @classmethod
    def _validate_predicates(cls, value: frozenset[str]) -> frozenset[str]:
        for predicate in value:
            assert_valid_predicate(predicate)
        return value


class StageHintV1(BaseModel):
    """An organization preference for a Method stage.

    The hint tells the writer how to order the claims in this stage, but
    NEVER dictates the claim text.  ``role_order`` lists the generic
    role names (from ``RoleAliasV1.role``) the writer should introduce
    in this stage, in the suggested order.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_name: str
    purpose: str
    role_order: tuple[str, ...] = Field(default_factory=tuple)
    organization_priority: int = 0


class BehaviorTemplateV1(BaseModel):
    """A composable behavior template.

    Templates are structural pattern matchers: they identify a common
    implementation pattern in a behavior graph and provide role aliases
    + stage hints to guide the supervisor's tool selection and the
    writer's organization.  Templates NEVER authorize claims: that is
    the generic compiler's job.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    description: str
    query: BehaviorTemplateQueryV1
    role_aliases: tuple[RoleAliasV1, ...] = Field(default_factory=tuple)
    stage_hints: tuple[StageHintV1, ...] = Field(default_factory=tuple)
    #: Other template ids this template composes with.  Two templates
    #: compose when their role aliases are disjoint and their stage
    #: hints can be concatenated without conflict.
    composable_with: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("template_id")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template_id must not be empty")
        return value


class DiscoveryQueryHintV2(BaseModel):
    """A vocabulary-bound search hint with no free-form factual prose."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hint_kind: Literal["predicate", "relation", "role", "stage"]
    value: str

    @field_validator("value")
    @classmethod
    def _identifier_only(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
            raise ValueError("discovery hint must be a generic identifier")
        return value


class DiscoveryRoleHintV2(BaseModel):
    """Generic role resolved only through behavior predicates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    required_predicates: frozenset[str] = Field(default_factory=frozenset)
    optional_predicates: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("role")
    @classmethod
    def _generic_role(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("role must be a generic identifier")
        return value

    @field_validator("required_predicates", "optional_predicates")
    @classmethod
    def _validate_predicates(cls, value: frozenset[str]) -> frozenset[str]:
        for predicate in value:
            assert_valid_predicate(predicate)
        return value


class DiscoveryStageHintV2(BaseModel):
    """Ordering-only stage metadata with no purpose/claim text field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_name: str
    role_order: tuple[str, ...] = Field(default_factory=tuple)
    organization_priority: int = 0

    @field_validator("stage_name")
    @classmethod
    def _generic_stage(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("stage_name must be a generic identifier")
        return value


class BehaviorDiscoveryTemplateV2(BaseModel):
    """D2 discovery-only template schema.

    The allowed fields are closed over predicates, relations, generic roles,
    generic stages, and vocabulary-bound query hints.  There is deliberately
    no path, symbol, fact, claim, gap-text, or free-form description field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    query: BehaviorTemplateQueryV1
    role_aliases: tuple[DiscoveryRoleHintV2, ...] = Field(default_factory=tuple)
    stage_hints: tuple[DiscoveryStageHintV2, ...] = Field(default_factory=tuple)
    query_hints: tuple[DiscoveryQueryHintV2, ...] = Field(default_factory=tuple)
    composable_with: frozenset[str] = Field(default_factory=frozenset)

    @field_validator("template_id")
    @classmethod
    def _generic_template_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("template_id must be a generic identifier")
        return value


class BehaviorTemplateMatchV1(BaseModel):
    """A single template's match result against a behavior graph.

    The match is deterministic: the same (template, graph) pair always
    produces the same ``match_score`` and the same role resolution.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str
    matched: bool
    match_score: float
    matched_predicate_count: int
    required_predicate_count: int
    matched_relation_count: int
    required_relation_count: int
    matched_role_aliases: tuple[str, ...] = Field(default_factory=tuple)
    unmatched_role_aliases: tuple[str, ...] = Field(default_factory=tuple)
    missing_predicates: tuple[str, ...] = Field(default_factory=tuple)
    missing_relation_kinds: tuple[str, ...] = Field(default_factory=tuple)
    #: Symbols that resolved each matched role alias (symbol_id ->
    #: role).  Empty when the role could not be resolved.  This is the
    #: only template output that references symbol ids, and it is
    #: derived at match time -- never hardcoded in the template.
    resolved_role_symbols: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------


def match_template(
    template: BehaviorTemplateV1,
    graph: CodeBehaviorGraphV1,
) -> BehaviorTemplateMatchV1:
    """Match a single template against a behavior graph.

    The match is deterministic and structural:

    - ``matched`` is True iff every required predicate appears in the
      graph's node predicates AND every required relation kind appears
      in the graph's relation kinds AND no forbidden predicate appears;
    - ``match_score`` is the Jaccard similarity between the required
      predicates+relations and the graph's actual predicates+relations,
      clamped to ``[0.0, 1.0]``.  When the template has no requirements,
      the score is 0.0 and ``matched`` is False (an empty template never
      matches);
    - role aliases are resolved by scanning symbols: a role resolves
      when at least one symbol's nodes contain all the role's required
      predicates.
    """

    graph_predicates = graph.predicates()
    graph_relation_kinds = graph.relation_kinds()

    required_predicates = set(template.query.required_predicates)
    required_relations = set(template.query.required_relation_kinds)
    forbidden_predicates = set(template.query.forbidden_predicates)

    missing_predicates = sorted(required_predicates - graph_predicates)
    missing_relation_kinds = sorted(required_relations - graph_relation_kinds)
    forbidden_present = sorted(forbidden_predicates & graph_predicates)

    has_requirements = bool(required_predicates or required_relations)
    if not has_requirements:
        # An empty template never matches: it would match every graph
        # and provide no information.
        return BehaviorTemplateMatchV1(
            template_id=template.template_id,
            matched=False,
            match_score=0.0,
            matched_predicate_count=0,
            required_predicate_count=0,
            matched_relation_count=0,
            required_relation_count=0,
        )

    matched_predicates = required_predicates & graph_predicates
    matched_relations = required_relations & graph_relation_kinds
    matched = (
        not missing_predicates
        and not missing_relation_kinds
        and not forbidden_present
    )

    # Jaccard similarity over the union of required + actual predicates
    # and relations.  This rewards graphs that cover the template's
    # requirements without penalizing graphs that have additional
    # unrelated behavior.
    required_union = required_predicates | required_relations
    actual_union = graph_predicates | graph_relation_kinds
    if not required_union:
        score = 0.0
    else:
        intersection = matched_predicates | matched_relations
        union = required_union | actual_union
        score = len(intersection) / len(union) if union else 0.0
        score = max(0.0, min(1.0, score))

    # Resolve role aliases.
    matched_roles: list[str] = []
    unmatched_roles: list[str] = []
    resolved_symbols: dict[str, str] = {}
    for alias in template.role_aliases:
        symbol_id = _resolve_role_alias(graph, alias)
        if symbol_id is not None:
            matched_roles.append(alias.role)
            resolved_symbols[alias.role] = symbol_id
        else:
            unmatched_roles.append(alias.role)

    return BehaviorTemplateMatchV1(
        template_id=template.template_id,
        matched=matched,
        match_score=score,
        matched_predicate_count=len(matched_predicates),
        required_predicate_count=len(required_predicates),
        matched_relation_count=len(matched_relations),
        required_relation_count=len(required_relations),
        matched_role_aliases=tuple(matched_roles),
        unmatched_role_aliases=tuple(unmatched_roles),
        missing_predicates=tuple(missing_predicates),
        missing_relation_kinds=tuple(missing_relation_kinds),
        resolved_role_symbols=resolved_symbols,
    )


def match_all_templates(
    templates: Iterable[BehaviorTemplateV1],
    graph: CodeBehaviorGraphV1,
) -> list[BehaviorTemplateMatchV1]:
    """Match all registered templates against a behavior graph.

    Returns matches sorted by ``match_score`` descending, then by
    ``template_id`` for determinism.  Only matched templates (``matched
    == True``) are included when ``matched_only=True`` (default).
    """

    matches = [match_template(template, graph) for template in templates]
    matches.sort(key=lambda m: (-m.match_score, m.template_id))
    return matches


def select_composable_templates(
    matches: list[BehaviorTemplateMatchV1],
    templates: Iterable[BehaviorTemplateV1],
) -> list[BehaviorTemplateMatchV1]:
    """Select a composable subset of matched templates.

    Two matched templates compose when:

    - each declares the other in its ``composable_with`` set; AND
    - their matched role aliases are disjoint (no role conflict).

    The selection is greedy: starting from the highest-scoring matched
    template, add each subsequent matched template that composes with
    every already-selected template.
    """

    templates_by_id = {t.template_id: t for t in templates}
    matched = [m for m in matches if m.matched]
    if not matched:
        return []

    selected: list[BehaviorTemplateMatchV1] = []
    selected_roles: set[str] = set()
    selected_ids: set[str] = set()

    for candidate in matched:
        candidate_template = templates_by_id.get(candidate.template_id)
        if candidate_template is None:
            continue
        # Check composability with all already-selected templates.
        composable = True
        for selected_id in selected_ids:
            selected_template = templates_by_id.get(selected_id)
            if selected_template is None:
                composable = False
                break
            if candidate.template_id not in selected_template.composable_with:
                composable = False
                break
            if selected_id not in candidate_template.composable_with:
                composable = False
                break
        # Check role disjointness.
        candidate_roles = set(candidate.matched_role_aliases)
        if candidate_roles & selected_roles:
            composable = False
        if composable:
            selected.append(candidate)
            selected_ids.add(candidate.template_id)
            selected_roles.update(candidate_roles)

    return selected


def _resolve_role_alias(
    graph: CodeBehaviorGraphV1,
    alias: RoleAliasV1,
) -> str | None:
    """Resolve a role alias to a symbol id.

    A role resolves when at least one symbol's behavior nodes contain
    ALL the role's required predicates.  When multiple symbols qualify,
    the one with the most matching nodes wins (deterministic tie-break
    by symbol_id).
    """

    if not alias.required_predicates:
        return None
    # Group nodes by symbol_id and count how many distinct required
    # predicates each symbol covers.
    symbol_predicates: dict[str, set[str]] = {}
    for node in graph.nodes:
        if node.predicate in alias.required_predicates:
            symbol_predicates.setdefault(node.symbol_id, set()).add(node.predicate)
    # A symbol qualifies when it covers all required predicates.
    qualified = [
        (sid, preds)
        for sid, preds in symbol_predicates.items()
        if alias.required_predicates <= preds
    ]
    if not qualified:
        return None
    # Tie-break: most matching nodes (proxy: most distinct predicates),
    # then lexicographically smallest symbol_id.
    qualified.sort(key=lambda item: (-len(item[1]), item[0]))
    return qualified[0][0]


# ---------------------------------------------------------------------------
# Default templates (R7 section 10)
# ---------------------------------------------------------------------------


#: The four composable behavior templates required by R7.
DEFAULT_BEHAVIOR_TEMPLATES: tuple[BehaviorTemplateV1, ...] = (
    BehaviorTemplateV1(
        template_id="feature_predict_score_rank_filter",
        description=(
            "Feature-based prediction with score computation, ranking, "
            "top-k selection and filtering.  Common in recommenders and "
            "feature-scoring pipelines."
        ),
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"COMPUTE", "SORT", "TOPK", "FILTER"}),
            optional_predicates=frozenset({"READ", "PROJECT"}),
            predicate_order_hint=("COMPUTE", "SORT", "TOPK", "FILTER"),
        ),
        role_aliases=(
            RoleAliasV1(
                role="predictor",
                required_predicates=frozenset({"COMPUTE"}),
                optional_predicates=frozenset({"PROJECT"}),
                description="Computes a score from input features.",
            ),
            RoleAliasV1(
                role="ranker",
                required_predicates=frozenset({"SORT", "TOPK"}),
                description="Sorts scores and selects the top-k.",
            ),
            RoleAliasV1(
                role="filter",
                required_predicates=frozenset({"FILTER"}),
                description="Filters the ranked results by a criterion.",
            ),
        ),
        stage_hints=(
            StageHintV1(
                stage_name="score_prediction",
                purpose="Compute scores from input features.",
                role_order=("predictor",),
                organization_priority=1,
            ),
            StageHintV1(
                stage_name="ranking_selection",
                purpose="Sort scores and select the top-k candidates.",
                role_order=("ranker",),
                organization_priority=2,
            ),
            StageHintV1(
                stage_name="filtering",
                purpose="Filter the ranked candidates by a criterion.",
                role_order=("filter",),
                organization_priority=3,
            ),
        ),
        composable_with=frozenset({
            "embedding_augment_dual_attention_rerank",
        }),
    ),
    BehaviorTemplateV1(
        template_id="embedding_augment_dual_attention_rerank",
        description=(
            "Embedding augmentation with dual attention (self + cross) "
            "and a reranking stage.  Common in retrieval and reranking "
            "architectures."
        ),
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"ATTEND", "CONCAT", "SORT", "TOPK"}),
            optional_predicates=frozenset({"READ", "TRANSFORM", "NORMALIZE"}),
            predicate_order_hint=("ATTEND", "CONCAT", "ATTEND", "SORT", "TOPK"),
        ),
        role_aliases=(
            RoleAliasV1(
                role="embedder",
                required_predicates=frozenset({"READ"}),
                optional_predicates=frozenset({"TRANSFORM", "NORMALIZE"}),
                description="Reads and transforms input embeddings.",
            ),
            RoleAliasV1(
                role="self_attention",
                required_predicates=frozenset({"ATTEND"}),
                description="Applies self-attention to the embeddings.",
            ),
            RoleAliasV1(
                role="cross_attention",
                required_predicates=frozenset({"ATTEND", "CONCAT"}),
                description="Applies cross-attention with concatenation fusion.",
            ),
            RoleAliasV1(
                role="reranker",
                required_predicates=frozenset({"SORT", "TOPK"}),
                description="Reranks the attended representations.",
            ),
        ),
        stage_hints=(
            StageHintV1(
                stage_name="embedding_augmentation",
                purpose="Read and augment input embeddings.",
                role_order=("embedder",),
                organization_priority=1,
            ),
            StageHintV1(
                stage_name="dual_attention",
                purpose="Apply self-attention then cross-attention fusion.",
                role_order=("self_attention", "cross_attention"),
                organization_priority=2,
            ),
            StageHintV1(
                stage_name="reranking",
                purpose="Rerank the attended representations.",
                role_order=("reranker",),
                organization_priority=3,
            ),
        ),
        composable_with=frozenset({
            "feature_predict_score_rank_filter",
        }),
    ),
    BehaviorTemplateV1(
        template_id="temporal_multichannel_sequence_readout",
        description=(
            "Temporal multi-channel sequence readout: reads multiple "
            "temporal channels, concatenates them, and aggregates into a "
            "sequence-level readout.  Common in time-series and sequence "
            "modeling."
        ),
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"READ", "CONCAT", "AGGREGATE", "REDUCE"}),
            optional_predicates=frozenset({"TRANSFORM", "STACK"}),
            predicate_order_hint=("READ", "CONCAT", "AGGREGATE", "REDUCE"),
        ),
        role_aliases=(
            RoleAliasV1(
                role="temporal_reader",
                required_predicates=frozenset({"READ"}),
                description="Reads temporal channel inputs.",
            ),
            RoleAliasV1(
                role="channel_merger",
                required_predicates=frozenset({"CONCAT"}),
                optional_predicates=frozenset({"STACK"}),
                description="Concatenates multiple channels.",
            ),
            RoleAliasV1(
                role="readout",
                required_predicates=frozenset({"AGGREGATE", "REDUCE"}),
                description="Aggregates and reduces to a sequence readout.",
            ),
        ),
        stage_hints=(
            StageHintV1(
                stage_name="temporal_channel_reading",
                purpose="Read multiple temporal channels.",
                role_order=("temporal_reader",),
                organization_priority=1,
            ),
            StageHintV1(
                stage_name="channel_merging",
                purpose="Merge channels via concatenation.",
                role_order=("channel_merger",),
                organization_priority=2,
            ),
            StageHintV1(
                stage_name="sequence_readout",
                purpose="Aggregate and reduce to a sequence-level readout.",
                role_order=("readout",),
                organization_priority=3,
            ),
        ),
        composable_with=frozenset(),
    ),
    BehaviorTemplateV1(
        template_id="sparse_bipartite_propagation_ppr",
        description=(
            "Sparse bipartite propagation with personalized PageRank "
            "(PPR) reduction.  Common in graph neural networks with "
            "neighbor sampling and PPR-based readout."
        ),
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"SAMPLE", "PROPAGATE", "REDUCE"}),
            required_relation_kinds=frozenset({"DATA_DEPENDS_ON"}),
            optional_predicates=frozenset({"AGGREGATE", "FILTER"}),
            predicate_order_hint=("SAMPLE", "PROPAGATE", "REDUCE"),
        ),
        role_aliases=(
            RoleAliasV1(
                role="sampler",
                required_predicates=frozenset({"SAMPLE"}),
                optional_predicates=frozenset({"FILTER"}),
                description="Samples bipartite neighbors.",
            ),
            RoleAliasV1(
                role="propagator",
                required_predicates=frozenset({"PROPAGATE"}),
                description="Propagates messages across the bipartite graph.",
            ),
            RoleAliasV1(
                role="ppr_reducer",
                required_predicates=frozenset({"REDUCE"}),
                optional_predicates=frozenset({"AGGREGATE"}),
                description="Reduces propagated messages via PPR.",
            ),
        ),
        stage_hints=(
            StageHintV1(
                stage_name="bipartite_sampling",
                purpose="Sample bipartite neighbors.",
                role_order=("sampler",),
                organization_priority=1,
            ),
            StageHintV1(
                stage_name="message_propagation",
                purpose="Propagate messages across the bipartite graph.",
                role_order=("propagator",),
                organization_priority=2,
            ),
            StageHintV1(
                stage_name="ppr_reduction",
                purpose="Reduce propagated messages via personalized PageRank.",
                role_order=("ppr_reducer",),
                organization_priority=3,
            ),
        ),
        composable_with=frozenset(),
    ),
)


def _to_discovery_template_v2(
    template: BehaviorTemplateV1,
) -> BehaviorDiscoveryTemplateV2:
    """Strip every prose-bearing V1 field at the production boundary."""

    query_hints = tuple(
        DiscoveryQueryHintV2(hint_kind="predicate", value=predicate)
        for predicate in sorted(template.query.required_predicates)
    ) + tuple(
        DiscoveryQueryHintV2(hint_kind="relation", value=relation)
        for relation in sorted(template.query.required_relation_kinds)
    )
    return BehaviorDiscoveryTemplateV2(
        template_id=template.template_id,
        query=template.query,
        role_aliases=tuple(
            DiscoveryRoleHintV2(
                role=alias.role,
                required_predicates=alias.required_predicates,
                optional_predicates=alias.optional_predicates,
            )
            for alias in template.role_aliases
        ),
        stage_hints=tuple(
            DiscoveryStageHintV2(
                stage_name=hint.stage_name,
                role_order=hint.role_order,
                organization_priority=hint.organization_priority,
            )
            for hint in template.stage_hints
        ),
        query_hints=query_hints,
        composable_with=template.composable_with,
    )


DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES: tuple[
    BehaviorDiscoveryTemplateV2, ...
] = tuple(_to_discovery_template_v2(item) for item in DEFAULT_BEHAVIOR_TEMPLATES)


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------


class BehaviorTemplateRegistry:
    """A registry of composable behavior templates.

    The registry is the integration point between the template module
    and the rest of the agent.  The supervisor calls
    ``registry.match(graph)`` to get the ranked list of template matches
    for the current behavior graph, then ``registry.select_composable``
    to pick a composable subset for Method organization.

    The registry NEVER authorizes claims: it only provides structural
    matches and role resolutions.  Fact authorization is the generic
    compiler's job.
    """

    def __init__(self, templates: Iterable[BehaviorTemplateV1] | None = None) -> None:
        self._templates: list[BehaviorTemplateV1] = list(templates or DEFAULT_BEHAVIOR_TEMPLATES)
        self._by_id: dict[str, BehaviorTemplateV1] = {
            t.template_id: t for t in self._templates
        }
        self._assert_unique_ids()

    def _assert_unique_ids(self) -> None:
        ids = [t.template_id for t in self._templates]
        duplicates = {tid for tid in ids if ids.count(tid) > 1}
        if duplicates:
            raise ValueError(f"duplicate template ids: {sorted(duplicates)}")

    @property
    def templates(self) -> tuple[BehaviorTemplateV1, ...]:
        return tuple(self._templates)

    def register(self, template: BehaviorTemplateV1) -> None:
        if template.template_id in self._by_id:
            raise ValueError(f"template already registered: {template.template_id}")
        self._templates.append(template)
        self._by_id[template.template_id] = template

    def match(self, graph: CodeBehaviorGraphV1) -> list[BehaviorTemplateMatchV1]:
        return match_all_templates(self._templates, graph)

    def select_composable(
        self, matches: list[BehaviorTemplateMatchV1] | None = None,
        graph: CodeBehaviorGraphV1 | None = None,
    ) -> list[BehaviorTemplateMatchV1]:
        if matches is None:
            if graph is None:
                raise ValueError("either matches or graph must be provided")
            matches = self.match(graph)
        return select_composable_templates(matches, self._templates)

    def get(self, template_id: str) -> BehaviorTemplateV1 | None:
        return self._by_id.get(template_id)


# ---------------------------------------------------------------------------
# Validation: templates must not contain forbidden content
# ---------------------------------------------------------------------------


#: Project-specific literals that MUST NOT appear in any template field.
#: These are the four real projects used for validation (R7 section 10).
_FORBIDDEN_PROJECT_LITERALS: frozenset[str] = frozenset({
    "rap", "ebcar", "dyg-mamba", "dyg_mamba", "dygmamba", "linear rag",
    "linearrag", "linear_rag",
})


def assert_template_free_of_project_literals(template: BehaviorTemplateV1) -> None:
    """Assert that a template contains no project-specific literals.

    R7 hard constraint: templates MUST NOT contain project names as
    required conditions, absolute file paths, project claim text, fixed
    evidence ids, or fixed fact ids.  This function scans every string
    field of the template for the forbidden project literals.

    Matching uses word boundaries so a short project name like ``rap``
    does not match the substring inside ``PageRank``.  Hyphens and
    underscores in project names (``dyg-mamba``, ``linear_rag``) are
    treated as word characters for the boundary check.
    """

    import re

    # Build a single alternation pattern with word boundaries.  We
    # escape each literal and replace internal separators so they match
    # either hyphen or underscore.
    escaped: list[str] = []
    for literal in _FORBIDDEN_PROJECT_LITERALS:
        # Normalize hyphens/underscores to a character class so both
        # variants match.
        pattern = re.escape(literal).replace(re.escape("-"), "[-_]").replace(
            re.escape("_"), "[-_]"
        )
        escaped.append(pattern)
    combined = "|".join(escaped)
    # Use lookarounds for word boundaries that treat ONLY ASCII
    # alphanumerics as word characters.  Hyphens and underscores are
    # treated as separators so "ebcar" IS flagged inside
    # "ebcar_stage" / "ebcar-stage", but "rap" is NOT flagged inside
    # "pagerank" (because 'e' precedes 'rap' there).
    boundary_pattern = re.compile(
        r"(?<![a-z0-9])(" + combined + r")(?![a-z0-9])",
        re.IGNORECASE,
    )

    def _check(value: str, field_path: str) -> None:
        match = boundary_pattern.search(value)
        if match:
            raise ValueError(
                f"template {template.template_id!r} field {field_path!r} "
                f"contains forbidden project literal {match.group(1)!r}"
            )

    _check(template.template_id, "template_id")
    _check(template.description, "description")
    for predicate in template.query.required_predicates:
        _check(predicate, "query.required_predicates")
    for predicate in template.query.optional_predicates:
        _check(predicate, "query.optional_predicates")
    for predicate in template.query.forbidden_predicates:
        _check(predicate, "query.forbidden_predicates")
    for predicate in template.query.predicate_order_hint:
        _check(predicate, "query.predicate_order_hint")
    for kind in template.query.required_relation_kinds:
        _check(kind, "query.required_relation_kinds")
    for alias in template.role_aliases:
        _check(alias.role, f"role_aliases.{alias.role}.role")
        _check(alias.description, f"role_aliases.{alias.role}.description")
    for hint in template.stage_hints:
        _check(hint.stage_name, f"stage_hints.{hint.stage_name}.stage_name")
        _check(hint.purpose, f"stage_hints.{hint.stage_name}.purpose")
        for role in hint.role_order:
            _check(role, f"stage_hints.{hint.stage_name}.role_order")
    for other in template.composable_with:
        _check(other, "composable_with")


def assert_all_templates_free_of_project_literals(
    templates: Iterable[BehaviorTemplateV1] = DEFAULT_BEHAVIOR_TEMPLATES,
) -> None:
    """Assert that every registered template is free of project literals.

    Called at module import time to enforce the R7 hard constraint
    continuously.
    """

    for template in templates:
        assert_template_free_of_project_literals(template)


# Run the constraint check at import time so any regression fails loudly.
assert_all_templates_free_of_project_literals()


__all__ = [
    "BehaviorTemplateQueryV1",
    "RoleAliasV1",
    "StageHintV1",
    "BehaviorTemplateV1",
    "DiscoveryQueryHintV2",
    "DiscoveryRoleHintV2",
    "DiscoveryStageHintV2",
    "BehaviorDiscoveryTemplateV2",
    "BehaviorTemplateMatchV1",
    "DEFAULT_BEHAVIOR_TEMPLATES",
    "DEFAULT_BEHAVIOR_DISCOVERY_TEMPLATES",
    "BehaviorTemplateRegistry",
    "match_template",
    "match_all_templates",
    "select_composable_templates",
    "assert_template_free_of_project_literals",
    "assert_all_templates_free_of_project_literals",
]
