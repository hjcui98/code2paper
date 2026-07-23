"""R6.4 tests for the R6.1 V3 authoring plan.

Verifies that ``authoring_plan_v3.py`` correctly:

- builds a section per obligation in topological (``precedes``) order;
- binds claims to sections via ``AtomicClaimV3.covers_obligation_ids``;
- binds explicit gaps to sections via the coverage report's
  ``matched_gap_ids``;
- enforces all seven R6.1 plan-gate rules;
- distinguishes ``is_trusted_ready`` (all supported), ``is_incomplete``
  (terminal but has explicit_gap/blocked must_cover), and gate failure
  (unresolved must_cover);
- never lets a hint / gap leak as a positive claim;
- authorizes equations against the claim's ``allowed_wording_boundary``.

The fixtures here are project-agnostic: they use only the generic V3
research-plane contracts.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from code2paper.agentic.authoring_plan_v3 import (
    AuthoringPlanV3,
    AuthoringSectionV3,
    authoring_plan_v3_brief,
    build_authoring_plan_v3,
    check_plan_gate,
    write_authoring_plan_v3,
)
from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    ExplicitCodeGapV1,
)
from code2paper.agentic.intent_compiler_v2 import (
    IntentObligationGraphV2,
    IntentObligationRelationV2,
    IntentObligationV2,
)
from code2paper.agentic.obligation_fact_alignment import (
    ObligationAlignmentV1,
    ObligationCoverageReportV2,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _target(target_id: str, *, predicates: tuple[str, ...] = ("COMPUTE",)) -> TypedBehaviorTargetV1:
    return TypedBehaviorTargetV1(
        target_id=target_id,
        role="role",
        desired_predicates=predicates,
    )


def _obligation(
    obligation_id: str,
    *,
    kind: str = "stage",
    priority: str = "must_cover",
    author_text: str = "do something",
    targets: tuple[TypedBehaviorTargetV1, ...] | None = None,
) -> IntentObligationV2:
    return IntentObligationV2(
        obligation_id=obligation_id,
        kind=kind,
        priority=priority,
        source_field="pipeline_steps",
        source_index=0,
        author_text=author_text,
        typed_behavior_targets=targets or (_target(obligation_id),),
    )


def _graph(
    obligations: list[IntentObligationV2],
    relations: list[IntentObligationRelationV2] | None = None,
) -> IntentObligationGraphV2:
    return IntentObligationGraphV2(
        schema_version="2.0",
        mode="intent-obligation-graph-v2",
        project_goal="goal",
        method_goal="method",
        implementation_scope="scope",
        obligations=obligations,
        relations=list(relations or []),
    )


def _claim(
    claim_id: str,
    *,
    covers_obligation_ids: list[str] | None = None,
    canonical_text: str = "claim text",
    allowed_wording_boundary: str = "boundary",
    status: str = "supported",
    direct_evidence_ids: list[str] | None = None,
    required_qualifiers: list[str] | None = None,
    canonical_identity: str = "ident",
) -> AtomicClaimV3:
    return AtomicClaimV3(
        claim_id=claim_id,
        canonical_text=canonical_text,
        claim_kind="implementation_behavior",
        fact_ids=["f1"],
        covers_obligation_ids=list(covers_obligation_ids or []),
        direct_evidence_ids=direct_evidence_ids or ["span-1"],
        relation_evidence_ids=[],
        required_qualifiers=list(required_qualifiers or []),
        unsupported_author_fragments=[],
        allowed_wording_boundary=allowed_wording_boundary,
        canonical_identity=canonical_identity,
        status=status,  # type: ignore[arg-type]
    )


def _claim_set(claims: list[AtomicClaimV3]) -> AtomicClaimSetV3:
    return AtomicClaimSetV3(
        schema_version="3.0",
        producer_version="test",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=claims,
        content_digest="sha256:set",
    )


def _coverage_item(
    obligation_id: str,
    *,
    kind: str = "stage",
    priority: str = "must_cover",
    coverage_status: str = "supported",
    matched_claim_ids: tuple[str, ...] = (),
    matched_gap_ids: tuple[str, ...] = (),
) -> ObligationAlignmentV1:
    return ObligationAlignmentV1(
        obligation_id=obligation_id,
        obligation_kind=kind,
        obligation_priority=priority,
        matched_claim_ids=matched_claim_ids,
        matched_gap_ids=matched_gap_ids,
        coverage_status=coverage_status,
        rationale="test",
    )


def _coverage_report(
    items: list[ObligationAlignmentV1],
    *,
    unresolved_must_cover_ids: list[str] | None = None,
) -> ObligationCoverageReportV2:
    must_cover_items = [i for i in items if i.obligation_priority == "must_cover"]
    return ObligationCoverageReportV2(
        schema_version="2.0",
        mode="obligation-coverage-v2",
        intent_graph_digest="sha256:graph",
        items=items,
        must_cover_count=len(must_cover_items),
        terminal_must_cover_count=sum(
            1 for i in must_cover_items
            if i.coverage_status in {"supported", "partial", "explicit_gap", "blocked"}
        ),
        supported_must_cover_count=sum(
            1 for i in must_cover_items if i.coverage_status == "supported"
        ),
        unresolved_must_cover_ids=list(
            unresolved_must_cover_ids
            if unresolved_must_cover_ids is not None
            else [
                i.obligation_id for i in must_cover_items
                if i.coverage_status == "unresolved"
            ]
        ),
        explicit_gap_count=sum(1 for i in items if i.coverage_status == "explicit_gap"),
    )


def _gap(gap_id: str, *, topic: str = "missing behavior") -> ExplicitCodeGapV1:
    return ExplicitCodeGapV1(
        gap_id=gap_id,
        topic=topic,
        status="not_implemented_in_repo",
        scope="any",
        rationale="not found",
        source_kind="author_obligation",
    )


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_build_plan_with_supported_must_cover_is_trusted_ready() -> None:
    """All must_cover supported -> plan gate passes, is_trusted_ready=True."""

    obligations = [
        _obligation("O-1", kind="method_mainline", author_text="Train a model."),
        _obligation("O-2", kind="stage", author_text="Compute training loss."),
    ]
    relations = [
        IntentObligationRelationV2(
            source_obligation_id="O-2",
            target_obligation_id="O-1",
            relation="supports",
        ),
    ]
    graph = _graph(obligations, relations)
    claims = [
        _claim("C-1", covers_obligation_ids=["O-1"], canonical_text="Mainline claim."),
        _claim("C-2", covers_obligation_ids=["O-2"], canonical_text="Stage claim."),
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item("O-1", kind="method_mainline", coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage", coverage_status="supported", matched_claim_ids=("C-2",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        method_name="Test Method",
        author_goal="Train a model.",
    )

    assert plan.plan_gate_passed
    assert plan.is_trusted_ready
    assert not plan.is_incomplete
    assert len(plan.sections) == 2
    # Method mainline should appear first (declared first, no precedes chain).
    assert plan.sections[0].obligation_id == "O-1"
    assert plan.sections[1].obligation_id == "O-2"
    assert plan.sections[0].claim_ids == ("C-1",)
    assert plan.sections[1].claim_ids == ("C-2",)
    assert plan.excluded_claim_ids == []
    assert plan.content_digest.startswith("sha256:")
    assert "authoring_plan_ready_for_evidence_constrained_method_writing" in plan.recommended_actions


def test_build_plan_with_explicit_gap_must_cover_is_incomplete() -> None:
    """A terminal explicit_gap must_cover makes the plan safely incomplete."""

    obligations = [
        _obligation("O-1", kind="method_mainline", author_text="Train a model."),
        _obligation("O-2", kind="stage", author_text="Compute loss."),
    ]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing loss")]
    claim_set = _claim_set([
        _claim("C-1", covers_obligation_ids=["O-1"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="method_mainline", coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item(
            "O-2",
            kind="stage",
            coverage_status="explicit_gap",
            matched_gap_ids=("G-1",),
        ),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )

    # Gate still passes: explicit_gap is terminal.
    assert plan.plan_gate_passed
    # Plan is incomplete (safe to emit) but not trusted ready.
    assert plan.is_incomplete
    assert not plan.is_trusted_ready
    gap_section = next(s for s in plan.sections if s.obligation_id == "O-2")
    assert gap_section.coverage_status == "explicit_gap"
    assert gap_section.gap_ids == ("G-1",)
    assert gap_section.caveat_required
    assert gap_section.claim_ids == ()
    assert "emit_method_as_incomplete_with_explicit_gaps" in plan.recommended_actions


def test_build_plan_with_unresolved_must_cover_fails_gate() -> None:
    """Unresolved must_cover obligations fail the plan gate."""

    obligations = [
        _obligation("O-1", kind="method_mainline", author_text="Train a model."),
        _obligation("O-2", kind="stage", author_text="Compute loss."),
    ]
    graph = _graph(obligations)
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="method_mainline", coverage_status="supported"),
        _coverage_item("O-2", kind="stage", coverage_status="unresolved"),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert not plan.plan_gate_passed
    assert not plan.is_trusted_ready
    assert not plan.is_incomplete
    assert any(f.startswith("unresolved_must_cover:O-2") for f in plan.gate_failures)
    assert any("O-1" not in f for f in plan.gate_failures)
    assert "return_to_research_loop_for_unresolved_must_cover" in plan.recommended_actions


# ---------------------------------------------------------------------------
# Topological order
# ---------------------------------------------------------------------------


def test_topological_order_respects_precedes_relations() -> None:
    """Sections are ordered so a predecessor stage appears before its successor."""

    obligations = [
        _obligation("O-mainline", kind="method_mainline", author_text="Train a model."),
        _obligation("O-stage-1", kind="stage", author_text="Step one."),
        _obligation("O-stage-2", kind="stage", author_text="Step two."),
        _obligation("O-stage-3", kind="stage", author_text="Step three."),
    ]
    # stage-1 precedes stage-2 precedes stage-3 precedes mainline.
    relations = [
        IntentObligationRelationV2(
            source_obligation_id="O-stage-1",
            target_obligation_id="O-stage-2",
            relation="precedes",
        ),
        IntentObligationRelationV2(
            source_obligation_id="O-stage-2",
            target_obligation_id="O-stage-3",
            relation="precedes",
        ),
        IntentObligationRelationV2(
            source_obligation_id="O-stage-3",
            target_obligation_id="O-mainline",
            relation="precedes",
        ),
    ]
    graph = _graph(obligations, relations)
    claims = [
        _claim(f"C-{oid}", covers_obligation_ids=[oid])
        for oid in ("O-stage-1", "O-stage-2", "O-stage-3", "O-mainline")
    ]
    claim_set = _claim_set(claims)
    coverage = _coverage_report([
        _coverage_item(oid, kind="stage" if "stage" in oid else "method_mainline",
                       coverage_status="supported", matched_claim_ids=(f"C-{oid}",))
        for oid in ("O-stage-1", "O-stage-2", "O-stage-3", "O-mainline")
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    order = [s.obligation_id for s in plan.sections]
    assert order == ["O-stage-1", "O-stage-2", "O-stage-3", "O-mainline"]
    assert plan.plan_gate_passed


def test_order_violation_failure_when_sections_out_of_order() -> None:
    """Constructing sections in reverse order triggers an order_violation failure.

    We build the sections manually and run ``check_plan_gate`` directly so
    we can inject an out-of-order arrangement without going through the
    topological builder (which always produces a valid order).
    """

    obligations = [
        _obligation("O-1", kind="stage", author_text="First stage."),
        _obligation("O-2", kind="stage", author_text="Second stage."),
    ]
    relations = [
        IntentObligationRelationV2(
            source_obligation_id="O-1",
            target_obligation_id="O-2",
            relation="precedes",
        ),
    ]
    graph = _graph(obligations, relations)
    claim_set = _claim_set([
        _claim("C-1", covers_obligation_ids=["O-1"]),
        _claim("C-2", covers_obligation_ids=["O-2"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported", matched_claim_ids=("C-1",)),
        _coverage_item("O-2", kind="stage", coverage_status="supported", matched_claim_ids=("C-2",)),
    ])

    # Manually build sections in REVERSED order so O-2 appears before O-1.
    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="Second stage",
            purpose="Second stage.",
            obligation_id="O-2",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
            claim_ids=("C-2",),
            evidence_ids=("span-1",),
            writing_instructions=("Write only the listed evidence.",),
        ),
        AuthoringSectionV3(
            section_id="AP-S2",
            heading="First stage",
            purpose="First stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
            claim_ids=("C-1",),
            evidence_ids=("span-1",),
            writing_instructions=("Write only the listed evidence.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[],
        intent_graph=graph,
    )

    assert not passed
    assert any(f.startswith("order_violation:O-1->O-2") for f in failures)


# ---------------------------------------------------------------------------
# Duplicate claim rule
# ---------------------------------------------------------------------------


def test_duplicate_claim_across_sections_fails_gate() -> None:
    """A claim appearing in two sections is a duplicate and fails the gate."""

    obligations = [
        _obligation("O-1", kind="stage", author_text="First stage."),
        _obligation("O-2", kind="stage", author_text="Second stage."),
    ]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim("C-shared", covers_obligation_ids=["O-1", "O-2"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-shared",)),
        _coverage_item("O-2", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-shared",)),
    ])

    # Build sections manually so both reference the same claim id.
    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="First stage",
            purpose="First stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
            claim_ids=("C-shared",),
            evidence_ids=("span-1",),
            writing_instructions=("Write only the listed evidence.",),
        ),
        AuthoringSectionV3(
            section_id="AP-S2",
            heading="Second stage",
            purpose="Second stage.",
            obligation_id="O-2",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
            claim_ids=("C-shared",),
            evidence_ids=("span-1",),
            writing_instructions=("Write only the listed evidence.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[],
        intent_graph=graph,
    )

    assert not passed
    assert any(f.startswith("duplicate_claim:C-shared") for f in failures)


def test_build_plan_deduplicates_claims_across_sections() -> None:
    """``build_authoring_plan_v3`` only binds a shared claim to the first section."""

    obligations = [
        _obligation("O-1", kind="stage", author_text="First stage."),
        _obligation("O-2", kind="stage", author_text="Second stage."),
    ]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim("C-shared", covers_obligation_ids=["O-1", "O-2"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-shared",)),
        _coverage_item("O-2", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-shared",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    # The build path binds C-shared to the first section only.  The redundant
    # second obligation is coalesced instead of manufacturing an empty Method
    # section, while its coverage remains present in the coverage report.
    sections_by_obligation = {s.obligation_id: s for s in plan.sections}
    assert sections_by_obligation["O-1"].claim_ids == ("C-shared",)
    assert "O-2" not in sections_by_obligation
    assert not any(f.startswith("duplicate_claim:") for f in plan.gate_failures)
    assert not any(
        f.startswith("section_without_claim_or_gap:")
        for f in plan.gate_failures
    )
    assert plan.plan_gate_passed


# ---------------------------------------------------------------------------
# Hint/gap leakage rules
# ---------------------------------------------------------------------------


def test_gap_section_not_caveated_fails_gate() -> None:
    """A gap-bound section without caveat_required fails the gate."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="explicit_gap",
                       matched_gap_ids=("G-1",)),
    ])

    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="Stage",
            purpose="Stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="explicit_gap",
            gap_ids=("G-1",),
            caveat_required=False,  # Wrong: should be True.
            writing_instructions=("Record the gap.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[_gap("G-1")],
        intent_graph=graph,
    )

    assert not passed
    assert any(f.startswith("gap_section_not_caveated:") for f in failures)


def test_explicit_gap_section_with_positive_claims_fails_gate() -> None:
    """An explicit_gap section with positive claims fails the gate."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim("C-leak", covers_obligation_ids=["O-1"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="explicit_gap",
                       matched_claim_ids=("C-leak",), matched_gap_ids=("G-1",)),
    ])

    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="Stage",
            purpose="Stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="explicit_gap",
            claim_ids=("C-leak",),  # Leak: positive claim on a gap section.
            gap_ids=("G-1",),
            caveat_required=True,
            writing_instructions=("Record the gap.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[_gap("G-1")],
        intent_graph=graph,
    )

    assert not passed
    assert any(
        f.startswith("explicit_gap_section_has_positive_claims:") for f in failures
    )


def test_unknown_gap_id_fails_gate() -> None:
    """A section referencing a gap id not in the explicit_gaps list fails."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="explicit_gap",
                       matched_gap_ids=("G-1",)),
    ])

    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="Stage",
            purpose="Stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="explicit_gap",
            gap_ids=("G-missing",),
            caveat_required=True,
            writing_instructions=("Record the gap.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[_gap("G-1")],
        intent_graph=graph,
    )

    assert not passed
    assert any(f.startswith("unknown_gap_id:G-missing:") for f in failures)


# ---------------------------------------------------------------------------
# Stage intro rule
# ---------------------------------------------------------------------------


def test_stage_intro_without_claim_or_gap_fails_gate() -> None:
    """A stage section with no claim and no gap fails the stage intro rule."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="unresolved"),
    ])

    sections = [
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="Stage",
            purpose="Stage.",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="unresolved",
            writing_instructions=("Empty.",),
        ),
    ]

    passed, failures = check_plan_gate(
        sections=sections,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=[],
        intent_graph=graph,
    )

    assert not passed
    assert any(
        f.startswith("stage_intro_missing_claim_or_gap:") for f in failures
    )
    # The general "section_without_claim_or_gap" rule also fires.
    assert any(
        f.startswith("section_without_claim_or_gap:") for f in failures
    )


# ---------------------------------------------------------------------------
# Equation authorization rule
# ---------------------------------------------------------------------------


def test_unauthorized_equation_in_claim_text_fails_gate() -> None:
    """A claim with an equation token not in its boundary fails the gate."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim(
            "C-eq",
            covers_obligation_ids=["O-1"],
            canonical_text="The loss is $L = x + y$ for the model.",
            allowed_wording_boundary="loss model",  # Does NOT contain the equation.
        ),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-eq",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert not plan.plan_gate_passed
    assert any(
        f.startswith("equation_unauthorized:C-eq:") for f in plan.gate_failures
    )


def test_authorized_equation_passes_gate() -> None:
    """A claim whose equation appears in the boundary (or boundary says formula) passes."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim(
            "C-eq",
            covers_obligation_ids=["O-1"],
            canonical_text="The loss is $L = x + y$ for the model.",
            allowed_wording_boundary="formula allowed",  # Permits any formula.
        ),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-eq",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert plan.plan_gate_passed
    assert plan.is_trusted_ready


def test_python_kwargs_not_flagged_as_equation() -> None:
    """Python kwargs like ``prompt=prompt`` must NOT be flagged as equations."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim(
            "C-kwarg",
            covers_obligation_ids=["O-1"],
            canonical_text=(
                "The forward pass calls engine(prompt=prompt, "
                "request_id=self, sampling_params=sampling_params) "
                "and returns the output."
            ),
            allowed_wording_boundary="exact behavior predicate and operands",
        ),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-kwarg",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert plan.plan_gate_passed
    assert not any(
        f.startswith("equation_unauthorized:") for f in plan.gate_failures
    )


def test_mathematical_equation_still_flagged() -> None:
    """Real equations with spaces around ``=`` are still detected."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim(
            "C-eq2",
            covers_obligation_ids=["O-1"],
            canonical_text="The loss = alpha * task_loss + lambda * reveal_loss.",
            allowed_wording_boundary="loss computation only",
        ),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-eq2",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert not plan.plan_gate_passed
    assert any(
        f.startswith("equation_unauthorized:C-eq2:") for f in plan.gate_failures
    )


# ---------------------------------------------------------------------------
# Excluded claims
# ---------------------------------------------------------------------------


def test_excluded_claims_are_listed() -> None:
    """Claims not bound to any obligation appear in ``excluded_claim_ids``."""

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim("C-bound", covers_obligation_ids=["O-1"]),
        _claim("C-orphan-1", covers_obligation_ids=[]),
        _claim("C-orphan-2", covers_obligation_ids=["O-nonexistent"]),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-bound",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    # Both orphan claims should be excluded (one has no obligation, the
    # other references an obligation that does not exist in the graph).
    assert "C-orphan-1" in plan.excluded_claim_ids
    assert "C-orphan-2" in plan.excluded_claim_ids
    assert "C-bound" not in plan.excluded_claim_ids
    assert plan.plan_gate_passed


# ---------------------------------------------------------------------------
# Brief and persistence
# ---------------------------------------------------------------------------


def test_brief_renders_gate_status_and_sections() -> None:
    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([_claim("C-1", covers_obligation_ids=["O-1"])])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    brief = authoring_plan_v3_brief(plan)
    assert "V3 evidence-bound Method writing plan:" in brief
    assert "Plan gate passed: True" in brief
    assert "Trusted ready: True" in brief
    assert "AP-S1" in brief
    assert "C-1" in brief


def test_write_and_load_plan_round_trip(tmp_path) -> None:
    import json
    from pathlib import Path

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([_claim("C-1", covers_obligation_ids=["O-1"])])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="supported",
                       matched_claim_ids=("C-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    output = write_authoring_plan_v3(str(tmp_path / "plan.json"), plan)
    data = json.loads(Path(output).read_text(encoding="utf-8"))
    assert data["schema_version"] == "3.0"
    assert data["plan_gate_passed"] is True
    assert data["is_trusted_ready"] is True
    assert len(data["sections"]) == 1
    assert data["sections"][0]["obligation_id"] == "O-1"


# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


def test_section_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuthoringSectionV3(
            section_id="AP-S1",
            heading="h",
            purpose="p",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
            surprise_field="not allowed",
        )


def test_plan_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AuthoringPlanV3(
            run_id="run-1",
            repo_snapshot_id="repo-1",
            project_tree_hash="tree-1",
            surprise_field="not allowed",
        )


def test_plan_validates_required_run_identifiers() -> None:
    with pytest.raises(ValidationError):
        AuthoringPlanV3(
            run_id="",
            repo_snapshot_id="repo-1",
            project_tree_hash="tree-1",
        )


def test_section_validates_nonempty_ids() -> None:
    with pytest.raises(ValidationError):
        AuthoringSectionV3(
            section_id="",
            heading="h",
            purpose="p",
            obligation_id="O-1",
            obligation_kind="stage",
            obligation_priority="must_cover",
            coverage_status="supported",
        )


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------


def test_recommended_actions_for_unresolved_must_cover() -> None:
    obligations = [
        _obligation("O-1", kind="stage", author_text="Stage 1."),
        _obligation("O-2", kind="stage", author_text="Stage 2."),
    ]
    graph = _graph(obligations)
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="unresolved"),
        _coverage_item("O-2", kind="stage", coverage_status="unresolved"),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert "return_to_research_loop_for_unresolved_must_cover" in plan.recommended_actions
    assert not plan.is_trusted_ready
    assert not plan.is_incomplete


def test_recommended_actions_for_incomplete_plan() -> None:
    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    gaps = [_gap("G-1", topic="missing")]
    claim_set = _claim_set([])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="explicit_gap",
                       matched_gap_ids=("G-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
        explicit_gaps=gaps,
    )

    assert plan.plan_gate_passed
    assert plan.is_incomplete
    assert "emit_method_as_incomplete_with_explicit_gaps" in plan.recommended_actions


# ---------------------------------------------------------------------------
# Partial coverage
# ---------------------------------------------------------------------------


def test_partial_coverage_section_is_caveat_required() -> None:
    """A partial must_cover obligation produces a caveat_required section.

    The plan is still trusted ready: partial is terminal and supported
    enough to emit, but every partial section must carry a caveat.
    """

    obligations = [_obligation("O-1", kind="stage", author_text="Stage.")]
    graph = _graph(obligations)
    claim_set = _claim_set([
        _claim(
            "C-1",
            covers_obligation_ids=["O-1"],
            required_qualifiers=["only describe the implemented fragment"],
        ),
    ])
    coverage = _coverage_report([
        _coverage_item("O-1", kind="stage", coverage_status="partial",
                       matched_claim_ids=("C-1",)),
    ])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert plan.plan_gate_passed
    # Partial is terminal and not explicit_gap/blocked: trusted ready.
    assert plan.is_trusted_ready
    assert not plan.is_incomplete
    section = plan.sections[0]
    assert section.caveat_required
    assert section.coverage_status == "partial"
    assert "only describe the implemented fragment" in section.qualifier_template


# ---------------------------------------------------------------------------
# Empty graph
# ---------------------------------------------------------------------------


def test_empty_intent_graph_produces_empty_plan() -> None:
    graph = _graph([])
    claim_set = _claim_set([])
    coverage = _coverage_report([])

    plan = build_authoring_plan_v3(
        run_id="run-1",
        repo_snapshot_id="repo-1",
        project_tree_hash="tree-1",
        intent_graph=graph,
        coverage_report=coverage,
        claim_set=claim_set,
    )

    assert plan.sections == []
    assert plan.plan_gate_passed  # No obligations to violate.
    assert plan.is_trusted_ready  # No unresolved must_cover, no gaps.
    assert not plan.is_incomplete
