from __future__ import annotations

import pytest
from code2paper.agentic.mechanism_context_compiler import (
    annotate_mechanism_paper_details,
    compile_mechanism_contexts,
    compile_mechanism_evidence_closures,
)


def test_annotate_mechanism_paper_details_terminal_coverage() -> None:
    mock_facts = [
        {
            "fact_id": "fact:linear:1",
            "subject": "entity_scores",
            "predicate": "propagate",
            "operands": ["active_entities", "sentences"],
            "result": "sentence_scores",
            "guard": "score >= iteration_threshold",
            "direct_span_ids": ["span:prop.py:5:12"],
            "scope": "propagate_frontier",
        },
        {
            "fact_id": "fact:linear:2",
            "subject": "sentence_scores",
            "predicate": "prune",
            "operands": ["sentence_scores", "threshold"],
            "result": "pruned_sentences",
            "direct_span_ids": ["span:prop.py:15:20"],
            "scope": "propagate_frontier",
        },
    ]
    facets = [
        {
            "facet_id": "facet:activation",
            "mechanism_id": "mech_activation_frontier",
            "author_statement": "Entity activation via propagation and dynamic threshold pruning.",
        },
    ]
    alignments = [
        {
            "facet_id": "facet:activation",
            "bound_fact_ids": ["fact:linear:1", "fact:linear:2"],
            "bound_span_ids": ["span:prop.py:5:12", "span:prop.py:15:20"],
        },
    ]

    closures = compile_mechanism_evidence_closures(
        facets=facets,
        facet_alignments=alignments,
        facts=mock_facts,
    )
    context_set = annotate_mechanism_paper_details(closures)

    assert len(context_set.contexts) == 1
    ctx = context_set.contexts[0]
    assert ctx.mechanism_id == "mech_activation_frontier"
    assert len(ctx.details) == 2

    # Invariant I3: Terminal coverage must be 1.0
    closure = ctx.evidence_closure
    assert closure.source_operation_terminal_coverage == 1.0
    assert len(closure.operation_dispositions) == 2
    for disp in closure.operation_dispositions:
        assert disp.disposition in ("absorbed_by_detail", "classified_supporting")

    # Check detail 1 has witness atoms for operation, operand, output, and condition
    d1 = ctx.details[0]
    atom_kinds = [a.atom_kind for a in d1.witness_atoms]
    assert "operation" in atom_kinds
    assert "operand" in atom_kinds
    assert "output" in atom_kinds
    assert "condition" in atom_kinds

    # Check edge between detail 1 and detail 2
    assert len(ctx.edges) == 1
    edge = ctx.edges[0]
    assert edge.source_detail_id == d1.detail_id
    assert edge.target_detail_id == ctx.details[1].detail_id


def test_compile_mechanism_contexts_end_to_end() -> None:
    mock_facts = [
        {
            "fact_id": "fact:ebcar:1",
            "subject": "attention_mask",
            "predicate": "apply_mask",
            "operands": ["doc_ids", "same_document"],
            "result": "masked_logits",
            "direct_span_ids": ["span:mask.py:1:5"],
            "scope": "dedicated_mask",
        },
    ]
    facets = [
        {
            "facet_id": "facet:mask",
            "mechanism_id": "mech_ebcar_attention",
            "author_statement": "Dedicated same-document attention mask.",
        },
    ]
    alignments = [
        {
            "facet_id": "facet:mask",
            "bound_fact_ids": ["fact:ebcar:1"],
            "bound_span_ids": ["span:mask.py:1:5"],
        },
    ]

    cset = compile_mechanism_contexts(
        facets=facets,
        facet_alignments=alignments,
        facts=mock_facts,
    )
    assert len(cset.contexts) == 1
    ctx = cset.contexts[0]
    assert ctx.mechanism_id == "mech_ebcar_attention"
    # Core is a conjunction: without a source manifest the operation authority
    # is unknown, so the detail stays supporting evidence and can never be a
    # repository-verified core.
    assert ctx.importance == "supporting"
    assert all(detail.importance != "core" for detail in ctx.details)
    assert ctx.source_context_digest.startswith("sha256:")


def test_core_requires_first_party_manifest_authority() -> None:
    """The same fixture becomes core only with first-party manifest authority."""

    mock_facts = [
        {
            "fact_id": "fact:ebcar:1",
            "subject": "attention_mask",
            "predicate": "apply_mask",
            "operands": ["doc_ids", "same_document"],
            "result": "masked_logits",
            "direct_span_ids": ["span:mask.py:1:5"],
            "scope": "dedicated_mask",
        },
    ]
    facets = [
        {
            "facet_id": "facet:mask",
            "mechanism_id": "mech_ebcar_attention",
            "author_statement": "Dedicated same-document attention mask.",
        },
    ]
    alignments = [
        {
            "facet_id": "facet:mask",
            "bound_fact_ids": ["fact:ebcar:1"],
            "bound_span_ids": ["span:mask.py:1:5"],
        },
    ]
    source_manifest = {
        "entries": [
            {
                "path": "mask.py",
                "source_kind": "first_party_executable",
                "content_digest": "sha256:mask-entry",
            },
        ],
    }

    cset = compile_mechanism_contexts(
        facets=facets,
        facet_alignments=alignments,
        facts=mock_facts,
        source_manifest=source_manifest,
    )

    ctx = cset.contexts[0]
    assert ctx.importance == "core"
    assert [detail.importance for detail in ctx.details] == ["core"]
    assert ctx.details[0].evidence_authority == "repository_verified"
    assert ctx.connected_input_to_output is True


def test_core_requires_evidence_derived_endpoints() -> None:
    """A closed dataflow cycle has no input endpoint, so nothing is core."""

    mock_facts = [
        {
            "fact_id": "fact:cycle:1",
            "subject": "left",
            "predicate": "mix",
            "operands": ["right"],
            "result": "left",
            "direct_span_ids": ["span:cycle.py:1:2"],
            "scope": "Model.forward",
        },
        {
            "fact_id": "fact:cycle:2",
            "subject": "right",
            "predicate": "mix",
            "operands": ["left"],
            "result": "right",
            "direct_span_ids": ["span:cycle.py:3:4"],
            "scope": "Model.forward",
        },
    ]
    facets = [
        {
            "facet_id": "facet:cycle",
            "mechanism_id": "mech_cycle",
            "author_statement": "Two mutually consuming buffers.",
        },
    ]
    alignments = [
        {
            "facet_id": "facet:cycle",
            "bound_fact_ids": ["fact:cycle:1", "fact:cycle:2"],
            "bound_span_ids": ["span:cycle.py:1:2", "span:cycle.py:3:4"],
        },
    ]
    source_manifest = {
        "entries": [
            {
                "path": "cycle.py",
                "source_kind": "first_party_executable",
                "content_digest": "sha256:cycle-entry",
            },
        ],
    }

    cset = compile_mechanism_contexts(
        facets=facets,
        facet_alignments=alignments,
        facts=mock_facts,
        source_manifest=source_manifest,
    )

    ctx = cset.contexts[0]
    assert ctx.input_detail_ids == ()
    assert ctx.connected_input_to_output is False
    assert all(detail.importance != "core" for detail in ctx.details)
    assert "core_path_endpoint_unknown" in ctx.unresolved_items
    # The operations remain archived as supporting evidence.
    assert len(ctx.details) == 2
