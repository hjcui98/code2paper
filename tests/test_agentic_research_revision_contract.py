"""R10 (§15): hypotheses are revisable, author constraints are not shrinkable.

The contract is exercised through the real harness entry points
(``assess_revision_proposal`` / ``apply_revision``) with a graph built by the
intent compiler, so the tests cover the producer->harness->journal chain and
the acceptance list of §15: revise inferred hypotheses; reject deleted author
constraints, reason-only proposals, unobserved refs, wrong parents, forged
revisions, exhausted budgets, duplicate resume and generic substitution; never
let a revision invent support or shrink the coverage denominator.
"""

from __future__ import annotations

import pytest

from code2paper.agentic.research_models import (
    TypedBehaviorTargetV1,
)
from code2paper.agentic.research_revision_contract import (
    AuthorConstraintSetV1,
    RevisionJournalV1,
    RevisionProposalV1,
    RevisionTargetV1,
    apply_revision,
    assess_revision_proposal,
    build_author_constraint_set,
)


def _target(
    target_id: str,
    *,
    provenance: str,
    predicates: tuple[str, ...] = ("CONCAT",),
    relations: tuple[str, ...] = (),
    conditions: tuple[str, ...] = (),
    inputs: tuple[str, ...] = (),
) -> TypedBehaviorTargetV1:
    return TypedBehaviorTargetV1(
        target_id=target_id,
        role="fusion",
        provenance=provenance,  # type: ignore[arg-type]
        desired_predicates=predicates,
        required_relations=relations,
        conditions=conditions,
        inputs=inputs,
    )


def _obligation(obligation_id: str, targets, author_text: str = ""):
    from code2paper.agentic.intent_compiler_v2 import IntentObligationV2

    return IntentObligationV2(
        obligation_id=obligation_id,
        kind="method_mainline",
        priority="must_cover",
        source_field="method_steps",
        author_text=author_text,
        typed_behavior_targets=tuple(targets),
    )


def _graph():
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2

    return IntentObligationGraphV2(
        project_goal="Explain the method.",
        method_goal="Reproduce the fusion stage.",
        obligations=[
            _obligation(
                "O-1",
                [
                    _target(
                        "target-author",
                        provenance="author_explicit",
                        predicates=("CONCAT", "SELECT"),
                        conditions=("training",),
                        inputs=("positive_pairs",),
                    ),
                    _target(
                        "target-inferred",
                        provenance="system_inferred",
                        predicates=("MEAN",),
                    ),
                ],
                author_text="The method concatenates positive and negative pairs.",
            ),
            _obligation(
                "O-2",
                [_target("target-other", provenance="author_explicit")],
                author_text="Second author requirement.",
            ),
        ],
    )


def _proposal(
    *,
    after_targets,
    before_target_ids=("target-inferred",),
    source_type: str = "system_inferred",
    observation_refs=("span:model.py:1:2",),
    relation_refs=(),
    budget_requests: int = 1,
    subquestion_parent_id: str = "",
    parent: str = "O-1",
    author_constraint_digest: str = "",
    proposal_id: str = "proposal:1",
) -> RevisionProposalV1:
    return RevisionProposalV1(
        proposal_id=proposal_id,
        parent_obligation_id=parent,
        source_type=source_type,  # type: ignore[arg-type]
        before_target_ids=tuple(before_target_ids),
        after_targets=tuple(after_targets),
        observation_refs=tuple(observation_refs),
        relation_refs=tuple(relation_refs),
        reason="the inspected span supports a different fusion",
        unresolved_impact=("downstream normalization still unresolved",),
        budget_requests=budget_requests,
        subquestion_parent_id=subquestion_parent_id,
        author_constraint_digest=author_constraint_digest,
    )


def _assess(proposal, *, graph=None, observed=("span:model.py:1:2",), **kwargs):
    graph = graph or _graph()
    constraints = build_author_constraint_set(graph)
    return assess_revision_proposal(
        proposal,
        graph=graph,
        author_constraints=constraints,
        observed_ref_ids=observed,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Allowed: revise an inferred hypothesis
# ---------------------------------------------------------------------------


def test_inferred_hypothesis_can_be_revised_with_observed_evidence() -> None:
    graph = _graph()
    constraints = build_author_constraint_set(graph)
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                role="fusion",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
                provenance="system_inferred",
            ),
        ],
        author_constraint_digest=constraints.content_digest,
    )
    assessment = _assess(proposal, graph=graph)
    assert assessment.verdict == "accepted", assessment.failures
    enriched, journal, failures = apply_revision(
        graph=graph,
        proposal=proposal,
        assessment=assessment,
        object_digests={"research_agenda_v1": "sha256:agenda"},
    )
    assert failures == ()
    assert journal.entries[0].handoff_invalidated is True
    assert journal.entries[0].applied_target_ids == ("target-inferred",)
    assert journal.entries[0].removed_target_ids == ()
    assert "target-author" in {
        target.target_id
        for obligation in enriched.obligations
        for target in obligation.typed_behavior_targets
    }
    # The coverage denominator stays the original author boundary.
    assert assessment.coverage_denominator_ids == constraints.non_deletable_target_ids(
        graph
    )


def test_new_subquestion_keeps_parent_provenance_and_its_own_budget() -> None:
    graph = _graph()
    constraints = build_author_constraint_set(graph)
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-subquestion",
                role="fusion",
                desired_predicates=("COMPUTE",),
                provenance="research_subquestion",
            ),
        ],
        before_target_ids=(),
        source_type="research_subquestion",
        subquestion_parent_id="O-1",
        author_constraint_digest=constraints.content_digest,
    )
    assessment = _assess(proposal, graph=graph, remaining_budget=2)
    assert assessment.verdict == "accepted", assessment.failures

    wrong_parent = _proposal(
        after_targets=list(proposal.after_targets),
        before_target_ids=(),
        source_type="research_subquestion",
        subquestion_parent_id="O-2",
        proposal_id="proposal:sub-wrong",
    )
    assert "revision_subquestion_parent_missing" in _assess(
        wrong_parent, graph=graph
    ).failures


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------


def test_author_constraint_cannot_be_deleted_or_downgraded() -> None:
    graph = _graph()
    constraints = build_author_constraint_set(graph)
    assert constraints.content_digest
    # Dropping the author-explicit target.
    drop = _proposal(
        before_target_ids=("target-author",),
        after_targets=[],
    )
    assert "revision_author_constraint_deleted:target-author" in _assess(
        drop, graph=graph
    ).failures
    # Keeping the predicate but replacing FUSION with a generic COMPUTE.
    generic = _proposal(
        before_target_ids=("target-author",),
        after_targets=[
            RevisionTargetV1(
                target_id="target-author",
                role="fusion",
                desired_predicates=("COMPUTE",),
                provenance="system_inferred",
                replaces_target_ids=("target-author",),
            ),
        ],
    )
    generic_failures = _assess(generic, graph=graph).failures
    assert any(
        failure.startswith("revision_generic_substitution:")
        or failure.startswith("revision_author_predicate_dropped:")
        for failure in generic_failures
    ), generic_failures
    # Dropping only the author condition is a shrink too.
    condition_drop = _proposal(
        before_target_ids=("target-author",),
        after_targets=[
            RevisionTargetV1(
                target_id="target-author",
                role="fusion",
                desired_predicates=("CONCAT", "SELECT"),
                provenance="system_inferred",
                replaces_target_ids=("target-author",),
            ),
        ],
    )
    assert "revision_author_condition_dropped:training" in _assess(
        condition_drop, graph=graph
    ).failures


def test_reason_only_and_unobserved_proposals_are_rejected() -> None:
    graph = _graph()
    reason_only = _proposal(before_target_ids=(), after_targets=[])
    assert "revision_no_target_change" in _assess(
        reason_only, graph=graph
    ).failures

    unobserved = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        observation_refs=("span:never:read:1",),
    )
    assert "revision_ref_unobserved:span:never:read:1" in _assess(
        unobserved, graph=graph
    ).failures

    no_refs = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        observation_refs=(),
    )
    assert "revision_evidence_refs_missing" in _assess(
        no_refs, graph=graph
    ).failures


def test_wrong_parent_forged_revision_budget_and_duplicate_resume() -> None:
    graph = _graph()
    wrong_parent = _proposal(
        parent="O-missing",
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
    )
    assert "revision_unknown_parent:O-missing" in _assess(
        wrong_parent, graph=graph
    ).failures

    forged = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
    ).model_copy(update={"revision_id": "sha256:forged"})
    assert "revision_forged_identity" in _assess(forged, graph=graph).failures

    over_budget = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        budget_requests=5,
    )
    assert any(
        failure.startswith("revision_research_allowance_exhausted:")
        for failure in _assess(over_budget, graph=graph, remaining_budget=1).failures
    )

    accepted = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
    )
    assessment = _assess(accepted, graph=graph)
    _enriched, journal, _failures = apply_revision(
        graph=graph, proposal=accepted, assessment=assessment
    )
    again = _assess(accepted, graph=graph, previous_journal=journal)
    assert any(
        failure.startswith("revision_already_applied:")
        for failure in again.failures
    )
    _graph_again, journal_again, apply_failures = apply_revision(
        graph=graph,
        proposal=accepted,
        assessment=assessment,
        previous_journal=journal,
    )
    assert any(
        failure.startswith("revision_already_applied:")
        for failure in apply_failures
    )
    assert journal_again.current_revision_id() == journal.current_revision_id()


def test_author_boundary_review_cannot_self_sign() -> None:
    graph = _graph()
    constraints = build_author_constraint_set(graph)
    # Rewriting the author target in place with an equivalent predicate set
    # requires an independent verifier; without one it stays pending review.
    in_place = _proposal(
        before_target_ids=("target-author",),
        after_targets=[
            RevisionTargetV1(
                target_id="target-author",
                role="fusion",
                # Adds an inferred predicate while keeping every author one.
                desired_predicates=("CONCAT", "SELECT", "COMPUTE"),
                conditions=("training",),
                inputs=("positive_pairs",),
                provenance="system_inferred",
                replaces_target_ids=("target-author",),
            ),
        ],
    )
    assessment = _assess(in_place, graph=graph)
    assert assessment.verdict == "pending_review", assessment.failures
    assert "revision_semantic_review_unavailable" in assessment.failures

    with_verifier = assess_revision_proposal(
        in_place,
        graph=graph,
        author_constraints=constraints,
        observed_ref_ids=("span:model.py:1:2",),
        semantic_verifier=lambda before, after: True,
    )
    assert with_verifier.verdict == "accepted", with_verifier.failures
    assert with_verifier.semantic_review == "independent_verifier"

    rejecting = assess_revision_proposal(
        in_place,
        graph=graph,
        author_constraints=constraints,
        observed_ref_ids=("span:model.py:1:2",),
        semantic_verifier=lambda before, after: False,
    )
    assert rejecting.verdict == "rejected"
    assert "revision_semantic_not_equivalent:target-author" in rejecting.failures


def test_target_cannot_be_stolen_from_another_obligation() -> None:
    graph = _graph()
    proposal = _proposal(
        before_target_ids=(),
        after_targets=[
            RevisionTargetV1(
                target_id="target-other",
                desired_predicates=("COMPUTE",),
                provenance="system_inferred",
            ),
        ],
    )
    assert "revision_target_owned_elsewhere:target-other" in _assess(
        proposal, graph=graph
    ).failures


def test_unproven_provenance_cannot_be_deleted() -> None:
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2

    graph = IntentObligationGraphV2(
        obligations=[
            _obligation(
                "O-1",
                [_target("target-legacy", provenance="unproven")],
                author_text="Legacy author requirement.",
            ),
        ],
    )
    proposal = _proposal(
        before_target_ids=("target-legacy",),
        after_targets=[],
    )
    assert "revision_author_constraint_deleted:target-legacy" in _assess(
        proposal, graph=graph
    ).failures


def test_rejected_revision_does_not_change_the_graph_or_denominator() -> None:
    graph = _graph()
    constraints = build_author_constraint_set(graph)
    before_denominator = constraints.non_deletable_target_ids(graph)
    proposal = _proposal(
        before_target_ids=("target-author",),
        after_targets=[],
    )
    assessment = _assess(proposal, graph=graph)
    assert assessment.verdict == "rejected"
    enriched, journal, failures = apply_revision(
        graph=graph, proposal=proposal, assessment=assessment
    )
    assert failures and failures[0].startswith("revision_not_accepted:")
    assert enriched is graph
    assert journal.entries == ()
    assert constraints.non_deletable_target_ids(graph) == before_denominator


def test_handoff_validity_follows_the_journal() -> None:
    graph = _graph()
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
    )
    assessment = _assess(proposal, graph=graph)
    _enriched, journal, _failures = apply_revision(
        graph=graph, proposal=proposal, assessment=assessment
    )
    assert journal.handoff_is_current(journal.current_revision_id()) is True
    assert journal.handoff_is_current("sha256:previous-revision") is False
    assert isinstance(journal, RevisionJournalV1)
    assert isinstance(
        build_author_constraint_set(graph), AuthorConstraintSetV1
    )


# ---------------------------------------------------------------------------
# §15.6 atomic binding, journal persistence and handoff validity
# ---------------------------------------------------------------------------


def test_revision_binds_every_changed_object_digest(tmp_path) -> None:
    """A revision journals every bound object it changed, with real digests."""

    graph = _graph()
    constraints = build_author_constraint_set(graph)
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        author_constraint_digest=constraints.content_digest,
    )
    assessment = _assess(proposal, graph=graph)
    from code2paper.agentic.research_revision_contract import (
        build_object_digests,
        load_revision_journal,
        missing_bound_objects,
        write_revision_journal,
    )
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2

    claim_set = {"content_digest": "sha256:claims", "claims": []}
    agenda = {"content_digest": "sha256:agenda"}
    digests = build_object_digests({
        "research_agenda_v1": agenda,
        "intent_obligation_graph_v2": graph,
        "atomic_claims_v3": claim_set,
        "candidate_handoff_v1": None,
    })
    assert digests["research_agenda_v1"] == "sha256:agenda"
    assert digests["intent_obligation_graph_v2"].startswith("sha256:")
    # Objects the run does not hold are reported, not invented.
    assert "candidate_handoff_v1" not in digests
    missing = missing_bound_objects(digests)
    assert "obligation_coverage_v2" in missing
    assert "research_agenda_v1" not in missing

    enriched, journal, failures = apply_revision(
        graph=graph,
        proposal=proposal,
        assessment=assessment,
        object_digests=digests,
    )
    assert failures == ()
    entry = journal.entries[0]
    assert entry.object_digests["research_agenda_v1"] == "sha256:agenda"
    assert entry.object_digests["intent_obligation_graph_v2"] != (
        graph.content_digest
    ), "the changed graph must carry its new digest"
    assert isinstance(enriched, IntentObligationGraphV2)
    assert enriched.content_digest == entry.object_digests[
        "intent_obligation_graph_v2"
    ]
    path = write_revision_journal(tmp_path, journal)
    reloaded = load_revision_journal(path)
    assert reloaded == journal
    assert reloaded.current_revision_id() == proposal.revision_id


def test_stale_handoff_is_refused_under_a_new_revision() -> None:
    """§15.6: an old handoff cannot stay usable under changed targets."""

    from code2paper.agentic.research_revision_contract import (
        handoff_matches_revision,
    )
    from code2paper.agentic.research_terminal import build_candidate_handoff

    graph = _graph()
    constraints = build_author_constraint_set(graph)
    handoff = build_candidate_handoff(
        run_id="run-1",
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        agenda_items=(),
        promotion_records=(),
        revision_id="",
    )
    assert handoff.revision_id == ""

    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        author_constraint_digest=constraints.content_digest,
    )
    assessment = _assess(proposal, graph=graph)
    _enriched, journal, _failures = apply_revision(
        graph=graph, proposal=proposal, assessment=assessment
    )
    assert handoff_matches_revision(handoff, journal) is False

    current = build_candidate_handoff(
        run_id="run-1",
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        agenda_items=(),
        promotion_records=(),
        revision_id=journal.current_revision_id(),
    )
    assert handoff_matches_revision(current, journal) is True
    assert current.handoff_id != handoff.handoff_id
    assert current.content_digest != handoff.content_digest


def test_writer_preadmission_rejects_a_stale_revision_handoff(
    tmp_path, monkeypatch
) -> None:
    """The Writer refuses a handoff built under an older research revision.

    The companion-artifact revalidation is covered elsewhere; this test patches
    only the handoff loader so the revision-staleness check itself is exercised
    in the real pre-admission function.
    """

    import json

    from code2paper.agentic import publication_method_writer as writer_module
    from code2paper.agentic.publication_method_writer import (
        _writer_research_preadmission_failures,
    )
    from code2paper.agentic.research_revision_contract import (
        RevisionJournalEntryV1,
        RevisionJournalV1,
        write_revision_journal,
    )
    from code2paper.agentic.research_terminal import build_candidate_handoff

    handoff = build_candidate_handoff(
        run_id="run-1",
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        agenda_items=(),
        promotion_records=(),
        agenda_digest="sha256:agenda",
        promotion_ledger_digest="sha256:promotions",
        retry_ledger_digest="sha256:retries",
        revision_id="sha256:revision:0",
    )
    handoff_path = tmp_path / "candidate_handoff_v1.json"
    handoff_path.write_text(handoff.model_dump_json(), encoding="utf-8")
    journal = RevisionJournalV1(entries=(RevisionJournalEntryV1(
        revision_id="sha256:revision:1",
        proposal_id="proposal:1",
        parent_obligation_id="O-1",
        object_digests={"intent_obligation_graph_v2": "sha256:graph:1"},
        coverage_denominator_ids=("target-author",),
    ),))
    journal_path = write_revision_journal(tmp_path, journal)
    monkeypatch.setattr(
        writer_module,
        "_load_authenticated_candidate_handoff",
        lambda paths: (handoff, ()),
    )

    failures = _writer_research_preadmission_failures(
        artifact_paths={
            "candidate_handoff_v1": str(handoff_path),
            "research_revision_journal_v1": str(journal_path),
        },
        required=(),
    )
    assert any(
        failure.startswith("research_revision_handoff_stale:")
        for failure in failures
    ), failures

    # The current-revision handoff passes the same check.
    current = build_candidate_handoff(
        run_id="run-1",
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        agenda_items=(),
        promotion_records=(),
        agenda_digest="sha256:agenda",
        promotion_ledger_digest="sha256:promotions",
        retry_ledger_digest="sha256:retries",
        revision_id="sha256:revision:1",
    )
    current_path = tmp_path / "candidate_handoff_current.json"
    current_path.write_text(current.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        writer_module,
        "_load_authenticated_candidate_handoff",
        lambda paths: (current, ()),
    )
    current_failures = _writer_research_preadmission_failures(
        artifact_paths={
            "candidate_handoff_v1": str(current_path),
            "research_revision_journal_v1": str(journal_path),
        },
        required=(),
    )
    assert not any(
        failure.startswith("research_revision_handoff_stale:")
        for failure in current_failures
    ), current_failures


def test_provenance_is_bound_by_the_target_identity_digest() -> None:
    """R10 §15.6: a provenance change is detectable without breaking legacy ids.

    ``content_digest`` keeps the pre-R10 identity (frozen artifacts stay
    comparable); provenance is covered by ``target_identity_digest``, which the
    revision journal binds, so a flip from inferred to author authority cannot
    hide behind an unchanged content digest.
    """

    graph = _graph()
    targets = [
        target
        for obligation in graph.obligations
        for target in obligation.typed_behavior_targets
    ]
    flipped_targets = tuple(
        target.model_copy(update={"provenance": "author_explicit"})
        if target.provenance == "system_inferred"
        else target
        for target in targets
    )
    from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2

    flipped = IntentObligationGraphV2(
        project_goal=graph.project_goal,
        method_goal=graph.method_goal,
        obligations=[
            obligation.model_copy(update={
                "typed_behavior_targets": tuple(
                    target
                    for target in flipped_targets
                    if target.target_id in {
                        item.target_id
                        for item in obligation.typed_behavior_targets
                    }
                ),
            })
            for obligation in graph.obligations
        ],
    )
    assert flipped.content_digest == graph.content_digest
    assert flipped.target_identity_digest != graph.target_identity_digest


# ---------------------------------------------------------------------------
# §15.6 live application: revalidation, binding and resume
# ---------------------------------------------------------------------------


def _runtime():
    """A minimal ResearchGraphRuntime-like object over the fixture graph."""

    from types import SimpleNamespace

    graph = _graph()
    from code2paper.agentic.research_models import ResearchAgendaItemV1, ResearchAgendaV1

    def _item(obligation_id: str, *, status: str = "supported", claims=()):
        return ResearchAgendaItemV1(
            obligation_id=obligation_id,
            priority="must_cover",
            status=status,
            supported_claim_ids=list(claims),
            attempted_actions=["SEARCH_SYMBOLS"],
        )

    agenda = ResearchAgendaV1(
        run_id="run-1",
        repo_snapshot_id="repo:1",
        project_tree_hash="sha256:tree",
        intent_graph_digest=graph.content_digest,
        items=[
            _item("O-1", status="supported", claims=("claim:1",)),
            _item("O-2", status="pending"),
        ],
    )
    return SimpleNamespace(run_id="run-1", intent_graph=graph, agenda=agenda)


def test_revision_revalidates_coverage_and_claims() -> None:
    """§15.6: old support decisions are re-evaluated under the new targets."""

    from code2paper.agentic.research_revision_contract import (
        revise_research_targets,
    )

    runtime = _runtime()
    constraints = build_author_constraint_set(runtime.intent_graph)
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        author_constraint_digest=constraints.content_digest,
    )
    application = revise_research_targets(
        runtime=runtime,
        proposal=proposal,
        observed_ref_ids=("span:model.py:1:2",),
        fact_set=None,
        claim_set=({"claims": []},),
    )
    assert application.failures == ()
    assert application.assessment.verdict == "accepted"
    changed = {
        item.obligation_id: item for item in application.agenda.items
    }
    # The changed obligation lost its promoted claim and needs re-research.
    assert changed["O-1"].status == "in_progress"
    assert changed["O-1"].supported_claim_ids == []
    assert any(
        marker.startswith("revision_revalidation_required:O-1")
        for marker in changed["O-1"].missing_information
    )
    # An untouched sibling keeps its state.
    assert changed["O-2"].status == "pending"
    assert application.revalidation_rows
    row = application.revalidation_rows[0]
    assert row["obligation_id"] == "O-1"
    # The journal binds the changed graph, agenda and identity digests.
    entry = application.journal.entries[0]
    assert entry.object_digests["intent_target_identity"] == (
        application.graph.target_identity_digest
    )
    assert entry.object_digests["research_agenda_v1"] == (
        application.agenda.content_digest
    )
    # The coverage denominator is still the author boundary.
    assert set(application.assessment.coverage_denominator_ids) == {
        "target-author",
        "target-other",
    }


def test_revision_resume_binding_refuses_replay_and_drift() -> None:
    """§15.6: resume may not re-apply a revision or cross a revision boundary."""

    from code2paper.agentic.research_revision_contract import (
        bind_research_revision,
        revision_resume_failures,
        revise_research_targets,
    )

    runtime = _runtime()
    constraints = build_author_constraint_set(runtime.intent_graph)
    proposal = _proposal(
        after_targets=[
            RevisionTargetV1(
                target_id="target-inferred",
                desired_predicates=("COMPUTE",),
                replaces_target_ids=("target-inferred",),
            ),
        ],
        author_constraint_digest=constraints.content_digest,
    )
    application = revise_research_targets(
        runtime=runtime,
        proposal=proposal,
        observed_ref_ids=("span:model.py:1:2",),
    )
    assert application.failures == ()
    binding = bind_research_revision(
        journal=application.journal,
        graph=application.graph,
        agenda=application.agenda,
        coverage_denominator_ids=application.assessment.coverage_denominator_ids,
    )
    # A resume that tries to apply the same revision again is refused.
    replay = revision_resume_failures(
        binding=binding,
        journal=application.journal,
        revision_id=proposal.revision_id,
        graph=application.graph,
        agenda=application.agenda,
    )
    assert any(
        failure.startswith("revision_already_applied:") for failure in replay
    )
    # A checkpoint bound to an older revision cannot continue silently.
    stale = revision_resume_failures(
        binding=binding.model_copy(update={"revision_id": "sha256:older"}),
        journal=application.journal,
        graph=application.graph,
        agenda=application.agenda,
    )
    assert any(
        failure.startswith("revision_binding_stale:") for failure in stale
    )
    # Drift in the live objects is detected too.
    drifted = revision_resume_failures(
        binding=binding,
        journal=application.journal,
        graph=_graph(),
        agenda=application.agenda,
    )
    assert "revision_binding_intent_graph_mismatch" in drifted
    # The current revision resumes cleanly.
    assert revision_resume_failures(
        binding=binding,
        journal=application.journal,
        graph=application.graph,
        agenda=application.agenda,
    ) == ()


def test_checkpoint_binds_the_revision_and_resume_refuses_replay(tmp_path) -> None:
    """§15.6: the stage checkpoint carries the revision a resume must agree with."""

    import json
    from pathlib import Path

    from code2paper.agentic.autonomous_method_agent import (
        UserClaimsInputV1,
        build_product_research_runtime,
        load_research_stage_checkpoint,
        persist_research_stage_checkpoint,
        run_product_research_phase,
    )
    from code2paper.agentic.research_revision_contract import (
        bind_research_revision,
        revise_research_targets,
    )
    from code2paper.schemas import LLMConfig, LLMProvider

    fixture = Path(__file__).resolve().parent / "fixtures" / "research_loop_project"
    intent_fixture = (
        Path(__file__).resolve().parent / "fixtures"
        / "research_loop_project_author_markers.yaml"
    )
    runtime = build_product_research_runtime(
        repo_path=fixture,
        author_intent_path=intent_fixture,
        claims=None,
        run_id="revision-resume",
        llm_config=LLMConfig(provider=LLMProvider.NONE, model="none"),
        artifact_root=tmp_path / "artifacts" / "research_tool_data",
    )
    loop = run_product_research_phase(runtime, max_turns=2)
    graph = runtime.intent_graph
    assert graph is not None and graph.obligations
    obligation = graph.obligations[0]
    # The real compiler marks every author-derived target ``author_explicit``,
    # so a legitimate revision adds an inferred sub-question instead of
    # rewriting an author constraint.
    constraints = build_author_constraint_set(graph)
    proposal = RevisionProposalV1(
        proposal_id="proposal:checkpoint",
        parent_obligation_id=str(obligation.obligation_id),
        source_type="research_subquestion",
        subquestion_parent_id=str(obligation.obligation_id),
        before_target_ids=(),
        after_targets=(RevisionTargetV1(
            target_id="target-llm-subquestion",
            role="subquestion",
            desired_predicates=("COMPUTE",),
            provenance="research_subquestion",
        ),),
        observation_refs=("span:model.py:1:2",),
        reason="the inspected span shows an addition worth a sub-question",
        author_constraint_digest=constraints.content_digest,
    )
    application = revise_research_targets(
        runtime=runtime,
        proposal=proposal,
        observed_ref_ids=("span:model.py:1:2",),
    )
    assert application.assessment.verdict == "accepted", application.failures
    binding = bind_research_revision(
        journal=application.journal,
        graph=application.graph,
        agenda=application.agenda,
        coverage_denominator_ids=application.assessment.coverage_denominator_ids,
    )
    # The runtime adopts the revised graph/agenda for the checkpoint through
    # the production rebinding helper, so the agenda -> graph link names the
    # revised graph instead of the pre-revision one.
    from code2paper.agentic.research_revision_contract import (
        rebind_revision_in_place,
    )

    assert rebind_revision_in_place(
        runtime_intent_graph=runtime.intent_graph,
        runtime_agenda=runtime.agenda,
        revised_graph=application.graph,
        revised_agenda=application.agenda,
    ) == ()
    assert runtime.agenda.intent_graph_digest == application.graph.content_digest

    checkpoint = persist_research_stage_checkpoint(
        out_root=tmp_path,
        runtime=runtime,
        claims_input=UserClaimsInputV1(claims=[]),
        loop_result=loop,
        packet_set=None,
        fact_set=None,
        claim_set=None,
        revision_binding=binding,
    )
    payload = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
    assert payload["research_revision_binding_v1"]["revision_id"] == (
        proposal.revision_id
    )

    # A resume that already applied this revision is refused.
    from code2paper.agentic.research_revision_contract import (
        RevisionJournalEntryV1,
        RevisionJournalV1,
    )

    replay_journal = RevisionJournalV1(entries=(
        *application.journal.entries,
        RevisionJournalEntryV1(
            revision_id=proposal.revision_id,
            proposal_id="proposal:replay",
            parent_obligation_id=str(obligation.obligation_id),
            object_digests={},
        ),
    ))
    with pytest.raises(ValueError) as excinfo:
        load_research_stage_checkpoint(
            path=checkpoint, runtime=runtime, revision_journal=replay_journal
        )
    assert "research_stage_checkpoint_revision_stale" in str(excinfo.value)
    assert "revision_binding_journal_digest_mismatch" in str(excinfo.value)

    # A journal whose current revision is a *newer* one makes the checkpoint
    # stale rather than replayed.
    newer_journal = RevisionJournalV1(entries=(
        *application.journal.entries,
        RevisionJournalEntryV1(
            revision_id="sha256:newer-revision",
            parent_revision_id=proposal.revision_id,
            proposal_id="proposal:newer",
            parent_obligation_id=str(obligation.obligation_id),
            object_digests={},
        ),
    ))
    with pytest.raises(ValueError) as stale_excinfo:
        load_research_stage_checkpoint(
            path=checkpoint, runtime=runtime, revision_journal=newer_journal
        )
    assert "revision_binding_stale" in str(stale_excinfo.value)

    # The matching journal still loads.
    restored = load_research_stage_checkpoint(
        path=checkpoint,
        runtime=runtime,
        revision_journal=application.journal,
    )
    assert restored[0] is not None


def test_deterministic_producer_submits_the_same_proposal_shape() -> None:
    """§15.2: the producer only submits; the harness decides."""

    from code2paper.agentic.research_revision_contract import (
        build_revision_proposal,
        build_subquestion_target,
        revise_research_targets,
    )

    runtime = _runtime()
    constraints = build_author_constraint_set(runtime.intent_graph)
    target = build_subquestion_target(
        target_id="target-subquestion-1",
        predicates=("PROPAGATE",),
    )
    proposal = build_revision_proposal(
        proposal_id="proposal:producer",
        parent_obligation_id="O-1",
        new_target=target,
        source_type="research_subquestion",
        subquestion_parent_id="O-1",
        observation_refs=("span:model.py:1:2",),
        reason="an observed addition worth a sub-question",
        unresolved_impact=("normalization still unresolved",),
        budget_requests=1,
        author_constraint_digest=constraints.content_digest,
    )
    application = revise_research_targets(
        runtime=runtime,
        proposal=proposal,
        observed_ref_ids=("span:model.py:1:2",),
        remaining_budget=2,
    )
    assert application.assessment.verdict == "accepted", application.failures
    new_ids = {
        target.target_id
        for obligation in application.graph.obligations
        for target in obligation.typed_behavior_targets
    }
    assert "target-subquestion-1" in new_ids

    # An unobserved predicate cannot be invented by the producer.
    from code2paper.agentic.behavior_graph import BEHAVIOR_PREDICATES

    with pytest.raises(ValueError):
        build_subquestion_target(
            target_id="target-bad", predicates=("NOT_A_PREDICATE",)
        )

    class _Graph:
        nodes = ()

    with pytest.raises(ValueError) as excinfo:
        build_subquestion_target(
            target_id="target-bad2",
            predicates=(BEHAVIOR_PREDICATES[0],),
            evidence_graph=_Graph(),
        )
    assert "unobserved behavior predicates" in str(excinfo.value)
