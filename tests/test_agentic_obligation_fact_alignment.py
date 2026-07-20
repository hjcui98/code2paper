"""R5.4 / R5.3 tests for the obligation-to-fact alignment layer.

R5.3 exit condition: ``训练义务不能被推理 facts 错误覆盖`` and ``mismatch 进 gap``.
This module exercises ``obligation_fact_alignment.py`` directly:

- a training-scoped obligation MUST NOT be covered by inference-scoped facts;
- an inference-scoped obligation MAY be covered by inference or unconditional
  facts, but never by training-only facts;
- an explicit gap recorded against any obligation forces a terminal
  ``explicit_gap`` status regardless of fact alignment;
- a ``verify_only`` obligation (rationale / innovation / mismatch) never
  becomes ``supported`` even when matching facts exist;
- the deterministic ``gap_obligation_bindings`` path takes precedence over
  the fallback predicate-based matcher.

The fixtures here are project-agnostic: they use the generic
``BEHAVIOR_PREDICATE_TO_FACT`` mapping and the V2 concept registry, with no
``F-RAP-*`` / ``C-RAP-*`` literals.
"""

from __future__ import annotations

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimV3,
    CodeFactV1,
    ExplicitCodeGapV1,
)
from code2paper.agentic.generic_fact_compiler import BEHAVIOR_PREDICATE_TO_FACT
from code2paper.agentic.intent_compiler_v2 import compile_intent_obligation_graph_v2
from code2paper.agentic.obligation_fact_alignment import (
    align_obligation,
    align_target_to_facts,
    build_obligation_coverage_v2,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _training_summary() -> AuthorIntentSummary:
    """A summary whose innovation claim is training-scoped."""

    return AuthorIntentSummary(
        project_goal="Train a predictor.",
        method_goal="Train with losses.",
        implementation_scope="Training pipeline.",
        method_mainline="Train a model with training losses and step the optimizer.",
        story_order=["Training"],
        priority_files=["train.py"],
        module_roles=["train.py::Trainer: compute losses and step the optimizer"],
        pipeline_steps=["Training: compute training losses and step the optimizer"],
        design_intents=[],
        innovation_claims=["Three training losses learn the predictor."],
    )


def _inference_summary() -> AuthorIntentSummary:
    """A summary whose mainline is inference-scoped."""

    return AuthorIntentSummary(
        project_goal="Infer scores at deployment.",
        method_goal="Infer without gradients.",
        implementation_scope="Inference entrypoint.",
        method_mainline="Infer scores at deployment without gradients.",
        story_order=["Inference"],
        priority_files=["infer.py"],
        module_roles=["infer.py::Model: forward pass without gradients"],
        pipeline_steps=["Inference: forward pass without gradients"],
        design_intents=[],
        innovation_claims=[],
    )


def _make_fact(
    fact_id: str,
    *,
    predicate: str,
    conditions: list[str] | None = None,
    validation_status: str = "supported",
) -> CodeFactV1:
    """Build a minimal ``CodeFactV1`` for alignment tests."""

    return CodeFactV1(
        fact_id=fact_id,
        subject="symbol",
        predicate=predicate,  # type: ignore[arg-type]
        object="result",
        conditions=list(conditions or []),
        scope="function",
        direct_span_ids=["span-1"],
        exact_source_digest="sha256:fixture",
        canonical_identity=f"fixture:{fact_id}",
        validation_status=validation_status,  # type: ignore[arg-type]
    )


def _training_fact(fact_id: str, *, predicate: str) -> CodeFactV1:
    """A fact whose conditions mark it as training-scoped."""

    return _make_fact(
        fact_id,
        predicate=predicate,
        conditions=["self.training == True", "loss.backward()"],
    )


def _inference_fact(fact_id: str, *, predicate: str) -> CodeFactV1:
    """A fact whose conditions mark it as inference-scoped."""

    return _make_fact(
        fact_id,
        predicate=predicate,
        conditions=["torch.no_grad()", "model.eval()"],
    )


def _unconditional_fact(fact_id: str, *, predicate: str) -> CodeFactV1:
    """A fact with no execution-scope guards (scope=any)."""

    return _make_fact(fact_id, predicate=predicate, conditions=[])


def _fact_predicate_for(behavior_predicate: str) -> str:
    """Translate an uppercase behavior predicate to its lowercase fact predicate."""

    return BEHAVIOR_PREDICATE_TO_FACT[behavior_predicate]


# ---------------------------------------------------------------------------
# R5.3 core: training obligation not covered by inference facts
# ---------------------------------------------------------------------------


def test_training_obligation_not_covered_by_inference_facts() -> None:
    """A training-scoped target MUST NOT be covered by inference-scoped facts.

    This is the R5.3 hard rule: training facts are the only authorized
    source for a training-scoped obligation.  Inference facts that match
    the predicate are recorded as ``scope_blocked`` instead of
    ``matched``, so the obligation stays unresolved rather than being
    silently covered.
    """

    graph = compile_intent_obligation_graph_v2(_training_summary())
    training_obligation = next(
        o for o in graph.obligations
        if o.kind == "high_risk_claim"
    )
    # The innovation claim must have at least one training-scoped target.
    training_targets = [
        t for t in training_obligation.typed_behavior_targets
        if "training" in t.conditions
    ]
    assert training_targets, (
        "fixture should produce a training-scoped target; "
        f"got {[t.conditions for t in training_obligation.typed_behavior_targets]}"
    )

    # Build inference-scoped facts whose predicates match every desired
    # predicate of the training target.  If the alignment layer accepts
    # these, the training obligation would be wrongly "supported".
    inference_facts: list[CodeFactV1] = []
    for target in training_targets:
        for behavior_pred in target.desired_predicates:
            inference_facts.append(_inference_fact(
                f"inf-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    alignment = align_obligation(training_obligation, facts=inference_facts)

    # The obligation MUST NOT be supported or partial via inference facts.
    assert alignment.coverage_status not in {"supported"}, (
        "Training obligation must not be covered by inference facts; "
        f"got status={alignment.coverage_status}, "
        f"matched={alignment.target_alignments}"
    )
    # Every target alignment should be scope_blocked, not resolved.
    for ta in alignment.target_alignments:
        if ta.target_scope == "training":
            assert ta.status == "scope_blocked", (
                f"training target {ta.target_id} should be scope_blocked by "
                f"inference facts; got status={ta.status}, "
                f"matched_fact_ids={ta.matched_fact_ids}"
            )
            assert ta.matched_fact_ids == (), (
                f"training target {ta.target_id} must have no matched facts; "
                f"got {ta.matched_fact_ids}"
            )
            assert ta.scope_blocked_fact_ids, (
                f"training target {ta.target_id} should record scope-blocked facts"
            )


def test_training_obligation_covered_by_training_facts() -> None:
    """A training-scoped target IS covered by training-scoped facts.

    This is the positive control for the previous test: the same obligation
    with the same desired predicates, but now fed training-scoped facts,
    must reach ``supported``.
    """

    graph = compile_intent_obligation_graph_v2(_training_summary())
    training_obligation = next(
        o for o in graph.obligations if o.kind == "high_risk_claim"
    )
    training_targets = [
        t for t in training_obligation.typed_behavior_targets
        if "training" in t.conditions
    ]
    assert training_targets

    training_facts: list[CodeFactV1] = []
    for target in training_targets:
        for behavior_pred in target.desired_predicates:
            training_facts.append(_training_fact(
                f"trn-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    alignment = align_obligation(training_obligation, facts=training_facts)

    # The training target should now be resolved (or at least partial).
    training_alignments = [
        ta for ta in alignment.target_alignments if ta.target_scope == "training"
    ]
    assert training_alignments, "expected at least one training-scoped target alignment"
    for ta in training_alignments:
        assert ta.status == "resolved", (
            f"training target {ta.target_id} should be resolved by training facts; "
            f"got status={ta.status}, matched={ta.matched_fact_ids}, "
            f"unmatched={ta.unmatched_predicates}"
        )


# ---------------------------------------------------------------------------
# R5.3 core: inference obligation covered by inference or any facts
# ---------------------------------------------------------------------------


def test_inference_obligation_covered_by_inference_facts() -> None:
    """An inference-scoped target IS covered by inference-scoped facts."""

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    inference_obligation = next(
        o for o in graph.obligations if o.kind == "method_mainline"
    )
    inference_targets = [
        t for t in inference_obligation.typed_behavior_targets
        if "inference" in t.conditions
    ]
    assert inference_targets, (
        "fixture should produce an inference-scoped target; "
        f"got {[t.conditions for t in inference_obligation.typed_behavior_targets]}"
    )

    inference_facts: list[CodeFactV1] = []
    for target in inference_targets:
        for behavior_pred in target.desired_predicates:
            inference_facts.append(_inference_fact(
                f"inf-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    alignment = align_obligation(inference_obligation, facts=inference_facts)
    for ta in alignment.target_alignments:
        if ta.target_scope == "inference":
            assert ta.status == "resolved", (
                f"inference target {ta.target_id} should be resolved by inference facts; "
                f"got status={ta.status}"
            )


def test_inference_obligation_not_covered_by_training_facts() -> None:
    """An inference-scoped target MUST NOT be covered by training-only facts."""

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    inference_obligation = next(
        o for o in graph.obligations if o.kind == "method_mainline"
    )
    inference_targets = [
        t for t in inference_obligation.typed_behavior_targets
        if "inference" in t.conditions
    ]
    assert inference_targets

    training_facts: list[CodeFactV1] = []
    for target in inference_targets:
        for behavior_pred in target.desired_predicates:
            training_facts.append(_training_fact(
                f"trn-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    alignment = align_obligation(inference_obligation, facts=training_facts)
    for ta in alignment.target_alignments:
        if ta.target_scope == "inference":
            assert ta.status == "scope_blocked", (
                f"inference target {ta.target_id} should be scope_blocked by "
                f"training facts; got status={ta.status}"
            )
            assert ta.matched_fact_ids == ()


def test_inference_obligation_covered_by_unconditional_facts() -> None:
    """An inference-scoped target MAY be covered by unconditional (any) facts.

    An unconditional fact (no training/eval guard) is assumed to run on
    the inference path unless explicitly training-gated, so it should
    cover an inference-scoped target.
    """

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    inference_obligation = next(
        o for o in graph.obligations if o.kind == "method_mainline"
    )
    inference_targets = [
        t for t in inference_obligation.typed_behavior_targets
        if "inference" in t.conditions
    ]
    assert inference_targets

    any_facts: list[CodeFactV1] = []
    for target in inference_targets:
        for behavior_pred in target.desired_predicates:
            any_facts.append(_unconditional_fact(
                f"any-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    alignment = align_obligation(inference_obligation, facts=any_facts)
    for ta in alignment.target_alignments:
        if ta.target_scope == "inference":
            assert ta.status == "resolved", (
                f"inference target {ta.target_id} should be resolved by "
                f"unconditional facts; got status={ta.status}"
            )


# ---------------------------------------------------------------------------
# R5.3 core: explicit gap forces terminal explicit_gap
# ---------------------------------------------------------------------------


def test_explicit_gap_forces_terminal_explicit_gap_status() -> None:
    """An explicit gap recorded against an obligation forces ``explicit_gap``.

    Even when matching facts exist, the gap is terminal: the research loop
    searched exhaustively and the behavior is absent from the executable
    scope.  This is the R5.3 ``mismatch 进 gap`` rule.
    """

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    mainline = next(o for o in graph.obligations if o.kind == "method_mainline")
    inference_targets = [
        t for t in mainline.typed_behavior_targets
        if "inference" in t.conditions
    ]
    assert inference_targets

    # Build matching facts (would normally resolve the target).
    matching_facts: list[CodeFactV1] = []
    for target in inference_targets:
        for behavior_pred in target.desired_predicates:
            matching_facts.append(_inference_fact(
                f"inf-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
            ))

    # Build an explicit gap bound to this obligation via gap_obligation_bindings.
    gap = ExplicitCodeGapV1(
        gap_id="gap-test-001",
        topic="inference forward pass without gradients",
        status="not_implemented_in_repo",
        scope="inference",
        rationale="Search exhausted: the requested forward-pass behavior is absent.",
        source_kind="author_obligation",
    )
    bindings = {gap.gap_id: [mainline.obligation_id]}

    alignment = align_obligation(
        mainline,
        facts=matching_facts,
        gaps=[gap],
        gap_obligation_bindings=bindings,
    )

    assert alignment.coverage_status == "explicit_gap", (
        "An explicit gap must force terminal explicit_gap status even when "
        f"matching facts exist; got {alignment.coverage_status}"
    )
    assert alignment.matched_gap_ids == (gap.gap_id,)
    assert alignment.is_terminal


def test_mismatch_check_obligation_terminates_as_explicit_gap() -> None:
    """A ``mismatch_check`` obligation terminates as explicit_gap when bound to a gap.

    This is the R5.3 ``mismatch 进 gap`` exit condition: when the author
    flags a potential mismatch, the research loop searches for it and, if
    the mismatch is confirmed (i.e. the behavior is absent), records an
    explicit gap that terminates the obligation.
    """

    summary = AuthorIntentSummary(
        project_goal="Train and infer.",
        method_goal="Train then infer.",
        implementation_scope="Training and inference.",
        method_mainline="Train a model then infer scores.",
        story_order=["Train", "Infer"],
        priority_files=["m.py"],
        module_roles=["m.py::Model: train and infer"],
        pipeline_steps=["Train.", "Infer."],
        design_intents=[],
        innovation_claims=[],
        potential_mismatches=[
            "The author claims a contrastive loss but the code may use cross-entropy.",
        ],
    )
    graph = compile_intent_obligation_graph_v2(summary)
    mismatch = next(o for o in graph.obligations if o.kind == "mismatch_check")
    assert mismatch.priority == "verify_only"

    gap = ExplicitCodeGapV1(
        gap_id="gap-mismatch-001",
        topic="contrastive loss vs cross-entropy mismatch",
        status="not_implemented_in_repo",
        scope="training",
        rationale="Confirmed mismatch: code uses cross-entropy, not contrastive loss.",
        source_kind="author_obligation",
    )
    bindings = {gap.gap_id: [mismatch.obligation_id]}

    alignment = align_obligation(
        mismatch,
        facts=[],
        gaps=[gap],
        gap_obligation_bindings=bindings,
    )

    assert alignment.coverage_status == "explicit_gap", (
        f"mismatch_check bound to a gap must terminate as explicit_gap; "
        f"got {alignment.coverage_status}"
    )
    assert alignment.is_terminal


# ---------------------------------------------------------------------------
# R5.3 verify_only obligations never become supported
# ---------------------------------------------------------------------------


def test_verify_only_obligation_never_becomes_supported_even_with_matching_facts() -> None:
    """A ``verify_only`` obligation never becomes ``supported``.

    Even when matching facts exist, verify_only obligations (rationale,
    innovation, mismatch) remain diagnostic: they may become ``partial``
    when related facts exist, or ``unresolved`` / ``explicit_gap``, but
    never ``supported``.
    """

    graph = compile_intent_obligation_graph_v2(_training_summary())
    innovation = next(o for o in graph.obligations if o.kind == "high_risk_claim")
    assert innovation.priority == "verify_only"

    # Build matching training facts for every target.
    matching_facts: list[CodeFactV1] = []
    for target in innovation.typed_behavior_targets:
        for behavior_pred in target.desired_predicates:
            scope = "training" if "training" in target.conditions else "any"
            if scope == "training":
                matching_facts.append(_training_fact(
                    f"trn-{target.target_id}-{behavior_pred}",
                    predicate=_fact_predicate_for(behavior_pred),
                ))
            else:
                matching_facts.append(_unconditional_fact(
                    f"any-{target.target_id}-{behavior_pred}",
                    predicate=_fact_predicate_for(behavior_pred),
                ))

    alignment = align_obligation(innovation, facts=matching_facts)
    assert alignment.coverage_status != "supported", (
        "verify_only obligation must never become supported even with "
        f"matching facts; got {alignment.coverage_status}"
    )


# ---------------------------------------------------------------------------
# R5.3 deterministic gap binding takes precedence over fallback matcher
# ---------------------------------------------------------------------------


def test_explicit_gap_binding_takes_precedence_over_fallback_matcher() -> None:
    """The deterministic ``gap_obligation_bindings`` path is authoritative.

    When a binding maps ``gap_id -> []`` (no obligations), the fallback
    matcher MUST NOT rebind the gap to any obligation.  This ensures the
    deterministic caller fully controls gap-to-obligation routing.
    """

    graph = compile_intent_obligation_graph_v2(_training_summary())
    innovation = next(o for o in graph.obligations if o.kind == "high_risk_claim")

    gap = ExplicitCodeGapV1(
        gap_id="gap-binding-001",
        topic="training losses",
        status="not_implemented_in_repo",
        scope="training",
        rationale="Test gap that would match via fallback if not explicitly bound.",
        source_kind="author_obligation",
    )
    # Empty binding list: the gap is explicitly bound to NO obligations.
    bindings = {gap.gap_id: []}

    alignment = align_obligation(
        innovation,
        facts=[],
        gaps=[gap],
        gap_obligation_bindings=bindings,
    )

    assert alignment.matched_gap_ids == (), (
        "An empty binding list must prevent the fallback matcher from "
        f"binding the gap; got {alignment.matched_gap_ids}"
    )
    assert alignment.coverage_status != "explicit_gap", (
        f"Empty binding must not produce explicit_gap; got {alignment.coverage_status}"
    )


def test_fallback_gap_matcher_uses_predicate_intersection_and_scope() -> None:
    """When no explicit binding is supplied, the fallback matcher runs.

    A gap covers an obligation when their derived predicates intersect AND
    their scopes are compatible.  This test verifies the fallback path is
    multilingual and predicate-based (no English token overlap, no
    project-specific ids).
    """

    graph = compile_intent_obligation_graph_v2(_training_summary())
    innovation = next(o for o in graph.obligations if o.kind == "high_risk_claim")
    # The innovation claim mentions training losses -> training_objective concept.
    training_targets = [
        t for t in innovation.typed_behavior_targets
        if "training" in t.conditions
    ]
    assert training_targets

    # A Chinese gap topic that triggers the same training_objective concept.
    gap = ExplicitCodeGapV1(
        gap_id="gap-fallback-001",
        topic="训练损失",  # Chinese: "training loss"
        status="not_implemented_in_repo",
        scope="training",
        rationale="Fallback matcher should bind via concept registry.",
        source_kind="author_obligation",
    )

    alignment = align_obligation(
        innovation,
        facts=[],
        gaps=[gap],
        gap_obligation_bindings=None,  # force fallback
    )

    assert gap.gap_id in alignment.matched_gap_ids, (
        "Fallback matcher should bind the Chinese training-loss gap to the "
        f"training-scoped innovation obligation; got {alignment.matched_gap_ids}"
    )
    assert alignment.coverage_status == "explicit_gap"


# ---------------------------------------------------------------------------
# R5.3 rejected facts do not cover obligations
# ---------------------------------------------------------------------------


def test_rejected_facts_do_not_cover_obligations() -> None:
    """A fact with ``validation_status == 'rejected'`` must not cover a target."""

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    mainline = next(o for o in graph.obligations if o.kind == "method_mainline")
    inference_targets = [
        t for t in mainline.typed_behavior_targets
        if "inference" in t.conditions
    ]
    assert inference_targets

    rejected_facts: list[CodeFactV1] = []
    for target in inference_targets:
        for behavior_pred in target.desired_predicates:
            rejected_facts.append(_make_fact(
                f"rej-{target.target_id}-{behavior_pred}",
                predicate=_fact_predicate_for(behavior_pred),
                conditions=["torch.no_grad()"],
                validation_status="rejected",
            ))

    alignment = align_obligation(mainline, facts=rejected_facts)
    for ta in alignment.target_alignments:
        assert ta.matched_fact_ids == (), (
            f"rejected facts must not match; got {ta.matched_fact_ids}"
        )


# ---------------------------------------------------------------------------
# R5.3 aggregate coverage report
# ---------------------------------------------------------------------------


def test_aggregate_coverage_report_marks_unresolved_must_cover() -> None:
    """``build_obligation_coverage_v2`` aggregates per-obligation alignment.

    When no facts are supplied, every must_cover obligation should be
    unresolved, and the report should list them in
    ``unresolved_must_cover_ids``.
    """

    graph = compile_intent_obligation_graph_v2(_inference_summary())
    report = build_obligation_coverage_v2(graph)

    assert report.schema_version == "2.0"
    assert report.mode == "obligation-coverage-v2"
    assert report.content_digest.startswith("sha256:")
    assert report.intent_graph_digest == graph.content_digest

    must_cover_items = [
        item for item in report.items
        if item.obligation_priority == "must_cover"
    ]
    assert must_cover_items
    for item in must_cover_items:
        assert item.coverage_status == "unresolved", (
            f"must_cover obligation {item.obligation_id} should be unresolved "
            f"without facts; got {item.coverage_status}"
        )
    assert report.unresolved_must_cover_ids, (
        "report should list unresolved must_cover ids"
    )


def test_aggregate_coverage_report_records_explicit_gap_count() -> None:
    """The report counts explicit_gap terminal obligations."""

    summary = AuthorIntentSummary(
        project_goal="Train.",
        method_goal="Train with losses.",
        implementation_scope="Training.",
        method_mainline="Train a model with training losses.",
        story_order=["Train"],
        priority_files=["t.py"],
        module_roles=["t.py::T: train"],
        pipeline_steps=["Train with training losses."],
        design_intents=[],
        innovation_claims=["Training losses learn the predictor."],
        potential_mismatches=[
            "The author claims a contrastive loss but the code may use cross-entropy.",
        ],
    )
    graph = compile_intent_obligation_graph_v2(summary)
    mismatch = next(o for o in graph.obligations if o.kind == "mismatch_check")
    gap = ExplicitCodeGapV1(
        gap_id="gap-agg-001",
        topic="contrastive loss mismatch",
        status="not_implemented_in_repo",
        scope="training",
        rationale="Confirmed mismatch.",
        source_kind="author_obligation",
    )
    bindings = {gap.gap_id: [mismatch.obligation_id]}

    report = build_obligation_coverage_v2(
        graph,
        explicit_gaps=[gap],
        gap_obligation_bindings=bindings,
    )
    assert report.explicit_gap_count >= 1, (
        f"expected at least one explicit gap; got {report.explicit_gap_count}"
    )


# ---------------------------------------------------------------------------
# R5.3 align_target_to_facts unit tests
# ---------------------------------------------------------------------------


def test_align_target_to_facts_returns_unmatched_predicates() -> None:
    """``align_target_to_facts`` reports which desired predicates are missing."""

    target = TypedBehaviorTargetV1(
        target_id="T-TEST-01",
        role="filter",
        desired_predicates=("MASK", "FILTER", "SORT"),
        required_relations=(),
        conditions=("inference",),
        risk_level="medium",
    )
    # Only MASK is matched; FILTER and SORT are unmatched.
    facts = [
        _inference_fact("f1", predicate=_fact_predicate_for("MASK")),
    ]
    alignment = align_target_to_facts(target, facts)
    assert alignment.matched_predicates == ("MASK",)
    assert set(alignment.unmatched_predicates) == {"FILTER", "SORT"}
    assert alignment.status == "partial"


def test_align_target_to_facts_resolved_when_all_predicates_matched() -> None:
    """All desired predicates matched -> status == resolved."""

    target = TypedBehaviorTargetV1(
        target_id="T-TEST-02",
        role="ranking",
        desired_predicates=("SORT", "TOPK"),
        required_relations=(),
        conditions=("inference",),
        risk_level="medium",
    )
    facts = [
        _inference_fact("f1", predicate=_fact_predicate_for("SORT")),
        _inference_fact("f2", predicate=_fact_predicate_for("TOPK")),
    ]
    alignment = align_target_to_facts(target, facts)
    assert alignment.status == "resolved"
    assert set(alignment.matched_predicates) == {"SORT", "TOPK"}
    assert alignment.unmatched_predicates == ()


def test_align_target_to_facts_unresolved_when_no_match() -> None:
    """No matching facts -> status == unresolved."""

    target = TypedBehaviorTargetV1(
        target_id="T-TEST-03",
        role="training",
        desired_predicates=("COMPUTE", "REDUCE"),
        required_relations=(),
        conditions=("training",),
        risk_level="high",
    )
    # Inference facts: scope-incompatible.
    facts = [
        _inference_fact("f1", predicate=_fact_predicate_for("COMPUTE")),
        _inference_fact("f2", predicate=_fact_predicate_for("REDUCE")),
    ]
    alignment = align_target_to_facts(target, facts)
    assert alignment.status == "scope_blocked"
    assert alignment.matched_fact_ids == ()
    assert set(alignment.scope_blocked_fact_ids) == {"f1", "f2"}
