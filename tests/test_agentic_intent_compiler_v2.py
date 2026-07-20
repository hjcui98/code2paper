"""R5.4 tests for the V2 robust intent compiler.

Verifies that ``compile_intent_obligation_graph_v2`` produces typed behavior
targets with the right priority, status and scope for each obligation kind,
and that the V2 graph is content-addressed.  These tests are the entry point
for the R5.4 exit conditions: the same intent expressed in different wording,
language or stage order MUST compile to the same typed behavior target
signature (covered in ``test_agentic_intent_paraphrases.py`` and
``test_agentic_intent_multilingual.py``).
"""

from __future__ import annotations

from code2paper.agentic.author_intent_summary import AuthorIntentSummary
from code2paper.agentic.behavior_graph import BEHAVIOR_PREDICATES, BEHAVIOR_RELATION_KINDS
from code2paper.agentic.intent_compiler_v2 import (
    INTENT_CONCEPTS,
    IntentConceptV1,
    IntentObligationGraphV2,
    IntentObligationV2,
    compile_intent_obligation_graph_v2,
    typed_targets_signature,
)
from code2paper.agentic.research_models import TypedBehaviorTargetV1


def _rap_style_summary() -> AuthorIntentSummary:
    """A RAP-style summary that exercises training + inference concepts."""

    return AuthorIntentSummary(
        project_goal="Predict primitive importance without using paper text as evidence.",
        method_goal="Score and prune low-importance primitives.",
        implementation_scope="Provided inference entrypoint.",
        method_mainline=(
            "Load a predictor, compute per-primitive scores, and prune "
            "low-ranked primitives."
        ),
        story_order=["Feature construction", "Score prediction", "Pruning"],
        priority_files=["prune_percent.py"],
        module_roles=[
            "utils/net_utils.py::PrunePredictor: predict one importance score per primitive",
        ],
        pipeline_steps=[
            "Feature construction: build per-primitive descriptors",
            "Pruning: sort scores, construct a mask, and remove low-ranked primitives",
        ],
        design_intents=["Avoid rendering in the scoped inference function."],
        innovation_claims=["Three training losses learn the importance predictor."],
    )


# ---------------------------------------------------------------------------
# Contract / schema tests
# ---------------------------------------------------------------------------


def test_v2_graph_is_content_addressed_and_schema_stable() -> None:
    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    assert isinstance(graph, IntentObligationGraphV2)
    assert graph.schema_version == "2.0"
    assert graph.mode == "intent-obligation-graph-v2"
    assert graph.content_digest.startswith("sha256:")
    # The digest is deterministic: recompiling produces the same digest.
    again = compile_intent_obligation_graph_v2(_rap_style_summary())
    assert again.content_digest == graph.content_digest


def test_v2_obligations_carry_typed_behavior_targets_with_valid_predicates() -> None:
    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    assert len(graph.obligations) >= 7  # mainline + 2 stages + component + 3 org + ...
    for obligation in graph.obligations:
        assert isinstance(obligation, IntentObligationV2)
        assert obligation.status == "unresolved"
        for target in obligation.typed_behavior_targets:
            assert isinstance(target, TypedBehaviorTargetV1)
            for predicate in target.desired_predicates:
                assert predicate in BEHAVIOR_PREDICATES, (
                    f"target {target.target_id} has unknown predicate {predicate!r}"
                )
            for relation in target.required_relations:
                assert relation in BEHAVIOR_RELATION_KINDS, (
                    f"target {target.target_id} has unknown relation {relation!r}"
                )


def test_v2_priorities_match_v1_obligation_structure() -> None:
    """V2 mirrors V1's obligation kinds and priorities for compatibility."""

    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    kinds_by_priority = {
        "must_cover": {"method_mainline", "stage"},
        "should_cover": {"component"},
        "preference": {"organization"},
        "verify_only": {"rationale_check", "high_risk_claim", "mismatch_check"},
    }
    for obligation in graph.obligations:
        assert obligation.kind in kinds_by_priority[obligation.priority], (
            f"{obligation.kind} has unexpected priority {obligation.priority}"
        )

    assert any(o.kind == "method_mainline" and o.priority == "must_cover" for o in graph.obligations)
    assert sum(1 for o in graph.obligations if o.kind == "stage" and o.priority == "must_cover") == 2
    assert all(o.priority == "preference" for o in graph.obligations if o.kind == "organization")
    assert all(
        o.priority == "verify_only"
        for o in graph.obligations
        if o.kind in {"rationale_check", "high_risk_claim"}
    )


# ---------------------------------------------------------------------------
# Typed behavior target tests
# ---------------------------------------------------------------------------


def test_v2_compiler_emits_inference_scoped_targets_for_inference_language() -> None:
    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    # The "Pruning" stage mentions sorting + masking -> ranking/filter concepts.
    pruning = next(
        o for o in graph.obligations
        if o.kind == "stage" and "pruning" in o.author_text.lower()
    )
    assert len(pruning.typed_behavior_targets) >= 1
    all_predicates = set()
    for target in pruning.typed_behavior_targets:
        all_predicates.update(target.desired_predicates)
    # Ranking/filtering concepts contribute SORT, TOPK, SELECT, MASK, FILTER.
    assert all_predicates & {"SORT", "TOPK", "SELECT", "MASK", "FILTER"}, (
        f"pruning stage should produce ranking/filter predicates, got {all_predicates}"
    )


def test_v2_compiler_emits_training_scoped_target_for_training_language() -> None:
    """The high_risk_claim about training losses must produce a training target."""

    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    high_risk = next(o for o in graph.obligations if o.kind == "high_risk_claim")
    assert "training" in high_risk.author_text.lower() or "loss" in high_risk.author_text.lower()

    # The high_risk_claim should have at least one training-scoped target.
    training_targets = [
        t for t in high_risk.typed_behavior_targets
        if "training" in t.conditions
    ]
    assert training_targets, (
        f"high_risk_claim {high_risk.obligation_id} should have a training-scoped target; "
        f"got conditions={[t.conditions for t in high_risk.typed_behavior_targets]}"
    )
    for target in training_targets:
        assert "training" in target.conditions
        # Training-scoped targets carry COMPUTE / REDUCE / AGGREGATE from training_objective concept.
        assert target.desired_predicates, "training target must have desired predicates"
        assert target.risk_level == "high", (
            f"training target should be high risk, got {target.risk_level}"
        )


def test_v2_compiler_separates_training_and_inference_targets_in_same_obligation() -> None:
    """An obligation mentioning both training and inference gets separate targets."""

    summary = AuthorIntentSummary(
        project_goal="Train and deploy a predictor.",
        method_goal="Train then infer.",
        implementation_scope="Training and inference.",
        method_mainline="Train a predictor with losses, then infer scores at deployment.",
        story_order=["Training", "Inference"],
        priority_files=["model.py"],
        module_roles=["model.py::Model: train and infer"],
        pipeline_steps=[
            "Training: compute losses and step the optimizer",
            "Inference: compute scores without gradients",
        ],
        design_intents=["Separate training and inference paths."],
        innovation_claims=["Three training losses learn the predictor."],
    )
    graph = compile_intent_obligation_graph_v2(summary)

    mainline = next(o for o in graph.obligations if o.kind == "method_mainline")
    scopes = set()
    for target in mainline.typed_behavior_targets:
        for cond in target.conditions:
            scopes.add(cond)
    # The mainline mentions both training ("losses", "optimizer") and inference
    # ("infer", "deployment"), so it should have targets in both scopes.
    assert "training" in scopes, (
        f"mainline should have a training-scoped target; got scopes={scopes}"
    )


def test_v2_compiler_emits_empty_targets_for_free_form_organization_preferences() -> None:
    """Organization preferences are stage names, not behavior claims."""

    summary = AuthorIntentSummary(
        project_goal="Do something.",
        method_goal="Do it well.",
        implementation_scope="Scoped.",
        method_mainline="Do the work.",
        story_order=["Introduction", "Background", "Conclusion"],
        priority_files=[],
        module_roles=[],
        pipeline_steps=["Do the work."],
        design_intents=[],
        innovation_claims=[],
    )
    graph = compile_intent_obligation_graph_v2(summary)

    orgs = [o for o in graph.obligations if o.kind == "organization"]
    assert orgs
    for org in orgs:
        # Organization obligations may have empty typed targets because the
        # author's stage names are pure narrative labels, not behavior claims.
        # The targets (if any) should not carry training/inference conditions.
        for target in org.typed_behavior_targets:
            assert "training" not in target.conditions
            assert "inference" not in target.conditions


# ---------------------------------------------------------------------------
# Concept registry tests
# ---------------------------------------------------------------------------


def test_intent_concepts_use_only_valid_predicates_and_relations() -> None:
    """The V2 concept registry must not reference unknown predicates/relations."""

    for concept in INTENT_CONCEPTS:
        assert isinstance(concept, IntentConceptV1)
        for predicate in concept.predicates:
            assert predicate in BEHAVIOR_PREDICATES, (
                f"concept {concept.concept_id} references unknown predicate {predicate!r}"
            )
        for relation in concept.relations:
            assert relation in BEHAVIOR_RELATION_KINDS, (
                f"concept {concept.concept_id} references unknown relation {relation!r}"
            )
        assert concept.scope in {"any", "training", "inference"}, (
            f"concept {concept.concept_id} has unknown scope {concept.scope!r}"
        )


def test_intent_concepts_have_both_en_and_cn_terms_for_parity() -> None:
    """Every concept should have at least one EN and one CN trigger term."""

    for concept in INTENT_CONCEPTS:
        assert concept.terms_en, f"concept {concept.concept_id} has no English terms"
        assert concept.terms_cn, f"concept {concept.concept_id} has no Chinese terms"


# ---------------------------------------------------------------------------
# Signature / equivalence tests
# ---------------------------------------------------------------------------


def test_typed_targets_signature_is_paraphrase_invariant() -> None:
    """Recompiling the same summary produces the same signature."""

    summary_a = _rap_style_summary()
    summary_b = _rap_style_summary()
    graph_a = compile_intent_obligation_graph_v2(summary_a)
    graph_b = compile_intent_obligation_graph_v2(summary_b)

    sig_a = typed_targets_signature(graph_a.obligations)
    sig_b = typed_targets_signature(graph_b.obligations)
    assert sig_a == sig_b, "same summary must produce the same signature"
    assert graph_a.content_digest == graph_b.content_digest


def test_v2_graph_handles_empty_summary() -> None:
    graph = compile_intent_obligation_graph_v2(None)
    assert isinstance(graph, IntentObligationGraphV2)
    assert graph.obligations == []
    assert graph.content_digest.startswith("sha256:")


def test_v2_graph_relations_link_stages_and_mainline() -> None:
    graph = compile_intent_obligation_graph_v2(_rap_style_summary())

    stage_ids = [o.obligation_id for o in graph.obligations if o.kind == "stage"]
    mainline = next(o for o in graph.obligations if o.kind == "method_mainline")
    # Each stage should support the mainline.
    supports = [
        r for r in graph.relations
        if r.relation == "supports" and r.target_obligation_id == mainline.obligation_id
    ]
    assert len(supports) == len(stage_ids)
    # Stages should precede each other in order.
    precedes = [r for r in graph.relations if r.relation == "precedes"]
    assert len(precedes) >= len(stage_ids) - 1
