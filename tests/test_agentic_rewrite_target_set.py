"""R8: the rewrite comparison denominator is the required target set.

The comparison digest must be stable under heading and section-order changes,
must not shrink when a candidate deletes a required target, and must keep a
per-target non-regression check on the intersection when a legal revision adds
targets.
"""

from __future__ import annotations

from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    MethodSectionPlanV2,
    SectionArgumentGraphV1,
)
from code2paper.agentic.method_proposition_models import MethodPropositionSetV1
from code2paper.agentic.publication_method_writer import (
    _rewrite_required_target_rows,
    _rewrite_required_target_set,
    _rewrite_transaction_has_cluster_gain,
)


def _plan(
    *,
    heading: str,
    section_id: str = "MA-S1",
    proposition_ids: tuple[str, ...] = ("prop:one",),
    claim_ids: tuple[str, ...] = ("claim:one",),
) -> MethodSectionPlanV2:
    unit = MethodArgumentUnitV1(
        argument_unit_id="unit:one",
        section_role="core_method",
        research_question="How does the method work?",
        proposition_ids=proposition_ids,
        claim_ids=claim_ids,
        authority_lanes=("executable_hard",),
    )
    section = SectionArgumentGraphV1(
        section_id=section_id,
        heading=heading,
        reader_question="How does the method work?",
    )
    return MethodSectionPlanV2(
        plan_id="plan:r8",
        sections=(section,),
        argument_units=(unit,),
    )


def _propositions() -> MethodPropositionSetV1:
    return MethodPropositionSetV1(propositions=())


def test_target_set_digest_ignores_headings_and_section_order() -> None:
    first = _plan(heading="First heading")
    second = _plan(heading="Completely different heading")
    first_digest, first_ids, first_rows = _rewrite_required_target_set(
        _rewrite_required_target_rows(plan=first, propositions=_propositions())
    )
    second_digest, second_ids, second_rows = _rewrite_required_target_set(
        _rewrite_required_target_rows(plan=second, propositions=_propositions())
    )
    assert first_digest == second_digest
    assert first_ids == second_ids == ("claim:claim:one", "proposition:prop:one")
    assert first_rows == second_rows

    # The digest never equals the whole plan digest: identity is the target
    # set, not the plan document.
    assert first_digest != first.content_digest


def test_candidate_deleting_a_required_target_is_not_a_gain() -> None:
    incumbent = {
        "required_target_ids": ("claim:claim:one", "proposition:prop:one"),
        "target_failures": {"claim:claim:one": 1},
        "validation_status": "failed",
        "style_issue_count": 3,
    }
    candidate = {
        "required_target_ids": ("proposition:prop:one",),
        "target_failures": {},
        "validation_status": "failed",
        "style_issue_count": 1,
    }
    accepted, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, candidate, cluster_name="method_language_style"
    )
    assert accepted is False
    assert reason == "required_target_removed:claim:claim:one"


def test_added_target_keeps_intersection_non_regression() -> None:
    incumbent = {
        "required_target_ids": ("proposition:prop:one",),
        "target_failures": {},
        "validation_status": "failed",
        "style_issue_count": 2,
    }
    # A legal revision adds a target; the old target must not regress.
    regression = {
        "required_target_ids": ("proposition:prop:one", "proposition:prop:two"),
        "target_failures": {"proposition:prop:one": 1},
        "validation_status": "failed",
        "style_issue_count": 1,
    }
    accepted, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, regression, cluster_name="method_language_style"
    )
    assert accepted is False
    assert reason == "required_target_regressed:proposition:prop:one"

    improved = {
        "required_target_ids": ("proposition:prop:one", "proposition:prop:two"),
        "target_failures": {},
        "validation_status": "failed",
        "style_issue_count": 1,
    }
    accepted_ok, reason_ok = _rewrite_transaction_has_cluster_gain(
        incumbent, improved, cluster_name="method_language_style"
    )
    assert accepted_ok is True, reason_ok

def test_same_target_contract_change_is_not_a_gain() -> None:
    """R8 correction: qualifier/polarity/authority changes are compared."""

    def _row(**overrides) -> dict:
        row = {
            "target_kind": "claim",
            "target_id": "claim:one",
            "argument_unit_id": "unit:one",
            "required_qualifiers": ("only on scoped inputs",),
            "polarity": "positive",
            "authority_lanes": ("executable_hard",),
        }
        row.update(overrides)
        return row

    def _snapshot(rows, *, style: int) -> dict:
        return {
            "required_target_ids": ("claim:claim:one",),
            "required_target_rows": rows,
            "target_failures": {},
            "validation_status": "failed",
            "style_issue_count": style,
        }

    incumbent = _snapshot((_row(),), style=2)
    for weakened in (
        _snapshot((_row(required_qualifiers=()),), style=1),
        _snapshot((_row(polarity="negative"),), style=1),
        _snapshot((_row(authority_lanes=("author_intent",)),), style=1),
    ):
        accepted, reason = _rewrite_transaction_has_cluster_gain(
            incumbent, weakened, cluster_name="method_language_style"
        )
        assert accepted is False
        assert reason.startswith("required_target_contract_changed:claim:claim:one")

    # A pure style gain that keeps the target contract is still accepted.
    accepted_ok, reason_ok = _rewrite_transaction_has_cluster_gain(
        incumbent, _snapshot((_row(),), style=1), cluster_name="method_language_style"
    )
    assert accepted_ok is True, reason_ok


def test_formula_obligations_are_part_of_the_denominator() -> None:
    """R8 correction: paragraph/section formula obligations are compared."""

    from code2paper.agentic.method_architect import (
        NarrativeParagraphPlanV3,
        NarrativePlanV3,
        NarrativeSectionPlanV3,
        NarrativeUnitV1,
    )

    plan = _plan(heading="Heading")
    section = plan.sections[0].model_copy(update={
        "formula_obligation_ids": ("ob:loss",),
    })
    plan = plan.model_copy(update={"sections": (section,)})
    narrative = NarrativePlanV3(
        plan_id="plan:narrative",
        sections=(NarrativeSectionPlanV3(
            section_id="MA-S1",
            heading="Heading",
            mechanism_ids=("mech:one",),
            paragraphs=(NarrativeParagraphPlanV3(
                paragraph_id="MA-S1_p1",
                section_id="MA-S1",
                role="formal_objective",
                mechanism_id="mech:one",
                formula_obligation_ids=("ob:loss",),
            ),),
        ),),
        narrative_units=(NarrativeUnitV1(
            unit_id="unit_1",
            section_id="MA-S1",
            mechanism_context_ids=("mech:one",),
            rhetorical_role="core_model",
            reader_question="How?",
            paragraph_ids=("MA-S1_p1",),
            required_detail_ids=(),
            optional_detail_ids=(),
            formula_obligation_ids=("ob:loss",),
            suggested_depth="standard",
        ),),
    )
    _digest, ids, rows = _rewrite_required_target_set(
        _rewrite_required_target_rows(
            plan=plan,
            propositions=_propositions(),
            narrative_plan=narrative,
        )
    )
    assert "formula_obligation:ob:loss" in ids
    assert any(
        row["target_kind"] == "formula_obligation"
        and row.get("paragraph_id") == "MA-S1_p1"
        for row in rows
    )

    incumbent = {
        "required_target_ids": ids,
        "required_target_rows": rows,
        "target_failures": {},
        "validation_status": "failed",
        "style_issue_count": 2,
    }
    dropped = {
        "required_target_ids": tuple(
            value for value in ids if value != "formula_obligation:ob:loss"
        ),
        "required_target_rows": tuple(
            row for row in rows if row["target_kind"] != "formula_obligation"
        ),
        "target_failures": {},
        "validation_status": "failed",
        "style_issue_count": 1,
    }
    accepted, reason = _rewrite_transaction_has_cluster_gain(
        incumbent, dropped, cluster_name="method_language_style"
    )
    assert accepted is False
    assert reason == "required_target_removed:formula_obligation:ob:loss"
