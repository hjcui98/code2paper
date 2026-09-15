from __future__ import annotations

import pytest
from code2paper.agentic.formalization_agent import (
    MechanismFormulaPackageV2,
)
from code2paper.agentic.mechanism_context_models import (
    DetailWitnessAtomV1,
    EvidenceOperationV1,
    MechanismContextSetV1,
    MechanismContextV1,
    MechanismDetailV1,
    MechanismEvidenceClosureV1,
    SourceOperationDispositionV1,
)
from code2paper.agentic.method_architect import (
    NARRATIVE_PARAGRAPH_ROLES,
    NarrativePlanV3,
    build_narrative_plan_v3,
    validate_narrative_plan,
)


def _make_context_set() -> MechanismContextSetV1:
    op1 = EvidenceOperationV1(
        operation_id="op:enc",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_span_id="span:enc:1",
        active_path_status="active_default",
    )
    op2 = EvidenceOperationV1(
        operation_id="op:loss",
        predicate="compute_loss",
        operands=("emb", "labels"),
        result="loss",
        source_span_id="span:loss:1",
        active_path_status="active_default",
    )
    closure = MechanismEvidenceClosureV1(
        closure_id="closure:main",
        mechanism_id="mech_main",
        operation_nodes=(op1, op2),
        operation_dispositions=(
            SourceOperationDispositionV1(
                operation_id="op:enc",
                disposition="absorbed_by_detail",
                detail_ids=("d:enc",),
            ),
            SourceOperationDispositionV1(
                operation_id="op:loss",
                disposition="absorbed_by_detail",
                detail_ids=("d:loss",),
            ),
        ),
        source_operation_terminal_coverage=1.0,
        exact_span_ids=("span:enc:1", "span:loss:1"),
    )
    d_enc = MechanismDetailV1(
        detail_id="d:enc",
        primary_mechanism_id="mech_main",
        order_index=0,
        role="representation",
        importance="core",
        claim_kind="specification",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="encode input tokens into embeddings",
        predicate="encode_input",
        operands=("tokens",),
        result="emb",
        source_operation_ids=("op:enc",),
        active_path_status="active_default",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:enc",
                atom_kind="operation",
                semantic_anchor="token encoding",
                source_operation_ids=("op:enc",),
            ),
        ),
    )
    d_loss = MechanismDetailV1(
        detail_id="d:loss",
        primary_mechanism_id="mech_main",
        order_index=1,
        role="training_objective",
        importance="core",
        claim_kind="formalization",
        evidence_authority="repository_verified",
        publication_policy="clean_candidate",
        semantic_atom="compute loss objective",
        predicate="compute_loss",
        operands=("emb", "labels"),
        result="loss",
        formalizable=True,
        source_operation_ids=("op:loss",),
        active_path_status="active_default",
        witness_atoms=(
            DetailWitnessAtomV1(
                atom_id="atom:d:loss",
                atom_kind="formal_relation",
                semantic_anchor="loss formula",
                source_operation_ids=("op:loss",),
            ),
        ),
    )
    ctx = MechanismContextV1(
        mechanism_id="mech_main",
        mechanism_name="Main Method Architecture",
        scientific_role="core_model",
        reader_question="How does the main model process data and train?",
        purpose="Complete end-to-end processing and optimization",
        importance="core",
        evidence_closure=closure,
        ordered_detail_ids=("d:enc", "d:loss"),
        details=(d_enc, d_loss),
    )
    return MechanismContextSetV1(
        repo_snapshot_id="repo:main",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:align",
        research_digest="sha256:research",
        contexts=(ctx,),
    )


def test_build_narrative_plan_v3_and_validation() -> None:
    context_set = _make_context_set()
    pkg = MechanismFormulaPackageV2(
        package_id="pkg:loss",
        mechanism_id="mech_main",
        source_detail_ids=("d:loss",),
        satisfied_obligation_ids=("ob:loss",),
        latex="loss = \\operatorname{compute_loss}(emb, labels)",
        prose_explanation="Computes loss.",
        symbol_definitions=(("emb", "embeddings"), ("labels", "ground truth")),
        evidence_authority="repository_verified",
        formula_lane="repository_derived",
        review_status="accepted",
        source_context_digest=context_set.contexts[0].source_context_digest,
    )

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        formula_packages=(pkg,),
    )
    assert isinstance(plan, NarrativePlanV3)
    assert len(plan.sections) == 1
    assert plan.sections[0].mechanism_ids == ("mech_main",)
    assert len(plan.sections[0].paragraphs) >= 2
    assert trace["sections_planned"] == 1
    assert trace["formula_placements_count"] == 1
    # §12.2: no proposal caller means no autonomous organization credit.
    assert trace["proposal_status"] == "not_requested"
    assert trace["proposal_failures"] == []

    # Validate the generated plan passes all gates
    failures = validate_narrative_plan(plan, context_set)
    assert failures == ()


def test_validate_narrative_plan_catches_violations() -> None:
    context_set = _make_context_set()
    plan, _ = build_narrative_plan_v3(contexts=context_set)

    # 1. Unknown mechanism ID failure
    bad_sec = plan.sections[0].model_copy(update={"mechanism_ids": ("unknown_mech",)})
    bad_plan = plan.model_copy(update={"sections": (bad_sec,)})
    failures = validate_narrative_plan(bad_plan, context_set)
    assert any("unknown_mechanism_id:unknown_mech" in f for f in failures)

    # 2. Unknown detail ID failure
    p0 = plan.sections[0].paragraphs[0]
    bad_p0 = p0.model_copy(update={"required_detail_ids": ("unknown_detail",)})
    bad_sec2 = plan.sections[0].model_copy(update={"paragraphs": (bad_p0, *plan.sections[0].paragraphs[1:])})
    bad_plan2 = plan.model_copy(update={"sections": (bad_sec2,)})
    failures2 = validate_narrative_plan(bad_plan2, context_set)
    assert any("unknown_detail_id:unknown_detail" in f for f in failures2)

    # 3. Missing core detail failure
    empty_p = [p.model_copy(update={"required_detail_ids": ()}) for p in plan.sections[0].paragraphs]
    bad_sec3 = plan.sections[0].model_copy(update={"paragraphs": tuple(empty_p)})
    bad_plan3 = plan.model_copy(update={"sections": (bad_sec3,)})
    failures3 = validate_narrative_plan(bad_plan3, context_set)
    assert any("missing_core_detail" in f for f in failures3)


def _two_context_set() -> MechanismContextSetV1:
    """Two mechanisms with disjoint core details and no source spans."""

    def _context(mechanism_id: str, detail_ids: tuple[str, ...]) -> MechanismContextV1:
        operations = tuple(
            EvidenceOperationV1(
                operation_id=f"op:{mechanism_id}:{index}",
                predicate="compute_step",
                operands=(f"input_{index}",),
                result=f"output_{index}",
                source_span_id="",
                active_path_status="active_default",
            )
            for index, _detail_id in enumerate(detail_ids)
        )
        details = tuple(
            MechanismDetailV1(
                detail_id=detail_id,
                primary_mechanism_id=mechanism_id,
                order_index=index,
                role="transformation" if index % 2 else "output",
                importance="core",
                claim_kind="implementation",
                evidence_authority="repository_verified",
                publication_policy="clean_candidate",
                semantic_atom=f"step {index}",
                predicate="compute_step",
                operands=(f"input_{index}",),
                result=f"output_{index}",
                active_path_status="active_default",
                source_operation_ids=(operations[index].operation_id,),
                witness_atoms=(DetailWitnessAtomV1(
                    atom_id=f"atom:{detail_id}",
                    atom_kind="operation",
                    semantic_anchor=f"step {index}",
                    source_operation_ids=(operations[index].operation_id,),
                ),),
            )
            for index, detail_id in enumerate(detail_ids)
        )
        closure = MechanismEvidenceClosureV1(
            closure_id=f"closure:{mechanism_id}",
            mechanism_id=mechanism_id,
            operation_nodes=operations,
            operation_dispositions=tuple(
                SourceOperationDispositionV1(
                    operation_id=operation.operation_id,
                    disposition="absorbed_by_detail",
                    detail_ids=(details[index].detail_id,),
                )
                for index, operation in enumerate(operations)
            ),
            source_operation_terminal_coverage=1.0,
        )
        return MechanismContextV1(
            mechanism_id=mechanism_id,
            mechanism_name=f"Mechanism {mechanism_id}",
            scientific_role="core_model",
            reader_question=f"How does {mechanism_id} work?",
            purpose="Explain the mechanism.",
            importance="core",
            evidence_closure=closure,
            ordered_detail_ids=tuple(d.detail_id for d in details),
            details=details,
        )

    return MechanismContextSetV1(
        repo_snapshot_id="repo:two",
        project_tree_hash="sha256:tree",
        intent_digest="sha256:intent",
        alignment_digest="sha256:align",
        research_digest="sha256:research",
        contexts=(
            _context("mech_alpha", ("d:a1", "d:a2", "d:a3")),
            _context("mech_beta", ("d:b1", "d:b2", "d:b3")),
        ),
    )


def test_multi_section_outline_places_every_mechanism_core_detail() -> None:
    """R7: a longer legacy outline must not drop the other mechanisms."""

    context_set = _two_context_set()
    base_plan, _ = build_narrative_plan_v3(contexts=context_set)
    prior_sections = tuple(
        section.model_copy(update={"section_id": f"MA-S{index + 1}"})
        for index, section in enumerate(base_plan.sections)
    ) + (
        base_plan.sections[0].model_copy(update={"section_id": "MA-S3"}),
        base_plan.sections[0].model_copy(update={"section_id": "MA-S4"}),
    )
    prior_plan = base_plan.model_copy(update={"sections": prior_sections})

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        prior_plan=prior_plan,
    )

    assert len(plan.sections) == len(prior_sections)
    assert trace["sections_planned"] == len(prior_sections)
    failures = validate_narrative_plan(plan, context_set)
    assert not [f for f in failures if f.startswith("missing_core_detail")]
    assert failures == ()

    placed = [
        detail_id
        for section in plan.sections
        for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    ]
    assert sorted(placed) == sorted({
        "d:a1", "d:a2", "d:a3", "d:b1", "d:b2", "d:b3",
    })

    # Section identity follows proven ownership, never position: a section
    # that declares beta must not carry alpha's details, and the heading that
    # names the declared owner must agree with the paragraph owners.
    prior_owner = {
        str(section.section_id): str(section.mechanism_ids[0])
        for section in prior_sections
    }
    for section in plan.sections:
        section_owner = prior_owner.get(str(section.section_id))
        if section_owner is None:
            continue
        assert section.mechanism_ids == (section_owner,)
        assert section_owner in str(section.heading)
        for paragraph in section.paragraphs:
            assert str(paragraph.mechanism_id) == section_owner
            assert all(
                detail_id.startswith("d:a") == section_owner.endswith("alpha")
                for detail_id in paragraph.required_detail_ids
            )

    # Every paragraph keeps exactly one mechanism owner, and each mechanism is
    # represented across the outline rather than only in the first section.
    owners = {
        str(paragraph.mechanism_id)
        for section in plan.sections
        for paragraph in section.paragraphs
    }
    assert owners == {"mech_alpha", "mech_beta"}
    unit_mechanisms = {
        mechanism_id
        for unit in plan.narrative_units
        for mechanism_id in unit.mechanism_context_ids
    }
    assert unit_mechanisms == {"mech_alpha", "mech_beta"}
    for unit in plan.narrative_units:
        assert len(unit.mechanism_context_ids) == len(
            set(unit.mechanism_context_ids)
        )

def test_reversed_outline_keeps_proven_owner_identity() -> None:
    """R7: outline order must not decide section content."""

    context_set = _two_context_set()
    base_plan, _ = build_narrative_plan_v3(contexts=context_set)
    base_by_owner = {
        str(section.mechanism_ids[0]): section for section in base_plan.sections
    }
    alpha_base = base_by_owner["mech_alpha"]
    beta_base = base_by_owner["mech_beta"]
    # The beta section comes first in the outline while alpha still owns two
    # sections; assignment must follow the proven owner, not the position.
    prior_sections = (
        beta_base.model_copy(update={"section_id": "MA-S1"}),
        alpha_base.model_copy(update={"section_id": "MA-S2"}),
        alpha_base.model_copy(update={"section_id": "MA-S3"}),
    )
    prior_plan = base_plan.model_copy(update={"sections": prior_sections})

    plan, _trace = build_narrative_plan_v3(
        contexts=context_set, prior_plan=prior_plan
    )
    failures = validate_narrative_plan(plan, context_set)
    assert failures == ()
    owners_by_section = {
        str(section.section_id): {
            str(paragraph.mechanism_id) for paragraph in section.paragraphs
        }
        for section in plan.sections
    }
    # MA-S1 now precedes the beta section in the outline but still owns beta.
    assert owners_by_section["MA-S1"] == {"mech_beta"}
    assert owners_by_section["MA-S2"] == {"mech_alpha"}
    assert owners_by_section["MA-S3"] == {"mech_alpha"}
    placed = sorted(
        detail_id
        for section in plan.sections
        for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    )
    assert placed == sorted({"d:a1", "d:a2", "d:a3", "d:b1", "d:b2", "d:b3"})


def test_ambiguous_prior_owner_blocks_instead_of_reassigning() -> None:
    """R7: an unproven prior section is never silently reassigned."""

    context_set = _two_context_set()
    base_plan, _ = build_narrative_plan_v3(contexts=context_set)
    alpha_section, beta_section = base_plan.sections
    conflicting = alpha_section.model_copy(update={
        "section_id": "MA-S1",
        "mechanism_ids": ("mech_alpha", "mech_beta"),
    })
    prior_sections = (
        conflicting,
        beta_section.model_copy(update={"section_id": "MA-S2"}),
        alpha_section.model_copy(update={"section_id": "MA-S3"}),
    )
    prior_plan = base_plan.model_copy(update={"sections": prior_sections})

    plan, trace = build_narrative_plan_v3(
        contexts=context_set, prior_plan=prior_plan
    )
    assert trace["section_identity_failures"] == [
        "prior_section_owner_unproven:MA-S1"
    ]
    # The ambiguous section is not reused with an invented owner.
    assert "MA-S1" not in {str(section.section_id) for section in plan.sections}
    assert all(
        len({str(paragraph.mechanism_id) for paragraph in section.paragraphs}) <= 1
        for section in plan.sections
    )
    assert all(
        str(section.mechanism_ids[0]) == str(paragraph.mechanism_id)
        for section in plan.sections
        for paragraph in section.paragraphs
    )
    # The proven owners still place every core detail exactly once.
    placed = sorted(
        detail_id
        for section in plan.sections
        for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    )
    assert placed == sorted({"d:a1", "d:a2", "d:a3", "d:b1", "d:b2", "d:b3"})

def test_unused_proposal_caller_is_recorded_as_not_accepted() -> None:
    """R7 §12.2: an unconsumed proposal never counts as accepted."""

    context_set = _two_context_set()
    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        proposal_caller=lambda *args, **kwargs: {},
    )
    assert trace["proposal_status"] == "not_accepted"
    # R7 correction: the rejection keeps its typed per-mechanism reason and the
    # legacy "not consumed" marker, so a caller can see both what was offered
    # and that nothing was applied.
    assert "narrative_proposal_not_consumed" in trace["proposal_failures"]
    assert any(
        failure.startswith("narrative_proposal_paragraphs_missing:")
        for failure in trace["proposal_failures"]
    )
    if trace["proposal_failures"].count("narrative_proposal_not_consumed") == 1:
        pass
    # The deterministic plan still passes every structural gate.
    assert validate_narrative_plan(plan, context_set) == ()


def _detail_ids_by_mechanism(context_set: MechanismContextSetV1):
    grouped: dict[str, list[str]] = {}
    for context in context_set.contexts:
        grouped[context.mechanism_id] = [
            detail.detail_id for detail in context.details
            if getattr(detail, "active_path_status", "unknown") in {
                "active_default", "active_selected", "conditional",
            }
        ]
    return grouped


def test_valid_narrative_organization_proposal_is_consumed() -> None:
    """R7: a closed-choice organization proposal is applied, not just noted."""

    context_set = _two_context_set()
    detail_ids = _detail_ids_by_mechanism(context_set)

    def _caller(mechanism_id, details, sections, roles, **kwargs):
        assert kwargs.get("kind") == "narrative_organization"
        assert set(details) == set(detail_ids[mechanism_id])
        assert set(roles) <= set(NARRATIVE_PARAGRAPH_ROLES)
        # One paragraph per detail: a legal partition with legal roles.
        return {
            "mechanism_id": mechanism_id,
            "paragraphs": [
                {"role": "core_transformations", "detail_ids": [detail_id]}
                for detail_id in details
            ],
        }

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        proposal_caller=_caller,
    )
    assert trace["proposal_status"] == "accepted", trace["proposal_failures"]
    assert trace["proposal_failures"] == []
    assert set(trace["proposal_accepted_mechanism_ids"]) == {"mech_alpha", "mech_beta"}
    for section in plan.sections:
        owner = str(section.mechanism_ids[0])
        placed = [
            detail_id
            for paragraph in section.paragraphs
            for detail_id in paragraph.required_detail_ids
        ]
        assert sorted(placed) == sorted(detail_ids[owner]), owner
    assert validate_narrative_plan(plan, context_set) == ()


def test_invalid_narrative_organization_proposals_fall_back_deterministically() -> None:
    """R7: an invalid proposal never places a detail the builder did not offer."""

    context_set = _two_context_set()
    detail_ids = _detail_ids_by_mechanism(context_set)

    def _proposal(mutate):
        def _caller(mechanism_id, details, sections, roles, **kwargs):
            payload = {
                "mechanism_id": mechanism_id,
                "paragraphs": [
                    {"role": "core_transformations", "detail_ids": list(details)}
                ],
            }
            mutate(payload, details)
            return payload
        return _caller

    cases = {
        "unknown_detail": lambda payload, details: payload["paragraphs"][0][
            "detail_ids"
        ].append("d:invented"),
        "duplicate_detail": lambda payload, details: payload["paragraphs"][0][
            "detail_ids"
        ].append(details[0]),
        "dropped_detail": lambda payload, details: payload["paragraphs"][0].update(
            {"detail_ids": list(details)[:-1]}
        ),
        "unknown_role": lambda payload, details: payload["paragraphs"][0].update(
            {"role": "invented_role"}
        ),
        "oversized_group": lambda payload, details: payload["paragraphs"][0].update(
            {"detail_ids": [details[0]] * 9}
        ),
    }
    for name, mutate in cases.items():
        plan, trace = build_narrative_plan_v3(
            contexts=context_set,
            proposal_caller=_proposal(mutate),
        )
        assert trace["proposal_status"] == "not_accepted", name
        assert "narrative_proposal_not_consumed" in trace["proposal_failures"], name
        # The deterministic grouping still places every clean detail once.
        placed = sorted(
            detail_id
            for section in plan.sections
            for paragraph in section.paragraphs
            for detail_id in paragraph.required_detail_ids
        )
        assert placed == sorted(
            detail_id
            for values in detail_ids.values()
            for detail_id in values
        ), name
        assert validate_narrative_plan(plan, context_set) == (), name


def test_equal_section_count_reverse_outline_keeps_owner_identity() -> None:
    """R7 correction: a reordered outline must not swap heading and owner.

    The second review's probe: two mechanisms, two sections, and a prior
    outline in reverse order.  Reusing ``prior_sections[sec_idx - 1]`` by
    position produced a section headed for ``mech_beta`` whose paragraphs and
    mechanism ids belonged to ``mech_alpha`` while ``validate_narrative_plan``
    stayed empty, because the new plan was internally consistent.
    """

    context_set = _two_context_set()
    base_plan, _trace = build_narrative_plan_v3(contexts=context_set)
    reversed_plan = base_plan.model_copy(
        update={"sections": tuple(reversed(base_plan.sections))}
    )
    plan, trace = build_narrative_plan_v3(
        contexts=context_set, prior_plan=reversed_plan
    )

    assert validate_narrative_plan(plan, context_set) == ()
    prior_by_id = {
        str(section.section_id): section for section in reversed_plan.sections
    }
    for section in plan.sections:
        declared = {str(value) for value in section.mechanism_ids}
        paragraph_owners = {
            str(paragraph.mechanism_id) for paragraph in section.paragraphs
        }
        assert declared, section.section_id
        assert paragraph_owners == declared, section.section_id
        # A reused section keeps the identity of the prior section that owns
        # the same mechanism, so heading and owner can never disagree.
        prior = prior_by_id.get(str(section.section_id))
        assert prior is not None, section.section_id
        assert {str(value) for value in prior.mechanism_ids} == declared
        assert section.heading == prior.heading
    identity = trace["section_identity"]
    assert {entry["owner"] for entry in identity["proven_sections"]} == {
        "mech_alpha",
        "mech_beta",
    }
    assert identity["owner_unproven"] == []


def _multi_section_prior_plan():
    """Two mechanisms, one of which owns two proven prior sections."""

    context_set = _two_context_set()
    base_plan, _ = build_narrative_plan_v3(contexts=context_set)
    alpha = base_plan.sections[0].model_copy(update={"mechanism_ids": ("mech_alpha",)})
    beta = base_plan.sections[1].model_copy(update={"mechanism_ids": ("mech_beta",)})
    prior_plan = base_plan.model_copy(update={"sections": (
        alpha.model_copy(update={"section_id": "MA-S1"}),
        beta.model_copy(update={"section_id": "MA-S2"}),
        alpha.model_copy(update={"section_id": "MA-S3"}),
    )})
    return context_set, prior_plan


def test_section_organization_proposal_replaces_the_count_split() -> None:
    """R7: a validated proposal decides which section argues which details."""

    context_set, prior_plan = _multi_section_prior_plan()
    base_plan, _ = build_narrative_plan_v3(contexts=context_set)
    # The mechanism's ordered clean details are the closed set the proposal
    # may partition; read them from the deterministic plan.
    deterministic_details = sorted(
        detail_id
        for section in base_plan.sections[:1]
        for paragraph in section.paragraphs
        for detail_id in paragraph.required_detail_ids
    )
    assert deterministic_details, "fixture must place alpha details"

    calls: list[dict] = []

    def _caller(mechanism_id, details, sections, roles, **kwargs):
        calls.append({
            "kind": kwargs.get("kind"),
            "mechanism_id": mechanism_id,
            "details": list(details),
            "sections": list(sections),
        })
        if kwargs.get("kind") != "section_organization":
            return {}
        # Reverse of the deterministic count split: the first section argues
        # two details, the second one.
        return {
            "mechanism_id": mechanism_id,
            "sections": [
                {"section_id": "MA-S1", "detail_ids": list(details)[:2]},
                {"section_id": "MA-S3", "detail_ids": list(details)[2:]},
            ],
        }

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        prior_plan=prior_plan,
        proposal_caller=_caller,
    )
    assert any(
        call["kind"] == "section_organization" and call["mechanism_id"] == "mech_alpha"
        for call in calls
    ), calls
    assert trace["proposal_status"] in {"accepted", "partially_accepted"}, trace[
        "proposal_failures"
    ]
    applied = [
        entry for entry in trace.get("proposal_applied", ())
        if entry.get("kind") == "section_organization"
    ]
    assert applied and applied[0]["mechanism_id"] == "mech_alpha"
    by_section = {
        str(section.section_id): sorted(
            detail_id
            for paragraph in section.paragraphs
            for detail_id in paragraph.required_detail_ids
        )
        for section in plan.sections
    }
    assert by_section["MA-S1"] == sorted(details_for_section(applied[0], "MA-S1"))
    assert by_section["MA-S3"] == sorted(details_for_section(applied[0], "MA-S3"))
    # The deterministic count split would have produced [1, 2]; the consumed
    # proposal produced [2, 1].
    assert len(by_section["MA-S1"]) == 2
    assert len(by_section["MA-S3"]) == 1
    assert validate_narrative_plan(plan, context_set) == ()


def details_for_section(entry: dict, section_id: str) -> list[str]:
    return list(entry["section_details"].get(section_id, ()))


def test_invalid_section_organization_proposal_falls_back_to_count_split() -> None:
    """R7: an invalid proposal never reassigns section ownership."""

    context_set, prior_plan = _multi_section_prior_plan()

    def _caller(mechanism_id, details, sections, roles, **kwargs):
        if kwargs.get("kind") != "section_organization":
            return {}
        # Unknown section id plus a dropped detail.
        return {
            "mechanism_id": mechanism_id,
            "sections": [
                {"section_id": "MA-S9", "detail_ids": list(details)[:2]},
                {"section_id": "MA-S3", "detail_ids": list(details)[2:]},
            ],
        }

    plan, trace = build_narrative_plan_v3(
        contexts=context_set,
        prior_plan=prior_plan,
        proposal_caller=_caller,
    )
    assert trace["proposal_status"] == "not_accepted"
    assert any(
        failure.startswith("section_proposal_unknown_section:")
        for failure in trace["proposal_failures"]
    ), trace["proposal_failures"]
    by_section = {
        str(section.section_id): sorted(
            detail_id
            for paragraph in section.paragraphs
            for detail_id in paragraph.required_detail_ids
        )
        for section in plan.sections
    }
    # Deterministic count split for three details over two sections.
    assert len(by_section["MA-S1"]) == 1
    assert len(by_section["MA-S3"]) == 2
    assert validate_narrative_plan(plan, context_set) == ()


def test_default_product_entry_builds_and_consumes_a_proposal_caller() -> None:
    """R7 (third review): the default product entry requests proposals.

    ``_build_narrative_plan_v3`` is the wrapper the Writer phase uses with no
    architect caller.  Given a usable model config and a transport, it must
    build the bounded proposal caller, capture the actual request with the
    mechanism semantics, consume the approved grouping and record the attempt.
    """

    from code2paper.agentic.publication_method_writer import (
        _build_narrative_plan_v3,
    )
    from code2paper.schemas import LLMConfig, LLMProvider

    context_set = _two_context_set()
    requests: list[dict] = []

    def _transport(config, request):
        payload = dict(request.input_payload or {})
        requests.append({
            "prompt": request.prompt,
            "payload": payload,
            "schema_name": request.schema_name,
            "schema": request.response_json_schema,
        })
        detail_ids = list(payload.get("detail_ids") or ())
        body = {
            "mechanism_id": str(payload.get("mechanism_id") or ""),
            "paragraphs": [
                {"role": "core_transformations", "detail_ids": [detail_id]}
                for detail_id in detail_ids
            ],
        }
        import json as _json

        class _Response:
            text = _json.dumps(body)

        return _Response()

    plan, trace = _build_narrative_plan_v3(
        context_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        proposal_llm_caller=_transport,
    )
    assert trace["proposal_default_caller"] == "configured"
    assert trace["proposal_status"] == "accepted", trace["proposal_failures"]
    assert trace.get("proposal_attempt_count", 0) >= 1
    assert trace["proposal_call_accounting"] == "recorded_not_in_invocation_plan"
    # The actual request carries the closed ids and the mechanism semantics.
    assert requests
    payload = requests[0]["payload"]
    assert payload["kind"] == "narrative_organization"
    assert payload["detail_ids"]
    assert "closed detail ids" in requests[0]["prompt"]
    assert requests[0]["schema_name"] == "NarrativeOrganizationProposalV1"
    # The accepted grouping is the plan the Writer request is built from.
    for section in plan.sections:
        for paragraph in section.paragraphs:
            assert len(paragraph.required_detail_ids) == 1
    assert validate_narrative_plan(plan, context_set) == ()

    # Without a transport and without a provider key the product path stays
    # deterministic and reports that no caller was requested.
    _plain_plan, plain_trace = _build_narrative_plan_v3(
        context_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
    )
    assert plain_trace["proposal_status"] == "not_requested"
    assert plain_trace["proposal_default_caller"] == "unavailable"


def test_default_proposal_caller_repairs_after_a_typed_rejection() -> None:
    """R7: the first rejection is fed back to the owner as repair input."""

    from code2paper.agentic.publication_method_writer import (
        _build_narrative_plan_v3,
    )
    from code2paper.schemas import LLMConfig, LLMProvider

    context_set = _two_context_set()
    attempts: list[dict] = []

    def _transport(config, request):
        import json as _json

        payload = dict(request.input_payload or {})
        attempts.append({
            "repair_failures": list(payload.get("repair_failures") or ()),
            "prompt": request.prompt,
        })
        if not payload.get("repair_failures"):
            # First answer drops a detail: the validator must reject it.
            body = {
                "mechanism_id": str(payload.get("mechanism_id") or ""),
                "paragraphs": [{
                    "role": "core_transformations",
                    "detail_ids": list(payload.get("detail_ids") or ())[:-1],
                }],
            }
        else:
            body = {
                "mechanism_id": str(payload.get("mechanism_id") or ""),
                "paragraphs": [
                    {"role": "core_transformations", "detail_ids": [detail_id]}
                    for detail_id in (payload.get("detail_ids") or ())
                ],
            }

        class _Response:
            text = _json.dumps(body)

        return _Response()

    plan, trace = _build_narrative_plan_v3(
        context_set,
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        proposal_llm_caller=_transport,
    )
    assert trace["proposal_status"] == "accepted", trace["proposal_failures"]
    # The retry carried the typed rejection back to the owner.
    assert len(attempts) >= 2
    assert attempts[0]["repair_failures"] == []
    assert any(
        failure.startswith("narrative_proposal_detail_unplaced:")
        for failure in attempts[1]["repair_failures"]
    ), attempts[1]["repair_failures"]
    assert "previous answer was rejected" in attempts[1]["prompt"]
    assert validate_narrative_plan(plan, context_set) == ()
