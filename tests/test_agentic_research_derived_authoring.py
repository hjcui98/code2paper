from __future__ import annotations

import json
from pathlib import Path

import pytest

from code2paper.agentic.formalization_agent import (
    MethodFormulaObligationV2,
    SectionFormulaPackageV1,
    validate_section_formula_package,
)
from code2paper.agentic.method_argument_brief_models import (
    PublicationFieldCandidateV1,
)
from code2paper.agentic.research_derived_authoring import (
    build_publication_authoring_packets,
    build_research_derived_callback_requests,
    build_research_mechanism_dossiers,
    compile_derivation_records,
    merge_derivations_into_field_candidates,
    validate_candidate_authority,
    write_research_derived_artifacts,
)


def _plan(*, field_id: str = "field:mechanism") -> dict:
    return {
        "sections": [{
            "section_id": "section:method",
            "reader_question": "How is the representation transformed?",
            "paragraphs": [{
                "paragraph_id": "paragraph:mechanism",
                "paragraph_role": "step_sequence",
                "required_facet_ids": ["facet:mechanism"],
                "required_field_candidate_ids": [field_id],
                "ordered_semantic_slot_ids": ["slot:operation"],
                "required_edge_ids": ["edge:flow"],
                "formula_obligation_ids": ["formula:mechanism"],
            }],
        }],
    }


def _candidate(*, field_id: str = "field:mechanism") -> PublicationFieldCandidateV1:
    return PublicationFieldCandidateV1(
        candidate_id=field_id,
        facet_id="facet:mechanism",
        field_name="operation",
        semantic_atom="normalizes representations",
        polarity="positive",
        bound_fact_ids=("fact:normalize",),
        bound_span_ids=("span:normalize",),
        exact_excerpts=("normalize",),
        ownership_roles=("target_core",),
        render_policy="optional",
    )


def _graph() -> dict:
    return {
        "nodes": [
            {
                "node_id": "node:entry",
                "symbol_id": "entry",
                "operation_id": "load_input",
                "predicate": "LOAD",
                "source_span_id": "span:entry",
            },
            {
                "node_id": "node:normalize",
                "symbol_id": "normalize",
                "operation_id": "normalize",
                "predicate": "NORMALIZE",
                "source_span_id": "span:normalize",
            },
            {
                "node_id": "node:score",
                "symbol_id": "score",
                "operation_id": "score",
                "predicate": "COMPUTE",
                "source_span_id": "span:score",
            },
            {
                "node_id": "node:evaluation",
                "symbol_id": "evaluation",
                "operation_id": "evaluation",
                "predicate": "COMPARE",
                "source_span_id": "span:evaluation",
            },
        ],
        "relations": [
            {
                "relation_id": "rel:load-normalize",
                "kind": "NEXT_CONTROL",
                "source_node_id": "node:entry",
                "target_node_id": "node:normalize",
                "source_symbol_id": "entry",
                "target_symbol_id": "normalize",
            },
            {
                "relation_id": "rel:normalize-score",
                "kind": "CALLS",
                "source_node_id": "node:normalize",
                "target_node_id": "node:score",
                "source_symbol_id": "normalize",
                "target_symbol_id": "score",
            },
            {
                "relation_id": "rel:normalize-data",
                "kind": "DATA_DEPENDS_ON",
                "source_node_id": "node:score",
                "target_node_id": "node:normalize",
                "source_symbol_id": "score",
                "target_symbol_id": "normalize",
            },
            {
                "relation_id": "rel:score-evaluation",
                "kind": "NEXT_CONTROL",
                "source_node_id": "node:score",
                "target_node_id": "node:evaluation",
                "source_symbol_id": "score",
                "target_symbol_id": "evaluation",
            },
        ],
        "unresolved_relations": [{
            "relation_id": "rel:dynamic",
            "source_node_id": "node:normalize",
            "source_symbol_id": "normalize",
            "reason": "dynamic dispatch",
        }],
        "content_digest": "sha256:graph-source",
    }


def _scope() -> dict:
    return {
        "target_entry_symbol_ids": ["entry"],
        "target_core_symbol_ids": ["entry", "normalize", "score"],
        "target_dependency_symbol_ids": [],
        "comparand_symbol_ids": [],
        "evaluation_symbol_ids": ["evaluation"],
        "configuration_symbol_ids": [],
        "unknown_symbol_ids": [],
        "content_digest": "sha256:scope-source",
    }


def test_dossier_is_connected_scoped_and_records_source_provenance() -> None:
    dossiers = build_research_mechanism_dossiers(
        plan=_plan(),
        facets=[{
            "facet_id": "facet:mechanism",
            "clause_id": "clause:mechanism",
            "exact_source_quote": "normalizes representations",
            "semantic_fields": {"operation": "normalizes representations"},
        }],
        field_candidates=[_candidate()],
        behavior_graph=_graph(),
        facts={"facts": [{
            "fact_id": "fact:normalize",
            "subject": "normalize",
            "direct_span_ids": ["span:normalize"],
            "relation_span_ids": [],
            "claim_ids": ["claim:normalize"],
        }], "content_digest": "sha256:facts-source"},
        claims={"claims": [{
            "claim_id": "claim:normalize",
            "fact_ids": ["fact:normalize"],
            "span_ids": ["span:normalize"],
        }], "content_digest": "sha256:claims-source"},
        equations={"equations": [{
            "equation_id": "equation:mechanism",
            "fact_ids": ["fact:normalize"],
            "span_ids": ["span:normalize"],
        }], "content_digest": "sha256:equations-source"},
        configurations={"claims": [{
            "configuration_id": "configuration:normalize",
            "definition_span_ids": ["span:normalize"],
            "active": False,
            "state": "resolved",
            "conditions": [],
        }], "content_digest": "sha256:config-source"},
        implementation_scope=_scope(),
    )

    assert len(dossiers) == 1
    dossier = dossiers[0]
    assert dossier.ordered_operation_node_ids
    assert "node:evaluation" not in dossier.ordered_operation_node_ids
    assert dossier.call_path_relation_ids == ("rel:normalize-score",)
    assert dossier.data_flow_relation_ids == ("rel:normalize-data",)
    assert dossier.unresolved_relations == ("rel:dynamic",)
    assert dossier.default_activation == "inactive"
    assert dossier.configuration_bindings[0]["configuration_id"] == "configuration:normalize"
    assert dossier.source_digests["behavior_graph"] == "sha256:graph-source"
    assert dossier.source_digests["facts"] == "sha256:facts-source"


def test_unresolved_dossier_emits_one_bounded_owner_callback() -> None:
    dossiers = build_research_mechanism_dossiers(
        plan=_plan(),
        facets=[{
            "facet_id": "facet:mechanism",
            "semantic_fields": {"operation": "normalizes representations"},
        }],
        field_candidates=[_candidate()],
        behavior_graph={
            "nodes": [{
                "node_id": "node:unrelated",
                "symbol_id": "unrelated",
                "source_span_id": "span:unrelated",
            }],
            "relations": [],
            "content_digest": "sha256:graph-source",
        },
        facts={"facts": [{
            "fact_id": "fact:normalize",
            "subject": "normalize",
            "direct_span_ids": ["span:normalize"],
        }], "content_digest": "sha256:facts-source"},
    )
    requests = build_research_derived_callback_requests(
        plan=_plan(), dossiers=dossiers,
    )
    assert len(requests) == 1
    request = requests[0]
    assert request["missing_rhetorical_move"] == "algorithm_or_data_flow"
    assert request["required_authority_lane"] == "executable_hard"
    assert request["status"] == "open"
    assert request["target_story_node_ids"] == ()
    assert "missing_connected_behavior_subgraph" in request["missing_parts"]
    assert request["exact_question"].startswith("Which bounded repository trace")


def test_derivation_keeps_repository_and_author_intent_lanes_separate() -> None:
    dossier = build_research_mechanism_dossiers(
        plan=_plan(field_id="field:author"),
        facets=[{
            "facet_id": "facet:mechanism",
            "clause_id": "clause:mechanism",
            "exact_source_quote": "the intended transformation",
            "semantic_fields": {"operation": "the intended transformation"},
            "contradiction_ids": ["contradiction:1"],
        }],
        field_candidates=[PublicationFieldCandidateV1(
            candidate_id="field:author",
            facet_id="facet:mechanism",
            field_name="operation",
            semantic_atom="the intended transformation",
            exact_excerpts=("the intended transformation",),
            ownership_roles=("target_core",),
            render_policy="optional",
        )],
    )
    records = compile_derivation_records(
        dossiers=dossier,
        facets=[{
            "facet_id": "facet:mechanism",
            "semantic_fields": {"operation": "the intended transformation"},
            "exact_source_quote": "the intended transformation",
        }],
        alignments=[{
            "facet_id": "facet:mechanism",
            "status": "mismatch",
            "field_bindings": [{
                "field_name": "operation",
                "status": "mismatch",
            }],
        }],
    )

    assert len(records) == 1
    assert records[0].derivation_kind == "author_intent_only"
    assert records[0].authority_status == "intent_code_mismatch"
    assert records[0].verified_eligible is False
    merged = merge_derivations_into_field_candidates(
        candidates=[PublicationFieldCandidateV1(
            candidate_id="field:author",
            facet_id="facet:mechanism",
            field_name="operation",
            semantic_atom="the intended transformation",
            exact_excerpts=("the intended transformation",),
            ownership_roles=("target_core",),
            render_policy="optional",
        )],
        derivations=records,
    )
    assert merged[0].surface_mode == "mismatch_statement"
    assert merged[0].derivation_kind == "author_intent_only"


def test_candidate_authority_rejects_harness_vocabulary() -> None:
    validation = validate_candidate_authority(
        candidate_text="The audit callback is pending and repository evidence is unverified.",
        candidates=(),
        derivations=(),
    )
    assert validation.status == "error"
    assert validation.internal_audit_term_count >= 3


def test_v2_packet_keeps_formula_consumer_local_and_does_not_emit_witnesses() -> None:
    packets = build_publication_authoring_packets(
        plan=_plan(),
        candidates=[_candidate()],
        formula_packages_by_section={"section:method": [{
            "package_id": "package:mechanism",
            "consumer_paragraph_id": "paragraph:mechanism",
            "satisfied_obligation_ids": ["formula:mechanism"],
            "latex": "z = x",
        }]},
    )
    packet = packets["section:method"][0]
    assert packet.paragraph_id == "paragraph:mechanism"
    assert packet.formula_packages[0]["package_id"] == "package:mechanism"
    assert "witnesses" not in packet.model_dump(mode="json")


def test_v2_packet_is_the_only_new_writer_surface() -> None:
    from code2paper.llm.section_writer import (
        WriterSectionInput,
        _llm_visible_section_payload,
    )

    section = WriterSectionInput(
        section_id="section:method",
        heading="Mechanism",
        prompt_payload={
            "section_id": "section:method",
            "heading": "Mechanism",
            "authoring_packets_v2": [{
                "schema_version": "2.0",
                "section_id": "section:method",
                "paragraph_id": "paragraph:mechanism",
                "rhetorical_goal": "Explain the transformation.",
                "ordered_targets": [{
                    "target_id": "field:mechanism",
                    "target_kind": "field_candidate",
                    "semantic_atom": "normalizes representations",
                    "surface_mode": "repository_statement",
                }],
                "dossier_summary": {
                    "operation_atoms": [{
                        "operation_id": "normalize",
                        "predicate": "NORMALIZE",
                    }],
                    "exact_span_ids": ["span:secret"],
                    "fact_ids": ["fact:secret"],
                },
                "formula_packages": [{
                    "package_id": "package:mechanism",
                    "latex": "z = x",
                    "markdown_block": "$$z=x$$",
                    "bound_fact_ids": ["fact:secret"],
                }],
                "closed_target_ids": ["field:mechanism"],
            }],
            "argument_units": [{"claim_ids": ["claim:secret"]}],
            "validation_constraints": {"claims": [{"claim_id": "claim:secret"}]},
        },
        publication_mode=True,
    )

    visible = _llm_visible_section_payload(section)
    assert set(visible) == {
        "section_id", "heading", "authoring_packets_v2",
    }
    packet = visible["authoring_packets_v2"][0]
    assert "exact_span_ids" not in packet["dossier_summary"]
    assert "fact_ids" not in packet["dossier_summary"]
    assert "bound_fact_ids" not in packet["formula_packages"][0]
    assert "argument_units" not in visible


def test_one_formula_package_can_close_multiple_obligations_for_one_consumer() -> None:
    obligations = (
        MethodFormulaObligationV2(
            obligation_id="formula:a",
            section_id="section:method",
            consumer_paragraph_id="paragraph:mechanism",
            facet_ids=("facet:a",),
            mathematical_goal="shared transform",
        ),
        MethodFormulaObligationV2(
            obligation_id="formula:b",
            section_id="section:method",
            consumer_paragraph_id="paragraph:mechanism",
            facet_ids=("facet:b",),
            mathematical_goal="shared transform",
        ),
    )
    package = SectionFormulaPackageV1(
        package_id="package:shared",
        section_id="section:method",
        satisfied_obligation_ids=("formula:a", "formula:b"),
        consumer_paragraph_id="paragraph:mechanism",
        purpose="shared transform",
        latex="z = x",
        prose_explanation="The transform maps the input to the output.",
        authority_status="partial",
        assumptions=("The shared transform is treated as a paper-level abstraction.",),
        bound_facet_ids=("facet:a", "facet:b"),
    )
    assert validate_section_formula_package(
        package,
        equations=type("Equations", (), {"equations": ()})(),
        facts=type("Facts", (), {"facts": ()})(),
        formula_obligations=obligations,
        require_consumer=True,
    ) == []

    wrong_consumer = package.model_copy(update={
        "consumer_paragraph_id": "paragraph:other",
    })
    assert "formula_package_consumer_paragraph_mismatch" in validate_section_formula_package(
        wrong_consumer,
        equations=type("Equations", (), {"equations": ()})(),
        facts=type("Facts", (), {"facts": ()})(),
        formula_obligations=obligations,
        require_consumer=True,
    )


def test_research_artifacts_are_content_addressed(tmp_path: Path) -> None:
    dossiers = build_research_mechanism_dossiers(
        plan=_plan(),
        facets=[{
            "facet_id": "facet:mechanism",
            "clause_id": "clause:mechanism",
            "exact_source_quote": "normalizes representations",
            "semantic_fields": {"operation": "normalizes representations"},
        }],
        field_candidates=[_candidate()],
    )
    paths = write_research_derived_artifacts(
        str(tmp_path), dossiers=dossiers, derivations=(),
    )
    dossier_payload = json.loads(
        Path(paths["research_mechanism_dossiers_v1"]).read_text(encoding="utf-8")
    )
    assert dossier_payload["content_digest"].startswith("sha256:")
    assert dossier_payload["items"][0]["content_digest"].startswith("sha256:")
    derivation_payload = json.loads(
        Path(paths["derivation_records_v1"]).read_text(encoding="utf-8")
    )
    assert derivation_payload["source_dossier_digest"] == dossier_payload["content_digest"]


def test_strict_research_rejects_an_empty_mechanism_dossier() -> None:
    bare_candidate = _candidate().model_copy(update={
        "bound_fact_ids": (),
        "bound_span_ids": (),
        "exact_excerpts": (),
        "semantic_atom": "",
    })
    with pytest.raises(ValueError, match="research_dossier_empty_mechanism_unit"):
        build_research_mechanism_dossiers(
            plan=_plan(),
            facets=[{
                "facet_id": "facet:mechanism",
                "clause_id": "clause:mechanism",
                "exact_source_quote": "",
                "semantic_fields": {},
            }],
            field_candidates=[bare_candidate],
            facet_alignments=[{
                "facet_id": "facet:mechanism",
                "status": "unresolved",
                "field_bindings": [],
            }],
            require_nonempty=True,
        )


def test_exact_alignment_span_recovers_omitted_fact_id() -> None:
    candidate = _candidate().model_copy(update={
        "bound_fact_ids": (),
        "bound_span_ids": (),
        "exact_excerpts": (),
    })
    dossiers = build_research_mechanism_dossiers(
        plan=_plan(),
        facets=[{
            "facet_id": "facet:mechanism",
            "clause_id": "clause:mechanism",
            "exact_source_quote": "normalizes representations",
            "semantic_fields": {"operation": "normalizes representations"},
            "required": True,
        }],
        field_candidates=[candidate],
        facet_alignments=[{
            "facet_id": "facet:mechanism",
            "status": "partial",
            "bound_fact_ids": [],
            "bound_span_ids": ["span:normalize"],
            "exact_excerpts": [{
                "span_id": "span:normalize",
                "exact_excerpt": "normalized = normalize(input)",
            }],
        }],
        behavior_graph=_graph(),
        facts={"facts": [{
            "fact_id": "fact:normalize",
            "subject": "normalize",
            "predicate": "normalizes",
            "object": ["input", "result=normalized"],
            "conditions": [],
            "scope": "normalize",
            "direct_span_ids": ["span:normalize"],
            "relation_span_ids": [],
            "relation_evidence_ids": [],
            "validation_status": "supported",
        }]},
        require_nonempty=True,
    )

    assert len(dossiers) == 1
    assert dossiers[0].evidence_readiness == "code_ready"
    assert dossiers[0].fact_ids == ("fact:normalize",)
    assert dossiers[0].formalizable_signatures[0]["result"] == "normalized"


def test_argument_unit_bindings_seed_formula_only_paragraph_dossier() -> None:
    """A replan-split paragraph may carry evidence only on its argument unit."""

    dossiers = build_research_mechanism_dossiers(
        plan={
            "sections": [{
                "section_id": "section:method",
                "paragraphs": [{
                    "paragraph_id": "paragraph:formula",
                    "paragraph_role": "formula",
                    "argument_unit_ids": ["unit:mechanism"],
                    "required_facet_ids": [],
                    "required_field_candidate_ids": [],
                    "formula_obligation_ids": ["formula:section:derivation"],
                }],
            }],
            "argument_units": [{
                "argument_unit_id": "unit:mechanism",
                "claim_ids": ["claim:normalize"],
                "equation_ids": ["equation:normalize"],
                "source_artifact_ids": ["span:normalize"],
            }],
        },
        facets=(),
        field_candidates=(),
        claims={"claims": [{
            "claim_id": "claim:normalize",
            "fact_ids": ["fact:normalize"],
            "span_ids": ["span:normalize"],
        }]},
        equations={"equations": [{
            "equation_id": "equation:normalize",
            "fact_ids": ["fact:normalize"],
            "span_ids": ["span:normalize"],
        }]},
        facts={"facts": [{
            "fact_id": "fact:normalize",
            "subject": "normalize",
            "predicate": "normalizes",
            "object": ["input", "result=normalized"],
            "conditions": [],
            "scope": "normalize",
            "direct_span_ids": ["span:normalize"],
            "relation_span_ids": [],
            "relation_evidence_ids": [],
            "validation_status": "supported",
        }]},
        require_nonempty=True,
    )

    assert len(dossiers) == 1
    dossier = dossiers[0]
    assert dossier.evidence_readiness == "code_ready"
    assert dossier.fact_ids == ("fact:normalize",)
    assert dossier.exact_span_ids == ("span:normalize",)
    assert dossier.formalizable_signatures[0]["result"] == "normalized"


def test_exact_method_unit_prevents_coarse_argument_unit_fact_inheritance() -> None:
    """A split paragraph consumes its MethodUnit, not every unit fact."""

    facts = {
        "facts": [
            {
                "fact_id": "fact:method",
                "subject": "normalize",
                "predicate": "normalizes",
                "object": ["input", "result=normalized"],
                "conditions": [],
                "scope": "normalize",
                "direct_span_ids": ["span:method"],
                "validation_status": "supported",
            },
            {
                "fact_id": "fact:coarse",
                "subject": "unrelated_stage",
                "predicate": "returns",
                "object": ["unrelated"],
                "conditions": [],
                "scope": "unrelated_stage",
                "direct_span_ids": ["span:coarse"],
                "validation_status": "supported",
            },
        ]
    }
    dossiers = build_research_mechanism_dossiers(
        plan={
            "sections": [{
                "section_id": "section:method",
                "paragraphs": [{
                    "paragraph_id": "paragraph:method",
                    "paragraph_role": "step_sequence",
                    "argument_unit_ids": ["unit:coarse"],
                    "required_facet_ids": ["facet:mechanism"],
                    "required_field_candidate_ids": ["field:mechanism"],
                    "formula_obligation_ids": [],
                }],
            }],
            "argument_units": [{
                "argument_unit_id": "unit:coarse",
                "fact_ids": ["fact:coarse"],
                "claim_ids": [],
                "equation_ids": [],
            }],
            "method_units": [{
                "method_unit_id": "method-unit:method",
                "paragraph_ids": ["paragraph:method"],
                "fact_ids": ["fact:method"],
                "claim_ids": [],
                "equation_ids": [],
                "evidence_spans": ["span:method"],
            }],
        },
        facets=[{
            "facet_id": "facet:mechanism",
            "semantic_fields": {"operation": "normalizes representations"},
        }],
        field_candidates=[_candidate().model_copy(update={
            "bound_fact_ids": ("fact:method",),
            "bound_span_ids": ("span:method",),
            "exact_excerpts": ("normalize",),
        })],
        facts=facts,
        require_nonempty=True,
    )

    assert len(dossiers) == 1
    assert dossiers[0].evidence_readiness == "code_ready"
    assert "fact:method" in dossiers[0].fact_ids
    assert "fact:coarse" not in dossiers[0].fact_ids


def test_unbound_alignment_cannot_compile_all_facts_by_default() -> None:
    candidate = _candidate().model_copy(update={
        "bound_fact_ids": (),
        "bound_span_ids": (),
        "exact_excerpts": (),
    })
    dossiers = build_research_mechanism_dossiers(
        plan=_plan(),
        facets=[{
            "facet_id": "facet:mechanism",
            "clause_id": "clause:mechanism",
            "exact_source_quote": "the intended transformation",
            "semantic_fields": {"operation": "the intended transformation"},
        }],
        field_candidates=[candidate],
        facet_alignments=[{
            "facet_id": "facet:mechanism",
            "status": "unresolved",
            "field_bindings": [],
        }],
        facts={"facts": [{
            "fact_id": "fact:normalize",
            "subject": "normalize",
            "predicate": "normalizes",
            "object": ["input", "result=normalized"],
            "scope": "normalize",
            "direct_span_ids": ["span:normalize"],
            "validation_status": "supported",
        }]},
    )

    assert len(dossiers) == 1
    assert dossiers[0].fact_ids == ()
    assert dossiers[0].evidence_readiness == "intent_ready"
    assert "facet_alignment_unresolved:facet:mechanism" in dossiers[0].readiness_failures


def test_method_unit_rejects_an_empty_mechanism_shell() -> None:
    from code2paper.agentic.method_argument_models import MethodUnitV2

    with pytest.raises(ValueError, match="empty mechanism shell"):
        MethodUnitV2(
            method_unit_id="method-unit:empty",
            section_id="section:method",
            reader_question="How does the method work?",
            purpose="Explain the method.",
        )


def test_callee_body_expansion_in_dossier_with_locality_ranking() -> None:
    plan = _plan()
    graph = {
        "nodes": [
            {
                "node_id": "node:graph_search",
                "symbol_id": "graph_search",
                "operation_id": "search",
                "predicate": "CALL",
                "source_span_id": "span:graph_search",
            },
            {
                "node_id": "node:calculate_entity_scores",
                "symbol_id": "calculate_entity_scores",
                "operation_id": "calculate",
                "predicate": "COMPUTE",
                "source_span_id": "span:calculate_entity_scores",
            },
        ],
        "relations": [
            {
                "relation_id": "rel:search-scores",
                "kind": "CALLS",
                "source_node_id": "node:graph_search",
                "target_node_id": "node:calculate_entity_scores",
                "source_symbol_id": "graph_search",
                "target_symbol_id": "calculate_entity_scores",
            },
        ],
        "unresolved_relations": [],
        "content_digest": "sha256:graph-source",
    }
    evidence_packets = {
        "packets": [{
            "packet_id": "packet:test",
            "scope": "test",
            "anchor_span_ids": ["span:graph_search", "span:calculate_entity_scores", "span:helper"],
            "relation_span_ids": [],
            "semantic_span_ids": [],
            "spans": [
                {
                    "span_id": "span:graph_search",
                    "path": "linear_rag.py",
                    "symbol": "graph_search",
                    "exact_excerpt": "scores = self.calculate_entity_scores(query)",
                    "file_digest": "sha256:f1",
                    "role": "anchor",
                },
                {
                    "span_id": "span:calculate_entity_scores",
                    "path": "linear_rag.py",
                    "symbol": "calculate_entity_scores",
                    "exact_excerpt": "def calculate_entity_scores():\n    # initialize\n    # similarity\n    # propagate\n    # threshold\n    return scores",
                    "file_digest": "sha256:f2",
                    "role": "semantic",
                },
                {
                    "span_id": "span:helper",
                    "path": "linear_rag.py",
                    "symbol": "helper",
                    "exact_excerpt": "logger.info('filter ORDINAL entities')\nreturn filtered",
                    "file_digest": "sha256:f3",
                    "role": "relation",
                },
            ],
        }],
    }
    candidate = _candidate().model_copy(update={
        "bound_fact_ids": ("fact:search",),
        "bound_span_ids": ("span:graph_search",),
        "exact_excerpts": ("scores = self.calculate_entity_scores(query)",),
    })
    facts = {
        "facts": [{
            "fact_id": "fact:search",
            "subject": "graph_search",
            "predicate": "CALLS",
            "object": ["calculate_entity_scores"],
            "scope": "graph_search",
            "direct_span_ids": ["span:graph_search"],
            "validation_status": "supported",
            "claim_ids": ["claim:search"],
        }],
        "content_digest": "sha256:facts",
    }
    claims = {
        "claims": [{
            "claim_id": "claim:search",
            "fact_ids": ["fact:search"],
            "span_ids": ["span:graph_search"],
        }],
        "content_digest": "sha256:claims",
    }
    scope = {
        "target_entry_symbol_ids": ["graph_search"],
        "target_core_symbol_ids": ["graph_search", "calculate_entity_scores"],
        "target_dependency_symbol_ids": [],
        "comparand_symbol_ids": [],
        "evaluation_symbol_ids": [],
        "configuration_symbol_ids": [],
        "unknown_symbol_ids": [],
        "content_digest": "sha256:scope",
    }
    dossiers = build_research_mechanism_dossiers(
        plan=plan,
        field_candidates=[candidate],
        behavior_graph=graph,
        evidence_packets=evidence_packets,
        facts=facts,
        claims=claims,
        implementation_scope=scope,
    )
    assert len(dossiers) == 1
    dossier = dossiers[0]
    # Callee span must be in exact_span_ids
    assert "span:calculate_entity_scores" in dossier.exact_span_ids
    # Callee body must be in exact_excerpts
    assert any("propagate" in ex for ex in dossier.exact_excerpts)
    # The callsite excerpt is primary, followed by callee body, while logging/helper is demoted
    excerpts = list(dossier.exact_excerpts)
    callsite_idx = next(i for i, ex in enumerate(excerpts) if "calculate_entity_scores(query)" in ex)
    body_idx = next(i for i, ex in enumerate(excerpts) if "propagate" in ex)
    assert callsite_idx < body_idx
    if any("ORDINAL" in ex for ex in excerpts):
        helper_idx = next(i for i, ex in enumerate(excerpts) if "ORDINAL" in ex)
        assert body_idx < helper_idx


def test_callee_expansion_recursive_cycle_prevention() -> None:
    plan = _plan()
    # Cyclic call graph: A calls B, B calls A
    graph = {
        "nodes": [
            {
                "node_id": "node:func_a",
                "symbol_id": "func_a",
                "operation_id": "op_a",
                "predicate": "CALL",
                "source_span_id": "span:func_a",
            },
            {
                "node_id": "node:func_b",
                "symbol_id": "func_b",
                "operation_id": "op_b",
                "predicate": "CALL",
                "source_span_id": "span:func_b",
            },
        ],
        "relations": [
            {
                "relation_id": "rel:a-calls-b",
                "kind": "CALLS",
                "source_node_id": "node:func_a",
                "target_node_id": "node:func_b",
                "source_symbol_id": "func_a",
                "target_symbol_id": "func_b",
            },
            {
                "relation_id": "rel:b-calls-a",
                "kind": "CALLS",
                "source_node_id": "node:func_b",
                "target_node_id": "node:func_a",
                "source_symbol_id": "func_b",
                "target_symbol_id": "func_a",
            },
        ],
        "unresolved_relations": [],
        "content_digest": "sha256:graph-cyclic",
    }
    evidence_packets = {
        "packets": [{
            "packet_id": "packet:cycle",
            "scope": "cycle",
            "anchor_span_ids": ["span:func_a", "span:func_b"],
            "relation_span_ids": [],
            "semantic_span_ids": [],
            "spans": [
                {
                    "span_id": "span:func_a",
                    "path": "cycle.py",
                    "symbol": "func_a",
                    "exact_excerpt": "def func_a():\n    return func_b()",
                    "file_digest": "sha256:fa",
                    "role": "anchor",
                },
                {
                    "span_id": "span:func_b",
                    "path": "cycle.py",
                    "symbol": "func_b",
                    "exact_excerpt": "def func_b():\n    return func_a()",
                    "file_digest": "sha256:fb",
                    "role": "semantic",
                },
            ],
        }],
    }
    candidate = _candidate().model_copy(update={
        "bound_fact_ids": ("fact:func_a",),
        "bound_span_ids": ("span:func_a",),
        "exact_excerpts": ("def func_a():\n    return func_b()",),
    })
    facts = {
        "facts": [{
            "fact_id": "fact:func_a",
            "subject": "func_a",
            "predicate": "CALLS",
            "object": ["func_b"],
            "scope": "func_a",
            "direct_span_ids": ["span:func_a"],
            "validation_status": "supported",
            "claim_ids": ["claim:func_a"],
        }],
        "content_digest": "sha256:facts",
    }
    claims = {
        "claims": [{
            "claim_id": "claim:func_a",
            "fact_ids": ["fact:func_a"],
            "span_ids": ["span:func_a"],
        }],
        "content_digest": "sha256:claims",
    }
    scope = {
        "target_entry_symbol_ids": ["func_a"],
        "target_core_symbol_ids": ["func_a", "func_b"],
        "target_dependency_symbol_ids": [],
        "comparand_symbol_ids": [],
        "evaluation_symbol_ids": [],
        "configuration_symbol_ids": [],
        "unknown_symbol_ids": [],
        "content_digest": "sha256:scope",
    }
    # Building dossiers should terminate cleanly without infinite loop or unbounded expansion
    dossiers = build_research_mechanism_dossiers(
        plan=plan,
        field_candidates=[candidate],
        behavior_graph=graph,
        evidence_packets=evidence_packets,
        facts=facts,
        claims=claims,
        implementation_scope=scope,
    )
    assert len(dossiers) == 1
    dossier = dossiers[0]
    # Length of exact_excerpts must be small and bounded
    assert len(dossier.exact_excerpts) <= 3
