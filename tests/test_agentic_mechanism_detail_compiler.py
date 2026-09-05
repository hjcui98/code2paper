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
    assert ctx.importance == "core"
    assert ctx.source_context_digest.startswith("sha256:")
