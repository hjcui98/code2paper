"""v34-like Candidate freeze: plan identity, empty pub slots, formula consume, voice."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from code2paper.agentic.callback_semantic_contract import (
    evaluate_authoring_structural_exit,
)
from code2paper.agentic.method_architect import (
    _preserve_incumbent_method_unit_surface,
    _refresh_incumbent_method_unit_surface,
)
from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    MethodSectionPlanV2,
    MethodUnitV2,
    ParagraphWitnessTargetV1,
    SectionArgumentGraphV1,
    SectionParagraphPlanV1,
)
from code2paper.agentic.publication_method_writer import _collapse_duplicate_section_h2
from code2paper.agentic.publication_transaction_contract import (
    required_targets_from_plan_row,
)
from code2paper.agentic.research_derived_authoring import (
    DerivationRecordV1,
    _candidate_surface_mode,
)
from code2paper.authoring.writer_skill import PublicationMethodWriterSkillV1
from tests.test_agentic_replay_execution_record import _load_script


def test_empty_publication_slots_are_not_promoted_from_ordered_support() -> None:
    row = {
        "required_publication_slot_ids": [],
        "ordered_semantic_slot_ids": [
            "slot:fact-O-COMPONENT-01",
            "slot:support-only",
        ],
        "support_slot_ids": ["slot:support-only"],
        "required_facet_ids": ["facet:1"],
        "formula_obligation_ids": [],
    }
    required = required_targets_from_plan_row(row)
    assert required["slot"] == ()
    assert required["facet"] == ("facet:1",)


def test_omitted_empty_publication_list_does_not_fall_back_when_split() -> None:
    row = {
        "ordered_semantic_slot_ids": ["slot:support-only"],
        "support_slot_ids": ["slot:support-only"],
        "required_field_candidate_ids": [],
    }
    assert required_targets_from_plan_row(row)["slot"] == ()


def test_legacy_row_without_publication_field_uses_ordered_slots() -> None:
    row = {"ordered_semantic_slot_ids": ["slot:transformation"]}
    assert required_targets_from_plan_row(row)["slot"] == ("slot:transformation",)


def test_callback_restore_deletes_files_created_after_snapshot(tmp_path: Path) -> None:
    module = _load_script()
    fresh = tmp_path / "fresh"
    authoring = fresh / "artifacts" / "06_authoring"
    authoring.mkdir(parents=True)
    (authoring / "assessments.json").write_bytes(b"seven-unit-assessments\n")
    snapshot = module._capture_authoring_transaction_snapshot(fresh)
    (authoring / "method_section_plan_v2.json").write_bytes(b"six-unit-callback-plan\n")
    (authoring / "assessments.json").write_bytes(b"mutated-assessments\n")

    module._restore_authoring_transaction_snapshot(fresh, snapshot)

    assert not (authoring / "method_section_plan_v2.json").exists()
    assert (authoring / "assessments.json").read_bytes() == b"seven-unit-assessments\n"


def test_reuse_persist_writes_rehashed_plan_to_authoring_lane(tmp_path: Path) -> None:
    module = _load_script()
    fresh = tmp_path / "fresh"
    artifacts = fresh / "artifacts"
    artifacts.mkdir(parents=True)
    graph = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Overview",
        reader_question="How?",
        argument_unit_ids=("u1",),
        paragraphs=(SectionParagraphPlanV1(
            paragraph_id="MA-S1:P1",
            argument_unit_ids=("u1",),
            required_publication_slot_ids=(),
            ordered_semantic_slot_ids=("slot:support",),
            support_slot_ids=("slot:support",),
        ),),
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="u1",
        section_role="mechanism",
        research_question="How?",
        claim_ids=(),
        authority_lanes=("executable_hard",),
    )
    plan = MethodSectionPlanV2(
        plan_id="method-plan:d6cd55a33bce6025c2286b14",
        method_name="toy",
        sections=(graph,),
        argument_units=(unit,),
        method_units=(MethodUnitV2(
            method_unit_id="MU-1",
            section_id="MA-S1",
            reader_question="How?",
            purpose="explain",
            author_statement="The encoder is intended to mix context.",
            paragraph_ids=("MA-S1:P1",),
            argument_unit_ids=("u1",),
        ),),
    )
    raw = '{"plan_id": "%s", "stale": true}\n' % plan.plan_id
    (artifacts / "method_section_plan_v2.json").write_text(
        plan.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    (artifacts / "method_argument_briefs_v1.json").write_text(raw, encoding="utf-8")

    module._persist_reused_method_unit_surface(fresh)

    authoring_plan = artifacts / "06_authoring" / "method_section_plan_v2.json"
    loaded = MethodSectionPlanV2.model_validate_json(
        authoring_plan.read_text(encoding="utf-8")
    )
    artifact_loaded = MethodSectionPlanV2.model_validate_json(
        (artifacts / "method_section_plan_v2.json").read_text(encoding="utf-8")
    )
    assert loaded.plan_id == plan.plan_id
    assert loaded.content_digest == artifact_loaded.content_digest
    assert loaded.method_units[0].paragraph_ids == ("MA-S1:P1",)
    assert loaded.sections[0].paragraphs[0].required_publication_slot_ids == ()
    assert (artifacts / "06_authoring" / "method_argument_briefs_v1.json").is_file()


def test_preserve_incumbent_method_units_keeps_paragraph_contracts() -> None:
    frozen_paragraph = SectionParagraphPlanV1(
        paragraph_id="MA-S3:P1",
        argument_unit_ids=("u3",),
        required_publication_slot_ids=(),
        ordered_semantic_slot_ids=("slot:support",),
        support_slot_ids=("slot:support",),
        formula_obligation_ids=("formula:1",),
    )
    prior = SimpleNamespace(
        method_units=(MethodUnitV2(
            method_unit_id="MU-S3",
            section_id="MA-S3",
            reader_question="How is attention mixed?",
            purpose="hybrid attention",
            author_statement="Hybrid attention is intended to mix token and graph context.",
            paragraph_ids=("MA-S3:P1",),
        ),),
        sections=(SectionArgumentGraphV1(
            section_id="MA-S3",
            heading="Attention",
            reader_question="How is attention mixed?",
            argument_unit_ids=("u3",),
            paragraphs=(frozen_paragraph,),
        ),),
    )
    regrouped = SectionArgumentGraphV1(
        section_id="MA-S3",
        heading="Attention",
        reader_question="How is attention mixed?",
        argument_unit_ids=("u3",),
        paragraphs=(
            SectionParagraphPlanV1(
                paragraph_id="MA-S3:P1",
                argument_unit_ids=("u3",),
                required_publication_slot_ids=("slot:support",),
                ordered_semantic_slot_ids=("slot:support",),
            ),
            SectionParagraphPlanV1(
                paragraph_id="MA-S3:P2",
                argument_unit_ids=("u3",),
                required_publication_slot_ids=("slot:other",),
                ordered_semantic_slot_ids=("slot:other",),
            ),
        ),
    )
    method_units, sections, trace = _preserve_incumbent_method_unit_surface(
        prior_plan=prior,
        rebuilt_sections=[regrouped],
    )
    assert trace["preserved_existing_method_units"] is True
    assert len(method_units) == 1
    assert len(sections) == 1
    assert len(sections[0].paragraphs) == 1
    assert sections[0].paragraphs[0].required_publication_slot_ids == ()
    assert sections[0].paragraphs[0].formula_obligation_ids == ("formula:1",)


def test_refresh_incumbent_method_units_rebuilds_reader_surface() -> None:
    prior_unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S3:unit-1",
        section_role="mechanism",
        research_question="How is the mechanism organized?",
        claim_ids=(),
        authority_lanes=("author_attested",),
    )
    prior = SimpleNamespace(
        method_units=(MethodUnitV2(
            method_unit_id="method-unit:MA-S3:old",
            section_id="MA-S3",
            reader_question="How is the mechanism organized?",
            purpose="old mechanism surface",
            author_statement="The mechanism combines two stages.",
            facet_ids=("facet:mechanism",),
            paragraph_ids=("paragraph:MA-S3:old",),
            argument_unit_ids=("MA-S3:unit-1",),
        ),),
        sections=(SectionArgumentGraphV1(
            section_id="MA-S3",
            heading="Mechanism",
            reader_question="How is the mechanism organized?",
            argument_unit_ids=("MA-S3:unit-1",),
            paragraphs=(SectionParagraphPlanV1(
                paragraph_id="paragraph:MA-S3:old",
                argument_unit_ids=("MA-S3:unit-1",),
                required_facet_ids=("facet:mechanism",),
            ),),
        ),),
        argument_units=(prior_unit,),
    )
    rebuilt = MethodUnitV2(
        method_unit_id="method-unit:MA-S3:fresh",
        section_id="MA-S3",
        reader_question="How is the mechanism organized?",
        purpose="reader rationale before mechanism",
        author_statement="The rationale is to avoid a redundant relation-extraction stage.",
        facet_ids=("facet:rationale",),
        paragraph_ids=("paragraph:MA-S3:fresh",),
        argument_unit_ids=("MA-S3:unit-1",),
    )
    rebuilt_graph = SectionArgumentGraphV1(
        section_id="MA-S3",
        heading="Mechanism",
        reader_question="How is the mechanism organized?",
        argument_unit_ids=("MA-S3:unit-1",),
        paragraphs=(SectionParagraphPlanV1(
            paragraph_id="paragraph:MA-S3:fresh",
            argument_unit_ids=("MA-S3:unit-1",),
            required_facet_ids=("facet:rationale",),
        ),),
    )
    method_units, sections, trace = _refresh_incumbent_method_unit_surface(
        prior_plan=prior,
        rebuilt_method_units=(rebuilt,),
        rebuilt_sections=[rebuilt_graph],
        units=(prior_unit,),
    )
    assert method_units[0].method_unit_id == "method-unit:MA-S3:old"
    assert method_units[0].facet_ids == ("facet:rationale",)
    assert sections[0].paragraphs[0].required_facet_ids == ("facet:rationale",)
    assert trace["fallback_to_prior_surface"] is False
    assert trace["reader_surface_mode"] == "rebuilt"
    assert trace["preserved_surface_count"] == 0


def test_structural_exit_consumes_unique_inline_latex_without_rendered_row() -> None:
    latex = r"y = Wx + b"
    block = f"$$\n{latex}\n$$"
    plan = {
        "content_digest": "sha256:plan",
        "sections": [{
            "section_id": "MA-S3",
            "paragraphs": [{
                "paragraph_id": "MA-S3:P1",
                "required_publication_slot_ids": [],
                "ordered_semantic_slot_ids": ["slot:support"],
                "formula_obligation_ids": ["formula:1"],
            }],
        }],
    }
    assessment = {
        "content_digest": "sha256:assessment",
        "plan_digest": "sha256:plan",
        "assessments": [{
            "section_id": "MA-S3",
            "paragraph_id": "MA-S3:P1",
            "valid": False,
            "witnessed_by_kind": {"formula": []},
            "missing_by_kind": {"slot": ["slot:missing"]},
        }],
    }
    trace = {
        "content_digest": "sha256:trace",
        "transaction_assessment_digest": "sha256:assessment",
        "rows": [{
            "section_id": "MA-S3",
            "paragraph_id": "MA-S3:P1",
            "terminal_state": "rendered_invalid",
            "accepted_formula_package_ids": ["package:1"],
            "field_bindings": [],
        }],
    }
    writer = {"plan_digest": "sha256:plan", "final_text_digest": "sha256:candidate"}
    formalization = {
        "sections": [{
            "section_id": "MA-S3",
            "packages": [{
                "package_id": "package:1",
                "latex": latex,
                "markdown_block": block,
                "review_status": "accepted",
                "authority_status": "code_verified",
                "formula_lane": "repository_derived",
            }],
            "obligation_truths": [{
                "obligation_id": "formula:1",
                "expectation": "required",
                "outcome": "rendered",
                "package_id": "package:1",
            }],
        }],
    }
    decision = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload={"requests": []},
        formalization_payload=formalization,
        candidate_digest="sha256:candidate",
        candidate_markdown=f"## Attention\n\nThe encoder uses\n\n{block}\n\nbefore scoring.\n",
    )
    assert decision.accepted_formula_packages == 1
    assert decision.consumed_formula_packages == 1
    assert not any(reason.startswith("formula_packages_unconsumed:") for reason in decision.reasons)


def test_structural_exit_does_not_consume_latex_without_display_math() -> None:
    latex = r"y = Wx + b"
    block = f"$$\n{latex}\n$$"
    plan = {
        "content_digest": "sha256:plan",
        "sections": [{
            "section_id": "MA-S3",
            "paragraphs": [{
                "paragraph_id": "MA-S3:P1",
                "required_publication_slot_ids": [],
                "ordered_semantic_slot_ids": ["slot:support"],
                "formula_obligation_ids": ["formula:1"],
            }],
        }],
    }
    assessment = {
        "content_digest": "sha256:assessment",
        "plan_digest": "sha256:plan",
        "assessments": [{
            "section_id": "MA-S3",
            "paragraph_id": "MA-S3:P1",
            "valid": False,
            "witnessed_by_kind": {"formula": []},
            "missing_by_kind": {"slot": ["slot:missing"]},
        }],
    }
    trace = {
        "content_digest": "sha256:trace",
        "transaction_assessment_digest": "sha256:assessment",
        "rows": [{
            "section_id": "MA-S3",
            "paragraph_id": "MA-S3:P1",
            "terminal_state": "rendered",
            "accepted_formula_package_ids": ["package:1"],
            "field_bindings": [],
        }],
    }
    writer = {"plan_digest": "sha256:plan", "final_text_digest": "sha256:candidate"}
    formalization = {
        "sections": [{
            "section_id": "MA-S3",
            "packages": [{
                "package_id": "package:1",
                "latex": latex,
                "markdown_block": block,
                "review_status": "accepted",
                "authority_status": "code_verified",
                "formula_lane": "repository_derived",
            }],
            "obligation_truths": [{
                "obligation_id": "formula:1",
                "expectation": "required",
                "outcome": "rendered",
                "package_id": "package:1",
            }],
        }],
    }
    decision = evaluate_authoring_structural_exit(
        plan_payload=plan,
        trace_payload=trace,
        assessment_payload=assessment,
        writer_payload=writer,
        callback_payload={"requests": []},
        formalization_payload=formalization,
        candidate_digest="sha256:candidate",
        candidate_markdown=f"## Attention\n\nThe encoder uses {latex} before scoring.\n",
    )
    assert decision.accepted_formula_packages == 1
    assert decision.consumed_formula_packages == 0
    assert any(reason.startswith("formula_packages_unconsumed:") for reason in decision.reasons)


def test_mismatch_without_contradiction_keeps_author_specification() -> None:
    record = DerivationRecordV1(
        derivation_id="drv:1",
        section_id="MA-S1",
        paragraph_id="MA-S1:P1",
        facet_id="facet:1",
        field_name="operation",
        semantic_atom="mix token and graph context",
        derivation_kind="author_intent_only",
        claim_strength="descriptive",
        authority_status="intent_code_mismatch",
        candidate_allowed=True,
    )
    assert _candidate_surface_mode(record) == "author_specification"


def test_candidate_skill_does_not_require_audit_mismatch_voice() -> None:
    skill = PublicationMethodWriterSkillV1()
    prompt = skill.system_prompt()
    joined = " ".join(skill.style_rules)
    assert "must describe the observed implementation" not in prompt
    assert "not yet been resolved" not in prompt
    assert "author-mechanism narrative" in prompt
    assert "observed implementation versus intended design" in joined
    example_bad = " ".join(item["bad"] for item in skill.examples)
    assert "observed implementation" in example_bad


def test_duplicate_section_h2_is_collapsed() -> None:
    markdown = "## Redesign\n\nThe encoder mixes context.\n\n## Redesign\n\n"
    collapsed = _collapse_duplicate_section_h2(markdown, expected_heading="Redesign")
    assert collapsed.count("## Redesign") == 1
    assert "The encoder mixes context." in collapsed


def test_unearned_repository_statement_becomes_author_specification() -> None:
    target = ParagraphWitnessTargetV1(
        target_id="facet-story",
        target_kind="facet",
        semantic_atom="evaluation suite for cross passage inference",
        paper_role="mechanism",
        authority_lane="author_attested",
    )
    assert target.surface_mode == "author_specification"


def test_executable_anchor_keeps_repository_statement() -> None:
    target = ParagraphWitnessTargetV1(
        target_id="facet-code",
        target_kind="facet",
        semantic_atom="retriever supplies passage embeddings",
        paper_role="mechanism",
        authority_lane="executable_hard",
        allowed_anchor_ids=("span:src/encode.py:10:20",),
    )
    assert target.surface_mode == "repository_statement"


def test_preserve_incumbent_keeps_argument_units_for_plan_validate() -> None:
    prior_unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S1:unit-1",
        section_role="motivation",
        research_question="Why?",
        claim_ids=(),
        authority_lanes=("author_attested",),
    )
    prior_paragraph = SectionParagraphPlanV1(
        paragraph_id="paragraph:MA-S1:method-unit-1",
        argument_unit_ids=("MA-S1:unit-1",),
        required_publication_slot_ids=(),
        ordered_semantic_slot_ids=(),
    )
    extra_unit = MethodArgumentUnitV1(
        argument_unit_id="MA-S1:unit-2",
        section_role="motivation",
        research_question="Why else?",
        claim_ids=(),
        authority_lanes=("author_attested",),
    )
    prior = MethodSectionPlanV2(
        plan_id="method-plan:frozen",
        method_name="toy",
        sections=(SectionArgumentGraphV1(
            section_id="MA-S1",
            heading="Motivation",
            reader_question="Why?",
            argument_unit_ids=("MA-S1:unit-1", "MA-S1:unit-2"),
            paragraphs=(prior_paragraph,),
        ),),
        argument_units=(prior_unit, extra_unit),
        method_units=(MethodUnitV2(
            method_unit_id="method-unit:MA-S1:1",
            section_id="MA-S1",
            reader_question="Why?",
            purpose="state the evaluation challenge",
            author_statement="The benchmark is intended to test cross-passage inference.",
            paragraph_ids=("paragraph:MA-S1:method-unit-1",),
            argument_unit_ids=("MA-S1:unit-1", "MA-S1:unit-2"),
        ),),
    )
    regrouped = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Motivation",
        reader_question="Why?",
        argument_unit_ids=("MA-S1:unit",),
        paragraphs=(SectionParagraphPlanV1(
            paragraph_id="paragraph:MA-S1:method-unit-1",
            argument_unit_ids=("MA-S1:unit",),
        ),),
    )
    method_units, sections, trace = _preserve_incumbent_method_unit_surface(
        prior_plan=prior,
        rebuilt_sections=[regrouped],
    )
    plan = MethodSectionPlanV2(
        plan_id=prior.plan_id,
        method_name=prior.method_name,
        sections=tuple(sections),
        argument_units=tuple(prior.argument_units),
        method_units=method_units,
    )
    assert trace["preserved_existing_method_units"] is True
    assert sections[0].argument_unit_ids == ("MA-S1:unit-1", "MA-S1:unit-2")
    assert plan.method_units[0].argument_unit_ids == ("MA-S1:unit-1", "MA-S1:unit-2")
