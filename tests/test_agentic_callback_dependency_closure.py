"""R8: a callback revalidates exactly the sections its delta can reach."""

from __future__ import annotations

import pytest

from code2paper.agentic.callback_dependency_closure import (
    CallbackAuthorityDeltaV1,
    compute_callback_dependency_closure,
    narrow_resume_sections,
)
from code2paper.agentic.method_argument_models import (
    MethodArgumentUnitV1,
    MethodSectionPlanV2,
    SectionArgumentGraphV1,
)
from code2paper.agentic.method_architect import (
    NarrativeParagraphPlanV3,
    NarrativePlanV3,
    NarrativeSectionPlanV3,
    NarrativeUnitV1,
)


def _plan() -> MethodSectionPlanV2:
    shared = MethodArgumentUnitV1(
        argument_unit_id="unit:shared",
        section_role="core_method",
        research_question="Shared configuration?",
        configuration_ids=("config:shared",),
    )
    return MethodSectionPlanV2(
        plan_id="plan:closure",
        sections=(
            SectionArgumentGraphV1(
                section_id="MA-S1",
                heading="First",
                reader_question="Q1?",
                argument_unit_ids=("unit:one", "unit:shared"),
            ),
            SectionArgumentGraphV1(
                section_id="MA-S2",
                heading="Second",
                reader_question="Q2?",
                argument_unit_ids=("unit:two", "unit:shared"),
            ),
        ),
        argument_units=(
            MethodArgumentUnitV1(
                argument_unit_id="unit:one",
                section_role="core_method",
                research_question="Q1?",
                claim_ids=("claim:alpha",),
            ),
            MethodArgumentUnitV1(
                argument_unit_id="unit:two",
                section_role="core_method",
                research_question="Q2?",
                claim_ids=("claim:beta",),
            ),
            shared,
        ),
    )


def _narrative_plan() -> NarrativePlanV3:
    def _section(section_id: str, mechanism_id: str, detail_id: str):
        paragraph_id = f"{section_id}_p1"
        return NarrativeSectionPlanV3(
            section_id=section_id,
            heading=f"Heading {section_id}",
            mechanism_ids=(mechanism_id,),
            paragraphs=(NarrativeParagraphPlanV3(
                paragraph_id=paragraph_id,
                section_id=section_id,
                role="core_transformations",
                mechanism_id=mechanism_id,
                required_detail_ids=(detail_id,),
            ),),
        )

    return NarrativePlanV3(
        plan_id="plan:narrative",
        sections=(
            _section("MA-S1", "mech_alpha", "d:alpha"),
            _section("MA-S2", "mech_beta", "d:beta"),
        ),
        narrative_units=(
            NarrativeUnitV1(
                unit_id="unit_1",
                section_id="MA-S1",
                mechanism_context_ids=("mech_alpha",),
                rhetorical_role="core_model",
                reader_question="How?",
                paragraph_ids=("MA-S1_p1",),
                required_detail_ids=("d:alpha",),
                optional_detail_ids=(),
                formula_obligation_ids=(),
                suggested_depth="standard",
            ),
        ),
    )


def test_closure_maps_typed_targets_to_owning_sections() -> None:
    closure = compute_callback_dependency_closure(
        CallbackAuthorityDeltaV1(
            claim_ids=("claim:alpha",),
            detail_ids=("d:beta",),
        ),
        plan=_plan(),
        narrative_plan=_narrative_plan(),
    )
    assert closure.affected_section_ids == ("MA-S1", "MA-S2")
    assert closure.affected_unit_ids == ("unit:one",)
    assert closure.affected_paragraph_ids == ("MA-S2_p1",)
    assert closure.basis["claim:claim:alpha"] == ("MA-S1",)
    assert closure.basis["detail:d:beta"] == ("MA-S2",)
    assert closure.unresolved_target_ids == ()


def test_shared_configuration_pulls_in_every_owning_section() -> None:
    closure = compute_callback_dependency_closure(
        CallbackAuthorityDeltaV1(configuration_ids=("config:shared",)),
        plan=_plan(),
        narrative_plan=_narrative_plan(),
    )
    assert closure.affected_section_ids == ("MA-S1", "MA-S2")
    assert closure.affected_unit_ids == ("unit:shared",)


def test_unmappable_targets_are_reported_not_dropped() -> None:
    closure = compute_callback_dependency_closure(
        CallbackAuthorityDeltaV1(fact_ids=("fact:unknown",)),
        plan=_plan(),
        narrative_plan=_narrative_plan(),
    )
    assert closure.unresolved_target_ids == ("fact:fact:unknown",)
    sections, reason, unresolved = narrow_resume_sections(
        requested_section_ids=("MA-S1", "MA-S2"), closure=closure
    )
    # An unmappable target cannot prove any scope sufficient: block.
    assert sections == ("MA-S1", "MA-S2")
    assert reason == "closure_unresolved_targets_blocked"
    assert unresolved == ("fact:fact:unknown",)


def test_heading_change_does_not_enter_the_closure() -> None:
    narrative = _narrative_plan()
    renamed = narrative.model_copy(update={
        "sections": tuple(
            section.model_copy(update={"heading": "Renamed"})
            for section in narrative.sections
        ),
    })
    delta = CallbackAuthorityDeltaV1(claim_ids=("claim:alpha",))
    first = compute_callback_dependency_closure(
        delta, plan=_plan(), narrative_plan=narrative
    )
    second = compute_callback_dependency_closure(
        delta, plan=_plan(), narrative_plan=renamed
    )
    assert first.affected_section_ids == second.affected_section_ids == ("MA-S1",)
    assert first.content_digest == second.content_digest


def test_proven_subset_narrows_the_resume_scope() -> None:
    closure = compute_callback_dependency_closure(
        CallbackAuthorityDeltaV1(claim_ids=("claim:alpha",)),
        plan=_plan(),
        narrative_plan=_narrative_plan(),
    )
    sections, reason, unresolved = narrow_resume_sections(
        requested_section_ids=("MA-S1", "MA-S2"), closure=closure
    )
    assert sections == ("MA-S1",)
    assert reason == "closure_narrowed"
    assert unresolved == ()

    # A closure that reaches beyond the request expands the resume scope; it
    # is never narrowed below the proven impact.
    sections_wide, reason_wide, unresolved_wide = narrow_resume_sections(
        requested_section_ids=("MA-S2",), closure=closure
    )
    assert sections_wide == ("MA-S2", "MA-S1")
    assert reason_wide == "closure_expanded"
    assert unresolved_wide == ()


def test_stage_statuses_separate_fulfillment_from_committed_prose() -> None:
    """R8: a fulfilled research request with a failed Writer is not committed."""

    from code2paper.agentic.writing_callback_fulfillment import (
        WritingCallbackFulfillmentResultV1,
    )

    result = WritingCallbackFulfillmentResultV1(
        research_fulfilled=True,
        revision_rebuilt=True,
        writer_resumed=True,
        prose_committed=False,
        final_validation_status="blocked",
        resume_scope_source="closure_narrowed",
        dependency_closure={"affected_section_ids": ["MA-S1"]},
        stage_identity={
            "initial": {"mode": "unified"},
            "research_fulfilled": {"mode": "unified"},
            "revision_rebuilt": {"mode": "unified"},
            "writer_resumed": {"mode": "unified"},
        },
    )
    assert result.research_fulfilled is True
    assert result.writer_resumed is True
    assert result.prose_committed is False
    assert result.stage_identity["writer_resumed"]["mode"] == "unified"
    assert result.final_validation_status == "blocked"


def test_callback_round_budget_survives_a_replay(tmp_path) -> None:
    """R8: re-entering the callback loop must not restart its round budget."""

    from code2paper.agentic.writing_callback_fulfillment import (
        _callback_budget_state_path,
        _read_consumed_rounds,
        _record_consumed_rounds,
    )

    state_path = _callback_budget_state_path(tmp_path)
    assert _read_consumed_rounds(state_path) == (0, True)
    _record_consumed_rounds(state_path, 1)
    assert _read_consumed_rounds(state_path) == (1, True)
    _record_consumed_rounds(state_path, 2)
    assert _read_consumed_rounds(state_path) == (2, True)

    # A corrupt budget record fails closed: it must not read as "no rounds
    # consumed", which would silently restart the budget after a crash.
    state_path.write_text("{not json", encoding="utf-8")
    consumed, ok = _read_consumed_rounds(state_path)
    assert ok is False
    state_path.write_text('{"consumed_rounds": "many"}', encoding="utf-8")
    assert _read_consumed_rounds(state_path)[1] is False


def test_authority_diff_closure_covers_changed_claim_contracts(tmp_path) -> None:
    """R8 correction: the closure follows the rebuilt authority, not new ids."""

    from code2paper.agentic.writing_callback_fulfillment import (
        _authority_delta_from_revision,
    )

    previous = tmp_path / "previous_claims.json"
    previous.write_text(
        '{"claims": [{"claim_id": "c-1", "status": "partial",'
        ' "required_qualifiers": ["only on scoped inputs"]}]}',
        encoding="utf-8",
    )
    rebuilt = tmp_path / "rebuilt_claims.json"
    rebuilt.write_text(
        '{"claims": [{"claim_id": "c-1", "status": "partial",'
        ' "required_qualifiers": []}]}',
        encoding="utf-8",
    )
    delta = _authority_delta_from_revision(
        previous_paths={"atomic_claim_set_v3": str(previous)},
        rebuilt_paths={"atomic_claim_set_v3": str(rebuilt)},
    )
    # The same claim id changed its contract: it must be part of the delta.
    assert delta.claim_ids == ("c-1",)

    unchanged = _authority_delta_from_revision(
        previous_paths={"atomic_claim_set_v3": str(rebuilt)},
        rebuilt_paths={"atomic_claim_set_v3": str(rebuilt)},
    )
    assert unchanged.claim_ids == ()


def test_corrupt_stage_record_and_receipts_fail_closed(tmp_path) -> None:
    """R8 correction: unreadable recovery records never read as success."""

    from code2paper.agentic.unified_invocation_ledger import (
        read_all_completed_receipts,
        unsettled_started_attempts,
    )
    from code2paper.agentic.writing_callback_fulfillment import (
        _callback_stage_state_path,
        _read_stage_state,
        _write_stage_state,
    )

    stage_path = _callback_stage_state_path(tmp_path)
    assert _read_stage_state(stage_path) == ({}, True)
    _write_stage_state(stage_path, {"initial": {"mode": "unified"}})
    stages, ok = _read_stage_state(stage_path)
    assert ok is True and stages["initial"]["mode"] == "unified"
    stage_path.write_text("{not json", encoding="utf-8")
    assert _read_stage_state(stage_path)[1] is False

    ledger_root = tmp_path / "invocations"
    invocation_dir = ledger_root / "inv-writer-MA-S1-abc"
    invocation_dir.mkdir(parents=True)
    (invocation_dir / "attempt-0001.completed.json").write_text(
        "{not json", encoding="utf-8"
    )
    assert read_all_completed_receipts(ledger_root) == ()
    with pytest.raises(ValueError, match="unified_receipt_corrupt"):
        read_all_completed_receipts(ledger_root, strict=True)

    # An interrupted attempt reserves its planned tokens, and the attempt
    # currently being measured is excluded from that reserve.
    from code2paper.agentic.unified_context_models import ConsumerInvocationV1

    invocation = ConsumerInvocationV1(
        invocation_id="inv:writer:MA-S1:page",
        role="writer",
        phase="writer",
        workset_id="workset:section:MA-S1",
        task_ids=("MA-S1",),
        mechanism_id="mech:one",
        page_id="page:one",
        expected_technical_bytes_digest="sha256:bytes",
        expected_request_envelope_digest="sha256:envelope",
        max_input_tokens=1000,
        max_output_tokens=100,
        max_attempts=2,
    )
    from code2paper.agentic.unified_context_models import ConsumerInvocationPlanV1

    plan = ConsumerInvocationPlanV1(
        plan_revision=1,
        phase="writer",
        archive_digest="sha256:archive",
        workset_manifest_digest="sha256:manifest",
        envelope_digest="sha256:envelope",
        profile_digest="sha256:profile",
        model_identity_digest="sha256:model",
        invocations=(invocation,),
        formalizer_repair_call_limit=0,
    )
    from code2paper.agentic.unified_invocation_ledger import invocation_dir as _dir

    started_dir = _dir(ledger_root, invocation.invocation_id)
    started_dir.mkdir(parents=True, exist_ok=True)
    # R6 correction: the attempt is metered from the plan it started under, so
    # the marker must name that plan (a marker without a plan digest cannot be
    # metered and is reported as unknown).
    from code2paper.agentic.unified_context_models import (
        InvocationAttemptStartedV1,
    )
    from code2paper.agentic.unified_invocation_ledger import (
        publish_attempt_started,
    )

    publish_attempt_started(
        ledger_root,
        InvocationAttemptStartedV1(
            invocation_id=invocation.invocation_id,
            attempt=1,
            plan_digest=str(plan.content_digest),
            page_id=invocation.page_id,
            expected_technical_bytes_digest="sha256:bytes",
            expected_request_envelope_digest="sha256:envelope",
            model_identity_digest="sha256:model",
            started_at_unix=1.0,
        ),
    )
    unsettled = unsettled_started_attempts(ledger_root, plan)
    assert unsettled == ((invocation.invocation_id, 1, 1000),)
    assert unsettled_started_attempts(
        ledger_root, plan, exclude=(invocation.invocation_id, 1)
    ) == ()


def test_configuration_value_change_reaches_every_owning_section(
    tmp_path,
) -> None:
    """R8 correction: a shared configuration change is an authority delta.

    The second review's probe: ``config:shared`` moved from ``true`` to
    ``false`` while being used by MA-S1 and MA-S2.  The previous diff only read
    claim contracts and new detail ids, so both the delta and the closure came
    back empty and the resume silently kept a single requested section.
    """

    from code2paper.agentic.method_argument_models import (
        ConfigurationClaimSetV1,
        ConfigurationClaimV1,
    )
    from code2paper.agentic.writing_callback_fulfillment import (
        _authority_delta_from_revision,
    )

    def _config(value: bool) -> ConfigurationClaimSetV1:
        return ConfigurationClaimSetV1(claims=(ConfigurationClaimV1(
            configuration_id="config:shared",
            key="use_feature",
            value=value,
            state="actual",
            definition_span_ids=("span:config.py:1:1",),
            entrypoint_span_ids=("span:main.py:1:1",),
        ),))

    before_path = tmp_path / "config_before.json"
    after_path = tmp_path / "config_after.json"
    before_path.write_text(_config(True).model_dump_json(), encoding="utf-8")
    after_path.write_text(_config(False).model_dump_json(), encoding="utf-8")

    delta = _authority_delta_from_revision(
        previous_paths={"configuration_claims_v1": str(before_path)},
        rebuilt_paths={"configuration_claims_v1": str(after_path)},
    )
    assert delta.configuration_ids == ("config:shared",)
    assert not delta.is_empty()

    closure = compute_callback_dependency_closure(
        delta, plan=_plan(), narrative_plan=_narrative_plan()
    )
    assert closure.unresolved_target_ids == ()
    assert closure.affected_section_ids == ("MA-S1", "MA-S2")
    sections, reason, unresolved = narrow_resume_sections(
        requested_section_ids=("MA-S1",), closure=closure
    )
    assert reason == "closure_expanded"
    assert sections == ("MA-S1", "MA-S2")
    assert unresolved == ()


def test_deleted_claim_is_a_delta_and_removes_its_section_from_scope(
    tmp_path,
) -> None:
    """R8 correction: a removed claim is an authority change, not a no-op."""

    import json

    from code2paper.agentic.writing_callback_fulfillment import (
        _authority_delta_from_revision,
    )

    before_path = tmp_path / "claims_before.json"
    after_path = tmp_path / "claims_after.json"
    before_path.write_text(
        json.dumps({"claims": [{
            "claim_id": "claim:alpha",
            "status": "supported",
            "required_qualifiers": [],
        }]}),
        encoding="utf-8",
    )
    after_path.write_text(json.dumps({"claims": []}), encoding="utf-8")

    delta = _authority_delta_from_revision(
        previous_paths={"atomic_claims_v3": str(before_path)},
        rebuilt_paths={"atomic_claims_v3": str(after_path)},
    )
    assert delta.claim_ids == ("claim:alpha",)

    closure = compute_callback_dependency_closure(
        delta, plan=_plan(), narrative_plan=_narrative_plan()
    )
    assert closure.unresolved_target_ids == ()
    assert closure.affected_section_ids == ("MA-S1",)


def test_removed_detail_and_fact_resolve_through_the_previous_graph() -> None:
    """R8 correction: deleted authority is mapped through the old graph too."""

    previous_narrative = _narrative_plan()
    # The rebuild deleted ``d:beta`` entirely, so the new plan no longer names
    # it.  Without the previous narrative plan the target would be unresolved
    # and the whole resume would block.
    rebuilt_narrative = NarrativePlanV3(
        plan_id="plan:narrative:rebuilt",
        sections=(
            previous_narrative.sections[0],
        ),
        narrative_units=(),
    )
    delta = CallbackAuthorityDeltaV1(detail_ids=("d:beta",))
    closure = compute_callback_dependency_closure(
        delta,
        plan=_plan(),
        narrative_plan=rebuilt_narrative,
        previous_narrative_plan=previous_narrative,
    )
    assert closure.unresolved_target_ids == ()
    assert closure.affected_section_ids == ("MA-S2",)

    # A fact that only the previous dependency graph connects to a detail.
    closure_from_map = compute_callback_dependency_closure(
        CallbackAuthorityDeltaV1(fact_ids=("fact:one",)),
        plan=_plan(),
        narrative_plan=rebuilt_narrative,
        previous_narrative_plan=previous_narrative,
        target_owner_map={"fact:fact:one": ("MA-S2",)},
    )
    assert closure_from_map.unresolved_target_ids == ()
    assert closure_from_map.affected_section_ids == ("MA-S2",)
    assert closure_from_map.basis["fact:fact:one"] == ("MA-S2",)


def test_snapshot_diff_survives_rebuild_into_the_same_path(tmp_path) -> None:
    """R8 correction: freeze the before revision, not the before path."""

    from code2paper.agentic.writing_callback_fulfillment import (
        _authority_delta_from_snapshots,
        _authority_revision_snapshot,
    )

    artifact = tmp_path / "configuration_claims_v1.json"
    artifact.write_text(
        '{"claims": [{"configuration_id": "config:shared", "key": "flag",'
        ' "value": true, "state": "actual"}]}',
        encoding="utf-8",
    )
    before = _authority_revision_snapshot(
        {"configuration_claims_v1": str(artifact)}
    )
    # The rebuild persists into the same output root.
    artifact.write_text(
        '{"claims": [{"configuration_id": "config:shared", "key": "flag",'
        ' "value": false, "state": "actual"}]}',
        encoding="utf-8",
    )
    after = _authority_revision_snapshot(
        {"configuration_claims_v1": str(artifact)}
    )
    delta = _authority_delta_from_snapshots(before=before, after=after)
    assert delta.configuration_ids == ("config:shared",)
