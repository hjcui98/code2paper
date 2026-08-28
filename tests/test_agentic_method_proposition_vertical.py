"""Static vertical proof for proposition-first Method authoring."""

from pathlib import Path

from code2paper.agentic.evidence_compiler_v3 import (
    AtomicClaimSetV3,
    AtomicClaimV3,
    CodeFactSetV1,
    CodeFactV1,
    EvidencePacketSetV3,
    EvidencePacketV3,
    EvidenceSpanV3,
)
from code2paper.agentic.final_text_claims import (
    extract_final_text_claims,
    write_final_text_claims,
)
from code2paper.agentic.method_architect import (
    build_method_section_plan_with_product_readiness,
)
from code2paper.agentic.method_argument_models import (
    MethodCompletenessItemV1,
    MethodCompletenessMatrixV1,
)
from code2paper.agentic.method_product_models import AuthorStoryNodeV1
from code2paper.agentic.method_proposition_compiler import compile_method_propositions
from code2paper.agentic.method_proposition_models import MethodPropositionProposalV1
from code2paper.agentic.proposition_semantic_aligner import (
    align_sentence_to_section_propositions,
)
from code2paper.agentic.publication_method_writer import _build_product_bundle
from code2paper.agentic.text_evidence_validator import (
    validate_text_evidence,
    write_text_evidence_validation,
)
from code2paper.agentic.trust_contracts import AuthoringInputProjection, ProjectedClaim
from code2paper.agentic.writer_view_projection import build_writer_view
from code2paper.core.schemas import EvidenceItem, RawEvidencePack, SourceType
from code2paper.llm.writer_section_repair import (
    assess_writer_section_progress,
    build_writer_section_repair_packet,
    repair_is_monotonic,
)


def test_proposition_first_authoring_vertical_contract(tmp_path: Path) -> None:
    span = EvidenceSpanV3(
        span_id="S1", snapshot_id="snapshot", project_tree_hash="tree",
        path="encoder.py", symbol="Encoder.read", line_start=1, line_end=2,
        exact_excerpt="features = read(configured_input)",
        excerpt_digest="sha256:excerpt", file_digest="sha256:file", role="anchor",
    )
    packets = EvidencePacketSetV3(
        repo_snapshot_id="snapshot", project_tree_hash="tree",
        packets=[EvidencePacketV3(
            packet_id="EP1", obligation_tags=["O-READ"], scope="Encoder.read",
            anchor_span_ids=["S1"], spans=[span], source_digest="sha256:packet",
        )], content_digest="sha256:packets",
    )
    fact = CodeFactV1(
        fact_id="F1", subject="Encoder.read", predicate="reads",
        object="configured input", scope="Encoder.read", direct_span_ids=["S1"],
        exact_source_digest="sha256:excerpt", canonical_identity="sha256:fact",
    )
    facts = CodeFactSetV1(
        repo_snapshot_id="snapshot", project_tree_hash="tree",
        evidence_packet_digest=packets.content_digest, facts=[fact],
        content_digest="sha256:facts",
    )
    claim = AtomicClaimV3(
        claim_id="C1", canonical_text="The encoder reads the configured input.",
        fact_ids=["F1"], covers_obligation_ids=["O-READ"],
        direct_evidence_ids=["S1"],
        allowed_wording_boundary="the encoder reads only the configured input",
        canonical_identity="sha256:claim", status="supported",
    )
    claims = AtomicClaimSetV3(
        repo_snapshot_id="snapshot", project_tree_hash="tree",
        evidence_packet_digest=packets.content_digest,
        code_fact_digest=facts.content_digest, claims=[claim],
        content_digest="sha256:claims",
    )
    completeness = MethodCompletenessMatrixV1(items=(
        MethodCompletenessItemV1(
            obligation_id="O-READ", statement="Read the configured representation.",
            status="supported_by_repository", claim_ids=("C1",),
            matched_fact_ids=("F1",), matched_span_ids=("S1",),
        ),
        MethodCompletenessItemV1(
            obligation_id="O-DEPLOY", statement="The intended deployment avoids rendering.",
            status="author_confirmation_required", reason="repository support is absent",
        ),
    ))
    story = (AuthorStoryNodeV1(
        story_node_id="ST-1", title="Method overview",
        author_statement="Explain representation use and intended deployment.",
        linked_obligation_ids=("O-READ", "O-DEPLOY"),
        evidence_lane="author_intent_unverified",
    ),)

    def architect(cluster):
        if cluster.origin == "repository_evidence":
            return MethodPropositionProposalV1(
                cluster_id=cluster.cluster_id, used_claim_ids=("C1",),
                used_fact_ids=("F1",), reader_subject="the encoder",
                transformation="consumes the configured representation",
                source_statement_fragments=(cluster.source_statements[0],),
            )
        return MethodPropositionProposalV1(
            cluster_id=cluster.cluster_id, reader_subject="the deployment path",
            transformation="is intended to avoid rendering",
            source_statement_fragments=(cluster.source_statements[0],),
        )

    propositions, sidecar, _clusters = compile_method_propositions(
        claims=claims, facts=facts, packets=packets, completeness=completeness,
        story_spine=story, proposal_architect=architect,
    )
    plan, readiness, _trace = build_method_section_plan_with_product_readiness(
        claims=claims, completeness=completeness, story_spine=story,
        propositions=propositions,
    )
    assert len(propositions.propositions) == 2
    assert len(sidecar.bindings) == 2
    assert any(unit.positive_proposition_ids for unit in plan.argument_units), (
        [(item.proposition_id, item.source_obligation_ids) for item in propositions.propositions],
        [(item.argument_unit_id, item.source_obligation_ids, item.claim_ids) for item in plan.argument_units],
    )
    assert any(unit.caveated_proposition_ids for unit in plan.argument_units), (
        propositions.model_dump(mode="json"), plan.model_dump(mode="json")
    )

    view = build_writer_view(
        heading=plan.sections[0].heading,
        reader_question=plan.sections[0].reader_question,
        section_goal="Explain the supported representation flow and intended deployment.",
        propositions=list(propositions.propositions), callback_opportunities=[],
    )
    initial = "## Method overview\n\nPending confirmation, we aim to explain deployment."
    initial_progress, initial_failures = assess_writer_section_progress(
        initial, writer_view=view.model_dump(mode="json")
    )
    packet = build_writer_section_repair_packet(
        section_id=plan.sections[0].section_id, attempt=1,
        incumbent_text=initial, writer_view=view.model_dump(mode="json"),
        progress=initial_progress, failures=initial_failures,
    )
    assert packet.missing_proposition_ids

    repaired = (
        "## Method overview\n\n"
        "The configured representation is consumed by the encoder. "
        "Our intended deployment path avoids rendering."
    )
    repaired_progress, repaired_failures = assess_writer_section_progress(
        repaired, writer_view=view.model_dump(mode="json")
    )
    assert repair_is_monotonic(initial_progress, repaired_progress)
    assert "empty_candidate_promise" not in repaired_failures

    projection = AuthoringInputProjection(
        project_id="fixture", method_name="Method", author_goal="Explain the method.",
        implementation_scope="fixture", projection_digest="sha256:projection",
        projected_claims=[ProjectedClaim(
            claim_id="C1", claim_text=claim.canonical_text,
            support_status="supported", direct_evidence_ids=["E1"],
            supported_fragment=claim.canonical_text,
            allowed_wording_boundary=claim.allowed_wording_boundary,
            input_digest="sha256:claim",
        )],
    )
    final_claims = extract_final_text_claims(repaired, projection)
    positive = next(item for item in propositions.propositions if item.may_enter_verified)
    candidate = next(item for item in propositions.propositions if item.requires_caveat)
    updated_claims = []
    for item in final_claims.atomic_claims:
        closed = [candidate] if "intended" in item.text.casefold() else [positive]
        alignment = align_sentence_to_section_propositions(
            item.text, closed,
            semantic_aligner=lambda _payload, closed=closed: {
                "status": "matched",
                "matched_proposition_ids": [closed[0].proposition_id],
                "preserved_roles": ["subject", "transformation"],
                "missing_roles": [],
            },
        )
        assert alignment.status == "matched"
        updated_claims.append(item.model_copy(update={
            "candidate_method_proposition_ids": list(alignment.matched_proposition_ids),
        }))
    final_claims = final_claims.model_copy(update={"atomic_claims": updated_claims})
    raw = RawEvidencePack(
        project_id="fixture", project_root=".", evidence_items=[EvidenceItem(
            evidence_id="E1", source_type=SourceType.SOURCE, path="encoder.py",
            symbol="Encoder.read", content_summary="The encoder reads the configured input.",
            line_start=1, line_end=2, confidence=1.0,
        )],
    )
    validation = validate_text_evidence(
        final_claims=final_claims, projection=projection, raw_evidence=raw,
        proposition_claim_ids={
            binding.proposition_id: binding.claim_ids for binding in sidecar.bindings
        },
        candidate_only_proposition_ids={candidate.proposition_id},
    )
    assert validation.supported_claims == 1
    assert validation.caveated_claims == 1

    claims_path = tmp_path / "final_claims.json"
    validation_path = tmp_path / "validation.json"
    projection_path = tmp_path / "projection.json"
    write_final_text_claims(claims_path, final_claims)
    write_text_evidence_validation(validation_path, validation)
    projection_path.write_text(projection.model_dump_json(), encoding="utf-8")
    candidate_text, verified_text, review, _queue, _split = _build_product_bundle(
        final_text=repaired,
        accepted=[(plan.sections[0].section_id, repaired, "sha256:writer")],
        plan=plan, completeness=completeness, readiness=readiness,
        research_requests=[], validation_paths={
            "final_text_claims": str(claims_path),
            "text_evidence_validation": str(validation_path),
            "authoring_projection_v1": str(projection_path),
        },
    )
    assert "intended deployment" in candidate_text
    assert "configured representation" in verified_text
    assert "intended deployment" not in verified_text
    assert review
