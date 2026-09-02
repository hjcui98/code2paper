"""Regression tests for live-bound Method authoring repair (2026-08-23)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from code2paper.agentic.formalization_agent import (
    AuthorIntentSectionFormalizerResponseV1,
    SectionFormulaPackageV1,
    coerce_section_formalizer_response,
    validate_section_formula_package,
)
from code2paper.agentic.method_argument_brief_models import (
    AuthorMechanismFacetV1,
    MethodArgumentBriefV1,
)
from code2paper.agentic.method_argument_facet_aligner import (
    _alignment_from_proposition_judge,
    _default_facet_required,
    _decompose_brief,
    _facet_from_row,
    _formula_expectation,
    _has_author_formula_signal,
    decompose_and_align_argument_facets,
)
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2, IntentObligationV2
from code2paper.agentic.method_architect import (
    _CandidateRowEntry,
    _fold_leftover_author_statement_buckets,
    _heading_is_author_instruction,
    _stabilize_plan_section_ids,
    _bucket_is_leftover_author_statement,
    _bucket_links_organization,
)
from code2paper.agentic.publication_method_writer import (
    _candidate_incomplete_section_ids,
    _facet_body_covers,
    _facet_required_for_section,
    _formula_package_rendered,
    _invoke_section_formalizer_llm,
    _looks_like_caveat_shell,
    _markdown_has_non_heading_body,
    _normalize_section_heading_breaks,
    _prose_has_repeated_phrase_spam,
    _section_formula_obligations,
    _section_output_acceptable,
    _with_normalized_section_markdown,
    _writer_facet_coverage,
    _writer_retry_failure_code,
    _writer_retry_required_action,
    _writing_request_is_locally_unfulfillable,
)
from code2paper.llm.section_writer import WriterSectionInput
from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    SectionArgumentGraphV1,
    MethodSectionPlanV2,
)
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1
from code2paper.llm.section_writer import (
    _apply_writer_context_clamp,
    _llm_visible_section_payload,
    _merge_publication_partition_outputs,
    _publication_section_partitions,
    _sanitize_publication_output_overlap,
    _writer_call_max_output_tokens,
    _writer_request_exceeds_context_window,
    WriterSectionInput,
)
from code2paper.schemas import LLMConfig


def test_empty_unsupported_judge_becomes_unresolved() -> None:
    facet = AuthorMechanismFacetV1(
        facet_id="facet:test",
        clause_id="clause:test",
        facet_kind="mechanism",
        semantic_fields={"operation": "encode"},
        search_terms=("test",),
        exact_source_quote="author says mechanism",
    )
    verdict = SimpleNamespace(
        status="unsupported",
        supported_fields=(),
        unsupported_fields=(),
        rationale="",
    )
    alignment = _alignment_from_proposition_judge(
        verdict,
        facet=facet,
        candidate_rows=(),
    )
    assert alignment.status == "unresolved"


def test_latex_macros_do_not_trigger_undefined_symbols() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:score",
                subject="forward",
                predicate="computes_formula",
                object="score",
                scope="sym:forward",
                direct_span_ids=["span:1"],
                semantic_context=["SCORE"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:score",
                validation_status="supported",
            )
        ],
        content_digest="sha256:facts",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[
            EquationClaimV1(
                equation_id="equation:score",
                expression="s = w @ x + b",
                fact_ids=["fact:score"],
                symbol_bindings=[
                    EquationSymbolBindingV1(
                        symbol="s", operand_role="result", operand_value="score", fact_id="fact:score"
                    ),
                ],
                canonical_identity="sha256:eq",
                validation_status="supported",
            )
        ],
        content_digest="sha256:eqs",
    )
    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S1:latex",
        section_id="MA-S1",
        purpose="Display score.",
        latex="\\begin{aligned} s &= w^\\top x + b \\end{aligned}",
        prose_explanation="The score uses a linear map with bias.",
        symbol_definitions=(("s", "score"), ("w", "weights"), ("x", "features"), ("b", "bias")),
        authority_status="author_intent",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(pkg, equations=equations, facts=facts)
    assert not any("undefined_symbols" in failure for failure in failures)


def test_sqrt_and_quad_macros_allowed() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:score",
                subject="forward",
                predicate="computes_formula",
                object="score",
                scope="sym:forward",
                direct_span_ids=["span:1"],
                semantic_context=["SCORE"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:score",
                validation_status="supported",
            )
        ],
        content_digest="sha256:facts",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[
            EquationClaimV1(
                equation_id="equation:score",
                expression="s = sqrt(x)",
                fact_ids=["fact:score"],
                symbol_bindings=[
                    EquationSymbolBindingV1(
                        symbol="s", operand_role="result", operand_value="score", fact_id="fact:score"
                    ),
                ],
                canonical_identity="sha256:eq",
                validation_status="supported",
            )
        ],
        content_digest="sha256:eqs",
    )
    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S1:sqrt",
        section_id="MA-S1",
        purpose="Display score.",
        latex="s = \\sqrt{x} \\quad \\text{for } x \\in \\mathbb{R}",
        prose_explanation="The score is the square root of features.",
        symbol_definitions=(("s", "score"), ("x", "features")),
        authority_status="author_intent",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
        formula_lane="author_intent_academic",
    )
    failures = validate_section_formula_package(pkg, equations=equations, facts=facts)
    assert not any("undefined_symbols" in failure for failure in failures)


def test_overlap_sanitizer_drops_deferred_ids() -> None:
    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="Mechanism prose about the design objective.",
        rendered_from_facet_ids=["facet:a"],
        deferred_facet_ids=["facet:a", "facet:b"],
    )
    sanitized = _sanitize_publication_output_overlap(output)
    assert "facet:a" in sanitized.rendered_from_facet_ids
    assert "facet:a" not in sanitized.deferred_facet_ids
    assert "facet:b" in sanitized.deferred_facet_ids


def test_partition_merge_unions_facet_witnesses() -> None:
    first = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="First partition body.",
        rendered_from_facet_ids=["facet:a"],
        deferred_facet_ids=[],
    )
    second = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        section_markdown="Second partition body.",
        rendered_from_facet_ids=["facet:b"],
        deferred_facet_ids=["facet:b"],
    )
    merged = _merge_publication_partition_outputs([first, second])
    assert "First partition body." in merged.section_markdown
    assert "Second partition body." in merged.section_markdown
    assert set(merged.rendered_from_facet_ids) == {"facet:a", "facet:b"}
    assert merged.deferred_facet_ids == ()


def test_writer_split_only_when_context_overflow() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={
            "writer_view": {
                "mechanism_authoring_packet": {
                    "facets": [{"facet_id": "facet:a", "text": "small"}],
                    "required_facet_ids": ["facet:a"],
                },
            },
            "binding_contract": {
                "allowed_facet_ids": ["facet:a"],
                "required_facet_ids": ["facet:a"],
            },
        },
        publication_mode=True,
        argument_graph={"moves": [{"move": "mechanism_overview", "paragraph_budget": 1}]},
    )
    config = LLMConfig(provider="openai", model="test", max_output_tokens=8192)
    partitions = _publication_section_partitions(
        section,
        system_prompt="Write method section.",
        response_json_schema={"type": "object"},
        config=config,
    )
    assert partitions == [section]
    huge_payload = {
        "section_id": "MA-S1",
        "heading": "Mechanism",
        "writer_view": {"blob": "x" * 600000},
    }
    assert _writer_request_exceeds_context_window(
        system_prompt="prompt",
        input_payload=huge_payload,
        response_json_schema={"type": "object"},
        config=config,
    )


def test_fold_leftover_author_statement_into_claim_bucket() -> None:
    row = SimpleNamespace(
        obligation_id="obl:long",
        statement="This leftover author sentence should not become its own section because it is far too long to serve as a heading without truncation.",
        role="motivation",
        status="author_confirmation_required",
    )
    candidate_buckets = [
        (
            row.statement,
            [_CandidateRowEntry(row, None)],
        )
    ]
    claim_buckets = [
        (
            "Core mechanism",
            [
                (
                    "SG-1",
                    "Core mechanism",
                    "Purpose",
                    [],
                    ("obl:core",),
                )
            ],
        )
    ]
    folded = _fold_leftover_author_statement_buckets(
        claim_buckets=claim_buckets,
        candidate_buckets=candidate_buckets,
    )
    assert folded == []
    assert len(claim_buckets[0][1]) == 2


def test_stabilize_section_ids_from_prior_plan() -> None:
    prior_graph = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Dynamic graph encoding",
        reader_question="How does encoding work?",
        argument_unit_ids=("MA-S1:unit",),
        primary_brief_ids=("brief:dyg",),
        story_node_ids=("story:encoding",),
    )
    prior_unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S1:unit",
        section_role="mechanism",
        research_question="How does encoding work?",
    )
    prior_plan = MethodSectionPlanV2(
        plan_id="plan:prior",
        method_name="Method",
        sections=(prior_graph,),
        argument_units=(prior_unit,),
    )
    new_graph = SectionArgumentGraphV1(
        section_id="MA-S2",
        heading="Dynamic graph encoding",
        reader_question="How does encoding work?",
        argument_unit_ids=("MA-S2:unit",),
        primary_brief_ids=("brief:dyg",),
        story_node_ids=("story:encoding",),
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S2:unit",
        section_role="mechanism",
        research_question="How does encoding work?",
        claim_ids=(),
        equation_ids=(),
        configuration_ids=(),
        allowed_expository_moves=("mechanism_overview",),
        unresolved_inputs=(),
        authority_lanes=("author_attested",),
        source_artifact_ids=(),
        supported=False,
    )
    units, graphs = _stabilize_plan_section_ids(
        units=[unit],
        graphs=[new_graph],
        prior_plan=prior_plan,
    )
    assert graphs[0].section_id == "MA-S1"
    assert units[0].argument_unit_id == "MA-S1:unit"


def test_compact_visible_payload_smaller_than_full_writer_view() -> None:
    full_view = {
        "purpose": {"heading": "Mechanism", "reader_question": "How?", "section_goal": "Explain"},
        "positive_briefs": [
            {"brief_id": "brief:a", "licensed_wording": "Licensed wording " * 200, "bound_claim_ids": ()},
        ],
        "caveated_briefs": [],
        "evidence_claim_texts": [
            {"brief_id": "brief:a", "claim_id": "claim:1", "canonical_text": "repo claim " * 100},
        ],
        "allowed_brief_ids": ["brief:a"],
        "required_brief_ids": ["brief:a"],
        "mechanism_authoring_packet": {
            "organization_seed": "seed",
            "required_facet_ids": ["facet:a"],
            "facets": [
                {
                    "facet_id": "facet:a",
                    "facet_kind": "mechanism",
                    "semantic_fields": {"operation": "encode", "paper_terms": ["graph"]},
                    "exact_source_quote": "author original wording " * 50,
                    "required": True,
                },
            ],
            "facet_policies": [{"facet_id": "facet:a", "prose_mode": "author_specification"}],
            "exact_evidence_excerpts": [
                {"facet_id": "facet:a", "span_id": "span:1", "text": "excerpt " * 200},
            ],
        },
    }
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={"writer_view": full_view},
        publication_mode=True,
    )
    compact = _llm_visible_section_payload(section)
    compact_view = compact["writer_view"]
    assert len(json.dumps(compact_view)) < len(json.dumps(full_view)) // 2
    assert "evidence_claim_texts" not in compact_view
    packet = compact_view["mechanism_authoring_packet"]
    assert "exact_evidence_excerpts" not in packet
    assert packet["facets"][0]["gist"]


def test_overflow_clamps_output_without_useless_partition() -> None:
    section = WriterSectionInput(
        section_id="MA-S1",
        heading="Mechanism",
        prompt_payload={
            "writer_view": {
                "purpose": {"heading": "Mechanism"},
                "mechanism_authoring_packet": {
                    "facets": [{"facet_id": "facet:a", "semantic_fields": {"operation": "encode"}}],
                    "required_facet_ids": ["facet:a"],
                },
            },
            "binding_contract": {
                "allowed_facet_ids": ["facet:a"],
                "required_facet_ids": ["facet:a"],
            },
        },
        publication_mode=True,
        argument_graph={"moves": [{"move": "mechanism_overview"}]},
    )
    config = LLMConfig(
        provider="openai",
        model="test",
        max_output_tokens=8192,
        max_input_tokens=131072,
    )
    system_prompt = "Write method section."
    schema = {"type": "object"}
    visible = {
        "section_id": "MA-S1",
        "heading": "Mechanism",
        **_llm_visible_section_payload(section),
    }
    partitions = _publication_section_partitions(
        section,
        system_prompt=system_prompt,
        response_json_schema=schema,
        config=config,
    )
    assert partitions == [section]
    near_window_input = {
        "section_id": "MA-S1",
        "heading": "Mechanism",
        "writer_view": {"blob": "x" * 368640},
    }
    assert _writer_request_exceeds_context_window(
        system_prompt="prompt",
        input_payload=near_window_input,
        response_json_schema=schema,
        config=config,
    )
    clamped = _writer_call_max_output_tokens(
        system_prompt="prompt",
        input_payload=near_window_input,
        response_json_schema=schema,
        config=config,
    )
    assert clamped < 8192
    clamped_config, blocked = _apply_writer_context_clamp(
        config,
        system_prompt="prompt",
        input_payload=near_window_input,
        response_json_schema=schema,
    )
    assert blocked is None
    assert clamped_config.max_output_tokens == clamped


def test_motivation_facet_not_required_by_default() -> None:
    assert not _default_facet_required("motivation")
    assert not _default_facet_required("mechanism")
    assert _default_facet_required("mechanism", source_field="key_building_blocks")
    assert _default_facet_required("formula", source_field="pipeline_steps")


def test_paraphrased_mechanism_covers_facet_without_author_quote() -> None:
    facet = {
        "exact_source_quote": "Initialize A as a diagonal matrix with learnable entries.",
        "semantic_fields": {
            "operation": "initialize",
            "outputs": ["diagonal matrix"],
            "paper_terms": ["learnable"],
        },
        "search_terms": ("diagonal", "learnable"),
    }
    paraphrase = (
        "We initialize the adjacency representation as a diagonal structure "
        "whose entries are learned during training."
    )
    assert _facet_body_covers(paraphrase, facet)


def test_primary_brief_binding_limits_required_facets() -> None:
    mechanism = AuthorMechanismFacetV1(
        facet_id="facet:core",
        clause_id="clause:core",
        facet_kind="mechanism",
        semantic_fields={"operation": "encode"},
        search_terms=("encode",),
        exact_source_quote="encode the graph",
        brief_id="brief:primary",
        required=True,
    )
    motivation = AuthorMechanismFacetV1(
        facet_id="facet:mot",
        clause_id="clause:mot",
        facet_kind="motivation",
        semantic_fields={"operation": "motivate"},
        search_terms=("motivate",),
        exact_source_quote="because theory",
        brief_id="brief:support",
        required=False,
    )
    primary = {"brief:primary"}
    assert _facet_required_for_section(mechanism, primary)
    assert not _facet_required_for_section(motivation, primary)


def test_short_imperative_heading_folds_into_claim_bucket() -> None:
    assert _heading_is_author_instruction("Initialize A as a diagonal matrix.")
    row = SimpleNamespace(
        obligation_id="obl:init",
        statement="Initialize A as a diagonal matrix with learnable entries.",
        role="mechanism",
        status="author_confirmation_required",
    )
    candidate_buckets = [
        (
            row.statement,
            [_CandidateRowEntry(row, None)],
        )
    ]
    claim_buckets = [
        (
            "Core mechanism",
            [
                (
                    "SG-1",
                    "Core mechanism",
                    "Purpose",
                    [],
                    ("obl:core",),
                )
            ],
        )
    ]
    folded = _fold_leftover_author_statement_buckets(
        claim_buckets=claim_buckets,
        candidate_buckets=candidate_buckets,
    )
    assert folded == []
    assert len(claim_buckets[0][1]) == 2


def _intent_obligation(
    obligation_id: str,
    *,
    source_field: str,
    author_text: str,
    kind: str = "stage",
) -> IntentObligationV2:
    return IntentObligationV2(
        obligation_id=obligation_id,
        kind=kind,
        priority="must_cover",
        source_field=source_field,
        source_index=0,
        author_text=author_text,
    )


def _intent_brief(
    obligation_id: str,
    statement: str,
    *,
    brief_id: str = "brief:test",
) -> MethodArgumentBriefV1:
    return MethodArgumentBriefV1(
        brief_id=brief_id,
        story_node_id="story:test",
        obligation_ids=(obligation_id,),
        author_statement=statement,
        clauses=(),
        mechanism_draft={
            "draft_id": f"draft:{brief_id}",
            "brief_id": brief_id,
            "status": "empty",
        },
    )


def test_intent_grain_one_facet_per_yaml_item() -> None:
    steps = tuple(f"Pipeline step {index}" for index in range(4))
    blocks = tuple(f"Building block {index}" for index in range(8))
    obligations = [
        _intent_obligation(
            f"obl:step:{index}",
            source_field="pipeline_steps",
            author_text=text,
        )
        for index, text in enumerate(steps)
    ] + [
        _intent_obligation(
            f"obl:block:{index}",
            source_field="key_building_blocks",
            author_text=text,
            kind="component",
        )
        for index, text in enumerate(blocks)
    ]
    intent_graph = IntentObligationGraphV2(obligations=obligations)
    briefs = [
        _intent_brief(f"obl:step:{index}", steps[index], brief_id=f"brief:step:{index}")
        for index in range(4)
    ] + [
        _intent_brief(
            f"obl:block:{index}",
            blocks[index],
            brief_id=f"brief:block:{index}",
        )
        for index in range(8)
    ]
    result = decompose_and_align_argument_facets(
        briefs=briefs,
        intent_graph=intent_graph,
    )
    assert len(result.facets) == 12
    required = [facet for facet in result.facets if facet.required]
    assert len(required) == 12
    assert len(required) < 39


def test_mainline_overlap_does_not_duplicate_required_facets() -> None:
    block_text = "Initialize A as a diagonal matrix with learnable entries."
    mainline_text = block_text
    intent_graph = IntentObligationGraphV2(
        obligations=[
            _intent_obligation(
                "obl:block:0",
                source_field="key_building_blocks",
                author_text=block_text,
                kind="component",
            ),
            _intent_obligation(
                "obl:mainline",
                source_field="method_mainline",
                author_text=mainline_text,
                kind="method_mainline",
            ),
        ]
    )
    briefs = [
        _intent_brief("obl:block:0", block_text, brief_id="brief:block"),
        _intent_brief("obl:mainline", mainline_text, brief_id="brief:mainline"),
    ]
    result = decompose_and_align_argument_facets(
        briefs=briefs,
        intent_graph=intent_graph,
    )
    assert len(result.facets) == 1
    assert result.facets[0].required


def test_mixed_authority_splits_at_most_three_facets() -> None:
    mixed_text = (
        "Inspired by Ebbinghaus forgetting theory, initialize A as a diagonal matrix; "
        "the spectral norm of the adjacency matrix must remain bounded for stability."
    )
    brief = _intent_brief("obl:block:0", mixed_text, brief_id="brief:mixed")
    facets = _decompose_brief(
        brief,
        claims=(),
        facts=(),
        facet_decomposer=None,
        proposition_architect=None,
        schema_failures=[],
        source_field="key_building_blocks",
    )
    assert 1 <= len(facets) <= 3
    assert not any(facet.facet_kind == "motivation" and facet.required for facet in facets)
    assert not any(facet.facet_kind == "guarantee" and facet.required for facet in facets)


def test_model_proposed_facet_id_is_ignored() -> None:
    brief = _intent_brief(
        "obl:block:0",
        "Encode dynamic graph snapshots with learnable embeddings.",
        brief_id="brief:fake-id",
    )
    facet, _ = _facet_from_row(
        {
            "facet_id": "facet:model-invented",
            "exact_source_quote": brief.author_statement,
            "facet_kind": "mechanism",
        },
        brief=brief,
        fallback_index=0,
        source_field="key_building_blocks",
    )
    assert facet.facet_id != "facet:model-invented"
    assert facet.facet_id.startswith("facet-")


def test_fused_heading_body_covers_facet_after_normalization() -> None:
    facet = {
        "exact_source_quote": "A dynamic graph encoder transforms raw events.",
        "semantic_fields": {
            "operation": "encode",
            "inputs": ["raw events"],
            "paper_terms": ["dynamic", "graph"],
        },
        "search_terms": ("dynamic", "graph", "encode", "events"),
    }
    fused = "## Robust selective reviewingA dynamic graph encoder transforms raw events."
    assert _facet_body_covers(
        fused,
        facet,
        expected_heading="Robust selective reviewing",
    )


def test_harness_infers_rendered_facets_without_model_witness() -> None:
    facet_id = "facet:encode-graph"
    output = PublicationMethodSectionOutputV1(
        section_markdown=(
            "## Graph encoding\n\n"
            "A dynamic graph encoder transforms raw events into latent states."
        ),
        rendered_from_facet_ids=[],
        deferred_facet_ids=[],
    )
    writer_input = WriterSectionInput(
        section_id="MA-S2",
        heading="Graph encoding",
        prompt_payload={
            "writer_view": {
                "mechanism_authoring_packet": {
                    "facets": [
                        {
                            "facet_id": facet_id,
                            "facet_kind": "mechanism",
                            "exact_source_quote": (
                                "Encode dynamic graph snapshots with learnable embeddings."
                            ),
                            "semantic_fields": {
                                "operation": "encode",
                                "inputs": ["dynamic graph"],
                                "paper_terms": ["embeddings"],
                            },
                            "search_terms": ("encode", "dynamic", "graph", "embeddings"),
                        }
                    ],
                    "required_facet_ids": [facet_id],
                },
            },
            "binding_contract": {
                "allowed_facet_ids": [facet_id],
                "required_facet_ids": [facet_id],
            },
        },
    )
    unknown, overlap, missing = _writer_facet_coverage(output, writer_input)
    assert not unknown
    assert not overlap
    assert facet_id not in missing


def test_author_intent_unresolved_retries_with_must_emit_instruction() -> None:
    from code2paper.agentic.equation_claims import EquationClaimSetV1
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
    from code2paper.agentic.formalization_agent import MethodFormulaObligationV2
    from code2paper.llm.client import LLMResponse
    from code2paper.schemas import LLMConfig, LLMProvider

    prompts: list[str] = []

    def caller(_config: LLMConfig, request) -> LLMResponse:
        prompts.append(request.prompt)
        return LLMResponse(
            text=(
                '{"outcome":"unresolved","section_id":"MA-S2","packages":[],'
                '"review_question":"Which line numbers in mamba_simple.py '
                'upgrade this formula to code_verified?"}'
            ),
            response_hash=f"sha256:unresolved:{len(prompts)}",
            finish_reason="stop",
        )

    obligation = MethodFormulaObligationV2(
        obligation_id="formula:facet:delta-t",
        facet_ids=("facet:delta-t",),
        expectation="required",
        mathematical_goal="State the author-intent discretization of Delta t.",
        exact_source_quotes=(
            "The time interval Delta t is obtained from a learnable projection.",
        ),
    )
    packages, traces = _invoke_section_formalizer_llm(
        graph=SimpleNamespace(
            section_id="MA-S2",
            reader_question="How is the state updated over Delta t?",
        ),
        unit_by_id={},
        proposition_by_id={},
        card_by_key={},
        core=[],
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            code_fact_digest="sha256:facts",
            equations=[],
            content_digest="sha256:eqs",
        ),
        facts=CodeFactSetV1(
            producer_version="test",
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            evidence_packet_digest="sha256:packets",
            facts=[],
            content_digest="sha256:facts",
        ),
        reader_points=[],
        formula_constraints=["preserve the author Delta t quote"],
        notation_hints=(),
        llm_config=LLMConfig(
            provider=LLMProvider.NONE,
            model="formalizer-test",
            cache=False,
        ),
        caller=caller,
        author_intent_lane=True,
        formula_obligation_required=True,
        formula_obligations=(obligation,),
    )
    assert packages == ()
    assert len(prompts) == 2
    assert "outcome=rendered" in prompts[0]
    assert "MUST produce" in prompts[0] or "must produce" in prompts[0].casefold()
    assert "Emit ONE" in prompts[1]
    assert "not allowed on the author_intent_academic lane" in prompts[1]
    assert traces[-1]["status"] == "declined_empty"


def test_cross_section_equation_obligations_are_trimmed_to_core() -> None:
    graph = SimpleNamespace(section_id="MA-S3")
    foreign_facet = SimpleNamespace(
        facet_id="facet:readout",
        brief_id="brief:other",
        formula_expectation="required",
        semantic_fields={},
        exact_source_quote="Read out the hidden state.",
    )
    local_facet = SimpleNamespace(
        facet_id="facet:local",
        brief_id="brief:local",
        formula_expectation="preferred",
        semantic_fields={"mathematical_goal": "Formalize the local readout."},
        exact_source_quote="Project the hidden state to scores.",
    )
    core = [SimpleNamespace(equation_id="equation:local")]
    obligations = _section_formula_obligations(
        graph=graph,
        facets=(foreign_facet, local_facet),
        obligation_ids=("equation:ssm-dt", "equation:local"),
        core=core,
        formula_constraints=[],
        primary_brief_ids={"brief:local"},
    )
    ids = {item.obligation_id for item in obligations}
    assert "equation:ssm-dt" not in ids
    assert "formula:facet:facet:readout" not in ids
    assert "formula:facet:facet:local" in ids
    assert "equation:local" in ids


def test_deferral_memo_without_mechanism_is_a_caveat_shell() -> None:
    markdown = (
        "## Selective SSM update\n\n"
        "No accepted formula packages were produced for this section, "
        "therefore deferred pending resolution of the formal derivation."
    )
    assert _looks_like_caveat_shell(markdown)
    assert not _section_output_acceptable(
        markdown,
        expected_heading="Selective SSM update",
    )


def test_planner_filled_mechanism_facets_cannot_all_defer() -> None:
    facet_id = "facet:ssm-update"
    output = PublicationMethodSectionOutputV1(
        section_markdown=(
            "## Selective SSM update\n\n"
            "No accepted formula packages were produced, therefore deferred."
        ),
        rendered_from_facet_ids=[],
        deferred_facet_ids=[facet_id],
    )
    writer_input = WriterSectionInput(
        section_id="MA-S2",
        heading="Selective SSM update",
        prompt_payload={
            "writer_view": {
                "mechanism_drafts": [
                    {
                        "brief_id": "brief:ssm",
                        "status": "planner_filled",
                        "text": (
                            "The selective SSM updates hidden states with a "
                            "learnable Delta t discretization."
                        ),
                    }
                ],
                "mechanism_authoring_packet": {
                    "facets": [
                        {
                            "facet_id": facet_id,
                            "brief_id": "brief:ssm",
                            "facet_kind": "mechanism",
                            "exact_source_quote": (
                                "Update hidden states with learnable Delta t."
                            ),
                            "semantic_fields": {
                                "operation": "update",
                                "paper_terms": ["Delta t", "SSM"],
                            },
                            "search_terms": ("update", "hidden", "Delta"),
                        }
                    ],
                    "required_facet_ids": [facet_id],
                },
            },
            "binding_contract": {
                "allowed_facet_ids": [facet_id],
                "required_facet_ids": [facet_id],
            },
        },
    )
    _unknown, _overlap, missing = _writer_facet_coverage(output, writer_input)
    assert facet_id in missing


def test_normalized_heading_is_written_back_to_section_markdown() -> None:
    output = PublicationMethodSectionOutputV1(
        section_markdown=(
            "## Robust selective reviewingA dynamic graph encoder transforms raw events."
        ),
    )
    persisted = _with_normalized_section_markdown(
        output,
        expected_heading="Robust selective reviewing",
    )
    assert persisted is not None
    assert persisted.section_markdown.startswith("## Robust selective reviewing\n")
    assert "A dynamic graph encoder" in persisted.section_markdown
    assert persisted.section_markdown != output.section_markdown


def test_repeated_token_spam_latex_is_not_rendered() -> None:
    package = {
        "latex": "h = " + " ".join(["dimesion"] * 20),
        "markdown_block": "$$" + " ".join(["dimesion"] * 20) + "$$",
    }
    spam = "## Encoder\n\n$$" + " ".join(["dimesion"] * 20) + "$$"
    assert _formula_package_rendered(spam, package) is False
    assert _formula_package_rendered(
        "## Encoder\n\nThe aligned state is $$h_{\\text{aligned}} = W x$$.",
        {"latex": "h_{\\text{aligned}} = W x"},
    ) is True


def test_fac_evidence_failure_is_not_rewrite_owned() -> None:
    from code2paper.agentic.publication_issue_owner_router import (
        rewrite_owned_issues,
        route_publication_issue,
    )
    from code2paper.agentic.research_models import TextRepairIssueV1

    fac_route = route_publication_issue(
        {
            "sentence_id": "FAC1",
            "failure_type": "direct_evidence_missing",
            "allowed_repair_scope": "drop_or_gap",
        },
        section_id="MA-S1",
    )
    assert fac_route.owner == "research_continuation"
    issues = [
        TextRepairIssueV1(
            sentence_id="FAC1",
            atomic_claim_id="FAC1",
            failure_type="unsupported_rationale",
            allowed_repair_scope="drop_or_gap",
            missing_fact_or_relation="direct_evidence_missing",
        ),
        TextRepairIssueV1(
            sentence_id="s-code",
            failure_type="method_language_style",
            allowed_repair_scope="wording_only",
            missing_fact_or_relation="self.time_mamba dominates the prose",
        ),
    ]
    owned = rewrite_owned_issues(issues, section_id="MA-S4")
    assert all(item.failure_type != "unsupported_rationale" for item in owned)
    assert any(
        item.failure_type == "method_language_style"
        and "time_mamba" in item.missing_fact_or_relation
        for item in owned
    )


def test_fac_failure_does_not_mark_non_shell_candidate_incomplete() -> None:
    output = PublicationMethodSectionOutputV1(
        section_markdown=(
            "## Graph encoding\n\n"
            "A dynamic graph encoder transforms raw events into latent states."
        ),
    )
    writer_input = WriterSectionInput(
        section_id="MA-S1",
        heading="Graph encoding",
        prompt_payload={"formula_packages": []},
    )
    incomplete = _candidate_incomplete_section_ids(
        plan_section_ids=("MA-S1",),
        accepted_section_ids={"MA-S1"},
        callback_section_ids=set(),
        required_facet_failures_by_section={},
        required_formula_failures_by_section={"MA-S1": ("formula:facet:delta-t",)},
        output_by_section={"MA-S1": output},
        writer_input_by_section={"MA-S1": writer_input},
    )
    assert incomplete == ()
    shell = PublicationMethodSectionOutputV1(
        section_markdown=(
            "## Graph encoding\n\n"
            "No accepted formula packages, therefore deferred."
        ),
    )
    shell_incomplete = _candidate_incomplete_section_ids(
        plan_section_ids=("MA-S1",),
        accepted_section_ids=set(),
        callback_section_ids=set(),
        required_facet_failures_by_section={},
        required_formula_failures_by_section={"MA-S1": ("formula:facet:delta-t",)},
        output_by_section={"MA-S1": shell},
        writer_input_by_section={"MA-S1": writer_input},
    )
    assert "MA-S1" in shell_incomplete

def test_delta_t_quote_is_preferred_or_required_formula() -> None:
    quote = (
        "Initialize A as a diagonal matrix with strictly negative real-part "
        "eigenvalues. The step size Δt is a learnable function of the time gap."
    )
    assert _has_author_formula_signal(quote)
    assert _formula_expectation(quote, "mechanism") in {"preferred", "required"}
    facet, _ = _facet_from_row(
        {
            "facet_kind": "mechanism",
            "formula_expectation": "none",
            "exact_source_quote": quote,
        },
        brief=_intent_brief("obl:block:0", quote, brief_id="brief:dt"),
        fallback_index=0,
        source_field="key_building_blocks",
    )
    assert facet.formula_expectation in {"preferred", "required"}


def test_empty_core_keeps_author_intent_obligation_from_delta_quote() -> None:
    graph = SimpleNamespace(section_id="MA-S2", formula_not_applicable=False)
    local = SimpleNamespace(
        facet_id="facet:delta-t",
        brief_id="brief:local",
        formula_expectation="none",
        semantic_fields={},
        exact_source_quote=(
            "The step size Δt is a learnable, monotonically increasing "
            "function of the time gap."
        ),
    )
    obligations = _section_formula_obligations(
        graph=graph,
        facets=(local,),
        obligation_ids=("equation:ssm-dt",),
        core=[],
        formula_constraints=[],
        primary_brief_ids={"brief:local"},
    )
    ids = {item.obligation_id for item in obligations}
    assert "equation:ssm-dt" not in ids
    assert any(
        item.obligation_id.startswith("formula:")
        for item in obligations
    )


def test_formula_not_applicable_does_not_synthesize_derivation() -> None:
    graph = SimpleNamespace(section_id="MA-S3", formula_not_applicable=True)
    facet = SimpleNamespace(
        facet_id="facet:readout",
        brief_id="brief:local",
        formula_expectation="required",
        semantic_fields={},
        exact_source_quote="Directly couple the SSM step size Δt to irregular timespans.",
    )
    obligations = _section_formula_obligations(
        graph=graph,
        facets=(facet,),
        obligation_ids=(),
        core=[],
        formula_constraints=[],
        primary_brief_ids={"brief:local"},
    )
    assert obligations == ()


def test_formula_not_applicable_ignores_plan_equation_ids() -> None:
    graph = SimpleNamespace(section_id="MA-S1", formula_not_applicable=True)
    obligations = _section_formula_obligations(
        graph=graph,
        facets=(),
        obligation_ids=("formula:equation:fact-incidental-add",),
        core=[],
        formula_constraints=[],
        primary_brief_ids=set(),
    )
    assert obligations == ()


def test_empty_core_plan_equation_ids_open_author_intent_derivation() -> None:
    graph = SimpleNamespace(section_id="MA-S2", formula_not_applicable=False)
    facet = SimpleNamespace(
        facet_id="facet:activation",
        brief_id="brief:local",
        formula_expectation="none",
        semantic_fields={},
        exact_source_quote=(
            "Offline indexing splits passages into sentences and records "
            "which entities they mention."
        ),
    )
    obligations = _section_formula_obligations(
        graph=graph,
        facets=(facet,),
        obligation_ids=("formula:equation:fact-O-STAGE-02-node:abc",),
        core=[],
        formula_constraints=[],
        primary_brief_ids={"brief:local"},
    )
    ids = {item.obligation_id for item in obligations}
    assert "formula:equation:fact-O-STAGE-02-node:abc" not in ids
    assert "formula:section:MA-S2:derivation" in ids
    assert all(item.expectation == "required" for item in obligations)


def test_repeated_code_trace_parenthetical_is_rejected() -> None:
    spam = (
        "## Redesign: timespan-informed Δt and A for temporally aware forgetting\n\n"
        + " (self.time_mamba and dts != None)" * 12
    )
    assert _prose_has_repeated_phrase_spam(spam)
    assert not _section_output_acceptable(
        spam,
        expected_heading=(
            "Redesign: timespan-informed Δt and A for temporally aware forgetting"
        ),
    )


def test_wrapped_heading_is_rejoined_to_plan_heading() -> None:
    heading = "Redesign: timespan-informed Δt and A for temporally aware forgetting"
    wrapped = (
        "## Redesign: timespan-informed Δt and\n\n"
        "A for temporally aware forgetting. The step size is timespan-dependent."
    )
    persisted = _with_normalized_section_markdown(
        PublicationMethodSectionOutputV1(section_markdown=wrapped),
        expected_heading=heading,
    )
    assert persisted is not None
    assert persisted.section_markdown.startswith(f"## {heading}\n")
    assert "The step size is timespan-dependent." in persisted.section_markdown

def test_heading_backtick_fence_is_stripped() -> None:
    heading = "Robust selective reviewing"
    fused = (
        "## Robust selective reviewing`case_study`\n\n"
        "The step size Δt is timespan-dependent."
    )
    persisted = _with_normalized_section_markdown(
        PublicationMethodSectionOutputV1(section_markdown=fused),
        expected_heading=heading,
    )
    assert persisted is not None
    assert persisted.section_markdown.startswith("## Robust selective reviewing\n")
    assert "`case_study`" not in persisted.section_markdown.splitlines()[0]
    assert "The step size" in persisted.section_markdown

def test_unresolved_payload_with_packages_is_coerced_to_rendered() -> None:
    parsed = coerce_section_formalizer_response(
        {
            "outcome": "unresolved",
            "section_id": "MA-S4",
            "packages": [
                {
                    "package_id": "fp:MA-S4:dt",
                    "section_id": "MA-S4",
                    "purpose": "Timespan-informed step size.",
                    "latex": r"\Delta t = f(\tau)",
                    "prose_explanation": "Step size grows with the time gap.",
                    "authority_status": "author_intent",
                    "formula_lane": "author_intent_academic",
                    "content_digest": "sha256:placeholder",
                }
            ],
        },
        section_id="MA-S4",
    )
    assert parsed is not None
    assert parsed.outcome == "rendered"
    assert parsed.packages
    assert r"\Delta t" in parsed.packages[0].latex


def test_conflicting_repository_lane_is_downgraded_to_author_intent() -> None:
    parsed = coerce_section_formalizer_response(
        {
            "outcome": "rendered",
            "section_id": "MA-S1",
            "packages": [
                {
                    "package_id": "fp:MA-S1:intent",
                    "section_id": "MA-S1",
                    "purpose": "State the author-proposed update.",
                    "latex": r"h_t = f(h_{t-1}, x_t)",
                    "prose_explanation": "The update is stated as an author-intent abstraction.",
                    "authority_status": "author_intent",
                    # Qwen sometimes copies the section lane even when it
                    # explicitly declares that the package is author intent.
                    "formula_lane": "repository_derived",
                }
            ],
        },
        section_id="MA-S1",
    )
    assert parsed is not None
    package = parsed.packages[0]
    assert package.formula_lane == "author_intent_academic"
    assert package.review_status == "review_required"


def test_conflicting_repository_lane_is_downgraded_to_partial() -> None:
    parsed = coerce_section_formalizer_response(
        {
            "outcome": "rendered",
            "section_id": "MA-S2",
            "packages": [
                {
                    "package_id": "fp:MA-S2:partial",
                    "section_id": "MA-S2",
                    "purpose": "State the partially supported operation.",
                    "latex": r"y = g(x)",
                    "prose_explanation": "The operation is only partially supported by the evidence.",
                    "authority_status": "partial",
                    "formula_lane": "repository_derived",
                }
            ],
        },
        section_id="MA-S2",
    )
    assert parsed is not None
    package = parsed.packages[0]
    assert package.formula_lane == "hybrid_partial"
    assert package.review_status == "review_required"


def test_author_intent_schema_forbids_unresolved_outcome() -> None:
    schema = AuthorIntentSectionFormalizerResponseV1.model_json_schema()
    outcome = schema["properties"]["outcome"]
    enum_values = outcome.get("enum") or [outcome.get("const")]
    assert "rendered" in enum_values
    assert "unresolved" not in enum_values


def test_author_intent_unresolved_with_latex_is_accepted() -> None:
    from code2paper.agentic.equation_claims import EquationClaimSetV1
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1
    from code2paper.agentic.formalization_agent import MethodFormulaObligationV2
    from code2paper.llm.client import LLMResponse
    from code2paper.schemas import LLMConfig, LLMProvider

    requests: list = []

    def caller(_config: LLMConfig, request) -> LLMResponse:
        requests.append(request)
        return LLMResponse(
            text=(
                '{"outcome":"unresolved","section_id":"MA-S4","packages":[{'
                '"package_id":"fp:MA-S4:dt","section_id":"MA-S4",'
                '"purpose":"Timespan-informed step size.",'
                r'"latex":"\\Delta t = f(\\tau)",'
                '"prose_explanation":"Step size grows with the time gap.",'
                '"symbol_definitions":[["\\\\tau","elapsed time gap"]],'
                '"authority_status":"author_intent",'
                '"formula_lane":"author_intent_academic"'
                "}]} "
            ),
            response_hash="sha256:salvage",
            finish_reason="structured_complete",
        )

    obligation = MethodFormulaObligationV2(
        obligation_id="formula:facet:delta-t",
        facet_ids=("facet:delta-t",),
        expectation="required",
        mathematical_goal="State Delta t.",
        exact_source_quotes=("The step size Delta t is timespan-dependent.",),
    )
    packages, traces = _invoke_section_formalizer_llm(
        graph=SimpleNamespace(
            section_id="MA-S4",
            reader_question="How is forgetting timed?",
        ),
        unit_by_id={},
        proposition_by_id={},
        card_by_key={},
        core=[],
        equations=EquationClaimSetV1(
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            code_fact_digest="sha256:facts",
            equations=[],
            content_digest="sha256:eqs",
        ),
        facts=CodeFactSetV1(
            producer_version="test",
            repo_snapshot_id="repo:test",
            project_tree_hash="sha256:tree",
            evidence_packet_digest="sha256:packets",
            facts=[],
            content_digest="sha256:facts",
        ),
        reader_points=[],
        formula_constraints=[],
        notation_hints=(),
        llm_config=LLMConfig(
            provider=LLMProvider.NONE,
            model="formalizer-test",
            cache=False,
        ),
        caller=caller,
        author_intent_lane=True,
        formula_obligation_required=True,
        formula_obligations=(obligation,),
    )
    assert packages
    assert r"\Delta t" in packages[0].latex
    schema = requests[0].response_json_schema
    outcome = schema["properties"]["outcome"]
    enum_values = outcome.get("enum") or [outcome.get("const")]
    assert "unresolved" not in enum_values
    assert traces[-1]["status"] == "accepted"


def test_glued_html_residue_heading_is_not_headings_only() -> None:
    heading = (
        "First retrieval stage: relevant entity activation via local semantic bridging"
    )
    fused = (
        f"## {heading}p>The first retrieval stage initializes, propagates, and "
        "prunes entity activations through a local semantic bridge. The scoring "
        "function returns entity weights and an activated entity set."
    )
    normalized = _normalize_section_heading_breaks(fused, expected_heading=heading)
    assert normalized.startswith(f"## {heading}\n")
    assert "The first retrieval stage initializes" in normalized
    assert _section_output_acceptable(fused, expected_heading=heading)


def test_html_p_tag_fused_heading_is_split() -> None:
    heading = (
        "First retrieval stage: relevant entity activation via local semantic bridging"
    )
    fused = (
        f"## {heading}<p>The first retrieval stage activates relevant entities "
        "through local semantic bridging and dynamic pruning of weak scores."
    )
    normalized = _normalize_section_heading_breaks(fused, expected_heading=heading)
    assert "\n\nThe first retrieval stage activates" in normalized or (
        "\nThe first retrieval stage activates" in normalized
    )
    assert _section_output_acceptable(fused, expected_heading=heading)


def test_extract_itex_spam_is_stripped_leaving_mechanism_prose() -> None:
    heading = "Contrastive training"
    spam = (
        f"## {heading}\n\n"
        "The embedding-based reranking framework refines initial dense "
        "passage embeddings through a Transformer encoder that incorporates "
        "structural cues and hybrid attention, followed by contrastive "
        "optimization. Pre-computed dense passage embeddings "
        "$[extract_itex]{}[/extract_itex]{}[extract_itex]{}[/extract_itex]{}"
        "[extract_itex]{}[/extract_itex]{}[extract_itex]{}[/extract_itex]{}"
        "[extract_itex]{}[/extract_itex]{}[extract_itex]{}[/extract_itex]{}$ "
        "are the encoder inputs."
    )
    normalized = _normalize_section_heading_breaks(spam, expected_heading=heading)
    assert "extract_itex" not in normalized
    assert "Transformer encoder" in normalized
    assert _section_output_acceptable(spam, expected_heading=heading)


def test_heading_identifier_run_is_stripped_without_inventing_body() -> None:
    heading = "Inference scoring and ranking"
    spam = "## " + heading + " {#MA-S2}" * 12
    normalized = _normalize_section_heading_breaks(spam, expected_heading=heading)
    assert "{#MA-S2}" not in normalized
    assert not _section_output_acceptable(spam, expected_heading=heading)


def test_repeated_parentheticals_collapse_when_mechanism_prose_remains() -> None:
    heading = "Offline Tri-Graph construction"
    guard = "(len(new_passage_hash_ids) > 0)"
    body = (
        f"## {heading}\n\n"
        "Offline Tri-Graph construction maps a raw corpus into a hierarchical "
        f"structure containing passages, sentences, and entities {guard}. The "
        f"corpus undergoes passage splitting to generate sentence-level units "
        f"{guard}. Sparse adjacency matrices encode structural relations "
        f"{guard}. The resulting tri-graph maintains three node tiers {guard}. "
        f"This configuration eliminates explicit relation extraction {guard}."
    )
    assert _prose_has_repeated_phrase_spam(body)
    normalized = _normalize_section_heading_breaks(body, expected_heading=heading)
    assert normalized.count(guard) == 1
    assert _section_output_acceptable(body, expected_heading=heading)


def test_backtick_code_guard_spam_collapses_when_mechanism_prose_remains() -> None:
    heading = "Offline Tri‑Graph construction"
    guard = "`len(new_passage_hash_ids) > 0`"
    body = (
        f"## {heading}\n\n"
        "Source passages decompose into discrete sentences, and a spaCy-based "
        f"pipeline identifies and normalizes entity spans {guard}. The "
        "transformation constructs two sparse adjacency matrices: a contain "
        "matrix linking passages to resident entities, and a mention matrix "
        f"linking sentences to referenced entities {guard}. The resulting "
        "representation maintains a direct mapping between textual hierarchy "
        f"and entity distribution without inferring intermediate relations "
        f"{guard}. The offline pipeline outputs a static tri-graph structure "
        f"that preserves exact passage-sentence-entity containment boundaries "
        f"{guard}."
    )
    assert _prose_has_repeated_phrase_spam(body)
    normalized = _normalize_section_heading_breaks(body, expected_heading=heading)
    assert normalized.count(guard) == 1
    assert _section_output_acceptable(body, expected_heading=heading)
    assert _writer_retry_failure_code(
        PublicationMethodSectionOutputV1(section_markdown=body),
        expected_heading=heading,
    ) != "repeated_token_spam"


def test_headings_only_retry_instruction_forbids_callback_in_place_of_body() -> None:
    action = _writer_retry_required_action(
        "section_body_missing_or_headings_only",
        heading="Second retrieval stage: passage retrieval via global importance aggregation",
    )
    assert "research callback is not a substitute" in action
    assert "planner_filled" in action


def test_formula_not_applicable_formal_derivation_is_locally_unfulfillable() -> None:
    graph = SimpleNamespace(section_id="MA-S1", formula_not_applicable=True)
    request = SimpleNamespace(
        required_authority_lane="formal_derivation",
        request_id="req:MA-S1:001",
    )
    assert _writing_request_is_locally_unfulfillable(request, graph=graph) is True
    graph_ok = SimpleNamespace(section_id="MA-S2", formula_not_applicable=False)
    assert _writing_request_is_locally_unfulfillable(request, graph=graph_ok) is False
    external = SimpleNamespace(
        required_authority_lane="expository_bridge",
        request_id="req:MA-S2:001",
    )
    assert _writing_request_is_locally_unfulfillable(external, graph=graph) is False


def test_parenthetical_only_spam_is_still_rejected() -> None:
    heading = "Redesign: timespan-informed Δt and A for temporally aware forgetting"
    spam = f"## {heading}\n\n" + " (self.time_mamba and dts != None)" * 12
    assert _prose_has_repeated_phrase_spam(spam)
    assert not _section_output_acceptable(spam, expected_heading=heading)


def test_spam_retry_code_is_not_heading_truncated() -> None:
    heading = "Offline Tri-Graph construction"
    guard = "(len(new_passage_hash_ids) > 0)"
    markdown = (
        f"## {heading}\n\n"
        f"The construction uses a sparse adjacency {guard} {guard} {guard} {guard}."
    )
    output = PublicationMethodSectionOutputV1(section_markdown=markdown)
    assert _writer_retry_failure_code(output, expected_heading=heading) == (
        "repeated_token_spam"
    )


def test_leq_dot_big_are_notation_not_undefined_symbols() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:score",
                subject="forward",
                predicate="computes_formula",
                object="score",
                scope="sym:forward",
                direct_span_ids=["span:1"],
                semantic_context=["SCORE"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:score",
                validation_status="supported",
            )
        ],
        content_digest="sha256:facts",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[
            EquationClaimV1(
                equation_id="equation:score",
                expression="hdot = A h",
                fact_ids=["fact:score"],
                symbol_bindings=[
                    EquationSymbolBindingV1(
                        symbol="h", operand_role="state", operand_value="hidden",
                        fact_id="fact:score",
                    ),
                ],
                canonical_identity="sha256:eq",
                validation_status="supported",
            )
        ],
        content_digest="sha256:eqs",
    )
    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S2:ssm",
        section_id="MA-S2",
        purpose="SSM core.",
        latex=(
            r"\begin{align*} \dot{h}(t) &= A h(t) \leq 1 \\ "
            r"y &= \big( C h \big) \end{align*}"
        ),
        prose_explanation="The hidden state evolves under a stable transition.",
        symbol_definitions=(("h", "hidden state"), ("A", "transition"), ("C", "output"), ("y", "output")),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
    )
    failures = validate_section_formula_package(pkg, equations=equations, facts=facts)
    assert not any("undefined_symbols" in failure for failure in failures)
    assert not any("markdown_block_not_display_math" in failure for failure in failures)


def test_markdown_block_without_display_math_is_rebuilt_from_latex() -> None:
    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Encoding.",
        latex=r"\begin{align*} h = \mathrm{Concat}(x) \end{align*}",
        prose_explanation="Encodings are concatenated.",
        markdown_block="render the encoding alignment without a math environment",
        symbol_definitions=(("h", "aligned encoding"), ("x", "inputs")),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
    )
    assert "$$" in pkg.markdown_block
    assert r"\begin{align*}" in pkg.markdown_block


def test_int_alpha_textbf_mid_are_notation_not_undefined_symbols() -> None:
    from code2paper.agentic.equation_claims import (
        EquationClaimSetV1,
        EquationClaimV1,
        EquationSymbolBindingV1,
    )
    from code2paper.agentic.evidence_compiler_v3 import CodeFactSetV1, CodeFactV1

    facts = CodeFactSetV1(
        producer_version="test",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        evidence_packet_digest="sha256:packets",
        facts=[
            CodeFactV1(
                fact_id="fact:score",
                subject="forward",
                predicate="computes_formula",
                object="score",
                scope="sym:forward",
                direct_span_ids=["span:1"],
                semantic_context=["SCORE"],
                exact_source_digest="sha256:src",
                canonical_identity="sha256:fact:score",
                validation_status="supported",
            )
        ],
        content_digest="sha256:facts",
    )
    equations = EquationClaimSetV1(
        schema_version="1.0",
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        code_fact_digest="sha256:facts",
        equations=[
            EquationClaimV1(
                equation_id="equation:score",
                expression="hdot = A h",
                fact_ids=["fact:score"],
                symbol_bindings=[
                    EquationSymbolBindingV1(
                        symbol="h", operand_role="state", operand_value="hidden",
                        fact_id="fact:score",
                    ),
                ],
                canonical_identity="sha256:eq",
                validation_status="supported",
            )
        ],
        content_digest="sha256:eqs",
    )
    pkg = SectionFormulaPackageV1(
        package_id="fp:MA-S2:core",
        section_id="MA-S2",
        purpose="Core update.",
        latex=(
            r"\begin{align*}\n"
            r"\int_0^{\Delta t} e^{A s}\,ds + \alpha \textbf{P} "
            r"\mid \underbrace{M}_{adj}\n"
            r"\end{align*}"
        ),
        prose_explanation="The discrete update integrates the state transition.",
        markdown_block=(
            "$$\n"
            r"\int_0^{\Delta t} e^{A s}\,ds + \alpha \textbf{P}"
            "\n$$"
        ),
        symbol_definitions=(
            ("A", "transition"),
            (r"\Delta t", "step"),
            ("P", "operator"),
            ("M", "adjacency"),
            ("s", "dummy time"),
        ),
        authority_status="author_intent",
        formula_lane="author_intent_academic",
        bound_equation_ids=("equation:score",),
        bound_fact_ids=("fact:score",),
    )
    failures = validate_section_formula_package(pkg, equations=equations, facts=facts)
    assert not any("undefined_symbols" in failure for failure in failures)


def test_repeated_config_guard_is_collapsed_and_accepted() -> None:
    heading = "Second retrieval stage: passage retrieval via global importance aggregation"
    guard = "`self.config.enabled_flag`"
    body = (
        f"## {heading}\n\n"
        f"The second stage ranks passages on the hierarchical graph {guard}. "
        f"It is decoupled from the local activation stage {guard}. "
        f"Passage nodes receive a hybrid initialization {guard}. "
        f"Propagation uses the pre-built adjacency {guard}. "
        f"Personalized ranking concentrates mass on the activated set {guard}. "
        f"Final scores complete the transition from local to global ranking {guard}."
    )
    assert _prose_has_repeated_phrase_spam(body)
    normalized = _normalize_section_heading_breaks(body, expected_heading=heading)
    assert normalized.count(guard) == 1
    assert "()" not in normalized
    assert _section_output_acceptable(body, expected_heading=heading)
    persisted = _with_normalized_section_markdown(
        PublicationMethodSectionOutputV1(section_markdown=body),
        expected_heading=heading,
    )
    assert persisted is not None
    assert persisted.section_markdown.count(guard) == 1
    assert _section_output_acceptable(
        persisted.section_markdown, expected_heading=heading,
    )


def test_fused_heading_with_leading_parenthetical_is_split() -> None:
    heading = (
        "Second retrieval stage: passage retrieval via global importance "
        "aggregation"
    )
    fused = (
        f"## {heading} (`self.config.enabled_flag` = `True` path) "
        "The second retrieval stage decouples local entity activation from "
        "global passage ranking. Passage nodes receive a hybrid initialization "
        "and personalized ranking concentrates mass on the activated set. "
        "### Personalized ranking The converged scores become the retrieved list."
    )
    normalized = _normalize_section_heading_breaks(fused, expected_heading=heading)
    assert normalized.startswith(f"## {heading}\n")
    assert "The second retrieval stage decouples" in normalized
    assert _section_output_acceptable(fused, expected_heading=heading)
    persisted = _with_normalized_section_markdown(
        PublicationMethodSectionOutputV1(section_markdown=fused),
        expected_heading=heading,
    )
    assert persisted is not None
    assert persisted.section_markdown.startswith(f"## {heading}\n")
    assert _markdown_has_non_heading_body(persisted.section_markdown)


def test_repeated_bracket_qualifiers_on_heading_are_not_a_body() -> None:
    heading = (
        "First retrieval stage: relevant entity activation via local "
        "semantic bridging"
    )
    markdown = "## " + heading + " [intended, partial]" * 16
    normalized = _normalize_section_heading_breaks(
        markdown, expected_heading=heading,
    )
    assert "intended" not in normalized.casefold()
    assert not _section_output_acceptable(markdown, expected_heading=heading)


def test_research_request_tokens_are_stripped_from_heading() -> None:
    heading = "Robust selective reviewing"
    markdown = (
        f"## {heading} [research-request:RR-MA-S2-268] "
        "[research-request:RR-MA-S2-269]\n\n"
        "The filter layer modulates hidden states with a learned weight "
        "and returns the gated representation."
    )
    normalized = _normalize_section_heading_breaks(
        markdown, expected_heading=heading,
    )
    assert "research-request" not in normalized.casefold()
    assert "filter layer modulates" in normalized.casefold()
    assert _section_output_acceptable(markdown, expected_heading=heading)


def test_organization_stage_bucket_is_not_leftover_author_statement() -> None:
    from code2paper.agentic.method_argument_models import MethodCompletenessItemV1
    from code2paper.agentic.method_product_models import AuthorStoryNodeV1

    title = (
        "First retrieval stage: relevant entity activation via local "
        "semantic bridging (initialization, iterative propagation, dynamic pruning)"
    )
    node = AuthorStoryNodeV1(
        story_node_id="story:O-ORGANIZATION-04",
        title=title,
        author_statement=title,
        linked_obligation_ids=("O-ORGANIZATION-04",),
    )
    row = MethodCompletenessItemV1(
        obligation_id="O-ORGANIZATION-04",
        role="organization",
        statement=title,
        status="author_confirmation_required",
        importance="high",
    )
    bucket = (title, [_CandidateRowEntry(row, node)])
    assert _bucket_links_organization(bucket) is True
    assert _bucket_is_leftover_author_statement(bucket) is False
    assert len(title.split()) > 12
    claim_buckets = [
        (
            "Core mechanism",
            [
                (
                    "SG-1",
                    "Core mechanism",
                    "Purpose",
                    [],
                    ("obl:core",),
                )
            ],
        )
    ]
    folded = _fold_leftover_author_statement_buckets(
        claim_buckets=claim_buckets,
        candidate_buckets=[bucket],
    )
    assert folded == [bucket]
    assert len(claim_buckets[0][1]) == 1
