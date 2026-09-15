from __future__ import annotations

import pytest
from code2paper.agentic.mechanism_context_compiler import (
    annotate_mechanism_paper_details,
    compile_mechanism_contexts,
    compile_mechanism_evidence_closures,
    validate_mechanism_context_completeness,
    validate_mechanism_context_structural_gates,
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


# ---------------------------------------------------------------------------
# R1: same-operation dual-view guard/status aggregation and its fail-closed
# negatives.  Every case goes through the public compile -> validate path; the
# private aggregation is never the only thing under test.
# ---------------------------------------------------------------------------

_R1_SPAN = "span:src/model.py:146:149"
_R1_BRANCH_SPAN = "span:src/model.py:145:174"
_R1_MANIFEST = {
    "entries": [{
        "path": "src/model.py",
        "source_kind": "first_party_executable",
        "content_digest": "sha256:model-entry",
    }],
}
_R1_FACETS = [{
    "facet_id": "facet:dual",
    "mechanism_id": "mech_model_forward",
    "author_statement": "Dedicated attention mask under configuration.",
}]
_R1_ALIGNMENTS = [{
    "facet_id": "facet:dual",
    "bound_fact_ids": ["fact:dual:zero-mask"],
    "bound_span_ids": [_R1_SPAN],
}]
_R1_CLAIMS = {
    "claims": [{
        "claim_id": "claim:dual:zero-mask",
        "fact_ids": ["fact:dual:zero-mask"],
        "validation_status": "supported",
    }],
}
_R1_CONFIG = {
    "claims": [{
        "configuration_id": "config:dual:flag",
        "key": "self.cfg.use_dedicated_attention",
        "value": None,
        "state": "unresolved",
        "definition_span_ids": [],
        "entrypoint_span_ids": [],
        "source_fact_ids": ["fact:dual:zero-mask"],
        "unresolved_reason": "config_access_unresolved:no_definition_or_entrypoint_value_evidence",
    }],
}


def _r1_facts(guard: str = "self.cfg.use_dedicated_attention") -> list[dict[str, object]]:
    return [{
        "fact_id": "fact:dual:zero-mask",
        "subject": "Model.forward",
        "predicate": "calls",
        "operands": ["torch.zeros", "shape", "device=self.device"],
        "result": "dedicated_attention_mask",
        "conditions": [guard] if guard else [],
        "scope": "sym:model_forward",
        "direct_span_ids": [_R1_SPAN],
        "validation_status": "supported",
        "validation_failures": [],
    }]


def _r1_graph(
    *,
    branch_guard: str = "self.cfg.use_dedicated_attention",
    branch_span: str = _R1_BRANCH_SPAN,
    call_predicate: str = "CALL",
    call_operands: tuple[str, ...] = ("torch.zeros", "shape", "device=self.device"),
    relations: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "nodes": [
            {
                "node_id": "node:branch-mask",
                "symbol_id": "sym:model_forward",
                "predicate": "BRANCH",
                "operands": [branch_guard],
                "result": "",
                "guard": branch_guard,
                "source_span_id": branch_span,
            },
            {
                "node_id": "node:call-zeros",
                "symbol_id": "sym:model_forward",
                "predicate": call_predicate,
                "operands": list(call_operands),
                "result": "dedicated_attention_mask",
                "guard": "",
                "source_span_id": _R1_SPAN,
            },
        ],
        "relations": [{
            "relation_id": "rel:true-branch-mask",
            "kind": "TRUE_BRANCH",
            "source_node_id": "node:branch-mask",
            "target_node_id": "node:call-zeros",
            "source_span_id": branch_span,
            "target_span_id": _R1_SPAN,
            "guard": branch_guard,
        }, *relations],
    }


def _r1_compile(
    *,
    facts: list[dict[str, object]] | None = None,
    graph: dict[str, object] | None = None,
    configurations: object | None = _R1_CONFIG,
):
    return compile_mechanism_contexts(
        facets=_R1_FACETS,
        facet_alignments=_R1_ALIGNMENTS,
        facts={"facts": facts if facts is not None else _r1_facts()},
        claims=_R1_CLAIMS,
        configurations=configurations,
        behavior_graph=graph if graph is not None else _r1_graph(),
        implementation_scope={
            "schema_version": "1.0",
            "target_entry_symbol_ids": ["sym:model_forward"],
            "target_core_symbol_ids": ["sym:model_forward"],
        },
        source_manifest=_R1_MANIFEST,
    )


def _r1_detail(ctx):
    return next(
        detail
        for detail in ctx.details
        if detail.source_span_ids and _R1_SPAN in detail.source_span_ids
    )


def test_dual_view_guard_alignment_resolves_core_active_path() -> None:
    cset = _r1_compile()
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    assert detail.importance == "core"
    assert detail.active_path_status == "conditional"
    # The recovered condition is preserved on the detail, backed by the typed
    # frozen TRUE_BRANCH relation that dominated the graph operation.
    assert detail.conditions == ("self.cfg.use_dedicated_attention",)
    assert detail.mismatch_reason == ""
    assert "rel:true-branch-mask" in detail.activation_basis_ids

    assert validate_mechanism_context_completeness(ctx, source_manifest=_R1_MANIFEST) == ()
    diagnostics = validate_mechanism_context_structural_gates(cset)
    assert diagnostics["unknown_core_active_path_count"] == 0
    assert diagnostics["core_ownerless_count"] == 0


def test_dual_view_guard_conflict_stays_unknown_with_reason() -> None:
    cset = _r1_compile(graph=_r1_graph(branch_guard="self.cfg.other_flag"))
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    # Two views of one operation name different guards.  Distinct condition
    # texts are not provably equivalent, so the detail must not be promoted.
    assert detail.active_path_status == "unknown"
    assert detail.mismatch_reason == (
        "guard_conflict:self.cfg.use_dedicated_attention|self.cfg.other_flag"
    )
    assert (
        f"core_detail_active_path_unknown:{detail.detail_id}"
        in validate_mechanism_context_completeness(ctx, source_manifest=_R1_MANIFEST)
    )
    assert validate_mechanism_context_structural_gates(cset)[
        "unknown_core_active_path_count"
    ] >= 1


def test_dual_view_correspondence_missing_stays_unknown() -> None:
    # A nested LOAD at the same span is a different operation, not a second
    # view of the call; same-span equality alone must not merge it.  The LOAD
    # is reachable on the default path (it is not dominated by the branch),
    # so the cluster mixes a conditional fact view with an active_default
    # graph view and cannot be collapsed without correspondence proof.
    graph = {
        "nodes": [
            {
                "node_id": "node:prologue",
                "symbol_id": "sym:model_forward",
                "predicate": "LOAD",
                "operands": ["batch_size"],
                "result": "batch_size",
                "guard": "",
                "source_span_id": "span:src/model.py:140:140",
            },
            {
                "node_id": "node:branch-mask",
                "symbol_id": "sym:model_forward",
                "predicate": "BRANCH",
                "operands": ["self.cfg.use_dedicated_attention"],
                "result": "",
                "guard": "self.cfg.use_dedicated_attention",
                "source_span_id": _R1_BRANCH_SPAN,
            },
            {
                "node_id": "node:nested-load",
                "symbol_id": "sym:model_forward",
                "predicate": "LOAD",
                "operands": ["torch.zeros"],
                "result": "dedicated_attention_mask",
                "guard": "",
                "source_span_id": _R1_SPAN,
            },
        ],
        "relations": [{
            "relation_id": "rel:next-control",
            "kind": "NEXT_CONTROL",
            "source_node_id": "node:prologue",
            "target_node_id": "node:nested-load",
            "source_span_id": "span:src/model.py:140:140",
            "target_span_id": _R1_SPAN,
            "guard": "",
        }],
    }
    cset = _r1_compile(graph=graph)
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    assert detail.active_path_status == "unknown"
    assert detail.mismatch_reason == "dual_view_correspondence_missing"
    assert (
        f"core_detail_active_path_unknown:{detail.detail_id}"
        in validate_mechanism_context_completeness(ctx, source_manifest=_R1_MANIFEST)
    )
    # The two same-span operations stay individually archived and named.
    nested = next(
        operation
        for operation in ctx.evidence_closure.operation_nodes
        if operation.operation_id == "graph-operation:node:nested-load"
    )
    assert nested.predicate == "LOAD"
    assert nested.guard == ""
    assert nested.active_path_status == "active_default"
    assert len(detail.source_operation_ids) == 2


def test_polarity_conflict_keeps_operation_unresolved() -> None:
    conflicting = {
        "relation_id": "rel:false-branch-mask",
        "kind": "FALSE_BRANCH",
        "source_node_id": "node:branch-mask",
        "target_node_id": "node:call-zeros",
        "source_span_id": _R1_BRANCH_SPAN,
        "target_span_id": _R1_SPAN,
        "guard": "self.cfg.use_dedicated_attention",
    }
    cset = _r1_compile(graph=_r1_graph(relations=(conflicting,)))
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)
    failures = validate_mechanism_context_completeness(ctx, source_manifest=_R1_MANIFEST)

    # The graph claims both polarities for one guard: nothing may be promoted
    # to core, and the unresolved disposition stays fail-closed.
    assert detail.active_path_status == "unknown"
    assert detail.importance != "core"
    assert detail.mismatch_reason == (
        "path_polarity_conflict:self.cfg.use_dedicated_attention"
    )
    assert "operation_disposition_unresolved" in failures


def test_unproven_dominance_does_not_align_conditional() -> None:
    cset = _r1_compile(graph=_r1_graph(branch_span="span:src/model.py:100:110"))
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    # The guarded typed edge exists but does not dominate this span; the
    # conditional claim may not be scoped here silently.
    assert detail.active_path_status == "unknown"
    assert detail.mismatch_reason == (
        "guard_dominance_unproven:self.cfg.use_dedicated_attention"
    )


def test_unconditional_default_path_stays_active_default() -> None:
    cset = _r1_compile(
        facts=_r1_facts(guard=""),
        graph=_r1_graph(branch_guard=""),
    )
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    # No guard anywhere: the proven default path is reported as such.
    assert detail.active_path_status == "active_default"
    assert detail.conditions == ()
    assert detail.polarity == "positive"


def test_unresolved_config_never_claims_actual_selection() -> None:
    cset = _r1_compile()
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    # The frozen Run E shape: the guard is precisely known while the selected
    # configuration value is unresolved, so only the proven conditional
    # behaviour is expressed; selection is never invented.
    assert detail.active_path_status == "conditional"
    assert detail.active_path_status != "active_selected"
    assert all(
        not basis.startswith("selected")
        for basis in detail.activation_basis_ids
    )
    binding = next(
        item
        for item in ctx.evidence_closure.configuration_bindings
        if item.get("key") == "self.cfg.use_dedicated_attention"
    )
    assert binding.get("value") is None
    assert binding.get("state") == "unresolved"


def test_same_span_dominance_aligns_guardless_fact_view() -> None:
    """A fact operation at a span a graph node is proven dominated at.

    The frozen Run E rebuild exposed this shape: the ``computes_formula``
    fact inside ``if self.cfg.add_positional_encoding:`` carries no
    condition, while the graph node at the same exact span is condition
    dominated by a typed TRUE_BRANCH edge.  The exact-span proof must align
    the fact view instead of leaving a permanent mixed-status unknown.
    """

    facts = [{
        "fact_id": "fact:dual:zero-mask",
        "subject": "Model.forward",
        "predicate": "computes_formula",
        "operands": ["passages", "document_id_embeddings"],
        "result": "passages",
        "conditions": [],
        "scope": "sym:model_forward",
        "direct_span_ids": [_R1_SPAN],
        "validation_status": "supported",
        "validation_failures": [],
    }]
    cset = _r1_compile(facts=facts)
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    assert detail.active_path_status == "conditional"
    assert detail.conditions == ("self.cfg.use_dedicated_attention",)
    assert detail.mismatch_reason == ""
    fact_op = next(
        operation
        for operation in ctx.evidence_closure.operation_nodes
        if operation.operation_id == "fact-operation:fact:dual:zero-mask"
    )
    assert fact_op.guard == "self.cfg.use_dedicated_attention"
    assert fact_op.active_path_status == "conditional"
    assert f"same_span_dominance:{_R1_SPAN}" in fact_op.activation_basis_ids
    assert "rel:true-branch-mask" in fact_op.activation_basis_ids
    assert validate_mechanism_context_completeness(ctx, source_manifest=_R1_MANIFEST) == ()


def test_contested_span_is_not_silently_aligned() -> None:
    """An unproven guarded edge on the span suppresses span-level alignment."""

    graph = _r1_graph()
    # A second node on the same span whose guarded typed edge cannot prove
    # bounded dominance makes the span contested.
    graph["nodes"].append({
        "node_id": "node:far-branch",
        "symbol_id": "sym:model_forward",
        "predicate": "BRANCH",
        "operands": ["self.cfg.other_flag"],
        "result": "",
        "guard": "self.cfg.other_flag",
        "source_span_id": "span:src/model.py:300:310",
    })
    graph["nodes"].append({
        "node_id": "node:far-call",
        "symbol_id": "sym:model_forward",
        "predicate": "COMPUTE",
        "operands": ["passages"],
        "result": "passages",
        "guard": "",
        "source_span_id": _R1_SPAN,
    })
    graph["relations"].append({
        "relation_id": "rel:far-branch",
        "kind": "TRUE_BRANCH",
        "source_node_id": "node:far-branch",
        "target_node_id": "node:far-call",
        "source_span_id": "span:src/model.py:300:310",
        "target_span_id": _R1_SPAN,
        "guard": "self.cfg.other_flag",
    })

    facts = [{
        "fact_id": "fact:dual:zero-mask",
        "subject": "Model.forward",
        "predicate": "computes_formula",
        "operands": ["passages", "document_id_embeddings"],
        "result": "passages",
        "conditions": [],
        "scope": "sym:model_forward",
        "direct_span_ids": [_R1_SPAN],
        "validation_status": "supported",
        "validation_failures": [],
    }]
    cset = _r1_compile(facts=facts, graph=graph)
    ctx = cset.contexts[0]

    fact_op = next(
        operation
        for operation in ctx.evidence_closure.operation_nodes
        if operation.operation_id == "fact-operation:fact:dual:zero-mask"
    )
    # Contested evidence must not be resolved by the span shortcut.
    assert fact_op.guard == ""
    assert fact_op.active_path_status == "active_default"
    assert all(
        not basis.startswith("same_span_dominance:")
        for basis in fact_op.activation_basis_ids
    )
    detail = _r1_detail(ctx)
    assert detail.active_path_status == "unknown"
    # The contested guarded edge is named as the reason instead of being
    # resolved by the span shortcut.
    assert detail.mismatch_reason == "guard_dominance_unproven:self.cfg.other_flag"


def test_resolved_false_config_disables_bound_operation() -> None:
    config = {
        "claims": [{
            "configuration_id": "config:dual:flag",
            "key": "self.cfg.use_dedicated_attention",
            "value": False,
            "state": "resolved",
            "active": False,
            "definition_span_ids": [_R1_SPAN],
            "entrypoint_span_ids": [],
        }],
    }
    cset = _r1_compile(configurations=config)
    ctx = cset.contexts[0]
    detail = _r1_detail(ctx)

    # A resolved disabled configuration is not silently upgraded into an
    # active path; the existing binding precedence still applies and the
    # detail cannot be promoted to core.
    assert detail.active_path_status in {"inactive_default", "unreachable", "unknown"}
    assert detail.active_path_status != "conditional"
    assert detail.importance != "core"


def test_context_set_json_round_trip_preserves_path_evidence() -> None:
    from code2paper.agentic.mechanism_context_models import (
        load_mechanism_context_set_v1_payload,
    )

    cset = _r1_compile()
    payload = cset.model_dump(mode="json")
    restored, migrated = load_mechanism_context_set_v1_payload(payload)

    assert migrated is False
    assert restored.content_digest == cset.content_digest
    before = _r1_detail(cset.contexts[0])
    after = _r1_detail(restored.contexts[0])
    assert after.active_path_status == before.active_path_status == "conditional"
    assert after.conditions == before.conditions
    assert after.activation_basis_ids == before.activation_basis_ids
    assert validate_mechanism_context_completeness(
        restored.contexts[0], source_manifest=_R1_MANIFEST
    ) == ()


def test_dual_view_recovery_does_not_leak_across_owners() -> None:
    cset = _r1_compile()
    for ctx in cset.contexts:
        closure_operation_ids = {
            operation.operation_id for operation in ctx.evidence_closure.operation_nodes
        }
        for detail in ctx.details:
            assert set(detail.source_operation_ids) <= closure_operation_ids
            # Every detail keeps exactly one primary owner.
            assert detail.primary_mechanism_id == ctx.mechanism_id
