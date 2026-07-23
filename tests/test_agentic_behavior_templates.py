"""R7 tests for composable behavior templates.

Verifies that ``behavior_templates.py`` correctly:

- registers the four required templates (design section 10);
- enforces the R7 hard constraints (no project names, file paths,
  claim text, fixed evidence/fact ids, direct authorization);
- matches templates structurally against a behavior graph using
  predicate / relation coverage;
- resolves role aliases to symbol ids deterministically;
- selects composable subsets with disjoint roles;
- never affects fact authorization (the generic compiler remains
  authoritative);
- produces a non-zero match score for graphs that cover the template's
  required predicates, and zero for empty templates.

The fixtures here are project-agnostic: they use only the generic V1
behavior graph vocabulary.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.behavior_graph import (
    BEHAVIOR_PREDICATES,
    BEHAVIOR_RELATION_KINDS,
    BehaviorNodeV1,
    BehaviorRelationV1,
    CodeBehaviorGraphV1,
    make_span_id,
    make_symbol_id,
)
from code2paper.agentic.behavior_templates import (
    DEFAULT_BEHAVIOR_TEMPLATES,
    BehaviorTemplateMatchV1,
    BehaviorTemplateQueryV1,
    BehaviorTemplateRegistry,
    BehaviorTemplateV1,
    RoleAliasV1,
    StageHintV1,
    assert_all_templates_free_of_project_literals,
    assert_template_free_of_project_literals,
    match_all_templates,
    match_template,
    select_composable_templates,
)
from code2paper.agentic.research_nodes import _behavior_template_search_hints


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _node(
    symbol_id: str,
    predicate: str,
    *,
    span_id: str | None = None,
    seq: int = 0,
) -> BehaviorNodeV1:
    return BehaviorNodeV1(
        node_id=BehaviorNodeV1.make_node_id(
            symbol_id=symbol_id,
            source_span_id=span_id or f"span:{symbol_id}:1:10",
            predicate=predicate,
            seq=seq,
        ),
        symbol_id=symbol_id,
        operation_id=f"op-{predicate.lower()}-{seq}",
        predicate=predicate,
        operands=("x",),
        result="y",
        source_span_id=span_id or f"span:{symbol_id}:1:10",
    )


def _relation(
    *,
    kind: str,
    source_symbol_id: str,
    target_symbol_id: str = "",
    source_node_id: str = "",
    target_node_id: str = "",
    seq: int = 0,
) -> BehaviorRelationV1:
    return BehaviorRelationV1(
        relation_id=BehaviorRelationV1.make_relation_id(
            kind=kind,
            source_node_id=source_node_id or f"node-src-{seq}",
            target_node_id=target_node_id,
            seq=seq,
        ),
        kind=kind,
        source_node_id=source_node_id or f"node-src-{seq}",
        target_node_id=target_node_id,
        source_symbol_id=source_symbol_id,
        target_symbol_id=target_symbol_id,
        source_span_id=f"span:{source_symbol_id}:1:10",
    )


def _graph(
    nodes: list[BehaviorNodeV1],
    relations: list[BehaviorRelationV1] | None = None,
) -> CodeBehaviorGraphV1:
    graph = CodeBehaviorGraphV1(
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        nodes=nodes,
        relations=list(relations or []),
    )
    return graph.with_digest()


# ---------------------------------------------------------------------------
# R7 section 10: the four required templates are registered
# ---------------------------------------------------------------------------


def test_four_required_templates_are_registered() -> None:
    """The four templates named in R7 section 10 must be in the default
    registry.
    """

    template_ids = {t.template_id for t in DEFAULT_BEHAVIOR_TEMPLATES}
    assert template_ids == {
        "feature_predict_score_rank_filter",
        "embedding_augment_dual_attention_rerank",
        "temporal_multichannel_sequence_readout",
        "sparse_bipartite_propagation_ppr",
    }


def test_partial_template_match_becomes_non_authorizing_supervisor_hint(monkeypatch) -> None:
    graph = _graph([_node("sym:fixture:score", "COMPUTE")])
    monkeypatch.setenv("CODE2PAPER_AGENTIC_BEHAVIOR_TEMPLATES", "1")
    hints = _behavior_template_search_hints(graph)
    target = next(
        item for item in hints
        if item.template_id == "feature_predict_score_rank_filter"
    )
    assert not target.matched
    assert target.match_score > 0
    assert set(target.missing_predicates) == {"SORT", "TOPK", "FILTER"}
    assert target.predicate_order_hint == ("COMPUTE", "SORT", "TOPK", "FILTER")


def test_template_search_hints_can_be_disabled_without_affecting_graph(monkeypatch) -> None:
    graph = _graph([_node("sym:fixture:score", "COMPUTE")])
    original_digest = graph.content_digest
    monkeypatch.setenv("CODE2PAPER_AGENTIC_BEHAVIOR_TEMPLATES", "0")
    assert _behavior_template_search_hints(graph) == ()
    assert graph.content_digest == original_digest


def test_registry_default_templates_match_default_constant() -> None:
    registry = BehaviorTemplateRegistry()
    assert set(registry.templates) == set(DEFAULT_BEHAVIOR_TEMPLATES)


def test_registry_rejects_duplicate_template_ids() -> None:
    template = DEFAULT_BEHAVIOR_TEMPLATES[0]
    registry = BehaviorTemplateRegistry([template])
    with pytest.raises(ValueError, match="already registered"):
        registry.register(template)


# ---------------------------------------------------------------------------
# R7 hard constraints: no project-specific content
# ---------------------------------------------------------------------------


def test_all_default_templates_pass_project_literal_check() -> None:
    """The import-time assertion already enforces this, but we test it
    explicitly so a future template addition cannot regress.
    """

    assert_all_templates_free_of_project_literals(DEFAULT_BEHAVIOR_TEMPLATES)


def test_template_with_project_name_in_description_is_rejected() -> None:
    template = BehaviorTemplateV1(
        template_id="test_template",
        description="A template that mentions rap project.",
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"COMPUTE"}),
        ),
    )
    with pytest.raises(ValueError, match="forbidden project literal"):
        assert_template_free_of_project_literals(template)


def test_template_with_project_name_in_stage_hint_is_rejected() -> None:
    template = BehaviorTemplateV1(
        template_id="test_template",
        description="A clean template.",
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"COMPUTE"}),
        ),
        stage_hints=(
            StageHintV1(
                stage_name="ebcar_stage",
                purpose="A stage named after a project.",
                role_order=(),
            ),
        ),
    )
    with pytest.raises(ValueError, match="forbidden project literal"):
        assert_template_free_of_project_literals(template)


def test_template_with_project_name_in_role_alias_is_rejected() -> None:
    template = BehaviorTemplateV1(
        template_id="test_template",
        description="A clean template.",
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"COMPUTE"}),
        ),
        role_aliases=(
            RoleAliasV1(
                role="dyg_mamba_role",
                required_predicates=frozenset({"COMPUTE"}),
                description="A role named after a project.",
            ),
        ),
    )
    with pytest.raises(ValueError, match="forbidden project literal"):
        assert_template_free_of_project_literals(template)


def test_pagerank_in_description_is_not_flagged() -> None:
    """``PageRank`` contains the substring ``rap`` but is NOT a project
    name.  The word-boundary check must not flag it.
    """

    template = BehaviorTemplateV1(
        template_id="test_template",
        description="Uses personalized PageRank for reduction.",
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"REDUCE"}),
        ),
    )
    # Must NOT raise.
    assert_template_free_of_project_literals(template)


def test_template_with_absolute_file_path_pattern_is_not_required() -> None:
    """Templates cannot reference absolute file paths.  We verify the
    default templates have no path-like strings in their queries.
    """

    for template in DEFAULT_BEHAVIOR_TEMPLATES:
        # No query field should contain "/" or "\\" (path separators).
        for predicate in template.query.required_predicates:
            assert "/" not in predicate
            assert "\\" not in predicate
        for kind in template.query.required_relation_kinds:
            assert "/" not in kind
            assert "\\" not in kind


def test_templates_never_authorize_claims() -> None:
    """Templates provide structural matches and role resolutions only.
    They MUST NOT produce claim text, evidence ids, or fact ids.  The
    ``BehaviorTemplateMatchV1`` model has no field for claims, evidence,
    or facts -- only structural information.
    """

    fields = set(BehaviorTemplateMatchV1.model_fields.keys())
    # The match result must not contain claim/evidence/fact fields.
    forbidden_fields = {"claim_ids", "evidence_ids", "fact_ids", "claim_text"}
    assert not (fields & forbidden_fields)


# ---------------------------------------------------------------------------
# Matching: structural coverage
# ---------------------------------------------------------------------------


def test_match_template_full_coverage_scores_high() -> None:
    """A graph that covers all required predicates + relations matches
    with a high score.
    """

    template = DEFAULT_BEHAVIOR_TEMPLATES[0]  # feature_predict_score_rank_filter
    # Build a graph with all four required predicates.
    symbol = make_symbol_id("path/to/mod.py", "predictor_fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
    ]
    graph = _graph(nodes)

    match = match_template(template, graph)

    assert match.matched
    assert match.match_score > 0.0
    assert match.matched_predicate_count == 4
    assert match.required_predicate_count == 4
    assert match.missing_predicates == ()


def test_match_template_partial_coverage_does_not_match() -> None:
    """A graph missing a required predicate does not match (matched=False),
    but the match_score is still computed for ranking.
    """

    template = DEFAULT_BEHAVIOR_TEMPLATES[0]  # requires COMPUTE, SORT, TOPK, FILTER
    symbol = make_symbol_id("path/to/mod.py", "predictor_fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        # Missing TOPK and FILTER.
    ]
    graph = _graph(nodes)

    match = match_template(template, graph)

    assert not match.matched
    assert "TOPK" in match.missing_predicates
    assert "FILTER" in match.missing_predicates
    assert match.matched_predicate_count == 2
    assert match.required_predicate_count == 4


def test_match_template_with_required_relation_kind() -> None:
    """The sparse_bipartite_propagation_ppr template requires a
    DATA_DEPENDS_ON relation.  A graph without it does not match.
    """

    template = next(
        t for t in DEFAULT_BEHAVIOR_TEMPLATES
        if t.template_id == "sparse_bipartite_propagation_ppr"
    )
    symbol = make_symbol_id("path/to/mod.py", "propagate_fn", 1)
    nodes = [
        _node(symbol, "SAMPLE", seq=0),
        _node(symbol, "PROPAGATE", seq=1),
        _node(symbol, "REDUCE", seq=2),
    ]
    # No DATA_DEPENDS_ON relation -> should not match.
    graph_no_relation = _graph(nodes)
    match_no = match_template(template, graph_no_relation)
    assert not match_no.matched
    assert "DATA_DEPENDS_ON" in match_no.missing_relation_kinds

    # With the relation -> should match.
    relation = _relation(
        kind="DATA_DEPENDS_ON",
        source_symbol_id=symbol,
        target_symbol_id=symbol,
        source_node_id=nodes[0].node_id,
        target_node_id=nodes[1].node_id,
    )
    graph_with_relation = _graph(nodes, [relation])
    match_with = match_template(template, graph_with_relation)
    assert match_with.matched


def test_match_template_empty_requirements_never_matches() -> None:
    """A template with no required predicates or relations never matches
    (it would match every graph and provide no information).
    """

    template = BehaviorTemplateV1(
        template_id="empty_template",
        description="A template with no requirements.",
        query=BehaviorTemplateQueryV1(),  # Empty query.
    )
    graph = _graph([_node("sym-1", "COMPUTE")])

    match = match_template(template, graph)
    assert not match.matched
    assert match.match_score == 0.0


def test_match_template_forbidden_predicate_blocks_match() -> None:
    """A template with a forbidden predicate does not match when the
    graph contains that predicate.
    """

    template = BehaviorTemplateV1(
        template_id="test_forbidden",
        description="A template that forbids SERIALIZE.",
        query=BehaviorTemplateQueryV1(
            required_predicates=frozenset({"COMPUTE"}),
            forbidden_predicates=frozenset({"SERIALIZE"}),
        ),
    )
    symbol = "sym-1"
    # Graph with COMPUTE and SERIALIZE -> forbidden blocks match.
    graph = _graph([
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SERIALIZE", seq=1),
    ])
    match = match_template(template, graph)
    assert not match.matched


# ---------------------------------------------------------------------------
# Role alias resolution
# ---------------------------------------------------------------------------


def test_role_alias_resolves_to_symbol_with_required_predicates() -> None:
    """A role alias resolves to the symbol whose nodes cover all the
    role's required predicates.
    """

    template = DEFAULT_BEHAVIOR_TEMPLATES[0]  # feature_predict_score_rank_filter
    predictor_sym = make_symbol_id("path/to/mod.py", "predictor_fn", 1)
    ranker_sym = make_symbol_id("path/to/mod.py", "ranker_fn", 10)
    filter_sym = make_symbol_id("path/to/mod.py", "filter_fn", 20)
    nodes = [
        _node(predictor_sym, "COMPUTE", seq=0),
        _node(ranker_sym, "SORT", seq=0),
        _node(ranker_sym, "TOPK", seq=1),
        _node(filter_sym, "FILTER", seq=0),
    ]
    graph = _graph(nodes)

    match = match_template(template, graph)

    assert match.matched
    assert "predictor" in match.matched_role_aliases
    assert "ranker" in match.matched_role_aliases
    assert "filter" in match.matched_role_aliases
    assert match.resolved_role_symbols["predictor"] == predictor_sym
    assert match.resolved_role_symbols["ranker"] == ranker_sym
    assert match.resolved_role_symbols["filter"] == filter_sym


def test_role_alias_unresolved_when_no_symbol_covers_predicates() -> None:
    """A role alias does not resolve when no single symbol covers all
    its required predicates (even if the predicates exist across
    different symbols).
    """

    template = DEFAULT_BEHAVIOR_TEMPLATES[0]  # ranker requires SORT + TOPK
    sym_a = make_symbol_id("path/to/mod.py", "sort_fn", 1)
    sym_b = make_symbol_id("path/to/mod.py", "topk_fn", 10)
    nodes = [
        _node(sym_a, "SORT", seq=0),  # SORT in one symbol
        _node(sym_b, "TOPK", seq=0),  # TOPK in a different symbol
        # Still need COMPUTE and FILTER for the template to match.
        _node(sym_a, "COMPUTE", seq=1),
        _node(sym_b, "FILTER", seq=1),
    ]
    graph = _graph(nodes)

    match = match_template(template, graph)

    # Template matches (all four required predicates present in graph).
    assert match.matched
    # But the "ranker" role does not resolve (no single symbol has both
    # SORT and TOPK).
    assert "ranker" in match.unmatched_role_aliases
    assert "ranker" not in match.matched_role_aliases
    assert "predictor" in match.matched_role_aliases  # COMPUTE in sym_a
    assert "filter" in match.matched_role_aliases  # FILTER in sym_b


def test_role_alias_resolution_is_deterministic() -> None:
    """The same (template, graph) pair always produces the same role
    resolution.
    """

    template = DEFAULT_BEHAVIOR_TEMPLATES[0]
    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
    ]
    graph = _graph(nodes)

    match1 = match_template(template, graph)
    match2 = match_template(template, graph)

    assert match1 == match2
    assert match1.resolved_role_symbols == match2.resolved_role_symbols


# ---------------------------------------------------------------------------
# match_all_templates: ranking
# ---------------------------------------------------------------------------


def test_match_all_templates_ranks_by_score_descending() -> None:
    """``match_all_templates`` returns matches sorted by score
    descending, then by template_id for determinism.
    """

    # Build a graph that fully matches feature_predict_score_rank_filter
    # and partially matches temporal_multichannel_sequence_readout.
    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
        # Partial match for temporal_multichannel: has READ and CONCAT
        # but not AGGREGATE or REDUCE.
        _node(symbol, "READ", seq=4),
        _node(symbol, "CONCAT", seq=5),
    ]
    graph = _graph(nodes)

    matches = match_all_templates(DEFAULT_BEHAVIOR_TEMPLATES, graph)

    # All four templates produce a match result.
    assert len(matches) == 4
    # Scores are non-increasing.
    scores = [m.match_score for m in matches]
    assert scores == sorted(scores, reverse=True)
    # The fully-matched template is first.
    assert matches[0].template_id == "feature_predict_score_rank_filter"
    assert matches[0].matched


def test_match_all_templates_tiebreak_by_template_id() -> None:
    """When two templates have the same score, they are sorted by
    template_id alphabetically.
    """

    # Empty graph: all templates have score 0.0 and matched=False.
    graph = _graph([])
    matches = match_all_templates(DEFAULT_BEHAVIOR_TEMPLATES, graph)

    ids = [m.template_id for m in matches]
    # All scores are 0.0, so sort by template_id.
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Composable selection
# ---------------------------------------------------------------------------


def test_select_composable_templates_picks_disjoint_roles() -> None:
    """``select_composable_templates`` greedily selects matched templates
    with disjoint role aliases.
    """

    # Build a graph that matches both feature_predict_score_rank_filter
    # and embedding_augment_dual_attention_rerank.  These two templates
    # declare each other as composable_with, and their roles are
    # disjoint (predictor/ranker/filter vs embedder/self_attention/
    # cross_attention/reranker).
    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        # feature_predict_score_rank_filter predicates.
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
        # embedding_augment_dual_attention_rerank predicates.
        _node(symbol, "ATTEND", seq=4),
        _node(symbol, "CONCAT", seq=5),
    ]
    graph = _graph(nodes)

    registry = BehaviorTemplateRegistry()
    matches = registry.match(graph)
    composable = registry.select_composable(matches=matches)

    # Both templates should be selected (they compose and have disjoint
    # roles).
    selected_ids = {m.template_id for m in composable}
    assert "feature_predict_score_rank_filter" in selected_ids
    assert "embedding_augment_dual_attention_rerank" in selected_ids
    # Roles are disjoint.
    all_roles: set[str] = set()
    for match in composable:
        roles = set(match.matched_role_aliases)
        assert not (roles & all_roles)  # No overlap.
        all_roles.update(roles)


def test_select_composable_skips_non_composable_templates() -> None:
    """A template that does not declare composability with the selected
    template is skipped.
    """

    # Build a graph that matches feature_predict_score_rank_filter and
    # temporal_multichannel_sequence_readout.  temporal_multichannel has
    # composable_with=frozenset(), so it does NOT compose with
    # feature_predict.
    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        # feature_predict_score_rank_filter.
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
        # temporal_multichannel_sequence_readout.
        _node(symbol, "READ", seq=4),
        _node(symbol, "CONCAT", seq=5),
        _node(symbol, "AGGREGATE", seq=6),
        _node(symbol, "REDUCE", seq=7),
    ]
    graph = _graph(nodes)

    registry = BehaviorTemplateRegistry()
    matches = registry.match(graph)
    composable = registry.select_composable(matches=matches)

    selected_ids = {m.template_id for m in composable}
    # Only feature_predict_score_rank_filter is selected (higher score,
    # and temporal_multichannel does not compose with it).
    assert "feature_predict_score_rank_filter" in selected_ids
    assert "temporal_multichannel_sequence_readout" not in selected_ids


def test_select_composable_empty_when_no_matches() -> None:
    """When no templates match, the composable selection is empty."""

    graph = _graph([])
    registry = BehaviorTemplateRegistry()
    composable = registry.select_composable(graph=graph)
    assert composable == []


# ---------------------------------------------------------------------------
# R7 exit condition: templates do not affect fact authorization
# ---------------------------------------------------------------------------


def test_templates_never_produce_facts_or_claims() -> None:
    """The R7 exit condition requires that templates only improve path
    discovery and organization, never fact authorization.  We verify
    that the template module's public API produces only
    ``BehaviorTemplateMatchV1`` objects, never facts or claims.
    """

    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
    ]
    graph = _graph(nodes)

    registry = BehaviorTemplateRegistry()
    matches = registry.match(graph)
    composable = registry.select_composable(matches=matches)

    # Every output is a BehaviorTemplateMatchV1 -- no facts or claims.
    for match in matches:
        assert isinstance(match, BehaviorTemplateMatchV1)
    for match in composable:
        assert isinstance(match, BehaviorTemplateMatchV1)


def test_generic_compiler_still_works_without_templates() -> None:
    """The R7 exit condition: with all templates disabled, the generic
    compiler MUST still produce some supported claims.  We verify the
    generic compiler is importable and produces facts from a behavior
    graph without any template involvement.
    """

    from code2paper.agentic.generic_fact_compiler import (
        FactCompilerInputV1,
        compile_facts_from_behavior_graph,
    )

    symbol = make_symbol_id("path/to/mod.py", "predictor_fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
    ]
    graph = _graph(nodes)

    compiler_input = FactCompilerInputV1(
        obligation_id="O-1",
        behavior_node_ids=[nodes[0].node_id],
        evidence_span_ids=[nodes[0].source_span_id],
        source_authority="executable_hard",
    )
    fact_set = compile_facts_from_behavior_graph(
        graph=graph,
        compiler_input=compiler_input,
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        evidence_packet_digest="sha256:packets",
    )

    # The generic compiler produced at least one supported fact without
    # any template involvement.
    assert len(fact_set.facts) >= 1
    supported = [f for f in fact_set.facts if f.validation_status == "supported"]
    assert len(supported) >= 1
    # The fact's predicate is the generic COMPUTE -> computes_formula.
    assert supported[0].predicate == "computes_formula"


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


def test_template_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BehaviorTemplateV1(
            template_id="test",
            description="d",
            query=BehaviorTemplateQueryV1(),
            surprise_field="not allowed",
        )


def test_query_model_rejects_unknown_predicates() -> None:
    with pytest.raises(ValueError, match="unknown behavior predicate"):
        BehaviorTemplateQueryV1(
            required_predicates=frozenset({"NOT_A_PREDICATE"}),
        )


def test_query_model_rejects_unknown_relation_kinds() -> None:
    with pytest.raises(ValueError, match="unknown behavior relation kind"):
        BehaviorTemplateQueryV1(
            required_relation_kinds=frozenset({"NOT_A_RELATION"}),
        )


def test_role_alias_rejects_unknown_predicates() -> None:
    with pytest.raises(ValueError, match="unknown behavior predicate"):
        RoleAliasV1(
            role="test",
            required_predicates=frozenset({"BOGUS"}),
        )


def test_match_model_is_frozen() -> None:
    match = BehaviorTemplateMatchV1(
        template_id="test",
        matched=True,
        match_score=0.5,
        matched_predicate_count=1,
        required_predicate_count=2,
        matched_relation_count=0,
        required_relation_count=0,
    )
    with pytest.raises(ValidationError):
        match.matched = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Template content: each template has role aliases and stage hints
# ---------------------------------------------------------------------------


def test_each_default_template_has_role_aliases_and_stage_hints() -> None:
    """Every R7 template must provide role aliases (for symbol
    resolution) and stage hints (for Method organization).
    """

    for template in DEFAULT_BEHAVIOR_TEMPLATES:
        assert template.role_aliases, f"{template.template_id} has no role aliases"
        assert template.stage_hints, f"{template.template_id} has no stage hints"
        # Every role mentioned in stage_hints must be defined in
        # role_aliases.
        defined_roles = {alias.role for alias in template.role_aliases}
        for hint in template.stage_hints:
            for role in hint.role_order:
                assert role in defined_roles, (
                    f"{template.template_id} stage hint {hint.stage_name} "
                    f"references undefined role {role!r}"
                )


def test_each_default_template_has_nonempty_query() -> None:
    """Every R7 template must have a non-empty query (required predicates
    or relation kinds).  An empty query never matches and provides no
    information.
    """

    for template in DEFAULT_BEHAVIOR_TEMPLATES:
        assert (
            template.query.required_predicates
            or template.query.required_relation_kinds
        ), f"{template.template_id} has an empty query"


def test_template_predicates_are_in_v1_vocabulary() -> None:
    """Every predicate referenced by a template must be in the V1
    ``BEHAVIOR_PREDICATES`` vocabulary.  This is enforced by the
    ``BehaviorTemplateQueryV1`` validator, but we test it explicitly.
    """

    predicate_set = set(BEHAVIOR_PREDICATES)
    for template in DEFAULT_BEHAVIOR_TEMPLATES:
        for predicate in template.query.required_predicates:
            assert predicate in predicate_set
        for predicate in template.query.optional_predicates:
            assert predicate in predicate_set


def test_template_relation_kinds_are_in_v1_vocabulary() -> None:
    """Every relation kind referenced by a template must be in the V1
    ``BEHAVIOR_RELATION_KINDS`` vocabulary.
    """

    relation_set = set(BEHAVIOR_RELATION_KINDS)
    for template in DEFAULT_BEHAVIOR_TEMPLATES:
        for kind in template.query.required_relation_kinds:
            assert kind in relation_set


# ---------------------------------------------------------------------------
# Integration: registry match -> composable selection
# ---------------------------------------------------------------------------


def test_registry_match_and_select_integration() -> None:
    """End-to-end: registry.match() -> registry.select_composable()
    produces a usable set of composable templates with resolved roles.
    """

    predictor_sym = make_symbol_id("path/to/mod.py", "predictor_fn", 1)
    ranker_sym = make_symbol_id("path/to/mod.py", "ranker_fn", 10)
    filter_sym = make_symbol_id("path/to/mod.py", "filter_fn", 20)
    embedder_sym = make_symbol_id("path/to/mod.py", "embedder_fn", 30)
    attention_sym = make_symbol_id("path/to/mod.py", "attention_fn", 40)
    reranker_sym = make_symbol_id("path/to/mod.py", "reranker_fn", 50)
    nodes = [
        # feature_predict_score_rank_filter.
        _node(predictor_sym, "COMPUTE", seq=0),
        _node(ranker_sym, "SORT", seq=0),
        _node(ranker_sym, "TOPK", seq=1),
        _node(filter_sym, "FILTER", seq=0),
        # embedding_augment_dual_attention_rerank.
        _node(embedder_sym, "READ", seq=0),
        _node(attention_sym, "ATTEND", seq=0),
        _node(attention_sym, "CONCAT", seq=1),
        _node(reranker_sym, "SORT", seq=0),
        _node(reranker_sym, "TOPK", seq=1),
    ]
    graph = _graph(nodes)

    registry = BehaviorTemplateRegistry()
    composable = registry.select_composable(graph=graph)

    # Both composable templates are selected.
    selected_ids = {m.template_id for m in composable}
    assert "feature_predict_score_rank_filter" in selected_ids
    assert "embedding_augment_dual_attention_rerank" in selected_ids

    # Every matched role alias resolved to a symbol id.
    for match in composable:
        assert match.matched_role_aliases
        for role in match.matched_role_aliases:
            assert role in match.resolved_role_symbols
            assert match.resolved_role_symbols[role]  # non-empty symbol id


def test_registry_get_returns_template_by_id() -> None:
    registry = BehaviorTemplateRegistry()
    template = registry.get("feature_predict_score_rank_filter")
    assert template is not None
    assert template.template_id == "feature_predict_score_rank_filter"
    assert registry.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Determinism: same graph -> same matches
# ---------------------------------------------------------------------------


def test_matching_is_deterministic_across_calls() -> None:
    """The same behavior graph always produces the same match results."""

    symbol = make_symbol_id("path/to/mod.py", "fn", 1)
    nodes = [
        _node(symbol, "COMPUTE", seq=0),
        _node(symbol, "SORT", seq=1),
        _node(symbol, "TOPK", seq=2),
        _node(symbol, "FILTER", seq=3),
    ]
    graph = _graph(nodes)

    registry = BehaviorTemplateRegistry()
    matches1 = registry.match(graph)
    matches2 = registry.match(graph)

    assert matches1 == matches2
