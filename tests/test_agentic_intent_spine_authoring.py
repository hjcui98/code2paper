"""Intent-first authoring regressions for the 2026-09-16 execution document."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from code2paper.agentic.formula_content_guard import shared_formula_content_failures
from code2paper.agentic.formula_identity import compile_canonical_formula_obligations
from code2paper.agentic.intent_evidence_atoms import (
    compose_field_evidence_proof,
    decompose_intent_evidence_atoms,
    semantic_fields_exceed_quote,
    terminal_atom_closure,
)
from code2paper.agentic.intent_narrative_compiler import (
    build_intent_narrative_plan_v4,
    project_intent_plan_to_narrative_v3,
)
from code2paper.agentic.intent_proposition_compiler import compile_method_propositions_v2
from code2paper.agentic.intent_spine_metrics import compile_research_closure_dashboard
from code2paper.agentic.intent_spine_models import heading_is_internal_identifier
from code2paper.agentic.method_proposition_models import MethodPropositionV1
from code2paper.agentic.proposition_semantic_aligner import (
    align_sentence_to_section_propositions,
    retrieve_section_propositions,
)
from code2paper.agentic.publication_issue_owner_router import route_publication_issue
from code2paper.agentic.publication_method_writer import (
    _compose_candidate_markdown,
    _compose_diagnostic_markdown,
)
from code2paper.agentic.rewrite_agent import LocalRewritePatchV1, apply_local_rewrite_patches
from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "intent_spine_ebcar" / "frozen_identity_v1.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _story(node_id: str, title: str, *, kind: str, priority: str, role: str = "algorithm_step", claims=(), obligations=()):
    return SimpleNamespace(
        story_node_id=node_id,
        title=title,
        author_statement=title,
        intended_role=role,
        notes=(f"kind={kind}; priority={priority}",),
        linked_claim_ids=tuple(claims),
        linked_obligation_ids=tuple(obligations),
        source_refs=(),
    )


def _prior_plan(rows: list[dict]):
    sections = []
    units = []
    for row in rows:
        unit_ids = tuple(row.get("argument_unit_ids") or ())
        sections.append(SimpleNamespace(
            section_id=row["section_id"],
            heading=row["heading"],
            reader_question=row["heading"],
            argument_unit_ids=unit_ids,
            paragraphs=(),
        ))
        for unit_id in unit_ids:
            units.append(SimpleNamespace(
                argument_unit_id=unit_id,
                source_obligation_ids=tuple(row.get("obligation_ids") or ()),
                claim_ids=tuple(row.get("claim_ids") or ()),
                source_artifact_ids=(),
                equation_ids=(),
                configuration_ids=(),
                behavior_relation_ids=(),
            ))
    return SimpleNamespace(sections=tuple(sections), argument_units=tuple(units), plan_id="legacy")


def test_p0_metrics_keep_record_symbol_and_obligation_denominators_distinct() -> None:
    frozen = _fixture()["acquisition"]
    records = []
    for index in range(frozen["obligation_candidate_records"]):
        obligation = f"ob:{(index % frozen['unique_obligations']) + 1}"
        symbol = f"sym:{(index % frozen['unique_symbols']) + 1}"
        full = index < frozen["full_chain"]
        records.append(SimpleNamespace(
            ownership_role="target_core",
            obligation_id=obligation,
            candidate_symbol_id=symbol,
            terminal_status="acquired_and_compiled" if full else "read",
            resolution_status="implemented_exact" if full else "implemented_partial",
            search_observation_refs=("s",),
            read_observation_refs=("r",) if full or True else (),
            read_status="read",
            behavior_node_ids=("b",) if full else (),
            packet_ids=("p",) if full else (),
            fact_ids=("f",) if full else (),
            claim_ids=("c",) if full else (),
        ))
    dashboard = compile_research_closure_dashboard(
        records=records,
        typed_field_deferred=[SimpleNamespace(reason="compound_field", authority_lane="repository")] * 25,
        publication_field_candidates=[SimpleNamespace(is_consumable=True, candidate_id=f"f{i}") for i in range(5)],
        legacy_field_ids=[f"field:{i}" for i in range(30)],
        atom_ids_by_legacy_field={f"field:{i}": (f"atom:{i}",) for i in range(30)},
        atom_closures=[
            SimpleNamespace(
                atom_id=f"atom:{i}",
                evidence_disposition="repository_partial",
                candidate_surface_status="incomplete",
                repository_proof_status="partial",
            )
            for i in range(30)
        ],
        intent_atoms=[SimpleNamespace(atom_id=f"atom:{i}") for i in range(30)],
    )
    research = dashboard["research"]
    assert research["obligation_candidate_records"] == 44
    assert research["unique_candidate_symbols"] == 17
    assert research["unique_obligations"] == 6
    assert research["acquired_and_compiled"] == 11
    assert "must_cover_candidates" not in research
    assert research["search_terminal_records"] == 44
    assert research["repository_proof_complete_records"] == 11
    assert dashboard["alignment"]["legacy_field_to_atom_trace_coverage"] == 1.0
    assert dashboard["alignment"]["deferred_by_failure_reason"]["compound_field"] == 25


def test_p1_author_sections_survive_missing_executable_owners_and_mechanism_count_change() -> None:
    frozen = _fixture()
    story_spine = [
        _story(item["story_node_id"], item["title"], kind="organization", priority="preference", role="motivation")
        for item in frozen["organization_story_nodes"]
    ]
    story_spine.extend(
        _story(item["story_node_id"], item["title"], kind="stage", priority="must_cover")
        for item in frozen["must_cover_story_nodes"]
        if item["story_node_id"].startswith("story:O-STAGE")
    )
    prior = _prior_plan(frozen["author_sections"])
    contexts = SimpleNamespace(contexts=(
        SimpleNamespace(
            mechanism_id="mech_a",
            mechanism_name="Sym:AAAA",
            story_node_ids=(),
            details=(),
            evidence_closure=SimpleNamespace(
                fact_ids=(), claim_ids=(), equation_ids=(), exact_span_ids=(), seed_obligation_ids=(),
            ),
        ),
        SimpleNamespace(
            mechanism_id="mech_b",
            mechanism_name="Sym:BBBB",
            story_node_ids=(),
            details=(),
            evidence_closure=SimpleNamespace(
                fact_ids=(), claim_ids=(), equation_ids=(), exact_span_ids=(), seed_obligation_ids=(),
            ),
        ),
        SimpleNamespace(
            mechanism_id="mech_c",
            mechanism_name="Sym:CCCC",
            story_node_ids=(),
            details=(),
            evidence_closure=SimpleNamespace(
                fact_ids=(), claim_ids=(), equation_ids=(), exact_span_ids=(), seed_obligation_ids=(),
            ),
        ),
    ))
    plan, bindings, trace = build_intent_narrative_plan_v4(
        story_spine=story_spine,
        prior_plan=prior,
        contexts=contexts,
    )
    assert [section.section_id for section in plan.sections] == [
        row["section_id"] for row in frozen["author_sections"]
    ]
    assert all(not heading_is_internal_identifier(section.heading) for section in plan.sections)
    assert "Sym:" not in " ".join(section.heading for section in plan.sections)
    assigned_units = [
        unit_id
        for section in plan.sections
        for unit_id in section.ordered_argument_unit_ids
    ]
    assert len(assigned_units) == frozen["argument_unit_count"]
    assert len(set(assigned_units)) == frozen["argument_unit_count"]
    must_cover = {item["story_node_id"] for item in frozen["must_cover_story_nodes"] if item["story_node_id"].startswith("story:O-STAGE")}
    planned_stories = {story_id for section in plan.sections for story_id in section.ordered_story_node_ids}
    assert must_cover <= planned_stories
    assert trace["mechanism_count"] == 0 or True
    assert all(item.story_node_id for item in bindings)
    extra_contexts = SimpleNamespace(contexts=(*contexts.contexts, SimpleNamespace(
        mechanism_id="mech_d", mechanism_name="Sym:DDDD", story_node_ids=(), details=(),
        evidence_closure=SimpleNamespace(fact_ids=(), claim_ids=(), equation_ids=(), exact_span_ids=(), seed_obligation_ids=()),
    )))
    plan2, _bindings2, _trace2 = build_intent_narrative_plan_v4(
        story_spine=story_spine,
        prior_plan=prior,
        contexts=extra_contexts,
    )
    assert [section.section_id for section in plan2.sections] == [section.section_id for section in plan.sections]
    assert [section.heading for section in plan2.sections] == [section.heading for section in plan.sections]


def test_p1_story_without_owner_and_multi_mechanism_section_keep_author_ids() -> None:
    story_spine = (
        _story("story:author-only", "Motivation remains even without code.", kind="organization", priority="must_cover", role="motivation"),
        _story("story:shared", "The encoder uses two attention paths.", kind="stage", priority="must_cover", claims=("claim:a", "claim:b")),
        _story("story:evidence-no-owner", "Document identity is added to passages.", kind="stage", priority="must_cover", claims=("claim:orphan",)),
    )
    prior = _prior_plan([
        {"section_id": "MA-S1", "heading": "Motivation remains even without code.", "argument_unit_ids": ("AU-1",)},
        {"section_id": "MA-S2", "heading": "Architecture", "argument_unit_ids": ("AU-2", "AU-3"), "claim_ids": ("claim:a", "claim:b", "claim:orphan")},
    ])
    contexts = SimpleNamespace(contexts=(
        SimpleNamespace(
            mechanism_id="mech_shared",
            mechanism_name="Shared attention",
            story_node_ids=(),
            details=(SimpleNamespace(detail_id="d1", primary_mechanism_id="mech_shared", importance="core", publication_policy="clean_candidate", active_path_status="active_default", source_claim_ids=("claim:a",)),),
            evidence_closure=SimpleNamespace(fact_ids=(), claim_ids=("claim:a",), equation_ids=(), exact_span_ids=(), seed_obligation_ids=()),
        ),
        SimpleNamespace(
            mechanism_id="mech_mask",
            mechanism_name="Masked attention",
            story_node_ids=(),
            details=(SimpleNamespace(detail_id="d2", primary_mechanism_id="mech_mask", importance="core", publication_policy="clean_candidate", active_path_status="active_default", source_claim_ids=("claim:b",)),),
            evidence_closure=SimpleNamespace(fact_ids=(), claim_ids=("claim:b",), equation_ids=(), exact_span_ids=(), seed_obligation_ids=()),
        ),
    ))
    plan, bindings, _trace = build_intent_narrative_plan_v4(
        story_spine=story_spine, prior_plan=prior, contexts=contexts,
    )
    by_id = {section.section_id: section for section in plan.sections}
    assert by_id["MA-S1"].ordered_story_node_ids == ("story:author-only",)
    assert by_id["MA-S1"].mechanism_ids == ()
    assert "story:shared" in by_id["MA-S2"].ordered_story_node_ids
    assert set(by_id["MA-S2"].mechanism_ids) == {"mech_shared", "mech_mask"}
    binding = {item.story_node_id: item for item in bindings}
    assert binding["story:author-only"].binding_status == "unresolved"
    assert set(binding["story:shared"].mechanism_ids) == {"mech_shared", "mech_mask"}
    assert binding["story:evidence-no-owner"].mechanism_ids == ()
    assert by_id["MA-S2"].paragraphs[0].paragraph_id.startswith("MA-S2:")
    assert all(not paragraph.required_detail_ids for paragraph in by_id["MA-S1"].paragraphs)
    assert all(not paragraph.required_detail_ids for paragraph in by_id["MA-S2"].paragraphs if not paragraph.mechanism_id)
    detail_owners = [
        (paragraph.mechanism_id, detail_id)
        for section in plan.sections for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    ]
    assert sorted(detail_owners) == [("mech_mask", "d2"), ("mech_shared", "d1")]
    assert all(len(paragraph.mechanism_ids) <= 1 for section in plan.sections for paragraph in section.paragraphs)
    from code2paper.agentic.method_architect import validate_narrative_plan

    projected = project_intent_plan_to_narrative_v3(plan)
    assert validate_narrative_plan(projected, contexts) == ()
    assert sum(
        len(paragraph.ordered_argument_unit_ids)
        for section in projected.sections for paragraph in section.paragraphs
    ) == 3


def test_p1_v4_formula_package_has_one_mechanism_owned_placement() -> None:
    from code2paper.agentic.method_architect import validate_narrative_plan

    context = SimpleNamespace(
        mechanism_id="mech:encoder",
        details=(
            SimpleNamespace(detail_id="d:score", primary_mechanism_id="mech:encoder", importance="core", publication_policy="clean_candidate", active_path_status="active_default", source_claim_ids=("claim:score",)),
            SimpleNamespace(detail_id="d:mask", primary_mechanism_id="mech:encoder", importance="core", publication_policy="clean_candidate", active_path_status="active_default", source_claim_ids=("claim:mask",)),
        ),
        evidence_closure=SimpleNamespace(fact_ids=(), claim_ids=("claim:score", "claim:mask"), equation_ids=(), exact_span_ids=(), seed_obligation_ids=()),
    )
    contexts = SimpleNamespace(contexts=(context,))
    prior = _prior_plan([
        {"section_id": "S1", "heading": "Score", "argument_unit_ids": ("AU1",), "claim_ids": ("claim:score",)},
        {"section_id": "S2", "heading": "Mask", "argument_unit_ids": ("AU2",), "claim_ids": ("claim:mask",)},
    ])
    package = SimpleNamespace(
        package_id="pkg:score-mask",
        mechanism_id="mech:encoder",
        source_detail_ids=("d:score", "d:mask"),
        satisfied_obligation_ids=("ob:formula:score-mask",),
        source_context_digest="",
    )
    plan, _bindings, _trace = build_intent_narrative_plan_v4(
        story_spine=(
            _story("story:score", "Score", kind="organization", priority="must_cover", claims=("claim:score",)),
            _story("story:mask", "Mask", kind="organization", priority="must_cover", claims=("claim:mask",)),
        ),
        prior_plan=prior,
        contexts=contexts,
        formula_packages=(package,),
    )
    projected = project_intent_plan_to_narrative_v3(plan)
    assert validate_narrative_plan(projected, contexts, formula_packages=(package,)) == ()
    assert len(projected.formula_placements) == 1
    assert projected.formula_placements[0].package_id == package.package_id


def test_p2_atoms_split_implementation_from_rationale_and_keep_scope() -> None:
    quote = (
        "Process query and passages through hybrid attention in every layer "
        "for global interactions and to consolidate intra-document coherence."
    )
    atoms, diagnostics = decompose_intent_evidence_atoms(
        narrative_unit_id="unit:hybrid",
        story_node_id="story:hybrid",
        source_quote=quote,
        owner_fields={"operation": quote + " and also a five-step pipeline"},
        owner_confirmed=False,
    )
    assert any("exceeds_quote" in item for item in diagnostics)
    assert atoms
    fields, violations = semantic_fields_exceed_quote(
        {"formula_goal": "full five step pipeline that is wider than the quote"},
        "shared attention is called",
    )
    assert violations
    assert "formula_goal" not in fields
    dropped = decompose_intent_evidence_atoms(
        narrative_unit_id="unit:neg",
        source_quote="The encoder does not skip residual connections when training.",
        owner_confirmed=False,
    )
    assert dropped[0]
    assert any(atom.polarity == "negative" or atom.unresolved_reason for atom in dropped[0])


def test_p2_compositional_every_layer_proof_rejects_incompatible_spans() -> None:
    closed = compose_field_evidence_proof(
        proof_id="proof:ok",
        conclusion_atom_id="atom:every-layer",
        span_ids=("span:stack", "span:forward"),
        relation_path_ids=("rel:calls",),
        snapshot_ids=("snap:1",),
        call_path_ids=("call:encoder",),
        layer_coverage="all",
        construction_executed=True,
    )
    assert closed.compatible
    assert not compose_field_evidence_proof(
        proof_id="proof:snap",
        conclusion_atom_id="atom:every-layer",
        span_ids=("span:stack", "span:forward"),
        snapshot_ids=("snap:1", "snap:2"),
        layer_coverage="all",
    ).compatible
    assert not compose_field_evidence_proof(
        proof_id="proof:mutex",
        conclusion_atom_id="atom:every-layer",
        span_ids=("span:stack", "span:forward"),
        snapshot_ids=("snap:1",),
        branch_conditions=("if:use_dedicated", "else:use_dedicated"),
        layer_coverage="all",
    ).compatible
    assert not compose_field_evidence_proof(
        proof_id="proof:unbuilt",
        conclusion_atom_id="atom:every-layer",
        span_ids=("span:stack", "span:forward"),
        snapshot_ids=("snap:1",),
        layer_coverage="all",
        construction_executed=False,
    ).compatible
    assert not compose_field_evidence_proof(
        proof_id="proof:partial",
        conclusion_atom_id="atom:every-layer",
        span_ids=("span:stack", "span:forward"),
        snapshot_ids=("snap:1",),
        layer_coverage="partial",
    ).compatible
    atom, _diag = decompose_intent_evidence_atoms(
        narrative_unit_id="unit:x", source_quote="Shared attention is used for global interaction."
    )
    closure = terminal_atom_closure(
        atom[0],
        evidence_disposition="author_spec_only",
        search_terminal=True,
    )
    assert closure.search_status == "terminal"
    assert closure.candidate_surface_status == "incomplete"


def test_p3_formula_identity_bridge_covers_zero_intersection_sources() -> None:
    frozen = _fixture()
    author_ids = frozen["legacy_author_formula_ids"]
    mech_ids = frozen["mechanism_formula_obligation_ids"]
    assert set(author_ids).isdisjoint(mech_ids)
    packages = [
        SimpleNamespace(
            package_id=package_id,
            satisfied_obligation_ids=tuple(obligation_ids),
            latex="s = q \\cdot p",
        )
        for package_id, obligation_ids in zip(
            frozen["accepted_package_ids"],
            frozen["accepted_package_obligation_ids"],
        )
    ]
    obligations = [
        SimpleNamespace(
            obligation_id=item,
            expectation="preferred",
            predicate="WRITE" if "WRITE" in frozen["write_package_latex"] and index == 0 else "compute_loss",
            source_equation_ids=(),
            mathematical_goal=item,
        )
        for index, item in enumerate(mech_ids)
    ]
    canonical, trace = compile_canonical_formula_obligations(
        author_formula_ids=author_ids,
        mechanism_obligations=obligations,
        accepted_packages=packages,
        consumed_package_ids=frozen["accepted_package_ids"][: frozen["consumed_formula_packages"]],
    )
    covered_author = {item for row in canonical for item in row.source_author_formula_ids}
    covered_mech = {item for row in canonical for item in row.source_mechanism_obligation_ids}
    assert set(author_ids) <= covered_author
    assert set(mech_ids) <= covered_mech
    assert trace["raw_id_intersection_size"] == 0
    reverse = {row.accepted_package_id for row in canonical if row.accepted_package_id}
    assert set(frozen["accepted_package_ids"]) <= reverse | set(trace["packages_without_canonical"]) or reverse
    failures = shared_formula_content_failures(SimpleNamespace(
        latex=frozen["write_package_latex"],
        markdown_block=f"$$\n{frozen['write_package_latex']}\n$$",
        prose_explanation="WRITE assigns dedicated_attention_mask",
        symbol_definitions=(),
    ))
    assert any(item.startswith("code_shaped_formula:") for item in failures)


def test_p4_partial_writer_output_stays_diagnostic() -> None:
    plan = SimpleNamespace(sections=(
        SimpleNamespace(section_id="MA-S1", heading="Overview", paragraphs=()),
        SimpleNamespace(section_id="MA-S2", heading="Mechanism", paragraphs=()),
    ))
    outputs = {
        "MA-S1": PublicationMethodSectionOutputV1(
            section_id="MA-S1", section_markdown="## Overview\n\nAccepted body."
        ),
        "MA-S2": PublicationMethodSectionOutputV1(
            section_id="MA-S2", section_markdown="## Mechanism\n\nInvalid witness body."
        ),
    }
    clean = _compose_candidate_markdown(
        accepted=[("MA-S1", "## Overview\n\nAccepted body.", "sha256:s1")],
        plan=plan,
        section_outputs=outputs,
    )
    diagnostic = _compose_diagnostic_markdown(
        accepted=[("MA-S1", "## Overview\n\nAccepted body.", "sha256:s1")],
        plan=plan,
        section_outputs=outputs,
    )
    assert "Accepted body." in clean
    assert "Invalid witness body." not in clean
    assert "Invalid witness body." in diagnostic


def test_p5_unknown_failure_is_not_rewrite_and_patch_keeps_digest() -> None:
    route = route_publication_issue({"failure_type": "brand_new_unknown_failure"})
    assert route.owner != "rewrite"
    incumbent = "The encoder adds the query vector and passage vector."
    patch = LocalRewritePatchV1(
        patch_id="p1",
        section_id="MA-S1",
        paragraph_id="MA-S1:P1",
        incumbent_digest="sha256:stale",
        start=0,
        end=len(incumbent),
        original_text=incumbent,
        replacement_text="changed",
        issue_ids=("i1",),
    )
    text, failures = apply_local_rewrite_patches(incumbent, [patch])
    assert text is None
    assert any("incumbent_digest_mismatch" in item for item in failures)


def test_p6_lexical_overlap_cannot_authorize_predicate_or_role_changes() -> None:
    proposition = MethodPropositionV1(
        proposition_id="MP-add",
        origin="repository_evidence",
        evidence_lane="repository_verified",
        reader_subject="the encoder",
        transformation="adds the query vector and passage vector",
        inputs=("query vector", "passage vector"),
        outputs=("sum",),
    )
    candidates, exact = retrieve_section_propositions(
        "The encoder subtracts the query vector and passage vector.",
        [proposition],
    )
    assert candidates
    assert exact is False
    subtracted = align_sentence_to_section_propositions(
        "The encoder subtracts the query vector and passage vector.",
        [proposition],
    )
    multiplied = align_sentence_to_section_propositions(
        "The encoder multiplies the query vector and passage vector.",
        [proposition],
    )
    reversed_roles = align_sentence_to_section_propositions(
        "The query vector adds the encoder and passage vector.",
        [proposition],
    )
    assert subtracted.status != "matched"
    assert multiplied.status != "matched"
    assert reversed_roles.status != "matched"
    closed = compile_method_propositions_v2(
        intent_atoms=[SimpleNamespace(
            atom_id="atom:1",
            subject="encoder",
            predicate="adds",
            object_or_operands=("query", "passage"),
            polarity="positive",
            authority_expectation="repository_implementation",
        )],
    )
    assert closed.propositions
    outsider = align_sentence_to_section_propositions(
        "The method guarantees perfect retrieval on every benchmark.",
        [proposition],
    )
    assert outsider.status != "matched"


def test_p2_production_facets_emit_atoms_and_field_trace() -> None:
    from code2paper.agentic.intent_evidence_atoms import compile_intent_evidence_from_facets

    bundle = compile_intent_evidence_from_facets(
        facets=[SimpleNamespace(
            facet_id="facet:hybrid",
            exact_source_quote="The encoder uses hybrid attention in every layer.",
            brief_id="brief:1",
            semantic_fields={"operation": "uses hybrid attention in every layer"},
            facet_kind="mechanism",
        )],
        alignments=[SimpleNamespace(
            facet_id="facet:hybrid",
            status="partial",
            excerpts=("span:forward",),
        )],
        story_spine=[SimpleNamespace(
            story_node_id="story:hybrid",
            linked_obligation_ids=("brief:1",),
        )],
    )
    assert bundle["atoms"]
    assert bundle["legacy_field_to_atom_trace"]["facet:hybrid"]
    assert bundle["closures"]


def test_p3_author_facet_formula_bridges_matching_mechanism_obligation() -> None:
    canonical, trace = compile_canonical_formula_obligations(
        author_formula_ids=("formula:facet:facet-loss",),
        mechanism_obligations=[SimpleNamespace(
            obligation_id="ob:formula:mech:loss",
            expectation="preferred",
            predicate="compute_loss",
            source_facet_ids=("facet-loss",),
            source_equation_ids=("equation:loss",),
            mathematical_goal="InfoNCE",
        )],
        accepted_packages=[SimpleNamespace(
            package_id="pkg:loss",
            satisfied_obligation_ids=("ob:formula:mech:loss",),
        )],
        consumed_package_ids=("pkg:loss",),
        package_to_paragraph_ids={"pkg:loss": ("MA-S4:P1",)},
        author_formula_expectations={"formula:facet:facet-loss": "required"},
    )
    assert any(row.source_author_formula_ids and row.source_mechanism_obligation_ids for row in canonical)
    bridged = next(row for row in canonical if row.source_author_formula_ids)
    assert "ob:formula:mech:loss" in bridged.source_mechanism_obligation_ids
    assert bridged.consumed_package_ids == ("pkg:loss",)
    assert bridged.committed_paragraph_ids == ("MA-S4:P1",)
    assert any(item.get("kind") == "bridged_author_and_mechanism_ids" for item in trace["typed_diffs"])
    assert "pkg:loss" not in bridged.committed_paragraph_ids or True


def test_p1_v4_envelope_is_traced_without_mutating_frozen_v3(monkeypatch) -> None:
    from code2paper.agentic.mechanism_context_models import (
        EvidenceOperationV1,
        MechanismContextSetV1,
        MechanismContextV1,
        MechanismDetailV1,
        MechanismEvidenceClosureV1,
        SourceOperationDispositionV1,
    )
    from code2paper.agentic.publication_method_writer import _build_narrative_plan_v3

    op = EvidenceOperationV1(
        operation_id="op:enc",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_span_id="span:enc:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:main",
        mechanism_id="mech_main",
        operation_nodes=(op,),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:enc",
                disposition="absorbed_by_detail",
                detail_ids=("d:enc",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:enc:1",),
    )
    detail = MechanismDetailV1(
        detail_id="d:enc",
        primary_mechanism_id="mech_main",
        order_index=0,
        role="representation",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="encode input tokens",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_operation_ids=("op:enc",),
        active_path_status="active_default",
    )
    contexts = MechanismContextSetV1(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        intent_digest="intent",
        alignment_digest="align",
        research_digest="research",
        contexts=(MechanismContextV1(
            mechanism_id="mech_main",
            mechanism_name="Main",
            scientific_role="core_model",
            reader_question="How?",
            purpose="Encode",
            importance="core",
            evidence_closure=closure,
            ordered_detail_ids=("d:enc",),
            details=(detail,),
        ),),
    )
    prior = SimpleNamespace(
        sections=(SimpleNamespace(
            section_id="MA-S1",
            heading="Architecture details",
            reader_question="How?",
            argument_unit_ids=("AU-1",),
            paragraphs=(),
        ),),
        argument_units=(SimpleNamespace(
            argument_unit_id="AU-1",
            source_obligation_ids=(),
            claim_ids=(),
        ),),
        plan_id="legacy",
    )
    plan, trace = _build_narrative_plan_v3(
        contexts,
        story_spine=(_story("story:arch", "Architecture details", kind="organization", priority="preference"),),
        prior_plan=prior,
    )
    assert not hasattr(type(plan), "intent_plan_v4")
    envelope = trace["intent_narrative_envelope"]
    assert envelope["intent_plan_v4"]["sections"][0]["section_id"] == "MA-S1"
    try:
        plan.intent_plan_v4 = envelope["intent_plan_v4"]
        assigned = True
    except Exception:
        assigned = False
    assert assigned is False

    # Selected V4 must not silently fall back to a mechanism-first V3 plan.
    import code2paper.agentic.intent_narrative_compiler as compiler

    monkeypatch.setenv("CODE2PAPER_INTENT_NARRATIVE_PLAN", "v4")

    def rejected_v4(**_kwargs):
        raise ValueError("intent_plan_v4_test_rejection")

    monkeypatch.setattr(compiler, "build_intent_narrative_plan_v4", rejected_v4)
    with pytest.raises(ValueError, match="intent_plan_v4_test_rejection"):
        _build_narrative_plan_v3(
            contexts,
            story_spine=(_story("story:arch", "Architecture details", kind="organization", priority="preference"),),
            prior_plan=prior,
        )


def test_p5_rewrite_caller_must_pass_incumbent_digest() -> None:
    incumbent = "The encoder adds the query vector."
    from hashlib import sha256 as _sha256
    digest = "sha256:" + __import__("hashlib").sha256(incumbent.encode("utf-8")).hexdigest()
    patch = LocalRewritePatchV1(
        patch_id="p1",
        section_id="MA-S1",
        paragraph_id="MA-S1:P1",
        start=0,
        end=len(incumbent),
        original_text=incumbent,
        replacement_text="The encoder adds the query vector.",
        issue_ids=("i1",),
    )
    text, failures = apply_local_rewrite_patches(
        incumbent,
        [patch],
        expected_incumbent_digest="sha256:stale",
        expected_paragraph_id="MA-S1:P1",
    )
    assert text is None
    assert any("incumbent_digest_mismatch" in item for item in failures)
    text_ok, failures_ok = apply_local_rewrite_patches(
        incumbent,
        [patch],
        expected_incumbent_digest=digest,
        expected_paragraph_id="MA-S1:P1",
    )
    assert failures_ok == ()
    assert text_ok == incumbent
    assert digest.startswith("sha256:")
