"""Project-neutral regressions for the attachment-aligned authoring closure."""

from __future__ import annotations

from types import SimpleNamespace

from code2paper.agentic.formalization_agent import (
    MethodFormulaObligationV2,
    SectionFormulaPackageV1,
    section_result_from_packages,
)
from code2paper.agentic.implementation_scope import (
    build_candidate_acquisition_ledger,
    seed_child_candidates_from_parents,
)
from code2paper.agentic.method_argument_brief_models import (
    AuthorMechanismFacetV1,
    FacetEvidenceAlignmentV1,
    FacetEvidenceExcerptV1,
    FacetFieldBindingV1,
)
from code2paper.agentic.method_argument_facet_aligner import (
    compile_publication_field_candidates,
)
from code2paper.agentic.publication_transaction_contract import (
    assess_paragraph_transaction,
    bind_paragraph_witnesses,
    required_anchors_from_plan_row,
)
from code2paper.agentic.method_architect import _reader_facing_slot_semantic_atom
from code2paper.agentic.research_models import ImplementationScopeV1


def _behavior_graph() -> SimpleNamespace:
    return SimpleNamespace(
        nodes=(
            SimpleNamespace(
                node_id="node:core",
                symbol_id="core",
                predicate="normalize",
                operands=("inputs",),
                result="scores",
            ),
            SimpleNamespace(
                node_id="node:child",
                symbol_id="child",
                predicate="normalize",
                operands=("inputs",),
                result="scores",
            ),
        ),
        relations=(SimpleNamespace(
            kind="CALLS",
            source_node_id="node:core",
            target_node_id="node:child",
        ),),
    )


def test_child_seeding_rejects_sibling_baseline_contamination() -> None:
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=("core",),
        target_core_symbol_ids=("core",),
        comparand_symbol_ids=("baseline",),
    )
    parent = SimpleNamespace(
        obligation_id="obligation:parent",
        status="pending",
        author_text="main normalization",
        candidate_symbol_ids=["core", "baseline"],
    )
    child = SimpleNamespace(
        obligation_id="obligation:child",
        status="pending",
        author_text="",
        candidate_symbol_ids=[],
        candidate_behavior_node_ids=["node:child"],
        typed_behavior_targets=(SimpleNamespace(
            role="transformation",
            search_terms=("normalize inputs",),
            inputs=(),
            transformations=(),
            outputs=(),
        ),),
    )

    changed = seed_child_candidates_from_parents(
        (parent, child), behavior_graph=_behavior_graph(), scope=scope
    )

    assert changed == (("obligation:child", ("core",)),)
    assert child.candidate_symbol_ids == ["core"]


def test_acquisition_ledger_keeps_closure_after_obligation_switch() -> None:
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=("core",),
        target_core_symbol_ids=("core",),
        comparand_symbol_ids=("baseline",),
    )
    observations = (
        SimpleNamespace(
            observation_id="observation:search",
            tool_name="search_symbols",
            status="success",
            result_refs=("core", "baseline"),
            exact_span_ids=(),
            notebook=None,
        ),
        SimpleNamespace(
            observation_id="observation:read",
            tool_name="read_symbol",
            status="success",
            result_refs=("core",),
            exact_span_ids=(),
            notebook=None,
        ),
    )
    packet = SimpleNamespace(
        packet_id="packet:core",
        anchor_span_ids=("span:core",),
        relation_span_ids=(),
        semantic_span_ids=(),
        spans=(),
    )
    fact = SimpleNamespace(
        fact_id="fact:core",
        direct_span_ids=("span:core",),
        relation_span_ids=(),
    )
    claim = SimpleNamespace(claim_id="claim:core", fact_ids=("fact:core",))
    compiled = SimpleNamespace(
        packet_set=SimpleNamespace(packets=(packet,)),
        fact_set=SimpleNamespace(facts=(fact,)),
        claim_set=SimpleNamespace(claims=(claim,)),
    )
    graph = SimpleNamespace(nodes=(
        SimpleNamespace(node_id="node:core", symbol_id="core", source_span_id="span:core"),
    ))
    parent = SimpleNamespace(
        obligation_id="obligation:parent",
        candidate_symbol_ids=["core", "baseline"],
    )
    parent_ledger = build_candidate_acquisition_ledger(
        scope=scope,
        agenda_items=(parent,),
        observations=observations,
        behavior_graph=graph,
        compiled_by_obligation={"obligation:parent": compiled},
    )

    parent_records = parent_ledger.by_key()
    assert parent_records[("obligation:parent", "core")].terminal_status == "acquired_and_compiled"
    assert parent_records[("obligation:parent", "baseline")].terminal_status == "explicitly_rejected"

    child = SimpleNamespace(
        obligation_id="obligation:child",
        candidate_symbol_ids=["core"],
    )
    child_ledger = build_candidate_acquisition_ledger(
        scope=scope,
        agenda_items=(child,),
        observations=observations,
        behavior_graph=graph,
        compiled_by_obligation={"obligation:child": compiled},
    )
    child_record = child_ledger.by_key()[("obligation:child", "core")]
    assert child_record.terminal_status == "acquired_and_compiled"
    assert child_record.read_observation_refs == ("observation:read",)


def _aligned_facet_fixture() -> tuple[
    AuthorMechanismFacetV1, FacetEvidenceAlignmentV1
]:
    facet = AuthorMechanismFacetV1(
        facet_id="facet:normalize",
        clause_id="clause:normalize",
        exact_source_quote="normalize inputs when the score exceeds a threshold",
        facet_kind="mechanism",
        semantic_fields={
            "operation": "normalize inputs",
            "conditions": "when score exceeds a threshold",
        },
        required=True,
    )
    operation_excerpt = FacetEvidenceExcerptV1(
        facet_id=facet.facet_id,
        span_id="span:operation",
        symbol="core",
        exact_excerpt="normalize inputs",
        fact_ids=("fact:operation",),
    )
    condition_excerpt = FacetEvidenceExcerptV1(
        facet_id=facet.facet_id,
        span_id="span:condition",
        symbol="core",
        exact_excerpt="score > threshold",
        fact_ids=("fact:condition",),
    )
    alignment = FacetEvidenceAlignmentV1(
        facet_id=facet.facet_id,
        clause_id=facet.clause_id,
        status="partial",
        supported_fields=("operation",),
        unsupported_fields=("conditions",),
        field_bindings=(
            FacetFieldBindingV1(
                field_name="operation",
                status="entailed",
                bound_fact_ids=("fact:operation",),
                bound_span_ids=("span:operation",),
            ),
            FacetFieldBindingV1(
                field_name="conditions",
                status="unresolved",
                unsupported_reason="condition branch not closed",
            ),
        ),
        exact_excerpts=(operation_excerpt, condition_excerpt),
    )
    return facet, alignment


def test_partial_field_preservation_rebinds_from_closed_excerpts() -> None:
    facet, alignment = _aligned_facet_fixture()
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=("core",),
        target_core_symbol_ids=("core",),
    )

    candidates, deferred = compile_publication_field_candidates(
        (facet,), (alignment,), implementation_scope=scope
    )

    operation = next(item for item in candidates if item.field_name == "operation")
    assert operation.render_policy == "required"
    assert operation.is_consumable
    assert operation.ownership_roles == ("target_core",)
    assert operation.exact_excerpts == ("normalize inputs",)
    assert any(item.field_name == "conditions" for item in deferred)


def test_unknown_scope_cannot_become_a_required_field_target() -> None:
    facet, alignment = _aligned_facet_fixture()
    scope = ImplementationScopeV1(
        target_entry_symbol_ids=("other",),
        target_core_symbol_ids=("other",),
        unknown_symbol_ids=("core",),
    )

    candidates, deferred = compile_publication_field_candidates(
        (facet,), (alignment,), implementation_scope=scope
    )

    assert not any(item.render_policy == "required" for item in candidates)
    assert any(item.field_name == "operation" for item in deferred)


def test_paragraph_anchor_rejects_unrelated_witness_even_when_text_is_in_body() -> None:
    plan_row = {
        "required_field_candidate_ids": ["field:normalize:operation"],
        "required_publication_slot_ids": ["slot:operation"],
        "required_edge_ids": ["edge:flow"],
        "witness_contract": {
            "targets": [
                {
                    "target_kind": "field",
                    "target_id": "field:normalize:operation",
                    "semantic_atom": "normalize inputs",
                    "required_conditions": ["when score exceeds threshold"],
                    "allowed_exact_excerpts": ["normalize inputs"],
                },
                {
                    "target_kind": "slot",
                    "target_id": "slot:operation",
                    "semantic_atom": "normalize inputs",
                    "required_conditions": ["when score exceeds threshold"],
                },
                {
                    "target_kind": "edge",
                    "target_id": "edge:flow",
                    "semantic_atom": "encoder produces scores",
                },
            ]
        },
    }
    body = (
        "The method performs normalize inputs when score exceeds threshold; "
        "the encoder produces scores."
    )
    transaction = {
        "paragraph_id": "paragraph:1",
        "paragraph_markdown": body,
        "rendered_field_candidate_ids": ["field:normalize:operation"],
        "rendered_slot_ids": ["slot:operation"],
        "rendered_edge_ids": ["edge:flow"],
        "witnesses": [
            {
                "witness_kind": "field",
                "target_id": "field:normalize:operation",
                "exact_text": "encoder produces scores",
            },
            {
                "witness_kind": "slot",
                "target_id": "slot:operation",
                "exact_text": "normalize inputs when score exceeds threshold",
            },
            {
                "witness_kind": "edge",
                "target_id": "edge:flow",
                "exact_text": "encoder produces scores",
            },
        ],
    }

    assessment = assess_paragraph_transaction(
        transaction,
        plan_row=plan_row,
        required_anchors=required_anchors_from_plan_row(plan_row),
    )

    assert not assessment.valid
    assert "semantic_anchor_missing:field:field:normalize:operation" in assessment.semantic_failures


def test_paragraph_condition_polarity_mutation_is_rejected() -> None:
    plan_row = {
        "required_field_candidate_ids": ["field:normalize:condition"],
        "witness_contract": {
            "targets": [{
                "target_kind": "field",
                "target_id": "field:normalize:condition",
                "semantic_atom": "select high scores",
                "required_polarity": "threshold_gt_selects",
                "required_conditions": ["score > threshold"],
                "allowed_exact_excerpts": ["score > threshold"],
            }],
        },
    }
    transaction = {
        "paragraph_id": "paragraph:polarity",
        "paragraph_markdown": "The method selects inputs when score < threshold.",
        "rendered_field_candidate_ids": ["field:normalize:condition"],
        "witnesses": [{
            "witness_kind": "field",
            "target_id": "field:normalize:condition",
            "exact_text": "selects inputs when score < threshold",
        }],
    }

    assessment = assess_paragraph_transaction(
        transaction,
        plan_row=plan_row,
        required_anchors=required_anchors_from_plan_row(plan_row),
    )

    assert not assessment.valid
    assert "condition_or_polarity_mismatch:field:field:normalize:condition" in assessment.semantic_failures


def test_binder_recovers_code_normalization_from_reader_facing_anchor() -> None:
    slot = SimpleNamespace(
        role="transformation",
        predicate="normalizes",
        operands=(
            "torch.nn.functional.normalize",
            "positional_encoding",
            "p=2",
            "dim=2",
            "result=positional_encoding",
        ),
        produced_entities=(),
        conditions=(),
    )
    semantic_atom = _reader_facing_slot_semantic_atom(slot)
    transaction = {
        "paragraph_id": "paragraph:normalization",
        "paragraph_markdown": (
            "The sinusoidal positional encoding is computed from passage positions "
            "and then subjected to L2 normalization along the embedding dimension."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:normalization"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:normalization",
            "semantic_atom": semantic_atom,
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:normalization"]
    assert len(bound["witnesses"]) == 1


def test_binder_recovers_residual_attention_update_from_reader_facing_anchor() -> None:
    slot = SimpleNamespace(
        role="transformation",
        predicate="computes_formula",
        operands=(
            "src",
            "result=src + dropout1(shared_out + dedicated_out)",
        ),
        produced_entities=(),
        conditions=(),
    )
    semantic_atom = _reader_facing_slot_semantic_atom(slot)
    assert "attention" in semantic_atom
    assert "dropout" in semantic_atom
    assert "residual" in semantic_atom

    transaction = {
        "paragraph_id": "paragraph:attention:update",
        "paragraph_markdown": (
            "The two attention outputs are summed, passed through dropout, "
            "and added to the residual connection."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:attention:update"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:attention:update",
            "semantic_atom": semantic_atom,
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:attention:update"]
    assert len(bound["witnesses"]) == 1


def test_binder_recovers_attention_return_without_source_variable_names() -> None:
    slot = SimpleNamespace(
        role="output",
        predicate="returns",
        operands=("src", "shared_attn_weights"),
        produced_entities=(),
        conditions=(),
    )
    semantic_atom = _reader_facing_slot_semantic_atom(slot)
    assert semantic_atom == "return attention weights"
    transaction = {
        "paragraph_id": "paragraph:attention:return",
        "paragraph_markdown": (
            "When requested, the module returns the shared attention weights "
            "alongside the updated representation."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:attention:return"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:attention:return",
            "semantic_atom": semantic_atom,
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:attention:return"]
    assert len(bound["witnesses"]) == 1


def test_binder_recovers_legacy_residual_slot_anchor() -> None:
    """Frozen plans may still contain the pre-reader-facing source atom."""

    transaction = {
        "paragraph_id": "paragraph:legacy:residual",
        "paragraph_markdown": (
            "The two attention outputs are combined, passed through dropout, "
            "and added through a residual connection."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:legacy:residual"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:legacy:residual",
            "semantic_atom": "combines src first dropout shared out dedicated",
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:legacy:residual"]
    assert len(bound["witnesses"]) == 1


def test_binder_semantic_fallback_does_not_prefer_code_excerpt_over_reader_text() -> None:
    transaction = {
        "paragraph_id": "paragraph:legacy:attention-facet",
        "paragraph_markdown": (
            "The hybrid attention mechanism combines a shared full attention "
            "module with a dedicated masked attention module. "
            "The dedicated masked attention is activated when the configuration "
            "flag for dedicated attention is set (`self.cfg.use_dedicated_attention`)."
        ),
        "rendered_from_facet_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_facet_ids": ["facet:attention"],
        "witness_contract": {"targets": [{
            "target_kind": "facet",
            "target_id": "facet:attention",
            "semantic_atom": (
                "dedicated masked attention attend multi head that restricts "
                "passage from same document"
            ),
            "allowed_exact_excerpts": ["if self.cfg.use_dedicated_attention:"],
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_from_facet_ids"] == ["facet:attention"]
    assert bound["witnesses"][0]["exact_text"].startswith(
        "The hybrid attention mechanism"
    )


def test_binder_prefers_specific_raw_slot_over_sibling_derived_anchor() -> None:
    """A frozen config slot must not be lost to a sibling hybrid facet sentence."""

    transaction = {
        "paragraph_id": "MA-S3:p3",
        "paragraph_markdown": (
            "The hybrid attention mechanism combines a shared full attention "
            "module with a dedicated masked attention module. The dedicated "
            "masked attention is active when `self.cfg.use_dedicated_attention`."
        ),
        "rendered_slot_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_publication_slot_ids": ["slot:dedicated-attention"],
        "witness_contract": {"targets": [{
            "target_kind": "slot",
            "target_id": "slot:dedicated-attention",
            "semantic_atom": "enable use dedicated attention attend",
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_slot_ids"] == ["slot:dedicated-attention"]
    assert "use_dedicated_attention" in bound["witnesses"][0]["exact_text"]


def test_binder_splits_prose_around_formula_before_semantic_recovery() -> None:
    transaction = {
        "paragraph_id": "paragraph:formula:boundary",
        "paragraph_markdown": (
            "The hybrid attention mechanism combines global and local pathways "
            "$$\n"
            "y = x + z\n"
            "$$ and exposes attention weights for analysis."
        ),
        "rendered_from_facet_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_facet_ids": ["facet:hybrid"],
        "witness_contract": {"targets": [{
            "target_kind": "facet",
            "target_id": "facet:hybrid",
            "semantic_atom": "hybrid attention combines global local pathways",
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_from_facet_ids"] == ["facet:hybrid"]
    assert bound["witnesses"][0]["exact_text"].startswith(
        "The hybrid attention mechanism"
    )


def test_binder_does_not_use_display_math_for_an_omitted_mechanism_facet() -> None:
    transaction = {
        "paragraph_id": "paragraph:ranking",
        "paragraph_markdown": (
            "The inference procedure computes similarity scores and sorts the "
            "passages in descending order. $$\n"
            "scores = \\operatorname{sort}(similarities)\n$$"
        ),
        "rendered_from_facet_ids": [],
        "witnesses": [],
    }
    plan_row = {
        "required_facet_ids": ["facet:ranking"],
        "witness_contract": {"targets": [{
            "target_kind": "facet",
            "target_id": "facet:ranking",
            "semantic_atom": (
                "inference scoring compute similarity and sort descending"
            ),
        }]},
    }

    bound = bind_paragraph_witnesses(transaction, plan_row=plan_row)

    assert bound["rendered_from_facet_ids"] == ["facet:ranking"]
    assert len(bound["witnesses"]) == 1
    assert "inference procedure" in bound["witnesses"][0]["exact_text"]


def test_formula_package_without_unique_consumer_is_not_accepted() -> None:
    obligation = MethodFormulaObligationV2(
        obligation_id="formula:normalize",
        mathematical_goal="normalize the score vector",
        paragraph_ids=("paragraph:one", "paragraph:two"),
    )
    package = SectionFormulaPackageV1(
        package_id="package:normalize",
        section_id="section:method",
        obligation_id=obligation.obligation_id,
        purpose="Explain normalization",
        latex="z=x/\\|x\\|",
        prose_explanation="The vector is normalized.",
        authority_status="code_verified",
        bound_equation_ids=("equation:normalize",),
    )

    result = section_result_from_packages(
        section_id="section:method",
        packages=(package,),
        formula_obligations=(obligation,),
    )

    assert result.packages == ()
    assert "consumer_not_unique:formula:normalize" in result.formula_route_failures
    assert result.required_formula_failures == ("formula:normalize",)
