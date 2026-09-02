"""WP3 Slice 3B: per-obligation formula truth projection."""

from __future__ import annotations

from code2paper.agentic.formalization_agent import (
    build_formula_obligation_truths,
    section_result_from_packages,
    SectionFormulaPackageV1,
)


def test_formula_obligation_rendered_when_package_binds_equation() -> None:
    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Present the section loss.",
        latex="L = -pos + \\log\\sum exp",
        prose_explanation="Loss combines negative similarity and log-sum-exp.",
        symbol_definitions=(("L", "scalar loss"),),
        authority_status="code_verified",
        bound_fact_ids=("fact:loss",),
        bound_equation_ids=("equation:loss",),
    )
    truths = build_formula_obligation_truths(
        section_id="MA-S1",
        obligation_ids=("formula:equation:loss",),
        packages=(package,),
        disposition=None,
        formula_not_applicable=False,
    )
    assert len(truths) == 1
    assert truths[0].outcome == "rendered"
    assert truths[0].package_id == "fp:MA-S1:1"


def test_formula_obligation_unresolved_without_package() -> None:
    truths = build_formula_obligation_truths(
        section_id="MA-S1",
        obligation_ids=("formula:equation:loss",),
        packages=(),
        disposition=None,
        formula_not_applicable=False,
    )
    assert len(truths) == 1
    assert truths[0].outcome == "unresolved"
    assert truths[0].review_question


def test_synthetic_not_applicable_obligation_has_not_applicable_terminal_state() -> None:
    truths = build_formula_obligation_truths(
        section_id="MA-S1",
        obligation_ids=("formula:section:MA-S1:none",),
        packages=(),
        disposition=None,
        formula_not_applicable=True,
    )

    assert truths[0].outcome == "not_applicable"
    assert truths[0].terminal_disposition == "not_applicable"
    assert truths[0].expectation == "none"


def test_section_result_carries_obligation_truths() -> None:
    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Present the section loss.",
        latex="L = x + y",
        prose_explanation="Combined terms.",
        symbol_definitions=(),
        authority_status="code_verified",
        bound_fact_ids=("fact:1",),
        bound_equation_ids=("equation:core",),
    )
    result = section_result_from_packages(
        section_id="MA-S1",
        packages=(package,),
        obligation_ids=("formula:equation:core",),
    )
    assert result.obligation_truths
    assert result.obligation_truths[0].outcome == "rendered"


def test_unmatched_formula_obligation_stays_unresolved_when_other_package_exists() -> None:
    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Present the section loss.",
        latex="L = x + y",
        prose_explanation="Combined terms.",
        symbol_definitions=(),
        authority_status="code_verified",
        bound_fact_ids=("fact:1",),
        bound_equation_ids=("equation:core",),
    )
    truths = build_formula_obligation_truths(
        section_id="MA-S1",
        obligation_ids=("formula:equation:core", "formula:equation:other"),
        packages=(package,),
        disposition=None,
        formula_not_applicable=False,
    )
    by_id = {item.obligation_id: item for item in truths}
    assert by_id["formula:equation:core"].outcome == "rendered"
    assert by_id["formula:equation:other"].outcome == "unresolved"


def test_unresolved_formula_becomes_formula_slot_not_limitation() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.publication_method_writer import _mechanism_section_payload

    graph = SimpleNamespace(
        section_id="MA-S1",
        reader_question="How is loss computed?",
        primary_concept_keys=("CK-LOSS",),
        supporting_concept_keys=(),
        required_dataflow_relation_ids=(),
        formula_obligation_ids=("formula:equation:loss",),
        formula_not_applicable=False,
        open_slots=(),
    )
    payload = _mechanism_section_payload(
        graph=graph,
        writer_view=None,
        formula_packages=(),
        formula_obligations=(
            {
                "obligation_id": "formula:equation:loss",
                "outcome": "unresolved",
                "review_question": "Which evidence binds the loss?",
            },
        ),
    )
    kinds = [slot["slot_kind"] for slot in payload["caveated_open_slots"]]
    assert "missing_formula_obligation" in kinds
    assert all(slot.get("authority_lane") != "limitations_or_mismatch" for slot in payload["caveated_open_slots"])
    assert "formula" in payload["chain_contract"]


def test_formalization_route_rejects_package_for_other_obligation() -> None:
    from types import SimpleNamespace

    from code2paper.agentic.formalization_agent import (
        FormalizationSectionResultV1,
        resolve_formalization_route_artifact,
    )

    package = SectionFormulaPackageV1(
        package_id="fp:MA-S1:1",
        section_id="MA-S1",
        purpose="Present the section loss.",
        latex="L = x + y",
        prose_explanation="Combined terms.",
        symbol_definitions=(),
        authority_status="code_verified",
        bound_fact_ids=("fact:1",),
        bound_equation_ids=("equation:core",),
    )
    result = FormalizationSectionResultV1(
        section_id="MA-S1",
        packages=(package,),
        obligation_truths=build_formula_obligation_truths(
            section_id="MA-S1",
            obligation_ids=("formula:equation:core", "formula:equation:other"),
            packages=(package,),
            disposition=None,
            formula_not_applicable=False,
        ),
    )
    request = SimpleNamespace(
        request_id="request:formula-other",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        candidate_symbols_or_terms=(),
        target_formula_obligation_ids=("formula:equation:other",),
    )
    assert resolve_formalization_route_artifact(
        request, section_results=(result,),
    ) is None
    matched = SimpleNamespace(
        request_id="request:formula-core",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        candidate_symbols_or_terms=(),
        target_formula_obligation_ids=("formula:equation:core",),
    )
    artifact = resolve_formalization_route_artifact(
        matched, section_results=(result,),
    )
    assert artifact is not None
    assert artifact.validated is True


def test_writer_visible_packages_exclude_non_accepted() -> None:
    from code2paper.agentic.publication_method_writer import (
        _writer_visible_formula_packages,
    )

    accepted = SectionFormulaPackageV1(
        package_id="fp:MA-S1:ok",
        section_id="MA-S1",
        purpose="Present the section loss.",
        latex="L = -pos + \\log\\sum exp",
        prose_explanation="Loss combines negative similarity and log-sum-exp.",
        symbol_definitions=(),
        authority_status="code_verified",
        bound_fact_ids=("fact:loss",),
        bound_equation_ids=("equation:loss",),
    )
    mismatch = SectionFormulaPackageV1(
        package_id="fp:MA-S1:bad",
        section_id="MA-S1",
        purpose="Unverified expression.",
        latex="L = invented",
        prose_explanation="Not bound to code.",
        symbol_definitions=(),
        authority_status="paper_code_mismatch",
        bound_fact_ids=(),
        bound_equation_ids=(),
    )
    visible = _writer_visible_formula_packages(
        type("Result", (), {"packages": (accepted, mismatch)})()
    )
    assert len(visible) == 1
    assert visible[0]["latex"] == accepted.latex
