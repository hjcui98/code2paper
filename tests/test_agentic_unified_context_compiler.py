from __future__ import annotations

from code2paper.agentic.formalization_agent import MechanismFormulaObligationV1
from code2paper.agentic.mechanism_context_models import (
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)
from code2paper.agentic.unified_context_compiler import (
    build_consumer_workset_manifest_v2,
    build_unified_context_archive_v2,
)
def test_qualified_equation_id_is_not_double_prefixed_in_formula_page() -> None:
    """A frozen ``equation:*`` ID must resolve to the same archive atom."""

    operation = EvidenceOperationV1(
        operation_id="op:loss",
        predicate="compute_loss",
        operands=("x",),
        result="loss",
        source_span_id="",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:loss",
        mechanism_id="mech_loss",
        operation_nodes=(operation,),
        equation_ids=("equation:fact-loss",),
        operation_dispositions=(SourceOperationDispositionV1(
            operation_id=operation.operation_id,
            disposition="absorbed_by_detail",
            detail_ids=("d:loss",),
        ),),
        source_operation_terminal_coverage=1.0,
    )
    detail = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_loss",
        order_index=0,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="unresolved",
        publication_policy="review_only",
        semantic_atom="compute loss",
        predicate="compute_loss",
        operands=("x",),
        result="loss",
        active_path_status="active_default",
        source_operation_ids=(operation.operation_id,),
        source_equation_ids=("equation:fact-loss",),
        formalizable=True,
    )
    context = MechanismContextV1(
        mechanism_id="mech_loss",
        mechanism_name="Loss",
        scientific_role="training_objective",
        reader_question="What is optimized?",
        purpose="Compute the objective.",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=(detail.detail_id,),
        details=(detail,),
        source_manifest_digest="sha256:manifest",
    )
    context_set = MechanismContextSetV1(
        repo_snapshot_id="repo:test",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:alignment",
        research_digest="sha256:research",
        contexts=(context,),
    )
    equations = ({
        "equation_id": "equation:fact-loss",
        "expression": "L = f(x)",
        "fact_ids": [],
        "symbol_bindings": [],
        "canonical_identity": "sha256:equation",
    },)
    archive = build_unified_context_archive_v2(
        context_set,
        source_manifest_digest="sha256:manifest",
        equations=equations,
    )
    obligation = MechanismFormulaObligationV1(
        obligation_id="ob:loss",
        mechanism_id=context.mechanism_id,
        source_detail_ids=(detail.detail_id,),
        source_equation_ids=("equation:fact-loss",),
        mathematical_goal="Formalize the loss.",
    )

    assert tuple(atom.atom_id for atom in archive.equation_atoms) == (
        "equation:fact-loss",
    )
    manifest = build_consumer_workset_manifest_v2(
        archive,
        {context.mechanism_id: (obligation,)},
        max_page_input_tokens=20_000,
        max_obligations_per_page=8,
    )
    assert "equation:fact-loss" in manifest.worksets[0].required_atom_ids
    assert all(
        not atom_id.startswith("equation:equation:")
        for atom_id in manifest.worksets[0].required_atom_ids
    )


def test_archive_stores_shared_operation_once_with_canonical_owner() -> None:
    """Two mechanisms sharing one dependency operation must not conflict."""

    from code2paper.agentic.mechanism_context_compiler import (
        annotate_mechanism_paper_details,
        compile_mechanism_evidence_closures,
    )
    from code2paper.agentic.unified_context_compiler import (
        build_unified_context_archive_v2,
    )

    facts = [
        {
            "fact_id": "fact:shared",
            "subject": "shared",
            "predicate": "load",
            "operands": ["path"],
            "result": "loaded",
            "direct_span_ids": ["span:a.py:1:2"],
            "scope": "a.py",
        },
        {
            "fact_id": "fact:a",
            "subject": "loaded",
            "predicate": "encode",
            "operands": ["loaded"],
            "result": "encoded",
            "direct_span_ids": ["span:a.py:3:4"],
            "scope": "a.py",
        },
        {
            "fact_id": "fact:b",
            "subject": "loaded",
            "predicate": "decode",
            "operands": ["loaded"],
            "result": "decoded",
            "direct_span_ids": ["span:a.py:5:6"],
            "scope": "a.py",
        },
    ]
    facets = [
        {"facet_id": "facet:a", "mechanism_id": "mech_a", "author_statement": "Encode."},
        {"facet_id": "facet:b", "mechanism_id": "mech_b", "author_statement": "Decode."},
    ]
    alignments = [
        {
            "facet_id": "facet:a",
            "bound_fact_ids": ["fact:shared", "fact:a"],
            "bound_span_ids": ["span:a.py:1:2", "span:a.py:3:4"],
        },
        {
            "facet_id": "facet:b",
            "bound_fact_ids": ["fact:shared", "fact:b"],
            "bound_span_ids": ["span:a.py:1:2", "span:a.py:5:6"],
        },
    ]
    from code2paper.agentic.source_inventory import (
        RepositorySourceEntryV1,
        RepositorySourceManifestV1,
    )

    entry = RepositorySourceEntryV1(
        path="a.py",
        source_kind="first_party_executable",
        ownership_role="target_core",
        executable_authority=True,
        content_digest="sha256:a-entry",
        classification_reason="fixture:first_party_executable",
    )
    source_manifest = RepositorySourceManifestV1(
        repo_snapshot_id="repo:fixture",
        # The context set has no repository provider in this fixture, so its
        # declared tree hash is the neutral placeholder.
        project_tree_hash="tree:unknown",
        entries=(entry,),
        target_core_paths=(entry.path,),
    )

    closures = compile_mechanism_evidence_closures(
        facets=facets,
        facet_alignments=alignments,
        facts=facts,
        source_manifest=source_manifest,
    )
    assert len(closures) == 2
    context_set = annotate_mechanism_paper_details(closures)

    archive = build_unified_context_archive_v2(
        context_set,
        source_manifest_digest=source_manifest.content_digest,
        source_manifest=source_manifest,
        repo_snapshot_digest="sha256:snapshot",
    )

    shared_atoms = [
        atom for atom in archive.operation_atoms
        if atom.atom_id == "operation:fact-operation:fact:shared"
    ]
    assert len(shared_atoms) == 1
    assert shared_atoms[0].primary_mechanism_id == "mech_a"
    # Both mechanisms keep their own closure projection in the archive.
    assert len(archive.mechanism_atoms) == 2
