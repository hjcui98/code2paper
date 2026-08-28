"""WP-B integration tests for argument brief mainline wiring."""

from __future__ import annotations

from code2paper.agentic.evidence_compiler_v3 import AtomicClaimSetV3, AtomicClaimV3
from code2paper.agentic.method_argument_brief_compiler import compile_method_argument_briefs
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
)
from code2paper.agentic.method_architect import build_method_section_plan_with_product_readiness
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.agentic.intent_compiler_v2 import IntentObligationGraphV2
from code2paper.agentic.writer_view_projection import build_writer_view_from_argument_briefs


def _fixture_bundle():
    obligation_id = "O-PARTIAL-01"
    statement = (
        "Apply DyGMamba softmax routing to temporal embeddings. "
        "Inspired by Ebbinghaus forgetting dynamics."
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snap",
        project_tree_hash="tree",
        evidence_packet_digest="sha256:packets",
        code_fact_digest="sha256:facts",
        claims=[
            AtomicClaimV3(
                claim_id="C-ROUTE",
                canonical_text="DyGMamba.compute normalizes F.softmax routing logits.",
                fact_ids=["F1"],
                covers_obligation_ids=[obligation_id],
                direct_evidence_ids=["S1"],
                relation_evidence_ids=[],
                allowed_wording_boundary="bounded",
                canonical_identity="sha256:claim",
            )
        ],
        content_digest="sha256:claims",
    )
    completeness = MethodCompletenessMatrixV1(
        items=(
            MethodCompletenessItemV1(
                obligation_id=obligation_id,
                role="implementation",
                statement=statement,
                status="partially_supported_by_repository",
                matched_fact_ids=("F1",),
                matched_span_ids=("S1",),
            ),
        ),
        content_digest="sha256:completeness",
    )
    intent = IntentObligationGraphV2(
        obligations=[
            {
                "obligation_id": obligation_id,
                "kind": "method_mainline",
                "priority": "must_cover",
                "source_field": "method_mainline",
                "author_text": statement,
                "typed_behavior_targets": [],
            }
        ],
    )
    spine = (
        AuthorStoryNodeV1(
            story_node_id=f"story:{obligation_id}",
            title="Routing",
            author_statement=statement,
            linked_obligation_ids=(obligation_id,),
            evidence_lane="repository_partial",
        ),
    )
    briefs = compile_method_argument_briefs(
        claims=claims,
        completeness=completeness,
        coverage=None,
        intent_graph=intent,
        story_spine=spine,
    )
    return claims, completeness, spine, briefs


def test_writer_view_briefs_xor_concepts():
    claims, completeness, spine, briefs = _fixture_bundle()
    plan, _, _ = build_method_section_plan_with_product_readiness(
        claims=claims,
        completeness=completeness,
        story_spine=spine,
        argument_briefs=briefs,
    )
    section = plan.sections[0]
    view = build_writer_view_from_argument_briefs(
        heading=section.heading,
        reader_question=section.reader_question,
        section_goal="Explain routing.",
        briefs=list(briefs.briefs),
        callback_opportunities=[],
        primary_brief_ids=tuple(section.primary_brief_ids),
    )
    assert view.positive_briefs or view.caveated_briefs
    assert not view.positive_concepts
    assert not view.positive_propositions
    assert view.allowed_brief_ids


def test_brief_callback_prototype_targets_unlicensed_clauses():
    from code2paper.agentic.publication_method_writer import _brief_callback_prototype_payload

    _, _, _, briefs = _fixture_bundle()
    payload = _brief_callback_prototype_payload(section_briefs=list(briefs.briefs))
    assert payload["brief_binding"]
    assert payload["target_brief_ids"]
    assert payload["target_clause_ids"]
    assert payload["missing_parts"]
    assert payload["evidence_refs_used"]
    assert payload["candidate_symbols_or_terms"]
    assert {
        "DyGMamba", "softmax", "Ebbinghaus", "forgetting", "embeddings", "routing",
    } & set(payload["candidate_symbols_or_terms"])
    assert "which repository evidence or author confirmation" not in (
        str(payload["exact_question"]).casefold()
    )
    assert "before its prose can leave the candidate lane" not in (
        str(payload["why_needed_for_reader"]).casefold()
    )
    assert "concept_binding" not in payload


def test_resolve_baseline_spans_from_target_brief_ids():
    from code2paper.agentic.writing_callback_fulfillment import resolve_request_baseline_spans
    from code2paper.agentic.method_argument_models import WritingResearchRequestV1

    _, _, _, briefs = _fixture_bundle()
    brief = briefs.briefs[0]
    request = WritingResearchRequestV1(
        request_id="request:brief:baseline",
        section_id="MA-S1",
        argument_unit_id="MA-S1:unit",
        missing_rhetorical_move="mechanism_overview",
        exact_question="Which evidence resolves the unlicensed clause?",
        required_authority_lane="executable_hard",
        candidate_symbols_or_terms=("DyGMamba",),
        target_brief_ids=(brief.brief_id,),
        evidence_refs_used=(f"claim:{brief.claim_ids[0]}",),
        priority="high",
    )
    spans, reasons = resolve_request_baseline_spans(
        request,
        argument_briefs=briefs,
        require_resolvable=False,
    )
    assert spans
    assert "baseline_binding_missing" not in reasons


def test_deferred_briefs_do_not_satisfy_required_primary():
    from code2paper.llm.section_writer import _publication_contract_failures
    from code2paper.llm.response_schemas import PublicationMethodSectionOutputV1

    output = PublicationMethodSectionOutputV1(
        section_id="MA-S1",
        heading_text="Overview",
        section_markdown="## Overview\n\nOne mechanism sentence.",
        rendered_brief_ids=(),
        deferred_brief_ids=("brief:primary",),
        rendered_concept_keys=(),
        deferred_concept_keys=(),
        rendered_proposition_ids=(),
        deferred_proposition_ids=(),
        used_argument_unit_ids=(),
        used_claim_ids=(),
        used_equation_ids=(),
        used_configuration_ids=(),
        completed_rhetorical_moves=(),
        new_research_requests=(),
    )
    failures = _publication_contract_failures(
        output,
        expected_section_id="MA-S1",
        contract={
            "primary_brief_ids": ("brief:primary",),
            "allowed_brief_ids": ("brief:primary",),
        },
    )
    assert any(failure.startswith("missing_required_briefs:") for failure in failures)
    from code2paper.llm.section_writer import _hard_publication_binding_failures

    assert _hard_publication_binding_failures(failures) == []


def test_markdown_repeated_caveat_tokens_is_headings_only():
    from code2paper.agentic.publication_method_writer import _markdown_has_non_heading_body

    markdown = "## Overview\n\n(intended, partial, pending)\n(intended, partial, pending)\n"
    assert not _markdown_has_non_heading_body(markdown)


def test_pending_caveat_shell_is_not_accepted_as_section_body():
    from code2paper.agentic.publication_method_writer import (
        _looks_like_caveat_shell,
        _section_output_acceptable,
    )

    markdown = "## Overview\n\nPending confirmation."
    assert _looks_like_caveat_shell(markdown)
    assert not _section_output_acceptable(markdown, expected_heading="Overview")


def test_substantive_caveated_mechanism_is_not_a_shell():
    from code2paper.agentic.publication_method_writer import _looks_like_caveat_shell

    markdown = (
        "## Overview\n\n"
        "The time interval controls the state update, although the intended "
        "monotonicity remains pending confirmation."
    )
    assert not _looks_like_caveat_shell(markdown)


def test_html_br_fused_heading_is_not_headings_only():
    """LinearRAG 100052 MA-S2: Writer fused heading and body with ``<br><br>``
    on one line. That is representation damage; Candidate must keep the body."""
    from code2paper.agentic.publication_method_writer import (
        _markdown_has_non_heading_body,
        _normalize_section_heading_breaks,
        _section_output_acceptable,
    )

    heading = (
        "First retrieval stage: relevant entity activation via local semantic bridging"
    )
    fused = (
        f"## {heading}<br><br>The first retrieval stage activates relevant "
        "entities through local semantic bridging. The scoring function "
        "returns entity weights and an activated entity set."
    )
    assert _markdown_has_non_heading_body(fused)
    normalized = _normalize_section_heading_breaks(fused, expected_heading=heading)
    assert normalized.startswith(f"## {heading}\n")
    assert "The first retrieval stage activates" in normalized
    assert _section_output_acceptable(fused, expected_heading=heading)


def test_period_fused_heading_is_not_headings_only():
    from code2paper.agentic.publication_method_writer import (
        _looks_like_caveat_shell,
        _markdown_has_non_heading_body,
        _normalize_section_heading_breaks,
        _section_output_acceptable,
    )

    heading = "Retrieval and embedding preparation"
    fused = (
        f"## {heading}. The intended retrieval stage uses a dense encoder "
        "to fetch candidate passages and their pre-computed embeddings."
    )
    normalized = _normalize_section_heading_breaks(fused, expected_heading=heading)
    assert normalized.startswith(f"## {heading}\n")
    assert "dense encoder" in normalized
    assert _markdown_has_non_heading_body(fused)
    assert _section_output_acceptable(fused, expected_heading=heading)

    shell = (
        f"## Embedding-based reranking formulation and overall framework.\n "
        "No authorized method operations are currently available for this section. "
        "The embedding-based reranking formulation and overall framework will be "
        "described once the repository-supported operations are authorized."
    )
    assert _looks_like_caveat_shell(shell)


def test_empty_anchor_move_is_not_anchored():
    from code2paper.agentic.method_architect import resolve_move_authority_proofs
    from code2paper.agentic.method_argument_models import (
        MethodArgumentUnitV1,
        ObligationMoveAssignmentV1,
        SectionArgumentGraphV1,
        SectionArgumentMoveV1,
        SemanticArgumentFrameV1,
    )

    section = SectionArgumentGraphV1(
        section_id="MA-S1",
        heading="Overview",
        reader_question="What is the method?",
        argument_unit_ids=("unit-1",),
        moves=(
            SectionArgumentMoveV1(
                move="mechanism_overview",
                required=True,
                argument_unit_ids=("unit-1",),
            ),
        ),
    )
    unit = MethodArgumentUnitV1(
        argument_unit_id="unit-1",
        section_role="mechanism",
        research_question="How does the mechanism work?",
        design_objective="Explain mechanism.",
        source_obligation_ids=("obl-1",),
    )
    proofs = resolve_move_authority_proofs(
        sections=(section,),
        units=(unit,),
        unit_frames={
            "unit-1": SemanticArgumentFrameV1(
                frame_id="frame-1",
                argument_unit_id="unit-1",
            ),
        },
        unit_equation_ids={"unit-1": ()},
        unit_configuration_ids={"unit-1": ()},
        assignments=(
            ObligationMoveAssignmentV1(
                obligation_id="obl-1",
                section_id="MA-S1",
                argument_unit_id="unit-1",
                required_move="mechanism_overview",
                placement_state="assigned",
                status="supported_by_repository",
                next_action="write",
            ),
        ),
    )
    proof = proofs[0]
    assert proof.state != "anchored" or proof.anchor_ids
